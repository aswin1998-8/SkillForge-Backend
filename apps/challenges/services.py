"""Challenge assignment and submission services."""

from __future__ import annotations

from datetime import date

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from apps.challenges.models import (
    Challenge,
    ChallengeAttempt,
    ChallengeDebrief,
    ChallengeFollowUp,
    ChallengeRubricItem,
    ConfidenceRating,
    DailyChallenge,
    Submission,
)
from apps.diagnostics.models import DiagnosticRoadmapItem
from apps.gaps.models import UserSkillGap
from apps.gaps.services import upsert_user_skill_gap
from apps.roles.models import Skill
from apps.users.models import User


def _skill_slug_from_topic(topic: str) -> str:
    return str(topic or "").strip().lower().replace(" ", "_")[:255]


def _update_gaps_for_challenge(
    *,
    user: User,
    challenge: Challenge,
    status: str,
    evidence_source_type: str,
    evidence_source_id: str,
    evidence_summary: str,
) -> None:
    topics = (
        DiagnosticRoadmapItem.objects.filter(user=user, challenge=challenge)
        .values_list("topic", flat=True)
        .distinct()
    )
    for topic in topics:
        slug = _skill_slug_from_topic(topic)
        if not slug:
            continue
        skill = Skill.objects.filter(slug=slug).first()
        if skill is None:
            skill, _ = Skill.objects.get_or_create(
                slug=slug,
                defaults={
                    "name": slug.replace("_", " ").title(),
                    "description": f"Practice competency: {slug.replace('_', ' ')}",
                },
            )
        upsert_user_skill_gap(
            user=user,
            skill=skill,
            status=status,
            evidence_source_type=evidence_source_type,
            evidence_source_id=evidence_source_id,
            evidence_summary=evidence_summary,
        )


def _maybe_increment_diagnostic_cycle(*, user: User) -> None:
    """When the last roadmap step closes, bump difficulty for the next diagnostic."""
    if DiagnosticRoadmapItem.objects.filter(user=user).exclude(status="closed").exists():
        return
    if not DiagnosticRoadmapItem.objects.filter(user=user).exists():
        return
    profile = getattr(user, "profile", None)
    if profile is None:
        return
    profile.diagnostic_difficulty_bump = int(profile.diagnostic_difficulty_bump or 0) + 1
    profile.diagnostic_cycle = int(profile.diagnostic_cycle or 1) + 1
    profile.save(
        update_fields=[
            "diagnostic_difficulty_bump",
            "diagnostic_cycle",
            "updated_at",
        ]
    )


def get_challenge_or_404(challenge_id: int) -> Challenge:
    try:
        return Challenge.objects.prefetch_related(
            "challenge_skills__skill",
            "rubric_items__follow_ups",
            "model_answer",
        ).get(
            pk=challenge_id,
            is_active=True,
        )
    except Challenge.DoesNotExist as exc:
        raise NotFound("Challenge not found.") from exc


def _preferred_difficulty(user: User) -> int | None:
    last = (
        ChallengeAttempt.objects.filter(user=user, status=ChallengeAttempt.Status.COMPLETED)
        .select_related("debrief", "challenge", "submission")
        .order_by("-completed_at")
        .first()
    )
    if last is None:
        return None
    base = last.challenge.difficulty
    submission = getattr(last, "submission", None)
    grading = (getattr(submission, "metadata", None) or {}).get("grading") or {}
    score = grading.get("score")
    if isinstance(score, (int, float)):
        if score >= 0.7:
            return min(base + 1, 5)
        if score < 0.4:
            return max(base - 1, 1)
    debrief = getattr(last, "debrief", None)
    if debrief and debrief.checklist_score is not None:
        if debrief.checklist_score >= 0.7:
            return min(base + 1, 5)
        if debrief.checklist_score < 0.4:
            return max(base - 1, 1)
    return base


def _direction_for_user(user: User) -> list[str]:
    profile = getattr(user, "profile", None)
    goal = (getattr(profile, "technical_goal", "") or "").lower()
    role = (getattr(profile, "current_role", "") or "").lower()
    if "switch" in goal or "new role" in goal:
        if "front" in role:
            return ["fe_to_be", "backend_mastery"]
        return ["be_to_fe", "frontend_mastery"]
    if "front" in role:
        return ["frontend_mastery"]
    if "back" in role:
        return ["backend_mastery"]
    return ["frontend_mastery", "backend_mastery"]


def get_active_roadmap_item(*, user: User) -> DiagnosticRoadmapItem | None:
    return (
        DiagnosticRoadmapItem.objects.filter(user=user)
        .exclude(status="closed")
        .order_by("priority", "id")
        .select_related("challenge")
        .first()
    )


def get_unlocked_challenge_id(*, user: User) -> int | None:
    """
    Sequential unlock: only the first non-closed roadmap challenge is playable.
    Returns None when the user has no roadmap (no sequential lock) or all steps are done.
    """
    if not DiagnosticRoadmapItem.objects.filter(user=user).exists():
        return None
    item = get_active_roadmap_item(user=user)
    if item is None:
        return None
    if item.challenge_id:
        return item.challenge_id
    # Roadmap step exists but isn't linked yet — unlock the resolved fallback.
    return _pick_fallback_challenge(user=user).id


def challenge_is_locked(*, user: User, challenge_id: int) -> tuple[bool, int | None]:
    unlocked_id = get_unlocked_challenge_id(user=user)
    if unlocked_id is None:
        return False, None
    return challenge_id != unlocked_id, unlocked_id


def _pick_fallback_challenge(*, user: User) -> Challenge:
    open_gap_skill_ids = list(
        UserSkillGap.objects.filter(user=user)
        .exclude(status=UserSkillGap.Status.CLOSED)
        .values_list("skill_id", flat=True)
    )
    roadmap_topics = list(
        DiagnosticRoadmapItem.objects.filter(user=user)
        .exclude(status="closed")
        .values_list("topic", flat=True)[:8]
    )
    completed_challenge_ids = ChallengeAttempt.objects.filter(
        user=user,
        status__in=[ChallengeAttempt.Status.COMPLETED, ChallengeAttempt.Status.SUBMITTED],
    ).values_list("challenge_id", flat=True)

    qs = Challenge.objects.filter(is_active=True).exclude(id__in=completed_challenge_ids)
    directions = _direction_for_user(user)
    if directions:
        direction_q = Q()
        for d in directions:
            direction_q |= Q(directions__contains=[d])
        directed = qs.filter(direction_q)
        if directed.exists():
            qs = directed

    preferred = _preferred_difficulty(user)
    if preferred is not None:
        qs = qs.filter(
            difficulty__gte=max(preferred - 1, 1),
            difficulty__lte=min(preferred + 1, 5),
        )

    if open_gap_skill_ids:
        qs = qs.filter(challenge_skills__skill_id__in=open_gap_skill_ids).annotate(
            gap_match_count=Count(
                "challenge_skills",
                filter=Q(challenge_skills__skill_id__in=open_gap_skill_ids),
            )
        ).order_by("-gap_match_count", "difficulty", "id")
    elif roadmap_topics:
        topic_q = Q()
        for topic in roadmap_topics:
            human = topic.replace("_", " ")[:20]
            topic_q |= Q(title__icontains=human) | Q(scenario__icontains=human)
            topic_q |= Q(workspace_config__competency_areas__contains=[topic])
        topic_qs = qs.filter(topic_q)
        qs = topic_qs if topic_qs.exists() else qs
        qs = qs.order_by("difficulty", "id")
    else:
        qs = qs.order_by("difficulty", "id")

    challenge = qs.distinct().first()
    if challenge is None:
        challenge = Challenge.objects.filter(is_active=True).order_by("difficulty", "id").first()
    if challenge is None:
        raise ValidationError("No active challenges available.")
    return challenge


def resolve_current_challenge(*, user: User) -> Challenge:
    """Current unlocked challenge from roadmap, or a fallback catalog pick."""
    item = get_active_roadmap_item(user=user)
    if item is not None:
        if item.status == "not_started":
            item.status = "in_progress"
            item.save(update_fields=["status"])
        if item.challenge_id:
            return item.challenge
    return _pick_fallback_challenge(user=user)


@transaction.atomic
def get_or_assign_today_challenge(*, user: User, on_date: date | None = None) -> DailyChallenge:
    """
    Returns the user's current unlocked challenge assignment.
    Kept under the /challenges/today/ endpoint for compatibility, but no longer
    gates progress to one challenge per calendar day.
    """
    today = on_date or timezone.localdate()
    challenge = resolve_current_challenge(user=user)

    existing = (
        DailyChallenge.objects.select_related("challenge")
        .prefetch_related("challenge__challenge_skills__skill")
        .filter(user=user, date=today)
        .first()
    )
    if existing:
        if existing.challenge_id != challenge.id:
            existing.challenge = challenge
            existing.status = DailyChallenge.Status.AVAILABLE
            existing.save(update_fields=["challenge", "status", "updated_at"])
        return (
            DailyChallenge.objects.select_related("challenge")
            .prefetch_related("challenge__challenge_skills__skill")
            .get(pk=existing.pk)
        )

    return DailyChallenge.objects.create(
        user=user,
        challenge=challenge,
        date=today,
        status=DailyChallenge.Status.AVAILABLE,
    )


@transaction.atomic
def submit_challenge(
    *,
    user: User,
    challenge_id: int,
    payload: dict,
) -> ChallengeAttempt:
    challenge = get_challenge_or_404(challenge_id)
    locked, unlocked_id = challenge_is_locked(user=user, challenge_id=challenge.id)
    if locked:
        raise ValidationError(
            "Complete your current roadmap challenge before unlocking the next one."
        )

    today = timezone.localdate()
    daily = DailyChallenge.objects.filter(user=user, date=today).first()
    if daily is None or daily.challenge_id != challenge.id:
        daily = get_or_assign_today_challenge(user=user, on_date=today)
        if daily.challenge_id != challenge.id:
            # Force pointer onto the challenge being submitted (unlocked).
            daily.challenge = challenge
            daily.status = DailyChallenge.Status.AVAILABLE
            daily.save(update_fields=["challenge", "status", "updated_at"])

    finished = (
        ChallengeAttempt.objects.filter(
            user=user,
            challenge=challenge,
            status__in=[
                ChallengeAttempt.Status.SUBMITTED,
                ChallengeAttempt.Status.COMPLETED,
            ],
        )
        .select_related("submission")
        .order_by("-started_at")
        .first()
    )
    retrying_failed = _attempt_failed_grading(finished)

    if finished and not retrying_failed:
        raise ValidationError("This challenge was already submitted.")

    if daily.status in {DailyChallenge.Status.SUBMITTED, DailyChallenge.Status.COMPLETED}:
        if retrying_failed and daily.challenge_id == challenge.id:
            daily.status = DailyChallenge.Status.AVAILABLE
            daily.save(update_fields=["status", "updated_at"])
        else:
            raise ValidationError("This challenge was already submitted.")

    if retrying_failed and finished is not None:
        attempt = finished
    else:
        attempt = (
            ChallengeAttempt.objects.filter(
                user=user,
                challenge=challenge,
                status=ChallengeAttempt.Status.IN_PROGRESS,
            )
            .order_by("-started_at")
            .first()
        )
        if attempt is None:
            attempt = ChallengeAttempt.objects.create(
                user=user,
                challenge=challenge,
                daily_challenge=daily,
                status=ChallengeAttempt.Status.IN_PROGRESS,
            )

    text_answer = payload.get("text_answer") or ""
    code = payload.get("code") or ""
    architecture_data = payload.get("architecture_data") or {}
    research_data = payload.get("research_data") or {}
    metadata = dict(payload.get("metadata") or {})

    grading = _grade_challenge_submission(
        challenge=challenge,
        text_answer=text_answer,
        code=code,
        architecture_data=architecture_data,
        research_data=research_data,
    )
    metadata["grading"] = grading
    passed = _grading_passed(grading)

    Submission.objects.update_or_create(
        attempt=attempt,
        defaults={
            "text_answer": text_answer,
            "code": code,
            "architecture_data": architecture_data,
            "research_data": research_data,
            "metadata": metadata,
        },
    )

    score = float(grading.get("score") or 0)
    summary = (
        f"Graded {challenge.modality}: score {score:.0%}"
        if grading.get("score") is not None
        else f"Completed {challenge.modality} challenge"
    )

    if passed:
        # Passed — lock the attempt and advance the roadmap.
        attempt.status = ChallengeAttempt.Status.COMPLETED
        attempt.completed_at = timezone.now()
        attempt.save(update_fields=["status", "completed_at"])

        daily.status = DailyChallenge.Status.COMPLETED
        daily.save(update_fields=["status", "updated_at"])

        DiagnosticRoadmapItem.objects.filter(
            user=user,
            challenge=challenge,
        ).update(status="closed")

        _update_gaps_for_challenge(
            user=user,
            challenge=challenge,
            status=UserSkillGap.Status.CLOSED,
            evidence_source_type="CHALLENGE_SUBMIT",
            evidence_source_id=str(attempt.id),
            evidence_summary=summary[:200],
        )

        next_item = get_active_roadmap_item(user=user)
        if next_item is not None and next_item.status != "in_progress":
            next_item.status = "in_progress"
            next_item.save(update_fields=["status"])

        _maybe_increment_diagnostic_cycle(user=user)
    else:
        # Failed grade — keep the step open so the user can retry.
        attempt.status = ChallengeAttempt.Status.SUBMITTED
        attempt.completed_at = timezone.now()
        attempt.save(update_fields=["status", "completed_at"])

        daily.status = DailyChallenge.Status.AVAILABLE
        daily.save(update_fields=["status", "updated_at"])

        DiagnosticRoadmapItem.objects.filter(
            user=user,
            challenge=challenge,
        ).update(status="in_progress")

        _update_gaps_for_challenge(
            user=user,
            challenge=challenge,
            status=UserSkillGap.Status.IN_PROGRESS,
            evidence_source_type="CHALLENGE_SUBMIT",
            evidence_source_id=str(attempt.id),
            evidence_summary=summary[:200],
        )

    from apps.sessions.services import record_session

    record_session(
        user=user,
        session_type="CHALLENGE",
        reference_id=attempt.id,
        title=f"Challenge: {challenge.title}",
        summary=summary[:200],
    )

    return (
        ChallengeAttempt.objects.select_related("submission", "challenge", "debrief")
        .prefetch_related("challenge__rubric_items")
        .get(pk=attempt.pk)
    )


def _grading_passed(grading: dict | None) -> bool:
    if not isinstance(grading, dict):
        return False
    if "is_correct" in grading:
        return bool(grading.get("is_correct"))
    score = grading.get("score")
    if score is None:
        return False
    try:
        return float(score) >= 0.5
    except (TypeError, ValueError):
        return False


def _attempt_failed_grading(attempt: ChallengeAttempt | None) -> bool:
    if attempt is None:
        return False
    submission = getattr(attempt, "submission", None)
    if submission is None:
        return True
    grading = (getattr(submission, "metadata", None) or {}).get("grading") or {}
    return not _grading_passed(grading)


def _flatten_research_data(research_data: dict | None) -> str:
    """Turn research workspace fields into plain text for keyword grading."""
    if not isinstance(research_data, dict) or not research_data:
        return ""
    parts: list[str] = []
    for key in ("question", "findings", "synthesis", "source", "notes", "summary"):
        value = research_data.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            parts.append(text)
    # Any other string fields the workspace may send.
    for key, value in research_data.items():
        if key in {"question", "findings", "synthesis", "source", "notes", "summary"}:
            continue
        if isinstance(value, str) and value.strip():
            parts.append(value.strip())
    return "\n".join(parts)


def _flatten_architecture_data(architecture_data: dict | None) -> str:
    """Extract labels/text from React Flow (or similar) architecture payloads."""
    if not isinstance(architecture_data, dict) or not architecture_data:
        return ""
    parts: list[str] = []
    for key in ("summary", "notes", "description", "rationale"):
        value = architecture_data.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(value.strip())

    for node in architecture_data.get("nodes") or []:
        if not isinstance(node, dict):
            continue
        for key in ("id", "type", "label", "name"):
            value = node.get(key)
            if isinstance(value, str) and value.strip():
                parts.append(value.strip())
        data = node.get("data")
        if isinstance(data, dict):
            for key in ("label", "name", "title", "description", "text"):
                value = data.get(key)
                if isinstance(value, str) and value.strip():
                    parts.append(value.strip())

    for edge in architecture_data.get("edges") or []:
        if not isinstance(edge, dict):
            continue
        for key in ("label", "source", "target", "id"):
            value = edge.get(key)
            if isinstance(value, str) and value.strip():
                parts.append(value.strip())
        data = edge.get("data")
        if isinstance(data, dict):
            label = data.get("label")
            if isinstance(label, str) and label.strip():
                parts.append(label.strip())

    return "\n".join(parts)


def _grade_challenge_submission(
    *,
    challenge: Challenge,
    text_answer: str,
    code: str,
    architecture_data: dict,
    research_data: dict,
) -> dict:
    from types import SimpleNamespace

    from apps.core.keyword_grade import grade_open_ended_keywords
    from apps.diagnostics.code_executor import run_test_cases

    modality = challenge.modality
    config = challenge.workspace_config or {}
    model = getattr(challenge, "model_answer", None)
    reference_text = getattr(model, "reference_text", "") if model else ""
    rubric_items = list(challenge.rubric_items.all())
    rubric_points = [i.text for i in rubric_items if i.text]
    rubric_hints = [
        (i.strength_fragment or i.gap_fragment or "") for i in rubric_items if i.text
    ]

    if modality in {Challenge.Modality.CODING, Challenge.Modality.EXPLAIN_CODE}:
        raw_cases = config.get("test_cases")
        if isinstance(raw_cases, list) and raw_cases:
            cases = []
            for i, case in enumerate(raw_cases):
                if not isinstance(case, dict):
                    continue
                cases.append(
                    SimpleNamespace(
                        input=str(case.get("input", "")),
                        expected_output=str(case.get("expected_output", "")),
                        is_hidden=bool(case.get("is_hidden", False)),
                        order=int(case.get("order", i)),
                    )
                )
            if cases:
                language = str(config.get("language") or "python")
                results = run_test_cases(
                    code=code or text_answer,
                    language=language,
                    test_cases=cases,
                )
                passed = all(r.get("passed") for r in results) if results else False
                score = 1.0 if passed else 0.0
                return {
                    "method": "test_execution",
                    "score": score,
                    "is_correct": passed,
                    "test_results": results,
                }

        is_correct, score, detail = grade_open_ended_keywords(
            answer_text=code or text_answer,
            rubric_points=rubric_points,
            rubric_hints=rubric_hints,
            reference_text=reference_text,
        )
        detail["is_correct"] = is_correct
        return detail

    answer_blob = "\n".join(
        part
        for part in [
            text_answer,
            code,
            _flatten_architecture_data(architecture_data),
            _flatten_research_data(research_data),
        ]
        if part and str(part).strip()
    )
    is_correct, score, detail = grade_open_ended_keywords(
        answer_text=answer_blob,
        rubric_points=rubric_points,
        rubric_hints=rubric_hints,
        reference_text=reference_text,
    )
    detail["is_correct"] = is_correct
    return detail


@transaction.atomic
def save_confidence(
    *,
    user: User,
    attempt_id: int,
    score: int,
    note: str = "",
) -> ConfidenceRating:
    if score < 1 or score > 5:
        raise ValidationError({"score": "Score must be between 1 and 5."})
    try:
        attempt = ChallengeAttempt.objects.get(pk=attempt_id, user=user)
    except ChallengeAttempt.DoesNotExist as exc:
        raise NotFound("Challenge attempt not found.") from exc

    rating, _ = ConfidenceRating.objects.update_or_create(
        attempt=attempt,
        defaults={"score": score, "note": note},
    )
    return rating


def get_attempt_for_user(*, user: User, attempt_id: int) -> ChallengeAttempt:
    try:
        return ChallengeAttempt.objects.select_related(
            "challenge",
            "challenge__model_answer",
            "submission",
            "confidence",
            "daily_challenge",
            "debrief",
        ).prefetch_related(
            "challenge__rubric_items__follow_ups",
            "challenge__challenge_skills__skill",
        ).get(pk=attempt_id, user=user)
    except ChallengeAttempt.DoesNotExist as exc:
        raise NotFound("Challenge attempt not found.") from exc


def get_debrief_payload(*, attempt: ChallengeAttempt) -> dict:
    challenge = attempt.challenge
    model = getattr(challenge, "model_answer", None)
    debrief = getattr(attempt, "debrief", None)
    rubric = [
        {
            "id": item.id,
            "text": item.text,
            "order": item.order,
            "follow_ups": [
                {"id": fu.id, "question_text": fu.question_text}
                for fu in item.follow_ups.all()
            ],
        }
        for item in challenge.rubric_items.all()
    ]
    return {
        "attempt_id": attempt.id,
        "status": debrief.status if debrief else "AWAITING_SELF_RATE",
        "reference_text": model.reference_text if model else "",
        "rubric_items": rubric,
        "checklist": debrief.checklist if debrief else {},
        "follow_up_answers": debrief.follow_up_answers if debrief else {},
        "selected_follow_ups": _selected_follow_ups(debrief, challenge) if debrief else [],
        "strengths": debrief.strengths if debrief else [],
        "gaps": debrief.gaps if debrief else [],
        "next_focus": debrief.next_focus if debrief else "",
        "checklist_score": debrief.checklist_score if debrief else None,
    }


def _selected_follow_ups(debrief: ChallengeDebrief | None, challenge: Challenge) -> list[dict]:
    if debrief is None or not debrief.checklist:
        return []
    selected: list[dict] = []
    for item in challenge.rubric_items.all():
        checked = bool(debrief.checklist.get(str(item.id)))
        if checked:
            continue
        for fu in item.follow_ups.all():
            selected.append(
                {
                    "id": fu.id,
                    "rubric_item_id": item.id,
                    "question_text": fu.question_text,
                }
            )
            if len(selected) >= 5:
                return selected
    return selected


@transaction.atomic
def submit_debrief_checklist(*, user: User, attempt_id: int, checklist: dict) -> dict:
    attempt = get_attempt_for_user(user=user, attempt_id=attempt_id)
    debrief, _ = ChallengeDebrief.objects.get_or_create(attempt=attempt)
    cleaned = {str(k): bool(v) for k, v in checklist.items()}
    debrief.checklist = cleaned
    debrief.status = ChallengeDebrief.Status.AWAITING_FOLLOWUPS
    debrief.save(update_fields=["checklist", "status"])
    return get_debrief_payload(attempt=attempt)


@transaction.atomic
def complete_debrief(
    *,
    user: User,
    attempt_id: int,
    follow_up_answers: dict,
) -> dict:
    attempt = get_attempt_for_user(user=user, attempt_id=attempt_id)
    debrief = getattr(attempt, "debrief", None)
    if debrief is None:
        raise ValidationError("Submit checklist before follow-ups.")

    debrief.follow_up_answers = {str(k): str(v) for k, v in follow_up_answers.items()}
    items = list(attempt.challenge.rubric_items.all())
    if not items:
        score = 1.0
        strengths = ["You completed the reflection loop."]
        gaps = []
        next_focus = "Continue with the next unlocked roadmap challenge."
    else:
        checked = sum(1 for i in items if debrief.checklist.get(str(i.id)))
        score = checked / len(items)
        strengths = [
            i.strength_fragment or i.text
            for i in items
            if debrief.checklist.get(str(i.id)) and (i.strength_fragment or i.text)
        ][:3]
        gaps = [
            i.gap_fragment or i.text
            for i in items
            if not debrief.checklist.get(str(i.id)) and (i.gap_fragment or i.text)
        ][:3]
        lowest = next((i for i in items if not debrief.checklist.get(str(i.id))), items[0])
        next_focus = lowest.gap_fragment or f"Focus next on: {lowest.text}"

    debrief.checklist_score = score
    debrief.strengths = strengths
    debrief.gaps = gaps
    debrief.next_focus = next_focus
    debrief.status = ChallengeDebrief.Status.COMPLETED
    debrief.completed_at = timezone.now()
    debrief.save()

    attempt.status = ChallengeAttempt.Status.COMPLETED
    attempt.save(update_fields=["status"])

    if attempt.daily_challenge_id:
        daily = attempt.daily_challenge
        daily.status = DailyChallenge.Status.COMPLETED
        daily.save(update_fields=["status", "updated_at"])

    DiagnosticRoadmapItem.objects.filter(
        user=user,
        challenge=attempt.challenge,
    ).update(status="closed")

    _update_gaps_for_challenge(
        user=user,
        challenge=attempt.challenge,
        status=UserSkillGap.Status.CLOSED,
        evidence_source_type="CHALLENGE_DEBRIEF",
        evidence_source_id=str(attempt.id),
        evidence_summary=next_focus[:200] or f"Closed gap via debrief on {attempt.challenge.title}",
    )

    next_item = get_active_roadmap_item(user=user)
    if next_item is not None and next_item.status != "in_progress":
        next_item.status = "in_progress"
        next_item.save(update_fields=["status"])

    _maybe_increment_diagnostic_cycle(user=user)

    from apps.sessions.services import record_session

    record_session(
        user=user,
        session_type="DEBRIEF",
        reference_id=debrief.id,
        title=f"Debrief: {attempt.challenge.title}",
        summary=next_focus[:200],
    )

    return get_debrief_payload(attempt=attempt)

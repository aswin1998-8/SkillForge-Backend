"""Adaptive diagnostic attempt services."""

from __future__ import annotations

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from apps.ai.services.assessment_service import (
    analyze_transfers,
    evaluate_adaptive_answer,
    explain_skill_gaps,
    generate_adaptive_question,
)
from apps.diagnostics.models import (
    Diagnostic,
    DiagnosticAttempt,
    DiagnosticQuestion,
    DiagnosticResult,
    DiagnosticTurn,
    SkillEvidence,
)
from apps.diagnostics.scoring import (
    classify_from_score,
    classify_gap_status,
    compute_skill_scores,
)
from apps.gaps.models import UserSkillGap
from apps.gaps.services import upsert_user_skill_gap
from apps.roles.models import RoleSkill, Skill, SkillTransfer
from apps.users.models import Profile, User, UserSkill


STAGE_ORDER = [
    DiagnosticAttempt.Stage.FOUNDATION,
    DiagnosticAttempt.Stage.SCENARIO,
    DiagnosticAttempt.Stage.DEBUGGING,
    DiagnosticAttempt.Stage.CODING,
    DiagnosticAttempt.Stage.CODE_REVIEW,
]


def _infer_goal(profile: Profile | None) -> str:
    if not profile:
        return DiagnosticAttempt.Goal.ROLE_SWITCH
    goal = (profile.technical_goal or "").lower()
    if "become better" in goal or "current job" in goal or "current role" in goal:
        return DiagnosticAttempt.Goal.CURRENT_ROLE
    return DiagnosticAttempt.Goal.ROLE_SWITCH


def _slugify_skill_name(name: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in name.strip())
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-") or "skill"


def _skills_list_payload(raw) -> list[dict]:
    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    for item in raw:
        name = str(item or "").strip()
        if not name:
            continue
        out.append({"name": name, "slug": _slugify_skill_name(name)})
    return out


def _known_skills_payload(profile: Profile | None) -> list[dict]:
    if not profile:
        return []
    return _skills_list_payload(profile.known_skills)


def _target_learn_skills_payload(profile: Profile | None) -> list[dict]:
    if not profile:
        return []
    return _skills_list_payload(profile.target_learn_skills)


def _target_role_payload(profile: Profile | None) -> dict:
    if not profile:
        return {"name": "", "slug": ""}
    label = (profile.target_role_label or "").strip()
    if label:
        return {"name": label, "slug": _slugify_skill_name(label)}
    if profile.target_role_id and profile.target_role:
        return {
            "name": profile.target_role.name,
            "slug": profile.target_role.slug,
        }
    return {"name": "", "slug": ""}


def _catalog_role_skills(profile: Profile | None) -> list[Skill]:
    if not profile or not profile.target_role_id:
        return []
    return list(
        Skill.objects.filter(role_skills__role_id=profile.target_role_id).distinct()[:12]
    )


def _resolve_learn_skills(profile: Profile | None) -> list[Skill]:
    """Match Step-03 learn stack names to Skill catalog rows when possible."""
    if not profile:
        return []
    names = [
        str(item).strip()
        for item in (profile.target_learn_skills or [])
        if str(item or "").strip()
    ]
    if not names:
        return []
    found: list[Skill] = []
    seen: set[int] = set()
    for name in names:
        slug = _slugify_skill_name(name)
        skill = (
            Skill.objects.filter(slug=slug).first()
            or Skill.objects.filter(name__iexact=name).first()
        )
        if skill and skill.id not in seen:
            found.append(skill)
            seen.add(skill.id)
    return found


def _target_skills(profile: Profile | None) -> list[Skill]:
    """Skills to assess toward the target role: learn stack first, then catalog."""
    learn = _resolve_learn_skills(profile)
    if learn:
        return learn
    return _catalog_role_skills(profile)


def build_assessment_context(
    *,
    user: User,
    attempt: DiagnosticAttempt,
    skill: Skill | None = None,
) -> dict:
    profile, _ = Profile.objects.get_or_create(user=user)
    known = _known_skills_payload(profile)
    learn = _target_learn_skills_payload(profile)
    catalog = [
        {"name": s.name, "slug": s.slug}
        for s in _catalog_role_skills(profile)
    ]
    # Prefer explicit learn stack for target_skills; fall back to catalog.
    target_skills = learn or catalog
    return {
        "user": {"experience_years": profile.years_of_experience},
        "current_role": {"name": profile.current_role or ""},
        "target_role": _target_role_payload(profile),
        "goal": attempt.goal,
        "skill": {"name": skill.name, "slug": skill.slug} if skill else {},
        "assessment_stage": attempt.current_stage,
        "difficulty": "MEDIUM",
        "previous_evidence": list(
            SkillEvidence.objects.filter(user=user, attempt=attempt).values(
                "stage", "score", "skill_id"
            )[:20]
        ),
        "current_skills": known,
        "known_skills": known,
        "target_skills": target_skills,
        "target_learn_skills": learn,
        "catalog_target_skills": catalog,
    }


def _pick_skill(attempt: DiagnosticAttempt) -> Skill | None:
    profile = getattr(attempt.user, "profile", None)
    skills = _target_skills(profile)
    if not skills:
        # Prefer free-text learn stack via context; do not invent an unrelated catalog skill.
        return None
    covered = set(
        SkillEvidence.objects.filter(attempt=attempt).values_list("skill_id", flat=True)
    )
    for skill in skills:
        if skill.id not in covered:
            return skill
    idx = attempt.turns.count() % len(skills)
    return skills[idx]


def _bank_fallback_question(attempt: DiagnosticAttempt, skill: Skill | None) -> dict:
    qs = DiagnosticQuestion.objects.filter(diagnostic=attempt.diagnostic)
    if skill:
        match = qs.filter(skill=skill).first()
        if match:
            return {
                "stage": attempt.current_stage,
                "skill_slug": skill.slug,
                "difficulty": str(match.difficulty),
                "question_type": match.question_type,
                "prompt_text": match.text,
                "requirements": [],
                "constraints": [],
                "expected_behavior": "",
                "evaluation_criteria": [],
            }
    first = qs.order_by("ordering").first()
    if first:
        return {
            "stage": attempt.current_stage,
            "skill_slug": first.skill.slug if first.skill_id else "",
            "difficulty": str(first.difficulty),
            "question_type": first.question_type,
            "prompt_text": first.text,
            "requirements": [],
            "constraints": [],
            "expected_behavior": "",
            "evaluation_criteria": [],
        }
    return {
        "stage": attempt.current_stage,
        "skill_slug": skill.slug if skill else "rag",
        "difficulty": "MEDIUM",
        "question_type": "FREE_TEXT",
        "prompt_text": "Describe how you would approach this skill in a production system.",
        "requirements": [],
        "constraints": [],
        "expected_behavior": "",
        "evaluation_criteria": [],
    }


@transaction.atomic
def start_adaptive_attempt(*, user: User, diagnostic_id: int) -> DiagnosticAttempt:
    from apps.diagnostics.services import get_diagnostic_or_404

    diagnostic = get_diagnostic_or_404(diagnostic_id)
    # Always start a fresh attempt so "Begin Diagnostic" regenerates AI questions
    # instead of resuming a stale IN_PROGRESS attempt (which may have bank fallbacks).
    DiagnosticAttempt.objects.filter(
        user=user,
        diagnostic=diagnostic,
        status=DiagnosticAttempt.Status.IN_PROGRESS,
    ).update(
        status=DiagnosticAttempt.Status.FAILED,
        completed_at=timezone.now(),
        active_turn_id=None,
    )

    profile, _ = Profile.objects.get_or_create(user=user)
    attempt = DiagnosticAttempt.objects.create(
        user=user,
        diagnostic=diagnostic,
        goal=_infer_goal(profile),
        current_stage=DiagnosticAttempt.Stage.FOUNDATION,
        stage_history=[DiagnosticAttempt.Stage.FOUNDATION],
    )
    turn = ensure_next_turn(attempt=attempt, require_ai=True)
    if turn is None:
        raise ValidationError("Could not generate the first AI diagnostic question.")
    return attempt


def ensure_next_turn(
    *,
    attempt: DiagnosticAttempt,
    require_ai: bool = False,
) -> DiagnosticTurn | None:
    import logging

    logger = logging.getLogger(__name__)

    if attempt.status != DiagnosticAttempt.Status.IN_PROGRESS:
        return None
    open_turn = (
        attempt.turns.filter(status=DiagnosticTurn.Status.ASKED)
        .order_by("ordering")
        .first()
    )
    if open_turn:
        if attempt.active_turn_id != open_turn.id:
            attempt.active_turn_id = open_turn.id
            attempt.save(update_fields=["active_turn_id"])
        return open_turn

    max_turns = int(getattr(settings, "AI_MAX_DIAGNOSTIC_TURNS", 8))
    if attempt.turns.count() >= max_turns:
        return None

    skill = _pick_skill(attempt)
    context = build_assessment_context(user=attempt.user, attempt=attempt, skill=skill)
    if not skill:
        learn = context.get("target_learn_skills") or []
        if learn:
            idx = attempt.turns.count() % len(learn)
            context["skill"] = learn[idx]
    generation_source = "ai"
    generation_error = ""
    try:
        generated = generate_adaptive_question(context)
        payload = generated.model_dump()
        skill_slug = payload.get("skill_slug") or (skill.slug if skill else "")
        if skill_slug:
            skill = Skill.objects.filter(slug=skill_slug).first() or skill
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "AI question generation failed for attempt %s: %s",
            attempt.id,
            exc,
        )
        if require_ai:
            raise ValidationError(
                "AI question generation failed. Check GEMINI_API_KEY / GEMINI_MODEL "
                "and restart the Django server."
            ) from exc
        generation_source = "bank_fallback"
        generation_error = str(exc)[:500]
        payload = _bank_fallback_question(attempt, skill)

    payload = {
        **payload,
        "generation_source": generation_source,
        "generation_error": generation_error,
    }

    ordering = attempt.turns.count() + 1
    turn = DiagnosticTurn.objects.create(
        attempt=attempt,
        ordering=ordering,
        stage=attempt.current_stage,
        skill=skill,
        difficulty=str(payload.get("difficulty") or "MEDIUM"),
        question_type=str(payload.get("question_type") or "FREE_TEXT"),
        question_payload=payload,
        status=DiagnosticTurn.Status.ASKED,
    )
    attempt.active_turn_id = turn.id
    attempt.save(update_fields=["active_turn_id"])
    return turn


def _next_stage(current: str, strength: str) -> str | None:
    try:
        idx = STAGE_ORDER.index(current)
    except ValueError:
        idx = 0
    if strength == "WEAK":
        return current
    if strength == "STRONG":
        if idx + 1 < len(STAGE_ORDER):
            return STAGE_ORDER[idx + 1]
        return None
    # MODERATE: advance slowly
    if idx + 1 < len(STAGE_ORDER):
        return STAGE_ORDER[idx + 1]
    return None


@transaction.atomic
def submit_turn_answer(
    *,
    user: User,
    attempt_id: int,
    turn_id: int,
    answer_text: str,
) -> DiagnosticAttempt:
    from apps.diagnostics.services import _get_user_attempt

    attempt = _get_user_attempt(user, attempt_id)
    if attempt.status != DiagnosticAttempt.Status.IN_PROGRESS:
        raise ValidationError("Attempt is not in progress.")
    try:
        turn = attempt.turns.get(pk=turn_id)
    except DiagnosticTurn.DoesNotExist as exc:
        raise NotFound("Turn not found.") from exc
    if turn.status not in {DiagnosticTurn.Status.ASKED, DiagnosticTurn.Status.ANSWERED}:
        raise ValidationError("Turn cannot accept an answer.")

    turn.answer_text = (answer_text or "")[:12000]
    turn.status = DiagnosticTurn.Status.ANSWERED
    turn.save(update_fields=["answer_text", "status", "updated_at"])

    context = build_assessment_context(
        user=user,
        attempt=attempt,
        skill=turn.skill,
    )
    context["assessment_stage"] = turn.stage
    try:
        evaluation = evaluate_adaptive_answer(context, turn.answer_text)
        eval_data = evaluation.model_dump()
        score = evaluation.mean_score()
        strength = evaluation.overall_strength or classify_from_score(score)
    except Exception:  # noqa: BLE001
        eval_data = {
            "evaluation": {
                "conceptual_accuracy": 0.5,
                "technical_depth": 0.5,
                "reasoning": 0.5,
                "problem_solving": 0.5,
            },
            "strengths": [],
            "weaknesses": ["Evaluation unavailable; recorded neutral score."],
            "misconceptions": [],
            "evidence": [],
            "confidence": 0.3,
            "recommended_next_stage": turn.stage,
            "overall_strength": "MODERATE",
        }
        score = 0.5
        strength = "MODERATE"

    turn.evaluation = eval_data
    turn.status = DiagnosticTurn.Status.EVALUATED
    turn.save(update_fields=["evaluation", "status", "updated_at"])

    if turn.skill_id:
        SkillEvidence.objects.create(
            user=user,
            skill=turn.skill,
            attempt=attempt,
            turn=turn,
            stage=turn.stage,
            score=score,
            evaluation=eval_data.get("evaluation") or {},
            strengths=eval_data.get("strengths") or [],
            weaknesses=eval_data.get("weaknesses") or [],
            confidence=float(eval_data.get("confidence") or 0.0),
            source_type="diagnostic_turn",
        )

    recommended = (eval_data.get("recommended_next_stage") or "").upper()
    next_stage = _next_stage(turn.stage, strength.upper() if isinstance(strength, str) else "MODERATE")
    if recommended in STAGE_ORDER:
        # Backend validates AI recommendation against rules: only allow same or next
        if recommended == turn.stage or (
            next_stage and STAGE_ORDER.index(recommended) <= STAGE_ORDER.index(next_stage)
        ):
            if strength.upper() != "WEAK" or recommended == turn.stage:
                next_stage = recommended if strength.upper() != "STRONG" else next_stage

    history = list(attempt.stage_history or [])
    if next_stage:
        attempt.current_stage = next_stage
        if not history or history[-1] != next_stage:
            history.append(next_stage)
        attempt.stage_history = history
        attempt.save(update_fields=["current_stage", "stage_history"])
        ensure_next_turn(attempt=attempt)
    else:
        complete_adaptive_attempt(attempt=attempt)

    return (
        DiagnosticAttempt.objects.select_related("diagnostic", "result")
        .prefetch_related("turns__skill", "answers__question")
        .get(pk=attempt.pk)
    )


@transaction.atomic
def complete_adaptive_attempt(*, attempt: DiagnosticAttempt) -> DiagnosticAttempt:
    evidence_rows = [
        {
            "skill_slug": e.skill.slug,
            "stage": e.stage,
            "score": e.score,
            "evaluation": e.evaluation,
        }
        for e in SkillEvidence.objects.filter(attempt=attempt).select_related("skill")
    ]
    scores = compute_skill_scores(evidence_rows)
    attempt.skill_scores = scores

    profile, _ = Profile.objects.get_or_create(user=attempt.user)
    target_skills = _target_skills(profile)
    known = _known_skills_payload(profile)
    learn = _target_learn_skills_payload(profile)
    target_role = _target_role_payload(profile)
    transfer_targets = learn or [
        {"name": s.name, "slug": s.slug} for s in target_skills
    ]

    transfer_report: list[dict] = []
    try:
        transfer_schema = analyze_transfers(
            {
                "current_skills": known,
                "target_skills": transfer_targets,
                "target_learn_skills": learn,
                "current_role": {"name": profile.current_role},
                "target_role": target_role,
            }
        )
        for item in transfer_schema.transfers:
            from_skill = Skill.objects.filter(slug=item.from_skill_slug).first()
            to_skill = Skill.objects.filter(slug=item.to_skill_slug).first()
            if from_skill and to_skill:
                SkillTransfer.objects.get_or_create(
                    from_skill=from_skill,
                    to_skill=to_skill,
                    defaults={"note": item.rationale},
                )
            transfer_report.append(
                {
                    "from_skill_slug": item.from_skill_slug,
                    "to_skill_slug": item.to_skill_slug,
                    "from_skill_name": from_skill.name if from_skill else item.from_skill_slug,
                    "to_skill_name": to_skill.name if to_skill else item.to_skill_slug,
                    "rationale": item.rationale,
                    "classification": "TRANSFERABLE",
                }
            )
    except Exception:  # noqa: BLE001
        transfer_report = []

    attempt.transfer_report = transfer_report

    gap_report: list[dict] = []
    importance_map = {
        rs.skill.slug: rs.importance
        for rs in RoleSkill.objects.filter(role_id=profile.target_role_id).select_related(
            "skill"
        )
    } if profile.target_role_id else {}

    for skill in target_skills:
        score_info = scores.get(skill.slug) or {"score": 0.0, "breakdown": {}}
        score = float(score_info.get("score") or 0.0)
        classification = classify_gap_status(
            score=score,
            importance=importance_map.get(skill.slug),
        )
        gap_report.append(
            {
                "skill_slug": skill.slug,
                "skill_name": skill.name,
                "score": score,
                "breakdown": score_info.get("breakdown") or {},
                "classification": classification,
                "importance": importance_map.get(skill.slug),
            }
        )
        if classification in {"GAP", "CRITICAL_GAP", "DEVELOPING"}:
            upsert_user_skill_gap(
                user=attempt.user,
                skill=skill,
                status=UserSkillGap.Status.NOT_STARTED,
                evidence_source_type="adaptive_diagnostic",
                evidence_source_id=str(attempt.id),
                evidence_summary=f"{classification}: score={score:.2f}",
            )
        # Sync UserSkill level from score
        level = UserSkill.Level.NONE
        if score >= 0.75:
            level = UserSkill.Level.ADVANCED
        elif score >= 0.5:
            level = UserSkill.Level.INTERMEDIATE
        elif score > 0:
            level = UserSkill.Level.BEGINNER
        UserSkill.objects.update_or_create(
            user=attempt.user,
            skill=skill,
            defaults={"level": level},
        )

    try:
        explanations = explain_skill_gaps({"gaps": gap_report})
        by_slug = {e.skill_slug: e.explanation for e in explanations.explanations}
        for row in gap_report:
            row["explanation"] = by_slug.get(row["skill_slug"], "")
    except Exception:  # noqa: BLE001
        pass

    attempt.gap_report = gap_report
    attempt.status = DiagnosticAttempt.Status.COMPLETED
    attempt.completed_at = timezone.now()
    attempt.active_turn_id = None
    attempt.save(
        update_fields=[
            "skill_scores",
            "transfer_report",
            "gap_report",
            "status",
            "completed_at",
            "active_turn_id",
        ]
    )

    strengths = [
        g["skill_name"] for g in gap_report if g["classification"] == "STRONG"
    ]
    gaps_payload = [
        {
            "skill_slug": g["skill_slug"],
            "severity": "critical" if g["classification"] == "CRITICAL_GAP" else "partial",
            "notes": g.get("explanation") or g["classification"],
        }
        for g in gap_report
        if g["classification"] in {"GAP", "CRITICAL_GAP", "DEVELOPING"}
    ]
    DiagnosticResult.objects.update_or_create(
        attempt=attempt,
        defaults={
            "strengths": strengths,
            "gaps": gaps_payload,
            "evidence": [
                {"source": "adaptive", "detail": f"{e['skill_slug']}:{e['stage']}:{e['score']}"}
                for e in evidence_rows[:20]
            ],
            "skill_findings": [
                {
                    "skill_slug": slug,
                    "level": classify_from_score(info["score"]),
                    "confidence": 0.8,
                    "score": info["score"],
                }
                for slug, info in scores.items()
            ],
            "recommended_focus": next(
                (g["skill_slug"] for g in gap_report if g["classification"] == "CRITICAL_GAP"),
                next((g["skill_slug"] for g in gap_report if g["classification"] == "GAP"), ""),
            ),
            "raw_payload": {
                "skill_scores": scores,
                "transfer_report": transfer_report,
                "gap_report": gap_report,
            },
        },
    )

    from apps.sessions.services import record_session

    record_session(
        user=attempt.user,
        session_type="DIAGNOSTIC",
        reference_id=attempt.id,
        title=attempt.diagnostic.title,
        summary="Adaptive diagnostic completed",
    )
    return attempt

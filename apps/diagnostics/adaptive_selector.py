"""Rule-based adaptive question selection."""

from __future__ import annotations

import hashlib
import logging
import random
import re
from typing import Iterable

from django.conf import settings
from django.db import models

from apps.diagnostics.grading import answer_score_for_adaptive
from apps.diagnostics.models import (
    DiagnosticSession,
    Question,
    QuickScoreAttempt,
    QuickScoreQuestion,
    SessionAnswer,
    SessionQuestion,
)

logger = logging.getLogger(__name__)

STAGE_MODALITY_MAP = {
    DiagnosticSession.Stage.FOUNDATIONAL: Question.Modality.FOUNDATIONAL,
    DiagnosticSession.Stage.SCENARIO: Question.Modality.SCENARIO,
    DiagnosticSession.Stage.DEBUGGING: Question.Modality.FIND_ISSUES,
    DiagnosticSession.Stage.CODING: Question.Modality.CODING,
    DiagnosticSession.Stage.FIND_ISSUES: Question.Modality.FIND_ISSUES,
}

STAGE_ORDER = [
    DiagnosticSession.Stage.FOUNDATIONAL,
    DiagnosticSession.Stage.SCENARIO,
    DiagnosticSession.Stage.DEBUGGING,
    DiagnosticSession.Stage.CODING,
    DiagnosticSession.Stage.FIND_ISSUES,
]

QUESTIONS_PER_STAGE = {
    DiagnosticSession.Stage.FOUNDATIONAL: 5,
    DiagnosticSession.Stage.SCENARIO: 4,
    DiagnosticSession.Stage.DEBUGGING: 3,
    DiagnosticSession.Stage.CODING: 2,
    DiagnosticSession.Stage.FIND_ISSUES: 1,
}


def _weak_threshold() -> float:
    return float(getattr(settings, "ADAPTIVE_WEAK_THRESHOLD", 0.4))


def _strong_threshold() -> float:
    return float(getattr(settings, "ADAPTIVE_STRONG_THRESHOLD", 0.7))


def _rolling_window() -> int:
    return int(getattr(settings, "ADAPTIVE_ROLLING_WINDOW", 5))


def experience_difficulty_band(years: int | None) -> tuple[int, int, int]:
    """Return (min_tier, max_tier, start_tier) from years of experience."""
    if years is None:
        return 1, 3, 1
    if years <= 2:
        return 1, 2, 1
    if years <= 5:
        return 2, 3, 2
    return 3, 5, 3


def _user_years(user) -> int | None:
    profile = getattr(user, "profile", None)
    years = getattr(profile, "years_of_experience", None)
    if years is None:
        return None
    try:
        return int(years)
    except (TypeError, ValueError):
        return None


def _rng(*parts: object) -> random.Random:
    material = "|".join(str(p) for p in parts)
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return random.Random(int(digest[:16], 16))


def build_assessment_competencies(session: DiagnosticSession) -> list[dict]:
    competencies: list[dict] = []
    frameworks = list(session.selected_frameworks.select_related("fundamentals_topic"))
    fundamentals_seen: set[int] = set()

    for framework in frameworks:
        for area in framework.clean_competency_areas():
            competencies.append(
                {
                    "framework_slug": framework.framework_name,
                    "competency_area": area,
                    "source": "framework",
                }
            )
        fundamentals = framework.fundamentals_topic
        if fundamentals.id not in fundamentals_seen:
            fundamentals_seen.add(fundamentals.id)
            for area in fundamentals.clean_competency_areas():
                competencies.append(
                    {
                        "framework_slug": fundamentals.language_family,
                        "competency_area": area,
                        "source": "fundamentals",
                    }
                )

    max_areas = int(getattr(settings, "DIAGNOSTIC_MAX_COMPETENCY_AREAS", 8))
    rng = _rng(session.user_id, session.id, "competencies")
    framework_comps = [c for c in competencies if c.get("source") == "framework"]
    other_comps = [c for c in competencies if c.get("source") != "framework"]
    rng.shuffle(framework_comps)
    rng.shuffle(other_comps)
    # Keep selected-framework areas first so sparse catalogs (e.g. sample
    # foundational prompts only for hooks/closures) are not truncated away.
    ordered = framework_comps + other_comps
    return ordered[:max_areas]


def rolling_score_for_area(
    session: DiagnosticSession,
    competency_area: str,
) -> float | None:
    answers = (
        SessionAnswer.objects.filter(question__session=session)
        .select_related("question__content_question")
        .order_by("-submitted_at")
    )
    scores: list[float] = []
    for answer in answers:
        if answer.question.competency_area != competency_area:
            continue
        score = answer_score_for_adaptive(answer)
        if score is None:
            continue
        scores.append(score)
        if len(scores) >= _rolling_window():
            break
    if not scores:
        return None
    return sum(scores) / len(scores)


def _used_question_ids(session: DiagnosticSession) -> set[int]:
    return set(session.questions.values_list("content_question_id", flat=True))


def _user_seen_diagnostic_question_ids(user_id: int) -> set[int]:
    """Never re-ask a diagnostic question this user has already been shown."""
    return set(
        SessionQuestion.objects.filter(session__user_id=user_id).values_list(
            "content_question_id", flat=True
        )
    )


def _user_seen_diagnostic_texts(user_id: int) -> list[str]:
    return list(
        SessionQuestion.objects.filter(session__user_id=user_id)
        .exclude(content_question__isnull=True)
        .values_list("content_question__question_text", flat=True)
    )


_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _normalize_question_text(text: str) -> str:
    return " ".join(_TOKEN_RE.findall((text or "").lower()))


def _token_set(text: str) -> set[str]:
    return set(_TOKEN_RE.findall((text or "").lower()))


def _texts_overlap(a: str, b: str, *, min_jaccard: float = 0.55) -> bool:
    """True when prompts are duplicates / near-duplicates of each other."""
    na = _normalize_question_text(a)
    nb = _normalize_question_text(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    if na in nb or nb in na:
        return True
    ta, tb = _token_set(a), _token_set(b)
    if not ta or not tb:
        return False
    intersection = len(ta & tb)
    union = len(ta | tb)
    return (intersection / union) >= min_jaccard


def _blocked_quick_score_texts_for_user(user_id: int) -> list[str]:
    """Prompts this learner already saw in Quick Score."""
    blocked: list[str] = []
    attempts = QuickScoreAttempt.objects.filter(user_id=user_id).only("answers")
    answered_ids: set[int] = set()
    for attempt in attempts:
        for qid in (attempt.answers or {}).keys():
            try:
                answered_ids.add(int(qid))
            except (TypeError, ValueError):
                continue
    if answered_ids:
        blocked.extend(
            QuickScoreQuestion.objects.filter(id__in=answered_ids).values_list(
                "question_text", flat=True
            )
        )
    return blocked


def _is_blocked_by_texts(question: Question, blocked_texts: Iterable[str]) -> bool:
    for blocked in blocked_texts:
        if _texts_overlap(question.question_text, blocked):
            return True
    return False


def _candidate_questions(
    session: DiagnosticSession,
    *,
    stage: str | None = None,
    competency_area: str,
    modality: str | None = None,
    max_difficulty: int | None = None,
    min_difficulty: int | None = None,
) -> list[Question]:
    if modality is None:
        if stage is None:
            return []
        modality = STAGE_MODALITY_MAP[stage]
    framework_ids = list(session.selected_frameworks.values_list("id", flat=True))
    fundamentals_ids = list(
        session.selected_frameworks.values_list("fundamentals_topic_id", flat=True)
    )
    used = _used_question_ids(session)
    seen_forever = _user_seen_diagnostic_question_ids(session.user_id)
    blocked_texts = (
        _blocked_quick_score_texts_for_user(session.user_id)
        + _user_seen_diagnostic_texts(session.user_id)
    )

    qs = Question.objects.filter(
        is_active=True,
        modality=modality,
        competency_area=competency_area,
    ).filter(
        models.Q(framework_topic_id__in=framework_ids)
        | models.Q(fundamentals_topic_id__in=fundamentals_ids)
    )
    if max_difficulty is not None:
        qs = qs.filter(difficulty_tier__lte=max_difficulty)
    if min_difficulty is not None:
        qs = qs.filter(difficulty_tier__gte=min_difficulty)

    candidates = [
        q
        for q in qs.order_by("difficulty_tier", "id")
        if q.id not in used
        and q.id not in seen_forever
        and not _is_blocked_by_texts(q, blocked_texts)
    ]
    rng = _rng(
        session.user_id,
        session.id,
        stage or modality,
        competency_area,
        min_difficulty,
        max_difficulty,
        len(used),
    )
    rng.shuffle(candidates)
    return candidates


def select_next_question(
    session: DiagnosticSession,
    *,
    stage: str,
    competency_area: str,
    current_tier: int = 1,
    min_tier: int = 1,
    max_tier: int = 5,
) -> tuple[Question | None, dict]:
    score = rolling_score_for_area(session, competency_area)
    weak = _weak_threshold()
    strong = _strong_threshold()

    reason = "default_same_tier"
    target_tier = max(min_tier, min(current_tier, max_tier))

    if score is not None and score < weak:
        reason = "weak_stay_area_lower_tier"
        target_tier = max(min_tier, min(current_tier, max_tier))
        candidates = _candidate_questions(
            session,
            stage=stage,
            competency_area=competency_area,
            min_difficulty=min_tier,
            max_difficulty=target_tier,
        )
    elif score is not None and score > strong:
        reason = "strong_escalate_tier"
        target_tier = min(current_tier + 1, max_tier)
        candidates = _candidate_questions(
            session,
            stage=stage,
            competency_area=competency_area,
            min_difficulty=target_tier,
            max_difficulty=target_tier,
        )
        if not candidates:
            candidates = _candidate_questions(
                session,
                stage=stage,
                competency_area=competency_area,
                min_difficulty=min_tier,
                max_difficulty=target_tier,
            )
    else:
        candidates = _candidate_questions(
            session,
            stage=stage,
            competency_area=competency_area,
            min_difficulty=min_tier,
            max_difficulty=target_tier,
        )

    if not candidates:
        # Relax difficulty band but still never re-ask seen questions.
        reason = "relax_difficulty_keep_unseen"
        candidates = _candidate_questions(
            session,
            stage=stage,
            competency_area=competency_area,
        )

    decision = {
        "stage": stage,
        "competency_area": competency_area,
        "rolling_score": score,
        "weak_threshold": weak,
        "strong_threshold": strong,
        "target_tier": target_tier,
        "min_tier": min_tier,
        "max_tier": max_tier,
        "reason": reason,
        "question_id": candidates[0].id if candidates else None,
    }
    return (candidates[0] if candidates else None, decision)


def allocate_stage_questions(session: DiagnosticSession, stage: str) -> list[SessionQuestion]:
    count = QUESTIONS_PER_STAGE.get(stage, 1)
    competencies = session.assessment_competencies or build_assessment_competencies(session)
    if not competencies:
        return []

    years = _user_years(session.user)
    min_tier, max_tier, start_tier = experience_difficulty_band(years)
    bump = int(getattr(session, "difficulty_bump", 0) or 0)
    min_tier = min(5, min_tier + bump)
    max_tier = min(5, max_tier + bump)
    start_tier = min(5, start_tier + bump)

    created: list[SessionQuestion] = []
    competency_index = 0
    current_tier = start_tier
    order = (
        session.questions.filter(stage=stage).order_by("-order").values_list("order", flat=True).first()
        or 0
    )

    for _ in range(count):
        question = None
        decision: dict = {}
        tried = 0
        while tried < len(competencies):
            comp = competencies[competency_index % len(competencies)]
            competency_area = comp["competency_area"]
            question, decision = select_next_question(
                session,
                stage=stage,
                competency_area=competency_area,
                current_tier=current_tier,
                min_tier=min_tier,
                max_tier=max_tier,
            )
            session.selection_log.append(decision)
            if question is not None:
                break
            competency_index += 1
            tried += 1

        if question is None:
            logger.warning(
                "No unseen question available for session=%s stage=%s",
                session.id,
                stage,
            )
            break

        order += 1
        sq = SessionQuestion.objects.create(
            session=session,
            content_question=question,
            stage=stage,
            order=order,
            competency_area=question.competency_area,
            status=SessionQuestion.Status.ASKED,
        )
        created.append(sq)

        if decision.get("reason") == "strong_escalate_tier":
            current_tier = min(current_tier + 1, max_tier)
        competency_index += 1

    session.save(update_fields=["selection_log"])
    return created


def next_stage(current_stage: str | None) -> str | None:
    if current_stage is None:
        return STAGE_ORDER[0]
    try:
        idx = STAGE_ORDER.index(current_stage)
    except ValueError:
        return STAGE_ORDER[0]
    if idx + 1 >= len(STAGE_ORDER):
        return None
    return STAGE_ORDER[idx + 1]


FOUNDATIONAL_SKIP_COUNT = 3
HARD_MODALITIES = [
    Question.Modality.CODING,
    Question.Modality.FIND_ISSUES,
    Question.Modality.DIAGNOSE,
]
EASY_FOLLOW_MODALITIES = [
    Question.Modality.SCENARIO,
    Question.Modality.CODING,
    Question.Modality.FIND_ISSUES,
]
EASY_SKIP_MODALITIES = {
    Question.Modality.FOUNDATIONAL,
    Question.Modality.SCENARIO,
}

MODALITY_TO_STAGE = {
    Question.Modality.FOUNDATIONAL: DiagnosticSession.Stage.FOUNDATIONAL,
    Question.Modality.SCENARIO: DiagnosticSession.Stage.SCENARIO,
    Question.Modality.FIND_ISSUES: DiagnosticSession.Stage.FIND_ISSUES,
    Question.Modality.CODING: DiagnosticSession.Stage.CODING,
    Question.Modality.DIAGNOSE: DiagnosticSession.Stage.DEBUGGING,
    Question.Modality.DEFEND: DiagnosticSession.Stage.SCENARIO,
    Question.Modality.EXPLAIN: DiagnosticSession.Stage.SCENARIO,
    Question.Modality.COMMUNICATE: DiagnosticSession.Stage.SCENARIO,
    Question.Modality.ARCHITECT: DiagnosticSession.Stage.SCENARIO,
}


def _skip_count() -> int:
    return int(getattr(settings, "FOUNDATIONAL_SKIP_COUNT", FOUNDATIONAL_SKIP_COUNT))


def _session_budget() -> int:
    return int(getattr(settings, "DIAGNOSTIC_SESSION_QUESTION_BUDGET", 15))


def skipped_easy_areas(session: DiagnosticSession) -> list[str]:
    tracks = session.area_tracks or {}
    return [
        area
        for area, track in tracks.items()
        if isinstance(track, dict) and track.get("skip_easy")
    ]


def _empty_track() -> dict:
    return {
        "foundational_asked": 0,
        "foundational_correct": 0,
        "skip_easy": False,
        "hard_asked": 0,
        "easy_follow_asked": 0,
        "asked_modalities": [],
    }


def _track_for(session: DiagnosticSession, competency_area: str) -> dict:
    tracks = dict(session.area_tracks or {})
    track = dict(tracks.get(competency_area) or _empty_track())
    for key, default in _empty_track().items():
        track.setdefault(key, default)
    return track


def update_area_track_after_answer(
    session: DiagnosticSession,
    *,
    session_question: SessionQuestion,
    is_correct: bool | None,
) -> dict | None:
    """Update per-area skip-ahead state. Returns skip event or None."""
    area = session_question.competency_area or session_question.content_question.competency_area
    if not area:
        return None
    modality = session_question.content_question.modality
    tracks = dict(session.area_tracks or {})
    track = _track_for(session, area)
    asked_modalities = list(track.get("asked_modalities") or [])
    asked_modalities.append(modality)
    track["asked_modalities"] = asked_modalities

    skip_event = None
    if modality == Question.Modality.FOUNDATIONAL:
        track["foundational_asked"] = int(track.get("foundational_asked") or 0) + 1
        if is_correct:
            track["foundational_correct"] = int(track.get("foundational_correct") or 0) + 1
        asked = int(track["foundational_asked"])
        correct = int(track["foundational_correct"])
        if asked >= _skip_count() and correct >= _skip_count() and not track.get("skip_easy"):
            track["skip_easy"] = True
            skip_event = {
                "competency_area": area,
                "reason": "strong_foundations_skip_easy",
                "foundational_asked": asked,
                "foundational_correct": correct,
            }
    elif track.get("skip_easy") or modality in HARD_MODALITIES:
        track["hard_asked"] = int(track.get("hard_asked") or 0) + 1
    else:
        track["easy_follow_asked"] = int(track.get("easy_follow_asked") or 0) + 1

    tracks[area] = track
    session.area_tracks = tracks
    session.save(update_fields=["area_tracks"])
    return skip_event


def _modalities_for_track(track: dict) -> list[str]:
    asked = int(track.get("foundational_asked") or 0)
    extra = int(track.get("hard_asked") or 0) + int(track.get("easy_follow_asked") or 0)
    if asked < _skip_count():
        return [Question.Modality.FOUNDATIONAL]
    if extra >= 1:
        return []
    if track.get("skip_easy"):
        return list(HARD_MODALITIES)
    return list(EASY_FOLLOW_MODALITIES)


def _has_open_asked(session: DiagnosticSession) -> bool:
    return session.questions.filter(status=SessionQuestion.Status.ASKED).exists()


def _create_session_question(
    session: DiagnosticSession,
    *,
    question: Question,
    decision: dict,
) -> SessionQuestion:
    stage = MODALITY_TO_STAGE.get(question.modality, DiagnosticSession.Stage.FOUNDATIONAL)
    order = (
        session.questions.filter(stage=stage)
        .order_by("-order")
        .values_list("order", flat=True)
        .first()
        or 0
    ) + 1
    sq = SessionQuestion.objects.create(
        session=session,
        content_question=question,
        stage=stage,
        order=order,
        competency_area=question.competency_area,
        status=SessionQuestion.Status.ASKED,
    )
    session.current_stage = stage
    log = list(session.selection_log or [])
    log.append(decision)
    session.selection_log = log
    session.save(update_fields=["current_stage", "selection_log"])
    return sq


def _pick_question_for_modality(
    session: DiagnosticSession,
    *,
    competency_area: str,
    modality: str,
) -> tuple[Question | None, dict]:
    years = _user_years(session.user)
    min_tier, max_tier, start_tier = experience_difficulty_band(years)
    bump = int(getattr(session, "difficulty_bump", 0) or 0)
    min_tier = min(5, min_tier + bump)
    max_tier = min(5, max_tier + bump)
    min_diff = min(5, start_tier + bump) if modality in HARD_MODALITIES else None
    candidates = _candidate_questions(
        session,
        competency_area=competency_area,
        modality=modality,
        min_difficulty=min_diff,
        max_difficulty=max_tier,
    )
    if not candidates:
        candidates = _candidate_questions(
            session,
            competency_area=competency_area,
            modality=modality,
        )
    question = candidates[0] if candidates else None
    decision = {
        "stage": MODALITY_TO_STAGE.get(modality, DiagnosticSession.Stage.FOUNDATIONAL),
        "competency_area": competency_area,
        "reason": "area_track_modality",
        "modality": modality,
        "question_id": question.id if question else None,
    }
    return question, decision


def allocate_next_question(session: DiagnosticSession) -> SessionQuestion | None:
    """Allocate a single next question using per-area skip-ahead tracks."""
    if _has_open_asked(session):
        return session.questions.filter(status=SessionQuestion.Status.ASKED).order_by("order").first()

    if session.questions.count() >= _session_budget():
        return None

    competencies = session.assessment_competencies or build_assessment_competencies(session)
    if not competencies:
        return None

    counts: dict[str, int] = {}
    for sq in session.questions.all():
        area = sq.competency_area or ""
        counts[area] = counts.get(area, 0) + 1

    ordered = sorted(
        competencies,
        key=lambda c: (counts.get(c.get("competency_area") or "", 0), competencies.index(c)),
    )

    for comp in ordered:
        area = comp.get("competency_area") or ""
        if not area:
            continue
        track = _track_for(session, area)
        for modality in _modalities_for_track(track):
            if track.get("skip_easy") and modality in EASY_SKIP_MODALITIES:
                continue
            question, decision = _pick_question_for_modality(
                session,
                competency_area=area,
                modality=modality,
            )
            if question is None:
                continue
            decision["skip_easy"] = bool(track.get("skip_easy"))
            decision["area_track"] = track
            return _create_session_question(session, question=question, decision=decision)

    # Last resort: any remaining unseen question for selected frameworks.
    used = _used_question_ids(session)
    seen_forever = _user_seen_diagnostic_question_ids(session.user_id)
    framework_ids = list(session.selected_frameworks.values_list("id", flat=True))
    fundamentals_ids = list(
        session.selected_frameworks.values_list("fundamentals_topic_id", flat=True)
    )
    fallback_qs = Question.objects.filter(is_active=True).filter(
        models.Q(framework_topic_id__in=framework_ids)
        | models.Q(fundamentals_topic_id__in=fundamentals_ids)
    ).exclude(id__in=used | seen_forever)
    skipped = set(skipped_easy_areas(session))
    for fallback in fallback_qs.order_by("difficulty_tier", "id"):
        if fallback.competency_area in skipped and fallback.modality in EASY_SKIP_MODALITIES:
            continue
        decision = {
            "reason": "fallback_any_unseen",
            "competency_area": fallback.competency_area,
            "modality": fallback.modality,
            "question_id": fallback.id,
        }
        return _create_session_question(session, question=fallback, decision=decision)
    return None

"""Rule-based adaptive question selection."""

from __future__ import annotations

import logging

from django.conf import settings
from django.db import models

from apps.diagnostics.grading import answer_score_for_adaptive
from apps.diagnostics.models import (
    DiagnosticSession,
    FrameworkTopic,
    FundamentalsTopic,
    Question,
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
    DiagnosticSession.Stage.FOUNDATIONAL: 4,
    DiagnosticSession.Stage.SCENARIO: 3,
    DiagnosticSession.Stage.DEBUGGING: 3,
    DiagnosticSession.Stage.CODING: 1,
    DiagnosticSession.Stage.FIND_ISSUES: 1,
}


def _weak_threshold() -> float:
    return float(getattr(settings, "ADAPTIVE_WEAK_THRESHOLD", 0.4))


def _strong_threshold() -> float:
    return float(getattr(settings, "ADAPTIVE_STRONG_THRESHOLD", 0.7))


def _rolling_window() -> int:
    return int(getattr(settings, "ADAPTIVE_ROLLING_WINDOW", 5))


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
    return competencies[:max_areas]


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


def _candidate_questions(
    session: DiagnosticSession,
    *,
    stage: str,
    competency_area: str,
    max_difficulty: int | None = None,
    min_difficulty: int | None = None,
) -> list[Question]:
    modality = STAGE_MODALITY_MAP[stage]
    framework_ids = list(session.selected_frameworks.values_list("id", flat=True))
    fundamentals_ids = list(
        session.selected_frameworks.values_list("fundamentals_topic_id", flat=True)
    )
    used = _used_question_ids(session)

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

    return [q for q in qs.order_by("difficulty_tier", "id") if q.id not in used]


def select_next_question(
    session: DiagnosticSession,
    *,
    stage: str,
    competency_area: str,
    current_tier: int = 1,
) -> tuple[Question | None, dict]:
    score = rolling_score_for_area(session, competency_area)
    weak = _weak_threshold()
    strong = _strong_threshold()

    reason = "default_same_tier"
    target_tier = current_tier

    if score is not None and score < weak:
        reason = "weak_stay_area_lower_tier"
        target_tier = current_tier
        candidates = _candidate_questions(
            session,
            stage=stage,
            competency_area=competency_area,
            max_difficulty=current_tier,
        )
    elif score is not None and score > strong:
        reason = "strong_escalate_tier"
        target_tier = min(current_tier + 1, 5)
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
                max_difficulty=target_tier,
            )
    else:
        candidates = _candidate_questions(
            session,
            stage=stage,
            competency_area=competency_area,
            max_difficulty=current_tier,
        )

    if not candidates:
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
        "reason": reason,
        "question_id": candidates[0].id if candidates else None,
    }
    return (candidates[0] if candidates else None, decision)


def allocate_stage_questions(session: DiagnosticSession, stage: str) -> list[SessionQuestion]:
    count = QUESTIONS_PER_STAGE.get(stage, 1)
    competencies = session.assessment_competencies or build_assessment_competencies(session)
    if not competencies:
        return []

    created: list[SessionQuestion] = []
    competency_index = 0
    current_tier = 1
    order = (
        session.questions.filter(stage=stage).order_by("-order").values_list("order", flat=True).first()
        or 0
    )

    for _ in range(count):
        comp = competencies[competency_index % len(competencies)]
        competency_area = comp["competency_area"]
        question, decision = select_next_question(
            session,
            stage=stage,
            competency_area=competency_area,
            current_tier=current_tier,
        )
        session.selection_log.append(decision)

        if question is None:
            logger.warning(
                "No question available for session=%s stage=%s area=%s",
                session.id,
                stage,
                competency_area,
            )
            competency_index += 1
            continue

        order += 1
        sq = SessionQuestion.objects.create(
            session=session,
            content_question=question,
            stage=stage,
            order=order,
            competency_area=competency_area,
            status=SessionQuestion.Status.ASKED,
        )
        created.append(sq)

        if decision.get("reason") == "strong_escalate_tier":
            current_tier = min(current_tier + 1, 5)
            competency_index += 1
        elif decision.get("reason") == "weak_stay_area_lower_tier":
            pass
        else:
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

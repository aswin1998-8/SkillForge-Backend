"""Rule-based synthesis and roadmap generation."""

from __future__ import annotations

from django.conf import settings
from django.utils import timezone

from apps.diagnostics.adaptive_selector import rolling_score_for_area
from apps.diagnostics.models import (
    DiagnosticRoadmapItem,
    DiagnosticSession,
    Question,
    SessionAnswer,
)


MODALITY_TO_CHALLENGE = {
    Question.Modality.FOUNDATIONAL: DiagnosticRoadmapItem.Modality.THEORY,
    Question.Modality.CODING: DiagnosticRoadmapItem.Modality.CODING,
    Question.Modality.FIND_ISSUES: DiagnosticRoadmapItem.Modality.DIAGNOSE,
    Question.Modality.SCENARIO: DiagnosticRoadmapItem.Modality.DEFEND,
    Question.Modality.DEFEND: DiagnosticRoadmapItem.Modality.DEFEND,
    Question.Modality.DIAGNOSE: DiagnosticRoadmapItem.Modality.DIAGNOSE,
    Question.Modality.ARCHITECT: DiagnosticRoadmapItem.Modality.ARCHITECT,
    Question.Modality.EXPLAIN: DiagnosticRoadmapItem.Modality.EXPLAIN_CODE,
    Question.Modality.COMMUNICATE: DiagnosticRoadmapItem.Modality.COMMUNICATE,
}


def _weak_threshold() -> float:
    return float(getattr(settings, "ADAPTIVE_WEAK_THRESHOLD", 0.4))


def _strong_threshold() -> float:
    return float(getattr(settings, "ADAPTIVE_STRONG_THRESHOLD", 0.7))


def _severity(score: float) -> str:
    if score < 0.2:
        return "high"
    if score < _weak_threshold():
        return "medium"
    return "low"


def synthesize_session(session: DiagnosticSession) -> dict:
    competencies = session.assessment_competencies or []
    areas = [c["competency_area"] for c in competencies]
    if not areas:
        areas = list(
            session.questions.values_list("competency_area", flat=True).distinct()
        )

    strengths: list[dict] = []
    gaps: list[dict] = []
    roadmap: list[dict] = []

    strong = _strong_threshold()
    weak = _weak_threshold()

    for area in areas:
        score = rolling_score_for_area(session, area)
        if score is None:
            continue
        if score >= strong:
            strengths.append(
                {
                    "skill_area": area,
                    "evidence": f"Rolling score {score:.2f} >= {strong:.2f}",
                }
            )
        elif score < weak:
            severity = _severity(score)
            gaps.append(
                {
                    "skill_area": area,
                    "block": "A",
                    "severity": severity,
                }
            )
            modality = _dominant_modality_for_area(session, area)
            roadmap.append(
                {
                    "challenge_modality": modality,
                    "topic": area,
                    "priority": _priority_for_severity(severity),
                }
            )

    roadmap.sort(key=lambda item: item["priority"])

    synthesis = {
        "strengths": strengths,
        "gaps": gaps,
        "transferable_skills": [],
        "roadmap": roadmap,
    }

    session.synthesis = synthesis
    session.status = DiagnosticSession.Status.COMPLETED
    session.completed_at = timezone.now()
    session.save(update_fields=["synthesis", "status", "completed_at"])

    DiagnosticRoadmapItem.objects.filter(session=session).delete()
    for item in roadmap:
        DiagnosticRoadmapItem.objects.create(
            session=session,
            user=session.user,
            challenge_modality=item["challenge_modality"],
            topic=item["topic"],
            priority=item["priority"],
        )

    return synthesis


def _dominant_modality_for_area(session: DiagnosticSession, area: str) -> str:
    answers = (
        SessionAnswer.objects.filter(
            question__session=session,
            question__competency_area=area,
        )
        .select_related("question__content_question")
        .order_by("-submitted_at")
    )
    for answer in answers:
        modality = answer.question.content_question.modality
        mapped = MODALITY_TO_CHALLENGE.get(modality)
        if mapped:
            return mapped
    return DiagnosticRoadmapItem.Modality.THEORY


def _priority_for_severity(severity: str) -> int:
    return {"high": 1, "medium": 2, "low": 3}.get(severity, 3)

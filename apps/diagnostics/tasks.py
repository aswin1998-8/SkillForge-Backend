"""Celery tasks for diagnostic result generation."""

from __future__ import annotations

import logging

from celery import shared_task
from django.db import transaction

from apps.ai.services.diagnostic_service import run_diagnostic_analysis
from apps.diagnostics.models import DiagnosticAttempt, DiagnosticResult
from apps.diagnostics.services import mark_attempt_completed, mark_attempt_failed
from apps.gaps.models import UserSkillGap
from apps.gaps.services import upsert_user_skill_gap
from apps.roles.models import Skill
from apps.sessions.services import record_session

logger = logging.getLogger(__name__)


@shared_task(name="apps.diagnostics.tasks.generate_diagnostic_result")
def generate_diagnostic_result(attempt_id: int) -> dict:
    try:
        attempt = DiagnosticAttempt.objects.select_related("diagnostic", "user").prefetch_related(
            "answers__question__skill",
            "diagnostic__questions__skill",
        ).get(pk=attempt_id)
    except DiagnosticAttempt.DoesNotExist:
        logger.error("Diagnostic attempt %s not found", attempt_id)
        return {"ok": False, "error": "not_found"}

    try:
        qa = [
            {
                "question_id": answer.question_id,
                "question_text": answer.question.text,
                "skill_slug": answer.question.skill.slug if answer.question.skill else None,
                "answer_text": answer.answer_text,
            }
            for answer in attempt.answers.all()
        ]
        skills = []
        seen: set[str] = set()
        for question in attempt.diagnostic.questions.all():
            if question.skill and question.skill.slug not in seen:
                seen.add(question.skill.slug)
                skills.append(
                    {
                        "id": question.skill.id,
                        "name": question.skill.name,
                        "slug": question.skill.slug,
                    }
                )

        result_schema = run_diagnostic_analysis(
            diagnostic_title=attempt.diagnostic.title,
            questions_and_answers=qa,
            skills=skills,
        )

        with transaction.atomic():
            DiagnosticResult.objects.update_or_create(
                attempt=attempt,
                defaults={
                    "strengths": result_schema.strengths,
                    "gaps": [g.model_dump() for g in result_schema.gaps],
                    "evidence": [e.model_dump() for e in result_schema.evidence],
                    "skill_findings": [f.model_dump() for f in result_schema.skill_findings],
                    "recommended_focus": result_schema.recommended_focus,
                    "raw_payload": result_schema.raw or result_schema.model_dump(),
                },
            )

            for gap in result_schema.gaps:
                skill = Skill.objects.filter(slug=gap.skill_slug).first()
                if skill is None:
                    continue
                upsert_user_skill_gap(
                    user=attempt.user,
                    skill=skill,
                    status=UserSkillGap.Status.NOT_STARTED,
                    evidence_source_type="diagnostic",
                    evidence_source_id=str(attempt.id),
                    evidence_summary=gap.notes or f"Identified via diagnostic {attempt.diagnostic.title}",
                )

            mark_attempt_completed(attempt)
            record_session(
                user=attempt.user,
                session_type="DIAGNOSTIC",
                reference_id=attempt.id,
                title=f"Diagnostic: {attempt.diagnostic.title}",
                summary=result_schema.summary or result_schema.recommended_focus,
            )

        return {"ok": True, "attempt_id": attempt_id}
    except Exception:
        logger.exception("Failed generating diagnostic result for attempt %s", attempt_id)
        mark_attempt_failed(attempt)
        return {"ok": False, "attempt_id": attempt_id}

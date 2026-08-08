"""Celery tasks for debrief question generation and evaluation."""

from __future__ import annotations

import logging

from celery import shared_task
from django.db import transaction

from apps.ai.services.debrief_service import run_debrief_question
from apps.ai.services.evaluation_service import run_debrief_evaluation
from apps.challenges.models import ChallengeAttempt
from apps.debriefs.models import (
    DebriefAnswer,
    DebriefEvaluation,
    DebriefQuestion,
    DebriefSession,
)
from apps.debriefs.services import _submission_summary
from apps.gaps.models import UserSkillGap
from apps.gaps.services import upsert_user_skill_gap
from apps.roles.models import Skill
from apps.sessions.services import record_session

logger = logging.getLogger(__name__)


@shared_task(name="apps.debriefs.tasks.generate_debrief_question")
def generate_debrief_question(session_id: int) -> dict:
    try:
        session = DebriefSession.objects.select_related(
            "attempt__challenge",
            "attempt__submission",
            "attempt__user",
        ).prefetch_related("questions__answer", "attempt__challenge__challenge_skills__skill").get(
            pk=session_id
        )
    except DebriefSession.DoesNotExist:
        logger.error("Debrief session %s not found", session_id)
        return {"ok": False, "error": "not_found"}

    if session.status in {
        DebriefSession.Status.EVALUATING,
        DebriefSession.Status.COMPLETED,
        DebriefSession.Status.FAILED,
    }:
        return {"ok": True, "skipped": True}

    next_order = session.questions.count() + 1
    if next_order > session.max_questions:
        from apps.debriefs.tasks import evaluate_debrief

        evaluate_debrief.delay(session.id)
        return {"ok": True, "queued_evaluation": True}

    attempt = session.attempt
    challenge = attempt.challenge
    prior_qa = []
    for q in session.questions.all():
        answer_text = ""
        try:
            answer_text = q.answer.answer_text
        except DebriefAnswer.DoesNotExist:
            answer_text = ""
        prior_qa.append(
            {
                "order": q.order,
                "prompt": q.prompt_text,
                "answer": answer_text,
            }
        )
    focus_skill = ""
    first_skill = challenge.challenge_skills.select_related("skill").first()
    if first_skill:
        focus_skill = first_skill.skill.slug

    try:
        schema = run_debrief_question(
            challenge_title=challenge.title,
            modality=challenge.modality,
            submission_summary=_submission_summary(attempt),
            prior_qa=prior_qa,
            next_order=next_order,
            max_questions=session.max_questions,
            focus_skill=focus_skill,
        )
        with transaction.atomic():
            DebriefQuestion.objects.create(
                session=session,
                order=next_order,
                prompt_text=schema.prompt_text,
                status=DebriefQuestion.Status.ASKED,
            )
            if session.status != DebriefSession.Status.ACTIVE:
                session.status = DebriefSession.Status.ACTIVE
                session.save(update_fields=["status", "updated_at"])
        return {"ok": True, "session_id": session_id, "order": next_order}
    except Exception:
        logger.exception("Failed generating debrief question for session %s", session_id)
        session.status = DebriefSession.Status.FAILED
        session.save(update_fields=["status", "updated_at"])
        return {"ok": False, "session_id": session_id}


@shared_task(name="apps.debriefs.tasks.evaluate_debrief")
def evaluate_debrief(session_id: int) -> dict:
    try:
        session = DebriefSession.objects.select_related(
            "attempt__challenge",
            "attempt__submission",
            "attempt__user",
        ).prefetch_related("questions__answer", "attempt__challenge__challenge_skills__skill").get(
            pk=session_id
        )
    except DebriefSession.DoesNotExist:
        logger.error("Debrief session %s not found", session_id)
        return {"ok": False, "error": "not_found"}

    attempt = session.attempt
    challenge = attempt.challenge
    qa_pairs = []
    for q in session.questions.all():
        answer_text = ""
        try:
            answer_text = q.answer.answer_text
        except DebriefAnswer.DoesNotExist:
            answer_text = ""
        qa_pairs.append({"order": q.order, "prompt": q.prompt_text, "answer": answer_text})

    focus_skill = ""
    first_skill = challenge.challenge_skills.select_related("skill").first()
    if first_skill:
        focus_skill = first_skill.skill.slug

    try:
        schema = run_debrief_evaluation(
            challenge_title=challenge.title,
            modality=challenge.modality,
            submission_summary=_submission_summary(attempt),
            qa_pairs=qa_pairs,
            focus_skill=focus_skill,
        )
        with transaction.atomic():
            DebriefEvaluation.objects.update_or_create(
                session=session,
                defaults={
                    "strengths": schema.strengths,
                    "gaps": schema.gaps,
                    "next_focus": schema.next_focus,
                    "score": schema.score,
                    "summary": schema.summary,
                    "raw_payload": schema.model_dump(),
                },
            )
            session.status = DebriefSession.Status.COMPLETED
            session.save(update_fields=["status", "updated_at"])

            attempt.status = ChallengeAttempt.Status.COMPLETED
            attempt.save(update_fields=["status"])
            if attempt.daily_challenge_id:
                from apps.challenges.models import DailyChallenge

                daily = attempt.daily_challenge
                daily.status = DailyChallenge.Status.COMPLETED
                daily.save(update_fields=["status", "updated_at"])

            # Update roadmap gaps from challenge skills + evaluation
            gap_status = (
                UserSkillGap.Status.CLOSED
                if schema.score >= 75
                else UserSkillGap.Status.IN_PROGRESS
            )
            for link in challenge.challenge_skills.select_related("skill").all():
                upsert_user_skill_gap(
                    user=attempt.user,
                    skill=link.skill,
                    status=gap_status,
                    evidence_source_type="debrief",
                    evidence_source_id=str(session.id),
                    evidence_summary=schema.summary or schema.next_focus,
                )

            if schema.next_focus:
                skill = Skill.objects.filter(slug=schema.next_focus).first()
                if skill:
                    upsert_user_skill_gap(
                        user=attempt.user,
                        skill=skill,
                        status=UserSkillGap.Status.IN_PROGRESS,
                        evidence_source_type="debrief",
                        evidence_source_id=str(session.id),
                        evidence_summary=schema.summary,
                    )

            record_session(
                user=attempt.user,
                session_type="DEBRIEF",
                reference_id=session.id,
                title=f"Debrief: {challenge.title}",
                summary=schema.summary,
            )
        return {"ok": True, "session_id": session_id}
    except Exception:
        logger.exception("Failed evaluating debrief session %s", session_id)
        session.status = DebriefSession.Status.FAILED
        session.save(update_fields=["status", "updated_at"])
        return {"ok": False, "session_id": session_id}

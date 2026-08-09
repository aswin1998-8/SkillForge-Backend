"""Challenge-related Celery tasks."""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="apps.challenges.tasks.ping_challenges")
def ping_challenges() -> str:
    return "challenges-ok"


@shared_task(bind=True, max_retries=2, default_retry_delay=20)
def evaluate_challenge_submission(self, attempt_id: int) -> str:
    from apps.ai.services.assessment_service import evaluate_challenge
    from apps.challenges.models import ChallengeAttempt
    from apps.diagnostics.models import SkillEvidence
    from apps.gaps.models import UserSkillGap
    from apps.gaps.services import upsert_user_skill_gap

    try:
        attempt = ChallengeAttempt.objects.select_related(
            "challenge",
            "submission",
            "user",
        ).prefetch_related("challenge__challenge_skills__skill").get(pk=attempt_id)
    except ChallengeAttempt.DoesNotExist:
        logger.warning("Challenge attempt %s missing for AI eval", attempt_id)
        return "missing"

    submission = getattr(attempt, "submission", None)
    if submission is None:
        return "no-submission"

    skills = [cs.skill for cs in attempt.challenge.challenge_skills.all()]
    context = {
        "challenge": {
            "title": attempt.challenge.title,
            "modality": attempt.challenge.modality,
            "difficulty": attempt.challenge.difficulty,
        },
        "skills": [{"name": s.name, "slug": s.slug} for s in skills],
        "assessment_stage": "CODING",
    }
    payload = {
        "text_answer": submission.text_answer,
        "code": submission.code,
        "architecture_data": submission.architecture_data,
        "research_data": submission.research_data,
    }
    try:
        result = evaluate_challenge(context, payload)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Challenge AI eval failed for %s", attempt_id)
        raise self.retry(exc=exc) from exc

    score = result.mean_score() if hasattr(result, "mean_score") else 0.5
    for skill in skills:
        SkillEvidence.objects.create(
            user=attempt.user,
            skill=skill,
            stage="CODING",
            score=float(score),
            evaluation=result.evaluation.model_dump() if result.evaluation else {},
            strengths=result.strengths,
            weaknesses=result.weaknesses,
            confidence=float(result.confidence or 0.0),
            source_type="challenge_submission",
        )
        status = (
            UserSkillGap.Status.CLOSED
            if score >= 0.75
            else UserSkillGap.Status.IN_PROGRESS
        )
        upsert_user_skill_gap(
            user=attempt.user,
            skill=skill,
            status=status,
            evidence_source_type="challenge_ai",
            evidence_source_id=str(attempt.id),
            evidence_summary=result.summary or f"score={score:.2f}",
        )
    return "ok"

"""Debrief session lifecycle services."""

from __future__ import annotations

from django.db import transaction
from rest_framework.exceptions import NotFound, ValidationError

from apps.challenges.models import ChallengeAttempt
from apps.debriefs.models import DebriefAnswer, DebriefQuestion, DebriefSession
from apps.users.models import User


@transaction.atomic
def start_debrief_for_attempt(*, attempt_id: int) -> DebriefSession:
    try:
        attempt = ChallengeAttempt.objects.select_related("challenge", "submission").get(
            pk=attempt_id
        )
    except ChallengeAttempt.DoesNotExist as exc:
        raise NotFound("Challenge attempt not found.") from exc

    session, created = DebriefSession.objects.get_or_create(
        attempt=attempt,
        defaults={"status": DebriefSession.Status.PENDING, "max_questions": 5},
    )
    if created or session.status == DebriefSession.Status.PENDING:
        from apps.debriefs.tasks import generate_debrief_question

        transaction.on_commit(lambda: generate_debrief_question.delay(session.id))
    return session


def get_debrief_for_user(*, user: User, session_id: int) -> DebriefSession:
    try:
        return DebriefSession.objects.select_related(
            "attempt__challenge",
            "attempt__submission",
            "evaluation",
        ).prefetch_related("questions__answer").get(
            pk=session_id,
            attempt__user=user,
        )
    except DebriefSession.DoesNotExist as exc:
        raise NotFound("Debrief session not found.") from exc


@transaction.atomic
def answer_debrief_question(
    *,
    user: User,
    session_id: int,
    answer_text: str,
) -> DebriefSession:
    session = get_debrief_for_user(user=user, session_id=session_id)
    if session.status not in {DebriefSession.Status.ACTIVE, DebriefSession.Status.PENDING}:
        raise ValidationError("Debrief session is not accepting answers.")

    question = (
        session.questions.filter(status=DebriefQuestion.Status.ASKED)
        .order_by("order")
        .first()
    )
    if question is None:
        raise ValidationError("No open debrief question to answer.")

    if not (answer_text or "").strip():
        raise ValidationError({"answer_text": "Answer text is required."})

    DebriefAnswer.objects.update_or_create(
        question=question,
        defaults={"answer_text": answer_text.strip()},
    )
    question.status = DebriefQuestion.Status.ANSWERED
    question.save(update_fields=["status"])

    answered_count = session.questions.filter(status=DebriefQuestion.Status.ANSWERED).count()
    if answered_count >= session.max_questions:
        session.status = DebriefSession.Status.EVALUATING
        session.save(update_fields=["status", "updated_at"])
        from apps.debriefs.tasks import evaluate_debrief

        transaction.on_commit(lambda: evaluate_debrief.delay(session.id))
    else:
        from apps.debriefs.tasks import generate_debrief_question

        transaction.on_commit(lambda: generate_debrief_question.delay(session.id))

    return session


def _submission_summary(attempt: ChallengeAttempt) -> str:
    submission = getattr(attempt, "submission", None)
    if submission is None:
        return ""
    parts = [
        submission.text_answer or "",
        submission.code or "",
        str(submission.architecture_data or {}),
        str(submission.research_data or {}),
    ]
    return "\n".join(p for p in parts if p).strip()

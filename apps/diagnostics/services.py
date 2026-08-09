"""Diagnostic attempt lifecycle services."""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from apps.diagnostics.models import (
    Diagnostic,
    DiagnosticAnswer,
    DiagnosticAttempt,
    DiagnosticQuestion,
)
from apps.users.models import User


def get_active_diagnostics() -> list[Diagnostic]:
    return list(
        Diagnostic.objects.filter(is_active=True).prefetch_related("questions__skill")
    )


def get_diagnostic_or_404(diagnostic_id: int) -> Diagnostic:
    try:
        return Diagnostic.objects.prefetch_related("questions__skill").get(
            pk=diagnostic_id,
            is_active=True,
        )
    except Diagnostic.DoesNotExist as exc:
        raise NotFound("Diagnostic not found.") from exc


@transaction.atomic
def start_attempt(*, user: User, diagnostic_id: int) -> DiagnosticAttempt:
    from apps.diagnostics.adaptive import start_adaptive_attempt

    return start_adaptive_attempt(user=user, diagnostic_id=diagnostic_id)


@transaction.atomic
def save_answers(*, user: User, attempt_id: int, answers: list[dict]) -> DiagnosticAttempt:
    attempt = _get_user_attempt(user, attempt_id)
    if attempt.status != DiagnosticAttempt.Status.IN_PROGRESS:
        raise ValidationError("Answers can only be saved for in-progress attempts.")

    question_ids = {item["question_id"] for item in answers}
    questions = {
        q.id: q
        for q in DiagnosticQuestion.objects.filter(
            diagnostic=attempt.diagnostic,
            id__in=question_ids,
        )
    }
    missing = question_ids - set(questions.keys())
    if missing:
        raise ValidationError({"question_id": f"Invalid question ids: {sorted(missing)}"})

    for item in answers:
        question = questions[item["question_id"]]
        DiagnosticAnswer.objects.update_or_create(
            attempt=attempt,
            question=question,
            defaults={"answer_text": item.get("answer_text") or ""},
        )
    return attempt


@transaction.atomic
def submit_attempt(*, user: User, attempt_id: int) -> DiagnosticAttempt:
    attempt = _get_user_attempt(user, attempt_id)
    if attempt.status not in {
        DiagnosticAttempt.Status.IN_PROGRESS,
        DiagnosticAttempt.Status.SUBMITTED,
    }:
        raise ValidationError("Attempt cannot be submitted in its current state.")

    answer_count = attempt.answers.count()
    if answer_count == 0:
        raise ValidationError("Submit at least one answer before finishing.")

    attempt.status = DiagnosticAttempt.Status.PROCESSING
    attempt.save(update_fields=["status"])

    from apps.diagnostics.tasks import generate_diagnostic_result

    transaction.on_commit(lambda: generate_diagnostic_result.delay(attempt.id))
    return attempt


def get_attempt_for_user(*, user: User, attempt_id: int) -> DiagnosticAttempt:
    return _get_user_attempt(user, attempt_id)


def _get_user_attempt(user: User, attempt_id: int) -> DiagnosticAttempt:
    try:
        return DiagnosticAttempt.objects.select_related("diagnostic", "result").prefetch_related(
            "answers__question",
            "diagnostic__questions",
            "turns__skill",
        ).get(pk=attempt_id, user=user)
    except DiagnosticAttempt.DoesNotExist as exc:
        raise NotFound("Diagnostic attempt not found.") from exc


def mark_attempt_completed(attempt: DiagnosticAttempt) -> DiagnosticAttempt:
    attempt.status = DiagnosticAttempt.Status.COMPLETED
    attempt.completed_at = timezone.now()
    attempt.save(update_fields=["status", "completed_at"])
    return attempt


def mark_attempt_failed(attempt: DiagnosticAttempt) -> DiagnosticAttempt:
    attempt.status = DiagnosticAttempt.Status.FAILED
    attempt.completed_at = timezone.now()
    attempt.save(update_fields=["status", "completed_at"])
    return attempt

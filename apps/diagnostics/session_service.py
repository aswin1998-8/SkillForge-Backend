"""Static-content diagnostic session orchestration."""

from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.diagnostics.adaptive_selector import (
    STAGE_ORDER,
    allocate_stage_questions,
    build_assessment_competencies,
    next_stage,
)
from apps.diagnostics.code_executor import run_test_cases
from apps.diagnostics.grading import (
    grade_session_answer,
    is_open_ended,
)
from apps.diagnostics.models import (
    DiagnosticSession,
    FrameworkTopic,
    Question,
    SessionAnswer,
    SessionQuestion,
)
from apps.diagnostics.synthesis_engine import synthesize_session
from apps.diagnostics.topic_defaults import ensure_default_topics
from apps.users.models import Profile

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = (DiagnosticSession.Status.AWAITING_ANSWERS,)


def get_active_session(*, user) -> DiagnosticSession | None:
    return (
        DiagnosticSession.objects.filter(user=user, status__in=ACTIVE_STATUSES)
        .order_by("-updated_at", "-id")
        .first()
    )


def get_session_for_user(*, user, session_id: int) -> DiagnosticSession:
    try:
        session = DiagnosticSession.objects.prefetch_related(
            "selected_frameworks",
            "questions__content_question__choices",
            "questions__content_question__test_cases",
            "questions__content_question__reference_answer",
            "questions__answer",
            "roadmap_items",
        ).get(id=session_id)
    except DiagnosticSession.DoesNotExist as exc:
        raise NotFound("Diagnostic session not found.") from exc
    if session.user_id != user.id:
        raise PermissionDenied("You do not have access to this session.")
    return session


def _resolve_frameworks(framework_slugs: list[str]) -> list[FrameworkTopic]:
    ensure_default_topics()
    if not framework_slugs:
        raise ValidationError({"framework_slugs": "At least one framework is required."})

    frameworks: list[FrameworkTopic] = []
    missing: list[str] = []
    for slug in framework_slugs:
        normalized = (slug or "").strip().lower()
        try:
            frameworks.append(
                FrameworkTopic.objects.select_related("fundamentals_topic").get(
                    framework_name=normalized
                )
            )
        except FrameworkTopic.DoesNotExist:
            missing.append(normalized)

    if missing:
        raise ValidationError(
            {"framework_slugs": f"Unknown frameworks: {', '.join(missing)}"}
        )
    return frameworks


def _profile_context(user) -> tuple[str, str]:
    profile = Profile.objects.filter(user=user).first()
    current_role = ""
    target_role = ""
    if profile:
        current_role = profile.current_role or ""
        if profile.target_role_label:
            target_role = profile.target_role_label
        elif profile.target_role_id:
            target_role = profile.target_role.name if profile.target_role else ""
    return current_role, target_role


@transaction.atomic
def start_session(*, user, goal: str, framework_slugs: list[str]) -> DiagnosticSession:
    active = get_active_session(user=user)
    if active is not None:
        # Resume in-progress diagnostic instead of forcing a restart.
        return active

    frameworks = _resolve_frameworks(framework_slugs)
    current_role, target_role = _profile_context(user)
    profile = getattr(user, "profile", None)
    difficulty_bump = int(getattr(profile, "diagnostic_difficulty_bump", 0) or 0)

    session = DiagnosticSession.objects.create(
        user=user,
        goal=goal,
        current_role=current_role,
        target_role=target_role if goal == DiagnosticSession.Goal.SWITCH_ROLE else current_role,
        status=DiagnosticSession.Status.AWAITING_ANSWERS,
        current_stage=STAGE_ORDER[0],
        difficulty_bump=difficulty_bump,
    )
    session.selected_frameworks.set(frameworks)
    session.assessment_competencies = build_assessment_competencies(session)
    session.save(update_fields=["assessment_competencies"])

    allocate_stage_questions(session, STAGE_ORDER[0])
    if not session.questions.exists():
        session.status = DiagnosticSession.Status.FAILED
        session.error = "No questions available for selected frameworks."
        session.save(update_fields=["status", "error"])
        raise ValidationError(session.error)

    return session


def _stage_fully_answered(session: DiagnosticSession, stage: str) -> bool:
    stage_questions = session.questions.filter(stage=stage).select_related(
        "content_question"
    )
    if not stage_questions.exists():
        return True
    for sq in stage_questions:
        try:
            sq.answer
        except SessionAnswer.DoesNotExist:
            return False
        # All modalities complete on ANSWERED (keyword auto-grade for open-ended).
        if sq.status not in {
            SessionQuestion.Status.ANSWERED,
            SessionQuestion.Status.SELF_RATED,
        }:
            return False
    return True


def _advance_session_stage(session: DiagnosticSession) -> None:
    while session.current_stage and _stage_fully_answered(session, session.current_stage):
        nxt = next_stage(session.current_stage)
        if nxt is None:
            synthesize_session(session)
            return
        session.current_stage = nxt
        session.save(update_fields=["current_stage"])
        created = allocate_stage_questions(session, nxt)
        if not created:
            nxt2 = next_stage(nxt)
            if nxt2 is None:
                synthesize_session(session)
                return
            session.current_stage = nxt2
            session.save(update_fields=["current_stage"])
            continue
        return


@transaction.atomic
def submit_stage_answers(
    *,
    user,
    session_id: int,
    answers: list[dict],
) -> DiagnosticSession:
    session = get_session_for_user(user=user, session_id=session_id)
    if session.status != DiagnosticSession.Status.AWAITING_ANSWERS:
        raise ValidationError("Session is not accepting answers.")

    for item in answers:
        sq_id = item["question_id"]
        try:
            sq = session.questions.select_related("content_question").get(id=sq_id)
        except SessionQuestion.DoesNotExist as exc:
            raise ValidationError(f"Invalid question_id: {sq_id}") from exc

        if sq.stage != session.current_stage:
            raise ValidationError("Question does not belong to the current stage.")

        grade_session_answer(
            session_question=sq,
            answer_text=item.get("answer_text") or "",
            choice_id=item.get("choice_id"),
            confidence_rating=item.get("confidence_rating"),
            run_tests_fn=run_test_cases,
        )

    _advance_session_stage(session)
    return get_session_for_user(user=user, session_id=session_id)


@transaction.atomic
def reveal_answer(*, user, session_id: int, answer_id: int) -> dict:
    session = get_session_for_user(user=user, session_id=session_id)
    try:
        answer = SessionAnswer.objects.select_related(
            "question__content_question__reference_answer"
        ).get(id=answer_id, question__session=session)
    except SessionAnswer.DoesNotExist as exc:
        raise ValidationError("Answer not found.") from exc

    content = answer.question.content_question
    if not is_open_ended(content.modality):
        raise ValidationError("Reference answers are only available for open-ended questions.")

    if answer.question.status == SessionQuestion.Status.ASKED:
        raise ValidationError("Submit an answer before revealing the reference.")

    ref = getattr(content, "reference_answer", None)
    if ref is None:
        raise ValidationError("No reference answer configured for this question.")

    answer.revealed_at = timezone.now()
    answer.save(update_fields=["revealed_at"])
    answer.question.status = SessionQuestion.Status.REVEALED
    answer.question.save(update_fields=["status"])

    return {
        "answer_id": answer.id,
        "reference_text": ref.reference_text,
        "rubric_points": ref.rubric_points or [],
    }


@transaction.atomic
def self_rate_answer(
    *,
    user,
    session_id: int,
    answer_id: int,
    rubric_alignment: dict,
) -> SessionAnswer:
    session = get_session_for_user(user=user, session_id=session_id)
    try:
        answer = SessionAnswer.objects.select_related("question__content_question").get(
            id=answer_id,
            question__session=session,
        )
    except SessionAnswer.DoesNotExist as exc:
        raise ValidationError("Answer not found.") from exc

    content = answer.question.content_question
    if not is_open_ended(content.modality):
        raise ValidationError("Self-rating is only for open-ended questions.")

    if answer.question.status not in {
        SessionQuestion.Status.ANSWERED,
        SessionQuestion.Status.REVEALED,
    }:
        raise ValidationError("Answer must be submitted and revealed before self-rating.")

    ref = getattr(content, "reference_answer", None)
    expected_points = (ref.rubric_points if ref else []) or []
    cleaned: dict[str, str] = {}
    for point in expected_points:
        value = rubric_alignment.get(point)
        if value not in {"yes", "no", "partial"}:
            raise ValidationError(
                {point: "Each rubric point requires yes, no, or partial."}
            )
        cleaned[point] = value

    answer.self_rated_alignment = cleaned
    answer.self_rated_at = timezone.now()
    answer.save(update_fields=["self_rated_alignment", "self_rated_at"])
    answer.question.status = SessionQuestion.Status.SELF_RATED
    answer.question.save(update_fields=["status"])

    _advance_session_stage(session)
    return answer


def run_tests_preview(
    *,
    user,
    session_id: int,
    question_id: int,
    code: str,
) -> list[dict]:
    session = get_session_for_user(user=user, session_id=session_id)
    try:
        sq = session.questions.select_related("content_question").get(id=question_id)
    except SessionQuestion.DoesNotExist as exc:
        raise ValidationError("Question not found.") from exc

    content = sq.content_question
    if content.modality not in {Question.Modality.CODING, Question.Modality.FIND_ISSUES}:
        raise ValidationError("Test preview is only for coding questions.")

    visible_cases = [tc for tc in content.test_cases.all() if not tc.is_hidden]
    return run_test_cases(code=code, language=content.language, test_cases=visible_cases)

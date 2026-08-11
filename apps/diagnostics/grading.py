"""Deterministic grading for diagnostic answers."""

from __future__ import annotations

from apps.core.keyword_grade import grade_open_ended_keywords
from apps.diagnostics.models import (
    Question,
    QuestionChoice,
    ReferenceAnswer,
    SessionAnswer,
    SessionQuestion,
)


def grade_foundational(
    *,
    question: Question,
    answer_text: str,
    choice_id: int | None = None,
) -> tuple[bool, dict]:
    choices = list(question.choices.all())
    if not choices:
        return False, {"error": "no_choices_configured"}

    if choice_id is not None:
        matched = next((c for c in choices if c.id == choice_id), None)
        if matched is None:
            return False, {"error": "invalid_choice_id", "choice_id": choice_id}
        is_correct = matched.is_correct
        return is_correct, {
            "method": "choice_id",
            "matched_choice_id": matched.id,
            "expected_correct": matched.is_correct,
        }

    normalized = (answer_text or "").strip().lower()
    for choice in choices:
        if choice.is_correct and choice.choice_text.strip().lower() == normalized:
            return True, {
                "method": "text_match",
                "matched_choice_id": choice.id,
                "expected_correct": True,
            }

    correct_ids = [c.id for c in choices if c.is_correct]
    return False, {
        "method": "text_match",
        "matched_choice_id": None,
        "expected_correct_ids": correct_ids,
    }


def grade_coding(
    *,
    question: Question,
    answer_text: str,
    run_tests_fn,
) -> tuple[bool, dict]:
    test_cases = list(question.test_cases.order_by("order", "id"))
    if not test_cases:
        return False, {"error": "no_test_cases_configured"}

    results = run_tests_fn(
        code=answer_text,
        language=question.language,
        test_cases=test_cases,
    )
    passed = all(r.get("passed") for r in results)
    return passed, {
        "method": "test_execution",
        "test_results": results,
    }


OPEN_ENDED_MODALITIES = {
    Question.Modality.SCENARIO,
    Question.Modality.DEFEND,
    Question.Modality.DIAGNOSE,
    Question.Modality.ARCHITECT,
    Question.Modality.EXPLAIN,
    Question.Modality.COMMUNICATE,
}


def is_open_ended(modality: str) -> bool:
    return modality in OPEN_ENDED_MODALITIES


def compute_open_ended_score(self_rated_alignment: dict | None) -> float | None:
    """Legacy self-rate score (kept for older answers)."""
    if not self_rated_alignment:
        return None
    if not isinstance(self_rated_alignment, dict):
        return None
    total = len(self_rated_alignment)
    if total == 0:
        return None
    score = 0.0
    for value in self_rated_alignment.values():
        normalized = str(value or "").strip().lower()
        if normalized == "yes":
            score += 1.0
        elif normalized == "partial":
            score += 0.5
    return score / total


def keyword_score_from_detail(grading_detail: dict | None) -> float | None:
    if not isinstance(grading_detail, dict):
        return None
    method = grading_detail.get("method")
    if method not in {"keyword_rubric", "keyword_reference_overlap"}:
        return None
    try:
        return float(grading_detail.get("score"))
    except (TypeError, ValueError):
        return None


def answer_score_for_adaptive(answer: SessionAnswer) -> float | None:
    question = answer.question.content_question
    modality = question.modality

    if modality == Question.Modality.FOUNDATIONAL:
        if answer.is_correct is None:
            return None
        return 1.0 if answer.is_correct else 0.0

    if modality in {Question.Modality.CODING, Question.Modality.FIND_ISSUES}:
        if answer.is_correct is None:
            return None
        return 1.0 if answer.is_correct else 0.0

    if is_open_ended(modality):
        keyword_score = keyword_score_from_detail(answer.grading_detail)
        if keyword_score is not None:
            return keyword_score
        return compute_open_ended_score(answer.self_rated_alignment)

    return None


def grade_session_answer(
    *,
    session_question: SessionQuestion,
    answer_text: str,
    choice_id: int | None = None,
    confidence_rating: int | None = None,
    run_tests_fn=None,
) -> SessionAnswer:
    content = session_question.content_question
    modality = content.modality

    answer, _ = SessionAnswer.objects.get_or_create(question=session_question)
    answer.answer_text = answer_text
    answer.choice_id = choice_id
    answer.confidence_rating = confidence_rating
    answer.grading_detail = {}
    answer.is_correct = None

    if modality == Question.Modality.FOUNDATIONAL:
        is_correct, detail = grade_foundational(
            question=content,
            answer_text=answer_text,
            choice_id=choice_id,
        )
        answer.is_correct = is_correct
        answer.grading_detail = detail
        session_question.status = SessionQuestion.Status.ANSWERED

    elif modality in {Question.Modality.CODING, Question.Modality.FIND_ISSUES}:
        if run_tests_fn is None:
            raise ValueError("run_tests_fn required for coding questions")
        is_correct, detail = grade_coding(
            question=content,
            answer_text=answer_text,
            run_tests_fn=run_tests_fn,
        )
        answer.is_correct = is_correct
        answer.grading_detail = detail
        session_question.status = SessionQuestion.Status.ANSWERED

    elif is_open_ended(modality):
        try:
            ref = content.reference_answer
        except ReferenceAnswer.DoesNotExist:
            ref = None
        rubric_points = list(getattr(ref, "rubric_points", None) or []) if ref else []
        reference_text = getattr(ref, "reference_text", None) if ref else None
        is_correct, _score, detail = grade_open_ended_keywords(
            answer_text=answer_text,
            rubric_points=rubric_points,
            reference_text=reference_text,
        )
        answer.is_correct = is_correct
        answer.grading_detail = detail
        session_question.status = SessionQuestion.Status.ANSWERED

    answer.save()
    session_question.save(update_fields=["status"])
    return answer

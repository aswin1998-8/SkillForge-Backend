"""Tests for keyword / rubric grading and open-ended auto-grade."""

from __future__ import annotations

import pytest

from apps.core.keyword_grade import grade_open_ended_keywords
from apps.diagnostics.grading import grade_session_answer
from apps.diagnostics.models import (
    FundamentalsTopic,
    Question,
    ReferenceAnswer,
    SessionAnswer,
    SessionQuestion,
)
from apps.diagnostics.models import DiagnosticSession
from apps.users.models import User


def test_keyword_rubric_partial_credit() -> None:
    is_correct, score, detail = grade_open_ended_keywords(
        answer_text="Use caching and index the hot query path for latency.",
        rubric_points=[
            "caching",
            "index",
            "horizontal scaling",
        ],
    )
    assert detail["method"] == "keyword_rubric"
    assert score == pytest.approx(2 / 3)
    assert is_correct is True


def test_keyword_reference_fallback() -> None:
    is_correct, score, detail = grade_open_ended_keywords(
        answer_text="cache redis latency",
        rubric_points=[],
        reference_text="Use Redis cache to reduce latency under load",
    )
    assert detail["method"] == "keyword_reference_overlap"
    assert score > 0
    assert isinstance(is_correct, bool)


@pytest.mark.django_db
def test_grade_session_open_ended_without_confidence() -> None:
    user = User.objects.create_user(email="grader@example.com", password="x")
    topic, _ = FundamentalsTopic.objects.get_or_create(
        language_family="javascript",
        defaults={"competency_areas": ["async"]},
    )
    question = Question.objects.create(
        fundamentals_topic=topic,
        competency_area="async",
        modality=Question.Modality.SCENARIO,
        question_text="How do you handle backpressure?",
        difficulty_tier=2,
    )
    ReferenceAnswer.objects.create(
        question=question,
        reference_text="Use queues and rate limiting.",
        rubric_points=["queues", "rate limiting", "load shedding"],
    )
    session = DiagnosticSession.objects.create(
        user=user,
        goal="sharpen_current",
        current_stage="SCENARIO",
        status=DiagnosticSession.Status.AWAITING_ANSWERS,
    )
    sq = SessionQuestion.objects.create(
        session=session,
        content_question=question,
        stage="SCENARIO",
        order=1,
        status=SessionQuestion.Status.ASKED,
    )

    answer = grade_session_answer(
        session_question=sq,
        answer_text="I would add a queue and rate limiting at the edge.",
        confidence_rating=None,
    )
    sq.refresh_from_db()
    assert isinstance(answer, SessionAnswer)
    assert sq.status == SessionQuestion.Status.ANSWERED
    assert answer.grading_detail.get("method") == "keyword_rubric"
    assert answer.is_correct is not None

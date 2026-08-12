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


def test_instructional_rubric_matches_research_answer() -> None:
    """Criteria-style rubric points should grade substantive research answers."""
    answer = """
    Strategy 1 — Dynamic rendering / no shared caching: Render personalized pages
    per request. Trade-off: safer isolation, higher TTFB.
    Strategy 2 — Cache only shared/public data; keep personalization dynamic.
    Next.js — Static and Dynamic Rendering
    """
    is_correct, score, detail = grade_open_ended_keywords(
        answer_text=answer,
        rubric_points=[
            "Compares at least two caching approaches with trade-offs",
            "Includes a credible source or docs reference",
        ],
        reference_text=(
            "Compare full-route cache vs dynamic rendering with partial caching."
        ),
    )
    assert detail["method"] in {"keyword_rubric", "keyword_reference_overlap"}
    assert score >= 0.5
    assert is_correct is True


def test_theory_rubric_blends_with_model_answer() -> None:
    answer = (
        "React reconciles trees by comparing element types and keys. "
        "Unstable keys remount components and lose state when the list reorders."
    )
    is_correct, score, detail = grade_open_ended_keywords(
        answer_text=answer,
        rubric_points=[
            "Explains tree diff / reconciliation at a high level",
            "Explains why unstable keys cause remounts/bugs",
        ],
        rubric_hints=[
            "Clear reconciliation mental model",
            "Understands key stability impact",
        ],
        reference_text=(
            "React reconciles trees by comparing element types and keys. Stable keys "
            "let React match previous instances so state is preserved."
        ),
    )
    assert is_correct is True
    assert score >= 0.5
    assert detail.get("reference_overlap", {}).get("score", 0) > 0


def test_diagnose_answer_matches_nplus1_rubric() -> None:
    answer = (
        "This is classic N+1 from nested serializers. "
        "Confirm with django-debug-toolbar query count, then fix with select_related."
    )
    is_correct, score, detail = grade_open_ended_keywords(
        answer_text=answer,
        rubric_points=[
            "Identifies N+1 / missing prefetch as likely cause",
            "Proposes a concrete verification (query count / EXPLAIN)",
        ],
        reference_text=(
            "Classic N+1: list fetches posts then one query per related user. "
            "Fix with select_related/prefetch_related and verify with query counting."
        ),
    )
    assert is_correct is True
    assert score >= 0.5


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
    assert answer.grading_detail.get("method") in {
        "keyword_rubric",
        "keyword_reference_overlap",
    }
    assert answer.is_correct is not None

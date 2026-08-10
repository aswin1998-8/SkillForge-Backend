"""Tests for static diagnostic grading."""

from __future__ import annotations

import pytest

from apps.diagnostics.grading import (
    compute_open_ended_score,
    grade_foundational,
)
from apps.diagnostics.models import FundamentalsTopic, Question, QuestionChoice


@pytest.mark.django_db
def test_grade_foundational_by_choice_id() -> None:
    topic, _ = FundamentalsTopic.objects.get_or_create(
        language_family="javascript",
        defaults={"competency_areas": ["closures"]},
    )
    question = Question.objects.create(
        fundamentals_topic=topic,
        competency_area="closures",
        modality=Question.Modality.FOUNDATIONAL,
        question_text="What is a closure?",
        difficulty_tier=1,
    )
    correct = QuestionChoice.objects.create(
        question=question,
        choice_text="Function plus lexical scope",
        is_correct=True,
    )
    QuestionChoice.objects.create(
        question=question,
        choice_text="A loop",
        is_correct=False,
    )

    is_correct, detail = grade_foundational(
        question=question,
        answer_text="",
        choice_id=correct.id,
    )
    assert is_correct is True
    assert detail["method"] == "choice_id"


def test_compute_open_ended_score() -> None:
    score = compute_open_ended_score({"a": "yes", "b": "partial", "c": "no"})
    assert score == pytest.approx(0.5)

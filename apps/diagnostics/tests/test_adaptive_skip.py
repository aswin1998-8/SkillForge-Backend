"""Per-area skip-ahead allocation for diagnostic sessions."""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.diagnostics.models import (
    CodingTestCase,
    DiagnosticSession,
    FrameworkTopic,
    Question,
    QuestionChoice,
    ReferenceAnswer,
    SessionQuestion,
)
from apps.diagnostics.session_service import start_session, submit_stage_answers
from apps.diagnostics.topic_defaults import ensure_default_topics
from apps.users.models import User


@pytest.fixture
def user(db) -> User:
    return User.objects.create_user(email="skip@test.com", password="testpass123")


def _choice(question: Question, text: str, *, correct: bool) -> QuestionChoice:
    return QuestionChoice.objects.create(
        question=question, choice_text=text, is_correct=correct
    )


def _foundational(framework: FrameworkTopic, area: str, text: str) -> Question:
    q = Question.objects.create(
        framework_topic=framework,
        competency_area=area,
        modality=Question.Modality.FOUNDATIONAL,
        question_text=text,
        difficulty_tier=1,
    )
    _choice(q, "right", correct=True)
    _choice(q, "wrong", correct=False)
    return q


@pytest.mark.django_db
def test_three_correct_foundational_skips_to_harder_modality(user: User) -> None:
    ensure_default_topics()
    react = FrameworkTopic.objects.get(framework_name="react")
    for i in range(3):
        _foundational(react, "hooks", f"hooks foundational {i}")
    scenario = Question.objects.create(
        framework_topic=react,
        competency_area="hooks",
        modality=Question.Modality.SCENARIO,
        question_text="easy scenario should be skipped",
        difficulty_tier=1,
    )
    ReferenceAnswer.objects.create(
        question=scenario,
        reference_text="scenario",
        rubric_points=["scenario"],
    )
    hard = Question.objects.create(
        framework_topic=react,
        competency_area="hooks",
        modality=Question.Modality.CODING,
        question_text="harder coding after skip",
        difficulty_tier=2,
        language="javascript",
    )
    CodingTestCase.objects.create(
        question=hard, input="1", expected_output="1", is_hidden=False, order=1
    )

    session = start_session(user=user, goal="sharpen_current", framework_slugs=["react"])
    session.assessment_competencies = [
        {"framework_slug": "react", "competency_area": "hooks", "source": "framework"}
    ]
    session.save(update_fields=["assessment_competencies"])

    for _ in range(3):
        asked = session.questions.filter(status=SessionQuestion.Status.ASKED).first()
        assert asked is not None
        assert asked.content_question.modality == Question.Modality.FOUNDATIONAL
        correct = asked.content_question.choices.get(is_correct=True)
        session = submit_stage_answers(
            user=user,
            session_id=session.id,
            answers=[
                {
                    "question_id": asked.id,
                    "choice_id": correct.id,
                    "answer_text": correct.choice_text,
                }
            ],
        )

    session = DiagnosticSession.objects.get(pk=session.id)
    assert session.area_tracks.get("hooks", {}).get("skip_easy") is True
    asked = session.questions.filter(status=SessionQuestion.Status.ASKED).first()
    assert asked is not None
    assert asked.content_question.modality != Question.Modality.FOUNDATIONAL
    assert asked.content_question.modality != Question.Modality.SCENARIO
    assert asked.content_question.modality in {
        Question.Modality.CODING,
        Question.Modality.FIND_ISSUES,
        Question.Modality.DIAGNOSE,
    }


@pytest.mark.django_db
def test_missed_foundational_keeps_easy_follow_up(user: User) -> None:
    ensure_default_topics()
    react = FrameworkTopic.objects.get(framework_name="react")
    for i in range(3):
        _foundational(react, "hooks", f"hooks miss {i}")
    scenario = Question.objects.create(
        framework_topic=react,
        competency_area="hooks",
        modality=Question.Modality.SCENARIO,
        question_text="keep grinding scenario",
        difficulty_tier=1,
    )
    ReferenceAnswer.objects.create(
        question=scenario,
        reference_text="scenario",
        rubric_points=["scenario"],
    )
    Question.objects.create(
        framework_topic=react,
        competency_area="hooks",
        modality=Question.Modality.CODING,
        question_text="coding after miss should not be first extra",
        difficulty_tier=2,
        language="javascript",
    )

    session = start_session(user=user, goal="sharpen_current", framework_slugs=["react"])
    session.assessment_competencies = [
        {"framework_slug": "react", "competency_area": "hooks", "source": "framework"}
    ]
    session.save(update_fields=["assessment_competencies"])

    for idx in range(3):
        asked = session.questions.filter(status=SessionQuestion.Status.ASKED).first()
        assert asked is not None
        if idx < 2:
            choice = asked.content_question.choices.get(is_correct=True)
        else:
            choice = asked.content_question.choices.get(is_correct=False)
        session = submit_stage_answers(
            user=user,
            session_id=session.id,
            answers=[
                {
                    "question_id": asked.id,
                    "choice_id": choice.id,
                    "answer_text": choice.choice_text,
                }
            ],
        )

    session = DiagnosticSession.objects.get(pk=session.id)
    assert session.area_tracks.get("hooks", {}).get("skip_easy") is not True
    asked = session.questions.filter(status=SessionQuestion.Status.ASKED).first()
    assert asked is not None
    assert asked.content_question.modality == Question.Modality.SCENARIO


@pytest.mark.django_db
def test_session_respects_question_budget(user: User, settings) -> None:
    settings.DIAGNOSTIC_SESSION_QUESTION_BUDGET = 2
    ensure_default_topics()
    react = FrameworkTopic.objects.get(framework_name="react")
    for i in range(5):
        _foundational(react, "hooks", f"budget hooks {i}")

    session = start_session(user=user, goal="sharpen_current", framework_slugs=["react"])
    session.assessment_competencies = [
        {"framework_slug": "react", "competency_area": "hooks", "source": "framework"}
    ]
    session.save(update_fields=["assessment_competencies"])

    for _ in range(2):
        asked = session.questions.filter(status=SessionQuestion.Status.ASKED).first()
        if asked is None:
            break
        choice = asked.content_question.choices.get(is_correct=True)
        session = submit_stage_answers(
            user=user,
            session_id=session.id,
            answers=[
                {
                    "question_id": asked.id,
                    "choice_id": choice.id,
                    "answer_text": choice.choice_text,
                }
            ],
        )

    session = DiagnosticSession.objects.get(pk=session.id)
    assert session.questions.count() <= 2
    assert session.status == DiagnosticSession.Status.COMPLETED


@pytest.mark.django_db
def test_never_reasks_seen_question(user: User) -> None:
    ensure_default_topics()
    react = FrameworkTopic.objects.get(framework_name="react")
    _foundational(react, "hooks", "unique never repeat")
    session = start_session(user=user, goal="sharpen_current", framework_slugs=["react"])
    asked = session.questions.filter(status=SessionQuestion.Status.ASKED).first()
    first_content_ids = set(session.questions.values_list("content_question_id", flat=True))
    choice = asked.content_question.choices.get(is_correct=True)
    session = submit_stage_answers(
        user=user,
        session_id=session.id,
        answers=[
            {
                "question_id": asked.id,
                "choice_id": choice.id,
                "answer_text": choice.choice_text,
            }
        ],
    )
    later_ids = list(session.questions.values_list("content_question_id", flat=True))
    assert len(later_ids) == len(set(later_ids))
    assert first_content_ids <= set(later_ids)


@pytest.mark.django_db
def test_start_session_returns_one_current_question(user: User) -> None:
    ensure_default_topics()
    api = APIClient()
    api.force_authenticate(user=user)
    from django.core.management import call_command

    call_command("import_questions", file="content/sample_questions.json")
    response = api.post(
        "/api/v1/diagnostic-sessions/",
        {"goal": "sharpen_current", "framework_slugs": ["react"]},
        format="json",
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert len(data["current_questions"]) == 1
    assert data["current_questions"][0]["status"] == "ASKED"

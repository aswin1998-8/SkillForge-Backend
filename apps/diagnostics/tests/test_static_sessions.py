"""Static diagnostic session tests."""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.diagnostics.models import DiagnosticSession, FrameworkTopic, Question
from apps.diagnostics.topic_defaults import ensure_default_topics
from apps.users.models import User


@pytest.fixture
def api() -> APIClient:
    return APIClient()


@pytest.fixture
def user(db) -> User:
    return User.objects.create_user(
        email="diag@test.com",
        password="testpass123",
    )


@pytest.fixture
def authed_api(api: APIClient, user: User) -> APIClient:
    api.force_authenticate(user=user)
    return api


@pytest.fixture
def seeded_topics(db):
    ensure_default_topics()
    from django.core.management import call_command

    call_command("import_questions", file="content/sample_questions.json")


@pytest.mark.django_db
def test_framework_topics_list(authed_api: APIClient, seeded_topics) -> None:
    response = authed_api.get("/api/v1/framework-topics/")
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 4


@pytest.mark.django_db
def test_start_diagnostic_session(authed_api: APIClient, user: User, seeded_topics) -> None:
    response = authed_api.post(
        "/api/v1/diagnostic-sessions/",
        {"goal": "sharpen_current", "framework_slugs": ["react", "django"]},
        format="json",
    )
    assert response.status_code == 201
    payload = response.json()["data"]
    assert payload["status"] == "AWAITING_ANSWERS"
    assert payload["current_stage"] == "FOUNDATIONAL"
    assert len(payload["current_questions"]) > 0


@pytest.mark.django_db
def test_foundational_answer_grading(authed_api: APIClient, user: User, seeded_topics) -> None:
    start = authed_api.post(
        "/api/v1/diagnostic-sessions/",
        {"goal": "sharpen_current", "framework_slugs": ["react"]},
        format="json",
    )
    session_id = start.json()["data"]["id"]
    question = start.json()["data"]["current_questions"][0]
    choice_id = question["choices"][0]["id"]

    response = authed_api.post(
        f"/api/v1/diagnostic-sessions/{session_id}/answers/",
        {
            "answers": [
                {
                    "question_id": question["id"],
                    "answer_text": question["choices"][0]["choice_text"],
                    "choice_id": choice_id,
                }
            ]
        },
        format="json",
    )
    assert response.status_code == 200
    answer = response.json()["data"]["questions"][0]["answer"]
    assert answer["is_correct"] is True
    assert answer["grading_detail"]

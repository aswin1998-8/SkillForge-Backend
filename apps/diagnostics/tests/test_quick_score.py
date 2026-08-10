"""Quick Score API tests."""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.diagnostics.quick_score import ensure_default_quick_score_content
from apps.users.models import User


@pytest.fixture
def api() -> APIClient:
    return APIClient()


@pytest.fixture
def user(db) -> User:
    return User.objects.create_user(email="qs@test.com", password="testpass123")


@pytest.mark.django_db
def test_quick_score_flow(api: APIClient, user: User) -> None:
    ensure_default_quick_score_content(force=True)
    api.force_authenticate(user=user)

    questions = api.get("/api/v1/quick-score/questions/?track=frontend")
    assert questions.status_code == 200
    payload = questions.data["data"]
    assert payload["track"] == "frontend"
    assert len(payload["questions"]) >= 5

    answers = []
    for q in payload["questions"]:
        answers.append({"question_id": q["id"], "choice_id": q["choices"][0]["id"]})

    submit = api.post(
        "/api/v1/quick-score/",
        {"track": "frontend", "answers": answers},
        format="json",
    )
    assert submit.status_code in {200, 201}
    attempt = submit.data["data"]
    assert 0 <= attempt["total_score"] <= 100
    assert attempt["band"]
    assert attempt["paragraph_text"]

    og = api.get(f"/api/v1/quick-score/{attempt['id']}/og.png")
    assert og.status_code == 200
    assert og["Content-Type"] == "image/png"
    assert len(og.content) > 100


@pytest.mark.django_db
def test_analytics_event(api: APIClient, user: User) -> None:
    api.force_authenticate(user=user)
    res = api.post(
        "/api/v1/events/",
        {"name": "quick_score_completed", "properties": {"x": 1}},
        format="json",
    )
    assert res.status_code == 201

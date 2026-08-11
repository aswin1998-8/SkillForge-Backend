"""Challenge submit auto-grade smoke tests."""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.challenges.models import (
    Challenge,
    ChallengeAttempt,
    ChallengeModelAnswer,
    ChallengeRubricItem,
)
from apps.challenges.services import submit_challenge
from apps.users.models import User


@pytest.mark.django_db
def test_submit_challenge_keyword_grades_and_completes() -> None:
    user = User.objects.create_user(email="chal@example.com", password="x")
    challenge = Challenge.objects.create(
        title="Theory sample",
        slug="theory-sample-grade",
        modality=Challenge.Modality.THEORY,
        difficulty=1,
        description="Explain caching",
        scenario="API latency",
    )
    ChallengeModelAnswer.objects.create(
        challenge=challenge,
        reference_text="Use Redis caching and indexes.",
    )
    ChallengeRubricItem.objects.create(
        challenge=challenge,
        text="caching",
        order=1,
    )
    ChallengeRubricItem.objects.create(
        challenge=challenge,
        text="indexes",
        order=2,
    )

    attempt = submit_challenge(
        user=user,
        challenge_id=challenge.id,
        payload={
            "text_answer": "I would add caching and indexes on hot paths.",
        },
    )
    assert attempt.status == ChallengeAttempt.Status.COMPLETED
    grading = attempt.submission.metadata.get("grading") or {}
    assert grading.get("method") in {
        "keyword_rubric",
        "keyword_reference_overlap",
    }
    assert "score" in grading


@pytest.mark.django_db
def test_submit_challenge_api_returns_completed() -> None:
    user = User.objects.create_user(email="chalapi@example.com", password="x")
    api = APIClient()
    api.force_authenticate(user=user)
    challenge = Challenge.objects.create(
        title="API theory",
        slug="api-theory-grade",
        modality=Challenge.Modality.THEORY,
        difficulty=1,
    )
    ChallengeModelAnswer.objects.create(
        challenge=challenge,
        reference_text="rate limiting",
    )
    ChallengeRubricItem.objects.create(
        challenge=challenge,
        text="rate limiting",
        order=1,
    )

    res = api.post(
        f"/api/v1/challenges/{challenge.id}/submit/",
        {"text_answer": "Use rate limiting at the gateway."},
        format="json",
    )
    assert res.status_code in {200, 201}
    data = res.json().get("data") or res.json()
    assert data["status"] == "COMPLETED"
    assert data["submission"]["metadata"]["grading"]["score"] is not None

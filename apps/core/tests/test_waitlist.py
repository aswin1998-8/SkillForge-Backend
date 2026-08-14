"""Public waitlist join endpoint."""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.core.models import WaitlistSignup
from apps.core.views import WaitlistJoinView, WaitlistRateThrottle


@pytest.fixture
def api() -> APIClient:
    return APIClient()


@pytest.mark.django_db
def test_waitlist_join_unauthenticated_creates_row(api: APIClient) -> None:
    response = api.post(
        "/api/v1/waitlist/join/",
        {
            "email": "dev@example.com",
            "role_or_stack": "React/Next.js",
            "interest_note": "I rubber-stamp Copilot diffs.",
            "utm_source": "twitter",
            "utm_medium": "social",
            "utm_campaign": "beta",
        },
        format="json",
    )
    assert response.status_code == 201
    assert response.json()["message"] == "You're on the list."
    assert WaitlistSignup.objects.filter(email="dev@example.com").count() == 1
    row = WaitlistSignup.objects.get()
    assert row.utm_source == "twitter"
    assert row.invited is False


@pytest.mark.django_db
def test_waitlist_join_invalid_email_returns_400(api: APIClient) -> None:
    response = api.post(
        "/api/v1/waitlist/join/",
        {"email": "not-an-email"},
        format="json",
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "email" in body["error"]["details"]
    assert WaitlistSignup.objects.count() == 0


@pytest.mark.django_db
def test_waitlist_allows_duplicate_email(api: APIClient) -> None:
    payload = {"email": "repeat@example.com", "role_or_stack": "Both"}
    first = api.post("/api/v1/waitlist/join/", payload, format="json")
    second = api.post("/api/v1/waitlist/join/", payload, format="json")
    assert first.status_code == 201
    assert second.status_code == 201
    assert WaitlistSignup.objects.filter(email="repeat@example.com").count() == 2


def test_waitlist_view_uses_waitlist_throttle_scope() -> None:
    assert WaitlistJoinView.throttle_classes == [WaitlistRateThrottle]
    assert WaitlistRateThrottle.scope == "waitlist"

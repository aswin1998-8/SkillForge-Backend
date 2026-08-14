"""Auth signup, verification, and Google coverage."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core import mail
from django.utils import timezone
from rest_framework.test import APIClient

from apps.users.models import EmailVerificationToken, Profile, User
from conftest import make_invite


@pytest.fixture
def api() -> APIClient:
    return APIClient()


def _register_payload(**overrides):
    email = overrides.get("email", "new@skillforge.test")
    data = {
        "email": email,
        "password": "SecurePass123!",
        "first_name": "Ada",
        "last_name": "Lovelace",
    }
    data.update(overrides)
    if not data.get("invite_token"):
        data["invite_token"] = make_invite(str(data["email"]))
    return data


@pytest.mark.django_db
def test_register_happy_path(api: APIClient) -> None:
    response = api.post("/api/v1/auth/register/", _register_payload(), format="json")
    assert response.status_code == 201
    assert "sf_access" in response.cookies
    assert "sf_refresh" in response.cookies
    data = response.data["data"]
    assert data["email"] == "new@skillforge.test"
    assert data["email_verified"] is False
    assert data["first_name"] == "Ada"
    assert data["last_name"] == "Lovelace"
    user = User.objects.get(email="new@skillforge.test")
    assert Profile.objects.filter(user=user).exists()
    assert EmailVerificationToken.objects.filter(user=user, used_at__isnull=True).exists()
    assert len(mail.outbox) == 1
    assert "verify-email?token=" in mail.outbox[0].body


@pytest.mark.django_db
def test_register_duplicate_email(api: APIClient) -> None:
    User.objects.create_user(email="new@skillforge.test", password="SecurePass123!")
    response = api.post("/api/v1/auth/register/", _register_payload(), format="json")
    assert response.status_code == 400
    assert response.data["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.django_db
def test_register_weak_password(api: APIClient) -> None:
    response = api.post(
        "/api/v1/auth/register/",
        _register_payload(password="password"),
        format="json",
    )
    assert response.status_code == 400
    details = response.data["error"]["details"]
    assert "password" in details


@pytest.mark.django_db
def test_register_short_password(api: APIClient) -> None:
    response = api.post(
        "/api/v1/auth/register/",
        _register_payload(password="Ab1!"),
        format="json",
    )
    assert response.status_code == 400
    assert "password" in response.data["error"]["details"]


@pytest.mark.django_db
def test_register_missing_names(api: APIClient) -> None:
    response = api.post(
        "/api/v1/auth/register/",
        _register_payload(first_name="", last_name=""),
        format="json",
    )
    assert response.status_code == 400
    details = response.data["error"]["details"]
    assert "first_name" in details
    assert "last_name" in details


@pytest.mark.django_db
def test_verify_email_valid_token(api: APIClient) -> None:
    register = api.post("/api/v1/auth/register/", _register_payload(), format="json")
    assert register.status_code == 201
    token = EmailVerificationToken.objects.get(user__email="new@skillforge.test").token
    response = api.post("/api/v1/auth/verify-email/", {"token": token}, format="json")
    assert response.status_code == 200
    assert response.data["data"]["email_verified"] is True
    user = User.objects.get(email="new@skillforge.test")
    assert user.email_verified is True


@pytest.mark.django_db
def test_verify_email_invalid_token(api: APIClient) -> None:
    response = api.post(
        "/api/v1/auth/verify-email/",
        {"token": "not-a-real-token"},
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_verify_email_expired_token(api: APIClient) -> None:
    user = User.objects.create_user(email="exp@skillforge.test", password="SecurePass123!")
    token = EmailVerificationToken.objects.create(
        user=user,
        token="expired-token-value",
        expires_at=timezone.now() - timedelta(hours=1),
    )
    response = api.post(
        "/api/v1/auth/verify-email/",
        {"token": token.token},
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_resend_verification_requires_auth(api: APIClient) -> None:
    response = api.post("/api/v1/auth/resend-verification/", format="json")
    assert response.status_code == 401


@pytest.mark.django_db
def test_resend_verification_authenticated(api: APIClient) -> None:
    register = api.post("/api/v1/auth/register/", _register_payload(), format="json")
    assert register.status_code == 201
    mail.outbox.clear()
    response = api.post("/api/v1/auth/resend-verification/", format="json")
    assert response.status_code == 200
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_google_auth_new_user_requires_invite(api: APIClient, settings) -> None:
    settings.GOOGLE_CLIENT_ID = "test-google-client"
    payload = {
        "email": "noinvite@skillforge.test",
        "email_verified": True,
        "sub": "google-sub-new-no-invite",
        "given_name": "No",
        "family_name": "Invite",
    }
    with patch(
        "apps.users.services.id_token.verify_oauth2_token",
        return_value=payload,
    ):
        response = api.post(
            "/api/v1/auth/google/",
            {"credential": "fake-jwt"},
            format="json",
        )
    assert response.status_code == 400
    assert not User.objects.filter(email="noinvite@skillforge.test").exists()


@pytest.mark.django_db
def test_register_requires_invite_token(api: APIClient) -> None:
    response = api.post(
        "/api/v1/auth/register/",
        {
            "email": "new@skillforge.test",
            "password": "SecurePass123!",
            "first_name": "Ada",
            "last_name": "Lovelace",
        },
        format="json",
    )
    assert response.status_code == 400
    assert "invite_token" in response.data["error"]["details"]


@pytest.mark.django_db
def test_google_auth_new_user(api: APIClient, settings) -> None:
    settings.GOOGLE_CLIENT_ID = "test-google-client"
    payload = {
        "email": "google@skillforge.test",
        "email_verified": True,
        "sub": "google-sub-1",
        "given_name": "Grace",
        "family_name": "Hopper",
    }
    with patch(
        "apps.users.services.id_token.verify_oauth2_token",
        return_value=payload,
    ):
        response = api.post(
            "/api/v1/auth/google/",
            {
                "credential": "fake-jwt",
                "invite_token": make_invite("google@skillforge.test"),
            },
            format="json",
        )
    assert response.data["data"]["email_verified"] is True
    assert "sf_access" in response.cookies
    user = User.objects.get(email="google@skillforge.test")
    assert user.google_sub == "google-sub-1"
    assert Profile.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_google_auth_links_existing_user(api: APIClient, settings) -> None:
    settings.GOOGLE_CLIENT_ID = "test-google-client"
    existing = User.objects.create_user(
        email="link@skillforge.test",
        password="SecurePass123!",
        email_verified=False,
    )
    payload = {
        "email": "link@skillforge.test",
        "email_verified": True,
        "sub": "google-sub-2",
        "given_name": "Link",
        "family_name": "User",
    }
    with patch(
        "apps.users.services.id_token.verify_oauth2_token",
        return_value=payload,
    ):
        response = api.post(
            "/api/v1/auth/google/",
            {"credential": "fake-jwt"},
            format="json",
        )
    assert response.status_code == 200
    existing.refresh_from_db()
    assert existing.google_sub == "google-sub-2"
    assert existing.email_verified is True


@pytest.mark.django_db
def test_google_rejects_unverified_email(api: APIClient, settings) -> None:
    settings.GOOGLE_CLIENT_ID = "test-google-client"
    payload = {
        "email": "bad@skillforge.test",
        "email_verified": False,
        "sub": "google-sub-3",
    }
    with patch(
        "apps.users.services.id_token.verify_oauth2_token",
        return_value=payload,
    ):
        response = api.post(
            "/api/v1/auth/google/",
            {"credential": "fake-jwt"},
            format="json",
        )
    assert response.status_code == 400

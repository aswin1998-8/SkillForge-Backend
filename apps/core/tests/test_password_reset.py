"""Forgot / reset password coverage."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.core import mail
from django.utils import timezone
from rest_framework.test import APIClient

from apps.users.models import PasswordResetToken, User


@pytest.fixture
def api() -> APIClient:
    return APIClient()


@pytest.mark.django_db
def test_forgot_password_sends_email_for_existing_user(api: APIClient) -> None:
    User.objects.create_user(email="reset@skillforge.test", password="SecurePass123!")
    response = api.post(
        "/api/v1/auth/forgot-password/",
        {"email": "reset@skillforge.test"},
        format="json",
    )
    assert response.status_code == 200
    assert PasswordResetToken.objects.filter(user__email="reset@skillforge.test").exists()
    assert len(mail.outbox) == 1
    assert "reset-password?token=" in mail.outbox[0].body


@pytest.mark.django_db
def test_forgot_password_unknown_email_still_ok(api: APIClient) -> None:
    response = api.post(
        "/api/v1/auth/forgot-password/",
        {"email": "missing@skillforge.test"},
        format="json",
    )
    assert response.status_code == 200
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_reset_password_happy_path(api: APIClient) -> None:
    user = User.objects.create_user(email="reset2@skillforge.test", password="OldPass123!")
    token = PasswordResetToken.objects.create(
        user=user,
        token="valid-reset-token",
        expires_at=timezone.now() + timedelta(hours=1),
    )
    response = api.post(
        "/api/v1/auth/reset-password/",
        {"token": token.token, "password": "NewSecurePass123!"},
        format="json",
    )
    assert response.status_code == 200
    assert "sf_access" in response.cookies
    user.refresh_from_db()
    assert user.check_password("NewSecurePass123!")
    token.refresh_from_db()
    assert token.used_at is not None


@pytest.mark.django_db
def test_reset_password_invalid_token(api: APIClient) -> None:
    response = api.post(
        "/api/v1/auth/reset-password/",
        {"token": "nope", "password": "NewSecurePass123!"},
        format="json",
    )
    assert response.status_code == 400

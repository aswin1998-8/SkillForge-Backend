"""Core API tests."""

from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.roles.models import Role
from apps.users.models import User


@pytest.fixture
def api() -> APIClient:
    return APIClient()


@pytest.fixture
def user(db) -> User:
    return User.objects.create_user(email="tester@skillforge.test", password="testpass123")


@pytest.mark.django_db
def test_health(api: APIClient) -> None:
    response = api.get("/api/v1/health/")
    assert response.status_code == 200
    assert response.data["data"]["status"] == "ok"


@pytest.mark.django_db
def test_register_login_me_logout(api: APIClient) -> None:
    register = api.post(
        "/api/v1/auth/register/",
        {
            "email": "new@skillforge.test",
            "password": "SecurePass123!",
            "first_name": "Ada",
            "last_name": "Lovelace",
        },
        format="json",
    )
    assert register.status_code == 201
    assert "sf_access" in register.cookies
    assert register.data["data"]["email_verified"] is False

    me = api.get("/api/v1/auth/me/")
    assert me.status_code == 200
    assert me.data["data"]["email"] == "new@skillforge.test"

    logout = api.post("/api/v1/auth/logout/")
    assert logout.status_code == 200


@pytest.mark.django_db
def test_profile_requires_auth(api: APIClient) -> None:
    response = api.get("/api/v1/profile/")
    assert response.status_code == 401


@pytest.mark.django_db
def test_onboarding_profile(api: APIClient, user: User) -> None:
    role = Role.objects.create(name="AI Engineer", slug="ai-engineer", description="Build AI systems")
    api.force_authenticate(user=user)
    response = api.patch(
        "/api/v1/profile/",
        {
            "current_role": "Frontend Developer",
            "years_of_experience": 3,
            "technical_goal": "Ship reliable AI agents",
            "target_role_id": role.id,
            "complete_onboarding": True,
        },
        format="json",
    )
    assert response.status_code == 200
    assert response.data["data"]["onboarding_completed"] is True

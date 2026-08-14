"""Staff waitlist invites and user activity console."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core import mail
from django.utils import timezone
from rest_framework.test import APIClient

from apps.challenges.models import Challenge, ChallengeAttempt
from apps.core.models import InviteToken, WaitlistSignup
from apps.diagnostics.models import DiagnosticSession
from apps.gaps.models import UserSkillGap
from apps.roles.models import Skill
from apps.sessions.models import LearningSession
from apps.users.models import Profile, User
from apps.users.services import ensure_user_side_effects
from conftest import make_invite


@pytest.fixture
def api() -> APIClient:
    return APIClient()


@pytest.fixture
def staff_user(db) -> User:
    user = User.objects.create_user(
        email="staff-console@skillforge.test",
        password="testpass123",
        is_staff=True,
    )
    ensure_user_side_effects(user)
    return user


@pytest.fixture
def normal_user(db) -> User:
    user = User.objects.create_user(
        email="member@skillforge.test",
        password="testpass123",
        is_staff=False,
    )
    ensure_user_side_effects(user)
    Profile.objects.filter(user=user).update(
        onboarding_completed=True,
        current_role="Frontend Developer",
    )
    return user


@pytest.mark.django_db
def test_staff_waitlist_requires_staff(api: APIClient, normal_user: User) -> None:
    api.force_authenticate(user=normal_user)
    response = api.get("/api/v1/staff/waitlist/")
    assert response.status_code == 403


@pytest.mark.django_db
def test_staff_waitlist_lists_rows(api: APIClient, staff_user: User, normal_user: User) -> None:
    WaitlistSignup.objects.create(
        email="member@skillforge.test",
        role_or_stack="React",
        interest_note="Ship better diffs",
    )
    WaitlistSignup.objects.create(email="fresh@skillforge.test", role_or_stack="Django")
    api.force_authenticate(user=staff_user)
    response = api.get("/api/v1/staff/waitlist/")
    assert response.status_code == 200
    results = response.data["data"]["results"]
    emails = {row["email"] for row in results}
    assert "member@skillforge.test" in emails
    assert "fresh@skillforge.test" in emails
    member = next(row for row in results if row["email"] == "member@skillforge.test")
    assert member["has_account"] is True
    fresh = next(row for row in results if row["email"] == "fresh@skillforge.test")
    assert fresh["has_account"] is False
    assert fresh["invite_status"] == "none"


@pytest.mark.django_db
def test_staff_send_invite_emails_and_resend_invalidates(
    api: APIClient, staff_user: User
) -> None:
    signup = WaitlistSignup.objects.create(email="invitee@skillforge.test")
    api.force_authenticate(user=staff_user)
    first = api.post(f"/api/v1/staff/waitlist/{signup.id}/invite/")
    assert first.status_code == 200
    assert len(mail.outbox) == 1
    assert "signup?invite=" in mail.outbox[0].body
    assert "Honed" in mail.outbox[0].subject
    first_token = InviteToken.objects.get(email="invitee@skillforge.test").token
    signup.refresh_from_db()
    assert signup.invited is True

    second = api.post(f"/api/v1/staff/waitlist/{signup.id}/invite/")
    assert second.status_code == 200
    assert len(mail.outbox) == 2
    assert not InviteToken.objects.filter(token=first_token).exists()
    new_token = InviteToken.objects.get(email="invitee@skillforge.test").token
    assert new_token != first_token

    preview = api.get("/api/v1/auth/invite/", {"token": first_token})
    assert preview.status_code == 400
    preview_ok = api.get("/api/v1/auth/invite/", {"token": new_token})
    assert preview_ok.status_code == 200
    assert preview_ok.data["data"]["email"] == "invitee@skillforge.test"


@pytest.mark.django_db
def test_invite_consumed_once_and_wrong_email_rejected(api: APIClient) -> None:
    token = make_invite("once@skillforge.test")
    first = api.post(
        "/api/v1/auth/register/",
        {
            "email": "once@skillforge.test",
            "password": "SecurePass123!",
            "first_name": "Once",
            "last_name": "User",
            "invite_token": token,
        },
        format="json",
    )
    assert first.status_code == 201
    assert InviteToken.objects.get(token=token).used_at is not None

    other = make_invite("other@skillforge.test")
    mismatch = api.post(
        "/api/v1/auth/register/",
        {
            "email": "mismatch@skillforge.test",
            "password": "SecurePass123!",
            "first_name": "Mis",
            "last_name": "Match",
            "invite_token": other,
        },
        format="json",
    )
    assert mismatch.status_code == 400


@pytest.mark.django_db
def test_expired_invite_rejected(api: APIClient) -> None:
    token = make_invite("old@skillforge.test")
    InviteToken.objects.filter(token=token).update(
        expires_at=timezone.now() - timedelta(days=1)
    )
    response = api.post(
        "/api/v1/auth/register/",
        {
            "email": "old@skillforge.test",
            "password": "SecurePass123!",
            "first_name": "Old",
            "last_name": "Invite",
            "invite_token": token,
        },
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_google_existing_user_no_invite(api: APIClient, settings, normal_user: User) -> None:
    settings.GOOGLE_CLIENT_ID = "test-google-client"
    payload = {
        "email": normal_user.email,
        "email_verified": True,
        "sub": "google-existing-sub",
        "given_name": "Mem",
        "family_name": "Ber",
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
    normal_user.refresh_from_db()
    assert normal_user.google_sub == "google-existing-sub"


@pytest.mark.django_db
def test_staff_users_list_and_detail(api: APIClient, staff_user: User, normal_user: User) -> None:
    skill, _ = Skill.objects.get_or_create(slug="hooks", defaults={"name": "Hooks"})
    DiagnosticSession.objects.create(
        user=normal_user,
        goal=DiagnosticSession.Goal.SHARPEN_CURRENT,
        current_role="FE",
        target_role="FE",
        status=DiagnosticSession.Status.COMPLETED,
    )
    challenge = Challenge.objects.create(
        title="Staff view challenge",
        slug="staff-view-challenge",
        modality=Challenge.Modality.THEORY,
        difficulty=1,
        is_active=True,
    )
    ChallengeAttempt.objects.create(
        user=normal_user,
        challenge=challenge,
        status=ChallengeAttempt.Status.COMPLETED,
    )
    LearningSession.objects.create(
        user=normal_user,
        session_type=LearningSession.SessionType.CHALLENGE,
        reference_id=1,
        title="Practice session",
        summary="Did the work",
    )
    UserSkillGap.objects.create(
        user=normal_user,
        skill=skill,
        status=UserSkillGap.Status.NOT_STARTED,
    )

    api.force_authenticate(user=staff_user)
    listing = api.get("/api/v1/staff/users/", {"q": "member@"})
    assert listing.status_code == 200
    results = listing.data["data"]["results"]
    assert len(results) == 1
    row = results[0]
    assert row["email"] == "member@skillforge.test"
    assert row["diagnostics_completed"] == 1
    assert row["challenges_completed"] == 1
    assert row["open_gaps"] == 1
    assert row["onboarding_completed"] is True

    detail = api.get(f"/api/v1/staff/users/{normal_user.id}/")
    assert detail.status_code == 200
    body = detail.data["data"]
    assert body["user"]["email"] == "member@skillforge.test"
    assert len(body["diagnostics"]) == 1
    assert body["challenge_attempts"][0]["challenge_title"] == "Staff view challenge"
    assert body["sessions"][0]["title"] == "Practice session"
    assert body["gaps"][0]["skill_slug"] == "hooks"


@pytest.mark.django_db
def test_staff_users_forbidden_for_non_staff(api: APIClient, normal_user: User) -> None:
    api.force_authenticate(user=normal_user)
    assert api.get("/api/v1/staff/users/").status_code == 403
    assert api.get(f"/api/v1/staff/users/{normal_user.id}/").status_code == 403

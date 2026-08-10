"""Skill gap analysis + staff nuclear progress reset."""

from __future__ import annotations

import pytest
from django.test import override_settings
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIClient

from apps.challenges.models import Challenge, ChallengeAttempt, DailyChallenge
from apps.diagnostics.models import DiagnosticRoadmapItem, DiagnosticSession
from apps.gaps.models import UserSkillGap
from apps.gaps.services import build_gap_analysis
from apps.roles.models import Skill
from apps.sessions.models import LearningSession
from apps.users.models import Profile, User
from apps.users.services import ensure_user_side_effects, reset_user_progress


@pytest.fixture
def api() -> APIClient:
    return APIClient()


@pytest.fixture
def staff_user(db) -> User:
    user = User.objects.create_user(
        email="staff-reset@skillforge.test",
        password="testpass123",
        is_staff=True,
    )
    ensure_user_side_effects(user)
    Profile.objects.filter(user=user).update(
        onboarding_completed=True,
        current_role="Frontend Developer",
        technical_goal="Sharpen React",
        known_skills=["react"],
        diagnostic_cycle=2,
        diagnostic_difficulty_bump=1,
    )
    return user


@pytest.fixture
def normal_user(db) -> User:
    user = User.objects.create_user(
        email="normal@skillforge.test",
        password="testpass123",
        is_staff=False,
    )
    ensure_user_side_effects(user)
    Profile.objects.filter(user=user).update(onboarding_completed=True)
    return user


def _seed_progress(user: User) -> None:
    skill, _ = Skill.objects.get_or_create(slug="hooks", defaults={"name": "Hooks"})
    challenge = Challenge.objects.create(
        title="Hooks reset test",
        slug=f"hooks-reset-{user.id}",
        modality=Challenge.Modality.THEORY,
        difficulty=1,
        is_active=True,
    )
    session = DiagnosticSession.objects.create(
        user=user,
        goal=DiagnosticSession.Goal.SHARPEN_CURRENT,
        current_role="FE",
        target_role="FE",
        status=DiagnosticSession.Status.COMPLETED,
        synthesis={
            "gaps": [
                {
                    "skill_area": "hooks",
                    "severity": "high",
                    "fragment": "Hooks timing needs practice.",
                    "block": "A",
                }
            ]
        },
    )
    DiagnosticRoadmapItem.objects.create(
        session=session,
        user=user,
        challenge_modality="THEORY",
        topic="hooks",
        priority=1,
        challenge=challenge,
        status="in_progress",
    )
    UserSkillGap.objects.create(
        user=user,
        skill=skill,
        status=UserSkillGap.Status.NOT_STARTED,
    )
    ChallengeAttempt.objects.create(
        user=user,
        challenge=challenge,
        status=ChallengeAttempt.Status.IN_PROGRESS,
    )
    DailyChallenge.objects.create(
        user=user,
        challenge=challenge,
        date=timezone.localdate(),
    )
    LearningSession.objects.create(
        user=user,
        session_type="DIAGNOSTIC",
        reference_id=session.id,
        title="Diagnostic",
        summary="test",
    )


@pytest.mark.django_db
def test_gap_analysis_payload(staff_user: User) -> None:
    _seed_progress(staff_user)
    from apps.diagnostics.models import MarketEvidence

    MarketEvidence.objects.create(
        competency_area="hooks",
        stat_text="Hooks remain a core React interview topic.",
        source_name="Sample survey",
        source_date="2025",
        is_active=True,
    )
    data = build_gap_analysis(staff_user)
    assert data["summary"]["open_count"] >= 1
    assert data["summary"]["by_severity"]["high"] >= 1
    assert "avg_proficiency" in data["summary"]
    assert "active_focus" in data["summary"]
    assert data["open_gaps"]
    gap = data["open_gaps"][0]
    assert gap["severity"] == "high"
    assert "Hooks" in (gap.get("fragment") or "")
    assert gap.get("challenge_id") is not None
    assert "progress_percent" in gap
    assert "radar" in data
    assert isinstance(data["radar"]["axes"], list)
    assert len(data["radar"]["axes"]) <= 6
    assert len(data["radar"]["axes"]) >= 1
    assert data["radar"]["axes"][0]["target"] == 1.0
    assert "market_trends" in data
    assert isinstance(data["market_trends"], list)
    assert any("Hooks" in t["label"] or "hooks" in t["label"].lower() for t in data["market_trends"])


@pytest.mark.django_db
def test_gap_analysis_endpoint(api: APIClient, staff_user: User) -> None:
    _seed_progress(staff_user)
    api.force_authenticate(user=staff_user)
    res = api.get("/api/v1/gaps/analysis/")
    assert res.status_code == 200
    payload = res.data["data"]
    assert "summary" in payload
    assert "open_gaps" in payload


@pytest.mark.django_db
@override_settings(DEBUG=False, ALLOW_STAFF_PROGRESS_RESET=True)
def test_non_staff_cannot_reset(api: APIClient, normal_user: User) -> None:
    api.force_authenticate(user=normal_user)
    res = api.post("/api/v1/admin/reset-progress/", {"confirm": "RESET"}, format="json")
    assert res.status_code == 403


@pytest.mark.django_db
@override_settings(DEBUG=False, ALLOW_STAFF_PROGRESS_RESET=True)
def test_staff_wrong_confirm(api: APIClient, staff_user: User) -> None:
    api.force_authenticate(user=staff_user)
    res = api.post("/api/v1/admin/reset-progress/", {"confirm": "yes"}, format="json")
    assert res.status_code == 400


@pytest.mark.django_db
@override_settings(DEBUG=False, ALLOW_STAFF_PROGRESS_RESET=True)
def test_staff_reset_wipes_progress(api: APIClient, staff_user: User) -> None:
    _seed_progress(staff_user)
    api.force_authenticate(user=staff_user)
    res = api.post("/api/v1/admin/reset-progress/", {"confirm": "RESET"}, format="json")
    assert res.status_code == 200

    staff_user.profile.refresh_from_db()
    assert staff_user.profile.onboarding_completed is False
    assert staff_user.profile.diagnostic_cycle == 1
    assert staff_user.profile.diagnostic_difficulty_bump == 0
    assert staff_user.profile.technical_goal == ""
    assert staff_user.profile.known_skills == []
    assert DiagnosticSession.objects.filter(user=staff_user).count() == 0
    assert DiagnosticRoadmapItem.objects.filter(user=staff_user).count() == 0
    assert UserSkillGap.objects.filter(user=staff_user).count() == 0
    assert ChallengeAttempt.objects.filter(user=staff_user).count() == 0
    assert DailyChallenge.objects.filter(user=staff_user).count() == 0
    assert LearningSession.objects.filter(user=staff_user).count() == 0
    assert User.objects.filter(pk=staff_user.pk).exists()


@pytest.mark.django_db
@override_settings(DEBUG=False, ALLOW_STAFF_PROGRESS_RESET=False)
def test_reset_disabled_without_flag(staff_user: User) -> None:
    with pytest.raises(PermissionDenied):
        reset_user_progress(user=staff_user, confirm="RESET")

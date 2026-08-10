"""Diagnostic, challenge, and roadmap flow tests."""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.challenges.models import Challenge, ChallengeSkill, DailyChallenge
from apps.diagnostics.topic_defaults import ensure_default_topics
from apps.gaps.models import UserSkillGap
from apps.roles.models import Role, RoleSkill, Skill
from apps.users.models import Profile, User


@pytest.fixture
def api() -> APIClient:
    return APIClient()


@pytest.fixture
def seeded(db):
    ensure_default_topics()
    from django.core.management import call_command

    call_command("import_questions", file="content/sample_questions.json")

    role = Role.objects.create(name="Frontend Developer", slug="frontend-developer", description="FE")
    skill = Skill.objects.create(name="React", slug="react", description="React")
    RoleSkill.objects.create(role=role, skill=skill, importance=5)
    challenge = Challenge.objects.create(
        title="React Theory",
        slug="react-theory",
        description="Explain reconciliation",
        modality=Challenge.Modality.THEORY,
        difficulty=1,
        estimated_duration_minutes=20,
        scenario="Team asks about keys",
        requirements=["Explain reconciliation"],
        constraints=["Under 500 words"],
        workspace_config={"editor": "markdown"},
        is_active=True,
    )
    ChallengeSkill.objects.create(challenge=challenge, skill=skill)
    from apps.users.services import ensure_user_side_effects

    user = User.objects.create_user(email="flow@skillforge.test", password="testpass123")
    ensure_user_side_effects(user)
    Profile.objects.filter(user=user).update(
        current_role="Frontend Developer",
        technical_goal="Sharpen React",
        target_role=role,
        onboarding_completed=True,
    )
    return {
        "user": user,
        "role": role,
        "skill": skill,
        "challenge": challenge,
    }


@pytest.mark.django_db
def test_diagnostic_session_start(api: APIClient, seeded) -> None:
    user = seeded["user"]
    api.force_authenticate(user=user)
    start = api.post(
        "/api/v1/diagnostic-sessions/",
        {"goal": "sharpen_current", "framework_slugs": ["react"]},
        format="json",
    )
    assert start.status_code == 201, start.data
    assert start.data["data"]["status"] == "AWAITING_ANSWERS"
    assert len(start.data["data"]["current_questions"]) > 0


@pytest.mark.django_db
def test_current_challenge_assignment_stable(api: APIClient, seeded) -> None:
    user = seeded["user"]
    api.force_authenticate(user=user)
    first = api.get("/api/v1/challenges/today/")
    second = api.get("/api/v1/challenges/today/")
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.data["data"]["id"] == second.data["data"]["id"]
    assert DailyChallenge.objects.filter(user=user).count() == 1


@pytest.mark.django_db
def test_sequential_unlock_locks_other_challenges(api: APIClient, seeded) -> None:
    user = seeded["user"]
    from apps.diagnostics.models import DiagnosticRoadmapItem, DiagnosticSession

    session = DiagnosticSession.objects.create(
        user=user,
        goal="sharpen_current",
        current_role="Frontend Developer",
        target_role="Frontend Developer",
        status=DiagnosticSession.Status.COMPLETED,
    )
    primary = seeded["challenge"]
    other = Challenge.objects.create(
        title="Other Challenge",
        slug="other-challenge",
        modality=Challenge.Modality.THEORY,
        difficulty=1,
        is_active=True,
    )
    DiagnosticRoadmapItem.objects.create(
        session=session,
        user=user,
        challenge_modality="THEORY",
        topic="hooks",
        priority=1,
        challenge=primary,
        status="in_progress",
    )
    DiagnosticRoadmapItem.objects.create(
        session=session,
        user=user,
        challenge_modality="THEORY",
        topic="state",
        priority=2,
        challenge=other,
        status="not_started",
    )
    api.force_authenticate(user=user)
    locked = api.get(f"/api/v1/challenges/{other.id}/")
    assert locked.status_code == 200
    assert locked.data["data"]["is_locked"] is True
    open_one = api.get(f"/api/v1/challenges/{primary.id}/")
    assert open_one.status_code == 200
    assert open_one.data["data"]["is_locked"] is False


@pytest.mark.django_db
def test_challenge_submit_completes(api: APIClient, seeded) -> None:
    user = seeded["user"]
    api.force_authenticate(user=user)
    today = api.get("/api/v1/challenges/today/")
    challenge_id = today.data["data"]["challenge"]["id"]
    submit = api.post(
        f"/api/v1/challenges/{challenge_id}/submit/",
        {"text_answer": "Keys help React track list identity across renders."},
        format="json",
    )
    assert submit.status_code in {200, 201}
    assert submit.data["data"]["status"] == "SUBMITTED"
    attempt_id = submit.data["data"]["id"]
    checklist = api.get(f"/api/v1/attempts/{attempt_id}/debrief/")
    assert checklist.status_code == 200
    items = checklist.data["data"]["rubric_items"]
    body = {str(i["id"]): True for i in items}
    checked = api.post(
        f"/api/v1/attempts/{attempt_id}/debrief/checklist/",
        {"checklist": body},
        format="json",
    )
    assert checked.status_code == 200
    done = api.post(
        f"/api/v1/attempts/{attempt_id}/debrief/complete/",
        {"follow_up_answers": {}},
        format="json",
    )
    assert done.status_code == 200
    assert done.data["data"]["status"] == "COMPLETED"


@pytest.mark.django_db
def test_roadmap_from_gaps(api: APIClient, seeded) -> None:
    user = seeded["user"]
    UserSkillGap.objects.create(user=user, skill=seeded["skill"], status=UserSkillGap.Status.NOT_STARTED)
    api.force_authenticate(user=user)
    response = api.get("/api/v1/roadmap/")
    assert response.status_code == 200
    assert response.data["data"] is not None

"""Re-diagnostic cycle, difficulty bump, gap close, and dashboard flags."""

from __future__ import annotations

import pytest
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from apps.challenges.models import (
    Challenge,
    ChallengeAttempt,
    ChallengeDebrief,
    ChallengeSkill,
    DailyChallenge,
)
from apps.challenges.services import complete_debrief, submit_challenge
from apps.diagnostics.adaptive_selector import experience_difficulty_band
from apps.diagnostics.models import DiagnosticRoadmapItem, DiagnosticSession
from apps.diagnostics.session_service import start_session
from apps.diagnostics.synthesis_engine import create_roadmap_items_from_entries
from apps.diagnostics.topic_defaults import ensure_default_topics
from apps.gaps.models import UserSkillGap
from apps.progress.services.dashboard import build_dashboard
from apps.roles.models import Skill
from apps.users.models import Profile, User
from apps.users.services import ensure_user_side_effects


@pytest.fixture
def api() -> APIClient:
    return APIClient()


@pytest.fixture
def cycle_user(db):
    ensure_default_topics()
    user = User.objects.create_user(email="rediag@skillforge.test", password="testpass123")
    ensure_user_side_effects(user)
    Profile.objects.filter(user=user).update(
        current_role="Frontend Developer",
        years_of_experience=3,
        technical_goal="Sharpen React",
        onboarding_completed=True,
        diagnostic_cycle=1,
        diagnostic_difficulty_bump=0,
    )
    skill, _ = Skill.objects.get_or_create(slug="hooks", defaults={"name": "Hooks"})
    react, _ = Skill.objects.get_or_create(slug="react", defaults={"name": "React"})
    challenge = Challenge.objects.create(
        title="Hooks Practice",
        slug="hooks-practice-rediag",
        modality=Challenge.Modality.THEORY,
        difficulty=2,
        is_active=True,
        workspace_config={"competency_areas": ["hooks"]},
    )
    ChallengeSkill.objects.create(challenge=challenge, skill=react)
    return {"user": user, "skill": skill, "challenge": challenge}


def _seed_completed_roadmap(*, user: User, challenge: Challenge, topic: str = "hooks"):
    session = DiagnosticSession.objects.create(
        user=user,
        goal=DiagnosticSession.Goal.SHARPEN_CURRENT,
        current_role="Frontend Developer",
        target_role="Frontend Developer",
        status=DiagnosticSession.Status.COMPLETED,
        synthesis={
            "gaps": [
                {
                    "skill_area": topic,
                    "severity": "high",
                    "fragment": "Hooks timing needs practice.",
                    "block": "A",
                }
            ],
            "strengths": [],
            "roadmap": [],
        },
    )
    item = DiagnosticRoadmapItem.objects.create(
        session=session,
        user=user,
        challenge_modality="THEORY",
        topic=topic,
        priority=1,
        challenge=challenge,
        status="in_progress",
    )
    UserSkillGap.objects.get_or_create(
        user=user,
        skill=Skill.objects.get(slug=topic),
        defaults={"status": UserSkillGap.Status.NOT_STARTED},
    )
    return session, item


@pytest.mark.django_db
def test_last_debrief_increments_bump_and_unlocks_rediagnostic(cycle_user) -> None:
    user = cycle_user["user"]
    challenge = cycle_user["challenge"]
    _seed_completed_roadmap(user=user, challenge=challenge)

    attempt = ChallengeAttempt.objects.create(
        user=user,
        challenge=challenge,
        status=ChallengeAttempt.Status.SUBMITTED,
    )
    ChallengeDebrief.objects.create(attempt=attempt, checklist={})

    complete_debrief(user=user, attempt_id=attempt.id, follow_up_answers={})

    user.profile.refresh_from_db()
    assert user.profile.diagnostic_difficulty_bump == 1
    assert user.profile.diagnostic_cycle == 2
    assert (
        UserSkillGap.objects.get(user=user, skill__slug="hooks").status
        == UserSkillGap.Status.CLOSED
    )

    dash = build_dashboard(user)
    assert dash["roadmap_complete"] is True
    assert dash["rediagnostic_unlocked"] is True
    assert dash["diagnostic_difficulty_bump"] == 1
    assert dash["today_challenge"] is None
    open_slugs = [g["skill"]["slug"] for g in dash["open_gaps"]]
    assert "hooks" not in open_slugs
    assert any(g["skill"]["slug"] == "hooks" for g in dash["recently_closed_gaps"])


@pytest.mark.django_db
def test_submit_marks_gap_in_progress(cycle_user) -> None:
    user = cycle_user["user"]
    challenge = cycle_user["challenge"]
    _seed_completed_roadmap(user=user, challenge=challenge)

    submit_challenge(
        user=user,
        challenge_id=challenge.id,
        payload={"text_answer": "Effects run after paint."},
    )
    gap = UserSkillGap.objects.get(user=user, skill__slug="hooks")
    assert gap.status == UserSkillGap.Status.IN_PROGRESS


@pytest.mark.django_db
def test_start_session_copies_difficulty_bump(api: APIClient, cycle_user) -> None:
    user = cycle_user["user"]
    call_command("import_questions", file="content/sample_questions.json")
    # years<=2 band is (1,2,1); bump+1 keeps start_tier in sample catalog (tiers 1–2).
    Profile.objects.filter(user=user).update(
        diagnostic_difficulty_bump=1,
        years_of_experience=1,
    )
    user.profile.refresh_from_db()

    session = start_session(
        user=user,
        goal=DiagnosticSession.Goal.SHARPEN_CURRENT,
        framework_slugs=["react"],
    )
    assert session.difficulty_bump == 1
    assert session.questions.exists()

    years = user.profile.years_of_experience
    min_tier, max_tier, start_tier = experience_difficulty_band(years)
    bump = session.difficulty_bump
    assert min(5, min_tier + bump) == 2
    assert min(5, max_tier + bump) == 3
    assert min(5, start_tier + bump) == 2


@pytest.mark.django_db
def test_create_roadmap_replaces_prior_user_items(cycle_user) -> None:
    user = cycle_user["user"]
    challenge = cycle_user["challenge"]
    old_session, old_item = _seed_completed_roadmap(user=user, challenge=challenge)
    today = timezone.localdate()
    DailyChallenge.objects.create(
        user=user,
        challenge=challenge,
        date=today,
        status=DailyChallenge.Status.AVAILABLE,
    )

    new_session = DiagnosticSession.objects.create(
        user=user,
        goal=DiagnosticSession.Goal.SHARPEN_CURRENT,
        current_role="Frontend Developer",
        target_role="Frontend Developer",
        status=DiagnosticSession.Status.AWAITING_ANSWERS,
        difficulty_bump=1,
    )
    created = create_roadmap_items_from_entries(
        session=new_session,
        roadmap=[
            {
                "topic": "hooks",
                "challenge_modality": "THEORY",
                "priority": 1,
                "initial_status": "not_started",
            }
        ],
    )
    assert created
    assert not DiagnosticRoadmapItem.objects.filter(pk=old_item.pk).exists()
    assert DiagnosticRoadmapItem.objects.filter(user=user).count() == len(created)
    assert DailyChallenge.objects.filter(user=user, date=today).count() == 0
    assert DiagnosticSession.objects.filter(pk=old_session.pk).exists()


@pytest.mark.django_db
def test_dashboard_enriches_open_gaps(cycle_user) -> None:
    user = cycle_user["user"]
    challenge = cycle_user["challenge"]
    _seed_completed_roadmap(user=user, challenge=challenge)
    dash = build_dashboard(user)
    assert dash["roadmap_complete"] is False
    assert dash["rediagnostic_unlocked"] is False
    assert dash["open_gaps"]
    gap = dash["open_gaps"][0]
    assert gap["severity"] == "high"
    assert "Hooks" in (gap.get("fragment") or "")
    assert gap.get("challenge_id") == challenge.id

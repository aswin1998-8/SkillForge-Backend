"""Tests for FE/BE challenge matching and AI orphan cleanup."""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.challenges.models import Challenge, ChallengeSkill
from apps.challenges.seed_challenges import deactivate_orphan_challenges
from apps.diagnostics.models import DiagnosticRoadmapItem, DiagnosticSession, FrameworkTopic
from apps.diagnostics.roadmap_rebuild import wipe_and_rebuild_user_roadmap
from apps.diagnostics.synthesis_engine import _find_challenge_for_topic
from apps.diagnostics.topic_defaults import ensure_default_topics
from apps.roles.models import Skill
from apps.users.models import User


@pytest.fixture
def user(db) -> User:
    return User.objects.create_user(email="roadmap-fix@test.com", password="testpass123")


@pytest.mark.django_db
def test_deactivate_orphan_ai_challenges(db) -> None:
    Skill.objects.get_or_create(slug="rag", defaults={"name": "RAG"})
    Challenge.objects.create(
        title="Explain RAG Chunking Trade-offs",
        slug="explain-rag-chunking-tradeoffs",
        modality=Challenge.Modality.THEORY,
        difficulty=1,
        is_active=True,
    )
    deactivated = deactivate_orphan_challenges()
    assert deactivated >= 1
    assert (
        Challenge.objects.get(slug="explain-rag-chunking-tradeoffs").is_active is False
    )


@pytest.mark.django_db
def test_matcher_never_returns_rag_for_react_session(user: User) -> None:
    ensure_default_topics()
    react_skill, _ = Skill.objects.get_or_create(slug="react", defaults={"name": "React"})
    Skill.objects.get_or_create(slug="rag", defaults={"name": "RAG"})

    Challenge.objects.create(
        title="Explain RAG Chunking Trade-offs",
        slug="explain-rag-chunking-tradeoffs",
        modality=Challenge.Modality.THEORY,
        difficulty=1,
        is_active=True,
    )
    fe = Challenge.objects.create(
        title="Explain React Reconciliation",
        slug="explain-react-reconciliation-test",
        modality=Challenge.Modality.THEORY,
        difficulty=1,
        is_active=True,
        workspace_config={"competency_areas": ["hooks", "rendering"]},
    )
    ChallengeSkill.objects.create(challenge=fe, skill=react_skill)

    react_fw = FrameworkTopic.objects.get(framework_name="react")
    session = DiagnosticSession.objects.create(
        user=user,
        goal=DiagnosticSession.Goal.SHARPEN_CURRENT,
        current_role="Frontend Developer",
        target_role="Frontend Developer",
        status=DiagnosticSession.Status.COMPLETED,
    )
    session.selected_frameworks.add(react_fw)

    matched = _find_challenge_for_topic(
        topic="hooks",
        modality=DiagnosticRoadmapItem.Modality.THEORY,
        session=session,
    )
    assert matched is not None
    assert matched.id == fe.id
    assert "RAG" not in matched.title


@pytest.mark.django_db
def test_build_roadmap_uses_latest_session_only(user: User) -> None:
    ensure_default_topics()
    from django.utils import timezone
    from datetime import timedelta

    react_skill, _ = Skill.objects.get_or_create(slug="react", defaults={"name": "React"})
    challenge = Challenge.objects.create(
        title="Lift State Without Prop Drilling Pain",
        slug="lift-state-test",
        modality=Challenge.Modality.THEORY,
        difficulty=1,
        is_active=True,
        workspace_config={"competency_areas": ["state_management"]},
    )
    ChallengeSkill.objects.create(challenge=challenge, skill=react_skill)
    react_fw = FrameworkTopic.objects.get(framework_name="react")

    old = DiagnosticSession.objects.create(
        user=user,
        goal=DiagnosticSession.Goal.SWITCH_ROLE,
        status=DiagnosticSession.Status.COMPLETED,
        completed_at=timezone.now() - timedelta(days=2),
        synthesis={"roadmap": [], "gaps": []},
    )
    old.selected_frameworks.add(react_fw)
    DiagnosticRoadmapItem.objects.create(
        session=old,
        user=user,
        challenge_modality="THEORY",
        topic="Apply current strengths to a small target-role scenario",
        priority=1,
        challenge=None,
        status="not_started",
    )

    latest = DiagnosticSession.objects.create(
        user=user,
        goal=DiagnosticSession.Goal.SHARPEN_CURRENT,
        status=DiagnosticSession.Status.COMPLETED,
        completed_at=timezone.now(),
        synthesis={
            "roadmap": [
                {
                    "challenge_modality": "THEORY",
                    "topic": "state_management",
                    "priority": 1,
                }
            ],
            "gaps": [{"skill_area": "state_management", "severity": "medium"}],
        },
    )
    latest.selected_frameworks.add(react_fw)
    DiagnosticRoadmapItem.objects.create(
        session=latest,
        user=user,
        challenge_modality="THEORY",
        topic="state_management",
        priority=1,
        challenge=challenge,
        status="in_progress",
    )

    api = APIClient()
    api.force_authenticate(user=user)
    response = api.get("/api/v1/roadmap/")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["source"] == "diagnostic_synthesis"
    assert len(data["steps"]) == 1
    assert data["steps"][0]["topic"] == "state_management"
    assert data["steps"][0]["challenge"]["title"] == challenge.title


@pytest.mark.django_db
def test_wipe_and_rebuild_replaces_mock_topics(user: User) -> None:
    ensure_default_topics()
    from django.utils import timezone

    react_skill, _ = Skill.objects.get_or_create(slug="react", defaults={"name": "React"})
    challenge = Challenge.objects.create(
        title="Diagnose Unnecessary Re-renders",
        slug="diagnose-rerenders-test",
        modality=Challenge.Modality.DIAGNOSE,
        difficulty=2,
        is_active=True,
        workspace_config={"competency_areas": ["rendering", "performance"]},
    )
    ChallengeSkill.objects.create(challenge=challenge, skill=react_skill)
    react_fw = FrameworkTopic.objects.get(framework_name="react")

    session = DiagnosticSession.objects.create(
        user=user,
        goal=DiagnosticSession.Goal.SHARPEN_CURRENT,
        status=DiagnosticSession.Status.COMPLETED,
        completed_at=timezone.now(),
        synthesis={
            "roadmap": [
                {
                    "challenge_modality": "DIAGNOSE",
                    "topic": "Debug a realistic failure mode",
                    "priority": 1,
                },
                {
                    "challenge_modality": "DIAGNOSE",
                    "topic": "rendering",
                    "priority": 2,
                },
            ],
            "gaps": [{"skill_area": "rendering", "severity": "high"}],
        },
    )
    session.selected_frameworks.add(react_fw)
    DiagnosticRoadmapItem.objects.create(
        session=session,
        user=user,
        challenge_modality="DIAGNOSE",
        topic="Debug a realistic failure mode",
        priority=1,
        status="not_started",
    )

    result = wipe_and_rebuild_user_roadmap(user=user)
    assert result["rebuilt"] >= 5  # full React competency path
    topics = list(
        DiagnosticRoadmapItem.objects.filter(user=user).values_list("topic", flat=True)
    )
    assert "Debug a realistic failure mode" not in topics
    assert "rendering" in topics
    assert "hooks" in topics
    assert "state_management" in topics
    item = DiagnosticRoadmapItem.objects.get(user=user, topic="rendering")
    assert item.challenge_id is not None

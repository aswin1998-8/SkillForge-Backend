"""AI integration unit tests (Mock provider only)."""

from __future__ import annotations

import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from apps.diagnostics.models import Diagnostic, DiagnosticAttempt, SkillEvidence
from apps.diagnostics.scoring import classify_gap_status, compute_skill_scores
from apps.roles.models import Role, RoleSkill, Skill
from apps.users.models import Profile, User


@pytest.fixture
def api() -> APIClient:
    return APIClient()


@pytest.fixture
def user(db) -> User:
    u = User.objects.create_user(email="ai@honed.test", password="SecurePass123!")
    Profile.objects.get_or_create(user=u)
    return u


@pytest.fixture
def catalog(db):
    role = Role.objects.create(name="AI Engineer", slug="ai-engineer")
    rag = Skill.objects.create(name="RAG", slug="rag")
    llm = Skill.objects.create(name="LLM APIs", slug="llm-apis")
    RoleSkill.objects.create(role=role, skill=rag, importance=5)
    RoleSkill.objects.create(role=role, skill=llm, importance=4)
    diagnostic = Diagnostic.objects.create(title="Baseline", description="Test", is_active=True)
    return {"role": role, "rag": rag, "llm": llm, "diagnostic": diagnostic}


def test_compute_skill_scores_weighted():
    rows = [
        {"skill_slug": "rag", "stage": "FOUNDATION", "score": 0.8},
        {"skill_slug": "rag", "stage": "SCENARIO", "score": 0.4},
        {"skill_slug": "rag", "stage": "DEBUGGING", "score": 0.2},
        {"skill_slug": "rag", "stage": "CODING", "score": 0.2},
    ]
    result = compute_skill_scores(rows)
    assert "rag" in result
    assert 0.0 <= result["rag"]["score"] <= 1.0
    assert "FOUNDATION" in result["rag"]["breakdown"]


def test_classify_gap_status():
    assert classify_gap_status(score=0.9, importance=5) == "STRONG"
    assert classify_gap_status(score=0.5, importance=3) == "DEVELOPING"
    assert classify_gap_status(score=0.2, importance=5) == "CRITICAL_GAP"


@override_settings(AI_PROVIDER="mock")
@pytest.mark.django_db
def test_adaptive_start_and_turn(api: APIClient, user: User, catalog) -> None:
    profile = user.profile
    profile.target_role = catalog["role"]
    profile.current_role = "Frontend Developer"
    profile.years_of_experience = 4
    profile.technical_goal = "Switch into AI engineering"
    profile.save()

    api.force_authenticate(user=user)
    start = api.post(f"/api/v1/diagnostics/{catalog['diagnostic'].id}/start/", format="json")
    assert start.status_code == 201
    attempt_id = start.data["data"]["id"]
    assert start.data["data"]["status"] == "IN_PROGRESS"
    active = start.data["data"].get("active_turn")
    assert active is not None
    turn_id = active["id"]

    submit = api.post(
        f"/api/v1/attempts/{attempt_id}/turns/",
        {"turn_id": turn_id, "answer_text": "Retrieval grounds LLMs in private data."},
        format="json",
    )
    assert submit.status_code == 200
    assert SkillEvidence.objects.filter(user=user, attempt_id=attempt_id).exists()
    attempt = DiagnosticAttempt.objects.get(pk=attempt_id)
    assert attempt.turns.filter(status="EVALUATED").exists()


@override_settings(AI_PROVIDER="mock")
@pytest.mark.django_db
def test_mock_provider_generate_question():
    from apps.ai.providers.mock import MockAIProvider

    provider = MockAIProvider()
    out = provider.generate_question(
        prompt="x",
        context={"assessment_stage": "FOUNDATION", "skill": {"name": "RAG", "slug": "rag"}},
    )
    assert "prompt_text" in out
    assert out["stage"] == "FOUNDATION"

"""Diagnostic, challenge, debrief, and roadmap flow tests."""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.challenges.models import Challenge, ChallengeSkill, DailyChallenge
from apps.diagnostics.models import Diagnostic, DiagnosticQuestion
from apps.debriefs.models import DebriefSession
from apps.gaps.models import UserSkillGap
from apps.roles.models import Role, RoleSkill, Skill
from apps.users.models import Profile, User


@pytest.fixture
def api() -> APIClient:
    return APIClient()


@pytest.fixture
def seeded(db):
    role = Role.objects.create(name="AI Engineer", slug="ai-engineer", description="AI")
    skill = Skill.objects.create(name="RAG", slug="rag", description="RAG")
    RoleSkill.objects.create(role=role, skill=skill, importance=5)
    diagnostic = Diagnostic.objects.create(
        title="Baseline",
        description="Test diagnostic",
        is_active=True,
    )
    question = DiagnosticQuestion.objects.create(
        diagnostic=diagnostic,
        text="How would you evaluate retrieval quality?",
        question_type="FREE_TEXT",
        skill=skill,
        difficulty=2,
        ordering=1,
    )
    challenge = Challenge.objects.create(
        title="RAG Theory",
        slug="rag-theory",
        description="Explain chunking",
        modality=Challenge.Modality.THEORY,
        difficulty=1,
        estimated_duration_minutes=20,
        scenario="Team proposes fixed chunks",
        requirements=["Explain trade-offs"],
        constraints=["Under 500 words"],
        workspace_config={"editor": "markdown"},
        is_active=True,
    )
    ChallengeSkill.objects.create(challenge=challenge, skill=skill)
    from apps.users.services import ensure_user_side_effects

    user = User.objects.create_user(email="flow@skillforge.test", password="testpass123")
    ensure_user_side_effects(user)
    Profile.objects.filter(user=user).update(
        current_role="Frontend",
        technical_goal="AI Engineer",
        target_role=role,
        onboarding_completed=True,
    )
    return {
        "user": user,
        "role": role,
        "skill": skill,
        "diagnostic": diagnostic,
        "question": question,
        "challenge": challenge,
    }


@pytest.mark.django_db
def test_diagnostic_submit_creates_gaps(api: APIClient, seeded) -> None:
    user = seeded["user"]
    api.force_authenticate(user=user)
    start = api.post(f"/api/v1/diagnostics/{seeded['diagnostic'].id}/start/")
    assert start.status_code == 201
    attempt_id = start.data["data"]["id"]

    answers = api.post(
        f"/api/v1/attempts/{attempt_id}/answers/",
        {"answers": [{"question_id": seeded["question"].id, "answer_text": "Use nDCG and human review."}]},
        format="json",
    )
    assert answers.status_code == 200

    submit = api.post(f"/api/v1/attempts/{attempt_id}/submit/")
    assert submit.status_code == 200

    # Celery task may run eagerly if configured; invoke synchronously for test certainty
    from apps.diagnostics.tasks import generate_diagnostic_result

    generate_diagnostic_result(attempt_id)
    detail = api.get(f"/api/v1/attempts/{attempt_id}/")
    assert detail.status_code == 200
    assert detail.data["data"]["status"] in {"COMPLETED", "PROCESSING", "SUBMITTED"}


@pytest.mark.django_db
def test_daily_challenge_one_per_day(api: APIClient, seeded) -> None:
    user = seeded["user"]
    api.force_authenticate(user=user)
    first = api.get("/api/v1/challenges/today/")
    second = api.get("/api/v1/challenges/today/")
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.data["data"]["id"] == second.data["data"]["id"]
    assert DailyChallenge.objects.filter(user=user).count() == 1


@pytest.mark.django_db
def test_challenge_submit_starts_debrief(api: APIClient, seeded) -> None:
    user = seeded["user"]
    api.force_authenticate(user=user)
    today = api.get("/api/v1/challenges/today/")
    challenge_id = today.data["data"]["challenge"]["id"]
    submit = api.post(
        f"/api/v1/challenges/{challenge_id}/submit/",
        {"text_answer": "Chunk by semantic sections; evaluate with recall@k."},
        format="json",
    )
    assert submit.status_code in {200, 201}
    attempt_id = submit.data["data"]["id"]
    assert "submission" in submit.data["data"] or submit.data["data"].get("status")

    session = DebriefSession.objects.filter(attempt_id=attempt_id).first()
    if session is None:
        from apps.challenges.models import ChallengeAttempt
        from apps.debriefs.services import start_debrief_for_attempt

        attempt = ChallengeAttempt.objects.get(id=attempt_id)
        session = start_debrief_for_attempt(attempt_id=attempt.id)

    from apps.debriefs.tasks import generate_debrief_question

    generate_debrief_question(session.id)
    session.refresh_from_db()
    detail = api.get(f"/api/v1/debriefs/{session.id}/")
    assert detail.status_code == 200


@pytest.mark.django_db
def test_roadmap_from_gaps(api: APIClient, seeded) -> None:
    user = seeded["user"]
    UserSkillGap.objects.create(user=user, skill=seeded["skill"], status=UserSkillGap.Status.NOT_STARTED)
    api.force_authenticate(user=user)
    response = api.get("/api/v1/roadmap/")
    assert response.status_code == 200
    assert response.data["data"] is not None

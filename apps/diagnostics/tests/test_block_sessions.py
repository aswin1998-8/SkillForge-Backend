"""Tests for Block A/B diagnostic sessions + domain-grounded sharpen."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.diagnostics.block_assessment import (
    allocate_competencies_to_stages,
    build_assessment_competencies,
    compute_block_b_gaps,
    start_session,
    submit_stage_answers,
)
from apps.diagnostics.models import (
    DiagnosticSession,
    DomainTaxonomy,
    RoleTaxonomy,
    SessionAnswer,
    SessionQuestion,
)

User = get_user_model()


@pytest.fixture
def api(settings):
    settings.AI_PROVIDER = "mock"
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True
    settings.ALLOWED_HOSTS = ["*", "testserver", "localhost"]
    return APIClient()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        email="blockab@example.com",
        password="TestPass123!",
        first_name="Block",
        last_name="Tester",
    )


def _seed_domains():
    """Override default catalog competencies for deterministic round-robin tests."""
    d1, _ = DomainTaxonomy.objects.update_or_create(
        slug="system-design",
        defaults={
            "domain_name": "System Design & Architecture",
            "competency_areas": ["a1", "a2", "a3", "a4", "a5", "a6"],
        },
    )
    d2, _ = DomainTaxonomy.objects.update_or_create(
        slug="reliability",
        defaults={
            "domain_name": "Reliability & Performance",
            "competency_areas": ["b1", "b2", "b3", "b4", "b5", "b6"],
        },
    )
    return d1, d2


def _drive_session_to_completion(user, session: DiagnosticSession, *, b_answers=None):
    guards = 0
    while session.status != DiagnosticSession.Status.COMPLETED and guards < 40:
        guards += 1
        session.refresh_from_db()
        if session.status == DiagnosticSession.Status.FAILED:
            raise AssertionError(session.error)
        if session.status == DiagnosticSession.Status.AWAITING_ANSWERS:
            qs = list(
                SessionQuestion.objects.filter(
                    session=session,
                    block=session.current_block,
                    stage=session.current_stage,
                    status="ASKED",
                )
            )
            answers = []
            for q in qs:
                text = f"ans {q.order}"
                if session.current_block == "B" and b_answers is not None:
                    text = b_answers.get(q.competency_area, "no exposure")
                answers.append({"question_id": q.id, "answer_text": text})
            submit_stage_answers(user=user, session_id=session.id, answers=answers)
        session.refresh_from_db()
    return session


@pytest.mark.django_db
def test_sharpen_requires_domains(api, user, settings):
    settings.AI_PROVIDER = "mock"
    settings.CELERY_TASK_ALWAYS_EAGER = True
    with pytest.raises(ValidationError) as exc:
        start_session(user=user, goal="sharpen_current", domain_slugs=[])
    assert "domain" in str(exc.value.detail).lower()


@pytest.mark.django_db
def test_sharpen_unknown_domain_fails(api, user, settings):
    settings.AI_PROVIDER = "mock"
    with pytest.raises(ValidationError) as exc:
        start_session(
            user=user,
            goal="sharpen_current",
            domain_slugs=["no-such-domain"],
        )
    assert "Unknown technical domain" in str(exc.value.detail)


@pytest.mark.django_db
def test_sharpen_auto_bootstraps_default_domains(api, user, settings):
    """Known FE slugs resolve without manual admin seeding."""
    settings.AI_PROVIDER = "mock"
    settings.CELERY_TASK_ALWAYS_EAGER = True
    DomainTaxonomy.objects.filter(
        slug__in=["system-design", "reliability"]
    ).delete()
    session = start_session(
        user=user,
        goal="sharpen_current",
        domain_slugs=["system-design", "reliability"],
    )
    session.refresh_from_db()
    assert DomainTaxonomy.objects.filter(slug="system-design").exists()
    assert DomainTaxonomy.objects.filter(slug="reliability").exists()
    assert len(session.assessment_competencies) >= 2


@pytest.mark.django_db
def test_round_robin_cap():
    d1, d2 = _seed_domains()
    plan = build_assessment_competencies([d1, d2], cap=8)
    assert len(plan) == 8
    # Round-robin: a1,b1,a2,b2,...
    assert [p["competency_area"] for p in plan] == [
        "a1",
        "b1",
        "a2",
        "b2",
        "a3",
        "b3",
        "a4",
        "b4",
    ]
    assert plan[0]["domain_slug"] == "system-design"
    assert plan[1]["domain_slug"] == "reliability"


@pytest.mark.django_db
def test_sharpen_skips_block_b_and_tags_competencies(api, user, settings):
    settings.AI_PROVIDER = "mock"
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.DIAGNOSTIC_MAX_COMPETENCY_AREAS = 8
    _seed_domains()

    session = start_session(
        user=user,
        goal="sharpen_current",
        domain_slugs=["system-design", "reliability"],
    )
    session.refresh_from_db()
    assert session.target_taxonomy_id is None
    assert len(session.assessment_competencies) == 8
    assert session.selected_domains.count() == 2

    session = _drive_session_to_completion(user, session)

    assert session.synthesis.get("transferable_skills") == []
    assert not SessionQuestion.objects.filter(session=session, block="B").exists()
    a_qs = SessionQuestion.objects.filter(session=session, block="A")
    assert a_qs.count() == 8
    assert all(q.competency_area for q in a_qs)
    assert all((q.metadata or {}).get("domain_slug") for q in a_qs)


@pytest.mark.django_db
def test_allocate_stages_sums_to_n():
    plan = [{"domain_slug": "x", "competency_area": f"c{i}"} for i in range(8)]
    allocation = allocate_competencies_to_stages(plan)
    total = sum(len(v) for v in allocation.values())
    assert total == 8


@pytest.mark.django_db
def test_switch_auto_creates_taxonomy_for_unknown_role(api, user, settings):
    settings.AI_PROVIDER = "mock"
    settings.CELERY_TASK_ALWAYS_EAGER = True
    from apps.users.models import Profile

    profile, _ = Profile.objects.get_or_create(user=user)
    profile.target_role_label = "Unknown Role XYZ"
    profile.target_learn_skills = ["Rust"]
    profile.save()

    assert not RoleTaxonomy.objects.filter(role_name__iexact="Unknown Role XYZ").exists()
    session = start_session(user=user, goal="switch_role")
    session.refresh_from_db()
    assert session.target_taxonomy_id is not None
    tax = session.target_taxonomy
    assert tax is not None
    assert len(tax.clean_competency_areas()) >= 3


@pytest.mark.django_db
def test_switch_block_b_one_question_per_competency(api, user, settings):
    settings.AI_PROVIDER = "mock"
    settings.CELERY_TASK_ALWAYS_EAGER = True
    from apps.users.models import Profile

    RoleTaxonomy.objects.create(
        role_name="Full stack developer",
        competency_areas=["vector_math", "api_design", "deployments"],
    )
    profile, _ = Profile.objects.get_or_create(user=user)
    profile.target_role_label = "full stack developer"
    profile.known_skills = ["React"]
    profile.target_learn_skills = ["Node.js"]
    profile.save()

    session = start_session(user=user, goal="switch_role")
    session.refresh_from_db()

    saw_b = False
    guards = 0
    while session.status != DiagnosticSession.Status.COMPLETED and guards < 40:
        guards += 1
        session.refresh_from_db()
        if session.status == DiagnosticSession.Status.FAILED:
            raise AssertionError(session.error)
        if session.status == DiagnosticSession.Status.AWAITING_ANSWERS:
            if session.current_block == "B":
                saw_b = True
                b_qs = list(
                    SessionQuestion.objects.filter(
                        session=session, block="B", status="ASKED"
                    ).order_by("order")
                )
                assert len(b_qs) == 3
            qs = list(
                SessionQuestion.objects.filter(
                    session=session,
                    block=session.current_block,
                    stage=session.current_stage,
                    status="ASKED",
                )
            )
            submit_stage_answers(
                user=user,
                session_id=session.id,
                answers=[
                    {"question_id": q.id, "answer_text": f"ans {q.order}"}
                    for q in qs
                ],
            )
        session.refresh_from_db()

    assert saw_b
    assert SessionQuestion.objects.filter(session=session, block="B").count() == 3


@pytest.mark.django_db
def test_deterministic_block_b_gap_formula(db, user, settings):
    settings.AI_PROVIDER = "mock"
    taxonomy = RoleTaxonomy.objects.create(
        role_name="ML Engineer",
        competency_areas=["vector_math", "model_eval", "feature_stores"],
    )
    session = DiagnosticSession.objects.create(
        user=user,
        goal=DiagnosticSession.Goal.SWITCH_ROLE,
        target_role=taxonomy.role_name,
        target_taxonomy=taxonomy,
        status=DiagnosticSession.Status.COMPLETED,
        current_block=DiagnosticSession.Block.B,
        current_stage=DiagnosticSession.Stage.FOUNDATIONAL,
        synthesis={
            "transferable_skills": [
                {
                    "from_current_role": "Stats basics",
                    "applies_to_target": "model_eval",
                }
            ],
            "gaps": [],
        },
    )
    q1 = SessionQuestion.objects.create(
        session=session,
        block="B",
        stage="FOUNDATIONAL",
        order=1,
        competency_area="vector_math",
        question_text="q1",
    )
    q2 = SessionQuestion.objects.create(
        session=session,
        block="B",
        stage="FOUNDATIONAL",
        order=2,
        competency_area="model_eval",
        question_text="q2",
    )
    q3 = SessionQuestion.objects.create(
        session=session,
        block="B",
        stage="FOUNDATIONAL",
        order=3,
        competency_area="feature_stores",
        question_text="q3",
    )
    SessionAnswer.objects.create(question=q1, answer_text="no", exposure_confirmed=False)
    SessionAnswer.objects.create(question=q2, answer_text="no", exposure_confirmed=False)
    SessionAnswer.objects.create(
        question=q3, answer_text="yes I used them", exposure_confirmed=True
    )

    gaps = compute_block_b_gaps(session)
    areas = {g["skill_area"] for g in gaps}
    assert areas == {"vector_math"}


@pytest.mark.django_db
def test_one_active_session(api, user, settings):
    settings.AI_PROVIDER = "mock"
    settings.CELERY_TASK_ALWAYS_EAGER = True
    _seed_domains()
    api.force_authenticate(user=user)
    r1 = api.post(
        "/api/v1/diagnostic-sessions/",
        {"goal": "sharpen_current", "domain_slugs": ["system-design"]},
        format="json",
    )
    assert r1.status_code == 201
    r2 = api.post(
        "/api/v1/diagnostic-sessions/",
        {"goal": "sharpen_current", "domain_slugs": ["system-design"]},
        format="json",
    )
    assert r2.status_code == 409

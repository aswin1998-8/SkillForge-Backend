"""Challenge submit auto-grade smoke tests."""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.challenges.models import (
    Challenge,
    ChallengeAttempt,
    ChallengeModelAnswer,
    ChallengeRubricItem,
)
from apps.challenges.services import submit_challenge
from apps.users.models import User


@pytest.mark.django_db
def test_submit_challenge_keyword_grades_and_completes() -> None:
    user = User.objects.create_user(email="chal@example.com", password="x")
    challenge = Challenge.objects.create(
        title="Theory sample",
        slug="theory-sample-grade",
        modality=Challenge.Modality.THEORY,
        difficulty=1,
        description="Explain caching",
        scenario="API latency",
    )
    ChallengeModelAnswer.objects.create(
        challenge=challenge,
        reference_text="Use Redis caching and indexes.",
    )
    ChallengeRubricItem.objects.create(
        challenge=challenge,
        text="caching",
        order=1,
    )
    ChallengeRubricItem.objects.create(
        challenge=challenge,
        text="indexes",
        order=2,
    )

    attempt = submit_challenge(
        user=user,
        challenge_id=challenge.id,
        payload={
            "text_answer": "I would add caching and indexes on hot paths.",
        },
    )
    assert attempt.status == ChallengeAttempt.Status.COMPLETED
    grading = attempt.submission.metadata.get("grading") or {}
    assert grading.get("method") in {
        "keyword_rubric",
        "keyword_reference_overlap",
    }
    assert "score" in grading


@pytest.mark.django_db
def test_submit_research_challenge_grades_research_data() -> None:
    user = User.objects.create_user(email="research@example.com", password="x")
    challenge = Challenge.objects.create(
        title="Research SSR Caching Trade-offs",
        slug="research-ssr-caching-grade",
        modality=Challenge.Modality.RESEARCH,
        difficulty=2,
        description="Choose cache strategy",
        scenario="Personalized Next.js pages",
    )
    ChallengeModelAnswer.objects.create(
        challenge=challenge,
        reference_text="Compare full-route cache vs dynamic rendering.",
    )
    ChallengeRubricItem.objects.create(
        challenge=challenge,
        text="Compares at least two caching approaches with trade-offs",
        order=1,
    )
    ChallengeRubricItem.objects.create(
        challenge=challenge,
        text="Includes a credible source or docs reference",
        order=2,
    )

    attempt = submit_challenge(
        user=user,
        challenge_id=challenge.id,
        payload={
            "text_answer": "",
            "code": "",
            "research_data": {
                "findings": (
                    "Strategy 1 — Dynamic rendering with no shared cache. "
                    "Strategy 2 — Cache shared public data only. "
                    "Main trade-off is TTFB vs isolation."
                ),
                "synthesis": "Keep personalization dynamic; cache only shared data.",
                "source": "Next.js — Static and Dynamic Rendering",
            },
        },
    )
    grading = attempt.submission.metadata.get("grading") or {}
    assert grading.get("method") == "keyword_rubric"
    assert grading.get("score") == pytest.approx(1.0)
    assert grading.get("is_correct") is True
    assert all(p["matched"] for p in grading.get("points") or [])


@pytest.mark.django_db
def test_submit_theory_challenge_grades_substantive_answer() -> None:
    user = User.objects.create_user(email="theory@example.com", password="x")
    challenge = Challenge.objects.create(
        title="Explain React Reconciliation",
        slug="explain-react-reconciliation-grade",
        modality=Challenge.Modality.THEORY,
        difficulty=1,
    )
    ChallengeModelAnswer.objects.create(
        challenge=challenge,
        reference_text=(
            "React reconciles trees by comparing element types and keys. Stable keys "
            "let React match previous instances so state is preserved."
        ),
    )
    ChallengeRubricItem.objects.create(
        challenge=challenge,
        text="Explains tree diff / reconciliation at a high level",
        strength_fragment="Clear reconciliation mental model",
        order=1,
    )
    ChallengeRubricItem.objects.create(
        challenge=challenge,
        text="Explains why unstable keys cause remounts/bugs",
        strength_fragment="Understands key stability impact",
        order=2,
    )

    attempt = submit_challenge(
        user=user,
        challenge_id=challenge.id,
        payload={
            "text_answer": (
                "React reconciles by comparing element types and keys between renders. "
                "Unstable keys remount components and drop local state when reordering."
            ),
        },
    )
    grading = attempt.submission.metadata.get("grading") or {}
    assert grading.get("is_correct") is True
    assert float(grading.get("score") or 0) >= 0.5


@pytest.mark.django_db
def test_failed_submit_can_be_retried() -> None:
    user = User.objects.create_user(email="retry@example.com", password="x")
    challenge = Challenge.objects.create(
        title="Defend Client Split",
        slug="defend-client-split-retry",
        modality=Challenge.Modality.DEFEND,
        difficulty=2,
    )
    ChallengeModelAnswer.objects.create(
        challenge=challenge,
        reference_text=(
            "Keep the page as a Server Component and push use client to the smallest "
            "interactive leaves so the JS bundle stays small."
        ),
    )
    ChallengeRubricItem.objects.create(
        challenge=challenge,
        text="Argues for leaf-level client boundaries",
        strength_fragment="Sound RSC boundary thinking",
        order=1,
    )
    ChallengeRubricItem.objects.create(
        challenge=challenge,
        text="Mentions JS bundle or server-capability cost",
        strength_fragment="Performance-aware composition",
        order=2,
    )

    first = submit_challenge(
        user=user,
        challenge_id=challenge.id,
        payload={"text_answer": "idk"},
    )
    assert first.status == ChallengeAttempt.Status.SUBMITTED
    assert (first.submission.metadata.get("grading") or {}).get("is_correct") is False

    second = submit_challenge(
        user=user,
        challenge_id=challenge.id,
        payload={
            "text_answer": (
                "Keep the page as a Server Component and put use client only on the "
                "interactive leaf widget so we do not inflate the client JS bundle."
            ),
        },
    )
    assert second.id == first.id
    assert second.status == ChallengeAttempt.Status.COMPLETED
    assert (second.submission.metadata.get("grading") or {}).get("is_correct") is True


@pytest.mark.django_db
def test_legacy_failed_completed_attempt_can_be_retried() -> None:
    """Old bug marked failed grades as COMPLETED — those must still be retryable."""
    user = User.objects.create_user(email="legacyretry@example.com", password="x")
    challenge = Challenge.objects.create(
        title="Defend legacy",
        slug="defend-legacy-retry",
        modality=Challenge.Modality.DEFEND,
        difficulty=2,
    )
    ChallengeModelAnswer.objects.create(
        challenge=challenge,
        reference_text=(
            "Keep the page as a Server Component and push use client to the smallest "
            "interactive leaves so the JS bundle stays small."
        ),
    )
    ChallengeRubricItem.objects.create(
        challenge=challenge,
        text="Argues for leaf-level client boundaries",
        order=1,
    )
    ChallengeRubricItem.objects.create(
        challenge=challenge,
        text="Mentions JS bundle or server-capability cost",
        order=2,
    )
    attempt = ChallengeAttempt.objects.create(
        user=user,
        challenge=challenge,
        status=ChallengeAttempt.Status.COMPLETED,
    )
    from apps.challenges.models import Submission

    Submission.objects.create(
        attempt=attempt,
        text_answer="idk",
        metadata={"grading": {"is_correct": False, "score": 0.0, "method": "keyword_rubric"}},
    )

    retried = submit_challenge(
        user=user,
        challenge_id=challenge.id,
        payload={
            "text_answer": (
                "Keep the page as a Server Component and put use client only on the "
                "interactive leaf widget so we do not inflate the client JS bundle."
            ),
        },
    )
    assert retried.id == attempt.id
    assert retried.status == ChallengeAttempt.Status.COMPLETED
    assert (retried.submission.metadata.get("grading") or {}).get("is_correct") is True


@pytest.mark.django_db
def test_passed_submit_is_idempotent() -> None:
    user = User.objects.create_user(email="idempotent@example.com", password="x")
    challenge = Challenge.objects.create(
        title="Theory idempotent",
        slug="theory-idempotent",
        modality=Challenge.Modality.THEORY,
        difficulty=1,
    )
    ChallengeModelAnswer.objects.create(
        challenge=challenge,
        reference_text="rate limiting",
    )
    ChallengeRubricItem.objects.create(
        challenge=challenge,
        text="rate limiting",
        order=1,
    )

    first = submit_challenge(
        user=user,
        challenge_id=challenge.id,
        payload={"text_answer": "Use rate limiting at the gateway."},
    )
    assert first.status == ChallengeAttempt.Status.COMPLETED

    second = submit_challenge(
        user=user,
        challenge_id=challenge.id,
        payload={"text_answer": "Use rate limiting at the gateway again."},
    )
    assert second.id == first.id
    assert second.status == ChallengeAttempt.Status.COMPLETED
    # Original passing answer is preserved (no silent overwrite).
    assert second.submission.text_answer == first.submission.text_answer


@pytest.mark.django_db
def test_submit_challenge_api_returns_completed() -> None:
    user = User.objects.create_user(email="chalapi@example.com", password="x")
    api = APIClient()
    api.force_authenticate(user=user)
    challenge = Challenge.objects.create(
        title="API theory",
        slug="api-theory-grade",
        modality=Challenge.Modality.THEORY,
        difficulty=1,
    )
    ChallengeModelAnswer.objects.create(
        challenge=challenge,
        reference_text="rate limiting",
    )
    ChallengeRubricItem.objects.create(
        challenge=challenge,
        text="rate limiting",
        order=1,
    )

    res = api.post(
        f"/api/v1/challenges/{challenge.id}/submit/",
        {"text_answer": "Use rate limiting at the gateway."},
        format="json",
    )
    assert res.status_code in {200, 201}
    data = res.json().get("data") or res.json()
    assert data["status"] == "COMPLETED"
    assert data["submission"]["metadata"]["grading"]["score"] is not None

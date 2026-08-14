"""Learning session score serialization."""

from __future__ import annotations

import pytest

from apps.challenges.models import (
    Challenge,
    ChallengeAttempt,
    ChallengeDebrief,
    Submission,
)
from apps.sessions.models import LearningSession
from apps.sessions.serializers import LearningSessionSerializer
from apps.users.models import User


@pytest.mark.django_db
def test_serializer_includes_challenge_grading_score() -> None:
    user = User.objects.create_user(email="score@example.com", password="x")
    challenge = Challenge.objects.create(
        title="Theory",
        slug="theory-score",
        modality=Challenge.Modality.THEORY,
        difficulty=1,
    )
    attempt = ChallengeAttempt.objects.create(user=user, challenge=challenge)
    Submission.objects.create(
        attempt=attempt,
        metadata={"grading": {"score": 0.72}},
    )
    session = LearningSession.objects.create(
        user=user,
        session_type=LearningSession.SessionType.CHALLENGE,
        reference_id=attempt.id,
        title="Challenge: Theory",
        summary="Graded THEORY: score 72%",
    )
    assert LearningSessionSerializer(session).data["score"] == 72


@pytest.mark.django_db
def test_serializer_includes_debrief_checklist_score() -> None:
    user = User.objects.create_user(email="debrief-score@example.com", password="x")
    challenge = Challenge.objects.create(
        title="Coding",
        slug="coding-debrief-score",
        modality=Challenge.Modality.CODING,
        difficulty=1,
    )
    attempt = ChallengeAttempt.objects.create(user=user, challenge=challenge)
    debrief = ChallengeDebrief.objects.create(attempt=attempt, checklist_score=0.4)
    session = LearningSession.objects.create(
        user=user,
        session_type=LearningSession.SessionType.DEBRIEF,
        reference_id=debrief.id,
        title="Debrief: Coding",
    )
    assert LearningSessionSerializer(session).data["score"] == 40


@pytest.mark.django_db
def test_serializer_leaves_diagnostic_score_null() -> None:
    user = User.objects.create_user(email="diag-score@example.com", password="x")
    session = LearningSession.objects.create(
        user=user,
        session_type=LearningSession.SessionType.DIAGNOSTIC,
        reference_id=1,
        title="Diagnostic: sharpen_current",
    )
    assert LearningSessionSerializer(session).data["score"] is None

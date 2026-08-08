"""Challenge assignment and submission services."""

from __future__ import annotations

from datetime import date

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from apps.challenges.models import (
    Challenge,
    ChallengeAttempt,
    ConfidenceRating,
    DailyChallenge,
    Submission,
)
from apps.gaps.models import UserSkillGap
from apps.users.models import User


def get_challenge_or_404(challenge_id: int) -> Challenge:
    try:
        return Challenge.objects.prefetch_related("challenge_skills__skill").get(
            pk=challenge_id,
            is_active=True,
        )
    except Challenge.DoesNotExist as exc:
        raise NotFound("Challenge not found.") from exc


@transaction.atomic
def get_or_assign_today_challenge(*, user: User, on_date: date | None = None) -> DailyChallenge:
    today = on_date or timezone.localdate()
    existing = (
        DailyChallenge.objects.select_related("challenge")
        .prefetch_related("challenge__challenge_skills__skill")
        .filter(user=user, date=today)
        .first()
    )
    if existing:
        return existing

    open_gap_skill_ids = list(
        UserSkillGap.objects.filter(user=user)
        .exclude(status=UserSkillGap.Status.CLOSED)
        .values_list("skill_id", flat=True)
    )

    completed_challenge_ids = ChallengeAttempt.objects.filter(
        user=user,
        status__in=[ChallengeAttempt.Status.COMPLETED, ChallengeAttempt.Status.SUBMITTED],
    ).values_list("challenge_id", flat=True)

    qs = Challenge.objects.filter(is_active=True).exclude(id__in=completed_challenge_ids)
    if open_gap_skill_ids:
        qs = qs.filter(challenge_skills__skill_id__in=open_gap_skill_ids).annotate(
            gap_match_count=Count(
                "challenge_skills",
                filter=Q(challenge_skills__skill_id__in=open_gap_skill_ids),
            )
        ).order_by("-gap_match_count", "difficulty", "id")
    else:
        qs = qs.order_by("difficulty", "id")

    challenge = qs.distinct().first()
    if challenge is None:
        challenge = Challenge.objects.filter(is_active=True).order_by("difficulty", "id").first()
    if challenge is None:
        raise ValidationError("No active challenges available.")

    return DailyChallenge.objects.create(
        user=user,
        challenge=challenge,
        date=today,
        status=DailyChallenge.Status.AVAILABLE,
    )


@transaction.atomic
def submit_challenge(
    *,
    user: User,
    challenge_id: int,
    payload: dict,
) -> ChallengeAttempt:
    challenge = get_challenge_or_404(challenge_id)
    today = timezone.localdate()
    daily = DailyChallenge.objects.filter(user=user, date=today, challenge=challenge).first()

    attempt = (
        ChallengeAttempt.objects.filter(
            user=user,
            challenge=challenge,
            status=ChallengeAttempt.Status.IN_PROGRESS,
        )
        .order_by("-started_at")
        .first()
    )
    if attempt is None:
        attempt = ChallengeAttempt.objects.create(
            user=user,
            challenge=challenge,
            daily_challenge=daily,
            status=ChallengeAttempt.Status.IN_PROGRESS,
        )

    Submission.objects.update_or_create(
        attempt=attempt,
        defaults={
            "text_answer": payload.get("text_answer") or "",
            "code": payload.get("code") or "",
            "architecture_data": payload.get("architecture_data") or {},
            "research_data": payload.get("research_data") or {},
            "metadata": payload.get("metadata") or {},
        },
    )

    attempt.status = ChallengeAttempt.Status.SUBMITTED
    attempt.completed_at = timezone.now()
    attempt.save(update_fields=["status", "completed_at"])

    if daily:
        daily.status = DailyChallenge.Status.SUBMITTED
        daily.save(update_fields=["status", "updated_at"])

    from apps.sessions.services import record_session

    record_session(
        user=user,
        session_type="CHALLENGE",
        reference_id=attempt.id,
        title=f"Challenge: {challenge.title}",
        summary=f"Submitted {challenge.modality} challenge",
    )

    from apps.debriefs.services import start_debrief_for_attempt

    transaction.on_commit(lambda: start_debrief_for_attempt(attempt_id=attempt.id))
    return attempt


@transaction.atomic
def save_confidence(
    *,
    user: User,
    attempt_id: int,
    score: int,
    note: str = "",
) -> ConfidenceRating:
    if score < 1 or score > 5:
        raise ValidationError({"score": "Score must be between 1 and 5."})
    try:
        attempt = ChallengeAttempt.objects.get(pk=attempt_id, user=user)
    except ChallengeAttempt.DoesNotExist as exc:
        raise NotFound("Challenge attempt not found.") from exc

    rating, _ = ConfidenceRating.objects.update_or_create(
        attempt=attempt,
        defaults={"score": score, "note": note},
    )
    return rating


def get_attempt_for_user(*, user: User, attempt_id: int) -> ChallengeAttempt:
    try:
        return ChallengeAttempt.objects.select_related(
            "challenge",
            "submission",
            "confidence",
            "daily_challenge",
        ).get(pk=attempt_id, user=user)
    except ChallengeAttempt.DoesNotExist as exc:
        raise NotFound("Challenge attempt not found.") from exc

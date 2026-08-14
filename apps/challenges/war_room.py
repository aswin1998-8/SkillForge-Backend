"""Scripted war-room beat progression (no live AI)."""

from __future__ import annotations

from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.challenges.models import (
    Challenge,
    ChallengeAttempt,
    DailyChallenge,
    Submission,
)
from apps.challenges.services import (
    challenge_is_locked,
    get_challenge_or_404,
    get_or_assign_today_challenge,
)


def _beats(challenge) -> list[dict]:
    raw = (challenge.workspace_config or {}).get("beats") or []
    if not isinstance(raw, list):
        return []
    return [b for b in raw if isinstance(b, dict) and b.get("id")]


def public_beats(*, challenge, current_index: int) -> list[dict]:
    out = []
    for idx, beat in enumerate(_beats(challenge)):
        locked = idx > current_index
        item = {
            "id": beat.get("id"),
            "type": beat.get("type") or "prompt",
            "title": beat.get("title") or "",
            "locked": locked,
        }
        if not locked:
            item["content"] = beat.get("content") or ""
            item["prompt"] = beat.get("prompt") or ""
        out.append(item)
    return out


def _ensure_attempt(*, user, challenge):
    locked, _ = challenge_is_locked(user=user, challenge_id=challenge.id)
    if locked:
        raise ValidationError(
            "Complete your current roadmap challenge before unlocking the next one."
        )
    daily = get_or_assign_today_challenge(user=user)
    if daily.challenge_id != challenge.id:
        daily.challenge = challenge
        daily.status = DailyChallenge.Status.IN_PROGRESS
        daily.save(update_fields=["challenge", "status", "updated_at"])

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
    submission, _ = Submission.objects.get_or_create(attempt=attempt)
    return attempt, submission


@transaction.atomic
def advance_war_room_beat(
    *,
    user,
    challenge_id: int,
    beat_id: str,
    text: str,
) -> dict:
    challenge = get_challenge_or_404(challenge_id)
    if challenge.modality != Challenge.Modality.WAR_ROOM:
        raise ValidationError("Beat progression is only for war room challenges.")
    beats = _beats(challenge)
    if not beats:
        raise ValidationError("No war room beats configured.")

    attempt, submission = _ensure_attempt(user=user, challenge=challenge)
    metadata = dict(submission.metadata or {})
    room = dict(metadata.get("war_room") or {})
    answers = dict(room.get("answers") or {})
    current_index = int(room.get("current_index") or 0)
    current_index = max(0, min(current_index, len(beats) - 1))
    current = beats[current_index]
    if str(current.get("id")) != str(beat_id):
        raise ValidationError("That beat is not the current war room step.")
    if not (text or "").strip():
        raise ValidationError({"text": "A response is required."})

    answers[str(beat_id)] = text.strip()
    last_index = len(beats) - 1
    complete = current_index >= last_index
    next_index = current_index if complete else current_index + 1
    room.update(
        {
            "current_index": next_index,
            "current_beat_id": beats[next_index].get("id"),
            "answers": answers,
            "complete": complete,
        }
    )
    metadata["war_room"] = room
    submission.metadata = metadata
    joined = "\n\n".join(answers.get(str(b.get("id")), "") for b in beats)
    submission.text_answer = joined
    submission.save(update_fields=["metadata", "text_answer", "updated_at"])

    return {
        "attempt_id": attempt.id,
        "current_index": next_index,
        "complete": complete,
        "beats": public_beats(challenge=challenge, current_index=next_index),
        "answers": answers,
    }


def war_room_state(*, user, challenge_id: int) -> dict:
    challenge = get_challenge_or_404(challenge_id)
    try:
        attempt = ChallengeAttempt.objects.filter(
            user=user, challenge=challenge
        ).order_by("-started_at").first()
    except ChallengeAttempt.DoesNotExist:
        attempt = None
    current_index = 0
    answers = {}
    complete = False
    attempt_id = None
    if attempt is not None:
        attempt_id = attempt.id
        submission = getattr(attempt, "submission", None)
        if submission is not None:
            room = (submission.metadata or {}).get("war_room") or {}
            current_index = int(room.get("current_index") or 0)
            answers = dict(room.get("answers") or {})
            complete = bool(room.get("complete"))
    return {
        "attempt_id": attempt_id,
        "current_index": current_index,
        "complete": complete,
        "beats": public_beats(challenge=challenge, current_index=current_index),
        "answers": answers,
    }

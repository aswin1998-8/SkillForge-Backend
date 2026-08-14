"""Session history helpers."""

from __future__ import annotations

from rest_framework.exceptions import NotFound

from apps.sessions.models import LearningSession
from apps.users.models import User


def record_session(
    *,
    user: User,
    session_type: str,
    reference_id: int,
    title: str,
    summary: str = "",
) -> LearningSession:
    existing = LearningSession.objects.filter(
        user=user,
        session_type=session_type,
        reference_id=reference_id,
    ).first()
    if existing:
        existing.title = title
        existing.summary = summary
        existing.save(update_fields=["title", "summary"])
        return existing
    return LearningSession.objects.create(
        user=user,
        session_type=session_type,
        reference_id=reference_id,
        title=title,
        summary=summary,
    )


def list_sessions(user: User):
    return LearningSession.objects.filter(user=user)


def get_session_for_user(*, user: User, session_id: int) -> LearningSession:
    try:
        return LearningSession.objects.get(pk=session_id, user=user)
    except LearningSession.DoesNotExist as exc:
        raise NotFound("Session not found.") from exc


def _to_percent(value) -> int | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if 0 <= number <= 1:
        return int(round(number * 100))
    if 0 < number <= 100:
        return int(round(number))
    if number == 0:
        return 0
    return None


def session_scores(sessions) -> dict[int, int | None]:
    """Map learning-session id -> score 0–100 (or omit if unknown)."""
    sessions = list(sessions)
    if not sessions:
        return {}

    challenge_ids: list[int] = []
    debrief_ids: list[int] = []
    for session in sessions:
        if session.session_type == LearningSession.SessionType.CHALLENGE:
            challenge_ids.append(session.reference_id)
        elif session.session_type == LearningSession.SessionType.DEBRIEF:
            debrief_ids.append(session.reference_id)

    challenge_by_id: dict[int, int | None] = {}
    if challenge_ids:
        from apps.challenges.models import ChallengeAttempt

        attempts = ChallengeAttempt.objects.filter(id__in=challenge_ids).select_related(
            "submission",
        )
        for attempt in attempts:
            submission = getattr(attempt, "submission", None)
            metadata = (submission.metadata if submission else None) or {}
            grading = metadata.get("grading") if isinstance(metadata, dict) else None
            raw = grading.get("score") if isinstance(grading, dict) else None
            challenge_by_id[attempt.id] = _to_percent(raw)

    debrief_by_id: dict[int, int | None] = {}
    if debrief_ids:
        from apps.challenges.models import ChallengeDebrief

        debriefs = ChallengeDebrief.objects.filter(id__in=debrief_ids)
        for debrief in debriefs:
            debrief_by_id[debrief.id] = _to_percent(debrief.checklist_score)

    scores: dict[int, int | None] = {}
    for session in sessions:
        if session.session_type == LearningSession.SessionType.CHALLENGE:
            scores[session.id] = challenge_by_id.get(session.reference_id)
        elif session.session_type == LearningSession.SessionType.DEBRIEF:
            scores[session.id] = debrief_by_id.get(session.reference_id)
        else:
            scores[session.id] = None
    return scores

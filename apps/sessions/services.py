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

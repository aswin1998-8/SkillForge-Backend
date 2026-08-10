"""Wipe stale roadmap rows and rebuild from the latest completed diagnostic."""

from __future__ import annotations

import logging

from django.db import transaction

from apps.diagnostics.models import DiagnosticRoadmapItem, DiagnosticSession
from apps.diagnostics.synthesis_engine import (
    build_practice_roadmap,
    create_roadmap_items_from_entries,
    _upsert_gaps_from_synthesis,
)
from apps.users.models import User

logger = logging.getLogger(__name__)


@transaction.atomic
def rebuild_roadmap_items_from_session(session: DiagnosticSession) -> list[DiagnosticRoadmapItem]:
    """
    Replace this session's roadmap with the full stack practice path
    (all selected-framework competencies, ordered by diagnostic need).
    """
    roadmap, gaps, strengths = build_practice_roadmap(session)
    created = create_roadmap_items_from_entries(session=session, roadmap=roadmap)

    if gaps:
        _upsert_gaps_from_synthesis(session, gaps)

    synthesis = dict(session.synthesis or {})
    synthesis["roadmap"] = [
        {
            "challenge_modality": row.challenge_modality,
            "topic": row.topic,
            "priority": row.priority,
        }
        for row in created
    ]
    synthesis["gaps"] = gaps
    synthesis["strengths"] = strengths
    session.synthesis = synthesis
    session.save(update_fields=["synthesis"])

    return created


@transaction.atomic
def wipe_and_rebuild_user_roadmap(*, user: User) -> dict:
    """
    Wipe all DiagnosticRoadmapItem rows for the user, then rebuild from the
    latest completed diagnostic session (if any).
    """
    deleted, _ = DiagnosticRoadmapItem.objects.filter(user=user).delete()
    latest = (
        DiagnosticSession.objects.filter(
            user=user,
            status=DiagnosticSession.Status.COMPLETED,
        )
        .order_by("-completed_at", "-id")
        .first()
    )
    if latest is None:
        return {
            "user_id": user.id,
            "deleted": deleted,
            "rebuilt": 0,
            "session_id": None,
        }

    items = rebuild_roadmap_items_from_session(latest)
    return {
        "user_id": user.id,
        "deleted": deleted,
        "rebuilt": len(items),
        "session_id": latest.id,
    }


def wipe_and_rebuild_all_users() -> list[dict]:
    results = []
    user_ids = (
        DiagnosticSession.objects.filter(status=DiagnosticSession.Status.COMPLETED)
        .values_list("user_id", flat=True)
        .distinct()
    )
    orphan_user_ids = DiagnosticRoadmapItem.objects.values_list(
        "user_id", flat=True
    ).distinct()
    all_ids = set(user_ids) | set(orphan_user_ids)
    for user in User.objects.filter(id__in=all_ids).order_by("id"):
        results.append(wipe_and_rebuild_user_roadmap(user=user))
    return results

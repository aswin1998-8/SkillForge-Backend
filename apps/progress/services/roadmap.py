"""Roadmap derived from the latest diagnostic synthesis items, with gap fallback."""

from __future__ import annotations

from typing import Any

from apps.challenges.models import Challenge
from apps.challenges.serializers import ChallengeSerializer
from apps.diagnostics.models import DiagnosticRoadmapItem, DiagnosticSession
from apps.gaps.serializers import UserSkillGapSerializer
from apps.gaps.services import list_user_gaps
from apps.users.models import User


def build_roadmap(user: User) -> dict[str, Any]:
    latest = (
        DiagnosticSession.objects.filter(
            user=user,
            status=DiagnosticSession.Status.COMPLETED,
        )
        .order_by("-completed_at", "-id")
        .first()
    )

    synthesis_items: list[DiagnosticRoadmapItem] = []
    if latest is not None:
        synthesis_items = list(
            DiagnosticRoadmapItem.objects.filter(user=user, session=latest)
            .select_related("challenge", "session")
            .order_by("priority", "id")
        )
        # Defensive: completed diagnostic but no items — rebuild once.
        if not synthesis_items:
            from apps.diagnostics.roadmap_rebuild import rebuild_roadmap_items_from_session

            rebuild_roadmap_items_from_session(latest)
            synthesis_items = list(
                DiagnosticRoadmapItem.objects.filter(user=user, session=latest)
                .select_related("challenge", "session")
                .order_by("priority", "id")
            )

    if synthesis_items:
        steps = []
        linked = []
        for item in synthesis_items:
            challenge = item.challenge
            if challenge is not None and not challenge.is_active:
                challenge = None
            if challenge is not None:
                linked.append(challenge)
            steps.append(
                {
                    "modality": item.challenge_modality,
                    "topic": item.topic,
                    "priority": item.priority,
                    "status": getattr(item, "status", None) or "not_started",
                    "challenge": ChallengeSerializer(challenge).data
                    if challenge is not None
                    else None,
                    "source": "diagnostic_synthesis",
                    "session_id": item.session_id,
                }
            )
        return {
            "source": "diagnostic_synthesis",
            "steps": steps,
            "suggested_challenges": ChallengeSerializer(linked, many=True).data,
            "focus_skills": [
                g.get("skill_area")
                for g in ((latest.synthesis or {}).get("gaps") or [])
                if isinstance(g, dict) and g.get("skill_area")
            ][:5]
            if latest
            else [],
            "annotations": {},
            "synthesis": latest.synthesis if latest else {},
        }

    gaps = list(list_user_gaps(user, include_closed=False).select_related("skill"))
    skill_ids = [g.skill_id for g in gaps]

    suggested = []
    if skill_ids:
        suggested = list(
            Challenge.objects.filter(
                is_active=True,
                challenge_skills__skill_id__in=skill_ids,
            )
            .prefetch_related("challenge_skills__skill")
            .distinct()
            .order_by("difficulty", "id")[:10]
        )

    ordered = sorted(suggested, key=lambda c: (c.difficulty, c.id))
    annotations: dict[int, str] = {}

    steps = []
    for gap in gaps:
        related = [
            c
            for c in ordered
            if any(cs.skill_id == gap.skill_id for cs in c.challenge_skills.all())
        ]
        steps.append(
            {
                "gap": UserSkillGapSerializer(gap).data,
                "suggested_challenges": ChallengeSerializer(related[:3], many=True).data,
                "status": gap.status,
                "notes": [
                    annotations.get(c.id, "")
                    for c in related[:3]
                    if annotations.get(c.id)
                ],
                "source": "gaps",
            }
        )

    return {
        "source": "gaps",
        "steps": steps,
        "suggested_challenges": ChallengeSerializer(ordered, many=True).data,
        "focus_skills": [g.skill.slug for g in gaps[:5]],
        "annotations": annotations,
        "synthesis": {},
    }

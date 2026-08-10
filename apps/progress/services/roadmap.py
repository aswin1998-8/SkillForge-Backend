"""Roadmap derived from diagnostic synthesis items, with gap/challenge fallback."""

from __future__ import annotations

from typing import Any

from apps.challenges.models import Challenge
from apps.challenges.serializers import ChallengeSerializer
from apps.diagnostics.models import DiagnosticRoadmapItem, DiagnosticSession
from apps.gaps.serializers import UserSkillGapSerializer
from apps.gaps.services import list_user_gaps
from apps.users.models import User


def build_roadmap(user: User) -> dict[str, Any]:
    synthesis_items = list(
        DiagnosticRoadmapItem.objects.filter(user=user)
        .select_related("challenge", "session")
        .order_by("priority", "id")
    )

    if synthesis_items:
        steps = [
            {
                "modality": item.challenge_modality,
                "topic": item.topic,
                "priority": item.priority,
                "challenge": ChallengeSerializer(item.challenge).data
                if item.challenge_id
                else None,
                "source": "diagnostic_synthesis",
                "session_id": item.session_id,
            }
            for item in synthesis_items
        ]
        linked = [i.challenge for i in synthesis_items if i.challenge_id]
        session = (
            DiagnosticSession.objects.filter(
                user=user,
                status=DiagnosticSession.Status.COMPLETED,
            )
            .order_by("-completed_at")
            .first()
        )
        return {
            "source": "diagnostic_synthesis",
            "steps": steps,
            "suggested_challenges": ChallengeSerializer(linked, many=True).data,
            "focus_skills": [
                g.get("skill_area")
                for g in ((session.synthesis or {}).get("gaps") or [])
                if isinstance(g, dict) and g.get("skill_area")
            ][:5]
            if session
            else [],
            "annotations": {},
            "synthesis": session.synthesis if session else {},
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

    ordered = list(suggested)
    annotations: dict[int, str] = {}
    ordered = sorted(suggested, key=lambda c: (c.difficulty, c.id))

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

"""Roadmap derived from open skill gaps and related challenges."""

from __future__ import annotations

from typing import Any

from apps.challenges.models import Challenge
from apps.challenges.serializers import ChallengeSerializer
from apps.gaps.serializers import UserSkillGapSerializer
from apps.gaps.services import list_user_gaps
from apps.users.models import User


def build_roadmap(user: User) -> dict[str, Any]:
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

    steps = []
    for gap in gaps:
        related = [
            c
            for c in suggested
            if any(cs.skill_id == gap.skill_id for cs in c.challenge_skills.all())
        ]
        steps.append(
            {
                "gap": UserSkillGapSerializer(gap).data,
                "suggested_challenges": ChallengeSerializer(related[:3], many=True).data,
                "status": gap.status,
            }
        )

    return {
        "steps": steps,
        "suggested_challenges": ChallengeSerializer(suggested, many=True).data,
        "focus_skills": [g.skill.slug for g in gaps[:5]],
    }

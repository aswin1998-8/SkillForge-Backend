"""Gap upsert and evidence helpers."""

from __future__ import annotations

from django.db import transaction

from apps.gaps.models import GapEvidence, UserSkillGap
from apps.roles.models import Skill
from apps.users.models import User


@transaction.atomic
def upsert_user_skill_gap(
    *,
    user: User,
    skill: Skill,
    status: str = UserSkillGap.Status.NOT_STARTED,
    evidence_source_type: str | None = None,
    evidence_source_id: str | None = None,
    evidence_summary: str = "",
) -> UserSkillGap:
    gap, created = UserSkillGap.objects.get_or_create(
        user=user,
        skill=skill,
        defaults={"status": status},
    )
    if not created and gap.status == UserSkillGap.Status.CLOSED and status != UserSkillGap.Status.CLOSED:
        gap.status = status
        gap.save(update_fields=["status", "updated_at"])
    elif not created and gap.status == UserSkillGap.Status.NOT_STARTED and status == UserSkillGap.Status.IN_PROGRESS:
        gap.status = status
        gap.save(update_fields=["status", "updated_at"])

    if evidence_source_type:
        GapEvidence.objects.create(
            user_skill_gap=gap,
            source_type=evidence_source_type,
            source_id=evidence_source_id or "",
            summary=evidence_summary,
        )
    return gap


def list_user_gaps(user: User, *, include_closed: bool = False):
    qs = UserSkillGap.objects.filter(user=user).select_related("skill").prefetch_related("evidence")
    if not include_closed:
        qs = qs.exclude(status=UserSkillGap.Status.CLOSED)
    return qs

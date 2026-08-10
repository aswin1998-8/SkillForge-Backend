"""Dashboard summary derived from gaps, daily challenge, and sessions."""

from __future__ import annotations

from typing import Any

from django.utils import timezone

from apps.challenges.models import DailyChallenge
from apps.challenges.serializers import DailyChallengeSerializer
from apps.challenges.services import get_or_assign_today_challenge
from apps.diagnostics.models import DiagnosticRoadmapItem, DiagnosticSession
from apps.gaps.models import UserSkillGap
from apps.gaps.serializers import UserSkillGapSerializer
from apps.gaps.services import (
    enrich_gap_rows,
    list_user_gaps,
    _synthesis_gap_index,
    _topic_challenge_map,
)
from apps.sessions.models import LearningSession
from apps.sessions.serializers import LearningSessionSerializer
from apps.users.models import User


def build_dashboard(user: User) -> dict[str, Any]:
    open_gaps_qs = list_user_gaps(user, include_closed=False)
    closed_gaps_qs = list_user_gaps(user, include_closed=True).filter(
        status=UserSkillGap.Status.CLOSED
    )
    closed_count = closed_gaps_qs.count()
    recent_sessions = LearningSession.objects.filter(user=user)[:5]
    active_diagnostic = (
        DiagnosticSession.objects.filter(
            user=user,
            status=DiagnosticSession.Status.AWAITING_ANSWERS,
        )
        .order_by("-updated_at", "-id")
        .first()
    )
    completed_diagnostic = (
        DiagnosticSession.objects.filter(
            user=user,
            status=DiagnosticSession.Status.COMPLETED,
        )
        .order_by("-completed_at", "-id")
        .first()
    )
    roadmap_qs = DiagnosticRoadmapItem.objects.filter(user=user)
    roadmap_steps_total = roadmap_qs.count()
    roadmap_steps_closed = roadmap_qs.filter(status="closed").count()
    has_roadmap = roadmap_steps_total > 0
    roadmap_complete = (
        completed_diagnostic is not None
        and roadmap_steps_total > 0
        and roadmap_steps_closed == roadmap_steps_total
    )
    rediagnostic_unlocked = roadmap_complete
    profile = getattr(user, "profile", None)
    onboarding_completed = bool(getattr(profile, "onboarding_completed", False))
    diagnostic_difficulty_bump = int(
        getattr(profile, "diagnostic_difficulty_bump", 0) or 0
    )
    diagnostic_cycle = int(getattr(profile, "diagnostic_cycle", 1) or 1)

    daily = None
    if (
        onboarding_completed
        and (has_roadmap or completed_diagnostic)
        and not active_diagnostic
        and not roadmap_complete
    ):
        try:
            daily = get_or_assign_today_challenge(user=user)
        except Exception:  # noqa: BLE001
            daily = (
                DailyChallenge.objects.select_related("challenge")
                .prefetch_related("challenge__challenge_skills__skill")
                .filter(user=user, date=timezone.localdate())
                .first()
            )
    else:
        daily = (
            DailyChallenge.objects.select_related("challenge")
            .prefetch_related("challenge__challenge_skills__skill")
            .filter(user=user, date=timezone.localdate())
            .first()
        )
        if roadmap_complete:
            daily = None

    focus_topics = list(
        DiagnosticRoadmapItem.objects.filter(user=user)
        .exclude(status="closed")
        .order_by("priority", "id")
        .values_list("topic", flat=True)[:5]
    )

    synth_index = _synthesis_gap_index(completed_diagnostic)
    topic_challenges = _topic_challenge_map(user)
    open_gaps = enrich_gap_rows(
        list(UserSkillGapSerializer(open_gaps_qs[:10], many=True).data),
        synth_index=synth_index,
        topic_challenges=topic_challenges,
    )
    recently_closed_gaps = enrich_gap_rows(
        list(UserSkillGapSerializer(closed_gaps_qs[:5], many=True).data),
        synth_index=synth_index,
        topic_challenges=topic_challenges,
    )

    return {
        "open_gaps_count": open_gaps_qs.count(),
        "closed_gaps_count": closed_count,
        "open_gaps": open_gaps,
        "recently_closed_gaps": recently_closed_gaps,
        "today_challenge": DailyChallengeSerializer(daily).data if daily else None,
        "recent_sessions": LearningSessionSerializer(recent_sessions, many=True).data,
        "onboarding_completed": onboarding_completed,
        "active_diagnostic_session_id": active_diagnostic.id if active_diagnostic else None,
        "diagnostic_completed": completed_diagnostic is not None,
        "has_roadmap": has_roadmap,
        "roadmap_steps_count": roadmap_steps_total,
        "roadmap_steps_total": roadmap_steps_total,
        "roadmap_steps_closed": roadmap_steps_closed,
        "roadmap_complete": roadmap_complete,
        "rediagnostic_unlocked": rediagnostic_unlocked,
        "diagnostic_difficulty_bump": diagnostic_difficulty_bump,
        "diagnostic_cycle": diagnostic_cycle,
        "roadmap_focus_topics": focus_topics,
    }

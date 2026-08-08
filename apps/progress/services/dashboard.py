"""Dashboard summary derived from gaps, daily challenge, and sessions."""

from __future__ import annotations

from typing import Any

from django.utils import timezone

from apps.challenges.models import DailyChallenge
from apps.challenges.serializers import DailyChallengeSerializer
from apps.gaps.models import UserSkillGap
from apps.gaps.serializers import UserSkillGapSerializer
from apps.gaps.services import list_user_gaps
from apps.sessions.models import LearningSession
from apps.sessions.serializers import LearningSessionSerializer
from apps.users.models import User


def build_dashboard(user: User) -> dict[str, Any]:
    open_gaps = list_user_gaps(user, include_closed=False)
    closed_count = UserSkillGap.objects.filter(
        user=user,
        status=UserSkillGap.Status.CLOSED,
    ).count()
    today = timezone.localdate()
    daily = (
        DailyChallenge.objects.select_related("challenge")
        .prefetch_related("challenge__challenge_skills__skill")
        .filter(user=user, date=today)
        .first()
    )
    recent_sessions = LearningSession.objects.filter(user=user)[:5]

    return {
        "open_gaps_count": open_gaps.count(),
        "closed_gaps_count": closed_count,
        "open_gaps": UserSkillGapSerializer(open_gaps[:10], many=True).data,
        "today_challenge": DailyChallengeSerializer(daily).data if daily else None,
        "recent_sessions": LearningSessionSerializer(recent_sessions, many=True).data,
        "onboarding_completed": bool(
            getattr(getattr(user, "profile", None), "onboarding_completed", False)
        ),
    }

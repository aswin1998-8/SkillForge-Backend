"""Staff waitlist and user-activity APIs."""

from __future__ import annotations

from typing import Any

from django.db.models import Count, Max, Q
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.challenges.models import ChallengeAttempt
from apps.core.invites import invite_status_payload, issue_invite_for_signup
from apps.core.models import InviteToken, WaitlistSignup
from apps.core.permissions import IsStaffUser
from apps.core.responses import success_response
from apps.diagnostics.models import DiagnosticSession
from apps.gaps.models import UserSkillGap
from apps.sessions.models import LearningSession
from apps.users.models import User


def _paginate(qs, request: Request, *, default: int = 50, max_size: int = 100):
    try:
        page = max(int(request.query_params.get("page") or 1), 1)
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = min(
            max(int(request.query_params.get("page_size") or default), 1),
            max_size,
        )
    except (TypeError, ValueError):
        page_size = default
    total = qs.count()
    start = (page - 1) * page_size
    items = list(qs[start : start + page_size])
    return items, {"page": page, "page_size": page_size, "total": total}


class StaffWaitlistListView(APIView):
    permission_classes = [IsAuthenticated, IsStaffUser]

    def get(self, request: Request) -> Response:
        qs = WaitlistSignup.objects.all()
        q = (request.query_params.get("q") or "").strip()
        if q:
            qs = qs.filter(email__icontains=q)
        rows, page = _paginate(qs, request)
        emails = [row.email.lower() for row in rows]
        accounts = set(
            User.objects.filter(email__in=emails).values_list("email", flat=True)
        )
        latest_tokens: dict[str, InviteToken] = {}
        for token in InviteToken.objects.filter(email__in=emails).order_by("-created_at"):
            latest_tokens.setdefault(token.email.lower(), token)

        results: list[dict[str, Any]] = []
        for row in rows:
            email = row.email.lower()
            payload = invite_status_payload(latest_tokens.get(email))
            results.append(
                {
                    "id": row.id,
                    "email": row.email,
                    "role_or_stack": row.role_or_stack,
                    "interest_note": row.interest_note,
                    "utm_source": row.utm_source,
                    "utm_medium": row.utm_medium,
                    "utm_campaign": row.utm_campaign,
                    "invited": row.invited,
                    "invited_at": row.invited_at,
                    "created_at": row.created_at,
                    "has_account": email in {e.lower() for e in accounts},
                    **payload,
                }
            )
        return success_response({**page, "results": results})


class StaffWaitlistInviteView(APIView):
    permission_classes = [IsAuthenticated, IsStaffUser]

    def post(self, request: Request, pk: int) -> Response:
        signup = WaitlistSignup.objects.filter(pk=pk).first()
        if signup is None:
            raise NotFound("Waitlist signup not found.")
        token = issue_invite_for_signup(signup)
        signup.refresh_from_db()
        return success_response(
            {
                "id": signup.id,
                "email": signup.email,
                "invited": True,
                "invited_at": signup.invited_at,
                "invite_status": "pending",
                "invite_expires_at": token.expires_at,
            },
            message="Invite sent.",
            status=status.HTTP_200_OK,
        )


class StaffUserListView(APIView):
    permission_classes = [IsAuthenticated, IsStaffUser]

    def get(self, request: Request) -> Response:
        qs = (
            User.objects.select_related("profile")
            .annotate(
                diagnostics_completed=Count(
                    "diagnostic_sessions",
                    filter=Q(
                        diagnostic_sessions__status=DiagnosticSession.Status.COMPLETED
                    ),
                ),
                challenges_completed=Count(
                    "challenge_attempts",
                    filter=Q(challenge_attempts__status=ChallengeAttempt.Status.COMPLETED),
                ),
                open_gaps=Count(
                    "skill_gaps",
                    filter=~Q(skill_gaps__status=UserSkillGap.Status.CLOSED),
                ),
                last_session_at=Max("learning_sessions__created_at"),
            )
            .order_by("-date_joined")
        )
        q = (request.query_params.get("q") or "").strip()
        if q:
            qs = qs.filter(
                Q(email__icontains=q)
                | Q(first_name__icontains=q)
                | Q(last_name__icontains=q)
            )
        users, page = _paginate(qs, request)
        results = []
        for user in users:
            profile = getattr(user, "profile", None)
            results.append(
                {
                    "id": user.id,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "is_staff": user.is_staff,
                    "email_verified": user.email_verified,
                    "date_joined": user.date_joined,
                    "last_login": user.last_login,
                    "onboarding_completed": bool(
                        getattr(profile, "onboarding_completed", False)
                    ),
                    "current_role": getattr(profile, "current_role", "") or "",
                    "diagnostics_completed": user.diagnostics_completed,
                    "challenges_completed": user.challenges_completed,
                    "open_gaps": user.open_gaps,
                    "last_session_at": user.last_session_at,
                }
            )
        return success_response({**page, "results": results})


class StaffUserDetailView(APIView):
    permission_classes = [IsAuthenticated, IsStaffUser]

    def get(self, request: Request, pk: int) -> Response:
        user = User.objects.select_related("profile", "profile__target_role").filter(pk=pk).first()
        if user is None:
            raise NotFound("User not found.")
        profile = getattr(user, "profile", None)
        target_role = getattr(profile, "target_role", None) if profile else None
        diagnostics = [
            {
                "id": session.id,
                "status": session.status,
                "goal": session.goal,
                "current_role": session.current_role,
                "target_role": session.target_role,
                "created_at": session.created_at,
                "completed_at": session.completed_at,
            }
            for session in DiagnosticSession.objects.filter(user=user)[:50]
        ]
        attempts = (
            ChallengeAttempt.objects.filter(user=user)
            .select_related("challenge")[:50]
        )
        challenge_attempts = [
            {
                "id": attempt.id,
                "status": attempt.status,
                "challenge_title": attempt.challenge.title,
                "modality": attempt.challenge.modality,
                "started_at": attempt.started_at,
                "completed_at": attempt.completed_at,
            }
            for attempt in attempts
        ]
        sessions = [
            {
                "id": session.id,
                "session_type": session.session_type,
                "title": session.title,
                "summary": session.summary,
                "created_at": session.created_at,
            }
            for session in LearningSession.objects.filter(user=user)[:50]
        ]
        gaps = (
            UserSkillGap.objects.filter(user=user)
            .select_related("skill")[:50]
        )
        gap_rows = [
            {
                "id": gap.id,
                "skill_name": gap.skill.name,
                "skill_slug": gap.skill.slug,
                "status": gap.status,
                "updated_at": gap.updated_at,
            }
            for gap in gaps
        ]
        return success_response(
            {
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "is_staff": user.is_staff,
                    "email_verified": user.email_verified,
                    "date_joined": user.date_joined,
                    "last_login": user.last_login,
                },
                "profile": None
                if profile is None
                else {
                    "current_role": profile.current_role,
                    "years_of_experience": profile.years_of_experience,
                    "technical_goal": profile.technical_goal,
                    "target_role": None
                    if target_role is None
                    else {
                        "id": target_role.id,
                        "slug": target_role.slug,
                        "name": target_role.name,
                    },
                    "target_role_label": profile.target_role_label,
                    "known_skills": profile.known_skills,
                    "target_learn_skills": profile.target_learn_skills,
                    "onboarding_completed": profile.onboarding_completed,
                    "diagnostic_cycle": profile.diagnostic_cycle,
                },
                "diagnostics": diagnostics,
                "challenge_attempts": challenge_attempts,
                "sessions": sessions,
                "gaps": gap_rows,
            }
        )

    def delete(self, request: Request, pk: int) -> Response:
        user = User.objects.filter(pk=pk).first()
        if user is None:
            raise NotFound("User not found.")
        if user.pk == request.user.pk:
            raise ValidationError({"id": "You cannot delete your own account."})
        email = user.email
        user.delete()
        return success_response({"id": pk, "email": email}, message="User deleted.")

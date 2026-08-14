"""Waitlist invite token issue, preview, and consume."""

from __future__ import annotations

import secrets
from datetime import timedelta
from typing import Any

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.core.models import InviteToken, WaitlistSignup

INVITE_TTL_DAYS = 7


def _normalize_email(email: str) -> str:
    return email.lower().strip()


def preview_invite(token: str) -> InviteToken:
    obj = InviteToken.objects.filter(token=token).first()
    if obj is None or not obj.is_valid():
        raise ValidationError(
            {"invite_token": "This invite link is invalid or has expired."}
        )
    return obj


@transaction.atomic
def consume_invite(*, token: str, email: str) -> InviteToken:
    email = _normalize_email(email)
    obj = (
        InviteToken.objects.select_for_update()
        .filter(token=token)
        .first()
    )
    if obj is None or not obj.is_valid():
        raise ValidationError(
            {"invite_token": "This invite link is invalid or has expired."}
        )
    if obj.email != email:
        raise ValidationError(
            {"invite_token": "This invite was issued for a different email."}
        )
    obj.used_at = timezone.now()
    obj.save(update_fields=["used_at"])
    return obj


def require_invite_for_new_user(*, email: str, invite_token: str) -> InviteToken:
    token = (invite_token or "").strip()
    if not token:
        raise ValidationError(
            {"invite_token": "An invite is required to create an account."}
        )
    return consume_invite(token=token, email=email)


@transaction.atomic
def issue_invite_for_signup(signup: WaitlistSignup) -> InviteToken:
    email = _normalize_email(signup.email)
    now = timezone.now()
    InviteToken.objects.filter(email=email, used_at__isnull=True).delete()
    token = InviteToken.objects.create(
        waitlist_signup=signup,
        email=email,
        token=secrets.token_urlsafe(32),
        expires_at=now + timedelta(days=INVITE_TTL_DAYS),
    )
    WaitlistSignup.objects.filter(email__iexact=email).update(
        invited=True,
        invited_at=now,
    )
    from apps.core.tasks import dispatch_invite_email

    dispatch_invite_email(email, token.token)
    return token


def invite_status_payload(token: InviteToken | None) -> dict[str, Any]:
    if token is None:
        return {
            "invite_status": "none",
            "invite_expires_at": None,
            "invite_used_at": None,
        }
    now = timezone.now()
    if token.used_at is not None:
        status = "used"
    elif token.expires_at <= now:
        status = "expired"
    else:
        status = "pending"
    return {
        "invite_status": status,
        "invite_expires_at": token.expires_at,
        "invite_used_at": token.used_at,
    }

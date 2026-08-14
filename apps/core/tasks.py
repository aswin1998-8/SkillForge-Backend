"""Waitlist invite email."""

from __future__ import annotations

import logging

from django.conf import settings
from rest_framework.exceptions import ValidationError

from apps.core.mail import send_outbound_email

logger = logging.getLogger(__name__)


def send_invite_email(email: str, token: str) -> None:
    frontend = getattr(settings, "FRONTEND_URL", "http://localhost:3000").rstrip("/")
    invite_url = f"{frontend}/signup?invite={token}"
    subject = "You're invited to Honed"
    message = (
        "Hi,\n\n"
        "You've been invited to join Honed. Create your account with this link:\n"
        f"{invite_url}\n\n"
        "This link expires in 7 days and can be used once. "
        "Sign up with the same email this invite was sent to.\n"
    )
    send_outbound_email(to=email, subject=subject, text=message)


def dispatch_invite_email(email: str, token: str) -> None:
    """Send immediately in-process. Celery/Redis is not required on Render."""
    try:
        send_invite_email(email, token)
    except ValidationError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to send invite email to %s", email)
        raise ValidationError(
            {
                "email": (
                    "Could not send the invite email. Set RESEND_API_KEY on Render "
                    "(SMTP is often blocked) or EMAIL_HOST credentials."
                )
            }
        ) from exc

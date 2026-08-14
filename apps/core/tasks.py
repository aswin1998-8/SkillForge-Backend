"""Waitlist invite email tasks."""

from __future__ import annotations

import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_invite_email_task(self, email: str, token: str) -> None:
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
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to send invite email to %s", email)
        raise self.retry(exc=exc) from exc


def dispatch_invite_email(email: str, token: str) -> None:
    try:
        send_invite_email_task.delay(email, token)
    except Exception:  # noqa: BLE001
        logger.warning("Celery unavailable; sending invite email synchronously")
        send_invite_email_task(email, token)

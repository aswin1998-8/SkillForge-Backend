"""Auth email Celery tasks."""

from __future__ import annotations

import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_verification_email_task(self, user_id: int, token: str) -> None:
    from apps.users.models import User

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.warning("Verification email skipped; user %s missing", user_id)
        return

    frontend = getattr(settings, "FRONTEND_URL", "http://localhost:3000").rstrip("/")
    verify_url = f"{frontend}/verify-email?token={token}"
    subject = "Verify your ForgeIQ email"
    message = (
        f"Hi {user.first_name or 'there'},\n\n"
        f"Confirm your ForgeIQ account by opening this link:\n{verify_url}\n\n"
        "This link expires in 24 hours.\n"
    )
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to send verification email to %s", user.email)
        raise self.retry(exc=exc) from exc


def dispatch_verification_email(user_id: int, token: str) -> None:
    """Enqueue Celery task; fall back to sync send if broker unavailable."""
    try:
        send_verification_email_task.delay(user_id, token)
    except Exception:  # noqa: BLE001
        logger.warning("Celery unavailable; sending verification email synchronously")
        send_verification_email_task(user_id, token)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_password_reset_email_task(self, user_id: int, token: str) -> None:
    from apps.users.models import User

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.warning("Password reset email skipped; user %s missing", user_id)
        return

    frontend = getattr(settings, "FRONTEND_URL", "http://localhost:3000").rstrip("/")
    reset_url = f"{frontend}/reset-password?token={token}"
    subject = "Reset your ForgeIQ password"
    message = (
        f"Hi {user.first_name or 'there'},\n\n"
        f"Reset your ForgeIQ password using this link:\n{reset_url}\n\n"
        "This link expires in 1 hour. If you did not request a reset, ignore this email.\n"
    )
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to send password reset email to %s", user.email)
        raise self.retry(exc=exc) from exc


def dispatch_password_reset_email(user_id: int, token: str) -> None:
    try:
        send_password_reset_email_task.delay(user_id, token)
    except Exception:  # noqa: BLE001
        logger.warning("Celery unavailable; sending password reset email synchronously")
        send_password_reset_email_task(user_id, token)

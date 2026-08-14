import secrets
from datetime import timedelta

import pytest
from django.utils import timezone


@pytest.fixture(autouse=True)
def _email_locmem(settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"


@pytest.fixture(autouse=True)
def _celery_eager(settings):
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True


@pytest.fixture(autouse=True)
def _relax_throttles(settings):
    rates = {
        **settings.REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {}),
        "register": "1000/min",
        "login": "1000/min",
        "google": "1000/min",
        "resend_verification": "1000/min",
        "anon": "1000/min",
        "user": "1000/min",
        "forgot_password": "1000/min",
        "reset_password": "1000/min",
        "waitlist": "1000/min",
        "invite_preview": "1000/min",
    }
    settings.REST_FRAMEWORK = {
        **settings.REST_FRAMEWORK,
        "DEFAULT_THROTTLE_CLASSES": [],
        "DEFAULT_THROTTLE_RATES": rates,
    }
    from rest_framework.throttling import SimpleRateThrottle

    SimpleRateThrottle.THROTTLE_RATES = rates


def make_invite(email: str) -> str:
    from apps.core.models import InviteToken, WaitlistSignup

    email = email.lower().strip()
    signup = WaitlistSignup.objects.create(email=email)
    token = secrets.token_urlsafe(32)
    InviteToken.objects.create(
        waitlist_signup=signup,
        email=email,
        token=token,
        expires_at=timezone.now() + timedelta(days=7),
    )
    return token

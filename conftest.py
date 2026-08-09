import pytest


@pytest.fixture(autouse=True)
def _celery_eager(settings):
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True
    settings.AI_PROVIDER = "mock"


@pytest.fixture(autouse=True)
def _relax_throttles(settings):
    settings.REST_FRAMEWORK = {
        **settings.REST_FRAMEWORK,
        "DEFAULT_THROTTLE_CLASSES": [],
        "DEFAULT_THROTTLE_RATES": {
            **settings.REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {}),
            "register": "1000/min",
            "login": "1000/min",
            "google": "1000/min",
            "resend_verification": "1000/min",
            "anon": "1000/min",
            "user": "1000/min",
            "ai": "1000/min",
            "forgot_password": "1000/min",
            "reset_password": "1000/min",
        },
    }

"""SkillForge Django settings."""

from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

import dj_database_url
from corsheaders.defaults import default_headers
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or value == "":
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _split_env(name: str, default: str = "") -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


def _origin_list(name: str, default: str = "") -> list[str]:
    """Normalize origins — browsers send Origin without a trailing slash."""
    return [origin.rstrip("/") for origin in _split_env(name, default)]


SECRET_KEY = _require_env("SECRET_KEY")
DEBUG = os.getenv("DEBUG", "False").lower() in {"1", "true", "yes"}
ALLOWED_HOSTS = _split_env("ALLOWED_HOSTS", "localhost,127.0.0.1")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt",
    "drf_spectacular",
    "apps.core",
    "apps.users",
    "apps.roles",
    "apps.diagnostics",
    "apps.gaps",
    "apps.challenges",
    "apps.sessions",
    "apps.progress",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": dj_database_url.parse(
        _require_env("DATABASE_URL"),
        conn_max_age=600,
        conn_health_checks=True,
    )
}

AUTH_USER_MODEL = "users.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CORS_ALLOWED_ORIGINS = _origin_list("CORS_ALLOWED_ORIGINS", "http://localhost:3000")
CORS_ALLOW_CREDENTIALS = True
# Cookie + CSRF preflight: browsers send Access-Control-Request-Headers: x-csrftoken
# which is not in django-cors-headers defaults.
CORS_ALLOW_HEADERS = list(default_headers) + [
    "x-csrftoken",
    "x-requested-with",
]
# Optional: comma-separated regexes, e.g. ^https://.*\.vercel\.app$
CORS_ALLOWED_ORIGIN_REGEXES = _split_env("CORS_ALLOWED_ORIGIN_REGEXES", "")
CSRF_TRUSTED_ORIGINS = _origin_list("CSRF_TRUSTED_ORIGINS", "http://localhost:3000")

# Behind Render/Vercel TLS terminators, treat X-Forwarded-Proto as HTTPS.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

COOKIE_SECURE = os.getenv("COOKIE_SECURE", "False").lower() in {"1", "true", "yes"}
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "Lax")
ACCESS_TOKEN_COOKIE_NAME = os.getenv("ACCESS_TOKEN_COOKIE_NAME", "sf_access")
REFRESH_TOKEN_COOKIE_NAME = os.getenv("REFRESH_TOKEN_COOKIE_NAME", "sf_refresh")

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
ADAPTIVE_WEAK_THRESHOLD = float(os.getenv("ADAPTIVE_WEAK_THRESHOLD", "0.4"))
ADAPTIVE_STRONG_THRESHOLD = float(os.getenv("ADAPTIVE_STRONG_THRESHOLD", "0.7"))
ADAPTIVE_ROLLING_WINDOW = int(os.getenv("ADAPTIVE_ROLLING_WINDOW", "5"))
DIAGNOSTIC_MAX_COMPETENCY_AREAS = int(os.getenv("DIAGNOSTIC_MAX_COMPETENCY_AREAS", "4"))
DIAGNOSTIC_SESSION_QUESTION_BUDGET = int(
    os.getenv("DIAGNOSTIC_SESSION_QUESTION_BUDGET", "15")
)
FOUNDATIONAL_SKIP_COUNT = int(os.getenv("FOUNDATIONAL_SKIP_COUNT", "3"))
CODE_EXECUTION_ENABLED = os.getenv("CODE_EXECUTION_ENABLED", "True").lower() in {
    "1",
    "true",
    "yes",
}
CODE_EXECUTION_TIMEOUT_SECONDS = float(os.getenv("CODE_EXECUTION_TIMEOUT_SECONDS", "5"))
ALLOW_STAFF_PROGRESS_RESET = os.getenv("ALLOW_STAFF_PROGRESS_RESET", "False").lower() in {
    "1",
    "true",
    "yes",
}
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")

DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "noreply@forgeiq.app")
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587") or "587")
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True").lower() in {"1", "true", "yes"}
_email_backend = os.getenv("EMAIL_BACKEND", "").strip()
if "locmem" in _email_backend:
    EMAIL_BACKEND = _email_backend
elif EMAIL_HOST:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
elif _email_backend:
    EMAIL_BACKEND = _email_backend
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_TASK_TRACK_STARTED = True
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "apps.users.authentication.CookieJWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/min",
        "user": "120/min",
        "register": "5/min",
        "login": "10/min",
        "google": "10/min",
        "resend_verification": "3/min",
        "forgot_password": "5/min",
        "reset_password": "5/min",
        "waitlist": "5/min",
        "invite_preview": "20/min",
    },
    "EXCEPTION_HANDLER": "apps.core.exceptions.custom_exception_handler",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": False,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "SkillForge API",
    "DESCRIPTION": "Technical mastery platform API",
    "VERSION": "1.0.0",
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "structured": {
            "format": "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "structured",
        }
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "apps": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "celery": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}

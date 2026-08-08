"""Auth cookie helpers."""

from __future__ import annotations

from django.conf import settings
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken


def set_jwt_cookies(response: Response, refresh: RefreshToken) -> Response:
    access = str(refresh.access_token)
    refresh_token = str(refresh)

    common = {
        "httponly": True,
        "secure": settings.COOKIE_SECURE,
        "samesite": settings.COOKIE_SAMESITE,
        "path": "/",
    }

    response.set_cookie(
        settings.ACCESS_TOKEN_COOKIE_NAME,
        access,
        max_age=int(settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds()),
        **common,
    )
    response.set_cookie(
        settings.REFRESH_TOKEN_COOKIE_NAME,
        refresh_token,
        max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
        **common,
    )
    return response


def clear_jwt_cookies(response: Response) -> Response:
    response.delete_cookie(settings.ACCESS_TOKEN_COOKIE_NAME, path="/")
    response.delete_cookie(settings.REFRESH_TOKEN_COOKIE_NAME, path="/")
    return response


def tokens_for_user(user) -> RefreshToken:
    return RefreshToken.for_user(user)

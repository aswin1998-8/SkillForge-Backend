"""Shared API response helpers."""

from __future__ import annotations

from typing import Any

from rest_framework.response import Response


def success_response(
    data: Any = None,
    message: str = "Success",
    status: int = 200,
) -> Response:
    return Response({"data": data, "message": message}, status=status)


def error_response(
    *,
    code: str,
    message: str,
    details: Any = None,
    status: int = 400,
) -> Response:
    payload: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
        }
    }
    if details is not None:
        payload["error"]["details"] = details
    return Response(payload, status=status)

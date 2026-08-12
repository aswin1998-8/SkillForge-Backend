"""DRF exception handling with consistent error envelope."""

from __future__ import annotations

import logging
from typing import Any

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

from apps.diagnostics.code_executor import CodeSecurityError

logger = logging.getLogger(__name__)


def custom_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    if isinstance(exc, CodeSecurityError):
        return Response(
            {
                "error": {
                    "code": "CODE_SECURITY_ERROR",
                    "message": str(exc) or "Code rejected by security checks.",
                }
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    response = exception_handler(exc, context)
    if response is None:
        logger.exception("Unhandled API exception")
        return Response(
            {
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred.",
                }
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    details = response.data
    code = "API_ERROR"
    message = "Request failed"

    if isinstance(details, dict):
        if "detail" in details:
            message = str(details["detail"])
            code = "PERMISSION_DENIED" if response.status_code == 403 else "API_ERROR"
            if response.status_code == 401:
                code = "AUTHENTICATION_FAILED"
            details = None
        else:
            code = "VALIDATION_ERROR"
            message = "Invalid request"
    elif isinstance(details, list):
        code = "VALIDATION_ERROR"
        message = "Invalid request"

    payload: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
        }
    }
    if details is not None:
        payload["error"]["details"] = details
    response.data = payload
    return response

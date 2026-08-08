from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.responses import success_response
from apps.diagnostics.serializers import (
    DiagnosticAttemptSerializer,
    DiagnosticSerializer,
    SaveAnswersSerializer,
)
from apps.diagnostics.services import (
    get_active_diagnostics,
    get_attempt_for_user,
    get_diagnostic_or_404,
    save_answers,
    start_attempt,
    submit_attempt,
)


class DiagnosticListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        diagnostics = get_active_diagnostics()
        return success_response(DiagnosticSerializer(diagnostics, many=True).data)


class DiagnosticDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, diagnostic_id: int) -> Response:
        diagnostic = get_diagnostic_or_404(diagnostic_id)
        return success_response(DiagnosticSerializer(diagnostic).data)


class DiagnosticStartView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request, diagnostic_id: int) -> Response:
        attempt = start_attempt(user=request.user, diagnostic_id=diagnostic_id)
        return success_response(
            DiagnosticAttemptSerializer(attempt).data,
            message="Attempt started",
            status=status.HTTP_201_CREATED,
        )


class AttemptAnswersView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request, attempt_id: int) -> Response:
        serializer = SaveAnswersSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        attempt = save_answers(
            user=request.user,
            attempt_id=attempt_id,
            answers=serializer.validated_data["answers"],
        )
        return success_response(
            DiagnosticAttemptSerializer(attempt).data,
            message="Answers saved",
        )


class AttemptSubmitView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request, attempt_id: int) -> Response:
        attempt = submit_attempt(user=request.user, attempt_id=attempt_id)
        return success_response(
            DiagnosticAttemptSerializer(attempt).data,
            message="Attempt submitted for processing",
        )


class AttemptDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, attempt_id: int) -> Response:
        attempt = get_attempt_for_user(user=request.user, attempt_id=attempt_id)
        return success_response(DiagnosticAttemptSerializer(attempt).data)

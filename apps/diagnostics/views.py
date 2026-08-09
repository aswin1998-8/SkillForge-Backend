from __future__ import annotations

from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from apps.core.responses import success_response
from apps.diagnostics.adaptive import ensure_next_turn, submit_turn_answer
from apps.diagnostics.serializers import (
    DiagnosticAttemptSerializer,
    DiagnosticSerializer,
    DiagnosticSessionSerializer,
    SaveAnswersSerializer,
    StartDiagnosticSessionSerializer,
    SubmitSessionAnswersSerializer,
    SubmitTurnSerializer,
)
from apps.diagnostics.block_assessment import (
    get_session_for_user,
    start_session,
    submit_stage_answers,
)
from apps.diagnostics.services import (
    get_active_diagnostics,
    get_attempt_for_user,
    get_diagnostic_or_404,
    save_answers,
    start_attempt,
    submit_attempt,
)


class AIRateThrottle(UserRateThrottle):
    scope = "ai"


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
    throttle_classes = [AIRateThrottle]

    def post(self, request: Request, diagnostic_id: int) -> Response:
        attempt = start_attempt(user=request.user, diagnostic_id=diagnostic_id)
        attempt = get_attempt_for_user(user=request.user, attempt_id=attempt.id)
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
    throttle_classes = [AIRateThrottle]

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


class AttemptNextView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [AIRateThrottle]

    def post(self, request: Request, attempt_id: int) -> Response:
        attempt = get_attempt_for_user(user=request.user, attempt_id=attempt_id)
        ensure_next_turn(attempt=attempt)
        attempt = get_attempt_for_user(user=request.user, attempt_id=attempt_id)
        return success_response(DiagnosticAttemptSerializer(attempt).data)


class AttemptTurnSubmitView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [AIRateThrottle]

    def post(self, request: Request, attempt_id: int) -> Response:
        serializer = SubmitTurnSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        attempt = submit_turn_answer(
            user=request.user,
            attempt_id=attempt_id,
            turn_id=serializer.validated_data["turn_id"],
            answer_text=serializer.validated_data["answer_text"],
        )
        return success_response(
            DiagnosticAttemptSerializer(attempt).data,
            message="Turn submitted",
        )


class DiagnosticSessionListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [AIRateThrottle]

    def post(self, request: Request) -> Response:
        serializer = StartDiagnosticSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            session = start_session(
                user=request.user,
                goal=serializer.validated_data["goal"],
                domain_slugs=serializer.validated_data.get("domain_slugs") or [],
            )
        except ValidationError as exc:
            detail = getattr(exc, "detail", exc)
            if isinstance(detail, dict) and "session_id" in detail:
                return Response(
                    {
                        "error": {
                            "code": "active_session",
                            "message": str(detail.get("detail") or detail),
                            "details": detail,
                        }
                    },
                    status=status.HTTP_409_CONFLICT,
                )
            raise
        session = get_session_for_user(user=request.user, session_id=session.id)
        return success_response(
            DiagnosticSessionSerializer(session).data,
            message="Diagnostic session started",
            status=status.HTTP_201_CREATED,
        )


class DiagnosticSessionDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, session_id: int) -> Response:
        session = get_session_for_user(user=request.user, session_id=session_id)
        return success_response(DiagnosticSessionSerializer(session).data)


class DiagnosticSessionAnswersView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [AIRateThrottle]

    def post(self, request: Request, session_id: int) -> Response:
        serializer = SubmitSessionAnswersSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session = submit_stage_answers(
            user=request.user,
            session_id=session_id,
            answers=serializer.validated_data["answers"],
        )
        session = get_session_for_user(user=request.user, session_id=session.id)
        return success_response(
            DiagnosticSessionSerializer(session).data,
            message="Answers submitted",
        )

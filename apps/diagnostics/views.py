from __future__ import annotations

from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.responses import success_response
from apps.diagnostics.models import FrameworkTopic
from apps.diagnostics.serializers import (
    DiagnosticSessionSerializer,
    FrameworkTopicSerializer,
    RunTestsSerializer,
    SelfRateAnswerSerializer,
    StartDiagnosticSessionSerializer,
    SubmitSessionAnswersSerializer,
)
from apps.diagnostics.session_service import (
    get_session_for_user,
    reveal_answer,
    run_tests_preview,
    self_rate_answer,
    start_session,
    submit_stage_answers,
)
from apps.diagnostics.topic_defaults import ensure_default_topics


class FrameworkTopicListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        ensure_default_topics()
        topics = FrameworkTopic.objects.select_related("fundamentals_topic").all()
        return success_response(FrameworkTopicSerializer(topics, many=True).data)


class DiagnosticSessionListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        serializer = StartDiagnosticSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            session = start_session(
                user=request.user,
                goal=serializer.validated_data["goal"],
                framework_slugs=serializer.validated_data["framework_slugs"],
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

    def post(self, request: Request, session_id: int) -> Response:
        serializer = SubmitSessionAnswersSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session = submit_stage_answers(
            user=request.user,
            session_id=session_id,
            answers=serializer.validated_data["answers"],
        )
        return success_response(
            DiagnosticSessionSerializer(session).data,
            message="Answers submitted",
        )


class DiagnosticSessionAnswerRevealView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request, session_id: int, answer_id: int) -> Response:
        payload = reveal_answer(
            user=request.user,
            session_id=session_id,
            answer_id=answer_id,
        )
        return success_response(payload, message="Reference answer revealed")


class DiagnosticSessionAnswerSelfRateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request, session_id: int, answer_id: int) -> Response:
        serializer = SelfRateAnswerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        answer = self_rate_answer(
            user=request.user,
            session_id=session_id,
            answer_id=answer_id,
            rubric_alignment=serializer.validated_data["rubric_alignment"],
        )
        session = get_session_for_user(user=request.user, session_id=session_id)
        return success_response(
            DiagnosticSessionSerializer(session).data,
            message="Self-rating recorded",
        )


class DiagnosticSessionRunTestsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request, session_id: int) -> Response:
        serializer = RunTestsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        results = run_tests_preview(
            user=request.user,
            session_id=session_id,
            question_id=serializer.validated_data["question_id"],
            code=serializer.validated_data["code"],
        )
        return success_response({"test_results": results})

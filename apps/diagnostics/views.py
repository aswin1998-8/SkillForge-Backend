from __future__ import annotations

from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.responses import success_response
from apps.diagnostics.models import FrameworkTopic, QuickScoreAttempt
from apps.diagnostics.quick_score import (
    ensure_default_quick_score_content,
    get_quick_score_questions,
    infer_track,
    render_quick_score_png,
    submit_quick_score,
)
from apps.diagnostics.serializers import (
    DiagnosticSessionSerializer,
    FrameworkTopicSerializer,
    QuickScoreAttemptSerializer,
    QuickScoreQuestionSerializer,
    RunTestsSerializer,
    SelfRateAnswerSerializer,
    StartDiagnosticSessionSerializer,
    SubmitQuickScoreSerializer,
    SubmitSessionAnswersSerializer,
)
from apps.diagnostics.session_service import (
    get_active_session,
    get_session_for_user,
    reveal_answer,
    run_tests_preview,
    self_rate_answer,
    start_session,
    submit_stage_answers,
)
from apps.diagnostics.topic_defaults import ensure_default_topics
from django.http import HttpResponse


class FrameworkTopicListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        ensure_default_topics()
        topics = FrameworkTopic.objects.select_related("fundamentals_topic").all()
        return success_response(FrameworkTopicSerializer(topics, many=True).data)


class DiagnosticSessionListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        active = get_active_session(user=request.user)
        if active is None:
            return success_response({"active_session": None})
        session = get_session_for_user(user=request.user, session_id=active.id)
        return success_response(
            {
                "active_session": DiagnosticSessionSerializer(session).data,
            }
        )

    def post(self, request: Request) -> Response:
        serializer = StartDiagnosticSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        existing = get_active_session(user=request.user)
        session = start_session(
            user=request.user,
            goal=serializer.validated_data["goal"],
            framework_slugs=serializer.validated_data["framework_slugs"],
        )
        session = get_session_for_user(user=request.user, session_id=session.id)
        resumed = existing is not None and existing.id == session.id
        return success_response(
            DiagnosticSessionSerializer(session).data,
            message="Diagnostic session resumed" if resumed else "Diagnostic session started",
            status=status.HTTP_200_OK if resumed else status.HTTP_201_CREATED,
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


class QuickScoreQuestionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        ensure_default_quick_score_content()
        track = request.query_params.get("track")
        profile = getattr(request.user, "profile", None)
        if track not in {"frontend", "backend"}:
            track = infer_track(
                current_role=getattr(profile, "current_role", "") or "",
                known_skills=list(getattr(profile, "known_skills", None) or []),
            )
        years = getattr(profile, "years_of_experience", None)
        try:
            years_int = int(years) if years is not None else None
        except (TypeError, ValueError):
            years_int = None
        questions = get_quick_score_questions(
            track=track,
            user=request.user,
            years_of_experience=years_int,
        )
        return success_response(
            {
                "track": track,
                "questions": QuickScoreQuestionSerializer(questions, many=True).data,
            }
        )


class QuickScoreSubmitView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        ensure_default_quick_score_content()
        serializer = SubmitQuickScoreSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        attempt = submit_quick_score(
            user=request.user,
            track=serializer.validated_data["track"],
            answers=serializer.validated_data["answers"],
        )
        return success_response(
            QuickScoreAttemptSerializer(attempt).data,
            message="Quick score complete",
            status=status.HTTP_201_CREATED,
        )


class QuickScoreDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, attempt_id: int) -> Response:
        try:
            attempt = QuickScoreAttempt.objects.get(id=attempt_id, user=request.user)
        except QuickScoreAttempt.DoesNotExist as exc:
            raise NotFound("Quick score attempt not found.") from exc
        return success_response(QuickScoreAttemptSerializer(attempt).data)


class QuickScoreOgImageView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, attempt_id: int) -> HttpResponse:
        try:
            attempt = QuickScoreAttempt.objects.get(id=attempt_id, user=request.user)
        except QuickScoreAttempt.DoesNotExist as exc:
            raise NotFound("Quick score attempt not found.") from exc
        png = render_quick_score_png(attempt)
        return HttpResponse(png, content_type="image/png")

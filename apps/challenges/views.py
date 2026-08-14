from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.challenges.models import AnalyticsEvent
from apps.challenges.serializers import (
    AnalyticsEventSerializer,
    ChallengeAttemptSerializer,
    ChallengeRunTestsSerializer,
    ChallengeSerializer,
    ChallengeSubmitSerializer,
    ConfidenceCreateSerializer,
    ConfidenceRatingSerializer,
    DailyChallengeSerializer,
    DebriefChecklistSerializer,
    DebriefFollowUpsSerializer,
    WarRoomBeatSerializer,
)
from apps.challenges.services import (
    challenge_is_locked,
    complete_debrief,
    get_attempt_for_user,
    get_challenge_or_404,
    get_debrief_payload,
    get_or_assign_today_challenge,
    run_challenge_tests_preview,
    save_confidence,
    submit_challenge,
    submit_debrief_checklist,
)
from apps.challenges.war_room import advance_war_room_beat, war_room_state
from apps.core.responses import success_response
from django.utils import timezone


class TodayChallengeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        daily = get_or_assign_today_challenge(user=request.user)
        return success_response(DailyChallengeSerializer(daily).data)


class ChallengeDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, challenge_id: int) -> Response:
        challenge = get_challenge_or_404(challenge_id)
        locked, current_id = challenge_is_locked(
            user=request.user,
            challenge_id=challenge.id,
        )
        if current_id is None:
            # No roadmap lock — still surface the current assignment for convenience.
            try:
                current_id = get_or_assign_today_challenge(user=request.user).challenge_id
                locked = False
            except Exception:  # noqa: BLE001
                current_id = None
                locked = False
        data = ChallengeSerializer(challenge).data
        data["is_locked"] = locked
        data["today_challenge_id"] = current_id
        data["current_challenge_id"] = current_id
        return success_response(data)


class ChallengeSubmitView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request, challenge_id: int) -> Response:
        serializer = ChallengeSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        attempt = submit_challenge(
            user=request.user,
            challenge_id=challenge_id,
            payload=serializer.validated_data,
        )
        return success_response(
            ChallengeAttemptSerializer(attempt).data,
            message="Challenge submitted",
            status=status.HTTP_201_CREATED,
        )


class ChallengeRunTestsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request, challenge_id: int) -> Response:
        serializer = ChallengeRunTestsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = run_challenge_tests_preview(
            user=request.user,
            challenge_id=challenge_id,
            code=serializer.validated_data.get("code") or "",
            files=serializer.validated_data.get("files") or {},
        )
        return success_response(payload, message="Tests executed")


class ChallengeWarRoomBeatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, challenge_id: int) -> Response:
        return success_response(war_room_state(user=request.user, challenge_id=challenge_id))

    def post(self, request: Request, challenge_id: int) -> Response:
        serializer = WarRoomBeatSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = advance_war_room_beat(
            user=request.user,
            challenge_id=challenge_id,
            beat_id=serializer.validated_data["beat_id"],
            text=serializer.validated_data["text"],
        )
        return success_response(payload, message="War room beat recorded")


class AttemptConfidenceView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request, attempt_id: int) -> Response:
        serializer = ConfidenceCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rating = save_confidence(
            user=request.user,
            attempt_id=attempt_id,
            score=serializer.validated_data["score"],
            note=serializer.validated_data.get("note") or "",
        )
        return success_response(
            ConfidenceRatingSerializer(rating).data,
            message="Confidence saved",
            status=status.HTTP_201_CREATED,
        )


class AttemptDebriefView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, attempt_id: int) -> Response:
        attempt = get_attempt_for_user(user=request.user, attempt_id=attempt_id)
        return success_response(get_debrief_payload(attempt=attempt))


class AttemptDebriefChecklistView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request, attempt_id: int) -> Response:
        serializer = DebriefChecklistSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = submit_debrief_checklist(
            user=request.user,
            attempt_id=attempt_id,
            checklist=serializer.validated_data["checklist"],
        )
        return success_response(payload, message="Checklist saved")


class AttemptDebriefCompleteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request, attempt_id: int) -> Response:
        serializer = DebriefFollowUpsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = complete_debrief(
            user=request.user,
            attempt_id=attempt_id,
            follow_up_answers=serializer.validated_data["follow_up_answers"],
        )
        return success_response(payload, message="Debrief completed")


class AnalyticsEventView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        serializer = AnalyticsEventSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        event = AnalyticsEvent.objects.create(
            user=request.user,
            name=serializer.validated_data["name"],
            properties=serializer.validated_data.get("properties") or {},
        )
        return success_response(
            {"id": event.id, "name": event.name, "created_at": timezone.now().isoformat()},
            status=status.HTTP_201_CREATED,
        )

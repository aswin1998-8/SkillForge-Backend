from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.challenges.serializers import (
    ChallengeAttemptSerializer,
    ChallengeSerializer,
    ChallengeSubmitSerializer,
    ConfidenceCreateSerializer,
    ConfidenceRatingSerializer,
    DailyChallengeSerializer,
)
from apps.challenges.services import (
    get_challenge_or_404,
    get_or_assign_today_challenge,
    save_confidence,
    submit_challenge,
)
from apps.core.responses import success_response


class TodayChallengeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        daily = get_or_assign_today_challenge(user=request.user)
        return success_response(DailyChallengeSerializer(daily).data)


class ChallengeDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, challenge_id: int) -> Response:
        challenge = get_challenge_or_404(challenge_id)
        return success_response(ChallengeSerializer(challenge).data)


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

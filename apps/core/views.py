from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework import status

from apps.core.responses import success_response
from apps.core.serializers import WaitlistSignupSerializer


class HealthView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request: Request) -> Response:
        return success_response(
            {
                "status": "ok",
                "service": "skillforge-api",
                "version": "v1",
            },
            message="Healthy",
        )


class WaitlistRateThrottle(AnonRateThrottle):
    scope = "waitlist"


class WaitlistJoinView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [WaitlistRateThrottle]

    def post(self, request: Request) -> Response:
        serializer = WaitlistSignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_response(
            {"email": serializer.validated_data["email"]},
            message="You're on the list.",
            status=status.HTTP_201_CREATED,
        )

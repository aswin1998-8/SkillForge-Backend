from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.responses import success_response


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

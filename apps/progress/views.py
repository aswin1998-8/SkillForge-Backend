from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.responses import success_response
from apps.progress.services.dashboard import build_dashboard
from apps.progress.services.roadmap import build_roadmap


class DashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        return success_response(build_dashboard(request.user))


class RoadmapView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        return success_response(build_roadmap(request.user))

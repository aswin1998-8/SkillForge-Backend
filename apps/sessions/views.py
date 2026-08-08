from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.responses import success_response
from apps.sessions.serializers import LearningSessionSerializer
from apps.sessions.services import get_session_for_user, list_sessions


class SessionListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        sessions = list_sessions(request.user)
        return success_response(LearningSessionSerializer(sessions, many=True).data)


class SessionDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, session_id: int) -> Response:
        session = get_session_for_user(user=request.user, session_id=session_id)
        return success_response(LearningSessionSerializer(session).data)

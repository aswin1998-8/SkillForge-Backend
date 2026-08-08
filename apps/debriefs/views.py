from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.responses import success_response
from apps.debriefs.serializers import DebriefAnswerCreateSerializer, DebriefSessionSerializer
from apps.debriefs.services import answer_debrief_question, get_debrief_for_user


class DebriefDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, session_id: int) -> Response:
        session = get_debrief_for_user(user=request.user, session_id=session_id)
        return success_response(DebriefSessionSerializer(session).data)


class DebriefAnswerView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request, session_id: int) -> Response:
        serializer = DebriefAnswerCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session = answer_debrief_question(
            user=request.user,
            session_id=session_id,
            answer_text=serializer.validated_data["answer_text"],
        )
        session = get_debrief_for_user(user=request.user, session_id=session.id)
        return success_response(
            DebriefSessionSerializer(session).data,
            message="Answer recorded",
        )

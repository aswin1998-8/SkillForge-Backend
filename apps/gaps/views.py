from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.responses import success_response
from apps.gaps.serializers import UserSkillGapSerializer
from apps.gaps.services import list_user_gaps


class UserSkillGapListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        include_closed = str(request.query_params.get("include_closed", "")).lower() in {
            "1",
            "true",
            "yes",
        }
        gaps = list_user_gaps(request.user, include_closed=include_closed)
        return success_response(UserSkillGapSerializer(gaps, many=True).data)

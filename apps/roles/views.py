from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.responses import success_response
from apps.roles.models import Role, Skill
from apps.roles.serializers import RoleSerializer, SkillSerializer


class RoleListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        roles = Role.objects.prefetch_related("role_skills__skill").all()
        return success_response(RoleSerializer(roles, many=True).data)


class SkillListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        skills = Skill.objects.all()
        return success_response(SkillSerializer(skills, many=True).data)

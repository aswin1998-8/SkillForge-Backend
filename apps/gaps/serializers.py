from __future__ import annotations

from rest_framework import serializers

from apps.gaps.models import GapEvidence, UserSkillGap
from apps.roles.serializers import SkillSerializer


class GapEvidenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = GapEvidence
        fields = ("id", "source_type", "source_id", "summary", "created_at")


class UserSkillGapSerializer(serializers.ModelSerializer):
    skill = SkillSerializer(read_only=True)
    evidence = GapEvidenceSerializer(many=True, read_only=True)

    class Meta:
        model = UserSkillGap
        fields = ("id", "skill", "status", "evidence", "created_at", "updated_at")

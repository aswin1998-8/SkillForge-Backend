from __future__ import annotations

from rest_framework import serializers

from apps.sessions.models import LearningSession


class LearningSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = LearningSession
        fields = (
            "id",
            "session_type",
            "reference_id",
            "title",
            "summary",
            "created_at",
        )

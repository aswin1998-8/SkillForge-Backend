from __future__ import annotations

from rest_framework import serializers

from apps.sessions.models import LearningSession
from apps.sessions.services import session_scores


class LearningSessionSerializer(serializers.ModelSerializer):
    score = serializers.SerializerMethodField()

    class Meta:
        model = LearningSession
        fields = (
            "id",
            "session_type",
            "reference_id",
            "title",
            "summary",
            "created_at",
            "score",
        )

    def get_score(self, obj: LearningSession) -> int | None:
        cached = self.context.get("scores")
        if cached is not None:
            return cached.get(obj.id)
        return session_scores([obj]).get(obj.id)

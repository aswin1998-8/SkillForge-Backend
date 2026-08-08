from __future__ import annotations

from rest_framework import serializers

from apps.debriefs.models import (
    DebriefAnswer,
    DebriefEvaluation,
    DebriefQuestion,
    DebriefSession,
)


class DebriefAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = DebriefAnswer
        fields = ("answer_text", "created_at")


class DebriefQuestionSerializer(serializers.ModelSerializer):
    answer = DebriefAnswerSerializer(read_only=True)

    class Meta:
        model = DebriefQuestion
        fields = ("id", "order", "prompt_text", "status", "answer", "created_at")


class DebriefEvaluationSerializer(serializers.ModelSerializer):
    class Meta:
        model = DebriefEvaluation
        fields = (
            "strengths",
            "gaps",
            "next_focus",
            "score",
            "summary",
            "created_at",
        )


class DebriefSessionSerializer(serializers.ModelSerializer):
    questions = DebriefQuestionSerializer(many=True, read_only=True)
    evaluation = DebriefEvaluationSerializer(read_only=True)
    attempt_id = serializers.IntegerField(source="attempt.id", read_only=True)
    challenge_title = serializers.CharField(source="attempt.challenge.title", read_only=True)

    class Meta:
        model = DebriefSession
        fields = (
            "id",
            "attempt_id",
            "challenge_title",
            "status",
            "max_questions",
            "questions",
            "evaluation",
            "created_at",
            "updated_at",
        )


class DebriefAnswerCreateSerializer(serializers.Serializer):
    answer_text = serializers.CharField()

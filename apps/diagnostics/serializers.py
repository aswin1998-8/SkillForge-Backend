from __future__ import annotations

from rest_framework import serializers

from apps.diagnostics.models import (
    Diagnostic,
    DiagnosticAnswer,
    DiagnosticAttempt,
    DiagnosticQuestion,
    DiagnosticResult,
)
from apps.roles.serializers import SkillSerializer


class DiagnosticQuestionSerializer(serializers.ModelSerializer):
    skill = SkillSerializer(read_only=True)

    class Meta:
        model = DiagnosticQuestion
        fields = (
            "id",
            "text",
            "question_type",
            "skill",
            "difficulty",
            "ordering",
        )


class DiagnosticSerializer(serializers.ModelSerializer):
    questions = DiagnosticQuestionSerializer(many=True, read_only=True)

    class Meta:
        model = Diagnostic
        fields = ("id", "title", "description", "is_active", "questions")


class DiagnosticAnswerSerializer(serializers.ModelSerializer):
    question_id = serializers.IntegerField(source="question.id", read_only=True)

    class Meta:
        model = DiagnosticAnswer
        fields = ("id", "question_id", "answer_text", "updated_at")


class DiagnosticResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = DiagnosticResult
        fields = (
            "strengths",
            "gaps",
            "evidence",
            "skill_findings",
            "recommended_focus",
            "created_at",
        )


class DiagnosticAttemptSerializer(serializers.ModelSerializer):
    answers = DiagnosticAnswerSerializer(many=True, read_only=True)
    result = DiagnosticResultSerializer(read_only=True)
    diagnostic_id = serializers.IntegerField(source="diagnostic.id", read_only=True)
    diagnostic_title = serializers.CharField(source="diagnostic.title", read_only=True)

    class Meta:
        model = DiagnosticAttempt
        fields = (
            "id",
            "diagnostic_id",
            "diagnostic_title",
            "status",
            "started_at",
            "completed_at",
            "answers",
            "result",
        )


class SaveAnswersSerializer(serializers.Serializer):
    answers = serializers.ListField(child=serializers.DictField(), allow_empty=False)

    def validate_answers(self, value: list) -> list:
        cleaned: list[dict] = []
        for item in value:
            if "question_id" not in item:
                raise serializers.ValidationError("Each answer requires question_id.")
            cleaned.append(
                {
                    "question_id": int(item["question_id"]),
                    "answer_text": str(item.get("answer_text") or ""),
                }
            )
        return cleaned

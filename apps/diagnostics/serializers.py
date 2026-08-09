from __future__ import annotations

from rest_framework import serializers

from apps.diagnostics.models import (
    Diagnostic,
    DiagnosticAnswer,
    DiagnosticAttempt,
    DiagnosticQuestion,
    DiagnosticResult,
    DiagnosticRoadmapItem,
    DiagnosticSession,
    DiagnosticTurn,
    SessionAnswer,
    SessionQuestion,
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


class DiagnosticTurnSerializer(serializers.ModelSerializer):
    skill = SkillSerializer(read_only=True)
    prompt_text = serializers.SerializerMethodField()

    class Meta:
        model = DiagnosticTurn
        fields = (
            "id",
            "ordering",
            "stage",
            "skill",
            "difficulty",
            "question_type",
            "prompt_text",
            "question_payload",
            "answer_text",
            "evaluation",
            "status",
            "created_at",
            "updated_at",
        )

    def get_prompt_text(self, obj: DiagnosticTurn) -> str:
        return (obj.question_payload or {}).get("prompt_text") or ""


class DiagnosticAttemptSerializer(serializers.ModelSerializer):
    answers = DiagnosticAnswerSerializer(many=True, read_only=True)
    turns = DiagnosticTurnSerializer(many=True, read_only=True)
    result = DiagnosticResultSerializer(read_only=True)
    diagnostic_id = serializers.IntegerField(source="diagnostic.id", read_only=True)
    diagnostic_title = serializers.CharField(source="diagnostic.title", read_only=True)
    active_turn = serializers.SerializerMethodField()

    class Meta:
        model = DiagnosticAttempt
        fields = (
            "id",
            "diagnostic_id",
            "diagnostic_title",
            "status",
            "goal",
            "current_stage",
            "stage_history",
            "active_turn_id",
            "active_turn",
            "skill_scores",
            "transfer_report",
            "gap_report",
            "started_at",
            "completed_at",
            "answers",
            "turns",
            "result",
        )

    def get_active_turn(self, obj: DiagnosticAttempt):
        turn = None
        if obj.active_turn_id:
            turn = next((t for t in obj.turns.all() if t.id == obj.active_turn_id), None)
        if turn is None:
            turn = next(
                (t for t in obj.turns.all() if t.status == DiagnosticTurn.Status.ASKED),
                None,
            )
        if turn is None:
            return None
        return DiagnosticTurnSerializer(turn).data


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


class SubmitTurnSerializer(serializers.Serializer):
    turn_id = serializers.IntegerField()
    answer_text = serializers.CharField(allow_blank=True, max_length=12000)


class SessionAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = SessionAnswer
        fields = ("id", "answer_text", "exposure_confirmed", "submitted_at")


class SessionQuestionSerializer(serializers.ModelSerializer):
    answer = SessionAnswerSerializer(read_only=True)
    question_type = serializers.SerializerMethodField()

    class Meta:
        model = SessionQuestion
        fields = (
            "id",
            "block",
            "stage",
            "order",
            "competency_area",
            "question_text",
            "question_type",
            "metadata",
            "status",
            "answer",
            "created_at",
        )

    def get_question_type(self, obj) -> str:
        return (obj.metadata or {}).get("question_type") or "FREE_TEXT"


class DiagnosticRoadmapItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = DiagnosticRoadmapItem
        fields = (
            "id",
            "challenge_modality",
            "topic",
            "priority",
            "challenge",
            "created_at",
        )


class DiagnosticSessionSerializer(serializers.ModelSerializer):
    questions = serializers.SerializerMethodField()
    current_questions = serializers.SerializerMethodField()
    roadmap_items = DiagnosticRoadmapItemSerializer(many=True, read_only=True)
    low_stakes = serializers.BooleanField(read_only=True)
    target_taxonomy_id = serializers.IntegerField(read_only=True, allow_null=True)
    target_taxonomy_name = serializers.SerializerMethodField()
    selected_domains = serializers.SerializerMethodField()

    class Meta:
        model = DiagnosticSession
        fields = (
            "id",
            "goal",
            "target_role",
            "target_taxonomy_id",
            "target_taxonomy_name",
            "selected_domains",
            "assessment_competencies",
            "current_role",
            "status",
            "current_block",
            "current_stage",
            "low_stakes",
            "synthesis",
            "error",
            "questions",
            "current_questions",
            "roadmap_items",
            "created_at",
            "updated_at",
            "completed_at",
        )

    def get_target_taxonomy_name(self, obj) -> str | None:
        tax = getattr(obj, "target_taxonomy", None)
        return tax.role_name if tax is not None else None

    def get_selected_domains(self, obj) -> list[dict]:
        return [
            {"slug": d.slug, "domain_name": d.domain_name}
            for d in obj.selected_domains.all()
        ]

    def get_questions(self, obj):
        return SessionQuestionSerializer(obj.questions.all(), many=True).data

    def get_current_questions(self, obj):
        if not obj.current_block or not obj.current_stage:
            return []
        qs = obj.questions.filter(
            block=obj.current_block,
            stage=obj.current_stage,
            status=SessionQuestion.Status.ASKED,
        ).order_by("order")
        return SessionQuestionSerializer(qs, many=True).data


class StartDiagnosticSessionSerializer(serializers.Serializer):
    goal = serializers.ChoiceField(choices=["sharpen_current", "switch_role"])
    domain_slugs = serializers.ListField(
        child=serializers.CharField(max_length=64),
        required=False,
        allow_empty=True,
    )

class SubmitSessionAnswersSerializer(serializers.Serializer):
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

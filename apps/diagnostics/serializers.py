from __future__ import annotations

from rest_framework import serializers

from apps.diagnostics.models import (
    CodingTestCase,
    DiagnosticRoadmapItem,
    DiagnosticSession,
    FrameworkTopic,
    FundamentalsTopic,
    Question,
    QuestionChoice,
    QuickScoreAttempt,
    QuickScoreChoice,
    QuickScoreQuestion,
    ReferenceAnswer,
    SessionAnswer,
    SessionQuestion,
)


class FrameworkTopicSerializer(serializers.ModelSerializer):
    fundamentals_language = serializers.CharField(
        source="fundamentals_topic.language_family",
        read_only=True,
    )

    class Meta:
        model = FrameworkTopic
        fields = (
            "id",
            "framework_name",
            "fundamentals_language",
            "competency_areas",
        )


class QuestionChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionChoice
        fields = ("id", "choice_text")


class CodingTestCasePublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = CodingTestCase
        fields = ("id", "input", "order")


class SessionAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = SessionAnswer
        fields = (
            "id",
            "answer_text",
            "choice_id",
            "is_correct",
            "confidence_rating",
            "self_rated_alignment",
            "grading_detail",
            "submitted_at",
            "revealed_at",
            "self_rated_at",
        )


class SessionQuestionSerializer(serializers.ModelSerializer):
    answer = SessionAnswerSerializer(read_only=True)
    question_text = serializers.CharField(source="content_question.question_text")
    modality = serializers.CharField(source="content_question.modality")
    difficulty_tier = serializers.IntegerField(source="content_question.difficulty_tier")
    language = serializers.CharField(source="content_question.language")
    choices = serializers.SerializerMethodField()
    test_cases = serializers.SerializerMethodField()

    class Meta:
        model = SessionQuestion
        fields = (
            "id",
            "stage",
            "order",
            "competency_area",
            "status",
            "question_text",
            "modality",
            "difficulty_tier",
            "language",
            "choices",
            "test_cases",
            "answer",
            "created_at",
        )

    def get_choices(self, obj: SessionQuestion) -> list[dict]:
        if obj.content_question.modality != Question.Modality.FOUNDATIONAL:
            return []
        return QuestionChoiceSerializer(
            obj.content_question.choices.all(),
            many=True,
        ).data

    def get_test_cases(self, obj: SessionQuestion) -> list[dict]:
        modality = obj.content_question.modality
        if modality not in {Question.Modality.CODING, Question.Modality.FIND_ISSUES}:
            return []
        visible = obj.content_question.test_cases.filter(is_hidden=False)
        return CodingTestCasePublicSerializer(visible, many=True).data


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
    skipped_easy_areas = serializers.SerializerMethodField()
    question_budget = serializers.SerializerMethodField()
    roadmap_items = DiagnosticRoadmapItemSerializer(many=True, read_only=True)
    selected_frameworks = serializers.SerializerMethodField()

    class Meta:
        model = DiagnosticSession
        fields = (
            "id",
            "goal",
            "target_role",
            "selected_frameworks",
            "assessment_competencies",
            "current_role",
            "status",
            "current_stage",
            "selection_log",
            "synthesis",
            "error",
            "difficulty_bump",
            "questions",
            "current_questions",
            "skipped_easy_areas",
            "question_budget",
            "roadmap_items",
            "created_at",
            "updated_at",
            "completed_at",
        )

    def get_selected_frameworks(self, obj) -> list[dict]:
        return [
            {
                "slug": fw.framework_name,
                "name": fw.get_framework_name_display(),
            }
            for fw in obj.selected_frameworks.all()
        ]

    def get_questions(self, obj):
        return SessionQuestionSerializer(obj.questions.all(), many=True).data

    def get_current_questions(self, obj):
        qs = obj.questions.filter(status=SessionQuestion.Status.ASKED).order_by("order")
        return SessionQuestionSerializer(qs, many=True).data

    def get_skipped_easy_areas(self, obj) -> list[str]:
        from apps.diagnostics.adaptive_selector import skipped_easy_areas

        return skipped_easy_areas(obj)

    def get_question_budget(self, obj) -> int:
        from django.conf import settings

        return int(getattr(settings, "DIAGNOSTIC_SESSION_QUESTION_BUDGET", 15))


class StartDiagnosticSessionSerializer(serializers.Serializer):
    goal = serializers.ChoiceField(choices=["sharpen_current", "switch_role"])
    framework_slugs = serializers.ListField(
        child=serializers.CharField(max_length=64),
        allow_empty=False,
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
                    "choice_id": int(item["choice_id"]) if item.get("choice_id") else None,
                    "confidence_rating": (
                        int(item["confidence_rating"])
                        if item.get("confidence_rating") is not None
                        else None
                    ),
                }
            )
        return cleaned


class SelfRateAnswerSerializer(serializers.Serializer):
    rubric_alignment = serializers.DictField(child=serializers.CharField())


class RunTestsSerializer(serializers.Serializer):
    question_id = serializers.IntegerField()
    code = serializers.CharField(allow_blank=False)


class QuickScoreChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuickScoreChoice
        fields = ("id", "choice_text")


class QuickScoreQuestionSerializer(serializers.ModelSerializer):
    choices = QuickScoreChoiceSerializer(many=True, read_only=True)

    class Meta:
        model = QuickScoreQuestion
        fields = (
            "id",
            "track",
            "competency_area",
            "question_text",
            "weight",
            "order",
            "choices",
        )


class QuickScoreAttemptSerializer(serializers.ModelSerializer):
    band_label = serializers.SerializerMethodField()
    track_label = serializers.CharField(source="get_track_display", read_only=True)

    class Meta:
        model = QuickScoreAttempt
        fields = (
            "id",
            "track",
            "track_label",
            "total_score",
            "band",
            "band_label",
            "paragraph_text",
            "highlight_areas",
            "created_at",
        )

    def get_band_label(self, obj) -> str:
        from apps.diagnostics.quick_score import BAND_LABELS

        return BAND_LABELS.get(obj.band, obj.band)


class SubmitQuickScoreSerializer(serializers.Serializer):
    track = serializers.ChoiceField(choices=["frontend", "backend"])
    answers = serializers.ListField(child=serializers.DictField(), allow_empty=False)

    def validate_answers(self, value: list) -> list:
        cleaned = []
        for item in value:
            if "question_id" not in item or "choice_id" not in item:
                raise serializers.ValidationError(
                    "Each answer requires question_id and choice_id."
                )
            cleaned.append(
                {
                    "question_id": int(item["question_id"]),
                    "choice_id": int(item["choice_id"]),
                }
            )
        return cleaned

from django.contrib import admin
from django.core.exceptions import ValidationError

from apps.diagnostics.models import (
    CodingTestCase,
    DiagnosticRoadmapItem,
    DiagnosticSession,
    FrameworkTopic,
    FundamentalsTopic,
    MarketEvidence,
    Question,
    QuestionChoice,
    QuickScoreAttempt,
    QuickScoreChoice,
    QuickScoreParagraph,
    QuickScoreQuestion,
    ReferenceAnswer,
    SessionAnswer,
    SessionQuestion,
    SkillAreaFragment,
)


class QuestionChoiceInline(admin.TabularInline):
    model = QuestionChoice
    extra = 1


class CodingTestCaseInline(admin.TabularInline):
    model = CodingTestCase
    extra = 1


class ReferenceAnswerInline(admin.StackedInline):
    model = ReferenceAnswer
    max_num = 1
    extra = 0


@admin.register(FundamentalsTopic)
class FundamentalsTopicAdmin(admin.ModelAdmin):
    list_display = ("language_family", "competency_count", "created_at")
    search_fields = ("language_family",)

    @admin.display(description="Competencies")
    def competency_count(self, obj: FundamentalsTopic) -> int:
        return len(obj.clean_competency_areas())

    def save_model(self, request, obj, form, change):
        areas = obj.clean_competency_areas()
        if not areas:
            raise ValidationError(
                "competency_areas must be a non-empty list of non-empty strings."
            )
        obj.competency_areas = areas
        super().save_model(request, obj, form, change)


@admin.register(FrameworkTopic)
class FrameworkTopicAdmin(admin.ModelAdmin):
    list_display = ("framework_name", "fundamentals_topic", "competency_count", "created_at")
    list_filter = ("fundamentals_topic",)
    search_fields = ("framework_name",)

    @admin.display(description="Competencies")
    def competency_count(self, obj: FrameworkTopic) -> int:
        return len(obj.clean_competency_areas())

    def save_model(self, request, obj, form, change):
        areas = obj.clean_competency_areas()
        if not areas:
            raise ValidationError(
                "competency_areas must be a non-empty list of non-empty strings."
            )
        obj.competency_areas = areas
        super().save_model(request, obj, form, change)


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "modality",
        "competency_area",
        "difficulty_tier",
        "framework_topic",
        "fundamentals_topic",
        "is_active",
    )
    list_filter = ("modality", "difficulty_tier", "is_active", "framework_topic")
    search_fields = ("question_text", "competency_area")
    inlines = [QuestionChoiceInline, CodingTestCaseInline, ReferenceAnswerInline]


class SessionQuestionInline(admin.TabularInline):
    model = SessionQuestion
    extra = 0
    readonly_fields = ("created_at",)


@admin.register(DiagnosticSession)
class DiagnosticSessionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "goal",
        "target_role",
        "status",
        "current_stage",
        "created_at",
    )
    list_filter = ("goal", "status", "current_stage")
    search_fields = ("user__email", "target_role")
    inlines = [SessionQuestionInline]


@admin.register(SessionQuestion)
class SessionQuestionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "session",
        "stage",
        "order",
        "competency_area",
        "status",
    )
    list_filter = ("stage", "status")


@admin.register(SessionAnswer)
class SessionAnswerAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "question",
        "is_correct",
        "confidence_rating",
        "submitted_at",
    )
    list_filter = ("is_correct",)


@admin.register(DiagnosticRoadmapItem)
class DiagnosticRoadmapItemAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "session",
        "priority",
        "topic",
        "challenge_modality",
        "status",
    )
    list_filter = ("challenge_modality", "status")


class QuickScoreChoiceInline(admin.TabularInline):
    model = QuickScoreChoice
    extra = 2


@admin.register(QuickScoreQuestion)
class QuickScoreQuestionAdmin(admin.ModelAdmin):
    list_display = ("id", "track", "competency_area", "order", "is_active")
    list_filter = ("track", "is_active")
    inlines = [QuickScoreChoiceInline]


@admin.register(QuickScoreParagraph)
class QuickScoreParagraphAdmin(admin.ModelAdmin):
    list_display = ("track", "band")
    list_filter = ("track", "band")


@admin.register(QuickScoreAttempt)
class QuickScoreAttemptAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "track", "total_score", "band", "created_at")
    list_filter = ("track", "band")


@admin.register(SkillAreaFragment)
class SkillAreaFragmentAdmin(admin.ModelAdmin):
    list_display = ("competency_area", "level")
    list_filter = ("level",)


@admin.register(MarketEvidence)
class MarketEvidenceAdmin(admin.ModelAdmin):
    list_display = ("competency_area", "source_name", "source_date", "is_active")
    list_filter = ("is_active",)

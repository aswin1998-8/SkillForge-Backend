from django.contrib import admin

from apps.challenges.models import (
    AnalyticsEvent,
    Challenge,
    ChallengeAttempt,
    ChallengeDebrief,
    ChallengeFollowUp,
    ChallengeModelAnswer,
    ChallengeRubricItem,
    ChallengeSkill,
    ConfidenceRating,
    DailyChallenge,
    Submission,
)


class ChallengeSkillInline(admin.TabularInline):
    model = ChallengeSkill
    extra = 0


class RubricInline(admin.TabularInline):
    model = ChallengeRubricItem
    extra = 1


class ModelAnswerInline(admin.StackedInline):
    model = ChallengeModelAnswer
    extra = 0
    max_num = 1


@admin.register(Challenge)
class ChallengeAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "modality", "difficulty", "is_active")
    list_filter = ("modality", "is_active", "difficulty")
    prepopulated_fields = {"slug": ("title",)}
    search_fields = ("title", "slug")
    inlines = [ChallengeSkillInline, ModelAnswerInline, RubricInline]


@admin.register(ChallengeRubricItem)
class ChallengeRubricItemAdmin(admin.ModelAdmin):
    list_display = ("id", "challenge", "order", "text")
    search_fields = ("text", "challenge__title")


@admin.register(ChallengeFollowUp)
class ChallengeFollowUpAdmin(admin.ModelAdmin):
    list_display = ("id", "rubric_item", "order", "question_text")


@admin.register(DailyChallenge)
class DailyChallengeAdmin(admin.ModelAdmin):
    list_display = ("user", "date", "challenge", "status")
    list_filter = ("status", "date")
    search_fields = ("user__email", "challenge__title")


class SubmissionInline(admin.StackedInline):
    model = Submission
    extra = 0


class ConfidenceInline(admin.StackedInline):
    model = ConfidenceRating
    extra = 0


@admin.register(ChallengeAttempt)
class ChallengeAttemptAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "challenge", "status", "started_at")
    list_filter = ("status",)
    search_fields = ("user__email", "challenge__title")
    inlines = [SubmissionInline, ConfidenceInline]


@admin.register(ChallengeDebrief)
class ChallengeDebriefAdmin(admin.ModelAdmin):
    list_display = ("id", "attempt", "status", "checklist_score", "completed_at")
    list_filter = ("status",)


admin.site.register(ChallengeSkill)
admin.site.register(Submission)
admin.site.register(ConfidenceRating)
admin.site.register(AnalyticsEvent)
admin.site.register(ChallengeModelAnswer)

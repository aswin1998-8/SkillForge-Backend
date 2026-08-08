from django.contrib import admin

from apps.challenges.models import (
    Challenge,
    ChallengeAttempt,
    ChallengeSkill,
    ConfidenceRating,
    DailyChallenge,
    Submission,
)


class ChallengeSkillInline(admin.TabularInline):
    model = ChallengeSkill
    extra = 0


@admin.register(Challenge)
class ChallengeAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "modality", "difficulty", "is_active")
    list_filter = ("modality", "is_active", "difficulty")
    prepopulated_fields = {"slug": ("title",)}
    search_fields = ("title", "slug")
    inlines = [ChallengeSkillInline]


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


admin.site.register(ChallengeSkill)
admin.site.register(Submission)
admin.site.register(ConfidenceRating)

from django.contrib import admin

from apps.debriefs.models import (
    DebriefAnswer,
    DebriefEvaluation,
    DebriefQuestion,
    DebriefSession,
)


class DebriefQuestionInline(admin.TabularInline):
    model = DebriefQuestion
    extra = 0


@admin.register(DebriefSession)
class DebriefSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "attempt", "status", "max_questions", "created_at")
    list_filter = ("status",)
    inlines = [DebriefQuestionInline]


@admin.register(DebriefQuestion)
class DebriefQuestionAdmin(admin.ModelAdmin):
    list_display = ("session", "order", "status")
    list_filter = ("status",)


@admin.register(DebriefAnswer)
class DebriefAnswerAdmin(admin.ModelAdmin):
    list_display = ("question", "created_at")


@admin.register(DebriefEvaluation)
class DebriefEvaluationAdmin(admin.ModelAdmin):
    list_display = ("session", "score", "next_focus", "created_at")

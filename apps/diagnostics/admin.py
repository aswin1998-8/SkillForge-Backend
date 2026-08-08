from django.contrib import admin

from apps.diagnostics.models import (
    Diagnostic,
    DiagnosticAnswer,
    DiagnosticAttempt,
    DiagnosticQuestion,
    DiagnosticResult,
)


class DiagnosticQuestionInline(admin.TabularInline):
    model = DiagnosticQuestion
    extra = 0


@admin.register(Diagnostic)
class DiagnosticAdmin(admin.ModelAdmin):
    list_display = ("title", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("title",)
    inlines = [DiagnosticQuestionInline]


@admin.register(DiagnosticQuestion)
class DiagnosticQuestionAdmin(admin.ModelAdmin):
    list_display = ("diagnostic", "ordering", "question_type", "skill", "difficulty")
    list_filter = ("question_type", "diagnostic")


class DiagnosticAnswerInline(admin.TabularInline):
    model = DiagnosticAnswer
    extra = 0


@admin.register(DiagnosticAttempt)
class DiagnosticAttemptAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "diagnostic", "status", "started_at", "completed_at")
    list_filter = ("status",)
    search_fields = ("user__email", "diagnostic__title")
    inlines = [DiagnosticAnswerInline]


@admin.register(DiagnosticResult)
class DiagnosticResultAdmin(admin.ModelAdmin):
    list_display = ("attempt", "recommended_focus", "created_at")

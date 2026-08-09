from django.contrib import admin

from django.core.exceptions import ValidationError

from apps.diagnostics.models import (
    Diagnostic,
    DiagnosticAnswer,
    DiagnosticAttempt,
    DiagnosticQuestion,
    DiagnosticResult,
    DiagnosticRoadmapItem,
    DiagnosticSession,
    DiagnosticTurn,
    DomainTaxonomy,
    RoleTaxonomy,
    SessionAnswer,
    SessionQuestion,
    SkillEvidence,
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


class DiagnosticTurnInline(admin.TabularInline):
    model = DiagnosticTurn
    extra = 0


@admin.register(DiagnosticAttempt)
class DiagnosticAttemptAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "diagnostic",
        "status",
        "goal",
        "current_stage",
        "started_at",
        "completed_at",
    )
    list_filter = ("status", "goal", "current_stage")
    search_fields = ("user__email", "diagnostic__title")
    inlines = [DiagnosticAnswerInline, DiagnosticTurnInline]


@admin.register(DiagnosticTurn)
class DiagnosticTurnAdmin(admin.ModelAdmin):
    list_display = ("id", "attempt", "ordering", "stage", "skill", "status")
    list_filter = ("stage", "status")


@admin.register(SkillEvidence)
class SkillEvidenceAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "skill", "stage", "score", "source_type", "created_at")
    list_filter = ("stage", "source_type")


@admin.register(DiagnosticResult)
class DiagnosticResultAdmin(admin.ModelAdmin):
    list_display = ("attempt", "recommended_focus", "created_at")


@admin.register(RoleTaxonomy)
class RoleTaxonomyAdmin(admin.ModelAdmin):
    list_display = ("role_name", "competency_count", "updated_at")
    search_fields = ("role_name",)

    @admin.display(description="Competencies")
    def competency_count(self, obj: RoleTaxonomy) -> int:
        areas = obj.clean_competency_areas()
        return len(areas)

    def save_model(self, request, obj, form, change):
        areas = obj.clean_competency_areas()
        if not areas:
            raise ValidationError(
                "competency_areas must be a non-empty list of non-empty strings."
            )
        obj.competency_areas = areas
        super().save_model(request, obj, form, change)


@admin.register(DomainTaxonomy)
class DomainTaxonomyAdmin(admin.ModelAdmin):
    list_display = ("slug", "domain_name", "competency_count", "updated_at")
    search_fields = ("slug", "domain_name")

    @admin.display(description="Competencies")
    def competency_count(self, obj: DomainTaxonomy) -> int:
        return len(obj.clean_competency_areas())

    def save_model(self, request, obj, form, change):
        areas = obj.clean_competency_areas()
        if not areas:
            raise ValidationError(
                "competency_areas must be a non-empty list of non-empty strings."
            )
        obj.competency_areas = areas
        obj.slug = (obj.slug or "").strip().lower()
        super().save_model(request, obj, form, change)


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
        "target_taxonomy",
        "status",
        "current_block",
        "current_stage",
        "created_at",
    )
    list_filter = ("goal", "status", "current_block")
    search_fields = ("user__email", "target_role")
    inlines = [SessionQuestionInline]


@admin.register(SessionQuestion)
class SessionQuestionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "session",
        "block",
        "stage",
        "order",
        "competency_area",
        "status",
    )
    list_filter = ("block", "stage", "status")


@admin.register(SessionAnswer)
class SessionAnswerAdmin(admin.ModelAdmin):
    list_display = ("id", "question", "exposure_confirmed", "submitted_at")


@admin.register(DiagnosticRoadmapItem)
class DiagnosticRoadmapItemAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "session", "priority", "topic", "challenge_modality")
    list_filter = ("challenge_modality",)

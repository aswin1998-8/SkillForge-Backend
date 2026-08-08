from django.contrib import admin

from apps.gaps.models import GapEvidence, UserSkillGap


class GapEvidenceInline(admin.TabularInline):
    model = GapEvidence
    extra = 0
    readonly_fields = ("created_at",)


@admin.register(UserSkillGap)
class UserSkillGapAdmin(admin.ModelAdmin):
    list_display = ("user", "skill", "status", "updated_at")
    list_filter = ("status",)
    search_fields = ("user__email", "skill__name", "skill__slug")
    inlines = [GapEvidenceInline]


@admin.register(GapEvidence)
class GapEvidenceAdmin(admin.ModelAdmin):
    list_display = ("user_skill_gap", "source_type", "source_id", "created_at")
    list_filter = ("source_type",)

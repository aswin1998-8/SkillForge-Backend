from django.contrib import admin

from apps.roles.models import Role, RoleSkill, Skill


class RoleSkillInline(admin.TabularInline):
    model = RoleSkill
    extra = 0


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name", "slug")
    inlines = [RoleSkillInline]


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name", "slug")


@admin.register(RoleSkill)
class RoleSkillAdmin(admin.ModelAdmin):
    list_display = ("role", "skill", "importance")
    list_filter = ("role",)

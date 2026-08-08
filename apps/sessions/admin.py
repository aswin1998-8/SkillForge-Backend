from django.contrib import admin

from apps.sessions.models import LearningSession


@admin.register(LearningSession)
class LearningSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "session_type", "title", "created_at")
    list_filter = ("session_type",)
    search_fields = ("user__email", "title")

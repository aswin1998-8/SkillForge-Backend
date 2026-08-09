from django.contrib import admin

from apps.ai.models import AIRequestLog


@admin.register(AIRequestLog)
class AIRequestLogAdmin(admin.ModelAdmin):
    list_display = ("id", "provider", "operation", "status", "latency_ms", "created_at")
    list_filter = ("provider", "status", "operation")
    search_fields = ("operation", "error", "model")

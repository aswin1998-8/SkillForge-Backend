"""AI request logging (observability only; no secrets)."""

from __future__ import annotations

from django.db import models


class AIRequestLog(models.Model):
    provider = models.CharField(max_length=32, db_index=True)
    model = models.CharField(max_length=128, blank=True, default="")
    operation = models.CharField(max_length=64, db_index=True)
    status = models.CharField(max_length=16, default="ok")
    latency_ms = models.PositiveIntegerField(default=0)
    token_usage = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"AIRequestLog<{self.provider}:{self.operation}:{self.status}>"

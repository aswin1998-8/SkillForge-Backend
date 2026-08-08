"""Learning session history models."""

from __future__ import annotations

from django.conf import settings
from django.db import models


class LearningSession(models.Model):
    class SessionType(models.TextChoices):
        DIAGNOSTIC = "DIAGNOSTIC", "Diagnostic"
        CHALLENGE = "CHALLENGE", "Challenge"
        DEBRIEF = "DEBRIEF", "Debrief"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="learning_sessions",
    )
    session_type = models.CharField(max_length=32, choices=SessionType.choices)
    reference_id = models.PositiveIntegerField()
    title = models.CharField(max_length=255)
    summary = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["session_type", "reference_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.session_type}:{self.title}"

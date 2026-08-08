"""User skill gap tracking models."""

from __future__ import annotations

from django.conf import settings
from django.db import models


class UserSkillGap(models.Model):
    class Status(models.TextChoices):
        NOT_STARTED = "NOT_STARTED", "Not started"
        IN_PROGRESS = "IN_PROGRESS", "In progress"
        CLOSED = "CLOSED", "Closed"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="skill_gaps",
    )
    skill = models.ForeignKey(
        "roles.Skill",
        on_delete=models.CASCADE,
        related_name="user_gaps",
    )
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.NOT_STARTED,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "skill")
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return f"Gap<{self.user_id}:{self.skill.slug}:{self.status}>"


class GapEvidence(models.Model):
    user_skill_gap = models.ForeignKey(
        UserSkillGap,
        on_delete=models.CASCADE,
        related_name="evidence",
    )
    source_type = models.CharField(max_length=64)
    source_id = models.CharField(max_length=64, blank=True, default="")
    summary = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Evidence<{self.source_type}:{self.source_id}>"

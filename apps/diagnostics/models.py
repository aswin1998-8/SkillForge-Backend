"""Diagnostic assessment models."""

from __future__ import annotations

from django.conf import settings
from django.db import models


class Diagnostic(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title"]

    def __str__(self) -> str:
        return self.title


class DiagnosticQuestion(models.Model):
    class QuestionType(models.TextChoices):
        FREE_TEXT = "FREE_TEXT", "Free text"
        CODE = "CODE", "Code"
        MULTIPLE_CHOICE = "MULTIPLE_CHOICE", "Multiple choice"

    diagnostic = models.ForeignKey(
        Diagnostic,
        on_delete=models.CASCADE,
        related_name="questions",
    )
    text = models.TextField()
    question_type = models.CharField(
        max_length=32,
        choices=QuestionType.choices,
        default=QuestionType.FREE_TEXT,
    )
    skill = models.ForeignKey(
        "roles.Skill",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="diagnostic_questions",
    )
    difficulty = models.PositiveSmallIntegerField(default=1)
    ordering = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["ordering", "id"]

    def __str__(self) -> str:
        return f"Q{self.ordering}: {self.text[:40]}"


class DiagnosticAttempt(models.Model):
    class Status(models.TextChoices):
        IN_PROGRESS = "IN_PROGRESS", "In progress"
        SUBMITTED = "SUBMITTED", "Submitted"
        PROCESSING = "PROCESSING", "Processing"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="diagnostic_attempts",
    )
    diagnostic = models.ForeignKey(
        Diagnostic,
        on_delete=models.CASCADE,
        related_name="attempts",
    )
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.IN_PROGRESS,
    )
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self) -> str:
        return f"Attempt<{self.id}:{self.status}>"


class DiagnosticAnswer(models.Model):
    attempt = models.ForeignKey(
        DiagnosticAttempt,
        on_delete=models.CASCADE,
        related_name="answers",
    )
    question = models.ForeignKey(
        DiagnosticQuestion,
        on_delete=models.CASCADE,
        related_name="answers",
    )
    answer_text = models.TextField(blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("attempt", "question")

    def __str__(self) -> str:
        return f"Answer<{self.attempt_id}:{self.question_id}>"


class DiagnosticResult(models.Model):
    attempt = models.OneToOneField(
        DiagnosticAttempt,
        on_delete=models.CASCADE,
        related_name="result",
    )
    strengths = models.JSONField(default=list, blank=True)
    gaps = models.JSONField(default=list, blank=True)
    evidence = models.JSONField(default=list, blank=True)
    skill_findings = models.JSONField(default=list, blank=True)
    recommended_focus = models.CharField(max_length=255, blank=True, default="")
    raw_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Result<{self.attempt_id}>"

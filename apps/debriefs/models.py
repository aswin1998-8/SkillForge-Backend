"""Debrief session models."""

from __future__ import annotations

from django.db import models


class DebriefSession(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ACTIVE = "ACTIVE", "Active"
        EVALUATING = "EVALUATING", "Evaluating"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"

    attempt = models.ForeignKey(
        "challenges.ChallengeAttempt",
        on_delete=models.CASCADE,
        related_name="debrief_sessions",
    )
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.PENDING,
    )
    max_questions = models.PositiveSmallIntegerField(default=5)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Debrief<{self.id}:{self.status}>"


class DebriefQuestion(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ASKED = "ASKED", "Asked"
        ANSWERED = "ANSWERED", "Answered"

    session = models.ForeignKey(
        DebriefSession,
        on_delete=models.CASCADE,
        related_name="questions",
    )
    order = models.PositiveSmallIntegerField()
    prompt_text = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order"]
        unique_together = ("session", "order")

    def __str__(self) -> str:
        return f"DebriefQ<{self.session_id}:{self.order}>"


class DebriefAnswer(models.Model):
    question = models.OneToOneField(
        DebriefQuestion,
        on_delete=models.CASCADE,
        related_name="answer",
    )
    answer_text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"DebriefA<{self.question_id}>"


class DebriefEvaluation(models.Model):
    session = models.OneToOneField(
        DebriefSession,
        on_delete=models.CASCADE,
        related_name="evaluation",
    )
    strengths = models.JSONField(default=list, blank=True)
    gaps = models.JSONField(default=list, blank=True)
    next_focus = models.CharField(max_length=255, blank=True, default="")
    score = models.PositiveSmallIntegerField(default=0)
    summary = models.TextField(blank=True, default="")
    raw_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"DebriefEval<{self.session_id}>"

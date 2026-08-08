"""Challenge and daily assignment models."""

from __future__ import annotations

from django.conf import settings
from django.db import models


class Challenge(models.Model):
    class Modality(models.TextChoices):
        THEORY = "THEORY", "Theory"
        CODING = "CODING", "Coding"
        RESEARCH = "RESEARCH", "Research"
        DEFEND = "DEFEND", "Defend"
        DIAGNOSE = "DIAGNOSE", "Diagnose"
        ARCHITECT = "ARCHITECT", "Architect"
        EXPLAIN_CODE = "EXPLAIN_CODE", "Explain code"
        USE_AI = "USE_AI", "Use AI"
        COMMUNICATE = "COMMUNICATE", "Communicate"

    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    description = models.TextField(blank=True, default="")
    modality = models.CharField(max_length=32, choices=Modality.choices)
    difficulty = models.PositiveSmallIntegerField(default=1)
    estimated_duration_minutes = models.PositiveIntegerField(default=30)
    scenario = models.TextField(blank=True, default="")
    requirements = models.JSONField(default=list, blank=True)
    constraints = models.JSONField(default=list, blank=True)
    workspace_config = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["difficulty", "title"]

    def __str__(self) -> str:
        return self.title


class ChallengeSkill(models.Model):
    challenge = models.ForeignKey(
        Challenge,
        on_delete=models.CASCADE,
        related_name="challenge_skills",
    )
    skill = models.ForeignKey(
        "roles.Skill",
        on_delete=models.CASCADE,
        related_name="challenge_skills",
    )

    class Meta:
        unique_together = ("challenge", "skill")

    def __str__(self) -> str:
        return f"{self.challenge.slug}:{self.skill.slug}"


class DailyChallenge(models.Model):
    class Status(models.TextChoices):
        LOCKED = "LOCKED", "Locked"
        AVAILABLE = "AVAILABLE", "Available"
        IN_PROGRESS = "IN_PROGRESS", "In progress"
        SUBMITTED = "SUBMITTED", "Submitted"
        COMPLETED = "COMPLETED", "Completed"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="daily_challenges",
    )
    challenge = models.ForeignKey(
        Challenge,
        on_delete=models.CASCADE,
        related_name="daily_assignments",
    )
    date = models.DateField()
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.AVAILABLE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "date")
        ordering = ["-date"]

    def __str__(self) -> str:
        return f"Daily<{self.user_id}:{self.date}:{self.challenge.slug}>"


class ChallengeAttempt(models.Model):
    class Status(models.TextChoices):
        IN_PROGRESS = "IN_PROGRESS", "In progress"
        SUBMITTED = "SUBMITTED", "Submitted"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="challenge_attempts",
    )
    challenge = models.ForeignKey(
        Challenge,
        on_delete=models.CASCADE,
        related_name="attempts",
    )
    daily_challenge = models.ForeignKey(
        DailyChallenge,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
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
        return f"ChallengeAttempt<{self.id}:{self.status}>"


class Submission(models.Model):
    attempt = models.OneToOneField(
        ChallengeAttempt,
        on_delete=models.CASCADE,
        related_name="submission",
    )
    text_answer = models.TextField(blank=True, default="")
    code = models.TextField(blank=True, default="")
    architecture_data = models.JSONField(default=dict, blank=True)
    research_data = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Submission<{self.attempt_id}>"


class ConfidenceRating(models.Model):
    attempt = models.OneToOneField(
        ChallengeAttempt,
        on_delete=models.CASCADE,
        related_name="confidence",
    )
    score = models.PositiveSmallIntegerField()
    note = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Confidence<{self.attempt_id}:{self.score}>"

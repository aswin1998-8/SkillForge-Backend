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
        USE_AI = "USE_AI", "Use AI without skill atrophy"
        COMMUNICATE = "COMMUNICATE", "Communicate"
        AUDIT_AI_PR = "AUDIT_AI_PR", "Audit the AI PR"
        EXPLAIN_AI_DIFF = "EXPLAIN_AI_DIFF", "Explain AI diff"
        INHERITED_CODEBASE = "INHERITED_CODEBASE", "Inherited codebase"
        WAR_ROOM = "WAR_ROOM", "War room"

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
    # frontend_mastery | backend_mastery | fe_to_be | be_to_fe
    directions = models.JSONField(default=list, blank=True)
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


class ChallengeModelAnswer(models.Model):
    challenge = models.OneToOneField(
        Challenge,
        on_delete=models.CASCADE,
        related_name="model_answer",
    )
    reference_text = models.TextField()

    def __str__(self) -> str:
        return f"ModelAnswer<{self.challenge_id}>"


class ChallengeRubricItem(models.Model):
    challenge = models.ForeignKey(
        Challenge,
        on_delete=models.CASCADE,
        related_name="rubric_items",
    )
    text = models.TextField()
    order = models.PositiveSmallIntegerField(default=1)
    strength_fragment = models.TextField(blank=True, default="")
    gap_fragment = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["order", "id"]

    def __str__(self) -> str:
        return f"Rubric<{self.challenge_id}:{self.order}>"


class ChallengeFollowUp(models.Model):
    rubric_item = models.ForeignKey(
        ChallengeRubricItem,
        on_delete=models.CASCADE,
        related_name="follow_ups",
    )
    question_text = models.TextField()
    order = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self) -> str:
        return f"FollowUp<{self.rubric_item_id}:{self.order}>"


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
    preferred_difficulty_bias = models.SmallIntegerField(default=0)
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


class ChallengeDebrief(models.Model):
    class Status(models.TextChoices):
        AWAITING_SELF_RATE = "AWAITING_SELF_RATE", "Awaiting self-rate"
        AWAITING_FOLLOWUPS = "AWAITING_FOLLOWUPS", "Awaiting follow-ups"
        COMPLETED = "COMPLETED", "Completed"

    attempt = models.OneToOneField(
        ChallengeAttempt,
        on_delete=models.CASCADE,
        related_name="debrief",
    )
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.AWAITING_SELF_RATE,
    )
    checklist = models.JSONField(default=dict, blank=True)
    follow_up_answers = models.JSONField(default=dict, blank=True)
    strengths = models.JSONField(default=list, blank=True)
    gaps = models.JSONField(default=list, blank=True)
    next_focus = models.TextField(blank=True, default="")
    checklist_score = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"Debrief<{self.attempt_id}:{self.status}>"


class AnalyticsEvent(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="analytics_events",
    )
    name = models.CharField(max_length=64, db_index=True)
    properties = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Event<{self.name}:{self.id}>"

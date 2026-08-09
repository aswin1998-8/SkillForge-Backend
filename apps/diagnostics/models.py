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

    class Goal(models.TextChoices):
        ROLE_SWITCH = "ROLE_SWITCH", "Role switch"
        CURRENT_ROLE = "CURRENT_ROLE", "Current role"

    class Stage(models.TextChoices):
        FOUNDATION = "FOUNDATION", "Foundation"
        SCENARIO = "SCENARIO", "Scenario"
        DEBUGGING = "DEBUGGING", "Debugging"
        CODING = "CODING", "Coding"
        CODE_REVIEW = "CODE_REVIEW", "Code review"

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
    goal = models.CharField(
        max_length=32,
        choices=Goal.choices,
        default=Goal.ROLE_SWITCH,
        blank=True,
    )
    current_stage = models.CharField(
        max_length=32,
        choices=Stage.choices,
        default=Stage.FOUNDATION,
    )
    stage_history = models.JSONField(default=list, blank=True)
    active_turn_id = models.PositiveIntegerField(null=True, blank=True)
    skill_scores = models.JSONField(default=dict, blank=True)
    transfer_report = models.JSONField(default=list, blank=True)
    gap_report = models.JSONField(default=list, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self) -> str:
        return f"Attempt<{self.id}:{self.status}>"


class DiagnosticTurn(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ASKED = "ASKED", "Asked"
        ANSWERED = "ANSWERED", "Answered"
        EVALUATED = "EVALUATED", "Evaluated"
        FAILED = "FAILED", "Failed"

    attempt = models.ForeignKey(
        DiagnosticAttempt,
        on_delete=models.CASCADE,
        related_name="turns",
    )
    ordering = models.PositiveIntegerField(default=1)
    stage = models.CharField(max_length=32, choices=DiagnosticAttempt.Stage.choices)
    skill = models.ForeignKey(
        "roles.Skill",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="diagnostic_turns",
    )
    difficulty = models.CharField(max_length=32, default="MEDIUM")
    question_type = models.CharField(max_length=32, default="FREE_TEXT")
    question_payload = models.JSONField(default=dict, blank=True)
    answer_text = models.TextField(blank=True, default="")
    evaluation = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["ordering", "id"]
        unique_together = ("attempt", "ordering")

    def __str__(self) -> str:
        return f"Turn<{self.attempt_id}:{self.ordering}:{self.stage}>"


class SkillEvidence(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="skill_evidence",
    )
    skill = models.ForeignKey(
        "roles.Skill",
        on_delete=models.CASCADE,
        related_name="skill_evidence",
    )
    attempt = models.ForeignKey(
        DiagnosticAttempt,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="skill_evidence",
    )
    turn = models.ForeignKey(
        DiagnosticTurn,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="skill_evidence",
    )
    stage = models.CharField(max_length=32)
    score = models.FloatField(default=0.0)
    evaluation = models.JSONField(default=dict, blank=True)
    strengths = models.JSONField(default=list, blank=True)
    weaknesses = models.JSONField(default=list, blank=True)
    confidence = models.FloatField(default=0.0)
    source_type = models.CharField(max_length=64, default="diagnostic_turn")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"SkillEvidence<{self.user_id}:{self.skill_id}:{self.stage}>"


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


class RoleTaxonomy(models.Model):
    """Admin-managed competency taxonomy for a target role (not LLM-invented)."""

    role_name = models.CharField(max_length=255, unique=True)
    competency_areas = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "role taxonomies"
        ordering = ["role_name"]

    def __str__(self) -> str:
        return self.role_name

    def clean_competency_areas(self) -> list[str]:
        raw = self.competency_areas or []
        if not isinstance(raw, list):
            return []
        out: list[str] = []
        for item in raw:
            name = str(item or "").strip()
            if name and name not in out:
                out.append(name)
        return out


class DomainTaxonomy(models.Model):
    """Admin-managed competency taxonomy for a technical domain (not LLM-invented)."""

    slug = models.SlugField(max_length=64, unique=True)
    domain_name = models.CharField(max_length=255)
    competency_areas = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "domain taxonomies"
        ordering = ["domain_name"]

    def __str__(self) -> str:
        return f"{self.domain_name} ({self.slug})"

    def clean_competency_areas(self) -> list[str]:
        raw = self.competency_areas or []
        if not isinstance(raw, list):
            return []
        out: list[str] = []
        for item in raw:
            name = str(item or "").strip()
            if name and name not in out:
                out.append(name)
        return out


class DiagnosticSession(models.Model):
    """Block A/B adaptive diagnostic session (replaces live Attempt/Turn flow)."""

    class Goal(models.TextChoices):
        SHARPEN_CURRENT = "sharpen_current", "Sharpen current role"
        SWITCH_ROLE = "switch_role", "Switch role"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        GENERATING = "GENERATING", "Generating"
        AWAITING_ANSWERS = "AWAITING_ANSWERS", "Awaiting answers"
        SYNTHESIZING = "SYNTHESIZING", "Synthesizing"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"

    class Block(models.TextChoices):
        A = "A", "Block A"
        B = "B", "Block B"

    class Stage(models.TextChoices):
        FOUNDATIONAL = "FOUNDATIONAL", "Foundational"
        SCENARIO = "SCENARIO", "Scenario"
        DEBUGGING = "DEBUGGING", "Debugging"
        CODING = "CODING", "Coding"
        FIND_ISSUES = "FIND_ISSUES", "Find issues"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="diagnostic_sessions",
    )
    goal = models.CharField(max_length=32, choices=Goal.choices)
    target_role = models.CharField(max_length=255, blank=True, default="")
    target_taxonomy = models.ForeignKey(
        RoleTaxonomy,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sessions",
    )
    selected_domains = models.ManyToManyField(
        DomainTaxonomy,
        blank=True,
        related_name="sessions",
    )
    assessment_competencies = models.JSONField(default=list, blank=True)
    current_role = models.CharField(max_length=255, blank=True, default="")
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.PENDING,
    )
    current_block = models.CharField(
        max_length=8,
        choices=Block.choices,
        null=True,
        blank=True,
    )
    current_stage = models.CharField(
        max_length=32,
        choices=Stage.choices,
        null=True,
        blank=True,
    )
    synthesis = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"DiagnosticSession<{self.id}:{self.goal}:{self.status}>"

    @property
    def low_stakes(self) -> bool:
        return self.current_block == self.Block.B


class SessionQuestion(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ASKED = "ASKED", "Asked"
        ANSWERED = "ANSWERED", "Answered"

    session = models.ForeignKey(
        DiagnosticSession,
        on_delete=models.CASCADE,
        related_name="questions",
    )
    block = models.CharField(max_length=8, choices=DiagnosticSession.Block.choices)
    stage = models.CharField(max_length=32, choices=DiagnosticSession.Stage.choices)
    order = models.PositiveIntegerField(default=1)
    competency_area = models.CharField(max_length=255, blank=True, default="")
    question_text = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.ASKED,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]
        unique_together = ("session", "block", "stage", "order")

    def __str__(self) -> str:
        return f"SessionQuestion<{self.session_id}:{self.block}:{self.stage}:{self.order}>"


class SessionAnswer(models.Model):
    question = models.OneToOneField(
        SessionQuestion,
        on_delete=models.CASCADE,
        related_name="answer",
    )
    answer_text = models.TextField(blank=True, default="")
    exposure_confirmed = models.BooleanField(null=True, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"SessionAnswer<{self.question_id}>"


class DiagnosticRoadmapItem(models.Model):
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

    session = models.ForeignKey(
        DiagnosticSession,
        on_delete=models.CASCADE,
        related_name="roadmap_items",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="diagnostic_roadmap_items",
    )
    challenge_modality = models.CharField(max_length=32, choices=Modality.choices)
    topic = models.CharField(max_length=512)
    priority = models.PositiveIntegerField(default=1)
    challenge = models.ForeignKey(
        "challenges.Challenge",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="diagnostic_roadmap_items",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["priority", "id"]

    def __str__(self) -> str:
        return f"RoadmapItem<{self.user_id}:{self.priority}:{self.topic[:40]}>"

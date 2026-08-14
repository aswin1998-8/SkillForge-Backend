"""Diagnostic assessment and static content models."""

from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class FundamentalsTopic(models.Model):
    class LanguageFamily(models.TextChoices):
        JAVASCRIPT = "javascript", "JavaScript / TypeScript"
        PYTHON = "python", "Python"
        SQL = "sql", "SQL"

    language_family = models.CharField(
        max_length=32,
        choices=LanguageFamily.choices,
        unique=True,
    )
    competency_areas = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["language_family"]

    def __str__(self) -> str:
        return self.get_language_family_display()

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


class FrameworkTopic(models.Model):
    class FrameworkName(models.TextChoices):
        REACT = "react", "React"
        NEXTJS = "nextjs", "Next.js"
        DJANGO = "django", "Django"
        FASTAPI = "fastapi", "FastAPI"
        POSTGRESQL = "postgresql", "PostgreSQL"

    framework_name = models.CharField(
        max_length=32,
        choices=FrameworkName.choices,
        unique=True,
    )
    fundamentals_topic = models.ForeignKey(
        FundamentalsTopic,
        on_delete=models.PROTECT,
        related_name="frameworks",
    )
    competency_areas = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["framework_name"]

    def __str__(self) -> str:
        return self.get_framework_name_display()

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


class Question(models.Model):
    class Modality(models.TextChoices):
        FOUNDATIONAL = "foundational", "Foundational"
        CODING = "coding", "Coding"
        FIND_ISSUES = "find_issues", "Find issues"
        SCENARIO = "scenario", "Scenario"
        DEFEND = "defend", "Defend"
        DIAGNOSE = "diagnose", "Diagnose"
        ARCHITECT = "architect", "Architect"
        EXPLAIN = "explain", "Explain"
        COMMUNICATE = "communicate", "Communicate"

    class Language(models.TextChoices):
        PYTHON = "python", "Python"
        JAVASCRIPT = "javascript", "JavaScript"

    fundamentals_topic = models.ForeignKey(
        FundamentalsTopic,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="questions",
    )
    framework_topic = models.ForeignKey(
        FrameworkTopic,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="questions",
    )
    competency_area = models.CharField(max_length=255)
    modality = models.CharField(max_length=32, choices=Modality.choices)
    question_text = models.TextField()
    difficulty_tier = models.PositiveSmallIntegerField(default=1)
    language = models.CharField(
        max_length=32,
        choices=Language.choices,
        blank=True,
        default="",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["difficulty_tier", "id"]

    def __str__(self) -> str:
        return f"{self.modality}:{self.competency_area}:{self.id}"

    def clean(self) -> None:
        has_fundamentals = self.fundamentals_topic_id is not None
        has_framework = self.framework_topic_id is not None
        if has_fundamentals == has_framework:
            raise ValidationError(
                "Exactly one of fundamentals_topic or framework_topic must be set."
            )
        if self.modality in {self.Modality.CODING, self.Modality.FIND_ISSUES}:
            if not self.language:
                raise ValidationError("Coding questions require a language.")


class QuestionChoice(models.Model):
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="choices",
    )
    choice_text = models.TextField()
    is_correct = models.BooleanField(default=False)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"Choice<{self.question_id}:{self.choice_text[:40]}>"


class CodingTestCase(models.Model):
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="test_cases",
    )
    input = models.TextField(blank=True, default="")
    expected_output = models.TextField()
    is_hidden = models.BooleanField(default=False)
    order = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self) -> str:
        return f"TestCase<{self.question_id}:{self.order}>"


class ReferenceAnswer(models.Model):
    question = models.OneToOneField(
        Question,
        on_delete=models.CASCADE,
        related_name="reference_answer",
    )
    reference_text = models.TextField()
    rubric_points = models.JSONField(default=list, blank=True)

    def __str__(self) -> str:
        return f"ReferenceAnswer<{self.question_id}>"


class DiagnosticSession(models.Model):
    """Static-content adaptive diagnostic session."""

    class Goal(models.TextChoices):
        SHARPEN_CURRENT = "sharpen_current", "Sharpen current role"
        SWITCH_ROLE = "switch_role", "Switch role"

    class Status(models.TextChoices):
        AWAITING_ANSWERS = "AWAITING_ANSWERS", "Awaiting answers"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"

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
    selected_frameworks = models.ManyToManyField(
        FrameworkTopic,
        blank=True,
        related_name="sessions",
    )
    assessment_competencies = models.JSONField(default=list, blank=True)
    current_role = models.CharField(max_length=255, blank=True, default="")
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.AWAITING_ANSWERS,
    )
    current_stage = models.CharField(
        max_length=32,
        choices=Stage.choices,
        null=True,
        blank=True,
    )
    selection_log = models.JSONField(default=list, blank=True)
    area_tracks = models.JSONField(default=dict, blank=True)
    synthesis = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True, default="")
    difficulty_bump = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"DiagnosticSession<{self.id}:{self.goal}:{self.status}>"


class SessionQuestion(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ASKED = "ASKED", "Asked"
        ANSWERED = "ANSWERED", "Answered"
        REVEALED = "REVEALED", "Revealed"
        SELF_RATED = "SELF_RATED", "Self rated"

    session = models.ForeignKey(
        DiagnosticSession,
        on_delete=models.CASCADE,
        related_name="questions",
    )
    content_question = models.ForeignKey(
        Question,
        on_delete=models.PROTECT,
        related_name="session_instances",
    )
    stage = models.CharField(
        max_length=32,
        choices=DiagnosticSession.Stage.choices,
    )
    order = models.PositiveIntegerField(default=1)
    competency_area = models.CharField(max_length=255, blank=True, default="")
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.ASKED,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]
        unique_together = ("session", "stage", "order")

    def __str__(self) -> str:
        return f"SessionQuestion<{self.session_id}:{self.stage}:{self.order}>"


class SessionAnswer(models.Model):
    question = models.OneToOneField(
        SessionQuestion,
        on_delete=models.CASCADE,
        related_name="answer",
    )
    answer_text = models.TextField(blank=True, default="")
    choice_id = models.PositiveIntegerField(null=True, blank=True)
    is_correct = models.BooleanField(null=True, blank=True)
    confidence_rating = models.PositiveSmallIntegerField(null=True, blank=True)
    self_rated_alignment = models.JSONField(null=True, blank=True)
    grading_detail = models.JSONField(default=dict, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    revealed_at = models.DateTimeField(null=True, blank=True)
    self_rated_at = models.DateTimeField(null=True, blank=True)

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
        USE_AI = "USE_AI", "Use AI without skill atrophy"
        COMMUNICATE = "COMMUNICATE", "Communicate"
        AUDIT_AI_PR = "AUDIT_AI_PR", "Audit the AI PR"
        EXPLAIN_AI_DIFF = "EXPLAIN_AI_DIFF", "Explain AI diff"
        INHERITED_CODEBASE = "INHERITED_CODEBASE", "Inherited codebase"
        WAR_ROOM = "WAR_ROOM", "War room"

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
    status = models.CharField(
        max_length=32,
        default="not_started",
        choices=[
            ("not_started", "Not started"),
            ("in_progress", "In progress"),
            ("closed", "Closed"),
        ],
    )
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


class QuickScoreQuestion(models.Model):
    class Track(models.TextChoices):
        FRONTEND = "frontend", "Frontend"
        BACKEND = "backend", "Backend"

    track = models.CharField(max_length=32, choices=Track.choices)
    competency_area = models.CharField(max_length=255)
    question_text = models.TextField()
    weight = models.PositiveSmallIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    order = models.PositiveSmallIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["track", "order", "id"]

    def __str__(self) -> str:
        return f"QuickScoreQ<{self.track}:{self.id}>"


class QuickScoreChoice(models.Model):
    question = models.ForeignKey(
        QuickScoreQuestion,
        on_delete=models.CASCADE,
        related_name="choices",
    )
    choice_text = models.TextField()
    points = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"QuickScoreChoice<{self.question_id}:{self.points}>"


class QuickScoreParagraph(models.Model):
    class Band(models.TextChoices):
        SOLID_FOUNDATION = "solid_foundation", "Solid Foundation"
        EMERGING_GAPS = "emerging_gaps", "Emerging Gaps"
        AT_RISK = "at_risk", "At Risk of Falling Behind"
        SIGNIFICANT_GAP = "significant_gap", "Significant Gap"

    band = models.CharField(max_length=32, choices=Band.choices)
    track = models.CharField(max_length=32, choices=QuickScoreQuestion.Track.choices)
    body_text = models.TextField()

    class Meta:
        unique_together = ("band", "track")
        ordering = ["track", "band"]

    def __str__(self) -> str:
        return f"QuickScoreParagraph<{self.track}:{self.band}>"


class QuickScoreAttempt(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="quick_score_attempts",
    )
    track = models.CharField(max_length=32, choices=QuickScoreQuestion.Track.choices)
    answers = models.JSONField(default=dict, blank=True)
    total_score = models.PositiveSmallIntegerField(default=0)
    band = models.CharField(max_length=32, choices=QuickScoreParagraph.Band.choices)
    paragraph_text = models.TextField(blank=True, default="")
    highlight_areas = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"QuickScoreAttempt<{self.user_id}:{self.total_score}:{self.band}>"


class SkillAreaFragment(models.Model):
    class Level(models.TextChoices):
        STRONG = "strong", "Strong"
        PARTIAL = "partial", "Partial"
        GAP = "gap", "Gap"

    competency_area = models.CharField(max_length=255)
    level = models.CharField(max_length=16, choices=Level.choices)
    body_text = models.TextField()

    class Meta:
        unique_together = ("competency_area", "level")
        ordering = ["competency_area", "level"]

    def __str__(self) -> str:
        return f"Fragment<{self.competency_area}:{self.level}>"


class MarketEvidence(models.Model):
    competency_area = models.CharField(max_length=255, db_index=True)
    stat_text = models.TextField()
    source_name = models.CharField(max_length=255)
    source_date = models.CharField(max_length=64, blank=True, default="")
    as_of = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["competency_area", "id"]

    def __str__(self) -> str:
        return f"Evidence<{self.competency_area}:{self.source_name}>"

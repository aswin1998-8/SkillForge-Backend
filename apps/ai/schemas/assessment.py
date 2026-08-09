"""Structured schemas for adaptive assessment AI outputs."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


AssessmentStage = Literal[
    "FOUNDATION",
    "SCENARIO",
    "DEBUGGING",
    "CODING",
    "CODE_REVIEW",
]


class GeneratedQuestionSchema(BaseModel):
    stage: str = "FOUNDATION"
    skill_slug: str = ""
    difficulty: str = "MEDIUM"
    question_type: str = "FREE_TEXT"
    prompt_text: str
    requirements: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    expected_behavior: str = ""
    evaluation_criteria: list[str] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class EvaluationDimensions(BaseModel):
    conceptual_accuracy: float = Field(default=0.5, ge=0.0, le=1.0)
    technical_depth: float = Field(default=0.5, ge=0.0, le=1.0)
    reasoning: float = Field(default=0.5, ge=0.0, le=1.0)
    problem_solving: float = Field(default=0.5, ge=0.0, le=1.0)


class AnswerEvaluationSchema(BaseModel):
    evaluation: EvaluationDimensions = Field(default_factory=EvaluationDimensions)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    misconceptions: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    recommended_next_stage: str = "FOUNDATION"
    overall_strength: str = "MODERATE"
    raw: dict[str, Any] = Field(default_factory=dict)

    def mean_score(self) -> float:
        e = self.evaluation
        return (
            e.conceptual_accuracy
            + e.technical_depth
            + e.reasoning
            + e.problem_solving
        ) / 4.0


class TransferItemSchema(BaseModel):
    from_skill_slug: str
    to_skill_slug: str
    rationale: str = ""


class TransferableSkillsSchema(BaseModel):
    transfers: list[TransferItemSchema] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class SkillGapExplanationSchema(BaseModel):
    skill_slug: str
    explanation: str = ""


class SkillGapAnalysisSchema(BaseModel):
    explanations: list[SkillGapExplanationSchema] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class RoadmapAnnotationSchema(BaseModel):
    challenge_id: int
    note: str = ""


class RoadmapGenerationSchema(BaseModel):
    ordered_challenge_ids: list[int] = Field(default_factory=list)
    annotations: list[RoadmapAnnotationSchema] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class ChallengeEvaluationSchema(BaseModel):
    evaluation: EvaluationDimensions = Field(default_factory=EvaluationDimensions)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    misconceptions: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    correctness: float = Field(default=0.5, ge=0.0, le=1.0)
    code_quality: float = Field(default=0.5, ge=0.0, le=1.0)
    architecture: float = Field(default=0.5, ge=0.0, le=1.0)
    security: float = Field(default=0.5, ge=0.0, le=1.0)
    summary: str = ""
    recommended_next_stage: str = "CODING"
    overall_strength: str = "MODERATE"
    raw: dict[str, Any] = Field(default_factory=dict)

    def mean_score(self) -> float:
        return (
            self.evaluation.mean_score()
            if hasattr(self.evaluation, "mean_score")
            else (
                self.evaluation.conceptual_accuracy
                + self.evaluation.technical_depth
                + self.evaluation.reasoning
                + self.evaluation.problem_solving
            )
            / 4.0
        )


class StageQuestionItemSchema(BaseModel):
    question_text: str
    question_type: str = "FREE_TEXT"


class StageQuestionsSchema(BaseModel):
    questions: list[StageQuestionItemSchema] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class BlockBQuestionItemSchema(BaseModel):
    competency_area: str
    question_text: str
    question_type: str = "FREE_TEXT"


class BlockBQuestionsSchema(BaseModel):
    questions: list[BlockBQuestionItemSchema] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


# Same shape as Block B: one question per competency_area for domain-grounded Block A.
BlockACompetencyQuestionItemSchema = BlockBQuestionItemSchema
BlockACompetencyQuestionsSchema = BlockBQuestionsSchema


class BlockBExposureItemSchema(BaseModel):
    question_id: int
    competency_area: str = ""
    exposure_confirmed: bool = False


class BlockBExposureSchema(BaseModel):
    classifications: list[BlockBExposureItemSchema] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class RoleTaxonomySchema(BaseModel):
    role_name: str = ""
    competency_areas: list[str] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class SynthesisStrengthSchema(BaseModel):
    skill_area: str
    evidence: str = ""


class SynthesisGapSchema(BaseModel):
    skill_area: str
    block: Literal["A", "B"] = "A"
    severity: str = "moderate"


class SynthesisTransferSchema(BaseModel):
    from_current_role: str
    applies_to_target: str


class SynthesisRoadmapItemSchema(BaseModel):
    challenge_modality: str
    topic: str
    priority: int = 1


class DiagnosticSynthesisSchema(BaseModel):
    strengths: list[SynthesisStrengthSchema] = Field(default_factory=list)
    gaps: list[SynthesisGapSchema] = Field(default_factory=list)
    transferable_skills: list[SynthesisTransferSchema] = Field(default_factory=list)
    roadmap: list[SynthesisRoadmapItemSchema] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)

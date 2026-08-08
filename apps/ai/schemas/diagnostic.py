from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DiagnosticGapItem(BaseModel):
    skill_slug: str
    severity: str = "partial"
    notes: str = ""


class DiagnosticEvidenceItem(BaseModel):
    source: str = ""
    detail: str = ""


class DiagnosticSkillFinding(BaseModel):
    skill_slug: str
    level: str = "BEGINNER"
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class DiagnosticResultSchema(BaseModel):
    strengths: list[str] = Field(default_factory=list)
    gaps: list[DiagnosticGapItem] = Field(default_factory=list)
    evidence: list[DiagnosticEvidenceItem] = Field(default_factory=list)
    skill_findings: list[DiagnosticSkillFinding] = Field(default_factory=list)
    recommended_focus: str = ""
    summary: str = ""
    raw: dict[str, Any] = Field(default_factory=dict)

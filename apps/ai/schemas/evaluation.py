from __future__ import annotations

from pydantic import BaseModel, Field


class DebriefEvaluationSchema(BaseModel):
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    next_focus: str = ""
    score: int = Field(default=0, ge=0, le=100)
    summary: str = ""

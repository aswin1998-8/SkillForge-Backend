from __future__ import annotations

from pydantic import BaseModel, Field


class DebriefQuestionSchema(BaseModel):
    prompt_text: str
    focus_area: str = ""

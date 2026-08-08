"""Debrief question AI service with validation and one retry."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import ValidationError

from apps.ai.prompts.debrief import build_debrief_question_prompt
from apps.ai.providers.factory import get_ai_provider
from apps.ai.schemas.debrief import DebriefQuestionSchema

logger = logging.getLogger(__name__)


def run_debrief_question(
    *,
    challenge_title: str,
    modality: str,
    submission_summary: str,
    prior_qa: list[dict[str, Any]],
    next_order: int,
    max_questions: int,
    focus_skill: str = "",
) -> DebriefQuestionSchema:
    provider = get_ai_provider()
    prompt = build_debrief_question_prompt(
        challenge_title=challenge_title,
        modality=modality,
        submission_summary=submission_summary,
        prior_qa=prior_qa,
        next_order=next_order,
        max_questions=max_questions,
        focus_skill=focus_skill,
    )
    context = {
        "next_order": next_order,
        "modality": modality,
        "focus_skill": focus_skill,
    }

    last_error: Exception | None = None
    for attempt in range(2):
        try:
            raw = provider.generate_debrief_question(prompt=prompt, context=context)
            return DebriefQuestionSchema.model_validate(raw)
        except (ValidationError, ValueError, TypeError) as exc:
            last_error = exc
            logger.warning("Debrief question AI parse failed (attempt %s): %s", attempt + 1, exc)

    raise ValueError(f"Debrief question AI failed after retry: {last_error}")

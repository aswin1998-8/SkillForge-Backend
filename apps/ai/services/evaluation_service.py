"""Debrief evaluation AI service with validation and one retry."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import ValidationError

from apps.ai.prompts.evaluation import build_evaluation_prompt
from apps.ai.providers.factory import get_ai_provider
from apps.ai.schemas.evaluation import DebriefEvaluationSchema

logger = logging.getLogger(__name__)


def run_debrief_evaluation(
    *,
    challenge_title: str,
    modality: str,
    submission_summary: str,
    qa_pairs: list[dict[str, Any]],
    focus_skill: str = "",
) -> DebriefEvaluationSchema:
    provider = get_ai_provider()
    prompt = build_evaluation_prompt(
        challenge_title=challenge_title,
        modality=modality,
        submission_summary=submission_summary,
        qa_pairs=qa_pairs,
        focus_skill=focus_skill,
    )
    context = {"focus_skill": focus_skill, "modality": modality}

    last_error: Exception | None = None
    for attempt in range(2):
        try:
            raw = provider.evaluate_debrief(prompt=prompt, context=context)
            return DebriefEvaluationSchema.model_validate(raw)
        except (ValidationError, ValueError, TypeError) as exc:
            last_error = exc
            logger.warning("Debrief evaluation AI parse failed (attempt %s): %s", attempt + 1, exc)

    raise ValueError(f"Debrief evaluation AI failed after retry: {last_error}")

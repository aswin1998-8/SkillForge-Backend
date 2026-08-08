"""Diagnostic AI service with validation and one retry."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import ValidationError

from apps.ai.prompts.diagnostic import build_diagnostic_prompt
from apps.ai.providers.factory import get_ai_provider
from apps.ai.schemas.diagnostic import DiagnosticResultSchema

logger = logging.getLogger(__name__)


def run_diagnostic_analysis(
    *,
    diagnostic_title: str,
    questions_and_answers: list[dict[str, Any]],
    skills: list[dict[str, Any]],
) -> DiagnosticResultSchema:
    provider = get_ai_provider()
    prompt = build_diagnostic_prompt(
        diagnostic_title=diagnostic_title,
        questions_and_answers=questions_and_answers,
        skills=skills,
    )
    context = {"skills": skills}

    last_error: Exception | None = None
    for attempt in range(2):
        try:
            raw = provider.generate_diagnostic(prompt=prompt, context=context)
            schema = DiagnosticResultSchema.model_validate(raw)
            schema.raw = raw
            return schema
        except (ValidationError, ValueError, TypeError) as exc:
            last_error = exc
            logger.warning("Diagnostic AI parse failed (attempt %s): %s", attempt + 1, exc)

    raise ValueError(f"Diagnostic AI failed after retry: {last_error}")

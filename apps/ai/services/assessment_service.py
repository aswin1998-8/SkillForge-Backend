"""AI orchestration helpers with validate + one retry."""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, TypeVar

from pydantic import BaseModel, ValidationError

from apps.ai.providers.factory import get_ai_provider

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


def run_structured(
    *,
    operation: str,
    call: Callable[[], dict[str, Any]],
    schema: type[T],
) -> T:
    last_error: Exception | None = None
    started = time.monotonic()
    for attempt in range(2):
        try:
            raw = call()
            parsed = schema.model_validate(raw)
            if hasattr(parsed, "raw"):
                parsed.raw = raw  # type: ignore[attr-defined]
            _log_request(
                operation=operation,
                status="ok",
                latency_ms=int((time.monotonic() - started) * 1000),
                error="",
            )
            return parsed
        except (ValidationError, ValueError, TypeError) as exc:
            last_error = exc
            logger.warning("%s AI parse failed (attempt %s): %s", operation, attempt + 1, exc)
    _log_request(
        operation=operation,
        status="error",
        latency_ms=int((time.monotonic() - started) * 1000),
        error=str(last_error),
    )
    raise ValueError(f"{operation} AI failed after retry: {last_error}")


def _log_request(*, operation: str, status: str, latency_ms: int, error: str) -> None:
    try:
        from django.conf import settings

        from apps.ai.models import AIRequestLog

        provider = (getattr(settings, "AI_PROVIDER", None) or "mock").lower()
        model = ""
        if provider == "gemini":
            model = getattr(settings, "GEMINI_MODEL", "")
        elif provider == "claude":
            model = getattr(settings, "CLAUDE_MODEL", "")
        AIRequestLog.objects.create(
            provider=provider,
            model=model,
            operation=operation,
            status=status,
            latency_ms=latency_ms,
            error=error[:2000],
        )
    except Exception:  # noqa: BLE001
        logger.debug("AIRequestLog write skipped", exc_info=True)


def generate_adaptive_question(context: dict[str, Any]):
    from apps.ai.prompts.assessment import build_generate_question_prompt
    from apps.ai.schemas.assessment import GeneratedQuestionSchema

    provider = get_ai_provider()
    prompt = build_generate_question_prompt(context=context)
    return run_structured(
        operation="generate_question",
        call=lambda: provider.generate_question(prompt=prompt, context=context),
        schema=GeneratedQuestionSchema,
    )


def evaluate_adaptive_answer(context: dict[str, Any], answer: str):
    from apps.ai.prompts.assessment import build_evaluate_answer_prompt
    from apps.ai.schemas.assessment import AnswerEvaluationSchema

    provider = get_ai_provider()
    stage = context.get("assessment_stage") or "FOUNDATION"
    prompt = build_evaluate_answer_prompt(context=context, answer=answer)
    if stage in {"CODING", "CODE_REVIEW"}:
        call = lambda: provider.evaluate_code(prompt=prompt, context=context)
    else:
        call = lambda: provider.evaluate_answer(prompt=prompt, context=context)
    return run_structured(
        operation="evaluate_answer",
        call=call,
        schema=AnswerEvaluationSchema,
    )


def analyze_transfers(context: dict[str, Any]):
    from apps.ai.prompts.assessment import build_transferable_skills_prompt
    from apps.ai.schemas.assessment import TransferableSkillsSchema

    provider = get_ai_provider()
    prompt = build_transferable_skills_prompt(context=context)
    return run_structured(
        operation="analyze_transferable_skills",
        call=lambda: provider.analyze_transferable_skills(prompt=prompt, context=context),
        schema=TransferableSkillsSchema,
    )


def explain_skill_gaps(context: dict[str, Any]):
    from apps.ai.prompts.assessment import build_skill_gap_prompt
    from apps.ai.schemas.assessment import SkillGapAnalysisSchema

    provider = get_ai_provider()
    prompt = build_skill_gap_prompt(context=context)
    return run_structured(
        operation="analyze_skill_gap",
        call=lambda: provider.analyze_skill_gap(prompt=prompt, context=context),
        schema=SkillGapAnalysisSchema,
    )


def rank_roadmap(context: dict[str, Any]):
    from apps.ai.prompts.assessment import build_roadmap_prompt
    from apps.ai.schemas.assessment import RoadmapGenerationSchema

    provider = get_ai_provider()
    prompt = build_roadmap_prompt(context=context)
    return run_structured(
        operation="generate_roadmap",
        call=lambda: provider.generate_roadmap(prompt=prompt, context=context),
        schema=RoadmapGenerationSchema,
    )


def evaluate_challenge(context: dict[str, Any], submission: dict[str, Any]):
    from apps.ai.prompts.assessment import build_challenge_eval_prompt
    from apps.ai.schemas.assessment import ChallengeEvaluationSchema

    provider = get_ai_provider()
    prompt = build_challenge_eval_prompt(context=context, submission=submission)
    return run_structured(
        operation="evaluate_challenge_submission",
        call=lambda: provider.evaluate_challenge_submission(prompt=prompt, context=context),
        schema=ChallengeEvaluationSchema,
    )


def generate_stage_questions(context: dict[str, Any]):
    from apps.ai.prompts.assessment import build_stage_questions_prompt
    from apps.ai.schemas.assessment import StageQuestionsSchema

    provider = get_ai_provider()
    prompt = build_stage_questions_prompt(context=context)
    return run_structured(
        operation="generate_stage_questions",
        call=lambda: provider.generate_stage_questions(prompt=prompt, context=context),
        schema=StageQuestionsSchema,
    )


def generate_block_b_questions(context: dict[str, Any]):
    from apps.ai.prompts.assessment import build_block_b_questions_prompt
    from apps.ai.schemas.assessment import BlockBQuestionsSchema

    provider = get_ai_provider()
    prompt = build_block_b_questions_prompt(context=context)
    return run_structured(
        operation="generate_block_b_questions",
        call=lambda: provider.generate_block_b_questions(prompt=prompt, context=context),
        schema=BlockBQuestionsSchema,
    )


def generate_block_a_competency_questions(context: dict[str, Any]):
    from apps.ai.prompts.assessment import build_block_a_competency_questions_prompt
    from apps.ai.schemas.assessment import BlockACompetencyQuestionsSchema

    provider = get_ai_provider()
    prompt = build_block_a_competency_questions_prompt(context=context)
    return run_structured(
        operation="generate_block_a_competency_questions",
        call=lambda: provider.generate_block_a_competency_questions(
            prompt=prompt, context=context
        ),
        schema=BlockACompetencyQuestionsSchema,
    )


def classify_block_b_exposure(context: dict[str, Any]):
    from apps.ai.prompts.assessment import build_block_b_exposure_prompt
    from apps.ai.schemas.assessment import BlockBExposureSchema

    provider = get_ai_provider()
    prompt = build_block_b_exposure_prompt(context=context)
    return run_structured(
        operation="classify_block_b_exposure",
        call=lambda: provider.classify_block_b_exposure(prompt=prompt, context=context),
        schema=BlockBExposureSchema,
    )


def generate_role_taxonomy(context: dict[str, Any]):
    from apps.ai.prompts.assessment import build_role_taxonomy_prompt
    from apps.ai.schemas.assessment import RoleTaxonomySchema

    provider = get_ai_provider()
    prompt = build_role_taxonomy_prompt(context=context)
    return run_structured(
        operation="generate_role_taxonomy",
        call=lambda: provider.generate_role_taxonomy(prompt=prompt, context=context),
        schema=RoleTaxonomySchema,
    )


def synthesize_diagnostic(context: dict[str, Any]):
    from apps.ai.prompts.assessment import build_diagnostic_synthesis_prompt
    from apps.ai.schemas.assessment import DiagnosticSynthesisSchema

    provider = get_ai_provider()
    prompt = build_diagnostic_synthesis_prompt(context=context)
    return run_structured(
        operation="synthesize_diagnostic",
        call=lambda: provider.synthesize_diagnostic(prompt=prompt, context=context),
        schema=DiagnosticSynthesisSchema,
    )

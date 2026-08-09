"""Gemini AI provider."""

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings

from apps.ai.providers.base import AIProvider
from apps.ai.providers.json_utils import extract_json_object

logger = logging.getLogger(__name__)


class GeminiProvider(AIProvider):
    def __init__(self, *, api_key: str | None = None, model: str | None = None) -> None:
        import google.generativeai as genai

        key = api_key or settings.GEMINI_API_KEY
        genai.configure(api_key=key)
        self._model_name = model or settings.GEMINI_MODEL
        self._model = genai.GenerativeModel(self._model_name)

    def _complete(self, *, system: str, user: str) -> dict[str, Any]:
        prompt = f"{system}\n\n{user}"
        response = self._model.generate_content(
            prompt,
            generation_config={
                "temperature": 0.3,
                "max_output_tokens": 4096,
                "response_mime_type": "application/json",
            },
        )
        raw = (getattr(response, "text", None) or "").strip()
        if not raw and getattr(response, "candidates", None):
            parts = []
            for cand in response.candidates:
                content = getattr(cand, "content", None)
                for part in getattr(content, "parts", []) or []:
                    text = getattr(part, "text", None)
                    if text:
                        parts.append(text)
            raw = "\n".join(parts).strip()
        logger.info("Gemini completion received (%s chars)", len(raw))
        return extract_json_object(raw)

    def _json_call(self, *, role: str, prompt: str) -> dict[str, Any]:
        system = (
            f"You are Honed's {role}. "
            "Respond with a single JSON object only. No markdown, no prose outside JSON."
        )
        return self._complete(system=system, user=prompt)

    def generate_diagnostic(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        return self._json_call(role="diagnostic analyst", prompt=prompt)

    def generate_debrief_question(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        return self._json_call(role="Socratic coach", prompt=prompt)

    def evaluate_debrief(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        return self._json_call(role="debrief evaluator", prompt=prompt)

    def generate_question(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        return self._json_call(role="adaptive assessment designer", prompt=prompt)

    def evaluate_answer(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        return self._json_call(role="answer evaluator", prompt=prompt)

    def evaluate_code(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        return self._json_call(role="code evaluator", prompt=prompt)

    def generate_follow_up_question(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        return self._json_call(role="follow-up question designer", prompt=prompt)

    def analyze_evidence(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        return self._json_call(role="evidence analyst", prompt=prompt)

    def analyze_skill_gap(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        return self._json_call(role="skill-gap explainer", prompt=prompt)

    def analyze_transferable_skills(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        return self._json_call(role="transferable-skills analyst", prompt=prompt)

    def generate_roadmap(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        return self._json_call(role="roadmap planner", prompt=prompt)

    def evaluate_challenge_submission(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        return self._json_call(role="challenge evaluator", prompt=prompt)

    def generate_stage_questions(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        return self._json_call(role="block assessment designer", prompt=prompt)

    def generate_block_b_questions(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        return self._json_call(role="block b taxonomy question designer", prompt=prompt)

    def generate_block_a_competency_questions(
        self, *, prompt: str, context: dict[str, Any]
    ) -> dict[str, Any]:
        return self._json_call(role="block a domain competency designer", prompt=prompt)

    def classify_block_b_exposure(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        return self._json_call(role="block b exposure classifier", prompt=prompt)

    def generate_role_taxonomy(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        return self._json_call(role="role taxonomy designer", prompt=prompt)

    def synthesize_diagnostic(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        return self._json_call(role="diagnostic synthesizer", prompt=prompt)

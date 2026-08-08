"""Claude (Anthropic) AI provider."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from django.conf import settings

from apps.ai.providers.base import AIProvider

logger = logging.getLogger(__name__)


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        data = json.loads(fence.group(1))
        if isinstance(data, dict):
            return data

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        data = json.loads(text[start : end + 1])
        if isinstance(data, dict):
            return data

    raise ValueError("Claude response did not contain valid JSON object.")


class ClaudeProvider(AIProvider):
    def __init__(self, *, api_key: str | None = None, model: str | None = None) -> None:
        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key or settings.CLAUDE_API_KEY)
        self._model = model or settings.CLAUDE_MODEL

    def _complete(self, *, system: str, user: str) -> dict[str, Any]:
        message = self._client.messages.create(
            model=self._model,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        parts: list[str] = []
        for block in message.content:
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
        raw = "\n".join(parts).strip()
        logger.info("Claude completion received (%s chars)", len(raw))
        return _extract_json(raw)

    def generate_diagnostic(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        system = (
            "You are SkillForge's diagnostic analyst. "
            "Respond with a single JSON object only. No markdown, no prose outside JSON."
        )
        return self._complete(system=system, user=prompt)

    def generate_debrief_question(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        system = (
            "You are SkillForge's Socratic coach. "
            "Respond with a single JSON object only containing the next debrief question."
        )
        return self._complete(system=system, user=prompt)

    def evaluate_debrief(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        system = (
            "You are SkillForge's debrief evaluator. "
            "Respond with a single JSON object only containing the evaluation."
        )
        return self._complete(system=system, user=prompt)

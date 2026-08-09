"""Factory for AI providers."""

from __future__ import annotations

import logging

from django.conf import settings

from apps.ai.providers.base import AIProvider
from apps.ai.providers.claude import ClaudeProvider
from apps.ai.providers.gemini import GeminiProvider
from apps.ai.providers.mock import MockAIProvider

logger = logging.getLogger(__name__)


def get_ai_provider() -> AIProvider:
    provider_name = (getattr(settings, "AI_PROVIDER", None) or "gemini").lower().strip()

    if provider_name == "mock":
        logger.info("Using MockAIProvider (AI_PROVIDER=mock)")
        return MockAIProvider()

    if provider_name == "gemini":
        api_key = (getattr(settings, "GEMINI_API_KEY", None) or "").strip()
        if not api_key:
            logger.info("Using MockAIProvider (no GEMINI_API_KEY)")
            return MockAIProvider()
        return GeminiProvider(api_key=api_key)

    if provider_name == "claude":
        api_key = (getattr(settings, "CLAUDE_API_KEY", None) or "").strip()
        if not api_key:
            logger.info("Using MockAIProvider (no CLAUDE_API_KEY)")
            return MockAIProvider()
        return ClaudeProvider(api_key=api_key)

    logger.warning("Unknown AI_PROVIDER=%s; falling back to MockAIProvider", provider_name)
    return MockAIProvider()

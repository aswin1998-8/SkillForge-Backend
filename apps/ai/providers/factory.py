"""Factory for AI providers."""

from __future__ import annotations

import logging

from django.conf import settings

from apps.ai.providers.base import AIProvider
from apps.ai.providers.claude import ClaudeProvider
from apps.ai.providers.mock import MockAIProvider

logger = logging.getLogger(__name__)


def get_ai_provider() -> AIProvider:
    api_key = (settings.CLAUDE_API_KEY or "").strip()
    provider_name = (settings.AI_PROVIDER or "claude").lower().strip()

    if not api_key or provider_name == "mock":
        logger.info("Using MockAIProvider (no CLAUDE_API_KEY or AI_PROVIDER=mock)")
        return MockAIProvider()

    if provider_name == "claude":
        return ClaudeProvider(api_key=api_key)

    logger.warning("Unknown AI_PROVIDER=%s; falling back to MockAIProvider", provider_name)
    return MockAIProvider()

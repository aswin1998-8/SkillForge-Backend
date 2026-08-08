"""Abstract AI provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class AIProvider(ABC):
    @abstractmethod
    def generate_diagnostic(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        """Return structured diagnostic analysis as a dict."""

    @abstractmethod
    def generate_debrief_question(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        """Return the next debrief question as a dict."""

    @abstractmethod
    def evaluate_debrief(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        """Return structured debrief evaluation as a dict."""

"""Abstract AI provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class AIProvider(ABC):
    """All LLM calls go through this interface. Domain code must not import SDKs."""

    # --- Legacy batch diagnostic (still used by Celery analysis task) ---
    @abstractmethod
    def generate_diagnostic(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        """Return structured diagnostic analysis as a dict."""

    @abstractmethod
    def generate_debrief_question(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        """Return the next debrief question as a dict."""

    @abstractmethod
    def evaluate_debrief(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        """Return structured debrief evaluation as a dict."""

    # --- Adaptive assessment ---
    @abstractmethod
    def generate_question(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        """Generate one adaptive assessment question."""

    @abstractmethod
    def evaluate_answer(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        """Evaluate a free-text / scenario / debugging answer."""

    @abstractmethod
    def evaluate_code(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        """Evaluate a coding or code-review response."""

    @abstractmethod
    def generate_follow_up_question(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        """Generate a follow-up probe within the same stage."""

    # --- Analysis ---
    @abstractmethod
    def analyze_evidence(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        """Summarize evidence across turns (explanatory only)."""

    @abstractmethod
    def analyze_skill_gap(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        """Explain skill gaps (classification is backend-owned)."""

    @abstractmethod
    def analyze_transferable_skills(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        """Propose transferable skill relationships."""

    @abstractmethod
    def generate_roadmap(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        """Rank/annotate eligible roadmap steps."""

    @abstractmethod
    def evaluate_challenge_submission(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        """Evaluate a challenge submission into structured evidence."""

    @abstractmethod
    def generate_stage_questions(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        """Generate a batch of stage questions for Block A/B diagnostics."""

    @abstractmethod
    def generate_block_b_questions(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        """Generate one foundational Block B question per taxonomy competency."""

    @abstractmethod
    def generate_block_a_competency_questions(
        self, *, prompt: str, context: dict[str, Any]
    ) -> dict[str, Any]:
        """Generate one Block A question per assigned domain competency."""

    @abstractmethod
    def classify_block_b_exposure(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        """Classify whether each Block B answer shows any exposure."""

    @abstractmethod
    def generate_role_taxonomy(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        """Propose competency_areas for an arbitrary target role."""

    @abstractmethod
    def synthesize_diagnostic(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        """Produce strict synthesis JSON for strengths/gaps/transfers/roadmap."""

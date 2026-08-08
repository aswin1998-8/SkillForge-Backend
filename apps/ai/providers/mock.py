"""Deterministic mock AI provider for local/dev without an API key."""

from __future__ import annotations

from typing import Any

from apps.ai.providers.base import AIProvider


class MockAIProvider(AIProvider):
    def generate_diagnostic(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        skills = context.get("skills") or []
        skill_slugs = [s.get("slug") or s.get("name") for s in skills if isinstance(s, dict)]
        if not skill_slugs:
            skill_slugs = ["rag", "llm-apis"]

        gaps = [
            {
                "skill_slug": slug,
                "severity": "partial",
                "notes": f"Mock gap identified for {slug}.",
            }
            for slug in skill_slugs[:3]
        ]
        strengths = skill_slugs[3:] or ["communication"]
        return {
            "strengths": strengths,
            "gaps": gaps,
            "evidence": [
                {
                    "source": "mock",
                    "detail": "Deterministic mock diagnostic evidence.",
                }
            ],
            "skill_findings": [
                {
                    "skill_slug": slug,
                    "level": "BEGINNER" if i < 2 else "INTERMEDIATE",
                    "confidence": 0.7,
                }
                for i, slug in enumerate(skill_slugs)
            ],
            "recommended_focus": gaps[0]["skill_slug"] if gaps else "rag",
            "summary": "Mock diagnostic completed successfully.",
        }

    def generate_debrief_question(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        order = int(context.get("next_order") or 1)
        modality = context.get("modality") or "GENERAL"
        return {
            "prompt_text": (
                f"Mock debrief question #{order} for {modality}: "
                "Explain the key trade-off in your approach and what you would change next."
            ),
            "focus_area": context.get("focus_skill") or "general",
        }

    def evaluate_debrief(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        return {
            "strengths": ["Clear reasoning under mock evaluation", "Structured answers"],
            "gaps": ["Needs deeper system-level justification"],
            "next_focus": context.get("focus_skill") or "rag",
            "score": 72,
            "summary": "Mock debrief evaluation complete. Continue practicing open gaps.",
        }

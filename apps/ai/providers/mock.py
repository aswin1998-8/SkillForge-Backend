"""Deterministic mock AI provider for local/dev and tests."""

from __future__ import annotations

from typing import Any

from apps.ai.providers.base import AIProvider


def _eval_payload(stage: str = "FOUNDATION") -> dict[str, Any]:
    return {
        "evaluation": {
            "conceptual_accuracy": 0.7,
            "technical_depth": 0.55,
            "reasoning": 0.6,
            "problem_solving": 0.5,
        },
        "strengths": ["Understands core concepts"],
        "weaknesses": ["Needs deeper debugging intuition"],
        "misconceptions": [],
        "evidence": ["Mock evidence from answer evaluation"],
        "confidence": 0.8,
        "recommended_next_stage": "SCENARIO" if stage == "FOUNDATION" else stage,
        "overall_strength": "MODERATE",
    }


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

    def generate_question(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        stage = context.get("assessment_stage") or "FOUNDATION"
        skill = (context.get("skill") or {}).get("name") or "RAG"
        return {
            "stage": stage,
            "skill_slug": (context.get("skill") or {}).get("slug") or "rag",
            "difficulty": context.get("difficulty") or "MEDIUM",
            "question_type": "FREE_TEXT" if stage != "CODING" else "CODE",
            "prompt_text": (
                f"[{stage}] Mock question for {skill}: "
                "Explain how you would approach this in production and what you would validate first."
            ),
            "requirements": ["Be specific", "Call out trade-offs"],
            "constraints": ["Keep answer under 400 words"],
            "expected_behavior": "Clear reasoning with concrete steps",
            "evaluation_criteria": ["accuracy", "depth", "trade-offs"],
        }

    def evaluate_answer(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        return _eval_payload(context.get("assessment_stage") or "FOUNDATION")

    def evaluate_code(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        payload = _eval_payload(context.get("assessment_stage") or "CODING")
        payload["evaluation"]["problem_solving"] = 0.65
        return payload

    def generate_follow_up_question(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        return self.generate_question(prompt=prompt, context=context)

    def analyze_evidence(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        return {
            "summary": "Mock evidence summary across turns.",
            "highlights": ["Solid foundation", "Weaker debugging"],
        }

    def analyze_skill_gap(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        return {
            "explanations": [
                {
                    "skill_slug": "rag",
                    "explanation": "Mock: retrieval diagnosis needs more practice.",
                }
            ]
        }

    def analyze_transferable_skills(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        return {
            "transfers": [
                {
                    "from_skill_slug": "api-integration",
                    "to_skill_slug": "llm-apis",
                    "rationale": "HTTP client patterns transfer to LLM API design.",
                }
            ]
        }

    def generate_roadmap(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        eligible = context.get("eligible_steps") or []
        ordered_ids = [s.get("challenge_id") for s in eligible if s.get("challenge_id")]
        return {
            "ordered_challenge_ids": ordered_ids,
            "annotations": [
                {"challenge_id": cid, "note": "Mock prioritized for open gap"}
                for cid in ordered_ids[:5]
            ],
        }

    def evaluate_challenge_submission(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        return {
            **_eval_payload("CODING"),
            "correctness": 0.7,
            "code_quality": 0.6,
            "architecture": 0.55,
            "security": 0.5,
            "summary": "Mock challenge evaluation.",
        }

    def generate_stage_questions(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        stage = context.get("stage") or "FOUNDATIONAL"
        count = int(context.get("question_count") or 3)
        role = (context.get("current_role") or context.get("target_role") or "engineer")
        low = " (intro / low-stakes)" if context.get("low_stakes") else ""
        return {
            "questions": [
                {
                    "question_text": (
                        f"[{stage}]{low} Mock Q{i} for {role}: "
                        "Describe how you would approach this in a real system."
                    ),
                    "question_type": "CODE" if stage in {"CODING", "FIND_ISSUES"} else "FREE_TEXT",
                }
                for i in range(1, count + 1)
            ]
        }

    def generate_block_b_questions(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        areas = list(context.get("competency_areas") or [])
        role = context.get("target_role") or "target role"
        return {
            "questions": [
                {
                    "competency_area": area,
                    "question_text": (
                        f"[FOUNDATIONAL] (intro / low-stakes) Any exposure to "
                        f"{area} for {role}? Describe briefly what you know."
                    ),
                    "question_type": "FREE_TEXT",
                }
                for area in areas
            ]
        }

    def generate_block_a_competency_questions(
        self, *, prompt: str, context: dict[str, Any]
    ) -> dict[str, Any]:
        stage = context.get("stage") or "FOUNDATIONAL"
        areas = list(context.get("competency_areas") or [])
        role = context.get("current_role") or "engineer"
        return {
            "questions": [
                {
                    "competency_area": area,
                    "question_text": (
                        f"[{stage}] Mock assessment for {area} as a {role}: "
                        "Explain your approach with concrete detail."
                    ),
                    "question_type": "CODE" if stage in {"CODING", "FIND_ISSUES"} else "FREE_TEXT",
                }
                for area in areas
            ]
        }

    def classify_block_b_exposure(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        items = list(context.get("block_b_items") or [])
        classifications = []
        for item in items:
            text = str(item.get("answer_text") or "").strip().lower()
            # Mock: explicit "no exposure" / empty → false; "exposure:" prefix or
            # non-empty substantive answers → true unless marked no.
            if not text or text.startswith("no exposure") or text in {"n/a", "none", "idk"}:
                confirmed = False
            else:
                confirmed = True
            classifications.append(
                {
                    "question_id": int(item["question_id"]),
                    "competency_area": str(item.get("competency_area") or ""),
                    "exposure_confirmed": confirmed,
                }
            )
        return {"classifications": classifications}

    def generate_role_taxonomy(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        role = str(context.get("target_role") or context.get("role_name") or "Engineer").strip()
        learn = [str(x).strip() for x in (context.get("target_learn_skills") or []) if str(x).strip()]
        areas = [
            "fundamentals",
            "system_design",
            "debugging",
            "tooling",
        ]
        for skill in learn[:4]:
            key = skill.lower().replace(" ", "_").replace(".", "_")
            if key and key not in areas:
                areas.append(key)
        return {
            "role_name": role,
            "competency_areas": areas[:8],
        }

    def synthesize_diagnostic(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        goal = context.get("goal") or "sharpen_current"
        areas = list(context.get("competency_areas") or [])
        transfers = []
        if goal == "switch_role":
            # Default mock transfer maps to first taxonomy area when present so
            # gap-formula tests can override; otherwise a generic label.
            applies = areas[0] if areas else "Full-stack API boundary design"
            transfers = [
                {
                    "from_current_role": "Frontend component architecture",
                    "applies_to_target": applies,
                }
            ]
        return {
            "strengths": [
                {
                    "skill_area": "Core fundamentals",
                    "evidence": "Clear answers in Block A foundational stage",
                }
            ],
            "gaps": [
                {
                    "skill_area": "Production debugging",
                    "block": "A",
                    "severity": "moderate",
                }
            ],
            "transferable_skills": transfers,
            "roadmap": [
                {
                    "challenge_modality": "THEORY",
                    "topic": "Apply current strengths to a small target-role scenario",
                    "priority": 1,
                },
                {
                    "challenge_modality": "CODING",
                    "topic": "Hands-on practice for an identified gap",
                    "priority": 2,
                },
                {
                    "challenge_modality": "DIAGNOSE",
                    "topic": "Debug a realistic failure mode",
                    "priority": 3,
                },
            ],
        }

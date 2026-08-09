"""Prompt builders for adaptive assessment."""

from __future__ import annotations

import json
from typing import Any


def _dump(data: Any) -> str:
    return json.dumps(data, indent=2, default=str)


def build_generate_question_prompt(*, context: dict[str, Any]) -> str:
    return f"""Generate one assessment question as JSON with keys:
stage, skill_slug, difficulty, question_type, prompt_text, requirements, constraints,
expected_behavior, evaluation_criteria.

SYSTEM CONTEXT
{_dump(context)}

Rules:
- Match assessment_stage and skill.
- Prefer realistic production scenarios for SCENARIO/DEBUGGING.
- For CODING/CODE_REVIEW include concrete requirements.
- Do not include answers.
"""


def build_evaluate_answer_prompt(*, context: dict[str, Any], answer: str) -> str:
    return f"""Evaluate the user answer. Return JSON with:
evaluation {{conceptual_accuracy, technical_depth, reasoning, problem_solving}} each 0-1,
strengths, weaknesses, misconceptions, evidence (string list), confidence 0-1,
recommended_next_stage, overall_strength (STRONG|MODERATE|WEAK).

SYSTEM CONTEXT
{_dump(context)}

USER ANSWER START
{answer[:8000]}
USER ANSWER END
"""


def build_transferable_skills_prompt(*, context: dict[str, Any]) -> str:
    return f"""Propose transferable skill mappings as JSON:
{{"transfers":[{{"from_skill_slug","to_skill_slug","rationale"}}]}}

Only use skill slugs from context.current_skills and context.target_skills.

SYSTEM CONTEXT
{_dump(context)}
"""


def build_skill_gap_prompt(*, context: dict[str, Any]) -> str:
    return f"""Explain each classified skill gap. Return JSON:
{{"explanations":[{{"skill_slug","explanation"}}]}}

Do not change classifications; explain only.

SYSTEM CONTEXT
{_dump(context)}
"""


def build_roadmap_prompt(*, context: dict[str, Any]) -> str:
    return f"""Rank eligible challenges. Return JSON:
{{"ordered_challenge_ids":[...], "annotations":[{{"challenge_id","note"}}]}}

Only use challenge ids from context.eligible_steps.

SYSTEM CONTEXT
{_dump(context)}
"""


def build_challenge_eval_prompt(*, context: dict[str, Any], submission: dict[str, Any]) -> str:
    return f"""Evaluate the challenge submission. Return JSON with evaluation dimensions 0-1,
strengths, weaknesses, misconceptions, evidence, confidence, correctness, code_quality,
architecture, security, summary, overall_strength.

SYSTEM CONTEXT
{_dump(context)}

USER SUBMISSION START
{_dump(submission)[:12000]}
USER SUBMISSION END
"""


def build_stage_questions_prompt(*, context: dict[str, Any]) -> str:
    count = context.get("question_count") or 3
    block = context.get("block") or "A"
    stage = context.get("stage") or "FOUNDATIONAL"
    low_stakes = bool(context.get("low_stakes"))
    stakes = (
        "These are LOW-STAKES foundational probes for a target role the user may not know yet. "
        "Do not assume expertise. Keep questions introductory."
        if low_stakes
        else "Assess the user's current-role competence honestly."
    )
    return f"""Generate exactly {count} assessment questions for Block {block} stage {stage}.
Return JSON only:
{{"questions":[{{"question_text":"...","question_type":"FREE_TEXT|CODE"}}]}}

{stakes}

Adapt to the running transcript in context.transcript when present (target weak areas).
Do not include answers.

SYSTEM CONTEXT
{_dump(context)}
"""


def build_block_b_questions_prompt(*, context: dict[str, Any]) -> str:
    areas = context.get("competency_areas") or []
    return f"""Generate exactly one LOW-STAKES foundational question per competency_area.
Return JSON only:
{{"questions":[{{"competency_area":"...","question_text":"...","question_type":"FREE_TEXT"}}]}}

Rules:
- competency_areas list is authoritative: {areas}
- Produce exactly one question for EACH listed competency_area (same string labels)
- Probe for ANY exposure at all — not mastery
- Do NOT invent extra competencies or omit any listed area
- Do not include answers

SYSTEM CONTEXT
{_dump(context)}
"""


def build_block_a_competency_questions_prompt(*, context: dict[str, Any]) -> str:
    areas = context.get("competency_areas") or []
    stage = context.get("stage") or "FOUNDATIONAL"
    return f"""Generate exactly one assessment question per competency_area for Block A stage {stage}.
Return JSON only:
{{"questions":[{{"competency_area":"...","question_text":"...","question_type":"FREE_TEXT|CODE"}}]}}

Rules:
- competency_areas list is authoritative: {areas}
- Produce exactly one question for EACH listed competency_area (same string labels)
- Match question style to stage {stage} (foundational / scenario / debugging / coding / find-issues)
- Assess real competence for the user's current role — not low-stakes exposure probes
- Do NOT invent extra competencies or omit any listed area
- Do not include answers

SYSTEM CONTEXT
{_dump(context)}
"""


def build_block_b_exposure_prompt(*, context: dict[str, Any]) -> str:
    return f"""Classify whether each Block B answer shows ANY exposure to the competency.
Return JSON only:
{{"classifications":[{{"question_id": number, "competency_area": string, "exposure_confirmed": true|false}}]}}

Rules:
- exposure_confirmed=true if the answer shows any real familiarity or prior contact
- exposure_confirmed=false if blank, unsure, or clearly no exposure
- Include every item from context.block_b_items exactly once
- JSON only

SYSTEM CONTEXT
{_dump(context)}
"""


def build_role_taxonomy_prompt(*, context: dict[str, Any]) -> str:
    role = context.get("target_role") or context.get("role_name") or "the target role"
    learn = context.get("target_learn_skills") or []
    return f"""Propose a competency taxonomy for the target role.
Return JSON only:
{{"role_name": string, "competency_areas": [string, ...]}}

Rules:
- role_name should be a clean display name for: {role}
- competency_areas: 4 to 8 distinct foundational competency keys for Block B exposure checks
- Prefer short snake_case or short phrase labels (e.g. "api_design", "system_design")
- Cover core skills for the role; incorporate learn-stack hints when present: {learn}
- Do not include soft-skill fluff; keep technical/role competencies
- JSON only

SYSTEM CONTEXT
{_dump(context)}
"""


def build_diagnostic_synthesis_prompt(*, context: dict[str, Any]) -> str:
    return f"""You are synthesizing a diagnostic assessment transcript.
Return a SINGLE JSON object only — no markdown, no prose outside JSON — with this exact shape:
{{
  "strengths": [{{"skill_area": string, "evidence": string}}],
  "gaps": [{{"skill_area": string, "block": "A", "severity": string}}],
  "transferable_skills": [{{"from_current_role": string, "applies_to_target": string}}],
  "roadmap": [{{"challenge_modality": string, "topic": string, "priority": number}}]
}}

Rules:
- challenge_modality MUST be one of: THEORY, CODING, RESEARCH, DEFEND, DIAGNOSE, ARCHITECT, EXPLAIN_CODE, USE_AI, COMMUNICATE
- If goal is sharpen_current, transferable_skills MUST be []
- If goal is switch_role, transferable_skills must identify real Block A competencies that carry to the target role
- For transferable_skills.applies_to_target, prefer exact competency_area labels from context.competency_areas when they apply
- gaps: ONLY Block A gaps from the transcript. Do NOT invent Block B gaps — the backend computes those deterministically
- roadmap: early items should leverage proven Block A strengths (applied in B context when switching) for early wins
- Use the full transcript in context

SYSTEM CONTEXT
{_dump(context)}
"""

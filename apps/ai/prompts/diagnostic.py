from __future__ import annotations

import json
from typing import Any

from apps.ai.prompts.common import json_only_instruction, wrap_user_submission


def build_diagnostic_prompt(
    *,
    diagnostic_title: str,
    questions_and_answers: list[dict[str, Any]],
    skills: list[dict[str, Any]],
) -> str:
    qa_blob = json.dumps(questions_and_answers, indent=2)
    skills_blob = json.dumps(skills, indent=2)
    return f"""Analyze this SkillForge diagnostic attempt.

Diagnostic: {diagnostic_title}

Relevant skills catalog:
{skills_blob}

{wrap_user_submission(qa_blob)}

Produce JSON with keys:
- strengths: string[]
- gaps: array of {{skill_slug, severity, notes}}
- evidence: array of {{source, detail}}
- skill_findings: array of {{skill_slug, level, confidence}}
- recommended_focus: string (skill_slug)
- summary: string

{json_only_instruction()}
"""

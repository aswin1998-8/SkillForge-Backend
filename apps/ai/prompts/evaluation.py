from __future__ import annotations

import json
from typing import Any

from apps.ai.prompts.common import json_only_instruction, wrap_user_submission


def build_evaluation_prompt(
    *,
    challenge_title: str,
    modality: str,
    submission_summary: str,
    qa_pairs: list[dict[str, Any]],
    focus_skill: str = "",
) -> str:
    qa_blob = json.dumps(qa_pairs, indent=2)
    return f"""Evaluate this SkillForge debrief session.

Challenge: {challenge_title}
Modality: {modality}
Focus skill: {focus_skill or "general"}

Submission:
{wrap_user_submission(submission_summary)}

Debrief Q&A:
{qa_blob}

Produce JSON with keys:
- strengths: string[]
- gaps: string[]
- next_focus: string
- score: integer 0-100
- summary: string

{json_only_instruction()}
"""

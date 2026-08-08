from __future__ import annotations

import json
from typing import Any

from apps.ai.prompts.common import json_only_instruction, wrap_user_submission


def build_debrief_question_prompt(
    *,
    challenge_title: str,
    modality: str,
    submission_summary: str,
    prior_qa: list[dict[str, Any]],
    next_order: int,
    max_questions: int,
    focus_skill: str = "",
) -> str:
    prior_blob = json.dumps(prior_qa, indent=2)
    return f"""Generate the next Socratic debrief question for a SkillForge challenge.

Challenge: {challenge_title}
Modality: {modality}
Focus skill: {focus_skill or "general"}
Question number: {next_order} of {max_questions}

Submission summary:
{wrap_user_submission(submission_summary)}

Prior Q&A:
{prior_blob}

Produce JSON with keys:
- prompt_text: string
- focus_area: string

{json_only_instruction()}
"""

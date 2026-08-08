from __future__ import annotations


USER_SUBMISSION_START = "<<<USER_SUBMISSION_START>>>"
USER_SUBMISSION_END = "<<<USER_SUBMISSION_END>>>"


def wrap_user_submission(content: str) -> str:
    return f"{USER_SUBMISSION_START}\n{content}\n{USER_SUBMISSION_END}"


def json_only_instruction() -> str:
    return (
        "Return ONLY a valid JSON object. "
        "Do not wrap it in markdown fences. "
        "Do not include commentary outside the JSON."
    )

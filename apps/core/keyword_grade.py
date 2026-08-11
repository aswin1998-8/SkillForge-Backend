"""Deterministic keyword / rubric-point grading shared by diagnostics and challenges."""

from __future__ import annotations

import re

_TOKEN_RE = re.compile(r"[a-z0-9_+#.-]{3,}")
_PASS_THRESHOLD = 0.5


def normalize_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def meaningful_tokens(value: str) -> list[str]:
    return _TOKEN_RE.findall(normalize_text(value))


def point_matched(*, answer_norm: str, answer_tokens: set[str], point: str) -> bool:
    """
    A rubric point matches if:
    - the full normalized phrase appears as a substring, OR
    - a majority of its meaningful tokens (len >= 3) appear in the answer.
    """
    point_norm = normalize_text(point)
    if not point_norm:
        return False
    if point_norm in answer_norm:
        return True
    tokens = meaningful_tokens(point_norm)
    if not tokens:
        return False
    hits = sum(1 for t in tokens if t in answer_tokens)
    return hits >= max(1, (len(tokens) + 1) // 2)


def grade_open_ended_keywords(
    *,
    answer_text: str,
    rubric_points: list[str] | None = None,
    reference_text: str | None = None,
    pass_threshold: float = _PASS_THRESHOLD,
) -> tuple[bool, float, dict]:
    """
    Returns (is_correct, score 0..1, grading_detail).
    Prefer rubric_points; fall back to token overlap with reference_text.
    """
    answer_norm = normalize_text(answer_text)
    answer_tokens = set(meaningful_tokens(answer_norm))
    points = [str(p).strip() for p in (rubric_points or []) if str(p).strip()]

    if points:
        point_results = []
        matched_count = 0
        for point in points:
            matched = point_matched(
                answer_norm=answer_norm,
                answer_tokens=answer_tokens,
                point=point,
            )
            if matched:
                matched_count += 1
            point_results.append({"point": point, "matched": matched})
        score = matched_count / len(points)
        is_correct = score >= pass_threshold
        return is_correct, score, {
            "method": "keyword_rubric",
            "score": score,
            "threshold": pass_threshold,
            "points": point_results,
        }

    # Fallback: overlap with reference answer tokens
    ref_tokens = meaningful_tokens(reference_text or "")
    if not ref_tokens:
        return False, 0.0, {
            "method": "keyword_rubric",
            "score": 0.0,
            "threshold": pass_threshold,
            "points": [],
            "error": "no_rubric_or_reference",
        }

    unique_ref = list(dict.fromkeys(ref_tokens))
    hits = sum(1 for t in unique_ref if t in answer_tokens)
    score = hits / len(unique_ref) if unique_ref else 0.0
    is_correct = score >= pass_threshold
    return is_correct, score, {
        "method": "keyword_reference_overlap",
        "score": score,
        "threshold": pass_threshold,
        "matched_tokens": hits,
        "total_tokens": len(unique_ref),
    }

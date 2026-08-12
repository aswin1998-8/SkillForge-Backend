"""Deterministic keyword / rubric-point grading shared by diagnostics and challenges."""

from __future__ import annotations

import re

_TOKEN_RE = re.compile(r"[a-z0-9_+#.-]{3,}")
_PASS_THRESHOLD = 0.5

# Instructional / filler words that appear in rubric criteria but not student answers.
_RUBRIC_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "with",
        "at",
        "least",
        "of",
        "to",
        "for",
        "in",
        "on",
        "is",
        "are",
        "be",
        "that",
        "this",
        "from",
        "into",
        "about",
        "than",
        "then",
        "when",
        "where",
        "which",
        "who",
        "how",
        "what",
        "why",
        "your",
        "you",
        "their",
        "them",
        "they",
        "more",
        "most",
        "some",
        "any",
        "all",
        "both",
        "each",
        "such",
        "using",
        "use",
        "used",
        "uses",
        "clear",
        "good",
        "proper",
        "appropriate",
        "high",
        "level",
        "likely",
        "primary",
        "concrete",
        "basic",
        "basics",
        "still",
        "fuzzy",
        "weak",
        "needs",
        "need",
        "practice",
        "compares",
        "compare",
        "comparing",
        "comparison",
        "includes",
        "include",
        "including",
        "explains",
        "explain",
        "explained",
        "describes",
        "describe",
        "shows",
        "show",
        "mentions",
        "mention",
        "provides",
        "provide",
        "demonstrates",
        "demonstrate",
        "identifies",
        "identify",
        "proposes",
        "propose",
        "proposed",
        "states",
        "state",
        "lists",
        "list",
        "covers",
        "cover",
        "addresses",
        "address",
        "presents",
        "present",
        "discusses",
        "discuss",
        "calls",
        "call",
        "out",
        "handles",
        "handle",
        "computes",
        "compute",
        "correctly",
        "incomplete",
        "complete",
        "credible",
        "official",
        "relevant",
        "enough",
        "should",
        "must",
        "have",
        "has",
        "had",
        "does",
        "did",
        "will",
        "would",
        "could",
        "can",
        "may",
        "might",
        "cause",
        "causes",
        "while",
        "between",
        "among",
        "across",
        "under",
        "over",
        "after",
        "before",
        "during",
        "via",
        "per",
        "its",
        "itself",
        "also",
        "just",
        "only",
        "even",
        "very",
        "too",
        "not",
        "without",
        "within",
        "every",
        "other",
        "another",
        "same",
        "different",
    }
)

_CITATION_CRITERION_MARKERS = (
    "source",
    "sources",
    "cite",
    "cites",
    "citation",
    "docs",
    "doc",
    "documentation",
    "reference",
    "references",
    "link",
)
_COMPARISON_CRITERION_MARKERS = (
    "two",
    "compare",
    "compares",
    "comparison",
    "versus",
    "trade-off",
    "trade-offs",
    "tradeoff",
    "tradeoffs",
    "approaches",
    "strategies",
)


def normalize_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def _stem_token(token: str) -> str:
    """Light normalize so trade-offs ≈ trade-off, approaches ≈ approach."""
    t = token.lower().strip(".-_")
    if len(t) > 4 and t.endswith("ies"):
        return t[:-3] + "y"
    if len(t) > 4 and t.endswith("es"):
        return t[:-2]
    if len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
        return t[:-1]
    return t


def meaningful_tokens(value: str) -> list[str]:
    return _TOKEN_RE.findall(normalize_text(value))


def content_tokens(value: str) -> list[str]:
    """Meaningful tokens with stopwords removed and light stemming."""
    out: list[str] = []
    seen: set[str] = set()
    for raw in meaningful_tokens(value):
        if raw in _RUBRIC_STOPWORDS:
            continue
        stemmed = _stem_token(raw)
        if stemmed in _RUBRIC_STOPWORDS or len(stemmed) < 3:
            continue
        if stemmed not in seen:
            seen.add(stemmed)
            out.append(stemmed)
    return out


def _answer_token_set(answer_norm: str) -> set[str]:
    tokens: set[str] = set()
    for raw in meaningful_tokens(answer_norm):
        tokens.add(raw)
        tokens.add(_stem_token(raw))
    return tokens


def _is_citation_criterion(point_norm: str) -> bool:
    return any(m in point_norm for m in _CITATION_CRITERION_MARKERS)


def _is_comparison_criterion(point_norm: str) -> bool:
    return any(m in point_norm for m in _COMPARISON_CRITERION_MARKERS)


def _has_citation_signal(answer_norm: str) -> bool:
    if re.search(r"https?://", answer_norm):
        return True
    citation_signals = (
        "documentation",
        "docs.",
        "mdn",
        "next.js",
        "according to",
        "official doc",
        "rfc ",
        "developer.mozilla",
        "react.dev",
        "django docs",
        "fastapi.tiangolo",
    )
    if any(s in answer_norm for s in citation_signals):
        return True
    if re.search(r"\b[a-z0-9.+#-]+\s+[—\-–]\s+\w+", answer_norm):
        return True
    return False


def _has_comparison_signal(answer_norm: str) -> bool:
    if re.search(r"\bstrategy\s*1\b", answer_norm) and re.search(
        r"\bstrategy\s*2\b", answer_norm
    ):
        return True
    if re.search(r"\bapproach\s*1\b", answer_norm) and re.search(
        r"\bapproach\s*2\b", answer_norm
    ):
        return True
    if re.search(r"\boption\s*[a1]\b", answer_norm) and re.search(
        r"\boption\s*[b2]\b", answer_norm
    ):
        return True
    if re.search(
        r"\bvs\.?\b|\bversus\b|compared to|on the other hand|alternatively",
        answer_norm,
    ):
        return True
    if re.search(r"\b(two|2)\s+(strategies|approaches|options|methods)\b", answer_norm):
        return True
    return False


def _majority_token_hit(*, tokens: list[str], answer_tokens: set[str]) -> bool:
    if not tokens:
        return False
    hits = sum(1 for t in tokens if t in answer_tokens)
    return hits >= max(1, (len(tokens) + 1) // 2)


def point_matched(
    *,
    answer_norm: str,
    answer_tokens: set[str],
    point: str,
    hint: str = "",
    reference_tokens: set[str] | None = None,
) -> bool:
    """
    A rubric point matches if:
    - the full normalized phrase appears as a substring, OR
    - a majority of its content tokens appear in the answer, OR
    - a majority of hint / strength tokens appear, OR
    - anchored tokens shared with the model answer appear, OR
    - criteria heuristics fire (comparison / citation style rubrics).
    """
    point_norm = normalize_text(point)
    if not point_norm:
        return False
    if point_norm in answer_norm:
        return True

    if _is_citation_criterion(point_norm) and _has_citation_signal(answer_norm):
        return True
    if _is_comparison_criterion(point_norm) and _has_comparison_signal(answer_norm):
        return True

    point_tokens = content_tokens(point_norm)
    if not point_tokens:
        point_tokens = [_stem_token(t) for t in meaningful_tokens(point_norm)]
        point_tokens = [t for t in point_tokens if t and t not in _RUBRIC_STOPWORDS]

    if _majority_token_hit(tokens=point_tokens, answer_tokens=answer_tokens):
        return True

    hint_norm = normalize_text(hint)
    if hint_norm:
        hint_tokens = content_tokens(hint_norm)
        if _majority_token_hit(tokens=hint_tokens, answer_tokens=answer_tokens):
            return True

    # Anchor to model-answer vocabulary so instructional wording doesn't dominate.
    if reference_tokens and point_tokens:
        anchored = [t for t in point_tokens if t in reference_tokens]
        if len(anchored) >= 1 and _majority_token_hit(
            tokens=anchored, answer_tokens=answer_tokens
        ):
            return True

    return False


def _reference_overlap_score(
    *,
    answer_tokens: set[str],
    reference_text: str,
) -> tuple[float, int, int]:
    ref_tokens = content_tokens(reference_text) or [
        _stem_token(t)
        for t in meaningful_tokens(reference_text)
        if _stem_token(t) not in _RUBRIC_STOPWORDS
    ]
    unique_ref = list(dict.fromkeys(ref_tokens))
    if not unique_ref:
        return 0.0, 0, 0
    hits = sum(1 for t in unique_ref if t in answer_tokens)
    return hits / len(unique_ref), hits, len(unique_ref)


def grade_open_ended_keywords(
    *,
    answer_text: str,
    rubric_points: list[str] | None = None,
    rubric_hints: list[str] | None = None,
    reference_text: str | None = None,
    pass_threshold: float = _PASS_THRESHOLD,
) -> tuple[bool, float, dict]:
    """
    Returns (is_correct, score 0..1, grading_detail).

    Grades instructional rubric criteria against the answer, strength hints, and
    the model/reference answer. When both rubric and reference exist, the final
    score is the max of the two so a solid answer is not zeroed by wording mismatch.
    """
    answer_norm = normalize_text(answer_text)
    answer_tokens = _answer_token_set(answer_norm)
    points = [str(p).strip() for p in (rubric_points or []) if str(p).strip()]
    hints = [str(h or "").strip() for h in (rubric_hints or [])]
    reference = (reference_text or "").strip()
    reference_tokens = (
        _answer_token_set(normalize_text(reference)) if reference else set()
    )

    rubric_score = 0.0
    point_results: list[dict] = []
    method = "keyword_rubric"

    if points:
        matched_count = 0
        for idx, point in enumerate(points):
            hint = hints[idx] if idx < len(hints) else ""
            matched = point_matched(
                answer_norm=answer_norm,
                answer_tokens=answer_tokens,
                point=point,
                hint=hint,
                reference_tokens=reference_tokens or None,
            )
            if matched:
                matched_count += 1
            point_results.append({"point": point, "matched": matched})
        rubric_score = matched_count / len(points)

    ref_score = 0.0
    ref_hits = 0
    ref_total = 0
    if reference:
        ref_score, ref_hits, ref_total = _reference_overlap_score(
            answer_tokens=answer_tokens,
            reference_text=reference,
        )

    if points and reference:
        score = max(rubric_score, ref_score)
        method = (
            "keyword_rubric"
            if rubric_score >= ref_score
            else "keyword_reference_overlap"
        )
    elif points:
        score = rubric_score
        method = "keyword_rubric"
    elif reference:
        score = ref_score
        method = "keyword_reference_overlap"
    else:
        return False, 0.0, {
            "method": "keyword_rubric",
            "score": 0.0,
            "threshold": pass_threshold,
            "points": [],
            "error": "no_rubric_or_reference",
        }

    is_correct = score >= pass_threshold
    detail: dict = {
        "method": method,
        "score": score,
        "threshold": pass_threshold,
        "points": point_results,
    }
    if reference:
        detail["reference_overlap"] = {
            "score": ref_score,
            "matched_tokens": ref_hits,
            "total_tokens": ref_total,
        }
        if points:
            detail["rubric_score"] = rubric_score
    return is_correct, score, detail

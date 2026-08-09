"""Deterministic skill scoring from evidence (backend source of truth)."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from django.conf import settings


STAGES = ("FOUNDATION", "SCENARIO", "DEBUGGING", "CODING", "CODE_REVIEW")


def score_weights() -> dict[str, float]:
    weights = dict(getattr(settings, "AI_SCORE_WEIGHTS", {}))
    total = sum(weights.get(s, 0.0) for s in STAGES) or 1.0
    return {s: float(weights.get(s, 0.0)) / total for s in STAGES}


def mean_dimensions(evaluation: dict[str, Any] | None) -> float:
    if not evaluation:
        return 0.0
    keys = (
        "conceptual_accuracy",
        "technical_depth",
        "reasoning",
        "problem_solving",
    )
    vals = [float(evaluation.get(k, 0.0) or 0.0) for k in keys]
    return sum(vals) / len(vals)


def compute_skill_scores(evidence_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """
    evidence_rows items:
      {skill_slug, stage, score (0-1), evaluation optional}
    Returns per skill: {score, breakdown, samples}
    """
    weights = score_weights()
    by_skill: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))

    for row in evidence_rows:
        slug = row.get("skill_slug") or ""
        stage = (row.get("stage") or "FOUNDATION").upper()
        if not slug or stage not in weights:
            continue
        score = row.get("score")
        if score is None:
            score = mean_dimensions(row.get("evaluation") or {})
        by_skill[slug][stage].append(float(score))

    results: dict[str, dict[str, Any]] = {}
    for slug, stages in by_skill.items():
        breakdown: dict[str, float] = {}
        weighted = 0.0
        used_weight = 0.0
        for stage, weight in weights.items():
            samples = stages.get(stage) or []
            if not samples:
                continue
            avg = sum(samples) / len(samples)
            breakdown[stage] = round(avg, 4)
            weighted += avg * weight
            used_weight += weight
        final = weighted / used_weight if used_weight else 0.0
        results[slug] = {
            "score": round(final, 4),
            "breakdown": breakdown,
            "sample_count": sum(len(v) for v in stages.values()),
        }
    return results


def classify_from_score(score: float) -> str:
    strong = float(getattr(settings, "AI_STRONG_THRESHOLD", 0.7))
    weak = float(getattr(settings, "AI_WEAK_THRESHOLD", 0.4))
    if score >= strong:
        return "STRONG"
    if score <= weak:
        return "WEAK"
    return "MODERATE"


def classify_gap_status(*, score: float, importance: int | None) -> str:
    """Backend-owned gap labels for UI."""
    strength = classify_from_score(score)
    imp = importance or 3
    if strength == "STRONG":
        return "STRONG"
    if strength == "MODERATE":
        return "DEVELOPING"
    if imp >= 4:
        return "CRITICAL_GAP"
    return "GAP"

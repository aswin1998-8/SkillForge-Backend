"""Match learner-reported issues against planted issue locations."""

from __future__ import annotations

SEVERITY_RANK = {
    "low": 0,
    "medium": 1,
    "high": 2,
    "critical": 3,
}

VALID_CATEGORIES = {"bug", "edge_case", "style", "security"}


def _norm_path(path: str) -> str:
    return str(path or "").strip().lstrip("./").replace("\\", "/")


def _as_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _ranges_overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    start_a, end_a = min(a_start, a_end), max(a_start, a_end)
    start_b, end_b = min(b_start, b_end), max(b_start, b_end)
    return start_a <= end_b and start_b <= end_a


def _severity_credit(expected: str, reported: str) -> float:
    exp = SEVERITY_RANK.get(str(expected or "").strip().lower())
    got = SEVERITY_RANK.get(str(reported or "").strip().lower())
    if exp is None or got is None:
        return 0.5
    if exp == got:
        return 1.0
    if abs(exp - got) == 1:
        return 0.5
    return 0.0


def grade_planted_issues(
    *,
    planted: list[dict],
    reported: list[dict],
    pass_threshold: float = 0.5,
) -> dict:
    planted_clean = [p for p in planted if isinstance(p, dict)]
    reported_clean = [r for r in reported if isinstance(r, dict)]
    if not planted_clean:
        return {
            "method": "issue_location_match",
            "score": 0.0,
            "is_correct": False,
            "error": "no_planted_issues_configured",
            "matched": 0,
            "total": 0,
        }

    used_reported: set[int] = set()
    matches: list[dict] = []
    credits: list[float] = []

    for planted_issue in planted_clean:
        best_idx = None
        best_credit = 0.0
        p_file = _norm_path(str(planted_issue.get("file") or ""))
        p_start = _as_int(planted_issue.get("start_line"), 1)
        p_end = _as_int(planted_issue.get("end_line"), p_start)
        p_cat = str(planted_issue.get("category") or "").strip().lower()

        for idx, report in enumerate(reported_clean):
            if idx in used_reported:
                continue
            r_file = _norm_path(str(report.get("file") or ""))
            if p_file and r_file and p_file != r_file:
                continue
            r_start = _as_int(report.get("start_line"), 0)
            r_end = _as_int(report.get("end_line"), r_start)
            if not _ranges_overlap(p_start, p_end, r_start, r_end):
                continue
            r_cat = str(report.get("category") or "").strip().lower()
            if p_cat and r_cat != p_cat:
                continue
            credit = _severity_credit(
                str(planted_issue.get("severity") or ""),
                str(report.get("severity") or ""),
            )
            if credit > best_credit:
                best_credit = credit
                best_idx = idx

        if best_idx is not None and best_credit > 0:
            used_reported.add(best_idx)
            credits.append(best_credit)
            matches.append(
                {
                    "planted_id": planted_issue.get("id"),
                    "reported_index": best_idx,
                    "credit": best_credit,
                }
            )
        else:
            credits.append(0.0)

    total = len(planted_clean)
    score = sum(credits) / total if total else 0.0
    return {
        "method": "issue_location_match",
        "score": round(score, 4),
        "is_correct": score >= pass_threshold,
        "matched": len(matches),
        "total": total,
        "matches": matches,
        "reported_count": len(reported_clean),
    }

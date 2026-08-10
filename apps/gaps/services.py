"""Gap upsert, list, and analysis helpers."""

from __future__ import annotations

from typing import Any

from django.db import transaction

from apps.diagnostics.models import DiagnosticRoadmapItem, DiagnosticSession
from apps.gaps.models import GapEvidence, UserSkillGap
from apps.gaps.serializers import UserSkillGapSerializer
from apps.roles.models import Skill
from apps.users.models import User


@transaction.atomic
def upsert_user_skill_gap(
    *,
    user: User,
    skill: Skill,
    status: str = UserSkillGap.Status.NOT_STARTED,
    evidence_source_type: str | None = None,
    evidence_source_id: str | None = None,
    evidence_summary: str = "",
) -> UserSkillGap:
    gap, created = UserSkillGap.objects.get_or_create(
        user=user,
        skill=skill,
        defaults={"status": status},
    )
    if not created and gap.status != status:
        reopen = (
            gap.status == UserSkillGap.Status.CLOSED
            and status != UserSkillGap.Status.CLOSED
        )
        close = status == UserSkillGap.Status.CLOSED
        progress = (
            gap.status == UserSkillGap.Status.NOT_STARTED
            and status == UserSkillGap.Status.IN_PROGRESS
        )
        if reopen or close or progress:
            gap.status = status
            gap.save(update_fields=["status", "updated_at"])

    if evidence_source_type:
        GapEvidence.objects.create(
            user_skill_gap=gap,
            source_type=evidence_source_type,
            source_id=evidence_source_id or "",
            summary=evidence_summary,
        )
    return gap


def list_user_gaps(user: User, *, include_closed: bool = False):
    qs = UserSkillGap.objects.filter(user=user).select_related("skill").prefetch_related("evidence")
    if not include_closed:
        qs = qs.exclude(status=UserSkillGap.Status.CLOSED)
    return qs


def _synthesis_gap_index(session: DiagnosticSession | None) -> dict[str, dict]:
    if session is None:
        return {}
    index: dict[str, dict] = {}
    for gap in (session.synthesis or {}).get("gaps") or []:
        area = str(gap.get("skill_area") or "").strip().lower().replace(" ", "_")
        if area:
            index[area] = gap
    return index


def _topic_challenge_map(user: User) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for topic, challenge_id in (
        DiagnosticRoadmapItem.objects.filter(user=user, challenge_id__isnull=False)
        .order_by("priority", "id")
        .values_list("topic", "challenge_id")
    ):
        key = str(topic or "").strip().lower().replace(" ", "_")
        if key and key not in mapping:
            mapping[key] = int(challenge_id)
    return mapping


def enrich_gap_rows(
    rows: list[dict[str, Any]],
    *,
    synth_index: dict[str, dict],
    topic_challenges: dict[str, int],
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        slug = str((item.get("skill") or {}).get("slug") or "").strip().lower()
        match = synth_index.get(slug) or {}
        if match:
            item["severity"] = match.get("severity") or item.get("severity")
            item["fragment"] = match.get("fragment") or item.get("fragment")
            item["skill_area"] = match.get("skill_area") or slug
        else:
            item.setdefault("severity", None)
            item.setdefault("fragment", None)
            item.setdefault("skill_area", slug)
        item["challenge_id"] = topic_challenges.get(slug)
        evidence = item.get("evidence") or []
        item["latest_evidence_summary"] = (
            evidence[0].get("summary") if evidence else item.get("fragment")
        )
        enriched.append(item)
    return enriched


def _severity_key(value: object) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"high", "medium", "low"}:
        return raw
    return "unknown"


_SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2, "unknown": 3}
_SEVERITY_CURRENT_PENALTY = {"high": 0.05, "medium": 0.02, "low": 0.0, "unknown": 0.0}


def _status_score(status: object, severity: object = None) -> float:
    s = str(status or "").upper()
    if s == UserSkillGap.Status.CLOSED:
        base = 1.0
    elif s == UserSkillGap.Status.IN_PROGRESS:
        base = 0.45
    else:
        base = 0.15
    penalty = _SEVERITY_CURRENT_PENALTY.get(_severity_key(severity), 0.0)
    if s == UserSkillGap.Status.CLOSED:
        return base
    return max(0.05, round(base - penalty, 2))


def _progress_percent(status: object) -> int:
    s = str(status or "").upper()
    if s == UserSkillGap.Status.CLOSED:
        return 100
    if s == UserSkillGap.Status.IN_PROGRESS:
        return 45
    return 0


def _human_label(key: str) -> str:
    return (key or "").replace("_", " ").strip().title() or "Skill"


def _build_radar_axes(
    open_rows: list[dict[str, Any]],
    closed_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_key: dict[str, dict[str, Any]] = {}
    for row in closed_rows + open_rows:
        key = str(row.get("skill_area") or (row.get("skill") or {}).get("slug") or "").strip().lower()
        if not key:
            continue
        # Prefer open/in-progress status over older closed when both exist for same key.
        existing = by_key.get(key)
        if existing and existing.get("status") != UserSkillGap.Status.CLOSED:
            continue
        by_key[key] = row

    # Prefer open gaps first, then recently closed, capped at 6.
    ordered_keys: list[str] = []
    for row in open_rows:
        key = str(row.get("skill_area") or "").strip().lower()
        if key and key not in ordered_keys:
            ordered_keys.append(key)
    for row in closed_rows:
        key = str(row.get("skill_area") or "").strip().lower()
        if key and key not in ordered_keys:
            ordered_keys.append(key)
    ordered_keys = ordered_keys[:6]

    axes: list[dict[str, Any]] = []
    for key in ordered_keys:
        row = by_key.get(key) or {}
        skill_name = (row.get("skill") or {}).get("name") or _human_label(key)
        axes.append(
            {
                "key": key,
                "label": skill_name,
                "current": _status_score(row.get("status"), row.get("severity")),
                "target": 1.0,
            }
        )
    return axes


def _collect_market_trends(
    session: DiagnosticSession | None,
    area_keys: list[str],
) -> list[dict[str, Any]]:
    trends: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(label: str, stat_text: str, source_name: str = "", source_date: str = "") -> None:
        dedupe = f"{label}|{stat_text}".lower()
        if not stat_text or dedupe in seen:
            return
        seen.add(dedupe)
        trends.append(
            {
                "label": label,
                "stat_text": stat_text,
                "source_name": source_name or "",
                "source_date": source_date or "",
            }
        )

    if session is not None:
        synthesis = session.synthesis or {}
        for bucket in ("gaps", "strengths"):
            for item in synthesis.get(bucket) or []:
                area = str(item.get("skill_area") or "").strip()
                label = _human_label(area) if area else "Skill"
                for ev in item.get("market_evidence") or []:
                    add(
                        label,
                        str(ev.get("stat_text") or "").strip(),
                        str(ev.get("source_name") or "").strip(),
                        str(ev.get("source_date") or "").strip(),
                    )

    from apps.diagnostics.models import MarketEvidence

    for key in area_keys[:8]:
        for row in MarketEvidence.objects.filter(competency_area=key, is_active=True)[:2]:
            add(
                _human_label(key),
                row.stat_text,
                row.source_name,
                row.source_date or "",
            )

    return trends[:6]


def build_gap_analysis(user: User) -> dict[str, Any]:
    completed_diagnostic = (
        DiagnosticSession.objects.filter(
            user=user,
            status=DiagnosticSession.Status.COMPLETED,
        )
        .order_by("-completed_at", "-id")
        .first()
    )
    synth_index = _synthesis_gap_index(completed_diagnostic)
    topic_challenges = _topic_challenge_map(user)

    all_open = list_user_gaps(user, include_closed=False)
    closed_qs = list_user_gaps(user, include_closed=True).filter(
        status=UserSkillGap.Status.CLOSED
    )

    open_rows = enrich_gap_rows(
        list(UserSkillGapSerializer(all_open, many=True).data),
        synth_index=synth_index,
        topic_challenges=topic_challenges,
    )
    closed_rows = enrich_gap_rows(
        list(UserSkillGapSerializer(closed_qs[:10], many=True).data),
        synth_index=synth_index,
        topic_challenges=topic_challenges,
    )

    for row in open_rows + closed_rows:
        row["progress_percent"] = _progress_percent(row.get("status"))
        slug = str(row.get("skill_area") or "").strip().lower()
        match = synth_index.get(slug) or {}
        evidence_list = match.get("market_evidence") or []
        if evidence_list:
            first = evidence_list[0]
            row["market_insight"] = first.get("stat_text") or None
        else:
            row.setdefault("market_insight", None)

    open_count = sum(
        1 for g in open_rows if g.get("status") == UserSkillGap.Status.NOT_STARTED
    )
    in_progress_count = sum(
        1 for g in open_rows if g.get("status") == UserSkillGap.Status.IN_PROGRESS
    )
    # Treat any non-closed without explicit IN_PROGRESS as open for summary.
    if open_count + in_progress_count < len(open_rows):
        open_count = len(open_rows) - in_progress_count

    by_severity = {"high": 0, "medium": 0, "low": 0, "unknown": 0}
    for gap in open_rows:
        by_severity[_severity_key(gap.get("severity"))] += 1

    open_rows.sort(
        key=lambda g: (
            _SEVERITY_ORDER.get(_severity_key(g.get("severity")), 3),
            str(g.get("skill_area") or ""),
        )
    )

    radar_axes = _build_radar_axes(open_rows, closed_rows)
    avg_proficiency = (
        int(round(sum(a["current"] for a in radar_axes) / len(radar_axes) * 100))
        if radar_axes
        else (
            int(
                round(
                    closed_qs.count()
                    / max(1, closed_qs.count() + open_count + in_progress_count)
                    * 100
                )
            )
            if (closed_qs.count() + open_count + in_progress_count)
            else 0
        )
    )

    area_keys = [a["key"] for a in radar_axes]
    market_trends = _collect_market_trends(completed_diagnostic, area_keys)

    return {
        "summary": {
            "open_count": open_count,
            "in_progress_count": in_progress_count,
            "closed_count": closed_qs.count(),
            "by_severity": by_severity,
            "avg_proficiency": avg_proficiency,
            "active_focus": open_count + in_progress_count,
        },
        "radar": {"axes": radar_axes},
        "market_trends": market_trends,
        "open_gaps": open_rows,
        "recently_closed_gaps": closed_rows,
    }

"""Rule-based synthesis and roadmap generation."""

from __future__ import annotations

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from apps.diagnostics.adaptive_selector import rolling_score_for_area
from apps.diagnostics.models import (
    DiagnosticRoadmapItem,
    DiagnosticSession,
    FrameworkTopic,
    MarketEvidence,
    Question,
    SessionAnswer,
    SkillAreaFragment,
)


MODALITY_TO_CHALLENGE = {
    Question.Modality.FOUNDATIONAL: DiagnosticRoadmapItem.Modality.THEORY,
    Question.Modality.CODING: DiagnosticRoadmapItem.Modality.CODING,
    Question.Modality.FIND_ISSUES: DiagnosticRoadmapItem.Modality.DIAGNOSE,
    Question.Modality.SCENARIO: DiagnosticRoadmapItem.Modality.DEFEND,
    Question.Modality.DEFEND: DiagnosticRoadmapItem.Modality.DEFEND,
    Question.Modality.DIAGNOSE: DiagnosticRoadmapItem.Modality.DIAGNOSE,
    Question.Modality.ARCHITECT: DiagnosticRoadmapItem.Modality.ARCHITECT,
    Question.Modality.EXPLAIN: DiagnosticRoadmapItem.Modality.EXPLAIN_CODE,
    Question.Modality.COMMUNICATE: DiagnosticRoadmapItem.Modality.COMMUNICATE,
}

TRANSFER_MAP = [
    {
        "from_current_role": "Async / concurrency mental models",
        "applies_to_target": "Event-loop and request concurrency patterns on the other side of the stack",
        "areas": {"async"},
    },
    {
        "from_current_role": "Testing discipline",
        "applies_to_target": "Writing contract and integration tests for the target stack",
        "areas": {"testing"},
    },
    {
        "from_current_role": "API contract thinking",
        "applies_to_target": "Designing and consuming typed request/response boundaries",
        "areas": {"routing", "views_api", "validation", "data_fetching"},
    },
    {
        "from_current_role": "Auth and session boundaries",
        "applies_to_target": "Securing cookies, tokens, and middleware across FE/BE",
        "areas": {"auth", "middleware"},
    },
    {
        "from_current_role": "Performance profiling habits",
        "applies_to_target": "Finding N+1 queries or render bottlenecks in the target role",
        "areas": {"performance", "indexing", "query_plans", "models_orm"},
    },
]


def _weak_threshold() -> float:
    return float(getattr(settings, "ADAPTIVE_WEAK_THRESHOLD", 0.4))


def _strong_threshold() -> float:
    return float(getattr(settings, "ADAPTIVE_STRONG_THRESHOLD", 0.7))


def _severity(score: float) -> str:
    if score < 0.2:
        return "high"
    if score < _weak_threshold():
        return "medium"
    return "low"


def _fragment_level(score: float) -> str:
    if score >= _strong_threshold():
        return SkillAreaFragment.Level.STRONG
    if score >= _weak_threshold():
        return SkillAreaFragment.Level.PARTIAL
    return SkillAreaFragment.Level.GAP


def _fragment_for(area: str, level: str) -> str:
    frag = SkillAreaFragment.objects.filter(competency_area=area, level=level).first()
    if frag:
        return frag.body_text
    defaults = {
        SkillAreaFragment.Level.STRONG: f"You demonstrate strength in {area.replace('_', ' ')}.",
        SkillAreaFragment.Level.PARTIAL: f"You show partial mastery of {area.replace('_', ' ')}; tighten fundamentals with deliberate practice.",
        SkillAreaFragment.Level.GAP: f"{area.replace('_', ' ').title()} is a gap area — prioritize challenges here before advancing.",
    }
    return defaults.get(level, "")


def _evidence_for(area: str) -> list[dict]:
    rows = MarketEvidence.objects.filter(competency_area=area, is_active=True)[:2]
    return [
        {
            "stat_text": row.stat_text,
            "source_name": row.source_name,
            "source_date": row.source_date,
            "as_of": row.as_of.isoformat() if row.as_of else None,
        }
        for row in rows
    ]


def _transferable_skills(session: DiagnosticSession) -> list[dict]:
    if session.goal != DiagnosticSession.Goal.SWITCH_ROLE:
        return []
    frameworks = list(session.selected_frameworks.all())
    areas = set()
    for fw in frameworks:
        areas.update(fw.clean_competency_areas())
        areas.update(fw.fundamentals_topic.clean_competency_areas())
    out = []
    for item in TRANSFER_MAP:
        if areas & item["areas"]:
            out.append(
                {
                    "from_current_role": item["from_current_role"],
                    "applies_to_target": item["applies_to_target"],
                }
            )
    return out[:5]


def _collect_practice_areas(session: DiagnosticSession) -> list[str]:
    """
    Full practice path areas: assessment competencies first, then every
    competency from selected frameworks (so the roadmap is not gap-only).
    """
    ordered: list[str] = []
    seen: set[str] = set()

    def add(area: str | None) -> None:
        key = (area or "").strip()
        if not key or key in seen:
            return
        seen.add(key)
        ordered.append(key)

    for row in session.assessment_competencies or []:
        if isinstance(row, dict):
            add(row.get("competency_area"))

    frameworks = list(session.selected_frameworks.select_related("fundamentals_topic").all())
    # Also merge profile-known stack so Focus labels like React + Next.js both appear.
    profile = getattr(session.user, "profile", None)
    known = [str(x).strip().lower() for x in (getattr(profile, "known_skills", None) or [])]
    alias = {
        "react": "react",
        "next.js": "nextjs",
        "nextjs": "nextjs",
        "django": "django",
        "fastapi": "fastapi",
        "postgresql": "postgresql",
        "postgres": "postgresql",
    }
    profile_slugs = {alias[k] for k in known if k in alias}
    selected_slugs = {fw.framework_name for fw in frameworks}
    missing = profile_slugs - selected_slugs
    if missing:
        frameworks.extend(
            list(
                FrameworkTopic.objects.filter(framework_name__in=missing).select_related(
                    "fundamentals_topic"
                )
            )
        )
    if not frameworks and profile_slugs:
        frameworks = list(
            FrameworkTopic.objects.filter(framework_name__in=profile_slugs).select_related(
                "fundamentals_topic"
            )
        )

    for fw in frameworks:
        for area in fw.clean_competency_areas():
            add(area)

    return ordered


def _priority_for_score(score: float | None) -> int:
    """Lower priority number = earlier in the practice path."""
    if score is None:
        return 4  # assessed stack area not yet scored — still on the path
    if score < 0.2:
        return 1
    if score < _weak_threshold():
        return 2
    if score < _strong_threshold():
        return 3
    return 9  # strong — keep visible at the end as mastered


def build_practice_roadmap(session: DiagnosticSession) -> tuple[list[dict], list[dict], list[dict]]:
    """
    Build the full visible practice roadmap for a session.

    Includes every competency on the selected stack (not only weak gaps),
    ordered by diagnostic need. Strong areas are included as closed/mastered.
    """
    strong = _strong_threshold()
    weak = _weak_threshold()
    areas = _collect_practice_areas(session)

    strengths: list[dict] = []
    gaps: list[dict] = []
    roadmap: list[dict] = []

    for area in areas:
        score = rolling_score_for_area(session, area)
        level = _fragment_level(score) if score is not None else SkillAreaFragment.Level.PARTIAL
        fragment = _fragment_for(area, level)
        evidence = _evidence_for(area)
        modality = _dominant_modality_for_area(session, area)
        priority = _priority_for_score(score)

        if score is not None and score >= strong:
            strengths.append(
                {
                    "skill_area": area,
                    "evidence": f"Rolling score {score:.2f} >= {strong:.2f}",
                    "fragment": fragment,
                    "market_evidence": evidence,
                }
            )
            roadmap.append(
                {
                    "challenge_modality": modality,
                    "topic": area,
                    "priority": priority,
                    "initial_status": "closed",
                }
            )
        elif score is not None and score < weak:
            severity = _severity(score)
            gaps.append(
                {
                    "skill_area": area,
                    "block": "A",
                    "severity": severity,
                    "fragment": fragment,
                    "market_evidence": evidence,
                }
            )
            roadmap.append(
                {
                    "challenge_modality": modality,
                    "topic": area,
                    "priority": priority,
                    "initial_status": "not_started",
                }
            )
        else:
            # Partial mastery or unassessed stack area — still on the full path.
            if score is not None:
                strengths.append(
                    {
                        "skill_area": area,
                        "evidence": f"Partial mastery (score {score:.2f})",
                        "fragment": fragment,
                        "market_evidence": evidence,
                    }
                )
            roadmap.append(
                {
                    "challenge_modality": modality,
                    "topic": area,
                    "priority": priority,
                    "initial_status": "not_started",
                }
            )

    roadmap.sort(key=lambda item: (item["priority"], item["topic"]))
    return roadmap, gaps, strengths


def create_roadmap_items_from_entries(
    *,
    session: DiagnosticSession,
    roadmap: list[dict],
) -> list[DiagnosticRoadmapItem]:
    """Persist roadmap entries as DiagnosticRoadmapItem rows with matched challenges.

    Replaces the user's entire practice path (all prior roadmap items + today's
    DailyChallenge pointer) so re-diagnostics do not keep stale assignments.
    """
    from apps.challenges.models import DailyChallenge

    DiagnosticRoadmapItem.objects.filter(user=session.user).delete()
    DailyChallenge.objects.filter(
        user=session.user,
        date=timezone.localdate(),
    ).delete()
    created_items: list[DiagnosticRoadmapItem] = []
    used_challenge_ids: set[int] = set()

    for item in roadmap:
        topic = str(item.get("topic") or "").strip()
        if not topic:
            continue
        modality = str(
            item.get("challenge_modality") or DiagnosticRoadmapItem.Modality.THEORY
        )
        initial_status = str(item.get("initial_status") or "not_started")
        challenge = _find_challenge_for_topic(
            topic=topic,
            modality=modality,
            session=session,
            exclude_challenge_ids=used_challenge_ids,
        )
        # If every tagged challenge was already used, allow reuse rather than
        # leaving the step unlinked.
        if challenge is None and used_challenge_ids:
            challenge = _find_challenge_for_topic(
                topic=topic,
                modality=modality,
                session=session,
                exclude_challenge_ids=None,
            )
        if challenge is not None:
            used_challenge_ids.add(challenge.id)
        created_items.append(
            DiagnosticRoadmapItem.objects.create(
                session=session,
                user=session.user,
                challenge_modality=modality,
                topic=topic,
                priority=int(item.get("priority") or 5),
                challenge=challenge,
                status=initial_status,
            )
        )

    # First incomplete step becomes the active unlock.
    for row in created_items:
        if row.status != "closed":
            row.status = "in_progress"
            row.save(update_fields=["status"])
            break

    return created_items


def synthesize_session(session: DiagnosticSession) -> dict:
    roadmap, gaps, strengths = build_practice_roadmap(session)
    transfers = _transferable_skills(session)

    synthesis = {
        "strengths": strengths,
        "gaps": gaps,
        "transferable_skills": transfers,
        "roadmap": [
            {
                "challenge_modality": item["challenge_modality"],
                "topic": item["topic"],
                "priority": item["priority"],
            }
            for item in roadmap
        ],
    }

    session.synthesis = synthesis
    session.status = DiagnosticSession.Status.COMPLETED
    session.completed_at = timezone.now()
    session.save(update_fields=["synthesis", "status", "completed_at"])

    create_roadmap_items_from_entries(session=session, roadmap=roadmap)
    _upsert_gaps_from_synthesis(session, gaps)

    try:
        from apps.sessions.services import record_session

        record_session(
            user=session.user,
            session_type="DIAGNOSTIC",
            reference_id=session.id,
            title=f"Diagnostic: {session.goal}",
            summary=f"{len(gaps)} gaps · {len(strengths)} strengths · {len(roadmap)} roadmap steps",
        )
    except Exception:  # noqa: BLE001
        pass

    return synthesis


def _session_stack_slugs(session: DiagnosticSession) -> set[str]:
    """Framework / skill slugs allowed for this diagnostic session."""
    slugs: set[str] = set()
    for fw in session.selected_frameworks.all():
        name = (fw.framework_name or "").strip().lower()
        if name:
            slugs.add(name)
    profile = getattr(session.user, "profile", None)
    known = list(getattr(profile, "known_skills", None) or [])
    alias = {
        "react": "react",
        "next.js": "nextjs",
        "nextjs": "nextjs",
        "django": "django",
        "fastapi": "fastapi",
        "postgresql": "postgresql",
        "postgres": "postgresql",
        "typescript": "typescript",
        "javascript": "typescript",
        "python": "python",
    }
    for raw in known:
        key = str(raw).strip().lower()
        if key in alias:
            slugs.add(alias[key])
        normalized = key.replace(" ", "").replace("/", "")
        if normalized in {"javascripttypescript", "javascript", "typescript"}:
            slugs.add("typescript")
    # Always allow fundamentals language skills tied to selected frameworks.
    if slugs & {"react", "nextjs"}:
        slugs.update({"react", "nextjs", "typescript"})
    if slugs & {"django", "fastapi"}:
        slugs.update({"django", "fastapi", "python"})
    if "postgresql" in slugs:
        slugs.add("postgresql")
    return slugs


def _normalize_topic_key(topic: str) -> str:
    return (topic or "").strip().lower().replace(" ", "_").replace("-", "_")


def _topic_aliases(topic_key: str) -> set[str]:
    aliases = {topic_key}
    # Diagnostic areas vs challenge tags.
    mapping = {
        "state_management": {"state_management", "state"},
        "state": {"state", "state_management"},
        "ssr_ssg": {"ssr_ssg", "ssr", "caching"},
        "ssr": {"ssr", "ssr_ssg"},
    }
    aliases.update(mapping.get(topic_key, set()))
    return aliases


def _preferred_min_challenge_difficulty(session: DiagnosticSession | None) -> int:
    bump = int(getattr(session, "difficulty_bump", 0) or 0) if session else 0
    return min(5, max(1, 1 + bump))


def _pick_preferred_difficulty(challenges: list, *, min_difficulty: int):
    if not challenges:
        return None
    harder = [c for c in challenges if int(c.difficulty or 1) >= min_difficulty]
    pool = harder or challenges
    pool.sort(key=lambda c: (int(c.difficulty or 1), c.id))
    return pool[0]


def _find_challenge_for_topic(
    topic: str,
    modality: str,
    *,
    session: DiagnosticSession | None = None,
    allowed_skill_slugs: set[str] | None = None,
    exclude_challenge_ids: set[int] | None = None,
):
    """
    Match active challenges for a competency topic, scoped to the user's stack.
    Prefer difficulty >= 1 + session.difficulty_bump when available.
    Never falls back to an unrelated modality-wide first row (prevents RAG/AI orphans).
    """
    from apps.challenges.models import Challenge

    topic_key = _normalize_topic_key(topic)
    topic_keys = _topic_aliases(topic_key)
    topic_words = [w for w in topic_key.split("_") if len(w) > 2]
    human = topic_key.replace("_", " ")
    excluded = set(exclude_challenge_ids or set())
    min_difficulty = _preferred_min_challenge_difficulty(session)

    stack = allowed_skill_slugs
    if stack is None and session is not None:
        stack = _session_stack_slugs(session)
    stack = set(stack or [])

    def base_qs(*, modality_filter: str | None = modality):
        qs = Challenge.objects.filter(is_active=True)
        if modality_filter:
            qs = qs.filter(modality=modality_filter)
        if stack:
            qs = qs.filter(challenge_skills__skill__slug__in=stack).distinct()
        if excluded:
            qs = qs.exclude(id__in=excluded)
        return qs

    def areas_for(challenge) -> set[str]:
        return {
            _normalize_topic_key(str(t))
            for t in (challenge.workspace_config or {}).get("competency_areas", [])
        }

    def first_tagged(qs):
        ordered = list(
            qs.prefetch_related("challenge_skills__skill").order_by("difficulty", "id")
        )
        tagged = [c for c in ordered if topic_keys & areas_for(c)]
        return _pick_preferred_difficulty(tagged, min_difficulty=min_difficulty)

    # 1) Same modality + competency tag
    qs = base_qs()
    hit = first_tagged(qs)
    if hit:
        return hit

    # 2) Same modality + title/scenario
    if human.strip():
        title_matches = list(
            qs.filter(title__icontains=human[:40]).order_by("difficulty", "id")
        )
        title_match = _pick_preferred_difficulty(
            title_matches, min_difficulty=min_difficulty
        )
        if title_match:
            return title_match
    for word in topic_words:
        scenario_matches = list(
            qs.filter(Q(title__icontains=word) | Q(scenario__icontains=word)).order_by(
                "difficulty", "id"
            )
        )
        scenario_match = _pick_preferred_difficulty(
            scenario_matches, min_difficulty=min_difficulty
        )
        if scenario_match:
            return scenario_match

    # 3) Any modality + competency tag (prefer correct topic over wrong modality)
    cross = first_tagged(base_qs(modality_filter=None))
    if cross:
        return cross

    # 4) Stack-scoped same-modality fallback
    ordered = list(qs.order_by("difficulty", "id"))
    return _pick_preferred_difficulty(ordered, min_difficulty=min_difficulty)


def _upsert_gaps_from_synthesis(session: DiagnosticSession, gaps: list[dict]) -> None:
    """Persist diagnostic gaps as UserSkillGap rows so home/daily assignment stay aligned."""
    from apps.gaps.models import UserSkillGap
    from apps.gaps.services import upsert_user_skill_gap
    from apps.roles.models import Skill

    for gap in gaps:
        area = (gap.get("skill_area") or "").strip()
        if not area:
            continue
        slug = area.lower().replace(" ", "_")[:255]
        skill, _ = Skill.objects.get_or_create(
            slug=slug,
            defaults={
                "name": area.replace("_", " ").title(),
                "description": f"Diagnostic competency: {area.replace('_', ' ')}",
            },
        )
        upsert_user_skill_gap(
            user=session.user,
            skill=skill,
            status=UserSkillGap.Status.NOT_STARTED,
            evidence_source_type="DIAGNOSTIC",
            evidence_source_id=str(session.id),
            evidence_summary=gap.get("fragment")
            or f"Flagged as {gap.get('severity', 'medium')} severity from diagnostic.",
        )


def _dominant_modality_for_area(session: DiagnosticSession, area: str) -> str:
    answers = (
        SessionAnswer.objects.filter(
            question__session=session,
            question__competency_area=area,
        )
        .select_related("question__content_question")
        .order_by("-submitted_at")
    )
    for answer in answers:
        modality = answer.question.content_question.modality
        mapped = MODALITY_TO_CHALLENGE.get(modality)
        if mapped:
            return mapped
    return DiagnosticRoadmapItem.Modality.THEORY


def _priority_for_severity(severity: str) -> int:
    return {"high": 1, "medium": 2, "low": 3}.get(severity, 3)


def ensure_default_report_content() -> None:
    fragments = [
        ("hooks", "strong", "You reason clearly about React hooks lifecycle and cleanup."),
        ("hooks", "gap", "Hooks timing and cleanup are a gap — practice effects and dependency arrays."),
        ("models_orm", "strong", "You show strength in ORM query design and related-object loading."),
        ("models_orm", "gap", "ORM query patterns (including N+1) need deliberate practice."),
        ("indexing", "strong", "You understand when indexes help equality and range lookups."),
        ("indexing", "gap", "Postgres indexing trade-offs are a gap for your target backend work."),
        ("async", "partial", "Async instincts are emerging — reinforce event-loop and blocking-call pitfalls."),
    ]
    for area, level, body in fragments:
        SkillAreaFragment.objects.update_or_create(
            competency_area=area,
            level=level,
            defaults={"body_text": body},
        )

    evidence = [
        (
            "hooks",
            "React remains among the most-requested frontend skills in public developer surveys.",
            "State of JS (illustrative)",
            "2024",
        ),
        (
            "models_orm",
            "Django/ORM proficiency commonly appears in Python backend role requirements.",
            "Sampled job postings (manual)",
            "2025",
        ),
        (
            "indexing",
            "SQL indexing and query performance regularly appear in backend interview loops.",
            "Stack Overflow Developer Survey (illustrative)",
            "2024",
        ),
    ]
    for area, stat, source, date in evidence:
        MarketEvidence.objects.update_or_create(
            competency_area=area,
            source_name=source,
            defaults={
                "stat_text": stat,
                "source_date": date,
                "is_active": True,
            },
        )

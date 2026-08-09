"""Block A/B diagnostic session orchestration."""

from __future__ import annotations

import logging
import re

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.ai.services.assessment_service import (
    classify_block_b_exposure as ai_classify_block_b_exposure,
    generate_block_a_competency_questions as ai_generate_block_a_competency_questions,
    generate_block_b_questions as ai_generate_block_b_questions,
    generate_role_taxonomy as ai_generate_role_taxonomy,
    generate_stage_questions,
    synthesize_diagnostic,
)
from apps.challenges.models import Challenge
from apps.diagnostics.models import (
    DiagnosticRoadmapItem,
    DiagnosticSession,
    DomainTaxonomy,
    RoleTaxonomy,
    SessionAnswer,
    SessionQuestion,
)
from apps.gaps.models import UserSkillGap
from apps.gaps.services import upsert_user_skill_gap
from apps.roles.models import Skill
from apps.sessions.services import record_session
from apps.users.models import Profile, User

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = (
    DiagnosticSession.Status.PENDING,
    DiagnosticSession.Status.GENERATING,
    DiagnosticSession.Status.AWAITING_ANSWERS,
    DiagnosticSession.Status.SYNTHESIZING,
)

BLOCK_A_STAGES = [
    DiagnosticSession.Stage.FOUNDATIONAL,
    DiagnosticSession.Stage.SCENARIO,
    DiagnosticSession.Stage.DEBUGGING,
    DiagnosticSession.Stage.CODING,
    DiagnosticSession.Stage.FIND_ISSUES,
]

QUESTION_COUNTS = {
    DiagnosticSession.Stage.FOUNDATIONAL: 4,
    DiagnosticSession.Stage.SCENARIO: 3,
    DiagnosticSession.Stage.DEBUGGING: 3,
    DiagnosticSession.Stage.CODING: 1,
    DiagnosticSession.Stage.FIND_ISSUES: 1,
}

STAGE_WEIGHTS = {
    DiagnosticSession.Stage.FOUNDATIONAL: 4,
    DiagnosticSession.Stage.SCENARIO: 3,
    DiagnosticSession.Stage.DEBUGGING: 3,
    DiagnosticSession.Stage.CODING: 1,
    DiagnosticSession.Stage.FIND_ISSUES: 1,
}

STAGE_WEIGHT_TOTAL = sum(STAGE_WEIGHTS.values())

VALID_MODALITIES = {c.value for c in Challenge.Modality}


def _normalize_modality(raw: str) -> str:
    value = (raw or "").strip().upper().replace(" ", "_").replace("-", "_")
    aliases = {
        "EXPLAIN": Challenge.Modality.EXPLAIN_CODE,
        "EXPLAIN_CODE": Challenge.Modality.EXPLAIN_CODE,
        "COMMUNICATE": Challenge.Modality.COMMUNICATE,
        "COMMUNICATION": Challenge.Modality.COMMUNICATE,
    }
    value = aliases.get(value, value)
    if value not in VALID_MODALITIES:
        return Challenge.Modality.THEORY
    return value


def _slug_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").strip().lower())


def competency_matches(left: str, right: str) -> bool:
    a = (left or "").strip().lower()
    b = (right or "").strip().lower()
    if not a or not b:
        return False
    if a == b:
        return True
    return _slug_key(a) == _slug_key(b)


def build_session_context(session: DiagnosticSession) -> dict:
    profile, _ = Profile.objects.get_or_create(user=session.user)
    taxonomy = session.target_taxonomy
    competency_areas: list[str] = []
    if taxonomy is not None:
        competency_areas = taxonomy.clean_competency_areas()
    assessment = list(session.assessment_competencies or [])
    if assessment and not competency_areas:
        competency_areas = [
            str(row.get("competency_area") or "").strip()
            for row in assessment
            if str(row.get("competency_area") or "").strip()
        ]
    return {
        "goal": session.goal,
        "current_role": session.current_role or profile.current_role,
        "target_role": session.target_role or profile.target_role_label,
        "experience_years": profile.years_of_experience,
        "known_skills": profile.known_skills or [],
        "target_learn_skills": profile.target_learn_skills or [],
        "technical_goal": profile.technical_goal,
        "competency_areas": competency_areas,
        "assessment_competencies": assessment,
    }


def build_transcript(session: DiagnosticSession, *, block: str | None = None) -> list[dict]:
    qs = session.questions.select_related("answer").order_by("id")
    if block:
        qs = qs.filter(block=block)
    rows: list[dict] = []
    for q in qs:
        answer = getattr(q, "answer", None)
        rows.append(
            {
                "block": q.block,
                "stage": q.stage,
                "order": q.order,
                "competency_area": q.competency_area or "",
                "domain_slug": (q.metadata or {}).get("domain_slug") or "",
                "question_text": q.question_text,
                "answer_text": answer.answer_text if answer else "",
                "exposure_confirmed": (
                    answer.exposure_confirmed if answer is not None else None
                ),
            }
        )
    return rows


def build_assessment_competencies(
    domains: list[DomainTaxonomy],
    *,
    cap: int,
) -> list[dict]:
    """Round-robin competency coverage across domains, capped at ``cap``."""
    queues: list[tuple[str, list[str]]] = []
    seen_keys: set[str] = set()
    for domain in domains:
        areas: list[str] = []
        for area in domain.clean_competency_areas():
            key = area.strip().lower()
            if not key or key in seen_keys:
                continue
            seen_keys.add(key)
            areas.append(area)
        if areas:
            queues.append((domain.slug, areas))

    if not queues:
        return []

    plan: list[dict] = []
    indices = [0] * len(queues)
    while len(plan) < cap:
        progressed = False
        for qi, (slug, areas) in enumerate(queues):
            if len(plan) >= cap:
                break
            idx = indices[qi]
            if idx >= len(areas):
                continue
            plan.append(
                {
                    "domain_slug": slug,
                    "competency_area": areas[idx],
                }
            )
            indices[qi] = idx + 1
            progressed = True
        if not progressed:
            break
    return plan


def allocate_competencies_to_stages(plan: list[dict]) -> dict[str, list[dict]]:
    """Distribute N competencies across Block A stages by STAGE_WEIGHTS."""
    n = len(plan)
    allocation: dict[str, list[dict]] = {stage: [] for stage in BLOCK_A_STAGES}
    if n == 0:
        return allocation

    raw = {
        stage: (n * STAGE_WEIGHTS[stage]) / STAGE_WEIGHT_TOTAL
        for stage in BLOCK_A_STAGES
    }
    counts = {stage: int(raw[stage]) for stage in BLOCK_A_STAGES}
    remainders = sorted(
        ((raw[stage] - counts[stage], stage) for stage in BLOCK_A_STAGES),
        key=lambda item: (-item[0], BLOCK_A_STAGES.index(item[1])),
    )
    leftover = n - sum(counts.values())
    for i in range(leftover):
        counts[remainders[i][1]] += 1

    cursor = 0
    for stage in BLOCK_A_STAGES:
        take = counts[stage]
        allocation[stage] = plan[cursor : cursor + take]
        cursor += take
    return allocation


def stage_counts_for_session(session: DiagnosticSession) -> dict[str, int]:
    if session.goal != DiagnosticSession.Goal.SHARPEN_CURRENT:
        return dict(QUESTION_COUNTS)
    plan = list(session.assessment_competencies or [])
    if not plan:
        return dict(QUESTION_COUNTS)
    allocation = allocate_competencies_to_stages(plan)
    return {stage: len(rows) for stage, rows in allocation.items()}


def next_block_a_stage(current: str | None, *, session: DiagnosticSession | None = None) -> str | None:
    counts = stage_counts_for_session(session) if session is not None else dict(QUESTION_COUNTS)

    def first_nonempty_from(start_idx: int) -> str | None:
        for stage in BLOCK_A_STAGES[start_idx:]:
            if counts.get(stage, 0) > 0:
                return stage
        return None

    if current is None:
        return first_nonempty_from(0)
    try:
        idx = BLOCK_A_STAGES.index(current)
    except ValueError:
        return first_nonempty_from(0)
    return first_nonempty_from(idx + 1)


def _normalize_competency_list(raw: list | None) -> list[str]:
    out: list[str] = []
    for item in raw or []:
        name = str(item or "").strip()
        if name and name not in out:
            out.append(name)
    return out


def resolve_domain_taxonomies(domain_slugs: list[str]) -> list[DomainTaxonomy]:
    from apps.diagnostics.domain_defaults import (
        DEFAULT_DOMAIN_BY_SLUG,
        ensure_default_domain_taxonomies,
    )

    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in domain_slugs:
        slug = str(raw or "").strip().lower()
        if not slug or slug in seen:
            continue
        seen.add(slug)
        cleaned.append(slug)
    if not cleaned:
        raise ValidationError(
            {"detail": "Select at least one technical domain for a sharpen diagnostic."}
        )

    # Bootstrap the fixed FE catalog so local/dev never needs manual admin seeding.
    ensure_default_domain_taxonomies()

    missing: list[str] = []
    empty: list[str] = []
    ordered: list[DomainTaxonomy] = []
    for slug in cleaned:
        tax = DomainTaxonomy.objects.filter(slug__iexact=slug).first()
        if tax is None and slug in DEFAULT_DOMAIN_BY_SLUG:
            row = DEFAULT_DOMAIN_BY_SLUG[slug]
            tax = DomainTaxonomy.objects.create(
                slug=row["slug"],
                domain_name=row["domain_name"],
                competency_areas=list(row["competency_areas"]),
            )
        if tax is None:
            missing.append(slug)
            continue
        if not tax.clean_competency_areas():
            if slug in DEFAULT_DOMAIN_BY_SLUG:
                tax.competency_areas = list(DEFAULT_DOMAIN_BY_SLUG[slug]["competency_areas"])
                tax.save(update_fields=["competency_areas", "updated_at"])
            else:
                empty.append(slug)
                continue
        ordered.append(tax)

    problems: list[str] = []
    if missing:
        problems.append(
            "Unknown technical domain(s): "
            + ", ".join(missing)
            + ". Use the onboarding domain cards."
        )
    if empty:
        problems.append(
            "DomainTaxonomy has empty competency_areas for: "
            + ", ".join(empty)
            + ". Fix in Django admin."
        )
    if problems:
        raise ValidationError({"detail": " ".join(problems)})
    return ordered


def resolve_or_create_taxonomy(*, label: str, profile: Profile) -> RoleTaxonomy:
    """Reuse admin/AI-cached taxonomy, or generate one for any free-text role."""
    label = (label or "").strip()
    if not label:
        raise ValidationError(
            {"detail": "Set a target role before starting a switch-role diagnostic."}
        )

    taxonomy = RoleTaxonomy.objects.filter(role_name__iexact=label).first()
    areas = taxonomy.clean_competency_areas() if taxonomy is not None else []
    if taxonomy is not None and areas:
        return taxonomy

    try:
        generated = ai_generate_role_taxonomy(
            {
                "target_role": label,
                "role_name": label,
                "target_learn_skills": profile.target_learn_skills or [],
                "known_skills": profile.known_skills or [],
                "current_role": profile.current_role or "",
            }
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Role taxonomy generation failed for %s", label)
        raise ValidationError(
            {
                "detail": (
                    f"Could not build a competency taxonomy for '{label}'. "
                    f"Try again shortly. ({exc})"
                )
            }
        ) from exc

    areas = _normalize_competency_list(list(generated.competency_areas or []))
    if len(areas) < 3:
        raise ValidationError(
            {
                "detail": (
                    f"Could not build enough competency areas for '{label}'. "
                    "Try again or pick a clearer role label."
                )
            }
        )

    if taxonomy is None:
        taxonomy = RoleTaxonomy.objects.create(
            role_name=label,
            competency_areas=areas,
        )
    else:
        taxonomy.competency_areas = areas
        taxonomy.save(update_fields=["competency_areas", "updated_at"])
    return taxonomy


@transaction.atomic
def start_session(
    *,
    user: User,
    goal: str,
    domain_slugs: list[str] | None = None,
) -> DiagnosticSession:
    if goal not in {
        DiagnosticSession.Goal.SHARPEN_CURRENT,
        DiagnosticSession.Goal.SWITCH_ROLE,
    }:
        raise ValidationError("goal must be sharpen_current or switch_role.")

    active = DiagnosticSession.objects.filter(user=user, status__in=ACTIVE_STATUSES).first()
    if active:
        raise ValidationError(
            {
                "detail": "You already have an active diagnostic session.",
                "session_id": active.id,
            }
        )

    from django.conf import settings

    profile, _ = Profile.objects.get_or_create(user=user)
    target_role = ""
    target_taxonomy = None
    domains: list[DomainTaxonomy] = []
    assessment_competencies: list[dict] = []

    if goal == DiagnosticSession.Goal.SWITCH_ROLE:
        label = (profile.target_role_label or "").strip()
        if profile.target_role_id and not label:
            label = profile.target_role.name
        taxonomy = resolve_or_create_taxonomy(label=label, profile=profile)
        target_taxonomy = taxonomy
        target_role = taxonomy.role_name
    else:
        target_role = (profile.current_role or "").strip()
        domains = resolve_domain_taxonomies(domain_slugs or [])
        cap = int(getattr(settings, "DIAGNOSTIC_MAX_COMPETENCY_AREAS", 8))
        assessment_competencies = build_assessment_competencies(domains, cap=cap)
        if not assessment_competencies:
            raise ValidationError(
                {"detail": "Selected domains produced no competency areas to assess."}
            )

    session = DiagnosticSession.objects.create(
        user=user,
        goal=goal,
        current_role=profile.current_role or "",
        target_role=target_role,
        target_taxonomy=target_taxonomy,
        assessment_competencies=assessment_competencies,
        status=DiagnosticSession.Status.GENERATING,
        current_block=DiagnosticSession.Block.A,
        current_stage=DiagnosticSession.Stage.FOUNDATIONAL,
    )
    if domains:
        session.selected_domains.set(domains)

    first_stage = next_block_a_stage(None, session=session)
    if first_stage is None:
        raise ValidationError({"detail": "No Block A stages to generate for this plan."})
    session.current_stage = first_stage
    session.save(update_fields=["current_stage", "updated_at"])

    sid = session.id
    if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
        _enqueue_generate(sid, DiagnosticSession.Block.A, first_stage)
    else:
        transaction.on_commit(
            lambda: _enqueue_generate(sid, DiagnosticSession.Block.A, first_stage)
        )
    return session


def _enqueue_generate(session_id: int, block: str, stage: str) -> None:
    from django.conf import settings

    from apps.diagnostics.tasks import generate_session_stage

    if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
        generate_session_stage(session_id, block, stage)
    else:
        generate_session_stage.delay(session_id, block, stage)


def _enqueue_block_b(session_id: int) -> None:
    from django.conf import settings

    from apps.diagnostics.tasks import generate_block_b_questions

    if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
        generate_block_b_questions(session_id)
    else:
        generate_block_b_questions.delay(session_id)


def _enqueue_synthesize(session_id: int) -> None:
    from django.conf import settings

    from apps.diagnostics.tasks import synthesize_session

    if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
        synthesize_session(session_id)
    else:
        synthesize_session.delay(session_id)


def generate_stage_for_session(*, session_id: int, block: str, stage: str) -> DiagnosticSession:
    """Generate Block A stage questions (Block B uses generate_block_b_for_session)."""
    if block == DiagnosticSession.Block.B:
        return generate_block_b_for_session(session_id=session_id)

    session = DiagnosticSession.objects.select_related("user").get(pk=session_id)
    if (
        session.goal == DiagnosticSession.Goal.SHARPEN_CURRENT
        and session.assessment_competencies
    ):
        return generate_sharpen_stage_for_session(
            session_id=session_id, stage=stage
        )

    session.status = DiagnosticSession.Status.GENERATING
    session.current_block = block
    session.current_stage = stage
    session.error = ""
    session.save(update_fields=["status", "current_block", "current_stage", "error", "updated_at"])

    count = QUESTION_COUNTS.get(stage, 3)
    context = {
        **build_session_context(session),
        "block": block,
        "stage": stage,
        "question_count": count,
        "low_stakes": False,
        "transcript": build_transcript(session, block=DiagnosticSession.Block.A),
    }

    try:
        generated = generate_stage_questions(context)
        items = generated.questions
    except Exception as exc:  # noqa: BLE001
        logger.exception("Stage generation failed session=%s", session_id)
        session.status = DiagnosticSession.Status.FAILED
        session.error = str(exc)[:2000]
        session.save(update_fields=["status", "error", "updated_at"])
        raise

    if not items:
        session.status = DiagnosticSession.Status.FAILED
        session.error = "AI returned no questions."
        session.save(update_fields=["status", "error", "updated_at"])
        raise ValidationError("AI returned no questions.")

    SessionQuestion.objects.filter(
        session=session,
        block=block,
        stage=stage,
        status=SessionQuestion.Status.ASKED,
    ).delete()

    for idx, item in enumerate(items[:count], start=1):
        SessionQuestion.objects.create(
            session=session,
            block=block,
            stage=stage,
            order=idx,
            competency_area="",
            question_text=item.question_text,
            metadata={"question_type": item.question_type},
            status=SessionQuestion.Status.ASKED,
        )

    session.status = DiagnosticSession.Status.AWAITING_ANSWERS
    session.current_block = block
    session.current_stage = stage
    session.save(
        update_fields=["status", "current_block", "current_stage", "updated_at"]
    )
    return session


def generate_sharpen_stage_for_session(*, session_id: int, stage: str) -> DiagnosticSession:
    """One foundational-style question per assigned competency for this stage."""
    session = DiagnosticSession.objects.select_related("user").get(pk=session_id)
    session.status = DiagnosticSession.Status.GENERATING
    session.current_block = DiagnosticSession.Block.A
    session.current_stage = stage
    session.error = ""
    session.save(
        update_fields=["status", "current_block", "current_stage", "error", "updated_at"]
    )

    allocation = allocate_competencies_to_stages(list(session.assessment_competencies or []))
    assigned = allocation.get(stage) or []
    if not assigned:
        session.status = DiagnosticSession.Status.FAILED
        session.error = f"No competencies allocated to stage {stage}."
        session.save(update_fields=["status", "error", "updated_at"])
        raise ValidationError(session.error)

    context = {
        **build_session_context(session),
        "block": DiagnosticSession.Block.A,
        "stage": stage,
        "low_stakes": False,
        "competency_rows": assigned,
        "competency_areas": [row["competency_area"] for row in assigned],
        "transcript": build_transcript(session, block=DiagnosticSession.Block.A),
    }

    try:
        generated = ai_generate_block_a_competency_questions(context)
        items = generated.questions
    except Exception as exc:  # noqa: BLE001
        logger.exception("Sharpen stage generation failed session=%s", session_id)
        session.status = DiagnosticSession.Status.FAILED
        session.error = str(exc)[:2000]
        session.save(update_fields=["status", "error", "updated_at"])
        raise

    by_area: dict[str, object] = {}
    for item in items:
        area = str(getattr(item, "competency_area", "") or "").strip()
        if not area:
            continue
        for row in assigned:
            expected = row["competency_area"]
            if competency_matches(area, expected) and expected not in by_area:
                by_area[expected] = item
                break

    missing = [row["competency_area"] for row in assigned if row["competency_area"] not in by_area]
    if missing:
        session.status = DiagnosticSession.Status.FAILED
        session.error = f"Block A missing questions for: {missing}"
        session.save(update_fields=["status", "error", "updated_at"])
        raise ValidationError(session.error)

    SessionQuestion.objects.filter(
        session=session,
        block=DiagnosticSession.Block.A,
        stage=stage,
        status=SessionQuestion.Status.ASKED,
    ).delete()

    for idx, row in enumerate(assigned, start=1):
        item = by_area[row["competency_area"]]
        SessionQuestion.objects.create(
            session=session,
            block=DiagnosticSession.Block.A,
            stage=stage,
            order=idx,
            competency_area=row["competency_area"],
            question_text=item.question_text,
            metadata={
                "question_type": getattr(item, "question_type", None) or "FREE_TEXT",
                "competency_area": row["competency_area"],
                "domain_slug": row.get("domain_slug") or "",
            },
            status=SessionQuestion.Status.ASKED,
        )

    session.status = DiagnosticSession.Status.AWAITING_ANSWERS
    session.current_block = DiagnosticSession.Block.A
    session.current_stage = stage
    session.save(
        update_fields=["status", "current_block", "current_stage", "updated_at"]
    )
    return session


def generate_block_b_for_session(*, session_id: int) -> DiagnosticSession:
    """One foundational Block B question per taxonomy competency_area."""
    session = DiagnosticSession.objects.select_related(
        "user", "target_taxonomy"
    ).get(pk=session_id)
    session.status = DiagnosticSession.Status.GENERATING
    session.current_block = DiagnosticSession.Block.B
    session.current_stage = DiagnosticSession.Stage.FOUNDATIONAL
    session.error = ""
    session.save(
        update_fields=["status", "current_block", "current_stage", "error", "updated_at"]
    )

    taxonomy = session.target_taxonomy
    if taxonomy is None:
        session.status = DiagnosticSession.Status.FAILED
        session.error = "Session has no RoleTaxonomy for Block B."
        session.save(update_fields=["status", "error", "updated_at"])
        raise ValidationError(session.error)

    areas = taxonomy.clean_competency_areas()
    if not areas:
        session.status = DiagnosticSession.Status.FAILED
        session.error = "RoleTaxonomy has no competency_areas."
        session.save(update_fields=["status", "error", "updated_at"])
        raise ValidationError(session.error)

    context = {
        **build_session_context(session),
        "block": DiagnosticSession.Block.B,
        "stage": DiagnosticSession.Stage.FOUNDATIONAL,
        "low_stakes": True,
        "competency_areas": areas,
        "transcript": build_transcript(session),
    }

    try:
        generated = ai_generate_block_b_questions(context)
        items = generated.questions
    except Exception as exc:  # noqa: BLE001
        logger.exception("Block B generation failed session=%s", session_id)
        session.status = DiagnosticSession.Status.FAILED
        session.error = str(exc)[:2000]
        session.save(update_fields=["status", "error", "updated_at"])
        raise

    by_area: dict[str, object] = {}
    for item in items:
        area = str(getattr(item, "competency_area", "") or "").strip()
        if not area:
            continue
        for expected in areas:
            if competency_matches(area, expected) and expected not in by_area:
                by_area[expected] = item
                break

    missing = [a for a in areas if a not in by_area]
    if missing:
        session.status = DiagnosticSession.Status.FAILED
        session.error = f"Block B missing questions for: {missing}"
        session.save(update_fields=["status", "error", "updated_at"])
        raise ValidationError(session.error)

    SessionQuestion.objects.filter(
        session=session,
        block=DiagnosticSession.Block.B,
        stage=DiagnosticSession.Stage.FOUNDATIONAL,
        status=SessionQuestion.Status.ASKED,
    ).delete()

    for idx, area in enumerate(areas, start=1):
        item = by_area[area]
        SessionQuestion.objects.create(
            session=session,
            block=DiagnosticSession.Block.B,
            stage=DiagnosticSession.Stage.FOUNDATIONAL,
            order=idx,
            competency_area=area,
            question_text=item.question_text,
            metadata={
                "question_type": getattr(item, "question_type", None) or "FREE_TEXT",
                "competency_area": area,
            },
            status=SessionQuestion.Status.ASKED,
        )

    session.status = DiagnosticSession.Status.AWAITING_ANSWERS
    session.current_block = DiagnosticSession.Block.B
    session.current_stage = DiagnosticSession.Stage.FOUNDATIONAL
    session.save(
        update_fields=["status", "current_block", "current_stage", "updated_at"]
    )
    return session


def classify_block_b_exposure(*, session_id: int) -> DiagnosticSession:
    """Celery helper: set SessionAnswer.exposure_confirmed for Block B answers."""
    session = DiagnosticSession.objects.select_related(
        "user", "target_taxonomy"
    ).get(pk=session_id)
    if session.goal != DiagnosticSession.Goal.SWITCH_ROLE:
        return session

    b_qs = list(
        SessionQuestion.objects.filter(
            session=session,
            block=DiagnosticSession.Block.B,
        )
        .select_related("answer")
        .order_by("order")
    )
    if not b_qs:
        return session

    taxonomy = session.target_taxonomy
    areas = taxonomy.clean_competency_areas() if taxonomy else []
    payload_items = []
    for q in b_qs:
        answer = getattr(q, "answer", None)
        payload_items.append(
            {
                "question_id": q.id,
                "competency_area": q.competency_area,
                "question_text": q.question_text,
                "answer_text": answer.answer_text if answer else "",
            }
        )

    context = {
        **build_session_context(session),
        "competency_areas": areas,
        "block_b_items": payload_items,
    }
    try:
        result = ai_classify_block_b_exposure(context)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Block B exposure classify failed session=%s", session_id)
        session.status = DiagnosticSession.Status.FAILED
        session.error = str(exc)[:2000]
        session.save(update_fields=["status", "error", "updated_at"])
        raise

    by_qid = {
        int(item.question_id): bool(item.exposure_confirmed)
        for item in result.classifications
    }
    for q in b_qs:
        answer = getattr(q, "answer", None)
        if answer is None:
            continue
        confirmed = by_qid.get(q.id)
        if confirmed is None:
            # Fallback: match by competency_area label from AI rows
            for item in result.classifications:
                if competency_matches(item.competency_area, q.competency_area):
                    confirmed = bool(item.exposure_confirmed)
                    break
        if confirmed is None:
            confirmed = False
        answer.exposure_confirmed = confirmed
        answer.save(update_fields=["exposure_confirmed"])
    return session


def compute_block_b_gaps(session: DiagnosticSession) -> list[dict]:
    """Deterministic Block B gaps: gap if not (exposure or transferable coverage)."""
    taxonomy = session.target_taxonomy
    if taxonomy is None:
        return []
    areas = taxonomy.clean_competency_areas()
    if not areas:
        return []

    exposure_by_area: dict[str, bool] = {}
    for q in SessionQuestion.objects.filter(
        session=session, block=DiagnosticSession.Block.B
    ).select_related("answer"):
        area = (q.competency_area or "").strip()
        if not area:
            continue
        answer = getattr(q, "answer", None)
        exposure_by_area[area] = bool(
            answer and answer.exposure_confirmed is True
        )

    transfers = []
    if isinstance(session.synthesis, dict):
        transfers = session.synthesis.get("transferable_skills") or []

    gaps: list[dict] = []
    for area in areas:
        exposed = False
        for key, val in exposure_by_area.items():
            if competency_matches(key, area):
                exposed = val
                break
        transferable = False
        for t in transfers:
            applies = str(
                t.get("applies_to_target") if isinstance(t, dict) else ""
            )
            if competency_matches(applies, area):
                transferable = True
                break
        if not (exposed or transferable):
            gaps.append(
                {
                    "skill_area": area,
                    "block": "B",
                    "severity": "foundational",
                    "competency_area": area,
                }
            )
    return gaps


def merge_deterministic_b_gaps(session: DiagnosticSession) -> list[dict]:
    """Keep LLM Block A gaps; replace any Block B gaps with deterministic ones."""
    synthesis = dict(session.synthesis or {})
    a_gaps = [
        g
        for g in (synthesis.get("gaps") or [])
        if str(g.get("block") or "A").upper() != "B"
    ]
    b_gaps = compute_block_b_gaps(session)
    merged = a_gaps + b_gaps
    synthesis["gaps"] = merged
    session.synthesis = synthesis
    session.save(update_fields=["synthesis", "updated_at"])
    return merged


@transaction.atomic
def submit_stage_answers(
    *,
    user: User,
    session_id: int,
    answers: list[dict],
) -> DiagnosticSession:
    session = DiagnosticSession.objects.select_for_update().get(pk=session_id, user=user)
    if session.status != DiagnosticSession.Status.AWAITING_ANSWERS:
        raise ValidationError("Session is not awaiting answers.")

    open_qs = list(
        SessionQuestion.objects.filter(
            session=session,
            block=session.current_block,
            stage=session.current_stage,
            status=SessionQuestion.Status.ASKED,
        ).order_by("order")
    )
    if not open_qs:
        raise ValidationError("No open questions for this stage.")

    by_id = {int(a["question_id"]): str(a.get("answer_text") or "") for a in answers}
    missing = [q.id for q in open_qs if q.id not in by_id]
    if missing:
        raise ValidationError(f"Missing answers for questions: {missing}")

    for q in open_qs:
        SessionAnswer.objects.update_or_create(
            question=q,
            defaults={"answer_text": by_id[q.id]},
        )
        q.status = SessionQuestion.Status.ANSWERED
        q.save(update_fields=["status"])

    block = session.current_block
    stage = session.current_stage

    if block == DiagnosticSession.Block.A:
        nxt = next_block_a_stage(stage, session=session)
        if nxt:
            session.status = DiagnosticSession.Status.GENERATING
            session.save(update_fields=["status", "updated_at"])
            sid, b, s = session.id, DiagnosticSession.Block.A, nxt
            from django.conf import settings

            if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
                _enqueue_generate(sid, b, s)
            else:
                transaction.on_commit(lambda: _enqueue_generate(sid, b, s))
            return session

        if session.goal == DiagnosticSession.Goal.SWITCH_ROLE:
            session.status = DiagnosticSession.Status.GENERATING
            session.current_block = DiagnosticSession.Block.B
            session.current_stage = DiagnosticSession.Stage.FOUNDATIONAL
            session.save(
                update_fields=[
                    "status",
                    "current_block",
                    "current_stage",
                    "updated_at",
                ]
            )
            sid = session.id
            from django.conf import settings

            if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
                _enqueue_block_b(sid)
            else:
                transaction.on_commit(lambda: _enqueue_block_b(sid))
            return session

        session.status = DiagnosticSession.Status.SYNTHESIZING
        session.save(update_fields=["status", "updated_at"])
        sid = session.id
        from django.conf import settings

        if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
            _enqueue_synthesize(sid)
        else:
            transaction.on_commit(lambda: _enqueue_synthesize(sid))
        return session

    # Block B completed → classify exposure then synthesis (via synthesize task)
    session.status = DiagnosticSession.Status.SYNTHESIZING
    session.save(update_fields=["status", "updated_at"])
    sid = session.id
    from django.conf import settings

    if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
        _enqueue_synthesize(sid)
    else:
        transaction.on_commit(lambda: _enqueue_synthesize(sid))
    return session


def run_synthesis(*, session_id: int) -> DiagnosticSession:
    session = DiagnosticSession.objects.select_related(
        "user", "target_taxonomy"
    ).get(pk=session_id)
    session.status = DiagnosticSession.Status.SYNTHESIZING
    session.error = ""
    session.save(update_fields=["status", "error", "updated_at"])

    if session.goal == DiagnosticSession.Goal.SWITCH_ROLE:
        classify_block_b_exposure(session_id=session_id)
        session.refresh_from_db()

    context = {
        **build_session_context(session),
        "transcript": build_transcript(session),
        "skip_block_b_gaps": True,
    }
    try:
        result = synthesize_diagnostic(context)
        payload = result.model_dump()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Synthesis failed session=%s", session_id)
        session.status = DiagnosticSession.Status.FAILED
        session.error = str(exc)[:2000]
        session.save(update_fields=["status", "error", "updated_at"])
        raise

    if session.goal != DiagnosticSession.Goal.SWITCH_ROLE:
        payload["transferable_skills"] = []

    # Drop any LLM-invented Block B gaps; deterministic merge happens next.
    payload["gaps"] = [
        g
        for g in (payload.get("gaps") or [])
        if str(g.get("block") or "A").upper() != "B"
    ]

    roadmap = []
    for item in payload.get("roadmap") or []:
        modality = _normalize_modality(str(item.get("challenge_modality") or ""))
        roadmap.append(
            {
                "challenge_modality": modality,
                "topic": str(item.get("topic") or "")[:512],
                "priority": int(item.get("priority") or 1),
            }
        )
    payload["roadmap"] = roadmap

    with transaction.atomic():
        session.synthesis = payload
        session.save(update_fields=["synthesis", "updated_at"])

        if session.goal == DiagnosticSession.Goal.SWITCH_ROLE:
            merge_deterministic_b_gaps(session)
            session.refresh_from_db()
            payload = session.synthesis

        session.status = DiagnosticSession.Status.COMPLETED
        session.completed_at = timezone.now()
        session.save(
            update_fields=["synthesis", "status", "completed_at", "updated_at"]
        )

        DiagnosticRoadmapItem.objects.filter(user=session.user).delete()
        for item in roadmap:
            challenge = (
                Challenge.objects.filter(
                    is_active=True,
                    modality=item["challenge_modality"],
                )
                .order_by("difficulty", "id")
                .first()
            )
            DiagnosticRoadmapItem.objects.create(
                session=session,
                user=session.user,
                challenge_modality=item["challenge_modality"],
                topic=item["topic"] or "Practice topic",
                priority=item["priority"],
                challenge=challenge,
            )

        for gap in payload.get("gaps") or []:
            area = str(gap.get("skill_area") or gap.get("competency_area") or "").strip()
            if not area:
                continue
            skill = (
                Skill.objects.filter(name__iexact=area).first()
                or Skill.objects.filter(slug=area.lower().replace(" ", "-")).first()
            )
            if not skill:
                continue
            competency = str(gap.get("competency_area") or area)
            upsert_user_skill_gap(
                user=session.user,
                skill=skill,
                status=UserSkillGap.Status.NOT_STARTED,
                evidence_source_type="diagnostic_session",
                evidence_source_id=str(session.id),
                evidence_summary=(
                    f"{gap.get('block')}:{gap.get('severity')}:{area}"
                    f":competency_area={competency}"
                ),
            )

        record_session(
            user=session.user,
            session_type="DIAGNOSTIC",
            title=f"Diagnostic ({session.goal})",
            reference_id=session.id,
            summary="Block A/B diagnostic completed",
        )

    return session


def get_session_for_user(*, user: User, session_id: int) -> DiagnosticSession:
    try:
        return DiagnosticSession.objects.select_related(
            "target_taxonomy"
        ).prefetch_related(
            "questions__answer",
            "roadmap_items",
            "selected_domains",
        ).get(pk=session_id, user=user)
    except DiagnosticSession.DoesNotExist as exc:
        from rest_framework.exceptions import NotFound

        raise NotFound("Diagnostic session not found.") from exc

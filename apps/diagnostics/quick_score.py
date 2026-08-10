"""Quick Score scoring and OG image generation."""

from __future__ import annotations

import io
from collections import defaultdict

from django.db import transaction
from PIL import Image, ImageDraw, ImageFont
from rest_framework.exceptions import ValidationError

from apps.diagnostics.models import (
    QuickScoreAttempt,
    QuickScoreChoice,
    QuickScoreParagraph,
    QuickScoreQuestion,
)


BAND_THRESHOLDS = [
    (75, QuickScoreParagraph.Band.SOLID_FOUNDATION),
    (55, QuickScoreParagraph.Band.EMERGING_GAPS),
    (35, QuickScoreParagraph.Band.AT_RISK),
    (0, QuickScoreParagraph.Band.SIGNIFICANT_GAP),
]

BAND_LABELS = {
    QuickScoreParagraph.Band.SOLID_FOUNDATION: "Solid Foundation",
    QuickScoreParagraph.Band.EMERGING_GAPS: "Emerging Gaps",
    QuickScoreParagraph.Band.AT_RISK: "At Risk of Falling Behind",
    QuickScoreParagraph.Band.SIGNIFICANT_GAP: "Significant Gap",
}


def infer_track(*, current_role: str = "", known_skills: list[str] | None = None) -> str:
    text = f"{current_role} {' '.join(known_skills or [])}".lower()
    backend_signals = ("django", "fastapi", "python", "backend", "postgres", "sql", "api")
    frontend_signals = ("react", "next", "frontend", "typescript", "javascript", "ui")
    be = sum(1 for s in backend_signals if s in text)
    fe = sum(1 for s in frontend_signals if s in text)
    if be > fe:
        return QuickScoreQuestion.Track.BACKEND
    return QuickScoreQuestion.Track.FRONTEND


def get_quick_score_questions(
    *,
    track: str,
    user=None,
    years_of_experience: int | None = None,
    limit: int = 5,
):
    """Return a per-user, experience-aware Quick Score set. Never repeats for a user."""
    from apps.diagnostics.adaptive_selector import (
        _rng,
        experience_difficulty_band,
    )

    qs = list(
        QuickScoreQuestion.objects.filter(track=track, is_active=True)
        .prefetch_related("choices")
        .order_by("order", "id")
    )
    if not qs:
        return []

    seen_ids: set[int] = set()
    if user is not None:
        for attempt in QuickScoreAttempt.objects.filter(user=user).only("answers"):
            for qid in (attempt.answers or {}).keys():
                try:
                    seen_ids.add(int(qid))
                except (TypeError, ValueError):
                    continue

    # Never re-ask a Quick Score prompt this user already answered.
    pool = [q for q in qs if q.id not in seen_ids]
    if not pool:
        return []

    min_tier, max_tier, _ = experience_difficulty_band(years_of_experience)
    orders = sorted({q.order for q in pool})
    preferred: list = pool
    if len(orders) >= 3:
        low_cut = orders[max(0, len(orders) // 3 - 1)]
        high_cut = orders[min(len(orders) - 1, (2 * len(orders)) // 3)]
        if max_tier <= 2:
            preferred = [q for q in pool if q.order <= high_cut] or pool
        elif min_tier >= 3:
            preferred = [q for q in pool if q.order >= low_cut] or pool
        else:
            preferred = pool

    preferred_ids = {q.id for q in preferred}
    primary = [q for q in pool if q.id in preferred_ids]
    secondary = [q for q in pool if q.id not in preferred_ids]

    seed_parts = [
        getattr(user, "id", "anon"),
        track,
        years_of_experience,
        len(seen_ids),
        "quick-score",
    ]
    rng = _rng(*seed_parts)
    rng.shuffle(primary)
    rng.shuffle(secondary)
    ordered = primary + secondary

    # Drop a user-specific item when the bank is larger than the quiz.
    if user is not None and len(ordered) > limit:
        omit_idx = int(user.id) % len(ordered)
        ordered = ordered[:omit_idx] + ordered[omit_idx + 1 :]

    return ordered[:limit]


def score_to_band(score: int) -> str:
    for threshold, band in BAND_THRESHOLDS:
        if score >= threshold:
            return band
    return QuickScoreParagraph.Band.SIGNIFICANT_GAP


@transaction.atomic
def submit_quick_score(*, user, track: str, answers: list[dict]) -> QuickScoreAttempt:
    questions = {
        q.id: q
        for q in QuickScoreQuestion.objects.filter(track=track, is_active=True).prefetch_related(
            "choices"
        )
    }
    if not questions:
        raise ValidationError("No quick score questions configured for this track.")

    earned = 0
    possible = 0
    area_scores: dict[str, list[float]] = defaultdict(list)
    answer_map: dict[str, int] = {}

    for item in answers:
        qid = int(item["question_id"])
        cid = int(item["choice_id"])
        question = questions.get(qid)
        if question is None:
            raise ValidationError(f"Invalid question_id: {qid}")
        choice = next((c for c in question.choices.all() if c.id == cid), None)
        if choice is None:
            raise ValidationError(f"Invalid choice_id: {cid}")
        max_points = max((c.points for c in question.choices.all()), default=0)
        weight = question.weight or 1
        earned += choice.points * weight
        possible += max_points * weight
        if max_points:
            area_scores[question.competency_area].append(choice.points / max_points)
        answer_map[str(qid)] = cid

    total = int(round((earned / possible) * 100)) if possible else 0
    band = score_to_band(total)
    paragraph = QuickScoreParagraph.objects.filter(band=band, track=track).first()
    highlight = [
        area
        for area, scores in area_scores.items()
        if (sum(scores) / len(scores)) < 0.6
    ][:3]

    return QuickScoreAttempt.objects.create(
        user=user,
        track=track,
        answers=answer_map,
        total_score=total,
        band=band,
        paragraph_text=(paragraph.body_text if paragraph else ""),
        highlight_areas=highlight,
    )


def render_quick_score_png(attempt: QuickScoreAttempt) -> bytes:
    width, height = 1200, 630
    img = Image.new("RGB", (width, height), "#0B1220")
    draw = ImageDraw.Draw(img)
    try:
        title_font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 56)
        body_font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 32)
        small_font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 24)
    except OSError:
        title_font = ImageFont.load_default()
        body_font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    draw.rectangle([0, 0, width, 12], fill="#3B82F6")
    draw.text((64, 64), "Honed", fill="#93C5FD", font=small_font)
    track_label = attempt.get_track_display()
    draw.text(
        (64, 120),
        f"Your {track_label} Mastery Score",
        fill="#F8FAFC",
        font=body_font,
    )
    draw.text((64, 200), f"{attempt.total_score}/100", fill="#FFFFFF", font=title_font)
    band_label = BAND_LABELS.get(attempt.band, attempt.band)
    draw.text((64, 290), band_label, fill="#60A5FA", font=body_font)
    if attempt.highlight_areas:
        areas = ", ".join(a.replace("_", " ") for a in attempt.highlight_areas)
        draw.text((64, 360), f"Emerging focus: {areas}", fill="#CBD5E1", font=small_font)
    draw.text(
        (64, 540),
        "Daily technical mastery through struggle, not consumption.",
        fill="#64748B",
        font=small_font,
    )

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def ensure_default_quick_score_content(*, force: bool = False) -> None:
    if (
        not force
        and QuickScoreQuestion.objects.filter(is_active=True).exists()
        and QuickScoreParagraph.objects.exists()
    ):
        # Keep choice IDs stable across requests; only seed when empty.
        return

    paragraphs = [
        (
            "frontend",
            "solid_foundation",
            "You show a solid frontend foundation. Keep sharpening edge cases around rendering, state, and framework-specific patterns so confidence stays ahead of AI-assisted shortcuts.",
        ),
        (
            "frontend",
            "emerging_gaps",
            "You have workable frontend instincts with emerging gaps. A focused diagnostic will pinpoint which React/Next fundamentals need deliberate practice.",
        ),
        (
            "frontend",
            "at_risk",
            "Your frontend score suggests confidence may outpace depth in key areas. Closing those gaps now prevents skill atrophy as AI tools take on more routine UI work.",
        ),
        (
            "frontend",
            "significant_gap",
            "There is meaningful room to rebuild frontend mastery. Start with fundamentals, then layer framework-specific challenges — proof beats vibes.",
        ),
        (
            "backend",
            "solid_foundation",
            "You show a solid backend foundation. Deepen ORM, async, and data-layer instincts so you can defend designs under real production pressure.",
        ),
        (
            "backend",
            "emerging_gaps",
            "You have workable backend instincts with emerging gaps. A full diagnostic will map Django/FastAPI/Postgres areas that need deliberate practice.",
        ),
        (
            "backend",
            "at_risk",
            "Your backend score suggests gaps that AI copilots can hide in day-to-day work. Closing them restores interview-ready confidence.",
        ),
        (
            "backend",
            "significant_gap",
            "There is meaningful room to rebuild backend mastery. Start with core Python/SQL patterns, then framework-specific challenges.",
        ),
    ]
    for track, band, body in paragraphs:
        QuickScoreParagraph.objects.update_or_create(
            track=track,
            band=band,
            defaults={"body_text": body},
        )

    samples = [
        (
            "frontend",
            "hooks",
            "You add a subscription in useEffect. What is the safest pattern for cleanup?",
            [
                ("Return an unsubscribe/cleanup function from the effect", 3),
                ("Rely on garbage collection alone", 0),
                ("Clear it only in CSS", 1),
            ],
        ),
        (
            "frontend",
            "rendering",
            "A child re-renders whenever the parent renders even though its props look unchanged. What should you check first?",
            [
                ("Whether props are new object/array identities each render", 3),
                ("Whether the browser zoom level changed", 0),
                ("Whether Tailwind classes are alphabetized", 1),
            ],
        ),
        (
            "frontend",
            "typescript",
            "You receive an API payload typed as unknown. What should you do before reading fields?",
            [
                ("Narrow it with type guards or a schema validator", 3),
                ("Cast to any and move on", 0),
                ("Ignore TypeScript errors in CI", 1),
            ],
        ),
        (
            "frontend",
            "nextjs",
            "You need auth checks before a page renders in the App Router. Which mechanism is the usual first stop?",
            [
                ("middleware.ts for request-level gating", 3),
                ("Putting secrets in NEXT_PUBLIC_ env vars", 0),
                ("Only client useEffect redirects", 1),
            ],
        ),
        (
            "frontend",
            "state_management",
            "Three sibling components each fetch the same user profile independently. What is the better default?",
            [
                ("Lift fetching into a shared cache/provider", 3),
                ("Keep three identical fetches for isolation", 0),
                ("Store the profile only in window globals", 1),
            ],
        ),
        (
            "frontend",
            "async",
            "A search box fires requests on every keystroke. What failure mode should you guard against?",
            [
                ("Out-of-order responses overwriting newer results", 3),
                ("Too many CSS transitions", 0),
                ("Missing favicon", 0),
            ],
        ),
        (
            "backend",
            "orm",
            "A list endpoint becomes slow after nesting related serializers. What is the most likely ORM issue?",
            [
                ("N+1 queries from related object access", 3),
                ("Missing HTTPS certificates", 0),
                ("Too many CSS files", 1),
            ],
        ),
        (
            "backend",
            "async",
            "An async FastAPI route calls a sync ORM method directly. What is the main risk?",
            [
                ("Blocking the event loop and reducing concurrency", 3),
                ("Disabling database indexes", 0),
                ("Breaking JSON encoding permanently", 1),
            ],
        ),
        (
            "backend",
            "sql",
            "EXPLAIN shows a sequential scan filtering a large table by email = $1. What should you verify first?",
            [
                ("Whether a usable index exists on email", 3),
                ("Whether the table name is capitalized", 0),
                ("Whether Redis is installed", 1),
            ],
        ),
        (
            "backend",
            "auth",
            "Where should a browser SPA keep a long-lived refresh token?",
            [
                ("HttpOnly Secure cookies", 3),
                ("localStorage as plain text", 1),
                ("In the URL hash", 0),
            ],
        ),
        (
            "backend",
            "api",
            "Clients retry failed writes. Which design helps most?",
            [
                ("Idempotency keys / idempotent methods for safe retries", 3),
                ("Always return 500 so clients keep guessing", 0),
                ("Require CONNECT for every mutation", 1),
            ],
        ),
        (
            "backend",
            "testing",
            "What should a solid API integration test usually verify?",
            [
                ("Status code, response contract, and side effects", 3),
                ("Only that pytest can import the module", 0),
                ("Only that CSS builds", 0),
            ],
        ),
    ]

    # Replace prior bank so local/dev DBs don't keep near-duplicate prompts.
    QuickScoreQuestion.objects.filter(track__in=["frontend", "backend"]).update(
        is_active=False
    )

    for order, (track, area, text, choices) in enumerate(samples, start=1):
        # Per-track ordering so FE/BE each start at 1.
        track_order = order if track == "frontend" else order - 6
        q, _ = QuickScoreQuestion.objects.update_or_create(
            track=track,
            competency_area=area,
            order=track_order,
            defaults={
                "question_text": text,
                "weight": 1,
                "is_active": True,
            },
        )
        existing = list(q.choices.order_by("id"))
        desired = [(choice_text, points) for choice_text, points in choices]
        if len(existing) == len(desired) and all(
            ec.choice_text == dt and ec.points == dp
            for ec, (dt, dp) in zip(existing, desired)
        ):
            continue
        QuickScoreChoice.objects.filter(question=q).delete()
        for choice_text, points in choices:
            QuickScoreChoice.objects.create(
                question=q,
                choice_text=choice_text,
                points=points,
            )

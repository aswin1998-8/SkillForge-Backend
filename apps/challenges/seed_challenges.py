"""Seed sample challenges across modalities with rubrics and follow-ups."""

from __future__ import annotations

from apps.challenges.models import (
    Challenge,
    ChallengeFollowUp,
    ChallengeModelAnswer,
    ChallengeRubricItem,
    ChallengeSkill,
)
from apps.roles.models import Skill


SAMPLE_CHALLENGES = [
    {
        "title": "Explain React Reconciliation",
        "slug": "explain-react-reconciliation",
        "modality": Challenge.Modality.THEORY,
        "difficulty": 1,
        "skill": "react",
        "competency_areas": ["hooks", "components", "rendering", "state"],
        "directions": ["frontend_mastery"],
        "scenario": "A junior asks why React needs keys in lists.",
        "requirements": ["Explain reconciliation", "Explain key purpose"],
        "model_answer": (
            "React reconciles trees by comparing element types and keys. Stable keys "
            "let React match previous instances so state is preserved and work is minimized."
        ),
        "rubric": [
            {
                "text": "Explains tree diff / reconciliation at a high level",
                "strength": "Clear reconciliation mental model",
                "gap": "Reconciliation basics still fuzzy",
                "follow_up": "In your own words, what does React compare between renders?",
            },
            {
                "text": "Explains why unstable keys cause remounts/bugs",
                "strength": "Understands key stability impact",
                "gap": "Key stability trade-offs need practice",
                "follow_up": "What breaks if you use array index as a key while reordering?",
            },
        ],
    },
    {
        "title": "Implement Pagination Helper",
        "slug": "implement-pagination-helper",
        "modality": Challenge.Modality.CODING,
        "difficulty": 2,
        "skill": "django",
        "competency_areas": ["views_api", "pagination", "queryset"],
        "directions": ["backend_mastery"],
        "scenario": "Write a helper to paginate queryset-like results.",
        "requirements": ["Accept page + page_size", "Return slice metadata"],
        "workspace_config": {"language": "python"},
        "model_answer": (
            "Clamp page/page_size, compute offset, return items plus total/pages metadata. "
            "Guard empty lists and page overflow."
        ),
        "rubric": [
            {
                "text": "Computes offset correctly from page and page_size",
                "strength": "Solid pagination arithmetic",
                "gap": "Offset/page math needs tightening",
                "follow_up": "What offset do you use for page=3 and page_size=20?",
            },
            {
                "text": "Handles empty input and out-of-range pages",
                "strength": "Edge-case aware pagination",
                "gap": "Boundary cases for pagination are incomplete",
                "follow_up": "What should happen when page exceeds total pages?",
            },
        ],
    },
    {
        "title": "Diagnose N+1 Query Spike",
        "slug": "diagnose-nplus1-query-spike",
        "modality": Challenge.Modality.DIAGNOSE,
        "difficulty": 2,
        "skill": "django",
        "competency_areas": ["models_orm", "performance", "queryset"],
        "directions": ["backend_mastery", "fe_to_be"],
        "scenario": "An API endpoint suddenly takes 4s under load after adding nested serializers.",
        "requirements": ["State a primary hypothesis", "Propose a verification step"],
        "workspace_config": {
            "symptoms": [
                "p95 latency jumped from 180ms to 4.1s",
                "CPU mostly idle while DB connections spike",
                "Recently added nested author profile on list endpoint",
            ],
            "logs": [
                "SELECT * FROM posts LIMIT 50",
                "SELECT * FROM users WHERE id = 12",
                "SELECT * FROM users WHERE id = 18",
                "... (48 similar user lookups)",
            ],
        },
        "model_answer": (
            "Classic N+1: list fetches posts then one query per related user. Fix with "
            "select_related/prefetch_related and verify with query counting."
        ),
        "rubric": [
            {
                "text": "Identifies N+1 / missing prefetch as likely cause",
                "strength": "Strong ORM performance diagnosis",
                "gap": "N+1 pattern recognition needs practice",
                "follow_up": "Which ORM tools would you use to confirm N+1?",
            },
            {
                "text": "Proposes a concrete verification (query count / EXPLAIN)",
                "strength": "Evidence-driven debugging habit",
                "gap": "Verification step was weak",
                "follow_up": "How would you prove the fix without deploying?",
            },
        ],
    },
    {
        "title": "Research SSR Caching Trade-offs",
        "slug": "research-ssr-caching-tradeoffs",
        "modality": Challenge.Modality.RESEARCH,
        "difficulty": 2,
        "skill": "nextjs",
        "competency_areas": ["ssr", "caching", "routing", "data_fetching"],
        "directions": ["frontend_mastery"],
        "scenario": "Your team must choose cache strategy for personalized Next.js pages.",
        "requirements": ["Compare at least two strategies", "Cite sources"],
        "model_answer": (
            "Compare full-route cache vs dynamic rendering with partial caching. Call out "
            "personalization invalidation cost and stale-while-revalidate patterns."
        ),
        "rubric": [
            {
                "text": "Compares at least two caching approaches with trade-offs",
                "strength": "Clear comparative research",
                "gap": "Trade-off comparison needs more structure",
                "follow_up": "When would you refuse full-route caching?",
            },
            {
                "text": "Includes a credible source or docs reference",
                "strength": "Evidence-backed research habit",
                "gap": "Source discipline needs improvement",
                "follow_up": "What official doc would you cite for Next.js caching?",
            },
        ],
    },
    {
        "title": "Sketch Request Path Architecture",
        "slug": "sketch-request-path-architecture",
        "modality": Challenge.Modality.ARCHITECT,
        "difficulty": 2,
        "skill": "fastapi",
        "competency_areas": ["routing", "auth", "middleware", "architecture"],
        "directions": ["backend_mastery", "fe_to_be"],
        "scenario": "Design a simple authenticated read path from client to Postgres.",
        "requirements": ["Show auth boundary", "Show data store"],
        "model_answer": (
            "Client → API gateway/BFF → auth middleware → service → Postgres. Call out "
            "token validation and connection pooling."
        ),
        "rubric": [
            {
                "text": "Shows client, API, and datastore with clear edges",
                "strength": "Readable architecture sketch",
                "gap": "Architecture topology incomplete",
                "follow_up": "Where does auth validation live in your diagram?",
            },
            {
                "text": "Calls out an auth or trust boundary",
                "strength": "Security-aware design",
                "gap": "Trust boundaries need emphasis",
                "follow_up": "What fails if the API trusts client-sent user ids?",
            },
        ],
    },
    {
        "title": "Defend API Error Contract",
        "slug": "defend-api-error-contract",
        "modality": Challenge.Modality.DEFEND,
        "difficulty": 2,
        "skill": "fastapi",
        "competency_areas": ["views_api", "validation", "error_handling"],
        "directions": ["backend_mastery", "be_to_fe"],
        "scenario": "A reviewer says your 422 and 500 payloads are inconsistent for FE clients.",
        "requirements": ["Defend a consistent error shape", "Address client ergonomics"],
        "model_answer": (
            "Standardize code/message/details fields. Map validation errors to 422 with "
            "field paths; reserve 500 for unexpected faults without leaking internals."
        ),
        "rubric": [
            {
                "text": "Proposes a consistent error envelope",
                "strength": "Strong API contract thinking",
                "gap": "Error envelope design needs practice",
                "follow_up": "Which fields belong in every error response?",
            },
            {
                "text": "Separates validation vs unexpected failures",
                "strength": "Clear status-code semantics",
                "gap": "Status-code semantics still muddy",
                "follow_up": "Why shouldn't validation failures return 500?",
            },
        ],
    },
    {
        "title": "Explain This Hook Diff",
        "slug": "explain-this-hook-diff",
        "modality": Challenge.Modality.EXPLAIN_CODE,
        "difficulty": 1,
        "skill": "react",
        "competency_areas": ["hooks", "effects", "state"],
        "directions": ["frontend_mastery", "be_to_fe"],
        "scenario": "Explain what changed between two useEffect dependency arrays.",
        "requirements": ["Describe behavior change", "Call out risk"],
        "workspace_config": {"language": "typescript"},
        "model_answer": (
            "Adding a dependency re-runs the effect when that value changes; omitting it "
            "can stale-close over old state. Call out infinite loop risks when setting state."
        ),
        "rubric": [
            {
                "text": "Explains when the effect re-runs",
                "strength": "Solid effect dependency reasoning",
                "gap": "Effect timing still needs practice",
                "follow_up": "When does cleanup run relative to a dependency change?",
            },
            {
                "text": "Mentions stale closure or loop risk",
                "strength": "Aware of common effect pitfalls",
                "gap": "Stale closure / loop risks missed",
                "follow_up": "Give an example of an effect that loops forever.",
            },
        ],
    },
    {
        "title": "Use AI Without Atrophy",
        "slug": "use-ai-without-atrophy",
        "modality": Challenge.Modality.USE_AI,
        "difficulty": 1,
        "skill": "typescript",
        "competency_areas": ["tooling", "verification"],
        "directions": ["frontend_mastery", "backend_mastery"],
        "scenario": "You may use an AI assistant, but you must still own the design decisions.",
        "requirements": [
            "List what you asked the AI",
            "List what you verified yourself",
            "State one risk of blind acceptance",
        ],
        "model_answer": (
            "Use AI for scaffolding and alternatives, then verify with tests/docs. Never "
            "ship unread generated code; keep ownership of invariants and failure modes."
        ),
        "rubric": [
            {
                "text": "Separates AI suggestions from self-verified claims",
                "strength": "Healthy AI usage hygiene",
                "gap": "AI/self verification boundary unclear",
                "follow_up": "What did you refuse to accept from the AI without checking?",
            },
            {
                "text": "Names a concrete atrophy/risk if AI is trusted blindly",
                "strength": "Aware of skill-atrophy risk",
                "gap": "Atrophy risk framing needs work",
                "follow_up": "Which skill would atrophy first if you never verify AI output?",
            },
        ],
    },
    {
        "title": "Communicate Incident Timeline",
        "slug": "communicate-incident-timeline",
        "modality": Challenge.Modality.COMMUNICATE,
        "difficulty": 2,
        "skill": "python",
        "competency_areas": ["communicate", "incidents"],
        "directions": ["backend_mastery"],
        "scenario": "Write a short incident update for eng + product after a cache outage.",
        "requirements": ["Include impact", "Include next step", "Avoid blame language"],
        "model_answer": (
            "State user impact, current mitigation, next checkpoint time, and owner. Keep "
            "language factual and avoid speculative blame."
        ),
        "rubric": [
            {
                "text": "States impact and current status clearly",
                "strength": "Clear stakeholder communication",
                "gap": "Impact/status clarity needs practice",
                "follow_up": "What is the minimum viable incident update?",
            },
            {
                "text": "Includes a concrete next step / ETA",
                "strength": "Actionable status updates",
                "gap": "Next-step discipline missing",
                "follow_up": "Why do stakeholders need a next checkpoint time?",
            },
        ],
    },
    {
        "title": "Postgres Indexing Trade-offs",
        "slug": "postgres-indexing-tradeoffs",
        "modality": Challenge.Modality.THEORY,
        "difficulty": 2,
        "skill": "postgresql",
        "competency_areas": ["indexing", "query_plans", "performance"],
        "directions": ["backend_mastery", "fe_to_be"],
        "scenario": "Explain when a B-tree index helps and when it hurts a write-heavy table.",
        "requirements": ["Explain read benefit", "Explain write cost"],
        "model_answer": (
            "B-tree indexes speed equality/range reads but add write amplification and "
            "storage. Prefer them for selective filters; avoid indexing low-cardinality "
            "columns on hot write paths."
        ),
        "rubric": [
            {
                "text": "Explains selective read benefit of indexes",
                "strength": "Solid indexing mental model",
                "gap": "Index read benefits still fuzzy",
                "follow_up": "When would a sequential scan beat an index lookup?",
            },
            {
                "text": "Calls out write/storage cost of extra indexes",
                "strength": "Aware of index trade-offs",
                "gap": "Write-cost trade-offs need practice",
                "follow_up": "What happens to INSERT latency as indexes multiply?",
            },
        ],
    },
    {
        "title": "Django Auth Middleware Boundaries",
        "slug": "django-auth-middleware-boundaries",
        "modality": Challenge.Modality.DEFEND,
        "difficulty": 2,
        "skill": "django",
        "competency_areas": ["auth", "middleware", "sessions"],
        "directions": ["backend_mastery"],
        "scenario": "Defend where session auth should be validated in a Django request path.",
        "requirements": ["Name the trust boundary", "Reject client-trusted identity"],
        "model_answer": (
            "Validate the session/cookie server-side in middleware or view decorators. "
            "Never trust a client-sent user id; derive identity from the authenticated session."
        ),
        "rubric": [
            {
                "text": "Places auth validation on the server boundary",
                "strength": "Clear auth boundary thinking",
                "gap": "Auth boundary placement needs work",
                "follow_up": "Why can't the client decide which user_id is authenticated?",
            },
            {
                "text": "Rejects trusting raw client-provided identity",
                "strength": "Security-aware API design",
                "gap": "Client-trust pitfalls still present",
                "follow_up": "What attack becomes trivial if user_id comes from the body?",
            },
        ],
    },
    {
        "title": "Lift State Without Prop Drilling Pain",
        "slug": "lift-state-without-prop-drilling",
        "modality": Challenge.Modality.THEORY,
        "difficulty": 1,
        "skill": "react",
        "competency_areas": ["state_management", "state", "hooks", "components"],
        "directions": ["frontend_mastery", "be_to_fe"],
        "scenario": "Two sibling components need the same form draft. A teammate wants to put it in a global store immediately.",
        "requirements": [
            "Explain when to lift state vs context vs store",
            "Pick a default for this sibling case",
        ],
        "model_answer": (
            "Lift state to the nearest common parent for sibling sharing. Reach for context "
            "when many distant consumers need the same value without prop noise. Prefer a "
            "dedicated store only when updates are frequent, cross-route, or need middleware."
        ),
        "rubric": [
            {
                "text": "Chooses parent lift for nearby sibling sharing",
                "strength": "Clear state ownership instincts",
                "gap": "State ownership boundaries still fuzzy",
                "follow_up": "Where should the draft live if only two siblings need it?",
            },
            {
                "text": "Names a concrete reason to avoid a global store here",
                "strength": "Avoids premature global state",
                "gap": "Store vs lift trade-offs need practice",
                "follow_up": "What cost does a global store add for a single form draft?",
            },
        ],
    },
    {
        "title": "Diagnose Unnecessary Re-renders",
        "slug": "diagnose-unnecessary-rerenders",
        "modality": Challenge.Modality.DIAGNOSE,
        "difficulty": 2,
        "skill": "react",
        "competency_areas": ["rendering", "performance", "hooks"],
        "directions": ["frontend_mastery"],
        "scenario": "A list item re-renders whenever an unrelated parent counter ticks.",
        "requirements": ["State a primary hypothesis", "Propose a verification step"],
        "workspace_config": {
            "symptoms": [
                "Profiler shows list rows lighting up on every parent counter change",
                "Row props are mostly stable primitives except a new inline onClick each render",
            ],
        },
        "model_answer": (
            "Parent re-render passes a new function identity (or unstable object) into rows, "
            "so memoized children still update. Verify with React Profiler and stabilize "
            "handlers with useCallback or move state down."
        ),
        "rubric": [
            {
                "text": "Identifies unstable props / parent render as the cause",
                "strength": "Solid render diagnosis",
                "gap": "Re-render root-cause analysis needs practice",
                "follow_up": "Why does an inline onClick bust React.memo?",
            },
            {
                "text": "Proposes Profiler or prop-identity verification",
                "strength": "Evidence-driven UI debugging",
                "gap": "Verification step was weak",
                "follow_up": "How would you confirm the handler identity changes each render?",
            },
        ],
    },
    {
        "title": "Implement a Tiny useToggle Hook",
        "slug": "implement-tiny-usetoggle-hook",
        "modality": Challenge.Modality.CODING,
        "difficulty": 1,
        "skill": "react",
        "competency_areas": ["hooks", "state_management", "state"],
        "directions": ["frontend_mastery", "be_to_fe"],
        "scenario": "Write a reusable toggle hook for boolean UI state.",
        "requirements": ["Return value + toggle", "Support optional initial value"],
        "workspace_config": {"language": "typescript"},
        "model_answer": (
            "useState(initial ?? false) plus a toggle callback that flips the boolean. "
            "Keep the API stable and avoid resetting on every parent render."
        ),
        "rubric": [
            {
                "text": "Exposes value and a toggle function",
                "strength": "Clean hook API design",
                "gap": "Hook API shape needs tightening",
                "follow_up": "What should useToggle return?",
            },
            {
                "text": "Honors an optional initial value",
                "strength": "Handles initialization correctly",
                "gap": "Initial-state handling incomplete",
                "follow_up": "What is the default when initial is omitted?",
            },
        ],
    },
    {
        "title": "Explain App Router Data Fetching",
        "slug": "explain-app-router-data-fetching",
        "modality": Challenge.Modality.EXPLAIN_CODE,
        "difficulty": 2,
        "skill": "nextjs",
        "competency_areas": ["data_fetching", "ssr_ssg", "routing"],
        "directions": ["frontend_mastery"],
        "scenario": "Explain when a Server Component fetch is cached vs dynamic in the App Router.",
        "requirements": ["Describe cache default", "Call out a dynamic trigger"],
        "workspace_config": {"language": "typescript"},
        "model_answer": (
            "Server Component fetches are cached by default unless opted into dynamic "
            "behavior via no-store, cookies(), headers(), or searchParams-driven rendering."
        ),
        "rubric": [
            {
                "text": "States the default caching behavior correctly",
                "strength": "Clear App Router fetch model",
                "gap": "Fetch cache defaults still fuzzy",
                "follow_up": "Are Server Component fetches cached by default?",
            },
            {
                "text": "Names a concrete dynamic opt-out",
                "strength": "Knows dynamic boundaries",
                "gap": "Dynamic triggers need practice",
                "follow_up": "Name one API that forces dynamic rendering.",
            },
        ],
    },
    {
        "title": "Defend Client vs Server Component Split",
        "slug": "defend-client-vs-server-component-split",
        "modality": Challenge.Modality.DEFEND,
        "difficulty": 2,
        "skill": "nextjs",
        "competency_areas": ["rendering", "routing", "ssr_ssg"],
        "directions": ["frontend_mastery"],
        "scenario": "A reviewer wants every interactive widget marked 'use client' at the page root.",
        "requirements": ["Defend a narrower client boundary", "Call out bundle cost"],
        "model_answer": (
            "Keep the page as a Server Component and push 'use client' to the smallest "
            "interactive leaves so data fetching and static shells stay on the server."
        ),
        "rubric": [
            {
                "text": "Argues for leaf-level client boundaries",
                "strength": "Sound RSC boundary thinking",
                "gap": "Client boundary placement needs work",
                "follow_up": "Why is a page-root use client usually a smell?",
            },
            {
                "text": "Mentions JS bundle or server-capability cost",
                "strength": "Performance-aware composition",
                "gap": "Bundle-cost framing missing",
                "follow_up": "What do you lose when the whole page becomes a client component?",
            },
        ],
    },
]


ALLOWED_CHALLENGE_SLUGS = {spec["slug"] for spec in SAMPLE_CHALLENGES}

# Legacy AI-engineer catalog from the pre-FE/BE seed — deactivate if present.
LEGACY_AI_CHALLENGE_SLUGS = frozenset(
    {
        "explain-rag-chunking-tradeoffs",
        "implement-llm-retry-wrapper",
        "diagnose-prompt-injection-incident",
        "research-agent-memory-strategies",
        "defend-your-eval-harness",
        "architect-observability-for-ai-features",
        "explain-this-retrieval-function",
        "use-ai-to-draft-an-eval-rubric",
        "communicate-an-ai-risk-to-leadership",
    }
)


def deactivate_orphan_challenges() -> int:
    """Deactivate challenges not in the current FE/BE allowlist (incl. legacy AI)."""
    from apps.challenges.models import DailyChallenge

    qs = Challenge.objects.filter(is_active=True).exclude(slug__in=ALLOWED_CHALLENGE_SLUGS)
    # Also force-deactivate known AI slugs even if somehow still active under allowlist miss.
    legacy = Challenge.objects.filter(slug__in=LEGACY_AI_CHALLENGE_SLUGS, is_active=True)
    ids = set(qs.values_list("id", flat=True)) | set(legacy.values_list("id", flat=True))
    if not ids:
        return 0
    deactivated = Challenge.objects.filter(id__in=ids).update(is_active=False)
    DailyChallenge.objects.filter(challenge_id__in=ids).delete()
    return deactivated


def seed_sample_challenges(*, skill_objs: dict[str, Skill]) -> int:
    created = 0
    for spec in SAMPLE_CHALLENGES:
        workspace = dict(spec.get("workspace_config") or {})
        areas = spec.get("competency_areas") or []
        if areas:
            workspace["competency_areas"] = areas
        challenge, _ = Challenge.objects.update_or_create(
            slug=spec["slug"],
            defaults={
                "title": spec["title"],
                "description": spec["scenario"],
                "modality": spec["modality"],
                "difficulty": spec["difficulty"],
                "scenario": spec["scenario"],
                "requirements": spec["requirements"],
                "workspace_config": workspace,
                "directions": spec.get("directions") or [],
                "is_active": True,
            },
        )
        skill = skill_objs.get(spec["skill"])
        if skill:
            ChallengeSkill.objects.update_or_create(challenge=challenge, skill=skill)

        ChallengeModelAnswer.objects.update_or_create(
            challenge=challenge,
            defaults={"reference_text": spec["model_answer"]},
        )

        ChallengeRubricItem.objects.filter(challenge=challenge).delete()
        for idx, item in enumerate(spec["rubric"], start=1):
            rubric = ChallengeRubricItem.objects.create(
                challenge=challenge,
                text=item["text"],
                order=idx,
                strength_fragment=item.get("strength") or "",
                gap_fragment=item.get("gap") or "",
            )
            ChallengeFollowUp.objects.create(
                rubric_item=rubric,
                question_text=item["follow_up"],
                order=1,
            )
        created += 1

    deactivate_orphan_challenges()
    return created

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
        "scenario": (
            "Implement solve(input) where input is a JSON string with "
            "items (list), page (1-based), and page_size. Return a JSON string with "
            "items (page slice), page, page_size, total, and pages."
        ),
        "requirements": [
            "Accept page + page_size",
            "Return slice metadata",
            "Implement solve(input) -> JSON string",
        ],
        "workspace_config": {
            "language": "python",
            "framework": "django",
            "starter_code": (
                "import json\n"
                "\n"
                "def solve(input):\n"
                "    data = json.loads(input)\n"
                "    items = data.get(\"items\") or []\n"
                "    page = int(data.get(\"page\") or 1)\n"
                "    page_size = int(data.get(\"page_size\") or 10)\n"
                "    # TODO: paginate and return JSON string with\n"
                "    # items, page, page_size, total, pages\n"
                "    return json.dumps({\n"
                "        \"items\": items,\n"
                "        \"page\": page,\n"
                "        \"page_size\": page_size,\n"
                "        \"total\": len(items),\n"
                "        \"pages\": 1,\n"
                "    }, separators=(\",\", \":\"))\n"
            ),
            "test_cases": [
                {
                    "id": 0,
                    "order": 0,
                    "is_hidden": False,
                    "input": '{"items":[1,2,3,4,5],"page":1,"page_size":2}',
                    "expected_output": '{"items":[1,2],"page":1,"page_size":2,"total":5,"pages":3}',
                },
                {
                    "id": 1,
                    "order": 1,
                    "is_hidden": False,
                    "input": '{"items":[1,2,3,4,5],"page":2,"page_size":2}',
                    "expected_output": '{"items":[3,4],"page":2,"page_size":2,"total":5,"pages":3}',
                },
                {
                    "id": 2,
                    "order": 2,
                    "is_hidden": True,
                    "input": '{"items":[],"page":1,"page_size":10}',
                    "expected_output": '{"items":[],"page":1,"page_size":10,"total":0,"pages":0}',
                },
                {
                    "id": 3,
                    "order": 3,
                    "is_hidden": True,
                    "input": '{"items":[1,2,3],"page":9,"page_size":2}',
                    "expected_output": '{"items":[],"page":9,"page_size":2,"total":3,"pages":2}',
                },
            ],
        },
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
        "title": "Implement Chunk Array",
        "slug": "implement-chunk-array",
        "modality": Challenge.Modality.CODING,
        "difficulty": 1,
        "skill": "react",
        "competency_areas": ["hooks", "state_management", "state"],
        "directions": ["frontend_mastery", "be_to_fe"],
        "scenario": (
            "Implement solve(input) where input is JSON {\"array\": [...], \"size\": n}. "
            "Return a JSON array of chunks of length size (last chunk may be shorter)."
        ),
        "requirements": [
            "Chunk an array by size",
            "Implement solve(input) -> JSON string",
        ],
        "workspace_config": {
            "language": "javascript",
            "framework": "react",
            "starter_code": (
                "function solve(input) {\n"
                "  const data = JSON.parse(input);\n"
                "  const arr = data.array || [];\n"
                "  const size = Number(data.size);\n"
                "  // TODO: return JSON string of chunked arrays\n"
                "  return JSON.stringify([arr]);\n"
                "}\n"
            ),
            "test_cases": [
                {
                    "id": 0,
                    "order": 0,
                    "is_hidden": False,
                    "input": '{"array":[1,2,3,4,5],"size":2}',
                    "expected_output": "[[1,2],[3,4],[5]]",
                },
                {
                    "id": 1,
                    "order": 1,
                    "is_hidden": False,
                    "input": '{"array":[1,2,3],"size":3}',
                    "expected_output": "[[1,2,3]]",
                },
                {
                    "id": 2,
                    "order": 2,
                    "is_hidden": True,
                    "input": '{"array":[],"size":2}',
                    "expected_output": "[]",
                },
                {
                    "id": 3,
                    "order": 3,
                    "is_hidden": True,
                    "input": '{"array":[1,2,3,4],"size":1}',
                    "expected_output": "[[1],[2],[3],[4]]",
                },
            ],
        },
        "model_answer": (
            "Iterate with a step of size and slice array[i:i+size]. "
            "Return JSON.stringify of the chunks list; empty input yields []."
        ),
        "rubric": [
            {
                "text": "Chunks array into groups of size",
                "strength": "Correct chunking logic",
                "gap": "Chunk boundaries need work",
                "follow_up": "What happens to the last incomplete chunk?",
            },
            {
                "text": "Handles empty arrays",
                "strength": "Edge-case aware",
                "gap": "Empty-input handling incomplete",
                "follow_up": "What should chunk([], 2) return?",
            },
        ],
    },
    {
        "title": "Build Django Query Filter Dict",
        "slug": "implement-django-query-filter-dict",
        "modality": Challenge.Modality.CODING,
        "difficulty": 2,
        "skill": "django",
        "competency_areas": ["views_api", "queryset", "validation"],
        "directions": ["backend_mastery"],
        "scenario": (
            "Implement solve(input) for a Django-style list endpoint. Input JSON has "
            "allowed_fields (list) and query (object of request GET params). Return a "
            "JSON object of ORM filters: only allowed keys, drop empty values, and map "
            "search -> name__icontains when search is present."
        ),
        "requirements": [
            "Whitelist query keys",
            "Map search to name__icontains",
            "Implement solve(input) -> JSON string",
        ],
        "workspace_config": {
            "language": "python",
            "framework": "django",
            "starter_code": (
                "import json\n"
                "\n"
                "def solve(input: str) -> str:\n"
                "    data = json.loads(input)\n"
                "    allowed = set(data.get(\"allowed_fields\") or [])\n"
                "    query = data.get(\"query\") or {}\n"
                "    # TODO: build filters dict and return JSON\n"
                "    return json.dumps({}, separators=(\",\", \":\"))\n"
            ),
            "test_cases": [
                {
                    "id": 0,
                    "order": 0,
                    "is_hidden": False,
                    "input": (
                        '{"allowed_fields":["status","owner_id","search"],'
                        '"query":{"status":"open","owner_id":"3","page":"1"}}'
                    ),
                    "expected_output": '{"status":"open","owner_id":"3"}',
                },
                {
                    "id": 1,
                    "order": 1,
                    "is_hidden": False,
                    "input": (
                        '{"allowed_fields":["status","search"],'
                        '"query":{"search":"hooks","status":""}}'
                    ),
                    "expected_output": '{"name__icontains":"hooks"}',
                },
                {
                    "id": 2,
                    "order": 2,
                    "is_hidden": True,
                    "input": '{"allowed_fields":["status"],"query":{"evil":"1"}}',
                    "expected_output": "{}",
                },
                {
                    "id": 3,
                    "order": 3,
                    "is_hidden": True,
                    "input": (
                        '{"allowed_fields":["search","status"],'
                        '"query":{"search":"x","status":"done"}}'
                    ),
                    "expected_output": '{"name__icontains":"x","status":"done"}',
                },
            ],
        },
        "model_answer": (
            "Iterate query items, skip blanks and non-allowed keys, translate search to "
            "name__icontains, json.dumps with compact separators."
        ),
        "rubric": [
            {
                "text": "Whitelists allowed query fields",
                "strength": "Safe filter construction",
                "gap": "Query whitelist incomplete",
                "follow_up": "Why reject unknown query keys?",
            },
            {
                "text": "Maps search to icontains lookup",
                "strength": "Correct ORM lookup mapping",
                "gap": "Search mapping missing",
                "follow_up": "Which lookup does search become?",
            },
        ],
    },
    {
        "title": "React Class Name Merger",
        "slug": "implement-react-classnames-merge",
        "modality": Challenge.Modality.CODING,
        "difficulty": 1,
        "skill": "react",
        "competency_areas": ["components", "rendering", "state"],
        "directions": ["frontend_mastery"],
        "scenario": (
            "Implement solve(input) for a React utility: input JSON is an array of "
            "tokens (strings, false, null). Return a single className string joining "
            "truthy string tokens with spaces (skip falsy)."
        ),
        "requirements": [
            "Join truthy class tokens",
            "Implement solve(input) -> string",
        ],
        "workspace_config": {
            "language": "typescript",
            "framework": "react",
            "starter_code": (
                "type Token = string | false | null | undefined;\n"
                "\n"
                "function solve(input: string): string {\n"
                "  const tokens = JSON.parse(input) as Token[];\n"
                "  // TODO: return space-joined truthy strings (skip false/null/\"\")\n"
                "  return \"\";\n"
                "}\n"
            ),
            "test_cases": [
                {
                    "id": 0,
                    "order": 0,
                    "is_hidden": False,
                    "input": '["btn","btn-primary",false,null,"active"]',
                    "expected_output": "btn btn-primary active",
                },
                {
                    "id": 1,
                    "order": 1,
                    "is_hidden": False,
                    "input": '[null,false,""]',
                    "expected_output": "",
                },
                {
                    "id": 2,
                    "order": 2,
                    "is_hidden": True,
                    "input": '["only"]',
                    "expected_output": "only",
                },
                {
                    "id": 3,
                    "order": 3,
                    "is_hidden": True,
                    "input": '["a",false,"b","",null,"c"]',
                    "expected_output": "a b c",
                },
            ],
        },
        "model_answer": (
            "JSON.parse the array, filter values that are non-empty strings, join with spaces."
        ),
        "rubric": [
            {
                "text": "Joins truthy class name tokens",
                "strength": "Clean className helper",
                "gap": "Token filtering incomplete",
                "follow_up": "How do you treat empty strings?",
            },
            {
                "text": "Ignores falsy tokens",
                "strength": "Conditional class handling",
                "gap": "Falsy handling incomplete",
                "follow_up": "Why skip false/null in class lists?",
            },
        ],
    },
    {
        "title": "Next.js Search Params Serializer",
        "slug": "implement-nextjs-search-params",
        "modality": Challenge.Modality.CODING,
        "difficulty": 2,
        "skill": "nextjs",
        "competency_areas": ["routing", "data_fetching", "ssr_ssg"],
        "directions": ["frontend_mastery"],
        "scenario": (
            "Implement solve(input) for App Router helpers. Input JSON has params "
            "(object of string | string[] | null). Return a query string without "
            "leading ?, sorted by key, skipping null/empty, repeating keys for arrays."
        ),
        "requirements": [
            "Serialize search params",
            "Stable key order",
            "Implement solve(input) -> query string",
        ],
        "workspace_config": {
            "language": "typescript",
            "framework": "nextjs",
            "starter_code": (
                "type ParamValue = string | string[] | null;\n"
                "\n"
                "function solve(input: string): string {\n"
                "  const data = JSON.parse(input) as { params: Record<string, ParamValue> };\n"
                "  const params = data.params || {};\n"
                "  // TODO: return query string without leading ?\n"
                "  // Skip null and empty strings; repeat keys for arrays; sort keys.\n"
                "  return \"\";\n"
                "}\n"
            ),
            "test_cases": [
                {
                    "id": 0,
                    "order": 0,
                    "is_hidden": False,
                    "input": '{"params":{"q":"hooks","page":"2"}}',
                    "expected_output": "page=2&q=hooks",
                },
                {
                    "id": 1,
                    "order": 1,
                    "is_hidden": False,
                    "input": '{"params":{"tag":["a","b"],"q":"x"}}',
                    "expected_output": "q=x&tag=a&tag=b",
                },
                {
                    "id": 2,
                    "order": 2,
                    "is_hidden": True,
                    "input": '{"params":{"q":"","page":null}}',
                    "expected_output": "",
                },
                {
                    "id": 3,
                    "order": 3,
                    "is_hidden": True,
                    "input": '{"params":{"z":"1","a":"2"}}',
                    "expected_output": "a=2&z=1",
                },
            ],
        },
        "model_answer": (
            "Sort keys, skip null/undefined/empty strings, append key=value for strings and "
            "one entry per array item, join with &."
        ),
        "rubric": [
            {
                "text": "Serializes params with stable ordering",
                "strength": "Deterministic query strings",
                "gap": "Ordering/serialization incomplete",
                "follow_up": "Why sort keys in cache-sensitive URLs?",
            },
            {
                "text": "Supports repeated keys for arrays",
                "strength": "Array param handling",
                "gap": "Array params incomplete",
                "follow_up": "How should tag=[a,b] appear?",
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
    {
        "title": "Audit the AI PR: checkout totals",
        "slug": "audit-ai-pr-checkout-totals",
        "modality": Challenge.Modality.AUDIT_AI_PR,
        "difficulty": 2,
        "skill": "python",
        "competency_areas": ["testing", "error_handling"],
        "directions": ["backend_mastery", "fe_to_be"],
        "scenario": (
            "An AI assistant opened a PR that 'fixes rounding' on checkout totals. "
            "Find and categorize the planted issues. There are 3 issues."
        ),
        "requirements": [
            "Locate each issue in the diff",
            "Categorize as bug, edge_case, style, or security",
            "Assign a severity",
        ],
        "workspace_config": {
            "feature_family": "ai_augment_engineering",
            "challenge_kind": "audit_ai_pr",
            "language": "python",
            "pr": {
                "title": "fix: stabilize checkout rounding",
                "description": "AI-generated change to compute tax-inclusive totals.",
                "diff": (
                    "--- a/checkout.py\n+++ b/checkout.py\n"
                    "@@ -1,12 +1,16 @@\n"
                    " def total(cents, tax_bps=1000):\n"
                    "-    return cents + cents * tax_bps // 10000\n"
                    "+    token = os.environ.get('STRIPE_KEY')\n"
                    "+    print('charging with', token)\n"
                    "+    if cents == None:\n"
                    "+        return 0\n"
                    "+    taxed = cents + cents * tax_bps / 10000\n"
                    "+    return int(taxed)\n"
                ),
            },
            "files": [
                {
                    "path": "checkout.py",
                    "content": (
                        "import os\n\n"
                        "def total(cents, tax_bps=1000):\n"
                        "    token = os.environ.get('STRIPE_KEY')\n"
                        "    print('charging with', token)\n"
                        "    if cents == None:\n"
                        "        return 0\n"
                        "    taxed = cents + cents * tax_bps / 10000\n"
                        "    return int(taxed)\n"
                    ),
                }
            ],
            "planted_issues": [
                {
                    "id": "sec-log",
                    "file": "checkout.py",
                    "start_line": 5,
                    "end_line": 5,
                    "category": "security",
                    "severity": "high",
                },
                {
                    "id": "bug-float",
                    "file": "checkout.py",
                    "start_line": 8,
                    "end_line": 9,
                    "category": "bug",
                    "severity": "high",
                },
                {
                    "id": "edge-none",
                    "file": "checkout.py",
                    "start_line": 6,
                    "end_line": 7,
                    "category": "edge_case",
                    "severity": "medium",
                },
            ],
        },
        "model_answer": (
            "Do not log secrets. Integer money math should stay integer (no float tax). "
            "None cents is an edge case that should raise, not silently become 0."
        ),
        "rubric": [
            {
                "text": "Flags secret logging of the Stripe key",
                "strength": "Caught the security leak",
                "gap": "Missed secret logging",
                "follow_up": "Where should credentials live instead of stdout?",
            },
            {
                "text": "Flags float tax math as a money bug",
                "strength": "Caught rounding/float money bug",
                "gap": "Float tax math slipped through",
                "follow_up": "Why is integer bps math safer for money?",
            },
        ],
    },
    {
        "title": "Explain what the AI changed",
        "slug": "explain-ai-diff-memo-cache",
        "modality": Challenge.Modality.EXPLAIN_AI_DIFF,
        "difficulty": 2,
        "skill": "react",
        "competency_areas": ["hooks", "performance", "rendering"],
        "directions": ["frontend_mastery", "be_to_fe"],
        "scenario": (
            "An AI refactored a list filter. No PR description. Explain what changed "
            "and why it works — or why it doesn't."
        ),
        "requirements": [
            "Describe the before/after behavior",
            "Explain why memoization was added",
            "Call out a remaining risk",
        ],
        "workspace_config": {
            "feature_family": "ai_augment_engineering",
            "challenge_kind": "explain_ai_diff",
            "language": "typescript",
            "before": (
                "export function VisibleItems({ items, query }: Props) {\n"
                "  const visible = items.filter((item) => item.name.includes(query));\n"
                "  return <List rows={visible} />;\n"
                "}\n"
            ),
            "after": (
                "export function VisibleItems({ items, query }: Props) {\n"
                "  const visible = useMemo(\n"
                "    () => items.filter((item) => item.name.includes(query)),\n"
                "    [items],\n"
                "  );\n"
                "  return <List rows={visible} />;\n"
                "}\n"
            ),
        },
        "model_answer": (
            "The AI wrapped the filter in useMemo but omitted query from the dependency "
            "array, so results go stale when the search string changes. The memoization "
            "intent is to skip refiltering when items is stable, but the missing dep is a bug."
        ),
        "rubric": [
            {
                "text": "Notes useMemo wrapping the filter",
                "strength": "Saw the memoization change",
                "gap": "Did not describe the memo wrap",
                "follow_up": "When would this memo actually skip work?",
            },
            {
                "text": "Calls out query missing from the dependency array",
                "strength": "Caught the stale-query bug",
                "gap": "Missed the incomplete dependency list",
                "follow_up": "What UI bug does a missing query dep cause?",
            },
        ],
    },
    {
        "title": "Add discounts to a messy cart",
        "slug": "inherited-cart-discounts",
        "modality": Challenge.Modality.INHERITED_CODEBASE,
        "difficulty": 2,
        "skill": "python",
        "competency_areas": ["testing", "data_structures"],
        "directions": ["backend_mastery"],
        "scenario": (
            "You inherited a small cart. Add percent discounts applied BEFORE tax, "
            "without taxing tax-exempt items."
        ),
        "requirements": [
            "Honor discount_pct on the payload",
            "Apply discount before tax",
            "Exempt items must stay untaxed",
        ],
        "constraints": ["Do not drop existing tax behavior for non-exempt items"],
        "workspace_config": {
            "language": "python",
            "files": {
                "pricing.py": (
                    "def line_total(cents, qty, exempt=False, discount_pct=0):\n"
                    "    subtotal = int(cents) * int(qty)\n"
                    "    taxed = subtotal if exempt else subtotal + subtotal // 10\n"
                    "    if discount_pct:\n"
                    "        return int(taxed * (100 - int(discount_pct)) / 100)\n"
                    "    return taxed\n"
                ),
                "cart.py": (
                    "import json\n"
                    "from pricing import line_total\n"
                    "\n"
                    "def solve(raw):\n"
                    "    data = json.loads(raw)\n"
                    "    discount = int(data.get('discount_pct') or 0)\n"
                    "    total = 0\n"
                    "    for item in data.get('items') or []:\n"
                    "        total += line_total(\n"
                    "            item.get('cents') or 0,\n"
                    "            item.get('qty') or 1,\n"
                    "            bool(item.get('exempt')),\n"
                    "            discount,\n"
                    "        )\n"
                    "    return total\n"
                ),
            },
            "test_cases": [
                {
                    "id": 0,
                    "order": 0,
                    "is_hidden": False,
                    "input": '{"items":[{"cents":1000,"qty":1,"exempt":false}],"discount_pct":0}',
                    "expected_output": "1100",
                },
                {
                    "id": 1,
                    "order": 1,
                    "is_hidden": False,
                    "input": '{"items":[{"cents":1000,"qty":1,"exempt":false}],"discount_pct":10}',
                    "expected_output": "990",
                },
                {
                    "id": 2,
                    "order": 2,
                    "is_hidden": True,
                    "input": '{"items":[{"cents":1000,"qty":1,"exempt":true}],"discount_pct":10}',
                    "expected_output": "900",
                },
            ],
        },
        "model_answer": (
            "Discount the pre-tax subtotal, then add 10% tax only when exempt is false."
        ),
        "rubric": [
            {
                "text": "Applies discount before tax",
                "strength": "Discount/tax order is correct",
                "gap": "Discount still applied after tax",
                "follow_up": "Why does post-tax discount break finance reporting?",
            },
            {
                "text": "Keeps exempt items untaxed",
                "strength": "Preserved the exempt invariant",
                "gap": "Exempt items were taxed",
                "follow_up": "What test would lock the exempt invariant?",
            },
        ],
    },
    {
        "title": "War room: checkout 500s",
        "slug": "war-room-checkout-500s",
        "modality": Challenge.Modality.WAR_ROOM,
        "difficulty": 3,
        "skill": "python",
        "competency_areas": ["error_handling", "testing"],
        "directions": ["backend_mastery"],
        "scenario": (
            "Prod is throwing 500s on checkout. Diagnose, answer your teammate, "
            "and propose a fix — one continuous incident, not isolated quiz cards."
        ),
        "requirements": [
            "Name the failing code path",
            "Give a realistic ETA",
            "Propose a concrete fix",
        ],
        "workspace_config": {
            "beats": [
                {
                    "id": "logs",
                    "type": "logs",
                    "title": "Pager: checkout 500s",
                    "content": (
                        "ERROR checkout.views charge() TypeError: unsupported operand "
                        "type(s) for +: 'int' and 'NoneType'\n"
                        "File checkout/pricing.py line 18 in add_tax\n"
                        "    return cents + cents * rate\n"
                        "rate=None for merchant_id=9 (EU VAT lookup timed out)"
                    ),
                    "prompt": "What is breaking, and what is the blast radius?",
                },
                {
                    "id": "slack",
                    "type": "slack",
                    "title": "Slack · @priya",
                    "content": (
                        "priya: leadership wants an ETA in 10 minutes. "
                        "Are we rolling back or patching?"
                    ),
                    "prompt": "Reply with impact, ETA, and next checkpoint. No blame.",
                },
                {
                    "id": "hypothesis",
                    "type": "slack",
                    "title": "Slack · @priya",
                    "content": (
                        "priya: infra thinks it's Redis. Can you confirm or kill that theory?"
                    ),
                    "prompt": "Agree or push back with evidence from the logs.",
                },
                {
                    "id": "fix",
                    "type": "fix",
                    "title": "Proposed fix",
                    "content": "Need a patch that keeps checkout alive when VAT lookup fails.",
                    "prompt": "Describe the fix (default rate, fail-open vs fail-closed, and a test).",
                },
            ],
        },
        "model_answer": (
            "VAT rate is None after a lookup timeout, then add_tax crashes. Not Redis. "
            "Give a short ETA, patch add_tax to reject/default the rate, and add a test "
            "for None rate. Fail closed for unknown tax rather than silently undercharging."
        ),
        "rubric": [
            {
                "text": "Identifies None tax rate / VAT lookup timeout",
                "strength": "Diagnosed the None rate crash",
                "gap": "Root cause still fuzzy",
                "follow_up": "What log line proves Redis is not involved?",
            },
            {
                "text": "Gives a stakeholder ETA without blame",
                "strength": "Clear incident communication",
                "gap": "ETA/impact communication was weak",
                "follow_up": "What is the minimum viable incident update?",
            },
            {
                "text": "Proposes guarding None rate with a test",
                "strength": "Concrete, testable fix",
                "gap": "Fix stayed hand-wavy",
                "follow_up": "Fail-open or fail-closed for missing VAT?",
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
        # Replaced by implement-chunk-array (executable harness).
        "implement-tiny-usetoggle-hook",
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
                "constraints": spec.get("constraints") or [],
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

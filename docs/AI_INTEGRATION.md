# Honed AI Integration

This document describes how AI integrates into the existing Honed (SkillForge) Django + Next.js application without replacing the architecture.

## Architecture rules

- Backend is the source of truth for scores, assessment state, gaps, roadmap eligibility, and auth.
- AI produces **structured evidence and generated content only**.
- Provider SDKs live only under `apps/ai/providers/`.
- API keys (`GEMINI_API_KEY`, `CLAUDE_API_KEY`) stay on Django; never sent to Next.js.
- Async AI work uses existing Celery + Redis.

```
Next.js → DRF APIs → domain services → apps.ai services → AIProvider → Gemini|Claude|Mock
                              ↓
                         PostgreSQL (evidence, scores, gaps)
```

## Existing architecture (reuse)

| Area | Location | Notes |
|------|----------|--------|
| AI app | `apps/ai/` | Provider ABC, Claude, Mock, factory, prompts, Pydantic schemas |
| Diagnostics | `apps/diagnostics/` | Fixed bank + attempt lifecycle + Celery analysis |
| Gaps | `apps/gaps/` | `UserSkillGap`, `GapEvidence` |
| Challenges | `apps/challenges/` | Daily assignment, submit → debrief |
| Debriefs | `apps/debriefs/` | Socratic Q&A + evaluation |
| Progress | `apps/progress/` | Computed dashboard/roadmap |
| Roles/Skills | `apps/roles/` | `Role`, `Skill`, `RoleSkill.importance` |
| Profile | `apps/users/` | `current_role`, years, `technical_goal`, `target_role`; unused `UserSkill` |
| Frontend | SkillForge-Frontend | Diagnostic → result → roadmap/today → debrief via sessions |

## Existing APIs to extend

- `POST /api/v1/diagnostics/<id>/start/`
- `POST /api/v1/attempts/<id>/answers/` (legacy batch)
- `POST /api/v1/attempts/<id>/submit/`
- `GET /api/v1/attempts/<id>/`
- `GET /api/v1/gaps/`, `GET /api/v1/roadmap/`
- Challenge submit + debrief answer endpoints

## What this integration adds

1. **GeminiProvider** (default) + expanded `AIProvider` interface; Claude remains selectable.
2. **Adaptive assessment**: AI-generated turns (`DiagnosticTurn`), stages FOUNDATION→…→CODE_REVIEW; bank is fallback.
3. **Evidence ledger** (`SkillEvidence`) + deterministic weighted scoring.
4. **SkillTransfer** + backend gap classification; AI explains only.
5. **Roadmap**: DB eligibility first, AI ranks/annotates.
6. **Challenge AI evaluation** + debrief handoff id to frontend.
7. **AIRequestLog** for observability (no secrets).

## Where AI lives

- Providers: `apps/ai/providers/`
- Schemas: `apps/ai/schemas/`
- Prompts: `apps/ai/prompts/{assessment,evaluation,analysis,debrief}/`
- Orchestration: `apps/ai/services/`
- Domain persistence: `diagnostics`, `gaps`, `roles`, `challenges`, `debriefs`, `progress`

## Frontend flows extended

- Turn-based diagnostic question UI
- Richer results (scores, transfers, gaps)
- API-driven roadmap (both growth paths)
- Challenge submit → debrief redirect

## Environment

```
AI_PROVIDER=gemini
GEMINI_API_KEY=
GEMINI_MODEL=gemini-flash-latest
CLAUDE_API_KEY=
CLAUDE_MODEL=claude-sonnet-4-20250514
```

See backend `.env.example`. Frontend does not receive these keys.

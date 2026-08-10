# SkillForge Backend

Django REST API for Honed — a technical mastery platform for software engineers.

## Stack

- Django 5 + Django REST Framework
- PostgreSQL
- Redis + Celery (email and background tasks only — no runtime AI)
- SimpleJWT in HttpOnly cookies
- Static diagnostic content with rule-based adaptive selection
- OpenAPI via drf-spectacular (`/api/docs/`)

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements/dev.txt
cp .env.example .env
python manage.py migrate
python manage.py seed_data
python manage.py runserver 8000
```

## Static diagnostic content

All diagnostic questions are manually authored and imported as static data.

- **Admin:** `/admin/` — `FundamentalsTopic`, `FrameworkTopic`, `Question`, and related models
- **Bulk import:** `python manage.py import_questions --file content/sample_questions.json`

Frameworks covered: React, Next.js, Django, FastAPI (with JS/Python fundamentals layers).

## Code execution (coding / find_issues modalities)

Coding answers are graded by running user code via **process-level subprocess execution** with:

- Hard timeout (`CODE_EXECUTION_TIMEOUT_SECONDS`, default 5s)
- AST import blocklist for Python (blocks `os`, `subprocess`, `socket`, etc.)
- Identifier blocklist for JavaScript
- Output size caps

**Security note:** Process-level execution is suitable for authenticated MVP users only. It is not safe against determined escape attempts from untrusted public input. Plan to upgrade to Docker or Judge0 before opening coding execution to anonymous users.

Disable execution entirely with `CODE_EXECUTION_ENABLED=False`.

User code should define `solve(input)` returning the answer; the harness prints the result for comparison against `CodingTestCase.expected_output`.

## Adaptive selection

Rule-based (not AI). Tunable via env vars:

- `ADAPTIVE_WEAK_THRESHOLD` (default 0.4)
- `ADAPTIVE_STRONG_THRESHOLD` (default 0.7)
- `ADAPTIVE_ROLLING_WINDOW` (default 5)

Selection decisions are logged on `DiagnosticSession.selection_log` for inspection.

## Tests

```bash
pytest
```

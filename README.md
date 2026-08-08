# SkillForge Backend

Django REST API for SkillForge — a technical mastery platform for developers.

## Stack

- Django 5 + Django REST Framework
- PostgreSQL
- Redis + Celery
- SimpleJWT in HttpOnly cookies
- AI provider abstraction (Claude, with mock fallback)
- OpenAPI via drf-spectacular (`/api/docs/`)

## Local setup (no Docker)

### 1. Homebrew services

```bash
brew install postgresql@16 redis
brew services start postgresql@16
brew services start redis
```

This project expects Homebrew Postgres on **port 5433** (default when another Postgres already uses 5432):

```bash
export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"
createdb -p 5433 skillforge
```

### 2. Python env

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements/dev.txt
cp .env.example .env
# Edit DATABASE_URL if needed
```

### 3. Migrate & seed

```bash
python manage.py migrate
python manage.py seed_data
```

### 4. Run API + Celery

```bash
python manage.py runserver 8000
celery -A config worker -l info
```

Health check: [http://127.0.0.1:8000/api/v1/health/](http://127.0.0.1:8000/api/v1/health/)  
API docs: [http://127.0.0.1:8000/api/docs/](http://127.0.0.1:8000/api/docs/)

### 5. Tests

```bash
pytest
```

## Auth

- `POST /api/v1/auth/register/`
- `POST /api/v1/auth/login/`
- `POST /api/v1/auth/google/` (GIS ID token)
- `POST /api/v1/auth/logout/`
- `POST /api/v1/auth/refresh/`
- `GET /api/v1/auth/me/`

JWT access/refresh tokens are set as HttpOnly cookies (`sf_access`, `sf_refresh`).

## AI

Set `CLAUDE_API_KEY` in `.env` to use Claude. If empty, `MockAIProvider` is used so local flows work offline.

## Production (EC2)

See [docs/EC2_DEPLOY.md](docs/EC2_DEPLOY.md).

# UCL Predictor

Predicts UEFA Champions League match outcomes. A Python engine ingests fixtures and results,
fits models, simulates the tournament and stores everything in Postgres. A Next.js app reads
those results and presents them.

## Architecture

- **`apps/engine`** (Python 3.12, uv): ingest, modelling, simulation and evaluation, plus a small
  FastAPI service. It **owns the database schema** (Alembic migrations in `apps/engine/migrations`)
  and performs **all writes**.
- **`apps/web`** (Next.js App Router, Tailwind, shadcn/ui): **read-only** access to Postgres
  through Drizzle ORM. Never runs migrations.
- **Database**: hosted Supabase Postgres (session pooler, port 5432). Both apps read
  `DATABASE_URL` from the single repo-root `.env`. No Docker.

## Setup (Windows, PowerShell)

Prerequisites: Node 24+, pnpm, uv, git.

```powershell
git clone <repo-url> ucl-predictor
cd ucl-predictor

# 1. Secrets: copy the template and fill in DATABASE_URL and FOOTBALL_DATA_TOKEN
Copy-Item .env.example .env
notepad .env

# 2. Web dependencies (from the repo root)
pnpm install

# 3. Engine dependencies (uv installs Python 3.12 if needed)
cd apps\engine
uv sync
uv run alembic upgrade head
cd ..\..

# 4. Optional: git hooks (ruff + prettier)
uvx pre-commit install
```

## Run

```powershell
# Engine API -> http://localhost:8000/health
cd apps\engine
uv run uvicorn engine.api.main:app --reload --port 8000

# Web (separate terminal, repo root) -> http://localhost:3000/api/health
pnpm dev:web
```

## Checks

```powershell
cd apps\engine; uv run ruff check .; uv run ruff format --check .; uv run pytest; cd ..\..
pnpm --filter web lint; pnpm --filter web typecheck; pnpm --filter web build
```

CI (`.github/workflows/ci.yml`) runs the same checks with no database.

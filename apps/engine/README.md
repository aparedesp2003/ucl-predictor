# engine

Python data/ML engine for the UCL predictor. See the repo-root README for setup.

## Data ingest

```sh
uv run alembic upgrade head
uv run python -m engine.ingest football-data                        # current season (football-data.org)
uv run python -m engine.ingest openfootball --from 2011-12 --to 2025-26  # past seasons (Football.TXT)
uv run python -m engine.ingest report                               # coverage + data-quality checks
```

Load football-data first: it creates teams with `fd_team_id`, which openfootball names then resolve
against. Raw downloads are cached under `data/raw/` (git-ignored). Team names that normalization
cannot match go in `src/engine/ingest/team_overrides.csv`, each with a reason.

Tests: `uv run pytest` (no network/DB); `RUN_INTEGRATION=1 uv run pytest -m integration` hits the DB
inside a rolled-back transaction.

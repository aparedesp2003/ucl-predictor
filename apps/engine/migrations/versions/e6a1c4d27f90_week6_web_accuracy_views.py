"""week6 web accuracy views

Revision ID: e6a1c4d27f90
Revises: b4fdcdb0088b
Create Date: 2026-11-07 18:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e6a1c4d27f90"
down_revision: str | Sequence[str] | None = "b4fdcdb0088b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Like the week5 views, these are the only relations the web role can SELECT
# (docs/sql/web_readonly.sql).

# One row per (model, finished match from 2026-27 on) with an official pre-kick-off prediction:
# prediction_scores (scored as in engine.evaluate.metrics) plus team names. ``hit`` is the favoured
# outcome (argmax, ties towards H then D) matching the 90-minute result, as isHit in the web app.
WEB_PREDICTION_SCORES = """
CREATE VIEW web_prediction_scores AS
SELECT p.model, p.match_id, p.season, p.stage, p.matchday, p.kickoff_utc, p.match_date,
       p.home_team_id, h.name AS home_name, h.short_name AS home_short_name, h.tla AS home_tla,
       p.away_team_id, a.name AS away_name, a.short_name AS away_short_name, a.tla AS away_tla,
       p.home_goals_90, p.away_goals_90, p.outcome, p.predicted,
       p.p_home, p.p_draw, p.p_away, p.log_loss, p.rps, p.brier,
       p.predicted = p.outcome AS hit,
       COALESCE(p.model = s.value, false) AS is_primary
FROM prediction_scores p
JOIN teams h ON h.id = p.home_team_id
JOIN teams a ON a.id = p.away_team_id
LEFT JOIN settings s ON s.key = 'primary_model'
WHERE p.season >= '2026-27'
ORDER BY COALESCE(p.kickoff_utc, p.match_date::timestamp AT TIME ZONE 'UTC') DESC, p.match_id DESC,
         p.model
"""

# The latest backtest run per model, one row per (model, scope), where scope is a test season or
# 'overall'. Values come straight from model_runs.metrics, nothing is recomputed:
# - elo runs (`elo backtest`) nest summaries per model under each scope ({"elo", "historical",
#   "uniform"}); the two baselines become their own rows. Their calibration is a list of P(home)
#   bins on the test seasons; no away-win table is stored.
# - the Poisson family (`poisson backtest`) stores its own summary per scope and calibration as
#   {"validation" | "test": {"home" | "away": bins}}.
# Calibration (bins of {lo, hi, n, mean_pred, observed}) is only set on the 'overall' rows.
WEB_BACKTEST_SUMMARY = """
CREATE VIEW web_backtest_summary AS
WITH run AS (
    SELECT DISTINCT ON (r.model) r.id, r.model, r.created_at, r.metrics
    FROM model_runs r
    WHERE r.kind = 'backtest' AND jsonb_typeof(r.metrics->'test') = 'object'
    ORDER BY r.model, r.id DESC
), entry AS (
    SELECT run.id AS model_run_id, run.created_at, run.model, 'candidate' AS role, t.key AS scope,
           CASE WHEN run.model = 'elo' THEN t.value->'elo' ELSE t.value END AS summary,
           run.metrics->'calibration' AS calibration
    FROM run
    CROSS JOIN LATERAL jsonb_each(run.metrics->'test') t
    UNION ALL
    SELECT run.id, run.created_at, b.model, 'baseline', t.key, t.value->b.model, NULL
    FROM run
    CROSS JOIN LATERAL jsonb_each(run.metrics->'test') t
    CROSS JOIN (VALUES ('uniform'), ('historical')) b(model)
    WHERE run.model = 'elo'
)
SELECT e.model, e.role, e.model_run_id, e.created_at AS run_created_at, e.scope,
       (e.summary->>'n')::int AS n,
       (e.summary->>'log_loss')::float8 AS log_loss,
       (e.summary->>'rps')::float8 AS rps,
       (e.summary->>'brier')::float8 AS brier,
       (e.summary->>'accuracy')::float8 AS accuracy,
       COALESCE(e.model = s.value, false) AS is_primary,
       CASE WHEN e.scope <> 'overall' THEN NULL
            WHEN jsonb_typeof(e.calibration) = 'array' THEN e.calibration
            WHEN jsonb_typeof(e.calibration->'test'->'home') = 'array'
                THEN e.calibration->'test'->'home'
       END AS calibration_home,
       CASE WHEN e.scope = 'overall' AND jsonb_typeof(e.calibration->'test'->'away') = 'array'
                THEN e.calibration->'test'->'away'
       END AS calibration_away
FROM entry e
LEFT JOIN settings s ON s.key = 'primary_model'
WHERE jsonb_typeof(e.summary) = 'object'
ORDER BY e.role DESC, e.scope, (e.summary->>'log_loss')::float8
"""


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(WEB_PREDICTION_SCORES)
    op.execute(WEB_BACKTEST_SUMMARY)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP VIEW web_backtest_summary")
    op.execute("DROP VIEW web_prediction_scores")

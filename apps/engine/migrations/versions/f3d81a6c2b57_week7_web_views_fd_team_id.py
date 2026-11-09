"""week7 web views expose fd_team_id

Revision ID: f3d81a6c2b57
Revises: e6a1c4d27f90
Create Date: 2026-11-09 10:00:00.000000

Appends the football-data team id (stable across databases, unlike teams.id) to the web views
that carry team names, so the web app can key its display names and badge codes on it.

CREATE OR REPLACE VIEW may only append columns: every existing column keeps its name, type and
position, so the web role's grants, and web code that does not select the new columns, keep
working. No view is created or dropped on upgrade, so docs/sql/web_readonly.sql need not be re-run.

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f3d81a6c2b57"
down_revision: str | Sequence[str] | None = "e6a1c4d27f90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_KICKOFF = "COALESCE(m.kickoff_utc, m.match_date::timestamp AT TIME ZONE 'UTC')"

# The SELECTs below are those of 5c2e7a91d4b3 (web_match_predictions, web_title_odds) and
# e6a1c4d27f90 (web_prediction_scores), with the fd ids as their last columns. The {fd} placeholder
# holds those extra columns on upgrade and is empty on downgrade.

MATCH_PREDICTIONS = """
SELECT m.id AS match_id, s.label AS season, m.stage, m.matchday, m.leg,
       m.kickoff_utc, m.match_date, m.status, m.home_goals_90, m.away_goals_90,
       m.home_team_id, h.name AS home_name, h.short_name AS home_short_name, h.tla AS home_tla,
       m.away_team_id, a.name AS away_name, a.short_name AS away_short_name, a.tla AS away_tla,
       o.p_home, o.p_draw, o.p_away, o.model, o.created_at AS predicted_at{fd}
FROM matches m
JOIN seasons s ON s.id = m.season_id
JOIN teams h ON h.id = m.home_team_id
JOIN teams a ON a.id = m.away_team_id
LEFT JOIN official_primary_predictions o ON o.match_id = m.id
WHERE s.label >= '2026-27'
ORDER BY s.label DESC, {kickoff}, m.id
"""

TITLE_ODDS = """
WITH cur AS (
    SELECT s.id, s.label
    FROM seasons s
    WHERE EXISTS (SELECT 1 FROM matches m WHERE m.season_id = s.id AND m.stage = 'LEAGUE_PHASE')
    ORDER BY s.label DESC
    LIMIT 1
), cur_teams AS (
    SELECT m.home_team_id AS team_id FROM matches m JOIN cur ON m.season_id = cur.id
    WHERE m.stage = 'LEAGUE_PHASE'
    UNION
    SELECT m.away_team_id FROM matches m JOIN cur ON m.season_id = cur.id
    WHERE m.stage = 'LEAGUE_PHASE'
), run AS (
    SELECT r.id, r.n_sims, r.as_of, r.created_at
    FROM simulation_runs r
    WHERE EXISTS (SELECT 1 FROM team_simulation_results t WHERE t.simulation_run_id = r.id)
      AND NOT EXISTS (SELECT 1 FROM team_simulation_results t
                      WHERE t.simulation_run_id = r.id
                        AND t.team_id NOT IN (SELECT team_id FROM cur_teams))
    ORDER BY r.id DESC
    LIMIT 1
)
SELECT cur.label AS season, run.id AS simulation_run_id,
       t.team_id, tm.name, tm.short_name, tm.tla,
       t.p_top8, t.p_playoff, t.p_out, t.p_r16, t.p_qf, t.p_sf, t.p_final, t.p_win,
       t.expected_points,
       run.n_sims, run.created_at AS run_created_at, run.as_of AS results_through{fd}
FROM run
CROSS JOIN cur
JOIN team_simulation_results t ON t.simulation_run_id = run.id
JOIN teams tm ON tm.id = t.team_id
"""

PREDICTION_SCORES = """
SELECT p.model, p.match_id, p.season, p.stage, p.matchday, p.kickoff_utc, p.match_date,
       p.home_team_id, h.name AS home_name, h.short_name AS home_short_name, h.tla AS home_tla,
       p.away_team_id, a.name AS away_name, a.short_name AS away_short_name, a.tla AS away_tla,
       p.home_goals_90, p.away_goals_90, p.outcome, p.predicted,
       p.p_home, p.p_draw, p.p_away, p.log_loss, p.rps, p.brier,
       p.predicted = p.outcome AS hit,
       COALESCE(p.model = s.value, false) AS is_primary{fd}
FROM prediction_scores p
JOIN teams h ON h.id = p.home_team_id
JOIN teams a ON a.id = p.away_team_id
LEFT JOIN settings s ON s.key = 'primary_model'
WHERE p.season >= '2026-27'
ORDER BY COALESCE(p.kickoff_utc, p.match_date::timestamp AT TIME ZONE 'UTC') DESC, p.match_id DESC,
         p.model
"""

_HOME_AWAY_FD = ",\n       h.fd_team_id AS home_fd_team_id, a.fd_team_id AS away_fd_team_id"

VIEWS: list[tuple[str, str, str]] = [
    ("web_match_predictions", MATCH_PREDICTIONS, _HOME_AWAY_FD),
    ("web_title_odds", TITLE_ODDS, ",\n       tm.fd_team_id"),
    ("web_prediction_scores", PREDICTION_SCORES, _HOME_AWAY_FD),
]


def _select(sql: str, fd: str) -> str:
    return sql.replace("{fd}", fd).replace("{kickoff}", _KICKOFF)


def upgrade() -> None:
    """Upgrade schema."""
    for name, sql, fd in VIEWS:
        op.execute(f"CREATE OR REPLACE VIEW {name} AS {_select(sql, fd)}")


def downgrade() -> None:
    """Downgrade schema.

    Postgres cannot drop view columns in place, so each view is dropped and recreated without the
    fd ids. That loses the web role's grants: re-run docs/sql/web_readonly.sql afterwards.
    """
    for name, sql, _ in reversed(VIEWS):
        op.execute(f"DROP VIEW {name}")
        op.execute(f"CREATE VIEW {name} AS {_select(sql, '')}")

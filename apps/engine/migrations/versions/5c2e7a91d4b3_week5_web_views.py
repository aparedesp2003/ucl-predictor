"""week5 web views

Revision ID: 5c2e7a91d4b3
Revises: 3bf98f27a79b
Create Date: 2026-11-07 10:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5c2e7a91d4b3"
down_revision: str | Sequence[str] | None = "3bf98f27a79b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_KICKOFF = "COALESCE(m.kickoff_utc, m.match_date::timestamp AT TIME ZONE 'UTC')"

# These views are the only relations the web role can SELECT (docs/sql/web_readonly.sql).

# One row per match from 2026-27 on (newest season first), with the official primary prediction
# when one exists (NULL probabilities otherwise).
WEB_MATCH_PREDICTIONS = f"""
CREATE VIEW web_match_predictions AS
SELECT m.id AS match_id, s.label AS season, m.stage, m.matchday, m.leg,
       m.kickoff_utc, m.match_date, m.status, m.home_goals_90, m.away_goals_90,
       m.home_team_id, h.name AS home_name, h.short_name AS home_short_name, h.tla AS home_tla,
       m.away_team_id, a.name AS away_name, a.short_name AS away_short_name, a.tla AS away_tla,
       o.p_home, o.p_draw, o.p_away, o.model, o.created_at AS predicted_at
FROM matches m
JOIN seasons s ON s.id = m.season_id
JOIN teams h ON h.id = m.home_team_id
JOIN teams a ON a.id = m.away_team_id
LEFT JOIN official_primary_predictions o ON o.match_id = m.id
WHERE s.label >= '2026-27'
ORDER BY s.label DESC, {_KICKOFF}, m.id
"""

# Per team, the latest simulation run of the current season (the newest season with league-phase
# matches, as in engine.simulate.store). simulation_runs has no season column, so a run belongs to
# the current season when every team it simulated plays in that season's league phase.
WEB_TITLE_ODDS = """
CREATE VIEW web_title_odds AS
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
       run.n_sims, run.created_at AS run_created_at, run.as_of AS results_through
FROM run
CROSS JOIN cur
JOIN team_simulation_results t ON t.simulation_run_id = run.id
JOIN teams tm ON tm.id = t.team_id
"""

# model_scoreboard plus whether the row's model is the configured primary model (settings), which
# the web role cannot read directly.
WEB_MODEL_SCOREBOARD = """
CREATE VIEW web_model_scoreboard AS
SELECT b.*, COALESCE(b.model = s.value, false) AS is_primary
FROM model_scoreboard b
LEFT JOIN settings s ON s.key = 'primary_model'
"""


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(WEB_MATCH_PREDICTIONS)
    op.execute(WEB_TITLE_ODDS)
    op.execute(WEB_MODEL_SCOREBOARD)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP VIEW web_model_scoreboard")
    op.execute("DROP VIEW web_title_odds")
    op.execute("DROP VIEW web_match_predictions")

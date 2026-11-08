"""web_match_predictions / web_title_odds / web_model_scoreboard on synthetic data (rolled back)."""

import os
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import insert, text

from engine.db.models import (
    Competition,
    Match,
    MatchStatus,
    ModelRunKind,
    Prediction,
    Season,
    SimulationRun,
    Source,
    Stage,
    Team,
    TeamSimulationResult,
)
from engine.models.store import create_model_run, set_primary_model

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.environ.get("RUN_INTEGRATION") != "1", reason="set RUN_INTEGRATION=1"),
]

SEASON = "2999-00"  # sorts after every real season, so it is the "current" one in this transaction
PRIMARY = "test_web_a"
OTHER = "test_web_b"
FUTURE = datetime(2100, 1, 1, 20, tzinfo=UTC)  # created_at = now() is then before kick-off


@pytest.fixture
def conn():
    from engine.db import get_engine

    with get_engine().connect() as connection:
        trans = connection.begin()
        try:
            yield connection
        finally:
            trans.rollback()


@pytest.fixture
def data(conn) -> dict:
    comp = conn.scalar(
        insert(Competition).values(code="TSW", name="test web").returning(Competition.id)
    )
    sid = conn.scalar(
        insert(Season)
        .values(competition_id=comp, label=SEASON, format="league_phase")
        .returning(Season.id)
    )
    a, b, c = (
        conn.scalar(insert(Team).values(name=f"Test {x}", tla=f"T{x}").returning(Team.id))
        for x in "ABC"
    )
    primary_run = create_model_run(conn, ModelRunKind.PREDICT, {}, None, None, model=PRIMARY)
    other_run = create_model_run(conn, ModelRunKind.PREDICT, {}, None, None, model=OTHER)
    set_primary_model(conn, PRIMARY)

    def match(i: int, status: MatchStatus, goals: tuple[int | None, int | None]) -> int:
        return conn.scalar(
            insert(Match)
            .values(season_id=sid, source=Source.MANUAL, source_key=f"test-web-{i}",
                    stage=Stage.LEAGUE_PHASE, matchday=i + 1, match_date=FUTURE.date(),
                    kickoff_utc=FUTURE, home_team_id=a, away_team_id=b, status=status,
                    home_goals_90=goals[0], away_goals_90=goals[1])
            .returning(Match.id)
        )  # fmt: skip

    finished = match(0, MatchStatus.FINISHED, (2, 1))
    unpredicted = match(1, MatchStatus.SCHEDULED, (None, None))
    for run_id, probs in ((primary_run, (0.5, 0.3, 0.2)), (other_run, (0.2, 0.3, 0.5))):
        conn.execute(
            insert(Prediction).values(
                model_run_id=run_id, match_id=finished, p_home=probs[0], p_draw=probs[1],
                p_away=probs[2],
            )
        )  # fmt: skip

    def sim_run(as_of: date, teams: list[int], p_win: float) -> int:
        rid = conn.scalar(
            insert(SimulationRun)
            .values(model_run_id=primary_run, n_sims=1000, seed=1, as_of=as_of)
            .returning(SimulationRun.id)
        )
        for team in teams:
            conn.execute(
                insert(TeamSimulationResult).values(
                    simulation_run_id=rid, team_id=team, p_top8=0.5, p_playoff=0.3, p_out=0.2,
                    p_r16=0.4, p_qf=0.3, p_sf=0.2, p_final=0.1, p_win=p_win,
                    expected_points=12.5, position_hist=[],
                )
            )  # fmt: skip
        return rid

    sim_run(date(2099, 1, 1), [a, b], 0.01)  # older run of this season
    latest = sim_run(date(2099, 2, 1), [a, b], 0.05)
    sim_run(date(2099, 3, 1), [a, c], 0.09)  # newer, but team C is not in this season
    return {"finished": finished, "unpredicted": unpredicted, "latest": latest, "teams": {a, b}}


def test_match_predictions(conn, data):
    rows = {
        r.match_id: r
        for r in conn.execute(
            text("SELECT * FROM web_match_predictions WHERE season = :s"), {"s": SEASON}
        )
    }
    assert set(rows) == {data["finished"], data["unpredicted"]}
    hit = rows[data["finished"]]
    assert (hit.p_home, hit.p_draw, hit.p_away, hit.model) == (0.5, 0.3, 0.2, PRIMARY)
    assert (hit.home_goals_90, hit.away_goals_90, hit.status) == (2, 1, "FINISHED")
    assert (hit.home_tla, hit.away_tla, hit.stage, hit.matchday) == ("TA", "TB", "LEAGUE_PHASE", 1)
    assert hit.predicted_at is not None
    miss = rows[data["unpredicted"]]
    assert (miss.p_home, miss.p_draw, miss.p_away, miss.model, miss.predicted_at) == (None,) * 5


def test_match_predictions_newest_season_first(conn, data):
    first = conn.execute(text("SELECT season FROM web_match_predictions LIMIT 1")).scalar_one()
    assert first == SEASON


def test_title_odds_latest_run_of_current_season(conn, data):
    rows = conn.execute(text("SELECT * FROM web_title_odds")).all()
    assert {r.team_id for r in rows} == data["teams"]
    assert {(r.season, r.simulation_run_id, r.p_win, r.n_sims) for r in rows} == {
        (SEASON, data["latest"], 0.05, 1000)
    }
    assert {r.results_through for r in rows} == {date(2099, 2, 1)}
    assert all(r.run_created_at is not None for r in rows)


def test_model_scoreboard_is_primary(conn, data):
    def flags() -> dict[str, bool]:
        rows = conn.execute(
            text("SELECT model, is_primary, n FROM web_model_scoreboard WHERE season = :s"),
            {"s": SEASON},
        ).all()
        assert {r.n for r in rows} == {1}
        return {r.model: r.is_primary for r in rows}

    assert flags() == {PRIMARY: True, OTHER: False}
    set_primary_model(conn, OTHER)
    assert flags() == {PRIMARY: False, OTHER: True}

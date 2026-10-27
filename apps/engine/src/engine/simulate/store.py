"""Database I/O for the simulator: build inputs from the latest poisson_shrink predict run, store
results."""

import logging
from dataclasses import dataclass
from datetime import date

from sqlalchemy import Connection, insert, select

from engine.db.models import (
    Match,
    MatchStatus,
    ModelRun,
    ModelRunKind,
    Season,
    SimulationRun,
    Stage,
    TeamRating,
    TeamSimulationResult,
)
from engine.models.elo import EloParams
from engine.models.poisson import PoissonParams
from engine.models.store import git_sha, latest_run
from engine.simulate.engine import Fixture, SimResult
from engine.simulate.rules import N_TEAMS

logger = logging.getLogger(__name__)

SIM_MODEL = "poisson_shrink"


@dataclass
class SimInputs:
    season: str
    team_ids: list[int]  # index -> team id
    fixtures: list[Fixture]
    ratings: list[float]
    params: PoissonParams  # shrink already applied
    shrink: float
    model_run_id: int
    as_of: date

    @property
    def n_remaining(self) -> int:
        return sum(f.home_goals is None for f in self.fixtures)


def load_inputs(conn: Connection) -> SimInputs:
    run = latest_run(conn, SIM_MODEL, ModelRunKind.PREDICT)
    if run is None:
        raise RuntimeError("no poisson_shrink predict run; run `python -m engine.models predict`")
    run_id, params = run
    as_of = conn.scalar(select(ModelRun.train_through).where(ModelRun.id == run_id))

    season = conn.scalar(
        select(Season.label)
        .join(Match, Match.season_id == Season.id)
        .where(Match.stage == Stage.LEAGUE_PHASE)
        .order_by(Season.label.desc())
        .limit(1)
    )
    rows = conn.execute(
        select(Match.home_team_id, Match.away_team_id, Match.status, Match.home_goals_90,
               Match.away_goals_90)
        .join(Season, Season.id == Match.season_id)
        .where(Season.label == season, Match.stage == Stage.LEAGUE_PHASE,
               Match.status != MatchStatus.CANCELLED)
    ).all()  # fmt: skip
    team_ids = sorted({r.home_team_id for r in rows} | {r.away_team_id for r in rows})
    if len(team_ids) != N_TEAMS or len(rows) != N_TEAMS * 4:
        raise RuntimeError(
            f"{season}: expected 36 teams / 144 matches, got {len(team_ids)}/{len(rows)}"
        )
    index = {t: i for i, t in enumerate(team_ids)}
    fixtures = [
        Fixture(index[r.home_team_id], index[r.away_team_id], r.home_goals_90, r.away_goals_90)
        if r.status == MatchStatus.FINISHED
        else Fixture(index[r.home_team_id], index[r.away_team_id])
        for r in rows
    ]

    stored = dict(
        conn.execute(
            select(TeamRating.team_id, TeamRating.rating).where(TeamRating.model_run_id == run_id)
        ).all()
    )
    default = EloParams.from_dict(params["elo"]).new_team_rating
    missing = [t for t in team_ids if t not in stored]
    if missing:
        logger.warning("%d teams have no rating; using new_team_rating %s", len(missing), default)
    if season not in params["poisson"]:
        raise RuntimeError(f"predict run {run_id} has no Poisson fit for {season}")
    return SimInputs(
        season=season,
        team_ids=team_ids,
        fixtures=fixtures,
        ratings=[stored.get(t, default) for t in team_ids],
        params=PoissonParams.from_dict(params["poisson"][season]).shrunk(params["shrink"]),
        shrink=params["shrink"],
        model_run_id=run_id,
        as_of=as_of,
    )


def write_results(
    conn: Connection, inputs: SimInputs, result: SimResult, n_sims: int, seed: int,
    sigma: float = 0.0,
) -> int:  # fmt: skip
    sim_id = conn.scalar(
        insert(SimulationRun)
        .values(model_run_id=inputs.model_run_id, n_sims=n_sims, seed=seed, sigma=sigma,
                as_of=inputs.as_of, git_sha=git_sha())
        .returning(SimulationRun.id)
    )  # fmt: skip
    hist = result.position_hist
    conn.execute(
        insert(TeamSimulationResult),
        [
            {
                "simulation_run_id": sim_id,
                "team_id": team_id,
                "p_top8": float(result.p_top8[i]),
                "p_playoff": float(result.p_playoff[i]),
                "p_out": float(result.p_out[i]),
                "p_r16": float(result.prob("r16")[i]),
                "p_qf": float(result.prob("qf")[i]),
                "p_sf": float(result.prob("sf")[i]),
                "p_final": float(result.prob("final")[i]),
                "p_win": float(result.prob("win")[i]),
                "expected_points": float(result.expected_points[i]),
                "position_hist": [float(x) for x in hist[i]],
            }
            for i, team_id in enumerate(inputs.team_ids)
        ],
    )
    return sim_id

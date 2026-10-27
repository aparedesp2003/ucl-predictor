"""Simulator inputs and storage against the real database (rolled-back transaction)."""

import os

import pytest
from sqlalchemy import func, select

from engine.db.models import TeamSimulationResult
from engine.simulate.engine import simulate
from engine.simulate.rules import N_TEAMS
from engine.simulate.store import load_inputs, write_results

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.environ.get("RUN_INTEGRATION") != "1", reason="set RUN_INTEGRATION=1"),
]


@pytest.fixture
def conn():
    from engine.db import get_engine

    with get_engine().connect() as connection:
        trans = connection.begin()
        try:
            yield connection
        finally:
            trans.rollback()


def test_load_simulate_store(conn):
    inputs = load_inputs(conn)
    assert len(inputs.team_ids) == N_TEAMS and len(inputs.fixtures) == 144
    result = simulate(inputs.fixtures, inputs.ratings, inputs.params, n_sims=200, seed=1)
    sim_id = write_results(conn, inputs, result, 200, 1)
    rows = conn.execute(
        select(func.count(), func.sum(TeamSimulationResult.p_win)).where(
            TeamSimulationResult.simulation_run_id == sim_id
        )
    ).one()
    assert rows[0] == N_TEAMS
    assert rows[1] == pytest.approx(1.0)

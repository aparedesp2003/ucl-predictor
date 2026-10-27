from datetime import date

import numpy as np
import pytest

from engine.db.models import Stage
from engine.models.elo import EloParams, EloState, MatchRow
from engine.simulate.uncertainty import default_sigma, estimate_sigma, rating_drift

PARAMS = EloParams(k=20, home_adv=0, season_regression=0.5, use_goal_diff=False)


def _m(id_, season, day, stage, home, away, hg, ag):
    return MatchRow(
        id_, season, stage, date(2015 + int(season[2:4]) - 15, 9, day), None, home, away, hg, ag
    )


def test_drift_is_final_minus_rating_after_third_phase_match():
    g, ko = Stage.GROUP_STAGE, Stage.LAST_16
    matches = [
        _m(1, "2015-16", 1, Stage.QUALIFYING, 1, 3, 2, 0),  # not a group match: not counted
        _m(2, "2015-16", 2, g, 1, 2, 1, 0),
        _m(3, "2015-16", 3, g, 2, 1, 1, 0),
        _m(4, "2015-16", 4, g, 1, 2, 2, 2),  # 3rd group match for 1 and 2
        _m(5, "2015-16", 5, g, 2, 1, 0, 3),
        _m(6, "2015-16", 6, ko, 1, 3, 1, 0),
        _m(7, "2016-17", 1, g, 1, 2, 0, 1),  # next season: regression must not leak into 2015-16
    ]
    state = EloState(PARAMS)
    after3 = {}
    for m in matches[:6]:
        state.apply(m)
        if m.id == 4:
            after3 = {1: state.ratings[1], 2: state.ratings[2]}
    expected = sorted([state.ratings[1] - after3[1], state.ratings[2] - after3[2]])
    drift = rating_drift(matches, PARAMS, seasons=("2015-16", "2015-16"))
    assert sorted(drift["2015-16"]) == pytest.approx(expected)
    assert len(drift["2015-16"]) == 2  # team 3 never played 3 group matches


def test_estimate_sigma_pools_and_reports_per_season():
    est = estimate_sigma({"a": [1.0, -1.0, 3.0], "b": [0.0, 2.0]})
    assert est.n == 5
    assert est.sigma == pytest.approx(np.std([1, -1, 3, 0, 2], ddof=1))
    assert est.per_season["b"] == (pytest.approx(np.std([0, 2], ddof=1)), 2)


DRIFT = {"2021-22": [10.0, -10.0], "2022-23": [20.0, -20.0], "2024-25": [40.0, -40.0],
         "2025-26": [50.0, -50.0], "2026-27": [500.0, -500.0]}  # fmt: skip
FORMATS = {"2021-22": "group_stage", "2022-23": "group_stage", "2024-25": "league_phase",
           "2025-26": "league_phase", "2026-27": "league_phase"}  # fmt: skip


def test_default_sigma_uses_earlier_seasons_of_the_same_format():
    choice = default_sigma(DRIFT, FORMATS, "2026-27")
    assert choice.seasons == ["2024-25", "2025-26"]  # the target season itself is excluded
    assert choice.sigma == pytest.approx(np.std([40, -40, 50, -50], ddof=1))
    assert choice.pooled.n == 8


def test_default_sigma_falls_back_to_pooled_with_fewer_than_two_seasons():
    choice = default_sigma(DRIFT, FORMATS, "2025-26")  # only 2024-25 is an earlier league phase
    assert choice.basis.startswith("pooled")
    assert choice.seasons == ["2021-22", "2022-23", "2024-25"]
    assert choice.sigma == pytest.approx(np.std([10, -10, 20, -20, 40, -40], ddof=1))

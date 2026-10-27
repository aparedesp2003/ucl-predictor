import itertools
from dataclasses import replace
from datetime import date, timedelta

import numpy as np
import pytest

from engine.db.models import Stage
from engine.evaluate.backtest import (
    UNIFORM,
    EloParams,
    calibration,
    extend_grid,
    grid_search,
    predict_upcoming,
    score,
    walk_forward,
)
from engine.models.elo import MatchRow, sort_key

SEASONS = ["2011-12", "2012-13", "2013-14", "2014-15"]
SCORE_FROM = "2013-14"
PARAMS = EloParams(k=25, home_adv=60, season_regression=0.3)


def _league(seed: int = 0) -> list[MatchRow]:
    """Double round robin of 6 teams per season, plus one qualifier, with strength-driven scores."""
    rng = np.random.default_rng(seed)
    strength = {t: s for t, s in zip(range(1, 7), [1.8, 1.5, 1.3, 1.1, 0.9, 0.7], strict=True)}
    rows, mid = [], 1
    for si, label in enumerate(SEASONS):
        day = date(2011 + si, 9, 1)
        rows.append(
            MatchRow(mid, label, Stage.QUALIFYING, day - timedelta(days=30), None, 7, 6,
                     int(rng.poisson(1.0)), int(rng.poisson(1.2)))
        )  # fmt: skip
        mid += 1
        for i, (h, a) in enumerate(itertools.permutations(strength, 2)):
            rows.append(
                MatchRow(mid, label, Stage.GROUP_STAGE, day + timedelta(days=i // 3), None, h, a,
                         int(rng.poisson(strength[h] * 1.1)), int(rng.poisson(strength[a])))
            )  # fmt: skip
            mid += 1
    return rows


def _by_id(preds):
    return {p.match.id: p for p in preds}


def test_burn_in_unscored_and_scored_seasons_have_probs():
    preds, _ = walk_forward(_league(), PARAMS, score_from=SCORE_FROM)
    assert len(preds) == len(_league())
    for p in preds:
        if p.match.season < SCORE_FROM:
            assert p.elo is None
        else:
            assert p.elo is not None and sum(p.elo) == pytest.approx(1.0)
            assert p.uniform == UNIFORM
            assert sum(p.historical) == pytest.approx(1.0)


@pytest.mark.parametrize("pos", [0, 1, 17, 30, -1])
def test_no_leakage_flipping_result_keeps_own_and_earlier_predictions(pos):
    matches = sorted(_league(), key=sort_key)
    scored = [i for i, m in enumerate(matches) if m.season >= SCORE_FROM]
    i = scored[pos]
    target = matches[i]
    flipped = list(matches)
    flipped[i] = replace(target, home_goals=target.away_goals + 3, away_goals=target.home_goals)

    base = _by_id(walk_forward(matches, PARAMS, score_from=SCORE_FROM)[0])
    alt = _by_id(walk_forward(flipped, PARAMS, score_from=SCORE_FROM)[0])
    for m in matches[: i + 1]:
        b, a = base[m.id], alt[m.id]
        assert (b.diff, b.elo, b.historical) == (a.diff, a.elo, a.historical), m.id
    if pos != -1:
        later = matches[i + 1 :]
        assert any(base[m.id].diff != alt[m.id].diff for m in later)


def test_score_separates_main_and_qualifiers():
    preds, _ = walk_forward(_league(), PARAMS, score_from=SCORE_FROM)
    main = score(preds, (SCORE_FROM, SEASONS[-1]))
    quals = score(preds, (SCORE_FROM, SEASONS[-1]), main=False)
    assert main["overall"]["elo"]["n"] == 2 * 30
    assert quals["overall"]["elo"]["n"] == 2
    assert set(main) == {"2013-14", "2014-15", "overall"}
    assert set(main["overall"]) == {"elo", "historical", "uniform"}
    assert main["overall"]["uniform"]["log_loss"] == pytest.approx(np.log(3))


def test_predict_upcoming_uses_final_ratings_and_prior_season_fit():
    matches = _league()
    last = max(matches, key=sort_key)
    upcoming = [
        MatchRow(10_001, "2015-16", Stage.GROUP_STAGE, date(2016, 9, 1), None, 1, 6, None, None),
        MatchRow(10_002, "2015-16", Stage.GROUP_STAGE, date(2016, 9, 1), None, 6, 1, None, None),
    ]
    out = predict_upcoming(matches + upcoming, PARAMS)
    assert out.train_through == last.match_date
    assert [m.id for m, _, _ in out.predictions] == [10_001, 10_002]
    (_, _, p1), (_, _, p2) = out.predictions
    assert sum(p1) == pytest.approx(1.0)
    assert p1[0] > p2[0]  # strongest team at home vs away
    assert out.ratings[1] > out.ratings[6]


# --- grid edge extension -----------------------------------------------------------------------


def _stub(k_opt: float, adv_opt: float):
    def objective(p: EloParams) -> tuple[float, float]:
        return (p.k - k_opt) ** 2 + (p.home_adv - adv_opt) ** 2, 0.0

    return objective


def test_grid_extends_outward_until_interior():
    grid = {"k": [10, 20, 30], "home_adv": [0, 25, 50], "use_goal_diff": [True]}
    result = grid_search(_stub(57, -40), grid)
    assert result.best.k == 60
    assert result.grid["k"] == [10, 20, 30, 40, 50, 60, 70]
    # home_adv optimum is below the hard bound 0: never extended below it.
    assert result.best.home_adv == 0
    assert result.grid["home_adv"] == [0, 25, 50]
    assert result.rounds == 5


def test_extend_grid_respects_bounds_and_booleans():
    best = EloParams(k=10, home_adv=50, season_regression=1.0, use_goal_diff=False)
    grid = {
        "k": [10, 20],
        "home_adv": [25, 50],
        "season_regression": [0.5, 1.0],
        "use_goal_diff": [False, True],
    }
    assert extend_grid(grid, best) == {
        "k": [10, 20],  # 0 would be the next step, but k must be > 0
        "home_adv": [25, 50, 75],
        "season_regression": [0.5, 1.0],
        "use_goal_diff": [False, True],
    }
    assert extend_grid({"k": [10, 20]}, EloParams(k=15)) is None


def test_grid_search_stops_at_max_rounds():
    result = grid_search(_stub(1000, 0), {"k": [10, 20]}, max_rounds=3)
    assert result.rounds == 3
    assert result.best.k == 40


def test_calibration_counts_scored_main_matches():
    preds, _ = walk_forward(_league(), PARAMS, score_from=SCORE_FROM)
    table = calibration(preds, (SCORE_FROM, SEASONS[-1]))
    assert len(table) == 10
    assert sum(b["n"] for b in table) == 60

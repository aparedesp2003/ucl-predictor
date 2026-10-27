from datetime import UTC, date, datetime

import pytest

from engine.db.models import Stage
from engine.models.elo import (
    AWAY,
    DRAW,
    HOME,
    EloParams,
    EloState,
    MatchRow,
    expected_home,
    goal_diff_multiplier,
    regress_to_mean,
    sort_key,
    update,
)


def _m(id_, season, d, home, away, hg=None, ag=None, kickoff=None, neutral=False):
    return MatchRow(id_, season, Stage.GROUP_STAGE, d, kickoff, home, away, hg, ag, neutral)


def test_equal_ratings_neutral_is_half():
    assert expected_home(1500, 1500, 100, neutral=True) == 0.5
    assert expected_home(1500, 1500, 100, neutral=False) > 0.5
    assert expected_home(1600, 1500, 0, neutral=False) == pytest.approx(1 / (1 + 10 ** (-0.25)))


@pytest.mark.parametrize("use_gd", [True, False])
@pytest.mark.parametrize("score", [(0, 0), (1, 0), (0, 3), (5, 1), (2, 2)])
@pytest.mark.parametrize("neutral", [True, False])
def test_updates_are_zero_sum(use_gd, score, neutral):
    params = EloParams(k=30, home_adv=80, use_goal_diff=use_gd)
    h, a = update(1620.0, 1480.0, *score, neutral, params)
    assert h + a == pytest.approx(1620.0 + 1480.0)


def test_update_direction_and_size():
    params = EloParams(k=20, home_adv=0, use_goal_diff=False)
    h, a = update(1500, 1500, 1, 0, True, params)
    assert h == pytest.approx(1510) and a == pytest.approx(1490)
    h, _ = update(1500, 1500, 1, 1, True, params)
    assert h == pytest.approx(1500)


@pytest.mark.parametrize(
    ("gd", "expected"),
    [(0, 1.0), (1, 1.0), (-1, 1.0), (2, 1.5), (-2, 1.5), (3, 1.75), (5, 2.0), (-7, 2.25)],
)
def test_goal_diff_multiplier(gd, expected):
    assert goal_diff_multiplier(gd, True) == expected
    assert goal_diff_multiplier(gd, False) == 1.0


def test_goal_diff_scales_update():
    with_gd = EloParams(k=20, home_adv=0, use_goal_diff=True)
    h, _ = update(1500, 1500, 4, 0, True, with_gd)
    assert h - 1500 == pytest.approx(20 * (15 / 8) * 0.5)


def test_regress_to_mean():
    out = regress_to_mean({1: 1600.0, 2: 1400.0, 3: 1500.0}, 0.25)
    assert out == {1: pytest.approx(1575.0), 2: pytest.approx(1425.0), 3: pytest.approx(1500.0)}
    assert regress_to_mean({1: 1600.0, 2: 1400.0}, 0.0) == {1: 1600.0, 2: 1400.0}
    assert regress_to_mean({1: 1600.0, 2: 1400.0}, 1.0) == {1: 1500.0, 2: 1500.0}


def test_state_regresses_once_per_new_season():
    params = EloParams(k=20, home_adv=0, season_regression=0.5, use_goal_diff=False)
    state = EloState(params)
    state.apply(_m(1, "2020-21", date(2020, 10, 1), 1, 2, 1, 0))
    assert state.ratings == {1: 1510, 2: 1490}
    state.pre_match(_m(2, "2021-22", date(2021, 10, 1), 1, 3))
    # Regression covers already-rated teams; team 3 is seeded afterwards at new_team_rating.
    assert state.ratings == {1: 1505, 2: 1495, 3: 1500}
    state.pre_match(_m(3, "2021-22", date(2021, 10, 2), 1, 2))
    assert state.ratings[1] == 1505


def test_new_team_rating_and_home_adv_in_diff():
    state = EloState(EloParams(new_team_rating=1400, home_adv=60))
    assert state.pre_match(_m(1, "2020-21", date(2020, 10, 1), 1, 2)) == 60
    assert state.pre_match(_m(2, "2020-21", date(2020, 10, 1), 1, 2, neutral=True)) == 0
    assert state.ratings == {1: 1400, 2: 1400}


def test_sort_key_orders_by_date_kickoff_id():
    late = datetime(2020, 10, 1, 19, tzinfo=UTC)
    early = datetime(2020, 10, 1, 16, tzinfo=UTC)
    rows = [
        _m(5, "s", date(2020, 10, 2), 1, 2),
        _m(4, "s", date(2020, 10, 1), 1, 2, kickoff=late),
        _m(3, "s", date(2020, 10, 1), 1, 2, kickoff=early),
        _m(9, "s", date(2020, 10, 1), 1, 2, kickoff=early),
        _m(7, "s", date(2020, 10, 1), 1, 2),
    ]
    assert [m.id for m in sorted(rows, key=sort_key)] == [7, 3, 9, 4, 5]


def test_result_classes():
    d = date(2020, 1, 1)
    assert _m(1, "s", d, 1, 2, 2, 1).result == HOME
    assert _m(1, "s", d, 1, 2, 1, 1).result == DRAW
    assert _m(1, "s", d, 1, 2, 0, 3).result == AWAY

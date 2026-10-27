import hashlib
import time

import numpy as np
import pytest

from engine.models.poisson import PoissonParams
from engine.simulate.engine import Fixture, rank, simulate, two_legs
from engine.simulate.rules import BRACKET_SIDE, N_TEAMS, PAIRS

P = PoissonParams(a=0.2, h=0.25, b=0.9, rho=-0.08)


def _schedule() -> list[tuple[int, int]]:
    """Circulant league phase: team i hosts i+1..i+4 (mod 36) -> 8 matches each, 144 in total."""
    return [(i, (i + k) % N_TEAMS) for i in range(N_TEAMS) for k in range(1, 5)]


def _all_remaining() -> list[Fixture]:
    return [Fixture(h, a) for h, a in _schedule()]


def _ratings(seed=0) -> np.ndarray:
    return 1500 + np.random.default_rng(seed).normal(0, 100, N_TEAMS)


def test_schedule_shape():
    games = np.bincount(np.array(_schedule()).ravel(), minlength=N_TEAMS)
    assert len(_schedule()) == 144 and set(games) == {8}


def test_bracket_covers_positions_1_to_24_once():
    used = sorted(p for tie in BRACKET_SIDE for pair in tie for p in pair)
    assert used == list(range(1, 25))
    assert sorted(p for pair in PAIRS for p in pair) == list(range(1, 25))


def test_invariants_exact_by_construction():
    res = simulate(_all_remaining(), _ratings(), P, n_sims=2000, seed=1)
    assert res.prob("win").sum() == pytest.approx(1.0, abs=1e-12)
    assert res.prob("final").sum() == pytest.approx(2.0, abs=1e-12)
    assert res.prob("sf").sum() == pytest.approx(4.0, abs=1e-12)
    assert res.prob("qf").sum() == pytest.approx(8.0, abs=1e-12)
    assert res.prob("r16").sum() == pytest.approx(16.0, abs=1e-12)
    assert res.p_top8.sum() == pytest.approx(8.0, abs=1e-12)
    assert res.p_playoff.sum() == pytest.approx(16.0, abs=1e-12)
    assert res.p_out.sum() == pytest.approx(12.0, abs=1e-12)
    np.testing.assert_allclose(res.position_hist.sum(axis=0), 1.0)  # each position filled once
    np.testing.assert_allclose(res.position_hist.sum(axis=1), 1.0)  # each team placed once
    # Each match hands out 2 or 3 points.
    assert 144 * 2 <= res.expected_points.sum() <= 144 * 3
    # Rounds are nested.
    assert np.all(res.prob("r16") >= res.prob("qf"))
    assert np.all(res.prob("qf") >= res.prob("sf"))
    assert np.all(res.prob("final") >= res.prob("win"))
    assert np.all(res.prob("r16") >= res.p_top8 - 1e-12)


def test_deterministic_for_fixed_seed():
    a = simulate(_all_remaining(), _ratings(), P, n_sims=500, seed=7)
    b = simulate(_all_remaining(), _ratings(), P, n_sims=500, seed=7)
    c = simulate(_all_remaining(), _ratings(), P, n_sims=500, seed=8)
    np.testing.assert_array_equal(a.position_counts, b.position_counts)
    assert all(np.array_equal(a.reached[k], b.reached[k]) for k in a.reached)
    assert not np.array_equal(a.position_counts, c.position_counts)


def test_stronger_team_does_better():
    r = np.full(N_TEAMS, 1500.0)
    r[0] = 1900.0
    res = simulate(_all_remaining(), r, P, n_sims=2000, seed=3)
    assert res.prob("win")[0] == res.prob("win").max()
    assert res.p_top8[0] > 0.9


def test_clinched_and_eliminated_teams():
    """All results known except two matches: team 0 cannot leave the top 8, team 35 is out."""
    fixtures = []
    for h, a in _schedule():
        if (h, a) in {(0, 1), (34, 35)}:
            fixtures.append(Fixture(h, a))
        else:  # the lower index always wins 1-0
            fixtures.append(Fixture(h, a, 1, 0) if h < a else Fixture(h, a, 0, 1))
    res = simulate(fixtures, _ratings(), P, n_sims=1000, seed=0)
    assert res.p_top8[0] == 1.0
    assert res.p_out[35] == 1.0
    assert res.prob("r16")[35] == 0.0 and res.prob("win")[35] == 0.0


def test_rank_applies_tiebreakers_in_order():
    rng = np.random.default_rng(0)
    played = np.zeros((4, 4), dtype=np.int64)
    pts = np.array([[9, 9, 9, 9]])
    gd = np.array([[2, 2, 1, 2]])
    gf = np.array([[5, 5, 9, 5]])
    away_gf = np.array([[1, 3, 0, 1]])
    wins = np.array([[3, 3, 3, 3]])
    away_wins = np.array([[0, 0, 0, 1]])
    order = rank(pts, gd, gf, away_gf, wins, away_wins, played, rng)
    # gd: team 2 last; away goals: team 1 first; then team 3 (away wins) before team 0.
    assert order.tolist() == [[1, 3, 0, 2]]


def test_two_legs_strong_team_usually_wins():
    rng = np.random.default_rng(0)
    r = np.array([1500.0, 1800.0])
    n = 4000
    winners = two_legs(np.zeros(n, dtype=int), np.ones(n, dtype=int), r, P, rng)
    share = (winners == 1).mean()
    assert 0.75 < share < 1.0


def test_runtime_for_10k_sims():
    start = time.perf_counter()
    simulate(_all_remaining(), _ratings(), P, n_sims=10_000, seed=42)
    assert time.perf_counter() - start < 60


def _fingerprint(res) -> tuple[str, str]:
    reached = b"".join(
        res.reached[k].astype("int64").tobytes() for k in ("r16", "qf", "sf", "final", "win")
    )
    return (
        hashlib.sha256(res.position_counts.astype("int64").tobytes()).hexdigest()[:16],
        hashlib.sha256(reached).hexdigest()[:16],
    )


# Output of the frozen-ratings simulator before rating uncertainty was added (n=500, seed=7).
FROZEN_FINGERPRINT = ("de59818f49956b12", "605358fbe0d2b11b")


def test_sigma_zero_reproduces_frozen_output_exactly():
    res = simulate(_all_remaining(), _ratings(), P, n_sims=500, seed=7, sigma=0.0)
    assert _fingerprint(res) == FROZEN_FINGERPRINT
    assert _fingerprint(simulate(_all_remaining(), _ratings(), P, n_sims=500, seed=7)) == (
        FROZEN_FINGERPRINT
    )


def test_sigma_keeps_invariants_exact_and_is_deterministic():
    a = simulate(_all_remaining(), _ratings(), P, n_sims=1000, seed=5, sigma=40.0)
    b = simulate(_all_remaining(), _ratings(), P, n_sims=1000, seed=5, sigma=40.0)
    assert _fingerprint(a) == _fingerprint(b)
    assert _fingerprint(a) != _fingerprint(
        simulate(_all_remaining(), _ratings(), P, n_sims=1000, seed=5)
    )
    for key, total in (("win", 1), ("final", 2), ("sf", 4), ("qf", 8), ("r16", 16)):
        assert a.prob(key).sum() == pytest.approx(total, abs=1e-12)
    assert a.p_top8.sum() == pytest.approx(8, abs=1e-12)
    assert a.p_out.sum() == pytest.approx(12, abs=1e-12)


def test_sigma_spreads_outcomes_for_a_dominant_team():
    r = np.full(N_TEAMS, 1500.0)
    r[0] = 1800.0
    frozen = simulate(_all_remaining(), r, P, n_sims=4000, seed=11)
    noisy = simulate(_all_remaining(), r, P, n_sims=4000, seed=11, sigma=150.0)
    assert noisy.prob("win")[0] < frozen.prob("win")[0]


def test_negative_sigma_rejected():
    with pytest.raises(ValueError):
        simulate(_all_remaining(), _ratings(), P, n_sims=10, sigma=-1.0)

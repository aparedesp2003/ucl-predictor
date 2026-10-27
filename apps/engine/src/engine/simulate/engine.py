"""Monte-Carlo simulation of the league phase and knockout phase (numpy, vectorised over sims).

Scorelines come from the Elo-driven Poisson + Dixon-Coles model (``models.poisson``) with ratings
frozen for the whole run. See ``simulate.rules`` for the competition rules and approximations.
"""

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from engine.models.poisson import PoissonParams, lambdas, scoreline_matrix
from engine.simulate.rules import (
    BRACKET_SIDE,
    EXTRA_TIME_FRACTION,
    N_PLAYOFF,
    N_TEAMS,
    N_TOP,
    PAIRS,
    QUARTER_FINALS,
)

_G = 11  # scoreline_matrix default size (0..10 goals)


@dataclass(frozen=True)
class Fixture:
    """League-phase match by team index (0..35). Goals are None when still to be played."""

    home: int
    away: int
    home_goals: int | None = None
    away_goals: int | None = None


@dataclass
class SimResult:
    n_sims: int
    position_counts: np.ndarray  # (36, 36): team x final position (0-based)
    points_sum: np.ndarray  # (36,)
    reached: dict[str, np.ndarray]  # round -> (36,) count of sims a team reached it

    def prob(self, key: str) -> np.ndarray:
        return self.reached[key] / self.n_sims

    @property
    def p_top8(self) -> np.ndarray:
        return self.position_counts[:, :N_TOP].sum(axis=1) / self.n_sims

    @property
    def p_playoff(self) -> np.ndarray:
        return self.position_counts[:, N_TOP:N_PLAYOFF].sum(axis=1) / self.n_sims

    @property
    def p_out(self) -> np.ndarray:
        return self.position_counts[:, N_PLAYOFF:].sum(axis=1) / self.n_sims

    @property
    def expected_points(self) -> np.ndarray:
        return self.points_sum / self.n_sims

    @property
    def position_hist(self) -> np.ndarray:
        return self.position_counts / self.n_sims


def _sample_matrix(cum: np.ndarray, u: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Inverse-CDF draw from flattened cumulative score matrices (..., 121)."""
    idx = np.minimum((cum < u[..., None]).sum(axis=-1), _G * _G - 1)
    return idx // _G, idx % _G


def _play(
    home: np.ndarray, away: np.ndarray, ratings: np.ndarray, p: PoissonParams,
    rng: np.random.Generator, neutral: bool = False,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:  # fmt: skip
    """90-minute goals for vectors of matches; also returns the rates for extra time."""
    lam_h, lam_a = lambdas(ratings[home] - ratings[away], neutral, p)
    cum = scoreline_matrix(lam_h, lam_a, p.rho).reshape(len(home), -1).cumsum(axis=1)
    hg, ag = _sample_matrix(cum, rng.random(len(home)))
    return hg, ag, lam_h, lam_a


def _decide(
    a: np.ndarray, b: np.ndarray, goals_a: np.ndarray, goals_b: np.ndarray,
    et_lam_a: np.ndarray, et_lam_b: np.ndarray, rng: np.random.Generator,
) -> np.ndarray:  # fmt: skip
    """Winner after regulation goals, then extra time, then a 50/50 shoot-out."""
    et_a = rng.poisson(et_lam_a * EXTRA_TIME_FRACTION)
    et_b = rng.poisson(et_lam_b * EXTRA_TIME_FRACTION)
    pens_a = rng.random(len(a)) < 0.5
    level = goals_a == goals_b
    a_wins = np.where(level, np.where(et_a == et_b, pens_a, et_a > et_b), goals_a > goals_b)
    return np.where(a_wins, a, b)


def two_legs(
    first_host: np.ndarray, second_host: np.ndarray, ratings: np.ndarray, p: PoissonParams,
    rng: np.random.Generator,
) -> np.ndarray:  # fmt: skip
    """Winner of a two-legged tie; extra time is played at the second-leg host."""
    h1, a1, _, _ = _play(first_host, second_host, ratings, p, rng)
    h2, a2, lam2_h, lam2_a = _play(second_host, first_host, ratings, p, rng)
    return _decide(second_host, first_host, a1 + h2, h1 + a2, lam2_h, lam2_a, rng)


def one_match_neutral(
    a: np.ndarray, b: np.ndarray, ratings: np.ndarray, p: PoissonParams, rng: np.random.Generator
) -> np.ndarray:
    ga, gb, lam_a, lam_b = _play(a, b, ratings, p, rng, neutral=True)
    return _decide(a, b, ga, gb, lam_a, lam_b, rng)


def league_table(
    fixtures: Sequence[Fixture], ratings: np.ndarray, p: PoissonParams, n_sims: int,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray]:  # fmt: skip
    """(order, points): order[s, k] = team at position k + 1 in sim s; points (n_sims, 36)."""
    shape = (n_sims, N_TEAMS)
    pts, gf, ga, away_gf, wins, away_wins = (np.zeros(shape, dtype=np.int64) for _ in range(6))
    played = np.zeros((N_TEAMS, N_TEAMS), dtype=np.int64)
    for f in fixtures:
        played[f.home, f.away] += 1
        played[f.away, f.home] += 1
        if f.home_goals is not None and f.away_goals is not None:
            hg = np.full(n_sims, f.home_goals)
            ag = np.full(n_sims, f.away_goals)
        else:
            lam_h, lam_a = lambdas(ratings[f.home] - ratings[f.away], False, p)
            cum = scoreline_matrix(lam_h, lam_a, p.rho).reshape(-1).cumsum()
            hg, ag = _sample_matrix(cum, rng.random(n_sims))
        gf[:, f.home] += hg
        ga[:, f.home] += ag
        gf[:, f.away] += ag
        ga[:, f.away] += hg
        away_gf[:, f.away] += ag
        pts[:, f.home] += np.where(hg > ag, 3, np.where(hg == ag, 1, 0))
        pts[:, f.away] += np.where(ag > hg, 3, np.where(hg == ag, 1, 0))
        wins[:, f.home] += hg > ag
        wins[:, f.away] += ag > hg
        away_wins[:, f.away] += ag > hg
    gd = gf - ga
    order = rank(pts, gd, gf, away_gf, wins, away_wins, played, rng)
    return order, pts


def rank(
    pts, gd, gf, away_gf, wins, away_wins, played: np.ndarray, rng: np.random.Generator
) -> np.ndarray:
    """Art. 18.01 order (best first) per sim; criteria 9-10 replaced by a random draw."""
    opp_pts, opp_gd, opp_gf = pts @ played, gd @ played, gf @ played
    random = rng.random(pts.shape)
    # np.lexsort sorts by the last key first; negate to sort descending.
    keys = (random, -opp_gf, -opp_gd, -opp_pts, -away_wins, -wins, -away_gf, -gf, -gd, -pts)
    return np.lexsort(keys, axis=-1)


def simulate(
    fixtures: Sequence[Fixture], ratings: Sequence[float], p: PoissonParams,
    n_sims: int = 10_000, seed: int = 42,
) -> SimResult:  # fmt: skip
    """Simulate the rest of the season ``n_sims`` times."""
    rng = np.random.default_rng(seed)
    r = np.asarray(ratings, dtype=float)
    if r.shape != (N_TEAMS,):
        raise ValueError(f"expected {N_TEAMS} ratings, got {r.shape}")
    order, pts = league_table(fixtures, r, p, n_sims, rng)

    positions = np.empty_like(order)
    np.put_along_axis(positions, order, np.arange(N_TEAMS)[None, :], axis=1)
    position_counts = np.zeros((N_TEAMS, N_TEAMS), dtype=np.int64)
    np.add.at(position_counts, (np.broadcast_to(np.arange(N_TEAMS), order.shape), positions), 1)

    # Silver/blue draw within every pair of positions (1/2, ..., 23/24).
    flip = rng.random((n_sims, len(PAIRS))) < 0.5
    side_team = {}
    for k, (hi, lo) in enumerate(PAIRS):
        a, b = order[:, hi - 1], order[:, lo - 1]
        side_team[(hi, lo), 0] = np.where(flip[:, k], a, b)
        side_team[(hi, lo), 1] = np.where(flip[:, k], b, a)

    reached = {k: np.zeros(N_TEAMS, dtype=np.int64) for k in ("r16", "qf", "sf", "final", "win")}

    def count(key: str, teams: np.ndarray) -> None:
        reached[key] += np.bincount(teams.ravel(), minlength=N_TEAMS)

    finalists = []
    for side in (0, 1):
        r16_winners = []
        for seeded, unseeded, top in BRACKET_SIDE:
            kopo = two_legs(side_team[unseeded, side], side_team[seeded, side], r, p, rng)
            host = side_team[top, side]
            count("r16", np.stack([kopo, host]))
            r16_winners.append(two_legs(kopo, host, r, p, rng))
        count("qf", np.stack(r16_winners))
        qf_winners = [
            two_legs(r16_winners[i], r16_winners[j], r, p, rng) for i, j in QUARTER_FINALS
        ]
        count("sf", np.stack(qf_winners))
        finalists.append(two_legs(qf_winners[0], qf_winners[1], r, p, rng))
    count("final", np.stack(finalists))
    count("win", one_match_neutral(finalists[0], finalists[1], r, p, rng))

    return SimResult(n_sims, position_counts, pts.sum(axis=0).astype(float), reached)

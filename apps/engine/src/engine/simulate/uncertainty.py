"""How far a team's Elo moves between matchday 3 and the end of its season.

The simulator starts from ratings after three league-phase matches, so the historical spread of
"final Elo of the season - Elo after the 3rd group/league-phase match" is a direct estimate of how
uncertain those ratings are for the rest of the season. Both ratings are taken within the season:
the regression applied at the next season's start is excluded.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

import numpy as np

from engine.db.models import Stage
from engine.models.elo import EloParams, EloState, MatchRow, sort_key

PHASE_STAGES = frozenset({Stage.GROUP_STAGE, Stage.LEAGUE_PHASE})
SEASONS = ("2015-16", "2025-26")


def rating_drift(
    matches: Iterable[MatchRow], params: EloParams, seasons: tuple[str, str] = SEASONS,
    after: int = 3,
) -> dict[str, list[float]]:  # fmt: skip
    """Per season: final rating minus rating after the team's ``after``-th group/league match."""
    state = EloState(params)
    phase_games: dict[tuple[str, int], int] = {}
    checkpoint: dict[tuple[str, int], float] = {}
    final: dict[tuple[str, int], float] = {}
    for m in sorted((m for m in matches if m.finished), key=sort_key):
        state.apply(m)
        for team in (m.home_id, m.away_id):
            key = (m.season, team)
            final[key] = state.ratings[team]  # within the season: before next season's regression
            if m.stage in PHASE_STAGES:
                phase_games[key] = phase_games.get(key, 0) + 1
                if phase_games[key] == after:
                    checkpoint[key] = state.ratings[team]
    out: dict[str, list[float]] = {}
    for (season, team), r in sorted(checkpoint.items()):
        if seasons[0] <= season <= seasons[1]:
            out.setdefault(season, []).append(final[season, team] - r)
    return out


@dataclass(frozen=True)
class SigmaEstimate:
    sigma: float  # std of all differences pooled
    n: int
    per_season: dict[str, tuple[float, int]]  # season -> (std, n)


def estimate_sigma(drift: dict[str, list[float]]) -> SigmaEstimate:
    pooled = np.concatenate([np.asarray(v) for v in drift.values()])
    return SigmaEstimate(
        sigma=float(np.std(pooled, ddof=1)),
        n=len(pooled),
        per_season={s: (float(np.std(v, ddof=1)), len(v)) for s, v in sorted(drift.items())},
    )


MIN_SAME_FORMAT_SEASONS = 2


@dataclass(frozen=True)
class SigmaChoice:
    sigma: float
    basis: str
    seasons: list[str]  # seasons whose drift the sigma is computed from
    pooled: SigmaEstimate  # all seasons before the target, for reference


def default_sigma(
    drift: dict[str, list[float]], formats: Mapping[str, str], target_season: str,
    min_seasons: int = MIN_SAME_FORMAT_SEASONS,
) -> SigmaChoice:  # fmt: skip
    """Sigma from earlier seasons with the target season's format (group stage vs league phase:
    different number of matches left after matchday 3), or from all earlier seasons when fewer
    than ``min_seasons`` share the format."""
    prior = {s: v for s, v in drift.items() if s < target_season}
    pooled = estimate_sigma(prior)
    fmt = formats[target_season]
    same = {s: v for s, v in prior.items() if formats.get(s) == fmt}
    if len(same) >= min_seasons:
        return SigmaChoice(estimate_sigma(same).sigma, f"{fmt} seasons", sorted(same), pooled)
    basis = f"pooled (only {len(same)} earlier {fmt} season(s))"
    return SigmaChoice(pooled.sigma, basis, sorted(prior), pooled)

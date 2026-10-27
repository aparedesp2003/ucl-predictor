"""Walk-forward backtest of the Elo model against uniform and historical-rate baselines.

Every prediction uses only strictly earlier information: the Elo difference comes from ratings
before the match, and the outcome model (and the historical baseline) are fitted on seasons before
the match's season (expanding window). Pure: takes ``MatchRow``s, never touches the database.
"""

import itertools
import logging
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field, replace
from datetime import date

import numpy as np

from engine.db.models import Stage
from engine.evaluate.metrics import calibration_table, summary
from engine.models.elo import EloParams, EloState, MatchRow, sort_key
from engine.models.outcome import OutcomeModel

logger = logging.getLogger(__name__)

BURN_IN = ("2011-12", "2014-15")
VALIDATION = ("2015-16", "2020-21")
TEST = ("2021-22", "2025-26")
QUALIFIER_STAGES = frozenset({Stage.QUALIFYING, Stage.PLAYOFF_ROUND})
MODELS = ("elo", "historical", "uniform")

UNIFORM = (1 / 3, 1 / 3, 1 / 3)

Probs = tuple[float, float, float]


def in_range(season: str, span: tuple[str, str]) -> bool:
    return span[0] <= season <= span[1]


def is_main(m: MatchRow) -> bool:
    return m.stage not in QUALIFIER_STAGES


@dataclass(frozen=True)
class Pred:
    """Pre-match view of one finished match. Probabilities are None during burn-in."""

    match: MatchRow
    diff: float
    elo: Probs | None = None
    historical: Probs | None = None
    uniform: Probs | None = None


@dataclass
class _Season:
    label: str
    matches: list[MatchRow] = field(default_factory=list)
    diffs: list[float] = field(default_factory=list)


def _historical_rates(history: Sequence[tuple[MatchRow, float]]) -> Probs:
    counts = np.bincount([m.result for m, _ in history if is_main(m)], minlength=3)
    rates = counts / counts.sum()
    return (float(rates[0]), float(rates[1]), float(rates[2]))


def fit_outcome(history: Sequence[tuple[MatchRow, float]]) -> OutcomeModel:
    return OutcomeModel().fit([d for _, d in history], [m.result for m, _ in history])


def walk_forward(
    matches: Iterable[MatchRow], params: EloParams, score_from: str = VALIDATION[0]
) -> tuple[list[Pred], EloState]:
    """Pre-match predictions for every finished match, plus the final Elo state.

    Seasons before ``score_from`` only build ratings (burn-in) and get no probabilities.
    """
    state = EloState(params)
    history: list[tuple[MatchRow, float]] = []  # (match, pre-match diff) of completed seasons
    preds: list[Pred] = []
    season: _Season | None = None

    def close(s: _Season) -> None:
        if s.label >= score_from:
            # Fitted on earlier seasons only; batched per season because the fit is fixed within it.
            proba = fit_outcome(history).predict_proba(s.diffs)
            hist = _historical_rates(history)
            for m, d, p in zip(s.matches, s.diffs, proba, strict=True):
                preds.append(Pred(m, d, (float(p[0]), float(p[1]), float(p[2])), hist, UNIFORM))
        else:
            preds.extend(Pred(m, d) for m, d in zip(s.matches, s.diffs, strict=True))
        history.extend(zip(s.matches, s.diffs, strict=True))

    for m in sorted((m for m in matches if m.finished), key=sort_key):
        if season is None or m.season != season.label:
            if season is not None:
                close(season)
            season = _Season(m.season)
        season.matches.append(m)
        season.diffs.append(state.pre_match(m))
        state.apply(m)
    if season is not None:
        close(season)
    return preds, state


@dataclass(frozen=True)
class Upcoming:
    """Fitted state for live predictions: final ratings and per-match probabilities."""

    ratings: dict[int, float]
    train_through: date | None
    predictions: list[tuple[MatchRow, float, Probs]]


def predict_upcoming(matches: Sequence[MatchRow], params: EloParams) -> Upcoming:
    """Fits on all finished matches and predicts every unfinished one.

    The outcome model for each unfinished match's season is fitted on finished matches of earlier
    seasons, as in the backtest.
    """
    preds, state = walk_forward(matches, params, score_from="9999")
    finished = [p.match for p in preds]
    train_through = max((m.match_date for m in finished), default=None)
    ratings = dict(state.ratings)
    history = [(p.match, p.diff) for p in preds]
    models: dict[str, OutcomeModel] = {}
    out = []
    for m in sorted((m for m in matches if not m.finished), key=sort_key):
        if m.season not in models:
            models[m.season] = fit_outcome([(h, d) for h, d in history if h.season < m.season])
        diff = state.pre_match(m)
        p = models[m.season].predict_proba([diff])[0]
        out.append((m, diff, (float(p[0]), float(p[1]), float(p[2]))))
    return Upcoming(ratings, train_through, out)


def _arrays(preds: Sequence[Pred], model: str) -> tuple[np.ndarray, np.ndarray]:
    return (
        np.array([getattr(p, model) for p in preds], dtype=float),
        np.array([p.match.result for p in preds], dtype=int),
    )


def score(
    preds: Iterable[Pred], span: tuple[str, str], main: bool = True
) -> dict[str, dict[str, dict[str, float]]]:
    """{season | "overall": {model: summary}} for scored matches in ``span``.

    ``main=True`` keeps main-competition matches; ``main=False`` keeps qualifiers only.
    """
    rows = _scored(preds, span, main)
    groups = {s: [p for p in rows if p.match.season == s] for s in sorted(_seasons(rows))}
    if rows:
        groups["overall"] = rows
    return {
        key: {model: summary(*_arrays(group, model)) for model in MODELS}
        for key, group in groups.items()
    }


def _scored(preds: Iterable[Pred], span: tuple[str, str], main: bool) -> list[Pred]:
    return [
        p
        for p in preds
        if p.elo is not None and in_range(p.match.season, span) and is_main(p.match) == main
    ]


def _seasons(preds: Iterable[Pred]) -> set[str]:
    return {p.match.season for p in preds}


def calibration(preds: Iterable[Pred], span: tuple[str, str], bins: int = 10) -> list[dict]:
    """Elo P(home) calibration on main-competition matches in ``span``."""
    probs, outcomes = _arrays(_scored(preds, span, True), "elo")
    return [vars(b) for b in calibration_table(probs[:, 0], outcomes == 0, bins)]


# --- grid search -------------------------------------------------------------------------------

Grid = dict[str, list]

DEFAULT_GRID: Grid = {
    "k": [10, 15, 20, 25, 30, 40],
    "home_adv": [0, 25, 50, 75, 100],
    "season_regression": [0, 0.1, 0.2, 0.33, 0.5],
    "use_goal_diff": [False, True],
    "new_team_rating": [1400, 1450, 1500],
}

# (lower, upper, lower_inclusive) for numeric dimensions; extension never crosses these.
HARD_BOUNDS: dict[str, tuple[float | None, float | None, bool]] = {
    "k": (0, None, False),
    "home_adv": (0, None, True),
    "season_regression": (0, 1, True),
    "new_team_rating": (0, None, False),
}

Objective = Callable[[EloParams], tuple[float, float]]


def validation_objective(matches: Sequence[MatchRow]) -> Objective:
    """Pooled (log loss, RPS) of Elo on validation main-competition matches."""
    subset = [m for m in matches if m.season <= VALIDATION[1]]

    def objective(params: EloParams) -> tuple[float, float]:
        preds, _ = walk_forward(subset, params, score_from=VALIDATION[0])
        s = score(preds, VALIDATION)["overall"]["elo"]
        return s["log_loss"], s["rps"]

    return objective


def _within(dim: str, value: float) -> bool:
    lo, hi, lo_incl = HARD_BOUNDS.get(dim, (None, None, True))
    if lo is not None and (value < lo or (value == lo and not lo_incl)):
        return False
    return hi is None or value <= hi


def extend_grid(grid: Grid, best: EloParams) -> Grid | None:
    """One step outward on every numeric dimension whose best value sits on a grid edge.

    Returns None when nothing can be extended.
    """
    new = {k: list(v) for k, v in grid.items()}
    changed = False
    for dim, values in grid.items():
        if any(isinstance(v, bool) for v in values) or len(values) < 2:
            continue
        vals = sorted(values)
        chosen = getattr(best, dim)
        candidates = []
        if chosen == vals[0]:
            candidates.append(vals[0] - (vals[1] - vals[0]))
        if chosen == vals[-1]:
            candidates.append(vals[-1] + (vals[-1] - vals[-2]))
        for c in candidates:
            c = round(c, 6)
            if _within(dim, c) and c not in vals:
                new[dim] = sorted([*new[dim], c])
                changed = True
    return new if changed else None


@dataclass
class GridResult:
    best: EloParams
    best_score: tuple[float, float]
    grid: Grid
    rounds: int
    evaluated: dict[EloParams, tuple[float, float]]


def _combos(grid: Grid) -> list[EloParams]:
    dims = list(grid)
    return [
        replace(EloParams(), **dict(zip(dims, values, strict=True)))
        for values in itertools.product(*(grid[d] for d in dims))
    ]


def grid_search(
    objective: Objective, grid: Grid = DEFAULT_GRID, max_rounds: int = 10
) -> GridResult:
    """Minimise (log loss, RPS); extend edge dimensions outward and repeat until interior."""
    evaluated: dict[EloParams, tuple[float, float]] = {}
    grid = {k: list(v) for k, v in grid.items()}
    for rnd in range(1, max_rounds + 1):
        todo = [p for p in _combos(grid) if p not in evaluated]
        logger.info("grid round %d: %d new combinations", rnd, len(todo))
        for params in todo:
            evaluated[params] = objective(params)
        in_grid = {p: evaluated[p] for p in _combos(grid)}
        best = min(in_grid, key=in_grid.__getitem__)
        extended = extend_grid(grid, best)
        if extended is None or rnd == max_rounds:
            if extended is not None:
                logger.warning("grid search hit max_rounds=%d with best on an edge", max_rounds)
            return GridResult(best, in_grid[best], grid, rnd, evaluated)
        logger.info("best %s on a grid edge; extending", best)
        grid = extended
    raise ValueError("max_rounds must be >= 1")

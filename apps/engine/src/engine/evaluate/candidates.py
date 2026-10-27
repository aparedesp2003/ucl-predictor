"""Candidate models on one walk-forward protocol, calibration, and choice of the primary model.

Candidates, all built from the same pre-match Elo ratings (``backtest.walk_forward``):

- ``elo``: multinomial outcome model on the Elo difference.
- ``poisson``: Elo-driven Poisson + Dixon-Coles (``models.poisson``), refitted each season on
  earlier seasons, like the outcome model.
- ``poisson_cal``: ``poisson`` with temperature scaling (scalar T).
- ``poisson_shrink``: ``poisson`` with the rating slope ``b`` scaled by a scalar ``s`` (calibration
  at the goals level, so it also carries into simulated scorelines).
- ``blend``: mean of ``elo`` and ``poisson_cal``.

T and s are fitted on validation seasons only. Test predictions use the fit on all validation
seasons; validation predictions use a leave-one-season-out fit (the season being scored is left
out), so choosing the primary by validation log loss is not in-sample.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

import numpy as np

from engine.evaluate.backtest import TEST, VALIDATION, Pred, Upcoming, in_range, is_main
from engine.evaluate.calibrate import fit_scalar, fit_temperature, temperature_scale
from engine.evaluate.metrics import calibration_table, log_loss, summary
from engine.models import poisson
from engine.models.elo import EloParams, MatchRow
from engine.models.poisson import PoissonParams

CANDIDATES = ("elo", "poisson", "poisson_cal", "poisson_shrink", "blend")
SHRINK_BOUNDS = (0.3, 2.0)


def raw_diff(p: Pred, params: EloParams) -> float:
    """Elo difference without the Elo home advantage (the Poisson model fits its own)."""
    return p.diff - (0.0 if p.match.neutral else params.home_adv)


def fit_poisson(history: Sequence[Pred], params: EloParams) -> PoissonParams:
    return poisson.fit(
        [raw_diff(p, params) for p in history],
        [p.match.neutral for p in history],
        [p.match.home_goals for p in history],
        [p.match.away_goals for p in history],
    )


def season_fits(preds: Sequence[Pred], params: EloParams) -> dict[str, PoissonParams]:
    """Poisson fit for every scored season, on all finished matches of earlier seasons."""
    seasons = sorted({p.match.season for p in preds if p.elo is not None})
    return {s: fit_poisson([p for p in preds if p.match.season < s], params) for s in seasons}


@dataclass
class Frame:
    """Scored matches as arrays (validation + test seasons, main and qualifiers)."""

    rows: list[Pred]
    seasons: np.ndarray
    main: np.ndarray
    outcomes: np.ndarray
    elo: np.ndarray
    diff_raw: np.ndarray
    neutral: np.ndarray
    fits: list[PoissonParams]

    def poisson_probs(self, s: float = 1.0) -> np.ndarray:
        out = np.empty((len(self.rows), 3))
        for fit in set(self.fits):
            idx = np.array([f == fit for f in self.fits])
            out[idx] = poisson.predict_proba(self.diff_raw[idx], self.neutral[idx], fit.shrunk(s))
        return out

    def take(self, idx: np.ndarray) -> "Frame":
        keep = np.flatnonzero(idx)
        return Frame(
            [self.rows[i] for i in keep],
            self.seasons[keep],
            self.main[keep],
            self.outcomes[keep],
            self.elo[keep],
            self.diff_raw[keep],
            self.neutral[keep],
            [self.fits[i] for i in keep],
        )

    def mask(self, span: tuple[str, str], main: bool | None = True) -> np.ndarray:
        m = (self.seasons >= span[0]) & (self.seasons <= span[1])
        return m if main is None else m & (self.main == main)


def _evaluated(season: str) -> bool:
    return in_range(season, VALIDATION) or in_range(season, TEST)


def build_frame(preds: Sequence[Pred], params: EloParams) -> Frame:
    fits = season_fits(preds, params)
    rows = [p for p in preds if p.elo is not None and _evaluated(p.match.season)]
    return Frame(
        rows=rows,
        seasons=np.array([p.match.season for p in rows]),
        main=np.array([is_main(p.match) for p in rows]),
        outcomes=np.array([p.match.result for p in rows]),
        elo=np.array([p.elo for p in rows], dtype=float),
        diff_raw=np.array([raw_diff(p, params) for p in rows]),
        neutral=np.array([p.match.neutral for p in rows]),
        fits=[fits[p.match.season] for p in rows],
    )


@dataclass
class Calibration:
    temperature: float  # fitted on all validation seasons; applied to test
    shrink: float
    loso_temperature: dict[str, float]  # validation season -> T fitted without it
    loso_shrink: dict[str, float]


def _cross_fit(
    frame: Frame, fitter: Callable[[np.ndarray], float]
) -> tuple[float, dict[str, float]]:
    """Fit on all validation main matches, and once per validation season leaving it out."""
    val = frame.mask(VALIDATION)
    full = fitter(val)
    loso = {s: fitter(val & (frame.seasons != s)) for s in sorted(set(frame.seasons[val]))}
    return full, loso


def fit_calibration(frame: Frame) -> Calibration:
    raw = frame.poisson_probs()
    y = frame.outcomes

    def temperature(idx: np.ndarray) -> float:
        return fit_temperature(raw[idx], y[idx])

    def shrink(idx: np.ndarray) -> float:
        sub = frame.take(idx)
        return fit_scalar(lambda s: log_loss(sub.poisson_probs(s), sub.outcomes), SHRINK_BOUNDS)

    t, t_loso = _cross_fit(frame, temperature)
    s, s_loso = _cross_fit(frame, shrink)
    return Calibration(t, s, t_loso, s_loso)


def candidate_probs(frame: Frame, cal: Calibration) -> dict[str, np.ndarray]:
    """(n, 3) probabilities per candidate; validation rows use the leave-one-season-out fits."""
    raw = frame.poisson_probs()
    temps = np.array([cal.loso_temperature.get(s, cal.temperature) for s in frame.seasons])
    shrinks = {s: cal.loso_shrink.get(s, cal.shrink) for s in set(frame.seasons)}
    shrunk = np.empty_like(raw)
    for s in set(shrinks.values()):
        idx = np.array([shrinks[season] == s for season in frame.seasons])
        shrunk[idx] = frame.poisson_probs(s)[idx]
    cal_probs = np.stack([temperature_scale(p, t) for p, t in zip(raw, temps, strict=True)])
    return {
        "elo": frame.elo,
        "poisson": raw,
        "poisson_cal": cal_probs,
        "poisson_shrink": shrunk,
        "blend": (frame.elo + cal_probs) / 2,
    }


Scores = dict[str, dict[str, dict[str, float]]]


def score_candidates(
    frame: Frame, probs: dict[str, np.ndarray], span: tuple[str, str], main: bool = True
) -> Scores:
    """{season | "overall": {candidate: summary}}."""
    sel = frame.mask(span, main)
    keys = [*sorted(set(frame.seasons[sel])), "overall"] if sel.any() else []
    out: Scores = {}
    for key in keys:
        idx = sel if key == "overall" else sel & (frame.seasons == key)
        out[key] = {c: summary(probs[c][idx], frame.outcomes[idx]) for c in probs}
    return out


def calibration_tables(
    frame: Frame, probs: dict[str, np.ndarray], span: tuple[str, str], bins: int = 10
) -> dict[str, dict[str, list[dict]]]:
    """{"home" | "away": {candidate: bins}} on main-competition matches in ``span``."""
    sel = frame.mask(span)
    y = frame.outcomes[sel]
    return {
        side: {
            c: [vars(b) for b in calibration_table(p[sel][:, col], y == col, bins)]
            for c, p in probs.items()
        }
        for side, col in (("home", 0), ("away", 2))
    }


def choose_primary(validation: Scores, test: Scores) -> tuple[str, str, bool]:
    """(chosen by validation, primary after the gate, gate passed).

    Chosen = lowest validation log loss (tie-break RPS). Gate: it must not be worse than ``elo`` on
    test log loss; otherwise ``elo`` stays primary.
    """
    val = validation["overall"]
    chosen = min(CANDIDATES, key=lambda c: (val[c]["log_loss"], val[c]["rps"]))
    ok = test["overall"][chosen]["log_loss"] <= test["overall"]["elo"]["log_loss"]
    return chosen, chosen if ok else "elo", ok


@dataclass
class ScheduledProbs:
    matches: list[MatchRow]
    probs: dict[str, np.ndarray]  # candidate -> (n, 3)
    fits: dict[str, PoissonParams]  # season -> Poisson fit (before shrinking) used for it


def predict_scheduled(
    up: Upcoming, params: EloParams, temperature: float, shrink: float
) -> ScheduledProbs:
    """Every candidate's probabilities for the unfinished matches in ``up``.

    The Poisson model for a season is fitted on finished matches of earlier seasons, as in the
    backtest; T and s come from the latest Poisson backtest.
    """
    matches = [m for m, _, _ in up.predictions]
    fits = {
        s: fit_poisson([p for p in up.history if p.match.season < s], params)
        for s in sorted({m.season for m in matches})
    }
    diff_raw = np.array([d - (0.0 if m.neutral else params.home_adv) for m, d, _ in up.predictions])
    neutral = np.array([m.neutral for m in matches], dtype=bool)
    raw, shrunk = np.empty((len(matches), 3)), np.empty((len(matches), 3))
    for season, fit in fits.items():
        idx = np.array([m.season == season for m in matches])
        raw[idx] = poisson.predict_proba(diff_raw[idx], neutral[idx], fit)
        shrunk[idx] = poisson.predict_proba(diff_raw[idx], neutral[idx], fit.shrunk(shrink))
    elo = np.array([p for _, _, p in up.predictions], dtype=float).reshape(-1, 3)
    cal = temperature_scale(raw, temperature)
    probs = {
        "elo": elo,
        "poisson": raw,
        "poisson_cal": cal,
        "poisson_shrink": shrunk,
        "blend": (elo + cal) / 2,
    }
    return ScheduledProbs(matches, probs, fits)


@dataclass
class ProbDiff:
    mean_abs: float  # over all matches and the three outcomes
    max_abs: float
    flagged: list[tuple[int, np.ndarray, np.ndarray]]  # (match id, a, b) with any |a - b| > tol


def compare_probs(
    a: Mapping[int, Sequence[float]], b: Mapping[int, Sequence[float]], tol: float = 0.05
) -> ProbDiff:
    """Absolute H/D/A differences between two models on the matches both predicted."""
    ids = sorted(set(a) & set(b))
    if not ids:
        return ProbDiff(float("nan"), float("nan"), [])
    pa = np.array([a[i] for i in ids], dtype=float)
    pb = np.array([b[i] for i in ids], dtype=float)
    diff = np.abs(pa - pb)
    flagged = [(i, pa[k], pb[k]) for k, i in enumerate(ids) if diff[k].max() > tol]
    return ProbDiff(float(diff.mean()), float(diff.max()), flagged)

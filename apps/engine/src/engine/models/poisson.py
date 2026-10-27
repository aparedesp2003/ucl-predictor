"""Elo-driven Poisson goals model with a Dixon-Coles low-score correction. Pure; no database access.

    log(lambda_home) = a + h * (not neutral) + b * d / 400
    log(lambda_away) = a             - b * d / 400

where ``d`` is the home-minus-away Elo rating difference *without* the Elo home advantage (the
Poisson model learns its own, ``h``). The joint score probability is
``tau(x, y) * Pois(x; lambda_home) * Pois(y; lambda_away)`` with the Dixon-Coles factor ``tau``
adjusting 0-0, 1-0, 0-1 and 1-1. Fitted by maximum likelihood on 90-minute goals.
"""

from dataclasses import asdict, dataclass, replace
from typing import Any

import numpy as np
from scipy.optimize import minimize
from scipy.special import gammaln

MAX_GOALS = 10
RHO_BOUNDS = (-0.2, 0.2)  # keeps tau > 0 for every realistic pair of rates
_TAU_FLOOR = 1e-10


@dataclass(frozen=True)
class PoissonParams:
    a: float
    h: float
    b: float
    rho: float

    def shrunk(self, s: float) -> "PoissonParams":
        """Same model with the rating slope scaled by ``s`` (goals-level calibration)."""
        return replace(self, b=self.b * s)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "PoissonParams":
        return cls(**{k: d[k] for k in cls.__dataclass_fields__})


def lambdas(diff_raw, neutral, p: PoissonParams) -> tuple[np.ndarray, np.ndarray]:
    """Expected 90-minute goals (home, away); broadcasts over array inputs."""
    x = p.b * np.asarray(diff_raw, dtype=float) / 400
    home = 1.0 - np.asarray(neutral, dtype=float)
    return np.exp(p.a + p.h * home + x), np.exp(p.a - x)


def dc_tau(x, y, lam_h, lam_a, rho: float) -> np.ndarray:
    """Dixon-Coles correction factor for scores (x, y); 1 outside the four low scores."""
    x, y = np.asarray(x), np.asarray(y)
    lam_h, lam_a = np.asarray(lam_h, dtype=float), np.asarray(lam_a, dtype=float)
    tau = np.ones(np.broadcast(x, y, lam_h, lam_a).shape)
    tau = np.where((x == 0) & (y == 0), 1 - lam_h * lam_a * rho, tau)
    tau = np.where((x == 0) & (y == 1), 1 + lam_h * rho, tau)
    tau = np.where((x == 1) & (y == 0), 1 + lam_a * rho, tau)
    return np.where((x == 1) & (y == 1), 1 - rho, tau)


def _neg_log_lik(theta, diff_raw, neutral, hg, ag) -> float:
    p = PoissonParams(*theta)
    lam_h, lam_a = lambdas(diff_raw, neutral, p)
    ll = (
        hg * np.log(lam_h) - lam_h - gammaln(hg + 1)
        + ag * np.log(lam_a) - lam_a - gammaln(ag + 1)
        + np.log(np.maximum(dc_tau(hg, ag, lam_h, lam_a, p.rho), _TAU_FLOOR))
    )  # fmt: skip
    return float(-ll.sum())


def fit(diff_raw, neutral, home_goals, away_goals) -> PoissonParams:
    """Maximum-likelihood (a, h, b, rho) on 90-minute scores."""
    args = tuple(np.asarray(v, dtype=float) for v in (diff_raw, neutral, home_goals, away_goals))
    if len(args[0]) == 0:
        raise ValueError("no matches to fit on")
    start = np.array([np.log(max(args[3].mean(), 0.1)), 0.2, 0.5, 0.0])
    res = minimize(
        _neg_log_lik,
        start,
        args=args,
        method="L-BFGS-B",
        bounds=[(None, None), (None, None), (None, None), RHO_BOUNDS],
    )
    if not res.success:
        raise RuntimeError(f"Poisson fit did not converge: {res.message}")
    return PoissonParams(*(float(v) for v in res.x))


def scoreline_matrix(lam_h, lam_a, rho: float, max_goals: int = MAX_GOALS) -> np.ndarray:
    """P(home = i, away = j) for i, j in 0..max_goals, normalised to sum to 1.

    Scalar rates give a (G+1, G+1) matrix; arrays of rates give (..., G+1, G+1).
    """
    lam_h = np.asarray(lam_h, dtype=float)[..., None, None]
    lam_a = np.asarray(lam_a, dtype=float)[..., None, None]
    g = np.arange(max_goals + 1)
    x, y = g[:, None], g[None, :]
    log_p = x * np.log(lam_h) - lam_h - gammaln(x + 1) + y * np.log(lam_a) - lam_a - gammaln(y + 1)
    m = np.exp(log_p) * np.maximum(dc_tau(x, y, lam_h, lam_a, rho), 0.0)
    return m / m.sum(axis=(-2, -1), keepdims=True)


def outcome_probs(matrix: np.ndarray) -> np.ndarray:
    """(..., 3) P(home win), P(draw), P(away win) from score matrices."""
    home = np.tril(matrix, -1).sum(axis=(-2, -1))
    draw = np.trace(matrix, axis1=-2, axis2=-1)
    away = np.triu(matrix, 1).sum(axis=(-2, -1))
    return np.stack([home, draw, away], axis=-1)


def predict_proba(diff_raw, neutral, p: PoissonParams) -> np.ndarray:
    """(n, 3) H/D/A probabilities for arrays of raw rating differences."""
    lam_h, lam_a = lambdas(diff_raw, neutral, p)
    return outcome_probs(scoreline_matrix(lam_h, lam_a, p.rho))

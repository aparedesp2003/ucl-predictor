"""Scores for 3-way (home / draw / away) probability forecasts.

``probs`` is an (n, 3) array in HOME, DRAW, AWAY order; ``outcomes`` holds class indices 0/1/2.
"""

from dataclasses import dataclass

import numpy as np

EPS = 1e-15


def _check(probs, outcomes) -> tuple[np.ndarray, np.ndarray]:
    p = np.asarray(probs, dtype=float)
    y = np.asarray(outcomes, dtype=int)
    if p.ndim != 2 or p.shape[1] != 3 or len(p) != len(y) or len(y) == 0:
        raise ValueError(f"expected (n, 3) probs and n outcomes, got {p.shape} and {y.shape}")
    return p, y


def _one_hot(y: np.ndarray) -> np.ndarray:
    return np.eye(3)[y]


def log_loss(probs, outcomes) -> float:
    p, y = _check(probs, outcomes)
    return float(-np.mean(np.log(np.clip(p[np.arange(len(y)), y], EPS, 1.0))))


def brier(probs, outcomes) -> float:
    """Multi-class Brier score: mean over matches of sum_k (p_k - y_k)^2, in [0, 2]."""
    p, y = _check(probs, outcomes)
    return float(np.mean(np.sum((p - _one_hot(y)) ** 2, axis=1)))


def rps(probs, outcomes) -> float:
    """Ranked probability score with the ordering home < draw < away, in [0, 1]."""
    p, y = _check(probs, outcomes)
    cum = np.cumsum(p, axis=1)[:, :-1] - np.cumsum(_one_hot(y), axis=1)[:, :-1]
    return float(np.mean(np.sum(cum**2, axis=1)) / 2)


def accuracy(probs, outcomes) -> float:
    p, y = _check(probs, outcomes)
    return float(np.mean(np.argmax(p, axis=1) == y))


def summary(probs, outcomes) -> dict[str, float]:
    return {
        "n": len(outcomes),
        "log_loss": log_loss(probs, outcomes),
        "rps": rps(probs, outcomes),
        "brier": brier(probs, outcomes),
        "accuracy": accuracy(probs, outcomes),
    }


@dataclass(frozen=True)
class CalibrationBin:
    lo: float
    hi: float
    n: int
    mean_pred: float | None
    observed: float | None


def calibration_table(p_home, home_won, bins: int = 10) -> list[CalibrationBin]:
    """Equal-width bins of predicted P(home win) vs the observed home-win rate."""
    p = np.asarray(p_home, dtype=float)
    y = np.asarray(home_won, dtype=float)
    idx = np.minimum((p * bins).astype(int), bins - 1)
    out = []
    for b in range(bins):
        mask = idx == b
        n = int(mask.sum())
        out.append(
            CalibrationBin(
                b / bins,
                (b + 1) / bins,
                n,
                float(p[mask].mean()) if n else None,
                float(y[mask].mean()) if n else None,
            )
        )
    return out

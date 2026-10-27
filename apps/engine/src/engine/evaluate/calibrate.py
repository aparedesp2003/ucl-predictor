"""Post-hoc calibration of 3-way probabilities."""

from collections.abc import Callable

import numpy as np
from scipy.optimize import minimize_scalar

from engine.evaluate.metrics import log_loss


def temperature_scale(probs, t: float) -> np.ndarray:
    """p_i ∝ p_i^(1/T): T > 1 flattens, T < 1 sharpens."""
    q = np.asarray(probs, dtype=float) ** (1.0 / t)
    return q / q.sum(axis=-1, keepdims=True)


def fit_scalar(loss: Callable[[float], float], bounds: tuple[float, float]) -> float:
    res = minimize_scalar(loss, bounds=bounds, method="bounded", options={"xatol": 1e-4})
    if not res.success:
        raise RuntimeError(f"scalar fit did not converge: {res.message}")
    return float(res.x)


def fit_temperature(probs, outcomes, bounds: tuple[float, float] = (0.25, 4.0)) -> float:
    """T minimising 3-way log loss."""
    p = np.asarray(probs, dtype=float)
    return fit_scalar(lambda t: log_loss(temperature_scale(p, t), outcomes), bounds)

import numpy as np
import pytest

from engine.models.outcome import OutcomeModel


def _synthetic(n=3000, seed=0):
    rng = np.random.default_rng(seed)
    diffs = rng.normal(50, 150, n)
    p_home = 1 / (1 + 10 ** (-diffs / 400))
    u = rng.random(n)
    draw_band = 0.25
    outcomes = np.where(u < p_home - draw_band / 2, 0, np.where(u < p_home + draw_band / 2, 1, 2))
    return diffs, outcomes


def test_probabilities_sum_to_one_and_home_increases():
    model = OutcomeModel().fit(*_synthetic())
    grid = np.linspace(-600, 600, 49)
    proba = model.predict_proba(grid)
    assert proba.shape == (49, 3)
    np.testing.assert_allclose(proba.sum(axis=1), 1.0, atol=1e-12)
    assert np.all(np.diff(proba[:, 0]) > 0)
    assert np.all(np.diff(proba[:, 2]) < 0)


def test_requires_all_classes():
    with pytest.raises(ValueError):
        OutcomeModel().fit([0, 10, 20], [0, 2, 0])

import math

import numpy as np
import pytest
from sklearn.metrics import log_loss as sk_log_loss

from engine.evaluate.metrics import accuracy, brier, calibration_table, log_loss, rps, summary

PROBS = [[0.5, 0.3, 0.2], [0.2, 0.3, 0.5], [0.6, 0.2, 0.2]]
OUTCOMES = [0, 1, 2]


def test_log_loss_hand_and_sklearn():
    expected = -(math.log(0.5) + math.log(0.3) + math.log(0.2)) / 3
    assert log_loss(PROBS, OUTCOMES) == pytest.approx(expected)
    sk = sk_log_loss(OUTCOMES, PROBS, labels=[0, 1, 2])
    assert log_loss(PROBS, OUTCOMES) == pytest.approx(sk)


def test_log_loss_matches_sklearn_on_random():
    rng = np.random.default_rng(1)
    p = rng.dirichlet([2, 1, 2], size=200)
    y = rng.integers(0, 3, size=200)
    assert log_loss(p, y) == pytest.approx(sk_log_loss(y, p, labels=[0, 1, 2]))


def test_brier_hand():
    # (0.25+0.09+0.04) + (0.04+0.49+0.25) + (0.36+0.04+0.64)
    assert brier(PROBS, OUTCOMES) == pytest.approx((0.38 + 0.78 + 1.04) / 3)


def test_rps_hand():
    # cum diffs: m1 (-0.5, -0.2) -> 0.29; m2 (0.2, -0.5) -> 0.29; m3 (0.6, 0.8) -> 1.0
    assert rps(PROBS, OUTCOMES) == pytest.approx((0.29 + 0.29 + 1.0) / 3 / 2)


def test_rps_perfect_and_worst():
    assert rps([[1, 0, 0]], [0]) == 0
    assert rps([[1, 0, 0]], [2]) == 1
    assert rps([[1 / 3] * 3], [1]) == pytest.approx((1 / 9 + 1 / 9) / 2)


def test_accuracy():
    assert accuracy(PROBS, OUTCOMES) == pytest.approx(1 / 3)


def test_summary_and_shape_check():
    assert summary(PROBS, OUTCOMES)["n"] == 3
    with pytest.raises(ValueError):
        log_loss([[0.5, 0.5]], [0])


def test_calibration_table():
    table = calibration_table([0.05, 0.08, 0.55, 1.0], [0, 1, 1, 1])
    assert len(table) == 10
    assert (table[0].n, table[0].observed) == (2, 0.5)
    assert table[0].mean_pred == pytest.approx(0.065)
    assert table[5].n == 1 and table[9].n == 1
    assert table[3].n == 0 and table[3].observed is None

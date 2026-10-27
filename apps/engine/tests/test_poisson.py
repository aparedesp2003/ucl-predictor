import numpy as np
import pytest
from scipy.stats import poisson

from engine.models.poisson import (
    PoissonParams,
    dc_tau,
    fit,
    lambdas,
    outcome_probs,
    predict_proba,
    scoreline_matrix,
)

TRUE = PoissonParams(a=0.25, h=0.3, b=0.8, rho=-0.08)


def _sample(p: PoissonParams, n=20_000, seed=0):
    rng = np.random.default_rng(seed)
    diffs = rng.normal(0, 150, n)
    neutral = rng.random(n) < 0.05
    lam_h, lam_a = lambdas(diffs, neutral, p)
    flat = scoreline_matrix(lam_h, lam_a, p.rho).reshape(n, -1)
    idx = (flat.cumsum(axis=1) < rng.random((n, 1))).sum(axis=1)
    return diffs, neutral, idx // 11, idx % 11


def test_lambdas_formula_and_neutral():
    lh, la = lambdas(400.0, False, TRUE)
    assert lh == pytest.approx(np.exp(0.25 + 0.3 + 0.8))
    assert la == pytest.approx(np.exp(0.25 - 0.8))
    lh_n, la_n = lambdas(0.0, True, TRUE)
    assert lh_n == pytest.approx(la_n)


def test_dc_tau_values():
    lh, la, rho = 1.5, 1.2, -0.1
    assert dc_tau(0, 0, lh, la, rho) == pytest.approx(1 - lh * la * rho)
    assert dc_tau(0, 1, lh, la, rho) == pytest.approx(1 + lh * rho)
    assert dc_tau(1, 0, lh, la, rho) == pytest.approx(1 + la * rho)
    assert dc_tau(1, 1, lh, la, rho) == pytest.approx(1 - rho)
    assert dc_tau(2, 1, lh, la, rho) == 1
    assert dc_tau(0, 0, lh, la, 0.0) == 1


def test_scoreline_matrix_normalised_and_independent_when_rho_zero():
    m = scoreline_matrix(1.4, 0.9, 0.0)
    assert m.shape == (11, 11)
    assert m.sum() == pytest.approx(1.0)
    expected = np.outer(poisson.pmf(np.arange(11), 1.4), poisson.pmf(np.arange(11), 0.9))
    np.testing.assert_allclose(m, expected / expected.sum())
    batch = scoreline_matrix(np.array([1.0, 2.0]), np.array([1.0, 0.5]), -0.1)
    assert batch.shape == (2, 11, 11)
    np.testing.assert_allclose(batch.sum(axis=(1, 2)), 1.0)


def test_negative_rho_inflates_draws():
    base = outcome_probs(scoreline_matrix(1.2, 1.2, 0.0))
    dc = outcome_probs(scoreline_matrix(1.2, 1.2, -0.1))
    assert dc[1] > base[1]
    assert dc.sum() == pytest.approx(1.0)


def test_outcome_probs_monotone_in_rating_difference():
    p = predict_proba(np.linspace(-600, 600, 25), np.zeros(25, dtype=bool), TRUE)
    np.testing.assert_allclose(p.sum(axis=1), 1.0)
    assert np.all(np.diff(p[:, 0]) > 0) and np.all(np.diff(p[:, 2]) < 0)


def test_fit_recovers_parameters():
    est = fit(*_sample(TRUE))
    assert est.a == pytest.approx(TRUE.a, abs=0.03)
    assert est.h == pytest.approx(TRUE.h, abs=0.04)
    assert est.b == pytest.approx(TRUE.b, abs=0.06)
    assert est.rho == pytest.approx(TRUE.rho, abs=0.04)


def test_shrunk_and_roundtrip():
    assert TRUE.shrunk(0.5).b == pytest.approx(0.4)
    assert PoissonParams.from_dict(TRUE.to_dict()) == TRUE

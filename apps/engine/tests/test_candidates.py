import numpy as np
import pytest

from engine.evaluate.calibrate import fit_temperature, temperature_scale
from engine.evaluate.candidates import (
    CANDIDATES,
    Calibration,
    Frame,
    candidate_probs,
    choose_primary,
    fit_calibration,
)
from engine.models import poisson
from engine.models.poisson import PoissonParams

FIT = PoissonParams(a=0.2, h=0.25, b=1.0, rho=-0.08)
SEASONS = ["2015-16", "2016-17", "2017-18", "2021-22"]  # three validation seasons + one test


def _frame(n_per_season=400, seed=0, slope=0.8) -> Frame:
    """Outcomes drawn from the model with the slope scaled by ``slope`` (overconfident if < 1)."""
    rng = np.random.default_rng(seed)
    n = n_per_season * len(SEASONS)
    diff = rng.normal(0, 200, n)
    neutral = np.zeros(n, dtype=bool)
    true = poisson.predict_proba(diff, neutral, FIT.shrunk(slope))
    outcomes = (true.cumsum(axis=1) < rng.random((n, 1))).sum(axis=1)
    model = poisson.predict_proba(diff, neutral, FIT)
    return Frame(
        rows=[None] * n,
        seasons=np.repeat(SEASONS, n_per_season),
        main=np.ones(n, dtype=bool),
        outcomes=outcomes,
        elo=model,
        diff_raw=diff,
        neutral=neutral,
        fits=[FIT] * n,
    )


def test_temperature_scale_basics():
    p = np.array([[0.6, 0.25, 0.15], [0.2, 0.3, 0.5]])
    np.testing.assert_allclose(temperature_scale(p, 1.0), p)
    flat = temperature_scale(p, 2.0)
    np.testing.assert_allclose(flat.sum(axis=1), 1.0)
    assert flat[0, 0] < p[0, 0] and flat[0, 2] > p[0, 2]
    assert temperature_scale(p, 0.5)[0, 0] > p[0, 0]


def test_fit_temperature_recovers_known_temperature():
    rng = np.random.default_rng(3)
    true = rng.dirichlet([3, 2, 3], size=20_000)
    y = (true.cumsum(axis=1) < rng.random((20_000, 1))).sum(axis=1)
    overconfident = temperature_scale(true, 0.7)
    assert fit_temperature(overconfident, y) == pytest.approx(1 / 0.7, rel=0.05)


def test_shrink_and_temperature_detect_overconfidence():
    cal = fit_calibration(_frame())
    assert cal.shrink == pytest.approx(0.8, abs=0.1)
    assert cal.temperature > 1.0
    assert set(cal.loso_shrink) == set(SEASONS[:3])  # validation seasons only


def test_leave_one_season_out_fit_ignores_the_held_out_season():
    frame = _frame()
    base = fit_calibration(frame)
    held = frame.seasons == "2015-16"
    frame.outcomes = np.where(held, 0, frame.outcomes)  # rewrite 2015-16 results
    changed = fit_calibration(frame)
    assert changed.loso_temperature["2015-16"] == base.loso_temperature["2015-16"]
    assert changed.loso_shrink["2015-16"] == base.loso_shrink["2015-16"]
    assert changed.temperature != base.temperature
    assert changed.loso_temperature["2016-17"] != base.loso_temperature["2016-17"]


def test_candidate_probs_use_loso_on_validation_and_full_fit_on_test():
    frame = _frame(n_per_season=5)
    cal = Calibration(2.0, 0.5, {"2015-16": 0.5}, {"2015-16": 1.5})
    probs = candidate_probs(frame, cal)
    assert set(probs) == set(CANDIDATES)
    raw = probs["poisson"]
    val, test = frame.seasons == "2015-16", frame.seasons == "2021-22"
    np.testing.assert_allclose(probs["poisson_cal"][val], temperature_scale(raw[val], 0.5))
    np.testing.assert_allclose(probs["poisson_cal"][test], temperature_scale(raw[test], 2.0))
    np.testing.assert_allclose(probs["poisson_shrink"][val], frame.poisson_probs(1.5)[val])
    np.testing.assert_allclose(probs["poisson_shrink"][test], frame.poisson_probs(0.5)[test])
    np.testing.assert_allclose(probs["blend"], (probs["elo"] + probs["poisson_cal"]) / 2)
    for p in probs.values():
        np.testing.assert_allclose(p.sum(axis=1), 1.0)


def _scores(ll: dict[str, float]):
    return {"overall": {c: {"log_loss": v, "rps": 0.2} for c, v in ll.items()}}


def test_choose_primary_and_gate():
    val = _scores({"elo": 0.95, "poisson": 0.96, "poisson_cal": 0.94, "poisson_shrink": 0.97,
                   "blend": 0.955})  # fmt: skip
    good = _scores({c: 0.95 for c in CANDIDATES} | {"poisson_cal": 0.94})
    assert choose_primary(val, good) == ("poisson_cal", "poisson_cal", True)
    bad = _scores({c: 0.95 for c in CANDIDATES} | {"poisson_cal": 0.96})
    assert choose_primary(val, bad) == ("poisson_cal", "elo", False)

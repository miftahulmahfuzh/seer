"""M0547's Hurst estimate and sort, pinned on made-up series."""

import numpy as np

from seer_engine.lab.methods.m0547_hurst_persistence_ranked import hurst_rs, neutralise, pick


def test_trending_series_reads_higher_than_noise_and_reverting():
    rng = np.random.default_rng(0)
    n = 252
    noise = rng.normal(size=(40, n))
    trend = np.empty_like(noise)
    revert = np.empty_like(noise)
    trend[:, 0] = revert[:, 0] = noise[:, 0]
    for t in range(1, n):
        trend[:, t] = 0.5 * trend[:, t - 1] + noise[:, t]
        revert[:, t] = -0.5 * revert[:, t - 1] + noise[:, t]
    h = {k: hurst_rs(v).mean() for k, v in (("noise", noise), ("trend", trend), ("revert", revert))}
    assert h["revert"] < h["noise"] < h["trend"]


def test_gappy_or_flat_rows_are_nan():
    x = np.random.default_rng(1).normal(size=(3, 252))
    x[1, :100] = np.nan
    x[2] = 0.0
    out = hurst_rs(x)
    assert np.isfinite(out[0]) and np.isnan(out[1]) and np.isnan(out[2])


def test_pick_direction_and_tiebreak():
    s = {"A": 0.4, "B": 0.6, "C": 0.6, "D": 0.5}
    assert pick(s, True, 2) == ["B", "C"]
    assert pick(s, False, 2) == ["A", "D"]


def test_neutralised_score_is_uncorrelated_with_its_controls():
    rng = np.random.default_rng(2)
    mom, vol = rng.normal(size=200), rng.normal(size=200)
    h = 0.8 * mom - 0.5 * vol + 0.2 * rng.normal(size=200)
    r = neutralise(h, mom, vol)
    assert abs(np.corrcoef(r, mom)[0, 1]) < 0.15 and abs(np.corrcoef(r, vol)[0, 1]) < 0.15

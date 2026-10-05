"""SUE -- standardized unexpected earnings on a seasonal random walk (Foster-Olsen-Shevlin).

Analyst-consensus surprise is out of scope: Finnhub's free tier returns 4 quarters and is not
backfillable to 2015 (plan Scope). The free substitute, and the definition PEAD is documented
on, is the seasonal random walk::

    surprise_q = EPS_q - EPS_{q-4}
    SUE_q      = surprise_q / stdev(surprise_{q-1} ... surprise_{q-K})

that is: this quarter's year-on-year change in diluted EPS, divided by the dispersion of the
**prior** such changes. The current surprise is excluded from its own scale, so SUE is a
z-score of the latest surprise against recent history, not a studentised residual.

**Minimum history, stated and enforced.** ``K`` is at most ``MAX_SURPRISES`` (8) and at least
``MIN_SURPRISES`` (4) prior surprises. A surprise needs the quarter four back, so 1 current
plus 4 prior surprises needs ``MIN_QUARTERS`` = 4 + 1 + 4 = **9 contiguous quarters** of diluted
EPS ending at the latest one visible. Fewer than 9 -> NaN. Never a partial number.

The series handed in must already be contiguous in fiscal quarters and ascending; building it
(including deriving an untagged Q4 as FY minus Q1+Q2+Q3, and truncating at a gap) is
``panel.SymbolFundamentals.quarters``.

Bit-identity rule, as ``strategies.indicators``: the surprise series is one elementwise
subtraction, and the dispersion is summed with an explicit left-to-right Python loop -- never
``sum``/``mean``/``std``, whose pairwise summation changes the rounding with the array length.
So a symbol's SUE is the same float whether it is computed from a 9-quarter series or a
60-quarter one, which is what makes the backtest and the nightly job agree.

Pure: no database, network, clock or randomness (tests/test_strategy_purity.py).
"""

from __future__ import annotations

import numpy as np

SEASON = 4  # quarters back for the seasonal random walk
MAX_SURPRISES = 8  # the dispersion window, in prior surprises
MIN_SURPRISES = 4  # fewer prior surprises than this and SUE is NaN
MIN_QUARTERS = SEASON + 1 + MIN_SURPRISES  # 9: the shortest EPS series that can yield a SUE


def _series(eps: object) -> np.ndarray:
    if not isinstance(eps, np.ndarray) or eps.dtype != np.float64 or eps.ndim != 1:
        raise ValueError("eps must be a 1-D float64 array, ascending by fiscal quarter")
    return eps


def surprises(eps: np.ndarray) -> np.ndarray:
    """``eps[i] - eps[i-4]`` for every quarter that has one: length ``len(eps) - 4``, or empty.

    One elementwise subtraction, so each element is bit-identical however long ``eps`` is.
    """
    eps = _series(eps)
    if eps.shape[0] <= SEASON:
        return np.zeros(0, dtype=np.float64)
    return eps[SEASON:] - eps[:-SEASON]


def dispersion(prior: np.ndarray) -> float:
    """Population (ddof 0) standard deviation of ``prior``, summed left to right.

    NaN when ``prior`` is empty or holds a non-finite value.
    """
    prior = _series(prior)
    k = prior.shape[0]
    if k == 0:
        return float("nan")
    acc = prior[0]
    for i in range(1, k):
        acc = acc + prior[i]
    mean = acc / k
    dev = prior[0] - mean
    var = dev * dev
    for i in range(1, k):
        dev = prior[i] - mean
        var = var + dev * dev
    return float(np.sqrt(var / k))


def sue(eps: np.ndarray) -> float:
    """SUE of the last quarter of ``eps`` (ascending, contiguous diluted EPS).

    NaN when the series is shorter than ``MIN_QUARTERS``, when it holds a non-finite value, or
    when the dispersion of the prior surprises is zero or non-finite (a filer whose year-on-year
    change has not moved at all carries no information, and dividing by it would be infinite).
    """
    eps = _series(eps)
    if eps.shape[0] < MIN_QUARTERS:
        return float("nan")
    if not bool(np.all(np.isfinite(eps))):
        return float("nan")
    s = surprises(eps)
    n = s.shape[0]
    current = float(s[n - 1])
    first = n - 1 - MAX_SURPRISES
    if first < 0:
        first = 0
    prior = s[first : n - 1]
    if prior.shape[0] < MIN_SURPRISES:
        return float("nan")
    sd = dispersion(prior)
    if not np.isfinite(sd) or sd == 0.0:
        return float("nan")
    return current / sd

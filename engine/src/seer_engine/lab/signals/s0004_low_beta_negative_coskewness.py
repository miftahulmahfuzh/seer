"""S0004 — crash-prone without the extra swing: negative coskewness among busy, low-beta names.

Source: variation of M0186 (the queued idea M0189); Harvey & Siddique (2000), "Conditional
Skewness in Asset Pricing Tests", Journal of Finance 55(3). Idea: M0186 found the premium for
names that fall hardest when the market is most volatile was earned by high-beta names. This asks
whether any of it is left once beta is taken out of the selection: among the ``BUSY`` most-traded
pool names whose weekly beta to SPY is at most ``BETA_MAX``, the more negative the standardised
coskewness, the higher the score. Every other name gets no opinion.

Weekly log returns are ``WEEKS`` five-session steps on SPY's calendar ending on the data date.
The parents read 156 weeks; a signal may read 473 bars, so this reads 90, a noisier estimate of
the same quantity. Coskewness is Harvey and Siddique's: E[e * m^2] / (sqrt(E[e^2]) * E[m^2]) with
e the market-model residual and m the demeaned market return. Pure; bars dated <= data_date only.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from datetime import date
from typing import Any

import numpy as np

from seer_engine.lab.signal import Signal
from seer_engine.strategies.base import History

MARKET = "SPY"
STEP = 5  # sessions per weekly return
WEEKS = 90
BUSY = 150  # the most-traded pool names, by DV_N-bar mean trading value
DV_N = 20
BETA_MAX = 1.0
MIN_FRAC = 0.8


def _on_calendar(h: History, cal: np.ndarray) -> np.ndarray:
    """``h``'s closes on the sessions ``cal``; NaN where it has no bar that day."""
    pos = np.searchsorted(h.dates, cal)
    ok = pos < len(h)
    pos = np.where(ok, pos, 0)
    ok &= h.dates[pos] == cal
    return np.where(ok, h.close[pos], np.nan)


def _dollar_volume(h: History, i: int) -> float:
    """Mean close times volume over the ``DV_N`` bars ending at bar ``i``."""
    return float(np.mean(h.close[i + 1 - DV_N : i + 1] * h.volume[i + 1 - DV_N : i + 1]))


def score(history: Mapping[str, History], market: Any, pool: AbstractSet[str], data_date: date) -> dict[str, float]:
    spy = history.get(MARKET)
    if spy is None:
        return {}
    j = spy.index_of(data_date)
    if j is None or j < STEP * WEEKS:
        return {}
    cal = spy.dates[j - STEP * WEEKS : j + 1 : STEP]
    mr = np.diff(np.log(spy.close[j - STEP * WEEKS : j + 1 : STEP]))
    busy: list[tuple[float, str]] = []
    for symbol in sorted(pool):
        h = history.get(symbol)
        if h is None:
            continue
        i = h.index_of(data_date)
        if i is None or i + 1 < DV_N:
            continue
        dv = _dollar_volume(h, i)
        if np.isfinite(dv):
            busy.append((-dv, symbol))
    out: dict[str, float] = {}
    for _, symbol in sorted(busy)[:BUSY]:
        c = _on_calendar(history[symbol], cal)
        with np.errstate(invalid="ignore", divide="ignore"):
            r = np.diff(np.log(c))
        ok = np.isfinite(r) & np.isfinite(mr)
        if int(ok.sum()) < MIN_FRAC * WEEKS:
            continue
        x, y = mr[ok], r[ok]
        m = x - x.mean()
        var = float(np.mean(m * m))
        if var <= 0.0:
            continue
        beta = float(np.mean(m * (y - y.mean()))) / var
        if beta > BETA_MAX:
            continue
        e = (y - y.mean()) - beta * m
        scale = float(np.sqrt(np.mean(e * e))) * var
        if scale > 0.0:
            out[symbol] = -float(np.mean(e * m * m)) / scale
    return out


SIGNAL = Signal(
    id="S0004",
    name="Names that fall hardest in wild markets, among busy companies no jumpier than the market",
    family="stock-coskewness",
    source_kind="variation",
    source_ref="variation of M0186 (queued as M0189); Harvey & Siddique (2000), Conditional Skewness in Asset Pricing Tests, J. Finance 55(3)",
    hypothesis=(
        "Investors are paid to hold names that do badly exactly when the market is most volatile. "
        "Among the most-traded members with beta at or below one, the more negative a name's "
        "coskewness with SPY, the higher its next-month return, with beta already controlled: a "
        "positive controlled slope on both stores and a positive 2009-2015 spread."
    ),
    expected_failure=(
        "M0186's premium was beta; with beta capped and controlled nothing is left. Ninety weekly "
        "returns estimate a third moment badly, so the ranking is mostly noise, and the names it "
        "likes (2007 banks) are the ones the dead-company store punishes."
    ),
    lookback=STEP * WEEKS + 1,
    score=score,
    idea_id="M0189",
    seen_keys=("concept:coskewness-low-beta-pool", "concept:coskewness-90-week"),
)

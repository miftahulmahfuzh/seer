"""S0014 — price delay: how much of a stock's response to market news arrives in later weeks.

Source: Hou & Moskowitz (2005), "Market Frictions, Price Delay, and the Cross-Section of Expected
Returns", Review of Financial Studies 18(3). Idea: a neglected stock takes weeks to reflect news
the market priced at once, and investors demand a premium to hold it. The paper's first delay
measure compares two regressions of the stock's weekly return: on this week's market return
alone, and on this week's plus the previous four.

    delay = 1 - R^2(this week only) / R^2(this week and four lags)

It is 0 when the lags add nothing and near 1 when the stock answers only late. Weekly log returns
are ``WEEKS`` five-session steps on SPY's calendar ending on the data date; the paper uses a year
of weeks, this reads ninety. Higher delay scores higher. Pure; bars dated <= data_date only.
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
LAGS = 4


def _on_calendar(h: History, cal: np.ndarray) -> np.ndarray:
    """``h``'s closes on the sessions ``cal``; NaN where it has no bar that day."""
    pos = np.searchsorted(h.dates, cal)
    ok = pos < len(h)
    pos = np.where(ok, pos, 0)
    ok &= h.dates[pos] == cal
    return np.where(ok, h.close[pos], np.nan)


def score(history: Mapping[str, History], market: Any, pool: AbstractSet[str], data_date: date) -> dict[str, float]:
    spy = history.get(MARKET)
    if spy is None:
        return {}
    j = spy.index_of(data_date)
    if j is None or j < STEP * WEEKS:
        return {}
    cal = spy.dates[j - STEP * WEEKS : j + 1 : STEP]
    mr = np.diff(np.log(spy.close[j - STEP * WEEKS : j + 1 : STEP]))
    if not np.all(np.isfinite(mr)):
        return {}
    rows = WEEKS - LAGS
    x = np.column_stack([np.ones(rows)] + [mr[LAGS - k : WEEKS - k] for k in range(LAGS + 1)])
    out: dict[str, float] = {}
    for symbol in sorted(pool):
        h = history.get(symbol)
        if h is None:
            continue
        c = _on_calendar(h, cal)
        if not (np.all(np.isfinite(c)) and np.all(c > 0.0)):
            continue
        y = np.diff(np.log(c))[LAGS:]
        total = float(np.sum((y - y.mean()) ** 2))
        if total <= 0.0:
            continue
        r2: list[float] = []
        for cols in (2, LAGS + 2):
            coef, *_ = np.linalg.lstsq(x[:, :cols], y, rcond=None)
            r2.append(1.0 - float(np.sum((y - x[:, :cols] @ coef) ** 2)) / total)
        if r2[1] > 0.0:
            out[symbol] = 1.0 - r2[0] / r2[1]
    return out


SIGNAL = Signal(
    id="S0014",
    name="How late a stock answers market news: the share of its market response that arrives in later weeks",
    family="stock-price-delay",
    source_kind="paper",
    source_ref="Hou & Moskowitz (2005), Market Frictions, Price Delay, and the Cross-Section of Expected Returns, Review of Financial Studies 18(3)",
    hypothesis=(
        "Stocks that are slow to reflect market-wide news are neglected, and holding them is paid: "
        "a higher delay goes with a higher next-month return beyond momentum, beta, size and "
        "volatility, giving a positive controlled slope on both stores and a positive 2009-2015 "
        "spread."
    ),
    expected_failure=(
        "The premium in the paper is earned by small, neglected companies; index members that "
        "pass a trading-value screen have almost no delay, so the measure is estimation noise "
        "from ninety weekly returns and reads as a coin toss."
    ),
    lookback=STEP * WEEKS + 1,
    score=score,
    seen_keys=("concept:price-delay", "paper:hou-moskowitz-2005"),
)

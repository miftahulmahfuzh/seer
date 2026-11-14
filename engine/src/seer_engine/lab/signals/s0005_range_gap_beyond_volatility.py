"""S0005 — a small daily range for the name's volatility and price: the range gap, residualised.

Source: variation of M0358 (the queued idea M0360); Parkinson (1980), "The Extreme Value Method
for Estimating the Variance of the Rate of Return", Journal of Business 53(1). Idea: M0358 ranked
on log(high-low volatility / close-to-close volatility) and could not tell the ratio from plain
volatility or price level in another coat. Here each month's log ratio is regressed across the
scored pool on log close-to-close volatility and log price, and the name is ranked on what is
left. M0358's treatment arm held the LOW end, so a lower residual scores higher: closes that move
more than the intraday range says they should.

Both volatilities are M0358's, over the ``N`` bars ending on the data date: Parkinson =
sqrt(mean(ln(high/low)^2) / (4 ln 2)), close volatility = the standard deviation of daily close
returns. A name with a high below its low or a non-positive price is not scored. Pure.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from datetime import date
from typing import Any

import numpy as np

from seer_engine.lab.signal import Signal
from seer_engine.strategies.base import History

N = 63  # daily returns, and daily ranges, in both volatilities
MIN_NAMES = 5  # three coefficients are fitted, so fewer names than this leave no residual to rank


def score(history: Mapping[str, History], market: Any, pool: AbstractSet[str], data_date: date) -> dict[str, float]:
    names: list[str] = []
    rows: list[tuple[float, float, float]] = []
    for symbol in sorted(pool):
        h = history.get(symbol)
        if h is None:
            continue
        i = h.index_of(data_date)
        if i is None or i < N:
            continue
        c = h.close[i - N : i + 1]
        hi, lo = h.high[i + 1 - N : i + 1], h.low[i + 1 - N : i + 1]
        if not (np.all(np.isfinite(c)) and np.all(c > 0.0) and np.all(lo > 0.0) and np.all(hi >= lo)):
            continue
        park = float(np.sqrt(np.mean(np.log(hi / lo) ** 2) / (4.0 * np.log(2.0))))
        vol = float(np.std(c[1:] / c[:-1] - 1.0))
        if park > 0.0 and vol > 0.0:
            names.append(symbol)
            rows.append((float(np.log(park / vol)), float(np.log(vol)), float(np.log(c[-1]))))
    if len(names) < MIN_NAMES:
        return {}
    a = np.asarray(rows)
    x = np.column_stack((np.ones(len(names)), a[:, 1], a[:, 2]))
    coef, *_ = np.linalg.lstsq(x, a[:, 0], rcond=None)
    resid = a[:, 0] - x @ coef
    return {s: -float(v) for s, v in zip(names, resid) if np.isfinite(v)}


SIGNAL = Signal(
    id="S0005",
    name="A daily high-low range that is small for the stock's volatility and price",
    family="stock-range-volatility-gap",
    source_kind="variation",
    source_ref="variation of M0358 (queued as M0360); Parkinson (1980), The Extreme Value Method for Estimating the Variance of the Rate of Return, J. Business 53(1)",
    hypothesis=(
        "Once ordinary volatility and price level are taken out, a name whose closes move more "
        "than its intraday range implies (overnight news, little intraday noise) earns more next "
        "month than one with a wide range and quiet closes: a positive controlled slope on both "
        "stores and a positive 2009-2015 spread."
    ),
    expected_failure=(
        "The residual is noise: M0358's ratio tied its random arms and faded on the dead-company "
        "store, and removing volatility removes the only thing it was measuring."
    ),
    lookback=N + 1,
    score=score,
    idea_id="M0360",
    seen_keys=("concept:range-volatility-gap-residualised",),
)

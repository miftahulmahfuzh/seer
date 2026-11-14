"""S0010 — among the forty most-traded members, the ones whose worst fall of the year was mildest.

Source: variation of M0606 (the queued idea M0610); "Maximum Drawdown, Recovery, and Momentum",
J. Risk Financial Management 14(11) 542 (2021). Idea: M0606 found the shallow-fall rank adds
nothing over the whole pool that the big-name pool does not already give. The one open question
is whether it adds anything inside the big-name pool. Only the ``BUSY`` most-traded pool names
are scored, and among them a milder worst peak-to-trough fall over the last ``WINDOW`` closes
scores higher. The fall is M0108's ``own_drawdown``. Pure; reads bars dated <= data_date only.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from datetime import date
from typing import Any

import numpy as np

from seer_engine.lab.signal import Signal
from seer_engine.strategies.base import History

WINDOW = 252  # closes the worst fall is measured over
BUSY = 40  # the most-traded pool names, by DV_N-bar mean trading value
DV_N = 20


def _dollar_volume(h: History, i: int) -> float:
    """Mean close times volume over the ``DV_N`` bars ending at bar ``i``."""
    return float(np.mean(h.close[i + 1 - DV_N : i + 1] * h.volume[i + 1 - DV_N : i + 1]))


def score(history: Mapping[str, History], market: Any, pool: AbstractSet[str], data_date: date) -> dict[str, float]:
    busy: list[tuple[float, str, float]] = []
    for symbol in sorted(pool):
        h = history.get(symbol)
        if h is None:
            continue
        i = h.index_of(data_date)
        if i is None or i + 1 < WINDOW:
            continue
        c = h.close[i + 1 - WINDOW : i + 1]
        if not (np.all(np.isfinite(c)) and np.all(c > 0.0)):
            continue
        dv = _dollar_volume(h, i)
        fall = float(np.max(1.0 - c / np.maximum.accumulate(c)))
        if np.isfinite(dv) and np.isfinite(fall):
            busy.append((-dv, symbol, fall))
    return {symbol: -fall for _, symbol, fall in sorted(busy)[:BUSY]}


SIGNAL = Signal(
    id="S0010",
    name="Among the forty most-traded members, those whose worst fall of the past year was mildest",
    family="stock-max-drawdown-rank",
    source_kind="variation",
    source_ref="variation of M0606 (queued as M0610); Maximum Drawdown, Recovery, and Momentum, J. Risk Financial Management 14(11) 542 (2021)",
    hypothesis=(
        "Inside the biggest names, the ones that held up best over the past year keep doing so: a "
        "milder worst fall goes with a higher next-month return beyond momentum, beta, size and "
        "volatility, giving a positive controlled slope on both stores and a positive 2009-2015 "
        "spread."
    ),
    expected_failure=(
        "A mild fall is low volatility and low beta, both controlled, so the slope is zero; forty "
        "names a month is the smallest cross-section the panel will measure, so the reading is "
        "noisy, and the big-name pool trailed SPY by about six points a year in 2009-2015."
    ),
    lookback=WINDOW,
    score=score,
    idea_id="M0610",
    seen_keys=("concept:shallow-fall-inside-40-most-traded",),
)

"""S0001 — twelve-month price momentum, skipping the most recent month.

Source: Jegadeesh and Titman (1993), "Returns to Buying Winners and Selling Losers", Journal of
Finance 48(1). Idea: the panel's known-positive check, the ranking behind F4-MOM12 and the
lab's longest-running family. Over a broad pool, names that rose most over the last year
(excluding the last month, where short-term reversal lives) have tended to keep outperforming
over the next month. Its controlled slope is close to zero **by construction**: twelve-minus-one
momentum is one of the panel's four controls, so the check is on its raw rank correlation and
spread, never on its controlled slope.
Pure: no clock, randomness, files, network, printing. Reads bars dated <= data_date only.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from datetime import date
from typing import Any

from seer_engine.lab.signal import Signal
from seer_engine.strategies.base import History

MOM_N = 252  # the window: the close 252 bars before data_date ...
SKIP = 21  # ... to the close 21 bars before it (f_factor's 12-1: c[-22] / c[-253] - 1)


def score(history: Mapping[str, History], market: Any, pool: AbstractSet[str], data_date: date) -> dict[str, float]:
    out: dict[str, float] = {}
    for symbol in sorted(pool):
        h = history.get(symbol)
        if h is None:
            continue
        i = h.index_of(data_date)
        if i is None or i < MOM_N:
            continue
        base = float(h.close[i - MOM_N])
        if base > 0.0:
            out[symbol] = float(h.close[i - SKIP]) / base - 1.0
    return out


SIGNAL = Signal(
    id="S0001",
    name="Twelve-month price momentum, skipping the most recent month",
    family="stock-momentum",
    source_kind="paper",
    source_ref="Jegadeesh and Titman (1993), Returns to Buying Winners and Selling Losers, Journal of Finance 48(1)",
    hypothesis=(
        "Across the screened pool, last year's winners (the most recent month left out) earn more "
        "over the next month than the pool does: a positive mean rank correlation and a positive "
        "top-minus-pool spread on the dev store, the panel's known-positive check."
    ),
    expected_failure=(
        "Momentum crashes after market bottoms (2009) turn the 2009-2015 era flat or negative, and "
        "its controlled slope is near zero because momentum is itself one of the controls."
    ),
    lookback=MOM_N + 1,
    score=score,
)

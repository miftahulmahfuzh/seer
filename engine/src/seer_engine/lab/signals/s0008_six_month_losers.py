"""S0008 — the index members that fell most over the last six months.

Source: variation of M0499 (the queued idea M0502); De Bondt & Thaler (1985) for
reversal at longer horizons. Idea: M0499's fallen-members control (the worst 126-day return among
current members) beat SPY in 2009-2015 while holding 0.6 names on average, too few to read. The
panel asks the same question of the whole pool.
The score is the close-to-close return over the ``N`` bars ending on the data date, negated, so
the deepest fallers score highest. Pure; reads bars dated <= data_date only.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from datetime import date
from typing import Any

import numpy as np

from seer_engine.lab.signal import Signal
from seer_engine.strategies.base import History

N = 126  # bars back the fall is measured over


def score(history: Mapping[str, History], market: Any, pool: AbstractSet[str], data_date: date) -> dict[str, float]:
    out: dict[str, float] = {}
    for symbol in sorted(pool):
        h = history.get(symbol)
        if h is None:
            continue
        i = h.index_of(data_date)
        if i is None or i < N:
            continue
        base = float(h.close[i - N])
        if base > 0.0:
            out[symbol] = -(float(h.close[i]) / base - 1.0)
    return out


SIGNAL = Signal(
    id="S0008",
    name="The index members that fell most over the last six months",
    family="stock-intermediate-reversal",
    source_kind="variation",
    source_ref="variation of M0499 (queued as M0502)",
    hypothesis=(
        "In M0499 the fallen-members control beat SPY in 2009-2015 while holding almost nothing. If "
        "that was a ranking and not a handful of names, the six-month losers among liquid members "
        "earn more next month than the pool, beyond what the momentum control already says: a "
        "positive controlled slope on both stores and a positive 2009-2015 spread."
    ),
    expected_failure=(
        "Six-month losers are momentum's short side: the raw readings are negative before 2009, "
        "and the dead-company store, where the fallers that kept falling are back, turns them "
        "negative everywhere."
    ),
    lookback=N + 1,
    score=score,
    idea_id="M0502",
    seen_keys=("concept:six-month-losers-whole-pool",),
)

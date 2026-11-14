"""S0009 — the index members that fell most over the last sixty sessions.

Source: variation of M0605 (the queued idea M0609); the mirror of M0562's
sixty-session winners. Idea: M0605 could not say whether the winners book's lead was momentum
or only its slow trading pace. A panel has no pace, so the loser ranking is read on its own.
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

N = 60  # bars back the fall is measured over


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
    id="S0009",
    name="The index members that fell most over the last sixty sessions",
    family="stock-momentum-short-window",
    source_kind="variation",
    source_ref="variation of M0605 (queued as M0609)",
    hypothesis=(
        "M0562's sixty-session winners led their matched blind draws at a slow pace. If that lead "
        "was the pace and not the ranking, the losers order returns as well as the winners did; if "
        "it was momentum, this ranking's readings are negative. Registered as the loser side: a "
        "positive controlled slope on both stores and a positive 2009-2015 spread."
    ),
    expected_failure=(
        "The winners' lead was real momentum, so the loser ranking reads negative on the dev "
        "store, and worse with the dead companies back."
    ),
    lookback=N + 1,
    score=score,
    idea_id="M0609",
    seen_keys=("concept:sixty-session-losers-whole-pool",),
)

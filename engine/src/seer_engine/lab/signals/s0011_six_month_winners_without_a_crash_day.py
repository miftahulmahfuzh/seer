"""S0011 — six-month winners that never lost a tenth of their value in one day.

Source: variation of M0614 (the queued idea M0616). Idea: M0614 banned one-day moves above 15% in
either direction and lost 1.6 points a year against the unfiltered six-month winners, probably
because big up-days are what winners are made of. This is the one-sided version: a name with a
one-day close-to-close fall worse than ``CRASH`` in the last ``CLEAN_N`` sessions gets no
opinion (a damaged stock), and every other name is scored on its ``MOM_N``-bar return. Big
up-days are allowed. Pure; reads bars dated <= data_date only.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from datetime import date
from typing import Any

import numpy as np

from seer_engine.lab.signal import Signal
from seer_engine.strategies.base import History

MOM_N = 126  # bars back the return is measured over
CLEAN_N = 90  # daily returns that must hold no crash day
CRASH = -0.10


def score(history: Mapping[str, History], market: Any, pool: AbstractSet[str], data_date: date) -> dict[str, float]:
    out: dict[str, float] = {}
    for symbol in sorted(pool):
        h = history.get(symbol)
        if h is None:
            continue
        i = h.index_of(data_date)
        if i is None or i < MOM_N:
            continue
        c = h.close[i - MOM_N : i + 1]
        if not (np.all(np.isfinite(c)) and np.all(c > 0.0)):
            continue
        recent = c[-CLEAN_N - 1 :]
        if float(np.min(recent[1:] / recent[:-1] - 1.0)) < CRASH:
            continue
        out[symbol] = float(c[-1]) / float(c[0]) - 1.0
    return out


SIGNAL = Signal(
    id="S0011",
    name="Six-month winners that never lost a tenth of their value in a single day",
    family="stock-gap-free-momentum",
    source_kind="variation",
    source_ref="variation of M0614 (queued as M0616)",
    hypothesis=(
        "A one-day crash marks a damaged company whose trailing return overstates its prospects. "
        "With those names removed, the six-month return orders next month's returns better than "
        "momentum's own control explains: a positive controlled slope on both stores and a "
        "positive 2009-2015 spread."
    ),
    expected_failure=(
        "It is six-month momentum with a handful of names removed, so the twelve-month momentum "
        "control absorbs it and the slope is zero; and momentum's 2009-2015 era is flat or "
        "negative among large members."
    ),
    lookback=MOM_N + 1,
    score=score,
    idea_id="M0616",
    seen_keys=("concept:down-gap-free-six-month-momentum",),
)

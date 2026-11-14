"""S0012 — the high-volume return premium: how unusual the latest session's volume is for the name.

Source: Gervais, Kaniel & Mingelgrin (2001), "The High-Volume Return Premium", Journal of Finance
56(3), 877-919, doi:10.1111/0022-1082.00349. Idea: a stock that trades unusually heavily for a
day becomes visible to investors who did not hold it, and tends to rise over the following
month; one that trades unusually lightly tends to lag. The paper compares the formation day's
volume with the same stock's previous 49 days, which cancels company size.

The score is the share of the previous ``REFERENCE`` sessions whose volume was below the data
date's (0 to 1; the paper's high-volume stocks are those above 0.9). The lab has punished a
persistent rise in trading value as crowding (M0034); this is the one-day shock, a different
horizon. Pure; reads bars dated <= data_date only.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from datetime import date
from typing import Any

import numpy as np

from seer_engine.lab.signal import Signal
from seer_engine.strategies.base import History

REFERENCE = 49  # the name's own previous sessions the latest volume is compared with


def score(history: Mapping[str, History], market: Any, pool: AbstractSet[str], data_date: date) -> dict[str, float]:
    out: dict[str, float] = {}
    for symbol in sorted(pool):
        h = history.get(symbol)
        if h is None:
            continue
        i = h.index_of(data_date)
        if i is None or i < REFERENCE:
            continue
        v = h.volume[i - REFERENCE : i + 1]
        if not (np.all(np.isfinite(v)) and np.all(v >= 0.0) and float(v.max()) > 0.0):
            continue
        out[symbol] = float(np.mean(v[:-1] < v[-1]))
    return out


SIGNAL = Signal(
    id="S0012",
    name="How unusually heavy the latest day's trading was, against the stock's own last ten weeks",
    family="stock-volume-shock",
    source_kind="paper",
    source_ref="Gervais, Kaniel & Mingelgrin (2001), The High-Volume Return Premium, Journal of Finance 56(3), doi:10.1111/0022-1082.00349",
    hypothesis=(
        "A day of unusually heavy trading widens the set of investors watching a stock, and its "
        "price rises over the following month; an unusually quiet day does the opposite. The "
        "volume rank orders next month's returns: a positive controlled slope on both stores and a "
        "positive 2009-2015 spread."
    ),
    expected_failure=(
        "Published in 2001 on NYSE stocks through 1996, so the dev window is mostly after it was "
        "known; index members are already visible to everyone; and the month-end session's volume "
        "is driven by index rebalances and window dressing, not by news about the company."
    ),
    lookback=REFERENCE + 1,
    score=score,
    seen_keys=("concept:high-volume-return-premium", "paper:gervais-kaniel-mingelgrin-2001"),
)

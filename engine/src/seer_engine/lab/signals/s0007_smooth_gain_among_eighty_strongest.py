"""S0007 — among the eighty strongest stocks, the ones whose gain came from many ordinary days.

Source: variation of M0436 (the queued idea M0486); Da, Gurun & Warachka (2014), "Frog in the
Pan: Continuous Information and Momentum", Review of Financial Studies 27(7). Idea: M0436 found
the smooth-gain filter no better than a random draw of the same forty strongest stocks, and forty
names for twenty slots leaves the filter little room to differ from plain momentum. This gives it
room once: only the ``STRONGEST`` highest 12-1 momentum pool names are scored, and among them a
smaller share of the year's gross upside earned on its five biggest days scores higher.

The key is M0436's: over the last 252 daily log returns ending on the data date, the sum of the
``BIG`` largest divided by the sum of all positive ones (0 to 1), negated. Pure.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from datetime import date
from typing import Any

import numpy as np

from seer_engine.lab.signal import Signal
from seer_engine.strategies.base import History

MOM_N = 252
SKIP = 21
STRONGEST = 80  # the pool names scored: the highest 12-1 momentum
BIG = 5  # the biggest days whose share of the upside is measured


def score(history: Mapping[str, History], market: Any, pool: AbstractSet[str], data_date: date) -> dict[str, float]:
    ranked: list[tuple[float, str, float]] = []
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
        r = np.diff(np.log(c))
        up = float(r[r > 0.0].sum())
        if up <= 0.0:
            continue
        share = float(np.sort(r)[-BIG:].sum()) / up
        ranked.append((-(float(c[-1 - SKIP]) / float(c[0]) - 1.0), symbol, share))
    return {symbol: -share for _, symbol, share in sorted(ranked)[:STRONGEST]}


SIGNAL = Signal(
    id="S0007",
    name="Among the eighty strongest stocks of the year, those whose gain came from many ordinary days",
    family="stock-return-jumpiness",
    source_kind="variation",
    source_ref="variation of M0436 (queued as M0486); Da, Gurun & Warachka (2014), Frog in the Pan, Review of Financial Studies 27(7)",
    hypothesis=(
        "Momentum that arrived a little at a time is under-noticed and continues; momentum that "
        "arrived on a few big days is already priced. Among the eighty strongest names, a smaller "
        "biggest-days share goes with a higher next-month return: a positive controlled slope on "
        "both stores and a positive 2009-2015 spread."
    ),
    expected_failure=(
        "The share is low volatility in another coat, which the panel controls for, and M0436 "
        "already found the filter inside a random pair's spread; a wider pool changes nothing."
    ),
    lookback=MOM_N + 1,
    score=score,
    idea_id="M0486",
    seen_keys=("concept:biggest-days-share-top80-momentum",),
)

"""S0013 — continuing overreaction: a year of trading volume signed by each month's direction.

Source: Byun, Lim & Yun (2016), "Continuing Overreaction and Stock Return Predictability", Journal
of Financial and Quantitative Analysis 51(6). Idea: overconfident investors trade more after a
move confirms their view, so volume that keeps arriving in the direction of the price is a
measure of overreaction still under way, and it predicts returns beyond past returns themselves.

    CO = sum over the last 12 months m (m = 0 the newest) of (12 - m) * sign(r_m) * volume_m
         / (mean monthly volume * sum of the weights)

A month is ``MONTH`` bars; r_m is its close-to-close return and volume_m its summed share
volume. Dividing by the name's own mean volume cancels size. Higher is better. Pure.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from datetime import date
from typing import Any

import numpy as np

from seer_engine.lab.signal import Signal
from seer_engine.strategies.base import History

MONTH = 21  # bars in one month
MONTHS = 12


def score(history: Mapping[str, History], market: Any, pool: AbstractSet[str], data_date: date) -> dict[str, float]:
    n = MONTH * MONTHS
    weights = np.arange(1.0, MONTHS + 1.0)  # oldest month first, the newest weighs MONTHS
    out: dict[str, float] = {}
    for symbol in sorted(pool):
        h = history.get(symbol)
        if h is None:
            continue
        i = h.index_of(data_date)
        if i is None or i < n:
            continue
        c = h.close[i - n : i + 1 : MONTH]
        v = h.volume[i + 1 - n : i + 1]
        if not (np.all(np.isfinite(c)) and np.all(c > 0.0) and np.all(np.isfinite(v))):
            continue
        vol = v.reshape(MONTHS, MONTH).sum(axis=1)
        mean = float(vol.mean())
        if mean <= 0.0:
            continue
        signed = np.sign(c[1:] / c[:-1] - 1.0) * vol
        out[symbol] = float(np.sum(weights * signed)) / (mean * float(weights.sum()))
    return out


SIGNAL = Signal(
    id="S0013",
    name="A year of trading volume counted for or against the stock by each month's direction, recent months most",
    family="stock-continuing-overreaction",
    source_kind="paper",
    source_ref="Byun, Lim & Yun (2016), Continuing Overreaction and Stock Return Predictability, JFQA 51(6)",
    hypothesis=(
        "Volume that keeps arriving in the direction of the price marks an overreaction still "
        "under way, and it carries information past returns do not: a higher signed-volume score "
        "goes with a higher next-month return with momentum controlled, giving a positive "
        "controlled slope on both stores and a positive 2009-2015 spread."
    ),
    expected_failure=(
        "It is the count of up months, weighted by volume: momentum in another coat, which the "
        "panel's momentum control absorbs. Published 2016 on data through 2011, with momentum's "
        "own weak 2009-2015 among large members."
    ),
    lookback=MONTH * MONTHS + 1,
    score=score,
    seen_keys=("concept:continuing-overreaction", "concept:signed-volume", "paper:byun-lim-yun-2016"),
)

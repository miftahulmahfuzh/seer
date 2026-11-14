"""S0006 — last month's losers, newest days counted most, with no single day allowed to dominate.

Source: variation of M0407 (the queued idea M0409); Cakici, Fieberg, Neszveda, Bianchi & Zaremba
(2026), the daily-return information factor (Alpha Architect summary,
https://alphaarchitect.com/daily-stock-returns/). Idea: M0407 showed that weighting last month's
days by recency only lifts a reversal ranking to a random pick's level. The other half of the
paper's idea is the size of single days: cap each daily return at ``CAP`` either way before the
recency-weighted sum, so one extreme day (an earnings gap, which drifts rather than reverses)
cannot carry the score.

    score = - sum over the last 21 daily returns r_a (a = 0 the newest) of DECAY**a * clip(r_a)

The sign is M0407's: the lowest sums are held, so the score is the sum negated. Pure.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from datetime import date
from typing import Any

import numpy as np

from seer_engine.lab.signal import Signal
from seer_engine.strategies.base import History

N = 21  # daily returns in the sum
DECAY = 0.9  # M0353's and M0407's middle setting
CAP = 0.03  # each daily return is clipped to +-CAP before it is weighted


def score(history: Mapping[str, History], market: Any, pool: AbstractSet[str], data_date: date) -> dict[str, float]:
    weights = DECAY ** np.arange(N - 1, -1, -1.0)  # oldest first, the newest day weighs 1
    out: dict[str, float] = {}
    for symbol in sorted(pool):
        h = history.get(symbol)
        if h is None:
            continue
        i = h.index_of(data_date)
        if i is None or i < N:
            continue
        c = h.close[i - N : i + 1]
        if not (np.all(np.isfinite(c)) and np.all(c > 0.0)):
            continue
        r = np.clip(c[1:] / c[:-1] - 1.0, -CAP, CAP)
        out[symbol] = -float(np.sum(weights * r))
    return out


SIGNAL = Signal(
    id="S0006",
    name="Last month's losers, recent days counted most and every day's move capped at three percent",
    family="stock-daily-return-shape",
    source_kind="variation",
    source_ref="variation of M0407 (queued as M0409); Cakici, Fieberg, Neszveda, Bianchi & Zaremba (2026), https://alphaarchitect.com/daily-stock-returns/",
    hypothesis=(
        "Short-term reversal lives in the ordinary days, and the extreme days (news) drift instead. "
        "Capping each day removes the part that does not reverse, so the capped, recency-weighted "
        "loser ranking orders next month's returns: a positive controlled slope on both stores and "
        "a positive 2009-2015 spread."
    ),
    expected_failure=(
        "Among large liquid members one-month reversal is too small to see after 2000, capped or "
        "not; M0407's uncapped ranking only matched random picks, and the cap changes few names."
    ),
    lookback=N + 1,
    score=score,
    idea_id="M0409",
    seen_keys=("concept:capped-daily-return-reversal",),
)

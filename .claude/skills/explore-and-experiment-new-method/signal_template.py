"""SNNNN — <one-line name: what it ranks on, in plain words>.

Source: <URL / citation / "variation of S00xx" / general knowledge>.
Idea: <two or three sentences: why a higher score should mean a higher next-month return>.

Copy to engine/src/seer_engine/lab/signals/sNNNN_<slug>.py (the next free id comes from
`lab next-signal-id`), replace every SNNNN, then commit it: the commit is the pre-registration.
Then run `lab panel SNNNN`.
A signal is only the ranking: no width, weights, switch or cadence. Those belong to the one
standard chassis a signal is booked on once it clears the panel.
Pure: no clock, randomness, files, network or printing. Read only bars dated <= data_date, and
no more than `lookback` of them. Find data_date with `h.index_of` so the score is the same on a
full history as on the cut `lab panel` hands you (tests/test_lab_signals.py checks both).
Higher is better. Leave a name out, or score it NaN, when you have no opinion.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from datetime import date
from typing import Any

from seer_engine.lab.signal import Signal
from seer_engine.strategies.base import History

LOOKBACK_N = 126  # bars back the score compares against


def score(history: Mapping[str, History], market: Any, pool: AbstractSet[str], data_date: date) -> dict[str, float]:
    out: dict[str, float] = {}
    for symbol in sorted(pool):
        h = history.get(symbol)
        if h is None:
            continue
        i = h.index_of(data_date)  # every pool name has a bar dated data_date
        if i is None or i < LOOKBACK_N:
            continue
        base = float(h.close[i - LOOKBACK_N])
        if base > 0.0:
            out[symbol] = float(h.close[i]) / base - 1.0  # <your score>
    return out


SIGNAL = Signal(
    id="SNNNN",
    name="<what it ranks on, in plain words>",
    family="stock-<what it ranks on>",
    source_kind="knowledge",  # paper | blog | github | knowledge | variation
    source_ref="",  # required unless source_kind is "knowledge"
    hypothesis="<why a higher score means a higher next-month return, written before the panel runs>",
    expected_failure="<the way it most likely fails: an era, a control that explains it, a dead-name effect>",
    lookback=LOOKBACK_N + 1,  # bars through data_date the score reads, at most 473
    score=score,
    market_fields=(),  # e.g. ("dividends",) when the score reads market.dividends
    idea_id=None,  # "M0xxx" when this answers a queued idea row
)

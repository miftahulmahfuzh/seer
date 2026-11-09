"""M0535 — The fallen after the storm, kept to live names: the members furthest below their 200-day
average, with a trading-volume floor on the pool, bought only while SPY is above its own 200-day
average.

Variation of M0285 (a variation of M0282; moving-average distance, Avramov, Kaplanski &
Subrahmanyam, working paper 2018; long-term reversal after De Bondt & Thaler 1985). Reserved by
Sera batch 20261109-1003 as an ``idea`` row; this file refines it and keeps its id.

WHY. M0285's fallen-stocks book behind SPY's 200-day switch led its blind draw by little, and M0330
found that the beaten-down book's return shrinks and its fall deepens once the dead companies the
dev store cannot price are put back. A beaten-down stock is, disproportionately, one that is about
to stop existing. M0288 found a cross-sectional dollar-volume floor works as a liveness filter on
a residual-momentum book (it narrowed the dev-minus-check-store gap, at a cost in return). This asks
whether the same floor, put on the fallen book's pool, keeps the bounce and sheds the names that
only look cheap because they are dying.

REUSE, NAMED. The picking is M0282's, imported unchanged: ``MadParams`` (hold 20, keep while inside
40, equal slots, monthly, the SPY 200-day switch), ``MadAllocator``, fractional shares at Gotrade's
real fees. The only addition is ``FloorMadParams.dv_pct`` and a pool step: after M0282's pool (sized
members, one listing per company) is built, the worst-traded ``dv_pct`` percent of it by 20-day
mean close x volume is dropped, ranked cross-sectionally on the day. Cross-sectional on purpose: a
fixed dollar bar would be a date filter, since dollar volumes grew by more than an order of
magnitude over the dev window. The cut is by rank, ties by symbol, so the rungs nest. A pool
that the floor leaves under M0282's 50-name minimum holds SPY, as M0282's own guard does.

ARMS (the floor rungs are 20 and 40 percent, so the ladder has a middle and a strict end; M0288
showed 80 percent herds the book into big companies).
    BOT20-SW-DV20       the fallen book behind the switch, least-traded fifth of the pool dropped
    BOT20-SW-DV20-PLC   its no-opinion arm: a blind hash-order draw with the same floored pool, book
                        size and entry count (the top-book shadow of M0282 replayed on the floored
                        pool), behind the same switch
    BOT20-SW-DV40       the least-traded two fifths dropped
    BOT20-SW-DV40-PLC   its blind draw
    BOT20-SW-DV00       no floor: M0285-BOT20-SW's book under this id. It is the unfloored twin
                        and the reference rung, not a new book, and ``lab twins`` will record it
                        as a twin of M0285-BOT20-SW; it costs no look.

Pure: no clock, randomness, files or network; reads only bars dated on or before ``data_date`` and
share counts filed by it.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab import control_draw
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0282_moving_average_distance import (
    DEPTH,
    Features,
    MadAllocator,
    MadParams,
    MadPrepared,
    banded,
    pool_on,
    scores,
)
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.indicators import mean_dollar_volume_window

ADDED = date(2026, 11, 9)
DV_BARS = 20  # sessions in the dollar-volume mean (M0288's, and F4's screen's)


@dataclass(frozen=True, slots=True)
class FloorMadParams(MadParams):
    """M0282's parameters plus ``dv_pct``, the percent of the day's pool dropped by dollar volume."""

    dv_pct: int = 0

    def __post_init__(self) -> None:
        MadParams.__post_init__(self)
        if isinstance(self.dv_pct, bool) or not isinstance(self.dv_pct, int):
            raise TypeError(f"dv_pct must be an int, got {type(self.dv_pct).__name__}")
        if not 0 <= self.dv_pct < 100:
            raise ValueError(f"dv_pct must be in [0, 100), got {self.dv_pct}")

    def as_dict(self) -> dict[str, str]:
        out = MadParams.as_dict(self)
        out["dv_pct"] = str(self.dv_pct)
        out["dv_bars"] = str(DV_BARS)
        return out


def _check(params: object) -> FloorMadParams:
    if not isinstance(params, FloorMadParams):
        raise TypeError(f"params must be FloorMadParams, got {type(params).__name__}")
    return params


def dollar_volume(prepared: MadPrepared, symbol: str, data_date: date) -> float | None:
    """20-session mean close x volume ending on ``data_date``, or None when it cannot be read."""
    h = prepared.history.get(symbol)
    if h is None:
        return None
    i = h.index_of(data_date)
    if i is None or i + 1 < DV_BARS:
        return None
    lo = i + 1 - DV_BARS
    dv = float(mean_dollar_volume_window(h.close[None, lo : i + 1], h.volume[None, lo : i + 1],
                                         DV_BARS)[0])
    return dv if math.isfinite(dv) else None


def floored_pool(prepared: MadPrepared, members: AbstractSet[str], data_date: date,
                 dv_pct: int) -> dict[str, Features]:
    """M0282's pool less its worst-traded ``dv_pct`` percent, or empty when too few names remain."""
    pool = pool_on(prepared, members, data_date)
    if dv_pct <= 0 or not pool:
        return pool
    dv = {s: dollar_volume(prepared, s, data_date) for s in pool}
    ranked = sorted((s for s in pool if dv[s] is not None), key=lambda s: (-dv[s], s))  # type: ignore[operator]
    keep = len(pool) - math.floor(len(pool) * dv_pct / 100)
    kept = ranked[:keep]
    out = {s: pool[s] for s in sorted(kept)}
    return out if len(out) >= 50 else {}


class FloorMadAllocator(MadAllocator):
    """M0282's picks from a pool with a dollar-volume floor; everything else is M0282's."""

    id = "M0535"

    def _names(self, prepared: MadPrepared, members: AbstractSet[str], data_date: date,
               held: frozenset[str], p: Any) -> Sequence[str]:
        p = _check(p)
        if p.signal == "control":
            def replay(d: date, shadow: AbstractSet[str]) -> tuple[list[str], list[str]]:
                pool = floored_pool(prepared, members, d, p.dv_pct)
                if not pool:
                    return [], []
                return sorted(pool), banded(scores(pool, "top"), shadow, p.top, p.keep)

            return control_draw.shadow_book(replay, data_date, held, tag="M0535", seed=p.seed,
                                            depth=DEPTH)
        pool = floored_pool(prepared, members, data_date, p.dv_pct)
        if not pool:
            return []
        return banded(scores(pool, p.signal), held, p.top, p.keep)


FLOOR = FloorMadAllocator()


def _v(suffix: str, params: FloorMadParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0535-{suffix}", family="M0535", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=FLOOR, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0535",
    name=("The fallen after the storm, kept to live names: beaten-down members with a "
          "trading-volume floor behind the 200-day switch"),
    family="stock-moving-average-distance",
    source_kind="variation",
    source_ref=("Variation of M0285; long-term reversal after De Bondt & Thaler (1985); "
                "moving-average distance, Avramov, Kaplanski & Subrahmanyam (2018 working paper); "
                "the floor is M0288's liveness filter."),
    parent_id="M0285",
    hypothesis=(
        "M0285's beaten-down-members book behind SPY's 200-day switch leaned on dead companies "
        "the dev store cannot price, and M0330 showed the extra return of this book shrinks and "
        "its fall deepens once they are back (loose fear switch: 13.1% to 8.7% a year, worst fall "
        "66% to 87% on the survivorship-check store). A trading-volume floor has closed the gap "
        "between the two stores on other price screens (M0288). Test the same book, band and "
        "switch (hold 20, keep inside 40, equal slots, monthly, fractional shares at Gotrade's "
        "real fees on the owner's top-up) with a cross-sectional floor on the pool: drop the "
        "least-traded 20% or 40% of the day's sized members by 20-day mean dollar volume. A "
        "floored blind draw behind the same switch is the no-opinion arm for each rung, and the "
        "unfloored book re-run under this id is the twin. Long-term reversal is published and "
        "old (1985), so a dev lead is likely an old edge. Predictions written before any result: "
        "the dev-minus-check-store gap of the fallen book narrows as the floor rises; the "
        "floored book keeps at least 1 point a year over its own floored draw; its worst fall "
        "on the check store stays under 50%. Read the survivorship-check store first."
    ),
    expected_failure=(
        "In order of likelihood. (1) The floor removes the cheapest, most beaten-down names that "
        "carry the edge, and the lead falls to the draw's: M0285's lead over its draw was "
        "already small, and M0288 found a volume floor costs return by herding a book into big "
        "companies. (2) The dying companies a floor is meant to shed are not thin until the end: "
        "a collapsing bank trades heavily on the way down, so dollar volume is a poor liveness "
        "test for a book that buys falling stocks, and the check-store fall stays deep. (3) With "
        "the floor on, the book converges on SPY's big-company drift and beats nothing in "
        "2009-2015. (4) The switch still re-enters after the bounce. Any of these is a "
        "rejection, not a reason to tune the floor afterwards."
    ),
    candidates=(
        _v("BOT20-SW-DV20", FloorMadParams(signal="bottom", switch=True, dv_pct=20),
           "The fallen book behind the 200-day switch, least-traded fifth of the pool dropped"),
        _v("BOT20-SW-DV20-PLC",
           FloorMadParams(signal="control", switch=True, seed=1, dv_pct=20),
           "Blind draw from the same floored pool behind the same switch: no opinion on names"),
        _v("BOT20-SW-DV40", FloorMadParams(signal="bottom", switch=True, dv_pct=40),
           "The fallen book behind the switch, least-traded two fifths of the pool dropped"),
        _v("BOT20-SW-DV40-PLC",
           FloorMadParams(signal="control", switch=True, seed=1, dv_pct=40),
           "Blind draw from the 40% floored pool behind the same switch"),
        _v("BOT20-SW-DV00", FloorMadParams(signal="bottom", switch=True, dv_pct=0),
           "No floor: M0285-BOT20-SW's book under this id, the unfloored twin and reference rung"),
    ),
    seen_keys=(
        "concept:dollar-volume-floor-on-fallen-stocks",
        "concept:long-term-reversal-trend-switch-liveness-floor",
    ),
)

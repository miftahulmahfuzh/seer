"""M0338 — Switch dwell time: how many days the market must agree before the cash switch flips.

Source: variation of M0337's chassis (F4's screen, plain 12-1 ranking, top 20 equal weight,
monthly, SPY 200-day switch, Gotrade real fees, fractional shares). The trend switch is old
(Brock, Lakonishok & LeBaron 1992; Faber 2007), so no fade argument applies to the idea itself.
M0148 bought hysteresis as a cool-off counted in monthly checks, and M0101 bought it as a price
band around the average; neither asked the plainer question tried here: how many consecutive
daily closes on the other side of the average before the book moves?

Rule at each monthly check, with k the dwell: if SPY's last k closes were each above their own
200-day average the switch is on; if each was at or below it, off; a mixed window leaves the
book as it is (invested stays invested, cash stays cash). k=1 is the plain strict switch, so
that arm must reproduce M0332-M12-1. Variants fixed before any result: k=1 (paired control),
k=3, k=10, k=21 (a full month), and the same book with the switch off, always invested, which
prices what the switch costs. A rule run beside an always-invested twin is what tells a dead
rule from a badly dressed one. Only the gate differs between arms; the screen and ranking come
from ``factor_rows`` unchanged. Pure; reads only bars dated <= data_date.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    FactorParams,
    factor_lookback,
    factor_rows,
    targets_from_rows,
)

ADDED = date(2026, 10, 24)

SWITCH = ("SPY", 200)


@dataclass(frozen=True, slots=True)
class Params:
    dwell: int = 1
    top: int = 20
    trend: tuple[str, int] | None = SWITCH

    def factor(self) -> FactorParams:
        return FactorParams(rank="momentum", top=self.top, mom_n=252, mom_skip=21, trend=self.trend)

    def as_dict(self) -> dict[str, str]:
        t = "none" if self.trend is None else f"{self.trend[0]}:{self.trend[1]}"
        return {"dwell": str(self.dwell), "top": str(self.top), "trend": t}


def _side(history: Mapping[str, History], data_date: date, symbol: str, n: int, k: int) -> int:
    """+1 when each of the last k closes sat above its own n-day average, -1 when each sat at or
    below it, 0 when mixed or when the history is too short to say."""
    h = history.get(symbol)
    if h is None:
        return 0
    i = h.index_of(data_date)
    if i is None or i + 1 < n + k - 1:
        return 0
    c = h.close
    above = 0
    for j in range(i - k + 1, i + 1):
        above += int(c[j] > float(np.mean(c[j + 1 - n : j + 1])))
    if above == k:
        return 1
    return -1 if above == 0 else 0


class Alloc:
    """F4's screened members ranked on 12-1 momentum, top ``top``, behind a dwell-confirmed switch.

    A mixed reading keeps the book where it is, read from ``held``: a non-empty book is
    invested, an empty one is in cash.
    """

    id = "M0338"

    def lookback(self, params: Params) -> int:
        return factor_lookback(params.factor()) + max(params.dwell, 1)

    def symbols(self, params: Params) -> tuple[str, ...]:
        return () if params.trend is None else (params.trend[0],)

    def holds(self, params: Params) -> tuple[str, ...]:
        return ()

    def uses_members(self, params: Params) -> bool:
        return True

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Params) -> tuple[Target, ...]:
        if params.dwell < 1:
            raise ValueError(f"dwell must be >= 1, got {params.dwell}")
        if params.trend is not None:
            symbol, n = params.trend
            side = _side(history, data_date, symbol, n, params.dwell)
            if side < 0 or (side == 0 and not held):
                return ()
        fp = params.factor()
        return targets_from_rows(factor_rows(history, members, data_date, fp), fp)

    def prepare(self, history: Mapping[str, History]) -> Any:
        return dict(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Params) -> tuple[Target, ...]:
        return self.targets(prepared, members, data_date, held, params)


ALLOC = Alloc()


def _v(suffix: str, dwell: int, rationale: str, trend=SWITCH) -> Candidate:
    return Candidate(id=f"M0338-{suffix}", family="M0338", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=ALLOC, params=Params(dwell=dwell, trend=trend),
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0338",
    name="Switch dwell time: how long the cash switch stays on",
    family="stock-switch-timing",
    source_kind="variation",
    source_ref="variation of M0337's chassis; Brock, Lakonishok & LeBaron (1992) and Faber (2007) for the trend switch; M0148 (monthly cool-off) and M0101 (price band) are the nearest tried hysteresis",
    parent_id="M0337",
    hypothesis=(
        "Every ranking tried behind the SPY 200-day switch lands near the plain 12-1 result, and the "
        "switch decides most of the outcome. Question: does requiring SPY to close on the same side "
        "of its 200-day average for k days running before the book moves cut false alarms and fees "
        "without missing the big falls? Book: F4's screen, plain 12-1 ranking, top 20 equal weight, "
        "monthly, fractional shares at Gotrade's real fees. Arms: k=1 (the plain switch, the paired "
        "control, which must reproduce M0332-M12-1), k=3, k=10, k=21, and the switch off, always "
        "invested, to price what acting on the signal costs. A mixed window keeps the book as it "
        "is. This differs from M0148, which waits a number of monthly checks after a flip, and from "
        "M0101, which widens the price threshold. The switch is decades old, so no fade argument "
        "applies. Success: a k above 1 keeps the plain switch's protection (worst fall near the "
        "control's) with a better funded return, fewer trades and a smaller 2009-2015 gap."),
    expected_failure=(
        "At a monthly check the 200-day average moves so slowly that k=3 and k=10 read almost "
        "always the same as k=1: the arms land within noise of the control and nothing separates. "
        "Where they do differ they exit a few days late in a real fall (2008) and return a few days "
        "late in a rebound (2009), so the dwell costs as much as it saves. The always-invested "
        "twin falls far deeper, as every momentum book here does, and the real gap to SPY in "
        "2009-2015 is time in cash plus fees, which the dwell barely touches."),
    candidates=(
        _v("K1", 1, "paired control: the strict one-day switch, must reproduce M0332-M12-1"),
        _v("K3", 3, "treatment: three days running on the same side before the book moves"),
        _v("K10", 10, "treatment: ten days (two trading weeks) running"),
        _v("K21", 21, "treatment: a full month of days running"),
        _v("NOSW", 1, "no opinion: same book, switch off, always invested", trend=None),
    ),
    seen_keys=("concept:switch-dwell-time", "concept:consecutive-close-trend-confirmation"),
)

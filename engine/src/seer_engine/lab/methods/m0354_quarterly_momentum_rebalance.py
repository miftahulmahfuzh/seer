"""M0354 — Slow the momentum book: re-rank plain 12-1 top-20 every quarter, not every month.

Source: variation of M0332, prompted by M0055. M0055 found plain 12-1 momentum earned far more
on the owner's deposits than any version that traded the last month, and those versions made about
twice the trades. The lab has never priced the cheapest way to trade less: keep the same picker and
simply look at it less often.
Idea: on Gotrade's real fees a $28 slot pays about 0.47% a trade, so a 20-name book that turns over
most of its names every month pays for it. Rank only at the end of March, June, September and
December and hold the names in between. Momentum is slow (12-1 changes little in a month) so most of
the monthly trades are churn at the margin. The cost: a loser lingers for up to three months, and
the 2008 fall is the likeliest place that shows. Jegadeesh and Titman published 12-1 momentum in
1993, so the dev window sits after the crowd; 2009-2015 is the first filter.

``QUARTERLY`` wraps ``FACTOR`` and changes nothing but *when the basket is allowed to change*. On a
decision session in a rank month (calendar month number divisible by ``period``, so period 1 is every
month, period 3 is Mar/Jun/Sep/Dec and period 6 is Jun/Dec) it returns the picker's fresh targets.
On any other decision session it keeps the names the book already holds at the picker's weight; the
SPY 200-day switch is still read every month, so the gate keeps its monthly cadence in every arm
and only the stock selection slows down. A book that holds nothing (it was in cash behind the
switch) buys a fresh basket the moment the switch turns on, because there is nothing to keep.
Period 1 never keeps anything and so reproduces M0332-M12-1 / -NOSW through another allocator id:
that is the control and the fidelity check in one. The no-switch twins are the dressing arms (the
switch carries most of what these books earn), so a quarterly effect that only shows behind the
switch is told apart from one that shows always invested. Pure; reads only bars dated <= d.
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
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import FACTOR, FactorParams, trend_on

ADDED = date(2026, 11, 1)

SWITCH = ("SPY", 200)
TOP = 20


@dataclass(frozen=True, slots=True)
class Params:
    """``period`` is months between re-ranks (1, 3 or 6, all divide 12); ``switch`` is the gate."""

    period: int = 3
    switch: bool = True

    def __post_init__(self) -> None:
        if self.period not in (1, 3, 6):
            raise ValueError(f"period must be 1, 3 or 6, got {self.period}")

    def as_dict(self) -> dict[str, str]:
        return {"period_months": str(self.period), "switch": str(self.switch)}

    def picker(self) -> FactorParams:
        return FactorParams(rank="momentum", top=TOP, mom_n=252, mom_skip=21,
                            trend=SWITCH if self.switch else None)


def _rank_month(d: date, period: int) -> bool:
    """True when the decision at ``d``'s close opens a re-rank (the next session starts month d+1)."""
    return (d.year * 12 + d.month) % period == 0


def _keep(history: Mapping[str, History], held: frozenset[str], d: date) -> tuple[Target, ...]:
    """The held names at the picker's equal weight, priced at their last close on or before d."""
    w = equal_weight(TOP)
    out: list[Target] = []
    for s in sorted(held):
        h = history.get(s)
        if h is None:
            continue
        end = int(np.searchsorted(h.dates, np.datetime64(d), side="right"))
        if end == 0:
            continue
        t = target_from_close(s, float(h.close[end - 1]), w)
        if t is not None:
            out.append(t)
    return tuple(out)


class QuarterlyAlloc:
    """FACTOR's 12-1 top-20, re-ranked every ``period`` months and held in between."""

    id = "M0354"

    def lookback(self, params: Params) -> int:
        return FACTOR.lookback(params.picker())

    def symbols(self, params: Params) -> tuple[str, ...]:
        return FACTOR.symbols(params.picker())

    def holds(self, params: Params) -> tuple[str, ...]:
        return ()

    def uses_members(self, params: Params) -> bool:
        return True

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Params) -> tuple[Target, ...]:
        p = params.picker()
        if not trend_on(history, data_date, p):
            return ()
        if _rank_month(data_date, params.period) or not held:
            return FACTOR.targets(history, members, data_date, held, p)
        return _keep(history, held, data_date)

    def prepare(self, history: Mapping[str, History]) -> Any:
        return FACTOR.prepare(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Params) -> tuple[Target, ...]:
        p = params.picker()
        if not trend_on(prepared.history, data_date, p):
            return ()
        if _rank_month(data_date, params.period) or not held:
            return FACTOR.targets_prepared(prepared, members, data_date, held, p)
        return _keep(prepared.history, held, data_date)


QUARTERLY = QuarterlyAlloc()


def _v(suffix: str, params: Params, rationale: str) -> Candidate:
    return Candidate(id=f"M0354-{suffix}", family="M0354", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=QUARTERLY, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0354",
    name="Hold last year's winners less often: plain 20-name momentum rebalanced quarterly instead of monthly",
    family="stock-momentum",
    source_kind="variation",
    source_ref="M0332",
    parent_id="M0332",
    hypothesis=(
        "M0055 showed plain 12-1 top-20 momentum earned far more on deposits than any version that "
        "traded the last month, and those versions made about twice the trades. Test whether the "
        "plain book, re-ranked every quarter instead of every month (fewer trades, fewer Gotrade "
        "fees on small slots), keeps its edge. Same picker as M0332-M12-1 (12-1, top 20, equal "
        "weight, F4's screen, SPY 200-day switch read monthly), fractional shares at Gotrade's real "
        "fees. Arms: Q3 (re-rank Mar/Jun/Sep/Dec), Q6 (re-rank Jun/Dec, the dial's far end), M1 "
        "(period 1, the monthly control and a reproduction of M0332-M12-1 through this allocator), "
        "and the two switch-off twins Q3-NOSW and M1-NOSW as the always-invested arms. Question: "
        "does re-ranking a third as often cut trades and fees enough to keep or beat the monthly "
        "book's return, and is any gain still there in 2009-2015? Momentum was published in 1993, so "
        "a strong dev edge may be the pre-publication years and fade after."),
    expected_failure=(
        "A slower rebalance lets losers linger and deepens the 2008 fall: the quarterly book's "
        "worst fall rises above M1's and the extra return does not pay for it. Second failure: the "
        "saving is smaller than hoped, because the monthly resize back to equal weight and the "
        "switch's monthly in-and-out trades still happen in every arm, so fees fall by much less "
        "than a third. Third: Q3 and M1 hold nearly the same names (12-1 changes slowly) and the "
        "difference is inside the noise of 20-name books. Behind the switch every arm still lags "
        "SPY in 2009-2015 through time in cash."),
    candidates=(
        _v("Q3", Params(period=3), "treatment: re-rank each quarter, switch on"),
        _v("Q6", Params(period=6), "dial end: re-rank twice a year, switch on"),
        _v("M1", Params(period=1), "control: monthly re-rank, switch on; reproduces M0332-M12-1"),
        _v("Q3-NOSW", Params(period=3, switch=False), "treatment with the switch off, always invested"),
        _v("M1-NOSW", Params(period=1, switch=False),
           "control with the switch off, always invested; reproduces M0332-M12-1-NOSW"),
    ),
    seen_keys=("concept:quarterly-momentum-rebalance", "concept:momentum-holding-period"),
)

"""M0499 — Dropped from the index, priced as printed: deletions above a real one-dollar floor and a
size floor, behind the market switch, beside fallen members.

Source: M0495 (parent), reserved by Sera batch 20261106-1616.
M0495's dropped-index book beat SPY on both stores but tied its fallen-members control in
2009-2015, and 48 of its 150 points of simple-sum lead came from 10 pick-months in stocks that
printed under one dollar (HealthSouth, Unisys, Sirius). Its ``$1`` floor read the stored,
split-adjusted close, so a company that later did a reverse split (Unisys, 1-for-10 in 2009) sat
above the floor on a price nobody could have paid. This method keeps M0495's pools and slot
arithmetic and changes only what decides whether a name may be bought:

  * **printed floor**: the close as it printed that day (stored close times every split the vendor
    applied after it, M0383's ``printed_close``) must be at least ``min_printed``. The adjusted-close
    floor is switched off (``min_price`` near zero) so the printed one is the only price test.
  * **size floor** (``min_value`` > 0): company size on the day (``Market.market_value``: shares
    as filed by that day times the printed close) must be at least ``min_value``. A name whose size
    is unknown is excluded, so a size-floored arm holds no stock before 1996, when the share
    record starts, and none whose filings the store lacks.
  * **switch** (``trend``): while SPY closes at or below its 200-day average the book is all cash,
    stocks and the SPY residual alike, as in M0491.

Both floors apply to the fallen-members control too, and the control still holds exactly as many
names as the deletion book holds on the day, so the two arms are invested on the same days in the
same amounts. Pools are ranked first and capped after filtering, so a name that fails a floor is
replaced by the next one, not left as a hole.

Market-aware (``market_fields = ("shares",)``): without splits there is no printed price, and the
book holds nothing on every arm. Fractional shares at Gotrade's real fees.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0383_nominal_price_level_tilt import printed_close
from seer_engine.lab.methods.m0495_index_deletion_rebound import (
    DELETION,
    DV_N,
    IDLE,
    DeletionParams,
    DeletionPrepared,
    deletion_pool,
    loser_pool,
)
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_swing import trend_on

ADDED = date(2026, 11, 6)

NO_ADJ_FLOOR = 1e-6  # the parent's adjusted-close floor, switched off


@dataclass(frozen=True, slots=True)
class PrintedDeletionParams:
    """M0495's window, slot and control, plus the printed floor, the size floor and the switch."""

    window_months: int = 6
    slot: float = 0.10
    control: str = "none"  # "losers": the matched fallen-member twin
    min_printed: float = 1.0
    min_value: float = 500_000_000.0  # 0 switches the size floor off
    trend: tuple[str, int] | None = None

    def __post_init__(self) -> None:
        DeletionParams(window_months=self.window_months, slot=self.slot, control=self.control)
        if not (self.min_printed > 0 and self.min_value >= 0):
            raise ValueError("min_printed must be > 0 and min_value >= 0")
        if self.trend is not None and (len(self.trend) != 2 or int(self.trend[1]) < 2):
            raise ValueError(f"trend must be (symbol, n >= 2) or None, got {self.trend!r}")

    @property
    def inner(self) -> DeletionParams:
        return DeletionParams(
            window_months=self.window_months, slot=self.slot, control=self.control,
            min_price=NO_ADJ_FLOOR,
        )

    def as_dict(self) -> dict[str, str]:
        return {
            "window_months": str(self.window_months),
            "slot": f"{self.slot:.4f}",
            "control": self.control,
            "min_printed": f"{self.min_printed:.2f}",
            "min_value": f"{self.min_value:.0f}",
            "trend": "none" if self.trend is None else f"{self.trend[0]}:{self.trend[1]}",
            "price_basis": "printed",
        }


def _check(params: object) -> PrintedDeletionParams:
    if not isinstance(params, PrintedDeletionParams):
        raise TypeError(f"params must be PrintedDeletionParams, got {type(params).__name__}")
    return params


@dataclass(frozen=True, eq=False)
class PrintedPrepared:
    """The parent's prepared exits and history, and the Market for splits and share counts."""

    inner: DeletionPrepared = field(repr=False)
    market: Any = field(default=None, repr=False)  # None on the history-only path or without splits


def passes(h: History, market: Any, symbol: str, data_date: date, p: PrintedDeletionParams) -> bool:
    """The printed close clears ``min_printed`` and, when set, the size on the day clears
    ``min_value``; an unknown printed price or size fails."""
    pc = printed_close(h, market, symbol, data_date)
    if pc is None or pc < p.min_printed:
        return False
    if p.min_value > 0:
        mv = market.market_value(symbol, data_date)
        if mv is None or not (mv >= p.min_value):
            return False
    return True


class PrintedDeletionAllocator:
    """M0495's deletion book and fallen control, floored on the printed price and company size,
    optionally behind the SPY 200-day switch."""

    id = "M0499"
    market_fields = ("shares",)

    def lookback(self, params: Any) -> int:
        p = _check(params)
        n = DELETION.lookback(p.inner)
        return max(n, DV_N, p.trend[1] + 1 if p.trend is not None else 0)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return (IDLE,) if p.trend is None else tuple(sorted({IDLE, p.trend[0]}))

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return (IDLE,)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(
        self, prepared: PrintedPrepared, members: AbstractSet[str], data_date: date,
        p: PrintedDeletionParams,
    ) -> tuple[Target, ...]:
        mk = prepared.market
        prep = prepared.inner
        if mk is None or prep.exits is None:
            return ()
        if not trend_on(prep.history, p.trend, data_date):
            return ()
        q = p.inner
        slots = q.slots
        picks = [
            (s, c) for _, s, c in deletion_pool(prep, members, data_date, q)
            if passes(prep.history[s], mk, s, data_date, p)
        ][:slots]
        if p.control == "losers":
            n = len(picks)
            picks = [
                (s, c) for _, s, c in loser_pool(prep.history, members, data_date, q)
                if passes(prep.history[s], mk, s, data_date, p)
            ][:n]
        slot = Decimal(f"{p.slot:.4f}")
        out: list[Target] = []
        for symbol, close in picks:
            t = target_from_close(symbol, close, slot)
            if t is not None:
                out.append(t)
        rest = Decimal(1) - slot * len(out)
        if rest > 0:
            h = prep.history.get(IDLE)
            i = h.index_of(data_date) if h is not None else None
            if i is not None:
                t = target_from_close(IDLE, float(h.close[i]), rest)
                if t is not None:
                    out.append(t)
        return tuple(out)

    def targets(
        self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
        held: frozenset[str], params: Any,
    ) -> tuple[Target, ...]:
        """The history-only path: no splits and no membership calendar, so no book."""
        return self._run(PrintedPrepared(DeletionPrepared(dict(history))), members, data_date,
                         _check(params))

    def prepare(self, history: Mapping[str, History]) -> PrintedPrepared:
        return PrintedPrepared(DeletionPrepared(dict(history)))

    def prepare_market(self, market: Any) -> PrintedPrepared:
        inner = DELETION.prepare_market(market)
        if not hasattr(market, "shares") or not market.shares.has_splits():
            return PrintedPrepared(inner, None)
        return PrintedPrepared(inner, market)

    def targets_prepared(
        self, prepared: Any, members: AbstractSet[str], data_date: date,
        held: frozenset[str], params: Any,
    ) -> tuple[Target, ...]:
        if not isinstance(prepared, PrintedPrepared):
            raise TypeError(f"prepared must be PrintedPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, _check(params))


PRINTED = PrintedDeletionAllocator()

SWITCH = ("SPY", 200)


def _v(suffix: str, params: PrintedDeletionParams, rationale: str) -> Candidate:
    return Candidate(
        id=f"M0499-{suffix}",
        family="M0499",
        rules=MONTHLY_HOLD_FRAC_GOTRADE,
        allocator=PRINTED,
        params=params,
        rationale=rationale,
        added=ADDED,
        owner_inputs=(),
    )


METHOD = Method(
    id="M0499",
    name=(
        "Dropped from the index, priced as printed: deletions above a real one-dollar floor and a "
        "size floor, behind the market switch, beside fallen members"
    ),
    family="stock-index-deletion-rebound",
    source_kind="variation",
    source_ref="M0495 (parent); M0383/M0387 for the printed price; Faber 2007 for the 200-day switch",
    parent_id="M0495",
    hypothesis=(
        "M0495 held S&P 500 / Nasdaq-100 names dropped in the last six months, 10% each, the rest "
        "in SPY. It beat SPY on both stores, but in 2009-2015 it did no better than a twin that "
        "held as many current members that had simply fallen hardest, and its one-dollar floor "
        "read the split-adjusted close: a name that later reverse-split looked like a $5 stock "
        "while it printed at 51 cents, and 10 such pick-months earned about a third of the lead. "
        "The rebound idea (Chen, Noronha & Singal) was published in 2004, so 2009-2015 is after "
        "the crowd could trade it. This method re-runs the six-month book with the floor on the "
        "printed price (M0383's printed close) and a point-in-time size floor of $500M "
        "(Market.market_value; unknown size excluded, so no stock is held before 1996), and "
        "crosses it with the SPY 200-day switch (all cash at or below the average), each beside "
        "the same fallen-members twin under the same floors. The 2x2 is P6 / PL6 (no switch) and "
        "P6G / PL6G (switch). P6NS drops the size floor to price the printed floor alone against "
        "M0495-D6, and P6S20G is the 20% slot behind the switch, M0495's best-luck arm with the "
        "fall it could not survive. The no-opinion arm for the switch is the pair itself (switch "
        "on vs off); SPY is the residual of every arm. Pre-registered reading: the family is "
        "closed if P6 minus PL6, funded, is under 2 points a year in 2009-2015, or if P6 does not "
        "beat total-return SPY there. Success: a deletion arm beats SPY and its fallen twin over "
        "the whole dev window and in 2009-2015, with a worst fall under the screen."
    ),
    expected_failure=(
        "Most of M0495's 2009-2015 lead over SPY was shared with the fallen-members twin, so the "
        "deletion label probably adds nothing once the sub-dollar pick-months are gone: P6 should "
        "lose most of its lead and tie or trail PL6. The size floor removes the smallest, most "
        "beaten names, which is where a forced-selling rebound would be largest, and it empties "
        "the book before 1996, so P6 may sit close to SPY with a few expensive extra trades and "
        "far too few trades for the lab's screen. The switch should cut the 2008 fall but costs "
        "time out of a rising 2009-2015 market, the lab's most-measured drag. Survivorship runs "
        "against it: deleted companies are the ones that go on to die and the dev store keeps "
        "the survivors."
    ),
    candidates=(
        _v("P6", PrintedDeletionParams(),
           "exits in the last 6 months above $1 printed and $500M size, 10% each, rest SPY"),
        _v("PL6", PrintedDeletionParams(control="losers"),
           "control: as many as P6 holds, current members with the worst 126-day return, same floors"),
        _v("P6G", PrintedDeletionParams(trend=SWITCH),
           "P6 behind the SPY 200-day switch, all cash when SPY is at or below its average"),
        _v("PL6G", PrintedDeletionParams(control="losers", trend=SWITCH),
           "control: PL6 behind the same switch"),
        _v("P6NS", PrintedDeletionParams(min_value=0.0),
           "P6 without the size floor: the printed $1 floor alone, against M0495-D6"),
        _v("P6S20G", PrintedDeletionParams(slot=0.20, trend=SWITCH),
           "P6G at a 20% slot (at most five names), the dose arm"),
    ),
    seen_keys=(
        "concept:index-deletion-rebound-printed-floor",
        "concept:index-deletion-size-floor",
        "concept:index-deletion-behind-switch",
    ),
)

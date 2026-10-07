"""M0012 — A faster crash gate for the residual-momentum book: the 1998-style shock, not the bear market.

Source: variation of M0007 (its N20-RAW variant) on M0020's weekly machinery (W-NOSTOP showed a
weekly re-issue of the monthly basket costs this book nothing: +15.3% vs +15.0% a year).
Idea: the raw-residual top-20 book's worst fall is a fast shock (Jul-Oct 1998) that the SPY 200-day
gate, read once a month, meets late. A gate that is read every week, and that also trips on a
short average or on SPY's own fall from its recent high, should step aside within days of such a
shock and step back in within a week of its end, without giving up the long bull runs.

Mechanics. Rules ``WEEKLY_HOLD``. The basket is M0007-N20-RAW's (raw cumulative residual, F4's
screen, top 20, equal weights) picked on the anchor date (the data date before the first session
of the traded session's month, as in M0020), but WITHOUT M0007's own trend gate: the gate here is
read on ``data_date`` every week instead. When it is off the allocator targets nothing (cash);
when it is on it re-issues the month's basket at fresh closes, so a gate that clears mid-month
buys the basket back at the next weekly check. The gate (all parts must hold, strict):

    * SPY's close on d above its simple average of each length in ``smas``;
    * when ``dd_limit`` is set: SPY's close on d no more than ``dd_limit`` below the highest close
      of the ``dd_n`` sessions through d.

False when SPY has no bar dated d or too little history. Reads only bars dated <= ``data_date``.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import (
    N20_NOTREND,
    RESIDMOM,
    ResidParams,
    ResidPrepared,
)
from seer_engine.lab.methods.m0020_stop_with_weekly_reentry import _refreshed, anchor_date
from seer_engine.sim.book import Target
from seer_engine.sim.rules import WEEKLY_HOLD
from seer_engine.strategies.base import History

ADDED = date(2026, 10, 7)
RAW20_NOGATE = ResidParams(N20_NOTREND, scaled=False)  # M0007-N20-RAW's book minus its own gate


@dataclass(frozen=True, slots=True)
class GateParams:
    inner: ResidParams = RAW20_NOGATE
    smas: tuple[int, ...] = (200,)
    dd_limit: Decimal | None = None  # trip when SPY is more than this far below its dd_n-day high
    dd_n: int = 126
    market: str = "SPY"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, ResidParams):
            raise TypeError(f"inner must be ResidParams, got {type(self.inner).__name__}")
        if self.inner.inner.trend is not None:
            raise ValueError("inner must carry no trend gate: this allocator reads its own gate weekly")
        if not isinstance(self.smas, tuple) or not self.smas:
            raise ValueError(f"smas must be a non-empty tuple, got {self.smas!r}")
        for n in self.smas:
            if isinstance(n, bool) or not isinstance(n, int) or n < 2:
                raise ValueError(f"every sma length must be an int >= 2, got {n!r}")
        if self.dd_limit is not None and (not isinstance(self.dd_limit, Decimal) or not 0 < self.dd_limit < 1):
            raise ValueError(f"dd_limit must be None or a Decimal in (0, 1), got {self.dd_limit!r}")
        if isinstance(self.dd_n, bool) or not isinstance(self.dd_n, int) or self.dd_n < 2:
            raise ValueError(f"dd_n must be an int >= 2, got {self.dd_n!r}")
        if not isinstance(self.market, str) or not self.market:
            raise ValueError(f"market must be a non-empty symbol, got {self.market!r}")

    def as_dict(self) -> dict[str, str]:
        out = {
            "smas": ",".join(str(n) for n in self.smas),
            "dd_limit": "none" if self.dd_limit is None else str(self.dd_limit),
            "dd_n": str(self.dd_n),
            "market": self.market,
        }
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> GateParams:
    if not isinstance(params, GateParams):
        raise TypeError(f"params must be GateParams, got {type(params).__name__}")
    return params


def gate_on(history: Mapping[str, History], data_date: date, p: GateParams) -> bool:
    """The two-speed market gate on ``data_date`` (see the module docstring)."""
    h = history.get(p.market)
    if h is None:
        return False
    i = h.index_of(data_date)
    if i is None:
        return False
    need = max(max(p.smas), p.dd_n if p.dd_limit is not None else 1)
    if i + 1 < need:
        return False
    close = float(h.close[i])
    for n in p.smas:
        if not close > float(h.close[i + 1 - n : i + 1].mean()):
            return False
    if p.dd_limit is not None:
        high = float(h.close[i + 1 - p.dd_n : i + 1].max())
        if not close > high * (1.0 - float(p.dd_limit)):
            return False
    return True


class FastGateAllocator:
    """The month's raw-residual basket while the weekly two-speed gate is on, cash while it is off."""

    id = "M0012"

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return max(RESIDMOM.lookback(p.inner) + 25, max(p.smas) + 1, p.dd_n + 1)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return tuple(sorted({p.market, *RESIDMOM.symbols(p.inner)}))

    def holds(self, params: Any) -> tuple[str, ...]:
        return RESIDMOM.holds(_check(params).inner)

    def uses_members(self, params: Any) -> bool:
        return RESIDMOM.uses_members(_check(params).inner)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if not gate_on(history, data_date, p):
            return ()
        anchor = anchor_date(data_date)
        cut = {s: h.upto(anchor) for s, h in history.items()}
        basket = RESIDMOM.targets(cut, members, anchor, held, p.inner)
        return _refreshed(basket, history, data_date, None)

    def prepare(self, history: Mapping[str, History]) -> ResidPrepared:
        return RESIDMOM.prepare(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, ResidPrepared):
            raise TypeError(f"prepared must be ResidPrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not gate_on(prepared.history, data_date, p):
            return ()
        basket = RESIDMOM.targets_prepared(prepared, members, anchor_date(data_date), held, p.inner)
        return _refreshed(basket, prepared.history, data_date, None)


FASTGATE = FastGateAllocator()


def _v(suffix: str, params: GateParams, rationale: str, rules=WEEKLY_HOLD) -> Candidate:
    return Candidate(id=f"M0012-{suffix}", family="M0012", rules=rules, allocator=FASTGATE,
                     params=params, rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0012",
    name="A faster crash gate for the residual-momentum book: the 1998-style shock, not the bear market",
    family="stock-residual-momentum",
    source_kind="variation",
    source_ref="M0007 (M0007-N20-RAW); M0020 (M0020-W-NOSTOP, the weekly re-issue machinery)",
    parent_id="M0007",
    hypothesis=(
        "M0007-N20-RAW (+15.0% a year, 19.6% max DD) and its weekly twin M0020-W-NOSTOP (+15.3%, "
        "19.3%) keep their 200-day SPY gate flat through 2001, 2002 and 2008, so their deepest fall "
        "is a fast shock (Jul-Oct 1998) that the 200-day average, read monthly, reacts to late. "
        "Reading the gate weekly and adding a faster leg - SPY above its 100-day average as "
        "well, or SPY within 8% of its six-month high - should step out within days of such a shock "
        "and back in within a week of its end. Expected: the worst fall drops to about 13-16% "
        "while return stays near +13-14% a year (well above SPY TR's +7.9%), MAR rises above the "
        "parent's 0.77, and the steadier curve lifts the luck score. W-SMA200 (weekly 200-day only) "
        "prices the weekly reading by itself."
    ),
    expected_failure=(
        "A fast leg trips on every 5-8% pullback, and most pullbacks in 1996-97, 2004-07 and "
        "2010-15 snap back: the book sells near the low and rebuys a week or more later, higher, "
        "so whipsaw costs several points of return a year and trades jump. Worse, the binding "
        "fall may not be a market fall at all: a momentum-specific crash with SPY still rising "
        "(the March-May 2000 tech reversal, or 2009's junk rally) is invisible to any SPY gate, so "
        "the worst fall stays near 18-19% while return falls toward +11-12%."
    ),
    candidates=(
        _v("W-SMA200", GateParams(smas=(200,)),
           "The parent's 200-day gate read weekly, with mid-month re-entry: prices the weekly reading alone"),
        _v("W-SMA200-100", GateParams(smas=(200, 100)),
           "Invested only while SPY is above both its 200-day and 100-day averages, read weekly"),
        _v("W-SMA200-DD8", GateParams(smas=(200,), dd_limit=Decimal("0.08"), dd_n=126),
           "200-day gate plus a drawdown trip: out while SPY is more than 8% below its 6-month high"),
    ),
    seen_keys=(
        "concept:residual-momentum-fast-market-gate",
        "concept:two-speed-trend-gate",
    ),
)

"""M0491 — The twenty most traded index members behind the 200-day switch: the stocks, or the switch?

Source: variation of M0490 (its no-opinion control arm ``M0490-CTRL-GATE``); reserved by Sera batch
20261106-1411. The switch is Faber's 2007 200-day rule; "the most traded names" is not a published
anomaly, it is the parent's placeholder for "no opinion".

Why it exists. M0490 tested a residual-reversal picker and lost to its own control: the twenty
index members with the largest 20-day dollar volume, equal weight, monthly, all cash while SPY
closes at or below its 200-day average. That control is the lab's best-looking arm of the batch
and nobody designed it. Two readings fit its record. (1) The most traded big companies are a real
pick: heavy trading marks the market's leaders of the moment (Cisco and Intel in 1999, Apple and
Exxon in 2012) and the book rides them. (2) The pick is nothing and the record is the switch: any
twenty liquid names behind the same switch, or SPY itself behind it, would have done as well,
because the switch sat out 2008. The parent cannot tell these apart because it has no arm that
keeps the switch and removes the pick. This method adds those arms and nothing else.

The arms, all on ``monthly-hold-frac-gotrade`` (fractional shares, Gotrade's real fees, asked
monthly), all behind the same switch ``trend=("SPY", 200)``:

* ``EW-SW``: the parent's control rebuilt verbatim under this allocator id: F4's screen (20-day
  mean close x volume over $20M, close at least $5, 253 bars of history), the 20 largest by
  dollar volume (ties by symbol), equal slots. Replicates ``M0490-CTRL-GATE``; a mismatch with
  the parent's record says the store moved, not the idea.
* ``CAP-SW``: the same ranking, held in proportion to company size instead of equal slots. Only
  names with a known market value (``Market.market_value``) can be held; one share class per
  company (identical share count; the class with the larger dollar volume stays, the dedupe
  older size-weighted methods use); the 20 most traded of those; weights by market value with a
  10% ceiling, water-filled (M0034's ``_apply_ceiling``; M0047 says a size-weighted book needs a
  ceiling). Asks whether the parent's equal slots were betting against SPY's big-company drift.
* ``DRAW1-SW``, ``DRAW2-SW``, ``DRAW3-SW``: the blind control. Twenty names drawn from the SAME
  screened pool (every member passing F4's screen that day, mostly the whole index) by the lab's
  matched draw (``control_draw.matched_book``, rule matched-draw-v1): each month it counts how
  many names ``EW-SW``'s ranking enters, keeps all but that many of its own names in a date-free
  hash order and draws the rest in a month-keyed hash order. Equal slots. Three seeds because one
  draw is not a control (insight on M0440: nineteen draws span 7.5 pts/yr).
* ``SPY-SW``: SPY itself, 100%, behind the same switch. The cleanest "is it only the switch"
  arm: it removes every stock and keeps every exit. It will trade far fewer than 100 times and is
  never a strategy; it is the yardstick for the arms above.

Assumptions written before any result. The parent's always-invested twin (``M0490-CTRL-ALWAYS``,
same screen and ranking with ``trend=None``) is already recorded on this chassis, so it is not
re-run here; the slot it would take goes to the SPY-behind-the-switch arm, which the parent lacks
and which answers the question directly. The cap arm holds cash before share counts exist (1996)
and skips unsized names, so its twenty can differ from ``EW-SW``'s twenty by a few names; that is
part of the price of sizing, not a bug. The draw arms share ``EW-SW``'s switch reading, so a
switch flip moves all of them at once and they pay the same exit and re-entry fees. GOOG/GOOGL
before 2014 can appear twice in ``EW-SW`` and the draws, exactly as in the parent; only the cap
arm dedupes, because only the cap arm weights by size.

Market-aware (``market_fields = ("shares",)``): ``lab run`` refuses it on a store without share
counts, and by the lab's contract for market-aware allocators every arm targets nothing on the
history-only path, so all six arms always run on the same store and the same code path.
Pure: reads only bars and share counts dated <= ``data_date``.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab import control_draw
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0034_size_tilt_residual import _apply_ceiling, _floor_weight
from seer_engine.sim.book import Target, equal_weight, to_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    FactorParams,
    FactorPrepared,
    FactorRow,
    factor_lookback,
    factor_rows,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 11, 6)
ARMS = ("equal", "cap", "draw", "spy")
DRAW_TAG = "M0491"


@dataclass(frozen=True, slots=True)
class LeadersParams:
    """``arm`` equal / cap / draw / spy; ``top`` names held; ``cap`` the per-name ceiling (cap arm
    only); ``seed`` the draw's hash seed (draw arm only); ``trend`` the switch, set by every arm."""

    arm: str
    top: int = 20
    cap: float | None = None
    seed: int = 0
    trend: tuple[str, int] | None = ("SPY", 200)

    def __post_init__(self) -> None:
        if self.arm not in ARMS:
            raise ValueError(f"arm must be one of {ARMS}, got {self.arm!r}")
        if isinstance(self.top, bool) or not isinstance(self.top, int) or not 1 <= self.top <= 100:
            raise ValueError(f"top must be an int in [1, 100], got {self.top!r}")
        if (self.cap is not None) != (self.arm == "cap"):
            raise ValueError("cap is set on the cap arm and only there")
        if self.cap is not None and not 1.0 / self.top <= float(self.cap) <= 1.0:
            raise ValueError(f"cap must lie in [1/top, 1], got {self.cap}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise ValueError(f"seed must be a non-negative int, got {self.seed!r}")
        if (self.seed != 0) != (self.arm == "draw"):
            raise ValueError("seed is set on the draw arm and only there")
        self.inner  # validates the switch

    @property
    def inner(self) -> FactorParams:
        """F4's screen and switch, exactly as the parent's control read them."""
        return FactorParams(rank="momentum", top=self.top, trend=self.trend)

    def as_dict(self) -> dict[str, str]:
        return {"arm": self.arm, "top": str(self.top),
                "cap": "none" if self.cap is None else repr(float(self.cap)),
                "seed": str(self.seed),
                "trend": "none" if self.trend is None else f"{self.trend[0]}:{self.trend[1]}",
                "rank": "dollar-volume-20", "class_rule": "identical-share-count"}


def _check(params: object) -> LeadersParams:
    if not isinstance(params, LeadersParams):
        raise TypeError(f"params must be LeadersParams, got {type(params).__name__}")
    return params


@dataclass(frozen=True, slots=True, eq=False)
class LeadersPrepared:
    history: Mapping[str, History]
    factor: FactorPrepared | None  # None on the plain history path: rows are computed directly
    market: Any  # the Market (share counts), or None when there is none


def _rows(prep: LeadersPrepared, members: AbstractSet[str], d: date, p: LeadersParams) -> list[FactorRow]:
    if prep.factor is not None:
        return prep.factor.rows_on(members, d, p.inner)
    return factor_rows(prep.history, members, d, p.inner)


def most_traded(rows: list[FactorRow], top: int) -> list[FactorRow]:
    """The parent control's ranking: largest 20-day dollar volume first, ties by symbol."""
    return sorted(rows, key=lambda r: (-r.dollar_volume, r.symbol))[:top]


def _cap_book(prep: LeadersPrepared, rows: list[FactorRow], d: date,
              p: LeadersParams) -> list[tuple[str, float, Decimal | None]]:
    """The most traded sized names, one class per company, weighted by market value under the ceiling."""
    mk = prep.market
    if mk is None:
        return []
    by_count: dict[float, tuple[float, str, float, float]] = {}
    for r in rows:
        v = mk.market_value(r.symbol, d)
        n = mk.shares_on(r.symbol, d)
        if v is None or n is None or not (np.isfinite(v) and v > 0.0):
            continue
        seen = by_count.get(n)
        if seen is None or (r.dollar_volume, r.symbol) > (seen[0], seen[1]):
            by_count[n] = (r.dollar_volume, r.symbol, float(v), r.close)
    picks = sorted(by_count.values(), key=lambda x: (-x[0], x[1]))[: p.top]
    if not picks:
        return []
    w = np.array([x[2] for x in picks], dtype=np.float64)
    w = _apply_ceiling(w / float(w.sum()), max(float(p.cap), 1.0 / len(picks)))
    return [(x[1], x[3], _floor_weight(float(wi))) for x, wi in zip(picks, w, strict=True)]


def _run(prep: LeadersPrepared, members: AbstractSet[str], d: date, held: frozenset[str],
         p: LeadersParams) -> tuple[Target, ...]:
    if prep.market is None:  # the lab's market-aware contract: no panel, no targets, on every arm
        return ()
    if not trend_on(prep.history, d, p.inner):
        return ()
    if p.arm == "spy":
        t = target_from_close("SPY", last_close(prep.history.get("SPY"), d), to_weight(1.0))
        return () if t is None else (t,)
    rows = _rows(prep, members, d, p)
    if not rows:
        return ()
    picks: list[tuple[str, float, Decimal | None]]
    if p.arm == "equal":
        w = equal_weight(p.top)
        picks = [(r.symbol, r.close, w) for r in most_traded(rows, p.top)]
    elif p.arm == "cap":
        picks = _cap_book(prep, rows, d, p)
    else:
        close = {r.symbol: r.close for r in rows}

        def select(at: date) -> tuple[list[str], list[str]]:
            pool = rows if at == d else _rows(prep, members, at, p)
            return [r.symbol for r in pool], [r.symbol for r in most_traded(pool, p.top)]

        names = control_draw.matched_book(select, d, held, tag=DRAW_TAG, seed=p.seed)
        w = equal_weight(p.top)
        picks = [(s, close[s], w) for s in names]
    out: list[Target] = []
    for s, c, w in picks:
        if w is None:
            continue
        t = target_from_close(s, c, w)
        if t is not None:
            out.append(t)
    return tuple(out)


class LiquidLeadersAllocator:
    """The 20 most traded screened index members (equal or size-weighted), a matched blind draw of
    20 from the same pool, or SPY itself; all cash while SPY closes at or below its 200-day
    average. Held names are not consulted except by the draw, which keeps its own names."""

    id = "M0491"
    market_fields = ("shares",)

    def lookback(self, params: Any) -> int:
        p = _check(params)
        inner = factor_lookback(p.inner)
        return control_draw.lookback_for(inner) if p.arm == "draw" else inner

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return ("SPY",) if p.trend is None else tuple(sorted({"SPY", p.trend[0]}))

    def holds(self, params: Any) -> tuple[str, ...]:
        return ("SPY",) if _check(params).arm == "spy" else ()

    def uses_members(self, params: Any) -> bool:
        return _check(params).arm != "spy"

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no share counts, so no arm targets anything (the contract)."""
        return _run(LeadersPrepared(history, None, None), members, data_date, held, _check(params))

    def prepare(self, history: Mapping[str, History]) -> LeadersPrepared:
        return LeadersPrepared(history, None, None)

    def prepare_market(self, market: Any) -> LeadersPrepared:
        sized = hasattr(market, "market_value") and len(market.shares) > 0
        return LeadersPrepared(market.history, prepare_factor(market.history), market if sized else None)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, LeadersPrepared):
            raise TypeError(f"prepared must be LeadersPrepared, got {type(prepared).__name__}")
        return _run(prepared, members, data_date, held, _check(params))


LEADERS = LiquidLeadersAllocator()


def _v(suffix: str, params: LeadersParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0491-{suffix}", family="M0491", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=LEADERS, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0491",
    name="Hold the 20 most traded big stocks behind the 200-day switch, sized three ways",
    family="stock-liquid-leaders-switch",
    source_kind="variation",
    source_ref="M0490 (its no-opinion control, M0490-CTRL-GATE); Faber 2007 for the 200-day switch",
    parent_id="M0490",
    hypothesis=(
        "M0490's no-opinion arm -- the 20 most traded index members, equal weight, monthly, behind "
        "the SPY 200-day switch, fractional at Gotrade fees -- beat SPY on deposits over the dev "
        "window but missed the luck bar and won only 1 of 4 walk-forward folds, the 2006-2008 one. "
        "If the most traded names are a real pick (heavy trading marks the market's leaders of the "
        "moment), then the equal-weight and the size-weighted books both beat all three matched "
        "blind draws of 20 names from the same screened pool behind the same switch, and both beat "
        "SPY-behind-the-switch, by more than the draws' own spread, and in 2009-2015 as well as "
        "over the whole window. Sizing by company value should cut the 2009-2015 shortfall against "
        "SPY's big-company drift without giving up the 2008 exit."
    ),
    expected_failure=(
        "It is the switch, not the stocks. The equal-weight book lands inside the blind draws' "
        "spread, SPY-behind-the-switch matches or beats it, and every arm lags SPY in 2009-2015, "
        "when the switch paid false-alarm exits and had no crash to dodge. The size-weighted book "
        "tracks SPY-behind-the-switch closely (the most traded names are mostly the biggest), so "
        "it inherits the switch's record rather than adding to it. The dev-window edge was earned "
        "in 2008, one episode, which is why the parent won one fold of four."
    ),
    candidates=(
        _v("EW-SW", LeadersParams("equal"),
           "The parent's control rebuilt: 20 most traded members, equal weight, behind the switch"),
        _v("CAP-SW", LeadersParams("cap", cap=0.10),
           "The same 20 most traded names held by company size, 10% ceiling, behind the switch"),
        _v("DRAW1-SW", LeadersParams("draw", seed=1),
           "Control: 20 names drawn blind from the same screened pool at EW-SW's churn, seed 1"),
        _v("DRAW2-SW", LeadersParams("draw", seed=2),
           "Control: 20 names drawn blind from the same screened pool at EW-SW's churn, seed 2"),
        _v("DRAW3-SW", LeadersParams("draw", seed=3),
           "Control: 20 names drawn blind from the same screened pool at EW-SW's churn, seed 3"),
        _v("SPY-SW", LeadersParams("spy"),
           "Control: SPY itself behind the same switch; every exit kept, every stock removed"),
    ),
    seen_keys=(
        "concept:most-traded-leaders-behind-switch",
        "concept:switch-only-yardstick-spy-behind-200d",
    ),
)

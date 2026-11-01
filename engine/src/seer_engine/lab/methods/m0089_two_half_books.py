"""M0089 — Two half-books a fortnight apart: the 12-month momentum book split into tranches.

Source: variation of M0086's host (F4-MOM12-N20-TREND, the plain 12-1 momentum book, measured
unchanged there); Hoffstein, Faber & Braun (2019/2020), "Rebalance timing luck: the (dumb) luck of
smart beta" and Blitz's tranching notes. Published 2019-2020, so the dev window predates it.

Idea. The host re-picks and checks its SPY-200 switch on one day a month. Its worst falls (1998,
2011) land between two such checks, so a month's timing decides whether the book was already in
cash. Splitting the money into K equal tranches, each re-picking its own 20 names and checking the
switch on its own day, spread across the month, means the whole book can no longer miss a switch
by the same margin. Names are not traded more often than the host (each tranche trades once a
month), but a name held by two tranches carries two slices of weight.

Schedule. The rank cadence is weekly, so the allocator is called on each week's data date ``d``
(the last session before the week). Month ends are data dates too (the last session of a month,
before the first session of the next, which is exactly the monthly host's decision date). A tranche
with offset ``o`` weeks re-picks on the ``o``-th week-end data date after the month end that opens
its cycle (``o = 0``: the month end itself). K=2 uses offsets (0, 2), K=4 uses (0, 1, 2, 3). The
allocator is pure: on any ``d`` it recomputes each tranche's latest pick date from the calendar
and the SPY history, then the basket and the gate as of that date. Between a tranche's pick dates
its target is fixed, so the weekly decision only trades when some tranche has re-picked. Held
names that left the index in between drop out of the target (members as of ``d``), a small
departure from "hold to the next pick" that the host does not have.

Arms (all fractional, at Gotrade's real fees, 20 names per tranche, equal slices):
    * HOST: K=1 on the monthly rules, the exact host (``tranches=(0,)`` reduces to F4's pick at ``d``);
    * ONE-W: K=1 on the weekly rules, the control for the weekly harness (no tranching, no opinion);
    * TWO / FOUR: tranches of picks, each tranche's gate checked on its own pick date;
    * TWO-GATE / FOUR-GATE: one monthly basket (the month-end pick), but each tranche's slice
      is gated on its own date. This splits the effect into "the switch is checked more often, in
      slices" (gate only) and "the picks are staggered too" (full tranches).
"""

from __future__ import annotations

import functools
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from decimal import ROUND_DOWN, Decimal
from typing import Any

from seer_engine import dates
from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20
from seer_engine.sim.book import WEIGHT_QUANTUM, Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorParams,
    FactorPrepared,
    FactorRow,
    factor_lookback,
    factor_rows,
    prepare_factor,
    rank_rows,
    trend_on,
)

ADDED = date(2026, 11, 1)
PICK_REACH = 60  # sessions a pick date can sit behind the decision's data date
WEEKLY_HOLD_FRAC_GOTRADE = replace(
    MONTHLY_HOLD_FRAC_GOTRADE, id="weekly-hold-frac-gotrade", cadence="weekly"
)


@dataclass(frozen=True, slots=True)
class TrancheParams:
    """``inner`` is the host; ``offsets`` are the tranches' week offsets after the month end."""

    inner: FactorParams
    offsets: tuple[int, ...] = (0,)
    gate_only: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if self.inner.rank != "momentum" or self.inner.sizing != "equal":
            raise ValueError("the host is the equal-weight momentum book")
        if (not isinstance(self.offsets, tuple) or not self.offsets
                or any(isinstance(o, bool) or not isinstance(o, int) or not 0 <= o <= 3
                       for o in self.offsets)
                or len(set(self.offsets)) != len(self.offsets)):
            raise ValueError(f"offsets must be distinct ints in 0..3, got {self.offsets!r}")
        if not isinstance(self.gate_only, bool):
            raise TypeError(f"gate_only must be a bool, got {type(self.gate_only).__name__}")

    def as_dict(self) -> dict[str, str]:
        out = {"offsets": ",".join(str(o) for o in self.offsets),
               "gate_only": str(self.gate_only).lower()}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> TrancheParams:
    if not isinstance(params, TrancheParams):
        raise TypeError(f"params must be TrancheParams, got {type(params).__name__}")
    return params


@functools.lru_cache(maxsize=4096)
def _cycles(d: date) -> tuple[date, tuple[date, ...], date, tuple[date, ...]]:
    """``(E0, weeks after E0 up to d, E1, weeks after E1 up to E0)``, from the calendar only.

    ``E0`` is the latest month-end data date on or before ``d`` (the last session of a month,
    the day before the monthly host decides), ``E1`` the one before it; a week-end data date is a
    session whose next session falls in another ISO week. No price is read.
    """
    span = dates.sessions(d - timedelta(days=100), d)
    ends = [s for s in span if dates.next_session(s).month != s.month]
    weeks = [s for s in span if dates.next_session(s).isocalendar()[:2] != s.isocalendar()[:2]]
    e0 = ends[-1] if ends else d
    e1 = ends[-2] if len(ends) > 1 else e0
    return (e0, tuple(s for s in weeks if e0 < s <= d), e1, tuple(s for s in weeks if e1 < s <= e0))


def pick_date(d: date, offset: int) -> date:
    """The latest pick date on or before ``d`` for a tranche ``offset`` weeks after a month end.

    Offset 0 is the month end itself. Otherwise the ``offset``-th week-end data date after the
    latest month end if that has arrived by ``d``, else the same slot of the month before (capped
    at that month's end when the month had too few weeks).
    """
    e0, w0, _e1, w1 = _cycles(d)
    if offset == 0:
        return e0
    if len(w0) >= offset:
        return w0[offset - 1]
    return w1[offset - 1] if len(w1) >= offset else e0


@dataclass
class TranchePrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared | None = field(repr=False)
    top_cache: dict[tuple[date, frozenset[str]], tuple[FactorRow, ...]] = field(
        default_factory=dict, repr=False)


class TrancheMomentum:
    """F4's momentum book run as K staggered tranches, each re-picking and gating on its own day."""

    id = "M0089"
    market_fields: tuple[str, ...] = ()

    def lookback(self, params: Any) -> int:
        # A tranche's pick date is up to a month and a half back (last cycle's third week-end).
        return factor_lookback(_check(params).inner) + PICK_REACH

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return () if p.inner.trend is None else (p.inner.trend[0],)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _basket(self, prepared: TranchePrepared, members: AbstractSet[str], on: date,
                p: TrancheParams) -> tuple[FactorRow, ...]:
        key = (on, frozenset(members))
        hit = prepared.top_cache.get(key)
        if hit is not None:
            return hit
        if prepared.factor is None:
            rows = factor_rows(prepared.history, members, on, p.inner)
        else:
            rows = prepared.factor.rows_on(members, on, p.inner)
        top = tuple(rank_rows([r for r in rows if r.symbol not in EXCLUDED], p.inner))
        if len(prepared.top_cache) > 64:
            prepared.top_cache.clear()
        prepared.top_cache[key] = top
        return top

    def _run(self, prepared: TranchePrepared, members: AbstractSet[str], data_date: date,
             held: AbstractSet[str], p: TrancheParams) -> tuple[Target, ...]:
        k = len(p.offsets)
        slice_w = (Decimal(1) / Decimal(k) / Decimal(p.inner.top)).quantize(
            WEIGHT_QUANTUM, rounding=ROUND_DOWN)
        weight: dict[str, Decimal] = {}
        order: dict[str, int] = {}
        for o in p.offsets:
            on = pick_date(data_date, o)
            if not trend_on(prepared.history, on, p.inner):
                continue
            basket_on = pick_date(data_date, 0) if p.gate_only else on
            for rank, row in enumerate(self._basket(prepared, members, basket_on, p)):
                weight[row.symbol] = weight.get(row.symbol, Decimal(0)) + slice_w
                order.setdefault(row.symbol, rank)
        out: list[Target] = []
        for sym in sorted(weight, key=lambda s: (-weight[s], order[s], s)):
            # The price is today's: a pick made on an earlier tranche date is bought at the next open
            # from the latest close, and a name with no bar today can only be one already held.
            h = prepared.history.get(sym)
            if h is None or (h.index_of(data_date) is None and sym not in held):
                continue
            c = last_close(h, data_date)
            t = None if c is None else target_from_close(sym, c, min(weight[sym], Decimal(1)))
            if t is not None:
                out.append(t)
        return tuple(out)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self._run(TranchePrepared(history, None), members, data_date, held, _check(params))

    def prepare(self, history: Mapping[str, History]) -> TranchePrepared:
        return TranchePrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, TranchePrepared):
            raise TypeError(f"prepared must be TranchePrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params))


TRANCHES = TrancheMomentum()


def _v(suffix: str, params: TrancheParams, rules: Any, rationale: str) -> Candidate:
    return Candidate(id=f"M0089-{suffix}", family="M0089", rules=rules, allocator=TRANCHES,
                     params=params, rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0089",
    name="Two half-books a fortnight apart: the 12-month momentum book split into two tranches that re-pick on alternate halves of the month",
    family="p7a-f4",
    source_kind="variation",
    source_ref=(
        "variation of M0086's host F4-MOM12-N20-TREND; Hoffstein, Faber & Braun (2019), Rebalance "
        "timing luck: the (dumb) luck of smart beta (SSRN 3474099)"
    ),
    parent_id="M0086",
    hypothesis=(
        "Published 2019-2020, after the whole dev window, so the idea is not crowded out in dev. The "
        "plain 12-month momentum book (F4-MOM12-N20-TREND, 20 names, 5% each, cash while SPY is at or "
        "below its 200-day average, checked monthly) beats SPY by about six points a year on dev but "
        "falls 23% at its worst, over the 20% limit, because the 1998 and 2011 crashes land between "
        "monthly checks of the switch; a weekly switch costs 3-5 points a year (M0076/M0078). "
        "Splitting the money into K equal tranches that each re-pick their own 20 names and check the "
        "switch on their own day, spread across the month, means the whole book can no longer miss a "
        "switch by the same margin, at no more trades per name (each tranche trades once a month). "
        "Variants: HOST (K=1 on monthly rules, the exact host); ONE-W (K=1 on weekly rules, the "
        "control for the weekly decision harness: no tranching, no opinion changed); TWO (offsets 0 "
        "and 2 weeks after the month end); FOUR (offsets 0-3); TWO-GATE and FOUR-GATE (one monthly "
        "basket, but each slice gated on its own date: separates a more-often-checked switch from "
        "staggered picks). All fractional at Gotrade's real fees. A definite yes: TWO or FOUR keeps "
        "within a point of ONE-W's CAGR and brings the worst fall under 20%, with 2009-2015 not worse. "
        "A definite no: the worst fall moves less than a point from ONE-W, or CAGR falls more than "
        "two points."
    ),
    expected_failure=(
        "Tranching cuts timing luck but not the size of a fast crash: the 1998 and 2011 falls are "
        "days long, and a half-book that misses the switch loses what the full book would have lost "
        "on the missed half, so the worst fall may only move from 23% to 21%. The mid-month tranche "
        "also ranks on a stale 12-1 signal two weeks older, and a name held by two tranches carries "
        "two slices, so the book is slightly more concentrated. The host's other weakness carries "
        "over: it lags SPY in 2009-2015 when big-company growth led, and tranching does nothing "
        "about that. The weekly harness may add a few trades (trims of drifted names) that the "
        "monthly host does not; ONE-W is there to show how many."
    ),
    candidates=(
        _v("HOST", TrancheParams(N20, (0,)), MONTHLY_HOLD_FRAC_GOTRADE,
           "The plain 12-month momentum book on monthly rules at real fees (the host, K=1)"),
        _v("ONE-W", TrancheParams(N20, (0,)), WEEKLY_HOLD_FRAC_GOTRADE,
           "The same book on the weekly decision harness: the control for tranching's plumbing"),
        _v("TWO", TrancheParams(N20, (0, 2)), WEEKLY_HOLD_FRAC_GOTRADE,
           "Two half-books, picks and gate two weeks apart"),
        _v("FOUR", TrancheParams(N20, (0, 1, 2, 3)), WEEKLY_HOLD_FRAC_GOTRADE,
           "Four quarter-books, picks and gate a week apart"),
        _v("TWO-GATE", TrancheParams(N20, (0, 2), gate_only=True), WEEKLY_HOLD_FRAC_GOTRADE,
           "One monthly basket, each half gated on its own date (two weeks apart)"),
        _v("FOUR-GATE", TrancheParams(N20, (0, 1, 2, 3), gate_only=True), WEEKLY_HOLD_FRAC_GOTRADE,
           "One monthly basket, each quarter gated on its own date (a week apart)"),
    ),
    seen_keys=(
        "concept:tranche-rebalance-timing",
        "concept:rebalance-timing-luck",
        "concept:staggered-momentum-tranches",
    ),
)

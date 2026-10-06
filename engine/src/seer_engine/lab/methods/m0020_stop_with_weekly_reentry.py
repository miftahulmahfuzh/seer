"""M0020 — Stopped-out stocks may come back at the next weekly check.

Source: variation of M0019 (per-stock protective stops on residual momentum), queued by its
analysis as the one remaining try for per-stock stops in this family.
Idea: M0019's stops sold near the bottom of basket-wide falls and then sat in cash until the next
monthly re-pick, missing the rebound, so the stops cost return without cutting the worst fall. If
the book checks once a week and buys a stopped-out stock back while it is still in this month's
basket, a stop costs at most a week of the rebound instead of a month.

Mechanics. The rules are ``WEEKLY_HOLD`` (a decision every week, held positions re-weighted to
target at the open when off by at least 1% of equity). The allocator keeps the parent's MONTHLY
choice: on every weekly decision it re-issues the basket the inner book picked on the anchor date,
the data date before the first session of the traded session's month (the parent's own monthly
decision date), with the same weights. Only the price is refreshed to the close on ``data_date``
(the open-limit sizing price and the stop are computed from it). So between monthly re-picks the
basket and its weights never change; what the weekly check adds is (a) a stock stopped out since
the last check is bought back with a fresh stop 20% below the latest close, and (b) the weekly
re-weighting toward equal weight. Variant W-NOSTOP runs the same weekly machinery with no stop, to
price (b) alone. Reads only bars dated <= ``data_date`` (the anchor is on or before it); index
membership is the one passed for ``data_date``.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from seer_engine import dates
from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import RESIDMOM, ResidParams, ResidPrepared
from seer_engine.lab.methods.m0011_raw_residual_own_vol import RAW20, RESIDVOL, ResidVolParams
from seer_engine.lab.methods.m0019_momentum_protective_stop import TV14_N21, with_stops
from seer_engine.sim.book import Target
from seer_engine.sim.rules import WEEKLY_HOLD
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History

ADDED = date(2026, 10, 7)


@dataclass(frozen=True, slots=True)
class ReentryParams:
    inner: ResidParams | ResidVolParams
    stop_pct: Decimal | None = Decimal("0.20")  # None: no stop (the weekly-machinery control)

    def __post_init__(self) -> None:
        if not isinstance(self.inner, (ResidParams, ResidVolParams)):
            raise TypeError(f"inner must be ResidParams or ResidVolParams, got {type(self.inner).__name__}")
        if self.stop_pct is not None and (not isinstance(self.stop_pct, Decimal) or not (0 < self.stop_pct < 1)):
            raise ValueError(f"stop_pct must be None or a Decimal in (0, 1), got {self.stop_pct!r}")

    def as_dict(self) -> dict[str, str]:
        out = {
            "stop_pct": "none" if self.stop_pct is None else str(self.stop_pct),
            "inner_kind": type(self.inner).__name__,
        }
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> ReentryParams:
    if not isinstance(params, ReentryParams):
        raise TypeError(f"params must be ReentryParams, got {type(params).__name__}")
    return params


def _inner_alloc(p: ReentryParams) -> Any:
    return RESIDVOL if isinstance(p.inner, ResidVolParams) else RESIDMOM


def anchor_date(data_date: date) -> date:
    """The data date of this month's decision: the session before the first session of the month
    that ``next_session(data_date)`` falls in. Never after ``data_date``."""
    first = dates.next_session(data_date)
    while dates.prev_session(first).month == first.month and dates.prev_session(first).year == first.year:
        first = dates.prev_session(first)
    return dates.prev_session(first)


def _refreshed(basket: tuple[Target, ...], history: Mapping[str, History], data_date: date,
               stop_pct: Decimal | None) -> tuple[Target, ...]:
    """The anchor basket with every price refreshed to the latest close on or before ``data_date``
    (same weights), each with a stop ``stop_pct`` below that close when ``stop_pct`` is set."""
    out: list[Target] = []
    for t in basket:
        h = history.get(t.symbol)
        close = None if h is None else last_close(h, data_date)
        if close is None:
            continue
        fresh = target_from_close(t.symbol, close, t.weight)
        if fresh is not None:
            out.append(fresh)
    refreshed = tuple(out)
    return refreshed if stop_pct is None else with_stops(refreshed, stop_pct)


class WeeklyReentryAllocator:
    """The inner book's monthly basket, re-issued every week at fresh prices (with fresh stops)."""

    id = "M0020"

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return _inner_alloc(p).lookback(p.inner) + 25  # the anchor can sit up to ~23 sessions back

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return _inner_alloc(p).symbols(p.inner)

    def holds(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return _inner_alloc(p).holds(p.inner)

    def uses_members(self, params: Any) -> bool:
        p = _check(params)
        return _inner_alloc(p).uses_members(p.inner)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        anchor = anchor_date(data_date)
        cut = {s: h.upto(anchor) for s, h in history.items()}
        basket = _inner_alloc(p).targets(cut, members, anchor, held, p.inner)
        return _refreshed(basket, history, data_date, p.stop_pct)

    def prepare(self, history: Mapping[str, History]) -> ResidPrepared:
        return RESIDMOM.prepare(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, ResidPrepared):
            raise TypeError(f"prepared must be ResidPrepared, got {type(prepared).__name__}")
        p = _check(params)
        anchor = anchor_date(data_date)
        basket = _inner_alloc(p).targets_prepared(prepared, members, anchor, held, p.inner)
        return _refreshed(basket, prepared.history, data_date, p.stop_pct)


REENTRY = WeeklyReentryAllocator()


def _v(suffix: str, params: ReentryParams, rationale: str, rules=WEEKLY_HOLD) -> Candidate:
    return Candidate(id=f"M0020-{suffix}", family="M0020", rules=rules, allocator=REENTRY,
                     params=params, rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0020",
    name="Stopped-out stocks may come back at the next weekly check",
    family="stock-momentum-risk-managed",
    source_kind="variation",
    source_ref="M0019 (M0019-RAW20-S20, M0019-TV14N21-S20); its analysis queued this as the last try",
    parent_id="M0019",
    hypothesis=(
        "M0019's 20% stop on the unbraked residual book worsened the worst fall (20.3% vs 19.6%) "
        "because a stopped stock waited up to a month in cash and missed the snap-back. Letting it "
        "come back at the next weekly check while still in this month's basket should recover most "
        "of that rebound: on the unbraked book the worst fall should land below the no-stop "
        "parent's 19.6% with return near its +15% a year, and on the braked book below 14.1% with "
        "return near +10.8% and a higher luck score than M0019's 0.873. W-NOSTOP prices the weekly "
        "re-weighting alone and should sit close to the monthly parent."
    ),
    expected_failure=(
        "Basket-wide falls last longer than a week: a stock bought back after a week is still "
        "falling, gets stopped again below the new stop, and the book pays two round trips per "
        "fall, so the stop variants end with more trades, lower gains vs losses and a worst fall "
        "no better than M0019's. The weekly re-weighting toward equal weight also trims momentum's "
        "winners every week, costing return even without stops (W-NOSTOP below the parent)."
    ),
    candidates=(
        _v("W-NOSTOP", ReentryParams(RAW20, None),
           "Unbraked monthly basket re-issued weekly, no stop: prices the weekly re-weighting alone"),
        _v("W-S20", ReentryParams(RAW20, Decimal("0.20")),
           "Same with a 20% stop and weekly re-entry: M0019-RAW20-S20 with the re-entry fix"),
        _v("W-TV14N21-S20", ReentryParams(TV14_N21, Decimal("0.20")),
           "The braked book (M0011's best) with a 20% stop and weekly re-entry"),
    ),
    seen_keys=(
        "concept:per-stock-stop-weekly-reentry",
    ),
)

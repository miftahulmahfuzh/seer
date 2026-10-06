"""M0019 — Momentum with a wide protective stop under each stock (a resting Stop Sell per holding).

Source: variation of M0011 (and its parent M0007-N20-RAW); the owner's question of 2026-10-07
whether a hold-for-months method can carry an automatic safety exit. Gotrade takes a standalone
Stop Sell in fractional shares (owner-verified 2026-10-07), so a per-stock stop is executable.
Idea: the residual-momentum book (M0007-N20-RAW: +15.0% a year, 19.6% worst fall) fails only the
15% drawdown limit. M0013 showed a brake on the WHOLE basket sells at the bottom of momentum's
sharp rebounds. A stop on each SINGLE stock, set wide (15-25% below the price it was bought
near), never fires on ordinary wobbles but sells a name that collapses on its own news instead of
holding it for up to a month until the next re-rank.

The allocator takes the inner book's targets unchanged (M0007's residual-momentum targets, or
M0011's volatility-braked ones) and gives every target a stop at ``stop_pct`` below its last close
on ``data_date``. The book engine fixes a position's stop at entry (``sim.book``): a held stock
keeps the stop it was bought with through later re-weights, exactly like a resting Stop Sell
placed once after the buy. A stopped-out stock stays out until the next monthly re-rank picks it
again (with a new stop). The stop fills at the stop price when the day's low touches it, or at the
open when the stock gaps below it.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import RESIDMOM, ResidParams, ResidPrepared
from seer_engine.lab.methods.m0011_raw_residual_own_vol import RAW20, RESIDVOL, ResidVolParams
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD
from seer_engine.strategies.base import History

ADDED = date(2026, 10, 7)
_PRICE = Decimal("0.0001")


@dataclass(frozen=True, slots=True)
class StopParams:
    inner: ResidParams | ResidVolParams
    stop_pct: Decimal = Decimal("0.20")

    def __post_init__(self) -> None:
        if not isinstance(self.inner, (ResidParams, ResidVolParams)):
            raise TypeError(f"inner must be ResidParams or ResidVolParams, got {type(self.inner).__name__}")
        if not isinstance(self.stop_pct, Decimal) or not (0 < self.stop_pct < 1):
            raise ValueError(f"stop_pct must be a Decimal in (0, 1), got {self.stop_pct!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"stop_pct": str(self.stop_pct), "inner_kind": type(self.inner).__name__}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> StopParams:
    if not isinstance(params, StopParams):
        raise TypeError(f"params must be StopParams, got {type(params).__name__}")
    return params


def _inner_alloc(p: StopParams) -> Any:
    return RESIDVOL if isinstance(p.inner, ResidVolParams) else RESIDMOM


def with_stops(targets: tuple[Target, ...], stop_pct: Decimal) -> tuple[Target, ...]:
    """Every target with a stop ``stop_pct`` below its last close (4 dp, half-up)."""
    out: list[Target] = []
    for t in targets:
        stop = (t.last * (1 - stop_pct)).quantize(_PRICE, rounding=ROUND_HALF_UP)
        out.append(replace(t, stop=stop) if stop > 0 else t)
    return tuple(out)


class ProtectiveStopAllocator:
    """The inner residual-momentum book's targets, each with a wide stop below its last close."""

    id = "M0019"

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return _inner_alloc(p).lookback(p.inner)

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
        inner = _inner_alloc(p).targets(history, members, data_date, held, p.inner)
        return with_stops(inner, p.stop_pct)

    def prepare(self, history: Mapping[str, History]) -> ResidPrepared:
        return RESIDMOM.prepare(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, ResidPrepared):
            raise TypeError(f"prepared must be ResidPrepared, got {type(prepared).__name__}")
        p = _check(params)
        inner = _inner_alloc(p).targets_prepared(prepared, members, data_date, held, p.inner)
        return with_stops(inner, p.stop_pct)


PROTSTOP = ProtectiveStopAllocator()
TV14_N21 = ResidVolParams(RAW20, Decimal("0.14"), 21)  # M0011-RAW20-TV14-N21's params, verbatim


def _v(suffix: str, params: StopParams, rationale: str, rules=MONTHLY_HOLD) -> Candidate:
    return Candidate(id=f"M0019-{suffix}", family="M0019", rules=rules, allocator=PROTSTOP,
                     params=params, rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0019",
    name="Momentum with a wide protective stop under each stock (a resting Stop Sell per holding)",
    family="stock-momentum-risk-managed",
    source_kind="variation",
    source_ref="M0011 (M0011-RAW20-TV14-N21) and M0007 (M0007-N20-RAW); owner question 2026-10-07",
    parent_id="M0011",
    hypothesis=(
        "The unbraked residual-momentum book (M0007-N20-RAW: +15.0% CAGR, 19.6% max DD, PF 2.16) "
        "fails only max DD, and M0011's volatility brake fixed DD (14.1%) at the price of 4 CAGR "
        "points. A wide stop on each stock, measured from the close before it was bought, should "
        "cut the single-name collapses that feed the worst fall while leaving ordinary momentum "
        "wobbles alone: on the unbraked book a 20% stop should land max DD near 15-16% with CAGR "
        "near +13%, i.e. more return per point of fall than the brake. On the braked M0011 book a "
        "20% stop should keep DD under 15% and add Sharpe by trimming its worst single-name losses, "
        "nudging DSR toward 0.95."
    ),
    expected_failure=(
        "The worst falls are basket-wide (Aug 1998, the 2000-02 momentum crash, 2009's junk rally), "
        "when every stock drops together: the stops fire on the same days, often on gap-down opens "
        "below the stop, and the book sits out the rebound until the next monthly re-rank. Then the "
        "stop costs return without cutting max DD (as M0013's basket brake did), the 15% stop "
        "whipsaws most, and DSR falls as N rises by four."
    ),
    candidates=(
        _v("RAW20-S15", StopParams(RAW20, Decimal("0.15")),
           "Unbraked top-20 residual book, stop 15% below the buy-day close: tightest, most whipsaw"),
        _v("RAW20-S20", StopParams(RAW20, Decimal("0.20")),
           "Same with a 20% stop: the centre of the hypothesis"),
        _v("RAW20-S25", StopParams(RAW20, Decimal("0.25")),
           "Same with a 25% stop: fires only on outright collapses"),
        _v("TV14N21-S20", StopParams(TV14_N21, Decimal("0.20")),
           "M0011's best braked book (TV14, one-month swing reading) plus a 20% stop"),
    ),
    seen_keys=(
        "concept:per-stock-protective-stop-momentum",
    ),
)

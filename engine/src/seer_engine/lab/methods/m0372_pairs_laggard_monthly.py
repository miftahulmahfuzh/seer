"""M0372 — Same chassis, same pace, laggard pick: a controlled check of whether M0068's edge is
the pick or just the data build and pace.

Source: variation of M0064. Gatev, Goetzmann & Rouwenhorst (2006), Pairs trading: performance of
a relative-value arbitrage rule, Rev. Financial Studies 19(3), doi:10.1093/rfs/hhj020.

Idea: M0068 (hold the leg that ran ahead of its pair partner, monthly, on a current price-history
build) beat its laggard-side twin M0064 (hold the lagging leg, weekly, on an older price-history
build) in four of five matched variants, but that comparison crossed three things at once: the
pick (leader vs laggard), the pace (weekly vs monthly), and the data build (M0068 ran roughly two
weeks after M0064, on a larger store). This method holds M0064's original pick — the laggard — but
on M0068's exact chassis: the monthly rules preset, run today on the same current price-history
build M0068 used. Pick is now the only thing left to vary between this method and M0068; pace and
build are matched. If this book lands close to M0068's numbers, the earlier leader-beats-laggard
reading was mostly the pace or the data build, not the stock pick. If it lands close to M0064's
original, clearly worse numbers, the leader-side pick is more likely doing real work.

Reuses M0064's chassis unmodified: the same ``PairsParams``, the same pair-formation and gap
state machine, the same ``open_legs`` (the laggard side) and the same ``build_targets``. The only
change from M0068's file is which pick function is called — ``open_legs`` (laggard) here instead
of ``open_legs_leader`` — and the allocator's own id, so the lab's kin tracking does not conflate
this engine with M0064's or M0068's.

Reads only grid columns dated <= data_date.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from datetime import date
from decimal import Decimal
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import (
    N20,
    N20_NOTREND,
    ResidPrepared,
    ReturnGrid,
    build_grid,
)
from seer_engine.lab.methods.m0064_pairs_laggard import (
    PairsParams,
    build_targets,
    open_legs,
    pairs_lookback,
)
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import factor_rows, prepare_factor, trend_on

ADDED = date(2026, 10, 26)


def _check(params: object) -> PairsParams:
    if not isinstance(params, PairsParams):
        raise TypeError(f"params must be PairsParams, got {type(params).__name__}")
    return params


# --------------------------------------------------------------------------- the allocator


class PairsLaggardMonthlyAllocator:
    """The laggard of every open pair, the rest in SPY (or cash), behind F4's gate, monthly.

    Identical to M0064's ``PairsLaggardAllocator`` except for its id: it is tracked as its own
    engine so the hard gate's kin rule does not conflate this run with M0064's weekly book or
    M0068's leader pick.
    """

    id = "M0372"

    def lookback(self, params: Any) -> int:
        return pairs_lookback(_check(params))

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        fixed = {p.market}
        if p.inner.trend is not None:
            fixed.add(p.inner.trend[0])
        return tuple(sorted(fixed))

    def holds(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return (p.market,) if p.park == "spy" else ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _targets(self, history: Mapping[str, History], rows, grid: ReturnGrid | None,
                 data_date: date, params: PairsParams) -> tuple[Any, ...]:
        if grid is None:
            return ()
        legs = open_legs(grid, [r.symbol for r in rows], data_date, params)
        return build_targets(rows, legs, history, data_date, params)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Any, ...]:
        p = _check(params)
        if not trend_on(history, data_date, p.inner):
            return ()
        rows = factor_rows(history, members, data_date, p.inner)
        return self._targets(history, rows, build_grid(history, p.market), data_date, p)

    def prepare(self, history: Mapping[str, History]) -> ResidPrepared:
        return ResidPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Any, ...]:
        if not isinstance(prepared, ResidPrepared):
            raise TypeError(f"prepared must be ResidPrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        rows = prepared.factor.rows_on(members, data_date, p.inner)
        return self._targets(prepared.history, rows, prepared.grid(p.market), data_date, p)


LAGGARD_MONTHLY = PairsLaggardMonthlyAllocator()


def _v(suffix: str, params: PairsParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0372-{suffix}", family="M0372", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=LAGGARD_MONTHLY, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0372",
    name=(
        "Same chassis, same pace, laggard pick: a controlled check of whether M0068's edge is "
        "the pick or just the data build and pace"
    ),
    family="stock-pairs-relative-value",
    source_kind="variation",
    source_ref="M0064",
    parent_id="M0064",
    hypothesis=(
        "M0068 (holding the leg that ran ahead of its pair partner, monthly, on the current "
        "price-history build) beat its laggard-side twin M0064 (weekly, an older price-history "
        "build) in four of five matched variants, but that comparison crosses both a data-build "
        "change and a pace change, so it cannot say whether picking the leader instead of the "
        "laggard is itself responsible. This method holds the laggard — M0064's original pick — "
        "on M0068's exact chassis and monthly cadence, so it runs on the same current "
        "price-history build as M0068 and isolates the pick from the pace and the data build. "
        "Each month, among F4's screened point-in-time members, pairs are formed on the 252 "
        "sessions before the current half-year Gatev trading period and the laggard of each open "
        "pair is held equal weight, rest in SPY, monthly 200-day gate, fractional shares at "
        "Gotrade's real fees. Same five matched variants as M0064 and M0068: P20, P50, P50-CASH, "
        "P50-K15, P50-NOGATE. If this monthly, same-build laggard book lands close to M0068's "
        "numbers, the earlier leader-beats-laggard reading was mostly the data build or the pace, "
        "not the stock pick. If it lands close to M0064's original, clearly worse numbers, the "
        "leader-side pick is more likely doing real work. Success for the comparison: a clear gap "
        "either way between this method's numbers and M0068's, read variant by matched variant."
    ),
    expected_failure=(
        "The laggard likely still lags on the current build and the monthly cadence just as it "
        "did weekly on the older one, so this method lands close to M0064's original numbers "
        "(beats SPY by little or not at all, fails the drawdown bar) while M0068 keeps its "
        "separate, better numbers — confirming the pick, not the pace or the build, was doing the "
        "work in the earlier leader-vs-laggard comparison. A messier possible outcome: moving to "
        "the current, larger price-history build and the monthly cadence alone (independent of "
        "which side is picked) changes the numbers enough that this method also lands closer to "
        "M0068 than M0064 did, in which case the pace or the build, not the pick, explains most of "
        "the earlier gap and the P50-NOGATE pair here (gate on vs off) only partially separates "
        "that from the pick itself. Either way, held laggards are a handful of names with the rest "
        "in SPY, so Gotrade's monthly fees and SPY resize may erase whatever difference remains."
    ),
    candidates=(
        _v("P20", PairsParams(N20, pairs=20),
           "Gatev's 20 closest pairs, open at 2 sigmas, 4-sigma stop, 40-session limit, "
           "laggard held, rest in SPY, monthly — matches M0068-P20 except for the pick"),
        _v("P50", PairsParams(N20, pairs=50),
           "50 closest pairs: more legs open, more of the book in the laggards"),
        _v("P50-CASH", PairsParams(N20, pairs=50, park="cash"),
           "P50 with the rest in cash: the laggards alone, measured against SPY"),
        _v("P50-K15", PairsParams(N20, pairs=50, entry=Decimal("1.5")),
           "P50 opening at 1.5 sigmas: more, smaller divergences"),
        _v("P50-NOGATE", PairsParams(N20_NOTREND, pairs=50),
           "P50 with no SPY 200-day gate: what the gate is worth on this pick, pace and build"),
    ),
    seen_keys=(
        "concept:pairs-trading",
        "concept:distance-method-pairs",
        "concept:relative-value-arbitrage",
        "concept:pairs-laggard-same-chassis-as-leader",
        "doi:10.1093/rfs/hhj020",
    ),
)

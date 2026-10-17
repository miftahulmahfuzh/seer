"""M0178 — The low-correlation book among the 200 most-traded members, with its control kept.

Source: variation of M0174 (Asness, Frazzini, Gormsen & Pedersen 2020, "Betting against
correlation", JFE 135(3)).
Idea: M0174's quarterly low-correlation book (ranked inside volatility terciles, behind the SPY
200-day switch) beat SPY on dev, but two things weakened it: on the survivorship-check store its
2009-2015 lead turned negative, and its walk-forward selection kept preferring the
high-correlation control. This method asks one new question: does the edge survive where the
missing dead companies matter least, among the 200 most heavily traded screened members? Big,
busy names rarely vanish from the data, and they are closer to the companies SPY is weighted in.

The pool. On a re-pick date d, F4's screen ($5 / $20M) gives the eligible members; of those, the
200 with the highest 20-day mean close x volume on d (ties by symbol) are the pool. The pool is
re-read at every re-pick, so a holding that drops out of the 200 is scored as unwanted and sold at
the next quarter end. Correlation, volatility, the tercile split, the 40% keep band, the quarterly
clock, unfilled slots in SPY and the switch are M0174's own functions, unchanged. In the 1990s the
screened members barely exceed 200, so the pool binds mostly from the 2000s on.

The control stays. Sera's caution (journalled on this method before it ran): dropping M0174's
control after the folds preferred it would win the folds by construction. So the high-correlation
book in the same pool is registered beside the idea, and the fold selection can still pick it.

Rules are ``monthly-hold-frac-gotrade``: fractional shares at Gotrade's real fees, asked monthly.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0174_betting_against_correlation import (
    CorrParams,
    CorrPrepared,
    choose,
)
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    FactorParams,
    FactorRow,
    factor_lookback,
    factor_rows,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 10, 17)


@dataclass(frozen=True, slots=True)
class BusyCorrParams:
    """``corr`` is M0174's book unchanged; ``pool`` the number of most-traded screened members it
    may choose from."""

    corr: CorrParams
    pool: int = 200

    def __post_init__(self) -> None:
        if not isinstance(self.corr, CorrParams):
            raise TypeError(f"corr must be CorrParams, got {type(self.corr).__name__}")
        if isinstance(self.pool, bool) or not isinstance(self.pool, int):
            raise TypeError(f"pool must be an int, got {type(self.pool).__name__}")
        if self.pool < self.corr.inner.top:
            raise ValueError(f"pool must be >= top, got pool={self.pool} top={self.corr.inner.top}")

    def as_dict(self) -> dict[str, str]:
        out = {"pool": str(self.pool)}
        for k, v in self.corr.as_dict().items():
            out[f"corr.{k}"] = v
        return out


def _check(params: object) -> BusyCorrParams:
    if not isinstance(params, BusyCorrParams):
        raise TypeError(f"params must be BusyCorrParams, got {type(params).__name__}")
    return params


def busiest(rows: list[FactorRow], pool: int) -> list[FactorRow]:
    """The ``pool`` rows with the highest dollar volume, back in symbol order."""
    top = sorted(rows, key=lambda r: (-r.dollar_volume, r.symbol))[:pool]
    return sorted(top, key=lambda r: r.symbol)


class BusyCorrAllocator:
    """M0174's low-correlation book, choosing only among the most-traded screened members."""

    id = "M0178"

    def lookback(self, params: Any) -> int:
        # As M0174: the screen's and the switch's need; an unscoreable member's slot holds SPY.
        return factor_lookback(_check(params).corr.inner)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params).corr
        fixed = {p.market}
        if p.inner.trend is not None:
            fixed.add(p.inner.trend[0])
        return tuple(sorted(fixed))

    def holds(self, params: Any) -> tuple[str, ...]:
        return (_check(params).corr.market,)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(self, prepared: CorrPrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: BusyCorrParams) -> tuple[Target, ...]:
        c = p.corr
        if not trend_on(prepared.history, data_date, c.inner):
            return ()
        if prepared.factor is None:
            rows = factor_rows(prepared.history, members, data_date, c.inner)
        else:
            rows = prepared.factor.rows_on(members, data_date, c.inner)
        return choose(prepared.history, members, busiest(rows, p.pool), data_date, held, c)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self._run(CorrPrepared(history, None), members, data_date, held, _check(params))

    def prepare(self, history: Mapping[str, History]) -> CorrPrepared:
        return CorrPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, CorrPrepared):
            raise TypeError(f"prepared must be CorrPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params))


BUSY_CORR = BusyCorrAllocator()

SW = ("SPY", 200)


def _p(top: int, high: bool = False) -> BusyCorrParams:
    # the rank is unused: only F4's screen, book size and switch
    return BusyCorrParams(CorrParams(FactorParams(rank="momentum", top=top, trend=SW), high=high))


def _v(suffix: str, params: BusyCorrParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0178-{suffix}", family="M0178", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=BUSY_CORR, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0178",
    name=(
        "The low-correlation book among the 200 most-traded members, with its "
        "high-correlation control kept"
    ),
    family="stock-low-correlation",
    source_kind="variation",
    source_ref="variation of M0174 (Asness, Frazzini, Gormsen & Pedersen 2020, JFE 135(3))",
    parent_id="M0174",
    hypothesis=(
        "M0174's 40-name low-correlation book (correlation with SPY from 3 years of overlapping "
        "3-day returns, ranked inside 1-year volatility terciles, quarterly, 40% keep band, behind "
        "the SPY 200-day switch) beat SPY on dev (+12.0% a year funded vs +7.2%, worst fall 24%, "
        "DSR 0.98) but its 2009-2015 lead turned from +0.5 to -1.3 points a year on the "
        "survivorship-check store, and the fold selection preferred its high-correlation control. "
        "The paper was circulated 2017, published 2020, so the dev window predates it, though "
        "betting against beta was public from 2010. Restrict the choice to the 200 screened "
        "members with the highest 20-day dollar volume on each re-pick date, where dead companies "
        "missing from the store should matter least and the book sits closer to SPY's big-company "
        "shape. Variants (all behind the switch, fractional at Gotrade's real fees on the owner's "
        "deposits): L30-SW and L40-SW (the idea at 30 and 40 names) and H40-SW (control: the 40 "
        "highest-correlation names in the same pool, same band; kept on Sera's instruction so the "
        "fold selection can still pick against the idea). M0174-C40-SW is reported beside it. "
        "Success: L40-SW or L30-SW beats total-return SPY with worst fall <= 25% and PF >= 1.3, "
        "the method's picks win a majority of walk-forward folds, H40-SW trails clearly, and the "
        "2009-2015 lead is positive on both the dev and the survivorship-check store."
    ),
    expected_failure=(
        "The busiest members are the market-tied ones (banks, tech, big industrials), so inside "
        "this pool the least-correlated names are mostly big utilities, staples, drug makers and "
        "oil, a defensive sector book that trails the 2009-2015 rise and loses the fold selection "
        "to the control again, exactly as M0174 did. Narrowing the pool also shrinks the spread "
        "between low and high correlation, so whatever premium M0174 showed partly came from "
        "the thinner members this pool drops, and the edge falls toward zero. If the 2009-2015 "
        "lead stays negative on the check store, the direction stops."
    ),
    candidates=(
        _v("L30-SW", _p(30),
           "The 30 lowest-correlation names inside their volatility tercile, among the 200 most-traded members"),
        _v("L40-SW", _p(40),
           "The 40-name rung of the same book among the 200 most-traded members"),
        _v("H40-SW", _p(40, high=True),
           "Control: the 40 highest-correlation names in the same pool, same band and switch"),
    ),
    seen_keys=(
        "concept:betting-against-correlation",
        "concept:low-market-correlation",
        "concept:liquid-pool-low-correlation",
    ),
)

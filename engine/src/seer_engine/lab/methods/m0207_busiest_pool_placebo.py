"""M0207 — The placebo book drawn only from the busiest members: does random picking among the giants land on SPY?

Source: variation of M0198 (the size-weighted placebo), reserved by Sera batch 20261017-1858. Not
a strategy. A yardstick that asks where the frame's lead lives once the equal slots are cleared.

Why it exists. M0187 filled the 20-slot quarterly frame in a meaningless hash order and still beat
SPY over 1996-2015 by as much as four real rankings. M0198 then kept those exact picks and sized
them by trading value: it cost under a point a year, so the equal slots are not the lead. The next
suspect is the pool. M0187 picks from any screened member (anything over $5 with $20M of daily
trading value), and most of those are mid-sized companies SPY barely holds. SPY's money sits in
the hundred-odd giants. This method keeps M0187's frame byte for byte and narrows only the pool:
on each date the screened members are cut to the ``pool`` with the highest 60-session average
trading value (close times volume, the size stand-in M0198 used), and M0187's own ``choose`` --
hash, three-year eligibility, 40% keep band, quarterly re-picks, unfilled slots in SPY, optional
switch -- runs on that cut. A held name that drops out of the busiest ``pool`` reads as outside the
band at the next re-pick and is replaced; between re-picks the pool is not consulted, exactly as
M0187 ignores its scores between re-picks.

Reading. If random picks among the giants land on SPY (within a point a year, beta near 1.0), the
frame's lead was "pick from the whole index", a lean toward mid-sized companies plus the dead
companies the dev store cannot price (M0198's cross-check put that at about 1.6 points a year). If
they keep a two-point lead, something in the screen and the quarterly holding itself is worth
naming. The ``pool=50`` variant is a dose check: a narrower pool should sit closer to SPY still.

Assumptions (written before any result): the pool is ranked among members that already pass F4's
screen, so it is "the busiest screened members", which for a 100-name cut is the same set in all
but thin years; trading value is busy-ness as well as size, so a stock in the news briefly joins
the pool (M0198 made the same trade-off); ties in trading value break by symbol.

Pure: the hash is a function of its inputs and the pool reads only bars dated <= ``data_date``.
Every variant sets ``trend`` explicitly (the ``FactorParams`` default is the SPY 200-day switch).

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
from seer_engine.lab.methods.m0179_coskewness import CoskewPrepared
from seer_engine.lab.methods.m0187_placebo_hash_order import PlaceboAllocator, PlaceboParams, choose
from seer_engine.lab.methods.m0198_size_weighted_placebo import trading_value
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import FactorParams, FactorRow, factor_lookback, factor_rows, trend_on

ADDED = date(2026, 10, 17)


@dataclass(frozen=True, slots=True)
class BusiestPoolParams:
    """M0187's placebo (``placebo``) drawn from the ``pool`` screened members with the highest
    ``dv_n``-session average trading value."""

    placebo: PlaceboParams
    pool: int = 100
    dv_n: int = 60

    def __post_init__(self) -> None:
        if not isinstance(self.placebo, PlaceboParams):
            raise TypeError(f"placebo must be PlaceboParams, got {type(self.placebo).__name__}")
        for name in ("pool", "dv_n"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int) or v < 1:
                raise ValueError(f"{name} must be a positive int, got {v!r}")
        if self.pool < self.placebo.inner.top:
            raise ValueError(f"pool must hold at least top={self.placebo.inner.top} names, got {self.pool}")

    def as_dict(self) -> dict[str, str]:
        out = {"pool": str(self.pool), "dv_n": str(self.dv_n), "pool_rank": "trading-value"}
        for k, v in self.placebo.as_dict().items():
            out[f"placebo.{k}"] = v
        return out


def _check(params: object) -> BusiestPoolParams:
    if not isinstance(params, BusiestPoolParams):
        raise TypeError(f"params must be BusiestPoolParams, got {type(params).__name__}")
    return params


def busiest(history: Mapping[str, History], rows: list[FactorRow], data_date: date,
            p: BusiestPoolParams) -> list[FactorRow]:
    """The ``pool`` rows with the highest trading value on ``data_date``, in the input's order."""
    if len(rows) <= p.pool:
        return rows
    dv = {r.symbol: trading_value(history[r.symbol], data_date, p.dv_n) for r in rows}
    keep = {s for _, s in sorted((-v, s) for s, v in dv.items())[: p.pool]}
    return [r for r in rows if r.symbol in keep]


class BusiestPoolAllocator(PlaceboAllocator):
    """M0187's hash-order frame on the busiest ``pool`` screened members."""

    id = "M0207"

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return max(factor_lookback(p.placebo.inner), p.dv_n)

    def symbols(self, params: Any) -> tuple[str, ...]:
        return super().symbols(_check(params).placebo)

    def holds(self, params: Any) -> tuple[str, ...]:
        return super().holds(_check(params).placebo)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _pooled(self, prepared: CoskewPrepared, members: AbstractSet[str], data_date: date,
                held: frozenset[str], p: BusiestPoolParams) -> tuple[Target, ...]:
        q = p.placebo
        if not trend_on(prepared.history, data_date, q.inner):
            return ()
        if prepared.factor is None:
            rows = factor_rows(prepared.history, members, data_date, q.inner)
        else:
            rows = prepared.factor.rows_on(members, data_date, q.inner)
        return choose(prepared.history, members, busiest(prepared.history, rows, data_date, p),
                      data_date, held, q)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self._pooled(CoskewPrepared(history, None), members, data_date, held, _check(params))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, CoskewPrepared):
            raise TypeError(f"prepared must be CoskewPrepared, got {type(prepared).__name__}")
        return self._pooled(prepared, members, data_date, held, _check(params))


BUSIEST = BusiestPoolAllocator()

SW = ("SPY", 200)


def _screen(top: int, trend: tuple[str, int] | None) -> FactorParams:
    return FactorParams(rank="momentum", top=top, trend=trend)  # the rank is unused: only the screen


def _pooled(seed: int, trend: tuple[str, int] | None = None, pool: int = 100) -> BusiestPoolParams:
    return BusiestPoolParams(PlaceboParams(_screen(20, trend), seed=seed), pool=pool)


def _v(suffix: str, params: BusiestPoolParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0207-{suffix}", family="M0207", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=BUSIEST, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0207",
    name="The meaningless-order book drawn only from the 100 busiest members: does random picking among the giants land on SPY?",
    family="placebo-hash-order",
    source_kind="variation",
    source_ref="variation of M0198 (the size-weighted placebo); reserved by Sera batch 20261017-1858",
    parent_id="M0198",
    hypothesis=(
        "Sizing the scrambled picks by trading value cost under a point a year (M0198), so the "
        "frame's lead is not the equal slots. The next suspect is the pool: picking from any "
        "screened member rather than from the big names that dominate SPY. Keep M0187's scramble, "
        "band, quarterly re-picks and SPY slots, but restrict the pool on each date to the 100 "
        "screened members with the highest 60-session trading value; 20 names, equal slots, seeds "
        "1-3 with no switch (trend explicitly None), seed 1 behind the SPY 200-day switch, and seed "
        "1 on a 50-name pool as a dose check; fractional at Gotrade's real fees on the owner's "
        "deposits. Expected: the unswitched seeds land within about a point a year of SPY's funded "
        "+7.2% (against M0187's +8.8-11.9%) with beta near 1.0, and the 50-name pool closer still; "
        "then the frame's lead was 'pick from the whole index' plus the missing dead companies. "
        "If they keep a two-point lead, the screen and quarterly holding are worth naming. The "
        "survivorship-check store is read beside the dev one. Not a published anomaly; evidence "
        "only, never to be promoted."
    ),
    expected_failure=(
        "Three ways this reads badly. (1) Twenty random names out of 100 giants is still a 20-name "
        "book: in 1999-2000 the busiest names were the bubble stocks (Cisco, Lucent, Worldcom), so "
        "a seed that drew them may crash harder than SPY and the seed spread may be too wide to "
        "say 'lands on SPY' or not. (2) Equal slots among giants still lean toward the smaller "
        "giants compared with SPY's weights, so a residual point of lead could be that lean, not "
        "the screen. (3) Membership in the pool churns with trading value, so held names drop out "
        "and the book trades more than M0187, paying Gotrade's fees for it. Expect unswitched "
        "worst falls near 50% in 2008 and the switched seed to trail SPY in 2009-2015."
    ),
    candidates=(
        _v("B1", _pooled(1), "Hash order, seed 1, from the 100 busiest screened members, no switch"),
        _v("B2", _pooled(2), "Hash order, seed 2, from the 100 busiest screened members, no switch"),
        _v("B3", _pooled(3), "Hash order, seed 3, from the 100 busiest screened members, no switch"),
        _v("B1-SW", _pooled(1, SW),
           "Hash order, seed 1, 100 busiest, behind the SPY 200-day switch"),
        _v("P50-1", _pooled(1, pool=50),
           "Dose check: hash order, seed 1, from the 50 busiest screened members, no switch"),
    ),
    seen_keys=(
        "concept:busiest-pool-placebo",
        "concept:pool-vs-weighting-test",
    ),
)

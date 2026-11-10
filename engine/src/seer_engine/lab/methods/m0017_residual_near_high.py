"""M0017 — residual momentum, only among stocks near their 52-week high.

Source: variation on M0015 (George & Hwang 2004, J. Finance 59(5), published long before the
dev window ends, so the crowd had it by 2015) and M0007-N20-RAW's residual-momentum engine.
Idea: M0015 found that nearness to the 52-week high is a good brake (worst fall 15.6-18.0%) but
a poor engine (+8.0-9.7% a year against SPY's +7.9%), and its only blend averaged the two ranks.
Here nearness is an eligibility filter and not a rank: the residual-momentum ranking is
untouched, but a name must close within ``floor`` of its 252-session max close to be considered.
The momentum-crash literature blames winners far below their highs (rebounders off a crash
low); this keeps the residual engine and drops exactly those names.

On data date d, with F4's screen, SPY 200-day gate, monthly rebalance and equal weights:

    * nearness = close[d] / max(close over the 252 sessions ending at d);
    * eligible = names whose nearness >= floor AND that have a raw residual-momentum score;
    * held = the ``top`` highest scores among the eligible (fewer if fewer qualify; the rest
      stays cash, which is part of what the filter does).

``floor`` 0.0 admits everyone, so that arm IS M0007-N20-RAW's book at Gotrade fees: the arm with
no opinion in it, registered so the filter's worth can be priced against the same book never
filtering (it is expected to record as a book twin of M0032-N20-RAW-FRAC-GT, which is fine).
Every arm trades fractional shares at Gotrade's real fees.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import (
    ResidParams,
    ResidPrepared,
    build_grid,
    resid_lookback,
    residual_scores,
    targets_from_scores,
)
from seer_engine.lab.methods.m0015_52week_high import HIGH_N, _near_map, nearness  # noqa: F401
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    FactorParams,
    factor_lookback,
    factor_rows,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 11, 10)


@dataclass(frozen=True, slots=True)
class NearResidParams:
    """``inner`` is F4's screen, gate, book size and weighting; ``floor`` the nearness bar."""

    inner: FactorParams
    floor: float = 0.90
    high_n: int = HIGH_N
    market: str = "SPY"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if isinstance(self.floor, bool) or not isinstance(self.floor, float) or not (
            0.0 <= self.floor < 1.0
        ):
            raise ValueError(f"floor must be a float in [0, 1), got {self.floor!r}")
        if isinstance(self.high_n, bool) or not isinstance(self.high_n, int) or self.high_n < 20:
            raise ValueError(f"high_n must be an int >= 20, got {self.high_n!r}")
        if not isinstance(self.market, str) or not self.market:
            raise ValueError(f"market must be a non-empty symbol, got {self.market!r}")

    def resid(self) -> ResidParams:
        """M0007-N20-RAW's model: unscaled cumulative residual."""
        return ResidParams(self.inner, scaled=False, market=self.market)

    def as_dict(self) -> dict[str, str]:
        out = {"floor": repr(self.floor), "high_n": str(self.high_n), "market": self.market}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> NearResidParams:
    if not isinstance(params, NearResidParams):
        raise TypeError(f"params must be NearResidParams, got {type(params).__name__}")
    return params


class NearResidAllocator:
    """Residual momentum's top set, restricted to names near their 52-week high."""

    id = "M0017"

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return max(factor_lookback(p.inner), p.high_n, resid_lookback(p.resid()))

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        out = {p.market}
        if p.inner.trend is not None:
            out.add(p.inner.trend[0])
        return tuple(sorted(out))

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _pick(self, history, rows, grid, data_date, p) -> tuple[Target, ...]:
        scores = residual_scores(grid, [r.symbol for r in rows], data_date, p.resid())
        if p.floor > 0.0:
            near = _near_map(history, rows, data_date, p.high_n)
            scores = {s: v for s, v in scores.items() if near.get(s, -1.0) >= p.floor}
        return targets_from_scores(rows, scores, p.resid())

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if not trend_on(history, data_date, p.inner):
            return ()
        rows = factor_rows(history, members, data_date, p.inner)
        if not rows:
            return ()
        grid = build_grid(history, p.market)
        if grid is None:
            return ()
        return self._pick(history, rows, grid, data_date, p)

    def prepare(self, history: Mapping[str, History]) -> ResidPrepared:
        return ResidPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, ResidPrepared):
            raise TypeError(f"prepared must be ResidPrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        rows = prepared.factor.rows_on(members, data_date, p.inner)
        if not rows:
            return ()
        grid = prepared.grid(p.market)
        if grid is None:
            return ()
        return self._pick(prepared.history, rows, grid, data_date, p)


NEARRESID = NearResidAllocator()

TREND = ("SPY", 200)
N20 = FactorParams(rank="momentum", top=20, trend=TREND)
N30 = FactorParams(rank="momentum", top=30, trend=TREND)


def _v(suffix: str, params: NearResidParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0017-{suffix}", family="M0017", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=NEARRESID, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0017",
    name="Residual momentum, only among stocks near their 52-week high",
    family="stock-52week-high",
    source_kind="variation",
    source_ref="M0015 (George & Hwang 2004) filter applied to M0007-N20-RAW's residual rank",
    parent_id="M0015",
    hypothesis=(
        "M0015 showed nearness to the 52-week high cuts drawdown (15.6-18.0%) but is a weak "
        "ranking key (+8-9.7% CAGR). Used as an eligibility filter on M0007-N20-RAW's raw "
        "residual-momentum rank (top-20/30, same F4 screen, SPY-200 gate, monthly, fractional "
        "shares at Gotrade fees), requiring close >= 0.85 or 0.90 of the 252-day max close, it "
        "keeps the residual engine and excludes far-below-high rebounders that momentum-crash "
        "work blames. George-Hwang was published in 2004, so the dev years can show an edge "
        "the crowd has since traded away. Expect worst fall near 15% at CAGR >= 12%. Kill if "
        "worst fall is not below 16.8% (M0015-N20-BLEND) or CAGR falls below 11%. The H00 arm "
        "(floor 0, no filter) is M0007-N20-RAW's book at real fees, the no-opinion control that "
        "prices the filter; it is expected to record as a book twin of M0032-N20-RAW-FRAC-GT."
    ),
    expected_failure=(
        "The filter removes the rebounders but also cash-drags: in calm bull years few names "
        "qualify rarely, but after a sell-off (spring 2009, 2011) almost none do, so the book "
        "sits in cash through the recovery and loses return without a safer fall, since the SPY-200 "
        "gate already handles crashes. Residual-ranked winners are mostly near their highs "
        "anyway, so the filter may barely bite and arms may repeat the control's curve."
    ),
    candidates=(
        _v("N20-H90", NearResidParams(N20, floor=0.90),
           "Top-20 residual rank among names within 10% of their 252-day high"),
        _v("N20-H85", NearResidParams(N20, floor=0.85),
           "Top-20 residual rank among names within 15% of their 252-day high (looser bar)"),
        _v("N30-H90", NearResidParams(N30, floor=0.90),
           "Top-30 with the 0.90 bar: breadth, so the filter can leave more names to choose from"),
        _v("N20-H00", NearResidParams(N20, floor=0.0),
           "Control with no opinion: no filter, M0007-N20-RAW's book at real fees"),
    ),
    seen_keys=(
        "concept:residual-momentum-near-high-filter",
        "concept:nearness-to-high-as-eligibility-filter",
    ),
)

"""M0015 — 52-week-high momentum: rank on nearness to the yearly high, not past return.

Source: George & Hwang (2004), "The 52-week high and momentum investing", Journal of Finance
59(5), doi:10.1111/j.1540-6261.2004.00695.x; and later work tying momentum crashes to winners
that sit far below their highs (FAJ 2023, "Momentum crashes and the 52-week high").
Idea: every momentum book in the lab ranks on 12-1 total or residual return, and its binding
drawdowns are crowd unwinds of last year's biggest risers. George-Hwang find that nearness to
the 52-week high (close / highest close of the last 252 sessions) carries most of momentum's
return with no long-run reversal: investors anchor on the high and under-react to news that
pushes a price toward it. A stock at its high that rose steadily is a different holding from
one that doubled off a crash low; the second is what momentum crashes unwind.

The allocator reuses F4's universe screen, trend gate, book size and equal weights verbatim
(``f_factor``) and replaces only the ranking key. On data date d, for each eligible member:

    * nearness = close[d] / max(close over the 252 sessions ending at d), in (0, 1];
    * ``near``: the ``top`` highest nearness; ties (several names AT their high, nearness == 1)
      are broken by 12-1 total momentum descending, then symbol;
    * ``blend``: each name gets its position in the nearness order (as above) and its position
      in the raw residual-momentum order (M0007-N20-RAW's score); the ``top`` lowest sums are
      held, ties by nearness position, then symbol. Names without a residual score are not
      eligible for the blend.

Closes, not intraday highs: the store's closes are the series every other lab method ranks on,
and a close-to-close high cannot be set by a single intraday print.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import (
    ResidParams,
    ResidPrepared,
    build_grid,
    resid_lookback,
    residual_scores,
)
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorParams,
    FactorRow,
    factor_lookback,
    factor_rows,
    factor_weights,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 10, 6)
HIGH_N = 252  # sessions in the 52-week high

Rank = Literal["near", "blend"]


@dataclass(frozen=True, slots=True)
class HighParams:
    """``inner`` is F4's screen, trend gate, book size and weighting; ``rank`` is the key."""

    inner: FactorParams
    rank: Rank = "near"
    high_n: int = HIGH_N
    market: str = "SPY"  # the residual model's market (blend only)

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if self.rank not in ("near", "blend"):
            raise ValueError(f"rank must be 'near' or 'blend', got {self.rank!r}")
        if isinstance(self.high_n, bool) or not isinstance(self.high_n, int) or self.high_n < 20:
            raise ValueError(f"high_n must be an int >= 20, got {self.high_n!r}")
        if not isinstance(self.market, str) or not self.market:
            raise ValueError(f"market must be a non-empty symbol, got {self.market!r}")

    def resid(self) -> ResidParams:
        """The blend's residual leg: M0007-N20-RAW's model (unscaled cumulative residual)."""
        return ResidParams(self.inner, scaled=False, market=self.market)

    def as_dict(self) -> dict[str, str]:
        out = {"rank": self.rank, "high_n": str(self.high_n), "market": self.market}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> HighParams:
    if not isinstance(params, HighParams):
        raise TypeError(f"params must be HighParams, got {type(params).__name__}")
    return params


def high_lookback(params: HighParams) -> int:
    lb = max(factor_lookback(params.inner), params.high_n)
    if params.rank == "blend":
        lb = max(lb, resid_lookback(params.resid()))
    return lb


def nearness(history: Mapping[str, History], symbol: str, data_date: date, n: int) -> float | None:
    """close[d] / max(close over the ``n`` sessions ending at d); reads no bar after d."""
    h = history.get(symbol)
    if h is None:
        return None
    i = h.index_of(data_date)
    if i is None or i + 1 < n:
        return None
    window = h.close[i + 1 - n : i + 1]
    hi = float(np.max(window))
    last = float(window[-1])
    if not (np.isfinite(hi) and np.isfinite(last)) or hi <= 0.0:
        return None
    return last / hi


def choose(rows: list[FactorRow], near: Mapping[str, float], resid: Mapping[str, float] | None,
           params: HighParams) -> tuple[Target, ...]:
    pool = [r for r in rows if r.symbol in near and r.symbol not in EXCLUDED]
    if resid is not None:
        pool = [r for r in pool if r.symbol in resid]
    by_near = sorted(pool, key=lambda r: (-near[r.symbol], -r.momentum, r.symbol))
    if resid is None:
        chosen = by_near[: params.inner.top]
    else:
        npos = {r.symbol: k for k, r in enumerate(by_near)}
        by_resid = sorted(pool, key=lambda r: (-resid[r.symbol], r.symbol))
        rpos = {r.symbol: k for k, r in enumerate(by_resid)}
        chosen = sorted(pool, key=lambda r: (npos[r.symbol] + rpos[r.symbol], npos[r.symbol],
                                             r.symbol))[: params.inner.top]
    out: list[Target] = []
    for row, weight in zip(chosen, factor_weights(chosen, params.inner), strict=True):
        if weight is None:
            continue
        target = target_from_close(row.symbol, row.close, weight)
        if target is not None:
            out.append(target)
    return tuple(out)


def _near_map(history: Mapping[str, History], rows: list[FactorRow], data_date: date,
              n: int) -> dict[str, float]:
    out: dict[str, float] = {}
    for r in rows:
        v = nearness(history, r.symbol, data_date, n)
        if v is not None:
            out[r.symbol] = v
    return out


class HighAllocator:
    """F4's book ranked on nearness to the 52-week high (or its blend with residual momentum).

    Held symbols get no special treatment: the targets are exactly the new top set.
    """

    id = "M0015"

    def lookback(self, params: Any) -> int:
        return high_lookback(_check(params))

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        out = set() if p.inner.trend is None else {p.inner.trend[0]}
        if p.rank == "blend":
            out.add(p.market)
        return tuple(sorted(out))

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if not trend_on(history, data_date, p.inner):
            return ()
        rows = factor_rows(history, members, data_date, p.inner)
        if not rows:
            return ()
        near = _near_map(history, rows, data_date, p.high_n)
        resid = None
        if p.rank == "blend":
            grid = build_grid(history, p.market)
            if grid is None:
                return ()
            resid = residual_scores(grid, [r.symbol for r in rows], data_date, p.resid())
        return choose(rows, near, resid, p)

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
        near = _near_map(prepared.history, rows, data_date, p.high_n)
        resid = None
        if p.rank == "blend":
            grid = prepared.grid(p.market)
            if grid is None:
                return ()
            resid = residual_scores(grid, [r.symbol for r in rows], data_date, p.resid())
        return choose(rows, near, resid, p)


HIGH = HighAllocator()

TREND = ("SPY", 200)
N20 = FactorParams(rank="momentum", top=20, trend=TREND)  # F4-MOM12-N20-TREND's screen
N30 = FactorParams(rank="momentum", top=30, trend=TREND)


def _v(suffix: str, params: HighParams, rationale: str, rules=MONTHLY_HOLD) -> Candidate:
    return Candidate(id=f"M0015-{suffix}", family="M0015", rules=rules, allocator=HIGH,
                     params=params, rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0015",
    name="52-week-high momentum: rank on nearness to the yearly high, not past return",
    family="stock-52week-high",
    source_kind="paper",
    source_ref=(
        "George & Hwang (2004), The 52-week high and momentum investing, J. Finance 59(5), "
        "doi:10.1111/j.1540-6261.2004.00695.x; Momentum crashes and the 52-week high, FAJ 2023"
    ),
    hypothesis=(
        "Every momentum book in the lab ranks on 12-1 total or residual return, and its binding "
        "drawdowns (Mar-Aug 2006, Aug 1998, spring 2010/2011) are crowd unwinds of last year's big "
        "risers while SPY stays above its 200-day average. Nearness to the 52-week high captures "
        "most of momentum's return without its reversal, and momentum crashes concentrate in "
        "winners far below their highs. Ranking the top-20 by close / 252-day max close (ties by "
        "12-1 return), with F4's screen, monthly rebalance and SPY 200-day gate, holds steadier "
        "names less exposed to speculative unwinds: max DD below F4's 22.2% at comparable CAGR, "
        "and the 50/50 blend with raw residual momentum below M0007-N20-RAW's 19.6%. Kill the "
        "direction if no variant gets max DD below 19.6%."
    ),
    expected_failure=(
        "Nearness to the high is a low-volatility, late-cycle tilt: the names at their highs in a "
        "calm bull market are the same crowded quality/defensive leaders that sold off together in "
        "May 2006 and 2011, so the drawdown barely moves (19-22%) while CAGR drops 2-4 points "
        "because the pure nearness rank skips the strongest early-trend rebounders. Ties at "
        "nearness 1.0 in strong markets make the pure rank collapse into plain 12-1 momentum, "
        "so N20 looks like F4."
    ),
    candidates=(
        _v("N20", HighParams(N20),
           "Top-20 by nearness to the 52-week high, ties by 12-1 return; F4-MOM12-N20-TREND's book"),
        _v("N30", HighParams(N30),
           "Top-30 by nearness: the broader book, since nearness ties are common"),
        _v("N20-BLEND", HighParams(N20, rank="blend"),
           "Top-20 by summed rank of nearness and raw residual momentum (M0007-N20-RAW's signal)"),
        _v("N30-BLEND", HighParams(N30, rank="blend"),
           "Top-30 blend: breadth plus both signals"),
    ),
    seen_keys=(
        "concept:52-week-high-momentum",
        "concept:nearness-to-high",
        "doi:10.1111/j.1540-6261.2004.00695.x",
    ),
)

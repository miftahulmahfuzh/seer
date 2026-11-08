"""M0027 — Step aside when the momentum gap collapses: a gate read off the stock-picking factor, not the market.

Source: variation of M0012 (its W-SMA200 family showed SPY-based gates cannot see this book's
binding falls) on M0007's raw-residual top-20 book. Idea family: momentum crashes (Daniel and
Moskowitz 2016, published 2016) are unwinds of the long-short spread, which shows in the factor
itself before it shows in the index.

Mechanics. Rules ``MONTHLY_HOLD_FRAC_GOTRADE`` (fractional, real fees; a 20-name book). On each
monthly decision date d the basket is exactly M0007-N20-RAW's (its own SPY 200-day gate included).
In addition, over the scorable index members on d, take the top and bottom decile by the SAME
residual score and measure the equal-weight 21-session price return of each; the spread is
top minus bottom. When it is below ``thresh`` the basket's weights are scaled by ``keep`` (0.5 =
half, 0 = cash); otherwise the basket is untouched. Fewer than 50 scorable names: no opinion.
Read once a month: M0012 showed weekly reading whipsaws. Reads only bars dated <= d.
The NEVER arm (thresh=-1e9) is the same book with no opinion; it re-states M0032-N20-RAW-FRAC-GT
as a book twin of that host, and prices the habit-free baseline.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import (
    N20,
    RESIDMOM,
    ResidParams,
    ResidPrepared,
    build_grid,
    residual_scores,
)
from seer_engine.sim.book import WEIGHT_QUANTUM, Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import EXCLUDED, factor_rows

ADDED = date(2026, 11, 8)
RAW20 = ResidParams(N20, scaled=False)  # M0007-N20-RAW
MIN_NAMES = 50


@dataclass(frozen=True, slots=True)
class SpreadParams:
    inner: ResidParams = RAW20
    thresh: float = -0.08  # spread below this trips the gate
    keep: float = 0.5  # share of the basket kept when tripped (0 = cash)
    ret_n: int = 21  # sessions in the spread's return window
    decile: float = 0.1

    def __post_init__(self) -> None:
        if not isinstance(self.inner, ResidParams):
            raise TypeError(f"inner must be ResidParams, got {type(self.inner).__name__}")
        if not 0.0 <= self.keep < 1.0:
            raise ValueError(f"keep must be in [0, 1), got {self.keep}")
        if self.ret_n < 2:
            raise ValueError(f"ret_n must be >= 2, got {self.ret_n}")
        if not 0.0 < self.decile <= 0.5:
            raise ValueError(f"decile must be in (0, 0.5], got {self.decile}")

    def as_dict(self) -> dict[str, str]:
        out = {"thresh": repr(self.thresh), "keep": repr(self.keep),
               "ret_n": str(self.ret_n), "decile": repr(self.decile)}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> SpreadParams:
    if not isinstance(params, SpreadParams):
        raise TypeError(f"params must be SpreadParams, got {type(params).__name__}")
    return params


def spread_on(history: Mapping[str, History], scores: Mapping[str, float], data_date: date,
              p: SpreadParams) -> float | None:
    """Top-decile minus bottom-decile equal-weight ``ret_n``-session return; None = no opinion."""
    rets: list[tuple[float, float]] = []
    for s, sc in scores.items():
        if s in EXCLUDED:
            continue
        h = history.get(s)
        if h is None:
            continue
        i = h.index_of(data_date)
        if i is None or i < p.ret_n:
            continue
        a, b = float(h.close[i]), float(h.close[i - p.ret_n])
        if not (b > 0.0 and a > 0.0):
            continue
        rets.append((sc, a / b - 1.0))
    if len(rets) < MIN_NAMES:
        return None
    rets.sort(key=lambda t: t[0])
    k = max(1, int(len(rets) * p.decile))
    lo = sum(r for _, r in rets[:k]) / k
    hi = sum(r for _, r in rets[-k:]) / k
    return hi - lo


def _scaled(basket: tuple[Target, ...], keep: float) -> tuple[Target, ...]:
    if keep <= 0.0:
        return ()
    out: list[Target] = []
    for t in basket:
        w = (t.weight * Decimal(repr(keep))).quantize(WEIGHT_QUANTUM)
        if w > 0:
            out.append(replace(t, weight=w))
    return tuple(out)


class SpreadGateAllocator:
    """M0007-N20-RAW's basket, scaled down while the top-minus-bottom decile spread is collapsed."""

    id = "M0027"

    def lookback(self, params: Any) -> int:
        return RESIDMOM.lookback(_check(params).inner) + 5

    def symbols(self, params: Any) -> tuple[str, ...]:
        return RESIDMOM.symbols(_check(params).inner)

    def holds(self, params: Any) -> tuple[str, ...]:
        return RESIDMOM.holds(_check(params).inner)

    def uses_members(self, params: Any) -> bool:
        return True

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        basket = RESIDMOM.targets(history, members, data_date, held, p.inner)
        if not basket:
            return basket
        rows = factor_rows(history, members, data_date, p.inner.inner)
        grid = build_grid(history, p.inner.market)
        if not rows or grid is None:
            return basket
        scores = residual_scores(grid, [r.symbol for r in rows], data_date, p.inner)
        sp = spread_on(history, scores, data_date, p)
        return _scaled(basket, p.keep) if sp is not None and sp < p.thresh else basket

    def prepare(self, history: Mapping[str, History]) -> ResidPrepared:
        return RESIDMOM.prepare(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, ResidPrepared):
            raise TypeError(f"prepared must be ResidPrepared, got {type(prepared).__name__}")
        p = _check(params)
        basket = RESIDMOM.targets_prepared(prepared, members, data_date, held, p.inner)
        if not basket:
            return basket
        rows = prepared.factor.rows_on(members, data_date, p.inner.inner)
        grid = prepared.grid(p.inner.market)
        if not rows or grid is None:
            return basket
        scores = residual_scores(grid, [r.symbol for r in rows], data_date, p.inner)
        sp = spread_on(prepared.history, scores, data_date, p)
        return _scaled(basket, p.keep) if sp is not None and sp < p.thresh else basket


SPREADGATE = SpreadGateAllocator()


def _v(suffix: str, params: SpreadParams, rationale: str, rules=MONTHLY_HOLD_FRAC_GOTRADE) -> Candidate:
    return Candidate(id=f"M0027-{suffix}", family="M0027", rules=rules, allocator=SPREADGATE,
                     params=params, rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0027",
    name="Step aside when the momentum gap collapses: a gate that reads the stock-picking factor, not the market",
    family="stock-residual-momentum",
    source_kind="variation",
    source_ref="M0012 (SPY gates cannot see the binding falls); M0007 (M0007-N20-RAW); Daniel & Moskowitz 2016 'Momentum crashes'",
    parent_id="M0012",
    hypothesis=(
        "M0012 showed the residual-momentum book's binding falls (May-Jul 2006 19.3%, Apr-May 2010 "
        "17.9%) happen while SPY sits above its averages, so no market gate can catch them, and weekly "
        "market gates whipsaw (worst falls 22-30%). A momentum unwind shows first as a collapse in the "
        "gap between the top-ranked and bottom-ranked names by the same residual score. Once a month "
        "(no weekly switch), compute the equal-weight 21-session return of the top decile minus the "
        "bottom decile of scorable index members by the book's own score. Below a fixed threshold "
        "hold half the basket (HALF) or none (OUT). Published 2016 (momentum crashes), so the dev "
        "window may show an edge the crowd has since traded. Arms: NEVER (thresh=-1e9, no opinion; a "
        "book twin of M0032-N20-RAW-FRAC-GT, real fees, fractional, priced as the habit-free "
        "baseline), HALF-8 and OUT-8 at -8%, HALF-4 and OUT-4 at -4% (a dose ladder on the threshold). "
        "Expected: the 2006 fall under 15% with return above +13% a year. The parent family's "
        "M0007-N20-RAW misses only the old 15% fall bar; judged now against the 25% bar and DSR 0.90."
    ),
    expected_failure=(
        "The spread turns only after the damage: momentum crashes are 1-3 weeks long and a monthly "
        "read of the trailing 21 sessions fires after the loss, then halves the book into the rebound "
        "(momentum rebounds hardest right after a crash). Cost of acting exceeds saving, as for "
        "M0247's correlation switch. Also possible: the threshold never trips, and the arms share "
        "NEVER's curve (the dial never moved)."
    ),
    candidates=(
        _v("NEVER", SpreadParams(thresh=-1e9, keep=0.5), "No opinion: the same book never stepping aside"),
        _v("HALF-8", SpreadParams(thresh=-0.08, keep=0.5), "Half the basket when the spread is below -8%"),
        _v("OUT-8", SpreadParams(thresh=-0.08, keep=0.0), "Cash when the spread is below -8%"),
        _v("HALF-4", SpreadParams(thresh=-0.04, keep=0.5), "Half the basket when the spread is below -4%"),
        _v("OUT-4", SpreadParams(thresh=-0.04, keep=0.0), "Cash when the spread is below -4%"),
    ),
    seen_keys=(
        "concept:momentum-spread-gate",
        "concept:factor-state-gate-residual-momentum",
    ),
)

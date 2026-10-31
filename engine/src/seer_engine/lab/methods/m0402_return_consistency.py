"""M0402 — Steady winners: stocks that rose in most of the last twelve months.

Source: Grinblatt & Moskowitz (2004), Predicting stock price movements from past returns: the role
of consistency and tax-loss selling, Journal of Financial Economics 71(3), 541-579.
Idea: momentum ranks stocks by how much they rose; the paper ranks by how *steadily* they rose, the
share of recent months with a positive return, and finds the steady winners beat the jumpy ones
with the same total gain. This book holds the steadiest names, not the biggest gainers.

The score, on data date d (column ``j`` of SPY's session calendar): a name's twelve monthly
returns are close(j - 21k) / close(j - 21(k+1)) - 1 for k = 1..12, so the latest month is skipped
(the 12-1 convention) and every close is dated at or before d. The score is the count of positive
months out of 12. A name missing any of the thirteen closes is not scored.

Ties are many (the score takes thirteen values), so ties are broken by the same fixed blake2b hash
the placebo uses, **not** by the 12-1 return. Assumption, written before the run: breaking ties by
return would quietly turn this into a momentum book on the days that matter; a hash keeps the
ranking about steadiness alone, so what is measured is the share of up months.

The book is M0203's frame: rank, keep a holding while it stays inside the top ``keep``, fill ``top``
slots of 1/top, unfilled slots in SPY, whole book in cash while SPY is under its 200-day average.
Pool: F4's screened members. ``signal="hash"`` is the placebo: same pool (names scoreable on d),
band, slots, fill and switch, ranked by hash alone. If steadiness does not clearly beat it, the
frame earned the result.

Assumption, written before the run: the reserved idea named a plain 12-1 momentum arm as a
contrast. It is left out, as M0203 left it out: the hard gate's behaviour test (hardgate D14) reads
every dev variant, and a momentum variant would tie the whole method to the test-failed momentum
books. The comparison with momentum is made in the analysis against recorded real-fee momentum
books. Instead the no-switch arm (always invested, no market opinion) prices the switch.

Rules are ``monthly-hold-frac-gotrade``: fractional shares at Gotrade's real fees. Pure: reads only
columns at or before d.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0203_trend_factor import CloseGrid, build_close_grid, draw
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History, as_day
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorParams,
    FactorPrepared,
    FactorRow,
    factor_lookback,
    factor_rows,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 10, 31)
STEP = 21  # sessions per month
MONTHS = 12  # monthly returns counted
SIGNALS = ("consistency", "hash")


@dataclass(frozen=True, slots=True)
class ConsParams:
    """``inner`` is F4's screen, switch and book size; the rest is the signal and the band."""

    inner: FactorParams
    keep: int = 40
    signal: str = "consistency"
    seed: int = 1
    market: str = "SPY"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        for name in ("keep", "seed"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int):
                raise TypeError(f"{name} must be an int, got {type(v).__name__}")
        if self.keep < self.inner.top:
            raise ValueError(f"keep must be >= top, got {self.keep} < {self.inner.top}")
        if self.signal not in SIGNALS:
            raise ValueError(f"signal must be one of {SIGNALS}, got {self.signal!r}")
        if not isinstance(self.market, str) or not self.market:
            raise ValueError(f"market must be a non-empty symbol, got {self.market!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"keep": str(self.keep), "signal": self.signal, "seed": str(self.seed),
               "market": self.market, "step": str(STEP), "months": str(MONTHS),
               "tiebreak": "blake2b-8"}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> ConsParams:
    if not isinstance(params, ConsParams):
        raise TypeError(f"params must be ConsParams, got {type(params).__name__}")
    return params


def up_months(grid: CloseGrid, symbols: list[str], data_date: date) -> dict[str, int]:
    """Positive months out of the twelve ending one month before ``data_date``; unscoreable names omitted."""
    day = as_day(data_date)
    j = int(np.searchsorted(grid.dates, day, side="right")) - 1
    if j < 0 or grid.dates[j] != day or j - STEP * (MONTHS + 1) < 0:
        return {}
    names = [s for s in symbols if s in grid.row]
    if not names:
        return {}
    idx = np.asarray([grid.row[s] for s in names], dtype=np.int64)
    cols = [j - STEP * k for k in range(1, MONTHS + 2)]  # newest first
    c = grid.close[np.ix_(idx, cols)]
    ok = np.isfinite(c).all(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        up = (c[:, :-1] / c[:, 1:] - 1.0) > 0.0
    n = up.sum(axis=1)
    return {names[k]: int(n[k]) for k in np.flatnonzero(ok)}


def scored(grid: CloseGrid, rows: list[FactorRow], data_date: date, p: ConsParams) -> dict[str, float]:
    """Higher is better. Share of up months, hash tie-break; the placebo is the hash alone."""
    pool = sorted(r.symbol for r in rows if r.symbol not in EXCLUDED and r.symbol != p.market)
    ups = up_months(grid, pool, data_date)
    tie = {s: 1.0 - draw(p.seed, s, data_date) / 2.0**64 for s in ups}  # in (0, 1]
    if p.signal == "hash":
        return tie
    return {s: ups[s] + tie[s] * 0.5 for s in ups}


def choose(history: Mapping[str, History], rows: list[FactorRow], sc: Mapping[str, float],
           data_date: date, held: frozenset[str], p: ConsParams) -> tuple[Target, ...]:
    """The band: held names ranked inside ``keep`` stay, the rest of ``top`` filled from the top."""
    order = sorted(sc, key=lambda s: (-sc[s], s))
    rank = {s: i for i, s in enumerate(order)}
    kept = sorted((s for s in held if rank.get(s, p.keep) < p.keep), key=lambda s: rank[s])
    picks = kept[: p.inner.top]
    for s in order:
        if len(picks) >= p.inner.top:
            break
        if s not in picks:
            picks.append(s)
    close = {r.symbol: r.close for r in rows}
    w = equal_weight(p.inner.top)
    out: list[Target] = []
    for s in picks:
        t = target_from_close(s, close[s], w)
        if t is not None:
            out.append(t)
    rest = Decimal(1) - w * len(out)
    mh = history.get(p.market)
    if rest > 0 and mh is not None and mh.index_of(data_date) is not None:
        t = target_from_close(p.market, last_close(mh, data_date), rest)
        if t is not None:
            out.append(t)
    return tuple(out)


@dataclass(frozen=True, slots=True, eq=False)
class ConsPrepared:
    """F4's rolling columns plus one close grid per market symbol, built on first use."""

    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)
    grids: dict[str, CloseGrid | None] = field(default_factory=dict, repr=False)

    def grid(self, market: str) -> CloseGrid | None:
        if market not in self.grids:
            self.grids[market] = build_close_grid(self.history, market)
        return self.grids[market]


class ConsistencyAllocator:
    """The ``top`` names with the most up months among screened members (or the placebo order)."""

    id = "M0402"

    def lookback(self, params: Any) -> int:
        # thirteen month-end closes need 13 * 21 sessions back, more than F4's 12-1 window
        return max(factor_lookback(_check(params).inner), STEP * (MONTHS + 1) + 1)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        fixed = {p.market}
        if p.inner.trend is not None:
            fixed.add(p.inner.trend[0])
        return tuple(sorted(fixed))

    def holds(self, params: Any) -> tuple[str, ...]:
        return (_check(params).market,)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _targets(self, history: Mapping[str, History], rows: list[FactorRow],
                 grid: CloseGrid | None, data_date: date, held: frozenset[str],
                 p: ConsParams) -> tuple[Target, ...]:
        if not rows or grid is None:
            return ()
        return choose(history, rows, scored(grid, rows, data_date, p), data_date, held, p)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if not trend_on(history, data_date, p.inner):
            return ()
        rows = factor_rows(history, members, data_date, p.inner)
        return self._targets(history, rows, build_close_grid(history, p.market), data_date, held, p)

    def prepare(self, history: Mapping[str, History]) -> ConsPrepared:
        return ConsPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, ConsPrepared):
            raise TypeError(f"prepared must be ConsPrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        rows = prepared.factor.rows_on(members, data_date, p.inner)
        return self._targets(prepared.history, rows, prepared.grid(p.market), data_date, held, p)


CONSISTENCY = ConsistencyAllocator()

TREND = ("SPY", 200)
N20 = FactorParams(rank="momentum", top=20, trend=TREND)
N40 = FactorParams(rank="momentum", top=40, trend=TREND)
N20_NOSW = FactorParams(rank="momentum", top=20, trend=None)


def _v(suffix: str, params: ConsParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0402-{suffix}", family="M0402",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=CONSISTENCY, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0402",
    name="Steady winners: stocks that rose in most of the last twelve months, not just the ones that rose most",
    family="stock-return-consistency",
    source_kind="paper",
    source_ref=("Grinblatt and Moskowitz (2004), Predicting stock price movements from past returns: "
                "the role of consistency and tax-loss selling, Journal of Financial Economics 71(3)"),
    hypothesis=(
        "Each month-end, count for each screened index member how many of the twelve monthly "
        "returns ending one month ago were positive (the latest month skipped, 12-1 style); hold "
        "the 20 with the most up months in equal 5% slots, monthly, keeping a holding while it "
        "ranks inside the top 40, ties broken by a fixed hash (not by return), unfilled slots in "
        "SPY, behind the SPY 200-day switch (F4's screen and switch, M0203's frame). Grinblatt and "
        "Moskowitz (published 2004) find that steadiness of the past path predicts returns beyond "
        "the size of the past gain. Published over twenty years ago and well known, so the dev "
        "window (to 2015) is mostly after publication and the edge may already be traded away. "
        "Arms: CONS-N40 (40 names, band 80), CONS-N20-NOSW (no switch: always invested, which "
        "prices the switch). Control: HASH-N20, same pool, band, slots, fill and switch in hash "
        "order. A plain 12-1 momentum arm named at reservation is dropped, as M0203 dropped it: a "
        "momentum variant would tie the whole method to the test-failed momentum books through "
        "the behaviour test (hardgate D14); momentum is compared in the analysis against recorded "
        "real-fee momentum books. Fractional shares at Gotrade's real fees on the owner's monthly "
        "top-up. Success: beats SPY TR on dev, worst fall <= 25%, PF >= 1.3, majority of "
        "walk-forward folds, a positive lead over SPY in 2009-2015, and beats the placebo by at "
        "least 2 points a year."
    ),
    expected_failure=(
        "Up-month count takes only thirteen values and in a bull market hundreds of names score "
        "10-12, so the top 20 is mostly a hash draw inside a big tie and the book trades like the "
        "placebo: the frame, not the steadiness, earns any lead (M0187). Steady risers are also "
        "low-volatility large caps that rise slowly, so the book may be a quality or low-vol tilt "
        "that lags SPY's big-company drift in 2009-2015 (insight 91) and pays fees on monthly "
        "churn in small slots. A widely published anomaly fades. If it wins, it is likely "
        "momentum by another route and inherits momentum's crash, met late by the 200-day switch. "
        "The close neighbour, smooth-versus-jumpy momentum paths (M0036), fell 22%, over the bar."
    ),
    candidates=(
        _v("CONS-N20", ConsParams(N20, keep=40),
           "20 names with the most up months of 12, held while inside the top 40, behind the 200-day switch"),
        _v("CONS-N40", ConsParams(N40, keep=80),
           "Same score, 40 names, band 80: does width help a score with many ties?"),
        _v("CONS-N20-NOSW", ConsParams(N20_NOSW, keep=40),
           "The main book without the switch: always invested, prices the switch"),
        _v("HASH-N20", ConsParams(N20, keep=40, signal="hash"),
           "Placebo: the same pool, band, slots and switch in a fixed hash order"),
    ),
    seen_keys=(
        "concept:positive-month-share-rank",
        "concept:return-consistency",
    ),
)

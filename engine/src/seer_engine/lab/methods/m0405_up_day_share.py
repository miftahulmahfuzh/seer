"""M0405 — Steady winners by share of up days, with same-size placebos at each width.

Source: Grinblatt & Moskowitz (2004), Journal of Financial Economics 71(3), 541-579, through
M0402, which ranked by the share of up *months*. Parent M0402 found its score takes thirteen
values, so most of the top 20 was a hash draw inside a tie, and its placebo traded 2.3 times as
much as the book, so the 0.2 point lead over the placebo could not be priced. This child fixes
both: the score is the share of up *days* over the last twelve months (252 daily returns, latest
21 sessions skipped, 12-1 style), which has far fewer ties, and every width gets its placebos.

The score, on data date d (column ``j`` of SPY's session calendar): the 252 daily returns
close(t)/close(t-1) - 1 for t = j-272 .. j-21, so every close is dated at or before d minus a
month. Higher share of positive days is better. A name missing any of the 253 closes is not
scored. Ties are broken by the fixed blake2b hash (not by return), as in M0402, so the ranking
stays about steadiness alone.

Placebos: ``signal="hash"`` ranks the same scoreable pool by hash alone, redrawn each month. A
fully redrawn order churns far more than a ranked book, which is what broke M0402's control.
Assumption, written before the run: the trade count cannot be matched by tuning after seeing it,
so each width gets two placebos, the same band as its book and a band twice as wide (slower
turnover). The analysis uses whichever of the two trades within 0.50-2.00 times the book's own
trade count (the lab's fair band); if both do, the nearer one. Rules are decided now, not after.

The frame is M0402's: keep a holding while it ranks inside ``keep``, fill ``top`` slots of 1/top,
unfilled slots in SPY, whole book in cash while SPY is under its 200-day average. Rules are
``monthly-hold-frac-gotrade``. No no-switch arm: M0402 priced the switch already. Pure.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0203_trend_factor import CloseGrid, build_close_grid, draw
from seer_engine.lab.methods.m0402_return_consistency import ConsPrepared, choose
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History, as_day
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorParams,
    FactorRow,
    factor_lookback,
    factor_rows,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 11, 1)
SKIP = 21  # latest month skipped
DAYS = 252  # daily returns counted
SIGNALS = ("updays", "hash")


@dataclass(frozen=True, slots=True)
class UpParams:
    """``inner`` is F4's screen, switch and book size; the rest is the signal and the band."""

    inner: FactorParams
    keep: int = 40
    signal: str = "updays"
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
               "market": self.market, "skip": str(SKIP), "days": str(DAYS),
               "tiebreak": "blake2b-8"}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> UpParams:
    if not isinstance(params, UpParams):
        raise TypeError(f"params must be UpParams, got {type(params).__name__}")
    return params


def up_days(grid: CloseGrid, symbols: list[str], data_date: date) -> dict[str, int]:
    """Positive days out of the 252 ending SKIP sessions before ``data_date``; unscoreable omitted."""
    day = as_day(data_date)
    j = int(np.searchsorted(grid.dates, day, side="right")) - 1
    if j < 0 or grid.dates[j] != day or j - SKIP - DAYS < 0:
        return {}
    names = [s for s in symbols if s in grid.row]
    if not names:
        return {}
    idx = np.asarray([grid.row[s] for s in names], dtype=np.int64)
    c = grid.close[idx, j - SKIP - DAYS: j - SKIP + 1]
    ok = np.isfinite(c).all(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        up = (c[:, 1:] / c[:, :-1] - 1.0) > 0.0
    n = up.sum(axis=1)
    return {names[k]: int(n[k]) for k in np.flatnonzero(ok)}


def scored(grid: CloseGrid, rows: list[FactorRow], data_date: date, p: UpParams) -> dict[str, float]:
    """Higher is better. Up-day count, hash tie-break; the placebo is the hash alone."""
    pool = sorted(r.symbol for r in rows if r.symbol not in EXCLUDED and r.symbol != p.market)
    ups = up_days(grid, pool, data_date)
    tie = {s: 1.0 - draw(p.seed, s, data_date) / 2.0**64 for s in ups}  # in (0, 1]
    if p.signal == "hash":
        return tie
    return {s: ups[s] + tie[s] * 0.5 for s in ups}


class UpDayAllocator:
    """The ``top`` names with the largest share of up days among screened members (or placebo)."""

    id = "M0405"

    def lookback(self, params: Any) -> int:
        return max(factor_lookback(_check(params).inner), SKIP + DAYS + 2)

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
                 p: UpParams) -> tuple[Target, ...]:
        if not rows or grid is None:
            return ()
        # choose() reads only keep, inner.top and market, which UpParams carries
        return choose(history, rows, scored(grid, rows, data_date, p), data_date, held, p)  # type: ignore[arg-type]

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


UPDAYS = UpDayAllocator()

TREND = ("SPY", 200)
N20 = FactorParams(rank="momentum", top=20, trend=TREND)
N40 = FactorParams(rank="momentum", top=40, trend=TREND)


def _v(suffix: str, params: UpParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0405-{suffix}", family="M0405",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=UPDAYS, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0405",
    name="Steady winners by share of up days, with a same-size placebo",
    family="stock-return-consistency",
    source_kind="variation",
    source_ref="Grinblatt and Moskowitz (2004), Journal of Financial Economics 71(3), via M0402",
    parent_id="M0402",
    hypothesis=(
        "Rank screened index members by the share of up days over the last twelve months "
        "(252 daily returns, the latest month skipped), a finer score than the share of up "
        "months that has far fewer ties. Hold 20 and 40 names equal weight, monthly, in "
        "fractional shares at Gotrade's real fees behind the 200-day switch, keeping a holding "
        "while it ranks inside twice its slot count, ties broken by a fixed hash. Register a "
        "hash placebo at each width, at the book's band and at twice that band (slower churn), "
        "so the lead can be priced against a control whose trade count falls within 0.50-2.00 "
        "times the book's own, the nearer one if both do. Parent M0402 found the 20-name steady "
        "book only 0.2 points a year ahead of its placebo (which traded 2.3 times as much) and "
        "the 40-name book (+9.7% vs SPY +7.2%) missed the luck bar at 0.898; 2009-2015 trailed "
        "SPY by 5.5 points a year. Published 2004, so the dev window is mostly after "
        "publication and the edge may already be traded away. Success: beats SPY TR on dev, "
        "worst fall <= 25%, PF >= 1.3, a positive lead over SPY in 2009-2015, a majority of "
        "walk-forward folds, and a lead over the matched placebo of at least 2 points a year."
    ),
    expected_failure=(
        "Steady risers are low-volatility large caps that rise slowly, so the book is a "
        "low-vol or quality tilt that lags SPY's big-company drift in 2009-2015 (insight 91) "
        "and pays fees on monthly churn in small slots. Share of up days is nearly a "
        "volatility-adjusted drift score, so it may be momentum by another route and inherit "
        "momentum's late exits. A finer score removes the tie, and with it the placebo-like "
        "behaviour, so a result close to M0402's would say the up-month version was never the "
        "limit. A widely published anomaly fades."
    ),
    candidates=(
        _v("UD-N20", UpParams(N20, keep=40),
           "20 names with the highest share of up days, held while inside the top 40, behind the switch"),
        _v("UD-N40", UpParams(N40, keep=80),
           "Same score, 40 names, band 80"),
        _v("HASH-N20", UpParams(N20, keep=40, signal="hash"),
           "Placebo at 20 names, the book's band, hash order"),
        _v("HASH-N20-WIDE", UpParams(N20, keep=80, signal="hash"),
           "Placebo at 20 names, band 80: slower churn, closer to the book's trade count"),
        _v("HASH-N40", UpParams(N40, keep=80, signal="hash"),
           "Placebo at 40 names, the book's band, hash order"),
        _v("HASH-N40-WIDE", UpParams(N40, keep=160, signal="hash"),
           "Placebo at 40 names, band 160: slower churn"),
    ),
    seen_keys=(
        "concept:up-day-share-rank",
        "concept:return-consistency",
    ),
)

"""M0056 — Steady overnight drift, not one big gap: overnight winners without the single-jump stocks.

Source: a variation of M0050 (its M0050-TOT-ON: the 40 best 12-1 total-momentum names, then the
20 of them whose past-year gain came most overnight; Lou, Polk & Skouras 2019). The "steady path"
idea is Da, Gurun & Warachka (2014), "Frog in the pan" (M0036's source), carried from the
close-to-close path onto the overnight leg.
Idea: M0050-TOT-ON earned 15.1% a year on the owner's deposits at real fees and failed one
condition only, a 22.8% worst fall. M0053 fixed the fall with a weekly volatility brake and paid
4.6 points of return and the fold record for it. This method keeps M0050-TOT-ON's book unbraked and
changes only the overnight sort inside the momentum pool: it scores each name on the overnight
gains that do NOT come from its few largest gaps, or on how often its overnight leg is positive, so
the book holds names that drift up night after night rather than names carried by one or two
earnings jumps, which tend to gap down together in a shock.

On data date d, over the same window as M0050 (231 sessions ending 21 sessions before d, on SPY's
calendar, back-to-back bars only, at least 80% of sessions usable):

    * ``key="trim"``: the overnight log-return sum minus its ``k`` largest single values;
    * ``key="pos"``: the share of usable sessions whose overnight log return is > 0, ties broken
      by the full overnight sum.

The pool is the ``pool`` highest 12-1 total-momentum names of F4's screen (behind the SPY 200-day
gate); the book is the ``top`` of them by the key, equal weight, monthly, fractional shares at
Gotrade's real fees on ``monthly-hold-frac-gotrade``.

Assumptions written before the run: "largest gaps" means the largest values, not the largest in
absolute size (trimming big down-gaps would reward exactly the gap-risk names this is meant to
avoid). The 30-name versions use pool 60, M0053's convention of keeping M0050's 2:1 pool-to-book
ratio. A session whose open equals the prior close counts as not positive; pre-2001 opens carry
such zeros, which is noise in ``pos`` and is not corrected. The ex-dividend gap stays inside the
overnight leg, as in M0050. Every piece reads only bars dated <= ``data_date``.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20, N30
from seer_engine.lab.methods.m0050_overnight_momentum import (
    MIN_FRAC,
    LegGrid,
    OnParams,
    OnPrepared,
    build_legs,
    on_lookback,
    targets_from_rows,
)
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History, as_day
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorRow,
    factor_rows,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 10, 9)

Key = Literal["trim", "pos"]
_KEYS: tuple[str, ...] = ("trim", "pos")


@dataclass(frozen=True, slots=True)
class SteadyParams:
    """``on`` is M0050's frame (screen, gate, window, pool, book size); the rest is the sort."""

    on: OnParams
    key: Key = "trim"
    k: int = 3  # "trim" only: how many of the largest overnight values are removed

    def __post_init__(self) -> None:
        if not isinstance(self.on, OnParams):
            raise TypeError(f"on must be OnParams, got {type(self.on).__name__}")
        if self.on.rank != "total-overnight":
            raise ValueError(f"on.rank must be 'total-overnight', got {self.on.rank!r}")
        if not isinstance(self.key, str) or self.key not in _KEYS:
            raise ValueError(f"key must be one of {_KEYS}, got {self.key!r}")
        if isinstance(self.k, bool) or not isinstance(self.k, int):
            raise TypeError(f"k must be an int, got {type(self.k).__name__}")
        if self.k < 0 or self.k >= self.on.n // 2:
            raise ValueError(f"k must be in [0, n/2), got {self.k}")

    def as_dict(self) -> dict[str, str]:
        out = {"key": self.key, "k": str(self.k)}
        for name, v in self.on.as_dict().items():
            out[f"on.{name}"] = v
        return out


def _check(params: object) -> SteadyParams:
    if not isinstance(params, SteadyParams):
        raise TypeError(f"params must be SteadyParams, got {type(params).__name__}")
    return params


def steady_scores(grid: LegGrid, symbols: list[str], data_date: date,
                  params: SteadyParams) -> dict[str, float]:
    """The sort key per scorable symbol over M0050's window ending ``skip`` sessions before d."""
    p = params.on
    d = as_day(data_date)
    j = int(np.searchsorted(grid.dates, d, side="right")) - 1
    if j < 0 or grid.dates[j] != d:
        return {}
    end = j - p.skip
    f0 = end - p.n + 1
    if end < 0 or f0 < 0:
        return {}
    names = [s for s in symbols if s in grid.row]
    if not names:
        return {}
    idx = np.asarray([grid.row[s] for s in names], dtype=np.int64)
    nt = grid.night[idx, f0 : end + 1]
    dy = grid.day[idx, f0 : end + 1]
    ok = np.isfinite(nt) & np.isfinite(dy)
    count = ok.sum(axis=1)
    enough = count >= max(3, math.ceil(MIN_FRAC * p.n))
    total = np.where(ok, nt, 0.0).sum(axis=1)
    if params.key == "trim":
        if params.k == 0:
            score = total
        else:
            ranked = np.sort(np.where(ok, nt, -np.inf), axis=1)[:, -params.k :]
            score = total - np.where(np.isfinite(ranked), ranked, 0.0).sum(axis=1)
    else:
        pos = (ok & (np.where(ok, nt, 0.0) > 0.0)).sum(axis=1)
        score = pos / np.maximum(count, 1)
    live = enough & np.isfinite(score) & np.isfinite(total)
    out: dict[str, float] = {}
    for i in np.flatnonzero(live):
        out[names[int(i)]] = float(score[int(i)])
    return out


def tiebreak(grid: LegGrid, symbols: list[str], data_date: date,
             params: SteadyParams) -> dict[str, float]:
    """The full overnight sum, used to break ties in ``pos`` (same window and usability rule)."""
    return steady_scores(grid, symbols, data_date, SteadyParams(params.on, key="trim", k=0))


def choose(rows: list[FactorRow], score: Mapping[str, float], tie: Mapping[str, float],
           params: SteadyParams) -> list[FactorRow]:
    """The pool of total-momentum winners, then the ``top`` of them by the steady key."""
    scorable = [r for r in rows if r.symbol in score and r.symbol not in EXCLUDED]
    winners = sorted(scorable, key=lambda r: (-r.momentum, r.symbol))[: params.on.pool]
    return sorted(winners, key=lambda r: (-score[r.symbol], -tie.get(r.symbol, 0.0), r.symbol))[
        : params.on.inner.top
    ]


class SteadyOvernightAllocator:
    """M0050-TOT-ON's book with a steadier overnight sort; held names get no special treatment."""

    id = "M0056"

    def lookback(self, params: Any) -> int:
        return on_lookback(_check(params).on)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params).on
        fixed = {p.market}
        if p.inner.trend is not None:
            fixed.add(p.inner.trend[0])
        return tuple(sorted(fixed))

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _targets(self, rows: list[FactorRow], grid: LegGrid | None, data_date: date,
                 params: SteadyParams) -> tuple[Target, ...]:
        if not rows or grid is None:
            return ()
        symbols = [r.symbol for r in rows]
        score = steady_scores(grid, symbols, data_date, params)
        if not score:
            return ()
        tie = tiebreak(grid, symbols, data_date, params) if params.key == "pos" else {}
        return targets_from_rows(choose(rows, score, tie, params), params.on)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if not trend_on(history, data_date, p.on.inner):
            return ()
        rows = factor_rows(history, members, data_date, p.on.inner)
        return self._targets(rows, build_legs(history, p.on.market), data_date, p)

    def prepare(self, history: Mapping[str, History]) -> OnPrepared:
        return OnPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, OnPrepared):
            raise TypeError(f"prepared must be OnPrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not trend_on(prepared.history, data_date, p.on.inner):
            return ()
        rows = prepared.factor.rows_on(members, data_date, p.on.inner)
        return self._targets(rows, prepared.grid(p.on.market), data_date, p)


STEADY = SteadyOvernightAllocator()

_ON20 = OnParams(N20, rank="total-overnight", pool=40)
_ON30 = OnParams(N30, rank="total-overnight", pool=60)


def _v(suffix: str, params: SteadyParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0056-{suffix}", family="M0056", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=STEADY, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0056",
    name="Steady overnight drift, not one big gap: overnight winners without the single-jump stocks",
    family="stock-overnight-intraday",
    source_kind="variation",
    source_ref=(
        "M0050-TOT-ON (Lou, Polk & Skouras 2019, doi:10.1016/j.jfineco.2019.03.011) with the "
        "steady-path idea of Da, Gurun & Warachka (2014) moved onto the overnight leg"
    ),
    parent_id="M0050",
    hypothesis=(
        "M0050-TOT-ON earned 15.1% a year on the owner's deposits at real fees with a 22.8% worst "
        "fall (summer 1998) and kept its edge out of sample in walk-forward (3 of 4 folds, positive "
        "in 2009-2015); M0053 showed a volatility brake fixes the fall only by giving up 4.6 points "
        "of return and the fold record. Fix the fall through selection instead. Among the 40 best "
        "12-1 momentum names (60 for a 30-name book), rank on the past year's overnight log-return "
        "sum after removing each name's 3 (TRIM3) or 5 (TRIM5) largest overnight values, or on the "
        "share of positive overnight sessions (POS), so the book holds names that drift up "
        "overnight steadily rather than ones carried by one or two earnings jumps; jump-driven "
        "names are news-sensitive and gap down together in a shock. Unbraked, monthly, equal "
        "weight, SPY 200-day gate, fractional shares at Gotrade's real fees on "
        "monthly-hold-frac-gotrade, owner's funding. Variants: TRIM3-N20, TRIM5-N20, POS-N20, "
        "TRIM3-N30, POS-N30. Success: a version with worst fall under 20% and funded return above "
        "13.7% (the real-fee residual book), and a majority of walk-forward folds beaten."
    ),
    expected_failure=(
        "The 1998 fall that sank M0050-TOT-ON was a market-wide momentum crash, not a cluster of "
        "earnings-gap reversals, so a steadier overnight path may pick nearly the same names and "
        "fall nearly as far; the pool of 40 already fixes most of the book (20 of 40), so the sort "
        "has limited room to change anything. Trimming the big gaps may also remove exactly the "
        "earnings-news drift that carries the overnight edge, so return may drop toward plain "
        "momentum's 13.8% without the fall improving. POS is the most exposed: before about 2001 "
        "many opens equal the prior close, so the share of positive nights partly measures how "
        "often a stock's open was recorded, i.e. data noise, and may tilt to the most liquid names. "
        "Thirty names should cut the fall by spreading the book but dilute return."
    ),
    candidates=(
        _v("TRIM3-N20", SteadyParams(_ON20, key="trim", k=3),
           "Top 40 by momentum, then the 20 with the largest overnight sum without its 3 biggest nights"),
        _v("TRIM5-N20", SteadyParams(_ON20, key="trim", k=5),
           "Same, removing the 5 biggest nights"),
        _v("POS-N20", SteadyParams(_ON20, key="pos"),
           "Top 40 by momentum, then the 20 that rose overnight most often"),
        _v("TRIM3-N30", SteadyParams(_ON30, key="trim", k=3),
           "Top 60 by momentum, then 30 by the overnight sum without its 3 biggest nights"),
        _v("POS-N30", SteadyParams(_ON30, key="pos"),
           "Top 60 by momentum, then the 30 that rose overnight most often"),
    ),
    seen_keys=(
        "concept:steady-overnight-drift",
        "concept:trimmed-overnight-momentum",
        "concept:overnight-up-share",
    ),
)

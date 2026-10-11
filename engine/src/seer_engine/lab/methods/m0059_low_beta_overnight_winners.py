"""M0059 — Overnight winners that move least with the market: low-beta stocks inside the overnight momentum book.

Source: a variation of M0056 (and through it M0050-TOT-ON: the 40 best 12-1 total-momentum names,
then the 20 of them whose past-year gain came most overnight; Lou, Polk & Skouras 2019). The beta
screen is the textbook market model; the low-beta tilt inside a momentum pool echoes
Frazzini & Pedersen (2014), "Betting against beta", without its leverage.
Idea: M0056 showed that re-sorting the 40 momentum winners by a steadier overnight path leaves the
summer-1998 fall untouched (22.9-25.6% across five versions), because the whole pool falls
together. This method changes what the book is exposed to instead of how the overnight sort is
done: before the overnight sort, it removes the momentum winners that move most with SPY (the
highest market beta), or it divides the overnight score by beta. High-beta winners are the ones a
market shock hits hardest; the overnight drift, which M0056 showed is spread across many ordinary
nights rather than a few jumps, should survive in the calmer names.

On data date d, beta is the OLS slope of a name's daily log return (close to close, on SPY's
calendar, back-to-back bars only) on SPY's over the ``beta_n`` sessions ending on d, with at least
80% of sessions usable. Names without a usable beta drop out of the pool. Then:

    * ``key="drop"``: of the ``pool`` highest 12-1 total-momentum names, remove the ``drop`` with
      the highest beta, then hold the ``top`` of the rest by M0050's overnight sum;
    * ``key="ratio"``: of the ``pool`` winners, hold the ``top`` by overnight sum / max(beta,
      ``floor``) when the sum is positive, and by sum * max(beta, ``floor``) when it is not, so a
      lower beta always ranks a name higher.

Equal weight, monthly, SPY 200-day gate, fractional shares at Gotrade's real fees on
``monthly-hold-frac-gotrade``: M0050-TOT-ON's frame exactly, unbraked.

Assumptions written before the run: beta is measured up to d (no skip month), because it is a
statement about exposure now, not a return signal. The floor of 0.3 keeps a near-zero or negative
beta (rare among liquid momentum winners) from producing an unbounded ratio. A pool tie on beta is
broken by symbol. A pool thinner than ``pool`` (few eligible names) never loses so many to the
beta cut that fewer than ``top`` remain: it keeps its ``top`` lowest-beta names instead. The ex-dividend gap stays inside the overnight leg, as in M0050. Every piece
reads only bars dated <= ``data_date``.
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
from seer_engine.lab.methods.m0007_residual_momentum import N20
from seer_engine.lab.methods.m0050_overnight_momentum import (
    MIN_FRAC,
    LegGrid,
    OnParams,
    OnPrepared,
    build_legs,
    leg_sums,
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

ADDED = date(2026, 10, 11)

Key = Literal["drop", "ratio"]
_KEYS: tuple[str, ...] = ("drop", "ratio")


@dataclass(frozen=True, slots=True)
class LowBetaParams:
    """``on`` is M0050's frame (screen, gate, window, pool, book size); the rest is the beta screen."""

    on: OnParams
    key: Key = "drop"
    drop: int = 10  # "drop" only: how many of the pool's highest-beta names are removed
    beta_n: int = 126  # sessions in the beta estimate, ending on d
    floor: float = 0.3  # "ratio" only: beta is floored here before it scales the overnight sum

    def __post_init__(self) -> None:
        if not isinstance(self.on, OnParams):
            raise TypeError(f"on must be OnParams, got {type(self.on).__name__}")
        if self.on.rank != "total-overnight":
            raise ValueError(f"on.rank must be 'total-overnight', got {self.on.rank!r}")
        if not isinstance(self.key, str) or self.key not in _KEYS:
            raise ValueError(f"key must be one of {_KEYS}, got {self.key!r}")
        for name in ("drop", "beta_n"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int):
                raise TypeError(f"{name} must be an int, got {type(v).__name__}")
        if self.drop < 0 or self.on.pool - self.drop < self.on.inner.top:
            raise ValueError(f"drop must leave at least top names, got pool={self.on.pool} "
                             f"drop={self.drop} top={self.on.inner.top}")
        if self.beta_n < 20:
            raise ValueError(f"beta_n must be >= 20, got {self.beta_n}")
        if isinstance(self.floor, bool) or not isinstance(self.floor, float):
            raise TypeError(f"floor must be a float, got {type(self.floor).__name__}")
        if not (0.0 < self.floor <= 1.0):
            raise ValueError(f"floor must be in (0, 1], got {self.floor}")

    def as_dict(self) -> dict[str, str]:
        out = {"key": self.key, "drop": str(self.drop), "beta_n": str(self.beta_n),
               "floor": repr(self.floor)}
        for name, v in self.on.as_dict().items():
            out[f"on.{name}"] = v
        return out


def _check(params: object) -> LowBetaParams:
    if not isinstance(params, LowBetaParams):
        raise TypeError(f"params must be LowBetaParams, got {type(params).__name__}")
    return params


def lowbeta_lookback(params: LowBetaParams) -> int:
    return max(on_lookback(params.on), params.beta_n + 2)


def betas(grid: LegGrid, symbols: list[str], data_date: date, params: LowBetaParams) -> dict[str, float]:
    """Market beta per usable symbol over the ``beta_n`` sessions ending on d (SPY's own row)."""
    market = params.on.market
    if market not in grid.row:
        return {}
    d = as_day(data_date)
    j = int(np.searchsorted(grid.dates, d, side="right")) - 1
    if j < 0 or grid.dates[j] != d:
        return {}
    f0 = j - params.beta_n + 1
    if f0 < 0:
        return {}
    names = [s for s in symbols if s in grid.row]
    if not names:
        return {}
    m = grid.row[market]
    x = grid.night[m, f0 : j + 1] + grid.day[m, f0 : j + 1]
    idx = np.asarray([grid.row[s] for s in names], dtype=np.int64)
    y = grid.night[idx, f0 : j + 1] + grid.day[idx, f0 : j + 1]
    ok = np.isfinite(y) & np.isfinite(x)[None, :]
    n = ok.sum(axis=1).astype(np.float64)
    xs = np.where(ok, x[None, :], 0.0)
    ys = np.where(ok, y, 0.0)
    sx, sy = xs.sum(axis=1), ys.sum(axis=1)
    sxx, sxy = (xs * xs).sum(axis=1), (xs * ys).sum(axis=1)
    den = n * sxx - sx * sx
    good = (n >= max(3, math.ceil(MIN_FRAC * params.beta_n))) & (den > 0.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        beta = np.where(good, (n * sxy - sx * sy) / np.where(good, den, 1.0), np.nan)
    out: dict[str, float] = {}
    for i in np.flatnonzero(good & np.isfinite(beta)):
        out[names[int(i)]] = float(beta[int(i)])
    return out


def choose(rows: list[FactorRow], on: Mapping[str, float], beta: Mapping[str, float],
           params: LowBetaParams) -> list[FactorRow]:
    """The pool of total-momentum winners, cut or re-scored by beta, then the ``top`` by overnight."""
    p = params.on
    scorable = [r for r in rows if r.symbol in on and r.symbol in beta and r.symbol not in EXCLUDED]
    winners = sorted(scorable, key=lambda r: (-r.momentum, r.symbol))[: p.pool]
    if params.key == "drop":
        keep = max(len(winners) - params.drop, min(p.inner.top, len(winners)))
        kept = sorted(winners, key=lambda r: (beta[r.symbol], r.symbol))[:keep]
        return sorted(kept, key=lambda r: (-on[r.symbol], r.symbol))[: p.inner.top]

    def ratio(r: FactorRow) -> float:
        b = max(beta[r.symbol], params.floor)
        s = on[r.symbol]
        return s / b if s > 0.0 else s * b

    return sorted(winners, key=lambda r: (-ratio(r), r.symbol))[: p.inner.top]


class LowBetaOvernightAllocator:
    """M0050-TOT-ON's book with its highest-beta winners screened out; held names get no favour."""

    id = "M0059"

    def lookback(self, params: Any) -> int:
        return lowbeta_lookback(_check(params))

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
                 params: LowBetaParams) -> tuple[Target, ...]:
        if not rows or grid is None:
            return ()
        symbols = [r.symbol for r in rows]
        on, _ = leg_sums(grid, symbols, data_date, params.on)
        if not on:
            return ()
        beta = betas(grid, symbols, data_date, params)
        if not beta:
            return ()
        return targets_from_rows(choose(rows, on, beta, params), params.on)

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


LOWBETA = LowBetaOvernightAllocator()

_ON40 = OnParams(N20, rank="total-overnight", pool=40)
_ON60 = OnParams(N20, rank="total-overnight", pool=60)


def _v(suffix: str, params: LowBetaParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0059-{suffix}", family="M0059", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=LOWBETA, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0059",
    name="Overnight winners that move least with the market: low-beta stocks inside the overnight momentum book",
    family="stock-overnight-intraday",
    source_kind="variation",
    source_ref=(
        "M0056 / M0050-TOT-ON (Lou, Polk & Skouras 2019, doi:10.1016/j.jfineco.2019.03.011) with a "
        "market-beta screen on the momentum pool, after Frazzini & Pedersen (2014), Betting against beta"
    ),
    parent_id="M0056",
    hypothesis=(
        "M0056 showed that re-sorting the 40 strongest momentum names by a steadier overnight path "
        "leaves the 23% summer-1998 fall untouched (22.9-25.6% across five versions) while keeping "
        "13-15% a year, because the whole pool falls together in a momentum crash. Change the crash "
        "exposure instead: among the 40 best 12-1 momentum names, drop the 10 (DROP10) or 20 "
        "(DROP20) with the highest 126-session daily beta to SPY and keep the 20 with the largest "
        "overnight sum; or rank the 40 on overnight sum divided by beta floored at 0.3 (RATIO); or "
        "drop the 10 highest-beta names on a 252-session beta (DROP10-B252, the estimate-length "
        "check); or start from the 60 best and drop the 30 highest-beta (P60-DROP30). "
        "High-beta momentum names carried the 1998 and 2011 drops; low-beta winners should keep "
        "the overnight drift (which M0056 showed is broad, not jump-driven) with a smaller fall. "
        "Unbraked, monthly, equal weight, SPY 200-day gate, 20 names, fractional shares at "
        "Gotrade's real fees on monthly-hold-frac-gotrade, owner's funding. Published 2019 (the "
        "overnight split) and 2014 (betting against beta): the dev window ends 2015 and predates "
        "the overnight paper's crowd. Success: a version with worst fall under 20%, funded return "
        "above 13.7% (the real-fee residual book), a positive edge on SPY in 2009-2015 and a "
        "majority of walk-forward folds kept."
    ),
    expected_failure=(
        "The 1998 shock was a momentum crash in which the strong stocks fell together whatever "
        "their beta: a 126-session beta measured in a calm first half of 1998 may not rank the "
        "names that later fell hardest, so the fall may barely move, as it did for M0056. A low-"
        "beta cut also leans the book toward defensive, slower names, which costs return in the "
        "2003-2007 and 2009-2015 rallies, exactly the years SPY's big-company drift is hardest to "
        "beat; DROP20 and P60-DROP30 are most exposed to that. RATIO can be dominated by the beta "
        "floor and pick only utilities-like names. Even if one version clears the fall, it is "
        "still a 12-month momentum book: the hard gate's behaviour rule may read it as kin of the "
        "test-failed momentum books (residual correlation 0.85 or more), so a dev pass may not be "
        "promotable. And the overnight edge is a published anomaly that inverted from 2018 for "
        "M0050, so a good dev result is likely to fade out of sample."
    ),
    candidates=(
        _v("DROP10", LowBetaParams(_ON40, key="drop", drop=10),
           "Top 40 by momentum, drop the 10 highest-beta, then 20 by overnight sum"),
        _v("DROP20", LowBetaParams(_ON40, key="drop", drop=20),
           "Top 40 by momentum, keep the 20 lowest-beta (the overnight sort no longer chooses)"),
        _v("RATIO", LowBetaParams(_ON40, key="ratio"),
           "Top 40 by momentum, then 20 by overnight sum divided by beta (floored at 0.3)"),
        _v("DROP10-B252", LowBetaParams(_ON40, key="drop", drop=10, beta_n=252),
           "DROP10 with beta measured over a year instead of six months"),
        _v("P60-DROP30", LowBetaParams(_ON60, key="drop", drop=30),
           "Top 60 by momentum, drop the 30 highest-beta, then 20 by overnight sum"),
    ),
    seen_keys=(
        "concept:low-beta-overnight-momentum",
        "concept:beta-screened-momentum-pool",
    ),
)

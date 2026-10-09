"""M0064 — Buy the laggard of a pair that usually moves together: the long side of pairs trading.

Source: Gatev, Goetzmann & Rouwenhorst (2006), Pairs trading: performance of a relative-value
arbitrage rule, Rev. Financial Studies 19(3), doi:10.1093/rfs/hhj020; Do & Faff (2010), Does
simple pairs trading still work?, Financial Analysts Journal 66(4).
Idea: two stocks whose prices tracked each other closely for a year tend to come back together
after they drift apart. Gatev et al. buy the cheap one and short the dear one; Gotrade is long
only, so this book holds the cheap leg alone and parks the rest of the money in SPY.

The rule, on data date d, with the trading period the calendar half-year (Jan-Jun or Jul-Dec)
that contains d -- Gatev's six-month trading period -- and the formation window the ``form_n``
market sessions just before it:

    * the universe is F4's screen on d (point-in-time members, price >= $5, 20-day dollar volume
      above 20M) whose returns are complete over the whole formation window;
    * each name's formation path is its cumulative return index; each name is matched with the
      partner whose path is nearest (sum of squared differences), and the ``pairs`` closest
      matches are the pairs for the period. ``sigma`` is the standard deviation of the pair's
      path difference over formation;
    * from the first session of the trading period both paths restart at 1. Day by day through
      d, a pair opens when its gap reaches ``entry`` sigmas, and closes when the gap crosses zero
      (converged), reaches ``stop`` sigmas (stopped), or has been open ``max_age`` sessions
      (timed out). After a stop or a time-out the pair stays shut until its gap next crosses zero;
    * the laggard of each pair open on d is held at ``1 / max_legs`` of the book, widest gaps
      first, at most ``max_legs`` legs; with ``park="spy"`` the rest is SPY, with ``"cash"`` it
      is cash; behind ``inner.trend`` everything is cash while SPY is below its 200-day average.

The state machine is replayed from the period's first session every time, so nothing is carried
between calls and ``held`` is never read. Reads only grid columns dated <= d.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from typing import Any, Literal

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import (
    N20,
    N20_NOTREND,
    ResidPrepared,
    ReturnGrid,
    build_grid,
)
from seer_engine.sim.book import Target, equal_weight, to_weight
from seer_engine.sim.rules import WEEKLY_HOLD
from seer_engine.strategies.allocator import target_from_close
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

ADDED = date(2026, 10, 9)
PERIOD_SLACK = 135  # sessions a half-year trading period can span, with room to spare

# Weekly decisions in fractional shares at Gotrade's real fees. There is no weekly real-fee preset
# yet, so this runs on dev but `promote` would need one (feature-wish if it wins).
WEEKLY_HOLD_FRAC_GOTRADE = replace(WEEKLY_HOLD, id="weekly-hold-frac-gotrade", fractional=True,
                                   cost_model="gotrade")

Park = Literal["spy", "cash"]
_PARKS: tuple[str, ...] = ("spy", "cash")


# --------------------------------------------------------------------------- params


@dataclass(frozen=True, slots=True)
class PairsParams:
    """``inner`` is F4's screen and trend gate (its ``top`` and ``rank`` select nothing here)."""

    inner: FactorParams
    pairs: int = 20  # closest matches traded per period
    max_legs: int = 20  # slots; each open leg is 1 / max_legs of the book
    entry: Decimal = Decimal("2")  # gap in formation sigmas that opens a pair
    stop: Decimal | None = Decimal("4")  # gap that stops a pair out (None = no stop)
    max_age: int | None = 40  # sessions a pair may stay open (None = until convergence or period end)
    form_n: int = 252  # formation window, sessions
    park: Park = "spy"
    market: str = "SPY"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        for name, lo in (("pairs", 1), ("max_legs", 1), ("form_n", 20)):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int):
                raise TypeError(f"{name} must be an int, got {type(v).__name__}")
            if v < lo:
                raise ValueError(f"{name} must be >= {lo}, got {v}")
        if not isinstance(self.entry, Decimal) or not self.entry.is_finite() or self.entry <= 0:
            raise ValueError(f"entry must be a positive Decimal, got {self.entry!r}")
        if self.stop is not None and (not isinstance(self.stop, Decimal) or not self.stop.is_finite()
                                      or self.stop <= self.entry):
            raise ValueError(f"stop must be None or a Decimal above entry, got {self.stop!r}")
        if self.max_age is not None and (isinstance(self.max_age, bool) or not isinstance(self.max_age, int)
                                         or self.max_age < 1):
            raise ValueError(f"max_age must be None or an int >= 1, got {self.max_age!r}")
        if not isinstance(self.park, str) or self.park not in _PARKS:
            raise ValueError(f"park must be one of {_PARKS}, got {self.park!r}")
        if not isinstance(self.market, str) or not self.market:
            raise ValueError(f"market must be a non-empty symbol, got {self.market!r}")

    def as_dict(self) -> dict[str, str]:
        out = {
            "pairs": str(self.pairs),
            "max_legs": str(self.max_legs),
            "entry": str(self.entry),
            "stop": "none" if self.stop is None else str(self.stop),
            "max_age": "none" if self.max_age is None else str(self.max_age),
            "form_n": str(self.form_n),
            "park": self.park,
            "market": self.market,
        }
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> PairsParams:
    if not isinstance(params, PairsParams):
        raise TypeError(f"params must be PairsParams, got {type(params).__name__}")
    return params


def pairs_lookback(params: PairsParams) -> int:
    return max(factor_lookback(params.inner), params.form_n + PERIOD_SLACK + 2)


# --------------------------------------------------------------------------- the signal


def _period_start(d: date) -> date:
    return date(d.year, 1 if d.month <= 6 else 7, 1)


def open_legs(grid: ReturnGrid, symbols: list[str], data_date: date,
              params: PairsParams) -> list[tuple[float, str]]:
    """``(gap in sigmas, laggard)`` for every pair open at the ``data_date`` close, widest first.

    Reads only grid columns dated <= ``data_date``.
    """
    day = as_day(data_date)
    j = int(np.searchsorted(grid.dates, day, side="right")) - 1
    if j < 0 or grid.dates[j] != day:
        return []
    s0 = int(np.searchsorted(grid.dates, as_day(_period_start(data_date)), side="left"))
    f0 = s0 - params.form_n
    if f0 < 0 or s0 > j:
        return []
    names = [s for s in symbols if s in grid.row and s not in EXCLUDED]
    if len(names) < 2:
        return []
    idx = np.asarray([grid.row[s] for s in names], dtype=np.int64)
    form = grid.rets[idx, f0:s0]
    full = np.all(np.isfinite(form), axis=1)
    if int(full.sum()) < 2:
        return []
    names = [n for n, ok in zip(names, full, strict=True) if ok]
    idx = idx[full]
    paths = np.cumprod(1.0 + form[full], axis=1)  # (n, form_n), each name's index over formation

    sq = (paths * paths).sum(axis=1)
    dist = sq[:, None] + sq[None, :] - 2.0 * (paths @ paths.T)
    np.fill_diagonal(dist, np.inf)
    nearest = np.argmin(dist, axis=1)
    seen: set[tuple[int, int]] = set()
    cands: list[tuple[float, int, int]] = []
    for a in range(len(names)):
        b = int(nearest[a])
        key = (min(a, b), max(a, b))
        if key in seen:
            continue
        seen.add(key)
        cands.append((float(dist[key[0], key[1]]), key[0], key[1]))
    cands.sort(key=lambda t: (t[0], names[t[1]], names[t[2]]))
    chosen = cands[: params.pairs]
    if not chosen:
        return []
    ia = np.asarray([c[1] for c in chosen], dtype=np.int64)
    ib = np.asarray([c[2] for c in chosen], dtype=np.int64)
    sigma = np.std(paths[ia] - paths[ib], axis=1)

    trade = np.nan_to_num(grid.rets[idx, s0 : j + 1], nan=0.0)  # a missing day carries the price
    run = np.cumprod(1.0 + trade, axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        gap = (run[ia] - run[ib]) / sigma[:, None]  # > 0: b lags; < 0: a lags
    gap = np.where(np.isfinite(gap), gap, 0.0)

    entry = float(params.entry)
    stop = math.inf if params.stop is None else float(params.stop)
    max_age = params.max_age
    npairs = len(chosen)
    side = np.zeros(npairs)  # +1 or -1 while open, 0 when flat
    locked = np.zeros(npairs)  # side a stopped or timed-out pair was shut on, 0 when free
    age = np.zeros(npairs, dtype=np.int64)
    for t in range(gap.shape[1]):
        g = gap[:, t]
        for k in range(npairs):
            if side[k] != 0.0:
                age[k] += 1
                if side[k] * g[k] <= 0.0:
                    side[k] = 0.0
                elif abs(g[k]) >= stop or (max_age is not None and age[k] >= max_age):
                    locked[k] = side[k]
                    side[k] = 0.0
            elif locked[k] != 0.0:
                if locked[k] * g[k] <= 0.0:
                    locked[k] = 0.0
            if side[k] == 0.0 and locked[k] == 0.0 and abs(g[k]) >= entry:
                side[k] = 1.0 if g[k] > 0.0 else -1.0
                age[k] = 0

    best: dict[str, float] = {}
    last = gap[:, -1]
    for k in range(npairs):
        if side[k] == 0.0:
            continue
        lag = names[int(ib[k])] if side[k] > 0 else names[int(ia[k])]
        best[lag] = max(best.get(lag, 0.0), abs(float(last[k])))
    return sorted(((v, s) for s, v in best.items()), key=lambda t: (-t[0], t[1]))


def build_targets(rows: list[FactorRow], legs: list[tuple[float, str]], history: Mapping[str, History],
                  data_date: date, params: PairsParams) -> tuple[Target, ...]:
    close = {r.symbol: r.close for r in rows}
    w = equal_weight(params.max_legs)
    out: list[Target] = []
    for _, s in legs:
        if len(out) >= params.max_legs:
            break
        t = target_from_close(s, close[s], w)
        if t is not None:
            out.append(t)
    if params.park == "spy":
        rest = Decimal(1) - w * len(out)
        m = history.get(params.market)
        i = None if m is None else m.index_of(data_date)
        if rest > 0 and m is not None and i is not None:
            t = target_from_close(params.market, float(m.close[i]), to_weight(rest))
            if t is not None:
                out.append(t)
    return tuple(out)


# --------------------------------------------------------------------------- the allocator


class PairsLaggardAllocator:
    """The cheap leg of every open pair, the rest in SPY (or cash), behind F4's trend gate."""

    id = "M0064"

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

    def _targets(self, history: Mapping[str, History], rows: list[FactorRow], grid: ReturnGrid | None,
                 data_date: date, params: PairsParams) -> tuple[Target, ...]:
        if grid is None:
            return ()
        legs = open_legs(grid, [r.symbol for r in rows], data_date, params)
        return build_targets(rows, legs, history, data_date, params)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if not trend_on(history, data_date, p.inner):
            return ()
        rows = factor_rows(history, members, data_date, p.inner)
        return self._targets(history, rows, build_grid(history, p.market), data_date, p)

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
        return self._targets(prepared.history, rows, prepared.grid(p.market), data_date, p)


PAIRS = PairsLaggardAllocator()


def _v(suffix: str, params: PairsParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0064-{suffix}", family="M0064", rules=WEEKLY_HOLD_FRAC_GOTRADE,
                     allocator=PAIRS, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0064",
    name="Buy the laggard of a pair that usually moves together: the long side of pairs trading",
    family="stock-pairs-relative-value",
    source_kind="paper",
    source_ref=(
        "Gatev, Goetzmann & Rouwenhorst (2006), Pairs trading: performance of a relative-value "
        "arbitrage rule, Rev. Financial Studies 19(3), doi:10.1093/rfs/hhj020; Do & Faff (2010), "
        "Does simple pairs trading still work?, FAJ 66(4)"
    ),
    parent_id=None,
    hypothesis=(
        "Gatev et al. (published 2006, working paper from 1999) match each stock with the partner "
        "whose normalised price path tracked it most closely over a 12-month formation window, "
        "trade the 20 closest pairs for the next six months, and open a pair when its gap passes "
        "two formation standard deviations, earning about 11% a year 1962-2002 before costs; Do "
        "and Faff find the profit fell after 2002 but held up in turbulent years such as "
        "2008-2009. Gotrade is long only, so this book holds only the cheap leg: every week, among "
        "F4's screened point-in-time members, pairs are formed on the 252 sessions before the "
        "current half-year, and the laggard of each open pair is held at 5% of the book until the "
        "gap closes, the gap reaches 4 sigmas (stop), or 40 sessions pass, at most 20 legs, the "
        "rest of the money in SPY, everything in cash while SPY is under its 200-day average. The "
        "signal is relative reversal, the opposite of momentum, so its moves should be unlike the "
        "failed momentum books. Fractional shares at Gotrade's real fees on a weekly book rule "
        "(weekly-hold-frac-gotrade, no promotion preset yet). Variants: P20 (Gatev's 20 pairs); "
        "P50 (50 pairs, more legs open, more of the book in stocks); P50-CASH (P50 with the rest in "
        "cash: the legs alone, does the laggard beat what SPY would have done with that money?); "
        "P50-K15 (opens at 1.5 sigmas: more, smaller bets); P50-NOGATE (no trend gate: what the "
        "gate is worth). Success: a SPY-parked variant beats total-return SPY on the owner's "
        "deposits with a worst fall under 20%, and P50-CASH shows the legs earn more than SPY per "
        "dollar invested. Judge 2009-2015 first."
    ),
    expected_failure=(
        "The long leg alone carries the market and little of the spread: most of Gatev's profit "
        "came from the short leg falling, and the laggard is often lagging for a reason (bad "
        "news), so the cheap legs roughly match SPY and the book becomes SPY minus fees. With only "
        "a handful of pairs open at a time the book is mostly SPY anyway, so any edge is diluted "
        "to near nothing. The store holds no delisted names, so laggards that went on to die are "
        "missing and the result is flattered (run survivorship_coverage). Gotrade's per-order fees "
        "on 5% legs held a few weeks, plus the weekly SPY resize, eat what is left. The trend gate "
        "will keep the worst fall near 20% but whipsaw in 2010-2012 and 2015 and cost the "
        "2009-2015 era. A published 2006 rule that Do and Faff already saw fading after 2002 is "
        "likely to look weakest in the best-covered, most recent years."
    ),
    candidates=(
        _v("P20", PairsParams(N20, pairs=20),
           "Gatev's 20 closest pairs, open at 2 sigmas, 4-sigma stop, 40-session limit, rest in SPY"),
        _v("P50", PairsParams(N20, pairs=50),
           "50 closest pairs: more legs open, more of the book in the laggards"),
        _v("P50-CASH", PairsParams(N20, pairs=50, park="cash"),
           "P50 with the rest in cash: the legs alone, measured against SPY"),
        _v("P50-K15", PairsParams(N20, pairs=50, entry=Decimal("1.5")),
           "P50 opening at 1.5 sigmas: more, smaller divergences"),
        _v("P50-NOGATE", PairsParams(N20_NOTREND, pairs=50),
           "P50 with no SPY 200-day gate: what the gate is worth"),
    ),
    seen_keys=(
        "concept:pairs-trading",
        "concept:distance-method-pairs",
        "concept:relative-value-arbitrage",
        "doi:10.1093/rfs/hhj020",
    ),
)

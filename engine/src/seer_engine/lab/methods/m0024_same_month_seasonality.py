"""M0024 — Same-month seasonality: buy the stocks that did best in this calendar month last year.

Source: Heston & Sadka (2008), "Seasonality in the cross-section of stock returns", Journal of
Financial Economics 87(2), doi:10.1016/j.jfineco.2007.02.003; Keloharju, Linnainmaa & Nyberg
(2016), "Return seasonalities", Journal of Finance 71(4).
Idea: a stock's return in a calendar month tends to repeat in that same month in later years,
apart from momentum, size and industry; the one-year lag is the strongest single lag in the
paper. Every lab book so far ranks on the past year's trend; a same-month rank picks names for a
reason that has little to do with trend, so it is a candidate second engine whose good and bad
months need not line up with momentum's.

Scope, decided before any run. The reserved idea averaged lags of 2-20 years. The lab cannot
express that: an allocator's ``lookback`` is both how far back it may read any stock (the
contract cuts histories to it) and how many SPY bars must exist before the window opens, so a
20-year memory would open the window in 2013 and fail the two-year smoke fixture. What fits is
the one-year lag (13 months of bars), which is what this method tests. The multi-year average
stays an open idea until the lab can warm a long member memory without moving the window start.

Mechanics. On the data date d, the target month T is the month of the next NYSE session (on a
monthly rank d is the last session of T-1). A month's return is its last close over the
previous month's last close, from the stock's own bars, kept only when the two months are
consecutive. For each member passing F4's screen (price, dollar volume, a 12-1 momentum and a
60-day vol it can compute):

    * ``same``: score = the return of month T-12 (the same calendar month last year); a name
      without that month scores 0;
    * ``net``: score = that return minus the mean of the other eleven months T-11..T-1 the stock
      has (Keloharju et al.'s seasonal-minus-non-seasonal split): it keeps the same-month part and
      strips last year's trend, which ``same`` shares with 12-1 momentum.

The ``top`` highest scores are held equal-weight for the month behind the SPY 200-day gate, as
F4. ``ranksum`` instead sums each name's position in the seasonal order and in M0007-N20-RAW's
residual-momentum order. Reads only bars dated <= d.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np

from seer_engine import dates
from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import (
    FACTOR_SYMBOLS,
    ResidParams,
    ResidPrepared,
    build_grid,
    resid_lookback,
    residual_scores,
)
from seer_engine.lab.methods.m0011_raw_residual_own_vol import RESIDVOL, ResidVolParams
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD
from seer_engine.strategies.allocator import BLEND, BlendParams, BlendPart, target_from_close
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

ADDED = date(2026, 10, 7)


SEASON_BARS = 23 * 13 + 5  # 13 calendar months of sessions at most, plus slack


@dataclass(frozen=True, slots=True)
class SeasonParams:
    """``inner`` is F4's screen, trend gate, book size and weighting; the rest is the seasonal key."""

    inner: FactorParams
    net: bool = False  # subtract the mean of the other eleven months of the last year
    ranksum: bool = False  # sum of seasonal and raw residual-momentum rank positions
    market: str = "SPY"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if not isinstance(self.net, bool):
            raise TypeError("net must be a bool")
        if not isinstance(self.ranksum, bool):
            raise TypeError("ranksum must be a bool")
        if not isinstance(self.market, str) or not self.market:
            raise ValueError(f"market must be a non-empty symbol, got {self.market!r}")

    def resid(self) -> ResidParams:
        """The ranksum leg: M0007-N20-RAW's model (unscaled cumulative residual)."""
        return ResidParams(self.inner, scaled=False, market=self.market)

    def as_dict(self) -> dict[str, str]:
        out = {"lag": "12m", "net": "yes" if self.net else "no",
               "ranksum": "yes" if self.ranksum else "no", "market": self.market}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> SeasonParams:
    if not isinstance(params, SeasonParams):
        raise TypeError(f"params must be SeasonParams, got {type(params).__name__}")
    return params


def season_lookback(params: SeasonParams) -> int:
    lb = max(factor_lookback(params.inner), SEASON_BARS)
    if params.ranksum:
        lb = max(lb, resid_lookback(params.resid()))
    return lb


# --------------------------------------------------------------------------- the seasonal score


def month_table(h: History) -> dict[int, float]:
    """{month id (months since 1970-01): that month's close-to-close return} from ``h``'s bars.

    A month's return is its last close over the previous month's last close, kept only when the
    two months are consecutive. The final month in ``h`` may be partial; callers read only
    months that end on or before their data date.
    """
    if len(h) < 2:
        return {}
    months = h.dates.astype("datetime64[M]").astype(np.int64)
    last = np.flatnonzero(np.diff(months) != 0)  # the last bar of every month but the final one
    last = np.append(last, len(months) - 1)
    m = months[last]
    c = h.close[last]
    out: dict[int, float] = {}
    for k in range(1, len(last)):
        if m[k] - m[k - 1] != 1:
            continue
        prev, cur = float(c[k - 1]), float(c[k])
        if prev > 0.0 and np.isfinite(prev) and np.isfinite(cur):
            out[int(m[k])] = cur / prev - 1.0
    return out


def target_month(data_date: date) -> int:
    """The month id the decision on ``data_date`` holds for: the next session's month."""
    nxt = dates.next_session(data_date)
    return (nxt.year - 1970) * 12 + (nxt.month - 1)


def season_score(table: Mapping[int, float], month: int, params: SeasonParams) -> float:
    same = table.get(month - 12, 0.0)
    if not params.net:
        return same
    others = [table[month - k] for k in range(1, 12) if month - k in table]
    return same - (float(np.mean(others)) if others else 0.0)


def choose(rows: list[FactorRow], season: Mapping[str, float], resid: Mapping[str, float] | None,
           params: SeasonParams) -> tuple[Target, ...]:
    pool = [r for r in rows if r.symbol in season and r.symbol not in EXCLUDED]
    if resid is not None:
        pool = [r for r in pool if r.symbol in resid]
    by_season = sorted(pool, key=lambda r: (-season[r.symbol], r.symbol))
    if resid is None:
        chosen = by_season[: params.inner.top]
    else:
        spos = {r.symbol: k for k, r in enumerate(by_season)}
        by_resid = sorted(pool, key=lambda r: (-resid[r.symbol], r.symbol))
        rpos = {r.symbol: k for k, r in enumerate(by_resid)}
        chosen = sorted(pool, key=lambda r: (spos[r.symbol] + rpos[r.symbol], spos[r.symbol],
                                             r.symbol))[: params.inner.top]
    out: list[Target] = []
    for row, weight in zip(chosen, factor_weights(chosen, params.inner), strict=True):
        if weight is None:
            continue
        target = target_from_close(row.symbol, row.close, weight)
        if target is not None:
            out.append(target)
    return tuple(out)


@dataclass(frozen=True, slots=True, eq=False)
class SeasonPrepared:
    """M0007's prepared columns plus a lazily built month table per symbol."""

    resid: ResidPrepared = field(repr=False)
    tables: dict[str, dict[int, float]] = field(default_factory=dict, repr=False)

    def table(self, symbol: str) -> dict[int, float]:
        if symbol not in self.tables:
            self.tables[symbol] = month_table(self.resid.history[symbol])
        return self.tables[symbol]


def _scores(tables: Any, rows: list[FactorRow], month: int, params: SeasonParams) -> dict[str, float]:
    return {r.symbol: season_score(tables(r.symbol), month, params) for r in rows}


class SeasonAllocator:
    """F4's book ranked on same-calendar-month returns in past years (or its ranksum with RAW).

    Held symbols get no special treatment: the targets are exactly the new top set.
    """

    id = "M0024"

    def lookback(self, params: Any) -> int:
        return season_lookback(_check(params))

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        out = set(FACTOR_SYMBOLS(p.inner)) | {p.market}  # SPY sets the window either way
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
        month = target_month(data_date)
        season = _scores(lambda s: month_table(history[s].upto(data_date)), rows, month, p)
        resid = None
        if p.ranksum:
            grid = build_grid(history, p.market)
            if grid is None:
                return ()
            resid = residual_scores(grid, [r.symbol for r in rows], data_date, p.resid())
        return choose(rows, season, resid, p)

    def prepare(self, history: Mapping[str, History]) -> SeasonPrepared:
        return SeasonPrepared(ResidPrepared(history, prepare_factor(history)))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, SeasonPrepared):
            raise TypeError(f"prepared must be SeasonPrepared, got {type(prepared).__name__}")
        p = _check(params)
        rp = prepared.resid
        if not trend_on(rp.history, data_date, p.inner):
            return ()
        rows = rp.factor.rows_on(members, data_date, p.inner)
        if not rows:
            return ()
        season = _scores(prepared.table, rows, target_month(data_date), p)
        resid = None
        if p.ranksum:
            grid = rp.grid(p.market)
            if grid is None:
                return ()
            resid = residual_scores(grid, [r.symbol for r in rows], data_date, p.resid())
        return choose(rows, season, resid, p)


SEASON = SeasonAllocator()

TREND = ("SPY", 200)
N20 = FactorParams(rank="momentum", top=20, trend=TREND)  # F4-MOM12-N20-TREND's screen
N40 = FactorParams(rank="momentum", top=40, trend=TREND)
N20_NOTREND = FactorParams(rank="momentum", top=20, trend=None)
RM = ResidVolParams(ResidParams(N20, scaled=False), Decimal("0.14"), 21)  # M0011-RAW20-TV14-N21

SAME20 = SeasonParams(N20)


def _v(suffix: str, allocator: Any, params: Any, rationale: str, rules=MONTHLY_HOLD) -> Candidate:
    return Candidate(id=f"M0024-{suffix}", family="M0024", rules=rules, allocator=allocator,
                     params=params, rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0024",
    name="Same-month seasonality: buy the stocks that did best in this calendar month last year",
    family="stock-seasonality",
    source_kind="paper",
    source_ref=(
        "Heston & Sadka (2008), Seasonality in the cross-section of stock returns, J. Financial "
        "Economics 87(2), doi:10.1016/j.jfineco.2007.02.003; Keloharju, Linnainmaa & Nyberg "
        "(2016), Return seasonalities, J. Finance 71(4)"
    ),
    hypothesis=(
        "Heston-Sadka find a stock's return in a calendar month repeats in the same month a year "
        "later (their strongest single lag), apart from momentum, size and industry. Each month, "
        "ranking F4's screened members by last year's same-month return and holding the top 20 "
        "equal-weight behind the SPY 200-day gate picks names largely unrelated to past-year trend. "
        "Alone it should roughly match or modestly beat SPY total return on 1996-2015 (CAGR within "
        "about 2 points of SPY's, max DD under 20% thanks to the gate, PF above 1.3, well over 100 "
        "trades). The net score (same month minus the other eleven) should isolate the seasonal "
        "part and do at least as well. Its real test is as a second engine: a 50/50 blend with RM "
        "(M0011-RAW20-TV14-N21) should keep most of RM's return and cut its worst fall because the "
        "two books' losing months do not line up; the ranksum with residual momentum should beat "
        "RAW alone on MAR."
    ),
    expected_failure=(
        "A single past month is one noisy draw: in large caps the same-month effect is small and "
        "concentrated in January and in small, illiquid names our screen removes, so the top 20 "
        "by one month's return are mostly high-volatility names that had one big month. Turnover "
        "is near total every month, so the 0.1% cost per side takes ~2.4 points a year. Expect the "
        "stand-alone books to trail SPY (CAGR +4-8%) with worse falls than momentum (20-30% in "
        "2000-02 and 2008 before the gate reacts), the ranksum to land below RAW, and the blend to "
        "dilute RM's return without a material drawdown cut."
    ),
    candidates=(
        _v("SAME-N20", SEASON, SAME20,
           "Top-20 by last year's same-month return, SPY 200-day gate: the paper's lag-12 signal"),
        _v("NET-N20", SEASON, SeasonParams(N20, net=True),
           "Top-20 by same month minus the mean of the other eleven months: seasonality without trend"),
        _v("SAME-N40", SEASON, SeasonParams(N40),
           "Top-40: the score is one noisy month, so a broader book may hold the signal with less luck"),
        _v("SAME-N20-NOTREND", SEASON, SeasonParams(N20_NOTREND),
           "No market gate: the bare engine, to see what the signal does through 2000-02 and 2008"),
        _v("SAME-N20-RANKSUM", SEASON, SeasonParams(N20, ranksum=True),
           "Top-20 by summed rank of same-month return and raw residual momentum (M0007-N20-RAW)"),
        _v("SAME-N20-BLEND-RM", BLEND,
           BlendParams((BlendPart(SEASON, SAME20, Decimal("0.5")), BlendPart(RESIDVOL, RM, Decimal("0.5")))),
           "Half the equity in SAME-N20, half in RM (M0011-RAW20-TV14-N21): the second-engine test"),
    ),
    seen_keys=(
        "concept:same-month-seasonality",
        "concept:return-seasonality",
        "doi:10.1016/j.jfineco.2007.02.003",
    ),
)

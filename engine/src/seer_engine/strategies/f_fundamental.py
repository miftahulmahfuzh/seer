"""Fundamental cross-sectional factors over index members (Gap B, R6).

One allocator, ``FUNDAMENTAL`` (id ``"FND"``). A sibling of ``f_factor``, not a rewrite of it:
``f_factor`` ranks on price history alone, this one ranks on point-in-time SEC filings.

THE PANEL AND THE TWO PATHS. Fundamentals do not live in ``Mapping[str, History]``, so they
cannot reach the allocator through ``prepare(history)``. They reach it through
``prepare_market(market)``, which reads ``market.fundamentals``. The consequence is explicit
and load-bearing:

    targets(history, ...) and prepare(history) see NO panel. With no panel no symbol has
    fundamental features, so no symbol is eligible, so both return (). That is the correct
    reading of "nothing is known about any filer", not a bug and not a silent zero.

    The live path is prepare_market(market) -> targets_prepared(prepared, ...).

``FundamentalPrepared`` is therefore a thin holder of ``(history, panel)``, and
``targets_prepared`` delegates to the same ``targets_with_panel`` the single-window path calls.
The Allocator contract's P4 identity
``targets_prepared(prepare(H), M, d, held, p) == targets(H.upto(d), M, d, held, p)`` then holds
by construction (both sides run the empty-panel case), and the identity that actually matters,
``targets_prepared(prepare_market(Market), ...) == targets_with_panel(H.upto(d), panel, ...)``,
holds bit for bit for the same reason. Defining ``prepare_market`` is what makes this class
satisfy phase 6's ``MarketAware`` protocol, which is how ``dev.py``'s ``prepare_for`` routes to
the live path and how the shared lab gate knows which identity to check.

On ``data_date`` d, a symbol is **eligible** when all of these hold:
    it is a member on d and is not ``"SPY"``; it has a bar dated d and at least
    ``fundamental_lookback(params)`` bars through d; close >= ``min_price``; its 20-day mean
    close x volume > ``min_dollar_volume`` (strict); the panel has a fact for it filed on or
    before d and no more than ``max_stale_days`` days before d; and every factor the chosen
    ranking reads (``factors_read(params)``) is finite.
A symbol with filings but no bar dated d - the 133 ever-members with no price history (Gap A) -
fails the bar test and is simply absent from the eligible set. It is never ranked, never
weighted, and never treated as a zero. A symbol with bars but no filings fails the panel test
the same way.

Features, all read from ONE phase-5 snapshot per symbol -- ``panel.as_of(symbol, d)`` -- which
answers from facts with ``filed <= d`` and only those. FLOWS ARE ANNUAL, not trailing-twelve-
month: phase 5 produces the latest visible fiscal year, because annual coverage is 8/8 while a
clean TTM needs four untroubled quarters and would put a systematic wedge through the
cross-section. The Fama-French convention is annual anyway.

    s             = panel.as_of(symbol, d)        (None -> the symbol is not eligible)
    market cap    = s.shares_outstanding x close(d)
                    (point-in-time only because the share count is filed-dated; when either
                    side is missing or <= 0 the cap is NaN and ``value`` is NaN with it)
    value         = s.equity / market cap                 (book-to-price, Fama-French)
    quality       = s.net_income / s.equity               (return on equity, ANNUAL income)
    profitability = s.gross_profit / s.assets             (ANNUAL gross profit)
                    (Novy-Marx gross profitability. ``s.gross_profit`` is phase 5's series and
                    may be derived: ``GrossProfit`` was tagged by only 2 of the 8 sampled
                    filers, so phase 5 falls back to ``Revenues - CostOfRevenue`` and records
                    which in ``s.gross_profit_basis``. This module consumes that series and
                    never re-derives it.)
    sue           = s.sue        (phase 5's seasonal random walk ``EPS_q - EPS_{q-4}`` scaled by
                    the dispersion of recent surprises; NaN until its minimum history is met,
                    which ``s.sue_quarters`` reports)
    staleness     = (d - s.filed).days            (the gate; s.filed is the no-look-ahead axis)

Phase 5 returns NaN, not None, for a field it could not resolve. ``_num`` maps both to NaN, so
the eligibility rule "every factor the ranking reads must be finite" is unchanged.
Analyst-consensus earnings surprise is deliberately absent: Finnhub's free tier returns four
quarters and cannot be backfilled to 2015 (plan index, Scope).

Ranking (ties broken by symbol ascending), the first ``top``:
    value | quality | profitability | sue  - that one feature, descending;
    composite                             - the cross-sectional z-score of each of the four over
                                            the eligible set, combined with ``params.weights``,
                                            descending. A factor whose eligible-set population
                                            standard deviation is zero, or that has fewer than
                                            two eligible rows, contributes 0.0 to every row.
Weights: ``equal`` gives every chosen name ``equal_weight(top)`` (fewer than ``top`` eligible
names leave the rest in cash); ``rank`` gives the i-th of k chosen (0-based)
``to_weight((k - i) / (k(k+1)/2) x k / top)`` - linear in rank, the same total exposure as
``equal`` - floor-quantized so the sum stays <= 1. A weight that floors to zero drops its name.
Trend gate: when ``trend = (symbol, n)``, nothing is targeted (all cash) unless that symbol has
a bar dated d, at least n bars through d, and close > SMA(n) (strict). Default ``None``:
measured, a 200-day gate over bars starting 2015-01-02 pushes the dev window start to
2015-10-19, past ``DEV_END``.
Held positions get no special treatment: the targets are exactly the new top set, so a held name
that falls out of it is signal-exited by the book engine (a rebalance).
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence, Set
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Literal, Protocol, runtime_checkable

import numpy as np

from seer_engine.fundamentals import EMPTY_PANEL
from seer_engine.sim.book import WEIGHT_QUANTUM, Target, equal_weight, to_weight
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History, as_day
from seer_engine.strategies.indicators import mean_dollar_volume_window, sma_window

DV_N = 20  # dollar-volume window, as f_factor and Strategy A
EXCLUDED: frozenset[str] = frozenset({"SPY"})  # never a factor target, even if listed as a member
MAX_TOP = 1000  # equal_weight(top) stays >= 0.001
FACTORS: tuple[str, ...] = ("value", "quality", "profitability", "sue")

Rank = Literal["value", "quality", "profitability", "sue", "composite"]
Sizing = Literal["equal", "rank"]
_RANKS: tuple[str, ...] = (*FACTORS, "composite")
_SIZINGS: tuple[str, ...] = ("equal", "rank")

_NAN = float("nan")


# --------------------------------------------------------------------------- the panel contract


@runtime_checkable
class Snapshot(Protocol):
    """One symbol's fundamentals as of one date -- phase 5's ``fundamentals.panel.Snapshot``.

    Every field answers from facts with ``filed <= t`` and only those. An unresolved field is
    NaN, never a zero. FLOWS ARE ANNUAL (the latest visible fiscal year), not TTM -- phase 5's
    decision 4, and the reason this module's quality and profitability legs are annual ratios.
    Only the seven members below are read here; the real Snapshot carries more.
    """

    filed: date | None
    net_income: float
    gross_profit: float
    assets: float
    equity: float
    shares_outstanding: float
    sue: float


@runtime_checkable
class Panel(Protocol):
    """What this allocator needs of a point-in-time fundamental panel (phase 5 supplies it).

    One call per symbol per rank session. ``None`` means "this panel has never heard of that
    symbol" -- distinct from a snapshot whose fields are NaN, which means "heard of it, knew
    nothing as of that date". Both make the symbol ineligible; the distinction is kept because
    the second is worth logging and the first is not.
    """

    def as_of(self, symbol: str, data_date: date) -> Snapshot | None: ...


# The "no fundamentals" panel is phase 5's EMPTY_PANEL, imported, NOT a local EmptyPanel
# class. An earlier draft of this file defined its own; that was a third object meaning the
# same thing (phase 5 owns EMPTY_PANEL, phase 6 re-exports it as backtest.market
# EMPTY_FUNDAMENTALS and uses it as Market.fundamentals' default), and the identity test
# `prepare_market(m).panel is EMPTY_PANEL` would then have been False for a Market built
# without a panel -- which is every Market in the tree before a store is rebuilt. One object,
# one identity. `seer_engine.fundamentals` is pure, so importing it here keeps
# test_strategy_purity.py green; it is the same import backtest/market.py makes.
#
# EMPTY_PANEL.as_of(symbol, t) returns None for every symbol, which is exactly the contract
# the Panel protocol above states and exactly what the history-only `prepare` path needs.


def _panel(obj: object) -> Panel:
    """``obj`` as a Panel, or ``EMPTY_PANEL`` when it is None.

    After phase 6, ``market.fundamentals`` is never None and never absent -- the field has a
    default and ``__post_init__`` type-checks it. The None branch is kept for the duck-typed
    ``prepare_market(market)`` contract (``market`` is deliberately ``Any`` so this module
    never imports ``backtest.market``), not because a real ``Market`` can reach it.
    """
    if obj is None:
        return EMPTY_PANEL
    if not isinstance(obj, Panel):
        raise TypeError(f"fundamentals must satisfy the Panel protocol, got {type(obj).__name__}")
    return obj


# --------------------------------------------------------------------------- params


def _plain(x: float | Decimal) -> str:
    """``x`` as a plain decimal string without trailing zeros: 5.0 -> "5", 20000000.0 -> "20000000"."""
    d = Decimal(repr(x)) if isinstance(x, float) else x
    return format(d.normalize(), "f")


def _check_int(name: str, v: object, lo: int) -> int:
    if isinstance(v, bool) or not isinstance(v, int):
        raise TypeError(f"{name} must be an int, got {type(v).__name__}")
    if v < lo:
        raise ValueError(f"{name} must be >= {lo}, got {v}")
    return v


def _check_float(name: str, v: object) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise TypeError(f"{name} must be a float, got {type(v).__name__}")
    out = float(v)
    if not math.isfinite(out):
        raise ValueError(f"{name} must be finite, got {out!r}")
    return out


@dataclass(frozen=True, slots=True)
class FundamentalParams:
    """Fundamental-factor parameters. ``weights`` is read only when ``rank == "composite"``."""

    rank: Rank
    top: int = 20  # holdings
    sizing: Sizing = "equal"
    weights: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0)  # value, quality, profitability, sue
    min_dollar_volume: float = 20_000_000.0  # 20-day mean close x volume > this (strict)
    min_price: float = 5.0  # close >= min_price
    max_stale_days: int = 400  # the latest fact used must be filed within this many days of d
    trend: tuple[str, int] | None = None  # all cash unless trend[0] close > SMA(trend[1]) on d

    def __post_init__(self) -> None:
        if not isinstance(self.rank, str):
            raise TypeError(f"rank must be a str, got {type(self.rank).__name__}")
        if self.rank not in _RANKS:
            raise ValueError(f"rank must be one of {_RANKS}, got {self.rank!r}")
        _check_int("top", self.top, 1)
        if self.top > MAX_TOP:
            raise ValueError(f"top must be <= {MAX_TOP}, got {self.top}")
        if not isinstance(self.sizing, str):
            raise TypeError(f"sizing must be a str, got {type(self.sizing).__name__}")
        if self.sizing not in _SIZINGS:
            raise ValueError(f"sizing must be one of {_SIZINGS}, got {self.sizing!r}")
        if not isinstance(self.weights, tuple) or len(self.weights) != len(FACTORS):
            raise TypeError(f"weights must be a tuple of {len(FACTORS)} floats, got {self.weights!r}")
        clean: list[float] = []
        total = 0.0
        for name, w in zip(FACTORS, self.weights, strict=True):
            value = _check_float(f"weights[{name}]", w)
            if value < 0.0:
                raise ValueError(f"weights[{name}] must be >= 0, got {value}")
            clean.append(value)
            total = total + value
        if total <= 0.0:
            raise ValueError(f"weights must not be all zero, got {self.weights!r}")
        object.__setattr__(self, "weights", (clean[0], clean[1], clean[2], clean[3]))
        dv = _check_float("min_dollar_volume", self.min_dollar_volume)
        if dv < 0.0:
            raise ValueError(f"min_dollar_volume must be >= 0, got {dv}")
        object.__setattr__(self, "min_dollar_volume", dv)
        price = _check_float("min_price", self.min_price)
        if price < 0.01:
            raise ValueError(f"min_price must be >= 0.01, got {price}")
        object.__setattr__(self, "min_price", price)
        _check_int("max_stale_days", self.max_stale_days, 1)
        if self.trend is not None:
            if not isinstance(self.trend, tuple) or len(self.trend) != 2:
                raise TypeError(f"trend must be None or a (symbol, n) tuple, got {self.trend!r}")
            symbol, n = self.trend
            if not isinstance(symbol, str) or not symbol:
                raise ValueError(f"trend symbol must be a non-empty str, got {symbol!r}")
            _check_int("trend n", n, 1)

    def as_dict(self) -> dict[str, str]:
        """Every parameter as a plain string, in a fixed key order (report and pre-registration)."""
        return {
            "rank": self.rank,
            "top": str(self.top),
            "sizing": self.sizing,
            "weights": ":".join(_plain(w) for w in self.weights),
            "min_dollar_volume": _plain(self.min_dollar_volume),
            "min_price": _plain(self.min_price),
            "max_stale_days": str(self.max_stale_days),
            "trend": "none" if self.trend is None else f"{self.trend[0]}:{self.trend[1]}",
        }


def _check_params(params: object) -> FundamentalParams:
    if not isinstance(params, FundamentalParams):
        raise TypeError(f"params must be FundamentalParams, got {type(params).__name__}")
    return params


def _check_held(held: object) -> None:
    if not isinstance(held, Set):
        raise TypeError(f"held must be a set of symbols, got {type(held).__name__}")


def fundamental_lookback(params: FundamentalParams) -> int:
    """Bars each read symbol needs through d: ``max(DV_N, trend n)``.

    Fundamentals need no bar warm-up of their own - a filing's availability is its ``filed``
    date, not a bar count - so the dollar-volume window is what binds. Measured: a 200-day
    trend gate over bars starting 2015-01-02 puts the dev window start at 2015-10-19, past
    ``backtest.dev.DEV_END``; keep ``trend`` None or short.
    """
    _check_params(params)
    trend_n = params.trend[1] if params.trend is not None else 0
    return max(DV_N, trend_n)


def factors_read(params: FundamentalParams) -> tuple[str, ...]:
    """The factor names ``params``' ranking reads: one of ``FACTORS``, or all four for composite."""
    p = _check_params(params)
    return FACTORS if p.rank == "composite" else (p.rank,)


# --------------------------------------------------------------------------- rows


@dataclass(frozen=True, slots=True)
class FundamentalRow:
    """One eligible symbol's features at a ``data_date`` close.

    A factor the ranking does not read may be NaN; a factor it does read is finite by
    construction (``fundamental_rows`` drops the row otherwise).
    """

    symbol: str
    close: float
    dollar_volume: float
    market_cap: float
    value: float
    quality: float
    profitability: float
    sue: float


def _num(x: object) -> float:
    """``x`` as a finite float, else NaN. None, a bool or a non-number all become NaN."""
    if x is None or isinstance(x, bool) or not isinstance(x, (int, float)):
        return _NAN
    out = float(x)
    return out if math.isfinite(out) else _NAN


def _pos(x: object) -> float | None:
    """``x`` as a finite float > 0, else None (a zero or negative denominator is "not known")."""
    out = _num(x)
    return out if out > 0.0 else None


def _dollar_volume(h: History, i: int) -> float:
    """``mean_dollar_volume_window`` over the ``DV_N`` bars ending at row ``i`` (inclusive)."""
    close = h.close[i + 1 - DV_N : i + 1].reshape(1, DV_N)
    volume = h.volume[i + 1 - DV_N : i + 1].reshape(1, DV_N)
    with np.errstate(divide="ignore", invalid="ignore"):
        return float(mean_dollar_volume_window(close, volume, DV_N)[0])


def _row(symbol: str, close: float, dollar_volume: float, snap: Snapshot) -> FundamentalRow:
    """One symbol's four factors from one phase-5 snapshot; anything unresolved becomes NaN.

    ``snap`` was built from facts with ``filed <= data_date`` and only those -- the
    no-look-ahead boundary is phase 5's and this module never second-guesses it. The two flow
    legs are ANNUAL (the latest visible fiscal year), not trailing-twelve-month; see C2.
    """
    shares = _pos(snap.shares_outstanding)
    equity = _pos(snap.equity)
    assets = _pos(snap.assets)
    net_income = _num(snap.net_income)
    gross_profit = _num(snap.gross_profit)
    market_cap = shares * close if shares is not None else _NAN
    value = equity / market_cap if (equity is not None and market_cap > 0.0) else _NAN
    quality = net_income / equity if (equity is not None and math.isfinite(net_income)) else _NAN
    profitability = gross_profit / assets if (assets is not None and math.isfinite(gross_profit)) else _NAN
    return FundamentalRow(
        symbol=symbol,
        close=close,
        dollar_volume=dollar_volume,
        market_cap=market_cap,
        value=value,
        quality=quality,
        profitability=profitability,
        sue=_num(snap.sue),
    )


def fundamental_rows(
    history: Mapping[str, History],
    panel: Panel,
    members: Set[str],
    data_date: date,
    params: FundamentalParams,
) -> list[FundamentalRow]:
    """Eligible members' features on ``data_date``, sorted by symbol (see the module docstring).

    Reads each member's last ``fundamental_lookback(params)`` bars ending at ``data_date`` and
    exactly one phase-5 snapshot per symbol, which answers from facts with
    ``filed <= data_date``; later bars and later filings are never read.
    """
    p = _check_params(params)
    as_day(data_date)
    panel = _panel(panel)
    lb = fundamental_lookback(p)
    wanted = factors_read(p)
    out: list[FundamentalRow] = []
    for symbol in sorted(members):
        if symbol in EXCLUDED:
            continue
        h = history.get(symbol)
        if h is None:
            continue
        i = h.index_of(data_date)
        if i is None or i + 1 < lb:
            continue
        close = float(h.close[i])
        if not math.isfinite(close) or close < p.min_price:
            continue
        dollar_volume = _dollar_volume(h, i)
        if not math.isfinite(dollar_volume) or not dollar_volume > p.min_dollar_volume:
            continue
        snap = panel.as_of(symbol, data_date)
        if snap is None:
            continue
        filed = snap.filed
        # filed > data_date would be a phase-5 bug, not a stale fact. Checked anyway: this is
        # the one assertion that stands between a look-ahead and a backtest that looks great.
        if filed is None or filed > data_date or (data_date - filed).days > p.max_stale_days:
            continue
        row = _row(symbol, close, dollar_volume, snap)
        if all(math.isfinite(getattr(row, name)) for name in wanted):
            out.append(row)
    return out


def trend_on(history: Mapping[str, History], data_date: date, params: FundamentalParams) -> bool:
    """The trend gate on ``data_date``: True when ``params.trend`` is None, else close > SMA(n) (strict).

    False when the trend symbol is absent, has no bar dated ``data_date`` or fewer than n bars
    through it. Reads only bars dated on or before ``data_date``.
    """
    p = _check_params(params)
    as_day(data_date)
    if p.trend is None:
        return True
    symbol, n = p.trend
    h = history.get(symbol)
    if h is None:
        return False
    i = h.index_of(data_date)
    if i is None or i + 1 < n:
        return False
    window = h.close[i + 1 - n : i + 1].reshape(1, n)
    with np.errstate(divide="ignore", invalid="ignore"):
        sma = sma_window(window, n)[0]
    return bool(window[0, -1] > sma)


# --------------------------------------------------------------------------- ranking


def zscores(values: Sequence[float]) -> list[float]:
    """Cross-sectional z-scores, population standard deviation, summed left to right.

    All zeros when there are fewer than two values or the standard deviation is not positive and
    finite. Accumulated in plain Python so the result depends only on the input order, which is
    the same (symbol ascending) on every path.
    """
    n = len(values)
    if n < 2:
        return [0.0] * n
    total = 0.0
    for x in values:
        total = total + x
    mean = total / n
    acc = 0.0
    for x in values:
        acc = acc + (x - mean) * (x - mean)
    sd = math.sqrt(acc / n)
    if not math.isfinite(sd) or sd <= 0.0:
        return [0.0] * n
    return [(x - mean) / sd for x in values]


def composite_scores(rows: Sequence[FundamentalRow], params: FundamentalParams) -> list[float]:
    """The weighted sum of each factor's z-score over ``rows``, one score per row, in row order."""
    p = _check_params(params)
    out = [0.0] * len(rows)
    for name, weight in zip(FACTORS, p.weights, strict=True):
        if weight == 0.0:
            continue
        column = zscores([float(getattr(r, name)) for r in rows])
        for k, z in enumerate(column):
            out[k] = out[k] + weight * z
    return out


def rank_rows(rows: Sequence[FundamentalRow], params: FundamentalParams) -> list[FundamentalRow]:
    """The chosen rows, in rank order (ties by symbol ascending)."""
    p = _check_params(params)
    if p.rank == "composite":
        scored = list(zip(composite_scores(rows, p), rows, strict=True))
        return [r for _, r in sorted(scored, key=lambda pair: (-pair[0], pair[1].symbol))][: p.top]
    return sorted(rows, key=lambda r: (-float(getattr(r, p.rank)), r.symbol))[: p.top]


def _floor_weight(x: float) -> Decimal | None:
    """``to_weight(x)``, or None when ``x`` floors to zero (or is not a finite positive float)."""
    if not math.isfinite(x) or Decimal(repr(x)) < WEIGHT_QUANTUM:
        return None
    return to_weight(x)


def fundamental_weights(chosen: Sequence[FundamentalRow], params: FundamentalParams) -> list[Decimal | None]:
    """One weight per chosen row (None = floors to zero, the row is dropped). Sum of non-None <= 1."""
    p = _check_params(params)
    if not chosen:
        return []
    if p.sizing == "equal":
        w = equal_weight(p.top)
        return [w for _ in chosen]
    k = len(chosen)
    denominator = float(k * (k + 1) // 2)
    scale = k / p.top
    return [_floor_weight((k - i) / denominator * scale) for i in range(k)]


def targets_from_rows(rows: Sequence[FundamentalRow], params: FundamentalParams) -> tuple[Target, ...]:
    """Rank, weigh and price ``rows``: Targets with no limit, stop or take, in rank order."""
    chosen = rank_rows(rows, params)
    out: list[Target] = []
    for row, weight in zip(chosen, fundamental_weights(chosen, params), strict=True):
        if weight is None:
            continue
        target = target_from_close(row.symbol, row.close, weight)
        if target is not None:
            out.append(target)
    return tuple(out)


def targets_with_panel(
    history: Mapping[str, History],
    panel: Panel,
    members: Set[str],
    data_date: date,
    held: frozenset[str],
    params: FundamentalParams,
) -> tuple[Target, ...]:
    """The one definition of this allocator's output. Both paths call it; nothing else does."""
    p = _check_params(params)
    _check_held(held)
    if not trend_on(history, data_date, p):
        return ()
    return targets_from_rows(fundamental_rows(history, panel, members, data_date, p), p)


# --------------------------------------------------------------------------- the allocator


@dataclass(frozen=True, slots=True, eq=False)
class FundamentalPrepared:
    """A history and the panel that goes with it. ``prepare`` supplies ``EMPTY_PANEL``.

    Deliberately thin: ``targets_prepared`` delegates to ``targets_with_panel``, so the prepared
    and single-window results are the same expression and cannot drift apart. The dollar-volume
    window is 20 bars over a few hundred members on a rank session, so there is nothing here
    worth precomputing.
    """

    history: Mapping[str, History] = field(repr=False)
    panel: Panel = field(repr=False)


class FundamentalAllocator:
    """Fundamental cross-sectional factors behind the ``Allocator`` protocol."""

    id = "FND"
    # Defining prepare_market is the whole declaration: it makes this class satisfy phase 6's
    # @runtime_checkable MarketAware protocol structurally, which is what dev.py's prepare_for
    # dispatches on and what the shared lab gate branches on. There is deliberately NO separate
    # `uses_fundamentals` flag -- two sources of truth for "my live path is prepare_market" is
    # one too many, and the protocol is the real one.

    def lookback(self, params: Any) -> int:
        return fundamental_lookback(_check_params(params))

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check_params(params)
        return () if p.trend is None else (p.trend[0],)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check_params(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check_params(params)
        return True

    def targets(
        self,
        history: Mapping[str, History],
        members: Set[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        """The history-only path. With no panel every symbol is ineligible, so this returns ().

        That is the contract, not a degradation, and the shared lab gate asserts it (Step 3).
        """
        return targets_with_panel(history, EMPTY_PANEL, members, data_date, held, _check_params(params))

    def prepare(self, history: Mapping[str, History]) -> FundamentalPrepared:
        return FundamentalPrepared(dict(history), EMPTY_PANEL)

    def prepare_market(self, market: Any) -> FundamentalPrepared:
        """The live path: the market's history plus its point-in-time fundamental panel.

        ``market`` is duck-typed on purpose - this module must not import ``backtest.market``.
        After phase 6 a real ``Market`` always carries a panel: the field defaults to
        ``backtest.market.EMPTY_FUNDAMENTALS``, which **is** the ``EMPTY_PANEL`` imported
        here. So a market built before a store was rebuilt yields that same object and this
        path degrades to exactly the ``prepare`` case, by identity rather than by accident.
        """
        return FundamentalPrepared(dict(market.history), _panel(getattr(market, "fundamentals", None)))

    def targets_prepared(
        self,
        prepared: Any,
        members: Set[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        if not isinstance(prepared, FundamentalPrepared):
            raise TypeError(f"prepared must be FundamentalPrepared, got {type(prepared).__name__}")
        return targets_with_panel(
            prepared.history, prepared.panel, members, data_date, held, _check_params(params)
        )


FUNDAMENTAL = FundamentalAllocator()

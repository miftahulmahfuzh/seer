"""The backtest's in-memory, point-in-time market: membership, bars and FX (P3, handover §3/§4).

Pure. Built once per process (``backtest.io.load_market`` in phase 5, or by a test), then read
by the runner, the benchmark and the survivorship count. Nothing here touches a database, a
file, the network or a clock.

- ``Membership`` answers "who was in the S&P 500 ∪ Nasdaq-100 on day d" from the ``universe``
  intervals (``[start, end)``, end exclusive, ``None`` = still a member) without a query per
  day: the intervals are swept once into constant segments, and a lookup is one bisect.
- ``Market`` holds every symbol's float64 ``History`` (SPY included) and builds a Decimal
  ``prices.Bar`` on demand, only for the few symbols the simulator needs on a session. Prices
  go through ``prices.to_decimal(float(x))``: ``bars`` columns are ``numeric(12,4)``, so the
  float's shortest repr is the stored value and the Decimal is exact.
"""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from seer_engine.prices import Bar, to_decimal
from seer_engine.strategies.base import History

SPY = "SPY"


def _check_date(name: str, d: object) -> date:
    if isinstance(d, datetime) or not isinstance(d, date):
        raise TypeError(f"{name} must be a date, got {type(d).__name__}")
    return d


@dataclass(frozen=True)
class Membership:
    """Point-in-time index membership, both indices unioned.

    ``intervals`` holds ``(symbol, start, end)`` with ``start`` inclusive and ``end``
    exclusive (``None`` = still a member); one row per ``universe`` row, so a symbol in both
    indices may appear twice and overlapping intervals are fine.
    """

    intervals: tuple[tuple[str, date, date | None], ...]
    _breaks: tuple[date, ...] = field(init=False, repr=False, compare=False)
    _segments: tuple[frozenset[str], ...] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.intervals, tuple):
            raise TypeError("intervals must be a tuple")
        delta: dict[date, dict[str, int]] = {}
        for item in self.intervals:
            if not (isinstance(item, tuple) and len(item) == 3):
                raise TypeError(f"an interval is (symbol, start, end), got {item!r}")
            symbol, start, end = item
            if not isinstance(symbol, str) or not symbol:
                raise ValueError(f"symbol must be a non-empty str, got {symbol!r}")
            _check_date("start", start)
            if end is not None:
                _check_date("end", end)
                if end <= start:
                    raise ValueError(f"{symbol}: end {end} must be after start {start}")
            delta.setdefault(start, {}).setdefault(symbol, 0)
            delta[start][symbol] += 1
            if end is not None:
                delta.setdefault(end, {}).setdefault(symbol, 0)
                delta[end][symbol] -= 1
        breaks = sorted(delta)
        active: dict[str, int] = {}
        segments: list[frozenset[str]] = []
        for b in breaks:
            for symbol, change in delta[b].items():
                count = active.get(symbol, 0) + change
                if count:
                    active[symbol] = count
                else:
                    active.pop(symbol, None)
            segments.append(frozenset(active))
        object.__setattr__(self, "_breaks", tuple(breaks))
        object.__setattr__(self, "_segments", tuple(segments))

    def members_on(self, d: date) -> frozenset[str]:
        """Symbols that were a member of either index on ``d`` (one bisect)."""
        i = bisect_right(self._breaks, _check_date("d", d)) - 1
        return self._segments[i] if i >= 0 else frozenset()

    def symbols(self) -> tuple[str, ...]:
        """Every symbol that was ever a member, sorted."""
        return tuple(sorted({s for s, _, _ in self.intervals}))


@dataclass(frozen=True, eq=False)
class Market:
    """Everything a backtest reads, in memory.

    ``history``: every symbol with bars (SPY included), keyed by symbol, each ``History``
    ascending. ``fx``: ``(date, usd_idr)`` rows, strictly ascending, ``usd_idr`` a Decimal > 0
    (publishing days only, so not every session has a row).
    """

    history: Mapping[str, History]
    membership: Membership
    fx: tuple[tuple[date, Decimal], ...]
    _fx_dates: tuple[date, ...] = field(init=False, repr=False)
    _last: Mapping[str, date] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.history, Mapping):
            raise TypeError(f"history must be a Mapping, got {type(self.history).__name__}")
        if not isinstance(self.membership, Membership):
            raise TypeError(f"membership must be a Membership, got {type(self.membership).__name__}")
        if not isinstance(self.fx, tuple):
            raise TypeError("fx must be a tuple of (date, Decimal) rows")
        last: dict[str, date] = {}
        for symbol, h in self.history.items():
            if not isinstance(h, History):
                raise TypeError(f"history[{symbol!r}] must be a History, got {type(h).__name__}")
            if h.symbol != symbol:
                raise ValueError(f"history[{symbol!r}] holds bars for {h.symbol!r}")
            d = h.last_date()
            if d is not None:
                last[symbol] = d
        prev: date | None = None
        for row in self.fx:
            if not (isinstance(row, tuple) and len(row) == 2):
                raise TypeError(f"an fx row is (date, Decimal), got {row!r}")
            d, rate = row
            _check_date("fx date", d)
            if not isinstance(rate, Decimal):
                raise TypeError(f"usd_idr on {d} must be a Decimal, got {type(rate).__name__}")
            if not rate.is_finite() or rate <= 0:
                raise ValueError(f"usd_idr on {d} must be > 0, got {rate}")
            if prev is not None and d <= prev:
                raise ValueError(f"fx rows must be strictly ascending: {d} after {prev}")
            prev = d
        object.__setattr__(self, "_fx_dates", tuple(d for d, _ in self.fx))
        object.__setattr__(self, "_last", last)

    def bar(self, symbol: str, d: date) -> Bar | None:
        """``symbol``'s bar dated ``d`` as a Decimal ``Bar`` (exact 4 dp), or None."""
        h = self.history.get(symbol)
        if h is None:
            return None
        i = h.index_of(_check_date("d", d))
        if i is None:
            return None
        return Bar(
            symbol=symbol,
            date=d,
            open=to_decimal(float(h.open[i])),
            high=to_decimal(float(h.high[i])),
            low=to_decimal(float(h.low[i])),
            close=to_decimal(float(h.close[i])),
            volume=int(h.volume[i]),
        )

    def bars_on(self, d: date, symbols: Iterable[str]) -> dict[str, Bar]:
        """``{symbol: Bar}`` for each of ``symbols`` that has a bar on ``d`` (as ``sim.step`` takes them)."""
        out: dict[str, Bar] = {}
        for symbol in symbols:
            b = self.bar(symbol, d)
            if b is not None:
                out[symbol] = b
        return out

    def last_bar_date(self, symbol: str) -> date | None:
        """The date of ``symbol``'s last bar in the loaded data, or None when it has none."""
        return self._last.get(symbol)

    def usd_idr_on(self, d: date) -> Decimal:
        """USD/IDR from the latest fx row dated on or before ``d``; ValueError when there is none."""
        i = bisect_right(self._fx_dates, _check_date("d", d)) - 1
        if i < 0:
            raise ValueError(f"no usd_idr rate on or before {d}")
        return self.fx[i][1]

    def spy(self) -> dict[date, Bar]:
        """Every SPY bar as a Decimal ``Bar``, keyed by date ascending ({} when SPY has no bars)."""
        h = self.history.get(SPY)
        if h is None:
            return {}
        out: dict[date, Bar] = {}
        for d, o, hi, lo, c, v in zip(
            h.dates.tolist(), h.open.tolist(), h.high.tolist(), h.low.tolist(),
            h.close.tolist(), h.volume.tolist(),
        ):
            out[d] = Bar(SPY, d, to_decimal(o), to_decimal(hi), to_decimal(lo), to_decimal(c), int(v))
        return out

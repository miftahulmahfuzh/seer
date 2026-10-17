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

import math
from bisect import bisect_right
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from decimal import Decimal
from typing import NamedTuple

from seer_engine.fundamentals import EMPTY_PANEL, FundamentalPanel as Panel
from seer_engine.prices import Bar, to_decimal
from seer_engine.strategies.base import History, as_day

SPY = "SPY"

EMPTY_FUNDAMENTALS: Panel = EMPTY_PANEL
"""The panel a ``Market`` carries when no fundamentals were loaded.

This IS ``seer_engine.fundamentals.EMPTY_PANEL``, not a second empty panel built here: one
shared instance means ``market.fundamentals is EMPTY_PANEL`` is a usable identity test and
there is exactly one object the whole tree means by "no fundamentals". It is immutable, so it
is a safe dataclass default. ``load_market`` returns it for a database with no
``fundamental_facts`` rows -- and for one where the table does not exist yet, which is every
database that has not run phase 2's migration.

``FundamentalPanel`` is aliased to ``Panel`` here and in ``io.py`` because that is the name
this phase's code, tests and docstrings use throughout; phase 5 owns the type.
"""


class Announcement(NamedTuple):
    """One dividend as it was known on a day: ``known`` is when the market learned of it.

    ``known`` is the board's declaration date when the store carries one (``declared`` True),
    else the ex-date itself -- an undated dividend is never assumed known earlier than the day
    it went ex.
    """

    known: date
    ex_date: date
    amount: Decimal
    declared: bool


class DividendCalendar:
    """Every symbol's cash dividends by ex-date, read point in time.

    ``rows`` maps a symbol to ``(ex_date, amount)`` pairs, strictly ascending by ex-date, each
    amount a Decimal > 0 in the bars' (split-adjusted) units. The only read is ``known_on``,
    which returns the ex-dates dated on or before ``data_date``: an allocator that asks with the
    ``data_date`` it was handed cannot see a dividend that has not gone ex yet. That is the same
    contract ``History`` keeps for bars, and ``tests/test_market_dividends.py`` holds it.

    Built from the research store's ``dividends.csv`` by ``research.load_store`` (dev and test
    windows alike, each clipped to its window by the loader). A market built any other way --
    the database path, a paper replay, a fixture -- carries ``EMPTY_DIVIDENDS``.

    ``declared`` optionally maps ``symbol -> ex_date -> declaration date`` for some of those
    dividends (the store's ``dividend_announcements.csv``). It feeds the second read,
    ``announced_on``, which lets an allocator act on a dividend from the day it was announced
    rather than the day it went ex. ``known_on`` ignores it and is unchanged.
    """

    __slots__ = ("_rows", "_dates", "_announced", "_known")

    def __init__(
        self,
        rows: Mapping[str, Iterable[tuple[date, Decimal]]],
        *,
        declared: Mapping[str, Mapping[date, date]] | None = None,
    ) -> None:
        if not isinstance(rows, Mapping):
            raise TypeError(f"rows must be a Mapping, got {type(rows).__name__}")
        out: dict[str, tuple[tuple[date, Decimal], ...]] = {}
        for symbol in sorted(rows):
            if not isinstance(symbol, str) or not symbol:
                raise ValueError(f"symbol must be a non-empty str, got {symbol!r}")
            items = tuple(rows[symbol])
            prev: date | None = None
            for item in items:
                if not (isinstance(item, tuple) and len(item) == 2):
                    raise TypeError(f"a {symbol} dividend is (ex_date, Decimal), got {item!r}")
                d, amount = item
                _check_date("ex_date", d)
                if not isinstance(amount, Decimal) or not amount.is_finite() or amount <= 0:
                    raise ValueError(f"{symbol} dividend on {d} must be a Decimal > 0, got {amount!r}")
                if prev is not None and d <= prev:
                    raise ValueError(f"{symbol} dividends must be strictly ascending: {d} after {prev}")
                prev = d
            if items:
                out[symbol] = items
        self._rows: Mapping[str, tuple[tuple[date, Decimal], ...]] = out
        self._dates: Mapping[str, tuple[date, ...]] = {s: tuple(d for d, _ in r) for s, r in out.items()}
        declared = {} if declared is None else declared
        if not isinstance(declared, Mapping):
            raise TypeError(f"declared must be a Mapping, got {type(declared).__name__}")
        for symbol, by_ex in declared.items():
            amounts = dict(out.get(symbol, ()))
            for ex_date, day in by_ex.items():
                if ex_date not in amounts:
                    raise ValueError(f"{symbol} has no dividend going ex on {ex_date} to date")
                _check_date("declared", day)
                if day > ex_date:
                    raise ValueError(f"{symbol} {ex_date}: declared {day} after the ex-date")
        announced: dict[str, tuple[Announcement, ...]] = {}
        for symbol, items in out.items():
            by_ex = declared.get(symbol, {})
            announced[symbol] = tuple(
                sorted(
                    (
                        Announcement(by_ex.get(d, d), d, amount, d in by_ex)
                        for d, amount in items
                    ),
                    key=lambda a: (a.known, a.ex_date),
                )
            )
        self._announced: Mapping[str, tuple[Announcement, ...]] = announced
        self._known: Mapping[str, tuple[date, ...]] = {
            s: tuple(a.known for a in r) for s, r in announced.items()
        }

    @staticmethod
    def from_map(
        dividends: Mapping[str, Mapping[date, Decimal]],
        *,
        declared: Mapping[str, Mapping[date, date]] | None = None,
    ) -> DividendCalendar:
        """A calendar from ``symbol -> ex_date -> amount`` (``ResearchData.dividends``' shape)."""
        return DividendCalendar(
            {s: sorted(by_date.items()) for s, by_date in dividends.items()}, declared=declared
        )

    def declared_count(self) -> int:
        """How many dividends carry a declaration date."""
        return sum(a.declared for r in self._announced.values() for a in r)

    def __len__(self) -> int:
        return sum(len(r) for r in self._rows.values())

    def symbols(self) -> tuple[str, ...]:
        """Every symbol with at least one dividend, sorted."""
        return tuple(self._rows)

    def known_on(self, symbol: str, data_date: date) -> tuple[tuple[date, Decimal], ...]:
        """``symbol``'s ``(ex_date, amount)`` rows dated on or before ``data_date``, ascending."""
        dates_ = self._dates.get(symbol)
        if dates_ is None:
            return ()
        return self._rows[symbol][: bisect_right(dates_, _check_date("data_date", data_date))]

    def announced_on(self, symbol: str, data_date: date) -> tuple[Announcement, ...]:
        """``symbol``'s dividends known on or before ``data_date``, ascending by ``known``.

        A dividend with a declaration date is known from that day, possibly weeks before it goes
        ex; one without is known from its ex-date, exactly as ``known_on`` reports it.
        """
        known = self._known.get(symbol)
        if known is None:
            return ()
        return self._announced[symbol][: bisect_right(known, _check_date("data_date", data_date))]


def _check_date(name: str, d: object) -> date:
    if isinstance(d, datetime) or not isinstance(d, date):
        raise TypeError(f"{name} must be a date, got {type(d).__name__}")
    return d


EMPTY_DIVIDENDS = DividendCalendar({})
"""The calendar a ``Market`` carries when no dividends were loaded (one shared instance)."""


class MarketSeries:
    """Market-wide daily series by name (VIX, Treasury yields, gold), read point in time.

    ``rows`` maps a series name to ``(date, value)`` pairs, strictly ascending by date, each value a
    finite float in the unit an allocator reasons in: the VIX family in index points, Treasury
    yields in percent (``T10Y`` 6.548 means 6.548%), gold in USD per ounce. Names with no rows are
    dropped, as ``DividendCalendar`` drops a symbol with no dividends.

    Every read takes the allocator's ``data_date`` and sees only rows dated on or before it. That
    is the same contract ``History`` keeps for bars and ``DividendCalendar.known_on`` keeps for
    dividends, and ``tests/test_market_series.py`` holds it.

    ``value_on`` is the **latest** value on or before ``data_date``, not only one dated exactly
    then: a Treasury index has no close on Columbus Day while the stock market trades, and the
    last published yield is what a trader knew that morning. An allocator that must know how old
    the value is reads ``upto(name, data_date, last=1)`` and compares the date.

    Built from the research store's optional ``market_series.csv`` by ``research.load_store``.
    A market built any other way -- the database path, a paper replay, a fixture -- carries
    ``EMPTY_SERIES``.
    """

    __slots__ = ("_rows", "_dates")

    def __init__(self, rows: Mapping[str, Iterable[tuple[date, float]]]) -> None:
        if not isinstance(rows, Mapping):
            raise TypeError(f"rows must be a Mapping, got {type(rows).__name__}")
        out: dict[str, tuple[tuple[date, float], ...]] = {}
        for name in sorted(rows):
            if not isinstance(name, str) or not name:
                raise ValueError(f"series name must be a non-empty str, got {name!r}")
            items: list[tuple[date, float]] = []
            prev: date | None = None
            for item in rows[name]:
                if not (isinstance(item, tuple) and len(item) == 2):
                    raise TypeError(f"a {name} row is (date, float), got {item!r}")
                d, value = item
                _check_date(f"{name} date", d)
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise TypeError(f"{name} on {d}: value must be a float, got {type(value).__name__}")
                value = float(value)
                if not math.isfinite(value):
                    raise ValueError(f"{name} on {d}: value must be finite, got {value!r}")
                if prev is not None and d <= prev:
                    raise ValueError(f"{name} rows must be strictly ascending: {d} after {prev}")
                prev = d
                items.append((d, value))
            if items:
                out[name] = tuple(items)
        self._rows: Mapping[str, tuple[tuple[date, float], ...]] = out
        self._dates: Mapping[str, tuple[date, ...]] = {n: tuple(d for d, _ in r) for n, r in out.items()}

    def __len__(self) -> int:
        return sum(len(r) for r in self._rows.values())

    def names(self) -> tuple[str, ...]:
        """Every series with at least one row, sorted."""
        return tuple(self._rows)

    def first_date(self, name: str) -> date | None:
        """The date of ``name``'s first row, or None when the series is absent."""
        dates_ = self._dates.get(name)
        return dates_[0] if dates_ else None

    def value_on(self, name: str, data_date: date) -> float | None:
        """``name``'s latest value dated on or before ``data_date``; None when there is none yet."""
        d = _check_date("data_date", data_date)
        dates_ = self._dates.get(name)
        if dates_ is None:
            return None
        i = bisect_right(dates_, d)
        return self._rows[name][i - 1][1] if i else None

    def upto(
        self, name: str, data_date: date, *, last: int | None = None
    ) -> tuple[tuple[date, float], ...]:
        """``name``'s ``(date, value)`` rows dated on or before ``data_date``, ascending.

        ``last`` keeps only the final ``last`` of them (a lookback window without copying the
        whole history on every rank day).
        """
        if last is not None and (isinstance(last, bool) or not isinstance(last, int) or last < 1):
            raise ValueError(f"last must be a positive int or None, got {last!r}")
        d = _check_date("data_date", data_date)
        dates_ = self._dates.get(name)
        if dates_ is None:
            return ()
        i = bisect_right(dates_, d)
        lo = 0 if last is None else max(0, i - last)
        return self._rows[name][lo:i]


EMPTY_SERIES = MarketSeries({})
"""The series a ``Market`` carries when no market series were loaded (one shared instance)."""


class ShareCount(NamedTuple):
    """One company's shares outstanding as it was public on a day (``ShareCounts.count``).

    ``shares`` is the figure the filer stated, in the share units of ``counted`` -- the day the
    filer counted (the cover's "as of" date, or the filing date when the cover gave none).
    ``filed`` is when it became public, always on or before the day it is read for. ``source``
    is ``"edgar-cover"`` (a 10-K/10-Q cover page, 1995-2010) or ``"xbrl"`` (the same figure,
    tagged, 2009 on).
    """

    shares: float
    counted: date
    filed: date
    source: str


class ShareCounts:
    """Point-in-time shares outstanding and the splits behind the store's adjusted closes.

    ``rows`` maps a symbol to ``(from_day, ShareCount | None)`` change points, strictly ascending:
    the count public from ``from_day`` until the next row (None: no usable figure from that day).
    The research store writes them already resolved (``shares.store``): a figure counts only from
    its filing date, the later filing wins, XBRL wins a same-day tie, the symbol is resolved to its
    filer on each day through the date-scoped ticker map, and a figure older than 400 days is not
    answered. Nothing here re-derives any of that; it only reads.

    ``splits`` maps a symbol to ``(dated, after_window)``: the splits the vendor applied to that
    symbol's adjusted closes inside the store's window, ascending ``(ex_date, ratio)``, and the
    product of the ones it applied after the window ends (1.0 when none). The second is held only
    so :meth:`raw_factor` can undo the adjustment; it is never answered on its own, and an
    allocator must not reach for it -- it is a fact about the future of the window.

    Every read takes the allocator's ``data_date`` and sees only figures filed on or before it.
    Built from the store's optional ``shares.csv`` and ``splits.csv`` by ``research.load_store``;
    any other market carries ``EMPTY_SHARES``.
    """

    __slots__ = ("_rows", "_from", "_splits")

    def __init__(
        self,
        rows: Mapping[str, Iterable[tuple[date, ShareCount | None]]],
        splits: Mapping[str, tuple[Iterable[tuple[date, float]], float]] | None = None,
    ) -> None:
        if not isinstance(rows, Mapping):
            raise TypeError(f"rows must be a Mapping, got {type(rows).__name__}")
        out: dict[str, tuple[tuple[date, ShareCount | None], ...]] = {}
        for symbol in sorted(rows):
            items = tuple(rows[symbol])
            prev: date | None = None
            for item in items:
                if not (isinstance(item, tuple) and len(item) == 2):
                    raise TypeError(f"a {symbol} share row is (date, ShareCount | None), got {item!r}")
                d, count = item
                _check_date(f"{symbol} from", d)
                if prev is not None and d <= prev:
                    raise ValueError(f"{symbol} share rows must be strictly ascending: {d} after {prev}")
                prev = d
                if count is not None:
                    if not isinstance(count, ShareCount):
                        raise TypeError(f"{symbol} on {d}: expected a ShareCount, got {type(count).__name__}")
                    if not (math.isfinite(count.shares) and count.shares > 0):
                        raise ValueError(f"{symbol} on {d}: shares must be positive, got {count.shares!r}")
                    if count.filed > d:
                        raise ValueError(f"{symbol} on {d}: a count filed {count.filed} is read before it was public")
            if items:
                out[symbol] = items
        self._rows: Mapping[str, tuple[tuple[date, ShareCount | None], ...]] = out
        self._from: Mapping[str, tuple[date, ...]] = {s: tuple(d for d, _ in r) for s, r in out.items()}
        clean: dict[str, tuple[tuple[tuple[date, float], ...], float]] = {}
        for symbol, (dated, after) in (splits or {}).items():
            items_ = tuple(sorted(dated))
            for d, ratio in items_:
                _check_date(f"{symbol} split", d)
                if not (math.isfinite(ratio) and ratio > 0):
                    raise ValueError(f"{symbol} split on {d}: ratio must be positive, got {ratio!r}")
            if not (math.isfinite(after) and after > 0):
                raise ValueError(f"{symbol}: the after-window split factor must be positive, got {after!r}")
            clean[symbol] = (items_, float(after))
        self._splits = clean

    def __len__(self) -> int:
        return sum(len(r) for r in self._rows.values())

    def symbols(self) -> tuple[str, ...]:
        """Every symbol with at least one share row, sorted."""
        return tuple(self._rows)

    def count(self, symbol: str, data_date: date) -> ShareCount | None:
        """The count public on ``data_date`` for the company trading as ``symbol`` that day."""
        froms = self._from.get(symbol)
        if froms is None:
            return None
        i = bisect_right(froms, _check_date("data_date", data_date))
        return self._rows[symbol][i - 1][1] if i else None

    def split_factor(self, symbol: str, after: date, through: date) -> float:
        """Product of ``symbol``'s in-window split ratios effective in ``(after, through]``."""
        dated = self._splits.get(symbol)
        f = 1.0
        if dated is not None:
            for d, ratio in dated[0]:
                if after < d <= through:
                    f *= ratio
        return f

    def shares_on(self, symbol: str, data_date: date) -> float | None:
        """``count(symbol, data_date)`` restated in the share units of ``data_date``: a count taken
        before a split is carried across it, so it pairs with that day's printed price."""
        c = self.count(symbol, data_date)
        if c is None:
            return None
        return c.shares * self.split_factor(symbol, c.counted, data_date)

    def raw_factor(self, symbol: str, d: date) -> float:
        """What the store's split-adjusted price on ``d`` is multiplied by to give the price as it
        printed that day: every split the vendor applied after ``d`` (``shares.history.unadjust``)."""
        dated = self._splits.get(symbol)
        if dated is None:
            return 1.0
        f = dated[1]
        for s_day, ratio in dated[0]:
            if s_day > d:
                f *= ratio
        return f

    def has_splits(self) -> bool:
        return bool(self._splits)


EMPTY_SHARES = ShareCounts({})
"""The share counts a ``Market`` carries when the store has none (one shared instance)."""

MARKET_VALUE_MAX_GAP_DAYS = 7
"""How old the last close may be when :meth:`Market.market_value` prices a company: a week, so a
long weekend or a halted day still has a size and a company that stopped trading does not."""


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

    ``dividends``: the point-in-time ex-date calendar (``DividendCalendar``), for an allocator
    that ranks on it; ``EMPTY_DIVIDENDS`` unless the research store loaded one. The book
    engine's cash ledger does not read it -- it still gets ``ResearchData.dividends``.

    ``series``: the point-in-time market-wide series (``MarketSeries``: VIX, VIX3M, Treasury
    yields, gold), ``EMPTY_SERIES`` unless the research store carries ``market_series.csv``. An
    allocator that reads it declares ``market_fields = ("series",)`` so ``lab run`` refuses it on
    a store without series.

    ``shares``: point-in-time shares outstanding and the splits behind the adjusted closes
    (``ShareCounts``), ``EMPTY_SHARES`` unless the store carries ``shares.csv``. Read it through
    :meth:`shares_on` and :meth:`market_value` (company size), and declare
    ``market_fields = ("shares",)`` so ``lab run`` refuses the allocator on a store without them.

    ``history``: every symbol with bars (SPY included), keyed by symbol, each ``History``
    ascending. ``fx``: ``(date, usd_idr)`` rows, strictly ascending, ``usd_idr`` a Decimal > 0
    (publishing days only, so not every session has a row). ``fundamentals``: the point-in-time
    SEC fact panel built by ``seer_engine.fundamentals``, ``EMPTY_FUNDAMENTALS`` when none was
    loaded.

    ``fundamentals`` is deliberately independent of ``history``. A symbol may have facts and no
    bars (the 133 delisted ever-members, whose prices are blocked on Gap A) or bars and no facts
    (every ETF). Nothing here cross-checks the two and nothing may start to.
    """

    history: Mapping[str, History]
    membership: Membership
    fx: tuple[tuple[date, Decimal], ...]
    fundamentals: Panel = EMPTY_FUNDAMENTALS
    dividends: DividendCalendar = EMPTY_DIVIDENDS
    series: MarketSeries = EMPTY_SERIES
    shares: ShareCounts = EMPTY_SHARES
    _fx_dates: tuple[date, ...] = field(init=False, repr=False)
    _last: Mapping[str, date] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.history, Mapping):
            raise TypeError(f"history must be a Mapping, got {type(self.history).__name__}")
        if not isinstance(self.membership, Membership):
            raise TypeError(f"membership must be a Membership, got {type(self.membership).__name__}")
        if not isinstance(self.fx, tuple):
            raise TypeError("fx must be a tuple of (date, Decimal) rows")
        if not isinstance(self.fundamentals, Panel):
            raise TypeError(f"fundamentals must be a Panel, got {type(self.fundamentals).__name__}")
        if not isinstance(self.dividends, DividendCalendar):
            raise TypeError(f"dividends must be a DividendCalendar, got {type(self.dividends).__name__}")
        if not isinstance(self.series, MarketSeries):
            raise TypeError(f"series must be a MarketSeries, got {type(self.series).__name__}")
        if not isinstance(self.shares, ShareCounts):
            raise TypeError(f"shares must be a ShareCounts, got {type(self.shares).__name__}")
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

    def with_fundamentals(self, fundamentals: Panel) -> Market:
        """This market with ``fundamentals`` attached; every other field is carried over.

        ``Market`` is frozen, so this returns a new value and leaves ``self`` untouched. It is
        the supported way to put a panel on a market that was built without one -- the research
        store, a paper replay, a test fixture -- without any of those having to know the field
        order.
        """
        return replace(self, fundamentals=fundamentals)

    def with_dividends(self, dividends: DividendCalendar) -> Market:
        """This market with ``dividends`` attached; every other field is carried over."""
        return replace(self, dividends=dividends)

    def with_series(self, series: MarketSeries) -> Market:
        """This market with ``series`` attached; every other field is carried over."""
        return replace(self, series=series)

    def with_shares(self, shares: ShareCounts) -> Market:
        """This market with ``shares`` attached; every other field is carried over."""
        return replace(self, shares=shares)

    def shares_on(self, symbol: str, d: date) -> float | None:
        """Shares outstanding of the company trading as ``symbol`` on ``d``, as public that day
        and in that day's share units; None when no usable figure was filed by ``d``."""
        return self.shares.shares_on(symbol, d)

    def market_value(self, symbol: str, d: date) -> float | None:
        """Company size on ``d`` in dollars: :meth:`shares_on` times the close **as it printed**.

        The close is ``symbol``'s last bar on or before ``d`` (at most
        ``MARKET_VALUE_MAX_GAP_DAYS`` old), un-adjusted for every split the vendor applied after
        it, so a pre-split count is never multiplied by a post-split price. None when the count or
        the close is unknown. Reads nothing dated after ``d``.
        """
        c = self.shares.count(symbol, _check_date("d", d))
        if c is None:
            return None
        h = self.history.get(symbol)
        if h is None:
            return None
        i = int(h.dates.searchsorted(as_day(d), side="right")) - 1
        if i < 0:
            return None
        last = h.dates[i].item()
        if (d - last).days > MARKET_VALUE_MAX_GAP_DAYS:
            return None
        close = float(h.close[i])
        if not (close > 0 and math.isfinite(close)):
            return None
        # The count in the share units of the close's own day, so both sides of the product are
        # on one side of every split (a count dated after the last close is carried back).
        if c.counted <= last:
            units = self.shares.split_factor(symbol, c.counted, last)
        else:
            units = 1.0 / self.shares.split_factor(symbol, last, c.counted)
        return c.shares * units * close * self.shares.raw_factor(symbol, last)

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

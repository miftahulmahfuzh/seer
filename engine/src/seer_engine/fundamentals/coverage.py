"""Can the panel rank? The dev-window coverage measure, and the floor ``lab run`` enforces.

M0005 was spent against a store whose panel held no fact filed before 2013, on a dev window that
opens in 1996. The check that was meant to catch that asked ``panel.as_of(symbol, t) is not
None`` -- and that question is vacuous. ``FundamentalPanel.as_of`` returns None only for a symbol
with no fact at ALL, ever, and ``SymbolFundamentals.as_of`` always answers with a ``Snapshot``: an
empty husk whose ``observations`` is ``{}`` when nothing is visible at ``t``. All 780 symbols of
the measured panel therefore passed that check on every date in 1996, and the number it produced
measured nothing. **The honest emptiness test is ``Snapshot.observations``.** The anti-pattern
must not appear anywhere in this tree except in this paragraph, which documents it.

What this module answers instead: *on how many sampled dev-window dates can the panel rank at
least ``top`` symbols?* A symbol counts on date ``t`` only when both

1. ``panel.as_of(symbol, t)`` has a **non-empty** ``observations``, and
2. that snapshot's newest ``filed`` is within ``max_stale_days`` days of ``t``.

(2) is ``strategies.f_fundamental``'s own eligibility gate, restated here deliberately so the
number predicts *rankability* rather than mere fact-existence: a symbol whose newest filing is
three years old is in the panel and is in no cross-section ``FUNDAMENTAL`` ever builds. The
window itself is read off ``FundamentalParams`` rather than written down again -- see
``default_max_stale_days``.

**The measure is an upper bound.** ``f_fundamental.eligible_rows`` additionally requires index
membership, a close at or above ``min_price``, twenty sessions of history and dollar volume above
``min_dollar_volume``; every one of those can only remove symbols. So a number below the floor is
conclusive -- the panel cannot rank -- while a number above it is necessary and not sufficient.
Bars are deliberately not read: this module is pure and takes a panel, nothing else.

Pure: no database, network, clock, randomness or file IO (tests/test_strategy_purity.py globs
``fundamentals/*.py``, so this file is policed automatically). Two consequences worth stating:

* ``format_report`` **returns** a string. ``print`` is forbidden here; the CLI prints.
* ``seer_engine.strategies.f_fundamental`` is imported **inside** ``default_max_stale_days``, not
  at module scope. That module imports this package at its own module scope
  (``f_fundamental.py:96``), so a module-scope import here would make
  ``import seer_engine.strategies.f_fundamental`` fail in a fresh interpreter.

``WINDOW_START`` and ``WINDOW_END`` are duplicated constants, pinned to ``backtest.dev`` and
``research`` by a test, for the same reason ``research.DEV_END`` duplicates ``dev.DEV_END``:
``backtest.dev`` imports ``backtest.market``, which imports this package, and ``research``
imports yfinance.
"""

from __future__ import annotations

import calendar
from collections.abc import Sequence
from dataclasses import dataclass, fields
from datetime import date, datetime

from seer_engine.fundamentals.panel import FundamentalPanel, Snapshot

WINDOW_START = date(1996, 1, 2)
"""First sampled date: the first ``sp500_history.csv`` row.

== ``backtest.dev.MEMBERSHIP_START`` == ``research.MEMBERSHIP_START``, pinned by
``test_fundamentals_coverage.py``. Not imported; see the module docstring.
"""

WINDOW_END = date(2015, 10, 16)
"""Last sampled date: the last dev session.

== ``backtest.dev.DEV_END`` == ``research.DEV_END``, pinned by the same test.
"""

DEFAULT_TOP = 20
"""How many symbols the panel must be able to rank for a date to count as covered.

``FundamentalParams.top``'s own default, and what every M0005 variant asked for. A date on which
fewer than this many symbols are rankable cannot fill the book from fundamentals.
"""

MIN_DEV_COVERAGE = 0.80
"""The fraction of sampled dev-window dates a ``MarketAware`` method's store must cover.

``lab run`` refuses below this (``lab.runner.preflight_data``). It is a floor on the *data*, not
on the hypothesis: a method whose panel can rank on four dates in five still has to beat SPY.
"""


class CoverageError(ValueError):
    """A coverage measurement was asked for on an impossible window or an invalid parameter."""


def _check_date(name: str, d: object) -> date:
    if isinstance(d, datetime) or not isinstance(d, date):
        raise CoverageError(f"{name} must be a date, got {type(d).__name__}")
    return d


def _check_int(name: str, v: object) -> int:
    if isinstance(v, bool) or not isinstance(v, int):
        raise CoverageError(f"{name} must be an int, got {type(v).__name__}")
    if v < 1:
        raise CoverageError(f"{name} must be >= 1, got {v}")
    return v


def default_max_stale_days() -> int:
    """``FundamentalParams.max_stale_days``'s own default, read off the dataclass.

    Read rather than restated: if the strategy's staleness window ever moves, the coverage
    measure moves with it and no second literal has to be found. The import is deliberately
    deferred -- ``strategies.f_fundamental`` imports this package at module scope, so importing
    it at module scope here would be a cycle. See the module docstring.
    """
    from seer_engine.strategies.f_fundamental import FundamentalParams

    for f in fields(FundamentalParams):
        if f.name == "max_stale_days":
            return _check_int("max_stale_days", f.default)
    raise CoverageError("FundamentalParams has no max_stale_days field")


def is_rankable(snapshot: Snapshot | None, t: date, max_stale_days: int) -> bool:
    """Can ``f_fundamental`` put this snapshot into its cross-section on ``t``?

    Mirrors ``strategies/f_fundamental.py``'s eligibility gate, in its order:

    * None means the panel has no fact for the symbol at all -- not rankable.
    * An **empty ``observations``** means nothing was visible at ``t``. This is the check, and
      the only honest one: a ``Snapshot`` exists for every symbol the panel knows, on every date
      in the window, whether or not anything had been filed.
    * ``filed is None`` cannot happen with non-empty observations, and ``filed > t`` would be a
      point-in-time bug rather than a stale fact. Both are refused anyway: this is the one
      assertion standing between a look-ahead and a backtest that looks wonderful.
    * A newest filing older than ``max_stale_days`` is stale -- in the panel, not in the book.
    """
    if snapshot is None:
        return False
    if not snapshot.observations:
        return False
    filed = snapshot.filed
    if filed is None or filed > t:
        return False
    return (t - filed).days <= max_stale_days


def rankable_symbols(
    panel: FundamentalPanel,
    t: date,
    *,
    max_stale_days: int | None = None,
) -> tuple[str, ...]:
    """Every symbol ``panel`` could rank on ``t``, sorted.

    ``max_stale_days`` defaults to ``default_max_stale_days()``. Membership, price and liquidity
    are not applied -- they are the caller's bars, and they can only shorten this list.
    """
    _check_date("t", t)
    stale = default_max_stale_days() if max_stale_days is None else _check_int("max_stale_days", max_stale_days)
    return tuple(s for s in panel.names() if is_rankable(panel.as_of(s, t), t, stale))


def rankable_count(panel: FundamentalPanel, t: date, *, max_stale_days: int | None = None) -> int:
    """How many symbols ``panel`` could rank on ``t``."""
    return len(rankable_symbols(panel, t, max_stale_days=max_stale_days))


def monthly_dates(start: date = WINDOW_START, end: date = WINDOW_END) -> tuple[date, ...]:
    """``start``, then the same day of month in every later month, through ``end``.

    A month shorter than ``start.day`` contributes its last day, so the sample is exactly one
    date per calendar month with no gaps and no dependence on a trading calendar. The default
    window gives 238 dates, 1996-01-02 .. 2015-10-02.
    """
    _check_date("start", start)
    _check_date("end", end)
    if end < start:
        raise CoverageError(f"end {end} is before start {start}")
    out: list[date] = []
    year, month = start.year, start.month
    while True:
        d = date(year, month, min(start.day, calendar.monthrange(year, month)[1]))
        if d > end:
            break
        if d >= start:
            out.append(d)
        month = month + 1
        if month == 13:
            year, month = year + 1, 1
    return tuple(out)


@dataclass(frozen=True, slots=True)
class YearCoverage:
    """One calendar year of a sample: dates sampled, dates covered, and the best date's count."""

    year: int
    sampled: int
    covered: int
    most_rankable: int


@dataclass(frozen=True, slots=True)
class Coverage:
    """What a panel can rank across a sampled window. Build it with :func:`measure`.

    ``counts[i]`` is how many symbols were rankable on ``dates[i]``. A date is *covered* when
    that count is at least ``top``. ``symbols`` is how many symbols the panel holds at all --
    reported next to the fraction precisely so that a large panel with a tiny coverage cannot be
    mistaken for a small one.
    """

    top: int
    max_stale_days: int
    dates: tuple[date, ...]
    counts: tuple[int, ...]
    symbols: int

    def __post_init__(self) -> None:
        if not self.dates:
            raise CoverageError("a coverage measurement needs at least one sampled date")
        if len(self.dates) != len(self.counts):
            raise CoverageError(f"{len(self.dates)} dates but {len(self.counts)} counts")

    @property
    def start(self) -> date:
        """The first sampled date."""
        return self.dates[0]

    @property
    def end(self) -> date:
        """The last sampled date."""
        return self.dates[-1]

    @property
    def covered_dates(self) -> int:
        """Sampled dates on which at least ``top`` symbols were rankable."""
        return sum(1 for c in self.counts if c >= self.top)

    @property
    def fraction(self) -> float:
        """``covered_dates`` over sampled dates: the one number the floor is compared against."""
        return self.covered_dates / len(self.dates)

    def by_year(self) -> tuple[YearCoverage, ...]:
        """One :class:`YearCoverage` per calendar year present in the sample, ascending."""
        rows: dict[int, list[int]] = {}
        for d, c in zip(self.dates, self.counts, strict=True):
            row = rows.setdefault(d.year, [0, 0, 0])
            row[0] = row[0] + 1
            if c >= self.top:
                row[1] = row[1] + 1
            if c > row[2]:
                row[2] = c
        return tuple(YearCoverage(y, rows[y][0], rows[y][1], rows[y][2]) for y in sorted(rows))


def measure(
    panel: FundamentalPanel,
    *,
    start: date = WINDOW_START,
    end: date = WINDOW_END,
    top: int = DEFAULT_TOP,
    max_stale_days: int | None = None,
    dates: Sequence[date] | None = None,
) -> Coverage:
    """How much of ``start..end`` ``panel`` can rank, sampled monthly.

    ``dates`` replaces the monthly sample outright (``start`` and ``end`` are then unused); it
    exists for tests and for a caller that wants a denser look. ``max_stale_days`` defaults to
    ``default_max_stale_days()``, i.e. to whatever ``f_fundamental`` currently enforces.

    An empty panel is a normal input and measures 0.0; it is not an error. An empty *sample* is.
    """
    if not isinstance(panel, FundamentalPanel):
        raise CoverageError(f"panel must be a FundamentalPanel, got {type(panel).__name__}")
    _check_int("top", top)
    stale = default_max_stale_days() if max_stale_days is None else _check_int("max_stale_days", max_stale_days)
    if dates is None:
        sample = monthly_dates(start, end)
    else:
        sample = tuple(dates)
        for i, d in enumerate(sample):
            _check_date(f"dates[{i}]", d)
    if not sample:
        raise CoverageError("a coverage measurement needs at least one sampled date")
    counts = tuple(len(rankable_symbols(panel, d, max_stale_days=stale)) for d in sample)
    return Coverage(top=top, max_stale_days=stale, dates=sample, counts=counts, symbols=len(panel))


def format_report(cov: Coverage, *, floor: float = MIN_DEV_COVERAGE) -> str:
    """``cov`` as a per-year table and one fraction, as a string. Prints nothing (this module is pure).

    The last two lines are the point of the whole phase: the number, whether it clears the floor,
    and the reminder that it is an upper bound.
    """
    lines = [
        f"panel coverage {cov.start} .. {cov.end}: {len(cov.dates)} monthly samples, "
        f"{cov.symbols} symbols in the panel",
        f"  rankable: non-empty observations AND a filing within {cov.max_stale_days} days; "
        f"covered: at least {cov.top} rankable symbols",
        "  year    covered/sampled    most rankable",
    ]
    for row in cov.by_year():
        lines.append(f"  {row.year}    {row.covered:>5}/{row.sampled:<5}      {row.most_rankable:>8}")
    verdict = "at or above" if cov.fraction >= floor else "BELOW"
    lines.append(
        f"  covered {cov.covered_dates} of {len(cov.dates)} sampled dates = {cov.fraction:.4f} "
        f"({verdict} the {floor:.2f} floor)"
    )
    lines.append(
        "  an upper bound: index membership, min_price and min_dollar_volume can only remove symbols"
    )
    return "\n".join(lines)

"""Stocks the owner's broker does not offer (migration 014): taken out of the paper universe.

Pure: no database, no clock. A :class:`Window` says a symbol could not be bought from ``since`` up
to ``until`` (exclusive; None = still not offered). :func:`clip` removes those days from the index
membership intervals, so on a date inside a window the symbol is simply not a member: every
allocator, Strategy C's candidate list and the evidence counts skip it, and the method's
next-best stock takes its place. Bars are left alone, so a stock already held still settles.

Only the paper market reads this (``paper.store.load_market_window``); the lab and the backtests
never do.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date

Interval = tuple[str, date, date | None]


@dataclass(frozen=True)
class Window:
    """One ``unavailable_symbols`` row: ``symbol`` not offered on ``since <= d < until``."""

    symbol: str
    since: date
    until: date | None = None

    def __post_init__(self) -> None:
        if self.until is not None and self.until < self.since:
            raise ValueError(f"{self.symbol}: until {self.until} is before since {self.since}")

    def covers(self, d: date) -> bool:
        return self.since <= d and (self.until is None or d < self.until)


def excluded_on(windows: Iterable[Window], d: date) -> frozenset[str]:
    """The symbols not offered on ``d``."""
    return frozenset(w.symbol for w in windows if w.covers(d))


def _cut(start: date, end: date | None, w: Window) -> list[tuple[date, date | None]]:
    """``[start, end)`` minus ``[w.since, w.until)``: zero, one or two pieces."""
    if w.until is not None and w.until <= w.since:
        return [(start, end)]  # an empty window removes nothing
    if (end is not None and end <= w.since) or (w.until is not None and w.until <= start):
        return [(start, end)]  # no overlap
    pieces: list[tuple[date, date | None]] = []
    if start < w.since:
        pieces.append((start, w.since))
    if w.until is not None and (end is None or w.until < end):
        pieces.append((w.until, end))
    return pieces


def clip(intervals: Iterable[Interval], windows: Iterable[Window]) -> tuple[Interval, ...]:
    """``intervals`` with every window's days removed from its symbol, order kept."""
    by_symbol: dict[str, list[Window]] = {}
    for w in windows:
        by_symbol.setdefault(w.symbol, []).append(w)
    out: list[Interval] = []
    for symbol, start, end in intervals:
        pieces: list[tuple[date, date | None]] = [(start, end)]
        for w in by_symbol.get(symbol, ()):
            pieces = [p for s, e in pieces for p in _cut(s, e, w)]
        out.extend((symbol, s, e) for s, e in pieces)
    return tuple(out)


def windows_from_rows(rows: Sequence[tuple[str, date, date | None]]) -> tuple[Window, ...]:
    return tuple(Window(symbol=r[0], since=r[1], until=r[2]) for r in rows)


def held_excluded(symbols: Iterable[str], windows: Iterable[Window], d: date) -> list[str]:
    """The ``symbols`` (in order, no repeats) not offered on ``d``."""
    gone = excluded_on(windows, d)
    return list(dict.fromkeys(s for s in symbols if s in gone))


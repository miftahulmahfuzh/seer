"""NYSE session arithmetic.

Dates are ``datetime.date`` values (the ET calendar date of a session). The only
timezone-aware datetimes here are UTC "now" and session closes from the NYSE calendar,
whose ``market_close`` already accounts for half days and daylight saving time.

- ``data_date``: the last completed session, i.e. the latest session whose close plus a
  settle margin is not after now.
- ``session_date``: the session after ``data_date``, which the next picks are for.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache

import pandas_market_calendars as mcal

CALENDAR = "NYSE"
DEFAULT_SETTLE = timedelta(hours=1)

# How many calendar years next_session/prev_session will scan before giving up.
_MAX_YEAR_SCAN = 3


@dataclass(frozen=True, slots=True)
class RunDates:
    data_date: date
    session_date: date


@lru_cache(maxsize=1)
def _calendar() -> mcal.MarketCalendar:
    return mcal.get_calendar(CALENDAR)


@lru_cache(maxsize=None)
def _year(year: int) -> tuple[tuple[date, datetime], ...]:
    """(session date, market close in UTC) for every NYSE session in ``year``, ascending."""
    sched = _calendar().schedule(start_date=f"{year}-01-01", end_date=f"{year}-12-31")
    out: list[tuple[date, datetime]] = []
    for idx, close in zip(sched.index, sched["market_close"]):
        out.append((idx.date(), close.to_pydatetime().astimezone(timezone.utc)))
    return tuple(out)


@lru_cache(maxsize=None)
def _closes(year: int) -> dict[date, datetime]:
    return dict(_year(year))


def _as_date(d: date) -> date:
    if isinstance(d, datetime):
        raise TypeError(f"expected a date, got a datetime: {d!r}")
    if not isinstance(d, date):
        raise TypeError(f"expected a date, got {type(d).__name__}")
    return d


def _as_utc(now_utc: datetime) -> datetime:
    if not isinstance(now_utc, datetime):
        raise TypeError(f"expected a datetime, got {type(now_utc).__name__}")
    if now_utc.tzinfo is None or now_utc.utcoffset() is None:
        raise ValueError("now_utc must be timezone-aware")
    return now_utc.astimezone(timezone.utc)


def sessions(start: date, end: date) -> list[date]:
    """Every NYSE session from ``start`` to ``end``, both inclusive, ascending."""
    start, end = _as_date(start), _as_date(end)
    if end < start:
        return []
    out: list[date] = []
    for year in range(start.year, end.year + 1):
        out.extend(d for d, _ in _year(year) if start <= d <= end)
    return out


def is_session(d: date) -> bool:
    """True when ``d`` is an NYSE trading day (half days included)."""
    d = _as_date(d)
    return d in _closes(d.year)


def next_session(d: date) -> date:
    """The first NYSE session strictly after ``d``."""
    d = _as_date(d)
    for year in range(d.year, d.year + _MAX_YEAR_SCAN):
        for s, _ in _year(year):
            if s > d:
                return s
    raise ValueError(f"no NYSE session after {d} within {_MAX_YEAR_SCAN} years")


def prev_session(d: date) -> date:
    """The last NYSE session strictly before ``d``."""
    d = _as_date(d)
    for year in range(d.year, d.year - _MAX_YEAR_SCAN, -1):
        for s, _ in reversed(_year(year)):
            if s < d:
                return s
    raise ValueError(f"no NYSE session before {d} within {_MAX_YEAR_SCAN} years")


def session_close_utc(d: date) -> datetime:
    """The scheduled close of session ``d`` in UTC (18:00 UTC on a winter half day)."""
    d = _as_date(d)
    try:
        return _closes(d.year)[d]
    except KeyError:
        raise ValueError(f"{d} is not an NYSE session") from None


def last_completed_session(now_utc: datetime, settle: timedelta = DEFAULT_SETTLE) -> date:
    """The latest session whose close + ``settle`` is at or before ``now_utc``."""
    now = _as_utc(now_utc)
    cutoff = now - settle
    # A session's close falls on its own UTC calendar date, so nothing after now's UTC date
    # can have closed yet.
    today = now.date()
    s = today if is_session(today) else prev_session(today)
    while session_close_utc(s) > cutoff:
        s = prev_session(s)
    return s


def run_dates(now_utc: datetime | None = None, settle: timedelta = DEFAULT_SETTLE) -> RunDates:
    """The dates a run started at ``now_utc`` (default: the current time) works with."""
    now = datetime.now(timezone.utc) if now_utc is None else now_utc
    data_date = last_completed_session(now, settle)
    return RunDates(data_date=data_date, session_date=next_session(data_date))

"""``Market.dividends``: the point-in-time ex-date calendar an allocator may rank on (M0051).

The purity half of the contract: ``known_on(symbol, data_date)`` never returns an ex-date after
``data_date``, so an allocator that asks with the ``data_date`` it was handed sees exactly what a
calendar cut at that date would show it. The load half lives in ``test_research_test_store``.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from labkit import smoke_market

from seer_engine.backtest.market import EMPTY_DIVIDENDS, DividendCalendar

ROWS = {
    "KO": {date(2014, 3, 12): Decimal("0.305"), date(2014, 6, 12): Decimal("0.305"),
           date(2014, 9, 11): Decimal("0.305"), date(2014, 11, 26): Decimal("0.305")},
    "XOM": {date(2014, 5, 8): Decimal("0.69"), date(2014, 8, 13): Decimal("0.69")},
}


def _cut(rows, d):
    return {s: {x: a for x, a in by.items() if x <= d} for s, by in rows.items()}


def test_known_on_returns_only_ex_dates_on_or_before_the_data_date():
    cal = DividendCalendar.from_map(ROWS)
    assert cal.known_on("KO", date(2014, 3, 11)) == ()
    assert cal.known_on("KO", date(2014, 3, 12)) == ((date(2014, 3, 12), Decimal("0.305")),)
    assert [d for d, _ in cal.known_on("KO", date(2014, 10, 1))] == [
        date(2014, 3, 12), date(2014, 6, 12), date(2014, 9, 11)]
    assert cal.known_on("NOPE", date(2014, 12, 31)) == ()
    assert len(cal) == 6 and cal.symbols() == ("KO", "XOM")


def test_no_future_ex_date_is_visible_on_any_day():
    """Every day of 2014: the full calendar read at d equals a calendar built from rows <= d."""
    full = DividendCalendar.from_map(ROWS)
    d = date(2013, 12, 31)
    while d <= date(2015, 1, 2):
        cut = DividendCalendar.from_map(_cut(ROWS, d))
        for symbol in ROWS:
            got = full.known_on(symbol, d)
            assert got == cut.known_on(symbol, d)
            assert all(x <= d for x, _ in got)
        d += timedelta(days=1)


@pytest.mark.parametrize("rows,err", [
    ({"KO": [(date(2014, 6, 1), Decimal("1")), (date(2014, 6, 1), Decimal("1"))]}, ValueError),
    ({"KO": [(date(2014, 6, 2), Decimal("1")), (date(2014, 6, 1), Decimal("1"))]}, ValueError),
    ({"KO": [(date(2014, 6, 1), Decimal("0"))]}, ValueError),
    ({"KO": [(date(2014, 6, 1), 0.5)]}, ValueError),
    ({"": [(date(2014, 6, 1), Decimal("1"))]}, ValueError),
    ({"KO": [("2014-06-01", Decimal("1"))]}, TypeError),
])
def test_bad_rows_are_refused(rows, err):
    with pytest.raises(err):
        DividendCalendar(rows)


def test_a_market_without_dividends_carries_the_shared_empty_calendar():
    m = smoke_market()
    assert m.dividends is EMPTY_DIVIDENDS
    assert m.dividends.known_on("SPY", date(2015, 10, 16)) == ()
    cal = DividendCalendar.from_map(ROWS)
    m2 = m.with_dividends(cal)
    assert m2.dividends is cal and m.dividends is EMPTY_DIVIDENDS
    assert m2.history is m.history
    with pytest.raises(TypeError):
        m.with_dividends(ROWS)

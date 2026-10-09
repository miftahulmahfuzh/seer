"""M0051's live path reads the dividend calendar point in time (the method lab's no-look-ahead).

``test_lab_methods`` drives only the history path, where a market-aware allocator targets
nothing. This drives ``prepare_market`` on a smoke market carrying a calendar and checks, on
every month's rank session, that the targets equal those computed from bars AND dividends cut
at ``data_date`` -- so neither a future bar nor a future ex-date can move a pick.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from allocatorkit import upto
from labkit import MEMBER_STOCKS, smoke_market

from seer_engine import dates
from seer_engine.backtest.dev import DEV_END
from seer_engine.backtest.market import DividendCalendar
from seer_engine.lab.methods.m0051_dividend_month_premium import DIVMONTH, METHOD, holding_month, predicted


def _calendar() -> dict[str, dict[date, Decimal]]:
    """Quarterly payers on staggered cycles: AAA/DDD/GGG Jan-Apr-Jul-Oct, BBB/EEE/HHH Feb..., CCC/FFF Mar..."""
    out: dict[str, dict[date, Decimal]] = {}
    for k, s in enumerate(MEMBER_STOCKS):
        rows = {}
        for year in range(2013, 2016):
            for m in range(1 + k % 3, 13, 3):
                d = date(year, m, 10)
                if d <= DEV_END:
                    rows[d] = Decimal("0.2") + Decimal(k) / 100
        out[s] = rows
    return out


def _cut(rows, d):
    return {s: {x: a for x, a in by.items() if x <= d} for s, by in rows.items()}


def test_prediction_reads_m_minus_3_and_m_minus_12():
    paid = ((date(2014, 1, 10), Decimal("1")),)
    assert predicted(paid, (2014, 4)) and predicted(paid, (2015, 1))
    assert not predicted(paid, (2014, 2)) and not predicted(paid, (2014, 7))
    assert holding_month(date(2015, 3, 31)) == (2015, 4)
    assert holding_month(date(2015, 3, 30)) == (2015, 3)


@pytest.mark.parametrize("c", METHOD.candidates, ids=[c.id for c in METHOD.candidates])
def test_live_path_never_looks_ahead_and_picks_something(c):
    rows = _calendar()
    market = smoke_market().with_dividends(DividendCalendar.from_map(rows))
    prepared = DIVMONTH.prepare_market(market)
    members = frozenset(MEMBER_STOCKS)
    nonempty = 0
    rank_days = [s for s in dates.sessions(date(2014, 12, 1), DEV_END) if s.day <= 7
                 and dates.prev_session(s).month != s.month]
    assert len(rank_days) >= 10
    for s in rank_days:
        d = dates.prev_session(s)
        live = DIVMONTH.targets_prepared(prepared, members, d, frozenset(), c.params)
        cut = DIVMONTH.targets_with_calendar(upto(market.history, d), DividendCalendar.from_map(_cut(rows, d)),
                                             members, d, c.params)
        assert live == cut, (c.id, d)
        nonempty += bool(live)
        if c.params.when == "on":
            month = holding_month(d)
            for t in live:
                assert predicted(market.dividends.known_on(t.symbol, d), month)
    assert nonempty > 0, f"{c.id}: no rank session picked anything"


def test_history_only_path_targets_nothing():
    market = smoke_market()
    for c in METHOD.candidates:
        assert DIVMONTH.targets(market.history, frozenset(MEMBER_STOCKS), date(2015, 6, 30), frozenset(), c.params) == ()

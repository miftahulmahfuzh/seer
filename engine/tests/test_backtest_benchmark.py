"""The dollar-cost-averaged SPY benchmark (plan set R3, handover section 4).

"Beats SPY TR" only means something if SPY is fed the same money on the same days as the book it
is compared against. These tests pin that the schedule reaches both curves, that the money lands
on the first session on or after its calendar date (so the owner's 25th-of-the-month deposit is
idle for the measured mean of 7.0 days before it buys anything), and that a curve built with no
contributions is byte-for-byte the curve this module has always produced.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from seer_engine import dates
from seer_engine.backtest.benchmark import Dividend, buy_and_hold, spy_curves
from seer_engine.backtest.metrics import curve_metrics
from seer_engine.prices import Bar

START = date(2015, 1, 2)
END = date(2015, 12, 31)
CASH0 = Decimal("10000.0000")


def _bar(d: date, price: str) -> Bar:
    """One flat bar. ``Bar`` is ``(symbol, date, open, high, low, close, volume)``
    (``seer_engine/prices.py:19-26``) -- the symbol field is easy to forget."""
    p = Decimal(price)
    return Bar(symbol="SPY", date=d, open=p, high=p, low=p, close=p, volume=1_000_000)


def _bars(start: date, end: date, price: str = "100.00") -> dict[date, Bar]:
    """A flat SPY at one price: every session's open, high, low and close are the same, so a
    curve's equity moves only when cash moves and the arithmetic is readable by hand."""
    return {d: _bar(d, price) for d in dates.sessions(start, end)}


def _schedule(first: date, months: int, amount: str = "500.0000") -> list[tuple[date, Decimal]]:
    """The owner's shape: the 25th of each month, as a calendar date (plan set Decision D6)."""
    out: list[tuple[date, Decimal]] = []
    for i in range(months):
        year = first.year + (first.month + i - 1) // 12
        month = (first.month + i - 1) % 12 + 1
        out.append((date(year, month, 25), Decimal(amount)))
    return out


def test_no_contributions_is_the_curve_this_module_has_always_produced():
    spy = _bars(START, END)
    plain = buy_and_hold(spy, START, END, CASH0, name="spy_price")
    explicit = buy_and_hold(spy, START, END, CASH0, name="spy_price", contributions=())
    assert plain == explicit
    assert plain.cashflows == ()
    assert curve_metrics(plain).mwr is None  # no deposits: CAGR already is the money-weighted return


def test_a_deposit_lands_on_the_first_session_on_or_after_its_date():
    """2015-12-25 was Christmas Day, an NYSE holiday: the money arrives on 2015-12-28."""
    spy = _bars(START, END)
    assert not dates.is_session(date(2015, 12, 25))
    curve = buy_and_hold(
        spy, START, END, CASH0, name="spy_price",
        contributions=[(date(2015, 12, 25), Decimal("500.0000"))],
    )
    assert [d for d, _ in curve.cashflows] == [date(2015, 12, 28)]

    # Measured against the unfunded curve rather than a hand-computed number, so the test states
    # the property -- identical until the money lands, then ahead by it less the fee of spending
    # it -- instead of restating the fee schedule.
    plain = buy_and_hold(spy, START, END, CASH0, name="spy_price")
    before = {s.date: s.equity_usd for s in plain.snapshots}
    after = {s.date: s.equity_usd for s in curve.snapshots}
    assert before[date(2015, 12, 24)] == after[date(2015, 12, 24)], "identical until the money lands"
    gained = after[date(2015, 12, 28)] - before[date(2015, 12, 28)]
    assert Decimal("499") < gained <= Decimal("500"), (
        "a flat market gives back the deposit less the fee of putting it to work"
    )


def test_a_deposit_dated_on_a_session_lands_on_that_session_not_the_next():
    spy = _bars(START, END)
    assert dates.is_session(date(2015, 6, 25))
    curve = buy_and_hold(
        spy, START, END, CASH0, name="spy_price",
        contributions=[(date(2015, 6, 25), Decimal("500.0000"))],
    )
    assert [d for d, _ in curve.cashflows] == [date(2015, 6, 25)]


def test_deposits_outside_the_window_are_dropped_like_a_dividend_on_the_start():
    spy = _bars(START, END)
    curve = buy_and_hold(
        spy, START, END, CASH0, name="spy_price",
        contributions=[
            (date(2014, 12, 25), Decimal("500.0000")),  # lands on START: the opening cash is the opening cash
            (date(2015, 6, 25), Decimal("500.0000")),
            (date(2016, 1, 25), Decimal("500.0000")),   # after END
        ],
    )
    assert [d for d, _ in curve.cashflows] == [date(2015, 6, 25)]


def test_the_deposit_is_spent_so_the_curve_rides_the_market_with_it():
    """A flat market holds the deposit as equity; a rising one must compound it. Buying is what
    makes this dollar-cost averaging rather than a savings account."""
    rising = _bars(START, END)
    for d in dates.sessions(date(2015, 7, 1), END):
        rising[d] = _bar(d, "200.00")
    curve = buy_and_hold(
        rising, START, END, CASH0, name="spy_price",
        contributions=[(date(2015, 2, 25), Decimal("1000.0000"))],
    )
    assert curve.cash < Decimal("200.0000"), "the deposit was put to work, not left idle"
    assert curve.snapshots[-1].equity_usd > CASH0 * 2


def test_a_credited_deposit_raises_equity_as_well_as_cash():
    """Invariant B2, the rule phases 6 and 7 both honour. On this side it holds by construction:
    the deposit is added to cash and the session is re-marked ``cash + shares * close``, so the
    equity carries it with no separate step and a deposit can never be under-deployed."""
    spy = _bars(START, END)
    landing = date(2015, 6, 25)
    plain = buy_and_hold(spy, START, END, CASH0, name="spy_price")
    funded = buy_and_hold(
        spy, START, END, CASH0, name="spy_price",
        contributions=[(landing, Decimal("500.0000"))],
    )
    before = {s.date: s for s in plain.snapshots}[landing]
    after = {s.date: s for s in funded.snapshots}[landing]
    gained = after.equity_usd - before.equity_usd
    assert Decimal("499") < gained <= Decimal("500"), "equity rose by the deposit, less its fee"
    assert after.cash_usd != after.equity_usd, "the deposit was spent, not parked"


def test_two_deposits_landing_on_one_session_are_summed_and_spent_once():
    spy = _bars(START, END)
    curve = buy_and_hold(
        spy, START, END, CASH0, name="spy_price",
        contributions=[
            (date(2015, 12, 25), Decimal("300.0000")),  # holiday -> 12-28
            (date(2015, 12, 26), Decimal("200.0000")),  # weekend -> 12-28
        ],
    )
    assert curve.cashflows == ((date(2015, 12, 28), Decimal("500.0000")),)


def test_both_spy_curves_receive_the_schedule():
    spy = _bars(START, END)
    schedule = _schedule(date(2015, 2, 25), 10)
    divs = (Dividend(ex_date=date(2015, 3, 20), amount=Decimal("1.00")),)
    price, total = spy_curves(spy, START, END, CASH0, divs, contributions=schedule)
    assert price.cashflows == total.cashflows
    assert len(price.cashflows) == 10
    assert total.dividends_usd > 0 and price.dividends_usd == 0


def test_a_dollar_cost_averaged_spy_reports_a_money_weighted_return():
    spy = _bars(START, END)
    schedule = _schedule(date(2015, 2, 25), 10)
    curve = buy_and_hold(spy, START, END, CASH0, name="spy_tr", contributions=schedule)
    m = curve_metrics(curve)
    assert m.mwr is not None, "a curve that was fed deposits has a money-weighted return"
    assert -0.02 < m.mwr < 0.0, (
        "a flat market earns nothing however much you pay into it -- the small negative is the "
        "fee on each buy, which is the only thing that happens here"
    )
    assert m.total_return is not None and m.total_return > 0.4, (
        "...while total return counts the deposits as growth, which is the whole problem"
    )


def test_contributions_are_validated():
    spy = _bars(START, END)
    with pytest.raises(TypeError, match="must be a Decimal"):
        buy_and_hold(spy, START, END, CASH0, name="x", contributions=[(date(2015, 6, 25), 500.0)])
    with pytest.raises(ValueError, match="must be > 0"):
        buy_and_hold(spy, START, END, CASH0, name="x", contributions=[(date(2015, 6, 25), Decimal("0"))])
    with pytest.raises(ValueError, match="not strictly ascending"):
        buy_and_hold(
            spy, START, END, CASH0, name="x",
            contributions=[(date(2015, 6, 25), Decimal("1")), (date(2015, 5, 25), Decimal("1"))],
        )


# --------------------------------------------------------------------------- the dev path, fed
#
# Exit criterion 7: the keyword phase 8's sweep runs on, and the row it produces. These live here
# rather than in test_backtest_dev.py because this phase creates this file and does not own that
# one; the market fixture is imported, which is how test_backtest_metrics.py already reaches
# test_backtest_runner's.


def test_run_registry_takes_a_contribution_schedule_and_feeds_book_and_spy_alike():
    """``phase-8.md``'s ``check_schedule_support()`` looks for exactly this keyword, and reads the
    money-weighted return off ``row.stats.metrics.mwr``.

    Both engines must answer. A ``RunResult`` gets its IRR through ``metrics.run_metrics``; a
    ``BookResult`` is built by ``book_runner._book_metrics``, which takes no cashflows, so
    ``dev._funded_stats`` fills it in -- without which the four book methods on the roster would
    rank on a CAGR that counts the owner's own deposits as growth.
    """
    import inspect

    from seer_engine.backtest import dev
    from seer_engine.sim.contributions import OWNER_MONTHLY
    from test_backtest_dev import DIVS, SPY_DIVS, short_market, short_registry

    assert "contributions" in inspect.signature(dev.run_registry).parameters

    market = short_market()
    registry, _, _, _ = short_registry()
    rows = dev.run_registry(market, DIVS, SPY_DIVS, registry, contributions=OWNER_MONTHLY)
    engines = {r.candidate.rules.engine for r in rows}
    assert {"book", "bracket_v0"} <= engines, "both engines must be exercised, or this pins nothing"
    for r in rows:
        assert r.stats.metrics.mwr is not None, f"{r.candidate.id} ({r.candidate.rules.engine})"
        assert r.spy_tr.mwr is not None, f"{r.candidate.id}: SPY was not fed the same money"
        assert r.mar is None or r.mar == r.stats.metrics.mwr / r.stats.metrics.max_drawdown, (
            "MAR must rank on the money-weighted return once the book was fed"
        )


def test_an_unfunded_registry_run_is_bit_for_bit_what_it_was():
    """Decision D7b: ``mwr`` is None on a run with no deposits, so every recorded ``cagr``,
    ``mar`` and eligibility is unchanged. This is what lets the phase land under a frozen lab."""
    from seer_engine.backtest import dev
    from test_backtest_dev import DIVS, SPY_DIVS, short_market, short_registry

    market = short_market()
    registry, _, _, _ = short_registry()
    rows = dev.run_registry(market, DIVS, SPY_DIVS, registry)
    for r in rows:
        assert r.stats.metrics.mwr is None
        assert r.spy_tr.mwr is None and r.spy_price.mwr is None
        assert r.mar is None or r.mar == r.stats.metrics.cagr / r.stats.metrics.max_drawdown

"""SPY buy-and-hold benchmark (handover §6 item 5) and the vendored dividend file.

Window used throughout: the week 2026-03-02 (Mon) .. 2026-03-06 (Fri), all NYSE sessions;
prev_session(2026-03-02) = 2026-02-27. Starting cash 1000.0000 USD.

Hand computation (open 100 on 03-02; closes 101, 102, 98, 99, 100.5):
  buy: floor(1000 / (100 × 1.001)) = floor(9.99) = 9 shares, cost q(900.9) = 900.9000,
       cash 99.1000 idle.
  price-only equity = 99.1 + 9 × close: 1008.1, 1017.1, 981.1, 990.1, 1003.6
  total return, dividend 2.50 ex 03-04 (close 98):
       cash 99.1 + q(9 × 2.5) = 121.6; floor(121.6 / 98.098) = 1 more share,
       cost q(98.098) = 98.0980, cash 23.5020, 10 shares.
       equity: 1008.1, 1017.1, 23.502 + 980 = 1003.502, 1013.502, 1028.502
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

import seer_engine
from seer_engine.backtest.benchmark import (
    DIVIDENDS_HEADER,
    BenchmarkCurve,
    Dividend,
    buy_and_hold,
    parse_dividends,
    spy_curves,
)
from seer_engine.dates import is_session
from seer_engine.sim import Snapshot
from simkit import D, P, bar

CASH = P("1000")
START = D("2026-03-02")
END = D("2026-03-06")
DIV_CSV = Path(seer_engine.__file__).resolve().parents[2] / "data" / "spy_dividends.csv"

# (date, open, close); high/low do not matter to the benchmark.
_WEEK = [
    ("2026-03-02", "100", "101"),
    ("2026-03-03", "101", "102"),
    ("2026-03-04", "100", "98"),
    ("2026-03-05", "98", "99"),
    ("2026-03-06", "99", "100.5"),
]


def spy_bars(rows=_WEEK) -> dict[date, object]:
    out = {}
    for d, o, c in rows:
        hi = max(Decimal(o), Decimal(c)) + 1
        lo = min(Decimal(o), Decimal(c)) - 1
        b = bar("SPY", d, o, hi, lo, c, 50_000_000)
        out[b.date] = b
    return out


def equities(curve: BenchmarkCurve) -> list[Decimal]:
    return [s.equity_usd for s in curve.snapshots]


def div(d: str, amount: str) -> Dividend:
    return Dividend(D(d), Decimal(amount))


# ----------------------------------------------------------------------------- price-only


def test_price_only_whole_shares_cost_and_idle_cash():
    c = buy_and_hold(spy_bars(), START, END, CASH, name="spy_price")
    assert c.name == "spy_price"
    assert c.shares == 9
    assert c.cash == P("99.1")
    assert c.dividends_usd == P("0")
    assert c.snapshots[0] == Snapshot(D("2026-02-27"), CASH, CASH)
    assert [s.date for s in c.snapshots[1:]] == [D(d) for d, _, _ in _WEEK]
    assert all(s.cash_usd == P("99.1") for s in c.snapshots[1:])
    assert equities(c) == [P(x) for x in ("1000", "1008.1", "1017.1", "981.1", "990.1", "1003.6")]


def test_price_only_curve_ignores_dividends():
    price, _ = spy_curves(spy_bars(), START, END, CASH, [div("2026-03-04", "2.5")])
    assert price.name == "spy_price"
    assert price.dividends_usd == P("0")
    assert equities(price)[-1] == P("1003.6")


def test_buy_uses_open_not_close_and_cost_can_drop_a_share():
    # 1001 / 100.1 = 10.0 exactly -> 10 shares cost q(1001.0) = 1001.0000, cash 0.
    c = buy_and_hold(spy_bars(), START, END, P("1001"), name="x")
    assert (c.shares, c.cash) == (10, P("0"))
    # 1000.9999 is a hair short of 10 shares with cost -> 9 shares.
    c = buy_and_hold(spy_bars(), START, END, P("1000.9999"), name="x")
    assert (c.shares, c.cash) == (9, P("100.0999"))


def test_cash_below_one_share_holds_cash_only():
    c = buy_and_hold(spy_bars(), START, END, P("100"), name="x")
    assert c.shares == 0
    assert equities(c) == [P("100")] * 6


def test_single_session_window():
    c = buy_and_hold(spy_bars(), START, START, CASH, name="x")
    assert equities(c) == [P("1000"), P("1008.1")]


# ----------------------------------------------------------------------------- total return


def test_total_return_reinvests_dividend_at_ex_date_close():
    price, tr = spy_curves(spy_bars(), START, END, CASH, [div("2026-03-04", "2.5")])
    assert tr.name == "spy_tr"
    assert tr.dividends_usd == P("22.5")
    assert tr.shares == 10
    assert tr.cash == P("23.502")
    assert equities(tr) == [P(x) for x in ("1000", "1008.1", "1017.1", "1003.502", "1013.502", "1028.502")]
    assert [s.cash_usd for s in tr.snapshots] == [P(x) for x in ("1000", "99.1", "99.1", "23.502", "23.502", "23.502")]
    assert equities(tr)[-1] > equities(price)[-1]


def test_dividend_amount_is_quantized_and_cash_remainder_kept():
    # 998 -> 9 shares (cost 900.9000), cash 97.1000. Dividend 0.123456 on 03-04:
    # q(9 x 0.123456 = 1.111104) = 1.1111 -> cash 98.2111; floor(98.2111 / 98.098) = 1 share,
    # cost 98.0980 -> cash 0.1131, 10 shares; equity at 03-06 = 0.1131 + 1005 = 1005.1131.
    tr = buy_and_hold(spy_bars(), START, END, P("998"), dividends=[div("2026-03-04", "0.123456")], name="spy_tr")
    assert tr.dividends_usd == P("1.1111")
    assert (tr.shares, tr.cash) == (10, P("0.1131"))
    assert equities(tr)[-1] == P("1005.1131")


def test_dividend_too_small_for_a_share_stays_idle_cash():
    # 900.9: floor(900.9 / 100.1) = 9 exactly (cost 900.9000), cash 0.
    # Dividend 1.00 on 03-04: cash q(9 x 1) = 9.0000 < 98.098 -> no share bought, cash 9.
    # equity at 03-06 = 9 + 9 x 100.5 = 913.5.
    tr = buy_and_hold(spy_bars(), START, END, P("900.9"), dividends=[div("2026-03-04", "1")], name="spy_tr")
    assert (tr.shares, tr.cash, tr.dividends_usd) == (9, P("9"), P("9"))
    assert equities(tr)[-1] == P("913.5")


def test_dividend_on_start_session_not_credited():
    _, tr = spy_curves(spy_bars(), START, END, CASH, [div("2026-03-02", "2.5")])
    assert tr.dividends_usd == P("0")
    assert equities(tr)[-1] == P("1003.6")


def test_dividends_outside_window_not_credited():
    divs = [div("2026-02-27", "2.5"), div("2026-03-09", "2.5")]
    _, tr = spy_curves(spy_bars(), START, END, CASH, divs)
    assert tr.dividends_usd == P("0")
    assert equities(tr)[-1] == P("1003.6")


def test_dividend_on_end_session_is_credited():
    _, tr = spy_curves(spy_bars(), START, END, CASH, [div("2026-03-06", "2.5")])
    # cash 99.1 + 22.5 = 121.6; floor(121.6 / (100.5 × 1.001 = 100.6005)) = 1; cost 100.6005
    # cash 20.9995, 10 shares, equity 20.9995 + 1005 = 1025.9995
    assert tr.dividends_usd == P("22.5")
    assert (tr.shares, tr.cash) == (10, P("20.9995"))
    assert equities(tr)[-1] == P("1025.9995")


# ----------------------------------------------------------------------------- errors


def test_missing_spy_bar_raises():
    bars = spy_bars()
    del bars[D("2026-03-04")]
    with pytest.raises(ValueError, match="no SPY bar on session 2026-03-04"):
        buy_and_hold(bars, START, END, CASH, name="x")


def test_missing_first_bar_raises():
    bars = spy_bars()
    del bars[START]
    with pytest.raises(ValueError, match="no SPY bar"):
        buy_and_hold(bars, START, END, CASH, name="x")


def test_misdated_bar_raises():
    bars = spy_bars()
    bars[D("2026-03-04")] = bars[D("2026-03-05")]
    with pytest.raises(ValueError, match="dated"):
        buy_and_hold(bars, START, END, CASH, name="x")


@pytest.mark.parametrize(
    ("start", "end"),
    [("2026-03-01", "2026-03-06"), ("2026-03-02", "2026-03-07"), ("2026-03-06", "2026-03-02")],
)
def test_window_must_be_sessions_in_order(start, end):
    with pytest.raises(ValueError):
        buy_and_hold(spy_bars(), D(start), D(end), CASH, name="x")


def test_cash_must_be_positive_decimal():
    with pytest.raises(ValueError):
        buy_and_hold(spy_bars(), START, END, P("0"), name="x")
    with pytest.raises(TypeError):
        buy_and_hold(spy_bars(), START, END, 1000.0, name="x")  # type: ignore[arg-type]


def test_unsorted_or_non_session_dividends_raise():
    with pytest.raises(ValueError, match="ascending"):
        buy_and_hold(spy_bars(), START, END, CASH, dividends=[div("2026-03-05", "1"), div("2026-03-04", "1")], name="x")
    with pytest.raises(ValueError, match="not an NYSE session"):
        buy_and_hold(spy_bars(), START, D("2026-03-09"), CASH, dividends=[div("2026-03-07", "1")], name="x")


def test_deterministic():
    divs = [div("2026-03-04", "2.5")]
    assert spy_curves(spy_bars(), START, END, CASH, divs) == spy_curves(spy_bars(), START, END, CASH, divs)


# ----------------------------------------------------------------------------- parse_dividends


def test_parse_dividends_ok():
    text = f"{DIVIDENDS_HEADER}\n2015-03-20,1.1931\n\n2015-06-19,1.03\n"
    assert parse_dividends(text) == (div("2015-03-20", "1.1931"), div("2015-06-19", "1.03"))
    assert parse_dividends(text)[1].amount == Decimal("1.03")


@pytest.mark.parametrize(
    ("text", "match"),
    [
        ("", "no header"),
        ("date,amount\n2015-03-20,1\n", "expected header"),
        (f"{DIVIDENDS_HEADER}\n2015-03-20\n", "2 fields"),
        (f"{DIVIDENDS_HEADER}\n2015-13-20,1\n", "bad ex_date"),
        (f"{DIVIDENDS_HEADER}\n2015-03-20,abc\n", "bad amount_usd"),
        (f"{DIVIDENDS_HEADER}\n2015-03-20,0\n", "> 0"),
        (f"{DIVIDENDS_HEADER}\n2015-03-20,-1\n", "> 0"),
        (f"{DIVIDENDS_HEADER}\n2015-03-20,NaN\n", "> 0"),
        (f"{DIVIDENDS_HEADER}\n2015-06-19,1\n2015-03-20,1\n", "not after"),
        (f"{DIVIDENDS_HEADER}\n2015-03-20,1\n2015-03-20,1\n", "not after"),
    ],
)
def test_parse_dividends_rejects(text, match):
    with pytest.raises(ValueError, match=match):
        parse_dividends(text)


# ----------------------------------------------------------------------------- vendored file


def test_vendored_spy_dividends_parse_and_cover_2015_2026():
    divs = parse_dividends(DIV_CSV.read_text(encoding="utf-8"))
    by_year: dict[int, int] = {}
    for dv in divs:
        by_year[dv.ex_date.year] = by_year.get(dv.ex_date.year, 0) + 1
        assert is_session(dv.ex_date), dv
        assert Decimal("0.5") < dv.amount < Decimal("3"), dv
    assert divs[0].ex_date.year == 2015
    assert all(by_year.get(y) == 4 for y in range(2015, 2026)), by_year
    assert by_year.get(2026, 0) >= 2, by_year


# ----------------------------------------------------------------------------- Gotrade costs


def test_gotrade_benchmark_pays_the_schedule_on_the_first_buy():
    # 9 shares at the open 100: $900 + trading 1.80 + regulatory 0.11 (cap) + PPN
    # q½↓(1.91 × 0.11 = 0.2101) 0.21 = 902.12; 10 shares would need 1002.34.
    c = buy_and_hold(spy_bars(), START, END, CASH, name="spy_price", cost_model="gotrade")
    assert (c.shares, c.cash) == (9, P("97.88"))
    assert equities(c) == [P(x) for x in ("1000", "1006.88", "1015.88", "979.88", "988.88", "1002.38")]


def test_gotrade_benchmark_pays_the_schedule_on_each_reinvestment():
    # 03-04: cash 97.88 + q(9 × 2.5) = 120.38; 1 share at the close 98 costs
    # 98 + 0.20 + 0.06 + q½↓(0.26 × 0.11 = 0.0286) 0.03 = 98.29 -> cash 22.09, 10 shares.
    _, tr = spy_curves(spy_bars(), START, END, CASH, [div("2026-03-04", "2.5")], cost_model="gotrade")
    assert (tr.shares, tr.cash, tr.dividends_usd) == (10, P("22.09"), P("22.5"))
    assert equities(tr) == [P(x) for x in ("1000", "1006.88", "1015.88", "1002.09", "1012.09", "1027.09")]


def test_gotrade_fractional_benchmark_spends_to_the_cent():
    # fees on the whole $1000 are 2.00 + 0.11 + 0.23 = 2.34, so 9.9766 shares (997.66) fit exactly.
    c = buy_and_hold(spy_bars(), START, END, CASH, name="x", fractional=True, cost_model="gotrade")
    assert (c.shares, c.cash) == (Decimal("9.9766"), P("0"))


def test_cost_model_default_is_flat_and_unknown_is_refused():
    assert buy_and_hold(spy_bars(), START, END, CASH, name="x") == buy_and_hold(
        spy_bars(), START, END, CASH, name="x", cost_model="flat"
    )
    with pytest.raises(ValueError, match="cost_model"):
        buy_and_hold(spy_bars(), START, END, CASH, name="x", cost_model="ibkr")  # type: ignore[arg-type]

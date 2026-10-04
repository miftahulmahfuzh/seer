from datetime import date
from decimal import Decimal

import pytest
from psycopg.rows import tuple_row

from seer_engine import db, dividends
from seer_engine.dividends import Dividend, adjust_for_splits, parse_massive, quantize_amount, totals
from seer_engine.splits import Split

EX = date(2026, 9, 18)


def row(ticker="SPY", amount=1.888834, kind="CD", currency="USD", ex="2026-09-18"):
    return {"ticker": ticker, "cash_amount": amount, "currency": currency, "dividend_type": kind, "ex_dividend_date": ex}


# ---- parsing (pure) ----

def test_parse_regular_and_special_cash():
    assert parse_massive(row()) == Dividend("SPY", EX, Decimal("1.888834"))
    assert parse_massive(row("AAPL", 0.5, kind="SC")) == Dividend("AAPL", EX, Decimal("0.5"))


@pytest.mark.parametrize(
    "raw",
    [
        row(kind="LT"),
        row(kind="ST"),
        row(kind=None),
        row(currency="CAD"),
        {"ticker": "SPY", "cash_amount": 1.0, "dividend_type": "CD", "ex_dividend_date": "2026-09-18"},
    ],
)
def test_parse_drops_non_cash_and_non_usd(raw):
    assert parse_massive(raw) is None


@pytest.mark.parametrize(
    ("raw", "error"),
    [
        ({"cash_amount": 1, "currency": "USD", "dividend_type": "CD", "ex_dividend_date": "2026-09-18"}, KeyError),
        (row(ticker=""), ValueError),
        (row(ticker=7), ValueError),
        (row(amount=0), ValueError),
        (row(amount=-0.1), ValueError),
        (row(amount="abc"), ValueError),
        (row(amount=True), TypeError),
        (row(ex="18/09/2026"), ValueError),
        (row(ex=None), ValueError),
        ({"ticker": "SPY", "currency": "USD", "dividend_type": "CD", "ex_dividend_date": "2026-09-18"}, KeyError),
    ],
)
def test_parse_malformed_rows_raise(raw, error):
    with pytest.raises(error):
        parse_massive(raw)


def test_quantize_amount_is_half_up_6dp():
    assert quantize_amount(Decimal("0.1234565")) == Decimal("0.123457")
    assert quantize_amount(Decimal("0.1234564999")) == Decimal("0.123456")
    assert quantize_amount(Decimal("2")) == Decimal("2.000000")


# ---- sums (pure) ----

def test_totals_sum_per_symbol_and_ex_date_sorted():
    out = totals(
        [
            Dividend("SPY", EX, Decimal("1.888834")),
            Dividend("AAPL", EX, Decimal("0.26")),
            Dividend("AAPL", EX, Decimal("0.0100005")),  # SC on the same ex-date: summed, then rounded
            Dividend("AAPL", date(2026, 9, 19), Decimal("0.1")),
        ]
    )
    assert out == [
        Dividend("AAPL", EX, Decimal("0.270001")),
        Dividend("AAPL", date(2026, 9, 19), Decimal("0.100000")),
        Dividend("SPY", EX, Decimal("1.888834")),
    ]


def test_totals_drop_amounts_that_round_to_zero():
    assert totals([Dividend("TINY", EX, Decimal("0.0000004"))]) == []
    assert totals([]) == []


# ---- split adjustment of fetched rows (pure) ----

NVDA_DIV = Dividend("NVDA", EX, Decimal("1.000000"))


def test_split_after_ex_date_scales_the_amount():
    out = adjust_for_splits([NVDA_DIV], [Split("NVDA", date(2026, 9, 21), Decimal(1), Decimal(10))])
    assert out == [Dividend("NVDA", EX, Decimal("0.100000"))]


def test_split_on_or_before_ex_date_and_other_symbols_leave_it():
    items = [NVDA_DIV, Dividend("AAPL", EX, Decimal("0.26"))]
    out = adjust_for_splits(
        items,
        [
            Split("NVDA", EX, Decimal(1), Decimal(10)),  # same day: the dividend is already post-split
            Split("NVDA", date(2026, 9, 17), Decimal(1), Decimal(4)),
            Split("MSFT", date(2026, 9, 21), Decimal(1), Decimal(2)),
        ],
    )
    assert out == items
    assert out[0] is NVDA_DIV


def test_chained_and_reverse_splits_round_each_step_like_sql():
    out = adjust_for_splits(
        [Dividend("ABC", EX, Decimal("1.000001"))],
        [
            Split("ABC", date(2026, 9, 22), Decimal(2), Decimal(3)),  # 3-for-2, applied second
            Split("ABC", date(2026, 9, 21), Decimal(5), Decimal(1)),  # reverse 1-for-5, applied first -> 5.000005
        ],
    )
    # in date order: 5.000005 -> 5.000005 * 2 / 3 = 3.33333666.. -> 3.333337
    assert out == [Dividend("ABC", EX, Decimal("3.333337"))]


def test_duplicate_split_rows_count_once():
    s = Split("NVDA", date(2026, 9, 21), Decimal(1), Decimal(10))
    assert adjust_for_splits([NVDA_DIV], [s, s]) == [Dividend("NVDA", EX, Decimal("0.100000"))]


def test_adjusted_amount_rounding_to_zero_is_dropped():
    tiny = Dividend("TINY", EX, Decimal("0.000001"))
    assert adjust_for_splits([tiny], [Split("TINY", date(2026, 9, 21), Decimal(1), Decimal(10))]) == []


# ---- writes (needs PG_TEST_URL) ----

def stored(conn):
    with conn.cursor(row_factory=tuple_row) as cur:
        cur.execute("SELECT symbol, ex_date, amount FROM dividends ORDER BY symbol, ex_date")
        rows = cur.fetchall()
    conn.rollback()
    return rows


def upsert(conn, items):
    with db.transaction(conn, False):
        return dividends.upsert_dividends(conn, items)


def test_upsert_inserts_then_is_idempotent_then_updates_changed(pg):
    items = [Dividend("SPY", EX, Decimal("1.888834")), Dividend("AAPL", EX, Decimal("0.26"))]
    assert upsert(pg, items) == 2
    assert stored(pg) == [("AAPL", EX, Decimal("0.260000")), ("SPY", EX, Decimal("1.888834"))]
    assert upsert(pg, items) == 0
    assert upsert(pg, [Dividend("AAPL", EX, Decimal("0.27")), Dividend("SPY", EX, Decimal("1.888834"))]) == 1
    assert stored(pg) == [("AAPL", EX, Decimal("0.270000")), ("SPY", EX, Decimal("1.888834"))]


def test_upsert_empty_batch_writes_nothing(pg):
    assert upsert(pg, []) == 0
    assert stored(pg) == []


def test_upsert_rejects_duplicates_and_non_positive_amounts(pg):
    with pytest.raises(ValueError, match="duplicate"):
        upsert(pg, [Dividend("SPY", EX, Decimal("1")), Dividend("SPY", EX, Decimal("2"))])
    with pytest.raises(ValueError, match="positive"):
        upsert(pg, [Dividend("SPY", EX, Decimal("0.0000001"))])
    assert stored(pg) == []

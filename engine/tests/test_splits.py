from datetime import date
from decimal import Decimal

import pytest
from psycopg.rows import tuple_row

from seer_engine import bars, db, splits
from seer_engine.splits import Split, should_apply


# ---- heuristic (pure) ----

def test_forward_split_unadjusted_history_applies():
    assert should_apply(Decimal("1200.00"), Decimal("121.00"), Decimal(10)) is True


def test_reverse_split_unadjusted_history_applies():
    assert should_apply(Decimal("0.50"), Decimal("16.20"), Decimal(1) / Decimal(32)) is True


def test_forward_split_already_adjusted_history_not_applied():
    assert should_apply(Decimal("120.00"), Decimal("121.00"), Decimal(10)) is False


def test_reverse_split_already_adjusted_history_not_applied():
    assert should_apply(Decimal("16.00"), Decimal("16.20"), Decimal(1) / Decimal(32)) is False


def test_large_overnight_gap_still_resolves_to_nearest_explanation():
    # 2:1 split plus a -20% gap: unadjusted 100 -> 40 open. ln(100/80)=0.22 < ln(100/40)=0.92
    assert should_apply(100, 40, 2) is True


def test_tiny_factor_is_ambiguous_and_applies_by_construction():
    # 21:20 stock dividend: a 5% factor is inside normal overnight noise -> always apply
    assert should_apply(Decimal("100"), Decimal("95.3"), Decimal(21) / Decimal(20)) is True
    assert should_apply(Decimal("100"), Decimal("104.0"), Decimal(21) / Decimal(20)) is True


def test_factor_one_never_applies():
    assert should_apply(100, 100, 1) is False


@pytest.mark.parametrize("args", [(0, 1, 2), (1, 0, 2), (1, 1, 0), (-1, 1, 2)])
def test_non_positive_inputs_raise(args):
    with pytest.raises(ValueError):
        should_apply(*args)


def test_split_from_massive():
    s = Split.from_massive({"ticker": "NVDA", "execution_date": "2024-06-10", "split_from": 1, "split_to": 10}, date(2000, 1, 1))
    assert s == Split("NVDA", date(2024, 6, 10), Decimal("1"), Decimal("10"))
    assert s.factor == Decimal(10)
    with pytest.raises(ValueError):
        Split.from_massive({"ticker": "X", "split_from": 0, "split_to": 1}, date(2024, 1, 2))
    with pytest.raises(KeyError):
        Split.from_massive({"split_from": 1, "split_to": 2}, date(2024, 1, 2))


# ---- DB application (needs PG_TEST_URL) ----

D0 = date(2026, 9, 30)
D1 = date(2026, 10, 1)
D2 = date(2026, 10, 2)


def seed(conn, rows):
    with db.transaction(conn, False):
        bars.upsert_bars(conn, [bars.make_bar(*r) for r in rows])


def bar(conn, symbol, d):
    with conn.cursor(row_factory=tuple_row) as cur:
        cur.execute("SELECT open, high, low, close, volume FROM bars WHERE symbol=%s AND date=%s", (symbol, d))
        row = cur.fetchone()
    conn.rollback()
    return row


def recorded(conn):
    with conn.cursor(row_factory=tuple_row) as cur:
        cur.execute("SELECT symbol, execution_date, split_from, split_to, applied FROM split_adjustments ORDER BY 1, 2")
        rows = cur.fetchall()
    conn.rollback()
    return rows


def apply(conn, items, first_opens):
    with db.transaction(conn, False):
        return splits.apply_splits(conn, items, first_opens)


NVDA_SPLIT = Split("NVDA", D2, Decimal(1), Decimal(10))


def test_split_applies_once_across_two_calls(pg):
    seed(pg, [("NVDA", D0, 1190, 1210, 1180, 1200, 1_000_000), ("NVDA", D1, 1200, 1220, 1190, 1210, 2_000_000)])
    first = apply(pg, [NVDA_SPLIT], {"NVDA": Decimal("121")})
    assert [(o.recorded, o.applied, o.rows) for o in first] == [(True, True, 2)]
    assert bar(pg, "NVDA", D1) == (Decimal("120.0000"), Decimal("122.0000"), Decimal("119.0000"), Decimal("121.0000"), 20_000_000)
    second = apply(pg, [NVDA_SPLIT], {"NVDA": Decimal("121")})
    assert [(o.recorded, o.applied, o.reason) for o in second] == [(False, False, "already recorded")]
    assert bar(pg, "NVDA", D1)[3] == Decimal("121.0000")
    assert recorded(pg) == [("NVDA", D2, Decimal(1), Decimal(10), True)]


def test_already_adjusted_history_recorded_not_applied(pg):
    seed(pg, [("NVDA", D1, 120, 122, 119, 121, 20_000_000)])
    out = apply(pg, [NVDA_SPLIT], {"NVDA": Decimal("121.5")})
    assert [(o.recorded, o.applied) for o in out] == [(True, False)]
    assert bar(pg, "NVDA", D1)[3] == Decimal("121.0000")
    assert recorded(pg)[0][4] is False


def test_stored_bar_on_execution_date_means_already_adjusted(pg):
    # e.g. a backfill fetched after the split: unadjusted-looking numbers are not trusted over dates
    seed(pg, [("NVDA", D1, 1200, 1200, 1200, 1200, 1), ("NVDA", D2, 121, 121, 121, 121, 1)])
    out = apply(pg, [NVDA_SPLIT], {"NVDA": Decimal("121")})
    assert out[0].applied is False
    assert bar(pg, "NVDA", D1)[3] == Decimal("1200.0000")


def test_symbol_without_bars_recorded_not_applied(pg):
    out = apply(pg, [Split("NEW", D2, Decimal(1), Decimal(2))], {"NEW": Decimal("50")})
    assert [(o.recorded, o.applied, o.reason) for o in out] == [(True, False, "no stored bars")]
    assert recorded(pg) == [("NEW", D2, Decimal(1), Decimal(2), False)]


def test_reverse_split_and_rounding(pg):
    seed(pg, [("XYZ", D1, Decimal("0.5"), Decimal("0.51"), Decimal("0.49"), Decimal("0.5"), 3_200_001)])
    out = apply(pg, [Split("XYZ", D2, Decimal(32), Decimal(1))], {"XYZ": Decimal("16.2")})
    assert out[0].applied is True
    o, h, l, c, v = bar(pg, "XYZ", D1)
    assert (o, h, l, c) == (Decimal("16.0000"), Decimal("16.3200"), Decimal("15.6800"), Decimal("16.0000"))
    assert v == 100_000  # 3_200_001 / 32 = 100000.03 -> 100000


def test_three_for_two_rounds_to_4dp(pg):
    seed(pg, [("ABC", D1, 100, 100, 100, 100, 1001)])
    apply(pg, [Split("ABC", D2, Decimal(2), Decimal(3))], {"ABC": Decimal("66.5")})
    o, _, _, c, v = bar(pg, "ABC", D1)
    assert (o, c) == (Decimal("66.6667"), Decimal("66.6667"))
    assert v == 1502  # 1501.5 rounds half away from zero


def test_chained_splits_in_one_batch_each_apply(pg):
    seed(pg, [("CH", D0, 100, 100, 100, 100, 1000)])
    s1 = Split("CH", D1, Decimal(1), Decimal(2))
    s2 = Split("CH", D2, Decimal(1), Decimal(2))
    out = apply(pg, [s2, s1], {"CH": Decimal("25")})  # fetched open already reflects both
    assert [(o.split.execution_date, o.applied) for o in out] == [(D1, True), (D2, True)]
    o, _, _, c, v = bar(pg, "CH", D0)
    assert c == Decimal("25.0000")
    assert v == 4000


def test_symbols_with_bars(pg):
    seed(pg, [("AAA", D1, 1, 1, 1, 1, 1)])
    assert splits.symbols_with_bars(pg, ["AAA", "BBB"]) == {"AAA"}
    assert splits.symbols_with_bars(pg, []) == set()
    pg.rollback()

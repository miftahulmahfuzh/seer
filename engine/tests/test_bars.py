"""Bar construction and idempotent upserts into ``bars``."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from seer_engine.bars import Bar, delete_bars_on, latest_bar_date, make_bar, upsert_bars

D1 = date(2026, 10, 1)
D2 = date(2026, 10, 2)


def _bars() -> list[Bar]:
    return [
        make_bar("SPY", D1, 764.36, 765.65, 758.7901, 763.99, 47708058.813089),
        make_bar("BRK.B", D1, "480.1", "482", "478.25", "481.5", 3_000_000),
        make_bar("SPY", D2, 764.0, 766.0, 760.0, 765.12345, 40_000_000),
    ]


def _xmins(conn) -> dict[tuple[str, date], str]:
    rows = conn.execute("SELECT symbol, date, xmin::text FROM bars").fetchall()
    return {(r[0], r[1]): r[2] for r in rows}


def test_make_bar_rounds_to_4dp_and_int_volume():
    b = make_bar("SPY", D1, 764.36, 765.65, 758.79005, 0.1, 47708058.813089)
    assert b.open == Decimal("764.3600")
    assert b.low == Decimal("758.7901")  # half-up
    assert b.close == Decimal("0.1000")  # float via shortest repr, not binary expansion
    assert b.volume == 47708059 and isinstance(b.volume, int)


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_make_bar_rejects_non_finite(bad):
    with pytest.raises(ValueError):
        make_bar("SPY", D1, bad, 1, 1, 1, 1)


def test_make_bar_rejects_negative_volume_and_datetime():
    from datetime import datetime

    with pytest.raises(ValueError):
        make_bar("SPY", D1, 1, 1, 1, 1, -1)
    with pytest.raises(TypeError):
        make_bar("SPY", datetime(2026, 10, 1), 1, 1, 1, 1, 1)


def test_bar_is_frozen():
    b = _bars()[0]
    with pytest.raises(AttributeError):
        b.close = Decimal("1")  # type: ignore[misc]


def test_upsert_inserts_then_identical_rerun_changes_nothing(pg):
    assert upsert_bars(pg, _bars()) == 3
    pg.commit()
    before = _xmins(pg)
    assert upsert_bars(pg, _bars()) == 0
    pg.commit()
    assert _xmins(pg) == before  # no new row versions either


def test_upsert_counts_only_changed_rows(pg):
    upsert_bars(pg, _bars())
    changed = _bars()
    changed[0] = make_bar("SPY", D1, 764.36, 765.65, 758.7901, 770.0, 47708058.813089)
    assert upsert_bars(pg, changed) == 1
    close = pg.execute("SELECT close FROM bars WHERE symbol='SPY' AND date=%s", (D1,)).fetchone()[0]
    assert close == Decimal("770.0000")


def test_upsert_volume_change_counts(pg):
    upsert_bars(pg, _bars())
    b = _bars()[1]
    assert upsert_bars(pg, [make_bar(b.symbol, b.date, b.open, b.high, b.low, b.close, 1)]) == 1


def test_upsert_twice_in_one_transaction(pg):
    assert upsert_bars(pg, _bars()[:1]) == 1
    assert upsert_bars(pg, _bars()[1:]) == 2
    assert pg.execute("SELECT count(*) FROM bars").fetchone()[0] == 3


def test_upsert_rejects_duplicate_keys_in_batch(pg):
    b = _bars()[0]
    with pytest.raises(ValueError, match="duplicate"):
        upsert_bars(pg, [b, b])


def test_upsert_empty_is_zero(pg):
    assert upsert_bars(pg, []) == 0


def test_latest_bar_date_and_delete(pg):
    assert latest_bar_date(pg, "SPY") is None
    upsert_bars(pg, _bars())
    assert latest_bar_date(pg, "SPY") == D2
    assert latest_bar_date(pg, "BRK.B") == D1
    assert delete_bars_on(pg, D1) == 2
    assert latest_bar_date(pg, "BRK.B") is None
    assert delete_bars_on(pg, D1) == 0

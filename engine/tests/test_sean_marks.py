"""Sean's closes: Yahoo per symbol, failures skipped, idempotent upsert."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pandas as pd

from seer_engine.sean import marks


def test_yahoo_closes_maps_the_symbol_and_drops_bars_after_the_end():
    calls = []

    def downloader(tickers, start, end_exclusive):
        calls.append((tickers, start, end_exclusive))
        idx = pd.DatetimeIndex(["2026-06-16", "2026-06-17", "2026-06-18"])
        return pd.DataFrame(
            {"Open": [1.0, 1.0, 1.0], "High": [2.0, 2.0, 2.0], "Low": [0.5, 0.5, 0.5],
             "Close": [1.5, 1.25, 1.75], "Volume": [10, 10, 10]},
            index=idx,
        )

    got = marks.yahoo_closes("BRK.B", date(2026, 6, 16), date(2026, 6, 17), downloader=downloader)
    assert calls == [(["BRK-B"], date(2026, 6, 16), date(2026, 6, 18))]
    assert got == [(date(2026, 6, 16), Decimal("1.5000")), (date(2026, 6, 17), Decimal("1.2500"))]


def test_a_failing_or_empty_symbol_is_skipped_not_fatal():
    def fetch(symbol, start, end):
        if symbol == "GONE":
            raise RuntimeError("delisted")
        if symbol == "EMPTY":
            return []
        return [(date(2026, 6, 15), Decimal("9")), (date(2026, 6, 16), Decimal("10")),
                (date(2026, 6, 23), Decimal("99"))]

    got = marks.fetch_closes(
        [("EMPTY", date(2026, 6, 16)), ("GONE", date(2026, 6, 16)), ("MU", date(2026, 6, 16))],
        date(2026, 6, 22),
        fetch,
    )
    assert got.closes == {"MU": [(date(2026, 6, 16), Decimal("10"))]}
    assert got.missing == ("EMPTY", "GONE")
    assert got.rows() == [("MU", date(2026, 6, 16), Decimal("10"))]


def test_a_symbol_first_traded_after_the_end_is_not_fetched():
    def fetch(symbol, start, end):
        raise AssertionError("must not fetch")

    got = marks.fetch_closes([("MU", date(2026, 6, 23))], date(2026, 6, 22), fetch)
    assert got.closes == {} and got.missing == ()


def test_upsert_is_idempotent_and_updates_changed_closes(pg):
    rows = [("MU", date(2026, 6, 16), Decimal("121")), ("MU", date(2026, 6, 17), Decimal("125"))]
    assert marks.upsert_marks(pg, rows) == 2
    assert marks.upsert_marks(pg, rows) == 0
    assert marks.upsert_marks(pg, [("MU", date(2026, 6, 17), Decimal("126"))]) == 1
    assert marks.upsert_marks(pg, []) == 0
    pg.commit()
    assert marks.read_marks(pg) == {
        "MU": [(date(2026, 6, 16), Decimal("121.0000")), (date(2026, 6, 17), Decimal("126.0000"))]
    }

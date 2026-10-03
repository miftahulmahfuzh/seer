"""Frankfurter parsing (fake HTTP) and idempotent ``fx_rates`` upserts."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from seer_engine import fx


@pytest.fixture
def fake_get_json(monkeypatch):
    calls: list[tuple[str, dict | None]] = []
    responses: dict[str, dict] = {}

    def get_json(url, params=None, **_kw):
        calls.append((url, params))
        return responses[url]

    monkeypatch.setattr(fx.http, "get_json", get_json)
    return calls, responses


def test_fetch_latest(fake_get_json):
    calls, responses = fake_get_json
    responses[f"{fx.FRANKFURTER}/latest"] = {
        "amount": 1.0,
        "base": "USD",
        "date": "2026-10-02",
        "rates": {"IDR": 17950.0},
    }
    assert fx.fetch_latest() == (date(2026, 10, 2), Decimal("17950.0000"))
    assert calls == [(f"{fx.FRANKFURTER}/latest", {"base": "USD", "symbols": "IDR"})]


def test_fetch_latest_without_idr_raises(fake_get_json):
    _, responses = fake_get_json
    responses[f"{fx.FRANKFURTER}/latest"] = {"date": "2026-10-02", "rates": {}}
    with pytest.raises(ValueError):
        fx.fetch_latest()


def test_fetch_range_chunks_per_calendar_year(fake_get_json):
    calls, responses = fake_get_json
    responses[f"{fx.FRANKFURTER}/2024-12-30..2024-12-31"] = {
        "rates": {
            "2024-12-27": {"IDR": 16200.5},  # outside the chunk: ignored
            "2024-12-30": {"IDR": 16100.12345},
            "2024-12-31": {"IDR": 16150},
        }
    }
    responses[f"{fx.FRANKFURTER}/2025-01-01..2025-12-31"] = {
        "rates": {"2025-01-02": {"IDR": 16200}}
    }
    responses[f"{fx.FRANKFURTER}/2026-01-01..2026-01-05"] = {
        "rates": {"2026-01-05": {"IDR": 16700}}
    }
    out = fx.fetch_range(date(2024, 12, 30), date(2026, 1, 5))
    assert [u for u, _ in calls] == [
        f"{fx.FRANKFURTER}/2024-12-30..2024-12-31",
        f"{fx.FRANKFURTER}/2025-01-01..2025-12-31",
        f"{fx.FRANKFURTER}/2026-01-01..2026-01-05",
    ]
    assert out == [
        (date(2024, 12, 30), Decimal("16100.1235")),
        (date(2024, 12, 31), Decimal("16150.0000")),
        (date(2025, 1, 2), Decimal("16200.0000")),
        (date(2026, 1, 5), Decimal("16700.0000")),
    ]


def test_fetch_range_empty_when_reversed(fake_get_json):
    calls, _ = fake_get_json
    assert fx.fetch_range(date(2026, 1, 2), date(2026, 1, 1)) == []
    assert calls == []


def test_upsert_fx_idempotent(pg):
    rows = [(date(2026, 10, 1), Decimal("17900")), (date(2026, 10, 2), 17950.0)]
    assert fx.upsert_fx(pg, rows) == 2
    pg.commit()
    assert fx.upsert_fx(pg, rows) == 0
    assert fx.upsert_fx(pg, [(date(2026, 10, 2), "17950.00001")]) == 0  # rounds to the same
    assert fx.upsert_fx(pg, [(date(2026, 10, 2), "17960")]) == 1
    rate = pg.execute("SELECT usd_idr FROM fx_rates WHERE date='2026-10-02'").fetchone()[0]
    assert rate == Decimal("17960.0000")


def test_upsert_fx_rejects_conflicting_duplicates(pg):
    with pytest.raises(ValueError):
        fx.upsert_fx(pg, [(date(2026, 10, 2), 1), (date(2026, 10, 2), 2)])


def test_upsert_fx_empty(pg):
    assert fx.upsert_fx(pg, []) == 0

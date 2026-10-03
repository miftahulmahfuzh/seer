"""USD/IDR from Frankfurter (ECB reference rates; no API key) and writes to ``fx_rates``."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from decimal import Decimal

import psycopg

from seer_engine import http
from seer_engine.bars import to_decimal

FRANKFURTER = "https://api.frankfurter.dev/v1"
PARAMS = {"base": "USD", "symbols": "IDR"}


def _idr(rates: dict, where: str) -> Decimal:
    try:
        return to_decimal(rates["IDR"])
    except (KeyError, TypeError) as exc:
        raise ValueError(f"Frankfurter response has no IDR rate ({where})") from exc


def fetch_latest() -> tuple[date, Decimal]:
    """The newest published USD/IDR rate and the date Frankfurter says it is for."""
    data = http.get_json(f"{FRANKFURTER}/latest", params=PARAMS)
    return date.fromisoformat(data["date"]), _idr(data.get("rates") or {}, "latest")


def fetch_range(start: date, end: date) -> list[tuple[date, Decimal]]:
    """Every published USD/IDR rate from ``start`` to ``end`` inclusive, ascending.

    One request per calendar year keeps each response small.
    """
    if end < start:
        return []
    out: dict[date, Decimal] = {}
    for year in range(start.year, end.year + 1):
        a = max(start, date(year, 1, 1))
        b = min(end, date(year, 12, 31))
        data = http.get_json(f"{FRANKFURTER}/{a.isoformat()}..{b.isoformat()}", params=PARAMS)
        for key, rates in (data.get("rates") or {}).items():
            d = date.fromisoformat(key)
            if a <= d <= b:
                out[d] = _idr(rates, key)
    return sorted(out.items())


def upsert_fx(conn: psycopg.Connection, rows: Iterable[tuple[date, Decimal | float | str]]) -> int:
    """Insert new rates and update changed ones (rounded to 4 decimals); return how many
    rows were inserted or changed. An identical re-run returns 0. Does not commit."""
    items: dict[date, Decimal] = {}
    for d, rate in rows:
        value = to_decimal(rate)
        if d in items and items[d] != value:
            raise ValueError(f"conflicting rates for {d.isoformat()} in one batch")
        items[d] = value
    if not items:
        return 0
    with conn.cursor() as cur:
        cur.execute(
            "CREATE TEMP TABLE IF NOT EXISTS _seer_fx_in "
            "(LIKE fx_rates INCLUDING DEFAULTS) ON COMMIT DELETE ROWS"
        )
        cur.execute("TRUNCATE _seer_fx_in")
        with cur.copy("COPY _seer_fx_in (date, usd_idr) FROM STDIN") as copy:
            for d, value in sorted(items.items()):
                copy.write_row((d, value))
        cur.execute(
            """
            INSERT INTO fx_rates AS f (date, usd_idr)
            SELECT date, usd_idr FROM _seer_fx_in
            ON CONFLICT (date) DO UPDATE
            SET usd_idr = EXCLUDED.usd_idr
            WHERE f.usd_idr IS DISTINCT FROM EXCLUDED.usd_idr
            """
        )
        changed = cur.rowcount
        cur.execute("TRUNCATE _seer_fx_in")
    return changed

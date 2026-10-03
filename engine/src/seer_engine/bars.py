"""Daily bars: the value type and idempotent writes to ``bars``.

Prices are split-adjusted only (no dividend adjustment), stored as numeric(12,4);
volume is an integer. Symbols are in canonical dot form ('BRK.B').
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

import psycopg

# Re-exported: these moved to the pure seer_engine.prices so the sim core can use them
# without importing psycopg. Every `from seer_engine.bars import Bar, ...` keeps working.
from seer_engine.prices import PRICE_QUANTUM, Bar, to_decimal  # noqa: F401


def to_volume(v: Decimal | float | int | str) -> int:
    """``v`` rounded half-up to a non-negative int (Massive reports volume as a float)."""
    if isinstance(v, bool):
        raise TypeError("bool is not a volume")
    if isinstance(v, int):
        n = v
    else:
        if isinstance(v, float) and not math.isfinite(v):
            raise ValueError(f"non-finite volume: {v!r}")
        n = int(Decimal(repr(v) if isinstance(v, float) else v).to_integral_value(ROUND_HALF_UP))
    if n < 0:
        raise ValueError(f"negative volume: {v!r}")
    return n


def make_bar(
    symbol: str,
    d: date,
    o: Decimal | float | int | str,
    h: Decimal | float | int | str,
    l: Decimal | float | int | str,  # noqa: E741
    c: Decimal | float | int | str,
    v: Decimal | float | int | str,
) -> Bar:
    """A Bar with prices rounded to 4 decimals and an int volume."""
    if not symbol:
        raise ValueError("empty symbol")
    if isinstance(d, datetime) or not isinstance(d, date):
        raise TypeError(f"expected a date, got {d!r}")
    return Bar(symbol, d, to_decimal(o), to_decimal(h), to_decimal(l), to_decimal(c), to_volume(v))


def upsert_bars(conn: psycopg.Connection, bars: Iterable[Bar]) -> int:
    """Insert new bars and update changed ones; return how many rows were inserted or changed.

    Bars identical to the stored row are skipped by the ``IS DISTINCT FROM`` guard, so they
    are not counted and create no new row versions: an identical re-run returns 0.
    Raises ValueError when the batch holds the same (symbol, date) twice. Does not commit.
    """
    rows = list(bars)
    if not rows:
        return 0
    seen: set[tuple[str, date]] = set()
    for b in rows:
        key = (b.symbol, b.date)
        if key in seen:
            raise ValueError(f"duplicate bar in batch: {b.symbol} {b.date.isoformat()}")
        seen.add(key)
    with conn.cursor() as cur:
        cur.execute(
            "CREATE TEMP TABLE IF NOT EXISTS _seer_bars_in "
            "(LIKE bars INCLUDING DEFAULTS) ON COMMIT DELETE ROWS"
        )
        cur.execute("TRUNCATE _seer_bars_in")
        with cur.copy(
            "COPY _seer_bars_in (symbol, date, open, high, low, close, volume) FROM STDIN"
        ) as copy:
            for b in rows:
                copy.write_row((b.symbol, b.date, b.open, b.high, b.low, b.close, b.volume))
        cur.execute(
            """
            INSERT INTO bars AS b (symbol, date, open, high, low, close, volume)
            SELECT symbol, date, open, high, low, close, volume FROM _seer_bars_in
            ON CONFLICT (symbol, date) DO UPDATE
            SET open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                volume = EXCLUDED.volume
            WHERE (b.open, b.high, b.low, b.close, b.volume)
                  IS DISTINCT FROM
                  (EXCLUDED.open, EXCLUDED.high, EXCLUDED.low, EXCLUDED.close, EXCLUDED.volume)
            """
        )
        changed = cur.rowcount
        cur.execute("TRUNCATE _seer_bars_in")
    return changed


def latest_bar_date(conn: psycopg.Connection, symbol: str) -> date | None:
    """The newest stored bar date for ``symbol``, or None when it has no bars."""
    row = conn.execute("SELECT max(date) FROM bars WHERE symbol = %s", (symbol,)).fetchone()
    return row[0]


def delete_bars_on(conn: psycopg.Connection, d: date) -> int:
    """Delete every bar dated ``d``; return the number deleted. Does not commit."""
    with conn.cursor() as cur:
        cur.execute("DELETE FROM bars WHERE date = %s", (d,))
        return cur.rowcount

"""Daily closes for every symbol the owner has held, stored in ``sean_marks``.

Owner symbols are not limited to the universe (FUTU) and may be delisted, so ``bars`` is not
used: each symbol is fetched from Yahoo on its own, from its first trade date to the last
completed session. A symbol that fails or comes back empty is logged and skipped; it never
aborts the run. Its earlier stored closes still stand, and with none the ledger values it at
its last order price (contract B).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

import psycopg

from seer_engine import yahoo

log = logging.getLogger(__name__)

# (symbol, first date, last date inclusive) -> [(date, close), ...]
CloseFetch = Callable[[str, date, date], list[tuple[date, Decimal]]]


def yahoo_closes(
    symbol: str, start: date, end: date, *, downloader: yahoo.Downloader | None = None
) -> list[tuple[date, Decimal]]:
    """Daily closes for one canonical symbol in ``[start, end]`` (split-adjusted, 4 decimals)."""
    got = yahoo.download([symbol], start, end + timedelta(days=1), downloader=downloader)
    bars = got.get(symbol.strip().upper(), [])
    return [(b.date, b.close) for b in bars if start <= b.date <= end]


@dataclass(frozen=True)
class Fetched:
    """Closes fetched this run, and the symbols that got none."""

    closes: dict[str, list[tuple[date, Decimal]]]
    missing: tuple[str, ...]

    def rows(self) -> list[tuple[str, date, Decimal]]:
        return [(s, d, c) for s, series in sorted(self.closes.items()) for d, c in series]


def fetch_closes(
    starts: Iterable[tuple[str, date]], end: date, fetch: CloseFetch = yahoo_closes
) -> Fetched:
    """Fetch ``[start, end]`` closes for each ``(symbol, start)``. Never raises for a symbol."""
    closes: dict[str, list[tuple[date, Decimal]]] = {}
    missing: list[str] = []
    for symbol, start in starts:
        if start > end:
            continue
        try:
            got = fetch(symbol, start, end)
        except Exception as exc:  # one symbol must never abort the run (contract B)
            log.warning("sean marks: no prices for %s (%s); its stored closes or last order price stand", symbol, exc)
            missing.append(symbol)
            continue
        by_date = {d: c for d, c in got if start <= d <= end}
        if not by_date:
            log.warning("sean marks: no prices for %s; its stored closes or last order price stand", symbol)
            missing.append(symbol)
            continue
        closes[symbol] = [(d, by_date[d]) for d in sorted(by_date)]
    return Fetched(closes=closes, missing=tuple(missing))


def upsert_marks(conn: psycopg.Connection, rows: Iterable[tuple[str, date, Decimal]]) -> int:
    """Insert new closes and update changed ones; return how many rows were written.

    An identical re-run writes nothing and returns 0. Does not commit.
    """
    batch = list(rows)
    if not batch:
        return 0
    cur = conn.execute(
        """
        INSERT INTO sean_marks (symbol, date, close)
        SELECT * FROM unnest(%s::text[], %s::date[], %s::numeric[])
        ON CONFLICT (symbol, date) DO UPDATE SET close = EXCLUDED.close
        WHERE sean_marks.close IS DISTINCT FROM EXCLUDED.close
        """,
        ([r[0] for r in batch], [r[1] for r in batch], [r[2] for r in batch]),
    )
    return cur.rowcount


def read_marks(conn: psycopg.Connection) -> dict[str, list[tuple[date, Decimal]]]:
    """Every stored close: ``{symbol: [(date, close), ...]}``, dates ascending."""
    out: dict[str, list[tuple[date, Decimal]]] = {}
    for symbol, d, close in conn.execute("SELECT symbol, date, close FROM sean_marks ORDER BY symbol, date"):
        out.setdefault(symbol, []).append((d, close))
    return out

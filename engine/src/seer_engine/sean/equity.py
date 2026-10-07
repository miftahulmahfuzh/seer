"""Sean's daily profit/loss series: ``sean_orders`` + ``sean_marks`` -> ``sean_equity``.

The series has one row per NYSE session from the first order's trade date to the last
completed session, recomputed in full and replaced on every run (a deleted or late upload
changes history, and the whole series is a few hundred rows).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date

import psycopg

from seer_engine import dates
from seer_engine.sean import ledger
from seer_engine.sean.ledger import Closes, Order, PnlPoint

_ORDER_SQL = """
SELECT id, symbol, side, executed_at, price, shares, total_usd,
       trading_fee_usd, regulatory_fee_usd, ppn_usd
  FROM sean_orders
 ORDER BY executed_at, id
"""

_INSERT_SQL = """
INSERT INTO sean_equity (date, value_usd, cost_usd, realized_usd, unrealized_usd, pnl_usd, fees_usd)
VALUES (%s, %s, %s, %s, %s, %s, %s)
"""


def read_orders(conn: psycopg.Connection) -> list[Order]:
    """Every stored order, in ledger order."""
    return [
        Order(
            id=int(r[0]),
            symbol=r[1],
            side=r[2],
            executed_at=r[3],
            price=r[4],
            shares=r[5],
            total_usd=r[6],
            trading_fee_usd=r[7],
            regulatory_fee_usd=r[8],
            ppn_usd=r[9],
        )
        for r in conn.execute(_ORDER_SQL).fetchall()
    ]


def symbol_starts(orders: Iterable[Order]) -> list[tuple[str, date]]:
    """``(symbol, first trade date)`` for every symbol ever traded, sorted by symbol."""
    first: dict[str, date] = {}
    for o in orders:
        d = o.trade_date
        if o.symbol not in first or d < first[o.symbol]:
            first[o.symbol] = d
    return sorted(first.items())


def series(orders: Sequence[Order], end: date, closes: Closes) -> list[PnlPoint]:
    """One point per NYSE session from the first trade date through ``end``."""
    if not orders:
        return []
    first = min(o.trade_date for o in orders)
    return ledger.pnl_series(orders, dates.sessions(first, end), closes)


def lock(conn: psycopg.Connection) -> None:
    """Serialize Sean writers (the nightly step and a dispatched sean.yml may overlap).

    EXCLUSIVE blocks other writers and other ``lock`` callers but not readers, so the site
    keeps reading the previous series until this transaction commits.
    """
    conn.execute("LOCK TABLE sean_marks, sean_equity IN EXCLUSIVE MODE")


def replace_equity(conn: psycopg.Connection, points: Sequence[PnlPoint]) -> int:
    """Replace the whole series with ``points``; return how many rows were written. No commit."""
    conn.execute("DELETE FROM sean_equity")
    if points:
        with conn.cursor() as cur:
            cur.executemany(
                _INSERT_SQL,
                [
                    (p.day, p.value_usd, p.cost_usd, p.realized_usd, p.unrealized_usd, p.pnl_usd, p.fees_usd)
                    for p in points
                ],
            )
    return len(points)

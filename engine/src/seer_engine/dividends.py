"""Cash dividends by ex-date: the value type, Massive row parsing, sums, and writes to ``dividends``.

Massive's /v3/reference/dividends returns one row per declared distribution. Seer keeps the USD
cash ones (dividend_type CD = regular cash, SC = special cash) and drops capital-gain
distributions (LT, ST) and other currencies. Rows for the same symbol and ex-date are summed and
quantized half-up to 6 dp, which is what the ``dividends`` table (migration 003) stores.

Units: stored amounts are per share in the same units as ``bars``. ``splits.apply_splits`` rewrites
stored rows before a split's execution date exactly when it rewrites the bars; rows fetched in the
same nightly batch as a later split are adjusted in memory by ``adjust_for_splits`` (Massive's
cash_amount is the declared, unadjusted amount, while grouped-daily bars are adjusted as of fetch
time).
"""
from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

import psycopg

from seer_engine.splits import Split

log = logging.getLogger(__name__)

AMOUNT_QUANTUM = Decimal("0.000001")
CASH_TYPES = frozenset({"CD", "SC"})
CURRENCY = "USD"


def quantize_amount(value: Decimal) -> Decimal:
    """``value`` rounded half-up to 6 decimals (numeric(14,6), like SQL round(x, 6) for x > 0)."""
    return value.quantize(AMOUNT_QUANTUM, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Dividend:
    symbol: str
    ex_date: date
    amount: Decimal  # USD per share, > 0


def _amount(value: Any) -> Decimal:
    if isinstance(value, bool):
        raise TypeError("bool is not an amount")
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError) as e:
        raise ValueError(f"cash_amount is not a number: {value!r}") from e
    if not d.is_finite() or d <= 0:
        raise ValueError(f"cash_amount must be positive: {value!r}")
    return d


def parse_massive(raw: Mapping[str, Any]) -> Dividend | None:
    """One Massive dividends row -> Dividend, or None for a valid row Seer does not credit.

    None: dividend_type not CD/SC (LT, ST capital gains, anything new) or currency not USD
    (a missing currency counts as not USD). Raises KeyError/ValueError/TypeError when a row of a
    kept type is malformed. The amount is not quantized here; ``totals`` does that after summing.
    """
    symbol = raw["ticker"]
    if not isinstance(symbol, str) or not symbol:
        raise ValueError(f"bad ticker: {symbol!r}")
    if raw.get("dividend_type") not in CASH_TYPES:
        return None
    if raw.get("currency") != CURRENCY:
        return None
    ex = raw["ex_dividend_date"]
    if not isinstance(ex, str) or not ex:
        raise ValueError(f"bad ex_dividend_date: {ex!r}")
    return Dividend(symbol=symbol, ex_date=date.fromisoformat(ex), amount=_amount(raw["cash_amount"]))


def totals(items: Iterable[Dividend]) -> list[Dividend]:
    """One Dividend per (symbol, ex_date): the exact sum, quantized half-up to 6 dp.

    Sums that quantize to zero are dropped (the table requires amount > 0). Sorted by
    (symbol, ex_date).
    """
    sums: dict[tuple[str, date], Decimal] = defaultdict(Decimal)
    for x in items:
        sums[(x.symbol, x.ex_date)] += x.amount
    out: list[Dividend] = []
    for (symbol, ex_date) in sorted(sums):
        amount = quantize_amount(sums[(symbol, ex_date)])
        if amount <= 0:
            log.warning("dividend %s %s rounds to 0 at 6 dp; dropped", symbol, ex_date.isoformat())
            continue
        out.append(Dividend(symbol, ex_date, amount))
    return out


def adjust_for_splits(items: Iterable[Dividend], split_items: Iterable[Split]) -> list[Dividend]:
    """Put freshly fetched dividends into the units of the bars fetched with them.

    For each dividend, every split of the same symbol whose execution_date is after its ex_date
    is applied in date order as ``quantize(amount * split_from / split_to)``: exactly what
    ``splits.apply_splits`` would do to the row had it been stored before the split. Splits are
    de-duplicated per (symbol, execution_date) like ``apply_splits``. Results that round to 0 are
    dropped. Order of ``items`` is kept.
    """
    by_symbol: dict[str, dict[date, Split]] = defaultdict(dict)
    for s in split_items:
        by_symbol[s.symbol].setdefault(s.execution_date, s)
    out: list[Dividend] = []
    for x in items:
        chain = by_symbol.get(x.symbol, {})
        amount = x.amount
        for execution_date in sorted(chain):
            if x.ex_date < execution_date:
                s = chain[execution_date]
                amount = quantize_amount(amount * s.split_from / s.split_to)
        if amount <= 0:
            log.warning(
                "dividend %s %s rounds to 0 after later splits; dropped", x.symbol, x.ex_date.isoformat()
            )
            continue
        out.append(x if amount == x.amount else Dividend(x.symbol, x.ex_date, amount))
    return out


_UPSERT = """
INSERT INTO dividends AS d (symbol, ex_date, amount)
SELECT t.symbol, t.ex_date, t.amount
FROM unnest(%(symbols)s::text[], %(ex_dates)s::date[], %(amounts)s::numeric[]) AS t(symbol, ex_date, amount)
ON CONFLICT (symbol, ex_date) DO UPDATE
SET amount = EXCLUDED.amount,
    recorded_at = now()
WHERE d.amount IS DISTINCT FROM EXCLUDED.amount
"""


def upsert_dividends(conn: psycopg.Connection, items: Iterable[Dividend]) -> int:
    """Insert new dividends and update changed ones; return how many rows were inserted or changed.

    Amounts are quantized to 6 dp first. Rows identical to the stored row are skipped by the
    ``IS DISTINCT FROM`` guard, so an identical re-run returns 0. Raises ValueError when the batch
    holds the same (symbol, ex_date) twice or an amount that is not positive at 6 dp.
    Does not commit.
    """
    rows = list(items)
    if not rows:
        return 0
    seen: set[tuple[str, date]] = set()
    symbols: list[str] = []
    ex_dates: list[date] = []
    amounts: list[Decimal] = []
    for x in rows:
        key = (x.symbol, x.ex_date)
        if key in seen:
            raise ValueError(f"duplicate dividend in batch: {x.symbol} {x.ex_date.isoformat()}")
        seen.add(key)
        amount = quantize_amount(x.amount)
        if amount <= 0:
            raise ValueError(f"dividend amount must be positive: {x.symbol} {x.ex_date.isoformat()} {x.amount}")
        symbols.append(x.symbol)
        ex_dates.append(x.ex_date)
        amounts.append(amount)
    with conn.cursor() as cur:
        cur.execute(_UPSERT, {"symbols": symbols, "ex_dates": ex_dates, "amounts": amounts})
        return cur.rowcount

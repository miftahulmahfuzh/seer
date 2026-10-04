"""Stock splits: decide whether stored history still needs a split, and apply it exactly once.

A split with factor f = split_to / split_from (NVDA 2024-06-10: 1 -> 10, f = 10) means every bar
before the execution date must be rewritten: prices * 1/f, volume * f, and every stored cash
dividend with an earlier ex-date * 1/f (6 dp). `split_adjustments` holds one row per
(symbol, execution_date); a split whose row already exists is never applied again, so re-runs and
replays cannot double-adjust.
"""
from __future__ import annotations

import logging
import math
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

import psycopg
from psycopg.rows import tuple_row

log = logging.getLogger(__name__)

# Below this |ln f| (f within 0.8x..1.25x) normal overnight gaps can exceed the split itself,
# so the price heuristic is not trusted; history that predates the split is adjusted by construction.
AMBIGUOUS_LOG_FACTOR = math.log(1.25)


def _positive_decimal(value: Any, name: str) -> Decimal:
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError) as e:
        raise ValueError(f"{name} is not a number: {value!r}") from e
    if not d.is_finite() or d <= 0:
        raise ValueError(f"{name} must be positive: {value!r}")
    return d


@dataclass(frozen=True)
class Split:
    symbol: str
    execution_date: date
    split_from: Decimal
    split_to: Decimal

    @property
    def factor(self) -> Decimal:
        """Shares after / shares before: 10 for a 10-for-1, 1/32 for a 1-for-32 reverse split."""
        return self.split_to / self.split_from

    @classmethod
    def from_massive(cls, raw: Mapping[str, Any], default_date: date) -> "Split":
        """Build from a Massive /v3/reference/splits result row. Raises KeyError/ValueError if malformed."""
        symbol = raw["ticker"]
        if not isinstance(symbol, str) or not symbol:
            raise ValueError(f"bad ticker: {symbol!r}")
        ex = raw.get("execution_date")
        execution_date = date.fromisoformat(ex) if ex else default_date
        return cls(
            symbol=symbol,
            execution_date=execution_date,
            split_from=_positive_decimal(raw["split_from"], "split_from"),
            split_to=_positive_decimal(raw["split_to"], "split_to"),
        )


@dataclass(frozen=True)
class SplitOutcome:
    split: Split
    recorded: bool  # a new split_adjustments row was inserted by this call
    applied: bool  # stored history was rewritten by this call
    reason: str
    rows: int  # bars rows rewritten
    dividend_rows: int = 0  # dividends rows rewritten (ex_date before the execution date)


def should_apply(prev_close: Decimal | float, open_today: Decimal | float, factor: Decimal | float) -> bool:
    """True when stored history still looks unadjusted for a split of `factor`.

    prev_close is the latest stored close before the split; open_today is the first post-split
    (adjusted) open. If history is unadjusted, prev_close / (open_today * f) is near 1; if it is
    already adjusted, prev_close / open_today is near 1. Apply when the first is closer:
    |ln(prev/(open*f))| < |ln(prev/open)|.

    Factors within AMBIGUOUS_LOG_FACTOR of 1 always return True (callers only ask when the stored
    history predates the split); a factor of exactly 1 returns False.
    """
    p, o, f = float(prev_close), float(open_today), float(factor)
    if p <= 0 or o <= 0 or f <= 0:
        raise ValueError(f"should_apply needs positive inputs, got prev={p} open={o} factor={f}")
    log_f = math.log(f)
    if log_f == 0.0:
        return False
    if abs(log_f) < AMBIGUOUS_LOG_FACTOR:
        return True
    x = math.log(p / o)
    return abs(x - log_f) < abs(x)


def symbols_with_bars(conn: psycopg.Connection, symbols: Iterable[str]) -> set[str]:
    """The subset of `symbols` that has at least one row in bars."""
    wanted = sorted(set(symbols))
    if not wanted:
        return set()
    with conn.cursor(row_factory=tuple_row) as cur:
        cur.execute(
            "SELECT s FROM unnest(%s::text[]) AS s "
            "WHERE EXISTS (SELECT 1 FROM bars b WHERE b.symbol = s)",
            (wanted,),
        )
        return {row[0] for row in cur.fetchall()}


def _decide(cur: psycopg.Cursor, split: Split, ref_open: Decimal | None) -> tuple[bool, str]:
    factor = split.factor
    if factor == 1:
        return False, "factor is 1"
    cur.execute(
        "SELECT date, close FROM bars WHERE symbol = %s ORDER BY date DESC LIMIT 1",
        (split.symbol,),
    )
    row = cur.fetchone()
    if row is None:
        return False, "no stored bars"
    last_date, last_close = row
    if last_date >= split.execution_date:
        return False, f"stored history reaches {last_date.isoformat()}; already post-split"
    if ref_open is None or ref_open <= 0 or last_close <= 0:
        return True, "no reference open; stored history predates the split"
    if should_apply(last_close, ref_open, factor):
        return True, f"prev close {last_close} vs open {ref_open} fits factor {factor}"
    return False, f"prev close {last_close} vs open {ref_open} already consistent"


_INSERT = """
INSERT INTO split_adjustments (symbol, execution_date, split_from, split_to, applied)
VALUES (%(symbol)s, %(execution_date)s, %(split_from)s, %(split_to)s, %(applied)s)
ON CONFLICT (symbol, execution_date) DO NOTHING
RETURNING symbol
"""

_REWRITE = """
UPDATE bars SET
  open   = round(open  * %(split_from)s / %(split_to)s, 4),
  high   = round(high  * %(split_from)s / %(split_to)s, 4),
  low    = round(low   * %(split_from)s / %(split_to)s, 4),
  close  = round(close * %(split_from)s / %(split_to)s, 4),
  volume = round(volume * %(split_to)s / %(split_from)s)::bigint
WHERE symbol = %(symbol)s AND date < %(execution_date)s
"""

# Dividends are stored in the same units as bars: an applied split rewrites every earlier
# ex-date for the symbol (cash per share * split_from / split_to, 6 dp). A row that would round
# to zero is removed first (dividends.amount must stay > 0).
_DROP_TINY_DIVIDENDS = """
DELETE FROM dividends
WHERE symbol = %(symbol)s AND ex_date < %(execution_date)s
  AND round(amount * %(split_from)s / %(split_to)s, 6) = 0
"""

_REWRITE_DIVIDENDS = """
UPDATE dividends SET amount = round(amount * %(split_from)s / %(split_to)s, 6)
WHERE symbol = %(symbol)s AND ex_date < %(execution_date)s
"""


def apply_splits(
    conn: psycopg.Connection,
    items: Iterable[Split],
    first_opens: Mapping[str, Decimal],
) -> list[SplitOutcome]:
    """Record every split once and rewrite stored history for the ones that need it.

    Stored history is the symbol's bars and its cash dividends with an ex-date before the
    execution date (same units as the bars). Must run inside the caller's write transaction,
    before any bar or dividend fetched in this batch is upserted (fetched bars are adjusted as of
    fetch time and fetched dividends are adjusted by ``dividends.adjust_for_splits``; neither may
    be rewritten again). `first_opens[symbol]` is the open of the earliest fetched bar for that
    symbol in this batch.
    """
    by_symbol: dict[str, dict[date, Split]] = defaultdict(dict)
    for s in items:
        by_symbol[s.symbol].setdefault(s.execution_date, s)

    outcomes: list[SplitOutcome] = []
    with conn.cursor(row_factory=tuple_row) as cur:
        for symbol in sorted(by_symbol):
            chain = [by_symbol[symbol][d] for d in sorted(by_symbol[symbol])]
            for k, split in enumerate(chain):
                later = math.prod((s.factor for s in chain[k + 1 :]), start=Decimal(1))
                first_open = first_opens.get(symbol)
                ref_open = first_open * later if first_open is not None else None
                apply, reason = _decide(cur, split, ref_open)
                params = {
                    "symbol": split.symbol,
                    "execution_date": split.execution_date,
                    "split_from": split.split_from,
                    "split_to": split.split_to,
                    "applied": apply,
                }
                cur.execute(_INSERT, params)
                if cur.fetchone() is None:
                    outcomes.append(SplitOutcome(split, False, False, "already recorded", 0))
                    log.info("split %s %s already recorded; skipped", symbol, split.execution_date)
                    continue
                rows = 0
                dividend_rows = 0
                if apply:
                    cur.execute(_REWRITE, params)
                    rows = cur.rowcount
                    cur.execute(_DROP_TINY_DIVIDENDS, params)
                    if cur.rowcount:
                        log.warning(
                            "split %s %s: %d earlier dividend(s) round to 0 after the split; removed",
                            symbol,
                            split.execution_date,
                            cur.rowcount,
                        )
                    cur.execute(_REWRITE_DIVIDENDS, params)
                    dividend_rows = cur.rowcount
                outcomes.append(SplitOutcome(split, True, apply, reason, rows, dividend_rows))
                log.info(
                    "split %s %s %s:%s %s (%s; %d rows, %d dividends)",
                    symbol,
                    split.execution_date,
                    split.split_from,
                    split.split_to,
                    "applied" if apply else "not applied",
                    reason,
                    rows,
                    dividend_rows,
                )
    return outcomes

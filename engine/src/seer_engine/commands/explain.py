"""explain: optional plain-language notes for the newest paper entries (design §4, D9).

For every roster strategy with a ``paper_state`` row whose ``pending_session`` is set:
  - bracket strategies: ``orders`` of that session with status 'pending' and no explanation;
  - book strategies: ``book_targets`` of that session with no explanation whose symbol the
    strategy does not already hold (``book_positions``): new entries only.
Each entry's prompt holds stored numbers only (symbol, strategy, prices, shares or weight, the
rule text from ``sim.rules.describe_rules``) and says it is PAPER ONLY, not a recommendation.

Failure never fails the night (design §8 "LLM fails -> explanation 'unavailable'"):
  - LLM_* not configured -> log "explanations unavailable", exit 0, no database connection;
  - an entry whose call fails or returns nothing -> its explanation stays NULL, the rest go on;
  - MAX_CONSECUTIVE_FAILURES failures in a row -> no more calls tonight, the rest stay NULL.
Reads happen in one short transaction that is closed before any LLM call; each strategy's
updates are then written in their own transaction, only where ``explanation IS NULL``.
``--dry-run`` reads, calls the LLM and runs the updates, then rolls back.
"""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol

import psycopg

from seer_engine import db, llm
from seer_engine.sim.rules import PRESETS, describe_rules

log = logging.getLogger(__name__)

HELP = "Write optional LLM explanations for the newest paper entries (never fails the night)"

MAX_CONSECUTIVE_FAILURES = 3
MAX_CHARS = 600

SYSTEM = (
    "You write short factual notes for a paper-trading log kept by a research app. "
    "Use only the facts you are given and add no numbers of your own. "
    "Never recommend buying or selling, never predict prices, never give financial advice. "
    "Write plain sentences without markdown, lists or headings."
)

_RULES_BY_ID = {r.id: r for r in PRESETS}

_STRATEGIES_SQL = """
SELECT s.id, s.name, s.sub, s.engine, s.rules_id, ps.pending_session
FROM strategies s
JOIN paper_state ps ON ps.strategy_id = s.id
WHERE s.engine IN ('bracket', 'book') AND ps.pending_session IS NOT NULL
ORDER BY s.sort, s.id
"""

_BRACKET_SQL = """
SELECT id, symbol, company, last_price, limit_price, tp_price, sl_price, shares
FROM orders
WHERE strategy_id = %s AND session_date = %s AND status = 'pending' AND explanation IS NULL
ORDER BY slot, symbol
"""

_BOOK_SQL = """
SELECT t.rank, t.symbol, t.weight, t.last_price, t.limit_price, t.stop_price, t.take_price
FROM book_targets t
WHERE t.strategy_id = %s AND t.session_date = %s AND t.explanation IS NULL
  AND NOT EXISTS (
    SELECT 1 FROM book_positions p WHERE p.strategy_id = t.strategy_id AND p.symbol = t.symbol
  )
ORDER BY t.rank
"""

_UPDATE_ORDER_SQL = "UPDATE orders SET explanation = %s WHERE id = %s AND explanation IS NULL"

_UPDATE_TARGET_SQL = """
UPDATE book_targets SET explanation = %s
WHERE strategy_id = %s AND session_date = %s AND symbol = %s AND explanation IS NULL
"""


class Completer(Protocol):
    def complete(self, system: str, prompt: str) -> str: ...


@dataclass(frozen=True)
class StrategyRow:
    id: str
    name: str
    sub: str
    engine: str
    rules_lines: tuple[str, ...]
    session_date: date


@dataclass(frozen=True)
class BracketEntry:
    strategy: StrategyRow
    order_id: int
    symbol: str
    company: str
    last_price: Decimal
    limit_price: Decimal
    tp_price: Decimal
    sl_price: Decimal
    shares: int


@dataclass(frozen=True)
class BookEntry:
    strategy: StrategyRow
    rank: int
    symbol: str
    weight: Decimal
    last_price: Decimal
    limit_price: Decimal | None
    stop_price: Decimal | None
    take_price: Decimal | None


Entry = BracketEntry | BookEntry


def _rules_lines(rules_id: str | None) -> tuple[str, ...]:
    rules = _RULES_BY_ID.get(rules_id) if rules_id is not None else None
    if rules is None:
        if rules_id is not None:
            log.debug("unknown rules_id %r; prompt carries no rule text", rules_id)
        return ()
    return describe_rules(rules)


def load_batches(conn: psycopg.Connection) -> list[tuple[StrategyRow, list[Entry]]]:
    """Every strategy's unexplained newest entries, in roster order; strategies with none omitted."""
    batches: list[tuple[StrategyRow, list[Entry]]] = []
    for sid, name, sub, engine, rules_id, pending in conn.execute(_STRATEGIES_SQL).fetchall():
        strategy = StrategyRow(sid, name, sub, engine, _rules_lines(rules_id), pending)
        entries: list[Entry] = []
        if engine == "bracket":
            for oid, symbol, company, last, limit, tp, sl, shares in conn.execute(
                _BRACKET_SQL, (sid, pending)
            ).fetchall():
                entries.append(BracketEntry(strategy, oid, symbol, company, last, limit, tp, sl, shares))
        else:
            for rank, symbol, weight, last, limit, stop, take in conn.execute(_BOOK_SQL, (sid, pending)).fetchall():
                entries.append(BookEntry(strategy, rank, symbol, weight, last, limit, stop, take))
        if entries:
            batches.append((strategy, entries))
    return batches


def _usd(x: Decimal) -> str:
    return f"${x:,.2f}"


def _pct(x: Decimal) -> str:
    return f"{x * 100:.1f}%"


def prompt_for(entry: Entry) -> str:
    """The user prompt for one entry: stored facts only, then the task."""
    s = entry.strategy
    facts = [
        "This is a PAPER trade only, simulated by the Seer research app. It is not a recommendation "
        "to buy, and no real money is involved.",
        f"Strategy: {s.name} ({s.sub}), a research strategy on paper.",
        f"Session the paper order is for: {s.session_date.isoformat()}.",
    ]
    if isinstance(entry, BracketEntry):
        facts += [
            f"Symbol: {entry.symbol} ({entry.company}).",
            f"Last close: {_usd(entry.last_price)}.",
            f"Paper order: buy {entry.shares} shares with a limit of {_usd(entry.limit_price)} "
            f"(about {_usd(entry.limit_price * entry.shares)}).",
            f"Take-profit: {_usd(entry.tp_price)}. Stop-loss: {_usd(entry.sl_price)}.",
        ]
    else:
        facts += [
            f"Symbol: {entry.symbol}.",
            f"Rank among this session's targets: {entry.rank}.",
            f"Target weight: {_pct(entry.weight)} of the paper portfolio.",
            f"Last close: {_usd(entry.last_price)}.",
        ]
        if entry.limit_price is not None:
            facts.append(f"Paper buy limit: {_usd(entry.limit_price)}.")
        if entry.take_price is not None:
            facts.append(f"Take-profit: {_usd(entry.take_price)}.")
        if entry.stop_price is not None:
            facts.append(f"Stop-loss: {_usd(entry.stop_price)}.")
    lines = ["Facts (all stored by Seer):", *(f"- {f}" for f in facts)]
    if s.rules_lines:
        lines.append("- Rules the paper simulator follows:")
        lines += [f"  - {r}" for r in s.rules_lines]
    lines.append(
        "Task: in at most 3 short plain-language sentences, explain what this paper entry does and "
        "how the rules above would exit it. Say that it is a paper trade, not a recommendation to buy. "
        "Use only the facts above."
    )
    return "\n".join(lines)


def clean(text: str) -> str | None:
    """Whitespace collapsed and capped at MAX_CHARS (cut at a word); None when nothing is left."""
    flat = " ".join(str(text).split())
    if not flat:
        return None
    if len(flat) > MAX_CHARS:
        cut = flat[:MAX_CHARS].rsplit(" ", 1)[0].rstrip(",;:")
        flat = f"{cut}…"
    return flat


def _update(conn: psycopg.Connection, entry: Entry, text: str) -> int:
    if isinstance(entry, BracketEntry):
        cur = conn.execute(_UPDATE_ORDER_SQL, (text, entry.order_id))
    else:
        cur = conn.execute(
            _UPDATE_TARGET_SQL, (text, entry.strategy.id, entry.strategy.session_date, entry.symbol)
        )
    return cur.rowcount


def execute(conn: psycopg.Connection, *, client: Completer, dry_run: bool = False) -> int:
    """Explain every new paper entry ``client`` can explain. Always returns 0."""
    batches = load_batches(conn)
    conn.rollback()  # close the read transaction before any slow network call
    total = sum(len(entries) for _, entries in batches)
    if total == 0:
        log.info("explain: no new paper entries without an explanation")
        return 0

    written = 0
    failures_in_row = 0
    stopped = False
    for strategy, entries in batches:
        texts: list[tuple[Entry, str]] = []
        for entry in entries:
            if stopped:
                break
            try:
                text = clean(client.complete(SYSTEM, prompt_for(entry)))
                if text is None:
                    raise llm.LlmError("empty explanation")
            except Exception as exc:  # noqa: BLE001 - an explanation must never fail the night
                failures_in_row += 1
                log.warning("explanation unavailable for %s %s: %s", strategy.id, entry.symbol, exc)
                if failures_in_row >= MAX_CONSECUTIVE_FAILURES:
                    stopped = True
                    log.warning(
                        "explain: %d failures in a row; no more LLM calls tonight, the rest stay unexplained",
                        failures_in_row,
                    )
                continue
            failures_in_row = 0
            texts.append((entry, text))
        if texts:
            with db.transaction(conn, dry_run):
                n = sum(_update(conn, entry, text) for entry, text in texts)
            written += n
            log.info("explain: %s %d of %d entries explained", strategy.id, n, len(entries))
    log.info("explain: %d written, %d unavailable, of %d new paper entries", written, total - written, total)
    return 0


def run(args: argparse.Namespace) -> int:
    cfg = llm.load_config()
    if cfg is None:
        log.warning("explanations unavailable: LLM_BASE_URL, LLM_API_KEY and LLM_MODEL must all be set")
        return 0
    conn = db.connect()
    try:
        return execute(conn, client=llm.Client(cfg), dry_run=bool(args.dry_run))
    finally:
        conn.close()

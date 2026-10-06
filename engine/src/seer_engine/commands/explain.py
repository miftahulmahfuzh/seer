"""explain: a plain "why this pick" note for each newest paper entry, from its stored evidence (design §4, D9).

For every roster strategy with a ``paper_state`` row whose ``pending_session`` is set:
  - bracket strategies: ``orders`` of that session with status 'pending' and no explanation;
  - book strategies: ``book_targets`` of that session with no explanation whose symbol the
    strategy does not already hold (``book_positions``): new entries only.
Each entry carries ``evidence`` (migration 009): the plain facts its method's formula used on that
stock the night ``paper`` picked it (``strategies.evidence``). The prompt holds the method's plain
name, the stock symbol and those facts, and nothing else: no order mechanics, no rule text. An entry
whose evidence is NULL or empty is skipped (logged) and keeps a NULL explanation.

The call disables thinking, at temperature 0, with ``EXPLAIN_MAX_TOKENS``: a reasoning model given a
small budget spends it thinking and returns a cut or empty text (the 2026-10-06 bug). Every reply
then goes through ``vet``: at most MAX_SENTENCES complete sentences, at most MAX_CHARS characters,
every number in it found among the facts' numbers, no advice or prediction phrase (``BANNED``), and
not a copy of a note already accepted for the same strategy tonight. A reply that fails is
discarded with its reason logged and stays NULL. Nothing is ever cut, and no ellipsis is added.

Failure never fails the night (design §8 "LLM fails -> explanation 'unavailable'"):
  - LLM_* not configured -> log "explanations unavailable", exit 0, no database connection;
  - an entry whose call raises, or whose reply is rejected -> its explanation stays NULL;
  - MAX_CONSECUTIVE_FAILURES calls in a row that *raise* -> no more calls tonight. A rejected reply
    is not an outage (the LLM answered), so it does not count and it resets the count.
Reads happen in one short transaction that is closed before any LLM call; each strategy's
updates are then written in their own transaction, only where ``explanation IS NULL``.
``--dry-run`` reads, calls the LLM and runs the updates, then rolls back.
"""

from __future__ import annotations

import argparse
import logging
import re
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol

import psycopg

from seer_engine import db, llm

log = logging.getLogger(__name__)

HELP = "Write optional LLM explanations for the newest paper entries (never fails the night)"

MAX_CONSECUTIVE_FAILURES = 3
MAX_CHARS = 320
MAX_SENTENCES = 2
# The length the prompt asks for, kept below MAX_CHARS so a reply that runs a little over still
# passes. Without a stated length the model restated all five facts and 6 of 8 replies came back
# at 330-381 characters (2026-10-06, first run on production).
PROMPT_CHARS = 260

# The call's settings. Thinking off is what makes the reply arrive whole: with thinking on,
# glm-5.3 spent a small budget on reasoning and returned a cut or empty text. Temperature 0 keeps
# the note a plain restatement of the facts. 1024 tokens is far more than two sentences need, so a
# provider that thinks anyway still has room to finish (veto uses the same three settings).
EXPLAIN_TEMPERATURE = 0.0
EXPLAIN_THINKING = "disabled"
EXPLAIN_MAX_TOKENS = 1024

SYSTEM = (
    "You write short factual notes for a paper-trading log kept by a research app. "
    "Use only the facts you are given and add no numbers of your own. "
    "Never recommend buying or selling, never predict prices, never give financial advice. "
    "Write plain sentences for a reader who is not a trader, without markdown, lists or headings."
)

_STRATEGIES_SQL = """
SELECT s.id, s.name, s.engine, ps.pending_session
FROM strategies s
JOIN paper_state ps ON ps.strategy_id = s.id
WHERE s.engine IN ('bracket', 'book') AND ps.pending_session IS NOT NULL
ORDER BY s.sort, s.id
"""

_BRACKET_SQL = """
SELECT id, symbol, evidence
FROM orders
WHERE strategy_id = %s AND session_date = %s AND status = 'pending' AND explanation IS NULL
ORDER BY slot, symbol
"""

_BOOK_SQL = """
SELECT t.symbol, t.evidence
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
    """What ``explain`` needs from the LLM (``llm.Client``)."""

    def complete(
        self,
        system: str,
        prompt: str,
        *,
        temperature: float | None = None,
        thinking: str | None = None,
        max_tokens: int | None = None,
    ) -> str: ...


def plain_name(name: str) -> str:
    """The display name without its roster code: 'F4 · Momentum' -> 'Momentum'.

    The code would put a number the facts do not hold (the 4 of F4) into the note, and the owner
    reads plain words, not ids. A name with no ' · ' part is returned as it is.
    """
    _, sep, rest = name.partition("·")
    rest = rest.strip()
    return rest if sep and rest else name.strip()


@dataclass(frozen=True)
class StrategyRow:
    id: str
    name: str
    engine: str
    session_date: date

    @property
    def plain_name(self) -> str:
        return plain_name(self.name)


@dataclass(frozen=True)
class BracketEntry:
    strategy: StrategyRow
    order_id: int
    symbol: str
    facts: tuple[str, ...]


@dataclass(frozen=True)
class BookEntry:
    strategy: StrategyRow
    symbol: str
    facts: tuple[str, ...]


Entry = BracketEntry | BookEntry


def facts_from(raw: Any) -> tuple[str, ...]:
    """A stored ``evidence`` value as facts: a JSON array of strings -> its non-blank strings,
    whitespace collapsed, in order. NULL, an empty array, or anything that is not an array of
    strings -> () (nothing to explain with)."""
    if not isinstance(raw, list) or not all(isinstance(f, str) for f in raw):
        return ()
    return tuple(" ".join(f.split()) for f in raw if f.strip())


def load_batches(conn: psycopg.Connection) -> list[tuple[StrategyRow, list[Entry]]]:
    """Every strategy's unexplained newest entries, in roster order; strategies with none omitted.

    Entries without evidence are returned too (with ``facts == ()``) so ``execute`` can count and
    log them; it never sends them to the LLM.
    """
    batches: list[tuple[StrategyRow, list[Entry]]] = []
    for sid, name, engine, pending in conn.execute(_STRATEGIES_SQL).fetchall():
        strategy = StrategyRow(sid, name, engine, pending)
        entries: list[Entry] = []
        if engine == "bracket":
            for oid, symbol, evidence in conn.execute(_BRACKET_SQL, (sid, pending)).fetchall():
                entries.append(BracketEntry(strategy, oid, symbol, facts_from(evidence)))
        else:
            for symbol, evidence in conn.execute(_BOOK_SQL, (sid, pending)).fetchall():
                entries.append(BookEntry(strategy, symbol, facts_from(evidence)))
        if entries:
            batches.append((strategy, entries))
    return batches


def prompt_for(entry: Entry) -> str:
    """The user prompt for one entry: the method's plain name, the stock, its facts, the task."""
    return "\n".join(
        [
            f"Method: {entry.strategy.plain_name}, a research method followed on paper.",
            f"Stock: {entry.symbol}",
            "Facts the method's formula used on this stock:",
            *(f"- {fact}" for fact in entry.facts),
            "Task: in at most 2 short plain sentences, say why this method picked this stock, "
            "using only these facts. Write every number exactly as the facts write it. "
            f"Keep the whole note under {PROMPT_CHARS} characters: use the two or three facts that "
            "matter most, not all of them. Say the method picked it, never that it flagged it. "
            "No advice, no predictions.",
        ]
    )


# ---- the checks ------------------------------------------------------------------------------


class Rejected(ValueError):
    """A reply ``vet`` refuses; the message is the reason, for the log."""


@dataclass(frozen=True)
class Banned:
    """A phrase no note may hold. ``allowed_if_in_facts``: the phrase may describe the past (e.g.
    "than expected"), so restating a fact that already uses it is not a prediction."""

    label: str
    pattern: re.Pattern[str]
    allowed_if_in_facts: bool = False


def _phrase(regex: str) -> re.Pattern[str]:
    return re.compile(regex, re.IGNORECASE)


# Word-bounded so "buyback", "buyer", "resell", "seller" and "unexpected" pass. "Best Buy" and
# "sell-off" are rejected; such a note stays NULL and the site shows the facts instead.
BANNED: tuple[Banned, ...] = (
    Banned("buy", _phrase(r"\bbuy(?:s|ing)?\b")),
    Banned("sell", _phrase(r"\bsell(?:s|ing)?\b")),
    Banned("recommend", _phrase(r"\brecommend\w*")),
    Banned("should", _phrase(r"\bshould(?:n['’]?t)?\b")),
    Banned(
        "will + a price move",
        _phrase(
            r"\bwill\s+(?:likely\s+|probably\s+)?(?:rise|go\s+up|go\s+down|fall|climb|drop|gain|grow|"
            r"rebound|recover|bounce|continue|keep|outperform|beat|soar|surge|rally)\b"
        ),
    ),
    Banned("going to", _phrase(r"\bgoing\s+to\b")),
    Banned("expect", _phrase(r"\bexpect(?:s|ed|ing|ations?)?\b"), allowed_if_in_facts=True),
    Banned("guarantee", _phrase(r"\bguarantee\w*")),
)

# A number: optional $, digits with optional thousands commas, optional decimals, optional %.
# Not preceded by a letter or digit, so a symbol such as S01 or a code such as F4 is not a number.
# A sign is not part of the token: "+3", "-3" and "3" are the same number to the reader.
_NUMBER = re.compile(r"(?<![A-Za-z0-9_])\$?\d(?:[\d,]*\d)?(?:\.\d+)?%?")
# A sentence ends at . ! or ? (plus closing quotes or brackets) followed by the end of the text, or
# by a space and a capital, digit, quote or bracket. "Inc. is" and "4.5" are not ends.
_SENTENCE_END = re.compile(r"[.!?]+[\"'”’)\]]*(?=\s+[A-Z0-9\"“(]|\s*$)")
_MARKUP = re.compile(r"[*_`#]+")
_BULLET = re.compile(r"^(?:[-•]|\d+[.)])\s+")
_QUOTES = "\"'“”‘’"


def normalize_number(token: str) -> str:
    """'$1,850.00' -> '1850', '6.10%' -> '6.1', '0.50' -> '0.5', '007' -> '7'."""
    s = token.replace("$", "").replace(",", "").replace("%", "")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    s = s.lstrip("0")
    return "0" + s if not s or s.startswith(".") else s


def numbers_in(text: str) -> set[str]:
    """Every number in ``text``, normalized (``normalize_number``)."""
    return {normalize_number(m) for m in _NUMBER.findall(text)}


def sentence_count(text: str) -> int:
    return len(_SENTENCE_END.findall(text))


def clean(text: str) -> str:
    """The reply without markdown marks, a leading bullet or wrapping quotes, whitespace collapsed.
    Never cut; "" when nothing is left."""
    flat = _MARKUP.sub("", " ".join(str(text).split()))
    flat = _BULLET.sub("", flat.strip())
    flat = flat.strip().strip(_QUOTES).strip()
    return " ".join(flat.split())


def vet(reply: str, facts: Sequence[str], earlier: Collection[str] = ()) -> str:
    """The cleaned note when it passes every check; ``Rejected(reason)`` otherwise.

    ``earlier``: the notes already accepted for the same strategy tonight.
    """
    text = clean(reply)
    if not text:
        raise Rejected("empty reply")
    if "…" in text or "..." in text:
        raise Rejected("has an ellipsis (a cut-off text)")
    if text[-1] not in ".!?":
        raise Rejected("not a complete sentence")
    n = sentence_count(text)
    if n > MAX_SENTENCES:
        raise Rejected(f"{n} sentences, at most {MAX_SENTENCES}")
    if len(text) > MAX_CHARS:
        raise Rejected(f"{len(text)} characters, at most {MAX_CHARS}")
    joined = " ".join(facts)
    for banned in BANNED:
        if banned.pattern.search(text) and not (banned.allowed_if_in_facts and banned.pattern.search(joined)):
            raise Rejected(f"banned phrase ({banned.label})")
    invented = sorted(numbers_in(text) - numbers_in(joined))
    if invented:
        raise Rejected(f"number not in the facts: {', '.join(invented)}")
    key = text.casefold()
    if any(clean(e).casefold() == key for e in earlier):
        raise Rejected("same as an earlier note for this strategy")
    return text


def accept(text: str, facts: Sequence[str], earlier: Collection[str] = ()) -> str | None:
    """``vet`` as a value: the note, or None when it is rejected."""
    try:
        return vet(text, facts, earlier)
    except Rejected:
        return None


# ---- the step --------------------------------------------------------------------------------


def _update(conn: psycopg.Connection, entry: Entry, text: str) -> int:
    if isinstance(entry, BracketEntry):
        cur = conn.execute(_UPDATE_ORDER_SQL, (text, entry.order_id))
    else:
        cur = conn.execute(
            _UPDATE_TARGET_SQL, (text, entry.strategy.id, entry.strategy.session_date, entry.symbol)
        )
    return cur.rowcount


def execute(conn: psycopg.Connection, *, client: Completer, dry_run: bool = False) -> int:
    """Explain every new paper entry that has evidence and a reply that passes ``vet``. Always 0."""
    batches = load_batches(conn)
    conn.rollback()  # close the read transaction before any slow network call
    total = sum(len(entries) for _, entries in batches)
    if total == 0:
        log.info("explain: no new paper entries without an explanation")
        return 0

    written = skipped = rejected = failed = 0
    failures_in_row = 0
    stopped = False
    for strategy, entries in batches:
        texts: list[tuple[Entry, str]] = []
        for entry in entries:
            if not entry.facts:
                skipped += 1
                log.info("explain: %s %s has no evidence; left unexplained", strategy.id, entry.symbol)
                continue
            if stopped:
                continue
            try:
                reply = client.complete(
                    SYSTEM,
                    prompt_for(entry),
                    temperature=EXPLAIN_TEMPERATURE,
                    thinking=EXPLAIN_THINKING,
                    max_tokens=EXPLAIN_MAX_TOKENS,
                )
            except Exception as exc:  # noqa: BLE001 - an explanation must never fail the night
                failed += 1
                failures_in_row += 1
                log.warning("explanation unavailable for %s %s: %s", strategy.id, entry.symbol, exc)
                if failures_in_row >= MAX_CONSECUTIVE_FAILURES:
                    stopped = True
                    log.warning(
                        "explain: %d failures in a row; no more LLM calls tonight, the rest stay unexplained",
                        failures_in_row,
                    )
                continue
            failures_in_row = 0  # the LLM answered: whatever vet says, it is not an outage
            try:
                text = vet(reply, entry.facts, [t for _, t in texts])
            except Rejected as why:
                rejected += 1
                log.warning("explanation rejected for %s %s: %s", strategy.id, entry.symbol, why)
                continue
            texts.append((entry, text))
        if texts:
            with db.transaction(conn, dry_run):
                n = sum(_update(conn, entry, text) for entry, text in texts)
            written += n
            log.info("explain: %s %d of %d entries explained", strategy.id, n, len(entries))
    log.info(
        "explain: %d written, %d rejected, %d failed, %d without evidence, of %d new paper entries",
        written, rejected, failed, skipped, total,
    )
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

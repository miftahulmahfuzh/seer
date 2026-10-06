> Adopted from `WHY_THIS_PICK_PIPELINE_PLAN.md` phase 3. Source: `.workflows/plan/why-this-pick-pipeline/phase-3.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 3: Explain from evidence, with checks

**Plan set:** `WHY_THIS_PICK_PIPELINE_PLAN.md`
**Analysis:** `20261006-213425-W7P3_code_analyzer.md`
**Satisfies:** R2, R3, R4, R8. Each new paper pick gets one or two plain sentences built only from
the numbers its method used. Invented numbers, advice, predictions, cut-off text and copies are
thrown away, and the night never fails.
**Depends on:** Phase 2 (migration 009 `evidence jsonb` on `orders` / `book_targets`, filled by `paper`). Phase 1 only through phase 2's stored strings.
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/commands`

---

## Goal

`explain` stops sending order details (shares, limit, take-profit, rule text, "say it is a paper
trade"). For each new entry it reads the `evidence` that phase 2 stored and sends the method's plain
name, the stock and those facts. It calls the LLM with thinking disabled and temperature 0. Every
reply must pass a deterministic `vet` check before it is written. A reply that fails the check
stays NULL. Entries with no evidence are skipped, nothing is cut, and no "…" is ever added. Only
real call failures (exceptions) count toward the stop after too many failures in a row.

## Interface Contract

**Deletes:**
- `explain.clean`'s cut at 600 characters with "…" (`explain.py:202`). `clean` is redefined below with a different signature.
- `explain._usd`, `explain._pct` (`explain.py:152,156`).
- `explain._rules_lines`, `explain._RULES_BY_ID` (`explain.py:47,124`) and the import of `sim.rules.PRESETS, describe_rules` (`explain.py:31`).
- Fields `StrategyRow.sub`, `StrategyRow.rules_lines`.
- Fields `BracketEntry.company/last_price/limit_price/tp_price/sl_price/shares`.
- Fields `BookEntry.rank/weight/last_price/limit_price/stop_price/take_price`.
- The `from decimal import Decimal` import.

**Renames:** none.

**Creates (all in `engine/src/seer_engine/commands/explain.py`):**
- Constants: `MAX_SENTENCES = 2`, `EXPLAIN_TEMPERATURE = 0.0`, `EXPLAIN_THINKING = "disabled"`, `EXPLAIN_MAX_TOKENS = 1024`, `BANNED` (a tuple of `Banned`).
- `class Rejected(ValueError)` and `@dataclass(frozen=True) class Banned(label, pattern, allowed_if_in_facts)`.
- `plain_name(name) -> str` and `facts_from(raw) -> tuple[str, ...]`.
- `normalize_number(token) -> str`, `numbers_in(text) -> set[str]` and `sentence_count(text) -> int`.
- `vet(reply, facts, earlier=()) -> str`, which raises `Rejected(reason)`.
- `accept(text, facts, earlier=()) -> str | None`.
- Field `facts: tuple[str, ...]` on `BracketEntry` and on `BookEntry`.

**Signature changes:**
- `MAX_CHARS` changes from `600` to `320`.
- `clean(text) -> str | None` becomes `clean(text) -> str`. It never cuts the text, and `""` means nothing is left.
- `Completer.complete(self, system, prompt) -> str` becomes `complete(self, system, prompt, *, temperature: float | None = None, thinking: str | None = None, max_tokens: int | None = None) -> str`. This is the same shape as `veto.Completer` and `llm.Client.complete`.
- `StrategyRow(id, name, sub, engine, rules_lines, session_date)` becomes `StrategyRow(id, name, engine, session_date)` and gains the property `plain_name`.
- `BracketEntry(strategy, order_id, symbol, company, last_price, limit_price, tp_price, sl_price, shares)` becomes `BracketEntry(strategy, order_id, symbol, facts)`.
- `BookEntry(strategy, rank, symbol, weight, last_price, limit_price, stop_price, take_price)` becomes `BookEntry(strategy, symbol, facts)`.
- `SYSTEM` adds "for a reader who is not a trader". It keeps "Never recommend buying or selling, never predict prices" (invariant 6).

**Unchanged:** `prompt_for(entry) -> str`, `load_batches(conn)`, `execute(conn, *, client, dry_run=False) -> int` and `run(args) -> int` keep their signatures. Their behaviour is new.

**Requires (from earlier phases):**
- The columns `orders.evidence` and `book_targets.evidence` exist as `jsonb` (`db/migrations/009_evidence.sql`, phase 2). They hold a JSON array of strings, or NULL. The `pg` test fixture applies every `db/migrations/*.sql`, so the tests see the columns.
- After a paper night, every pending order or target row of A, C, F4, F1 and FND has a non-empty `evidence` array, except the idle symbol (phase 2 exit criterion). `tests/test_paper_c.py::test_explain_fills_c_pending_orders_like_a` depends on this for C.
- Each fact is a plain sentence with its numbers formatted inside the string (K1, phase 1). It has no indicator codes, and the stock symbol is not required in it.

**Leaves alone (owned by others):**
- `paper/store.py`, `commands/paper.py`, `db/migrations/009_evidence.sql` and `tests/test_paper_evidence.py` (phase 2).
- `strategies/evidence.py` and `tests/test_evidence.py` (phase 1).
- `commands/promote.py`, `tests/test_promote_command.py` and the explore skill (phase 4).
- `web/**` (phase 5).
- `commands/veto.py` and `strategies/c.py`. Veto's prompt `c-veto-v1` is frozen.
- `book_previews`: Explain never writes to it (plan decision: previews show their facts and get no LLM text).

**Also owns (granted to this phase in invariant 8 by the reconciler; no other phase edits them):**
- `engine/tests/test_paper_c.py:490`. A single assertion changes because the prompt no longer contains `"C · News veto"`. (Phase 2's `test_paper_evidence.py` imports this file's helpers but never edits it.)
- `engine/src/seer_engine/llm.py:10-16,166-172`. Docstrings only, because they say `explain` makes the keyword-less call. No code changes.
- The docs of the whole set live in this phase's two doc files: phase 2's Paper step and its warning line (runbook 5f), and phase 4's third promotable condition (package_readme 6h). Phases 2, 4 and 5 do not edit these files, so phases 3, 4 and 5 can run at the same time.

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/commands/explain.py` | rewrite | evidence-only prompt, thinking disabled, `vet`/`accept` checks, skip entries without evidence, rejections not counted as failures |
| `engine/tests/test_explain.py` | rewrite | seeds `evidence`, fake Completer takes keyword arguments, PG tests for skip / reject / duplicates / outage, pure unit tests for `vet` |
| `engine/tests/test_paper_c.py` | modify (line 490) | the prompt now names the method `"News veto"`, not `"C · News veto"` |
| `engine/src/seer_engine/llm.py` | modify (docstrings 10-16, 166-172) | `explain` now passes keywords too |
| `docs/runbooks/paper-trading.md` | modify (94, 98, 136, 148, 159, new section before 323) | Paper stores evidence (phase 2) and its warning line; Explain: what it reads, the checks, why thinking is disabled |
| `engine/package_readme.md` | modify (30, 97, 504-510, 540 promote bullet, 1970, new Migration 009 section before 2047, new Usage section before 2274, 2397) | evidence → explain pipeline overview; promote's evidence condition (phase 4's behaviour, documented here) |

## Implementation Steps

### Step 1: Rewrite `explain.py`
**File:** `engine/src/seer_engine/commands/explain.py:1-274` (whole file)
**Change:** replace the whole file with the code below.
**Code:**
```python
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
```
**Impact:**
- `explain` reads the `evidence` column, so it needs migration 009 applied. In production, the nightly Migrate step runs before Explain.
- Entries written before phase 2 have NULL evidence and stay unexplained. Re-explaining them is out of scope (plan Scope).
- `tests/test_paper_c.py` imports `FakeClient` from `test_explain`. The new `FakeClient()` keeps a no-argument constructor and the reply `"Paper note for {symbol}."` (Step 3).
- `psycopg` loads `jsonb` as Python lists by default, so `facts_from` receives a `list`. No loader configuration is needed.

### Step 2: Rewrite `tests/test_explain.py`
**File:** `engine/tests/test_explain.py:1-208` (whole file)
**Change:** replace the whole file. It keeps the fake-Completer style. The seed now writes `evidence` with `psycopg.types.json.Jsonb`. The `vet` / `accept` unit tests need no database.
**Code:**
```python
"""explain: notes for the newest paper entries, from their stored evidence only; every reply is
vetted, and the night never fails (PG for the step, pure for the checks)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal

import pytest
from psycopg.types.json import Jsonb

from seer_engine import cli, llm
from seer_engine.commands import explain

LAST = date(2026, 10, 30)
NEXT = date(2026, 11, 2)
OLD = date(2026, 10, 1)
F4 = "F4-MOM12-N20-TREND"
F1 = "F1-SPY-SMA200-M"

AAPL_FACTS = [
    "AAPL closed at $190.00, 6.1% above its 200-day average.",
    "Its 2-day strength score was 4 out of 100; below 10 counts as a sharp short drop.",
    "It came 1st of 2 stocks that qualified tonight.",
]
JNJ_FACTS = [
    "JNJ closed at $151.20, 2.4% above its 200-day average.",
    "Its 2-day strength score was 7 out of 100; below 10 counts as a sharp short drop.",
    "It came 2nd of 2 stocks that qualified tonight.",
]
NVDA_FACTS = [  # phase 1's exact FACTOR wording
    "Its price rose 48.2% from 12 months ago to 1 month ago.",
    "It ranked 3rd of 412 stocks checked on that move, strongest first.",
    "SPY closed 4.1% above its 200-day average, so the method is allowed to hold stocks.",
]
SPY_FACTS = ["SPY closed at $671.20, 8.3% above its 200-day average of $619.80, so the rule says hold."]

Reply = Callable[[str, str], str]


def paper_note(symbol: str, prompt: str) -> str:
    return f"  Paper note\n for {symbol}.  "


class FakeClient:
    """Records every call; replies ``reply(symbol, prompt)`` (default: "Paper note for X.")."""

    def __init__(self, fail_on: set[str] | None = None, fail_all: bool = False, reply: Reply = paper_note):
        self.fail_on = fail_on or set()
        self.fail_all = fail_all
        self.reply = reply
        self.prompts: list[str] = []
        self.systems: list[str] = []
        self.kwargs: list[dict[str, object]] = []

    def complete(
        self,
        system: str,
        prompt: str,
        *,
        temperature: float | None = None,
        thinking: str | None = None,
        max_tokens: int | None = None,
    ) -> str:
        self.prompts.append(prompt)
        self.systems.append(system)
        self.kwargs.append({"temperature": temperature, "thinking": thinking, "max_tokens": max_tokens})
        symbol = next(line for line in prompt.splitlines() if line.startswith("Stock: "))[len("Stock: "):]
        if self.fail_all or symbol in self.fail_on:
            raise llm.LlmError("HTTP 503 from the LLM endpoint: busy", 503)
        return self.reply(symbol, prompt)


def seed(pg) -> None:
    """Rows as `paper` (with phase 2's evidence) would leave them after deciding session NEXT."""
    for sid in ("SPY", "A", F4, F1):
        pg.execute(
            "INSERT INTO paper_state (strategy_id, last_session, cash_usd, equity_usd, initial_cash_usd,"
            " usd_idr, pending_session, pending_decision) VALUES (%s, %s, 1000, 1000, 1200, 16500, %s, %s)",
            (sid, LAST, NEXT, sid in (F4, F1)),
        )
    order_sql = (
        "INSERT INTO orders (strategy_id, session_date, slot, symbol, company, last_price, limit_price,"
        " tp_price, sl_price, shares, explanation, status, evidence)"
        " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
    )
    pg.execute(order_sql, ("A", NEXT, 1, "AAPL", "Apple Inc.", 190, 185, 195, 180, 10, None, "pending", Jsonb(AAPL_FACTS)))
    pg.execute(order_sql, ("A", NEXT, 2, "JNJ", "Johnson & Johnson", 151, 148, 155, 145, 3, None, "pending", Jsonb(JNJ_FACTS)))
    pg.execute(order_sql, ("A", NEXT, 3, "MSFT", "Microsoft", 400, 390, 410, 380, 2, "kept", "pending", Jsonb(AAPL_FACTS)))
    pg.execute(order_sql, ("A", NEXT, 4, "PFE", "Pfizer", 27, 27, 28, 26, 30, None, "pending", None))  # no evidence
    pg.execute(order_sql, ("A", LAST, 5, "KO", "Coca-Cola", 60, 59, 61, 58, 30, None, "open", Jsonb(AAPL_FACTS)))
    target_sql = (
        "INSERT INTO book_targets (strategy_id, session_date, rank, symbol, weight, last_price, limit_price, evidence)"
        " VALUES (%s,%s,%s,%s,%s,%s,%s,%s)"
    )
    pg.execute(target_sql, (F4, NEXT, 1, "NVDA", Decimal("0.05"), 120, Decimal("122.40"), Jsonb(NVDA_FACTS)))
    pg.execute(target_sql, (F4, NEXT, 2, "AAPL", Decimal("0.05"), 190, Decimal("193.80"), Jsonb(NVDA_FACTS)))
    pg.execute(target_sql, (F4, NEXT, 3, "META", Decimal("0.05"), 700, Decimal("714.00"), Jsonb([])))  # empty
    pg.execute(target_sql, (F4, OLD, 1, "AMD", Decimal("0.05"), 150, Decimal("153.00"), Jsonb(NVDA_FACTS)))
    pg.execute(target_sql, (F1, NEXT, 1, "SPY", Decimal("1"), 660, Decimal("673.20"), Jsonb(SPY_FACTS)))
    pos_sql = (
        "INSERT INTO book_positions (strategy_id, symbol, shares, mark, entry_date, entry_price, days_held,"
        " cost_usd, income_usd) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)"
    )
    pg.execute(pos_sql, (F4, "AAPL", 5, 190, OLD, 180, 20, 1, 0))
    pg.execute(pos_sql, ("SPY", "SPY", 2, 660, OLD, 650, 20, 1, 0))  # the benchmark's holding, not F1's
    pg.commit()


def order_notes(pg) -> dict[str, str | None]:
    rows = pg.execute("SELECT symbol, explanation FROM orders WHERE strategy_id = 'A'").fetchall()
    pg.rollback()
    return dict(rows)


def target_notes(pg) -> dict[tuple[str, date, str], str | None]:
    rows = pg.execute("SELECT strategy_id, session_date, symbol, explanation FROM book_targets").fetchall()
    pg.rollback()
    return {(sid, d, sym): note for sid, d, sym, note in rows}


def all_null_except_kept(pg) -> None:
    assert order_notes(pg) == {"AAPL": None, "JNJ": None, "MSFT": "kept", "PFE": None, "KO": None}
    assert set(target_notes(pg).values()) == {None}


# ---- the step (PG) ---------------------------------------------------------------------------


def test_fills_only_the_newest_entries_that_have_evidence(pg):
    seed(pg)
    client = FakeClient()
    assert explain.execute(pg, client=client) == 0
    assert order_notes(pg) == {
        "AAPL": "Paper note for AAPL.",
        "JNJ": "Paper note for JNJ.",
        "MSFT": "kept",
        "PFE": None,  # no evidence: skipped, never sent
        "KO": None,  # an older, open order
    }
    assert target_notes(pg) == {
        (F4, NEXT, "NVDA"): "Paper note for NVDA.",
        (F4, NEXT, "AAPL"): None,  # already held: a re-weight, not a new entry
        (F4, NEXT, "META"): None,  # evidence is an empty array: skipped
        (F4, OLD, "AMD"): None,  # an older decision
        (F1, NEXT, "SPY"): "Paper note for SPY.",  # SPY held by the benchmark, not by F1
    }
    assert len(client.prompts) == 4
    assert not any("Stock: PFE" in p or "Stock: META" in p for p in client.prompts)


def test_prompt_is_the_plain_name_the_stock_and_its_facts_only(pg):
    seed(pg)
    client = FakeClient()
    explain.execute(pg, client=client)
    aapl, jnj, nvda, spy = client.prompts
    assert aapl.splitlines()[:2] == ["Method: Quant, a research method followed on paper.", "Stock: AAPL"]
    for fact in AAPL_FACTS:
        assert f"- {fact}" in aapl
    assert "- " + JNJ_FACTS[0] in jnj and AAPL_FACTS[0] not in jnj
    assert "Method: Momentum," in nvda and "Method: Trend," in spy
    for fact in NVDA_FACTS:
        assert f"- {fact}" in nvda
    for p in client.prompts:
        assert "at most 2 short plain sentences" in p and "using only these facts" in p
        assert "No advice, no predictions." in p
        # no order mechanics, no roster codes, no paper boilerplate (R4, R8)
        for gone in ("PAPER", "paper trade", "Take-profit", "Stop-loss", "limit", "shares", "Rule set",
                     "A · Quant", "F4", "F1", "Apple Inc.", "$185.00", "Target weight"):
            assert gone not in p


def test_call_disables_thinking_at_temperature_zero(pg):
    seed(pg)
    client = FakeClient()
    explain.execute(pg, client=client)
    assert client.kwargs == [
        {"temperature": 0.0, "thinking": "disabled", "max_tokens": explain.EXPLAIN_MAX_TOKENS}
    ] * 4
    assert set(client.systems) == {explain.SYSTEM}
    assert "Never recommend buying or selling, never predict prices" in explain.SYSTEM


def test_rerun_calls_nothing(pg):
    seed(pg)
    explain.execute(pg, client=FakeClient())
    again = FakeClient()
    assert explain.execute(pg, client=again) == 0
    assert again.prompts == []


def test_one_failure_leaves_that_entry_null_and_exits_zero(pg):
    seed(pg)
    assert explain.execute(pg, client=FakeClient(fail_on={"NVDA"})) == 0
    notes = target_notes(pg)
    assert notes[(F4, NEXT, "NVDA")] is None
    assert notes[(F1, NEXT, "SPY")] == "Paper note for SPY."
    assert order_notes(pg)["AAPL"] == "Paper note for AAPL."


def test_llm_down_leaves_everything_null_and_exits_zero(pg, monkeypatch):
    seed(pg)
    monkeypatch.setattr(explain, "MAX_CONSECUTIVE_FAILURES", 2)
    client = FakeClient(fail_all=True)
    assert explain.execute(pg, client=client) == 0
    assert len(client.prompts) == 2  # the circuit breaker stopped the third call
    all_null_except_kept(pg)


def test_rejected_replies_stay_null_and_never_stop_the_night(pg, monkeypatch, caplog):
    seed(pg)
    monkeypatch.setattr(explain, "MAX_CONSECUTIVE_FAILURES", 2)
    client = FakeClient(reply=lambda symbol, prompt: f"{symbol} rose 99% in a week.")
    assert explain.execute(pg, client=client) == 0
    assert len(client.prompts) == 4  # a rejection is not an outage: every entry was still asked
    all_null_except_kept(pg)
    assert "explanation rejected for A AAPL: number not in the facts: 99" in caplog.text


def test_a_rejection_resets_the_failure_count(pg, monkeypatch):
    seed(pg)
    monkeypatch.setattr(explain, "MAX_CONSECUTIVE_FAILURES", 2)
    # AAPL fails, JNJ answers (rejected: a buy word), NVDA fails, SPY answers well. Without the reset
    # the second failure would stop the night before SPY.
    client = FakeClient(
        fail_on={"AAPL", "NVDA"},
        reply=lambda symbol, prompt: "A buy." if symbol == "JNJ" else f"Paper note for {symbol}.",
    )
    assert explain.execute(pg, client=client) == 0
    assert len(client.prompts) == 4
    assert target_notes(pg)[(F1, NEXT, "SPY")] == "Paper note for SPY."
    assert order_notes(pg)["JNJ"] is None


def test_the_same_note_twice_in_one_strategy_is_kept_once(pg):
    seed(pg)
    same = FakeClient(reply=lambda symbol, prompt: "The method picked this stock on its own numbers.")
    assert explain.execute(pg, client=same) == 0
    notes = order_notes(pg)
    assert notes["AAPL"] == "The method picked this stock on its own numbers."
    assert notes["JNJ"] is None  # a copy of AAPL's note in the same strategy
    # another strategy's batch is judged on its own
    assert target_notes(pg)[(F4, NEXT, "NVDA")] == "The method picked this stock on its own numbers."


def test_client_bug_never_raises(pg):
    seed(pg)

    class Broken:
        def complete(self, system, prompt, **kwargs):
            raise KeyError("unexpected")

    assert explain.execute(pg, client=Broken()) == 0
    all_null_except_kept(pg)


def test_empty_reply_counts_as_unavailable(pg):
    seed(pg)

    class Blank:
        def complete(self, system, prompt, **kwargs):
            return "   \n "

    assert explain.execute(pg, client=Blank()) == 0
    all_null_except_kept(pg)


def test_dry_run_writes_nothing(pg):
    seed(pg)
    client = FakeClient()
    assert explain.execute(pg, client=client, dry_run=True) == 0
    assert len(client.prompts) == 4
    all_null_except_kept(pg)


def test_no_paper_state_is_a_no_op(pg):
    client = FakeClient()
    assert explain.execute(pg, client=client) == 0
    assert client.prompts == []


def test_missing_config_exits_zero_without_touching_the_db(pg, monkeypatch, caplog):
    seed(pg)
    for name in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"):
        monkeypatch.delenv(name, raising=False)
    # DATABASE_URL_UNPOOLED points at an invalid host (conftest): a connection attempt would fail.
    assert cli.main(["explain"]) == 0
    assert "explanations unavailable" in caplog.text
    all_null_except_kept(pg)


def test_cli_end_to_end(pg_schema, pg, monkeypatch):
    seed(pg)
    monkeypatch.setenv("LLM_BASE_URL", "https://llm.test/api/anthropic")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    monkeypatch.setenv("LLM_MODEL", "glm-test")
    monkeypatch.setenv("DATABASE_URL_UNPOOLED", pg_schema.url)
    fake = FakeClient()
    monkeypatch.setattr(llm, "Client", lambda cfg: fake)
    assert cli.main(["explain"]) == 0
    assert target_notes(pg)[(F4, NEXT, "NVDA")] == "Paper note for NVDA."
    assert cli.main(["--dry-run", "explain"]) == 0  # nothing left to explain; still 0


# ---- the checks (pure) -----------------------------------------------------------------------

FACTS = (
    "NVDA rose 48.2% over the 12 months up to a month ago.",
    "That ranked 3rd of 412 eligible stocks.",
    "SPY closed at $671.20, 8.3% above its 200-day average of $1,619.80.",
)


@pytest.mark.parametrize(
    ("reply", "want"),
    [
        ("NVDA rose 48.2% over the past 12 months, the 3rd best of 412 stocks.",
         "NVDA rose 48.2% over the past 12 months, the 3rd best of 412 stocks."),
        ('  **"NVDA rose 48.20% over 12 months."**  ', "NVDA rose 48.20% over 12 months."),  # markup, quotes, zeros
        ("- NVDA rose 48.2% over 12 months.", "NVDA rose 48.2% over 12 months."),  # a bullet
        ("SPY was 8.3% above its 1619.8 average.", "SPY was 8.3% above its 1619.8 average."),  # $ , and zeros
        ("NVDA rose 48.2% over 12 months. That ranked 3rd of 412 stocks.",
         "NVDA rose 48.2% over 12 months. That ranked 3rd of 412 stocks."),  # two sentences
        ("NVDA ranked 3rd of 412 stocks, ahead of the buyback names.",
         "NVDA ranked 3rd of 412 stocks, ahead of the buyback names."),  # "buyback" is not "buy"
        ("S01 ranked 3rd of 412 stocks.", "S01 ranked 3rd of 412 stocks."),  # a symbol's digits are no number
    ],
)
def test_vet_accepts(reply, want):
    assert explain.vet(reply, FACTS) == want
    assert explain.accept(reply, FACTS) == want


@pytest.mark.parametrize(
    ("reply", "reason"),
    [
        ("", "empty"),
        ("  \n ", "empty"),
        ("NVDA rose 50% over 12 months.", "number not in the facts: 50"),
        ("NVDA rose 48.2% over 12 months and ranked", "not a complete sentence"),
        ("NVDA rose 48.2%…", "ellipsis"),
        ("NVDA rose 48.2%...", "ellipsis"),
        ("NVDA rose 48.2%. It ranked 3rd. Of 412 stocks.", "3 sentences"),
        ("NVDA rose 48.2% over 12 months " + "and kept its place " * 20 + ".", "characters"),
        ("You should look at NVDA, which rose 48.2%.", "should"),
        ("NVDA shouldn't fall.", "should"),
        ("NVDA is a buy after rising 48.2%.", "buy"),
        ("NVDA hit a sell signal.", "sell"),
        ("Analysts recommend NVDA.", "recommend"),
        ("NVDA will rise after its 48.2% gain.", "a price move"),  # match= is a regex: no "+"
        ("NVDA is going to climb.", "going to"),
        ("We expect NVDA to keep its place.", "expect"),
        ("Returns are not guaranteed.", "guarantee"),
    ],
)
def test_vet_rejects(reply, reason):
    with pytest.raises(explain.Rejected, match=reason):
        explain.vet(reply, FACTS)
    assert explain.accept(reply, FACTS) is None


def test_vet_rejects_a_copy_of_an_earlier_note():
    with pytest.raises(explain.Rejected, match="same as an earlier note"):
        explain.vet("NVDA rose 48.2% over 12 months.", FACTS, ["  nvda rose 48.2% over 12 months. "])
    assert explain.vet("NVDA rose 48.2% over 12 months.", FACTS, ["NVDA ranked 3rd of 412 stocks."])


def test_a_past_tense_phrase_the_facts_use_is_allowed():
    facts = ("Its last earnings came in above what was expected.",)
    assert explain.vet("Its last earnings came in above what was expected.", facts)
    with pytest.raises(explain.Rejected, match="expect"):
        explain.vet("Its last earnings came in above what was expected.", FACTS)


def test_accepted_notes_are_short_and_never_cut():
    assert explain.MAX_CHARS <= 320 and explain.MAX_SENTENCES == 2
    long = "NVDA rose 48.2% over 12 months " + "and kept its place " * 20 + "."
    assert explain.clean(long).endswith(".")  # clean never cuts and never adds an ellipsis
    assert "…" not in explain.clean(long)


def test_numbers_in():
    assert explain.numbers_in("$1,850.00, 6.10%, +3, S01, F4, 12-1, 3rd, 0.50") == {"1850", "6.1", "3", "12", "1", "0.5"}


@pytest.mark.parametrize(
    ("name", "want"),
    [("A · Quant", "Quant"), ("F4 · Momentum", "Momentum"), ("C · News veto", "News veto"), ("SPY", "SPY")],
)
def test_plain_name(name, want):
    assert explain.plain_name(name) == want


@pytest.mark.parametrize(
    ("raw", "want"),
    [
        (None, ()),
        ([], ()),
        (["  a  b ", "", "c"], ("a b", "c")),
        ("a", ()),
        ([1, "a"], ()),
        ({"a": "b"}, ()),
    ],
)
def test_facts_from(raw, want):
    assert explain.facts_from(raw) == want


# Phase 1's exact fact shapes (strategies/evidence.py "Fact strings", real prototype output). A faithful
# note that restates them must pass vet: every number is extracted identically from facts and note, and
# no fact carries a BANNED word (the reconciled trend fact says "hold stocks", not "buy").
PHASE_ONE_FACTS = (
    ("It closed at $219.00, 1.9% above its 200-day average of $215.00.",
     "Its 2-day strength score was 1.1 out of 100; below 10 counts as a sharp short drop.",
     "Over the last 2 trading days it fell 2.6%, and over the last 5 it fell 2.4%.",
     "On an average day over the last 20 trading days, $224 million of its shares changed hands.",
     "It ranked 1st of 3 stocks that passed the rule that day, lowest strength score first."),
    ("Its price rose 60% from 12 months ago to 1 month ago.",
     "It ranked 1st of 5 stocks checked on that move, strongest first.",
     "SPY closed 9.8% above its 200-day average, so the method is allowed to hold stocks."),
    ("SPY closed at $1,231.40, 9.8% above its 200-day average of $1,121.50.",
     "The rule holds SPY while SPY closes above its 200-day average, so it holds SPY."),
    ("It ranked 1st of 5 companies checked on a combined score of 4 measures from its financial filings.",
     "Its net worth on its books is 623.4% of its stock-market value, the highest of the 5 companies checked.",
     "It earned 12.5% on its shareholders' money in its last fiscal year, the lowest of the 5 companies checked.",
     "Its latest quarterly earnings beat the same quarter a year earlier by 2.8 times the usual size of its "
     "earnings surprises, higher than 25% of the other companies checked.",
     "Its latest financial filing used here is 252 days old."),
)


@pytest.mark.parametrize("facts", PHASE_ONE_FACTS)
def test_phase_one_fact_shapes_pass_the_checks(facts):
    joined = " ".join(facts)
    assert not [b.label for b in explain.BANNED if b.pattern.search(joined)]
    for fact in facts:  # each fact restated verbatim is an acceptable note
        assert explain.vet(fact, facts) == fact
    assert explain.vet(f"{facts[0]} {facts[1]}", facts)  # and two of them together
    assert explain.numbers_in("$224 million, 3rd of 412, 200-day, $1,231.40, 6.1%") == {
        "224", "3", "412", "200", "1231.4", "6.1"
    }
```
**Impact:**
- The seed writes `orders.evidence` and `book_targets.evidence`, so the PG tests need phase 2's migration 009.
- `FakeClient` keeps its old constructor and default reply, so `test_paper_c.py` still imports and uses it unchanged.
- I checked the regexes: every accept and reject case above was run against a scratch copy of `vet` and gave the stated result.

### Step 3: Update C's explain test to the new prompt
**File:** `engine/tests/test_paper_c.py:490`
**Change:** the prompt names the method by its plain name. Replace the assertion line

```python
    assert sum("C · News veto" in p for p in client.prompts) == len(c_pending)
```
with
```python
    assert sum("Method: News veto," in p for p in client.prompts) == len(c_pending)
```
The other lines of `test_explain_fills_c_pending_orders_like_a` stay as they are. The `notes == {s: f"Paper note for {s}." ...}` check still holds: `"Paper note for S03."` has no number token, because the digits of a symbol like `S03` follow a letter, and it ends with `.`. That check is also the end-to-end proof that phase 2 stores evidence on every C pending order.
**Impact:** none beyond the single line. If phase 1 or phase 2 leaves a C order without evidence, this test fails, and it should.

### Step 4: Correct `llm.py` docstrings (no code change)
**File:** `engine/src/seer_engine/llm.py:10-16`
**Change:** replace the text from `` ``Client.complete(system, prompt)`` POSTs`` through `` (``explain``). Connection errors, timeouts, 429`` with:
```
``Client.complete(system, prompt)`` POSTs one non-streaming Messages request to
``messages_url(LLM_BASE_URL)`` and returns the reply's text. Optional keywords
``temperature``, ``thinking`` and ``max_tokens`` add ``"temperature"`` and
``"thinking": {"type": ...}`` to the body and override the client's ``max_tokens`` for that call
(Strategy C's veto and ``explain`` both pass all three, thinking disabled); without them the body
is exactly ``{model, max_tokens, system, messages}``. Connection errors, timeouts, 429
```
**File:** `engine/src/seer_engine/llm.py:166-172`
**Change:** replace the method docstring with:
```python
        """Send one user ``prompt`` under ``system`` and return the reply's text.

        ``temperature`` adds ``"temperature"`` to the body, ``thinking`` adds
        ``"thinking": {"type": thinking}`` (e.g. ``"disabled"``), and ``max_tokens`` replaces the
        client's default for this call. With none of them the body is exactly
        ``{model, max_tokens, system, messages}``.
        """
```
**Impact:** docstrings only. `test_llm.py::test_no_keywords_keeps_the_body_byte_identical` tests the client, not `explain`, and is unaffected.

### Step 5: Runbook, Explain
**File:** `docs/runbooks/paper-trading.md`

5a. Line 98, the night tree's last line becomes:
```
└─ Explain                   one or two plain sentences per new pick, from the evidence Paper stored
                             (C's included); replies are checked, a failing one stays NULL; never fails the night
```

5a'. (reconciled: phase 2's Paper step, documented here because this phase owns the runbook) After line 94
(`│                              F4/F1: targets on a month's first session → book_targets; SPY: hold)`), insert:
```
│                              → each decided symbol's evidence (strategies/evidence.py) stored with it
│                                (orders / book_targets / book_previews .evidence, migration 009); the idle
│                                symbol gets none; an evidence error logs "<id> <date>: no evidence stored
│                                tonight (…)", stores NULL and never changes a decision or fails the night
```

5b. Line 136, Commands table row becomes:
```
| `… -m seer_engine -v explain` | "why this pick" notes for new paper entries that have evidence and no note yet (see [Explain: why this pick](#explain-why-this-pick)) | `orders.explanation`, `book_targets.explanation` |
```

5c. Line 148, Exit codes row for `explain` becomes:
```
| `explain` | always, including when any `LLM_*` is unset or empty (logged "explanations unavailable", no database connection), an entry has no evidence (skipped), an entry's LLM call fails, or its reply fails the checks (text stays NULL) | only a database error (connection or SQL), which `cli.main` turns into 1; the workflow step is `continue-on-error` | `LLM_*` set but `DATABASE_URL_UNPOOLED` missing |
```

5d. Line 159, Failure states row becomes:
```
| Explain failed, `LLM_*` not set, or a reply failed the checks | text stays NULL | green (`continue-on-error`) | the stored facts instead of the note, or "explanation unavailable" when there are none | Owner step 1 when `LLM_*` is missing; otherwise nothing (the log line `explanation rejected for …` names the reason) |
```

5e. Insert a new section immediately before `## Health checks` (line 323):
````markdown
## Explain: why this pick

The last step of the night writes the "Why this pick" text for every new paper entry: A's and
C's new pending orders, and new targets of F4, F1 and FND (a symbol the strategy already
holds is a re-weight and is skipped).

**What it reads.** Only the entry's `evidence` (migration 009). Paper writes it at decision time,
from `strategies/evidence.py`. It is a short list of plain facts with their numbers, such as "Its
price rose 48.2% from 12 months ago to 1 month ago." or "It ranked 3rd of 412 stocks checked on that
move, strongest first." The
prompt is the method's plain name ("Momentum", not "F4 · Momentum"), the stock symbol, those facts,
and the task: "in at most 2 short plain sentences, say why this method picked this stock, using only
these facts". There are no order prices, no share counts, no rule text and no "this is a paper trade"
(the site already labels everything **paper**). An entry with no evidence (NULL or an empty
list: written before 009, the idle symbol, or a night whose evidence function raised — Paper's log
then has `<strategy> <date>: no evidence stored tonight (…)`) is skipped and its text stays NULL.

**Why thinking is disabled.** The call is `temperature=0.0, thinking="disabled",
max_tokens=1024`, the same settings Veto uses. Before this, `glm-5.3` thought by default on a
400-token budget. Reasoning used up the budget, so the text stopped mid-sentence ("This is a paper
trade simulated by the Seer") or came back empty (NULL). Temperature 0 keeps the note a
restatement of the facts.

**The checks.** Every reply must pass all of these, or it is discarded (logged as
`explanation rejected for <strategy> <symbol>: <reason>`), and the text stays NULL:
- a complete sentence: it ends with `.`, `!` or `?`, and it has no `…` or `...`;
- at most 2 sentences and at most 320 characters. Nothing is ever cut, and no ellipsis is added;
- every number in the reply also appears in the facts. Before comparing, `$`, `,`, `%` and signs
  are removed and trailing zeros dropped, so `$1,850.00` matches `1850`. The digits of a ticker
  such as `S01` are not numbers. Numbers spelled out in words are not checked;
- no advice or prediction phrase: buy, sell, recommend, should, "will" with a price move (rise,
  fall, go up, ...), going to, expect, guarantee. Matches are whole words, so "buyback" and
  "unexpected" pass. "expect" is allowed only when the facts themselves use it (a past
  earnings result);
- not the same text as a note already accepted for the same strategy that night.

**Failures.** A call that raises (timeout, 5xx, a client bug) leaves that text NULL. After 3
calls in a row raise, no more calls are made that night. A rejected reply is not an outage,
because the LLM answered: it does not count toward the 3, and it resets the count. Explain
always exits 0 unless the database fails.

**Old entries.** Entries written before the evidence pipeline shipped have no evidence. They stay
as they are and are not re-explained. New entries get notes from the next night on.
````
**Impact:** docs only.

### Step 6: Engine package README, evidence → explain overview
**File:** `engine/package_readme.md`

6a. Line 30 (Overview, the "Nightly paper trading" bullet): replace `optionally explained by an LLM (`explain`).` with
```
each new pick stored with its evidence (the plain facts its formula used, `strategies/evidence.py`, migration 009) and optionally explained from that evidence by an LLM (`explain`).
```

6b. After line 97 (`f_swing.py …` in the Layout tree), insert:
```
      evidence.py           per-pick evidence (why-this-pick-pipeline phase 1): EVIDENCE keyed by paper.roster.RESOLVER name -> (market, params, data_date, symbols) -> {symbol: plain facts}; evidence_for(), has_evidence(). Pure; never read by any decision
```

6c. Lines 504-510, `### \`explain\` (P4)` section body (keep the heading and usage block). Replace the paragraph with:
```
"Why this pick" notes (D9) for new paper entries without one: `orders.explanation` for A's and C's new pending orders, `book_targets.explanation` for new (not already held) targets of the latest decision. The prompt is the entry's stored `evidence` (migration 009) and the method's plain name (`plain_name("F4 · Momentum") == "Momentum"`), nothing else. An entry with NULL or empty evidence is skipped. The call is `complete(SYSTEM, prompt, temperature=0.0, thinking="disabled", max_tokens=EXPLAIN_MAX_TOKENS)` (1024). Every reply passes `vet(reply, facts, earlier)` or is discarded (logged with the reason, text stays NULL): `clean` (markdown, bullet and wrapping quotes removed, whitespace collapsed, never cut), ends with `.`/`!`/`?`, no ellipsis, at most `MAX_SENTENCES = 2` sentences and `MAX_CHARS = 320` characters, no `BANNED` phrase (advice or prediction, word-bounded), every `numbers_in(text)` within `numbers_in(facts)` (normalized: `$ , % +` dropped, trailing zeros removed; ticker digits are not numbers), and not equal (case-folded) to a note already accepted for the same strategy tonight. `accept(...)` is the same check returning `str | None`. Only calls that raise count toward `MAX_CONSECUTIVE_FAILURES = 3`; a rejection resets the count. Missing or empty `LLM_*` settings leave every text NULL and exit 0. Paper correctness never depends on it. Exit 1 only on a database error; 2 when `LLM_*` is set but `DATABASE_URL_UNPOOLED` is missing.
```

6d. Line 1970 (`### llm (P4)` Client bullet). Replace `` `explain` calls it with no keywords, and its request body is byte-identical to P4's; `veto` (P6) passes `` with `` `veto` (P6) and `explain` (why-this-pick-pipeline) both pass ``, so the sentence reads: "... `veto` (P6) and `explain` (why-this-pick-pipeline) both pass `temperature=0.0`, `thinking="disabled"` (sent as `{"type": "disabled"}`) and `max_tokens=1024`, because `glm-5.3` with a small budget spends it on reasoning and returns no text."

6e. Insert a new section immediately before `## Data Flow` (line 2047):
```markdown
## Migration 009 (`db/migrations/009_evidence.sql`, why-this-pick-pipeline phase 2)

Additive only: `evidence jsonb` (nullable) on `orders`, `book_targets` and `book_previews`. The value is a JSON array of plain-English strings, the facts the method's formula used on that symbol the night it was decided. NULL means no evidence: rows written before 009, the idle symbol, or a night whose evidence function raised (Paper logs it and still stores the decision). `paper/store.py` writes it through keyword-only `evidence=` arguments of `insert_pending_orders`, `save_book_decision` and `save_book_preview`. It never enters `paper.replay.Records` or `compare`, so `paper_check` is unaffected. Readers: `explain` (orders, book_targets) and the web (all three, through `to_jsonb(row) -> 'evidence'` so a query also works before 009 is applied).
```

6f. Insert a new Usage subsection immediately before `### Strategy C: the news check (P6)` (line 2274):
````markdown
### Why this pick: evidence → explain (why-this-pick-pipeline)

How a pick gets its "Why this pick" text, end to end:

1. **Evidence (pure, phase 1).** `strategies/evidence.py` has one function per `paper.roster.RESOLVER` name (`STRATEGY_A`, `STRATEGY_C`, `FACTOR`, `TIMING`, `FUNDAMENTAL`; the benchmark has none). Each one, `(market, params, data_date, symbols) -> {symbol: facts}`, recomputes the numbers the formula ranked on, such as a 2-day strength score, the distance from the 200-day average, 12-month momentum and its rank among eligible stocks, or filed fundamentals compared with the eligible set. It returns them as 2–6 plain sentences with the numbers already formatted. It reads nothing dated after `data_date`, and it never touches a params class, so no roster digest moves.
2. **Storage (Paper, phase 2).** At decision time `commands/paper.py` calls the evidence function on the decision's own market view for the decided symbols. Any exception gives NULL for that night. The facts go into `orders.evidence`, `book_targets.evidence` and `book_previews.evidence` (migration 009). The decisions themselves are byte-for-byte unchanged.
3. **Explanation (Explain, phase 3).** `explain` sends the method's plain name, the symbol and the stored facts, with thinking disabled. It keeps a reply only if `vet` passes: 2 complete sentences at most, ≤ 320 characters, every number taken from the facts, no advice or prediction words, and no copy of another note for the same strategy that night. Otherwise the text stays NULL.
4. **Display (web, phase 5).** "Why this pick" shows the note. When the note is NULL but there is evidence, it shows the facts as a short list. It says "unavailable" only when both are missing. "Would pick now" rows show their facts, with no LLM. C keeps its "Why it passed the news check" line.
5. **Promotion (phase 4).** `promote` refuses a lab method whose allocator has no `EVIDENCE` entry.

```
cd <repo or worktree root>
SEER_ENV_FILE=/home/miftah/seer/.env.local engine/.venv/bin/python -m seer_engine --dry-run -v explain   # real LLM calls, rolled back
```
````

6h. (reconciled: phase 4's behaviour, documented here because this phase owns the file) Line 540,
the `promote` section's first bullet: replace `**Promotable means two things**, and anything that is
not both is refused.` with `**Promotable means three things**, and anything that is not all three is
refused.`, and append to the end of that bullet: ` (3) That name has an entry in
\`strategies.evidence.EVIDENCE\` (\`_check_evidence\`, checked right after the name is resolved and
before any write, dry-run included): a strategy that cannot say, per pick, which numbers its formula
used would show picks on the site with no reason, so it is refused with one line naming
\`seer_engine/strategies/evidence.py\` and \`EVIDENCE\`.`

6g. Line 2397 (Notes): replace the bullet `` - `explain` must never decide anything: it writes text only, and a failure leaves NULL. `` with:
```
- `explain` must never decide anything: it writes text only, and a failure leaves NULL. It reads only stored evidence. Never add order mechanics, rule text or anything outside the facts to its prompt, and never loosen `vet` to let a reply through: a NULL note shows the facts on the site, while a wrong note shows advice the facts do not support.
```
**Impact:** docs only.

## Verification

**Build:** `cd /home/miftah/.worktrees/seer/why-this-pick-pipeline && engine/.venv/bin/ruff check engine`
**Tests:** `docker start seer-pg` and then
`cd /home/miftah/.worktrees/seer/why-this-pick-pipeline && PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q`.
This must pass except for the two known Python-3.12-only failures (`test_f_fundamental.py::test_allocator_shape`, `test_market_fundamentals.py::test_adding_the_hook_does_not_change_the_allocator_check`). Run `engine/tests/test_explain.py`, `engine/tests/test_paper_c.py`, `engine/tests/test_paper_evidence.py` and `engine/tests/test_llm.py` first for a fast loop. Then `cd web && npx vitest run && npx tsc --noEmit` (unaffected by this phase, still part of invariant 1). Use the worktree's own `engine/.venv` and `web/node_modules`, never main's.
**Manual check:**
- Optionally, against the real LLM: `SEER_ENV_FILE=/home/miftah/seer/.env.local engine/.venv/bin/python -m seer_engine --dry-run -v explain`. Read the `explanation rejected …` lines and the final count line. It needs Neon to have 009 and at least one night of evidence, so it can only be run after phase 2 has shipped.
- `grep -n "…" engine/src/seer_engine/commands/explain.py`: the only hits are the ellipsis-rejection check and the docstring, never an appended "…".
**Exit criteria:**
- The prompt is built only from the plain name, the symbol and the stored evidence.
- Every call passes `temperature=0.0`, `thinking="disabled"` and `max_tokens=1024`.
- `vet` rejects invented numbers, cut-off text, more than 2 sentences, more than 320 characters, banned phrases and same-strategy duplicates.
- No "…" is ever written.
- Entries without evidence are skipped and never sent.
- A rejection does not count toward the consecutive-failure stop.
- `execute` and `run` always return 0 except on a database error.
- The full engine test suite and ruff are green.

## Handoffs

- **Phase 2:** `book_previews.evidence` is not read by Explain (plan decision: previews get facts only, no LLM text). Nothing to do. Recorded so the reconciler does not expect a preview path here.
- **Phase 2:** `test_paper_c.py::test_explain_fills_c_pending_orders_like_a` now proves C orders carry evidence after a paper night. If phase 2's helper leaves C rows NULL on the synthetic `S00…S23` world (for example, phase 1's STRATEGY_C function returns nothing on that sawtooth), this test fails here. The fix belongs in phase 1 or 2, not in Explain. **Reconciler:** `test_paper_c.py` is on no phase's ownership list, and this phase edits line 490 only.
- **Phase 5 (R5, R6):** the facts fallback when `explanation` is NULL, and the "would pick now" facts. Explain deliberately leaves rejected notes NULL so that fallback shows instead.
- **Phase 1 (R1, R8):** fact wording should avoid the `BANNED` words. "buy", "sell", "should", "expect" (unless a past result), "will …" and "going to" in a fact are allowed in the prompt, but the LLM echoing them gets the note rejected. Facts should write each number the way the note should show it (e.g. "48.2%"), because the LLM is told to copy numbers exactly and rounding ("48%") is rejected.
- **No phase:** `llm.DEFAULT_MAX_TOKENS = 400` stays. Neither caller relies on it any more. Lowering or removing it is a cleanup for a later card.

## Rollback

Revert this phase's commit. `explain.py` goes back to the order-mechanics prompt, and the tests, the `test_paper_c` line, the `llm.py` docstrings and the docs revert with it. Nothing in the database changes: the `evidence` columns (phase 2) are simply not read, and notes already written stay.

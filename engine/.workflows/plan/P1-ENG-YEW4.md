> Adopted from `PAPER_TRADING_SHIP_PLAN.md` phase 9. Source: `.workflows/plan/paper-trading-ship/phase-9.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 9: explain: optional LLM explanations

**Plan set:** `PAPER_TRADING_SHIP_PLAN.md`
**Analysis:** `20261004-082027-P4S7_code_analyzer.md`
**Satisfies:** R5 — every new paper entry gets a short plain-language note when `LLM_*` is configured; otherwise the note stays empty ("unavailable") and nothing else is affected
**Depends on:** Phase 1 (migration 003: `strategies.engine`, `strategies.rules_id`, `paper_state`, `book_targets.explanation`, `book_positions`, the roster rows)
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine` (`llm.py`, `commands/explain.py`)

---

## Goal

After this phase, `python -m seer_engine [--dry-run] explain` finds the newest paper entries and
writes an explanation for each one. Entries are the pending bracket orders and the new book targets
for each roster strategy's `paper_state.pending_session` whose `explanation IS NULL`. Each
explanation is ≤ 3 plain-language sentences built only from stored numbers, and comes from an
Anthropic-compatible Messages API (`llm.py`). A missing `LLM_*` config, any LLM error or an empty
reply leaves the explanation NULL, and the command still exits 0. Paper correctness never depends on
this step (D9, design §8: "LLM fails → explanation 'unavailable'").

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.
**Creates:**
- `seer_engine.llm` (`engine/src/seer_engine/llm.py`): `LlmError`, `LlmConfig` (frozen; `api_key` excluded from repr), `load_config() -> LlmConfig | None`, `messages_url(base_url) -> str`, `scrub(text, secret) -> str`, `Transport` (Protocol: `post(url, *, headers, json, timeout)`), `Client(cfg, *, transport=None, timeout=20.0, retries=1, backoff=2.0, max_tokens=400, sleep=time.sleep)` with `.complete(system, prompt) -> str` and `.model`, constants `ANTHROPIC_VERSION = "2023-06-01"`, `DEFAULT_TIMEOUT_S`, `DEFAULT_RETRIES`, `DEFAULT_BACKOFF_S`, `DEFAULT_MAX_TOKENS`.
- `seer_engine.commands.explain` (`engine/src/seer_engine/commands/explain.py`): CLI command `explain` (`HELP`, `run(args)`), `execute(conn, *, client, dry_run=False) -> int`, `load_batches(conn)`, `prompt_for(entry) -> str`, `clean(text) -> str | None`, `SYSTEM`, `MAX_CONSECUTIVE_FAILURES = 3`, `MAX_CHARS = 600`, dataclasses `StrategyRow`, `BracketEntry`, `BookEntry`, Protocol `Completer`.
- Tests: `engine/tests/test_llm.py`, `engine/tests/test_explain.py`.

**Signature changes:** none.
**Requires (from earlier phases):**
- Phase 1, migration `003_paper.sql` (C1) exactly as follows. `strategies.engine` is in (`bracket`, `book`, `benchmark`) and `strategies.rules_id` is `design-v0` or `monthly-hold`. `paper_state(strategy_id, last_session, cash_usd, equity_usd, initial_cash_usd, usd_idr, pending_session, pending_decision)` exists. `book_targets(strategy_id, session_date, rank, symbol, weight, last_price, limit_price, stop_price, take_price, explanation)` exists. `book_positions(strategy_id, symbol, shares, mark, entry_date, entry_price, days_held, cost_usd, income_usd, …)` exists. The roster rows (`SPY`, `A`, `F4-MOM12-N20-TREND`, `F1-SPY-SMA200-M`) with `name`, `sub`, `engine`, `rules_id` are inserted by the migration.
- `orders.explanation` (001, unchanged).
- At run time (not at test time): phase 7's `paper` writes `paper_state.pending_session`, the pending `orders` of `A` for that session and the `book_targets` of book strategies for it. This phase only reads those rows and updates their `explanation`. It never inserts rows and never changes any other column.

**Leaves alone (owned by others):**
- `commands/paper.py`, `paper/*` (phases 1, 3, 4, 6, 7).
- `.github/workflows/nightly.yml` and the runbook. Phase 13 adds the "Explain" step (`continue-on-error: true`, env `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` from repo secrets) and the owner step for those secrets.
- `web/*` (phase 11 shows `explanation` with `WhyToggle`).
- `docs/*`, `engine/package_readme.md` (phase 13).
- `http.py`: reused by import (`http.redact`), not edited.
- `sim/rules.py`: `PRESETS` and `describe_rules` are reused by import, not edited.

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/llm.py` | create (whole file, line 1) | Minimal Anthropic-compatible Messages client with an injectable transport, a short timeout, one retry and redacted errors |
| `engine/src/seer_engine/commands/explain.py` | create (whole file, line 1) | The `explain` command: finds the entries, builds prompts, calls the LLM, writes updates in one transaction per strategy |
| `engine/tests/test_llm.py` | create (whole file, line 1) | Fake-transport tests: request shape, URL rules, retry, timeout, no retry on 4xx, redaction, config loading |
| `engine/tests/test_explain.py` | create (whole file, line 1) | PG tests on seeded 003 rows: fills NULLs of the latest entries only, re-run is a no-op, failure leaves NULL with exit 0, the circuit breaker, dry-run, missing config exits 0 without a DB, CLI end to end |

No existing file is modified. `cli.discover()` picks up `commands/explain.py` automatically
(`cli.py` docstring: "Adding a command means adding a module; this file never changes").

## Design notes (decisions made here)

1. **Endpoint.** `.env.example` lists `LLM_BASE_URL`, `LLM_API_KEY` and `LLM_MODEL`, and design §3
   says "GLM via z.ai (Anthropic-compatible endpoint)". The z.ai base URL is the one Anthropic SDKs
   take (`https://api.z.ai/api/anthropic`), and the SDK appends `/v1/messages`. `messages_url`
   therefore appends `/v1/messages` to the base URL. If the base already ends in `/v1`, it appends
   only `/messages`. If the base already ends in `/v1/messages`, it uses it as is. So any of the
   three ways an owner might write the secret works.
2. **Headers.** `x-api-key: <key>` **and** `Authorization: Bearer <key>` (z.ai compatibility:
   its Anthropic-compatible endpoint is driven by `ANTHROPIC_AUTH_TOKEN`, which is sent as a
   bearer token; Anthropic-style endpoints read `x-api-key`), plus `anthropic-version: 2023-06-01`,
   `content-type: application/json` and a `user-agent`. Sending both is the reconciled decision
   (plan index Decisions, "LLM auth"); neither header is ever logged.
3. **Timeouts and retries.** A 20 s timeout per request. One retry for connection errors, timeouts,
   429 and 5xx, with a 2 s backoff. Any other non-200 status fails at once. Worst case is about 42 s
   per entry.
4. **Circuit breaker.** After `MAX_CONSECUTIVE_FAILURES = 3` failed entries in a row, the command
   stops calling the LLM for the rest of the night. Those entries stay NULL. This keeps an
   unreachable endpoint from adding minutes to the job. At most about 25 entries exist per night
   (A ≤ 4, F4 ≤ 20, F1 ≤ 1).
5. **Redaction.** Every `LlmError` message goes through `scrub`: `http.redact` (key/token query
   parameters), then a literal replace of the API key with `REDACTED`. Response bodies are cut to
   200 characters before scrubbing. The key is never logged, and `repr(LlmConfig)` and
   `repr(Client)` omit it.
6. **Which entries.** For each strategy with `engine IN ('bracket','book')` and a `paper_state` row
   whose `pending_session` is set, only rows for that `pending_session` are used:
   - bracket: `orders` with `status = 'pending'` and `explanation IS NULL`;
   - book: `book_targets` with `explanation IS NULL` whose symbol is **not** in that strategy's
     `book_positions`, so only new entries count, not re-weights of holdings.

   The SPY benchmark (`engine = 'benchmark'`) has no entries. Older sessions are never touched, so a
   backlog never builds up after an outage.
7. **Prompt.** Built from stored numbers only:
   - strategy name and sub, session date, symbol (and company for bracket orders);
   - last close;
   - bracket: limit/TP/SL/shares and the estimated cost (`limit × shares`);
   - book: rank, weight, last close, and limit/stop/take when set;
   - the rule text from `sim.rules.describe_rules(PRESETS[rules_id])`;
   - the statement that it is PAPER ONLY, not a recommendation to buy, with no real money.

   The task asks for ≤ 3 short sentences, no predictions, no advice and no markdown. The reply is
   cleaned (whitespace collapsed, capped at 600 characters). An empty reply counts as a failure.
8. **Transactions.** The rows are read in one short read transaction, which is closed
   (`conn.rollback()`) before any LLM call, so no transaction stays open across network calls. Each
   strategy's explanations are then written in their own `db.transaction(conn, dry_run)`. Each
   update is guarded by `explanation IS NULL`, so it never overwrites a note. `--dry-run` makes the
   reads and the LLM calls and runs the UPDATEs, then rolls back.
9. **Exit codes.**
   - Missing config: logs "explanations unavailable: …", returns 0, and never opens a DB connection.
   - Any per-entry exception (the LLM, or a non-LLM bug in the client): caught; the entry stays
     NULL; the command returns 0.
   - Database errors (connection or SQL) are not swallowed. `cli.main` turns them into exit 1, and
     phase 13's `continue-on-error` keeps the night green. Hiding a broken schema behind exit 0 would
     be dishonest reporting.

## Implementation Steps

### Step 1: The LLM client
**File:** `engine/src/seer_engine/llm.py:1` (new)
**Change:** create the module.
**Code:**
```python
"""Minimal Anthropic-compatible Messages API client for optional explanations (design §4, D9).

Configured by three environment variables (see ``.env.example``):

    LLM_BASE_URL   the provider's Anthropic-compatible base URL, e.g. https://api.z.ai/api/anthropic
    LLM_API_KEY    sent as both ``x-api-key`` and ``Authorization: Bearer`` (z.ai
                   compatibility), never logged
    LLM_MODEL      the model id passed in the request body

``Client.complete(system, prompt)`` POSTs one non-streaming Messages request to
``messages_url(LLM_BASE_URL)`` and returns the reply's text. Connection errors, timeouts, 429
and 5xx are retried ``retries`` times; any other failure raises ``LlmError`` at once. Every
error message is scrubbed of the API key and of key/token query parameters.

The transport is injectable (anything with ``post(url, *, headers, json, timeout)`` returning a
requests-like response), so tests never touch the network. Callers treat every ``LlmError`` as
"explanation unavailable": nothing in the paper step depends on this module.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

import requests

from seer_engine import __version__, config, http

log = logging.getLogger(__name__)

ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_TIMEOUT_S = 20.0
DEFAULT_RETRIES = 1
DEFAULT_BACKOFF_S = 2.0
DEFAULT_MAX_TOKENS = 400
MAX_ERROR_BODY = 200


class LlmError(RuntimeError):
    """An LLM request failed (after retries), or its reply held no text."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class LlmConfig:
    base_url: str
    api_key: str = field(repr=False)
    model: str


class Transport(Protocol):
    def post(self, url: str, *, headers: dict[str, str], json: dict[str, Any], timeout: float) -> Any: ...


def load_config() -> LlmConfig | None:
    """The LLM settings, or None when any of LLM_BASE_URL, LLM_API_KEY, LLM_MODEL is unset or empty."""
    base_url = config.get("LLM_BASE_URL")
    api_key = config.get("LLM_API_KEY")
    model = config.get("LLM_MODEL")
    if base_url is None or api_key is None or model is None:
        return None
    base_url, api_key, model = base_url.strip(), api_key.strip(), model.strip()
    if not (base_url and api_key and model):
        return None
    return LlmConfig(base_url=base_url, api_key=api_key, model=model)


def messages_url(base_url: str) -> str:
    """The Messages endpoint for ``base_url``.

    ``https://h/api/anthropic`` -> ``https://h/api/anthropic/v1/messages`` (what Anthropic SDKs do
    with a base URL); a base already ending in ``/v1`` gains ``/messages``; one already ending in
    ``/v1/messages`` is used as is.
    """
    base = base_url.strip().rstrip("/")
    if base.endswith("/v1/messages"):
        return base
    if base.endswith("/v1"):
        return f"{base}/messages"
    return f"{base}/v1/messages"


def scrub(text: str, secret: str | None) -> str:
    """``text`` with key/token query parameters and every occurrence of ``secret`` redacted."""
    out = http.redact(text)
    if secret:
        out = out.replace(secret, "REDACTED")
    return out


def _reply_text(resp: Any) -> str:
    """The concatenated text blocks of a Messages reply; LlmError when there are none."""
    try:
        data = resp.json()
    except ValueError as exc:
        raise LlmError("non-JSON reply from the LLM endpoint", resp.status_code) from exc
    if not isinstance(data, dict):
        raise LlmError("expected a JSON object from the LLM endpoint", resp.status_code)
    content = data.get("content")
    parts: list[str] = []
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str):
                parts.append(block["text"])
    text = " ".join(p.strip() for p in parts if p.strip())
    if not text:
        raise LlmError(f"no text in the LLM reply (stop_reason={data.get('stop_reason')!r})", resp.status_code)
    return text


def _default_transport() -> Transport:
    session = requests.Session()
    session.headers["User-Agent"] = f"seer-engine/{__version__}"
    return session


class Client:
    """One Anthropic-compatible Messages endpoint; ``complete`` is the only call."""

    def __init__(
        self,
        cfg: LlmConfig,
        *,
        transport: Transport | None = None,
        timeout: float = DEFAULT_TIMEOUT_S,
        retries: int = DEFAULT_RETRIES,
        backoff: float = DEFAULT_BACKOFF_S,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._cfg = cfg
        self._url = messages_url(cfg.base_url)
        self._transport = transport if transport is not None else _default_transport()
        self._timeout = timeout
        self._retries = retries
        self._backoff = backoff
        self._max_tokens = max_tokens
        self._sleep = sleep

    @property
    def model(self) -> str:
        return self._cfg.model

    def __repr__(self) -> str:
        return f"Client(url={self._url!r}, model={self._cfg.model!r})"

    def complete(self, system: str, prompt: str) -> str:
        """Send one user ``prompt`` under ``system`` and return the reply's text."""
        headers = {
            "x-api-key": self._cfg.api_key,
            "authorization": f"Bearer {self._cfg.api_key}",
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
            "user-agent": f"seer-engine/{__version__}",
        }
        body: dict[str, Any] = {
            "model": self._cfg.model,
            "max_tokens": self._max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
        }
        attempt = 0
        while True:
            attempt += 1
            status: int | None = None
            try:
                resp = self._transport.post(self._url, headers=headers, json=body, timeout=self._timeout)
            except requests.RequestException as exc:
                message = f"{type(exc).__name__}: {exc}"
                retryable = True
            else:
                status = resp.status_code
                if status == 200:
                    try:
                        return _reply_text(resp)
                    except LlmError as exc:
                        raise LlmError(scrub(str(exc), self._cfg.api_key), status) from None
                message = f"HTTP {status} from the LLM endpoint: {str(resp.text)[:MAX_ERROR_BODY]}"
                retryable = status == 429 or status >= 500
            message = scrub(message, self._cfg.api_key)
            if not retryable or attempt > self._retries:
                raise LlmError(message, status)
            delay = self._backoff * (2 ** (attempt - 1))
            log.warning("LLM call failed (%s); retry %d/%d in %.1fs", message, attempt, self._retries, delay)
            self._sleep(delay)
```
**Impact:** a new module with no callers outside phase 9. `requests` is already a dependency
(`engine/pyproject.toml`). Nothing imports it at CLI start-up except through `commands/explain.py`.

### Step 2: The `explain` command
**File:** `engine/src/seer_engine/commands/explain.py:1` (new)
**Change:** create the command module. `cli.discover()` registers it as `explain`.
**Code:**
```python
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
```
**Impact:** adds the `explain` subcommand. Under `--dry-run`, `written` counts the updates of the
rolled-back transactions, and the log says so through `db.transaction`'s "dry-run: transaction
rolled back" line. No module-level side effects. It does not take `--now`: the latest
`pending_session` is read from `paper_state`, not computed from the clock.

### Step 3: LLM client tests
**File:** `engine/tests/test_llm.py:1` (new)
**Code:**
```python
"""The Anthropic-compatible Messages client: request shape, retries, timeouts, redaction (no network)."""

from __future__ import annotations

import pytest
import requests

from seer_engine import llm

KEY = "sk-test-SECRET-123"
CFG = llm.LlmConfig(base_url="https://llm.test/api/anthropic", api_key=KEY, model="glm-test")


class _Resp:
    def __init__(self, status: int, body=None, text: str | None = None):
        self.status_code = status
        self._body = body
        self.text = text if text is not None else ("" if body is None else str(body))
        self.headers: dict[str, str] = {}

    def json(self):
        if self._body is None:
            raise ValueError("no json")
        return self._body


class FakeTransport:
    def __init__(self, *items):
        self.queue = list(items)
        self.calls: list[dict] = []

    def post(self, url, *, headers, json, timeout):
        self.calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        item = self.queue.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


def ok(text: str = "A paper note.") -> _Resp:
    return _Resp(200, {"content": [{"type": "text", "text": text}], "stop_reason": "end_turn"})


def make(transport: FakeTransport, sleeps: list[float] | None = None, **kw) -> llm.Client:
    return llm.Client(CFG, transport=transport, sleep=(sleeps if sleeps is not None else []).append, **kw)


def test_messages_url_forms():
    assert llm.messages_url("https://api.z.ai/api/anthropic") == "https://api.z.ai/api/anthropic/v1/messages"
    assert llm.messages_url("https://api.z.ai/api/anthropic/") == "https://api.z.ai/api/anthropic/v1/messages"
    assert llm.messages_url("https://api.anthropic.com/v1") == "https://api.anthropic.com/v1/messages"
    assert llm.messages_url("https://h.test/v1/messages") == "https://h.test/v1/messages"


def test_load_config_needs_all_three(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://llm.test")
    monkeypatch.setenv("LLM_API_KEY", KEY)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    assert llm.load_config() is None
    monkeypatch.setenv("LLM_MODEL", "   ")
    assert llm.load_config() is None
    monkeypatch.setenv("LLM_MODEL", "glm-test")
    assert llm.load_config() == llm.LlmConfig("https://llm.test", KEY, "glm-test")


def test_key_never_in_repr():
    assert KEY not in repr(CFG)
    assert KEY not in repr(make(FakeTransport()))


def test_complete_posts_one_messages_request():
    t = FakeTransport(ok("Hello there."))
    assert make(t).complete("sys text", "user text") == "Hello there."
    [call] = t.calls
    assert call["url"] == "https://llm.test/api/anthropic/v1/messages"
    assert call["headers"]["x-api-key"] == KEY
    assert call["headers"]["authorization"] == f"Bearer {KEY}"
    assert call["headers"]["anthropic-version"] == llm.ANTHROPIC_VERSION
    assert call["headers"]["content-type"] == "application/json"
    assert call["timeout"] == llm.DEFAULT_TIMEOUT_S
    assert call["json"] == {
        "model": "glm-test",
        "max_tokens": llm.DEFAULT_MAX_TOKENS,
        "system": "sys text",
        "messages": [{"role": "user", "content": "user text"}],
    }


def test_joins_text_blocks_and_ignores_others():
    body = {
        "content": [
            {"type": "thinking", "thinking": "hidden"},
            {"type": "text", "text": " First. "},
            {"type": "text", "text": "Second."},
        ]
    }
    assert make(FakeTransport(_Resp(200, body))).complete("s", "p") == "First. Second."


def test_reply_without_text_raises():
    t = FakeTransport(_Resp(200, {"content": [], "stop_reason": "max_tokens"}))
    with pytest.raises(llm.LlmError, match="no text"):
        make(t).complete("s", "p")


def test_non_json_reply_raises():
    with pytest.raises(llm.LlmError, match="non-JSON"):
        make(FakeTransport(_Resp(200, None, text="<html>"))).complete("s", "p")


def test_retries_5xx_and_429_then_succeeds():
    sleeps: list[float] = []
    t = FakeTransport(_Resp(503, text="busy"), ok("Done."))
    assert make(t, sleeps).complete("s", "p") == "Done."
    assert len(t.calls) == 2 and sleeps == [llm.DEFAULT_BACKOFF_S]

    sleeps2: list[float] = []
    t2 = FakeTransport(_Resp(429, text="slow down"), _Resp(429, text="slow down"), ok("Done."))
    assert make(t2, sleeps2, retries=2).complete("s", "p") == "Done."
    assert sleeps2 == [llm.DEFAULT_BACKOFF_S, llm.DEFAULT_BACKOFF_S * 2]


def test_timeout_is_retried_then_raises():
    sleeps: list[float] = []
    t = FakeTransport(requests.Timeout("read timed out"), requests.Timeout("read timed out"))
    with pytest.raises(llm.LlmError, match="Timeout") as exc:
        make(t, sleeps, timeout=1.5).complete("s", "p")
    assert exc.value.status is None
    assert len(t.calls) == 2 and all(c["timeout"] == 1.5 for c in t.calls)
    assert sleeps == [llm.DEFAULT_BACKOFF_S]


def test_4xx_is_not_retried_and_the_key_is_redacted():
    sleeps: list[float] = []
    t = FakeTransport(_Resp(401, text=f'{{"error": "invalid key {KEY}"}}'))
    with pytest.raises(llm.LlmError) as exc:
        make(t, sleeps).complete("s", "p")
    assert exc.value.status == 401
    assert KEY not in str(exc.value) and "REDACTED" in str(exc.value)
    assert len(t.calls) == 1 and sleeps == []


def test_connection_error_text_is_redacted(caplog):
    t = FakeTransport(
        requests.ConnectionError(f"https://llm.test/x?api_key={KEY} refused"),
        requests.ConnectionError(f"failed with {KEY}"),
    )
    with pytest.raises(llm.LlmError) as exc:
        make(t).complete("s", "p")
    assert KEY not in str(exc.value)
    assert KEY not in caplog.text


def test_scrub():
    assert llm.scrub(f"a {KEY} b ?token=xyz", KEY) == "a REDACTED b ?token=REDACTED"
    assert llm.scrub("plain", None) == "plain"
```
**Impact:** none on other tests. The autouse `_isolated_env` fixture already keeps `.env.local` out
of the process. `monkeypatch` restores `LLM_*`.

### Step 4: `explain` command tests on Postgres
**File:** `engine/tests/test_explain.py:1` (new)
**Code:**
```python
"""explain: fills explanations of the newest paper entries only, and never fails the night (PG)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from seer_engine import cli, llm
from seer_engine.commands import explain

LAST = date(2026, 10, 30)
NEXT = date(2026, 11, 2)
OLD = date(2026, 10, 1)
F4 = "F4-MOM12-N20-TREND"
F1 = "F1-SPY-SMA200-M"


class FakeClient:
    def __init__(self, fail_on: set[str] | None = None, fail_all: bool = False):
        self.fail_on = fail_on or set()
        self.fail_all = fail_all
        self.prompts: list[str] = []

    def complete(self, system: str, prompt: str) -> str:
        self.prompts.append(prompt)
        symbol = next(line for line in prompt.splitlines() if line.startswith("- Symbol: "))
        if self.fail_all or any(f"- Symbol: {s}" in symbol for s in self.fail_on):
            raise llm.LlmError("HTTP 503 from the LLM endpoint: busy", 503)
        return f"  Paper note\n for {symbol[len('- Symbol: '):].split()[0].rstrip('.')}.  "


def seed(pg) -> None:
    """Rows as `paper` (phase 7) would leave them after deciding session NEXT."""
    for sid in ("SPY", "A", F4, F1):
        pg.execute(
            "INSERT INTO paper_state (strategy_id, last_session, cash_usd, equity_usd, initial_cash_usd,"
            " usd_idr, pending_session, pending_decision) VALUES (%s, %s, 1000, 1000, 1200, 16500, %s, %s)",
            (sid, LAST, NEXT, sid in (F4, F1)),
        )
    order_sql = (
        "INSERT INTO orders (strategy_id, session_date, slot, symbol, company, last_price, limit_price,"
        " tp_price, sl_price, shares, explanation, status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
    )
    pg.execute(order_sql, ("A", NEXT, 1, "AAPL", "Apple Inc.", 190, 185, 195, 180, 10, None, "pending"))
    pg.execute(order_sql, ("A", NEXT, 2, "MSFT", "Microsoft", 400, 390, 410, 380, 2, "kept", "pending"))
    pg.execute(order_sql, ("A", LAST, 3, "KO", "Coca-Cola", 60, 59, 61, 58, 30, None, "open"))
    target_sql = (
        "INSERT INTO book_targets (strategy_id, session_date, rank, symbol, weight, last_price, limit_price)"
        " VALUES (%s,%s,%s,%s,%s,%s,%s)"
    )
    pg.execute(target_sql, (F4, NEXT, 1, "NVDA", Decimal("0.05"), 120, Decimal("122.40")))
    pg.execute(target_sql, (F4, NEXT, 2, "AAPL", Decimal("0.05"), 190, Decimal("193.80")))
    pg.execute(target_sql, (F4, OLD, 1, "AMD", Decimal("0.05"), 150, Decimal("153.00")))
    pg.execute(target_sql, (F1, NEXT, 1, "SPY", Decimal("1"), 660, Decimal("673.20")))
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
    assert order_notes(pg) == {"AAPL": None, "MSFT": "kept", "KO": None}
    assert set(target_notes(pg).values()) == {None}


def test_fills_only_the_newest_unexplained_entries(pg):
    seed(pg)
    client = FakeClient()
    assert explain.execute(pg, client=client) == 0
    assert order_notes(pg) == {"AAPL": "Paper note for AAPL.", "MSFT": "kept", "KO": None}
    assert target_notes(pg) == {
        (F4, NEXT, "NVDA"): "Paper note for NVDA.",
        (F4, NEXT, "AAPL"): None,  # already held: a re-weight, not a new entry
        (F4, OLD, "AMD"): None,  # an older decision
        (F1, NEXT, "SPY"): "Paper note for SPY.",  # SPY held by the benchmark, not by F1
    }
    assert len(client.prompts) == 3


def test_prompts_carry_stored_facts_and_paper_label(pg):
    seed(pg)
    client = FakeClient()
    explain.execute(pg, client=client)
    a, nvda, spy = client.prompts
    assert "- Symbol: AAPL (Apple Inc.)." in a
    assert "buy 10 shares with a limit of $185.00 (about $1,850.00)" in a
    assert "Take-profit: $195.00. Stop-loss: $180.00." in a
    assert "Rule set: design-v0." in a and "A · Quant" in a
    assert "Target weight: 5.0% of the paper portfolio." in nvda
    assert "Paper buy limit: $122.40." in nvda and "Rule set: monthly-hold." in nvda
    assert "Target weight: 100.0%" in spy
    for p in client.prompts:
        assert "PAPER trade only" in p and "not a recommendation" in p and "at most 3" in p


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


def test_client_bug_never_raises(pg):
    seed(pg)

    class Broken:
        def complete(self, system, prompt):
            raise KeyError("unexpected")

    assert explain.execute(pg, client=Broken()) == 0
    all_null_except_kept(pg)


def test_empty_reply_counts_as_unavailable(pg):
    seed(pg)

    class Blank:
        def complete(self, system, prompt):
            return "   \n "

    assert explain.execute(pg, client=Blank()) == 0
    all_null_except_kept(pg)


def test_dry_run_writes_nothing(pg):
    seed(pg)
    client = FakeClient()
    assert explain.execute(pg, client=client, dry_run=True) == 0
    assert len(client.prompts) == 3
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


@pytest.mark.parametrize(
    ("raw", "want"),
    [("  a\n b  ", "a b"), ("", None), ("  \n", None)],
)
def test_clean(raw, want):
    assert explain.clean(raw) == want


def test_clean_caps_length():
    out = explain.clean("word " * 400)
    assert out is not None and len(out) <= explain.MAX_CHARS + 1 and out.endswith("…")
```
**Impact:** the tests depend on phase 1's migration (tables `paper_state`, `book_targets`,
`book_positions`, columns `strategies.engine` and `rules_id`, and the roster rows with
`name = 'A · Quant'`). They run with 0 skips when `PG_TEST_URL` is set.

Notes for the implementer:
- `FakeClient.complete` returns `"Paper note for AAPL."` after `clean` collapses the whitespace.
  The symbol comes from the prompt's `- Symbol: AAPL (Apple Inc.).` line, so `.split()[0]` gives
  `AAPL`. For a book entry the line is `- Symbol: NVDA.`, so `.rstrip('.')` gives `NVDA`.
- `caplog` captures records through the root logger. `cli.main` also installs its own stderr
  handler, which the autouse `_drop_cli_log_handler` removes afterwards.
- `test_cli_end_to_end` works because `commands/explain.py` resolves `llm.Client` at call time
  (`llm.Client(cfg)` through the module attribute), so `monkeypatch.setattr(llm, "Client", …)` takes
  effect. Keep it that way: do not write `from seer_engine.llm import Client`.

## Verification

**Build:** `cd /home/miftah/.worktrees/seer/paper-trading-ship && engine/.venv/bin/python -c "from seer_engine import cli; assert 'explain' in cli.discover()"`
**Tests:**
```
docker start seer-pg
cd /home/miftah/.worktrees/seer/paper-trading-ship
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests/test_llm.py engine/tests/test_explain.py -q
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q   # 0 skipped
cd web && npx vitest run   # untouched by this phase; invariant 1
```
**Manual check (optional, only if the implementer chooses to; prints model text only, never a secret):**
`engine/.venv/bin/python -c "from seer_engine import llm; c = llm.load_config(); print('unconfigured' if c is None else llm.Client(c).complete('Reply with one word.', 'Say OK.'))"`
This reads `.env.local` through `config` and prints only the reply. It confirms that the z.ai
endpoint accepts the key (sent as both `x-api-key` and `Authorization: Bearer`) at
`<base>/v1/messages`. Do not print the config.
**Exit criteria:** the new tests are green. The full engine suite passes with 0 skipped.
`python -m seer_engine explain` exits 0 with no `LLM_*` set and with an LLM that always fails. No
file outside the four listed is changed.

## Handoffs

- **Phase 13 (R6/R7):**
  - Add the "Explain" step to `.github/workflows/nightly.yml` after "Paper" (and after "Paper
    check" if that is ordered first). It runs `python -m seer_engine -v explain`, has
    `continue-on-error: true`, and gets `LLM_BASE_URL: ${{ secrets.LLM_BASE_URL }}`,
    `LLM_API_KEY: ${{ secrets.LLM_API_KEY }}`, `LLM_MODEL: ${{ secrets.LLM_MODEL }}` and
    `DATABASE_URL_UNPOOLED` in `env`. Without the secrets the step logs "explanations unavailable"
    and exits 0, so the step can land before the owner adds them.
  - Write the owner step for the three `LLM_*` repo secrets into the paper runbook.
  - Document `explain` in `engine/package_readme.md`.
- **Phase 11 (R4):** the web reads `orders.explanation` and `book_targets.explanation`. NULL means
  "unavailable". This phase never writes a placeholder string into the column, so the UI owns that
  wording.
- **Phase 13 / ruff:** the two `except Exception` sites carry `# noqa: BLE001`, matching
  `commands/nightly.py`. If phase 13's minimal rule set does not include BLE, the comment is
  harmless.
- **Not done here (no requirement asks for it):** explanations for exits or closed trades, and
  backfilling explanations of older sessions. Only the newest decision is explained, on purpose.

## Risks

- **Reasoning models.** A model that spends the whole `max_tokens` budget on thinking returns no
  text block, which counts as unavailable. Raise `DEFAULT_MAX_TOKENS` if that shows up in the logs.
- **Schema drift.** If phase 1 renames any C1 column this phase reads, the SQL here must follow.
  C1 fixes the names, so this is only a reconciler check.

## Rollback

Delete `engine/src/seer_engine/llm.py`, `engine/src/seer_engine/commands/explain.py`,
`engine/tests/test_llm.py` and `engine/tests/test_explain.py` (or `git revert` the phase commit).
Nothing else references them until phase 13 adds the workflow step. If that step has already landed,
remove it too, or leave it: `continue-on-error` keeps the night green even when the command is gone.
Explanations already written are plain text in nullable columns. They can stay, or be cleared with
`UPDATE orders SET explanation = NULL; UPDATE book_targets SET explanation = NULL;`.

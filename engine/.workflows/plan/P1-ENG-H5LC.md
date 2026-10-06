> Adopted from `WHY_THIS_PICK_PIPELINE_PLAN.md` phase 2. Source: `.workflows/plan/why-this-pick-pipeline/phase-2.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 2: Store evidence with every paper entry

**Plan set:** `WHY_THIS_PICK_PIPELINE_PLAN.md`
**Analysis:** `20261006-213425-W7P3_code_analyzer.md`
**Satisfies:** R1 (each pick's evidence is stored with it), R6 (book previews, the "would pick now" rows, get evidence too)
**Depends on:** Phase 1 (`strategies/evidence.py`, contract K1)
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine/paper`, `engine/src/seer_engine/commands`, `db/migrations`

---

## Goal

After this phase, every paper night stores the evidence (K1 facts) next to each decision it
writes: a jsonb array of plain-English strings on each new pending `orders` row (A, C), each
`book_targets` row (F4, F1, FND) and each `book_previews` row. The idle instrument and any
symbol the evidence function cannot explain store NULL. An evidence function that raises
stores NULL for that strategy that night, logs one warning, and the night still succeeds.
Decisions, the replay and `paper_check` are byte-for-byte unchanged.

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.
**Creates:**
- `db/migrations/009_evidence.sql`: nullable `evidence jsonb` on `orders`, `book_targets`, `book_previews` (K2, verbatim).
- `seer_engine.paper.store._evidence_json(evidence, symbol) -> Jsonb | None` (private).
- `seer_engine.commands.paper._evidence(e, market, data_date, symbols) -> dict[str, tuple[str, ...]]` (private; the one helper that catches every exception, invariant 5).
- `engine/tests/test_paper_evidence.py`.

**Signature changes (keyword-only, default None, all existing callers unchanged):**
- `store.insert_pending_orders(conn, strategy_id, placed, companies=None)` -> `store.insert_pending_orders(conn, strategy_id, placed, companies=None, *, evidence: Mapping[str, Sequence[str]] | None = None)`
- `store.save_book_decision(conn, strategy_id, session, targets)` -> `store.save_book_decision(conn, strategy_id, session, targets, *, evidence: Mapping[str, Sequence[str]] | None = None)`
- `store.save_book_preview(conn, strategy_id, data_date, targets)` -> `store.save_book_preview(conn, strategy_id, data_date, targets, *, evidence: Mapping[str, Sequence[str]] | None = None)`

Storage semantics (what phases 3 and 5 read): the column holds a JSON **array of non-empty
strings** with at least one element, or SQL NULL. Never `[]`, never a JSON object, never a
JSON `null` literal. A symbol absent from the mapping, an empty fact list, `evidence=None`,
the idle symbol, and every row written before 009 are all SQL NULL.

**Requires (from earlier phases):**
- Phase 1: `seer_engine.strategies.evidence` with `evidence_for(object_name, market, params, data_date, symbols) -> dict[str, tuple[str, ...]]` (KeyError for an unknown name) and `EVIDENCE: dict[str, EvidenceFn]` keyed by `"STRATEGY_A"`, `"STRATEGY_C"`, `"FACTOR"`, `"TIMING"`, `"FUNDAMENTAL"`. `evidence_for` must look `EVIDENCE[object_name]` up **at call time** (the tests swap one entry with `monkeypatch.setitem`).
- Phase 1: evidence is a pure function of bars dated `<= data_date` (no look-ahead). The existing `test_paper_command.py::test_no_look_ahead` and `::test_catch_up_of_two_sessions_equals_night_by_night` compare `book_targets` with `SELECT *`, so after this phase they also compare the stored evidence; a look-ahead in K1 fails them.
- Phase 1: for a symbol the decision picked on the same `market`/`data_date`, the function returns facts (the test world here asserts every A order, F4 and F1 target and preview has evidence).

**Leaves alone (owned by others):**
- `strategies/evidence.py`, `tests/test_evidence.py` (Phase 1).
- `commands/explain.py`, `tests/test_explain.py`, `tests/test_paper_c.py`, `engine/src/seer_engine/llm.py`, `docs/runbooks/paper-trading.md`, `engine/package_readme.md` (Phase 3). This phase only *imports* `test_paper_c`'s world helpers (`night`, `allow_all`) and never edits that file.
- `commands/promote.py`, `tests/test_promote_command.py`, the explore skill (Phase 4).
- `web/**`, including `web/scripts/seed-demo.mjs` (Phase 5).
- `paper/replay.py` (`Records`, `compare`), `commands/paper_check.py`, `paper/book.py`, `paper/bracket.py`, every strategy and params class, `paper/roster.py`, `demo.py`: not touched.

## Files

| File | Action | What changes |
|---|---|---|
| `db/migrations/009_evidence.sql` | create | three `ADD COLUMN IF NOT EXISTS evidence jsonb` |
| `engine/src/seer_engine/paper/store.py` | modify | docstring line (~:22); `_evidence_json` helper (new, after `_one_row` ~:100); `evidence=` on `save_book_preview` (:465), `insert_pending_orders` (:628), `save_book_decision` (:967) |
| `engine/src/seer_engine/commands/paper.py` | modify | docstring paragraph (~:43); import `evidence` (:70); `_evidence` helper (new, after `_bracket_strategy` :461); calls in `_start` (:495-512), `_step_bracket` (:529-531), `_step_book` (:572-582) |
| `engine/tests/test_paper_evidence.py` | create | migration, store, helper and whole-night tests (incl. C orders carry facts, idle rows NULL) |

No change needed in:
- `engine/tests/test_migrate.py`: it pins only `ALL[:4]`, subsets of columns (`test_003_adds_the_columns` uses `<=`), and per-table exact column lists for `news_vetoes` and the 005 tables. `len(ALL)` is computed from the directory. 009 needs no acknowledgement there.
- `engine/tests/test_paper_roster.py`: no migration-name or column pin. Roster digests do not move (no params, object or rules change).
- `engine/src/seer_engine/demo.py`: the purge `TRUNCATE`s `orders` and `book_targets`, which takes the new column's values with the rows. `book_previews` is not in `DEMO_TABLES` today; that is pre-existing and unrelated to evidence (see Handoffs).
- `engine/tests/test_paper_command.py`: `CONTENT["book_targets"]` is `SELECT *`, so it starts comparing `evidence` too. That is intended extra coverage, not a break, because evidence is deterministic per night view. `CONTENT["orders"]` lists columns explicitly and does not include `evidence`.

## Implementation Steps

### Step 1: Migration 009
**File:** `db/migrations/009_evidence.sql` (new)
**Change:** additive, nullable columns, idempotent. Same style as `008_book_kickoff.sql`.
**Code:**
```sql
-- Seer schema v9: every paper entry keeps the evidence its method saw (why-this-pick pipeline).
-- Additive only: three nullable columns. No row is touched.
--
-- evidence: a JSON array of short plain-English strings (strategies.evidence, contract K1), the
-- numbers the method's formula read for that symbol on the decision night, already formatted for
-- a reader. Written by `paper` when it writes the row; NULL = no evidence (the idle instrument, a
-- symbol the method could not explain, an evidence function that failed that night, or any row
-- written before this migration). Display and explanation input only: nothing trades on it and
-- the replay (paper_check) never reads it.
ALTER TABLE orders        ADD COLUMN IF NOT EXISTS evidence jsonb;
ALTER TABLE book_targets  ADD COLUMN IF NOT EXISTS evidence jsonb;
ALTER TABLE book_previews ADD COLUMN IF NOT EXISTS evidence jsonb;
```
**Impact:** none on existing rows or readers. The web reads it through `to_jsonb(row)`
(Phase 5, K5), so the site works before the nightly Migrate step applies it.

### Step 2: Store docstring line
**File:** `engine/src/seer_engine/paper/store.py:22` (module docstring, after the "Inputs read at night" bullet, before the blank line that precedes "Every money value…")
**Change:** add one bullet.
**Code:**
```python
- Evidence (migration 009): ``orders``, ``book_targets`` and ``book_previews`` take an optional
  ``evidence`` mapping ``{symbol: facts}`` when they are written; each row stores its symbol's
  facts as a jsonb array of strings, or NULL. Nothing here reads it back: the replay never
  compares it, and ``explain`` / the site read it with their own SQL.
```
**Impact:** docs only.

### Step 3: `_evidence_json` helper
**File:** `engine/src/seer_engine/paper/store.py`, directly after `_one_row` (which starts at :100; insert after its body, before the next section's first definition).
**Change:** new private function. `Jsonb`, `Mapping` and `Sequence` are already imported (:35, :43).
**Code:**
```python
def _evidence_json(evidence: Mapping[str, Sequence[str]] | None, symbol: str) -> Jsonb | None:
    """``evidence[symbol]`` as a jsonb array of strings for an ``evidence`` column (009).

    None (SQL NULL) when ``evidence`` is None, the symbol is absent, or its facts are empty: the
    column never holds ``[]``. A non-mapping, a bare string, or a non-string fact is a TypeError
    (``commands.paper._evidence`` normalizes before it gets here, so the night never sees one).
    """
    if evidence is None:
        return None
    if not isinstance(evidence, Mapping):
        raise TypeError(f"evidence must be a mapping of symbol to facts, got {type(evidence).__name__}")
    facts = evidence.get(symbol)
    if facts is None:
        return None
    if isinstance(facts, str) or not isinstance(facts, Sequence):
        raise TypeError(f"{symbol}: evidence must be a sequence of strings, got {type(facts).__name__}")
    items = list(facts)
    for f in items:
        if not isinstance(f, str):
            raise TypeError(f"{symbol}: evidence must hold only strings, got {type(f).__name__}")
    return Jsonb(items) if items else None
```
**Impact:** none until used.

### Step 4: `save_book_preview` takes evidence
**File:** `engine/src/seer_engine/paper/store.py:465-486` (replace the whole function)
**Code:**
```python
def save_book_preview(
    conn: psycopg.Connection,
    strategy_id: str,
    data_date: date,
    targets: Sequence[Target] | None,
    *,
    evidence: Mapping[str, Sequence[str]] | None = None,
) -> None:
    """Replace the strategy's ``book_previews`` with ``targets``, what it would pick from the bars
    of ``data_date`` if it ranked tonight. Display only (008). None or empty leaves no rows.

    ``evidence``: ``{symbol: facts}`` (009); each row stores its symbol's facts, or NULL when the
    symbol is absent (the idle instrument, one the method could not explain) or ``evidence`` is
    None."""
    _session("data_date", data_date)
    conn.execute("DELETE FROM book_previews WHERE strategy_id = %s", (strategy_id,))
    rows: list[tuple[Any, ...]] = []
    for rank, t in enumerate(targets or (), start=1):
        if not isinstance(t, Target):
            raise TypeError(f"targets must hold Target values, got {type(t).__name__}")
        rows.append(
            (
                strategy_id,
                data_date,
                rank,
                t.symbol,
                _exact("weight", t.weight, WEIGHT_QUANTUM),
                _exact("last", t.last),
                _evidence_json(evidence, t.symbol),
            )
        )
    if rows:
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO book_previews (strategy_id, data_date, rank, symbol, weight, last, evidence) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                rows,
            )
```
**Impact:** existing callers (positional, no `evidence`) write NULL, same as before plus one column.

### Step 5: `insert_pending_orders` takes evidence
**File:** `engine/src/seer_engine/paper/store.py:628-660` (replace the whole function)
**Change:** keyword-only `evidence`; the INSERT gains the column. `_order_params` and
`_UPDATE_ORDER_SQL` are **not** changed: later updates of the row (fill, exit, marks) never
touch `evidence`, so it survives the order's whole life.
**Code:**
```python
def insert_pending_orders(
    conn: psycopg.Connection,
    strategy_id: str,
    placed: Iterable[Order],
    companies: Mapping[str, str] | None = None,
    *,
    evidence: Mapping[str, Sequence[str]] | None = None,
) -> int:
    """Insert ``SizingResult.placed`` as pending ``orders`` rows; returns how many.

    ``company`` is ``companies[symbol]`` when given, else the symbol (``orders.company`` is NOT
    NULL and the engine has no company names). ``evidence`` is ``{symbol: facts}`` (009): each
    row stores its symbol's facts as a jsonb array, or NULL when the symbol is absent or
    ``evidence`` is None; no later update of the row touches it. ``explanation`` stays NULL
    (``explain`` fills it). Only pending orders are accepted. A row that already exists for
    (strategy, session, symbol) is a database error: the caller decides each session once.
    """
    rows: list[dict[str, Any]] = []
    for o in placed:
        if not isinstance(o, Order):
            raise TypeError(f"placed must hold Order values, got {type(o).__name__}")
        if o.status != "pending":
            raise ValueError(f"only pending orders are inserted, got {o.status} {o.symbol}")
        params = _order_params(strategy_id, o, None)
        params["company"] = (companies or {}).get(o.symbol, o.symbol)
        params["evidence"] = _evidence_json(evidence, o.symbol)
        rows.append(params)
    if not rows:
        return 0
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO orders (strategy_id, session_date, slot, symbol, company, last_price, "
            "limit_price, tp_price, sl_price, shares, status, evidence) VALUES (%(strategy_id)s, "
            "%(session_date)s, %(slot)s, %(symbol)s, %(company)s, %(last_price)s, %(limit_price)s, "
            "%(tp_price)s, %(sl_price)s, %(shares)s, 'pending', %(evidence)s)",
            rows,
        )
    return len(rows)
```
**Impact:** existing callers unchanged (NULL evidence).

### Step 6: `save_book_decision` takes evidence
**File:** `engine/src/seer_engine/paper/store.py:967-1009` (replace the whole function)
**Change:** keyword-only `evidence`; the INSERT gains the column. `_rewrite_executed_targets`
(:899) is **not** changed: it UPDATEs prices/weight of an executed target and leaves
`evidence` as written at decision time. `read_book_targets` (:755) is **not** changed:
it selects explicit columns, so the replay never sees `evidence` (invariant 3).
**Code:**
```python
def save_book_decision(
    conn: psycopg.Connection,
    strategy_id: str,
    session: date,
    targets: Sequence[Target] | None,
    *,
    evidence: Mapping[str, Sequence[str]] | None = None,
) -> None:
    """Record tonight's decision for ``session`` (``next_session(paper_state.last_session)``).

    ``targets`` None: ``session`` is not a decision session (no rows, ``pending_decision``
    false). A sequence (possibly empty, idle target included last when ``_with_idle`` added one):
    the rows for (strategy, ``session``) are replaced by these, ranked 1.. in order, and
    ``pending_decision`` is true. Earlier sessions' rows are kept as the decision record.

    ``evidence`` is ``{symbol: facts}`` (009): each row stores its symbol's facts as a jsonb
    array, or NULL when the symbol is absent (the idle target, one the method could not explain)
    or ``evidence`` is None. ``read_book_targets`` never reads it back, so the replay ignores it.
    """
    write_pending(conn, strategy_id, session, decision=targets is not None)
    if targets is None:
        return
    rows: list[tuple[Any, ...]] = []
    for rank, t in enumerate(targets, start=1):
        if not isinstance(t, Target):
            raise TypeError(f"targets must hold Target values, got {type(t).__name__}")
        rows.append(
            (
                strategy_id,
                session,
                rank,
                t.symbol,
                _exact("weight", t.weight, WEIGHT_QUANTUM),
                _exact("last", t.last),
                _exact_or_none("limit", t.limit),
                _exact_or_none("stop", t.stop),
                _exact_or_none("take", t.take),
                _evidence_json(evidence, t.symbol),
            )
        )
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM book_targets WHERE strategy_id = %s AND session_date = %s", (strategy_id, session)
        )
        if rows:
            cur.executemany(
                "INSERT INTO book_targets (strategy_id, session_date, rank, symbol, weight, last_price, "
                "limit_price, stop_price, take_price, evidence) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                rows,
            )
```
**Impact:** existing callers unchanged (NULL evidence).

### Step 7: Paper docstring paragraph and import
**File:** `engine/src/seer_engine/commands/paper.py`
**Change A** (module docstring, after the Strategy C paragraph ending at :42, before the
"Trade logic lives in…" paragraph at :44): add
```python
Evidence (migration 009, ``strategies.evidence``): every decision written tonight -- a bracket
entry's pending orders, a book entry's targets and its "would pick now" preview -- stores, per
symbol, the facts its method's formula read on that night's view (``_evidence``). The idle
instrument gets none. Evidence never changes a decision and never fails the night: an evidence
function that raises leaves that strategy's evidence NULL for the night and logs a warning.
```
**Change B** (imports, :70-71): add one import line after `from seer_engine.strategies.base import History, Strategy`:
```python
from seer_engine.strategies import evidence
```
Keep `from seer_engine.strategies.c import NewsVeto` where it is. (`evidence` is referenced as a
module attribute, `evidence.evidence_for`, so a test can monkeypatch it.)
**Impact:** none on behaviour.

### Step 8: The `_evidence` helper
**File:** `engine/src/seer_engine/commands/paper.py`, new function directly after `_bracket_strategy` (ends :460), before `_start` (:463).
**Code:**
```python
Facts = tuple[str, ...]


def _evidence(e: RosterEntry, market: Market, data_date: date, symbols: Iterable[str]) -> dict[str, Facts]:
    """``{symbol: facts}`` for the symbols ``e`` just decided on ``market`` (the decision's own
    night view) and ``data_date``, through ``strategies.evidence.evidence_for``.

    The idle instrument (``e.rules.idle_symbol``) is never asked for and never gets evidence.
    A symbol the method cannot explain is absent (stored NULL). Never raises (plan invariant 5):
    any exception -- an unknown object name, a bug in an evidence function, a malformed result --
    logs one warning and returns ``{}``, so the decision is stored with NULL evidence and the
    night goes on. Nothing here feeds back into a decision.
    """
    idle = None if e.rules is None else e.rules.idle_symbol
    wanted = tuple(dict.fromkeys(s for s in symbols if s != idle))
    if not wanted:
        return {}
    try:
        found = evidence.evidence_for(e.object_name, market, e.params, data_date, wanted)
        if not isinstance(found, Mapping):
            raise TypeError(f"evidence_for returned {type(found).__name__}, not a mapping")
        out: dict[str, Facts] = {}
        for symbol in wanted:
            facts = found.get(symbol)
            if facts is None:
                continue
            if isinstance(facts, str):
                raise TypeError(f"{symbol}: facts must be a sequence of strings, got a str")
            items = tuple(facts)
            for f in items:
                if not isinstance(f, str) or not f.strip():
                    raise TypeError(f"{symbol}: every fact must be a non-empty string, got {f!r}")
            if items:
                out[symbol] = items
        return out
    except Exception as exc:  # noqa: BLE001 - evidence must never fail the night (invariant 5)
        log.warning(
            "%s %s: no evidence stored tonight (%s); the decision is unchanged",
            e.id,
            data_date,
            _error_text(exc),
        )
        return {}
```
Also extend the `collections.abc` import at :52 to `from collections.abc import Iterable, Mapping, Sequence`.
**Impact:** none until called.

### Step 9: `_start` stores evidence
**File:** `engine/src/seer_engine/commands/paper.py:495-512` (the `if e.engine == "bracket": … elif e.engine == "book": …` branches inside `_start`; replace those two branches, keep the benchmark/else branches and the `log.info` after them)
**Code:**
```python
    if e.engine == "bracket":
        sized = decide_bracket(
            new_portfolio(cash0),
            _bracket_strategy(conn, e, paper_start, paper_start),
            e.params,
            view.history,
            view.membership.members_on(rd.data_date),
            rd.data_date,
        )
        facts = _evidence(e, view, rd.data_date, (o.symbol for o in sized.placed))
        store.insert_pending_orders(conn, e.id, sized.placed, evidence=facts)
        store.write_pending(conn, e.id, paper_start, decision=False)
    elif e.engine == "book":
        kickoff = needs_kickoff(e.rules, paper_start, paper_start, None)
        targets, _ = decide_book(view, e.obj, e.params, e.rules, rd.data_date, frozenset(), force=kickoff)
        facts = None if targets is None else _evidence(e, view, rd.data_date, (t.symbol for t in targets))
        store.save_book_decision(conn, e.id, paper_start, targets, evidence=facts)
        if kickoff:
            store.write_kickoff(conn, e.id, paper_start)
        store.save_book_preview(conn, e.id, rd.data_date, targets, evidence=facts)
```
**Impact:** the preview on the first night is the decision itself, so it reuses the same facts
(one evidence call, not two). Decision values unchanged.

### Step 10: `_step_bracket` stores evidence
**File:** `engine/src/seer_engine/commands/paper.py:520-533` (replace the whole function)
**Code:**
```python
def _step_bracket(conn: psycopg.Connection, e: RosterEntry, sessions: Sequence[date], tonight: _Tonight) -> None:
    pf = store.load_portfolio(conn, e.id)
    if not sessions:
        return
    strategy = _bracket_strategy(conn, e, dates.next_session(sessions[0]), dates.next_session(sessions[-1]))
    for s in sessions:
        view = tonight.view(s)
        night = settle_bracket(pf, s, view.bars_on(s, pf.held_symbols()), tonight.splits_on(s), view.last_bar_date)
        store.save_bracket_night(conn, e.id, night.portfolio, night.events, night.snapshot)
        sized = decide_bracket(night.portfolio, strategy, e.params, view.history, view.membership.members_on(s), s)
        facts = _evidence(e, view, s, (o.symbol for o in sized.placed))
        store.insert_pending_orders(conn, e.id, sized.placed, evidence=facts)
        store.write_pending(conn, e.id, dates.next_session(s), decision=False)
        pf = sized.portfolio
        log.info("%s %s: equity %s, %d live order(s)", e.id, s, pf.equity, len(pf.orders))
```
**Impact:** C's evidence is computed with `e.params` (`CParams`; K1 reads `params.a`) and the
symbols C actually placed (allowed by the news check). A night with no placed orders makes no
evidence call.

### Step 11: `_step_book` stores evidence (targets and preview)
**File:** `engine/src/seer_engine/commands/paper.py:536-590` (replace the whole function)
**Code:**
```python
def _step_book(
    conn: psycopg.Connection,
    e: RosterEntry,
    sessions: Sequence[date],
    tonight: _Tonight,
    state: PaperState,
    paper_start: date,
) -> None:
    rules = e.rules
    loaded = store.load_book(conn, e.id, idle_symbol=rules.idle_symbol)
    book, targets, idle_added = loaded.book, loaded.targets, loaded.idle_added
    kicked = state.kickoff_session
    for s in sessions:
        view = tonight.view(s)
        symbols = set(book.held())
        if targets is not None:
            symbols.update(t.symbol for t in targets)
        night = settle_book(
            book,
            s,
            view.bars_on(s, sorted(symbols)),
            targets,
            idle_added,
            rules,
            tonight.dividends_on(s),
            tonight.splits_on(s),
            view.last_bar_date,
        )
        store.save_book_night(
            conn, e.id, night.book, night.fills, night.trades, night.snapshot, executed_targets=night.targets
        )
        book = night.book
        nxt = dates.next_session(s)
        # A book that has never decided ranks on its first session instead of waiting for its
        # cadence (008, paper.book.needs_kickoff); the replay ranks on the stored kickoff too.
        kickoff = needs_kickoff(rules, paper_start, nxt, kicked)
        targets, idle_added = decide_book(view, e.obj, e.params, rules, s, book.held(), force=kickoff)
        facts = None if targets is None else _evidence(e, view, s, (t.symbol for t in targets))
        store.save_book_decision(conn, e.id, nxt, targets, evidence=facts)
        if kickoff:
            store.write_kickoff(conn, e.id, nxt)
            kicked = nxt
        if s == sessions[-1]:
            # What it would pick if it ranked tonight: display only, never traded or replayed.
            preview, preview_facts = targets, facts
            if preview is None:
                preview, _ = decide_book(view, e.obj, e.params, rules, s, book.held(), force=True)
                preview_facts = None if preview is None else _evidence(e, view, s, (t.symbol for t in preview))
            store.save_book_preview(conn, e.id, s, preview, evidence=preview_facts)
        log.info(
            "%s %s: equity %s, %d position(s)%s",
            e.id,
            s,
            book.equity,
            len(book.positions),
            f", {len(targets)} target(s) for {nxt}" if targets is not None else "",
        )
```
**Impact:** evidence is computed only on decision sessions (targets not None) and once for the
preview on the night's last session when it is not a decision session. On a monthly book that
is about one extra evidence call per night (the preview). Decisions unchanged.

### Step 12: Tests
**File:** `engine/tests/test_paper_evidence.py` (new)
**Change:** the world is `test_paper_check.py`'s (A picks every night there, F4 and F1 decide
2026-11-02, `paper_check` is green on it). Its `world` fixture is re-declared here from the
module's constants instead of importing the fixture (an imported fixture used as a parameter
is a pyflakes F811). `test_paper_check.night` asserts `paper.execute(...) == 0` itself.
**Code:**
```python
"""Evidence stored with every paper entry (why-this-pick pipeline, phase 2, contract K2).

Migration 009 adds a nullable jsonb ``evidence`` column to ``orders``, ``book_targets`` and
``book_previews``. ``paper`` fills it from ``strategies.evidence`` for every decision it writes;
the idle instrument gets none; an evidence function that raises leaves NULL and the night still
succeeds; decisions and ``paper_check`` are unchanged.

The world is ``test_paper_check``'s: A picks every night, F4 and F1 decide 2026-11-02, FND has no
fundamentals panel and so picks nothing, C has no stored verdicts and so buys nothing.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

import test_paper_c as tc
import test_paper_check as pc
from seer_engine import bars, db, fx
from seer_engine.commands import paper, paper_check
from seer_engine.commands.migrate import MIGRATIONS_DIR
from seer_engine.paper import roster, store
from seer_engine.sim import MONTHLY_HOLD_TBILL, Pick, Target, size_picks
from seer_engine.strategies.a import STRATEGY_A_PARAMS
from seer_engine.strategies.c import STRATEGY_C_PARAMS

D = Decimal
EVIDENCE_TABLES = ("orders", "book_targets", "book_previews")
S1 = date(2026, 9, 29)
S3 = date(2026, 10, 1)


def boom(*args, **kwargs):
    raise RuntimeError("evidence exploded apiKey=sekret")


@pytest.fixture
def world(pg):
    """``test_paper_check.world``, declared here (bars, one FX row, 24 members, a SPY dividend)."""
    with db.transaction(pg, False):
        bars.upsert_bars(pg, pc.synthetic_bars())
        fx.upsert_fx(pg, [(pc.HIST_START, pc.USD_IDR)])
        for s in pc.MEMBERS:
            pg.execute(
                "INSERT INTO universe (symbol, index_id, start_date, end_date, source_symbol) "
                "VALUES (%s, 'SP500', '2000-01-03', NULL, %s)",
                (s, s),
            )
        pg.execute(
            "INSERT INTO dividends (symbol, ex_date, amount) VALUES ('SPY', %s, %s)",
            (pc.SPY_EX_DATE, pc.SPY_DIVIDEND),
        )
    return pg


def run_nights(conn, nights=pc.NIGHTS) -> None:
    for d in nights:
        pc.night(conn, d)  # asserts paper.execute(...) == 0


def evidence_rows(conn, table: str, strategy_id: str):
    key = "data_date" if table == "book_previews" else "session_date"
    return pc.q(
        conn,
        f"SELECT {key}, symbol, evidence FROM {table} WHERE strategy_id = %s ORDER BY {key}, symbol",
        (strategy_id,),
    )


def assert_facts(value) -> None:
    assert isinstance(value, list) and value, value
    assert all(isinstance(f, str) and f.strip() for f in value), value


# Decision content without evidence: must be identical whatever evidence does.
DECISIONS = {
    "orders": (
        "strategy_id, session_date, slot, symbol, company, last_price, limit_price, tp_price, sl_price, "
        "shares, status, fill_date, fill_price, days_held, exit_date, exit_price, exit_reason, pnl_usd, mark",
        "strategy_id, session_date, symbol",
    ),
    "book_targets": (
        "strategy_id, session_date, rank, symbol, weight, last_price, limit_price, stop_price, take_price",
        "strategy_id, session_date, rank",
    ),
    "book_previews": ("strategy_id, data_date, rank, symbol, weight, last", "strategy_id, rank"),
    "book_positions": ("*", "strategy_id, symbol"),
    "book_fills": (
        "strategy_id, session_date, seq, symbol, side, shares, price, cash_usd, cost_usd, reason",
        "strategy_id, session_date, seq",
    ),
    "equity_snapshots": ("*", "strategy_id, date"),
    "paper_state": (
        "strategy_id, last_session, cash_usd, equity_usd, pending_session, pending_decision, kickoff_session",
        "strategy_id",
    ),
}


def decisions(conn):
    return {t: pc.q(conn, f"SELECT {cols} FROM {t} ORDER BY {order}") for t, (cols, order) in DECISIONS.items()}


def reset(conn) -> None:
    """Reset the paper clock (bars, universe and runs rows stay), as test_paper_command.reset does."""
    with db.transaction(conn, False):
        conn.execute(
            "TRUNCATE paper_state, book_positions, book_targets, book_fills, book_trades, book_previews, "
            "action_dismissals, orders, equity_snapshots RESTART IDENTITY"
        )
        conn.execute("UPDATE strategies SET paper_start = NULL, params = '{}'::jsonb")
        conn.execute("UPDATE runs SET paper_status = NULL, paper_error = NULL, paper_finished_at = NULL")


# ---- migration 009 -----------------------------------------------------------------------------


def test_009_adds_a_nullable_jsonb_evidence_column_to_three_tables(pg):
    rows = pg.execute(
        "SELECT table_name, data_type, is_nullable, column_default FROM information_schema.columns "
        "WHERE table_schema = current_schema() AND column_name = 'evidence' ORDER BY table_name"
    ).fetchall()
    assert rows == [(t, "jsonb", "YES", None) for t in sorted(EVIDENCE_TABLES)]


def test_009_is_idempotent(pg):
    before = pg.execute(
        "SELECT table_name, column_name, data_type FROM information_schema.columns "
        "WHERE table_schema = current_schema() ORDER BY table_name, ordinal_position"
    ).fetchall()
    pg.execute((MIGRATIONS_DIR / "009_evidence.sql").read_text(encoding="utf-8"))
    pg.commit()
    after = pg.execute(
        "SELECT table_name, column_name, data_type FROM information_schema.columns "
        "WHERE table_schema = current_schema() ORDER BY table_name, ordinal_position"
    ).fetchall()
    assert after == before


# ---- paper.store -------------------------------------------------------------------------------


PICKS = (
    Pick("AAA", D("10"), D("10"), D("11"), D("9.5")),
    Pick("BBB", D("20"), D("20"), D("22"), D("19")),
)
TARGETS = (
    Target("AAA", D("0.500000"), D("10")),
    Target("BIL", D("0.500000"), D("91.5")),
)


def test_insert_pending_orders_stores_each_symbols_facts_and_null_when_absent(pg):
    store.init_paper_state(pg, "A", paper_start=S1, cash0=D("1250.0000"), usd_idr=D("16000.0000"))
    sized = size_picks(store.load_portfolio(pg, "A"), PICKS, S1)
    facts = {"AAA": ("Closed at $10.00.", "1st of 2 that qualified.")}
    assert store.insert_pending_orders(pg, "A", sized.placed, evidence=facts) == 2
    assert pg.execute("SELECT symbol, evidence FROM orders ORDER BY symbol").fetchall() == [
        ("AAA", ["Closed at $10.00.", "1st of 2 that qualified."]),
        ("BBB", None),
    ]


def book_state(pg) -> None:
    """save_book_decision writes paper_state.pending_session, so the book needs a state row."""
    store.init_paper_state(pg, pc.F4, paper_start=S3, cash0=D("1250.0000"), usd_idr=D("16000.0000"))


def test_store_without_evidence_writes_null_like_before(pg):
    store.init_paper_state(pg, "A", paper_start=S1, cash0=D("1250.0000"), usd_idr=D("16000.0000"))
    book_state(pg)
    sized = size_picks(store.load_portfolio(pg, "A"), PICKS, S1)
    store.insert_pending_orders(pg, "A", sized.placed)
    store.save_book_decision(pg, pc.F4, S3, TARGETS)
    store.save_book_preview(pg, pc.F4, S1, TARGETS)
    for t in EVIDENCE_TABLES:
        assert pg.execute(f"SELECT count(*) FROM {t} WHERE evidence IS NOT NULL").fetchone()[0] == 0
        assert pg.execute(f"SELECT count(*) FROM {t}").fetchone()[0] == 2


def test_book_decision_and_preview_store_facts_and_null_for_the_idle_symbol(pg):
    book_state(pg)
    facts = {"AAA": ["Rose 48.2% over the 12 months up to a month ago."]}
    store.save_book_decision(pg, pc.F4, S3, TARGETS, evidence=facts)
    store.save_book_preview(pg, pc.F4, S1, TARGETS, evidence=facts)
    expected = [("AAA", ["Rose 48.2% over the 12 months up to a month ago."]), ("BIL", None)]
    assert pg.execute("SELECT symbol, evidence FROM book_targets ORDER BY rank").fetchall() == expected
    assert pg.execute("SELECT symbol, evidence FROM book_previews ORDER BY rank").fetchall() == expected
    # The replay's reader is unchanged: evidence never reaches a Target.
    assert store.read_book_targets(pg, pc.F4, S3) == TARGETS


def test_empty_facts_are_stored_as_null_and_bad_facts_are_refused(pg):
    book_state(pg)
    store.save_book_decision(pg, pc.F4, S3, TARGETS, evidence={"AAA": ()})
    assert pg.execute("SELECT evidence FROM book_targets ORDER BY rank").fetchall() == [(None,), (None,)]
    with pytest.raises(TypeError):
        store.save_book_decision(pg, pc.F4, S3, TARGETS, evidence={"AAA": "not a list"})
    with pytest.raises(TypeError):
        store.save_book_decision(pg, pc.F4, S3, TARGETS, evidence={"AAA": ["ok", 3]})


# ---- commands.paper._evidence (no database) ----------------------------------------------------


def test_helper_never_asks_for_the_idle_symbol_and_dedups(monkeypatch):
    seen = []

    def fake(object_name, market, params, data_date, symbols):
        seen.append((object_name, tuple(symbols)))
        return {s: (f"{s} fact.",) for s in symbols}

    monkeypatch.setattr(paper.evidence, "evidence_for", fake)
    e = replace(roster.entry(pc.F4), rules=MONTHLY_HOLD_TBILL)
    out = paper._evidence(e, None, S1, ["AAA", "BIL", "AAA", "BBB"])
    assert seen == [("FACTOR", ("AAA", "BBB"))]
    assert out == {"AAA": ("AAA fact.",), "BBB": ("BBB fact.",)}
    seen.clear()
    assert paper._evidence(e, None, S1, ["BIL"]) == {}
    assert seen == []  # nothing to explain: no call at all


def test_helper_turns_any_failure_into_no_evidence_and_a_warning(monkeypatch, caplog):
    caplog.set_level(logging.WARNING, logger="seer_engine.commands.paper")
    e = roster.entry("A")
    monkeypatch.setattr(paper.evidence, "evidence_for", boom)
    assert paper._evidence(e, None, S1, ["AAA"]) == {}
    assert "A 2026-09-29: no evidence stored tonight" in caplog.text
    assert "sekret" not in caplog.text
    for bad in (["not a mapping"], {"AAA": "a bare string"}, {"AAA": ("ok", "")}, {"AAA": (1,)}):
        monkeypatch.setattr(paper.evidence, "evidence_for", lambda *a, _bad=bad, **k: _bad)
        assert paper._evidence(e, None, S1, ["AAA"]) == {}


def test_helper_drops_symbols_the_method_cannot_explain(monkeypatch):
    monkeypatch.setattr(paper.evidence, "evidence_for", lambda *a, **k: {"AAA": ("x.",), "BBB": ()})
    assert paper._evidence(roster.entry("A"), None, S1, ["AAA", "BBB", "CCC"]) == {"AAA": ("x.",)}


def test_the_benchmark_is_never_asked(world, monkeypatch):
    calls = []
    real = paper.evidence.evidence_for

    def spy(object_name, *args, **kwargs):
        calls.append(object_name)
        return real(object_name, *args, **kwargs)

    monkeypatch.setattr(paper.evidence, "evidence_for", spy)
    run_nights(world, pc.NIGHTS[:2])
    assert calls and roster.BENCHMARK_OBJECT not in calls


# ---- whole nights ------------------------------------------------------------------------------


def test_every_entry_written_by_paper_has_evidence(world):
    run_nights(world)
    a_orders = evidence_rows(world, "orders", "A")
    assert len(a_orders) >= 7  # A picks every night in this world
    for _, _, value in a_orders:
        assert_facts(value)
    # Each stock has its own reason: no two orders of one session share their facts.
    by_session: dict[date, list] = {}
    for session, _, value in a_orders:
        by_session.setdefault(session, []).append(tuple(value))
    for facts in by_session.values():
        assert len(set(facts)) == len(facts)
    for sid in (pc.F4, pc.F1):
        # The idle instrument (if the rules have one) is never explained; every other row is. A night
        # F1's rule is off decides nothing but the idle (TIMING returns {}), so only non-idle rows count.
        idle = roster.entry(sid).rules.idle_symbol
        targets = [r for r in evidence_rows(world, "book_targets", sid) if r[1] != idle]
        previews = [r for r in evidence_rows(world, "book_previews", sid) if r[1] != idle]
        assert targets  # F4 and F1 both decide 2026-11-02 in this world (test_paper_check)
        for _, _, value in targets + previews:
            assert_facts(value)
        for _, symbol, value in evidence_rows(world, "book_targets", sid) + evidence_rows(world, "book_previews", sid):
            if symbol == idle:
                assert value is None
    assert {s for _, s, _ in evidence_rows(world, "book_targets", pc.F1)} - {roster.entry(pc.F1).rules.idle_symbol} == {"SPY"}
    # Nothing paper writes for SPY, C (no verdicts) or FND (no panel) carries evidence.
    for t in EVIDENCE_TABLES:
        assert pc.q(world, f"SELECT count(*) FROM {t} WHERE strategy_id IN ('SPY', 'C', 'FND') AND evidence IS NOT NULL") == [(0,)]
    assert paper_check.execute(world, require_sessions=7) == 0


def test_c_orders_carry_a_facts_under_c_params(world):
    """C's placed orders get STRATEGY_C evidence (A's facts under ``CParams.a``). Phase 3's
    ``test_paper_c.py::test_explain_fills_c_pending_orders_like_a`` relies on this."""
    for d in pc.NIGHTS[:3]:
        tc.night(world, d, tc.allow_all)  # bars run, every candidate allowed, paper
    c_orders = evidence_rows(world, "orders", "C")
    assert c_orders
    for _, _, value in c_orders:
        assert_facts(value)
    if STRATEGY_C_PARAMS.a == STRATEGY_A_PARAMS:
        a_facts = {(d, s): v for d, s, v in evidence_rows(world, "orders", "A")}
        for d, s, v in c_orders:
            if (d, s) in a_facts:
                assert v == a_facts[(d, s)]


def test_an_evidence_function_that_raises_leaves_null_and_the_night_succeeds(world, monkeypatch, caplog):
    caplog.set_level(logging.WARNING, logger="seer_engine.commands.paper")
    monkeypatch.setattr(paper.evidence, "evidence_for", boom)
    run_nights(world)
    for t in EVIDENCE_TABLES:
        assert pc.q(world, f"SELECT count(*) FROM {t} WHERE evidence IS NOT NULL") == [(0,)]
    assert pc.q(world, "SELECT count(*) FROM orders WHERE strategy_id = 'A'")[0][0] >= 7
    assert pc.q(world, "SELECT DISTINCT paper_status FROM runs WHERE NOT is_demo AND paper_status IS NOT NULL") == [
        ("success",)
    ]
    assert "no evidence stored tonight" in caplog.text and "sekret" not in caplog.text
    assert paper_check.execute(world, require_sessions=7) == 0


def test_one_method_failing_does_not_touch_the_others(world, monkeypatch):
    monkeypatch.setitem(paper.evidence.EVIDENCE, "FACTOR", boom)
    run_nights(world)
    assert evidence_rows(world, "book_targets", pc.F4)
    assert all(value is None for _, _, value in evidence_rows(world, "book_targets", pc.F4))
    assert all(value is None for _, _, value in evidence_rows(world, "book_previews", pc.F4))
    for _, _, value in evidence_rows(world, "orders", "A") + evidence_rows(world, "book_targets", pc.F1):
        assert_facts(value)
    assert paper_check.execute(world, require_sessions=7) == 0


def test_evidence_never_changes_a_decision(world, monkeypatch):
    nights = pc.NIGHTS[:6]  # through the night that decides 2026-11-02
    run_nights(world, nights)
    with_evidence = decisions(world)
    reset(world)
    monkeypatch.setattr(paper.evidence, "evidence_for", boom)
    run_nights(world, nights)
    assert decisions(world) == with_evidence
```
**Impact:** new tests only. Notes for the implementer:
- `roster.entry(strategy_id)` (`paper/roster.py:563`) returns the compiled `RosterEntry`; `F4`'s `object_name` is `"FACTOR"`, A's is `"STRATEGY_A"`.
- `size_picks` places orders only for picks the cash can buy. With 1250 USD both cheap picks are placed (`test_paper_store.py::_bracket_day0` places three at the same cash).
- `test_one_method_failing…` relies on K1's `evidence_for` reading `EVIDENCE[name]` at call time. If Phase 1 binds the function elsewhere, patch whatever `evidence_for` dispatches through. The point is "FACTOR fails, the others don't".
- `import test_paper_check as pc` follows the existing cross-test import convention (`test_paper_c.py:19`). Importing the module by alias does not re-collect its tests here. `import test_paper_c as tc` likewise (its world is the same bars/universe/dividend as `pc`'s, so `tc.night` runs on this file's `world` fixture; `tc` imports `FakeClient` from `test_explain`, which exists both before and after phase 3's rewrite).
- The whole-night test tolerates an idle instrument and a TIMING-off night: idle rows must be NULL, every non-idle row must hold facts (reconciled; F4/F1 currently have no idle symbol, so this is a guard, not a change of expectation).

## Verification

**Build:** `/home/miftah/.worktrees/seer/why-this-pick-pipeline/engine/.venv/bin/ruff check /home/miftah/.worktrees/seer/why-this-pick-pipeline/engine`
**Tests:**
```
docker start seer-pg
cd /home/miftah/.worktrees/seer/why-this-pick-pipeline
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests/test_paper_evidence.py engine/tests/test_paper_command.py engine/tests/test_paper_check.py engine/tests/test_paper_store.py engine/tests/test_paper_c.py engine/tests/test_paper_kickoff.py engine/tests/test_paper_fnd.py engine/tests/test_migrate.py engine/tests/test_demo.py engine/tests/test_strategy_purity.py engine/tests/test_paper_roster.py -q
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q
```
The full run passes except the two known Python-3.12-only failures (invariant 1: `test_f_fundamental.py::test_allocator_shape`, `test_market_fundamentals.py::test_adding_the_hook_does_not_change_the_allocator_check`). `cd web && npx vitest run && npx tsc --noEmit` is unaffected (no web change) but is part of invariant 1.
**Manual check:** none required. Optionally run one night against a local DB with `-v` and read a row: `SELECT symbol, evidence FROM orders ORDER BY id DESC LIMIT 3`.
**Exit criteria:** after paper nights in the test world, every A order, every C order (with allow verdicts), and every non-idle F4/F1 target and preview row holds a non-empty JSON array of strings; idle rows, SPY and FND (no panel) rows hold NULL. An evidence function that raises leaves every evidence NULL, logs a warning, and every night returns 0. With and without evidence the decision tables are equal, `paper_check` is ok, and every existing paper test passes unchanged.

## Handoffs

- **Phase 3 (R2, R3):** `explain` should read `evidence` from `orders` / `book_targets` (jsonb → Python `list[str]` via psycopg) and skip rows where it is NULL. Rows written before 009 and every row of a night whose evidence failed are NULL. The runbook (`docs/runbooks/paper-trading.md`) and `engine/package_readme.md` should mention the new column and the warning line `"<id> <date>: no evidence stored tonight (...)"`. Phase 3 owns both docs.
- **Phase 5 (R5, R6, R8):** `book_previews.evidence` is the "would pick now" facts (R6). The demo seed (`web/scripts/seed-demo.mjs`) may now write `evidence` on its demo `orders`/`book_targets`/`book_previews` rows. Phase 5 owns that file.
- **Phase 4 (R7):** a promoted object with no `EVIDENCE` entry does not fail the night here (KeyError → warning → NULL). The gate that stops it reaching the roster is phase 4's.
- **Out of scope, pre-existing, any phase or a follow-up card:** `demo.DEMO_TABLES` does not include `book_previews` (migration 008). A demo seed that writes previews would leave them after the purge. This is unrelated to evidence, so it is not fixed here.

## Rollback

Revert this phase's commit. 009 is additive (three nullable columns). If it was already
applied, leaving the columns in place is harmless because nothing else writes them. To remove
them by hand: `ALTER TABLE orders DROP COLUMN IF EXISTS evidence; ALTER TABLE book_targets DROP
COLUMN IF EXISTS evidence; ALTER TABLE book_previews DROP COLUMN IF EXISTS evidence; DELETE FROM
schema_migrations WHERE name = '009_evidence.sql';` (only after Phases 3 and 5 are reverted too,
since they read the column; Phase 5 reads it through `to_jsonb` and tolerates its absence).

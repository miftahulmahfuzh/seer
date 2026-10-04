> Adopted from `STRATEGY_C_NEWS_VETO_PLAN.md` phase 2. Source: `.workflows/plan/strategy-c-news-veto/phase-2.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 2: Migration 004, roster entry C, verdict store

**Plan set:** `STRATEGY_C_NEWS_VETO_PLAN.md`
**Analysis:** `20261004-171449-C5V8_code_analyzer.md`
**Spec:** `docs/handover/2026-10-04-strategy-c-news-veto.md` (D1, D5, D7, D9)
**Satisfies:** R1 (roster entry `C` with its frozen spec), R2 (migration `004`, verdict store) — C exists as a roster strategy with a pinned spec, its display row and the `news_vetoes` table exist in the schema, and `veto` / `paper` / `paper_check` have a store API to write and read verdicts
**Depends on:** Phase 1 (`strategies/c.py`, contract K1)
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine/paper`, `db/migrations`

---

## Goal

After this phase the paper roster has a fifth entry `C` (sort 5, last) whose frozen spec is A's spec
plus the frozen news check (K1 `CParams.as_dict()`), pinned in `test_paper_roster.py::PINS` beside the four
unchanged pins. Migration `004` puts the `C` display row back and creates `news_vetoes` (K2 verbatim),
`paper.store` reads and writes verdicts (K3), and `news_vetoes` is demo-owned. Because the roster object
`STRATEGY_C` carries no verdicts, `paper` and `paper_check` already run C end to end in this phase and C
simply never buys until phase 5 hands it stored verdicts (verified: the whole `test_paper_command.py`,
`test_paper_check.py` and `test_explain.py` suites pass with C on the roster, after the one-line
`ROSTER_IDS` edit in `test_paper_check.py` below).

## Interface Contract

**Deletes:** nothing.
**Renames:** test `test_migrate.py::test_repo_has_001_to_003` -> `test_repo_has_001_to_004`;
test `test_paper_roster.py::test_the_roster_is_the_four_handover_entries_in_sort_order` ->
`test_the_roster_is_the_handover_entries_in_sort_order`. No source symbol renamed.
**Creates:**
- `db/migrations/004_news_veto.sql` (K2 byte for byte; verified with `diff` against the index's K2 block).
- `seer_engine.paper.roster.RosterEntry.gate_applicable: bool = True` (last field, default).
- `ROSTER` entry `C` (K4 verbatim), appended last (sort 5). `ROSTER_IDS == ("SPY", "A", "F4-MOM12-N20-TREND", "F1-SPY-SMA200-M", "C")`.
- `seer_engine.paper.store.NewsVerdict` (frozen, slots dataclass; K3 fields in K3 order).
- `seer_engine.paper.store.has_vetoes(conn, strategy_id: str, session: date) -> bool`
- `seer_engine.paper.store.write_vetoes(conn, strategy_id: str, session: date, verdicts: Sequence[NewsVerdict]) -> int`
- `seer_engine.paper.store.read_vetoes(conn, strategy_id: str, session: date) -> tuple[NewsVerdict, ...]` (by rank)
- `seer_engine.paper.store.allowed_between(conn, strategy_id: str, start: date, end: date) -> dict[date, frozenset[str]]`
- `engine/tests/test_paper_store_vetoes.py`.
**Signature changes:** `roster.backtest_gate(e)` keeps its signature; it returns
`{"passed": False, "applicable": False, "note": e.gate_note}` when `e.gate_applicable` is False (C only),
and exactly the old `{"passed": False, "note": e.gate_note}` (same keys, same order) otherwise.
`demo.DEMO_TABLES` gains `"news_vetoes"` (after `"book_trades"`).
**Behaviour notes the other phases code against:**
- `write_vetoes`: plain INSERTs, no upsert; the caller checks `has_vetoes` first in the same transaction.
  Validates **before** writing (nothing written on a bad input): `session` must be an NYSE session
  (`ValueError`; `TypeError` for a non-date or a datetime); every item a `NewsVerdict` (`TypeError`);
  `rank` an int, not bool (`TypeError`); ranks exactly `1..n`, any order (`ValueError`); symbols non-empty and
  unique (`ValueError`); `verdict` in `strategies.c.VERDICTS`, case-sensitive (`ValueError`); `reason` a `str`
  (may be empty; `TypeError`); `model` `str | None` (`TypeError`); `prompt_version` non-empty (`ValueError`);
  each headline a `Mapping` (`TypeError`); `earnings_date` a date or None (`TypeError`); `decided_at` a tz-aware
  `datetime` (`ValueError`). Empty `verdicts` -> returns 0, writes nothing. A duplicate is
  `psycopg.errors.UniqueViolation`; an unknown strategy id is `psycopg.errors.ForeignKeyViolation`. Rows are
  written in rank order. Headlines are stored as a jsonb list of `dict(h)`.
- `read_vetoes` returns headlines as `tuple[dict, ...]` and `decided_at` as psycopg's aware datetime (equal
  instant to what was written; the tz may be the server's).
- `allowed_between`: sessions `start..end` inclusive, `verdict = 'allow'` only, via `strategies.c.allowed_map`.
  A session with no allowed symbol **may be absent** (depends on phase 1's `allowed_map`): callers must use
  `.get(session, frozenset())` — K1 `NewsVeto.picks` already does. `start > end` -> `{}`. Never raises on
  data; `TypeError` only for non-date arguments.
- None of the four functions commit or roll back.
**Requires (from earlier phases):** Phase 1's `engine/src/seer_engine/strategies/c.py` exporting exactly (K1):
`STRATEGY_C`, `STRATEGY_C_PARAMS`, `STRATEGY_C_ID`, `FROZEN_MODEL`, `PROMPT_VERSION`, `SYSTEM_PROMPT`,
`USER_TEMPLATE`, `VERDICTS`, `allowed_map`, `NewsVeto` (with `.id`, `.lookback`, `.allowed`), `CParams.as_dict()`.
`strategies.c` must not import `seer_engine.paper.*` (store and roster import it; a cycle would break import).
**C's pin depends on phase 1's exact `CParams.as_dict()` and prompt texts** — see Step 5's note.
**Leaves alone (owned by others):** `strategies/c.py` (Phase 1); `finnhub.py`, `llm.py` (Phase 3);
`commands/veto.py` (Phase 4); `commands/paper.py`, `commands/paper_check.py`, `commands/explain.py` (Phase 5);
`web/**` incl. `web/scripts/seed-demo.mjs` (Phase 6); `.github/workflows/*`, docs, `engine/package_readme.md`,
`.env.example` (Phase 7). Closed records (`db/migrations/00[1-3]_*.sql`, registry, runners, `strategies/a.py`,
`paper/bracket.py`, `paper/replay.py`, ...) untouched.

## Files

| File | Action | What changes |
|---|---|---|
| `db/migrations/004_news_veto.sql` | create | K2 verbatim: `C` roster row (upsert) + `news_vetoes` table |
| `engine/src/seer_engine/paper/roster.py` | modify | docstring (lines 3–4, 9–15, 28–29), import `STRATEGY_C, STRATEGY_C_PARAMS` (after line 50), `RosterEntry` docstring + `gate_applicable` field (lines 68–86), comment line 111, entry `C` appended (after line 183), `backtest_gate` (lines 256–258) |
| `engine/src/seer_engine/paper/store.py` | modify | docstring bullet (after line 16), import `VERDICTS, allowed_map` (after line 46), new section appended after line 1032 |
| `engine/src/seer_engine/demo.py` | modify | docstring paragraph (after line 11), `"news_vetoes"` in `DEMO_TABLES` (after line 38) |
| `engine/tests/test_migrate.py` | modify | imports (line 5), `C_ROW` (after 15), `_upto` helper (before line 48), 003 tests pinned to a schema at 003 (lines 66–67, 124–125, 150–154, 157–159, 171, 186), new 004 tests appended |
| `engine/tests/test_paper_roster.py` | modify | docstring, imports, PINS `C`, roster ids/sorts, `C` object checks, gate assertion, lookbacks, new C tests appended |
| `engine/tests/test_demo.py` | modify | seed a `news_vetoes` row; assert it is demo-owned and purged |
| `engine/tests/test_paper_store_vetoes.py` | create | K3 round trip, order, validation, `has_vetoes`, `allowed_between` |
| `engine/tests/test_paper_store.py` | modify | line 58: `read_strategies` now returns five rows (C last) |
| `engine/tests/test_paper_check.py` | modify | line 51: `ROSTER_IDS` gains `"C"` (the only phase-2 edit in a phase-5 test file; see Handoffs) |

## Existing tests that see C — audit

Grepped `engine/tests` for `ROSTER`, `ROSTER_IDS`, `len(ROSTER)`, `F1-SPY-SMA200-M` and four-row assumptions, then
ran every affected file in a scratch copy with this phase applied (phase 1 stubbed from K1):

| Test | Effect of phase 2 | Fix |
|---|---|---|
| `test_migrate.py::test_repo_has_001_to_003` | still passes (`ALL[:3]`) but is the migration list | renamed `_to_004`, asserts `ALL[:4]` |
| `test_migrate.py::test_003_on_a_fresh_schema_writes_the_roster_with_spy_champion` | **fails** (C row from 004) | applies migrations up to 003 only (`_upto`) |
| `test_migrate.py::test_003_sql_is_idempotent` | **fails**: re-running 003 after 004 deletes the unreferenced C row | runs on a schema at 003 (`pg_empty` + `_upto`) |
| `test_migrate.py::test_003_on_neon_flips_the_champion_and_drops_unreferenced_b_and_c` | **fails** (`== ["003_paper.sql"]`, `set(rows) == ROSTER_IDS`) | applies up to 003 only |
| `test_migrate.py::test_003_keeps_a_referenced_b_or_c[orders]` | **fails** (004 re-inserts C, so "C gone" is false) | applies up to 003 only (both params) |
| `test_paper_roster.py` (6 tests) | **fail** (5 entries, PINS, unpack of 4, gate dict, lookbacks) | edited below |
| `test_demo.py::test_purge_empties_demo_tables_and_keeps_strategies_and_dividends` | **fails** (`news_vetoes` empty in the seed) | seed one verdict row |
| `test_paper_store.py::test_read_strategies_returns_the_roster_rows_in_sort_order` | **fails** (5 rows) | add `"C"` |
| `test_paper_check.py::test_fresh_database_reports_every_strategy_not_started` | **fails** (`tuple(found) == ROSTER_IDS`, 5 vs 4) | `ROSTER_IDS` gains `"C"`; with that, every test in the file passes (C starts on the same first night with `STRATEGY_C` buying nothing, so its live state equals its replay; `(sessions, paper_start, last_session)` match the other four) |
| `test_paper_command.py` (all) | pass unchanged | none — its assertions are per strategy id |
| `test_explain.py` (all) | pass unchanged | none |
| `test_strategy_purity.py` | pass (roster imports `strategies.c`, which is pure; `paper/store.py` is excluded as impure) | none |
| `test_paper_replay.py` | pass unchanged | none |

Full engine suite with phase 2 applied: see Verification.

## Implementation Steps

### Step 1: Migration 004
**File:** `db/migrations/004_news_veto.sql` (new)
**Change:** K2 verbatim. Do not reformat: the file must equal the index's K2 block byte for byte
(check: `sed -n '/^### K2/,/^### K3/p' STRATEGY_C_NEWS_VETO_PLAN.md | sed -n '/^```sql/,/^```$/p' | sed '1d;$d' | diff - db/migrations/004_news_veto.sql`).
**Code:**
```sql
-- Strategy C (handover D1, D7). 003 deleted the unreferenced 'C' row; this puts the roster row back.
INSERT INTO strategies (id, name, sub, icon, is_champion, is_benchmark, sort, engine, rules_id) VALUES
  ('C', 'C · News veto', 'A''s picks, LLM can veto on news', 'gavel', false, false, 5, 'bracket', 'design-v0')
ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, sub = EXCLUDED.sub, icon = EXCLUDED.icon,
  is_champion = EXCLUDED.is_champion, is_benchmark = EXCLUDED.is_benchmark, sort = EXCLUDED.sort,
  engine = EXCLUDED.engine, rules_id = EXCLUDED.rules_id;

-- One row per (strategy, session, candidate): the news check `veto` ran the night before the session.
-- Replay (paper_check) reads these; the LLM is never re-asked (handover §2, D8).
CREATE TABLE IF NOT EXISTS news_vetoes (
  strategy_id     text NOT NULL REFERENCES strategies(id),
  session_date    date NOT NULL,                 -- the session the candidate would be bought for
  rank            int NOT NULL CHECK (rank >= 1),-- rank in A's list (1..max_candidates)
  symbol          text NOT NULL,
  verdict         text NOT NULL CHECK (verdict IN ('allow', 'veto', 'failed')),
  reason          text NOT NULL,                 -- the LLM's sentence, or why the check failed (redacted)
  model           text,                          -- LLM_MODEL as configured that night; NULL when unset
  prompt_version  text NOT NULL,                 -- 'c-veto-v1'
  headlines       jsonb NOT NULL DEFAULT '[]',   -- [{id, datetime (ISO UTC), source, headline}], newest first
  earnings_date   date,                          -- earnings found inside the holding window, if any
  decided_at      timestamptz NOT NULL,          -- the veto run's start: the news cutoff
  PRIMARY KEY (strategy_id, session_date, symbol),
  UNIQUE (strategy_id, session_date, rank)
);
```
**Impact:** every `pg` fixture schema now has a fifth `strategies` row `C` and the `news_vetoes` table. On Neon,
the nightly `Migrate` step applies it on the first run after the merge; the four existing rows are not touched
(the upsert only names `C`; proven by `test_004_on_a_post_003_schema_adds_c_and_leaves_the_roster_rows_alone`).

### Step 2: Roster — `gate_applicable`, entry `C`, `backtest_gate`
**File:** `engine/src/seer_engine/paper/roster.py`

2a. Module docstring, lines 3–4. Replace
```text
Pure: no database, no clock, no I/O. Four portfolios paper-trade every night from the same
first paper day; this module is the single place that says what each one is.
```
with
```text
Pure: no database, no clock, no I/O. Five portfolios paper-trade every night, each on its own
paper clock; this module is the single place that says what each one is.
```

2b. Lines 11–15. Replace
```text
  under their own ``MONTHLY_HOLD`` rules (the book engine).

Each entry's display fields (``name`` .. ``sort``, ``engine``, ``rules_id``) equal the row that
``db/migrations/003_paper.sql`` inserts; ``tests/test_paper_roster.py`` checks that against a
migrated database.
```
with
```text
  under their own ``MONTHLY_HOLD`` rules (the book engine).
- ``C``: Strategy C (``strategies.c.STRATEGY_C`` with ``STRATEGY_C_PARAMS``) under
  ``DESIGN_V0``: A's ranked candidates minus every symbol the stored news check did not
  allow (strategy-c-news-veto handover D1, D5). The roster object carries no verdicts, so
  it never buys on its own; ``paper`` and ``paper_check`` hand the engine a copy carrying
  the stored verdicts.

Each entry's display fields (``name`` .. ``sort``, ``engine``, ``rules_id``) equal the row that
``db/migrations/003_paper.sql`` (``C``: ``004_news_veto.sql``) inserts;
``tests/test_paper_roster.py`` checks that against a migrated database.
```

2c. Lines 28–29. Replace
```text
``backtest_gate`` is a display fact for the go-live checklist (D12), not part of the spec:
correcting its note does not reset a paper clock. Every entry is ``passed: false`` today.
```
with
```text
``backtest_gate`` is a display fact for the go-live checklist (D12), not part of the spec:
correcting its note does not reset a paper clock. Every entry is ``passed: false`` today.
An entry with ``gate_applicable=False`` (C, an LLM strategy: design §1 item 5, handover D9)
also says ``applicable: false``; the four quant/benchmark entries' gate dicts are unchanged.
```

2d. Imports, line 50. Replace
```python
from seer_engine.strategies.base import Strategy
```
with
```python
from seer_engine.strategies.base import Strategy
from seer_engine.strategies.c import STRATEGY_C, STRATEGY_C_PARAMS
```

2e. `RosterEntry` docstring end + fields, lines 68–86. Replace
```python
    ``lookback`` is the bars through a data date ``obj`` reads (1 for the benchmark, which
    reads only the session's own bar).
    """
```
with
```python
    ``lookback`` is the bars through a data date ``obj`` reads (1 for the benchmark, which
    reads only the session's own bar). ``gate_applicable`` is ``False`` only for an entry the
    quant backtest gate does not apply to (C); it changes ``backtest_gate``, never the spec.
    """
```
and replace
```python
    lookback: int
    gate_note: str

```
with
```python
    lookback: int
    gate_note: str
    gate_applicable: bool = True

```
(The field is last and defaulted, so the four existing constructor calls are unchanged.)

2f. Comment, line 111. Replace
```python
# Sorted by ``sort``; every value is the 003 migration's INSERT row for the same id.
```
with
```python
# Sorted by ``sort``; every value is the 003 (C: 004) migration's INSERT row for the same id.
```

2g. Append entry `C` (K4) as the last tuple element, lines 182–184. Replace
```python
        gate_note="P7a dev window only; failed max DD <= 15% (18.7%) and >= 100 trades (11)",
    ),
)
```
with
```python
        gate_note="P7a dev window only; failed max DD <= 15% (18.7%) and >= 100 trades (11)",
    ),
    RosterEntry(
        id="C",
        name="C · News veto",
        sub="A's picks, LLM can veto on news",
        icon="gavel",
        is_champion=False,
        is_benchmark=False,
        sort=5,
        engine="bracket",
        rules=DESIGN_V0,
        obj=STRATEGY_C,
        object_name="STRATEGY_C",
        params=STRATEGY_C_PARAMS,
        registry_id=None,
        lookback=STRATEGY_C.lookback,
        gate_note="Backtest gate: not applicable (LLM strategy, design §1 item 5)",
        gate_applicable=False,
    ),
)
```
`MAX_LOOKBACK_BARS` stays 253 (`STRATEGY_C.lookback == STRATEGY_A.lookback == 200`). `spec(e)` needs no change:
for C it yields `object_id = STRATEGY_C.id` (`"C-news-veto"`) and `params = STRATEGY_C_PARAMS.as_dict()`.

2h. `backtest_gate`, lines 256–258. Replace
```python
def backtest_gate(e: RosterEntry) -> dict[str, Any]:
    """Contract C2 ``params.backtest_gate``: no roster entry has passed a backtest gate."""
    return {"passed": False, "note": e.gate_note}
```
with
```python
def backtest_gate(e: RosterEntry) -> dict[str, Any]:
    """Contract C2 ``params.backtest_gate``: no roster entry has passed a backtest gate.

    An entry the gate does not apply to (C: design §1 item 5, handover D9) also says
    ``"applicable": False``; it still counts as not passed. The applicable entries' dict is
    exactly ``{"passed": False, "note": ...}``, as before C existed.
    """
    if not e.gate_applicable:
        return {"passed": False, "applicable": False, "note": e.gate_note}
    return {"passed": False, "note": e.gate_note}
```
**Impact:** `ROSTER` has five entries; `paper` freezes C on its first night (its own `paper_start`) and steps it
with the no-verdict `STRATEGY_C`, which buys nothing until phase 5. The four digests are unchanged (verified:
SPY `ca309ea7…`, A `37cd89be…`, F4 `6c55c13a…`, F1 `e7fbb32d…`), and so are their gate dicts.

### Step 3: Verdict store
**File:** `engine/src/seer_engine/paper/store.py`

3a. Docstring, after line 16 (`- Every engine writes ``equity_snapshots``.`). Insert:
```text
- Strategy C's news check (migration 004): ``news_vetoes`` rows, written once per session by
  ``veto`` and read by ``paper`` / ``paper_check`` as the verdicts C decides and replays from.
```

3b. Imports, line 46. Replace
```python
from seer_engine.sim.rules import SHARE_QUANTUM
```
with
```python
from seer_engine.sim.rules import SHARE_QUANTUM
from seer_engine.strategies.c import VERDICTS, allowed_map
```
(`Mapping`, `Sequence`, `Any`, `datetime`, `date`, `Jsonb`, `psycopg`, `_date`, `_session` are already imported
or defined in this module.)

3c. Append at the end of the file (after line 1032, the end of `load_market_window`):
```python
# --------------------------------------------------------------------------- news vetoes (strategy C)


@dataclass(frozen=True, slots=True)
class NewsVerdict:
    """One ``news_vetoes`` row: the news check of one candidate for one session (migration 004).

    ``headlines`` are the lean items the LLM saw, newest first: ``{"id": int, "datetime":
    "YYYY-MM-DDTHH:MM:SSZ", "source": str, "headline": str}`` (no summaries). ``decided_at`` is
    the ``veto`` run's start, tz-aware: the news cutoff.
    """

    rank: int
    symbol: str
    verdict: str  # one of strategies.c.VERDICTS
    reason: str
    model: str | None
    prompt_version: str
    headlines: tuple[Mapping[str, Any], ...]
    earnings_date: date | None
    decided_at: datetime


_VETO_COLUMNS = "rank, symbol, verdict, reason, model, prompt_version, headlines, earnings_date, decided_at"


def _check_verdicts(verdicts: Sequence[NewsVerdict]) -> None:
    """TypeError/ValueError unless ``verdicts`` is a complete, well-formed night for one session."""
    for v in verdicts:
        if not isinstance(v, NewsVerdict):
            raise TypeError(f"verdicts must be NewsVerdict, got {type(v).__name__}")
        if isinstance(v.rank, bool) or not isinstance(v.rank, int):
            raise TypeError(f"rank must be an int, got {type(v.rank).__name__}")
        if not isinstance(v.symbol, str) or not v.symbol:
            raise ValueError(f"rank {v.rank}: symbol must be a non-empty str")
        if v.verdict not in VERDICTS:
            raise ValueError(f"{v.symbol}: verdict {v.verdict!r} is not one of {VERDICTS}")
        if not isinstance(v.reason, str):
            raise TypeError(f"{v.symbol}: reason must be a str, got {type(v.reason).__name__}")
        if v.model is not None and not isinstance(v.model, str):
            raise TypeError(f"{v.symbol}: model must be a str or None, got {type(v.model).__name__}")
        if not isinstance(v.prompt_version, str) or not v.prompt_version:
            raise ValueError(f"{v.symbol}: prompt_version must be a non-empty str")
        if not all(isinstance(h, Mapping) for h in v.headlines):
            raise TypeError(f"{v.symbol}: every headline must be a mapping")
        if v.earnings_date is not None:
            _date(f"{v.symbol}: earnings_date", v.earnings_date)
        if not isinstance(v.decided_at, datetime) or v.decided_at.utcoffset() is None:
            raise ValueError(f"{v.symbol}: decided_at must be a tz-aware datetime")
    ranks = sorted(v.rank for v in verdicts)
    if ranks != list(range(1, len(verdicts) + 1)):
        raise ValueError(f"ranks must be 1..{len(verdicts)} with no gap or repeat, got {ranks}")
    symbols = [v.symbol for v in verdicts]
    if len(set(symbols)) != len(symbols):
        raise ValueError(f"symbols must be unique, got {symbols}")


def has_vetoes(conn: psycopg.Connection, strategy_id: str, session: date) -> bool:
    """True when ``news_vetoes`` holds any row for (``strategy_id``, ``session``): the news
    check for that session already ran."""
    _date("session", session)
    row = conn.execute(
        "SELECT EXISTS (SELECT 1 FROM news_vetoes WHERE strategy_id = %s AND session_date = %s)",
        (strategy_id, session),
    ).fetchone()
    return bool(row[0])


def write_vetoes(
    conn: psycopg.Connection, strategy_id: str, session: date, verdicts: Sequence[NewsVerdict]
) -> int:
    """Insert one ``news_vetoes`` row per verdict for ``session``; returns the rows written.

    Plain INSERTs: a row already stored for (strategy, session, symbol) or (strategy, session,
    rank) is a database error, so the caller checks :func:`has_vetoes` first in the same
    transaction. Validates first and writes nothing on a bad input: ranks 1..n without gaps or
    repeats, unique symbols, ``verdict`` in ``strategies.c.VERDICTS``, tz-aware ``decided_at``.
    An empty ``verdicts`` writes nothing and returns 0.
    """
    _session("session", session)
    verdicts = tuple(verdicts)
    _check_verdicts(verdicts)
    if not verdicts:
        return 0
    with conn.cursor() as cur:
        cur.executemany(
            f"INSERT INTO news_vetoes (strategy_id, session_date, {_VETO_COLUMNS}) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            [
                (
                    strategy_id,
                    session,
                    v.rank,
                    v.symbol,
                    v.verdict,
                    v.reason,
                    v.model,
                    v.prompt_version,
                    Jsonb([dict(h) for h in v.headlines]),
                    v.earnings_date,
                    v.decided_at,
                )
                for v in sorted(verdicts, key=lambda v: v.rank)
            ],
        )
    return len(verdicts)


def read_vetoes(conn: psycopg.Connection, strategy_id: str, session: date) -> tuple[NewsVerdict, ...]:
    """Every stored verdict of (``strategy_id``, ``session``), by rank; empty when none."""
    _date("session", session)
    rows = conn.execute(
        f"SELECT {_VETO_COLUMNS} FROM news_vetoes WHERE strategy_id = %s AND session_date = %s ORDER BY rank",
        (strategy_id, session),
    ).fetchall()
    return tuple(
        NewsVerdict(
            rank=int(rank),
            symbol=symbol,
            verdict=verdict,
            reason=reason,
            model=model,
            prompt_version=prompt_version,
            headlines=tuple(dict(h) for h in (headlines or [])),
            earnings_date=earnings_date,
            decided_at=decided_at,
        )
        for rank, symbol, verdict, reason, model, prompt_version, headlines, earnings_date, decided_at in rows
    )


def allowed_between(conn: psycopg.Connection, strategy_id: str, start: date, end: date) -> dict[date, frozenset[str]]:
    """``{session: symbols whose stored verdict is "allow"}`` for sessions ``start..end``
    inclusive, via ``strategies.c.allowed_map``. A session with no allowed symbol (all vetoed,
    all failed, or no rows: C sits it out) may be absent, so callers look up with
    ``.get(session, frozenset())``. Empty when ``start > end``."""
    _date("start", start)
    _date("end", end)
    rows = conn.execute(
        "SELECT session_date, symbol, verdict FROM news_vetoes "
        "WHERE strategy_id = %s AND session_date BETWEEN %s AND %s ORDER BY session_date, rank",
        (strategy_id, start, end),
    ).fetchall()
    return allowed_map((d, s, v) for d, s, v in rows)
```
**Impact:** additive; nothing existing calls these yet (phase 4 `veto` calls `has_vetoes`/`write_vetoes`,
phase 5 calls `allowed_between`, phase 6 reads the table from TypeScript).

### Step 4: Demo-owned `news_vetoes`
**File:** `engine/src/seer_engine/demo.py`

4a. Docstring, after line 11 (`the rows but resets those two columns, so the first real ``paper`` run starts cleanly.`). Insert:
```text

``news_vetoes`` (migration 004) is demo-owned as well: the demo seed writes verdict rows for
C, and real verdicts never coexist with a demo run (``veto`` purges first, like ``paper``).
```

4b. `DEMO_TABLES`, lines 37–38. Replace
```python
    "book_trades",
    "bars",
```
with
```python
    "book_trades",
    "news_vetoes",
    "bars",
```
**Impact:** `purge_demo` truncates `news_vetoes`. `strategies` stays out of the list. `TRUNCATE news_vetoes`
needs no CASCADE (nothing references it).

### Step 5: `test_paper_roster.py`
**File:** `engine/tests/test_paper_roster.py`

5a. Docstring lines 3 and 6–7. Replace
```text
- The display fields equal the rows migration 003 inserts.
```
with
```text
- The display fields equal the rows migrations 003 and 004 (``C``) insert.
```
and replace
```text
- The spec digests are pinned. A failing pin means a roster strategy changed: give it a NEW
  id (its own paper clock) instead of editing the pin.
```
with
```text
- The spec digests are pinned. A failing pin means a roster strategy changed: give it a NEW
  id (its own paper clock) instead of editing the pin.
- C (strategy-c-news-veto D1, D5, D9) is A's spec plus the frozen news check; its backtest gate
  says "not applicable"; the four earlier entries' digests and gate dicts are unchanged.
```

5b. Imports, line 34. Replace
```python
from seer_engine.strategies.a import STRATEGY_A, STRATEGY_A_PARAMS
```
with
```python
from seer_engine.strategies.a import STRATEGY_A, STRATEGY_A_PARAMS
from seer_engine.strategies.c import (
    FROZEN_MODEL,
    PROMPT_VERSION,
    STRATEGY_C,
    STRATEGY_C_ID,
    STRATEGY_C_PARAMS,
    SYSTEM_PROMPT,
    USER_TEMPLATE,
)
```

5c. `PINS`, lines 45–46. Replace
```python
    F1: "e7fbb32d1cc4e11b2d0d9b941ab01ac1a545e49a08c11bf8c70da5c54cad9e2f",
}
```
with
```python
    F1: "e7fbb32d1cc4e11b2d0d9b941ab01ac1a545e49a08c11bf8c70da5c54cad9e2f",
    "C": "6cea6cb8de993f6a3f2d7ef4b48c878654a57df16cab87f72a95e9dd49a1b762",
}
```
**Note on C's pin.** `6cea6cb8…b762` was computed by `spec_digest(spec(entry("C")))` in a scratch copy where
`strategies/c.py` was written from K1 with these readings, which phase 1 must match (the reconciler should
copy them into phase 1's plan if phase 1 states otherwise):
- `SYSTEM_PROMPT` and `USER_TEMPLATE` are the K1 text blocks exactly, lines joined by `"\n"`, **no trailing
  newline**; `USER_TEMPLATE` ends with `{headline_lines}`.
- `CParams.as_dict()` keys: `a.rsi_max`, `a.limit_atr`, `a.tp_atr`, `a.sl_atr`, `a.min_dollar_volume` (values from
  `STRATEGY_A_PARAMS.as_dict()`), `a_object="STRATEGY_A"`, `a_object_id="A"`, `max_candidates="10"`,
  `news_days="3"`, `max_headlines="20"`, `max_summary_chars="280"`, `earnings_sessions="5"`, `model="glm-5.3"`,
  `prompt_version="c-veto-v1"`, `temperature="0"`, `thinking="disabled"`, `max_tokens="1024"`,
  `system_prompt=SYSTEM_PROMPT`, `user_template=USER_TEMPLATE` — no other key (no bare `"a"` key).
- `STRATEGY_C.id == "C-news-veto"`.

**Reconciliation check (2026-10-04):** phase 1's plan code (`SYSTEM_PROMPT`/`USER_TEMPLATE` without a trailing
newline, the 19 `as_dict` keys in the order above, `STRATEGY_C.id == "C-news-veto"`) matches every reading above. Built
in a scratch copy with phase 1's `c.py` and this phase's roster, `spec_digest(spec(entry("C")))` printed
`6cea6cb8de993f6a3f2d7ef4b48c878654a57df16cab87f72a95e9dd49a1b762` and the four P4 digests unchanged, so the pin
stands as written.

**Re-pin rule.** If `test_paper_roster.py`'s pin test fails **only for `"C"`** (the four P4 pins pass), re-pin `"C"`
to the digest the command below prints. That is legal for C alone: C has never been frozen anywhere (no paper clock,
no Neon row with its digest), so no recorded spec changes. Never re-pin any of the four P4 entries.
C has never been frozen anywhere (no paper clock), so the implementer of **this** phase pins whatever
`engine/.venv/bin/python -c 'from seer_engine.paper.roster import entry, spec, spec_digest; print(spec_digest(spec(entry("C"))))'`
prints once phase 1 has landed, **provided** `test_c_spec_is_a_plus_the_frozen_news_check` (5h) passes unchanged
— that test fixes every non-prompt value, so a differing digest can only come from the prompt texts' exact bytes,
which are phase 1's to own. After this phase merges, C's pin is frozen like the other four.

5d. Lines 65–68. Replace
```python
def test_the_roster_is_the_four_handover_entries_in_sort_order():
    assert ROSTER_IDS == ("SPY", "A", F4, F1)
    assert [e.sort for e in ROSTER] == [1, 2, 3, 4]
    assert "B" not in ROSTER_IDS and "C" not in ROSTER_IDS
```
with
```python
def test_the_roster_is_the_handover_entries_in_sort_order():
    assert ROSTER_IDS == ("SPY", "A", F4, F1, "C")
    assert [e.sort for e in ROSTER] == [1, 2, 3, 4, 5]
    assert "B" not in ROSTER_IDS
```

5e. Line 82. Replace
```python
    spy, a, f4, f1 = (entry(i) for i in ROSTER_IDS)
```
with
```python
    spy, a, f4, f1, c = (entry(i) for i in ROSTER_IDS)
```
and line 89, replace
```python
    assert (f4.registry_id, f1.registry_id) == (F4, F1)
```
with
```python
    assert (f4.registry_id, f1.registry_id) == (F4, F1)
    assert c.engine == "bracket" and c.rules is DESIGN_V0 and c.rules_id == "design-v0"
    assert c.obj is STRATEGY_C and c.params is STRATEGY_C_PARAMS and c.object_name == "STRATEGY_C"
    assert c.registry_id is None
    assert c.params.a is STRATEGY_A_PARAMS
```

5f. Line 154 (in `test_strategy_params_is_contract_c2`). Replace
```python
        assert p["backtest_gate"] == backtest_gate(e) == {"passed": False, "note": e.gate_note}
```
with
```python
        assert p["backtest_gate"] == backtest_gate(e)
        assert p["backtest_gate"]["passed"] is False and p["backtest_gate"]["note"] == e.gate_note
```
(The exact four-entry dict moves to `test_the_four_earlier_gate_dicts_are_unchanged`, 5h.)

5g. Line 170. Replace
```python
    assert {e.id: e.lookback for e in ROSTER} == {"SPY": 1, "A": 200, F4: 253, F1: 200}
```
with
```python
    assert {e.id: e.lookback for e in ROSTER} == {"SPY": 1, "A": 200, F4: 253, F1: 200, "C": 200}
```

5h. Append at the end of the file (after `test_entry_rejects_an_id_off_the_roster`):
```python


# ---- C (strategy-c-news-veto D1, D5, D9) ---------------------------------------------------------


def test_the_four_earlier_gate_dicts_are_unchanged():
    for sid in ("SPY", "A", F4, F1):
        e = entry(sid)
        assert e.gate_applicable is True
        gate = backtest_gate(e)
        assert gate == {"passed": False, "note": e.gate_note}
        assert list(gate) == ["passed", "note"]


def test_c_gate_is_not_applicable_and_not_passed():
    c = entry("C")
    assert c.gate_applicable is False
    assert c.gate_note == "Backtest gate: not applicable (LLM strategy, design §1 item 5)"
    assert backtest_gate(c) == {"passed": False, "applicable": False, "note": c.gate_note}
    assert strategy_params(c)["backtest_gate"] == backtest_gate(c)


def test_c_spec_is_a_plus_the_frozen_news_check():
    s = spec(entry("C"))
    assert (s["engine"], s["object"], s["object_id"], s["registry_id"], s["registry_digest"], s["rules_id"]) == (
        "bracket", "STRATEGY_C", STRATEGY_C_ID, None, None, "design-v0",
    )
    assert STRATEGY_C.id == STRATEGY_C_ID == "C-news-veto"
    assert s["rules"] == rules_dict(DESIGN_V0) == spec(entry("A"))["rules"]
    assert s["initial_idr"] == "20000000"
    p = s["params"]
    assert p == STRATEGY_C_PARAMS.as_dict()
    assert {k[2:]: v for k, v in p.items() if k.startswith("a.")} == STRATEGY_A_PARAMS.as_dict()
    assert (p["a_object"], p["a_object_id"]) == ("STRATEGY_A", STRATEGY_A.id)
    assert {k: p[k] for k in (
        "max_candidates", "news_days", "max_headlines", "max_summary_chars", "earnings_sessions",
        "model", "prompt_version", "temperature", "thinking", "max_tokens",
    )} == {
        "max_candidates": "10",
        "news_days": "3",
        "max_headlines": "20",
        "max_summary_chars": "280",
        "earnings_sessions": "5",
        "model": FROZEN_MODEL,
        "prompt_version": PROMPT_VERSION,
        "temperature": "0",
        "thinking": "disabled",
        "max_tokens": "1024",
    }
    assert (FROZEN_MODEL, PROMPT_VERSION) == ("glm-5.3", "c-veto-v1")
    assert (p["system_prompt"], p["user_template"]) == (SYSTEM_PROMPT, USER_TEMPLATE)


def test_c_digest_moves_with_the_model_and_the_prompt():
    s = spec(entry("C"))
    for key, value in (("model", "glm-9"), ("prompt_version", "c-veto-v2"), ("system_prompt", "x")):
        changed = json.loads(json.dumps(s))
        changed["params"][key] = value
        assert spec_digest(changed) != spec_digest(s), key


def test_the_roster_c_object_carries_no_verdicts():
    assert len(entry("C").obj.allowed) == 0
```
`test_display_fields_equal_the_migration_rows` and `test_strategy_params_round_trip_through_jsonb` need no edit:
they iterate `ROSTER` against the `pg` fixture, which now applies 004, so C's display row and pin are covered.

### Step 6: `test_migrate.py`
**File:** `engine/tests/test_migrate.py`

6a. Imports, line 5. Replace
```python
from datetime import date

import psycopg
```
with
```python
import shutil
from datetime import date, datetime, timezone
from pathlib import Path

import psycopg
```

6b. After line 15 (`ROSTER_IDS = {...}` — unchanged: it is the roster **003** writes). Insert:
```python
C_ROW = ("C", "C · News veto", "A's picks, LLM can veto on news", "gavel", False, False, 5, "bracket", "design-v0")
```

6c. Before `def _neon_before_003` (line 48). Insert:
```python
def _upto(tmp_path: Path, last: str) -> Path:
    """A migrations directory holding the repo's files up to and including ``last``: the
    schema as it stood when ``last`` was the newest migration."""
    out = tmp_path / f"upto-{last}"
    out.mkdir()
    for p in migration_files(MIGRATIONS_DIR):
        if p.name <= last:
            shutil.copy(p, out / p.name)
    return out


```

6d. Lines 66–67. Replace
```python
def test_repo_has_001_to_003():
    assert ALL[:3] == ["001_init.sql", "002_engine.sql", "003_paper.sql"]
```
with
```python
def test_repo_has_001_to_004():
    assert ALL[:4] == ["001_init.sql", "002_engine.sql", "003_paper.sql", "004_news_veto.sql"]
```

6e. Lines 124–125. Replace
```python
def test_003_on_a_fresh_schema_writes_the_roster_with_spy_champion(pg_empty):
    apply_migrations(pg_empty, MIGRATIONS_DIR)
```
with
```python
def test_003_on_a_fresh_schema_writes_the_roster_with_spy_champion(pg_empty, tmp_path):
    apply_migrations(pg_empty, _upto(tmp_path, "003_paper.sql"))
```

6f. Lines 150–154. Replace
```python
def test_003_sql_is_idempotent(pg):
    before = (_columns(pg), _constraints(pg), _tables(pg), _strategies(pg))
    pg.execute((MIGRATIONS_DIR / "003_paper.sql").read_text(encoding="utf-8"))
    pg.commit()
    assert (_columns(pg), _constraints(pg), _tables(pg), _strategies(pg)) == before
```
with
```python
def test_003_sql_is_idempotent(pg_empty, tmp_path):
    # On the schema 003 left (before 004): 003's DELETE of an unreferenced C would undo 004's row.
    apply_migrations(pg_empty, _upto(tmp_path, "003_paper.sql"))
    pg = pg_empty
    before = (_columns(pg), _constraints(pg), _tables(pg), _strategies(pg))
    pg.execute((MIGRATIONS_DIR / "003_paper.sql").read_text(encoding="utf-8"))
    pg.commit()
    assert (_columns(pg), _constraints(pg), _tables(pg), _strategies(pg)) == before
```

6g. Lines 157–159. Replace
```python
def test_003_on_neon_flips_the_champion_and_drops_unreferenced_b_and_c(pg_empty):
    _neon_before_003(pg_empty)
    assert apply_migrations(pg_empty, MIGRATIONS_DIR) == ["003_paper.sql"]
```
with
```python
def test_003_on_neon_flips_the_champion_and_drops_unreferenced_b_and_c(pg_empty, tmp_path):
    _neon_before_003(pg_empty)
    assert apply_migrations(pg_empty, _upto(tmp_path, "003_paper.sql")) == ["003_paper.sql"]
```

6h. Line 171. Replace
```python
def test_003_keeps_a_referenced_b_or_c(pg_empty, kept):
```
with
```python
def test_003_keeps_a_referenced_b_or_c(pg_empty, tmp_path, kept):
```
and line 186 (inside the same test), replace
```python
    pg_empty.commit()
    apply_migrations(pg_empty, MIGRATIONS_DIR)
    ids = {r[0] for r in pg_empty.execute("SELECT id FROM strategies").fetchall()}
```
with
```python
    pg_empty.commit()
    apply_migrations(pg_empty, _upto(tmp_path, "003_paper.sql"))
    ids = {r[0] for r in pg_empty.execute("SELECT id FROM strategies").fetchall()}
```

6i. Append at the end of the file (after `test_003_checks_reject_unknown_values`):
```python


# ---- 004_news_veto.sql -----------------------------------------------------------------------

NEWS_VETOES_COLUMNS = [
    ("news_vetoes", "strategy_id", "text", "NO", None),
    ("news_vetoes", "session_date", "date", "NO", None),
    ("news_vetoes", "rank", "integer", "NO", None),
    ("news_vetoes", "symbol", "text", "NO", None),
    ("news_vetoes", "verdict", "text", "NO", None),
    ("news_vetoes", "reason", "text", "NO", None),
    ("news_vetoes", "model", "text", "YES", None),
    ("news_vetoes", "prompt_version", "text", "NO", None),
    ("news_vetoes", "headlines", "jsonb", "NO", "'[]'::jsonb"),
    ("news_vetoes", "earnings_date", "date", "YES", None),
    ("news_vetoes", "decided_at", "timestamp with time zone", "NO", None),
]
DECIDED = datetime(2026, 10, 5, 23, 30, tzinfo=timezone.utc)


def _veto(conn, strategy_id="C", session=date(2026, 10, 6), rank=1, symbol="NVDA", verdict="allow") -> None:
    conn.execute(
        "INSERT INTO news_vetoes (strategy_id, session_date, rank, symbol, verdict, reason, model, "
        "prompt_version, decided_at) VALUES (%s, %s, %s, %s, %s, 'r', 'glm-5.3', 'c-veto-v1', %s)",
        (strategy_id, session, rank, symbol, verdict, DECIDED),
    )


def _started_a(conn) -> None:
    """A's paper clock started, with one pending order and its state (what Neon will hold)."""
    conn.execute(
        "UPDATE strategies SET paper_start = %s, params = '{\"digest\": \"x\"}'::jsonb WHERE id = 'A'",
        (date(2026, 10, 6),),
    )
    conn.execute(
        "INSERT INTO paper_state (strategy_id, last_session, cash_usd, equity_usd, initial_cash_usd, "
        "usd_idr, pending_session, pending_decision) VALUES ('A', %s, 1000, 1000, 1000, 16530, %s, false)",
        (date(2026, 10, 5), date(2026, 10, 6)),
    )
    conn.execute(
        "INSERT INTO orders (strategy_id, session_date, slot, symbol, company, last_price, "
        "limit_price, tp_price, sl_price, shares, status) "
        "VALUES ('A', %s, 1, 'NVDA', 'NVIDIA', 180, 178, 185, 172, 10, 'pending')",
        (date(2026, 10, 6),),
    )
    conn.commit()


def _paper_rows(conn) -> list:
    return [
        conn.execute(f"SELECT x::text FROM {t} x ORDER BY x::text").fetchall()
        for t in ("paper_state", "orders", "equity_snapshots", "book_positions", "book_targets")
    ]


def test_004_on_a_fresh_schema_adds_c_last_and_the_news_vetoes_table(pg_empty):
    apply_migrations(pg_empty, MIGRATIONS_DIR)
    rows = pg_empty.execute(
        "SELECT id, name, sub, icon, is_champion, is_benchmark, sort, engine, rules_id, params, paper_start "
        "FROM strategies ORDER BY sort"
    ).fetchall()
    assert [r[0] for r in rows] == ["SPY", "A", "F4-MOM12-N20-TREND", "F1-SPY-SMA200-M", "C"]
    assert rows[-1] == (*C_ROW, {}, None)
    assert pg_empty.execute("SELECT id FROM strategies WHERE is_champion").fetchall() == [("SPY",)]
    assert [c for c in _columns(pg_empty) if c[0] == "news_vetoes"] == NEWS_VETOES_COLUMNS
    assert pg_empty.execute("SELECT count(*) FROM news_vetoes").fetchone()[0] == 0


def test_004_on_a_post_003_schema_adds_c_and_leaves_the_roster_rows_alone(pg_empty, tmp_path):
    _neon_before_003(pg_empty)
    assert apply_migrations(pg_empty, _upto(tmp_path, "003_paper.sql")) == ["003_paper.sql"]
    _started_a(pg_empty)
    before = (_strategies(pg_empty), _paper_rows(pg_empty))
    assert "news_vetoes" not in _tables(pg_empty)
    assert apply_migrations(pg_empty, MIGRATIONS_DIR) == ["004_news_veto.sql"]
    after = _strategies(pg_empty)
    assert [r for r in after if r[0] != "C"] == before[0]  # SPY, A (started), F4, F1: byte for byte
    assert [r[:9] for r in after if r[0] == "C"] == [C_ROW]
    assert _paper_rows(pg_empty) == before[1]
    assert "news_vetoes" in _tables(pg_empty)
    assert apply_migrations(pg_empty, MIGRATIONS_DIR) == []


def test_004_restyles_a_c_row_that_003_kept(pg_empty, tmp_path):
    _neon_before_003(pg_empty)
    pg_empty.execute(
        "INSERT INTO equity_snapshots (strategy_id, date, cash_usd, equity_usd) VALUES ('C', %s, 1, 1)",
        (date(2026, 10, 2),),
    )
    pg_empty.commit()
    apply_migrations(pg_empty, _upto(tmp_path, "003_paper.sql"))
    assert pg_empty.execute("SELECT name FROM strategies WHERE id = 'C'").fetchone() == ("C · LLM",)
    assert apply_migrations(pg_empty, MIGRATIONS_DIR) == ["004_news_veto.sql"]
    row = pg_empty.execute(
        "SELECT id, name, sub, icon, is_champion, is_benchmark, sort, engine, rules_id FROM strategies WHERE id = 'C'"
    ).fetchone()
    assert row == C_ROW
    assert pg_empty.execute("SELECT count(*) FROM equity_snapshots WHERE strategy_id = 'C'").fetchone()[0] == 1


def test_004_sql_is_idempotent(pg):
    _veto(pg)
    pg.commit()
    before = (_columns(pg), _constraints(pg), _tables(pg), _strategies(pg))
    rows = pg.execute("SELECT x::text FROM news_vetoes x").fetchall()
    pg.execute((MIGRATIONS_DIR / "004_news_veto.sql").read_text(encoding="utf-8"))
    pg.commit()
    assert (_columns(pg), _constraints(pg), _tables(pg), _strategies(pg)) == before
    assert pg.execute("SELECT x::text FROM news_vetoes x").fetchall() == rows


def test_004_news_vetoes_defaults_and_keys(pg):
    _veto(pg)
    headlines, earnings = pg.execute("SELECT headlines, earnings_date FROM news_vetoes").fetchone()
    assert (headlines, earnings) == ([], None)
    pg.commit()
    for dup in (
        {"rank": 2, "symbol": "NVDA"},  # (strategy, session, symbol) is the primary key
        {"rank": 1, "symbol": "AAPL"},  # (strategy, session, rank) is unique
    ):
        with pytest.raises(psycopg.errors.UniqueViolation):
            _veto(pg, **dup)
        pg.rollback()
    _veto(pg, session=date(2026, 10, 7))  # the same symbol and rank on another session is fine
    _veto(pg, strategy_id="A")  # ... and for another strategy
    pg.rollback()


def test_004_checks_reject_unknown_values(pg):
    with pytest.raises(psycopg.errors.CheckViolation):
        _veto(pg, verdict="maybe")
    pg.rollback()
    with pytest.raises(psycopg.errors.CheckViolation):
        _veto(pg, rank=0)
    pg.rollback()
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        _veto(pg, strategy_id="B")
    pg.rollback()
```
**Impact:** the 003 tests keep testing 003 exactly as before (on the schema 003 produced); the migration-list
assertions now include 004; 004 is tested fresh, on a post-003 Neon-shaped schema with A's clock started (the four
rows and their paper rows byte-identical), on a 003-kept `C` row (restyled), idempotent, and against its keys/checks.

### Step 7: `test_demo.py`
**File:** `engine/tests/test_demo.py`

7a. `_seed` docstring, line 21. Replace
```python
    The roster's ``strategies`` rows come from migration 003 (the ``pg`` fixture applies it).
```
with
```python
    The roster's ``strategies`` rows come from migrations 003 and 004 (the ``pg`` fixture
    applies them).
```

7b. Line 67. Replace
```python
    conn.execute("INSERT INTO dividends (symbol, ex_date, amount) VALUES ('SPY', %s, 1.888834)", (D,))
```
with
```python
    conn.execute(
        "INSERT INTO news_vetoes (strategy_id, session_date, rank, symbol, verdict, reason, model, "
        "prompt_version, decided_at) VALUES ('C', %s, 1, 'NVDA', 'veto', 'Earnings inside the window.', "
        "'glm-5.3', 'c-veto-v1', '2026-10-02 23:30+00')",
        (S,),
    )
    conn.execute("INSERT INTO dividends (symbol, ex_date, amount) VALUES ('SPY', %s, 1.888834)", (D,))
```

7c. Line 87. Replace
```python
    assert set(PAPER_TABLES) <= set(DEMO_TABLES)
```
with
```python
    assert set(PAPER_TABLES) <= set(DEMO_TABLES)
    assert "news_vetoes" in DEMO_TABLES
```

7d. Line 134. Replace
```python
        assert other.execute("SELECT count(*) FROM paper_state").fetchone()[0] == 0
```
with
```python
        assert other.execute("SELECT count(*) FROM paper_state").fetchone()[0] == 0
        assert other.execute("SELECT count(*) FROM news_vetoes").fetchone()[0] == 0
```
(`counts["strategies"] == len(ROSTER)` and `_clock == [(None, {})] * len(ROSTER)` already hold with five rows.)

### Step 8: New `test_paper_store_vetoes.py`
**File:** `engine/tests/test_paper_store_vetoes.py` (new)
**Code:**
```python
"""paper.store's news-veto API on Postgres (strategy-c-news-veto contract K3, migration 004):
round trip, order by rank, validation before any write, has_vetoes, allowed_between."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta, timezone

import psycopg
import pytest

from seer_engine.paper import store
from seer_engine.paper.store import NewsVerdict
from seer_engine.strategies.c import PROMPT_VERSION, VERDICTS

S1, S2, S3, S4 = date(2026, 10, 6), date(2026, 10, 7), date(2026, 10, 8), date(2026, 10, 9)
DECIDED = datetime(2026, 10, 5, 23, 31, 7, 250000, tzinfo=timezone.utc)
HEADLINES = (
    {"id": 9002, "datetime": "2026-10-05T21:10:00Z", "source": "Reuters", "headline": "NVIDIA ships a new chip"},
    {"id": 9001, "datetime": "2026-10-05T14:02:00Z", "source": "Yahoo", "headline": "Chip stocks rally"},
)


def verdict(rank: int, symbol: str, v: str = "allow", **kw) -> NewsVerdict:
    base = NewsVerdict(
        rank=rank,
        symbol=symbol,
        verdict=v,
        reason=f"{symbol}: no event risk in the window.",
        model="glm-5.3",
        prompt_version=PROMPT_VERSION,
        headlines=(),
        earnings_date=None,
        decided_at=DECIDED,
    )
    return replace(base, **kw)


NIGHT = (
    verdict(1, "NVDA", "allow", headlines=HEADLINES),
    verdict(2, "BRK.B", "veto", reason="Earnings on 2026-10-08, inside the window.", earnings_date=S3),
    verdict(3, "AAPL", "failed", reason="LLM_* is not configured", model=None),
    verdict(4, "MSFT", "allow"),
)


def count(conn) -> int:
    return conn.execute("SELECT count(*) FROM news_vetoes").fetchone()[0]


def test_verdicts_are_the_three_k2_values():
    assert VERDICTS == ("allow", "veto", "failed")


def test_write_then_read_round_trips_by_rank(pg):
    assert store.read_vetoes(pg, "C", S1) == ()
    assert store.write_vetoes(pg, "C", S1, NIGHT) == 4
    back = store.read_vetoes(pg, "C", S1)
    assert back == NIGHT
    assert back[0].headlines == HEADLINES and back[0].decided_at == DECIDED
    assert back[0].decided_at.utcoffset() is not None
    assert back[1].earnings_date == S3 and back[2].model is None


def test_rows_come_back_by_rank_whatever_the_write_order(pg):
    store.write_vetoes(pg, "C", S1, tuple(reversed(NIGHT)))
    assert [v.rank for v in store.read_vetoes(pg, "C", S1)] == [1, 2, 3, 4]
    assert [v.symbol for v in store.read_vetoes(pg, "C", S1)] == ["NVDA", "BRK.B", "AAPL", "MSFT"]


def test_headlines_are_stored_as_a_jsonb_list_newest_first(pg):
    store.write_vetoes(pg, "C", S1, NIGHT[:1])
    stored = pg.execute("SELECT headlines FROM news_vetoes WHERE symbol = 'NVDA'").fetchone()[0]
    assert stored == [dict(h) for h in HEADLINES]


def test_has_vetoes_is_per_strategy_and_session(pg):
    assert store.has_vetoes(pg, "C", S1) is False
    store.write_vetoes(pg, "C", S1, NIGHT[:2])
    assert store.has_vetoes(pg, "C", S1) is True
    assert store.has_vetoes(pg, "C", S2) is False
    assert store.has_vetoes(pg, "A", S1) is False


def test_a_second_write_for_the_session_is_a_database_error(pg):
    store.write_vetoes(pg, "C", S1, NIGHT[:2])
    pg.commit()
    with pytest.raises(psycopg.errors.UniqueViolation):
        store.write_vetoes(pg, "C", S1, NIGHT[:1])
    pg.rollback()
    assert count(pg) == 2


def test_an_empty_night_writes_nothing(pg):
    assert store.write_vetoes(pg, "C", S1, ()) == 0
    assert count(pg) == 0
    assert store.has_vetoes(pg, "C", S1) is False


def test_nothing_commits(pg):
    store.write_vetoes(pg, "C", S1, NIGHT)
    pg.rollback()
    assert count(pg) == 0


BAD = [
    pytest.param((verdict(1, "NVDA"), verdict(3, "AAPL")), ValueError, "ranks must be 1..2", id="rank-gap"),
    pytest.param((verdict(2, "NVDA"),), ValueError, "ranks must be 1..1", id="rank-not-from-1"),
    pytest.param((verdict(1, "NVDA"), verdict(1, "AAPL")), ValueError, "ranks must be 1..2", id="rank-repeat"),
    pytest.param((verdict(1, "NVDA"), verdict(2, "NVDA")), ValueError, "symbols must be unique", id="symbol-repeat"),
    pytest.param((verdict(1, "NVDA", "maybe"),), ValueError, "is not one of", id="verdict"),
    pytest.param((verdict(1, "NVDA", "Allow"),), ValueError, "is not one of", id="verdict-case"),
    pytest.param((verdict(1, ""),), ValueError, "symbol must be a non-empty str", id="symbol-empty"),
    pytest.param(
        (verdict(1, "NVDA", decided_at=datetime(2026, 10, 5, 23, 31)),), ValueError, "tz-aware", id="naive-decided-at"
    ),
    pytest.param((verdict(1, "NVDA", decided_at=S1),), ValueError, "tz-aware", id="date-decided-at"),
    pytest.param((verdict(1, "NVDA", prompt_version=""),), ValueError, "prompt_version", id="prompt-version"),
    pytest.param((verdict(1, "NVDA", reason=None),), TypeError, "reason must be a str", id="reason-none"),
    pytest.param((verdict(1, "NVDA", model=5),), TypeError, "model must be a str or None", id="model-type"),
    pytest.param((replace(verdict(1, "NVDA"), rank=True),), TypeError, "rank must be an int", id="rank-bool"),
    pytest.param((verdict(1, "NVDA", headlines=("x",)),), TypeError, "headline must be a mapping", id="headline"),
    pytest.param(
        (verdict(1, "NVDA", earnings_date=DECIDED),), TypeError, "earnings_date must be a date", id="earnings-datetime"
    ),
    pytest.param(((1, "NVDA", "allow"),), TypeError, "must be NewsVerdict", id="not-a-verdict"),
]


@pytest.mark.parametrize(("verdicts", "error", "message"), BAD)
def test_bad_input_raises_before_any_write(pg, verdicts, error, message):
    with pytest.raises(error, match=message):
        store.write_vetoes(pg, "C", S1, verdicts)
    assert count(pg) == 0


def test_the_session_must_be_an_nyse_session(pg):
    with pytest.raises(ValueError, match="not an NYSE session"):
        store.write_vetoes(pg, "C", date(2026, 10, 10), NIGHT)  # a Saturday
    with pytest.raises(TypeError):
        store.write_vetoes(pg, "C", DECIDED, NIGHT)
    with pytest.raises(TypeError):
        store.has_vetoes(pg, "C", DECIDED)
    with pytest.raises(TypeError):
        store.read_vetoes(pg, "C", DECIDED)
    assert count(pg) == 0


def test_an_unknown_strategy_is_a_database_error(pg):
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        store.write_vetoes(pg, "B", S1, NIGHT[:1])
    pg.rollback()


def nonempty(m: dict[date, frozenset[str]]) -> dict[date, frozenset[str]]:
    return {d: s for d, s in m.items() if s}


def test_allowed_between_keeps_only_allow_inclusive_and_per_strategy(pg):
    store.write_vetoes(pg, "C", S1, NIGHT)  # NVDA, MSFT allowed
    store.write_vetoes(pg, "C", S2, (verdict(1, "NVDA", "veto"), verdict(2, "AMD", "failed")))  # none allowed
    store.write_vetoes(pg, "C", S3, (verdict(1, "AMD", "allow"),))
    store.write_vetoes(pg, "C", S4, (verdict(1, "TSLA", "allow"),))
    store.write_vetoes(pg, "A", S3, (verdict(1, "XOM", "allow"),))  # another strategy's rows never leak in
    got = store.allowed_between(pg, "C", S1, S3)
    assert nonempty(got) == {S1: frozenset({"NVDA", "MSFT"}), S3: frozenset({"AMD"})}
    assert got.get(S2, frozenset()) == frozenset()
    assert S4 not in got
    assert nonempty(store.allowed_between(pg, "C", S3, S3)) == {S3: frozenset({"AMD"})}
    assert nonempty(store.allowed_between(pg, "C", S2, S2)) == {}
    assert store.allowed_between(pg, "C", S4, S1) == {}  # start after end
    assert nonempty(store.allowed_between(pg, "C", S1 - timedelta(days=30), S4 + timedelta(days=30))) == {
        S1: frozenset({"NVDA", "MSFT"}),
        S3: frozenset({"AMD"}),
        S4: frozenset({"TSLA"}),
    }


def test_allowed_between_with_no_rows_is_empty(pg):
    assert store.allowed_between(pg, "C", S1, S4) == {}
    with pytest.raises(TypeError):
        store.allowed_between(pg, "C", DECIDED, S4)
```
`nonempty(...)` keeps the assertions independent of whether phase 1's `allowed_map` keeps sessions with no
allowed symbol as empty frozensets or drops them.

### Step 9: Existing tests that now see a fifth strategy
**File:** `engine/tests/test_paper_store.py:58`. Replace
```python
    assert [r.id for r in rows] == ["SPY", "A", BOOK_ID, TIMING_ID]
```
with
```python
    assert [r.id for r in rows] == ["SPY", "A", BOOK_ID, TIMING_ID, "C"]
```

**File:** `engine/tests/test_paper_check.py:51`. Replace
```python
ROSTER_IDS = ("SPY", "A", F4, F1)
```
with
```python
ROSTER_IDS = ("SPY", "A", F4, F1, "C")
```
**Impact:** this file is phase 5's; the one-line edit is the minimum that keeps the tree green when C joins the
roster in phase 2. With it every test in the file passes (C is checked as `ok` with the same
`(sessions, paper_start, last_session)` as the others; its log line appears). Phase 5 builds on this constant.

## Verification

**Build:** `docker start seer-pg` then `engine/.venv/bin/ruff check engine` (clean).
**Tests:** `PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q`
— 0 failed, **0 skipped**. Focused run:
`... pytest engine/tests/test_migrate.py engine/tests/test_paper_roster.py engine/tests/test_demo.py engine/tests/test_paper_store_vetoes.py engine/tests/test_paper_store.py engine/tests/test_paper_check.py engine/tests/test_paper_command.py engine/tests/test_explain.py engine/tests/test_strategy_purity.py -q`.
Web: `cd web && npx vitest run && npx tsc --noEmit` — unaffected (no web file changes; no web test reads migrations).
**Pre-verified in a scratch copy** (phase 1 stubbed from K1): migrate 20 passed, roster + demo 27 passed,
store vetoes 28 passed, paper_check + paper_store 51 passed, paper_command/explain/replay/purity unchanged-green;
ruff clean; 004 byte-identical to K2; **full engine suite 2011 passed, 0 failed, 0 skipped (354 s)**.
**Manual check:** `python -c 'from seer_engine.paper.roster import ROSTER, spec, spec_digest; [print(e.id, spec_digest(spec(e))) for e in ROSTER]'`
prints the four old digests unchanged and C's pinned one.
**Exit criteria:** suite green with 0 skipped; the four PINS values and gate dicts byte-identical; `004` applies on a
schema at 003 (and on a fresh one), is a no-op the second time, and leaves the four roster rows and their paper rows
untouched; `store.write_vetoes` → `read_vetoes` round-trips by rank; `allowed_between` returns only `allow` symbols.

## Handoffs

- **Phase 1 (R1):** C's pin (`6cea6cb8…b762`) assumes the K1 readings listed under Step 5c (no trailing newline on
  the prompt texts, the exact `as_dict` key set, `STRATEGY_C.id == "C-news-veto"`). `strategies/c.py` must not import
  `seer_engine.paper` (store and roster import it). `allowed_map` may omit or keep empty sessions — phase 2's tests
  accept either.
- **Phase 5 (R2):** `test_paper_check.py:51` `ROSTER_IDS` already contains `"C"` after phase 2 — phase 5's edits to that
  file start from it. With phase 2 alone, `paper` already freezes and steps C nightly using the verdict-less
  `STRATEGY_C` (no orders); phase 5 swaps in `with_allowed(store.allowed_between(...))`. Cosmetic: `commands/paper.py`
  `PaperError("strategies row ... is missing; run `migrate` (003) first")` could say 004 — phase 5's file, left alone.
- **Phase 6 (R4):** `web/scripts/seed-demo.mjs` runs `TRUNCATE ... strategies RESTART IDENTITY CASCADE` and re-inserts only
  the four rows, so after a local demo seed the `C` row is **gone** (and the CASCADE also empties `news_vetoes`). Until
  phase 6 adds C to the seed's `strategies` array (with `params.backtest_gate = {passed: false, applicable: false, note}`),
  a local `nightly`+`paper` after a demo seed would hit `paper`'s "strategies row 'C' is missing" error. Neon is
  unaffected (never demo-seeded by the pipeline). Phase 6 should also list `news_vetoes` explicitly in the TRUNCATE.
- **Phase 7 (R5):** `engine/package_readme.md` — document `RosterEntry.gate_applicable`, the C entry, the store's
  verdict API and the `004` migration; runbook reset procedure includes `news_vetoes` (demo-owned).

## Rollback

Revert this phase's commit. Locally: `DROP TABLE news_vetoes; DELETE FROM strategies WHERE id = 'C'
AND NOT EXISTS (SELECT 1 FROM orders WHERE strategy_id = 'C') AND NOT EXISTS (SELECT 1 FROM equity_snapshots WHERE
strategy_id = 'C') AND NOT EXISTS (SELECT 1 FROM paper_state WHERE strategy_id = 'C'); DELETE FROM schema_migrations
WHERE name = '004_news_veto.sql'`. Phases 4–6 depend on this phase and must be reverted first. Nothing here touches
Neon; if 004 already ran there, the C row and empty table are harmless to the four existing strategies.

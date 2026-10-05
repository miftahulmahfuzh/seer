> Adopted from `EDGAR_FUNDAMENTALS_PLAN.md` phase 4. Source: `.workflows/plan/edgar-fundamentals/phase-4.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 4: `fundamentals` command — resumable ingest

**Plan set:** `EDGAR_FUNDAMENTALS_PLAN.md`
**Analysis:** `20261005-081833-G7K2_code_analyzer.md`
**Satisfies:** R2 (bulk ingest of SEC XBRL facts, `filed` as the no-look-ahead boundary,
restatements kept queryable), R5 (a new resumable `seer_engine` command respecting SEC fair
access)
**Satisfies (reconciled):** also **R1** — this phase owns `sync_ticker_cik`, the one writer of
the `ticker_cik` table from phase 1's vendored CSV (index Decisions)
**Depends on:** Phase 1 (`seer_engine/cik.py` + `engine/data/ticker_cik.csv`), Phase 2
(`db/migrations/005_fundamentals.sql`), Phase 3 (`seer_engine/sec.py` + `SEC_CONTACT_EMAIL`),
**Phase 5** (`seer_engine.fundamentals.ladder.LADDER_TAGS`, the ingest tag allowlist)
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/commands`

---

## Reconciled contracts with phases 1, 2, 3 and 5

This plan was written before any of those plan files existed, so its original A1–A6 were
guesses. **The reconciler replaced them with the real contracts.** Every one of them is still
confined to a single named seam in this phase's code, listed with the contract.

### C1 — Phase 2: `fundamental_facts` (seam: `_FACTS_COPY`, `_FACTS_UPSERT`)

Phase 2 ships exactly this. The original A1 guessed `cik text` and a `frame` column; both were
wrong. **`cik` is `bigint`** and **there is no `frame` column** — phase 2 omitted it on purpose
(it is SEC's canonical-frame annotation, nothing in the ladder reads it, and it costs ~10–22 MB
of a 0.5 GB tier). This phase writes twelve columns, not thirteen.

```sql
CREATE TABLE IF NOT EXISTS fundamental_facts (
  cik           bigint NOT NULL CHECK (cik > 0 AND cik <= 9999999999),
  taxonomy      text NOT NULL CHECK (taxonomy IN ('us-gaap', 'dei')),
  tag           text NOT NULL,
  unit          text NOT NULL,
  period_start  date NOT NULL,          -- = period_end for an instantaneous fact
  period_end    date NOT NULL,
  accn          text NOT NULL,          -- a restatement is a NEW row
  val           numeric NOT NULL,
  fy            int,
  fp            text,
  form          text NOT NULL,
  filed         date NOT NULL,          -- the ONLY no-look-ahead boundary
  PRIMARY KEY (cik, taxonomy, tag, unit, period_start, period_end, accn),
  CHECK (period_start <= period_end)
);
```

**A1's one correctness claim survived and was adopted by phase 2.** In one 10-K a filer tags
`Revenues` for the fiscal year (`start=2015-01-01, end=2015-12-31`) *and* for Q4
(`start=2015-10-01, end=2015-12-31`) — same `cik`, `taxonomy`, `tag`, `unit`, `end` and `accn`,
different `start`. `period_start` is therefore `NOT NULL` and in the primary key, with
`period_start = period_end` meaning *instantaneous* (SEC omits `start` for `Assets`,
`StockholdersEquity`, `dei:EntityCommonStockSharesOutstanding`). This phase writes that
convention; phase 5 maps it back to `period_start=None` on the read side.

### C2 — Phase 2: `fundamentals_log` is keyed by `cik` (seam: `_LOG_UPSERT`, `_write_batch`)

The original A2 keyed it by `symbol` with a `cik` attribute and `backfill_log`'s
`first_date`/`last_date` names. **Both were wrong.** Invariant 4 settles it: one CIK backs
several tickers (`GOOG`/`GOOGL`, `CMCSA`/`CMCSK`, `BATRA`/`BATRK`), so symbol-keying refetches
the same JSON and double-counts `rows`; and one ticker maps to several CIKs over time, so one
row would carry two companies' outcomes. The unit of work is one `companyfacts` fetch, which is
one CIK.

```sql
CREATE TABLE IF NOT EXISTS fundamentals_log (
  cik          bigint PRIMARY KEY CHECK (cik > 0 AND cik <= 9999999999),
  status       text NOT NULL CHECK (status IN ('ok', 'empty', 'failed')),
  first_filed  date,
  last_filed   date,
  rows         int,
  error        text,
  updated_at   timestamptz NOT NULL DEFAULT now()
);
```

**Consequence for this phase's own logic, and it is not cosmetic.** `select_symbols`'s resume
rule can no longer be "skip symbols already in the log". It becomes **"skip CIKs already in the
log"**: resolve every in-scope symbol to its CIK first, deduplicate to the set of CIKs, and skip
the ones already logged with any status (`--retry-failed` re-attempts `failed` and `empty`).
`SymbolResult` keeps its name and its `symbol` field for the human summary, but the dedupe key,
the log row and the fetch are all per CIK, and `format_summary` reports per symbol by mapping
each symbol back through its CIK's result.

**Steps 3, 6, 7, 9 and 11 are all written against that shape** — `CikJob`, `plan_jobs`,
`fetch_cik`, `CikResult.per_symbol()` — and four tests in Step 11 pin it: `GOOG`/`GOOGL` cause
exactly **one** `company_facts` call, **one** log row and a `"rows"` count that is not doubled;
a second run skips that CIK for both symbols; naming one twin reports only that symbol; and a
symbol the map cannot resolve gets **no** log row at all and is therefore re-attempted every
run. `Summary.exit_code` is untouched by any of it: `1` iff some symbol `failed`.

### C3 — Phase 2: `ticker_cik` (seam: `_MAP_SELECT`, `_MAP_INSERT`, `sync_ticker_cik`)

The original A3 guessed `ticker` and omitted `source`. Phase 2's real table:

```sql
CREATE TABLE IF NOT EXISTS ticker_cik (
  symbol      text NOT NULL,
  cik         bigint NOT NULL CHECK (cik > 0 AND cik <= 9999999999),
  start_date  date NOT NULL,
  end_date    date,                     -- EXCLUSIVE; NULL = still current
  company     text NOT NULL,
  source      text NOT NULL CHECK (source IN ('current','edgar','exact','fuzzy','manual')),
  note        text,
  PRIMARY KEY (symbol, start_date),
  CHECK (end_date IS NULL OR end_date > start_date)
);
```

Mapping from phase 1's CSV, which this phase's `sync_ticker_cik` performs:
`symbol→symbol`, `cik→cik` (**`int(row.cik)`** — the CSV holds a 10-digit zero-padded string),
`start_date→start_date`, `end_date→end_date`, **`company_name→company`**, `source→source`,
`note→note`. **Rows whose CSV `cik` is the literal `NONE` are skipped**: the column is
`NOT NULL bigint` and those symbols have no EDGAR filer at all.

### C4 — Phase 3: `sec.Fact` and `sec.Client` (seam: `fetch_cik`, `upsert_facts`)

The original A4 guessed `start`/`end` and no `cik`. Phase 3 ships:

```python
@dataclass(frozen=True, slots=True)
class Fact:
    cik: str              # 10-digit zero-padded
    taxonomy: str
    tag: str
    unit: str
    period_start: date | None   # None for an instantaneous fact
    period_end: date
    val: float
    accn: str
    form: str
    fy: int | None
    fp: str | None
    filed: date
    frame: str | None     # served by SEC, NOT persisted (phase 2 has no frame column)

@dataclass(frozen=True, slots=True)
class CompanyFacts:
    cik: str
    entity_name: str
    facts: tuple[Fact, ...]

class Client:
    def __init__(self, contact: str, *, transport=None, ...) -> None: ...
    def company_facts(self, cik: str | int, *, tags: Collection[str] | None = None) -> CompanyFacts: ...
```

`company_facts` returns a **`CompanyFacts`**, not a bare sequence — this phase's `FactsSource`
Protocol and `fetch_cik` read `.facts` off it — **not** the response itself, which has no
`__iter__`. `sec.SecNotFound` maps to `status='empty'`,
every other `sec.SecError` to `status='failed'`. Pacing, retries and the contact `User-Agent`
are entirely phase 3's: this phase adds no inter-batch sleep and injects no clock.
`sec.cik10(cik)` is the padding helper; `sec.require_contact()` is the setting accessor (phase 3
does **not** edit `config.py`).

### C5 — Phase 1: `seer_engine.cik` (seam: `load_cik_map`, `resolve_cik`)

The original A5 guessed `cik.load_map(cik.DEFAULT_PATH)` and rows with a `.ticker` attribute.
Phase 1 ships:

```python
cik.DATA_DIR: Path                 # engine/data
cik.TICKER_CIK_FILE: str           # "ticker_cik.csv"
cik.NO_FILER: str                  # "NONE"
cik.CikRow                         # frozen: symbol, cik: str|None, start_date,
                                   #         end_date: date|None, company_name, source, note
cik.load_ticker_cik(path: Path) -> list[CikRow]
cik.load_index(data_dir: Path = DATA_DIR) -> dict[str, tuple[CikRow, ...]]
cik.resolve_row(symbol, on: date, index) -> CikRow     # raises CikError
cik.no_filer_symbols(index) -> tuple[str, ...]
```

The attribute is **`.symbol`**, not `.ticker`, and the company field is **`.company_name`**.
This phase keeps its own `resolve_cik`/`resolve_window_cik` (so `cik.resolve_row`'s raising
behaviour is not a dependency), but reads the right attribute names.

### C6 — Phase 5: the ingest tag allowlist is **imported**, not defined here

The index's Decisions table settles it: the allowlist lives in phase 5's pure
`fundamentals/ladder.py` as `LADDER_TAGS: frozenset[tuple[str, str]]`, and this phase imports
it. Impure-imports-pure is the only legal direction under invariant 5, and the list must sit in
a module both the ingest and the derivation can read, or they drift and the ladder silently
reads a tag nobody stored. **This phase therefore defines no `INGEST_TAGS` of its own** (see the
rewritten Step 2) and gains a dependency on phase 5. Wave order: `{1,2,3} → {5} → {4,6} → {7}`.

### C7 — Scope count: **795**, settled

`docs/runbooks/data-pipeline.md:298–302` records the 2026-10-03 backfill: `all_symbols(since=
2015-01-02)` = **796** = 795 ever-members ∪ SPY, and `backfill_log` holds 663 `ok` + 133 `empty`
= 796. The brief's 819 is not reproducible from `universe`; phase 1 measured 795 independently.
The index, the analysis and every plan now say 795.

**This phase still hardcodes no count.** The scope set is the SQL predicate
`end_date IS NULL OR end_date > 2015-01-02` over `universe`, minus `SPY` — the same predicate
`universe.all_symbols` uses. **SPY is excluded deliberately:** it is an ETF trust, files no
`us-gaap` XBRL, and would guarantee one permanent non-`ok` row. `universe.BENCHMARK` is the
constant used.

### C8 — Landing order: phases 1 and 4 must land together for a green *run*

`resolve_window_cik` classifies a symbol with no row in the map as `failed`, so
`python -m seer_engine fundamentals` exits 1 against an incomplete `ticker_cik.csv`. That is
deliberate — it makes phase 1's "covers every ever-member" criterion machine-checkable — but it
means the command is only expected to exit 0 once **both** phases are merged. It does **not**
make either phase's `pytest engine/tests -q` depend on the other: this phase's tests use a fake
map and never read `engine/data/ticker_cik.csv`. Phase 1 carries the matching note.

---

## Goal

`python -m seer_engine fundamentals` exists and loads SEC EDGAR XBRL company facts for every
S&P 500 / Nasdaq-100 ever-member since 2015-01-02, resolving each symbol to a CIK through the
dated map so a recycled ticker can never fetch the wrong company's filings. Each batch of symbols
is written in one transaction together with its `fundamentals_log` rows, so a crash loses at most
one batch and a re-run resumes. Facts are stored raw with `accn` and `filed`, so restatements
coexist with the figures they restate and nothing downstream can look ahead. Nothing in the path
reads, joins or requires `bars`.

## Interface Contract

**Creates:**
- `seer_engine.commands.fundamentals` (`engine/src/seer_engine/commands/fundamentals.py`) — a new
  command module; `cli.discover()` picks it up with no edit to `cli.py`
- `fundamentals.HELP`, `add_arguments`, `run` — the command-module protocol
- `fundamentals.FundamentalsError` — exit-code-2 condition
- `fundamentals.Options`, `fundamentals.CikJob`, `fundamentals.CikResult`,
  `fundamentals.SymbolResult`, `fundamentals.Summary`, `fundamentals.Summary.exit_code`
- `fundamentals.FactsSource` (Protocol, one method `company_facts(cik, *, tags=None)`)
- `fundamentals.DEFAULT_SINCE`, `DEFAULT_SINCE_FILED`, `DEFAULT_BATCH_SIZE`,
  `STATUS_OK/EMPTY/FAILED`
- `fundamentals.load_cik_map`, `resolve_cik`, `resolve_window_cik`, `membership_windows`,
  `select_symbols`, `plan_jobs`, `select_facts`, `fetch_cik`, `upsert_facts`,
  `sync_ticker_cik`, `ingest`, `format_summary`

**The unit of work is a CIK, not a symbol (C2).** `select_symbols` answers "what is in scope";
`plan_jobs` turns that into `CikJob`s and skips the ones already logged; `fetch_cik` makes one
`companyfacts` call per job; `_write_batch` writes one `fundamentals_log` row per job; and
`CikResult.per_symbol()` fans the outcome back out so the summary and the exit code stay per
symbol. There is **no `fetch_symbol`** — an earlier draft had one and it is gone, because it
would have fetched GOOG and GOOGL separately and written the same log row twice.
- `engine/tests/test_fundamentals_command.py`

**Deletes:** none.
**Renames:** none.
**Signature changes:** none.

**Imports (does not create):** `seer_engine.fundamentals.ladder.LADDER_TAGS` — the stored tag
allowlist, owned by phase 5 (C6). This module re-exports it under no new name; it calls it
`LADDER_TAGS` throughout so a reader cannot mistake it for a local list.

**Writes (tables):** `fundamental_facts` (upsert, twelve columns, **no `frame`**),
`fundamentals_log` (upsert, **keyed by `cik`**), `ticker_cik` (full replace — see Handoff H1).
**Reads (tables):** `universe`, `fundamentals_log`, `ticker_cik`. **Never `bars`.**

**Requires (from earlier phases):**
- Phase 1: `seer_engine.cik.load_ticker_cik(path) -> list[CikRow]`, `cik.DATA_DIR`,
  `cik.TICKER_CIK_FILE`, `cik.NO_FILER`; rows expose
  `.symbol .cik .start_date .end_date .company_name .source .note`; intervals for one symbol
  never overlap (the loader enforces it) and `end_date` is **exclusive**, `None` = still held
  (C5).
- Phase 2: `fundamental_facts` with PK `(cik, taxonomy, tag, unit, period_start, period_end,
  accn)`, `period_start NOT NULL`, `cik bigint` and **no `frame` column** (C1);
  `fundamentals_log` keyed by `cik` with `first_filed`/`last_filed` (C2); `ticker_cik` with
  `symbol`/`company`/`source` (C3). All three applied by `migrate`, so the `pg` test fixture
  has them.
- Phase 3: `seer_engine.sec.Client(contact)` with
  `company_facts(cik, *, tags=None) -> CompanyFacts`; `sec.Fact` fields per C4;
  `sec.require_contact()` for `SEC_CONTACT_EMAIL`; `sec.SecNotFound` → `empty`, other
  `sec.SecError` → `failed`; pacing, retries and the contact `User-Agent` enforced inside the
  client.
- **Phase 5:** `seer_engine.fundamentals.ladder.LADDER_TAGS: frozenset[tuple[str, str]]` — the
  stored tag allowlist (C6). This is an import of a *pure* module from an *impure* one, which
  is the only legal direction under invariant 5.

**Leaves alone (owned by others):**
- `engine/src/seer_engine/cli.py` — discovery is automatic (`cli.py:32–42`)
- `engine/src/seer_engine/sec.py` (Phase 3), `cik.py` (Phase 1), `config.py` (Phase 3)
- `db/migrations/*` (Phase 2)
- `engine/src/seer_engine/fundamentals/` (Phase 5) — **this command derives nothing**. It
  imports exactly one name from the package, `ladder.LADDER_TAGS`, and calls no function in it.
- `engine/src/seer_engine/backtest/*`, `strategies/*` (Phases 6, 7)
- `docs/runbooks/data-pipeline.md` (Phase 7) — the contract it must document is stated below
- `engine/src/seer_engine/universe.py` — the membership-window query lives in this phase's own
  module rather than being added to `universe.py`, so no shared module changes shape

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/commands/fundamentals.py` | **create** (new, ~430 lines) | the whole command: docstring + constants (L1–L120), CLI (L122–L215), the work (L217–L330), writes (L332–L420), output (L422–L end) |
| `engine/tests/test_fundamentals_command.py` | **create** (new, ~460 lines) | fakes + 22 tests (four of them on the CIK fan-out and the `NONE` sentinel); no network, no clock |

No existing file is modified.

## Implementation Steps

All steps land in one new file, in the order given. Line anchors are positions within that file.

### Step 1: Module docstring and imports
**File:** `engine/src/seer_engine/commands/fundamentals.py:1`
**Change:** create the file. The docstring states the three things a reader must not get wrong:
the per-batch transaction, Gap A independence, and why the tag allowlist exists.
**Code:**
```python
"""fundamentals -- resumable ingest of SEC EDGAR XBRL company facts (Gap B).

One ``data.sec.gov`` ``companyfacts`` call per CIK, resolved from the vendored dated
ticker->CIK map, for every S&P 500 / Nasdaq-100 ever-member since 2015-01-02. Symbols are
processed in batches and **each batch is written in its own transaction together with its
``fundamentals_log`` rows**, so a crash loses at most one batch and a re-run resumes where
it stopped -- the shape ``backfill`` uses.

No dependency on ``bars``. 133 of the ever-members have no price history at all and they are
precisely the names this pipeline exists to cover, so nothing here reads ``bars``, joins
against it, or treats a missing bar as an error.

Point in time: every fact is stored with its ``filed`` date and its accession number, and
``accn`` is part of the row identity, so a restatement inserts a second row rather than
overwriting the figure it restates. ``period_end`` is never an availability date. Nothing
here derives anything: the concept ladder and the ``filed <= t`` selection are pure code in
``seer_engine.fundamentals``.

Storage. ``companyfacts`` for a large filer holds tens of thousands of facts across hundreds
of tags; Neon's free tier is 0.5 GB and ``bars`` already takes 177 MB. So the ingest keeps
only the taxonomy/tag pairs in ``ladder.LADDER_TAGS`` (phase 5 owns the list) and only facts
with ``filed >= --since-filed``.
Widening either is a deliberate decision that costs a re-ingest, which is why both are
visible constants and the summary prints ``pg_total_relation_size('fundamental_facts')``.

Fair access is the SEC client's job, not this module's: ``sec.Client`` paces itself to
<= 10 req/s from the end of the previous call and sends the contact ``User-Agent``. This
command therefore adds no inter-batch sleep.

Idempotent: every write is an upsert guarded by ``IS DISTINCT FROM``; re-running with the
same arguments changes no ``fundamental_facts`` rows.
"""

from __future__ import annotations

import argparse
import logging
import math
from collections.abc import Collection, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Protocol

import psycopg

from seer_engine import cik, config, db, membership, sec, universe
from seer_engine.sec import CompanyFacts, Fact

log = logging.getLogger(__name__)
```
**Impact:** `cli.discover()` now imports this module on every CLI invocation and in
`test_cli.py`, so an import error here breaks every command. `sec` and `cik` must exist
(phases 3 and 1).

### Step 2: Constants, and the imported tag allowlist
**File:** `engine/src/seer_engine/commands/fundamentals.py:~56`
**Change:** the command's tunables. The allowlist is **imported from phase 5**, not defined here
(C6) — see Handoff H2.
**Code:**
```python
from seer_engine.fundamentals.ladder import LADDER_TAGS

HELP = "Load SEC EDGAR XBRL company facts for every index ever-member; resumable."

DEFAULT_SINCE = date(2015, 1, 2)
# Facts filed before this are never usable: the backtest window opens at DEFAULT_SINCE and
# SUE needs EPS_{q-4} plus a year of surprises to scale by, so two years of lead is enough.
# Dropping 2009-2012 roughly halves the row count on a 0.5 GB database.
DEFAULT_SINCE_FILED = date(2013, 1, 1)
DEFAULT_BATCH_SIZE = 20
ERROR_MAX_LEN = 500

STATUS_OK = "ok"
STATUS_EMPTY = "empty"
STATUS_FAILED = "failed"

# The (taxonomy, tag) pairs stored are EXACTLY seer_engine.fundamentals.ladder.LADDER_TAGS --
# every rung of every concept the derivation reads, and nothing else. This command owns no
# list of its own, deliberately: if the ingest's allowlist and the ladder's rungs could drift,
# the ladder would silently read a tag nobody stored and a concept would go dark with no error.
# ladder.py is pure (no psycopg, no requests, no clock), so importing it here is the legal
# direction under invariant 5; the reverse would not be.
#
# Measured coverage over 8 dead filers lives in
# docs/plans/2026-10-05-delisted-and-fundamentals.md section 3.2: revenue, net income, assets,
# equity, operating cash flow, diluted EPS and shares outstanding are 8/8; operating income is
# 6/8 (SIVB, PXD missing); gross profit is only 2/8, which is why the cost-of-revenue rungs are
# in the ladder at all -- phase 5 derives Revenues - CostOfRevenue from them.
#
# ADDING A TAG COSTS A FULL RE-INGEST. It is added to ladder.py, never here.


class FundamentalsError(Exception):
    """A user-facing reason the ingest cannot start or continue (exit code 2)."""


class FactsSource(Protocol):
    """Anything returning parsed XBRL facts for a CIK. ``sec.Client`` satisfies it."""

    def company_facts(
        self, cik: str | int, *, tags: Collection[str] | None = None
    ) -> CompanyFacts: ...
```
**Impact:** the stored set is `LADDER_TAGS`. Phase 5's ladder has eleven concepts whose rungs
total roughly twenty `(taxonomy, tag)` pairs; at ~100 facts per pair per filer, over 795 filers
with the 2013 `filed` cutoff, that is roughly 0.8 M rows — inside phase 2's budget.

**Two tags the original draft of this phase listed are deliberately gone**, because no ladder
concept reads them and every stored tag costs rows on a 0.5 GB tier:
`us-gaap:Liabilities` (the ladder derives nothing from it; book equity is tagged directly) and
`us-gaap:EarningsPerShareBasic` (SUE and the EPS series are defined on **diluted** EPS, which is
8/8 in the measurement). Either can be added later by adding a rung in `ladder.py` and
re-ingesting.

### Step 3: `Options`, `CikJob`, `CikResult`, `SymbolResult`, `Summary`
**File:** `engine/src/seer_engine/commands/fundamentals.py:~128`
**Change:** the shapes `backfill.py:53–86` establishes, **plus the two the CIK keying adds**.
`backfill`'s unit of work is a symbol; here it is a CIK, so there is a `CikJob` (what to fetch)
and a `CikResult` (what came back), and `SymbolResult` becomes what `CikResult` fans out into
for the human summary. `Summary.exit_code` is **unchanged** from `backfill.Summary.exit_code`
(`backfill.py:85`): `1` iff some symbol `failed`, and `empty` is deliberately not a failure.
**Code:**
```python
@dataclass(frozen=True)
class Options:
    today: date
    since: date = DEFAULT_SINCE
    since_filed: date = DEFAULT_SINCE_FILED
    symbols: tuple[str, ...] | None = None
    retry_failed: bool = False
    batch_size: int = DEFAULT_BATCH_SIZE
    sync_map: bool = True
    dry_run: bool = False


@dataclass(frozen=True)
class CikJob:
    """One ``companyfacts`` fetch: a CIK and every in-scope symbol it backs.

    ``symbols`` is sorted and never empty. It holds more than one entry exactly when a share
    class pair is in scope (GOOG/GOOGL, CMCSA/CMCSK, BATRA/BATRK) -- the case C2 exists for.
    """

    cik: str                       # 10-digit zero-padded
    symbols: tuple[str, ...]


@dataclass(frozen=True)
class CikResult:
    """What one fetch produced. **This is what the log row is written from** (one per CIK)."""

    cik: str
    symbols: tuple[str, ...]
    status: str
    facts: tuple[Fact, ...] = ()
    error: str | None = None

    def per_symbol(self) -> tuple[SymbolResult, ...]:
        """The fan-out: the same outcome reported once for each symbol the CIK backs.

        The ONE place a CIK-keyed result becomes symbol-keyed output. The facts are **not**
        copied into the per-symbol records -- they belong to the CIK and counting them per
        symbol would double-count a share-class pair -- so ``SymbolResult.facts`` is left
        empty here and ``Summary.facts_fetched`` is accumulated from the ``CikResult``.
        """
        return tuple(
            SymbolResult(s, self.status, cik=self.cik, error=self.error) for s in self.symbols
        )


@dataclass(frozen=True)
class SymbolResult:
    """One line of the human summary. Not a unit of work and not a log row (C2)."""

    symbol: str
    status: str
    cik: str | None = None
    error: str | None = None


@dataclass
class Summary:
    ok: list[str] = field(default_factory=list)
    empty: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    skipped: int = 0            # SYMBOLS whose CIK was already logged
    ciks_fetched: int = 0       # companyfacts calls actually made; <= len(ok) + len(empty)
    facts_fetched: int = 0      # accumulated per CIK, never per symbol (no double counting)
    facts_written: int = 0
    map_rows: int = 0
    map_changed: bool = False
    facts_bytes: int | None = None

    def exit_code(self) -> int:
        """1 when any symbol failed, else 0. ``empty`` is deliberately not an error: a
        filer with no facts in the ingest tag set is a fact about the filer, not a fault."""
        return 1 if self.failed else 0
```
**Impact:** `today` is the only required field, so every test constructs `Options(today=...)`.

### Step 4: CLI surface
**File:** `engine/src/seer_engine/commands/fundamentals.py:~175`
**Change:** `add_arguments` / `options_from_args` / `run`, mirroring `backfill.py:92–185`.
`--symbols` normalises through `membership.normalize_ticker` (pure, dash->dot) rather than
`yahoo.from_yahoo`, because EDGAR has nothing to do with Yahoo's ticker spelling.
**Code:**
```python
def _iso_date(text: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"not a YYYY-MM-DD date: {text!r}") from exc


def _symbol_list(text: str) -> list[str]:
    try:
        items = [membership.normalize_ticker(part) for part in text.split(",") if part.strip()]
    except membership.MembershipError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
    if not items:
        raise argparse.ArgumentTypeError("--symbols needs at least one symbol")
    return list(dict.fromkeys(items))


def _positive_int(text: str) -> int:
    try:
        value = int(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"not an integer: {text!r}") from exc
    if value < 1:
        raise argparse.ArgumentTypeError("must be >= 1")
    return value


def add_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--since",
        type=_iso_date,
        default=DEFAULT_SINCE,
        help=f"ingest every member on or after this date (default {DEFAULT_SINCE.isoformat()})",
    )
    p.add_argument(
        "--since-filed",
        type=_iso_date,
        default=DEFAULT_SINCE_FILED,
        help=(
            "drop facts filed before this date "
            f"(default {DEFAULT_SINCE_FILED.isoformat()}; widening costs a re-ingest)"
        ),
    )
    p.add_argument(
        "--symbols",
        type=_symbol_list,
        default=None,
        help="comma list (e.g. ATVI,BRK.B) instead of the universe; ignores fundamentals_log",
    )
    p.add_argument(
        "--retry-failed",
        action="store_true",
        help="also re-attempt symbols logged as failed or empty",
    )
    p.add_argument(
        "--batch-size",
        type=_positive_int,
        default=DEFAULT_BATCH_SIZE,
        help=f"symbols per write transaction (default {DEFAULT_BATCH_SIZE})",
    )
    p.add_argument(
        "--no-sync-map",
        action="store_true",
        help="do not mirror engine/data/ticker_cik.csv into the ticker_cik table",
    )


def options_from_args(args: argparse.Namespace, now: datetime | None = None) -> Options:
    today = (now if now is not None else datetime.now(timezone.utc)).date()
    if args.since > today:
        raise FundamentalsError(f"--since {args.since} is in the future (today is {today})")
    if args.since_filed > args.since:
        raise FundamentalsError(
            f"--since-filed {args.since_filed} is after --since {args.since}: a fact has to be "
            "filed before the window opens to be usable on its first date"
        )
    return Options(
        today=today,
        since=args.since,
        since_filed=args.since_filed,
        symbols=tuple(args.symbols) if args.symbols else None,
        retry_failed=bool(args.retry_failed),
        batch_size=int(args.batch_size),
        sync_map=not bool(args.no_sync_map),
        dry_run=bool(args.dry_run),
    )


def run(args: argparse.Namespace) -> int:
    try:
        opts = options_from_args(args)
    except FundamentalsError as exc:
        log.error("fundamentals: %s", exc)
        return 2
    # Read the contact address before opening a connection, so a missing setting reports the
    # setting rather than a database error. ConfigError propagates; cli.main turns it into 2.
    contact = config.require("SEC_CONTACT_EMAIL")
    client = sec.Client(contact)
    conn = db.connect()
    try:
        summary = ingest(conn, opts, source=client)
    except FundamentalsError as exc:
        log.error("fundamentals: %s", exc)
        return 2
    finally:
        conn.close()
    print(format_summary(summary, opts))
    return summary.exit_code()
```
**Impact:** `cli.main` (`cli.py:112–114`) already maps `config.ConfigError` to exit 2, so a
missing `SEC_CONTACT_EMAIL` or `DATABASE_URL_UNPOOLED` is exit 2 with no extra handling.

### Step 5: The CIK map — the single phase-1 seam
**File:** `engine/src/seer_engine/commands/fundamentals.py:~288`
**Change:** load the vendored map through phase 1, but resolve here, so only the loader is a
cross-phase dependency. `resolve_cik` is the enforcement point for invariant 4.
**Code:**
```python
def load_cik_map(path: Path | None = None) -> Sequence[cik.CikRow]:
    """Phase 1's vendored, validated ticker->CIK map (C5).

    The only call into ``seer_engine.cik``. Rows expose ``symbol``, ``cik`` (a 10-digit
    zero-padded string, or ``cik.NO_FILER`` == "NONE" for a symbol with no EDGAR filer at all),
    ``start_date``, ``end_date`` (exclusive; None = still held), ``company_name``, ``source``
    and ``note``. If ``cik.py``'s loader is named or shaped differently, this function is the
    one place to change.
    """
    return cik.load_ticker_cik(
        (cik.DATA_DIR / cik.TICKER_CIK_FILE) if path is None else path
    )


def resolve_cik(mappings: Iterable[cik.CikRow], symbol: str, on: date) -> cik.CikRow | None:
    """The mapping row that held ``symbol`` on ``on``, or None.

    A match needs ``start_date <= on`` and ``on < end_date`` (or an open interval). Keyed on
    (symbol, date) and never on the bare ticker, so CA on 2015-01-02 is CA Inc. and not the
    Xtrackers ETF that holds the ticker today. Phase 1's loader rejects overlapping intervals
    for one symbol, so at most one row can match. A row whose ``cik`` is ``cik.NO_FILER`` is
    returned, not skipped -- "this symbol has no filer" is an answer, and ``resolve_window_cik``
    turns it into ``empty`` rather than ``failed``.
    """
    for mapping in mappings:
        if mapping.symbol != symbol:
            continue
        if mapping.start_date <= on and (mapping.end_date is None or on < mapping.end_date):
            return mapping
    return None


def resolve_window_cik(
    mappings: Iterable[cik.CikRow], symbol: str, first_day: date, last_day: date
) -> tuple[str | None, str, str | None]:
    """``(cik, status, error)`` for ``symbol`` across its whole membership window.

    Returns one of three outcomes, and the three-way split is the point:

    * ``(cik10, STATUS_OK, None)``   -- one filer covers the whole window; fetch it.
    * ``(None, STATUS_EMPTY, note)`` -- the map says this symbol has **no EDGAR filer**
      (``cik == cik.NO_FILER``). Not an error: ``Summary.exit_code`` treats ``empty`` as
      success, exactly as ``backfill`` does for a symbol with no bars.
    * ``(None, STATUS_FAILED, why)`` -- the map cannot answer: no row at all, or two different
      filers across the window.

    Both ends of the window are probed and must agree. A disagreement means the ticker changed
    hands while the symbol was an index member, which would make a single companyfacts fetch
    silently mix two companies -- so it is a failure, never a guess.
    """
    rows = list(mappings)
    first = resolve_cik(rows, symbol, first_day)
    last = resolve_cik(rows, symbol, last_day)
    if first is None or last is None:
        missing = first_day if first is None else last_day
        return None, STATUS_FAILED, (
            f"no CIK for {symbol} on {missing.isoformat()}: add a dated row to "
            f"engine/data/ticker_cik.csv (a ticker alone never identifies a company)"
        )
    if first.cik == cik.NO_FILER or last.cik == cik.NO_FILER:
        return None, STATUS_EMPTY, (
            f"{symbol} has no EDGAR filer in engine/data/ticker_cik.csv: {first.note or last.note}"
        )
    if first.cik != last.cik:
        return None, STATUS_FAILED, (
            f"{symbol} maps to CIK {first.cik} on {first_day.isoformat()} but CIK {last.cik} "
            f"on {last_day.isoformat()}: the ticker changed hands inside its index membership; "
            f"split the interval in engine/data/ticker_cik.csv"
        )
    return first.cik, STATUS_OK, None
```
**Impact:** a ticker **missing** from the map becomes a `failed` symbol (exit 1), so
`--retry-failed` picks it up after the CSV is re-vendored, and phase 1's "covers every
ever-member" criterion is machine-checkable by running this command (C8). A ticker the map
explicitly marks `NONE` becomes `empty` and does not fail the run — the map answered, and the
answer was "there is nothing at EDGAR to fetch".

### Step 6: Membership windows, CIK resolution and job selection
**File:** `engine/src/seer_engine/commands/fundamentals.py:~352`
**Change:** the scope query, then **resolution to CIKs before the resume rule**. This is the
shape C2 forces and it is the one place the symbol→CIK fan-in happens. `backfill`'s
`select_symbols` (`backfill.py:217–237`) skipped symbols already in its log; here the log is
keyed by `cik`, so the run resolves every in-scope symbol first, groups the symbols by CIK, and
skips the **CIKs** already logged. One `companyfacts` fetch per CIK, one log row per CIK,
`GOOG` and `GOOGL` counted once.
**Code:**
```python
# Same scope predicate as universe.all_symbols (universe.py:41-48), plus the window each
# symbol was a member for, so the CIK can be resolved by date. `end_date` is exclusive, so
# the last day of membership is `end_date - 1`. The window start is clamped to `since`
# because the universe runs back to 1996 while ticker_cik.csv covers the backtest era.
_WINDOWS_SQL = """
SELECT symbol,
       greatest(min(start_date), %(since)s)                     AS first_day,
       least(max(coalesce(end_date - 1, %(today)s)), %(today)s) AS last_day
FROM universe
WHERE end_date IS NULL OR end_date > %(since)s
GROUP BY symbol
ORDER BY symbol
"""


def membership_windows(
    conn: psycopg.Connection, since: date, today: date
) -> dict[str, tuple[date, date]]:
    """symbol -> (first day, last day) of index membership, for every ever-member since
    ``since``. The benchmark is excluded: SPY is an ETF trust and files no us-gaap XBRL."""
    rows = conn.execute(_WINDOWS_SQL, {"since": since, "today": today}).fetchall()
    out: dict[str, tuple[date, date]] = {}
    for symbol, first_day, last_day in rows:
        if symbol == universe.BENCHMARK:
            continue
        out[symbol] = (first_day, max(first_day, last_day))
    return out


def select_symbols(opts: Options, windows: dict[str, tuple[date, date]]) -> list[str]:
    """The in-scope symbols, before any CIK resolution.

    ``--symbols`` replaces the universe outright. Note what that means once the log is keyed by
    CIK: naming ``GOOG`` alone still fetches CIK 1652044 once and writes one log row, and the
    summary reports ``GOOG`` only, because ``GOOGL`` is not in the run. Naming both reports
    both from the one fetch.
    """
    if opts.symbols:
        return list(opts.symbols)
    candidates = sorted(windows)
    if not candidates:
        raise FundamentalsError(
            f"the universe table holds no member on or after {opts.since.isoformat()}; "
            "run `python -m seer_engine universe refresh` first"
        )
    return candidates


def plan_jobs(
    conn: psycopg.Connection,
    opts: Options,
    symbols: Sequence[str],
    windows: dict[str, tuple[date, date]],
    mappings: Sequence[cik.CikRow],
) -> tuple[list[CikJob], list[SymbolResult], int]:
    """``(jobs, unresolved, skipped)`` -- the heart of the CIK-keyed resume rule (C2).

    Resolution happens **before** the log is consulted, because the log's key is the CIK and a
    symbol does not have one until the dated map is asked. The three returns are:

    * ``jobs``       -- one per distinct CIK still to fetch, carrying every in-scope symbol it
      backs, sorted by (first symbol, cik) so batching is deterministic.
    * ``unresolved`` -- the symbols the map could not turn into a CIK: ``failed`` (no row, or
      two filers across the window) and ``empty`` (the map says ``NONE``). **These never get a
      ``fundamentals_log`` row** -- the table's primary key is a bigint CIK and there is none --
      so they are re-evaluated on every run, which is right: nothing was fetched and nothing
      stored. A ``failed`` one therefore keeps failing until ``ticker_cik.csv`` is re-vendoured;
      a ``NONE`` one keeps reporting ``empty``, which is not an error.
    * ``skipped``    -- how many **symbols** were skipped because their CIK is already logged.
      Counted per symbol, not per CIK, because the summary line is per symbol.

    A share-class pair collapses here: ``GOOG`` and ``GOOGL`` resolve to the same CIK, so they
    produce ONE job with ``symbols == ("GOOG", "GOOGL")``, one ``company_facts`` call and one
    log row.
    """
    by_cik: dict[str, list[str]] = {}
    unresolved: list[SymbolResult] = []
    for symbol in symbols:
        window = windows.get(symbol, (opts.since, opts.today))
        number, status, why = resolve_window_cik(mappings, symbol, *window)
        if number is None:
            if status == STATUS_FAILED:
                log.warning("fundamentals: %s unresolved: %s", symbol, why)
            unresolved.append(
                SymbolResult(symbol, status, error=_error_text(str(why)) if why else None)
            )
            continue
        by_cik.setdefault(number, []).append(symbol)

    # `--symbols` ignores the log outright -- that is what its help text promises and what
    # makes it the tool for re-fetching one filer after a fix. Everything else resumes.
    logged = {} if opts.symbols else _logged_statuses(conn, sorted(by_cik))
    done = {STATUS_OK} if opts.retry_failed else {STATUS_OK, STATUS_EMPTY, STATUS_FAILED}
    jobs: list[CikJob] = []
    skipped = 0
    for number, group in by_cik.items():
        if logged.get(number) in done:
            skipped += len(group)
            continue
        jobs.append(CikJob(cik=number, symbols=tuple(sorted(group))))
    jobs.sort(key=lambda j: (j.symbols[0], j.cik))
    return jobs, unresolved, skipped


def _logged_statuses(conn: psycopg.Connection, ciks: Sequence[str]) -> dict[str, str]:
    """CIK -> status, for the CIKs about to be fetched. Keyed by ``cik`` (C2): there is no
    ``symbol`` column in ``fundamentals_log``. The table's column is a ``bigint``; the keys
    returned here are the 10-digit zero-padded strings the rest of the module uses, so the
    round trip is ``int()`` out and ``sec.cik10()`` back."""
    if not ciks:
        return {}
    rows = conn.execute(
        "SELECT cik, status FROM fundamentals_log WHERE cik = ANY(%s)",
        ([int(c) for c in ciks],),
    ).fetchall()
    return {sec.cik10(number): status for number, status in rows}
```
**Impact:** this is the Gap A independence point. `_WINDOWS_SQL` names `universe` and nothing
else; a symbol with zero rows in `bars` is indistinguishable from one with ten years of them.

**And it is the fan-in point.** Everything downstream of `plan_jobs` works in CIKs; everything
the operator reads works in symbols. The two meet exactly twice: here, and in
`CikResult.per_symbol()` (Step 7).

### Step 7: Per-CIK fetch and fact filtering
**File:** `engine/src/seer_engine/commands/fundamentals.py:~412`
**Change:** one SEC call per **CIK** (C2), not per symbol; any exception from the client fails
that CIK only, and the failure is reported for every symbol the CIK backs.
**Code:**
```python
# ``_period_start`` is defined once, in Step 8 beside the writer that uses it.


def select_facts(facts: Iterable[Fact], since_filed: date) -> tuple[Fact, ...]:
    """The facts worth storing: in ``ladder.LADDER_TAGS`` and filed on or after ``since_filed``.

    Sorted into a deterministic order so a batch's COPY payload -- and therefore the test
    expectations -- do not depend on the order data.sec.gov happened to return.
    """
    kept = [
        f for f in facts if (f.taxonomy, f.tag) in LADDER_TAGS and f.filed >= since_filed
    ]
    kept.sort(
        key=lambda f: (
            f.taxonomy, f.tag, f.unit, _period_start(f), f.period_end, f.accn, f.filed
        )
    )
    return tuple(kept)


def fetch_cik(job: CikJob, opts: Options, source: FactsSource) -> CikResult:
    """Fetch one CIK's facts. Never raises: every failure becomes a ``failed`` result so one
    dead filer cannot end the run.

    The CIK is already resolved -- ``plan_jobs`` did that, and did it once for the whole run
    rather than once per symbol. ``source.company_facts`` returns a ``sec.CompanyFacts``
    (C4), so the facts are read off ``.facts``; the tag filter is passed down so the client
    can skip parsing units the ladder does not read.
    """
    try:
        response = source.company_facts(job.cik, tags=tuple(sorted(t for _, t in LADDER_TAGS)))
    except sec.SecNotFound as exc:
        # C4: a 404 from data.sec.gov means this CIK has no companyfacts document at all.
        # That is a fact about the filer, not a fault, so it is `empty` and exits 0 -- the
        # same call `backfill` makes for a symbol with no bars.
        return CikResult(
            job.cik,
            job.symbols,
            STATUS_EMPTY,
            error=_error_text(f"no companyfacts document for CIK {job.cik}: {exc}"),
        )
    except Exception as exc:  # noqa: BLE001 - one filer's failure never ends the run
        error = _error_text(f"{type(exc).__name__}: {exc}")
        log.warning(
            "fundamentals: CIK %s (%s) failed: %s", job.cik, ", ".join(job.symbols), error
        )
        return CikResult(job.cik, job.symbols, STATUS_FAILED, error=error)
    kept = select_facts(response.facts, opts.since_filed)
    if not kept:
        return CikResult(
            job.cik,
            job.symbols,
            STATUS_EMPTY,
            error=(
                f"CIK {job.cik} returned no fact in the ingest tag set filed on or after "
                f"{opts.since_filed.isoformat()}"
            ),
        )
    return CikResult(job.cik, job.symbols, STATUS_OK, facts=kept)


def _error_text(text: str) -> str:
    return text if len(text) <= ERROR_MAX_LEN else text[: ERROR_MAX_LEN - 3] + "..."
```
**Impact:** mirrors `backfill.fetch_batch`'s contract — the batch loop sees only `CikResult`s
and fans them out to `SymbolResult`s once, at the summary. **`sec.SecNotFound` is not special
cased here**: it arrives through the same `except Exception` and becomes `failed`, which is
what C4 asks for only when the error is *not* a 404. If phase 3's `SecNotFound` is to mean
`empty` (C4 says it is), add the one branch:

```python
    except sec.SecNotFound as exc:
        return CikResult(job.cik, job.symbols, STATUS_EMPTY,
                         error=_error_text(f"no companyfacts for CIK {job.cik}: {exc}"))
```
The two statuses differ in the exit code, which is why the branch is written out rather than
folded into the broad handler.

### Step 8: Writes — facts, the log, and the map mirror
**File:** `engine/src/seer_engine/commands/fundamentals.py:~480`
**Change:** the COPY-into-temp upsert `bars.upsert_bars` (`bars.py:53–97`) establishes, plus the
log upsert and the `ticker_cik` full replace.
**Code:**
```python
def _to_numeric(value: Decimal | float | int | str) -> Decimal:
    """A fact value as an exact ``numeric``. Rejects bools and non-finite floats."""
    if isinstance(value, bool):
        raise TypeError("bool is not a fact value")
    if isinstance(value, Decimal):
        number = value
    elif isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"non-finite fact value: {value!r}")
        number = Decimal(repr(value))
    else:
        try:
            number = Decimal(value)
        except (InvalidOperation, TypeError) as exc:
            raise ValueError(f"not a fact value: {value!r}") from exc
    if not number.is_finite():
        raise ValueError(f"non-finite fact value: {value!r}")
    return number


_FACTS_TEMP = """
CREATE TEMP TABLE IF NOT EXISTS _seer_facts_in
(LIKE fundamental_facts INCLUDING DEFAULTS) ON COMMIT DELETE ROWS
"""

# Twelve columns, in phase 2's declared order. THERE IS NO `frame` COLUMN: phase 2 omitted
# SEC's canonical-frame annotation on purpose (nothing in the ladder reads it, and it costs
# ~10-22 MB of a 0.5 GB tier). sec.Fact still carries `frame`; it is simply not persisted.
_FACTS_COPY = (
    "COPY _seer_facts_in "
    "(cik, taxonomy, tag, unit, period_start, period_end, accn, val, fy, fp, form, filed) "
    "FROM STDIN"
)

# DISTINCT ON is required, not defensive: ON CONFLICT DO UPDATE cannot touch the same row
# twice in one statement, and companyfacts can repeat an identical entry inside a unit array.
# The conflict tuple IS the fact identity -- `accn` keeps a restatement as a separate row and
# `period_start` keeps a 10-K's Q4 figure from colliding with its full-year figure.
_FACTS_UPSERT = """
INSERT INTO fundamental_facts AS f
    (cik, taxonomy, tag, unit, period_start, period_end, accn, val, fy, fp, form, filed)
SELECT DISTINCT ON (cik, taxonomy, tag, unit, period_start, period_end, accn)
       cik, taxonomy, tag, unit, period_start, period_end, accn, val, fy, fp, form, filed
FROM _seer_facts_in
ORDER BY cik, taxonomy, tag, unit, period_start, period_end, accn, filed DESC, val DESC
ON CONFLICT (cik, taxonomy, tag, unit, period_start, period_end, accn) DO UPDATE
SET val = EXCLUDED.val,
    fy = EXCLUDED.fy,
    fp = EXCLUDED.fp,
    form = EXCLUDED.form,
    filed = EXCLUDED.filed
WHERE (f.val, f.fy, f.fp, f.form, f.filed)
      IS DISTINCT FROM
      (EXCLUDED.val, EXCLUDED.fy, EXCLUDED.fp, EXCLUDED.form, EXCLUDED.filed)
"""


def _period_start(fact: Fact) -> date:
    """``fact.period_start``, or ``fact.period_end`` when SEC omitted it (C1).

    ``period_start = period_end`` IS the stored encoding of "instantaneous"; phase 2's column
    is NOT NULL and in the primary key, and phase 5 maps the equality back to None on the read
    side. No us-gaap or dei duration fact has a one-day period, so the convention is
    unambiguous.
    """
    return fact.period_end if fact.period_start is None else fact.period_start


def upsert_facts(conn: psycopg.Connection, rows: Iterable[tuple[int, Fact]]) -> int:
    """Insert new facts and update changed ones; return how many rows were inserted or
    changed. ``rows`` pairs the already-resolved integer CIK with each fact -- phase 2's
    column is ``bigint``, so the 10-digit zero-padded string form never reaches the database.
    Facts identical to the stored row are skipped by the ``IS DISTINCT FROM`` guard, so an
    identical re-run returns 0. Does not commit."""
    batch = list(rows)
    if not batch:
        return 0
    with conn.cursor() as cur:
        cur.execute(_FACTS_TEMP)
        cur.execute("TRUNCATE _seer_facts_in")
        with cur.copy(_FACTS_COPY) as copy:
            for number, fact in batch:
                copy.write_row(
                    (
                        number,
                        fact.taxonomy,
                        fact.tag,
                        fact.unit,
                        _period_start(fact),
                        fact.period_end,
                        fact.accn,
                        _to_numeric(fact.val),
                        fact.fy,
                        fact.fp,
                        fact.form,
                        fact.filed,
                    )
                )
        cur.execute(_FACTS_UPSERT)
        changed = cur.rowcount
        cur.execute("TRUNCATE _seer_facts_in")
    return changed


# backfill's _LOG_UPSERT (backfill.py:360-376), including the guard that an attempt which
# fails never downgrades a filer already logged ok -- but KEYED BY cik, not symbol (C2), and
# with phase 2's `first_filed`/`last_filed` names. One row per companyfacts fetch.
_LOG_UPSERT = """
INSERT INTO fundamentals_log
    (cik, status, first_filed, last_filed, "rows", error, updated_at)
VALUES (%s, %s, %s, %s, %s, %s, now())
ON CONFLICT (cik) DO UPDATE SET
    status = EXCLUDED.status,
    first_filed = EXCLUDED.first_filed,
    last_filed = EXCLUDED.last_filed,
    "rows" = EXCLUDED."rows",
    error = EXCLUDED.error,
    updated_at = EXCLUDED.updated_at
WHERE (fundamentals_log.status, fundamentals_log.first_filed, fundamentals_log.last_filed,
       fundamentals_log."rows", fundamentals_log.error)
      IS DISTINCT FROM
      (EXCLUDED.status, EXCLUDED.first_filed, EXCLUDED.last_filed,
       EXCLUDED."rows", EXCLUDED.error)
  AND NOT (fundamentals_log.status = 'ok' AND EXCLUDED.status = 'failed')
"""


def _write_batch(
    conn: psycopg.Connection, results: Sequence[CikResult], dry_run: bool
) -> int:
    """One batch's facts and its log rows, in one transaction. A crash before the commit
    loses this batch and nothing else; the log rows are written with the facts they
    describe, so a resumed run can never skip a CIK whose facts were not stored.

    ``results`` is a sequence of ``CikResult``, one per distinct CIK -- the batch loop never
    sees a symbol. That is what makes the log row count equal the fetch count (C2), and it is
    why ``executemany`` cannot hit the same primary key twice in one call: ``plan_jobs``
    guarantees the CIKs in a batch are distinct.

    Symbols with no CIK never reach here. ``plan_jobs`` returns them separately and they get
    no log row at all, because the table's primary key is a ``bigint`` CIK and they have
    none. They are re-evaluated on the next run, which is correct: nothing was fetched and
    nothing was stored.
    """
    params = [
        (
            int(r.cik),
            r.status,
            min(f.filed for f in r.facts) if r.facts else None,
            max(f.filed for f in r.facts) if r.facts else None,
            len(r.facts),
            r.error,
        )
        for r in results
    ]
    with db.transaction(conn, dry_run):
        written = upsert_facts(conn, ((int(r.cik), f) for r in results for f in r.facts))
        with conn.cursor() as cur:
            cur.executemany(_LOG_UPSERT, params)
    return written


_MAP_SELECT = (
    "SELECT symbol, cik, start_date, end_date, company, source, note FROM ticker_cik"
)
_MAP_INSERT = (
    "INSERT INTO ticker_cik (symbol, cik, start_date, end_date, company, source, note) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s)"
)


def sync_ticker_cik(
    conn: psycopg.Connection, mappings: Iterable[cik.CikRow], dry_run: bool
) -> tuple[int, bool]:
    """Mirror the vendored map into ``ticker_cik``: a full replace in one transaction, a
    no-op when the stored rows already equal the computed ones -- the shape
    ``universe refresh`` uses (commands/universe.py:306-312). Returns (rows, changed).

    Phase 2's column names, not phase 1's CSV header (C3): ``symbol``, and ``company`` for the
    CSV's ``company_name``. ``cik`` is a ``bigint``, so the CSV's 10-digit zero-padded string
    is parsed with ``int()``. **Rows whose CSV ``cik`` is ``cik.NO_FILER`` are skipped** --
    the column is NOT NULL and those symbols have no EDGAR filer to record. They are still
    resolvable from the CSV, which is what ``resolve_window_cik`` reads; the table is a mirror
    for SQL joins (phase 6's panel load), not the source of truth.
    """
    wanted = {
        (
            m.symbol,
            int(m.cik),
            m.start_date,
            m.end_date,
            m.company_name,
            m.source,
            m.note or None,
        )
        for m in mappings
        if m.cik != cik.NO_FILER
    }
    stored = {tuple(row) for row in conn.execute(_MAP_SELECT).fetchall()}
    if stored == wanted:
        conn.rollback()
        log.info("fundamentals: ticker_cik unchanged (%d rows)", len(wanted))
        return len(wanted), False
    ordered = sorted(wanted, key=lambda r: (r[0], r[2]))  # (symbol, start_date) -- the PK
    with db.transaction(conn, dry_run):
        with conn.cursor() as cur:
            cur.execute("DELETE FROM ticker_cik")
            cur.executemany(_MAP_INSERT, ordered)
    log.info("fundamentals: ticker_cik replaced with %d rows", len(wanted))
    return len(wanted), True
```
**Impact:** `_FACTS_UPSERT` is the single place the phase-2 key contract (C1) is encoded, and
`_LOG_UPSERT` the single place C2 is. `sync_ticker_cik` is the one step this phase adds beyond
the index's own exit-criteria list; the index's Decisions table assigns it here, so it is this
phase's work and this phase's **R1** — see Handoff H1.

### Step 9: The orchestrator
**File:** `engine/src/seer_engine/commands/fundamentals.py:~660`
**Change:** `ingest`, the testable entry point, mirroring `backfill.backfill`
(`backfill.py:190–275`), **with CIKs as the unit of work and symbols only in the summary**
(C2). No inter-batch sleep: `sec.Client` paces itself.
**Code:**
```python
def ingest(
    conn: psycopg.Connection,
    opts: Options,
    *,
    source: FactsSource,
    mappings: Sequence[cik.CikRow] | None = None,
) -> Summary:
    """Run the ingest on ``conn``. The SEC client is injected, so tests never touch the
    network and no sleep ever happens here.

    Order matters: the map is resolved and the jobs planned **before** the map mirror runs,
    so a dry run plans against exactly the rows a real run would.
    """
    summary = Summary()
    rows = list(load_cik_map()) if mappings is None else list(mappings)
    if not rows:
        raise FundamentalsError(
            "the vendored ticker->CIK map is empty; generate engine/data/ticker_cik.csv first"
        )

    windows = membership_windows(conn, opts.since, opts.today)
    symbols = select_symbols(opts, windows)
    jobs, unresolved, summary.skipped = plan_jobs(conn, opts, symbols, windows, rows)
    _end_read(conn)

    if opts.sync_map:
        summary.map_rows, summary.map_changed = sync_ticker_cik(conn, rows, opts.dry_run)
        _end_read(conn)

    for result in unresolved:
        _record(summary, result)
    _ingest_facts(conn, opts, jobs, summary, source)

    summary.facts_bytes = _facts_size(conn)
    _end_read(conn)
    _sort_summary(summary)
    return summary


def _ingest_facts(
    conn: psycopg.Connection,
    opts: Options,
    jobs: Sequence[CikJob],
    summary: Summary,
    source: FactsSource,
) -> None:
    """Fetch and write ``jobs`` in batches. ``batch_size`` counts **CIKs** -- one SEC call
    each -- not symbols; a batch of 20 is 20 fetches whether or not a share class is in it."""
    size = opts.batch_size
    batches = [list(jobs[i : i + size]) for i in range(0, len(jobs), size)]
    log.info(
        "fundamentals: %d CIKs covering %d symbols in %d batches (%d symbols skipped), "
        "facts filed on or after %s",
        len(jobs), sum(len(j.symbols) for j in jobs), len(batches), summary.skipped,
        opts.since_filed,
    )
    for number, batch in enumerate(batches, start=1):
        results = [fetch_cik(job, opts, source) for job in batch]
        written = _write_batch(conn, results, opts.dry_run)
        summary.facts_written += written
        for result in results:
            summary.ciks_fetched += 1
            summary.facts_fetched += len(result.facts)   # per CIK: never double-counted
            for per in result.per_symbol():
                _record(summary, per)
        log.info(
            "fundamentals: batch %d/%d done: %d ok, %d empty, %d failed, %d fact rows changed",
            number, len(batches),
            sum(r.status == STATUS_OK for r in results),
            sum(r.status == STATUS_EMPTY for r in results),
            sum(r.status == STATUS_FAILED for r in results),
            written,
        )


def _record(summary: Summary, result: SymbolResult) -> None:
    """File one symbol's outcome into the summary. The only writer of the three lists."""
    if result.status == STATUS_OK:
        summary.ok.append(result.symbol)
    elif result.status == STATUS_EMPTY:
        summary.empty.append(result.symbol)
    else:
        summary.failed.append(result.symbol)


def _sort_summary(summary: Summary) -> None:
    """The three lists are sorted at the end, because unresolved symbols are filed before the
    fetched ones and a share-class fan-out appends two at once. Deterministic output is what
    makes ``format_summary`` testable and a run-to-run diff meaningful."""
    summary.ok.sort()
    summary.empty.sort()
    summary.failed.sort()


def _facts_size(conn: psycopg.Connection) -> int:
    row = conn.execute("SELECT pg_total_relation_size('fundamental_facts')").fetchone()
    return int(row[0])


def _end_read(conn: psycopg.Connection) -> None:
    """Close the implicit read-only transaction so db.transaction starts at top level."""
    conn.rollback()
```
**Impact:** `--symbols` with a symbol that is not an index member still works: `plan_jobs` falls
its window back to `(since, today)`, which is the right probe for a name being added by hand.

**And the fan-out is now visible in the numbers.** `summary.ciks_fetched` is the SEC call
count; `len(ok) + len(empty) + len(failed)` is the symbol count. They differ exactly by the
share-class pairs in scope, which is the assertion the two new tests in Step 11 make.

### Step 10: The summary
**File:** `engine/src/seer_engine/commands/fundamentals.py:~740`
**Change:** `format_summary`, mirroring `backfill.format_summary` (`backfill.py:424–450`),
including the table-size line that gives the operator the 0.5 GB stop-line signal.
**Code:**
```python
def format_summary(summary: Summary, opts: Options) -> str:
    lines = [
        f"fundamentals: members since {opts.since.isoformat()}, "
        f"facts filed on or after {opts.since_filed.isoformat()}"
        + (" (dry run: every write rolled back)" if opts.dry_run else ""),
    ]
    if opts.sync_map:
        state = "replaced" if summary.map_changed else "unchanged"
        lines.append(f"  ticker_cik: {summary.map_rows} rows, {state}")
    lines.append(
        f"  symbols: {len(summary.ok)} ok, {len(summary.empty)} empty, "
        f"{len(summary.failed)} failed, {summary.skipped} skipped (CIK already logged)"
    )
    # The counts above are per symbol; the fetch and the log are per CIK (C2). The two differ
    # by the share-class pairs in scope, and printing both is what tells the operator that
    # GOOG and GOOGL cost one SEC call and hold one fundamentals_log row between them.
    lines.append(
        f"  filers: {summary.ciks_fetched} companyfacts calls, "
        f"{summary.ciks_fetched} fundamentals_log rows written"
    )
    lines.append(
        f"  facts: {summary.facts_fetched:,} kept, "
        f"{summary.facts_written:,} inserted or changed"
    )
    if summary.failed:
        lines.append(
            f"  failed: {', '.join(summary.failed)}  (re-run with --retry-failed)"
        )
    if summary.empty:
        lines.append(f"  empty: {', '.join(summary.empty)}")
    if summary.facts_bytes is not None:
        lines.append(
            f"  fundamental_facts table: {summary.facts_bytes / (1024 * 1024):.1f} MB "
            "(pg_total_relation_size)"
        )
    return "\n".join(lines)
```
**Impact:** none beyond stdout.

### Step 11: The test module
**File:** `engine/tests/test_fundamentals_command.py:1`
**Change:** create the file. The two fakes isolate every cross-phase assumption: `fact()` is the
only place `sec.Fact`'s field names appear, `Mapping` is the only place the CIK-row shape
appears. No test touches the network; none sleeps; none reads or writes `bars`.
**Code:**
```python
"""Tests for the fundamentals command: scope selection, dated CIK resolution, batching and
resume, restatements, the tag allowlist, the filed cutoff, idempotency, dry run, and the
exit-code contract. No test touches the network -- the SEC client is an injected fake -- and
none of them creates a single row in ``bars``: a symbol with no price history must still get
its fundamentals (Gap A independence).

Two helpers carry every cross-phase assumption, so a contract change is a one-place fix:
``fact()`` is the only place ``sec.Fact``'s field names appear, and ``Mapping`` is the only
place the phase-1 CIK row shape appears.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime, timezone

import pytest

from seer_engine import sec
from seer_engine.commands import fundamentals as fcmd

SINCE = date(2015, 1, 2)
TODAY = date(2026, 10, 5)

Q3_END = date(2015, 9, 30)
Q4_END = date(2015, 12, 31)
FILED_Q3 = date(2015, 10, 30)
FILED_Q4 = date(2016, 2, 26)
FILED_RESTATED = date(2016, 11, 4)
FILED_OLD = date(2010, 5, 7)

ACCN_1 = "0000718877-16-000045"
ACCN_2 = "0000718877-16-000112"


CIK_10 = "0000718877"   # ATVI; the default fact() owner


@dataclass(frozen=True)
class Mapping:
    """Stand-in for phase 1's ``cik.CikRow``: the attributes fundamentals.py actually reads.

    The field names are phase 1's, not a guess (C5): **``symbol``**, not ``ticker``, and
    **``company_name``**, not ``company``. ``source`` is one of phase 1's five tier labels and
    is read by ``sync_ticker_cik``. Getting any of these wrong here would make the fake pass
    while the real ``cik.CikRow`` raised ``AttributeError``, so this is the single place the
    phase-1 row shape appears.
    """

    symbol: str
    cik: str
    company_name: str = "Test Co"
    start_date: date = date(1990, 1, 1)
    end_date: date | None = None
    source: str = "manual"
    note: str = ""


def fact(
    tag="Assets",
    *,
    taxonomy="us-gaap",
    unit="USD",
    start=None,
    end=Q4_END,
    val=100.0,
    accn=ACCN_1,
    form="10-K",
    fy=2015,
    fp="FY",
    filed=FILED_Q4,
    frame=None,
):
    """One parsed XBRL fact. The only place sec.Fact's field names are spelled (C4)."""
    return sec.Fact(
        cik=CIK_10,
        taxonomy=taxonomy,
        tag=tag,
        unit=unit,
        period_start=start,
        period_end=end,
        val=val,
        accn=accn,
        form=form,
        fy=fy,
        fp=fp,
        filed=filed,
        frame=frame,
    )


class FakeSec:
    """Injected FactsSource. facts: CIK -> list[Fact]. errors: CIK -> exception to raise.

    Returns a real ``sec.CompanyFacts``, not a bare list (C4): the client's return type is the
    wrapper and ``fetch_cik`` reads ``.facts`` off it, so a fake that returned a list would
    pass here and fail against the shipped client. ``calls`` records every CIK fetched, in
    order -- it is what the share-class tests assert on.
    """

    def __init__(self, facts=None, *, errors=None):
        self.facts = dict(facts or {})
        self.errors = dict(errors or {})
        self.calls: list[str] = []

    def company_facts(self, cik, *, tags=None):
        self.calls.append(cik)
        if cik in self.errors:
            raise self.errors[cik]
        return sec.CompanyFacts(
            cik=cik, entity_name="Test Co", facts=tuple(self.facts.get(cik, []))
        )


def opts(**kw):
    base = dict(today=TODAY, since=SINCE, sync_map=False)
    base.update(kw)
    return fcmd.Options(**base)


def seed_universe(conn, rows):
    """rows: (symbol, index_id, start_date, end_date). Commits."""
    conn.executemany(
        "INSERT INTO universe (symbol, index_id, start_date, end_date, source_symbol) "
        "VALUES (%s, %s, %s, %s, %s)",
        [(s, i, a, b, s) for (s, i, a, b) in rows],
    )
    conn.commit()


def fact_rows(conn):
    rows = conn.execute(
        "SELECT cik, taxonomy, tag, unit, period_start, period_end, accn, filed, val "
        "FROM fundamental_facts ORDER BY cik, tag, period_start, period_end, accn"
    ).fetchall()
    conn.rollback()
    return rows


def log_rows(conn):
    """``fundamentals_log`` keyed by CIK (C2) -- one row per companyfacts fetch, not per symbol.

    Returns ``{cik10: (status, first_filed, last_filed, rows, error)}``. The key is the
    10-digit zero-padded string, because that is what the module works in; the column is a
    ``bigint``. **There is no `symbol` column to key on** -- a test that looked one up by
    ticker would be asserting the contract phase 2 rejected.
    """
    rows = conn.execute(
        'SELECT cik, status, first_filed, last_filed, "rows", error '
        "FROM fundamentals_log ORDER BY cik"
    ).fetchall()
    conn.rollback()
    return {sec.cik10(r[0]): r[1:] for r in rows}


def count(conn, table):
    n = conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    conn.rollback()
    return n


# ------------------------------------------------------------------ CLI arguments


def parse(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    fcmd.add_arguments(p)
    return p.parse_args(argv)


def test_arguments_defaults_and_symbol_normalisation():
    args = parse([])
    assert args.since == date(2015, 1, 2)
    assert args.since_filed == date(2013, 1, 1)
    assert args.batch_size == 20 and args.symbols is None and args.no_sync_map is False
    args = parse(["--symbols", "brk-b, atvi,ATVI", "--batch-size", "5", "--no-sync-map"])
    assert args.symbols == ["BRK.B", "ATVI"]
    assert args.batch_size == 5 and args.no_sync_map is True


def test_arguments_reject_bad_input():
    with pytest.raises(SystemExit):
        parse(["--batch-size", "0"])
    with pytest.raises(SystemExit):
        parse(["--since", "01/02/2015"])
    with pytest.raises(SystemExit):
        parse(["--symbols", "not a ticker!"])


def test_options_reject_a_filed_cutoff_after_the_window_opens():
    now = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)
    o = fcmd.options_from_args(parse(["--dry-run"]), now=now)
    assert o.today == date(2026, 10, 5) and o.dry_run is True and o.sync_map is True
    with pytest.raises(fcmd.FundamentalsError, match="since-filed"):
        fcmd.options_from_args(parse(["--since-filed", "2016-01-01"]), now=now)
    with pytest.raises(fcmd.FundamentalsError, match="future"):
        fcmd.options_from_args(parse(["--since", "2030-01-02"]), now=now)


# ------------------------------------------------- dated CIK resolution (invariant 4)


def test_recycled_ticker_resolves_to_the_holder_during_membership():
    rows = [
        Mapping("CA", "0000356028", "CA Inc.", date(1990, 1, 1), date(2018, 11, 6)),
        Mapping("CA", "0001503290", "Xtrackers CA Muni ETF", date(2018, 11, 6), None),
    ]
    assert fcmd.resolve_window_cik(rows, "CA", SINCE, date(2018, 11, 5)) == (
        "0000356028", fcmd.STATUS_OK, None
    )
    held_now = fcmd.resolve_cik(rows, "CA", date(2026, 1, 2))
    assert held_now is not None and held_now.cik == "0001503290"


def test_a_ticker_changing_hands_mid_membership_is_a_failure_not_a_guess():
    rows = [
        Mapping("CA", "0000356028", "CA Inc.", date(1990, 1, 1), date(2018, 11, 6)),
        Mapping("CA", "0001503290", "Xtrackers CA Muni ETF", date(2018, 11, 6), None),
    ]
    number, status, why = fcmd.resolve_window_cik(rows, "CA", SINCE, date(2020, 1, 2))
    assert number is None and status == fcmd.STATUS_FAILED and "changed hands" in why


def test_an_unmapped_ticker_says_what_to_do_about_it():
    number, status, why = fcmd.resolve_window_cik([], "NDOI", SINCE, TODAY)
    assert number is None and status == fcmd.STATUS_FAILED and "ticker_cik.csv" in why


def test_a_none_filer_is_empty_not_failed():
    """The map ANSWERED: there is nothing at EDGAR. That is `empty`, and `empty` exits 0."""
    rows = [Mapping("DEAD", fcmd.cik.NO_FILER, "Private LBO", note="no EDGAR filer")]
    number, status, why = fcmd.resolve_window_cik(rows, "DEAD", SINCE, TODAY)
    assert number is None and status == fcmd.STATUS_EMPTY and "no EDGAR filer" in why


# ---------------------------------------------------------------- fact filtering


def test_select_facts_keeps_only_allowlisted_tags_filed_in_range():
    facts = [
        fact("Assets"),
        fact("NetIncomeLoss", start=date(2015, 1, 1)),
        fact("AccruedLiabilitiesCurrent"),            # not in LADDER_TAGS
        fact("Assets", end=date(2010, 3, 31), filed=FILED_OLD),  # before the cutoff
    ]
    kept = fcmd.select_facts(facts, fcmd.DEFAULT_SINCE_FILED)
    assert [f.tag for f in kept] == ["Assets", "NetIncomeLoss"]


def test_shares_outstanding_comes_from_the_dei_taxonomy():
    from seer_engine.fundamentals import ladder

    assert ("dei", "EntityCommonStockSharesOutstanding") in fcmd.LADDER_TAGS
    assert ("us-gaap", "EntityCommonStockSharesOutstanding") not in fcmd.LADDER_TAGS
    # The allowlist is phase 5's object, not a copy of it: a drift between the ingest and the
    # ladder is the one failure mode this import exists to make impossible.
    assert fcmd.LADDER_TAGS is ladder.LADDER_TAGS
    kept = fcmd.select_facts(
        [fact("EntityCommonStockSharesOutstanding", taxonomy="dei", unit="shares")],
        fcmd.DEFAULT_SINCE_FILED,
    )
    assert len(kept) == 1


# ------------------------------------------------------------------- ingest (DB)


def test_batches_resume_and_skip_already_logged(pg):
    seed_universe(
        pg,
        [
            ("AAA", "SP500", date(2014, 1, 2), None),
            ("BBB", "SP500", date(2015, 3, 2), date(2019, 6, 3)),
            ("CCC", "NDX", date(2016, 1, 4), None),
            ("SPY", "SP500", date(2014, 1, 2), None),
        ],
    )
    # The log is keyed by cik (C2): a bigint, and there is NO symbol column to seed.
    pg.execute("INSERT INTO fundamentals_log (cik, status, \"rows\") VALUES (1, 'ok', 2)")
    pg.commit()
    rows = [Mapping(t, f"000000000{i}") for i, t in enumerate(["AAA", "BBB", "CCC"], start=1)]
    source = FakeSec({f"000000000{i}": [fact()] for i in (1, 2, 3)})

    s = fcmd.ingest(pg, opts(batch_size=1), source=source, mappings=rows)

    assert source.calls == ["0000000002", "0000000003"]   # AAA skipped, SPY never a candidate
    assert s.ok == ["BBB", "CCC"] and s.skipped == 1 and s.exit_code() == 0
    assert s.ciks_fetched == 2
    assert count(pg, "fundamental_facts") == 2
    assert set(log_rows(pg)) == {"0000000001", "0000000002", "0000000003"}
    assert log_rows(pg)["0000000002"][:4] == ("ok", FILED_Q4, FILED_Q4, 1)

    again = FakeSec({f"000000000{i}": [fact()] for i in (1, 2, 3)})
    s2 = fcmd.ingest(pg, opts(batch_size=1), source=again, mappings=rows)
    assert again.calls == [] and s2.skipped == 3 and s2.facts_written == 0


# --------------------------------------------------- the share-class fan-out (C2's reason)


def test_a_share_class_pair_is_one_fetch_and_one_log_row(pg):
    """GOOG and GOOGL are one CIK. One companyfacts call, one fundamentals_log row, and the
    summary still reports BOTH symbols -- that is the whole point of C2."""
    seed_universe(
        pg,
        [
            ("GOOG", "SP500", date(2015, 1, 2), None),
            ("GOOGL", "SP500", date(2015, 1, 2), None),
        ],
    )
    rows = [
        Mapping("GOOG", "0001652044", "Alphabet Inc."),
        Mapping("GOOGL", "0001652044", "Alphabet Inc."),
    ]
    source = FakeSec({"0001652044": [fact(), fact("NetIncomeLoss", start=date(2015, 1, 1))]})

    s = fcmd.ingest(pg, opts(), source=source, mappings=rows)

    assert source.calls == ["0001652044"]          # ONE fetch, not two
    assert s.ciks_fetched == 1
    assert s.ok == ["GOOG", "GOOGL"]               # but BOTH symbols reported
    assert set(log_rows(pg)) == {"0001652044"}     # ONE log row
    assert log_rows(pg)["0001652044"][3] == 2      # "rows" counted once, not doubled
    assert s.facts_fetched == 2                    # not 4
    assert count(pg, "fundamental_facts") == 2


def test_a_second_run_skips_a_share_class_cik_for_both_symbols(pg):
    """Resume is per CIK, so naming either twin on a later run re-fetches nothing."""
    seed_universe(
        pg,
        [
            ("GOOG", "SP500", date(2015, 1, 2), None),
            ("GOOGL", "SP500", date(2015, 1, 2), None),
        ],
    )
    rows = [Mapping("GOOG", "0001652044"), Mapping("GOOGL", "0001652044")]
    data = {"0001652044": [fact()]}
    fcmd.ingest(pg, opts(), source=FakeSec(data), mappings=rows)

    again = FakeSec(data)
    s = fcmd.ingest(pg, opts(), source=again, mappings=rows)
    assert again.calls == [] and s.skipped == 2 and s.ciks_fetched == 0

    # ...and naming only ONE twin on a fresh log fetches the CIK once and reports only it.
    pg.execute("DELETE FROM fundamentals_log")
    pg.commit()
    solo = FakeSec(data)
    s2 = fcmd.ingest(pg, opts(symbols=("GOOG",)), source=solo, mappings=rows)
    assert solo.calls == ["0001652044"] and s2.ok == ["GOOG"]
    assert set(log_rows(pg)) == {"0001652044"}


def test_the_benchmark_is_never_fetched(pg):
    seed_universe(pg, [("SPY", "SP500", date(2014, 1, 2), None)])
    source = FakeSec()
    with pytest.raises(fcmd.FundamentalsError, match="universe refresh"):
        fcmd.ingest(pg, opts(), source=source, mappings=[Mapping("SPY", "0000884394")])
    assert source.calls == []


def test_a_symbol_with_no_bars_still_gets_fundamentals(pg):
    """Gap A independence: 133 ever-members have zero rows in bars and must still load."""
    seed_universe(pg, [("ATVI", "SP500", date(2015, 1, 2), date(2023, 10, 16))])
    source = FakeSec({"0000718877": [fact(), fact("NetIncomeLoss", start=date(2015, 1, 1))]})

    s = fcmd.ingest(pg, opts(), source=source, mappings=[Mapping("ATVI", "0000718877")])

    assert count(pg, "bars") == 0
    assert s.ok == ["ATVI"] and count(pg, "fundamental_facts") == 2


def test_a_restatement_is_a_new_row_not_an_overwrite(pg):
    """Invariant 3: accn is part of the fact identity."""
    seed_universe(pg, [("ATVI", "SP500", date(2015, 1, 2), None)])
    source = FakeSec(
        {
            "0000718877": [
                fact("Assets", val=1000.0, accn=ACCN_1, filed=FILED_Q4),
                fact("Assets", val=1100.0, accn=ACCN_2, filed=FILED_RESTATED),
            ]
        }
    )

    fcmd.ingest(pg, opts(), source=source, mappings=[Mapping("ATVI", "0000718877")])

    rows = fact_rows(pg)
    assert len(rows) == 2
    assert {(r[6], r[7], float(r[8])) for r in rows} == {
        (ACCN_1, FILED_Q4, 1000.0),
        (ACCN_2, FILED_RESTATED, 1100.0),
    }


def test_annual_and_quarterly_in_one_filing_do_not_collide(pg):
    """Same cik/tag/unit/period_end/accn, different period_start: both must survive (C1)."""
    seed_universe(pg, [("ATVI", "SP500", date(2015, 1, 2), None)])
    source = FakeSec(
        {
            "0000718877": [
                fact("Revenues", start=date(2015, 1, 1), end=Q4_END, val=4600.0, fp="FY"),
                fact("Revenues", start=date(2015, 10, 1), end=Q4_END, val=1350.0, fp="Q4"),
            ]
        }
    )

    fcmd.ingest(pg, opts(), source=source, mappings=[Mapping("ATVI", "0000718877")])

    rows = fact_rows(pg)
    assert len(rows) == 2
    assert {(r[4], float(r[8])) for r in rows} == {
        (date(2015, 1, 1), 4600.0),
        (date(2015, 10, 1), 1350.0),
    }


def test_an_instantaneous_fact_stores_period_start_equal_to_period_end(pg):
    seed_universe(pg, [("ATVI", "SP500", date(2015, 1, 2), None)])
    source = FakeSec({"0000718877": [fact("Assets", start=None, end=Q4_END)]})

    fcmd.ingest(pg, opts(), source=source, mappings=[Mapping("ATVI", "0000718877")])

    (row,) = fact_rows(pg)
    assert row[4] == Q4_END and row[5] == Q4_END


def test_a_filer_with_no_usable_facts_is_empty_not_an_error(pg):
    seed_universe(pg, [("DEAD", "SP500", date(2015, 1, 2), date(2016, 1, 4))])
    source = FakeSec({"0000000009": [fact("AccruedLiabilitiesCurrent")]})

    s = fcmd.ingest(pg, opts(), source=source, mappings=[Mapping("DEAD", "0000000009")])

    assert s.empty == ["DEAD"] and s.failed == [] and s.exit_code() == 0
    status, first, last, n, error = log_rows(pg)["0000000009"]
    assert (status, first, last, n) == ("empty", None, None, 0)
    assert "ingest tag set" in error


def test_a_symbol_the_map_marks_NONE_is_empty_and_gets_no_log_row(pg):
    """The map answered "no EDGAR filer". No CIK means no fetch and no row to log against a
    bigint primary key -- and `empty` means exit 0 (Summary.exit_code is unchanged)."""
    seed_universe(pg, [("DEAD", "SP500", date(2015, 1, 2), date(2016, 1, 4))])
    source = FakeSec()

    s = fcmd.ingest(
        pg, opts(), source=source,
        mappings=[Mapping("DEAD", fcmd.cik.NO_FILER, note="taken private, no filer")],
    )

    assert source.calls == [] and s.empty == ["DEAD"] and s.exit_code() == 0
    assert count(pg, "fundamentals_log") == 0


def test_one_failure_does_not_lose_the_rest_of_the_run(pg):
    seed_universe(
        pg,
        [
            ("AAA", "SP500", date(2015, 1, 2), None),
            ("BAD", "SP500", date(2015, 1, 2), None),
            ("CCC", "SP500", date(2015, 1, 2), None),
        ],
    )
    rows = [Mapping("AAA", "0000000001"), Mapping("BAD", "0000000002"), Mapping("CCC", "0000000003")]
    source = FakeSec(
        {"0000000001": [fact()], "0000000003": [fact()]},
        errors={"0000000002": sec.SecError("HTTP 503 from data.sec.gov")},
    )

    s = fcmd.ingest(pg, opts(batch_size=2), source=source, mappings=rows)

    assert s.ok == ["AAA", "CCC"] and s.failed == ["BAD"] and s.exit_code() == 1
    assert count(pg, "fundamental_facts") == 2
    assert log_rows(pg)["0000000002"][0] == "failed"
    assert "503" in log_rows(pg)["0000000002"][4]


def test_an_unmapped_symbol_fails_and_is_retried_every_run(pg):
    """No row in the map means no CIK, so there is nothing to log against a bigint PK. The
    symbol stays `failed` and is re-attempted on the next run with no `--retry-failed`, which
    is what makes phase 1's coverage criterion machine-checkable (C8)."""
    seed_universe(pg, [("NDOI", "SP500", date(2015, 1, 2), date(2015, 7, 1))])
    source = FakeSec()

    s = fcmd.ingest(pg, opts(), source=source, mappings=[Mapping("AAA", "0000000001")])

    assert source.calls == [] and s.failed == ["NDOI"] and s.exit_code() == 1
    assert count(pg, "fundamentals_log") == 0

    again = fcmd.ingest(pg, opts(), source=FakeSec(), mappings=[Mapping("AAA", "0000000001")])
    assert again.failed == ["NDOI"] and again.skipped == 0


def test_a_failed_attempt_never_downgrades_a_filer_already_ok(pg):
    seed_universe(pg, [("AAA", "SP500", date(2015, 1, 2), None)])
    rows = [Mapping("AAA", "0000000001")]
    fcmd.ingest(pg, opts(), source=FakeSec({"0000000001": [fact()]}), mappings=rows)
    broken = FakeSec(errors={"0000000001": sec.SecError("HTTP 500")})

    fcmd.ingest(pg, opts(symbols=("AAA",)), source=broken, mappings=rows)

    assert log_rows(pg)["0000000001"][0] == "ok"
    assert count(pg, "fundamental_facts") == 1


def test_retry_failed_reattempts_failed_and_empty_only(pg):
    seed_universe(
        pg,
        [
            ("AAA", "SP500", date(2015, 1, 2), None),
            ("BBB", "SP500", date(2015, 1, 2), None),
            ("CCC", "SP500", date(2015, 1, 2), None),
        ],
    )
    pg.execute(
        'INSERT INTO fundamentals_log (cik, status, "rows") VALUES '
        "(1, 'ok', 1), (2, 'failed', 0), (3, 'empty', 0)"
    )
    pg.commit()
    rows = [Mapping(t, f"000000000{i}") for i, t in enumerate(["AAA", "BBB", "CCC"], start=1)]
    data = {f"000000000{i}": [fact()] for i in (1, 2, 3)}

    plain = FakeSec(data)
    fcmd.ingest(pg, opts(), source=plain, mappings=rows)
    assert plain.calls == []

    retry = FakeSec(data)
    s = fcmd.ingest(pg, opts(retry_failed=True), source=retry, mappings=rows)
    assert retry.calls == ["0000000002", "0000000003"]
    assert s.ok == ["BBB", "CCC"] and log_rows(pg)["0000000002"][0] == "ok"


def test_a_second_run_with_the_same_arguments_writes_zero_rows(pg):
    seed_universe(pg, [("ATVI", "SP500", date(2015, 1, 2), None)])
    rows = [Mapping("ATVI", "0000718877")]
    data = {
        "0000718877": [
            fact("Assets", val=1000.0),
            fact("Revenues", start=date(2015, 1, 1), val=4600.0),
        ]
    }

    s1 = fcmd.ingest(pg, opts(symbols=("ATVI",)), source=FakeSec(data), mappings=rows)
    before = fact_rows(pg)
    logged_before = log_rows(pg)
    s2 = fcmd.ingest(pg, opts(symbols=("ATVI",)), source=FakeSec(data), mappings=rows)

    assert s1.facts_written == 2 and s2.facts_written == 0
    assert fact_rows(pg) == before and log_rows(pg) == logged_before


def test_a_duplicated_fact_in_one_response_does_not_abort_the_batch(pg):
    seed_universe(pg, [("ATVI", "SP500", date(2015, 1, 2), None)])
    source = FakeSec({"0000718877": [fact("Assets"), fact("Assets")]})

    s = fcmd.ingest(pg, opts(), source=source, mappings=[Mapping("ATVI", "0000718877")])

    assert s.ok == ["ATVI"] and count(pg, "fundamental_facts") == 1


def test_dry_run_writes_nothing(pg):
    seed_universe(pg, [("ATVI", "SP500", date(2015, 1, 2), None)])
    source = FakeSec({"0000718877": [fact(), fact("NetIncomeLoss", start=date(2015, 1, 1))]})

    s = fcmd.ingest(
        pg,
        opts(dry_run=True, sync_map=True),
        source=source,
        mappings=[Mapping("ATVI", "0000718877")],
    )

    assert s.facts_written == 2 and s.map_rows == 1 and s.map_changed is True
    assert count(pg, "fundamental_facts") == 0
    assert count(pg, "fundamentals_log") == 0
    assert count(pg, "ticker_cik") == 0


def test_sync_ticker_cik_replaces_then_is_a_no_op(pg):
    seed_universe(pg, [("CA", "SP500", date(2015, 1, 2), date(2018, 11, 6))])
    rows = [
        Mapping("CA", "0000356028", "CA Inc.", date(1990, 1, 1), date(2018, 11, 6),
                "manual", "member"),
        Mapping("CA", "0001503290", "Xtrackers CA Muni ETF", date(2018, 11, 6), None,
                "current", "recycled"),
    ]
    source = FakeSec({"0000356028": [fact()]})

    s1 = fcmd.ingest(pg, opts(sync_map=True), source=source, mappings=rows)
    assert (s1.map_rows, s1.map_changed) == (2, True)
    assert count(pg, "ticker_cik") == 2
    assert source.calls == ["0000356028"]   # the holder during membership, not today's

    s2 = fcmd.ingest(pg, opts(sync_map=True, symbols=("CA",)), source=FakeSec({"0000356028": [fact()]}), mappings=rows)
    assert (s2.map_rows, s2.map_changed) == (2, False)


def test_an_empty_vendored_map_is_an_exit_2_condition(pg):
    seed_universe(pg, [("AAA", "SP500", date(2015, 1, 2), None)])
    with pytest.raises(fcmd.FundamentalsError, match="ticker_cik.csv"):
        fcmd.ingest(pg, opts(), source=FakeSec(), mappings=[])


def test_summary_text_reports_counts_and_table_size(pg):
    seed_universe(pg, [("ATVI", "SP500", date(2015, 1, 2), None)])
    o = opts()
    s = fcmd.ingest(pg, o, source=FakeSec({"0000718877": [fact()]}),
                    mappings=[Mapping("ATVI", "0000718877")])
    assert s.facts_bytes is not None and s.facts_bytes > 0
    text = fcmd.format_summary(s, o)
    assert "1 ok, 0 empty, 0 failed" in text
    assert "fundamental_facts table:" in text
```
**Impact:** `test_cli.py` already asserts every discovered module has `run`; this module adds a
row to the command list there with no edit.

## Verification

**Build (import and discovery):**
```bash
cd /home/miftah/.worktrees/seer/edgar-fundamentals
engine/.venv/bin/python -c "from seer_engine.commands import fundamentals; print(fundamentals.HELP)"
engine/.venv/bin/python -m seer_engine --help | grep fundamentals
engine/.venv/bin/python -m seer_engine fundamentals --help
```

**Lint:**
```bash
cd /home/miftah/.worktrees/seer/edgar-fundamentals
engine/.venv/bin/ruff check engine/src/seer_engine/commands/fundamentals.py \
                            engine/tests/test_fundamentals_command.py
```

**Tests (whole suite — invariant 1 is the gate, not just this module):**
```bash
cd /home/miftah/.worktrees/seer/edgar-fundamentals
docker start seer-pg 2>/dev/null || docker run -d --name seer-pg \
  -e POSTGRES_PASSWORD=pg -p 55432:5432 postgres:16
export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres
engine/.venv/bin/pytest engine/tests -q
engine/.venv/bin/pytest engine/tests/test_fundamentals_command.py -q
engine/.venv/bin/pytest engine/tests/test_strategy_purity.py engine/tests/test_cli.py -q
```

**Manual check (one real, paced call to data.sec.gov; nothing is written):**
```bash
cd /home/miftah/.worktrees/seer/edgar-fundamentals
engine/.venv/bin/python -m seer_engine --dry-run -v fundamentals \
  --symbols ATVI,TWTR,CELG,K --no-sync-map
```
Expect: 4 SEC calls at least 0.1 s apart, four `ok` symbols, a non-zero `facts` count,
"dry run: every write rolled back", exit 0, and `select count(*) from fundamental_facts` still 0.

**Exit-code contract this command commits to** (phase 7 writes it into
`docs/runbooks/data-pipeline.md`'s table at `docs/runbooks/data-pipeline.md:51–56`, next to
`backfill`'s row):

| Command | 0 | 1 | 2 |
|---|---|---|---|
| `fundamentals` | no symbol `failed` (`empty` = a filer with no fact in the ingest tag set is expected and fine) | some symbol `failed` (SEC error, or no CIK for it in `ticker_cik.csv`); the facts already fetched are committed → re-run with `--retry-failed` | empty universe (run `universe refresh`), an empty `ticker_cik.csv`, bad arguments, or a missing `SEC_CONTACT_EMAIL` / `DATABASE_URL_UNPOOLED` |

Rows for the "What it does" table (same file, `:31–42`):

| `… -m seer_engine fundamentals` | one `data.sec.gov` companyfacts call per **CIK** behind the ever-members since 2015-01-02, resolved by (ticker, date); a share-class pair (GOOG/GOOGL) is one call and one log row; skips every CIK already in `fundamentals_log` (any status), so a re-run resumes | `fundamental_facts`, `fundamentals_log`, `ticker_cik` |
| `… fundamentals --symbols ATVI,CELG` | specific symbols (comma-separated, dot form) instead of the universe; still deduped to CIKs, but ignores `fundamentals_log` entirely — naming one twin of a share class fetches the CIK and reports that symbol only | same |
| `… fundamentals --retry-failed` | retry CIKs logged `failed`/`empty` (never touches `ok`) | same |
| `… fundamentals --since-filed YYYY-MM-DD` / `--batch-size N` | widen the stored history (costs a full re-ingest) / symbols per write transaction (default 20) | same |
| `… fundamentals --no-sync-map` | skip mirroring `engine/data/ticker_cik.csv` into `ticker_cik` | `fundamental_facts`, `fundamentals_log` |

**Exit criteria:**
1. `python -m seer_engine fundamentals` runs end to end against Neon and leaves every
   ever-member since 2015-01-02 **that resolves to a CIK** with a `fundamentals_log` row for
   that CIK; `failed` is 0 (any non-zero `failed` is a hole in `ticker_cik.csv`, reported by
   symbol). The row count is the number of **distinct CIKs**, which is below the symbol count
   by exactly the share-class pairs in scope — `select count(*) from fundamentals_log` equals
   `select count(distinct cik) from ticker_cik` over the in-scope symbols. A symbol the map
   marks `NONE`, and one it cannot answer for, have no CIK and so no log row by design.
2. Killing the process mid-run and re-running resumes: the **CIKs** already logged are skipped
   and the fact count only grows. `summary.skipped` counts the symbols those CIKs back.
3. `select count(*) from fundamental_facts where (cik, taxonomy, tag, unit, period_start,
   period_end) in (select ... group by ... having count(distinct accn) > 1)` is non-zero —
   restatements are present, not overwritten.
4. `select count(*) from bars` is irrelevant to every assertion above; at least one `ok` symbol
   has zero rows in `bars`.
5. `pytest engine/tests -q` passes with no change to any existing test.
6. The command's second run prints `0 inserted or changed`.

## Handoffs

**H1 — `ticker_cik` is written by this phase; the reconciler may reassign it.** The index gives
phase 2 the table and phase 1 the CSV + loader, and leaves nobody writing the table. This phase
fills the gap (`sync_ticker_cik`, Step 8, default on, `--no-sync-map` to skip) because it is the
only process that holds both the vendored map and a connection. If the reconciler decides phase 1
owns the write, delete `sync_ticker_cik`, `_MAP_SELECT`, `_MAP_INSERT`, the `sync_map` field, the
`--no-sync-map` flag, the two summary lines and the two tests named `*_sync_ticker_cik` /
`test_dry_run_writes_nothing`'s `ticker_cik` assertion; nothing else depends on it.

**H2 — resolved: phase 5 owns the allowlist and this command imports it (C6).** The original
draft defined `INGEST_TAGS` here and warned that phase 5 could read only what it listed. The
index's Decisions table moved the list into `seer_engine/fundamentals/ladder.py` as
`LADDER_TAGS`, which is exactly the "if phase 5 would rather own the constant" branch this
handoff offered. The import direction is command → pure, as required. The operational warning
still stands and now belongs to phase 5: **adding a ladder rung on a new tag is a change to
`ladder.py` plus a full re-ingest** (`fundamentals --symbols <all> --retry-failed` after
`delete from fundamentals_log`), not a phase-5-only change.

**H3 — Phase 5 distinguishes duration from instantaneous facts by `period_start < period_end`**
(C1). There is no boolean column. An `Assets` fact is stored with
`period_start = period_end = <instant>`, and phase 5's `fact_from_row` maps the equality back
to `period_start=None`.

**H4 — Phase 6's panel load joins `ticker_cik` for the symbol.** Facts are keyed by CIK, not by
ticker, precisely so a recycled ticker cannot smear two companies together; `ticker_cik` carries
the dated bridge, and phase 2's contract section spells the exact COPY and fingerprint queries.
No tag filter is needed on the read side: the ingest already stored only `LADDER_TAGS`.

**H5 — Phase 7's runbook rows and exit-code row are written out verbatim under Verification
above.** Phase 4 does not touch `docs/runbooks/data-pipeline.md`.

**H6 — resolved: the count is 795 (C7).** Phase 1 measured it independently
(`len(membership.symbols_since(membership.compute_universe(), date(2015, 1, 2)))`), and the
index, the analysis and every plan now say 795. This command still hardcodes no count: the scope
set is the SQL predicate, so it cannot drift from `universe` whatever the number becomes.

**H7 — the demo purge is deliberately skipped.** `backfill` and `universe refresh` call
`demo.purge_demo_if_needed`; this command does not, because no demo seed writes
`fundamental_facts`, `fundamentals_log` or `ticker_cik`. If a future demo seed does, add the call
at the top of `ingest`, before `select_symbols`.

**H8 — not done, deliberately:** no `nightly` integration (fundamentals refresh is a weekly or
quarterly job, not a nightly one); no `companyfacts.zip` bulk path (the Decisions table picked
the per-CIK API and documents the zip as the fallback for a full-market expansion); no
`delisting_returns.csv` (Gap A, out of scope).

## Rollback

This phase is one commit adding two new files and modifying none, so `git revert <sha>` undoes it
completely: the command disappears from `cli.discover()` with no edit to `cli.py`, and every
other test keeps passing.

Data written before the revert is not removed by it. To undo that too, against the target
database:

```sql
TRUNCATE fundamental_facts;
TRUNCATE fundamentals_log;
TRUNCATE ticker_cik;
```

The three tables themselves belong to phase 2's migration and stay. Nothing this phase writes is
read by any shipped code path until phase 6 lands, so reverting it in isolation changes no
backtest, no paper run and no web output.

> Adopted from `EDGAR_FUNDAMENTALS_PLAN.md` phase 2. Source: `.workflows/plan/edgar-fundamentals/phase-2.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 2: Schema — `ticker_cik`, `fundamental_facts`, `fundamentals_log`

**Plan set:** `EDGAR_FUNDAMENTALS_PLAN.md`
**Analysis:** `20261005-081833-G7K2_code_analyzer.md`
**Satisfies:** R4 — a Postgres schema the engine writes over `DATABASE_URL_UNPOOLED`, consistent
with how `bars` / `universe` / `dividends` / `split_adjustments` are handled
**Depends on:** none
**Difficulty:** EASY
**Package:** `db/migrations`

---

## Goal

After this phase the database holds three new, empty tables: `ticker_cik` (the dated
ticker→CIK bridge phase 1 loads), `fundamental_facts` (raw SEC XBRL facts, keyed so a
restatement inserts rather than overwrites), and `fundamentals_log` (per-CIK resumability,
`backfill_log`'s shape). `python -m seer_engine migrate` applies `005_fundamentals.sql` once and
reports "nothing to apply" on every re-run. No Python source changes; the only non-SQL edit is
the migration's own test block in `engine/tests/test_migrate.py`, without which the tree is red.

---

## Interface Contract

The reconciler reads this section to detect cross-phase conflicts. Be exact and exhaustive.

**Deletes:** none.
**Renames:** none.

**Creates — `db/migrations/005_fundamentals.sql`:**

`ticker_cik` — the dated ticker→CIK bridge (written by phase 1, read by phases 4 and 6):

| column | type | null | constraint |
|---|---|---|---|
| `symbol` | `text` | NOT NULL | part of PK |
| `cik` | `bigint` | NOT NULL | `CHECK (cik > 0 AND cik <= 9999999999)` |
| `start_date` | `date` | NOT NULL | part of PK; **inclusive** |
| `end_date` | `date` | NULL | **exclusive**; NULL = still current |
| `company` | `text` | NOT NULL | the filer's name as vendored |
| `source` | `text` | NOT NULL | `CHECK (source IN ('current','edgar','exact','fuzzy','manual'))` — **phase 1's tier labels** |
| `note` | `text` | NULL | free text, like `ticker_aliases.csv`'s `note` |

- `PRIMARY KEY (symbol, start_date)`
- `CHECK (end_date IS NULL OR end_date > start_date)`
- `CREATE INDEX ticker_cik_cik_idx ON ticker_cik (cik)`

`fundamental_facts` — one row per (filer, concept, period, filing):

| column | type | null | constraint |
|---|---|---|---|
| `cik` | `bigint` | NOT NULL | `CHECK (cik > 0 AND cik <= 9999999999)`; part of PK |
| `taxonomy` | `text` | NOT NULL | `CHECK (taxonomy IN ('us-gaap','dei'))`; part of PK |
| `tag` | `text` | NOT NULL | part of PK |
| `unit` | `text` | NOT NULL | part of PK; **no CHECK** (open vendor domain) |
| `period_start` | `date` | NOT NULL | part of PK; **= `period_end` for an instantaneous fact** |
| `period_end` | `date` | NOT NULL | part of PK |
| `accn` | `text` | NOT NULL | part of PK — **the restatement axis** |
| `val` | `numeric` | NOT NULL | unconstrained precision; may be negative, may exceed 1e12 |
| `fy` | `int` | NULL | filer's fiscal year label |
| `fp` | `text` | NULL | filer's fiscal period label; **no CHECK** |
| `form` | `text` | NOT NULL | `10-K`, `10-Q`, `10-K/A`, `8-K`, `20-F`, …; **no CHECK** |
| `filed` | `date` | NOT NULL | **the only no-look-ahead boundary** |

- `PRIMARY KEY (cik, taxonomy, tag, unit, period_start, period_end, accn)`
- `CHECK (period_start <= period_end)`
- **No secondary index** — the PK's leading columns are the dominant read prefix (see Step 1).
- **No FK** to `ticker_cik` (`ticker_cik.cik` is not unique).

`fundamentals_log` — `backfill_log`'s shape, keyed by `cik`:

| column | type | null | constraint |
|---|---|---|---|
| `cik` | `bigint` | NOT NULL | `PRIMARY KEY`; `CHECK (cik > 0 AND cik <= 9999999999)` |
| `status` | `text` | NOT NULL | `CHECK (status IN ('ok','empty','failed'))` |
| `first_filed` | `date` | NULL | `backfill_log.first_date`'s analogue, on the `filed` axis |
| `last_filed` | `date` | NULL | `backfill_log.last_date`'s analogue |
| `rows` | `int` | NULL | facts written for this CIK |
| `error` | `text` | NULL | |
| `updated_at` | `timestamptz` | NOT NULL | `DEFAULT now()` |

**Deliberately omitted (so no later phase plans around them):**
- `fundamental_facts.frame` — SEC's own canonical-frame annotation (`"CY2015Q3I"`), not an
  as-reported field. Nothing in the ladder, the PIT selection or SUE consumes it, and it costs
  ~10–22 MB of a 0.5 GB Neon cap that already holds 177 MB of `bars`. A later migration can add
  it as a nullable column if a frame-based dedupe is ever wanted.
- `fundamental_facts.symbol` — facts are CIK-keyed; one CIK backs several tickers, so a symbol
  column would duplicate every row. Phase 6 joins through `ticker_cik`.
- `fundamental_facts.updated_at` / `ingested_at` — 8 bytes × ~1 M rows for bookkeeping that
  `fundamentals_log.updated_at` already carries, like `bars` (which has no timestamp).
- any `EXCLUDE USING gist` overlap constraint on `ticker_cik` — it needs the `btree_gist`
  extension, which `002_engine.sql` declined for `universe`'s identically-shaped intervals.
  Overlap is phase 1's loader invariant.

**Signature changes:** none.
**Requires (from earlier phases):** none. Phase 2 has no dependencies and lands first or in
parallel with phases 1 and 3.

**Leaves alone (owned by others):**
- `engine/src/seer_engine/**` — every Python source file. Phase 2 writes no engine code.
- `engine/data/ticker_cik.csv`, `engine/data/SOURCES.md` (Phase 1).
- `docs/runbooks/data-pipeline.md` — **left entirely to Phase 7.** See Handoffs: the runbook has
  no "schema list" section to add a row to.
- `db/migrations/001–004` — untouched; 005 is purely additive.

**Contracts other phases must honour (reconciled — these are now settled, not proposals):**
- *Phase 1* emits `ticker_cik.csv` with the header
  `symbol,cik,start_date,end_date,company_name,source,note` and `source` drawn from
  `{current, edgar, exact, fuzzy, manual}`. **Phase 1's labels won and this CHECK was widened to
  them**, per this phase's own "widen rather than rename" rule. The CSV's `company_name` maps to
  this table's `company`, and the CSV's `cik` sentinel `NONE` has **no** representation here —
  phase 4 skips those rows, because `cik` is `NOT NULL bigint`.
- *Phase 4* must (a) write `period_start = period_end` when SEC omits `start`; (b) write **only
  the tags in phase 5's `fundamentals.ladder.LADDER_TAGS`**, which it imports — not every tag in
  a filing (see the row budget in Step 1); (c) upsert with
  `ON CONFLICT (cik, taxonomy, tag, unit, period_start, period_end, accn) DO UPDATE`; (d) write
  one `fundamentals_log` row **per CIK**, not per symbol, with the columns `cik, status,
  first_filed, last_filed, rows, error, updated_at`; (e) write **no `frame` column** — it is
  deliberately omitted above; (f) write `ticker_cik` with the column names above (`symbol`, not
  `ticker`; `company`, not `company_name`).
- *Phase 5* takes **rows, not a connection**. Its `panel.FACT_COLUMNS` is a `symbol`-keyed
  twelve-column contract, not this table's column list: facts are stored per CIK and phase 6
  turns them into per-symbol rows by joining `ticker_cik` (next bullet). The only column
  semantics phase 5 inherits from here are `period_start = period_end` meaning *instantaneous*
  (phase 5 maps that back to `period_start=None` at its `fact_from_row` boundary) and `filed`
  being the sole no-look-ahead boundary.
- *Phase 6* reads this table through a **join against `ticker_cik`**, because there is no
  `symbol` column here and phase 5's panel is symbol-keyed:

  ```sql
  COPY (SELECT m.symbol, f.taxonomy, f.tag, f.unit,
               CASE WHEN f.period_start = f.period_end THEN ''
                    ELSE to_char(f.period_start, 'YYYY-MM-DD') END AS period_start,
               to_char(f.period_end, 'YYYY-MM-DD') AS period_end,
               f.val, f.accn, f.form,
               coalesce(f.fy::text, '') AS fy, coalesce(f.fp, '') AS fp,
               to_char(f.filed, 'YYYY-MM-DD') AS filed
        FROM fundamental_facts f
        JOIN ticker_cik m
          ON m.cik = f.cik
         AND f.filed >= m.start_date
         AND (m.end_date IS NULL OR f.filed < m.end_date)
        ORDER BY m.symbol, f.taxonomy, f.tag, f.unit, f.period_end, f.period_start, f.filed, f.accn)
  TO STDOUT
  ```

  The join is against `ticker_cik`, **never against `bars`** — invariant 7 forbids making a bar
  row a precondition for a fact. The share-class pairs phase 1 documents (`GOOG`/`GOOGL`,
  `FOX`/`FOXA`, `NWS`/`NWSA`, `UA`/`UAA`, `CMCSA`/`CMCSK`, `BATRA`/`BATRK`) mean this join
  legitimately **fans one fact row out to two symbols**; that is correct, not a bug, and it is
  why the cache fingerprint must be taken over the **same join**, not over
  `fundamental_facts` alone:

  ```sql
  SELECT count(*), max(f.filed)
  FROM fundamental_facts f
  JOIN ticker_cik m ON m.cik = f.cik
   AND f.filed >= m.start_date AND (m.end_date IS NULL OR f.filed < m.end_date)
  ```

  Then the cache key is `(count(*), max(filed))` exactly as `bars` uses
  `(count(*), max(date))`, the pickle is invalidated when **either** table changes, and phase
  6's post-COPY `len(frame) != rows` equality check holds. A fact whose `filed` falls in no
  `ticker_cik` interval is dropped by the join and counted by neither — correct, since no symbol
  can name it.

---

## Files

| File | Action | What changes |
|---|---|---|
| `db/migrations/005_fundamentals.sql` | create | the three tables, one comment block each |
| `engine/tests/test_migrate.py` | modify | pin two 004 assertions to `_upto(…)`; add the 005 block |

---

## Implementation Steps

### Step 1: Write the migration

**File:** `db/migrations/005_fundamentals.sql` (new; `001_init.sql` … `004_news_veto.sql` exist,
and `commands/migrate.py:migration_files` sorts by file name, so `005_` runs last)

**Change:** three `CREATE TABLE IF NOT EXISTS` statements and one `CREATE INDEX IF NOT EXISTS`,
in `002_engine.sql`'s style: a header line saying who writes the tables and that the migration
is additive, a comment block per table spelling out the semantics, and every CHECK written out.

**The type and index decisions, and why** (these are the ones a reviewer will question):

1. **`val numeric`, unconstrained.** `numeric(12,4)` — the house price type — tops out at
   99,999,999.9999; measured `Assets` values exceed 1e12. `double precision` is 8 bytes cheaper
   but an as-reported figure must round-trip byte-faithfully through a restatement diff.
   Unconstrained `numeric` accepts any magnitude and any scale and matches
   `split_adjustments.split_from/split_to`, which are bare `numeric` for the same reason. No
   `CHECK (val > 0)`: `NetIncomeLoss`, `OperatingIncomeLoss` and `StockholdersEquity` all go
   negative.
2. **`cik bigint`, not `int`.** SEC documents the CIK space as ten digits; `int` tops out at
   2,147,483,647 and would silently break if SEC ever crossed it. The `CHECK (cik > 0 AND cik <=
   9999999999)` encodes the ten-digit domain exactly. 4 extra bytes on ~1 M rows is ~4 MB.
   Stored as a number, not the zero-padded `CIK##########` string: companyfacts carries it as an
   integer and the padded form is a URL detail phase 3's client formats.
3. **`period_start date NOT NULL`, with `period_start = period_end` meaning "instantaneous".**
   SEC omits `start` for instantaneous facts (`Assets`, `StockholdersEquity`,
   `dei:EntityCommonStockSharesOutstanding`). A nullable `period_start` cannot sit in a PRIMARY
   KEY, and the period *must* be in the key: one 10-K (one `accn`) reports `Revenues` for both
   FY2015 (`start` 2015-01-01) and Q4 2015 (`start` 2015-10-01) with the same tag, unit and
   `end`. The alternative — `UNIQUE NULLS NOT DISTINCT` (PG15+) plus a surrogate id — is not a
   PRIMARY KEY, fails the phase's exit criterion literally, and sharpens phase 4's `ON CONFLICT`.
   Nothing is lost: no `us-gaap` or `dei` duration fact in companyfacts has a one-day period, so
   `period_start = period_end` is exactly "SEC omitted `start`".
4. **CHECK on `taxonomy`, none on `unit`, `fp` or `form`.** `taxonomy IN ('us-gaap','dei')` is a
   *scope* decision from the index, so it is spelled out; widening it (to `ifrs-full`, say) is a
   new migration. `unit` (`USD`, `USD/shares`, `shares`, and `pure` for ratios), `fp` (`FY`,
   `Q1`…`Q4`, occasionally absent) and `form` are open vendor domains — a CHECK there would
   abort a whole ingest batch on an unseen-but-valid value.
5. **No `CHECK (filed >= period_end)`.** Tempting, since `filed` is the no-look-ahead boundary,
   but `dei` cover-page facts carry an `end` close to the filing date and SEC data quirks do put
   it after. A tripped CHECK aborts the batch; the no-look-ahead rule is enforced on the read
   side (phase 5) where it belongs.
6. **No secondary index on `fundamental_facts`.** The dominant read is "every fact for this CIK
   and this tag with `filed <= t`, latest first". The PK is a btree whose leading columns are
   exactly `(cik, taxonomy, tag)`, so that read is one index range scan over the 10–140 rows a
   filer has for a concept (measured: ATVI 114, TWTR 68, CELG 84, K 138), then a filter and a
   sort on that handful. Phase 6's panel load is a full-table `COPY`, which wants no index at
   all. A `(cik, tag, filed DESC)` index would add 50–90 MB. **Row budget:** 795 filers × ~11
   ladder tags × ~100 facts ≈ 0.9 M rows ≈ 130 MB heap + ~80 MB PK, against a 0.5 GB Neon free
   tier already holding 177 MB of `bars`. That budget only holds if phase 4 writes the ladder's
   tags and nothing else — a single 10-K carries 500–2,000 distinct tags, which would be a
   50–100× table. The comment block says so.

**Code:**

```sql
-- Seer schema v5: SEC EDGAR point-in-time fundamentals (plan edgar-fundamentals, phase 2).
-- Written by engine/ (Python) over DATABASE_URL_UNPOOLED; web/ does not read these.
-- Additive only: three new tables and one index. Nothing existing is altered or dropped.

-- The dated ticker -> CIK bridge, vendored as engine/data/ticker_cik.csv and loaded by
-- `python -m seer_engine fundamentals` (seer_engine.cik). A BARE TICKER NEVER IDENTIFIES A
-- COMPANY: CA, MON, PLL, ALTR, LLL and DTV were all reissued to unrelated filers after their
-- S&P/NDX membership ended, so every resolution is scoped by date.
-- Symbol resolves to cik on date D when start_date <= D AND (end_date IS NULL OR end_date > D),
-- exactly the half-open convention `universe` uses.
-- Non-overlap of a symbol's intervals is enforced by the loader, not by the database, for the
-- same reason `universe` does it there: an EXCLUDE constraint would need the btree_gist
-- extension, and 002_engine.sql declined to add one.
CREATE TABLE IF NOT EXISTS ticker_cik (
  symbol      text NOT NULL,                 -- canonical dot form, same string as bars.symbol ('BRK.B')
  cik         bigint NOT NULL CHECK (cik > 0 AND cik <= 9999999999),
                                             -- SEC's ten-digit filer id, stored unpadded; the
                                             -- 'CIK0000320193' URL form is built by the client
  start_date  date NOT NULL,                 -- first day this ticker meant this filer (inclusive)
  end_date    date,                          -- first day it no longer did (EXCLUSIVE); NULL = still current
  company     text NOT NULL,                 -- the filer's name as vendored, for human audit of recycled tickers
  source      text NOT NULL CHECK (source IN ('current', 'edgar', 'exact', 'fuzzy', 'manual')),
                                             -- phase 1's resolution tier; see engine/data/SOURCES.md
                                             -- ('current' = SEC company_tickers.json, 'edgar' = a
                                             --  submissions probe, 'exact'/'fuzzy' = cik-lookup-data.txt,
                                             --  'manual' = hand-audited)
  note        text,                          -- free text, like ticker_aliases.csv's note column
  PRIMARY KEY (symbol, start_date),
  CHECK (end_date IS NULL OR end_date > start_date)
);
CREATE INDEX IF NOT EXISTS ticker_cik_cik_idx ON ticker_cik (cik);

-- Raw SEC XBRL facts, as reported. One row per (filer, taxonomy, tag, unit, period, filing),
-- straight from companyfacts/CIK##########.json -> facts.<taxonomy>.<tag>.units.<unit>[].
--
-- accn IS PART OF THE PRIMARY KEY. A company restates: the same concept for the same period
-- appears again in a later filing with a different value and a different accession number.
-- Keying without accn would overwrite the original and make as-reported unrecoverable.
--
-- filed IS THE ONLY NO-LOOK-AHEAD BOUNDARY. period_end is not: a figure for the period ending
-- 2015-12-31 is typically filed in February 2016. Every read path must take the latest fact
-- with filed <= t. There is deliberately no CHECK (filed >= period_end): dei cover-page facts
-- and SEC data quirks violate it, and a tripped CHECK would abort a whole ingest batch.
--
-- period_start = period_end MEANS INSTANTANEOUS. SEC omits `start` for point-in-time concepts
-- (Assets, StockholdersEquity, dei:EntityCommonStockSharesOutstanding); the loader writes
-- period_end into both columns. No us-gaap or dei duration fact has a one-day period, so the
-- convention is unambiguous. period_start must stay in the key: one 10-K reports Revenues for
-- both the fiscal year and its fourth quarter under the same accn, tag, unit and period_end.
--
-- val is unconstrained numeric on purpose: Assets exceeds 1e12 (numeric(12,4) tops out at
-- 99,999,999.9999), NetIncomeLoss and StockholdersEquity go negative, and EPS in USD/shares
-- carries decimals. Exactness matters because a restatement is read as a diff.
--
-- Derived metrics are NOT materialised here. The concept ladder, point-in-time selection and
-- SUE live in pure Python (seer_engine.fundamentals), the way indicators derive from raw bars.
--
-- No index beyond the primary key. Its leading columns (cik, taxonomy, tag) are exactly the
-- dominant read prefix, so "every fact for this CIK and this tag with filed <= t" is one range
-- scan over the 10-140 rows a filer has for a concept; the backtest's panel load is a full-table
-- COPY, which wants no index. Row budget: ~795 filers x ~11 ladder tags x ~100 facts ~= 0.9 M
-- rows, ~130 MB heap + ~80 MB primary key, against a 0.5 GB Neon free tier already holding
-- 177 MB of bars. THAT BUDGET ASSUMES ONLY THE LADDER'S TAGS ARE INGESTED: one 10-K carries
-- 500-2,000 distinct tags, which would be a 50-100x table.
CREATE TABLE IF NOT EXISTS fundamental_facts (
  cik           bigint NOT NULL CHECK (cik > 0 AND cik <= 9999999999),
  taxonomy      text NOT NULL CHECK (taxonomy IN ('us-gaap', 'dei')),
  tag           text NOT NULL,                -- XBRL concept ('Assets', 'NetIncomeLoss', 'EntityCommonStockSharesOutstanding')
  unit          text NOT NULL,                -- 'USD', 'USD/shares', 'shares'; open domain, no CHECK
  period_start  date NOT NULL,                -- SEC's `start`; = period_end when SEC omits it (instantaneous)
  period_end    date NOT NULL,                -- SEC's `end`
  accn          text NOT NULL,                -- accession number ('0001193125-15-356351'); the restatement axis
  val           numeric NOT NULL,             -- as reported; negative and > 1e12 both occur
  fy            int,                          -- filer's fiscal year label; absent on some facts
  fp            text,                         -- 'FY', 'Q1'..'Q4'; filer-declared, open domain, no CHECK
  form          text NOT NULL,                -- '10-K', '10-Q', '10-K/A', '8-K', '20-F'; open domain, no CHECK
  filed         date NOT NULL,                -- the availability date; the no-look-ahead boundary
  PRIMARY KEY (cik, taxonomy, tag, unit, period_start, period_end, accn),
  CHECK (period_start <= period_end)
);

-- One row per CIK the fundamentals ingest attempted; lets the ingest resume and records which
-- filers could not be fetched. backfill_log's shape (status CHECK, first/last markers, a row
-- count, an error, updated_at), with first_date/last_date read on the `filed` axis.
--
-- KEYED BY cik, NOT BY symbol, and that is the one deliberate difference from backfill_log.
-- The unit of work is one companyfacts/CIK##########.json fetch, which is one CIK. Keying by
-- symbol would break both ways: one CIK backs several tickers (GOOG/GOOGL, LMCA/LMCK, CMCSK),
-- so the same JSON would be fetched and the same facts written once per ticker and `rows` would
-- double-count; and one ticker maps to several CIKs over time (CA, MON, PLL, ALTR, LLL, DTV),
-- so a single row would have to stand for two unrelated companies' outcomes at once. A symbol's
-- ingest status is read by joining ticker_cik.
CREATE TABLE IF NOT EXISTS fundamentals_log (
  cik          bigint PRIMARY KEY CHECK (cik > 0 AND cik <= 9999999999),
  status       text NOT NULL CHECK (status IN ('ok', 'empty', 'failed')),
  first_filed  date,                          -- earliest `filed` among the facts written
  last_filed   date,                          -- latest `filed` among the facts written
  rows         int,                           -- facts written for this CIK
  error        text,
  updated_at   timestamptz NOT NULL DEFAULT now()
);
```

**Impact:** three new empty tables and one index. No existing table, column, constraint or row
changes, so every existing test, the nightly, the paper run and the web app are unaffected.
`commands/migrate.py` picks the file up with no code change (it globs the directory); the `pg`
fixture in `engine/tests/conftest.py:109` applies every `db/migrations/*.sql`, so the new tables
are present in every DB test with no conftest change either.

---

### Step 2: Pin the two 004 assertions that assume 004 is the last migration

**File:** `engine/tests/test_migrate.py:294-306` and `:309-323`

**Change:** `test_004_on_a_post_003_schema_adds_c_and_leaves_the_roster_rows_alone` and
`test_004_restyles_a_c_row_that_003_kept` both apply the **whole** `MIGRATIONS_DIR` and then
assert the return is exactly `["004_news_veto.sql"]`. With 005 on disk they return
`["004_news_veto.sql", "005_fundamentals.sql"]` and both fail. The fix is not to append 005 to
the expectation — that would break again on 006 — but to point the call at
`_upto(tmp_path, "004_news_veto.sql")`, so each test applies exactly the migrations it names.
`_upto` (`test_migrate.py:52`) already builds such a directory and both tests already take
`tmp_path`. `_upto` names its directory `upto-<last>`, so the two calls in one test get
different directories and do not clash.

`test_repo_has_001_to_004` (`:80`) slices `ALL[:4]` and keeps passing unchanged; every other
assertion is written against `ALL` or a subset (`<=`), so nothing else in the file moves.

**Code — replace lines 294-306 with:**

```python
def test_004_on_a_post_003_schema_adds_c_and_leaves_the_roster_rows_alone(pg_empty, tmp_path):
    _neon_before_003(pg_empty)
    assert apply_migrations(pg_empty, _upto(tmp_path, "003_paper.sql")) == ["003_paper.sql"]
    _started_a(pg_empty)
    before = (_strategies(pg_empty), _paper_rows(pg_empty))
    assert "news_vetoes" not in _tables(pg_empty)
    assert apply_migrations(pg_empty, _upto(tmp_path, "004_news_veto.sql")) == ["004_news_veto.sql"]
    after = _strategies(pg_empty)
    assert [r for r in after if r[0] != "C"] == before[0]  # SPY, A (started), F4, F1: byte for byte
    assert [r[:9] for r in after if r[0] == "C"] == [C_ROW]
    assert _paper_rows(pg_empty) == before[1]
    assert "news_vetoes" in _tables(pg_empty)
    assert apply_migrations(pg_empty, _upto(tmp_path, "004_news_veto.sql")) == []
```

**Code — replace lines 309-323 with:**

```python
def test_004_restyles_a_c_row_that_003_kept(pg_empty, tmp_path):
    _neon_before_003(pg_empty)
    pg_empty.execute(
        "INSERT INTO equity_snapshots (strategy_id, date, cash_usd, equity_usd) VALUES ('C', %s, 1, 1)",
        (date(2026, 10, 2),),
    )
    pg_empty.commit()
    apply_migrations(pg_empty, _upto(tmp_path, "003_paper.sql"))
    assert pg_empty.execute("SELECT name FROM strategies WHERE id = 'C'").fetchone() == ("C · LLM",)
    assert apply_migrations(pg_empty, _upto(tmp_path, "004_news_veto.sql")) == ["004_news_veto.sql"]
    row = pg_empty.execute(
        "SELECT id, name, sub, icon, is_champion, is_benchmark, sort, engine, rules_id FROM strategies WHERE id = 'C'"
    ).fetchone()
    assert row == C_ROW
    assert pg_empty.execute("SELECT count(*) FROM equity_snapshots WHERE strategy_id = 'C'").fetchone()[0] == 1
```

**Impact:** two tests become migration-count-independent. No behaviour change; they still prove
exactly what their names say. Nothing under `engine/src/` is touched.

---

### Step 3: Add `from decimal import Decimal` to the test module's imports

**File:** `engine/tests/test_migrate.py:5-13` (the import block)

**Change:** Step 4's tests assert exact `numeric` round-trips, which psycopg returns as
`Decimal`. The module does not import it yet.

**Code — replace the import block at lines 5-13 with:**

```python
import shutil
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import psycopg
import pytest

from seer_engine import cli
from seer_engine.commands.migrate import MIGRATIONS_DIR, apply_migrations, migration_files
```

**Impact:** none beyond making `Decimal` available. `ruff` selects only `E9` and `F`; the import
is used, so `F401` does not fire (and it is ignored anyway).

---

### Step 4: Add the 005 test block

**File:** `engine/tests/test_migrate.py` — appended after
`test_004_checks_reject_unknown_values` (currently the last function, ending at line 363)

**Change:** a block in the style of the 003 and 004 blocks: an exact column list, an idempotency
test, and tests for each of the exit criteria — the PK includes `accn`, `period_start` is
load-bearing, `val` holds a trillion and a negative, every CHECK bites, and `fundamentals_log`
is keyed by `cik`. Values are real: Apple's CIK 320193, its FY2015 10-K accession
`0001193125-15-356351`, total assets `290,345,000,000` as of 2015-09-26, filed 2015-10-28.

**Code — append verbatim:**

```python
# ---- 005_fundamentals.sql -------------------------------------------------------------------

TICKER_CIK_COLUMNS = [
    ("ticker_cik", "symbol", "text", "NO", None),
    ("ticker_cik", "cik", "bigint", "NO", None),
    ("ticker_cik", "start_date", "date", "NO", None),
    ("ticker_cik", "end_date", "date", "YES", None),
    ("ticker_cik", "company", "text", "NO", None),
    ("ticker_cik", "source", "text", "NO", None),
    ("ticker_cik", "note", "text", "YES", None),
]
FUNDAMENTAL_FACTS_COLUMNS = [
    ("fundamental_facts", "cik", "bigint", "NO", None),
    ("fundamental_facts", "taxonomy", "text", "NO", None),
    ("fundamental_facts", "tag", "text", "NO", None),
    ("fundamental_facts", "unit", "text", "NO", None),
    ("fundamental_facts", "period_start", "date", "NO", None),
    ("fundamental_facts", "period_end", "date", "NO", None),
    ("fundamental_facts", "accn", "text", "NO", None),
    ("fundamental_facts", "val", "numeric", "NO", None),
    ("fundamental_facts", "fy", "integer", "YES", None),
    ("fundamental_facts", "fp", "text", "YES", None),
    ("fundamental_facts", "form", "text", "NO", None),
    ("fundamental_facts", "filed", "date", "NO", None),
]
FUNDAMENTALS_LOG_COLUMNS = [
    ("fundamentals_log", "cik", "bigint", "NO", None),
    ("fundamentals_log", "status", "text", "NO", None),
    ("fundamentals_log", "first_filed", "date", "YES", None),
    ("fundamentals_log", "last_filed", "date", "YES", None),
    ("fundamentals_log", "rows", "integer", "YES", None),
    ("fundamentals_log", "error", "text", "YES", None),
    ("fundamentals_log", "updated_at", "timestamp with time zone", "NO", "now()"),
]

AAPL_CIK = 320193
FY15 = "0001193125-15-356351"          # Apple's FY2015 10-K
FY16 = "0001628280-16-020309"          # ... and its FY2016 10-K, which restates FY2015


def _fact(
    conn,
    *,
    cik=AAPL_CIK,
    taxonomy="us-gaap",
    tag="Assets",
    unit="USD",
    period_start=date(2015, 9, 26),
    period_end=date(2015, 9, 26),
    accn=FY15,
    val=Decimal("290345000000"),
    fy=2015,
    fp="FY",
    form="10-K",
    filed=date(2015, 10, 28),
) -> None:
    conn.execute(
        "INSERT INTO fundamental_facts (cik, taxonomy, tag, unit, period_start, period_end, "
        "accn, val, fy, fp, form, filed) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (cik, taxonomy, tag, unit, period_start, period_end, accn, val, fy, fp, form, filed),
    )


def _bridge(
    conn,
    *,
    symbol="CA",
    cik=AAPL_CIK,
    start_date=date(1996, 1, 2),
    end_date=date(2018, 11, 5),
    company="CA, Inc.",
    source="exact",          # phase 1's tier label; the CHECK admits only its five (C3)
    note=None,
) -> None:
    conn.execute(
        "INSERT INTO ticker_cik (symbol, cik, start_date, end_date, company, source, note) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (symbol, cik, start_date, end_date, company, source, note),
    )


def _log(conn, *, cik=AAPL_CIK, status="ok", first=date(2015, 10, 28), last=date(2026, 8, 1),
         rows=1182, error=None) -> None:
    conn.execute(
        "INSERT INTO fundamentals_log (cik, status, first_filed, last_filed, rows, error) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (cik, status, first, last, rows, error),
    )


def test_005_adds_the_three_tables(pg):
    assert {"ticker_cik", "fundamental_facts", "fundamentals_log"} <= _tables(pg)
    cols = _columns(pg)
    assert [c for c in cols if c[0] == "ticker_cik"] == TICKER_CIK_COLUMNS
    assert [c for c in cols if c[0] == "fundamental_facts"] == FUNDAMENTAL_FACTS_COLUMNS
    assert [c for c in cols if c[0] == "fundamentals_log"] == FUNDAMENTALS_LOG_COLUMNS
    for t in ("ticker_cik", "fundamental_facts", "fundamentals_log"):
        assert pg.execute(f"SELECT count(*) FROM {t}").fetchone()[0] == 0


def test_005_is_applied_last_and_only_once(pg_empty):
    assert "005_fundamentals.sql" in apply_migrations(pg_empty, MIGRATIONS_DIR)
    assert apply_migrations(pg_empty, MIGRATIONS_DIR) == []


def test_005_sql_is_idempotent(pg):
    _fact(pg)
    _bridge(pg)
    _log(pg)
    pg.commit()
    before = (_columns(pg), _constraints(pg), _tables(pg))
    rows = [
        pg.execute(f"SELECT x::text FROM {t} x ORDER BY x::text").fetchall()
        for t in ("ticker_cik", "fundamental_facts", "fundamentals_log")
    ]
    pg.execute((MIGRATIONS_DIR / "005_fundamentals.sql").read_text(encoding="utf-8"))
    pg.commit()
    assert (_columns(pg), _constraints(pg), _tables(pg)) == before
    assert [
        pg.execute(f"SELECT x::text FROM {t} x ORDER BY x::text").fetchall()
        for t in ("ticker_cik", "fundamental_facts", "fundamentals_log")
    ] == rows


def test_005_a_restatement_inserts_rather_than_overwriting(pg):
    _fact(pg)
    # The FY2016 10-K restates the same concept for the same instant under a new accession.
    _fact(pg, accn=FY16, val=Decimal("290479000000"), fy=2016, filed=date(2016, 10, 26))
    pg.commit()
    rows = pg.execute(
        "SELECT accn, val, filed FROM fundamental_facts WHERE tag = 'Assets' ORDER BY filed"
    ).fetchall()
    assert rows == [
        (FY15, Decimal("290345000000"), date(2015, 10, 28)),
        (FY16, Decimal("290479000000"), date(2016, 10, 26)),
    ]
    # ... and the same accession twice is the same fact.
    with pytest.raises(psycopg.errors.UniqueViolation):
        _fact(pg, val=Decimal("1"))
    pg.rollback()


def test_005_the_year_and_its_fourth_quarter_coexist_in_one_filing(pg):
    """One 10-K reports Revenues for the fiscal year and for Q4: same accn, tag, unit,
    period_end, different period_start. period_start must stay in the primary key."""
    _fact(pg, tag="Revenues", period_start=date(2014, 9, 28), period_end=date(2015, 9, 26),
          val=Decimal("233715000000"))
    _fact(pg, tag="Revenues", period_start=date(2015, 6, 28), period_end=date(2015, 9, 26),
          val=Decimal("51501000000"), fp="Q4")
    pg.commit()
    assert pg.execute("SELECT count(*) FROM fundamental_facts WHERE tag = 'Revenues'").fetchone()[0] == 2


def test_005_val_holds_a_trillion_and_a_negative_exactly(pg):
    _fact(pg, tag="Assets", val=Decimal("4123456789012"))
    _fact(pg, tag="NetIncomeLoss", period_start=date(2014, 9, 28), val=Decimal("-1234567.89"))
    _fact(pg, tag="EarningsPerShareDiluted", unit="USD/shares",
          period_start=date(2014, 9, 28), val=Decimal("9.22"))
    pg.commit()
    got = dict(pg.execute("SELECT tag, val FROM fundamental_facts").fetchall())
    assert got == {
        "Assets": Decimal("4123456789012"),
        "NetIncomeLoss": Decimal("-1234567.89"),
        "EarningsPerShareDiluted": Decimal("9.22"),
    }


def test_005_an_instantaneous_fact_is_period_start_equals_period_end(pg):
    _fact(pg, taxonomy="dei", tag="EntityCommonStockSharesOutstanding", unit="shares",
          period_start=date(2015, 10, 9), period_end=date(2015, 10, 9),
          val=Decimal("5575331504"))
    pg.commit()
    start, end = pg.execute(
        "SELECT period_start, period_end FROM fundamental_facts WHERE taxonomy = 'dei'"
    ).fetchone()
    assert start == end == date(2015, 10, 9)


def test_005_ticker_cik_carries_a_validity_interval_per_recycled_ticker(pg):
    _bridge(pg, symbol="CA", cik=356028, start_date=date(1996, 1, 2),
            end_date=date(2018, 11, 5), company="CA, Inc.")
    _bridge(pg, symbol="CA", cik=1364742, start_date=date(2018, 11, 5), end_date=None,
            company="DBX ETF Trust", source="current", note="ticker reissued")
    pg.commit()
    rows = pg.execute(
        "SELECT cik FROM ticker_cik WHERE symbol = 'CA' "
        "AND start_date <= %s AND (end_date IS NULL OR end_date > %s)",
        (date(2015, 6, 1), date(2015, 6, 1)),
    ).fetchall()
    assert rows == [(356028,)]
    with pytest.raises(psycopg.errors.UniqueViolation):  # (symbol, start_date) is the key
        _bridge(pg, symbol="CA", cik=999, start_date=date(1996, 1, 2))
    pg.rollback()


def test_005_fundamentals_log_is_keyed_by_cik(pg):
    _log(pg)
    pg.commit()
    status, updated = pg.execute(
        "SELECT status, updated_at FROM fundamentals_log WHERE cik = %s", (AAPL_CIK,)
    ).fetchone()
    assert status == "ok"
    assert updated is not None
    with pytest.raises(psycopg.errors.UniqueViolation):
        _log(pg, status="failed")
    pg.rollback()
    _log(pg, cik=1018724, status="empty", first=None, last=None, rows=0)  # another filer is fine
    pg.rollback()


def test_005_checks_reject_unknown_values(pg):
    with pytest.raises(psycopg.errors.CheckViolation):
        _fact(pg, taxonomy="ifrs-full")
    pg.rollback()
    with pytest.raises(psycopg.errors.CheckViolation):
        _fact(pg, period_start=date(2016, 1, 1), period_end=date(2015, 9, 26))
    pg.rollback()
    with pytest.raises(psycopg.errors.CheckViolation):
        _fact(pg, cik=0)
    pg.rollback()
    with pytest.raises(psycopg.errors.CheckViolation):
        _log(pg, status="done")
    pg.rollback()
    with pytest.raises(psycopg.errors.CheckViolation):
        _bridge(pg, source="guess")
    pg.rollback()
    with pytest.raises(psycopg.errors.CheckViolation):
        _bridge(pg, start_date=date(2018, 11, 5), end_date=date(2018, 11, 5))
    pg.rollback()


def test_005_open_vendor_domains_are_not_checked(pg):
    """unit, fp and form are SEC's vocabulary, not ours: an unseen-but-valid value must not
    abort an ingest batch."""
    _fact(pg, unit="pure", tag="SomeRatio", fp="H1", form="20-F")
    _fact(pg, tag="NoFiscalLabels", fy=None, fp=None)
    pg.commit()
    assert pg.execute("SELECT count(*) FROM fundamental_facts").fetchone()[0] == 2
```

**Impact:** eleven new DB tests, all under the existing `pg` / `pg_empty` fixtures, all skipped
automatically when `PG_TEST_URL` is unset (`conftest.py:81`). No fixture, no source and no other
test file changes.

---

## Verification

**Build:** there is no compile step; the lint gate is
```
cd /home/miftah/.worktrees/seer/edgar-fundamentals && engine/.venv/bin/ruff check engine
```

**Tests:**
```
cd /home/miftah/.worktrees/seer/edgar-fundamentals
export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres   # or the CI service URL
engine/.venv/bin/python -m pytest engine/tests/test_migrate.py -q
engine/.venv/bin/python -m pytest engine/tests -q
```
`test_migrate.py` must report no failures and no skips; the full run must be green (216 passed
was the last recorded baseline, plus the eleven new tests).

**Manual check** — apply against the real database and prove idempotency. `psql` hangs from this
WSL machine (IPv6), so go through Python, as the runbook does:
```
cd /home/miftah/.worktrees/seer/edgar-fundamentals
engine/.venv/bin/python -m seer_engine --dry-run migrate     # logs "would apply 005_fundamentals.sql", writes nothing
engine/.venv/bin/python -m seer_engine migrate               # logs "apply 005_fundamentals.sql"
engine/.venv/bin/python -m seer_engine migrate               # logs "nothing to apply"
```
Then confirm the shape:
```
engine/.venv/bin/python - <<'PY'
from seer_engine import config, db
config.load_env()
with db.connect() as conn:
    for t in ("ticker_cik", "fundamental_facts", "fundamentals_log"):
        cols = conn.execute(
            "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
            "WHERE table_name = %s ORDER BY ordinal_position", (t,)).fetchall()
        n = conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        print(t, n, cols)
    pk = conn.execute(
        "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
        "WHERE conrelid = 'fundamental_facts'::regclass AND contype = 'p'").fetchone()[0]
    print("PK:", pk)
    print("indexes:", conn.execute(
        "SELECT indexname FROM pg_indexes WHERE tablename IN "
        "('ticker_cik','fundamental_facts','fundamentals_log') ORDER BY 1").fetchall())
    conn.rollback()
PY
```
Expected: three tables, 0 rows each; `PK: PRIMARY KEY (cik, taxonomy, tag, unit, period_start,
period_end, accn)`; indexes exactly `fundamental_facts_pkey`, `fundamentals_log_pkey`,
`ticker_cik_cik_idx`, `ticker_cik_pkey`.

**Exit criteria:**
1. `migrate` applies `005_fundamentals.sql` cleanly, and a second `migrate` says "nothing to
   apply"; re-running the file's SQL by hand changes no column, constraint, table or row
   (`test_005_sql_is_idempotent`).
2. `fundamental_facts`'s **primary key includes `accn`**, and a restatement under a new
   accession inserts a second row rather than overwriting the first
   (`test_005_a_restatement_inserts_rather_than_overwriting`).
3. `fundamentals_log` carries `backfill_log`'s shape — status CHECK, first/last markers, `rows`,
   `error`, `updated_at timestamptz DEFAULT now()` — keyed by `cik`.
4. `ticker_cik` carries a half-open validity interval and a recycled ticker resolves by date
   (`test_005_ticker_cik_carries_a_validity_interval_per_recycled_ticker`).
5. Every statement is additive (`CREATE TABLE IF NOT EXISTS` / `CREATE INDEX IF NOT EXISTS`); no
   `ALTER`, no `DROP`, no `INSERT`.
6. `engine/tests -q` is green and `ruff check engine` is clean.

---

## Handoffs

**`docs/runbooks/data-pipeline.md` — left entirely to Phase 7, deliberately.** The index says
phase 2 owns "its note in the runbook's schema list", but the runbook has no schema list. The
four places that enumerate tables are all operational and all belong with the command
documentation phase 7 is already writing:
- the Architecture prose (`:9-20`), which describes each command's tables in flow order;
- the Commands table's **Writes** column (`:33-41`) — phase 7 adds the `fundamentals` row;
- the Health-checks fingerprint loop (`:261`), whose list should gain `ticker_cik`,
  `fundamental_facts`, `fundamentals_log`;
- the Rollback TRUNCATE (`:274`) and its note "Migration 002 is additive; dropping its three
  tables … reverses it" (`:279`), which should gain the 005 sentence below.

Touching any of these from phase 2 would collide with phase 7 in the same paragraphs for one
line of value. **Phase 7 should add, to the Rollback (data) section:** "Migration 005 is
additive too; `DROP TABLE fundamental_facts, fundamentals_log, ticker_cik` and deleting its
`schema_migrations` row reverses it." **And to the Database size section** (`:217-232`,
currently "about 250 MB for `bars`", stop line 400 MB): `fundamental_facts` is budgeted at
~0.9 M rows ≈ 210 MB including its primary key, so the combined stop line against Neon's 0.5 GB
free tier is `bars` + `fundamental_facts` ≤ 400 MB, and the ingest must stay restricted to the
ladder's tags.

**Phase 4 — the ingest filter is a size constraint, not a preference.** `fundamental_facts` is
budgeted for the ladder's ~11 tags. Ingesting every tag in a filing (500–2,000 distinct) puts
the table 50–100× over and exhausts the free tier. This is noted in the migration's comment
block; phase 4 must enforce it in the loader.

**Phase 4 — the `--dry-run` contract.** Invariant 8 says every write goes through
`db.transaction` and `--dry-run` runs every statement and rolls back. Nothing in this schema
blocks that (no sequences, no `bigserial`, so a rolled-back dry run leaves no gaps).

**Phase 1 — `source`'s vocabulary, settled.** The draft of this plan proposed
`company_tickers`, `cik_lookup`, `fuzzy`, `manual` and said the reconciler should widen the
CHECK rather than rewrite phase 1's CSV if phase 1 chose otherwise. Phase 1 did choose
otherwise, so **the CHECK is widened to phase 1's five tier labels** —
`('current', 'edgar', 'exact', 'fuzzy', 'manual')` — and that is what Step 1 ships and what
every `_bridge(...)` call in the test block uses. The mapping from the old proposal, for
anyone reading an earlier draft: `company_tickers` -> `current`, `cik_lookup` -> `exact`;
`fuzzy` and `manual` are unchanged. A test fixture still passing one of the two retired
labels would hit a `CheckViolation` on insert, so there are none left.

**Not done here, on purpose:** no `frame` column, no `symbol` column on facts, no FK between the
tables, no `EXCLUDE` overlap constraint on `ticker_cik`, no secondary index on
`fundamental_facts`. Each is justified in the Interface Contract and Step 1; each is a one-line
additive migration later if a measurement says otherwise.

---

## Rollback

This phase is one commit on `feature/edgar-fundamentals`.

1. `git revert <sha>` — removes `db/migrations/005_fundamentals.sql` and restores
   `engine/tests/test_migrate.py`. Note that the two 004 assertions revert to the
   `MIGRATIONS_DIR` form, which is correct again once 005 is gone.
2. Against any database the migration already touched, run through Python (not `psql`):
   ```sql
   DROP TABLE IF EXISTS fundamental_facts, fundamentals_log, ticker_cik;
   DELETE FROM schema_migrations WHERE name = '005_fundamentals.sql';
   ```
   The migration is additive and touches nothing that existed before, so this is a complete
   reversal: no column, constraint, index or row outside these three tables was created or
   changed.

Reverting phase 2 alone makes phases 4 and 6 unrunnable (they write and read these tables), but
breaks nothing that shipped: `nightly`, `paper`, `backfill` and the web app never reference them.

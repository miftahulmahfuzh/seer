# Phase 3: Fix B: re-ingest at `--since-filed 2009-01-01`, and measure 2009–2012

**Plan set:** `FUNDAMENTAL_PANEL_COVERAGE_PLAN.md`
**Analysis:** `20261005-133648-2XUM_code_analyzer.md`
**Satisfies:** R2 — Fix B (§3): re-ingest EDGAR at `--since-filed 2009-01-01`, and **measure**
how much 2009–2012 XBRL actually exists before anything depends on it
**Depends on:** Phase 2
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine/commands`

---

## Runtime preamble — run this before every command in this phase

Reconciled set-wide (see the index's `## Decisions`, row C2). The worktree has **no venv of its
own**, and `/home/miftah/seer/engine/.venv` is an *editable* install whose
`__editable__.seer_engine-0.1.0.pth` contains the literal `/home/miftah/seer/engine/src` — the
**main checkout**. `engine/pyproject.toml`'s `[tool.pytest.ini_options]` sets only
`testpaths = ["tests"]` and **no `pythonpath`**, so pytest resolves `seer_engine` through that
same editable install. Without the block below, every command in this phase — `pytest`
included — silently exercises `main`'s code and reads `main`'s `engine/data/`.

```bash
export SEER_WT=/home/miftah/.worktrees/seer/fundamental-panel-coverage
export SEER_PY=/home/miftah/seer/engine/.venv/bin/python
export PYTHONPATH=$SEER_WT/engine/src          # searched before anything `site` adds
cd "$SEER_WT"
"$SEER_PY" -c 'import seer_engine, pathlib; print(pathlib.Path(seer_engine.__file__).resolve())'
# must print $SEER_WT/engine/src/seer_engine/__init__.py
```

**Reuse main's venv; do not build one in the worktree.** `PYTHONPATH` wins over the `.pth`
(measured), carries `cik.DATA_DIR` (`Path(cik.__file__).parents[2] / "data"`) to the worktree
with it, and applies uniformly to `pytest` and to `python -m seer_engine`. A second venv would
mean a second dependency resolution, and invariant 1 pins this set to the `2dad9ff` baseline of
2216 passed / 332 skipped measured in *this* interpreter.
`engine/scripts/build_ticker_cik.py:40` does its own
`sys.path.insert(0, Path(__file__).resolve().parents[1] / "src")`, so the generator
self-resolves when invoked by its worktree path — that rescues the generator and nothing else.

**This phase touches a database, so it also needs (index `## Decisions`, row C3):**

```bash
export SEER_ENV_FILE=/home/miftah/seer/.env.local-train     # ABSOLUTE, always
export SEER_TRAIN_URL=postgresql://postgres:pg@localhost:55432/postgres
```

`config.env_file()` returns `Path(override)` verbatim and resolves a relative path against the
**cwd**. `.env*` is gitignored, so the worktree holds no `.env.local-train`: a relative
`SEER_ENV_FILE=.env.local-train` loads nothing, `DATABASE_URL_UNPOOLED` falls through to the
ambient environment, and the ambient one points at **Neon**. Invariant 8 forbids any Neon
write. Prove the resolved DSN before anything writes:

```bash
"$SEER_PY" -c "import os, seer_engine.config as c; c.load_env(); u = os.environ['DATABASE_URL_UNPOOLED']; assert 'localhost:55432' in u, f'REFUSING: {u}'; print('DSN ok:', u)"
```

---

## Goal

After this phase, `commands/fundamentals.py` carries one floor — 2009-01-01 — at both ends
instead of two different ones (2015-01-02 for membership, 2013-01-01 for filings), and the
local train database holds the facts that floor admits: every XBRL fact filed from 2009 on,
for all ~913 ever-members phase 2's re-vendored `ticker_cik.csv` can resolve, rather than only
facts filed from 2013 on for the 795 members the old clamp admitted. And the phase produces the
measurement §3 asks for: facts by `filed` year for 2009–2026, with 2009–2012 reported as they
actually land, against the 2013–2026 baseline already in the analysis.

The deliverable is **the measurement as much as the rows**. If 2009 and 2010 come in far below
~90k facts, that is the real floor and this phase says so plainly; phase 5 writes it down.

---

## Interface Contract

The reconciler reads this section to detect cross-phase conflicts.

**Deletes:** nothing.

**Renames:** nothing.

**Creates:** nothing in `engine/src`. One throwaway database table in the **local train**
database only, as a rollback aid: `fundamentals_log_pre_fixb`, a **read-only snapshot** taken
with `CREATE TABLE AS SELECT * FROM fundamentals_log` (dropped or kept at the operator's
discretion; not in any migration and not in git). **Nothing in this phase truncates, deletes
from, or drops `fundamentals_log` itself** — see the reconciled blocker section below.

**Signature changes:** none. `Options`, `add_arguments`, `options_from_args`, `ingest`,
`select_facts`, `plan_jobs`, `membership_windows`, `format_summary` all keep their exact
signatures. **Only two module constants change value:**

- `seer_engine.commands.fundamentals.DEFAULT_SINCE`: `date(2015, 1, 2)` -> `date(2009, 1, 1)`
  (`engine/src/seer_engine/commands/fundamentals.py:63`)
- `seer_engine.commands.fundamentals.DEFAULT_SINCE_FILED`: `date(2013, 1, 1)` ->
  `date(2009, 1, 1)` (`engine/src/seer_engine/commands/fundamentals.py:67`)

**Requires (from earlier phases):**

- Phase 2 has landed `engine/data/ticker_cik.csv` regenerated at `cik.SINCE = date(2009, 1, 1)`:
  913 symbols, >= 916 rows, 525 existing `start_date`s moved earlier, 118 symbols new, 0 lost,
  zero `source=fuzzy` rows, `NDOI` still the only `NONE`. **Without it this phase buys almost
  nothing** — the dated join `m.cik = f.cik AND f.filed >= m.start_date AND (m.end_date IS NULL
  OR f.filed < m.end_date)` would still discard every fact filed before each symbol's 2015-01-02
  clamp, and the pre-2015 filers of the 118 new symbols would never be fetched at all.
- Phase 2 has lowered `seer_engine.cik.SINCE` to `date(2009, 1, 1)`. This phase reads it only
  indirectly (through the CSV phase 2 generated); it does not import or assert on it.

**Leaves alone (owned by others):**

- `engine/src/seer_engine/cik.py`, `engine/scripts/build_ticker_cik.py`,
  `engine/data/ticker_cik.csv`, `engine/data/SOURCES.md`, `engine/tests/test_cik.py` — **phase 2**
- `engine/src/seer_engine/fundamentals/**` (including the new `coverage.py`),
  `engine/src/seer_engine/lab/**`, `engine/tests/test_fundamentals_coverage.py` — **phase 1**
- `engine/src/seer_engine/research.py`, `engine/src/seer_engine/commands/research_store.py`,
  `engine/.research/`, `engine/tests/test_research_store.py` — **phases 4 and 5**
- `docs/**`, `engine/package_readme.md`,
  `engine/src/seer_engine/lab/methods/m0005_fundamental_factors.py` — **phase 5**
- `db/migrations/**` — `005_fundamentals.sql` is applied and verified. **No schema change.**
- `engine/src/seer_engine/backtest/io.py` — read in this plan to pin down the join and the
  `filed < period_end` tolerance (`b76b38d`); **not modified**.
- **Neon.** `fundamental_facts` and `fundamentals_log` are deliberately truncated in production
  and stay that way. Every database write in this phase goes to the database
  `.env.local-train` names.

---

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/commands/fundamentals.py` | modify | module docstring (`:3-4`, `:26-31`), `DEFAULT_SINCE` (`:63`), the comment + `DEFAULT_SINCE_FILED` (`:64-67`), the two `--since*` help strings (`:210-224`) |
| `engine/tests/test_fundamentals_command.py` | modify | `SINCE` (`:24`), `FILED_OLD` (`:32`), the defaults assertion (`:177-178`), the filed-cutoff fixture (`:272-281`) |

Two files. The third artifact of this phase is **the ingest run itself**, which writes no file
in git — it writes rows to the local train database and a measurement recorded in the phase
summary.

---

## Measured starting state (this host, 2026-10-05, against `2dad9ff`)

Everything below was measured, not assumed. The plan's steps depend on these numbers.

| Thing | Value |
|---|---|
| `fundamental_facts` rows | 1,228,822 over **773** distinct CIKs |
| `fundamental_facts` size | 385 MB (`pg_total_relation_size` = 403,226,624) |
| `fundamental_facts` `min(filed)` / `max(filed)` | 2013-01-02 / 2026-10-02 |
| `fundamental_facts` `min(period_end)` | 2008-06-30 |
| `fundamental_facts where filed < period_end` | **28** |
| `ticker_cik` rows | 797 |
| `fundamentals_log` | **773 `ok`, 3 `empty`, 0 `failed`** |
| `universe` rows | **0** |
| `bars` rows | **0** |
| `runs where is_demo` | false (so `universe refresh`'s demo purge is a no-op) |
| Joined rows (`fundamental_facts` x `ticker_cik`, the panel's own join) | **831,725** over **780** symbols |
| Joined rows by `filed` year | 2015: 70,234 · 2016: 71,466 · 2017: 71,384 · 2018: 73,054 · 2019: 77,888 · 2020: 78,917 · 2021: 74,199 · 2022: 67,776 · 2023: 67,059 · 2024: 66,863 · 2025: 66,858 · 2026: 46,027 — **2013 and 2014 are absent entirely** |
| Joined rows with `filed < period_end` | **18** (the 28 above, less the ones the join drops) |
| `membership.compute_universe(DATA_DIR)` | 1544 intervals, 1265 distinct symbols |
| `symbols_since(2009-01-01)` / `symbols_since(2015-01-02)` | **913** / 795 |
| `engine/.cache/` | only `bars-2026-10-02-1817429.pkl`; **no `fundamentals-*.pkl`** |

The joined-by-year row is the whole case for Fix B in one line: 181,491 facts filed in 2013–2014
sit in the table and **reach the panel as zero rows**, because every `ticker_cik` interval starts
on or after 2015-01-02 and the join keys on `filed`.

### Two environment facts the run depends on (measured)

1. **The worktree has no `engine/.venv` and no `.env.local-train`.** Both live in the main
   checkout, `/home/miftah/seer`. The venv is an *editable* install whose `.pth` adds
   `/home/miftah/seer/engine/src` to `sys.path`, so running `engine/.venv/bin/python -m
   seer_engine` would execute **main's** code and read **main's** `engine/data/ticker_cik.csv`
   — the old 795-symbol file, not phase 2's. `PYTHONPATH` is searched before anything `site`
   adds, so exporting it fixes this; verified:

   ```
   module:            /home/miftah/.worktrees/seer/fundamental-panel-coverage/engine/src/seer_engine/__init__.py
   cik.DATA_DIR:      /home/miftah/.worktrees/seer/fundamental-panel-coverage/engine/data
   config.REPO_ROOT:  /home/miftah/.worktrees/seer/fundamental-panel-coverage
   ```

2. **`SEER_ENV_FILE` must be an absolute path.** `config.env_file()` returns `Path(override)`
   verbatim, resolved against the *current working directory* — and `.env.local-train` does not
   exist in the worktree. A relative `SEER_ENV_FILE=.env.local-train` run from the worktree
   silently loads nothing, `DATABASE_URL_UNPOOLED` falls through to whatever is in the ambient
   environment, and the run could land **on Neon**. Use
   `SEER_ENV_FILE=/home/miftah/seer/.env.local-train` and verify it before the run (Step 5).

---

## The blocker nobody has noticed yet, and it is bigger than the empty `universe`

**`--retry-failed` does not re-fetch the 773 CIKs already logged `ok`.** `plan_jobs`
(`fundamentals.py:479-487`):

```python
    logged = {} if opts.symbols else _logged_statuses(conn, sorted(by_cik))
    done = {STATUS_OK} if opts.retry_failed else {STATUS_OK, STATUS_EMPTY, STATUS_FAILED}
```

With `--retry-failed`, `done == {"ok"}` — so every CIK whose log row says `ok` is skipped. The
773 filers already in `fundamentals_log` as `ok` were fetched under `--since-filed 2013-01-01`
and their 2009–2012 facts were discarded by `select_facts` before any write. Running the command
from the plan index verbatim against today's log would fetch only the ~117 **new** CIKs plus the
3 `empty` ones, and would leave the 2009–2012 history of the other 773 — the bulk of the data
Fix B exists to recover — unfetched. The summary would even look healthy.

**The fix — RECONCILED, and it is `--symbols`, not `TRUNCATE`.** The original plan for this
phase was to back up and `TRUNCATE fundamentals_log`. The reconciler compared that against the
route the same function already offers, three lines above the one quoted:

```python
    # `--symbols` ignores the log outright -- that is what its help text promises and what
    # makes it the tool for re-fetching one filer after a fix. Everything else resumes.
    logged = {} if opts.symbols else _logged_statuses(conn, sorted(by_cik))
```

With `--symbols` naming the whole member set, `logged` is `{}` and **every** resolved CIK is
fetched — exactly the job list an emptied log would produce, with nothing deleted. The two
routes are equivalent in what they fetch and differ only in blast radius:

| | `TRUNCATE fundamentals_log` | `--symbols <the whole member set>` |
|---|---|---|
| CIKs fetched | ~890 (log empty) | ~890 (log ignored) |
| Rows destroyed if the DSN guard fails and this lands on **Neon** | the whole production ledger | **none** — rows are upserted, never deleted |
| Needs a backup table to be recoverable | yes | no (the snapshot is optional insurance) |
| Resume after a crash | re-run; log now partly repopulated | re-run; see below |

**The rung is invariant 8** — *"No network write and no Neon write"* — and the thing invariant 8
is protecting is a database that must not lose rows. A route that cannot delete a row in any
database, even when every guard above it fails, is the one that honours it. The surrounding
convention agrees: `docs/runbooks/data-pipeline.md:174-175` already prescribes
`fundamentals --symbols <the changed tickers>` as *the* way to re-ingest after a map fix.
**`--symbols` is taken; the `TRUNCATE` is gone from this plan.**

The one thing `--symbols` costs is the cheap resume, because an interrupted run leaves the log
holding a mix of this run's rows and the pre-run ones. Step 8 gives the two correct resumes:
re-running the identical command (always right, up to another 45 minutes of free SEC calls,
zero changed fact rows for the CIKs already done) or the narrowed form keyed on
`fundamentals_log.first_filed`, which is the honest discriminator — a CIK re-fetched at the 2009
floor has `first_filed < 2013-01-01` unless it genuinely has no older filing.

This is also what makes the ~30-minute budget in the phase brief arithmetically true: ~890 CIKs
at 1–3 s is 15–45 minutes. ~120 CIKs would be four minutes, and four minutes would be the sign
that the run did the wrong thing.

---

## Implementation Steps

Steps 1–4 are the code change and must land (and the suite must pass) before the run. Steps 5–9
are the run and the measurement.

### Step 1: Both floors move to 2009-01-01

**File:** `engine/src/seer_engine/commands/fundamentals.py:61-69`
**Change:** replace the constants block and the comment that justified 2013 with one that
justifies 2009 and explains why the two floors are not independent.

The old comment is obsolete on both of its claims. *"the backtest window opens at
DEFAULT_SINCE"* — the backtest window is `dev.MEMBERSHIP_START` (1996-01-02) through
`research.DEV_END`, not `DEFAULT_SINCE`. *"Dropping 2009-2012 roughly halves the row count on a
0.5 GB database"* — train/eval is local now; Neon's `fundamental_facts` is truncated and the
0.5 GB tier no longer bounds this choice.

**Code:** replace lines 61–69 (from `HELP = ...` through `ERROR_MAX_LEN = 500`) with:

```python
HELP = "Load SEC EDGAR XBRL company facts for every index ever-member; resumable."

DEFAULT_SINCE = date(2009, 1, 1)
# 2009-01-01 at both ends, and it is the earliest floor worth having: XBRL did not exist
# before roughly FY2009, so there is nothing earlier to fetch at any price or from any vendor.
#
# THE TWO FLOORS MOVE TOGETHER, ALWAYS. `--since` picks WHICH members are ingested
# (_WINDOWS_SQL over the `universe` table) and bounds the window resolve_window_ciks resolves
# CIKs over; `--since-filed` picks WHICH of a fetched filer's facts are kept. A member admitted
# from 2009 whose facts are dropped below 2013 buys nothing, and a fact kept from 2009 for a
# member only admitted from 2015 is never fetched at all, because the member is out of scope.
# `options_from_args` enforces since_filed <= since, which 2009-01-01 <= 2009-01-01 satisfies.
#
# Lowering the filed floor costs no extra request: `companyfacts` returns a filer's whole
# history in one response whatever the floor, so the earlier 2013 cutoff was discarding rows
# that had already been downloaded. What it buys is the panel. The panel's load joins
# `fundamental_facts` to `ticker_cik` ON `filed >= start_date AND filed < end_date`
# (backtest/io.py:93-98), so a fact filed before the map's start_date for that symbol never
# reaches the panel at all -- which is why the filed floor and the vendored map's floor have
# to agree, and why 181,491 facts filed in 2013-2014 were stored and invisible.
#
# Coverage in 2009-2010 is partial and size-biased: XBRL phased in by filer size, large
# accelerated filers from roughly FY2009 and all filers by FY2011. Do not assume those years
# are as thick as 2013 onwards; the measured per-year counts are in
# docs/plans/2026-10-05-fundamental-panel-coverage.md section 3.
DEFAULT_SINCE_FILED = date(2009, 1, 1)
DEFAULT_BATCH_SIZE = 20
ERROR_MAX_LEN = 500
```

**Impact:** `--since` and `--since-filed` both default to 2009-01-01. Every caller that passes
neither now ingests the 913-symbol member set and keeps facts from 2009. Nothing else in the
module reads either constant except `add_arguments` (Step 3) and the `Options` defaults
(`:108-109`), which pick the new values up automatically.

### Step 2: The module docstring stops saying 2015-01-02 and stops doing Neon's arithmetic

**File:** `engine/src/seer_engine/commands/fundamentals.py:1-39`
**Change:** two edits inside the docstring — the scope sentence and the Storage paragraph. The
Storage paragraph currently reasons from "Neon's free tier is 0.5 GB and `bars` already takes
177 MB", which is no longer the constraint on this command at all: these facts are not on Neon.

**Code:** replace the whole module docstring (lines 1–39) with:

```python
"""fundamentals -- resumable ingest of SEC EDGAR XBRL company facts (Gap B).

One ``data.sec.gov`` ``companyfacts`` call per CIK, resolved from the vendored dated
ticker->CIK map, for every S&P 500 / Nasdaq-100 ever-member since 2009-01-01. Symbols are
processed in batches and **each batch is written in its own transaction together with its
``fundamentals_log`` rows**, so a crash loses at most one batch and a re-run resumes where
it stopped -- the shape ``backfill`` uses.

The unit of work is the CIK, not the symbol. One CIK backs several tickers (GOOG/GOOGL,
CMCSA/CMCSK, BATRA/BATRK), so symbol-keyed work would fetch the same JSON twice and
double-count its rows; and one ticker maps to several CIKs over time, so a symbol-keyed log
row would carry two companies' outcomes. ``plan_jobs`` resolves every in-scope symbol, groups
by CIK and skips the CIKs already logged; ``CikResult.per_symbol`` fans the outcome back out
so the summary and the exit code stay per symbol.

Resuming is keyed on the log, so **widening a floor is not something a flag can express**:
``--retry-failed`` re-attempts ``failed`` and ``empty`` filers only, and a filer logged ``ok``
under a narrower ``--since-filed`` is skipped with its older facts still missing. The supported
way to re-fetch everything is ``--symbols`` with the whole member set: ``plan_jobs`` ignores the
log outright when it is given, so every resolved CIK is fetched without a row being deleted
anywhere. The facts upsert is idempotent, so a filer whose facts are unchanged still writes zero
rows, and re-running is always safe. Do NOT empty ``fundamentals_log`` to achieve this: it
destroys the resume ledger for a result ``--symbols`` reaches without destroying anything.

No dependency on ``bars``. 133 of the ever-members have no price history at all and they are
precisely the names this pipeline exists to cover, so nothing here reads ``bars``, joins
against it, or treats a missing bar as an error.

Point in time: every fact is stored with its ``filed`` date and its accession number, and
``accn`` is part of the row identity, so a restatement inserts a second row rather than
overwriting the figure it restates. ``period_end`` is never an availability date. Nothing
here derives anything: the concept ladder and the ``filed <= t`` selection are pure code in
``seer_engine.fundamentals``.

Storage. ``companyfacts`` for a large filer holds tens of thousands of facts across hundreds
of tags, so the ingest keeps only the taxonomy/tag pairs in ``ladder.LADDER_TAGS`` (phase 5
owns the list) and only facts with ``filed >= --since-filed``. Narrowing either is a deliberate
decision that costs a re-ingest, which is why both are visible constants and the summary prints
``pg_total_relation_size('fundamental_facts')``.

**These facts do not live on Neon.** Every write goes to the database ``.env.local-train``
names, because the only database read in the whole train/eval pipeline is ``fundamental_facts``
x ``ticker_cik`` and pointing that one read at a local Postgres takes Neon out of train/eval
entirely. Neon's ``fundamental_facts`` and ``fundamentals_log`` are deliberately truncated, so
the 0.5 GB free tier no longer bounds the filed floor; the only remaining bound on
``--since-filed`` is when XBRL began, and that is 2009.

Fair access is the SEC client's job, not this module's: ``sec.Client`` paces itself to
<= 10 req/s from the end of the previous call and sends the contact ``User-Agent``. This
command therefore adds no inter-batch sleep.

Idempotent: every write is an upsert guarded by ``IS DISTINCT FROM``; re-running with the
same arguments changes no ``fundamental_facts`` rows.
"""
```

**Impact:** documentation only. No behaviour change. The new fourth paragraph is the one that
would have saved this phase an afternoon.

### Step 3: The two `--since*` help strings say what each floor actually selects

**File:** `engine/src/seer_engine/commands/fundamentals.py:209-224`
**Change:** replace the first two `p.add_argument` calls in `add_arguments`. The rest of the
function (`--symbols`, `--retry-failed`, `--batch-size`, `--no-sync-map`) is unchanged; it is
reproduced here so the replacement is a whole function and nothing has to be spliced.

**Code:**

```python
def add_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--since",
        type=_iso_date,
        default=DEFAULT_SINCE,
        help=(
            "ingest every member on or after this date; this selects the MEMBER SET, not the "
            f"facts (default {DEFAULT_SINCE.isoformat()}; must be >= --since-filed)"
        ),
    )
    p.add_argument(
        "--since-filed",
        type=_iso_date,
        default=DEFAULT_SINCE_FILED,
        help=(
            "drop facts filed before this date; this selects the FACTS of a fetched filer "
            f"(default {DEFAULT_SINCE_FILED.isoformat()}, which is where XBRL begins -- there "
            "is nothing earlier to widen to; narrowing it costs a re-ingest to undo)"
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
        help=(
            "also re-attempt symbols logged as failed or empty; a filer logged ok is still "
            "skipped, so widening --since-filed needs --symbols, which ignores the log"
        ),
    )
    p.add_argument(
        "--batch-size",
        type=_positive_int,
        default=DEFAULT_BATCH_SIZE,
        help=f"CIKs per write transaction (default {DEFAULT_BATCH_SIZE})",
    )
    p.add_argument(
        "--no-sync-map",
        action="store_true",
        help="do not mirror engine/data/ticker_cik.csv into the ticker_cik table",
    )
```

**Impact:** `--help` output only. No parsing behaviour changes.

### Step 4: The tests stop hardcoding the old floors

**File:** `engine/tests/test_fundamentals_command.py:24`, `:32`, `:175-183`, `:272-281`

Four edits. Two are the constants, one is the defaults assertion, one is the fixture that only
tested the filed cutoff *because* 2010 was below it — with the floor at 2009-01-01, a fact filed
2010-05-07 is now **kept**, and the test would fail with a correct implementation. The fixture
moves to 2008, which is below the new floor and below XBRL itself.

**Change 4a** — `engine/tests/test_fundamentals_command.py:24`:

```python
SINCE = date(2009, 1, 1)
```

(Checked against every use. `SINCE` reaches `opts()` as `Options.since` and
`resolve_window_ciks` as `first_day`. Every `seed_universe` row in the file starts
2014-01-02 or later and ends 2016-01-04 or later or `NULL`, so `_WINDOWS_SQL`'s
`end_date IS NULL OR end_date > since` admits the same rows at either floor; every `Mapping`
default `start_date` is `date(1990, 1, 1)`, so every resolution still matches. The only
observable difference is that `AAA`'s window `first_day` becomes 2014-01-02 instead of
2015-01-02, which no assertion reads.)

**Change 4b** — `engine/tests/test_fundamentals_command.py:32`:

```python
FILED_OLD = date(2008, 5, 7)
```

**Change 4c** — replace `test_arguments_defaults_and_symbol_normalisation`
(`engine/tests/test_fundamentals_command.py:175-183`) in full:

```python
def test_arguments_defaults_and_symbol_normalisation():
    args = parse([])
    # One floor, at both ends: the member set and the filed cutoff have to agree or the
    # dated ticker_cik join silently drops whatever falls between them.
    assert args.since == date(2009, 1, 1)
    assert args.since_filed == date(2009, 1, 1)
    assert args.batch_size == 20 and args.symbols is None and args.no_sync_map is False
    args = parse(["--symbols", "brk-b, atvi,ATVI", "--batch-size", "5", "--no-sync-map"])
    assert args.symbols == ["BRK.B", "ATVI"]
    assert args.batch_size == 5 and args.no_sync_map is True
```

**Change 4d** — replace `test_select_facts_keeps_only_allowlisted_tags_filed_in_range`
(`engine/tests/test_fundamentals_command.py:272-281`) in full:

```python
def test_select_facts_keeps_only_allowlisted_tags_filed_in_range():
    facts = [
        fact("Assets"),
        fact("NetIncomeLoss", start=date(2015, 1, 1)),
        fact("AccruedLiabilitiesCurrent"),            # not in LADDER_TAGS
        # Before the cutoff. FILED_OLD is 2008, not 2010: the floor is 2009-01-01 now, which
        # is where XBRL begins, so nothing filed on or after it is ever dropped for being old.
        fact("Assets", end=date(2008, 3, 31), filed=FILED_OLD, fy=2008, fp="Q1"),
    ]
    kept = fcmd.select_facts(facts, fcmd.DEFAULT_SINCE_FILED)
    assert [f.tag for f in kept] == ["Assets", "NetIncomeLoss"]
```

**Impact:** four tests in this file touch the floors;
`test_options_reject_a_filed_cutoff_after_the_window_opens` (`:194-201`) needs no change —
`--since-filed 2016-01-01` is still after the new `--since` default of 2009-01-01, so the
`FundamentalsError` still fires, and `--since 2030-01-02` is still in the future.
`test_shares_outstanding_comes_from_the_dei_taxonomy` (`:283-298`) passes
`fcmd.DEFAULT_SINCE_FILED` to a fact filed 2016-02-26 and is unaffected.

**Checkpoint:** the suite must be green here, before any database is touched.

```bash
cd "$SEER_WT"
"$SEER_PY" -m pytest engine/tests/test_fundamentals_command.py -q
"$SEER_PY" -m pytest engine/tests -q
```

### Step 5: Pre-flight — prove which code, which data and which database

**File:** none. This is a command, and it is not optional: every way this run can go wrong
goes wrong here, silently.

The five exports are the **Runtime preamble**'s, unchanged — re-export them if this is a fresh
shell.

```bash
cd "$SEER_WT"
"$SEER_PY" - <<'PY'
import os
import seer_engine, seer_engine.cik as cik, seer_engine.config as config
from seer_engine.commands import fundamentals as f
print("module          :", seer_engine.__file__)
print("cik.DATA_DIR    :", cik.DATA_DIR)
print("config.REPO_ROOT:", config.REPO_ROOT)
print("env file        :", config.env_file(), "exists:", config.env_file().is_file())
print("loaded          :", config.load_env())
print("DATABASE_URL_UNPOOLED:", os.environ.get("DATABASE_URL_UNPOOLED"))
print("cik.SINCE       :", cik.SINCE)
print("DEFAULT_SINCE   :", f.DEFAULT_SINCE, " DEFAULT_SINCE_FILED:", f.DEFAULT_SINCE_FILED)
idx = cik.load_index()
print("ticker_cik.csv  :", len(idx), "symbols,",
      sum(len(v) for v in idx.values()), "rows")
PY
```

**Every one of these must hold before continuing:**

- `module` and `cik.DATA_DIR` point **inside the worktree**, not `/home/miftah/seer`.
- `env file` is `/home/miftah/seer/.env.local-train` and `exists: True`.
- `DATABASE_URL_UNPOOLED` is `postgresql://postgres:pg@localhost:55432/postgres`. **If it names
  any host that is not `localhost:55432`, stop.** That would be Neon, and Neon's
  `fundamental_facts` must stay truncated.
- `cik.SINCE` is `2009-01-01` and `ticker_cik.csv` reports **913 symbols** — that is phase 2
  landed. 795 means phase 2 has not landed and this phase must wait.
- `DEFAULT_SINCE` and `DEFAULT_SINCE_FILED` are both `2009-01-01` — that is Step 1 landed.

**Impact:** none; read-only. It is the gate that keeps the run off Neon and off main's data.

### Step 6: Populate `universe`, snapshot the ledger, and build the member list

**File:** none. Three operations against the local train database, in this order. **None of
them deletes a row.**

`membership_windows` reads the `universe` table and the local train database holds **0 rows**,
so `select_symbols` would raise *"the universe table holds no member on or after 2009-01-01;
run `python -m seer_engine universe refresh` first"*. `universe refresh` rebuilds the table from
the vendored CSVs via `membership.compute_universe` -> `membership.replace_universe`; it is
idempotent and **needs no network**. (`universe check` *does* hit Wikipedia — do not run it.)
Its `demo.purge_demo_if_needed` call is a measured no-op here: `SELECT EXISTS (SELECT 1 FROM
runs WHERE is_demo)` is false and `fundamental_facts` is not in `DEMO_TABLES` in any case.

```bash
# 6a. universe: 0 rows -> 1544 intervals, 1265 distinct symbols, 913 of them since 2009-01-01.
"$SEER_PY" -m seer_engine universe refresh
```

`universe refresh` is not optional even though `--symbols` bypasses `select_symbols`'s universe
check: `plan_jobs` still reads `windows` and falls back to `(opts.since, opts.today)` for any
symbol the table does not describe, which would resolve a recycled ticker across the whole
2009→today span instead of its real membership window. Populate it, then build the list from it.

Expected output ends with `universe: replaced table with 1544 rows`, and the summary line
reports `1544 intervals, 1265 distinct symbols, N since 2015-01-01` (that `SINCE` is
`commands/universe.py:24`, a display constant of a different command — **not** one this phase
owns or touches).

```bash
# 6b. Snapshot the resume ledger. A COPY, nothing else: no TRUNCATE, no DELETE, no DROP of
#     fundamentals_log itself. It is insurance for the rollback, not a prerequisite of the run.
"$SEER_PY" - <<'PY'
import os, psycopg
url = os.environ["SEER_TRAIN_URL"]
assert "localhost:55432" in url, f"refusing to run against {url}"
with psycopg.connect(url) as conn:
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS fundamentals_log_pre_fixb")
        cur.execute("CREATE TABLE fundamentals_log_pre_fixb AS "
                    "SELECT * FROM fundamentals_log")
        cur.execute("SELECT count(*) FROM fundamentals_log_pre_fixb")
        print("snapshot:", cur.fetchone()[0], "log rows copied into fundamentals_log_pre_fixb")
        cur.execute("SELECT count(*) FROM fundamentals_log")
        print("fundamentals_log still holds", cur.fetchone()[0], "rows (unchanged)")
        cur.execute("SELECT count(*) FROM fundamental_facts")
        print("fundamental_facts still holds", cur.fetchone()[0], "rows")
    conn.commit()
PY
```

Expected: `snapshot: 776 log rows`, `fundamentals_log still holds 776 rows (unchanged)`,
`fundamental_facts still holds 1228822 rows`.

```bash
# 6c. The member set the run must cover, as the one comma list --symbols takes.
mkdir -p /tmp/seer-fixb
"$SEER_PY" - <<'PY' > /tmp/seer-fixb/symbols.txt
import os, psycopg
from datetime import date
from seer_engine.commands import fundamentals as f

with psycopg.connect(os.environ["SEER_TRAIN_URL"]) as c:
    windows = f.membership_windows(c, f.DEFAULT_SINCE, date.today())
symbols = sorted(windows)
assert len(symbols) >= 900, f"only {len(symbols)} members -- did `universe refresh` run?"
print(",".join(symbols), end="")
PY
tr ',' '\n' < /tmp/seer-fixb/symbols.txt | wc -l      # expect 912 (913 ever-members less SPY)
wc -c < /tmp/seer-fixb/symbols.txt                     # ~5 kB, well inside ARG_MAX
```

`membership_windows` is the *same* function the default path calls, with the *same* floor, and
it already drops `SPY`. So the list is exactly what `select_symbols` would have returned — the
run fetches the same CIKs an emptied log would have produced, and deletes nothing to get there.

**Impact:** `universe` goes from 0 to 1544 rows. `fundamentals_log` is **unchanged** (776 rows),
with a snapshot beside it. **No row is deleted anywhere.**

### Step 7: A one-filer smoke test before the 30-minute run

**File:** none. `--symbols` ignores `fundamentals_log` outright and `--dry-run` rolls every
write back, so this proves the new floor fetches pre-2013 facts without writing anything.

```bash
"$SEER_PY" -m seer_engine fundamentals --dry-run \
    --symbols ATVI --since 2009-01-01 --since-filed 2009-01-01 --no-sync-map
```

**What to look for:** the summary's `facts: N kept` for ATVI must be materially larger than the
count stored for CIK `0000718877` today. Check that number first:

```bash
"$SEER_PY" - <<'PY'
import os, psycopg
with psycopg.connect(os.environ["SEER_TRAIN_URL"]) as c:
    print(c.execute("SELECT count(*), min(filed) FROM fundamental_facts WHERE cik = 718877")
          .fetchall())
PY
```

If `kept` is not larger, or `min(filed)` in the dry run's debug output is still 2013, the floor
did not take effect — stop and find out why before spending 30 minutes and ~890 SEC calls.

**Impact:** none. One `companyfacts` call; every write rolled back.

### Step 8: The run

**File:** none.

```bash
cd "$SEER_WT"
"$SEER_PY" -m seer_engine fundamentals \
    --since 2009-01-01 --since-filed 2009-01-01 \
    --symbols "$(cat /tmp/seer-fixb/symbols.txt)" \
    2>&1 | tee /tmp/seer-fixb/ingest-$(date +%Y%m%dT%H%M%S).log
```

The explicit floors are redundant after Step 1 and are passed anyway, so the log records what
the run was asked for rather than what a constant happened to be. **`--retry-failed` is not
passed and must not be**: with `--symbols` the log is ignored outright, so the flag that spawned
this phase's blocker section has no effect here at all.

**What it does.** `sync_ticker_cik` replaces the `ticker_cik` table with phase 2's CSV (797 rows
-> >= 916, `NONE` rows excluded) in one transaction. `select_symbols` returns the 912 symbols
from 6c verbatim; `plan_jobs` resolves them against the per-symbol `windows` the populated
`universe` supplies, grouping into roughly 890 distinct CIKs — up from 776 — and skips none,
because `logged` is `{}` whenever `--symbols` is given. Batches of 20 CIKs are fetched and
written, each batch one transaction carrying its own `fundamentals_log` rows.

**Expect it to take 15–45 minutes** at the measured 1–3 s per filer. `sec.Client` paces itself;
this command adds no sleep.

**If it crashes or is interrupted**, either resume is correct:

1. **Re-run the identical command.** Always right, never under-fetches, and costs at most
   another 45 minutes of free SEC calls — the facts upsert is `IS DISTINCT FROM`-guarded, so
   every CIK already done writes zero changed fact rows.
2. **Narrow it**, if the lost time matters. A CIK re-fetched at the 2009 floor carries
   `first_filed < 2013-01-01` in its log row unless it genuinely has no older filing, so the
   not-yet-done set is:

   ```bash
   "$SEER_PY" - <<'PY' > /tmp/seer-fixb/symbols-resume.txt
   import os, psycopg
   todo = set(open("/tmp/seer-fixb/symbols.txt").read().split(","))
   with psycopg.connect(os.environ["SEER_TRAIN_URL"]) as c:
       done = {r[0] for r in c.execute(
           "SELECT DISTINCT m.symbol FROM fundamentals_log l "
           "JOIN ticker_cik m ON m.cik = l.cik "
           "WHERE l.first_filed < DATE '2013-01-01'").fetchall()}
   rest = sorted(todo - done)
   assert rest, "nothing left to fetch"
   print(",".join(rest), end="")
   PY
   ```

   then re-run Step 8 with `symbols-resume.txt`. It over-fetches the genuinely-2013-onward
   filers, which is idempotent and cheap, and it never skips one that is still missing history.

**Do not** repeat 6b on a resume — it would overwrite the snapshot with the half-updated ledger.

**Expected summary shape** (the numbers are what to record, not what to require):

```
fundamentals: members since 2009-01-01, facts filed on or after 2009-01-01
  ticker_cik: <>= 916> rows, replaced
  symbols: <~900> ok, <some> empty, <0 hoped> failed, 0 skipped (CIK already logged)
  filers: <~890> companyfacts calls, <~890> fundamentals_log rows written
  facts: <N> kept, <M> inserted or changed
  fundamental_facts table: <X> MB (pg_total_relation_size)
```

`0 skipped` is structural under `--symbols` and therefore proves nothing on its own. **The line
that proves the run did the right thing is `filers:`** — it must read roughly **890**
`companyfacts` calls. A three-figure number near 120 means the symbol list was built against an
empty `universe` or the wrong floor; stop and redo 6a/6c.

**Impact:** `ticker_cik` replaced; `fundamentals_log` rewritten with one row per CIK;
`fundamental_facts` grows by the 2009–2014 facts of the existing filers plus everything the 118
new symbols' filers contribute. Nothing outside the local train database is written.

### Step 9: The measurement — this phase's deliverable

**File:** none. Run every query and record every answer in the phase summary, **whatever the
numbers are**. Do not reshape anything around a hoped-for value.

```bash
"$SEER_PY" - <<'PY'
import os, psycopg

JOIN = ("FROM fundamental_facts f JOIN ticker_cik m ON m.cik = f.cik "
        "AND f.filed >= m.start_date AND (m.end_date IS NULL OR f.filed < m.end_date) ")

# The 2013-2026 baseline measured at 2dad9ff, for the comparison section 3 asks for.
BASELINE = {2013: 89913, 2014: 91578, 2015: 91921, 2016: 91655, 2017: 90595,
            2018: 92259, 2019: 98506, 2020: 98431, 2021: 91870, 2022: 84183,
            2023: 83277, 2024: 83970, 2025: 83504, 2026: 57160}

with psycopg.connect(os.environ["SEER_TRAIN_URL"]) as c:
    print("=== M1  facts by filed year (stored), vs the 2dad9ff baseline ===")
    print(f"{'year':>6} {'facts':>10} {'filers':>8} {'baseline':>10} {'delta':>10}")
    rows = c.execute(
        "SELECT extract(year FROM filed)::int, count(*), count(DISTINCT cik) "
        "FROM fundamental_facts GROUP BY 1 ORDER BY 1").fetchall()
    total = 0
    for year, n, filers in rows:
        total += n
        base = BASELINE.get(year)
        print(f"{year:>6} {n:>10,} {filers:>8} "
              f"{(f'{base:,}' if base else '--'):>10} "
              f"{(f'{n-base:+,}' if base else '--'):>10}")
    print(f"{'total':>6} {total:>10,}   (baseline total 1,228,822)")

    print("\n=== M2  table totals ===")
    print(c.execute(
        "SELECT count(*) AS facts, count(DISTINCT cik) AS ciks, min(filed), max(filed), "
        "min(period_end), pg_size_pretty(pg_total_relation_size('fundamental_facts')) "
        "FROM fundamental_facts").fetchall())

    print("\n=== M3  what the PANEL sees: the dated ticker_cik join, by filed year ===")
    print("    (baseline: 831,725 rows / 780 symbols, and 2013-2014 absent entirely)")
    for row in c.execute(
            "SELECT extract(year FROM f.filed)::int, count(*), count(DISTINCT m.symbol) "
            + JOIN + "GROUP BY 1 ORDER BY 1").fetchall():
        print(f"    {row[0]}  {row[1]:>10,} rows  {row[2]:>4} symbols")
    print("    joined total:", c.execute("SELECT count(*), count(DISTINCT m.symbol), "
                                         "max(f.filed) " + JOIN).fetchall())

    print("\n=== M4  facts EDGAR tagged with filed < period_end (b76b38d; 28 / 18 before) ===")
    print("    stored:", c.execute(
        "SELECT count(*), count(DISTINCT cik) FROM fundamental_facts "
        "WHERE filed < period_end").fetchall())
    print("    joined:", c.execute(
        "SELECT count(*) " + JOIN + "WHERE f.filed < f.period_end").fetchall())
    print("    (facts_from_frame drops and counts these; it is NOT an error)")

    print("\n=== M5  fundamentals_log outcome ===")
    print("   ", c.execute("SELECT status, count(*) FROM fundamentals_log "
                           "GROUP BY 1 ORDER BY 1").fetchall())
    for cik_, err in c.execute("SELECT cik, error FROM fundamentals_log "
                               "WHERE status = 'failed' ORDER BY cik").fetchall():
        print(f"    FAILED {cik_}: {err}")

    print("\n=== M6  ticker_cik and universe ===")
    print("   ", c.execute("SELECT count(*), count(DISTINCT symbol) FROM ticker_cik").fetchall())
    print("   ", c.execute("SELECT count(*), count(DISTINCT symbol) FROM universe").fetchall())
    c.rollback()
PY
```

**How to report it.** In the phase summary, paste M1's table and M3's table verbatim, then add
one paragraph in plain words:

- How many facts 2009, 2010, 2011 and 2012 each hold, and how many distinct filers contributed
  to each. **If 2009–2010 land far below ~90k, say so in those words** — "2009 holds N facts
  from F filers against a 2013 baseline of 89,913 from 773; the real floor is therefore Y, not
  2009" — and leave it there. Phase 5 writes it into the runbook and §4. XBRL phased in by filer
  size, so a thin, large-cap-skewed 2009 is the expected outcome, not a failure of this phase.
- The new `filed < period_end` count from M4, stored and joined. It will rise as the window
  widens (28 / 18 before). It is a filer-side typo class, it is dropped and counted by
  `facts_from_frame`, and **it is not an error**.
- Whether M3's 2013 and 2014 rows are now non-zero. That is the single number that says Fix A
  and Fix B worked together: 181,491 facts that were stored and invisible should now reach the
  panel.
- Any `failed` row in M5, with its error, or the explicit statement that there are none.

**Impact:** read-only. Produces the phase's deliverable.

---

## Verification

**Build:** this is pure Python; `python -m compileall` is implied by the test run.

```bash
cd "$SEER_WT"
"$SEER_PY" -c "from seer_engine.commands import fundamentals; print(fundamentals.DEFAULT_SINCE, fundamentals.DEFAULT_SINCE_FILED)"
```

**Tests:**

```bash
cd "$SEER_WT"

# Non-DB suite.
"$SEER_PY" -m pytest engine/tests -q

# With the DB tests. SAFE AGAINST THE SAME CONTAINER THE TRAINING FACTS LIVE IN:
# engine/tests/conftest.py gives every DB test a throwaway schema `t_<hex>` and never touches
# `public`, where the 1.2M facts are. Nobody needs to panic about this line.
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
"$SEER_PY" -m pytest engine/tests -q
```

**The test delta, not an absolute.** This phase adds and removes **no** test: it edits four
existing ones in `engine/tests/test_fundamentals_command.py` in place, so its delta is **+0**
and every test that passed must still pass. Off the `2dad9ff` baseline alone that is 2216
passed / 332 skipped; in the swarm the inherited count is whatever phases 1, 2 and 4 contributed.
The 332 skips are exactly the DB tests; with `PG_TEST_URL` set they run and must pass. **No
phase may reduce the passing count** (plan invariant 1).

**Manual check:**

- `git diff --stat` shows exactly two files: `engine/src/seer_engine/commands/fundamentals.py`
  and `engine/tests/test_fundamentals_command.py`. If `ticker_cik.csv` or anything under
  `engine/src/seer_engine/fundamentals/` appears, a phase boundary was crossed.
- `grep -n "2015-01-02\|2013-01-01" engine/src/seer_engine/commands/fundamentals.py` returns
  nothing.
- The Step 8 summary line reads roughly `filers: ~890 companyfacts calls`. (`0 skipped` is
  automatic under `--symbols` and is not evidence of anything.)
- M5 shows no unexplained `failed` row.

**Exit criteria:**

1. Both floors are `date(2009, 1, 1)` and the full suite is green, with and without `PG_TEST_URL`.
2. `universe` holds 1544 rows in the local train database.
3. `fundamentals_log` holds one row per known CIK (~890 after the run, up from 776), with every
   `failed` row explained in the phase summary or none at all, and **no row was deleted** to get
   there — `fundamentals_log_pre_fixb` is a snapshot, never a restore point this phase needed.
4. The per-year `filed` counts for 2009–2026 (M1), the joined per-year counts (M3), the
   `fundamental_facts` row count and `pg_total_relation_size` (M2), and the new
   `filed < period_end` counts (M4) are **recorded in the phase summary**, as measured.
5. The summary states plainly how thin or thick 2009–2012 actually are, in the terms §3 asked
   for, without reshaping the conclusion around a hoped-for number.
6. Neon is untouched: no command in this phase ran without `SEER_ENV_FILE` pointing at
   `/home/miftah/seer/.env.local-train`.

---

## Handoffs

Work found but deliberately left to another phase.

- **Writing the measured numbers into prose — phase 5 (R4).** M1/M3's tables, the honest
  sentence about how thin 2009–2010 are, and the new `filed < period_end` count belong in
  `docs/runbooks/data-pipeline.md` and §4 of
  `docs/plans/2026-10-05-fundamental-panel-coverage.md`. This phase produces and reports the
  numbers; it writes no `docs/` file. R4 is phase 5's, not this phase's.
- **Refreshing `engine/.research/` so the panel actually contains these facts — phase 4, then
  phase 5.** The rows this phase writes reach no backtest until the store's `fundamentals.csv`
  is rebuilt without re-downloading bars. This phase does not touch `engine/.research/`,
  `research.py` or `commands/research_store.py`.
- **Measuring panel coverage after the refresh — phase 1's `--coverage`, run by phase 5 (R3/R4).**
  "Facts by filed year" is not "dates on which the panel can rank 20 symbols". This phase
  deliberately reports only the former; conflating them is the M0005 bug (plan invariant 9).
- **`engine/package_readme.md` and the `m0005` preamble — phase 5.** Both describe the ingest
  and will be stale after this phase; neither is touched here.
- **`commands/universe.py:24`'s `SINCE = date(2015, 1, 1)`** is a display constant of the
  `universe` command's summary line and has nothing to do with the ingest floors. It is left
  exactly as it is. If anyone later wants it aligned, that is a separate change in a separate
  phase — it is not in this phase's `satisfies`.
- **`fundamentals_log_pre_fixb`** is left in the local train database as a rollback aid — a
  snapshot copy, taken before the run and never written to again. Dropping it is a one-liner
  whenever the operator is satisfied; it is not in any migration and not in git.

---

## Rollback

This phase has two halves and they undo independently.

**The code** — one commit on `feature/fundamental-panel-coverage`:

```bash
git revert <this phase's commit>
```

Both constants return to `date(2015, 1, 2)` / `date(2013, 1, 1)` and the four test edits revert
with them. Nothing else in the tree depends on either value.

**The database** — the local train database only; **Neon is untouched throughout, so production
cannot be affected.**

```bash
export SEER_TRAIN_URL=postgresql://postgres:pg@localhost:55432/postgres
"$SEER_PY" - <<'PY'
import os, psycopg
url = os.environ["SEER_TRAIN_URL"]
assert "localhost:55432" in url, f"refusing to run against {url}"
with psycopg.connect(url) as conn:
    with conn.cursor() as cur:
        # 1. the facts this phase added
        cur.execute("DELETE FROM fundamental_facts WHERE filed < '2013-01-01'")
        print("deleted", cur.rowcount, "pre-2013 facts")
        # 2. the resume ledger, from the snapshot Step 6b took. OPTIONAL: this phase never
        #    deleted a log row, so the only thing restoring buys is the pre-run first_filed /
        #    rows / updated_at values. Skip it and the ledger stays correct about what is stored.
        cur.execute("TRUNCATE fundamentals_log")
        cur.execute("INSERT INTO fundamentals_log SELECT * FROM fundamentals_log_pre_fixb")
        print("restored", cur.rowcount, "log rows")
    conn.commit()
PY
```

Two residues this does not undo, both harmless and both re-derivable:

- The **118 new symbols' facts filed from 2013 on** stay. They are correct facts about correct
  filers; they simply would not have been fetched before. Removing them needs phase 2 reverted
  first, after which `DELETE FROM fundamental_facts f WHERE NOT EXISTS (SELECT 1 FROM ticker_cik
  m WHERE m.cik = f.cik)` run against the restored `ticker_cik` clears them.
- The `ticker_cik` table now mirrors phase 2's CSV. Reverting phase 2 and re-running
  `fundamentals --no-sync-map`-less (or `universe refresh` followed by any ingest) replaces it
  again; the table is a mirror, never a source of truth.
- `universe` is now populated. That is a strict improvement and `universe refresh` is idempotent;
  there is nothing to undo. `TRUNCATE universe` restores the measured starting state if someone
  wants the before-picture back exactly.

A clean re-run of this phase from scratch is: revert the code, restore the log, delete the
pre-2013 facts, then redo Steps 1–9.

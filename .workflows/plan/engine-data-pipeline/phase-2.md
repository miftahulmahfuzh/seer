# Phase 2: Point-in-time universe membership

**Plan set:** `ENGINE_DATA_PIPELINE_PLAN.md`
**Analysis:** `20261003-121931-K7P2_code_analyzer.md`
**Spec:** `docs/handover/2026-10-03-data-pipeline.md` §2.2, §6.1, §6.3, §6.7, §7 (membership source)
**Satisfies:** R2 (point-in-time S&P 500 ∪ Nasdaq-100 membership in the new `universe` table), R4 (`universe refresh` re-run writes nothing), R6 (unit tests and a dry-run that writes nothing)
**Depends on:** Phase 1
**Difficulty:** NORMAL
**Package:** `engine/` (`seer_engine.membership`, `seer_engine.commands.universe`, `engine/data/`)

---

## Goal

After this phase `python -m seer_engine universe refresh` fills the `universe` table that phase 1's
migration 002 created. The rows are every S&P 500 and Nasdaq-100 membership interval since 1996/2007,
stored under the ticker `bars` uses. The command replaces the table in one transaction and writes
nothing on a re-run. `python -m seer_engine universe check` compares the computed current members
with Wikipedia's live component tables and exits 1 on any drift. The membership inputs are
vendored and pinned in `engine/data/` with their provenance and known gaps.

**Pre-verified while planning (2026-10-03).** The code below ran end to end against a Postgres 16
built from phase 1's draft migration 002, and against the live Wikipedia API:

- 29/29 tests passed.
- `universe refresh` reported 1,544 intervals, 1,265 distinct symbols, 795 since 2015-01-01, and
  current SP500=503 NDX=101 union=518. The second run printed `unchanged, nothing written`.
- `universe check` printed `identical` for both indexes and exited 0.

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.
**Creates:**
- `engine/data/sp500_history.csv`, `engine/data/ndx_history.csv` (vendored, pinned by full sha)
- `engine/data/membership_overrides.csv`, `engine/data/ticker_aliases.csv`, `engine/data/SOURCES.md`
- `seer_engine.membership` (`engine/src/seer_engine/membership.py`):
  - constants `DATA_DIR`, `SNAPSHOT_FILES`, `INDEX_IDS = ("SP500", "NDX")`, `OVERRIDES_FILE`,
    `ALIASES_FILE`, `WIKIPEDIA_PAGES`
  - types `Snapshot = tuple[date, frozenset[str]]`, `MembershipError(ValueError)`, and frozen
    dataclasses `Interval(symbol, index_id, start_date, end_date: date|None, source_symbol)`,
    `Override(date, index_id, action, ticker, note)`, `Alias(old, new, effective_date, note)`
  - `normalize_ticker(raw) -> str`
  - `load_snapshots(path) -> list[Snapshot]`, `load_overrides(path) -> list[Override]`,
    `load_aliases(path) -> list[Alias]`
  - `apply_overrides(snapshots, overrides, index_id) -> list[Snapshot]`
  - `resolve_symbol(ticker, on, aliases_by_old) -> str`
  - `build_intervals(snapshots, index_id, aliases=()) -> list[Interval]`
  - `compute_universe(data_dir=DATA_DIR) -> list[Interval]`
  - `current_members(intervals, index_id) -> frozenset[str]`
  - `symbols_since(intervals, since) -> frozenset[str]`
  - `stored_intervals(conn) -> set[Interval]`
  - `replace_universe(conn, intervals) -> int`
  - `parse_constituents(wikitext) -> frozenset[str]`
  - `diff_members(computed, reference) -> dict[str, tuple[list[str], list[str]]]`
- `seer_engine.commands.universe` (`engine/src/seer_engine/commands/universe.py`):
  - the command contract: `HELP`, `add_arguments(p)`, `run(args) -> int`
  - actions `refresh` and `check`, each taking `--data-dir`, plus `--dry-run`/`-v` accepted after
    the action
  - helpers `refresh(conn, intervals, dry_run) -> RefreshResult(changed, rows)`,
    `check(intervals, fetch, out=None) -> int`, `fetch_wikitext(page) -> str`, `print_summary(intervals)`
- `engine/tests/test_membership.py`

**Signature changes:** none (all new).

**Requires (from Phase 1, consumed exactly as in the plan index "Shared interface contract"):**
- `db.connect()`, `db.transaction(conn, dry_run)`: a context manager that commits on success,
  rolls back on error, and rolls back under dry_run. A `return` inside the block counts as success.
- `demo.purge_demo_if_needed(conn, dry_run)`
- `http.get_json(url, params)`. Its requests must carry a non-default User-Agent: Wikipedia
  returns **403** to `python-requests/x`. It accepted `seer-engine/0.1.0`, which is what phase 1's
  draft `http.py` sets.
- `cli` discovers `commands/universe.py` automatically (invariant 7), so `cli.py` is not edited.
  `cli.build_parser()` is used by two CLI tests.
- Migration `db/migrations/002_engine.sql` creates exactly the table below. **This is the table
  phase 2 writes. If phase 1 changes any column name, the `index_id` values, or the
  exclusive-end meaning, phase 2's SQL must change too:**
  ```sql
  CREATE TABLE IF NOT EXISTS universe (
    symbol         text NOT NULL,
    index_id       text NOT NULL CHECK (index_id IN ('SP500', 'NDX')),
    start_date     date NOT NULL,
    end_date       date,                 -- EXCLUSIVE; NULL = still a member
    source_symbol  text NOT NULL,
    PRIMARY KEY (index_id, symbol, start_date),
    CHECK (end_date IS NULL OR end_date > start_date)
  );
  ```
  Phase 2 stores the source tickers oldest first, joined with `/`, when one merged interval
  spans a rename (`FB/META`, `HCP/PEAK/DOC`). **Reconciled:** phase 1's migration comment on
  `source_symbol` now documents exactly that form.
- `engine/tests/conftest.py` fixture `pg`: a `psycopg.Connection` (autocommit off) whose
  search_path is a throwaway schema with every `db/migrations/*.sql` applied. It skips when
  `PG_TEST_URL` is unset.
- `config.REPO_ROOT` is not used. `membership.DATA_DIR` is `Path(__file__).resolve().parents[2] / "data"`,
  which is `engine/data` in the src layout. That needs the editable install phase 1 sets up
  (`pip install -e 'engine[dev]'`); `--data-dir` covers any other layout.

**Provides (for later phases):**
- Phase 3 (`backfill`) reads `universe.all_symbols(conn, since)` (phase 1). It works once
  `universe refresh` has run: 795 symbols since 2015-01-01, plus SPY.
- Phase 4 (`nightly`) reads `universe.symbols_for_bars` (phase 1). Same data.
- Phase 5's weekly workflow runs `python -m seer_engine universe refresh` then
  `python -m seer_engine universe check`. Exit codes: refresh 0 (1 on an error such as a bad
  override). check 0 when identical, 1 on drift or on a fetch/parse failure (the
  `cli.main` exception path).

**Leaves alone (owned by others):** `engine/src/seer_engine/{cli,config,db,http,dates,demo,universe,bars,fx,runs}.py`,
`commands/migrate.py`, `db/migrations/*`, `engine/tests/conftest.py`, `engine/pyproject.toml` (Phase 1);
`yahoo.py`, `commands/backfill.py` (Phase 3); `massive.py`, `splits.py`, `commands/nightly.py` (Phase 4);
`.github/`, `docs/`, `web/` (Phase 5).

## Files

| File | Action | What changes |
|---|---|---|
| `engine/data/sp500_history.csv` | create (vendored) | fja05680 S&P 500 snapshots @ `a2430f2a…`, 2,720 rows to 2026-08-18 |
| `engine/data/ndx_history.csv` | create (vendored) | thuningxu Nasdaq-100 snapshots @ `1cc1de27…`, 112 rows to 2026-05-18 |
| `engine/data/membership_overrides.csv` | create | 20 rows: NDX changes after 2026-05-18, S&P changes after 2026-08-18 |
| `engine/data/ticker_aliases.csv` | create | 34 verified renames, old ticker → current ticker |
| `engine/data/SOURCES.md` | create | URL, full sha, license, last row, sha256, format, known gaps, re-vendoring |
| `engine/src/seer_engine/membership.py` | create | loaders, overrides, aliases, interval builder, DB replace, Wikipedia parse/diff |
| `engine/src/seer_engine/commands/universe.py` | create | `universe refresh` / `universe check` |
| `engine/tests/test_membership.py` | create | 29 tests: intervals, overrides, aliases, vendored data, check diff, DB idempotency, CLI |

All files are new, so every change starts at line 1.

## Implementation Steps

### Step 1: Vendor the two snapshot files
**File:** `engine/data/sp500_history.csv:1`, `engine/data/ndx_history.csv:1` (new)
**Change:** download both files at their pinned full commit shas, renamed. Do not edit them by hand.
**Code:**
```sh
cd /home/miftah/.worktrees/seer/engine-data-pipeline
mkdir -p engine/data
curl -fsSL -o engine/data/sp500_history.csv \
  "https://raw.githubusercontent.com/fja05680/sp500/a2430f2af0c79ddf0748e91de11bdeb1616ab5a7/S%26P%20500%20Historical%20Components%20%26%20Changes%20(Updated).csv"
curl -fsSL -o engine/data/ndx_history.csv \
  "https://raw.githubusercontent.com/thuningxu/sp500nq100/1cc1de2770874293597a418b41b079e5337b260c/nasdaq100_components_history.csv"
sha256sum engine/data/sp500_history.csv engine/data/ndx_history.csv
# expect:
# 36326709d46d6cd25834de5df457b16f5f96fad3a06b9beac28f7b88aa0b0d54  engine/data/sp500_history.csv
# c7de3905bfdd228eefbd3c7df1539a1178bee9006a04688fb319314a646e18e8  engine/data/ndx_history.csv
head -c 40 engine/data/sp500_history.csv; echo; tail -c 30 engine/data/ndx_history.csv
```
The full shas were resolved with `curl -s https://api.github.com/repos/fja05680/sp500/commits/a2430f2af0`
and `curl -s https://api.github.com/repos/thuningxu/sp500nq100/commits/1cc1de2770`. The thuningxu
license check was `curl -s https://api.github.com/repos/thuningxu/sp500nq100/license`, which returns 404:
there is no license file. SOURCES.md records that and the Wikipedia CC BY-SA derivation.
**Impact:** about 5.6 MB of data in the repo (the S&P file is 5.5 MB). `.gitignore` does not
exclude `engine/data`. The web build is unaffected. **Reconciled:** the Vercel project's root
directory is `web/`, so `engine/` is never part of a Vercel deployment; the repo-root
`.vercelignore` (`.env*`, `node_modules`, `.next`, `docs`) needs no change and no phase edits it.

### Step 2: Seed the overrides file
**File:** `engine/data/membership_overrides.csv:1` (new)
**Change:** add the changes Wikipedia recorded after each snapshot file's last row, as listed in
the analysis ("Recent changes to seed the overrides file"). Each override's ticker must be (for
`remove`) or must not be (for `add`) a member at that point. The loader enforces both, so a
typo fails `refresh` and the tests.
**Code:**
```csv
date,index_id,action,ticker,note
2026-06-22,NDX,add,ALAB,Wikipedia NASDAQ-100 component changes (read 2026-10-03): replaces CHTR
2026-06-22,NDX,remove,CHTR,Wikipedia NASDAQ-100 component changes (read 2026-10-03): replaced by ALAB
2026-06-22,NDX,add,CRWV,Wikipedia NASDAQ-100 component changes (read 2026-10-03): replaces CTSH
2026-06-22,NDX,remove,CTSH,Wikipedia NASDAQ-100 component changes (read 2026-10-03): replaced by CRWV
2026-06-22,NDX,add,NBIS,Wikipedia NASDAQ-100 component changes (read 2026-10-03): replaces INSM
2026-06-22,NDX,remove,INSM,Wikipedia NASDAQ-100 component changes (read 2026-10-03): replaced by NBIS
2026-06-22,NDX,add,RKLB,Wikipedia NASDAQ-100 component changes (read 2026-10-03): replaces VRSK
2026-06-22,NDX,remove,VRSK,Wikipedia NASDAQ-100 component changes (read 2026-10-03): replaced by RKLB
2026-06-22,NDX,add,TER,Wikipedia NASDAQ-100 component changes (read 2026-10-03): replaces ZS
2026-06-22,NDX,remove,ZS,Wikipedia NASDAQ-100 component changes (read 2026-10-03): replaced by TER
2026-06-29,NDX,add,HONA,Wikipedia NASDAQ-100 component changes (read 2026-10-03)
2026-07-07,NDX,add,SPCX,Wikipedia NASDAQ-100 component changes (read 2026-10-03)
2026-08-04,NDX,remove,EA,Wikipedia NASDAQ-100 component changes (read 2026-10-03)
2026-09-14,NDX,remove,KHC,Wikipedia NASDAQ-100 component changes (read 2026-10-03)
2026-09-21,SP500,add,BE,Wikipedia S&P 500 selected changes (read 2026-10-03): replaces TAP
2026-09-21,SP500,remove,TAP,Wikipedia S&P 500 selected changes (read 2026-10-03): replaced by BE
2026-09-21,SP500,add,P,Wikipedia S&P 500 selected changes (read 2026-10-03): replaces TTD
2026-09-21,SP500,remove,TTD,Wikipedia S&P 500 selected changes (read 2026-10-03): replaced by P
2026-09-21,SP500,add,ILMN,Wikipedia S&P 500 selected changes (read 2026-10-03): replaces BLDR
2026-09-21,SP500,remove,BLDR,Wikipedia S&P 500 selected changes (read 2026-10-03): replaced by ILMN
```
**Impact:** the computed current members match Wikipedia exactly (verified: SP500 503, NDX 101).

### Step 3: Seed the alias file (verified against the vendored CSVs)
**File:** `engine/data/ticker_aliases.csv:1` (new)
**Change:** map each historical ticker to the ticker yfinance and Massive use today.

How the brief's list was verified (`chk2.py`-style scan of both files: last snapshot with `old`,
first with `new`, whether the two ever share a snapshot):

- **Kept as given:** FB→META, PCLN→BKNG (only the NDX file uses PCLN; fja05680 back-fills BKNG
  from 2009), BK→BNY (the S&P file switches BK→BNY on 2026-05-21, so the alias is needed), ANTM→ELV,
  ABC→COR, FLT→CPAY, PKI→RVTY, RE→EG, WLTW→WTW, COG→CTRA, PEAK→DOC, BLL→BALL, TMK→GL.
- **FISV→FI is dropped and replaced by FI→FISV (2025-11-11).** Fiserv went FISV→FI on
  2023-06-07, then back to FISV on 2025-11-11. Both files hold FI only from 2023-06-07 to
  2025-11-04, and FISV is the current ticker (Yahoo knows FISV, not FI). With FI→FISV the S&P
  interval becomes one continuous `FISV` interval from 2001 with `source_symbol` `FISV/FI/FISV`.
- **VIAC→PARA becomes VIAC→PSKY.** PARA is no longer current: Paramount Skydance started
  2025-08-07, and Yahoo's PSKY history starts 2005, so it carries PARA/VIAC/CBS. Added
  PARA→PSKY and CBS→PSKY so the chain is flat.
- **FBHS→FBIN and HFC→DINO are kept even though `new` never appears in the files.** Both names
  left the S&P 500 before their rename. The brief's rule ("new must appear after") would drop
  them. The alias has a separate job: it makes the bars fetchable, because yfinance knows FBIN
  (from 2011) and DINO but not FBHS or HFC. They form non-contiguous intervals, which is
  correct. **This deliberately departs from the brief's drop rule.** The rule used instead is
  the one the test checks: `old` is a member somewhere before `effective_date`, and `old` and
  `new` never share a snapshot.
- **Added after verification** (each one passes that rule, and `new` first appears in exactly the
  snapshot after `old`'s last, except CTRP→TCOM): HCP→DOC, SYMC→GEN, NLOK→GEN, CBS→PSKY,
  PARA→PSKY, UTX→RTX, HRS→LHX, BBT→TFC, JEC→J, BHGE→BKR, ARNC→HWM, CDAY→DAY, DISCA→WBD, MYL→VTRS,
  LB→BBWI, MMC→MRSH, CTRP→TCOM (NDX keeps CTRP until its 2021 removal, so the effective date is
  2021-12-20).
- **Checked and rejected:** KORS→CPRI and Q→IQV (the pair shares snapshots, so the files mean two
  different securities), DWDP/DOW→DD, LLL→LHX, mergers whose ticker died (WRK→SW, TWX, ESRX→CI,
  RHT→IBM…), DISCK→WBD (a second share class, so it would collide with DISCA), CHK→EXE (the
  pre-bankruptcy equity was cancelled), GPS→GAP and ADS→BFH (could not confirm Yahoo history).
**Code:**
```csv
old,new,effective_date,note
ABC,COR,2023-08-30,AmerisourceBergen renamed Cencora
ANTM,ELV,2022-06-28,Anthem renamed Elevance Health
ARNC,HWM,2020-04-06,Arconic Inc renamed Howmet Aerospace 2020-04-01 (first snapshot without ARNC is 2020-04-06); ARNC was then reused by the Arconic Corp spin-off
BBT,TFC,2019-12-09,BB&T merged with SunTrust as Truist Financial (BB&T the surviving entity)
BHGE,BKR,2019-10-18,Baker Hughes a GE company renamed Baker Hughes
BK,BNY,2026-05-21,Bank of New York Mellon ticker change
BLL,BALL,2022-05-17,Ball Corp ticker change
CBS,PSKY,2019-12-04,CBS renamed ViacomCBS (VIAC) then Paramount (PARA) then Paramount Skydance (PSKY)
CDAY,DAY,2024-02-01,Ceridian renamed Dayforce
COG,CTRA,2021-10-01,Cabot Oil & Gas merged with Cimarex as Coterra Energy (Cabot the surviving entity)
CTRP,TCOM,2021-12-20,Ctrip renamed Trip.com 2019-10-31; the NDX snapshots keep CTRP until its 2021 removal
DISCA,WBD,2022-04-11,Discovery Inc renamed Warner Bros. Discovery (Discovery the surviving entity)
FB,META,2022-06-09,Facebook renamed Meta Platforms
FBHS,FBIN,2022-12-15,Fortune Brands Home & Security renamed Fortune Brands Innovations (left the S&P 500 before the rename)
FI,FISV,2025-11-11,Fiserv ticker FISV->FI 2023-06-07 and back to FISV 2025-11-11 (the FISV->FI direction is deliberately absent)
FLT,CPAY,2024-03-25,FleetCor renamed Corpay
HCP,DOC,2019-11-05,HCP renamed Healthpeak (PEAK) then took ticker DOC 2024-03-01
HFC,DINO,2022-03-14,HollyFrontier became HF Sinclair (left the S&P 500 before the rename)
HRS,LHX,2019-07-01,Harris merged with L3 as L3Harris Technologies (Harris the surviving entity)
JEC,J,2019-12-10,Jacobs Engineering ticker change
LB,BBWI,2021-08-03,L Brands renamed Bath & Body Works
MMC,MRSH,2026-01-14,Marsh & McLennan ticker change
MYL,VTRS,2020-11-16,Mylan combined with Upjohn as Viatris
NLOK,GEN,2022-11-08,NortonLifeLock renamed Gen Digital
PARA,PSKY,2025-08-07,Paramount Global merged with Skydance as Paramount Skydance
PCLN,BKNG,2018-02-27,Priceline Group renamed Booking Holdings
PEAK,DOC,2024-03-01,Healthpeak ticker change after the Physicians Realty merger
PKI,RVTY,2023-05-16,PerkinElmer renamed Revvity
RE,EG,2023-07-10,Everest Re renamed Everest Group
SYMC,GEN,2019-11-05,Symantec renamed NortonLifeLock (NLOK) then Gen Digital (GEN)
TMK,GL,2019-08-09,Torchmark renamed Globe Life
UTX,RTX,2020-04-03,United Technologies merged with Raytheon as Raytheon Technologies (UTX the surviving entity)
VIAC,PSKY,2022-02-16,ViacomCBS renamed Paramount (PARA) then Paramount Skydance (PSKY)
WLTW,WTW,2022-01-10,Willis Towers Watson ticker change
```
**Impact:** 28 merged multi-ticker intervals. META (both indexes), BKNG (NDX), FISV, GEN, DOC
and PSKY (S&P) each become one continuous interval. Without the aliases, phase 3 would be asked
to fetch dead tickers (FB, PCLN, FI, NLOK, PEAK, VIAC, PARA…) and would log them as failures.

### Step 4: Write SOURCES.md
**File:** `engine/data/SOURCES.md:1` (new)
**Code:**
````markdown
# Membership data sources

Vendored inputs for `seer_engine.membership` / `python -m seer_engine universe refresh`.
Owner of this directory: the engine. Read by nothing else.

## sp500_history.csv: S&P 500

| | |
|---|---|
| Upstream | https://github.com/fja05680/sp500, file `S&P 500 Historical Components & Changes (Updated).csv` |
| Pinned commit | `a2430f2af0c79ddf0748e91de11bdeb1616ab5a7` (2026-09-07) |
| Raw URL | https://raw.githubusercontent.com/fja05680/sp500/a2430f2af0c79ddf0748e91de11bdeb1616ab5a7/S%26P%20500%20Historical%20Components%20%26%20Changes%20(Updated).csv |
| License | MIT, Copyright (c) 2019-2020 Farrell J. Aultman |
| Rows | 2,720 snapshots, 1996-01-02 .. **2026-08-18** (503 members on the last row) |
| sha256 | `36326709d46d6cd25834de5df457b16f5f96fad3a06b9beac28f7b88aa0b0d54` |

## ndx_history.csv: Nasdaq-100

| | |
|---|---|
| Upstream | https://github.com/thuningxu/sp500nq100, file `nasdaq100_components_history.csv` |
| Pinned commit | `1cc1de2770874293597a418b41b079e5337b260c` (2026-06-07) |
| Raw URL | https://raw.githubusercontent.com/thuningxu/sp500nq100/1cc1de2770874293597a418b41b079e5337b260c/nasdaq100_components_history.csv |
| License | **None declared** (no LICENSE file; GitHub API reports no license as of 2026-10-03). The file is derived from Wikipedia's "List of NASDAQ-100 companies" component and change tables, which are CC BY-SA 4.0; attribute Wikipedia and its contributors. |
| Rows | 112 snapshots, 2007-02-01 .. **2026-05-18** (101 members on the last row) |
| sha256 | `c7de3905bfdd228eefbd3c7df1539a1178bee9006a04688fb319314a646e18e8` |

## Format (both files)

`date,tickers`. `tickers` is a quoted comma list holding the **full** membership effective on
that date. Membership on day D is the latest row with `date <= D`. Share classes use a dot
(`BRK.B`, `BF.B`), the canonical form everywhere in Seer.

## membership_overrides.csv

`date,index_id,action,ticker,note`, where `index_id` is `SP500|NDX` and `action` is `add|remove`.
Index changes that happened **after** a snapshot file's last row, read from Wikipedia's change
tables. Each date's rows become one extra snapshot appended to that index. An override
dated on or before the snapshot file's last row is an **error**: once the upstream file covers
that date the change would be applied twice. When re-vendoring a newer upstream file, delete the
overrides it now covers.

## ticker_aliases.csv

`old,new,effective_date,note`. A ticker `old` in a snapshot dated **before** `effective_date` is
stored under `new`, the ticker yfinance and Massive use today (`universe.symbol` = `bars.symbol`).
`universe.source_symbol` keeps the ticker(s) the source used, oldest first, joined with `/`
(`FB/META`). A rename followed directly by its new ticker gives one continuous interval. Every
`old` points straight at the **current** ticker (chains such as HCP->PEAK->DOC are written
HCP->DOC and PEAK->DOC; the loader rejects chains). On/after `effective_date` the old ticker is
taken literally, so a ticker reused by another company later (ARNC) stays correct.
`tests/test_membership.py::test_vendored_aliases_check_out` checks every row against the
snapshot files.

## Known gaps

- **Nasdaq-100 before 2017:** two removals are missing from Wikipedia's change table, so
  **ENDP** (added 2015-12-21) and **CMCSK** (added 2014-12-22) are absent for the windows
  they should cover. Some 2007-2014 departures may carry a later symbol. 2015-2017 shows
  105-108 lines (multi-class Google/Fox/Discovery/Liberty). 2017 onward is clean (upstream README).
- **Ticker renames:** fja05680 sometimes back-fills the current ticker (BKNG appears in the S&P
  file from 2009, never PCLN). thuningxu keeps some old tickers until removal (CTRP until
  2021). Renames not listed in `ticker_aliases.csv` are stored under the historical ticker.
  yfinance does not know those, so the backfill logs them as unfetchable.
- **Delisted / acquired names** (and mergers where the ticker died, such as WRK, CELG, TWX) have
  no yfinance history. This is the survivorship bias the handover (section 3) already accepts.
- **Freshness:** the snapshots end on 2026-08-18 (S&P) and 2026-05-18 (NDX). Later changes
  live in `membership_overrides.csv`. The weekly `universe check` compares the computed current
  members with Wikipedia and fails on any drift.

## Re-vendoring

```sh
cd engine/data
SP_SHA=<new full sha>; NDX_SHA=<new full sha>
curl -fsSL -o sp500_history.csv \
  "https://raw.githubusercontent.com/fja05680/sp500/${SP_SHA}/S%26P%20500%20Historical%20Components%20%26%20Changes%20(Updated).csv"
curl -fsSL -o ndx_history.csv \
  "https://raw.githubusercontent.com/thuningxu/sp500nq100/${NDX_SHA}/nasdaq100_components_history.csv"
```

Then update this file: commit, last row, sha256. Drop the overrides the new files now cover,
then run `pytest tests/test_membership.py`, `python -m seer_engine universe check` and
`python -m seer_engine universe refresh`.
````
**Impact:** documentation only. It meets handover §7: "Pick one, document its gaps."

### Step 5: `membership.py`: pure membership logic plus the two DB helpers
**File:** `engine/src/seer_engine/membership.py:1` (new)
**Change:** loaders that validate headers, dates, tickers and ordering. Overrides become
appended snapshots; an override on or before a file's last row raises. Aliases resolve per
snapshot, so a contiguous rename merges into one interval. The interval end is exclusive: the
date of the first snapshot that no longer contains the symbol. `compute_universe` puts it
together, and `stored_intervals`/`replace_universe` handle the table. It also holds the
Wikipedia wikitext parser and the diff for `check`. It imports no `seer_engine` module, so its
unit tests need no DB or env.
**Code:**
```python
"""Point-in-time S&P 500 / Nasdaq-100 membership.

Source data (vendored in ``engine/data``, see ``SOURCES.md``):

* ``sp500_history.csv`` / ``ndx_history.csv`` -- ``date,tickers`` snapshots; each row is the
  full membership effective on that date, so membership on D is the latest row with
  ``date <= D``.
* ``membership_overrides.csv`` -- ``date,index_id,action,ticker,note`` changes announced after
  a snapshot file's last row (``action`` is ``add`` or ``remove``).
* ``ticker_aliases.csv`` -- ``old,new,effective_date,note``: a historical ticker ``old`` seen
  in a snapshot dated before ``effective_date`` is stored under the current ticker ``new``
  (the symbol yfinance and Massive know, i.e. the ``bars`` symbol).

The output is a list of :class:`Interval` rows for the ``universe`` table. ``end_date`` is
exclusive: it is the date of the first snapshot that no longer contains the symbol, and
``None`` while the symbol is still a member.
"""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable, Mapping, Sequence

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

SNAPSHOT_FILES: Mapping[str, str] = {
    "SP500": "sp500_history.csv",
    "NDX": "ndx_history.csv",
}
INDEX_IDS: tuple[str, ...] = tuple(SNAPSHOT_FILES)
OVERRIDES_FILE = "membership_overrides.csv"
ALIASES_FILE = "ticker_aliases.csv"

_TICKER_RE = re.compile(r"^[A-Z][A-Z0-9]*(\.[A-Z])?$")

Snapshot = tuple[date, frozenset[str]]


class MembershipError(ValueError):
    """The vendored membership data is inconsistent."""


@dataclass(frozen=True, order=True)
class Interval:
    symbol: str
    index_id: str
    start_date: date
    end_date: date | None
    source_symbol: str


@dataclass(frozen=True)
class Override:
    date: date
    index_id: str
    action: str
    ticker: str
    note: str


@dataclass(frozen=True)
class Alias:
    old: str
    new: str
    effective_date: date
    note: str


def normalize_ticker(raw: str) -> str:
    """Canonical dot form: ``brk-b`` -> ``BRK.B``. Raises on anything that is not a ticker."""
    ticker = raw.strip().upper().replace("-", ".").replace("/", ".")
    if not _TICKER_RE.match(ticker):
        raise MembershipError(f"not a ticker: {raw!r}")
    return ticker


def _parse_date(raw: str, where: str) -> date:
    try:
        return date.fromisoformat(raw.strip())
    except ValueError as exc:
        raise MembershipError(f"{where}: bad date {raw!r}") from exc


def load_snapshots(path: Path) -> list[Snapshot]:
    """Read a ``date,tickers`` file into ascending ``(date, frozenset)`` snapshots."""
    snapshots: list[Snapshot] = []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames != ["date", "tickers"]:
            raise MembershipError(f"{path}: expected header date,tickers, got {reader.fieldnames}")
        for lineno, row in enumerate(reader, start=2):
            where = f"{path.name}:{lineno}"
            d = _parse_date(row["date"], where)
            tickers = frozenset(
                normalize_ticker(t) for t in row["tickers"].split(",") if t.strip()
            )
            if not tickers:
                raise MembershipError(f"{where}: empty membership")
            snapshots.append((d, tickers))
    if not snapshots:
        raise MembershipError(f"{path}: no rows")
    dates = [d for d, _ in snapshots]
    if dates != sorted(dates) or len(set(dates)) != len(dates):
        raise MembershipError(f"{path}: dates must be strictly ascending")
    return snapshots


def load_overrides(path: Path) -> list[Override]:
    overrides: list[Override] = []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames != ["date", "index_id", "action", "ticker", "note"]:
            raise MembershipError(
                f"{path}: expected header date,index_id,action,ticker,note, got {reader.fieldnames}"
            )
        for lineno, row in enumerate(reader, start=2):
            where = f"{path.name}:{lineno}"
            index_id = row["index_id"].strip()
            if index_id not in SNAPSHOT_FILES:
                raise MembershipError(f"{where}: unknown index_id {index_id!r}")
            action = row["action"].strip()
            if action not in ("add", "remove"):
                raise MembershipError(f"{where}: action must be add|remove, got {action!r}")
            overrides.append(
                Override(
                    date=_parse_date(row["date"], where),
                    index_id=index_id,
                    action=action,
                    ticker=normalize_ticker(row["ticker"]),
                    note=(row["note"] or "").strip(),
                )
            )
    return overrides


def load_aliases(path: Path) -> list[Alias]:
    aliases: list[Alias] = []
    seen: set[str] = set()
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames != ["old", "new", "effective_date", "note"]:
            raise MembershipError(
                f"{path}: expected header old,new,effective_date,note, got {reader.fieldnames}"
            )
        for lineno, row in enumerate(reader, start=2):
            where = f"{path.name}:{lineno}"
            alias = Alias(
                old=normalize_ticker(row["old"]),
                new=normalize_ticker(row["new"]),
                effective_date=_parse_date(row["effective_date"], where),
                note=(row["note"] or "").strip(),
            )
            if alias.old == alias.new:
                raise MembershipError(f"{where}: old == new ({alias.old})")
            if alias.old in seen:
                raise MembershipError(f"{where}: duplicate alias for {alias.old}")
            seen.add(alias.old)
            aliases.append(alias)
    olds = {a.old for a in aliases}
    for a in aliases:
        if a.new in olds:
            raise MembershipError(
                f"alias chain {a.old}->{a.new}->...: point every old ticker at the current one"
            )
    return aliases


def apply_overrides(
    snapshots: Sequence[Snapshot], overrides: Iterable[Override], index_id: str
) -> list[Snapshot]:
    """Append one snapshot per override date for ``index_id``.

    Overrides must be dated strictly after the snapshot file's last row; an earlier one would be
    applied twice once the upstream file catches up, so it is rejected.
    """
    result = list(snapshots)
    if not result:
        raise MembershipError(f"{index_id}: no snapshots")
    last_date = result[-1][0]
    by_date: dict[date, list[Override]] = defaultdict(list)
    for o in overrides:
        if o.index_id != index_id:
            continue
        if o.date <= last_date:
            raise MembershipError(
                f"override {o.date} {o.index_id} {o.action} {o.ticker} is not after the "
                f"snapshot file's last row ({last_date}); drop it from {OVERRIDES_FILE}"
            )
        by_date[o.date].append(o)
    members = set(result[-1][1])
    for d in sorted(by_date):
        for o in sorted(by_date[d], key=lambda x: (x.action != "remove", x.ticker)):
            if o.action == "remove":
                if o.ticker not in members:
                    raise MembershipError(f"override {d} {index_id}: remove {o.ticker}, not a member")
                members.remove(o.ticker)
            else:
                if o.ticker in members:
                    raise MembershipError(f"override {d} {index_id}: add {o.ticker}, already a member")
                members.add(o.ticker)
        result.append((d, frozenset(members)))
    return result


def _alias_map(aliases: Iterable[Alias]) -> dict[str, Alias]:
    return {a.old: a for a in aliases}


def resolve_symbol(ticker: str, on: date, aliases: Mapping[str, Alias]) -> str:
    """The bars symbol for ``ticker`` as it appeared in a snapshot dated ``on``."""
    alias = aliases.get(ticker)
    if alias is not None and on < alias.effective_date:
        return alias.new
    return ticker


def build_intervals(
    snapshots: Sequence[Snapshot], index_id: str, aliases: Iterable[Alias] = ()
) -> list[Interval]:
    """Turn ascending snapshots into membership intervals keyed by the current (bars) symbol.

    A symbol's interval runs from the first snapshot containing it to the first later snapshot
    that does not (exclusive). Because aliases are resolved per snapshot, an old ticker followed
    directly by its new one (FB -> META) yields one continuous interval; ``source_symbol`` then
    lists the tickers used, oldest first, joined with ``/`` (``FB/META``).
    """
    amap = _alias_map(aliases)
    open_start: dict[str, date] = {}
    open_sources: dict[str, list[str]] = {}
    intervals: list[Interval] = []
    for d, tickers in snapshots:
        resolved: dict[str, str] = {}
        for ticker in sorted(tickers):
            symbol = resolve_symbol(ticker, d, amap)
            if symbol in resolved:
                raise MembershipError(
                    f"{index_id} {d}: {resolved[symbol]} and {ticker} both resolve to {symbol}"
                )
            resolved[symbol] = ticker
        for symbol in sorted(set(open_start) - set(resolved)):
            intervals.append(
                Interval(
                    symbol=symbol,
                    index_id=index_id,
                    start_date=open_start.pop(symbol),
                    end_date=d,
                    source_symbol="/".join(open_sources.pop(symbol)),
                )
            )
        for symbol, ticker in resolved.items():
            if symbol not in open_start:
                open_start[symbol] = d
                open_sources[symbol] = [ticker]
            elif open_sources[symbol][-1] != ticker:
                open_sources[symbol].append(ticker)
    for symbol in sorted(open_start):
        intervals.append(
            Interval(
                symbol=symbol,
                index_id=index_id,
                start_date=open_start[symbol],
                end_date=None,
                source_symbol="/".join(open_sources[symbol]),
            )
        )
    return sorted(intervals, key=_sort_key)


def _sort_key(iv: Interval) -> tuple[str, str, date]:
    return (iv.index_id, iv.symbol, iv.start_date)


def compute_universe(data_dir: Path = DATA_DIR) -> list[Interval]:
    """Every membership interval of every index, from the vendored files."""
    overrides = load_overrides(data_dir / OVERRIDES_FILE)
    aliases = load_aliases(data_dir / ALIASES_FILE)
    intervals: list[Interval] = []
    for index_id, filename in SNAPSHOT_FILES.items():
        snapshots = load_snapshots(data_dir / filename)
        snapshots = apply_overrides(snapshots, overrides, index_id)
        intervals.extend(build_intervals(snapshots, index_id, aliases))
    return sorted(intervals, key=_sort_key)


def current_members(intervals: Iterable[Interval], index_id: str) -> frozenset[str]:
    """Symbols whose interval in ``index_id`` is still open."""
    return frozenset(
        iv.symbol for iv in intervals if iv.index_id == index_id and iv.end_date is None
    )


def symbols_since(intervals: Iterable[Interval], since: date) -> frozenset[str]:
    """Distinct symbols that were a member of any index on or after ``since``."""
    return frozenset(iv.symbol for iv in intervals if iv.end_date is None or iv.end_date > since)


def stored_intervals(conn) -> set[Interval]:
    """The ``universe`` table as a set of :class:`Interval`."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT symbol, index_id, start_date, end_date, source_symbol FROM universe"
        )
        return {Interval(*row) for row in cur.fetchall()}


def replace_universe(conn, intervals: Sequence[Interval]) -> int:
    """Replace the whole ``universe`` table; caller owns the transaction. Returns rows inserted."""
    with conn.cursor() as cur:
        cur.execute("DELETE FROM universe")
        cur.executemany(
            "INSERT INTO universe (symbol, index_id, start_date, end_date, source_symbol) "
            "VALUES (%s, %s, %s, %s, %s)",
            [
                (iv.symbol, iv.index_id, iv.start_date, iv.end_date, iv.source_symbol)
                for iv in intervals
            ],
        )
    return len(intervals)


# --- Wikipedia current components (used by `universe check`) -------------------------------

WIKIPEDIA_PAGES: Mapping[str, str] = {
    "SP500": "List of S&P 500 companies",
    "NDX": "List of NASDAQ-100 companies",
}

_CONSTITUENTS_TABLE_RE = re.compile(r'\{\|[^\n]*id="constituents"[^\n]*\n(.*?)\n\|\}', re.S)
_ROW_SEPARATOR_RE = re.compile(r"^\|-[^\n]*$", re.M)
_CELL_SEPARATOR_RE = re.compile(r"\|\||\n\|")
_TEMPLATE_RE = re.compile(r"\{\{([^{}]*)\}\}")
_WIKILINK_RE = re.compile(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]")
_REF_RE = re.compile(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", re.S)


def parse_constituents(wikitext: str) -> frozenset[str]:
    """Tickers in the first column of the ``id="constituents"`` table of a Wikipedia page.

    Handles both layouts in use on 2026-10-03: one cell per line with a
    ``{{NyseSymbol|MMM}}`` template (S&P 500) and ``| ADBE || [[Adobe Inc.]] || ...`` rows
    (Nasdaq-100).
    """
    match = _CONSTITUENTS_TABLE_RE.search(wikitext)
    if match is None:
        raise MembershipError('no {| ... id="constituents" table in the page wikitext')
    tickers: set[str] = set()
    for row in _ROW_SEPARATOR_RE.split(match.group(1)):
        row = row.strip()
        if not row.startswith("|"):
            continue  # header row ("!") or table caption/attributes
        first = _CELL_SEPARATOR_RE.split(row.lstrip("|"), maxsplit=1)[0]
        first = _REF_RE.sub("", first)
        template = _TEMPLATE_RE.search(first)
        if template is not None:
            first = template.group(1).split("|")[-1]
        first = _WIKILINK_RE.sub(r"\1", first)
        tickers.add(normalize_ticker(first))
    if not tickers:
        raise MembershipError("constituents table has no rows")
    return frozenset(tickers)


def diff_members(
    computed: Mapping[str, frozenset[str]], reference: Mapping[str, frozenset[str]]
) -> dict[str, tuple[list[str], list[str]]]:
    """Per index: (in reference but not computed, in computed but not reference). Only indexes
    with a difference are returned."""
    diffs: dict[str, tuple[list[str], list[str]]] = {}
    for index_id in INDEX_IDS:
        ours = computed.get(index_id, frozenset())
        theirs = reference.get(index_id, frozenset())
        missing = sorted(theirs - ours)
        extra = sorted(ours - theirs)
        if missing or extra:
            diffs[index_id] = (missing, extra)
    return diffs
```
**Impact:** new module. Nothing imports it except `commands/universe.py` and the tests.

Notes for the implementer:
- `parse_constituents` handles the two layouts live on 2026-10-03. **Verify it on the live pages**
  (Step 8, `universe check`). The S&P page puts each cell on its own line, with the ticker in
  `{{NyseSymbol|MMM}}` / `{{NasdaqSymbol|…}}` templates; the Nasdaq-100 page uses
  `| ADBE || [[Adobe Inc.]] || …`. Both tables carry `id="constituents"`. Any ticker cell that
  does not normalize to `^[A-Z][A-Z0-9]*(\.[A-Z])?$` raises `MembershipError`, so a layout change
  fails loudly instead of quietly returning garbage.
- The NDX page title is **"List of NASDAQ-100 companies"**. The "Nasdaq-100" article also exists,
  but its components table is not the one used here.

### Step 6: `commands/universe.py`: `refresh` and `check`
**File:** `engine/src/seer_engine/commands/universe.py:1` (new)
**Change:**
- `refresh` loads the intervals, then runs `demo.purge_demo_if_needed` in its own transaction
  (invariant 6). Next, in one `db.transaction(conn, dry_run)`, it compares the stored set with
  the computed set. If they are equal it returns with nothing written. Otherwise it runs
  `DELETE FROM universe` plus `executemany INSERT`.
- `check` is read-only, opens no DB connection, and takes an injectable `fetch` for tests.
- `--dry-run` and `-v` are also accepted after the action, because the global flags phase 1
  adds to the `universe` parser do not reach the nested `refresh`/`check` parsers.
**Code:**
```python
"""`universe refresh` / `universe check`: point-in-time index membership.

refresh  Rebuild the ``universe`` table from the vendored files in ``engine/data``. Full replace
         in one transaction; a no-op (nothing written) when the computed rows equal the stored
         rows.
check    Compare the computed current members with Wikipedia's current component tables.
         Read-only. Exit 1 on any difference, so the weekly workflow fails loudly on drift.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable, Sequence

from seer_engine import db, demo, http, membership
from seer_engine.membership import Interval

HELP = "Point-in-time S&P 500 / Nasdaq-100 membership: refresh the universe table, check drift"

SINCE = date(2015, 1, 1)
WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"

Fetch = Callable[[str], str]


@dataclass(frozen=True)
class RefreshResult:
    changed: bool
    rows: int


def add_arguments(p: argparse.ArgumentParser) -> None:
    sub = p.add_subparsers(dest="action", required=True, metavar="{refresh,check}")
    refresh = sub.add_parser("refresh", help="rebuild the universe table from engine/data")
    check = sub.add_parser(
        "check", help="compare current members with Wikipedia; exit 1 on any difference"
    )
    for action in (refresh, check):
        action.add_argument(
            "--data-dir",
            type=Path,
            default=membership.DATA_DIR,
            help="membership data directory (default: engine/data)",
        )
        # Accept the global flags after the action too (`universe refresh --dry-run`).
        # SUPPRESS keeps an absent flag from resetting the value parsed earlier.
        action.add_argument("--dry-run", action="store_true", default=argparse.SUPPRESS)
        action.add_argument("-v", "--verbose", action="count", default=argparse.SUPPRESS)


def run(args: argparse.Namespace) -> int:
    intervals = membership.compute_universe(args.data_dir)
    if args.action == "refresh":
        return _run_refresh(intervals, args.dry_run)
    if args.action == "check":
        return check(intervals, fetch_wikitext)
    raise ValueError(f"unknown universe action {args.action!r}")


def _run_refresh(intervals: Sequence[Interval], dry_run: bool) -> int:
    conn = db.connect()
    try:
        demo.purge_demo_if_needed(conn, dry_run)
        result = refresh(conn, intervals, dry_run)
    finally:
        conn.close()
    print_summary(intervals)
    if not result.changed:
        print("universe: unchanged, nothing written")
    elif dry_run:
        print(f"universe: would replace table with {result.rows} rows (dry run, rolled back)")
    else:
        print(f"universe: replaced table with {result.rows} rows")
    return 0


def refresh(conn, intervals: Sequence[Interval], dry_run: bool) -> RefreshResult:
    """Replace the ``universe`` table with ``intervals`` unless it already holds exactly them."""
    with db.transaction(conn, dry_run):
        if membership.stored_intervals(conn) == set(intervals):
            return RefreshResult(changed=False, rows=len(intervals))
        rows = membership.replace_universe(conn, intervals)
    return RefreshResult(changed=True, rows=rows)


def print_summary(intervals: Sequence[Interval]) -> None:
    sp = membership.current_members(intervals, "SP500")
    ndx = membership.current_members(intervals, "NDX")
    print(
        f"universe: {len(intervals)} intervals, "
        f"{len({iv.symbol for iv in intervals})} distinct symbols, "
        f"{len(membership.symbols_since(intervals, SINCE))} since {SINCE.isoformat()}"
    )
    print(f"universe: current SP500={len(sp)} NDX={len(ndx)} union={len(sp | ndx)}")


def fetch_wikitext(page: str) -> str:
    """Raw wikitext of a Wikipedia page via the MediaWiki parse API."""
    body = http.get_json(
        WIKIPEDIA_API,
        {
            "action": "parse",
            "page": page,
            "prop": "wikitext",
            "format": "json",
            "formatversion": "2",
            "redirects": "1",
        },
    )
    if "error" in body:
        raise RuntimeError(f"Wikipedia API error for {page!r}: {body['error']}")
    return body["parse"]["wikitext"]


def check(intervals: Sequence[Interval], fetch: Fetch, out=None) -> int:
    """Print the difference between computed and Wikipedia current members; 1 if any."""
    out = out or sys.stdout
    computed: dict[str, frozenset[str]] = {
        index_id: membership.current_members(intervals, index_id)
        for index_id in membership.INDEX_IDS
    }
    reference: dict[str, frozenset[str]] = {
        index_id: membership.parse_constituents(fetch(page))
        for index_id, page in membership.WIKIPEDIA_PAGES.items()
    }
    diffs = membership.diff_members(computed, reference)
    for index_id in membership.INDEX_IDS:
        line = (
            f"{index_id}: computed {len(computed[index_id])}, "
            f"Wikipedia {len(reference[index_id])}"
        )
        if index_id not in diffs:
            print(f"{line} -- identical", file=out)
            continue
        missing, extra = diffs[index_id]
        print(f"{line} -- DIFFERENT", file=out)
        if missing:
            print(f"  on Wikipedia, not computed: {' '.join(missing)}", file=out)
        if extra:
            print(f"  computed, not on Wikipedia: {' '.join(extra)}", file=out)
    if diffs:
        print(
            "universe check: drift -- add dated rows to engine/data/membership_overrides.csv "
            "(or ticker_aliases.csv for a rename), then run `universe refresh`",
            file=out,
        )
        return 1
    return 0
```
**Impact:** `python -m seer_engine --help` lists `universe`. Running `universe refresh` against Neon
**purges the demo data** (R5/§3 decision). That is intended, but phase 5 owns the live run; in
this phase, run it only against `PG_TEST_URL`.

### Step 7: Tests
**File:** `engine/tests/test_membership.py:1` (new)
**Change:** pure tests cover loaders, interval building (exclusive end, leave/rejoin, overrides
after a snapshot, overrides on or before a snapshot rejected, alias merge FB→META, alias not
applied after its date, alias collision, alias chain rejected, dot form). Vendored-data tests
check current counts, that overrides apply, that META is one interval, and that every alias
row checks out. `check` is tested with a stubbed fetch. DB tests (fixture `pg`) cover refresh
twice (no change), replacing changed rows, and dry run writing nothing. CLI tests cover flag
placement.
**Code:**
```python
"""Phase 2: point-in-time membership (engine/src/seer_engine/membership.py, commands/universe.py)."""

from __future__ import annotations

import io
from datetime import date
from pathlib import Path

import pytest

from seer_engine import membership as m
from seer_engine.commands import universe as cmd
from seer_engine.membership import Alias, Interval, MembershipError, Override

D = date.fromisoformat


def snaps(*rows: tuple[str, str]) -> list[m.Snapshot]:
    return [(D(d), frozenset(t.split(","))) for d, t in rows]


def write(path: Path, text: str) -> Path:
    path.write_text(text.strip() + "\n", encoding="utf-8")
    return path


# --- loading -----------------------------------------------------------------------------


def test_load_snapshots_reads_quoted_list_and_dot_form(tmp_path):
    path = write(
        tmp_path / "x.csv",
        'date,tickers\n2020-01-02,"AAPL,BRK.B,MSFT"\n2020-03-02,"AAPL,BRK-B"\n',
    )
    assert m.load_snapshots(path) == [
        (D("2020-01-02"), frozenset({"AAPL", "BRK.B", "MSFT"})),
        (D("2020-03-02"), frozenset({"AAPL", "BRK.B"})),
    ]


def test_load_snapshots_rejects_unsorted_dates(tmp_path):
    path = write(tmp_path / "x.csv", 'date,tickers\n2020-03-02,"A"\n2020-01-02,"A"\n')
    with pytest.raises(MembershipError, match="ascending"):
        m.load_snapshots(path)


def test_normalize_ticker():
    assert m.normalize_ticker(" brk-b ") == "BRK.B"
    assert m.normalize_ticker("BF.B") == "BF.B"
    with pytest.raises(MembershipError):
        m.normalize_ticker("Apple Inc.")


# --- intervals ---------------------------------------------------------------------------


def test_build_intervals_exclusive_end_and_open_interval():
    s = snaps(("2020-01-02", "A,B"), ("2020-02-03", "A,C"))
    assert m.build_intervals(s, "SP500") == [
        Interval("A", "SP500", D("2020-01-02"), None, "A"),
        Interval("B", "SP500", D("2020-01-02"), D("2020-02-03"), "B"),
        Interval("C", "SP500", D("2020-02-03"), None, "C"),
    ]


def test_build_intervals_leave_and_rejoin_gives_two_intervals():
    s = snaps(("2020-01-02", "A,B"), ("2020-02-03", "A"), ("2020-05-01", "A,B"))
    got = [iv for iv in m.build_intervals(s, "NDX") if iv.symbol == "B"]
    assert got == [
        Interval("B", "NDX", D("2020-01-02"), D("2020-02-03"), "B"),
        Interval("B", "NDX", D("2020-05-01"), None, "B"),
    ]


def test_alias_merges_contiguous_rename_into_one_interval():
    s = snaps(("2012-12-12", "AAPL,FB"), ("2022-06-09", "AAPL,META"))
    aliases = [Alias("FB", "META", D("2022-06-09"), "")]
    got = [iv for iv in m.build_intervals(s, "NDX", aliases) if iv.symbol == "META"]
    assert got == [Interval("META", "NDX", D("2012-12-12"), None, "FB/META")]


def test_alias_does_not_apply_on_or_after_effective_date():
    # The old ticker re-used by a different company after the rename stays itself.
    s = snaps(("2019-01-02", "ARNC"), ("2020-04-06", "HWM"), ("2021-01-04", "ARNC,HWM"))
    aliases = [Alias("ARNC", "HWM", D("2020-04-06"), "")]
    got = m.build_intervals(s, "SP500", aliases)
    assert got == [
        Interval("ARNC", "SP500", D("2021-01-04"), None, "ARNC"),
        Interval("HWM", "SP500", D("2019-01-02"), None, "ARNC/HWM"),
    ]


def test_alias_collision_in_one_snapshot_is_an_error():
    s = snaps(("2020-01-02", "FB,META"),)
    with pytest.raises(MembershipError, match="both resolve to META"):
        m.build_intervals(s, "NDX", [Alias("FB", "META", D("2022-06-09"), "")])


def test_load_aliases_rejects_chains(tmp_path):
    path = write(
        tmp_path / "a.csv",
        "old,new,effective_date,note\nHCP,PEAK,2019-11-05,\nPEAK,DOC,2024-03-01,\n",
    )
    with pytest.raises(MembershipError, match="chain"):
        m.load_aliases(path)


# --- overrides ---------------------------------------------------------------------------


def test_overrides_after_last_snapshot_append_snapshots():
    s = snaps(("2026-05-18", "A,B,C"))
    overrides = [
        Override(D("2026-06-22"), "NDX", "add", "D", ""),
        Override(D("2026-06-22"), "NDX", "remove", "B", ""),
        Override(D("2026-08-04"), "NDX", "remove", "C", ""),
        Override(D("2026-09-21"), "SP500", "add", "Z", ""),  # other index: ignored
    ]
    got = m.apply_overrides(s, overrides, "NDX")
    assert got == [
        (D("2026-05-18"), frozenset({"A", "B", "C"})),
        (D("2026-06-22"), frozenset({"A", "C", "D"})),
        (D("2026-08-04"), frozenset({"A", "D"})),
    ]
    ivs = {iv.symbol: iv for iv in m.build_intervals(got, "NDX")}
    assert ivs["B"].end_date == D("2026-06-22")
    assert ivs["C"].end_date == D("2026-08-04")
    assert ivs["D"] == Interval("D", "NDX", D("2026-06-22"), None, "D")


@pytest.mark.parametrize("when", ["2026-05-18", "2026-01-02"])
def test_override_on_or_before_last_snapshot_is_rejected(when):
    s = snaps(("2026-05-18", "A,B"))
    with pytest.raises(MembershipError, match="not after"):
        m.apply_overrides(s, [Override(D(when), "NDX", "add", "C", "")], "NDX")


def test_override_removing_non_member_is_rejected():
    s = snaps(("2026-05-18", "A,B"))
    with pytest.raises(MembershipError, match="not a member"):
        m.apply_overrides(s, [Override(D("2026-06-01"), "NDX", "remove", "Q", "")], "NDX")


def test_load_overrides_rejects_bad_action(tmp_path):
    path = write(
        tmp_path / "o.csv",
        "date,index_id,action,ticker,note\n2026-06-22,NDX,swap,A,\n",
    )
    with pytest.raises(MembershipError, match="add\\|remove"):
        m.load_overrides(path)


# --- vendored data -----------------------------------------------------------------------


@pytest.fixture(scope="module")
def vendored() -> list[Interval]:
    return m.compute_universe(m.DATA_DIR)


def test_vendored_data_builds(vendored):
    sp = m.current_members(vendored, "SP500")
    ndx = m.current_members(vendored, "NDX")
    assert 495 <= len(sp) <= 510
    assert 98 <= len(ndx) <= 110
    assert "BRK.B" in sp
    assert all(iv.end_date is None or iv.start_date < iv.end_date for iv in vendored)
    assert len(m.symbols_since(vendored, D("2015-01-01"))) > 700


def test_vendored_overrides_are_applied(vendored):
    ndx = m.current_members(vendored, "NDX")
    sp = m.current_members(vendored, "SP500")
    assert {"ALAB", "CRWV", "NBIS", "RKLB", "TER", "HONA", "SPCX"} <= ndx
    assert not {"CHTR", "CTSH", "INSM", "VRSK", "ZS", "EA", "KHC"} & ndx
    assert {"BE", "P", "ILMN"} <= sp
    assert not {"TAP", "TTD", "BLDR"} & sp


def test_vendored_fb_meta_is_one_interval(vendored):
    meta = [iv for iv in vendored if iv.symbol == "META"]
    assert {iv.index_id for iv in meta} == {"SP500", "NDX"}
    assert all(iv.end_date is None and iv.source_symbol == "FB/META" for iv in meta)
    assert not [iv for iv in vendored if iv.symbol == "FB"]


def test_vendored_aliases_check_out():
    """Every alias: the old ticker is a member somewhere before its effective date, and never
    shares a snapshot with the new ticker (which would mean two different securities)."""
    aliases = m.load_aliases(m.DATA_DIR / m.ALIASES_FILE)
    all_snaps = [
        s for f in m.SNAPSHOT_FILES.values() for s in m.load_snapshots(m.DATA_DIR / f)
    ]
    for a in aliases:
        before = [d for d, t in all_snaps if a.old in t and d < a.effective_date]
        assert before, f"{a.old}->{a.new}: {a.old} never a member before {a.effective_date}"
        both = [d for d, t in all_snaps if a.old in t and a.new in t]
        assert not both, f"{a.old}->{a.new}: both in the snapshot of {both[0]}"


# --- universe check ----------------------------------------------------------------------

SP_WIKITEXT = """
{| class="wikitable sortable mw-collapsible sticky-header" id="constituents"
|-
![[Ticker symbol|Symbol]]
! Security !! GICS Sector
|-
|| {{NyseSymbol|MMM}}
|| [[3M]]
|| Industrials
|-
|| {{NyseSymbol|BRK.B}}<ref>note</ref>
|| [[Berkshire Hathaway]]
|| Financials
|}
"""

NDX_WIKITEXT = """
{| class="wikitable sortable" id="constituents"
|-
! Ticker !! Company !! ICB Industry
|-
| ADBE || [[Adobe Inc.]] || Technology
|-
| [[Alphabet Inc.|GOOGL]] || [[Alphabet Inc.]] (Class A) || Technology
|}
"""


def test_parse_constituents_both_layouts():
    assert m.parse_constituents(SP_WIKITEXT) == {"MMM", "BRK.B"}
    assert m.parse_constituents(NDX_WIKITEXT) == {"ADBE", "GOOGL"}


def test_parse_constituents_without_table_raises():
    with pytest.raises(MembershipError, match="constituents"):
        m.parse_constituents("no table here")


def _fake_fetch(pages: dict[str, str]):
    def fetch(page: str) -> str:
        return pages[page]

    return fetch


def _intervals(sp: str, ndx: str) -> list[Interval]:
    return [Interval(t, "SP500", D("2020-01-02"), None, t) for t in sp.split(",")] + [
        Interval(t, "NDX", D("2020-01-02"), None, t) for t in ndx.split(",")
    ]


def test_check_identical_exits_0():
    fetch = _fake_fetch(
        {"List of S&P 500 companies": SP_WIKITEXT, "List of NASDAQ-100 companies": NDX_WIKITEXT}
    )
    out = io.StringIO()
    assert cmd.check(_intervals("MMM,BRK.B", "ADBE,GOOGL"), fetch, out) == 0
    assert "DIFFERENT" not in out.getvalue()


def test_check_difference_exits_1_and_names_symbols():
    fetch = _fake_fetch(
        {"List of S&P 500 companies": SP_WIKITEXT, "List of NASDAQ-100 companies": NDX_WIKITEXT}
    )
    out = io.StringIO()
    ivs = _intervals("MMM,TAP", "ADBE,GOOGL") + [
        Interval("BRK.B", "SP500", D("2010-02-16"), D("2020-01-02"), "BRK.B")  # closed
    ]
    assert cmd.check(ivs, fetch, out) == 1
    text = out.getvalue()
    assert "SP500: computed 2, Wikipedia 2 -- DIFFERENT" in text
    assert "on Wikipedia, not computed: BRK.B" in text
    assert "computed, not on Wikipedia: TAP" in text
    assert "NDX: computed 2, Wikipedia 2 -- identical" in text


# --- universe refresh (DB) ---------------------------------------------------------------


def _table(conn) -> list[tuple]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT symbol, index_id, start_date, end_date, source_symbol FROM universe "
            "ORDER BY index_id, symbol, start_date"
        )
        return cur.fetchall()


def test_refresh_twice_changes_nothing(pg, vendored):
    first = cmd.refresh(pg, vendored, dry_run=False)
    assert first.changed and first.rows == len(vendored)
    snapshot = _table(pg)
    assert len(snapshot) == len(vendored)

    second = cmd.refresh(pg, vendored, dry_run=False)
    assert second.changed is False
    assert _table(pg) == snapshot


def test_refresh_replaces_changed_rows(pg):
    old = [Interval("A", "SP500", D("2020-01-02"), None, "A")]
    new = [
        Interval("A", "SP500", D("2020-01-02"), D("2021-01-04"), "A"),
        Interval("B", "SP500", D("2021-01-04"), None, "B"),
    ]
    cmd.refresh(pg, old, dry_run=False)
    assert cmd.refresh(pg, new, dry_run=False).changed
    assert [row[0] for row in _table(pg)] == ["A", "B"]


def test_refresh_dry_run_writes_nothing(pg, vendored):
    result = cmd.refresh(pg, vendored, dry_run=True)
    assert result.changed
    assert _table(pg) == []


# --- CLI wiring --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "argv",
    [
        ["--dry-run", "universe", "refresh"],
        ["universe", "--dry-run", "refresh"],
        ["universe", "refresh", "--dry-run"],
    ],
)
def test_cli_parses_dry_run_anywhere(argv):
    from seer_engine import cli

    args = cli.build_parser().parse_args(argv)
    assert args.command == "universe" and args.action == "refresh"
    assert args.dry_run is True
    assert args.data_dir == m.DATA_DIR


def test_cli_check_defaults():
    from seer_engine import cli

    args = cli.build_parser().parse_args(["universe", "check"])
    assert args.action == "check" and args.dry_run is False
```
**Impact:** 29 tests. The 3 DB tests skip without `PG_TEST_URL`.

### Step 8: Run it
**Change:** no code. Run the commands under Verification, against a local Postgres only.

## Verification

**Build:**
```sh
cd /home/miftah/.worktrees/seer/engine-data-pipeline
engine/.venv/bin/python -c "import seer_engine.membership, seer_engine.commands.universe"
engine/.venv/bin/python -m seer_engine --help | grep universe
```
**Tests:**
```sh
# Postgres as phase 1's conftest documents (docker), or any local PG 16:
export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres
engine/.venv/bin/pytest engine/tests -q          # whole suite green (invariant 1)
engine/.venv/bin/pytest engine/tests/test_membership.py -q   # 29 passed, 0 skipped with PG_TEST_URL
```
**Manual check** (local DB only. **Never** point `DATABASE_URL_UNPOOLED` at Neon in this phase.
`SEER_ENV_FILE=/nonexistent` keeps `.env.local`, which holds the Neon URL, from loading):
```sh
cd /home/miftah/.worktrees/seer/engine-data-pipeline/engine
export SEER_ENV_FILE=/nonexistent DATABASE_URL_UNPOOLED="$PG_TEST_URL"
.venv/bin/python -m seer_engine migrate
.venv/bin/python -m seer_engine universe refresh            # replaced table with 1544 rows
.venv/bin/python -m seer_engine universe refresh            # unchanged, nothing written
.venv/bin/python -m seer_engine --dry-run universe refresh  # unchanged; rolled back
.venv/bin/python -m seer_engine universe check; echo "exit $?"   # identical x2, exit 0
```
Expected output from the planning run:
```
universe: 1544 intervals, 1265 distinct symbols, 795 since 2015-01-01
universe: current SP500=503 NDX=101 union=518
universe: replaced table with 1544 rows
...
SP500: computed 503, Wikipedia 503 -- identical
NDX: computed 101, Wikipedia 101 -- identical
```
If `universe check` reports drift because Wikipedia changed after 2026-10-03, add the dated rows
to `membership_overrides.csv` (or an alias for a rename) and re-run. That is the workflow
SOURCES.md documents, not a phase failure.

**Exit criteria:**
- `universe refresh` replaces the `universe` table in one transaction and a re-run prints
  `unchanged, nothing written`.
- `--dry-run` leaves the table untouched.
- `universe check` exits 0 on the live pages and 1 on any difference (tested).
- `test_membership.py` covers interval building, overrides and aliases, and passes along with
  the rest of `engine/tests`.

## Handoffs

- **Phase 1 (reconciled, no action left):** the `universe` DDL is unchanged; the `source_symbol`
  comment now documents the `/`-joined form; `http.USER_AGENT = "seer-engine/0.1.0"` is set on the
  shared session (Wikipedia 403s `python-requests`); `db.transaction` is a generator context
  manager, so a `return` inside the block commits (or rolls back under dry-run).
- **Phase 5:** `universe.yml` should run `python -m seer_engine universe refresh` then
  `python -m seer_engine universe check`. Check exits 1 on drift, which is the loud failure
  wanted. The job needs `DATABASE_URL_UNPOOLED` only for refresh; check needs no secret. The
  runbook should copy the SOURCES.md drift procedure: add an override row, re-run refresh, then
  `backfill --symbols <new>`. That last command comes from the analysis's "Settled open
  questions", and phase 3 owns its flag. The live run order must be `migrate` →
  `universe refresh` → `backfill`.
- **Phase 3:** the analysis expects ~650 of the 795 symbols since 2015 to be fetchable via yfinance.
  The rest are delisted or acquired names (survivorship bias) plus any rename this alias file
  misses. yfinance returns no rows for them, so backfill logs them as **`empty`** (not `failed`)
  and a normal backfill still exits 0; `failed` is reserved for rate limits and download errors.
  A missed rename can be fixed later with an alias row, a refresh and `backfill --symbols NEW`.
- **Not done (no phase owns it):** an automated job that re-vendors the upstream CSVs. Quarterly
  re-vendoring is manual (SOURCES.md "Re-vendoring").

## Rollback

`git rm -r engine/data engine/src/seer_engine/membership.py engine/src/seer_engine/commands/universe.py engine/tests/test_membership.py`
(or `git revert` the phase commit). On any database where `universe refresh` ran:
`TRUNCATE universe;`. Phase 1's table and helpers are untouched, so the rest of the tree still
builds and tests green.

# Phase 1: Survivorship-check store: cleaning, build, marker, reports

**Plan set:** `EODHD_SURVIVORSHIP_MARKET_PLAN.md`
**Analysis:** `20261010-181548-E7HD_code_analyzer.md`
**Satisfies:** R1, R2, R3 — a separate, clearly marked dev-window store that adds the dead companies the dev store never served, cleaned honestly, with a cleaning report and a coverage report inside it
**Depends on:** none
**Difficulty:** HARD
**Package:** `engine/src/seer_engine` (`survivorship.py`, `commands/survivorship_store.py`, `research.py`, `lab/runner.py`, `lab/remeasure.py`, `commands/lab.py`)

---

## Goal

After this phase `/home/miftah/seer/engine/.research-sv` exists: the dev store byte for byte plus
cleaned, split-adjusted EODHD bars and dividends for 322 of the 522 members the dev store could not
serve, sealed for the dev window with `"purpose": "survivorship-check"` in its manifest and its own
price fingerprint. Every trial-writing path (`lab run`, `lab test`, `lab remeasure`) refuses a store
carrying that mark before anything is written. `cleaning_report.csv` (all 522 symbols, an action and
a reason each) and `coverage_report.txt` (member-days per year before/after, the members still
missing) sit inside the store, outside the manifest. `engine/.research` is untouched.

**Everything in this plan was built and run before it was written.** The three new files and the
four patches below were applied to a scratch copy of this branch, the full engine suite passed
there (3,663 passed, 411 skipped without Postgres), `ruff check` passed, and the real build ran
twice from the real cache into a scratch directory with identical fingerprints both times. The
numbers in **Measured** are what the executor's build must reproduce exactly.

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.
**Creates:**
- `research.SV_STORE_DIR` (`research.py`, after line 69) = `config.REPO_ROOT / "engine" / ".research-sv"`
- `research.PURPOSE_KEY = "purpose"`, `research.SURVIVORSHIP_PURPOSE = "survivorship-check"`, `research.PURPOSES: frozenset[str]` (`research.py`, before `DEFAULT_BATCH_SIZE`, line 173)
- `research.ResearchData.purpose: str | None = None` (new last field, `research.py:209`)
- `research.declared_purpose(store_dir: Path) -> str | None` and private `research._declared_purpose(path, manifest)` (`research.py`, before `_read_manifest`, line 1208)
- `runner.survivorship_refusal(what: str, purpose: str) -> store.LabError` and `runner.refuse_survivorship_store(data: object, what: str) -> None` (`lab/runner.py`, before `_dsr`, line 260); every refusal message contains the text `lab survivorship`
- new module `seer_engine.survivorship` (`engine/src/seer_engine/survivorship.py`): `SourceSeries`, `RawBar`, `Split`, `RawDividend`, `CleanBar`, `Cleaned`, `YearCoverage`; `read_series(cache, symbol) -> SourceSeries | None`, `parse_bars`, `parse_splits`, `parse_dividend_rows`, `parse_split`, `eodhd_code`, `member_sessions(intervals, symbol, sessions)`, `clean_symbol(series, member_days, sessions) -> Cleaned`, `applied_splits`, `best_of(candidates) -> Cleaned`, `bar_line`, `amount_text`, `report_text`, `merge_sorted_lines`, `coverage_by_year`; constants `EODHD_SOURCE`, the rule thresholds, `KEPT/REPAIRED/TRIMMED/DROPPED/ACTIONS`, `REPORT_HEADER`
- new command `survivorship_store` (`engine/src/seer_engine/commands/survivorship_store.py`): `HELP`, `add_arguments`, `run`, `CACHE_DIR`, `CLEANING_REPORT = "cleaning_report.csv"`, `COVERAGE_REPORT = "coverage_report.txt"`, `REPORT_FILES`, `SurvivorshipStoreError`, `BuildPlan`, `plan_build(source_dir, cache, *, data_dir=None, extra_sources=None) -> BuildPlan`, `write_store(plan, out, cache, *, data_dir=None, extra_reports=None) -> dict`, `cleaning_report(plan) -> str`, `coverage_report(plan) -> str`
- `engine/tests/test_survivorship_store.py` (37 tests)
- `.gitignore`: `engine/.research-sv/`, `engine/.research-sv.tmp/`, `engine/.research-sv.old/`
- data, not code: `/home/miftah/seer/engine/.research-sv/` (gitignored; never committed)

**Signature changes:**
- `research._seal(tmp, counts, *, extra_files=(), window=DEV_WINDOW)` -> `research._seal(tmp, counts, *, extra_files=(), window=DEV_WINDOW, purpose: str | None = None)` (keyword, default keeps every existing caller byte-identical)
- `research._refresh_optional` now passes `purpose=before.get(PURPOSE_KEY)` to `_seal`, so a refreshed survivorship-check store keeps its mark (phase 3's `refresh_market_series` on the SV store relies on this)
- `research._read_manifest` accepts `purpose` beside either existing key set and refuses an unknown value

**Behaviour changes in existing paths (refusals only):** `runner.run_method`, `runner.run_test`,
`remeasure.measure`, `remeasure.remeasure`, `remeasure.remeasure_seed` call
`refuse_survivorship_store` first; `commands/lab.py:_run` refuses a purpose-marked `--store` by its
manifest before discovering the method or loading the store. No ordinary store is affected:
`purpose` is absent from `engine/.research` and from any test store.

**Requires (from earlier phases):** none.

**Seams other phases rely on (exact):**
- Phase 2 (alias fill): passes alias series as `extra_sources: Mapping[str, Sequence[survivorship.SourceSeries]]` (store symbol -> candidate series, `source` e.g. `"eodhd-alias"`, `code` the alias code) to `plan_build`; each candidate goes through the same `clean_symbol`, and `best_of` keeps the one covering the most member days (ties go to the original cache). It writes `alias_report.csv` through `write_store(..., extra_reports={"alias_report.csv": text})` (inside the store, outside the manifest). Phase 2 owns wiring a `--fetch-aliases` flag and alias-file loading into `run()`; `run()` today calls `plan_build` without `extra_sources`.
- Phase 3 (market series): `write_store` copies every name in `research.OPTIONAL_DATA_FILES` that the source manifest lists (except `dividend_announcements.csv`, which it re-matches), so once phase 3 adds `market_series.csv` to that tuple a rebuild carries it with no change here. A `_refresh_optional` on the SV store keeps `purpose`.
- Phase 4 (`lab survivorship`): loads with `research.load_store(research.SV_STORE_DIR)` (default dev window) and requires `data.purpose == research.SURVIVORSHIP_PURPOSE`; may call `research.declared_purpose(path)` for a cheap check. Its own path must not call `runner.refuse_survivorship_store`. The refusal text already names `lab survivorship`.

**Leaves alone (owned by others):** `engine/.research/*` (read only, invariant 1); `eodhd.py`,
`survivorship_alias.py` and the alias wiring of `commands/survivorship_store.py`'s `run()` /
`add_arguments` (phase 2);
`backtest/market.py`, `research.OPTIONAL_DATA_FILES`, `tests/test_market_fundamentals.py` (phase 3);
`commands/lab.py` beyond the `_run` refusal (phase 3 `unblock`, phase 4 `survivorship` and its
docstring line), `lab/survivorship_check.py` (phase 4);
`.claude/skills/*`, `docs/lab/survivorship/` (phase 5).

## Files

| File | Action | What changes |
|---|---|---|
| `.gitignore:29` | modify | three `engine/.research-sv*` entries after `engine/.research-test.old/` (step 1, before anything is built) |
| `engine/src/seer_engine/research.py:69,173,209,793-831,990,1022,1129,1208-1215` | modify | `SV_STORE_DIR`; `PURPOSE_KEY`/`SURVIVORSHIP_PURPOSE`/`PURPOSES`; `ResearchData.purpose`; `_seal(purpose=)`; `_refresh_optional` carries purpose; `load_store` surfaces it; `declared_purpose`; `_read_manifest` accepts and validates it |
| `engine/src/seer_engine/lab/runner.py:260,424,810` | modify | `survivorship_refusal`, `refuse_survivorship_store`; first line of `run_method` and `run_test` |
| `engine/src/seer_engine/lab/remeasure.py:69,437,599,1181` | modify | import; refusal first in `measure`, `remeasure`, `remeasure_seed` |
| `engine/src/seer_engine/commands/lab.py:1259` | modify | `_run` refuses a purpose-marked `--store` by its manifest (message only; nothing else in this file) |
| `engine/src/seer_engine/survivorship.py` | create | the pure cleaning, merge and coverage library (896 lines) |
| `engine/src/seer_engine/commands/survivorship_store.py` | create | the cache-only build command (413 lines) |
| `engine/tests/test_survivorship_store.py` | create | 37 tests, synthetic fixtures only |
| `/home/miftah/seer/engine/.research-sv/` | create (data) | the real store, built in step 9 |

## Design (what the rules are and why — read before the code)

Calibrated with read-only probes over `/home/miftah/seer/engine/.cache/eodhd` and
`/home/miftah/seer/engine/.research` (scripts in `/tmp/claude-1000/svprobe/`, never in the repo).

**EODHD's dividend `value` is split-adjusted.** Of the dev store's 28,206 dividends, 28,008 have an
EODHD row on the same ex-date; `value / store amount` is within 1% for 97.5% of them and within 5%
for 98.0%. The 11 symbols whose median ratio is off by more than 2% (AIV, JEF, DXC, ADSK, JCI, BCO,
SSP, ADP, BUD, TCOM, RYAAY) are spin-off and special-distribution adjustments. So the build uses
`value`, USD only, and refuses a payment above 25% of the prior close (22 refused in the real build).

**EODHD's "raw" prices are not uniformly raw.** For AVP the raw close does not halve on the listed
1998-09-14 2:1 split (27.47 -> 28.13): the earlier rows already carry it. Blindly dividing by every
listed split creates a fake 2x jump (the handover's "exactly 2.0x" cases AVP, BCR, CTX, BRCM, ...).
So each listed split is applied only when the raw close actually fell by about its ratio across its
date (`|ln(q*ratio)| < |ln(q)|`); 256 listed splits applied, 336 skipped in the real build.

**There are systematic vendor scale errors, mostly around mid-December and 2003-09-10.** CERN prints
1993-12-22..1994-12-20 at 15x; EA drops x0.118 on 2003-11-18 on ordinary volume; TIE/WFT/GMCR jump
13x-115x on 2003-09-10. A jump filter alone cannot tell these from collapses, and the handover's
point is that a collapse must stay. The discriminator that works on this data: a real collapse has
**volume behind it** (CVH 2008-10-22 14x the prior median, ENRNQ 2001-11-28 8x, ETFC 2007-11-12 17x)
or it is **terminal** (WAMUQ 2008-09-26 x0.095, three days before it left the index, on low printed
volume). A vendor error has neither.

The eleven rules (constants in `survivorship.py`; the module docstring repeats them):

| # | Rule | Constant(s) | Real-build effect |
|---|---|---|---|
| 1 | remove rows with no positive close, and zero-volume fillers at one price (o=h=l=c); non-positive o/h/l -> close | — | 58,705 fillers among 1,192,432 in-window cached rows |
| 2 | apply a listed split only if the raw close fell by ~its ratio across its date | — | 256 applied / 336 skipped |
| 3 | keep `STORE_START..DEV_END` NYSE sessions only (D9) | — | 6 non-session rows |
| 4 | segment at holes > 10 sessions; keep every segment with a row inside the membership span; cut the rest (reused ticker) | `HOLE_SESSIONS=10` | only 4 symbols have such a hole inside their span (BT, CCE, CTXS, ONE) |
| 5 | end the kept rows 21 sessions after the last member session | `TAIL_GRACE_SESSIONS=21` | — |
| 6 | divide prices / multiply volume by the applied splits dated after the row | — | — |
| 7 | scale break: one-day move within 5% of a simple ratio, open moved the same, persists 5 rows both sides, volume inverse within 3x -> rescale rows before | `SCALE_MIN=1.4`, `SIMPLE_RATIOS`, `CLOSE_TOL=OPEN_TOL=0.05`, `PERSIST_ROWS=5`, `PERSIST_TOL=0.15`, `VOLUME_TOL=3` | 44 repairs in 35 symbols |
| 8 | spike: <= 5 rows beyond 2x that come back within 1.33x -> rows removed | `JUMP=2`, `SPIKE_MAX_ROWS=5`, `SPIKE_BACK=1.33` | — |
| 9 | island: two consecutive >2x moves that cancel within 1.25x, <= 1300 rows apart -> stretch rescaled (equal residual at both edges) | `ISLAND_TOL=1.25`, `ISLAND_MAX_ROWS=1300` | 18 repairs in 14 symbols |
| 10 | remaining >2x moves: genuine if volume surge >= 2x the 20-row median or a fall within 63 sessions of the end -> kept; else suspect: before the span cuts the head, after the span cuts the tail, inside the span rescales the rows before (level repair); > 3 suspects or > 3 genuine inside the span -> dropped | `SURGE_MIN=2`, `SURGE_ROWS=20`, `TERMINAL_SESSIONS=63`, `ABSURD_MAX_MOVES=3` | 17 level repairs in 12 symbols; 31 genuine moves kept in 27 symbols; 1 symbol dropped as absurd (FBF) |
| 11 | 4 dp: close 0.0000 removes the row; o/h/l 0.0000 -> close; high/low widened to contain o and c; wick beyond 3x the body cut | `WICK=3` | 4 values repaired |

Actions: `dropped` > `trimmed` (rows cut for a splice or an unexplained move outside the span) >
`repaired` (anything rescaled or removed) > `kept`.

**What was considered and rejected.** Dropping every symbol with an unexplained move inside its
membership (first prototype) dropped CFC, MRO, EA and GR among 17, losing whole careers of member
days to one vendor error each; the level repair keeps every return but that one day. Treating every
2x move as a split missed the ones whose day also moved 5-10% (BRCM 1999-02-18 at 2.094x); the
per-split raw check fixed those at the source. Name matching against `symbols-US-delisted.json` was
measured and not used as a rule: only 235 of the 522 have a `ticker_cik.csv` name, 173 of those
match a delisted entry, and the 25 mismatches are renames (CTL -> Lumen, KFT, ...), not splices.
Holes and the membership span decide splices instead (rule 4).

## Measured — the real build (scratch run, 2026-10-10, twice, identical)

Command: `survivorship_store --build --source /home/miftah/seer/engine/.research --cache /home/miftah/seer/engine/.cache/eodhd --out <scratch>`; 48 s wall, 1.77 GB peak RSS.

| Manifest key | Value |
|---|---|
| `bar_rows` | 3,356,955 (dev 2,490,793 + 866,162 added) |
| `dividend_rows` | 35,029 (dev 28,206 + 6,823 added) |
| `fx_rows` | 4,300 |
| `symbols_requested` / `symbols_served` | 1,061 / 861 (200 still unserved) |
| `purpose` | `survivorship-check` |
| `fingerprint` | `cce6fd7039ecc243640bebbe9b3134bb7950c27f01874525508ff101e19ff009` |
| price fingerprint | `bc5ba895a719bd805e6260299a696c493ec5124478a76e94fc5b4478423935d2` (dev: `5451195f…`) |
| `files` | bars, dividends, fx, unserved, fundamentals (byte-identical to dev, sha `79c880ec…`), dividend_announcements (25,098 rows: the dev store's 23,355 reproduced exactly, plus 1,743 for added symbols) |

Actions over the 522 cached symbols (`cleaning_report.csv`): **kept 187** (333,602 member-days
covered, 508,966 bars, 3,728 dividends), **repaired 73** (150,840 / 239,765 / 2,222), **trimmed 62**
(92,885 / 117,431 / 873), **dropped 200** — 111 have an EODHD series only after 2015-10-16 (the code
now belongs to another company), 47 never trade inside their membership (reused ticker), 41 have no
EODHD series at all (`null`), 1 absurd (FBF).

Coverage (`coverage_report.txt`; member-days = sessions 1996-01-02..2015-10-16 a symbol was an S&P 500
or Nasdaq-100 member, ETFs excluded; handover §3 measured 58.6% -> 81.8% for "any EODHD row"):

| year | member-days | before | after |
|---|---|---|---|
| 1996 | 123,539 | 39.9% | 46.2% |
| 1997 | 123,372 | 42.1% | 48.2% |
| 1998 | 123,485 | 45.5% | 71.1% |
| 1999 | 123,695 | 47.4% | 74.6% |
| 2000 | 124,001 | 48.8% | 76.7% |
| 2001 | 122,786 | 50.6% | 77.1% |
| 2002 | 124,665 | 52.2% | 79.1% |
| 2003 | 124,487 | 53.9% | 80.6% |
| 2004 | 124,677 | 54.8% | 82.6% |
| 2005 | 124,961 | 55.7% | 83.6% |
| 2006 | 124,746 | 58.4% | 84.7% |
| 2007 | 136,484 | 60.1% | 85.7% |
| 2008 | 137,747 | 62.5% | 87.5% |
| 2009 | 135,625 | 65.4% | 89.4% |
| 2010 | 133,940 | 67.8% | 91.0% |
| 2011 | 133,361 | 68.9% | 90.9% |
| 2012 | 131,629 | 70.7% | 91.9% |
| 2013 | 132,197 | 72.9% | 92.7% |
| 2014 | 131,966 | 74.5% | 93.7% |
| 2015 | 104,913 | 76.2% | 94.0% |
| **all** | **2,542,276** | **58.6%** | **81.3%** |

Members still missing (no bar on any member day): **239, 369,976 member-days** — the 200 still
unserved plus 39 symbols the dev store serves whose yfinance bars never fall on a member day (ACV,
AMH, AR, ASC, ASND, ...: yfinance served a later company under the code). The 39 are reported, not
fixed: the dev store's bars are carried byte for byte (invariant 1's spirit; phase 2's alias work
may revisit them).

The handover §3 named cases:

| symbol | action | covered / member-days | kept span | why |
|---|---|---|---|---|
| AVP | kept | 4332 / 4838 | 1997-12-31..2015-04-21 | 2 listed splits already in the raw prices, not applied; no jump left |
| BCR | repaired | 4478 / 4984 | 1997-12-31..2015-10-16 | unlisted 2:1 at 2003-09-10 rescaled |
| CTX | trimmed | 2926 / 3432 | 1997-12-31..2009-08-18 | 891 rows of a later company cut after a 661-session hole; 2003-09-10 rescaled |
| CVH | kept | 1933 / 1933 | 1997-12-31..2013-05-06 | 2008-10-22 x0.489 kept: a crash (open -36%, 14x volume), not a split |
| CFC | trimmed | 1414 / 2776 | 1999-01-04..2008-07-30 | stale 2000-2002 filler rows removed, 7 spike rows, 2007-01-25..2008-07-29 island rescaled; the 2007-08 fall is inside the island and kept |
| ACS | trimmed | 496 / 1472 | 2004-03-05..2010-03-09 | rows before an 88-session hole and after an 18-session hole cut, 48 spike rows, two islands, one level repair |
| FBF | dropped | 0 / 2077 | — | absurd: 6 unexplained moves inside the membership |
| CBE | repaired | 3061 / 3702 | 1993-01-29..2012-11-30 | 371 spike rows, one island, two level repairs |
| MER | kept | 2768 / 3274 | 1997-12-31..2008-12-31 | clean inside the window (the 2018 reuse is after DEV_END); 1996-97 missing |
| CGP | trimmed | 776 / 1282 | 1997-12-31..2001-01-29 | rows after a 3265-session hole cut |
| FPC | kept | 367 / 367 | 1997-12-31..2000-11-30 | clean |
| IACI | dropped | 0 / 728 | — | series 1998 only; member 2007-2009: another company |
| JH | dropped | 0 / 568 | — | series 1999-2007; member 1996-1998: another company |
| BGEN | trimmed | 952 / 952 | 1997-12-31..2003-11-12 | rows after a 1599-session hole cut |
| ENRNQ | repaired | 984 / 1490 | 1997-12-31..2001-12-31 | 2001-11-28 x0.148 kept (8x volume); 1996-97 missing |
| WAMUQ | trimmed | 2703 / 2829 | 1997-12-31..2008-09-29 | 2008-09-26 x0.0947 kept (terminal); later rows after a hole cut |
| BSC | trimmed | 53 / 2494 | 2008-03-17..2008-05-30 | EODHD starts in the collapse week; rows after a 47-session hole cut |
| CPQ | kept | 837 / 1596 | 1999-01-04..2002-05-03 | EODHD starts 1999 |
| EA | trimmed | 3335 / 3335 | 2000-09-11..2015-10-16 | 2003-11-18 x0.118 on ordinary volume: level repair; head before a 2000-09-11 vendor error cut |
| WCOEQ | dropped | 0 / 1540 | — | EODHD has no series |
| LEH | — | — | — | not in `unserved.csv` (the dev store serves it) |

Smoke check (not a result; phase 4/5 own the measurement and nothing was journaled): M0069's first
variant (M0069-L60-N20) runs end to end on both stores — dev money-weighted 9.01% vs DCA SPY 7.19%,
survivorship store 7.12% vs 7.19%, 885 trades.

## Implementation Steps

### Step 0: Environment (worktree has no venv, store or cache)
**File:** none (shell)
**Change:** create the worktree's own venv with the same Python as the main checkout, read-only
symlinks for the dev store and the cache, and local exclude lines for those symlinks. Never build
into a symlinked path. This is the set's one environment recipe; phases 2-5 repeat it idempotently.
**Code:**
```bash
WT=/home/miftah/.worktrees/seer/eodhd-survivorship-market
cd $WT/engine
[ -x .venv/bin/python ] || { /home/miftah/.pyenv/versions/3.11.0/bin/python -m venv .venv && .venv/bin/pip install -e '.[dev]'; }
.venv/bin/python -c "import seer_engine; print(seer_engine.__file__)"   # must be under $WT/engine/src
[ -e .research ] || ln -s /home/miftah/seer/engine/.research .research   # read only: never written by this phase
[ -e .cache ]    || ln -s /home/miftah/seer/engine/.cache .cache         # read only
# .gitignore's `engine/.research/` and `engine/.cache/` (trailing slash) match directories only; a
# symlink is a file to git, so the links show as untracked unless excluded locally. The worktree's
# exclude file is the one `git rev-parse --git-path info/exclude` names (the shared git dir's).
EXCL=$(git -C $WT rev-parse --git-path info/exclude)
for p in engine/.cache engine/.research; do grep -qxF "$p" "$EXCL" || echo "$p" >> "$EXCL"; done
git -C $WT status --short                                # must not list engine/.cache or engine/.research
.venv/bin/python -m pytest tests -q 2>&1 | tail -1      # baseline: 3626 passed, 411 skipped (no Postgres)
```
**Impact:** none on the repo; the exclude file is untracked. `SEER_LAB_DB` is not set in this phase:
it writes no lab row (Step 10's probe uses a scratch copy of the DB).

### Step 1: Gitignore the store before anything is built
**File:** `.gitignore:29` (after `engine/.research-test.old/`)
**Change:** add the three entries, and — because the real store is built inside the **main
checkout**, whose `.gitignore` does not have them until this branch merges — add the same three
lines to the shared git dir's local exclude file (`/home/miftah/seer/.git/info/exclude`, untracked,
applies to the main checkout and every worktree). The licence is personal and the repo is public:
`engine/.research-sv` must never show up as untracked in the main checkout, where Sera sessions
commit.
**Code:** (`git apply` this, or edit by hand)
```diff
--- a/.gitignore
+++ b/.gitignore
@@ -28,6 +28,12 @@
 engine/.research-test.tmp/
 engine/.research-test.old/
 
+# survivorship-check store (`python -m seer_engine survivorship_store --build`): the dev store plus
+# cleaned EODHD bars for the members it never served. Vendor rows: never commit (personal licence)
+engine/.research-sv/
+engine/.research-sv.tmp/
+engine/.research-sv.old/
+
 # misc
 .DS_Store
 *.log
```
```bash
printf 'engine/.research-sv/\nengine/.research-sv.tmp/\nengine/.research-sv.old/\n' >> /home/miftah/seer/.git/info/exclude
git -C /home/miftah/seer check-ignore -v engine/.research-sv/bars.csv   # must print the exclude line
```
**Impact:** none; ignored paths only.

### Step 2: The `purpose` mark in `research.py`
**File:** `engine/src/seer_engine/research.py` (hunks at lines 69, 173, 209, 796, 813, 826, 987, 1019, 1127, 1205)
**Change:** `SV_STORE_DIR`; `PURPOSE_KEY`, `SURVIVORSHIP_PURPOSE`, `PURPOSES`; `ResearchData.purpose`;
`_seal(..., purpose=None)` validates and writes it; `_refresh_optional` carries it; `load_store`
surfaces it; new `_declared_purpose` / `declared_purpose`; `_read_manifest` subtracts the key before
the key-set check and validates its value. `MANIFEST_KEYS`, `OPTIONAL_MANIFEST_KEYS`,
`OPTIONAL_DATA_FILES` and every message the existing tests match are unchanged.
**Code:** apply exactly (`git apply` from the repo root):
```diff
--- a/engine/src/seer_engine/research.py
+++ b/engine/src/seer_engine/research.py
@@ -67,6 +67,13 @@
 FX_START = date(1999, 1, 4)  # first Frankfurter USD/IDR row (== backtest.dev.FX_START)
 STORE_DIR = config.REPO_ROOT / "engine" / ".research"  # gitignored; the dev window
 TEST_STORE_DIR = config.REPO_ROOT / "engine" / ".research-test"  # gitignored; the P7b test window
+SV_STORE_DIR = config.REPO_ROOT / "engine" / ".research-sv"  # gitignored; the survivorship check
+"""The survivorship-check store: the dev store plus EODHD bars for the members it never served.
+
+Dev window, its own price fingerprint, and ``purpose: "survivorship-check"`` in its manifest
+(:data:`PURPOSE_KEY`), which every trial-writing path refuses. Written only by
+``python -m seer_engine survivorship_store --build``; never by ``build_store``.
+"""
 TEST_WINDOW_START = date(2015, 10, 19)  # the first NYSE session after DEV_END (design S3)
 """The first session the test window TRADES. Not where the test store's data starts.
 
@@ -170,6 +177,21 @@
 keys.
 """
 
+PURPOSE_KEY = "purpose"
+SURVIVORSHIP_PURPOSE = "survivorship-check"
+PURPOSES: frozenset[str] = frozenset({SURVIVORSHIP_PURPOSE})
+"""What a store that is NOT for recording trials says it is for. Absent means an ordinary store.
+
+``purpose`` is optional and sits outside both key sets above on purpose: the dev store's and
+the test store's manifests never carry it, so they stay byte-identical, and :func:`_read_manifest`
+accepts it beside either shape. Its only value today is ``"survivorship-check"``: the store
+``commands/survivorship_store.py`` builds from the dev store plus EODHD bars for the members the
+dev store never served. It loads like a dev store -- same window, same readers -- and that is
+exactly why it needs a mark: ``lab run``, ``lab test`` and ``lab remeasure`` refuse any store
+whose :attr:`ResearchData.purpose` is set, so a survivorship check can never become a trial.
+Like the window keys it is not hashed: ``fingerprint_of`` covers the ``files`` map alone.
+"""
+
 DEFAULT_BATCH_SIZE = 40
 BATCH_PAUSE_S = 3.0
 RATE_LIMIT_BACKOFF_S: tuple[float, ...] = (60.0, 120.0, 240.0)
@@ -207,6 +229,7 @@
     unserved: tuple[str, ...] = ()  # requested members with no bars, sorted
     window: Window = DEV_WINDOW  # the window this store declares; its ``end`` is the D9 bound
     price_fingerprint: str | None = None  # price_fingerprint_of(files): fundamentals excluded
+    purpose: str | None = None  # manifest["purpose"]; None for the dev and test stores
 
 
 @dataclass(frozen=True)
@@ -796,6 +819,7 @@
     *,
     extra_files: Sequence[str] = (),
     window: Window = DEV_WINDOW,
+    purpose: str | None = None,
 ) -> dict[str, Any]:
     """The manifest for the store under ``tmp``, written and returned.
 
@@ -813,7 +837,13 @@
     ``store_start`` is ``STORE_START`` for both windows: it is where the DATA starts, and the
     test store holds the same deep history the dev store does. Only ``window_start`` says where
     scoring begins.
+
+    ``purpose`` is written as :data:`PURPOSE_KEY` only when it is not None, and must then be one
+    of :data:`PURPOSES` (ValueError otherwise, before anything is written). Every caller that
+    predates it passes nothing, so the dev store's and the test store's manifests are unchanged.
     """
+    if purpose is not None and purpose not in PURPOSES:
+        raise ValueError(f"purpose must be one of {sorted(PURPOSES)} or None, got {purpose!r}")
     files = {name: file_sha256(tmp / name) for name in (*DATA_FILES, *extra_files)}
     manifest: dict[str, Any] = {
         "dev_end": DEV_END.isoformat(),
@@ -826,6 +856,8 @@
         manifest[WINDOW_NAME_KEY] = window.name
         manifest[WINDOW_START_KEY] = window.start.isoformat()
         manifest[WINDOW_END_KEY] = window.end.isoformat()
+    if purpose is not None:
+        manifest[PURPOSE_KEY] = purpose
     with (tmp / MANIFEST_FILE).open("w", encoding="utf-8", newline="\n") as fh:
         fh.write(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
     return manifest
@@ -987,7 +1019,9 @@
     Returns ``(manifest before, manifest after)``. The source store is verified with
     ``load_store`` first and refused with ``ResearchStoreError`` when it does not; the other
     optional files the store already holds are carried too, so refreshing one optional file
-    never silently drops another.
+    never silently drops another. A store's :data:`PURPOSE_KEY` is carried the same way: a
+    refreshed survivorship-check store is still marked, and still refused by every
+    trial-writing path.
     """
     if name not in OPTIONAL_DATA_FILES:
         raise ValueError(f"{name} is not one of {list(OPTIONAL_DATA_FILES)}")
@@ -1019,7 +1053,9 @@
                     f"{before['files'][carry]}; the copy is not byte-identical, nothing written"
                 )
         _write_text(tmp / name, header, list(lines))
-        manifest = _seal(tmp, counts, extra_files=extra, window=window)
+        manifest = _seal(
+            tmp, counts, extra_files=extra, window=window, purpose=before.get(PURPOSE_KEY)
+        )
         _swap_in(tmp, store_dir)
     except BaseException:
         shutil.rmtree(tmp, ignore_errors=True)
@@ -1127,6 +1163,7 @@
         unserved=unserved,
         window=window,
         price_fingerprint=price_fingerprint_of(files),
+        purpose=manifest.get(PURPOSE_KEY),
     )
 
 
@@ -1205,14 +1242,40 @@
     return _declared_window(path, manifest)
 
 
+def _declared_purpose(path: Path, manifest: Mapping[str, Any]) -> str | None:
+    """The manifest's :data:`PURPOSE_KEY`, or None when absent; ValueError on an unknown value."""
+    if PURPOSE_KEY not in manifest:
+        return None
+    purpose = manifest[PURPOSE_KEY]
+    if not isinstance(purpose, str) or purpose not in PURPOSES:
+        raise ValueError(
+            f"{path}: {PURPOSE_KEY!r} must be one of {sorted(PURPOSES)} when present, got {purpose!r}"
+        )
+    return purpose
+
+
+def declared_purpose(store_dir: Path) -> str | None:
+    """What the store at ``store_dir`` says it is for: None for an ordinary store.
+
+    Reads the manifest alone and verifies nothing else, like :func:`declared_window`. A caller
+    that must refuse a survivorship-check store before paying for a full ``load_store`` asks
+    here; ``load_store`` itself surfaces the same value as ``ResearchData.purpose``. ValueError
+    when the manifest is missing, unparseable, or names an unknown purpose.
+    """
+    path, manifest = _manifest_json(Path(store_dir))
+    return _declared_purpose(path, manifest)
+
+
 def _read_manifest(store_dir: Path, window: Window = DEV_WINDOW) -> dict[str, Any]:
     path, manifest = _manifest_json(store_dir)
-    keys = set(manifest)
+    keys = set(manifest) - {PURPOSE_KEY}
     if keys != MANIFEST_KEYS and keys != MANIFEST_KEYS | OPTIONAL_MANIFEST_KEYS:
         raise ValueError(
             f"{path}: expected keys {sorted(MANIFEST_KEYS)}, optionally also "
-            f"{sorted(OPTIONAL_MANIFEST_KEYS)} (all three or none), got {sorted(keys)}"
+            f"{sorted(OPTIONAL_MANIFEST_KEYS)} (all three or none) and {PURPOSE_KEY!r}, "
+            f"got {sorted(set(manifest))}"
         )
+    _declared_purpose(path, manifest)
     if manifest["dev_end"] != DEV_END.isoformat():
         raise ValueError(
             f"{path}: the store was built for dev_end {manifest['dev_end']!r}; this code expects "
```
**Impact:** the dev and test stores load exactly as before (no `purpose` key; `ResearchData.purpose`
is None). A manifest with an unknown purpose, or a non-string one, is refused.

### Step 3: Refusals in the trial-writing paths
**File:** `engine/src/seer_engine/lab/runner.py:260` (new helpers before `_dsr`), `:424` (`run_method`), `:810` (`run_test`)
**Change:** one helper builds the refusal; `run_method` and `run_test` call it before anything else.
**Code:**
```diff
--- a/engine/src/seer_engine/lab/runner.py
+++ b/engine/src/seer_engine/lab/runner.py
@@ -257,6 +257,30 @@
     )
 
 
+def survivorship_refusal(what: str, purpose: str) -> store.LabError:
+    """The one refusal every trial-writing path gives a purpose-marked store (``research.PURPOSE_KEY``)."""
+    return store.LabError(
+        f"{what}: this research store is marked {purpose!r} in its manifest. It is the dev store "
+        "plus EODHD bars for the members the dev store never served, built to measure how much "
+        "the missing delisted companies flatter recorded results, and nothing measured on it is "
+        "ever recorded as a trial, a moment or a look -- its prices are not the ones every "
+        "recorded trial was compared on. Use `lab survivorship` to set a method's dev result "
+        "beside its result on this store; point --store at the dev store for anything that "
+        "records. Nothing ran and nothing was written"
+    )
+
+
+def refuse_survivorship_store(data: object, what: str) -> None:
+    """Raise :func:`survivorship_refusal` when ``data`` (a ``ResearchData``) carries a purpose.
+
+    ``getattr`` rather than the attribute: a hand-built fixture without the field is an
+    ordinary store, exactly as ``ResearchData.purpose``'s default None says.
+    """
+    purpose = getattr(data, "purpose", None)
+    if purpose is not None:
+        raise survivorship_refusal(what, str(purpose))
+
+
 def _dsr(row: DevRow, n_trials: int, var_trials: float | None) -> float | None:
     m = daily_moments(row.stats.daily_returns)
     if m is None or var_trials is None:
@@ -420,7 +444,11 @@
     with ``data.price_fingerprint``, in the transaction that inserts the trial. So the record can
     never name a capital the run was not given, and a later ``lab remeasure`` re-runs it at the
     capital it actually had, whatever ``INITIAL_IDR`` reads by then.
+
+    A survivorship-check store (``data.purpose`` set) is refused first, before the preflight and
+    before any backtest, so it can never produce a trial.
     """
+    refuse_survivorship_store(data, f"lab run {method.id}")
     preflight(conn, method, path, require_commit=require_commit)
     capital = INITIAL_IDR
     results: list[tuple[DevRow, Any]] = []
@@ -806,7 +834,10 @@
     still the first write inside the one ``BEGIN IMMEDIATE``, every refusal is the same refusal in
     the same order, and the funding row is written inside that transaction -- so the look and its
     record land together or not at all, exactly as the trial and the status move already did.
+
+    A survivorship-check store (``data.purpose`` set) is refused before everything else.
     """
+    refuse_survivorship_store(data, f"lab test {candidate.id}")
     window = data.window
     if window.name != "test":
         raise store.LabError(
```
**File:** `engine/src/seer_engine/lab/remeasure.py:69` (import), `:437` (`measure`), `:599` (`remeasure`), `:1181` (`remeasure_seed`)
**Code:**
```diff
--- a/engine/src/seer_engine/lab/remeasure.py
+++ b/engine/src/seer_engine/lab/remeasure.py
@@ -66,7 +66,7 @@
 from seer_engine.commands.backtest_dev import daily_moments, registry_problem
 from seer_engine.lab import npolicy, store
 from seer_engine.lab.method import METHOD_ID, Method, config_digest, source_sha
-from seer_engine.lab.runner import recorded_capital
+from seer_engine.lab.runner import recorded_capital, refuse_survivorship_store
 from seer_engine.sim.contributions import OWNER_MONTHLY
 
 log = logging.getLogger(__name__)
@@ -434,6 +434,7 @@
     miss their recorded Sharpe by 9.5e-4 .. 5.2e-2 against ``SHARPE_TOL``; at their recorded
     20,000,000 IDR every variant reproduces with delta 0.000e+00.
     """
+    refuse_survivorship_store(data, f"lab remeasure {method.id}")
     if data.window != research.DEV_WINDOW:
         w = data.window
         raise store.LabError(
@@ -595,7 +596,10 @@
     inside one ``BEGIN IMMEDIATE``, after both checks have passed for every trial. ``preflight``
     runs again inside the lock because a parallel explorer session may have backfilled the same
     method in between -- the same race ``runner.run_method`` guards.
+
+    A survivorship-check store (``data.purpose`` set) is refused before anything is read.
     """
+    refuse_survivorship_store(data, f"lab remeasure {method.id}")
     plan = preflight(conn, method, path, require_commit=require_commit)
     if plan.nothing_to_do:
         return Report(method_id=method.id, measured=(), written=(), skipped=plan.present)
@@ -1177,7 +1181,9 @@
 
     ``on_chunk(index, total, written, blocked)``, when given, is called after each chunk commits;
     ``commands/lab.py`` uses it to print progress on a job that has no other output until the end.
+    A survivorship-check store (``data.purpose`` set) is refused before anything else.
     """
+    refuse_survivorship_store(data, "lab remeasure (seed trials)")
     if data.window != research.DEV_WINDOW:
         w = data.window
         raise store.LabError(
```
**File:** `engine/src/seer_engine/commands/lab.py:1259` (`_run`, before `methods = discover()`) — the only edit to this file
**Code:**
```diff
--- a/engine/src/seer_engine/commands/lab.py
+++ b/engine/src/seer_engine/commands/lab.py
@@ -1256,6 +1256,14 @@
     from seer_engine.lab import hardgate, runner
     from seer_engine.lab.method import discover
 
+    # A survivorship-check store says so in its manifest; refuse it before discovering the method
+    # or paying for a full load. runner.run_method refuses it again on the loaded data.
+    try:
+        purpose = research.declared_purpose(Path(args.store))
+    except ValueError:
+        purpose = None  # missing or unreadable: research.load_store below names the problem
+    if purpose is not None:
+        raise runner.survivorship_refusal(f"lab run {args.method}", purpose)
     methods = discover()
     if args.method not in methods:
         raise store.LabError(f"no method file for {args.method} in seer_engine/lab/methods/")
```
**Impact:** a purpose-marked store is refused with exit 2 (`store.LabError`) before any preflight,
backtest or insert; N and test looks cannot move. `getattr` keeps `labkit` fixtures without the
field working. No existing test changes.

### Step 4: The cleaning library
**File:** `engine/src/seer_engine/survivorship.py` (create)
**Change:** the whole module below. Pure apart from `read_series` (reads three cached JSON files).
`clean_symbol` never raises on vendor data; every outcome is a `Cleaned` with an action and a
comma-free reason.
**Code:**
```python
"""The survivorship-check store's cleaning: EODHD series for the members the dev store never served.

Pure, apart from :func:`read_series`, which reads one symbol's cached EODHD answers (``eod/``,
``splits/`` and ``dividends/`` under ``engine/.cache/eodhd``) and nothing else -- no network, no
store, no database. ``commands/survivorship_store.py`` is the impure edge that writes the store.

**Why it exists.** ``engine/.research`` holds bars for 539 of the 1061 symbols it requested; the
other 522 are mostly companies that died (bankruptcies, buyouts, renamed tickers). Every lab
result was measured without them. The paid EODHD month downloaded their raw daily history, and
this module turns it into bars in the dev store's own conventions -- split-adjusted, not
dividend-adjusted, 4 dp, integer volume -- so a second, clearly marked store can say how much
the gap flattered the lab.

**The rules, in the order they run** (the constants below; each was calibrated on the real cache
on 2026-10-10 and the phase-1 plan records the measured counts):

1. *Invalid rows.* A close that is missing or not positive removes the row, and so does a
   zero-volume row whose open, high, low and close are one number: a filler carrying the last
   price forward, not a trade (58,705 of the 1,192,432 cached rows inside the dev window; CFC
   prints 60.00 for weeks in 2000). A missing or non-positive open, high or low becomes the close.
2. *Listed splits, checked one by one.* EODHD's "raw" prices are sometimes already adjusted for
   a split it lists (AVP 1998-09-14, BRCM 1999-02-18). A listed split is applied only when the
   raw close actually fell by about its ratio across its date -- when ``|ln(q * ratio)|`` is
   smaller than ``|ln(q)|`` for the raw one-day ratio ``q`` -- and skipped when the raw prices
   already carry it, or when no raw row lies on both sides of it. Decided on the whole raw
   series, so a split after 2015 is checked against the rows around it.
3. *Window.* Rows outside ``STORE_START..DEV_END`` and rows on a day that is not an NYSE
   session are dropped (D9: the dev store never holds a row after 2015-10-16).
4. *Splices (reused tickers).* The series is cut into segments at every hole of more than
   :data:`HOLE_SESSIONS` NYSE sessions. Every segment with a row inside the membership span
   (first to last member session) is the member company -- a ticker cannot be reused while its
   company is in the index -- and is kept, holes and all. A segment wholly outside that span
   sits across a long hole and may be another company under the same code (CTX after 2012, BSC
   after 2008-05, CGP, BGEN): it is cut and the symbol reads ``trimmed``. A symbol with no
   segment inside its span (IACI, JH) is ``dropped``.
5. *Tail.* The kept rows end :data:`TAIL_GRACE_SESSIONS` sessions after the last member
   session, so a book holding a company that leaves the index still exits at a real price, and
   a code reused later without a hole cannot leak in.
6. *Split adjustment.* Prices are divided, and volume multiplied, by the product of the applied
   splits dated after the row.
7. *Scale breaks.* A one-day move within :data:`CLOSE_TOL` of a simple ratio, whose open moved by
   the same ratio (:data:`OPEN_TOL`), that persists :data:`PERSIST_ROWS` rows on both sides and
   whose volume moved inversely (:data:`VOLUME_TOL`) is a split EODHD neither lists nor applied
   correctly (BCR 2003-09-10): the rows before it are rescaled. A crash fails the open test --
   CVH 2008-10-22 opened 36% down and closed 51% down -- so it is never "repaired" away.
8. *Spikes.* A run of at most :data:`SPIKE_MAX_ROWS` rows that moves beyond :data:`JUMP` from the
   last good close and comes back within :data:`SPIKE_BACK` of it is a data error (CFC's
   alternating 1/12-scale rows): the rows are removed.
9. *Islands.* Two consecutive persistent moves beyond :data:`JUMP` whose ratios cancel to within
   :data:`ISLAND_TOL`, at most :data:`ISLAND_MAX_ROWS` rows apart, bracket a stretch the vendor
   printed at the wrong scale (CERN 1993-12-22..1994-12-21 at 15x): the stretch is rescaled
   so both edges carry the same small residual move.
10. *What is left.* Each remaining move beyond :data:`JUMP` is **genuine** when the volume on
   its day or the next is at least :data:`SURGE_MIN` times the median of the
   :data:`SURGE_ROWS` rows before, or when it is a fall within :data:`TERMINAL_SESSIONS` sessions
   of the end of the membership or of the series -- that is what a collapse looks like (ENRNQ
   2001-11-28, WAMUQ 2008-09-26, CVH 2008-10-22), and it stays: dropping it would bring
   survivorship bias back by the side door. Any other such move is **suspect** (no volume
   behind it: a vendor level error, EA 2003-11-18 x0.118). A suspect move before the membership
   span cuts the rows before it; one after the span cuts the rows from it on; one inside the
   span is repaired by rescaling every row before it by the move, so the later prices stand as
   printed and no return but that one day's changes. More than :data:`ABSURD_MAX_MOVES` suspect
   moves inside the span, or more than that many genuine ones, drops the symbol: that is not a
   company's price history (FBF).
11. *Bars the loader would refuse.* After rounding to 4 dp a close of 0.0000 removes the row; an
   open, high or low of 0.0000 becomes the close; high and low are widened to contain open and
   close, and a wick beyond :data:`WICK` times the body is cut back to the body.

Dividends come from ``dividends/<SYM>.json``'s ``value`` -- EODHD's split-adjusted amount: on the
28,008 dev-store dividends with a same-day EODHD row, 97.5% agree within 1% -- USD only, clipped
to the kept bars, refused when one payment exceeds :data:`MAX_DIVIDEND_YIELD` of the prior close.

**The seam for a second source** (phase 2's alias fill): :class:`SourceSeries` is source-agnostic,
:func:`clean_symbol` takes one, and :func:`best_of` picks among several cleaned candidates for one
symbol the one covering the most member days.
"""

from __future__ import annotations

import json
import math
import statistics
from bisect import bisect_left
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

import numpy as np

from seer_engine import research
from seer_engine.bars import to_volume
from seer_engine.prices import to_decimal
from seer_engine.yahoo import DIVIDEND_QUANTUM

EODHD_SOURCE = "eodhd"

HOLE_SESSIONS = 10
TAIL_GRACE_SESSIONS = 21
JUMP = 2.0
SCALE_MIN = 1.4
SIMPLE_RATIOS: tuple[float, ...] = (1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 20.0)
CLOSE_TOL = 0.05
OPEN_TOL = 0.05
PERSIST_ROWS = 5
PERSIST_TOL = 0.15
VOLUME_TOL = 3.0
SPIKE_MAX_ROWS = 5
SPIKE_BACK = 1.33
ISLAND_TOL = 1.25
ISLAND_MAX_ROWS = 1300
SURGE_MIN = 2.0
SURGE_ROWS = 20
TERMINAL_SESSIONS = 63
ABSURD_MAX_MOVES = 3
WICK = Decimal(3)
MAX_DIVIDEND_YIELD = Decimal("0.25")

KEPT = "kept"
REPAIRED = "repaired"
TRIMMED = "trimmed"
DROPPED = "dropped"
ACTIONS: tuple[str, ...] = (KEPT, REPAIRED, TRIMMED, DROPPED)

ZERO_PRICE = Decimal("0.0000")
REPORT_HEADER = (
    "symbol,source,code,action,member_days,covered_days,first,last,rows,raw_rows,"
    "splits_applied,splits_skipped,scale_repairs,island_repairs,level_repairs,rows_removed,fields_repaired,"
    "moves_kept,dividends,dividends_refused,reason"
)


# ---- value types ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RawBar:
    """One vendor row, raw (not split-adjusted). Any price may be None or non-positive."""

    date: date
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    volume: float | None


@dataclass(frozen=True)
class Split:
    """A listed split: ``ratio`` new shares per old (2.0 for 2-for-1, 0.1 for 1-for-10)."""

    date: date
    ratio: float


@dataclass(frozen=True)
class RawDividend:
    ex_date: date
    value: Decimal | None  # split-adjusted, as the vendor reports it
    currency: str | None


@dataclass(frozen=True)
class SourceSeries:
    """Everything one source knows about one store symbol. Source-agnostic on purpose."""

    symbol: str  # the store's symbol (``BRK.B``), never the vendor's code
    source: str  # ``eodhd``; phase 2 adds its alias source
    code: str  # the vendor code the rows were fetched under (``BRK-B.US``)
    bars: tuple[RawBar, ...]
    splits: tuple[Split, ...] = ()
    dividends: tuple[RawDividend, ...] = ()


@dataclass(frozen=True)
class CleanBar:
    date: date
    open: Decimal  # 4 dp
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int


@dataclass(frozen=True)
class Cleaned:
    """One symbol after cleaning: what goes into the store and what the report says about it."""

    symbol: str
    source: str
    code: str
    action: str  # one of ACTIONS
    reason: str  # plain words, never empty, no commas
    member_days: int = 0
    raw_rows: int = 0
    bars: tuple[CleanBar, ...] = ()
    dividends: tuple[tuple[date, Decimal], ...] = ()
    covered_days: int = 0
    splits_applied: int = 0
    splits_skipped: int = 0
    scale_repairs: int = 0
    island_repairs: int = 0
    level_repairs: int = 0
    rows_removed: int = 0
    fields_repaired: int = 0
    moves_kept: int = 0
    dividends_refused: int = 0

    @property
    def first(self) -> date | None:
        return self.bars[0].date if self.bars else None

    @property
    def last(self) -> date | None:
        return self.bars[-1].date if self.bars else None

    def report_line(self) -> str:
        """This symbol's ``cleaning_report.csv`` row (:data:`REPORT_HEADER` order)."""
        cells = (
            self.symbol, self.source, self.code, self.action, self.member_days,
            self.covered_days, self.first or "", self.last or "", len(self.bars), self.raw_rows,
            self.splits_applied, self.splits_skipped, self.scale_repairs, self.island_repairs,
            self.level_repairs,
            self.rows_removed, self.fields_repaired, self.moves_kept, len(self.dividends),
            self.dividends_refused, report_text(self.reason),
        )
        return ",".join(str(c) for c in cells)


@dataclass(frozen=True)
class YearCoverage:
    """Member-days in one calendar year, and how many of them have a bar before and after."""

    year: int
    member_days: int
    before: int
    after: int


# ---- reading the cache ---------------------------------------------------------------------


def parse_split(text: object) -> float:
    """``"2.000000/1.000000"`` -> 2.0 (new shares per old). ValueError on anything else."""
    new, sep, old = str(text).partition("/")
    try:
        ratio = float(new) / float(old) if sep else float("nan")
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError(f"not a split ratio: {text!r}") from exc
    if not math.isfinite(ratio) or ratio <= 0:
        raise ValueError(f"not a split ratio: {text!r}")
    return ratio


def _number(raw: object) -> float | None:
    if raw is None or isinstance(raw, bool):
        return None
    try:
        value = float(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _decimal(raw: object) -> Decimal | None:
    if raw is None or isinstance(raw, bool):
        return None
    try:
        value = Decimal(str(raw))
    except InvalidOperation:
        return None
    return value if value.is_finite() else None


def _day(raw: object) -> date | None:
    try:
        return date.fromisoformat(str(raw)[:10])
    except ValueError:
        return None


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def parse_bars(rows: object) -> tuple[RawBar, ...]:
    """EODHD ``/eod`` JSON (a list of dicts, or None) as RawBars, ascending, one per date."""
    if not isinstance(rows, list):
        return ()
    by_date: dict[date, RawBar] = {}
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        d = _day(raw.get("date"))
        if d is None:
            continue
        by_date[d] = RawBar(
            date=d,
            open=_number(raw.get("open")),
            high=_number(raw.get("high")),
            low=_number(raw.get("low")),
            close=_number(raw.get("close")),
            volume=_number(raw.get("volume")),
        )
    return tuple(by_date[d] for d in sorted(by_date))


def parse_splits(rows: object) -> tuple[Split, ...]:
    """EODHD ``/splits`` JSON (a list, or None) as Splits, ascending; unparsable rows skipped."""
    if not isinstance(rows, list):
        return ()
    out: list[Split] = []
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        d = _day(raw.get("date"))
        try:
            ratio = parse_split(raw.get("split", ""))
        except ValueError:
            continue
        if d is not None:
            out.append(Split(d, ratio))
    return tuple(sorted(out, key=lambda s: s.date))


def parse_dividend_rows(rows: object) -> tuple[RawDividend, ...]:
    """The ``rows`` of a cached ``dividends/<SYM>.json`` as RawDividends, ascending."""
    if not isinstance(rows, list):
        return ()
    out: list[RawDividend] = []
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        d = _day(raw.get("date"))
        if d is None:
            continue
        currency = raw.get("currency")
        out.append(RawDividend(d, _decimal(raw.get("value")), currency if isinstance(currency, str) else None))
    return tuple(sorted(out, key=lambda r: r.ex_date))


def eodhd_code(symbol: str) -> str:
    """The store symbol in EODHD form (``BRK.B`` -> ``BRK-B.US``); same rule as ``eodhd.ticker``."""
    return symbol.strip().upper().replace(".", "-") + ".US"


def read_series(cache: Path, symbol: str) -> SourceSeries | None:
    """The cached EODHD answers for ``symbol``; None when ``eod/<symbol>.json`` was never fetched.

    A fetched-but-404 symbol (its file holds ``null``) is a SourceSeries with no bars, so the
    report can say "EODHD has no series" rather than "never fetched".
    """
    cache = Path(cache)
    eod_path = cache / "eod" / f"{symbol}.json"
    if not eod_path.is_file():
        return None
    div_doc = _load_json(cache / "dividends" / f"{symbol}.json")
    return SourceSeries(
        symbol=symbol,
        source=EODHD_SOURCE,
        code=eodhd_code(symbol),
        bars=parse_bars(_load_json(eod_path)),
        splits=parse_splits(_load_json(cache / "splits" / f"{symbol}.json")),
        dividends=parse_dividend_rows(div_doc.get("rows") if isinstance(div_doc, dict) else None),
    )


# ---- membership and sessions ---------------------------------------------------------------


def member_sessions(
    intervals: Iterable[tuple[str, date, date | None]], symbol: str, sessions: Sequence[date]
) -> tuple[date, ...]:
    """The sessions in ``sessions`` on which ``symbol`` is a member: ``start <= d < end``."""
    days: set[date] = set()
    for s, start, end in intervals:
        if s != symbol:
            continue
        lo = bisect_left(sessions, start)
        hi = len(sessions) if end is None else bisect_left(sessions, end)
        days.update(sessions[lo:hi])
    return tuple(sorted(days))


# ---- cleaning ------------------------------------------------------------------------------


def report_text(reason: str) -> str:
    """A report cell: no commas (the report CSVs are unquoted), never empty."""
    return reason.replace(",", ";").replace("\n", " ").strip() or "-"


def _near(q: float, k: float, tol: float) -> bool:
    return abs(q / k - 1.0) <= tol


def _simple_ratio(q: float) -> float | None:
    """The simple ratio (or its inverse) within CLOSE_TOL of ``q``, else None."""
    for k in SIMPLE_RATIOS:
        for r in (k, 1.0 / k):
            if _near(q, r, CLOSE_TOL):
                return r
    return None


@dataclass
class _Rows:
    """Mutable working columns for one symbol: floats, volume included, until rounding."""

    dates: list[date]
    o: list[float]
    h: list[float]
    lo: list[float]
    c: list[float]
    v: list[float]

    def take(self, keep: Iterable[int]) -> None:
        keep = list(keep)
        for name in ("dates", "o", "h", "lo", "c", "v"):
            column = getattr(self, name)
            setattr(self, name, [column[i] for i in keep])

    def scale(self, lo: int, hi: int, price: float, volume: float = 1.0) -> None:
        """Multiply prices of rows ``lo..hi-1`` by ``price`` and their volume by ``volume``."""
        for j in range(lo, hi):
            self.o[j] *= price
            self.h[j] *= price
            self.lo[j] *= price
            self.c[j] *= price
            self.v[j] *= volume

    def __len__(self) -> int:
        return len(self.dates)


def _invalid(b: RawBar) -> bool:
    """Rule 1's removals: no positive close, or a zero-volume filler at one price."""
    if b.close is None or b.close <= 0:
        return True
    return not b.volume and b.open == b.high == b.low == b.close


def _valid_rows(bars: Sequence[RawBar]) -> tuple[_Rows, int]:
    """Rule 1: (the rows that are not :func:`_invalid`, open/high/low values repaired)."""
    rows = _Rows([], [], [], [], [], [])
    repaired = 0
    for b in bars:
        if _invalid(b):
            continue
        parts = (b.open, b.high, b.low)
        fixed = [x if x is not None and x > 0 else b.close for x in parts]
        repaired += sum(1 for x in parts if x is None or x <= 0)
        rows.dates.append(b.date)
        rows.o.append(fixed[0])
        rows.h.append(fixed[1])
        rows.lo.append(fixed[2])
        rows.c.append(b.close)
        rows.v.append(b.volume if b.volume is not None and b.volume > 0 else 0.0)
    return rows, repaired


def applied_splits(rows: _Rows, splits: Sequence[Split]) -> tuple[tuple[Split, ...], tuple[Split, ...]]:
    """Rule 2: (splits to apply, splits skipped), judged on the raw closes around each date."""
    applied: list[Split] = []
    skipped: list[Split] = []
    for s in splits:
        j = bisect_left(rows.dates, s.date)
        if j == 0 or j >= len(rows):
            skipped.append(s)
            continue
        q = rows.c[j] / rows.c[j - 1]
        (applied if abs(math.log(q * s.ratio)) < abs(math.log(q)) else skipped).append(s)
    return tuple(applied), tuple(skipped)


def _scale_break(rows: _Rows, i: int) -> float | None:
    """Rule 7: the factor to rescale the rows before ``i`` by, or None."""
    prev, cur = rows.c[i - 1], rows.c[i]
    q = cur / prev
    if max(q, 1.0 / q) < SCALE_MIN:
        return None
    k = _simple_ratio(q)
    if k is None or not _near(rows.o[i] / prev, k, OPEN_TOL):
        return None
    if i < PERSIST_ROWS or i + PERSIST_ROWS > len(rows):
        return None
    if not _near(statistics.median(rows.c[i - PERSIST_ROWS : i]), prev, PERSIST_TOL):
        return None
    if not _near(statistics.median(rows.c[i : i + PERSIST_ROWS]), cur, PERSIST_TOL):
        return None
    vb = statistics.median(rows.v[i - PERSIST_ROWS : i])
    va = statistics.median(rows.v[i : i + PERSIST_ROWS])
    if vb > 0 and va > 0 and not 1.0 / VOLUME_TOL <= (va / vb) * k <= VOLUME_TOL:
        return None
    return k


def _surge(rows: _Rows, i: int) -> float:
    """Volume on day ``i`` (or the next) over the median of the SURGE_ROWS rows before; 0 if unknown."""
    before = [v for v in rows.v[max(0, i - SURGE_ROWS) : i] if v > 0]
    if not before:
        return 0.0
    day = max(rows.v[i], rows.v[i + 1] if i + 1 < len(rows) else 0.0)
    return day / statistics.median(before)


def _moves(rows: _Rows) -> list[tuple[int, float]]:
    """Every (row, ratio) whose close moved beyond JUMP from the row before."""
    out = []
    for i in range(1, len(rows)):
        q = rows.c[i] / rows.c[i - 1]
        if max(q, 1.0 / q) > JUMP:
            out.append((i, q))
    return out


def clean_symbol(
    series: SourceSeries,
    member_days: Sequence[date],
    sessions: Sequence[date],
) -> Cleaned:
    """Clean one symbol's series against its membership (the module docstring's rules, in order).

    ``member_days`` are the dev-window sessions the symbol was an index member, ascending;
    ``sessions`` are every NYSE session ``STORE_START..DEV_END``, ascending. Never raises on bad
    vendor data: every outcome is a :class:`Cleaned` with an action and a reason.
    """
    head = dict(
        symbol=series.symbol, source=series.source, code=series.code,
        member_days=len(member_days), raw_rows=len(series.bars),
    )
    src = series.source
    if not member_days:
        return Cleaned(**head, action=DROPPED, reason="never an index member in the dev window")
    if not series.bars:
        return Cleaned(**head, action=DROPPED, reason=f"{src} has no daily series for {series.code}")
    index = {d: i for i, d in enumerate(sessions)}
    notes: list[str] = []

    # 1. invalid rows; 2. which listed splits the raw prices still need
    rows, fields = _valid_rows(series.bars)
    removed = sum(
        1 for b in series.bars
        if _invalid(b) and research.STORE_START <= b.date <= research.DEV_END
    )
    if not rows:
        return Cleaned(**head, action=DROPPED, reason=f"no {src} row has a positive close")
    use, skip = applied_splits(rows, series.splits)
    if skip:
        notes.append(f"{len(skip)} listed splits not applied (already in the raw prices or outside the series)")

    # 3. window and sessions
    raw_first, raw_last = rows.dates[0], rows.dates[-1]
    keep = [i for i, d in enumerate(rows.dates) if d in index]
    removed += sum(1 for d in rows.dates if research.STORE_START <= d <= research.DEV_END and d not in index)
    rows.take(keep)
    if not rows:
        return Cleaned(
            **head, action=DROPPED,
            reason=(
                f"{src} series {raw_first}..{raw_last} has no session inside "
                f"{research.STORE_START}..{research.DEV_END}"
            ),
        )

    # 4. splices
    m_first, m_last = member_days[0], member_days[-1]
    cuts = [0] + [
        i for i in range(1, len(rows))
        if index[rows.dates[i]] - index[rows.dates[i - 1]] - 1 > HOLE_SESSIONS
    ] + [len(rows)]
    touching = [
        (a, b) for a, b in zip(cuts[:-1], cuts[1:])
        if any(m_first <= rows.dates[j] <= m_last for j in range(a, b))
    ]
    if not touching:
        return Cleaned(
            **head, action=DROPPED,
            reason=(
                f"{src} series {rows.dates[0]}..{rows.dates[-1]} never trades inside the membership "
                f"{m_first}..{m_last}: another company under the same ticker"
            ),
        )
    lo_i, hi_i = touching[0][0], touching[-1][1]
    trimmed = False
    if lo_i > 0:
        trimmed = True
        notes.append(
            f"cut {lo_i} rows {rows.dates[0]}..{rows.dates[lo_i - 1]} across a hole of "
            f"{index[rows.dates[lo_i]] - index[rows.dates[lo_i - 1]] - 1} sessions before the membership"
        )
    if hi_i < len(rows):
        trimmed = True
        notes.append(
            f"cut {len(rows) - hi_i} rows {rows.dates[hi_i]}..{rows.dates[-1]} across a hole of "
            f"{index[rows.dates[hi_i]] - index[rows.dates[hi_i - 1]] - 1} sessions after the membership"
        )
    rows.take(range(lo_i, hi_i))

    # 5. tail
    tail_end = sessions[min(index[m_last] + TAIL_GRACE_SESSIONS, len(sessions) - 1)]
    rows.take(i for i, d in enumerate(rows.dates) if d <= tail_end)

    # 6. split adjustment
    for i, d in enumerate(rows.dates):
        f = math.prod(s.ratio for s in use if s.date > d)
        if f != 1.0:
            rows.scale(i, i + 1, 1.0 / f, f)

    # 7. scale breaks, latest first: rescaling the rows before i never changes an earlier ratio
    breaks = 0
    for i in range(len(rows) - 1, 0, -1):
        k = _scale_break(rows, i)
        if k is not None:
            rows.scale(0, i, k, 1.0 / k)
            breaks += 1
            notes.append(f"rescaled rows before {rows.dates[i]} by {k:g} (a split nobody applied)")

    # 8. spikes
    kept_rows = [0]
    spikes = 0
    i = 1
    while i < len(rows):
        g = kept_rows[-1]
        q = rows.c[i] / rows.c[g]
        if max(q, 1.0 / q) > JUMP:
            back = next(
                (j for j in range(i + 1, min(i + 1 + SPIKE_MAX_ROWS, len(rows)))
                 if 1.0 / SPIKE_BACK <= rows.c[j] / rows.c[g] <= SPIKE_BACK),
                None,
            )
            if back is not None:
                spikes += back - i
                i = back
                continue
        kept_rows.append(i)
        i += 1
    if spikes:
        notes.append(f"removed {spikes} spike rows that came straight back")
        removed += spikes
        rows.take(kept_rows)

    # 9. islands
    islands = 0
    changed = True
    while changed:
        changed = False
        moves = _moves(rows)
        for (a, qa), (b, qb) in zip(moves, moves[1:]):
            if b - a <= ISLAND_MAX_ROWS and abs(math.log(qa * qb)) <= math.log(ISLAND_TOL):
                f = math.sqrt(qb / qa)
                rows.scale(a, b, f)
                islands += 1
                notes.append(f"rescaled the stretch {rows.dates[a]}..{rows.dates[b - 1]} by {f:.4g} (printed at the wrong scale)")
                changed = True
                break

    # 10. what is left
    suspects: list[tuple[int, float]] = []
    genuine: list[tuple[int, float]] = []
    for i, q in _moves(rows):
        d = rows.dates[i]
        terminal = q < 1.0 and (
            index[m_last] - index[d] <= TERMINAL_SESSIONS or len(rows) - 1 - i <= TERMINAL_SESSIONS
        )
        (genuine if terminal or _surge(rows, i) >= SURGE_MIN else suspects).append((i, q))
    inside = [(i, q) for i, q in suspects if m_first <= rows.dates[i] <= m_last]
    if len(inside) > ABSURD_MAX_MOVES:
        listed = "; ".join(f"{rows.dates[i]} x{q:.3g}" for i, q in inside[:3])
        return Cleaned(
            **head, action=DROPPED,
            reason=(
                f"absurd: {len(inside)} one-day moves beyond {JUMP:g}x with no volume behind them "
                f"inside the membership (first {listed})"
            ),
            scale_repairs=breaks, island_repairs=islands, rows_removed=removed,
        )
    for i, q in sorted(inside, reverse=True):
        rows.scale(0, i, q)
        notes.append(
            f"rescaled rows before {rows.dates[i]} by {q:.4g}: a x{q:.3g} move with no volume behind it "
            "inside the membership (a vendor level error; the later prices are kept as printed)"
        )
    levels = len(inside)
    before = [i for i, _ in suspects if rows.dates[i] < m_first]
    after = [i for i, _ in suspects if rows.dates[i] > m_last]
    if before:
        cut = max(before)
        notes.append(f"cut {cut} rows before an unexplained move on {rows.dates[cut]} ahead of the membership")
        trimmed = True
    if after:
        cut = min(after)
        notes.append(f"cut {len(rows) - cut} rows from an unexplained move on {rows.dates[cut]} after the membership")
        trimmed = True
    lo_cut = max(before) if before else 0
    hi_cut = min(after) if after else len(rows)
    genuine_in = [(i, q) for i, q in genuine if lo_cut <= i < hi_cut and m_first <= rows.dates[i] <= m_last]
    if len(genuine_in) > ABSURD_MAX_MOVES:
        return Cleaned(
            **head, action=DROPPED,
            reason=(
                f"absurd: {len(genuine_in)} one-day moves beyond {JUMP:g}x inside the membership "
                f"(first {rows.dates[genuine_in[0][0]]})"
            ),
            scale_repairs=breaks, island_repairs=islands, rows_removed=removed,
        )
    moves_kept = [(i, q) for i, q in genuine if lo_cut <= i < hi_cut]
    if moves_kept:
        notes.append(
            f"kept {len(moves_kept)} one-day moves beyond {JUMP:g}x with volume behind them or at the "
            f"end ({'; '.join(f'{rows.dates[i]} x{q:.3g}' for i, q in moves_kept[:3])})"
        )
    rows.take(range(lo_cut, hi_cut))

    # 11. 4 dp and the bars the loader would refuse
    bars: list[CleanBar] = []
    for i in range(len(rows)):
        c = to_decimal(rows.c[i])
        if c <= ZERO_PRICE:
            removed += 1
            continue
        o, h, lo = (to_decimal(x) for x in (rows.o[i], rows.h[i], rows.lo[i]))
        fixes = 0
        if o <= ZERO_PRICE:
            o, fixes = c, fixes + 1
        if h <= ZERO_PRICE:
            h, fixes = c, fixes + 1
        if lo <= ZERO_PRICE:
            lo, fixes = c, fixes + 1
        top, bottom = max(o, c), min(o, c)
        if h < top:
            h, fixes = top, fixes + 1
        if lo > bottom:
            lo, fixes = bottom, fixes + 1
        if h > top * WICK:
            h, fixes = top, fixes + 1
        if lo * WICK < bottom:
            lo, fixes = bottom, fixes + 1
        fields += fixes
        bars.append(CleanBar(rows.dates[i], o, h, lo, c, to_volume(max(rows.v[i], 0.0))))
    member_set = set(member_days)
    covered = sum(1 for b in bars if b.date in member_set)
    if not covered:
        return Cleaned(
            **head, action=DROPPED, reason="no clean bar on a member day",
            scale_repairs=breaks, island_repairs=islands, rows_removed=removed,
        )

    dividends, refused = _dividends(series.dividends, bars)
    if refused:
        notes.append(f"refused {refused} dividends (not USD or above {MAX_DIVIDEND_YIELD:.0%} of the prior close)")
    if removed:
        notes.append(f"{removed} rows removed")
    if fields:
        notes.append(f"{fields} open/high/low values repaired")
    if covered < len(member_days):
        notes.append(f"covers {covered} of {len(member_days)} member days")
    action = TRIMMED if trimmed else REPAIRED if (breaks or islands or levels or removed or fields) else KEPT
    return Cleaned(
        **head,
        action=action,
        reason=report_text("; ".join(notes) if notes else "clean"),
        bars=tuple(bars),
        dividends=dividends,
        covered_days=covered,
        splits_applied=len(use),
        splits_skipped=len(skip),
        scale_repairs=breaks,
        island_repairs=islands,
        level_repairs=levels,
        rows_removed=removed,
        fields_repaired=fields,
        moves_kept=len(moves_kept),
        dividends_refused=refused,
    )


def _dividends(
    rows: Sequence[RawDividend], bars: Sequence[CleanBar]
) -> tuple[tuple[tuple[date, Decimal], ...], int]:
    """USD dividends inside the kept bars, 6 dp; refused when above MAX_DIVIDEND_YIELD."""
    if not bars:
        return (), 0
    days = [b.date for b in bars]
    out: dict[date, Decimal] = {}
    refused = 0
    for r in rows:
        if not days[0] <= r.ex_date <= min(days[-1], research.DEV_END):
            continue
        if r.value is None or r.value <= 0:
            continue
        if r.currency not in (None, "USD"):
            refused += 1
            continue
        amount = r.value.quantize(DIVIDEND_QUANTUM, rounding=ROUND_HALF_UP)
        if amount <= 0:
            continue
        i = bisect_left(days, r.ex_date) - 1
        if i < 0 or amount > bars[i].close * MAX_DIVIDEND_YIELD:
            refused += 1
            continue
        out[r.ex_date] = out.get(r.ex_date, Decimal(0)) + amount
    return tuple(sorted(out.items())), refused


def best_of(candidates: Sequence[Cleaned]) -> Cleaned:
    """Of several cleaned series for one symbol, the one covering the most member days.

    Ties, and a field where every candidate was dropped, go to the earliest candidate, so the
    original cache wins over a phase-2 alias unless the alias genuinely covers more.
    ValueError on an empty sequence or on candidates for different symbols.
    """
    if not candidates:
        raise ValueError("best_of needs at least one candidate")
    if len({c.symbol for c in candidates}) != 1:
        raise ValueError("best_of compares candidates for one symbol")
    best = candidates[0]
    for c in candidates[1:]:
        if c.action != DROPPED and (best.action == DROPPED or c.covered_days > best.covered_days):
            best = c
    return best


# ---- the store's text ----------------------------------------------------------------------


def bar_line(symbol: str, b: CleanBar) -> str:
    """One ``bars.csv`` line in the dev store's encoding: fixed 4 dp, integer volume."""
    return f"{symbol},{b.date.isoformat()},{b.open},{b.high},{b.low},{b.close},{b.volume}"


def amount_text(amount: Decimal) -> str:
    """A dividend amount the way ``dividends.csv`` writes it: at most 6 dp, no trailing zeros."""
    q = amount.quantize(DIVIDEND_QUANTUM, rounding=ROUND_HALF_UP).normalize()
    return format(q, "f")


def merge_sorted_lines(
    existing: Iterable[str], added: Mapping[str, Sequence[str]]
) -> Iterable[str]:
    """``existing`` data lines (grouped by symbol, symbols ascending) with ``added``'s groups
    inserted at their sorted place. Every line starts ``<symbol>,``.

    ValueError when ``existing`` is out of order or a symbol is in both: the merged file must be
    contiguous per symbol and ascending, or ``histories_from_frame`` refuses it.
    """
    pending = sorted(added)
    k = 0
    last: str | None = None
    for line in existing:
        symbol = line.split(",", 1)[0]
        if symbol != last:
            if last is not None and symbol < last:
                raise ValueError(f"the source lines are not sorted by symbol: {symbol} after {last}")
            if symbol in added:
                raise ValueError(f"{symbol} is in the source store and in the added series")
            while k < len(pending) and pending[k] < symbol:
                yield from added[pending[k]]
                k += 1
            last = symbol
        yield line
    while k < len(pending):
        yield from added[pending[k]]
        k += 1


# ---- coverage ------------------------------------------------------------------------------


def coverage_by_year(
    member_days: Mapping[str, Sequence[date]],
    before: Mapping[str, np.ndarray],
    after: Mapping[str, np.ndarray],
) -> tuple[YearCoverage, ...]:
    """Member-days per calendar year, and how many have a bar in ``before`` / ``after``.

    ``member_days`` maps each member symbol to its member sessions; ``before`` and ``after`` map
    a symbol to its bar dates as a ``datetime64[D]`` array (absent: no bars).
    """
    empty = np.array([], dtype="datetime64[D]")
    totals: dict[int, list[int]] = {}
    for symbol, days in member_days.items():
        if not days:
            continue
        arr = np.array(days, dtype="datetime64[D]")
        years = arr.astype("datetime64[Y]").astype(int) + 1970
        hit_b = np.isin(arr, before.get(symbol, empty))
        hit_a = np.isin(arr, after.get(symbol, empty))
        for y in np.unique(years):
            mask = years == y
            row = totals.setdefault(int(y), [0, 0, 0])
            row[0] += int(mask.sum())
            row[1] += int(hit_b[mask].sum())
            row[2] += int(hit_a[mask].sum())
    return tuple(YearCoverage(y, *totals[y]) for y in sorted(totals))
```
**Impact:** new module, imported only by the new command and the new tests.

### Step 5: The build command
**File:** `engine/src/seer_engine/commands/survivorship_store.py` (create; auto-discovered by `cli.py`, which is not edited)
**Change:** the whole module below. It uses `research._seal`, `research._swap_in` and
`research._write_text` (private, same package, deliberately reused so the store is sealed and
swapped with exactly the dev store's discipline) and `commands.dividend_announcements.read_cache`.
**Code:**
```python
"""survivorship_store -- build the survivorship-check store from the EODHD cache. No network.

    python -m seer_engine survivorship_store            # clean every cached series, print the coverage report; writes nothing
    python -m seer_engine survivorship_store --build    # write the store at --out (default engine/.research-sv)
    python -m seer_engine survivorship_store --report   # print the reports of the store already at --out

The store is ``--source`` (default the dev store, ``engine/.research``, read only) plus a cleaned
EODHD series for every member the dev store could not serve, read from ``--cache`` (default
``engine/.cache/eodhd``: ``eod/``, ``splits/``, ``dividends/``). ``seer_engine.survivorship`` holds
the cleaning rules; this module only reads, merges and writes.

What lands in ``--out``, built in ``<out>.tmp`` and swapped in whole or not at all:

- ``bars.csv`` / ``dividends.csv``: the source's lines, byte for byte, with the added symbols'
  lines inserted at their sorted place; ``fx.csv`` and every optional file (``fundamentals.csv``
  and whatever else the source lists) copied byte for byte and sha-checked;
- ``unserved.csv``: the members still without a bar, each with the reason the cleaning gave;
- ``dividend_announcements.csv``: re-matched with ``dividend_announcements.match`` over the merged
  dividends from the cached ``dividends/`` files (carried from the source when the cache has none);
- ``manifest.json``: sealed for the dev window with ``"purpose": "survivorship-check"``, so its
  price fingerprint is its own and ``lab run`` / ``lab test`` / ``lab remeasure`` refuse it;
- ``cleaning_report.csv`` (one row per symbol the dev store could not serve: action, reason,
  counts) and ``coverage_report.txt`` (member-days per year before and after, and the members still
  missing). Both sit inside the store but outside the manifest: the loader ignores unlisted files,
  so the reports can be read without touching the fingerprint.

``--out`` must not be the source, a symlink, or the dev or test store's directory: ``_swap_in``
would replace the directory a symlink names. The source is verified with ``research.load_store``
first, and the built store is loaded once more before it is swapped in.

Exit codes: 0 ok; 2 refused (paths, a source that does not verify or is itself a
survivorship-check store, a store at ``--out`` that is not one, for ``--report``).
"""

from __future__ import annotations

import argparse
import logging
import shutil
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np

from seer_engine import config, dates, research
from seer_engine import dividend_announcements as da
from seer_engine import survivorship as sv
from seer_engine.commands.dividend_announcements import read_cache

log = logging.getLogger(__name__)

HELP = (
    "Build the survivorship-check store (engine/.research-sv): the dev store plus cleaned EODHD "
    "bars for the members it never served, from the local cache, with a cleaning and a coverage "
    "report inside it."
)

CACHE_DIR = config.REPO_ROOT / "engine" / ".cache" / "eodhd"
CLEANING_REPORT = "cleaning_report.csv"
COVERAGE_REPORT = "coverage_report.txt"
REPORT_FILES: tuple[str, ...] = (CLEANING_REPORT, COVERAGE_REPORT)


class SurvivorshipStoreError(RuntimeError):
    """The build was refused or could not finish; nothing was written."""


@dataclass(frozen=True)
class BuildPlan:
    """Everything a build writes, computed in memory from the source store and the cache."""

    source_dir: Path
    source_manifest: Mapping[str, Any]
    source_price_fingerprint: str | None
    cleaned: Mapping[str, sv.Cleaned]  # one per symbol the source could not serve
    source_dividends: Mapping[str, Mapping[date, Any]]
    coverage: tuple[sv.YearCoverage, ...]
    missing: tuple[tuple[str, int, str], ...]  # (symbol, member days, why), members still without a bar

    @property
    def added(self) -> dict[str, sv.Cleaned]:
        return {s: c for s, c in sorted(self.cleaned.items()) if c.action != sv.DROPPED}

    @property
    def still_unserved(self) -> dict[str, sv.Cleaned]:
        return {s: c for s, c in sorted(self.cleaned.items()) if c.action == sv.DROPPED}


def add_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument("--build", action="store_true", help="write the store at --out")
    p.add_argument("--report", action="store_true", help="print the reports of the store at --out")
    p.add_argument("--out", type=Path, default=research.SV_STORE_DIR, help=f"store to write (default {research.SV_STORE_DIR})")
    p.add_argument("--source", type=Path, default=research.STORE_DIR, help=f"dev store to start from, read only (default {research.STORE_DIR})")
    p.add_argument("--cache", type=Path, default=CACHE_DIR, help=f"EODHD cache (default {CACHE_DIR})")


# ---- planning ------------------------------------------------------------------------------


def plan_build(
    source_dir: Path,
    cache: Path,
    *,
    data_dir: Path | None = None,
    extra_sources: Mapping[str, Sequence[sv.SourceSeries]] | None = None,
) -> BuildPlan:
    """Clean every symbol the source store could not serve; nothing is written.

    ``extra_sources`` maps a store symbol to further candidate series (phase 2's alias fill);
    each is cleaned like the cache's own and :func:`survivorship.best_of` keeps the one covering
    the most member days. SurvivorshipStoreError when the source does not verify or is itself a
    survivorship-check store.
    """
    source_dir = Path(source_dir)
    try:
        data = research.load_store(source_dir, data_dir=data_dir)
    except ValueError as exc:
        raise SurvivorshipStoreError(f"{source_dir}: the source store does not verify: {exc}") from exc
    if data.purpose is not None:
        raise SurvivorshipStoreError(
            f"{source_dir}: the source is itself a {data.purpose!r} store; build from the dev store"
        )
    sessions = dates.sessions(research.STORE_START, research.DEV_END)
    member_window = [d for d in sessions if d >= research.MEMBERSHIP_START]
    intervals = data.market.membership.intervals
    extra = extra_sources or {}
    cleaned: dict[str, sv.Cleaned] = {}
    for symbol in sorted(data.unserved):
        days = sv.member_sessions(intervals, symbol, member_window)
        candidates: list[sv.Cleaned] = []
        primary = sv.read_series(cache, symbol)
        if primary is not None:
            candidates.append(sv.clean_symbol(primary, days, sessions))
        for series in extra.get(symbol, ()):
            candidates.append(sv.clean_symbol(series, days, sessions))
        cleaned[symbol] = (
            sv.best_of(candidates)
            if candidates
            else sv.Cleaned(
                symbol=symbol, source=sv.EODHD_SOURCE, code=sv.eodhd_code(symbol),
                action=sv.DROPPED, reason="never fetched into the EODHD cache",
                member_days=len(days),
            )
        )
        log.debug("survivorship: %s %s %s", symbol, cleaned[symbol].action, cleaned[symbol].reason)

    members = sorted({s for s, _, _ in intervals} - set(research.RESEARCH_ETFS))
    member_days = {s: sv.member_sessions(intervals, s, member_window) for s in members}
    before = {s: h.dates for s, h in data.market.history.items()}
    after = dict(before)
    for s, c in cleaned.items():
        if c.bars:
            after[s] = np.array([b.date for b in c.bars], dtype="datetime64[D]")
    coverage = sv.coverage_by_year(member_days, before, after)
    missing: list[tuple[str, int, str]] = []
    for s in members:
        days = member_days[s]
        if not days:
            continue
        have = after.get(s)
        if have is not None and bool(np.isin(np.array(days, dtype="datetime64[D]"), have).any()):
            continue
        why = cleaned[s].reason if s in cleaned else "the source store has bars but none on a member day"
        missing.append((s, len(days), why))
    return BuildPlan(
        source_dir=source_dir,
        source_manifest=dict(data.manifest),
        source_price_fingerprint=data.price_fingerprint,
        cleaned=cleaned,
        source_dividends=data.dividends,
        coverage=coverage,
        missing=tuple(missing),
    )


# ---- reports -------------------------------------------------------------------------------


def cleaning_report(plan: BuildPlan) -> str:
    """``cleaning_report.csv``: one row per symbol the source could not serve, sorted."""
    lines = [sv.REPORT_HEADER, *(plan.cleaned[s].report_line() for s in sorted(plan.cleaned))]
    return "\n".join(lines) + "\n"


def coverage_report(plan: BuildPlan) -> str:
    """``coverage_report.txt``: plain text, deterministic (no timestamps), LF."""
    lines = [
        "Survivorship-check store: member-day coverage over the dev window",
        f"source store: price fingerprint {plan.source_price_fingerprint}",
        "member-days: sessions 1996-01-02..2015-10-16 on which a symbol was an S&P 500 or "
        "Nasdaq-100 member (ETFs excluded)",
        "before: the dev store has a bar that day; after: this store has one",
        "",
        f"{'year':>4}  {'member-days':>11}  {'before':>7}  {'after':>7}",
    ]
    total = [0, 0, 0]
    for y in plan.coverage:
        lines.append(
            f"{y.year:>4}  {y.member_days:>11}  {y.before / y.member_days:>7.1%}  {y.after / y.member_days:>7.1%}"
        )
        total[0] += y.member_days
        total[1] += y.before
        total[2] += y.after
    if total[0]:
        lines.append(f"{'all':>4}  {total[0]:>11}  {total[1] / total[0]:>7.1%}  {total[2] / total[0]:>7.1%}")
    lines += ["", f"Cleaning of the {len(plan.cleaned)} symbols the dev store could not serve:"]
    for action in sv.ACTIONS:
        group = [c for c in plan.cleaned.values() if c.action == action]
        lines.append(
            f"  {action:<9} {len(group):>4} symbols, {sum(c.covered_days for c in group):>8} member-days covered, "
            f"{sum(len(c.bars) for c in group):>8} bars, {sum(len(c.dividends) for c in group):>6} dividends"
        )
    lines += [
        "",
        f"Members still missing (no bar on any member day): {len(plan.missing)}, "
        f"{sum(n for _, n, _ in plan.missing)} member-days",
    ]
    lines += [f"  {s:<8} {n:>5}  {why}" for s, n, why in plan.missing]
    return "\n".join(lines) + "\n"


# ---- writing -------------------------------------------------------------------------------


def _refuse_out(out: Path, source_dir: Path) -> None:
    out = Path(out)
    if out.is_symlink():
        raise SurvivorshipStoreError(f"{out} is a symlink; pass the real directory (os.replace would move the link)")
    resolved = out.resolve()
    forbidden = {Path(source_dir).resolve(), research.STORE_DIR.resolve(), research.TEST_STORE_DIR.resolve()}
    if resolved in forbidden:
        raise SurvivorshipStoreError(f"{out} is the source, dev or test store; the survivorship-check store needs its own directory")
    if out.exists() and (out / research.MANIFEST_FILE).is_file():
        try:
            purpose = research.declared_purpose(out)
        except ValueError:
            purpose = None
        if purpose != research.SURVIVORSHIP_PURPOSE:
            raise SurvivorshipStoreError(
                f"{out} already holds a store that is not a survivorship-check store; refusing to replace it"
            )


def _copy_checked(src: Path, dst: Path, digest: str) -> None:
    shutil.copyfile(src, dst)
    copied = research.file_sha256(dst)
    if copied != digest:
        raise SurvivorshipStoreError(f"{src.name}: the copy hashes {copied}, the verified source {digest}")


def _data_lines(path: Path):
    with path.open(encoding="utf-8") as fh:
        next(fh)
        for line in fh:
            yield line.rstrip("\n")


def write_store(
    plan: BuildPlan,
    out: Path,
    cache: Path,
    *,
    data_dir: Path | None = None,
    extra_reports: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Write the store ``plan`` describes at ``out``; return its manifest.

    ``extra_reports`` are further ``name -> text`` files written inside the store and outside the
    manifest (phase 2's ``alias_report.csv``). Built in ``<out>.tmp``, verified with
    ``research.load_store``, then swapped in; on any failure nothing at ``out`` changes.
    """
    out = Path(out)
    source = plan.source_dir
    _refuse_out(out, source)
    files = plan.source_manifest["files"]
    added = plan.added
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".tmp")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir()
    try:
        bar_rows = 0
        with (tmp / research.BARS_FILE).open("w", encoding="utf-8", newline="\n") as fh:
            fh.write(research.BARS_HEADER + "\n")
            new = {s: [sv.bar_line(s, b) for b in c.bars] for s, c in added.items()}
            for line in sv.merge_sorted_lines(_data_lines(source / research.BARS_FILE), new):
                fh.write(line + "\n")
                bar_rows += 1
        new_divs = {
            s: [f"{s},{d.isoformat()},{sv.amount_text(a)}" for d, a in c.dividends]
            for s, c in added.items() if c.dividends
        }
        dividend_lines = list(sv.merge_sorted_lines(_data_lines(source / research.DIVIDENDS_FILE), new_divs))
        research._write_text(tmp / research.DIVIDENDS_FILE, research.DIVIDENDS_HEADER, dividend_lines)
        _copy_checked(source / research.FX_FILE, tmp / research.FX_FILE, files[research.FX_FILE])
        unserved = plan.still_unserved
        research._write_text(
            tmp / research.UNSERVED_FILE,
            research.UNSERVED_HEADER,
            [f"{s},no usable EODHD series: {sv.report_text(c.reason)}" for s, c in unserved.items()],
        )
        extra_files: list[str] = []
        for name in research.OPTIONAL_DATA_FILES:
            if name == research.ANNOUNCEMENTS_FILE or name not in files:
                continue
            _copy_checked(source / name, tmp / name, files[name])
            extra_files.append(name)
        merged: dict[str, dict[date, Any]] = {s: dict(v) for s, v in plan.source_dividends.items()}
        for s, c in added.items():
            if c.dividends:
                merged[s] = dict(c.dividends)
        dividends_cache = Path(cache) / "dividends"
        if dividends_cache.is_dir():
            vendor = read_cache(dividends_cache, sorted(merged))
            match = da.match(merged, vendor, skip=research.RESEARCH_ETFS, years=(1996, research.DEV_END.year))
            research._write_text(
                tmp / research.ANNOUNCEMENTS_FILE,
                research.ANNOUNCEMENTS_HEADER,
                research.announcement_lines(match.rows, merged),
            )
            extra_files.append(research.ANNOUNCEMENTS_FILE)
        elif research.ANNOUNCEMENTS_FILE in files:
            _copy_checked(source / research.ANNOUNCEMENTS_FILE, tmp / research.ANNOUNCEMENTS_FILE, files[research.ANNOUNCEMENTS_FILE])
            extra_files.append(research.ANNOUNCEMENTS_FILE)
        counts = {
            "bar_rows": bar_rows,
            "dividend_rows": len(dividend_lines),
            "fx_rows": int(plan.source_manifest["fx_rows"]),
            "symbols_requested": int(plan.source_manifest["symbols_requested"]),
            "symbols_served": int(plan.source_manifest["symbols_served"]) + len(added),
        }
        manifest = research._seal(
            tmp, counts,
            extra_files=tuple(n for n in research.OPTIONAL_DATA_FILES if n in extra_files),
            window=research.DEV_WINDOW,
            purpose=research.SURVIVORSHIP_PURPOSE,
        )
        reports = {CLEANING_REPORT: cleaning_report(plan), COVERAGE_REPORT: coverage_report(plan), **(extra_reports or {})}
        for name, text in reports.items():
            if name in manifest["files"] or name == research.MANIFEST_FILE:
                raise SurvivorshipStoreError(f"{name} is a store file, not a report")
            (tmp / name).write_text(text, encoding="utf-8", newline="\n")
        try:
            built = research.load_store(tmp, data_dir=data_dir)
        except ValueError as exc:
            raise SurvivorshipStoreError(f"the built store does not load: {exc}") from exc
        if built.purpose != research.SURVIVORSHIP_PURPOSE:
            raise SurvivorshipStoreError("the built store lost its purpose mark")
        if added and built.price_fingerprint == plan.source_price_fingerprint:
            raise SurvivorshipStoreError("the built store has the source's price fingerprint although bars were added")
        del built
        research._swap_in(tmp, out)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    log.info(
        "survivorship: store %s built: %d symbols added, %d still unserved, %d bar rows, price fingerprint %s",
        out, len(added), len(plan.still_unserved), bar_rows, research.price_fingerprint_of(manifest["files"]),
    )
    return manifest


# ---- the command ---------------------------------------------------------------------------


def _print_store_reports(out: Path) -> int:
    try:
        purpose = research.declared_purpose(out)
    except ValueError as exc:
        print(f"survivorship_store: {exc}")
        return 2
    if purpose != research.SURVIVORSHIP_PURPOSE:
        print(f"survivorship_store: {out} is not a survivorship-check store")
        return 2
    report = out / COVERAGE_REPORT
    if not report.is_file():
        print(f"survivorship_store: {out} has no {COVERAGE_REPORT}")
        return 2
    print(report.read_text(encoding="utf-8"), end="")
    return 0


def run(args: argparse.Namespace) -> int:
    out = Path(args.out)
    if args.report:
        return _print_store_reports(out)
    try:
        plan = plan_build(Path(args.source), Path(args.cache))
    except SurvivorshipStoreError as exc:
        print(f"survivorship_store: {exc}")
        return 2
    print(coverage_report(plan), end="")
    if not args.build:
        print(f"\nnothing written; pass --build to write {out}")
        return 0
    if getattr(args, "dry_run", False):
        print(f"\ndry run: would write {len(plan.added)} added symbols into {out}")
        return 0
    try:
        manifest = write_store(plan, out, Path(args.cache))
    except SurvivorshipStoreError as exc:
        print(f"survivorship_store: {exc}")
        return 2
    print(
        f"\nwrote {out}: {manifest['symbols_served']} of {manifest['symbols_requested']} symbols served, "
        f"{manifest['bar_rows']} bar rows, price fingerprint {research.price_fingerprint_of(manifest['files'])}, "
        f"purpose {manifest[research.PURPOSE_KEY]!r}"
    )
    return 0
```
**Impact:** new CLI command `python -m seer_engine survivorship_store`. Default (no flag) cleans and
prints, writing nothing; `--build` writes; `--report` prints a built store's `coverage_report.txt`;
the global `--dry-run` with `--build` writes nothing.

### Step 6: Tests
**File:** `engine/tests/test_survivorship_store.py` (create)
**Change:** 37 tests. Every vendor series is synthetic on real NYSE sessions; the source store is
`test_research_store`'s fixture (`GONE` is a member 1996-01-02..2000-01-03 it never served; `DDD`
is unserved and unknown to the fake cache). Covers each cleaning rule, the merge, coverage, the
purpose mark (seal, load, refresh, unknown value), the build (source untouched, reports unlisted,
sorting and encoding, path refusals, a marked source), the command's three modes, and the refusal
in `run_method`, `run_test`, `remeasure`, `remeasure_seed` and `commands/lab.py:_run` with N, looks
and `trial_moments` unchanged.
**Code:**
```python
"""The survivorship-check store: the cleaning rules (``seer_engine.survivorship``), the build
(``commands/survivorship_store.py``), the ``purpose`` manifest mark (``research``) and the refusal
of a marked store by every trial-writing path. No network and no real cache: every vendor series
here is synthetic, laid on real NYSE sessions, and the source store is ``test_research_store``'s
tiny fixture."""

from __future__ import annotations

import argparse
import dataclasses
import json
from bisect import bisect_left
from datetime import date
from decimal import Decimal
from pathlib import Path

import numpy as np
import pytest
from labkit import smoke_data, smoke_test_data

import test_research_store as rs
from test_research_store import FACTS_A, build
from seer_engine import config, dates, research
from seer_engine import survivorship as sv
from seer_engine.commands import lab as lab_cmd
from seer_engine.commands import survivorship_store as cmd
from seer_engine.lab import remeasure as rm
from seer_engine.lab import runner, store
from seer_engine.lab.seed import seed

SESSIONS = dates.sessions(research.STORE_START, research.DEV_END)
MARK = research.SURVIVORSHIP_PURPOSE


def days_from(start: date, n: int) -> list[date]:
    i = bisect_left(SESSIONS, start)
    return SESSIONS[i : i + n]


def series(
    closes,
    *,
    start: date = date(2000, 1, 3),
    opens=None,
    volumes=None,
    splits=(),
    dividends=(),
    symbol: str = "ZZZ",
    day_list=None,
) -> sv.SourceSeries:
    """A synthetic raw series: one bar per session from ``start`` (or on ``day_list``)."""
    ds = day_list if day_list is not None else days_from(start, len(closes))
    opens = opens if opens is not None else closes
    volumes = volumes if volumes is not None else [1_000_000.0] * len(closes)
    bars = tuple(
        sv.RawBar(d, o, max(o, c) * 1.01, min(o, c) * 0.99, c, v)
        for d, o, c, v in zip(ds, opens, closes, volumes)
    )
    return sv.SourceSeries(
        symbol=symbol, source=sv.EODHD_SOURCE, code=sv.eodhd_code(symbol), bars=bars,
        splits=tuple(splits), dividends=tuple(dividends),
    )


def wave(n: int, base: float = 20.0) -> list[float]:
    """Gentle, deterministic prices: never a one-day move near 1.4x."""
    return [round(base * (1.0 + 0.02 * ((i % 7) - 3) / 3.0), 4) for i in range(n)]


def clean(s: sv.SourceSeries, member=None) -> sv.Cleaned:
    member = member if member is not None else tuple(b.date for b in s.bars)
    return sv.clean_symbol(s, tuple(member), SESSIONS)


def closes(c: sv.Cleaned) -> list[float]:
    return [float(b.close) for b in c.bars]


def max_move(c: sv.Cleaned) -> float:
    cs = closes(c)
    return max(max(b / a, a / b) for a, b in zip(cs, cs[1:]))


# ---- reading the cache ---------------------------------------------------------------------


def test_parse_split_reads_new_over_old_and_refuses_junk():
    assert sv.parse_split("2.000000/1.000000") == 2.0
    assert sv.parse_split("1.000000/10.000000") == pytest.approx(0.1)
    for bad in ("2", "0/1", "x/1", "1/0"):
        with pytest.raises(ValueError):
            sv.parse_split(bad)


def test_read_series_reads_the_three_cache_folders(tmp_path):
    (tmp_path / "eod").mkdir()
    (tmp_path / "splits").mkdir()
    (tmp_path / "dividends").mkdir()
    (tmp_path / "eod" / "BRK.B.json").write_text(json.dumps([
        {"date": "2000-01-04", "open": 10, "high": 11, "low": 9, "close": 10.5, "adjusted_close": 1, "volume": 100},
        {"date": "2000-01-03", "open": None, "high": 11, "low": 9, "close": 10, "adjusted_close": 1, "volume": None},
    ]))
    (tmp_path / "splits" / "BRK.B.json").write_text(json.dumps([{"date": "2010-01-21", "split": "50.000000/1.000000"}]))
    (tmp_path / "dividends" / "BRK.B.json").write_text(json.dumps(
        {"symbol": "BRK.B", "rows": [{"date": "2000-01-04", "value": 0.5, "currency": "USD"}]}
    ))
    (tmp_path / "eod" / "GONE.json").write_text("null")
    s = sv.read_series(tmp_path, "BRK.B")
    assert s.code == "BRK-B.US" and s.source == sv.EODHD_SOURCE
    assert [b.date for b in s.bars] == [date(2000, 1, 3), date(2000, 1, 4)]
    assert s.bars[0].open is None and s.bars[0].volume is None
    assert s.splits == (sv.Split(date(2010, 1, 21), 50.0),)
    assert s.dividends == (sv.RawDividend(date(2000, 1, 4), Decimal("0.5"), "USD"),)
    assert sv.read_series(tmp_path, "GONE").bars == ()
    assert sv.read_series(tmp_path, "NEVER") is None


def test_member_sessions_is_start_inclusive_end_exclusive():
    iv = (("AAA", date(2000, 1, 3), date(2000, 1, 6)), ("BBB", date(2000, 1, 3), None))
    assert sv.member_sessions(iv, "AAA", SESSIONS) == (date(2000, 1, 3), date(2000, 1, 4), date(2000, 1, 5))
    assert sv.member_sessions(iv, "BBB", SESSIONS)[-1] == research.DEV_END
    assert sv.member_sessions(iv, "CCC", SESSIONS) == ()


# ---- the cleaning rules --------------------------------------------------------------------


def test_a_clean_series_is_kept_in_the_dev_store_encoding():
    c = clean(series(wave(60)))
    assert c.action == sv.KEPT and c.reason == "clean"
    assert c.covered_days == c.member_days == 60
    b = c.bars[0]
    assert sv.bar_line("ZZZ", b).startswith("ZZZ,2000-01-03,")
    assert all(len(cell.split(".")[1]) == 4 for cell in sv.bar_line("ZZZ", b).split(",")[2:6])
    assert isinstance(b.volume, int)


def test_a_listed_split_the_raw_prices_need_is_applied():
    raw = wave(40) + [x / 2 for x in wave(40)]
    vols = [1e6] * 40 + [2e6] * 40
    split_day = days_from(date(2000, 1, 3), 80)[40]
    c = clean(series(raw, volumes=vols, splits=[sv.Split(split_day, 2.0)]))
    assert c.action == sv.KEPT and c.splits_applied == 1 and c.splits_skipped == 0
    assert max_move(c) < 1.1
    assert closes(c)[0] == pytest.approx(wave(40)[0] / 2, abs=1e-4)
    assert c.bars[0].volume == 2_000_000


def test_a_listed_split_already_in_the_raw_prices_is_skipped():
    split_day = days_from(date(2000, 1, 3), 80)[40]
    c = clean(series(wave(80), splits=[sv.Split(split_day, 2.0)]))
    assert c.splits_applied == 0 and c.splits_skipped == 1
    assert closes(c) == pytest.approx(wave(80), abs=1e-4)
    assert max_move(c) < 1.1


def test_an_unlisted_split_is_repaired_as_a_scale_break():
    raw = wave(40) + [x / 2 for x in wave(40)]
    vols = [1e6] * 40 + [2e6] * 40
    c = clean(series(raw, volumes=vols))
    assert c.action == sv.REPAIRED and c.scale_repairs == 1
    assert max_move(c) < 1.1
    assert closes(c)[0] == pytest.approx(wave(40)[0] / 2, abs=1e-4)


def test_a_crash_is_kept_even_when_its_close_is_near_a_simple_ratio():
    """CVH 2008-10-22: opened 36% down, closed 51% down, on ten times the volume."""
    pre, post = wave(40, 28.0), wave(40, 13.7)
    opens = pre + [18.3] + post[1:]
    vols = [1.5e6] * 40 + [19e6, 7e6] + [5e6] * 38
    c = clean(series(pre + post, opens=opens, volumes=vols))
    assert c.action == sv.KEPT and c.scale_repairs == 0 and c.moves_kept == 1
    assert closes(c)[40] == pytest.approx(13.7 * (1 + 0.02 * -1), abs=1e-3)


def test_a_spike_that_comes_straight_back_is_removed():
    raw = wave(60)
    raw[30] = raw[29] * 12
    c = clean(series(raw))
    assert c.action == sv.REPAIRED and c.rows_removed == 1
    assert len(c.bars) == 59 and max_move(c) < 1.1


def test_an_island_printed_at_the_wrong_scale_is_rescaled():
    raw = wave(300)
    for i in range(100, 200):
        raw[i] *= 15.0
    c = clean(series(raw))
    assert c.island_repairs == 1 and c.action == sv.REPAIRED
    assert max_move(c) < 1.1


def test_a_quiet_level_shift_inside_the_membership_rescales_the_earlier_rows():
    """EA 2003-11-18: x0.118 on ordinary volume. The later prices stand as printed."""
    raw = wave(100) + [x * 0.12 for x in wave(100)]
    c = clean(series(raw))
    assert c.level_repairs == 1 and c.action == sv.REPAIRED
    assert max_move(c) < 1.1
    assert closes(c)[-1] == pytest.approx(raw[-1], abs=1e-4)


def test_too_many_quiet_moves_drop_the_symbol():
    raw: list[float] = []
    for level in (1.0, 10.0, 2.5, 30.0, 4.0, 50.0):  # five quiet jumps, no two of them cancel
        raw += [x * level for x in wave(40)]
    c = clean(series(raw))
    assert c.action == sv.DROPPED and c.reason.startswith("absurd")
    assert c.bars == ()


def test_a_collapse_at_the_end_of_the_membership_is_kept_without_volume():
    """WAMUQ 2008-09-26: seized overnight, x0.095 two days before it left the index."""
    raw = wave(100) + [0.16, 0.15, 0.14]
    c = clean(series(raw, volumes=[1e6] * 100 + [5e5] * 3))
    assert c.action == sv.KEPT and c.moves_kept == 1
    assert closes(c)[-1] == pytest.approx(0.14, abs=1e-4)


def test_a_reused_ticker_after_a_long_hole_is_cut():
    member = days_from(date(2000, 1, 3), 80)
    later = days_from(date(2001, 1, 2), 40)
    s = series(wave(80) + wave(40, 5.0), day_list=member + later)
    c = clean(s, member=member)
    assert c.action == sv.TRIMMED and c.last == member[-1]
    assert "after the membership" in c.reason


def test_the_tail_ends_a_month_after_the_membership():
    ds = days_from(date(2000, 1, 3), 200)
    c = clean(series(wave(200), day_list=ds), member=ds[:100])
    assert c.last == ds[99 + sv.TAIL_GRACE_SESSIONS]


def test_a_series_that_never_trades_inside_the_membership_is_dropped():
    c = clean(series(wave(40), start=date(1999, 1, 4)), member=days_from(date(2007, 2, 1), 30))
    assert c.action == sv.DROPPED and "another company" in c.reason


def test_no_series_and_a_series_only_after_2015_are_dropped():
    empty = sv.SourceSeries("ZZZ", sv.EODHD_SOURCE, "ZZZ.US", ())
    assert clean(empty, member=days_from(date(2000, 1, 3), 5)).reason == "eodhd has no daily series for ZZZ.US"
    late = series(wave(5), day_list=[date(2020, 1, d) for d in (2, 3, 6, 7, 8)])
    c = clean(late, member=days_from(date(2000, 1, 3), 5))
    assert c.action == sv.DROPPED and "has no session inside" in c.reason


def test_rows_the_loader_would_refuse_are_removed_or_repaired():
    ds = days_from(date(2000, 1, 3), 6)
    bars = (
        sv.RawBar(ds[0], 10.0, 10.5, 9.5, 10.0, 1000.0),
        sv.RawBar(ds[1], 0.0, 10.5, 9.5, 10.1, 1000.0),  # open 0 -> the close
        sv.RawBar(ds[2], 10.0, 9.0, 11.0, 10.2, 1000.0),  # high < low -> widened
        sv.RawBar(ds[3], 10.2, 10.2, 10.2, 10.2, 0.0),  # a filler -> removed
        sv.RawBar(ds[4], None, None, None, None, None),  # no close -> removed
        sv.RawBar(ds[5], 10.0, 40.0, 9.9, 10.1, 1000.0),  # a wick beyond 3x the body -> cut
    )
    c = clean(sv.SourceSeries("ZZZ", sv.EODHD_SOURCE, "ZZZ.US", bars), member=ds)
    assert [b.date for b in c.bars] == [ds[0], ds[1], ds[2], ds[5]]
    assert c.rows_removed == 2 and c.fields_repaired >= 4
    for b in c.bars:
        assert Decimal(0) < b.low <= min(b.open, b.close) <= max(b.open, b.close) <= b.high
    assert c.bars[1].open == c.bars[1].close
    assert c.bars[3].high == Decimal("10.1000")


def test_a_price_that_rounds_to_zero_is_removed():
    raw = wave(30, 0.002)
    raw[10] = 0.00004
    c = clean(series(raw))
    assert all(b.close > 0 for b in c.bars)


def test_dividends_are_clipped_to_the_kept_bars_and_sanity_checked():
    ds = days_from(date(2000, 1, 3), 60)
    divs = [
        sv.RawDividend(date(1999, 6, 1), Decimal("0.1"), "USD"),  # before the bars
        sv.RawDividend(ds[10], Decimal("0.1234567"), "USD"),  # kept, 6 dp
        sv.RawDividend(ds[20], Decimal("9"), "USD"),  # 45% of the price: refused
        sv.RawDividend(ds[30], Decimal("0.1"), "CAD"),  # not USD: refused
        sv.RawDividend(ds[40], None, "USD"),  # no value: ignored
    ]
    c = clean(series(wave(60), day_list=ds, dividends=divs))
    assert c.dividends == ((ds[10], Decimal("0.123457")),)
    assert c.dividends_refused == 2
    assert sv.amount_text(Decimal("0.500000")) == "0.5"


def test_best_of_prefers_coverage_and_ties_go_to_the_first():
    a = sv.Cleaned("ZZZ", "eodhd", "ZZZ.US", sv.KEPT, "clean", covered_days=10)
    b = sv.Cleaned("ZZZ", "alias", "ZZZ1.US", sv.KEPT, "clean", covered_days=20)
    d = sv.Cleaned("ZZZ", "eodhd", "ZZZ.US", sv.DROPPED, "none")
    assert sv.best_of([a, b]) is b
    assert sv.best_of([a, dataclasses.replace(b, covered_days=10)]) is a
    assert sv.best_of([d, a]) is a
    with pytest.raises(ValueError):
        sv.best_of([])
    with pytest.raises(ValueError):
        sv.best_of([a, dataclasses.replace(b, symbol="YYY")])


def test_merge_sorted_lines_inserts_each_group_at_its_place():
    existing = ["AAA,1", "AAA,2", "CCC,1"]
    added = {"BBB": ["BBB,1"], "DDD": ["DDD,1"], "A": ["A,1"]}
    assert list(sv.merge_sorted_lines(existing, added)) == ["A,1", "AAA,1", "AAA,2", "BBB,1", "CCC,1", "DDD,1"]
    with pytest.raises(ValueError):
        list(sv.merge_sorted_lines(existing, {"AAA": ["AAA,3"]}))
    with pytest.raises(ValueError):
        list(sv.merge_sorted_lines(["CCC,1", "AAA,1"], {}))


def test_coverage_by_year_counts_member_days_with_a_bar():
    member = {"AAA": [date(1999, 12, 30), date(1999, 12, 31), date(2000, 1, 3)], "BBB": [date(2000, 1, 3)]}
    before = {"AAA": np.array([date(1999, 12, 31)], dtype="datetime64[D]")}
    after = {**before, "BBB": np.array([date(2000, 1, 3)], dtype="datetime64[D]")}
    assert sv.coverage_by_year(member, before, after) == (
        sv.YearCoverage(1999, 2, 1, 1),
        sv.YearCoverage(2000, 2, 0, 1),
    )


# ---- the purpose mark ----------------------------------------------------------------------


def test_the_survivorship_store_dirs_are_gitignored():
    lines = (config.REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    for entry in ("engine/.research-sv/", "engine/.research-sv.tmp/", "engine/.research-sv.old/"):
        assert entry in lines
    assert research.SV_STORE_DIR == config.REPO_ROOT / "engine" / ".research-sv"


def test_seal_refuses_an_unknown_purpose(tmp_path, members_dir):
    src = tmp_path / "store"
    build(src, members_dir)
    with pytest.raises(ValueError, match="purpose"):
        research._seal(src, {k: 0 for k in research._COUNT_KEYS}, purpose="dev-trials")


def test_an_unknown_purpose_is_refused_at_load(tmp_path, members_dir):
    src = tmp_path / "store"
    build(src, members_dir)
    path = src / research.MANIFEST_FILE
    manifest = json.loads(path.read_text())
    assert research.declared_purpose(src) is None
    assert research.load_store(src, data_dir=members_dir).purpose is None
    manifest["purpose"] = "something-else"
    path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    with pytest.raises(ValueError, match="purpose"):
        research.load_store(src, data_dir=members_dir)
    with pytest.raises(ValueError, match="purpose"):
        research.declared_purpose(src)


# ---- the build -----------------------------------------------------------------------------


@pytest.fixture
def members_dir(tmp_path):
    return rs.members_dir.__wrapped__(tmp_path)


def _write_cache(cache: Path) -> None:
    """GONE (a member 1996-01-02..2000-01-03 the source never served) has a clean EODHD
    series, a dividend with a declaration date, and a reused ticker after a long hole; DDD is
    unknown to EODHD."""
    for sub in ("eod", "splits", "dividends"):
        (cache / sub).mkdir(parents=True)
    gone_days = days_from(date(1997, 12, 31), 560)
    member_part = [d for d in gone_days if d < date(2000, 1, 3)]
    rows = [
        {"date": d.isoformat(), "open": p, "high": p * 1.01, "low": p * 0.99, "close": p,
         "adjusted_close": p, "volume": 500000}
        for d, p in zip(gone_days, wave(len(gone_days), 30.0))
    ]
    rows += [
        {"date": d.isoformat(), "open": 3.0, "high": 3.1, "low": 2.9, "close": 3.0, "adjusted_close": 3.0, "volume": 900}
        for d in days_from(date(2005, 1, 3), 20)
    ]
    (cache / "eod" / "GONE.json").write_text(json.dumps(rows))
    (cache / "splits" / "GONE.json").write_text("null")
    (cache / "dividends" / "GONE.json").write_text(json.dumps({
        "symbol": "GONE", "ticker": "GONE.US", "fetched": "2026-10-10T00:00:00+00:00",
        "rows": [{"date": member_part[100].isoformat(), "value": 0.25, "currency": "USD",
                  "declarationDate": member_part[80].isoformat()}],
    }))
    (cache / "eod" / "DDD.json").write_text("null")


@pytest.fixture
def built(tmp_path, members_dir):
    src = tmp_path / "store"
    build(src, members_dir, facts=FACTS_A)
    cache = tmp_path / "eodhd"
    _write_cache(cache)
    before = {p.name: p.read_bytes() for p in src.iterdir()}
    out = tmp_path / "store-sv"
    plan = cmd.plan_build(src, cache, data_dir=members_dir)
    manifest = cmd.write_store(plan, out, cache, data_dir=members_dir)
    return src, cache, out, plan, manifest, before


def test_the_build_adds_the_cleaned_member_and_marks_the_store(built, members_dir):
    src, _, out, plan, manifest, before = built
    assert {p.name: p.read_bytes() for p in src.iterdir()} == before, "the source is read only"
    assert manifest[research.PURPOSE_KEY] == MARK
    data = research.load_store(out, data_dir=members_dir)
    assert data.purpose == MARK and research.declared_purpose(out) == MARK
    assert "GONE" in data.market.history and data.unserved == ("DDD",)
    assert data.market.history["GONE"].last_date() == date(2000, 2, 1)  # 21 sessions of grace, then the hole
    source = research.load_store(src, data_dir=members_dir)
    assert data.price_fingerprint != source.price_fingerprint
    assert manifest["symbols_served"] == source.manifest["symbols_served"] + 1
    assert manifest["symbols_requested"] == source.manifest["symbols_requested"]
    assert (out / research.FUNDAMENTALS_FILE).read_bytes() == (src / research.FUNDAMENTALS_FILE).read_bytes()
    assert (out / research.FX_FILE).read_bytes() == (src / research.FX_FILE).read_bytes()
    assert data.market.dividends.declared_count() == 1
    assert "DDD,no usable EODHD series: eodhd has no daily series for DDD.US" in (out / research.UNSERVED_FILE).read_text()
    assert plan.cleaned["GONE"].action == sv.TRIMMED


def test_the_reports_sit_inside_the_store_and_outside_the_manifest(built):
    _, _, out, plan, manifest, _ = built
    for name in cmd.REPORT_FILES:
        assert (out / name).is_file() and name not in manifest["files"]
    report = (out / cmd.CLEANING_REPORT).read_text().splitlines()
    assert report[0] == sv.REPORT_HEADER
    assert [line.split(",")[0] for line in report[1:]] == ["DDD", "GONE"]
    assert [line.split(",")[3] for line in report[1:]] == [sv.DROPPED, sv.TRIMMED]
    text = (out / cmd.COVERAGE_REPORT).read_text()
    assert "Members still missing (no bar on any member day): 1" in text and "DDD" in text
    years = {y.year: y for y in plan.coverage}
    assert years[1998].after > years[1998].before


def test_every_bar_row_is_sorted_contiguous_and_dev_encoded(built):
    _, _, out, _, _, _ = built
    lines = (out / research.BARS_FILE).read_text().splitlines()[1:]
    symbols = [line.split(",", 1)[0] for line in lines]
    groups = [s for i, s in enumerate(symbols) if i == 0 or s != symbols[i - 1]]
    assert groups == sorted(set(symbols))
    gone = [line for line in lines if line.startswith("GONE,")]
    assert all(len(cell.split(".")[1]) == 4 for line in gone for cell in line.split(",")[2:6])


def test_a_refresh_keeps_the_mark(built, members_dir):
    _, _, out, _, _, _ = built
    after = research.refresh_fundamentals(out, FACTS_A, data_dir=members_dir)
    assert after[research.PURPOSE_KEY] == MARK
    assert research.load_store(out, data_dir=members_dir).purpose == MARK


def test_the_build_refuses_bad_paths_and_a_marked_source(built, tmp_path, members_dir):
    src, cache, out, plan, _, _ = built
    with pytest.raises(cmd.SurvivorshipStoreError, match="source"):
        cmd.write_store(plan, src, cache, data_dir=members_dir)
    link = tmp_path / "link"
    link.symlink_to(tmp_path / "elsewhere", target_is_directory=True)
    with pytest.raises(cmd.SurvivorshipStoreError, match="symlink"):
        cmd.write_store(plan, link, cache, data_dir=members_dir)
    other = tmp_path / "other"
    build(other, members_dir)
    with pytest.raises(cmd.SurvivorshipStoreError, match="not a survivorship-check store"):
        cmd.write_store(plan, other, cache, data_dir=members_dir)
    with pytest.raises(cmd.SurvivorshipStoreError, match="survivorship-check"):
        cmd.plan_build(out, cache, data_dir=members_dir)
    # rebuilding over an existing survivorship-check store is allowed
    cmd.write_store(plan, out, cache, data_dir=members_dir)


def test_the_command_prints_without_writing_and_reports_a_built_store(built, members_dir, monkeypatch, capsys):
    src, cache, out, _, _, _ = built
    real_load = research.load_store
    monkeypatch.setattr(research, "load_store", lambda s, **kw: real_load(s, **{"data_dir": members_dir, **kw}))
    fresh = out.parent / "fresh-sv"
    args = argparse.Namespace(build=False, report=False, out=fresh, source=src, cache=cache, dry_run=False)
    assert cmd.run(args) == 0
    assert "nothing written" in capsys.readouterr().out and not fresh.exists()
    assert cmd.run(argparse.Namespace(**{**vars(args), "build": True, "dry_run": True})) == 0
    assert not fresh.exists()
    assert cmd.run(argparse.Namespace(**{**vars(args), "out": out, "report": True})) == 0
    assert "member-days" in capsys.readouterr().out
    assert cmd.run(argparse.Namespace(**{**vars(args), "out": src, "report": True})) == 2


# ---- every trial-writing path refuses a marked store ---------------------------------------


@pytest.fixture()
def conn(tmp_path):
    c = store.connect(tmp_path / "lab.sqlite")
    seed(c)
    yield c
    c.close()


def _method():
    from test_lab_runner import _method as make

    return make()


def test_lab_run_refuses_a_marked_store_and_records_nothing(conn):
    n = store.dev_trial_count(conn)
    marked = dataclasses.replace(smoke_data(), purpose=MARK)
    with pytest.raises(store.LabError, match="lab survivorship"):
        runner.run_method(conn, _method(), Path(__file__), marked, git_sha="x", require_commit=False)
    assert store.dev_trial_count(conn) == n
    assert store.get_method(conn, "M0001") is None


def test_lab_test_refuses_a_marked_store_before_anything_else(conn):
    m = _method()
    looks = store.test_looks(conn)
    marked = dataclasses.replace(smoke_test_data(), purpose=MARK)
    with pytest.raises(store.LabError, match="lab survivorship"):
        runner.run_test(conn, m, Path(__file__), m.candidates[0], marked, git_sha="x", require_commit=False)
    assert store.test_looks(conn) == looks


def test_lab_remeasure_refuses_a_marked_store(conn):
    marked = dataclasses.replace(smoke_data(), purpose=MARK)
    rows = conn.execute("SELECT count(*) FROM trial_moments").fetchone()[0]
    with pytest.raises(store.LabError, match="lab survivorship"):
        rm.remeasure(conn, _method(), Path(__file__), marked, require_commit=False)
    with pytest.raises(store.LabError, match="lab survivorship"):
        rm.remeasure_seed(conn, None, marked)
    assert conn.execute("SELECT count(*) FROM trial_moments").fetchone()[0] == rows


def test_lab_run_command_refuses_a_marked_store_by_its_manifest(conn, built):
    _, _, out, _, _, _ = built
    with pytest.raises(store.LabError, match="lab survivorship"):
        lab_cmd._run(conn, argparse.Namespace(method="M0001", store=out, allow_coverage=0.8))


def test_an_unmarked_store_is_not_refused():
    runner.refuse_survivorship_store(smoke_data(), "lab run M0001")
    runner.refuse_survivorship_store(object(), "lab run M0001")
```
**Impact:** none on other tests (imports `test_research_store`, `test_lab_runner` and `labkit`
helpers, as the existing suites already do).

### Step 7: Lint and the full suite
**File:** none
**Code:**
```bash
cd /home/miftah/.worktrees/seer/eodhd-survivorship-market
engine/.venv/bin/ruff check engine                                 # All checks passed!
engine/.venv/bin/python -m pytest engine/tests/test_survivorship_store.py -q   # 37 passed
engine/.venv/bin/python -m pytest engine/tests -q 2>&1 | tail -1   # 3663 passed, 411 skipped (baseline 3626 + 37)
```

### Step 8: Dry run against the real data (writes nothing)
**File:** none
**Code:**
```bash
cd /home/miftah/.worktrees/seer/eodhd-survivorship-market
engine/.venv/bin/python -m seer_engine survivorship_store \
  --source /home/miftah/seer/engine/.research \
  --cache /home/miftah/seer/engine/.cache/eodhd \
  --out /home/miftah/seer/engine/.research-sv
```
**Check:** the printed table ends `all  2542276  58.6%  81.3%`, the cleaning block reads
`kept 187 / repaired 73 / trimmed 62 / dropped 200`, and the last line says `nothing written`.
If any number differs, stop: the cache or the code differs from what this plan measured.

### Step 9: The real build (absolute paths, never a symlink for --out)
**File:** `/home/miftah/seer/engine/.research-sv/` (data, gitignored)
**Code:**
```bash
cd /home/miftah/.worktrees/seer/eodhd-survivorship-market
sha256sum /home/miftah/seer/engine/.research/* > /tmp/claude-1000/dev-store-before.sha
engine/.venv/bin/python -m seer_engine survivorship_store --build \
  --source /home/miftah/seer/engine/.research \
  --cache /home/miftah/seer/engine/.cache/eodhd \
  --out /home/miftah/seer/engine/.research-sv
sha256sum -c /tmp/claude-1000/dev-store-before.sha                     # every line OK
python3 -c "import json; print(json.load(open('/home/miftah/seer/engine/.research/manifest.json'))['fingerprint'])"
#   fd2bc190e915b0528be1520bc35ae562c5567608f581481d6e329d9143dfa753
engine/.venv/bin/python - <<'EOF'
from pathlib import Path
from seer_engine import research
d = research.load_store(Path("/home/miftah/seer/engine/.research-sv"))
print(d.purpose, d.price_fingerprint, d.fingerprint, len(d.market.history), len(d.unserved))
# survivorship-check bc5ba895a719bd805e6260299a696c493ec5124478a76e94fc5b4478423935d2 cce6fd7039ecc243640bebbe9b3134bb7950c27f01874525508ff101e19ff009 861 200
EOF
ls /home/miftah/seer/engine/.research-sv          # + cleaning_report.csv coverage_report.txt, no .tmp/.old beside it
git -C /home/miftah/seer status --short | grep research-sv   # prints nothing
```
**Impact:** writes only `/home/miftah/seer/engine/.research-sv`. The dev store is read, never written.

### Step 10: Prove the refusal on the real store, then commit
**Code:**
```bash
cd /home/miftah/.worktrees/seer/eodhd-survivorship-market
cp /home/miftah/seer/lab/lab.sqlite /tmp/claude-1000/lab-probe.sqlite   # a scratch copy: the live DB is never opened
engine/.venv/bin/python -m seer_engine lab --db /tmp/claude-1000/lab-probe.sqlite run M0069 \
  --store /home/miftah/seer/engine/.research-sv; echo "exit $?"
#   ERROR ... lab run M0069: this research store is marked 'survivorship-check' in its manifest. ...
#   Use `lab survivorship` ... Nothing ran and nothing was written
#   exit 2
git add .gitignore engine/src/seer_engine/research.py engine/src/seer_engine/lab/runner.py \
  engine/src/seer_engine/lab/remeasure.py engine/src/seer_engine/commands/lab.py \
  engine/src/seer_engine/survivorship.py engine/src/seer_engine/commands/survivorship_store.py \
  engine/tests/test_survivorship_store.py
git commit   # on feature/eodhd-survivorship-market only; never main, never lab/lab.sqlite
```
The probe runs against a scratch copy of the lab DB (a Sera batch may be writing the live one);
the refusal is raised in `_run` before `discover()`, so even the copy is not written. Commit message:
`engine: survivorship-check store — cleaned EODHD bars for the 522 unserved members, purpose mark, refusals` plus the attribution lines.

## Verification

**Build:** `engine/.venv/bin/ruff check engine` -> `All checks passed!`
**Tests:** `engine/.venv/bin/python -m pytest engine/tests -q` -> 3663 passed, 411 skipped (no Postgres; baseline before the phase 3626 passed, 411 skipped; with Postgres the skips run and pass as before)
**Manual check:** `python -m seer_engine survivorship_store --report --out /home/miftah/seer/engine/.research-sv` prints the coverage table above; `cleaning_report.csv` has 523 lines (header + 522); `unserved.csv` has 201 lines.
**Exit criteria:**
- `/home/miftah/seer/engine/.research-sv` loads with `research.load_store`, `purpose == "survivorship-check"`, price fingerprint `bc5ba895…` (not `5451195f…`), 861 of 1,061 symbols served;
- `/home/miftah/seer/engine/.research/manifest.json` fingerprint is still `fd2bc190e915b0528be1520bc35ae562c5567608f581481d6e329d9143dfa753` and every dev file hashes as before;
- `lab run M0069 --store <sv>` exits 2 with the refusal before anything is written;
- `cleaning_report.csv` lists all 522 cached symbols with an action and a reason; `coverage_report.txt` shows per-year coverage before/after and the 239 members still missing;
- the suite passes; nothing under `engine/.research-sv` is tracked or untracked-visible in either checkout.

## Handoffs

- **R7 / R3 (phase 2):** the 200 still-unserved symbols, especially the 111 whose EODHD code only
  has a post-2015 series and the 47 that never trade inside their membership, are the alias-fill
  candidates; the 41 `null` series likewise. Phase 2 supplies `extra_sources` to `plan_build` and an
  `alias_report.csv` through `extra_reports`, and wires its flags into `run()`.
- **Not done by any phase (Decision D11):** the 39 dev-served symbols with no bar on any member day
  (ACV, AMH, AR, ...) — yfinance served a later company under the code. Fixing them would mean
  replacing dev rows, which `merge_sorted_lines` refuses by design; they stay in the 239 still
  missing and phase 5's insight names them as residual uncertainty.
- **R8 (phase 3):** after `market_series.csv` joins `OPTIONAL_DATA_FILES`, a rebuild (or
  `_refresh_optional` on the SV store) carries it; `_refresh_optional` already keeps `purpose`.
- **R4 (phase 4):** require `data.purpose == research.SURVIVORSHIP_PURPOSE`; never route through
  `run_method`/`remeasure`. The refusal message already names `lab survivorship`.
- **Phase 5:** the `sync-research-store` skill must not sync `engine/.research-sv` under the dev
  store's key (its own prefix or none); the explore skill's Promotion step 0b should name the store
  and the command. Copy `coverage_report.txt` and `cleaning_report.csv` (derived, no vendor rows) to
  `docs/lab/survivorship/` if wanted.
- **Not done, deliberately:** the dev store's own junk (COMS, MCIC, CPWR one-day moves of 3x-140x
  in `engine/.research/bars.csv`) is carried byte for byte; cleaning it would move the dev price
  fingerprint. Worth an idea card, not this phase.

## Rollback

`rm -rf /home/miftah/seer/engine/.research-sv` (the dev store was never written), remove the three
lines from `/home/miftah/seer/.git/info/exclude` if wanted, and `git revert` the phase commit on the
feature branch. No lab DB row, trial, moment or look was produced, so nothing else needs undoing.

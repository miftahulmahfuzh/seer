# Plan: EODHD month — survivorship-check store, its measurement, and market series

**Slug:** eodhd-survivorship-market
**Date:** 2026-10-10 18:15
**Analysis:** `20261010-181548-E7HD_code_analyzer.md`
**Worktree:** `/home/miftah/.worktrees/seer/eodhd-survivorship-market`
**Branch:** `feature/eodhd-survivorship-market` (base: `origin/main` @ `5e5ec5c`)
**Phases:** 5
**Status:** planned
**Coordinator:** —

---

## Why

From `docs/plans/HANDOVER_20261010-eodhd.md` (verbatim excerpts — the handover is the spec):

> The owner paid **$19.99 for one month of EODHD's "EOD Historical, All-World" plan** (personal
> licence) and canceled the same day. **The key stays valid until 2026-11-10.** […] The owner's
> instruction: *exploit this paid data as much as possible, and get a definite answer on whether it
> can improve our methods.* Passing the gate is not required. Clarity is.

> **The question it answers:** *how much does the missing-dead-companies gap flatter lab results?*
> Every lab result so far was measured on a store that holds about 59% of index-member days, and
> mostly the survivors.

> 1. **A separate dev-window store**, e.g. `engine/.research-sv`: today's dev store plus EODHD bars
>    for the unserved members, in the same conventions, clipped to the dev window. It needs its own
>    price fingerprint, and the existing `engine/.research` stays byte-identical. Prefer building it
>    from the cache by script, with no network.
> 2. **Cleaning that is honest about bankruptcies:** Split-adjust from `splits/`. Detect reused-ticker
>    splices and keep only the segment that overlaps the membership, or drop the symbol. […] Drop or
>    repair the absurd errors. Keep genuine collapses. A company that went to near zero while a
>    member is exactly what this store is for. Every dropped symbol is listed with its reason in a
>    report file inside the store, never silently.
> 3. **A coverage report**: year by year, member-days covered before and after, and the list of
>    members still missing.
> 4. **The measurement.** A **report-only** command, in the spirit of `lab costs` and `lab regime`
>    (no new trial row, no change to N, no status change, journaled with `lab note`/`lab insight`).
>    It reruns a recorded method's variants on the survivorship-check store and prints them side by
>    side with the dev-store result: funded CAGR vs SPY, max DD, PF, DSR inputs, 2009-2015 era,
>    walk-forward folds. Run it on the roster and the near misses (M0007, M0021, M0022, M0029, M0032,
>    M0020, M0019, M0011, M0033, M0063, M0070, M0069) and on this Sera batch's dividend-date methods.
>    **M0069 (buying long-term losers) is the sharpest test**.
> 5. **A plain-words lab insight** (the owner is not a trader; no ids or code) saying how much
>    survivorship flattered results, which methods it changed, and what 1996-97 and the 201
>    still-missing members leave uncertain.

> ### 5.2 Market series strategies can read
> […] it must be read point in time (only values dated on or before the allocator's `data_date`),
> and it must not move the price fingerprint. Minimum set: VIX (1990+), VIX3M (2007-11+, with VXV
> 2006-07+ as its earlier name), IRX, FVX, TNX and TYX […] Move their status [M0039, M0038] from
> `blocked-data` back to `idea` once the data loads, with a note saying how much of the dev window
> each covers.

## Requirements

| ID | What the user asked for | Phases |
|---|---|---|
| R1 | Separate dev-window survivorship-check store `engine/.research-sv`, cache-built, own price fingerprint, dev store byte-identical | 1 |
| R2 | Honest cleaning: split-adjust, splice detection, absurd-error repair/drop, collapses kept, every drop listed in a report inside the store | 1 |
| R3 | Coverage report: member-days per year before/after, still-missing list | 1, 2 |
| R4 | Report-only measurement command, dev vs survivorship store side by side, journaled, N unchanged | 4 |
| R5 | Run it on the roster, the near misses and the Sera dividend-date methods; M0069 first | 5 |
| R6 | Plain-words lab insight on how much survivorship flattered results | 5 |
| R7 | Decide the gate's use of the store, and whether to spend calls on the 201 empty members | 2 (calls), 5 (gate) |
| R8 | Market series as point-in-time allocator data without moving the price fingerprint | 3 (code, proven on copies), 5 (SV store file); the real dev store file is post-landing L1 |
| R9 | M0039 and M0038 back from `blocked-data` to `idea` with a coverage note | 3 (`lab unblock`, measured notes); the two moves are post-landing L2, once the data loads on `main` |

## Scope

**In scope:** a pure cleaning/merge library and a cache-only build command for `engine/.research-sv`;
a `purpose` marker on that store's manifest and refusals in every trial-writing path; an alias
resolution + targeted EODHD fetch for members with no usable series, fed to the build as second
candidates; an optional `market_series.csv` store file read point in time through `Market.series`;
`lab unblock`; `lab survivorship` (report only); running it and journaling the answer; skill docs;
the post-landing dev-store refresh and the two unblocks.

**Out of scope:** rebuilding or editing `engine/.research`'s price files; building the test-window
store; any change to `lab/hardgate.py` promotion rules (Decision D1); new trading methods using
the series (the explore loop does that once M0039/M0038 read `idea`); bulk `eod-bulk-last-day`
crawls (Decision D2); repairing the 39 dev-served symbols with no member-day bars (Decision D11);
the web app.

## Invariants

1. `engine/.research`'s `bars.csv`, `dividends.csv`, `fx.csv`, `unserved.csv`, `fundamentals.csv`
   and `dividend_announcements.csv` stay byte-identical. Its price fingerprint `5451195f…` never
   moves. The only change to that directory in this whole set is the optional `market_series.csv`
   written through `_refresh_optional` by **post-landing step L1**, after the code that can load it
   is on `main` (Decision D8). No phase writes it.
2. No raw vendor row is ever committed or written under `web/`. `engine/.research-sv*` is
   gitignored (and excluded in the shared `.git/info/exclude`) before anything is built. Derived
   numbers (coverage tables, report CSVs) may be committed.
3. No `trials`, `trial_moments`, `trial_funding` or `trial_provenance` row is ever produced from the
   survivorship-check store; `store.dev_trial_count` and `store.test_looks` are unchanged by every
   phase.
4. Stores are addressed by **absolute path in the main checkout**:
   `/home/miftah/seer/engine/.research` (read only until L1) and `/home/miftah/seer/engine/.research-sv`
   (written only by `survivorship_store --build` and phase 5's `market_series --refresh`). Never
   point a build or refresh at a symlink (`_swap_in` would move the link). The worktree gets its own
   `engine/.venv` (`/home/miftah/.pyenv/versions/3.11.0/bin/python -m venv`), read-only symlinks for
   `engine/.research` and `engine/.cache`, and exclude lines for those symlinks in the file
   `git rev-parse --git-path info/exclude` names (phase 1 Step 0; every later phase repeats it
   idempotently).
5. Lab database writes go to the main checkout's DB (`SEER_LAB_DB=/home/miftah/seer/lab/lab.sqlite`)
   — only in phase 5 and post-landing L2-L3. Phases 1-4
   write no lab row (probes and smoke runs use scratch copies). Never `git add lab/lab.sqlite`;
   staging only via `lab stage`, under Decision D6.
6. The test-window store is never built.
7. EODHD network only in phase 2 (before 2026-11-10). Every store build and refresh reads the cache
   only.
8. The full engine suite (`engine/.venv/bin/python -m pytest engine/tests -q`) passes at the end of
   every phase.

## Phases

| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID | Card |
|---|-------|-----------|---------|-------|-----------|------------|------|--------|------|
| 1 | Survivorship-check store: cleaning, build, marker, reports | R1, R2, R3 | `seer_engine` (research, survivorship, commands, lab/runner, lab/remeasure) | 8 | — | HARD | `.workflows/plan/eodhd-survivorship-market/phase-1.md` | P1-ENG-8X1K (done 2026-10-10) | — |
| 2 | Alias fill for the empty members | R7, R3 | `seer_engine` (eodhd, survivorship_alias, commands/survivorship_store) | 6 | 1 | HARD | `.workflows/plan/eodhd-survivorship-market/phase-2.md` | P1-ENG-SLCU (done 2026-10-10) | — |
| 3 | Market series store file, `Market.series`, `lab unblock` | R8, R9 | `seer_engine` (research, backtest/market, lab/runner, commands) | 8 | 1 | NORMAL | `.workflows/plan/eodhd-survivorship-market/phase-3.md` | P1-ENG-9L1M (done 2026-10-10) | — |
| 4 | `lab survivorship` report command | R4 | `seer_engine` (lab, commands/lab) | 3 | 1, 3 | HARD | `.workflows/plan/eodhd-survivorship-market/phase-4.md` | P1-ENG-AMKN | — |
| 5 | Run, journal, document | R5, R6, R7, R8 | lab DB, docs, skills | 6 | 2, 3, 4 | NORMAL | `.workflows/plan/eodhd-survivorship-market/phase-5.md` | P1-ENG-STM7 | — |

### Phase 1 — Survivorship-check store
**Satisfies:** R1, R2, R3
**Owns:** the set's environment recipe (venv, symlinks, worktree exclude lines) and the main
checkout's exclude lines for `engine/.research-sv*`; `.gitignore` entries for
`engine/.research-sv{,.tmp,.old}/`; new pure module `engine/src/seer_engine/survivorship.py`
(`SourceSeries`, `RawBar`, `Split`, `RawDividend`, `CleanBar`, `Cleaned`, `read_series`,
`parse_*`, `member_sessions`, `clean_symbol(series, member_days, sessions)`, `best_of`, the eleven
rules, coverage arithmetic); new command `engine/src/seer_engine/commands/survivorship_store.py`
(`plan_build(..., extra_sources=)`, `write_store(..., extra_reports=)`, `--build`, `--report`,
`--out`, `--cache`, `--source`); in `research.py`: `SV_STORE_DIR`, `PURPOSE_KEY`,
`SURVIVORSHIP_PURPOSE`, `PURPOSES`, `ResearchData.purpose`, `_seal(purpose=)`, `_refresh_optional`
carrying `purpose`, `declared_purpose`, `_read_manifest` validating it; refusals in
`runner.run_method`, `runner.run_test`, `remeasure.measure/remeasure/remeasure_seed` and
`commands/lab.py:_run`; `cleaning_report.csv` and `coverage_report.txt` inside the store, outside
the manifest; 37 tests; the real build into `/home/miftah/seer/engine/.research-sv`.
**Does not touch:** `engine/.research` (read only), `eodhd.py`, `backtest/market.py`,
`commands/lab.py` beyond the `_run` refusal, `OPTIONAL_DATA_FILES`.
**Exit criteria:** the real SV store builds offline and loads with `research.load_store`
(`purpose == "survivorship-check"`, price fingerprint `bc5ba895…`, 861 of 1,061 served); the dev
store's manifest still reads `fd2bc190…`; `lab run --store <sv>` is refused before any trial is
written; `cleaning_report.csv` lists all 522 cached symbols (kept 187 / repaired 73 / trimmed 62 /
dropped 200); `coverage_report.txt` shows 58.6% → 81.3% and the 239 still missing; tests pass
(3,663 passed).

### Phase 2 — Alias fill for the empty members
**Satisfies:** R7 (the calls decision), R3 (refreshed coverage)
**Owns:** offline alias resolution for phase 1's 200 dropped symbols (EODHD code candidates from
`symbols-US-delisted.json` / `symbols-US-live.json` by hint, `ticker_cik.csv` name,
`ticker_aliases.csv`, class spelling, bankruptcy stem and code variants; accepted only when the
series has member-day rows and cleans to a usable action through phase 1's `clean_symbol`);
`eodhd.Client.eod/splits/dividends_by_code` and `exchange_code`; `survivorship_store
--resolve-aliases / --fetch-aliases [--symbols] [--refetch]` writing
`engine/.cache/eodhd/alias/{probe/<CODE>,<SYM>}.json` only; the build offering accepted alias series
to `plan_build(extra_sources=)` by default (`--no-aliases` off) and writing `alias_report.csv`
through `write_store(extra_reports=)`; `engine/data/eodhd_alias_hints.csv`; the rebuilt SV store.
**Does not touch:** `research.py`, `survivorship.py`, `commands/lab.py`, `backtest/`, the original
cache folders.
**Exit criteria:** every one of the 200 targets has an `alias_report.csv` line (code + why, or "no
candidate code" / "no candidate fits" / "ambiguous"); resolved series fetched with ≤ 4 `/eod`
probes + 1 `/splits` per overlapping probe + 1 `/div` per accepted member (≈500 calls); filled
symbols read `source = eodhd-alias` in `cleaning_report.csv`; the SV store rebuilt offline and its
coverage report shows the gain; the original cache hashes unchanged; tests pass without network.

### Phase 3 — Market series
**Satisfies:** R8, R9 (code and measured notes; the real dev-store file and the two status moves are
post-landing L1-L2)
**Owns:** `research.MARKET_SERIES_FILE = "market_series.csv"` (header `series,date,value`) joined to
`OPTIONAL_DATA_FILES` (and the pinned test updated deliberately), reader, `refresh_market_series`
via `_refresh_optional`; `backtest/market.py` `MarketSeries` (point-in-time `value_on`, `upto`,
`names`, `first_date`) and `Market.series` defaulting to `EMPTY_SERIES`; `runner.preflight_data`
refusing a `"series"` method on a store without series; new command `commands/market_series.py`
(report + `--refresh`, cache-only, TNX/FVX/TYX ÷ 10, VXV spliced before VIX3M, NYSE sessions only,
clipped to the window); `lab unblock MNNNN --note …`; the refresh proven on scratch copies of both
stores.
**Does not touch:** survivorship cleaning, `lab survivorship`, the real dev store, the real SV
store, the lab DB.
**Exit criteria:** on copies, `market_series --refresh` adds the file with neither price
fingerprint moving and the SV mark kept (43,317 rows, 10 series); `Market.series.value_on` never
returns a value dated after `d` (tested); a series method is refused on a store without series
(tested); `lab unblock` tested; tests pass.

### Phase 4 — `lab survivorship`
**Satisfies:** R4
**Owns:** new `engine/src/seer_engine/lab/survivorship_check.py` (`SV_PURPOSE =
research.SURVIVORSHIP_PURPOSE`, `peek_purpose` over `research.declared_purpose`, `CSV_HEADER`) and
the `survivorship` subcommand in `commands/lab.py` (docstring entry, subparser, handler,
`_HANDLERS`): for each named method, every variant with a recorded dev trial is re-run at its
recorded capital and funding on the dev store, then on the SV store (never both in memory); the dev
re-run must reproduce the recorded total return (else the report says so); per variant and store:
yearly return (money-weighted when funded) vs SPY's, max DD, PF, trades, daily Sharpe / T / skew /
kurt and the DSR at the recorded N and var_trials, the 2009-2015 era edge; per method and store:
walk-forward record; one plain-words `observation` per method (unless `--no-journal`); optional
`--csv`; N and test looks printed before and after.
**Does not touch:** any trial-writing path, `hardgate.py` rules, stores, `research.py`.
**Exit criteria:** the command runs on fixtures end to end, lowers the fixture method on the
collapse store, refuses a wrong store pair / same store twice / test-window store / unknown or
unrun method, never writes trial rows; a `--no-journal` smoke run of M0069 on the real stores
completes against a scratch DB copy.

### Phase 5 — Run, journal, document
**Satisfies:** R5, R6, R7 (the gate decision), R8 (the SV store's series file)
**Owns:** Step 0's guarded `git merge origin/main` (Decision D12); the final offline rebuild of
the SV store plus `market_series --refresh` on it; running `lab survivorship` on M0069 first, then
the roster/near misses and the dividend-date methods picked at run time (any method reading
`Market.dividends` with dev trials: M0051, M0076-M0079, M0081-M0083, M0085, M0086 on today's DB);
the derived grid, README and insight under `docs/lab/survivorship/`; one plain-words `synthesis`
insight; the explore skill (Promotion step 0b, "Testable?" market series, `lab survivorship` /
`lab unblock` in the command block) and the sync skill naming the new store; the handover's Done
line; staging per D6; the post-landing L0-L3 block repeated in its completion note (Step 14). Runs
no L step.
**Does not touch:** engine code, beyond a fix a run proves necessary (which then gets its own
test); the dev store.
**Exit criteria:** every listed method has a journaled observation and grid rows; `guard.py`
passes (N, looks, dev manifest unchanged; no trial on the SV store); the synthesis insight is in
plain words; skills updated; branch pushed; staging per D6 done or deferred with a reason; the
completion note ends with the post-landing block.

## Post-landing (runs in the main checkout, after the merge)

**Who runs it.** The session that lands the set, as its **final act**: under
`/analyze-orchestrator`, the coordinator, after Step 5's `land --step push` has put the merge on
`origin/main` (worktree `cleanup` may already have run: nothing below needs the worktree) and
before its final `pusher`, so the close-out report carries each L step's outcome. Under one-phase-
at-a-time `/implement`, the completion handler that merges the last phase. If neither runs it,
phase 5's completion note carries the same block (phase 5 Step 14) for a human. No phase runs any
L step, and no phase depends on anything an L step produces.

**Where.** In the main checkout, `/home/miftah/seer`, with the **main checkout's venv** (an
editable install of `/home/miftah/seer/engine/src`, so once L0 has fast-forwarded `main` it runs
exactly the landed code). Never the worktree's venv (it may be gone) and never a symlinked store.

**Re-running.** Every step checks its own end state first and is a no-op when already done, so
the whole block may be re-run top to bottom after an interruption. No step asks a question.

```bash
MAIN=/home/miftah/seer
PY=$MAIN/engine/.venv/bin/python
export SEER_LAB_DB=$MAIN/lab/lab.sqlite
```

**L0 — guard: the main checkout carries the landed code.** The live Sera batch loads the dev store
with the main checkout's code, and only the landed code accepts a manifest listing
`market_series.csv`:
```bash
git -C $MAIN fetch origin main
grep -q MARKET_SERIES_FILE $MAIN/engine/src/seer_engine/research.py \
  || git -C $MAIN merge --ff-only origin/main
$PY -c "import seer_engine, sys; from seer_engine import research as r; \
assert seer_engine.__file__.startswith('$MAIN/engine/src/'), seer_engine.__file__; \
assert 'market_series.csv' in r.OPTIONAL_DATA_FILES and hasattr(r, 'SURVIVORSHIP_PURPOSE'); print('READY')" \
  || echo DEFER
```
On `DEFER` (the fast-forward was refused: a dirty file the landing touches, or a diverged local
`main`; or the venv does not import the landed code), skip L1-L3 and write in the close-out note:
"post-landing L1-L3 pending: main checkout not at the landed code". Never force, stash or reset the
main checkout (the Sera batch's lab DB lives there).

**L1 — market series into the real dev store, then push it.** Skip the refresh when the store
already lists the file:
```bash
python3 -c "import json,sys; sys.exit(0 if 'market_series.csv' in json.load(open('$MAIN/engine/.research/manifest.json'))['files'] else 1)" \
  && echo "L1 refresh already done"
```
Otherwise wait for quiet. `_refresh_optional` swaps the directory in place, so a process inside
`load_store` at that moment fails its sha check (no trial is written, but the run is wasted). Use a
Monitor until-loop polling every 60 s, never a foreground sleep:
`until ! pgrep -f '[s]eer_engine.*( lab .*(run|remeasure|costs|survivorship|test|walkforward|regime)| (backtest_dev|survivorship_store|research_store|dividend_announcements|market_series))'; do sleep 60; done`.
After 45 minutes, proceed when every remaining match is older than 10 minutes
(`ps -o etimes= -p <pid>` > 600: it finished loading). Then:
```bash
mkdir -p /tmp/claude-1000/postland
[ -f /tmp/claude-1000/postland/research-manifest-before.json ] \
  || cp $MAIN/engine/.research/manifest.json /tmp/claude-1000/postland/research-manifest-before.json
cd $MAIN && $PY -m seer_engine market_series --refresh --store $MAIN/engine/.research --cache $MAIN/engine/.cache/eodhd/market
#   must print "price fingerprint 5451195fd552e208eaadfc6bc89241b9b8e3e6ccb0f4c447a84bbc4f32e7d90a (unchanged)"; exit 0
$PY - <<'EOF2'
import json
from seer_engine import research
dev = "/home/miftah/seer/engine/.research"
a = json.load(open("/tmp/claude-1000/postland/research-manifest-before.json"))["files"]
b = json.load(open(f"{dev}/manifest.json"))["files"]
assert all(b[k] == v for k, v in a.items()), "a carried file changed"
d = research.load_store(dev)
assert d.price_fingerprint.startswith("5451195f") and d.purpose is None and len(d.market.series) == 43317
print("L1 OK", d.fingerprint)
EOF2
python3 $MAIN/.claude/skills/sync-research-store/sync_store.py status
python3 $MAIN/.claude/skills/sync-research-store/sync_store.py push
```
The new full fingerprint should equal the one phase 3's completion note recorded for its copy; a
different value with the checks above passing is recorded, not a stop. A failed check: run the
rollback below and record it. No Blob token: record "dev store not pushed: no Blob token"; do not
block. A re-run's push of an unchanged store is a no-op (content-addressed).

**L2 — unblock M0039 and M0038.** First re-read the coverage from the real store (read only):
```bash
cd $MAIN && $PY -m seer_engine market_series --store $MAIN/engine/.research --cache $MAIN/engine/.cache/eodhd/market
#   expect: VIX3M member days 2331 (46.8%), T10Y member days 4966 (99.6%),
#   "differ on 9, by at most 1.05 (2014-10-15)"
```
If a printed number differs from the note below, replace that number in the note with the printed
one before running it (mechanical; no other wording changes). Then:
```bash
$PY -m seer_engine lab unblock M0039 --note \
"The fear index and its three-month version now load from the research store's market series (the store calls them VIX and VIX3M; the three-month series was named VXV until November 2007, and the store uses the newer name wherever both exist). The three-month series starts on 17 July 2006, so this gate can be tested on 2,331 of the 4,984 trading days the dev window holds index members: 46.8%, about 9.3 of 19.8 years, mid-2006 to October 2015. That span includes the 2008 crash, the May 2010 flash crash and the August 2011 downgrade. It does not include the mid-1998 fall this idea was written for, nor 2000-2002. The two names of the three-month series agree on 1,987 of the 1,996 days they overlap and differ by at most 1.05 points (15 October 2014). A fair test compares the gate with the same book over the same 2006-2015 span, not over the whole window."
$PY -m seer_engine lab unblock M0038 --note \
"Only the yield-curve half arrived. The 13-week Treasury bill and the 5-, 10- and 30-year Treasury yields, in percent, now load from the research store's market series (the store calls them T13W, T5Y, T10Y and T30Y). The longer yields start on 2 November 1993 and the bill on 29 January 1993. The 10-year minus 13-week spread exists on 4,966 of the 4,984 trading days the dev window holds index members (99.6%). The 18 missing days are bond-market holidays, where the last published yield carries over, so the spread covers the whole dev window: 19.8 of 19.8 years. Two differences from the idea as written. First, the spread is 10-year minus 13-week bill, not 10-year minus 2-year: no 2-year series was available. Second, the credit-spread half (corporate BAA yield minus the 10-year) and the inflation-protected yield are still unavailable, because the paid data plan has no corporate or inflation-protected bond yields. So only the yield-curve gate is testable, and a test must say it tests that half alone."
```
A method that is no longer `blocked-data` is refused (exit 2) and left as it is; that is the
re-run case. Record it and go on.

**L3 — stage per Decision D6.** Only when no `sera-*` tmux window and no lab writer is alive
(phase 5 Step 13's two checks); then, in `$MAIN` on `main` with an empty index:
`$PY -m seer_engine lab stage`, check `git diff --cached --name-only` is exactly `lab/lab.sqlite`
and `web/data/lab.json`, commit, `git push origin main` (rejected push: leave the commit local and
say so; never pull or rebase here). Otherwise the Sera coordinator's next `lab stage` carries the
rows; record that. Nothing staged when nothing changed: a re-run is a no-op.

**Rollback of L1/L2:** restore `/tmp/claude-1000/postland/research-manifest-before.json` into the
dev store and delete its `market_series.csv` (the six other files never changed; `load_store`
verifies against `fd2bc190…` again), or `sync_store.py pull --force` the previous version;
`lab block M0039 --on "<old blocked_on>"` (and M0038) plus a `lab note` saying why.

## Reconciliation Log

| # | Conflict | Class | Resolution |
|---|---|---|---|
| 1 | Phase 2 assumed `clean_symbol(symbol, RawSeries, intervals, *, end)`, `RawSeries`, and a `post_clean` hook; phase 1 ships `SourceSeries`, `clean_symbol(series, member_days, sessions)`, `best_of`, `plan_build(extra_sources=)`, `write_store(extra_reports=)` | Unmet assumption / contract drift | Phase 2 rewritten to phase 1's API: `phase1_clean(series, intervals)` adapter (same sessions and member days as `plan_build`), `targets` via `read_series`, `series_of`, `alias_sources` → `extra_sources`, `report_rows` after `best_of` chose, `AliasFill.report` → `extra_reports`; `substitute`/`read_primary`/`alias_hook` removed; phase 1's `run()` quoted and replaced whole; tests rewritten (fake clean signature, report test, a real build test) |
| 2 | Phase 2's target count (199 empty, 157 with another code) vs phase 1's 200 dropped (111 post-2015, 47 reused, 41 null, 1 absurd) | Contract drift | Target set = phase 1's 200 drops; the 199 are exactly 111+47+41, FBF is the 200th; expectations in phase 2 Steps 7-8 and the alias report say 200 (157-158 with candidates) |
| 3 | Phase 2 asked phase 1 to add worktree exclude lines for the `engine/.cache` / `engine/.research` symlinks; phase 1 claimed the links were already ignored | Gap / contract drift | Added to phase 1 Step 0 via `git rev-parse --git-path info/exclude`; phase 1 Step 1's main-checkout exclude lines for `.research-sv*` kept; phases 2-5 repeat the recipe idempotently |
| 4 | Environment recipes differed (`python3`, `python3.11`, pyenv 3.11.0; `SEER_LAB_DB` exported in phase 3, which no longer writes the DB) | Contract drift | One recipe (phase 1 Step 0) everywhere; `SEER_LAB_DB` only in phase 5 and L2 (Invariant 5 reworded) |
| 5 | Phase 3 refreshed the shared dev store with `market_series.csv` mid-set; the main checkout's `_read_manifest` (which the live Sera batch runs) refuses a manifest listing a file outside its `OPTIONAL_DATA_FILES`, so every main-checkout `lab run` would fail until landing; the sync push would spread it | Broken-build (live system) | Real dev refresh, Blob push and the M0039/M0038 unblocks moved to post-landing L0-L3 (D8); phase 3 proves the refresh on a scratch copy; R8/R9 rows updated; Invariant 1 reworded |
| 6 | Phase 3 refreshed the real SV store while phase 2 (parallel) rebuilds it, and phase 5 asserted the rebuild carries `market_series.csv` from the dev store | Ordering / file collision | Phase 3 checks the mark on an SV copy only; phase 5 runs `market_series --refresh` on the SV store after its final rebuild (D9); R8 added to phase 5's Satisfies |
| 7 | Phase 3's restore-the-manifest fallback for a dropped `purpose` | Dead branch | Phase 1's `_refresh_optional` carries `purpose` (verified in its diff and test); the fallback became a check-only assertion on a copy |
| 8 | Phase 4 defined `SV_PURPOSE = "survivorship-check"` and its own manifest peek | Duplicate work | `SV_PURPOSE = research.SURVIVORSHIP_PURPOSE`; `peek_purpose` wraps `research.declared_purpose` (`import json` dropped); confirmed `load_store(sv_dir)` needs no keyword |
| 9 | Phase 4 handed the `commands/lab.py` docstring entry to phase 5, which must not touch engine code | Contract drift | Docstring entry is phase 4 Step 2d (after the `lab costs` block) |
| 10 | Phase 5's `COL`/`METHOD_COL` and `store` labels assumed `method,variant,funded_cagr,…`, `sv` | Contract drift | Aligned to phase 4's `CSV_HEADER`: `method_id`, `candidate_id`, `yearly_return`, `spy_yearly_return`, `max_drawdown`, `profit_factor`, `era_edge`, `wf_won`, `wf_scored`, store `survivorship`, `reproduced` `1`/`0` |
| 11 | Phase 5 asserted the SV store's `dividend_announcements.csv` is byte-identical to the dev store's; phase 1 re-matches it | Contract drift | Assertion limited to `fundamentals.csv`; announcements checked present |
| 12 | Phase 5 assumed `--build` picks up aliases with no flag | Unmet assumption | Confirmed: phase 2's rewired `run()` offers aliases by default, `--no-aliases` turns it off |
| 13 | "30%" drawdown bar mentioned in phase 5 | Contract drift | Removed; the bar is `metrics.MAX_DRAWDOWN = 0.20` throughout |
| 14 | Phase 5 Step 0 `git merge origin/main` could stop an unattended run on a conflict | Ordering | Guarded merge (D12): plan files ours, lab DB/snapshot theirs, anything else aborts and the phase continues; suite failure after merge resets to `ORIG_HEAD` |
| 15 | Phase 3's docs handoff (`lab unblock`, `Market.series`, series names/units in the explore skill) had no owner | Gap | Phase 5 Step 9 Edits C and D |
| 16 | Phase 1's optional handoff of the 39 dev-served symbols with no member-day bars had no owner | Gap | Decided not done (D11); named as residual uncertainty in phase 5's README |
| 17 | `commands/lab.py` edited by 1 → 3 → 4; `research.py` and `lab/runner.py` by 1 → 3; `commands/survivorship_store.py` by 1 → 2 | File collision | Checked: distinct anchors in every pair; phase 3 and 4 Files tables give the post-phase-1 line shifts and anchor by quoted text; phase 2 quotes `run()` and the import block as phase 1 leaves them |
| 18 | Phase 4's real-store smoke run and phase 2's SV rebuild can overlap (phase 4 does not depend on 2) | Ordering | Both wait for quiet (`pgrep` Monitor loop) before touching the SV store |
| 19 | Index D2 and phase-2 exit said "≤ 3 calls each"; phase 2 probes up to 4 codes | Contract drift | Index updated to ≤ 4 `/eod` + 1 `/splits` per overlapping probe + 1 `/div` (≈500 calls) |

| 20 | (round 2) Post-landing L0-L3 ran "from this worktree's venv", but the orchestrator's `land --step cleanup` deletes the worktree; executor and place were not pinned to the landing order (`land --step push` → cleanup → pusher) | Unmet assumption | Section retitled "runs in the main checkout, after the merge"; executor = landing coordinator (or completion handler) as its final act, after `push`, before the final pusher; `PY` = main checkout's venv (editable on `main`); L0 fetches, fast-forwards and asserts the venv imports the landed code (D15) |
| 21 | (round 2) L steps were not all safe to re-run (L1 re-swapped the store and overwrote its before-manifest; L2/L3 re-run behaviour implicit) | Contract drift | L1 skips when the manifest already lists `market_series.csv`, keeps the first before-manifest, verifies carried hashes + price fingerprint + 43,317 rows; L2's exit 2 on a non-blocked method is the re-run case; L3 no-op when nothing changed |
| 22 | (round 2) Phase 3 Step 14 told a phase session to edit the plan index's L2 notes; under the swarm the coordinator holds its own copy, so the edit could be lost | File collision / ownership | Phase 3 reports the 13a fingerprint and any differing numbers in its completion note; L2 re-reads coverage from the real store and substitutes differing numbers mechanically; the full-fingerprint match in L1 is recorded, not a stop (D16) |
| 23 | (round 2) Phase 5 calls phase 3's `market_series --refresh` (Step 2) but listed only 2, 4 | Ordering (incomplete edge) | Phase 5 `Depends on: 2, 3, 4` (index and plan header) |
| 24 | (round 2) Phase 2's wait-for-quiet pattern `lab survivorship` misses phase 4's smoke command line (`lab --db … survivorship`); phase 3's 13c copy of the real SV store had no wait while phase 2 may rebuild it | Ordering (parallel 2 ‖ 3 ‖ 4 on the SV store) | Patterns widened (`lab .*survivorship`, `[s]eer_engine` self-exclusion); phase 3 13c waits for quiet and re-copies once on a torn copy; phase 4's smoke reruns once after a mid-load swap |
| 25 | (round 2) Nothing told a human the L steps exist if the lander does not run them | Gap | Phase 5 Step 14 repeats the index's L0-L3 block verbatim in its completion note; phase 5 exit criteria and index Owns/Exit updated |
| 26 | (round 2) Verified, no change: phase 2's calls match phase 1's `SourceSeries`, `parse_*`, `read_series`, `member_sessions`, `clean_symbol(series, member_days, sessions)`, `best_of`, `Cleaned.source/action/reason/covered_days`, `plan_build(extra_sources=)`, `write_store(extra_reports=)` and the quoted `run()`; phase 4's `SV_PURPOSE`/`peek_purpose` match `research.SURVIVORSHIP_PURPOSE`/`declared_purpose` (OSError and ValueError both mapped); phase 5's `COL`/`METHOD_COL`/store labels are literal `CSV_HEADER` names | — | — |

## Decisions

| Fork | Chosen | Rung |
|---|---|---|
| D1 Should the gate use the SV store? | No: report-only cross-check; any change to promotion rules is a separate argued commit in `lab/hardgate.py` after reading phase 5's numbers | 5: handover's stated default + explore skill ("argued commit") |
| D2 Spend calls on the 201 empty members? | Yes, but per-code `/eod` probes (≤ 4 candidates per member), `/splits` per overlapping probe and `/div` per accepted member (≈500 calls), not `eod-bulk-last-day` (100 calls a day of the whole market, keyed by current codes) | 5: owner's "exploit this paid data as much as possible" + R1's cache-only build kept by fetching in a separate step |
| D3 How is the SV store kept out of the trial record? | Optional manifest key `purpose: "survivorship-check"`; `ResearchData.purpose`; `run_method`, `run_test`, `remeasure` and `lab run` refuse it | 1: invariant 3 |
| D4 Where do reports live? | `cleaning_report.csv`, `coverage_report.txt`, `alias_report.csv` inside the store directory, outside the manifest (the loader ignores unlisted files); derived tables copied to `docs/lab/survivorship/` in phase 5 | 5: handover R2 "a report file inside the store" |
| D5 Market series format | Optional store file `market_series.csv` (long format `series,date,value`), values normalized to the unit an allocator reasons in (yields in percent, VIX in points); series VIX, VIX3M (VXV spliced before 2007-11-13), VIX9D, VXN, VVIX, T13W, T5Y, T10Y, T30Y, GOLD | 5: handover offers either shape; the optional-file precedent keeps the price fingerprint fixed |
| D6 Who stages the lab DB? | Phase 5 (and L3) write through `SEER_LAB_DB` into the main checkout's DB; if no `sera-*` tmux window and no lab writer is alive it runs `lab stage` in the main checkout and commits + pushes the DB and snapshot; otherwise it leaves staging to the coordinator and says so | 6: convention (`store.py` comment, handover §6, Sera coordinator owns commits) |
| D7 Handover order (§5.1 first) vs parallelism | Phase 3 depends on phase 1 (both edit `research.py`); phase 4 depends on 3 (both edit `commands/lab.py`) | 6: convention (no two sessions on one file) + handover order |
| D8 When does the real dev store get `market_series.csv` (and M0039/M0038 their unblock)? | After landing (L0-L3), in the main checkout with its venv (D15), only once the main checkout carries the code; phase 3 proves the refresh on a copy | 4: index Why ("Move their status … once the data loads"), applied under reconciler rule 1 (build-green: the live Sera batch runs main's code, whose `_read_manifest` refuses the file); Invariant 1 reworded to match |
| D9 Who writes `market_series.csv` into the real SV store? | Phase 5, right after its final rebuild; phase 3 checks the `purpose` survives on a copy | 2: phase 5's exit criterion (its guard and final rebuild own the SV store) + D7's one-session-per-file convention (phase 2 rebuilds it in parallel with phase 3) |
| D10 How do alias series enter the build? | As `extra_sources` candidates to phase 1's `plan_build`, chosen by `best_of` (most member days; ties to the original); `alias_report.csv` via `write_store(extra_reports=)`; filled symbols read `source = eodhd-alias`, `code = <ALIAS>.US` in `cleaning_report.csv`. On by default, `--no-aliases` off | 3: phase 1's code blocks (built and tested) |
| D11 Repair the 39 dev-served symbols with no bar on any member day? | No: dev rows are carried byte for byte (`merge_sorted_lines` refuses a symbol in both); they stay in the still-missing list and the README names them | 3: phase 1's code blocks; invariant 1's byte-identical spirit |
| D12 Phase 5's merge of `origin/main` in an unattended run | Merge; resolve only plan files (ours) and `lab/lab.sqlite`/`web/data/lab.json` (theirs); any other conflict → `git merge --abort` and continue; suite failure after merge → reset to `ORIG_HEAD` and continue | 6: convention (no human in the loop; the landing merges `main` anyway) |
| D13 Phase 2's target set | Phase 1's 200 drops (199 with no member-day row + FBF) | 3: phase 1's measured build |
| D14 Who writes the `lab survivorship` line in `commands/lab.py`'s docstring? | Phase 4 (Step 2d), the phase that edits the file | 2: phase 5's "Does not touch: engine code" |
| D15 Who runs L0-L3, where, with which interpreter? | The landing session as its final act (orchestrator coordinator after `land --step push`, before its final pusher; else the completion handler), in `/home/miftah/seer` with `/home/miftah/seer/engine/.venv` after L0 fast-forwards `main`; DEFER without force/stash/reset if `main` cannot fast-forward | 6: convention (the orchestrator's Step 5 deletes the worktree; main's venv is an editable install of the main checkout; the Sera batch owns that checkout's working state) |
| D16 How do phase 3's measured numbers reach L1/L2? | Through phase 3's completion note and a re-read from the real store in L2 (numbers substituted mechanically); no phase edits the plan index; L1's full-fingerprint match is advisory, its price-fingerprint/carried-hash/row-count checks are binding | 4: index Why ("with a note saying how much of the dev window each covers" — the note must state the real store's numbers) + Invariant 1 (the price fingerprint is the binding check) |

## Open Questions

(none)

## Rollback

- Phase 1/2: delete `/home/miftah/seer/engine/.research-sv` and revert the commits; the dev store
  was never written. Phase 2's `engine/.cache/eodhd/alias/` can be deleted; the original cache
  folders were never written.
- Phase 3: `git revert`; it wrote only scratch copies.
- Phase 4: revert; nothing persistent.
- Phase 5: journal entries are append-only; a wrong one is answered with a correcting insight.
- Post-landing L1/L2: see **Post-landing** above.

## Next

Execute the phases one at a time, starting at phase 1:

    /implement -f EODHD_SURVIVORSHIP_MARKET_PLAN.md --phase 1

Or run the whole set as a swarm — a session per phase, concurrent wherever `Depends on` allows,
resumable on any machine:

    /analyze-orchestrator -f EODHD_SURVIVORSHIP_MARKET_PLAN.md

Whichever way the set runs, its lander finishes with **Post-landing L0-L3** above, in the main
checkout after the merge (the real dev store's market series, its Blob push, the M0039/M0038
unblocks, staging). Phase 5's completion note repeats the block for a human.

Or put them on the board first (GitHub repos only):

    /create-task --from-plan EODHD_SURVIVORSHIP_MARKET_PLAN.md

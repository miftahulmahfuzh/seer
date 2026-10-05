# Plan: Fundamental panel coverage

**Slug:** fundamental-panel-coverage
**Date:** 2026-10-05T13:36:48+07:00
**Analysis:** `20261005-133648-2XUM_code_analyzer.md`
**Worktree:** `/home/miftah/.worktrees/seer/fundamental-panel-coverage`
**Branch:** `feature/fundamental-panel-coverage` (base: `HEAD` @ `2dad9ff`)
**Phases:** 5
**Status:** reconciled
**Coordinator:** —

---

## Why

Verbatim from `docs/plans/2026-10-05-fundamental-panel-coverage.md` §8, which is the
specification for what may change and what may not:

> **Do Fix A and Fix B, and build the coverage gate.** All three are free, all three are local,
> and Fix A corrects a factual error in shipped data (525 rows claiming a membership date that
> is not theirs).
>
> Explicitly **not** in this plan:
>
> - The test-window decision (§5). It is one irreversible spend and deserves its own doc.
> - Pre-2009 fundamentals from any paid vendor (§4).
> - Gap A / delisted price bars / the $199 Massive gate. Unrelated.
> - Re-running M0005. Its id is spent; a re-test is a new variation method, and it should not be
>   minted until the coverage gate reports a number worth testing.
>
> The success criterion is **not** "a fundamentals method beats SPY". It is:
>
> 1. `ticker_cik.csv` carries each symbol's real first-membership interval, with every invariant
>    in §2 still enforced by tests.
> 2. The panel's coverage is measured and reported across the whole dev window, by a check that
>    lives in the engine rather than in a runbook snippet.
> 3. That number is honest — if it lands near 30%, the plan says so and does not claim the test
>    problem is solved.

And §5, which bounds what success can mean:

> **30% coverage will not produce a method that passes this lab's gates**, and the plan must not
> pretend otherwise. `>= 100 trades` over a window two-thirds of which holds cash is not
> reachable. Fix A and Fix B make the *data* honest; they do not make the *test* valid.

## Requirements

| ID | What the user asked for | Phases |
|---|---|---|
| R1 | Fix A (§2): re-vendor `ticker_cik.csv` with real first-membership intervals, every §2 invariant still enforced by tests | **2** |
| R2 | Fix B (§3): re-ingest at `--since-filed 2009-01-01`, and measure how much 2009–2012 XBRL actually exists | **3** |
| R3 | The coverage gate (§6.2): the check moves out of the runbook and into the engine, so no future method runs against a panel that cannot rank | **1** |
| R4 | Honest reporting (§8.3): the resulting coverage is measured across the whole dev window and written down as it is | **4, 5** |
| R5 | §6.1: `paper/store.py` must not silently build a `Market` with `EMPTY_PANEL` | **5** |

This is the post-reconciliation map and it is what `create-task` reads. Two notes on it:

- **R4 is served by two phases, and always was** — phase 4 ships the *capability* (a
  fundamentals-only store refresh, without which there is nothing honest to report about), phase
  5 does the *reporting*. The draft table named only phase 5; the phase plans named both. No step
  moved between phases to make this true, only the table.
- **R5 already landed** as `2dad9ff`, with **three** tests (not two — see `## Decisions`, row
  C4c). Phase 5 verifies it rather than re-implementing it and writes no code for it.

No requirement is unowned, so `## Open Questions` is empty.

## Scope

**In scope**

- `engine/src/seer_engine/cik.py` — `SINCE` 2015-01-02 → 2009-01-01.
- `engine/scripts/build_ticker_cik.py` — stop copying the clamp into `MANUAL`; audit the 118
  symbols the new floor admits; extend `SCREEN_EXEMPT` where the screen flags a correct row.
- `engine/data/ticker_cik.csv` — regenerated (795 → 913 symbols).
- `engine/src/seer_engine/commands/fundamentals.py` — both floors → 2009-01-01, and one local
  re-ingest against `.env.local-train`.
- `engine/src/seer_engine/fundamentals/coverage.py` *(new)* — the pure coverage measure.
- `engine/src/seer_engine/commands/research_store.py` — `--coverage`, and a fundamentals-only
  refresh that does not re-download bars.
- `engine/src/seer_engine/research.py` — that refresh.
- `engine/src/seer_engine/lab/runner.py`, `commands/lab.py` — the refusal.
- `docs/runbooks/data-pipeline.md`, `engine/data/SOURCES.md`, `engine/package_readme.md`,
  `docs/plans/2026-10-05-fundamental-panel-coverage.md` §4.

**Out of scope, and why**

- **The test-window decision (§5).** One irreversible spend; its own doc. No phase may run a
  method on the post-2015 test window, and no phase may shorten the dev window.
- **Pre-2009 fundamentals (§4).** XBRL did not exist. No vendor, no Compustat, no plan.
- **Gap A / delisted price bars / the $199 Massive gate.** Unrelated.
- **Re-running or re-minting M0005.** Its id is spent. No phase calls `lab run M0005`, and no
  phase mints a variation method.
- **A full research-store rebuild.** Two rebuilds give two fingerprints because yfinance answers
  differently day to day; phase 4 exists precisely so the bars survive byte-identical.
- **Neon.** `fundamental_facts` and `fundamentals_log` stay truncated there. Every database
  write in this set goes to `.env.local-train`.
- **`http.get_json` headers (§6.3).** Conditional in the doc on a phase already touching
  `http.py`; none does. See `## Decisions`.

## Invariants

Every phase must hold all of these. They are checkable, not felt.

1. **The tree builds and the suite passes at the end of each phase**, run as
   `"$SEER_PY" -m pytest engine/tests -q` under the set-wide **Runtime preamble** below.
   Baseline at `2dad9ff`: **2216 passed, 332 skipped**. **Each phase reports a DELTA off what it
   inherited, never an absolute** — the phases land in a swarm, so an absolute is only meaningful
   for whichever phase happens to run first. The reconciled deltas are **P1 +27, P2 +5, P3 +0,
   P4 +13, P5 +0**, counted from the plans' own test code; with all five merged off `2dad9ff`
   that is **2261 passed, 332 skipped**. What binds is the direction: no phase may reduce the
   passing count and no existing test may change its result. With
   `PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres` exported the DB tests must
   pass too — safe, because `conftest.py` gives each one a throwaway schema `t_<hex>` and never
   touches `public`, where the 1.2M training facts live.
2. **A recycled ticker never resolves to a later holder.** The defence is in the data: a row is
   truncated at the handover and the new holder is omitted. Extending a `start_date` backwards
   is allowed; **extending an `end_date` forwards is never allowed.** `CA`, `MON`, `PLL`,
   `ALTR`, `LLL`, `DTV` keep their exact end dates, and `test_vendored_recycled_ticker_*` keeps
   passing unchanged.
3. **Zero `fuzzy` rows ship.** Every `exact` and `fuzzy` candidate is read by hand before it
   becomes a row; a kept one is promoted to `manual` with a note saying what was checked.
   `engine/data/SOURCES.md` requires this and the `HAR` → `0001073146` miss is why.
4. **`NDOI` stays the file's only `NONE`, and stays its symbol's only row.**
5. **`K` → `0000055067` (Kellanova).** `0000039899` (TEGNA) must never be it. The whole
   `SPOT_CHECKS` table in `engine/tests/test_cik.py` keeps passing with its existing values.
6. **The 11 `SCREEN_EXEMPT` symbols stay exempt, each keeping its recorded reason.** New entries
   may be added; none may be removed or have its note weakened.
7. **`source` stays within the five tier labels** (`current`, `edgar`, `exact`, `fuzzy`,
   `manual`) — the `ticker_cik` CHECK constraint in `005_fundamentals.sql` is already widened to
   exactly these and no phase alters the migration.
8. **No network write and no Neon write.** The only mutated database is the one
   `.env.local-train` names. `lab run` is never invoked. `docs/plans/*.md` other than §4 of the
   target doc are not rewritten.
9. **Coverage is measured on content, never on presence.** `panel.as_of(symbol, t)` returns a
   `Snapshot` husk with `observations == {}` whenever nothing is known; any check that treats a
   non-`None` snapshot as coverage is the M0005 bug and must not appear in code, tests or docs.
10. **The plan reports what it measures.** No phase may state a coverage figure it did not run,
    and phase 5 must print the number even when it is bad.
11. **Every phase runs the worktree's code, against the local train database.** Set-wide, from
    the **Runtime preamble**: `PYTHONPATH=$SEER_WT/engine/src` over the main checkout's venv
    (never a second venv), and `SEER_ENV_FILE=/home/miftah/seer/.env.local-train` as an
    **absolute** path with the resolved DSN proved to name `localhost:55432` before any write.
    Added by reconciliation; see `## Decisions`, rows C2 and C3.

## Runtime preamble

Every phase plan opens with this block and every command in this set assumes it. It is reproduced
here because it is the one thing that, omitted, makes every other check in this document lie.

```bash
export SEER_WT=/home/miftah/.worktrees/seer/fundamental-panel-coverage
export SEER_PY=/home/miftah/seer/engine/.venv/bin/python
export PYTHONPATH=$SEER_WT/engine/src                        # wins over the editable .pth
export SEER_MAIN=/home/miftah/seer
export SEER_STORE=$SEER_MAIN/engine/.research                # the store lives ONLY here
export SEER_ENV_FILE=$SEER_MAIN/.env.local-train             # ABSOLUTE, always
export SEER_TRAIN_URL=postgresql://postgres:pg@localhost:55432/postgres
cd "$SEER_WT"
"$SEER_PY" -c 'import seer_engine, pathlib; print(pathlib.Path(seer_engine.__file__).resolve())'
# must print $SEER_WT/engine/src/seer_engine/__init__.py
```

Measured: the worktree has **no venv of its own**; `/home/miftah/seer/engine/.venv` is an
*editable* install whose `__editable__.seer_engine-0.1.0.pth` names `/home/miftah/seer/engine/src`;
and `engine/pyproject.toml` sets `testpaths` but **no `pythonpath`**, so pytest resolves
`seer_engine` through that same install. Without the preamble, phase 2 could regenerate a
913-symbol CSV in the worktree and have `test_cik.py` pass green against `main`'s 795-symbol one,
because `cik.DATA_DIR` is `Path(cik.__file__).parents[2] / "data"` and follows whichever tree
won. `engine/scripts/build_ticker_cik.py:40` self-resolves via its own `sys.path.insert`; that
rescues the generator and nothing else.

## Phases

| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID | Card |
|---|-------|-----------|---------|-------|-----------|------------|------|--------|------|
| 1 | The coverage gate: a pure measure, a CLI surface, a `lab run` refusal | R3 | `engine/src/seer_engine/fundamentals`, `commands`, `lab` | 7 | — | NORMAL | `.workflows/plan/fundamental-panel-coverage/phase-1.md` | P1-ENG-TJ4M | — |
| 2 | Fix A: re-vendor `ticker_cik.csv` back to real 2009 membership, with the `EARLY` start screen | R1 | `engine/scripts`, `engine/data`, `seer_engine.cik` | 5 | — | HARD | `.workflows/plan/fundamental-panel-coverage/phase-2.md` | P1-ENG-QD7X | — |
| 3 | Fix B: re-ingest at `--since-filed 2009-01-01` via `--symbols`, and measure 2009–2012 | R2 | `engine/src/seer_engine/commands` | 2 | 2 | NORMAL | `.workflows/plan/fundamental-panel-coverage/phase-3.md` | P1-ENG-F2BN | — |
| 4 | Refresh the store's panel without re-downloading bars | R4 | `engine/src/seer_engine` (research) | 3 | **1** | NORMAL | `.workflows/plan/fundamental-panel-coverage/phase-4.md` | P1-ENG-K8RV | — |
| 5 | Measure, report honestly, and retire the runbook snippet | R4, R5 | `docs`, `engine` (docs only) | 4 (+2 untracked) | 1, 2, 3, 4 | NORMAL | `.workflows/plan/fundamental-panel-coverage/phase-5.md` | P1-ENG-M3HE | — |

Waves the `Depends on` column implies: **{1, 2}** concurrently, then **{3, 4}**, then **{5}**.

Phase 4's edge on phase 1 is **added by reconciliation**: both phases edit
`engine/src/seer_engine/commands/research_store.py`'s `run()` and `add_arguments()`, phase 1
rewrites `run()` wholesale, and phase 4's own required branch order can only be produced by a
serialisation. A correct serialisation beats a false concurrency; see `## Decisions`, row C1.
Phase 1 and phase 2 share no file and no package. Phase 3 needs phase 2's regenerated CSV because
a pre-2015 filer cannot be resolved without it. Phase 5 needs all four because it runs them.

Phase 3's file count is **2**, not the draft's 3: its third artefact is the ingest **run**, which
writes no file in git. Phase 2's `Files` count of 5 is unchanged by the `EARLY` screen — the
screen, `EARLY_EXEMPT`, `EARLY_WINDOW_DAYS` and `periodic_dates` all land inside
`engine/scripts/build_ticker_cik.py`, which phase 2 already owned, and `engine/data/SOURCES.md`
documents them.

### Phase 1 — The coverage gate: a pure measure, a CLI surface, a `lab run` refusal

**Satisfies:** R3
**Owns:** a new `engine/src/seer_engine/fundamentals/coverage.py` (pure: no database, network,
clock or randomness — `tests/test_strategy_purity.py` territory) exporting the measure and its
constants; its export from `fundamentals/__init__.py`; a `--coverage` mode on
`commands/research_store.py` that loads the store and prints the per-year table plus one
fraction; a post-load refusal in `lab/runner.py` wired into `commands/lab.py:_run` between
`load_store` and `run_method`, with an `--allow-coverage FLOAT` escape; and tests in a new
`engine/tests/test_fundamentals_coverage.py` plus additions to `engine/tests/test_lab_runner.py`.

**Does not touch:** `cik.py`, `build_ticker_cik.py`, `ticker_cik.csv`,
`commands/fundamentals.py`, `research.py`'s build or seal path, any `docs/` file, any database.
It must work against the **current** 2.5%-coverage store, and its tests must not depend on a
store on disk.

**Contract this phase fixes for the others** (phases 4 and 5 call it, so it is settled here, not
negotiated later):

- The measure answers *"on how many sampled dev-window dates can the panel rank at least `top`
  symbols?"*, where a symbol counts only when `panel.as_of(sym, t)` has **non-empty
  `observations`** *and* its newest `filed` is within `max_stale_days` of `t` — the same gate
  `f_fundamental` applies, so the number predicts rankability rather than merely fact-existence.
- Defaults: sample monthly from `dev.MEMBERSHIP_START` (1996-01-02) through `research.DEV_END`
  (2015-10-16); `top = 20`; `max_stale_days = 400` (`f_fundamental.FundamentalParams`'s own
  default, imported, never restated).
- `lab run` refuses when the fraction is below `MIN_DEV_COVERAGE = 0.80` **and** the method has
  at least one `MarketAware` allocator (`isinstance(allocator, strategies.allocator.MarketAware)`
  — `FUNDAMENTAL` satisfies it structurally). The refusal is a `lab.store.LabError` naming the
  measured fraction, the per-year table, and `--allow-coverage`.
- `--allow-coverage F` lowers the floor to `F` for that run and prints the measured number
  loudly. It is an acknowledgement, not a bypass: it does not suppress the table.
- A method with no `MarketAware` allocator is never refused — M0001 and M0004 rank on price and
  must stay runnable against a store with no panel at all.

**Exit criteria:** `python -m seer_engine research_store --coverage --store "$SEER_STORE"`
prints, for the 2026-10-05 store, a table whose 1996–2014 rows are 0 and whose 2015 row is
non-zero, and a fraction of **`0.0378`** — measured by phase 1 during planning on that store,
under **this set's one definition of coverage: a MONTHLY sample of 1996-01-02 .. 2015-10-16
(238 dates), `top = 20`, `max_stale_days = 400`, content checked through
`Snapshot.observations`**, and reported as an **upper bound** because the measure reads no bars.

The draft of this line said *"a fraction near `0.025`"*. That was the analysis's **semiannual**
sample (1 of 40 dates) and it is not this measure; nor is the decision doc §4's `4%`, which is a
**span estimate** (nine months of 19.8 years). Three definitions were in play and one survives.
See `## Decisions`, row C4a.

A unit test builds a synthetic panel and asserts the measure returns 0.0
for a panel whose facts all postdate the window, 1.0 for one that covers it, and that a
`Snapshot` with empty `observations` counts as *not* rankable. A `lab run` test asserts the
refusal fires for a `MarketAware` method on a thin panel, does not fire for a price-only method,
and is lifted by `--allow-coverage`. Full suite green.

### Phase 2 — Fix A: re-vendor `ticker_cik.csv` back to real 2009 membership

**Satisfies:** R1
**Owns:** `engine/src/seer_engine/cik.py` (`SINCE` → `date(2009, 1, 1)` and the docstring that
explains it); `engine/scripts/build_ticker_cik.py` (the `MANUAL` start sentinel, the new audits,
`SCREEN_EXEMPT` additions, **the second `EARLY` screen — `periodic_dates`, `EARLY_WINDOW_DAYS`
and `EARLY_EXEMPT`**, accepted by reconciliation, see `## Decisions` row C5 — and the measured
counts in its module docstring); `engine/data/ticker_cik.csv` (regenerated);
`engine/data/SOURCES.md`; `engine/tests/test_cik.py` (one assertion widened, **five** tests
added).

**Does not touch:** `commands/fundamentals.py` (phase 3 owns both ingest floors),
`fundamentals/` (phase 1), `research.py` (phase 4), any `docs/` file outside `engine/data`, and
the `ticker_cik` **table** or `005_fundamentals.sql`.

**The mechanism, settled here:** `spans()` already derives every start from
`max(iv.start_date, SINCE)`, so lowering `SINCE` fixes tiers 1–4 for free. What it does **not**
fix is `MANUAL`, whose 70 entries carry *literal* start strings and roughly 60 of which hardcode
`"2015-01-02"` — a copy of the old clamp. An empty `start` cell in a `MANUAL` tuple must come to
mean *"the symbol's membership start from `spans()`"*, and every `MANUAL` start that is exactly
`2015-01-02` becomes that sentinel. Starts that are genuinely later stay literal: `WRK`
2015-07-02, `BXLT` 2015-07-01, `CMCSK` 2015-09-21, `SHPG` 2016-10-19, `BATRA`/`BATRK`
2016-04-18, `DINO` 2018-06-18, `INFO` 2017-06-02, `CSRA` 2015-11-30, `CPGX` 2015-07-02, `LILA`/
`LILAK` 2015-07-02 and the second row of each multi-row symbol. **Every `end` stays literal and
unchanged** (invariant 2).

**The work this phase cannot avoid:** 118 symbols enter scope (measured, listed in the analysis).
Most are delisted before 2015 and absent from `company_tickers.json`, so they fall to tier 2
(browse-edgar), tiers 3–4 (Massive name → `cik-lookup-data.txt`) or `MANUAL`. Seven carry
bankruptcy `Q` suffixes. The generator reports `UNRESOLVED` and `SCREEN` lists and exits 1 until
every one is resolved; each resolution is a hand-audit against
`https://data.sec.gov/submissions/CIK<cik>.json` with the finding recorded in `note`. Expect
also **new pre-2015 ticker recycling**: `cik._check_intervals` rejects overlapping intervals, so
a genuine handover is split into two dated rows, never merged.

**Exit criteria:** `engine/data/ticker_cik.csv` loads through `cik.load_index()` with 913
symbols; `cik.coverage_gaps(index, compute_universe())` is empty; zero rows carry `source=fuzzy`;
zero rows start at 2015-01-02; `NDOI` is still the only `NONE` and still alone; the generator
exits 0 with `UNRESOLVED`, `SCREEN` **and `EARLY`** all empty, every exemption carrying a reason
naming what was checked; `RECYCLED`, `SPOT_CHECKS`, `SHARE_CLASSES`, the WestRock and Alphabet
tests all pass **with their existing expected values**; `SOURCES.md`'s row and tier counts match
the file. Suite green at **+5**.

### Phase 3 — Fix B: re-ingest at `--since-filed 2009-01-01`, and measure 2009–2012

**Satisfies:** R2
**Owns:** `engine/src/seer_engine/commands/fundamentals.py` (`DEFAULT_SINCE` and
`DEFAULT_SINCE_FILED` → `date(2009, 1, 1)`, the module docstring's "since 2015-01-02", the two
`--since*` help strings, the storage paragraph's arithmetic);
`engine/tests/test_fundamentals_command.py`; and the ingest **run** itself against
`.env.local-train`.

**Does not touch:** `cik.py` or `ticker_cik.csv` (phase 2), `fundamentals/` (phase 1),
`research.py` or `engine/.research/` (phases 4 and 5), Neon, and the `005` migration.

**Prerequisite this phase must handle, measured:** the local train database has **0 `universe`
rows and 0 `bars` rows**, so `membership_windows` returns nothing and `select_symbols` raises
*"the universe table holds no member on or after …"*. `universe refresh` populates it from the
vendored CSVs and needs no network. It must run before the ingest — and it is still required
under `--symbols`, which bypasses `select_symbols` but not `plan_jobs`'s per-symbol `windows`.

**The run, as reconciled.** The decision doc §3 prescribes
`fundamentals --since-filed 2009-01-01 --retry-failed`, and **that command does not work**:
`plan_jobs` (`commands/fundamentals.py:480`) reads
`done = {STATUS_OK} if opts.retry_failed else {...}`, so `--retry-failed` *narrows* what counts
as done and still skips every CIK logged `ok`. All 773 existing filers are `ok`, so the doc's
command fetches ~120 CIKs, recovers almost none of the 2009–2012 history, and reports success.
The doc's text stays as the user wrote it — it is the record — and the command below replaces
it. See `## Decisions`, row C6.

```bash
"$SEER_PY" -m seer_engine universe refresh                        # 0 -> 1544 rows, no network
# build the member list from the SAME function the default path uses, then:
"$SEER_PY" -m seer_engine fundamentals \
    --since 2009-01-01 --since-filed 2009-01-01 \
    --symbols "$(cat /tmp/seer-fixb/symbols.txt)"                 # 912 symbols, one comma list
```

`--symbols` makes `plan_jobs` set `logged = {}` and fetch every resolved CIK — the same job list
an emptied `fundamentals_log` would produce, **without deleting a row anywhere**. The phase's
first draft truncated the log instead; `--symbols` reaches the same result and cannot destroy a
ledger if a guard above it fails, which is what invariant 8 is protecting. `--retry-failed` is
not passed and must not be: with `--symbols` the log is ignored outright.

`--since` moves too, not only `--since-filed`: with `--since` left at 2015-01-02 the member set
stays at 795 and the pre-2015 filers of the 118 new symbols are never fetched.
`options_from_args` requires `since_filed <= since`, which `2009-01-01 <= 2009-01-01` satisfies.
Measured rate on this host is 1–3 s per filer and the CIK count rises from 776 to roughly 890,
so budget ~30 minutes, not 13. The line that proves the run did the right thing is
`filers: ~890 companyfacts calls`; `0 skipped` is automatic under `--symbols` and proves nothing.

**The measurement §3 asks for, and it is this phase's deliverable as much as the rows are:**
facts by `filed` year for 2009–2012 against the 2013–2026 baseline already in the analysis
(89,913 / 91,578 / 91,921 / …). XBRL phased in by filer size — large accelerated filers from
roughly FY2009, all filers by FY2011 — so 2009–2010 will be partial and size-biased. The number
is reported whatever it is; if 2009–2010 come in much thinner than ~90k, **that** is the real
floor and phase 5 says so.

**Exit criteria:** `fundamentals_log` holds no `failed` row that is not explained, and **no log
row was deleted** to get there; a per-year `filed` count for 2009–2026 is recorded in the phase's
summary; `fundamental_facts` row count and `pg_total_relation_size` are recorded; the resolved
DSN named `localhost:55432` before anything was written. Suite green at **+0** (four existing
tests edited in place, none added or removed).

### Phase 4 — Refresh the store's panel without re-downloading bars

**Satisfies:** R4 (the capability half)
**Depends on:** **phase 1**, for one file only — see `## Decisions`, row C1.
**Owns:** `engine/src/seer_engine/research.py` (a refresh that reuses an existing store's
`bars.csv`, `dividends.csv`, `fx.csv` and `unserved.csv` byte for byte, writes a new
`fundamentals.csv`, re-seals and swaps); the `--refresh-fundamentals` flag, its two handlers and
**one additional branch in `run()`** on `engine/src/seer_engine/commands/research_store.py`;
`engine/tests/test_research_store.py`.

**Does not touch:** `build_store`'s existing download path, `load_store`, `MANIFEST_KEYS`,
`_COUNT_KEYS`, the fingerprint algorithm, `fundamentals/` (phase 1), **phase 1's `--coverage`
flag, its `_coverage` handler and its branch in `run()`** — all three must survive phase 4's
edit unmodified — and `engine/.research/` itself, which phase 5 runs.

**The shared file, settled.** The branch order in `run()` is
**guards → `--coverage` → `--verify` → `--refresh-fundamentals` → build**, and phase 4's plan
quotes the whole post-change function verbatim so the two phases cannot disagree about it.
Neither phase converts `--verify` into a mutually-exclusive argparse group; phase 4 adds one
explicit guard instead, covering both read-only flags. `--verify` with `--coverage` still
resolves to `--coverage`, which is phase 1's rule.

**Why this phase exists:** `build_store` always fetches FX and downloads every symbol's bars
before writing anything, and there is no other path into a store. Running it to pick up the new
panel would replace all 2,490,793 bar rows with whatever yfinance answers today, and the
decision doc §7 is explicit that two rebuilds give two different fingerprints for exactly that
reason — which would break comparability with the 64 trials already recorded. The counts the
manifest carries for the copied files (`bar_rows`, `dividend_rows`, `fx_rows`,
`symbols_requested`, `symbols_served`) must be carried over from the existing manifest or
recomputed from the copied files, never re-derived from a download.

**Exit criteria:** a test builds a store with facts A, refreshes it with facts B, and asserts
that `bars.csv`, `dividends.csv`, `fx.csv` and `unserved.csv` are byte-identical before and
after; that `fundamentals.csv` changed; that the fingerprint changed; that every `_COUNT_KEYS`
value is unchanged; and that `load_store` accepts the result. A second test asserts the refresh
refuses rather than half-writing when the source store is missing or fails verification. The
`.tmp`/`.old` swap discipline and the "nothing is written on failure" guarantee hold. Phase 1's
`--coverage` branch is still reachable and still wins over `--verify`. Suite green at **+13**
(ten test functions, one parametrized over the four `DATA_FILES`; the draft's "+12" was a
miscount).

### Phase 5 — Measure, report honestly, and retire the runbook snippet

**Satisfies:** R4, R5
**Owns:** running phase 4's refresh against the real store with phase 3's facts; running phase
1's `--coverage` against the result; `docs/runbooks/data-pipeline.md` — **the whole file's
fundamental-panel surface**: `:188-256` (the snippet is replaced by the command, and the measured
numbers replace the 2026-10-05 ones) **and, assigned by reconciliation, `:151-175` and the stale
scope lines at `:12,:15,:44,:51`** (see `## Decisions`, row C7ii);
`docs/plans/2026-10-05-fundamental-panel-coverage.md` §4 (the `~14%` / `~30%` estimates replaced
by measurements, the rest untouched);
`engine/src/seer_engine/lab/methods/m0005_fundamental_factors.py`'s "READ THIS BEFORE RUNNING"
preamble (it points at the gate instead of a `python -c` one-liner, and says M0005 is spent);
`engine/package_readme.md`; and pushing the refreshed store with `/sync-research-store push`.

**Does not touch:** any `engine/src` file outside the one method docstring, `ticker_cik.csv`,
the database, and any other `docs/plans/*.md`. **It does not run `lab run`, does not mint a
variation method, and does not touch the test window.**

**The verification of R5:** `2dad9ff` already made `load_market_window` pass `fundamentals=` and
added **three** tests, at `engine/tests/test_paper_store.py:554`, `:573` and `:585`:

- `test_market_window_carries_the_fundamental_panel_not_an_empty_one`
- `test_market_window_panel_equals_the_full_loads_panel`
- `test_market_window_panel_is_empty_when_no_facts_are_stored`

This phase confirms all three exist and pass with `PG_TEST_URL` set, together with the fact that
`engine/src` has exactly three `Market(` construction sites and all three pass `fundamentals=`,
and records that §6.1 is closed. It writes no new code for it.

The draft of this section named a fourth, non-existent test,
`test_market_window_panel_is_empty_when_the_facts_tables_are_absent` — taken from an uncommitted
draft, and corrected here, in the analysis document and in phase 5's plan. See `## Decisions`,
row C4c.

**The honesty clause, which is the deliverable:** §5 says 30% coverage will not produce a method
that passes this lab's gates, and §8.3 says the plan must say so. Whatever the measured number
is, the runbook and §4 must state it, state that the dev window still opens 13 years before any
XBRL exists, and state that the test-window decision remains unmade and out of scope. If the
number lands near 30%, the docs say *"this does not make a fundamentals method testable on the
dev window"* in those terms. No phase may write a sentence implying otherwise.

**Exit criteria:** `python -m seer_engine research_store --coverage --store "$SEER_STORE"`
output is pasted into the runbook with its date and the store's new fingerprint, and **described
as an upper bound wherever the number is quoted** (`## Decisions`, row C8); §4's table has
measured values in the `+ Fix A` and `+ Fix B` rows, or the explicit words "not separately
measured" and why; the runbook's two copy-paste Python blocks are gone and commands stand in
their place; the runbook's duplicated re-vendoring recipe is a pointer to `SOURCES.md` and no
longer claims "98 of 133"; `grep '2015-01-02' docs/runbooks/data-pipeline.md` returns only lines
whose subject is **bars**; `grep -c '<<'` over the four edited documents returns 0; the store is
pushed with `--keep 0`, `e597367b…` is still listed remotely, and the push's content hash is
recorded; `git status` shows no stray file; suite green at **+0** with and without
`PG_TEST_URL`.

## Reconciliation Log

Fifteen conflicts found across the five plans, fifteen resolved. "Resolution" means the losing
side was **edited out of the plan file**, not outranked in a note: a phase session that meets a
fork at 3am is a phase session that stops.

| # | Class | Where | What was wrong | Resolution |
|---|---|---|---|---|
| C1 | File collision | `commands/research_store.py`, phases 1 & 4 | Both rewrote `run()` and extended `add_arguments()`, in the same wave, so neither could quote the other's output. Phase 4 also asserted a branch order phase 1's code block contradicts. | **DAG edge added: 4 depends on 1.** Phase 1 lands first and its `run()` is final for it; phase 4's Step 3 now quotes *that* body verbatim and inserts three statements into it. Order settled as guards → `--coverage` → `--verify` → `--refresh-fundamentals` → build. Phase 4's "Shared-file sequencing" section rewritten; phase 1's handoff updated. |
| C2 | Unmet assumption | set-wide | The worktree has no venv; main's is an editable install of `main`; pytest has no `pythonpath`. Phase 2 answered with a worktree venv, phase 3 with `PYTHONPATH`, phases 1/4/5 not at all. Phase 2 could have shipped a 913-symbol CSV and passed tests against main's 795-symbol one. | **One mechanism: `PYTHONPATH` over main's venv.** A set-wide **Runtime preamble** added to the index and to all five plans; every command in all five, pytest included, rewritten to use it. Phase 2's and phase 5's venv-building steps deleted. |
| C3 | Unmet assumption | phases 3, 4, 5 and the index | `SEER_ENV_FILE=.env.local-train` is relative, the file is gitignored and absent from the worktree, so `DATABASE_URL_UNPOOLED` falls through to the ambient environment — **Neon**, which invariant 8 forbids writing. | Absolute `SEER_ENV_FILE=/home/miftah/seer/.env.local-train` everywhere, plus a DSN guard asserting `localhost:55432` before any write, propagated to phases 3, 4 and 5 and into invariant 11. The runbook prose phase 5 writes keeps the relative form (correct for a main-checkout reader) with the cwd caveat spelled out. |
| C4a | Index wrong | phase-1 exit criterion | "a fraction near `0.025`" was a **semiannual** sample; phase 1 standardised on monthly/top=20/400-day and measured **0.0378** on the same store. Three definitions were circulating (doc §4's 4% span estimate, 2.5% semiannual, 0.0378 monthly). | Index corrected to **0.0378** and the sampling definition named. Phase 1 and phase 5 now state the definition and retire the other two by name wherever the number appears. |
| C4b | Index wrong | Rollback | "the Blob push adds an object and deletes nothing" — `sync_store.py` has `KEEP_VERSIONS = 3` and `cmd_push` calls `_prune(tok, keep=args.keep)` at `:294`, so a fourth push deletes the oldest, possibly `e597367b…`. | Rollback section rewritten: what makes it safe is `push --keep 0` **plus** the local backup outside the repo that phase 5 takes in its Step 1, **plus** confirming `e597367b…` is still listed after the push. |
| C4c | Index wrong | phase-5 `Owns`, analysis `Reference List` | Both named `test_market_window_panel_is_empty_when_the_facts_tables_are_absent`, which exists nowhere. `2dad9ff` added **three** tests at `:554/:573/:585`. | All three real names and line numbers written into the index, the **analysis file** and phase 5. Phase 5's own correction note kept and re-pointed at the corrected source. |
| C5 | Scope addition | phase 2 | The `EARLY` screen + `EARLY_EXEMPT` were not named in the index. | **Accepted**, after verifying it is free of network cost (same disk-cached `submissions-<cik>.json`) and does not weaken `SCREEN_EXEMPT`'s 11 entries. Added to the index's phase table, phase 2's `Owns` and its exit criteria. See `## Decisions`, row C5. |
| C6 | Contract drift vs. the source doc | phase 3 | The decision doc §3's `--retry-failed` **narrows** `done` to `{ok}` and skips all 773 `ok` filers; phase 3 answered with back-up-and-`TRUNCATE fundamentals_log`. | **`--symbols` taken instead** — `plan_jobs` sets `logged = {}` when it is given, producing the same job list without deleting a row. Phase 3's blocker section, steps 6b/6c/8/9, verification and rollback rewritten; its module-docstring and `--retry-failed` help-string copy fixed to match. The doc's §3 quote stays as written; the index records that it is insufficient and names the replacement. |
| C7i | Out of scope | phase 2 handoff | `TMUS`/`DXC`/`LDOS` membership hulls open before the ticker existed — a `membership_overrides.csv` defect. | Recorded in `## Decisions` as a follow-up; **no phase assigned, no card id invented.** Phase 2's handoff reworded to say so. |
| C7ii | Gap | `docs/runbooks/data-pipeline.md:151-175` + `:12,:15,:44,:51` | The re-vendoring recipe ("98 of 133") and the "ever-members since 2015-01-02" scope lines go stale when phase 2 lands. Phase 2 disclaimed them; phase 5 edited only `:188-256`. Nobody owned them. | **Assigned to phase 5** (rule 5: the phase that owns the file). New **Step 8b** replaces the stale counts with a pointer to `SOURCES.md`, which phase 2 keeps current, so phase 5 states no figure it did not run. Lines 12 and 44 are flagged as **bars** scope and must not move. |
| C8 | Honesty | phase 5 | Phase 1 states its measure is an upper bound (no bars → no membership, `min_price`, `min_dollar_volume`); phase 5's prose quoted the number flat. | "Upper bound" written into phase 5's runbook block, §4 annotation, M0005 docstring and `package_readme.md` text, and into the index's phase-1 and phase-5 exit criteria. |
| C9 | Test-count drift | phases 1–5 | Phase 2 claimed an absolute 2221, phase 4 an absolute 2228, and phase 4's own `+12` was a miscount (10 functions, one parametrized ×4 = **13**). Three absolutes cannot all be measured from one baseline and also be final. | Restated as **per-phase deltas** off the inherited count — P1 +27, P2 +5, P3 +0, P4 +13, P5 +0 — in every plan and in invariant 1. The all-merged figure (2261/332) is given once, as arithmetic, not as a gate. |
| C10 | Contract drift | phase 2 | Its Interface Contract listed **4** new `test_cik.py` tests; step 8b writes **5** and its own verification counts 5. | Contract corrected to five, named. |
| C11 | Contract drift | phase 3 | Its `Creates` named `fundamentals_log_pre_fixb` as a rollback aid while the steps also truncated the live table. | Under C6 the truncate is gone; the contract now describes the table as a **read-only snapshot** and says explicitly that nothing truncates, deletes from, or drops `fundamentals_log`. |
| C12 | Broken step | phase 5, Step 6 | The "Fix A alone" script used `research._read_fundamentals` as if it returned `Fact`s (it returns a `FundamentalPanel`), `research.FundamentalPanel` (does not exist — `research.py:58` imports it as `Panel`), and printed a `Coverage` object. All three verified wrong against the tree. | Script rewritten against the real surface: `pd.read_csv` with `research.py:276-282`'s dtypes → `backtest.io.facts_from_frame` → `fundamentals.FundamentalPanel.from_facts` → `coverage.format_report(coverage.measure(panel))`, plus a one-line import check to run before it. |
| C13 | Index wrong | phase table | Phase 3's `Files` said 3 (its table has 2 — the third artefact is the run); phase 5's said 5 (4 tracked + 2 untracked artefacts). | Corrected to 2 and "4 (+2 untracked)". |

## Decisions

Every behavioural fork settled during reconciliation, with the rung on the ladder that settled
it. Executors read this instead of asking.

| # | The fork | The choice | The rung |
|---|---|---|---|
| C1 | Who owns `research_store.run()` — phase 1's wholesale rewrite or phase 4's append — and whether `--coverage` or `--verify` is tested first | **Phase 1 first; phase 4 depends on it and quotes its body.** Order: guards → `--coverage` → `--verify` → `--refresh-fundamentals` → build | **The plans' code blocks.** Phase 1's step-3d block and its Interface Contract both put `--coverage` first and state it wins when both read-only flags are given; phase 4 asserted the opposite only in prose. A whole-function rewrite must land before an append, or the append is deleted |
| C2 | A venv in the worktree (phases 2, 5) vs. `PYTHONPATH` over main's venv (phase 3) | **`PYTHONPATH`, set-wide. No worktree venv is built.** | **A stated invariant** — invariant 1 pins this set to the `2dad9ff` baseline of 2216 passed / 332 skipped. A second venv is a second dependency resolution, and the baseline stops being comparable. `PYTHONPATH` was measured to win over the editable `.pth`, carries `cik.DATA_DIR` with it, and applies to pytest and `python -m seer_engine` alike |
| C3 | Relative `SEER_ENV_FILE=.env.local-train` (the index, phase 3's first draft, the decision doc §3) vs. an absolute path | **Absolute `/home/miftah/seer/.env.local-train`, plus a DSN guard proving `localhost:55432` before any write** | **A stated invariant** — invariant 8, "no Neon write". `.env*` is gitignored, the worktree has no such file, `config.env_file()` resolves relative against cwd, and the ambient `DATABASE_URL_UNPOOLED` is Neon's |
| C4a | Which number is "the coverage": `4%` (doc §4), `2.5%` (analysis, semiannual), `0.0378` (phase 1, monthly) | **`0.0378`, monthly / `top = 20` / `max_stale_days = 400` / 1996-01-02..2015-10-16, content-checked via `Snapshot.observations`.** The other two are retired by name wherever the number appears | **A phase's exit criteria** — phase 1 defines the measure, owns it, and *ran* it. Invariant 10 ("the plan reports what it measures") then forbids carrying the other two forward as if they were this one |
| C4b | Is the store rollback safe because the push "deletes nothing"? | **No — `push` prunes to `KEEP_VERSIONS = 3`. Safety comes from `push --keep 0`, a local backup outside the repo, and confirming `e597367b…` is still listed afterwards** | **Surrounding code** — `sync_store.py:294`, `cmd_push` → `_prune(tok, keep=args.keep)`. The index's claim was simply false about the tool |
| C5 | Accept phase 2's unplanned `EARLY` screen, or take its stated fallback (keep `periodic_dates`, drop the `EARLY` block) | **Accept.** Verified free of network cost — both screens read the same disk-cached `submissions-<cik>.json` and `_PERIODIC_CACHE` memoises the parse — and verified not to weaken `SCREEN_EXEMPT`: all 11 entries keep their reasons, none is removed, and `EARLY_EXEMPT` is a separate table for a different question | **A stated invariant** — invariant 2 makes the data the whole defence against a recycled ticker, and the existing screen passes all 541 moved starts *by construction*, so without `EARLY` R1's 541 rows are unauditable. Corroborated by the decision doc §2: *"Expect new cases: the further back the intervals reach, the more recycling they cross"* |
| C6 | The decision doc §3's `--retry-failed` command vs. truncating `fundamentals_log` vs. `--symbols` | **`--symbols` with the whole member set.** The doc's command is insufficient and is recorded as such; the truncate is not taken | **A stated invariant** — invariant 8. All three routes fetch the same ~890 CIKs; only `--symbols` cannot delete a row in any database when a guard above it fails. Corroborated by the surrounding convention: `docs/runbooks/data-pipeline.md:174-175` already prescribes `fundamentals --symbols` as the way to re-ingest after a map fix, and `plan_jobs`'s own comment calls it "the tool for re-fetching one filer after a fix" |
| C7i | Fix the `TMUS`/`DXC`/`LDOS` membership hulls here, or not | **Not here. No phase owns it, no card id is invented for it.** It is a `engine/data/membership_overrides.csv` defect in the membership subsystem — the same class as `NDOI` — and the rows are defensible under the hull doctrine, with both screens passing them. Follow-up for whoever owns that file | **The index's Scope section**, which bounds this set to Fix A, Fix B and the coverage gate. Nothing here needs it to be true |
| C7ii | Who owns the runbook's stale re-vendoring recipe and scope lines | **Phase 5** (it owns the file), and it replaces the stale counts with a **pointer to `SOURCES.md`** rather than restating phase 2's numbers | **A stated invariant** — invariant 10 forbids phase 5 stating a figure it did not run. One copy of a recipe, owned by the phase that regenerates the data, is also the only shape that does not drift again |
| C8 | Does phase 5 quote the coverage fraction flat, or as an upper bound | **As an upper bound, every time.** The measure reads no bars, so index membership on the date, `min_price`, twenty sessions of history and `min_dollar_volume` are all unapplied, and each can only remove symbols | **A stated invariant** — invariant 10, plus R4's own wording ("that number is honest"). Below the floor is conclusive; above it is necessary and not sufficient |
| C9 | Three phases each claiming a different absolute final test count | **Per-phase deltas, never absolutes: P1 +27, P2 +5, P3 +0, P4 +13, P5 +0** | **A stated invariant** — invariant 1 is about the *direction* of the count. Three absolutes measured from one baseline cannot all also be final once the phases land concurrently |
| §6.3 | `http.get_json` takes no `headers` argument | **Not folded in.** No phase of this set touches `engine/src/seer_engine/http.py` — the generator uses `urllib.request` through its own `SecFetcher`, and `sec.py` has its own retry loop | **The user's raw input** — decision doc §6.3 scopes it conditionally: *"Fold in only if a phase is already touching `http.py`."* None does. It is recorded here rather than minted as an unowned `R` |
| R5 | Re-implement §6.1 or verify it | **Verify.** `2dad9ff` landed it with three tests and three `Market(` sites all passing `fundamentals=`; phase 5 runs them and records §6.1 closed, writing no code | **The surrounding code** — the fix is already in the tree at the base commit this set branches from |

## Open Questions

**None.**

Every fork in C1–C13 was decidable and was decided, and every requirement id has at least one
phase serving it. Nothing in this set is irreversible: no method id is spent, no trial is
recorded, the post-2015 test window is never touched, `main` is never written to until a human
merges, and the only side effects outside git — the local train database and `engine/.research/`
— both have working undo procedures in `## Rollback`. An item parked here would cost this plan
set its unattended launch, and nothing earned that.

## Rollback

**Per phase.** Every phase is one commit on `feature/fundamental-panel-coverage`; `git revert`
backs it out. The two phases with side effects outside git:

- **Phase 3** writes ~300–500k rows to the local train database. To undo:
  `DELETE FROM fundamental_facts WHERE filed < '2013-01-01'`, and optionally restore
  `fundamentals_log` from the `fundamentals_log_pre_fixb` snapshot the phase takes before the
  run. The log restore is **optional**, because under the reconciled `--symbols` route
  (`## Decisions`, row C6) the phase never deletes a log row — it upserts them, so the ledger
  stays correct about what is stored even if nothing is restored. Neon is untouched throughout,
  so production cannot be affected. `universe refresh` is idempotent and harmless.
- **Phase 5** replaces `engine/.research/` and pushes it to Blob. **Correcting the draft: the
  push does NOT "add an object and delete nothing".** `~/.claude/skills/sync-research-store/sync_store.py`
  sets `KEEP_VERSIONS = 3` and `cmd_push` calls `_prune(tok, keep=args.keep)` at `:294`, so a
  fourth push deletes the oldest remote version — which may be `e597367b…`, the object the whole
  rollback story rests on. Three things make the rollback safe, and all three are in phase 5's
  plan:
  1. **`push --keep 0`**, so the push prunes nothing;
  2. a **local copy outside the repo** taken before the refresh
     (`cp -a "$SEER_STORE" /home/miftah/.seer-store-backup-e597367b`), which restores the
     2026-10-05 store instantly and with no network;
  3. **listing the remote before and after** and confirming
     `e597367bb6806d7edc2f9af4033b26c366aae92517207b4e71daad96346fcca3` is still there.

  With those, `/sync-research-store pull` at the previous fingerprint remains available as the
  third line of defence (the store is gitignored and content-addressed on its manifest
  fingerprint; it was pushed at 41.8 MB compressed).

**As a whole.** `git branch -D feature/fundamental-panel-coverage` and
`git worktree remove /home/miftah/.worktrees/seer/fundamental-panel-coverage`, then
`/sync-research-store pull` for the old store. Nothing in this set is irreversible: no method id
is spent, no trial is recorded, the test window is never touched, and `main` is never written to
until a human merges.

## Next

Execute the phases one at a time, starting at phase 1:

    /implement -f FUNDAMENTAL_PANEL_COVERAGE_PLAN.md --phase 1

Or run the whole set as a swarm — a session per phase, concurrent wherever `Depends on` allows,
resumable on any machine:

    /analyze-orchestrator -f FUNDAMENTAL_PANEL_COVERAGE_PLAN.md

Or put them on the board first (GitHub repos only):

    /create-task --from-plan FUNDAMENTAL_PANEL_COVERAGE_PLAN.md

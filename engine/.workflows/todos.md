# Todos: engine

**Package Path**: `engine`
**Package Code**: ENG
**Last Updated**: 2026-10-03 14:27:00
**Total Active Tasks**: 1

TaskID format: `P{Priority}-{PackageCode}-{4CharID}` (4CharID = 4 random uppercase alphanumerics, unique).

## Quick Stats
- P0 Critical: 0
- P1 High: 1
- P2 Medium: 0
- P3 Low: 0
- P4 Backlog: 0
- Blocked: 0
- Completed: 7

---

## Active Tasks

### [P0] Critical

### [P1] High

- [ ] **P1-ENG-SEZ7** Phase 4: Public API, scenario, determinism, benchmark, docs
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns `engine/src/seer_engine/sim/__init__.py` (add the sizing and split exports), `engine/tests/test_sim_scenario.py` (new), `engine/package_readme.md` (`sim` + `prices` sections, layout, performance, P3/P4 usage loop), `docs/ROADMAP.md` (P2 status line). Exit: a ≥10-session, 4-slot, mixed-outcome scenario with hand-checked final cash, every snapshot's equity, and every closed trade's `pnl_usd` (12 sessions; final cash 985.0996, final equity 1340.5996, Σ pnl 84.6604). Running the scenario twice gives identical outputs. A benchmark of 2,950 sessions × 4 slots finishes under a generous bound, and the measured time is written in the readme. The readme documents the API for P3 and P4. Suite green with 0 skipped.
  - **Status**: open
  - **Plan Set**: `ENGINE_FILL_SIMULATOR_PLAN.md` (phase 4 of 4)
  - **Satisfies**: R4 — Small pure deterministic API for P3/P4, import-purity test, ≥10-session hand-checked scenario, documented in `engine/package_readme.md`
  - **Depends on**: P1-ENG-2PWS, P1-ENG-56QL (both done 2026-10-03)
  - **Plan**: `.workflows/plan/P1-ENG-SEZ7.md`

### [P2] Medium

### [P3] Low

### [P4] Backlog

### 🚫 Blocked

---

## Completed Tasks
- [x] **P1-ENG-2PWS** Phase 2: Whole-share sizing of picks into slots
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns `engine/src/seer_engine/sim/sizing.py` (new), `engine/tests/test_sim_sizing.py` (new). Exit: tests for whole-share sizing, equity ÷ 4 from the last snapshot, the cash cap with earlier placements that night, `lt_one_share`, `held` (no adding, including a symbol already pending and a duplicate pick), `no_slot`, 0 picks, the lowest free slot first in pick order, slot reuse after an exit or expiry on the same session (driven through `step`), and validation errors. Suite green.
  - **Status**: completed
  - **Plan Set**: `ENGINE_FILL_SIMULATOR_PLAN.md` (phase 2 of 4)
  - **Satisfies**: R2 — Whole-share sizing, 4 slots, equity ÷ 4 recomputed daily, cash cap, ineligible < 1 share, no adding, 0 picks valid
  - **Depends on**: P1-ENG-DQFG
  - **Plan**: `.workflows/plan/P1-ENG-2PWS.md`
  - **Completed**: 2026-10-03 14:27
  - **Method**: /do
  - **Files**: engine/src/seer_engine/sim/sizing.py, engine/tests/test_sim_sizing.py

- [x] **P1-ENG-56QL** Phase 3: Split recompute for live orders
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns `engine/src/seer_engine/sim/split_adjust.py` (new), `engine/tests/test_sim_split.py` (new). Exit: tests for a forward split (10:1, 3:2) and a reverse split (1:32, 1:3 with a fractional remainder → cash in lieu) on an open position and on a pending order, a pending order flooring to 0 → `expire` event, an open position flooring to 0 → forced `exit` paid in lieu, prices that 4 dp cannot hold → `ValueError` with the input untouched, symbols not affected, `marks` rescaled, and a split followed by `step` on adjusted bars giving the same economic P/L. Suite green.
  - **Status**: completed
  - **Plan Set**: `ENGINE_FILL_SIMULATOR_PLAN.md` (phase 3 of 4)
  - **Satisfies**: R5 — Pure split-recompute function for live orders (forward and reverse)
  - **Depends on**: P1-ENG-DQFG
  - **Plan**: `.workflows/plan/P1-ENG-56QL.md`
  - **Completed**: 2026-10-03 14:26
  - **Method**: /do
  - **Files**: engine/src/seer_engine/sim/split_adjust.py, engine/tests/test_sim_split.py

- [x] **P1-ENG-DQFG** Phase 1: Pure price types, sim model and session lifecycle
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns `engine/src/seer_engine/prices.py` (new), `engine/src/seer_engine/bars.py` (move `Bar`/`PRICE_QUANTUM`/`to_decimal` out, re-export), `engine/src/seer_engine/sim/__init__.py`, `sim/model.py`, `sim/lifecycle.py`, `engine/tests/simkit.py`, `engine/tests/test_sim_lifecycle.py`, `engine/tests/test_sim_purity.py`. Exit: `step` and `close_unpriced` implement every lifecycle rule and decision. A test exists for each lifecycle edge case in handover §6.1: touch vs penetrate for entry/TP/SL, open < limit, gap SL → `gap`, gap TP → `tp`, same-bar SL first, no check on the fill session, time stop at the day-6 open across a holiday and a half day, expiry, costs and `pnl_usd` to the cent, slot freed after an exit, a missing bar for a held symbol, a missing bar for a pending order, and `close_unpriced`. The purity subprocess test passes. The full suite is green with 0 skipped.
  - **Status**: completed
  - **Plan Set**: `ENGINE_FILL_SIMULATOR_PLAN.md` (phase 1 of 4)
  - **Satisfies**: R1 — Order lifecycle `pending → open → closed` / `pending → expired` exactly as design §5 + handover §3; R3 — Cash/equity per portfolio, 0.1% cost per side, `pnl_usd`, per-session equity snapshot; R4 — Small pure deterministic API for P3/P4, import-purity test, ≥10-session hand-checked scenario, documented in `engine/package_readme.md`
  - **Plan**: `.workflows/plan/P1-ENG-DQFG.md`
  - **Completed**: 2026-10-03 14:23
  - **Method**: /do
  - **Files**: engine/src/seer_engine/prices.py, engine/src/seer_engine/bars.py, engine/src/seer_engine/sim/__init__.py, engine/src/seer_engine/sim/model.py, engine/src/seer_engine/sim/lifecycle.py, engine/tests/simkit.py, engine/tests/test_sim_lifecycle.py, engine/tests/test_sim_purity.py

- [x] **P1-ENG-VP1R** Phase 1: Engine foundation: package, migration 002, dates, DB helpers, demo purge
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns `engine/pyproject.toml` (incl. pytest config), `engine/.gitignore`, `engine/src/seer_engine/{__init__,__main__,cli,config,db,http,dates,demo,universe,bars,fx,runs}.py`, `commands/{__init__,migrate}.py`, `db/migrations/002_engine.sql`, and `engine/tests/{conftest,test_dates,test_cli,test_migrate,test_bars,test_fx,test_runs,test_demo,test_universe_queries,test_http}.py`. Does not touch membership loading, non-Frankfurter sources, `.github/`, `web/`, root `.gitignore`, Neon. Exit: `python -m seer_engine --help` lists `migrate`; `--dry-run migrate` against `PG_TEST_URL` exits 0 and leaves no `schema_migrations`; 101 tests pass against Postgres 16 (container `seer-pg`, port 55432) with 0 skipped, incl. handover §6.4 date cases; a second identical `upsert_bars`/`upsert_fx` returns 0 and leaves `xmin` unchanged.
  - **Status**: done
  - **Plan Set**: `ENGINE_DATA_PIPELINE_PLAN.md` (phase 1 of 5)
  - **Satisfies**: R2 — Point-in-time S&P 500 ∪ Nasdaq-100 membership in a new table (migration 002); R4 — Every step idempotent for the same date; R5 — First real engine write deletes all demo data atomically; R6 — Unit tests (dates, adjustment, idempotent upserts) and a dry-run mode that writes nothing
  - **Depends on**: —
  - **Plan**: `.workflows/plan/P1-ENG-VP1R.md`
  - **Completed**: 2026-10-03 12:51
  - **Method**: /do
  - **Files**: engine/pyproject.toml, engine/.gitignore, db/migrations/002_engine.sql, engine/src/seer_engine/{__init__,__main__,cli,config,db,http,dates,demo,universe,bars,fx,runs}.py, engine/src/seer_engine/commands/{__init__,migrate}.py, engine/tests/{conftest,test_dates,test_cli,test_migrate,test_bars,test_fx,test_runs,test_demo,test_universe_queries,test_http}.py

- [x] **P1-ENG-GF8Y** Phase 4: Nightly command: Massive bars, splits, FX, runs
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns `engine/src/seer_engine/massive.py`, `splits.py`, `commands/nightly.py`, `engine/tests/{test_massive,test_splits,test_nightly}.py`. Does not touch backfill, membership, `.github/`, Neon. Exit: `nightly` computes `RunDates`, no-ops when that session already succeeded, else fetches every missing session up to `data_date` via grouped daily (≤ 30, calls ≥ 12.5 s apart), applies every split in the gap once (`split_adjustments`; guard "stored bar on/after execution date → already adjusted", then ratio heuristic for `|ln f| ≥ ln 1.25`) before upserting fetched bars, upserts FX, finishes the run — all bars/splits/FX/run-success in one transaction; failures mark the run failed (exit 1) with no bars written; missing key exits 2; dry-run writes nothing; checksum test proves a same-`now` re-run leaves `bars`, `fx_rates`, `runs`, `split_adjustments` identical.
  - **Status**: done
  - **Plan Set**: `ENGINE_DATA_PIPELINE_PLAN.md` (phase 4 of 5)
  - **Satisfies**: R3 — Nightly Actions job: Massive bars + Frankfurter FX + `runs` row with correct dates; failed fetch → `failed` run, no partial bars; R4 — Every step idempotent for the same date; R6 — Unit tests (dates, adjustment, idempotent upserts) and a dry-run mode that writes nothing
  - **Depends on**: P1-ENG-VP1R
  - **Plan**: `.workflows/plan/P1-ENG-GF8Y.md`
  - **Completed**: 2026-10-03 12:56
  - **Method**: /do
  - **Files**: engine/src/seer_engine/splits.py, engine/src/seer_engine/massive.py, engine/src/seer_engine/commands/nightly.py, engine/tests/test_massive.py, engine/tests/test_splits.py, engine/tests/test_nightly.py
  - **Decided**: readme-updater/pusher chain vs coordinator 'do not push' → commit locally only, skip readme-updater and push (rung 5: coordinator -note; plan scope already excludes git push)

- [x] **P1-ENG-L73U** Phase 3: yfinance + FX history backfill
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns `engine/src/seer_engine/yahoo.py`, `commands/backfill.py`, `engine/tests/test_backfill.py`. Does not touch Massive, `runs`, `split_adjustments`, `universe` contents, membership loading. Exit: `backfill` (default start 2015-01-02, end = `last_completed_session(now)`, overridable with `--end`) loads `all_symbols(since=start)` in throttled batches of 40, records every symbol in `backfill_log` (`ok` / `empty` = no Yahoo data / `failed` = rate limit or error), skips every already-logged symbol by default (`--retry-failed` re-attempts `failed`+`empty`, `--symbols` ignores the log), loads Frankfurter history into `fx_rates`; exit 0 unless a symbol is `failed` or FX failed (1) or the universe is empty (2); re-run changes nothing; 32 tests with an injected fake downloader pass against `PG_TEST_URL`.
  - **Status**: done
  - **Plan Set**: `ENGINE_DATA_PIPELINE_PLAN.md` (phase 3 of 5)
  - **Satisfies**: R1 — Backfill 10+ years of split-adjusted daily bars for every ever-member (yfinance), logging unfetchable symbols; R4 — Every step idempotent for the same date; R6 — Unit tests (dates, adjustment, idempotent upserts) and a dry-run mode that writes nothing
  - **Depends on**: P1-ENG-VP1R
  - **Plan**: `.workflows/plan/P1-ENG-L73U.md`
  - **Completed**: 2026-10-03 13:05
  - **Method**: /do
  - **Files**: engine/src/seer_engine/yahoo.py, engine/src/seer_engine/commands/backfill.py, engine/tests/test_backfill.py

- [x] **P1-ENG-853Z** Phase 2: Point-in-time universe membership
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns `engine/data/{sp500_history.csv, ndx_history.csv, ticker_aliases.csv, membership_overrides.csv, SOURCES.md}`, `engine/src/seer_engine/membership.py`, `commands/universe.py` (`universe refresh`, `universe check`), `engine/tests/test_membership.py`. Does not touch `universe.py` queries or other phase-1 files, `bars`, `.vercelignore`. Exit: `universe refresh` replaces the `universe` table in one transaction and prints `unchanged, nothing written` on re-run; `--dry-run universe refresh` leaves the table untouched; `universe check` exits 0 on live Wikipedia pages and 1 on any diff (tested); 29 tests in `test_membership.py` cover interval building, overrides and aliases; full suite green.
  - **Status**: done
  - **Plan Set**: `ENGINE_DATA_PIPELINE_PLAN.md` (phase 2 of 5)
  - **Satisfies**: R2 — Point-in-time S&P 500 ∪ Nasdaq-100 membership in a new table (migration 002); R4 — Every step idempotent for the same date; R6 — Unit tests (dates, adjustment, idempotent upserts) and a dry-run mode that writes nothing
  - **Depends on**: P1-ENG-VP1R
  - **Plan**: `.workflows/plan/P1-ENG-853Z.md`
  - **Completed**: 2026-10-03 13:10
  - **Method**: /implement
  - **Commit**: 4ea9360
  - **Files**: engine/data/{sp500_history.csv, ndx_history.csv, ticker_aliases.csv, membership_overrides.csv, SOURCES.md}, engine/src/seer_engine/membership.py, engine/src/seer_engine/commands/universe.py, engine/tests/test_membership.py
  - **Verified**: test_membership 29/29, suite 216 passed (seer-pg); local refresh 1544 rows then "unchanged, nothing written"; universe check identical SP500 503 / NDX 101

---

## Archive

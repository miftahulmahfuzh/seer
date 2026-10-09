# Plan: Seer data pipeline (P1) — engine/ + GitHub Actions

**Slug:** engine-data-pipeline
**Date:** 2026-10-03 12:19 WIB
**Analysis:** `20261003-121931-K7P2_code_analyzer.md`
**Worktree:** `/home/miftah/.worktrees/seer/engine-data-pipeline`
**Branch:** `feature/engine-data-pipeline` (base: `origin/main` @ `c059f59`)
**Phases:** 5
**Status:** phases 1–5 of 5 complete
**Coordinator:** —

---

## Why

The specification is `docs/handover/2026-10-03-data-pipeline.md` (committed at `c059f59`).
Its §2 goal, verbatim:

> Build `engine/` (Python) and a GitHub Actions workflow that:
> 1. **Backfills** 10+ years of split-adjusted daily bars for the universe into Neon `bars`.
> 2. **Maintains point-in-time universe membership** (S&P 500 ∪ Nasdaq-100) in a new table.
> 3. **Runs nightly** (~06:00 WIB = 23:00 UTC, Mon–Fri): fetches the latest session's bars and
>    the USD/IDR rate, and writes a `runs` row with correct `data_date` and `session_date`.
> 4. Is **idempotent**: re-running any step for the same date changes nothing.
>
> **Out of scope for P1** (later phases, don't build): fill simulator (P2), strategies and
> backtest (P3), placing picks/orders, LLM explanations (P4), any web UI change.

§3 decisions are law ("do not reopen"); §6 is the acceptance list; §7's open questions are
settled in the analysis document ("Settled open questions").

## Requirements

| ID | What the user asked for | Phases |
|---|---|---|
| R1 | Backfill 10+ years of split-adjusted daily bars for every ever-member (yfinance), logging unfetchable symbols | 3, 5 |
| R2 | Point-in-time S&P 500 ∪ Nasdaq-100 membership in a new table (migration 002) | 1, 2 |
| R3 | Nightly Actions job: Massive bars + Frankfurter FX + `runs` row with correct dates; failed fetch → `failed` run, no partial bars | 4, 5 |
| R4 | Every step idempotent for the same date | 1, 2, 3, 4 |
| R5 | First real engine write deletes all demo data atomically | 1, 5 |
| R6 | Unit tests (dates, adjustment, idempotent upserts) and a dry-run mode that writes nothing | 1, 2, 3, 4 |

Coupling, stated rather than hidden: R4 and R6 are properties of every writer, so they are served
by each phase that writes (1–4); phase 1 owns the shared write helpers so the property is
implemented once. R5's purge is implemented once in phase 1 (`demo.purge_demo_if_needed`); phases
2–4 only call it (invariant 6), and phase 5 performs it on Neon.

## Scope

**In scope:** `engine/` Python package (`seer_engine`), migration `002_engine.sql`, vendored
membership data, backfill + nightly + universe commands, GitHub Actions workflows (CI, nightly,
weekly universe check, manual backfill), a seed-script guard, a runbook, and executing the
pipeline once against Neon from the local machine.

**Out of scope:** P2–P6 (simulator, strategies, orders, LLM, Finnhub), any `web/app` or
`web/components` change, `git push`, `gh secret set` (handover §5: owner approves those), a
README (owner rule: README is written at release time only).

## Invariants

1. Every phase ends with `engine/.venv/bin/pytest engine/tests` green (DB tests run against
   `PG_TEST_URL`; see phase 1) and nothing else in the repo broken (`cd web && npx vitest run`
   still green where touched).
2. Dates are `datetime.date` / `YYYY-MM-DD` strings end to end. Never construct a local-midnight
   datetime from a date; the only timezone-aware datetimes are UTC "now" and calendar closes.
3. Canonical symbol form is the dot form (`BRK.B`) in every table. Conversion to Yahoo's dash
   form happens only inside `yahoo.py`.
4. Bars are **split-adjusted only** (no dividend adjustment), rounded to 4 decimals; volume is
   an `int`.
5. Every DB write goes through `db.transaction(conn, dry_run)`; `--dry-run` rolls back every
   transaction and therefore writes nothing.
6. Every write command calls `demo.purge_demo_if_needed(conn, args.dry_run)` in its own
   transaction **before** any other write. Under `--dry-run` that transaction runs and is rolled
   back like every other (invariant 5), and "would purge" is logged; nothing persists.
7. Commands are discovered from `seer_engine/commands/*.py`; adding a command never edits
   `cli.py`. Global flags work on either side of the command; every documented command places
   them before it: `python -m seer_engine --dry-run -v <command> ...`.
8. No secrets in code or logs (the Massive key is redacted from any logged URL).
9. Exit codes: 0 success or no-op; 1 a failed run / failed symbols / uncaught error; 2 a missing
   setting (`ConfigError`) or an unmet precondition (empty universe, bad arguments).

## Shared interface contract (phase 1 creates; phases 2–4 consume as written)

```
engine/pyproject.toml                    package seer_engine, src layout, python >=3.11
  deps: psycopg[binary]>=3.2, pandas>=2.2, pandas_market_calendars>=5.0, yfinance>=1.0,
        requests>=2.32, python-dotenv>=1.0 ; extra [dev]: pytest>=8
engine/src/seer_engine/cli.py            python -m seer_engine [--dry-run] [-v] <command> ...
  each commands/<name>.py exposes: HELP: str ; add_arguments(p: argparse.ArgumentParser) -> None
                                    run(args: argparse.Namespace) -> int   (args.dry_run present)
config.py   load_env() ; get(name) -> str|None ; require(name) -> str (raises ConfigError)
db.py       connect() -> psycopg.Connection   (DATABASE_URL_UNPOOLED, autocommit=False)
            transaction(conn, dry_run: bool) -> contextmanager  (commit | rollback)
http.py     get_json(url, params=None, *, retries=3, backoff=5.0, timeout=30) -> dict
            redact(url) -> str ; HttpError(.status) ; USER_AGENT = "seer-engine/0.1.0"
            (sent on every request; Wikipedia 403s the default python-requests agent)
dates.py    sessions(start, end) -> list[date]        inclusive, NYSE
            is_session(d) -> bool ; next_session(d) -> date ; prev_session(d) -> date
            session_close_utc(d) -> datetime (UTC)
            last_completed_session(now_utc, settle=timedelta(hours=1)) -> date
            RunDates(data_date: date, session_date: date) ; run_dates(now_utc) -> RunDates
demo.py     purge_demo(conn) -> bool        (TRUNCATE action_dismissals, orders,
                                             equity_snapshots, bars, fx_rates, runs
                                             RESTART IDENTITY; only if a demo run exists)
            purge_demo_if_needed(conn, dry_run) -> bool   (own transaction; rolled back
                                                           under dry_run)
universe.py BENCHMARK = "SPY"
            members_on(conn, d) -> set[str]
            symbols_for_bars(conn, d, grace_days=30) -> set[str]   (∪ BENCHMARK)
            all_symbols(conn, since: date) -> list[str]            (∪ BENCHMARK, sorted)
bars.py     Bar(symbol, date, open, high, low, close, volume)  frozen dataclass, Decimal prices
            make_bar(symbol, d, o, h, l, c, v) -> Bar   (rounds to 4 dp, int volume)
            upsert_bars(conn, bars: Iterable[Bar]) -> int   (rows inserted or changed)
            latest_bar_date(conn, symbol) -> date|None
            delete_bars_on(conn, d) -> int
fx.py       fetch_latest() -> tuple[date, Decimal] ; fetch_range(start, end) -> list[tuple[date, Decimal]]
            upsert_fx(conn, rows) -> int
runs.py     start_run(conn, rd: RunDates) -> int|None   (None = already succeeded → no-op;
                                                     reuses a failed OR stale running row, same id)
            finish_run(conn, run_id) ; fail_run(conn, run_id, error: str)
            (none of bars/fx/runs/universe/purge_demo commit; db.transaction does, and re-raises
             after rolling back. Hold connections with closing()/try-finally, not `with connect()`)
db/migrations/002_engine.sql   universe, split_adjustments, backfill_log, runs_real_session_uidx
engine/tests/conftest.py   fixtures: pg (migrated throwaway schema, committed/idle), pg_empty,
                           pg_schema, pg_url (skip with the docker command if PG_TEST_URL unset),
                           utc(y, m, d, h=0, mi=0) clock factory; autouse _isolated_env points
                           SEER_ENV_FILE at a missing file and DATABASE_URL_UNPOOLED at a .invalid
                           host, so tests set any key (e.g. MASSIVE_API_KEY) via monkeypatch.
                           Local test DB: container seer-pg,
                           PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres
```

## Phases

| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID | Card |
|---|-------|-----------|---------|-------|-----------|------------|------|--------|------|
| 1 (done) | Engine foundation: package, migration 002, dates, DB helpers, demo purge | R2, R4, R5, R6 | `engine/`, `db/` | 27 | — | HARD | `.workflows/plan/engine-data-pipeline/phase-1.md` | P1-ENG-VP1R | — |
| 2 (done) | Point-in-time universe membership | R2, R4, R6 | `engine/` | 8 | 1 | NORMAL | `.workflows/plan/engine-data-pipeline/phase-2.md` | P1-ENG-853Z | — |
| 3 (done) | yfinance + FX history backfill | R1, R4, R6 | `engine/` | 3 | 1 | NORMAL | `.workflows/plan/engine-data-pipeline/phase-3.md` | P1-ENG-L73U | — |
| 4 (done) | Nightly command: Massive bars, splits, FX, runs | R3, R4, R6 | `engine/` | 6 | 1 | HARD | `.workflows/plan/engine-data-pipeline/phase-4.md` | P1-ENG-GF8Y | — |
| 5 (done) | Workflows, seed guard, runbook, live run on Neon | R1, R3, R5 | `.github/`, `web/scripts`, `docs/` | 7 (+1 data append only on drift) | 2, 3, 4 | NORMAL | `.workflows/plan/engine-data-pipeline/phase-5.md` | P1-ROOT-2QEA | — |

Phases 2, 3 and 4 depend only on phase 1 and touch disjoint files, so they can run concurrently.
Phase 2 is a **run-time** prerequisite of 3 and 4 (a populated `universe`), not a build or test
one: their tests monkeypatch `universe.all_symbols` / `universe.symbols_for_bars`.

### Phase 1 — Engine foundation
**Satisfies:** R2 (the table), R4 (idempotent helpers), R5 (purge), R6 (test infra, date tests, dry-run plumbing)
**Owns:** `engine/pyproject.toml` (incl. `[tool.pytest.ini_options]`); `engine/.gitignore`; `engine/src/seer_engine/{__init__,__main__,cli,config,db,http,dates,demo,universe,bars,fx,runs}.py`; `engine/src/seer_engine/commands/{__init__,migrate}.py`; `db/migrations/002_engine.sql`; `engine/tests/{conftest,test_dates,test_cli,test_migrate,test_bars,test_fx,test_runs,test_demo,test_universe_queries,test_http}.py`.
**Does not touch:** membership loading (phase 2), any network source other than Frankfurter, `.github/`, `web/`, root `.gitignore`, Neon.
**Exit criteria:** `python -m seer_engine --help` lists `migrate`; `python -m seer_engine --dry-run migrate` against `PG_TEST_URL` exits 0 and leaves no `schema_migrations`; 101 tests pass against Postgres 16 (container `seer-pg`, port 55432) with 0 skipped, including handover §6.4 date cases; a second identical `upsert_bars`/`upsert_fx` returns 0 and leaves `xmin` unchanged.

### Phase 2 — Point-in-time universe membership
**Satisfies:** R2, R4 (refresh re-run writes nothing), R6
**Owns:** `engine/data/{sp500_history.csv, ndx_history.csv, ticker_aliases.csv, membership_overrides.csv, SOURCES.md}`; `engine/src/seer_engine/membership.py`; `engine/src/seer_engine/commands/universe.py` (`universe refresh`, `universe check`); `engine/tests/test_membership.py`.
**Does not touch:** `universe.py` query functions and every other phase-1 file, `bars`, `.vercelignore` (Vercel root dir is `web/`).
**Exit criteria:** `universe refresh` replaces the `universe` table in one transaction and prints `unchanged, nothing written` on re-run; `--dry-run universe refresh` leaves the table untouched; `universe check` exits 0 on the live Wikipedia pages and 1 on any diff (tested); 29 tests in `test_membership.py` cover interval building, overrides and aliases, and the full suite stays green.

### Phase 3 — yfinance + FX history backfill
**Satisfies:** R1, R4, R6
**Owns:** `engine/src/seer_engine/yahoo.py`; `engine/src/seer_engine/commands/backfill.py`; `engine/tests/test_backfill.py`.
**Does not touch:** Massive, `runs`, `split_adjustments`, `universe` contents, membership loading.
**Exit criteria:** `backfill` (default start 2015-01-02, end = `last_completed_session(now)`, overridable with `--end`) loads `all_symbols(since=start)` in throttled batches of 40, records every symbol in `backfill_log` (`ok` / `empty` = no Yahoo data, e.g. delisted / `failed` = rate limit or error), by default skips every already-logged symbol (`--retry-failed` re-attempts `failed`+`empty`, `--symbols` ignores the log), loads Frankfurter history into `fx_rates`; exit 0 unless a symbol is `failed` or FX failed (1) or the universe is empty (2); re-run changes nothing; 32 tests with an injected fake downloader pass against `PG_TEST_URL`.

### Phase 4 — Nightly command
**Satisfies:** R3, R4, R6
**Owns:** `engine/src/seer_engine/massive.py`; `engine/src/seer_engine/splits.py`; `engine/src/seer_engine/commands/nightly.py`; `engine/tests/{test_massive,test_splits,test_nightly}.py`.
**Does not touch:** backfill, membership, `.github/`, Neon (its live dry run is phase 5 Step 13).
**Exit criteria:** `nightly` computes `RunDates`, no-ops when that session already succeeded, otherwise fetches every missing session up to `data_date` via grouped daily (≤ 30, calls ≥ 12.5 s apart), applies every split in the gap once (`split_adjustments`; guard "stored bar on/after execution date → already adjusted", then the ratio heuristic for `|ln f| ≥ ln 1.25`) before upserting fetched bars, upserts FX, and finishes the run — all bars/splits/FX/run-success in one transaction; failures mark the run failed (exit 1) with no bars written; missing key exits 2; dry-run writes nothing; the checksum test proves a same-`now` re-run leaves `bars`, `fx_rates`, `runs`, `split_adjustments` identical.

### Phase 5 — Workflows, seed guard, runbook, live run
**Satisfies:** R1, R3, R5 (operationally)
**Owns:** `.github/workflows/{engine-ci,nightly,universe,backfill}.yml`; `web/scripts/seed-demo.mjs` (refuse when > 100 real bars exist); `docs/runbooks/data-pipeline.md` (incl. exit codes and split handling); `docs/ROADMAP.md` P1 line; data-only appends to `engine/data/membership_overrides.csv` if `universe check` drifts; live execution on Neon (migrate → universe refresh (first write, purges demo) → universe check → backfill with pinned `--end` → `--retry-failed` → nightly ×2 + dry run with checksums → web read path → storage size), results recorded in the runbook.
**Does not touch:** `engine/**` code, `git push`, `gh secret set`, `web/app`, `web/components`, `web/lib`.
**Exit criteria:** workflows pass `actionlint` (or a YAML parse if actionlint is unavailable); CI fails if any engine test is skipped; seed refuses on Neon after the backfill; Neon has migration 002 and no demo rows; `bars` covers every fetchable ever-member since 2015-01-02 with unfetchable ones in `backfill_log` and the runbook, under 400 MB; two nightly runs and one dry run leave identical fingerprints and the single real `runs` row equals `dates.run_dates(now)`; runbook acceptance checklist ticked with evidence; nothing pushed, no secret set.

## Reconciliation Log

| # | Conflict | Class | Phases | Resolution |
|---|---|---|---|---|
| 1 | Phase 2 needs a non-default User-Agent for Wikipedia | Unmet assumption (check) | 1, 2 | Verified: phase 1 `http.py` sets `USER_AGENT = "seer-engine/0.1.0"` on the shared session. Added to the index contract; phase 2 handoff marked resolved. |
| 2 | Phases 2–4 tests vs phase 1 conftest (fixture names, env isolation) | Unmet assumption (check) | 1, 2, 3, 4 | Verified: all use `pg`; phase 4 monkeypatches `config.require`; no test reads `.env.local`. Index contract now lists the real fixtures (`pg`, `pg_empty`, `pg_schema`, `pg_url`, `utc`, autouse `_isolated_env`). No code change. |
| 3 | Phase 4 assumptions on `runs` (no commit, reuse failed + stale running), `db.transaction` re-raise, `apiKey` redaction | Unmet assumption (check) | 1, 4 | Verified against phase 1 code: all hold (`start_run` `DO UPDATE … WHERE status <> 'success'`). Phase 4 Assumptions/Handoffs edited to say so. |
| 4 | Phase 3 A6/A9 misdescribe phase 1 (purge "no-op" under dry-run; `rows NOT NULL`) | Contract drift | 1, 3 | Phase 3 assumption text corrected (purge runs then rolls back; `rows` nullable, always written). `upsert_bars` duplicate-raise, `make_bar(Decimal)` and `"rows"` naming verified; no code change. |
| 5 | Phase 2 handoff said delisted symbols are logged `failed`; phase 3 code logs no-data as `empty` and exits 0 | Contract drift | 2, 3, 5 | Phase 2 handoff corrected to `empty`; phase 5 Requires, runbook exit-code table and `backfill.yml` comments state 0/1/2 semantics. See Decisions. |
| 6 | Resume semantics: index draft and phase 5 runbook said "skips `ok` symbols"; phase 3 skips every logged symbol | Contract drift | 3, 5, index | Phase 5 Requires/runbook/Step 12 and the index phase 3 exit criteria now match phase 3. See Decisions. |
| 7 | `backfill.yml` lacked `batch_size` and `dry_run` inputs that phase 3 asked for | Gap | 3, 5 | Added both inputs to phase 5 Step 4, with flags placed before the command and `--dry-run` threaded through migrate and refresh too. |
| 8 | Backfill resume passes on different days end on different sessions; if SPY lands in a later pass, nightly's SPY-based gap check leaves holes for earlier symbols | Gap | 3, 4, 5 | Phase 5 Step 12 computes `--end` once (`.workflows/live/backfill-end.txt`) and passes it to every pass and to `--retry-failed`; runbook documents `--end`. |
| 9 | Split handling (backfill none; nightly applies gap splits first; guard + heuristic) not in the runbook | Gap | 3, 4, 5 | Added a "Splits" section to the phase 5 runbook; phase 3's phase-4 handoff marked consistent (nightly only fetches splits after SPY's last stored bar). |
| 10 | Flag placement inconsistent (`migrate --dry-run` in phase 1/index, `universe refresh --dry-run` in phase 2 manual check) | Contract drift (docs) | 1, 2, index | Normalised every documented command to flags-before-command; phase 2's code and test still accept both positions. Invariant 7 states the style. |
| 11 | `nightly` returned 1 for a missing `MASSIVE_API_KEY`; phase 1's CLI maps `ConfigError` to 2 | Contract drift | 1, 4 | Phase 4 `run()` returns 2 and its test is `test_run_without_key_exits_2`. See Decisions. |
| 12 | Test DB collision: phase 5 started `seer-pg-test` on port 55432 (busy with phase 1's `seer-pg`); phase 3 cited `127.0.0.1:5432/seer_test` | File/resource collision | 1, 3, 4, 5 | Every local command uses phase 1's container and `postgresql://postgres:pg@localhost:55432/postgres`; CI keeps its own `postgres:16` service on 5432. |
| 13 | Migration 002 `universe.source_symbol` comment did not describe phase 2's `/`-joined form | Contract drift | 1, 2 | Phase 1 Step 2 SQL comment rewritten. |
| 14 | Phase 4 manual check ran a Neon dry run before migration 002 exists on Neon | Ordering violation | 4, 5 | Removed from phase 4; phase 5 Step 13 already runs that dry run after the backfill. |
| 15 | CI could silently skip the 35+ DB tests if `PG_TEST_URL` did not reach pytest (phase 1 handoff) | Gap | 1, 5 | `engine-ci.yml` fails when pytest `-rs` output contains `SKIPPED`. |
| 16 | Root `.gitignore` lacks `*.egg-info/` (phase 1 "unowned") | Gap | 1, 5 | Already covered by phase 1's `engine/.gitignore`; root `*.log` covers `.workflows/live/*.log`. No edit to the root file. |
| 17 | Phase 2 vendors ~5.6 MB of CSVs vs `.vercelignore` | Possible collision | 2 | None: Vercel's root directory is `web/`, so `engine/` is never deployed; `.vercelignore` unchanged. Noted in phase 2 Step 1. |
| 18 | Phase 2's refresh is idempotent (R4) but its Satisfies line omitted R4, while the index says every writer serves R4 | Requirement creep / index inconsistency | 2, index | Phase 2 Satisfies and the Requirements table now include R4 for phase 2 (the step cannot move; it is the refresh itself). See Decisions. |
| 19 | Invariant 6 said the purge is "skipped under `--dry-run`"; phase 1 runs it and rolls back | Contract drift | 1, 4, index | Invariant 6 reworded; phase 4 docstring and phase 5 runbook wording aligned. See Decisions. |
| 20 | Runbook override/alias formats were vague ("effective date, index, add/remove, symbol"; `OLD,NEW`) | Contract drift (docs) | 2, 5 | Runbook now gives `date,index_id,action,ticker,note` and `old,new,effective_date,note`, plus the no-chain rule. |
| 21 | Phase 5 Step 0 created the venv with `python`, phase 1 with `python3.11`; owner steps assumed a venv in the main checkout | Minor drift | 1, 5 | Both use `python3.11`; owner steps create the venv if missing. |
| 22 | Concurrency group `seer-db-writer`, nightly `timeout-minutes: 30`, comma-separated `--symbols`, nightly non-zero on failure | Check | 3, 4, 5 | Verified consistent across plans; no edit. |
| 23 | Live run order (migrate → universe refresh → backfill → retry-failed → nightly ×2) and command names | Check | 2, 3, 4, 5 | Verified against phases 2–4 command names and flags; phase 5 is the only phase that touches Neon. |

## Decisions

| Fork | Chosen | Rung |
|---|---|---|
| Live execution on Neon in an unattended phase vs. owner-only | Execute migrate/backfill/nightly on Neon locally (demo purge is a §3 decision); **do not** push or set secrets | 5: user raw input (handover §3 demo decision, §5 "ask before pushing or setting secrets") |
| `runs` idempotency ("identical contents" on re-run) | One real row per `session_date` (partial unique index); a re-run of an already-successful session writes nothing; a failed one is reused | 4: Why/§6.3 |
| Store full Massive response vs. universe | Universe ∪ SPY (~250 MB est. vs ~400 MB/yr full market) | 5: handover §7 |
| Dividend adjustment | Split-only, both sources | 5: handover §3 "likely answer" |
| Backfill start date | 2015-01-02 (10y backtest from 2016 + ~1y indicator warm-up) | 5: handover §2.1 "10+ years" |
| Delisted / unknown-to-Yahoo symbols: `failed` (phase 2 handoff) vs `empty` (phase 3 code) | `empty`; they do not affect the exit code, so a normal full backfill exits 0; `failed` means rate limit / download error and exits 1 | 3: code blocks (phase 3 `fetch_batch`, `Summary.exit_code`); also matches handover §6.2 "log the ones that can't" |
| Default backfill resume: skip only `ok` (index draft wording) vs skip every logged symbol (phase 3) | Skip every logged symbol; `--retry-failed` re-attempts `failed`+`empty`; `--symbols` ignores the log | 3: code blocks (phase 3 `select_symbols`); the draft exit criterion ("skips `ok`") is satisfied by both, and phase 3's choice is the only one where `--retry-failed` does anything |
| `nightly` exit code for a missing `MASSIVE_API_KEY`: 1 (phase 4) vs 2 (phase 1 CLI `ConfigError`) | 2, everywhere; 1 is reserved for a run marked `failed` | 3: code blocks (phase 1 `cli.main`, authoritative for the shared contract) |
| Demo purge under `--dry-run`: skipped (invariant 6 draft) vs executed and rolled back (phase 1) | Executed and rolled back, logged "would purge" | 1: invariant 5 (every transaction rolls back under `--dry-run`); both satisfy "writes nothing" |
| Local test database: `seer-pg-test` (phase 5) / `:5432/seer_test` (phase 3) vs `seer-pg` (phase 1) | Phase 1's `seer-pg`, `postgresql://postgres:pg@localhost:55432/postgres`; CI keeps its service DB | 3: code blocks (phase 1 conftest docstring and Verification) |
| Phase 2 Satisfies: R2, R6 only vs also R4 | Add R4 (refresh is a writer and is idempotent) | 4: index Why/Requirements coupling note ("R4 and R6 are served by each phase that writes") |
| CI with DB tests silently skipped vs failing | Fail CI when any engine test is skipped | 1: invariant 1 (DB tests run against `PG_TEST_URL`) |
| Backfill end date across resume passes: per-pass default vs pinned | Pin `--end` once for the live backfill and its retries | 4: R1 (every symbol ≥ 10 years, no holes) + phase 4's SPY-based gap detection |

## Open Questions

## Rollback

Per phase: `git revert` the phase commit. Phase 5's live run: `DELETE FROM runs WHERE NOT is_demo;
TRUNCATE bars, fx_rates, universe, split_adjustments, backfill_log;` then `npm run db:seed-demo`
restores the demo state (the seed guard only blocks while real runs or > 100 bars exist). Migration 002 is additive; dropping its
three tables and the index reverses it.

## Next

Execute the phases one at a time, starting at phase 1:

    /implement -f ENGINE_DATA_PIPELINE_PLAN.md --phase 1

Or run the whole set as a swarm — a session per phase, concurrent wherever `Depends on` allows:

    /analyze-orchestrator -f ENGINE_DATA_PIPELINE_PLAN.md

Or put them on the board first:

    /create-task --from-plan ENGINE_DATA_PIPELINE_PLAN.md

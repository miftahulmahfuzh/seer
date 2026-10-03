# Code Analysis: Seer data pipeline (roadmap P1)

**Type:** Feature Implementation
**Date:** 2026-10-03 12:19 WIB
**Session ID:** 20261003-121931-K7P2
**Plan:** `ENGINE_DATA_PIPELINE_PLAN.md` (5 phases)
**Worktree:** `/home/miftah/.worktrees/seer/engine-data-pipeline` on `feature/engine-data-pipeline` (base `origin/main` @ `c059f59`)

---

## User Input

### Original User Request

```
/analyze docs/handover/2026-10-03-data-pipeline.md
```

The argument is the whole specification: `docs/handover/2026-10-03-data-pipeline.md`, committed
at `c059f59` and present unchanged in this worktree. It is not copied here so there is exactly one
copy of it; every phase plan cites it by section (§1–§7). Its §3 "Decisions already made — do not
reopen" and §6 "Acceptance criteria" are binding; §7 lists the open questions this analysis
settles (see "Settled open questions" below).

### User-Provided Context

- Handover §4 verified facts (Massive free tier = ~2 years, 5 calls/min, grouped daily = 12,594
  tickers per call; Frankfurter needs no key; Neon via psycopg + `DATABASE_URL_UNPOOLED`; raw
  `psql` hangs from WSL; keep dates as `YYYY-MM-DD` / `datetime.date`).
- Handover §5: zsh, Python 3.11.0 via pyenv, no `uv`; `.env.local` at repo root holds every key;
  **ask the owner before pushing or setting GitHub secrets.**

### User-Provided Files
- `docs/handover/2026-10-03-data-pipeline.md`
- (cited by it) `docs/plans/2026-10-03-seer-design.md`, `docs/ROADMAP.md`,
  `db/migrations/001_init.sql`, `web/lib/data.ts`

### Requirement IDs

| ID | What the user asked for |
|---|---|
| R1 | Backfill 10+ years of split-adjusted daily bars for every symbol ever in the universe into `bars` (yfinance), logging symbols that can't be fetched (§2.1, §6.2) |
| R2 | Maintain point-in-time S&P 500 ∪ Nasdaq-100 membership in a new table via migration `002_*.sql` (§2.2, §6.1) |
| R3 | Nightly GitHub Actions job (~23:00 UTC Mon–Fri): latest session bars from Massive grouped daily + USD/IDR from Frankfurter, and a `runs` row with correct `data_date`/`session_date`; a failed fetch writes `status='failed'` and no partial bars (§2.3, §6.4, §6.5) |
| R4 | Idempotency: re-running any step for the same date changes nothing (§2.4, §6.3) |
| R5 | The first real engine write deletes all demo data atomically (§3 "Demo data", §6.6) |
| R6 | Unit tests for date logic, adjustment and idempotent upserts, plus a dry-run mode that writes nothing (§6.7) |

---

## Detailed Requirements Understanding

**Problem/Requirement Statement.** The repo has a live Neon schema (`001_init.sql`) and a
read-only Next.js app that today renders demo rows. Nothing writes real data. P1 builds a Python
package in `engine/` that (a) loads point-in-time index membership, (b) backfills ~11.75 years of
split-adjusted daily bars and USD/IDR history once, and (c) runs every US trading night from
GitHub Actions to append the newest session, keep splits consistent, record FX, and write one
`runs` row per target session.

**Success Criteria.** Handover §6, items 1–7, verbatim. Concretely:
- `SELECT count(DISTINCT symbol) FROM bars` covers every fetchable ever-member; `backfill_log`
  lists the rest with a reason.
- Running `nightly` twice for the same clock time leaves byte-identical tables (verified by
  per-table checksums).
- `dates.run_dates()` returns Friday→Monday, Friday-before-Memorial-Day→Tuesday, etc., under
  fixed-date unit tests.
- A forced Massive failure leaves `runs.status='failed'`, `error` set, and zero `bars` rows for
  the target date.
- With demo rows present, the first engine write truncates them in one transaction.
- `--dry-run` on any command performs all reads and computes all writes, then rolls back.

**Key Considerations.**
- *Storage* (Neon free = 0.5 GB). Measured response: 12,594 tickers/day for the whole market →
  ~3.2 M rows/year ≈ 400+ MB/year. Universe-only is ~800 ever-members (780 S&P intervals since
  2015 from `sp500_ticker_start_end.csv` + ~80 Nasdaq-only names), ~650 fetchable via yfinance,
  × ~2,950 sessions (2015-01-02 → 2026-10) ≈ 1.9 M rows × ~130 B (heap + PK index) ≈ **250 MB**,
  growing ~21 MB/year. → **store universe ∪ SPY only.** Measure `pg_total_relation_size('bars')`
  after the backfill and record it.
- *Adjustment.* Gotrade shows unadjusted-for-dividends prices; limit/TP/SL comparisons must match
  them. Both sources give **split-only** adjustment: yfinance with `auto_adjust=False` (its
  `Open/High/Low/Close/Volume` are split-adjusted; `Adj Close` is the dividend-adjusted one and is
  ignored); Massive `adjusted=true` is split-only. Splits that happen *after* a bar was stored
  must be re-applied to history → Massive `/v3/reference/splits?execution_date=` (verified on the
  free tier: NVDA 2024-06-10 `split_from=1, split_to=10`).
- *Ticker conventions.* Massive, fja05680 and thuningxu use dots (`BRK.B`); yfinance uses
  dashes (`BRK-B`). Canonical in `bars`/`universe` = dot form (also what Gotrade shows).
  Renames (FB→META) are point-in-time in the membership data; yfinance only knows the current
  ticker → an alias map stores membership under the bars symbol.
- *Dates.* `data_date` = latest NYSE session whose close (+1 h settle) ≤ now; `session_date` =
  next NYSE session after it. Half days are handled because the calendar's `market_close` is used.
- *Idempotency of `runs`.* "Run twice → identical contents" is only possible if a re-run for a
  session that already succeeded writes nothing; a re-run of a failed session reuses its row.
  Needs a partial unique index on `runs(session_date) WHERE NOT is_demo`.
- *Demo purge vs. backfill ordering.* `seed-demo.mjs` TRUNCATEs `bars`; demo rows are not
  distinguishable from real bars except by the existence of an `is_demo` run. So every engine
  write command purges first (guarded by "a demo run exists"), and the seed script must also
  refuse once real bars exist.

**Assumptions** (stated, planned against):
- Massive grouped daily for date D is available by 23:00 UTC (19:00 EDT/18:00 EST). A 01:00 UTC
  retry slot covers late publication.
- 5 calls/min is the binding Massive limit; the client spaces calls ≥ 12.5 s.
- yfinance 1.x from WSL works with modest throttling (batches of 40, 3 s pause, backoff on
  `YFRateLimitError`), resumable via `backfill_log`.
- A real Postgres is available for DB tests: GitHub Actions `postgres:16` service; locally
  Docker 28.4 (verified present) or `/usr/lib/postgresql/16/bin` (verified present).

### Settled open questions (handover §7)

| Question | Decision | Gaps documented |
|---|---|---|
| Historical membership source | **S&P 500:** fja05680/sp500 `S&P 500 Historical Components & Changes (Updated).csv` (MIT, commit `a2430f2af0`, last row 2026-08-18). **Nasdaq-100:** thuningxu/sp500nq100 `nasdaq100_components_history.csv` (same `date,tickers` format, commit `1cc1de2770`, last row 2026-05-18; built from Wikipedia's dated changes table, validated against today's components). Vendored into `engine/data/` with a dated overrides file for changes after each snapshot, and a weekly check against Wikipedia's current component lists that fails loudly on drift. | NDX: ENDP / CMCSK windows missing pre-2017; 2007–2014 may carry later symbols. Both: delisted names have no yfinance data (survivorship bias, already accepted in §3). |
| yfinance batching | `yf.download(batch, auto_adjust=False, actions=False, group_by="ticker", threads=False)` in batches of 40, 3 s between batches, exponential backoff (60/120/240 s) on rate-limit errors, per-symbol retry for empties, resumable via `backfill_log`. ~22 batches for ~850 symbols. | — |
| Store full market or universe | Universe ∪ SPY (estimate above). | Symbols added to an index later have bars only from when the backfill/nightly started covering them → `universe refresh` makes new members eligible for `backfill --symbols`. |
| SPY | `universe.BENCHMARK = "SPY"` is unioned into every symbol set the engine fetches. | — |

Recent changes to seed the overrides file with (from Wikipedia, 2026-10-03):
- NDX after 2026-05-18: 2026-06-22 +ALAB −CHTR, +CRWV −CTSH, +NBIS −INSM, +RKLB −VRSK, +TER −ZS;
  2026-06-29 +HONA; 2026-07-07 +SPCX; 2026-08-04 −EA; 2026-09-14 −KHC.
  (2026-05-18 +LITE −CSGP is already the snapshot's last row.)
- S&P 500 after 2026-08-18: 2026-09-21 +BE −TAP, +P −TTD, +ILMN −BLDR.

---

## Analysis Scope

### Explicitly Mentioned Files
- `docs/handover/2026-10-03-data-pipeline.md`
- `docs/plans/2026-10-03-seer-design.md`
- `docs/ROADMAP.md`
- `db/migrations/001_init.sql`
- `web/lib/data.ts`

### Discovered Related Files
- `web/scripts/migrate.mjs` — the migration runner the engine must stay compatible with
- `web/scripts/seed-demo.mjs` — writes the demo rows the engine must purge; TRUNCATEs `bars`
- `web/lib/session.ts` — the web's own stale check (`isStale`), which the engine's dates feed
- `web/lib/db.ts` — `neon(DATABASE_URL)` (pooled, read path)
- `.gitignore` — already ignores `__pycache__/`, `.venv/`, `.pytest_cache/`, `.env*`
- `.env.example` — already lists `MASSIVE_API_KEY`, `DATABASE_URL_UNPOOLED`

There is no `engine/` and no `.github/` directory yet.

---

## Current Dataflow

### Entry Point: web read path (the pipeline's consumer)

**Location:** `web/lib/data.ts:33` `runStatus()`
**Trigger:** every page render (server component)
**Reads:**
- `runs WHERE status='success' ORDER BY finished_at DESC LIMIT 1` → `session_date::text`,
  `data_date::text`, `finished_at`, `is_demo`
- `fx_rates ORDER BY date DESC LIMIT 1` → `usd_idr` (fallback 16500)
**Then:** `isStale(sessionDate, now)` (`web/lib/session.ts:37`) — stale when
`session_date < nextUsSession(now)`; `nextUsSession` ignores holidays (weekday-only), so an engine
`session_date` that skips a holiday is always ≥ the web's guess → never falsely stale.

`positions()` (`web/lib/data.ts:72`) reads the latest `bars.close` per open-order symbol
(`ORDER BY b.date DESC LIMIT 1`). Bars must use the same symbol string as `orders.symbol`
(dot form).

### Entry Point: migrations

**Location:** `web/scripts/migrate.mjs`
**Trigger:** `npm run db:migrate` in `web/` (`node --env-file=.env.local` — note: resolves
`.env.local` relative to `web/`, while the handover says it is at repo root).
**Behavior:** creates `schema_migrations`, applies `db/migrations/*.sql` in name order, each in
its own transaction, inserting the file name. A Python runner must use the identical table and
key (file name) so either runner can apply any migration exactly once.

### Entry Point: demo seed

**Location:** `web/scripts/seed-demo.mjs:113`
**Behavior:** refuses if `runs WHERE NOT is_demo` has rows; otherwise
`TRUNCATE action_dismissals, orders, equity_snapshots, bars, fx_rates, runs, strategies RESTART
IDENTITY CASCADE`, then inserts 4 strategies, one `is_demo=true` success run, one `fx_rates`
row (16,530), 6 demo `bars` rows on `dataDate`, orders, equity snapshots.
**Hazard:** after a backfill but before the first real `runs` row, running the seed would wipe
the backfilled bars.

### Data Persistence (schema the pipeline writes)

`db/migrations/001_init.sql`:
- `bars(symbol text, date date, open/high/low/close numeric(12,4), volume bigint, PK(symbol,date))`
- `fx_rates(date date PK, usd_idr numeric(12,4))`
- `runs(id bigserial, started_at, finished_at, status in running|success|failed, data_date,
  session_date, is_demo bool default false, error)` — no uniqueness on dates today
- `strategies` (seeded by demo script; P1 does not write it but must not delete it — `orders`
  references it)
- `schema_migrations(name PK, applied_at)`

### Exit Points
None yet — P1 creates them (see plan).

---

## Key Data Structures

### Table: `runs` — `db/migrations/001_init.sql:16`
Consumed by `runStatus()` (latest success by `finished_at`). P1 adds partial unique index on
`session_date WHERE NOT is_demo`.

### Table: `bars` — `001_init.sql:54`
Consumed by `positions()`. P1 is the sole writer (besides the demo seed).

### External: Massive grouped daily (verified 2026-10-03)
`GET https://api.massive.com/v2/aggs/grouped/locale/us/market/stocks/{YYYY-MM-DD}?adjusted=true&apiKey=…`
→ `{status:"OK", adjusted:true, resultsCount, results:[{T, o, h, l, c, v (float), vw, t (ms), n}]}`.
Sample 2026-10-01: SPY o 764.36 h 765.65 l 758.7901 c 763.99 v 47708058.813089; `BRK.B` dot form.

### External: Massive splits (verified on free tier)
`GET https://api.massive.com/v3/reference/splits?execution_date=YYYY-MM-DD&limit=1000&apiKey=…`
→ `results:[{ticker, execution_date, split_from, split_to}]`; NVDA 10-for-1 = from 1, to 10.
Pre-split price ÷ (split_to/split_from); pre-split volume × (split_to/split_from).

### External: Frankfurter
`GET https://api.frankfurter.dev/v1/latest?base=USD&symbols=IDR` → `{date, rates:{IDR}}`;
range `GET /v1/2015-01-01..2026-10-03?base=USD&symbols=IDR` → `{rates:{date:{IDR}}}`.

### External: membership CSVs
`date,tickers` where `tickers` is a quoted comma list = full membership effective on that date;
membership on D = latest row with `date ≤ D`.

---

## Dependencies

- **Python:** 3.11 (pyenv), new venv `engine/.venv`. Packages: `psycopg[binary]` 3.3,
  `pandas`, `pandas_market_calendars` 5.4, `yfinance` 1.7, `requests`, `python-dotenv`;
  dev `pytest`.
- **Env:** `DATABASE_URL_UNPOOLED` (writes), `MASSIVE_API_KEY`; local from repo-root
  `.env.local` (dotenv parser; `DATABASE_URL` has an unquoted `&`, so never `source` it).
- **GitHub:** repo `miftahulmahfuzh/seer` public, `origin/main` == local `main` @ `c059f59`.
  Secrets needed later: `DATABASE_URL_UNPOOLED`, `MASSIVE_API_KEY` — **owner action**.
- **Neon:** ap-southeast-1, free 0.5 GB.

---

## Reference List

New feature — the reference list is the set of existing sites the engine must agree with:

| Symbol / key | File:line | Kind | Package |
|---|---|---|---|
| `runs` status/date columns | `db/migrations/001_init.sql:16` | def | db |
| `bars` | `db/migrations/001_init.sql:54` | def | db |
| `fx_rates` | `db/migrations/001_init.sql:73` | def | db |
| `schema_migrations` | `db/migrations/001_init.sql:84`, `web/scripts/migrate.mjs:12` | def/use | db, web |
| `runStatus()` | `web/lib/data.ts:33` | consumer of runs, fx_rates | web |
| `positions()` latest close | `web/lib/data.ts:72` | consumer of bars | web |
| `isStale`, `nextUsSession` | `web/lib/session.ts:29,37` | consumer of session_date | web |
| demo refusal + TRUNCATE | `web/scripts/seed-demo.mjs:115-119` | writer | web/scripts |
| `MASSIVE_API_KEY`, `DATABASE_URL_UNPOOLED` | `.env.example` | config | root |
| P1 progress line | `docs/ROADMAP.md:15` | doc | docs |

---

## Impact Points (files that WILL need changes)

1. `db/migrations/002_engine.sql` — new: `universe`, `split_adjustments`, `backfill_log`, runs partial unique index — **phase 1**
2. `engine/pyproject.toml`, `engine/src/seer_engine/{__init__,__main__,cli,config,db,http,dates,demo,universe,bars,fx,runs}.py`, `engine/src/seer_engine/commands/{__init__,migrate}.py`, `engine/tests/{conftest,test_dates,test_db_helpers,test_demo}.py` — **phase 1**
3. `engine/data/*` (vendored CSVs, aliases, overrides, SOURCES.md), `engine/src/seer_engine/membership.py`, `commands/universe.py`, tests — **phase 2**
4. `engine/src/seer_engine/yahoo.py`, `commands/backfill.py`, tests — **phase 3**
5. `engine/src/seer_engine/{massive,splits}.py`, `commands/nightly.py`, tests — **phase 4**
6. `.github/workflows/{engine-ci,nightly,universe,backfill}.yml`, `web/scripts/seed-demo.mjs` (refusal guard), `docs/runbooks/data-pipeline.md`, `docs/ROADMAP.md`; live execution on Neon — **phase 5**

**This document describes. The plan files prescribe.**

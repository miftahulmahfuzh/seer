# Runbook — Seer data pipeline (P1)

Spec: [handover 2026-10-03](../handover/2026-10-03-data-pipeline.md) ·
Plan: `ENGINE_DATA_PIPELINE_PLAN.md` · Roadmap: [P1](../ROADMAP.md)

## Architecture

`engine/` is a Python 3.11 package, `seer_engine`, that writes into the same Neon Postgres the
web app reads. Writes go over `DATABASE_URL_UNPOOLED` with psycopg. `universe refresh` turns the
vendored point-in-time S&P 500 and Nasdaq-100 histories in `engine/data/` (plus
`membership_overrides.csv` and `ticker_aliases.csv`) into the `universe` table. `backfill` loads
split-adjusted daily bars for every symbol that was ever a member since 2015-01-02, plus SPY,
from yfinance, and USD/IDR history from Frankfurter. Each symbol's outcome is recorded in
`backfill_log`, so the backfill can resume. `nightly` runs after every US session. It computes
`data_date`/`session_date` from the NYSE calendar, fetches the missing sessions from Massive
grouped-daily (universe ∪ SPY, plus any symbol held or pending in paper state), applies new
splits once (`split_adjustments`), records each session's cash dividends (`dividends`), records the
FX rate, and finishes one `runs` row per session, all in one transaction. A failure marks the
run `failed` and writes no bars. Every write command first deletes the demo rows in its own
transaction, once. GitHub Actions supplies the schedule; Vercel only reads.

Paper trading (P4) runs after `nightly` in the same job: see [paper-trading.md](paper-trading.md).

## Commands

Install once: `python -m venv engine/.venv && engine/.venv/bin/pip install -e 'engine[dev]'`.
Locally the engine reads the repo-root `.env.local` itself. **Never `source .env.local`**:
`DATABASE_URL` contains an unquoted `&`. Raw `psql` hangs from this WSL machine (IPv6), so every
check below goes through Python.

| Command | What it does | Writes |
|---|---|---|
| `engine/.venv/bin/python -m seer_engine migrate` | applies `db/migrations/*.sql` not yet in `schema_migrations` (same table as `npm run db:migrate`) | schema |
| `… -m seer_engine universe refresh` | rebuilds `universe` from `engine/data/` in one transaction; no-op when unchanged | `universe` |
| `… -m seer_engine universe check` | compares today's computed members with Wikipedia's current lists; exits 1 on any difference | nothing |
| `… -m seer_engine backfill` | yfinance bars from 2015-01-02 to the last completed session for every ever-member ∪ SPY, plus Frankfurter FX; skips every symbol already in `backfill_log` (any status), so a re-run resumes | `bars`, `fx_rates`, `backfill_log` |
| `… backfill --symbols NEW1,NEW2` | backfill specific symbols (comma-separated, dot form); ignores `backfill_log` | same |
| `… backfill --retry-failed` | retry symbols logged `failed`/`empty` (never touches `ok`) | same |
| `… backfill --end YYYY-MM-DD` / `--batch-size N` | pin the last date (keep it fixed across resume passes on different days) / symbols per yfinance call (default 40) | same |
| `… backfill --fx-only` / `--skip-fx` | only / everything but the FX history | same |
| `… -m seer_engine nightly` | the nightly run for "now"; no-op if that session already succeeded | `bars`, `split_adjustments`, `dividends`, `fx_rates`, `runs` |
| `… nightly --now 2026-10-05T23:00:00Z` | replay the nightly as of a given UTC instant (format: `nightly --help`) | same |

Global flags go **before** the command: `--dry-run` does every read and computes every write,
then rolls back (nothing is written; the demo purge also runs and is rolled back, and is logged
as "would purge"). `-v` gives debug logs.
Example: `engine/.venv/bin/python -m seer_engine --dry-run -v nightly`.

Exit codes:

| Command | 0 | 1 | 2 |
|---|---|---|---|
| `backfill` | no symbol `failed`, FX loaded (`empty` = delisted/unknown to Yahoo is expected and fine) | some symbol `failed` (rate limit, download error) or FX failed; fetched bars are committed → re-run with `--retry-failed` (or `--fx-only`) | empty universe (run `universe refresh`) or bad arguments |
| `nightly` | run `success`, or the session already succeeded (no-op) | run marked `failed` with `error`; no bars written for it | `MASSIVE_API_KEY` or `DATABASE_URL_UNPOOLED` missing |
| `universe check` | identical to Wikipedia | drift (or a fetch/parse error) | — |
| any | — | uncaught error | missing setting (`ConfigError`) |

## Splits

- `backfill` records no splits: yfinance's `Open/High/Low/Close/Volume` (`auto_adjust=False`) are
  split-adjusted (not dividend-adjusted) as of the moment of the download.
- `nightly` fetches Massive's splits for every session it fetches (only sessions after SPY's
  latest stored bar, so never a split the backfill already saw). In one transaction it first
  applies **every** split in the gap to the history stored before this run (prices ÷
  `split_to/split_from`, volume ×), then upserts the fetched bars, which Massive already adjusted
  as of fetch time.
- Guard, in order: a split already in `split_adjustments` is never applied again; a symbol whose
  latest stored bar is on or after the execution date is already adjusted (recorded with
  `applied=false`); otherwise, for factors with `|ln f| ≥ ln 1.25` the price-ratio heuristic
  (`prev close` vs the first fetched open) decides, and smaller factors (stock dividends such as
  21:20) are applied because the stored history predates them by construction.
- Only splits of universe ∪ SPY symbols, or of symbols that already have bars, are recorded.
- Stored `dividends` rows with an ex-date before a split's execution date are rewritten with the
  bars (`amount × split_from / split_to`, 6 decimals), so dividends stay in the bars' units.
- Re-running `backfill --symbols X` after a split overwrites X's history with yfinance's newly
  adjusted values, which are consistent with what the nightly applied.

Tests: `PG_TEST_URL=… engine/.venv/bin/pytest engine/tests -q` (see "Local test database").
Without `PG_TEST_URL` the DB tests are skipped with a reason.

## Environment and secrets

| Variable | Used by | Where |
|---|---|---|
| `DATABASE_URL_UNPOOLED` | every engine command | `.env.local` locally; repo secret in Actions |
| `MASSIVE_API_KEY` | `nightly` only | `.env.local` locally; repo secret in Actions |
| `PG_TEST_URL` | tests only | your shell locally; set by `engine-ci.yml` in CI |

### Owner steps (need the owner's approval; not done by the pipeline session)

Run these from the main checkout `/home/miftah/seer` after the feature branch is merged into
`main`. The two secret commands pipe each value straight from `.env.local` through the engine's
dotenv parser, so nothing is echoed and nothing is `source`d:

```bash
cd /home/miftah/seer
test -x engine/.venv/bin/python || { python3.11 -m venv engine/.venv && engine/.venv/bin/pip install -q -e 'engine[dev]'; }
engine/.venv/bin/python -c 'from dotenv import dotenv_values; print(dotenv_values(".env.local")["DATABASE_URL_UNPOOLED"], end="")' \
  | gh secret set DATABASE_URL_UNPOOLED --repo miftahulmahfuzh/seer
engine/.venv/bin/python -c 'from dotenv import dotenv_values; print(dotenv_values(".env.local")["MASSIVE_API_KEY"], end="")' \
  | gh secret set MASSIVE_API_KEY --repo miftahulmahfuzh/seer
gh secret list --repo miftahulmahfuzh/seer          # both names listed
git push origin main
gh workflow run nightly.yml --repo miftahulmahfuzh/seer -f dry_run=true
gh run watch --repo miftahulmahfuzh/seer             # dry run must end green
gh workflow run universe.yml --repo miftahulmahfuzh/seer
```

Schedules only run from the default branch (`main`), so nothing is scheduled until that push.

## Workflows and schedule

| Workflow | Trigger | UTC | WIB (UTC+7) | New York |
|---|---|---|---|---|
| `nightly.yml` | cron `0 23 * * 1-5` | 23:00 Mon–Fri | 06:00 Tue–Sat | 19:00 EDT / 18:00 EST Mon–Fri |
| `nightly.yml` retry | cron `0 1 * * 2-6` | 01:00 Tue–Sat | 08:00 Tue–Sat | 21:00 EDT / 20:00 EST Mon–Fri |
| `universe.yml` | cron `30 0 * * 1` | 00:30 Mon | 07:30 Mon | 20:30 EDT / 19:30 EST Sun |
| `backfill.yml` | manual only (`start`, `symbols`, `retry_failed`) | — | — | — |
| `engine-ci.yml` | push / PR touching `engine/`, `db/`, `web/`, `.github/workflows/` | — | — | — |

- The NYSE close is 20:00 UTC in summer and 21:00 UTC in winter. The engine waits one hour of
  settle time, so 23:00 UTC is always after it. Half days close earlier and are covered too.
- GitHub cron often starts late, from minutes to about an hour. The retry slot covers a late
  start, and it covers Massive publishing late.
- Nightly, universe and backfill share the concurrency group `seer-db-writer`, so only one of
  them writes to Neon at a time. A run that is in progress is never cancelled. While a long
  backfill runs, a queued 23:00 nightly may be replaced by the 01:00 retry, which does the same
  work.
- Weekday holidays (for example Thanksgiving): the run that evening finds the same
  `session_date` that already succeeded the night before, and exits without writing anything.
- **60-day inactivity.** GitHub disables scheduled workflows in a public repo after 60 days
  without repository activity. The nightly job commits nothing, so this *will* happen. GitHub
  emails a warning about a week ahead. Re-enable with
  `gh workflow enable nightly.yml --repo miftahulmahfuzh/seer` (and `universe.yml`), or push any
  commit before the deadline.

## Failure modes and what the web shows

The web reads the latest `runs` row with `status='success'`. It shows the stale-data screen when
that row's `session_date` is earlier than the next US session (`web/lib/session.ts` `isStale`).

| Failure | Engine result | Workflow | Web | Fix |
|---|---|---|---|---|
| Massive down, 429, or not yet published | run row `failed` + `error`, **no bars** for that date | red; GitHub emails | stale screen (previous session's data) | nothing: the 01:00 retry reuses the failed row. Otherwise `gh workflow run nightly.yml` |
| Frankfurter down | same as above (FX is part of the nightly transaction) | red | stale screen | same |
| Secret missing or wrong | "Check secrets" step fails before Python starts, or the connection fails | red | stale screen | Owner steps above |
| Neon storage full (0.5 GB) | insert fails, run `failed` | red | stale screen | see Storage budget |
| Membership drift | — | `universe.yml` red | unaffected | see Membership maintenance |
| Backfill rate-limited or timed out | symbols stay non-`ok` in `backfill_log` | red (manual run) | unaffected | run it again (it resumes), then `--retry-failed` |
| Schedules disabled (60 days) | nothing runs | — | stale screen | `gh workflow enable …` |

Check the latest runs at any time:

```bash
cd /home/miftah/seer
engine/.venv/bin/python - <<'PY'
from seer_engine import config, db
config.load_env()
with db.connect() as conn:
    for r in conn.execute("SELECT id, status, data_date, session_date, started_at, finished_at, left(error, 120) "
                          "FROM runs WHERE NOT is_demo ORDER BY id DESC LIMIT 10"):
        print(r)
PY
```

## Membership maintenance

- `universe.yml` runs every Monday. A red run means Wikipedia's current S&P 500 or Nasdaq-100
  list differs from what `engine/data/` computes for today. The job log prints the added and
  removed symbols.
- Fix: append one line per change to `engine/data/membership_overrides.csv` as
  `date,index_id,action,ticker,note` (`index_id` is `SP500` or `NDX`, `action` is `add` or
  `remove`, ticker in dot form; see `engine/data/SOURCES.md`). The date must be after the
  snapshot file's last row, or `refresh` rejects it. Take the effective date from Wikipedia's "Selected changes" table, not
  from the date you noticed. Then run locally:
  `engine/.venv/bin/python -m seer_engine universe refresh && engine/.venv/bin/python -m seer_engine universe check`
  (it must exit 0). Commit the CSV and push.
- New members have bars only from the day the nightly started covering them. Load their history
  with `engine/.venv/bin/python -m seer_engine backfill --symbols NEW1,NEW2`, or use the Backfill
  workflow with `symbols` set.
- When an upstream snapshot is refreshed (fja05680/sp500, thuningxu/sp500nq100), re-vendor it as
  `engine/data/SOURCES.md` describes, and delete any overrides the new snapshot already contains.

## Renames going forward

yfinance and Massive only know a company's *current* ticker. When a member renames (FB→META style):

1. Add `OLD,NEW,<effective date>,<note>` to `engine/data/ticker_aliases.csv`
   (`old,new,effective_date,note`; see `engine/data/SOURCES.md`), so membership before the rename
   is stored under the symbol that has the bars. Every `old` must point at the **current**
   ticker: if an existing row already maps something to `OLD`, repoint it to `NEW` (the loader
   rejects chains).
2. Move the stored history to the new symbol, dropping any day the nightly already wrote under
   the new name:

   ```bash
   cd /home/miftah/seer
   OLD=FB NEW=META engine/.venv/bin/python - <<'PY'
   import os
   from seer_engine import config, db
   config.load_env()
   old, new = os.environ["OLD"], os.environ["NEW"]
   with db.connect() as conn:
       with conn.transaction():
           d = conn.execute("DELETE FROM bars o USING bars n WHERE o.symbol = %s AND n.symbol = %s AND n.date = o.date",
                            (old, new)).rowcount
           u = conn.execute("UPDATE bars SET symbol = %s WHERE symbol = %s", (new, old)).rowcount
           conn.execute("UPDATE backfill_log SET symbol = %s WHERE symbol = %s "
                        "AND NOT EXISTS (SELECT 1 FROM backfill_log WHERE symbol = %s)", (new, old, new))
       print(f"dropped {d} overlapping rows, moved {u} rows {old} -> {new}")
   PY
   ```
3. `engine/.venv/bin/python -m seer_engine universe refresh`, then commit the alias line.

## Storage budget

Neon free is 0.5 GB. Estimated before the backfill: about 1.9 M rows, about 250 MB for `bars`,
growing about 21 MB a year (universe ∪ SPY only, not the whole market). Measured after the first
backfill: see First run. Check:

```bash
cd /home/miftah/seer
engine/.venv/bin/python - <<'PY'
from seer_engine import config, db
config.load_env()
with db.connect() as conn:
    print(conn.execute("SELECT pg_size_pretty(pg_total_relation_size('bars')), "
                       "pg_size_pretty(pg_database_size(current_database()))").fetchone())
PY
```

Above 400 MB for `bars`: don't widen the universe. Instead consider dropping symbols that were
never members after the backtest window, or moving to a paid tier.

## Local test database

```bash
docker start seer-pg 2>/dev/null || docker run -d --name seer-pg -e POSTGRES_PASSWORD=pg -p 55432:5432 postgres:16
docker exec seer-pg pg_isready -U postgres -t 60
export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres
engine/.venv/bin/pytest engine/tests -q -rs     # DB tests must run, not skip
docker rm -f seer-pg             # when done
```

With no Docker, use `/usr/lib/postgresql/16/bin/initdb` and `pg_ctl` on a scratch directory and
point `PG_TEST_URL` at it. CI uses a `postgres:16` service with
`PG_TEST_URL=postgresql://postgres:postgres@localhost:5432/seer_test`.

## Health checks

Per-table fingerprint, used to prove a re-run changed nothing. The fingerprint is the row count
plus an order-independent sum of per-row md5 hashes. `string_agg` over about 2 M rows would hold
more than 100 MB in memory on Neon's free compute.

```bash
cd /home/miftah/seer
engine/.venv/bin/python - <<'PY'
from seer_engine import config, db
config.load_env()
with db.connect() as conn:
    for t in ["bars", "fx_rates", "runs", "universe", "split_adjustments", "backfill_log"]:
        n, h = conn.execute(f"SELECT count(*), coalesce(sum(('x' || left(md5(r::text), 15))::bit(60)::bigint), 0) "
                            f"FROM {t} r").fetchone()
        print(f"{t:18} rows={n:>9} hash={h}")
PY
```

## Rollback (data)

Restores the demo state, for example to re-test the purge:

```sql
DELETE FROM runs WHERE NOT is_demo;
TRUNCATE bars, fx_rates, universe, split_adjustments, backfill_log;
```

Run it through Python (`conn.execute(...)` in a `with conn.transaction():` block), then
`cd web && npm run db:seed-demo`. The seed now refuses only while real runs or more than 100
bars exist. Migration 002 is additive; dropping its three tables and the `runs_real_session_uidx`
index reverses it.

## First run — 2026-10-03

Run locally from the worktree `/home/miftah/.worktrees/seer/engine-data-pipeline`, against Neon.

**Workflow lint:** actionlint 1.7.12 (`rhysd/actionlint:latest` via Docker, shellcheck included): clean, exit 0, no findings for all four workflows.

**Tests:** `216 passed in 10.93s` (0 skipped; `PG_TEST_URL` = container `seer-pg`, Postgres 16); `vitest`: 4 files, `20 passed`.

**Before (demo state):** runs is_demo 1 (real 0) · orders 219 · equity_snapshots 264 · action_dismissals 0 · bars 6 · fx_rates 1 · strategies 4; `schema_migrations` = `001_init.sql`.

**migrate:** `--dry-run migrate` → "would apply 002_engine.sql", exit 0, nothing written; `migrate` → "apply 002_engine.sql", exit 0; second `migrate` → "nothing to apply". `schema_migrations` = `001_init.sql, 002_engine.sql`; tables `backfill_log, split_adjustments, universe` and index `runs_real_session_uidx` exist; demo counts unchanged by migrate (runs is_demo 1, bars 6, orders 219).

**universe refresh:** dry run logged "would purge demo data" and "would replace table with 1544 rows (dry run, rolled back)"; fingerprints before/after identical (`diff` empty). Real refresh: "1544 intervals, 1265 distinct symbols, 795 since 2015-01-01; current SP500=503 NDX=101 union=518; replaced table with 1544 rows". Second refresh: "unchanged, nothing written".
**Demo purge:** the real refresh logged "demo data found: truncated action_dismissals, orders, equity_snapshots, bars, fx_rates, runs". After: runs is_demo 0, orders 0, equity_snapshots 0, action_dismissals 0, bars 0, fx_rates 0; strategies unchanged (4); universe 1544 rows / 1265 symbols.
**universe check:** exit 0 — "SP500: computed 503, Wikipedia 503 -- identical", "NDX: computed 101, Wikipedia 101 -- identical". No override lines needed.

**backfill:** 06:02:28–06:15:21 UTC (13 min), one invocation `backfill --end 2026-10-02` (end pinned in `.workflows/live/backfill-end.txt`), 796 symbols in 20 batches of 40, 0 rate-limit failures. Then one `--retry-failed --end 2026-10-02` pass (exit 0): it re-tried the 133 `empty` symbols, all still empty, 663 `ok` skipped, 0 rows changed.
- backfill_log: ok 663 · empty 133 · failed 0
- not fetchable: 133 symbols, all `empty` ("yfinance returned no bars for 2015-01-02..2026-10-02"), none `failed`. They are delisted or acquired names whose history Yahoo no longer serves; **none of them is a current member** (`members_on(2026-10-02) ∩ empty = ∅`). `GPS` is the one rename among them (Gap Inc. now trades as `GAP`; no alias row yet, see Renames going forward). Full list: AABA (empty), ABMD (empty), ADS (empty), AET (empty), AGN (empty), ALTR (empty), ALXN (empty), ANDV (empty), ANSS (empty), ARG (empty), ATVI (empty), AVP (empty), BCR (empty), BRCM (empty), BXLT (empty), CA (empty), CCE (empty), CELG (empty), CERN (empty), CFN (empty), CHK (empty), CMA (empty), CMCSK (empty), COL (empty), COV (empty), CPGX (empty), CTL (empty), CTLT (empty), CTRA (empty), CTRX (empty), CTXS (empty), CVC (empty), CXO (empty), DAY (empty), DFS (empty), DISCK (empty), DISH (empty), DNB (empty), DNR (empty), DO (empty), DRE (empty), DTV (empty), DWDP (empty), ENDP (empty), ESRX (empty), ESV (empty), ETFC (empty), EVHC (empty), FDO (empty), FL (empty), FLIR (empty), FRC (empty), FTR (empty), GAS (empty), GGP (empty), GMCR (empty), GPS (empty), HAR (empty), HBI (empty), HCBK (empty), HES (empty), HOLX (empty), HOT (empty), HSP (empty), IPG (empty), JNPR (empty), JOY (empty), JWN (empty), K (empty), KORS (empty), KRFT (empty), KSU (empty), LLL (empty), LLTC (empty), LM (empty), LMCA (empty), LMCK (empty), LO (empty), LVLT (empty), MJN (empty), MNK (empty), MON (empty), MRO (empty), MWV (empty), MXIM (empty), NBL (empty), NDOI (empty), NLSN (empty), PBCT (empty), PCP (empty), PDCO (empty), PETM (empty), PLL (empty), PX (empty), PXD (empty), QEP (empty), QRTEA (empty), RAI (empty), RHT (empty), RTN (empty), SATS (empty), SCG (empty), SEE (empty), SGEN (empty), SHPG (empty), SIAL (empty), SIVB (empty), SNI (empty), SPLK (empty), SRCL (empty), STJ (empty), SWN (empty), SWY (empty), TEG (empty), TGNA (empty), TIF (empty), TSS (empty), TWC (empty), TWTR (empty), TWX (empty), VAR (empty), VIAB (empty), WBA (empty), WCG (empty), WFM (empty), WFMI (empty), WIN (empty), WRK (empty), WYND (empty), XEC (empty), XL (empty), XLNX (empty), YHOO (empty)
- bars: 1,817,429 rows across 663 symbols; SPY 2015-01-02 → 2026-10-02, 2,955 rows of 2,955 NYSE sessions in that range (no gap)
- coverage: `all_symbols(since=2015-01-02)` = 796 (ever-members ∪ SPY), of which 663 have bars; 133 missing, all logged `empty`; unexplained missing: none (`unexplained=[]`); no symbol in `bars` outside `all_symbols`. 99 of the 663 start after 2015-01-02 (listed or spun off later), so they hold their full available history rather than 10 years
- fx_rates: 3,009 rows, 2015-01-02 → 2026-10-02 (Frankfurter, every day it publishes)
- `pg_total_relation_size('bars')`: 177 MB (185,729,024 bytes), under the 400 MB stop line · database: 186 MB
- seed guard: `npm run db:seed-demo` → "Error: Real bars exist (backfill ran); refusing to overwrite with demo data." (thrown at `seed-demo.mjs:103`, before `BEGIN`), exit 1; bars still 1,817,429, strategies 4, runs 0

**nightly:** run 1 (06:23 UTC Sat) "now 2026-10-03T06:23:27Z -> data_date 2026-10-02, session_date 2026-10-05; bars already reach 2026-10-02; no sessions to fetch; wrote 0 bars over 0 session(s), 0 split(s) recorded (0 applied), fx 2026-10-02=17950.0000 (0 changed), run 1 success", exit 0. Because the backfill already reached `data_date`, run 1 made no Massive call. A separate read-only probe (`massive.Client.grouped(2026-10-02)` with the real key) returned closes identical to the backfilled bars (SPY 769.64, AAPL 333.69, MSFT 517.53, BRK.B 502.65) and 8 splits for that day, so the key and endpoint work. The first Massive write happens on the first scheduled nightly (Mon 2026-10-05 23:00 UTC) · run 2 "session 2026-10-05 already succeeded; nothing to do", exit 0 · dry run "already succeeded; nothing to do", transactions rolled back, exit 0
- runs row: id 1, status success, data_date 2026-10-02, session_date 2026-10-05 (the only real row) = `dates.run_dates(now)` `RunDates(data_date=2026-10-02, session_date=2026-10-05)`; assertion "runs dates: ok"
- fingerprints after run 1 / run 2 / dry run:

| table | rows | after run 1 | after run 2 | after dry run |
|---|---|---|---|---|
| bars | 1,817,429 | 1048483982293959805141698 | 1048483982293959805141698 | 1048483982293959805141698 |
| fx_rates | 3,009 | 1744655359371504148756 | 1744655359371504148756 | 1744655359371504148756 |
| runs | 1 | 43327952163727168 | 43327952163727168 | 43327952163727168 |
| universe | 1,544 | 890326075855417493314 | 890326075855417493314 | 890326075855417493314 |
| split_adjustments | 0 | 0 | 0 | 0 |
| backfill_log | 796 | 461998260082261274523 | 461998260082261274523 | 461998260082261274523 |

**Web read path:** over the pooled `DATABASE_URL` with `@neondatabase/serverless`: `run {session_date: 2026-10-05, data_date: 2026-10-02, is_demo: false}`, `fx {2026-10-02, usd_idr 17950.0000}`, `spy {2026-10-02, close 769.6400}`, `demoRuns 0`. `web/lib/session.ts` evaluated at 2026-10-03T06:26Z: `nextUsSession = 2026-10-05`, `isStale(2026-10-05) = false`, so no stale screen and no "Demo data" badge

### Acceptance (handover §6)

- [x] 1. Migration `002_engine.sql` adds `universe` (symbol, index, start/end) plus `split_adjustments`, `backfill_log`, `runs_real_session_uidx`; applied by the Python runner through `schema_migrations`. Evidence: migrate line above (`001_init.sql, 002_engine.sql`, three tables and the index present, second migrate "nothing to apply"); `engine/tests/test_migrate.py` (7 tests)
- [x] 2. `bars` holds ≥ 10 years for every fetchable ever-member; the rest are logged. Evidence: backfill lines above. 663 symbols / 1,817,429 rows from 2015-01-02 (later listings from their first day), SPY 2,955/2,955 sessions; the 133 unfetchable symbols are all in `backfill_log` as `empty` and listed above; 0 `failed`; no current member missing
- [x] 3. Nightly run twice for the same date leaves identical contents. Evidence: fingerprint table above, identical after run 1, run 2 and the dry run (`diff` empty); run 2 logged "already succeeded"; plus `test_same_now_twice_leaves_identical_tables`
- [x] 4. Friday → Monday (Tuesday after a Monday holiday); pre-holiday skips the holiday. Evidence: `test_run_dates` (25 cases: Fri→Mon, Labor Day / Memorial Day Fri→Tue, runs on the holiday Monday, Thanksgiving skip to the half day, Good Friday, year end), `test_last_completed_session_across_dst`, `test_sessions_inclusive_and_skip_holidays`, `test_next_and_prev_session` in `engine/tests/test_dates.py`, plus the live row (2026-10-02 Fri → 2026-10-05 Mon)
- [x] 5. A failed fetch writes `failed` + `error` and no partial bars; the web shows stale. Evidence: `test_massive_failure_marks_run_failed_and_writes_no_bars_then_rerun_reuses_row`, `test_fx_failure_marks_run_failed_and_writes_no_bars`, `test_empty_grouped_marks_run_failed`, `test_coverage_below_90_percent_fails`, `test_dry_run_failure_writes_nothing` in `engine/tests/test_nightly.py`. Stale display: a failed run is not `status='success'`, so the web keeps the previous session and `isStale` is true; not forced on Neon on purpose (it would leave a failed row for a real session)
- [x] 6. First real run removes all `is_demo` data atomically. Evidence: Before/Demo purge lines above
- [x] 7. Unit tests for dates, adjustment, idempotent upserts; dry-run writes nothing. Evidence: 216 passed, 0 skipped. Collected per file: dates 37 (parametrised), splits/adjustment 20, bars 12, fx 7, runs 8, backfill 32, nightly 22, membership 29 plus the unchanged dry-run fingerprints for universe refresh and nightly

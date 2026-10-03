# Phase 5: Workflows, seed guard, runbook, live run on Neon

**Plan set:** `ENGINE_DATA_PIPELINE_PLAN.md`
**Analysis:** `20261003-121931-K7P2_code_analyzer.md`
**Spec:** `docs/handover/2026-10-03-data-pipeline.md` (cited as §1–§7)
**Satisfies:** R1, R3, R5 (in practice): the backfill really runs against Neon (R1), the nightly job is scheduled in GitHub Actions and proven on Neon (R3), and the demo purge really happens on Neon, with the seed script refusing to undo it (R5)
**Depends on:** Phase 2, 3, 4 (and through them, Phase 1)
**Difficulty:** NORMAL (the file changes are small; the live run takes hours and needs care)
**Package:** `.github/workflows/`, `web/scripts/`, `docs/`

---

## Goal

After this phase the repo has four GitHub Actions workflows: CI on push and PR, the nightly
job with a retry slot, a weekly universe drift check, and a manual backfill. The demo seed
script also refuses to run once real bars exist. The engine has been run once, for real,
against Neon from this machine: migrate, universe refresh, the 10-year backfill, nightly run
twice. The results (row counts, failed symbols, `bars` size, identical checksums) are written
down in `docs/runbooks/data-pipeline.md`, with every handover §6 acceptance item ticked against
evidence. Pushing and setting secrets are left as owner steps with exact commands.

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.
**Creates:**
- `.github/workflows/engine-ci.yml`: workflow `CI`, jobs `engine` (pytest against a `postgres:16` service) and `web` (Node 20, `npm ci`, `npx vitest run`)
- `.github/workflows/nightly.yml`: workflow `Nightly`, cron `0 23 * * 1-5` plus retry cron `0 1 * * 2-6`, `workflow_dispatch` input `dry_run` (boolean)
- `.github/workflows/universe.yml`: workflow `Universe`, cron `30 0 * * 1` plus `workflow_dispatch`
- `.github/workflows/backfill.yml`: workflow `Backfill`, `workflow_dispatch` only, inputs `start` (string), `symbols` (string, comma-separated dot form), `retry_failed` (boolean), `batch_size` (string, default `40`), `dry_run` (boolean)
- `docs/runbooks/data-pipeline.md`: the operator runbook, including the "First run" evidence section
- Concurrency group `seer-db-writer`, shared by nightly, universe and backfill (one Neon writer at a time)

**Signature changes:** `web/scripts/seed-demo.mjs` also refuses when `SELECT count(*) FROM bars` > 100. The refusal message is `Real bars exist (backfill ran); refusing to overwrite with demo data.`

**Requires (from earlier phases):**
- CLI `python -m seer_engine [--dry-run] [-v] <command>`. Phase 1 accepts the global flags on either side of the command; every command in this plan set places them **before** it (Phase 1)
- `migrate` applies `db/migrations/*.sql` through `schema_migrations` (Phase 1)
- `seer_engine.config.load_env()` loads the repo-root `.env.local` when it exists. It must **not** fail when the file is missing (CI gets its env from secrets), and it must not overwrite variables already set in the process environment (Phase 1)
- `seer_engine.db.connect()` returns a `psycopg.Connection` usable as a context manager (Phase 1)
- `seer_engine.dates.run_dates(now_utc) -> RunDates(data_date, session_date)` and `dates.sessions(start, end)` (Phase 1)
- `seer_engine.universe.all_symbols(conn, since)` (Phase 1)
- Tables `universe`, `split_adjustments`, `backfill_log` exist after migration 002, and `backfill_log` has columns `symbol` and `status` with values `ok|empty|failed` (Phase 1)
- Every write command purges demo data first: `universe refresh` is the first write in this phase's live order (Phase 1, invariant 6)
- `universe refresh`, and `universe check` that exits non-zero on drift (Phase 2)
- `engine/data/membership_overrides.csv` and `engine/data/ticker_aliases.csv` with a format documented in the file header or `engine/data/SOURCES.md` (Phase 2)
- `backfill [--start YYYY-MM-DD] [--end YYYY-MM-DD] [--symbols A,B,C] [--retry-failed] [--skip-fx | --fx-only] [--batch-size N]`. By default it skips **every** symbol already in `backfill_log` (`ok`, `empty` or `failed`); `--retry-failed` re-attempts `failed` and `empty`; `--symbols` (a **comma-separated** list) ignores `backfill_log`. Exit codes: 0 = no symbol `failed` and FX loaded (`empty` symbols, i.e. delisted names, do not count); 1 = some symbol `failed` or the FX fetch failed (fetched bars stay committed); 2 = empty universe or bad arguments (Phase 3)
- `nightly [--now ISO8601]` exits 1 when it marks the run `failed`, 2 when `MASSIVE_API_KEY` is missing, and 0 with no writes when the target session already succeeded. It requires `MASSIVE_API_KEY`; no other command does (Phase 4)
- The membership data files are found when the package is installed **editable** (`pip install -e engine`). All workflows install that way (Phase 2)
- Engine tests make no network calls and use `PG_TEST_URL` (Phase 1 conftest). Locally that is phase 1's container `seer-pg`: `postgresql://postgres:pg@localhost:55432/postgres`

**Leaves alone (owned by others):** `engine/**` source, tests and `pyproject.toml` (Phases 1–4); `db/migrations/*` (Phase 1); `web/app/**`, `web/components/**`, `web/lib/**`; `web/scripts/migrate.mjs`. One exception, stated here so the reconciler sees it: if `universe check` reports drift during the live run, this phase appends lines to `engine/data/membership_overrides.csv` (Phase 2's file). That is **data maintenance in the format Phase 2 defines**, not a code change. See Step 11.

## Files

| File | Action | What changes |
|---|---|---|
| `.github/workflows/engine-ci.yml` | create | CI: engine pytest with a postgres:16 service, and a web vitest job |
| `.github/workflows/nightly.yml` | create | weekday nightly and retry slot, plus a manual dry-run |
| `.github/workflows/universe.yml` | create | weekly `universe refresh` and `universe check` |
| `.github/workflows/backfill.yml` | create | manual backfill with start/symbols/retry_failed |
| `web/scripts/seed-demo.mjs` | modify (line 3, after line 101) | header comment, plus refusal when `bars` > 100 rows |
| `docs/runbooks/data-pipeline.md` | create | runbook, plus first-run evidence and acceptance checklist |
| `docs/ROADMAP.md` | modify (line 15) | P1 progress marker |
| `engine/data/membership_overrides.csv` | append (only if drift) | new index changes Wikipedia shows (data maintenance) |

The live run also creates git-ignored files that are not committed: `.env.local` and `web/.env.local` symlinks, `engine/.venv/`, `web/node_modules/`, and `.workflows/live/*.log` (matched by the `*.log` ignore rule).

## Implementation Steps

### Step 0: Worktree prerequisites (no tracked changes)
**File:** none tracked.
**Change:** make the worktree runnable. `.env.local` lives only in the main checkout. The engine
reads the repo-root `.env.local`, and `npm run db:*` reads `web/.env.local`. Never `source` it.
**Code:**
```bash
cd /home/miftah/.worktrees/seer/engine-data-pipeline
ln -sfn /home/miftah/seer/.env.local .env.local
ln -sfn ../.env.local web/.env.local
git check-ignore -q .env.local && git check-ignore -q web/.env.local && echo "env symlinks ignored: ok"
test -x engine/.venv/bin/python || python3.11 -m venv engine/.venv
engine/.venv/bin/pip install -q -e 'engine[dev]'
(cd web && npm ci --no-audit --no-fund)
mkdir -p .workflows/live
```
**Impact:** nothing tracked changes. `git status` must stay clean apart from this phase's files.

### Step 1: CI workflow
**File:** `.github/workflows/engine-ci.yml` (new)
**Change:** CI for the engine and the web unit tests.
Decision: include the `web` job. It is cheap: `npm ci` plus about 4 pure test files, no build,
no env. It also closes P0's open item "CI runs lint + tests on push" for tests. No lint script
exists in the repo, so lint is out of scope; see Handoffs. Node is pinned to `20`, matching the
local 20.11.1 that Vitest 3 is pinned for. The paths filter includes `web/**` so web changes
are tested too.
**Code:**
```yaml
name: CI

on:
  push:
    paths:
      - 'engine/**'
      - 'db/**'
      - 'web/**'
      - '.github/workflows/**'
  pull_request:
    paths:
      - 'engine/**'
      - 'db/**'
      - 'web/**'
      - '.github/workflows/**'
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

jobs:
  engine:
    name: engine (pytest)
    runs-on: ubuntu-latest
    timeout-minutes: 15
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: seer_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd "pg_isready -U postgres -d seer_test"
          --health-interval 5s
          --health-timeout 5s
          --health-retries 12
    env:
      PG_TEST_URL: postgresql://postgres:postgres@localhost:5432/seer_test
      PYTHONUNBUFFERED: '1'
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: pip
          cache-dependency-path: engine/pyproject.toml

      - name: Install engine
        run: python -m pip install -e 'engine[dev]'

      - name: Test engine (DB tests must run, not skip)
        shell: bash
        run: |
          set -o pipefail
          python -m pytest engine/tests -q -rs | tee pytest.out
          if grep -q '^SKIPPED' pytest.out; then
            echo "::error::engine tests were skipped; PG_TEST_URL did not reach pytest"
            exit 1
          fi

  web:
    name: web (vitest)
    runs-on: ubuntu-latest
    timeout-minutes: 10
    defaults:
      run:
        working-directory: web
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: npm
          cache-dependency-path: web/package-lock.json

      - name: Install web
        run: npm ci --no-audit --no-fund

      - name: Test web
        run: npx vitest run
```
**Impact:** none locally. Runs on GitHub after the owner pushes.

### Step 2: Nightly workflow
**File:** `.github/workflows/nightly.yml` (new)
**Change:** weekday nightly at 23:00 UTC (06:00 WIB), with a 01:00 UTC retry slot. The retry is
a no-op when the session already succeeded (Phase 4's `start_run` returns None), and it reuses
the row when the earlier run failed. A manual dispatch can dry-run. Secrets are checked up front
so a missing secret gives a clear error instead of a stack trace. Flags are built in a bash array,
which keeps shellcheck/actionlint clean, and inputs reach the shell only through `env`, never
through `${{ }}` inside `run`.
Decision: the concurrency group is `seer-db-writer`, shared by nightly, universe and backfill,
not `nightly` alone. The brief named it `nightly`, but a 5-hour manual backfill and a nightly
writing `bars` at the same time would race on the same rows. One group serialises every Neon
writer. `cancel-in-progress: false` never kills a running writer. GitHub keeps at most one
*pending* run per group: when the 23:00 run is still queued behind a backfill, the 01:00 retry
replaces it. That is harmless, because the retry does the same work.
**Code:**
```yaml
name: Nightly

on:
  schedule:
    # 23:00 UTC Mon-Fri = 06:00 WIB Tue-Sat = 19:00 EDT / 18:00 EST after each US session.
    - cron: '0 23 * * 1-5'
    # Retry slot, 01:00 UTC Tue-Sat. No-op when the 23:00 run already succeeded.
    - cron: '0 1 * * 2-6'
  workflow_dispatch:
    inputs:
      dry_run:
        description: 'Fetch and compute everything, then roll back (writes nothing)'
        type: boolean
        default: false

permissions:
  contents: read

concurrency:
  group: seer-db-writer
  cancel-in-progress: false

jobs:
  nightly:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    env:
      DATABASE_URL_UNPOOLED: ${{ secrets.DATABASE_URL_UNPOOLED }}
      MASSIVE_API_KEY: ${{ secrets.MASSIVE_API_KEY }}
      DRY_RUN: ${{ inputs.dry_run == true }}
      PYTHONUNBUFFERED: '1'
    steps:
      - name: Check secrets
        run: |
          missing=0
          for name in DATABASE_URL_UNPOOLED MASSIVE_API_KEY; do
            if [ -z "${!name}" ]; then
              echo "::error::Repository secret $name is not set. See docs/runbooks/data-pipeline.md (Owner steps)."
              missing=1
            fi
          done
          exit "$missing"

      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: pip
          cache-dependency-path: engine/pyproject.toml

      - name: Install engine
        run: python -m pip install -e engine

      - name: Migrate
        run: |
          flags=()
          if [ "$DRY_RUN" = "true" ]; then flags+=(--dry-run); fi
          python -m seer_engine "${flags[@]}" migrate

      - name: Nightly
        run: |
          flags=(-v)
          if [ "$DRY_RUN" = "true" ]; then flags+=(--dry-run); fi
          python -m seer_engine "${flags[@]}" nightly
```
**Impact:** none until pushed and secrets are set.

### Step 3: Universe workflow
**File:** `.github/workflows/universe.yml` (new)
**Change:** weekly refresh plus drift check, Monday 00:30 UTC (07:30 WIB Monday, Sunday evening
ET). That slot clashes with no nightly slot, since there is no Sunday 23:00 run and no Monday
01:00 retry. `universe check` exits non-zero on drift, which turns the run red, and GitHub emails
the owner about failed scheduled runs. The job needs only the DB secret.
**Code:**
```yaml
name: Universe

on:
  schedule:
    # 00:30 UTC Monday = 07:30 WIB Monday = Sunday 20:30 EDT / 19:30 EST.
    - cron: '30 0 * * 1'
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: seer-db-writer
  cancel-in-progress: false

jobs:
  universe:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    env:
      DATABASE_URL_UNPOOLED: ${{ secrets.DATABASE_URL_UNPOOLED }}
      PYTHONUNBUFFERED: '1'
    steps:
      - name: Check secrets
        run: |
          if [ -z "$DATABASE_URL_UNPOOLED" ]; then
            echo "::error::Repository secret DATABASE_URL_UNPOOLED is not set. See docs/runbooks/data-pipeline.md (Owner steps)."
            exit 1
          fi

      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: pip
          cache-dependency-path: engine/pyproject.toml

      - name: Install engine
        run: python -m pip install -e engine

      - name: Migrate
        run: python -m seer_engine migrate

      - name: Refresh membership
        run: python -m seer_engine -v universe refresh

      - name: Check against Wikipedia (fails on drift)
        run: python -m seer_engine -v universe check
```
**Impact:** none until pushed.

### Step 4: Backfill workflow
**File:** `.github/workflows/backfill.yml` (new)
**Change:** manual backfill, used to add new index members (`symbols`) or to retry failures.
The first full backfill is done locally (Step 12). Yahoo throttles shared runner IPs more, and
the local run keeps a log you can watch. `timeout-minutes: 300` stays under GitHub's 360-minute
cap. A timed-out run is safe, because the backfill resumes when run again.
**Code:**
```yaml
name: Backfill

on:
  workflow_dispatch:
    inputs:
      start:
        description: 'First date to fetch (YYYY-MM-DD)'
        type: string
        default: '2015-01-02'
      symbols:
        description: 'Comma-separated symbols in dot form (BRK.B); empty = every ever-member'
        type: string
        default: ''
      retry_failed:
        description: 'Retry symbols logged as failed or empty'
        type: boolean
        default: false
      batch_size:
        description: 'Symbols per yfinance call'
        type: string
        default: '40'
      dry_run:
        description: 'Fetch and compute everything, then roll back (writes nothing)'
        type: boolean
        default: false

permissions:
  contents: read

concurrency:
  group: seer-db-writer
  cancel-in-progress: false

jobs:
  backfill:
    runs-on: ubuntu-latest
    timeout-minutes: 300
    env:
      DATABASE_URL_UNPOOLED: ${{ secrets.DATABASE_URL_UNPOOLED }}
      START: ${{ inputs.start }}
      SYMBOLS: ${{ inputs.symbols }}
      RETRY_FAILED: ${{ inputs.retry_failed }}
      BATCH_SIZE: ${{ inputs.batch_size }}
      DRY_RUN: ${{ inputs.dry_run == true }}
      PYTHONUNBUFFERED: '1'
    steps:
      - name: Check secrets
        run: |
          if [ -z "$DATABASE_URL_UNPOOLED" ]; then
            echo "::error::Repository secret DATABASE_URL_UNPOOLED is not set. See docs/runbooks/data-pipeline.md (Owner steps)."
            exit 1
          fi

      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: pip
          cache-dependency-path: engine/pyproject.toml

      - name: Install engine
        run: python -m pip install -e engine

      - name: Migrate
        run: |
          flags=()
          if [ "$DRY_RUN" = "true" ]; then flags+=(--dry-run); fi
          python -m seer_engine "${flags[@]}" migrate

      - name: Refresh membership
        run: |
          flags=(-v)
          if [ "$DRY_RUN" = "true" ]; then flags+=(--dry-run); fi
          python -m seer_engine "${flags[@]}" universe refresh

      - name: Backfill
        # Exit 0: no symbol failed (delisted names land as `empty` and are fine).
        # Exit 1: some symbol failed (rate limit) or FX failed; re-run with retry_failed.
        # Exit 2: empty universe or bad input.
        run: |
          flags=(-v)
          if [ "$DRY_RUN" = "true" ]; then flags+=(--dry-run); fi
          args=(--start "$START" --batch-size "${BATCH_SIZE:-40}")
          if [ -n "$SYMBOLS" ]; then args+=(--symbols "$SYMBOLS"); fi
          if [ "$RETRY_FAILED" = "true" ]; then args+=(--retry-failed); fi
          python -m seer_engine "${flags[@]}" backfill "${args[@]}"
```
**Impact:** none until pushed.

### Step 5: Validate the workflows
**File:** `.github/workflows/*.yml`
**Change:** lint them. Try actionlint through Docker first (Docker 28.4 is installed; the image
also runs shellcheck on `run:` blocks). If the image cannot be pulled, fall back to a YAML parse
plus a structural assertion (system `python3` has PyYAML 6.0.3).
**Code:**
```bash
cd /home/miftah/.worktrees/seer/engine-data-pipeline
if docker run --rm -v "$PWD:/repo" -w /repo rhysd/actionlint:latest -color; then
  echo "actionlint: clean"
else
  rc=$?
  echo "actionlint exited $rc (findings above, or the image is unavailable)"
fi
```
If actionlint printed findings, fix them in the YAML above and run it again. Only when Docker or
the image itself is unavailable, run the fallback:
```bash
cd /home/miftah/.worktrees/seer/engine-data-pipeline
python3 - <<'PY'
import pathlib, yaml
for p in sorted(pathlib.Path(".github/workflows").glob("*.yml")):
    doc = yaml.safe_load(p.read_text())
    on = doc.get("on", doc.get(True))  # PyYAML parses a bare `on:` key as True
    assert doc["permissions"] == {"contents": "read"}, p
    assert on, p
    for name, job in doc["jobs"].items():
        assert "timeout-minutes" in job, (p, name)
        assert job["steps"], (p, name)
    print(f"{p}: ok ({', '.join(doc['jobs'])})")
PY
```
**Impact:** none. Write the result (actionlint clean, or the fallback and why) into the runbook's First-run section.

### Step 6: Seed guard
**File:** `web/scripts/seed-demo.mjs:3` and `web/scripts/seed-demo.mjs:100-101`
**Change:** after the backfill, and before the first real `runs` row exists, the current guard
lets the seed `TRUNCATE bars` and wipe roughly 1.9 M backfilled rows. Add a second refusal when
`bars` has more than 100 rows. The demo writes 6, so 100 leaves a wide margin. Both checks run
before `BEGIN`, so a refusal touches nothing. The style matches the existing check: one
`c.query`, one `throw`.

Current lines 3 and 100–101, exactly:
```js
// Refuses to run once the real engine has written a run.
```
```js
  const real = await c.query('SELECT count(*)::int AS n FROM runs WHERE NOT is_demo');
  if (real.rows[0].n > 0) throw new Error('Real engine runs exist; refusing to overwrite with demo data.');
```
**Code:** replace line 3 with
```js
// Refuses to run once the real engine has written a run or backfilled bars.
```
and replace lines 100–101 with
```js
  const real = await c.query('SELECT count(*)::int AS n FROM runs WHERE NOT is_demo');
  if (real.rows[0].n > 0) throw new Error('Real engine runs exist; refusing to overwrite with demo data.');
  const bars = await c.query('SELECT count(*)::int AS n FROM bars');
  if (bars.rows[0].n > 100) throw new Error('Real bars exist (backfill ran); refusing to overwrite with demo data.');
```
**Impact:** `npm run db:seed-demo` now refuses after a backfill. Before a backfill it behaves as
before: the demo has 6 bars, at most a few dozen even after repeated seeds, since it truncates first.
Static check:
```bash
cd /home/miftah/.worktrees/seer/engine-data-pipeline
node --check web/scripts/seed-demo.mjs && echo "syntax ok"
awk '/Real bars exist/{g=NR} /query\(.BEGIN.\)/{b=NR} END{ if (g && b && g<b) print "guard before BEGIN: ok (" g "<" b ")"; else { print "GUARD ORDER WRONG"; exit 1 } }' web/scripts/seed-demo.mjs
```

### Step 7: Runbook
**File:** `docs/runbooks/data-pipeline.md` (new; `docs/runbooks/` does not exist yet)
**Change:** write the runbook below. Everything is final text except the **First run** section,
whose `⟨…⟩` slots are filled with real output during Steps 9–15. No slot may stay unfilled at
the end of the phase. Don't add a README (owner rule).
**Code:**
````markdown
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
grouped-daily (universe ∪ SPY only), applies new splits once (`split_adjustments`), records the
FX rate, and finishes one `runs` row per session, all in one transaction. A failure marks the
run `failed` and writes no bars. Every write command first deletes the demo rows in its own
transaction, once. GitHub Actions supplies the schedule; Vercel only reads.

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
| `… -m seer_engine nightly` | the nightly run for "now"; no-op if that session already succeeded | `bars`, `split_adjustments`, `fx_rates`, `runs` |
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

## First run — ⟨YYYY-MM-DD of the nightly checksum step⟩

Run locally from the worktree `/home/miftah/.worktrees/seer/engine-data-pipeline`, against Neon.

**Workflow lint:** ⟨"actionlint (rhysd/actionlint:latest): clean", or the YAML-parse fallback and why⟩

**Tests:** ⟨`N passed, M skipped` line from pytest with PG_TEST_URL set; `vitest`: `N passed`⟩

**Before (demo state):** ⟨demo counts: runs is_demo / orders / equity_snapshots / action_dismissals / bars / fx_rates / strategies⟩

**migrate:** ⟨output; schema_migrations = 001_init.sql, 002_engine.sql⟩

**universe refresh:** ⟨dry-run fingerprint unchanged: yes; real refresh output: N intervals, M distinct symbols; second refresh: no-op⟩
**Demo purge:** ⟨counts after the first real write: runs is_demo 0, orders 0, equity_snapshots 0, action_dismissals 0, bars 0, fx_rates 0; strategies unchanged (4)⟩
**universe check:** ⟨exit 0, or the drift found + override lines added + rerun exit 0⟩

**backfill:** ⟨start–end time, number of invocations, then `--retry-failed`⟩
- backfill_log: ⟨ok N · empty N · failed N⟩
- not fetchable: ⟨comma list of symbol (status), or "none"⟩
- bars: ⟨rows⟩ across ⟨distinct symbols⟩; SPY ⟨min date⟩ → ⟨max date⟩, ⟨rows⟩ of ⟨NYSE sessions in that range⟩
- coverage: ⟨len(all_symbols) ever-members∪SPY, of which N have bars; unexplained missing: none⟩
- fx_rates: ⟨rows, min → max date⟩
- `pg_total_relation_size('bars')`: ⟨pretty (bytes)⟩ · database: ⟨pretty⟩
- seed guard: `npm run db:seed-demo` → ⟨"Real bars exist (backfill ran); refusing to overwrite with demo data.", exit 1; bars count unchanged⟩

**nightly:** run 1 ⟨output summary: data_date, session_date, sessions fetched, bars upserted, splits applied⟩ · run 2 ⟨"already succeeded" no-op⟩ · dry run ⟨no-op⟩
- runs row: ⟨id, status success, data_date, session_date⟩ = `dates.run_dates(now)` ⟨printed RunDates⟩
- fingerprints after run 1 / run 2 / dry run:

| table | rows | after run 1 | after run 2 | after dry run |
|---|---|---|---|---|
| bars | ⟨⟩ | ⟨⟩ | ⟨⟩ | ⟨⟩ |
| fx_rates | ⟨⟩ | ⟨⟩ | ⟨⟩ | ⟨⟩ |
| runs | ⟨⟩ | ⟨⟩ | ⟨⟩ | ⟨⟩ |
| universe | ⟨⟩ | ⟨⟩ | ⟨⟩ | ⟨⟩ |
| split_adjustments | ⟨⟩ | ⟨⟩ | ⟨⟩ | ⟨⟩ |
| backfill_log | ⟨⟩ | ⟨⟩ | ⟨⟩ | ⟨⟩ |

**Web read path:** ⟨runStatus query: session_date, data_date, is_demo false, usd_idr; stale = false because session_date ≥ next US session⟩

### Acceptance (handover §6)

- [ ] 1. Migration `002_engine.sql` adds `universe` (symbol, index, start/end) plus `split_adjustments`, `backfill_log`, `runs_real_session_uidx`; applied by the Python runner through `schema_migrations`. Evidence: ⟨⟩
- [ ] 2. `bars` holds ≥ 10 years for every fetchable ever-member; the rest are logged. Evidence: ⟨⟩
- [ ] 3. Nightly run twice for the same date leaves identical contents. Evidence: fingerprint table above, ⟨⟩
- [ ] 4. Friday → Monday (Tuesday after a Monday holiday); pre-holiday skips the holiday. Evidence: ⟨pytest test names from engine/tests/test_dates.py⟩ plus the live row (⟨data_date⟩ → ⟨session_date⟩)
- [ ] 5. A failed fetch writes `failed` + `error` and no partial bars; the web shows stale. Evidence: ⟨test names in engine/tests/test_nightly.py⟩; not forced on Neon on purpose (it would leave a failed row for a real session)
- [ ] 6. First real run removes all `is_demo` data atomically. Evidence: Before/Demo purge lines above
- [ ] 7. Unit tests for dates, adjustment, idempotent upserts; dry-run writes nothing. Evidence: ⟨test counts⟩ plus the unchanged dry-run fingerprints for universe refresh and nightly
````
**Impact:** docs only.

### Step 8: Engine and web tests green (live step 1)
**File:** none (evidence goes to the runbook "Tests" line).
**Code:** phase 1's test container (`seer-pg`, port 55432) is reused; do not start a second
container on the same port.
```bash
cd /home/miftah/.worktrees/seer/engine-data-pipeline
docker start seer-pg 2>/dev/null || docker run -d --name seer-pg -e POSTGRES_PASSWORD=pg -p 55432:5432 postgres:16
docker exec seer-pg pg_isready -U postgres -t 60
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q -rs
(cd web && npx vitest run)
```
**Exit:** pytest reports 0 failed and 0 DB skips (`-rs` lists any skip; a skip with the reason "PG_TEST_URL unset" means the env var did not reach the process). Vitest is green. **Stop here if anything fails.** Engine failures belong to Phases 1–4; record them under Handoffs rather than fixing them in this phase.

### Step 9: Migrate Neon (live step 2)
**Code:**
```bash
cd /home/miftah/.worktrees/seer/engine-data-pipeline
PY=engine/.venv/bin/python
# demo-state snapshot, recorded under "Before"
$PY - <<'PY'
from seer_engine import config, db
config.load_env()
with db.connect() as conn:
    print(conn.execute("""SELECT (SELECT count(*) FROM runs WHERE is_demo) AS demo_runs,
        (SELECT count(*) FROM runs WHERE NOT is_demo) AS real_runs,
        (SELECT count(*) FROM orders) AS orders, (SELECT count(*) FROM equity_snapshots) AS equity,
        (SELECT count(*) FROM action_dismissals) AS dismissals, (SELECT count(*) FROM bars) AS bars,
        (SELECT count(*) FROM fx_rates) AS fx, (SELECT count(*) FROM strategies) AS strategies""").fetchone())
    print([r[0] for r in conn.execute("SELECT name FROM schema_migrations ORDER BY name")])
PY
$PY -m seer_engine --dry-run migrate
$PY -m seer_engine migrate
$PY -m seer_engine migrate        # second run: nothing to apply
$PY - <<'PY'
from seer_engine import config, db
config.load_env()
with db.connect() as conn:
    print([r[0] for r in conn.execute("SELECT name FROM schema_migrations ORDER BY name")])
    print([r[0] for r in conn.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' "
                                      "AND tablename IN ('universe','split_adjustments','backfill_log') ORDER BY 1")])
    print(conn.execute("SELECT indexname FROM pg_indexes WHERE indexname='runs_real_session_uidx'").fetchone())
PY
```
**Exit:** `schema_migrations` lists `001_init.sql` and `002_engine.sql`, the three tables and the index exist, the second migrate applies nothing, and the demo counts are still unchanged (migrate does not purge).

### Step 10: Universe refresh and demo purge (live step 3)
**Code:**
```bash
cd /home/miftah/.worktrees/seer/engine-data-pipeline
PY=engine/.venv/bin/python
fp() { $PY - <<'PY'
from seer_engine import config, db
config.load_env()
with db.connect() as conn:
    for t in ["bars", "fx_rates", "runs", "universe", "split_adjustments", "backfill_log"]:
        n, h = conn.execute(f"SELECT count(*), coalesce(sum(('x' || left(md5(r::text), 15))::bit(60)::bigint), 0) FROM {t} r").fetchone()
        print(f"{t:18} rows={n:>9} hash={h}")
PY
}
fp > .workflows/live/fp-before-universe-dry.log
$PY -m seer_engine --dry-run -v universe refresh 2>&1 | tee .workflows/live/universe-dry.log
fp > .workflows/live/fp-after-universe-dry.log
diff .workflows/live/fp-before-universe-dry.log .workflows/live/fp-after-universe-dry.log && echo "dry-run wrote nothing: ok"
$PY -m seer_engine -v universe refresh 2>&1 | tee .workflows/live/universe-1.log
$PY -m seer_engine -v universe refresh 2>&1 | tee .workflows/live/universe-2.log   # must report no change
$PY - <<'PY'
from seer_engine import config, db
config.load_env()
with db.connect() as conn:
    print(conn.execute("""SELECT (SELECT count(*) FROM runs WHERE is_demo), (SELECT count(*) FROM orders),
        (SELECT count(*) FROM equity_snapshots), (SELECT count(*) FROM action_dismissals),
        (SELECT count(*) FROM bars), (SELECT count(*) FROM fx_rates), (SELECT count(*) FROM strategies),
        (SELECT count(*) FROM universe), (SELECT count(DISTINCT symbol) FROM universe)""").fetchone())
PY
```
**Exit:** the dry run left the fingerprints unchanged. After the real refresh, demo rows are 0 in
runs, orders, equity_snapshots, action_dismissals, bars and fx_rates, and `strategies` is
unchanged. `universe` is populated, and the second refresh reports no change. Record it all.

### Step 11: Universe check and drift fix (live step 3, continued)
**Code:**
```bash
cd /home/miftah/.worktrees/seer/engine-data-pipeline
engine/.venv/bin/python -m seer_engine -v universe check; echo "exit=$?"
```
**Decision:** fixing drift **is allowed in this phase** as data maintenance, because it is the
exact procedure the runbook documents for the owner, and it is the first time that procedure
runs. When the check exits 1, append the reported changes to
`engine/data/membership_overrides.csv` in Phase 2's format. Take each effective date from
Wikipedia's change table for that index (the analysis already lists every change known up to
2026-10-03; Phase 2 should have seeded those). Then rerun `universe refresh` and `universe
check` until the check exits 0. **Do not** edit `membership.py` or any other code. If the drift
cannot be expressed as override lines (for example a parsing bug in the check), stop. Record the
diff in the runbook and in Handoffs for Phase 2, and go on with the backfill: the backfill uses
`all_symbols` since 2015, and a one-name drift changes today's membership, not the history.
**Exit:** `exit=0`, or a recorded and justified stop.

### Step 12: Backfill (live step 4)
**Code:**
```bash
cd /home/miftah/.worktrees/seer/engine-data-pipeline
PY=engine/.venv/bin/python
$PY -m seer_engine --dry-run -v backfill --symbols SPY,BRK.B --skip-fx 2>&1 | tail -n 20   # smoke test: dot→dash conversion, nothing written
# Pin the end date once, so every resume pass (even on a later day) ends on the same session.
$PY -c 'from datetime import datetime, timezone; from seer_engine import dates; print(dates.last_completed_session(datetime.now(timezone.utc)))' > .workflows/live/backfill-end.txt
END=$(cat .workflows/live/backfill-end.txt)
nohup $PY -m seer_engine -v backfill --end "$END" > .workflows/live/backfill-1.log 2>&1 &
echo $! > .workflows/live/backfill.pid
```
Poll every ~10 minutes with `tail -n 5 .workflows/live/backfill-1.log` and
`kill -0 "$(cat .workflows/live/backfill.pid)"` (use the Monitor tool where available; never
block on a foreground `sleep`). Expect 1–3 h. If the process dies or is killed (for example a
`psycopg.OperationalError` after Neon auto-suspended during a long rate-limit backoff), start it
again with the same `--end "$(cat .workflows/live/backfill-end.txt)"` and a new log number
(`backfill-2.log`, …). It resumes, because every symbol already in `backfill_log` is skipped.
A pass that ends with exit 1 has `failed` symbols (rate limits); exit 0 with a list of `empty`
symbols is the normal outcome (delisted names, roughly 145 expected). When a pass finishes:
```bash
cd /home/miftah/.worktrees/seer/engine-data-pipeline
engine/.venv/bin/python -m seer_engine -v backfill --retry-failed --end "$(cat .workflows/live/backfill-end.txt)" > .workflows/live/backfill-retry.log 2>&1; echo "exit=$?"
engine/.venv/bin/python - <<'PY'
from datetime import date
from seer_engine import config, db, dates, universe
config.load_env()
since = date(2015, 1, 2)
with db.connect() as conn:
    print("backfill_log:", conn.execute("SELECT status, count(*) FROM backfill_log GROUP BY status ORDER BY status").fetchall())
    for r in conn.execute("SELECT * FROM backfill_log WHERE status <> 'ok' ORDER BY symbol"):
        print("  not ok:", r)
    want = set(universe.all_symbols(conn, since))
    have = {r[0] for r in conn.execute("SELECT DISTINCT symbol FROM bars")}
    status = dict(conn.execute("SELECT symbol, status FROM backfill_log").fetchall())
    missing = sorted(want - have)
    unexplained = [s for s in missing if status.get(s) in (None, "ok")]
    print(f"ever-members∪SPY={len(want)} with_bars={len(want & have)} missing={len(missing)} unexplained={unexplained}")
    print("extra symbols in bars (not in all_symbols):", sorted(have - want))
    print("bars rows:", conn.execute("SELECT count(*) FROM bars").fetchone()[0])
    lo, hi, n = conn.execute("SELECT min(date), max(date), count(*) FROM bars WHERE symbol = 'SPY'").fetchone()
    print(f"SPY {lo} -> {hi}: {n} rows, NYSE sessions in range: {len(dates.sessions(lo, hi))}")
    print("fx_rates:", conn.execute("SELECT count(*), min(date), max(date) FROM fx_rates").fetchone())
    print("size:", conn.execute("SELECT pg_size_pretty(pg_total_relation_size('bars')), pg_total_relation_size('bars'), "
                                "pg_size_pretty(pg_database_size(current_database()))").fetchone())
PY
```
Repeat the `--retry-failed` pass (new log name each time) while it still reduces the `failed`
count; whatever stays `failed` after that is recorded in the runbook as not fetchable, with its
error.
**Exit:** `unexplained=[]`. SPY starts on 2015-01-02 and its row count equals the NYSE session
count; a small shortfall is acceptable only if the log explains it. `pg_total_relation_size('bars')`
< 400 MB (419430400 bytes). **If it is larger, stop**: record the size and leave the nightly
step to the owner.

Then test the seed guard live. This is the only window where it is the deciding check, because
real bars exist and no real run does yet. The seed's guard runs before `BEGIN`, which Step 6's
awk check proved. Run the awk check again right before:
```bash
cd /home/miftah/.worktrees/seer/engine-data-pipeline
awk '/Real bars exist/{g=NR} /query\(.BEGIN.\)/{b=NR} END{ exit !(g && b && g<b) }' web/scripts/seed-demo.mjs && \
  (cd web && npm run db:seed-demo; echo "seed exit=$?")
```
**Exit:** it prints `Real bars exist (backfill ran); refusing to overwrite with demo data.` with
a non-zero exit, and the `bars` row count is the same as before. If it ever seeds by mistake,
recover with `TRUNCATE backfill_log` (through Python), rerun `universe refresh` (to purge the
demo), and rerun the backfill.

### Step 13: Nightly ×2, dry run, checksums, run dates (live step 5)
**Code:**
```bash
cd /home/miftah/.worktrees/seer/engine-data-pipeline
PY=engine/.venv/bin/python
fp() { $PY - <<'PY'
from seer_engine import config, db
config.load_env()
with db.connect() as conn:
    for t in ["bars", "fx_rates", "runs", "universe", "split_adjustments", "backfill_log"]:
        n, h = conn.execute(f"SELECT count(*), coalesce(sum(('x' || left(md5(r::text), 15))::bit(60)::bigint), 0) FROM {t} r").fetchone()
        print(f"{t:18} rows={n:>9} hash={h}")
PY
}
$PY -m seer_engine -v nightly 2>&1 | tee .workflows/live/nightly-1.log; echo "exit=${pipestatus[1]}"
fp | tee .workflows/live/fp-nightly-1.log
$PY -m seer_engine -v nightly 2>&1 | tee .workflows/live/nightly-2.log; echo "exit=${pipestatus[1]}"
fp | tee .workflows/live/fp-nightly-2.log
$PY -m seer_engine --dry-run -v nightly 2>&1 | tee .workflows/live/nightly-dry.log
fp | tee .workflows/live/fp-nightly-dry.log
diff .workflows/live/fp-nightly-1.log .workflows/live/fp-nightly-2.log && \
diff .workflows/live/fp-nightly-2.log .workflows/live/fp-nightly-dry.log && echo "identical: ok"
$PY - <<'PY'
from datetime import datetime, timezone
from seer_engine import config, db, dates
config.load_env()
rd = dates.run_dates(datetime.now(timezone.utc))
with db.connect() as conn:
    rows = conn.execute("SELECT id, status, data_date, session_date, started_at, finished_at, error "
                        "FROM runs WHERE NOT is_demo ORDER BY id").fetchall()
for r in rows:
    print(r)
print("run_dates(now):", rd)
last = rows[-1]
assert last[1] == "success" and (last[2], last[3]) == (rd.data_date, rd.session_date), "runs row dates disagree with dates.run_dates(now)"
assert len([r for r in rows if r[3] == rd.session_date]) == 1, "more than one runs row for the session"
print("runs dates: ok")
PY
```
(`${pipestatus[1]}` is zsh, which is the user's shell. In bash it is `${PIPESTATUS[0]}`.)

Expected on 2026-10-03/04 (weekend WIB): `data_date = 2026-10-02` (Fri) and `session_date =
2026-10-05` (Mon). Run 2 and the dry run are "already succeeded" no-ops with exit 0.
**Exit:** both nightly exits are 0, all three fingerprint files are identical, there is exactly
one real `runs` row for the session, and its dates equal `run_dates(now)`. When run 1 exits
non-zero, record the `runs.error` and stop. That is a Phase 4 defect, so put it in Handoffs. A
failed row is reused by the next attempt, so rerunning after a fix is safe.

### Step 14: Web read path (live step 6)
**Code:** use the same driver and the same SQL as `web/lib/data.ts:31-33`, over the pooled
`DATABASE_URL` that `web/lib/db.ts` uses:
```bash
cd /home/miftah/.worktrees/seer/engine-data-pipeline/web
node --env-file=.env.local --input-type=module - <<'JS'
import { Pool, neonConfig } from '@neondatabase/serverless';
import ws from 'ws';
neonConfig.webSocketConstructor = ws;
const pool = new Pool({ connectionString: process.env.DATABASE_URL });
const run = await pool.query(`SELECT session_date::text, data_date::text, finished_at, is_demo FROM runs
  WHERE status = 'success' ORDER BY finished_at DESC LIMIT 1`);
const fx = await pool.query('SELECT date::text, usd_idr FROM fx_rates ORDER BY date DESC LIMIT 1');
const spy = await pool.query(`SELECT date::text, close FROM bars WHERE symbol = 'SPY' ORDER BY date DESC LIMIT 1`);
const demo = await pool.query('SELECT count(*)::int AS n FROM runs WHERE is_demo');
console.log({ run: run.rows[0], fx: fx.rows[0], spy: spy.rows[0], demoRuns: demo.rows[0].n });
await pool.end();
JS
```
**Exit:** `run.is_demo === false`, `demoRuns === 0`, `run.session_date` equals the Step 13
`session_date`, `fx.usd_idr` is a real rate (about 17,950, not the demo's 16,530), and the SPY
date equals `data_date`. Expected screen: no "Demo data" badge and not stale, because
`session_date` ≥ `nextUsSession(now)`. There are no picks, positions or history, because
P2–P4 have not run. Optionally confirm on the deployed site. This is read-only and needs no push.

### Step 15: Fill the runbook evidence
**File:** `docs/runbooks/data-pipeline.md`, section "First run"
**Change:** replace every `⟨…⟩` slot with the recorded output from Steps 5 and 8–14, tick each
acceptance box `[x]` with its evidence, and set the heading date to the date Step 13 completed.
**Code:**
```bash
cd /home/miftah/.worktrees/seer/engine-data-pipeline
grep -n '⟨' docs/runbooks/data-pipeline.md && echo "UNFILLED SLOTS REMAIN" || echo "runbook complete"
grep -c '^- \[x\]' docs/runbooks/data-pipeline.md   # expect 7
```
An item you could not prove stays `[ ]`, and its reason is written next to it. Never tick
without evidence.

### Step 16: Roadmap P1 progress line
**File:** `docs/ROADMAP.md:15`
**Change:** current line 15, exactly:
```markdown
## P1 — Data pipeline
```
replace it with (date = the Step 13 date; `2026-10-03` shown, adjust if the run crossed midnight WIB):
```markdown
## P1 — Data pipeline · done 2026-10-03 locally on Neon (backfill + nightly, [runbook](runbooks/data-pipeline.md)); Actions schedule awaits secrets + push
```
**Impact:** docs only. Leave the P0 line alone (see Handoffs).

## Verification

**Build:** `node --check web/scripts/seed-demo.mjs` and `docker run --rm -v "$PWD:/repo" -w /repo rhysd/actionlint:latest` (or the Step 5 YAML fallback), both run from the worktree root.
**Tests:** `PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q -rs` and `cd web && npx vitest run`.
**Manual check:** read `docs/runbooks/data-pipeline.md` "First run" and check that it has no `⟨` left. `git status` shows only the files in the Files table: no `.env.local`, logs or venv.
**Exit criteria:**
1. Four workflows exist and are actionlint-clean (or YAML-valid, with the reason recorded).
2. The seed script refuses on Neon with the "Real bars exist" message after the backfill.
3. Neon has migration 002 and no demo rows. `bars` covers every fetchable ever-member since 2015-01-02, with unfetchable ones listed in `backfill_log` and in the runbook. `bars` is under 400 MB.
4. Two nightly runs and one dry run leave identical fingerprints, and the single real `runs` row matches `dates.run_dates(now)`.
5. The runbook's acceptance checklist has all 7 items ticked with evidence, and ROADMAP P1 is marked.
6. Nothing was pushed and no secret was set.

## Handoffs

- **Owner (approval required):** `gh secret set DATABASE_URL_UNPOOLED`, `gh secret set MASSIVE_API_KEY`, `git push origin main` after the merge, then a dispatched dry-run nightly. The exact commands are in the runbook's "Owner steps".
- **P0 roadmap line** (`docs/ROADMAP.md:8`, "CI still open"): the CI workflow now exists but has not run on GitHub. Change that line only after the owner's first green CI run on GitHub. Lint is still open, because the repo has no lint script (eslint/ruff). Adding one is P0 work, not P1.
- **Phase 2 (reconciled):** override rows are `date,index_id,action,ticker,note` (`index_id` `SP500|NDX`, `action` `add|remove`, dated strictly after the snapshot file's last row) and alias rows are `old,new,effective_date,note` (every `old` points at the current ticker; chains are rejected). The runbook's "Membership maintenance" and "Renames going forward" sections use these columns. If `universe check` drift cannot be fixed with override lines, the diff is recorded here for Phase 2.
- **Phase 1 (reconciled):** `config.load_env()` returns None when `.env.local` is absent and never overrides set variables; `db.connect()` reads it lazily too, so the explicit call is harmless. `backfill_log.symbol` is the primary key. The snippets use `with db.connect() as conn:` (psycopg commits on exit), which is fine for these read-only checks and for the rename snippet's explicit `conn.transaction()`; engine commands themselves use `closing()`/`try-finally` as phase 1 prescribes.
- **Phase 3 (reconciled):** `--symbols` is a comma-separated list (dash or dot form accepted, stored as dot form); `--batch-size` and `--end` exist; exit codes are as in "Requires" above.
- **Phase 4 (reconciled):** `nightly` exits 1 after `fail_run`, so a failed fetch turns the workflow red and GitHub emails. `--now` takes ISO 8601 (`2026-10-05T23:00:00Z`; naive means UTC).
- **Later (not P1):** a keep-alive for the 60-day schedule disablement, for example a monthly workflow that commits nothing and calls `gh workflow enable`. That needs `actions: write` and owner consent. Documented as a manual step for now.
- Any engine defect found during the live run goes back to its owning phase. This phase does not patch `engine/` code.

## Rollback

- **Files:** `git revert` this phase's commit. That removes the four workflows, the runbook, the
  seed guard and the roadmap line, plus the overrides lines if any were added. Nothing else in the
  tree depends on them.
- **Neon data:** run the runbook's "Rollback (data)" SQL through Python, then `cd web && npm run
  db:seed-demo`. Once the data is gone the guard no longer blocks, so the demo can be re-seeded
  without reverting the guard. Migration 002 stays; it is additive and harmless to the web.
- **Local:** `docker rm -f seer-pg`; the untracked symlinks, venv and logs can be deleted
  freely.

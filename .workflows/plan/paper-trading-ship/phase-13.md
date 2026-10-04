# Phase 13: Ship: CI lint, workflow, Neon, Vercel, docs

**Plan set:** `PAPER_TRADING_SHIP_PLAN.md`
**Analysis:** `20261004-082027-P4S7_code_analyzer.md`
**Satisfies:** R6 (ship: P0 CI lint, deploy, owner-step runbook; README and `v0.1.0` are "After landing"), R7 (docs: engine readme, ROADMAP, paper runbook)
**Depends on:** Phase 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12
**Difficulty:** NORMAL
**Package:** repo (`.github/workflows`, `engine/pyproject.toml`, `docs/`, `engine/package_readme.md`)

---

## Goal

CI lints on every push: `ruff check` with a bugs-only rule set, and `tsc --noEmit` for the web. The
nightly job runs `paper_check` after `paper`, with failures visible, and then runs the optional
`explain` step. Neon is at migration 003, and a rolled-back `paper` night on real data is recorded.
The web build is proven on Vercel, and every owner step plus the release checklist is written in
`docs/runbooks/paper-trading.md`. `docs/ROADMAP.md` and `engine/package_readme.md` describe what
landed. The phase changes no source behavior.

## Facts measured while planning (2026-10-04, against `844e4d7`)

These facts drive the choices below. The implementer re-checks the ones marked *(re-verify)* at
implementation time.

1. **Ruff.** `ruff 0.16.10` was installed in a scratch venv and run on `engine/` (src + tests,
   125 files):
   - `--select E,W,F`: 4,428 findings (4,409 are E501).
   - `--select B`: 62. `--select I`: 31. `--select UP`: 24.
   - `--select F`: 5, all F401 (unused import):
     - `backtest/registry.py:36`, a closed record that must not be edited;
     - `backtest/report.py:32`, `:41`;
     - `tests/test_backtest_b_walkforward.py:54`;
     - `tests/test_sim_lifecycle.py:24`.
   - `--select E9,F --ignore F401`: **All checks passed**.
   - With the config placed in `engine/pyproject.toml`, `ruff check engine` run from the repo root
     finds that config and passes. The default excludes skip `engine/.venv`: a planted
     `.venv/lib/x.py` was not checked.
2. **tsc.** `npx tsc --noEmit` on a clean `git archive` of `web/` (no `next-env.d.ts`, no
   `.next/`, the same as CI) exits 0. `tsconfig.tsbuildinfo` is written, and it is already
   gitignored (`web/.gitignore:4`).
3. **Vercel** (CLI 62.2.0, credentials read from `/home/miftah/seer/.env.local` without
   `source`):
   - Project `seer16/seer`, Root Directory `web`, Node 22.x, framework Next.js. It has no
     `.vercel/` directory anywhere: the CLI links through the `VERCEL_ORG_ID` and
     `VERCEL_PROJECT_ID` environment variables.
   - `vercel env ls` shows `ALLOWED_EMAIL`, `AUTH_GOOGLE_SECRET`, `AUTH_GOOGLE_ID`,
     `AUTH_SECRET` and `DATABASE_URL`, all on Production and Preview. *(re-verify)*
   - **The project is already Git-connected.** Every push to `main` builds a production
     deployment, and the latest one is `main@844e4d7` (READY). Feature-branch pushes build
     previews. *(re-verify)*
   - **seertrade.site is already connected.** The apex resolves to Vercel (64.29.17.1,
     216.198.79.1), and `www` is a CNAME to `*.vercel-dns-017.com`. `vercel project ls` shows
     the latest production URL `https://seertrade.site`.
     - `GET /` → 307 to `/signin`.
     - `/manifest.webmanifest` → 200.
     - `/api/auth/providers` → 200, `callbackUrl` `https://seertrade.site/api/auth/callback/google`.

     *(re-verify)*
   - `*.vercel.app` deployment URLs are behind Vercel Deployment Protection: they return 302 to
     `vercel.com/sso-api`. The custom domain is public.
   - **Plain `vercel ls` prints the token in clear text** in its pagination hint
     (`To display the next page, run vercel ls --token <TOKEN> --next …`). Never run it. Use
     `vercel ls --format json` piped through a filter, or `vercel inspect`.
4. The production web on `main` (before this set lands) keeps working against a Neon that is
   already at migration 003. Every strategy lookup in it has a fallback
   (`ICONS[st.icon] ?? Sigma`, `CARD_BG[st.id] ?? 'bg-sheet'`, `STRAT[...] ?? STRAT.A`,
   `LINE[...] ?? 'var(--ink-2)'`), and it never reads the new tables. Applying 003 before the
   merge is therefore safe for the live site.
5. `migrate` on `main` ignores `schema_migrations` names it has no file for. A Neon at 003 does
   not break the scheduled `nightly.yml` on `main` before the merge.

### Preview deploy, not `vercel deploy --prod` (reconciled: accepted)

The draft scope said to deploy with `vercel deploy --prod`. That was written while the handover said
"Not deployed. seertrade.site DNS pending", and fact 3 shows that is no longer true:
- production already deploys itself from `main` through the Git integration;
- seertrade.site is already live.

A manual `--prod` deploy from the feature worktree would put unmerged code on the owner's live
domain. The next push to `main` would then revert it: the swarm's `chore(orchestration)` commits
land on `main` while the set is still open. Production would flip between the two builds.

This phase therefore:
- proves the build with a **preview** deploy of the exact worktree tree (`vercel deploy`, no
  `--prod`) and records that URL;
- records `https://seertrade.site` as the production URL;
- leaves the production build of the merged code to the Git integration on merge. The "After
  landing" check verifies it.

`vercel deploy --prod` stays in the runbook only as the fallback if the Git integration is ever
disconnected. The plan index's Decisions row "Vercel" records this choice; it is final.

## Interface Contract

**Deletes:** in `docs/ROADMAP.md`:
- the "CI still open" status;
- the P4 body (three bullets plus "Done when");
- the P5 "awaiting seertrade.site DNS" status;
- the v0.1.0 body.

In `engine/package_readme.md`, the sections "Simulator: P4 nightly" (lines 1423–1443) and
"Strategy: P4 nightly picks" (lines 1445–1462), which are replaced. No code symbol is deleted.

**Renames:** none.

**Creates:**
- `docs/runbooks/paper-trading.md`;
- the `[tool.ruff]` and `[tool.ruff.lint]` tables in `engine/pyproject.toml`;
- dev dependency `ruff>=0.16,<0.17`;
- CI steps "Lint engine" (engine job) and "Typecheck web" (web job);
- `nightly.yml` steps "Paper check" (`id: paper_check`) and "Explain", and `timeout-minutes: 45`;
- Neon state: `schema_migrations` row `003_paper.sql`;
- a Vercel preview deployment.

**Signature changes:** none.

**Requires (from earlier phases):**
- Phase 1: `db/migrations/003_paper.sql` exists and follows C1.
- Phase 7:
  - `.github/workflows/nightly.yml` has a step named `Paper` after `Nightly`, and that step runs
    `python -m seer_engine … paper`;
  - `commands/paper.py` supports the global `--dry-run`, plus `-v` and `--now`.
- Phase 8: `commands/paper_check.py` exists and supports `--require-sessions N`. It is
  read-only, and its exit code is non-zero on a mismatch. It must exit 0 when no roster strategy
  has started ("not started"), and it must exit 0 right after the first `paper` night.
- Phase 9: `commands/explain.py` exists. It treats unset **or empty** `LLM_API_KEY`,
  `LLM_BASE_URL` or `LLM_MODEL` as "not configured" and exits 0 (GitHub passes an unset secret
  as an empty string).
- Phases 10–12: the web passes `npx tsc --noEmit` and `npx vitest run`.
- Phases 1–12: their Python passes `ruff check` under `select = ["E9", "F"]`,
  `ignore = ["F401"]`. If it does not, see Step 3's contingency.

**Leaves alone (owned by others):**
- the `Paper` step body in `nightly.yml` (Phase 7);
- every file under `engine/src`, `engine/tests`, `web/` and `db/`;
- `README.md` and the `v0.1.0` release ("After landing");
- `backtest/registry.py` and the other closed records.

## Files

| File | Action | What changes |
|---|---|---|
| `engine/pyproject.toml:21-22,32` | modify | `ruff` added to the `dev` extra; `[tool.ruff]` and `[tool.ruff.lint]` appended |
| `.github/workflows/engine-ci.yml:55-56,84-88` | modify | "Lint engine" step after "Install engine"; "Typecheck web" step before "Test web" |
| `.github/workflows/nightly.yml` (after phase 7's `Paper` step, at the end of `steps`; `jobs.nightly.timeout-minutes`) | modify | "Paper check" and "Explain" steps; `timeout-minutes` 30 → 45 |
| `docs/runbooks/paper-trading.md` | create | the operations runbook, owner steps, release checklist, ship-check record |
| `docs/runbooks/data-pipeline.md:9-20,38,69` | modify | `nightly` now records dividends and fetches held paper symbols; pointer to the paper runbook |
| `docs/ROADMAP.md:5-6,8,73-77,79-84,92-94` | modify | goal line, P0 closed, P4 paper-only entry, P5 deploy status, v0.1.0 pending the 5-night check |
| `engine/package_readme.md` (anchors per step) | modify | header, overview, layout, the `paper`, `paper_check` and `explain` CLI sections, `paper/*`, `dividends` and `llm` API, P4 additions to existing modules, migration 003, reverse deps, performance, usage (the real nightly flow), gotchas, notes |
| Neon (no file) | operate | `migrate` → 003; `paper_check` (not started); `--dry-run -v paper` (rolled back), measured |
| Vercel (no file) | operate | `vercel env ls` (names only); preview `vercel deploy` of the worktree tree; `vercel inspect` |

## Substitution tokens

The docs below contain values that only exist once Steps 6–8 have run. Each token is replaced
with the value recorded by the named step, and **no token may remain in a committed file**
(Step 14 greps for `{{`).

| Token | Source |
|---|---|
| `{{IMPL_DATE}}` | `TZ=Asia/Jakarta date +%F` on the day this phase runs |
| `{{RUFF_VERSION}}` | `engine/.venv/bin/ruff --version` (Step 3) |
| `{{ENGINE_TESTS}}` | the pytest summary line, e.g. `612 passed in 48.1s` (Step 14) |
| `{{WEB_TESTS}}` | the vitest summary, e.g. `14 files, 131 passed` (Step 14) |
| `{{DB_SIZE_BEFORE}}`, `{{DB_SIZE_AFTER}}` | Step 6a / 6c |
| `{{MIGRATE_LINES}}` | the log lines of Step 6b's dry run, real run and second run |
| `{{ROSTER_ROWS}}` | Step 6c's `strategies` dump (`id, is_champion, is_benchmark, engine, rules_id, paper_start`) |
| `{{CHECK_NOT_STARTED}}` | Step 6d's last output line and exit code |
| `{{PAPER_NOW}}` | the `now` the dry run used (logged by `paper`), and its `data_date` / `session_date` |
| `{{PAPER_DRYRUN_SUMMARY}}` | Step 6e: the per-strategy summary lines and the final line of `paper`'s log, secrets-scrubbed |
| `{{PAPER_SECONDS}}`, `{{PAPER_RSS_MB}}` | Step 6e: `/usr/bin/time -v` "Elapsed (wall clock)" and "Maximum resident set size" ÷ 1024 |
| `{{WINDOW_LOAD}}` | Step 6e: the windowed bars load line (rows and seconds) from `paper -v`'s log |
| `{{CHECK_SECONDS}}` | Step 6d: wall time of `paper_check` |
| `{{VERCEL_ENV_NAMES}}` | Step 8a: the names listed, comma-separated |
| `{{PREVIEW_URL}}`, `{{PREVIEW_STATE}}` | Step 8b / 8c |
| `{{PROD_PROBE}}` | Step 8d: the status codes for `/`, `/signin`, `/manifest.webmanifest`, `/api/auth/providers` on seertrade.site |

## Implementation Steps

### Step 0: Prepare the worktree and read the landed code

**File:** none (environment).
**Change:**

```bash
cd /home/miftah/.worktrees/seer/paper-trading-ship
git log --oneline -15          # phases 1-12 present
docker start seer-pg
engine/.venv/bin/pip install -q -e 'engine[dev]'     # after Step 1 this also installs ruff
S=/tmp/claude-1000/-home-miftah-seer/463a1415-1166-49ad-a66c-3f174b43318a/scratchpad   # or this session's scratchpad
mkdir -p "$S/p13"
```

**Truth pass.** Every doc in this phase was written against contracts C1–C4 and the index, because
the phase 1–12 plans did not exist when this plan was written. Before writing any doc, read these
files as they landed, and correct every name, flag, log line and exit code in Steps 9–13 to match
the code. **The code wins.**
- `.workflows/plan/paper-trading-ship/phase-{1..12}.md` (their Interface Contracts);
- `engine/src/seer_engine/paper/*.py`;
- `commands/paper.py`, `paper_check.py`, `explain.py`, `nightly.py`;
- `runs.py`, `universe.py`, `demo.py`, `dividends.py`, `llm.py`, `massive.py` (`dividends`),
  `splits.py`;
- `sim/book.py` (`apply_book_split`), `backtest/io.py` (`read_bars_frame`);
- `db/migrations/003_paper.sql`.

Then run `python -m seer_engine paper --help`, `paper_check --help` and `explain --help`, and copy
their usage lines into the readme and runbook verbatim.

**Impact:** none.

### Step 1: Ruff configuration and dev dependency

**File:** `engine/pyproject.toml:21-22` (the `dev` extra) and `:32` (append after
`[tool.pytest.ini_options]`).
**Change:** the whole file after the edit:

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "seer-engine"
version = "0.1.0"
description = "Seer data pipeline: point-in-time universe, daily bars, FX, nightly runs."
requires-python = ">=3.11"
dependencies = [
  "psycopg[binary]>=3.2",
  "pandas>=2.2",
  "numpy>=2",
  "pandas_market_calendars>=5.0",
  "yfinance>=1.0",
  "requests>=2.32",
  "python-dotenv>=1.0",
  "scikit-learn>=1.9,<1.10",
]

[project.optional-dependencies]
dev = ["pytest>=8", "ruff>=0.16,<0.17"]

[project.scripts]
seer-engine = "seer_engine.cli:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra"

[tool.ruff]
target-version = "py311"
extend-exclude = [".cache", ".research"]

[tool.ruff.lint]
# P0 CI lint: bugs only. E9 = syntax/IO errors; F = pyflakes (undefined names, redefinitions,
# unused variables, broken format strings, bad comparisons). Style families (E501, I, UP, B) are
# not selected: the tree has 4,400+ long lines, and closed records must not be reformatted.
select = ["E9", "F"]
# F401 (unused import): backtest/registry.py, a closed record, imports MONTHLY_HOLD_TBILL unused.
ignore = ["F401"]
```

If any of phases 1–12 changed `dependencies` (none is expected to; the plan index lists no new
runtime dependency), keep their list and change only the `dev` line and the appended tables.

**Impact:**
- `pip install -e 'engine[dev]'` now installs ruff.
- `nightly.yml` installs `engine` without `[dev]`, so ruff never reaches the nightly job.
- The minor-version pin keeps a ruff release that adds new F rules from turning CI red unasked.

### Step 2: CI runs lint and the type check

**File:** `.github/workflows/engine-ci.yml`. Insert after line 56 (the end of "Install engine") and
before line 84 ("Test web").
**Change:** the whole file after the edit. The job names are unchanged, so any required-check
names keep matching:

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

      - name: Lint engine
        # Rules live in engine/pyproject.toml [tool.ruff.lint]: bugs only (E9, F minus F401).
        run: python -m ruff check engine

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

      - name: Typecheck web
        run: npx tsc --noEmit

      - name: Test web
        run: npx vitest run
```

**Impact:** CI now fails on a pyflakes bug in `engine/` or on a type error in `web/`. That closes
P0's "CI runs lint + tests on push".

### Step 3: Run lint and the type check locally (with the contingency)

**File:** none.
**Change:**

```bash
cd /home/miftah/.worktrees/seer/paper-trading-ship
engine/.venv/bin/ruff --version                      # -> {{RUFF_VERSION}}
engine/.venv/bin/python -m ruff check engine         # must print "All checks passed!"
cd web && npm ci --no-audit --no-fund && npx tsc --noEmit && echo TSC-OK
```

**Contingency.** If ruff reports a finding in code that phases 1–12 added, handle it by code:
- **F841** (local assigned, never used): rename the variable to `_name`. Do not delete the
  assignment, because its right-hand side may have side effects.
- **F811** (redefined, unused): delete the first, dead definition only when it is
  byte-identical in behavior (the same body). Otherwise do not edit it; stop and hand it back.
- **F541** (f-string without placeholders): drop the `f` prefix.
- **F821** (undefined name), **F822**/**F823**, or any **E9**: this is a real defect. Do **not**
  fix it in this phase. Stop, record it under Handoffs as a defect in the owning phase, and
  return the phase as blocked.
- Any other F code: rename or remove only when it is provably behavior-neutral. Otherwise treat it
  as a defect, as above.

List every contingency edit, with its file and line, in the phase commit message.

If `tsc` fails, it is a phase 10–12 defect. Do not fix it here; hand it back as above.
**Impact:** none when the tree is clean, which is the expected case.

### Step 4: `nightly.yml` gets "Paper check" and "Explain"

**File:** `.github/workflows/nightly.yml`. Append two steps after phase 7's `Paper` step, which is
the last step after phase 7.
**Change:** the whole file as it should read after this step. The `Paper` step below is the shape
phase 7 is expected to have written. **If phase 7's `Paper` step differs, keep phase 7's text
byte for byte**, and add only the two new steps after it.

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
    # 45, not 30: nightly makes 3 Massive calls per missing session (bars, splits, dividends) at
    # 12.5 s spacing, then Paper, Paper check and Explain run in the same job.
    timeout-minutes: 45
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

      - name: Paper
        run: |
          flags=(-v)
          if [ "$DRY_RUN" = "true" ]; then flags+=(--dry-run); fi
          python -m seer_engine "${flags[@]}" paper

      # Replay check (D7): the stored paper state must equal a one-shot run_rules / buy_and_hold
      # replay. Read-only. A mismatch turns the run red (GitHub emails); paper state is already
      # committed and the next night still runs. See docs/runbooks/paper-trading.md.
      - name: Paper check
        id: paper_check
        run: |
          flags=(-v)
          if [ "$DRY_RUN" = "true" ]; then flags+=(--dry-run); fi
          python -m seer_engine "${flags[@]}" paper_check

      # Optional LLM explanations (D9). Never fails the night: missing secrets or any LLM error
      # leave the text NULL ("unavailable" in the app). Runs after a red Paper check too, but
      # not after a failed Nightly or Paper.
      - name: Explain
        if: ${{ success() || steps.paper_check.outcome == 'failure' }}
        continue-on-error: true
        env:
          LLM_API_KEY: ${{ secrets.LLM_API_KEY }}
          LLM_BASE_URL: ${{ secrets.LLM_BASE_URL }}
          LLM_MODEL: ${{ secrets.LLM_MODEL }}
        run: |
          flags=(-v)
          if [ "$DRY_RUN" = "true" ]; then flags+=(--dry-run); fi
          python -m seer_engine "${flags[@]}" explain
```

`timeout-minutes` goes from 30 to 45 (reconciled; plan index Decisions "Nightly time budget"): a
full 30-session catch-up is about 19 minutes of Massive rate-limit waits alone (3 calls per missing
session since phase 5), and Paper, Paper check and Explain now share the job. Phase 7 does not
touch the timeout; this step owns it.

**Impact:**
- A failed `paper_check` makes the nightly run red, but `Paper` has already committed. That is
  intended: the check is evidence, not a gate on the state (runbook "Failure states").
- `Explain` cannot make the run red.
- "Check secrets" is unchanged: the `LLM_*` secrets are optional.

### Step 5: Lint the workflows

**File:** none.
**Change:**

```bash
cd /home/miftah/.worktrees/seer/paper-trading-ship
docker run --rm -v "$PWD":/repo -w /repo rhysd/actionlint:latest -color   # must exit 0, no findings
```

**Impact:** none. Fix only findings in the lines that Steps 2 and 4 added. A finding in another
line is recorded under Handoffs.

### Step 6: Neon: migration 003, the not-started check, and a rolled-back night on real data

**File:** none. The outputs are pasted into the runbook's "Ship check" section in Step 9.
**Change:** run everything from the worktree, so that the worktree's code and `db/migrations`
are what run.
- Never `source` `.env.local`.
- Every command reads it through `SEER_ENV_FILE`.
- Save every log in `$S/p13/` (the scratchpad), not in the repo.

```bash
cd /home/miftah/.worktrees/seer/paper-trading-ship
export SEER_ENV_FILE=/home/miftah/seer/.env.local
PY=engine/.venv/bin/python

# 6a. Storage before (handover §7: measure before adding tables)
$PY - <<'PY' | tee "$S/p13/size-before.txt"
from seer_engine import config, db
config.load_env()
with db.connect() as conn:
    print(conn.execute("SELECT pg_size_pretty(pg_database_size(current_database())), "
                       "pg_size_pretty(pg_total_relation_size('bars'))").fetchone())
    print(conn.execute("SELECT string_agg(name, ', ' ORDER BY name) FROM schema_migrations").fetchone())
    print(conn.execute("SELECT id, status, data_date, session_date FROM runs WHERE NOT is_demo "
                       "ORDER BY id DESC LIMIT 3").fetchall())
PY

# 6b. Migrate: dry run, real, idempotent re-run
$PY -m seer_engine --dry-run migrate 2>&1 | tee "$S/p13/migrate-dry.log"     # "would apply 003_paper.sql"
$PY -m seer_engine migrate 2>&1 | tee "$S/p13/migrate.log"                   # "apply 003_paper.sql"
$PY -m seer_engine migrate 2>&1 | tee "$S/p13/migrate-2.log"                 # "nothing to apply"

# 6c. After: size, tables, roster rows
$PY - <<'PY' | tee "$S/p13/size-after.txt"
from seer_engine import config, db
config.load_env()
with db.connect() as conn:
    print(conn.execute("SELECT pg_size_pretty(pg_database_size(current_database()))").fetchone())
    print(conn.execute("SELECT string_agg(name, ', ' ORDER BY name) FROM schema_migrations").fetchone())
    print(conn.execute("SELECT string_agg(table_name, ', ' ORDER BY table_name) FROM information_schema.tables "
                       "WHERE table_schema = current_schema() AND table_name IN "
                       "('paper_state','book_positions','book_targets','book_fills','book_trades','dividends')").fetchone())
    for r in conn.execute("SELECT id, is_champion, is_benchmark, engine, rules_id, paper_start "
                          "FROM strategies ORDER BY sort"):
        print(r)
PY

# 6d. Replay check before any paper session: must report "not started" cleanly
/usr/bin/time -f '%e s wall' $PY -m seer_engine -v paper_check 2>&1 | tee "$S/p13/check-not-started.log"; echo "exit=${PIPESTATUS[0]}"

# 6e. One night on real data, rolled back, measured
/usr/bin/time -v $PY -m seer_engine --dry-run -v paper 2>&1 | tee "$S/p13/paper-dry.log"; echo "exit=${PIPESTATUS[0]}"

# 6f. Nothing persisted by the dry run
$PY - <<'PY'
from seer_engine import config, db
config.load_env()
with db.connect() as conn:
    print("paper_state rows:", conn.execute("SELECT count(*) FROM paper_state").fetchone()[0])
    print("paper_start set:", conn.execute("SELECT count(*) FROM strategies WHERE paper_start IS NOT NULL").fetchone()[0])
    print("snapshots:", conn.execute("SELECT count(*) FROM equity_snapshots").fetchone()[0])
    print("orders:", conn.execute("SELECT count(*) FROM orders").fetchone()[0])
    print("book_targets:", conn.execute("SELECT count(*) FROM book_targets").fetchone()[0])
    print("runs.paper_status:", conn.execute("SELECT paper_status FROM runs WHERE NOT is_demo ORDER BY id DESC LIMIT 1").fetchone()[0])
PY
```

Expected results:
- 6b: 003 applied once.
- 6c: four roster rows. `SPY` is the only champion, and it is the benchmark. `B` and `C` are gone,
  because Neon has 0 orders and 0 snapshots. `paper_start` is NULL everywhere. Six new tables.
- 6d: exit 0, one `paper_check: <id>  not-started  no paper start` line per roster strategy, and
  the final line `paper_check: ok (0 of 4 roster strategies started)`.
- 6e: exit 0, and the log shows:
  - the init (paper start = the current `session_date`, day-0 snapshots);
  - A's sized picks;
  - F4/F1 "not a decision session" until the first session of November;
  - SPY's opening buy plan;
  - the rollback.
- 6f: every count is 0 and `paper_status` is NULL. That is the proof that `--dry-run` wrote
  nothing.

If `paper` refuses because the real run for `run_dates(now).session_date` is not `success` (for
example, run on a weekday before that night's nightly):
- take `finished_at` of the latest `success` real run from 6a's output;
- re-run 6e with `paper --now <that instant in ISO 8601 UTC>`;
- record both attempts.

**Before pasting any log into a doc, scrub it:**
`grep -nE 'postgres(ql)?://|neon\.tech|npg_|apiKey=|Authorization' "$S/p13/"*.log`
must print nothing for the lines you paste. Drop or redact any line it hits.

**Impact:**
- Neon gains the 003 tables and roster rows. This is the only persistent write in this phase, and
  it is additive (index invariant 3).
- The production web on `main` keeps rendering (fact 4).
- Rollback is in the runbook.

### Step 7: Engine and web suites (pre-docs gate)

**File:** none.
**Change:**

```bash
cd /home/miftah/.worktrees/seer/paper-trading-ship
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q -rs 2>&1 | tail -3
cd web && npx vitest run 2>&1 | tail -5
```

Both must be green with **0 skipped**. Record the summaries as `{{ENGINE_TESTS}}` and
`{{WEB_TESTS}}` (re-run in Step 14 after the docs, and use those final lines).
**Impact:** none.

### Step 8: Vercel: env names, preview deploy of the worktree, production probe

**File:** none.
**Change:**

```bash
cd /home/miftah/.worktrees/seer/paper-trading-ship
# Credentials into this shell only, through the dotenv parser; nothing is echoed.
eval "$(engine/.venv/bin/python -c 'import shlex; from dotenv import dotenv_values; v = dotenv_values("/home/miftah/seer/.env.local"); print("\n".join(f"export {k}={shlex.quote(v[k])}" for k in ("VERCEL_TOKEN", "VERCEL_ORG_ID", "VERCEL_PROJECT_ID")))')"
redact() { sed "s|${VERCEL_TOKEN}|<redacted>|g"; }
vercel whoami 2>&1 | redact | tail -1

# 8a. Which env vars exist (names and targets only; never `vercel env pull`, never print values)
vercel env ls 2>&1 | redact | awk '/^ [A-Z][A-Z0-9_]+ /{print $1, $(NF-3), $(NF-2)}' | tee "$S/p13/vercel-env.txt"
for n in DATABASE_URL AUTH_SECRET AUTH_GOOGLE_ID AUTH_GOOGLE_SECRET ALLOWED_EMAIL; do
  grep -q "^$n " "$S/p13/vercel-env.txt" && echo "present $n" || echo "MISSING $n  -> owner step (runbook)"
done

# 8b. Preview deploy of exactly the committed worktree tree (Root Directory = web is applied by Vercel;
#     .vercelignore drops docs/, .env*, node_modules, .next; git archive drops engine/.venv and every untracked file)
D=$(mktemp -d "$S/p13/deploy.XXXX")
git archive HEAD | tar -x -C "$D"
(cd "$D" && vercel deploy --yes 2>&1 | redact | tee "$S/p13/vercel-deploy.log")
PREVIEW_URL=$(grep -oE 'https://seer-[a-z0-9]+-seer16\.vercel\.app' "$S/p13/vercel-deploy.log" | tail -1); echo "$PREVIEW_URL"

# 8c. Build state (Deployment Protection blocks curl on *.vercel.app; do not create a bypass secret)
vercel inspect "$PREVIEW_URL" 2>&1 | redact | grep -E 'status|url|target|created' | tee "$S/p13/vercel-inspect.txt"
# On a build error: vercel inspect "$PREVIEW_URL" --logs 2>&1 | redact | tail -60

# 8d. Production (custom domain, public): today's main
for p in / /signin /manifest.webmanifest /api/auth/providers; do
  printf '%-24s %s\n' "$p" "$(curl -sS -o /dev/null -w '%{http_code} %{redirect_url}' "https://seertrade.site$p")"
done | tee "$S/p13/prod-probe.txt"
curl -sS https://seertrade.site/api/auth/providers | engine/.venv/bin/python -c 'import json,sys; print(json.load(sys.stdin)["google"]["callbackUrl"])'
```

**Never run:**
- plain `vercel ls`: it prints the token;
- `vercel env add`, `vercel env rm`, `vercel env pull`;
- `vercel domains add`;
- `vercel curl`: it can create a protection-bypass secret;
- `vercel link`: it writes `.vercel/` into the tree.

Setting env vars, the OAuth redirect URI and the GitHub secrets are owner steps (runbook). DNS is
already live (fact 3); it is not an owner step.

Expected results:
- 8a: all five names present.
- 8b/8c: `status ● Ready`, target preview.
- 8d: `/` 307 → `/signin`; `/signin` 200; manifest 200; providers 200 with the callback
  `https://seertrade.site/api/auth/callback/google`.

A preview build failure is a phase 10–12 defect: hand it back, do not fix it here. A missing env
var does not block the phase: the runbook names the owner step that remains, which is index exit
criterion "deploy URL recorded or the blocking owner step named".

**Impact:**
- One preview deployment (the Vercel free tier keeps it; prune it later with the
  `prune-vercel-deployments` skill if needed).
- Production is untouched until the merge.

### Step 9: Write `docs/runbooks/paper-trading.md`

**File:** `docs/runbooks/paper-trading.md` (new).
**Change:** the full content is below.
- Replace every `{{TOKEN}}` from the table above.
- Correct anything the Step 0 truth pass contradicts: command usage, log wording, exit codes and
  table names.
- The exit-code table was reconciled against phases 7, 8 and 9 (`paper.execute`,
  `replay.exit_code`/`failures`, `explain` design note 9) and `cli.main` (`ConfigError` → 2).
  Re-check it against the landed commands and their tests.

~~~~markdown
# Runbook — Seer paper trading (P4, paper-only)

Spec: [handover 2026-10-04](../handover/2026-10-04-paper-trading-ship.md) ·
Plan: `PAPER_TRADING_SHIP_PLAN.md` · Roadmap: [P4](../ROADMAP.md) ·
Bars, splits and FX: [data-pipeline.md](data-pipeline.md)

**Paper only.** The owner chose ROADMAP option (b) on 2026-10-04:
- SPY buy-and-hold is the champion;
- Seer recommends no real buys;
- four frozen portfolios trade on paper every night, and the app shows them month by month next
  to SPY.

Design §1 is unchanged: no strategy has passed a backtest gate, so nothing here leads to real
money, whatever the paper results show. One month of results is mostly luck. The monthly table is
for watching, not for deciding.

## The roster

Fixed on 2026-10-04, before any paper result (D1). Every entry starts from 20,000,000 IDR,
converted at the latest `fx_rates` rate on or before the first paper night's `data_date`; the rate
is stored in `paper_state.usd_idr`. Every entry starts on the same first paper session
(`strategies.paper_start`).

| Id | What it is | Engine | Rules | Backtest gate |
|---|---|---|---|---|
| `SPY` | Buy and hold SPY, dividends reinvested at the ex-date close (`benchmark.buy_and_hold` rules) | benchmark | — | champion and yardstick; not a strategy |
| `A` | Strategy A, `STRATEGY_A_PARAMS` (frozen in P3); 5-day brackets, 4 slots | bracket | `design-v0` | failed (P3, and the P3b rework) |
| `F4-MOM12-N20-TREND` | Top 20 S&P 500 ∪ NDX members by 12-1 momentum, SPY 200-day filter, monthly | book | `monthly-hold` | not passed: P7a dev window only, max DD 22.2% > 15% |
| `F1-SPY-SMA200-M` | Hold SPY while it closes above its 200-day average, checked monthly; else cash | book | `monthly-hold` | not passed: P7a dev window only, max DD 18.7% > 15%, 11 trades |

Monthly entries decide only on the first session of a month. A paper start in early October means
F4 and F1 hold cash until the open of Monday 2026-11-02, and their October shows 0%. That is the
same semantics the backtest runner (`run_book`) uses, so it is not a bug.

### Frozen means frozen: a change is a new id

`strategies.params` holds each entry's frozen spec:
- the engine;
- the strategy or allocator object;
- the registry id or `STRATEGY_A_PARAMS`;
- the rules id;
- the params;
- a sha256 `digest` of the canonical spec text;
- the `backtest_gate` note the app shows.

`paper` fails the night when a started strategy's stored digest differs from the code's
(`paper/roster.py`): `store.SpecMismatch`, everything rolled back, `runs.paper_status = failed`,
exit 1. A `paper_start` with no `paper_state` row is refused the same way until the clock is reset
(see Rollback).

To change anything about a strategy (a parameter, the rules, the universe), add a **new roster
entry with a new id**. Its paper clock starts on its own first night. Never edit an entry that has
a `paper_start`, and never reset a clock by deleting rows. Concretely:
1. Add the entry to `paper/roster.py` with a new id, and pin its digest in
   `tests/test_paper_roster.py`.
2. Add a migration `00N_*.sql` that inserts its display row (`id, name, sub, icon, sort, engine,
   rules_id`, `is_champion = false`), in the style of `003_paper.sql`.
3. Commit, push, merge. The next nightly writes its spec and `paper_start`.

New research ideas belong in a new handover (registry append under P7a's D6). Paper results are
never a reason to change a running entry.

## The night

```
GitHub Actions nightly.yml   cron 23:00 UTC Mon-Fri (06:00 WIB), retry 01:00 UTC; group seer-db-writer
│
├─ Check secrets             DATABASE_URL_UNPOOLED, MASSIVE_API_KEY (LLM_* are optional)
├─ Migrate                   db/migrations/*.sql not yet applied
├─ Nightly                   one transaction: missing sessions' bars (universe ∪ SPY ∪ symbols held or
│                            pending in paper state), splits (split_adjustments; history rewritten
│                            backwards, dividends too), cash dividends (Massive CD + SC → dividends),
│                            USD/IDR; runs.status = success.   A failure → no bars, no paper.
├─ Paper                     only if runs.status = success for run_dates(now).session_date.
│                            One transaction for all four strategies + runs.paper_status:
│                              for every session after paper_state.last_session through data_date:
│                                splits applied on that session (state rescaled once, in its own units)
│                                → settle (A: sim.step; F4/F1: sim.step_book; SPY: buy_and_hold rules)
│                                → dividends on the ex-date (F4, F1, SPY) → force-close symbols whose
│                                bars ended → equity snapshot
│                              then decide session_date (A: picks → size_picks → pending orders;
│                              F4/F1: targets on a month's first session → book_targets; SPY: hold)
├─ Paper check               read-only replay: run_rules / buy_and_hold over [paper_start, last
│                            session] on Neon's bars must equal what Paper stored. Red on mismatch.
└─ Explain                   optional LLM text for new paper entries; never fails the night
```

The web (Vercel) only reads. Today shows the SPY-champion "no buys" state. Positions and History
show every research strategy's paper orders and positions, labelled **paper**. The Leaderboard has
the metrics, the honest go-live checklist ("Backtest gate passed: no" for every entry) and the
**Month by month** sheet.

Timing follows the NYSE calendar (`dates.run_dates`):
- `data_date` is the last session whose close is at least an hour old;
- `session_date` is the next session, the one tonight's decisions are for;
- decisions for session S read only data dated ≤ `prev_session(S)` and members on that date (no
  look-ahead).

**First night.** The first scheduled run after the code is on `main` writes:
- each strategy's spec and `paper_start = session_date`;
- `paper_state`;
- a day-0 snapshot at `data_date`;
- the first decisions.

Nothing before `paper_start` is paper evidence (D11).

## Commands

Run from the repo root or a worktree. Locally, point `SEER_ENV_FILE` at the main checkout's
`.env.local`. **Never `source` it** (`DATABASE_URL` has an unquoted `&`).

| Command | What it does | Writes |
|---|---|---|
| `SEER_ENV_FILE=/home/miftah/seer/.env.local engine/.venv/bin/python -m seer_engine -v paper` | tonight's paper step for `run_dates(now)`; a no-op if that session's paper step already succeeded | `strategies.params/paper_start` (first night), `paper_state`, `orders`, `book_positions`, `book_targets`, `book_fills`, `book_trades`, `equity_snapshots`, `runs.paper_*` |
| `… -m seer_engine --dry-run -v paper` | the same, then rolls back (nothing persists) | nothing |
| `… -m seer_engine paper --now 2026-10-06T23:30:00Z` | the paper step as of a given UTC instant (format: `paper --help`) | as `paper` |
| `… -m seer_engine -v paper_check` | the replay check over every started strategy | nothing |
| `… -m seer_engine paper_check --require-sessions 5` | the same, and also requires ≥ 5 stepped sessions per strategy (the release check) | nothing |
| `… -m seer_engine -v explain` | LLM explanations for new paper entries that have none yet | `orders.explanation`, `book_targets.explanation` |

Global flags go before the command: `--dry-run` (do everything, roll back) and `-v` (debug logs).

### Exit codes

| Command | 0 | 1 | 2 |
|---|---|---|---|
| `paper` | night stepped and decided (`runs.paper_status = success`), or already done for this session (no-op) | no successful bars run for the session (design §8: no paper step, nothing written); or the night failed: everything rolled back, `runs.paper_status = failed`, `paper_error` set (a changed spec digest fails here as `SpecMismatch`) | missing setting (`DATABASE_URL_UNPOOLED`) |
| `paper_check` | every started strategy equals its replay (strategies touched by a split are reported `split-affected`, not failed), or nothing has started yet (`not-started`) | a mismatch: the first differing snapshot, trade or position is logged; or `--require-sessions N` is given and a strategy stepped fewer than N sessions (`not-started` counts as 0) | missing setting (`DATABASE_URL_UNPOOLED`) |
| `explain` | always, including when any `LLM_*` is unset or empty (logged "explanations unavailable", no database connection) or an entry's LLM call fails (text stays NULL) | only a database error (connection or SQL), which `cli.main` turns into 1; the workflow step is `continue-on-error` | `LLM_*` set but `DATABASE_URL_UNPOOLED` missing |

## Failure states (design §8) and what the app shows

| What happened | Engine result | Workflow | App | Fix |
|---|---|---|---|---|
| Bars run failed (Massive or Frankfurter down, coverage < 90%) | `runs.status = failed`; `paper` refuses and writes nothing | red at "Nightly"; Paper, Paper check and Explain are skipped | stale-data screen ("do not trade") | nothing: the 01:00 retry, or `gh workflow run nightly.yml` |
| Paper failed (a bug, a DB error, Neon full) | whole paper transaction rolled back; `runs.paper_status = failed`, `paper_error` | red at "Paper" | paper warning on Positions; data stays at the last good night | read `paper_error` (Health check), fix, then `gh workflow run nightly.yml` (bars are a no-op, paper catches up every missed session) |
| Paper check mismatch | paper state already committed | red at "Paper check"; Explain still runs | no change | run `paper_check -v` locally; the log names the first difference. A mismatch is a same-path bug: open a card, do not edit rows by hand |
| A split on a held or pending symbol | state rescaled once (`apply_split` / `apply_book_split`); `paper_check` reports that strategy `split-affected` from then on | green | positions in post-split shares and prices | none: whole-share rounding across a split makes exact replay equality impossible (see Splits) |
| Explain failed or `LLM_*` not set | text stays NULL | green (`continue-on-error`) | "explanation unavailable" | Owner step 1 |
| Holiday / weekend | the run finds the session already succeeded: bars no-op, paper no-op | green | unchanged | none |
| Data stale (no successful run for the next session) | — | — | stale-data screen first on Today | as for a failed bars run |
| Spec digest changed in code | `paper` fails the night with `SpecMismatch`: rolled back, `runs.paper_status = failed` | red at "Paper" | paper warning on Positions; data stays at the last good night | revert the change; a changed strategy needs a new id (see The roster) |
| Held symbol has no bar on a session (halted, delisted) | force-closed at its last mark that night, the runners' rule | green | trade with exit reason `forced` | none. If the symbol resumes trading, the replay check will flag it; record it in the ROADMAP |
| Schedules disabled after 60 days without a commit | nothing runs | — | stale | `gh workflow enable nightly.yml --repo miftahulmahfuzh/seer` |

## Splits and dividends

- **Units.** Paper state always stays in the units it was sized in:
  - marks are stored (`orders.mark`, `book_positions.mark`) and never rebuilt from `bars`;
  - `nightly` rewrites `bars` history backwards on a split, so a mark rebuilt from bars would
    already be adjusted and would be rescaled twice.
- **When a split touches state.** Only when `split_adjustments.applied = true` for (symbol,
  session), that is, when the stored history really moved. Then, before that session is settled:
  - bracket orders go through `sim.apply_split`: shares × factor (floored), prices ÷ factor, cash
    in lieu;
  - book positions and pending `book_targets` go through `sim.apply_book_split`: whole shares
    floored with cash in lieu, credited to cash and the position's `income_usd`; stop, take, mark
    and entry price ÷ the exact factor. A position that floors to zero closes as `forced` at the
    old mark.
- **Dividends.**
  - `nightly` stores Massive's cash dividends (types CD + SC, summed per symbol and ex-date) in
    `dividends` for every session it fetches. A split rewrites earlier dividend amounts with the
    bars.
  - On the ex-date, `F4` and `F1` (rules `dividends = true`) are credited for symbols they held
    the night before, and SPY is credited and reinvests at that close (whole shares).
  - `A` gets no dividends, exactly as in its backtest (`DESIGN_V0`).
- **Replay across a split.** A replay over today's adjusted bars sizes positions after the split,
  and the live state was sized before it. Whole-share rounding then differs, so `paper_check`
  reports such a strategy `split-affected` instead of failing it.

## Replay check (`paper_check`)

For every strategy with a `paper_start`, `paper_check`:
- loads Neon's bars from about 550 calendar days before `paper_start`;
- re-runs `run_rules` for A, F4 and F1, or `buy_and_hold` for SPY, over
  `[paper_start, paper_state.last_session]` with the stored `paper_state.usd_idr`;
- compares every equity snapshot (day 0 included), every closed trade and every open order or
  position with what `paper` stored.

It is the proof that backtest and live share one code path (design §9, D7). It runs every night
after Paper, and before the release with `--require-sessions 5`.

## Health checks

```bash
cd /home/miftah/seer
engine/.venv/bin/python - <<'PY'
from seer_engine import config, db
config.load_env()
with db.connect() as conn:
    for r in conn.execute("SELECT id, status, paper_status, data_date, session_date, paper_finished_at, "
                          "left(paper_error, 160) FROM runs WHERE NOT is_demo ORDER BY id DESC LIMIT 10"):
        print(r)
    for r in conn.execute("SELECT s.id, s.paper_start, p.last_session, p.pending_session, p.cash_usd, p.equity_usd "
                          "FROM strategies s LEFT JOIN paper_state p ON p.strategy_id = s.id ORDER BY s.sort"):
        print(r)
    for r in conn.execute("SELECT strategy_id, count(*) - 1 AS sessions, min(date), max(date) "
                          "FROM equity_snapshots GROUP BY 1 ORDER BY 1"):
        print(r)
PY
```

Storage: the paper tables add kilobytes per month. Watch the database size with the query in
[data-pipeline.md](data-pipeline.md#storage-budget). Neon free is 0.5 GB.

## Owner steps

These need the owner, so the pipeline session does not do them. Each one is independent. Run them
from the main checkout `/home/miftah/seer` after the feature branch is merged into `main`. No
command echoes a secret, and nothing is `source`d.

### 1. LLM secrets for the Explain step (optional)

Without them the night is still correct, and the app shows "explanation unavailable".

```bash
cd /home/miftah/seer
for n in LLM_API_KEY LLM_BASE_URL LLM_MODEL; do
  engine/.venv/bin/python -c "from dotenv import dotenv_values; print(dotenv_values('.env.local')['$n'], end='')" \
    | gh secret set "$n" --repo miftahulmahfuzh/seer
done
gh secret list --repo miftahulmahfuzh/seer     # LLM_API_KEY, LLM_BASE_URL, LLM_MODEL listed (values never shown)
```

### 2. Google sign-in on seertrade.site

The app's Google callback is `https://seertrade.site/api/auth/callback/google`.
1. Open <https://console.cloud.google.com/apis/credentials> while signed in as the account that
   owns the OAuth client.
2. Under **OAuth 2.0 Client IDs**, open the client whose Client ID equals `AUTH_GOOGLE_ID` in
   `.env.local`.
3. **Authorized JavaScript origins** → **Add URI** → `https://seertrade.site`.
4. **Authorized redirect URIs** → **Add URI** → `https://seertrade.site/api/auth/callback/google`.
5. **Save**. Google says changes can take a few minutes.
6. On the iPhone, open <https://seertrade.site>, then **Continue with Google** with
   `ALLOWED_EMAIL`. Today must open. Any other Google account must land back on Sign-in, denied.

### 3. Vercel environment variables

Verified present on {{IMPL_DATE}} for Production and Preview: {{VERCEL_ENV_NAMES}}. Only if one is
missing, or after rotating a value, re-add it from `.env.local` without echoing it, then redeploy:

```bash
cd /home/miftah/seer
eval "$(engine/.venv/bin/python -c 'import shlex; from dotenv import dotenv_values; v = dotenv_values(".env.local"); print("\n".join(f"export {k}={shlex.quote(v[k])}" for k in ("VERCEL_TOKEN", "VERCEL_ORG_ID", "VERCEL_PROJECT_ID")))')"
N=DATABASE_URL     # or AUTH_SECRET, AUTH_GOOGLE_ID, AUTH_GOOGLE_SECRET, ALLOWED_EMAIL
vercel env rm "$N" production --yes 2>/dev/null
engine/.venv/bin/python -c "from dotenv import dotenv_values; print(dotenv_values('.env.local')['$N'], end='')" | vercel env add "$N" production
git commit --allow-empty -m "chore: redeploy for env change" && git push origin main   # the Git integration redeploys
```

The web needs the **pooled** `DATABASE_URL` (Neon serverless driver). The engine uses
`DATABASE_URL_UNPOOLED`. Never run plain `vercel ls`: its pagination hint prints the token. Use
`vercel ls --format json`.

### 4. Domain and deploys: nothing to do

seertrade.site is already live and connected to the Vercel project (verified {{IMPL_DATE}}:
{{PROD_PROBE}}). Production deploys itself from every push to `main` through the Vercel Git
integration, so merging this set ships the web. No DNS step remains for the owner.

Only if the Git integration is ever disconnected, deploy production by hand from a clean tree of
`main`:

```bash
D=$(mktemp -d) && git -C /home/miftah/seer archive origin/main | tar -x -C "$D" && (cd "$D" && vercel deploy --prod --yes)
```

### 5. Install on the iPhone (PWA)

In Safari, open <https://seertrade.site> → **Share** → **Add to Home Screen** → **Add**. The Seer
icon opens full screen.

## Release checklist (v0.1.0)

Do these in order, only after the paper clock has run. Owner rule: the README is written at
release, right before the GitHub release.

1. **≥ 5 consecutive paper sessions** ran unattended.
   - `gh run list --workflow nightly.yml --repo miftahulmahfuzh/seer --limit 10`: the last five
     scheduled runs are green through "Paper" and "Paper check".
   - The Health check shows `sessions ≥ 5` for all four strategies, and `paper_status = success`
     on each of those runs.
2. **Replay check on Neon:**
   `SEER_ENV_FILE=/home/miftah/seer/.env.local engine/.venv/bin/python -m seer_engine -v paper_check --require-sessions 5`
   must exit 0 (`split-affected` is allowed and must be named in the release notes).
3. **App check** on the XS Max and on desktop, light and dark:
   - Today shows the SPY-champion "no buys" state;
   - Positions and History show A's paper orders labelled paper;
   - the Leaderboard's Month by month shows October as a partial month for all four, with the
     SPY column.
4. **README.md**: write the full README (what Seer is, paper-only, the roster, how to run, links
   to the runbooks). `/update-readme` does not apply; this is the repo README.
5. **ROADMAP**: mark P4 "done <date>: 5 consecutive sessions, replay check passed" and v0.1.0
   "released <date>".
6. **Release:** commit and push, wait for CI to go green, then
   `gh release create v0.1.0 --repo miftahulmahfuzh/seer --target main --title "Seer v0.1.0: paper-only" --notes-file <notes.md>`.
   The notes say:
   - paper only;
   - design §1 unchanged;
   - no strategy has passed a backtest gate;
   - the paper start date;
   - the 5-night replay result;
   - the live URL.

The 3-month forward clock of design §1 counts from `paper_start`. It unlocks nothing by itself:
real money also needs a passed backtest gate, and none has passed.

## Rollback

- **Stop paper trading, keep bars:** delete the "Paper", "Paper check" and "Explain" steps from
  `nightly.yml`, then commit and push. Paper state stays where it was.
- **Reset paper state** (this also resets the clock; the next nightly starts over with a new
  `paper_start`), in one transaction through Python:
  ```sql
  TRUNCATE paper_state, book_positions, book_targets, book_fills, book_trades;
  DELETE FROM orders WHERE strategy_id IN ('SPY', 'A', 'F4-MOM12-N20-TREND', 'F1-SPY-SMA200-M');
  DELETE FROM equity_snapshots WHERE strategy_id IN ('SPY', 'A', 'F4-MOM12-N20-TREND', 'F1-SPY-SMA200-M');
  UPDATE strategies SET paper_start = NULL, params = '{}'::jsonb;
  UPDATE runs SET paper_status = NULL, paper_error = NULL, paper_finished_at = NULL;
  ```
  The repo is public and losses are shown on purpose: never reset to hide a result.
- **Migration 003 is additive.** The web from before this set ignores its tables.
  `UPDATE strategies SET is_champion = (id = 'A')` restores the old champion flag, but A then
  shows research picks as advice, which the paper-only decision forbids. Prefer reverting the
  code to resetting the data.

## Ship check — {{IMPL_DATE}}

Run from the worktree `/home/miftah/.worktrees/seer/paper-trading-ship` (phases 1–12 landed),
against Neon. Nothing below started the paper clock: every paper write was rolled back.

**CI commands, locally:**
- `ruff check engine` ({{RUFF_VERSION}}, rules E9 + F minus F401): All checks passed.
- `npx tsc --noEmit`: clean.
- Engine tests: {{ENGINE_TESTS}}, 0 skipped.
- Web tests: {{WEB_TESTS}}.
- actionlint: clean for all four workflows.

**Neon before:** {{DB_SIZE_BEFORE}}.
**migrate:** {{MIGRATE_LINES}}.
**Neon after:**
- {{DB_SIZE_AFTER}};
- roster rows: {{ROSTER_ROWS}}.

**paper_check before any session:** {{CHECK_NOT_STARTED}} ({{CHECK_SECONDS}}).

**paper, dry run on real data:**
- {{PAPER_NOW}};
- {{PAPER_DRYRUN_SUMMARY}};
- windowed load {{WINDOW_LOAD}};
- whole command {{PAPER_SECONDS}}, peak RSS {{PAPER_RSS_MB}} MB;
- afterwards `paper_state` 0 rows, no `paper_start`, 0 snapshots, 0 orders, 0 targets: nothing
  persisted.

**Vercel:**
- env present (Production, Preview): {{VERCEL_ENV_NAMES}};
- preview of the worktree tree: {{PREVIEW_URL}} ({{PREVIEW_STATE}});
- production <https://seertrade.site> (still `main` before the merge): {{PROD_PROBE}}.

After the merge, the Git integration deploys the merged commit to production. Check that the top
production deployment's `githubCommitSha` is the merge commit:

```bash
vercel ls --format json | python3 -c 'import json,sys; d=[x for x in json.load(sys.stdin)["deployments"] if x.get("target")=="production"][0]; print(d["url"], d.get("state"), (d.get("meta") or {}).get("githubCommitSha"))'
```

**Remaining owner steps:** 1 (LLM secrets, optional), 2 (Google redirect URI check, and
sign-in on the phone) and 5 (Add to Home Screen), plus 3 if 8a listed a missing name. DNS is live:
no step. The paper clock starts with the first
scheduled nightly after the merge.
~~~~

**Impact:** a new doc. No behavior change.

### Step 10: `docs/runbooks/data-pipeline.md`: `nightly` now also writes dividends and held symbols

**File:** `docs/runbooks/data-pipeline.md`, lines 16–17, line 38 and line 69.
**Change:** three exact replacements and one insertion. Confirm the wording against phase 5's
`nightly.py` and `dividends.py` in the Step 0 truth pass.

1. Lines 16–17. Old:
   ```
   `data_date`/`session_date` from the NYSE calendar, fetches the missing sessions from Massive
   grouped-daily (universe ∪ SPY only), applies new splits once (`split_adjustments`), records the
   FX rate, and finishes one `runs` row per session, all in one transaction. A failure marks the
   ```
   New:
   ```
   `data_date`/`session_date` from the NYSE calendar, fetches the missing sessions from Massive
   grouped-daily (universe ∪ SPY, plus any symbol held or pending in paper state), applies new
   splits once (`split_adjustments`), records each session's cash dividends (`dividends`), records the
   FX rate, and finishes one `runs` row per session, all in one transaction. A failure marks the
   ```
2. After line 20, the end of the Architecture paragraph ("…GitHub Actions supplies the schedule;
   Vercel only reads."), insert a blank line and then:
   ```
   Paper trading (P4) runs after `nightly` in the same job: see [paper-trading.md](paper-trading.md).
   ```
3. Line 38. Old:
   `| \`… -m seer_engine nightly\` | the nightly run for "now"; no-op if that session already succeeded | \`bars\`, \`split_adjustments\`, \`fx_rates\`, \`runs\` |`
   New:
   `| \`… -m seer_engine nightly\` | the nightly run for "now"; no-op if that session already succeeded | \`bars\`, \`split_adjustments\`, \`dividends\`, \`fx_rates\`, \`runs\` |`
4. After line 69 ("- Only splits of universe ∪ SPY symbols, or of symbols that already have bars,
   are recorded."), insert:
   ```
   - Stored `dividends` rows with an ex-date before a split's execution date are rewritten with the
     bars (`amount × split_from / split_to`, 6 decimals), so dividends stay in the bars' units.
   ```

**Impact:** docs only.

### Step 11: `docs/ROADMAP.md`

**File:** `docs/ROADMAP.md`, lines 5–6, 8, 73–77, 79–84 and 92–94.
**Change:** five exact replacements.

1. Lines 5–6. Old:
   ```
   v0.1.0 goal: **Strategy A forward paper trading live every night, visible on the phone.**
   Real money is out of scope until the go-live checklist is fully green.
   ```
   New:
   ```
   v0.1.0 goal: **Seer's frozen paper roster (SPY champion, A, F4, F1) trading on paper every night,
   shown month by month next to SPY, on the phone.** Paper only (owner option (b), 2026-10-04): real
   money is out of scope; design §1 is unchanged, and no strategy has passed a backtest gate.
   ```
2. Line 8. Old: `## P0 — Foundations · mostly done 2026-10-03 (CI still open)`
   New: `## P0 — Foundations · done {{IMPL_DATE}} (CI: \`ruff check\` + engine pytest, \`tsc --noEmit\` + web vitest on every push)`
3. Lines 73–77 (the whole P4 section). New:
   ```
   ## P4 — Nightly forward paper trading · paper-only (owner option (b), 2026-10-04); no real-money recommendations; §1 unchanged · code landed {{IMPL_DATE}}; the clock starts with the first scheduled nightly after the merge ([runbook](runbooks/paper-trading.md))
   - Spec: [handover](handover/2026-10-04-paper-trading-ship.md). Plan: `PAPER_TRADING_SHIP_PLAN.md` (13 phases)
   - Roster, frozen before any result (D1, D4): `SPY` (buy and hold, dividends reinvested; the champion), `A` (`STRATEGY_A_PARAMS`, design-v0 brackets), `F4-MOM12-N20-TREND` and `F1-SPY-SMA200-M` (P7a registry, monthly-hold book rules). Each starts from 20,000,000 IDR on the same first paper day; a changed strategy gets a new id and its own clock
   - What landed: migration 003 (`paper_state`, `book_positions`, `book_targets`, `book_fills`, `book_trades`, `dividends`, roster rows with SPY as champion); pure night functions in `engine/src/seer_engine/paper/` that mirror the runner loop bodies (bracket, book, benchmark), plus a book-engine split rule; Massive dividends and held-symbol bars in `nightly`; the `paper` command (one transaction per night, idempotent per session, `runs.paper_status`); the `paper_check` replay check against `run_rules` / `buy_and_hold`; optional `explain` (LLM); nightly steps Paper → Paper check → Explain; the web: SPY-champion Today with no buys, paper labels, book positions and trades, Month by month, an honest six-row go-live checklist
   - Neon at migration 003 since {{IMPL_DATE}}; a rolled-back night on real data succeeded ([runbook ship check](runbooks/paper-trading.md#ship-check--{{IMPL_DATE}}))
   - No look-ahead: decisions for session S read data through `prev_session(S)` only; stale data or a failed bars run means no paper step and the "do not trade" screen
   - **Done when:** 5 consecutive trading days run unattended with correct settlement, proven by `paper_check --require-sessions 5` on Neon and checked in the run logs and the app. Pending: needs 5 live sessions after the merge
   ```
4. Lines 79–84 (the whole P5 section). New:
   ```
   ## P5 — Web app · done 2026-10-03 on demo data; live at [seertrade.site](https://seertrade.site) (Vercel Git integration: every push to `main` deploys production; domain verified {{IMPL_DATE}}); paper views land with P4
   - Implement the Claude Design output: Sign-in, Today, Positions, Leaderboard, History
   - Auth.js, Google only, single `ALLOWED_EMAIL`
   - PWA manifest + apple-touch-icon; Lucide icon-only buttons
   - Deploy to Vercel, connect seertrade.site: done. The paper-trading build was proven as a preview deploy on {{IMPL_DATE}} and reaches production with the merge
   - Paper-only additions (P4 set): Today shows "SPY buy-and-hold is the champion; Seer recommends no buys"; research orders and positions labelled paper; Month by month on the Leaderboard; checklist row "Backtest gate passed"
   - Owner checks left ([runbook](runbooks/paper-trading.md#owner-steps)): the Google OAuth redirect URI for seertrade.site and a sign-in from the XS Max, Add to Home Screen, and the optional `LLM_*` repo secrets
   - **Done when:** usable from the XS Max home screen; picks copyable into Gotrade (for the paper-only ship: the paper views readable on the phone)
   ```
   In the domain clause, write what Step 8d actually observed. If the probe failed, write
   "domain not serving: owner step 4 in the runbook" instead.
5. Lines 92–94 (the whole v0.1.0 section). New:
   ```
   ## v0.1.0 release · pending the 5-night check
   Paper-only (owner option (b), 2026-10-04): P0, P1, P2 and P5 done; P4 code landed and running on paper.
   Release when P4's "Done when" holds: ≥ 5 consecutive paper sessions, `paper_check --require-sessions 5`
   green on Neon. Then the README, then `gh release create v0.1.0`
   ([release checklist](runbooks/paper-trading.md#release-checklist-v010)). P6 may trail into v0.2.0.
   The 3-month forward clock of design §1 starts on the first live paper day, but it unlocks nothing
   by itself: no roster strategy has passed a backtest gate.
   ```

Check each anchor link against GitHub's slug rules:
- `#ship-check--{{IMPL_DATE}}` becomes `#ship-check--2026-10-0X` (the em dash drops out, and the
  two spaces around it become a double hyphen);
- `#release-checklist-v010`;
- `#owner-steps`.

Open the runbook on GitHub after the push and correct any link that does not jump.
**Impact:** docs only.

### Step 12: `engine/package_readme.md`: the paper sections

**File:** `engine/package_readme.md`. Apply the anchors bottom-up, so that earlier line numbers
stay valid while you edit.
**Change:** the edits below, in the order applied. Write all text against the landed code (Step 0).
For every "API list" below, list **each public name** in the module with its exact signature as
written in the code, plus a one-line description taken from its docstring. That is a mechanical
copy, not invention.

**12a. Notes (append after line 1566, the end of the file):**
```

The P4 sections (`paper/*`, the `paper`, `paper_check` and `explain` commands, `dividends`, `llm`,
the book split rule, migration 003, the P4 additions to `massive`, `splits`, `nightly`, `universe`,
`runs`, `demo` and `backtest.io`, and the real nightly flow under Usage) were added on {{IMPL_DATE}}.
P4 runs paper-only by the owner's option (b) of 2026-10-04: no real-money recommendations, design §1
unchanged. Design, invariants and decisions: `PAPER_TRADING_SHIP_PLAN.md` and
`docs/handover/2026-10-04-paper-trading-ship.md`; operations: `docs/runbooks/paper-trading.md`.
```

**12b. Gotchas (insert after line 1540, the last bullet):**
```
- **Paper state stays in the units it was sized in.** Never rebuild a mark or a price of a live paper order or position from `bars`: `nightly` rewrites history backwards on a split, and `apply_split` / `apply_book_split` would then rescale it twice. Marks are stored (`orders.mark`, `book_positions.mark`).
- **A roster entry is frozen.** `paper` fails the night (`store.SpecMismatch`, rolled back, `runs.paper_status = failed`) when a started strategy's stored spec digest differs from `paper/roster.py`'s. Change a strategy by adding a new id (its own `paper_start`), never by editing a started one or deleting its rows.
- `paper` runs only after a successful bars run for the same session, and only in the `seer-db-writer` concurrency group. Never run a real (non-`--dry-run`) `paper` locally against Neon while the scheduled job may run, and never before the code is on `main` (D11: no back-dated paper days).
- `paper_check` reports a strategy `split-affected` (not failed) once an applied split touched a symbol it held or had pending: whole-share rounding before and after a split cannot match a replay over adjusted bars.
- `explain` must never decide anything: it writes text only, and a failure leaves NULL.
```

**12c. Usage: replace lines 1423–1462** (from `### Simulator: P4 nightly` through the line "backtest's picks for that date given the same bars.") with:
```
### Paper: one night (P4)

The night as `commands/paper.py` runs it, after `nightly` has succeeded for `rd.session_date`.
Every arrow below is a call into code the backtests also run.

1. `rd = dates.run_dates(now)`; refuse unless the real `runs` row for `rd.session_date` is `success`.
2. Load the roster (`paper.roster`), every strategy's state (`paper.store`), the windowed market
   (`paper.store.load_market_window(conn, since)` with `since = store.market_window_since(d)`, 550
   calendar days before the earliest session to step), the applied splits and the dividends. Each
   session S is computed on `night_view(market, S, later)`: the market as it stood on S's night,
   with splits executed after S undone.
3. First night only: write each frozen spec and `paper_start = rd.session_date`, the initial cash
   (`initial_cash_usd(20,000,000 IDR, the latest fx_rates rate ≤ rd.data_date)`) and a day-0 snapshot at
   `rd.data_date`.
4. For every session S after `paper_state.last_session` through `rd.data_date`, per strategy:
   - A: `paper.bracket.settle_bracket(pf, S, bars, splits, last_bar_date)`, which is `apply_split` per
     applied split, then `sim.step`, then `close_unpriced`, with the snapshot replaced;
   - F4, F1: `paper.book.settle_book(book, S, bars, targets, idle_added, MONTHLY_HOLD, dividends, splits, last_bar_date)`,
     which is `sim.apply_book_split` per applied split, then `sim.step_book`, then `close_book_unpriced`;
   - SPY: `paper.benchmark.step_benchmark(state, S, bar, dividend, split=<applied SPY split on S or None>)`, the `buy_and_hold` rules.
5. Decide `rd.session_date`:
   - A: `paper.bracket.decide_bracket(pf, STRATEGY_A, STRATEGY_A_PARAMS, history, members, rd.data_date)`
     gives the pending `orders`;
   - F4, F1: `paper.book.decide_book(market, allocator, params, MONTHLY_HOLD, rd.data_date, held)` gives
     `book_targets`, or `None` when it is not a month's first session.
6. Persist through `paper.store`: orders, positions, targets, fills, trades, snapshots and
   `paper_state`. Then `runs.finish_paper` sets `runs.paper_status = success`. All of this is one
   `db.transaction` (`runs.start_paper` marked the run `running` in a short transaction just before
   it), so a failure rolls back everything and `runs.fail_paper` records `paper_status = failed` in
   its own transaction.

Run it:

```
cd <repo or worktree root>
SEER_ENV_FILE=/home/miftah/seer/.env.local engine/.venv/bin/python -m seer_engine --dry-run -v paper   # rolled back
SEER_ENV_FILE=/home/miftah/seer/.env.local engine/.venv/bin/python -m seer_engine -v paper_check
```

The real night runs only in `nightly.yml` (Paper → Paper check → Explain).

### Paper: replay check (P4)

`paper_check` re-runs `backtest.book_runner.run_rules` (A, F4, F1) and `backtest.benchmark.buy_and_hold`
(SPY) over `[paper_start, last_session]` on the same windowed market, with `paper_state.usd_idr`, and
compares them with the stored state through `paper.replay` (pure): every snapshot, closed trade and open
order or position. `--require-sessions N` also demands ≥ N stepped sessions per strategy. That is the
v0.1.0 release check.
```
Correct every function name and argument list in 12c to the landed code. The order of the steps
and the "one transaction" statement are contracts (C3, C4). If the code does them differently,
that is a defect: hand it back.

**12d. Performance (insert before line 1354, "- There is no benchmark coverage for the DB writers."):**
```
- Paper (P4), measured on Neon on {{IMPL_DATE}} from WSL2, Python 3.11, with the real data (bars through
  the latest nightly), as a rolled-back first night (`--dry-run -v paper`):
  - Windowed bars load: {{WINDOW_LOAD}}. The plan's probe: `COPY … WHERE date >= '2025-06-01'`
    219,575 rows in 2.34 s; `>= '2024-10-01'` 326,410 rows in 2.73 s. There is no pickle cache.
  - Whole command: {{PAPER_SECONDS}}, peak RSS {{PAPER_RSS_MB}} MB. That is well inside the nightly job's 45-minute timeout.
  - `paper_check` before any session: {{CHECK_SECONDS}}. Its cost grows with the paper window, one
    `run_rules` per strategy over `[paper_start, last_session]`.
  - Migration 003 changed the database size from {{DB_SIZE_BEFORE}} to {{DB_SIZE_AFTER}}. The paper tables
    grow by kilobytes per month.
```

**12e. Reverse Dependencies (insert after line 1306):**
```
- P4 runs **paper-only** (owner option (b), 2026-10-04): `commands/paper.py` steps the frozen roster (`paper/roster.py`: `SPY`, `A` with `STRATEGY_A_PARAMS`, `F4-MOM12-N20-TREND` and `F1-SPY-SMA200-M` from `backtest/registry.py`, read-only) through the same `sim` and strategy/allocator code the backtests ran. Nothing is a real-money recommendation: SPY is the champion, and `strategies.params.backtest_gate.passed` is false for every entry.
- `web/lib/data.ts` reads `paper_state`, `book_positions`, `book_targets`, `book_trades`, `orders`, `equity_snapshots`, `runs.paper_*` and `strategies.params`/`paper_start` (read-only). The web never imports the engine; the schema in migration 003 is the contract.
- `.github/workflows/nightly.yml` runs `migrate` → `nightly` → `paper` → `paper_check` → `explain`; `.github/workflows/engine-ci.yml` runs `ruff check engine` (rules in `pyproject.toml`) before pytest.
```

**12f. Migration 003 (insert after line 1254, before `## Data Flow`).** The table list must match
`db/migrations/003_paper.sql` as landed:
```
## Migration 003 (`db/migrations/003_paper.sql`, P4)

Additive only: new columns are nullable or defaulted, `orders` keeps every type and constraint.

- `strategies` gains `engine` (`bracket` | `book` | `benchmark`), `rules_id` (`design-v0`, `monthly-hold`, NULL for SPY) and `paper_start` (the first paper session; NULL until `paper` starts it). `params` holds the frozen spec, its digest and `backtest_gate`.
- `orders` gains `mark` (an open order's last close, in the order's own pre-split units).
- `runs` gains `paper_status` (`running` | `success` | `failed`), `paper_error` and `paper_finished_at`.
- `paper_state(strategy_id PK, last_session, cash_usd, equity_usd, initial_cash_usd, usd_idr, pending_session, pending_decision, updated_at)`: one row per paper strategy.
- `book_positions(strategy_id, symbol)` PK: `sim.book.Position` (fractional-capable `shares`, `mark`, entry date and price, `days_held`, episode `cost_usd` / `income_usd`, stop, take, `exit_pending`). The SPY benchmark's holding is a row here too.
- `book_targets(strategy_id, session_date, symbol)` PK, unique rank: a book strategy's ranked decision for one session, kept after execution, with `explanation`.
- `book_fills` (`seq` within a session, side, reason `entry`…`forced`) and `book_trades` (closed holding episodes, `idle` flag, exit reasons `signal`, `time`, `gap`, `tp`, `sl`, `forced`; index on `(strategy_id, exit_date)`).
- `dividends(symbol, ex_date)` PK, `amount` > 0: Massive cash dividends (CD + SC summed), in bars' units; `splits.apply_splits` rewrites them with the bars.
- Data: the four roster display rows (upsert; `SPY` is the only champion and the benchmark), and `B`/`C` deleted only when no `orders` or `equity_snapshots` row references them.
- Applied to Neon on {{IMPL_DATE}} (runbook ship check).
```

**12g. Exported API (insert after the "backtest: dev runner, report and registry (P7a)" section,
before line 1247 `## Migration 002`):**
```
### paper (P4)

`seer_engine.paper` is nightly paper trading. Every module but `store.py` is pure (no psycopg,
requests, yfinance, clock or randomness), `Decimal`-only for money, and covered by the purity tests.
Each night function steps exactly one session the way a runner's loop body does, and its tests prove
that looping it equals the runner (`run_backtest`, `run_book`, `buy_and_hold`) over hundreds of
synthetic sessions.

- **`paper.roster`**: the frozen roster (D1, D4). <API list: the entry type and its fields, the
  four entries, the canonical spec text, `digest`, `backtest_gate`, the lookback helper>.
- **`paper.bracket`**: `settle_bracket(pf, session, bars, splits, last_bar_date) -> BracketNight`
  and `decide_bracket(pf, strategy, params, history, members, data_date) -> SizingResult`. <API list>.
- **`paper.book`**: `settle_book(book, session, bars, targets, idle_added, rules, dividends, splits, last_bar_date) -> BookNight`
  and `decide_book(market, allocator, params, rules, data_date, held) -> (targets | None, idle_added)`.
  `backtest.book_runner._with_idle` is reused by import. <API list>.
- **`paper.benchmark`**: `BenchmarkState`, `start_benchmark(cash0, start)`, and
  `step_benchmark(state, session, bar, dividend, *, split=None) -> (state, Snapshot, fills)`. Whole shares at the
  first session's open; dividends with an ex-date after the start credited on the ex-date and
  reinvested at that close; marked at every close. <API list>.
- **`paper.replay`**: the pure comparison behind `paper_check`: stored vs replayed snapshots, trades
  and positions; `split-affected` detection. <API list>.
- **`paper.store`** (impure): load and save every engine's state, `load_market_window(conn, since)`,
  dividends by ex-date, applied splits on a session, roster rows. <API list>.

### dividends (P4)

<API list of `dividends.py`: parsing Massive's `/v3/reference/dividends` rows (types CD + SC summed per
symbol and ex-date) and the idempotent upsert into `dividends`.>

### llm (P4)

<API list of `llm.py`: the Anthropic-compatible Messages call over `LLM_BASE_URL` / `LLM_API_KEY` /
`LLM_MODEL`, its timeout, and redaction. Missing or empty settings mean "not configured". It never raises
past `explain`.>

### P4 additions to existing modules

- `massive.Client.dividends(d)` (and the `MassiveSource` protocol): one call per fetched session, `/v3/reference/dividends?ex_dividend_date=D` (the free tier served 513 rows for 2026-09-18 in one page).
- `splits.apply_splits` also rewrites `dividends` before the execution date: `round(amount * split_from / split_to, 6)`.
- `commands/nightly.py`: fetches and stores dividends for every missing session in its one transaction, and adds paper-held symbols (`universe.paper_symbols(conn, d)`) to each session's wanted set, so a position keeps its bars after its symbol leaves the index.
- `universe.paper_symbols(conn, d) -> set[str]`: symbols paper state still needs a bar for on session `d`: pending or open `orders`, every `book_positions` row (the SPY benchmark holding included), and `book_targets` decided for `d` or later.
- `runs`: <the paper status helpers, exact signatures> set `paper_status`, `paper_error` (redacted, cut like `error`) and `paper_finished_at` on the real run row.
- `sim.apply_book_split(book, symbol, factor, session, rules, targets=None) -> BookSplit` (`sim/book.py`, exported from `seer_engine.sim`): the book engine's split rule. Shares × factor (floored for whole-share rules); cash in lieu credited to cash and the position's `income_usd`; stop, take, mark and entry price ÷ the exact factor; floor-to-zero closes as `forced` at the old mark; pending targets for the symbol rescaled. Called only for splits recorded with `applied = true`.
- `backtest.io.read_bars_frame(conn, *, since=None)`: `since` limits the `COPY` to `date >= since`. The default is unchanged, so every existing caller and `load_market` are byte-identical.
```
Replace every `<API list …>` marker with the mechanical list from the landed module before the
commit. Step 14's grep fails while any `<API list` remains.

**12h. demo (line 457).** Replace the `DEMO_TABLES` bullet with the tuple exactly as it is in
`demo.py` after phase 1, keeping the sentence "`strategies` is kept on purpose." and adding: "A purge
also resets `strategies.paper_start` and `params` (the demo seed's paper clock), so the first real
`paper` run starts cleanly; `dividends` is never purged."

**12i. runs (insert after line 442, the last runs bullet):**
```
- P4: <paper status helpers, exact signatures from runs.py>. `paper` sets `running` in a short transaction of its own, then `success` inside the night's transaction; a failure rolls the night back and sets `failed` with a redacted `paper_error` in its own transaction.
```
Replace the marker as in 12g.

**12j. CLI (insert before line 359 `## Exported API`):**
```
### `paper` (P4)

```
<usage line copied from `python -m seer_engine paper --help`>
```

The nightly paper step for the frozen roster (`docs/runbooks/paper-trading.md`).

- **Precondition**: the real `runs` row for `run_dates(now).session_date` has `status = success`. Otherwise nothing is written and it exits 1 (design §8: a failed bars run means no paper step).
- **First night**: writes each roster row's frozen spec (`params`) and `paper_start = session_date`, `paper_state` (initial cash 20,000,000 IDR at the latest FX on or before `data_date`), day-0 snapshots at `data_date`, and the first decisions.
- **Every night**: steps every session after `paper_state.last_session` through `data_date` for every strategy, then decides `session_date`. See Usage, "Paper: one night".
- **Idempotent** per (strategy, session): a re-run for a session already done writes nothing.
- **One transaction** for the whole night plus `runs.paper_status`. A failure rolls back everything and records `paper_status = failed`.
- **Frozen spec**: a started strategy whose stored digest differs from `paper/roster.py` fails the night as `store.SpecMismatch` (rolled back, `paper_status = failed`, exit 1).
- **Exit codes**: <copy from the runbook's table after the truth pass>.

### `paper_check` (P4)

```
<usage line copied from `python -m seer_engine paper_check --help`>
```

The read-only replay check (D7). See Usage, "Paper: replay check". "Not started" (no `paper_start`) is a pass. A strategy touched by an applied split is reported `split-affected`, not failed. `--require-sessions N` is the v0.1.0 release check. Exit codes: <copy from the runbook>.

### `explain` (P4)

```
<usage line copied from `python -m seer_engine explain --help`>
```

Optional LLM explanations (D9) for new paper entries without one: `orders.explanation` for A's new pending orders, `book_targets.explanation` for new entries of the latest decision. Missing or empty `LLM_*` settings, or any LLM error, leave the text NULL and exit 0. Paper correctness never depends on it.
```
Replace the three `<usage line …>` markers and the two `<copy …>` markers before the commit.

**12k. Layout:**
- Line 107. After `db/migrations/002_engine.sql  (outside the package, owned by it)`, add the line
  `db/migrations/003_paper.sql   (outside the package; paper state, book tables, dividends, roster rows; P4)`.
- Line 100. After `      backtest_dev.py       \`backtest_dev\` command (P7a)`, add:
  ```
        nightly.py            `nightly` command (P1; P4 adds dividends and held paper symbols)
        paper.py              `paper` command (P4)
        paper_check.py        `paper_check` command (P4)
        explain.py            `explain` command (P4)
  ```
- Before line 61, `    strategies/ …`, insert:
  ```
      paper/                  nightly paper trading (P4); every module but store.py is pure
        __init__.py           docstring only
        roster.py             the frozen roster: four entries, canonical spec text, digest, backtest_gate
        bracket.py            settle_bracket(), decide_bracket(): run_backtest's loop body for one session
        book.py               settle_book(), decide_book(): run_book's loop body for one session
        benchmark.py          BenchmarkState, start_benchmark(), step_benchmark(): buy_and_hold for one session
        replay.py             the pure comparison behind paper_check
        store.py              load/save paper state, windowed market, splits and dividends queries (impure)
  ```
- Line 60. Change it to
  `      book.py               the book engine: Target, Book, Position, Fill, Trade, step_book(), close_book_unpriced() (P7a); apply_book_split(), BookSplit (P4)`.
- After line 52 (`research.py …`), insert:
  ```
      dividends.py            Massive cash dividends (CD + SC) per ex-date, upsert into `dividends` (P4)
      llm.py                  optional Anthropic-compatible Messages call for `explain`; never raises past it (P4)
  ```
- Add one line for any other new file that phases 1–12 created (check with
  `git diff --name-status 844e4d7 -- engine/src`).

**12l. Overview (insert after line 28, the P7a bullet):**
```
- Nightly paper trading (P4, paper-only by the owner's option (b), 2026-10-04): a frozen roster of four paper portfolios (`SPY` the champion and benchmark, `A`, `F4-MOM12-N20-TREND`, `F1-SPY-SMA200-M`) stepped one session at a time by pure night functions (`paper/bracket.py`, `paper/book.py`, `paper/benchmark.py`) that mirror the backtest runners' loop bodies; persisted in migration 003's tables by `paper/store.py`; driven by the `paper` command after `nightly`; proven equal to a one-shot `run_rules` / `buy_and_hold` replay by `paper_check`; optionally explained by an LLM (`explain`). No real-money path exists, and design §1 is unchanged
```

**12m. Header (line 4).** Replace it with:
`**Last Updated**: {{IMPL_DATE}} (P4 paper-only, phase 13 of \`PAPER_TRADING_SHIP_PLAN.md\`: migration 003, the \`paper/\` package, the book split rule, Massive dividends, the \`paper\`, \`paper_check\` and \`explain\` commands, ruff lint in CI)`

**Impact:** docs only. No section about a closed record (P3–P7a) changes.

### Step 13: Final consistency of the docs

**File:** the four docs above.
**Change:** run these checks and fix what they find:

```bash
cd /home/miftah/.worktrees/seer/paper-trading-ship
grep -nE '\{\{|<API list|<usage line|<copy |<paper status' docs/runbooks/paper-trading.md docs/runbooks/data-pipeline.md docs/ROADMAP.md engine/package_readme.md   # must print nothing
grep -nE 'postgres(ql)?://[^ ]*@|npg_|vcp_|sk-[A-Za-z0-9]{10,}' docs/runbooks/paper-trading.md docs/ROADMAP.md engine/package_readme.md   # must print nothing (no secrets)
for c in paper paper_check explain; do engine/.venv/bin/python -m seer_engine $c --help >/dev/null || echo "missing $c"; done
```

Also read the runbook top to bottom once. Every command in it must be one you ran in this phase,
or one whose `--help` you checked. **Impact:** none.

### Step 14: Full verification and commit

**File:** none.
**Change:**

```bash
cd /home/miftah/.worktrees/seer/paper-trading-ship
engine/.venv/bin/python -m ruff check engine
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q -rs 2>&1 | tail -3   # 0 skipped
cd web && npx tsc --noEmit && npx vitest run 2>&1 | tail -5 && cd ..
docker run --rm -v "$PWD":/repo -w /repo rhysd/actionlint:latest -color
git status --short     # only the 7 files of this phase (plus any Step 3 contingency edits, listed in the message)
```

Commit with a message that names R6 and R7, lists any Step 3 contingency edits, and states:
"Neon at 003; dry-run paper on Neon OK; preview deploy {{PREVIEW_URL}}; production follows the
merge via the Git integration". Use the real values. End it with the attribution lines from the
system reminder.

**Impact:** none beyond the above.

## Verification

**Build:**
- `engine/.venv/bin/python -m ruff check engine` → "All checks passed!";
- `cd web && npx tsc --noEmit` → exit 0;
- actionlint → clean.

**Tests:**
- `PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q` (0 skipped);
- `cd web && npx vitest run`.

**Manual check:**
- Neon `schema_migrations` includes `003_paper.sql`, and the roster has four rows with SPY as
  the only champion.
- `paper_check` exited 0 with every strategy `not-started`.
- `--dry-run -v paper` exited 0, and 6f's counts were all 0.
- `vercel inspect <preview>` is Ready.
- seertrade.site answers as in fact 3.
- The runbook, ROADMAP and readme contain no `{{`, no `<API list` marker and no secret.

**Exit criteria:**
- CI's lint and type-check commands pass locally, and the workflows are lint-clean.
- Neon is at migration 003, with a recorded rolled-back paper night on real data and a recorded
  not-started check.
- The preview deploy URL and the production URL are recorded, and any blocking owner step is
  named in the runbook.
- `docs/runbooks/paper-trading.md`, `docs/ROADMAP.md` (P0 closed, the P4 paper-only entry, P5,
  v0.1.0 pending) and `engine/package_readme.md` describe what landed.
- No file under `engine/src`, `engine/tests`, `web/` or `db/` changed, except listed Step 3
  contingency edits.

## Handoffs

- **R6, "After landing" (not a phase):**
  - the first scheduled nightly after the merge starts the paper clock;
  - after ≥ 5 sessions, run `paper_check --require-sessions 5` on Neon;
  - check the app;
  - write the full `README.md` (owner rule: README at release);
  - mark P4 and v0.1.0 done in the ROADMAP;
  - `gh release create v0.1.0`.

  All of it is spelled out in the runbook's release checklist.
- **Production deploy:** it happens on merge through the Vercel Git integration (see "Preview
  deploy, not `vercel deploy --prod`" above; accepted in reconciliation). After the merge, confirm that the top production deployment's
  `githubCommitSha` is the merge commit (command in the runbook's ship check).
- **Owner steps** (runbook):
  1. `LLM_*` repo secrets;
  2. confirm the Google OAuth redirect URI and JavaScript origin for seertrade.site, and sign in
     from the XS Max;
  3. a Vercel env var, only if Step 8a found one missing;
  4. Add to Home Screen.

  DNS is not an owner step: seertrade.site is already live (fact 3), and the runbook says so.
- **Phase 7, 8, 9 contracts this phase relies on:**
  - phase 8: `paper_check` must exit 0 for "not started" and right after the first night;
  - phase 9: `explain` must treat empty `LLM_*` as unset.

  If either does not hold, the nightly workflow goes red on the first live night. That is a
  defect in the owning phase. Step 6d proves the phase 8 contract on Neon.
- **Out of my scope, noticed:**
  - `docs/ROADMAP.md:15`, the P1 heading, still says "Actions schedule awaits repo secrets". The
    secrets were set on 2026-10-03. A one-line ROADMAP fix belongs to whoever next edits P1 (not
    R6/R7).
  - The five F401 unused imports (fact 1) could be cleaned by a later chore. `registry.py` must
    stay as it is.
- **Defects found in Step 3, 8 or 13** (lint F821/E9, a tsc error, a preview build failure, a
  command whose behavior contradicts C3/C4) go back to the owning phase. They are not fixed here.

## Rollback

- **Code and docs:** `git revert <phase-13 commit>`. That restores the CI, the nightly workflow,
  `pyproject.toml` and the docs, and touches no source.
- **Neon:** migration 003 is additive, and the web on `main` before this set ignores it (fact 4).
  To also undo the roster rows, run in one Python transaction:
  `UPDATE strategies SET is_champion = (id = 'A')`. B and C are gone; re-insert them only if the
  pre-set web needs them (it does not: its lookups have fallbacks). Leave the 003 tables in place.
  Dropping them is destructive and needs no rollback, because nothing outside this set reads them.
- **Vercel:** the preview deployment has no effect on production. Delete it with
  `vercel remove <preview-url> --yes` (credentials exported as in Step 8) if wanted.

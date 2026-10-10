# CLAUDE.md

Seer is a one-person quant lab. It searches for a stock-picking rule that beats SPY, tries to
disprove every candidate on paper, and shows the owner an order ticket for Gotrade each morning.
It is built to kill bad strategies, not to make predictions. Read `README.md` for the full tour.
The rules that bind everything are in `docs/plans/2026-10-03-seer-design.md` (§1, the bar for
real money) and `docs/plans/2026-10-04-method-lab-design.md` (the lab).

## Layout

- `engine/`: Python 3.11 package `seer_engine`, the whole pipeline. GitHub Actions cron runs it
  nightly and it writes to Neon Postgres.
  - `commands/`: one module per CLI subcommand, discovered automatically. Add a module and leave
    `cli.py` alone.
  - `sim/` is the fill simulator, trade rules and Gotrade fees (`sim/costs.py`). Backtests and live
    paper trading share this one simulator.
  - `strategies/`, `backtest/`, `paper/` (pure night functions that mirror the runner loops),
    `sean/` (the owner's real-money ledger), `fundamentals/` (SEC EDGAR).
  - `lab/`: pre-registration, N policy, hard gate, DSR. `lab/methods/mNNNN_<slug>.py` holds one
    method per file, each exporting `METHOD = Method(...)`.
- `web/`: Next.js 16 and React 19 with the app router. It is a read-only view over Neon; only Sean
  writes. `/sera` reads the committed `web/data/lab.json`. **This Next.js is newer than your
  training data, so read `node_modules/next/dist/docs/` before writing web code** (see
  `web/AGENTS.md`).
- `db/migrations/NNN_*.sql`: applied in order by either runner (`python -m seer_engine migrate` or
  `npm run db:migrate`).
- `lab/lab.sqlite`: the committed, append-only method lab. Triggers enforce append-only.
- `docs/`: `plans/` (designs, plans, handovers), `backtests/`, `runbooks/`, `design/Seer v2.dc.html`
  (the UI design to match).
- `.workflows/todos.md` and `package_readme.md` files: task tracking and per-package docs.

## Commands

```bash
# engine (each worktree needs its own engine/.venv)
python3.11 -m venv engine/.venv && engine/.venv/bin/pip install -e 'engine[dev]'
engine/.venv/bin/python -m seer_engine [--dry-run] [-v|-vv] <command>   # --dry-run rolls back all writes
engine/.venv/bin/ruff check engine                  # CI lint is bugs only: E9 and F, minus F401
engine/.venv/bin/pytest engine/tests                # runs in parallel (-n auto); -n0 for serial

# DB tests need Postgres. CI fails if they skip.
docker run -d --name seer-pg -e POSTGRES_PASSWORD=pg -p 55432:5432 postgres:16
export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres

# web
cd web && npm ci
npx tsc --noEmit && npm test                         # what CI runs
npm run dev:env                                      # localhost:3111 with .env.local
npm run shoot -- --theme dark --width 390 /positions # headless signed-in screenshots
```

Use the `run-the-web-app` skill to visually check any change to web/.

## The lab: how methods get run

- The method file must be **committed before** `lab run MNNNN`. That commit is the
  pre-registration, and the runner refuses uncommitted or already-run digests.
- Get the next free id with `lab next-id`. After a lab change, `lab stage` writes
  `web/data/lab.json` and git-adds it with `lab.sqlite`. CI checks that the two agree row for row.
- The dev window ends 2015-10-16. The test window is spent once per method (`lab test`) and
  should be treated as a budget. Never peek at it.
- Parallel sessions share state through `SEER_LAB_DB` and `SEER_RESEARCH_STORE`. The research
  store is `engine/.research/` (gitignored; use the `sync-research-store` skill).
- Exit codes: 0 means ok, 2 means the lab's rules refused the request, 1 means an error.
- Commit messages follow the existing style: `lab: M00NN pre-registered — …` and
  `lab: M00NN rejected (plain reason)`.

## Invariants that are easy to break

- Tests must never reach production. An autouse fixture points them at a nonexistent env file and
  an `.invalid` DB host. Keep it that way.
- `web/` mirrors some engine constants (drawdown bar, contribution schedule, fee minimums, resize
  band), and a test asserts they match. The TS and Python ledgers share a fixture. When you change
  one side, change the other.
- Closed records (`backtest/registry.py`, past backtest reports, existing lab rows) are frozen.
  Do not reformat or "fix" them.
- argparse help strings must still format, so escape `%` as `%%`.
- Gotrade bracket orders (with TP and SL) take whole shares only. Plain limit orders can be
  fractional.
- The §1 real-money bar (18 months of paper, beat SPY, PF ≥ 1.3, max DD ≤ 20%, a 10-year backtest)
  changes only through a dated owner revision.

## Conventions

- Modules carry prose docstrings that explain *why* the code is shaped the way it is. Match that
  style.
- UI: every button is icon-only (Lucide) with an `aria-label` and a tooltip. Follow the Seer v2
  design and avoid generic styling.
- Text the owner reads (site summaries, Sera pages) uses plain language: no ids, digests or code.
- Once a change is verified, commit and push to `main`.

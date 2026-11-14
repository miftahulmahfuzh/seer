# CLAUDE.md

Seer is a one-person quant lab. It searches for a stock-picking rule that beats SPY, tries to
disprove every candidate on paper, and shows the owner an order ticket for Gotrade each morning.
It is built to kill bad strategies, not to make predictions. Read `README.md` for the full tour.
The rules that bind everything are in `docs/plans/2026-10-03-seer-design.md` (§1, the bar for
real money) and `docs/plans/2026-10-04-method-lab-design.md` (the lab).

## Claim verification

Never state a number — a count, a method id, a population size, a denominator, a benchmark
comparison — until this session has read it back from the lab DB or the research store, or
recomputed it here. A figure that comes from memory, a handover brief or a half-finished run is
unverified: label it as such, and measure it before it reaches an analysis doc, a journal entry,
a report or another agent.

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
    method per file, each exporting `METHOD = Method(...)`. `lab/signals/sNNNN_<slug>.py` holds
    one stock-picking signal per file, each exporting `SIGNAL = Signal(...)`. `lab/panel.py`
    measures a signal on a stock-by-month panel (stage one), and `lab/signal_book.py` is the one
    fixed book a cleared signal runs as (stage two).
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

To prove a change works (web, engine or lab), use the `verify-seer` skill
(`.claude/skills/verify-seer/scripts/verify.sh`). It runs a throwaway copy against its own local
Postgres, demo data and lab copy, and never reaches Neon, GitHub, Telegram or the test window. Its
feature map is `.claude/skills/verify-seer/features/README.md`: a user-facing change updates its
entry in the same commit.

## The lab: how methods get run

- The method file must be **committed before** `lab run MNNNN`. That commit is the
  pre-registration, and the runner refuses uncommitted or already-run digests.
- **Two stages.** A rule for choosing which stocks to hold is a signal first. Commit its file
  (get the id from `lab next-signal-id`); then `lab panel SNNNN` measures it on the dev store and
  the survivorship store, records the readings append-only and spends no N. `lab panel-map`
  ranks every panel under one false-discovery correction, computed on read. Only a signal that
  clears gets a method, and that method is `signal="SNNNN"` plus `standard_candidates(...)`.
  `lab run` refuses (exit 2) a method with an arm that picks index members unless it names a
  cleared signal or carries `panel_exempt` (`chassis:`, `market:` or `control-study:`). A signal
  file is never edited after its panel; a tweak is a new id.
- Get the next free id with `lab next-id`. After a lab change, `lab stage` writes
  `web/data/lab.json` and git-adds it with `lab.sqlite`. CI checks that the two agree row for row.
- The dev window ends 2015-10-16. The test window is spent once per method (`lab test`) and
  should be treated as a budget. Never peek at it.
- Parallel sessions share state through `SEER_LAB_DB` and `SEER_RESEARCH_STORE`. The research
  store is `engine/.research/` (gitignored; use the `sync-research-store` skill).
- Exit codes: 0 means ok, 2 means the lab's rules refused the request, 1 means an error.
- Commit messages follow the existing style: `lab: M00NN pre-registered — …`,
  `lab: M00NN rejected (plain reason)`, `lab: S00NN pre-registered — …` and, for a sweep,
  `lab: sera <stamp> pre-registers S00aa..S00bb`.

## Experiment protocol

Every method experiment runs in the same order: verify the data store is the one you mean →
pre-register the hypothesis and every arm in a committed method file → run the control arms beside
the treatment (cite a recorded control by trial instead when it is the same book on the current
store; `lab run` itself measures every otherwise-eligible arm against its random twins, so a
hand-written random arm is a control, not the luck test) → survivorship and sanity check → record
the verdict (accept or reject) in the journal → queue a follow-up idea only when the result names
one → report to the coordinator. A stock-picking idea runs a shorter order first, as a signal:
verify the store → commit the signal file → `lab panel` → read the corrected verdict in
`lab panel-map` → journal → stop unless it cleared. Only a cleared signal goes on to the steps
above, as its one fixed book. Pre-registration is not skippable, least of all when the result
looks obvious.

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
- The §1 real-money bar (18 months of paper, beat SPY, PF ≥ 1.3, max DD ≤ 25%, a 10-year backtest)
  changes only through a dated owner revision. The fall was 15% to 2026-10-07 and 20% to
  2026-10-14; design §18 is the revision that set 25%. The lab's *screen* is a separate, looser
  number (`metrics.DEV_MAX_DRAWDOWN`) and collapsing the two back together undoes that split.

## Conventions

- Modules carry prose docstrings that explain *why* the code is shaped the way it is. Match that
  style.
- UI: every button is icon-only (Lucide) with an `aria-label` and a tooltip. Follow the Seer v2
  design and avoid generic styling.
- Text the owner reads (site summaries, Sera pages) uses plain language: no ids, digests or code.
- Smallest change that satisfies the request. Before adding a module, a panel or an
  abstraction layer nobody asked for, state the proposed scope in one line and wait.
- Once a change is verified, commit and push to `main`.

## Concurrency in shared worktrees

Other phases and agents may be working in this same checkout at the same time.

- Commit explicit file paths only. Never `git commit -a`, never a broad pathspec: you will land
  someone else's half-finished work under your message.
- A failure a peer reports is not a failure until you re-run that test file yourself. A concurrent
  `lab run` reddens tests that read like you broke a frozen record.
- Re-verify before reporting a failure as real, and say which run you verified it in.

> [!IMPORTANT]

> when user type in "p" : you must git add your work only, then commit and push in a new subagent. USE haiku model for this task.

> when user type in "c" : you must list leftover tasks in this session, then write a handover file, then run a new tmux analyze session using it. USE opus model for this task.

> when user type in "a" : you must spawn calculate-assets 1-4-2018 tmux on each of the sera methods that have been explored in this session only. to avoid crash because of memory overload, spawn them 2 at a time. subscribe to them so you can reap them when they are done. USE sonnet model for this task.

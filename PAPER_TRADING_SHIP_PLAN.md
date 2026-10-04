# Plan: Paper trading every night, month-by-month view, v0.1.0 ship

**Slug:** paper-trading-ship
**Date:** 2026-10-04
**Analysis:** `20261004-082027-P4S7_code_analyzer.md`
**Worktree:** `/home/miftah/.worktrees/seer/paper-trading-ship`
**Branch:** `feature/paper-trading-ship` (base: `HEAD` = `origin/main` @ `844e4d7`)
**Phases:** 13
**Status:** planned
**Coordinator:** —

---

## Why

The specification is `docs/handover/2026-10-04-paper-trading-ship.md` (committed at `844e4d7`);
every phase reads all of it. The owner's words:

> *"i still don't want to give up developing this app. how about we just keep going with our major
> plan, then we'll ship it. and we will see how it performs this month WITHOUT MY REAL MONEY …
> the app should be able to show us how seer performs month by month on paper"*

This is ROADMAP option (b): SPY buy-and-hold is the honest champion, Seer recommends no real buys,
research strategies paper-trade every night, and the app shows how they do, month by month, next to
SPY. Design §1 stays law: nothing here leads to real money.

## Requirements

| ID | What the user asked for | Phases |
|---|---|---|
| R1 | Engine paper step: pure core + impure command, per roster strategy per new session (state, splits, settle, dividends, force-close, decide, persist, SPY benchmark) | 2, 3, 4, 5, 6, 7 |
| R2 | Migration `003` (D6) + roster `strategies` rows with `paper_start` and frozen spec (D4); demo seed in the new shape | 1, 10 |
| R3 | Replay check (D7) + design §8 failure handling | 7, 8 |
| R4 | Web: Today SPY-champion state, paper labels, book positions/trades, monthly table, leaderboard incl. book strategies, checklist honesty, no 4-slot assumption | 10, 11, 12 |
| R5 | Optional LLM explanations (D9) | 9 |
| R6 | Ship: CI lint (P0), Vercel deploy, owner-step runbook, README + `v0.1.0` at release | 13 (release itself: "After landing") |
| R7 | Docs: engine readme, ROADMAP, paper runbook | 13 |

## Scope

**In scope:** handover §4 items 1–7.
**Out of scope:** handover §4 "Out of scope" (real money, design §1, new strategies or registry
appends, P7b, Strategy C, closed reports, notifications, trade journal). Also: refactoring
`run_backtest`/`run_book`/`buy_and_hold` (closed records; see Decisions).

## Invariants

1. At the end of every phase: `PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q` passes with **0 skipped**, and `cd web && npx vitest run` passes. (The worktree has its own `engine/.venv`; `docker start seer-pg` first.)
2. **Closed records.** Not edited: `backtest/registry.py`, `backtest/runner.py`, `backtest/book_runner.py`, `backtest/benchmark.py`, `docs/backtests/*`, `STRATEGY_A_PARAMS`, `STRATEGY_A2_PARAMS`, `STRATEGY_B_FROZEN`. `backtest/io.py` may gain an optional keyword whose default keeps every existing call byte-identical.
3. **Additive migrations.** `003` only adds columns (nullable or defaulted), tables and indexes, plus the two data statements named in phase 1. No column of `orders` changes type or constraint.
4. **Pure means pure.** `sim/*`, `strategies/*`, `paper/roster.py`, `paper/bracket.py`, `paper/book.py`, `paper/benchmark.py`, `paper/replay.py` import no psycopg, requests, yfinance, clock or randomness, and are covered by a purity test. `paper/store.py` and `commands/*` are the impure edge.
5. **No look-ahead.** Decisions for session S read data dated ≤ `prev_session(S)` and members on `prev_session(S)`.
6. **Same code path.** Trade logic lives only in `sim` and in the strategy/allocator objects. Commands and the web never re-implement fills, sizing, exits or costs.
7. **UI law.** Seer v2 design (`docs/design/Seer v2.dc.html`); every button icon-only (Lucide) with `aria-label` and `data-tip`; mobile 414 pt and desktop; light and dark. Research picks never appear on Today; nothing reads as a real-money recommendation.
8. **File ownership.** `engine/package_readme.md`, `docs/ROADMAP.md`, `docs/runbooks/*`, `README.md`: phase 13 only. `.github/workflows/nightly.yml`: phase 7 (paper step) then phase 13 (check + explain steps, `timeout-minutes` 30 → 45). `.github/workflows/engine-ci.yml`, `engine/pyproject.toml`: phase 13 only. `engine/src/seer_engine/demo.py`: phase 1 only. `web/app/(app)/page.tsx`, `positions/page.tsx`, `leaderboard/page.tsx`: phase 10 (minimal compile fixes) then phases 11/12 (whole-file replacements quoting phase 10's version).
9. Money is `Decimal` quantized as `sim.model.q`; no float enters engine state. No secret is logged, committed or written to `runs`.

## Contracts every phase codes against

### C1 — Migration `db/migrations/003_paper.sql` (phase 1 writes it)

```sql
ALTER TABLE strategies ADD COLUMN IF NOT EXISTS engine text CHECK (engine IN ('bracket', 'book', 'benchmark'));
ALTER TABLE strategies ADD COLUMN IF NOT EXISTS rules_id text;         -- 'design-v0', 'monthly-hold', NULL for SPY
ALTER TABLE strategies ADD COLUMN IF NOT EXISTS paper_start date;      -- first paper session; NULL until `paper` starts it

ALTER TABLE orders ADD COLUMN IF NOT EXISTS mark numeric(12,4);        -- open order's last close, in the order's own (pre-split) units

ALTER TABLE runs ADD COLUMN IF NOT EXISTS paper_status text CHECK (paper_status IN ('running', 'success', 'failed'));
ALTER TABLE runs ADD COLUMN IF NOT EXISTS paper_error text;
ALTER TABLE runs ADD COLUMN IF NOT EXISTS paper_finished_at timestamptz;

-- One row per paper strategy (every engine): the state between nights.
CREATE TABLE IF NOT EXISTS paper_state (
  strategy_id       text PRIMARY KEY REFERENCES strategies(id),
  last_session      date NOT NULL,            -- last session stepped; prev_session(paper_start) right after init
  cash_usd          numeric(14,4) NOT NULL,
  equity_usd        numeric(14,4) NOT NULL,   -- equity at last_session's snapshot
  initial_cash_usd  numeric(14,4) NOT NULL,
  usd_idr           numeric(12,4) NOT NULL,   -- the rate initial cash was converted at
  pending_session   date,                     -- session the stored decision is for (next_session(last_session))
  pending_decision  boolean NOT NULL DEFAULT false, -- book: pending_session is a decision session (book_targets may be empty)
  updated_at        timestamptz NOT NULL DEFAULT now()
);

-- Open book positions (book strategies and the SPY benchmark holding). sim.book.Position fields.
CREATE TABLE IF NOT EXISTS book_positions (
  strategy_id   text NOT NULL REFERENCES strategies(id),
  symbol        text NOT NULL,
  shares        numeric(16,4) NOT NULL CHECK (shares > 0),
  mark          numeric(12,4) NOT NULL,
  entry_date    date NOT NULL,
  entry_price   numeric(12,4) NOT NULL,
  days_held     int NOT NULL CHECK (days_held >= 1),
  cost_usd      numeric(14,4) NOT NULL,
  income_usd    numeric(14,4) NOT NULL,
  stop_price    numeric(12,4),
  take_price    numeric(12,4),
  exit_pending  boolean NOT NULL DEFAULT false,
  PRIMARY KEY (strategy_id, symbol)
);

-- A book strategy's decision for one session, ranked (kept after execution as the decision record).
CREATE TABLE IF NOT EXISTS book_targets (
  strategy_id   text NOT NULL REFERENCES strategies(id),
  session_date  date NOT NULL,
  rank          int NOT NULL CHECK (rank >= 1),
  symbol        text NOT NULL,
  weight        numeric(8,6) NOT NULL CHECK (weight > 0 AND weight <= 1),
  last_price    numeric(12,4) NOT NULL,
  limit_price   numeric(12,4),
  stop_price    numeric(12,4),
  take_price    numeric(12,4),
  explanation   text,
  PRIMARY KEY (strategy_id, session_date, symbol),
  UNIQUE (strategy_id, session_date, rank)
);

CREATE TABLE IF NOT EXISTS book_fills (
  id            bigserial PRIMARY KEY,
  strategy_id   text NOT NULL REFERENCES strategies(id),
  session_date  date NOT NULL,
  seq           int NOT NULL,                 -- order within the session, from 1 (sim order: splits, open, trim, buy, intraday, forced)
  symbol        text NOT NULL,
  side          text NOT NULL CHECK (side IN ('buy', 'sell')),
  shares        numeric(16,4) NOT NULL CHECK (shares > 0),
  price         numeric(12,4) NOT NULL,
  cash_usd      numeric(14,4) NOT NULL,
  cost_usd      numeric(14,4) NOT NULL,
  reason        text NOT NULL CHECK (reason IN ('entry', 'add', 'trim', 'signal', 'time', 'gap', 'tp', 'sl', 'forced')),
  UNIQUE (strategy_id, session_date, seq)
);

CREATE TABLE IF NOT EXISTS book_trades (
  id            bigserial PRIMARY KEY,
  strategy_id   text NOT NULL REFERENCES strategies(id),
  symbol        text NOT NULL,
  entry_date    date NOT NULL,
  exit_date     date NOT NULL,
  entry_price   numeric(12,4) NOT NULL,
  exit_price    numeric(12,4) NOT NULL,
  days_held     int NOT NULL,
  cost_usd      numeric(14,4) NOT NULL,
  income_usd    numeric(14,4) NOT NULL,
  pnl_usd       numeric(14,4) NOT NULL,
  exit_reason   text NOT NULL CHECK (exit_reason IN ('signal', 'time', 'gap', 'tp', 'sl', 'forced')),
  idle          boolean NOT NULL DEFAULT false,
  UNIQUE (strategy_id, symbol, entry_date)
);
CREATE INDEX IF NOT EXISTS book_trades_exit_idx ON book_trades (strategy_id, exit_date);

-- Cash dividends by ex-date (Massive types CD + SC, summed per symbol and ex-date).
-- Same units as bars: splits.apply_splits rewrites earlier rows with the bars.
CREATE TABLE IF NOT EXISTS dividends (
  symbol       text NOT NULL,
  ex_date      date NOT NULL,
  amount       numeric(14,6) NOT NULL CHECK (amount > 0),
  recorded_at  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (symbol, ex_date)
);

-- Roster display rows (the frozen spec and paper_start are written by `paper`, phase 7).
-- SPY is the champion; nothing else is (D2).
INSERT INTO strategies (id, name, sub, icon, is_champion, is_benchmark, sort, engine, rules_id) VALUES
  ('SPY', 'SPY', 'S&P 500, buy and hold', 'landmark', true, true, 1, 'benchmark', NULL),
  ('A', 'A · Quant', 'Mean reversion, 5-day brackets', 'sigma', false, false, 2, 'bracket', 'design-v0'),
  ('F4-MOM12-N20-TREND', 'F4 · Momentum', 'Top 20 by 12-1 momentum, monthly', 'trending-up', false, false, 3, 'book', 'monthly-hold'),
  ('F1-SPY-SMA200-M', 'F1 · Trend', 'SPY above its 200-day average, monthly', 'shield', false, false, 4, 'book', 'monthly-hold')
ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, sub = EXCLUDED.sub, icon = EXCLUDED.icon,
  is_champion = EXCLUDED.is_champion, is_benchmark = EXCLUDED.is_benchmark, sort = EXCLUDED.sort,
  engine = EXCLUDED.engine, rules_id = EXCLUDED.rules_id;
-- B and C are not on the roster; drop their rows only when nothing references them.
DELETE FROM strategies s WHERE s.id IN ('B', 'C')
  AND NOT EXISTS (SELECT 1 FROM orders o WHERE o.strategy_id = s.id)
  AND NOT EXISTS (SELECT 1 FROM equity_snapshots e WHERE e.strategy_id = s.id);
```

Phase 1 may adjust column comments and index choices, but not names, types or semantics; any
change it makes is reconciled across phases before execution.

### C2 — `strategies.params` jsonb (the frozen spec, D4), written by `paper`

```json
{
  "spec": {"engine": "book", "object": "FACTOR", "registry_id": "F4-MOM12-N20-TREND",
           "rules_id": "monthly-hold", "params": {"rank": "momentum", "top": "20", "...": "..."}},
  "digest": "<sha256 hex of the canonical spec text>",
  "backtest_gate": {"passed": false, "note": "P7a dev window only; failed max DD <= 15% (22.2%)"}
}
```
`paper/roster.py` (phase 1) owns the canonical spec text, the digest and the `backtest_gate` note per
entry. The web reads `params->'backtest_gate'` (phase 10). A row whose `paper_start` is set and whose
stored digest differs from the code's is a hard error in `paper` (a changed strategy needs a new id).

### C3 — Pure night functions (phases 3, 4; signatures fixed here, internals the planners')

Every function steps exactly one session the way the runner loop body does, and is proven equal to
the runner over many sessions by that phase's tests.

- `paper/bracket.py` — `settle_bracket(pf, session, bars, splits, last_bar_date) -> BracketNight`
  (`apply_split` for each `(symbol, factor)` executing on `session` → `sim.step` → `close_unpriced`
  for open orders whose `last_bar_date(symbol)` is None or `< session`, snapshot replaced);
  `decide_bracket(pf, strategy, params, history, members, data_date) -> SizingResult`
  (`size_picks(pf, strategy.picks(history cut at data_date, members, data_date, params), next_session(data_date))`).
- `paper/book.py` — `settle_book(book, session, bars, targets, idle_added, rules, dividends, splits, last_bar_date) -> BookNight`
  (`sim.book.apply_book_split` per split (also rescaling `targets`) → `step_book` → `close_book_unpriced`
  for gone positions, snapshot replaced); `decide_book(market, allocator, params, rules, data_date, held) -> (targets | None, idle_added)`
  for `next_session(data_date)` (`None` when it is not a decision session; members on `data_date`;
  held minus the idle symbol; `backtest.book_runner._with_idle` reused by import).
- `paper/benchmark.py` — `BenchmarkState` and `start_benchmark(cash0, start)` / `step_benchmark(state, session, bar, dividend, *, split=None) -> (state, Snapshot, fills)`
  mirroring `buy_and_hold`: whole shares at the first session's open, dividends with ex-date after
  the start credited on the ex-date and reinvested at that close, every session marked at its close.
  **Extended (reconciled):** `split_benchmark(state, factor, session) -> (state, in_lieu)` applies an
  applied SPY split (floor shares, cash in lieu, prices ÷ the exact factor); `step_benchmark(...,
  split=factor)` runs it before the step, and `paper` passes the applied SPY split on S through it.
  The holding is persisted as a `book_positions` row (symbol `SPY`) plus `paper_state`.
- `sim/book.py` (phase 2) — `apply_book_split(book, symbol, factor, session, rules, targets=None) -> BookSplit`.

### C4 — Store and command (phases 6, 7)

- `paper/store.py` (impure, phase 6; the names every caller uses): roster rows `read_strategies`,
  `read_strategy`, `freeze_spec`, `check_digest` (raises `SpecMismatch`); `PaperState`,
  `read_paper_state`, `init_paper_state` (day 0 + snapshot), `write_pending`; bracket `load_portfolio`,
  `insert_pending_orders`, `save_bracket_night`, `read_orders`; book `load_book` (`LoadedBook`),
  `save_book_night(..., executed_targets=)`, `save_book_decision`, `read_book_*`; benchmark
  `load_benchmark`, `save_benchmark_night`; `dividends_on` / `dividends_between` (DividendMap shape),
  `applied_splits_on` / `applied_splits_between`; `MARKET_WINDOW_DAYS = 550` (the single source of the
  window), `market_window_since(d)`, `load_market_window(conn, since)` (bars since a date via
  `backtest.io.read_bars_frame(conn, since=...)`). Nothing commits; `paper` runs a night in one transaction.
- Persisted conventions (phase 8 relies on them; verified in phases 6/7): expired and closed orders stay in
  `orders`; `book_targets` stay after execution, ranked 1..n (an empty decision writes no row); every
  strategy has a day-0 snapshot at `prev_session(paper_start)`; SPY keeps one whole-share `book_positions`
  row; between nights every engine's `paper_state.pending_session = next_session(last_session)`.
- `commands/paper.py`: `python -m seer_engine [--dry-run] [-v] paper [--now ISO8601]`. Runs only when the
  real `runs` row for `run_dates(now).session_date` is `success`; steps every new session for every
  roster strategy, decides the next session, all in one transaction (`runs.start_paper` marks `running` in its own
  short transaction, `finish_paper` sets `success` inside the night's transaction, `fail_paper` records a failure in its own);
  idempotent per (strategy, session).
- `commands/paper_check.py` (phase 8): read-only replay check, `[--require-sessions N]`, exit 1 on mismatch.
- `commands/explain.py` (phase 9): optional LLM text for new paper entries; never fails the night.

## Phases

| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID | Card |
|---|-------|-----------|---------|-------|-----------|------------|------|--------|------|
| 1 | Migration 003 and the frozen roster | R2 | `db`, `engine/paper` | 8 | — | NORMAL | `.workflows/plan/paper-trading-ship/phase-1.md` | — | — |
| 2 | Book-engine split rule | R1 | `engine/sim` | 3 | — | NORMAL | `.workflows/plan/paper-trading-ship/phase-2.md` | — | — |
| 3 | Bracket and benchmark night cores | R1 | `engine/paper` | 4 | 1 | HARD | `.workflows/plan/paper-trading-ship/phase-3.md` | — | — |
| 4 | Book night core | R1 | `engine/paper` | 2 | 1, 2 | HARD | `.workflows/plan/paper-trading-ship/phase-4.md` | — | — |
| 5 | Dividends and held-symbol bars in `nightly` | R1 | `engine` | 10 | 1 | NORMAL | `.workflows/plan/paper-trading-ship/phase-5.md` | — | — |
| 6 | Paper store (load and save state) | R1 | `engine/paper` | 3 | 1, 3, 4 | HARD | `.workflows/plan/paper-trading-ship/phase-6.md` | — | — |
| 7 | `paper` command and workflow step | R1, R3 | `engine/commands` | 5 | 5, 6 | HARD | `.workflows/plan/paper-trading-ship/phase-7.md` | — | — |
| 8 | `paper_check` replay check | R3 | `engine/paper` | 4 | 7 | HARD | `.workflows/plan/paper-trading-ship/phase-8.md` | — | — |
| 9 | `explain`: optional LLM explanations | R5 | `engine` | 4 | 1 | NORMAL | `.workflows/plan/paper-trading-ship/phase-9.md` | — | — |
| 10 | Web data layer, monthly math, demo seed | R4, R2 | `web/lib` | 13 | 1 | HARD | `.workflows/plan/paper-trading-ship/phase-10.md` | — | — |
| 11 | Web: Today, Positions, History | R4 | `web/app` | 12 | 10 | HARD | `.workflows/plan/paper-trading-ship/phase-11.md` | — | — |
| 12 | Web: Leaderboard, monthly table, checklist | R4 | `web/app` | 4 | 11 | HARD | `.workflows/plan/paper-trading-ship/phase-12.md` | — | — |
| 13 | Ship: CI lint, workflow, Neon, Vercel, docs | R6, R7 | repo | 7 | 1–12 | NORMAL | `.workflows/plan/paper-trading-ship/phase-13.md` | — | — |

### Phase 1 — Migration 003 and the frozen roster
**Satisfies:** R2
**Owns:** `db/migrations/003_paper.sql` (C1); `engine/src/seer_engine/paper/__init__.py` (docstring only, no re-exports); `engine/src/seer_engine/paper/roster.py` (pure: `RosterEntry` with display fields, engine, `obj`, `params`, `rules`, `lookback`, `gate_note`; `ROSTER`, `ROSTER_IDS`, `MAX_LOOKBACK_BARS` = 253, `entry`, `spec`, `spec_text`, `spec_digest`, `backtest_gate`, `strategy_params`); purity-test coverage for `paper/*.py` except `store.py`; `demo.DEMO_TABLES` gains the five paper state tables and `purge_demo` also resets `strategies.paper_start`/`params` (the demo seed's paper clock); tests (`test_migrate`, new `test_paper_roster.py`, `test_demo`).
**Does not touch:** any other engine module, the web, workflows, docs.
**Exit criteria:** `migrate` applies 003 on a fresh schema and is a no-op twice; roster display fields equal the migration's INSERT; digests pinned in a test; a demo purge empties the paper tables, keeps `dividends`, and resets the roster rows' `paper_start`/`params`.

### Phase 2 — Book-engine split rule
**Satisfies:** R1
**Owns:** `sim/book.py` `apply_book_split` + `BookSplit`; export in `sim/__init__.py`; tests in a new `tests/test_sim_book_split.py`.
**Does not touch:** `step_book` behavior, `sim/split_adjust.py`, anything outside `sim`.
**Exit criteria:** whole-share and fractional rules, cash in lieu (credited to cash and `income_usd`), floor-to-zero → `forced` Trade, prices/targets rescaled by the exact fraction, reverse splits, purity.

### Phase 3 — Bracket and benchmark night cores
**Satisfies:** R1
**Owns:** `paper/bracket.py`, `paper/benchmark.py` (C3, incl. `split_benchmark` and `step_benchmark(..., split=)`); tests proving `settle_bracket`+`decide_bracket` looped over ≥ 300 synthetic sessions equal `run_backtest` (snapshots, events, closed, open), `step_benchmark` looped equals `buy_and_hold` with dividends; split on a pending and on an open bracket order; no look-ahead.
**Does not touch:** `sim/*`, runners, `paper/book.py`, DB.
**Exit criteria:** equality tests green; purity green.

### Phase 4 — Book night core
**Satisfies:** R1
**Owns:** `paper/book.py` (C3); tests proving `decide_book`+`settle_book` looped equal `run_book` for `MONTHLY_HOLD` with FACTOR and TIMING on synthetic markets (incl. dividends and a forced close), split on a held position and on pending targets, no look-ahead.
**Does not touch:** `sim/*` (uses phase 2's `apply_book_split`), runners, DB.
**Exit criteria:** equality tests green; purity green.

### Phase 5 — Dividends and held-symbol bars in `nightly`
**Satisfies:** R1
**Owns:** `massive.Client.dividends(d)` (+ `MassiveSource` protocol); new `dividends.py` (parse CD+SC, sum per symbol/ex-date, upsert into `dividends`); `splits.apply_splits` also rewrites `dividends` before the execution date (`round(amount * from / to, 6)`); `nightly` fetches dividends per missing session in the same transaction and adds paper-held symbols (`universe.paper_symbols(conn, d)`: open/pending `orders`, `book_positions`, `book_targets` for sessions ≥ the session) to each session's wanted set; tests (`test_massive`, `test_nightly`, `test_splits`, new `test_dividends`).
**Does not touch:** `paper/*`, workflows, web.
**Exit criteria:** fake-client tests for dividends, split rewrite of dividends, held symbol outside the universe still fetched; nightly stays one transaction.

### Phase 6 — Paper store
**Satisfies:** R1
**Owns:** `paper/store.py` (C4, the API listed there; `MARKET_WINDOW_DAYS = 550` is the only window constant in the set); `backtest/io.read_bars_frame(conn, *, since=None)` (default unchanged); PG round-trip tests for every engine's state, targets, fills, trades, snapshots, splits and dividends queries; windowed market load.
**Does not touch:** commands, workflows, web, runners.
**Exit criteria:** save→load round trips are exact (Decimal, dates, ordering); `load_market` unchanged.

### Phase 7 — `paper` command and workflow step
**Satisfies:** R1, R3
**Owns:** `commands/paper.py` (calls only phase 1's roster API and phase 6's store API; the window is `store.market_window_since`; catch-up uses `night_view` for bars/FX and undoes later splits on dividends too; passes an applied SPY split to `step_benchmark(split=)`); `runs.py` paper status helpers; `.github/workflows/nightly.yml` "Paper" step after "Nightly"; PG integration tests with synthetic bars: init (paper_start = session_date, day-0 snapshot), ≥ 5 consecutive nights, idempotent re-run writes nothing, a failure leaves no partial state and marks `paper_status = failed`, failed/missing bars run → no paper step, no look-ahead (changing bars dated ≥ S leaves S's decisions unchanged), frozen-spec mismatch refused (`SpecMismatch`).
**Does not touch:** `nightly.py`, `paper/*` cores and store (only calls them), `demo.py`, the job's `timeout-minutes`, web, docs.
**Exit criteria:** tests green; `--dry-run` writes nothing.

### Phase 8 — `paper_check` replay check
**Satisfies:** R3
**Owns:** `paper/replay.py` (pure comparison), `commands/paper_check.py`; tests: after ≥ 5 nights of `paper` on synthetic data the check passes; a tampered snapshot/trade/position fails; a split on a held symbol reports "split-affected" without failing; `--require-sessions`.
**Does not touch:** `commands/paper.py`, workflows (phase 13 adds the step), web.
**Exit criteria:** tests green.

### Phase 9 — `explain`
**Satisfies:** R5
**Owns:** `llm.py` (Anthropic-compatible Messages call over `LLM_BASE_URL`/`LLM_API_KEY`/`LLM_MODEL`; the key is sent as both `x-api-key` and `Authorization: Bearer` for z.ai compatibility; timeouts, redaction), `commands/explain.py` (fills `orders.explanation` for new pending A orders and `book_targets.explanation` for new entries of the latest decision; missing config or any LLM failure → leaves NULL, exit 0, logs); tests with a fake transport.
**Does not touch:** `paper` command, workflows (phase 13), web.
**Exit criteria:** tests green; never raises on LLM failure.

### Phase 10 — Web data layer, monthly math, demo seed
**Satisfies:** R4, R2
**Owns:** `web/lib/strategy.ts` (`Engine`, `Gate`, `engineOf`, `parseGate`, `shortLabel`); `web/lib/data.ts` (`Strategy` with `engine/rulesId/paperStart/gate/isPaper/short`; `Holding` with `kind/key/orderId/maxDays` for both engines and the benchmark; `pendingOrders()` → `Pending`/`PendingOrder`; `Trade.key/strategyShort/ExitReason`; leaderboard pnls per engine; `RunStatus.latestStatus/paperStatus/paperError/paperFinishedAt`; `monthly(id, sessionDate)` → `MonthlyTable`); `web/lib/monthly.ts` (new, pure) + `monthly.test.ts` hand-checked fixture; `web/lib/metrics.ts` `checklist(m, spy, gate)` 6th item "Backtest gate passed"; `web/lib/slots.ts` (`slotCount`, `cardBg`; no 4-slot assumption for book); `web/scripts/seed-demo.mjs` in the new shape (gate notes = `roster.py` texts); Step 10 minimal compile fixes to `page.tsx`, `positions/page.tsx`, `leaderboard/page.tsx` (these land before phases 11/12).
**Does not touch:** page components beyond the Step 10 fixes (phases 11, 12), engine.
**Exit criteria:** vitest green incl. monthly fixture (month boundaries, partial first/current month, no-trade months, SPY same months); `tsc --noEmit` clean.

### Phase 11 — Web: Today, Positions, History
**Satisfies:** R4
**Owns:** `app/(app)/page.tsx` + `today.module.css` (SPY-champion no-buys state; stale/failed still first), `positions/*` (strategy switcher, paper chip, bracket/book/benchmark cards by `Holding.kind`, `pendingOrders` sheet, paper-step warning), `history/*` (roster-driven filters, book exit reasons signal/forced, paper chip, `Trade.key`), new shared `components/StrategySwitch.tsx` (icon-only links, `?s=`, `href`/`label` props), `components/PaperChip.tsx`, and `components/roster.ts` (only `strategyIcon`, `selectStrategy`, `sharesLabel`: short labels and the paper flag stay phase 10's). The three pages are replaced whole, starting from phase 10 Step 10's versions.
**Does not touch:** leaderboard, `web/lib/*` (consumes phase 10's API; a missing field is added in phase 10's plan, not here).
**Exit criteria:** vitest + `tsc --noEmit` green; screens render on demo data at 414 pt and desktop, light and dark.

### Phase 12 — Web: Leaderboard, monthly table, checklist
**Satisfies:** R4
**Owns:** `app/(app)/leaderboard/page.tsx` + `leaderboard.module.css` + `view.ts`/`view.test.ts` (leaderboard-only helpers: looks, best research, score line, month rows over phase 10's `MonthlyTable`): roster-driven colors/cards (no hardcoded A/B/C), SPY crown, checklist per research strategy via phase 11's `StrategySwitch`/`selectStrategy`/`strategyIcon` with `checklist(m, spy, gate)` and an honest score line, "Month by month" sheet from `monthly(id, run.sessionDate)` (Return, SPY, Trades, Worst drop; since-start row; partial-month marker).
**Does not touch:** other screens, `web/lib/*`.
**Exit criteria:** as phase 11, on the Leaderboard.

### Phase 13 — Ship: CI lint, workflow, Neon, Vercel, docs
**Satisfies:** R6, R7
**Owns:** `.github/workflows/engine-ci.yml` (ruff `select = ["E9", "F"]`, `ignore = ["F401"]` + `tsc --noEmit`), `engine/pyproject.toml` (ruff config, `ruff>=0.16,<0.17` dev dep), `.github/workflows/nightly.yml` ("Paper check" and "Explain" steps; `timeout-minutes` 30 → 45), applying `003` to Neon and a `paper --dry-run` against Neon, a **preview** `vercel deploy` of the worktree tree (production deploys from `main` on merge through the Git integration; seertrade.site is already live), `docs/runbooks/paper-trading.md` (operations + owner steps: LLM secrets, Google OAuth, Vercel env if missing, Add to Home Screen; no DNS step + the release checklist), `docs/runbooks/data-pipeline.md`, `docs/ROADMAP.md` (P0, P4 paper-only entry, P5, v0.1.0), `engine/package_readme.md` sections.
**Does not touch:** source behavior. The README and the `v0.1.0` release are **not** in this phase (see After landing).
**Exit criteria:** CI commands pass locally; Neon at migration 003; dry-run paper on Neon succeeds; preview deploy URL and production URL recorded, remaining owner steps named in the runbook; docs updated.

## Reconciliation Log

Round 1. Requirement map after every move: R1 → 2, 3, 4, 5, 6, 7; R2 → 1, 10; R3 → 7, 8; R4 → 10, 11, 12;
R5 → 9; R6 → 13; R7 → 13 (unchanged from the draft; no step moved between phases).

| # | Conflict | Phases | Resolution |
|---|---|---|---|
| 1 | Unmet assumption: phase 7 called assumed roster names (`RosterEntry.digest`, `frozen_params`, `paper_object_lookback`) | 1, 7 | Phase 7 rewritten to `roster.strategy_params(e)["digest"]`, `strategy_params(e)`, `e.lookback`; its tests too |
| 2 | Unmet assumption: phase 7 called 15 assumed store names/shapes (`load_roster_rows`, `save_roster_spec`, `load_paper_states`, `save_paper_state`, `save_snapshot`, `save_bracket_decision`, `load_book_targets`, `load_portfolio(conn, state)`, `save_book_night(conn, sid, session, night)`, `load_benchmark(conn, state, start)`, `dividends_on(conn, session)`, …) | 6, 7 | Every call site rewritten to phase 6's real API (`read_strategies`, `check_digest`, `freeze_spec`, `read_paper_state`, `init_paper_state`, `write_pending`, `load_portfolio`, `save_bracket_night`, `insert_pending_orders`, `load_book`, `save_book_night(executed_targets=)`, `save_book_decision`, `load_benchmark`, `save_benchmark_night`, `dividends_between`, `applied_splits_on`, `load_market_window`); Requires table replaced |
| 3 | Duplicate constant: phase 7 `WINDOW_DAYS = 550` vs phase 6 `MARKET_WINDOW_DAYS = 550` | 6, 7 | Phase 7's constant deleted; it calls `store.market_window_since` |
| 4 | Contract drift: phase 7 wrote `paper_state` itself while phase 6's `save_*_night` / `write_pending` / `save_book_decision` / `init_paper_state` already write it | 6, 7 | Phase 7 no longer writes `paper_state` directly; the store owns every `paper_state` write |
| 5 | Behavioral fork: SPY `pending_session` NULL (phase 3/6 handoff prose) vs `next_session(last_session)` (phase 7 `plan_night` guard and tests, phase 10 seed) | 3, 6, 7, 10 | Every engine keeps `pending_session = next_session(last_session)`; phase 7 calls `write_pending(..., decision=False)` for SPY at init and after every SPY night; phase 3/6 handoffs edited (Decisions) |
| 6 | Contract drift: frozen-spec mismatch raised as phase 7 `PaperError` vs phase 6 `check_digest` → `SpecMismatch` | 6, 7 | Phase 7 uses `store.check_digest`; test asserts `SpecMismatch: A: stored spec digest … new id` |
| 7 | Behavioral fork: `paper_start` set but no `paper_state` "restarts cleanly" (phase 7) vs `freeze_spec` refuses an already-frozen row (phase 6) | 6, 7 | `plan_night` refuses with a "reset its paper clock" error; reset procedure (index Rollback, runbook, phase 7 handoff) now includes `UPDATE strategies SET paper_start = NULL, params = '{}'` |
| 8 | Unmet assumption / gap: demo seed writes `paper_start`/`params`; purge kept them; `paper` would refuse the first real night (handoffs in 1, 7, 10) | 1, 7, 10 | Phase 1 `purge_demo` also resets `strategies.paper_start`/`params` (`RESET_PAPER_CLOCK`), with tests; phase 10 seed writes both freely; phase 7 refusal unchanged |
| 9 | Contract drift: seed `backtest_gate.note` texts differed from `roster.py` `gate_note` | 1, 10 | Seed uses phase 1's texts verbatim |
| 10 | Gap: catch-up `night_view` undid later splits on bars but not on stored dividends (rewritten by `apply_splits`), so a multi-session catch-up could credit post-split amounts to pre-split shares | 5, 7 | `_Tonight.dividends_on` multiplies an ex-date-S amount by later applied split factors (6 dp, half-up) |
| 11 | Unmet assumption: phase 11 coded against an assumed web API (`BracketPosition`/`BookPosition` union, `targets()`/`Target`, `picks()` for paper orders, `Trade.id` as key, `engine: Engine \| null`) | 10, 11 | Today/Positions/History rewritten to `Holding` (`kind`, `key`, `orderId`, `maxDays`, nullable `tp/sl/weight`), `pendingOrders()`/`Pending`/`PendingOrder`, `Trade.key`/`strategyShort`, `cardBg` |
| 12 | Duplicate work: phase 11 `roster.ts` `shortName`/`isPaper` vs phase 10 `shortLabel`/`Strategy.short`/`Strategy.isPaper` | 10, 11 | Removed from `roster.ts` (keeps `strategyIcon`, `selectStrategy`, `sharesLabel`); tests trimmed |
| 13 | Unmet assumption: phase 12 coded against `Board.rows[].exits`, `monthly(curve, spy, exits, today)` with `ret/spy` fields, nullable `gate`, `StrategySwitch({ path })` | 10, 11, 12 | Rewritten to `monthly(id, run.sessionDate)` → `MonthlyTable` (`return`, `spyReturn`, nullable `sinceStart`), `Gate`, `StrategySwitch({ href, label })` |
| 14 | Duplicate work: phase 12 `view.ts` `shortName`/`selectStrategy` and page `ICONS` map vs phases 10/11 | 10, 11, 12 | Removed; page uses `Strategy.short`, phase 11 `selectStrategy`/`strategyIcon`; `view.ts` keeps leaderboard-only helpers |
| 15 | Behavioral fork: current-month partial from `wibDate(now)` (phase 12) vs `runStatus().sessionDate` (phase 10) | 10, 12 | `sessionDate` wins; phase 12 calls `monthly(id, run.sessionDate)` |
| 16 | File collision: phase 10 Step 10 edits `page.tsx`, `positions/page.tsx`, `leaderboard/page.tsx`; phases 11/12 quoted the pre-phase-10 files | 10, 11, 12 | 11/12 now state they replace phase 10's versions; Today keeps phase 10's `orderId`/`maxDays` day-5 guard; phase 12 rollback no longer warns about `checklist` arity |
| 17 | Open risk: phase 9 sent only `x-api-key`; z.ai may need `Authorization: Bearer` | 9 | Client sends both headers; test asserts both; risk removed |
| 18 | Scope deviation: index said `vercel deploy --prod`; phase 13 planned a preview deploy | 13 | Preview accepted (Decisions "Vercel"); phase 13 text made final |
| 19 | Stale owner step: DNS listed as an owner step though seertrade.site is live | 13 | Runbook section 4 says DNS is live (no step); handoff list trimmed |
| 20 | Unowned change: nightly job budget (phase 5 handed it to "7/13"; phase 13 conditional) | 5, 7, 13 | Phase 13 sets `timeout-minutes: 45`; phase 7 does not touch it; phase 5 handoff edited |
| 21 | Contract extension: phase 3 added `split_benchmark` / `step_benchmark(split=)` beyond C3 | 3, 7 | Accepted (C3 extended); phase 7 passes the applied SPY split on S |
| 22 | Contract drift: phase 13 runbook gave `paper` exit 2 for a missing bars run / changed digest; phase 7 returns 1 | 7, 13 | Runbook exit-code row corrected |
| 23 | Verification: phase 8's persisted conventions (expired orders kept, targets kept ranked 1..n, day-0 snapshots, SPY single whole-share row) | 6, 7, 8 | Hold in phases 6/7 as written; only SPY's pending convention changed (row 5), which phase 8 ignores |
| 24 | Verification: phase 13 lint (`E9`, `F`, ignore `F401`) over phases 1–9 | 1–9 | pyflakes over every full-module Python block: no finding other than F401 |

Round 2 (verification). Requirement map unchanged: R1 → 2–7; R2 → 1, 10; R3 → 7, 8; R4 → 10, 11, 12; R5 → 9;
R6 → 13; R7 → 13. Phases 1–9 and 10–12 were checked by building every plan code block into scratch trees
(engine plan suites green against `seer-pg`, incl. phase 7/8 integration; web `tsc --noEmit` + vitest green
after 10, after 11 and after 12; seed replayed onto 001+002+003). No cross-phase signature mismatch in 1–12.

| # | Conflict | Phases | Resolution |
|---|---|---|---|
| 25 | Contract drift: phase 13 runbook said a changed digest makes `paper` "refuse to run (changes nothing)" | 7, 13 | Runbook/readme/12j: fails the night as `store.SpecMismatch`, rolled back, `paper_status = failed`, exit 1; orphaned-clock refusal added |
| 26 | Name drift: phase 13 used status `"not started"`; phase 8 emits `not-started` | 8, 13 | Phase 13 expected output, verification and exit table use `not-started` |
| 27 | Stale caveat: phase 13 exit-code table marked `paper_check`/`explain` codes as unverified (†) | 8, 9, 13 | Marks removed; codes stated from phases 8/9 (`explain` exit 1 DB error only, 2 only when `LLM_*` set but `DATABASE_URL_UNPOOLED` missing) |
| 28 | Contract drift: phase 13 readme described the window as `load_market_window(conn, since)` only and `step_benchmark` without `split=` | 3, 6, 7, 13 | Uses `store.market_window_since(d)` + `night_view`; `step_benchmark(…, *, split=None)` |
| 29 | Contract drift: phase 13 (and index C4) said `running` → `success` in one transaction | 7, 13 | Matches phase 7's `start_paper` / `finish_paper` / `fail_paper` transaction split; index C4 wording fixed |
| 30 | Signature drift: phase 13 and index phase 5 row quoted `universe.paper_symbols(conn)` | 5, 13 | `paper_symbols(conn, d)` everywhere |
| 31 | Plan hygiene: stray code fences in phase 11 (after Positions `page.tsx`) and phase 12 (after `view.ts`, `view.test.ts`) misrendered steps | 11, 12 | Fences removed |
| 32 | Contract drift: phase 12 Files table said `view.ts` does "selection" (phase 11's `selectStrategy`) | 11, 12 | Wording removed; vitest count corrected to 16 |
| 33 | Index status still `planned` | index | Set to `reconciled` |

## Decisions

| Fork | Chosen | Rung |
|---|---|---|
| §6 persistence shape | Separate `book_*` tables + `paper_state`, `orders.mark` column; `orders` otherwise unchanged | 1: invariant 3 (additive) + D6 recommendation |
| §6 pure nightly core | New `paper/` night functions mirroring the runner loop bodies; runners untouched; equality proven by tests and D7 | 1: invariant 2 (closed records must re-render byte for byte) |
| §6 history at night | Windowed `COPY` of bars since `date − 550 calendar days` (≥ 253-bar lookbacks with margin); no pickle cache. Measured 219,575 rows in 2.34 s and 326,410 rows in 2.73 s from Neon | 6: measurement |
| §6 dividend source | Massive `/v3/reference/dividends?ex_dividend_date=D` per session (free tier verified: 513 rows for 2026-09-18 in one page, SPY 1.888834), types CD + SC summed per symbol/ex-date, persisted in `dividends`, rewritten by splits like bars | 5: handover §6 "check Massive first; persist recommended" + probe |
| §6 book split rule | As the handover lists; cash in lieu credited to cash and the position's `income_usd` (so pnl reconciles); floor-to-zero closes with reason `forced` at the old mark; persisted targets for the split symbol rescaled too | 5: handover §6 + `apply_split` mirror |
| When a split touches paper state | Only when `split_adjustments.applied = true` for (symbol, session): then stored history moved, and the state sized from it must move once | 1: invariant 6 (state stays in the units it was sized in) |
| Marks for bracket orders | Persisted in `orders.mark`, never rebuilt from `bars` (rebuilt marks would be post-split and `apply_split` would rescale them twice) | 6: readme "Simulator: P4 nightly" warning |
| §6 SPY benchmark persistence | `paper_state` + one `book_positions` row (SPY) + `equity_snapshots`, stepped nightly with `buy_and_hold` rules | 5: handover §6 recommendation |
| Decisions between nights | Persisted (bracket: pending `orders`; book: `book_targets` + `paper_state.pending_*`) and executed as persisted the next night; the replay check proves recompute == persisted | 1: same-path law + design §3 (picks are made at night, executed next session) |
| §6 paper start | Every roster entry starts on the same first paper day: the `session_date` of the first successful `paper` run | 5: handover §6 recommendation + D11 |
| Initial FX | The latest `fx_rates` row on or before the first run's `data_date` (the first paper day's own rate does not exist yet at decision time), stored in `paper_state.usd_idr`; the replay passes it explicitly | 5: D1 wording vs no look-ahead (invariant 5 wins) |
| Monthly strategies in October | F4 and F1 decide only on the first session of a month, so they sit in cash until the open of 2026-11-02; shown as such, not special-cased | 1: same-path law (`run_book` semantics) |
| Force-close rule live | A held symbol with no bar on S is closed on S at its mark (the runners' rule as known that night); a later resume makes the replay check report it | 1: same-path law |
| Replay check scope | `run_rules` / `buy_and_hold` equality is asserted for a strategy unless an applied split hit a symbol it held or had pending in the window; then the strategy is reported "split-affected", not failed | 4: handover acceptance 1 vs whole-share rounding across splits |
| Roster rows | Migration 003 writes display rows and flips the champion to SPY, deletes B/C only if unreferenced; `paper` writes the frozen spec + `paper_start` and refuses a changed spec under an existing id | 5: D2, D4 |
| §6 monthly view placement | Leaderboard screen, a "Month by month" sheet with a strategy switcher (`?s=`) | 5: design §6 ("bottom tab bar, 4 icons") |
| §6 web metrics for book strategies | `strategyMetrics(snapshots incl. day 0, pnls of non-idle book_trades)`, as `run_stats` does | 5: handover §6 |
| Go-live checklist | Six rows: the five design-§1 metrics plus "Backtest gate passed", read from `strategies.params.backtest_gate`; false for every roster entry today | 5: D12 |
| Paper failure state | `runs.paper_status/paper_error/paper_finished_at`; the UI warns when the latest run's paper step is not `success` | 5: design §8 |
| Held symbols leaving the index | `nightly` keeps fetching bars for symbols held or pending in paper state | 1: same-path law (a position needs its bars) |
| LLM step | Separate `explain` command after `paper`, `continue-on-error`, writes nothing on failure | 5: D9 + design §8 |
| CI lint (P0) | `ruff check` with a minimal rule set that the current tree passes, plus `tsc --noEmit` for the web | 6: convention (no linter exists yet; do not mass-edit closed code) |
| Vercel | Phase 13 proves the build with a **preview** `vercel deploy` of the worktree tree, not `--prod`: the project is Git-connected and seertrade.site is live, so production deploys from `main` on the merge (a manual `--prod` from the branch would put unmerged code on the live domain). DNS is already live and is no owner step. The Google OAuth redirect URI, any missing Vercel env var, the `LLM_*` repo secrets and Add to Home Screen are owner steps written into the runbook, not performed | 5: handover §7 ("owner steps … document them in a runbook instead of waiting") + phase 13's measured facts; coordinator decision |
| API names (engine) | Phases 7 and 8 call phase 1's roster API (`RosterEntry`, `ROSTER`, `MAX_LOOKBACK_BARS`, `strategy_params`, `spec_digest`) and phase 6's store API as written; phase 7's assumed names are gone | 3: plan code blocks (phases 1 and 6 are the implementations) |
| Bars window constant | `store.MARKET_WINDOW_DAYS = 550` is the only one; `paper` uses `store.market_window_since` | 3: plan code blocks (phase 6) |
| Who writes `paper_state` | Only `paper.store` (`init_paper_state`, `save_*_night`, `write_pending`, `save_book_decision`); `paper` never writes it directly | 3: plan code blocks (phase 6's saves already write it) |
| SPY `pending_session` | `next_session(last_session)` between nights, `pending_decision` false, like every engine (`write_pending` after each SPY night) | 3: plan code blocks (phase 7 `plan_night` guard + tests, phase 10 seed) over phase 3/6 handoff prose |
| Changed spec / orphaned clock | A changed digest under a set `paper_start` fails the night as `store.SpecMismatch`; a `paper_start` with no `paper_state` is refused until the clock is reset (`paper_start = NULL, params = '{}'` plus the paper rows) | 3: plan code blocks (phase 6 `check_digest`, `freeze_spec` writes once) |
| Demo purge vs paper clock | `demo.purge_demo` (phase 1) also runs `UPDATE strategies SET paper_start = NULL, params = '{}'` when it purges; the demo seed may write both; `paper`'s frozen-spec refusal is unchanged | 1: C2 ("a changed digest is a hard error") + invariant 8 ownership of `demo.py`; coordinator decision |
| Web names | Phases 11 and 12 use phase 10's real exports (`Holding`, `pendingOrders`/`Pending`/`PendingOrder`, `Trade.key`/`strategyShort`/`ExitReason`, `Strategy.engine/rulesId/paperStart/gate/isPaper/short`, `RunStatus.paperStatus`, `checklist(m, spy, gate)`, `monthly(id, sessionDate)` → `MonthlyTable`, `slotCount`/`cardBg`, `shortLabel`) | 3: plan code blocks (phase 10) |
| Shared web helpers | `components/roster.ts` (phase 11) holds only what `web/lib` lacks: `strategyIcon`, `selectStrategy`, `sharesLabel`; phase 12 reuses them plus `StrategySwitch`/`PaperChip`; `leaderboard/view.ts` holds leaderboard-only helpers | 6: convention (one owner per helper) |
| Partial current month | The latest month is partial while `runStatus().sessionDate` (engine calendar) is in it; phase 12 calls `monthly(id, run.sessionDate)` | 3: plan code blocks (phase 10 `monthly.ts` + fixture) |
| Page edit order | Phase 10 Step 10's minimal compile fixes to `page.tsx`, `positions/page.tsx`, `leaderboard/page.tsx` land first; phases 11 and 12 replace those files whole, quoting phase 10's version | 2: phase exit criteria (`tsc --noEmit` green at every phase) + DAG 10 → 11 → 12 |
| Seed gate notes | The demo seed's `backtest_gate.note` texts are `roster.py`'s `gate_note` verbatim | 3: plan code blocks (phase 1 is the single source, C2) |
| LLM auth | `llm.Client` sends the key as both `x-api-key` and `Authorization: Bearer <key>` (z.ai compatibility) | 5: design §3 ("GLM via z.ai, Anthropic-compatible") + coordinator decision |
| Nightly time budget | Phase 13 raises the nightly job's `timeout-minutes` 30 → 45 (3 Massive calls per missing session plus Paper, Paper check, Explain); phase 7 does not touch it | 6: measurement (phase 5: a 30-session gap is ≈ 19 min of rate-limit waits) |
| Catch-up night view | Kept: a multi-session catch-up computes each session on `night_view` (later bars/FX hidden, later applied splits undone on bars) and undoes later splits on that session's dividends too, so it equals night-by-night stepping. Undoing a later split on 4-dp stored bars (6-dp dividends) is exact only to that rounding; such sessions involve an applied split on a held or pending symbol and are already inside the replay check's split-affected scope | 1: invariant 5 (no look-ahead) + invariant 6 (same path); coordinator decision |
| SPY split | Phase 3's `split_benchmark` / `step_benchmark(split=)` is accepted (C3 extended); `paper` passes the applied SPY split on S through it, so a SPY split never stops the night | 2: phase 3 exit criteria + C3 extension; coordinator decision |
| Persisted conventions (phase 8) | Expired/closed orders stay in `orders`; `book_targets` stay ranked 1..n after execution (empty decision = no rows); day-0 snapshot for every strategy; SPY = one whole-share `book_positions` row. Verified in phases 6/7 | 3: plan code blocks (phase 6 store, phase 7 init) |
| CI lint rule set | Phase 13's ruff `select = ["E9", "F"]`, `ignore = ["F401"]`, `ruff>=0.16,<0.17` dev dep, is accepted; phases 1–12 Python must pass it (spot-checked clean) | 6: convention (P0 bugs-only lint; closed records untouched) |
| `paper` exit codes | 0 = stepped or no-op; 1 = no successful bars run (nothing written) or the night failed (rolled back, `paper_status = failed`; a changed digest lands here); 2 = missing setting (cli) | 3: plan code blocks (phase 7 `execute`) |
| Release timing | The 5-night verification, the README and `v0.1.0` run after this set lands and ≥ 5 paper sessions exist ("After landing"); they are not a phase, because a phase that waits days would hold the whole set off `main` and stop the clock from starting | 5: handover §6 "land the code, start the clock, leave the 5-day verification and the release as a clearly stated final step" + D11 |

## Open Questions

(none)

## Rollback

- Per phase: `git revert` the phase commit; every phase leaves the tree green.
- Neon: migration 003 is additive. To back out after it was applied: the web from `main` before this
  set ignores the new tables; `UPDATE strategies SET is_champion = (id = 'A')` restores the old flag.
  Paper rows can be removed with `TRUNCATE paper_state, book_positions, book_targets, book_fills, book_trades`
  plus `DELETE FROM orders/equity_snapshots WHERE strategy_id IN (roster)` plus
  `UPDATE strategies SET paper_start = NULL, params = '{}'` — which resets the paper clock (without the
  last statement `paper` refuses to restart: a `paper_start` with no `paper_state`).
- Workflow: removing the "Paper" step stops paper trading without touching bars.

## After landing (operational, not a phase)

1. The next scheduled `nightly.yml` run after the merge migrates Neon (already at 003 from phase 13)
   and runs `paper` for the first time: paper_start = that run's `session_date`.
2. After ≥ 5 paper sessions: `engine/.venv/bin/python -m seer_engine paper_check --require-sessions 5`
   on Neon, and the run logs and the UI checked (acceptance 1 and 6).
3. Then, per the runbook's release checklist: write the full `README.md` (owner rule: README at
   release), mark P4 and v0.1.0 done in the ROADMAP, and `gh release create v0.1.0`.

## Next

Execute the phases one at a time, starting at phase 1:

    /implement -f PAPER_TRADING_SHIP_PLAN.md --phase 1

Or run the whole set as a swarm — a session per phase, concurrent wherever `Depends on` allows,
resumable on any machine:

    /analyze-orchestrator -f PAPER_TRADING_SHIP_PLAN.md

Or put them on the board first (GitHub repos only):

    /create-task --from-plan PAPER_TRADING_SHIP_PLAN.md

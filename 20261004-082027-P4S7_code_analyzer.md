# Code Analysis: Paper trading every night, month-by-month view, v0.1.0 ship

**Type:** Feature Implementation
**Date:** 2026-10-04 08:20 (UTC+7)
**Session ID:** 20261004-082027-P4S7
**Plan:** `PAPER_TRADING_SHIP_PLAN.md` (13 phases)
**Worktree:** `/home/miftah/.worktrees/seer/paper-trading-ship`, branch `feature/paper-trading-ship` (base `HEAD` = `origin/main` @ `844e4d7`)

---

## User Input

### Original User Request

```
/analyze docs/handover/2026-10-04-paper-trading-ship.md
```

The handover file is the specification. It is committed at `844e4d7` and is not copied here; every
phase reads it in full. The owner's own words, quoted in it:

> *"i still don't want to give up developing this app. how about we just keep going with our major
> plan, then we'll ship it. and we will see how it performs this month WITHOUT MY REAL MONEY …
> the app should be able to show us how seer performs month by month on paper"*

### User-Provided Context
- Handover §2 "Law: do not reopen": design §1 unchanged; same code path; no look-ahead; closed records
  untouched (`backtest/registry.py` not edited); read-only UI; Seer v2 design with icon-only Lucide
  buttons; honest reporting.
- Decisions D1–D12 (roster, SPY champion, paper labelling, frozen strategies, monthly view, book
  persistence, replay check, dividends, LLM, one writer, start date, no real-money surface).
- §6 lists the questions this analysis settles (answered in the plan index's Decisions table).
- Owner memories in force: no generic UI; icon-only buttons; public repo by choice; README only at
  release; worktree needs its own venv; paper-only ship; proof before money.

### User-Provided Files
- `docs/handover/2026-10-04-paper-trading-ship.md`

### Requirement IDs

Handover §4 "In scope" is already a numbered list; its numbering is used.

| ID | What the user asked for |
|---|---|
| R1 | Engine paper step: a new impure command and its pure core, per roster strategy per new session (load state, splits, settle, dividends, force-close, decide next session, persist orders/positions/fills/trades/snapshot, SPY benchmark snapshot) |
| R2 | Migration `003` (D6) plus the roster's `strategies` rows with `paper_start` and the frozen spec (D4); demo seed updated to the new shape |
| R3 | Replay check (D7) and design §8 failure handling (failed bars run → no paper step; stale data → "do not trade"; holidays → no session) |
| R4 | Web: Today champion state (D2), paper labelling (D3), book positions/trades in Positions and History, month-by-month table (D5), leaderboard metrics incl. book strategies, go-live checklist honesty (D12), no 4-slot assumption for book strategies |
| R5 | Optional LLM explanations (D9) |
| R6 | Ship: P0 CI closed (lint), Vercel deploy, owner steps for DNS and secrets in a runbook, README at release, `v0.1.0` release once acceptance holds |
| R7 | Docs: `engine/package_readme.md`, `docs/ROADMAP.md` (P4 paper-only, P5, v0.1.0), paper-operations runbook |

---

## Detailed Requirements Understanding

**Problem/Requirement Statement.** Seer has a bars pipeline (`nightly`), a pure fill simulator for
design-§5 brackets (`sim.size_picks` + `sim.step`), a pure book engine (`sim.step_book`), strategy A
and P7a's allocators, and runners (`run_backtest`, `run_book`, `run_rules`, `buy_and_hold`) that loop
those pure functions over in-memory history. Nothing yet runs a strategy forward night by night
against Neon, persists its state between nights, or shows that state per month. The work turns the
runner loop bodies into a per-night step over persisted state for a fixed roster of four paper
portfolios (SPY benchmark, A, F4-MOM12-N20-TREND, F1-SPY-SMA200-M), proves the stepped state equals
a one-shot `run_rules` replay, and surfaces it in the existing web app with a monthly table, with SPY
as champion and no real-money surface.

**Success Criteria.** Handover §5 acceptance 1–8. The ones that a code phase can meet tonight:
same-path equality on synthetic data over ≥ 5 nights; no look-ahead; idempotency; one transaction per
night; split and dividend synthetic tests; monthly values hand-checked against a fixture; Today's SPY
champion state; CI green with lint; docs. The ones that need real sessions (acceptance 1 on Neon,
acceptance 6, and the release) can only be checked after ≥ 5 live nights.

**Key Considerations.**
- The runners are closed records (A, A2, B and P7a reports must still re-render byte for byte), so
  the nightly core is new code that mirrors their loop bodies, and equality is proven by tests and by
  the replay check, not by refactoring the runners.
- Splits: Neon history is rewritten backwards by `splits.apply_splits` *before* the paper step runs
  (separate command, same job). Live state must therefore stay in the units it was sized in, and be
  rescaled exactly once by `apply_split` (bracket) or a new book split rule. The readme's P4 sketch
  already warns that marks must be pre-split; reconstructing marks from `bars` would double-adjust.
- A whole-share position sized before a split and one sized after it (as a replay over adjusted bars
  would) differ by rounding; `run_rules` equality cannot hold across a split on a held symbol.
- Monthly rules (`MONTHLY_HOLD`) decide only on the first session of a month. A paper start on
  Tuesday 2026-10-06 means F4 and F1 hold cash until the open of Monday 2026-11-02. That is the
  `run_book` semantics D7 compares against, so it is expected, and the UI shows a 0% October for them.
- Neon free tier: database 186 MB today (bars 177 MB); the new tables add kilobytes per month.
- The paper clock must start only after the code lands on `main` (D11); the 5-night verification and
  the release therefore happen after the orchestrated set lands.

**Assumptions** (each recorded with its rung in the plan index's Decisions table).

---

## Analysis Scope

### Explicitly Mentioned Files
- `docs/handover/2026-10-04-paper-trading-ship.md`, and through it: `docs/plans/2026-10-03-seer-design.md`,
  `docs/ROADMAP.md`, `engine/package_readme.md`, `docs/backtests/2026-10-04-p7a-dev-exploration.md`,
  `docs/runbooks/data-pipeline.md`, `web/lib/data.ts`, `web/lib/metrics.ts`, `web/app/(app)/*/page.tsx`,
  `web/scripts/seed-demo.mjs`, `docs/plans/claude-design-brief.md`, `docs/plans/2026-10-03-web-v2-implementation.md`.

### Discovered Related Files
- `engine/src/seer_engine/backtest/runner.py` (`run_backtest`, loop body at 171–200)
- `engine/src/seer_engine/backtest/book_runner.py` (`run_book` 164–281, `run_rules` 284–332, `run_stats` 537)
- `engine/src/seer_engine/backtest/benchmark.py` (`buy_and_hold` 123–184)
- `engine/src/seer_engine/backtest/market.py` (`Market`, `Membership`)
- `engine/src/seer_engine/backtest/io.py` (`load_market` 69, `read_bars_frame` 117, `read_intervals` 154, `read_fx` 177, `histories_from_frame` 238)
- `engine/src/seer_engine/sim/{model,lifecycle,sizing,split_adjust,book,rules,__init__}.py`
- `engine/src/seer_engine/strategies/{a,allocator,f_index,f_factor,base}.py`
- `engine/src/seer_engine/backtest/registry.py` (F1-SPY-SMA200-M line 101, F4-MOM12-N20-TREND line 221; read-only)
- `engine/src/seer_engine/commands/nightly.py`, `runs.py`, `dates.py`, `db.py`, `demo.py`, `cli.py`, `config.py`, `splits.py`, `massive.py`, `yahoo.py`, `universe.py`, `fx.py`, `bars.py`, `http.py`
- `engine/tests/{conftest,simkit,stratkit,allocatorkit,test_sim_purity,test_strategy_purity,test_nightly,test_migrate,test_demo}.py`
- `.github/workflows/nightly.yml`, `.github/workflows/engine-ci.yml`
- `db/migrations/001_init.sql`, `002_engine.sql`
- `web/lib/{session,format,slots,allow}.ts`, `web/components/{AppHeader,Nav,WhyToggle,CopyButton,RefreshButton}.tsx`, `web/app/(app)/{layout.tsx,actions.ts,*.module.css}`, `web/app/globals.css`, `web/auth.ts`, `web/package.json`, `web/vercel.json`
- `docs/design/Seer v2.dc.html` (the design source the UI must follow)

---

## Current Dataflow

### Entry Point: GitHub Actions `nightly.yml`

**Location:** `.github/workflows/nightly.yml`
**Trigger:** cron `0 23 * * 1-5` (and retry `0 1 * * 2-6`), concurrency group `seer-db-writer`.
**Steps:** check secrets → checkout → setup-python 3.11 → `pip install -e engine` → `python -m seer_engine migrate` → `python -m seer_engine -v nightly`.

### Processing Chain: `nightly`

1. **`commands/nightly.py:execute`** (97–134)
   - `demo.purge_demo_if_needed` (own transaction; truncates `DEMO_TABLES` when a demo run exists).
   - `rd = dates.run_dates(now)` → `data_date` = last completed session (close + 1 h ≤ now), `session_date` = next session.
   - `runs.start_run(conn, rd)` (`runs.py:16`): upsert on `runs_real_session_uidx`; returns None when the session already succeeded → exit 0.
2. **`_fetch`** (137–214): `missing` = sessions after SPY's latest bar through `data_date` (≤ `MAX_GAP` 30);
   `wanted[d] = universe.symbols_for_bars(conn, d)` (members on d plus a 30-day grace); per session
   `client.grouped(d)` (≥ 90% coverage required) and `client.splits(d)`; `fx.fetch_latest()`.
   **Held paper symbols are not in `wanted`**: a position in a symbol that left the index more than
   30 days ago would stop receiving bars.
3. **`_write`** (217–255): one transaction: `splits.apply_splits` (records each split once in
   `split_adjustments`, rewrites earlier `bars` rows when `applied`), `bars.upsert_bars`,
   `fx.upsert_fx`, `runs.finish_run`.
4. Any exception after `start_run`: rollback, `runs.fail_run` in its own transaction, exit 1.

### Processing Chain: backtests (the code paper trading must mirror)

1. **`run_backtest`** (`backtest/runner.py:129`), per session S: `members_on(data_date)`;
   `strategy.picks(history cut at data_date)` or `picks_prepared`; `size_picks(pf, picks, S)`;
   `step(pf, S, bars_on(S, held))`; force-close open orders whose symbol has no bar on S or later
   (`close_unpriced`) and replace S's snapshot; `data_date = S`. `snapshots[0] = (prev_session(start), cash0, cash0)`,
   `cash0 = initial_cash_usd(20,000,000 IDR, market.usd_idr_on(start))`.
2. **`run_book`** (`backtest/book_runner.py:164`), per session S: on `is_decision_session(rules, S)`
   targets from `allocator.targets(history cut, members_on(data_date), data_date, held − idle, params)`
   plus `_with_idle`; `bars_on(S, held ∪ targets)`; dividends with ex-date S for symbols held at night
   (`rules.dividends`); `step_book`; force-close gone positions (`close_book_unpriced`) and replace the
   snapshot. `usd_idr` may be passed explicitly.
3. **`run_rules`** (284): `bracket_v0` + Strategy → `run_backtest` (`usd_idr` must equal
   `market.usd_idr_on(start)`); `book` + Allocator → `run_book`.
4. **`buy_and_hold`** (`backtest/benchmark.py:123`): whole shares at `start`'s open, dividends with
   `start < ex_date ≤ end` credited on the ex-date and reinvested at that close, every session marked
   at its close; `snapshots[0] = (prev_session(start), cash0, cash0)`.

### Pure simulator pieces

- `sim.step` (`sim/lifecycle.py:128`): exits (time, gap, intraday SL-first) → fills/expiries → snapshot.
- `sim.size_picks` (`sim/sizing.py`): ranked picks into free slots 1..4, whole shares.
- `sim.apply_split` (`sim/split_adjust.py:113`): bracket live orders and marks rescaled by an exact
  fraction; cash in lieu; floored-to-zero positions force-closed. Call after S−1's step, before S.
- `sim.step_book` (`sim/book.py:445`): dividends → open exits → trims → buys → intraday exits →
  aging/marking → snapshot. `close_book_unpriced` (718). **No split rule for book positions.**
- `Portfolio` (`sim/model.py:175`): `cash`, `equity`, live `orders` (≤ 4, by slot), `marks` (open
  symbols' last closes), `last_session`. `Book` (`sim/book.py:217`): `cash`, `equity`, `positions`
  (sorted by symbol), `last_session`.

### Data Persistence (today)

- `strategies` (001): id, name, sub, icon, is_champion, is_benchmark, params jsonb, sort. Neon rows:
  A (champion), B, C, SPY (benchmark), all `params = {}`.
- `orders` (001): bracket rows, `slot 1..4`, `shares int > 0`, `exit_reason in (tp, sl, time, gap)`,
  `UNIQUE (strategy_id, session_date, symbol)`, `explanation text`. 0 rows on Neon.
- `equity_snapshots` (001): `(strategy_id, date)` PK, cash and equity. 0 rows on Neon.
- `runs` (001/002): one real row per session. Neon: 1 success (data 2026-10-02, session 2026-10-05).
- `bars`: 1,817,429 rows, 663 symbols, through 2026-10-02; `fx_rates` through 2026-10-02 (17,950);
  `split_adjustments`: 0 rows; `universe`: 518 current members.
- No dividends table, no book tables. `schema_migrations`: 001, 002.

### Exit Points (web, read-only)

- `web/lib/data.ts`: `strategies()`, `champion()`, `runStatus()` (latest success run + latest FX,
  `isStale` from `lib/session.ts`), `picks()` (pending orders of a strategy for a session),
  `positions()` (open orders with the latest close), `closedTrades()` (closed orders, ≤ 300),
  `leaderboard()` (all snapshots + closed-order pnls → `strategyMetrics`), `dismissAction()`.
- `web/lib/metrics.ts`: `strategyMetrics(snaps, pnls)` (total return last/first − 1, win rate,
  PF, peak max DD, trades, months = days/30.44) and `checklist()` (5 items; no backtest-gate item).
- Screens: Today (`app/(app)/page.tsx`) shows the champion's pending picks with 4 slot visuals, the
  stale alarm and day-5 actions; Positions shows the champion's open orders with stop/target range and
  5 day dots; History filters by hardcoded A/B/C; Leaderboard chart + champion checklist + cards with
  hardcoded `CARD_BG`/`LINE` for A/B/C.
- Navigation: 4 icon tabs (design §6).

---

## Key Data Structures

### `Order` — `engine/src/seer_engine/sim/model.py:101`
session_date, slot 1..4, symbol, last/limit/tp/sl prices, int shares, status, fill_date/price,
days_held, exit_date/price/reason, pnl_usd. Maps 1:1 onto `orders` (key `(strategy_id, session_date, symbol)`).

### `Position` / `Book` / `Target` / `Fill` / `Trade` / `BookSnapshot` — `sim/book.py:143–297`
Position: symbol, Decimal shares (fractional-capable), mark, entry_date, entry_price, days_held,
cost_usd, income_usd, stop, take, exit_pending. Trade exit reasons: signal, time, gap, tp, sl, forced;
`idle` flag. Fill reasons: entry, add, trim, signal, time, gap, tp, sl, forced.

### `TradeRules` — `sim/rules.py:65`
`DESIGN_V0` (bracket_v0, dividends False); `MONTHLY_HOLD` (book, monthly, open_limit, resize, dividends True, no idle).

### Roster objects
- A: `STRATEGY_A` + `STRATEGY_A_PARAMS` (`strategies/a.py:105, 324`), lookback 200.
- F4-MOM12-N20-TREND: `FACTOR` + `FactorParams(rank="momentum", top=20)` under `MONTHLY_HOLD`
  (`backtest/registry.py:221`); `factor_lookback` = max(253, 61, 20, 200) = 253; trend SPY:200.
- F1-SPY-SMA200-M: `TIMING` + `TimingParams(hold="SPY", signal="SPY", rule="sma", n=200)` under `MONTHLY_HOLD` (`registry.py:101`).
- SPY: `buy_and_hold` semantics with dividends.

---

## Dependencies

### Configuration / Environment / External Services
- `DATABASE_URL_UNPOOLED`, `MASSIVE_API_KEY` (repo secrets set). `LLM_API_KEY`, `LLM_BASE_URL`,
  `LLM_MODEL` are in `.env.local` but not repo secrets. `.env.local` also has `VERCEL_TOKEN`,
  `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`, `DATABASE_URL`, `AUTH_*`, `ALLOWED_EMAIL`; `vercel whoami` = miftahulmahfuzh.
- **Massive dividends (verified 2026-10-04 on the free key):** `GET /v3/reference/dividends?ex_dividend_date=2026-09-18&limit=1000`
  returned 513 rows in one page (505 `CD`, 8 `SC`), SPY `cash_amount` 1.888834. One call per session,
  like `splits(d)`.
- **Windowed bars load (measured from WSL to Neon):** `COPY ... WHERE date >= '2025-06-01'` 219,575 rows
  in 2.34 s; `>= '2024-10-01'` 326,410 rows in 2.73 s.
- Neon size 186 MB (bars 177 MB, every other table < 400 kB).

---

## Reference List

| Symbol / key | File:line | Kind | Package |
|---|---|---|---|
| `run_backtest` loop | engine/src/seer_engine/backtest/runner.py:171 | def (mirrored, not edited) | backtest |
| `run_book` loop | engine/src/seer_engine/backtest/book_runner.py:218 | def (mirrored, not edited) | backtest |
| `run_rules` | engine/src/seer_engine/backtest/book_runner.py:284 | call (replay check) | backtest |
| `_with_idle`, `_dividends_on`, `_gone`, `_invested` | engine/src/seer_engine/backtest/book_runner.py:108–161 | def (reused by import) | backtest |
| `buy_and_hold` | engine/src/seer_engine/backtest/benchmark.py:123 | def (mirrored; replay check calls it) | backtest |
| `step_book`, `close_book_unpriced` | engine/src/seer_engine/sim/book.py:445, 718 | call | sim |
| `apply_split` | engine/src/seer_engine/sim/split_adjust.py:113 | call (bracket) / mirrored (book) | sim |
| `size_picks`, `step`, `close_unpriced` | engine/src/seer_engine/sim/{sizing,lifecycle}.py | call | sim |
| `read_bars_frame` | engine/src/seer_engine/backtest/io.py:117 | def (gains a `since`) | backtest |
| `nightly._fetch` wanted set | engine/src/seer_engine/commands/nightly.py:154 | call site (held symbols added) | commands |
| `Client.splits` | engine/src/seer_engine/massive.py:841 | def (pattern for `dividends`) | engine |
| `apply_splits` `_REWRITE` | engine/src/seer_engine/splits.py:141 | def (dividends rewrite added) | engine |
| `DEMO_TABLES` | engine/src/seer_engine/demo.py:18 | config (new tables added) | engine |
| `runs.start_run`/`finish_run`/`fail_run` | engine/src/seer_engine/runs.py | def (paper status helpers added) | engine |
| `strategies` rows | db/migrations/001_init.sql:3 | schema (columns added) | db |
| `orders` | db/migrations/001_init.sql:30 | schema (`mark` column added) | db |
| `strategies()`, `positions()`, `closedTrades()`, `leaderboard()`, `runStatus()` | web/lib/data.ts | def | web |
| `checklist()` | web/lib/metrics.ts:47 | def (6th item) | web |
| `SLOT_*` | web/lib/slots.ts | def (book strategies skip slots) | web |
| `STRAT`, `STRAT_BTNS` hardcoded A/B/C | web/app/(app)/history/page.tsx:282–286 | config | web |
| `ICONS`, `CARD_BG`, `LINE` hardcoded A/B/C | web/app/(app)/leaderboard/page.tsx:382–384 | config | web |
| `champion()` used by Today/Positions | web/app/(app)/page.tsx, positions/page.tsx | call | web |
| seed strategies A/B/C/SPY | web/scripts/seed-demo.mjs:37 | data | web |
| nightly workflow steps | .github/workflows/nightly.yml | config | ci |
| CI (no lint) | .github/workflows/engine-ci.yml | config | ci |
| ROADMAP P0/P4/P5/v0.1.0 | docs/ROADMAP.md | doc | docs |
| readme "Simulator: P4 nightly", "Strategy: P4 nightly picks" | engine/package_readme.md:1423–1462 | doc | docs |

---

## Impact Points (files that WILL need changes)

1. `db/migrations/003_paper.sql` (new): strategies/orders/runs columns, `paper_state`, `book_positions`, `book_targets`, `book_fills`, `book_trades`, `dividends` — phase 1
2. `engine/src/seer_engine/paper/__init__.py`, `paper/roster.py` (new) and purity-test coverage — phase 1
3. `engine/src/seer_engine/demo.py` (`DEMO_TABLES`) — phase 1
4. `engine/src/seer_engine/sim/book.py`, `sim/__init__.py` (book split rule) — phase 2
5. `engine/src/seer_engine/paper/bracket.py`, `paper/benchmark.py` (new, pure) — phase 3
6. `engine/src/seer_engine/paper/book.py` (new, pure) — phase 4
7. `engine/src/seer_engine/massive.py`, `dividends.py` (new), `splits.py`, `commands/nightly.py` — phase 5
8. `engine/src/seer_engine/paper/store.py` (new), `backtest/io.py` (`since`) — phase 6
9. `engine/src/seer_engine/commands/paper.py` (new), `runs.py`, `.github/workflows/nightly.yml` (paper step) — phase 7
10. `engine/src/seer_engine/commands/paper_check.py` (new), `paper/replay.py` (new) — phase 8
11. `engine/src/seer_engine/commands/explain.py`, `llm.py` (new) — phase 9
12. `web/lib/data.ts`, `web/lib/metrics.ts`, `web/lib/monthly.ts` (new), `web/lib/slots.ts`, `web/scripts/seed-demo.mjs` and tests — phase 10
13. `web/app/(app)/page.tsx`, `positions/*`, `history/*`, new shared components — phase 11
14. `web/app/(app)/leaderboard/*` (monthly table, checklist switcher, roster colors) — phase 12
15. `.github/workflows/engine-ci.yml`, `.github/workflows/nightly.yml` (check + explain steps), `engine/pyproject.toml` (ruff), `docs/runbooks/paper-trading.md` (new), `docs/ROADMAP.md`, `engine/package_readme.md`, Vercel deploy — phase 13

**This document describes. The plan files prescribe.**

# Code Analysis: Fill simulator (roadmap P2) — `engine/src/seer_engine/sim/`

**Type:** Feature Implementation
**Date:** 2026-10-03 13:44 WIB
**Session ID:** 20261003-134417-F7S2
**Plan:** `ENGINE_FILL_SIMULATOR_PLAN.md` (4 phases)
**Worktree:** `/home/miftah/.worktrees/seer/engine-fill-simulator` on `feature/engine-fill-simulator` (base `HEAD` @ `b9780b8`; local `main` is 1 commit ahead of `origin/main`, the handover commit itself)

---

## User Input

### Original User Request

```
/analyze docs/handover/2026-10-03-fill-simulator.md
```

The argument is the specification. `docs/handover/2026-10-03-fill-simulator.md` is committed at
`b9780b8`, so it is part of the tree every phase works on. Its §2 goal, verbatim:

> Build the order-lifecycle and portfolio simulator in `engine/` as **pure, deterministic Python**:
> no database and no network in the core. **One code path** must serve both the 10-year backtest
> (P3) and nightly forward paper trading (P4). The ROADMAP calls this the critical path, and design
> §9 calls it "the highest-priority code in the repo".
>
> It must:
> 1. Take pending bracket orders through `pending → open → closed` or `pending → expired`, exactly
>    as in design §5 plus the decisions in §3 below.
> 2. Size orders with whole shares across 4 slots, using equity ÷ 4 recomputed daily.
> 3. Keep cash and equity per strategy portfolio, with 0.1% costs per side, and produce a
>    per-session equity snapshot.
> 4. Give P3/P4 a small API: advance a portfolio through one session's bars, report the events
>    (fill, expire, exit), and size new picks for the next session.
>
> **Done when:** every edge case in design §5 and in §3 below has a passing test on synthetic bars
> (ROADMAP P2), the full engine suite stays green with 0 skipped, and the API is documented in
> `engine/package_readme.md`.
>
> **Out of scope, don't build:** strategies and signals (P3), the backtest runner and report (P3),
> the SPY buy-and-hold benchmark curve (P3), writing to `orders`/`equity_snapshots` and wiring into
> `nightly` (P4), LLM explanations (P4), any web change.

Handover §3 (decisions, "do not reopen"), §4 (verified facts), §6 (acceptance criteria) and §7
(open questions) are binding input and are not repeated here; §7 is settled below under
"Settled open questions".

### User-Provided Context
- Design `docs/plans/2026-10-03-seer-design.md` §5 is law; §8 (splits → open orders recomputed;
  holidays → no day counted) and §9 (exhaustive synthetic-bar tests; one code path) apply.
- The repo is public; never `git push` / `gh secret set` without asking the owner.

### User-Provided Files
- `docs/handover/2026-10-03-fill-simulator.md`

### Requirement IDs

| ID | What the user asked for |
|---|---|
| R1 | Order lifecycle `pending → open → closed` / `pending → expired` exactly as design §5 + handover §3 (strict fill, open<limit fill at open, SL-first, gaps, time stop, expiry, holidays, missing bars) |
| R2 | Whole-share sizing across 4 slots with equity ÷ 4 recomputed daily, the cash cap, ineligible < 1 share, no adding to a holding, 0 picks valid |
| R3 | Cash and equity per portfolio with 0.1% cost per side, `pnl_usd` per closed trade, a per-session equity snapshot |
| R4 | A small pure API for P3/P4 (advance one session → events; size picks), deterministic, no DB/network imports (enforced), documented in `engine/package_readme.md`, with a ≥10-session hand-checked scenario |
| R5 | The pure split-recompute function for live orders (design §8; handover §4 "P2 provides the pure function; P4 calls it"), forward and reverse |

---

## Detailed Requirements Understanding

**Problem/Requirement Statement.** Nothing in `engine/` models orders or portfolios today. P1
built bars, calendar, universe, FX and `runs`. P2 adds a pure-Python, Decimal-only state machine:
a strategy portfolio holds cash and up to 4 live orders (one per slot); each NYSE session's bars
advance it through fills, exits, expiries and a mark-to-close; each night, ranked picks are sized
into free slots for the next session. P3 will loop this over ~2,950 sessions, and P4 will call it
once a night after loading state from `orders`, so the order state must map 1:1 onto the `orders`
columns.

**Success Criteria.** Handover §6 items 1–6: one test per rule (the 15-item edge-case list), a
determinism test, a ≥10-session hand-checked scenario, a purity test (no `psycopg`, `requests`,
`yfinance` in `sys.modules` after importing the core), a readme API section, and the full suite
green with 0 skipped (currently 216 tests).

**Key Considerations.**
- `seer_engine.bars` imports `psycopg` at module top (`bars.py:15`). Importing `Bar` from it puts
  `psycopg` into `sys.modules`, which fails acceptance #4. Measured: `import seer_engine.dates`
  leaves `psycopg`, `requests`, `yfinance` and `urllib3` absent; `import seer_engine.bars` loads
  `psycopg`. `Bar`, `to_decimal` and `PRICE_QUANTUM` must move to a module with no DB imports;
  `bars.py` re-exports them, so existing imports keep working.
- `Decimal` performance: 59,000 multiply+quantize ops took 0.028 s locally. A 10-year loop with 4
  slots is ~50k such ops, so floats are unnecessary.
- The calendar is the caller's job (P3 iterates `dates.sessions`; P4 knows `run_dates`). `dates`
  is import-clean, so the core may still validate `is_session`.
- `days_held` must agree with the demo seed and the UI: seed `web/scripts/seed-demo.mjs:122` uses
  `fill = back(days - 1)`, so the fill session is day 1, and `page.tsx:26` raises the day-5 action
  item at `day >= 5`.

**Assumptions** (each recorded as a decision in the plan index):
- Inputs are already split-adjusted `Bar`s keyed by symbol for one session; a symbol absent from
  the mapping has "no bar" that session.
- The portfolio holds only *live* orders (pending + open). Terminal orders (closed, expired) leave
  the portfolio and appear once, in the event that ended them, which is where P4 writes them.

---

## Analysis Scope

### Explicitly Mentioned Files
- `docs/handover/2026-10-03-fill-simulator.md`

### Discovered Related Files
- `docs/plans/2026-10-03-seer-design.md` (§5 rules, §8 failure handling, §9 testing)
- `docs/ROADMAP.md` (P2 section; P3/P4 consumers)
- `db/migrations/001_init.sql` (`orders`, `equity_snapshots` columns and checks)
- `engine/src/seer_engine/bars.py` (`Bar`, `to_decimal`, `PRICE_QUANTUM`, `make_bar`; imports psycopg)
- `engine/src/seer_engine/dates.py` (`sessions`, `is_session`, `next_session`, `prev_session`)
- `engine/src/seer_engine/splits.py` (`Split.factor` = split_to / split_from; DB-side history rescale)
- `engine/src/seer_engine/__init__.py` (version only, no imports)
- `engine/tests/conftest.py` (autouse env isolation; DB fixtures skip without `PG_TEST_URL`)
- `engine/tests/test_bars.py`, `test_dates.py` (test style: plain pytest functions, `D("…")` date helpers, parametrize)
- `engine/package_readme.md` (Exported API section, per-module subsections; "Performance" section)
- `.github/workflows/engine-ci.yml` (fails on any SKIPPED)
- `web/lib/data.ts` (reads `days_held`, `fill_price`, `exit_reason`, `pnl_usd`)
- `web/app/(app)/page.tsx:26` (`p.day >= 5` → day-5 action item)
- `web/app/(app)/history/page.tsx:16` (`gap` = "Gapped past stop at open"; `time` = "Time exit, day 5")
- `web/scripts/seed-demo.mjs:121-136` (pnl formula, days_held counting)

---

## Current Dataflow

There is no simulator dataflow yet. These are the existing flows the simulator sits between.

### Entry Point (upstream): bars in Neon
**Location:** `engine/src/seer_engine/bars.py` (`Bar`), `commands/backfill.py`, `commands/nightly.py`
**Data:** `Bar(symbol, date, open, high, low, close: Decimal(4dp), volume: int)`, split-adjusted
only. When a split executes, the nightly job rescales stored history by `factor = split_to / split_from`
(`splits.py:47`), so history is always consistent backwards in post-split units.

### Calendar
**Location:** `engine/src/seer_engine/dates.py`
`sessions(start, end)` (inclusive, ascending), `is_session(d)`, `next_session(d)`,
`prev_session(d)`. Half days are sessions. Holidays and weekends are not. `run_dates(now)` gives
`(data_date, session_date)`. It is the only wall-clock reader, and the simulator must not call it.

### Exit Point (downstream, P4): `orders` and `equity_snapshots`
**Location:** `db/migrations/001_init.sql`
- `orders`: `session_date, slot (1..4), symbol, company, last_price, limit_price, tp_price, sl_price numeric(12,4), shares int > 0, status in (pending, open, closed, expired), fill_date, fill_price, days_held int default 0, exit_date, exit_price, exit_reason in (tp, sl, time, gap), pnl_usd numeric(12,4)`; `UNIQUE (strategy_id, session_date, symbol)`.
- `equity_snapshots`: `(strategy_id, date) PK, cash_usd, equity_usd numeric(14,4)`.

### Readers (web, unchanged by P2)
- `positions()` (`data.ts:69`): `status='open'`, `days_held` → `day`; current = latest bar close.
- `closedTrades()` (`data.ts:89`): `status='closed'`, win = `pnl_usd > 0`.
- `leaderboard()`: equity curve from `equity_snapshots`, profit factor and win rate from closed `pnl_usd`.
- Demo seed pnl: `(ex − en) × sh − 0.001 × (ex + en) × sh` (`seed-demo.mjs:129`).

### Data Persistence
None in P2. The core is pure, and P4 persists its outputs.

---

## Key Data Structures

### `Bar` — `engine/src/seer_engine/bars.py:20`
Frozen, slotted dataclass: `symbol: str, date: date, open/high/low/close: Decimal, volume: int`.
Used in `bars.upsert_bars`, `yahoo`, `massive`, `commands/backfill.py`, `commands/nightly.py`,
and tests.

### `PRICE_QUANTUM = Decimal("0.0001")` and `to_decimal(x)` — `bars.py:17`, `bars.py:31`
Rounds half-up to 4 dp. Floats go through `repr`.

### `Split` — `splits.py:40`
`factor = split_to / split_from` (10 for a 10-for-1, 1/32 for a 1-for-32 reverse split).

---

## Dependencies

- Python 3.11, venv `engine/.venv`, pytest ≥ 8. No new third-party dependency is needed.
- `pandas_market_calendars` (via `dates`) is import-clean of the forbidden modules (measured).
- Tests: `PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q` after `docker start seer-pg`. The simulator tests need no DB, but the full suite does.

---

## Settled open questions (handover §7)

| Question | Settlement |
|---|---|
| API shape | New package `seer_engine/sim/`. Immutable frozen dataclasses (`Order`, `Portfolio`, `Event`, `Snapshot`) and pure functions: `step(portfolio, session_date, bars) -> StepResult(portfolio, events, snapshot)`; `size_picks(portfolio, picks, session_date) -> SizingResult(portfolio, placed, rejected)`; `apply_split(portfolio, symbol, factor) -> (portfolio, events)`; `close_unpriced(portfolio, symbols) -> (portfolio, events)`. Immutability makes determinism and P3 replays trivial, and Decimal makes the copying cost irrelevant at 4 slots. |
| Delisted / halted while held | No bar → no event that session, but the day still counts (`days_held` +1, marked at the last known close). A due time stop waits for the next available open. "No further bar ever" cannot be known by a pure step, so the caller decides it: `close_unpriced` exits at the last known close, reason `time`, `forced=True` on the event. A pending order with no bar expires. |
| Reverse-split rounding | `shares = floor(shares × factor)`. The fractional remainder is credited to cash at the adjusted last close (cash in lieu), with no cost and no `pnl_usd` effect. The amount is on the event. A pending order whose shares floor to 0 expires. |
| Performance | Keep `Decimal`. Phase 4 adds a benchmark test (2,950 sessions × 4 slots) with a generous bound and records the measured time in the readme. |

---

## Reference List

| Symbol / key | File:line | Kind | Package |
|---|---|---|---|
| `Bar` | `engine/src/seer_engine/bars.py:20` | def (moves to `prices.py`, re-exported) | seer_engine |
| `PRICE_QUANTUM` | `bars.py:17` | def (moves, re-exported) | seer_engine |
| `to_decimal` | `bars.py:31` | def (moves, re-exported) | seer_engine |
| `import psycopg` | `bars.py:15` | import (stays in `bars.py`) | seer_engine |
| `from seer_engine.bars import …` | `yahoo.py`, `massive.py`, `commands/backfill.py`, `commands/nightly.py`, `tests/test_bars.py` and others | call | seer_engine |
| `dates.is_session` / `sessions` | `dates.py` | used by sim core / tests | seer_engine |
| `Split.factor` | `splits.py:47` | convention the sim's `apply_split` factor must match | seer_engine |
| `orders.*` columns | `db/migrations/001_init.sql` | schema the `Order` fields mirror | db |
| `equity_snapshots.*` | `001_init.sql` | schema `Snapshot` mirrors | db |
| `days_held >= 5` | `web/app/(app)/page.tsx:26` | reader semantics | web |
| `exit_reason` labels | `web/app/(app)/history/page.tsx:16` | reader semantics | web |
| `### bars` API section | `engine/package_readme.md:147` | doc | engine |
| `## Performance` | `engine/package_readme.md:268` | doc ("no benchmark coverage") | engine |
| ROADMAP P2 | `docs/ROADMAP.md` | doc status line | docs |

## Impact Points (files that WILL need changes)

1. `engine/src/seer_engine/prices.py` (new): pure `Bar`, `PRICE_QUANTUM`, `to_decimal`. Phase 1
2. `engine/src/seer_engine/bars.py`: re-exports from `prices`. Phase 1
3. `engine/src/seer_engine/sim/__init__.py` (new): public surface. Phase 1 creates it; phase 4 adds the sizing and split exports
4. `engine/src/seer_engine/sim/model.py` (new): constants, `Order`, `Portfolio`, `Event`, `Snapshot`, `StepResult`, money helpers. Phase 1
5. `engine/src/seer_engine/sim/lifecycle.py` (new): `step`, `close_unpriced`. Phase 1
6. `engine/src/seer_engine/sim/sizing.py` (new): `Pick`, `Rejection`, `SizingResult`, `size_picks`. Phase 2
7. `engine/src/seer_engine/sim/split_adjust.py` (new): `apply_split`. Phase 3
8. `engine/tests/simkit.py` (new): synthetic bar and order builders. Phase 1
9. `engine/tests/test_sim_lifecycle.py`, `test_sim_purity.py` (new). Phase 1
10. `engine/tests/test_sim_sizing.py` (new). Phase 2
11. `engine/tests/test_sim_split.py` (new). Phase 3
12. `engine/tests/test_sim_scenario.py` (new): ≥10-session hand-checked scenario, determinism, benchmark. Phase 4
13. `engine/package_readme.md`: `sim` API section, layout, performance. Phase 4
14. `docs/ROADMAP.md`: P2 status line. Phase 4

**This document describes. The plan files prescribe.**

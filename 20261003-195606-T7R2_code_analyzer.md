# Code Analysis: trade rules as a value, a research store, and a wide dev-window strategy search (P7a)

**Type:** Feature Implementation
**Date:** 2026-10-03 19:56 WIB
**Session ID:** 20261003-195606-T7R2
**Plan:** `TRADE_RULES_DEV_SEARCH_PLAN.md` (13 phases)
**Worktree:** `/home/miftah/.worktrees/seer/trade-rules-dev-search`, branch `feature/trade-rules-dev-search` (base `origin/main` @ `2546a92`)

---

## User Input

### Original User Request

```
/analyze docs/handover/2026-10-03-trade-rules-revision.md
```

The handover file is the specification. It was committed at `2546a92` and is read in full by
every phase. Its binding parts, verbatim:

> The owner chose option **(c)**: revisit the design-§5 trade rules. The owner's words: *"open all
> options and approaches and possibilities and strategies … do not give up … let's take our time.
> slowly, but sure. there is no rush."*

> So yes, we are still trying to beat SPY buy-and-hold. Nothing in this handover lowers that bar.

> | D1 | **Split the work in two** | **P7a (this handover)** builds the machinery and explores **only on a development window**. It ends with a committed **pre-registration file** naming at most 3 finalists, each exactly specified. **P7b (a later handover)** runs those finalists **once** on the test window and applies the gate. P7a never runs a candidate on the test window |

> | D2 | **Rules as a value** | Introduce a `TradeRules` value carrying every §5 lever in §4.A. `TradeRules.DESIGN_V0` reproduces today's §5 exactly. The simulator and runner take it, and with `DESIGN_V0` they are **byte-for-byte unchanged in behaviour** … New behaviours (signal exits, rebalancing, dividends, fractional shares, market-on-open entries) are new code paths reached only through non-default rules |

Sections §3 (Law, What (c) opens, D1–D13, Owner inputs, Owner facts), §7 (acceptance) and §8
(open questions) are binding and are quoted where used in the plan index.

### User-Provided Context
- Three strategies have failed so far: A (P3), A2 (P3b), B (P6a). P4 stays blocked.
- The owner plans to put real money in on 2026-11-01. That conflicts with design §1, which is law.
  The handover says to report this conflict plainly and not to move §1.

### User-Provided Files
- `docs/handover/2026-10-03-trade-rules-revision.md`

### Requirement IDs

These are the nine acceptance items of handover §7.

| ID | What the user asked for |
|---|---|
| R1 | `TradeRules`: `DESIGN_V0` reproduces §5, and A, A2 and B re-render byte-identically (synthetic test plus a real-data `cmp`). Each new lever has its own synthetic-bar tests (signal exit, rebalance, dividends, fractional, market-on-open, slots ≠ 4, time stop ≠ 5 or none, vol-scaled sizing, idle T-bill) |
| R2 | Research data: a command builds a local research store (pre-2015 member bars, the L9 ETF set, dividends back to the start). It records what yfinance could not serve, per year. Nothing is written to Neon. It is deterministic and records a fingerprint |
| R3 | No look-ahead and P4 identity for every new strategy family; the prepared and single-window paths agree |
| R4 | The dev window is enforced in code: any session after 2015-10-16 is rejected, and a test proves it |
| R5 | The candidate registry is committed before the dev runs, append-only, ≤ 60 entries. Each entry has a family, `TradeRules`, fixed parameters, a rationale and a `needs-owner-verification` flag |
| R6 | One dev run over every registry candidate. The committed report has: every candidate's row, the SPY curves, year by year for the top candidates, exposure, turnover and cost drag, the survivorship table, the trial count with a multiple-testing note, and the D8 finalist rule applied |
| R7 | The pre-registration file `docs/plans/<date>-p7b-preregistration.md`, naming each finalist exactly (or "none eligible") and the proposed §5 revision |
| R8 | Determinism and purity: `==` results and byte-identical files on a re-run; the new pure modules pass the purity glob |
| R9 | Docs: `engine/package_readme.md` and the ROADMAP P7a and P7b entries. The suite is green with 0 skipped, and CI is green |

---

## Detailed Requirements Understanding

**Problem/Requirement Statement.** Design §5's trade shape (4 equal slots, whole shares, a
dip-limit bracket, a 5-day time stop, idle cash earning nothing, no dividends) is hard-wired into
`seer_engine.sim`:
- `SLOTS = 4`, `TIME_STOP_DAYS = 5` and `COST_RATE` are module constants in `sim/model.py:35-37`;
- `Order` validates `slot <= SLOTS`, and `Portfolio` validates `len(orders) <= SLOTS`;
- `size_picks` sizes at `equity / SLOTS`.

The simulator has no notion of selling a position for any reason other than TP, SL, a gap, the
time stop or a forced close. It has no dividends, no fractional shares and no market entry. The
only strategy interface is `Strategy.picks -> list[Pick]`, which returns brackets.

P7a has to do four things:
1. Turn those rules into a value.
2. Add the execution paths that rebalance, signal-exit and income strategies need.
3. Assemble a never-seen 1993 → 2015-10-16 dataset, locally.
4. Run a pre-registered, bounded registry of candidates on that window only, then pick ≤ 3
   finalists by a rule written before any result.

**Success criteria.** Every item in handover §7 (R1–R9) holds. A, A2 and B behave exactly as
before. No P7a artefact contains a number computed on a session after 2015-10-16.

**Key considerations.**
- *Byte-identity of the closed records* is cheapest to guarantee by not touching their code path
  at all: no edit to `sim/model.py`, `lifecycle.py`, `sizing.py`, `runner.py` or the reports. New
  rules get a separate engine, and `DESIGN_V0` is dispatched to the untouched `run_backtest`.
- *The handover's lever list mixes execution levers with selection levers.*
  - Execution levers are cadence, entry type, time stop, fractional shares, dividends, idle cash
    and cost.
  - Selection levers are slots, sizing, universe, the exposure switch and vol targeting.
  - The selection levers depend on history, so they belong to the strategy (allocator) side.
- *Trade counting under rebalancing.* §1 counts "closed trades". A monthly single-ETF switcher
  makes only tens of round trips in 20 years, so D8's ≥ 100-trade rule excludes it by
  construction. This is law, not something to tune around. The report must say so.
- *Survivorship on the dev window is severe* for single stocks:
  - yfinance has no delisted tickers;
  - tickers that were reused can silently map an old member to a different company.

  The report must state both. ETF candidates are unaffected.
- *FX.* Frankfurter publishes USD/IDR from 1999-01-04 (verified by request, 8002 IDR per USD).
  The dev window starts earlier (SPY from 1993), so the starting-capital conversion needs a rule.
  It only affects the conversion, never a decision.

**Assumptions** (each one is recorded as a Decision in the plan index):
1. Sale proceeds at an open can fund buys at the same open.
2. A "market-on-open" entry is executed as a marketable limit at last close + 2%. That is a limit
   order, so it needs no owner verification.
3. "No TP" is executed in Gotrade as a bracket with a far take-profit.
4. Dividends credit cash on the ex-date to the holder at the previous close.

---

## Analysis Scope

### Explicitly Mentioned Files
- `docs/handover/2026-10-03-trade-rules-revision.md`

### Discovered Related Files
- `engine/src/seer_engine/sim/model.py`: constants, `Order`, `Portfolio`, `buy_cost`, `sell_proceeds`, `q`
- `engine/src/seer_engine/sim/lifecycle.py`: `step`, `close_unpriced`, `_exit_on_bar`
- `engine/src/seer_engine/sim/sizing.py`: `Pick`, `size_picks`, `_whole_shares`
- `engine/src/seer_engine/sim/split_adjust.py`: `apply_split` (live path only; the backtest bars are pre-adjusted)
- `engine/src/seer_engine/sim/__init__.py`: the exports
- `engine/src/seer_engine/strategies/base.py`: `History`, `Strategy` protocol, `as_day`
- `engine/src/seer_engine/strategies/a.py`, `a2.py`, `b.py`, `indicators.py`
- `engine/src/seer_engine/backtest/runner.py`: `run_backtest`, `ParamsSchedule`, `survivorship`, `INITIAL_IDR`
- `engine/src/seer_engine/backtest/market.py`: `Market`, `Membership`
- `engine/src/seer_engine/backtest/benchmark.py`: `spy_curves`, `buy_and_hold`, `Dividend`, `parse_dividends`
- `engine/src/seer_engine/backtest/metrics.py`: `strategy_metrics`, `cagr_between`, formatters, `checklist`
- `engine/src/seer_engine/backtest/io.py`: `load_market`, `histories_from_frame`, `merge_intervals`, writers
- `engine/src/seer_engine/backtest/wf_report.py`: `_chart` (the SVG line chart reused by B)
- `engine/src/seer_engine/membership.py`: `compute_universe` (offline, from the vendored CSVs)
- `engine/src/seer_engine/yahoo.py`: `yf_download` (`auto_adjust=False`, `actions=False`), `parse_frame`
- `engine/src/seer_engine/fx.py`: `fetch_range` (Frankfurter, one request per year)
- `engine/src/seer_engine/dates.py`: NYSE calendar (`pandas_market_calendars`)
- `engine/src/seer_engine/commands/backfill.py`, `backtest.py`, `backtest_wf.py`, `backtest_b.py`, `cli.py`
- `engine/tests/test_strategy_purity.py`, `test_sim_purity.py`, `stratkit.py`, `simkit.py`
- `engine/data/sp500_history.csv` (from 1996-01-02), `ndx_history.csv` (from 2007-02-01), `spy_dividends.csv` (from 2015-03-20)
- `docs/plans/2026-10-03-seer-design.md` §1, §2, §5; `docs/ROADMAP.md`; `engine/package_readme.md`

---

## Current Dataflow

### Entry Point: `run_backtest(market, strategy, params, start, end, *, prepared=None)`

**Location:** `engine/src/seer_engine/backtest/runner.py:146`
**Trigger:** called by `commands/backtest.py`, `backtest_wf.py`, `backtest_b.py`, `walkforward.walk_forward`, `b_walkforward.walk_forward_b`
**Input:** a `Market`, a `Strategy`, params (or a `ParamsSchedule`), and NYSE-session `start`/`end`

**Processing chain, per session S:**
1. `members = market.membership.members_on(data_date)`, where `data_date = prev_session(S)`.
2. `picks = strategy.picks_prepared(prepared, members, data_date, params)`, or `picks(history.upto(data_date), …)`.
3. `sim.size_picks(pf, picks, S)` (`sizing.py:679`):
   - slot budget `q(equity / SLOTS)`;
   - budget `min(slot, cash − committed)`;
   - whole shares `floor(budget / (limit × 1.001))`;
   - rejections are `held`, `no_slot` and `lt_one_share`;
   - picks are taken in rank order, and each takes the lowest free slot.
4. `sim.step(pf, S, market.bars_on(S, pf.held_symbols()))` (`lifecycle.py:448`):
   - open positions, in slot order:
     - time stop (`days_held >= 5`) → exit at the open, `time`;
     - gap `open <= sl` → exit at the open, `gap`; `open >= tp` → exit at the open, `tp`;
     - intraday `low <= sl` → exit at sl, `sl`; else `high > tp` → exit at tp, `tp`;
     - otherwise `days_held + 1` and mark at the close;
   - pending orders: fill when `low < limit` at `min(open, limit)`, with `days_held = 1`; otherwise expire;
   - snapshot `q(cash + Σ shares × mark)`.
5. Any open symbol whose `last_bar_date < S` → `close_unpriced` (exit at its mark, `time`, `forced=True`), and the snapshot is replaced.

**Exit:** `RunResult(snapshots, events, closed, open_at_end, rejections, initial_cash, usd_idr)`.

Money is `Decimal` at 4 dp throughout the sim. Cost is `COST_RATE = 0.001` per side, inside
`buy_cost` and `sell_proceeds`. Floats exist only in strategy features and metrics.

### Benchmark: `benchmark.spy_curves(spy, start, end, cash0, dividends)`
**Location:** `backtest/benchmark.py:737`. It buys whole SPY shares at `start`'s open. On every
ex-date it credits `q(shares × amount)` and reinvests at that close. It raises when any session
in the window has no SPY bar. Its dividends come from `engine/data/spy_dividends.csv`, which
starts 2015-03-20, so it is **not usable for a pre-2015 window** without another source.

### Data loading: `backtest.io.load_market(conn)`
**Location:** `backtest/io.py:258`.
- It streams `bars` by `COPY` into a pandas frame, cached as a pickle under `engine/.cache/` and
  keyed by `count(*)` and `max(date)`.
- It reads the `universe` intervals and `fx_rates`.
- It builds `History` per symbol and `Membership`.
- Neon `bars` holds 2015-01-02 → 2026-10-02 only. `Market` itself is a pure in-memory value and
  can be built from any source.

### Membership: `membership.compute_universe(data_dir)`
**Location:** `membership.py:278`. It is pure file parsing of the vendored CSVs: snapshots,
overrides and aliases → `Interval`s. Neon's `universe` table is exactly its output, so a research
`Membership` can be built offline: `Membership(intervals=io.merge_intervals(...))`.

### Price convention: `yahoo.yf_download`
**Location:** `yahoo.py:73`. It uses `auto_adjust=False` and `actions=False`, so prices are
split-adjusted and **not** dividend-adjusted, stored at 4 dp. Dividends are not fetched today.
`yf.download(actions=True)` adds `Dividends` and `Stock Splits` columns to the same frame.

### Purity enforcement
- `tests/test_strategy_purity.py` globs `strategies/*.py` and `backtest/*.py`, except
  `backtest/io.py`. It forbids psycopg, requests, yfinance, `seer_engine.bars`, time, random,
  logging, `.now`, `.random`, `print` and `open`.
- `tests/test_sim_purity.py` does the same for `sim/*.py`.
- Sub-packages are **not** globbed.

### Exit Points
- `docs/backtests/<stem>.md/.csv/.svg` through `io.write_*`.
- Logs.
- Nothing is written to Neon by any backtest.

---

## Key Data Structures

| Struct | Location | Notes |
|---|---|---|
| `Order` | `sim/model.py:113` | int `shares`; `slot` in 1..`SLOTS`; the exit reasons `tp`/`sl`/`time`/`gap` |
| `Portfolio` | `sim/model.py:187` | at most `SLOTS` live orders; `marks` cover the open symbols exactly |
| `Pick` | `sim/sizing.py:618` | `sl < limit < tp`, all 4-dp Decimal |
| `History` | `strategies/base.py:34` | float64 arrays, `datetime64[D]` dates, `upto(d)`, `index_of(d)` |
| `Strategy` | `strategies/base.py:119` | `id`, `lookback`, `picks`, `prepare`, `picks_prepared`, plus the P4-identity contract |
| `Market` | `backtest/market.py:94` | `history`, `membership`, `fx`, `bar`, `bars_on`, `last_bar_date`, `usd_idr_on`, `spy` |
| `RunResult` | `backtest/runner.py:47` | snapshots, events, closed, open_at_end, rejections |
| `Metrics` | `backtest/metrics.py:38` | total_return, win_rate, profit_factor, max_drawdown, trades, months, cagr, … |
| `BenchmarkCurve` | `backtest/benchmark.py:598` | snapshots, shares, cash, dividends_usd |

---

## Dependencies

- **Configuration:** `SEER_ENV_FILE`, `DATABASE_URL_UNPOOLED` (only for Neon-backed commands).
  `config.REPO_ROOT`.
- **External, verified 2026-10-03:**
  - yfinance (bars back to the 1990s for survivors; ETFs from launch; no delisted tickers).
  - Frankfurter `api.frankfurter.dev/v1`: USD/IDR from **1999-01-04** (8002).
- **Python:** 3.11. numpy, pandas, pandas_market_calendars, yfinance, scikit-learn 1.9. **No
  pyarrow**, so parquet is not available without a new dependency.
- **Test baseline:** 970 tests collected on `2546a92` in a fresh worktree venv. The main
  checkout's `engine/.venv` lacks scikit-learn (8 collection errors), which confirms the memory
  rule that a worktree needs its own venv.

---

## Reference List

| Symbol / key | File:line | Kind | Package |
|---|---|---|---|
| `SLOTS`, `TIME_STOP_DAYS`, `COST_RATE` | `sim/model.py:35-37` | def | sim |
| `SLOTS` | `sim/model.py:140,213,254`; `sim/sizing.py:708` | call | sim |
| `TIME_STOP_DAYS` | `sim/lifecycle.py:409` | call | sim |
| `COST_RATE` | `sim/model.py:93,101`; `sim/sizing.py:602`; `backtest/benchmark.py:656`; `backtest/labels.py:47` (tested equal) | call | sim, backtest |
| `run_backtest` | `backtest/runner.py:146` | def | backtest |
| `run_backtest` | `walkforward.py`, `b_walkforward.py`, `commands/backtest*.py`, `tests/test_backtest_runner.py`, … | call | backtest, commands |
| `Strategy` protocol | `strategies/base.py:119` | def | strategies |
| `spy_curves` | `backtest/benchmark.py:737` | def | backtest |
| `INITIAL_IDR` | `backtest/runner.py:41` | def | backtest |
| `survivorship` | `backtest/runner.py:236` | def | backtest |
| `compute_universe` | `membership.py:278` | def | root |
| `merge_intervals` | `backtest/io.py:351` | def | backtest (impure module, pure function) |
| `yf_download` | `yahoo.py:73` | def | root |
| `fx.fetch_range` | `fx.py:31` | def | root |
| `IMPURE = {("backtest","io.py")}` | `tests/test_strategy_purity.py:24` | test | tests |
| `engine/.cache/` | `.gitignore` | config | — |
| design §5 | `docs/plans/2026-10-03-seer-design.md:84-102` | doc | docs |

---

## Impact Points (files that WILL need changes)

New files (by owning phase):
1. `sim/rules.py`, `sim/book.py`, and `tests/test_sim_rules.py` and `tests/test_sim_book.py` (phase 1).
2. `strategies/allocator.py` and `tests/test_allocator.py` (phase 2).
3. `backtest/book_runner.py` and `tests/test_book_runner.py` (phase 3).
4. `seer_engine/research.py`, `commands/research_store.py` and `tests/test_research_store.py` (phase 4).
5. `strategies/f_index.py` (phase 5), `strategies/f_rotation.py` (phase 6),
   `strategies/f_factor.py` (phase 7) and `strategies/f_swing.py` (phase 8), each with its test.
6. `backtest/dev.py` (phase 9) and `backtest/dev_report.py` (phase 10), each with its test.
7. `backtest/registry.py` and `tests/test_registry.py` (phase 11).
8. `commands/backtest_dev.py` and `tests/test_backtest_dev_command.py` (phase 12).
9. `docs/backtests/<run date>-p7a-dev-exploration.*` and `docs/plans/<date>-p7b-preregistration.md` (phase 13).

Additive edits:
- `sim/__init__.py` exports (phase 1).
- `strategies/indicators.py`: new functions only (phase 2).
- `yahoo.py`: a dividends-aware download (phase 4).
- `.gitignore`: `engine/.research/` (phase 4).
- `backtest/io.py`: `write_dev_report` (phase 12).
- `engine/package_readme.md` and `docs/ROADMAP.md` (phase 13).

**This document describes. The plan files prescribe.**

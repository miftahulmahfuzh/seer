# Code Analysis: the measuring tape (resize band, idle-cash interest, survivorship data) and a tree ranker

**Type:** Feature Implementation (engine levers + data + two lab methods)
**Date:** 2026-10-12 20:55 WIB
**Session ID:** 20261012-205553-M7T1
**Plan:** `MEASURE_THEN_LEARN_PLAN.md` (7 phases)
**Worktree:** `/home/miftah/.worktrees/seer/measure-then-learn`, branch `feature/measure-then-learn` (base `origin/main` @ `5faa3cb`)

---

## User Input

### Original User Request
> Read docs/plans/HANDOVER_20261012-measure-then-learn.md and plan and build its leftover tasks (Step 0 then Step 1).

### User-Provided Context
The handover `docs/plans/HANDOVER_20261012-measure-then-learn.md` (committed at `5faa3cb`) is the
specification. Its §2 leftover tasks, verbatim headings:

- Step 0, the measuring tape (do first): 1. resize band measured against the whole account;
  2. interest on idle cash; 3. survivorship check data restored on this machine; 4. re-price the
  near misses under the fixed tape, as new pre-registered variation twins, and answer Sera's
  question (picking or equal-weight shape?).
- Step 1, one tree ranker in the lab: 5. a new method family, gradient-boosted trees, walk-forward
  retrains inside the dev window only, fixed seed, target = forward 1-month return rank, features
  only from what is already computed and point-in-time, monthly top-N long-only book at Gotrade fees
  in fractional shares on the owner's real funding plan, every hyperparameter setting counts, never
  touch the test window. 6. a small neural net only if the trees show something (conditional).
  7. daily inference, designed only once a method passes the dev gate (conditional).
- Owner side: 8. the owner runs `/calculate-assets` by hand.

Also binding: lab sqlite insight 211 (the Sera 20261012-1842 synthesis) and insight 208 (M0117,
"the check that adds back the companies that died is missing from this machine").

### User-Provided Files
- `docs/plans/HANDOVER_20261012-measure-then-learn.md`

### Requirement IDs

| ID | What the user asked for |
|---|---|
| R1 | Step 0.1: measure the resize band against the holding's own target, without changing any past result, with an explicit decision on paper and the `web/` mirror |
| R2 | Step 0.2: interest on idle cash, as a versioned, explicit simulator input built from the cached T-bill yields |
| R3 | Step 0.3: make the survivorship check runnable on this machine, pulling what EODHD still offers before the key expires 2026-11-10 |
| R4 | Step 0.4: re-price the near misses (M0030-SAT100, M0007-N20-RAW, M0021-B70-RAW, M0020-W-NOSTOP) under the fixed tape as new pre-registered twins, and answer "picking or shape?" |
| R5 | Step 1.5: one pre-registered gradient-boosted-tree cross-sectional ranker in the lab, run on the dev window |

Items 6, 7 and 8 are conditional or owner-side; they are out of scope (see the plan index).

---

## Detailed Requirements Understanding

**Problem.** Three properties of the simulator/data bias every lab result:
1. `sim/book.py` trims and adds only when the share gap × last price ≥ `RESIZE_BAND × equity`
   (1% of the whole account). In a 20–50 name book a holding must drift 50–100% of its own target
   before anything trades, so "resize" rules are near no-ops and weekly-vs-monthly arms measured
   little.
2. Idle cash earns nothing (`backtest/dev.py:269` says so). Rules that step aside and every
   deposit waiting ~4 sessions for the month-start rotation are under-credited.
3. The survivorship check (`lab survivorship`) could not run in the Sera worktree that ran M0117.

Then the four near misses must be re-measured as new twins, and a tree ranker built and run.

**Success criteria.**
- New `TradeRules` levers exist whose default values leave every recorded digest, every pinned
  paper spec digest and every closed record byte-identical.
- A lab run can choose "band relative to target" and "idle cash earns the 13-week T-bill yield".
- `lab survivorship` runs from any worktree on this machine, the sv store matches the current dev
  store, and the EODHD alias top-up is fetched before 2026-11-10.
- A twin method of the near misses is pre-registered, run on the dev window, survivorship-checked,
  noted, staged, with a plain-words answer to "picking or shape".
- A tree-ranker method is pre-registered, run on the dev window, noted, staged; the test window
  is never touched.

**Assumptions.** Recorded as Decisions in the plan index.

---

## Analysis Scope

### Explicitly Mentioned Files
- `docs/plans/HANDOVER_20261012-measure-then-learn.md`
- `engine/src/seer_engine/sim/book.py:561`, `:617` (and `:654`, the add path)

### Discovered Related Files
- `engine/src/seer_engine/sim/rules.py` — `TradeRules`, `RESIZE_BAND`, presets, `LEVERS_SINCE_PINS`, `describe_rules`, `rule_owner_inputs`
- `engine/src/seer_engine/sim/__init__.py:71,106` — re-exports `RESIZE_BAND`
- `engine/src/seer_engine/backtest/book_runner.py:246-380` — `run_book`, the lab's session loop; calls `step_book` at :373
- `engine/src/seer_engine/paper/book.py:419` — live paper calls the same `step_book`
- `engine/src/seer_engine/backtest/registry.py:325-331` — `_canon`, which omits pinned-default levers
- `engine/src/seer_engine/paper/roster.py:1392-1411` — `rules_dict`/spec digest, also omits pinned-default levers; `SEED_ROWS` :904
- `engine/src/seer_engine/backtest/dev.py:175-215,269` — `Candidate`, owner inputs, "idle cash earns nothing"
- `engine/src/seer_engine/backtest/market.py:189-209,343` — `MarketSeries.value_on`, `Market`
- `engine/src/seer_engine/research.py:81,151-153,205,1138,1320` — store dirs, `MARKET_SERIES_NAMES`, sv purpose, series refresh, load
- `engine/src/seer_engine/commands/market_series.py:43,104,117` — `T13W` from EODHD `IRX.INDX`
- `engine/src/seer_engine/lab/survivorship_check.py`, `commands/lab.py:380-400`, `commands/survivorship_store.py`, `survivorship.py`, `survivorship_alias.py`, `eodhd.py`
- `engine/src/seer_engine/lab/method.py`, `lab/runner.py`, `lab/store.py`, `lab/npolicy.py`, `lab/hardgate.py`, `lab/real_costs.py`
- `engine/src/seer_engine/lab/methods/m0007_residual_momentum.py`, `m0011_raw_residual_own_vol.py`, `m0020_stop_with_weekly_reentry.py`, `m0021_momentum_lowvol_blend.py`, `m0030_spy_core_momentum_satellite.py`, `m0029_blend_fractional.py`, `m0119_deposit_deployment.py`, `m0120_calendar_clock.py`
- `engine/src/seer_engine/strategies/allocator.py`, `f_factor.py`, `f_fundamental.py`, `indicators.py`, `b_model.py`, `b.py`
- `engine/tests/test_sean_mirrors.py`, `engine/tests/test_sim_rules.py:70`, `engine/tests/test_paper_roster.py` (PINS), `engine/tests/allocatorkit.py`, `engine/tests/test_strategy_purity.py`, `engine/tests/test_lab_methods.py`
- `web/lib/cadence.ts:73,92`, `web/lib/sean/reminders.ts:326` (`RESIZING_RULES`), `web/app/(app)/positions/page.tsx:608`
- `.claude/skills/explore-and-experiment-new-method/SKILL.md:31,244-259`, `.claude/skills/sera-the-explorer/SKILL.md:29`, `.claude/skills/redo-sera-experiments/SKILL.md`

---

## Current Dataflow

### Entry point: `lab run MNNNN` (`commands/lab.py:193`, `_run` :1437 → `lab/runner.py`)
1. `runner.preflight` (:225) refuses an uncommitted or already-run method file, a candidate that
   already has a dev trial, and (`real_costs.real_cost_problem`, M0031 on) any candidate that is
   not `engine="book"` with `cost_model="gotrade"`.
2. `preflight_data` (:336) checks `market_fields`, fundamentals coverage.
3. `dev.run_registry(..., contributions=OWNER_MONTHLY, initial_idr=capital)` (:621) runs each
   candidate through `backtest/book_runner.run_book`.
4. `trial_rows` (:428) computes DSR with `n = store.pending_gate(...).n` (`DSR_POLICY="methods"`:
   `npolicy.effective_n` = max(distinct methods with a dev trial, ceil(participation ratio))). Variants
   of one method add 0 to N but raise `var_trials`.
5. One transaction inserts trials, funding, moments and provenance rows, sets status
   `dev-eligible`/`rejected`.

### Processing chain: `run_book` (`backtest/book_runner.py:246`)
Per NYSE session S:
1. `credit_for(contributions, data_date, S, rate)` adds the 25th-of-month deposit at the open.
2. On `is_rank_session(rules, S)` (or a resize-only session) the allocator returns targets from
   history ≤ `prev_session(S)`. `_with_idle` (:190) adds `1-Σw` in `rules.idle_symbol` if set,
   otherwise the residual stays cash.
3. `step_book(book, S, bars, targets, rules, divs, idle_symbol_ok=...)` (:373).

### `step_book` (`sim/book.py:486-757`)
- Night plan (:550-563): planned sells for dropped names, and trims where
  `excess * t.last >= RESIZE_BAND * equity` (:561).
- (1) dividends credited to cash (:565-576).
- (2) open exits; (3) trims at the open, skipped when `excess * t.last < RESIZE_BAND * equity` (:617);
  (4) buys, adds skipped when `gap * t.last < RESIZE_BAND * equity` (:654); (5) intraday SL/TP;
  (6) age and mark; (7) snapshot `q(cash + Σ shares × mark)`.
- Cash is never credited anything except dividends and sale proceeds.

### Canonical text and digests
- `TradeRules` (`sim/rules.py:79-93`): `id, engine, cadence, resize_cadence, entry, max_positions,
  time_stop, resize, fractional, dividends, idle_symbol, cost_rate, cost_model`.
- `LEVERS_SINCE_PINS` (:247-255) maps a lever added after pins to its no-op default;
  `backtest/registry._canon` (:325-331) and `paper/roster.rules_dict` (:1392-1404) omit a field at
  that value, so neither lab config digests nor paper spec digests move.
- `RESIZE_BAND` is a module constant, in no digest. Changing it would silently change live paper
  and every re-run.

### Survivorship check
- `lab survivorship MNNNN` (`lab/survivorship_check.py`) re-runs recorded dev variants on the dev
  store and on the sv store (`research.SV_STORE_DIR = REPO_ROOT/engine/.research-sv`, research.py:81).
  `--sv-store` defaults to that path with **no env fallback** (`commands/lab.py:393-396`), while
  `--store` honours `$SEER_RESEARCH_STORE`. `REPO_ROOT` resolves under whatever checkout the code
  runs from, so in a Sera worktree the default points at a missing dir.
- On this machine the main checkout has `engine/.research-sv/` (built 2026-10-10 20:21, purpose
  `survivorship-check`, 989/1061 served) and the EODHD cache `engine/.cache/eodhd/`
  (`eod/` 522 files, `alias/`, `dividends/`, `splits/`, `market/`, `symbols-US-delisted.json`,
  `symbols-US-live.json`). The dev store was rebuilt later (20:56); their
  `dividend_announcements.csv` shas differ.
- Build: `python -m seer_engine survivorship_store --build [--out] [--source] [--cache]`, offline;
  `--fetch-aliases` is the one network path (`survivorship_store.py:445-520`).
- EODHD token `EODHD_API_TOKEN` (in `.env.local`), valid to 2026-11-10 (memory note).

### Cash-rate data
- `engine/.research/market_series.csv` holds series `T13W` (13-week T-bill yield, percent, from
  EODHD `IRX.INDX`), 5,722 rows 1993-01-29..2015-10-16. Read point-in-time through
  `market.series.value_on("T13W", d)`. Nothing reads it for cash accrual today.
- `engine/.research-test/` has no `market_series.csv`.

### Live paper
- Roster in `paper/roster.py:SEED_ROWS`: active rules ids `benchmark`, `design-v0-gotrade`,
  `monthly-rank-weekly-resize-frac-gotrade`, `monthly-hold-frac-gotrade` (×3). Spec digests pinned
  in `engine/tests/test_paper_roster.py`.
- `paper/book.py:419` steps the book with the same `step_book`.

### Web mirrors
- `web/lib/cadence.ts:73` `RESIZE_BAND = 0.01` used by `sizeChange` (:92) and
  `web/lib/sean/reminders.ts:326`. `engine/tests/test_sean_mirrors.py` guards exactly four mirrors
  (`RESIZE_BAND`, `RESIZING_RULES` = every `PRESETS` entry with `engine=="book" and resize`,
  `OWNER_MONTHLY`, `OWNER_USD_IDR`); `test_every_mirror_is_covered` asserts that set.

### Existing ML code
- `strategies/b_model.py`: `HistGradientBoostingRegressor` with fixed `TREE_PARAMS`, model digest,
  `fit_tree(X, y, threads=...)` under `threadpool_limits`; sklearn pinned `>=1.9,<1.10`. Strategy B
  was a daily bracket ranker on design-v0 (one round only, closed record). LightGBM is not installed.
- Feature code: 12-1 momentum and volatility in `strategies/f_factor.py` / `indicators.py`;
  residual momentum in `lab/methods/m0007_residual_momentum.py` (`build_grid`, `residual_scores`);
  52-week-high `nearness` in `m0015_52week_high.py`; dividend events in `m0070_dividend_raise_drift.py`
  (`classify`, `live_event`); fundamentals in `strategies/f_fundamental.py` (point-in-time by
  `filed`). The dev store has `fundamentals.csv`.

---

## Key Data Structures

- `TradeRules` — `sim/rules.py:79`
- `Target` — `sim/book.py:153`; `Book` :226; `BookStep` :300 (`book, fills, trades, dividends, rejected, snapshot`)
- `Candidate` — `backtest/dev.py:175` (`id, family, rules, allocator, params, rationale, added, owner_inputs`)
- `Method` / `Amendment` — `lab/method.py:117` / `:56`; `config_digest` :44-53
- `Allocator` protocol — `strategies/allocator.py:57`; `MarketAware.prepare_market` :99
- `MarketSeries` — `backtest/market.py:189`

---

## Reference List

| Symbol / key | File:line | Kind | Package |
|---|---|---|---|
| `RESIZE_BAND` | sim/rules.py:43 | def | engine sim |
| `RESIZE_BAND` | sim/book.py:20,60,561,617,654 | call/doc | engine sim |
| `RESIZE_BAND` | sim/__init__.py:71,106 | export | engine sim |
| `RESIZE_BAND` | sim/rules.py:427 (describe_rules) | doc | engine sim |
| `RESIZE_BAND` | tests/test_sean_mirrors.py:40,48,88-89,130; tests/test_sim_rules.py:70 | test | engine |
| `RESIZE_BAND` | web/lib/cadence.ts:73,92; web/lib/sean/reminders.ts:326; web/app/(app)/positions/page.tsx:608 | mirror | web |
| `LEVERS_SINCE_PINS` | sim/rules.py:247; backtest/registry.py:325-331; paper/roster.py:1396-1411 | def/call | engine |
| `PRESETS` | sim/rules.py:194; tests/test_sean_mirrors.py (RESIZING_RULES) | def/test | engine/web |
| `step_book(` | sim/book.py:486; backtest/book_runner.py:373; paper/book.py:419 | def/call | engine |
| `describe_rules` idle-cash line | sim/rules.py (Idle cash line) | doc | engine |
| `rule_owner_inputs` | sim/rules.py; backtest/dev.py:69,180 | def/call | engine |
| `--sv-store` default | commands/lab.py:393-396 | config | engine |
| `SV_STORE_DIR` | research.py:81 | def | engine |
| `T13W` | commands/market_series.py:43,104; research.py:151 | config | engine |
| sv path in skills | .claude/skills/explore-and-experiment-new-method/SKILL.md:31,244-259; sera-the-explorer/SKILL.md:29 | doc | skills |

---

## Impact Points (files that WILL need changes)
1. `engine/src/seer_engine/sim/rules.py` — new `resize_basis` lever + `TARGET_RESIZE_BAND` (P1); `cash_yield` lever (P2); new presets (P3)
2. `engine/src/seer_engine/sim/book.py` — band by basis (P1); interest accrual (P2)
3. `engine/src/seer_engine/sim/__init__.py` — exports (P1, P2)
4. `engine/src/seer_engine/backtest/book_runner.py` — pass the cash rate (P2)
5. `engine/src/seer_engine/backtest/dev.py` — the "idle cash earns nothing" docstring / owner inputs (P2)
6. `engine/src/seer_engine/paper/book.py`, `commands/promote.py` — refuse cash-yield rules on paper (P2)
7. `engine/tests/test_sim_rules.py`, `test_sim_book*.py`, `test_book_runner*.py`, digest/pin tests (P1, P2)
8. `web/lib/cadence.ts`, `web/lib/sean/reminders.ts`, tests, `engine/tests/test_sean_mirrors.py` (P3)
9. `engine/src/seer_engine/commands/lab.py`, `research.py` — `SEER_SV_STORE` (P4); skills docs (P4); sv store rebuild + alias top-up (P4, data)
10. `engine/src/seer_engine/lab/methods/mNNNN_*` near-miss twin method + lab.sqlite + web/data/lab.json (P5)
11. new tree-ranker module + tests (P6); `lab/methods/mNNNN_*` ranker method + lab rows (P7)

**This document describes. The plan files prescribe.**

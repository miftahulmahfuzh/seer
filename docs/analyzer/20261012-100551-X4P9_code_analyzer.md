# Code Analysis: the lab exposure diagnostic (handover §4.1)

**Type:** Feature Implementation
**Date:** 2026-10-12 10:05:51 +07
**Session ID:** 20261012-100551-X4P9
**Plan:** `docs/plans/LAB_EXPOSURE_DIAGNOSTIC_PLAN.md` (2 phases)
**Worktree:** `/home/miftah/.worktrees/seer/lab-exposure-diagnostic`, branch `feature/lab-exposure-diagnostic` (base `origin/main` @ `85f65bd`)

---

## User Input

### Original User Request

```
/analyze docs/plans/HANDOVER_20261012-picks-not-brakes.md

Plan and then build the target in §4.1: the exposure diagnostic that measures a method's own
picks separately from the spare money it parks in the market, then run it over the five
surviving kin-clean dev-eligible methods in §2 and journal the answer.

Read the whole handover first. The hard constraints are in §3 (it must be report-only: no trial
recorded, N unmoved, no test-window look, because N counts distinct methods and every new one
raises the luck hurdle for the whole lab retroactively) and §6 (lab stage, no mid-batch rebase,
Postgres for DB tests, no hard-gate override). §4.1 lists open design questions that are yours
to decide, not mine.
```

### User-Provided Context

The handover `docs/plans/HANDOVER_20261012-picks-not-brakes.md`, read in full. The load-bearing
parts:

- **§1** — batch `sera-20261012-0832`'s accidental finding. M0107 carried a control arm (`NONE`)
  that stripped the parked SPY out of the calm dividend-raiser book. The dividend picks filled
  about four slots in ten; the rest sat in SPY, timed by the 200-day switch. With the parked money
  removed the picks lose to the market in **every** era: behind 4.4 pts/yr in 1996–2002, ahead
  ~1 pt in 2003–2008, behind 5.7 pts from 2009. The timed SPY holding was worth ~9 pts/yr early;
  the switch on top of it ~0.4. Six methods and thirty-five variations had no picking edge at all.
  Nothing in the lab would have caught it. That is feature-wish 174.
- **§2** — the live space is five methods in five clean families:
  `stock-short-term-reversal`, `stock-seasonality`, `stock-overnight-intraday`,
  `stock-momentum-attention`, `stock-core-satellite`. One of them (`stock-core-satellite`) is
  parked SPY *by construction*. "If the remaining four are also mostly parked market money, the
  lab has no live candidate at all, and should be told so plainly."
- **§3** — `N` for the deflated Sharpe counts distinct methods, so a new method raises the luck
  hurdle for the whole lab retroactively (N=74 → z=2.4228; N=78 → z=2.4419, 0.79% higher SR*).
  The diagnostic **must not be built as new lab methods**. Follow the `lab costs` pattern: re-run,
  print, record no trial, leave N and the look budget alone.
- **§4.1** — the target, plus four open design questions explicitly handed to the planner.
- **§6** — `lab stage` is the only way to commit `lab/lab.sqlite` and must include
  `web/data/lab.json`; no mid-batch `pull --rebase`; a `lab` subcommand dirties `lab.sqlite` even
  on a read; the research store is not in worktrees; worktree tests need `PYTHONPATH`; DB tests
  need Postgres; the hard gate has no override.

### User-Provided Files

- `docs/plans/HANDOVER_20261012-picks-not-brakes.md`

### Requirement IDs

| ID | What the user asked for |
|---|---|
| R1 | Build the §4.1 exposure diagnostic: for a given method and variant, report what share of the book's money was in its own picks (whole window and per era) versus parked in the market or in cash, and what the picks alone did against SPY TR per era with the parked holding removed and the brakes off. |
| R2 | Run it over the five surviving kin-clean dev-eligible methods in §2 and journal the answer. |
| R3 | Hold the §3/§6 constraints: report-only — no trial row, no moments, N unmoved, no test-window look, nothing written to `lab.sqlite` but a journal entry; `lab stage` for any database commit; no hard-gate override. |

---

## Detailed Requirements Understanding

**Problem statement.** Every number the lab records about a method is a number about the *whole
book*: total return, CAGR, max drawdown, profit factor, `exposure`. None of them separates the
two different things a book is made of — the names the method **picked**, and the money it
**parked** (in SPY or another index instrument, or left as cash because a gate fired or a slot
went unfilled). A method whose picks have no edge can still post a good whole-book number when
most of its money is parked market beta, and the lab cannot see the difference. That is exactly
what happened to `stock-dividend-change-drift` over three batches and thirty-five variations.

**What must change.** A new report-only path that, for a recorded method variant, runs the same
allocator with its targets re-weighted in three further ways, and prints the four runs beside each
other per era:

| Arm | What it holds | The question it answers |
|---|---|---|
| `BOOK` | the recorded variant, untouched | the reference; does the re-run still reproduce the record? |
| `PICKS` | the same targets with the parked symbols dropped, surviving weights unchanged | what share of the book was ever in its own picks, and what did that sleeve do carrying its own cash drag |
| `FULL` | the same, with the surviving picks rescaled to fill the book | what the picks did with the brakes off and the whole book behind them — the fair selection test against SPY |
| `PARK` | only the parked symbols, rescaled to fill the book | what the spare money in the market did, priced on its own |

**Success criteria.**

1. `lab exposure M0024 M0028 M0030 M0044 M0053` prints, per method and variant, the four arms'
   whole-window numbers and their per-era leads over SPY, and journals one plain-words
   observation per method.
2. It records no `trials`, `trial_moments`, `trial_funding` or `trial_provenance` row, moves no
   method status, touches no pre-registration, and leaves `store.dev_trial_count` (the lab's N)
   and `store.test_looks` exactly where it found them — printed before and after, and asserted in
   a test.
3. It never names the test window: `measure` refuses any store whose window is not
   `research.DEV_WINDOW`, and `dev.run_registry` is called with no `window=` keyword.
4. No new method file, no new method id, no `lab run`. N does not move, so no recorded method's
   DSR hurdle moves.
5. The five methods are run, the answer is read, and it is journaled as observations plus one
   synthesis.

**Key considerations, edge cases and assumptions.**

- **A whole-book gate cannot be undone generically.** When an allocator's gate fires it returns
  `()` — no targets at all. A wrapper that re-weights whatever the inner returns can undo a park,
  a vol-target brake and an unfilled slot, but it cannot invent the basket a gated-off allocator
  would have produced. The diagnostic therefore reports the **share of decision sessions on which
  the inner returned nothing** as a first-class number, instead of faking a counterfactual.
- **Recorded trials no longer reproduce exactly.** Measured in this session: M0053-RESON20-TV16
  re-runs to `364.8766403699613` against a recorded `364.876640369961` (reproduces), but
  M0030-C50T re-runs to `9.583603214115273` against a recorded `9.58372256394318`, and its SPY TR
  re-runs to `3.4668045` against a recorded `3.5142062`. The store fingerprint moved today
  (`399d0d25` → `77c37d55`). So **the arms are compared with each other, never with the recorded
  row**; the reproduction check is printed as information, the way `lab costs` prints it.
- **Mixed funding.** M0024 and M0030 have no `trial_funding` row (lump sum); M0028, M0044 and
  M0053 are funded on `OWNER_MONTHLY`. All four arms of one variant must share that variant's
  recorded capital and funding, or they stop being a comparison. Across methods, only the *lead
  over SPY* is comparable, never the absolute return.
- **Per-era arithmetic must be de-funded.** A funded curve sliced raw counts the owner's deposits
  as growth against a benchmark that received none (`backtest/regime.py:223-232` records what that
  cost the lab on 2026-10-09). `lab.walkforward.measure(curve, start, end, deposits)` already
  de-funds before it cuts; `hardgate.trial_deposits` already builds the deposit map.
- **Run cost is not a constraint.** Measured: the dev store loads in 10.1s and one dev run of a
  twenty-year book takes 1.8–5.4s. Five methods × every recorded variant (23 trials) × 4 arms is
  under ten minutes.

---

## Analysis Scope

### Explicitly Mentioned Files

- `docs/plans/HANDOVER_20261012-picks-not-brakes.md`

### Discovered Related Files

- `engine/src/seer_engine/lab/real_costs.py` — the `lab costs` report-only pattern the handover
  names (`measure` / `format_report` / `insight_text` / `journal`).
- `engine/src/seer_engine/lab/survivorship_check.py` — the *multi-method* report-only pattern
  (`plan_methods` / `Side` / `run_store` / `compare` / `format_report` / `summary_line` /
  `write_csv` / `journal`), and the only existing per-era lead computation.
- `engine/src/seer_engine/commands/lab.py` — the CLI: module docstring, subparsers, handlers,
  `_HANDLERS`.
- `engine/src/seer_engine/backtest/dev.py` — `Candidate`, `DevRow`, `run_registry`,
  `candidate_window`, the D9 window guard.
- `engine/src/seer_engine/backtest/book_runner.py` — `run_rules`, `run_book`, `RunStats`,
  `BookResult`, `_invested`.
- `engine/src/seer_engine/strategies/allocator.py` — the `Allocator` protocol, `MarketAware`,
  `prepare_for`, `scale_weight`, `BLEND`, `VOLTARGET`.
- `engine/src/seer_engine/sim/book.py` — `Target`, `to_weight`, `WEIGHT_QUANTUM`, `BookSnapshot`.
- `engine/src/seer_engine/sim/rules.py` — `TradeRules.idle_symbol`, `DEFAULT_ETFS`.
- `engine/src/seer_engine/lab/walkforward.py` — `measure(curve, start, end, deposits) -> Slice`.
- `engine/src/seer_engine/backtest/regime.py` — `defunded`, `BENCH_CANDIDATE = "REF-SPY-HOLD"`.
- `engine/src/seer_engine/lab/hardgate.py` — `geometry(conn)` (the recorded benchmark curve),
  `trial_deposits(conn, row, curve)`.
- `engine/src/seer_engine/lab/runner.py` — `recorded_capital`, `recorded_contributions`.
- `engine/src/seer_engine/lab/store.py` — `trials_of`, `dev_trial_count`, `test_looks`,
  `add_insight`, `INSIGHT_KINDS`, `LabError`.
- `engine/src/seer_engine/lab/method.py` — `Method`, `discover()`, `METHOD_ID`.
- `engine/src/seer_engine/commands/backtest_dev.py` — `month_end_curve(snapshots)`.
- `engine/src/seer_engine/strategies/f_index.py` — `TIMING.holds()` returns the held symbol.
- The five methods' files: `m0024_same_month_seasonality.py`, `m0028_short_term_reversal.py`,
  `m0030_spy_core_momentum_satellite.py`, `m0044_drizzle_blend_own_vol.py`,
  `m0053_overnight_winners_weekly_brake.py`; and `m0107_stock_trend_exit_raisers.py`, the method
  whose hand-built control arm this generalises.
- `engine/tests/labkit.py`, `engine/tests/allocatorkit.py`, `engine/tests/test_lab_costs.py`,
  `engine/tests/test_lab_survivorship.py` — the fixtures and the test shape to copy.
- `engine/tests/test_strategy_purity.py` — globs `strategies/`, `backtest/`, `fundamentals/`,
  `paper/`. **`lab/` is not globbed**, so a `lab` module may log.

---

## Current Dataflow

### Entry Point: `python -m seer_engine lab costs M0007`

**Location:** `engine/src/seer_engine/commands/lab.py:1778` (`_costs`)
**Trigger:** CLI subcommand, dispatched through `_HANDLERS` (`commands/lab.py:2338`)
**Input:** `args.method`, `args.candidate`, `args.store`; an open `sqlite3.Connection` to
`lab/lab.sqlite`.

**Validation, in order, all before a byte of market data is read:**

1. `real_costs.resolve_method(args.method)` — the id matches `METHOD_ID`, and `discover()` has a
   committed method file for it (`lab/real_costs.py:88`).
2. `real_costs.pick_candidate(conn, method, args.candidate)` — the method has a dev trial, and the
   named (or best-by-MAR) variant is still in the file (`lab/real_costs.py:104`).
3. `real_costs.twins(candidate)` — the variant runs the book engine at the default cost rate
   (`lab/real_costs.py:142`).
4. `runner.recorded_capital(conn, trial["n"])` — the trial has a `trial_provenance` row
   (`lab/runner.py:126`).
5. `research.DEV_END == dev.DEV_END`.

**Then:** `n_before = store.dev_trial_count(conn)`, `looks_before = store.test_looks(conn)`,
`research.load_store(Path(args.store))` (a test-window store raises `ValueError`, re-raised as
`LabError`), `real_costs.measure(...)`, `print(format_report(cmp))`, `with conn: journal(conn, cmp)`,
then both counters are printed again.

**Next step:** `real_costs.measure` → `dev.run_registry`.

### Processing Chain

1. **`real_costs.measure(method, candidate, trial, data, contributions, initial_idr)`**
   - **Location:** `lab/real_costs.py:243`
   - **Input:** a `Method`, a `Candidate`, the recorded trial row, a loaded `ResearchData`, the
     recorded funding and capital.
   - **Transform:** refuses `data.window != research.DEV_WINDOW`; builds the `(flat, real)` twin
     pair; calls `dev.run_registry(data.market, data.dividends, data.spy_dividends, (flat, real),
     on_result=..., contributions=..., initial_idr=...)` — **with no `window=` keyword**, so the
     D9 default `DEV_WINDOW` binds.
   - **Output:** a frozen `Comparison` of two `Side` records. No market, result or `DevRow` is
     retained.
   - **Calls:** `dev.run_registry` at `backtest/dev.py:608`.

2. **`dev.run_registry(market, dividends, spy_dividends, registry, *, on_result, window=DEV_WINDOW, initial_idr, contributions, contribution_fx)`**
   - **Location:** `backtest/dev.py:608`
   - **Transform:** `_check_market` and `_check_dividends` raise `DevWindowError` on any bar, FX
     row or dividend after `window.end`; refuses a registry over `MAX_CANDIDATES` (60), duplicate
     candidate ids, or two different allocator objects sharing an `allocator.id`;
     `prepare_for(c.allocator, market)` once per allocator id, cached and dropped after the last
     candidate that uses it; then `_run` per candidate.
   - **Output:** `tuple[DevRow, ...]`, and `on_result(i, result, row)` per candidate with the full
     `BookResult`/`RunResult`.

3. **`dev._run(...)`**
   - **Location:** `backtest/dev.py:492`
   - **Transform:** `candidate_window(market, c, window=window)` → `(start, end)`; the USD/IDR rate
     at `max(start, FX_START)`; `run_rules(...)`; then `spy_curves(spy, start, end,
     result.initial_cash, spy_dividends, cost_model=c.rules.cost_model, contributions=result.cashflows)`
     — the benchmark receives the identical dollars on the identical sessions; then
     `make_row(c, start, end, _funded_stats(result), spy_tr=curve_metrics(total),
     spy_price=curve_metrics(price), window=window)`.
   - **Output:** `(result, DevRow)`.

4. **`book_runner.run_rules` → `run_book`**
   - **Location:** `backtest/book_runner.py:414` → `:249`
   - **Transform:** per NYSE session: credit any contribution at the open; on a rank session call
     `allocator.targets_prepared(prepared, members, data_date, mine, params)` where
     `mine = held - {rules.idle_symbol}`; on a resize-only session rescale the last rank basket by
     the allocator's own total-weight move (`_rescaled`); append the residual idle target
     (`_with_idle`) — **an allocator that targets the idle symbol itself is a `ValueError`**; then
     `step_book`; then force-close any symbol with no bar on or after the session.
   - **Output:** `BookResult(snapshots, fills, trades, open_at_end, dividends_usd, costs_usd,
     rejections, contributions, cashflows)`. `BookSnapshot` is
     `(date, cash_usd, equity_usd, invested_usd)` — **no per-symbol breakdown**.

5. **`book_runner.run_stats(result)` → `RunStats`**
   - **Location:** `backtest/book_runner.py:506` (docstring), `:741` (book path)
   - **`exposure` for a book run is `mean(snapshot.invested_usd / snapshot.equity_usd)` over
     `snapshots[1:]`**, and `invested_usd` is `_invested(book, rules)` =
     `q(sum(shares × mark))` **over the non-idle positions** (`book_runner.py:238`). So the lab's
     existing `exposure` already excludes `rules.idle_symbol` — and nothing else. A symbol the
     allocator itself targets (an SPY core, a `park=True` residual) counts as invested.

### Data Persistence

**Database:** `lab/lab.sqlite`, opened by `commands/lab.py` and migrated on connect (so even a
read dirties the file). `lab costs` writes exactly one row:

- `insights(kind, title, body, method_id, added)` via `store.add_insight`
  (`lab/store.py:2075`), `kind ∈ INSIGHT_KINDS = ("observation", "hypothesis", "data-wish",
  "feature-wish", "risk", "synthesis")` (`lab/store.py:115`).

Nothing else. `trials`, `trial_moments`, `trial_funding`, `trial_provenance`, `methods.status` and
`docs/lab/prereg/` are untouched, which is what keeps `store.dev_trial_count` (the lab's N) and
`store.test_looks` still.

**Cache:** none. The research store is loaded from `engine/.research` (271 MB; `bars.csv`,
`dividends.csv`, `fundamentals.csv`, `fx.csv`, `market_series.csv`, `manifest.json`,
`unserved.csv`) and freed when the command returns.

### Exit Points

- stdout: the report, then the N / looks before-and-after line, then the `lab stage` reminder.
- the journal row.
- exit code 0; `store.LabError` → 2; anything else → 1.

---

## Key Data Structures

### Protocol: `Allocator`

**Location:** `strategies/allocator.py:58`
**Members:** `id: str`, `lookback(params)`, `symbols(params)`, `holds(params)`,
`uses_members(params)`, `targets(history, members, data_date, held, params)`,
`prepare(history)`, `targets_prepared(prepared, members, data_date, held, params)`.
`runtime_checkable`, so `isinstance` tests attribute presence only.

**`holds(params)` is the declared set of fixed instruments the allocator may hold** — the one
existing, generic, already-maintained answer to "what is parked here":

| Allocator | `holds(params)` | Location |
|---|---|---|
| `f_index.TIMING` | `(params.hold,)` — e.g. `("SPY",)` | `strategies/f_index.py:297` |
| `f_index.CALENDAR` | `(params.hold,)` | `strategies/f_index.py:343` |
| `allocator.BLEND` | the sorted union of its parts' `holds` | `strategies/allocator.py:521` |
| `allocator.VOLTARGET` | the inner's `holds` | `strategies/allocator.py:629` |
| `M0107.STOCKTREND` | `(b.market,)` when `park=True`, else `()` | `m0107_stock_trend_exit_raisers.py:200` |
| `M0024`, `M0028`, `M0053` | `()` | their method files |
| `M0044.FROGVOL` | `FROG.holds(inner)` = `()` | `m0044_drizzle_blend_own_vol.py:88` |

`dev.candidate_owner_inputs` already treats it that way: it adds `etf:<symbol>` for every held
instrument outside `DEFAULT_ETFS` (`backtest/dev.py:243`).

### Protocol: `MarketAware`

**Location:** `strategies/allocator.py:96`. One member, `prepare_market(market)`. Dispatched by
`prepare_for(obj, market)` (`:113`). **`LazyPrepared` (used by `BLEND` and `VOLTARGET`) silently
loses it** — `of(inner)` calls `inner.prepare(self.history)`, so a `MarketAware` inner wrapped in
`BLEND` never sees `market.dividends`. A new wrapper must therefore hold its inner allocator on
the **instance** and go through `prepare_for`, not through `LazyPrepared`.

Twenty method files implement `prepare_market` (the dividend families, `M0039`), so this matters
for any later run of the diagnostic over them, even though none of the five live methods needs it.

### Dataclass: `Candidate`

**Location:** `backtest/dev.py:176`
**Fields:** `id`, `family`, `rules: TradeRules`, `allocator: Allocator | Strategy`, `params`,
`rationale: str`, `added: date`, `owner_inputs: tuple[str, ...]`.
**Constraints:** `id` matches `[A-Z0-9]+(-[A-Z0-9]+)*`; `family` matches `F1..F11|REF|M\d{4}`;
a non-bracket rule set needs an `Allocator`; `rationale` is one non-empty line; `owner_inputs`
sorted and unique.

### Dataclass: `Target`

**Location:** `sim/book.py:152`. `weight` must be in `(0, 1]` and an exact multiple of
`WEIGHT_QUANTUM = Decimal("0.000001")`. `scale_weight(weight, factor)`
(`strategies/allocator.py:236`) returns `to_weight(weight × factor)` or `None` when it floors to
zero — the one correct way to re-weight a target.

### Dataclass: `RunStats`

**Location:** `backtest/book_runner.py:506`. `metrics`, `exposure`, `turnover`, `costs_usd`,
`gross_pnl_usd`, `cost_drag`, `dividends_usd`, `daily_returns`, `sharpe`, `year_returns`, …

### Dataclass: `Slice` (per-era arithmetic)

**Location:** `lab/walkforward.py:72`. `measure(curve, start, end, deposits)` de-funds the whole
curve with `regime.defunded` **before** cutting it, then returns
`Slice(months, total_return, cagr, max_drawdown, mar)`, or `None` when fewer than two months land
in the slice. This is the existing per-era primitive; `survivorship_check.side_of` already uses it
for its 2009–2015 lead (`lab/survivorship_check.py:333`).

### Dataclass: `Geometry`

**Location:** `lab/hardgate.py:571`. `geometry(conn)` reads the first recorded `REF-SPY-HOLD` dev
trial's `curve_json` — trial `n=1`, `1993-02-01..2015-10-16`, 6546 bytes — and cuts the
walk-forward folds from it. `bench` is the lab's one benchmark curve, unfunded, and is what every
per-era lead in the lab is measured against.

---

## Dependencies

### Configuration / Environment

- `SEER_LAB_DB` → `--db` (the shared lab database for parallel sessions).
- `SEER_RESEARCH_STORE` → `--store` default, else `research.STORE_DIR` (`engine/.research`).
  **The research store is not in worktrees**; a run from a worktree must point at
  `/home/miftah/seer/engine/.research`.
- `PG_TEST_URL` — Postgres for the DB tests; CI fails if they skip.
- `PYTHONPATH` — a worktree's pytest silently tests the main checkout without it.

### External Services

None. The diagnostic reads the committed method files, the lab database and the local research
store. No network, no Neon.

---

## Reference List

Everything the new code reads or extends. Nothing in this table is modified except
`commands/lab.py`, and that additively.

| Symbol / key | File:line | Kind | Package |
|---|---|---|---|
| `Allocator` (protocol) | `strategies/allocator.py:58` | impl (new wrapper implements it) | strategies |
| `MarketAware` | `strategies/allocator.py:96` | impl | strategies |
| `prepare_for` | `strategies/allocator.py:113` | call | strategies |
| `scale_weight` | `strategies/allocator.py:236` | call | strategies |
| `BLEND.holds` | `strategies/allocator.py:521` | read | strategies |
| `VOLTARGET.holds` | `strategies/allocator.py:629` | read | strategies |
| `TIMING.holds` | `strategies/f_index.py:297` | read | strategies |
| `Target`, `to_weight`, `WEIGHT_QUANTUM` | `sim/book.py:152,116,63` | call | sim |
| `TradeRules.idle_symbol` | `sim/rules.py:91` | read | sim |
| `DEFAULT_ETFS` | `sim/rules.py:45` | read | sim |
| `Candidate` | `backtest/dev.py:176` | call (constructs arm candidates) | backtest |
| `DevRow` | `backtest/dev.py:334` | read | backtest |
| `dev.run_registry` | `backtest/dev.py:608` | call | backtest |
| `dev.MAX_CANDIDATES` | `backtest/dev.py:84` | read | backtest |
| `dev.DEV_END` / `research.DEV_END` | `backtest/dev.py:79` | read | backtest |
| `RunStats.exposure` | `backtest/book_runner.py:529` | read | backtest |
| `month_end_curve` | `commands/backtest_dev.py:388` | call | commands |
| `daily_moments` | `commands/backtest_dev.py:419` | call (optional) | commands |
| `wf.measure` | `lab/walkforward.py:126` | call | lab |
| `regime.defunded` | `backtest/regime.py:190` | call (via `wf.measure`) | backtest |
| `regime.BENCH_CANDIDATE` | `backtest/regime.py:42` | read | backtest |
| `hardgate.geometry` | `lab/hardgate.py:593` | call | lab |
| `hardgate.trial_deposits` | `lab/hardgate.py:513` | call | lab |
| `runner.recorded_capital` | `lab/runner.py:126` | call | lab |
| `runner.recorded_contributions` | `lab/runner.py:114` | call | lab |
| `store.trials_of` | `lab/store.py` | call | lab |
| `store.dev_trial_count`, `store.test_looks` | `lab/store.py` | call (invariant print) | lab |
| `store.add_insight` | `lab/store.py:2075` | call | lab |
| `store.LabError` | `lab/store.py` | raise | lab |
| `method.discover`, `METHOD_ID` | `lab/method.py:106,25` | call | lab |
| `research.load_store`, `DEV_WINDOW`, `ResearchData` | `research.py:237` | call | engine |
| `real_costs.REPRO_TOL` | `lab/real_costs.py:46` | read | lab |
| `survivorship_check` (shape to mirror) | `lab/survivorship_check.py` | reference | lab |
| `_costs` handler, subparser | `commands/lab.py:1778,254` | reference | commands |
| `_survivorship` handler, subparser | `commands/lab.py:2148,339` | reference | commands |
| `_HANDLERS` | `commands/lab.py:2338` | **edit** (one entry) | commands |
| module docstring command list | `commands/lab.py:1-85` | **edit** (one block) | commands |
| `labkit.smoke_data`, `stamp_provenance` | `tests/labkit.py` | call | tests |
| `allocatorkit.assert_p4_identity`, `assert_valid_targets` | `tests/allocatorkit.py` | call | tests |
| `test_strategy_purity._pure_sources` | `tests/test_strategy_purity.py:34` | read (`lab/` not globbed) | tests |

### Lab state this is measured against (read-only, 2026-10-12)

The five surviving kin-clean dev-eligible methods and their recorded dev trials:

| Method | Family | Dev trials | Best recorded eligible by MAR | `holds()` on it |
|---|---|---|---|---|
| M0024 | `stock-seasonality` | #117–122 (6) | none eligible → best by MAR `M0024-SAME-N20-BLEND-RM` (0.697) | `()` |
| M0028 | `stock-short-term-reversal` | #157–161 (5) | `M0028-BLEND-RM` (0.619, eligible) | `()` |
| M0030 | `stock-core-satellite` | #126–128 (3) | none eligible → best by MAR `M0030-C50T` (0.682) | `("SPY",)` |
| M0044 | `stock-momentum-attention` | #153–156 (4) | `M0044-TV14-N21` (0.454, eligible) | `()` |
| M0053 | `stock-overnight-intraday` | #167–171 (5) | `M0053-RESON20-TV16` (0.582, eligible) | `()` |

M0028, M0044 and M0053 are funded (`trial_funding` rows, `+5,000,000 IDR on the 25th`, 237
deposits); M0024 and M0030 are lump-sum.

### Measured in this session (not read off the record)

- Dev store `engine/.research` loads in **10.1 s**, fingerprint `77c37d553508`.
- `M0053-RESON20-TV16`: **5.4 s**, window `1996-01-03..2015-10-16`, exposure 0.590, 1500 trades,
  total return `364.8766403699613` (recorded `364.876640369961` — reproduces), mwr `0.10193`
  vs SPY mwr `0.07188`.
- `M0030-C50T`: **1.8 s**, same window, exposure 0.706, 1615 trades, total return
  `9.583603214115273` (recorded `9.58372256394318` — **does not** reproduce at `REPRO_TOL = 1e-9`),
  SPY TR `3.4668045` (recorded `3.5142062`).

---

## Impact Points (files that WILL need changes)

1. **`engine/src/seer_engine/lab/exposure.py` — NEW.** The whole diagnostic: the park-set rule,
   the `ExposureAllocator` wrapper and its params, the four arm builders, `plan_methods`,
   `measure`, the era table, `format_report`, `summary_line`, `insight_text`, `journal`.
   Phase 1.
2. **`engine/src/seer_engine/commands/lab.py` — EDIT, additive.** One line in the module
   docstring's command list, one `sub.add_parser("exposure", ...)` block beside `survivorship`'s,
   one `_exposure(conn, args)` handler, one `_HANDLERS` entry. Nothing existing changes.
   Phase 1.
3. **`engine/tests/test_lab_exposure.py` — NEW.** The allocator-contract checks on the wrapper,
   the re-weighting arithmetic, the refusals before any store loads, the report-only invariant
   (N and looks unmoved, no `trials`/`trial_moments`/`trial_funding`/`trial_provenance` row, no
   status change), the test-window refusal, and an end-to-end CLI run on the smoke fixture.
   Phase 1.
4. **`lab/lab.sqlite` + `web/data/lab.json` — WRITTEN, by `lab exposure` and `lab stage`.**
   Five observations and one synthesis, staged together. Phase 2.
5. **`docs/backtests/20261012-exposure-diagnostic.md` — NEW.** The owner-facing write-up of what
   the five methods' picks did, and the full grid. Phase 2.
6. **`.workflows/todos.md` — EDIT.** The task record, per repo convention. Phase 2.

### Explicitly NOT touched

`sim/`, `backtest/`, `strategies/`, `paper/`, `sean/` — no shared engine code changes. The
share-of-money-in-the-picks number comes from an **arm's own `RunStats.exposure`**, which is the
same quantity M0107's session reported (HOST 70.4% invested, NONE 41.9%), so no per-session
holdings record has to be added to `BookResult` and no recorded result can shift.

**This document describes. The plan files prescribe.**

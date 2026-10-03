# Plan: Strategy A rework under walk-forward validation (P3b): `strategies/a2.py`, `backtest/walkforward.py`, `backtest_wf`

**Slug:** strategy-a-rework
**Date:** 2026-10-03 16:08 WIB
**Analysis:** `20261003-160830-R4W9_code_analyzer.md`
**Worktree:** `/home/miftah/.worktrees/seer/strategy-a-rework`
**Branch:** `feature/strategy-a-rework` (base: `HEAD` = `origin/main` @ `e14de0c`)
**Phases:** 6
**Status:** phase 3/6 complete
**Coordinator:** —

---

## Why

The specification is `docs/handover/2026-10-03-strategy-a-rework.md` (committed at `e14de0c`). Read
all of it. Its §3 "Law" table and its "Decided in this handover" table are binding. §6 is the
acceptance list. §7's open questions are settled under **Decisions** below. Its core, verbatim:

> P3 implemented Strategy A (Connors-style RSI(2) mean reversion, design §4) and backtested it
> over 10 years through the P2 simulator. **It failed honestly.** […] ROADMAP P3 says: *rework
> before P4; P4 must not start.* This handover is that rework, done once and under a protocol that
> cannot fool us.

> **One round only.** This rework runs **once**. If A2 fails the gate, Strategy A is not reworked
> again on this data. The report and ROADMAP say so, and P4 stays blocked.

> **The OOS window is burned.** 2022-01-03 → 2026-10-02 has been looked at once. Any variant
> judged on it again is not out-of-sample any more. The rework therefore validates with an
> **anchored walk-forward**, and the report shows the old split only as "seen before".

> **Never shrink the variants or the grid after results.**

## Requirements

| ID | What the user asked for (handover §6) | Phases |
|---|---|---|
| R1 | Variants V0–V3 with tests of each added rule: regime off at SPY close ≤ SMA(200), including equality; the ATR% ranking and its tie order; the $10 floor at exactly 10.0000; V0 picks `==` v1 picks | 1 |
| R2 | P4 identity and no look-ahead for every variant, including SPY's own bars dated ≥ S | 1 |
| R3 | Anchored yearly walk-forward: folds as defined, each fold's selection sees only its tuning window, segments chain into one portfolio, brackets survive the year boundary, the fallback is used when nothing qualifies | 2, 3 |
| R4 | Determinism: `==` results and byte-identical files; a parallel gather, if any, comes back in a fixed order | 3, 5 |
| R5 | The new modules pass the globbing purity test | 1, 3, 4 |
| R6 | One real walk-forward run on Neon, with a committed report holding fold selections and tables, per-variant curves, WF vs both SPY curves, diagnostics, the "seen before" window, the survivorship note and the P3b verdict sentence | 4, 5, 6 |
| R7 | Freeze or stop: on a pass, frozen A2 params with a comment naming the report and a code↔report test; on a fail, ROADMAP records that the one rework failed and P4 stays blocked, and the report lists what was tried | 6 |
| R8 | The v1 `backtest` report is byte-identical when re-run on the same data; `engine/package_readme.md` documents the variants, walk-forward and the new command; the suite is green with 0 skipped; CI is green | 2, 6 |

## Scope

**In scope:**
- New: `engine/src/seer_engine/strategies/a2.py`, `backtest/walkforward.py`, `backtest/wf_report.py`,
  `commands/backtest_wf.py`, and their tests.
- Additive edits:
  - `strategies/__init__.py` (exports);
  - `backtest/runner.py` (`ParamsSchedule`);
  - `backtest/metrics.py` (`metrics_through`);
  - `backtest/tuning.py` (`select(..., fallback=)`);
  - `backtest/io.py` (`write_wf_report`).
- The committed report set `docs/backtests/<end>-strategy-a2-walkforward*`.
- On a pass only: `STRATEGY_A2_PARAMS` and `tests/test_strategy_a2_frozen.py`. That test exists in
  both branches and asserts whichever branch the report took.
- `engine/package_readme.md` and `docs/ROADMAP.md`.

**Out of scope (handover §3 Law):**
- No edit to `seer_engine/sim/*`, `strategies/a.py`, `strategies/base.py`,
  `strategies/indicators.py`, `commands/backtest.py`, `backtest/report.py`,
  `test_strategy_a_frozen.py`, or `docs/backtests/2026-10-02-strategy-a.*`.
- No DB write and no migration.
- No change to `web/`, `.github/workflows/` or `cli.py`.
- No new variant, grid value or tuning rule beyond the handover's.
- No P4 or P6 work.

## Invariants

1. **The suite stays green.** At the end of every phase,
   `PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q`
   passes with **0 skipped**. Run `docker start seer-pg` first. Baseline on `e14de0c`: **598 passed**.
   Expected `passed` count at the end of each phase (no test is ever skipped or removed):

   | After | Adds | Passed |
   |---|---|---|
   | baseline `e14de0c` | — | 598 |
   | phase 1 alone (phase 1 lands first) | +62 | 660 |
   | phase 2 alone (phase 2 lands first) | +13 | 611 |
   | phases 1 and 2, either order | +62 +13 | 673 |
   | phase 3 | +39 | 712 |
   | phase 4 | +28 | 740 |
   | phase 5 | +17 | 757 |
   | phase 6 | +4 | 761 |

   A different count is a finding: name the missing or extra tests in the phase log before moving on.
   - `engine/.venv` must be the **worktree's own** venv. The worktree has none at first, so the first
     phase session in the tree runs
     `python3 -m venv engine/.venv && engine/.venv/bin/pip install -e 'engine[dev]'` from the
     worktree root.
   - Never use `/home/miftah/seer/engine/.venv`: it tests main's tree.
2. **Purity.** Every module in `strategies/` and `backtest/` except `backtest/io.py` is pure.
   `tests/test_strategy_purity.py` globs both directories, so new modules are covered without
   editing it. Only `backtest/io.py` and `commands/backtest_wf.py` (and v1's `commands/backtest.py`)
   touch the DB or files, log, or read the clock.
3. **No simulator change. v1 is untouched.**
   - `run_backtest` called with a plain params object behaves exactly as on `e14de0c`: same code
     path, same `RunResult`.
   - `tuning.select(rows)` without `fallback` returns exactly what it did.
   - Everything v1 reads (`a.py`, `report.py`, `commands/backtest.py`) is unedited. Therefore the v1
     report re-renders byte-identically.
4. **Read-only on Neon.** Nothing writes any table, `strategies.params` included.
5. **Determinism.**
   - The same inputs give `==` results and byte-identical files.
   - No unsorted set iteration in an output path.
   - No wall-clock value in any rendered file. Wall time goes to logs only.
   - The tuning pass is sequential (Decision D3), so results come in `combinations()` order.
6. **No look-ahead, no tuning on traded data.**
   - Picks for session S read bars through `prev_session(S)` only, SPY's included.
   - Fold Y's selection reads metrics through `tune_end(Y) = prev_session(first session of Y)` only.
   - Nothing computed on a traded segment feeds any selection.
7. **Decimal at the sim boundary.** `Pick` prices, `Bar` prices and cash are 4-dp `Decimal`s. Floats
   appear only in indicator math, threshold comparisons and metrics.
8. Every handover §3 rule holds, and so does every row under **Decisions**.

## Shared interface contract (all phases plan against this)

```python
# ---- seer_engine/strategies/a2.py  (phase 1; pure; a.py is NOT edited) ----------------------
from seer_engine.strategies.a import (LOOKBACK, SMA_N, AParams, APrepared, Features, DESIGN_PARAMS,
                                      features_at, prepare_a, _setup, _bracket)
from seer_engine.strategies.indicators import sma_window

REGIME_SYMBOL = "SPY"          # == universe.BENCHMARK (asserted by a test; a2 must not import universe: psycopg)
FLOOR_PRICE = 10.0             # V3: close >= 10.0 (inclusive); fixed, never tuned
VARIANTS: tuple[str, ...] = ("control", "regime", "regime_calm", "regime_calm_floor")   # V0..V3, this order everywhere

@dataclass(frozen=True, slots=True)
class A2Params:
    variant: str = "control"                       # one of VARIANTS, else ValueError; non-str TypeError
    rsi_max: float = 10.0
    limit_atr: Decimal = Decimal("0.5")
    tp_atr: Decimal = Decimal("1.0")
    sl_atr: Decimal = Decimal("1.5")
    min_dollar_volume: float = 20_000_000.0
    # __post_init__: validate variant; validate + coerce the other five exactly as AParams does, by building
    # AParams(rsi_max=..., ...) and copying its (coerced) values back with object.__setattr__.
    def a_params(self) -> AParams: ...             # AParams with the same five values
    def as_dict(self) -> dict[str, str]: ...       # {"variant": variant, **self.a_params().as_dict()}  (variant first)
    @classmethod
    def from_a(cls, variant: str, p: AParams) -> "A2Params": ...

A2_DESIGN_PARAMS = A2Params()                       # V0 with the design values: the walk-forward fallback
STRATEGY_A2_PARAMS: A2Params | None = None          # phase 6 sets it ONLY if the P3b gate passes (+ comment naming the report)

def regime_on(spy: History | None, data_date: date) -> bool:
    """True iff SPY has a bar dated data_date, >= LOOKBACK bars through it, and close > SMA(200) (STRICT),
    SMA = sma_window over SPY's last LOOKBACK closes ending at data_date (bit-identical rule).
    Missing SPY / no bar on data_date / too few bars -> False (no new picks for V1..V3)."""

def picks_from_features_a2(features: Iterable[Features], members: AbstractSet[str],
                           params: A2Params, regime: bool) -> list[Pick]:
    """variant != "control" and not regime -> [].
    Candidates: f.symbol in members, f.symbol != REGIME_SYMBOL, a._setup(f, a_params) and a._bracket(f, a_params) is not None;
    regime_calm_floor additionally needs f.close >= FLOOR_PRICE.
    Rank: control/regime -> (f.rsi, f.symbol); regime_calm/regime_calm_floor -> (f.atr / f.close, f.rsi, f.symbol). Ascending, uncapped."""

@dataclass(frozen=True, slots=True, eq=False)
class A2Prepared:
    a: APrepared                       # prepare_a(history) unchanged (contains SPY's rows too; filtered out by the rules)
    regime_dates: np.ndarray           # datetime64[D], ascending: every SPY bar date with >= LOOKBACK bars through it
    regime: np.ndarray                 # bool, same length: rolling SMA close > sma, bit-identical to regime_on
    def regime_on(self, data_date: date) -> bool: ...   # False when data_date not in regime_dates

def prepare_a2(history: Mapping[str, History]) -> A2Prepared
def picks_prepared_a2(prepared: A2Prepared, members, data_date, params: A2Params) -> list[Pick]
    # same vectorized pre-filter as picks_prepared_a (on prepared.a), then picks_from_features_a2(..., prepared.regime_on(d))

class StrategyA2:                      # implements strategies.base.Strategy
    id = "A2"
    lookback = LOOKBACK
    def picks(self, history, members, data_date, params): ...
        # params must be A2Params (TypeError otherwise); features_at({s: h for s in members}, d) as StrategyA does;
        # regime_on(history.get(REGIME_SYMBOL), d)   <- SPY read from the SAME history mapping, never a member
    def prepare(self, history) -> A2Prepared: ...
    def picks_prepared(self, prepared, members, data_date, params): ...
STRATEGY_A2 = StrategyA2()
# CONTRACT (P4 identity): picks_prepared(prepare(H), M, d, p) == picks({s: h.upto(d)}, M, d, p) for every variant.
# V0 identity: for any M with REGIME_SYMBOL not in M, STRATEGY_A2.picks(H, M, d, A2Params.from_a("control", p))
#              == STRATEGY_A.picks(H, M, d, p).

# ---- seer_engine/backtest/runner.py  (phase 2; additive) -------------------------------------
@dataclass(frozen=True)
class ParamsSchedule:
    """Params that change by session. segments[i] = (first_session_i, params_i); first sessions are NYSE
    sessions, strictly ascending; at least one segment."""
    segments: tuple[tuple[date, Any], ...]
    def at(self, session: date) -> Any: ...   # params of the last segment with first_session <= session; ValueError before segments[0]

# run_backtest(market, strategy, params, start, end, *, prepared=None, initial_idr=INITIAL_IDR) -- signature UNCHANGED.
# When isinstance(params, ParamsSchedule): ValueError if start < params.segments[0][0]; picks for session S use
# params.at(S) (S = the session being traded, NOT data_date); RunResult.params is the schedule object.
# Any other params value: the e14de0c code path, byte for byte in behaviour.
# ParamsSchedule.__post_init__ accepts any non-str iterable of pairs and stores a tuple of 2-tuples;
# TypeError on a non-pair / non-date / nested schedule, ValueError on empty / non-session / not ascending.

# ---- engine/tests/test_backtest_runner.py  (phase 2; additive test helpers) -------------------
# Unchanged and still importable: pick, FixedPicks, TABLE, scenario_market, run_scenario, START, END.
# New: ParamPicks(tables) (fake strategy, picks = tables[params][data_date], records .seen),
#      TABLE_B, SWITCH = date(2025, 3, 7), smoke_market(cut: date | None = None) -> (Market, start, end).
# Phase 3's tests import START and run_scenario from here; phase 2's metrics tests import the rest.

# ---- seer_engine/backtest/metrics.py  (phase 2; additive) ------------------------------------
def metrics_through(r: RunResult, end: date) -> Metrics:
    """run_metrics of r cut at session `end` (r.start <= end <= r.end, a session; ValueError otherwise):
    snapshots dated <= end; closed orders = exit events with event.session_date <= end, in event order.
    CONTRACT (prefix property): == run_metrics(run_backtest(<same market/strategy/params/start/prepared>, end=end))."""

# ---- seer_engine/backtest/tuning.py  (phase 2; additive) -------------------------------------
def select(rows: Sequence[GridRow], *, fallback: Any = DESIGN_PARAMS) -> Selection: ...
# Unchanged rule, tie-breaks and reason strings; only the fallback params object is a parameter.

# ---- seer_engine/backtest/walkforward.py  (phase 3; pure) ------------------------------------
FIRST_TRADE_YEAR = 2018
SEEN_BEFORE_START = tuning.OOS_START             # 2022-01-03: the burned P3 out-of-sample start
COMBINED = "walk-forward"                        # name of the variant-chosen-per-fold curve

@dataclass(frozen=True)
class Fold:
    year: int
    tune_start: date      # is_start (anchored)
    tune_end: date        # prev_session(trade_start)
    trade_start: date     # first NYSE session of `year`
    trade_end: date       # min(last NYSE session of `year`, end)

def folds(is_start: date, first_year: int, end: date) -> tuple[Fold, ...]
    # one per year first_year..end.year whose first session <= end; ValueError if is_start/end not sessions,
    # no fold, or folds[0].tune_end < is_start.
def combinations() -> tuple[A2Params, ...]
    # 324 = for variant in VARIANTS: for p in tuning.grid(): A2Params.from_a(variant, p)   (variant outer, grid inner)
def tune(market, strategy, prepared, combos, folds) -> tuple[tuple[GridRow, ...], ...]
    # ONE run_backtest per combo on [folds[0].tune_start, folds[-1].tune_end], then
    # GridRow(combo, metrics_through(run, f.tune_end)) for every fold; result[k] = fold k's rows in combos order.
    # Sequential. (Decision D3.)
def select_fold(rows: Sequence[GridRow], variant: str | None = None) -> Selection
    # variant None: tuning.select(rows, fallback=A2_DESIGN_PARAMS) over all rows;
    # variant v: tuning.select([r for r in rows if r.params.variant == v], fallback=A2Params(variant=v)).
def schedule(folds, selections: Sequence[Selection]) -> ParamsSchedule   # ((f.trade_start, s.params) for each fold)

@dataclass(frozen=True)
class WalkForward:
    name: str                          # COMBINED or a VARIANTS entry
    folds: tuple[Fold, ...]
    selections: tuple[Selection, ...]  # one per fold, folds order
    run: RunResult                     # run_backtest(market, strategy, schedule, folds[0].trade_start, folds[-1].trade_end, prepared=...)

def walk_forward(market, strategy, prepared, folds, fold_rows, variant: str | None = None) -> WalkForward

@dataclass(frozen=True)
class Diagnostics:                     # EXPLAINS results; never read by any selection
    trades: int
    pnl_by_reason: tuple[tuple[str, int, Decimal], ...]   # (reason, trades, Σ pnl_usd), metrics.EXIT_REASONS order, zeros kept
    pnl_by_year: tuple[tuple[int, int, Decimal], ...]     # (exit year, trades, Σ pnl_usd), ascending, years with trades only
    small_trades: int                                     # closed trades with shares < 3
    gross_pnl_usd: Decimal                                # Σ (exit_price − fill_price) × shares
    costs_usd: Decimal                                    # Σ (gross_i − pnl_usd_i)  (both 0.1% sides)
    cost_drag: float | None                               # costs / gross when gross > 0, else None
def diagnostics(r: RunResult) -> Diagnostics

def window_metrics(r: RunResult, start: date) -> Metrics            # the curve from prev_session(start) on, trades whose exit event is on/after start
def curve_window_metrics(c: BenchmarkCurve, start: date) -> Metrics # same slice of a SPY curve
def gate_p3b(wf: Metrics, spy_tr: Metrics, start: date, end: date) -> tuning.Verdict
    # checks = metrics.checklist(wf, spy_tr.total_return)[2:5]; passed = all three.
    # pass: "Strategy A2 passes the P3b gate: walk-forward from {start} to {end} it returned {wf} against {spy}
    #        for total-return SPY, with profit factor {pf} and max drawdown {dd}."
    # fail: "... fails the P3b gate: ..., so it fails on {failed}; Strategy A's one rework has failed, and P4 stays blocked."

# ---- seer_engine/backtest/wf_report.py  (phase 4; pure) --------------------------------------
@dataclass(frozen=True)
class WalkForwardReport:
    data_end: date
    bars_rows: int
    symbols_with_bars: int
    never_fetched_members: int
    survivorship: tuple[YearGap, ...]          # runner.survivorship(market, is_start, data_end)
    is_start: date
    folds: tuple[Fold, ...]
    fold_rows: tuple[tuple[GridRow, ...], ...] # tune() output
    combined: WalkForward                      # name COMBINED
    variants: tuple[WalkForward, ...]          # VARIANTS order
    spy_price: BenchmarkCurve                  # spy_curves(spy, folds[0].trade_start, folds[-1].trade_end, combined.run.initial_cash, dividends)
    spy_tr: BenchmarkCurve
    verdict: Verdict                           # gate_p3b(run_metrics(combined.run), curve_metrics(spy_tr), combined.run.start, combined.run.end)
    frozen_params: A2Params | None             # STRATEGY_A2_PARAMS at run time

    def curves(self) -> tuple[WalkForward, ...]   # (combined, *variants)
# _validate (called by every renderer) recomputes and REQUIRES: is_start == folds[0].tune_start; every
# fold_rows[k] lists the same A2Params combos in the same order; every curve's run.params ==
# walkforward.schedule(folds, wf.selections) and spans folds[0].trade_start..folds[-1].trade_end;
# all curves + both SPY curves aligned; verdict == gate_p3b(run_metrics(combined.run),
# curve_metrics(spy_tr), combined.run.start, combined.run.end).

def report_stem(data_end: date) -> str         # f"{data_end.isoformat()}-strategy-a2-walkforward"
GATE_KEY = "p3b-gate"; FROZEN_KEY = "frozen-params"; LAST_FOLD_KEY = "last-fold-params"; TOP_N = 10
def machine_lines(r) -> list[str]              # exactly, in this order:
    #   "p3b-gate: passed" | "p3b-gate: failed"                      (r.verdict.passed)
    #   "last-fold-params: " + json.dumps(r.combined.selections[-1].params.as_dict())   (variant first, never sorted)
    #   "frozen-params: null" | "frozen-params: " + json.dumps(r.frozen_params.as_dict())
    # rendered inside one ```text fence at the end of the Markdown
def parse_machine_line(markdown: str, key: str) -> str   # raw value of the single "<key>: <value>" line; ValueError unless exactly one
def top_rows(rows: Sequence[GridRow]) -> list[int]       # 0-based indices of the D11 top-10
GRID_CSV_HEADER: tuple[str, ...]   # fold,tune_start,tune_end,combo,variant,rsi_max,limit_atr,tp_atr,sl_atr,min_dollar_volume,
                                   # total_return,cagr,win_rate,profit_factor,max_drawdown,trades,months,avg_days_held,qualifies,selected
EQUITY_CSV_HEADER: str             # "date,walk_forward,control,regime,regime_calm,regime_calm_floor,spy_price,spy_tr"
def render_markdown(r) -> str      # ends in exactly one "\n"
def equity_csv(r) -> str           # date,walk_forward,control,regime,regime_calm,regime_calm_floor,spy_price,spy_tr
def grid_csv(r) -> str             # one row per (fold, combo): every tuning-window run
def equity_svg(r) -> str           # walk-forward vs SPY price-only vs SPY total-return
def variants_svg(r) -> str         # the four per-variant curves + SPY total-return

# ---- seer_engine/backtest/io.py  (phase 5; additive) -----------------------------------------
def write_wf_report(out_dir: Path, report: WalkForwardReport) -> list[Path]
    # <stem>.md, <stem>-equity.csv, <stem>-equity.svg, <stem>-variants.svg, <stem>-grid.csv; all rendered before any write

# ---- seer_engine/commands/backtest_wf.py  (phase 5) ------------------------------------------
# python -m seer_engine backtest_wf [--out DIR] [--cache-dir DIR] [--refresh-cache] [--is-start D]
#                                   [--first-year YYYY] [--end D] [--dividends PATH]
# def execute(market, bars_rows, dividends, is_start, first_year, end) -> WalkForwardReport   (pure but for logging + perf_counter)
#     builds spy_curves(market.spy(), folds[0].trade_start, folds[-1].trade_end, combined.run.initial_cash, dividends)
#     and verdict = gate_p3b(run_metrics(combined.run), curve_metrics(spy_tr), combined.run.start, combined.run.end),
#     frozen_params = strategies.a2.STRATEGY_A2_PARAMS read at call time
# def resolve(market, is_start, first_year, end: date | None) -> WfWindows    # BacktestWfError -> exit 2
# def tune_all(market, strategy, prepared, combos, folds)   # walkforward.tune(..., (combo,), folds) per combo, timed,
#     stitched in combos order; == walkforward.tune(..., combos, folds) (tested)   (Decision D17)
# def run_walk_forward(market, strategy, prepared, folds, fold_rows, variant) -> WalkForward   # walk_forward + logging
```

## Phases

| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID | Card |
|---|-------|-----------|---------|-------|-----------|------------|------|--------|------|
| 1 | Strategy A2: variants V0–V3 | R1, R2, R5 | `strategies` | 3 | — | NORMAL | `.workflows/plan/strategy-a-rework/phase-1.md` | P1-ENG-WCIA | — |
| 2 | Runner params schedule, `metrics_through`, `select` fallback | R3, R8 | `backtest` | 6 | — | NORMAL | `.workflows/plan/strategy-a-rework/phase-2.md` | P1-ENG-3PA3 | — |
| 3 | Walk-forward engine | R3, R4, R5 | `backtest` | 2 | 1, 2 | HARD | `.workflows/plan/strategy-a-rework/phase-3.md` | P1-ENG-ODYP | — |
| 4 | Walk-forward report rendering | R5, R6 | `backtest` | 2 | 3 | HARD | `.workflows/plan/strategy-a-rework/phase-4.md` | P1-ENG-BVN5 | — |
| 5 | `backtest_wf` command + `write_wf_report` | R4, R6 | `commands`, `backtest` | 3 | 4 | NORMAL | `.workflows/plan/strategy-a-rework/phase-5.md` | P1-ENG-U4G0 | — |
| 6 | Real run on Neon, freeze or stop, docs | R6, R7, R8 | `docs`, `strategies`, `tests` | 8 (fail) / 9 (pass); 5 generated | 5 | NORMAL | `.workflows/plan/strategy-a-rework/phase-6.md` | P1-ENG-RTWR | — |

### Phase 1: Strategy A2, variants V0–V3
**Satisfies:** R1, R2, R5. One module, so the variant rules and their identity/look-ahead tests cannot be split.
**Owns:**
- `strategies/a2.py` (new), exactly the contract above;
- `strategies/__init__.py` exports;
- `tests/test_strategy_a2.py` (new): every R1 rule; V0 `==` v1 over a contract set for several params; P4 identity for all four variants; no look-ahead with SPY mutated or truncated from S; SPY never picked; `REGIME_SYMBOL == universe.BENCHMARK`.

Reuse `tests/stratkit.py` builders; the plan needs no new builder, so `stratkit.py` is not edited.
`STRATEGY_A2_PARAMS = None` sits on its own line under a two-line placeholder comment, and
`Decimal` is imported in `a2.py` (phase 6 replaces those three lines on a pass).
**Does not touch:** `a.py`, `base.py`, `indicators.py`, `stratkit.py`, `test_strategy_purity.py`, anything in `backtest/`.
**Exit criteria:** suite green, 0 skipped (660 alone, 673 with phase 2); the purity glob covers `a2.py`; `a.py`, `base.py`, `indicators.py` byte-identical to `e14de0c`.

### Phase 2: Runner params schedule, `metrics_through`, `select` fallback
**Satisfies:** R3 (schedule + prefix property), R8 (v1 path provably unchanged).
**Owns:**
- `ParamsSchedule` + the schedule branch in `run_backtest`;
- `metrics_through` in `metrics.py`;
- `fallback=` on `tuning.select`;
- tests in `test_backtest_runner.py`, `test_backtest_metrics.py`, `test_backtest_tuning.py`:
  - a schedule switching params mid-run, where an open order keeps its bracket across the switch;
  - a one-segment schedule `==` the plain-params run, except for `RunResult.params`;
  - the prefix property on the scenario market and on a Strategy A smoke market, for several cut sessions, forced closes included;
  - `select` with and without `fallback`;
  - test helpers `ParamPicks`, `TABLE_B`, `SWITCH`, `smoke_market(cut=None)` appended to `test_backtest_runner.py`; the existing helpers (`START`, `END`, `TABLE`, `FixedPicks`, `scenario_market`, `run_scenario`) are left exactly as they are, because phases 2 and 3 import them.
- The one existing assertion that must change: `test_backtest_tuning.py::test_gate_and_select_see_only_their_own_window` asserts `select`'s parameters are `["rows"]`. It is widened to `["rows", "fallback"]`, with `fallback` keyword-only and defaulting to `DESIGN_PARAMS` (Decision D19). No other phase edits that file.

**Does not touch:** `strategies/`, `report.py`, `commands/`.
**Exit criteria:** suite green, 0 skipped (611 alone, 673 with phase 1); every existing runner/tuning/metrics test unchanged and passing, except the widened `select` signature guard (D19).

### Phase 3: Walk-forward engine
**Satisfies:** R3, R4, R5.
**Owns:**
- `backtest/walkforward.py` (new): `folds`, `combinations`, `tune`, `select_fold`, `schedule`,
  `walk_forward`, `diagnostics`, `window_metrics`, `curve_window_metrics`, `gate_p3b`;
- `tests/test_backtest_walkforward.py` (new), on synthetic data:
  - folds exactly as defined (real calendar: 2018…2026 against end 2026-10-02, plus edge cases);
  - 324 combinations in order;
  - `tune` rows `==` direct per-fold `run_backtest` + `run_metrics` on a small market;
  - mutating any bar inside a traded year leaves that fold's rows and selection unchanged;
  - the WF run is one portfolio whose params switch at year starts, and an order open across 31 Dec keeps its bracket;
  - fallback (`A2_DESIGN_PARAMS`, and `A2Params(variant=v)` per variant) is used when nothing qualifies;
  - diagnostics hand-computed;
  - gate sentences;
  - two identical calls give `==` results.

Its tests import `START` and `run_scenario` from `test_backtest_runner.py` (unchanged by phase 2) and `hist`/`mutate_from` from `stratkit.py`.
**Does not touch:** `runner.py`, `metrics.py`, `tuning.py` (it uses phase 2's API), `strategies/`, any existing test file.
**Exit criteria:** suite green, 0 skipped (712); purity glob covers the module.

### Phase 4: Walk-forward report rendering
**Satisfies:** R6 (content), R5.
**Owns:**
- `backtest/wf_report.py` (new): `WalkForwardReport`, `report_stem`, machine lines, `parse_machine_line`, `render_markdown`, `equity_csv`, `grid_csv`, `equity_svg`, `variants_svg`;
- `tests/test_backtest_wf_report.py` (new), built from a small synthetic walk-forward via phase 3's API.

Sections, in order:
1. title;
2. verdict;
3. Data;
4. Method, which lists **everything tried**: 4 variants × 81 grid, the fold rule, the selection rule and the fallback;
5. Folds: per fold, its windows, the selection, its reason, and a **top-10** table;
6. Walk-forward results vs both SPY curves;
7. Per-variant walk-forward table and per-variant fold selections;
8. Diagnostics, for the combined curve and each variant;
9. "Seen before" (2022-01-03 → end, sliced from the continuous curves, labelled information only);
10. Go-live checklist;
11. Survivorship;
12. Open positions at end;
13. Equity curves (both SVGs, and links to both CSVs);
14. Gate verdict;
15. "If the gate failed: what the owner decides next", with handover §8's options (a)–(c) verbatim in substance, rendered only on a fail;
16. machine lines.

Machine lines exactly as in the contract (D14). It imports these `report.py` names read-only, all present on `e14de0c`: `FENCE`, `_CHECK_NOTES`, `_EXIT_LABELS`, `_LABEL_GAP`, `_MB`, `_ML`, `_MR`, `_MT`, `_SVG_H`, `_SVG_W`, `_check_aligned`, `_esc`, `_nice_ticks`, `_order_row`, `_pass`, `_plain`, `_sessions`, `_span`, `_table`, `_tick_label`, `_usd`. It defines its own `_STYLE` (seven series classes) rather than reusing `_SVG_STYLE`.
**Does not touch:** `report.py`. It imports `report`'s helpers read-only. If a helper must change, copy it instead.
**Exit criteria:** suite green, 0 skipped (740); rendering is deterministic (two renders are byte-equal; this serves invariant 5, see D16).

### Phase 5: `backtest_wf` command + `write_wf_report`
**Satisfies:** R6 (the runnable command), R4 (byte-identical files).
**Owns:**
- `io.write_wf_report`;
- `commands/backtest_wf.py`: args, `resolve` preconditions mirroring v1's exit-2 cases, `tune_all` (per-combination timing by calling `walkforward.tune` once per combination, D17), `run_walk_forward`, and `execute`. `execute` builds the SPY curves and the verdict exactly as `wf_report._validate` recomputes them (contract). `execute` logs:
  - the prepare time;
  - per-combo tuning time and the total;
  - per-fold selections;
  - the verdict;
  - whether `STRATEGY_A2_PARAMS` matches the last fold's selection.
- `tests/test_backtest_wf_command.py`: discovery and defaults; the exit-2 cases; an end-to-end run on a synthetic PG schema spanning ≥ 2 trade years, which checks read-only access, the five file names, a cache hit on re-run, and every file byte-identical on re-run.

**Does not touch:** `commands/backtest.py`, `report.py`, `walkforward.py`, `wf_report.py` (except to fix a defect found here, recorded in the phase log).
**Exit criteria:** suite green, 0 skipped (757); `python -m seer_engine backtest_wf --help` works; `tune_all == tune` on a subset is tested.

### Phase 6: Real run on Neon, freeze or stop, docs
**Satisfies:** R6, R7, R8.
**Owns:**
- One real `backtest_wf` run. Commit `docs/backtests/<end>-strategy-a2-walkforward{.md,-equity.csv,-equity.svg,-variants.svg,-grid.csv}`.
- **Pass:** replace phase 1's two-line placeholder comment and the `STRATEGY_A2_PARAMS = None` line with an explicit `A2Params(...)` literal of the last fold's selection and a comment naming the report, then re-run so the report records it.
- **Fail:** leave it `None`.
- `tests/test_strategy_a2_frozen.py` asserts the branch the newest report took.
- The v1 byte-identity check against the committed `2026-10-02-strategy-a.*` (Decision D9).
- `docs/ROADMAP.md`: a P3b line under P3, carrying the verdict sentence. On a fail it says the one rework failed and P4 stays blocked.
- `engine/package_readme.md`:
  - `strategies` (A2 and its variants);
  - `backtest` (schedule, `metrics_through`, walkforward, wf_report);
  - the `backtest_wf` command section;
  - `## Performance` with the measured times;
  - Usage.

**Does not touch:** any pure module's logic. If the real run exposes a defect, fix it in the owning module with a test, and record it in the phase log.
**Exit criteria:** report committed; frozen test green; v1 identity verified; suite green, 0 skipped (761); CI green on push.

## Reconciliation Log

| Conflict | Phases | Resolution |
|---|---|---|
| Contract drift: phase 5's `execute` built the SPY curves to `end` and gated on `(trade_start, end)`, while phase 4's `_validate` and the index recompute over `folds[-1].trade_end` and `(combined.run.start, combined.run.end)`. Equal by the fold rule, but spelled differently | 4, 5 | Phase 5's code now uses `folds[-1].trade_end` and `(combined.run.start, combined.run.end)` literally; its note explains why the values are the same as `end`. Index contract says so (D18) |
| Contract drift: the index's phase 2 exit criterion said "every existing tuning test unchanged", but phase 2 must widen `test_gate_and_select_see_only_their_own_window` (`["rows"]` → `["rows", "fallback"]`) or the build breaks | 2 | Exit criterion and Owns updated to name the one widened guard; phase 2 states no other phase touches `test_backtest_tuning.py` (D19). Ledger confirms no other plan edits it |
| Unmet-assumption check: phase 3's tests import `START`, `run_scenario` from `test_backtest_runner.py`, which phase 2 edits | 2, 3 | Verified phase 2 only replaces the import block and appends; added an explicit guarantee in phase 2's contract and in the index contract that `pick`, `FixedPicks`, `TABLE`, `scenario_market`, `run_scenario`, `START`, `END` stay unchanged and importable |
| Unmet-assumption check: phase 4 imports 21 private names from `report.py` | 4 | Every name verified present on `e14de0c` (`_ML, _MR, _MT, _MB` are one tuple assignment at `report.py:593`; the rest are defs/constants). Listed in the index's phase 4 section. No change needed |
| Unmet-assumption check: phase 4 imports `GRID_*` from `tuning`, `ATR_N`/`SMA_N` from `strategies.a`, `EXIT_REASONS`/`fmt_num`/`forced_closes` from `metrics` | 4 | All present on `e14de0c`. No change |
| Unmet-assumption check: phase 5's `tune_all` stitches per-combo `walkforward.tune` calls | 3, 5 | Phase 3's `tune(market, strategy, prepared, combos, folds)` accepts any sequence, returns `len(folds)` tuples of rows in `combos` order, one independent run per combo; matches phase 5's stitch and phase 3's own design note. Recorded as D17 |
| Unmet-assumption check: machine-line formats between phases 4, 5 and 6 | 4, 5, 6 | Phase 4 renders `p3b-gate: passed\|failed`, `last-fold-params: json.dumps(as_dict())`, `frozen-params: null\|json.dumps(as_dict())` once each in a `text` fence; phase 5's e2e test and phase 6's frozen test parse exactly that via `parse_machine_line` + `json.loads`. Formats spelled out in the index contract |
| Unmet-assumption check: phase 6 needs `STRATEGY_A2_PARAMS` on its own line with `Decimal` imported | 1, 6 | Phase 1's code has both; the placeholder comment is two lines, not one. Phase 1's handoff and phase 6's Step 4 now name both comment lines and say to keep the `A2_DESIGN_PARAMS` line |
| Contract drift: phase 6's readme module-graph text claimed `strategies.a2` imports `prices` and left `commands.backtest`'s use conditional | 6 | Rewritten to the imports phases 1, 3, 4, 5 actually plan (`a2` does not import `prices`; `backtest_wf` imports `commands.backtest.never_fetched_members`) |
| Missing precision: per-phase expected test counts were relative ("611 + phase 1's count", "X + 39") | 1–6 | Invariant 1 now holds the absolute table (598 → 660/611 → 673 → 712 → 740 → 757 → 761); each phase's Verification quotes its row |
| Requirement-creep check: phase 4's byte-equal-renders test looks like R4 work | 4 | Not moved: it enforces invariant 5, which binds every phase. R4 stays with phases 3 and 5 (D16) |
| Interface additions not in the index contract (`WalkForwardReport.curves`, `machine_lines`, `top_rows`, `TOP_N`, CSV headers; `resolve`, `tune_all`, `run_walk_forward`; phase 2 test helpers) | 2, 4, 5 | Added to the shared interface contract |
| Phase 6 file count was "5–7" | 6 | Corrected to 8 on a fail, 9 on a pass (5 generated + frozen test + readme + ROADMAP, + `a2.py` on a pass) |

## Decisions

| Fork | Chosen | Rung |
|---|---|---|
| D1 §7 Params schedule vs separate runner | Extend `run_backtest`: `params` may be a `ParamsSchedule`, and picks use `params.at(S)`. Any other value takes the unchanged path. Signature unchanged. | 5: handover §7 "prefer extending it, with a default that keeps today's behaviour" |
| D2 §7 Variant-in-params or variant-as-strategy | One `A2Params(variant=…, + A's five fields)` and one `STRATEGY_A2`, so selection runs over a single 324-row list and a `ParamsSchedule` can switch variant by year | 5: handover §7 "prefer one params type" |
| D3 §7 Fold tuning cost | `prepare_a2` runs **once** over all history: it is param- and variant-independent and causal. Tuning runs **one** `run_backtest` per combination over `[IS_START, last tune_end]` and reads each fold's metrics with `metrics_through(run, tune_end)`. That is exact by the runner's prefix property (proven by phase 2/3 tests), cuts ≈ 9× the work, and the selection still sees only its window. Sequential, with no process pool. Measure and log the time; parallelize in fixed order only if it exceeds 60 min. | 1: invariant 6 holds; 5: handover "measure before deciding" |
| D4 §7 SPY in V1's `history` | The regime reads `history.get("SPY")` (`picks`) or a precomputed SPY regime column (`prepare_a2`), both bit-identical over the last 200 bars ending at `data_date`. SPY missing, no bar on `data_date`, or < 200 bars means the regime is **off**. SPY can never be a pick: it is excluded explicitly (`symbol != REGIME_SYMBOL`), and the universe never lists it anyway. | 5: handover §3 V1 row + §7 |
| D5 Regime boundary | Regime on ⇔ SPY close > SMA(200), **strict**. Equality means no new picks. | 5: handover V1 "close ≤ SMA(200) → no new picks" |
| D6 Schedule key | Params are keyed by the **traded session** S. The first session of Y uses fold Y's params, with `data_date` = the last session of Y−1 = `tune_end(Y)`. Orders keep the bracket they were placed with, because the simulator never rewrites one. | 5: handover fold row "open orders keep the brackets they were placed with" |
| D7 Per-variant fallback | Per-variant curves fall back to **that variant** with the design values (`A2Params(variant=v)`), so the variant stays fixed. The combined curve falls back to `A2_DESIGN_PARAMS` (V0 design). | 5: handover "variant fixed, grid tuned per fold" + "the fold trades V0 with the design values" |
| D8 Command name | `backtest_wf` (module `commands/backtest_wf.py`). `cli.discover` names commands after modules, and a hyphen is not a legal module name. `cli.py` is not edited. | 6: surrounding convention |
| D9 v1 byte-identity check | Phase 6 re-runs v1 `backtest` into a scratch dir and `cmp`s it with the committed three files. Main has **no** warm bar cache (verified by the phase 6 planner), so that first load is cold (~25 s) and it writes the cache the walk-forward run then reuses. If Neon's `bars` fingerprint is no longer `(1,817,429, 2026-10-02)`, phase 6's scratch script rebuilds v1 from `bars` filtered to `date <= 2026-10-02` (guarded by the exact row count). If the files still differ, it runs the same script under main's venv (`e14de0c`) to tell a data change from a code change. Report the method used. | 1: invariant 3; 6: convention |
| D10 Data end | The WF run uses whatever data Neon has. Its stem and every window end use that date. The 2022-01-03 "seen before" slice runs to the same end. | 5: handover §4 "record the data end the run actually used" |
| D11 Report layout | The main `.md` holds per-fold **top-10** tables plus each selection. `-grid.csv` holds all 9 × 324 rows. Top-10 order: qualified rows first, by the selection key (−return, DD, index), then the rest by (−return, DD, index). | 5: handover §7 recommendation |
| D12 Diagnostics definitions | P/L by exit reason and by **exit year** (Σ `pnl_usd`, net). Small trades = closed with `shares < 3`. Cost drag = Σ(gross − net) ÷ Σ gross, and "—" when Σ gross ≤ 0, with costs and gross also shown in USD. Diagnostics never reach `select`. | 5: handover diagnostics row |
| D13 "Seen before" | A slice of the **continuous** walk-forward and SPY curves from `prev_session(2022-01-03)`, not a fresh portfolio. It is labelled "seen before: information only, not out-of-sample" and never feeds the gate. | 5: handover "the report shows the old split only as 'seen before'" |
| D14 Freeze mechanics | `STRATEGY_A2_PARAMS = None` until phase 6. The report always carries `p3b-gate: passed\|failed`, `last-fold-params: {json}` and `frozen-params: null\|{json}`. On a pass, phase 6 freezes, re-runs, and commits the re-rendered report. `test_strategy_a2_frozen.py` asserts: passed ⇒ code == frozen == last-fold and the comment names the report; failed ⇒ code is `None` and frozen is `null`. | 5: handover "Deployed parameters" + §6.7 |
| D15 Survivorship window | `survivorship(market, is_start, data_end)`: the walk-forward reads bars from `is_start` on, since tuning uses them | 6: convention (P3 used its full window) |
| D16 Who owns determinism tests | Each phase tests determinism of what it builds (phase 3: `==` results; phase 4: byte-equal renders; phase 5: byte-identical files on re-run). R4 is credited to phases 3 and 5 only; phase 4's test enforces invariant 5 and is not R4 creep | 1: invariant 5 binds every phase |
| D17 Per-combination tuning time | `walkforward.tune` gets no progress callback. Phase 5's `tune_all` calls `tune(..., (combo,), folds)` once per combination, times it, and stitches results in `combinations()` order; a test asserts `tune_all == tune` | 3: phase 3's code block (`tune` accepts any combo sequence) + phase 3's design note; 1: invariant 5 (fixed order) |
| D18 SPY curve and gate span | SPY curves over `folds[0].trade_start → folds[-1].trade_end` (not `--end`), gate over `(combined.run.start, combined.run.end)`. Equal to `end` by the fold rule; spelled this way so `_validate` recomputes the identical value | 3: phase 4's `_validate` code block |
| D19 `select` signature guard | The existing `test_gate_and_select_see_only_their_own_window` is widened, not deleted: `select`'s parameters are `["rows", "fallback"]`, `fallback` keyword-only with default `DESIGN_PARAMS`. Its intent (selection takes no out-of-sample window) is kept | 1: invariant 3 (`select(rows)` unchanged) and invariant 6; 2: phase 2's exit criteria (build green) |

## Open Questions

None. Every requirement R1–R8 has an owning phase, and no fork was irreversible.

## Rollback

- Per phase: `git revert` the phase commit. Phases 1–5 add modules and additive kwargs only.
  Phase 6 adds docs and one constant.
- As a whole: delete branch `feature/strategy-a-rework` before merge, or revert the merge commit
  after. v1's files, `a.py` and the simulator are never touched, so a revert restores `e14de0c`
  behaviour exactly.

## Next

Execute the phases one at a time, starting at phase 1:

    /implement -f STRATEGY_A_REWORK_PLAN.md --phase 1

Or run the whole set as a swarm: one session per phase, concurrent wherever `Depends on` allows,
and resumable on any machine:

    /analyze-orchestrator -f STRATEGY_A_REWORK_PLAN.md

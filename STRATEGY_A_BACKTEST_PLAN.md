# Plan: Strategy A + 10-year backtest (P3) — `seer_engine/strategies/`, `seer_engine/backtest/`

**Slug:** strategy-a-backtest
**Date:** 2026-10-03 14:45 WIB
**Analysis:** `20261003-144506-Q8N4_code_analyzer.md`
**Worktree:** `/home/miftah/.worktrees/seer/strategy-a-backtest`
**Branch:** `feature/strategy-a-backtest` (base: `origin/main` = `HEAD` @ `d3a2e1d`)
**Phases:** 6
**Status:** phase 3/6 complete
**Coordinator:** —

---

## Why

The specification is `docs/handover/2026-10-03-strategy-a-backtest.md` (committed at `d3a2e1d`).
Its §3 tables are law, §6 is the acceptance list, and §7's open questions are settled under
**Decisions** below. Its §2, verbatim:

> Implement Strategy A and a 10-year backtest that runs it through the **P2 simulator**, then give
> an honest verdict on whether it beats SPY.
>
> It must:
> 1. Compute Strategy A's signals (design §4) from split-adjusted daily bars, using only data
>    available at the `data_date` close (no look-ahead), and turn them into ranked `sim.Pick`s.
>    Put this behind a small strategy interface, because P4 calls the same code nightly and P6 adds
>    strategies B and C next to it.
> 2. Run a backtest over the point-in-time universe (S&P 500 ∪ Nasdaq-100 members on each
>    `data_date`) for every NYSE session in the window, using `sim.size_picks` → `sim.step` →
>    `sim.close_unpriced` exactly as the readme's "P3 backtest loop" shows.
> 3. Build the SPY buy-and-hold benchmark curve over the same window, net of the same 0.1% costs.
> 4. Tune parameters on the early years only, validate on the later years without tuning, then
>    **freeze** the parameters in code.
> 5. Produce a backtest report: equity curve vs SPY, total return, CAGR, win rate, profit factor,
>    max drawdown, trade count, exit-reason breakdown, and the go-live criteria from design §1
>    that a backtest can evaluate. Report the in-sample and out-of-sample windows separately.
>
> **The gate (ROADMAP P3):** if Strategy A cannot beat SPY in the backtest, **stop and report it**.
> Do not start P4, and do not tune on the validation window to rescue it. A losing verdict, honestly
> measured, is a successful P3. Tuning until the number looks good is the failure mode this project
> exists to avoid.
>
> **Out of scope, don't build:** nightly wiring, writing `orders`/`equity_snapshots`/`strategies.params`
> to Neon (P4), LLM explanations (P4), strategies B and C (P6), any web change, any change to
> simulator rules.

## Requirements

| ID | What the user asked for | Phases |
|---|---|---|
| R1 | Strategy A signals from data through `data_date` only → ranked `sim.Pick`s, behind a small pure strategy interface shared with P4/P6 | 1 |
| R2 | Backtest runner over the point-in-time universe, every NYSE session, `size_picks` → `step` → `close_unpriced`, delisting handled | 3 |
| R3 | SPY buy-and-hold curves (price-only and total-return), same 0.1% costs and whole-share rule | 2 |
| R4 | Tune on in-sample with the fixed 81-run grid, validate once on out-of-sample, freeze params in code | 4, 6 |
| R5 | Backtest report (curves vs SPY, return, CAGR, win rate, PF, max DD, trades, exit reasons, go-live criteria, IS/OOS separately, survivorship note, gate verdict), metrics identical to `web/lib/metrics.ts` | 4, 5, 6 |
| R6 | One real 10-year run on Neon, report committed, gate verdict stated, API documented in `engine/package_readme.md`, suite green with 0 skipped, CI green | 5, 6 |

## Scope

**In scope:** new packages `engine/src/seer_engine/strategies/` and `engine/src/seer_engine/backtest/`,
new command `engine/src/seer_engine/commands/backtest.py`, new tests under `engine/tests/`, vendored
`engine/data/spy_dividends.csv` (+ `SOURCES.md` entry), `numpy` declared in `engine/pyproject.toml`,
`engine/.cache/` in `.gitignore`, the committed report under `docs/backtests/`, the P3 sections of
`engine/package_readme.md`, and the P3 status line in `docs/ROADMAP.md`.

**Out of scope:** everything in the handover's "Out of scope" list. No edits to `seer_engine/sim/*`,
`dates.py`, `universe.py`, `membership.py`, `bars.py`, `prices.py`, `cli.py`, any DB writer, any
migration, `web/`, or `.github/workflows/`.

## Invariants

1. The tree builds and `PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q` passes with **0 skipped** at the end of every phase (`docker start seer-pg` first). Baseline: 374 passed. Expected after each phase (measured by the reconciler on scratch copies with the plans' code blocks applied): phase 1 → **448**; phase 2 → **480** if it lands before phase 3, **503** after it; phase 3 → **471** if it lands before phase 2, **503** after it; phase 4 → **570**; phase 5 → **595**; phase 6 → **598**. `engine/.venv` is the **worktree's own** venv: the worktree has none at first, so the first phase session in a tree runs `python3 -m venv engine/.venv && engine/.venv/bin/pip install -e 'engine[dev]'` from the worktree root (re-run the `pip install -e` after phase 1 adds `numpy` to the dependencies; it is already installed transitively). Never run tests with `/home/miftah/seer/engine/.venv`: it is an editable install of `/home/miftah/seer` and tests main's tree.
2. **Purity.** Every module in `seer_engine/strategies/` and every module in `seer_engine/backtest/` **except `backtest/io.py`** is pure: importing it loads no `psycopg`, `requests`, `yfinance` or `seer_engine.bars`; its source has no `time`/`random`/`logging`/`urllib`/`socket` import, no `.now/.utcnow/.today/.fromtimestamp`, no `print/open/input`. `engine/tests/test_strategy_purity.py` (phase 1) enforces it by **globbing** both directories, so modules added by later phases are covered without editing the test. Only `backtest/io.py` and `commands/backtest.py` touch the database or files.
3. **No simulator change.** `seer_engine/sim/*` is not edited. All sizing, fills, exits and costs go through it. The backtest never calls `apply_split`.
4. **Read-only on Neon.** Nothing in P3 writes to any database table.
5. **Determinism.** Same inputs → `==`-identical results and byte-identical report files. No set or dict-from-set iteration in an output path without sorting; no clock read in any pure module (the command passes dates in).
6. **Out-of-sample is never tuned on.** The grid runs on the in-sample window only. Selection reads in-sample metrics only. The out-of-sample window is run exactly once per report, with the selected parameters, and no code path feeds its metrics back into selection.
7. **Decimal at the sim boundary.** Everything handed to `seer_engine.sim` (`Pick` prices, `Bar` prices, cash) is a 4-dp `Decimal`. Floats exist only in indicator math, threshold comparisons and metrics.
8. Every handover §3 rule holds, and so does every row under **Decisions**.

## Shared interface contract (all phases plan against this)

```python
# ---- seer_engine/strategies/base.py  (phase 1; pure) -------------------------------------
import numpy as np
@dataclass(frozen=True, slots=True, eq=False)
class History:
    """One symbol's daily bars, ascending, one row per bar the symbol has (gaps allowed)."""
    symbol: str
    dates: np.ndarray    # dtype datetime64[D], strictly ascending
    open: np.ndarray     # float64, same length as dates
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    volume: np.ndarray   # float64
    def __len__(self) -> int: ...
    def upto(self, d: date) -> "History": ...     # the bars dated <= d (a view slice; searchsorted)
    def last_date(self) -> date | None: ...
    def index_of(self, d: date) -> int | None: ...  # row of the bar dated d, else None
def history_from_bars(symbol: str, bars: Sequence[Bar]) -> History   # float(Decimal) per field; arrays read-only
def as_day(d: date) -> np.datetime64                                    # date -> datetime64[D]; TypeError for datetime

class Strategy(Protocol):
    id: str          # "A"
    lookback: int    # bars per symbol picks() needs, ending at data_date (A: 200)
    def picks(self, history: Mapping[str, History], members: AbstractSet[str],
              data_date: date, params: Any) -> list[Pick]: ...
    def prepare(self, history: Mapping[str, History]) -> Any: ...   # param-independent precompute
    def picks_prepared(self, prepared: Any, members: AbstractSet[str],
                       data_date: date, params: Any) -> list[Pick]: ...
# CONTRACT: for every d, picks_prepared(prepare(H), M, d, p) == picks({s: h.upto(d) for s, h in H.items()}, M, d, p).
# picks() may be given longer histories than `lookback`; it only reads the last `lookback` bars dated <= data_date.

# ---- seer_engine/strategies/indicators.py  (phase 1; pure numpy) -------------------------
# Window functions take 2-D float64 arrays shaped (rows, W) — one row per window, oldest column first —
# and return one float64 per row. They use only elementwise numpy ops and an explicit loop over the
# columns (NO np.sum/np.mean/cumsum/convolve along the time axis), so a row's result is bit-identical
# whatever the number of rows. NaN when W is too short for n.
def sma_window(close, n) -> np.ndarray                       # mean of the last n columns, summed left→right, / n
def wilder_rsi_window(close, n) -> np.ndarray                 # see Decisions "Indicator definitions"
def wilder_atr_window(high, low, close, n) -> np.ndarray
def mean_dollar_volume_window(close, volume, n) -> np.ndarray # mean of close×volume over the last n columns
def rolling(fn, *series, window: int, **kw) -> np.ndarray     # 1-D series of length T -> length-T result,
                                                              # NaN for t < window-1; fn applied to sliding_window_view rows

# ---- seer_engine/strategies/a.py  (phase 1; pure) ----------------------------------------
LOOKBACK = 200; SMA_N = 200; RSI_N = 2; ATR_N = 14; DV_N = 20
@dataclass(frozen=True, slots=True)
class AParams:
    rsi_max: float = 10.0                       # setup: RSI(2) < rsi_max (strict)
    limit_atr: Decimal = Decimal("0.5")         # limit = last − limit_atr × ATR
    tp_atr: Decimal = Decimal("1.0")            # tp    = limit + tp_atr × ATR
    sl_atr: Decimal = Decimal("1.5")            # sl    = limit − sl_atr × ATR
    min_dollar_volume: float = 20_000_000.0     # setup: 20-day mean close×volume > this (strict)
    def as_dict(self) -> dict[str, str]: ...    # normalized plain decimals, fixed key order:
        # DESIGN_PARAMS -> {"rsi_max": "10", "limit_atr": "0.5", "tp_atr": "1", "sl_atr": "1.5", "min_dollar_volume": "20000000"}
    # __post_init__: rsi_max/min_dollar_volume coerced to float (bool/str TypeError); ATR multipliers must be Decimal
DESIGN_PARAMS = AParams()
STRATEGY_A_PARAMS: AParams = DESIGN_PARAMS      # phase 6 replaces with the frozen selection + a comment naming the report
@dataclass(frozen=True, slots=True)
class Features:
    symbol: str; data_date: date
    close: float; sma: float; rsi: float; atr: float; dollar_volume: float
def features_at(history: Mapping[str, History], data_date: date) -> list[Features]  # sorted by symbol; only symbols
    # with a bar ON data_date and >= LOOKBACK bars through it; computed on the last LOOKBACK bars
def picks_from_features(features: Iterable[Features], members: AbstractSet[str], params: AParams) -> list[Pick]
class APrepared:   # columnar features per eligible (symbol, date); features_on(d) == features_at(upto(d), d)
def prepare_a(history) -> APrepared; def picks_prepared_a(prepared, members, data_date, params) -> list[Pick]
class StrategyA:   # implements Strategy; id = "A", lookback = LOOKBACK; prepare() -> APrepared
STRATEGY_A = StrategyA()

# ---- seer_engine/backtest/__init__.py  (phase 1) — docstring only, no imports ----------

# ---- seer_engine/backtest/benchmark.py  (phase 2; pure) -----------------------------------
@dataclass(frozen=True, slots=True) class Dividend: ex_date: date; amount: Decimal   # USD per share
def parse_dividends(text: str) -> tuple[Dividend, ...]   # CSV header "ex_date,amount_usd"; ascending, unique, > 0
@dataclass(frozen=True) class BenchmarkCurve:
    name: str                          # "spy_price" | "spy_tr"
    snapshots: tuple[Snapshot, ...]    # [0] = Snapshot(prev_session(start), cash0, cash0); then one per session
    shares: int; cash: Decimal; dividends_usd: Decimal
def buy_and_hold(spy: Mapping[date, Bar], start: date, end: date, initial_cash: Decimal,
                 *, dividends: Sequence[Dividend] = (), name: str) -> BenchmarkCurve
def spy_curves(spy, start, end, initial_cash, dividends) -> tuple[BenchmarkCurve, BenchmarkCurve]  # (price, tr)

# ---- seer_engine/backtest/market.py  (phase 3; pure) --------------------------------------
SPY = "SPY"
@dataclass(frozen=True) class Membership:
    intervals: tuple[tuple[str, date, date | None], ...]   # (symbol, start, end-exclusive|None), index ids unioned;
                                                           # raw per-index rows or merged spells both accepted
    def members_on(self, d: date) -> frozenset[str]: ...    # fast: all 2,950 sessions in well under 2 s
    def symbols(self) -> tuple[str, ...]: ...               # every ever-member, sorted (listing helper only)
@dataclass(frozen=True, eq=False) class Market:
    history: Mapping[str, History]                 # every symbol with bars, SPY included
    membership: Membership
    fx: tuple[tuple[date, Decimal], ...]           # (date, usd_idr) ascending
    def bar(self, symbol: str, d: date) -> Bar | None: ...         # Decimal via prices.to_decimal(float); int volume
    def bars_on(self, d: date, symbols: Iterable[str]) -> dict[str, Bar]: ...
    def last_bar_date(self, symbol: str) -> date | None: ...
    def usd_idr_on(self, d: date) -> Decimal: ...  # latest fx row dated <= d; ValueError when none
    def spy(self) -> dict[date, Bar]: ...          # every SPY bar as Decimal Bars (benchmark input)

# ---- seer_engine/backtest/runner.py  (phase 3; pure) --------------------------------------
INITIAL_IDR = Decimal("20000000")
@dataclass(frozen=True) class RunResult:
    strategy_id: str; params: Any; start: date; end: date
    usd_idr: Decimal; initial_cash: Decimal
    snapshots: tuple[Snapshot, ...]      # [0] = Snapshot(prev_session(start), cash0, cash0); then one per session
    events: tuple[Event, ...]            # every event in order, forced closes included
    closed: tuple[Order, ...]            # closed orders in exit order
    open_at_end: tuple[Order, ...]       # still open after `end` (marked at close, never liquidated)
    rejections: tuple[tuple[str, int], ...]   # (reason, count), sorted by reason
def run_backtest(market: Market, strategy: Strategy, params: Any, start: date, end: date,
                 *, prepared: Any = None, initial_idr: Decimal = INITIAL_IDR) -> RunResult
    # start and end must be NYSE sessions, start <= end (ValueError otherwise)
@dataclass(frozen=True) class YearGap:
    year: int; member_sessions: int; missing: int; missing_never_fetched: int; missing_other: int
def survivorship(market: Market, start: date, end: date) -> tuple[YearGap, ...]   # (member, session) pairs with no bar, per year

# ---- seer_engine/backtest/metrics.py  (phase 4; pure, floats) -----------------------------
@dataclass(frozen=True) class Metrics:
    total_return: float | None; win_rate: float | None; profit_factor: float | None   # math.inf when no loss
    max_drawdown: float | None; trades: int; months: float
    cagr: float | None; avg_days_held: float | None; exit_reasons: tuple[tuple[str, int], ...]
def strategy_metrics(snaps: Sequence[tuple[date, float]], pnls: Sequence[float]) -> Metrics   # metrics.ts parity
@dataclass(frozen=True) class CheckItem: label: str; val: str; ok: bool
def checklist(m: Metrics, spy_return: float | None) -> list[CheckItem]                       # metrics.ts parity
def run_metrics(r: RunResult) -> Metrics
def curve_metrics(c: BenchmarkCurve) -> Metrics
# + MONTH_DAYS = 30.44, YEAR_DAYS = 365.25, EXIT_REASONS, cagr_between, avg_days_held, exit_reason_counts,
#   forced_closes, to_fixed (JS toFixed port), fmt_signed_pct, fmt_pct, fmt_pf, fmt_num

# ---- seer_engine/backtest/tuning.py  (phase 4; pure) --------------------------------------
IS_START = date(2015, 10, 19); OOS_START = date(2022, 1, 3)    # IS end = prev_session(OOS_START) = 2021-12-31
GRID_RSI = (5.0, 10.0, 15.0); GRID_LIMIT = (Decimal("0.25"), Decimal("0.5"), Decimal("0.75"))
GRID_TP = (Decimal("0.75"), Decimal("1.0"), Decimal("1.5")); GRID_SL = (Decimal("1.0"), Decimal("1.5"), Decimal("2.0"))
MAX_DRAWDOWN = 0.15; MIN_PROFIT_FACTOR = 1.3
def grid() -> tuple[AParams, ...]                  # 81, nested rsi → limit → tp → sl, each ascending
@dataclass(frozen=True) class GridRow: params: AParams; metrics: Metrics
@dataclass(frozen=True) class Selection: params: AParams; qualified: bool; reason: str
def select(rows: Sequence[GridRow]) -> Selection   # IS metrics only
@dataclass(frozen=True) class Verdict: passed: bool; checks: tuple[CheckItem, ...]; sentence: str
def gate(oos: Metrics, spy_tr_oos: Metrics) -> Verdict

# ---- seer_engine/backtest/report.py  (phase 4; pure) --------------------------------------
@dataclass(frozen=True) class WindowResult: name: str; run: RunResult; spy_price: BenchmarkCurve; spy_tr: BenchmarkCurve
@dataclass(frozen=True) class BacktestReport:
    data_end: date; bars_rows: int; symbols_with_bars: int
    grid_rows: tuple[GridRow, ...]; selection: Selection; frozen_params: AParams
    in_sample: WindowResult; out_of_sample: WindowResult; full: WindowResult
    survivorship: tuple[YearGap, ...]; never_fetched_members: int; verdict: Verdict
def render_markdown(report: BacktestReport) -> str
def equity_csv(report: BacktestReport) -> str
def equity_svg(report: BacktestReport) -> str
def report_stem(data_end: date) -> str             # f"{data_end.isoformat()}-strategy-a"
FROZEN_KEY = "frozen-params"; SELECTED_KEY = "selected-params"
def params_line(key: str, params: AParams) -> str  # f"{key}: {json.dumps(params.as_dict())}"
def parse_params_line(markdown: str, key: str) -> dict[str, str]   # ValueError unless exactly one such line
# render_markdown emits each machine line exactly once, unindented, inside a ```text fence; it raises unless every
# window run used selection.params. WindowResult.name is rendered as given ("In-sample" | "Out-of-sample" | "Full window").

# ---- seer_engine/backtest/io.py  (phase 5; impure: DB + files) ---------------------------
CACHE_DIR = config.REPO_ROOT / "engine" / ".cache"
DIVIDENDS_CSV = config.REPO_ROOT / "engine" / "data" / "spy_dividends.csv"
def load_market(conn, *, cache_dir: Path = CACHE_DIR, refresh: bool = False) -> tuple[Market, int]   # (market, bars rows)
def read_dividends(path: Path = DIVIDENDS_CSV) -> tuple[Dividend, ...]
def write_report(out_dir: Path, report: BacktestReport) -> list[Path]   # <stem>.md, <stem>-equity.csv, <stem>-equity.svg

# ---- seer_engine/commands/backtest.py  (phase 5) -----------------------------------------
# python -m seer_engine backtest [--out DIR] [--cache-dir DIR] [--refresh-cache] [--is-start D] [--oos-start D]
#                                [--end D] [--dividends PATH]
WINDOW_NAMES = ("In-sample", "Out-of-sample", "Full window")   # the one owner of the window labels
def resolve_windows(market, is_start, oos_start, end) -> Windows   # BacktestError (exit 2) unless all are sessions,
                                                                   # is_start < oos_start <= end <= last SPY bar, fx exists
def never_fetched_members(market, start, end) -> int               # the one definition of the report's count
```

## Phases

| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID | Card |
|---|-------|-----------|---------|-------|-----------|------------|------|--------|------|
| 1 ✓ | Strategy interface, indicators, Strategy A | R1 | `seer_engine.strategies` | 10 | — | HARD | `.workflows/plan/strategy-a-backtest/phase-1.md` | P1-ENG-WHQG | — |
| 2 ✓ | SPY buy-and-hold benchmark + vendored dividends | R3 | `seer_engine.backtest` | 4 | 1 | NORMAL | `.workflows/plan/strategy-a-backtest/phase-2.md` | P1-ENG-3WDD | — |
| 3 ✓ | Point-in-time market + backtest runner + survivorship | R2 | `seer_engine.backtest` | 4 | 1 | HARD | `.workflows/plan/strategy-a-backtest/phase-3.md` | P1-ENG-HCER | — |
| 4 | Metrics (web parity), grid + selection + gate, report rendering | R4, R5 | `seer_engine.backtest` | 6 | 2, 3 | NORMAL | `.workflows/plan/strategy-a-backtest/phase-4.md` | P1-ENG-VTZ5 | — |
| 5 | Neon loader with cache + `backtest` command | R5, R6 | `seer_engine.backtest`, `seer_engine.commands` | 5 | 4 | NORMAL | `.workflows/plan/strategy-a-backtest/phase-5.md` | P1-ENG-5LGI | — |
| 6 | Real 10-year run, freeze params, committed report, docs | R4, R5, R6 | `seer_engine.strategies`, docs | 7 | 5 | NORMAL | `.workflows/plan/strategy-a-backtest/phase-6.md` | P1-ENG-KG5T | — |

Phases 2 and 3 share no file and run concurrently after phase 1. Phase 4 couples R4 and R5 because
selection, the gate and the report are all built on the same `Metrics`; splitting them would leave a
phase that only defines a dataclass.

### Phase 1 — Strategy interface, indicators, Strategy A
**Satisfies:** R1
**Owns:** `engine/pyproject.toml` (declare `numpy>=2`), `engine/src/seer_engine/strategies/{__init__,base,indicators,a}.py` (new), `engine/src/seer_engine/backtest/__init__.py` (new, docstring only), `engine/tests/stratkit.py` (new synthetic `History` builders), `engine/tests/test_indicators.py`, `engine/tests/test_strategy_a.py`, `engine/tests/test_strategy_purity.py` (new; globs `strategies/*.py` and `backtest/*.py` minus `io.py`).
**Does not touch:** `sim/*`, `test_sim_purity.py`, any other `backtest/` module, readme.
**Exit criteria:** handover §6 items 1, 2, 3 and 8 (for the strategy modules): each indicator matches hand-computed values on short synthetic windows including the warm-up boundary (NaN before enough bars); `rolling(...)[t]` is bit-identical (`==`, not approx) to the window function on the last W bars ending at t; changing any bar dated ≥ S leaves the picks for session S (data_date = prev_session(S)) unchanged; `picks_prepared(prepare(H), …) == picks(upto(d), …)` on every date of a multi-symbol synthetic set; setup filter tests for each condition alone; limit/TP/SL to 4 dp; RSI ranking with symbol tie-break; invalid prices dropped; non-members excluded, including a symbol joining and one leaving mid-window. 74 new tests; suite **448 passed**, 0 skipped.

### Phase 2 — SPY buy-and-hold benchmark + vendored dividends
**Satisfies:** R3
**Owns:** `engine/src/seer_engine/backtest/benchmark.py` (new), `engine/data/spy_dividends.csv` (new, fetched once with yfinance `Ticker("SPY").dividends`, 2015-01-01 → today), `engine/data/SOURCES.md` (add its entry), `engine/tests/test_benchmark.py` (new).
**Does not touch:** `market.py`, `runner.py`, anything in `strategies/`.
**Exit criteria:** handover §6 item 5: price-only and total-return curves on synthetic bars plus a dividend, including whole-share purchase at the first session's open after the 0.1% cost, an idle cash remainder, a dividend on the ex-date reinvested at that close (whole shares, with cost), a dividend dated on the start session not credited, a missing SPY bar raising, an in-window ex-date that is not a session raising, and the vendored CSV parsing cleanly (ascending, unique, positive, every ex-date a session, covers 2015–2026). 32 new tests; suite **480** (or **503** after phase 3), 0 skipped.

### Phase 3 — Point-in-time market + backtest runner + survivorship
**Satisfies:** R2
**Owns:** `engine/src/seer_engine/backtest/market.py`, `engine/src/seer_engine/backtest/runner.py` (new), `engine/tests/test_backtest_market.py`, `engine/tests/test_backtest_runner.py` (new).
**Does not touch:** `benchmark.py`, `strategies/*` (consumes them), `stratkit.py` (may import its builders; add local helpers in its own test files).
**Exit criteria:** handover §6 items 4 and 7 (runner side): `Membership.members_on` honours `[start, end)` and unions both indices; `Market.bar` returns exact 4-dp Decimals from floats; a synthetic multi-symbol backtest through `size_picks` → `step` → `close_unpriced` with hand-checked final cash, equity and trade list, including a held symbol whose bars end (forced `close_unpriced` exactly once, at the first session after its last bar) and a session with 0 picks; a 3-session halt (bars resume) does not force-close; members are evaluated on `data_date`; the run with `prepared=` equals the run without it; two runs are `==`; non-session windows raise; `survivorship` counts per year are hand-checked. 23 new tests; suite **471** (or **503** after phase 2), 0 skipped.

### Phase 4 — Metrics (web parity), grid + selection + gate, report rendering
**Satisfies:** R4, R5
**Owns:** `engine/src/seer_engine/backtest/{metrics,tuning,report}.py` (new), `engine/tests/test_backtest_metrics.py`, `engine/tests/test_backtest_tuning.py`, `engine/tests/test_backtest_report.py` (new).
**Does not touch:** `market.py`, `runner.py`, `benchmark.py`, `strategies/*`.
**Exit criteria:** handover §6 item 6: `strategy_metrics`/`checklist` reproduce every case of `web/lib/metrics.test.ts` with the same inputs; CAGR, avg days held and exit-reason counts tested; `grid()` is the exact 81 in the stated order; `select` picks the highest IS return among `max_dd ≤ 0.15 and PF ≥ 1.3` with the stated tie-break, and falls back to `DESIGN_PARAMS` when none qualifies; `gate` passes only when OOS return > OOS total-return SPY, PF ≥ 1.3 and max DD ≤ 0.15; `render_markdown`/`equity_csv`/`equity_svg` are deterministic and contain every required section (built from a small synthetic `BacktestReport`); the `frozen-params:`/`selected-params:` lines round-trip through `parse_params_line`. 67 new tests; suite **570**, 0 skipped.

### Phase 5 — Neon loader with cache + `backtest` command
**Satisfies:** R5, R6
**Owns:** `engine/src/seer_engine/backtest/io.py`, `engine/src/seer_engine/commands/backtest.py` (new), `.gitignore` (add `engine/.cache/`), `engine/tests/test_backtest_io.py`, `engine/tests/test_backtest_command.py` (new; DB tests on the `pg` fixture).
**Does not touch:** the pure modules (except a bug fix found by the end-to-end test, recorded in the commit), readme, ROADMAP, `strategies/a.py`'s params.
**Exit criteria:** `load_market` on a seeded test schema returns the right `Market` (bars via one streamed `COPY ... TO STDOUT`, universe, fx); the cache is written to and reused from `cache_dir` keyed by `(max(date), count(*))`, and a changed fingerprint invalidates it; the command, pointed at a synthetic test DB with short windows, writes the three report files, logs the gate verdict, exits 0, and writes nothing to the DB; the command module passes `discover()`; the grid's wall time is logged per run and in total; window names are `WINDOW_NAMES`; `--cache-dir` keeps the test cache out of the repo. 25 new tests; suite **595**, 0 skipped.

### Phase 6 — Real 10-year run, freeze params, committed report, docs
**Satisfies:** R4, R5, R6
**Owns:** `engine/src/seer_engine/strategies/a.py` (`STRATEGY_A_PARAMS` only, written in the grid constants' spelling), `docs/backtests/<end>-strategy-a.md`, `<end>-strategy-a-equity.csv`, `<end>-strategy-a-equity.svg` (new, produced by the command), `engine/tests/test_strategy_a_frozen.py` (new: the frozen params equal the ones recorded in the committed report), `engine/package_readme.md` (strategy interface, indicators, Strategy A, backtest modules, command, report), `docs/ROADMAP.md` (P3 status + verdict).
**Does not touch:** any other source module. If the real run exposes a bug, fix it in the owning module and record it in the commit message; never change a rule to move the result.
**Exit criteria:** one real run on Neon (`SEER_ENV_FILE=/home/miftah/seer/.env.local`, read-only), report committed, `STRATEGY_A_PARAMS` equals the selection with a comment naming the report, a re-run reproduces byte-identical report files, the verdict sentence is in the report and in ROADMAP P3. If the gate fails, ROADMAP says so and that P4 must not start. readme documents everything above, `--cache-dir` included. 3 new tests (`test_strategy_a_frozen.py`, via `report.parse_params_line`); suite **598**, 0 skipped.

## Reconciliation Log

Round 1. Method: every phase's code blocks (phases 1–5) were applied to scratch copies of `engine/`
at `d3a2e1d`, with a dedicated venv and `seer-pg`, and the full suite was run on each tree: base 374,
P1 448, P1+P2 480, P1+P3 471 (so phases 2 and 3 each build green on phase 1 alone), P1–3 503,
P1–4 570, P1–5 595, all 0 skipped. Phase 2's yfinance fetch reproduced the planner's probe exactly
(47 rows 2015-03-20 → 2026-09-18, sha256 `3251a852…598a`). Phase 6's frozen-params test was run
against a report rendered by phase 4's code with a literal `STRATEGY_A_PARAMS` naming it: 598 passed.
After the edits below the trees were rebuilt from the edited plans and re-run with the same counts.

| # | Conflict | Class | Phases | Resolution |
|---|---|---|---|---|
| 1 | Window labels: phase 4 renders and tests `"In-sample"`/`"Out-of-sample"`/`"Full window"`; phase 5 passed `("in_sample", "out_of_sample", "full")` and asserted them in its e2e test | Contract drift | 4, 5 | Phase 5's `commands/backtest.WINDOW_NAMES` is the one owner and now holds phase 4's labels; its e2e assertion and handoffs edited. No phase-4 code change. Decision "Window names" |
| 2 | Membership input: phase 5 merges overlapping/touching SP500+NDX spells per symbol; phase 3 documented raw rows | Unmet assumption (checked) | 3, 5 | No conflict: phase 3's sweep counts overlaps per symbol, so raw and merged give the same `members_on` and `survivorship`. Merge kept; both plans' notes reworded. Decision "Membership input" |
| 3 | Never-fetched count defined twice: phase 3's handoff said `Membership.symbols() − history` (ever-members), phase 5 computes window-restricted `never_fetched_members` | Duplicate work / contract drift | 3, 5 | Phase 5's window-restricted function is the single definition (it matches phase 4's report wording "members in the window"); phase 3's contract and handoff now call `symbols()` a listing helper only. Phase 6 readme wording aligned. Decision "Never-fetched count" |
| 4 | numpy 2 `repr(np.float64)` is `'np.float64(…)'`; `to_decimal` must get `float(x)` | Unmet assumption (checked) | 1, 3 | Holds: phase 1 builds `Features` with `float(...)` everywhere, phase 3's `Market.bar` uses `float(...)` and `spy()` uses `.tolist()`. Phase 3 handoff reworded from "risk" to "checked" |
| 5 | Phase 4 hand-builds `RunResult` (11 fields), `YearGap`, `BenchmarkCurve`, `sim.Order`/`Event` by keyword | Unmet assumption (checked) | 2, 3, 4 | Holds: plain frozen dataclasses, no `__post_init__`; phase 4's 67 tests pass on phases 1–3 |
| 6 | Machine-readable lines: phase 6 wrote its own permissive regex (HTML comment / backticks) and expected `as_dict` to use `str(Decimal)` | Contract drift | 4, 6 | Phase 6's test now imports `report.FROZEN_KEY`, `SELECTED_KEY`, `parse_params_line` (no second regex); its Requires states phase 4's exact format. Decision "Machine-readable params lines" |
| 7 | Phase 6 Step 3 said copy Decimal text as the JSON shows (`"1.0"`), but phase 1's `as_dict` normalizes (`Decimal("1.0")` → `"1"`) | Contract drift | 1, 6 | Phase 6 Step 3 rewritten: JSON is normalized; write the literal in the grid constants' spelling; value equality makes either spelling pass. Example fixed. Decision "Frozen literal spelling" |
| 8 | Pre/post-freeze `.md` diff: phase 6 expected only the `frozen-params:` line and a sentence; phase 4 also renders a "Frozen in code" column | File collision (expectation) | 4, 6 | Column kept (phase 4's test pins it). Phase 6 Step 5 and Verification now expect `2 + <params that differ>` changed lines. Decision "Pre/post-freeze report diff" |
| 9 | `--cache-dir` added by phase 5; absent from the index CLI line, phase 6's Requires and readme | Contract drift | 5, 6 | Accepted. Index contract, phase 6 Requires and readme (8d usage + cache bullet) updated. Decision "`--cache-dir`" |
| 10 | Phase 1 drops a pick whose `last` rounds to 0; index "Invalid picks" row and phase 6 readme "Dropped" row omitted it | Contract drift | 1, 6 | Index Decisions row and phase 6 readme row now list `last ≤ 0` |
| 11 | Phase 2 raises on an in-window ex-date that is not a session; phase 3 `run_backtest` requires session bounds | Unmet assumption (checked) | 2, 3, 5 | Holds: the vendored file test asserts every ex-date is a session; phase 5 `resolve_windows` checks all three flags are sessions and derives `is_end = prev_session(oos_start)`. Decisions "Non-session dividend" and "Window bounds" |
| 12 | Phase 1's purity glob forbids the attribute `random` and `print/open/input` calls in every later pure module | Unmet assumption (checked) | 1, 2, 3, 4 | Holds: `benchmark`, `market`, `runner`, `metrics`, `tuning`, `report` pass `test_strategy_purity.py` in the P1–5 tree. Decision "Purity scan" |
| 13 | Expected test counts absent or conditional in phases 2–6 and Invariant 1 | Gap | all | Measured counts written into Invariant 1, every phase's exit criteria and verification |
| 14 | Index shared contract missed names the plans create and others consume (`as_day`, `APrepared`, `SPY`, `Membership.symbols`, report's params-line API, `WINDOW_NAMES`, `resolve_windows`, `never_fetched_members`, metrics helpers) | Gap | 1, 3, 4, 5 | Added to the contract block |
| 15 | Phase table file count for phase 6 (6 vs the plan's 7, three generated) | Contract drift | 6 | Set to 7 |
| 16 | Phase 6 readme module graph omitted `config`/`universe` imports of `commands.backtest`; layout called `strategies/__init__.py` a "package marker" though it re-exports | Contract drift | 5, 6 | Readme text corrected (the code wins) |
| 17 | Grid runtime: the Decisions row said "parallelize" above 60 min; phase 5 called it phase 6's call; phase 6 said record and hand off | Contract drift | 5, 6 | Settled on phase 6's text (record + follow-up, never parallelize mid-phase); Decisions row and phase 5 handoff edited |
| 18 | Requirement coverage | Unowned / creep check | all | Every R1–R6 has an owner; no phase serves an `R` outside its **Satisfies** line. No change |

## Decisions

| Fork | Chosen | Rung |
|---|---|---|
| Strategy interface (§7) | `Strategy` protocol in `strategies/base.py` with `picks(history, members, data_date, params)` for P4, plus `prepare`/`picks_prepared` for the backtest's fast path, bound by the equality contract above. `history` is `Mapping[str, History]` of float64 numpy arrays | 5: handover §7 recommendation; split into two entry points so the backtest is fast and P4 is simple, with a test proving they agree |
| P4 identity of recursive indicators (§7 "per-night recomputation must give identical numbers") | Every indicator for `data_date` is a function of the symbol's **last `LOOKBACK = 200` bars ending at `data_date`** only. Wilder recursions are seeded inside that window. Window functions use only elementwise ops plus an explicit column loop, so the backtest (sliding windows over full history) and P4 (one window of the last 200 bars) produce bit-identical floats | 5: handover §7 + §3 eligibility (200 bars). A full-history seed would make P4 depend on how much history it loads |
| Indicator definitions | SMA(n): sum of the last n closes left to right, / n. RSI(n) Wilder: changes `d_i = c_i − c_{i−1}` for i = 1..W−1; seed `avgG`/`avgL` = mean of the first n gains/losses; then `avg = (avg·(n−1) + x_i) / n`; RSI = 100 if `avgL == 0`, else `100 − 100 / (1 + avgG/avgL)`. ATR(n) Wilder: `TR_i = max(h_i − l_i, |h_i − c_{i−1}|, |l_i − c_{i−1}|)` for i = 1..W−1 (the window's first bar has no TR); seed = mean of the first n TRs; Wilder after. Dollar volume(n): mean of `close × volume` over the last n bars. NaN when the window is too short | 5: handover §3 "Indicator definitions" row, made exact |
| Eligibility | Member on `data_date`, a bar dated `data_date`, and ≥ 200 bars through `data_date` | 5: handover §3 |
| Float vs Decimal (§7) | Indicators and setup comparisons in float64; comparisons are strict (`close > sma`, `rsi < rsi_max`, `dv > min_dollar_volume`), so RSI exactly 10.0 is excluded. Prices: `last = to_decimal(close)` (exact: `numeric(12,4)` survives the float round trip through `repr`), `atr_d = to_decimal(atr)`, `limit = q(last − limit_atr·atr_d)`, `tp = q(limit + tp_atr·atr_d)`, `sl = q(limit − sl_atr·atr_d)`. A float could flip a threshold only within ~1e-12 of it, and does so identically in backtest and nightly because the floats are bit-identical. Documented in the readme | 5: handover §7 recommendation + §3 "Prices" row |
| Invalid picks | Dropped silently (never raised) by the strategy when, after `q`, `last ≤ 0`, `limit ≤ 0`, `sl ≤ 0`, `sl ≥ limit` or `tp ≤ limit` (`sim.Pick` would raise) | 5: handover §3 "Prices" row, extended to `sl ≤ 0` and `last ≤ 0` (phase 1 code block) because `Pick` requires every price > 0 |
| Ranking and list length | Sort by `(rsi, symbol)` ascending; return every qualifying candidate (no cap). Held symbols are not filtered by the strategy: `size_picks` rejects them as `held` without using a slot, so the next candidate fills it | 5: handover §3 ties row + design §4 "fill free slots"; 3: sim `size_picks` semantics |
| Loading bars (§7) | One streamed `COPY (SELECT … ORDER BY symbol, date) TO STDOUT` into a pandas frame (`float_precision="round_trip"`, `na_filter=False`), inside one `REPEATABLE READ, READ ONLY` transaction always ended by rollback, cached as a pickle `<cache dir>/bars-<max date>-<rows>.pkl` (default `engine/.cache/`, gitignored), re-validated by a cheap `count(*), max(date)` query. No pyarrow | 6: convention (no new dependency) + 5: handover §7 |
| Memory | Bars live as float64 arrays in `History`; `Market.bar` builds a Decimal `Bar` on demand, only for symbols with a live order and for SPY | 1: invariant 7 with the measured data size |
| SPY dividends (§7) | Vendored `engine/data/spy_dividends.csv` (`ex_date,amount_usd`) fetched once from yfinance, with a `SOURCES.md` entry. No new table | 5: handover §7 recommendation |
| Dividend crediting | A dividend counts when `start < ex_date ≤ end` (the holder at the previous close); cash `+= q(shares × amount)`, then buy `floor(cash / (close × 1.001))` more shares at that session's close with `buy_cost`. Price-only ignores dividends | 5: handover §3 benchmark rows |
| Gone vs halted (§7) | A held symbol is gone at session S when `last_bar_date(symbol) < S`; `close_unpriced` runs right after S's `step` and the last snapshot is replaced. A halt (bars resume later) is left to the simulator's missing-bar rule | 5: handover §7 recommendation |
| Curve start point | Every curve (strategy and both SPY) starts with `Snapshot(prev_session(start), cash0, cash0)`, so total return = last/first − 1 measures from the starting cash | 6: convention; matches handover §3 "total return = last/first − 1" |
| Starting FX | `usd_idr` = the latest `fx_rates` row dated on or before the window's start session | 6: convention (`fx_rates` holds publishing days only) |
| End of window | Open positions and the SPY holding are marked at the last close, never liquidated, for both — identical treatment | 5: handover §3 benchmark row ("same costs … as the strategy") |
| Windows | In-sample 2015-10-19 → 2021-12-31; out-of-sample 2022-01-03 → last SPY bar; full 2015-10-19 → last SPY bar, one continuous portfolio. Each window has its own fresh 20,000,000 IDR portfolio and its own SPY curves starting the same session. 2015-10-19 = `next_session` of the 200th session from 2015-01-02 (measured) | 5: handover §3 window row |
| Selection tie-break | Highest IS total return; ties → lower IS max drawdown → earlier grid index | 6: determinism (invariant 5) |
| Grid runtime (§7) | `prepare` once (param-independent features), then 81 IS runs. Phase 5 logs wall time per run and in total (planners measured ~1 s per run: 3.7 s `prepare`, 0.64 s of picks and 0.27 s of runner per in-sample run, so ~1.5 min for the grid). If the real grid exceeds 60 min, the run is still valid; phase 6 records the time and leaves a follow-up to parallelize across processes with results gathered in grid order (it does not parallelize itself). The grid itself never shrinks after it was declared | 1: invariant 6 (the grid was fixed before results); 2: phase 6's exit criteria (parallelizing changes no number, so it is not phase 6 work) |
| Report format (§7) | `docs/backtests/<data end>-strategy-a.md` with the grid table in the same file, plus `-equity.csv` (wide: `date` + one column per curve) and `-equity.svg` (hand-written SVG, no new dependency). The stem uses the data end date so a re-run on the same data is byte-identical | 5: handover §7 + invariant 5 |
| Gate | Passes only when, on **out-of-sample**: total return > total-return SPY, PF ≥ 1.3, max DD ≤ 0.15. Trade count and months are shown for information (go-live #1 is forward-only) | 5: handover §3 gate row |
| Command exit code | 0 whether the gate passes or fails (a losing verdict is a result); 1 on error; 2 on a precondition (no bars, no SPY bars, a window date that is not a session or is after the last SPY bar, `is_start < oos_start <= end` violated, no fx on or before the in-sample start, missing dividends file) | 6: convention (`cli.main` exit codes) |
| Worktree env for the real run | `SEER_ENV_FILE=/home/miftah/seer/.env.local`, because `config.REPO_ROOT` resolves to the worktree, which has no `.env.local` | 1: invariant 4 + measured `config.env_file()` |
| Frozen params when the gate fails | Still freeze the selected parameters (they are what P3 measured) and record the failing verdict; ROADMAP P3 says rework before P4 | 5: handover §2 gate |
| Window names | `WindowResult.name` is `"In-sample"`, `"Out-of-sample"`, `"Full window"`, defined once in `commands/backtest.WINDOW_NAMES` (phase 5) and rendered as given by `report.py` | 3: the plans' code blocks (phase 4's headings and tests assert these labels; the report is read by people) |
| Membership input | `io.read_intervals` merges each symbol's overlapping or touching spells across both indices; `Membership` accepts merged or raw rows with identical results | 3: the plans' code blocks (phase 3's per-symbol sweep, phase 5's tested merge) |
| Never-fetched count | `never_fetched_members` = symbols that are members at some point of the full window and have no bars at all, computed only in `commands/backtest.never_fetched_members`; `Membership.symbols()` is a listing helper | 3: the plans' code blocks (phase 4 renders "Index members in the window with no bars at all") |
| Machine-readable params lines | `frozen-params: <json>` and `selected-params: <json>`, `json.dumps(as_dict())` with default separators, each exactly once, unindented, inside a ```` ```text ```` fence; read back only with `report.parse_params_line` | 3: the plans' code blocks (phase 4's renderer and round-trip test) |
| Params rendering | `AParams.as_dict()` writes normalized plain decimals in fixed key order (`Decimal("1.0")` → `"1"`, `5.0` → `"5"`); the report and the frozen test go through it, never hand formatting | 3: the plans' code blocks (phase 1's `test_design_params_are_the_design_values`) |
| Frozen literal spelling | Phase 6 writes `STRATEGY_A_PARAMS` as an explicit `AParams(...)` literal in the grid constants' spelling (`Decimal("1.0")`, `15.0`); `AParams` equality compares Decimals by value, so the normalized JSON and the literal agree | 6: surrounding convention (`tuning.GRID_*` spelling) on top of 3: phase 1's dataclass equality |
| Pre/post-freeze report diff | Freezing changes exactly the `frozen-params:` line, the "Frozen in code" sentence and the selection-table rows whose "Frozen in code" cell differs (`2 + n` lines); CSV and SVG are byte-identical; the fallback case changes nothing | 2: phase exit criteria (phase 6 byte-identity) with 3: phase 4's `test_frozen_params_change_only_their_own_lines` |
| `--cache-dir` | The command takes `--cache-dir DIR` (default `engine/.cache`) so tests keep the pickle out of the repo; documented in the readme | 3: the plans' code blocks (phase 5's e2e test needs it); harmless for the real run |
| Non-session dividend | `buy_and_hold` raises `ValueError` when a dividend with `start < ex_date ≤ end` is not an NYSE session (never silently skipped); the vendored file's test asserts every ex-date is a session | 5: handover §3 benchmark rows (credit on the ex-date session) via 3: phase 2's code block |
| Window bounds | `run_backtest` and `buy_and_hold` require `start`/`end` to be NYSE sessions; the command's `resolve_windows` validates `--is-start`/`--oos-start`/`--end` (default: last SPY bar) and derives the in-sample end as `prev_session(oos_start)`, exiting 2 otherwise | 3: the plans' code blocks (phases 2, 3, 5) |
| Purity scan | The globbing purity test forbids, in every pure module: imports of `time`/`random`/`logging`/`urllib`/`socket`/psycopg/requests/yfinance/`seer_engine.bars`; the attributes `now`/`utcnow`/`today`/`fromtimestamp`/`random` (so `np.random` too); calls to `print`/`open`/`input`. Tests may use `np.random` and `time` | 1: invariants 2 and 5 |
| CAGR convention | Actual/365.25 from the first snapshot (`prev_session(start)`, starting cash) to the last: `(e1/e0) ** (365.25/days) − 1`; `None` when days ≤ 0 or e0 ≤ 0 or e1 < 0 | 6: surrounding convention (`months = days / 30.44` in `web/lib/metrics.ts` is the same 365.25-day year) |

## Open Questions

(none)

## Rollback

Every phase adds new files (plus one-line edits to `pyproject.toml`, `.gitignore`, `SOURCES.md`).
Per phase: `git revert` its commit. Whole set: `git revert` the merge commit on `main`, or delete the
branch before merging. No database state is created, so nothing else to undo. Delete
`engine/.cache/` locally if wanted.

## Next

Execute the phases one at a time, starting at phase 1:

    /implement -f STRATEGY_A_BACKTEST_PLAN.md --phase 1

Or run the whole set as a swarm — a session per phase, concurrent wherever `Depends on` allows,
resumable on any machine:

    /analyze-orchestrator -f STRATEGY_A_BACKTEST_PLAN.md

Or put them on the board first (GitHub repos only):

    /create-task --from-plan STRATEGY_A_BACKTEST_PLAN.md

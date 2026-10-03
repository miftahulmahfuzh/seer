# Plan: Strategy B, the ML cross-sectional ranker, under walk-forward (P6a): `strategies/b.py`, `b_model.py`, `backtest/labels.py`, `b_walkforward.py`, `b_report.py`, `backtest_b`

**Slug:** strategy-b-ranker
**Date:** 2026-10-03 18:08 WIB
**Analysis:** `20261003-180843-B6R1_code_analyzer.md`
**Worktree:** `/home/miftah/.worktrees/seer/strategy-b-ranker`
**Branch:** `feature/strategy-b-ranker` (base: `origin/main` @ `0e91d8a`)
**Phases:** 7
**Status:** landed on main @ 2086664 (7/7 phases)
**Coordinator:** orch-strategy-b-ranker

---

## Why

The specification is `docs/handover/2026-10-03-strategy-b-ranker.md` (committed at `0e91d8a`). Read
all of it:
- its §3 tables ("Law" and "Decided in this handover") are binding;
- §6 is the acceptance list;
- §7's open questions are settled under **Decisions** below.

Its core, verbatim:

> **This handover takes (a)** [Strategy B] … It is research-only and read-only, and it touches no
> trade rule.

> **B must be trained on a net-of-cost target and must be allowed to pass on a night.** Zero picks
> is valid (design §5).

> | One round only | B runs **once** on this data. If it fails, B is not reworked on this data either. The report and ROADMAP say so |

> These are recommendations, and each can be overturned with a one-line change before planning. They
> are fixed **now, before anyone sees a B result**, which is the point.

## Requirements

| ID | What the user asked for (handover §6) | Phases |
|---|---|---|
| R1 | Labels. Synthetic tests cover every label path. The vectorized labeler agrees with a one-order `sim` run on a seeded sample. Changing a bar after `tune_end(Y)` leaves fold Y's training set unchanged | 3, 4 |
| R2 | Features. Each is hand-computed. The rolling and single-window paths are bit-identical. Ranks use that date's candidates only, ties averaged. SPY features read SPY's bars through `data_date` only | 2 |
| R3 | P4 identity and no look-ahead, for B and B-linear, with a fixed model. SPY bars dated ≥ S are included | 2, 4 |
| R4 | Walk-forward. The folds are exactly P3b's. Training uses purged labels only. One chained portfolio, whose brackets survive the year boundary. `backtest_wf`'s A2 report stays byte-identical | 4, 7 |
| R5 | Determinism. `==` results and byte-identical files. The gated model is bit-identical across runs and thread counts, or the pre-registered switch to B-linear takes effect | 1, 4, 5, 6 |
| R6 | Purity. The new modules pass the globbing purity test | 1, 2, 3, 4, 5 |
| R7 | One real run on Neon, with the committed report holding every section §6.7 lists | 5, 6, 7 |
| R8 | Freeze or stop. **Pass:** artifact + constant + tie test. **Fail:** ROADMAP records the failure, P4 stays blocked, and the report lists the owner's options | 7 |
| R9 | The readme documents B. The suite is green with 0 skipped. CI is green with scikit-learn | 1, 7 |

## Scope

**In scope:**
- New:
  - `strategies/b_model.py`, `strategies/b.py`;
  - `backtest/labels.py`, `backtest/b_walkforward.py`, `backtest/b_report.py`;
  - `commands/backtest_b.py`;
  - their tests.
- Additive edits:
  - `engine/pyproject.toml` (scikit-learn);
  - `strategies/indicators.py` (`mean_window`, `stdev_return_window`);
  - `strategies/__init__.py` (exports from `b.py` only);
  - `backtest/io.py` (`write_b_report`, `write_model_artifact`).
- The committed report set `docs/backtests/<end>-strategy-b-walkforward{.md,-equity.csv,-equity.svg}`.
- On a pass only:
  - the artifact `engine/data/models/<end>-strategy-b.pkl`;
  - the `STRATEGY_B_FROZEN` constant.
- `tests/test_strategy_b_frozen.py`, which exists in both branches.
- `engine/package_readme.md` and `docs/ROADMAP.md`.

**Out of scope (handover §3 Law):**
- No edit to:
  - `seer_engine/sim/*`;
  - `strategies/a.py`, `strategies/a2.py`, `strategies/base.py`;
  - `backtest/runner.py`, `walkforward.py`, `wf_report.py`, `metrics.py`, `tuning.py`, `report.py`,
    `market.py`, `benchmark.py`;
  - `commands/backtest.py`, `commands/backtest_wf.py`;
  - any existing test file;
  - `docs/backtests/2026-10-02-*`.
- B reuses their public functions, plus the private report helpers they already share, imported
  read-only.
- No DB write and no migration.
- No change to `web/`, `.github/workflows/` or `cli.py`. CI picks scikit-learn up from
  `pyproject.toml`.
- No hyperparameter search, no new feature and no second model beyond the handover's.
- No P4 work, and no Strategy C.

## Invariants

1. **The suite stays green.** At the end of every phase,
   `PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q`
   passes with **0 skipped**. Run `docker start seer-pg` first. Baseline on `0e91d8a`: **761 passed**
   (measured 2026-10-03). Each phase states the tests it adds, and the reconciled count table is
   below. A different count is a finding, so name the missing or extra tests in the phase log.

   | Phase | Adds | Test files | Passed on its own (761 + adds) | Cumulative |
   |---|---|---|---|---|
   | 1 | +29 | `test_b_model.py` (25 functions, 4 parametrized over `KINDS`) | 790 | — |
   | 2 | +59 | `test_indicators_b.py` (11), `test_strategy_b.py` (48) | 820 | — |
   | 3 | +30 | `test_backtest_labels.py` | 791 | — |
   | 1 + 2 | | | | 849 |
   | 1 + 3 | | | | 820 |
   | 2 + 3 | | | | 850 |
   | 1 + 2 + 3 (all landed; phase 4's base) | | | | **879** |
   | 4 | +35 | `test_backtest_b_walkforward.py` | | **914** |
   | 5 | +27 | `test_backtest_b_report.py` | | **941** |
   | 6 | +23 | `test_backtest_b_command.py` | | **964** |
   | 7 | +6 | `test_strategy_b_frozen.py` (+ any Bug-protocol regression tests, each named) | | **970** |

   Phases 1, 2 and 3 run concurrently, so a session among them sees 761 plus whichever of the
   three have merged into the branch.
   - `engine/.venv` must be the **worktree's own** venv. The first phase session in the tree runs
     `python3 -m venv engine/.venv && engine/.venv/bin/pip install -e 'engine[dev]'` from the
     worktree root. After phase 1 adds scikit-learn, every session re-runs the `pip install -e`.
     It is idempotent.
   - Never use `/home/miftah/seer/engine/.venv`: it tests main's tree.
2. **Purity.**
   - Every module in `strategies/` and `backtest/` except `backtest/io.py` is pure.
     `tests/test_strategy_purity.py` globs both directories, so new modules are covered without
     editing it.
   - Pure means no `logging`, `time`, `random`, `.random`, `.now` or `open()` in the source.
   - scikit-learn and `threadpoolctl` may be imported, because they load none of psycopg,
     requests or yfinance (verified).
   - Seeds are passed as `random_state=0` ints, never via `np.random`.
3. **A2, v1 and the simulator are untouched.** Every file under "Out of scope" is byte-identical
   to `0e91d8a` at the end of every phase. Check with `git diff --stat 0e91d8a -- <paths>`.
4. **Read-only on Neon.** Nothing writes any table, `strategies.params` included.
5. **Determinism.**
   - The same inputs give `==` results and byte-identical files.
   - No unsorted set iteration in an output path.
   - No wall-clock value in a rendered file.
   - Every fit and run is sequential, in fold order.
6. **No look-ahead.**
   - Picks for session S read bars through `prev_session(S)` only, SPY's included.
   - Fold Y's model is fit only on rows whose label resolved on or before `tune_end(Y)`.
   - Nothing computed on a traded segment feeds any fit.
7. **Decimal at the sim boundary.** `Pick` prices are 4-dp `Decimal`s from `a._bracket`. Floats
   appear only in features, labels, model inputs and outputs, and metrics.
8. Every handover §3 rule holds, and so does every row under **Decisions**.

## Shared interface contract (all phases plan against this)

```python
# ---- engine/pyproject.toml  (phase 1) ---------------------------------------------------------
# dependencies += "scikit-learn>=1.9,<1.10"   (verified 1.9.1 with numpy 2.4.6, Python 3.11)

# ---- seer_engine/strategies/b_model.py  (phase 1; pure; imports sklearn, threadpoolctl, pickle, hashlib) ----
TREE = "tree"
RIDGE = "ridge"
KINDS: tuple[str, ...] = (TREE, RIDGE)
TREE_PARAMS: dict[str, object] = dict(loss="squared_error", learning_rate=0.05, max_iter=300, max_leaf_nodes=15,
                                      min_samples_leaf=200, l2_regularization=1.0, early_stopping=False, random_state=0)
RIDGE_ALPHA = 1.0
BLOCK_ROWS = 65_536            # ridge accumulation block; results depend on the data only, never on threads

@dataclass(frozen=True, slots=True, eq=False)
class RidgeFit:
    coef: np.ndarray            # float64 (n_features,), read-only
    intercept: float

@dataclass(frozen=True, eq=False)
class BModel:
    kind: str                   # TREE | RIDGE
    n_features: int
    digest: str                 # sha256 hex of the functional content (below); identity of the model
    estimator: Any              # fitted HistGradientBoostingRegressor (TREE) | RidgeFit (RIDGE)
    def __eq__(self, other) -> bool   # isinstance BModel and (kind, n_features, digest) equal
    def __hash__(self) -> int         # hash((kind, n_features, digest))
    def predict(self, X: np.ndarray) -> np.ndarray
        # float64 (rows,). X: 2-D float64, n_features columns (ValueError otherwise; 0 rows -> empty).
        # PER-ROW BIT-IDENTITY: row i's value does not depend on the other rows or on the batch size.
        #   TREE: estimator.predict(X) (verified batch-independent);
        #   RIDGE: acc = full(rows, intercept); for j in range(n): acc = acc + X[:, j] * coef[j]   (explicit loop)
    def as_dict(self) -> dict[str, str]   # {"kind": kind, "digest": digest}

def check_xy(X, y) -> None      # X 2-D float64 finite, >= 1 row; y 1-D float64 finite, same rows; else ValueError/TypeError
def fit_tree(X, y, *, threads: int | None = None) -> BModel
    # HistGradientBoostingRegressor(**TREE_PARAMS).fit(X, y); threads not None -> inside
    # threadpoolctl.threadpool_limits(limits=threads). digest = sha256(baseline bytes + every predictor's
    # nodes.tobytes(), in predictor order)   (sklearn private `_baseline_prediction`, `_predictors`; version pinned)
def fit_ridge(X, y, alpha: float = RIDGE_ALPHA) -> BModel
    # closed form with an UNPENALIZED intercept: column means, centred Xc / yc, XtX and Xty accumulated per
    # BLOCK_ROWS block with np.einsum(..., optimize=False), blocks summed in order; coef = np.linalg.solve(XtX + alpha*I, Xty);
    # intercept = ybar - Σ_j xbar_j*coef_j (explicit loop). digest = sha256(coef.tobytes() + float64(intercept).tobytes())
def fit(kind: str, X, y) -> BModel         # dispatch; ValueError on an unknown kind
def importance(model: BModel, X: np.ndarray) -> tuple[float, ...]
    # one share per feature, summing to 1.0 (all 0.0 when the total is 0). TREE: Σ node["gain"] over non-leaf
    # nodes, by node["feature_idx"], over every predictor. RIDGE: |coef_j| x population std of X[:, j]
    # (std by the indicators' column-free rule: mean via a block loop, then mean of squared deviations).
def r2(y: np.ndarray, pred: np.ndarray) -> float | None   # 1 - SS_res/SS_tot; None when SS_tot == 0
def dumps(model: BModel) -> bytes          # pickle.dumps((model.kind, model.n_features, model.estimator), protocol=5)
def loads(data: bytes) -> BModel           # inverse; recomputes the digest from the estimator (so a tampered payload changes it)
def sha256(data: bytes) -> str             # hex
# ARTIFACT IDENTITY (D25): a fresh fit's dumps() is byte-identical across runs, but dumps(loads(b)) != b is
# possible for a TREE (pickle re-frames an unpickled estimator). Identity is sha256(file bytes) and
# loads(b).digest / loads(b) == model, never re-pickled bytes.

# ---- seer_engine/strategies/indicators.py  (phase 2; additive; same bit-identity rule) -----------
def mean_window(x: np.ndarray, n: int) -> np.ndarray          # mean of the last n columns, summed left to right (== _column_mean)
def stdev_return_window(close: np.ndarray, n: int) -> np.ndarray
    # population (ddof 0) stdev of the last n one-bar returns r = c_i / c_{i-1} - 1; NaN rows when W < n + 1.
    # mean by a column loop, then Σ (r - mean)^2 by a column loop, / n, np.sqrt.

# ---- seer_engine/strategies/b.py  (phase 2; pure; does NOT import b_model) -----------------------
LOOKBACK = 200                               # == a.LOOKBACK
# (+ public helper constants, phase 2) N_SYMBOL = 15, N_FEATURES = 18, CLOSE_COL = 15, ATR_COL = 16, DV_COL = 17,
#   SMA_FAST_N = 50, SMA_SLOW_N = 200, RSI_FAST_N = 2, RSI_SLOW_N = 14, ATR_N = 14, STDEV_N = 20, DV_N = 20,
#   VOLUME_FAST_N = 5, VOLUME_SLOW_N = 20, SPY_RETURN_HORIZONS = (5, 20)
SPY_SYMBOL = "SPY"                           # == a2.REGIME_SYMBOL == universe.BENCHMARK (tested; no universe import)
MIN_DOLLAR_VOLUME = 20_000_000.0             # == a.DESIGN_PARAMS.min_dollar_volume (strict >)
RETURN_HORIZONS = (1, 5, 20, 60, 120)
SYMBOL_FEATURES: tuple[str, ...] = ("ret_1", "ret_5", "ret_20", "ret_60", "ret_120", "close_sma50", "close_sma200",
    "rsi_2", "rsi_14", "atr_pct", "stdev_20", "dollar_volume_20", "volume_5_20", "gap", "range_pos")   # 15, ranked
SPY_FEATURES: tuple[str, ...] = ("spy_ret_5", "spy_ret_20", "spy_close_sma200")                          # 3, raw
FEATURE_NAMES = SYMBOL_FEATURES + SPY_FEATURES                                                           # 18 model columns, this order
# Per-symbol raw values on the last LOOKBACK bars ending at data_date (o,h,l,c,v windows, oldest first):
#   ret_k = c[-1]/c[-1-k] - 1 ; close_sma50 = c[-1]/sma_window(c,50) - 1 ; close_sma200 = c[-1]/sma_window(c,200) - 1
#   rsi_2 / rsi_14 = wilder_rsi_window(c, 2 / 14) ; atr_pct = wilder_atr_window(h,l,c,14) / c[-1]
#   stdev_20 = stdev_return_window(c, 20) ; dollar_volume_20 = mean_dollar_volume_window(c, v, 20)   (Decision D6: rank of log == rank)
#   volume_5_20 = mean_window(v,5) / mean_window(v,20) ; gap = o[-1]/c[-2] - 1
#   range_pos = (c[-1]-l[-1])/(h[-1]-l[-1]) when h[-1] > l[-1], else 0.5
# SPY raw values on SPY's last LOOKBACK bars ending at data_date: spy_ret_5, spy_ret_20 (as ret_k), spy_close_sma200.
# Undefined (-> no candidates that date) when SPY has no bar dated data_date or < LOOKBACK bars through it.

def window_features(o, h, l, c, v) -> np.ndarray
    # (rows, 18) float64 for (rows, LOOKBACK) windows: the 15 SYMBOL_FEATURES raw values, then close, atr, dollar_volume
    # (columns RAW_COLUMNS = SYMBOL_FEATURES + ("close", "atr", "dollar_volume")). Used by BOTH paths.
def spy_window_features(c) -> np.ndarray     # (rows, 3) for SPY close windows (rows, LOOKBACK)
def rank01(x: np.ndarray) -> np.ndarray
    # average ranks among x's entries (ties averaged), scaled (rank-1)/(n-1); n == 1 -> 0.5; n == 0 -> empty.
    # Stable: argsort(kind="stable"), then equal runs share the mean rank. ValueError unless 1-D float64 and
    # finite; -0.0 and 0.0 tie.

@dataclass(frozen=True, slots=True, eq=False)
class Design:
    """The candidates of one data_date: what the model sees and what a pick needs."""
    data_date: date
    symbols: tuple[str, ...]      # sorted ascending
    X: np.ndarray                 # (m, 18) float64: rank01 of each SYMBOL_FEATURES column among these m rows, then SPY's 3 raw values
    close: np.ndarray             # (m,) float64 last close
    atr: np.ndarray               # (m,) float64 ATR(14)
    # (+) arrays read-only; __post_init__ checks the date type and shapes (TypeError/ValueError); __len__ = m
# Candidates on d: symbol in members, != SPY_SYMBOL, a bar dated d, >= LOOKBACK bars through d,
# dollar_volume_20 > MIN_DOLLAR_VOLUME, all 15 raw SYMBOL_FEATURES finite, AND SPY's features defined on d.
# (Bracket validity is NOT a candidate rule: it is applied to picks, and to training rows. Decision D5.)

@dataclass(frozen=True, slots=True, eq=False)
class BPrepared:
    symbols: tuple[str, ...]      # sorted, EXCLUDING SPY_SYMBOL (SPY never has a row); sym indexes into it
    dates: np.ndarray             # datetime64[D] ascending, one per eligible (symbol, date) row with >= LOOKBACK bars
    sym: np.ndarray               # int64
    raw: np.ndarray               # (rows, 18) float64 window_features output, read-only, ordered by (date, symbol)
    spy_dates: np.ndarray         # datetime64[D] ascending: SPY dates with >= LOOKBACK bars
    spy: np.ndarray               # (k, 3) float64
    def design_on(self, members: AbstractSet[str], data_date: date) -> Design   # empty Design (0 rows) when none
def prepare_b(history: Mapping[str, History]) -> BPrepared     # sliding_window_view of each symbol's 5 series -> window_features
def design_at(history: Mapping[str, History], members, data_date: date) -> Design
    # single-window path: == prepare_b({s: h.upto(d)}).design_on(members, d), bit for bit (P4 identity)

@runtime_checkable
class Predictor(Protocol):
    def predict(self, X: np.ndarray) -> np.ndarray: ...      # b_model.BModel satisfies it; tests use a fake
    # predict MUST return a float64 ndarray of shape (rows,), else picks_from_design raises ValueError

@dataclass(frozen=True, slots=True)
class BParams:
    model: Predictor              # equality and hash come from the model (BModel: kind+n_features+digest)
    # (+) __post_init__: TypeError when the model has no predict (isinstance(model, Predictor))

def bracket(symbol: str, close: float, atr: float) -> Pick | None
    # a._bracket(a.Features(symbol, <any date>, close, nan, nan, atr, nan), a.DESIGN_PARAMS): limit 0.5 ATR,
    # TP +1.0 ATR, SL -1.5 ATR, Decimal 4 dp, None when invalid or when close/atr is not finite
def picks_from_design(design: Design, params: BParams) -> list[Pick]
    # pred = params.model.predict(design.X); keep pred > 0.0 (strict); order by (-pred, symbol); bracket each;
    # drop None. Empty design -> [] without calling predict. TypeError on a non-Design/non-BParams argument.

@dataclass(frozen=True, slots=True)
class FrozenModel:                # set ONLY by phase 7 on a pass
    report: str                   # "docs/backtests/<end>-strategy-b-walkforward.md"
    artifact: str                 # "engine/data/models/<end>-strategy-b.pkl"
    train_end: date               # the last fold's tune_end
    sha256: str                   # of the artifact bytes
STRATEGY_B_FROZEN: FrozenModel | None = None   # placeholder comment above it, two lines, replaced by phase 7 on a pass
# NOT re-exported from strategies/__init__.py (D24). Every reader (phase 6 command, phase 7 test) reads
# seer_engine.strategies.b.STRATEGY_B_FROZEN at call time. strategies/__init__.py re-exports FEATURE_NAMES,
# STRATEGY_B, BParams, BPrepared, Design, FrozenModel, Predictor, StrategyB, design_at, picks_from_design,
# prepare_b, and never imports b_model (import seer_engine.strategies loads no sklearn).

class StrategyB:                  # implements strategies.base.Strategy
    id = "B"
    lookback = LOOKBACK
    def picks(self, history, members, data_date, params): ...   # BParams else TypeError; picks_from_design(design_at(...), params)
    def prepare(self, history) -> BPrepared: ...
    def picks_prepared(self, prepared, members, data_date, params): ...   # picks_from_design(prepared.design_on(...), params)
STRATEGY_B = StrategyB()
# CONTRACT: picks_prepared(prepare(H), M, d, p) == picks({s: h.upto(d)}, M, d, p), for every p.

# ---- seer_engine/backtest/labels.py  (phase 3; pure) ------------------------------------------
REASONS: tuple[str, ...] = ("expire", "tp", "sl", "gap", "time", "forced")   # code = index; -1 = unresolved
COST = 0.001                         # == float(sim.COST_RATE) (tested)

@dataclass(frozen=True, eq=False)
class Labels:
    label: np.ndarray                # float64 (n,): exit*(1-COST)/(fill*(1+COST)) - 1; 0.0 for "expire"; NaN unresolved
    resolved: np.ndarray             # datetime64[D] (n,): exit session ("expire": the order session); NaT unresolved
    reason: np.ndarray               # int8 (n,) index into REASONS, -1 unresolved
    fill: np.ndarray                 # float64 (n,), NaN when not filled
    exit: np.ndarray                 # float64 (n,), NaN when not filled or unresolved
    # no __post_init__: keyword construction works (phase 4 scatters into full-table arrays); arrays returned read-only

def label_orders(history: Mapping[str, History], symbols: Sequence[str], data_dates: np.ndarray,
                 limit: np.ndarray, tp: np.ndarray, sl: np.ndarray, end: date) -> Labels
    # One bracket order per row, alone, under design §5 exactly as sim.step + the runner apply it, on NYSE
    # sessions (dates.sessions), reading bars dated <= end only:
    #  - order session S1 = next_session(data_date). S1 > end -> unresolved.
    #  - S1 has no bar, or low >= limit -> "expire", label 0.0, resolved S1.
    #  - else fill = min(open, limit) on S1, days_held = 1, no exit check on S1.
    #  - each later session S: no bar -> days_held += 1; else in order: days_held >= 5 -> open ("time");
    #    open <= sl -> open ("gap"); open >= tp -> open ("tp"); low <= sl -> sl ("sl"); high > tp -> tp ("tp");
    #    else days_held += 1.
    #  - after S's checks, still open and the symbol's last bar (<= end) is before S -> exit at that last
    #    close ("forced"; sim reason "time" with forced=True), resolved S.
    #  - not resolved by end -> unresolved.
    # Vectorized: session-aligned dense float matrices for the symbols present, one numpy pass per session offset
    # over the still-open rows only. limit/tp/sl are float(Decimal) of a._bracket's 4-dp prices.
    # PRECONDITIONS (ValueError otherwise): data_dates datetime64[D] without NaT; limit/tp/sl float64, finite and
    # 0 < sl < limit < tp on EVERY row (so phase 4 passes only valid-bracket rows); end a date, not a datetime.

# ---- seer_engine/backtest/b_walkforward.py  (phase 4; pure) -------------------------------------
B = "B"                    # curve name of the tree model
B_LINEAR = "B-linear"      # curve name of the ridge model
DECILES = 10
TOP_FEATURES = 5

@dataclass(frozen=True, eq=False)
class CandidateTable:
    """Every candidate row from data_date prev_session(is_start) through prev_session(end): rows ordered by (data_date, symbol)."""
    data_dates: np.ndarray        # datetime64[D] (n,)
    symbols: tuple[str, ...]      # (n,) per row
    X: np.ndarray                 # (n, 18) == the Design rows of that date, bit for bit
    limit: np.ndarray             # float64 (n,) float(Decimal) of b.bracket; NaN when the bracket is invalid
    tp: np.ndarray
    sl: np.ndarray
    labels: Labels                # label_orders(..., end=end) over the rows with a valid bracket (NaN/NaT/-1 elsewhere)
def candidate_table(market: Market, prepared: BPrepared, is_start: date, end: date) -> CandidateTable
def training_mask(table: CandidateTable, fold: Fold) -> np.ndarray
    # valid bracket & resolved not NaT & resolved <= fold.tune_end & data_date >= prev_session(fold.tune_start)

@dataclass(frozen=True)          # VALUE equality (D20): train_folds(...) == train_folds(...), BWalkForward ==, BReport ==
class FoldModel:
    fold: Fold
    model: BModel
    rows: int
    label_mean: float
    label_sum: float
    pred_mean: float              # in-fold, information
    r2: float | None              # in-fold, information
    positive_share: float         # in-fold share of predictions > 0
    importance: tuple[float, ...] # b_model.importance, FEATURE_NAMES order
def train_folds(table, folds, kind: str) -> tuple[FoldModel, ...]   # sequential, folds order; ValueError on a fold without rows
def probe_determinism(table, fold: Fold) -> bool
    # fit_tree(rows of fold, threads=1).digest == fit_tree(same rows, threads=None).digest; ValueError on no rows

@dataclass(frozen=True)
class BWalkForward:
    name: str                       # B | B_LINEAR
    folds: tuple[Fold, ...]
    fold_models: tuple[FoldModel, ...]
    run: RunResult                  # run_backtest(market, STRATEGY_B, model_schedule(...), folds[0].trade_start, folds[-1].trade_end, prepared=)
def model_schedule(folds, fold_models) -> ParamsSchedule          # ((f.trade_start, BParams(fm.model)) ...)
def walk_forward_b(market, prepared, folds, fold_models, name) -> BWalkForward
    # ValueError unless name B has TREE fold models and B_LINEAR has RIDGE fold models

@dataclass(frozen=True)
class CalibrationRow:
    decile: int                     # 1..DECILES, ascending prediction
    rows: int
    pred_min: float
    pred_max: float
    pred_mean: float
    label_mean: float
def oos_predictions(table, folds, fold_models) -> tuple[np.ndarray, np.ndarray]
    # (row indices int64, predictions float64) for every table row with a valid bracket whose session
    # next_session(data_date) lies in a fold's [trade_start, trade_end], predicted by THAT fold's model; rows ascend
def calibration(pred: np.ndarray, label: np.ndarray) -> tuple[CalibrationRow, ...]
    # pred, label: 1-D float64, same shape. Drops NaN (unresolved) labels ITSELF (callers pass table.labels.label[idx]
    # unfiltered); ValueError when fewer than DECILES labels are resolved; order = lexsort((position, pred));
    # np.array_split into DECILES groups. So a returning call gives exactly DECILES non-empty rows, deciles 1..10 (D21).
def passed_nights(table, folds, fold_models) -> tuple[int, int]
    # (sessions with zero picks, traded sessions): a session passes when no candidate of its data_date has
    # a valid bracket and pred > 0.0 (exactly picks_from_design's emptiness).
    # traded = len(dates.sessions(folds[0].trade_start, folds[-1].trade_end)) == len(run.snapshots) - 1
def gate_p6a(wf: Metrics, spy_tr: Metrics, start: date, end: date, gated: str) -> Verdict
    # metrics.checklist(wf, spy_tr.total_return)[2:5]; gated = B or B_LINEAR (B_LINEAR only via the switch, D13)
    # pass: "Strategy B passes the P6a gate: walk-forward from {s} to {e} it returned {wf} against {spy} for
    #        total-return SPY, with profit factor {pf} and max drawdown {dd}."
    # fail: "Strategy B fails the P6a gate: ..., so it fails on {failed}; Strategy B's one round has failed on
    #        this data, and P4 stays blocked."
    # gated == B_LINEAR: ONLY the subject (the sentence's first "Strategy B") becomes
    #   "Strategy B (as B-linear, by the pre-registered determinism switch)"; the fail tail "Strategy B's one round
    #   has failed on this data, and P4 stays blocked." is unchanged (D22).
# Imports read-only from walkforward.py (frozen by law): _check_folds, _day, _session, _join, _GATE_NAMES (D26).

# ---- seer_engine/backtest/b_report.py  (phase 5; pure) ------------------------------------------
@dataclass(frozen=True)
class BReport:
    data_end: date
    bars_rows: int
    symbols_with_bars: int
    never_fetched_members: int
    survivorship: tuple[YearGap, ...]
    is_start: date
    folds: tuple[Fold, ...]
    candidate_rows: int
    labelled_rows: int                         # rows with a valid bracket and a resolved label
    determinism_ok: bool                       # probe_determinism on the last fold
    gated: str                                 # B if determinism_ok else B_LINEAR
    b: BWalkForward
    b_linear: BWalkForward
    a2: WalkForward                            # A2's combined walk-forward, recomputed (information)
    passed: tuple[tuple[str, int, int], ...]   # (curve name, passed sessions, traded sessions) for B, B-linear
    calibration: tuple[tuple[str, tuple[CalibrationRow, ...]], ...]   # (B, rows), (B-linear, rows)
    spy_price: BenchmarkCurve
    spy_tr: BenchmarkCurve
    verdict: Verdict                           # gate_p6a on the gated curve
    frozen: FrozenModel | None                 # STRATEGY_B_FROZEN at run time
    def curves(self) -> tuple[BWalkForward, BWalkForward]   # (b, b_linear)
    def gated_curve(self) -> BWalkForward                   # b if gated == B else b_linear
def report_stem(data_end) -> str               # f"{data_end.isoformat()}-strategy-b-walkforward"
def top_features(importance: Sequence[float]) -> tuple[tuple[str, float], ...]
    # up to TOP_FEATURES (FEATURE_NAMES[j], share) pairs by (-share, j), shares <= 0 left out; ValueError unless 18 shares
GATE_KEY = "p6a-gate"; GATED_KEY = "gated-model"; LAST_FOLD_KEY = "last-fold-model"; FROZEN_KEY = "frozen-model"
def machine_lines(r) -> list[str]
    # "p6a-gate: passed|failed"; "gated-model: B|B-linear";
    # "last-fold-model: " + json.dumps({"kind","digest","train_end": ISO str,"rows": int,"label_sum": STRING repr(float)})
    #   (gated curve, last fold; keys in this order; label_sum read back with float(...)) (D23)
    # "frozen-model: null" | json.dumps({"report","artifact","train_end","sha256"})
def parse_machine_line(markdown: str, key: str) -> str      # delegates to wf_report.parse_machine_line
# render_markdown / equity_csv / equity_svg call _validate first: verdict == gate_p6a(run_metrics(gated.run),
#   curve_metrics(spy_tr), gated.run.start, gated.run.end, gated); passed[i][2] == len(run.snapshots) - 1;
#   calibration deciles 1..DECILES; gated == (B if determinism_ok else B_LINEAR); runs' params == model_schedule.
# b_report never imports backtest.io (io imports b_report).
EQUITY_CSV_HEADER = "date,b,b_linear,a2,spy_price,spy_tr"
def render_markdown(r) -> str; def equity_csv(r) -> str; def equity_svg(r) -> str   # svg: B, B-linear, A2, SPY price, SPY TR via wf_report._chart

# ---- seer_engine/backtest/io.py  (phase 6; additive) ------------------------------------------
MODELS_DIR = config.REPO_ROOT / "engine" / "data" / "models"
def write_b_report(out_dir: Path, report: BReport) -> list[Path]     # <stem>.md, -equity.csv, -equity.svg; all rendered first
def write_model_artifact(model_dir: Path, data_end: date, model: BModel) -> tuple[Path, str]
    # writes b_model.dumps(model) to <model_dir>/<data_end>-strategy-b.pkl (tmp file + os.replace);
    # returns (path, sha256 of the written bytes). ONLY phase 6 edits io.py.

# ---- seer_engine/commands/backtest_b.py  (phase 6) --------------------------------------------
# python -m seer_engine backtest_b [--out DIR] [--cache-dir DIR] [--refresh-cache] [--is-start D]
#                                  [--first-year YYYY] [--end D] [--dividends PATH] [--model-dir DIR]
# def resolve(...) -> reuse backtest_wf.resolve (BacktestWfError -> exit 2)
# def execute(market, bars_rows, dividends, is_start, first_year, end) -> BReport
# def recompute_a2(market, folds) -> walkforward.WalkForward   # (+ phase 6) the A2 step as one named, timed unit
#   folds; prepare_b; candidate_table; train_folds(TREE) and (RIDGE); probe_determinism(last fold);
#   walk_forward_b x2; A2: STRATEGY_A2.prepare + backtest_wf.tune_all(walkforward.combinations()) +
#   backtest_wf.run_walk_forward(..., None); spy_curves; survivorship; passed_nights; calibration;
#   gate_p6a on the gated curve; frozen = strategies.b.STRATEGY_B_FROZEN read at call time. Every step timed + logged.
# run(): writes the report; when the gate passed, also write_model_artifact(gated curve's last fold model) and log
#   the sha256 + the instruction to freeze it (phase 7), as the literal
#   FrozenModel(report='docs/backtests/<stem>.md', artifact='engine/data/models/<end>-strategy-b.pkl',
#               train_end=date(Y, M, D), sha256='<hex of the file bytes>')   (repo-relative POSIX paths)
# Every CLI command imports scikit-learn through cli.discover -> backtest_b (eager imports, D19).
```

## Phases

| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID | Card |
|---|-------|-----------|---------|-------|-----------|------------|------|--------|------|
| 1 | B model interface + scikit-learn dependency | R5, R6, R9 | `strategies` | 3 | — | NORMAL | `.workflows/plan/strategy-b-ranker/phase-1.md` | P1-ENG-CW71 | — |
| 2 | B features, ranks, candidates, `StrategyB` | R2, R3, R6 | `strategies` | 5 | — | HARD | `.workflows/plan/strategy-b-ranker/phase-2.md` | P1-ENG-1OMN | — |
| 3 | Vectorized bracket labeler | R1, R6 | `backtest` | 2 | — | HARD | `.workflows/plan/strategy-b-ranker/phase-3.md` | P1-ENG-DKWU | — |
| 4 | B walk-forward: candidate table, purge, per-fold fits, runs, diagnostics, gate | R1, R3, R4, R5, R6 | `backtest` | 2 | 1, 2, 3 | HARD | `.workflows/plan/strategy-b-ranker/phase-4.md` | P1-ENG-U5JJ | — |
| 5 | B report rendering | R5, R6, R7 | `backtest` | 2 | 4 | HARD | `.workflows/plan/strategy-b-ranker/phase-5.md` | P1-ENG-VK5P | — |
| 6 | `backtest_b` command + io writers | R5, R7 | `commands`, `backtest` | 3 | 5 | NORMAL | `.workflows/plan/strategy-b-ranker/phase-6.md` | P1-ENG-UREW | — |
| 7 | Real run on Neon, A2 byte-identity check, freeze or stop, docs | R4, R7, R8, R9 | `docs`, `strategies`, `tests` | 6–8 | 6 | NORMAL | `.workflows/plan/strategy-b-ranker/phase-7.md` | P1-ENG-M99E | — |

### Phase 1: B model interface + scikit-learn dependency
**Satisfies:** R5 (model determinism), R6, R9 (the dependency reaches CI).
**Owns:**
- `engine/pyproject.toml`: the scikit-learn pin.
- `strategies/b_model.py` (new), exactly as the contract above.
- `tests/test_b_model.py` (new):
  - fit and predict on synthetic data;
  - ridge against a hand-solved small case;
  - per-row batch independence for both kinds;
  - two fits give `==` models with equal digests;
  - **thread-count determinism**: a subprocess fits the tree with `OMP_NUM_THREADS=1` and another
    with 4, about 50k × 18 rows, and the digests and predictions must match;
  - the `dumps`/`loads` round trip gives identical predictions and digest;
  - importance shares sum to 1;
  - `r2`;
  - input validation;
  - the purity glob covers the module.

**Does not touch:** `b.py`, `strategies/__init__.py`, anything in `backtest/`.
**Exit criteria:** the suite is green with 0 skipped (790 alone; see the count table).
`pip install -e 'engine[dev]'` pulls scikit-learn 1.9.x. Artifact identity is sha256 of the file
bytes and `loads(b).digest`, never re-pickled bytes (D25).

### Phase 2: B features, ranks, candidates, `StrategyB`
**Satisfies:** R2, R3 (with a fake `Predictor`), R6.
**Owns:**
- `strategies/indicators.py`: additive `mean_window` and `stdev_return_window`, plus tests in a new
  `tests/test_indicators_b.py` (the existing `test_indicators.py` stays unedited).
- `strategies/b.py` (new), exactly as the contract above.
- `strategies/__init__.py`: exports from `b.py`. It never imports `b_model`, so `import
  seer_engine.strategies` does not load scikit-learn.
- `tests/test_strategy_b.py` (new):
  - every feature hand-computed on synthetic series;
  - bit-identity between `prepare_b` and `design_at`;
  - `rank01` with ties and the n = 0 and n = 1 cases;
  - ranks use members on d only;
  - SPY features from SPY's bars through d, with no candidates when SPY is missing or short;
  - `picks_from_design` covers the positive-only rule, the order with symbol tie-breaks, and the
    invalid-bracket drop;
  - P4 identity over several dates and several fake models;
  - no look-ahead: mutating or truncating any symbol's bars, SPY's included, from S on leaves S's
    picks unchanged;
  - SPY is never picked;
  - `SPY_SYMBOL == universe.BENCHMARK`;
  - `MIN_DOLLAR_VOLUME == a.DESIGN_PARAMS.min_dollar_volume`.

**Does not touch:** `a.py`, `a2.py`, `base.py`, the existing indicator functions, `b_model.py`,
`backtest/`.
**Exit criteria:** the suite is green with 0 skipped (+59: 11 in `test_indicators_b.py`, 48 in
`test_strategy_b.py`), the purity glob covers `b.py`, and `import seer_engine.strategies` loads
no `sklearn`. `STRATEGY_B_FROZEN` is not re-exported from the package (D24).

### Phase 3: Vectorized bracket labeler
**Satisfies:** R1 (label paths and sim parity), R6.
**Owns:**
- `backtest/labels.py` (new), exactly as the contract above.
- `tests/test_backtest_labels.py` (new):
  - synthetic bars for every path: no fill (no bar, and low ≥ limit), fill at the limit, fill at
    the open when open < limit, TP intraday, SL intraday, both in range (SL first), gap through SL
    at the open, gap through TP at the open, the day-5 time stop, the time stop delayed by a
    missing bar, the forced close after the last bar, and unresolved at the end;
  - every label net of 0.1% per side;
  - **sim parity**: on a seeded synthetic market (a fixed `np.random.default_rng` is NOT
    allowed in the module, but a test may use it), for a few thousand rows, `run_backtest` with a
    one-pick fake strategy must give the same exit reason (`forced` matches sim `time` with
    `forced=True`), the same exit date or expiry, and a return within 1e-6;
  - mutating bars after a row's resolved date leaves its label unchanged.

**Does not touch:** `sim/`, `runner.py`, `strategies/`.
**Exit criteria:** the suite is green with 0 skipped (+30), and the purity glob covers the module.

### Phase 4: B walk-forward
**Satisfies:** R1 (purge), R3 (with real tree and ridge models), R4, R5, R6.
**Owns:**
- `backtest/b_walkforward.py` (new), exactly as the contract above: `FoldModel` with value
  equality (D20), `calibration` dropping NaN labels itself (D21), `gate_p6a` changing only the
  subject for B-linear (D22), `passed_nights`' traded == `len(run.snapshots) - 1`, and five
  private `walkforward.py` helpers imported read-only (D26).
- `tests/test_backtest_b_walkforward.py` (new, 35 tests), on synthetic markets:
  - the `CandidateTable` rows equal each date's `design_on`;
  - **the purge**: mutating any bar after `tune_end(Y)` leaves fold Y's training mask, X and
    labels unchanged, and so its model digest;
  - the folds equal `walkforward.folds`;
  - `train_folds` works for both kinds;
  - the schedule switches at year starts, and an order open across 31 Dec keeps its bracket;
  - P4 identity of `STRATEGY_B` with real fitted tree and ridge `BParams`;
  - `oos_predictions` uses the right fold's model;
  - calibration deciles are hand-checked;
  - passed nights equal the count of empty-pick sessions in the run;
  - `gate_p6a` sentences, in both kinds and both outcomes;
  - two identical calls give `==` results;
  - `probe_determinism` is True on synthetic data.

**Does not touch:** `walkforward.py` and every other out-of-scope file.
**Exit criteria:** the suite is green with 0 skipped (914), and the purity glob covers the module.

### Phase 5: B report rendering
**Satisfies:** R5 (byte-stable rendering), R6, R7 (content).
**Owns:**
- `backtest/b_report.py` (new): `BReport` (with `curves()` and `gated_curve()`), `_validate`,
  `top_features`, machine lines (`label_sum` as a JSON string of `repr(float)`, D23),
  `render_markdown`, `equity_csv`, `equity_svg`.
- `tests/test_backtest_b_report.py` (new, 27 tests), built from a small synthetic run via phase 4's API.

Markdown sections, in order:
1. title;
2. data (rows, symbols, data end, candidate and labelled rows);
3. method (folds, candidates, features, label, purge, model and hyperparameters, B-linear, picks,
   gate, determinism probe result, "one round only");
4. per-fold training summary for B and B-linear (rows, label mean, in-fold R², pred mean, positive
   share, top 5 features);
5. results: B, B-linear and A2 vs both SPY curves (return, CAGR, PF, max DD, trades, win rate);
6. year by year;
7. diagnostics for B and B-linear (P/L by exit reason and by year, < 3 shares, cost drag, passed
   nights, calibration table);
8. seen before (2022-01-03 →);
9. go-live checklist;
10. survivorship, with the learned-model caveat;
11. open positions at the end;
12. curves (the SVG link);
13. verdict sentence;
14. on a fail, the owner's options (b), (c) and (d) as handover §8 names them;
15. the machine fence.

**Does not touch:** `wf_report.py` and `report.py`. Their helpers are imported, never edited.
**Exit criteria:** the suite is green with 0 skipped (941). Rendering twice is byte-identical.
`_validate` rejects a mismatched verdict, a misaligned curve, and a schedule that does not match
`fold_models`.

### Phase 6: `backtest_b` command + io writers
**Satisfies:** R5, R7.
**Owns:**
- `backtest/io.py` (additive): `MODELS_DIR`, `write_b_report` and `write_model_artifact`. This is
  the only phase that edits `io.py`.
- `commands/backtest_b.py` (new), including the public `recompute_a2(market, folds)`. It imports
  eagerly, so every CLI command now loads scikit-learn through `cli.discover` (D19).
- `tests/test_backtest_b_command.py` (new, 23 tests):
  - `execute` on a synthetic market, run twice, gives `==` reports and byte-identical files;
  - a gate pass writes the artifact, and a fail does not;
  - exit 2 on a precondition;
  - the A2 curve equals `backtest_wf`'s combined curve on the same market;
  - wall times appear in logs only.
- Test helpers for a synthetic market go in the new test file.

**Does not touch:** `backtest_wf.py` (imported only), `cli.py` (it discovers commands
automatically).
**Exit criteria:** the suite is green with 0 skipped (964), and `python -m seer_engine backtest_b --help`
works.

### Phase 7: Real run on Neon, A2 byte-identity, freeze or stop, docs
**Satisfies:** R4 (the A2 byte-identity check), R7, R8, R9.
**Owns:**
1. Run `backtest_b` against Neon from the worktree (with `SEER_ENV_FILE`), and record the data
   end, wall time and peak RSS.
2. Re-run `backtest_wf --end 2026-10-02 --out <scratch>`, then `cmp` all 5 files against the
   committed `docs/backtests/2026-10-02-strategy-a2-walkforward*`. A difference is a finding, and
   it stops the phase.
3. Commit the B report set.
4. **On a pass:**
   - set `STRATEGY_B_FROZEN` in `b.py` (report, artifact, `train_end`, sha256) and commit the
     artifact;
   - re-run, so the report records `frozen-model` (the artifact is rewritten byte-identically);
   - `tests/test_strategy_b_frozen.py` (6 tests) asserts the pass branch: constant == machine
     line, `sha256(artifact file bytes)` matches, and `b_model.loads(artifact).digest` is the
     report's last-fold digest (never re-pickled bytes, D25). It reads
     `strategies.b.STRATEGY_B_FROZEN` at call time (D24) and `label_sum` as a repr string (D23).

   **On a fail:**
   - the constant stays None;
   - the test asserts the fail branch: the report says `failed` and `frozen-model: null`, and no
     artifact exists under `engine/data/models/`.
5. Docs:
   - `engine/package_readme.md`: B, the labeler, the features, the model, `backtest_b`, its
     performance, and the module graph;
   - `docs/ROADMAP.md`: P6a and its verdict. On a fail: "B's one round failed on this data; P4
     stays blocked", with the owner's remaining options.

**Edits in `b.py`:** only the `STRATEGY_B_FROZEN` line and the two comment lines above it, and
only on a pass. No other source edit, except a Bug-protocol fix in the owning phase's module.
**Exit criteria:** the suite is green with 0 skipped (970, plus any named Bug-protocol regression
tests), CI is green, and the report is committed.

## Reconciliation Log

Round 1, 2026-10-03. Ledger built over all 7 plans; every analysis Impact Point (1–11) has exactly
one owning phase; every R1–R9 is served by the phases in the Requirements table; dependencies point
backward only; no symbol is deleted or renamed anywhere, so there is no deleted-then-used case.

| # | Conflict | Class | Phases | Resolution |
|---|---|---|---|---|
| 1 | Index declared `FoldModel` `eq=False`; phase 4's code uses `@dataclass(frozen=True)`; phases 4 and 6 need value `==` for R5 ("two calls give `==` results", `BReport ==`) | Contract drift | index, 4, 5, 6 | Index contract amended to value equality (D20). Phase 4 unchanged; phase 6 H1 and Requires marked resolved |
| 2 | `calibration`: phase 4 drops NaN labels itself and raises below `DECILES` resolved labels; phase 5 assumed "always `DECILES` rows"; phase 6 passes `table.labels.label[idx]` unfiltered | Unmet assumption | 4, 5, 6 | All three now state one rule (D21): drops NaN itself, raises below 10 resolved labels, so a returning call gives exactly 10 non-empty deciles. Phase 4 item 4, phase 5 Requires, phase 6 Requires edited |
| 3 | `passed_nights` "traded": phase 4 = `len(sessions(trade_start, trade_end))`; phases 5/6 assume `len(run.snapshots) - 1` | Unmet assumption (verified equal) | 4, 5, 6 | Equal by `runner.run_backtest` (`snapshots[0]` at `prev_session(start)`, then one per session). Stated as phase 4 contract item 8 and in its docstring; phase 5 Requires/Handoffs and phase 6 Requires/H3 point to it |
| 4 | `gate_p6a` B-linear sentence: index said a plain "Strategy B" replace "in both"; phase 4 replaces the subject only; phase 5 tests the substring "by the pre-registered determinism switch" | Contract drift | index, 4, 5 | Phase 4's subject-only rule adopted (D22); exact subject string recorded in phase 4 item 5, phase 5 Requires and the index |
| 5 | `last-fold-model.label_sum`: phase 5 renders a JSON string of `repr(float)`; phase 7's contract and test accepted "a float, or a string" | Contract drift | 5, 7, index | String only (D23). Phase 7's Requires and `test_last_fold_line_is_a_valid_model_record` now assert `isinstance(str)` and `repr(float(s)) == s`; index contract updated |
| 6 | `STRATEGY_B_FROZEN` read: phase 2 does not re-export it; phase 7's test imported it by name at module import | Unmet assumption | 2, 5, 6, 7 | Every reader goes through `seer_engine.strategies.b` at call time (D24). Phase 7's three tests now bind `strategy_b.STRATEGY_B_FROZEN` locally; the `from ... import STRATEGY_B_FROZEN` is removed. Phases 5/6 already comply |
| 7 | Artifact identity: risk of asserting `dumps(loads(b)) == b` | Unmet assumption (checked) | 1, 6, 7 | No plan asserts it. Phase 6 compares the file to `dumps(<fresh model>)` and `loads(data) == model`; phase 7 uses `sha256(file bytes)` and `loads(b).digest`. Rule recorded (D25) in the index contract; phase 7 Step 5 cross-check says so |
| 8 | FrozenModel literal: phase 6 logs `FrozenModel(report='docs/backtests/<stem>.md', artifact='engine/data/models/<end>-strategy-b.pkl', train_end=date(..), sha256=..)`; phase 7 builds its literal from report + artifact | Duplicate work (benign) | 6, 7 | Both kept; phase 7 Step 5 now cross-checks its four values against phase 6's WARNING line, a mismatch being a phase 6 bug. Paths and field order agree with phase 2's `FrozenModel` and phase 5's `_frozen_json` |
| 9 | Phase 4 imports `_check_folds`, `_day`, `_session`, `_join`, `_GATE_NAMES` from frozen `walkforward.py` | Scope check | 4 | Allowed: read-only reuse of a law-frozen module (D1, D26). Phase 5 likewise imports `report`/`wf_report` private helpers and phase 6 `backtest_wf._pct`/`_num`, all read-only |
| 10 | Every CLI command (nightly included) now imports scikit-learn via `cli.discover` -> `backtest_b` -> `b_walkforward` -> `b_model`, and via `backtest.io` | Behavioral fork | 6 | Eager imports kept (D19); phase 6 Risk K1 cites D19. No plan does otherwise. `import seer_engine.strategies` still loads no sklearn (phases 1/2 tests) |
| 11 | Phase table said phase 6 touches 4 files; phase 6 touches 3 | Contract drift | index, 6 | Table set to 3; phase 6's Files note reworded |
| 12 | Test counts per phase unreconciled; phases 1–3 concurrent | Gap | all | Count table under Invariant 1 (verified from each plan's test functions and parametrizations: +29, +59, +30, +35, +27, +23, +6; final 970). Phases 1, 4, 5, 6 and 7 Verification/Exit lines now state their absolute counts |
| 13 | Public names beyond the index contract: phase 2 (`CLOSE_COL` etc., `Design.__post_init__`/`__len__`, `runtime_checkable Predictor`, `BParams` TypeError, `rank01` validation, `BPrepared.symbols` without SPY, non-finite `bracket` -> None), phase 5 (`top_features`, `BReport.curves()`/`gated_curve()`), phase 6 (`recompute_a2`), phase 3 (`label_orders` preconditions), phase 1 (artifact identity facts) | Contract drift (additive) | 1, 2, 3, 5, 6 | All added to the index contract |
| 14 | Phase 4 handoff told phase 6 to gate on "window or run metrics"; phase 5's `_validate` recomputes with `run_metrics(gated.run)` | Contract drift | 4, 5, 6 | Phase 4 handoff now states `run_metrics(gated.run)`, `curve_metrics(spy_tr)`, the run's span, exactly as phase 5 validates and phase 6 computes |
| 15 | Interfaces used across phases (item 12 of the caller's list) | Verification | 1–4 | All hold as written: `Labels` keyword construction (no `__post_init__`); `BModel.predict` on 0 rows -> empty float64; `b_model.KINDS`; `design_on(members, data_date)`; `Design` fields `data_date, symbols, X, close, atr`; `label_orders`' `0 < sl < limit < tp` met because phase 4 passes only rows whose `a._bracket` was valid (Decimal-ordered, and `float()` keeps the order). Recorded in phase 4 Handoffs |
| 16 | File collisions | Verification | all | `io.py`: phase 6 only. `strategies/__init__.py`, `indicators.py`: phase 2 only. `b.py`: phase 2 creates it; phase 7 edits only the `STRATEGY_B_FROZEN` line and the two comment lines above it, on a pass. No phase edits an out-of-scope file (phase 7's Bug protocol fixes only the owning phase's new module) |

## Decisions

| Fork | Chosen | Rung |
|---|---|---|
| D1 · Generalize `walkforward.py` vs a separate B driver (§3 "Walk-forward code" allows either) | **Separate `backtest/b_walkforward.py`.** It reuses `folds`, `diagnostics`, `window_metrics`, `curve_window_metrics`, `ParamsSchedule` and `run_backtest`. `walkforward.py`, `wf_report.py` and `backtest_wf.py` are not edited, so A2's output stays byte-identical by construction, and phase 7 checks it with `cmp` | 1: invariant "A2 byte-identical" (handover §3 Law) |
| D2 · Labeler semantics (§7) | **Session-aligned, mirroring `sim.step` and the runner exactly.** That covers fill only on the order session, `days_held` growing on sessions without a bar, the forced close at the last close after a symbol's final bar, and rows unresolved at the data end being excluded. Floats are fine for labels. Brackets are `float()` of the Decimal 4-dp `a._bracket` prices, computed before the labeler sees them | 4: handover §3 "Label" + §7 recommendation |
| D3 · Labeler parity check (§7) | A seeded synthetic sample of a few thousand rows, compared with `run_backtest` + a one-pick fake strategy. The test may use `np.random.default_rng(seed)`; the module may not (purity) | 4: §7 recommendation; 1: invariant 2 |
| D4 · Model as `params` (§7) | **`BParams(model)`**, with equality and hash from `BModel` = `(kind, n_features, digest)`. The digest is the sha256 of the tree's baseline and node arrays, or of the ridge coefficients and intercept. `RunResult.params` is then a `ParamsSchedule` of `BParams` that `_validate` can compare | 4: §7 recommendation ("identity by … content hash") |
| D5 · Bracket validity: a candidate rule or a pick rule | **A pick rule.** The rank universe is the candidates defined by §3, with no bracket check, so ranks need no Decimal. Picks drop invalid brackets after prediction. Training rows with an invalid bracket are excluded, because no order exists | 6: convention (performance), consistent with §3 "Candidates" and "Picks" |
| D6 · "log 20-day mean dollar volume" | **The ranked column is the dollar volume itself (`dollar_volume_20`).** `log` is strictly monotonic, so the cross-sectional rank is identical, and it keeps libm out of the bit-identity path | 4: §3 "Features" (every per-symbol feature is a rank) |
| D7 · Feature definitions left open | Returns are over k **bars** within the 200-bar window. The stdev uses ddof 0 over 20 one-bar returns. RSI(14) and ATR(14) are Wilder, seeded at the window start (the indicators' rule). `range_pos` is 0.5 when high == low. A candidate needs all 15 raw values finite | 6: convention (`indicators.py`) |
| D8 · Prepared shape (§7) | `prepare_b` stores the raw per-(symbol, date) features once. Ranks are computed per `data_date` at pick time, from the members passed in. The candidate table does the same once per date for training | 4: §7 recommendation |
| D9 · Ridge determinism | A fixed-block `einsum(optimize=False)` accumulation, then `np.linalg.solve` on 18×18, with an unpenalized intercept. Prediction is an explicit column loop. So the result never depends on BLAS threads or batch size | 1: invariant 5 |
| D10 · Tree determinism (§7) | **Verified 2026-10-03:** sklearn 1.9.1 HGB gives bit-identical predictions at 1.2M × 18 under `OMP_NUM_THREADS` 1, 7 and 24, and pickles are byte-identical across fits. Pin `scikit-learn>=1.9,<1.10`. Phase 1 tests it on synthetic data, and the command re-probes it on the real last fold (D13) | 1: invariant 5; §3 "Determinism" |
| D11 · Feature importance: permutation or split gain (§3 "Report contents") | **Split gain** (Σ node gain by feature over all trees), as shares. Permutation needs randomness that the purity rule forbids. For B-linear: \|coef\| × feature std | 1: invariant 2 (purity) |
| D12 · A2 on the chart (§7) | **Recompute** A2's combined walk-forward through `backtest_wf.tune_all` + `run_walk_forward(None)` over the same folds (about 4 min). Reading the committed CSV would break when the data end moves past 2026-10-02, and it carries no trades for the metrics table | 6: convention; §7 allows either |
| D13 · How the pre-registered determinism switch fires | **Automatically, in code.** `probe_determinism` refits the last fold's tree at 1 thread and at the default, and compares the digests. If they match, B is gated. If not, B-linear is gated, and the report and the verdict sentence say so. Nobody chooses this after seeing a result | 1: §3 "Determinism" (pre-registered switch) |
| D14 · Report layout (§7) | Three files: `.md`, `-equity.csv` (`date,b,b_linear,a2,spy_price,spy_tr`) and `-equity.svg`. No per-date predictions CSV, because it would be about 1.3M rows. The calibration and fold tables go in the Markdown | 4: §7 recommendation |
| D15 · Artifact format (§7) | `b_model.dumps` is a protocol-5 pickle of `(kind, n_features, estimator)` at `engine/data/models/<end>-strategy-b.pkl`. `STRATEGY_B_FROZEN = FrozenModel(report, artifact, train_end, sha256)`. The retrain recipe (rows, `label_sum`, `train_end`) is in the report's `last-fold-model` line. Phase 1 tests the round trip on synthetic data | 4: §7 recommendation |
| D16 · Training window start | Rows with `data_date ≥ prev_session(is_start)`. The data has no row with 200 bars before that, so this only makes P3b's anchor explicit | 4: §3 "Folds" |
| D17 · B-linear in the strategy | The same `STRATEGY_B` with a ridge `BParams`. The curves are told apart by name (`B`, `B-linear`), and both runs report `strategy_id` "B" | 6: convention |
| D18 · Parallelism | Sequential everywhere. Expected whole command: about 6–8 min (about 4 for the A2 recompute). Parallelize only above 60 min (§3 "Runtime") | 4: §3 "Runtime" |
| D19 · Eager vs lazy scikit-learn import in the CLI (`cli.discover` imports every command, so `backtest_b` makes every command, the nightly included, load scikit-learn, about 0.5–1 s) | **Eager, module-level imports.** scikit-learn is now a declared core dependency (phase 1), the CLI's convention is plain top-level imports, and a lazy import inside `execute` would hide the import graph. `import seer_engine.strategies` stays sklearn-free (phase 2) so P4's pick path can stay light; the readme records the startup cost | 6: convention (the surrounding code's top-level imports) |
| D20 · `FoldModel` equality (`eq=False` in the draft index vs value equality in phase 4's code) | **Value equality**, `@dataclass(frozen=True)`. Every field is value-comparable (`BModel` by kind, n_features, digest) | 2: exit criteria (phase 4 "two identical calls give `==` results", phase 6 "`==` `BReport`s"; R5) |
| D21 · Where unresolved labels are dropped for calibration, and its minimum | **`calibration` drops NaN labels itself and raises ValueError below `DECILES` resolved labels**, so a returning call always gives 10 non-empty deciles | 3: phase 4's code block |
| D22 · B-linear verdict wording (plain replace vs subject only) | **Subject only**: "Strategy B (as B-linear, by the pre-registered determinism switch)"; the fail tail "Strategy B's one round has failed on this data, and P4 stays blocked." is unchanged | 3: phase 4's code block (a plain replace would garble the tail) |
| D23 · `label_sum` in `last-fold-model` (number vs string) | **A JSON string holding `repr(float)`**, so it round-trips exactly; readers use `float(...)` | 3: phase 5's code block |
| D24 · How `STRATEGY_B_FROZEN` is read | **Not re-exported from `strategies/__init__.py`; always read as `seer_engine.strategies.b.STRATEGY_B_FROZEN` at call time** (phase 6 command, phase 7 test) | 3: phase 2's code block; the index's "read at call time" |
| D25 · Artifact identity | **`sha256(file bytes)` and `b_model.loads(bytes).digest`** (or `loads(b) == model`); never `dumps(loads(b)) == b`, which can differ by pickle framing for a tree (measured +26 bytes) | 3: phase 1's code block and measured fact; 1: invariant 5 |
| D26 · Reusing `walkforward.py`'s private helpers in `b_walkforward.py` | **Import `_check_folds`, `_day`, `_session`, `_join`, `_GATE_NAMES` read-only**, not copied; the module is frozen by law, so they cannot drift | 4: index Scope ("private … helpers … imported read-only") and D1 |

## Open Questions

(none)

## Rollback

- Every phase is additive. Revert its commit(s) on `feature/strategy-b-ranker`.
- The whole set: delete the branch. `main` is untouched until the orchestrator lands it.
- After landing: `git revert` the merge commit. No DB state is involved.

## Next

Execute the phases one at a time, starting at phase 1:

    /implement -f STRATEGY_B_RANKER_PLAN.md --phase 1

Or run the whole set as a swarm: a session per phase, concurrent wherever `Depends on` allows
(phases 1, 2 and 3 run together), resumable on any machine:

    /analyze-orchestrator -f STRATEGY_B_RANKER_PLAN.md

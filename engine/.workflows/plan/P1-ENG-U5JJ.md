> Adopted from `STRATEGY_B_RANKER_PLAN.md` phase 4. Source: `.workflows/plan/strategy-b-ranker/phase-4.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 4: B walk-forward: candidate table, purge, per-fold fits, runs, diagnostics, gate

**Plan set:** `STRATEGY_B_RANKER_PLAN.md`
**Analysis:** `20261003-180843-B6R1_code_analyzer.md`
**Satisfies:** R1 (the label purge), R3 (P4 identity and no look-ahead with real fitted tree and ridge models), R4 (P3b's folds, purged training, one chained portfolio, brackets across 31 Dec), R5 (`==` results, the determinism probe), R6 (purity of the new module)
**Depends on:** Phase 1 (`b_model`), Phase 2 (`b`), Phase 3 (`labels`)
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/backtest`

---

## Goal

After this phase, `seer_engine.backtest.b_walkforward` turns a `Market` and a `BPrepared` into:
- one candidate table: every candidate row of every data date, its Decimal bracket as floats, and
  its net-of-cost label;
- one purged training set and one fitted model per P3b fold, for both the tree and the ridge;
- one chained walk-forward run per model kind;
- the out-of-sample diagnostics that explain a result and never select anything (predictions,
  calibration deciles, passed nights);
- the one-sentence P6a verdict.

Nothing renders and nothing writes files. Phase 5 renders and phase 6 orchestrates. The new test
file proves the purge, P3b's folds, the year-boundary bracket rule, P4 identity with real
models, and determinism on a synthetic market.

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.
**Creates** (all in `engine/src/seer_engine/backtest/b_walkforward.py`, a new pure module):
- `B = "B"`, `B_LINEAR = "B-linear"`, `DECILES = 10`, `TOP_FEATURES = 5`.
- `CandidateTable` (frozen, `eq=False`). Fields: `data_dates`, `symbols`, `X`, `limit`, `tp`,
  `sl`, `labels`. Every array is read-only.
- `candidate_table(market, prepared, is_start, end) -> CandidateTable`.
- `training_mask(table, fold) -> np.ndarray[bool]`.
- `FoldModel` (frozen). Fields: `fold`, `model`, `rows`, `label_mean`, `label_sum`, `pred_mean`,
  `r2`, `positive_share`, `importance`.
- `train_folds(table, folds, kind) -> tuple[FoldModel, ...]`.
- `probe_determinism(table, fold) -> bool`.
- `BWalkForward` (frozen). Fields: `name`, `folds`, `fold_models`, `run`.
- `model_schedule(folds, fold_models) -> ParamsSchedule`.
- `walk_forward_b(market, prepared, folds, fold_models, name) -> BWalkForward`.
- `CalibrationRow` (frozen). Fields: `decile`, `rows`, `pred_min`, `pred_max`, `pred_mean`,
  `label_mean`.
- `oos_predictions(table, folds, fold_models) -> tuple[np.ndarray[int64], np.ndarray[float64]]`.
- `calibration(pred, label) -> tuple[CalibrationRow, ...]`.
- `passed_nights(table, folds, fold_models) -> tuple[int, int]`.
- `gate_p6a(wf, spy_tr, start, end, gated) -> tuning.Verdict`.

**Signature changes:** none.

**Where this phase is stricter than the index contract, or goes past it.** The reconciler
adopted all of these into the index contract (Reconciliation Log, Decisions D20–D22, D26).
1. **`FoldModel` uses value equality.** It is `@dataclass(frozen=True)`, not `eq=False`. Every
   field compares by value: `Fold`, `BModel` (by `kind`, `n_features` and `digest`), ints, finite
   floats or None, and a tuple of floats. Without this, `train_folds(...) == train_folds(...)`
   (R5 "== on repeat") and `BWalkForward ==` would compare by object identity. Phase 5's
   `_validate` can then compare fold models directly.
2. **`walk_forward_b` checks the model kind against the name:** `B` takes TREE models only, and
   `B_LINEAR` takes RIDGE models only. Anything else is a ValueError.
3. **`train_folds` and `probe_determinism` raise ValueError** when a fold has no training row.
   Without this, `b_model.check_xy`'s generic error would surface instead.
4. **`calibration`'s inputs and errors:**
   - `pred` and `label` must be 1-D float64 arrays of the same shape;
   - it drops rows whose label is NaN (unresolved) itself, so callers (phase 6) pass
     `table.labels.label[idx]` unfiltered;
   - it raises ValueError when fewer than `DECILES` rows have a resolved (finite) label, so
     every decile is non-empty;
   - so every call that returns gives exactly `DECILES` rows, deciles `1..DECILES` in order
     (phase 5's `_validate` relies on that);
   - "row index" in the ordering means the position in the arrays passed in.
5. **`gate_p6a` with `gated == B_LINEAR`** replaces only the sentence's subject (its first
   "Strategy B"). The fail sentence's tail, "Strategy B's one round has failed on this data, and
   P4 stays blocked.", stays as it is. A plain text replace would produce "Strategy B (as
   B-linear, …)'s one round". The subject is exactly
   `"Strategy B (as B-linear, by the pre-registered determinism switch)"`, so phase 5's test
   substring `"by the pre-registered determinism switch"` holds.
6. **`oos_predictions` returns `idx` as int64.**
7. **The module imports five private names from `walkforward.py`, read-only:** `_check_folds`,
   `_day`, `_session`, `_join` and `_GATE_NAMES`. `walkforward.py` is frozen by handover §3
   Law, so these cannot drift. They are not copied.
8. **`passed_nights`'s "traded" is the run's session count.** It is
   `len(dates.sessions(folds[0].trade_start, folds[-1].trade_end))`, which equals
   `len(walk_forward_b(...).run.snapshots) - 1` (`report._sessions(run)`: `snapshots[0]` is the
   starting cash on `prev_session(trade_start)`, then one per session). Phase 5's `_validate`
   and phase 6's `test_execute_report_fields` both assert this equality.

**Requires (from earlier phases):**
- **Phase 1** (`seer_engine.strategies.b_model`):
  - `TREE`, `RIDGE`, `KINDS`, `BModel` (with `.kind`, `.n_features`, `.digest` and
    `.predict(X)`);
  - `predict` on 0 rows returns an empty float64 array, and a row's value does not depend on
    the batch;
  - `fit(kind, X, y)`, which raises ValueError on an unknown kind;
  - `fit_tree(X, y, *, threads=)`, `fit_ridge(X, y)`, `importance(model, X)` and
    `r2(y, pred)`.
- **Phase 2** (`seer_engine.strategies.b`):
  - `FEATURE_NAMES` (18 names), `BPrepared` and `prepare_b`;
  - `BPrepared.design_on(members, data_date) -> Design`, whose fields are `symbols` (sorted),
    `X` (m, 18) float64, `close` and `atr`;
  - `BParams(model)`, `bracket(symbol, close, atr) -> Pick | None` (`Pick.limit_price` /
    `tp_price` / `sl_price` are 4-dp Decimals) and `STRATEGY_B`;
  - for every model, `picks_prepared(prepared, M, d, BParams(model)) == picks_from_design(design_on(M, d), ...)`.
- **Phase 3** (`seer_engine.backtest.labels`):
  - `Labels(label, resolved, reason, fill, exit)` can be built with keyword arguments, using
    float64 / `datetime64[D]` / int8 / float64 / float64 arrays of equal length;
  - `label_orders(history, symbols, data_dates, limit, tp, sl, end) -> Labels`, aligned with
    its input rows, where `symbols` is a list of str and `data_dates` is a `datetime64[D]`
    array.

**Reuses, without editing:**
- `walkforward`: `Fold`, `folds` (tests), `_check_folds`, `_day`, `_session`, `_join` and
  `_GATE_NAMES`;
- `runner`: `ParamsSchedule`, `RunResult` and `run_backtest`;
- `metrics`: `Metrics`, `checklist` and `fmt_signed_pct`;
- `tuning.Verdict`, `market.Market` and `dates`.

**Leaves alone (owned by others):**
- `strategies/b_model.py` (Phase 1), `strategies/b.py`, `strategies/indicators.py` and
  `strategies/__init__.py` (Phase 2), `backtest/labels.py` (Phase 3);
- `backtest/b_report.py` (Phase 5), `backtest/io.py` and `commands/backtest_b.py` (Phase 6);
- the docs, the frozen constant and the frozen test (Phase 7);
- every file the index lists as out of scope: `walkforward.py`, `wf_report.py`, `runner.py`,
  `metrics.py`, `tuning.py`, `report.py`, `market.py`, `benchmark.py`, `sim/*`, `a.py`, `a2.py`,
  `base.py`, `commands/backtest*.py` and every existing test file.

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/backtest/b_walkforward.py` | create (new file, lines 1–end) | the whole module below |
| `engine/tests/test_backtest_b_walkforward.py` | create (new file, lines 1–end) | 35 tests on one seeded synthetic market |

No other file changes. `test_strategy_purity.py` globs `backtest/*.py`, so the new module is
covered without editing it.

## Implementation Steps

### Step 1: The B walk-forward module
**File:** `engine/src/seer_engine/backtest/b_walkforward.py:1` (new)

**Change:** create the module.

**Performance at real scale** (about 2,750 data dates, about 1.3M candidate rows):
- **`candidate_table`:**
  - one `design_on` per data date, vectorized inside phase 2;
  - one Decimal `b.bracket` call per row. This is the only per-row Python, and it measured
    6.5 µs per `a._bracket` call, so about 13 s at 1.3M rows;
  - one `label_orders` call over every valid row (phase 3's vectorized labeler);
  - building X concatenates the per-date blocks, so memory peaks at about 2 × 190 MB, briefly.
- **`train_folds`:** 9 sequential fits. Each masked copy of X is at most about 150 MB, and it is
  released before the next fold.
- **`oos_predictions`:** one batch `predict` per fold.
- **`passed_nights`:** pure numpy over `oos_predictions`.

**Code:**
```python
"""Strategy B under P3b's anchored yearly walk-forward (roadmap P6a, handover §3).

Pure: no database, files, clock, logging or randomness (tests/test_strategy_purity.py globs this
module). ``commands/backtest_b.py`` times and logs around these calls. Nothing here is
A2-specific, and ``walkforward.py`` is reused, never edited (Decision D1).

The procedure, fixed before any B result was seen:

- ``candidate_table``: every candidate row of every data date from ``prev_session(is_start)``
  through ``prev_session(end)``, ordered by (data_date, symbol). X is that date's
  ``BPrepared.design_on`` matrix, bit for bit. The bracket is ``b.bracket``'s 4-dp Decimal
  prices as floats, or NaN when it is invalid (Decision D5). The label is
  ``labels.label_orders`` over the valid rows, reading bars through ``end`` only.
- ``training_mask`` (**the purge**): fold Y trains on rows with a valid bracket whose label
  resolved on or before ``tune_end(Y)``, from ``prev_session(tune_start)`` on (Decision D16). A
  row whose order was still open at ``tune_end`` is excluded, so no bar after ``tune_end(Y)``
  reaches fold Y's model.
- ``train_folds``: one fit per fold, sequential, in fold order. No hyperparameter search.
- ``walk_forward_b``: ONE ``run_backtest`` of ``STRATEGY_B`` from the first fold's trade start
  to the last fold's trade end. Its ``ParamsSchedule`` switches to fold Y's model at Y's first
  session. One portfolio: cash, positions and pending orders carry across 31 December, and an
  order keeps the bracket it was placed with.
- ``oos_predictions``, ``calibration`` and ``passed_nights`` explain a finished walk-forward. They
  never feed a fit or a choice. ``gate_p6a`` is P3b's gate (design §1 items 3-5), worded for B.
- ``probe_determinism``: the pre-registered switch (Decision D13). If the last fold's tree,
  refit at 1 thread and at the default thread count, gives two different digests, the gated
  curve is B-linear.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

import numpy as np

from seer_engine import dates
from seer_engine.backtest.labels import Labels, label_orders
from seer_engine.backtest.market import Market
from seer_engine.backtest.metrics import Metrics, checklist, fmt_signed_pct
from seer_engine.backtest.runner import ParamsSchedule, RunResult, run_backtest
from seer_engine.backtest.tuning import Verdict

# walkforward.py is frozen by handover §3 Law; its private helpers are reused read-only.
from seer_engine.backtest.walkforward import _GATE_NAMES, Fold, _check_folds, _day, _join, _session
from seer_engine.strategies import b_model
from seer_engine.strategies.b import FEATURE_NAMES, STRATEGY_B, BParams, BPrepared, bracket
from seer_engine.strategies.b_model import RIDGE, TREE, BModel

B = "B"  # curve name of the tree model (the gated one unless the determinism switch fires)
B_LINEAR = "B-linear"  # curve name of the ridge model (information; gated only via the switch)
DECILES = 10
TOP_FEATURES = 5  # how many features the report lists per fold (phase 5 reads this)

_N_FEATURES = len(FEATURE_NAMES)
_KIND_OF = {B: TREE, B_LINEAR: RIDGE}
_SUBJECT = {
    B: "Strategy B",
    B_LINEAR: "Strategy B (as B-linear, by the pre-registered determinism switch)",
}


# --------------------------------------------------------------------------- types


@dataclass(frozen=True, eq=False)
class CandidateTable:
    """Every candidate row from data_date ``prev_session(is_start)`` through ``prev_session(end)``,
    ordered by (data_date, symbol). Arrays are read-only and have one entry per row."""

    data_dates: np.ndarray  # datetime64[D] (n,)
    symbols: tuple[str, ...]  # (n,) one per row
    X: np.ndarray  # (n, 18) float64: the Design rows of that date, bit for bit
    limit: np.ndarray  # float64 (n,): float(Decimal) of b.bracket; NaN when the bracket is invalid
    tp: np.ndarray
    sl: np.ndarray
    labels: Labels  # label_orders(..., end) over the valid rows; NaN / NaT / -1 elsewhere


@dataclass(frozen=True)
class FoldModel:
    """One fold's fitted model and its in-fold training summary (information only)."""

    fold: Fold
    model: BModel
    rows: int  # training rows (training_mask(table, fold).sum())
    label_mean: float  # label_sum / rows
    label_sum: float  # math.fsum of the training labels (the retrain recipe's checksum)
    pred_mean: float  # in-fold mean prediction
    r2: float | None  # in-fold R²; None when the labels have no variance
    positive_share: float  # in-fold share of predictions > 0
    importance: tuple[float, ...]  # b_model.importance, FEATURE_NAMES order


@dataclass(frozen=True)
class BWalkForward:
    """One B curve: per-fold models chained into one run."""

    name: str  # B | B_LINEAR
    folds: tuple[Fold, ...]
    fold_models: tuple[FoldModel, ...]  # one per fold, folds order
    run: RunResult  # params is model_schedule(folds, fold_models)


@dataclass(frozen=True)
class CalibrationRow:
    """One prediction decile: how the mean prediction compares with the mean realized label."""

    decile: int  # 1..DECILES, ascending prediction
    rows: int
    pred_min: float
    pred_max: float
    pred_mean: float
    label_mean: float


# --------------------------------------------------------------------------- validation


def _readonly(arr: np.ndarray) -> np.ndarray:
    arr.setflags(write=False)
    return arr


def _table(table: object) -> CandidateTable:
    if not isinstance(table, CandidateTable):
        raise TypeError(f"table must be a CandidateTable, got {type(table).__name__}")
    return table


def _fold(fold: object) -> Fold:
    if not isinstance(fold, Fold):
        raise TypeError(f"fold must be a Fold, got {type(fold).__name__}")
    return fold


def _fold_models(fs: tuple[Fold, ...], fold_models: Sequence[FoldModel], kind: str | None = None) -> tuple[FoldModel, ...]:
    """``fold_models`` as a tuple aligned with ``fs`` (one per fold, same fold), else an error."""
    fms = tuple(fold_models)
    if len(fms) != len(fs):
        raise ValueError(f"{len(fs)} folds but {len(fms)} fold models")
    for f, fm in zip(fs, fms):
        if not isinstance(fm, FoldModel):
            raise TypeError(f"fold_models must hold FoldModel values, got {type(fm).__name__}")
        if fm.fold != f:
            raise ValueError(f"fold model for {fm.fold.year} is not aligned with fold {f.year}")
        if kind is not None and fm.model.kind != kind:
            raise ValueError(f"fold {f.year}: a {fm.model.kind!r} model where {kind!r} is expected")
    return fms


# --------------------------------------------------------------------------- the candidate table


def _labels(
    market: Market,
    symbols: Sequence[str],
    data_dates: np.ndarray,
    limit: np.ndarray,
    tp: np.ndarray,
    sl: np.ndarray,
    end: date,
) -> Labels:
    """``label_orders`` over the rows with a valid bracket, scattered back to every row."""
    n = len(symbols)
    label = np.full(n, np.nan, dtype=np.float64)
    resolved = np.full(n, np.datetime64("NaT", "D"), dtype="datetime64[D]")
    reason = np.full(n, -1, dtype=np.int8)
    fill = np.full(n, np.nan, dtype=np.float64)
    exit_ = np.full(n, np.nan, dtype=np.float64)
    idx = np.flatnonzero(~np.isnan(limit))
    if idx.size:
        sub = label_orders(
            market.history,
            [symbols[i] for i in idx.tolist()],
            data_dates[idx],
            limit[idx],
            tp[idx],
            sl[idx],
            end,
        )
        label[idx] = sub.label
        resolved[idx] = sub.resolved
        reason[idx] = sub.reason
        fill[idx] = sub.fill
        exit_[idx] = sub.exit
    return Labels(
        label=_readonly(label),
        resolved=_readonly(resolved),
        reason=_readonly(reason),
        fill=_readonly(fill),
        exit=_readonly(exit_),
    )


def candidate_table(market: Market, prepared: BPrepared, is_start: date, end: date) -> CandidateTable:
    """Every candidate of every data date in ``[prev_session(is_start), prev_session(end)]``.

    Row by row, the date's ``prepared.design_on(market.membership.members_on(d), d)``: the
    same members and the same matrix the runner's picks see for the session after ``d``. The
    bracket is ``b.bracket(symbol, close, atr)`` (A's design bracket, 4-dp Decimal) as floats,
    NaN when it is invalid. The labels read bars dated on or before ``end`` only.

    Raises TypeError on a wrong type, and ValueError when ``is_start`` or ``end`` is not an NYSE
    session or ``end < is_start``.
    """
    if not isinstance(market, Market):
        raise TypeError(f"market must be a Market, got {type(market).__name__}")
    if not isinstance(prepared, BPrepared):
        raise TypeError(f"prepared must be a BPrepared, got {type(prepared).__name__}")
    _session("is_start", is_start)
    _session("end", end)
    if end < is_start:
        raise ValueError(f"end {end} is before is_start {is_start}")

    day_blocks: list[np.ndarray] = []
    x_blocks: list[np.ndarray] = []
    symbols: list[str] = []
    limit: list[float] = []
    tp: list[float] = []
    sl: list[float] = []
    for d in dates.sessions(dates.prev_session(is_start), dates.prev_session(end)):
        design = prepared.design_on(market.membership.members_on(d), d)
        m = len(design.symbols)
        if m == 0:
            continue
        day_blocks.append(np.full(m, np.datetime64(d, "D"), dtype="datetime64[D]"))
        x_blocks.append(design.X)
        for symbol, close, atr in zip(design.symbols, design.close.tolist(), design.atr.tolist()):
            symbols.append(symbol)
            pick = bracket(symbol, close, atr)
            if pick is None:
                limit.append(math.nan)
                tp.append(math.nan)
                sl.append(math.nan)
            else:
                limit.append(float(pick.limit_price))
                tp.append(float(pick.tp_price))
                sl.append(float(pick.sl_price))

    if x_blocks:
        data_dates = np.concatenate(day_blocks)
        X = np.concatenate(x_blocks, axis=0).astype(np.float64, copy=False)
    else:
        data_dates = np.empty(0, dtype="datetime64[D]")
        X = np.empty((0, _N_FEATURES), dtype=np.float64)
    if X.shape[1] != _N_FEATURES:
        raise ValueError(f"design_on gave {X.shape[1]} columns, expected {_N_FEATURES}")
    limit_a = np.array(limit, dtype=np.float64)
    tp_a = np.array(tp, dtype=np.float64)
    sl_a = np.array(sl, dtype=np.float64)
    labels = _labels(market, symbols, data_dates, limit_a, tp_a, sl_a, end)
    return CandidateTable(
        data_dates=_readonly(data_dates),
        symbols=tuple(symbols),
        X=_readonly(X),
        limit=_readonly(limit_a),
        tp=_readonly(tp_a),
        sl=_readonly(sl_a),
        labels=labels,
    )


# --------------------------------------------------------------------------- the purge and the fits


def training_mask(table: CandidateTable, fold: Fold) -> np.ndarray:
    """Fold ``fold``'s training rows (the label purge).

    A valid bracket, a resolved label, resolved on or before ``fold.tune_end``, and
    data_date on or after ``prev_session(fold.tune_start)``.
    """
    t = _table(table)
    f = _fold(fold)
    first = np.datetime64(dates.prev_session(f.tune_start), "D")
    cut = np.datetime64(f.tune_end, "D")
    resolved = t.labels.resolved
    return (~np.isnan(t.limit)) & (~np.isnat(resolved)) & (resolved <= cut) & (t.data_dates >= first)


def _fold_rows(table: CandidateTable, fold: Fold) -> tuple[np.ndarray, np.ndarray]:
    mask = training_mask(table, fold)
    X = table.X[mask]
    y = table.labels.label[mask]
    if X.shape[0] == 0:
        raise ValueError(f"fold {fold.year} has no training row resolved by {fold.tune_end}")
    return X, y


def train_folds(table: CandidateTable, folds: Sequence[Fold], kind: str) -> tuple[FoldModel, ...]:
    """One ``b_model.fit(kind, ...)`` per fold on its purged rows. Sequential, in fold order.

    The summary fields are in-fold and information only. Sums are ``math.fsum``, so they do not
    depend on summation order.
    """
    t = _table(table)
    fs = _check_folds(folds)
    if not isinstance(kind, str) or kind not in b_model.KINDS:
        raise ValueError(f"unknown model kind {kind!r}, expected one of {b_model.KINDS}")
    out: list[FoldModel] = []
    for f in fs:
        X, y = _fold_rows(t, f)
        model = b_model.fit(kind, X, y)
        pred = model.predict(X)
        rows = int(X.shape[0])
        label_sum = math.fsum(y.tolist())
        out.append(
            FoldModel(
                fold=f,
                model=model,
                rows=rows,
                label_mean=label_sum / rows,
                label_sum=label_sum,
                pred_mean=math.fsum(pred.tolist()) / rows,
                r2=b_model.r2(y, pred),
                positive_share=int(np.count_nonzero(pred > 0.0)) / rows,
                importance=b_model.importance(model, X),
            )
        )
    return tuple(out)


def probe_determinism(table: CandidateTable, fold: Fold) -> bool:
    """True when ``fold``'s tree, fit at 1 thread and at the default thread count, has one digest.

    The pre-registered switch (Decision D13): False makes B-linear the gated curve.
    """
    t = _table(table)
    f = _fold(fold)
    X, y = _fold_rows(t, f)
    return b_model.fit_tree(X, y, threads=1).digest == b_model.fit_tree(X, y, threads=None).digest


# --------------------------------------------------------------------------- the walk-forward runs


def model_schedule(folds: Sequence[Fold], fold_models: Sequence[FoldModel]) -> ParamsSchedule:
    """Fold k's model, as ``BParams``, from fold k's first traded session on."""
    fs = _check_folds(folds)
    fms = _fold_models(fs, fold_models)
    return ParamsSchedule(segments=tuple((f.trade_start, BParams(fm.model)) for f, fm in zip(fs, fms)))


def walk_forward_b(
    market: Market,
    prepared: BPrepared,
    folds: Sequence[Fold],
    fold_models: Sequence[FoldModel],
    name: str,
) -> BWalkForward:
    """Trade every fold as ONE ``run_backtest`` of ``STRATEGY_B`` under ``model_schedule``.

    ``name`` is ``B`` (TREE fold models) or ``B_LINEAR`` (RIDGE fold models).
    """
    if not isinstance(name, str):
        raise TypeError(f"name must be a str, got {type(name).__name__}")
    if name not in _KIND_OF:
        raise ValueError(f"unknown curve name {name!r}, expected {B!r} or {B_LINEAR!r}")
    if not isinstance(prepared, BPrepared):
        raise TypeError(f"prepared must be a BPrepared, got {type(prepared).__name__}")
    fs = _check_folds(folds)
    fms = _fold_models(fs, fold_models, _KIND_OF[name])
    run = run_backtest(
        market, STRATEGY_B, model_schedule(fs, fms), fs[0].trade_start, fs[-1].trade_end, prepared=prepared
    )
    return BWalkForward(name=name, folds=fs, fold_models=fms, run=run)


# --------------------------------------------------------------------------- explaining a finished walk-forward


def _order_sessions(data_dates: np.ndarray) -> np.ndarray:
    """``next_session(d)`` for every (ascending) data date ``d``, vectorized."""
    if data_dates.size == 0:
        return np.empty(0, dtype="datetime64[D]")
    first = data_dates[0].item()
    last = data_dates[-1].item()
    sess = np.array(dates.sessions(first, dates.next_session(last)), dtype="datetime64[D]")
    return sess[np.searchsorted(sess, data_dates, side="right")]


def oos_predictions(
    table: CandidateTable, folds: Sequence[Fold], fold_models: Sequence[FoldModel]
) -> tuple[np.ndarray, np.ndarray]:
    """(row indices, predictions): every row with a valid bracket whose order session
    ``next_session(data_date)`` lies in a fold's ``[trade_start, trade_end]``, predicted by THAT
    fold's model, which is the model the walk-forward run used for that session. Rows ascend.
    Because a row's prediction does not depend on the batch, these are the exact floats
    ``picks_from_design`` compared with 0.0.
    """
    t = _table(table)
    fs = _check_folds(folds)
    fms = _fold_models(fs, fold_models)
    session = _order_sessions(t.data_dates)
    valid = ~np.isnan(t.limit)
    idx_parts: list[np.ndarray] = []
    pred_parts: list[np.ndarray] = []
    for f, fm in zip(fs, fms):
        inside = valid & (session >= np.datetime64(f.trade_start, "D")) & (session <= np.datetime64(f.trade_end, "D"))
        rows = np.flatnonzero(inside).astype(np.int64)
        idx_parts.append(rows)
        pred_parts.append(np.asarray(fm.model.predict(t.X[rows]), dtype=np.float64))
    return np.concatenate(idx_parts), np.concatenate(pred_parts)


def calibration(pred: np.ndarray, label: np.ndarray) -> tuple[CalibrationRow, ...]:
    """Mean prediction against mean realized label, by prediction decile.

    Rows with a resolved (finite) label only. They are ordered by (prediction, position in the
    arrays), then split into ``DECILES`` groups with ``np.array_split``, so the first groups take
    the remainder. Raises ValueError on mismatched or non-1-D inputs, on a non-finite prediction
    among the kept rows, or when fewer than ``DECILES`` labels are resolved.
    """
    p = np.asarray(pred)
    lab = np.asarray(label)
    if p.dtype != np.float64 or lab.dtype != np.float64:
        raise TypeError("pred and label must be float64 arrays")
    if p.ndim != 1 or lab.shape != p.shape:
        raise ValueError(f"pred {p.shape} and label {lab.shape} must be 1-D and the same shape")
    keep = np.flatnonzero(np.isfinite(lab)).astype(np.int64)
    if keep.size < DECILES:
        raise ValueError(f"{keep.size} resolved labels; calibration needs at least {DECILES}")
    if not np.isfinite(p[keep]).all():
        raise ValueError("every prediction of a resolved row must be finite")
    order = keep[np.lexsort((keep, p[keep]))]
    out: list[CalibrationRow] = []
    for k, group in enumerate(np.array_split(order, DECILES), start=1):
        gp = p[group]
        gl = lab[group]
        n = int(group.size)
        out.append(
            CalibrationRow(
                decile=k,
                rows=n,
                pred_min=float(gp[0]),
                pred_max=float(gp[-1]),
                pred_mean=math.fsum(gp.tolist()) / n,
                label_mean=math.fsum(gl.tolist()) / n,
            )
        )
    return tuple(out)


def passed_nights(
    table: CandidateTable, folds: Sequence[Fold], fold_models: Sequence[FoldModel]
) -> tuple[int, int]:
    """(sessions B passed, traded sessions) over ``[folds[0].trade_start, folds[-1].trade_end]``.

    A session passes when no candidate of its data date has a valid bracket and a prediction
    > 0.0, which is exactly when ``picks_from_design`` returns ``[]``. A session whose data
    date has no candidate at all passes too. "Traded sessions" is every NYSE session of the
    span, which is ``len(run.snapshots) - 1`` of the matching ``walk_forward_b`` run.
    """
    fs = _check_folds(folds)
    idx, pred = oos_predictions(table, fs, fold_models)
    traded = len(dates.sessions(fs[0].trade_start, fs[-1].trade_end))
    picked = np.unique(table.data_dates[idx[pred > 0.0]])
    return traded - int(picked.size), traded


# --------------------------------------------------------------------------- the P6a gate


def gate_p6a(wf: Metrics, spy_tr: Metrics, start: date, end: date, gated: str) -> Verdict:
    """The P6a gate on the gated walk-forward curve over ``[start, end]``.

    The same rule as P3b: the walk-forward total return beats total-return SPY (strict), with
    profit factor ≥ 1.3 and max drawdown ≤ 15% (``checklist`` items 3–5, the web's labels and
    values). ``gated`` is ``B``, or ``B_LINEAR`` only when the determinism switch fired, and
    then the sentence's subject says so.
    """
    if not isinstance(wf, Metrics) or not isinstance(spy_tr, Metrics):
        raise TypeError("gate_p6a takes two Metrics")
    _day("start", start)
    _day("end", end)
    if not isinstance(gated, str):
        raise TypeError(f"gated must be a str, got {type(gated).__name__}")
    if gated not in _SUBJECT:
        raise ValueError(f"gated must be {B!r} or {B_LINEAR!r}, got {gated!r}")
    beats, pf, dd = checklist(wf, spy_tr.total_return)[2:5]
    checks = (beats, pf, dd)
    passed = beats.ok and pf.ok and dd.ok
    subject = _SUBJECT[gated]
    said = (
        f"walk-forward from {start.isoformat()} to {end.isoformat()} it returned "
        f"{fmt_signed_pct(wf.total_return)} against {fmt_signed_pct(spy_tr.total_return)} for "
        f"total-return SPY, with profit factor {pf.val} and max drawdown {dd.val}"
    )
    if passed:
        sentence = f"{subject} passes the P6a gate: {said}."
    else:
        failed = [name for name, item in zip(_GATE_NAMES, checks) if not item.ok]
        sentence = (
            f"{subject} fails the P6a gate: {said}, so it fails on {_join(failed)}; "
            "Strategy B's one round has failed on this data, and P4 stays blocked."
        )
    return Verdict(passed=passed, checks=checks, sentence=sentence)
```

**Impact:**
- This is a new module, so nothing existing changes.
- Importing it loads scikit-learn through `b_model`. The purity test checks that this is
  allowed (analysis: sklearn loads none of psycopg, requests or yfinance).
- The source avoids every forbidden token: no `logging`, `time`, `random`, `.random`, `.now`,
  `.today`, `open()` or `print()`.

### Step 2: Tests on a seeded synthetic market
**File:** `engine/tests/test_backtest_b_walkforward.py:1` (new)

**The synthetic market:**
- **Sessions:** 2019-01-02 → 2021-06-30 (629 NYSE sessions).
- **`IS = SESSIONS[200]` = 2019-10-17.** Its data date, `SESSIONS[199]`, is the first with 200
  bars.
- **Folds:** `folds(IS, 2020, END)` gives two folds, 2020 and 2021 (to 2021-06-30).
- **Symbols:**
  - 20 seeded random walks, `S00`…`S19`. `S19` joins membership only on 2020-06-01, which tests
    point-in-time membership;
  - `ZZZ`: liquid, with closes alternating 1 and 3, so ATR > close/2. Its candidate rows have
    **invalid brackets**, which exercises the NaN rows and the dropped picks;
  - `ILQ`: illiquid, at about $4M a day, so it is never a candidate;
  - `SPY`: a walk that is never a member.

**Training rows and HGB:**
- Fold 2020 trains on roughly 900–1,000 rows (data dates 2019-10-16 → about 2019-12-20).
- Fold 2021 trains on roughly 6,000.
- Both exceed the 400 rows that `min_samples_leaf=200` needs for one split, and a test asserts
  ≥ 400 rows per fold.
- Fold 2020's trees are shallow (at most 4 leaves), and fold 2021's are fuller. That is enough
  for real, non-trivial fits.

**Determinism-heavy assertions use models whose output is known:**
- **Constant ridge fits** (`y` ≡ c, so the prediction is about c) force "every candidate picked"
  or "every night passed".
- **"Targeted" fits** (`y = X[:, 0] − 0.3`, which is positive for the top `ret_1` ranks) make
  picks non-empty on every date, so the identity tests are not vacuous.

**Runtime:** about 12 tree fits of at most about 9k × 18, at well under 1 s each, so the
expected wall time is about 15–25 s.

**Code:**
```python
"""B walk-forward (plan phase 4; handover §6.1 purge, §6.3, §6.4, §6.5).

One seeded synthetic market, 2019-01-02..2021-06-30:

- ``S00``..``S19``: seeded random walks (4-dp prices, lognormal volumes, $30M+ a day). ``S19`` is
  a member only from 2020-06-01 (point-in-time membership).
- ``ZZZ``: liquid, closes alternating 1 and 3, so ATR > close/2 and every bracket is invalid
  (NaN rows in the table, never picked).
- ``ILQ``: about $4M a day, never a candidate. ``SPY``: a walk, never a member.

``IS`` = 2019-10-17 (its data date is the first with 200 bars). The folds are ``folds(IS, 2020,
END)``: 2020, and 2021 to 2021-06-30. Fold 2020 trains on roughly 1,000 purged rows and fold
2021 on roughly 6,000, both above the 400 that HistGradientBoosting's ``min_samples_leaf=200``
needs for a split.
"""

from __future__ import annotations

import math
from dataclasses import replace
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

import numpy as np
import pytest
from simkit import D
from stratkit import hist, mutate_from

from seer_engine import dates
from seer_engine.backtest.b_walkforward import (
    B,
    B_LINEAR,
    DECILES,
    TOP_FEATURES,
    BWalkForward,
    CalibrationRow,
    FoldModel,
    calibration,
    candidate_table,
    gate_p6a,
    model_schedule,
    oos_predictions,
    passed_nights,
    probe_determinism,
    train_folds,
    training_mask,
    walk_forward_b,
)
from seer_engine.backtest.labels import label_orders
from seer_engine.backtest.market import Market, Membership
from seer_engine.backtest.metrics import Metrics, checklist
from seer_engine.backtest.runner import ParamsSchedule, run_backtest
from seer_engine.backtest.walkforward import Fold, folds
from seer_engine.strategies.b import FEATURE_NAMES, STRATEGY_B, BParams, bracket, prepare_b
from seer_engine.strategies.b_model import RIDGE, TREE, fit, fit_ridge, importance, r2
from seer_engine.strategies.base import History

SESSIONS = dates.sessions(D("2019-01-02"), D("2021-06-30"))
IS = SESSIONS[200]  # 2019-10-17: data date SESSIONS[199] has exactly 200 bars
END = SESSIONS[-1]  # 2021-06-30
FIRST_YEAR = 2020
WALKS = tuple(f"S{k:02d}" for k in range(20))
LATE, LATE_JOIN = "S19", D("2020-06-01")
WIDE, THIN, SPY = "ZZZ", "ILQ", "SPY"


# --------------------------------------------------------------------------- the synthetic market


def _walk(symbol: str, k: int, *, first: float, volume: float) -> History:
    """A seeded random walk rounded to 4 dp, with gaps, wicks and lognormal volumes."""
    n = len(SESSIONS)
    rng = np.random.default_rng(6000 + k)
    ret = rng.normal(0.0004, 0.02, n)
    gap = rng.normal(0.0, 0.005, n)
    up = np.abs(rng.normal(0.0, 0.010, n))
    down = np.abs(rng.normal(0.0, 0.012, n))
    vol = rng.lognormal(0.0, 0.3, n)
    o, h, lo, c = [], [], [], []
    prev = first
    for i in range(n):
        op = round(prev * (1 + gap[i]), 4)
        cl = round(prev * math.exp(ret[i]), 4)
        o.append(op)
        c.append(cl)
        h.append(round(max(op, cl) * (1 + up[i]), 4))
        lo.append(round(min(op, cl) * (1 - down[i]), 4))
        prev = cl
    return hist(symbol, c, days=SESSIONS, opens=o, highs=h, lows=lo, volumes=[float(round(volume * v)) for v in vol])


def _wide() -> History:
    """Closes 1, 3, 1, 3, …; high = close + 0.5, low = close − 0.5; $100M a day. ATR ≈ 2.5 > close/2."""
    closes = [1.0 if i % 2 == 0 else 3.0 for i in range(len(SESSIONS))]
    return hist(WIDE, closes, days=SESSIONS, volume=50_000_000.0)


def base_history() -> dict[str, History]:
    out = {s: _walk(s, k, first=30.0 + 5.0 * k, volume=1_000_000.0) for k, s in enumerate(WALKS)}
    out[WIDE] = _wide()
    out[THIN] = _walk(THIN, 50, first=40.0, volume=100_000.0)
    out[SPY] = _walk(SPY, 99, first=300.0, volume=50_000_000.0)
    return out


def b_market(history: dict[str, History] | None = None) -> Market:
    intervals = tuple((s, D("2015-01-02"), None) for s in WALKS if s != LATE)
    intervals += ((LATE, LATE_JOIN, None), (WIDE, D("2015-01-02"), None), (THIN, D("2015-01-02"), None))
    return Market(
        history=dict(base_history() if history is None else history),
        membership=Membership(intervals),  # SPY is never a member
        fx=((D("2018-12-31"), Decimal("16000")),),
    )


@pytest.fixture(scope="module")
def world():
    market = b_market()
    prepared = prepare_b(market.history)
    fs = folds(IS, FIRST_YEAR, END)
    table = candidate_table(market, prepared, IS, END)
    return SimpleNamespace(
        market=market,
        prepared=prepared,
        folds=fs,
        table=table,
        tree=train_folds(table, fs, TREE),
        ridge=train_folds(table, fs, RIDGE),
    )


@pytest.fixture(scope="module")
def runs(world):
    return {
        B: walk_forward_b(world.market, world.prepared, world.folds, world.tree, B),
        B_LINEAR: walk_forward_b(world.market, world.prepared, world.folds, world.ridge, B_LINEAR),
    }


@pytest.fixture(scope="module")
def targeted(world):
    """Real fits whose top ``ret_1`` ranks predict > 0 on every date (non-empty picks)."""
    t = world.table
    y = t.X[:, 0] - 0.3
    return {TREE: fit(TREE, t.X, y), RIDGE: fit(RIDGE, t.X, y)}


def _constant_models(world, values: tuple[float, ...]) -> tuple[FoldModel, ...]:
    """One ridge FoldModel per fold that predicts ≈ ``values[k]`` for every row (y ≡ value)."""
    X = np.ascontiguousarray(world.table.X[:50])
    out = []
    for f, v in zip(world.folds, values):
        model = fit_ridge(X, np.full(50, v, dtype=np.float64))
        out.append(
            FoldModel(
                fold=f, model=model, rows=50, label_mean=v, label_sum=50 * v, pred_mean=v, r2=None,
                positive_share=1.0 if v > 0 else 0.0, importance=(0.0,) * len(FEATURE_NAMES),
            )
        )
    return tuple(out)


def _next_sessions(t) -> np.ndarray:
    nxt = {d: dates.next_session(d) for d in sorted({x.item() for x in t.data_dates})}
    return np.array([nxt[x.item()] for x in t.data_dates], dtype="datetime64[D]")


# --------------------------------------------------------------------------- constants


def test_constants():
    assert (B, B_LINEAR, DECILES, TOP_FEATURES) == ("B", "B-linear", 10, 5)
    assert IS == D("2019-10-17") and END == D("2021-06-30")


# --------------------------------------------------------------------------- the candidate table


def test_candidate_table_rows_are_each_dates_design(world):
    t = world.table
    n = len(t.symbols)
    assert t.X.shape == (n, len(FEATURE_NAMES)) and t.X.dtype == np.float64
    for arr in (t.data_dates, t.limit, t.tp, t.sl):
        assert arr.shape == (n,)
        assert not arr.flags.writeable
    assert t.data_dates.dtype == np.dtype("datetime64[D]")
    seen = 0
    invalid = 0
    for d in dates.sessions(dates.prev_session(IS), dates.prev_session(END)):
        design = world.prepared.design_on(world.market.membership.members_on(d), d)
        rows = np.flatnonzero(t.data_dates == np.datetime64(d, "D"))
        assert rows.size == len(design.symbols)
        if rows.size == 0:
            continue
        assert rows.tolist() == list(range(seen, seen + rows.size))  # ordered by (date, symbol)
        assert tuple(t.symbols[i] for i in rows.tolist()) == design.symbols
        assert t.X[rows].tobytes() == np.ascontiguousarray(design.X).tobytes()
        for i, s, c, a in zip(rows.tolist(), design.symbols, design.close.tolist(), design.atr.tolist()):
            pick = bracket(s, c, a)
            got = (t.limit[i], t.tp[i], t.sl[i])
            if pick is None:
                assert all(math.isnan(v) for v in got)
                invalid += 1
            else:
                assert got == (float(pick.limit_price), float(pick.tp_price), float(pick.sl_price))
        seen += rows.size
    assert seen == n > 0
    assert invalid > 0 and all(t.symbols[i] == WIDE for i in np.flatnonzero(np.isnan(t.limit)).tolist())
    assert WIDE in t.symbols and THIN not in t.symbols and SPY not in t.symbols
    assert t.data_dates[0] == np.datetime64(dates.prev_session(IS), "D")
    assert t.data_dates[-1] == np.datetime64(dates.prev_session(END), "D")
    late = t.data_dates[np.array([s == LATE for s in t.symbols])]
    assert late.size > 0 and late.min() >= np.datetime64(LATE_JOIN, "D")


def test_candidate_table_labels_are_label_orders_on_the_valid_rows(world):
    t = world.table
    lab = t.labels
    valid = np.flatnonzero(~np.isnan(t.limit))
    invalid = np.flatnonzero(np.isnan(t.limit))
    direct = label_orders(
        world.market.history, [t.symbols[i] for i in valid.tolist()], t.data_dates[valid],
        t.limit[valid], t.tp[valid], t.sl[valid], END,
    )
    n = len(t.symbols)
    for name in ("label", "fill", "exit"):
        got = getattr(lab, name)
        assert got.shape == (n,) and got.dtype == np.float64
        assert got[valid].tobytes() == np.asarray(getattr(direct, name), dtype=np.float64).tobytes()
        assert np.isnan(got[invalid]).all()
    assert lab.resolved.dtype == np.dtype("datetime64[D]")
    assert lab.resolved[valid].view(np.int64).tolist() == np.asarray(direct.resolved).view(np.int64).tolist()
    assert np.isnat(lab.resolved[invalid]).all()
    assert lab.reason.dtype == np.int8
    assert lab.reason[valid].tolist() == np.asarray(direct.reason).tolist()
    assert (lab.reason[invalid] == -1).all()
    assert (lab.reason[valid] >= 0).any() and (lab.reason[valid] == -1).any()  # some still open at END


def test_candidate_table_rejects_bad_arguments(world):
    with pytest.raises(TypeError):
        candidate_table("market", world.prepared, IS, END)
    with pytest.raises(TypeError):
        candidate_table(world.market, None, IS, END)
    with pytest.raises(TypeError):
        candidate_table(world.market, world.prepared, datetime(2019, 10, 17), END)
    with pytest.raises(ValueError):
        candidate_table(world.market, world.prepared, D("2019-10-19"), END)  # a Saturday
    with pytest.raises(ValueError):
        candidate_table(world.market, world.prepared, END, IS)


# --------------------------------------------------------------------------- the purge


def test_training_mask_keeps_valid_rows_resolved_by_tune_end(world):
    t = world.table
    first = np.datetime64(dates.prev_session(IS), "D")
    for f in world.folds:
        m = training_mask(t, f)
        cut = np.datetime64(f.tune_end, "D")
        assert m.dtype == np.bool_ and m.shape == (len(t.symbols),)
        expect = np.array(
            [
                (not math.isnan(t.limit[i]))
                and (not np.isnat(t.labels.resolved[i]))
                and bool(t.labels.resolved[i] <= cut)
                and bool(t.data_dates[i] >= first)
                for i in range(len(t.symbols))
            ]
        )
        assert np.array_equal(m, expect)
        assert int(m.sum()) >= 400  # enough rows for min_samples_leaf=200 to split
        assert (t.data_dates[m] < cut).all()  # an order placed on tune_end resolves after it
        on_cut = (t.data_dates == cut) & ~np.isnan(t.limit)
        assert on_cut.any() and not (m & on_cut).any()
    later = replace(world.folds[0], tune_start=SESSIONS[230])
    m2 = training_mask(t, later)
    assert (m2 <= training_mask(t, world.folds[0])).all()
    assert (t.data_dates[m2] >= np.datetime64(SESSIONS[229], "D")).all()
    with pytest.raises(TypeError):
        training_mask(t, "2020")
    with pytest.raises(TypeError):
        training_mask("table", world.folds[0])


@pytest.mark.parametrize("year", [2020, 2021])
def test_mutating_every_bar_after_tune_end_leaves_the_fold_unchanged(world, year):
    k = [f.year for f in world.folds].index(year)
    f = world.folds[k]
    mutated = b_market({s: mutate_from(h, f.trade_start) for s, h in world.market.history.items()})  # SPY too
    mt = candidate_table(mutated, prepare_b(mutated.history), IS, END)
    t = world.table
    cut = np.datetime64(f.tune_end, "D")
    n = int(np.count_nonzero(t.data_dates <= cut))
    assert int(np.count_nonzero(mt.data_dates <= cut)) == n
    assert mt.symbols[:n] == t.symbols[:n]
    assert mt.X[:n].tobytes() == t.X[:n].tobytes()
    for name in ("limit", "tp", "sl"):
        assert getattr(mt, name)[:n].tobytes() == getattr(t, name)[:n].tobytes()
    m0, m1 = training_mask(t, f), training_mask(mt, f)
    assert np.array_equal(m0[:n], m1[:n]) and not m0[n:].any() and not m1[n:].any()
    assert mt.X[m1].tobytes() == t.X[m0].tobytes()
    assert mt.labels.label[m1].tobytes() == t.labels.label[m0].tobytes()
    assert mt.labels.resolved[m1].tobytes() == t.labels.resolved[m0].tobytes()
    assert train_folds(mt, (f,), TREE) == (world.tree[k],)  # same rows, same labels, same digest
    assert mt.X[n:].tobytes() != t.X[n:].tobytes()  # the change is real after tune_end


# --------------------------------------------------------------------------- folds and fits


def test_the_folds_are_p3bs(world, runs):
    assert world.folds == folds(IS, FIRST_YEAR, END)
    assert [(f.year, f.tune_start, f.tune_end, f.trade_start, f.trade_end) for f in world.folds] == [
        (2020, IS, D("2019-12-31"), D("2020-01-02"), D("2020-12-31")),
        (2021, IS, D("2020-12-31"), D("2021-01-04"), END),
    ]
    for fms in (world.tree, world.ridge):
        assert tuple(fm.fold for fm in fms) == world.folds
    for w in runs.values():
        assert w.folds == world.folds and tuple(fm.fold for fm in w.fold_models) == world.folds


@pytest.mark.parametrize("kind", [TREE, RIDGE])
def test_train_folds_fits_each_fold_on_its_purged_rows(world, kind):
    fms = world.tree if kind == TREE else world.ridge
    assert len(fms) == len(world.folds)
    for f, fm in zip(world.folds, fms):
        m = training_mask(world.table, f)
        X, y = world.table.X[m], world.table.labels.label[m]
        model = fit(kind, X, y)
        pred = model.predict(X)
        rows = int(m.sum())
        assert fm == FoldModel(
            fold=f,
            model=model,
            rows=rows,
            label_mean=math.fsum(y.tolist()) / rows,
            label_sum=math.fsum(y.tolist()),
            pred_mean=math.fsum(pred.tolist()) / rows,
            r2=r2(y, pred),
            positive_share=int(np.count_nonzero(pred > 0.0)) / rows,
            importance=importance(model, X),
        )
        assert fm.model.kind == kind and fm.model.n_features == len(FEATURE_NAMES)
        assert len(fm.importance) == len(FEATURE_NAMES) and math.isclose(sum(fm.importance), 1.0)
        assert 0.0 <= fm.positive_share <= 1.0
    assert fms[0].rows < fms[1].rows  # anchored: the later fold sees more
    assert fms[0].model != fms[1].model


def test_train_folds_rejects_bad_kinds_and_folds_without_rows(world):
    with pytest.raises(ValueError):
        train_folds(world.table, world.folds, "forest")
    with pytest.raises(ValueError):
        train_folds(world.table, (), TREE)
    with pytest.raises(TypeError):
        train_folds("table", world.folds, TREE)
    no_brackets = replace(world.table, limit=np.full_like(world.table.limit, np.nan))
    with pytest.raises(ValueError):
        train_folds(no_brackets, world.folds, RIDGE)
    with pytest.raises(ValueError):
        probe_determinism(no_brackets, world.folds[-1])


def test_probe_determinism_is_true_on_synthetic_data(world):
    assert probe_determinism(world.table, world.folds[-1]) is True


# --------------------------------------------------------------------------- schedule and runs


def test_model_schedule_switches_at_each_trade_start(world):
    sched = model_schedule(world.folds, world.tree)
    p0, p1 = BParams(world.tree[0].model), BParams(world.tree[1].model)
    assert sched == ParamsSchedule(segments=((D("2020-01-02"), p0), (D("2021-01-04"), p1)))
    assert sched.at(D("2020-12-31")) == p0
    assert sched.at(D("2021-01-04")) == p1
    assert p0 != p1


def test_model_schedule_rejects_misaligned_fold_models(world):
    with pytest.raises(ValueError):
        model_schedule(world.folds, world.tree[:1])
    with pytest.raises(ValueError):
        model_schedule(world.folds, world.tree[::-1])
    with pytest.raises(TypeError):
        model_schedule(world.folds, (world.tree[0], "model"))


def test_an_order_open_across_31_december_keeps_the_bracket_it_was_placed_with(world):
    fms = _constant_models(world, (0.01, 0.02))  # two different models, both pick every valid candidate
    assert fms[0].model != fms[1].model
    w = walk_forward_b(world.market, world.prepared, world.folds, fms, B_LINEAR)
    assert w.run.params.segments == ((D("2020-01-02"), BParams(fms[0].model)), (D("2021-01-04"), BParams(fms[1].model)))
    t = world.table
    row = {(t.data_dates[i].item(), s): i for i, s in enumerate(t.symbols)}
    orders = w.run.closed + w.run.open_at_end
    assert orders
    for o in orders:
        i = row[(dates.prev_session(o.session_date), o.symbol)]
        assert (float(o.limit_price), float(o.tp_price), float(o.sl_price)) == (t.limit[i], t.tp[i], t.sl[i])
        assert o.symbol != WIDE  # invalid brackets are never picked
    across = [o for o in w.run.closed if o.fill_date <= D("2020-12-31") and o.exit_date >= D("2021-01-04")]
    assert across  # placed under fold 2020's model, closed under fold 2021's, bracket unchanged


def test_walk_forward_b_trades_every_fold_as_one_run(world, runs):
    for name, fms in ((B, world.tree), (B_LINEAR, world.ridge)):
        w = runs[name]
        assert isinstance(w, BWalkForward)
        assert (w.name, w.folds, w.fold_models) == (name, world.folds, fms)
        sched = model_schedule(world.folds, fms)
        assert w.run.params == sched
        assert w.run == run_backtest(world.market, STRATEGY_B, sched, D("2020-01-02"), END, prepared=world.prepared)
        assert w.run.strategy_id == "B"
        assert [s.date for s in w.run.snapshots] == [D("2019-12-31")] + dates.sessions(D("2020-01-02"), END)
        assert w.run.usd_idr == Decimal("16000")  # starting cash once, never reset at a year start


def test_walk_forward_b_rejects_bad_names_kinds_and_prepared(world):
    with pytest.raises(ValueError):
        walk_forward_b(world.market, world.prepared, world.folds, world.tree, "A2")
    with pytest.raises(TypeError):
        walk_forward_b(world.market, world.prepared, world.folds, world.tree, None)
    with pytest.raises(ValueError):
        walk_forward_b(world.market, world.prepared, world.folds, world.ridge, B)  # ridge models under B
    with pytest.raises(ValueError):
        walk_forward_b(world.market, world.prepared, world.folds, world.tree, B_LINEAR)
    with pytest.raises(TypeError):
        walk_forward_b(world.market, None, world.folds, world.tree, B)


# --------------------------------------------------------------------------- P4 identity and no look-ahead


@pytest.mark.parametrize("kind", [TREE, RIDGE])
def test_p4_identity_with_real_fitted_models(world, targeted, kind):
    trained = (world.tree if kind == TREE else world.ridge)[-1].model
    days = SESSIONS[199:-1:37]
    nonempty = 0
    for model in (targeted[kind], trained):
        p = BParams(model)
        for d in days:
            members = world.market.membership.members_on(d)
            cut = {s: h.upto(d) for s, h in world.market.history.items()}
            prepared_picks = STRATEGY_B.picks_prepared(world.prepared, members, d, p)
            assert prepared_picks == STRATEGY_B.picks(cut, members, d, p)
            if model is targeted[kind]:
                nonempty += bool(prepared_picks)
    assert nonempty == len(days)  # the identity is not vacuous


def test_bars_dated_on_or_after_the_session_never_change_its_picks(world, targeted):
    for session in (D("2020-06-15"), D("2021-01-04")):
        d = dates.prev_session(session)
        mutated = b_market({s: mutate_from(h, session) for s, h in world.market.history.items()})  # SPY too
        mp = prepare_b(mutated.history)
        members = world.market.membership.members_on(d)
        for model in (targeted[TREE], targeted[RIDGE], world.tree[-1].model, world.ridge[-1].model):
            p = BParams(model)
            base = STRATEGY_B.picks_prepared(world.prepared, members, d, p)
            assert STRATEGY_B.picks_prepared(mp, members, d, p) == base
            if model is targeted[TREE] or model is targeted[RIDGE]:
                assert base != []


# --------------------------------------------------------------------------- out-of-sample diagnostics


def test_oos_predictions_use_each_folds_model(world):
    t = world.table
    idx, pred = oos_predictions(t, world.folds, world.tree)
    assert idx.dtype == np.int64 and pred.dtype == np.float64 and idx.shape == pred.shape
    assert (np.diff(idx) > 0).all()
    session = _next_sessions(t)
    lo, hi = np.datetime64(world.folds[0].trade_start, "D"), np.datetime64(world.folds[-1].trade_end, "D")
    expected = np.flatnonzero(~np.isnan(t.limit) & (session >= lo) & (session <= hi))
    assert idx.tolist() == expected.tolist()
    assert t.data_dates[idx[0]] == np.datetime64(world.folds[0].tune_end, "D")
    for f, fm in zip(world.folds, world.tree):
        inside = (session[idx] >= np.datetime64(f.trade_start, "D")) & (session[idx] <= np.datetime64(f.trade_end, "D"))
        rows = idx[inside]
        assert rows.size > 0
        assert pred[inside].tobytes() == fm.model.predict(t.X[rows]).tobytes()
        for j in np.flatnonzero(inside)[:3].tolist():  # one row alone gives the same float
            assert fm.model.predict(t.X[idx[j] : idx[j] + 1])[0] == pred[j]
    in21 = session[idx] >= np.datetime64(world.folds[1].trade_start, "D")
    assert pred[in21].tobytes() != world.tree[0].model.predict(t.X[idx[in21]]).tobytes()  # not fold 2020's model


def test_calibration_hand_checked():
    pred = np.array([0.5, -0.125, 0.0625, 0.0625, 0.25, -0.25, 0.125, 0.75, 0.0, 0.375, -0.0625, 0.1875, 1.0])
    label = np.array(
        [0.03125, -0.0625, 0.0, 0.125, 0.015625, -0.03125, 0.0, 0.0625, np.nan, 0.046875, -0.015625, 0.0078125, np.nan]
    )
    # 11 resolved rows (8 and 12 are not), ordered by (pred, position):
    # 5, 1 | 10 | 2 | 3 | 6 | 11 | 4 | 9 | 0 | 7  — array_split gives the first decile the extra row,
    # and the tie at 0.0625 keeps position order (row 2 before row 3).
    assert calibration(pred, label) == (
        CalibrationRow(1, 2, -0.25, -0.125, -0.1875, -0.046875),
        CalibrationRow(2, 1, -0.0625, -0.0625, -0.0625, -0.015625),
        CalibrationRow(3, 1, 0.0625, 0.0625, 0.0625, 0.0),
        CalibrationRow(4, 1, 0.0625, 0.0625, 0.0625, 0.125),
        CalibrationRow(5, 1, 0.125, 0.125, 0.125, 0.0),
        CalibrationRow(6, 1, 0.1875, 0.1875, 0.1875, 0.0078125),
        CalibrationRow(7, 1, 0.25, 0.25, 0.25, 0.015625),
        CalibrationRow(8, 1, 0.375, 0.375, 0.375, 0.046875),
        CalibrationRow(9, 1, 0.5, 0.5, 0.5, 0.03125),
        CalibrationRow(10, 1, 0.75, 0.75, 0.75, 0.0625),
    )
    even = calibration(np.arange(100, dtype=np.float64)[::-1] / 128.0, np.arange(100, dtype=np.float64)[::-1] / 64.0)
    assert [r.rows for r in even] == [10] * 10
    assert (even[0].pred_min, even[0].pred_max, even[-1].pred_max) == (0.0, 9 / 128.0, 99 / 128.0)
    assert [r.label_mean for r in even] == [2.0 * r.pred_mean for r in even]


def test_calibration_rejects_bad_input():
    ok = np.arange(12, dtype=np.float64)
    with pytest.raises(ValueError):
        calibration(ok, ok[:11])
    with pytest.raises(ValueError):
        calibration(ok.reshape(3, 4), ok.reshape(3, 4))
    with pytest.raises(ValueError):
        calibration(ok, np.where(ok < 3, ok, np.nan))  # 3 resolved < DECILES
    with pytest.raises(ValueError):
        calibration(np.where(ok == 0, np.nan, ok), ok)
    with pytest.raises(TypeError):
        calibration(np.arange(12), ok)


def test_passed_nights_are_the_sessions_without_picks(world, runs):
    sessions = dates.sessions(world.folds[0].trade_start, world.folds[-1].trade_end)
    for name, fms in ((B, world.tree), (B_LINEAR, world.ridge)):
        sched = runs[name].run.params
        empty = 0
        for session in sessions:
            d = dates.prev_session(session)
            members = world.market.membership.members_on(d)
            if not STRATEGY_B.picks_prepared(world.prepared, members, d, sched.at(session)):
                empty += 1
        assert passed_nights(world.table, world.folds, fms) == (empty, len(sessions))


def test_passed_nights_when_every_prediction_is_negative_or_positive(world):
    n = len(dates.sessions(D("2020-01-02"), END))
    assert passed_nights(world.table, world.folds, _constant_models(world, (-0.01, -0.02))) == (n, n)
    assert passed_nights(world.table, world.folds, _constant_models(world, (0.01, 0.02))) == (0, n)


# --------------------------------------------------------------------------- the P6a gate


def M(ret, pf=1.5, dd=0.10, trades=120, months=105.0):
    return Metrics(total_return=ret, win_rate=0.55, profit_factor=pf, max_drawdown=dd, trades=trades, months=months)


SPY_TR = Metrics(total_return=0.75, win_rate=None, profit_factor=None, max_drawdown=0.20, trades=0, months=105.0)
GATE_START, GATE_END = D("2018-01-02"), D("2026-10-02")
SWITCHED = "Strategy B (as B-linear, by the pre-registered determinism switch)"
SUBJECTS = [(B, "Strategy B"), (B_LINEAR, SWITCHED)]


@pytest.mark.parametrize(("gated", "subject"), SUBJECTS)
def test_gate_p6a_pass_sentence(gated, subject):
    wf_m = M(0.80, pf=1.5, dd=0.12, trades=300)
    v = gate_p6a(wf_m, SPY_TR, GATE_START, GATE_END, gated)
    assert v.passed
    assert v.checks == tuple(checklist(wf_m, 0.75)[2:5])
    assert v.sentence == (
        f"{subject} passes the P6a gate: walk-forward from 2018-01-02 to 2026-10-02 it returned "
        "+80.0% against +75.0% for total-return SPY, with profit factor 1.50 and max drawdown 12.0%."
    )


@pytest.mark.parametrize(("gated", "subject"), SUBJECTS)
def test_gate_p6a_fail_sentence_names_every_failed_check_and_blocks_p4(gated, subject):
    v = gate_p6a(M(-0.10, pf=0.9, dd=0.30), SPY_TR, GATE_START, GATE_END, gated)
    assert not v.passed
    assert v.sentence == (
        f"{subject} fails the P6a gate: walk-forward from 2018-01-02 to 2026-10-02 it returned "
        "−10.0% against +75.0% for total-return SPY, with profit factor 0.90 and max drawdown 30.0%, "
        "so it fails on beating total-return SPY, profit factor ≥ 1.3 and max drawdown ≤ 15%; "
        "Strategy B's one round has failed on this data, and P4 stays blocked."
    )


@pytest.mark.parametrize(
    ("wf_m", "name"),
    [
        (M(0.70, pf=1.5, dd=0.12), "beating total-return SPY"),
        (M(0.80, pf=1.29, dd=0.12), "profit factor ≥ 1.3"),
        (M(0.80, pf=1.5, dd=0.151), "max drawdown ≤ 15%"),
    ],
)
def test_gate_p6a_fails_on_each_condition_alone(wf_m, name):
    v = gate_p6a(wf_m, SPY_TR, GATE_START, GATE_END, B)
    assert not v.passed
    assert v.sentence.endswith(
        f", so it fails on {name}; Strategy B's one round has failed on this data, and P4 stays blocked."
    )


def test_gate_p6a_boundaries_and_bad_arguments():
    assert not gate_p6a(M(0.75, pf=1.5, dd=0.12), SPY_TR, GATE_START, GATE_END, B).passed  # equal is not beating
    assert gate_p6a(M(0.80, pf=1.3, dd=0.15), SPY_TR, GATE_START, GATE_END, B).passed  # inclusive thresholds
    inf = gate_p6a(M(0.80, pf=math.inf, dd=0.10), SPY_TR, GATE_START, GATE_END, B)
    assert inf.passed and "profit factor ∞" in inf.sentence
    with pytest.raises(TypeError):
        gate_p6a(M(0.80), SPY_TR, "2018-01-02", GATE_END, B)
    with pytest.raises(TypeError):
        gate_p6a("metrics", SPY_TR, GATE_START, GATE_END, B)
    with pytest.raises(TypeError):
        gate_p6a(M(0.80), SPY_TR, GATE_START, GATE_END, None)
    with pytest.raises(ValueError):
        gate_p6a(M(0.80), SPY_TR, GATE_START, GATE_END, "A2")


# --------------------------------------------------------------------------- determinism and purity


def test_identical_calls_give_equal_results(world, runs):
    t = world.table
    t2 = candidate_table(world.market, prepare_b(world.market.history), IS, END)
    assert t2.symbols == t.symbols
    for name in ("data_dates", "X", "limit", "tp", "sl"):
        assert getattr(t2, name).tobytes() == getattr(t, name).tobytes()
    for name in ("label", "resolved", "reason", "fill", "exit"):
        assert getattr(t2.labels, name).tobytes() == getattr(t.labels, name).tobytes()
    assert train_folds(t2, world.folds, TREE) == world.tree
    assert train_folds(t2, world.folds, RIDGE) == world.ridge
    assert walk_forward_b(world.market, world.prepared, world.folds, world.tree, B) == runs[B]
    assert walk_forward_b(world.market, world.prepared, world.folds, world.ridge, B_LINEAR) == runs[B_LINEAR]
    for fms in (world.tree, world.ridge):
        i1, p1 = oos_predictions(t, world.folds, fms)
        i2, p2 = oos_predictions(t2, world.folds, fms)
        assert i1.tobytes() == i2.tobytes() and p1.tobytes() == p2.tobytes()
        assert calibration(p1, t.labels.label[i1]) == calibration(p2, t2.labels.label[i2])
        assert passed_nights(t, world.folds, fms) == passed_nights(t2, world.folds, fms)


def test_the_purity_glob_covers_the_module():
    from test_strategy_purity import _module_name, _pure_sources

    assert "seer_engine.backtest.b_walkforward" in {_module_name(p) for p in _pure_sources()}
```

**Impact:** 35 new tests. Two are pytest parametrizations, so they count once per case:
- 1 constants;
- 3 candidate table;
- 1 training mask;
- 2 purge (2020 and 2021);
- 1 folds;
- 2 `train_folds` (TREE and RIDGE);
- 1 `train_folds` errors;
- 1 probe;
- 2 schedule;
- 1 year-boundary bracket;
- 2 run and run errors;
- 2 P4 identity (TREE and RIDGE);
- 1 no look-ahead;
- 1 `oos_predictions`;
- 2 calibration;
- 2 passed nights;
- 2 + 2 gate sentences (B and B-linear, pass and fail);
- 3 gate single-condition;
- 1 gate boundaries and errors;
- 1 `==` on repeat;
- 1 purity glob.

That totals 1+3+1+2+1+2+1+1+2+1+2+2+1+1+2+2+4+3+1+1+1 = **35**.

## Verification

**Setup** (the worktree's own venv; phase 1 has added scikit-learn):
```
cd /home/miftah/.worktrees/seer/strategy-b-ranker
test -x engine/.venv/bin/python || python3 -m venv engine/.venv
engine/.venv/bin/pip install -e 'engine[dev]'
docker start seer-pg
```

**Build:**
```
engine/.venv/bin/python -c "import seer_engine.backtest.b_walkforward as m; print(m.B, m.B_LINEAR)"
```

**Tests:**
```
engine/.venv/bin/pytest engine/tests/test_backtest_b_walkforward.py -q
engine/.venv/bin/pytest engine/tests/test_strategy_purity.py -q
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q
```

**Expected count:** the result of phases 1–3 plus **35 passed**, with 0 skipped: 761 + 29 + 59
+ 30 = 879 before this phase, **914 passed** after it (the index's count table).

**Manual check:**
- `git diff --stat 0e91d8a -- engine/src/seer_engine/backtest/{walkforward,wf_report,runner,metrics,tuning,report,market,benchmark}.py engine/src/seer_engine/sim engine/src/seer_engine/strategies/a.py engine/src/seer_engine/strategies/a2.py engine/src/seer_engine/strategies/base.py engine/src/seer_engine/commands engine/tests/test_*.py`
  must list nothing beyond the new test files that phases 1–4 add.
- `grep -nE "\b(logging|time|random)\b|\.now|open\(|print\(" engine/src/seer_engine/backtest/b_walkforward.py`
  must print nothing.

**Exit criteria:**
- `b_walkforward.py` exists exactly as above, and the 35 new tests pass.
- The full suite is green with 0 skipped.
- The purity glob covers `seer_engine.backtest.b_walkforward`.
- No out-of-scope file differs from `0e91d8a`.

## Handoffs

- **Phase 5 (`b_report.py`):**
  - Top features per fold: the `TOP_FEATURES` largest `FoldModel.importance` shares. Break ties
    by `FEATURE_NAMES` order, for example by sorting on `(-share, index)`. Phase 4 deliberately
    adds no helper for this, because the index contract has none.
  - `CalibrationRow` and `passed_nights` come in through `BReport`.
  - `_validate` can compare `b.run.params == model_schedule(b.folds, b.fold_models)`, now that
    `FoldModel` has value equality.
- **Phase 6 (`commands/backtest_b.py`):**
  - Calibration input: `idx, pred = oos_predictions(table, folds, fms)`, then
    `calibration(pred, table.labels.label[idx])`.
  - `candidate_rows = len(table.symbols)`.
  - `labelled_rows = int(np.count_nonzero(~np.isnat(table.labels.resolved)))`. Unresolved and
    invalid rows are NaT, so this counts exactly "valid bracket and resolved".
  - `gate_p6a(run_metrics(gated.run), curve_metrics(spy_tr), gated.run.start, gated.run.end, gated)`:
    exactly what phase 5's `_validate` recomputes (`run.start`/`run.end` are
    `folds[0].trade_start`/`folds[-1].trade_end`).
  - Pass `end` (the data end) as both `candidate_table`'s `end` and `walkforward.folds`'s `end`.
  - **Do not set `OMP_NUM_THREADS`** (or any thread limit) in the process before
    `probe_determinism`. Otherwise "default threads" is 1, and the probe proves nothing.
- **Phase 7:** at real scale, record the wall time of `candidate_table`. It is mostly the Decimal
  bracket loop, about 13 s at 1.3M rows, plus phase 3's labeler. Also record the peak RSS. While
  X's per-date blocks are concatenated it briefly holds about 2 × 190 MB.
- **Phases 1–3 (assumptions this plan depends on):** the signatures listed under **Requires**.
  In particular:
  - `Labels` takes keyword construction;
  - `label_orders` takes a list of str and a `datetime64[D]` array;
  - `BModel.predict` returns an empty float64 array on 0 rows;
  - `b_model.KINDS` exists.

  The reconciler checked each one against phases 1–3's code blocks: all hold as written
  (`Labels` has no `__post_init__`; `label_orders` requires `0 < sl < limit < tp` on every row,
  which `_labels` meets by passing only the valid-bracket rows, since a non-None `a._bracket`
  guarantees it and `float()` of distinct 4-dp Decimals keeps the order).

## Rollback

Delete `engine/src/seer_engine/backtest/b_walkforward.py` and
`engine/tests/test_backtest_b_walkforward.py`, or revert this phase's commit. Nothing else
changed. Phases 5–7 depend on this module, so they would have to be rolled back first.

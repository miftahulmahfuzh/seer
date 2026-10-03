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

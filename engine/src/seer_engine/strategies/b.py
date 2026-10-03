"""Strategy B: a learned cross-sectional ranker (roadmap P6a, handover 2026-10-03 §3).

Candidates on ``data_date`` d (Strategy A's eligible set):
    a member on d, not ``SPY_SYMBOL``, a bar dated d, at least ``LOOKBACK`` bars through d,
    20-day mean close×volume > ``MIN_DOLLAR_VOLUME`` (strict), all 15 raw ``SYMBOL_FEATURES``
    finite, AND SPY's three features defined on d (SPY has a bar dated d and ``LOOKBACK`` bars
    through it). No candidates otherwise.
Features (``FEATURE_NAMES``, 18 model columns): the 15 ``SYMBOL_FEATURES``, each turned into a
cross-sectional rank in [0, 1] among d's candidates (``rank01``, ties averaged), then SPY's 3 raw
``SPY_FEATURES``, the same for every candidate of d. Every raw value is a function of the last
``LOOKBACK`` bars ending at d only, computed under the indicators' bit-identity rule, so the
backtest (``prepare_b``: sliding windows) and the nightly job (``design_at``: one window per
symbol) build bit-identical ``Design`` matrices.
Picks: the model's prediction per candidate; keep pred > 0.0 (strict); order by (-pred, symbol);
each gets Strategy A's design bracket (``a._bracket`` with ``a.DESIGN_PARAMS``); an invalid
bracket drops the candidate. Zero picks is a valid night.

The model is opaque here: anything with ``predict(X) -> float64 (rows,)`` (``Predictor``). This
module never imports ``b_model`` (scikit-learn), so ``import seer_engine.strategies`` stays light.
Pure: no database, network, clock or randomness (tests/test_strategy_purity.py).
"""

from __future__ import annotations

from collections.abc import Mapping, Set
from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol, runtime_checkable

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from seer_engine.sim import Pick
from seer_engine.strategies.a import DESIGN_PARAMS, Features, _bracket
from seer_engine.strategies.base import History, as_day
from seer_engine.strategies.indicators import (
    mean_dollar_volume_window,
    mean_window,
    sma_window,
    stdev_return_window,
    wilder_atr_window,
    wilder_rsi_window,
)

LOOKBACK = 200  # == a.LOOKBACK (tested)
SPY_SYMBOL = "SPY"  # == a2.REGIME_SYMBOL == universe.BENCHMARK (tested; universe imports psycopg, so not imported)
MIN_DOLLAR_VOLUME = 20_000_000.0  # == a.DESIGN_PARAMS.min_dollar_volume (tested); candidate needs dv > this
RETURN_HORIZONS: tuple[int, ...] = (1, 5, 20, 60, 120)
SYMBOL_FEATURES: tuple[str, ...] = (
    "ret_1",
    "ret_5",
    "ret_20",
    "ret_60",
    "ret_120",
    "close_sma50",
    "close_sma200",
    "rsi_2",
    "rsi_14",
    "atr_pct",
    "stdev_20",
    "dollar_volume_20",
    "volume_5_20",
    "gap",
    "range_pos",
)  # 15, each ranked among the date's candidates
SPY_FEATURES: tuple[str, ...] = ("spy_ret_5", "spy_ret_20", "spy_close_sma200")  # 3, raw
FEATURE_NAMES: tuple[str, ...] = SYMBOL_FEATURES + SPY_FEATURES  # the 18 model columns, in this order
RAW_COLUMNS: tuple[str, ...] = SYMBOL_FEATURES + ("close", "atr", "dollar_volume")  # window_features' 18 columns

N_SYMBOL = len(SYMBOL_FEATURES)  # 15
N_FEATURES = len(FEATURE_NAMES)  # 18
CLOSE_COL = RAW_COLUMNS.index("close")  # 15
ATR_COL = RAW_COLUMNS.index("atr")  # 16
DV_COL = RAW_COLUMNS.index("dollar_volume")  # 17

SMA_FAST_N = 50
SMA_SLOW_N = 200
RSI_FAST_N = 2
RSI_SLOW_N = 14
ATR_N = 14
STDEV_N = 20
DV_N = 20
VOLUME_FAST_N = 5
VOLUME_SLOW_N = 20
SPY_RETURN_HORIZONS: tuple[int, ...] = (5, 20)

_NO_DATE = date.min  # a._bracket never reads Features.data_date


# ---- raw features on (rows, LOOKBACK) windows ------------------------------------------------


def _window(name: str, x: object) -> np.ndarray:
    if not isinstance(x, np.ndarray) or x.dtype != np.float64 or x.ndim != 2 or x.shape[1] != LOOKBACK:
        raise ValueError(f"{name} must be a 2-D float64 array (rows, {LOOKBACK})")
    return x


def _ret(c: np.ndarray, k: int) -> np.ndarray:
    """``c[-1] / c[-1-k] - 1`` per row: the return over the last ``k`` bars."""
    return c[:, -1] / c[:, -1 - k] - 1.0


def _close_over_sma(c: np.ndarray, n: int) -> np.ndarray:
    return c[:, -1] / sma_window(c, n) - 1.0


def window_features(o: np.ndarray, h: np.ndarray, l: np.ndarray, c: np.ndarray, v: np.ndarray) -> np.ndarray:  # noqa: E741
    """Raw per-symbol values for ``(rows, LOOKBACK)`` windows, oldest bar first: ``(rows, 18)`` float64.

    Columns ``RAW_COLUMNS``: the 15 ``SYMBOL_FEATURES`` raw values, then the last close, ATR(14)
    and the 20-day mean dollar volume. Row i depends only on row i of the inputs, bit for bit
    (elementwise numpy plus the indicators' column loops), so a window computed alone equals the
    same window computed among any others. Division by zero yields a non-finite value, which
    makes the row a non-candidate; numpy's warnings for it are suppressed.
    """
    o, h, l, c, v = (_window(n, x) for n, x in zip("ohlcv", (o, h, l, c, v), strict=True))  # noqa: E741
    rows = c.shape[0]
    out = np.empty((rows, len(RAW_COLUMNS)), dtype=np.float64)
    with np.errstate(divide="ignore", invalid="ignore"):
        last = c[:, -1]
        atr = wilder_atr_window(h, l, c, ATR_N)
        dv = mean_dollar_volume_window(c, v, DV_N)
        for j, k in enumerate(RETURN_HORIZONS):  # columns 0..4: ret_1 .. ret_120
            out[:, j] = _ret(c, k)
        out[:, 5] = _close_over_sma(c, SMA_FAST_N)
        out[:, 6] = _close_over_sma(c, SMA_SLOW_N)
        out[:, 7] = wilder_rsi_window(c, RSI_FAST_N)
        out[:, 8] = wilder_rsi_window(c, RSI_SLOW_N)
        out[:, 9] = atr / last
        out[:, 10] = stdev_return_window(c, STDEV_N)
        out[:, 11] = dv
        out[:, 12] = mean_window(v, VOLUME_FAST_N) / mean_window(v, VOLUME_SLOW_N)
        out[:, 13] = o[:, -1] / c[:, -2] - 1.0
        hi, lo = h[:, -1], l[:, -1]
        wide = hi > lo
        out[:, 14] = np.where(wide, (last - lo) / np.where(wide, hi - lo, 1.0), 0.5)
        out[:, CLOSE_COL] = last
        out[:, ATR_COL] = atr
        out[:, DV_COL] = dv
    return out


def spy_window_features(c: np.ndarray) -> np.ndarray:
    """SPY's raw ``SPY_FEATURES`` for ``(rows, LOOKBACK)`` close windows: ``(rows, 3)`` float64.

    ``spy_ret_5``, ``spy_ret_20`` (as ``ret_k``) and ``spy_close_sma200`` (as ``close_sma200``).
    """
    c = _window("c", c)
    out = np.empty((c.shape[0], len(SPY_FEATURES)), dtype=np.float64)
    with np.errstate(divide="ignore", invalid="ignore"):
        for j, k in enumerate(SPY_RETURN_HORIZONS):
            out[:, j] = _ret(c, k)
        out[:, 2] = _close_over_sma(c, SMA_SLOW_N)
    return out


def rank01(x: np.ndarray) -> np.ndarray:
    """Cross-sectional rank of each entry of 1-D finite ``x``, scaled into [0, 1].

    Average ranks (1-based; equal values share the mean of their positions), then
    ``(rank - 1) / (n - 1)``. n == 1 -> [0.5]; n == 0 -> an empty array. Order-independent:
    a stable argsort, then equal runs share one rank, so the result depends only on the values.
    """
    if not isinstance(x, np.ndarray) or x.dtype != np.float64 or x.ndim != 1:
        raise ValueError("rank01 needs a 1-D float64 array")
    n = x.shape[0]
    if n == 0:
        return np.empty(0, dtype=np.float64)
    if not bool(np.isfinite(x).all()):
        raise ValueError("rank01 needs finite values")
    if n == 1:
        return np.full(1, 0.5, dtype=np.float64)
    order = np.argsort(x, kind="stable")
    xs = x[order]
    starts = np.flatnonzero(np.concatenate(([True], xs[1:] != xs[:-1])))
    ends = np.concatenate((starts[1:], [n]))
    mean_rank = (starts + ends + 1).astype(np.float64) / 2.0  # 1-based mean of positions start+1 .. end
    ranks = np.empty(n, dtype=np.float64)
    ranks[order] = np.repeat(mean_rank, ends - starts)
    return (ranks - 1.0) / float(n - 1)


# ---- the design matrix of one data_date --------------------------------------------------------


def _readonly(arr: np.ndarray) -> np.ndarray:
    arr.setflags(write=False)
    return arr


@dataclass(frozen=True, slots=True, eq=False)
class Design:
    """The candidates of one ``data_date``: what the model sees and what a pick needs.

    ``symbols`` ascending; ``X`` row i is ``symbols[i]``: ``rank01`` of each ``SYMBOL_FEATURES``
    column among these m rows, then SPY's 3 raw values. ``close`` and ``atr`` feed the bracket.
    """

    data_date: date
    symbols: tuple[str, ...]
    X: np.ndarray  # (m, 18) float64, read-only
    close: np.ndarray  # (m,) float64, read-only
    atr: np.ndarray  # (m,) float64, read-only

    def __post_init__(self) -> None:
        as_day(self.data_date)
        if not isinstance(self.symbols, tuple):
            raise TypeError("symbols must be a tuple")
        m = len(self.symbols)
        for name, shape in (("X", (m, N_FEATURES)), ("close", (m,)), ("atr", (m,))):
            arr = getattr(self, name)
            if not isinstance(arr, np.ndarray) or arr.dtype != np.float64 or arr.shape != shape:
                raise ValueError(f"Design.{name} must be a float64 array of shape {shape}")

    def __len__(self) -> int:
        return len(self.symbols)


def _empty_design(data_date: date) -> Design:
    return Design(
        data_date,
        (),
        _readonly(np.empty((0, N_FEATURES), dtype=np.float64)),
        _readonly(np.empty(0, dtype=np.float64)),
        _readonly(np.empty(0, dtype=np.float64)),
    )


def _candidate_mask(raw: np.ndarray) -> np.ndarray:
    """Rows of ``raw`` (window_features output) passing the liquidity floor with 15 finite features."""
    return (raw[:, DV_COL] > MIN_DOLLAR_VOLUME) & np.isfinite(raw[:, :N_SYMBOL]).all(axis=1)


def _design(data_date: date, symbols: list[str], raw: np.ndarray, spy_row: np.ndarray) -> Design:
    """The ``Design`` from the raw rows of ``symbols`` (ascending, members, not SPY) on ``data_date``.

    The ONE builder both paths share: candidates filtered by ``_candidate_mask``, ranks per
    column among the survivors only, SPY's raw values broadcast.
    """
    keep = _candidate_mask(raw)
    if not bool(keep.any()):
        return _empty_design(data_date)
    cand = raw[keep]
    names = tuple(s for s, k in zip(symbols, keep.tolist(), strict=True) if k)
    m = len(names)
    X = np.empty((m, N_FEATURES), dtype=np.float64)
    for j in range(N_SYMBOL):
        X[:, j] = rank01(np.ascontiguousarray(cand[:, j]))
    X[:, N_SYMBOL:] = spy_row
    return Design(
        data_date,
        names,
        _readonly(X),
        _readonly(cand[:, CLOSE_COL].copy()),
        _readonly(cand[:, ATR_COL].copy()),
    )


@dataclass(frozen=True, slots=True, eq=False)
class BPrepared:
    """Strategy B's raw features for every (symbol, date) with ``LOOKBACK`` bars, plus SPY's.

    Columnar, ordered by (date, symbol). ``symbols`` is sorted and excludes ``SPY_SYMBOL``
    (SPY never has a row). Built once by ``prepare_b``; ranks are NOT stored, because they
    depend on the members passed at pick time (``design_on``).
    """

    symbols: tuple[str, ...]  # sorted, SPY excluded; ``sym`` indexes into it
    dates: np.ndarray  # datetime64[D] ascending, one per row
    sym: np.ndarray  # int64
    raw: np.ndarray  # (rows, 18) float64, RAW_COLUMNS, read-only
    spy_dates: np.ndarray  # datetime64[D] ascending: SPY dates with >= LOOKBACK bars through them
    spy: np.ndarray  # (k, 3) float64 SPY_FEATURES, read-only

    def _rows(self, data_date: date) -> tuple[int, int]:
        day = as_day(data_date)
        lo = int(np.searchsorted(self.dates, day, side="left"))
        hi = int(np.searchsorted(self.dates, day, side="right"))
        return lo, hi

    def _spy_row(self, data_date: date) -> np.ndarray | None:
        day = as_day(data_date)
        i = int(np.searchsorted(self.spy_dates, day, side="left"))
        if i == self.spy_dates.shape[0] or self.spy_dates[i] != day:
            return None
        return self.spy[i]

    def design_on(self, members: Set[str], data_date: date) -> Design:
        """The candidates of ``data_date`` among ``members`` (== ``design_at`` on the same bars).

        Empty (0 rows) when SPY's features are undefined on ``data_date`` or nothing qualifies.
        """
        spy_row = self._spy_row(data_date)
        lo, hi = self._rows(data_date)
        if spy_row is None or lo == hi:
            return _empty_design(data_date)
        sym = self.sym[lo:hi].tolist()
        member = np.fromiter((self.symbols[k] in members for k in sym), dtype=np.bool_, count=hi - lo)
        if not bool(member.any()):
            return _empty_design(data_date)
        rows = np.flatnonzero(member) + lo
        names = [self.symbols[int(self.sym[k])] for k in rows]
        return _design(data_date, names, self.raw[rows], spy_row)


def _empty_prepared(symbols: tuple[str, ...], spy_dates: np.ndarray, spy: np.ndarray) -> BPrepared:
    return BPrepared(
        symbols,
        _readonly(np.empty(0, dtype="datetime64[D]")),
        _readonly(np.empty(0, dtype=np.int64)),
        _readonly(np.empty((0, len(RAW_COLUMNS)), dtype=np.float64)),
        spy_dates,
        spy,
    )


def _spy_prepared(history: Mapping[str, History]) -> tuple[np.ndarray, np.ndarray]:
    spy = history.get(SPY_SYMBOL)
    if spy is None or len(spy) < LOOKBACK:
        return (
            _readonly(np.empty(0, dtype="datetime64[D]")),
            _readonly(np.empty((0, len(SPY_FEATURES)), dtype=np.float64)),
        )
    dates = spy.dates[LOOKBACK - 1 :].copy()
    feats = spy_window_features(sliding_window_view(spy.close, LOOKBACK))
    return _readonly(dates), _readonly(feats)


def prepare_b(history: Mapping[str, History]) -> BPrepared:
    """Raw B features over every symbol's whole history, by sliding windows (see ``BPrepared``)."""
    symbols = tuple(sorted(s for s in history if s != SPY_SYMBOL))
    spy_dates, spy = _spy_prepared(history)
    dates_parts: list[np.ndarray] = []
    sym_parts: list[np.ndarray] = []
    raw_parts: list[np.ndarray] = []
    for k, symbol in enumerate(symbols):
        h = history[symbol]
        if len(h) < LOOKBACK:
            continue
        windows = [sliding_window_view(getattr(h, f), LOOKBACK) for f in ("open", "high", "low", "close", "volume")]
        dates_parts.append(h.dates[LOOKBACK - 1 :])
        sym_parts.append(np.full(len(h) - LOOKBACK + 1, k, dtype=np.int64))
        raw_parts.append(window_features(*windows))
    if not dates_parts:
        return _empty_prepared(symbols, spy_dates, spy)
    dates = np.concatenate(dates_parts)
    order = np.argsort(dates, kind="stable")  # symbols were appended in sorted order
    return BPrepared(
        symbols,
        _readonly(dates[order]),
        _readonly(np.concatenate(sym_parts)[order]),
        _readonly(np.concatenate(raw_parts)[order]),
        spy_dates,
        spy,
    )


def _spy_row_at(history: Mapping[str, History], data_date: date) -> np.ndarray | None:
    spy = history.get(SPY_SYMBOL)
    if spy is None:
        return None
    i = spy.index_of(data_date)
    if i is None or i + 1 < LOOKBACK:
        return None
    return spy_window_features(spy.close[i + 1 - LOOKBACK : i + 1].reshape(1, LOOKBACK))[0]


def design_at(history: Mapping[str, History], members: Set[str], data_date: date) -> Design:
    """The candidates of ``data_date`` from one window per symbol: the nightly (single-window) path.

    Reads each symbol's last ``LOOKBACK`` bars ending at ``data_date`` only, SPY's included, so
    ``history`` may hold later bars. Equal, bit for bit, to
    ``prepare_b({s: h.upto(d) for s, h in history.items()}).design_on(members, d)``.
    """
    as_day(data_date)
    spy_row = _spy_row_at(history, data_date)
    if spy_row is None:
        return _empty_design(data_date)
    names: list[str] = []
    ends: list[int] = []
    for symbol in sorted(history):
        if symbol == SPY_SYMBOL or symbol not in members:
            continue
        i = history[symbol].index_of(data_date)
        if i is None or i + 1 < LOOKBACK:
            continue
        names.append(symbol)
        ends.append(i + 1)
    if not names:
        return _empty_design(data_date)

    def stack(field: str) -> np.ndarray:
        return np.stack([getattr(history[s], field)[e - LOOKBACK : e] for s, e in zip(names, ends, strict=True)])

    raw = window_features(stack("open"), stack("high"), stack("low"), stack("close"), stack("volume"))
    return _design(data_date, names, raw, spy_row)


# ---- the model, the params, the picks ----------------------------------------------------------


@runtime_checkable
class Predictor(Protocol):
    """A fitted model: float64 ``(rows,)`` predictions for a float64 ``(rows, 18)`` design matrix.

    Row i's prediction must depend on row i only (``b_model.BModel`` guarantees it).
    """

    def predict(self, X: np.ndarray) -> np.ndarray: ...


@dataclass(frozen=True, slots=True)
class BParams:
    """Strategy B's params: the fitted model. Equality and hash come from the model."""

    model: Predictor

    def __post_init__(self) -> None:
        if not isinstance(self.model, Predictor):
            raise TypeError(f"model must have a predict method, got {type(self.model).__name__}")


def bracket(symbol: str, close: float, atr: float) -> Pick | None:
    """Strategy A's design bracket for ``symbol``: limit −0.5 ATR, TP +1.0 ATR, SL −1.5 ATR, 4-dp Decimal.

    ``a._bracket`` with ``a.DESIGN_PARAMS``; None when it is invalid, or when ``close`` or
    ``atr`` is not finite.
    """
    if not (np.isfinite(close) and np.isfinite(atr)):
        return None
    return _bracket(Features(symbol, _NO_DATE, float(close), np.nan, np.nan, float(atr), np.nan), DESIGN_PARAMS)


def picks_from_design(design: Design, params: BParams) -> list[Pick]:
    """Ranked B picks: candidates with prediction > 0.0, by (-prediction, symbol), each bracketed.

    An empty design returns [] without calling the model. A candidate with an invalid bracket
    is dropped after ranking. Uncapped: the simulator fills free slots in this order.
    """
    if not isinstance(design, Design):
        raise TypeError(f"design must be a Design, got {type(design).__name__}")
    if not isinstance(params, BParams):
        raise TypeError(f"params must be BParams, got {type(params).__name__}")
    m = len(design.symbols)
    if m == 0:
        return []
    pred = params.model.predict(design.X)
    if not isinstance(pred, np.ndarray) or pred.dtype != np.float64 or pred.shape != (m,):
        raise ValueError(f"predict must return a float64 array of shape ({m},)")
    ranked = sorted((-float(pred[k]), design.symbols[k], k) for k in np.flatnonzero(pred > 0.0).tolist())
    picks: list[Pick] = []
    for _, symbol, k in ranked:
        pick = bracket(symbol, float(design.close[k]), float(design.atr[k]))
        if pick is not None:
            picks.append(pick)
    return picks


# ---- the frozen model (P6a phase 7) -------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FrozenModel:
    """The deployed B model: its report, its committed artifact, its training cut-off and its SHA-256."""

    report: str  # "docs/backtests/<end>-strategy-b-walkforward.md"
    artifact: str  # "engine/data/models/<end>-strategy-b.pkl"
    train_end: date  # the last fold's tune_end
    sha256: str  # hex digest of the artifact bytes


# Set by P6a phase 7 ONLY if the gate passes (tests/test_strategy_b_frozen.py ties it to the report).
# None means Strategy B is not frozen.
STRATEGY_B_FROZEN: FrozenModel | None = None


# ---- the Strategy protocol ---------------------------------------------------------------------


def _check_params(params: object) -> BParams:
    if not isinstance(params, BParams):
        raise TypeError(f"params must be BParams, got {type(params).__name__}")
    return params


class StrategyB:
    """Strategy B behind the ``Strategy`` protocol.

    CONTRACT: ``picks_prepared(prepare(H), M, d, p) == picks({s: h.upto(d)}, M, d, p)`` for every p.
    """

    id = "B"
    lookback = LOOKBACK

    def picks(
        self,
        history: Mapping[str, History],
        members: Set[str],
        data_date: date,
        params: Any,
    ) -> list[Pick]:
        params = _check_params(params)
        return picks_from_design(design_at(history, members, data_date), params)

    def prepare(self, history: Mapping[str, History]) -> BPrepared:
        return prepare_b(history)

    def picks_prepared(
        self,
        prepared: Any,
        members: Set[str],
        data_date: date,
        params: Any,
    ) -> list[Pick]:
        if not isinstance(prepared, BPrepared):
            raise TypeError(f"prepared must be BPrepared, got {type(prepared).__name__}")
        params = _check_params(params)
        return picks_from_design(prepared.design_on(members, data_date), params)


STRATEGY_B = StrategyB()

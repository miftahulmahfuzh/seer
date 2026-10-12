"""Tree ranker: a walk-forward gradient-boosted-tree cross-sectional stock ranker (stock-ml-ranker).

Every method in the lab so far ranks on ONE hand-chosen signal. This allocator learns how to
combine signals the lab already computes, point in time, and nothing else: the "tabular ML, not
deep learning" step of docs/plans/HANDOVER_20261012-measure-then-learn.md (Step 1).

WHERE IT LIVES. Under ``lab/``, not ``strategies/``. Three of its features are lab methods' own
signal code, imported and never copied, so the ranker reads exactly the numbers those methods
ranked on: M0007's residual momentum (``build_grid``/``residual_scores``, its N20-RAW model),
M0015's 52-week-high ``nearness`` and M0070's dividend-raise event (``live_event``). Lab methods
import ``strategies``; ``strategies`` never imports a lab method at module scope
(``strategies/evidence.py`` does it lazily, inside functions), and doing so would invert the
layering and put ``lab.methods -> backtest.dev -> strategies`` on an import cycle.
``lab/exposure.py`` and ``lab/gate_probe.py`` are the precedent for a reusable pure allocator
under ``lab/``. tests/test_strategy_purity.py does not glob ``lab/``, so tests/test_tree_rank.py
runs its AST and fresh-interpreter checks on this file.

THE DECISION CALENDAR. A training sample is a (symbol, t) pair on a month-end NYSE session t
(``month_ends``): the data dates of a monthly book. The model can decide on any data date d.

ELIGIBILITY on a date is F4's screen verbatim (``FactorPrepared.rows_on`` with ``SCREEN``): an
index member that day (the market's point-in-time membership for a training date, the members the
runner passes for the decision date), not SPY, a bar dated that day and 253 bars through it,
finite momentum, volatility and dollar volume, volatility > 0, 20-day mean dollar volume > $20M
and close >= $5.

FEATURES, each read from bars dated <= t, dividends gone ex <= t and filings filed <= t. NaN means
"not known", never zero; the trees send a missing value down a learned branch.

    momentum           12-1 total return                             (f_factor row)
    volatility         stdev of the last 60 one-day returns          (f_factor row)
    dollar_volume      20-day mean close x volume                    (f_factor row)
    residual_momentum  M0007-N20-RAW's cumulative market-model residual (m0007.residual_scores)
    high_nearness      close / highest close of the last 252 sessions   (m0015.nearness)
    dividend_raise     1 while M0070's raise-or-first-payment event is live, else 0 (m0070.live_event)
    dividend_yield     cash dividends gone ex in the last 365 days / close   (Market.dividends)
  'price+fund' adds four from one filed-dated snapshot (``panel.as_of``) no older than
  f_fundamental's 400-day staleness window:
    value, quality, profitability, sue                                (f_fundamental._row)

Each feature is rank-normalised across the eligible cross-section of its own date
(``strategies.b.rank01`` over the finite entries, NaN kept), so the model learns orderings, not
levels, and a 1999 cross-section speaks the same units as a 2013 one.

LABEL. The percentile rank (``rank01``) across t's cross-section of the forward return from t's
close to the close of the symbol's last bar on or before ``label_end(t, horizon)``, the 21st NYSE
session after t. A symbol with no bar after t has no label. The label of (s, t) is known on
``label_end(t)``, and not one day before.

WALK-FORWARD. One model per calendar year. The model deciding on d is the one refit at
``anchor_for(d)``, the last NYSE session of the latest year ended on or before d, on every sample
with ``train_start <= t`` and ``label_end(t) <= anchor`` (an expanding window). A sample therefore
enters training only once its label has been read, and nothing dated after the anchor, hence after
d, is ever read. With fewer than ``min_train_months`` labelled month-ends there is no model, no
target and the book is cash. With the defaults the first model is the 1998-12-31 refit
(35 month-ends, January 1996 to November 1998) and the first book is January 1999.

THE BOOK. The ``top_n`` highest predictions (ties by symbol) at ``equal_weight(top_n)``, priced at
d's close; fewer eligible names leave the rest in cash. Held names get no special treatment
(as F4): a name that falls out of the top set is signal-exited by the book engine.

THE TWO PATHS. Membership history, the dividend calendar and the fundamental panel are not in
``Mapping[str, History]``, so the live path is ``prepare_market(market) -> targets_prepared``. The
history-only ``prepare``/``targets`` path sees none of them and, by the market-aware contract
tests/test_lab_methods.py enforces, targets nothing. The identity that matters, held by
tests/test_tree_rank.py, is

    targets_prepared(prepare_market(M), members, d, held, p)
        == targets_with_inputs(TreeInputs.from_market(M), members, d, held, p)

where the right side rebuilds every feature, label and model from data cut at d (slow; the tests
use small markets).

TWO OBJECTS, ONE CLASS. ``lab run`` decides which market fields a method ranks on from the
allocator's ``market_fields`` (``lab.runner.market_fields``), not from its params, and refuses a
store whose fundamentals cover too little of the dev window. So the feature set picks the object:
``TREE_RANK`` ranks on bars and the dividend calendar, ``TREE_RANK_FUND`` also on fundamentals,
and ``params.feature_set`` must name the object's own set.

DETERMINISM. ``HistGradientBoostingRegressor`` with ``early_stopping=False`` and
``random_state=seed``, fitted and evaluated under ``threadpool_limits(1)``: a multi-threaded
histogram sums in a thread-dependent order, a single thread does not. Training rows are stacked by
(t, symbol). A model's identity is Strategy B's ``b_model._tree_digest`` (reused, b_model not
modified). sklearn draws from ``random_state`` only for the early-stopping split (off) and the
bin-threshold subsample above 200,000 rows, so on this lab's data (57,291 rows at the 2014 refit)
``seed`` is inert; it is fixed so the configuration is complete.

PERFORMANCE. ``prepare_market`` builds F4's rolling columns and M0007's return grid once. Each
cross-section and each label vector is computed on first use and cached, and each refit year's
model is fitted once per ``model_key`` and cached, so variants that differ only in ``top_n``
share every fit.

Pure: no database, network, clock, randomness, logging or I/O.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Literal

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from threadpoolctl import threadpool_limits

from seer_engine import dates
from seer_engine.backtest.market import EMPTY_DIVIDENDS, DividendCalendar
from seer_engine.fundamentals import EMPTY_PANEL
from seer_engine.lab.methods.m0007_residual_momentum import (
    N20_NOTREND,
    ResidParams,
    ReturnGrid,
    build_grid,
    resid_lookback,
    residual_scores,
)
from seer_engine.lab.methods.m0015_52week_high import HIGH_N, nearness
from seer_engine.lab.methods.m0070_dividend_raise_drift import RaiseParams, live_event
from seer_engine.sim.book import Target, equal_weight
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.b import rank01
from seer_engine.strategies.b_model import _tree_digest
from seer_engine.strategies.base import History, as_day
from seer_engine.strategies.f_factor import EXCLUDED, FactorPrepared, factor_lookback, prepare_factor
from seer_engine.strategies.f_fundamental import FundamentalParams, Panel, _panel, _row

SCREEN = N20_NOTREND
"""F4's eligibility screen with no trend switch: F4-MOM12-N20's universe, name for name."""

RESID = ResidParams(N20_NOTREND, scaled=False)
"""M0007-N20-RAW's residual model: 378-session beta, 252 residuals, skip 21, unscaled."""

RAISE_EVENT = RaiseParams(N20_NOTREND)
"""M0070-R10-H6's event: a raise of 10% to 100%, or a first payment, gone ex under 182 days ago."""

FUND_STALE_DAYS = FundamentalParams(rank="composite").max_stale_days
"""f_fundamental's own staleness window (400 days), read off its dataclass, not restated."""

YIELD_DAYS = 365  # the trailing window of dividend_yield, in calendar days
NAN = float("nan")
MAX_TOP = 100  # equal_weight(top_n) stays >= 0.01

PRICE_FEATURES: tuple[str, ...] = (
    "momentum",
    "volatility",
    "dollar_volume",
    "residual_momentum",
    "high_nearness",
    "dividend_raise",
    "dividend_yield",
)
FUND_FEATURES: tuple[str, ...] = ("value", "quality", "profitability", "sue")

FEATURE_LOOKBACK = max(factor_lookback(SCREEN), resid_lookback(RESID), HIGH_N)
"""Bars through d the widest feature reads: M0007's residual window, 401."""

FeatureSet = Literal["price", "price+fund"]
FEATURE_SETS: tuple[str, ...] = ("price", "price+fund")


def feature_names(feature_set: str) -> tuple[str, ...]:
    """The model's columns, in order, for ``feature_set``."""
    if feature_set == "price":
        return PRICE_FEATURES
    if feature_set == "price+fund":
        return PRICE_FEATURES + FUND_FEATURES
    raise ValueError(f"feature_set must be one of {FEATURE_SETS}, got {feature_set!r}")


# --------------------------------------------------------------------------- params


def _check_int(name: str, v: object, lo: int, hi: int | None = None) -> int:
    if isinstance(v, bool) or not isinstance(v, int):
        raise TypeError(f"{name} must be an int, got {type(v).__name__}")
    if v < lo or (hi is not None and v > hi):
        bound = f">= {lo}" if hi is None else f"in [{lo}, {hi}]"
        raise ValueError(f"{name} must be {bound}, got {v}")
    return v


def _check_float(name: str, v: object, *, positive: bool, at_most: float | None = None) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise TypeError(f"{name} must be a float, got {type(v).__name__}")
    out = float(v)
    if not math.isfinite(out) or out < 0.0 or (positive and out == 0.0):
        raise ValueError(f"{name} must be a finite float {'> 0' if positive else '>= 0'}, got {out!r}")
    if at_most is not None and out > at_most:
        raise ValueError(f"{name} must be <= {at_most}, got {out!r}")
    return out


def _check_date(name: str, d: object) -> date:
    if isinstance(d, datetime) or not isinstance(d, date):
        raise TypeError(f"{name} must be a date, got {type(d).__name__}")
    return d


def _plain(x: float) -> str:
    """``x`` as a plain decimal string without trailing zeros: 1.0 -> "1", 0.05 -> "0.05"."""
    return format(Decimal(repr(x)).normalize(), "f")


@dataclass(frozen=True, slots=True)
class TreeRankParams:
    """The ranker's pre-registered knobs. Small on purpose: every field enters the config digest.

    ``top_n`` names are held at equal weight. ``feature_set`` must name the allocator object's own
    set (``TREE_RANK``: "price", ``TREE_RANK_FUND``: "price+fund"). The five model fields are
    ``HistGradientBoostingRegressor``'s (``l2`` is ``l2_regularization``) and default to Strategy
    B's pre-registered ``TREE_PARAMS``. ``train_start`` is the first date a training sample may
    carry; ``min_train_months`` is how many labelled month-ends a model needs before it is trusted
    (fewer means cash); ``horizon`` is the label's length in sessions; ``seed`` is the estimator's
    ``random_state``. The refit cadence is fixed (annual, see the module docstring), not a knob.
    """

    top_n: int = 20
    feature_set: FeatureSet = "price"
    learning_rate: float = 0.05
    max_iter: int = 300
    max_leaf_nodes: int = 15
    min_samples_leaf: int = 200
    l2: float = 1.0
    train_start: date = date(1996, 1, 31)
    min_train_months: int = 35
    horizon: int = 21
    seed: int = 0

    def __post_init__(self) -> None:
        _check_int("top_n", self.top_n, 1, MAX_TOP)
        if not isinstance(self.feature_set, str):
            raise TypeError(f"feature_set must be a str, got {type(self.feature_set).__name__}")
        feature_names(self.feature_set)
        object.__setattr__(
            self, "learning_rate", _check_float("learning_rate", self.learning_rate, positive=True, at_most=1.0)
        )
        _check_int("max_iter", self.max_iter, 1, 10_000)
        _check_int("max_leaf_nodes", self.max_leaf_nodes, 2, 4096)
        _check_int("min_samples_leaf", self.min_samples_leaf, 1)
        object.__setattr__(self, "l2", _check_float("l2", self.l2, positive=False))
        _check_date("train_start", self.train_start)
        _check_int("min_train_months", self.min_train_months, 1)
        _check_int("horizon", self.horizon, 1, 252)
        _check_int("seed", self.seed, 0, 2**32 - 1)

    def model_key(self) -> tuple[Any, ...]:
        """Every field a fitted model depends on. Not ``top_n``: book size never changes a fit."""
        return (
            self.feature_set,
            self.learning_rate,
            self.max_iter,
            self.max_leaf_nodes,
            self.min_samples_leaf,
            self.l2,
            self.train_start,
            self.min_train_months,
            self.horizon,
            self.seed,
        )

    def as_dict(self) -> dict[str, str]:
        """Every parameter as a plain string, in a fixed key order (report and pre-registration)."""
        return {
            "top_n": str(self.top_n),
            "feature_set": self.feature_set,
            "learning_rate": _plain(self.learning_rate),
            "max_iter": str(self.max_iter),
            "max_leaf_nodes": str(self.max_leaf_nodes),
            "min_samples_leaf": str(self.min_samples_leaf),
            "l2": _plain(self.l2),
            "train_start": self.train_start.isoformat(),
            "min_train_months": str(self.min_train_months),
            "horizon": str(self.horizon),
            "seed": str(self.seed),
        }


# --------------------------------------------------------------------------- the calendar


def month_ends(start: date, end: date) -> tuple[date, ...]:
    """The last NYSE session of every calendar month, from ``start`` to ``end`` inclusive, ascending."""
    _check_date("start", start)
    _check_date("end", end)
    if end < start:
        return ()
    days = dates.sessions(start, date(end.year + 1, 1, 31))
    out: list[date] = []
    for a, b in zip(days, days[1:]):
        if a > end:
            break
        if (a.year, a.month) != (b.year, b.month):
            out.append(a)
    return tuple(out)


def label_end(t: date, horizon: int) -> date:
    """The ``horizon``-th NYSE session after ``t``: the close a sample dated ``t`` is labelled at."""
    _check_date("t", t)
    _check_int("horizon", horizon, 1)
    days = dates.sessions(dates.next_session(t), t + timedelta(days=2 * horizon + 14))
    if len(days) < horizon:
        raise ValueError(f"the calendar has fewer than {horizon} sessions after {t}")
    return days[horizon - 1]


def year_end(year: int) -> date:
    """The last NYSE session of ``year``: the refit date of the model that trades the next year."""
    return dates.prev_session(date(year + 1, 1, 1))


def anchor_for(d: date) -> date:
    """The refit date whose model decides on ``d``: the latest year-end session on or before ``d``."""
    _check_date("d", d)
    this_year = year_end(d.year)
    return this_year if d >= this_year else year_end(d.year - 1)


# --------------------------------------------------------------------------- inputs


Members = Callable[[date], AbstractSet[str]]


@dataclass(frozen=True, slots=True, eq=False)
class TreeInputs:
    """Everything the ranker reads, each point in time.

    ``history``: every symbol's bars. ``members_on(t)``: the index members on t
    (``Market.membership.members_on``). ``dividends``: the ex-date calendar, read only through
    ``known_on``. ``panel``: the filed-dated fundamental panel, read only through ``as_of``.
    """

    history: Mapping[str, History]
    members_on: Members
    dividends: DividendCalendar = EMPTY_DIVIDENDS
    panel: Panel = EMPTY_PANEL

    def __post_init__(self) -> None:
        if not isinstance(self.history, Mapping):
            raise TypeError(f"history must be a Mapping, got {type(self.history).__name__}")
        if not callable(self.members_on):
            raise TypeError("members_on must be callable: date -> set of symbols")
        if not isinstance(self.dividends, DividendCalendar):
            raise TypeError(f"dividends must be a DividendCalendar, got {type(self.dividends).__name__}")
        object.__setattr__(self, "history", dict(self.history))
        object.__setattr__(self, "panel", _panel(self.panel))

    @staticmethod
    def from_market(market: Any) -> TreeInputs:
        """A ``Market``'s inputs. Duck-typed, like ``f_fundamental.prepare_market``: a test may pass
        any object with ``history``, ``membership.members_on`` and, optionally, ``dividends`` and
        ``fundamentals``."""
        membership = getattr(market, "membership", None)
        members_on = getattr(membership, "members_on", None)
        if not callable(members_on):
            raise TypeError("market.membership.members_on must be callable")
        return TreeInputs(
            dict(market.history),
            members_on,
            getattr(market, "dividends", EMPTY_DIVIDENDS),
            _panel(getattr(market, "fundamentals", None)),
        )

    def upto(self, d: date) -> TreeInputs:
        """These inputs with every history cut to its bars dated on or before ``d``.

        Membership, dividends and the panel are already point in time (every read names a date),
        so they are carried over unchanged.
        """
        _check_date("d", d)
        return TreeInputs({s: h.upto(d) for s, h in self.history.items()}, self.members_on, self.dividends, self.panel)


# --------------------------------------------------------------------------- features


@dataclass(frozen=True, slots=True, eq=False)
class Section:
    """One date's eligible cross-section.

    ``symbols`` sorted; ``close`` their closes; ``raw`` their features (rows x ``feature_names``)
    with NaN for "not known"; ``X`` the same matrix rank-normalised column by column, which is
    what the model reads. All arrays read-only.
    """

    day: date
    symbols: tuple[str, ...]
    close: np.ndarray
    raw: np.ndarray
    X: np.ndarray


def rank_columns(raw: np.ndarray) -> np.ndarray:
    """Each column's ``rank01`` over its finite entries; NaN stays NaN. A new float64 array."""
    out = np.full(raw.shape, NAN, dtype=np.float64)
    for j in range(raw.shape[1]):
        col = raw[:, j]
        ok = np.isfinite(col)
        if ok.any():
            out[ok, j] = rank01(np.ascontiguousarray(col[ok], dtype=np.float64))
    return out


def dividend_features(
    calendar: DividendCalendar, h: History | None, symbol: str, t: date, close: float
) -> tuple[float, float]:
    """(dividend_raise, dividend_yield) on ``t`` from dividends gone ex on or before ``t``.

    ``dividend_raise`` is 1.0 while M0070's event is live (``live_event`` with ``RAISE_EVENT``;
    ``first_bar`` is the symbol's first bar, as M0070 passes it), else 0.0. ``dividend_yield`` is
    the cash gone ex in the last ``YIELD_DAYS`` calendar days over ``close`` (0.0 for a non-payer).
    """
    paid = calendar.known_on(symbol, t)
    first = h.dates[0].item() if h is not None and len(h) > 0 else None
    raised = 1.0 if live_event(paid, first, t, RAISE_EVENT) is not None else 0.0
    since = t - timedelta(days=YIELD_DAYS)
    total = Decimal(0)
    for ex_date, amount in paid:
        if ex_date > since:
            total += amount
    yld = float(total) / close if math.isfinite(close) and close > 0.0 else NAN
    return raised, yld


def fundamental_features(
    panel: Panel, symbol: str, t: date, close: float, dollar_volume: float
) -> tuple[float, float, float, float]:
    """(value, quality, profitability, sue) on ``t`` from one snapshot, f_fundamental's formulas.

    All NaN when the panel has never heard of the symbol, or its newest visible filing is undated,
    dated after ``t`` (a panel bug; checked anyway, as f_fundamental does) or older than
    ``FUND_STALE_DAYS``.
    """
    missing = (NAN, NAN, NAN, NAN)
    snap = panel.as_of(symbol, t)
    if snap is None:
        return missing
    filed = snap.filed
    if filed is None or filed > t or (t - filed).days > FUND_STALE_DAYS:
        return missing
    row = _row(symbol, close, dollar_volume, snap)
    return (row.value, row.quality, row.profitability, row.sue)


def _section(day: date, symbols: tuple[str, ...], close: np.ndarray, raw: np.ndarray) -> Section:
    X = rank_columns(raw)
    for arr in (close, raw, X):
        arr.setflags(write=False)
    return Section(day, symbols, close, raw, X)


def build_section(
    inputs: TreeInputs,
    factor: FactorPrepared,
    grid: ReturnGrid | None,
    universe: AbstractSet[str],
    t: date,
    feature_set: str,
) -> Section:
    """The eligible cross-section of ``universe`` on ``t`` and its features (module docstring).

    ``factor`` and ``grid`` are F4's prepared columns and M0007's return grid built from
    ``inputs.history``; both read only bars dated on or before ``t`` here.
    """
    names = feature_names(feature_set)
    k = len(names)
    rows = [
        r for r in factor.rows_on(universe, t, SCREEN)
        if r.symbol not in EXCLUDED and r.symbol != RESID.market
    ]
    if not rows:
        return _section(t, (), np.empty(0, dtype=np.float64), np.empty((0, k), dtype=np.float64))
    symbols = [r.symbol for r in rows]
    resid = residual_scores(grid, symbols, t, RESID) if grid is not None else {}
    with_fund = feature_set == "price+fund"
    raw = np.full((len(rows), k), NAN, dtype=np.float64)
    for i, r in enumerate(rows):
        near = nearness(inputs.history, r.symbol, t, HIGH_N)
        raised, yld = dividend_features(inputs.dividends, inputs.history.get(r.symbol), r.symbol, t, r.close)
        values = [
            r.momentum,
            r.vol,
            r.dollar_volume,
            resid.get(r.symbol, NAN),
            NAN if near is None else near,
            raised,
            yld,
        ]
        if with_fund:
            values.extend(fundamental_features(inputs.panel, r.symbol, t, r.close, r.dollar_volume))
        raw[i, :] = values
    close = np.array([r.close for r in rows], dtype=np.float64)
    return _section(t, tuple(symbols), close, raw)


def forward_returns(history: Mapping[str, History], section: Section, end: date) -> np.ndarray:
    """Each section symbol's return from ``section.day``'s close to its last close on or before ``end``.

    NaN when the symbol has no bar after ``section.day`` by ``end`` or a close is unusable. Reads
    only bars dated on or before ``end``.
    """
    out = np.full(len(section.symbols), NAN, dtype=np.float64)
    day = as_day(section.day)
    stop = as_day(end)
    for k, symbol in enumerate(section.symbols):
        h = history[symbol]
        i = int(np.searchsorted(h.dates, day, side="left"))
        j = int(np.searchsorted(h.dates, stop, side="right")) - 1
        if i >= len(h) or h.dates[i] != day or j <= i:
            continue
        c0 = float(h.close[i])
        c1 = float(h.close[j])
        if math.isfinite(c0) and math.isfinite(c1) and c0 > 0.0:
            out[k] = c1 / c0 - 1.0
    out.setflags(write=False)
    return out


# --------------------------------------------------------------------------- the model


@dataclass(frozen=True, eq=False)
class TreeModel:
    """One refit. Identity is (anchor, months, rows, n_features, digest); the estimator is the payload."""

    anchor: date
    months: int  # labelled month-ends it learned from
    rows: int
    n_features: int
    digest: str  # b_model._tree_digest of the fitted estimator
    estimator: HistGradientBoostingRegressor

    def _key(self) -> tuple[Any, ...]:
        return (self.anchor, self.months, self.rows, self.n_features, self.digest)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TreeModel):
            return NotImplemented
        return self._key() == other._key()

    def __hash__(self) -> int:
        return hash(self._key())

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predicted label per row, float64, under a one-thread limit."""
        with threadpool_limits(limits=1):
            return np.asarray(self.estimator.predict(X), dtype=np.float64)


def fit_model(X: np.ndarray, y: np.ndarray, params: TreeRankParams) -> HistGradientBoostingRegressor:
    """``params``' regressor fitted on (X, y) under a one-thread limit (module docstring, DETERMINISM).

    A column with no finite value at all (the four fundamentals before the EDGAR panel starts in
    2009) is fitted as a constant 0.0. sklearn 1.9 bins a one-valued column into a single bin and
    never splits on it, which is what an all-missing column means, but it raises on a column with
    zero distinct values. Any column with one finite value is passed through untouched, so every
    fit that succeeded before this guard is bit-identical.
    """
    blank = ~np.isfinite(X).any(axis=0) if X.size else np.zeros(X.shape[1], dtype=bool)
    if blank.any():
        X = X.copy()
        X[:, blank] = 0.0
    estimator = HistGradientBoostingRegressor(
        loss="squared_error",
        learning_rate=params.learning_rate,
        max_iter=params.max_iter,
        max_leaf_nodes=params.max_leaf_nodes,
        min_samples_leaf=params.min_samples_leaf,
        l2_regularization=params.l2,
        early_stopping=False,
        random_state=params.seed,
    )
    with threadpool_limits(limits=1):
        estimator.fit(X, y)
    return estimator


# --------------------------------------------------------------------------- the prepared value


@dataclass(eq=False)
class TreeRankPrepared:
    """The ranker's state for one market; ``inputs`` is None on the history-only path (no targets).

    Caches: cross-sections by (date, universe), label dates by (date, horizon), forward returns by
    (date, label date), models by (anchor, ``params.model_key()``).
    """

    feature_set: str
    inputs: TreeInputs | None = field(default=None, repr=False)
    factor: FactorPrepared | None = field(default=None, repr=False)
    grid: ReturnGrid | None = field(default=None, repr=False)
    _sections: dict[tuple[date, frozenset[str]], Section] = field(default_factory=dict, repr=False)
    _ends: dict[tuple[date, int], date] = field(default_factory=dict, repr=False)
    _returns: dict[tuple[date, date], np.ndarray] = field(default_factory=dict, repr=False)
    _models: dict[tuple[Any, ...], TreeModel | None] = field(default_factory=dict, repr=False)

    @staticmethod
    def build(inputs: TreeInputs, feature_set: str) -> TreeRankPrepared:
        """F4's rolling columns and M0007's return grid over ``inputs.history``; everything else lazily."""
        if not isinstance(inputs, TreeInputs):
            raise TypeError(f"inputs must be TreeInputs, got {type(inputs).__name__}")
        feature_names(feature_set)
        return TreeRankPrepared(
            feature_set,
            inputs,
            prepare_factor(inputs.history),
            build_grid(inputs.history, RESID.market),
        )

    def _live(self) -> tuple[TreeInputs, FactorPrepared]:
        if self.inputs is None or self.factor is None:
            raise ValueError("a history-only prepared value has no market inputs")
        return self.inputs, self.factor

    def section(self, t: date, universe: AbstractSet[str] | None = None) -> Section:
        """The cross-section on ``t``: of ``universe``, or of the index members on ``t`` when None."""
        inputs, factor = self._live()
        members = frozenset(inputs.members_on(t) if universe is None else universe)
        key = (t, members)
        hit = self._sections.get(key)
        if hit is None:
            hit = build_section(inputs, factor, self.grid, members, t, self.feature_set)
            self._sections[key] = hit
        return hit

    def end(self, t: date, horizon: int) -> date:
        """``label_end(t, horizon)``, cached."""
        key = (t, horizon)
        hit = self._ends.get(key)
        if hit is None:
            hit = label_end(t, horizon)
            self._ends[key] = hit
        return hit

    def forward_returns(self, t: date, horizon: int) -> np.ndarray:
        """Forward returns of the members' cross-section on ``t`` over ``horizon`` sessions."""
        inputs, _ = self._live()
        end = self.end(t, horizon)
        key = (t, end)
        hit = self._returns.get(key)
        if hit is None:
            hit = forward_returns(inputs.history, self.section(t), end)
            self._returns[key] = hit
        return hit

    def labels(self, t: date, horizon: int) -> np.ndarray:
        """The labels of the members' cross-section on ``t``: ``rank01`` of the finite forward returns."""
        return rank_columns(self.forward_returns(t, horizon).reshape(-1, 1))[:, 0]

    def training_dates(self, params: TreeRankParams, anchor: date) -> tuple[date, ...]:
        """Month-ends a refit on ``anchor`` learns from: on or after ``train_start``, label read by ``anchor``."""
        return tuple(t for t in month_ends(params.train_start, anchor) if self.end(t, params.horizon) <= anchor)

    def training_set(self, params: TreeRankParams, anchor: date) -> tuple[np.ndarray, np.ndarray, int]:
        """(X, y, labelled month-ends) for a refit on ``anchor``, rows stacked by (t, symbol)."""
        k = len(feature_names(self.feature_set))
        xs: list[np.ndarray] = []
        ys: list[np.ndarray] = []
        months = 0
        for t in self.training_dates(params, anchor):
            y = self.labels(t, params.horizon)
            ok = np.isfinite(y)
            if not ok.any():
                continue
            months += 1
            xs.append(self.section(t).X[ok])
            ys.append(y[ok])
        if not xs:
            return np.empty((0, k), dtype=np.float64), np.empty(0, dtype=np.float64), 0
        return np.concatenate(xs, axis=0), np.concatenate(ys), months

    def model(self, params: TreeRankParams, anchor: date) -> TreeModel | None:
        """The model refit on ``anchor``, or None when it has fewer than ``min_train_months`` to learn from."""
        if params.feature_set != self.feature_set:
            raise ValueError(f"params.feature_set {params.feature_set!r} != prepared {self.feature_set!r}")
        key = (anchor, params.model_key())
        if key in self._models:
            return self._models[key]
        X, y, months = self.training_set(params, anchor)
        model: TreeModel | None = None
        if months >= params.min_train_months and X.shape[0] >= 2:
            estimator = fit_model(X, y, params)
            model = TreeModel(anchor, months, int(X.shape[0]), int(X.shape[1]), _tree_digest(estimator), estimator)
        self._models[key] = model
        return model

    def model_on(self, data_date: date, params: TreeRankParams) -> TreeModel | None:
        """The model that decides on ``data_date``: the one refit at ``anchor_for(data_date)``."""
        return self.model(params, anchor_for(data_date))

    def targets_on(self, members: AbstractSet[str], data_date: date, params: TreeRankParams) -> tuple[Target, ...]:
        """The ``top_n`` highest predictions among ``members``' cross-section on ``data_date``."""
        if params.feature_set != self.feature_set:
            raise ValueError(f"params.feature_set {params.feature_set!r} != prepared {self.feature_set!r}")
        model = self.model_on(data_date, params)
        if model is None:
            return ()
        sec = self.section(data_date, members)
        if not sec.symbols:
            return ()
        pred = model.predict(sec.X)
        order = sorted(range(len(sec.symbols)), key=lambda k: (-float(pred[k]), sec.symbols[k]))
        weight = equal_weight(params.top_n)
        out: list[Target] = []
        for k in order:
            if len(out) == params.top_n:
                break
            if not math.isfinite(float(pred[k])):
                continue
            target = target_from_close(sec.symbols[k], float(sec.close[k]), weight)
            if target is not None:
                out.append(target)
        return tuple(out)


# --------------------------------------------------------------------------- the allocator


def _check_call(members: object, data_date: object, held: object) -> None:
    if not isinstance(members, AbstractSet):
        raise TypeError(f"members must be a set, got {type(members).__name__}")
    _check_date("data_date", data_date)
    if not isinstance(held, frozenset):
        raise TypeError(f"held must be a frozenset, got {type(held).__name__}")


class TreeRankAllocator:
    """The tree ranker behind the ``Allocator`` and ``MarketAware`` protocols (module docstring).

    One object per feature set: ``id`` and ``market_fields`` are what ``lab run`` reads, and they
    depend on whether fundamentals are ranked on.
    """

    def __init__(self, feature_set: str) -> None:
        feature_names(feature_set)
        self.feature_set = feature_set
        self.id = "TREE" if feature_set == "price" else "TREEF"
        self.market_fields: tuple[str, ...] = (
            ("dividends",) if feature_set == "price" else ("dividends", "fundamentals")
        )

    def _check(self, params: object) -> TreeRankParams:
        if not isinstance(params, TreeRankParams):
            raise TypeError(f"params must be TreeRankParams, got {type(params).__name__}")
        if params.feature_set != self.feature_set:
            raise ValueError(
                f"{self.id} ranks feature_set {self.feature_set!r}; params name {params.feature_set!r}"
            )
        return params

    def lookback(self, params: Any) -> int:
        self._check(params)
        return FEATURE_LOOKBACK

    def symbols(self, params: Any) -> tuple[str, ...]:
        self._check(params)
        return (RESID.market,)

    def holds(self, params: Any) -> tuple[str, ...]:
        self._check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        self._check(params)
        return True

    def targets(
        self,
        history: Mapping[str, History],
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        """The history-only path: no membership history, no calendar, so no model and no target."""
        self._check(params)
        _check_call(members, data_date, held)
        return ()

    def prepare(self, history: Mapping[str, History]) -> TreeRankPrepared:
        return TreeRankPrepared(self.feature_set)

    def prepare_market(self, market: Any) -> TreeRankPrepared:
        return TreeRankPrepared.build(TreeInputs.from_market(market), self.feature_set)

    def targets_prepared(
        self,
        prepared: Any,
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        p = self._check(params)
        _check_call(members, data_date, held)
        if not isinstance(prepared, TreeRankPrepared):
            raise TypeError(f"prepared must be TreeRankPrepared, got {type(prepared).__name__}")
        if prepared.feature_set != self.feature_set:
            raise ValueError(f"{self.id} was handed a prepared value for feature_set {prepared.feature_set!r}")
        if prepared.inputs is None:
            return ()
        return prepared.targets_on(members, data_date, p)


TREE_RANK = TreeRankAllocator("price")
TREE_RANK_FUND = TreeRankAllocator("price+fund")


def targets_with_inputs(
    inputs: TreeInputs,
    members: AbstractSet[str],
    data_date: date,
    held: frozenset[str],
    params: TreeRankParams,
) -> tuple[Target, ...]:
    """The from-scratch path: every feature, label and model rebuilt from ``inputs`` cut at ``data_date``.

    Slow by design. The prepared path must equal it bit for bit (tests/test_tree_rank.py).
    """
    if not isinstance(inputs, TreeInputs):
        raise TypeError(f"inputs must be TreeInputs, got {type(inputs).__name__}")
    if not isinstance(params, TreeRankParams):
        raise TypeError(f"params must be TreeRankParams, got {type(params).__name__}")
    _check_call(members, data_date, held)
    prepared = TreeRankPrepared.build(inputs.upto(data_date), params.feature_set)
    return prepared.targets_on(members, data_date, params)

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

THE FALL LABEL, the second thing this module can be asked to predict, and the one place this
module does NOT rank-normalise. The constraint that binds this lab is not the pick but the fall: of
394 recorded dev trials 65% beat SPY total return and only 23% keep the worst drawdown at or under
20% (handover 2026-10-13, "measure the constraint"). So beside the forward return rank there is a
forward *downside* LEVEL. ``forward_drawdown`` is the worst peak-to-trough fall of a symbol's
closes from ``section.day`` to its last close on or before the label end, as a fraction;
``forward_downside_vol`` is the root mean square of its down days over the same window. Both read
only bars dated on or before that end, and both are NaN where the window cannot be measured and a
measured 0.0 where it was calm -- NaN means "not known", never "no fall".

**``fall_labels`` returns that measure RAW. ``rank01`` is not applied to it, ever.** The return
label is a per-date rank because the ranker's question is "which of these names"; the fall model's
question is "how much of this book", and a per-date rank cannot answer it. Every FEATURE column is
already rank-normalised per date (``rank_columns`` in ``build_section``); a per-date rank LABEL on
top of that would make the prediction distribution near-stationary across dates by construction, so
a cut would select a count that moved only with cross-sectional composition noise, and in October
2008 -- when every name is about to fall -- the per-date ranks would still be uniform and the label
could not encode "all of them" even in principle. That is a selection test wearing a sizing head.
The level can say "every name on this date is about to fall thirty per cent"; the rank cannot.

The horizon is a quarter (``QUARTER``, 63 sessions) rather than the ranker's month, because a fall
is a path and a month of a path is mostly noise. A longer horizon costs label-end calendar, not
lookback: a sample enters training only once ``label_end(t, horizon) <= anchor``, so the first fall
refit with 35 labelled month-ends is 1999-12-31 against the ranker's 1998-12-31, the first book year
is 2000 against 1999, and the last labelled dev month-end is 2015-06-30 against 2015-08-31.
``FEATURE_LOOKBACK`` does not move.

THE MARKET-LEVEL COLUMNS, because a level label needs level inputs. If every feature were a per-date
rank the model could not tell 2008 from 2005 and the best it could do with a level label is predict
the unconditional mean. ``build_fall_section`` therefore COMPOSES ``build_section`` -- which is not
edited, nor is ``Section``, ``rank_columns`` or ``PRICE_FEATURES`` -- and appends three columns that
are deliberately NOT normalised: SPY's distance below its trailing ``MARKET_HIGH_N`` (252) session
high, SPY's realised volatility over the last ``MARKET_VOL_N`` (60) sessions, and the cross-sectional
dispersion of the date's own 12-1 momentum, read off the raw matrix before ranking. All three are
per-date scalars broadcast down the rows: within a date they carry no cross-sectional information
and so cannot change which names the model prefers, only how far the whole date's predictions shift
-- which is exactly the level the head reads. Each reads only bars dated on or before the decision
date. ``FALL_FEATURE_LOOKBACK`` is ``max(FEATURE_LOOKBACK, MARKET_HIGH_N, MARKET_VOL_N + 1)`` = 401,
unchanged, and under the lab smoke fixture's 473-bar cap.

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

THE SIZING HEAD reads a MARKET-LEVEL quantity, not a per-name one. The names are still read in one
pass -- the calmest predicted falls first, ties by symbol -- but how many of the ``slots`` are
filled is decided by where the WHOLE CROSS-SECTION sits, and the slots that are not filled are cash.
At each refit the model predicts on its own training rows, takes the mean predicted fall per
training date, and keeps those date-level means sorted (``FallModel.levels``); ``FallModel.cut`` is
their median, the level at which the book sits at half exposure. At a decision date the head takes
the date's cross-sectional MEAN predicted fall and asks where it falls in that training
distribution: ``danger`` is the share of training dates that looked no more dangerous, and the book
holds ``slots - floor(danger * slots)`` whole slots. Calmer than every training date and the book is
full; more dangerous than every one of them and the book is entirely cash; at the median, half.
It is monotone, it reaches both ends, and NOT ONE NUMBER IN IT WAS CHOSEN -- the ladder is the
empirical distribution of the model's own in-sample predictions, so nothing here was read off the
dev window, which is what pre-registration requires. ``size=False`` is the control: the same
ordering, the ladder ignored, the book always full, which separates what the sizing adds from what
ranking by predicted calm adds.

WHY WHOLE SLOTS. The weight of a held name is ``equal_weight(slots)`` and never changes with how
many are held: the book is never renormalised onto the names that survived. The measuring tape
(``sim.rules.MONTHLY_HOLD_FRAC_GOTRADE_TBAND``) resizes a holding only once it is off by
``TARGET_RESIZE_BAND``, 20% of its OWN target value, so at 20 slots a weight nudge smaller than 1%
of equity is never traded at all and a head that expressed exposure by nudging weights would be
swallowed whole by the band. An entry or an exit is a gap of a full slot, 5% of equity at 20 slots:
five times the band, every time, at every book size. So exposure moves in whole slots, which is the
only step this tape can hear.

ONE OBJECT, DELIBERATELY. ``FALL_SIZE`` is the fall model's only exported allocator, beside the
ranker's pair ``TREE_RANK`` and ``TREE_RANK_FUND``. There is no ``FALL_SIZE_FUND``: the EDGAR panel
starts in 2009, so a method pre-registered on fundamentals would be learning from four empty columns
for thirteen of the dev window's twenty years and would burn its method id measuring the panel
rather than the hypothesis. An exported allocator that no method may ever use would only claim an
allocator id forever, so the id ``FALLF`` is left free. ``FallSizeAllocator`` still accepts
``"price+fund"`` -- the branch is reachable and tested by constructing one locally -- but the fall
model is built to run on price and dividend features alone, and that is what it is pre-registered on.

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
    _falls: dict[tuple[date, date, str], np.ndarray] = field(default_factory=dict, repr=False)
    _fall_sections: dict[tuple[date, Any], Section] = field(default_factory=dict, repr=False)
    _fall_models: dict[tuple[Any, ...], FallModel | None] = field(default_factory=dict, repr=False)

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

    def forward_fall(self, t: date, horizon: int, measure: str) -> np.ndarray:
        """``measure``'s forward fall of the members' cross-section on ``t`` over ``horizon`` sessions.

        Cached in ``_falls``, keyed by (t, label end, measure). That is a different dict from
        ``_returns``, so a fall vector can never be served where a forward return was asked for,
        or the other way round, whatever the horizon -- the two caches cannot reach each other.
        """
        inputs, _ = self._live()
        end = self.end(t, horizon)
        key = (t, end, measure)
        hit = self._falls.get(key)
        if hit is None:
            hit = forward_fall(inputs.history, self.section(t), end, measure)
            self._falls[key] = hit
        return hit

    def fall_labels(self, t: date, horizon: int, measure: str) -> np.ndarray:
        """The fall labels on ``t``: the RAW forward fall. A LEVEL, never a rank (D13).

        ``rank01``/``rank_columns`` is deliberately NOT applied here and must never be added. Every
        FEATURE column is already rank-normalised per date; a per-date rank LABEL on top of that
        makes the prediction distribution near-stationary across dates by construction, so the head
        could only ever select a count that moved with cross-sectional composition noise, and in
        October 2008 the per-date ranks are still uniform -- the label could not encode "all of
        them" even in principle. The level can; that is the whole point of this path.

        NaN is passed through unchanged and still means "not known": ``fall_training_set`` drops
        those rows and ``forward_fall`` never returns 0.0 for an unmeasurable window.
        """
        return self.forward_fall(t, horizon, measure)

    def fall_section(self, t: date, members: AbstractSet[str] | None = None) -> Section:
        """The fall model's section on ``t``: the ranker's, plus the three market-level columns.

        ``self.section(...)`` is the ranker's own cached builder and is called, never copied, so
        the seven rank-normalised columns are byte-identical between the two heads and the feature
        work is paid for once. ``build_fall_section`` appends the un-normalised level columns (D13).
        Cached in ``_fall_sections``, its own dict, so a 10-column fall section can never be served
        where a 7-column ranker section was asked for.
        """
        inputs, _ = self._live()
        key = (t, None if members is None else frozenset(members))
        hit = self._fall_sections.get(key)
        if hit is None:
            base = self.section(t) if members is None else self.section(t, members)
            hit = build_fall_section(base, inputs.history, MOMENTUM_COL)
            self._fall_sections[key] = hit
        return hit

    def fall_training_set(
        self, params: FallSizeParams, anchor: date
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, int]:
        """(X, y, groups, labelled month-ends) for a fall refit on ``anchor``.

        Rows are stacked by (t, symbol) exactly as the ranker's ``training_set`` stacks them, and
        ``groups`` carries each row's training-date index, 0 .. months-1. The head's ladder is a
        distribution over DATES, not over rows, so the fit needs to know which rows belong to which
        date; without ``groups`` a date with 500 names would outvote one with 20 (D2c).

        ``training_dates`` is the ranker's own, called and never copied: it reads
        ``params.train_start`` and ``params.horizon``, which this params class carries under the
        same names, so both heads share one calendar by construction rather than by a restated rule.
        """
        k = len(fall_feature_names(self.feature_set))
        xs: list[np.ndarray] = []
        ys: list[np.ndarray] = []
        gs: list[np.ndarray] = []
        months = 0
        for t in self.training_dates(params, anchor):
            y = self.fall_labels(t, params.horizon, params.measure)
            ok = np.isfinite(y)
            if not ok.any():
                continue
            xs.append(self.fall_section(t).X[ok])
            ys.append(y[ok])
            gs.append(np.full(int(ok.sum()), months, dtype=np.int64))
            months += 1
        if not xs:
            return (
                np.empty((0, k), dtype=np.float64),
                np.empty(0, dtype=np.float64),
                np.empty(0, dtype=np.int64),
                0,
            )
        return np.concatenate(xs, axis=0), np.concatenate(ys), np.concatenate(gs), months

    def fall_model(self, params: FallSizeParams, anchor: date) -> FallModel | None:
        """The fall model refit on ``anchor``, or None with fewer than ``min_train_months`` to learn from."""
        if params.feature_set != self.feature_set:
            raise ValueError(f"params.feature_set {params.feature_set!r} != prepared {self.feature_set!r}")
        key = (anchor, params.model_key())
        if key in self._fall_models:
            return self._fall_models[key]
        X, y, groups, months = self.fall_training_set(params, anchor)
        model: FallModel | None = None
        if months >= params.min_train_months and X.shape[0] >= 2:
            model = fit_fall_model(X, y, groups, months, anchor, params)
        self._fall_models[key] = model
        return model

    def fall_model_on(self, data_date: date, params: FallSizeParams) -> FallModel | None:
        """The fall model that decides on ``data_date``: the one refit at ``anchor_for(data_date)``."""
        return self.fall_model(params, anchor_for(data_date))

    def fall_targets_on(
        self, members: AbstractSet[str], data_date: date, params: FallSizeParams
    ) -> tuple[Target, ...]:
        """The book the predicted fall sizes on ``data_date``: the calmest names, cash for the rest.

        TWO DECISIONS, DELIBERATELY SEPARATE (D13, D2c):

        - HOW MANY slots are filled is a MARKET-LEVEL question. The date's cross-sectional MEAN
          predicted fall is located in the model's own training distribution of date-level means
          (``model.levels``, sorted at fit time); ``danger`` is the share of training dates that
          looked no more dangerous, and the book holds ``slots - floor(danger * slots)`` whole
          slots. Calmer than every training date -> a full book; more dangerous than all of them ->
          entirely cash; at the median -> half. Monotone, both ends reachable, and not one number
          in it was chosen: the ladder IS the empirical distribution of the model's own in-sample
          predictions, so nothing was read off the dev window.
        - WHICH names fill them is the ordinary cross-sectional question: predicted fall ascending,
          ties by symbol.

        Every held name is at ``equal_weight(params.slots)`` whatever the count -- the book is NEVER
        renormalised onto the survivors, and the unfilled slots are cash. With ``size`` off the
        ladder is ignored entirely and ``k`` is ``slots``: the always-full control.

        A non-finite prediction is dropped before both the mean and the sort, so no NaN reaches
        either; when nothing is finite the date is all cash.
        """
        if params.feature_set != self.feature_set:
            raise ValueError(f"params.feature_set {params.feature_set!r} != prepared {self.feature_set!r}")
        model = self.fall_model_on(data_date, params)
        if model is None:
            return ()
        sec = self.fall_section(data_date, members)
        if not sec.symbols:
            return ()
        pred = model.predict(sec.X)
        live = [k for k in range(len(sec.symbols)) if math.isfinite(float(pred[k]))]
        if not live:
            return ()
        k_slots = params.slots if not params.size else model.exposure(
            float(np.mean([float(pred[k]) for k in live])), params.slots
        )
        if k_slots <= 0:
            return ()
        order = sorted(live, key=lambda k: (float(pred[k]), sec.symbols[k]))
        weight = equal_weight(params.slots)
        out: list[Target] = []
        for k in order:
            if len(out) == k_slots:
                break
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


# --------------------------------------------------------------- the fall label (R2, 2026-10-13)


QUARTER = 63
"""NYSE sessions in a calendar quarter: the fall label's horizon, the handover's "next quarter"."""

FallMeasure = Literal["drawdown", "downside_vol"]
FALL_MEASURES: tuple[str, ...] = ("drawdown", "downside_vol")


def _window(h: History, day: np.datetime64, stop: np.datetime64) -> np.ndarray | None:
    """``h``'s closes from its bar dated ``day`` through its last bar dated on or before ``stop``.

    None -- "not measurable" -- when ``h`` has no bar dated exactly ``day``, no bar after it by
    ``stop``, or any close in the window is not a finite positive price. The two ``searchsorted``
    calls are ``forward_returns``' discipline verbatim: ``j`` is found with ``side="right"`` on
    ``stop``, so a bar dated after the label end can never enter the window, however far the
    history runs past it.
    """
    i = int(np.searchsorted(h.dates, day, side="left"))
    j = int(np.searchsorted(h.dates, stop, side="right")) - 1
    if i >= len(h) or h.dates[i] != day or j <= i:
        return None
    path = np.asarray(h.close[i : j + 1], dtype=np.float64)
    if not bool(np.isfinite(path).all()) or not bool((path > 0.0).all()):
        return None
    return path


def forward_drawdown(history: Mapping[str, History], section: Section, end: date) -> np.ndarray:
    """Each section symbol's worst peak-to-trough fall from ``section.day`` to ``end``, as a fraction.

    0.0 for a path that never closes below a previous close in the window -- a measured zero, which
    is why "unmeasurable" is NaN and never 0.0. NaN when the window is unmeasurable (``_window``).
    Reads only bars dated on or before ``end``.
    """
    out = np.full(len(section.symbols), NAN, dtype=np.float64)
    day = as_day(section.day)
    stop = as_day(end)
    for k, symbol in enumerate(section.symbols):
        path = _window(history[symbol], day, stop)
        if path is None:
            continue
        fall = float(np.max(1.0 - path / np.maximum.accumulate(path)))
        out[k] = fall if fall > 0.0 else 0.0
    out.setflags(write=False)
    return out


def forward_downside_vol(history: Mapping[str, History], section: Section, end: date) -> np.ndarray:
    """Each section symbol's realised downside volatility from ``section.day`` to ``end``.

    The root mean square of ``min(r, 0)`` over the window's one-day simple returns: up days count
    as zero, so a path that only rises scores 0.0. NaN when the window is unmeasurable
    (``_window``). Reads only bars dated on or before ``end``.
    """
    out = np.full(len(section.symbols), NAN, dtype=np.float64)
    day = as_day(section.day)
    stop = as_day(end)
    for k, symbol in enumerate(section.symbols):
        path = _window(history[symbol], day, stop)
        if path is None:
            continue
        down = np.minimum(path[1:] / path[:-1] - 1.0, 0.0)
        out[k] = float(np.sqrt(float(np.mean(down * down))))
    out.setflags(write=False)
    return out


def forward_fall(
    history: Mapping[str, History], section: Section, end: date, measure: str
) -> np.ndarray:
    """``measure``'s forward fall of ``section`` over (``section.day``, ``end``]."""
    if measure == "drawdown":
        return forward_drawdown(history, section, end)
    if measure == "downside_vol":
        return forward_downside_vol(history, section, end)
    raise ValueError(f"measure must be one of {FALL_MEASURES}, got {measure!r}")


# ------------------------------------------------- the market-level columns (D13, un-normalised)


MARKET_HIGH_N = 252
"""Sessions in the trailing high SPY's drawdown column is measured against (one year)."""

MARKET_VOL_N = 60
"""One-day SPY returns in the realised-volatility column; it needs MARKET_VOL_N + 1 bars."""

MARKET_FEATURES: tuple[str, ...] = (
    "spy_drawdown_from_high",
    "spy_vol_60",
    "momentum_dispersion",
)

MOMENTUM_COL = PRICE_FEATURES.index("momentum")
"""Where the 12-1 momentum column sits in ``build_section``'s raw matrix.

Looked up from the frozen tuple rather than written as a literal ``0``: if ``PRICE_FEATURES`` is
ever reordered, this raises at import instead of silently computing the dispersion of the wrong
column.
"""

FALL_FEATURE_LOOKBACK = max(FEATURE_LOOKBACK, MARKET_HIGH_N, MARKET_VOL_N + 1)
"""How far back the FALL model reads: max(401, 252, 61) = 401, so the ranker's own window.

``FEATURE_LOOKBACK`` is frozen (M0130's recorded digests do not name it, but ``TreeRankAllocator``
does and this module does not edit that path). This constant is the fall allocator's own, written
as a ``max`` so that the claim "the market columns add no reach" is arithmetic a reader can check
rather than a sentence they must trust. The lab's smoke fixture is 473 bars, so 401 clears it.
"""


def fall_feature_names(feature_set: str) -> tuple[str, ...]:
    """The fall model's columns: the ranker's own, then the three un-normalised market columns.

    ``feature_names`` is the ranker's and is not edited. The market columns come last so the
    ranker's column order inside the matrix is the one ``build_section`` produced, byte for byte.
    """
    return tuple(feature_names(feature_set)) + MARKET_FEATURES


def market_columns(
    history: Mapping[str, History], day: date, momentum: np.ndarray
) -> tuple[float, float, float]:
    """The date's three market-level scalars. Reads only bars dated on or before ``day``.

    Per-date SCALARS, not per-name values: broadcast down every row of the section, they carry no
    cross-sectional information and so cannot change which names the model prefers. They can only
    shift the whole date's predictions, which is exactly the level a sizing head has to read (D13).

    - ``spy_drawdown_from_high``: ``1 - close(day) / max(close over the trailing MARKET_HIGH_N
      sessions ending at day)``. 0.0 at a new high, larger the further the market has already
      fallen. NaN when SPY has no bar dated ``day`` or fewer than two bars behind it.
    - ``spy_vol_60``: the sample standard deviation of SPY's last ``MARKET_VOL_N`` one-day simple
      returns ending at ``day``. NaN with fewer than ``MARKET_VOL_N + 1`` bars.
    - ``momentum_dispersion``: the standard deviation of the date's own 12-1 momentum column, taken
      from ``build_section``'s RAW matrix before ``rank_columns`` touched it, over the finite
      entries. NaN when fewer than two are finite.

    The slice is ``searchsorted(dates, day, side="right")`` -- ``forward_returns``' and
    ``_window``'s own discipline -- so a bar dated after ``day`` can never enter, however far the
    history runs past it. NaN is left as NaN: ``fit_model`` bins a missing value into its own bin,
    which is the honest encoding of "this column is not known on this date".
    """
    h = history.get(RESID.market)
    dd = NAN
    vol = NAN
    if h is not None:
        j = int(np.searchsorted(h.dates, as_day(day), side="right"))
        if j > 0 and h.dates[j - 1] == as_day(day):
            hi = np.asarray(h.close[max(0, j - MARKET_HIGH_N) : j], dtype=np.float64)
            if len(hi) >= 2 and bool(np.isfinite(hi).all()) and bool((hi > 0.0).all()):
                peak = float(np.max(hi))
                if peak > 0.0:
                    dd = float(1.0 - float(hi[-1]) / peak)
            win = np.asarray(h.close[max(0, j - MARKET_VOL_N - 1) : j], dtype=np.float64)
            if len(win) >= MARKET_VOL_N + 1 and bool(np.isfinite(win).all()) and bool((win > 0.0).all()):
                vol = float(np.std(win[1:] / win[:-1] - 1.0, ddof=1))
    ok = np.isfinite(momentum)
    disp = float(np.std(momentum[ok], ddof=1)) if int(ok.sum()) >= 2 else NAN
    return dd, vol, disp


def build_fall_section(
    base: Section, history: Mapping[str, History], momentum_index: int
) -> Section:
    """``base`` with the three market-level columns appended, un-normalised.

    COMPOSES ``build_section``'s output; it does not reimplement or edit it. ``base.X`` already
    carries the ranker's seven rank-normalised columns and is copied through untouched, so the
    fall model sees exactly what the ranker sees plus three columns that were never ranked -- which
    is the whole of D13's second requirement. ``Section`` itself is unedited: this constructs one.

    ``momentum_index`` is the position of the 12-1 momentum column in ``base.raw``; the dispersion
    is read from the RAW matrix, because the standard deviation of a rank column is a constant of
    the cross-section's size and would carry no information at all.
    """
    extra = np.array(
        market_columns(history, base.day, np.asarray(base.raw[:, momentum_index], dtype=np.float64)),
        dtype=np.float64,
    )
    block = np.repeat(extra.reshape(1, -1), len(base.symbols), axis=0)
    raw = np.hstack([np.asarray(base.raw, dtype=np.float64), block])
    X = np.hstack([np.asarray(base.X, dtype=np.float64), block])
    raw.setflags(write=False)
    X.setflags(write=False)
    return Section(base.day, base.symbols, base.close, raw, X)


# ------------------------------------------------------------- the fall model and its sizing head


@dataclass(frozen=True, slots=True)
class FallSizeParams:
    """The fall model's pre-registered knobs. Every field enters the config digest.

    A new class rather than a field on ``TreeRankParams``: ``lab.method.config_text`` writes
    ``params={registry._canon(c.params)}`` over every ``compare`` field of the params dataclass,
    so one more field there would move five of M0130's six recorded ``config_digest``s (measured
    2026-10-13: M0130-P20 381a0d7c -> e7d9e0c2, and four more) and silently rewrite closed records.
    The two classes share ``fit_model``, the calendar, the features and the section cache by reuse.

    At most ``slots`` names are held, each at ``equal_weight(slots)``, and the unfilled slots are
    cash. ``size`` is the sizing switch: on, the model's own exposure ladder decides how many of
    the slots are filled; off, the book is always full and the method is the control that isolates
    what the sizing adds. ``measure`` picks the forward-fall measure (``FALL_MEASURES``) -- both
    are LEVELS, in their own units, never ranks (D13). ``feature_set`` must name the allocator
    object's own set (``FALL_SIZE``: "price"). The five model fields are
    ``HistGradientBoostingRegressor``'s and default to Strategy B's pre-registered ``TREE_PARAMS``,
    as the ranker's do. ``horizon`` is the label's length in sessions and defaults to ``QUARTER``.
    The refit cadence is fixed (annual), not a knob.
    """

    slots: int = 20
    size: bool = True
    feature_set: FeatureSet = "price"
    measure: FallMeasure = "drawdown"
    learning_rate: float = 0.05
    max_iter: int = 300
    max_leaf_nodes: int = 15
    min_samples_leaf: int = 200
    l2: float = 1.0
    train_start: date = date(1996, 1, 31)
    min_train_months: int = 35
    horizon: int = QUARTER
    seed: int = 0

    def __post_init__(self) -> None:
        _check_int("slots", self.slots, 1, MAX_TOP)
        if not isinstance(self.size, bool):
            raise TypeError(f"size must be a bool, got {type(self.size).__name__}")
        if not isinstance(self.feature_set, str):
            raise TypeError(f"feature_set must be a str, got {type(self.feature_set).__name__}")
        feature_names(self.feature_set)
        if not isinstance(self.measure, str):
            raise TypeError(f"measure must be a str, got {type(self.measure).__name__}")
        if self.measure not in FALL_MEASURES:
            raise ValueError(f"measure must be one of {FALL_MEASURES}, got {self.measure!r}")
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
        """Every field a fitted fall model depends on.

        NEITHER ``slots`` NOR ``size`` is in it, exactly as ``TreeRankParams.model_key()`` leaves
        ``top_n`` out, because neither touches the fit. ``levels`` and ``cut`` are the distribution
        of the model's own per-date in-sample predictions; ``slots`` is applied to that
        distribution at DECISION time by the exposure ladder, and ``size`` only decides whether the
        ladder is consulted at all. So two variants differing only in book size share one annual
        refit ladder -- which is both cheaper and the honest statement that they are the same model.
        """
        return (
            self.feature_set,
            self.measure,
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
            "slots": str(self.slots),
            "size": "on" if self.size else "off",
            "feature_set": self.feature_set,
            "measure": self.measure,
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


@dataclass(frozen=True, eq=False)
class FallModel:
    """One fall refit, plus the training distribution of DATE-LEVEL predicted falls its head reads.

    Identity is (anchor, months, rows, n_features, digest, levels); the estimator is the payload,
    as in ``TreeModel``. ``levels`` is in the identity because it is what the head actually
    consults, and ``cut`` is derived from it, so two models with the same estimator and the same
    levels are the same model to every caller.

    ``levels`` is a sorted ``tuple[float, ...]``, not an ndarray: the dataclass is hashable and a
    recorded model must compare by value. One float per labelled training month-end, so a few
    hundred at most.
    """

    anchor: date
    months: int  # labelled month-ends it learned from
    rows: int
    n_features: int
    digest: str  # b_model._tree_digest of the fitted estimator
    levels: tuple[float, ...]  # sorted mean in-sample predicted fall, one per training date
    estimator: HistGradientBoostingRegressor

    @property
    def cut(self) -> float:
        """The median training date-level predicted fall: the half-exposure point.

        Reported and tested as the model's single scalar summary of "what an ordinary date looks
        like to me". The head does not read it directly -- it reads the whole of ``levels`` -- but
        ``exposure(cut, slots)`` is about half of ``slots`` by construction, which is what makes
        this the honest one-number description of the ladder.
        """
        return self.levels[len(self.levels) // 2]

    def exposure(self, level: float, slots: int) -> int:
        """How many whole slots a cross-section at ``level`` is worth: 0 .. ``slots``.

        ``danger`` is the share of this model's training dates that looked NO MORE dangerous than
        ``level``; the book keeps the complement. Calmer than every training date -> ``slots``;
        more dangerous than all of them -> 0; at the median -> half. Monotone non-increasing in
        ``level``, so a more dangerous-looking market can never buy the book more exposure.

        Nothing here is a chosen number: the ladder is the empirical CDF of the model's own
        in-sample date-level predictions. An absolute threshold would have had to be read off the
        dev window, which pre-registration forbids.
        """
        danger = float(np.searchsorted(np.asarray(self.levels), level, side="right")) / float(
            len(self.levels)
        )
        return int(slots - math.floor(danger * slots))

    def _key(self) -> tuple[Any, ...]:
        return (self.anchor, self.months, self.rows, self.n_features, self.digest, self.levels)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, FallModel):
            return NotImplemented
        return self._key() == other._key()

    def __hash__(self) -> int:
        return hash(self._key())

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predicted fall per row -- a LEVEL in the label's own units -- float64, one thread."""
        return _predict(self.estimator, X)


def _predict(estimator: HistGradientBoostingRegressor, X: np.ndarray) -> np.ndarray:
    """``estimator``'s predictions, float64, under a one-thread limit (module docstring, DETERMINISM)."""
    with threadpool_limits(limits=1):
        return np.asarray(estimator.predict(X), dtype=np.float64)


def fit_fall_model(
    X: np.ndarray,
    y: np.ndarray,
    groups: np.ndarray,
    months: int,
    anchor: date,
    params: FallSizeParams,
) -> FallModel:
    """``params``' regressor fitted on (X, y), plus the training distribution its head reads.

    The fit is ``fit_model``, shared with the ranker and not modified, so the two heads differ in
    their label and in nothing else -- including the all-blank-column guard, which matters for the
    market columns on a history that does not reach back far enough and is otherwise inert.

    THE LEVELS are the model's own in-sample predictions averaged WITHIN each training date, then
    sorted. A distribution over DATES, not over rows, which is why ``groups`` is a parameter: the
    head asks "how dangerous does this whole cross-section look, against the cross-sections I was
    trained on", and a date with 500 names must not outvote one with 20. ``FallModel.cut`` is their
    median and ``FallModel.exposure`` is the ladder (D13, D2c).

    Nothing in this is a chosen number and nothing was read off the dev window: the ladder is the
    empirical CDF of the model's own training predictions. ``params.slots`` is NOT used here at all
    -- it is applied to this distribution at decision time -- which is why it is out of
    ``model_key()`` and why two variants differing only in book size share one fit.

    Predicting on the caller's ``X`` rather than on ``fit_model``'s internally zeroed copy is
    deliberate and makes no difference: an all-blank column is binned into one bin and never split
    on, which ``tests/test_tree_rank.py::test_an_all_missing_column_fits_as_unsplittable_and_leaves_other_fits_untouched``
    already pins.
    """
    estimator = fit_model(X, y, params)
    rows = int(X.shape[0])
    inside = _predict(estimator, X)
    levels = tuple(
        sorted(float(np.mean(inside[groups == g])) for g in range(months) if bool((groups == g).any()))
    )
    return FallModel(
        anchor,
        months,
        rows,
        int(X.shape[1]),
        _tree_digest(estimator),
        levels,
        estimator,
    )


class FallSizeAllocator:
    """The fall model behind the ``Allocator`` and ``MarketAware`` protocols (module docstring).

    One object per feature set, as ``TreeRankAllocator`` is: ``id`` and ``market_fields`` are what
    ``lab run`` reads, and they depend on whether fundamentals are ranked on. ``FALL`` was free
    across all 75 allocator ids in the registry and every discovered lab method on 2026-10-13, and
    ``tests/test_tree_fall.py`` keeps it free.

    ONLY THE "price" OBJECT IS EXPORTED (D14). The ``"price+fund"`` branch stays reachable and is
    exercised by constructing one locally in the tests, but no module-level ``FALL_SIZE_FUND``
    exists: the EDGAR panel starts in 2009, so no method may pre-register on fundamentals (D8), and
    an exported allocator no method can use would claim the id ``FALLF`` forever for nothing.
    """

    def __init__(self, feature_set: str) -> None:
        feature_names(feature_set)
        self.feature_set = feature_set
        self.id = "FALL" if feature_set == "price" else "FALLF"
        self.market_fields: tuple[str, ...] = (
            ("dividends",) if feature_set == "price" else ("dividends", "fundamentals")
        )

    def _check(self, params: object) -> FallSizeParams:
        if not isinstance(params, FallSizeParams):
            raise TypeError(f"params must be FallSizeParams, got {type(params).__name__}")
        if params.feature_set != self.feature_set:
            raise ValueError(
                f"{self.id} ranks feature_set {self.feature_set!r}; params name {params.feature_set!r}"
            )
        return params

    def lookback(self, params: Any) -> int:
        """``FALL_FEATURE_LOOKBACK`` -- the fall model's own constant, not the ranker's.

        It evaluates to the same 401 today (the market columns reach 252 and 61 sessions, both
        inside the ranker's window), but it is written as its own ``max`` so that the claim is
        arithmetic rather than a coincidence a later edit could quietly break.
        """
        self._check(params)
        return FALL_FEATURE_LOOKBACK

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
        return prepared.fall_targets_on(members, data_date, p)


FALL_SIZE = FallSizeAllocator("price")
#: No FALL_SIZE_FUND (D14/D8): the EDGAR panel starts in 2009, no method may pre-register on it,
#: and an exported allocator nothing uses would claim the id "FALLF" for ever. The "price+fund"
#: branch above stays reachable; construct one locally if you need it.


def fall_targets_with_inputs(
    inputs: TreeInputs,
    members: AbstractSet[str],
    data_date: date,
    held: frozenset[str],
    params: FallSizeParams,
) -> tuple[Target, ...]:
    """The fall model's from-scratch path: every feature, label, model and cut rebuilt from
    ``inputs`` cut at ``data_date``.

    Slow by design, and the sibling of ``targets_with_inputs``. The prepared path must equal it bit
    for bit (tests/test_tree_fall.py), which is what proves that the shared section cache, the
    shared calendar and the two private caches never let anything dated after ``data_date`` in.
    """
    if not isinstance(inputs, TreeInputs):
        raise TypeError(f"inputs must be TreeInputs, got {type(inputs).__name__}")
    if not isinstance(params, FallSizeParams):
        raise TypeError(f"params must be FallSizeParams, got {type(params).__name__}")
    _check_call(members, data_date, held)
    prepared = TreeRankPrepared.build(inputs.upto(data_date), params.feature_set)
    return prepared.fall_targets_on(members, data_date, params)

"""M0144 — Market-state columns for the learned ranker: let the trees see the fear gauge, the
yield curve and gold-free macro, not only one company against another.

Source: variation of M0137 (the forgetting ranker), which is this method's parent, and through it
of M0131 (the slow-target ranker) whose arm B20 is the lab's only eligible learned ranker. The
model class, the seven per-company features, the 252-session label, the annual walk-forward refit,
the expanding training window, the SPY 200-day switch, the book size and the measuring tape are
all inherited, imported and never copied. **One thing moves: what the model is allowed to look
at.**

WHY. Three levers have now been turned on this picker and all three are spent.

    * M0130 turned MODEL CAPACITY. Its trees picked worse than simply holding the most-traded big
      companies, and its least flexible arm did best -- the signature of a model with nothing to
      learn.
    * M0131 turned the TARGET HORIZON. Asking for next year's rank instead of next month's was
      worth 3.8 points a year over 2000-2015 and 6.5 over 2009-2015, made a learned ranker
      eligible for the first time (B20: funded 10.9% a year against SPY's 7.2%, worst fall 20.0%,
      DSR 0.912), and reversed the capacity finding -- with a slow label the FLEXIBLE tree wins,
      because now there is something to fit.
    * M0137 turned MEMORY. Forgetting made it worse in a straight line: 10.9% / 10.0% / 9.1%
      funded as the window shortened, monotone across five measures and three rungs, and the
      short windows were about six times more survivorship-fragile than the expanding one.

Every one of those is a knob on the MODEL. What has never moved is WHAT THE MODEL MAY SEE. All
seven features are per-company AND rank-normalised across the cross-section of their own date
(``rank_columns`` in ``build_section``), so **by construction the picker cannot tell 2008 from
2013**: within any date the ranks are uniform whatever the market is doing. It sees only how
companies stand against each other on a given day, never what kind of day it is.

The lab's own fall model already argues this exact case in ``tree_rank``'s docstring -- "a per-date
rank cannot encode 'every name on this date is about to fall thirty per cent', only a level can" --
and ``build_fall_section`` appends three deliberately un-normalised market-level columns for that
reason. The ranker was never given the same. This method gives it them, from
``Market.series``: the store already serves VIX, VIX3M, VIX9D, VXN, VVIX, the four Treasury
yields and gold point in time, free, with no new purchase and no new look-ahead surface beyond
``value_on``/``upto``, which are point-in-time by construction.

THE MECHANISM, AND A CORRECTION TO THE IDEA ROW THIS METHOD WAS RESERVED UNDER. The reserved idea
said a per-date column "carries no cross-sectional information and cannot change which names are
preferred, only how the whole date's predictions shift". **That is true of a linear model and
false of a tree, and the difference is the entire method.** A gradient-boosted tree that splits on
``vix_level`` at its root sends every row of a given date down the SAME branch -- and the splits
*below* that branch are on per-company features and may be different splits on the two sides. So a
market-state column does not shift a date's predictions, it SELECTS WHICH PER-COMPANY RULE RANKS
THAT DATE. "When fear is high, prefer the names nearest their 52-week high; when it is low, prefer
residual momentum" is a rule this model can now express and could not express before. The
hypothesis is about that interaction, not about a level shift, and if the mechanism is real it
should show up as a book that ranks differently in 2008 from 2013 rather than as a book that holds
more or less.

THE COLUMNS, and why these four and not the ones the idea row named. The idea row proposed the
VIX3M-over-VIX term structure. The dev store's VIX3M begins **2006-07-17** against VIX's
1993-01-29: a term-structure column would be missing for roughly six of the sixteen traded years
and -- far worse -- the model refit at the end of 2008, the single most informative regime in the
window, would have had about two and a half years of it to learn from. A column that is absent
exactly where the regime story lives tests the store, not the idea. So the fear pair is built from
VIX alone, which covers the whole window, using M0039's own whole-window construction (fear
against its own recent level) as the term-structure proxy M0039 pre-registered for the same
reason. Gold is dropped for the same arithmetic: the store's GOLD begins 2000-08-30, after the
first traded month, so every training row before the 2001 refit would be missing it.

    vix_level     the fear index, in index points, latest value dated <= d
    vix_vs_year   that level over the mean of its last VIX_MEAN_N (252) published rows through d
    t10y_level    the ten-year Treasury yield, in percent, latest value dated <= d
    t10y_slope    that yield minus the thirteen-week yield: the curve's slope, in percent

All four read only rows dated on or before the decision date, through ``MarketSeries.upto``, and a
reading older than ``STALE_DAYS`` (7 calendar days, M0039's constant, imported not restated) is
NaN -- "not known", never zero. ``fit_model`` bins a missing value into its own bin, and a column
with no finite value at all is fitted as a constant, so an arm still runs on a store with no
series at all (which is what the lab's smoke fixture is).

NOT RANK-NORMALISED, DELIBERATELY, and this is the one place this method departs from the ranker's
discipline on purpose. ``rank_columns`` would destroy the column: a per-date scalar broadcast down
the rows has exactly one distinct value, so its rank is a constant of the cross-section's size and
carries nothing at all. ``build_state_section`` therefore COMPOSES ``build_section`` -- which is
not edited, nor is ``Section``, ``rank_columns``, ``PRICE_FEATURES`` or any other line of
``lab/tree_rank.py`` -- and appends the raw levels after the seven ranked columns, exactly as
``build_fall_section`` does. Nothing in ``m0130``, ``m0131`` or ``m0137`` is edited either; all
four files have run and are frozen, and no recorded configuration's digest moves, because this
method's params are a new class behind a new allocator id.

WITH NO COLUMNS THE AUGMENTATION IS A NO-OP BY SHORT CIRCUIT, not by arithmetic: ``_section``
returns the base ``Section`` object itself when ``columns`` is empty, so CTRL is bit-identical to
M0137-EXP, which is M0131-B20. That is both the in-batch control and a correctness check -- if
CTRL does not reproduce EXP's recorded numbers the wrapper has a bug and the batch is void.

EVERY VARIANT IS GATED, the control included and read first, because M0130's ungated arms fell
about 70% in 2008 and the lab has measured the SPY 200-day switch helping 22 of 22 variants
whole-window. Re-measuring that here would spend the method id on a settled question. Note the
tension this creates and which the analysis must address: **the gate is itself a market-state
reading**, and it is where the whole-window win has come from so far (M0131's exposure was 68%).
A market-state column that merely re-discovers a worse version of the gate, on the 68% of days
the gate already said "on", would be a null result wearing a new coat. ``lab exposure`` and
``lab gate`` separate the picker from the switch and the analysis reports both.

Pure: no clock, randomness, files, network or printing. Reads only data dated <= data_date.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from datetime import date, timedelta
from types import MappingProxyType
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import EMPTY_SERIES, MarketSeries
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0039_vix_term_structure_gate import STALE_DAYS
from seer_engine.lab.methods.m0130_tree_ranker import (
    BENCH,
    GATE,
    ControlParams,
    _bench,
    model_ready,
)
from seer_engine.lab.methods.m0131_slow_target_ranker import YEAR, GatedDollarVolumeBook
from seer_engine.lab.tree_rank import (
    TREE_RANK,
    Section,
    TreeInputs,
    TreeModel,
    TreeRankParams,
    TreeRankPrepared,
    anchor_for,
    feature_names,
    fit_model,
)
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE_TBAND
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.b_model import _tree_digest
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import factor_lookback, trend_on

ADDED = date(2026, 10, 14)

NAN = float("nan")

# M0131's B20 tree, field for field, reached through M0137: the flexible tree on the yearly label,
# the lab's only eligible learned ranker. Not searched here and not an arm of this method.
BASE = TreeRankParams(top_n=20, horizon=YEAR)

VIX_MEAN_N = 252
"""Published VIX rows in the trailing mean ``vix_vs_year`` is measured against (about one year).

Rows, not sessions: the series publishes on its own calendar and ``upto(..., last=N)`` counts what
was published. 252 is the ranker's own year (``tree_rank.YEAR``) read in the same spirit, and VIX
has published since 1993-01-29, so the column is finite from early 1994 and over every training
row this method ever sees.
"""


# --------------------------------------------------------------------- the market-state columns


def _fresh(series: MarketSeries, name: str, day: date) -> float:
    """``name``'s latest published value dated on or before ``day``, or NaN when it is stale.

    M0039's discipline, and its constant: a series row older than ``STALE_DAYS`` calendar days is
    no reading at all. A Treasury index has no close on Columbus Day while the stock market
    trades, so "dated exactly ``day``" would be wrong; "published within a week" is what a trader
    actually knew that morning. NaN is left as NaN -- the tree bins a missing value into its own
    branch, which is the honest encoding of "this column is not known on this date".
    """
    rows = series.upto(name, day, last=1)
    if not rows or (day - rows[-1][0]) > timedelta(days=STALE_DAYS):
        return NAN
    return float(rows[-1][1])


def _vix_level(series: MarketSeries, day: date) -> float:
    return _fresh(series, "VIX", day)


def _vix_vs_year(series: MarketSeries, day: date) -> float:
    """Fear against its own recent level: VIX(d) over the mean of its last ``VIX_MEAN_N`` rows.

    M0039's ``spike`` construction, which that method pre-registered as the whole-window proxy for
    an inverted term structure precisely because the three-month series starts in 2006. Stationary
    by construction, unlike the raw level, and that is the point of having both: if the model can
    only use one of them, which one tells us whether the regime signal is a level or a surprise.
    """
    level = _fresh(series, "VIX", day)
    if not math.isfinite(level):
        return NAN
    rows = series.upto("VIX", day, last=VIX_MEAN_N)
    if len(rows) < VIX_MEAN_N:
        return NAN
    mean = sum(v for _, v in rows) / len(rows)
    return level / mean if mean > 0.0 else NAN


def _t10y_level(series: MarketSeries, day: date) -> float:
    return _fresh(series, "T10Y", day)


def _t10y_slope(series: MarketSeries, day: date) -> float:
    """The ten-year yield minus the thirteen-week yield, in percent; negative is an inverted curve."""
    long_ = _fresh(series, "T10Y", day)
    short = _fresh(series, "T13W", day)
    if not (math.isfinite(long_) and math.isfinite(short)):
        return NAN
    return long_ - short


COLUMNS: Mapping[str, Any] = MappingProxyType({
    "vix_level": _vix_level,
    "vix_vs_year": _vix_vs_year,
    "t10y_level": _t10y_level,
    "t10y_slope": _t10y_slope,
})
"""Every market-state column this method can ask for, by name. The only four it ever tries."""

FEAR_COLS: tuple[str, ...] = ("vix_level", "vix_vs_year")
RATE_COLS: tuple[str, ...] = ("t10y_level", "t10y_slope")
BOTH_COLS: tuple[str, ...] = FEAR_COLS + RATE_COLS


def check_columns(columns: object) -> tuple[str, ...]:
    """``columns`` as a validated tuple of known names: a tuple, no duplicates, each known."""
    if not isinstance(columns, tuple):
        raise TypeError(f"columns must be a tuple, got {type(columns).__name__}")
    for name in columns:
        if not isinstance(name, str):
            raise TypeError(f"a column name must be a str, got {type(name).__name__}")
        if name not in COLUMNS:
            raise ValueError(f"unknown market-state column {name!r}; known: {tuple(COLUMNS)}")
    if len(set(columns)) != len(columns):
        raise ValueError(f"columns must not repeat, got {columns}")
    return tuple(columns)


def market_state(series: MarketSeries, day: date, columns: tuple[str, ...]) -> tuple[float, ...]:
    """The date's market-state scalars, in ``columns`` order. Reads only rows dated <= ``day``."""
    return tuple(COLUMNS[name](series, day) for name in columns)


def build_state_section(
    base: Section, series: MarketSeries, columns: tuple[str, ...]
) -> Section:
    """``base`` with the market-state columns appended raw, after its seven ranked ones.

    COMPOSES ``build_section``'s output; it does not reimplement or edit it. With no columns it
    returns ``base`` ITSELF -- the same object, not an equal one -- so a no-column arm is
    bit-identical to M0137-EXP rather than merely arithmetically equal to it.

    ``base.X`` carries the ranker's rank-normalised columns and is copied through untouched, so the
    model sees exactly what the ranker sees plus columns that were never ranked. ``base.raw`` gains
    the same block, so a reader of the raw matrix sees the levels as they were read.
    """
    if not columns:
        return base
    extra = np.array(market_state(series, base.day, columns), dtype=np.float64)
    block = np.repeat(extra.reshape(1, -1), len(base.symbols), axis=0)
    raw = np.hstack([np.asarray(base.raw, dtype=np.float64), block])
    X = np.hstack([np.asarray(base.X, dtype=np.float64), block])
    raw.setflags(write=False)
    X.setflags(write=False)
    return Section(base.day, base.symbols, base.close, raw, X)


# --------------------------------------------------------------------------- params


@dataclass(frozen=True, slots=True)
class StateParams:
    """M0137's book params with the rolling window removed and the column set put in its place.

    ``tree`` is the tree M0131 ran (B20's), unchanged and never searched here. ``columns`` is the
    market-state block, empty for the control. ``gate`` is the SPY 200-day switch and is True in
    every variant of this method.
    """

    tree: TreeRankParams
    columns: tuple[str, ...] = ()
    gate: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.tree, TreeRankParams):
            raise TypeError(f"tree must be TreeRankParams, got {type(self.tree).__name__}")
        if not isinstance(self.gate, bool):
            raise TypeError(f"gate must be a bool, got {type(self.gate).__name__}")
        object.__setattr__(self, "columns", check_columns(self.columns))

    def model_key(self) -> tuple[Any, ...]:
        """Every field a fitted model depends on: the tree's own key plus the column set."""
        return (*self.tree.model_key(), self.columns)

    def as_dict(self) -> dict[str, str]:
        out = dict(self.tree.as_dict())
        out["market_state"] = ",".join(self.columns) if self.columns else "none"
        out["gate"] = "SPY:200" if self.gate else "none"
        return out


# --------------------------------------------------------------------------- the prepared value


@dataclass(eq=False)
class StatePrepared:
    """This method's state for one market: the ranker's prepared value plus the series and caches.

    ``inner`` holds the base cross-sections, the labels, the label calendar and the training-date
    rule, all of which are the ranker's and are reused rather than reimplemented. What this method
    owns is the augmented sections (cached by date, universe and column set) and the models fitted
    on them (cached by anchor and ``model_key``), because the ranker's own caches are keyed on
    ``TreeRankParams`` and know nothing about a column set.

    ``history`` is None on the history-only path, which targets nothing by the lab's market-aware
    contract.
    """

    inner: TreeRankPrepared
    history: Mapping[str, History] | None = field(default=None, repr=False)
    series: MarketSeries = field(default=EMPTY_SERIES, repr=False)
    _sections: dict[tuple[date, Any, tuple[str, ...]], Section] = field(
        default_factory=dict, repr=False
    )
    _models: dict[tuple[Any, ...], TreeModel | None] = field(default_factory=dict, repr=False)

    def section(self, t: date, universe: AbstractSet[str] | None, columns: tuple[str, ...]) -> Section:
        """The augmented cross-section on ``t``: the ranker's own, plus this method's columns."""
        key = (t, None if universe is None else frozenset(universe), columns)
        hit = self._sections.get(key)
        if hit is None:
            hit = build_state_section(self.inner.section(t, universe), self.series, columns)
            self._sections[key] = hit
        return hit

    def training_set(self, p: StateParams, anchor: date) -> tuple[np.ndarray, np.ndarray, int]:
        """(X, y, labelled month-ends) for a refit on ``anchor``, rows stacked by (t, symbol).

        The ranker's ``training_dates`` and ``labels`` verbatim, so the rows and their labels are
        the ones M0137-EXP trained on, name for name and date for date; only the width of X moves.
        """
        k = len(feature_names(self.inner.feature_set)) + len(p.columns)
        xs: list[np.ndarray] = []
        ys: list[np.ndarray] = []
        months = 0
        for t in self.inner.training_dates(p.tree, anchor):
            y = self.inner.labels(t, p.tree.horizon)
            ok = np.isfinite(y)
            if not ok.any():
                continue
            months += 1
            xs.append(self.section(t, None, p.columns).X[ok])
            ys.append(y[ok])
        if not xs:
            return np.empty((0, k), dtype=np.float64), np.empty(0, dtype=np.float64), 0
        return np.concatenate(xs, axis=0), np.concatenate(ys), months

    def model(self, p: StateParams, anchor: date) -> TreeModel | None:
        """The model refit on ``anchor``, or None with fewer than ``min_train_months`` to learn from."""
        key = (anchor, p.model_key())
        if key in self._models:
            return self._models[key]
        X, y, months = self.training_set(p, anchor)
        model: TreeModel | None = None
        if months >= p.tree.min_train_months and X.shape[0] >= 2:
            estimator = fit_model(X, y, p.tree)
            model = TreeModel(
                anchor, months, int(X.shape[0]), int(X.shape[1]), _tree_digest(estimator), estimator
            )
        self._models[key] = model
        return model

    def targets_on(
        self, members: AbstractSet[str], data_date: date, p: StateParams
    ) -> tuple[Target, ...]:
        """The ``top_n`` highest predictions among ``members``' cross-section on ``data_date``.

        The ranker's ``targets_on`` rule, read against this method's sections and models: highest
        prediction first, ties by symbol, non-finite predictions skipped, equal weight at
        ``top_n``, priced at the date's close.
        """
        model = self.model(p, anchor_for(data_date))
        if model is None:
            return ()
        sec = self.section(data_date, members, p.columns)
        if not sec.symbols:
            return ()
        pred = model.predict(sec.X)
        order = sorted(range(len(sec.symbols)), key=lambda k: (-float(pred[k]), sec.symbols[k]))
        weight = equal_weight(p.tree.top_n)
        out: list[Target] = []
        for k in order:
            if len(out) == p.tree.top_n:
                break
            if not math.isfinite(float(pred[k])):
                continue
            target = target_from_close(sec.symbols[k], float(sec.close[k]), weight)
            if target is not None:
                out.append(target)
        return tuple(out)


# --------------------------------------------------------------------------- the allocator


class MarketStateBook:
    """M0137's gated tree book with market-state columns in the feature matrix, nothing else moved.

    The three rules are read in M0137's order and are identical in every arm: switch off -> cash;
    no model yet -> hold SPY; otherwise hand the model the augmented cross-section. The readiness
    rule reads the tree's own ``train_start``, so every variant starts trading the same session,
    January 2000, and every paired difference inside this batch is the column set alone.
    """

    id = "M0144"

    def __init__(self) -> None:
        self.inner = TREE_RANK
        # The inner ranker's fields, plus the series this method reads: `lab run` refuses a store
        # without market series (runner.preflight_data), which is the right failure.
        self.market_fields: tuple[str, ...] = (*TREE_RANK.market_fields, "series")

    def _check(self, params: object) -> StateParams:
        if not isinstance(params, StateParams):
            raise TypeError(f"params must be StateParams, got {type(params).__name__}")
        return params

    def lookback(self, params: Any) -> int:
        p = self._check(params)
        n = self.inner.lookback(p.tree)
        return max(n, factor_lookback(GATE)) if p.gate else n

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = self._check(params)
        return tuple(sorted({BENCH, *self.inner.symbols(p.tree)}))

    def holds(self, params: Any) -> tuple[str, ...]:
        self._check(params)
        return (BENCH,)

    def uses_members(self, params: Any) -> bool:
        self._check(params)
        return True

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """History-only path: no membership, no calendar, no series, no model, so no target."""
        self._check(params)
        return ()

    def prepare(self, history: Mapping[str, History]) -> StatePrepared:
        return StatePrepared(self.inner.prepare(history))

    def prepare_market(self, market: Any) -> StatePrepared:
        return StatePrepared(
            TreeRankPrepared.build(TreeInputs.from_market(market), self.inner.feature_set),
            MappingProxyType(dict(market.history)),
            getattr(market, "series", EMPTY_SERIES),
        )

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = self._check(params)
        if not isinstance(prepared, StatePrepared):
            raise TypeError(f"prepared must be StatePrepared, got {type(prepared).__name__}")
        if prepared.history is None or prepared.inner.inputs is None:
            return ()
        if p.gate and not trend_on(prepared.history, data_date, GATE):
            return ()
        if not model_ready(data_date, p.tree.train_start, p.tree.min_train_months, p.tree.horizon):
            return _bench(prepared.history, data_date)
        return prepared.targets_on(members, data_date, p)


STATE_BOOK = MarketStateBook()


class M0144Control(GatedDollarVolumeBook):
    """M0131's gated dollar-volume control, re-run here under this method's own allocator id.

    Not one line of its behaviour changes; only the id does, because a config digest names the
    allocator by id and the lab rightly refuses a configuration it has already run. Running it
    again costs compute and nothing else (a method is one look however many variants it has), and
    it buys the batch a no-forecast control measured at the same trial boundary as the arms it
    judges, rather than quoted across one.
    """

    id = "M0144-DV"


DV_BOOK = M0144Control()


# --------------------------------------------------------------------------- the method


def _v(suffix: str, allocator: Any, params: Any, rationale: str) -> Candidate:
    return Candidate(id=f"M0144-{suffix}", family="M0144", rules=MONTHLY_HOLD_FRAC_GOTRADE_TBAND,
                     allocator=allocator, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0144",
    name=(
        "Market-state columns for the learned ranker: the trees see the fear gauge and the yield "
        "curve, not only one company against another"
    ),
    family="stock-ml-ranker",
    source_kind="variation",
    source_ref="variation of M0137 (the forgetting ranker); Sera batch 20261014-1312",
    parent_id="M0137",
    hypothesis=(
        "Three levers have been turned on this picker and all three are spent. M0130 turned model "
        "capacity and found a model with nothing to learn (its least flexible arm did best, and "
        "every arm lost to a control that forecasts nothing). M0131 turned the target horizon and "
        "found 3.8 points a year over 2000-2015 and 6.5 over 2009-2015, making B20 the lab's "
        "first and only eligible learned ranker. M0137 turned memory and found a monotone "
        "dose-response in the WRONG direction: halving the training window cost 0.9 points a year "
        "and quartering it cost 1.8, the 2009-2015 lead fell from -0.7% to -2.0% to -4.4%, and the "
        "survivorship check punished the short windows about six times harder. Three facts now "
        "agree: more history helps, more capacity helps, short memory is fragile. The picker is "
        "INFORMATION-STARVED, not regime-confused. And every one of those three levers is a knob "
        "on the MODEL. WHAT HAS NEVER MOVED IS WHAT THE MODEL MAY LOOK AT. All seven features are "
        "per-company and every one is rank-normalised across the cross-section of its own date, so "
        "by construction the picker cannot tell 2008 from 2013: within any date the ranks are "
        "uniform whatever the market is doing. The lab's own fall model already fixes this for its "
        "own question and its docstring argues the case explicitly -- a per-date rank cannot "
        "encode 'every name on this date is about to fall thirty per cent', only a level can -- "
        "and it appends three un-normalised market-level columns for exactly that reason. The "
        "ranker was never given the same. THE MECHANISM IS AN INTERACTION, NOT A LEVEL SHIFT, and "
        "this corrects the idea row this method was reserved under. A per-date constant column "
        "cannot change a LINEAR model's ranking, but a TREE that splits on it sends every row of a "
        "date down the same branch and then applies DIFFERENT per-company splits on the two sides. "
        "So a market-state column selects WHICH PER-COMPANY RULE RANKS THAT DATE. 'When fear is "
        "high prefer the names nearest their 52-week high; when it is low prefer residual "
        "momentum' is a rule this model can now express and could not express before, and that, "
        "not a shift in the level of its predictions, is what this method is testing. THE SOURCE "
        "IS FREE AND ALREADY POINT IN TIME: Market.series serves VIX from 1993, the four Treasury "
        "yields from 1993, and the rest, read through value_on/upto which cannot see past the "
        "decision date; declaring that this method reads them means lab run refuses a store "
        "without them, which is the right failure. THE COLUMNS ARE FOUR, AND NOT THE ONES THE IDEA "
        "ROW NAMED, for a measured reason written down before the run: the store's three-month "
        "fear series begins 2006-07-17 and gold begins 2000-08-30, so a term-structure or gold "
        "column would be missing for six of the sixteen traded years and -- worse -- the model "
        "refit at the end of 2008, the single most informative regime in the window, would have "
        "had about two and a half years of it to learn from. A column absent exactly where the "
        "regime story lives tests the store, not the idea. So the fear pair is the VIX level and "
        "the VIX against the mean of its own last 252 published rows (M0039's pre-registered "
        "whole-window proxy for an inverted curve, chosen by M0039 for this same coverage reason), "
        "and the rate pair is the ten-year yield and the ten-year minus the thirteen-week slope. "
        "All four cover every training row this method ever sees. A reading older than seven "
        "calendar days is NaN, M0039's constant, imported not restated; NaN means not known, never "
        "zero, and the trees bin it into its own branch. FIVE VARIANTS, THE ONLY SETTINGS EVER "
        "TRIED, none chosen by looking at a dev result: CTRL is the unchanged seven-feature book, "
        "which is M0137-EXP, which is M0131-B20, and it is BOTH the in-batch control and a "
        "correctness check -- the augmentation returns the base cross-section object itself when "
        "the column set is empty, so CTRL must reproduce EXP's recorded numbers bit for bit, and "
        "if it does not the wrapper has a bug and the batch is void; FEAR adds the two fear "
        "columns; RATE adds the two rate columns; BOTH adds all four; DV20 is the CONTROL, M0131's "
        "gated 20-name dollar-volume book re-run here so the what-does-the-model-add comparison "
        "never crosses a trial boundary. Every arm is gated at the SPY 200-day switch, the control "
        "included and read first, because M0130's ungated arms fell about 70% in 2008 and the "
        "switch has helped 22 of 22 lab variants whole-window. THE TENSION THAT CREATES IS NAMED "
        "NOW: the gate is itself a market-state reading and it is where the whole-window win has "
        "come from so far (M0131's exposure was 68%, its picks alone earned 9.9% a year). A column "
        "that merely re-discovers a worse version of the gate on the 68% of days the gate already "
        "said 'on' is a null result wearing a new coat, and the analysis will report the picks "
        "alone beside the gated book so the two cannot be confused. WHAT COUNTS AS AN IMPROVEMENT, "
        "FIXED NOW AND NOT NEGOTIABLE AFTERWARDS: a market-state arm beats the seven-feature "
        "control over 2009-2015 de-funded AND wins at least 3 of its 4 walk-forward folds -- the "
        "same bar M0137 set and failed, because it is the right bar and failing it honestly is the "
        "point. The arm that clears it must be one the bar named; an arm that clears it by "
        "accident is not the result. IF NO ARM CLEARS IT, the learned-ranker direction is closed "
        "on this signal set: the lab will have changed the model's capacity, its target, its "
        "memory and its inputs and found no recent edge in any of them, and it should stop "
        "building rankers and go looking for information it does not have. WHAT COUNTS AS A "
        "METHOD: a variant clears every design section 1 bar at DSR >= 0.90 at the lab's N, "
        "against the dev screen on the worst fall (50%) and the real-money bar (25%). No variant "
        "is promoted in this run whatever it shows: the test window is not touched."
    ),
    expected_failure=(
        "Most likely the market-state columns are the thinnest information the model has ever been "
        "given, and no arm clears the pre-registered bar. Six reasons, written before the run. "
        "FIRST AND STRONGEST, the effective sample size. Every per-company feature has about "
        "57,000 training rows at the 2014 refit. A market-state column is a per-DATE scalar, so "
        "however many rows it is broadcast down it carries at most 216 distinct values -- one per "
        "training month-end -- and because the label is a 252-session forward return on monthly "
        "samples, neighbouring dates overlap 92%. The number of genuinely independent REGIME "
        "observations over 1996-2014 is not 216 but something nearer the count of business cycles: "
        "two, perhaps three. Asking a 300-iteration tree with 15 leaves to learn a regime "
        "interaction from two or three independent regimes is the textbook recipe for memorising "
        "'in 2008, do this' and generalising nothing. The lab's own fall model lives with exactly "
        "this limitation and is honest about it. SECOND, the rate levels are non-stationary in a "
        "way the fear columns are not. The ten-year yield falls from about 7% in 1996 to about 2% "
        "by 2015 and never returns, so a tree whose splits were learned on 1996-2008 rate levels "
        "sends EVERY date from 2009 on down the same terminal branch: the RATE arm may be "
        "arithmetically incapable of distinguishing anything in the era the bar is scored on, "
        "which would be a null result caused by the column's own distribution rather than by the "
        "idea. The slope is better behaved and inverted before both of the window's recessions, so "
        "if any rate column earns its place it should be that one, and the arm is built so the two "
        "can be told apart. THIRD, the gate has already taken the regime signal. The SPY 200-day "
        "switch is a market-state reading, it sits in front of every arm, and it produced the "
        "whole-window win: M0131 held no pick on 28% of decision days and returned about 0% in "
        "2001, 2002 and 2008. On the 68% of days the switch says 'on' the market is by "
        "construction above its own 200-day average, which is most of the low-fear days, so the "
        "fear columns may have almost no variation left to read where the book is actually "
        "invested. A column that only fires when the book is already in cash cannot change a "
        "single trade. FOURTH, interaction needs more data than a main effect, not less. The "
        "mechanism this method is built on is 'rank differently in different regimes', which asks "
        "the model to fit a separate per-company rule per regime out of a sample that was already "
        "too small for one rule -- M0130's whole finding was a model with nothing to learn, and "
        "M0131's flexible-tree win says it is data-limited. Splitting a data-limited sample by "
        "regime is the direction that makes it worse. FIFTH, survivorship is unchanged and "
        "unhelped: the check store already deepened B20's worst fall from 20.0% to 23.1% and "
        "dropped its DSR to 0.839, under the 0.90 bar, so any eligibility here still rests on data "
        "missing four in ten index-member days, and a regime column cannot restore a dead company. "
        "SIXTH, DSR at N = 90 and rising needs a Sharpe above anything any of the three rankers "
        "has produced (the best is 0.84), so even an arm that beats the control on return is "
        "likely to fail the luck test. THE MOST INFORMATIVE FAILURE would be FEAR clearing the "
        "2009-2015 leg and failing the folds: that would say the regime signal is real in sample "
        "and does not survive being chosen, which is M0137's finding about short memory arriving "
        "by a second road and would close the direction harder than a flat null. THE LEAST "
        "INFORMATIVE would be all four arms within noise of CTRL, which would say the columns were "
        "never split on at all -- and that is checkable, because a tree that never splits on a "
        "column produces a book identical to CTRL's, trade for trade."
    ),
    candidates=(
        _v("CTRL", STATE_BOOK, StateParams(BASE),
           "Control and correctness check: the unchanged seven-feature book, which must reproduce "
           "M0137-EXP exactly"),
        _v("FEAR", STATE_BOOK, StateParams(BASE, columns=FEAR_COLS),
           "The fear pair: the VIX level and the VIX against the mean of its own last 252 rows"),
        _v("RATE", STATE_BOOK, StateParams(BASE, columns=RATE_COLS),
           "The rate pair: the ten-year yield and the ten-year minus thirteen-week curve slope"),
        _v("BOTH", STATE_BOOK, StateParams(BASE, columns=BOTH_COLS),
           "All four market-state columns at once: the method's main arm"),
        _v("DV20", DV_BOOK, ControlParams(top_n=20, horizon=YEAR),
           "Control: the same gated 20-name book picked by trading volume, no model"),
    ),
    seen_keys=(
        "concept:market-state-columns-learned-ranker",
        "concept:regime-conditional-cross-sectional-ranking",
        "concept:macro-features-stock-ranker",
    ),
)

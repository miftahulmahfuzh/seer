"""M0153 — The accounts-only picker, judged where the accounts exist: the learned ranker on the SEC
panel alone, trained from 2010 and scored on 2012-2015 against the same tree on price alone.

Source: variation of M0144 (the market-state ranker), which is this method's parent, and through it
of M0131 (the slow-target ranker) whose B20 tree this method keeps field for field: the flexible
tree, the 252-session label, the annual walk-forward refit, the expanding window, the SPY 200-day
switch, 20 names at equal weight and the measuring tape. **What moves is the information the trees
may see, and the calendar that information forces.**

WHY. Four levers have now been turned on the learned ranker -- capacity (M0130), target horizon
(M0131), memory (M0137) and market-state inputs (M0144) -- and the out-of-sample record was 1 or 2
of 4 walk-forward folds every time. Every one of its seven signals is price and dividend
arithmetic, the one thing every other participant has for free. The unused asset is already on
disk: the SEC EDGAR panel, which ``tree_rank`` reads through ``TREE_RANK_FUND``'s four columns
(value, quality, profitability, surprise) and which no ranker method has ever been pre-registered
on, because the panel starts in 2009 and a panel-gated method would be blind for thirteen of the
dev window's twenty years. This method takes that objection at its word instead of arguing with
it: it learns only where the panel exists and is scored only where its first model exists.

THE CALENDAR, MEASURED ON THE DEV STORE BEFORE THIS FILE WAS WRITTEN (index members with a finite
column, at quarter-ends, of about 355-410 members priced):

    value          233 by 2009-09, 268 by 2010-03, 342 by 2011-12
    quality          2 by 2009-09, 208 by 2010-03, 314 by 2011-12
    profitability    1 by 2009-09, 132 by 2010-03, 204 by 2011-12
    surprise         0 until 2010-03, 46 by 2011-03, 243 by 2011-06, 260 by 2011-12

So the panel can first describe most members on three of its four columns at the 2010-03-31
month-end, and that is ``train_start``. The label is a 252-session forward return, so a month-end
sample becomes trainable a year later: the refit at the last session of 2011 (2011-12-30) holds
exactly ten labelled month-ends, 2010-03 through 2010-12, about 3,500 rows. ``min_train_months``
is therefore 10 -- the most that refit can hold -- so the first model decides the first session of
2012 and every variant starts picking on the same day, 2012-01-03. The 2012 refit then holds 22
months, the 2013 refit 34 and the 2014 refit 46. The surprise column is nearly absent from the
first model's rows (it fills in during 2011) and enters properly from the 2012 refit. A larger
``min_train_months`` would push the first pick to 2013 and leave under three years to score; a
smaller one would not move the first pick, so 10 is the calendar's answer, not a tuned one.

BEFORE THE FIRST MODEL, THE BOOK IS SPY, UNGATED. This is the one rule this method orders
differently from M0131 and M0144 (which read the switch first), and it is deliberate. The dev row
covers 1996-2015 whether the method can see or not; the contract test's smoke market is 473
sessions long, so the start cannot be moved by declaring a nineteen-year lookback. Holding plain
SPY until the model exists makes the book's curve the benchmark's own curve, deposits and Gotrade
fees included, so the whole-window row can only differ from SPY in 2012-2015. The pre-registered
measure is nevertheless not that row: it is the recorded monthly curves, de-funded, sliced to
2012-01 .. 2015-10 (walk-forward's own ``measure``), beside SPY's recorded curve on the same slice.
The whole-window row will also fail the worst-fall screen on SPY's own 2008 fall; that is the
yardstick's fall, not the picker's, and the analysis says so.

THE ARMS read one cross-section: ``TREE_RANK_FUND``'s eleven columns (seven price, four accounts),
built once by ``tree_rank``'s own ``build_section`` and rank-normalised per date as ever. An arm is
a column subset of that matrix. Every arm trains on the same rows with the same labels, so the
paired differences are the columns alone:

    FUND   the four account columns only
    PRICE  the seven price columns only -- the paired control, B20's features on the short window
    ALL    all eleven
    DV20   M0131's gated 20-name dollar-volume book, no model, on the same calendar

A member with no visible filing has NaN account columns; the tree bins NaN into its own branch, so
"no filing" is information the FUND arm may use or ignore. The universe is the same in every arm.

UNPROMOTABLE BY CONSTRUCTION, AND RUN ANYWAY. The hard gate's fold rule wants at least four
scoreable walk-forward folds; a 1996 curve yields three, and only the third (2012-14) is picked by a
model. This method can never be promoted. It is run because the question it answers -- do the
accounts add anything on top of price, where both can be seen? -- decides whether the lab should
ever pay for older fundamentals, and the paired comparison inside one trial answers it at the cost
of one method look.

Pure: no clock, randomness, files, network or printing. Reads only data dated <= data_date.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from datetime import date
from types import MappingProxyType
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0130_tree_ranker import (
    BENCH,
    GATE,
    ControlParams,
    _bench,
    model_ready,
)
from seer_engine.lab.methods.m0131_slow_target_ranker import YEAR, GatedDollarVolumeBook
from seer_engine.lab.tree_rank import (
    FUND_FEATURES,
    PRICE_FEATURES,
    TREE_RANK_FUND,
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

ADDED = date(2026, 10, 16)

PANEL_START = date(2010, 3, 31)
"""The first month-end on which the panel describes most members on three of its four columns."""

FIRST_MODEL_MONTHS = 10
"""Labelled month-ends the 2011-12-30 refit holds from ``PANEL_START``: 2010-03 .. 2010-12."""

# M0131's B20 tree, field for field, on the eleven-column cross-section and the panel's calendar.
TREE = TreeRankParams(
    top_n=20, feature_set="price+fund", horizon=YEAR,
    train_start=PANEL_START, min_train_months=FIRST_MODEL_MONTHS,
)

ALL_COLS: tuple[str, ...] = feature_names("price+fund")
FUND_COLS: tuple[str, ...] = FUND_FEATURES
PRICE_COLS: tuple[str, ...] = PRICE_FEATURES


def check_columns(columns: object) -> tuple[str, ...]:
    """``columns`` as a validated, non-empty tuple of the eleven names, in the matrix's own order."""
    if not isinstance(columns, tuple) or not columns:
        raise TypeError(f"columns must be a non-empty tuple, got {columns!r}")
    for name in columns:
        if name not in ALL_COLS:
            raise ValueError(f"unknown column {name!r}; known: {ALL_COLS}")
    if len(set(columns)) != len(columns):
        raise ValueError(f"columns must not repeat, got {columns}")
    return tuple(c for c in ALL_COLS if c in columns)


@dataclass(frozen=True, slots=True)
class SubsetParams:
    """The B20 tree on the panel's calendar, and which of the eleven columns the arm may see."""

    tree: TreeRankParams
    columns: tuple[str, ...]
    gate: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.tree, TreeRankParams):
            raise TypeError(f"tree must be TreeRankParams, got {type(self.tree).__name__}")
        if self.tree.feature_set != "price+fund":
            raise ValueError("the tree must read the eleven-column cross-section")
        if not isinstance(self.gate, bool):
            raise TypeError(f"gate must be a bool, got {type(self.gate).__name__}")
        object.__setattr__(self, "columns", check_columns(self.columns))

    @property
    def index(self) -> tuple[int, ...]:
        return tuple(ALL_COLS.index(c) for c in self.columns)

    def model_key(self) -> tuple[Any, ...]:
        return (*self.tree.model_key(), self.columns)

    def as_dict(self) -> dict[str, str]:
        out = dict(self.tree.as_dict())
        out["columns"] = ",".join(self.columns)
        out["gate"] = "SPY:200" if self.gate else "none"
        out["before_first_model"] = "SPY"
        return out


def _subset(sec: Section, index: tuple[int, ...]) -> Section:
    """``sec`` with only the columns at ``index`` in X (raw keeps all eleven, for a reader)."""
    X = np.ascontiguousarray(np.asarray(sec.X, dtype=np.float64)[:, list(index)])
    X.setflags(write=False)
    return Section(sec.day, sec.symbols, sec.close, sec.raw, X)


@dataclass(eq=False)
class SubsetPrepared:
    """The ranker's eleven-column prepared value, plus this method's subset sections and models.

    ``inner`` owns the cross-sections, labels and training dates, reused rather than reimplemented;
    this value owns only the column-subset views and the models fitted on them, keyed by anchor and
    ``SubsetParams.model_key``. ``history`` is None on the history-only path (no targets).
    """

    inner: TreeRankPrepared
    history: Mapping[str, History] | None = field(default=None, repr=False)
    _sections: dict[tuple[Any, ...], Section] = field(default_factory=dict, repr=False)
    _models: dict[tuple[Any, ...], TreeModel | None] = field(default_factory=dict, repr=False)

    def section(self, t: date, universe: AbstractSet[str] | None, index: tuple[int, ...]) -> Section:
        key = (t, None if universe is None else frozenset(universe), index)
        hit = self._sections.get(key)
        if hit is None:
            hit = _subset(self.inner.section(t, universe), index)
            self._sections[key] = hit
        return hit

    def training_set(self, p: SubsetParams, anchor: date) -> tuple[np.ndarray, np.ndarray, int]:
        """The ranker's own rows and labels for a refit on ``anchor``; only the width of X moves."""
        xs: list[np.ndarray] = []
        ys: list[np.ndarray] = []
        months = 0
        for t in self.inner.training_dates(p.tree, anchor):
            y = self.inner.labels(t, p.tree.horizon)
            ok = np.isfinite(y)
            if not ok.any():
                continue
            months += 1
            xs.append(self.section(t, None, p.index).X[ok])
            ys.append(y[ok])
        if not xs:
            return np.empty((0, len(p.index)), dtype=np.float64), np.empty(0, dtype=np.float64), 0
        return np.concatenate(xs, axis=0), np.concatenate(ys), months

    def model(self, p: SubsetParams, anchor: date) -> TreeModel | None:
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

    def targets_on(self, members: AbstractSet[str], data_date: date, p: SubsetParams) -> tuple[Target, ...]:
        """The ranker's ``targets_on`` rule on this arm's columns: top ``top_n`` predictions."""
        model = self.model(p, anchor_for(data_date))
        if model is None:
            return ()
        sec = self.section(data_date, members, p.index)
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


class SubsetBook:
    """The gated B20 book on a column subset of the eleven-column cross-section.

    Rules, in this order: no model yet -> hold SPY, ungated, so the curve is the yardstick's own;
    switch off -> cash; otherwise the arm's model picks.
    """

    id = "M0153"

    def __init__(self) -> None:
        self.inner = TREE_RANK_FUND
        self.market_fields: tuple[str, ...] = TREE_RANK_FUND.market_fields

    def _check(self, params: object) -> SubsetParams:
        if not isinstance(params, SubsetParams):
            raise TypeError(f"params must be SubsetParams, got {type(params).__name__}")
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
        """History-only path: no membership, no panel, no model, so no target."""
        self._check(params)
        return ()

    def prepare(self, history: Mapping[str, History]) -> SubsetPrepared:
        return SubsetPrepared(self.inner.prepare(history))

    def prepare_market(self, market: Any) -> SubsetPrepared:
        return SubsetPrepared(
            TreeRankPrepared.build(TreeInputs.from_market(market), self.inner.feature_set),
            MappingProxyType(dict(market.history)),
        )

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = self._check(params)
        if not isinstance(prepared, SubsetPrepared):
            raise TypeError(f"prepared must be SubsetPrepared, got {type(prepared).__name__}")
        if prepared.history is None or prepared.inner.inputs is None:
            return ()
        if not model_ready(data_date, p.tree.train_start, p.tree.min_train_months, p.tree.horizon):
            return _bench(prepared.history, data_date)
        if p.gate and not trend_on(prepared.history, data_date, GATE):
            return ()
        return prepared.targets_on(members, data_date, p)


SUBSET_BOOK = SubsetBook()


class M0153Control(GatedDollarVolumeBook):
    """M0131's gated dollar-volume control on this method's calendar and rule order.

    Same picks as M0131-DV once ready; before the first model it holds SPY ungated, like the arms.
    """

    id = "M0153-DV"

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = self._check(params)
        if not model_ready(data_date, p.train_start, p.min_train_months, p.horizon):
            return self._bench(history, data_date)
        return super().targets(history, members, data_date, held, params)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = self._check(params)
        if not model_ready(data_date, p.train_start, p.min_train_months, p.horizon):
            return self._bench(prepared.history, data_date)
        return super().targets_prepared(prepared, members, data_date, held, params)


DV_BOOK = M0153Control()


def _v(suffix: str, allocator: Any, params: Any, rationale: str) -> Candidate:
    return Candidate(id=f"M0153-{suffix}", family="M0153", rules=MONTHLY_HOLD_FRAC_GOTRADE_TBAND,
                     allocator=allocator, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0153",
    name=(
        "The accounts-only picker, judged where the accounts exist: a learned ranker on the SEC "
        "panel alone, scored on 2012-2015 against the same ranker on price alone"
    ),
    family="stock-fundamental-cross-section",
    source_kind="variation",
    source_ref="variation of M0144 (the market-state ranker); Sera batch 20261016-2004",
    parent_id="M0144",
    hypothesis=(
        "Four levers have been turned on the learned ranker -- capacity, target horizon, memory "
        "and market-state inputs -- and the walk-forward record was 1 or 2 of 4 folds every time. "
        "The binding constraint is the signal set: all seven signals are price and dividend "
        "arithmetic, which every participant has free. The unused asset on disk is the SEC "
        "EDGAR panel (value, quality, profitability, earnings surprise; academic roots in Fama-"
        "French 1992, Novy-Marx 2013 and Bernard-Thomas 1989, so all widely published and likely "
        "crowded by 2010). No ranker was ever registered on it because the panel starts in 2009. "
        "This method learns only where the panel exists and is scored only where its first model "
        "exists. CALENDAR, MEASURED BEFORE THE RUN: the panel describes most index members on "
        "three of four columns from the 2010-03-31 month-end (surprise fills in during 2011), so "
        "training starts there; the 252-session label means the 2011-12-30 refit holds exactly 10 "
        "labelled month-ends, so min_train_months is 10 and every arm starts picking on "
        "2012-01-03, with 22, 34 and 46 months at the next three refits. Before the first model "
        "every arm holds plain SPY ungated, so its curve is the yardstick's own and the dev row "
        "can only differ from SPY in 2012-2015 (the contract test's 473-session smoke market rules "
        "out moving the start through the lookback). FOUR FIXED ARMS on one eleven-column cross-"
        "section, same rows, same labels, B20's tree, gated at the SPY 200-day switch once the "
        "model exists: FUND (the four account columns), PRICE (the seven price columns, the paired "
        "control), ALL (eleven), DV20 (M0131's no-model dollar-volume book on the same calendar). "
        "THE MEASURE, FIXED NOW: the recorded monthly curves, de-funded, sliced 2012-01 .. "
        "2015-10, beside SPY's recorded curve on the same slice. THE IMPROVEMENT BAR, FIXED NOW "
        "AND HONOURED: FUND or ALL beats PRICE by at least 1.0 point a year over that slice AND in "
        "at least 3 of the 4 calendar years 2012, 2013, 2014, 2015-to-October. If it clears, the "
        "accounts carry information the price columns lack and older fundamentals become worth "
        "pricing; if not, the accounts add nothing on top of price even where they exist, and the "
        "fundamentals question is closed as M0144 closed market state. NOT PROMOTABLE BY "
        "CONSTRUCTION: a 1996 curve yields three walk-forward folds where the hard gate needs "
        "four, and only one of them is picked by a model. The whole-window row will fail the "
        "worst-fall screen on SPY's own 2008 fall. This is evidence, bought for one method look."
    ),
    expected_failure=(
        "Most likely the accounts add nothing a year-ahead price ranker does not already have, and "
        "no arm clears the bar. FIRST, the sample is tiny: about 3,500 rows at the first refit and "
        "16,000 at the last, against 57,000 for B20, and 2012-2015 is under four years -- roughly "
        "45 monthly decisions with heavily overlapping labels -- so a 1-point gap is inside the "
        "noise of a single regime. SECOND, 2012-2015 was a steady, low-dispersion large-cap rally "
        "where SPY was hard to beat with any equal-weight 20-name book, so every arm may lose to "
        "SPY and the comparison would be between losers. THIRD, value lost money through most of "
        "the 2010s, and the published quality and profitability premia were crowded by then, so "
        "the account columns may be read and point the wrong way. FOURTH, the price arm is not B20 "
        "but B20 starved of history (M0137 found short memory hurts in a straight line), so even a "
        "FUND win would partly be PRICE being weak, which is why ALL, not FUND, is the arm that "
        "matters. FIFTH, missing filings are not random: a member with no visible filing is "
        "unusual, and the tree may learn the missingness rather than the accounts. SIXTH, the "
        "survivorship hole is smallest in these years, so that at least should not flatter it."
    ),
    candidates=(
        _v("FUND", SUBSET_BOOK, SubsetParams(TREE, FUND_COLS),
           "The four account columns only: value, quality, profitability, earnings surprise"),
        _v("PRICE", SUBSET_BOOK, SubsetParams(TREE, PRICE_COLS),
           "Paired control: the seven price columns only, same rows, same calendar"),
        _v("ALL", SUBSET_BOOK, SubsetParams(TREE, ALL_COLS),
           "All eleven columns: do the accounts add anything on top of price"),
        _v("DV20", DV_BOOK, ControlParams(top_n=20, train_start=PANEL_START,
                                          min_train_months=FIRST_MODEL_MONTHS, horizon=YEAR),
           "Control: the same gated 20-name book picked by trading volume, no model, same calendar"),
    ),
    seen_keys=(
        "concept:fundamentals-learned-ranker",
        "concept:accounts-only-ranker-short-window",
        "concept:fundamentals-vs-price-paired-ranker",
    ),
)

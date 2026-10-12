# Phase 6: Tree-ranker allocator (features, walk-forward model, tests)

**Plan set:** `MEASURE_THEN_LEARN_PLAN.md`
**Analysis:** `20261012-205553-M7T1_code_analyzer.md`
**Satisfies:** R5. This phase builds the allocator that the pre-registered gradient-boosted-tree ranker method (phase 7) runs on.
**Depends on:** none
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/lab` (new module `lab/tree_rank.py`)

---

## Goal

After this phase the engine has a pure, deterministic allocator that learns to rank stocks. Each
month-end it builds a point-in-time feature cross-section from signal code the lab already has
(F4's 12-1 momentum, volatility and dollar volume, M0007's residual momentum, M0015's 52-week-high
nearness, M0070's dividend-raise event, a trailing dividend yield and, optionally, f_fundamental's
four SEC factors). It rank-normalises each feature and refits a fixed-seed
`HistGradientBoostingRegressor` once a year on every sample whose forward-21-session label was
already read. It then holds the top N predictions at equal weight. Nothing reads data dated after
the decision date. The tests prove that: the prepared path equals a from-scratch path built on data
cut at d, and changing anything after d changes nothing.

## Decision: where the module lives

**`engine/src/seer_engine/lab/tree_rank.py`, not `strategies/tree_rank.py`.** Reasons:

1. Three of the features are lab methods' own signal code: `m0007.build_grid`/`residual_scores`,
   `m0015.nearness` and `m0070.live_event`. The scope says to import them, not copy them.
2. Lab methods import `strategies`, never the reverse. The one exception is
   `strategies/evidence.py:313-506`, and it imports lab methods only lazily, inside functions. A
   module-scope import from `strategies/` into `lab.methods` would invert the layering and create
   an import cycle: `lab.methods.m0007 -> backtest.dev:70 -> strategies.allocator`. On top of that,
   `strategies/__init__.py` deliberately keeps scikit-learn out of `import seer_engine.strategies`.
3. There is precedent for reusable pure allocators under `lab/`: `lab/exposure.py` and
   `lab/gate_probe.py`. `lab/name_count.py:56` imports `m0007` at module scope.
4. `tests/test_strategy_purity.py` globs only `strategies/ backtest/ fundamentals/ paper/`. To keep
   purity enforced, `tests/test_tree_rank.py` runs the same AST scan and fresh-interpreter
   import check on `lab/tree_rank.py`. It reuses that test's `FORBIDDEN_*` sets, as
   `test_b_model.py:43` already imports from it, and adds the stricter lab-method extras from
   `test_lab_methods.py:38-41`. Measured on 2026-10-12 with the main checkout's venv: importing
   m0007, m0015, m0070, `sklearn.ensemble` and `threadpoolctl` loads none of `psycopg`,
   `requests`, `yfinance` or `seer_engine.bars`.

## Decisions taken inside this phase (implementer: do not re-litigate)

| Fork | Chosen | Why |
|---|---|---|
| History-only path (`prepare(history)` / `targets(history, ...)`) | **targets nothing**, always `()` | `tests/test_lab_methods.py:93-101` asserts that a `MarketAware` allocator targets nothing on the history-only path (`nonempty == 0`). Phase 7's method will be checked by it automatically. This is the same contract as `f_fundamental` and `m0070`. |
| How "unprepared must be identical" is held | a module function `targets_with_inputs(inputs, members, d, held, params)` rebuilds everything from `inputs.upto(d)` from scratch. Tests assert `targets_prepared(prepare_market(M), ...) == targets_with_inputs(TreeInputs.from_market(M), ...)` | This is the `f_fundamental.targets_with_panel` pattern. The plain `targets()` path cannot be the reference because it has no membership history or calendar. |
| Feature-set switch vs `market_fields` | two allocator objects: `TREE_RANK` (id `"TREE"`, `market_fields=("dividends",)`) and `TREE_RANK_FUND` (id `"TREEF"`, `market_fields=("dividends","fundamentals")`). `params.feature_set` must match the object, otherwise `ValueError` | `lab.runner.market_fields` (`lab/runner.py:305`) reads `market_fields` off the allocator, not the params. With one object, a price-only variant would either wrongly trip the fundamentals coverage gate or a price+fund variant would dodge it. `dev.run_registry` (`backtest/dev.py:661`) refuses two objects that share an id, so the ids differ. |
| Training universe on a past date t | `market.membership.members_on(t)`: point-in-time index membership | Using today's members would be survivorship bias inside the training set. |
| Decision calendar | month-end NYSE sessions (`month_ends`), via `seer_engine.dates` | These are the data dates of a monthly book: `prev_session` of the first session of a month. |
| Label | `rank01` across t's eligible cross-section of `close(last bar <= label_end(t)) / close(t) - 1`. `label_end(t)` is the 21st NYSE session after t. No bar after t means no label. | Calendar-based, so a gap in a symbol's bars can never push a label past d. |
| Refit | anchor = the latest year-end NYSE session on or before d (`anchor_for`). Train on t with `train_start <= t` and `label_end(t) <= anchor`. | Purely a function of d, so it does not depend on call order. The year-end decision itself (rank session = first session of January) gets the fresh model. |
| Minimum history | `min_train_months` labelled month-ends, default **35**. Fewer than that: no model, so cash. | With `train_start=1996-01-31` (the first month-end after `MEMBERSHIP_START` 1996-01-02), the 1998-12-31 refit sees exactly 35 month-ends (Jan 1996 to Nov 1998; November's label is read on 1998-12-30). So 35 is "three years" and the first model trades January 1999. A default of 36 would push the first model to the end of 1999. |
| Residual-momentum variant | M0007-N20-RAW's model: `ResidParams(N20_NOTREND, scaled=False)` | This is the near miss the handover names. The trees see only its rank, and the raw score is the one the lab found strongest. |
| Model digest | `strategies.b_model._tree_digest`, imported (b_model untouched) | It generalises. `b_model.fit_tree` does not (its `TREE_PARAMS` are fixed) and `check_xy` rejects the NaN features this model needs, so those are not reused. |
| `lookback(params)` | `FEATURE_LOOKBACK` = 401 (M0007's residual window), with no warm-up knob | `labkit.smoke_market` has 473 SPY bars (`SMOKE_FIRST` 2013-12-02). Any lookback above 473 makes `dev.candidate_window` raise, which would break `test_lab_methods.test_candidate_runs_a_smoke_window` for phase 7's method. So the dev window can't be delayed to model readiness; the book is cash until the first refit (see Handoffs). The allocatorkit `check_lookback` identity does not hold for a learner (training reads all history since `train_start`). It is vacuous here because the history-only path is `()`. |

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.
**Creates:** (all in `engine/src/seer_engine/lab/tree_rank.py`)
- allocators `TREE_RANK` (`TreeRankAllocator("price")`, id `"TREE"`) and `TREE_RANK_FUND`
  (`TreeRankAllocator("price+fund")`, id `"TREEF"`); class `TreeRankAllocator`
- params `TreeRankParams(top_n=20, feature_set="price", learning_rate=0.05, max_iter=300,
  max_leaf_nodes=15, min_samples_leaf=200, l2=1.0, train_start=date(1996,1,31),
  min_train_months=35, horizon=21, seed=0)` with `as_dict()` and `model_key()`
- `TreeInputs` (history, `members_on`, dividends, panel; `from_market`, `upto`)
- `TreeRankPrepared` (`build`, `section`, `end`, `forward_returns`, `labels`, `training_dates`,
  `training_set`, `model`, `model_on(data_date, params)`, `targets_on`; field `inputs: TreeInputs | None`,
  None on the history-only path `TreeRankAllocator.prepare(history)`, which targets nothing), `Section`, `TreeModel`
- functions `targets_with_inputs`, `month_ends`, `label_end`, `year_end`, `anchor_for`,
  `feature_names`, `rank_columns`, `build_section`, `forward_returns`, `dividend_features`,
  `fundamental_features`, `fit_model`
- constants `SCREEN`, `RESID`, `RAISE_EVENT`, `FUND_STALE_DAYS`, `YIELD_DAYS`, `NAN`, `MAX_TOP`,
  `PRICE_FEATURES`, `FUND_FEATURES`, `FEATURE_LOOKBACK`, `FEATURE_SETS`
- tests `engine/tests/test_tree_rank.py`

**Signature changes:** none.
**Requires (from earlier phases):** none. The allocator is rules-agnostic, and phase 7 pairs it with
phase 3's `monthly-hold-frac-gotrade-tband` preset.
**Leaves alone (owned by others):** `strategies/b.py`, `strategies/b_model.py` (closed Strategy B
record, imported only); `strategies/f_factor.py`, `strategies/f_fundamental.py`,
`lab/methods/m0007_*`, `m0015_*`, `m0070_*` (imported only, never edited); `sim/*` (phases 1-3);
`lab/methods/` new files, `lab/lab.sqlite`, `web/data/lab.json` (phases 5, 7);
`tests/test_strategy_purity.py`, `tests/test_lab_methods.py` (not edited; constants imported).

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/tree_rank.py:1` | create | the whole allocator (Step 2) |
| `engine/tests/test_tree_rank.py:1` | create | contract, identity, no-lookahead, determinism, labels, features, feature-set switch, purity, smoke run (Step 3) |

## Implementation Steps

### Step 1: Worktree venv

**File:** none (environment)
**Change:** the worktree has no `engine/.venv`. Create it, because the main checkout's venv tests
the wrong tree.
```bash
cd /home/miftah/.worktrees/seer/measure-then-learn
python3.11 -m venv engine/.venv && engine/.venv/bin/pip install -e 'engine[dev]'
```
**Impact:** none on the tree.

### Step 2: The allocator module

**File:** `engine/src/seer_engine/lab/tree_rank.py:1` (new)
**Change:** create the file with exactly this content.
**Code:**
```python
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
    """``params``' regressor fitted on (X, y) under a one-thread limit (module docstring, DETERMINISM)."""
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
```
**Impact:** new module, nothing imports it yet. It lives under `lab/` but not under `lab/methods/`, so
`lab.method.discover` (`lab/method.py:37`, `MODULE_NAME` regex over `lab/methods`) does not see
it. `ruff` (E9 and F, minus F401) must be clean: every import above is used.

Notes for the implementer:
- `f_fundamental._row` and `_panel` and `b_model._tree_digest` are private imports, made
  deliberately so the formulas and the digest are not copied. Do not edit those modules.
- Keep the column order of `values` in `build_section` identical to `PRICE_FEATURES` and then
  `FUND_FEATURES`. The tests index columns by `PRICE_FEATURES.index(...)`.

### Step 3: Tests

**File:** `engine/tests/test_tree_rank.py:1` (new)
**Change:** create the file with exactly this content.
**Code:**
```python
"""The tree ranker (lab/tree_rank.py; measure-then-learn phase 6, R5).

Hand-checked calendar and labels; features equal to the lab code they import; point-in-time
training membership; the market path equal to the from-scratch path built on data cut at d; no
look-ahead in bars, dividends or membership; bit-identical refits; the feature-set switch; the
history-only contract (nothing targeted, as test_lab_methods requires of a market-aware
allocator); a smoke run through the dev runner; and the module's purity (test_strategy_purity
does not glob lab/).
"""

from __future__ import annotations

import ast
import math
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from allocatorkit import assert_no_lookahead, assert_p4_identity, assert_valid_targets, everyone
from labkit import SPY_EX_DATE, smoke_market
from stratkit import hist, mutate_from, truncate_before
from test_strategy_purity import (
    FORBIDDEN_ATTRS,
    FORBIDDEN_CALLS,
    FORBIDDEN_IMPORT_ROOTS,
    FORBIDDEN_MODULES,
    _fresh_python,
)

from seer_engine import dates
from seer_engine.backtest.benchmark import Dividend
from seer_engine.backtest.dev import DEV_END, Candidate, run_candidate
from seer_engine.backtest.market import DividendCalendar, Market, Membership
from seer_engine.lab import runner, tree_rank
from seer_engine.lab.methods.m0007_residual_momentum import build_grid, residual_scores
from seer_engine.lab.methods.m0015_52week_high import nearness
from seer_engine.lab.methods.m0070_dividend_raise_drift import live_event
from seer_engine.lab.tree_rank import (
    FEATURE_LOOKBACK,
    PRICE_FEATURES,
    RAISE_EVENT,
    RESID,
    SCREEN,
    TREE_RANK,
    TREE_RANK_FUND,
    TreeInputs,
    TreeRankParams,
    TreeRankPrepared,
    anchor_for,
    fundamental_features,
    label_end,
    month_ends,
    targets_with_inputs,
    year_end,
)
from seer_engine.sim.book import equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import Allocator, MarketAware
from seer_engine.strategies.f_factor import factor_rows

# ---- the synthetic market ---------------------------------------------------------------------

START = date(2009, 1, 2)
END = date(2014, 12, 31)
DAYS = dates.sessions(START, END)  # 1510 sessions
STOCKS: tuple[str, ...] = tuple(f"S{k:02d}" for k in range(10))
LEAVER, LEAVES = "S08", date(2012, 6, 1)  # leaves the index (interval end, exclusive)
JOINER, JOINS = "S09", date(2011, 3, 1)  # joins the index late


def walk(seed: int, drift: float) -> list[float]:
    """A seeded random walk from 80, floored at 10 (close >= $5 and $50M dollar volume always hold)."""
    rng = np.random.default_rng(seed)
    path = 80.0 * np.cumprod(1.0 + rng.normal(drift, 0.015, len(DAYS)))
    return [float(x) for x in np.round(np.maximum(path, 10.0), 2)]


def quarterly(first: int, amounts: list[str]) -> list[tuple[date, Decimal]]:
    """One ex-date every 63 sessions from DAYS[first], one per amount."""
    return [(DAYS[first + 63 * q], Decimal(a)) for q, a in enumerate(amounts)]


DIVS: dict[str, list[tuple[date, Decimal]]] = {
    "S00": quarterly(30, ["0.25"] * 22),
    "S01": quarterly(40, ["0.20"] * 10 + ["0.30"] * 12),  # a 50% raise at the 11th payment
    "S02": quarterly(700, ["0.15"] * 12),  # a first payment in late 2011: an initiation
    "S03": quarterly(20, ["0.40"] * 22),
}


def build_market() -> Market:
    history = {
        s: hist(s, walk(100 + k, 0.0002 * (k % 5) - 0.0003), days=DAYS, volume=5_000_000.0)
        for k, s in enumerate(STOCKS)
    }
    history["SPY"] = hist("SPY", walk(99, 0.0003), days=DAYS, volume=50_000_000.0)
    intervals = tuple(
        (s, DAYS[0], LEAVES if s == LEAVER else None) for s in STOCKS if s != JOINER
    ) + ((JOINER, JOINS, None),)
    return Market(
        history=history,
        membership=Membership(intervals=intervals),
        fx=((DAYS[0], Decimal("15000")),),
        dividends=DividendCalendar(DIVS),
    )


MARKET = build_market()
SMALL = TreeRankParams(
    top_n=3, max_iter=15, max_leaf_nodes=7, min_samples_leaf=5, train_start=date(2010, 2, 1), min_train_months=6
)
WIDE = replace(SMALL, top_n=5, learning_rate=0.1, max_leaf_nodes=5)
FUND = replace(SMALL, feature_set="price+fund")
# 2010-11-30 is before the first model (anchor 2009-12-31: no sample yet); the rest trade.
PROBES: tuple[date, ...] = (
    date(2010, 11, 30),
    date(2010, 12, 31),
    date(2011, 6, 30),
    date(2012, 12, 31),
    date(2013, 3, 14),
    date(2014, 11, 28),
)


def members(d: date) -> frozenset[str]:
    return MARKET.membership.members_on(d)


@pytest.fixture(scope="module")
def prepared() -> TreeRankPrepared:
    return TREE_RANK.prepare_market(MARKET)


# ---- a fake fundamental panel ------------------------------------------------------------------


@dataclass(frozen=True)
class Snap:
    filed: date | None
    net_income: float
    gross_profit: float
    assets: float
    equity: float
    shares_outstanding: float
    sue: float


NAN_SNAP = Snap(None, math.nan, math.nan, math.nan, math.nan, math.nan, math.nan)


class FakePanel:
    """Each symbol's snapshots by filing date; ``as_of`` answers from those filed on or before t."""

    def __init__(self, facts: dict[str, list[Snap]]) -> None:
        self.facts = facts

    def as_of(self, symbol: str, data_date: date) -> Snap | None:
        snaps = self.facts.get(symbol)
        if snaps is None:
            return None
        seen = [s for s in snaps if s.filed is not None and s.filed <= data_date]
        return seen[-1] if seen else NAN_SNAP


PANEL = FakePanel({
    "S01": [
        Snap(date(2011, 3, 1), 1.0e8, 4.0e8, 2.0e9, 1.0e9, 1.0e8, 0.5),
        Snap(date(2012, 3, 1), 1.2e8, 4.4e8, 2.2e9, 1.1e9, 1.0e8, 1.5),
    ],
    "S02": [Snap(date(2010, 3, 1), 5.0e7, 1.0e8, 1.0e9, 5.0e8, 2.0e7, -0.5)],  # stale after 2011-04-05
    "S03": [Snap(date(2012, 1, 15), 2.0e7, 9.0e7, 6.0e8, 3.0e8, 5.0e7, 0.0)],
})
FUND_MARKET = SimpleNamespace(
    history=MARKET.history, membership=MARKET.membership, dividends=MARKET.dividends, fundamentals=PANEL
)


# ---- the fixture itself -----------------------------------------------------------------------


def test_fixture_every_member_is_eligible_on_every_probe(prepared):
    """If a seed ever walks a stock under the screen, change the seed: the tests below assume this."""
    for d in PROBES + (date(2011, 2, 28), date(2011, 3, 31), date(2012, 5, 31), date(2012, 6, 29)):
        assert set(prepared.section(d).symbols) == set(members(d)), d


# ---- params and protocol ----------------------------------------------------------------------


def test_params_defaults_validation_and_as_dict():
    assert TreeRankParams().as_dict() == {
        "top_n": "20",
        "feature_set": "price",
        "learning_rate": "0.05",
        "max_iter": "300",
        "max_leaf_nodes": "15",
        "min_samples_leaf": "200",
        "l2": "1",
        "train_start": "1996-01-31",
        "min_train_months": "35",
        "horizon": "21",
        "seed": "0",
    }
    coerced = TreeRankParams(learning_rate=1, l2=0)
    assert isinstance(coerced.learning_rate, float) and isinstance(coerced.l2, float)
    for bad in (
        dict(top_n=0), dict(top_n=101), dict(feature_set="fund"), dict(learning_rate=0.0),
        dict(learning_rate=1.5), dict(max_iter=0), dict(max_leaf_nodes=1), dict(min_samples_leaf=0),
        dict(l2=-1.0), dict(min_train_months=0), dict(horizon=0), dict(seed=-1),
    ):
        with pytest.raises(ValueError):
            TreeRankParams(**bad)
    with pytest.raises(TypeError):
        TreeRankParams(top_n=True)
    with pytest.raises(TypeError):
        TreeRankParams(train_start=datetime(1996, 1, 31))
    assert replace(SMALL, top_n=9).model_key() == SMALL.model_key()
    assert replace(SMALL, seed=1).model_key() != SMALL.model_key()


def test_two_allocator_objects_and_what_lab_run_reads_off_them():
    for alloc in (TREE_RANK, TREE_RANK_FUND):
        assert isinstance(alloc, Allocator) and isinstance(alloc, MarketAware)
    assert (TREE_RANK.id, TREE_RANK_FUND.id) == ("TREE", "TREEF")
    assert runner.market_fields(TREE_RANK) == ("dividends",)
    assert runner.market_fields(TREE_RANK_FUND) == ("dividends", "fundamentals")
    assert TREE_RANK.lookback(SMALL) == FEATURE_LOOKBACK == 401
    assert TREE_RANK.symbols(SMALL) == ("SPY",)
    assert TREE_RANK.holds(SMALL) == ()
    assert TREE_RANK.uses_members(SMALL) is True
    with pytest.raises(ValueError, match="feature_set"):
        TREE_RANK.lookback(FUND)
    with pytest.raises(ValueError, match="feature_set"):
        TREE_RANK_FUND.lookback(SMALL)
    with pytest.raises(TypeError):
        TREE_RANK.lookback(object())


# ---- the calendar and the labels, by hand ------------------------------------------------------


def test_calendar_is_hand_checked():
    assert month_ends(date(2014, 1, 1), date(2014, 3, 31)) == (date(2014, 1, 31), date(2014, 2, 28), date(2014, 3, 31))
    assert month_ends(date(2014, 1, 31), date(2014, 1, 31)) == (date(2014, 1, 31),)
    assert month_ends(date(2014, 2, 1), date(2014, 2, 27)) == ()
    assert label_end(date(2014, 1, 31), 21) == date(2014, 3, 4)  # 19 February sessions, then Mar 3, 4
    assert label_end(date(2012, 11, 30), 21) == date(2013, 1, 2)  # December 2012 had 20 sessions
    assert label_end(date(2014, 1, 31), 1) == date(2014, 2, 3)
    assert year_end(2010) == date(2010, 12, 31)
    assert year_end(2014) == date(2014, 12, 31)
    assert anchor_for(date(2014, 12, 30)) == date(2013, 12, 31)
    assert anchor_for(date(2014, 12, 31)) == date(2014, 12, 31)
    assert anchor_for(date(2015, 1, 2)) == date(2014, 12, 31)


def test_training_dates_hold_only_labels_read_by_the_refit(prepared):
    anchor = date(2012, 12, 31)
    ts = prepared.training_dates(SMALL, anchor)
    assert ts[0] == date(2010, 2, 26)
    assert ts[-1] == date(2012, 10, 31)  # November's label is read on 2013-01-02, after the refit
    assert all(label_end(t, SMALL.horizon) <= anchor for t in ts)
    assert label_end(date(2012, 11, 30), SMALL.horizon) > anchor


def test_labels_are_the_cross_sectional_rank_of_the_forward_return():
    days = dates.sessions(date(2013, 1, 2), date(2014, 6, 30))
    t = date(2014, 1, 31)
    i0 = days.index(t)
    j = days.index(label_end(t, 21))  # 2014-03-04

    def series(after: float, later: float) -> list[float]:
        before = [50.0 + (0.2 if k % 2 else -0.2) for k in range(i0)]
        return before + [50.0] + [after] * (j - i0) + [later] * (len(days) - j - 1)

    history = {
        "A": hist("A", series(55.0, 70.0), days=days, volume=5e6),
        "B": hist("B", series(50.0, 20.0), days=days, volume=5e6),
        "C": hist("C", series(45.0, 90.0), days=days, volume=5e6),
        "D": hist("D", series(50.0, 50.0)[: i0 + 1], days=days[: i0 + 1], volume=5e6),  # no bar after t
        "SPY": hist("SPY", [100.0 + 0.1 * k for k in range(len(days))], days=days, volume=5e7),
    }
    inputs = TreeInputs(history, lambda d: frozenset({"A", "B", "C", "D"}))
    prep = TreeRankPrepared.build(inputs, "price")
    assert prep.section(t).symbols == ("A", "B", "C", "D")
    rets = prep.forward_returns(t, 21)
    assert rets[0] == pytest.approx(0.10)  # read at the label date, not at the later 70.0
    assert rets[1] == 0.0
    assert rets[2] == pytest.approx(-0.10)
    assert math.isnan(rets[3])
    labels = prep.labels(t, 21)
    assert labels[:3].tolist() == [1.0, 0.5, 0.0]
    assert math.isnan(labels[3])


# ---- features ---------------------------------------------------------------------------------


def test_features_are_the_lab_code_they_import(prepared):
    t = date(2012, 6, 29)
    sec = prepared.section(t)
    rows = factor_rows(MARKET.history, members(t), t, SCREEN)
    assert sec.symbols == tuple(r.symbol for r in rows)
    assert sec.raw.shape == (len(rows), len(PRICE_FEATURES))
    col = {name: sec.raw[:, k] for k, name in enumerate(PRICE_FEATURES)}
    np.testing.assert_array_equal(col["momentum"], [r.momentum for r in rows])
    np.testing.assert_array_equal(col["volatility"], [r.vol for r in rows])
    np.testing.assert_array_equal(col["dollar_volume"], [r.dollar_volume for r in rows])
    scores = residual_scores(build_grid(MARKET.history, "SPY"), list(sec.symbols), t, RESID)
    np.testing.assert_array_equal(col["residual_momentum"], [scores.get(s, math.nan) for s in sec.symbols])
    np.testing.assert_array_equal(col["high_nearness"], [nearness(MARKET.history, s, t, 252) for s in sec.symbols])
    raised = [
        1.0 if live_event(MARKET.dividends.known_on(s, t), DAYS[0], t, RAISE_EVENT) is not None else 0.0
        for s in sec.symbols
    ]
    np.testing.assert_array_equal(col["dividend_raise"], raised)
    yields = []
    for s, close in zip(sec.symbols, sec.close.tolist()):
        paid = sum((a for e, a in MARKET.dividends.known_on(s, t) if e > t - timedelta(days=365)), Decimal(0))
        yields.append(float(paid) / close)
    np.testing.assert_array_equal(col["dividend_yield"], yields)
    for k in range(sec.X.shape[1]):
        finite = np.isfinite(sec.raw[:, k])
        assert (np.isfinite(sec.X[:, k]) == finite).all()
        if finite.any():
            assert sec.X[finite, k].min() >= 0.0 and sec.X[finite, k].max() <= 1.0


def test_the_dividend_event_feature_is_not_vacuous(prepared):
    k = PRICE_FEATURES.index("dividend_raise")
    assert any(1.0 in prepared.section(m).raw[:, k] for m in month_ends(date(2011, 10, 1), date(2012, 3, 31)))


def test_training_universe_is_point_in_time_membership(prepared):
    assert LEAVER in prepared.section(date(2012, 5, 31)).symbols
    assert LEAVER not in prepared.section(date(2012, 6, 29)).symbols
    assert JOINER not in prepared.section(date(2011, 2, 28)).symbols
    assert JOINER in prepared.section(date(2011, 3, 31)).symbols


# ---- the walk-forward model and the book --------------------------------------------------------


def test_no_model_before_enough_months_means_cash(prepared):
    early = date(2010, 12, 30)
    assert prepared.model_on(early, SMALL) is None  # its refit is 2009-12-31: no sample yet
    assert TREE_RANK.targets_prepared(prepared, members(early), early, frozenset(), SMALL) == ()
    model = prepared.model_on(date(2010, 12, 31), SMALL)
    assert model is not None
    assert (model.anchor, model.months, model.n_features) == (date(2010, 12, 31), 10, 7)  # Feb..Nov 2010
    strict = replace(SMALL, min_train_months=11)
    assert prepared.model_on(date(2010, 12, 31), strict) is None
    assert prepared.model_on(date(2011, 12, 30), strict) is not None


def test_targets_are_the_top_n_predictions_at_equal_weight(prepared):
    d = date(2013, 7, 31)
    got = TREE_RANK.targets_prepared(prepared, members(d), d, frozenset(), SMALL)
    sec = prepared.section(d, members(d))
    pred = prepared.model_on(d, SMALL).predict(sec.X)
    order = sorted(range(len(sec.symbols)), key=lambda k: (-pred[k], sec.symbols[k]))[: SMALL.top_n]
    assert [t.symbol for t in got] == [sec.symbols[k] for k in order]
    assert all(t.weight == equal_weight(3) for t in got)
    assert_valid_targets(got, MARKET.history, d, frozenset())


def test_market_path_equals_the_from_scratch_path(prepared):
    inputs = TreeInputs.from_market(MARKET)
    nonempty = 0
    for d in PROBES:
        for held in (frozenset(), frozenset({"S01"})):
            for p in (SMALL, WIDE):
                got = TREE_RANK.targets_prepared(prepared, members(d), d, held, p)
                assert got == targets_with_inputs(inputs, members(d), d, held, p), (d, held, p)
                assert_valid_targets(got, MARKET.history, d, held)
                nonempty += bool(got)
    assert nonempty == 4 * (len(PROBES) - 1)


def test_bars_dividends_and_membership_after_d_change_nothing(prepared):
    nonempty = 0
    for d in PROBES[1:]:
        s = dates.next_session(d)
        divs = {k: list(v) for k, v in DIVS.items()}
        divs["S04"] = [(s, Decimal("5.00"))]
        divs["S01"] = [x for x in divs["S01"] if x[0] < s] + [(dates.next_session(s), Decimal("9.99"))]
        intervals = tuple((sym, a, s if sym == "S07" else b) for sym, a, b in MARKET.membership.intervals)
        futures = (
            Market(
                history={k: mutate_from(h, s) for k, h in MARKET.history.items()},
                membership=Membership(intervals=intervals),
                fx=MARKET.fx,
                dividends=DividendCalendar(divs),
            ),
            Market(
                history={k: truncate_before(h, s) for k, h in MARKET.history.items()},
                membership=MARKET.membership,
                fx=MARKET.fx,
                dividends=MARKET.dividends,
            ),
        )
        before = TREE_RANK.targets_prepared(prepared, members(d), d, frozenset(), SMALL)
        for future in futures:
            after = TREE_RANK.targets_prepared(TREE_RANK.prepare_market(future), members(d), d, frozenset(), SMALL)
            assert after == before, (d, s)
        nonempty += bool(before)
    assert nonempty == len(PROBES) - 1


def test_two_prepares_fit_bit_identical_models():
    a = TREE_RANK.prepare_market(MARKET)
    b = TREE_RANK.prepare_market(MARKET)
    for year in (2010, 2011, 2012, 2013):
        ma = a.model(SMALL, year_end(year))
        mb = b.model(SMALL, year_end(year))
        assert ma is not None and ma == mb and ma.digest == mb.digest and len(ma.digest) == 64
    for d in PROBES:
        assert TREE_RANK.targets_prepared(a, members(d), d, frozenset(), SMALL) == TREE_RANK.targets_prepared(
            b, members(d), d, frozenset(), SMALL
        )
    anchor = year_end(2012)
    assert a.model(replace(SMALL, top_n=9), anchor) is a.model(SMALL, anchor)  # book size shares the fit
    assert a.model(replace(SMALL, learning_rate=0.2), anchor).digest != a.model(SMALL, anchor).digest


# ---- the feature-set switch ---------------------------------------------------------------------


def test_feature_set_switch_adds_the_four_fundamental_columns(prepared):
    fund = TREE_RANK_FUND.prepare_market(FUND_MARKET)
    t = date(2012, 6, 29)
    a, b = prepared.section(t), fund.section(t)
    assert a.symbols == b.symbols
    assert b.raw.shape == (len(b.symbols), 11)
    np.testing.assert_array_equal(b.raw[:, :7], a.raw)
    k = b.symbols.index("S01")
    close = float(b.close[k])
    assert b.raw[k, 7:].tolist() == [1.1e9 / (1.0e8 * close), 1.2e8 / 1.1e9, 4.4e8 / 2.2e9, 1.5]
    assert np.isnan(b.raw[b.symbols.index("S02"), 7:]).all()  # filed 2010-03-01: older than 400 days
    assert np.isnan(b.raw[b.symbols.index("S00"), 7:]).all()  # never filed
    assert fund.model(FUND, year_end(2012)).n_features == 11
    assert prepared.model(SMALL, year_end(2012)).n_features == 7
    with pytest.raises(ValueError, match="feature_set"):
        TREE_RANK.targets_prepared(prepared, members(t), t, frozenset(), FUND)
    with pytest.raises(ValueError, match="feature_set"):
        TREE_RANK_FUND.targets_prepared(fund, members(t), t, frozenset(), SMALL)
    d = date(2013, 7, 31)
    got = TREE_RANK_FUND.targets_prepared(fund, members(d), d, frozenset(), FUND)
    assert got
    assert got == targets_with_inputs(TreeInputs.from_market(FUND_MARKET), members(d), d, frozenset(), FUND)


def test_a_filing_dated_after_t_is_never_read():
    class Liar:
        def as_of(self, symbol: str, data_date: date) -> Snap:
            return Snap(data_date + timedelta(days=1), 1.0, 1.0, 1.0, 1.0, 1.0, 1.0)

    assert all(math.isnan(x) for x in fundamental_features(Liar(), "S01", date(2012, 6, 29), 50.0, 1e8))


# ---- the history-only contract and the dev runner ---------------------------------------------


def test_history_only_path_targets_nothing():
    """test_lab_methods.test_allocator_contract requires exactly this of a market-aware allocator."""
    stocks = everyone({s: MARKET.history[s] for s in STOCKS})
    probe = [dates.next_session(d) for d in PROBES[1:]]
    assert assert_p4_identity(TREE_RANK, MARKET.history, stocks, PROBES, [frozenset()], [SMALL]) == 0
    assert assert_no_lookahead(TREE_RANK, MARKET.history, stocks, probe, [frozenset()], [SMALL]) == 0


def test_a_candidate_runs_the_lab_smoke_window():
    """The shape phase 7's method will have, through the same runner test_lab_methods uses."""
    params = TreeRankParams()
    market = smoke_market(TREE_RANK.symbols(params))
    c = Candidate(
        id="M9999-SMOKE",
        family="M9999",  # a lab-method-shaped family; phase 7 uses its real id
        rules=MONTHLY_HOLD_FRAC_GOTRADE,
        allocator=TREE_RANK,
        params=params,
        rationale="smoke: the tree ranker through the dev runner",
        added=date(2026, 10, 12),
        owner_inputs=(),
    )
    amount = Decimal("1.0300")
    result, row = run_candidate(market, {"SPY": {SPY_EX_DATE: amount}}, (Dividend(SPY_EX_DATE, amount),), c)
    assert row.end == DEV_END
    assert len(result.snapshots) >= 2


# ---- purity (tests/test_strategy_purity.py does not glob lab/) ---------------------------------

LAB_IMPORT_ROOTS = FORBIDDEN_IMPORT_ROOTS | {"os", "subprocess", "sqlite3"}  # test_lab_methods' extras
LAB_CALLS = FORBIDDEN_CALLS | {"eval", "exec"}


def test_tree_rank_source_has_no_clock_randomness_or_io():
    path = Path(tree_rank.__file__)
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    problems: list[str] = []
    for node in ast.walk(tree):
        where = f"{path.name}:{getattr(node, 'lineno', '?')}"
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in LAB_IMPORT_ROOTS or alias.name == "seer_engine.bars":
                    problems.append(f"{where} import {alias.name}")
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module.split(".")[0] in LAB_IMPORT_ROOTS or node.module in (
                "seer_engine.bars", "seer_engine.research", "seer_engine.lab.store"
            ):
                problems.append(f"{where} from {node.module} import ...")
        elif isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_ATTRS:
            problems.append(f"{where} .{node.attr}")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in LAB_CALLS:
            problems.append(f"{where} {node.func.id}()")
    assert problems == []


def test_tree_rank_loads_no_db_or_network_module():
    code = (
        "import importlib, sys\n"
        "importlib.import_module('seer_engine.lab.tree_rank')\n"
        f"bad = [m for m in {FORBIDDEN_MODULES!r} if m in sys.modules]\n"
        "print(','.join(bad))\n"
    )
    assert _fresh_python(code) == ""
```
**Impact:** about 20 new tests. Runtime estimate: the identity test makes 24 from-scratch builds,
each fitting one 15-iteration model on at most about 500 rows. The no-lookahead test makes 10
fresh prepares. The whole module should take well under a minute serially.

Implementer notes:
- **Seeds.** `test_fixture_every_member_is_eligible_on_every_probe` guards the fixture. If a seed
  walks a stock under the screen (volatility 0 from a long floor stretch, which is unlikely at the
  10 floor), change that stock's seed in `walk(100 + k, ...)`. Do not loosen an assertion.
- **`model.months == 10`** follows from `train_start=2010-02-01`: the first eligible month-end is
  2010-02-26 (253 bars from 2009-01-02 is 2010-01-04), and the 2010-11-30 label is read on
  2010-12-30. If the fixture eligibility test passes, this holds.
- **`test_history_only_path_targets_nothing`** calls `assert_p4_identity` with the default
  `check_lookback=True`. It holds because every result is `()`, exactly as `test_lab_methods`
  drives it.
- If `_fresh_python` import from `test_strategy_purity` misbehaves under xdist, copy its eight
  lines into this module instead. `test_b_model.py:43` already imports from it, so it should not.

## Verification

**Build:** `engine/.venv/bin/python -c "import seer_engine.lab.tree_rank"` and `engine/.venv/bin/ruff check engine`
**Tests:**
```bash
cd /home/miftah/.worktrees/seer/measure-then-learn
engine/.venv/bin/pytest engine/tests/test_tree_rank.py -n0 -q
engine/.venv/bin/pytest engine/tests/test_strategy_purity.py engine/tests/test_lab_methods.py engine/tests/test_b_model.py -q
export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres   # DB tests must not skip
engine/.venv/bin/pytest engine/tests
```
**Manual check (performance, no lab data written):** time the real dev store end to end.
`SEER_RESEARCH_STORE` is only read here and nothing is recorded.
```bash
cd /home/miftah/.worktrees/seer/measure-then-learn
engine/.venv/bin/python - <<'EOF'
import time
from pathlib import Path
from seer_engine import research
from seer_engine.lab.tree_rank import TREE_RANK, TreeRankParams, month_ends, year_end
from datetime import date
data = research.load_store(Path("/home/miftah/seer/engine/.research"))
t0 = time.perf_counter()
prep = TREE_RANK.prepare_market(data.market)
p = TreeRankParams()
n = 0
for d in month_ends(date(1996, 1, 31), date(2015, 9, 30)):
    n += bool(TREE_RANK.targets_prepared(prep, data.market.membership.members_on(d), d, frozenset(), p))
print("months with a book:", n, "seconds:", round(time.perf_counter() - t0, 1))
print({y: prep.model(p, year_end(y)).rows for y in (1998, 2005, 2014)})
EOF
```
Measured during planning (2026-10-12, the plan's code run from a scratch copy against the main
checkout's dev store): store load 13 s, `prepare_market` 0.2 s, 202 month-ends with a book (the first
is 1998-12-31), every fit and section for 1996-2015 in 9.0 s on one fit thread, and a second variant
differing only in `top_n` in 1.6 s (shared fits). Refit sizes: 1998 has 3,898 rows over 35 months,
2005 has 20,994 rows over 119, and 2014 has 57,291 rows over 227. Expect numbers of this order. Record the time in the phase-7 handoff note. If it is much slower, profile
`build_section`: `fundamental_features` is only on the `price+fund` object, so the slow part on
`TREE_RANK` would be `nearness`/`live_event` in Python. Cache by (t), not by params. The fit is
single-threaded by design, and parallelism belongs across variants, not inside a fit.
**Exit criteria:** `test_tree_rank.py` is green, including the market-path identity (prepared ==
from scratch, 20 non-empty cases), no-lookahead (bars, dividends and membership after d changed or
deleted: identical targets), determinism (two prepares give equal digests for four refit years),
labels hand-checked (`[1.0, 0.5, 0.0, NaN]`), the feature-set switch (7 vs 11 columns, fundamental
values hand-checked), the history-only contract (0 non-empty) and purity. `ruff check engine` is
clean and the full engine suite is green with `PG_TEST_URL` set.

## Handoffs

- **Phase 7 (R5): the method file.** Import `TREE_RANK` (and `TREE_RANK_FUND` only if you accept
  its gate, see below) and `TreeRankParams` from `seer_engine.lab.tree_rank`. Use phase 3's
  `monthly-hold-frac-gotrade-tband` rules. At most 6 variants, all in the committed file, because
  every hyperparameter setting counts toward N. `test_lab_methods` will apply the history-only
  contract and the smoke run to them automatically, and both are already proven here.
- **Phase 7: the fundamentals coverage gate.** `TREE_RANK_FUND.market_fields` includes
  `"fundamentals"`, so `lab.runner.preflight_data` measures panel coverage over 1996-2015 against
  `MIN_DEV_COVERAGE = 0.80`. The dev store's `fundamentals.csv` begins in 2009 (XBRL), so a
  `price+fund` variant will very likely be refused unless `--allow-coverage` is passed. That is an
  acknowledgement the method's notes must explain. The simplest honest choice is price-only
  variants. This phase deliberately does not bypass the gate.
- **Phase 7: cash before the first refit.** With `train_start=1996-01-31` and
  `min_train_months=35`, the first model is the 1998-12-31 refit, so the book is cash from the dev
  window's opening (early 1996, set by `MEMBERSHIP_START` and the 401-bar lookback) to January
  1999. That drags against SPY's 1996-98 run. The window cannot be delayed through `lookback`:
  `labkit.smoke_market` has 473 SPY bars, so any lookback above 473 breaks `test_lab_methods`'
  smoke run. If phase 7 wants less cash, a smaller `min_train_months` (for example 11, so the
  first model is the 1996-12-31 refit) is a pre-registered variant and counts toward N. Say so in
  the method's `expected_failure`.
- **Phase 7: `seed` is inert** below 200,000 training rows (measured: 57,291 rows at the 2014 refit).
  Do not spend a variant on it.
- **Phase 7: kinship.** `lab/hardgate.py`'s behavioural-kin checks may treat the ranker as kin of
  the residual-momentum family, because it reads M0007's signal. Whatever they say is phase 7's to
  report, not this phase's.
- **Completion handler:** the engine `package_readme.md` (if one covers `lab/`) should gain one
  line for `lab/tree_rank.py`. This phase writes no docs beyond its docstrings.
- **Known limitation (documented, not fixed):** labels exist only for symbols whose bars continue
  after t. The store serves 539 of 1061 ever-members, so the training set inherits the store's
  survivorship. Phase 4's survivorship check is the place this gets measured for the method.

## Rollback

Delete `engine/src/seer_engine/lab/tree_rank.py` and `engine/tests/test_tree_rank.py` (or revert
the phase's commit). Nothing else imports them until phase 7, and no lab row, digest, preset or
web file is touched.

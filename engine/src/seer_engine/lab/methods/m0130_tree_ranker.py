"""M0130 — A learned stock ranker: gradient-boosted trees combine the lab's own signals.

Source: Gu, Kelly & Xiu (2020), "Empirical Asset Pricing via Machine Learning", Review of
Financial Studies 33(5). Handover 2026-10-12 ("measure then learn"), Step 1, item 5.

Idea: every method in the lab so far ranks on ONE hand-chosen signal. This one lets a
gradient-boosted tree learn, walk-forward and point in time, how to combine signals the lab
already computes: 12-1 momentum, volatility, dollar volume, M0007's residual momentum, the
52-week-high distance, M0070's dividend-raise event, the trailing dividend yield and, in one
variant, the four SEC EDGAR factors. Gu, Kelly & Xiu found trees beat linear ranking, but mostly
in small caps and long-short before costs. This is the large-cap, long-only, real-fee test of
whether any of that survives.

THE MODEL is phase 6's ``lab.tree_rank`` allocator, unchanged: ``HistGradientBoostingRegressor``
refitted once a year (at each year's last session) on every month-end sample since 1996-01-31
whose forward 21-session return rank was already known, with features rank-normalised per date.
It holds the top N predictions at equal weight. Nothing dated after the decision date is read.

THE WRAPPER (``TreeBook``) adds two pre-registered rules around it and nothing else:

    * **Before the first model, hold SPY.** The first refit with enough history (35 labelled
      month-ends) is 1998-12-31, and a member book's dev window opens in early 1996. Three years
      of cash during SPY's 1996-98 run would decide "beats SPY" by a data-availability artefact.
      Holding the yardstick while there is nothing to learn from is neutral against it, and is
      identical in every variant, so each paired difference is the model alone. "Is there a
      model on d" is the calendar rule ``model_ready``, shared with the control, so both kinds of
      variant switch on the same session.
    * **An optional SPY 200-day switch** (``gate``), the lab's standing constant
      (``m0007.N20``'s trend), for the one variant that asks whether the model plus the lab's
      usual safety rule can keep the 2008 fall inside 20%.

THE CONTROL (``DollarVolumeBook``) is the same book without the model: the 20 screen-eligible
members (the tree's own screen, ``tree_rank.SCREEN``) with the largest 20-day dollar volume,
equal weight, on the same 401-bar lookback, the same SPY-before-the-model rule and the same
rules. It ranks on size of trading, which forecasts nothing, so tree minus control is what the
model's picking adds over the shape of the book. It is deliberately NOT a momentum book: the hard
gate's behavioural kin test (``lab/hardgate.py`` D14) reads every dev variant of a method, and one
momentum variant correlating with the test-failed momentum books would make every tree variant
here unpromotable.

THE SIX VARIANTS are the only hyperparameter settings this lab ever tries for this idea. Every
one of them counts, and none was chosen by looking at dev results. The base tree is Strategy B's
pre-registered ``TREE_PARAMS`` (``strategies/b_model.py``, fixed 2026-10-03 for a different book).
The regularised tree is a fixed alternative with fewer, shallower, fatter-leaved trees.

Pure: no clock, randomness, files, network or printing. Reads only data dated <= data_date.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20
from seer_engine.lab.tree_rank import (
    FEATURE_LOOKBACK,
    SCREEN,
    TREE_RANK,
    TREE_RANK_FUND,
    TreeRankAllocator,
    TreeRankParams,
    anchor_for,
    label_end,
    month_ends,
)
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE_TBAND
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    FactorPrepared,
    factor_lookback,
    factor_rows,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 10, 12)
BENCH = "SPY"  # held before the first model, and the gate's instrument
GATE = N20  # the lab's standing SPY 200-day switch (F4-MOM12-N20-TREND's), read only for its trend
BASE = TreeRankParams()  # Strategy B's pre-registered tree: lr 0.05, 300 iters, 15 leaves, 200/leaf, L2 1
REG = TreeRankParams(
    top_n=50, learning_rate=0.05, max_iter=100, max_leaf_nodes=7, min_samples_leaf=1000, l2=10.0
)


def model_ready(data_date: date, train_start: date, min_train_months: int, horizon: int) -> bool:
    """Is there a model to decide on ``data_date``? The calendar half of ``tree_rank``'s rule.

    The model deciding on d is the one refitted at ``anchor_for(d)``. It exists when at least
    ``min_train_months`` month-ends from ``train_start`` on had their label read by the anchor.
    Calendar only, so the control (which has no model) switches on the same session as the trees.
    """
    anchor = anchor_for(data_date)
    if anchor < train_start:
        return False
    ends = month_ends(train_start, anchor)
    if len(ends) < min_train_months:
        return False
    labelled = sum(1 for t in ends if label_end(t, horizon) <= anchor)
    return labelled >= min_train_months


def _bench(history: Mapping[str, History], data_date: date) -> tuple[Target, ...]:
    """SPY at full weight, priced at d's close; nothing when SPY has no bar dated d."""
    h = history.get(BENCH)
    if h is None or h.index_of(data_date) is None:
        return ()
    t = target_from_close(BENCH, last_close(h, data_date), equal_weight(1))
    return () if t is None else (t,)


# --------------------------------------------------------------------------- the tree book


@dataclass(frozen=True, slots=True)
class BookParams:
    """The tree's own params, and whether the SPY 200-day switch stands in front of it."""

    tree: TreeRankParams
    gate: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.tree, TreeRankParams):
            raise TypeError(f"tree must be TreeRankParams, got {type(self.tree).__name__}")
        if not isinstance(self.gate, bool):
            raise TypeError(f"gate must be a bool, got {type(self.gate).__name__}")

    def as_dict(self) -> dict[str, str]:
        out = dict(self.tree.as_dict())
        out["gate"] = "SPY:200" if self.gate else "none"
        return out


@dataclass(frozen=True, slots=True, eq=False)
class TreeBookPrepared:
    """The inner tree's prepared value, and the bars the SPY fill and the gate read.

    ``history`` is None on the history-only path, which by the market-aware contract targets
    nothing (tests/test_lab_methods.py).
    """

    inner: Any
    history: Mapping[str, History] | None


class TreeBook:
    """Phase 6's tree ranker, SPY before its first model, optionally behind the SPY 200-day switch."""

    def __init__(self, inner: TreeRankAllocator, ident: str) -> None:
        self.inner = inner
        self.id = ident
        # What `lab run` gates on (runner.market_fields): exactly the inner tree's fields.
        self.market_fields: tuple[str, ...] = tuple(inner.market_fields)

    def _check(self, params: object) -> BookParams:
        if not isinstance(params, BookParams):
            raise TypeError(f"params must be BookParams, got {type(params).__name__}")
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
        """History-only path: no membership history, no calendar, no model, so no target."""
        self._check(params)
        return ()

    def prepare(self, history: Mapping[str, History]) -> TreeBookPrepared:
        return TreeBookPrepared(self.inner.prepare(history), None)

    def prepare_market(self, market: Any) -> TreeBookPrepared:
        return TreeBookPrepared(self.inner.prepare_market(market), MappingProxyType(dict(market.history)))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = self._check(params)
        if not isinstance(prepared, TreeBookPrepared):
            raise TypeError(f"prepared must be TreeBookPrepared, got {type(prepared).__name__}")
        if prepared.history is None:
            return ()
        if p.gate and not trend_on(prepared.history, data_date, GATE):
            return ()
        if not model_ready(data_date, p.tree.train_start, p.tree.min_train_months, p.tree.horizon):
            return _bench(prepared.history, data_date)
        return self.inner.targets_prepared(prepared.inner, members, data_date, held, p.tree)


TREE_BOOK = TreeBook(TREE_RANK, "M0130")
TREE_BOOK_FUND = TreeBook(TREE_RANK_FUND, "M0130-F")


# --------------------------------------------------------------------------- the control


@dataclass(frozen=True, slots=True)
class ControlParams:
    """The control's book size, and the tree clock it shares (defaults: the tree's own)."""

    top_n: int = BASE.top_n
    train_start: date = BASE.train_start
    min_train_months: int = BASE.min_train_months
    horizon: int = BASE.horizon

    def __post_init__(self) -> None:
        for name in ("top_n", "min_train_months", "horizon"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int):
                raise TypeError(f"{name} must be an int, got {type(v).__name__}")
            if v < 1:
                raise ValueError(f"{name} must be >= 1, got {v}")
        if self.top_n > 100:
            raise ValueError(f"top_n must be <= 100, got {self.top_n}")
        if not isinstance(self.train_start, date):
            raise TypeError(f"train_start must be a date, got {type(self.train_start).__name__}")

    def as_dict(self) -> dict[str, str]:
        return {
            "top_n": str(self.top_n),
            "train_start": self.train_start.isoformat(),
            "min_train_months": str(self.min_train_months),
            "horizon": str(self.horizon),
        }


@dataclass(frozen=True, slots=True, eq=False)
class ControlPrepared:
    history: Mapping[str, History]
    factor: FactorPrepared


class DollarVolumeBook:
    """The tree book's shape without the model: the most-traded eligible members, equal weight."""

    id = "M0130-DV"

    def _check(self, params: object) -> ControlParams:
        if not isinstance(params, ControlParams):
            raise TypeError(f"params must be ControlParams, got {type(params).__name__}")
        return params

    def lookback(self, params: Any) -> int:
        self._check(params)
        return FEATURE_LOOKBACK  # the trees' window, so all six variants score the same sessions

    def symbols(self, params: Any) -> tuple[str, ...]:
        self._check(params)
        return (BENCH,)

    def holds(self, params: Any) -> tuple[str, ...]:
        self._check(params)
        return (BENCH,)

    def uses_members(self, params: Any) -> bool:
        self._check(params)
        return True

    def _pick(self, rows: list[Any], p: ControlParams) -> tuple[Target, ...]:
        chosen = sorted(rows, key=lambda r: (-r.dollar_volume, r.symbol))[: p.top_n]
        w = equal_weight(p.top_n)
        out: list[Target] = []
        for row in chosen:
            t = target_from_close(row.symbol, row.close, w)
            if t is not None:
                out.append(t)
        return tuple(out)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = self._check(params)
        if not model_ready(data_date, p.train_start, p.min_train_months, p.horizon):
            return _bench(history, data_date)
        return self._pick(factor_rows(history, members, data_date, SCREEN), p)

    def prepare(self, history: Mapping[str, History]) -> ControlPrepared:
        return ControlPrepared(MappingProxyType(dict(history)), prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = self._check(params)
        if not isinstance(prepared, ControlPrepared):
            raise TypeError(f"prepared must be ControlPrepared, got {type(prepared).__name__}")
        if not model_ready(data_date, p.train_start, p.min_train_months, p.horizon):
            return _bench(prepared.history, data_date)
        return self._pick(prepared.factor.rows_on(members, data_date, SCREEN), p)


DV_BOOK = DollarVolumeBook()


# --------------------------------------------------------------------------- the method


def _v(suffix: str, allocator: Any, params: Any, rationale: str) -> Candidate:
    return Candidate(id=f"M0130-{suffix}", family="M0130", rules=MONTHLY_HOLD_FRAC_GOTRADE_TBAND,
                     allocator=allocator, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0130",
    name="A learned stock ranker: gradient-boosted trees combine the lab's own signals, refitted once a year",
    family="stock-ml-ranker",
    source_kind="paper",
    source_ref=(
        "Gu, Kelly & Xiu (2020), Empirical Asset Pricing via Machine Learning, Review of Financial "
        "Studies 33(5); handover 2026-10-12 (measure then learn), Step 1 item 5"
    ),
    parent_id=None,
    hypothesis=(
        "Every method in this lab ranks on one hand-chosen signal, and the closest near misses all "
        "lean on the same one, residual momentum. Gu, Kelly & Xiu (2020) found that regression trees "
        "combining many such signals rank US stocks better than any linear combination. This method "
        "asks whether a small part of that survives where this lab has to live: large-cap index "
        "members, long only, monthly, Gotrade's real fees, fractional shares, the owner's 5,000,000 "
        "IDR monthly deposits, and a resize band measured against each holding's own target. THE "
        "MODEL: scikit-learn's histogram gradient-boosted trees, refitted once a year at the last "
        "session of each year on every month-end sample since January 1996 whose next-21-session "
        "return rank was already known by then (an expanding window, nothing read after the "
        "decision date). Seven features the lab already computes, each rank-normalised per date: "
        "12-1 momentum, 60-day volatility, 20-day dollar volume, M0007-N20-RAW's residual momentum, "
        "distance from the 52-week high, M0070's dividend-raise event and the trailing dividend "
        "yield; the PF20 variant adds the four SEC EDGAR factors (value, quality, profitability, "
        "earnings surprise). The book holds the top N predictions at equal weight. The first "
        "refit with enough history (35 labelled month-ends) is 1998-12-31; until then every "
        "variant, the control included, holds SPY, so 1996-1998 is the same in all six and every "
        "paired difference below is the model alone. SIX VARIANTS, THE ONLY SETTINGS EVER TRIED: no "
        "hyperparameter was tuned on the dev window off the books, and none will be; a change after "
        "a result is a new method. The base tree is Strategy B's pre-registered setting (learning "
        "rate 0.05, 300 trees, 15 leaves, at least 200 samples per leaf, L2 1.0), fixed on "
        "2026-10-03 for a different book and never searched; the regularised tree (100 trees, 7 "
        "leaves, 1,000 per leaf, L2 10) is the one fixed alternative. The seed is 0 and is inert at "
        "this sample size. P20 and P50 hold the top 20 and top 50; P50-REG is the regularised tree "
        "at 50; P20-GATE is P20 behind the lab's standing SPY 200-day switch; PF20 is P20 with the "
        "fundamentals; DV20 is the CONTROL, the same 20-name equal-weight book on the same screen, "
        "window and SPY-before-the-model rule, picked by 20-day dollar volume, which forecasts "
        "nothing. The control is deliberately not a momentum book: the hard gate reads every "
        "variant's behaviour, and one momentum variant moving with the four test-failed momentum "
        "books would bar every tree variant from promotion. The comparison with momentum is made in "
        "the analysis against the lab's recorded real-fee momentum books instead. FUNDAMENTALS: the "
        "store's EDGAR panel can rank 20 names on only 31.5% of the dev window (none of 1996-2008, "
        "5 of 12 months of 2009, all of 2010-2015), so the run is recorded under --allow-coverage "
        "0.31, knowingly; before 2009 the four columns are empty and PF20 should pick what P20 "
        "picks, so PF20 minus P20 measures the fundamentals in 2010-2015 only. WHAT COUNTS AS THE "
        "MODEL ADDING SOMETHING, fixed now: P20 beats DV20 by at least 2 points a year of funded "
        "return over 1999-2015 AND is ahead of it in 2009-2015, the era most like today. WHAT COUNTS "
        "AS A METHOD: a variant clears every design section 1 bar at DSR >= 0.90 at the lab's N, "
        "including the worst fall <= 20%, which only P20-GATE is built to have a chance at. No "
        "variant is promoted in this run, whatever it shows: the test window is not touched."
    ),
    expected_failure=(
        "Most likely the model adds nothing measurable over the dollar-volume control after fees. "
        "Gu, Kelly & Xiu's edge is concentrated in small and illiquid stocks and in the short leg, "
        "and is measured before costs; this universe is the S&P 500 union the Nasdaq-100 above $20M "
        "a day, long only, and a 20-to-50-name book re-picked monthly pays Gotrade's minimum fees on "
        "$29-70 slots. The paper was published in 2020 but its inputs (momentum and its cousins) "
        "were published long before the dev window ended, so any dev edge is the pre-crowd edge and "
        "likely to fade. Second, the trees will probably learn mostly momentum: residual momentum "
        "and 12-1 momentum are the strongest inputs, so the picks may move with the lab's "
        "test-failed momentum books closely enough that the hard gate reads them as kin, which would "
        "be the right verdict on a model that only re-discovered momentum. Third, every ungated "
        "variant will fall far more than 20% in 2008 -- a fully invested 20-name book fell 50-60% in "
        "every lab precedent -- and the monthly-read SPY switch in P20-GATE reacted late in 2008 "
        "for every lab book that used it, so even the gated variant is likely to miss the 20% bar, "
        "as M0007-N20-RAW did once the missing dead companies were added back (19.6% on the dev "
        "store, 23.5% on the survivorship-check store). Fourth, the training set inherits the "
        "store's survivorship: about half of all index members ever listed are missing, mostly the "
        "ones that died, so the model learns from winners' histories and the survivorship check is "
        "expected to cost it more than the 1-1.4 points a year it cost the hand-built momentum "
        "books. Fifth, PF20 is expected to differ from P20 by noise: the fundamentals enter "
        "training only from late 2009 and are a small slice of every refit's history even by 2014. "
        "Sixth, the regularised tree is expected to sit between the base tree and the control, and "
        "P50 to trail P20 on fees. Finally, twenty years of monthly cross-sections is a small "
        "sample for a learner: about 57,000 training rows by 2014, heavily correlated within each "
        "month, so a DSR at the lab's N may not separate a real ranking skill from luck even if the "
        "returns look good."
    ),
    candidates=(
        _v("P20", TREE_BOOK, BookParams(BASE),
           "The base tree on the seven price and dividend features, top 20, equal weight"),
        _v("P50", TREE_BOOK, BookParams(TreeRankParams(top_n=50)),
           "The same base tree holding its top 50"),
        _v("P50-REG", TREE_BOOK, BookParams(REG),
           "A more regularised tree (100 trees, 7 leaves, 1000 per leaf, L2 10), top 50"),
        _v("P20-GATE", TREE_BOOK, BookParams(BASE, gate=True),
           "The base tree's top 20 behind the lab's standing SPY 200-day switch"),
        _v("PF20", TREE_BOOK_FUND, BookParams(TreeRankParams(feature_set="price+fund")),
           "The base tree's top 20 with the four SEC fundamentals added (they exist from 2009 only)"),
        _v("DV20", DV_BOOK, ControlParams(),
           "Control: the same 20-name book picked by trading volume, no model"),
    ),
    seen_keys=(
        "concept:gradient-boosted-tree-ranker",
        "concept:ml-cross-sectional-ranker",
        "concept:walk-forward-annual-refit",
        "concept:learned-signal-combination",
    ),
)

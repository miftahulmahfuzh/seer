"""M0131 — A slower target for the learned ranker: next year's return rank, not next month's.

Source: variation of M0130 (the first learned ranker), which is this method's parent. The model
class, the features, the walk-forward calendar and the measuring tape are M0130's, unchanged and
imported rather than copied. **One thing moves: the label.**

WHY. M0130 asked a gradient-boosted tree to rank next month's return. It picked worse than the
most-traded big companies, and the ordering of its own variants was the tell: the LEAST flexible
tree (100 trees, 7 leaves, 1,000 samples a leaf, L2 10) finished ahead of the base tree at both
book sizes, and the base tree finished behind a control that forecasts nothing. A model whose
accuracy rises monotonically as you take its capacity away is a model with nothing to learn — the
flexible one is fitting noise because noise is what is there. One month of a stock's return is
roughly 95% noise around any cross-sectional signal the lab computes; twelve months is the
horizon at which momentum, value and quality were measured in the literature the features come
from. So this method keeps the capacity low (the regularised tree is the default here, not an
alternative) and makes the target slow: the percentile rank of the forward 252-session return,
with one arm at 63 sessions to put a middle rung on the ladder.

The machinery already takes it: ``TreeRankParams.horizon`` is a pre-registered field that enters
the model key and the config digest, bounded at 252 sessions. Nothing in ``lab/tree_rank.py`` is
edited for this method, and nothing in ``m0130_tree_ranker.py`` is either — M0130 has run and is
frozen. ``TreeBook``, ``BookParams``, ``model_ready`` and the SPY 200-day ``GATE`` are imported
from it; the one new object here is the control's gated twin.

THE COST OF A SLOW LABEL IS CALENDAR, NOT LOOKBACK. A sample enters training only once
``label_end(t, horizon) <= anchor``, so with a 252-session label the first refit holding 35
labelled month-ends is 1999-12-31 (36 of them, January 1996 to December 1998) rather than
M0130's 1998-12-31, and the first traded month is January 2000 rather than January 1999.
``FEATURE_LOOKBACK`` does not move. The 63-session arm lands on the same 1999-12-31 refit (45
labelled month-ends), so **all five variants here start trading the same session** and every
paired difference inside this batch is the picker alone. The comparison with M0130 carries a
one-year offset and the analysis says so.

EVERY VARIANT IS GATED. M0130's ungated arms fell about 70% in 2008; the lab has measured the SPY
200-day switch helping 22 of 22 variants whole-window, so running an ungated arm here would spend
four fifths of the batch re-measuring a settled question. The gate stands in front of the control
too, and it is read before the model-ready rule, exactly as M0130's gated arm read it: with the
gate off the book is cash, in 1996-1999 as much as in 2008. That rule is identical in all five.

THE CONTROL IS IN THIS BATCH, not quoted from M0130's trial. ``GatedDollarVolumeBook`` is M0130's
``DollarVolumeBook`` composed with the same gate: the 20 screen-eligible members with the largest
20-day dollar volume, equal weight, same lookback, same clock, same tape. Dollar volume forecasts
nothing, so tree minus control is what the model's picking adds over the shape of the book. It is
deliberately not a momentum book: the hard gate reads every dev variant's behaviour, and one
momentum arm moving with the lab's test-failed momentum books would bar the whole method.

Pure: no clock, randomness, files, network or printing. Reads only data dated <= data_date.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date
from types import MappingProxyType
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0130_tree_ranker import (
    BENCH,
    GATE,
    BookParams,
    ControlParams,
    TreeBook,
    model_ready,
)
from seer_engine.lab.tree_rank import FEATURE_LOOKBACK, SCREEN, TREE_RANK, TreeRankParams
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

ADDED = date(2026, 10, 14)

YEAR = 252  # the slow label: the forward 252-session return rank. The field's own upper bound.
QUARTER = 63  # the middle rung, and the horizon the lab's fall model already uses

# The regularised tree is the DEFAULT here, not an alternative. These five numbers are M0130's
# pre-registered `REG`, copied field for field and never searched on the dev window; only
# `top_n` and `horizon` differ between the arms below.
REG = TreeRankParams(
    top_n=20, learning_rate=0.05, max_iter=100, max_leaf_nodes=7, min_samples_leaf=1000, l2=10.0,
    horizon=YEAR,
)
# Strategy B's pre-registered tree (lr 0.05, 300 iters, 15 leaves, 200/leaf, L2 1), fixed
# 2026-10-03 for a different book. One arm carries it so the slow label is also read with M0130's
# flexible tree held fixed: B20 against M0130-P20-GATE is the horizon and nothing else.
BASE = TreeRankParams(top_n=20, horizon=YEAR)

TREE_BOOK = TreeBook(TREE_RANK, "M0131")


# --------------------------------------------------------------------------- the gated control


@dataclass(frozen=True, slots=True, eq=False)
class GatedControlPrepared:
    history: Mapping[str, History]
    factor: FactorPrepared


class GatedDollarVolumeBook:
    """M0130's dollar-volume control with the SPY 200-day switch in front of it.

    The same three rules the tree arms obey, read in the same order: switch off -> cash; no model
    yet -> hold SPY; otherwise pick. It owns no model, but it reads the trees' clock
    (``ControlParams.horizon``) so it starts trading on the same session they do.
    """

    id = "M0131-DV"

    def _check(self, params: object) -> ControlParams:
        if not isinstance(params, ControlParams):
            raise TypeError(f"params must be ControlParams, got {type(params).__name__}")
        return params

    def lookback(self, params: Any) -> int:
        self._check(params)
        return max(FEATURE_LOOKBACK, factor_lookback(GATE))

    def symbols(self, params: Any) -> tuple[str, ...]:
        self._check(params)
        return (BENCH,)

    def holds(self, params: Any) -> tuple[str, ...]:
        self._check(params)
        return (BENCH,)

    def uses_members(self, params: Any) -> bool:
        self._check(params)
        return True

    def _bench(self, history: Mapping[str, History], data_date: date) -> tuple[Target, ...]:
        h = history.get(BENCH)
        if h is None or h.index_of(data_date) is None:
            return ()
        t = target_from_close(BENCH, last_close(h, data_date), equal_weight(1))
        return () if t is None else (t,)

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
        if not trend_on(history, data_date, GATE):
            return ()
        if not model_ready(data_date, p.train_start, p.min_train_months, p.horizon):
            return self._bench(history, data_date)
        return self._pick(factor_rows(history, members, data_date, SCREEN), p)

    def prepare(self, history: Mapping[str, History]) -> GatedControlPrepared:
        return GatedControlPrepared(MappingProxyType(dict(history)), prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = self._check(params)
        if not isinstance(prepared, GatedControlPrepared):
            raise TypeError(f"prepared must be GatedControlPrepared, got {type(prepared).__name__}")
        if not trend_on(prepared.history, data_date, GATE):
            return ()
        if not model_ready(data_date, p.train_start, p.min_train_months, p.horizon):
            return self._bench(prepared.history, data_date)
        return self._pick(prepared.factor.rows_on(members, data_date, SCREEN), p)


DV_BOOK = GatedDollarVolumeBook()


# --------------------------------------------------------------------------- the method


def _v(suffix: str, allocator: Any, params: Any, rationale: str) -> Candidate:
    return Candidate(id=f"M0131-{suffix}", family="M0131", rules=MONTHLY_HOLD_FRAC_GOTRADE_TBAND,
                     allocator=allocator, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0131",
    name=(
        "A slower target for the learned ranker: the same yearly-refitted trees predict next "
        "year's return rank, not next month's, regularised, behind the market switch"
    ),
    family="stock-ml-ranker",
    source_kind="variation",
    source_ref="variation of M0130 (the first learned ranker); Sera batch 20261014-1206",
    parent_id="M0130",
    hypothesis=(
        "The first learned ranker fitted next month's return rank and lost to a control that "
        "forecasts nothing, and the ordering of its own variants said why: its LEAST flexible "
        "tree finished ahead of its base tree at both book sizes. A model that gets better as you "
        "take its capacity away has nothing to learn, because one month of a stock's return is "
        "almost all noise around anything this lab can compute. This method changes exactly one "
        "thing about the model and nothing else: the label. Instead of the percentile rank of the "
        "next 21 sessions' return it predicts the rank of the next 252 sessions' return, the "
        "horizon at which the features' own literature measured them, with one arm at 63 sessions "
        "to put a middle rung on the ladder. Everything else is M0130's, imported not copied: the "
        "same seven rank-normalised price and dividend features, the same annual walk-forward "
        "refit on an expanding window of month-end samples whose labels were already readable at "
        "the refit, the same equal-weight top-N book, the same fractional shares at Gotrade's real "
        "fees on the owner's 5,000,000 IDR monthly deposits, and the same resize band measured "
        "against each holding's own target. THE CAPACITY IS LOW BY DEFAULT: M0130's regularised "
        "setting (100 trees, 7 leaves, at least 1,000 samples a leaf, L2 10) is this method's "
        "base, copied field for field and never searched. EVERY VARIANT IS BEHIND THE LAB'S "
        "STANDING SPY 200-DAY SWITCH, the control included and read before every other rule, "
        "because M0130's ungated arms fell about 70% in 2008 and the switch has helped 22 of 22 "
        "lab variants whole-window; spending an arm to re-measure that would waste the method id. "
        "FIVE VARIANTS, THE ONLY SETTINGS EVER TRIED, no hyperparameter chosen by looking at a dev "
        "result: Y20 is the regularised tree on the yearly label holding its top 20; Y50 is the "
        "same model holding 50; B20 is the yearly label read with M0130's flexible base tree at 20 "
        "names, so B20 against M0130-P20-GATE is the horizon and nothing else; Q20 is the "
        "regularised tree on the 63-session label at 20 names; DV20 is the CONTROL, the same "
        "20-name equal-weight gated book on the same screen, lookback and clock, picked by 20-day "
        "dollar volume, which forecasts nothing. The control is run here rather than quoted from "
        "M0130's trial, and it is deliberately not a momentum book: the hard gate reads every "
        "variant's behaviour and one momentum arm moving with the lab's test-failed momentum books "
        "would bar the whole method. THE CALENDAR: a 252-session label is known 252 sessions late, "
        "so the first refit with 35 labelled month-ends is 1999-12-31 and the first traded month "
        "is January 2000; the 63-session arm lands on the same refit, so all five variants start "
        "trading the same session and every paired difference inside this batch is the picker "
        "alone. Before that they hold SPY when the switch is on and cash when it is off, "
        "identically. WHAT COUNTS AS THE MODEL ADDING SOMETHING, FIXED NOW: Y20 beats DV20 by at "
        "least 2 points a year of funded return over 2000-2015 AND is ahead of it in 2009-2015, "
        "the era most like today. If no tree arm clears that, the finding this method records is "
        "that the binding constraint is the lab's own signal set and not the model class or the "
        "target speed, and the lab should stop building rankers on these seven features rather "
        "than reach for a bigger model. WHAT COUNTS AS A METHOD: a variant clears every design "
        "section 1 bar at DSR >= 0.90 at the lab's N, against the dev screen on the worst fall "
        "(50%) and the real-money bar (25%). No variant is promoted in this run whatever it shows: "
        "the test window is not touched."
    ),
    expected_failure=(
        "Most likely the slower label changes the ranking less than it changes the turnover, and "
        "no tree arm clears the 2-point bar against the dollar-volume control. Four reasons. "
        "First, a 252-session label on monthly samples overlaps 92% with the next month's label, "
        "so consecutive training rows are nearly the same observation: the nominal 50,000-odd rows "
        "at the 2014 refit are worth perhaps a twentieth of that in independent information, and a "
        "slower target buys signal-to-noise per sample while paying for it in effective sample "
        "size. The net may be zero or worse. Second, the features that would plausibly survive a "
        "yearly horizon are momentum and its cousins, and a tree that learns them hands this "
        "method the same problem M0130 flagged: the picks may move with the lab's four test-failed "
        "momentum books closely enough that the hard gate's behavioural kin test bars promotion, "
        "which would be the correct verdict on a model that only re-discovered momentum. Third, "
        "the gate in front of every arm is read monthly and reacted late in 2008 for every lab "
        "book that used it; M0130's gated arm still fell 24.7%, inside the new 50% dev screen but "
        "close to the 25% real-money bar, and a book of 20 names cannot do much better than the "
        "switch allows. Fourth, the training set inherits the store's survivorship: about half of "
        "all index members ever listed are missing, mostly the ones that died, so the model learns "
        "from winners' histories, and the survivorship check cost the hand-built momentum books "
        "1-1.4 points a year and deepened their worst fall by about 2.6 points. A slow label makes "
        "that worse, not better: a name that was about to be delisted is exactly the one whose "
        "twelve-month forward return is missing from the training set. Fifth, Q20 is expected to "
        "sit between M0130's monthly arms and Y20 if the target-speed story is right, and to sit "
        "nowhere in particular if it is not — a non-monotone ladder would itself be evidence that "
        "the model is reading noise at every horizon. Sixth, B20 is expected to trail Y20: if the "
        "diagnosis is right the flexible tree should still overfit a slow label, just less. "
        "Finally, DSR at the lab's N of 82-plus needs a Sharpe well above anything M0130's arms "
        "produced (its best gated arm reached 0.63 and scored 0.647 against a 0.90 bar), so even a "
        "tree arm that beats SPY on return is likely to fail the luck test, and losing on luck "
        "after beating the control would still be a real finding about the signal set."
    ),
    candidates=(
        _v("Y20", TREE_BOOK, BookParams(REG, gate=True),
           "The regularised tree on next year's return rank, top 20, behind the SPY 200-day switch"),
        _v("Y50", TREE_BOOK, BookParams(replace(REG, top_n=50), gate=True),
           "The same yearly-label regularised tree holding its top 50"),
        _v("B20", TREE_BOOK, BookParams(BASE, gate=True),
           "The yearly label read with M0130's flexible base tree, top 20: the horizon and nothing else"),
        _v("Q20", TREE_BOOK, BookParams(replace(REG, horizon=QUARTER), gate=True),
           "The regularised tree on the next quarter's return rank, top 20: the ladder's middle rung"),
        _v("DV20", DV_BOOK, ControlParams(top_n=20, horizon=YEAR),
           "Control: the same gated 20-name book picked by trading volume, no model"),
    ),
    seen_keys=(
        "concept:annual-horizon-learned-ranker",
        "concept:slow-label-tree-ranker",
        "concept:forward-return-horizon-ladder",
    ),
)

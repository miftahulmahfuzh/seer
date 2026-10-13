"""M0132 -- Learn the fall, not the pick: a model that sizes the book, not its names.

Source: Moreira & Muir (2017), "Volatility-Managed Portfolios", Journal of Finance 72(4).
Handover 2026-10-13 ("measure the constraint"), section 2 item 2.

WHY THIS AND NOT ANOTHER RANKER. The lab's own record says the binding constraint is the fall, not
the pick: of 394 dev trials with a recorded return, 256 (65%) beat SPY total return but only 92
(23%) keep the worst fall at or under 20%. Out of sample it inverts -- all four spent test looks
failed on return. A two-thirds dev hit rate that vanishes out of sample is the signature of
selection, and more selection is the one thing this lab should stop buying. Against that, the lab
has exactly ONE risk control -- the SPY 200-day switch -- and it has never been improved on. So
this method points the same walk-forward, point-in-time machinery M0130 used at a different
question: not "which names will go up" but "how much of this book should be held".

THE LABEL is the forward FALL, AS A LEVEL: the worst peak-to-trough drop over the next quarter (63
NYSE sessions), in fractions, not the next month's return rank and not a rank of the fall either.
That distinction is the method. Every FEATURE the lab computes is already rank-normalised within
its date; a label ranked the same way would leave the model's forecasts near-identical on every
date by construction, and in October 2008 -- when every name is about to fall -- the per-date ranks
are still uniform, so the label could not say "all of them" even in principle. A level can.

THE FEATURE MATRIX therefore carries a level too, or the level label would buy nothing: the seven
rank-normalised features the lab already computes, plus three un-normalised market-level columns --
the market's distance below its trailing one-year high, its realised volatility over the last sixty
sessions, and the spread of the day's own momentum across the cross-section. Each is one number for
the whole date, repeated down the rows, so it cannot change which names the model prefers; it can
only move the whole date's forecast up or down. That is the level the head reads.

THE HEAD turns the forecast into EXPOSURE -- what share of the book is held, with the remainder in
cash -- rather than into a pick order, and it reads a MARKET-LEVEL quantity to do it. The date's
cross-sectional MEAN forecast fall is located in the model's own training distribution of
date-level means; the book keeps the share of its slots that the date is calmer than, in whole
slots, each at a fixed weight, never renormalised onto the survivors. A date calmer than every
training date is a full book; a date worse than all of them is entirely cash; the median date is
half. NO NUMBER IN THAT LADDER WAS CHOSEN: it is the model's own in-sample distribution, so nothing
in this head was read off the dev window, which is what pre-registration requires.

All of that lives in ``lab.tree_rank`` beside the return-rank path; nothing in that module that
M0130's recorded configurations depend on is touched.

THE NAMES ARE NOT THE QUESTION, and are therefore held fixed. Every variant, model and control
alike, holds the twenty screen-eligible index members with the largest 20-day dollar volume
(``tree_rank.SCREEN``, the tree's own screen). Dollar volume forecasts nothing -- it is the
yardstick M0130 used as its control -- so the only thing that differs between variants is how much
of that same book is held, and every paired difference below is the sizing alone.

IT IS DELIBERATELY NOT A MOMENTUM BOOK. The hard gate's behavioural kin test
(``lab/hardgate.py``, ``KIN_CORRELATION`` 0.85) reads EVERY dev variant of a method against the
four test-failed books' tested variants, and one match bars the whole method from promotion
forever. Three of those four are momentum books. A dollar-volume book's residual, once each
series' fit on SPY is removed, is size- and liquidity-shaped, not momentum-shaped; and no variant
here ranks on momentum in any era at any exposure.

BEFORE THE FIRST MODEL, HOLD SPY. ``model_ready`` is M0130's calendar rule, imported rather than
re-written so the pre-model era of the two methods is identical. With a 63-session label and 35
required labelled month-ends the first refit with enough history is 1999-12-31 (only 33 month-ends
from 1996-01-31 have their quarter-long label read by 1998-12-31), so the book is SPY through 1999
in all five variants. It is calendar-only and shared with the controls, which have no model, so
every variant switches on the same session and the pre-model era cancels out of every difference.

THE FIVE VARIANTS are the only settings this idea will ever try. None was chosen by looking at a
dev result and none will be revised after one; a change after a result is a new method.

    FALL20       the fall model sizes the twenty-name book, base tree
    FALL20-REG   the same, with the one fixed regularised tree (M0130's REG, verbatim)
    FALL20-GATE  the same base model, also behind the lab's standing SPY 200-day switch
    GATE20       CONTROL: the same twenty names, sized only by the SPY 200-day switch
    ON20         CONTROL: the same twenty names, always fully invested, no risk control

IDLE CASH EARNS NOTHING here (``MONTHLY_HOLD_FRAC_GOTRADE_TBAND``, M0130's rule set). The
cash-crediting preset raises an owner input paper refuses, and this is the version the owner can
actually trade. It biases every exposure-reducing variant downward -- but GATE20 sits in cash too,
so the FALL20-minus-GATE20 difference, which is the question, absorbs nearly all of that bias.

NO FUNDAMENTALS VARIANT. The EDGAR panel starts in 2009; a panel-gated variant would be all-cash
for thirteen of the dev window's twenty years and would measure the panel rather than the
hypothesis. Every variant ranks on price and dividend features only, so the coverage floor is never
engaged and this method never runs under ``--allow-coverage``.

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
from seer_engine.lab.methods.m0130_tree_ranker import model_ready
from seer_engine.lab.tree_rank import (
    FALL_FEATURE_LOOKBACK,
    FALL_SIZE,
    SCREEN,
    FallSizeParams,
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

ADDED = date(2026, 10, 13)
BENCH = "SPY"  # held before the first model, and the gate's instrument
GATE = N20  # the lab's standing SPY 200-day switch (F4-MOM12-N20-TREND's), read only for its trend

# The decision calendar, written once and shared by the model and both controls, so that
# `model_ready` fires on the same session for all five variants.
TRAIN_START = date(1996, 1, 31)
MIN_TRAIN_MONTHS = 35
HORIZON = 63  # one quarter: the window the forward fall is measured over
TOP_N = 20  # the book's size, identical in every variant

#: The base tree: Strategy B's pre-registered setting (lr 0.05, 300 iters, 15 leaves, 200/leaf,
#: L2 1), fixed 2026-10-03 for a different book and never searched. `slots` is phase 2's field
#: name for the book's size; `size=True` (the default) switches the exposure ladder on.
BASE = FallSizeParams(
    slots=TOP_N,
    horizon=HORIZON,
    train_start=TRAIN_START,
    min_train_months=MIN_TRAIN_MONTHS,
)
#: The one fixed alternative: fewer, shallower, fatter-leaved trees. M0130's REG, verbatim, so
#: "regularised" means the same thing in both methods.
REG = FallSizeParams(
    slots=TOP_N,
    horizon=HORIZON,
    train_start=TRAIN_START,
    min_train_months=MIN_TRAIN_MONTHS,
    max_iter=100,
    max_leaf_nodes=7,
    min_samples_leaf=1000,
    l2=10.0,
)


def _bench(history: Mapping[str, History], data_date: date) -> tuple[Target, ...]:
    """SPY at full weight, priced at d's close; nothing when SPY has no bar dated d."""
    h = history.get(BENCH)
    if h is None or h.index_of(data_date) is None:
        return ()
    t = target_from_close(BENCH, last_close(h, data_date), equal_weight(1))
    return () if t is None else (t,)


# --------------------------------------------------------------------------- the model book


@dataclass(frozen=True, slots=True)
class FallBookParams:
    """The fall model's own params, and whether the SPY 200-day switch stands in front of it."""

    fall: FallSizeParams
    gate: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.fall, FallSizeParams):
            raise TypeError(f"fall must be FallSizeParams, got {type(self.fall).__name__}")
        if not isinstance(self.gate, bool):
            raise TypeError(f"gate must be a bool, got {type(self.gate).__name__}")

    def as_dict(self) -> dict[str, str]:
        out = dict(self.fall.as_dict())
        out["gate"] = "SPY:200" if self.gate else "none"
        return out


@dataclass(frozen=True, slots=True, eq=False)
class FallBookPrepared:
    """The inner model's prepared value, and the bars the SPY fill and the gate read.

    ``history`` is None on the history-only path, which by the market-aware contract targets
    nothing (tests/test_lab_methods.py).
    """

    inner: Any
    history: Mapping[str, History] | None


class FallBook:
    """Phase 2's fall-sizing book, SPY before its first model, optionally behind the SPY switch."""

    def __init__(self, inner: Any, ident: str) -> None:
        self.inner = inner
        self.id = ident
        # What `lab run` gates on (runner.market_fields): exactly the inner model's fields.
        self.market_fields: tuple[str, ...] = tuple(inner.market_fields)

    def _check(self, params: object) -> FallBookParams:
        if not isinstance(params, FallBookParams):
            raise TypeError(f"params must be FallBookParams, got {type(params).__name__}")
        return params

    def lookback(self, params: Any) -> int:
        p = self._check(params)
        n = self.inner.lookback(p.fall)
        return max(n, factor_lookback(GATE)) if p.gate else n

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = self._check(params)
        return tuple(sorted({BENCH, *self.inner.symbols(p.fall)}))

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

    def prepare(self, history: Mapping[str, History]) -> FallBookPrepared:
        return FallBookPrepared(self.inner.prepare(history), None)

    def prepare_market(self, market: Any) -> FallBookPrepared:
        return FallBookPrepared(
            self.inner.prepare_market(market), MappingProxyType(dict(market.history))
        )

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = self._check(params)
        if not isinstance(prepared, FallBookPrepared):
            raise TypeError(f"prepared must be FallBookPrepared, got {type(prepared).__name__}")
        if prepared.history is None:
            return ()
        if p.gate and not trend_on(prepared.history, data_date, GATE):
            return ()
        if not model_ready(data_date, p.fall.train_start, p.fall.min_train_months, p.fall.horizon):
            return _bench(prepared.history, data_date)
        return self.inner.targets_prepared(prepared.inner, members, data_date, held, p.fall)


FALL_BOOK = FallBook(FALL_SIZE, "M0132")


# --------------------------------------------------------------------------- the controls


@dataclass(frozen=True, slots=True)
class ControlParams:
    """The control's book size, whether the SPY switch sizes it, and the clock it shares.

    The clock defaults are the model's own (``BASE``), so `model_ready` fires on the same session
    for a control as for a model variant and the pre-model era cancels out of every difference.
    """

    top_n: int = TOP_N
    gate: bool = False
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
        if not isinstance(self.gate, bool):
            raise TypeError(f"gate must be a bool, got {type(self.gate).__name__}")
        if not isinstance(self.train_start, date):
            raise TypeError(f"train_start must be a date, got {type(self.train_start).__name__}")

    def as_dict(self) -> dict[str, str]:
        return {
            "top_n": str(self.top_n),
            "gate": "SPY:200" if self.gate else "none",
            "train_start": self.train_start.isoformat(),
            "min_train_months": str(self.min_train_months),
            "horizon": str(self.horizon),
        }


@dataclass(frozen=True, slots=True, eq=False)
class ControlPrepared:
    history: Mapping[str, History]
    factor: FactorPrepared


class SizedVolumeBook:
    """The model book's shape without the model: the most-traded eligible members, equal weight.

    ``gate=False`` is the no-risk-control floor: always fully invested once the model era starts.
    ``gate=True`` is the lab's one existing risk control -- the SPY 200-day switch -- sizing the
    same book, which is the yardstick the handover says has never been improved on.
    """

    id = "M0132-DV"

    def _check(self, params: object) -> ControlParams:
        if not isinstance(params, ControlParams):
            raise TypeError(f"params must be ControlParams, got {type(params).__name__}")
        return params

    def lookback(self, params: Any) -> int:
        p = self._check(params)
        n = FALL_FEATURE_LOOKBACK  # the model's window, so all five variants score the same sessions
        return max(n, factor_lookback(GATE)) if p.gate else n

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
        if p.gate and not trend_on(history, data_date, GATE):
            return ()
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
        if p.gate and not trend_on(prepared.history, data_date, GATE):
            return ()
        if not model_ready(data_date, p.train_start, p.min_train_months, p.horizon):
            return _bench(prepared.history, data_date)
        return self._pick(prepared.factor.rows_on(members, data_date, SCREEN), p)


SIZED_DV = SizedVolumeBook()


# --------------------------------------------------------------------------- the method


def _v(suffix: str, allocator: Any, params: Any, rationale: str) -> Candidate:
    return Candidate(id=f"M0132-{suffix}", family="M0132", rules=MONTHLY_HOLD_FRAC_GOTRADE_TBAND,
                     allocator=allocator, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0132",
    name="Learn the fall, not the pick: a model that forecasts the next quarter's drop and sizes the book by it",
    family="model-sized-exposure",
    source_kind="paper",
    source_ref=(
        "Moreira & Muir (2017), Volatility-Managed Portfolios, Journal of Finance 72(4); "
        "handover 2026-10-13 (measure the constraint), section 2 item 2"
    ),
    parent_id=None,
    hypothesis=(
        "This lab's own record says the constraint that binds is the fall, not the pick: of 394 "
        "dev trials with a recorded return, 256 (65%) beat SPY total return but only 92 (23%) keep "
        "the worst fall at or under 20%, and all four spent test looks failed on return, not on "
        "drawdown. A two-thirds dev hit rate that vanishes out of sample is the signature of "
        "selection. Against that the lab has exactly one risk control, the SPY 200-day switch, and "
        "nothing has improved on it. THE QUESTION: can a learned forecast of the coming fall size "
        "a book better than that switch does? THE LABEL is the forward fall AS A LEVEL -- the "
        "worst peak-to-trough drop over the next 63 NYSE sessions, one quarter, in fractions -- "
        "not the next month's return rank and not a rank of the fall either. That distinction is "
        "the method: every feature below is rank-normalised within its date, and a label ranked "
        "the same way would leave the forecasts near-identical on every date by construction, so "
        "in October 2008, when every name is about to fall, the label could not say 'all of them' "
        "even in principle. THE HEAD turns the forecast into exposure, the share of the book that "
        "is held, with the remainder in cash, and it reads a MARKET-LEVEL quantity to do it: the "
        "date's cross-sectional MEAN forecast fall is located in the model's own training "
        "distribution of date-level means, and the book keeps the share of its slots that the date "
        "is calmer than -- in whole slots, each at a fixed weight, never renormalised onto the "
        "survivors. A date calmer than every training date is a full book, a date worse than all "
        "of them is entirely cash, the median date is half. NO NUMBER IN THAT LADDER WAS CHOSEN: "
        "it is the model's own in-sample distribution, so nothing in the head was read off the dev "
        "window. The machinery is M0130's: scikit-learn histogram "
        "gradient-boosted trees refitted once a year at the last session of each year, on every "
        "month-end sample since January 1996 whose label had already been read by then (an "
        "expanding window; nothing dated after the decision date is ever read), on the same seven "
        "features the lab already computes, each rank-normalised per date: 12-1 momentum, 60-day "
        "volatility, 20-day dollar volume, M0007-N20-RAW's residual momentum, distance from the "
        "52-week high, M0070's dividend-raise event and the trailing dividend yield -- PLUS THREE "
        "UN-NORMALISED MARKET-LEVEL COLUMNS, without which a level label would buy nothing: the "
        "market's distance below its trailing one-year high, its realised volatility over the last "
        "sixty sessions, and the spread of the day's own momentum across the cross-section. Each "
        "of those three is one number for the whole date, repeated down the rows, so none of them "
        "can change which names the model prefers -- only how far the whole date's forecast moves, "
        "which is exactly the level the head reads. THE NAMES ARE "
        "HELD FIXED and are not the question: every variant, model and control alike, holds the "
        "twenty screen-eligible index members with the largest 20-day dollar volume, equal weight. "
        "Dollar volume forecasts nothing, so the only thing that differs between variants is how "
        "much of that same book is held, and every paired difference below is the sizing alone. "
        "BEFORE THE FIRST MODEL every variant holds SPY. With a quarter-long label and 35 required "
        "labelled month-ends the first refit with enough history is 1999-12-31, so the book is SPY "
        "through 1999 in all five; the rule is calendar-only and shared with the controls, which "
        "have no model, so the pre-model era is identical everywhere and cancels out. FIVE "
        "VARIANTS, THE ONLY SETTINGS EVER TRIED: no hyperparameter was tuned on the dev window off "
        "the books, and none will be; a change after a result is a new method. The base tree is "
        "Strategy B's pre-registered setting (learning rate 0.05, 300 trees, 15 leaves, at least "
        "200 samples per leaf, L2 1.0), fixed 2026-10-03 for a different book and never searched; "
        "the regularised tree (100 trees, 7 leaves, 1,000 per leaf, L2 10) is M0130's one fixed "
        "alternative re-used verbatim. FALL20 is the model sizing the book; FALL20-REG is the "
        "regularised tree doing the same; FALL20-GATE is the base model also behind the SPY "
        "200-day switch; GATE20 is the CONTROL in which that switch alone sizes the same twenty "
        "names; ON20 is the CONTROL that is always fully invested, with no risk control at all. "
        "WHAT EACH DIFFERENCE ISOLATES: GATE20 minus ON20 is what the lab's existing control is "
        "worth on this exact book; FALL20 minus ON20 is what the learned forecast adds over no "
        "control; FALL20 minus GATE20 is the question itself; FALL20-GATE minus GATE20 is whether "
        "the model sees anything the switch has not already taken; FALL20-REG minus FALL20 is "
        "whether any of it is model capacity rather than signal. WHAT COUNTS AS THE MODEL ADDING "
        "SOMETHING, fixed now: FALL20's worst fall over the model era is at least 5 percentage "
        "points shallower than GATE20's AND its funded return is no more than 2 points a year "
        "behind GATE20's -- a control that only costs return is not an improvement, because the "
        "switch already does that -- AND FALL20 beats ON20 on MAR. WHAT COUNTS AS A METHOD: a "
        "variant clears every design section 1 bar at DSR >= 0.90 at the lab's N, the worst fall "
        "at or under 20% included. IDLE CASH EARNS NOTHING in these rules, which is the version "
        "the owner can actually trade; it biases every exposure-reducing variant downward, and the "
        "FALL20-minus-GATE20 comparison absorbs nearly all of that because GATE20 sits in cash "
        "too. NO VARIANT IS PROMOTED in this run whatever it shows: the test window is not touched."
    ),
    expected_failure=(
        "Most likely the model's exposure ladder turns out to be a slow volatility target wearing "
        "a new name. Realised volatility is the most persistent of the seven features and is "
        "already one of them, and a forward-fall label over a quarter is largely a volatility "
        "label, so the forecast will probably track trailing volatility closely enough that the "
        "book cuts exposure when volatility is already high -- which is after the fall has begun, "
        "not before it. The lab has priced volatility targets before and they did not clear the "
        "20% bar, and two of the three market-level columns -- the market's own realised "
        "volatility, and its distance below its one-year high -- are precisely the inputs a slow "
        "volatility target would use, so the head has every opportunity to rediscover one. Second, "
        "the level may be too coarse to be worth reading: the exposure ladder is driven by a "
        "single number a date, the cross-sectional mean forecast, located in a training "
        "distribution of at most a couple of hundred date-level means, so the ladder's resolution "
        "is one slot per few percentiles and the book may end up moving between full and nearly "
        "full on almost every date. If the realised exposure turns out to sit in a narrow band -- "
        "say between eighteen and twenty of the twenty slots on nine dates in ten -- then FALL20 "
        "will be nearly indistinguishable from ON20 whatever the forecast said, and the honest "
        "verdict is that the question was asked too quietly to hear the answer. (The flat-exposure "
        "failure this method was originally at risk of -- a label ranked within each date, which "
        "cannot encode a market-wide fall at all -- was removed before pre-registration: the label "
        "is a level and the feature matrix carries un-normalised market columns. That the exposure "
        "moves at all, and falls in 2008, was measured on the dev window before this file was "
        "committed. What was NOT measured, and is the open risk, is whether it moves ENOUGH and in "
        "the right years.) Third, the SPY 200-day switch is a very hard thing to beat on this window for a "
        "reason that is not skill: it caught 2008, the one year that dominates every whole-window "
        "drawdown number, and the lab has already measured that nearly all of the switch's "
        "whole-window value is that single year and that it has been a drag since 2009. So GATE20 "
        "is likely to win the whole window on the strength of 2008 and lose 2009-2015, and a model "
        "that is better than it after 2009 may still look worse over the full record. Fourth, the "
        "fall is broader than one crash: of the 302 dev trials that breached 20%, the worst year "
        "is 2008 for 103 of them but 2011 for 51 and 2015 for 50, so a forecast that only learns "
        "the shape of 2008 will not keep the fall under 20% and no variant here will clear design "
        "section 1. Fifth, cutting exposure costs return in a window SPY roughly quadrupled over, "
        "and with idle cash earning nothing every reduction is a pure drag on the return side of "
        "every bar; the monthly decision cadence also means the book cannot step aside faster than "
        "once a month, which was late in 2008 for every lab book that used the switch. Sixth, the "
        "training set inherits the store's survivorship -- about half of the index members ever "
        "listed are missing, mostly the ones that died -- and a fall model trained on survivors' "
        "histories has systematically seen fewer catastrophic falls than really happened, which "
        "should make it optimistic exactly where it matters most. Seventh, twenty years of monthly "
        "cross-sections is a small and heavily correlated sample for a learner, and a quarter-long "
        "label makes neighbouring month-ends overlap by two thirds, so the effective sample is "
        "roughly a third of the row count and the DSR at the lab's N may not separate a real "
        "sizing skill from luck even if the returns look good. Finally, the regularised arm is "
        "expected to sit between the base model and the controls, and if it does not -- if the "
        "regularised tree is clearly better -- that is evidence the base tree was overfitting the "
        "label and the right reading is that neither setting found anything."
    ),
    candidates=(
        _v("FALL20", FALL_BOOK, FallBookParams(BASE),
           "The fall model sizes a twenty-name dollar-volume book, base tree"),
        _v("FALL20-REG", FALL_BOOK, FallBookParams(REG),
           "The same book sized by the regularised tree (100 trees, 7 leaves, 1000 per leaf, L2 10)"),
        _v("FALL20-GATE", FALL_BOOK, FallBookParams(BASE, gate=True),
           "The base model's sizing behind the lab's standing SPY 200-day switch as well"),
        _v("GATE20", SIZED_DV, ControlParams(gate=True),
           "Control: the same twenty names sized only by the SPY 200-day switch, no model"),
        _v("ON20", SIZED_DV, ControlParams(),
           "Control: the same twenty names always fully invested, no risk control at all"),
    ),
    seen_keys=(
        "concept:forward-drawdown-label",
        "concept:model-sized-exposure",
        "concept:learned-risk-control",
        "concept:market-level-exposure-ladder",
        "concept:walk-forward-annual-refit",
    ),
)

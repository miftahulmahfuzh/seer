"""M0137 — A forgetting ranker: the yearly-horizon trees retrained on a rolling ten-year window.

Source: variation of M0131 (the slow-target learned ranker), which is this method's parent and
whose best arm, B20, this method keeps field for field. The model class, the seven features, the
label horizon, the refit cadence, the SPY 200-day switch, the book size and the measuring tape are
all M0131's, imported and never copied. **One thing moves: how much history each refit learns
from.**

WHY. M0131 found the horizon, not the model. Asking the trees to rank the next 252 sessions
instead of the next 21 took the flexible tree from 6.7% to 10.5% a year over 2000-2015 and from
9.4% to 15.9% over 2009-2015, and B20 became the first learned ranker in this lab to clear every
design §1 bar (funded 10.9% a year against SPY's 7.2%, worst fall 20.0%, DSR 0.912). Promotion was
refused all the same, on the hard gate's fold rule: 2 of 4 walk-forward folds, and **both losses
are rising markets** (2003-05: +35.9% against SPY's +52.1%; 2009-11: +59.7% against +60.8%). Both
wins are the switch sitting in cash (2006-08, 2012-14). Every arm also lost to SPY over 2009-2015,
the era most like today. So the whole-window win is the safety rule, not the picking.

THE SUSPECT IS MEMORY. Every refit so far learns from an expanding window that starts at
1996-01-31 and never forgets. The 2012 model still carries the 1996-2000 technology boom and bust
as a large share of its training rows, and M0130 already diagnosed the tilt that produces: away
from the largest, most-extended names. A tilt learned in 1999-2002 is exactly the tilt that loses
to a rising large-cap market, which is exactly where M0131's two folds failed. A model that
forgets should track the regime it is about to trade.

THE ONE FIELD. ``train_start`` already exists in ``TreeRankParams``, it already enters
``model_key`` and the config digest, and ``TreeRankPrepared.training_dates`` already reads it as
``month_ends(train_start, anchor)``. A rolling window is therefore **not new machinery**: it is the
existing machinery asked for a ``train_start`` that moves with the anchor. ``RollingTreeBook``
computes, at each decision date, ``train_start = max(1996-01-31, 1 January of (anchor year - years
+ 1))`` and hands ``TREE_RANK`` the same ``TreeRankParams`` with that one field replaced. Nothing
in ``lab/tree_rank.py``, ``m0130_tree_ranker.py`` or ``m0131_slow_target_ranker.py`` is edited —
all three have run and are frozen — and no recorded configuration's digest moves, because this
method's params are a new class behind a new allocator id.

THE FLOOR AND THE CALENDAR MATTER, and the honest reading of this batch depends on them. The
window is clipped at M0131's own ``train_start``, so a rolling arm is **identical** to the
expanding arm until the roll bites:

    * the 5-year arm first differs at the 2001-12-31 refit, so from the 2002 book year;
    * the 10-year arm first differs at the 2006-12-31 refit, so from the 2007 book year.

Seven of the sixteen traded years are therefore the same book in R10 and EXP by construction. That
is not a flaw to hide, it is the dev window's length, and it has a useful consequence: **R5 is the
instrument for the 2003-05 fold and R10 for the 2009-11 fold** — the two folds M0131 lost. The
readiness rule (``model_ready``) is read on the FLOOR date in every arm, so all five variants start
trading the same session, January 2000, and every paired difference inside this batch is the
training window alone. A 5-year window always holds at least 47 labelled month-ends against the
35 a model needs, so no arm ever goes to cash for want of training rows.

EVERY VARIANT IS GATED, the control included and read first, because M0130's ungated arms fell
about 70% in 2008 and the lab has measured the SPY 200-day switch helping 22 of 22 variants
whole-window. Re-measuring that here would spend the method id on a settled question.

THE CONTROLS ARE IN THIS BATCH, not quoted across a trial boundary. EXP is M0131-B20's economics
under this method's allocator: if it does not reproduce B20's recorded numbers, the rolling
wrapper has a bug and the whole batch is void — it is a correctness check as much as a control.
DV20 is M0131's gated dollar-volume book, subclassed for a distinct allocator id and otherwise
untouched, so the "what does the model add" comparison also stays inside one trial.

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
    ControlParams,
    TreeBookPrepared,
    _bench,
    model_ready,
)
from seer_engine.lab.methods.m0131_slow_target_ranker import YEAR, GatedDollarVolumeBook
from seer_engine.lab.tree_rank import (
    TREE_RANK,
    TreeRankParams,
    anchor_for,
)
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE_TBAND
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import factor_lookback, trend_on

ADDED = date(2026, 10, 14)

# M0131's B20 tree, field for field: Strategy B's pre-registered flexible setting on the yearly
# label. M0131 measured the flexible tree beating the regularised one once the label is slow, so
# the flexible one is this method's base and the regularised one is the single fixed alternative.
BASE = TreeRankParams(top_n=20, horizon=YEAR)
REG = TreeRankParams(
    top_n=20, learning_rate=0.05, max_iter=100, max_leaf_nodes=7, min_samples_leaf=1000, l2=10.0,
    horizon=YEAR,
)

DECADE = 10  # the rolling window the idea names: the most recent ten calendar years of month-ends
LUSTRUM = 5  # the short rung, and the only arm that reaches M0131's 2003-05 fold


# --------------------------------------------------------------------------- the rolling window


def window_start(floor: date, train_years: int | None, anchor: date) -> date:
    """The first month-end a refit on ``anchor`` may learn from.

    ``None`` is the expanding window: the floor, forever, which is what M0131 did. Otherwise the
    window is the most recent ``train_years`` CALENDAR years of month-ends ending at the anchor
    (1 January of ``anchor.year - train_years + 1``), never reaching below ``floor``. Calendar
    years, not a session count, because the refit itself is calendar-anchored: the model fitted at
    the last session of 2011 with ten years of memory learns from January 2002 onward, and the
    samples whose labels are not yet readable drop out through the existing
    ``training_dates`` rule rather than through anything new here.
    """
    if not isinstance(floor, date):
        raise TypeError(f"floor must be a date, got {type(floor).__name__}")
    if not isinstance(anchor, date):
        raise TypeError(f"anchor must be a date, got {type(anchor).__name__}")
    if train_years is None:
        return floor
    if isinstance(train_years, bool) or not isinstance(train_years, int):
        raise TypeError(f"train_years must be an int or None, got {type(train_years).__name__}")
    if train_years < 1:
        raise ValueError(f"train_years must be >= 1, got {train_years}")
    return max(floor, date(anchor.year - train_years + 1, 1, 1))


@dataclass(frozen=True, slots=True)
class RollingParams:
    """M0131's book params plus the one new field: how many years back a refit may look.

    ``tree`` is the tree M0131 ran, and its ``train_start`` is read here as the FLOOR of the
    rolling window rather than as its start. ``train_years`` of ``None`` is the expanding window,
    which reproduces M0131 exactly. ``gate`` is the SPY 200-day switch and is True in every
    variant of this method.
    """

    tree: TreeRankParams
    train_years: int | None = None
    gate: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.tree, TreeRankParams):
            raise TypeError(f"tree must be TreeRankParams, got {type(self.tree).__name__}")
        if not isinstance(self.gate, bool):
            raise TypeError(f"gate must be a bool, got {type(self.gate).__name__}")
        # Validate the window field the same way on every construction, never at decision time.
        window_start(self.tree.train_start, self.train_years, date(2000, 12, 29))

    def as_dict(self) -> dict[str, str]:
        out = dict(self.tree.as_dict())
        out["train_years"] = "expanding" if self.train_years is None else str(self.train_years)
        out["gate"] = "SPY:200" if self.gate else "none"
        return out


class RollingTreeBook:
    """M0131's gated tree book with the training window rolled, and nothing else changed.

    The three rules are read in M0131's order and are identical in every arm: switch off -> cash;
    no model yet (the FLOOR calendar, so all arms start the same session) -> hold SPY; otherwise
    hand the inner ranker the tree params with ``train_start`` replaced by this anchor's window.
    """

    id = "M0137"

    def __init__(self) -> None:
        self.inner = TREE_RANK
        # What `lab run` gates the store on (runner.market_fields): the inner ranker's own fields.
        self.market_fields: tuple[str, ...] = tuple(TREE_RANK.market_fields)

    def _check(self, params: object) -> RollingParams:
        if not isinstance(params, RollingParams):
            raise TypeError(f"params must be RollingParams, got {type(params).__name__}")
        return params

    def _rolled(self, p: RollingParams, data_date: date) -> TreeRankParams:
        start = window_start(p.tree.train_start, p.train_years, anchor_for(data_date))
        return p.tree if start == p.tree.train_start else replace(p.tree, train_start=start)

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
        return TreeBookPrepared(
            self.inner.prepare_market(market), MappingProxyType(dict(market.history))
        )

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
        return self.inner.targets_prepared(
            prepared.inner, members, data_date, held, self._rolled(p, data_date)
        )


ROLLING_BOOK = RollingTreeBook()


class M0137Control(GatedDollarVolumeBook):
    """M0131's gated dollar-volume control, re-run here under this method's own allocator id.

    Not one line of its behaviour changes; only the id does, because a config digest names the
    allocator by id and the lab rightly refuses a configuration it has already run. Running it
    again costs compute and nothing else (a method is one look however many variants it has), and
    it buys the batch a control measured at the same trial boundary as the arms it judges.
    """

    id = "M0137-DV"


DV_BOOK = M0137Control()


# --------------------------------------------------------------------------- the method


def _v(suffix: str, allocator: Any, params: Any, rationale: str) -> Candidate:
    return Candidate(id=f"M0137-{suffix}", family="M0137", rules=MONTHLY_HOLD_FRAC_GOTRADE_TBAND,
                     allocator=allocator, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0137",
    name=(
        "A forgetting ranker: the yearly-horizon trees retrained on a rolling ten-year window "
        "instead of an ever-growing one"
    ),
    family="stock-ml-ranker",
    source_kind="variation",
    source_ref="variation of M0131 (the slow-target learned ranker); Sera batch 20261014-1242",
    parent_id="M0131",
    hypothesis=(
        "M0131 showed that asking the trees about the next twelve months instead of the next "
        "month is worth 3.8 points a year over 2000-2015 and 6.5 points over 2009-2015, with the "
        "model, the gate, the tape and the window all held fixed; and that with a slow label the "
        "flexible tree beats the regularised one, reversing M0130. What it did not fix is where "
        "the money comes from: every arm lost to SPY in 2009-2015 (best 15.9% against 16.6%), the "
        "whole-window win is the SPY 200-day switch sitting in cash through 2001, 2002 and 2008, "
        "and the walk-forward record is 2 of 4 folds with BOTH losses in rising markets "
        "(2003-05 +35.9% against SPY's +52.1%; 2009-11 +59.7% against +60.8%), which is what "
        "refuses promotion. THE SUSPECT IS MEMORY. Every refit so far adds twelve months to an "
        "expanding window that starts in January 1996 and never forgets, so the 1996-2000 "
        "technology boom and bust is still a large share of the 2012 model's training set and the "
        "tilt M0130 diagnosed -- away from the largest, most-extended names -- never decays. A "
        "tilt learned in 1999-2002 is exactly the tilt that loses to a rising large-cap market, "
        "which is exactly where M0131's two folds failed. This method keeps M0131-B20 exactly -- "
        "the flexible tree, the 252-session label, the top 20, the SPY 200-day switch, the fixed "
        "tape at Gotrade's real fees on the owner's 5,000,000 IDR monthly deposits -- and changes "
        "one field: the training window becomes the most recent N calendar years of labelled "
        "month-ends rather than everything since 1996. NO NEW MACHINERY: train_start already "
        "exists, already enters the model key and the config digest, and already drives "
        "training_dates; a rolling window is that field moved with the refit anchor, and no file "
        "that has run is edited. THE WINDOW IS CLIPPED AT 1996-01-31, so a rolling arm is "
        "IDENTICAL to the expanding arm until the roll bites: the 5-year arm first differs at the "
        "2001 refit (the 2002 book year), the 10-year arm at the 2006 refit (the 2007 book year). "
        "Seven of sixteen traded years are the same book in the 10-year arm by construction. That "
        "is the dev window's length, not a flaw, and it has a useful consequence that is written "
        "down here before any result: THE 5-YEAR ARM IS THE INSTRUMENT FOR THE 2003-05 FOLD AND "
        "THE 10-YEAR ARM FOR THE 2009-11 FOLD, the two folds M0131 lost. The readiness rule is "
        "read on the floor date in every arm, so all five variants start trading the same "
        "session, January 2000, and every paired difference in this batch is the training window "
        "alone; a 5-year window always holds at least 47 labelled month-ends against the 35 a "
        "model needs, so no arm ever sits in cash for want of training rows. FIVE VARIANTS, THE "
        "ONLY SETTINGS EVER TRIED, none chosen by looking at a dev result: R10 is the ten-year "
        "rolling window on M0131-B20's tree; R5 is the five-year window on the same tree; EXP is "
        "the unchanged expanding window, which is B20's economics under this method's allocator "
        "and therefore BOTH the in-batch control and a correctness check -- if EXP does not "
        "reproduce B20's recorded numbers the wrapper has a bug and the batch is void; R10REG is "
        "the ten-year window read with M0131's regularised tree, the secondary question of whether "
        "forgetting (40% fewer training rows) restores the capacity ordering M0131 reversed; DV20 "
        "is the CONTROL, M0131's gated 20-name dollar-volume book re-run here so the "
        "what-does-the-model-add comparison never crosses a trial boundary. Every arm is gated: "
        "M0130's ungated arms fell about 70% in 2008 and the switch has helped 22 of 22 lab "
        "variants whole-window. WHAT COUNTS AS AN IMPROVEMENT, FIXED IN ADVANCE AND NOT "
        "NEGOTIABLE AFTERWARDS: a rolling arm beats the expanding arm over 2009-2015 de-funded "
        "AND wins at least 3 of its 4 walk-forward folds. The arm that clears it must be one the "
        "bar named; an arm that clears it by accident is not the result. If neither rolling arm "
        "clears it, the honest reading this method records is that the lab's seven signals "
        "contain no recent edge however the model is trained, and the lab should stop building "
        "rankers on them and go looking for information it does not have. WHAT COUNTS AS A "
        "METHOD: a variant clears every design section 1 bar at DSR >= 0.90 at the lab's N, "
        "against the dev screen on the worst fall (50%) and the real-money bar (25%). No variant "
        "is promoted in this run whatever it shows: the test window is not touched."
    ),
    expected_failure=(
        "Most likely forgetting costs more in sample size than it buys in relevance, and no "
        "rolling arm clears the pre-registered bar. Six reasons, written before the run. First, "
        "the arithmetic: a ten-year window at the 2014 refit holds roughly 108 labelled "
        "month-ends against the expanding window's 216, so about half the rows, and a 252-session "
        "label on monthly samples already overlaps 92% between neighbours, so the EFFECTIVE "
        "sample is perhaps a twentieth of the nominal one either way. Halving an already tiny "
        "effective sample is the most likely way to make a noisy model noisier; the five-year arm "
        "halves it again. Second, M0131's own evidence points the other way on capacity: with a "
        "slow label the FLEXIBLE tree won, which says the model was data-limited, not "
        "regime-confused, and a data-limited model is hurt by forgetting. Third, the roll barely "
        "reaches the 2003-05 fold in the ten-year arm at all (it is identical to the expanding arm "
        "until the 2007 book year), so even a real regime effect can only show in one of the two "
        "folds the method is aiming at, and 3 of 4 folds may be arithmetically out of reach for "
        "R10. Fourth, the result is still a gate result underneath: M0131's exposure was 68% and "
        "its picks alone earned 9.9% a year, so a training-window change can only move the 32% of "
        "the time the book is actually invested, and it cannot touch the cash years 2001, 2002 and "
        "2008 that produced the whole-window win. Fifth, survivorship: the check store already "
        "deepened B20's worst fall from 20.0% to 23.1% and dropped its DSR to 0.839, under the "
        "0.90 bar, so eligibility here rests on a margin measured on data missing four in ten "
        "index-member days -- and a rolling window makes it worse, because a short window weights "
        "the recent, better-covered years less than an expanding one weights them in aggregate. "
        "Sixth, the DSR at N = 86 and rising needs a Sharpe above anything either ranker has "
        "produced, so even an arm that beats the expanding control on return is likely to fail the "
        "luck test. The most informative failure would be R5 beating R10 while both lose to EXP: "
        "that would say the window matters and the direction is the opposite of the one this "
        "method guessed, which is still a finding. The least informative would be all three "
        "within noise of each other, which would close the ranker direction on this signal set."
    ),
    candidates=(
        _v("R10", ROLLING_BOOK, RollingParams(BASE, train_years=DECADE),
           "The ten-year rolling training window on M0131-B20's tree: the method's main arm"),
        _v("R5", ROLLING_BOOK, RollingParams(BASE, train_years=LUSTRUM),
           "The five-year window: the short rung, and the only arm that reaches the 2003-05 fold"),
        _v("EXP", ROLLING_BOOK, RollingParams(BASE),
           "Control: the unchanged expanding window, which must reproduce M0131-B20 exactly"),
        _v("R10REG", ROLLING_BOOK, RollingParams(REG, train_years=DECADE),
           "The ten-year window read with the regularised tree: does forgetting restore capacity?"),
        _v("DV20", DV_BOOK, ControlParams(top_n=20, horizon=YEAR),
           "Control: the same gated 20-name book picked by trading volume, no model"),
    ),
    seen_keys=(
        "concept:rolling-training-window-ranker",
        "concept:forgetting-walk-forward-refit",
        "concept:training-memory-length",
    ),
)

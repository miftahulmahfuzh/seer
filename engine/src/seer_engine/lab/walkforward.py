"""Walk-forward evaluation: many out-of-sample looks, from the window we already have.

**The problem.** A lab method is chosen on one twenty-year window and then gets exactly one
out-of-sample observation, spent at the very end, after the decision to promote has already been
made. One observation cannot tell luck from skill, and by the time it arrives the method is on the
roster and the owner's money is in it. Four of four counted looks have now failed on
``beats SPY TR``, and the deflated Sharpe did not survive the move either -- M0022 went 0.912 on
dev to 0.136 on test.

**The idea.** Roll the split instead of making it once. In each fold, apply the lab's own
selection rule to the *training* slice only -- pick the variant a researcher would have picked
knowing nothing after the train end -- then score that pick on the evaluation slice it has never
seen. The result is a record of how a method's *selection process* behaved out of sample, several
times over, on data the lab already owns, costing no counted look.

A method that wins its dev average but loses three of four folds is not a method. Nothing in the
lab could notice that before.

**It re-runs nothing.** Every recorded trial carries its monthly equity curve, so a fold is a date
slice of rows already in the database. No backtest, no research store, no trial row, no look. The
price of that shortcut is stated rather than hidden:

- **Profit factor and trade count cannot be sliced** from a monthly curve; they need fills. So the
  per-fold rule ranks on MAR, and the caller is expected to have filtered to candidates whose
  whole-window record cleared the non-sliceable conditions. That is a proxy for the real rule.
- **Folds share training data**, so they are not independent observations. Four overlapping folds
  are a sanity check, not a significance test, and nothing here may be fed into a DSR.
- **A funded curve must have its deposits removed first** (``regime.defunded``). From M0032 on
  every trial is funded, and a raw funded curve counts the owner's deposits as growth while the
  benchmark it is measured against receives none.

**Not to be confused with ``backtest.walkforward``**, which is the P3b anchored yearly
walk-forward for Strategy A2: that one re-runs the bracket simulator over a tuning grid and
selects parameters per fold. This module never runs a backtest and never tunes anything -- it
slices curves the lab has already recorded, and the only thing it "selects" is which of a method's
variants the lab's own rule would have named at each point in time. Different engine, different
question, deliberately a different module.

Pure: no I/O, no database, no clock. ``lab walkforward`` supplies the curves.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from seer_engine.backtest.regime import defunded

MIN_TRAIN_YEARS = 10  # a shorter training slice is not a researcher's situation, it is a guess
EVAL_YEARS = 3  # long enough to contain a regime, short enough to leave several folds
MIN_EVAL_MONTHS = 12  # an evaluation slice thinner than this is not evidence


@dataclass(frozen=True, slots=True)
class Fold:
    """One train/evaluate split. ``train`` is everything from the start of the curve."""

    index: int
    train_end: date
    eval_start: date
    eval_end: date


@dataclass(frozen=True, slots=True)
class Slice:
    """What a curve did between two dates, deposits already removed."""

    months: int
    total_return: float | None
    cagr: float | None
    max_drawdown: float | None
    mar: float | None


@dataclass(frozen=True, slots=True)
class FoldPick:
    """The variant the training slice chose, and what it then did unseen."""

    fold: Fold
    picked: str | None  # None when no candidate had enough training history
    train_mar: float | None
    got: Slice | None
    bench: Slice | None

    @property
    def beat(self) -> bool | None:
        """Did the pick's evaluation slice out-return the benchmark's? None when unmeasurable."""
        if self.got is None or self.bench is None:
            return None
        if self.got.total_return is None or self.bench.total_return is None:
            return None
        return self.got.total_return > self.bench.total_return


def folds(
    months: Sequence[date],
    *,
    min_train_years: int = MIN_TRAIN_YEARS,
    eval_years: int = EVAL_YEARS,
) -> tuple[Fold, ...]:
    """Expanding-train, fixed-evaluate splits across ``months`` (a monthly curve's dates).

    The first fold trains on at least ``min_train_years`` and evaluates the ``eval_years`` after
    it; each later fold moves both ends forward by ``eval_years``. A final partial slice is kept
    only when it holds at least ``MIN_EVAL_MONTHS``, so a two-month tail is dropped rather than
    reported as a fold anyone should read.
    """
    if min_train_years < 1 or eval_years < 1:
        raise ValueError("min_train_years and eval_years must both be at least 1")
    ms = sorted(months)
    if len(ms) < 2:
        return ()
    first, last = ms[0], ms[-1]
    out: list[Fold] = []
    train_end = date(first.year + min_train_years, first.month, 1)
    while train_end < last:
        eval_end = date(min(train_end.year + eval_years, last.year + 1), train_end.month, 1)
        in_eval = [d for d in ms if train_end <= d < eval_end]
        if len(in_eval) >= MIN_EVAL_MONTHS:
            out.append(Fold(len(out) + 1, train_end, in_eval[0], min(in_eval[-1], last)))
        train_end = eval_end
    return tuple(out)


def measure(
    curve: Sequence[tuple[date, float]],
    start: date,
    end: date,
    deposits: Mapping[date, float] | None = None,
) -> Slice | None:
    """``curve`` between ``start`` and ``end``, deposits removed. None when too few months.

    The slice is de-funded **before** it is cut, not after: a deposit's effect on later values
    does not stop at a fold boundary, so removing it from the whole series first is the only way
    the cut sees a book that was never fed.
    """
    clean = defunded(list(curve), deposits)
    seg = [(d, v) for d, v in clean if start <= d <= end]
    if len(seg) < 2 or seg[0][1] <= 0:
        return None
    years = (seg[-1][0] - seg[0][0]).days / 365.25
    total = seg[-1][1] / seg[0][1] - 1.0
    cagr = (1.0 + total) ** (1.0 / years) - 1.0 if years > 0 and total > -1 else None
    peak, fall = seg[0][1], 0.0
    for _d, v in seg:
        peak = max(peak, v)
        fall = max(fall, 1.0 - v / peak)
    # A slice that never fell has infinite return per unit of fall, which is the truth and ranks
    # above any finite MAR. Returning None here instead would make `pick` silently drop the best
    # candidate in the slice, because it skips anything it cannot rank.
    if cagr is None:
        mar = None
    elif fall > 0:
        mar = cagr / fall
    else:
        mar = math.inf if cagr > 0 else -math.inf
    return Slice(len(seg), total, cagr, fall, mar)


def pick(
    curves: Mapping[str, Sequence[tuple[date, float]]],
    fold: Fold,
    first: date,
    deposits: Mapping[str, Mapping[date, float]] | None = None,
) -> tuple[str | None, float | None]:
    """The candidate the training slice ranks best by MAR, and that MAR.

    Ties break on the candidate id so the choice is reproducible rather than dict-ordered.
    """
    dep = deposits or {}
    best: tuple[float, str] | None = None
    for cid in sorted(curves):
        got = measure(curves[cid], first, fold.train_end, dep.get(cid))
        if got is None or got.mar is None:
            continue
        if best is None or got.mar > best[0]:
            best = (got.mar, cid)
    return (None, None) if best is None else (best[1], best[0])


def evaluate(
    curves: Mapping[str, Sequence[tuple[date, float]]],
    bench: Sequence[tuple[date, float]],
    the_folds: Sequence[Fold],
    deposits: Mapping[str, Mapping[date, float]] | None = None,
) -> tuple[FoldPick, ...]:
    """One ``FoldPick`` per fold: choose on train, score unseen on evaluate."""
    if not curves:
        return ()
    dep = deposits or {}
    first = min(d for c in curves.values() for d, _v in c)
    out: list[FoldPick] = []
    for fold in the_folds:
        chosen, train_mar = pick(curves, fold, first, dep)
        if chosen is None:
            out.append(FoldPick(fold, None, None, None, None))
            continue
        out.append(
            FoldPick(
                fold,
                chosen,
                train_mar,
                measure(curves[chosen], fold.eval_start, fold.eval_end, dep.get(chosen)),
                measure(bench, fold.eval_start, fold.eval_end),
            )
        )
    return tuple(out)


@dataclass(frozen=True, slots=True)
class Record:
    """A method's whole walk-forward record."""

    method: str
    picks: tuple[FoldPick, ...]

    @property
    def scored(self) -> tuple[FoldPick, ...]:
        return tuple(p for p in self.picks if p.beat is not None)

    @property
    def won(self) -> int:
        return sum(1 for p in self.scored if p.beat)

    @property
    def majority(self) -> bool:
        """Beat the benchmark in more than half the folds that could be scored."""
        n = len(self.scored)
        return n > 0 and self.won * 2 > n

    @property
    def stable(self) -> bool:
        """Did the training slice keep choosing the same variant?

        An unstable record says the choice between a method's variants is noise, which matters:
        the lab spends its one look on whichever variant happened to rank best on the last day.
        """
        names = {p.picked for p in self.picks if p.picked}
        return len(names) <= 1

    def summary(self) -> str:
        n = len(self.scored)
        if n == 0:
            return "no fold could be scored"
        return f"{self.won} of {n} folds" + ("" if self.stable else ", pick changed")


# --------------------------------------------------------------------------- the buy signal

BUY_CONDITIONS = ("dev-eligible", "majority of folds", "positive 2009-2015 edge")


def buy_signal(
    dev_eligible: bool, record: Record, high_coverage_edge: float | None
) -> tuple[bool, str]:
    """Is this the moment survivorship-free price history becomes worth paying for?

    All three must hold: the method is dev-eligible at the bars in force; it beat the benchmark in
    a majority of walk-forward folds; and its edge in the highest-coverage era (2009-2015) is
    positive, so the edge is not an artefact of the half of the universe the store cannot price.

    The third is what makes the purchase about *data*. The dev store prices 48% of index members
    in 1996 and 74% in 2014, and the 522 it cannot price are disproportionately the companies that
    died. A method whose edge lives in the thin early years and dies by 2009-2015 is probably
    reading that hole, and it can be rejected for free. A method that passes all three has used up
    the free evidence, and the next two things that happen are a counted look and real money.

    Returns ``(fired, why)``; ``why`` names the first condition that failed, so a report can say
    what is missing rather than only that nothing happened.
    """
    if not dev_eligible:
        return False, "not dev-eligible"
    if not record.majority:
        return False, f"fails the folds: {record.summary()}"
    if high_coverage_edge is None:
        return False, "no 2009-2015 edge measured"
    if high_coverage_edge <= 0:
        return False, f"negative 2009-2015 edge ({high_coverage_edge * 100:+.1f} pts)"
    return True, (
        f"cleared all three: dev-eligible, {record.summary()}, "
        f"2009-2015 edge {high_coverage_edge * 100:+.1f} pts"
    )

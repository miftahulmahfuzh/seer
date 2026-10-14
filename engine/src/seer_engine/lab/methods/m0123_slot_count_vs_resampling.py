"""M0123 — Hold your shortlist, do not resample it: slot count against swap rate.

Source: variation of M0118 (whose ALWAYS arm is the finding this attacks), with M0097's
S20-ALWAYS as the second anchor. Reserved by Sera 20261014-1206.

**The observation that started this.** Two methods have now held an equal-weight basket carved
out of the same shortlist -- the ``universe`` most-traded point-in-time S&P 500 union Nasdaq-100
members by median dollar volume -- at Gotrade's real fees, monthly, fractional, on the owner's
monthly top-up, over the same 1996-2015 window. M0097-S20-ALWAYS held 20 names and earned +3.2%
a year on the owner's deposits. M0118-ALWAYS held 50 and earned +6.0%. Nearly three points a year
from nothing but slot count -- a bigger gap than any clock this lab has priced, M0084's 200-day
switch included.

**Why that reading is probably wrong, and what this measures instead.** Both of those baskets
were *samples*: every k-th name down the dollar-volume ranking, k = universe // slots. The
ranking is recomputed every month, so a name slides across a sampling boundary and is bought or
sold for no reason connected to any signal. The trade counts say so -- 20 slots took 3479 trades,
50 slots took 5888, while M0097's all-100 arm took 1621. So "slot count" and "resampling churn"
were the same number in both experiments and neither method could tell them apart.

This method separates them. One shortlist, one cadence, one fee model, **no clock anywhere**, and
only two things vary:

    * **how many names the book owns** -- 20, 50 or 100 of the 100;
    * **how it chooses them** -- ``sample=False`` takes the top ``slots`` outright, so a name is
      sold only when it falls out of the top ``slots`` of the shortlist; ``sample=True`` takes
      every k-th name, reproducing the M0118/M0097 construction, which is the churn arm.

At 100 slots the two are the same book (k = 1), so ALL100 is the no-churn limit of the ladder and
is declared ``sample=False``.

**The third lever, which is not a param: where the rebalance band is measured.** The book engine
tops a held name back up only once it is off target by ``RESIZE_BAND`` (1%) **of the whole
account** under ``resize_basis="equity"``, which every recorded trial in this lab used. In a
100-name book each slot *is* 1% of the account, so a monthly deposit can never move a holding far
enough to be topped up: arithmetically, a deposit D into equity E moves a 1% slot by 0.01*D
against a band of 0.01*(E+D), and D >= E+D is never true. Deposits therefore reach the book only
through turnover -- a name leaving the shortlist is sold whole, a name entering is bought whole --
so the arm with the least churn is also the arm that deploys the owner's money slowest. That is
precisely the confound that would make a slot-count ladder unreadable. ALL100-TB is the same
all-100 book on ``MONTHLY_HOLD_FRAC_GOTRADE_TBAND``, where the band is 20% of the holding's *own*
target value and deposits do reach held names; the ALL100 / ALL100-TB pair prices the cash drag
directly, so the rest of the ladder can be read knowing how big it is.

**Why the shared 316-bar lookback.** It is M0118's, to the bar, and it is not a free parameter
here: ``reading_set`` only admits a member carrying ``LOOKBACK_BARS`` of history through d, so
the number decides *which names are on the shortlist at all*. Reusing 316 makes SAMPLE50 the same
configuration M0118-ALWAYS ran and SAMPLE20 the same one M0097-S20-ALWAYS ran, which is what turns
this method's within-method ladder into a bridge to both recorded parents instead of a third
incomparable experiment. The cost is the first ~15 months of 1996-97 spent in cash, which both
parents also paid.

Known bias, written before the run: the shortlist is ranked on dollar volume computed from
split- and dividend-adjusted closes times unadjusted volume, and membership is point-in-time for
d only, so a name that joined the index after a run is on the shortlist no earlier than its
membership but its *rank* is computed from an adjusted price series. The effect is a small,
slot-count-independent reshuffle of the ranking, and it is identical across all six arms, so
every paired difference below is unaffected by it. The shortlist also excludes delisted names
(the dev store prices survivors only), which flatters all six equally.

Fractional shares at Gotrade's real fees, monthly, funded on the owner's monthly top-up. Pure:
reads only bars dated <= d; ``held`` is not read at all, so a name's fate depends on the
shortlist and nothing else.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE, MONTHLY_HOLD_FRAC_GOTRADE_TBAND
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History

ADDED = date(2026, 10, 14)
BENCH = "SPY"
#: Bars of history every variant demands: M0118's, to the bar, so SAMPLE50 is the configuration
#: M0118-ALWAYS ran and SAMPLE20 the one M0097-S20-ALWAYS ran. It also fixes the shortlist's
#: admission test, so all six arms rank the same names on the same sessions.
LOOKBACK_BARS = 316


@dataclass(frozen=True, slots=True)
class ShapeParams:
    universe: int = 100  # names on the shortlist, by median dollar volume
    slots: int = 50  # names held out of it
    sample: bool = False  # True: every k-th name (the churn arm); False: the top `slots`
    dv_n: int = 60  # bars in the median dollar volume

    def __post_init__(self) -> None:
        for name in ("universe", "slots", "dv_n"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int) or v < 1:
                raise ValueError(f"{name} must be an int >= 1, got {v!r}")
        if self.slots > self.universe:
            raise ValueError(f"slots ({self.slots}) must be <= universe ({self.universe})")
        if self.dv_n > LOOKBACK_BARS:
            raise ValueError(f"dv_n ({self.dv_n}) exceeds the shared lookback ({LOOKBACK_BARS})")
        if not isinstance(self.sample, bool):
            raise TypeError(f"sample must be a bool, got {type(self.sample).__name__}")
        if self.sample and self.slots == self.universe:
            raise ValueError(
                "sample=True at slots == universe is the same book as sample=False (k = 1); "
                "declare the all-names arm as sample=False so the two never digest apart"
            )

    def as_dict(self) -> dict[str, str]:
        return {"universe": str(self.universe), "slots": str(self.slots),
                "sample": str(self.sample), "dv_n": str(self.dv_n)}


def _check(params: object) -> ShapeParams:
    if not isinstance(params, ShapeParams):
        raise TypeError(f"params must be ShapeParams, got {type(params).__name__}")
    return params


def shortlist(history: Mapping[str, History], members: AbstractSet[str], data_date: date,
              p: ShapeParams) -> list[str]:
    """The ``universe`` most-traded members carrying a full lookback through d, busiest first.

    Identical in shape and admission test to M0118's ``reading_set``, so the two methods rank
    the same names on the same sessions and SAMPLE50 reproduces M0118-ALWAYS.
    """
    scored: list[tuple[float, str]] = []
    for s in sorted(members):
        if s == BENCH:
            continue
        h = history.get(s)
        if h is None:
            continue
        i = h.index_of(data_date)
        if i is None or i < LOOKBACK_BARS - 1:
            continue
        dv = h.close[i - p.dv_n + 1 : i + 1] * h.volume[i - p.dv_n + 1 : i + 1]
        if not bool(np.all(np.isfinite(dv))):
            continue
        med = float(np.median(dv))
        if not med > 0.0:
            continue
        scored.append((-med, s))
    scored.sort()
    return [s for _, s in scored[: p.universe]]


def chosen_names(ranked: list[str], p: ShapeParams) -> list[str]:
    """``slots`` names out of the shortlist: the top of it, or an evenly spaced sample of it."""
    if not p.sample:
        return ranked[: p.slots]
    step = max(p.universe // p.slots, 1)
    return ranked[::step][: p.slots]


class BookShapeAllocator:
    """An equal-weight basket of the busiest index members; only its shape varies.

    No clock, no signal, no ranking on anything but trading size. Held symbols get no special
    treatment: a name that leaves the chosen set is sold, whatever it has done lately.
    """

    id = "M0123"

    def lookback(self, params: Any) -> int:
        _check(params)
        return LOOKBACK_BARS

    def symbols(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return (BENCH,)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()  # members only: there is nothing to step aside into

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        ranked = shortlist(history, members, data_date, p)
        if not ranked:
            return ()  # no shortlist: stand aside rather than guess
        names = chosen_names(ranked, p)
        if not names:
            return ()
        w = equal_weight(p.slots)
        out: list[Target] = []
        for s in names:
            t = target_from_close(s, last_close(history[s], data_date), w)
            if t is not None:
                out.append(t)
        return tuple(out)

    def prepare(self, history: Mapping[str, History]) -> Any:
        return dict(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self.targets(prepared, members, data_date, held, params)


SHAPE = BookShapeAllocator()


def _v(suffix: str, params: ShapeParams, rationale: str, rules=MONTHLY_HOLD_FRAC_GOTRADE) -> Candidate:
    return Candidate(id=f"M0123-{suffix}", family="M0123", rules=rules, allocator=SHAPE,
                     params=params, rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0123",
    name="Hold your shortlist, do not resample it: separating how many names a book owns from how often it swaps them",
    family="stock-portfolio-construction",
    source_kind="variation",
    source_ref="M0118 (ALWAYS arm) and M0097 (S20-ALWAYS arm): the same basket at two slot counts",
    parent_id="M0118",
    hypothesis=(
        "M0118's no-clock control is the finding, and it is about construction, not timing. Two "
        "methods have now held an equal-weight basket carved from the same shortlist -- the 100 "
        "most-traded point-in-time S&P 500 / Nasdaq-100 members by 60-day median dollar volume -- "
        "at Gotrade's real fees, monthly, fractional, on the owner's top-up, over the same "
        "1996-2015 window: M0097-S20-ALWAYS held 20 and earned +3.2% a year on the deposits; "
        "M0118-ALWAYS held 50 and earned +6.0%. Nearly three points a year from slot count alone, "
        "larger than any clock the lab has priced including M0084's 200-day switch. But the trade "
        "counts say it is probably NOT concentration: 20 slots took 3479 trades and 50 took 5888, "
        "because both SAMPLE the shortlist (every k-th name by dollar-volume rank) and that "
        "ranking reshuffles monthly, so names churn in and out for no reason connected to any "
        "signal. M0097's all-100 arm took only 1621 trades -- but it was CLOCKED, so it is not a "
        "control and must not be quoted as one; that missing control is why this needs its own "
        "run. Design: one shortlist, one cadence, one fee model, no clock anywhere, and vary only "
        "construction, so slot count and resampling stop being the same number. Arms: TOP50 and "
        "TOP20 take the top half and top fifth of the shortlist outright, selling a name only "
        "when it leaves that band; SAMPLE50 and SAMPLE20 take every second and every fifth name, "
        "reproducing the M0118 and M0097 constructions under one shared lookback so the "
        "20-vs-50 comparison is within one method rather than across two; ALL100 holds the whole "
        "shortlist at 1% each, the no-churn limit of the ladder. The sixth arm is not a "
        "construction at all: the book engine tops a held name up only once it is off by 1% of "
        "the WHOLE ACCOUNT, and in a 100-name book each slot is 1% of the account, so a monthly "
        "deposit can never reach a held name and money is deployed only by turnover -- which "
        "would make the least-churning arm also the slowest to invest and the ladder unreadable. "
        "ALL100-TB is the same all-100 book on the target-basis band (20% of the holding's own "
        "target), so the ALL100 / ALL100-TB pair prices that cash drag directly. SUCCESS IS A "
        "MEASUREMENT, NOT ELIGIBILITY: every arm is fully invested in equities with no safety "
        "rule of any kind, so all six carry 2008 in full and none is expected to clear the "
        "real-money 25% worst-fall bar; the dev screen is 50% and a 100-name book of the biggest "
        "members may sit near it, so screening through is possible but is not the point. The "
        "readable numbers are the funded return, the trade count, the money-in-picks share and "
        "the 2009-2015 split. The hypothesis under test: at equal slot count the no-sampling arm "
        "beats the sampling arm, and the gap is roughly the churn the trade counts predict. If "
        "TOP50 beats SAMPLE50 by a point a year or more, every sampled book in the lab is paying "
        "a construction tax that has nothing to do with its signal, and the fix is free."
    ),
    expected_failure=(
        "The most likely outcome is that the slot-count ladder is real but is a cash story, not a "
        "concentration story: ALL100 under the equity band deploys the owner's deposits only "
        "through turnover, and with the least turnover of any arm it may sit on a large and "
        "growing cash pile, so it could post the best money-in-picks-adjusted return and the "
        "worst funded return at once, or the reverse. If ALL100 and ALL100-TB differ by more than "
        "a point a year, nothing in the ladder can be read as slot count until the band is "
        "controlled, and the honest verdict is that the M0097-vs-M0118 gap was never measured. "
        "The second likely failure is that TOP and SAMPLE barely differ: an evenly spaced sample "
        "of a dollar-volume ranking is not a random sample, it is a stratified one, and its "
        "churn may be small enough that the fee difference is tenths of a point rather than the "
        "point-a-year the trade counts suggest -- the extra trades of a sampled book are mostly "
        "tiny boundary swaps whose fee is a few cents on a $28 order. Third, TOP20 is twenty "
        "mega-caps and is close to a cap-weighted index with the weights thrown away, so it may "
        "beat SAMPLE20 for a reason that has nothing to do with churn: it simply owns the "
        "companies that led, which is the market-shape effect M0122 just priced and found costly "
        "to chase. Fourth, all six are fully invested through 2000-2002 and 2008 and will fall "
        "50-60%, so beats-SPY-TR and the worst-fall screen are the conditions that decide "
        "eligibility and the luck bar will be far out of reach at N in the eighties. Not "
        "modelled: interest on idle cash, which matters most to exactly the arm (ALL100) whose "
        "cash pile this method is trying to measure, so the cash drag reported here is an upper "
        "bound on the real one."
    ),
    candidates=(
        _v("ALL100", ShapeParams(slots=100),
           "The whole shortlist at 1% each: the no-churn limit, and the arm the 1%-of-equity band bites hardest"),
        _v("ALL100-TB", ShapeParams(slots=100),
           "The same all-100 book where deposits actually reach held names: the cash-drag control",
           rules=MONTHLY_HOLD_FRAC_GOTRADE_TBAND),
        _v("TOP50", ShapeParams(slots=50),
           "The busiest 50 outright, 2% slots: a name is sold only when it leaves the top half"),
        _v("SAMPLE50", ShapeParams(slots=50, sample=True),
           "Every second name, 2% slots: the M0118-ALWAYS construction, as the churn arm"),
        _v("TOP20", ShapeParams(slots=20),
           "The busiest 20 outright, 5% slots: the concentrated end with no resampling"),
        _v("SAMPLE20", ShapeParams(slots=20, sample=True),
           "Every fifth name, 5% slots: the M0097-S20-ALWAYS construction, under this method's id"),
    ),
    seen_keys=(
        "concept:slot-count-vs-resampling-construction",
        "concept:equal-weight-busiest-members-no-clock",
    ),
)

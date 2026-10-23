"""M0309 — Is the illiquidity book buying an anomaly, or buying bad data? Put the liveness bar back one rung at a time.

Source: variation of M0058 (the Amihud illiquidity book), driven by M0297's two-store reading and
M0298's correction to how a liquidity bar must be specified.

Idea. M0058-ILL20-T is the only book in the lab that earns dramatically *more* when the dead and
delisted companies are put back: M0297 measured it at +12.8%/yr money-weighted on the dev store and
+22.3% on the survivorship-check store, a +9.5 point jump. Nothing else moves like that; the largest
previously recorded move in that direction is +1.3 points (proximity to the 52-week high). Its two
shape-matched blind draws moved the *other* way, so the jump is in the ranking, not the pool or the
chassis.

There is an obvious suspect. M0058 is the only lab book that sets ``min_dollar_volume`` to zero --
its whole idea is to buy the thinnest-traded big names -- and M0284/M0288/M0298 measured that a
dollar-volume bar is a general *liveness* filter: companies go quiet before they die, so refusing
quiet names refuses the ones that vanish. A floorless book is therefore the maximum possible
exposure both to the names the dev store is missing and to the names whose reconstructed EODHD
history is least trustworthy. "Illiquidity pays" and "the thinnest names are the ones the dev store
cannot price" predict the same +9.5 points.

This method separates them with a dose ladder. The identical Amihud-ranked 20-name book runs behind
a **fixed-rank** liveness bar -- keep only the ``dv_rank`` most-traded names of the day's eligible
pool -- at six rungs, and the whole ladder is then read on both tapes. Fixed rank, not a percentile,
is M0298's correction: a percentile bar moves when the pool grows, and here the pool grows a lot.
Measured in this session by streaming each store's ``bars.csv`` against
``research.research_membership()``, the eligible pool (members priced at $5 or more) is::

    1998-12-31   dev 223   sv 406
    2003-12-31   dev 264   sv 443
    2009-12-31   dev 345   sv 504
    2015-10-16   dev 408   sv 519

A percentile bar would therefore cut a different number of names on each tape, every year; a fixed
rank cuts to the same count on both, and the rungs nest exactly.

The rungs are M0298's own -- 0, 250, 200, 150, 100, 50 -- deliberately, so this ladder and M0298's
ladder on the residual-momentum book can be read side by side at matching settings.

What each outcome would mean, written before the run:

    * the two-store gap stays large at every rung -> illiquidity really does pay more once the dead
      are back, and the gap is not about thinness-as-missing-data;
    * the gap collapses as the bar tightens -> the +9.5 points was concentrated in names too thin to
      price honestly, and M0058's dev-eligible status is an artefact of a hole in the tape.

The bar is ``apply_rank`` imported from M0298 rather than re-implemented, so the cut is
bit-identical to the one M0298 measured. Everything else is M0058-ILL20-T's configuration verbatim:
F4's screen with the volume floor removed, the $5 price floor, the SPY 200-day gate, 20 equal-weight
names, Amihud over 252 bar pairs, fractional shares on ``monthly-hold-frac-gotrade``.

Reads only bars dated <= data_date.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0058_illiquidity_premium import (
    OPEN20,
    IlliqParams,
    choose,
    illiq_lookback,
    targets_from_rows,
)
from seer_engine.lab.methods.m0298_fixed_rank_liveness_bar import apply_rank
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    FactorPrepared,
    factor_rows,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 10, 23)

# M0298's rungs, verbatim, so the two ladders can be compared rung for rung.
RUNGS: tuple[tuple[str, int], ...] = (
    ("K0", 0),
    ("K250", 250),
    ("K200", 200),
    ("K150", 150),
    ("K100", 100),
    ("K50", 50),
)


@dataclass(frozen=True, slots=True)
class BarredIlliqParams:
    """``inner`` is M0058-ILL20-T's configuration verbatim; ``dv_rank`` is the only dial.

    ``dv_rank`` is a **count**, not a percentage: keep the this-many most-traded eligible names of
    the day's pool before ranking them on Amihud illiquidity. 0 means no bar, which reproduces
    M0058-ILL20-T. A count rather than a percentile because the eligible pool is nearly twice as
    large on the survivorship-check store as on the dev store (223 vs 406 names at the end of 1998),
    so a percentile would cut a different number on each tape and the ladder would not be a ladder.

    ``inner`` is wrapped rather than extended: ``IlliqParams`` is shared with M0058, and adding a
    field to it would move every config digest M0058 has already recorded.
    """

    inner: IlliqParams
    dv_rank: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.inner, IlliqParams):
            raise TypeError(f"inner must be IlliqParams, got {type(self.inner).__name__}")
        if isinstance(self.dv_rank, bool) or not isinstance(self.dv_rank, int):
            raise TypeError(f"dv_rank must be an int, got {type(self.dv_rank).__name__}")
        if self.dv_rank < 0:
            raise ValueError(f"dv_rank must be >= 0, got {self.dv_rank}")

    def as_dict(self) -> dict[str, str]:
        out = {"dv_rank": str(self.dv_rank)}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> BarredIlliqParams:
    if not isinstance(params, BarredIlliqParams):
        raise TypeError(f"params must be BarredIlliqParams, got {type(params).__name__}")
    return params


@dataclass
class BarredPrepared:
    history: Mapping[str, History]
    factor: FactorPrepared


class BarredIlliquidityAllocator:
    """M0058's illiquidity book with a fixed-rank liveness bar in front of the Amihud ranking.

    The bar runs on the day's eligible rows before anything is scored, so the ranking never sees a
    name the bar removed. Held symbols get no special treatment: a name that leaves the top set is
    signal-exited, exactly as in M0058.
    """

    id = "M0309"

    def lookback(self, params: Any) -> int:
        return illiq_lookback(_check(params).inner)

    def symbols(self, params: Any) -> tuple[str, ...]:
        inner = _check(params).inner.inner
        return (inner.trend[0],) if inner.trend is not None else ()

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if not trend_on(history, data_date, p.inner.inner):
            return ()
        rows = apply_rank(factor_rows(history, members, data_date, p.inner.inner), p.dv_rank)
        return targets_from_rows(choose(rows, history, data_date, p.inner), p.inner)

    def prepare(self, history: Mapping[str, History]) -> BarredPrepared:
        return BarredPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, BarredPrepared):
            raise TypeError(f"prepared must be BarredPrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not trend_on(prepared.history, data_date, p.inner.inner):
            return ()
        rows = apply_rank(prepared.factor.rows_on(members, data_date, p.inner.inner), p.dv_rank)
        return targets_from_rows(choose(rows, prepared.history, data_date, p.inner), p.inner)


BARRED = BarredIlliquidityAllocator()

BASE = IlliqParams(OPEN20, side="illiquid")  # M0058-ILL20-T's parameters verbatim


def _v(suffix: str, dv_rank: int, rationale: str) -> Candidate:
    return Candidate(id=f"M0309-{suffix}", family="M0309", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=BARRED, params=BarredIlliqParams(BASE, dv_rank=dv_rank),
                     rationale=rationale, added=ADDED, owner_inputs=())


_RATIONALE = {
    0: "No bar: M0058-ILL20-T's configuration under a new allocator, the ladder's anchor rung",
    250: "Keep the 250 most-traded eligible names, then hold the 20 most illiquid of those",
    200: "Keep the 200 most-traded: the first rung that bites on the dev tape in every year",
    150: "Keep the 150 most-traded: both tapes cut well below their smallest pool",
    100: "Keep the 100 most-traded: the two tapes' kept sets should now largely coincide",
    50: "Keep the 50 most-traded: the forced-agreement rung, where any two-store gap left is not thinness",
}


METHOD = Method(
    id="M0309",
    name=(
        "Is the illiquidity book buying an anomaly or buying bad data? "
        "Put the volume floor back one rung at a time, on both tapes"
    ),
    family="stock-illiquidity-premium",
    source_kind="variation",
    source_ref="variation of M0058; two-store reading from M0297, fixed-rank bar from M0298",
    parent_id="M0058",
    hypothesis=(
        "The thin-stock book is the only book in the lab that earns dramatically more once the dead "
        "and delisted companies are put back: M0297 measured M0058-ILL20-T at +12.8%/yr "
        "money-weighted on the dev store against +22.3% on the survivorship-check store, a +9.5 "
        "point jump, where the largest move previously recorded in that direction is +1.3 points. "
        "Its two shape-matched blind draws moved the other way, so the jump lives in the ranking, "
        "not the pool or the chassis. M0058 is also the only lab book with no dollar-volume floor "
        "at all, and M0284/M0288/M0298 measured that such a floor is a general liveness filter -- "
        "companies go quiet before they die -- so a floorless book is the maximum possible exposure "
        "to exactly the names the dev tape is missing and whose reconstructed history is least "
        "trustworthy. This runs the identical Amihud-ranked 20-name book behind a fixed-rank "
        "liveness bar at six rungs (no bar, then the 250, 200, 150, 100 and 50 most-traded names of "
        "the day's eligible pool) and reads the two-store gap at each rung. A fixed count rather "
        "than a percentile because the eligible pool is 223 names on dev against 406 on the "
        "survivorship store at the end of 1998 and 408 against 519 in 2015 (measured this session "
        "from each store's bars against point-in-time membership), so a percentile bar would cut a "
        "different number of names on each tape; the rungs are M0298's own so the two ladders can "
        "be compared setting for setting. Success for the anomaly reading: the gap stays large at "
        "every rung, so illiquidity genuinely pays more once the dead are back. Success for the "
        "artefact reading: the gap collapses as the bar tightens, which says the +9.5 points was "
        "concentrated in names too thin to price honestly, and the parent's dev-eligible status is "
        "a hole in the tape. The K50 rung is the built-in null: the 50 most-traded names are nearly "
        "the same companies on both tapes, so any gap surviving there is not about thinness."
    ),
    expected_failure=(
        "The ladder is monotone and uninformative because tightening the bar simply deletes the "
        "strategy: an illiquidity book behind a liquidity floor is a contradiction, and at the "
        "tight rungs the 20 'most illiquid of the 100 most traded' are just ordinary large "
        "companies, so every rung below 150 collapses toward the parent's own most-liquid control "
        "and the return falls away for a reason that has nothing to do with survivorship. If the "
        "return and the gap fall together at the same rate, the ladder cannot separate the two "
        "readings and the honest finding is that this book cannot be made honest -- in which case "
        "its id should not be spent on a test look. Separately, the parent is already a poor "
        "candidate on evidence the lab is allowed to see: its 2009-2015 record is negative on both "
        "tapes (-1.7 and -0.9 points), it fails the lab's first filter, and M0297 showed a coin "
        "toss drawn from its floorless pool clearing every go-live condition at DSR 0.960. Nothing "
        "here is expected to produce a candidate; the deliverable is the shape of the gap."
    ),
    candidates=tuple(_v(s, k, _RATIONALE[k]) for s, k in RUNGS),
    seen_keys=(
        "concept:illiquidity-liveness-bar-dose-ladder",
        "concept:survivorship-gap-vs-liquidity-bar",
    ),
)

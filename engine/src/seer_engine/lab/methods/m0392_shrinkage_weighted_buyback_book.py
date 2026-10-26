"""M0392 — Hold a doubtful buyback name smaller instead of throwing it out.

Source: variation of M0380 (itself M0378 → M0375 → M0371 → M0227, Pontiff & Woodgate 2008).
Reserved by Sera batch 20261026-1320 as an ``idea`` row; this file refines it and keeps its id.

Idea. The buyback book (M0227) ranks index members by how much their split-adjusted share count
shrank over the trailing year and holds the twenty biggest shrinkers. Four separate CONFIRMATION
filters have now been laid on that book and all four cost it money against its own no-veto twin,
measured on the owner's deposits: M0375's six-month pace veto +10.3% a year against +12.8% (2.5
points), M0378's year-over-year pace veto +9.3% against +12.1% (2.8 points), and M0380's two price
vetoes +9.1% against +13.3% (4.2 points, outright weakness) and +10.2% against +13.3% (3.1 points,
weakness against the index) -- ``lab show M0375``, ``lab show M0378``, ``lab show M0380``,
2026-10-26.

What all four share is the SAME mechanism, and it is visible in the trade counts rather than the
returns. M0375's unfiltered arm traded 713 times and its filtered arm 1337; M0380's unfiltered arm
traded 609 and its two filtered arms 1378 and 1350 (the same ``lab show`` rows). A veto does not
simply hold nineteen names instead of twenty: it must reach further down the ranked list to refill
the slot it emptied, the replacement is by construction a SMALLER shrinker, and the name that
refills a slot this month is not the name that refills it next month. So a veto buys a weaker pick
and pays roughly double the trading for it.

This variation removes that mechanism entirely. Hold the SAME names the unfiltered book holds --
never reach past the top ``top`` -- and vary only HOW MUCH of each is held, scaled by how hard that
company is actually shrinking its share count, with a weight ceiling so one name cannot dominate
(M0047's lesson). Nothing is ever replaced, so the refill cost that sank all four vetoes cannot
arise, and the only thing being asked is whether the rank the book already trusts carries usable
information in its MAGNITUDE as well as its order.

The honest prior is against it. M0047 sized a momentum book by company size instead of equal slots
and the verdict was "Sizing the momentum picks by company size cost 2.5 to 3.3 points a year, did
not soften the worst fall, and lost to SPY in 2009-2015; equal slots stay better" (``lab show
M0047``, 2026-10-26). That was a different score on a different book, but it is the lab's one prior
reading on replacing equal slots with a score-proportional weight, and it says the weighting cost
about what the vetoes cost. If this run lands in the same place the finding generalises: on this
lab's books, equal slots are not a convenience, they are the best use of a cross-sectional rank.

The pool and the book. ``m0227_net_share_shrinkers.scored_pool`` unmodified -- M0227's own
trailing-twelve-month log share-count change, its missed-split and units-error guards, its 180-day
minimum count gap, and the identical-share-count dedupe this family uses (larger 60-session trading
value wins). One deviation from M0227, fixed here and never retuned: the book is the ``top``
biggest shrinkers **among members whose score is actually negative**. A book of shrinkers contains
only shrinkers. It costs almost nothing in the thick years (the top twenty of a few hundred scored
members are genuine shrinkers in any ordinary month) and it is what makes a weight proportional to
shrinkage well defined -- a name that issued stock has no shrinkage to be proportional to. In a
month with fewer than ``top`` genuine shrinkers every arm holds fewer names, equally, and that is
reported as lower exposure rather than papered over.

The weighting. ``weighting="equal"`` gives every name 1/n: the no-opinion twin, the arm the whole
file exists to beat. ``weighting="shrink"`` gives every name a share proportional to its own
shrinkage (``max(0, -score)``), normalised to one, then puts a ceiling ``cap_bp`` on any single
name and redistributes the excess proportionally among the names still under it, repeating until
none is over. ``weighting="hash"`` is the blind re-weighting: it takes the EXACT weight vector
``"shrink"`` would produce at the same ceiling on the same date and re-assigns it to the same names
in a date-free hash order (``lab.control_draw.keep_key``). The multiset of weights is identical by
construction -- same dispersion, same ceiling, same full investment, same names, same entries and
exits -- and only the mapping from name to weight is blind. That is a far better-matched control
than a name draw can be, and it is matched because the two arms are the same book.

The tape. Arms run on ``monthly-hold-frac-gotrade-tband``: fractional shares at Gotrade's real
fees, asked monthly, with the resize band measured against each holding's OWN target (20% of its
slot) instead of 1% of the whole account. That choice is forced, not stylistic. Under the account
basis a 5% holding in a twenty-name book must drift 20% of itself before anything trades and a 10%
holding must drift 10% of itself, so the account basis would maintain a big slot twice as tightly
as a small one -- it would re-weight the book as a side effect of measuring it. The target basis
maintains every slot to the same proportional tolerance, which is the only tape on which "vary only
how much of each is held" means what it says. The band is not shut to zero, deliberately: Gotrade's
trading fee has a $0.10 minimum, so a full rebalance of twenty names every month would pay that
minimum on dollar-sized trims, and a time-varying weight vector trims more often than a fixed one
-- the cost of the minimum would land on the treatment arms and not on the control, which is a
handicap dressed as a result. One sixth arm, ``EQ20-FAM``, runs the identical equal-weight book on
the family's own ``monthly-hold-frac-gotrade`` so the tape's own cost is priced separately from the
weighting's, and so the file is anchored to a number the lab already holds (M0227-S20, +13.0% a
year funded).

Market-aware (``market_fields = ("shares",)``): the history-only path has no share counts, so by
the contract it targets nothing. Pure: reads only bars and counts public on or before
``data_date``.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab import control_draw
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0227_net_share_shrinkers import DV_N, IssuancePrepared, scored_pool
from seer_engine.sim.book import WEIGHT_QUANTUM, Target, equal_weight, to_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE, MONTHLY_HOLD_FRAC_GOTRADE_TBAND
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import FactorParams, trend_on

ADDED = date(2026, 10, 26)
WEIGHTINGS = ("equal", "shrink", "hash")
BENCH = "SPY"
TAG = "M0392"  # the hash arm's draw tag: this method's id, so its order is its own
MIN_WEIGHT = float(WEIGHT_QUANTUM)  # a slot this small cannot be expressed; see ``_weights``


@dataclass(frozen=True, slots=True)
class ShrinkWeightParams:
    """``top`` names held (the biggest genuine shrinkers, never more); ``weighting`` how the slots
    are sized -- "equal" (the no-opinion twin), "shrink" (proportional to each name's own
    twelve-month share-count fall) or "hash" (the blind control: "shrink"'s own weight vector
    re-assigned to the same names by a date-free hash); ``cap_bp`` the ceiling on any one name in
    basis points of the book, 0 on the equal arm where no ceiling applies; ``seed`` the hash arm's
    draw seed; ``trend`` the switch, (symbol, n) or None, set by every variant."""

    top: int
    weighting: str = "shrink"
    cap_bp: int = 1000
    seed: int = 0
    trend: tuple[str, int] | None = None

    def __post_init__(self) -> None:
        if isinstance(self.top, bool) or not isinstance(self.top, int) or not 1 <= self.top <= 200:
            raise ValueError(f"top must be an int in [1, 200], got {self.top!r}")
        if self.weighting not in WEIGHTINGS:
            raise ValueError(f"weighting must be one of {WEIGHTINGS}, got {self.weighting!r}")
        if isinstance(self.cap_bp, bool) or not isinstance(self.cap_bp, int):
            raise TypeError(f"cap_bp must be an int, got {type(self.cap_bp).__name__}")
        if self.weighting == "equal":
            if self.cap_bp != 0:
                raise ValueError(f"the equal arm has no ceiling: cap_bp must be 0, got {self.cap_bp}")
        else:
            if not 0 < self.cap_bp <= 10000:
                raise ValueError(f"cap_bp must be in (0, 10000], got {self.cap_bp}")
            if self.cap_bp * self.top <= 10000:
                raise ValueError(
                    f"a ceiling of {self.cap_bp} bp on {self.top} names is at or below equal "
                    "weight, which would silently make a weighted arm an equal-weight arm"
                )
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise ValueError(f"seed must be a non-negative int, got {self.seed!r}")
        FactorParams(rank="momentum", top=self.top, trend=self.trend)  # validates the switch

    def as_dict(self) -> dict[str, str]:
        return {"top": str(self.top), "weighting": self.weighting, "cap_bp": str(self.cap_bp),
                "seed": str(self.seed),
                "trend": "none" if self.trend is None else f"{self.trend[0]}:{self.trend[1]}",
                "pool": "m0227-scored-pool", "book_rule": "negative-score-only",
                "dv_n": str(DV_N), "class_rule": "identical-share-count",
                "min_weight": repr(MIN_WEIGHT), "tag": TAG}


def _check(params: object) -> ShrinkWeightParams:
    if not isinstance(params, ShrinkWeightParams):
        raise TypeError(f"params must be ShrinkWeightParams, got {type(params).__name__}")
    return params


def _gate(p: ShrinkWeightParams) -> FactorParams:
    return FactorParams(rank="momentum", top=p.top, trend=p.trend)


def shrinkers(pool: Mapping[str, float], top: int) -> tuple[str, ...]:
    """The ``top`` biggest genuine shrinkers in ``pool``, most negative score first.

    Only a negative score is a shrinker. A month with fewer than ``top`` of them holds fewer
    names -- in EVERY arm equally, so the arms stay comparable -- rather than reaching into the
    issuers to fill a slot, which is the refill cost this whole method exists to avoid."""
    order = sorted((s for s in pool if pool[s] < 0.0), key=lambda s: (pool[s], s))
    return tuple(order[:top])


def capped(raw: list[float], cap: float) -> list[float]:
    """``raw`` (non-negative, summing to one) with no entry above ``cap``, the excess pushed
    proportionally onto the entries still below it, repeated until none is over.

    Terminates because every pass freezes at least one more entry at ``cap``. When every entry is
    frozen the weights are equal at ``cap`` and the caller's ``cap * n > 1`` validation makes that
    unreachable, so the uncapped total is never empty while an entry is still over."""
    n = len(raw)
    w = list(raw)
    frozen = [False] * n
    while True:
        over = [i for i in range(n) if not frozen[i] and w[i] > cap]
        if not over:
            return w
        for i in over:
            w[i] = cap
            frozen[i] = True
        free = 1.0 - cap * sum(frozen)
        total = sum(w[i] for i in range(n) if not frozen[i])
        if total <= 0.0 or free <= 0.0:
            return w
        scale = free / total
        for i in range(n):
            if not frozen[i]:
                w[i] *= scale


def weights_for(names: tuple[str, ...], pool: Mapping[str, float],
                p: ShrinkWeightParams) -> list[float]:
    """One weight per name in ``names``, summing to one (bar a 1e-12 safety shave).

    "equal": 1/n. "shrink": each name's own shrinkage as a share of the book's, then ``cap_bp``.
    "hash": the "shrink" vector of THIS book on THIS date, sorted biggest first and handed back to
    the same names in ``control_draw.keep_key`` order -- date-free, so a name keeps its rung while
    the book is unchanged and the control does not churn for a reason the book it controls never
    has (the sticky-versus-redrawn distinction: a re-drawn order would trade far more and price
    the churn instead of the weighting)."""
    n = len(names)
    if n == 0:
        return []
    if p.weighting == "equal":
        return [1.0 / n] * n
    intensity = [max(0.0, -pool[s]) for s in names]
    total = sum(intensity)
    raw = [x / total for x in intensity] if total > 0.0 else [1.0 / n] * n
    w = capped(raw, p.cap_bp / 10000.0)
    shave = sum(w)
    if shave > 0.0:
        w = [x / shave * (1.0 - 1e-12) for x in w]
    if p.weighting == "shrink":
        return w
    order = sorted(range(n), key=lambda i: (control_draw.keep_key(TAG, p.seed, names[i]), names[i]))
    rungs = sorted(w, reverse=True)
    out = [0.0] * n
    for rung, i in enumerate(order):
        out[i] = rungs[rung]
    return out


class ShrinkWeightAllocator:
    """The ``top`` biggest genuine shrinkers by trailing-year share-count level, held in equal
    slots, in slots proportional to each name's own shrinkage under a ceiling, or in that same
    vector of slots handed out by a blind date-free hash; fully invested; nothing while the
    switch, if any, is off. No share counts (history-only path): no targets."""

    id = "M0392"
    market_fields = ("shares",)

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return max(DV_N, 0 if p.trend is None else p.trend[1])

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return (BENCH,) if p.trend is None else tuple(sorted({BENCH, p.trend[0]}))

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(self, prepared: IssuancePrepared, members: AbstractSet[str], data_date: date,
             p: ShrinkWeightParams) -> tuple[Target, ...]:
        if prepared.market is None:
            return ()
        if not trend_on(prepared.history, data_date, _gate(p)):
            return ()
        pool = scored_pool(prepared, members, data_date)
        if not pool:
            return ()
        names = shrinkers(pool, p.top)
        if not names:
            return ()
        ws = weights_for(names, pool, p)
        out: list[Target] = []
        for s, x in zip(names, ws, strict=True):
            if x < MIN_WEIGHT:  # below the weight quantum: the slot cannot be expressed at all
                continue
            t = target_from_close(s, last_close(prepared.history[s], data_date), to_weight(x))
            if t is not None:
                out.append(t)
        return tuple(out)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no share counts, so no signal and no target."""
        return self._run(IssuancePrepared(history, None), members, data_date, _check(params))

    def prepare(self, history: Mapping[str, History]) -> IssuancePrepared:
        return IssuancePrepared(history, None)

    def prepare_market(self, market: Any) -> IssuancePrepared:
        if not hasattr(market, "shares") or len(market.shares) == 0:
            return IssuancePrepared(market.history, None)
        return IssuancePrepared(market.history, market)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, IssuancePrepared):
            raise TypeError(f"prepared must be IssuancePrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, _check(params))


SHRINKW = ShrinkWeightAllocator()

SW = ("SPY", 200)


def _v(suffix: str, params: ShrinkWeightParams, rationale: str,
       rules=MONTHLY_HOLD_FRAC_GOTRADE_TBAND) -> Candidate:
    return Candidate(id=f"M0392-{suffix}", family="M0392", rules=rules, allocator=SHRINKW,
                     params=params, rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0392",
    name="Hold a doubtful buyback name smaller instead of throwing it out",
    family="stock-net-share-issuance",
    source_kind="variation",
    source_ref="M0380",
    parent_id="M0380",
    hypothesis=(
        "Four confirmation filters have now been laid on the buyback book and all four cost it "
        "money against its own no-veto twin, on the owner's deposits: M0375's six-month pace veto "
        "earned +10.3% a year against +12.8% (2.5 points), M0378's year-over-year pace veto +9.3% "
        "against +12.1% (2.8 points), and M0380's two price vetoes +9.1% against +13.3% (4.2 "
        "points, outright weakness) and +10.2% against +13.3% (3.1 points, weakness against the "
        "index) -- 'lab show M0375', 'lab show M0378', 'lab show M0380', 2026-10-26. The trade "
        "counts in those same rows name the mechanism: M0375 traded 713 times unfiltered and 1337 "
        "filtered; M0380 traded 609 unfiltered and 1378 and 1350 filtered. A veto does not hold "
        "nineteen names instead of twenty -- it reaches further down the ranked list to refill the "
        "slot it emptied, the replacement is by construction a smaller shrinker, and the refilling "
        "name changes from month to month. A weaker pick at roughly double the trading. This "
        "method removes that mechanism entirely rather than trying a fifth veto. Hold the SAME "
        "names the unfiltered book holds -- never reach past the top twenty -- and vary only how "
        "much of each is held, proportional to how hard that company is actually shrinking its own "
        "share count, under a ceiling so one name cannot dominate (M0047's lesson). Nothing is "
        "ever replaced, so the refill cost cannot arise, and the single question is whether the "
        "rank this book already trusts carries usable information in its MAGNITUDE as well as its "
        "order. Book: the twenty biggest genuine shrinkers (a negative score only) by M0227's own "
        "trailing-twelve-month share-count level, its guards and its identical-share-count dedupe "
        "unmodified; fractional shares at Gotrade's real fees on the owner's monthly top-up, asked "
        "monthly, with the resize band measured against each holding's own slot "
        "(monthly-hold-frac-gotrade-tband) because an account-basis band would maintain a 10% slot "
        "twice as tightly as a 5% one and so re-weight the book as a side effect of measuring it. "
        "Target max drawdown 20% or less, gains-to-losses 1.3 or better, well over 100 trades. "
        "Arms, all on the identical book: EQ20, equal slots -- the no-opinion twin every weighted "
        "arm has to beat; SHRINK20-C10, slots proportional to shrinkage under a 10% ceiling (twice "
        "equal weight); SHRINK20-C075, the tighter 7.5% rung of the same ceiling ladder; "
        "PLC20-C10, the blind control, which takes SHRINK20-C10's OWN weight vector on the same "
        "date and hands it to the same names in a date-free hash order, so dispersion, ceiling, "
        "names, entries and exits are identical by construction and only the mapping from name to "
        "weight is blind; SHRINK20-C10-SW, the weighted arm behind the SPY 200-day switch, the "
        "only construction in this family that has ever reached the drawdown bar; and EQ20-FAM, "
        "the identical equal-weight book on the family's own monthly-hold-frac-gotrade, which "
        "prices the tape change separately from the weighting and anchors this file to a number "
        "the lab already holds (M0227-S20 earned +13.0% a year funded). Every ceiling is fixed now "
        "and never retuned. Success is SHRINK20-C10 beating EQ20 by more than a point a year AND "
        "beating PLC20-C10 by more than 1.5 points a year, the lab's own measured width for a "
        "single shuffling seed. Exposure is read beside every return: M0374 bought a better luck "
        "reading by investing 57% of the account and then won only one of four folds, so an arm "
        "here that wins while holding less than a full book has not won."
    ),
    expected_failure=(
        "Four ways, in order of likelihood. (1) The weighting costs about what the vetoes cost. "
        "This is the honest prior and it has a measurement behind it: M0047 sized a momentum book "
        "by company size instead of equal slots and its verdict reads 'Sizing the momentum picks "
        "by company size cost 2.5 to 3.3 points a year, did not soften the worst fall, and lost to "
        "SPY in 2009-2015; equal slots stay better' ('lab show M0047', 2026-10-26). A different "
        "score on a different book, but the lab's one prior reading on replacing equal slots with "
        "a score-proportional weight, and it points the same way the four vetoes point. If "
        "SHRINK20-C10 lands two to three points below EQ20 the finding generalises beyond this "
        "book: on this lab's cross-sectional ranks, equal slots are not a convenience but the best "
        "use of the rank, because the rank orders well and measures badly. That is the outcome "
        "this file expects. (2) Indistinguishable from the blind re-weighting. The hash arm holds "
        "the same names with the same spread of slot sizes, so if the two land within 1.5 points a "
        "year of each other the magnitudes carry no information and the dispersion alone explains "
        "whatever moved -- a rejection, and a cleaner one than any name-draw in this family has "
        "been able to give, because this control is matched by construction rather than by a "
        "turnover formula. (3) Concentration bought with risk, not skill. A proportional weight on "
        "a right-skewed score concentrates the book, so SHRINK20-C10 may beat EQ20 on return while "
        "its worst fall deepens and its gains-to-losses ratio falls; the tighter C075 rung is in "
        "the run precisely so this reads as a ladder -- if return and fall both rise monotonically "
        "from C075 to C10, the arm bought leverage on the top name and not a better book, and the "
        "ladder says so without a second method. (4) The family's 2009-2015 shortfall survives. "
        "Every member of this family has been weak in the best-covered years and re-weighting "
        "twenty names it already holds does not change where the underlying rank earns its money; "
        "a twenty-year win with a negative 2009-2015 split is a rejection here as it has been "
        "everywhere else in this family. A fifth possibility worth naming because it would look "
        "like success: the switched arm SHRINK20-C10-SW reaches the drawdown bar and the DSR bar "
        "while the unswitched weighted arm does not. That would be the switch, which every "
        "switched arm in this family already has, and not the weighting -- readable because EQ20 "
        "and SHRINK20-C10 are in the same run on the same tape. Any of these is a rejection. None "
        "is a reason to retune the ceilings, the top of twenty, the negative-score book rule or "
        "M0227's guards afterwards."
    ),
    candidates=(
        _v("EQ20", ShrinkWeightParams(20, weighting="equal", cap_bp=0, trend=None),
           "Control: the same twenty shrinkers in equal slots on the same tape -- the no-opinion "
           "twin every weighted arm has to beat, and the arm that says what the weighting is "
           "worth"),
        _v("SHRINK20-C10", ShrinkWeightParams(20, weighting="shrink", cap_bp=1000, trend=None),
           "The idea: the same twenty names, each held in proportion to its own twelve-month "
           "share-count fall, no name above 10% of the book (twice an equal slot)"),
        _v("SHRINK20-C075", ShrinkWeightParams(20, weighting="shrink", cap_bp=750, trend=None),
           "The tighter rung of the ceiling ladder: the same proportional weighting with no name "
           "above 7.5% of the book, so concentration reads as a dose and not as a second method"),
        _v("PLC20-C10", ShrinkWeightParams(20, weighting="hash", cap_bp=1000, seed=1, trend=None),
           "Placebo, matched by construction: SHRINK20-C10's own weight vector on the same date, "
           "handed to the same twenty names in a date-free hash order -- identical dispersion, "
           "ceiling, names, entries and exits, blind only in which name gets which slot"),
        _v("SHRINK20-C10-SW", ShrinkWeightParams(20, weighting="shrink", cap_bp=1000, trend=SW),
           "SHRINK20-C10 behind the SPY 200-day switch, the only construction in this family that "
           "has reached the drawdown bar"),
        _v("EQ20-FAM", ShrinkWeightParams(20, weighting="equal", cap_bp=0, trend=None),
           "Control: the identical equal-weight book on the family's own monthly-hold-frac-gotrade "
           "tape, which prices the band change on its own and anchors this file to M0227-S20",
           rules=MONTHLY_HOLD_FRAC_GOTRADE),
    ),
    seen_keys=(
        "concept:shrinkage-weighted-buyback-book",
        "concept:score-proportional-weights-instead-of-a-veto",
    ),
)

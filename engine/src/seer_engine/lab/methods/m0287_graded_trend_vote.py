"""M0287 -- Many speeds, graded exposure: does a VOTE across trend horizons beat one on-off line?

Source: Faber (2007), "A Quantitative Approach to Tactical Asset Allocation", SSRN 962461, for
the long-moving-average switch and for the claim this method exists to test -- that the rule is
broadly insensitive to its horizon, with the 200-day and 252-day versions statistically
indistinguishable; Moskowitz, Ooi & Pedersen (2012), "Time Series Momentum", JFE 104(2), for the
same insensitivity measured across one-, three-, six- and twelve-month look-backs. The chassis,
the store and the two measured prices of cash come from M0271 and M0270, which are this file's
parents in everything but the citation.

-------------------------------------------------------------------------------------------------
THE CLAIM, AND WHY IT IS WORTH A METHOD ID AFTER SIX MONTHS OF GATE TUNING

If four horizons are each individually defensible but disagree on different days, then averaging
their votes GRADES exposure instead of switching it: 0, a quarter, a half, three quarters or all
of the book, instead of all or nothing. This is the single most widely repeated refinement of the
Faber switch in the practitioner literature, and this lab has never run it.

It is worth running HERE, now, because the lab has just measured the two numbers that decide it.
M0270 priced a point of the account held in cash, spread evenly over every session, at **0.1732
points a year** of de-funded lead over 2009-2015 on this exact book, store and era. M0271 then
priced the same point of cash bought in EPISODES -- all-or-nothing, the shape a switch produces --
at **0.2832**. Cash in lumps costs about 1.6 times what the same average cash costs when it is
spread. A graded gate holds the same average cash in smaller, more frequent pieces. So the
hypothesis has an actual arithmetic behind it rather than an aesthetic: grading should buy the
same protection out of cheaper cash.

The danger is the exact opposite reading, and the lab has that scar too. Turning a losing timing
rule DOWN cannot save it: dilution halves the good half and the bad half together and leaves the
ratio invariant at about 0.69 (measured on the rate-trend lean, M0281). On that reading a vote is
simply the 200-day gate run at a lower average exposure with a story attached, and is worth
nothing at all.

-------------------------------------------------------------------------------------------------
THE TRAP THE OBVIOUS DESIGN FALLS INTO, FOUND BEFORE THIS FILE WAS WRITTEN

The obvious arm is the literature's own set -- 50, 100, 200 and 252 days -- against the lab's
single 200-day gate. `docs/backtests/2026-10-23-graded-trend-vote.py` measured that on SPY's own
closes, monthly, unfunded, before a word of this file existed:

    arm                                  average exposure   UNFUNDED CAGR   worst fall
    the single 200-day gate                      73.42%          8.07%        19.03%
    the 50/100/200/252 vote                      70.57%          6.36%        21.24%

The vote loses 1.7 points a year AND falls 2.2 points deeper. A run of that pair alone would have
been read as "grading fails", and it would have been the wrong conclusion, because the comparison
confounds TWO changes at once. Moving the same probe over horizon sets centred on 200 instead
separates them:

    horizon set                     mean horizon   exposure   UNFUNDED CAGR   worst fall
    200 (the lab's gate)                   200      73.42%        8.07%         19.03%
    150 / 250                              200      73.21%        8.00%         19.41%
    125 / 175 / 225 / 275                  200      72.68%        7.58%         19.03%
    125 .. 275, eight horizons             200      73.10%        7.87%         19.03%
    50 / 117 / 185 / 252                   151      70.89%        6.74%         18.73%
    50 / 100 / 200 / 252 (the paper's)     151      70.57%        6.36%         21.24%

**Nearly the whole of the published vote's shortfall is its CENTRE OF GRAVITY, not its grading.**
Every set centred on 200 lands within half a point of the single gate; every set centred near 150
loses one and a half points. The 50-day horizon is simply a worse timer than the 200-day one on
this tape, and a vote that includes it is a worse rule for that reason alone. Averaging four
horizons that span 50 to 252 does not hold the gate's opinion and grade it; it REPLACES the gate's
opinion with a faster one and grades that.

So this method holds the mean horizon fixed at 200 and moves ONLY how finely the same average
opinion is expressed.

-------------------------------------------------------------------------------------------------
THE INSTRUMENT: k EVENLY SPACED HORIZONS ON [125, 275], FOR k = 1, 4 AND 8

    horizons(k) = k values evenly spaced across [125, 275], rounded to whole sessions

    k = 1   200                                          2 exposure levels   -- the lab's own gate
    k = 4   125, 175, 225, 275                            5 exposure levels
    k = 8   125, 146, 168, 189, 211, 232, 254, 275        9 exposure levels

Every set sums to exactly 200 x k, so the mean horizon is 200 at every rung and the span is 150 at
every rung above one. **k = 1 is not a foreign comparison bolted on beside the ladder: it IS the
ladder's first rung**, the degenerate single-horizon member of the same family, and it computes
`close > SMA(200)` on SPY, which is `f_factor.trend_on` with `("SPY", 200)` -- the identical rule
every gated book in this lab already runs. The incumbent is rung zero of the experiment.

**THE LADDER IS EXPOSURE-MATCHED BY CONSTRUCTION, WHICH IS BETTER THAN AN EXPOSURE-MATCHED
CONTROL.** Measured off SPY's bars in advance and reading no return: the three rungs sit at 73.42,
72.68 and 73.15 percent of monthly decisions invested -- a spread of 0.74 points. The lab's own
published tolerance is to match exposure to half a point and skip the correction (M0270), so this
is 0.24 points outside it, worth about 0.13 points a year at the 2009-2015 price of cash and about
0.004 at the 2003-2008 price. That residual is reported with every rung difference rather than
swept up. The point is that a difference BETWEEN these rungs cannot be dilution, because there is
nothing left to dilute: the dilution reading is excluded by the design rather than by an argument.

That is why the idea row's `G200-DIL` arm has moved. It was specified to dilute the single switch
down to the vote's average exposure, and on the centred ladder there is no gap worth diluting. It
is spent instead where there IS one -- on the published 50/100/200/252 set, which really does run
2.85 points less invested than the gate -- so the control sits on the one arm that needs it.

-------------------------------------------------------------------------------------------------
THE SIX ARMS

    arm     horizons                          levels  predicted exposure   what it is for
    FULL    none, the gate switched off            1        98.6%          the no-opinion endpoint
    K1      200                                    2        72.4%          the lab's shared gate
    K4      125/175/225/275                        5        71.7%          the graded rung
    K8      125/146/168/189/211/232/254/275        9        72.1%          the finest rung
    LIT4    50/100/200/252                         5        69.6%          the published set
    DIL     200, capped at 0.961207                2        69.6%          LIT4's dilution control

The predicted exposures are the decision-session shares above, multiplied by the base book's own
98.57% (its recorded full-weight exposure, M0266 trial 893). They are PREDICTIONS; the realised
numbers are read afterwards and never aimed at.

**FULL is the no-opinion arm and it is registered deliberately** (insight 523). Twenty-two of the
lab's twenty-eight reversed pairs cannot be priced at all because nobody registered theirs, and
"is the opinion worth what the habit costs" is the question that decided every timing rule settled
this month. FULL is the same book never stepping aside and never switching, so the cost of the
HABIT is recoverable here rather than cancelling across a pair. It also costs no method id: it is
one more variant inside the same pre-registration.

**DIL is the single 200-day gate holding 0.961207 of the book when it is on, and nothing when it
is off.** That constant is `LIT4's average decision exposure / K1's`, 0.705696 / 0.734177, read
off SPY's bars before this file was committed and reading no return. It gives DIL exactly LIT4's
whole-window average exposure with the gate's own lumpy shape, so `LIT4 vs DIL` is the published
vote against the single switch at the published vote's own exposure: the dilution question, asked
where it is real. The constant is fixed on the whole scored window because that is the window a
trial's recorded exposure and its MAR are measured over; over 2009-2015 alone the matching ratio
would be 0.944030 instead, so DIL runs about 1.4 points richer than LIT4 in that era and the era
comparison carries that correction explicitly.

-------------------------------------------------------------------------------------------------
THE HOST, AND WHY IT IS THE OPINION-FREE BOOK

M0270's `ExposureLadderBook`, which is M0266's allocator by inheritance: the 50 most-traded index
members at equal weight, band zero, no stock picking, no brake, no memory, at full scale. Chosen
over a book that actually picks, for three reasons that are worth more here than eligibility:

 1. **The two prices of cash this method's hypothesis rests on were measured on it**, on this
    store, in this era. 0.1732 for evenly spread cash and 0.2832 for episodic cash are numbers
    about THIS chassis. On any other host they are borrowed, and a ratio carried between chassis
    is exactly the mistake this lab has paid for twice.
 2. **Two arms reproduce recorded trials to the digit, for free.** FULL is M0270-S100 and
    M0271-OFF with the gate switched off; K1 is M0271-D000. If either fails to reproduce, the file
    has a bug and nothing below may be read. No other host offers that check.
 3. **The book has no opinion of its own to interact with the gate's.** A graded gate on a
    momentum book changes which names the book can afford as well as how much of it is invested.
    Here the names are fixed by dollar volume and nothing else moves.

The price is stated plainly: the base book loses to a deposit-matched SPY and falls past 50
percent, so **no arm here is a candidate and none will be promoted**. Eligibility would be
reported and would still not be acted on. This method's deliverable is a measurement, and the
measurement is the kind that stops the lab spending ids on a refinement that cannot work.

-------------------------------------------------------------------------------------------------
PREDICTIONS, WRITTEN BEFORE ANY RETURN WAS COMPUTED

 1. **FULL reproduces M0270-S100 and M0271-OFF to the digit** on the dev store -- same return,
    same worst fall, same 1338 trades -- because with no horizons the vote is 1 and the subclass
    computes M0266's scale-1 targets and nothing else. **K1 reproduces M0271-D000 to the digit**
    for the same reason. A mismatch is a bug and is chased before anything else is read.
 2. **Realised exposure lands within 2 points of 98.6, 72.4, 71.7, 72.1, 69.6 and 69.6 percent**
    for FULL, K1, K4, K8, LIT4 and DIL. If K1, K4 and K8 do not land within a point of each other
    the exposure match has failed and the graininess ladder may not be read as one.
 3. **GRADING AT A FIXED CENTRE IS NEARLY INERT, AND THAT IS THE HEADLINE I EXPECT.** On SPY alone
    the three rungs span 0.49 points a year (8.07, 7.58, 7.88) and are NOT monotone in k, which is
    the signature of noise rather than a dial. I predict the funded book reproduces that: the
    K1-to-K8 spread stays under 1 point a year whole window, the ordering is not monotone, and the
    worst falls land within 1.5 points of each other. The structural reason is in the level
    histogram: a centred vote is fully invested on 66.7% of decisions and fully out on 20.3%, so
    it agrees with the single gate on 87 percent of them and the grading only bites on the
    remaining 13. **A rule that is the same rule seven times out of eight cannot be worth much.**
 4. **THE FUNDED ANSWER SHOULD BE WORSE FOR THE GRADED ARMS THAN THE UNFUNDED PRIOR, AND BY AN
    AMOUNT THIS METHOD CAN MEASURE.** Weight changes at monthly decisions, counted off SPY's bars:
    K1 flips on 21 of 236, K4 on 55, K8 on 56, LIT4 on 115. Grading does not reduce churn, it
    roughly triples it, and the published set quintuples it. On a 50-name book at Gotrade's real
    fees a quarter-weight move still places fifty orders and still pays the per-order minimum on
    most of them, so grading buys its smoother cash with a fee bill the SPY prior charges nothing
    for. I expect the graded rungs to lose 0.3 to 1.0 points a year more than the prior says, and
    LIT4 considerably more. Zero-fee twins of all six arms are run outside the registry to split
    the churn from the market, exactly as M0270 and M0271 did.
 5. **LIT4 LOSES TO K4, AND THE GAP IS THE CENTRE OF GRAVITY RATHER THAN THE GRADING.** Both are
    four horizons and five exposure levels; only the centre and span differ. The prior puts the
    gap at 1.22 points a year. If it survives funding, the published refinement's whole shortfall
    is "the 50-day average is a worse timer", and no amount of grading recovers it.
 6. **LIT4 LOSES TO DIL TOO**, at its own average exposure -- the prior says 6.36 against 7.78 --
    which would mean the published vote is beaten by the single switch turned down to match it,
    and the dilution reading of a vote is not merely unhelpful but strictly worse than dilution.
 7. **THE GATE'S HABIT IS EXPENSIVE IN 2009-2015 AND THAT SWAMPS EVERYTHING ELSE.** The unfunded
    era column puts FULL at 12.72% against 7.43 to 7.82 for every gated rung. Five points a year.
    Whatever grading is worth, it is worth a tenth of what the gate itself costs in the era the
    owner's money actually lives in, and the analysis must say that in those words rather than
    burying it under a 0.3-point ladder.
 8. **WORST FALL BARELY MOVES ACROSS THE CENTRED LADDER** -- 19.03, 19.03, 19.03 on the prior, the
    same three digits -- because the deep falls happen when every horizon agrees and a vote with
    every member voting the same way IS the single gate. If grading bought safety anywhere it
    would be here, and the prior says it buys none.
 9. **BOTH STORES IN ONE SWEEP.** The dev store answers the claim; the survivorship-check store is
    reported beside it with both fingerprints printed, because a ratio drawn across two store
    vintages is not a comparison.
10. **NO ARM IS A CANDIDATE** (see the host note). Eligibility is reported and not acted on.

THE DELIVERABLE, fixed now so it cannot be chosen afterwards. In points a year of de-funded lead
over SPY TR, whole window and over 2009-2015, with every rung difference quoted beside the
exposure gap that produced it at M0270's era price of cash:

    G = lead(K8) - lead(K1)   the whole value of grading, finest against the incumbent, at a
                              matched centre and a matched exposure

`|G| <= 0.3` points a year CONFIRMS that a graded trend vote is the single switch wearing a finer
dress, and the lab should stop considering ensembles of the same rule. `G >= 1.0` with a monotone
ladder FALSIFIES it and says grading is worth about G a year, in which case the next method runs
the same ladder on a book that picks. `G <= -1.0` says grading actively hurts and the switch's
all-or-nothing shape is doing work nobody has credited it with. Between those, the answer is "too
small to tune against", and the method says so rather than rounding to whichever end reads better.

-------------------------------------------------------------------------------------------------
TRAPS ON THIS HOST, ALL PREVIOUSLY MEASURED

  * A published anomaly fades, and this one is nineteen years old. Faber's switch is not new and
    the ensemble refinement has been in print for over a decade, so a strong dev result would be
    the surprise. The prior already says there is no strong dev result to fade.
  * A slope read from two points is not a measurement (insight 533). The graininess ladder has
    three rungs and the dilution question has its own matched control.
  * A partial-weight book records zero trades and `PF --` without being inert (insight 507). Every
    graded arm here is a partial-weight book. EXPOSURE is the meter, never the trade count.
  * An allocator cannot read its own weight (insight 511). Nothing here does: the vote is computed
    from SPY's bars at the data date and the book is scaled to it, with no memory of what it held.
  * `trend_on` returns False when SPY has no bar dated `data_date` or too few bars behind it, so a
    horizon that is not yet ready votes NO rather than abstaining. At 275 bars of lookback that
    cannot happen inside the dev window, and the one place it can -- the smoke fixture's opening
    sessions -- is asserted in the test module rather than hoped about.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0127_slot_relative_resize_band import T00
from seer_engine.lab.methods.m0266_exposure_matched_rebalance import ScaledBandParams
from seer_engine.lab.methods.m0270_exposure_return_curve import ExposureLadderBook
from seer_engine.sim.book import Target
from seer_engine.sim.rules import TradeRules
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import FactorParams, FactorPrepared, trend_on

ADDED = date(2026, 10, 23)

#: The band every arm runs: zero, so every holding is traded back to its slot on every month
#: start. M0127's object, imported through the chain M0266, M0270 and M0271 use, so the four
#: methods' chassis cannot drift apart.
BAND: TradeRules = T00

#: The widest horizon any arm reads, and therefore the SPY bars the deepest vote needs.
MAX_HORIZON = 275

#: ``M0266-T00``'s recorded average exposure on the dev store (trial 893): the base book at full
#: scale with no gate, which is what ``FULL`` is. Used only to PREDICT where the arms land.
EXPOSURE_AT_FULL_WEIGHT = 0.9856884609713539


def horizons_for(k: int) -> tuple[int, ...]:
    """``k`` whole-session horizons evenly spaced across [125, 275], mean exactly 200.

    ``k = 1`` is the midpoint alone -- 200 -- which makes the lab's own shared gate the degenerate
    first rung of this family rather than a separate thing compared against it. For k above 1 the
    endpoints are included and the interior points are rounded half-up to whole sessions; the sets
    for k = 4 and k = 8 were checked to sum to 200 * k before this file was committed, so the mean
    horizon is 200 at every rung and nothing about the ladder's centre moves with k.
    """
    if k < 1:
        raise ValueError(f"k must be >= 1, got {k}")
    if k == 1:
        return (200,)
    lo, hi = 125, MAX_HORIZON
    step = (hi - lo) / (k - 1)
    return tuple(int(lo + step * i + 0.5) for i in range(k))


@dataclass(frozen=True, slots=True)
class VoteParams:
    """The base book's params, plus the two fields this method adds.

    ``horizons`` is the set of SPY moving-average lengths voting on each decision date. ``None``
    switches the vote off altogether, which is the no-opinion arm. ``(200,)`` is the gate exactly
    as every other book in this lab reads it.

    ``cap`` multiplies the vote's share before it scales the book. It is 1 on every arm but the
    dilution control, where it brings the single switch down to the published vote's own average
    exposure without touching a single one of its dates.

    The base book is carried as a whole ``ScaledBandParams`` rather than re-typed, so this method's
    arms and M0266's, M0270's and M0271's cannot drift apart, and so the recorded config digests
    of those methods are untouched: a shared params class may not gain a field without moving every
    digest that already references it.
    """

    book: ScaledBandParams = ScaledBandParams()
    horizons: tuple[int, ...] | None = (200,)
    cap: Decimal = Decimal(1)

    def __post_init__(self) -> None:
        if not isinstance(self.book, ScaledBandParams):
            raise TypeError(f"book must be ScaledBandParams, got {type(self.book).__name__}")
        if self.horizons is not None:
            if not isinstance(self.horizons, tuple) or not self.horizons:
                raise TypeError(f"horizons must be None or a non-empty tuple, got {self.horizons!r}")
            for n in self.horizons:
                if isinstance(n, bool) or not isinstance(n, int):
                    raise TypeError(f"every horizon must be an int, got {n!r}")
                if not 2 <= n <= MAX_HORIZON:
                    raise ValueError(f"every horizon must be in 2..{MAX_HORIZON}, got {n}")
            if len(set(self.horizons)) != len(self.horizons):
                raise ValueError(f"horizons must be distinct, got {self.horizons}")
            if list(self.horizons) != sorted(self.horizons):
                raise ValueError(f"horizons must be ascending, got {self.horizons}")
        if not isinstance(self.cap, Decimal) or not self.cap.is_finite():
            raise TypeError(f"cap must be a Decimal, got {self.cap!r}")
        if not 0 < self.cap <= 1:
            raise ValueError(f"cap must be a Decimal in (0, 1], got {self.cap}")

    def as_dict(self) -> dict[str, str]:
        out = dict(self.book.as_dict())
        out["gate"] = "off" if self.horizons is None else "SPY:" + "/".join(
            str(n) for n in self.horizons
        )
        out["gate_levels"] = "1" if self.horizons is None else str(len(self.horizons) + 1)
        out["gate_cap"] = str(self.cap)
        return out


def _check(params: object) -> VoteParams:
    if not isinstance(params, VoteParams):
        raise TypeError(f"params must be VoteParams, got {type(params).__name__}")
    return params


def vote_share(history: Mapping[str, History], data_date: date,
               horizons: tuple[int, ...] | None) -> Decimal:
    """The share of ``horizons`` whose average SPY closes above on ``data_date``.

    ``None`` is the vote switched off: 1, always invested. Otherwise each horizon is asked through
    ``f_factor.trend_on`` with ``("SPY", n)``, so nothing about what a trend reading SAYS is
    re-implemented in this file -- the k = 1 rung is literally the function every gated book in
    this lab already calls, and the graded rungs are that same function averaged.

    The result is an exact Decimal: ``k`` is 1, 4 or 8 here, so the share is a whole number of
    quarters or eighths and no rounding enters the weight path. Reads only bars dated on or before
    ``data_date``.
    """
    if horizons is None:
        return Decimal(1)
    up = sum(1 for n in horizons if trend_on(history, data_date, FactorParams(
        rank="momentum", trend=("SPY", n))))
    return Decimal(up) / Decimal(len(horizons))


class GradedVoteBook(ExposureLadderBook):
    """M0270's base book -- hence M0266's, by inheritance -- scaled to a trend vote.

    Subclassed twice over rather than copied, so that ``FULL`` is guaranteed, not merely believed,
    to compute M0270-S100's targets and ``K1`` to compute M0271-D000's. The only overrides are
    ``id`` (so the digests are distinct), ``symbols`` (SPY is now read and must be loaded),
    ``lookback`` (the widest horizon) and the two target paths, each of which computes the vote and
    then delegates to the parent with the book's own ``scale`` multiplied by it.

    DELEGATING THROUGH ``ScaledBandParams.scale`` RATHER THAN RESCALING THE PARENT'S OUTPUT IS THE
    POINT: the partial weights this method produces are then rounded by exactly the helper M0266,
    M0270 and M0271 already round with, so a graded arm's weights are the same arithmetic as a
    scaled arm's and the two ladders are readable against each other.
    """

    id = "M0287"

    def lookback(self, params: Any) -> int:
        """The widest horizon, the same at every rung, so no arm's scored window differs.

        275 bars, comfortably inside the 473-bar cap the smoke fixture imposes and far inside the
        739 bars that would move the dev window's first scored session off 1996-01-03.
        """
        return max(super().lookback(_check(params).book), MAX_HORIZON)

    def symbols(self, params: Any) -> tuple[str, ...]:
        """SPY, which every horizon reads. The ``None`` arm still declares it: an arm must not
        change which instruments the store loads, or the arms stop being the same measurement."""
        _check(params)
        return ("SPY",)

    def holds(self, params: Any) -> tuple[str, ...]:
        return super().holds(_check(params).book)

    def uses_members(self, params: Any) -> bool:
        return super().uses_members(_check(params).book)

    def _book(self, params: VoteParams, share: Decimal) -> ScaledBandParams | None:
        """The base book's params with its ``scale`` multiplied by the vote and the cap.

        ``None`` when the product is zero -- every horizon voted no -- which is the fully-out leg
        the single gate has always had and which ``ScaledBandParams`` rightly refuses as a scale.
        """
        scale = params.book.scale * share * params.cap
        if scale <= 0:
            return None
        return replace(params.book, scale=scale)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        q = _check(params)
        book = self._book(q, vote_share(history, data_date, q.horizons))
        if book is None:
            return ()
        return super().targets(history, members, data_date, held, book)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, FactorPrepared):
            raise TypeError(f"prepared must be FactorPrepared, got {type(prepared).__name__}")
        q = _check(params)
        book = self._book(q, vote_share(prepared.history, data_date, q.horizons))
        if book is None:
            return ()
        return super().targets_prepared(prepared, members, data_date, held, book)


BOOK = GradedVoteBook()

#: ``LIT4``'s average decision exposure divided by ``K1``'s, over the whole scored window, read
#: off SPY's bars before this file was committed and reading no return at all: 0.705696 / 0.734177.
#: It is the only calibrated number in the file and it calibrates the CONTROL, never the idea.
DILUTION = Decimal("0.961207")

#: The published set, kept exactly as Faber and the practitioner literature state it.
LIT_HORIZONS: tuple[int, ...] = (50, 100, 200, 252)

#: Each arm's share of monthly decisions invested, measured off SPY's bars in advance and costing
#: no backtest: (whole window, 2009-2015). Predictions only; the realised exposures are read.
DECISION_SHARE: Mapping[str, tuple[float, float]] = {
    "FULL": (1.0000, 1.0000),
    "K1": (0.7342, 0.8171),
    "K4": (0.7268, 0.8018),
    "K8": (0.7315, 0.8079),
    "LIT4": (0.7057, 0.7713),
    "DIL": (0.7057, 0.7854),
}


def _v(suffix: str, params: VoteParams, what: str) -> Candidate:
    whole, era = DECISION_SHARE[suffix]
    return Candidate(
        id=f"M0287-{suffix}",
        family="M0287",
        rules=BAND,
        allocator=BOOK,
        params=params,
        rationale=(
            f"{what}; invested on {whole * 100:.2f}% of monthly decisions whole window and "
            f"{era * 100:.2f}% over 2009-2015, so predicted average exposure "
            f"{whole * EXPOSURE_AT_FULL_WEIGHT * 100:.1f}% over the scored window"
        ),
        added=ADDED,
        owner_inputs=(),
    )


METHOD = Method(
    id="M0287",
    name=(
        "Many speeds, graded exposure: a trend vote across horizons instead of one on-off "
        "200-day line"
    ),
    family="market-trend-switch",
    source_kind="paper",
    source_ref=(
        "Faber 2007, A Quantitative Approach to Tactical Asset Allocation (SSRN 962461), for the "
        "switch and for the parameter-stability claim this method tests; Moskowitz, Ooi & Pedersen "
        "2012, Time Series Momentum (JFE 104:2), for the same insensitivity across one-, three-, "
        "six- and twelve-month look-backs; M0271, whose re-entry-delay ladder measured episodic "
        "cash at 0.2832 points a year per point over 2009-2015 on this exact book and store, and "
        "whose verdict asked for the shape of cash to be priced on its own; M0270, which measured "
        "evenly spread cash at 0.1732 on the same book; M0266 for the opinion-free 50-name "
        "chassis; M0281 for the measured warning that turning a losing timing rule down leaves "
        "its ratio invariant; insight 523, the rule that a reversed pair needs a no-opinion third "
        "arm; docs/backtests/2026-10-23-graded-trend-vote.py, the unfunded prior grid"
    ),
    parent_id="M0271",
    hypothesis=(
        "Faber reports broad parameter stability from a three-month trend out to beyond twelve, "
        "with the 200-day and 252-day versions statistically indistinguishable, and Moskowitz, "
        "Ooi and Pedersen report the same across one to twelve months. If several horizons are "
        "each individually defensible but disagree on different days, a vote across them GRADES "
        "exposure instead of switching it, and this lab has just measured the two numbers that "
        "decide whether that is worth anything. M0270 priced a point of the account held in cash "
        "spread evenly over every session at 0.1732 points a year of de-funded lead over "
        "2009-2015 on this exact book, store and era; M0271 priced the same point bought in "
        "all-or-nothing episodes at 0.2832. Cash in lumps costs about 1.6 times what the same "
        "average cash costs spread out, so a graded gate should buy the same protection out of "
        "cheaper cash. The opposite reading is that grading is dilution wearing a story, and "
        "dilution halves the good half and the bad half together and leaves the ratio invariant "
        "at about 0.69. THE OBVIOUS EXPERIMENT CANNOT TELL THOSE APART, AND THE PRIOR GRID SHOWS "
        "WHY. Measured on SPY's own closes, monthly and unfunded, before this file was written: "
        "the literature's own 50/100/200/252 vote earns 6.36 percent a year against the single "
        "200-day gate's 8.07 and falls 21.24 percent against 19.03 -- worse on both axes. But "
        "every horizon set centred on 200 instead lands within half a point of the gate (150/250 "
        "at 8.00, 125/175/225/275 at 7.58, eight horizons spanning 125 to 275 at 7.87), while "
        "every set centred near 150 loses one and a half points. Nearly the whole of the "
        "published vote's shortfall is its CENTRE OF GRAVITY and not its grading: the 50-day "
        "average is simply a worse timer than the 200-day one on this tape, and a vote including "
        "it replaces the gate's opinion with a faster one rather than grading the gate's own. SO "
        "THIS METHOD HOLDS THE MEAN HORIZON FIXED AT 200 AND MOVES ONLY HOW FINELY THE SAME "
        "AVERAGE OPINION IS EXPRESSED. The instrument is k whole-session horizons evenly spaced "
        "across 125 to 275, every set summing to exactly 200 times k: k=1 is 200 alone, which is "
        "the lab's own shared gate and therefore the degenerate first rung of this family rather "
        "than a foreign comparison; k=4 is 125/175/225/275 with five exposure levels; k=8 is "
        "125/146/168/189/211/232/254/275 with nine. THE LADDER IS EXPOSURE-MATCHED BY "
        "CONSTRUCTION, WHICH IS BETTER THAN AN EXPOSURE-MATCHED CONTROL: read off SPY's bars in "
        "advance, the three rungs sit at 73.42, 72.68 and 73.15 percent of monthly decisions "
        "invested, a spread of 0.74 points, worth about 0.13 points a year at the era price of "
        "cash and reported beside every rung difference. A difference between these rungs cannot "
        "be dilution because there is nothing left to dilute. That is why the idea row's "
        "exposure-matched control has moved: it is spent on the published 50/100/200/252 set, "
        "which really does run 2.85 points less invested, as a single 200-day switch capped at "
        "0.961207 of the book when it is on -- LIT4's average exposure over K1's, read from the "
        "same bars -- so the dilution question is asked on the one arm where it is real. The "
        "sixth arm is the gate switched off entirely, always invested, the no-opinion endpoint "
        "insight 523 asks for and the thing that makes the cost of the HABIT recoverable rather "
        "than cancelling across a pair. The host is M0270's opinion-free book -- M0266's 50 "
        "most-traded index members at equal weight, band zero, no picking, no brake, full scale "
        "-- chosen because the two prices of cash this hypothesis rests on were measured on it, "
        "because the no-gate arm reproduces M0270-S100 and M0271-OFF to the digit and the k=1 arm "
        "reproduces M0271-D000, and because a book with no opinion of its own cannot interact "
        "with the gate's. The price is that the base book loses to a deposit-matched SPY and "
        "falls past 50 percent, so no arm is a candidate and none will be promoted; eligibility "
        "would be reported and still not acted on. PREDICTIONS, written now. The no-gate and k=1 "
        "arms reproduce their recorded twins to the digit, and a mismatch is a bug chased before "
        "anything else is read. Realised exposure lands within 2 points of 98.6, 72.4, 71.7, "
        "72.1, 69.6 and 69.6 percent, and if the three centred rungs do not land within a point "
        "of each other the graininess ladder may not be read as one. GRADING AT A FIXED CENTRE IS "
        "NEARLY INERT AND THAT IS THE HEADLINE I EXPECT: on SPY alone the three rungs span 0.49 "
        "points a year and are not monotone in k, which is the signature of noise rather than a "
        "dial, and the structural reason is that a centred vote is fully invested on 66.7 percent "
        "of decisions and fully out on 20.3, agreeing with the single gate on 87 percent of them. "
        "A rule that is the same rule seven times out of eight cannot be worth much. THE FUNDED "
        "ANSWER SHOULD BE WORSE FOR THE GRADED ARMS THAN THE PRIOR, BY AN AMOUNT THIS METHOD "
        "MEASURES: weight changes at monthly decisions run 21 of 236 for k=1, 55 for k=4, 56 for "
        "k=8 and 115 for the published set, so grading roughly triples the churn and the "
        "published set quintuples it, and on a 50-name book at Gotrade's real fees a "
        "quarter-weight move still places fifty orders and still pays the per-order minimum on "
        "most of them. I expect the graded rungs to lose 0.3 to 1.0 points a year more than the "
        "prior says; zero-fee twins of all six arms are run outside the registry to split the "
        "churn from the market. The published set loses to the centred four-horizon set -- same "
        "k, same five levels, only the centre and span differ -- by about 1.22 points a year, and "
        "it loses to its own dilution control too, which would make the published vote strictly "
        "worse than simply turning the single switch down. Worst fall barely moves across the "
        "centred ladder, three times 19.03 on the prior, because the deep falls happen when every "
        "horizon agrees and a vote with every member voting the same way IS the single gate. And "
        "the gate's habit costs about five points a year in 2009-2015 on the unfunded prior "
        "(12.72 for always-invested against 7.43 to 7.82 for every gated rung), which swamps "
        "everything else here and must be said in those words rather than buried under a "
        "0.3-point ladder. THE DELIVERABLE, fixed now so it cannot be chosen afterwards: G is the "
        "de-funded lead of the finest rung minus the lead of the incumbent, at a matched centre "
        "and a matched exposure, quoted whole window and over 2009-2015 beside the 0.74-point "
        "exposure residual that produced part of it. G within 0.3 points a year CONFIRMS that a "
        "graded trend vote is the single switch wearing a finer dress and the lab should stop "
        "considering ensembles of one rule; G at or above 1.0 with a monotone ladder FALSIFIES "
        "that and the next method runs the same ladder on a book that picks; G at or below -1.0 "
        "says the all-or-nothing shape is doing work nobody has credited it with. Between those "
        "the answer is too small to tune against and the method says so. Both stores in one "
        "sweep with both fingerprints printed. Fractional shares, Gotrade's real fees, the "
        "owner's funding plan. Success is a measurement."
    ),
    expected_failure=(
        "THE LIKELIEST FAILURE IS THAT THE WHOLE LADDER COMES OUT INSIDE THE NOISE AND THE METHOD "
        "CANNOT TELL 'GRADING IS WORTH NOTHING' FROM 'THIS BOOK CANNOT MEASURE 0.3 POINTS A "
        "YEAR'. The prior's three centred rungs span 0.49 points a year on SPY alone with no fees "
        "and no picking; on a funded 50-name book that falls past 50 percent, path jitter between "
        "two arms holding the same names in different amounts through 2008 is of that order. The "
        "honest answer then is a bound -- 'grading is worth less than X a year on this chassis, "
        "and X is as small as this lab can currently measure' -- and not a finding either way. "
        "The internal noise band is the only honest yardstick: every rung is the same book on the "
        "same tape with one dial moved, and M0270's rung-pair errors on this chassis ran 0.000 to "
        "0.034 points a year, so a ladder scatter near a twentieth of a point is expected and a "
        "spread much larger than that is real. The lab-wide 3.1 points a year of year-to-year "
        "noise is a different quantity about different books and is NOT the yardstick here. THE "
        "SECOND FAILURE IS THAT THE EXPOSURE MATCH FAILS IN THE RUN even though it holds on SPY's "
        "bars. The decision-session shares are computed on SPY alone; the realised exposure of a "
        "funded book also carries its fill path, its cash drag between decisions and its deposits, "
        "and those need not be identical across arms whose weights differ. If the three centred "
        "rungs land more than a point apart in realised exposure, the graininess ladder has "
        "become an exposure ladder and must be read as one, with M0270's era price applied and "
        "the residual stated rather than the difference quoted raw. THE THIRD IS THAT GRADING'S "
        "COST IS ENTIRELY THE FEE SCHEDULE AND NOT THE MARKET. A quarter-weight move on a 50-name "
        "book places fifty orders of a quarter the size and pays Gotrade's per-order minimum on "
        "more of them, so the graded rungs are penalised for a reason that has nothing to do with "
        "trend following. The zero-fee twins exist to split that, but if the gross and net "
        "ladders disagree about the SIGN of G then this method has measured a 20,000,000 IDR "
        "account's order economics rather than a market fact, and the verdict must say so in "
        "those words rather than dress it up. THE FOURTH IS THAT THE CENTRED LADDER IS TOO "
        "CONSERVATIVE TO BE THE TEST ANYONE MEANT. Holding the mean horizon at 200 is what makes "
        "the experiment clean, and it is also what makes the vote agree with the single gate on "
        "87 percent of decisions. A reader could fairly say the method has defined the ensemble "
        "down to something that could not possibly differ. The answer is that the wide set is "
        "registered too, beside its own dilution control, so the published refinement is measured "
        "in its own terms as well -- but if LIT4 turns out to be the only arm that moves, then "
        "what this method has really measured is the 50-day horizon and not grading at all, and "
        "it must be reported under that name. THE FIFTH IS THAT THE BASE BOOK IS NOT A BOOK "
        "ANYONE WOULD TRADE. It falls past 50 percent and loses to SPY at every rung, so every "
        "lead here is a small difference between two large and violent numbers, and what grading "
        "is worth on it need not be what grading is worth on a 20-name book that picks. That is "
        "the deliberate price of an opinion-free chassis and it is why the deliverable is a bound "
        "on G rather than a recommendation. THE SIXTH IS THE ONE THAT WOULD HURT MOST: the "
        "ladder comes out monotone and positive, grading is worth a point a year, and the lab "
        "learns it on a chassis where no arm can be promoted and must spend another method id to "
        "find out whether it survives on a book that picks. That would be a good result arriving "
        "expensively, and the right response is to queue that method rather than to regret this "
        "one. THE SEVENTH is the dull one and would be the most useful: G comes out at zero, the "
        "graded vote is the single switch wearing a finer dress, and the practitioner literature's "
        "favourite refinement of the Faber rule is confirmed to be decoration. That must be "
        "reported with the same emphasis as a surprise rather than buried as a non-finding, "
        "because it closes a direction this lab would otherwise keep paying ids to re-open."
    ),
    candidates=(
        _v("FULL", VoteParams(horizons=None),
           "no gate at all: always invested, the no-opinion endpoint"),
        _v("K1", VoteParams(horizons=horizons_for(1)),
           "the lab's shared SPY 200-day gate, the single-horizon rung of this family"),
        _v("K4", VoteParams(horizons=horizons_for(4)),
           "four horizons evenly spaced across 125 to 275, mean 200, five exposure levels"),
        _v("K8", VoteParams(horizons=horizons_for(8)),
           "eight horizons evenly spaced across 125 to 275, mean 200, nine exposure levels"),
        _v("LIT4", VoteParams(horizons=LIT_HORIZONS),
           "the published 50/100/200/252 set, mean horizon 150.5, five exposure levels"),
        _v("DIL", VoteParams(horizons=horizons_for(1), cap=DILUTION),
           "the single 200-day gate capped at 0.961207 when on: the published set's own average "
           "exposure in the gate's lumpy shape, the dilution control"),
    ),
    seen_keys=(
        "concept:graded-trend-vote-across-horizons",
        "concept:moving-average-ensemble-exposure",
        "concept:gate-graininess-ladder",
    ),
)

"""M0127 — Rebalance on the slot, not on the account: what a trading threshold that never fires costs.

Source: variation of M0119 (the deposit-deployment method, whose closing paragraph queued this
one), on M0109's deliberately neutral base book. M0139 is the nearest prior art and is answered
below.

WHAT THIS IS. Not a strategy. A measurement of the lab's own simulator, pre-registered so that it
is held to a prediction. The book engine trims or tops up a holding only once its gap from target
is worth at least a band, and under ``resize_basis="equity"`` -- the basis of every recorded trial
in this lab before 2026-10-12 -- that band is ``RESIZE_BAND`` x equity, **1% of the whole
account**. The band does not scale with the slot. In a 12-name book a slot is 8.3% of the account
and 1% of the account is an eighth of it, a sensible trigger. In a 50-name book a slot is 2% and
1% of the account is **half the holding**: the name must roughly halve or double before anything
trades. Measured on the dev store before M0119 ran, the gap clears the band in 0.1% of
holding-months at 50 equal slots, 0.8% at 30, 4.2% at 20 and 16.2% at 12. M0109 confirmed it from
the other end: its monthly and its weekly 50-name controls, which differ in nothing but how often
they are allowed to re-scale, made the IDENTICAL 1338 trades. So every book this lab runs at 20
names or more is in practice never rebalanced, whatever its method file says, and nobody decided
that -- it fell out of a constant.

THE QUESTION, in one sentence: on a book whose picks do not change, what does genuine monthly
rebalancing cost in fees and pay in return and in worst fall?

WHY THE ANSWER TRANSFERS. Insight 479 priced the weighting arrangement itself: an equal-weight
top-fifty book and a size-weighted one held the IDENTICAL fifty names and made the IDENTICAL 360
trades, and the equal-weight one earned 6.9% a year against 5.6% -- one and a quarter points from
how the money is held, with names and trade count fixed. That number is the lab's current estimate
of what re-imposing slots is worth, and it was measured on two books that differ in their TARGET
weights. This method measures the same effect from the only angle that is free of that confound:
identical targets, identical names, identical dates, and nothing different but how far a holding
may drift before it is traded back. Whatever comes out re-prices every control comparison the lab
has ever drawn, because every one of them was drawn on the equity basis.

THE DESIGN, and why it isolates exactly one thing. All five variants share ONE allocator, ONE set
of params and ONE pick rule. The allocator ignores ``held`` entirely, so on every rank session all
five arms are handed the identical fifty symbols at the identical weight 1/50. They differ in
their ``TradeRules`` and in nothing else, and within TradeRules in one field: the resize band. This
is the cleanest isolation available in this engine -- there is no pick difference, no exposure
rule, no cadence difference and no fee-model difference to charge anything to.

THE BASE BOOK is M0109's, verbatim and unbraked: on a rank session, among the point-in-time index
members that are not ETFs, have at least 20 bars, a close of at least ``min_price`` and a
20-session mean close x volume above ``min_dollar_volume``, hold the ``top`` = 50 with the HIGHEST
dollar volume at 1/50 each. Nothing is ranked on returns, volatility, fundamentals or calendar.
It was chosen for this method for three reasons, all of them about neutrality rather than about
winning: it does no stock picking at all, so the number is the band's and not a ranking's; its
picks turn over slowly, so the band is the only machine in the book that can move money, which is
exactly the regime M0139 could not reach; and 50 names is where the broken band bites hardest
while the slots are still big enough to trade (a 20,000,000 IDR account split fifty ways is a $29
slot, which is where Gotrade's fee schedule was measured; a hundred names is a $14 slot paying
about a point a side). It has no trend gate and no stop, so no arm spends time in cash for a
reason the band did not cause, and the exposure column reads the band directly.

THE LADDER. One control and four treatments, in order of how hard they trade:

  * ``E1`` -- the control and the status quo: ``resize_basis="equity"``, the band 1% of the
    account. At fifty equal slots that is **50% of a slot**, which the measurement above says
    fires in one holding-month in a thousand. This arm is "never rebalanced" in practice.
  * ``T33`` -- the band 33% of the holding's own target.
  * ``T20`` -- 20% of the target: the existing ``monthly-hold-frac-gotrade-tband`` preset, the
    tape the lab adopted on 2026-10-12. Running it here prices the tape the lab already switched
    to, on the book where it matters most.
  * ``T10`` -- 10% of the target.
  * ``T00`` -- the band 0: every non-zero gap is beyond it, so every holding is traded back to
    exactly 1/50 on every month start. This is the textbook monthly rebalance, and it is here
    because it is the only arm that unambiguously IS one. It is expected to be ruinous and that
    is the point: see the prediction below.

A dose-response ladder was chosen over a single treatment deliberately. A two-point comparison
cannot tell "rebalancing helps" from "this particular threshold helps", and the lab has learned
(dose-response beats a placebo) that a monotone ladder is worth more than any one margin.

WHAT IS PREDICTED, in numbers, before any result.

 1. THE BAND IS THE ONLY THING THAT TRADES. ``E1`` should record close to the smallest trade count
    the book can have -- entries and exits forced by the dollar-volume ranking changing, and
    nothing else. Each tightening should add trades monotonically, and ``T00`` should record
    roughly fifty orders per month start on top of that, around 12,000 over the window.
 2. FEES TURN THE LADDER OVER SOMEWHERE. Gotrade charges a minimum per ORDER (about $0.13 all in
    on a small trade), and a rebalancing trade is not a slot, it is a slot's DRIFT -- a few dollars.
    At a $29 slot a 10% drift is a $2.90 order paying about 4.5% to trade. So the fee bill does not
    scale with the band, it explodes as the band tightens, and ``T00`` should be the worst arm in
    the lab by a wide margin: fifty orders a month at the minimum fee is of order 5% of a 20M IDR
    account a year. The honest expectation is that the ladder is NOT monotone in return: it rises
    from ``E1`` to some middle rung as real rebalancing starts to pay, then collapses as the
    minimum fee takes over. Finding where it turns is the deliverable.
 3. WORST FALL SHOULD IMPROVE, SLIGHTLY AND MONOTONICALLY, with tightening. Never trimming lets a
    winner grow into an oversized slot, and an oversized slot is a concentration the book never
    agreed to. The effect should be small on a fifty-name book of large liquid companies and it
    should be largest around 2000-2002, when the most-traded list was the dot-coms.
 4. THE 2009-2015 COLUMN DECIDES WHETHER THIS TRANSFERS. Those are the best-covered years and the
    most like today. A band effect that lives only in 1996-2002 is a reading of a bubble, not of
    rebalancing, and the verdict must say so.
 5. NONE OF THESE ARMS IS EXPECTED TO BE A CANDIDATE. An equal-weight book of the most-traded
    index members is a bet against SPY's big-company shape before any band is applied, and every
    lab book of that shape lost to a deposit-matched SPY after 2018. The base is M0109's, which
    trailed SPY. Eligibility here would be a surprise and would be reported, not pursued.

WHAT M0139 ALREADY ANSWERED, AND WHAT IT COULD NOT. M0139 ran the equity basis against the 20%
target basis at 35, 50 and 70 names on M0007's gated residual-momentum picks, and found almost
nothing: 2548 trades against 2548 at 35 names, 3367 against 3365 at 50, 4169 against 4167 at 70,
and 0.1 to 0.3 points a year of funded return. That is a real result and it is not this one. That
book turns over about 8.9 times a year and its gate liquidates it outright in 2001, 2002 and 2008,
so its holdings were replaced long before any band could bind, and the band had nothing left to do.
The two readings together are the finding: the band matters in proportion to how LITTLE a book
trades for other reasons. This method puts the band on a book that trades for no other reason, and
adds the three rungs M0139 had no lever to reach -- 33%, 10% and 0 -- because until today the band
was a module constant.

THE LEVER THIS NEEDED. ``TradeRules.resize_band`` (2026-10-20) names the band's size for either
basis; ``None`` keeps the basis's own constant. It is a lever added after the pins
(``sim.rules.LEVERS_SINCE_PINS``), so at ``None`` it drops out of every canonical text and no
recorded trial, pinned candidate digest or live paper spec moves; ``tests/test_resize_band_pins.py``
is the proof. No preset names a band, so the three new rungs are one-off rule sets declared here,
exactly as M0063's weekly real-fee rule set was. That makes them unpromotable by construction
(``promote`` needs a preset of the variant's own id), which is accepted: this is a measurement, and
a feature wish for presets is journalled.

Every piece reads only bars dated <= d.
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
from seer_engine.lab.methods.m0109_book_drawdown_brake import (
    BrakeParams,
    book_rows,
    book_targets,
    prepared_rows,
)
from seer_engine.sim.book import Target
from seer_engine.sim.rules import (
    MONTHLY_HOLD_FRAC_GOTRADE,
    MONTHLY_HOLD_FRAC_GOTRADE_TBAND,
    TradeRules,
)
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import DV_N, FactorPrepared, prepare_factor

ADDED = date(2026, 10, 20)


# --------------------------------------------------------------------------- params


@dataclass(frozen=True, slots=True)
class BandParams:
    """The base book's screen and size. The band itself is a rule-set lever, never a param.

    Keeping the band out of the params is what makes the experiment clean: all five variants are
    handed the SAME params object, so the allocator cannot possibly behave differently between
    them, and the only surviving difference is in ``rules``.
    """

    top: int = 50
    min_dollar_volume: float = 20_000_000.0  # 20-session mean close x volume > this (strict)
    min_price: float = 5.0  # close >= this

    def __post_init__(self) -> None:
        if isinstance(self.top, bool) or not isinstance(self.top, int) or not 1 <= self.top <= 200:
            raise ValueError(f"top must be an int in 1..200, got {self.top!r}")
        for name in ("min_dollar_volume", "min_price"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise TypeError(f"{name} must be a float, got {type(v).__name__}")
            v = float(v)
            if v != v or v in (float("inf"), float("-inf")) or v < 0.0:
                raise ValueError(f"{name} must be finite and >= 0, got {v!r}")
            object.__setattr__(self, name, v)

    def as_dict(self) -> dict[str, str]:
        return {
            "top": str(self.top),
            "min_dollar_volume": format(Decimal(repr(self.min_dollar_volume)).normalize(), "f"),
            "min_price": format(Decimal(repr(self.min_price)).normalize(), "f"),
        }

    def as_brake(self) -> BrakeParams:
        """The same screen as M0109's params with its brake switched off (``taper=None``).

        The book this method measures IS M0109's unbraked base, so the screen is reused rather
        than re-typed: one definition, no chance of the two drifting apart.
        """
        return BrakeParams(
            top=self.top,
            min_dollar_volume=self.min_dollar_volume,
            min_price=self.min_price,
            taper=None,
        )


def _check(params: object) -> BandParams:
    if not isinstance(params, BandParams):
        raise TypeError(f"params must be BandParams, got {type(params).__name__}")
    return params


# --------------------------------------------------------------------------- the allocator


class MostTradedEqualWeight:
    """The ``top`` most-traded index members at 1/``top`` each. No gate, no brake, no memory.

    ``held`` is ignored on purpose: every rank session is a fresh top set, so a held name that
    falls out of the most-traded list is exited and a new one is bought. Two arms of this method
    on the same date therefore receive byte-identical targets, whatever either of them is holding,
    which is what makes the band the only difference between them.
    """

    id = "M0127"

    def lookback(self, params: Any) -> int:
        _check(params)
        return DV_N  # the screen's 20-session mean dollar volume is the deepest thing it reads

    def symbols(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params).as_brake()
        return book_targets(book_rows(history, members, data_date, p), p)

    def prepare(self, history: Mapping[str, History]) -> FactorPrepared:
        return prepare_factor(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, FactorPrepared):
            raise TypeError(f"prepared must be FactorPrepared, got {type(prepared).__name__}")
        p = _check(params).as_brake()
        return book_targets(prepared_rows(prepared, members, data_date, p), p)


BOOK = MostTradedEqualWeight()


# --------------------------------------------------------------------------- the rule-set ladder

#: The control: the band is 1% of the WHOLE account, which at fifty equal slots is half a slot.
#: Every recorded trial in this lab before 2026-10-12 ran on this basis.
E1 = MONTHLY_HOLD_FRAC_GOTRADE
#: The tape the lab adopted on 2026-10-12: 20% of the holding's own target.
T20 = MONTHLY_HOLD_FRAC_GOTRADE_TBAND
#: The rungs that needed ``TradeRules.resize_band``. Not presets, so not promotable: a feature
#: wish is journalled rather than four presets added for a measurement.
T33 = replace(T20, id="monthly-hold-frac-gotrade-tband33", resize_band=Decimal("0.33"))
T10 = replace(T20, id="monthly-hold-frac-gotrade-tband10", resize_band=Decimal("0.10"))
T00 = replace(T20, id="monthly-hold-frac-gotrade-tband00", resize_band=Decimal("0"))


def _v(suffix: str, rules: TradeRules, rationale: str) -> Candidate:
    return Candidate(id=f"M0127-{suffix}", family="M0127", rules=rules, allocator=BOOK,
                     params=BandParams(), rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0127",
    name="Rebalance on the slot, not on the account: pricing the trading threshold that never fires",
    family="portfolio-rebalancing",
    source_kind="variation",
    source_ref=(
        "M0119 (the deposit-deployment method, whose closing paragraph queued this one) for the "
        "question; M0109 for the neutral 50-name base book and its 1338-identical-trades evidence; "
        "M0139 for the nearest prior art, which measured the two bases on a high-churn gated book "
        "and found almost nothing; insight 479 for the 1.25 points a year the weighting "
        "arrangement was worth on identical names and identical trades"
    ),
    parent_id="M0119",
    hypothesis=(
        "The book engine trims or tops up a holding only once its gap from target is worth at "
        "least a band, and under the equity basis -- the basis of every recorded trial in this lab "
        "before 2026-10-12 -- that band is 1% of the WHOLE account and does not scale with the "
        "slot. At fifty equal slots it is half a holding, and the gap clears it in 0.1% of "
        "holding-months (0.8% at 30 names, 4.2% at 20, 16.2% at 12); M0109's monthly and weekly "
        "50-name controls made the identical 1338 trades. So every book this lab runs at 20 names "
        "or more is in practice never rebalanced, whatever its method file says. This method "
        "prices the alternative on a book whose picks do no stock picking at all: M0109's "
        "unbraked base, the 50 most-traded index members at equal weight, with ONE allocator and "
        "ONE params object across every arm, so all five are handed byte-identical targets on "
        "byte-identical dates and the ONLY difference between them is how far a holding may drift "
        "before it is traded back. The ladder is the control at 1% of the account (half a slot, "
        "the status quo) and four treatments at 33%, 20%, 10% and 0% of the holding's own target, "
        "0% being a full rebalance to 1/50 on every month start -- the textbook monthly rebalance, "
        "and the only arm that unambiguously is one. Fractional shares, Gotrade's real fee "
        "schedule, the owner's funding plan, against a SPY fed the identical deposits on the "
        "identical days. PREDICTIONS, written now. (1) Trade count rises monotonically as the band "
        "tightens, from near the book's forced minimum at the control to roughly fifty orders per "
        "month start at 0%. (2) RETURN IS NOT MONOTONE. Gotrade charges a minimum per order and a "
        "rebalancing trade is a slot's DRIFT, not a slot: at a $29 slot a 10% drift is a $2.90 "
        "order paying about 4.5% to trade, so the fee bill explodes as the band tightens while "
        "the rebalancing benefit does not. Expect the ladder to rise from the control to some "
        "middle rung and then collapse, with the 0% arm the worst arm in the lab by a wide "
        "margin. Where it turns is the deliverable. (3) Worst fall improves slightly and "
        "monotonically with tightening, because never trimming lets a winner grow into a "
        "concentration the book never agreed to; largest around 2000-2002, when the most-traded "
        "list was the dot-coms. (4) The 2009-2015 column decides whether any of this transfers; a "
        "band effect that lives only in 1996-2002 is a reading of a bubble. (5) No arm is expected "
        "to be a candidate and none is being pursued as one: the base is M0109's, which trailed "
        "SPY, and an equal-weight book of the most-traded members is a bet against SPY's "
        "big-company shape before any band is applied. ASSUMPTIONS RECORDED BEFORE THE RUN: the "
        "band's size needed a new rule-set lever (TradeRules.resize_band, a post-pins no-op lever "
        "that moves no recorded digest), and the three new rungs are one-off rule sets rather than "
        "presets, which makes them unpromotable by construction -- accepted, with a feature wish "
        "journalled. Success here is a measurement, not a candidate: state what genuine monthly "
        "rebalancing costs in fees and pays in return and in worst fall, on a book whose picks do "
        "not change, so the number transfers to every book in the lab."
    ),
    expected_failure=(
        "The likeliest disappointment is that the ladder is swamped by its own fee bill and says "
        "nothing about rebalancing at all. Gotrade's minimum is charged per order and a drift "
        "trade is tiny, so if even the 33% rung pays more in fees than it recovers in return, the "
        "honest reading is that this is a measurement of a 20,000,000 IDR account's order "
        "economics rather than of rebalancing, and the verdict must say so and must quote the "
        "turnover and the fee bill beside the return so the two can be told apart. The second way "
        "it fails is that the band turns out not to bind even at 33%, because the dollar-volume "
        "ranking already replaces enough of the book each month that holdings never get the chance "
        "to drift -- which is precisely what happened to M0139 on a high-churn book -- in which "
        "case the control and the first two treatments record near-identical trade counts and the "
        "finding is that this base was not slow enough either. The third is survivorship: the dev "
        "store prices no delisted names and this book holds fifty of the shortlist, so the names "
        "that drifted furthest down are disproportionately the ones missing; a rebalancing rule "
        "buys the fallers, so if the dead companies are absent the trimming-and-topping-up arms "
        "are flattered, and the widest-moving arm must be survivorship-checked and the result "
        "quoted beside the dev column. The fourth is that the effect is real but lives entirely "
        "in 2000-2002, where the most-traded list was the dot-coms and the equal-weight book fell "
        "58%: a rule that only helps in one bubble has been tested once. The fifth is that the "
        "deposits soften every arm's worst fall alike, so none of these falls may be lined up "
        "against an unfunded trial's."
    ),
    candidates=(
        _v("E1", E1,
           "Control and status quo: the band is 1% of the whole account, half a slot at fifty names"),
        _v("T33", T33,
           "The band is 33% of the holding's own target: the loosest genuinely slot-relative rung"),
        _v("T20", T20,
           "The band is 20% of the holding's own target: the tape the lab adopted on 2026-10-12"),
        _v("T10", T10,
           "The band is 10% of the holding's own target: twice as busy as the adopted tape"),
        _v("T00", T00,
           "The band is 0: every holding is traded back to 1/50 on every month start, the textbook rebalance"),
    ),
    seen_keys=(
        "concept:resize-band-size-ladder",
        "concept:price-of-monthly-rebalancing",
    ),
)

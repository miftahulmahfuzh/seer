"""M0156 — The roster's OTHER book, priced the way the owner trades it, at five widths.

Source: a variation of M0152, which asked this question of the roster's residual-momentum book
and answered 35 names. This method asks it of the book M0152 explicitly could not reach.

**The hole this exists to close.** The paper roster holds two books the owner mirrors with his own
money. ``RAW-FR-GT`` is M0007-N20-RAW's picks; M0152 measured it at seven widths on both price
histories and found its twenty-name form falls 25.05% on the survivorship-check store against a
real-money bar of 25%. ``MOM-FR-GT`` is this book -- M0002-REL-85, momentum de-risked only when
its own volatility is above its own median -- and it has **no row in
docs/lab/survivorship/grid.csv, no reading on the check store in any form, and no lab trial at the
fees and share basis the owner actually pays.** It is also a twenty-name book: the exact shape that
came out worst in M0152.

**Why a new method id rather than an amendment.** ``runner.AMEND_CLOSED`` refuses an amendment on
any method that has spent its test-window look, and M0002 reads ``test-failed`` -- so the natural
host is closed by design, and correctly: design section 3 gives one look per configuration.
M0152 is amendable but is the wrong host: a different allocator, a different family, and
``store.best_dev_eligible`` returns exactly one variant per method, so an amendment would make
M0152's single promotion candidate a choice between two different picking rules. M0152's own
frozen hypothesis also says of this book, before any of its results were seen, that it is "not
fixable inside this method id". Measured cost of the new id: the lab's N moves from 94 distinct
methods to 95 under ``store.DSR_POLICY = "methods"``, applied retroactively. Accepted, and stated
here rather than discovered later.

**What the free report could and could not settle.** ``lab survivorship M0002`` re-runs the
recorded M0002 trials at their recorded basis -- whole shares, the lab's old flat 0.1% a trade,
and **unfunded**, because none of trials #75-#80 has a ``trial_funding`` row. Three independent
mismatches against M0152's curve, which is fractional, at Gotrade's measured schedule, and funded
on the owner's plan. So that report measures the *picking rule's* survivorship sensitivity and
cannot measure the owner's book. This method measures the owner's book. Its rung set was fixed in
the implementation plan before that report was run, so no result selected it.

**Nothing varies but the slot count.** ``_picks`` is M0002-REL-85's parameters with ``top`` moved
through ``dataclasses.replace`` and nothing else: the same momentum screen, the same SPY 200-day
all-cash gate, the same 63-session short volatility window against the same 378-session reference
median, the same 0.85 multiple of its own normal volatility, the same equal money per slot. A
reading at 25 names and a reading at 35 names differ in one integer.

**The preset is monthly-hold-frac-gotrade-tband, and that is deliberately NOT what the live roster
entry trades.** ``MOM-FR-GT`` runs on ``monthly-hold-frac-gotrade``, whose resize band is read
against equity and, measured 2026-10-14, never fires in a many-name book -- so the owner's monthly
deposits reach the book only through turnover and a slow book sits half in cash. Every width
reading on that tape is confounded. The banded preset is the tape that invests the deposits, is
what M0152's whole curve is measured on, and carries no owner input. The gap between this
measurement and the live entry's rule set is real, is named here, and is a roster question rather
than a lab one.

Assumptions written down before the run:

- **PROMOTION IS NOT AVAILABLE AND IS NOT SOUGHT.** This line runs through M0002, which is
  test-failed, so the hard gate refuses on kin (D9/D13) whatever these arms score. Any arm that
  reads ELIGIBLE on the dev screen is a by-product and must not be reported as a candidate.
- **Deposits soften every fall in this file alike.** These numbers line up against M0152's,
  M0139's and M0128's, which are funded identically (10,000,000 IDR opening, +5,000,000 IDR on the
  25th, 237 deposits), and against no unfunded trial anywhere -- M0002's own recorded trials
  included.
- **The check store is a cross-check, not truth.** It adds most of the members the dev store
  cannot price and not all of them, and real collapses were kept while data errors were cleaned,
  which is a judgement call. That is why the decision rule below asks for a cushion under the
  owner's bar rather than for the bar itself.
- Pure: every arm reads only bars dated <= ``data_date``; the preset is looked up by id so the
  file names the rule set exactly as the trial will record it.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0002_asymmetric_vol_regime import MOM20_TREND, REGIME, RegimeParams
from seer_engine.lab.methods.m0128_near_miss_fixed_tape import MONTHLY_TBAND
from seer_engine.sim.rules import rule_owner_inputs

ADDED = date(2026, 10, 14)

#: The rungs this method buys. Fixed in the implementation plan before `lab survivorship M0002`
#: was run, so no result selected them. 20 is the roster's own width and the realistic twin;
#: 25/30/35 span the interval where M0152 found the whole of the other book's protection; 45
#: prices the far end, where M0152 found the two histories converge.
WIDTHS: tuple[int, ...] = (20, 25, 30, 35, 45)

#: M0002-REL-85's own regime rule, verbatim -- the four positional arguments M0002's own
#: ``_v("REL-85", ...)`` passes: scale by min(1, 0.85 x its median vol / its current vol), a
#: 63-session short window against a 378-session reference median, full exposure at or below
#: normal. ``target_vol`` is unused in "relative" mode and is left at the value M0002 recorded.
#: The literals are written out rather than read off ``RegimeParams`` as class attributes:
#: ``RegimeParams`` is ``@dataclass(frozen=True, slots=True)`` and a slots dataclass exposes a
#: slot descriptor under the field name, not the default value.
REL85 = RegimeParams(MOM20_TREND, "relative", Decimal("0.12"), Decimal("0.85"))


def _picks(top: int) -> RegimeParams:
    """M0002-REL-85's params with only ``top`` moved: same screen, same gate, same regime rule."""
    return replace(REL85, inner_params=replace(MOM20_TREND, top=top))


def _v(top: int, rationale: str) -> Candidate:
    return Candidate(id=f"M0156-N{top}", family="M0156", rules=MONTHLY_TBAND, allocator=REGIME,
                     params=_picks(top), rationale=rationale, added=ADDED,
                     owner_inputs=rule_owner_inputs(MONTHLY_TBAND))


METHOD = Method(
    id="M0156",
    name="The roster's relative-strength book, priced the way the owner trades it, at five widths",
    family="stock-momentum-risk-managed",
    source_kind="variation",
    source_ref=(
        "M0152 for the question, the paired-curve method and the seven-rung curve on the roster's "
        "other book; M0002-REL-85 (trial #79) for the picking rule, which is what the paper "
        "roster entry MOM-FR-GT holds; M0128 for the banded real-fee preset; "
        "docs/lab/survivorship/roster-width-curve-2026-10-14.csv for the curve this one is read "
        "beside"
    ),
    parent_id="M0152",
    hypothesis=(
        "A measurement whose output is a number the owner will act on with real money, not a "
        "candidate. The paper roster holds two books and he mirrors both. M0152 measured the "
        "first at seven widths on both price histories and recommended thirty-five names. The "
        "second -- this one, momentum de-risked only when its own volatility is above its own "
        "median -- has never been read on the survivorship-check store, has no row in the "
        "committed survivorship grid, and has never been run at the fees or the share basis the "
        "owner pays. It is a twenty-name book, which is the width that came out worst in M0152. "
        "This method runs it at twenty, twenty-five, thirty, thirty-five and forty-five names on "
        "monthly-hold-frac-gotrade-tband, funded on the owner's plan against a SPY fed the "
        "identical deposits on the identical days, and then lab survivorship re-reads all five on "
        "the check store -- report only, no trial, no look -- so the two roster books can be read "
        "as two paired curves on one tape instead of one curve and a blank. "
        "THE TWENTY-NAME ARM IS THE DELIVERABLE AS MUCH AS THE CURVE IS. It is the first time "
        "this book has been priced at Gotrade's real fees in fractional shares on a tape that "
        "invests the deposits, and the first time it has been read against the history that keeps "
        "the companies that went bankrupt. Whatever the width answer turns out to be, the owner "
        "ends this run knowing what half his money has actually been doing. "
        "WHAT IS PREDICTED, in numbers, before any result. (1) THE DEV CURVE SAYS NOTHING, as it "
        "did for the other book. All five dev-store worst falls land inside 17% to 23% with no "
        "reliable ordering in width. The dev store misses about four in ten of the days companies "
        "sat in the index and the ones it misses are overwhelmingly the ones that failed, so "
        "behind a market gate it is structurally blind to what width protects against and can "
        "only ever show what width costs. (2) THE CHECK CURVE FALLS WITH WIDTH, and the "
        "twenty-name arm is the one at risk. Predicted check-store worst falls: 23% to 28% at "
        "twenty names, 21% to 25% at twenty-five, 20% to 24% at thirty, 19% to 23% at "
        "thirty-five, 18% to 22% at forty-five. Equivalently the gap between the two histories "
        "should start between +2 and +6 points at twenty names and close to under +1 by "
        "forty-five, on the schedule both previously measured books showed. (3) THE RETURN COST "
        "IS SMALL BELOW ABOUT THIRTY-FIVE NAMES AND REAL ABOVE IT, as it was on both previous "
        "books: within half a point a year from twenty to thirty-five, and one to three points "
        "a year by forty-five. (4) THE DECISION RULE, FIXED NOW SO THE RESULT CANNOT CHOOSE IT. "
        "The recommended width is the narrowest rung whose check-store worst fall is at or under "
        "23.0% -- the owner's 25% bar less a two-point cushion, because the check store is a "
        "cross-check and not truth and a recommendation resting on a tenth of a point of margin "
        "is not a recommendation -- provided its check-store return is within 1.0 point a year of "
        "the twenty-name arm's. If no rung satisfies both, the recommendation is the rung with "
        "the best check-store MAR and the verdict says plainly that the owner is being asked to "
        "buy safety with return. If the twenty-name arm itself clears 23.0%, the recommendation "
        "is TWENTY and the finding is that the two roster books differ -- which would be a "
        "genuine and reassuring result and must be reported as the primary one, not as an "
        "absence. (5) WHEN, NOT ONLY HOW FAR. The survivorship report gives the size of each "
        "worst fall and never its date, so 'the whole effect is one bad year' cannot be excluded "
        "from its rows alone. The month-end equity curve of every arm on both stores is available "
        "in process, so the peak month and the trough month of each worst fall will be computed "
        "and reported beside it, together with the worst fall inside each of 1998, the dot-com "
        "years, 2006, the financial crisis and 2010-2015. The prediction, carried over from the "
        "other book, is that the narrow arms trough in the spring of 2006 -- a 2% market dip that "
        "made a new high by September -- and the wide arms trough in 1998. If the dates instead "
        "cluster in the crises, that is a different mechanism from the one M0152 found and leads "
        "the verdict. (6) THE LIVE ROSTER ENTRY TRADES A DIFFERENT RULE SET from the one measured "
        "here: its resize band is read against equity and, measured on 2026-10-14, a band read "
        "that way never fires in a many-name book, so the monthly deposits reach the book only "
        "through turnover. The banded preset used here is the tape that invests them and is what "
        "the other book's whole curve was measured on. The size of that difference for THIS book "
        "is not measured by this method and the verdict must not pretend otherwise. "
        "ELIGIBILITY IS NOT THE POINT AND PROMOTION IS REFUSED. This line runs through M0002, "
        "which is test-failed, so the hard gate refuses promotion on kin whatever these arms "
        "score. Accepted before the run."
    ),
    expected_failure=(
        "THE MOST LIKELY DISAPPOINTMENT IS A FLAT CHECK CURVE. If all five check-store falls land "
        "within a point of each other and within the bar, then width buys this book nothing, the "
        "roster's second entry needs no change, and the five rungs priced one null result. That "
        "is still worth recording -- it would be the first evidence that the two roster books "
        "carry different single-name risk, and it would mean the owner can stop worrying about "
        "half of what he holds -- but it is a thinner result than the one predicted and the "
        "verdict must say so in its first paragraph rather than dress it up. "
        "Specific failures written now. (1) THE CURVE COULD RUN THE WRONG WAY. A wider book owns "
        "more of the shortlist and therefore more of the companies the dev store cannot price, so "
        "the check store could punish width rather than reward it, as it did to M0123's "
        "all-shortlist basket. A check-store fall that RISES from twenty to forty-five names "
        "would be a stronger argument for keeping twenty than any dev number and the verdict "
        "would have to carry it. (2) THE REGIME BRAKE COULD BE DOING THE WORK WIDTH WOULD "
        "OTHERWISE DO. This book already de-risks when its own volatility is high for itself, and "
        "a single holding collapsing inside a twenty-name book raises the basket's volatility. If "
        "so, the check-store falls will be flat in width AND the twenty-name arm will spend "
        "measurably more of the window below full exposure than the forty-five-name arm does. "
        "That is a mechanism, not a null, and it is the most interesting thing this method could "
        "find -- it would say the two roster books want different widths for a reason rather than "
        "by accident. (3) ONE ERA COULD BE DOING ALL THE WORK. If every arm's worst fall is dated "
        "inside one stretch and the 2009-2015 era leads are flat across width, this is a "
        "measurement of one episode dressed as a measurement of width. The trough dates are "
        "computed precisely so this cannot be glossed over; if the answer is one episode, the "
        "verdict leads with it and the recommendation is downgraded to a leaning rather than a "
        "number. (4) REPRODUCTION FIRST. lab survivorship prints a dev re-run beside the recorded "
        "trial. Any arm whose dev re-run does not land on its recorded trial has a meaningless "
        "side-by-side and must be dropped from the curve rather than quoted. (5) FEES AND FILL AT "
        "THE WIDE END. This account ramps from 10,000,000 IDR, so a forty-five-name book holds "
        "slots near 28 USD in its early years, where Gotrade's per-order floor is a large share "
        "of the order. Trade counts are quoted so the claim stays checkable. (6) THE CHECK STORE "
        "IS NOT TRUTH, and a recommendation that turns on the difference between 23% and 25% on "
        "it turns on which data errors somebody chose to clean. If the chosen rung clears 23.0% "
        "by less than half a point, the verdict must say the margin is inside the cross-check's "
        "own uncertainty and recommend the next rung out. (7) DEPOSITS SOFTEN EVERY WORST FALL "
        "HERE ALIKE and no figure may be lined up against an unfunded trial -- M0002's own "
        "recorded trials #75 to #80 included, which is the whole reason this method exists rather "
        "than a re-read of them. (8) THE RECOMMENDATION IS ABOUT WIDTH AND NOT ABOUT WHETHER TO "
        "HOLD THIS BOOK AT ALL. M0002 is test-failed and so is this line; nothing here says the "
        "picking rule works. It says only what it costs to hold it in twenty slots rather than "
        "more."
    ),
    candidates=tuple(
        _v(top, rationale)
        for top, rationale in (
            (20, "Twenty names: the roster's own width, and the first time this book has been "
                 "priced at the owner's real fees on a tape that invests his deposits"),
            (25, "Twenty-five names: the first rung past the roster, and the test of whether any "
                 "protection arrives gradually or in one step"),
            (30, "Thirty names: the rung that bought nothing on the other book, included so the "
                 "two curves can be read against each other rung for rung"),
            (35, "Thirty-five names: the width the other roster book was recommended at, asked of "
                 "this one"),
            (45, "Forty-five names: prices the far end, where the two price histories converged "
                 "on both books measured so far"),
        )
    ),
    seen_keys=(
        "concept:regime-vol-book-name-count",
        "concept:roster-relative-strength-book-width-on-the-check-store",
    ),
)

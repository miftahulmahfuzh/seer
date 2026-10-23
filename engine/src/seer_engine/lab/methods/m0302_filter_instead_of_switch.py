"""M0302 — can a calm filter replace the cash rule instead of sitting behind it?

Source: variation of M0293, which bolted a market-beta filter onto M0197's bond-like book and
found it was insurance bought on top of insurance. Behind the SPY 200-day switch every arm scored
the identical lead in 2008 because the switch had already taken the book to cash, so the filter
could never make a claim and still paid its premium for twenty years.

Idea: M0293 answered "does the filter add anything behind the switch" (no) and raised, but could
not answer, "can the filter stand in for the switch". This method turns the switch off and turns
the filter up. It does not propose a candidate: a book with no cash rule falls far too deep for
the owner's bar and is not meant to clear it. It measures one number — how much of a cash rule's
protection a pick filter can buy, and at what price — so the lab can stop stacking protections and
start choosing between them.

The engine is M0293's, imported and not re-written: this method changes only the dose and the
seeds, so the two are the same book by construction and the comparison across them is exact.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0293_calm_filter_on_a_host import (
    CALMFILTER,
    NOSW,
    CalmFilterParams,
)
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE

ADDED = date(2026, 10, 23)


def _v(suffix: str, drop_frac: str, side: str, seed: int, rationale: str) -> Candidate:
    """One arm of the ladder: M0293's engine on M0197's gate-off host, one dose, one seed."""
    return Candidate(
        id=f"M0302-{suffix}",
        family="M0302",
        rules=MONTHLY_HOLD_FRAC_GOTRADE,
        allocator=CALMFILTER,
        params=CalmFilterParams(NOSW, drop_frac=Decimal(drop_frac), side=side, seed=seed),
        rationale=rationale,
        added=ADDED,
        owner_inputs=(),
    )


# The two shallow rungs of the ladder are NOT registered here, and that is deliberate rather than
# an omission. ``CalmFilterParams(NOSW, 0, "high")`` and ``CalmFilterParams(NOSW, 0.25, "high")``
# are byte-identical to M0293-REF-NOSW and M0293-HI25-NOSW, which ran on this store today; because
# this method reuses M0293's allocator object, they digest the same and ``has_trial`` would refuse
# them after the backtest was already paid for. They are read off the record instead, which is the
# stronger version of the same thing: the ladder's first two points are measurements nobody can
# accuse this method of having tuned.

METHOD = Method(
    id="M0302",
    name="Can a calm filter replace the cash rule instead of sitting behind it?",
    family="stock-market-beta",
    source_kind="variation",
    source_ref=(
        "variation of M0293 (market beta as a safety filter on M0197-Y20-SW's book); "
        "Frazzini & Pedersen 2014, Betting Against Beta, JFE 111(1)"
    ),
    parent_id="M0293",
    hypothesis=(
        "M0293 bolted a market-beta filter onto M0197's bond-like book and found it was insurance "
        "bought on top of insurance: behind the SPY 200-day switch the book was already in cash "
        "through 2008, so the filter could never make a claim and still paid its premium for "
        "twenty years. M0293's own amendment turned the switch off and showed the filter doing "
        "real work for the first time -- dropping the jumpiest quarter cut the 2008 calendar loss "
        "from -39.5% to -24.5% (M0293-REF-NOSW vs M0293-HI25-NOSW, read from the recorded trials) "
        "-- but it could not say whether that was enough to stand in for the cash rule, because a "
        "quarter was the deepest dose it ever ran with the switch off. This method turns the dial "
        "up. Three facts frame it, all read off recorded trials on this store: switch ON and "
        "filter off, the book falls 22.0% (M0293-REF); switch OFF and filter off, it falls 62.1% "
        "(M0293-REF-NOSW); switch off with a quarter dropped, 56.4% (M0293-HI25-NOSW). So a "
        "quarter-drop bought 5.7 points of the 40.1 points the switch was worth -- about a "
        "seventh. The question is whether depth buys the rest. Two new rungs, 0.40 and 0.60, both "
        "with the switch off and nothing else changed, extend the recorded 0.00 and 0.25 into a "
        "four-point ladder. FOUR blind draws sit at the deepest rung, not one, because M0293's "
        "single blind control supported a 3.2-point claim that three more seeds erased, and "
        "because the lab has since measured that nineteen identical rules drawn blind span 7.5 "
        "points a year of return and 20.7 points of worst fall. The pool was measured before "
        "registration and not assumed: across the 79 quarterly re-ranks inside the scored window "
        "the screened pool runs 66 to 396 names (median 257), and a 0.60 drop never leaves fewer "
        "than 26, so every arm holds exactly 20 names fully invested and no dose can empty a slot "
        "into SPY -- the confound that sank M0277's and M0279's six pick filters. Success is "
        "stated narrowly and now: some registered dose brings the switch-off worst fall under 35%, "
        "keeps a lead over total-return SPY on the owner's deposits, and beats ALL FOUR blind "
        "draws at that dose on the worst fall. Anything less and the answer is that a cash rule "
        "protects far more cheaply than any pick filter, which is the publishable finding either "
        "way. Predictions, written before the run, on the recorded de-funded worst fall: D60 falls "
        "at least 8 points shallower than D40, so the dial is monotone and not U-shaped; D60's "
        "fall is at least 3 points below the shallowest of its four blind draws, without which the "
        "shrink was the diversifying and not the calmness; D60 gives up more than 2 points a year "
        "of funded return against M0293-REF-NOSW's +12.5%, because M0293's 0.50 rung with the "
        "switch on already cost 3.5 points a year against its own reference; and no arm here "
        "reaches 35%, so the method is rejected on its own stated success clause."
    ),
    expected_failure=(
        "The likeliest failure is that the ladder is flat where it matters, and M0293 has already "
        "half-shown it. Its gate-off quarter-drop fell 56.4% while its four blind quarter-drops "
        "fell 55.2%, 56.5%, 56.8% and 59.4% -- the calm arm sits INSIDE that spread and is beaten "
        "by one of the coins. Only on the 2008 calendar year did it clear them (-24.5% against a "
        "best blind of -28.5%). If the worst fall is the seed-noisy reading and the calendar year "
        "is the seed-stable one, the deep doses will shuffle inside a wide blind spread and the "
        "honest answer is that this method cannot distinguish the filter from the arithmetic of "
        "dropping names. Second, a trailing one-year beta is backward-looking and a crash is "
        "forward-looking: by mid-2008 Fannie Mae, Freddie Mac and the regional banks had not yet "
        "collapsed, so a deeper cut may simply remove more names that were never the problem. "
        "Third, and the reason the ladder may be U-shaped, a 0.60 drop leaves a median of 103 "
        "names of which the bond-like end is utilities and property, so the deep rungs concentrate "
        "the book in exactly the taper-scare exposure M0197 feared -- M0293's 0.50 rung with the "
        "switch on fell DEEPER than its 0.25 rung (25.2% against 20.3%) while losing 3.5 points a "
        "year, which is the U-shape already visible on the other side of the switch. Fourth, even "
        "a clean win here cannot become a candidate: 35% is far past the owner's 25% bar, so the "
        "best outcome available is a number, not a strategy. Fifth, betting against beta was "
        "published in 2014 at the very end of the dev window, so any dev edge here is the kind "
        "most likely to have faded. None of these is a reason to add a dose, change the host or "
        "re-seed a draw after the run."
    ),
    candidates=(
        _v("D40", "0.40", "high", 293,
           "Drop the jumpiest 40% of the pool with no cash rule: the middle rung of the dial, "
           "between M0293's recorded quarter and this method's 60%"),
        _v("D60", "0.60", "high", 293,
           "Drop the jumpiest 60% of the pool with no cash rule: the idea, the deepest dose, and "
           "the arm that must bring the fall under 35% to mean anything"),
        _v("D60-R1", "0.60", "blind", 302,
           "Control: drop the same 60% count by a fixed per-symbol hash — the placebo that prices "
           "what dropping any three fifths of the pool buys in a crash"),
        _v("D60-R2", "0.60", "blind", 303,
           "Control: the same hash-drawn placebo on a second seed, so the blind arm has a spread "
           "and not a point"),
        _v("D60-R3", "0.60", "blind", 304,
           "Control: the same hash-drawn placebo on a third seed"),
        _v("D60-R4", "0.60", "blind", 305,
           "Control: the same hash-drawn placebo on a fourth seed, because one coin toss cannot "
           "price a claim smaller than one coin toss"),
    ),
    seen_keys=(
        "concept:pick-filter-as-a-replacement-for-the-trend-switch",
        "concept:deep-dose-ladder-on-a-gate-off-book",
        "concept:four-blind-draws-at-the-deepest-dose",
    ),
)

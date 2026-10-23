"""M0314 — Does the switch's fall-spread invariance survive a less concentrated book?

Source: variation of M0306 (the finished gated-coin width measurement).

**Why this file does not run the idea row's original text.** M0314 was reserved asking for the
switched-on draw population to be widened from seven to nineteen seeds, at the same three
industries M0307 used. That exact measurement was completed and rejected today, as M0306: it ran
seeds 8-19 of the identical three-industry engine and found the switched-on fall spread is 22.9
points against the switched-off 20.7 — no narrower, slightly wider. Re-running the same widening
under a different method id would spend a second look to re-answer a question M0306 already
answered on the identical chassis (``lab seen`` holds it under ``concept:gated-draw-population-
completed-to-nineteen`` → M0306). A sibling method already running concurrently, M0313, carries
the obvious next step — does the finding transfer to a momentum-ranked book — so this file takes
a different, still-open branch of the same question instead of either duplicate.

Idea in one line: M0306's proposed mechanism for "the switch shrinks the fall but not its spread"
is that the switch removes the one shared anchor (2008) and leaves each draw's worst fall to its
own private whipsaw accident. A three-industry draw concentrates the whole twenty-name book into
three sector bets; a six-industry draw spreads the identical twenty slots over twice as many
sectors (``allot(20, 6)`` = 4/4/3/3/3/3 instead of 7/7/6). If idiosyncratic sector risk is what
drives the private-accident spread, a less concentrated book should show *more* narrowing behind
the switch than the three-industry book did (ratio clearly below 1.105); if the ratio does not
move, concentration is not the ingredient and M0306's practical rule — never read a gated
worst-fall gap under about 20 points as evidence — holds regardless of how a gated book is built.

**The construction, unchanged from M0295/M0296/M0306 except ``industries``.** Same F4 screen
(close >= $5, 20-day mean dollar volume > $20M, >= 253 bars), same Fama-French 12 taxonomy, same
``side="matched"`` blind industry draw by blake2b(seed | industry | year-month), same opinion-free
member order inside each chosen industry, same 20 total slots (just split over six industries
instead of three), same SPY 200-day switch via ``inner=GATED`` or ``inner=OPEN``. Three seeds each
way, matched seed for seed, so the switch's own contribution at this concentration is readable
directly off three pairs — the same design M0307 used for its first six switched-on draws, here
halved again because the question is the *direction* of a concentration effect, not its exact
width. Rules are ``monthly-hold-frac-gotrade``: fractional shares, Gotrade's real fees, the
owner's monthly deposits. Pure: reads only bars dated at or before d, no clock, randomness, file
or network of its own — it imports M0295's allocator object and param class unchanged.

Assumption, written before the run: a three-draw population is thinner than the seven M0307
itself flagged as only a lower bound, so this measures whether the ratio moves in a readable
direction, not its precise width. If the direction is clear, a follow-up amendment can widen it
the way M0296/M0306 did; if it is not, that is itself the answer to how many draws a concentration
comparison needs.
"""

from __future__ import annotations

from datetime import date

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0295_industry_bellwether_lead_lag import (
    GATED,
    LEADLAG,
    OPEN,
    LeadLagParams,
)
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE

ADDED = date(2026, 10, 23)

INDUSTRIES = 6
SEEDS = (1, 2, 3)


def _draw(seed: int, inner, tag: str) -> Candidate:
    gated = inner is GATED
    return Candidate(
        id=f"M0314-{'GDRAW6' if gated else 'NOGATE6'}-S{seed}",
        family="M0314",
        rules=MONTHLY_HOLD_FRAC_GOTRADE,
        allocator=LEADLAG,
        params=LeadLagParams(inner=inner, industries=INDUSTRIES, side="matched",
                             leader="largest", seed=seed),
        rationale=(
            f"blind draw {seed} of three, six industries instead of three, switch "
            f"{'on' if gated else 'off'} ({tag}) — a placebo shaped like a less concentrated "
            "version of M0306's book, differing from its switch-paired twin in nothing but the "
            "SPY 200-day gate"
        ),
        added=ADDED,
        owner_inputs=(),
    )


METHOD = Method(
    id="M0314",
    name="Does the switch's fall-spread invariance survive a less concentrated book?",
    family="market-shape-yardstick",
    source_kind="variation",
    source_ref="M0306",
    parent_id="M0306",
    hypothesis=(
        "M0306 measured, on a twenty-name book drawn blind from three Fama-French industries, "
        "that the SPY 200-day switch cuts every draw's worst fall by about 30 points on average "
        "while leaving the SPREAD of those falls no narrower than with the switch off (22.9 "
        "points gated against 20.7 ungated, a ratio of 1.105 where dilution by time invested "
        "alone predicts 0.720). The proposed mechanism was that the switch removes the one "
        "shared anchor every draw has in common -- 2008 -- and leaves each draw's deepest fall "
        "to its own private whipsaw accident, which the switch cannot flatten because it reads "
        "only the market, never the book. A three-industry draw concentrates all twenty slots "
        "into three sector bets, which is exactly the shape that would make private accidents "
        "large and idiosyncratic. This method rebuilds the identical measurement with the same "
        "twenty slots spread over six industries instead of three (4/4/3/3/3/3 instead of "
        "7/7/6) -- three switched-on draws and three switched-off draws, matched seed for seed. "
        "If sector concentration is what drives the private-accident spread, the six-industry "
        "switched-on/switched-off fall-spread ratio should sit clearly below the three-industry "
        "book's 1.105, because a less concentrated draw should leave less idiosyncratic risk for "
        "the switch to fail to flatten. Success is not a strategy and no arm is expected to be "
        "eligible: the deliverable is whether concentration is an ingredient in M0306's finding "
        "or whether the finding is a property of the switch alone, independent of how a gated "
        "book is built."
    ),
    expected_failure=(
        "The likeliest failure is that three draws each way is too thin to read a direction at "
        "all: M0307 already flagged seven draws as a lower bound on the three-industry book's "
        "width, and three is half that. The measured ratio could land anywhere within a wide "
        "band purely from which three hashes happened to be drawn, in which case the honest "
        "report is 'not resolved at this sample size' rather than a number, and a widening "
        "amendment (the way M0296 went 7 to 13 to 19) would be the next step rather than a "
        "verdict. The second failure is about the instrument rather than the mechanism: the "
        "Fama-French 12 taxonomy has roughly ten to twelve industries eligible on any given "
        "date, so a six-industry draw covers more than half the eligible pool and any two draws "
        "share several industries by construction -- far more overlap than a three-industry draw "
        "has. A narrower measured spread at six industries could then be a pool-exhaustion "
        "artefact (the draws are closer to being the same book) rather than evidence that "
        "diversification tames idiosyncratic whipsaw risk, and this method cannot tell the two "
        "apart on its own; it would need a universe larger than twelve industries to settle, "
        "which this lab's Fama-French taxonomy does not have. The third possibility is that the "
        "ratio simply does not move from M0306's 1.105, in which case concentration is not the "
        "ingredient, the shared-anchor-removal story needs no sector-risk term at all, and "
        "M0306's practical rule -- never treat a gated worst-fall gap under about 20 points as "
        "evidence -- applies to every shape of gated book the lab is likely to register, not "
        "only three-industry ones."
    ),
    candidates=(
        _draw(1, GATED, "switch on"),
        _draw(2, GATED, "switch on"),
        _draw(3, GATED, "switch on"),
        _draw(1, OPEN, "switch off"),
        _draw(2, OPEN, "switch off"),
        _draw(3, OPEN, "switch off"),
    ),
    seen_keys=(
        "concept:industry-concentration-and-switch-fall-spread",
        "concept:switch-fall-spread-by-book-concentration",
    ),
)

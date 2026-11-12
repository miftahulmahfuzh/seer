"""M0573 -- The plain market-value-weighted core, with the 200-day switch removed.

Source: variation of M0564 (CORE-TILT0, its no-opinion control for the industry-momentum-dilution
family).
Idea: M0564 registered CORE-TILT0 -- hold every known-industry member the store can size, weighted
by its own market value, no industry overweight at all, cash under SPY's 200-day average -- only
as a side-effect control inside a method built to test an industry-momentum TILT. M0564's own
analysis flagged CORE-TILT0 plainly: it "was never built or tested as a method in its own right,"
and under the combined run it lost 3 of 4 walk-forward folds and ran a negative 2009-2015 lead of
-6.2%/yr. What M0564 never separated is M0217's standing finding for this whole family: that its
2009-2015 weakness traces to time spent in cash under the 200-day SPY switch, not to the industry
mix. CORE-TILT0 has no industry mix at all (tilt=0), so it is the one book in the family where the
switch can be isolated with nothing else to confound the answer. This method registers that single
new arm and reads it against M0564-CORE-TILT0's already-recorded dev trial directly -- it does not,
and by the lab's own digest rule cannot, re-register CORE-TILT0's exact configuration as a new
trial (``lab run`` refuses a byte-identical config digest outright, with no override: "renaming
doesn't help, digests ignore the id").

On data date d, the one arm here, CORE-TILT0-NOSWITCH, is M0564-CORE-TILT0's exact book-construction
logic (``CoreTiltAllocator``, reused unchanged, ``tilt=0.0`` so no industry is ever overweighted),
with one single change:

    * the pool is F4's screened members on d, same universe and industry mapping as M0563/M0564
      (an unknown industry is excluded from the book, as in every recorded arm of this family);
    * industries with >= 5 pool members are identified (``MIN_MEMBERS``, M0563's exact bar), but
      at ``tilt=0`` no industry's members are ever overweighted -- every eligible member is held
      at its own plain market-value share, renormalized to 1;
    * no name above 10% of the whole account (the family's standing cap, M0034/M0221/M0563's
      water-filling), applied once across the renormalized core;
    * the ONE change from M0564-CORE-TILT0: always invested, no 200-day SPY switch
      (``inner.trend=None`` where M0564-CORE-TILT0 used ``("SPY", 200)``).

Why this is not a repeat of a recorded book. The trend parameter differs from every recorded arm
of this family that holds a market-wide core at tilt=0 -- M0564-CORE-TILT0 is the only one, and it
runs the switch. No recorded arm of M0563/M0216/M0217/M0564 has run the plain, untilted,
market-value core with the switch removed: M0563's own NOSW control (47.3% max DD) was measured on
its narrow, 3-4-industry concentrated book, not this market-wide one, and M0564 explicitly declined
to re-ask the switch question on the diluted book ("this run does not re-spend an arm re-asking
that question on the diluted book"). This run asks it, on the one book with no industry opinion
left to confound the answer.

How the comparison is made without a repeated arm. M0564-CORE-TILT0's dev trial is already
recorded (``lab show M0564``); this run's single CORE-TILT0-NOSWITCH trial is read against it
directly in the analysis -- same universe, same signal window, same cap, same cost model
(``MONTHLY_HOLD_FRAC_GOTRADE``, already Gotrade's real fees), the switch is the only variable that
moved. Comparing the two trials' 2009-2015 era slices (``lab survivorship``/era reads) answers
whether removing the switch recovers some or all of M0564-CORE-TILT0's recorded -6.2%/yr shortfall
there.

Assumption, written before any result: the ~38-43% of pool member-days in 2009-2015 with no known
market value (M0563/M0564's flagged gap, mostly later-delisted names) applies unchanged to this
arm; an edge or its absence that depends on the uncovered half is a question for
``lab survivorship``, not this run.

Market-aware (``market_fields = ("shares",)``, M0564's exact contract): the history-only path has
no share counts, so by contract it targets nothing. Rules are ``monthly-hold-frac-gotrade``:
fractional shares at Gotrade's real fees, asked monthly. Pure: no clock, randomness, files or
network in this file; reads only bars and share counts dated at or before d.
"""

from __future__ import annotations

from datetime import date

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0564_industry_momentum_diluted_core import CORETILT, CoreTiltParams
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.f_factor import FactorParams

ADDED = date(2026, 11, 12)

W6_NOSWITCH = FactorParams(rank="momentum", top=500, mom_n=126, mom_skip=21, trend=None)


def _v(suffix: str, params: CoreTiltParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0573-{suffix}", family="M0573", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=CORETILT, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0573",
    name="Plain market-value-weighted core, 200-day switch removed",
    family="stock-cap-weighted-core",
    source_kind="variation",
    source_ref="M0564",
    parent_id="M0564",
    hypothesis=(
        "M0564's own no-opinion control, CORE-TILT0 -- hold every known-industry member the store "
        "can size at its own market value, cash under SPY's 200-day average, no industry tilt at "
        "all -- was never built or tested as a method in its own right; under M0564's combined run "
        "it lost 3 of 4 walk-forward folds and ran a negative 2009-2015 lead of -6.2%/yr. M0217 "
        "found this family's 2009-2015 weakness traces to time spent in cash under the 200-day "
        "switch, not the industry mix -- and CORE-TILT0 is the one book in the family with no "
        "industry mix left to confound that answer. This method registers CORE-TILT0-NOSWITCH, the "
        "identical no-opinion core always invested (no switch), and reads it against "
        "M0564-CORE-TILT0's already-recorded trial to isolate the switch's own cost in 2009-2015 "
        "on this exact book (the lab's digest rule refuses re-registering M0564-CORE-TILT0's exact "
        "configuration as a new trial, so the comparison is made directly against that recorded "
        "trial rather than by re-running it here). Success: CORE-TILT0-NOSWITCH closes some or all "
        "of the recorded -6.2%/yr 2009-2015 shortfall relative to M0564-CORE-TILT0, confirming the "
        "switch (not the no-opinion core) was the drag in that era, and it clears DSR >= 0.90, "
        "worst fall <= 25%, PF >= 1.3 and a majority of its own walk-forward folds."
    ),
    expected_failure=(
        "Removing the switch could fail to close the 2009-2015 gap at all, meaning the plain "
        "market-value core itself -- not the timing overlay -- underperforms SPY in the best-covered "
        "era, which would mean this no-opinion construction has nothing left to offer the family "
        "regardless of what is layered on top of it (tilt, switch, or both). It is also possible "
        "removing the switch instead trades a 2009-2015 timing drag for a worse drawdown elsewhere "
        "(2008, 2020), the same trade M0563's own NOSW control made on its narrower book (47.3% max "
        "DD) -- a market-wide core is at least as exposed to a sharp trend reversal as a "
        "concentrated one, since it holds nearly the whole known universe either way. Finally, "
        "M0564-CORE-TILT0 already lost 3 of 4 walk-forward folds with the switch on; an "
        "always-invested twin of a book that already loses on picks, not on timing, may simply lose "
        "differently rather than win."
    ),
    candidates=(
        _v("CORE-TILT0-NOSWITCH",
           CoreTiltParams(W6_NOSWITCH, sectors=3, tilt=0.0, pick="momentum"),
           "The same plain market-value core as M0564-CORE-TILT0, same no industry opinion, always "
           "invested (no 200-day SPY switch) -- isolates the switch's own cost on the one book in "
           "this family with no industry mix left to confound the answer, read against "
           "M0564-CORE-TILT0's recorded trial rather than re-running it (that exact configuration "
           "is refused as a repeated dev-window digest)."),
    ),
    seen_keys=(
        "concept:market-value-core-no-opinion-standalone",
        "concept:core-no-opinion-switch-cutoff",
    ),
)

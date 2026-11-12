"""M0573 -- The plain market-value-weighted core of the whole known universe, on its own ticket.

Source: variation of M0564 (CORE-TILT0, its no-opinion control for the industry-momentum-dilution
family).
Idea: M0564 registered CORE-TILT0 -- hold every known-industry member the store can size, weighted
by its own market value, no industry overweight at all, cash under SPY's 200-day average -- only
as a side-effect control inside a method built to test an industry-momentum TILT. That control's
own analysis flagged it plainly: it "was never built or tested as a method in its own right," had
no expected_failure of its own and no success bar, and was never checked against the walk-forward
folds or the 2009-2015 era as a standalone hypothesis -- only read off M0564's combined run. This
method tests exactly that construction, with its own pre-registration, its own expected failure
and its own era/fold checks, rather than a number borrowed from another method's control arm.

M0564's own numbers already warn this is unlikely to survive: CORE-TILT0 lost 3 of 4 walk-forward
folds and ran a negative 2009-2015 lead of -6.2%/yr under M0564's combined analysis (both figures
re-verified here, not re-measured, since the trial is M0564's and this method does not re-run it --
see the CORE-TILT0-SWITCH arm below). The one thing M0564 never separated is M0217's standing
finding for this whole family: that its 2009-2015 weakness traces to time spent in cash under the
200-day SPY switch, not to the industry mix. CORE-TILT0 has no industry mix at all (tilt=0), so if
the switch is still the drag, a switch-off twin of the identical no-opinion core should recover
some or all of that 2009-2015 shortfall; if the shortfall persists with the switch removed, the
no-opinion core itself -- not the timing overlay -- is the weak link, and the plain market-value
core has nothing further to offer this family.

On data date d, both arms below share M0564's exact book-construction logic (``CoreTiltAllocator``,
reused unchanged, ``tilt=0.0`` so no industry is ever overweighted):

    * the pool is F4's screened members on d, same universe and industry mapping as M0563/M0564
      (an unknown industry is excluded from the book, as in every recorded arm of this family);
    * industries with >= 5 pool members are identified (``MIN_MEMBERS``, M0563's exact bar), but
      at ``tilt=0`` no industry's members are ever overweighted -- every eligible member is held
      at its own plain market-value share, renormalized to 1;
    * no name above 10% of the whole account (the family's standing cap, M0034/M0221/M0563's
      water-filling), applied once across the renormalized core;
    * CORE-TILT0-SWITCH holds cash under SPY's 200-day average, M0564's recorded setting
      (``inner.trend=("SPY", 200)``); CORE-TILT0-NOSWITCH is always invested (``inner.trend=None``)
      -- the only change between the two arms, isolating the switch's own cost on this exact book.

Why CORE-TILT0-SWITCH is not a new result. Its params are byte-identical to M0564-CORE-TILT0's
(``tilt=0.0, sectors=3, pick="momentum", cap=0.10, seed=1, market="SPY", inner=W6`` with
``trend=("SPY", 200)``) -- the same config digest, the same recorded curve. It is registered here
as a declared control, not as new evidence: its purpose is to let this method's OWN pre-registration,
N and promotion-path checks (``lab walkforward M0573``, ``lab survivorship M0573``) run against the
construction directly, rather than reading them off M0564's combined-method record, which mixes
CORE-TILT0 with four other tilted arms when the hard gate counts kin and folds. Its money and
metrics are M0564-CORE-TILT0's, first recorded under that trial, and are reported here under that
name, never as a new number.

Why CORE-TILT0-NOSWITCH is new. No recorded arm of this family has ever run the plain, untilted
market-value core with the 200-day switch removed -- M0563's own NOSW control (47.3% max DD) was
run on its narrow, 3-4-industry concentrated book, not this market-wide one, and M0564 explicitly
declined to re-ask the switch question on the diluted book ("this run does not re-spend an arm
re-asking that question on the diluted book"). This arm asks it, on the one book in the family with
no industry opinion left to confound the answer.

Assumption, written before any result: the ~38-43% of pool member-days in 2009-2015 with no known
market value (M0563/M0564's flagged gap, mostly later-delisted names) applies unchanged to both
arms here; an edge or its absence that depends on the uncovered half is a question for
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

SW = ("SPY", 200)
W6_SWITCH = FactorParams(rank="momentum", top=500, mom_n=126, mom_skip=21, trend=SW)
W6_NOSWITCH = FactorParams(rank="momentum", top=500, mom_n=126, mom_skip=21, trend=None)


def _v(suffix: str, params: CoreTiltParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0573-{suffix}", family="M0573", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=CORETILT, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0573",
    name="Plain market-value-weighted core of the whole known universe, no industry opinion",
    family="stock-cap-weighted-core",
    source_kind="variation",
    source_ref="M0564",
    parent_id="M0564",
    hypothesis=(
        "M0564's own no-opinion control, CORE-TILT0 -- hold every known-industry member the store "
        "can size at its own market value, cash under SPY's 200-day average, no industry tilt at "
        "all -- was never built or tested as a method in its own right; it fell out of M0564's run "
        "as a side effect of testing an industry-momentum tilt, with no standalone pre-registration, "
        "no own expected_failure and no success bar read against its own N. This method gives it "
        "both, and asks one further question M0564 explicitly declined to re-spend an arm on: M0217 "
        "found this family's 2009-2015 weakness traces to time spent in cash under the 200-day "
        "switch, not the industry mix -- and CORE-TILT0 is the one book in the family with no "
        "industry mix left to confound that answer. CORE-TILT0-SWITCH repeats M0564-CORE-TILT0's "
        "exact book (a declared control, not new evidence) so this method's own gate and fold checks "
        "run against the construction directly; CORE-TILT0-NOSWITCH is the same no-opinion core "
        "always invested, isolating the switch's own cost in 2009-2015 on this exact book. Success: "
        "CORE-TILT0-NOSWITCH closes some or all of the recorded -6.2%/yr 2009-2015 shortfall "
        "relative to CORE-TILT0-SWITCH, confirming the switch (not the no-opinion core) was the "
        "drag in that era, and either arm clears DSR >= 0.90, worst fall <= 25%, PF >= 1.3 and a "
        "majority of its own walk-forward folds."
    ),
    expected_failure=(
        "M0564's combined record already shows CORE-TILT0 lost 3 of 4 walk-forward folds, so "
        "CORE-TILT0-SWITCH (the identical book) is very unlikely to read differently under its own "
        "standalone fold check -- it is the same curve. The more informative failure is on "
        "CORE-TILT0-NOSWITCH: removing the switch could fail to close the 2009-2015 gap at all, "
        "meaning the plain market-value core itself -- not the timing overlay -- underperforms SPY "
        "in the best-covered era, which would mean this no-opinion construction has nothing left to "
        "offer the family regardless of what is layered on top of it (tilt, switch, or both). It is "
        "also possible removing the switch instead trades a 2009-2015 timing drag for a worse "
        "drawdown elsewhere (2008, 2020), the same trade M0563's own NOSW control made on its "
        "narrower book (47.3% max DD) -- a market-wide core is at least as exposed to a sharp trend "
        "reversal as a concentrated one, since it holds nearly the whole known universe either way. "
        "Finally, CORE-TILT0-SWITCH's book twin is M0564-CORE-TILT0 by construction: `lab run` is "
        "expected to record it as a declared repeat, not as a new trial, and the analysis must read "
        "its numbers as M0564's, never as a new result."
    ),
    candidates=(
        _v("CORE-TILT0-SWITCH",
           CoreTiltParams(W6_SWITCH, sectors=3, tilt=0.0, pick="momentum"),
           "Control: repeats M0564-CORE-TILT0's book exactly (identical config digest, identical "
           "curve) -- mounts this idea's own standalone pre-registration, N and era/fold checks "
           "against the construction directly, rather than borrowing them from M0564's combined "
           "five-arm run. Its money and metrics are M0564-CORE-TILT0's, first recorded there."),
        _v("CORE-TILT0-NOSWITCH",
           CoreTiltParams(W6_NOSWITCH, sectors=3, tilt=0.0, pick="momentum"),
           "The same plain market-value core, same no industry opinion, always invested (no "
           "200-day SPY switch) -- isolates the switch's own cost on the one book in this family "
           "with no industry mix left to confound the answer; no recorded arm of this family has "
           "run this exact combination before."),
    ),
    seen_keys=(
        "concept:market-value-core-no-opinion-standalone",
        "concept:core-no-opinion-switch-cutoff",
    ),
)

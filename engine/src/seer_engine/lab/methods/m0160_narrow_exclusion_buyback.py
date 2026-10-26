"""M0160 — The asymmetry book with momentum's top names barred, bought back on a positive quarter.

Source: a variation of M0150 (the asymmetry book ranked only outside momentum's own top names),
reserved as a backlog idea by Sera batch 20261016-2004 and refined here.

M0150 measured that barring momentum's own top companies from the asymmetry book's pool kills its
resemblance to the test-failed momentum book (0.8964 down to 0.28-0.55) but also removes most of
its edge: the cleanest arm, X20-G40 (momentum's top 20 barred, 40 names held, the plain 200-day
exit/entry), earned +10.3% a year funded against the market's +7.2%, held the parent's fall at
21.7%, but scored DSR 0.841 (N=101 at the time; N=235 today) against the 0.90 bar, and lost both
post-2009 folds (2009-2011, 2012-2014). Separately, M0133 measured that keeping the same 200-day
exit but letting M0113's measured-better trigger -- a positive trailing quarter -- time the
re-entry, instead of the plain 200-day cross, added about 1.1-1.6 points a year to the 20-name
book at an unchanged fall (M0133-G20 +15.6%/22.7% vs M0133-G20-UP63 +16.7%/22.7%), and M0150
confirmed the same trigger still helped once momentum's top 40 was barred (X40-G20-UP63
+11.7%/23.3%, DSR 0.821).

No configuration has combined the cheapest exclusion this family has measured (top 20, the one
that held the parent's fall almost exactly and was the closest of M0150's four arms to the luck
bar) with that same buy-back trigger. This method registers that cell, and its top-40 twin at the
same 40-name book size, so the exclusion width's dose-response can be read directly against
M0150's two plain-gate arms of the same two widths:

* ``X20-G40-UP63`` -- exclude momentum's top 20, hold 40, 200-day exit, positive-quarter re-entry.
  The headline: the cheapest exclusion this family has found, paired with the trigger that has
  added return at every book size tried so far.
* ``X40-G40-UP63`` -- exclude momentum's top 40 instead, same hold size and trigger. Pairs against
  M0150-X40-G40 (same exclusion and hold, plain gate) to read the buy-back's own contribution at
  the wider exclusion, and against M0150-X40-G20-UP63 (same exclusion and gate, 20-name hold) to
  read the hold-size effect separately from the trigger.

Everything else is M0150's code, imported unchanged: the exclusion, the asymmetry rank, the
weighting and the pricing. A difference from M0150's plain-gate arms can only be the trigger.

Assumptions, written before the run:

- The buy-back uplift measured so far (M0133, M0150) was always on a 20-name book. This run holds
  40, so the uplift could differ in either direction; it is not assumed to carry over unchanged.
- Kin is expected to stay clean: X20-G40 already read 0.551 against the failed momentum book
  (worst pair 0.814), and the buy-back only changes *when* the book is in or out, not which
  companies it holds when in. That is a reasoned expectation, not a measurement -- it is read from
  the recorded trial's own kin check, never assumed in the verdict.
- Reads only bars dated <= ``data_date``. Pure: no clock, no I/O, no randomness.
"""

from __future__ import annotations

from datetime import date

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0133_gated_updown_asymmetry import AsymParams, N40
from seer_engine.lab.methods.m0150_asymmetry_outside_momentum import EXCL, ExclParams
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE

ADDED = date(2026, 10, 26)


def _v(suffix: str, params: ExclParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0160-{suffix}", family="M0160", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=EXCL, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0160",
    name="The asymmetry book with momentum's top names barred, bought back on a positive quarter",
    family="stock-updown-asymmetry",
    source_kind="variation",
    source_ref=(
        "variation of M0150 (asymmetry book ranked outside momentum's own top names), adding "
        "M0113's positive-quarter re-entry trigger; reserved by Sera batch 20261016-2004"
    ),
    parent_id="M0150",
    hypothesis=(
        "M0150-X20-G40 (momentum's top 20 barred, 40 names held, plain 200-day gate) is the "
        "cleanest arm this family has found: it holds the parent's fall almost exactly (21.7% vs "
        "21.6%), reads clean against every test-failed book (0.551 against the failed momentum "
        "book, 0.814 worst case against any), but earns +10.3% a year funded against the market's "
        "+7.2% and scores DSR 0.841 against the 0.90 bar, short by about the margin the "
        "positive-quarter buy-back has added elsewhere: M0133-G20-UP63 added 1.1 points over "
        "M0133-G20 (+16.7% vs +15.6%, same 22.7% fall) and M0150-X40-G20-UP63 still beat the "
        "market by 11.7% a year once momentum's top 40 was barred too. No configuration has put "
        "that trigger on the top-20 exclusion. This method registers X20-G40-UP63 (exclude 20, "
        "hold 40, buy-back entry) and X40-G40-UP63 (exclude 40, same hold and trigger, the "
        "dose-response twin), each comparable to an existing M0150 plain-gate trial at the same "
        "exclusion and hold size. Success: X20-G40-UP63 gains on the order of 1-1.6 points a year "
        "over X20-G40 without moving the fall past 25%, clears or closes in on DSR 0.90, and wins "
        "at least one of the two post-2009 folds X20-G40 lost (2009-2011, 2012-2014)."
    ),
    expected_failure=(
        "The buy-back's measured uplift (1.1-1.6 points a year) came from 20-name books; this "
        "runs 40, and the size of the gain -- or whether there is one at all -- has not been "
        "measured at that book size. X20-G40 is already the cheapest-looking arm of the family, "
        "so there may be little room left for the trigger to add, and a thinner, "
        "momentum-adjacent pool could make the quarter-return re-entry noisier rather than "
        "better. Second, and most likely: the trigger changes only when the book re-enters after "
        "an exit, not whether leaving was the wrong call, and the known failure of every gated "
        "variant in this family is 2009-2015, a recovery decade with no real bear market where "
        "the gate itself loses 6-11 points a year to SPY (M0084, M0113). Both post-2009 folds may "
        "stay lost even if DSR improves, which leaves the hard gate's fold condition unmet. "
        "Third, survivorship is deferred again: nothing in this family has been dev-eligible, so "
        "no check has been owed yet, and this run likely will not change that."
    ),
    candidates=(
        _v("X20-G40-UP63", ExclParams(AsymParams(N40, gate="sma200-up63"), exclude_top=20),
           "Exclude momentum's top 20, hold 40, positive-quarter re-entry: the headline"),
        _v("X40-G40-UP63", ExclParams(AsymParams(N40, gate="sma200-up63"), exclude_top=40),
           "Exclude momentum's top 40 instead, same hold and trigger: the dose-response twin"),
    ),
    seen_keys=(
        "concept:asymmetry-exclusion-with-positive-quarter-buyback",
    ),
)

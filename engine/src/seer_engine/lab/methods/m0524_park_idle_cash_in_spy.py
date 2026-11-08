"""M0524 — Park the undeployed cash in SPY: is the 11% the book never spends a drag or a cushion?

Source: variation of M0519 (and M0269 before it). Both left about 11% of an equal-weight 50-stock
book idle (88.6% invested) while the book trailed SPY by about 0.7 points a year, and every attempt
to spend that cash on the fallers made things worse. The plain fix is older than any of them: do not
let money sit in cash, put it in the index (cash drag is textbook; no anomaly is involved, so there
is nothing here for the crowd to have faded).

THE LEVER is ``TradeRules.idle_symbol``: ``book_runner._with_idle`` gives the residual weight
``1 - sum(weights)`` to that symbol each decision. SPY is a default ETF, so it is allowed on
Gotrade. No lab method has set it before (``lab/exposure.py``), so this is also the first look at
whether the lever behaves.

FOUR ARMS on M0266's chassis (50 most-traded index members, equal weight, fractional shares,
Gotrade's real fees, the owner's monthly funding):
  * CASH: the host. Never resizes, idle money stays cash. It is M0266-L's book under this method's
    own allocator id, so it records as that book's twin (expected, costs no look).
  * SPY: the treatment. Same book, the residual goes to SPY.
  * SPY-HALF: no-opinion dose arm. The stock book scaled to half weight, the other half goes to SPY.
    If the stock picking has no edge over the index, this arm sits between SPY and SPY (scale 1),
    and the dose reads as a straight line toward SPY.
  * SPY-QUARTER: a second dose, a quarter in stocks.
Scales were fixed before any return was read.

Pure. The allocator is M0266's, reads only bars dated <= d; SPY's bar is the decision day's.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0127_slot_relative_resize_band import E1
from seer_engine.lab.methods.m0266_exposure_matched_rebalance import ScaledBandParams, ScaledMostTradedEqualWeight
from seer_engine.sim.rules import TradeRules

ADDED = date(2026, 11, 8)


class _HostBook(ScaledMostTradedEqualWeight):
    """M0266's book under this method's own id, so the CASH arm gets a new digest (it is M0266-L)."""

    id = "M0524"


BOOK = _HostBook()

PARK: TradeRules = replace(E1, id="monthly-hold-frac-gotrade-idle-spy", idle_symbol="SPY")


def _v(suffix: str, rules: TradeRules, scale: str, rationale: str) -> Candidate:
    return Candidate(
        id=f"M0524-{suffix}",
        family="M0524",
        rules=rules,
        allocator=BOOK,
        params=ScaledBandParams(scale=Decimal(scale)),
        rationale=rationale,
        added=ADDED,
        owner_inputs=(),
    )


METHOD = Method(
    id="M0524",
    name="Park the undeployed cash in SPY",
    family="portfolio-rebalancing",
    source_kind="variation",
    source_ref=(
        "M0519 and M0269, both of which left about 11% of the book idle and trailed SPY; M0266 "
        "(the cash was the point); M0054 (parks in SPY, but behind a trend switch)"
    ),
    parent_id="M0519",
    hypothesis=(
        "M0519 and M0269 left 11% of an equal-weight 50-stock book idle as cash (88.6% invested) "
        "while the book trailed SPY by 0.7 points a year, and every attempt to spend that cash on "
        "the fallers made things worse. Hypothesis: sending the idle cash into SPY itself removes "
        "the cash drag and closes most of that gap, without the deeper falls that buying fallers "
        "caused. Four arms on M0266's chassis (50 most-traded index members, equal weight, "
        "fractional shares, Gotrade real fees, owner funding): CASH (host, M0266-L's book twin under "
        "this method's own allocator id), SPY (residual into SPY), and two no-opinion dose arms, "
        "SPY-HALF and SPY-QUARTER (stock book at half and a quarter weight, rest in SPY), which show "
        "whether the stock picking adds anything over holding the index. Plain cash-drag fix, so the "
        "published-anomaly note does not apply. PREDICTIONS. (1) SPY beats CASH on funded return by "
        "0.5 to 1.0 point a year, as the idle 11% earns the index's rise. (2) Max drawdown is within "
        "a point of CASH's, because SPY is the market the book already mostly holds. (3) Still no "
        "beat of total-return SPY: the stock slots add nothing over SPY, so the dose arms line up "
        "monotonically toward SPY."
    ),
    expected_failure=(
        "The 50 most-traded members have no edge over SPY, so SPY-QUARTER beats SPY, which beats "
        "CASH, and nothing beats SPY itself: parking fixes the drag and the verdict is still reject. "
        "Or the idle residual is small and lumpy so SPY and CASH are nearly the same curve (a book "
        "twin, the lever never acted). Or the fees on rebalancing the SPY sleeve each decision eat "
        "the gain on small slots."
    ),
    candidates=(
        _v("CASH", E1, "1", "Host control: idle money stays cash, never resizes"),
        _v("SPY", PARK, "1", "THE TREATMENT: the same book, residual weight held in SPY"),
        _v("SPY-HALF", PARK, "0.5", "No-opinion dose: half the weight in the stock book, rest SPY"),
        _v("SPY-QUARTER", PARK, "0.25", "No-opinion dose: a quarter in the stock book, rest SPY"),
    ),
    seen_keys=(
        "concept:park-idle-cash-in-spy",
        "concept:idle-instrument-spy-residual",
    ),
)

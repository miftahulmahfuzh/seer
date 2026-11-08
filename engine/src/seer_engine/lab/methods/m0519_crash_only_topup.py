"""M0519 — Top up the fallers only in a crash: is the shallower fall bought by buying, or by waiting?

Source: variation of M0269. M0269 pulled trimming into its two halves and found the shallower worst
fall came from SPENDING on the fallers, not from selling the winners (selling into cash deepened the
fall), at a cost of about half a point a year in the calm 2009-2015 years. The idea row asks the
obvious next question: keep the buying, but only when the market is frightened. Buying the dip is a
decades-old idea (the volatility index, VIX, was published in 1993 and "buy when VIX spikes" has been
in the trade press since), so a strong dev result is likely to have faded by 2018.

THE LEVERS. Two new ``TradeRules`` levers, both ``LEVERS_SINCE_PINS`` no-ops at their defaults:
``resize_trims=False`` (a winner is never sold back to its slot: the adds-only half of resizing) and
``add_gate_vix`` (a held name below its slot is topped up only on a decision session whose previous
close had the VIX at or above the gate; below it the cash waits). ``backtest.book_runner`` reads the
VIX point in time through ``Market.series`` and hands ``step_book`` the gate; ``step_book`` refuses a
gated rule set whose caller did not.

FOUR ARMS on M0266's chassis (M0109's 50 most-traded index members, equal weight, fractional shares,
Gotrade's real fees, the owner's monthly funding). The hosting book is M0127's never-resize control
(M0266-L is this same book; NEVER repeats it under this method's own allocator id and so records as its book twin). The "no opinion" arm is ALWAYS, the same
adds-only book that tops up every month whatever the VIX says, so the gate's worth can be read apart
from the habit of topping up. THE CALIBRATION WAS MEASURED BEFORE ANY RETURN WAS READ: exposure only,
from a scratch run of ``dev.run_registry`` on the dev store, printing no return. At scale 1 the
never-resize control sits at 0.8865 average exposure, and a scale above 1 is refused, so the three
adds-only arms are scaled DOWN to it by bisection on exposure alone:

  * never-resize control, scale 1:        0.8865
  * adds every month (ALWAYS), 0.8263:    0.8871   (0.9817 at scale 1)
  * adds when VIX >= 25 (VIX25), 0.925:   0.8872   (0.9193 at scale 1)
  * adds when VIX >= 30 (VIX30), 0.98:    0.8857   (0.8975 at scale 1)

Every arm is inside the pre-registered half-point of the control. Realised exposure is re-read from
the recorded trials and any pair that misses by more than half a point is not compared. The
survivorship-check store was NOT calibrated separately (insight 527): its exposures will differ.

Pure. The allocator is M0266's (id M0266), imported and not re-typed; it reads only bars dated <= d,
and the VIX read is the previous close's.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0127_slot_relative_resize_band import E1, T20
from seer_engine.lab.methods.m0266_exposure_matched_rebalance import ScaledBandParams, ScaledMostTradedEqualWeight
from seer_engine.sim.rules import TradeRules

ADDED = date(2026, 11, 8)


class _HostBook(ScaledMostTradedEqualWeight):
    """M0266's book under this method's own allocator id. The NEVER arm is exactly M0266-L (same
    rules, same scale 1, same params), and ``lab run`` refuses a configuration already run on the
    dev window (the first attempt did, with nothing recorded). A new id gives the arm a new digest;
    it records as a book twin of M0266-L, which is expected, costs no look, and is named as such."""

    id = "M0519"


BOOK = _HostBook()

#: M0127's 20%-of-target band, adds only: the same resize rung as the sell-only arms of M0269, with
#: the selling switched off instead of the buying.
ADDS: TradeRules = replace(T20, id="monthly-hold-frac-gotrade-tband20-addsonly", resize_trims=False)
VIX25: TradeRules = replace(ADDS, id="monthly-hold-frac-gotrade-tband20-addsonly-vix25", add_gate_vix=Decimal("25"))
VIX30: TradeRules = replace(ADDS, id="monthly-hold-frac-gotrade-tband20-addsonly-vix30", add_gate_vix=Decimal("30"))


def _v(suffix: str, rules: TradeRules, scale: str, rationale: str) -> Candidate:
    return Candidate(
        id=f"M0519-{suffix}",
        family="M0519",
        rules=rules,
        allocator=BOOK,
        params=ScaledBandParams(scale=Decimal(scale)),
        rationale=rationale,
        added=ADDED,
        owner_inputs=(),
    )


METHOD = Method(
    id="M0519",
    name="Top up the fallers only in a crash",
    family="portfolio-rebalancing",
    source_kind="variation",
    source_ref=(
        "M0269, which found that topping up the fallers is what made the worst fall shallower and "
        "that it cost about half a point a year in 2009-2015; M0119 (feeding the laggard cost 1.1 "
        "points a year); M0266 (the cash was the point, not the rebalancing); insight 527"
    ),
    parent_id="M0269",
    hypothesis=(
        "M0269 found that topping up the fallers is what made the worst fall shallower (1.8 to 2.5 "
        "points at equal cash) and that it cost about half a point a year in the calm 2009-2015 "
        "years. Hypothesis: the shallower fall is earned only in the frightened months, so topping "
        "up only while the volatility index is high keeps the fall benefit and drops the calm-years "
        "cost. Four arms on M0266's chassis (50 most-traded index members, equal weight, fractional "
        "shares, Gotrade real fees, owner funding), all at the never-resize control's measured "
        "exposure (0.8865 on dev, calibrated before any return was read, see the module docstring): "
        "NEVER (host: the book that never resizes, M0266-L's book twin under this method's own allocator id), ALWAYS (the "
        "no-opinion arm: adds-only, tops up every month whatever the market does), VIX25 and VIX30 "
        "(adds-only, topping up only while the VIX at the previous close is at least 25 or 30). "
        "Published-anomaly note: buying the dip when the VIX spikes has been public for decades, so "
        "any dev edge probably predates 2018. PREDICTIONS. (1) Both gated arms have a worse "
        "2009-2015 result than NEVER by less than ALWAYS does (the gate recovers some of the calm "
        "cost). (2) Their worst fall is shallower than NEVER's by 1 to 2.5 points, no worse than "
        "ALWAYS's. (3) None beats SPY: all are 89%-invested books that fell behind SPY in M0269's "
        "family. No arm is a candidate and none has a preset."
    ),
    expected_failure=(
        "VIX25 and VIX30 top up so rarely that they are NEVER with a few extra trades: their curves "
        "match NEVER's or each other's (book twins), so the gate never acted and the dial reads as "
        "flat. Or the gate fires in 2008-09 only, once, so the whole result is one episode (one "
        "crash is one observation, not a pattern). Or cash that waited through a calm decade is "
        "larger than the crash buys back and the gated arms sit on dead cash at matched exposure, "
        "losing to ALWAYS in the calm years for the plain reason that they hold less stock when it "
        "rises. The check store was not separately calibrated."
    ),
    candidates=(
        _v("NEVER", E1, "1",
           "Host control: never resizes, scale 1; the exposure all other arms are matched to"),
        _v("ALWAYS", ADDS, "0.8263",
           "No-opinion arm: adds-only top-up every month, scaled down to the control's exposure"),
        _v("VIX25", VIX25, "0.925",
           "THE TREATMENT: top up the fallers only while the VIX is at least 25"),
        _v("VIX30", VIX30, "0.98",
           "THE SECOND TREATMENT: top up the fallers only while the VIX is at least 30"),
    ),
    seen_keys=(
        "concept:crash-only-topup-gate",
        "concept:vix-gated-faller-adds",
    ),
)

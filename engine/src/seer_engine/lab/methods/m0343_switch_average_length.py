"""M0343 — Switch average length: how many days the cash switch's moving average spans.

Source: variation of M0338's chassis (F4's screen, plain 12-1 ranking, top 20 equal weight,
monthly, SPY trend switch, Gotrade real fees, fractional shares). The switch is old (Brock,
Lakonishok & LeBaron 1992; Faber 2007), so no fade argument applies. M0338 waited days before the
switch flipped and got worse, so the one-day reading looks best; what no trial has varied on the
plain 12-1 book is the length of the average itself. M0267 and M0107 used 200 days as given.

Rule at each monthly check: SPY's close above its n-day average means invested, at or below means
cash. Only n differs between arms; the screen and ranking are M0338's, unchanged. Arms fixed before
any result: n=100, 150, 200 (paired control, must reproduce M0332-M12-1 and M0338-K1), 250, and the
same book with the switch off, always invested, which prices what acting on the signal costs.
Pure; reads only bars dated <= data_date.
"""

from __future__ import annotations

from datetime import date

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0338_switch_dwell_time import Alloc as _DwellAlloc
from seer_engine.lab.methods.m0338_switch_dwell_time import Params
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE

ADDED = date(2026, 11, 1)


class Alloc(_DwellAlloc):
    """M0338's allocator at dwell 1; only the average length (``params.trend``) moves."""

    id = "M0343"


ALLOC = Alloc()


def _v(suffix: str, rationale: str, n: int | None) -> Candidate:
    trend = None if n is None else ("SPY", n)
    return Candidate(id=f"M0343-{suffix}", family="M0343", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=ALLOC, params=Params(dwell=1, trend=trend),
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0343",
    name="Switch average length: how long a window the cash switch averages over",
    family="stock-switch-timing",
    source_kind="variation",
    source_ref="variation of M0338's chassis; Brock, Lakonishok & LeBaron (1992) and Faber (2007) for the trend switch",
    parent_id="M0338",
    hypothesis=(
        "Waiting days before the switch flips made it worse (M0338), so the first-day reading looks "
        "best, but the 200-day length itself was never varied on the plain 12-1 book. Question: do a "
        "100, 150 or 250-day average change the false alarms, the 2008 exit and the 2009 return "
        "enough to beat 200? Book: F4's screen, plain 12-1 ranking, top 20 equal weight, monthly, "
        "fractional shares at Gotrade's real fees. Arms: 100, 150, 200 (control, must reproduce the "
        "recorded plain 12-1 trial), 250, and always invested to price what the switch costs. The "
        "switch is decades old, so no fade argument applies. Success: a length other than 200 keeps "
        "the worst fall at or under the control's with a better funded return and a smaller "
        "2009-2015 gap to SPY."),
    expected_failure=(
        "The 200-day length is an accident of history and the other lengths are noise in the same "
        "direction: 100 and 150 flip more often, pay more fees and whipsaw in 2009-2015; 250 exits "
        "late in a real fall. Every arm lands within draw noise of 200, and the always-invested "
        "twin falls far deeper, as every momentum book here does. A single length that looks best "
        "is the best of four tries, not a finding."),
    candidates=(
        _v("N100", "treatment: 100-day average, faster to flip", 100),
        _v("N150", "treatment: 150-day average", 150),
        _v("N200", "paired control: the usual 200-day, must reproduce M0332-M12-1", 200),
        _v("N250", "treatment: 250-day average, slower to flip", 250),
        _v("NOSW", "no opinion: same book, switch off, always invested", None),
    ),
    seen_keys=("concept:switch-average-length", "concept:trend-switch-ma-length-sweep"),
)

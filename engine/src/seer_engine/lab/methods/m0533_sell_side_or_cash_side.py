"""M0533 — Does the sell-side or the cash-side cost the add-only book its extra fall?

Source: variation on M0532, whose add-only arms spent each top-up promptly and raised exposure
from about 89% to 99%, yet cut the funded return by 0.3 to 0.4 points a year and deepened the
worst fall by 7 to 8 points. Two levers moved together in those arms: the rebalancing band was
shut to zero, and trims were switched off. Cash drag is textbook, not a published anomaly, so
nothing here has had a crowd to fade.

THE 2x2, on M0532's one fixed host (the 50 most-traded index members, equal weight, fractional
shares, Gotrade's real fees, the owner's monthly funding), under this method's own allocator id so
every arm is a fresh digest. Same names and weights on every rank date; only deployment differs.
  * BAND1-TRIM:  1% band, trims on  - today's rule (E1). Book twin of M0532-HABIT. Control.
  * BAND0-NOTRIM: band shut, trims off - M0532's ADD-MONTHLY. Book twin of it. Expected, no look.
  * BAND0-TRIM:  band shut, trims on  - every gap is traded both ways. NEW cell.
  * BAND1-NOTRIM: 1% band, trims off  - the band still gates, nothing is ever sold. NEW cell.
Reading the square: moving across trims at a fixed band prices the sell side; moving down the band
at fixed trims prices the cash side (small deposits trading below the band). If BAND0-TRIM keeps
the fall of BAND1-TRIM while BAND0-NOTRIM deepens it, the sell side was what protected the book.

Pure. The allocator is M0266's and reads only bars dated <= d.
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

ADDED = date(2026, 11, 9)


class _HostBook(ScaledMostTradedEqualWeight):
    """M0266's book under this method's own id: a new digest, the same names and weights."""

    id = "M0533"


BOOK = _HostBook()
PARAMS = ScaledBandParams(scale=Decimal(1))

BAND0_TRIM: TradeRules = replace(E1, id="monthly-hold-frac-gotrade-band0-trim", resize_band=Decimal("0"))
BAND0_NOTRIM: TradeRules = replace(
    E1, id="monthly-hold-frac-gotrade-add-only", resize_band=Decimal("0"), resize_trims=False
)
BAND1_NOTRIM: TradeRules = replace(E1, id="monthly-hold-frac-gotrade-band1-notrim", resize_trims=False)


def _v(suffix: str, rules: TradeRules, rationale: str) -> Candidate:
    return Candidate(
        id=f"M0533-{suffix}",
        family="M0533",
        rules=rules,
        allocator=BOOK,
        params=PARAMS,
        rationale=rationale,
        added=ADDED,
        owner_inputs=(),
    )


METHOD = Method(
    id="M0533",
    name="Is it the selling or the cash that deepens the add-only fall?",
    family="deposit-deployment",
    source_kind="variation",
    source_ref="M0532 (add-only arms: exposure 88.6% to 99%, return -0.3 to -0.4 pts/yr, fall +7 to +8 pts); M0269 (trims and fall)",
    parent_id="M0532",
    hypothesis=(
        "M0532 changed two things at once: it shut the band and it stopped selling. Run the 2x2 on "
        "the same host, monthly, fractional, Gotrade real fees, owner funding: band 1% or shut, "
        "trims on or off. Arms: BAND1-TRIM (today's rule, book twin of M0532-HABIT), BAND0-NOTRIM "
        "(M0532's ADD-MONTHLY, book twin), and two new cells, BAND0-TRIM and BAND1-NOTRIM. "
        "PREDICTIONS, written before any return was read. (1) BAND0-NOTRIM and BAND1-NOTRIM have "
        "the deeper worst fall than the two trim arms, because with no selling a falling book "
        "holds its losers and the deposit buys more of them (M0269: selling winners made the fall "
        "worse, but trimming is the only rule that ever raises cash in a decline). (2) Shutting "
        "the band at fixed trims moves the funded return by under 0.3 points a year, since the "
        "deposit is a small share of the account. (3) Exposure is highest for BAND0-NOTRIM. "
        "(4) 2009-2015 reads the same sign as the whole window; no arm beats deposit-matched SPY."
    ),
    expected_failure=(
        "The four arms land within noise of each other, so deposit handling is not a lever at this "
        "book size. Or BAND1-NOTRIM shares BAND1-TRIM's curve (a band that is never crossed upward "
        "never trims, so the trims dial never turned), which would say the fall difference is the "
        "band alone. Or BAND0-TRIM shares BAND0-NOTRIM's curve."
    ),
    candidates=(
        _v("BAND1-TRIM", E1, "Control: today's rule, 1% band, trims on"),
        _v("BAND0-TRIM", BAND0_TRIM, "Band shut, trims on: every gap traded both ways"),
        _v("BAND1-NOTRIM", BAND1_NOTRIM, "1% band, trims off: the band gates, nothing is sold"),
        _v("BAND0-NOTRIM", BAND0_NOTRIM, "Band shut, trims off: M0532's add-only monthly arm"),
    ),
    seen_keys=(
        "concept:sell-side-versus-cash-side-2x2",
        "concept:band-versus-trims-split",
    ),
)

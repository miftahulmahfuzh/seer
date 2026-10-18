"""M0226 — The dividend-raise lean on the whole market: every index member at its real size.

Source: M0222 (the same FTSE/MSCI-style raise tilt on the 50 biggest companies) and its analysis:
the tilt beat a random tilt of the same strength by 0.2-0.4 points a year (0.4-1.0 on the
survivorship-check store), but the top-50 core trailed SPY by 1.2 points a year, so M0222 said
nothing about whether a raise tilt can beat the market. Reserved by Sera 20261018-2051 as M0226.

What changes. Only the core's breadth and the ceiling. ``top`` is set past the number of index
members the store ever holds on one day (the S&P 500 plus the Nasdaq-100 is about 600), so the
core is every screened member with a known market value, one class per company, weighted by that
value; ``ceiling`` drops from 10% to 5%, the ceiling the lab has used on size-weighted books
since M0047, because a wider book lets the biggest names carry less of it before the cap binds.
Everything else -- the score, its neutral cases, the random twin's draw, the screen, the
target-relative band, the fees -- is M0222's allocator, run unchanged with these params, so the
difference to M0222 is the core and nothing else.

Why reuse rather than copy. A config digest names the allocator by id, and M0222's allocator
already takes ``top`` and ``ceiling`` as parameters; a copy under a new id would be the same code
twice. The lab counts this as its own method (its own pre-registration and its own N look).

Two things to read off the result, written before it: (1) whether CORE now tracks SPY within half
a point a year on the owner's deposits (M0221-C100 at real fees trailed by 2.4, worse than C50's
1.6, so wider may not mean closer: the store misses the dead companies and fifty-plus small
orders a month cost real fees); (2) whether TILT1/TILT2 still beat RAND1/RAND2 when the score has
hundreds of names, many with bigger raises and cuts than the giants', to spread over.

Pure: reads only bars, dividends and share counts dated <= d (the reused allocator's contract).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0070_dividend_raise_drift import NOT20
from seer_engine.lab.methods.m0222_raise_tilted_market_core import TILT, TiltParams
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE_TBAND

ADDED = date(2026, 10, 18)
EVERY = 1000  # past any day's member count: the core is every member with a known size
CEIL = Decimal("0.05")


def _p(power: int, order: str = "raise") -> TiltParams:
    return TiltParams(NOT20, top=EVERY, ceiling=CEIL, power=power, order=order)


def _v(suffix: str, params: TiltParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0226-{suffix}", family="M0226", rules=MONTHLY_HOLD_FRAC_GOTRADE_TBAND,
                     allocator=TILT, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0226",
    name=(
        "The dividend-raise lean on the whole market: every index member at its real size, "
        "not only the 50 biggest"
    ),
    family="stock-dividend-change-drift",
    source_kind="variation",
    source_ref=(
        "M0222 (raise tilt on the top-50 market-value core) and its analysis; FTSE Russell "
        "factor-tilt method; Michaely, Thaler & Womack (1995), JF 50(2); M0221 (cap-weighted "
        "top-N yardstick); M0047 (a size-weighted book needs a ceiling)"
    ),
    parent_id="M0222",
    hypothesis=(
        "Published 1995 (dividend-change drift); tilting is index practice since about 2013. "
        "M0222 tilted the 50 biggest companies by market value toward dividend raisers; the "
        "tilt beat a random tilt of the same strength by 0.2-0.4 points a year (0.4-1.0 on the "
        "survivorship-check store), but the top-50 core trailed SPY by 1.2 points a year, so "
        "the test said nothing about whether a raise tilt can beat the market. Run M0222's "
        "allocator unchanged except for the core: every F4-screened index member with a known "
        "point-in-time market value (top=1000, past any day's member count), one class per "
        "company, weighted by market value, no company over 5%. Same score (normal-CDF of the "
        "dividend change against its own prior payments, scaled by the day's rms change, neutral "
        "0.5, raises up, cuts down), power 1 and 2, against CORE (power 0) and RAND1/RAND2 (the "
        "day's non-neutral scores handed to hash-drawn names). All monthly, fractional, Gotrade's "
        "real fees, target-relative band, owner's deposits, no SPY parking, no 200-day switch "
        "(M0222's switched twin lost 3 of 4 folds and trailed by 8 points in 2009-2015). Success: "
        "TILT1 or TILT2 beats total-return SPY on the owner's deposits, beats its RAND twin and "
        "CORE, and does not trail SPY in 2009-2015. Also read: does CORE now track SPY within "
        "half a point a year? Assumptions: 5% ceiling (M0047's), the tband preset so deposits "
        "reach hundreds of sub-1% weights, first payments neutral."
    ),
    expected_failure=(
        "Hundreds of small orders a month at Gotrade's minimum fees cost more than the tilt "
        "earns: on the owner's 5M IDR deposits a 0.2% weight is a sub-dollar order. M0221 "
        "already showed a wider cap-weighted core trailing more, not less (top-100 +4.8% a year "
        "against top-50's +5.6% and SPY's +7.2%). About 44% of member-days have no market value "
        "(mostly members with no bars at all, the companies that later died), so the core is "
        "the survivors' market, not SPY, and in 2009-2015 it lacks some of the era's biggest "
        "winners, so CORE trails SPY by 1-3 points. The tilt's spread grows with smaller names' "
        "bigger raises and cuts, but the weight it moves sits mostly in the giants, where raises "
        "are routine, so the tilt-minus-random gap stays at tenths of a point. Ungated, every "
        "variant falls 45-55% in 2008, twice the bar. A published anomaly; any dev edge may "
        "have faded; dividend withholding tax is not modelled."
    ),
    candidates=(
        _v("CORE", _p(0), "The yardstick: every member with a known size at market value, 5% ceiling, no tilt"),
        _v("TILT1", _p(1), "Market value x dividend-change score (normal-CDF, neutral 0.5)"),
        _v("TILT2", _p(2), "Market value x score squared: the stronger tilt"),
        _v("RAND1", _p(1, "random"), "Control: the same day's scores handed to hash-drawn names, power 1"),
        _v("RAND2", _p(2, "random"), "Control: the same day's scores handed to hash-drawn names, power 2"),
    ),
    seen_keys=(
        "concept:dividend-increase-drift",
        "concept:dividend-change",
        "concept:market-cap-weight",
        "concept:factor-tilt",
        "concept:random-tilt-control",
        "concept:whole-market-core",
    ),
)

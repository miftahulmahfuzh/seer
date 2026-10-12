"""M0030 — Hold the market as the core and add momentum on top: an SPY core with a residual-momentum satellite.

Source: a variation of M0029, after its test-window look; the lab's P7a F9 (a timed SPY core with
a plain-momentum satellite, +12.2% a year at a 19.2% worst fall on dev, failing only the old 15%
limit and a luck score it never had the moments to compute) is the closest prior.
Idea: M0029 (70% residual momentum, 30% calm stocks, fractional) was fully invested on 2016-2026
and still made 7.4% a year vs SPY's 13.6%: the decade's risk was lagging a few mega-cap leaders,
which an equal-weight 40-stock book barely owns. A core that holds SPY itself owns those leaders by
construction; a residual-momentum satellite (M0007-N20-RAW's book) adds the dev window's edge.

No new allocator: ``BLEND`` of the index ``TIMING`` allocator (hold SPY) and ``RESIDMOM``, each on
its fixed share of equity, in fractional shares (``monthly-hold-frac``) as paper would trade it.
Every piece reads only bars dated <= d.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Amendment, Method
from seer_engine.lab.methods.m0007_residual_momentum import (
    N20_NOTREND,
    RESIDMOM,
    ResidParams,
)
from seer_engine.lab.methods.m0011_raw_residual_own_vol import RAW20
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC
from seer_engine.strategies.allocator import BLEND, BlendParams, BlendPart
from seer_engine.strategies.f_index import TIMING, TimingParams

ADDED = date(2026, 10, 7)

TIMED_SPY = TimingParams(hold="SPY", signal="SPY", rule="sma", n=200)  # F1/F9's core, verbatim
ALWAYS_SPY = TimingParams(hold="SPY", signal="SPY", rule="always")


def _blend(core: TimingParams, core_share: str) -> BlendParams:
    c = Decimal(core_share)
    return BlendParams((BlendPart(TIMING, core, c), BlendPart(RESIDMOM, RAW20, Decimal(1) - c)))


def _v(suffix: str, params: BlendParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0030-{suffix}", family="M0030", rules=MONTHLY_HOLD_FRAC, allocator=BLEND,
                     params=params, rationale=rationale, added=ADDED, owner_inputs=())


# --------------------------------------------------------------------------- amendment 2026-10-12
#
# The exposure diagnostic (`lab exposure`, 2026-10-12; dev window 1996-01-03..2015-10-16, research
# store 77c37d553508, prices 5451195f; committed grid docs/backtests/2026-10-12-exposure-diagnostic
# -grid.csv) re-ran each of this method's three recorded versions four ways, and one of its four
# arms -- "its own picks at full size", which drops the parked SPY holding and rescales the
# survivors to fill the book -- lands on the SAME numbers for C70T, C50T and C50A. It has to:
# dropping SPY and rescaling leaves RESIDMOM on RAW20 alone at 100% whatever the core share was.
# That arm is the strongest post-2009 reading anywhere in the grid, and it is the only reason this
# amendment exists. The three candidates below turn it into something the lab can be held to.
#
# What the grid says, so the prediction below can be read against it later:
#   M0030-C50T as recorded     12.7%/yr, lead +4.7 whole / -1.7 for 2009-2015, 18.6% worst fall
#   M0030-*-FULL (all three)   15.4%/yr, lead +7.5 whole / +2.7 for 2009-2015, 20.4% worst fall
#   the parked SPY alone        9.7%/yr, lead +1.8 whole / -5.8 for 2009-2015, 19.0% worst fall
#   share of C50T's book ever in its own picks: 35.6%
#
# EVERY FIGURE IN THAT BLOCK IS UNFUNDED. `lab exposure` re-runs each trial at its own recorded
# capital and funding, and this method's three recorded trials (126, 127, 128) were lump-sum runs
# of 20,000,000 IDR with no monthly top-up -- recorded before the lab runner was funded on
# 2026-10-08, and carrying no trial_funding row at all. The three candidates below run FUNDED, at
# today's INITIAL_IDR of 10,000,000 plus 5,000,000 on the 25th of each month (237 deposits). So
# the 20.4% worst fall is a re-weighted lump-sum number and the funded run may land either side of
# the owner's 20% bar; the hypothesis below says so before the run rather than after it. For the
# same reason these three are NOT comparable column-for-column with C70T/C50T/C50A: the honest
# comparison is money-weighted return against deposit-matched SPY. (M0053's five recorded trials
# ARE funded at 10,000,000 and its amendment is genuinely comparable -- this caveat is this
# method's alone.)
#
# SAT100 is not literally that arm: the diagnostic rescales a blend's surviving sleeve each
# decision, while SAT100 is a plain residual-momentum book from its first day. The two should land
# close; they are not required to agree digit for digit, and the hypothesis says so.

AMENDED = date(2026, 10, 12)

# RAW20 (M0007-N20-RAW's params, imported above) with the shared SPY 200-day gate switched off and
# nothing else changed: FactorParams.trend is the single read every gated book in this lab shares.
SAT_NOGATE = ResidParams(N20_NOTREND, scaled=False)


def _a(suffix: str, allocator, params, rationale: str) -> Candidate:
    """An amendment candidate: the method's own rules and flat cost, dated to the amendment."""
    return Candidate(id=f"M0030-{suffix}", family="M0030", rules=MONTHLY_HOLD_FRAC,
                     allocator=allocator, params=params, rationale=rationale, added=AMENDED,
                     owner_inputs=())


AMENDMENT_2026_10_12 = Amendment(
    added=AMENDED,
    why="The parked market money is the drag, and the gate is one year of value",
    hypothesis=(
        "Measured 2026-10-12 on the dev window with the committed research store (77c37d553508): "
        "re-running all three recorded versions of this method with the parked SPY core dropped "
        "and the satellite rescaled to fill the book gives the same result for every one of them "
        "-- 15.4% a year against deposit-matched SPY's 7.9%, a +7.5-point lead over the whole "
        "window and +2.7 a year after 2009, at a 20.4% worst fall and a profit factor of 2.11. "
        "The post-2009 figure is the strongest reading anywhere in that grid; every other arm of "
        "every other live book is behind the market over that stretch. Only 35.6% of M0030-C50T's "
        "book was ever in its own picks, and the parked market money priced on its own leads by "
        "just +1.8 over the whole window while trailing by 5.8 after 2009. On this book the core "
        "is the drag and the satellite is the edge, which is the inverse of what the dividend "
        "family turned out to be. "
        "SAT100 makes that a candidate instead of a column in a diagnostic: the residual-momentum "
        "satellite alone, filling the book, on the same monthly-hold-frac rules and the same flat "
        "0.1% cost as the three recorded versions. It should land near +15% a year, beat SPY TR "
        "comfortably, hold a profit factor near 2 and trade well over a thousand times. "
        "Every number quoted above is an UNFUNDED one, and this run will not be. The three "
        "recorded versions of this method (trials 126, 127 and 128) were lump-sum runs of "
        "20,000,000 IDR with no monthly top-up, recorded before the lab's runner was funded on "
        "2026-10-08: they carry no funding row at all. The exposure diagnostic re-runs each trial "
        "at its OWN recorded capital and funding, so the 20.4% worst fall quoted for the full-size "
        "arm is that same lump-sum geometry. These three new candidates run funded -- 10,000,000 "
        "IDR to start plus 5,000,000 IDR on the 25th of each month, 237 deposits -- which changes "
        "the shape of the equity curve a drawdown is measured on. The 20.4% is therefore a "
        "re-weighting of an unfunded book, and the funded run may land either side of the 20% bar: "
        "deposits arriving through a fall can deepen a percentage drawdown or cushion it, and "
        "nothing in the grid settles which. "
        "The prediction, stated with that caveat in front of it: SAT100 is expected INELIGIBLE on "
        "max drawdown, because the unfunded re-weighting sits 0.4 points above the limit and "
        "nothing about funding is expected to move it by much more than that -- while clearing "
        "beats-SPY, profit factor and trade count. It is a weak prediction on that one condition "
        "ON PURPOSE, and it is written weak before the run rather than sharpened after it. What "
        "is NOT weak is the reason for recording it: if the drawdown breach holds, the only "
        "post-2009 edge this lab has found is a configuration that exists only above the owner's "
        "risk limit, and the lab will hold that as a pre-registered, recorded trial rather than as "
        "an inference from a re-weighting column in a report. If it clears instead, that is a "
        "bigger finding than the one predicted and it must be reported first and loudly. "
        "Because the funding differs, SAT100's numbers must NEVER be put in the same column as "
        "C70T's, C50T's or C50A's; the comparison that is honest is money-weighted return against "
        "deposit-matched SPY, which is what the write-up will report. "
        "The two NOGATE arms ask the second question: what the shared SPY 200-day gate is worth "
        "on this book. Four of the five live books go to cash on the same 28.3% of decision days "
        "behind the same read of SPY against its 200-day average (67 of 237 monthly decisions), "
        "and that one rule produced an identical +34.8-point lead in 2008 for every one of them: "
        "one trade shared five ways, not five discoveries. The lab's own recorded control -- "
        "M0024-SAME-N20 against M0024-SAME-N20-NOTREND -- prices the gate at +2.7 a year gated "
        "against +1.0 ungated over the whole window, but after 2009 the gated version trails by "
        "5.4 while the ungated one leads by 1.5. SAT100-NOGATE is SAT100 with that gate removed "
        "and nothing else changed, so the gap between the two is the gate's price on THIS book "
        "rather than on the seasonality book. C50A-NOGATE is the recorded C50A with the gate off "
        "on BOTH legs -- the always-held core never had one, so this removes the satellite's -- "
        "and shows what the book as the owner might actually hold it looks like with nothing "
        "braking it at all. Expected: both ungated arms lead after 2009 and lose badly in 2008."
    ),
    expected_failure=(
        "The most likely outcome is the one predicted above, and it is written here before the run "
        "so the result cannot be read afterwards as a success: SAT100 misses the 20% drawdown "
        "limit by a small margin and is ineligible, so this amendment promotes nothing and is "
        "worth running only for what it records. "
        "The drawdown prediction is the WEAKEST claim in this pre-registration and that is stated "
        "here rather than discovered later. The 20.4% it rests on was measured on an unfunded, "
        "20,000,000 IDR lump-sum book -- the capital this method's three recorded trials actually "
        "had -- and SAT100 runs funded at 10,000,000 IDR plus 5,000,000 a month. A margin of 0.4 "
        "points is well inside the distance that change alone could move, in either direction. So "
        "a reading of 19.6% is NOT a refutation of this amendment's thesis and must not be "
        "reported as one, and a reading of 21% is not a confirmation of a sharp prediction; both "
        "are the same finding at a different decimal. The claim worth holding this amendment to is "
        "the one the funding does not touch: whether the satellite alone keeps a positive lead "
        "over deposit-matched SPY after 2009 when it is actually run rather than re-weighted. "
        "Beyond that, the +2.7 post-2009 reading is one stretch of one window measured once, and "
        "the satellite's whole-window lead leans on 1996-2002 (+9.7), the era where the dev "
        "store's survivorship-free coverage is thinnest. SAT100 is a plain residual-momentum book "
        "from its first day, not a blend rescaled each decision, so it need not reproduce the "
        "diagnostic arm digit for digit; if its post-2009 lead comes in materially below +2.7, "
        "then the one encouraging number in the grid was an artefact of the re-weighting and this "
        "is simply M0007-N20-RAW in fractional shares, already recorded and already short of the "
        "bar. "
        "The NOGATE arms are expected to fail harder and for a reason the lab already knows: "
        "without the gate the 2008 fall is taken in full, so both should breach 20% by a wide "
        "margin -- M0024-SAME-N20-NOTREND drew down 61.0% -- and C50A-NOGATE inherits half of "
        "SPY's roughly 55% fall on top of an ungated momentum satellite. Their verdict will most "
        "likely be that the gate buys the drawdown the owner's bar requires and costs the return "
        "he would rather have, which is a trade for him to price, not for the lab to tune away. "
        "No intermediate core split and no intermediate brake setting is in this amendment. The "
        "grid already puts every full-size arm of this method at 20.4%, so a 65/35 or an 80/20 "
        "core would be a search for the split that squeaks under 20% after the result was seen. "
        "The method lab design SS4 forbids exactly that -- never tune after seeing a result within "
        "a method -- and anything chosen that way would have to be a new variation method with its "
        "own pre-registration, not an amendment to this one. These three are fixed before the run "
        "and these three are all that will be run."
    ),
    candidates=(
        _a("SAT100", RESIDMOM, RAW20,
           "The residual-momentum satellite alone at full size: the diagnostic's best post-2009 arm, made real"),
        _a("SAT100-NOGATE", RESIDMOM, SAT_NOGATE,
           "The same book with the shared SPY 200-day gate off: what the gate costs and buys here"),
        _a("C50A-NOGATE", BLEND,
           BlendParams((BlendPart(TIMING, ALWAYS_SPY, Decimal("0.5")),
                        BlendPart(RESIDMOM, SAT_NOGATE, Decimal("0.5")))),
           "The recorded 50/50 always-held core with the gate off on both legs: nothing braking the book"),
    ),
)


METHOD = Method(
    id="M0030",
    name="Hold the market as the core and add momentum on top: an SPY core with a residual-momentum satellite",
    family="stock-core-satellite",
    source_kind="variation",
    source_ref="M0029's test look; P7a F9-SPY200M70-MOM30; M0007-N20-RAW as the satellite",
    parent_id="M0029",
    hypothesis=(
        "M0029's test look showed the 2016-2026 risk was lagging a few mega-cap leaders, not "
        "crashing. Holding SPY itself as the core owns those leaders by construction, and the "
        "residual-momentum satellite (M0007-N20-RAW, +15.0% a year on dev) adds the edge. On dev, "
        "with the SPY 200-day filter on both parts: 70% core + 30% satellite (C70T) should land "
        "near F9's +12% a year at a worst fall under 20% (F9 had 19.2% with a weaker satellite), "
        "and 50/50 (C50T) near +13% at a similar worst fall, both with a smoother ride than either "
        "part alone and so a luck score above 0.90. The always-on core (C50A, the satellite still "
        "filtered) is evidence for what the filter costs and buys: it should break the 20% limit "
        "in 2008 (SPY fell about 55%; half of that is about 27%)."
    ),
    expected_failure=(
        "A timed SPY core is F1's 200-day rule, whose dev record is a fraction of a point a year "
        "ahead of SPY with whipsaw exits; the satellite carries all of the edge, so the 70% core "
        "dilutes it to barely above SPY and the luck score falls short of 0.90. The 50/50 version "
        "inherits the momentum book's 1998 shock at half weight plus the core's whipsaws and lands "
        "near the 20% limit. C50A breaks the limit in 2008."
    ),
    candidates=(
        _v("C70T", _blend(TIMED_SPY, "0.7"), "70% SPY under its 200-day filter, 30% residual-momentum top 20"),
        _v("C50T", _blend(TIMED_SPY, "0.5"), "50% SPY under its 200-day filter, 50% residual-momentum top 20"),
        _v("C50A", _blend(ALWAYS_SPY, "0.5"),
           "50% SPY always held, 50% residual-momentum top 20 (still filtered): what the core's filter buys"),
    ),
    seen_keys=("concept:spy-core-momentum-satellite", "concept:core-satellite"),
    amendments=(AMENDMENT_2026_10_12,),
)

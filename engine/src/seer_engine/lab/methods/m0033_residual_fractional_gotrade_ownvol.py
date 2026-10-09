"""M0033 — The real-fee fractional residual book under an own-volatility brake.

Source: a variation of M0032 (its M0032-N20-RAW-FRAC-GT) with M0011's own-volatility overlay
(Barroso & Santa-Clara 2015), on ``monthly-hold-frac-gotrade`` and the owner's monthly top-up.
Idea: M0032 is the lab's first honest real-fee funded result and fails exactly one go-live
condition -- a 20.6% worst fall against a 20% limit. Scale every weight by
``min(1, target_vol / the target basket's own annualized volatility)`` and the fall comes down.
The only question worth a method is *how hard to brake*, because a brake costs return.

Reuses M0011's allocator object (``RESIDVOL``, allocator id "M0011") unchanged, so the config
digest differs from M0011's trials only in the trade rules -- whole shares at a flat 0.1% there,
fractional shares at Gotrade's measured fees here. Every piece reads only bars dated <= d.

Why five variants and not the one the idea row reserved
-------------------------------------------------------
The reserved idea said "M0011's RAW20-TV14 parameters verbatim, one variant". Reading M0011's
recorded trials before writing this file says that is the wrong single point, twice over, so the
idea is refined here and the id kept (assumption recorded, nobody asked):

1. **The 63-day window is not M0011's best; the 21-day one is, and it dominates.**
   M0011-RAW20-TV14 (n=63) made +9.3% a year at a 15.4% fall, MAR 0.60. M0011-RAW20-TV14-N21
   made +10.8% at a 14.1% fall, MAR 0.76 -- more return *and* a shallower fall from the same
   target. A faster volatility estimate reacts to a shock instead of averaging it away, which is
   what a brake is for. Pre-registering the dominated window as the sole variant would spend the
   method's one look on a configuration already known to be beaten by its own sibling.
2. **Every target M0011 tested over-brakes this book by roughly ten times what it needs.**
   M0032 must lose 0.6 points of fall (20.6% -> under 20%). M0011's TV14 took the unbraked book
   from 19.6% to 14.1-15.4%: it removes 4-5 points. On M0011's own measured exchange rate --
   about 0.76 points of yearly return per point of fall removed (15.0% -> 10.8% CAGR buying
   19.6% -> 14.1% DD) -- paying for 5 points of fall when 0.6 are wanted throws away roughly 3.5
   points of yearly return for nothing. The idea row's own arithmetic ("about half a point of
   yearly return") is right about the *rate* and wrong about the *quantity*: it priced 0.6 points
   of fall but then pre-registered a brake that buys 5.

   So the dial is spanned instead of guessed. M0011's recorded n=63 ladder -- TV12: 13.3% fall,
   TV14: 15.4%, TV16: 16.3%, unbraked: 19.6% -- extrapolates to roughly TV18 ~17.5% and
   TV20 ~18.5% on that book; the funded real-fee book runs about a point deeper, so the light
   end of the ladder is where the limit is crossed. The ladder below brackets it from both
   sides, and the two M0011 anchors keep the result comparable with the parent overlay.

All five are fixed here, before any result. The lab counts one look per method, so spanning the
dial costs no N; what it buys is the exchange rate measured at real fees instead of assumed.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0011_raw_residual_own_vol import RAW20, RESIDVOL, ResidVolParams
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE

ADDED = date(2026, 10, 9)


def _v(suffix: str, target_vol: str, n: int, rationale: str) -> Candidate:
    return Candidate(id=f"M0033-{suffix}", family="M0033", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=RESIDVOL, params=ResidVolParams(RAW20, Decimal(target_vol), n),
                     added=ADDED, owner_inputs=(), rationale=rationale)


METHOD = Method(
    id="M0033",
    name="The real-fee fractional residual book under an own-volatility brake",
    family="stock-residual-momentum",
    source_kind="variation",
    source_ref="M0032-N20-RAW-FRAC-GT + M0011's own-volatility overlay (Barroso & Santa-Clara "
               "2015), on monthly-hold-frac-gotrade, funded monthly",
    parent_id="M0032",
    hypothesis=(
        "M0032-N20-RAW-FRAC-GT is the lab's first honest real-fee funded result and fails exactly "
        "one go-live condition: a 20.6% worst fall, about six tenths of a point over the 20% "
        "limit, with its luck score (0.939 at N=29) and gains-to-losses (1.98) both clear and "
        "your money earning +13.7% a year against +7.2% for the same deposits put into SPY TR. "
        "This method buys that six tenths of a point down with the cheapest brake that will do "
        "it, rather than the brake its sibling happened to test. Scaling every weight by "
        "min(1, target_vol / the target basket's own annualized volatility) is the overlay M0011 "
        "already measured on this exact ranking, and it measured the price too: 15.0% -> 10.8% a "
        "year buying 19.6% -> 14.1% worst fall, about 0.76 points of yearly return per point of "
        "fall removed. At that rate the six tenths of a point actually needed costs under half a "
        "point of yearly return -- but only if the brake is set to remove six tenths, not five "
        "points. So the dial is spanned, light end first. I expect TV20-N21 to win: a 20% "
        "volatility target barely binds in a calm market and clamps hard in a crash, which is "
        "where the 20.6% fall was made, so it should land near a 18-19% fall while giving up "
        "well under a point of yearly return -- a money-weighted return around 12.8-13.3% a year "
        "against the same deposit-matched SPY's 7.2%, which would be the widest honest margin in "
        "the lab and the first configuration to break no go-live condition at real fees. TV22-N21 "
        "is the control from above: if it also lands under 20% then the brake barely had to "
        "engage at all and the fall was made on a handful of days. TV18-N21 is the first fallback "
        "if the light end misses. The two TV14 anchors are not expected to win; they are there so "
        "the result is comparable with M0011's recorded ladder, and N21 should beat N63 on both "
        "return and fall exactly as it did there. The brake also has to survive a fee schedule it "
        "never faced: rescaling weights every month places resize trades the unscaled book does "
        "not, so trades should rise above M0032's 1,607 and the fee drag with them, which is the "
        "one way a light brake can cost more than the arithmetic says."
    ),
    expected_failure=(
        "The brake does not bind where the fall was made, so the whole ladder either costs return "
        "without buying fall, or buys fall only by braking so hard that the return goes with it. "
        "M0032's worst fall is a funded-book fall, and the engine refuses to let deposits soften "
        "it, so it may well be a fast shock -- 1998, or the first weeks of 2008 -- that hit a book "
        "whose trailing volatility was still low going in. A min(1, target/realized) scale reads "
        "the past, so on a fall that arrives faster than the estimate the light targets sit at "
        "scale 1.0 and change nothing: TV22 and TV20 would come back at 20.5-20.6% with the "
        "return intact and nothing bought, and only TV14 would clear the limit, at the 3-4 points "
        "of yearly return the idea was written to avoid paying. That outcome is still worth the "
        "look, because it says the fall is a timing problem rather than a sizing problem and "
        "points at a drawdown brake on the book itself (M0009) instead. The second way it fails "
        "is the fee schedule: a 20-name book funded 5,000,000 IDR a month places small orders, "
        "and a brake that moves every weight a little every month turns 20 holds into 20 resizes, "
        "each paying a 0.10 USD floor on a slice that may be worth 30 dollars. If that lifts the "
        "trade count far above 1,607, the fee drag could take more yearly return than the brake "
        "saves in fall, leaving every variant worse than the unbraked parent on return per unit "
        "of fall."
    ),
    candidates=(
        _v("TV22-N21", "0.22", 21,
           "The lightest brake: binds only in a crash, the control from above"),
        _v("TV20-N21", "0.20", 21,
           "A 20% target on a one-month window: expected to just clear the 20% fall limit"),
        _v("TV18-N21", "0.18", 21,
           "One step harder, the first fallback if the light end misses"),
        _v("TV14-N21", "0.14", 21,
           "M0011's best variant (MAR 0.76) verbatim, at real fees in fractional shares"),
        _v("TV14-N63", "0.14", 63,
           "The idea row's reserved configuration: M0011-RAW20-TV14, the slow-window anchor"),
    ),
    seen_keys=("concept:residual-momentum-own-vol-fractional-gotrade",),
)

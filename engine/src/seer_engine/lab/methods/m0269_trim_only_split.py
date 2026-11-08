"""M0269 — Cap the winners, do not feed the laggards: which half of trimming buys the shallower fall?

Source: variation of M0266. Exposure-matched, M0266 found that trimming a wide book earns nothing
(-0.10 points a year at band 0, +0.02 at the 20%-of-target band), costs money in 2009-2015 on both
stores, and yet makes the worst fall SHALLOWER, which reverses M0127's claim that rebalancing
deepens the fall by buying the faller. Trimming is two actions welded together: SELLING a slice of
whatever outgrew its slot, and SPENDING the proceeds on whatever shrank below it. This method pulls
them apart on M0266's own chassis, with the one lever the engine lacked:
``TradeRules.resize_adds=False`` (2026-11-08, a ``LEVERS_SINCE_PINS`` no-op at True), under which a
held target below its band is left alone and the proceeds of a trim stay in cash.

Idea. Hypothesis: the safety comes from the selling, the 2009-2015 cost from the buying.

THE CALIBRATION CHANGED DIRECTION, AND WAS MEASURED BEFORE ANY RETURN WAS READ. The idea row asked
to calibrate the sell-only arms' scale UPWARD to the unbraked book's exposure. It cannot be: a
scale above 1 makes target weights sum past 1, which the engine refuses, and a sell-only arm sits
far BELOW the controls anyway (the expected failure, and it happened). Exposure only, read from a
scratch run of the same ``dev.run_registry`` on the dev store with no return printed:

  * sell-only at band 20% of target, scale 1: average exposure 0.5587  (controls 0.8865 / 0.9621)
  * sell-only at band 0, scale 1:             average exposure 0.5385  (control 0.9857)

So the CONTROLS are scaled DOWN to the sell-only arm's exposure instead, pair by pair. The scales
were found by bisection on exposure alone and each one verified by a further exposure-only run:

  * never-trim (loose band) at 0.6721 -> 0.5601 against 0.5587   (band-20 pair)
  * trim-and-feed band 20% at 0.580727 -> 0.5610 against 0.5587
  * never-trim (loose band) at 0.6515 -> 0.5385 against 0.5385   (band-0 pair)
  * trim-and-feed band 0 at 0.546332 -> 0.5393 against 0.5385

Every pair is inside the pre-registered half-point. Realised exposure is re-read from the recorded
trials and any pair that misses by more than half a point is not split. The 20%-of-target and
band-0 pairs are separate on purpose: they run at different exposures, so one never-trim control
cannot match both. THE SURVIVORSHIP-CHECK STORE WAS NOT CALIBRATED SEPARATELY: ``lab survivorship``
re-runs recorded variants at their recorded params, so its exposures will differ by store (insight
527) and its realised exposures are to be quoted beside any dev-versus-check difference, which is
then not an exposure-matched number.

Pure. The allocator is M0266's (id M0266), imported and not re-typed; it reads only bars dated <= d.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0127_slot_relative_resize_band import E1, T00, T20
from seer_engine.lab.methods.m0266_exposure_matched_rebalance import BOOK, ScaledBandParams
from seer_engine.sim.rules import TradeRules

ADDED = date(2026, 11, 8)

#: Sell-only twins of M0127's rungs: identical band, identical basis, identical cadence and fees.
#: The one difference is that a holding below its band is left alone.
SELL20: TradeRules = replace(T20, id="monthly-hold-frac-gotrade-tband20-sellonly", resize_adds=False)
SELL00: TradeRules = replace(T00, id="monthly-hold-frac-gotrade-tband00-sellonly", resize_adds=False)


def _v(suffix: str, rules: TradeRules, scale: str, rationale: str) -> Candidate:
    return Candidate(
        id=f"M0269-{suffix}",
        family="M0269",
        rules=rules,
        allocator=BOOK,
        params=ScaledBandParams(scale=Decimal(scale)),
        rationale=rationale,
        added=ADDED,
        owner_inputs=(),
    )


METHOD = Method(
    id="M0269",
    name="Cap the winners, do not feed the laggards: which half of trimming buys the shallower fall?",
    family="portfolio-rebalancing",
    source_kind="variation",
    source_ref=(
        "M0266, which found trimming worth nothing with exposure matched, negative in 2009-2015 on "
        "both stores, and a shallower worst fall on both; M0127's claim that rebalancing deepens "
        "the fall; M0119 (feeding the laggard cost 1.1 points a year); insight 527 (exposure "
        "matches are per store)"
    ),
    parent_id="M0266",
    hypothesis=(
        "M0266 measured, with exposure held fixed, that trimming a wide book is worth nothing "
        "(-0.10 pts/yr at band 0, +0.02 at the 20%-of-target band), is negative in 2009-2015 on "
        "both stores, and yet makes the worst fall shallower (-1.7 pts dev, -3.4 check). Trimming "
        "is two actions: SELLING what outgrew its slot and SPENDING the proceeds on what shrank "
        "below it. The hypothesis is that the safety comes entirely from the selling (an uncapped "
        "winner becomes a concentration the book never agreed to) and the 2009-2015 cost entirely "
        "from the buying (topping up a faller is a mean-reversion bet that has been wrong for the "
        "modern era). Six arms on M0266's chassis (M0109's unbraked 50 most-traded index members, "
        "equal weight, fractional shares, Gotrade's real fees, the owner's funding): two sell-only "
        "arms (new lever resize_adds=False) at band 20% of target and band 0, each at scale 1, and "
        "for each a never-trim control and a trim-and-feed arm scaled DOWN to the sell-only arm's "
        "measured exposure. The exposure calibration was done before any return was read (see the "
        "module docstring): sell-only runs 55.87% (band 20) and 53.85% (band 0) invested on dev "
        "against 88.6-98.6% for the full-weight controls, so scale could not be raised on the "
        "sell-only arms and the controls were lowered. PREDICTIONS. (1) Sell-only is not worse "
        "than never-trim at the same exposure in 2009-2015, and trim-and-feed is worse than both "
        "there. (2) The worst fall of sell-only is shallower than the never-trim control at the "
        "same exposure by 1.5 to 3 points; trim-and-feed's fall is between the two. (3) Whole-"
        "window money-weighted return of sell-only is within 0.3 points a year of never-trim. If "
        "(2) holds and (1) holds, the payoff is a dial worth building: cap winners, keep the "
        "proceeds. No arm is a candidate: all are low-exposure books that lose to SPY by "
        "construction, and none has a preset."
    ),
    expected_failure=(
        "Sell-only drifts into a very different cash share than the controls (it did: 54-56% "
        "invested), so the comparison lives at low exposure where trims are rare and tiny and "
        "every difference sits inside noise. A sell-only rule's cash share depends on how much the "
        "book has run, so cash is NOT a constant buffer and the paths differ even at equal "
        "averages (the controls' cash is a fixed fraction, sell-only's is ratcheted up by rallies "
        "and never released until a name drops out of the top 50). The shallower fall may then be "
        "the cash being there at the 2008 peak, not the selling. The survivorship-check store was "
        "not separately calibrated, so any check-store difference is not exposure-matched."
    ),
    candidates=(
        _v("NEVER20", E1, "0.6721",
           "Control for the band-20 pair: never trims, scaled down to the sell-only arm's exposure"),
        _v("FEED20", T20, "0.580727",
           "Trim-and-feed at the 20%-of-target band, scaled down to the sell-only arm's exposure"),
        _v("SELL20", SELL20, "1",
           "THE TREATMENT: trim winners at the 20%-of-target band, never top up a faller"),
        _v("NEVER00", E1, "0.6515",
           "Control for the band-0 pair: never trims, scaled down to the sell-only arm's exposure"),
        _v("FEED00", T00, "0.546332",
           "Full monthly trim-and-feed, scaled down to the sell-only arm's exposure"),
        _v("SELL00", SELL00, "1",
           "THE SECOND TREATMENT: trim every winner back to its slot every month, never top up"),
    ),
    seen_keys=(
        "concept:trim-only-sell-side-split",
        "concept:cap-winners-do-not-feed-laggards",
    ),
)

"""M0536 -- Price the coin-flip spread of the printed-price pool before reading any lead.

Parent: M0531. Reserved by Sera batch 20261110-1011 as an ``idea`` row; this file refines it and
keeps its id.

M0531 ran four blind draws matched to M0383-HIGH20 (the 20 dearest printed share prices behind
SPY's 200-day switch) and found them spread 6.8 points a year, wider than the lead HIGH20 claimed
over one draw. Four draws is too few to say where a lead sits in that spread. This method adds six
more draws from the same rule so the family is judged against ten coin flips, not four.

**Why the draws reuse M0531's allocator rather than a new one.** The question is "where does
HIGH20 rank among draws of one rule". Six draws under ``M0531-A1`` with fresh seeds (536-541) are
the same rule as M0531's four (seeds 531-534) and differ only in the seed, so the ten pool into
one reference distribution. A new allocator id would be a second rule and the pooling would be a
claim instead of a construction. New seeds mean new books, so no arm repeats a recorded curve.

**No treatment arm, on purpose.** HIGH20 is already recorded (M0383-HIGH20, and its twin
M0531-HIGH20); re-running it a third time buys nothing. M0383-ADJLOW20 is a look-ahead diagnostic
(it ranks on store-adjusted closes, which know future splits) and is never a strategy; the
coordinator flagged that it reads promotable at 4 of 4 folds, so its rank among the same ten
draws is reported too, but only as the price of the look-ahead, never as a lead.

Fractional shares at Gotrade's real fees (``MONTHLY_HOLD_FRAC_GOTRADE``), as every arm of M0383
and M0531 ran.
"""

from __future__ import annotations

from datetime import date

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0531_dearest_price_disproof import BLIND, SW, DearParams
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE

ADDED = date(2026, 11, 10)

SEEDS = (536, 537, 538, 539, 540, 541)


def _blind(n: int, seed: int) -> Candidate:
    return Candidate(
        id=f"M0536-BLIND-{n:02d}", family="M0536", rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=BLIND,
        params=DearParams(top=20, side="random", seed=seed, trend=SW),
        rationale=(f"Control: hash-drawn placebo {n} (seed {seed}) under M0531's blind-draw rule -- "
                   "M0383's screened pool, HIGH20's own size, entry count and churn, none of its "
                   "names, behind the same switch."),
        added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0536",
    name="Price the coin-flip spread of the printed-price pool: six more blind draws, ten in all",
    family="stock-nominal-price-level",
    source_kind="variation",
    source_ref="parent M0531 (four blind draws matched to M0383-HIGH20); M0383",
    parent_id="M0531",
    hypothesis=(
        "M0531's four blind draws matched to M0383-HIGH20 spread 6.8 points a year (funded), wider "
        "than the lead HIGH20 claimed over one draw (recorded figures, re-read before quoting). "
        "This method runs six more draws under the identical rule (M0531's blind-draw allocator, "
        "seeds 536-541, M0383's screened pool, HIGH20's size, entry count and churn, behind SPY's "
        "200-day switch, fractional shares at Gotrade's real fees) and pools them with M0531's four "
        "into ten. Every arm is a control: no arm here is a strategy and none may be promoted. "
        "Readout, fixed now: rank M0383-HIGH20's recorded funded CAGR among the ten draws (11 "
        "books). Keep the printed-price family only if HIGH20 ranks 1st or 2nd of 11 (top "
        "quarter); 3rd or lower retires it. Also report HIGH20's lead over the ten-draw mean in "
        "units of the draws' standard deviation, its max-drawdown rank, and its 2009-2015 rank. "
        "M0383-ADJLOW20 (look-ahead diagnostic) is ranked among the same ten only to price what the "
        "look-ahead buys; whatever its rank, it is not a strategy. Prediction: HIGH20 lands 3rd-5th "
        "of 11 -- inside the spread -- and the family retires."
    ),
    expected_failure=(
        "HIGH20 sits mid-pack among the ten draws (the prediction). The draws themselves may beat "
        "SPY on average, which says the pool and the switch, not the price rank, carry the return. "
        "Pooling assumes the six new seeds are exchangeable with M0531's four; if their mean "
        "differs from the four's by more than the spread, say so and judge on the six alone."
    ),
    candidates=tuple(_blind(i + 1, s) for i, s in enumerate(SEEDS)),
    seen_keys=(
        "concept:nominal-price-level-draw-spread",
        "concept:dearest-price-vs-ten-blind-draws",
    ),
)

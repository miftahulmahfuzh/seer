"""M0382 — Push the discount dial lower on M0377's rescaled book, beside an undiluted control.

Source: a variation of M0377, the next move its own closing opinion queued.

M0377 handed the weight a discounted name gives up to the book's other held names, so the
discount no longer costs idle cash. Its half-weight arm cleared the luck bar on dev (DSR 0.912),
read clean on resemblance and won every fold, then failed its one test-window look. That makes
every descendant kin of a test-failed method: this run cannot be promoted through the hard gate.
It is dev-window evidence about the weight dial only, and is journalled as such.

What is new: the dial goes lower than M0377 or M0374 ever took it, and the book is also run with
no dial at all.

* ``RESCALE20-W10-G40-UP63`` — momentum's top 20 at a tenth of a normal slot, freed weight
  rescaled into the other held names.
* ``RESCALE20-W05-G40-UP63`` — momentum's top 20 at a twentieth of a slot, the freed weight
  rescaled into the rest: the far end of the dial, short of M0160's full bar with exposure
  restored. A full drop (0.0) is not registered: it zeroes every held name on the contract test's
  small fixture, so the allocator contract cannot be proved for it.
* ``RESCALE20-W100-G40-UP63`` — the control with no opinion in it: the same book, the same gate,
  the same fees, the dial untouched (down_weight 1.0 makes ``downweight`` and ``rescale_freed``
  no-ops). Any difference between it and the two arms above is the price or the worth of the
  discount itself, with the cost of trading the book cancelling. M0377 never ran this arm, so its
  headline's gain over the plain book was never priced.

The half and quarter weights are not re-registered: M0377 already holds those exact
configurations, so they read against its recorded trials.

Assumptions, written before the run: screen, rank, gate and the discount are M0374's and M0377's
own code, imported unchanged. Reads only bars dated <= ``data_date``. Pure.
"""

from __future__ import annotations

from datetime import date

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0133_gated_updown_asymmetry import N40, AsymParams
from seer_engine.lab.methods.m0374_softened_exclusion_downweight import SoftExclParams
from seer_engine.lab.methods.m0377_rescaled_soft_exclusion import RescaledSoftExclusionAllocator
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE

ADDED = date(2026, 11, 3)


class DeeperDiscountAllocator(RescaledSoftExclusionAllocator):
    """M0377's allocator under its own id; the logic is inherited whole."""

    id = "M0382"


DEEPER = DeeperDiscountAllocator()


def _v(suffix: str, dw: float, rationale: str) -> Candidate:
    params = SoftExclParams(AsymParams(N40, gate="sma200-up63"), momentum_top_n=20, down_weight=dw)
    return Candidate(id=f"M0382-{suffix}", family="M0382", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=DEEPER, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0382",
    name="Push the discount dial lower now that exposure is no longer its cost",
    family="stock-updown-asymmetry",
    source_kind="variation",
    source_ref="variation of M0377 (rescaled soft exclusion); the next move its own closing opinion queued",
    parent_id="M0377",
    hypothesis=(
        "M0377 removed the idle-cash cost of discounting momentum's favourite names by giving the "
        "freed weight to the rest of the book. M0374 had shown that the lighter the discount, the "
        "further the book's monthly pattern moved from the failed momentum book. With exposure now "
        "restored, a tenth (W10) or a twentieth (W05) of a normal slot should push the resemblance "
        "reading further under the 0.85 limit without losing the fold majority or a DSR of 0.90 "
        "that M0377's half-weight arm earned. A third arm leaves the dial untouched (W100): the "
        "same book with no opinion on momentum, so the worth of the discount is read against the "
        "book's own trading cost instead of against a different method. Success: W10 or W05 keeps "
        "DSR >= 0.90, a fold majority, and beats W100 by a margin larger than the arms' draw "
        "noise, with a lower resemblance reading than M0377's. This idea rests on a momentum "
        "anomaly published long before 2015, so any dev edge is expected to have faded since."
    ),
    expected_failure=(
        "The likeliest failure is that the discount was never doing work: W100 matches or beats W10 "
        "and W05, so M0377's dev win was the book itself and the dial a coat of paint. Second, "
        "rescaling pours the freed weight into names that are still momentum-adjacent, so the "
        "resemblance reading barely moves with a deeper dial. Third, as the dial approaches zero "
        "the book concentrates in fewer names and its worst fall deepens past the screen. Fourth, "
        "the parent failed out of sample, so even a clean dev result cannot be promoted: the "
        "hard gate refuses kin of a test-failed method."
    ),
    candidates=(
        _v("RESCALE20-W10-G40-UP63", 0.1,
           "Momentum's top 20 at a tenth of a slot, rescaled: the deeper discount"),
        _v("RESCALE20-W05-G40-UP63", 0.05,
           "Momentum's top 20 at a twentieth of a slot, rescaled: the far end of the dial"),
        _v("RESCALE20-W100-G40-UP63", 1.0,
           "Dial untouched: the always-invested control with no opinion on momentum"),
    ),
    seen_keys=(
        "concept:deeper-discount-on-rescaled-downweighted-book",
    ),
)

"""M0315 — Does the coin get wider as the book gets narrower?

Source: variation of M0307 (the coin's width behind the switch).

**The gap M0307 opened and could not close.** M0307 measured the lab's only gated error bar on a
twenty-name, three-industry blind draw: seven identical, opinion-free books, same seeds, same
switch, differing in nothing but a hash, spanning funded CAGR 32.0%-33.9% and max drawdown
20.8%-36.4% (recorded trials #1039-#1044 plus the seed-1 arm M0295-MATCHED-T3). That bar is quoted
lab-wide to judge whether an idea's lead over its control is bigger than luck. But every book it was
measured on holds twenty names. The lab also has methods that hold ten (M0288's liveness-filtered
screens), forty (the wider stock-picking books M0139 already priced on *return*), and everything in
between — and a coin's width is not a property of the rule alone. Each pick in a ten-name book is
10% of the result; in a forty-name book it is 2.5%. A book that holds fewer names must scatter more
under the same hash, because a bad single draw cannot be diluted by as many neighbours. Applying
M0307's twenty-name bar to a ten-name method understates the noise it should be judged against, and
applying it to a forty-name method overstates it — in both directions the lab would read a real
signal as inside the coin, or a coin as a signal, for a reason that has nothing to do with the idea
being judged.

**What M0139 already settled, and what it left open.** M0139 priced what book width does to
*return*: holding seventy names instead of twenty gave up 2.8 points a year, because the book
dilutes its best ideas into its worst ones. That is the opinion's cost. What width does to *noise* —
the spread an OPINION-FREE book shows from nothing but which names a coin happened to pick — has
never been measured. This method measures it, on the identical engine, switch and seeds M0307 used,
varying only the book's width.

**The one dial, on the one chassis that already has a gated width.** M0295's ``LeadLagParams``
wraps a ``FactorParams`` (``inner``) whose ``top`` field is literally the number of equal slots the
book splits over its three chosen industries (``allot(inner.top, industries)``: 20 over 3 is
[7, 7, 6]; the slot weight is ``equal_weight(inner.top)``). Holding ``industries=3``,
``side="matched"``, ``leader="largest"`` and the switch fixed at M0295's own ``GATED`` trend rule,
and changing only ``inner.top``, leaves the chosen three industries **identical for a given seed**
across every width — ``side="matched"`` draws industries by blake2b(seed | industry | month), which
does not read ``top`` at all — so the only thing that differs between a width-10, width-20 and
width-40 draw on the same seed is how many of each industry's hash-ordered followers are bought.
This is the cleanest width dial the lab owns: no new allocator, no new screen, a single field swept
through three values on a chassis the lab has already run at one of them.

**Why ten and forty, not twenty again.** Twenty is already fully measured: M0295-MATCHED-T3 (seed
1) plus M0307-GDRAW-S2..S7 are six already-recorded gated draws at ``top=20``, and re-registering
them would run a recorded configuration a second time, which ``config_digest`` refuses regardless
of the id it is given. So this method spends its arms on the two widths the lab does not have:
``top=10`` (half as wide) and ``top=40`` (twice as wide), each run on the identical six seeds
M0307 used (2-7), so every width's population pairs hash-for-hash with the recorded width-20
population and with each other. ``MAX_VARIANTS`` caps one batch at six, so the twelve new arms are
one batch of six (``top=10``) plus one amendment of six (``top=40``), both written and committed in
this same file before either runs — the amendment is not a reaction to a result, it is the second
half of one pre-registered sweep that the file-format cap forces into two batches.

**What three points buy that two cannot.** A line drawn through two widths (ten and twenty, say)
could be straight, could bend, and this lab has been burned before reading a slope off two points.
Three widths — ten, the already-recorded twenty, and forty — let the analysis check whether the
spread's width scales the way a dilution argument predicts (roughly like 1/sqrt(width), if the
picks behaved like independent draws) or does something else entirely, which a single comparison
cannot distinguish from noise in the comparison itself.

**Known confound, stated before the run.** At ``top=40`` each of the three chosen industries must
fill up to 14 slots from its own hash-ordered followers (``allot(40, 3) = [14, 13, 13]``), and
``MIN_MEMBERS = 5`` only guarantees an industry has five pool members, not fourteen. An industry
that runs out of followers leaves its unfilled slots in SPY (M0295's own fallback for every width),
which means a wide book's measured spread is partly "how often an industry ran dry" rather than
purely "how many independent names diluted the result" — a book that is forced wide ends up holding
more SPY, not more diversification, which could narrow the spread for a reason unrelated to the
width being tested. The analysis must check each arm's SPY fill fraction before reading the
top=40 spread as pure dilution.

Rules are ``monthly-hold-frac-gotrade``: fractional shares at Gotrade's real fees on the owner's
monthly deposits, identical to every arm this is read against. Pure: the engine is M0295's, which
reads only bars dated at or before d and has no clock, randomness, file or network of its own. The
seed enters only through a fixed blake2b of the seed, the industry name and the decision's month.

Assumptions, written before the run:
  * a seed is an arbitrary label, so the same six seeds (2-7) are as fair a sample of "a gated blind
    draw" at width 10 and width 40 as they already are at width 20 — the same assumption M0296 and
    M0307 wrote down and the same hash that justifies it;
  * ``industries=3`` is held fixed because the idea row asks for width alone; a book that also
    widened its industry count would be testing two dials in one method and could not attribute
    a scaling result to either one cleanly;
  * the switch stays ``GATED`` throughout, matching M0307 rather than M0296, because the lab
    clusters by its gate (M0307's own finding) and the bar this method extends is the gated one the
    lab actually audits against, not the ungated one M0296 produced.
"""

from __future__ import annotations

from datetime import date

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Amendment, Method
from seer_engine.lab.methods.m0295_industry_bellwether_lead_lag import (
    LEADLAG,
    TREND,
    LeadLagParams,
)
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.f_factor import FactorParams

ADDED = date(2026, 10, 23)

#: Mirrors M0307's own seed choice: 1 is absent on purpose everywhere, because the gated seed-1
#: draw at width 20 is already recorded (M0295-MATCHED-T3) and a width-10/-40 book run on the same
#: seed-1 hash would not change that fact — only widths 10 and 40 need registering, and only on
#: the six seeds that already have a width-20 twin.
SEEDS = (2, 3, 4, 5, 6, 7)

#: top=20's gated FactorParams is M0295's own GATED object, already fully drawn (6 seeds here,
#: 1 more recorded as M0295-MATCHED-T3). These are the two widths that are not yet measured.
WIDTH_10 = FactorParams(rank="momentum", top=10, mom_n=252, mom_skip=21, trend=TREND)
WIDTH_40 = FactorParams(rank="momentum", top=40, mom_n=252, mom_skip=21, trend=TREND)


def _draw(width_label: str, inner: FactorParams, seed: int) -> Candidate:
    return Candidate(
        id=f"M0315-W{width_label}-S{seed}",
        family="M0315",
        rules=MONTHLY_HOLD_FRAC_GOTRADE,
        allocator=LEADLAG,
        params=LeadLagParams(inner=inner, industries=3, side="matched", leader="largest",
                             seed=seed),
        rationale=(
            f"gated blind draw {seed}, book width {width_label}: the identical three industries "
            f"M0307's seed-{seed} draw chose (side=matched hashes on seed, industry and month, "
            f"never on width), split over {width_label} equal slots instead of 20 — the twin of "
            f"the recorded width-20 draw on seed {seed}, differing from it in the slot count "
            "alone and from its same-width siblings in the seed alone"
        ),
        added=ADDED,
        owner_inputs=(),
    )


_HYP = (
    "A blind draw's spread scales with how few names it holds, because each pick is a larger share "
    "of a narrower book: M0307 measured the gated coin at width 20 and found funded CAGR spanning "
    "32.0%-33.9% and max drawdown 20.8%-36.4% across six seeds plus the recorded seed-1 arm. If "
    "noise scales the way diluting independent picks predicts, the same six seeds at width 10 "
    "should span MORE than that on both axes and at width 40 should span LESS, with the ordering "
    "10 > 20 > 40 holding on both return and drawdown and not just on one. Success is that ordering, "
    "stated as a usable scaling factor (for instance, how many points of spread one more halving or "
    "doubling of width buys or costs) that the audit M0307 queued can apply to a method of any "
    "width instead of assuming every book scatters like a twenty-name one. No arm here is trying to "
    "beat SPY and none is expected to be dev-eligible; the deliverable is the scaling rule, not a "
    "candidate."
)

_EXP = (
    "The likeliest failure is the one flagged above: at width 40 each industry must fill up to 14 "
    "slots from hash-ordered followers that ``MIN_MEMBERS=5`` never guaranteed exist, so unfilled "
    "slots fall to SPY and the width-40 arms end up partly invested in the market itself rather "
    "than in fourteen independent picks per industry. If that happens the width-40 spread will "
    "narrow for the wrong reason — forced SPY exposure smoothing the result, not forty names "
    "diluting it — and the scaling read will overstate how much a genuinely wide, fully-filled book "
    "would narrow. The second failure is that the switch dominates again exactly as M0307 found "
    "for the width/switch dial: the SPY 200-day gate may compress every width's drawdown toward the "
    "same floor (time in cash in 2008 regardless of how many names are held), so the drawdown axis "
    "shows no width ordering at all while the return axis does — a bar that scales on one axis and "
    "not the other, which is harder to use than a single scaling factor. The third is that six "
    "seeds per width is still too few: M0307 itself warned that seven gated draws can be dominated "
    "by whichever single seed sits furthest out, and that risk applies at each of three widths "
    "independently, so a non-monotonic reading (20 wider than 10, say) may be seed-count noise "
    "rather than evidence against dilution. If any of the three lands, the fallback is to report "
    "the scaling as a loose direction and a known lower/upper bound rather than a precise factor, "
    "and to flag M0307's audit as still needing the ungated chassis swept the same way before any "
    "number here is applied to an ungated method."
)

AMEND_WHY = (
    "The second width of the same pre-registered sweep. MAX_VARIANTS caps one batch at six "
    "candidates, so the twelve width-10-and-width-40 arms this method needs do not fit in one "
    "block; this amendment is written and committed in the same file, before the width-10 batch "
    "has run, and is not a reaction to any result — it is the other half of 'turn the dial three "
    "times' that the file format forces into two run commands (`lab run M0315` then "
    "`lab run M0315 --amend`)."
)

AMEND_1 = Amendment(
    added=ADDED,
    why=AMEND_WHY,
    hypothesis=_HYP,
    expected_failure=_EXP,
    candidates=tuple(_draw("40", WIDTH_40, s) for s in SEEDS),
)


METHOD = Method(
    id="M0315",
    name="Does the coin get wider as the book gets narrower",
    family="market-shape-yardstick",
    source_kind="variation",
    source_ref="M0307",
    parent_id="M0307",
    hypothesis=_HYP,
    expected_failure=_EXP,
    candidates=tuple(_draw("10", WIDTH_10, s) for s in SEEDS),
    amendments=(AMEND_1,),
    seen_keys=(
        "concept:draw-spread-scales-with-book-width",
        "concept:gated-coin-width-by-slot-count",
        "concept:width-forty-forces-spy-fill",
    ),
)

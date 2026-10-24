"""M0333 — Does smallest-first size ranking keep its lead over random books once SPY's 200-day
switch caps the fall?

Source: variation of M0323 (direct size ranking on M0318's chassis, no switch). Small-firm size
premium: Banz 1981 (JFE 9(1)) and Fama & French 1992 (JF 47(2)); published long before the dev
window ends, so a strong dev reading is expected to be the faded kind.

Idea. M0323's smallest-first book beat its three random books on both price sets and led SPY in
2009-2015, but fell 71.9% with no cash rule. Here the same chassis (20 equal slots, yield-fit
pool, 40% keep band, quarterly re-rank, SPY in leftover slots) sits behind SPY's 200-day average
switch (all cash when SPY closes at or under it). M0323's own switch-off arms are the other half
of the 2x2: the same configurations cannot be re-run (a configuration runs once per window), so
the switch-off cells are read from M0323's recorded trials on the same store, and the analysis
says so. Arms (six, the lab's cap): SMALL, BIG (mirror), R1-R3 (hash-ranked, new seeds) and HOST
(the untouched yield-ranked book behind the switch: the no-size-opinion arm that prices the
habit of the chassis). The 2x2 then reads size opinion (SMALL against R1-R3) and time-in-cash
habit (switch on against M0323's switch off) separately.

Reuses M0323's allocator unchanged; only the host's ``trend`` differs, so no new logic.
Rules are ``monthly-hold-frac-gotrade``: twenty slots of fractional shares at real fees.
"""

from __future__ import annotations

from datetime import date

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0293_calm_filter_on_a_host import HOST
from seer_engine.lab.methods.m0318_size_filter_dose import SIZEFILTER, SizeFilterParams
from seer_engine.lab.methods.m0323_rank_by_size import SIZERANK, SizeRankParams
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE

ADDED = date(2026, 10, 24)


def _v(suffix: str, side: str, seed: int, rationale: str) -> Candidate:
    return Candidate(id=f"M0333-{suffix}", family="M0333", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=SIZERANK, params=SizeRankParams(HOST, side=side, seed=seed),
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0333",
    name=("Does smallest-first size ranking keep its lead over random books once SPY's 200-day "
          "switch caps the fall?"),
    family="stock-size-tilt",
    source_kind="variation",
    source_ref=("variation of M0323 (direct size ranking, no switch); small-firm size premium, "
                "Banz 1981 JFE 9(1), Fama & French 1992 JF 47(2)"),
    parent_id="M0323",
    hypothesis=(
        "M0323's smallest-first book beat all three random books on both price sets and led SPY "
        "in 2009-2015, but fell 71.9% with no cash rule. Put the same ranking behind SPY's "
        "200-day average switch and price the size opinion and the time-in-cash habit separately "
        "(2x2: size or random order, switch on or off). The switch-off cells are M0323's recorded "
        "trials on the same store, because a configuration cannot be re-run. Arms: SMALL "
        "(smallest first), BIG (the mirror, same costs and chassis, opposite opinion), R1-R3 "
        "(hash-ranked draws, seeds 333-335), HOST (the untouched yield-ranked book behind the "
        "switch: no size opinion, prices the chassis). The size premium was published in 1981 "
        "and 1992, so a dev edge is expected to be the pre-crowd kind. Predictions, written now: "
        "SMALL's worst fall drops under 50% (the pass line from the parent's own opinion); SMALL "
        "still beats the best of R1-R3 on funded CAGR, but by under the 7.5-point chance "
        "spread; SMALL's lead over BIG shrinks against M0323's switch-off gap because the "
        "switch removes the 2008 crash where small names fell hardest; SMALL still leads SPY in "
        "2009-2015 on the regular prices, and on the survivorship-check store its lead over the "
        "best random draw is smaller than on the regular prices. Names with no market value "
        "rank last in every ranked arm."
    ),
    expected_failure=(
        "The likeliest failure is that the switch fixes the fall but costs the return: time in "
        "cash through a rising 2009-2015 decade gave up about 3.6 points a year on a 30-name "
        "switch book (insight 462), so SMALL behind the switch trails SPY there even if size "
        "still beats random order. Second, the fall may stay over 50% because a small-cap "
        "crash is faster than a 200-day average reacts, and ten-year dev has two real crashes. "
        "Third, the edge over random draws may shrink inside the 7.5-point spread once cash "
        "hides the years that carried it (M0267: the trend rule's edge was earned in 2000-2002). "
        "Fourth, survivorship: dead small companies are missing from the dev store. Fifth, a "
        "published anomaly that fades from 2018. Three hash draws are a thin spread; claims "
        "leaning on its width are weak."
    ),
    candidates=(
        _v("SMALL", "small", 0, "Rank the pool smallest market value first behind SPY's "
                                "200-day switch: the idea"),
        _v("BIG", "big", 0, "Rank biggest first behind the same switch: the mirror"),
        _v("R1", "blind", 333, "Control: hash-ranked pool, seed 333, behind the same switch"),
        _v("R2", "blind", 334, "Control: hash-ranked pool, seed 334"),
        _v("R3", "blind", 335, "Control: hash-ranked pool, seed 335"),
        Candidate(id="M0333-HOST", family="M0333", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                  allocator=SIZEFILTER, params=SizeFilterParams(HOST),
                  rationale="No-size-opinion control: the untouched yield-ranked book behind "
                            "the same switch, prices the chassis plus the switch",
                  added=ADDED, owner_inputs=()),
    ),
    seen_keys=(
        "concept:size-rank-behind-200-day-switch-2x2",
    ),
)

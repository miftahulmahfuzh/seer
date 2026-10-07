"""M0029 — The momentum plus calm-stock blend in fractional shares, so every pick is actually bought.

Source: a variation of M0021 (its pre-registered B70-RAW, unchanged except for the share rule).
Idea: M0021-B70-RAW failed its one test-window look at +3.3% a year vs SPY's +13.6%, with only 18%
of the money invested. The lab starts a book at 20,000,000 IDR (about $1,450 in October 2015), so
each of its 40 slots was $22-51, and in whole shares most index stocks cost more than that at
2016-2026 prices; those picks were skipped and their money sat in cash. Gotrade takes fractional
limit buys and sells (owner, 2026-10-07) and the paper roster trades its lab winners that way, so
the configuration that would actually trade is the same blend on ``monthly-hold-frac``.

One variant only, chosen before any result: the B70-RAW split M0021 pre-registered. No other dial
moves, so this adds a single trial to N. Every piece reads only bars dated <= d.
"""

from __future__ import annotations

from datetime import date

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0021_momentum_lowvol_blend import _blend
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC
from seer_engine.strategies.allocator import BLEND

ADDED = date(2026, 10, 7)

METHOD = Method(
    id="M0029",
    name="The momentum plus calm-stock blend in fractional shares, so every pick is actually bought",
    family="stock-multi-factor-blend",
    source_kind="variation",
    source_ref="M0021-B70-RAW on monthly-hold-frac; M0021's test-window look (whole-share fill)",
    parent_id="M0021",
    hypothesis=(
        "M0021-B70-RAW (70% residual-momentum top 20, 30% calmest 20, monthly, SPY 200-day filter) "
        "failed its test look with only 18% of the money invested: at a 20M IDR start, whole shares "
        "could not fill most $22-51 slots at 2016-2026 prices. On the dev window, back-adjusted "
        "prices let almost every slot fill, so the fractional twin should land within a few tenths "
        "of a point of M0021-B70-RAW (+12.6% a year, 14.0% worst fall, DSR 0.945 at N=113) and stay "
        "eligible. Its value is on the test window, where it should be invested about as much as on "
        "dev (~60%) and so measure the picks, not the account size."
    ),
    expected_failure=(
        "On dev, fractional shares change little, so the run mainly pins the configuration. On the "
        "test window, even fully invested, 2016-2026 was a mega-cap growth decade: a calm-stock "
        "sleeve and a 200-day filter that sits out sharp dips (2018, 2020, 2022) can lag SPY's "
        "+13.6% a year."
    ),
    candidates=(
        Candidate(id="M0029-B70-RAW-FRAC", family="M0029", rules=MONTHLY_HOLD_FRAC, allocator=BLEND,
                  params=_blend("0.7", braked=False), added=ADDED, owner_inputs=(),
                  rationale="M0021-B70-RAW verbatim, in fractional shares"),
    ),
    seen_keys=("concept:momentum-lowvol-blend-fractional",),
)

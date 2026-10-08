"""M0032 — Raw residual momentum the way the owner really trades it.

Source: a variation of M0007 (its pre-registered N20-RAW), unchanged except for the share rule,
the fee schedule and the funding.
Idea: M0007-N20-RAW is the lab's best dev book by return per unit of fall (MAR 0.77: +15.0% a
year at a 19.6% worst fall), but it was measured on three assumptions the owner does not live
under. It bought whole shares, so at a 20,000,000 IDR book each of its twenty slots was worth
$22-73 and most index names cost more than that -- the pick was skipped and its money sat in
cash, which is exactly what cost M0021 its test-window look. It paid the lab's flat 0.1% a
trade, where Gotrade's measured schedule is a trading fee with a $0.10 minimum, a regulatory fee
and 11% VAT on both (``sim/costs.py``, fitted to the owner's receipts). And it was judged on one
lump sum that never grew, where the owner adds 5,000,000 IDR on the 25th of every month.

``lab costs M0007 --candidate M0007-N20-RAW`` already separated the fee half: at Gotrade's real
fees the same variant made +12.8% a year against SPY TR's +7.9% with a 19.3% worst fall and
gains-to-losses of 2.04, with fees taking 15.6% of gross trade profit instead of 5.6%, and broke
no go-live condition the flat run cleared. That is a report, not a trial: this method is the
pre-registration that lets the real-fee configuration actually be judged.

One variant only, chosen before any result: M0007's N20-RAW parameters verbatim on
``monthly-hold-frac-gotrade``. No other dial moves, so this adds a single trial and isolates the
realism -- any difference from the cost report's Gotrade column is the fractional fills and the
funding, nothing else. Every piece reads only bars dated <= d.
"""

from __future__ import annotations

from datetime import date

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20, RESIDMOM, ResidParams
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE

ADDED = date(2026, 10, 8)

METHOD = Method(
    id="M0032",
    name="Raw residual momentum in fractional shares at Gotrade's real fees, on the monthly top-up",
    family="stock-residual-momentum",
    source_kind="variation",
    source_ref="redo-sera-experiments: M0007-N20-RAW on monthly-hold-frac-gotrade, funded monthly",
    parent_id="M0007",
    hypothesis=(
        "Runs M0007-N20-RAW's configuration verbatim -- top-20 raw cumulative residual momentum, "
        "F4's screen, SPY-200 trend gate, equal weights, monthly -- with three pieces of realism "
        "switched on at once: fractional shares, so each of the twenty slots is actually bought "
        "instead of being skipped and left in cash at a 20M IDR book; Gotrade's measured fee "
        "schedule (cost_model='gotrade'), fitted to the owner's own order receipts, instead of the "
        "lab's flat 0.1% a trade; and the owner's real funding plan, 5,000,000 IDR arriving on the "
        "25th of every month on top of the opening book, judged against a SPY TR fed the identical "
        "dollars on the identical days. The fee half alone was already measured by the cost report "
        "on M0007-N20-RAW: +12.8% a year against SPY's +7.9%, worst fall 19.3%, gains-to-losses "
        "2.04, 1,579 trades, fees eating 15.6% of gross trade profit against 5.6% at the flat rate, "
        "and no go-live condition broken that the flat run cleared. I expect the fee cost to "
        "survive and the ranking edge with it: the money-weighted return should still beat a SPY "
        "fed the same deposits, because this book turns over about 1,580 times in twenty years -- "
        "some 80 trades a year -- which is slow enough that a fee schedule with a 0.10 USD minimum "
        "cannot eat a 4.9-point annual margin. Fractional fills should change the dev window almost "
        "nothing, because back-adjusted 1996-2015 prices are small against a book that grows, but "
        "they should remove the cash drag that cost M0021 its test look. What I do NOT expect to "
        "survive unchanged is the worst fall or the luck score: monthly deposits keep topping the "
        "account up, so the fall will read shallower than it was, and the luck score is computed "
        "from daily account changes in which every deposit day looks like an enormous up day, so I "
        "expect it to flatter the method and will not read it as comparable to the parent's."
    ),
    expected_failure=(
        "The money-weighted return comes in at or below the deposit-matched SPY even though the "
        "lump-sum version beat it. The deposits arrive evenly across 1996-2015, so most of the "
        "money is only invested for the back half of the window, and this book is about 62% "
        "invested with a trend gate that sits in cash through 2000-02 and 2008-09 -- precisely the "
        "years a monthly buyer's new money buys cheapest. A money-weighted return rewards being "
        "invested when the money arrives, so the gate that earns the method its shallow fall may "
        "hand the deposit-matched comparison to SPY. The second way it fails is the fee minimum: "
        "a 20-name book funded 5M IDR a month places small orders early on, and a 0.10 USD floor "
        "on a $20 slice is half a percent a side, which would show up as a fee drag well above the "
        "cost report's 15.6% and a MAR below the 0.66 it measured."
    ),
    candidates=(
        Candidate(id="M0032-N20-RAW-FRAC-GT", family="M0032", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                  allocator=RESIDMOM, params=ResidParams(N20, scaled=False), added=ADDED,
                  owner_inputs=(),
                  rationale="M0007-N20-RAW verbatim, in fractional shares at Gotrade's real fees"),
    ),
    seen_keys=("concept:residual-momentum-fractional-gotrade",),
)

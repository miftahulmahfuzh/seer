"""M0164 — A small high-yield partner beside a large SPY core: 70% SPY, 30% the yearly banded yield book.

Source: variation of M0163 (Novy-Marx & Velikov 2016, value survives costs when traded slowly; Fama &
French 1993, dividend yield as value), reserved by Sera batch 20261113-0953; the core-satellite frame
of M0030 and M0104.
Idea: M0163's yield book beat SPY on the owner's deposits (+9.0% vs +7.2%, recorded trial 512) but
fell 62% in 2008 and lost all of 2009-2014, and its own advice was to hold one small yield book
beside a large SPY core. Held at 30%, it keeps SPY's big-company drift for 70% of the money and
lends only a third of the yield book's fall.

No new allocator: ``BLEND`` of the index ``TIMING`` allocator holding SPY at all times and M0163's
``YIELD`` allocator on M0163's recorded Y20-B40 params (and its switched twin), each on its fixed
share. The yield sleeve parks unfilled slots in SPY, as in M0163. Every arm is fractional at
Gotrade's real fees on the owner's deposits.

Assumptions, written before the run:
- The idea asks to rebalance to 70/30 only when the split drifts past 60/40 or 80/20. The book
  engine has no account-split band (its bands are per holding), so the drift rule is approximated
  two ways: C70-YB rebalances on the preset's 1%-of-account band (close to a monthly rebalance, as
  M0104 did), and C70-YB-TBAND on the 20%-of-own-target band, which leaves a position alone until it
  is a fifth off its slot. Neither is the exact 60/40-80/20 rule; the pair brackets it.
- Controls are cited, not re-run: the sleeve alone is M0163-Y20-B40 (recorded trial 512, its
  switched twin 513); SPY is the lab's benchmark on the same deposits and fees in every run; the
  80/20 core-satellite comparator is M0104-C80-UP (trial 522).
- The 2006-2008 fold: the yearly book's own walk-forward number is read from M0163's fold record in
  the analysis, not assumed (the M0163 analysis carries a correction about which pick that fold used).

Pure: every piece reads only bars dated <= d; no clock, randomness or I/O.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0163_banded_dividend_yield import YIELD, YieldParams, _screen
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE, MONTHLY_HOLD_FRAC_GOTRADE_TBAND
from seer_engine.strategies.allocator import BLEND, BlendParams, BlendPart
from seer_engine.strategies.f_index import TIMING, TimingParams

ADDED = date(2026, 11, 13)

ALWAYS_SPY = TimingParams(hold="SPY", signal="SPY", rule="always")
Y20_B40 = YieldParams(_screen(20), pool=100, keep=40)  # M0163-Y20-B40's params, verbatim
Y20_B40_SW = YieldParams(_screen(20, ("SPY", 200)), pool=100, keep=40)  # M0163-Y20-B40-SW's, verbatim


def _blend(core_share: str, params: YieldParams) -> BlendParams:
    c = Decimal(core_share)
    return BlendParams((BlendPart(TIMING, ALWAYS_SPY, c), BlendPart(YIELD, params, Decimal(1) - c)))


def _v(suffix: str, rules, params: BlendParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0164-{suffix}", family="M0164", rules=rules, allocator=BLEND,
                     params=params, rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0164",
    name="A small high-yield partner beside a large SPY core: 70% SPY, 30% the yearly banded dividend-yield book",
    family="stock-core-satellite",
    source_kind="variation",
    source_ref=(
        "Variation of M0163 (Novy-Marx & Velikov 2016, A Taxonomy of Anomalies and Their Trading "
        "Costs, Rev. Financial Studies 29(1); Fama & French 1993); the core-satellite frame of M0030 and M0104"
    ),
    parent_id="M0163",
    hypothesis=(
        "Dividend yield as value is decades old and the low-turnover framing came in 2016, after "
        "the dev window. M0163's 20-in, 40-out yield book re-ranked each December beat SPY on the "
        "owner's deposits (+9.0% vs +7.2%, trial 512) but fell 62% in 2008 and lost all of "
        "2009-2014, so alone it cannot meet the 25% fall bar or the 2009-2015 era. Held as a 30% "
        "slice beside a 70% always-SPY core it keeps SPY's drift for most of the money and "
        "takes about a third of the yield book's fall. Fractional shares at Gotrade's real fees "
        "on the owner's deposits. Arms: C70-YB (70% SPY, 30% M0163-Y20-B40's book, preset 1% "
        "band, close to a monthly rebalance), C70-YB-TBAND (the same on the 20%-of-own-target "
        "band, the nearest available to a drift-only rebalance), C85-YB (dose check: 15% yield "
        "book), C70-YB-SW (the sleeve behind M0163's SPY-200 switch, so it sits in cash in a bear "
        "market). Controls cited, not re-run: the sleeve alone is M0163-Y20-B40 (trial 512) and "
        "its switched twin (trial 513); the 80/20 comparator is M0104-C80-UP (trial 522). "
        "Success: C70-YB beats total-return SPY with worst fall <= 25%, PF >= 1.3, a positive "
        "edge in 2009-2015 and a majority of walk-forward folds, and the dose check moves the "
        "same way as the slice."
    ),
    expected_failure=(
        "SPY alone fell about 55% from its 2007 peak, and a 70% SPY core with an unbraked 30% "
        "yield slice that fell 62% cannot fall less than SPY: every unswitched arm should break "
        "the 25% fall bar, so eligibility is only possible behind the switch. The yield book "
        "lagged in 2009-2014 when big growth led, so the blends should trail SPY there, and 30% "
        "is probably too little to lift the total above SPY at all: the whole-window lead, if any, "
        "will be a fraction of a point. Survivorship flatters the slice (yield traps that died are "
        "missing), and withholding tax on dividends is not modelled."
    ),
    candidates=(
        _v("C70-YB", MONTHLY_HOLD_FRAC_GOTRADE, _blend("0.7", Y20_B40),
           "70% SPY, 30% the yearly banded yield book (M0163-Y20-B40's params), 1%-of-account resize band"),
        _v("C70-YB-TBAND", MONTHLY_HOLD_FRAC_GOTRADE_TBAND, _blend("0.7", Y20_B40),
           "The same blend on the 20%-of-own-target band: a lazier rebalance, nearest to a drift-only rule"),
        _v("C85-YB", MONTHLY_HOLD_FRAC_GOTRADE, _blend("0.85", Y20_B40),
           "Dose check: 85% SPY, 15% the yield book"),
        _v("C70-YB-SW", MONTHLY_HOLD_FRAC_GOTRADE, _blend("0.7", Y20_B40_SW),
           "70% SPY, 30% the yield book behind the SPY-200 switch (M0163-Y20-B40-SW's params): the sleeve idles in cash in a bear market"),
    ),
    seen_keys=(
        "concept:core-satellite-spy-yield-banded",
        "concept:dividend-yield-value",
        "concept:core-satellite",
    ),
)

"""M0532 — Invest each top-up the day it arrives: does a deposit waiting for the next re-pick cost the book anything?

Source: knowledge, from Sera 20261108-1427's reading of M0524 (the book's idle money was mostly a
deposit the 1% band left unspent) and M0119's HOLD arm (a book that left deposits in cash was 77%
invested and lost 1.5 points a year). Cash drag is textbook; no published anomaly is involved, so
nothing here has had a crowd to fade.

THE MECHANISM, measured before the arms were fixed: the host is 50 equal slots, so one slot is 2%
of equity and the owner's 5,000,000 IDR top-up is a few tenths of a percent of the account after
the first years. Under the habitual band (1% of equity) no single name's gap ever reaches the
band from a deposit alone, so a monthly book does not "wait for the next re-pick" with the cash,
it waits until drift or an exit happens to clear the band. That is why the lever here is the band
and the cadence together, never the picking.

ONE FIXED BOOK, no new picking: M0524's host (the 50 most-traded index members, equal weight,
fractional shares, Gotrade's real fees, the owner's monthly funding), under this method's own
allocator id. Every arm shares the names and weights on every rank date; only the deployment
differs.
  * HABIT: today's rule (E1, monthly, 1% band). Records as M0524-CASH's book twin (itself
    M0266-L's). Expected, costs no look; it is the control, not a new book.
  * SPY-PARK: the same, with the unspent residual held in SPY until the re-pick. Records as
    M0524-SPY's book twin; named here so the arms sit in one run at one fee schedule.
  * ADD-MONTHLY: band shut to zero and trims off, monthly. The deposit is spent at the next
    re-pick in full, on the names furthest below a slot, and nothing is sold to fund it.
  * ADD-WEEKLY: the same, checked every week (a deposit waits at most a week).
  * ADD-DAILY: the same, checked every session, so the deposit is invested the day it lands.
Trims are off on every ADD arm so that the only new trading is spending cash: a rebalancing sell
would move the answer from "when is cash spent" to "what does rebalancing pay", which M0266 and
M0286 already settled (nothing). Dividends are cash too, and are spent the same way.
The all-SPY yardstick the idea named is the lab's own benchmark line (funded return against the
same deposits in total-return SPY), recorded on every trial, so no arm repeats it.

Pure. The allocator is M0266's and reads only bars dated <= d.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0127_slot_relative_resize_band import E1
from seer_engine.lab.methods.m0266_exposure_matched_rebalance import ScaledBandParams, ScaledMostTradedEqualWeight
from seer_engine.sim.rules import TradeRules

ADDED = date(2026, 11, 9)


class _HostBook(ScaledMostTradedEqualWeight):
    """M0266's book under this method's own id: a new digest, the same names and weights."""

    id = "M0532"


BOOK = _HostBook()
PARAMS = ScaledBandParams(scale=Decimal(1))

PARK: TradeRules = replace(E1, id="monthly-hold-frac-gotrade-idle-spy", idle_symbol="SPY")
ADD_MONTHLY: TradeRules = replace(
    E1, id="monthly-hold-frac-gotrade-add-only", resize_band=Decimal("0"), resize_trims=False
)
ADD_WEEKLY: TradeRules = replace(
    ADD_MONTHLY, id="monthly-rank-weekly-add-only-frac-gotrade", resize_cadence="weekly"
)
ADD_DAILY: TradeRules = replace(
    ADD_MONTHLY, id="monthly-rank-daily-add-only-frac-gotrade", resize_cadence="daily"
)


def _v(suffix: str, rules: TradeRules, rationale: str) -> Candidate:
    return Candidate(
        id=f"M0532-{suffix}",
        family="M0532",
        rules=rules,
        allocator=BOOK,
        params=PARAMS,
        rationale=rationale,
        added=ADDED,
        owner_inputs=(),
    )


METHOD = Method(
    id="M0532",
    name="Invest each top-up the day it arrives",
    family="deposit-deployment",
    source_kind="knowledge",
    source_ref=(
        "M0524 (the idle money was a deposit the band left unspent); M0119 HOLD (77% invested, "
        "-1.5 pts/yr); M0286 EQ-DEPOSIT (spend the deposit, never sell); insight 492 (cash in "
        "lumps costs more than cash spread evenly)"
    ),
    parent_id=None,
    hypothesis=(
        "Sera 20261108-1427 found that most of a book's idle money was a deposit the rebalancing "
        "band left unspent until the next re-pick, not leftover weight (M0524). The owner tops up "
        "5,000,000 IDR on the 25th; the question is whether the timing of putting that cash to work "
        "is worth anything on one fixed book with no new picking in it. Host: M0524's 50 most-traded "
        "index members, equal weight, fractional shares, Gotrade real fees, owner funding, under "
        "this method's own allocator id. Five arms: HABIT (monthly, 1% band: today's rule, book twin "
        "of M0524-CASH and so of M0266-L), SPY-PARK (the residual held in SPY, book twin of "
        "M0524-SPY), and a three-rung ladder with the band shut and trims off, so the only new "
        "trading is spending cash: ADD-MONTHLY, ADD-WEEKLY, ADD-DAILY. Fees can make many small buys "
        "cost more than the wait, so the lab's fee and trade columns are read beside return. "
        "Cash drag is textbook, not a published anomaly, so the fade note does not apply. "
        "PREDICTIONS, written before any return was read. (1) Exposure rises down the ladder: "
        "HABIT about 89%, ADD-MONTHLY near 97%, ADD-DAILY near 99%. (2) Funded return rises with "
        "it but by under one point a year from HABIT to ADD-DAILY, because the deposit is a few "
        "tenths of the account once it is a few years old. (3) ADD-DAILY pays more in fees than "
        "ADD-WEEKLY for almost no extra return, because Gotrade's per-order minimum bites on "
        "dust-sized buys. (4) No arm beats deposit-matched SPY: the book has no edge over the "
        "index, only a different cash balance."
    ),
    expected_failure=(
        "The ladder reads flat: the cash sat for a week or two on average, so the gap is a "
        "fraction of a point and inside fee noise. Or the band-zero arms trade the whole book "
        "back to slot on the first add and the fees swamp the gain, making ADD arms worse than "
        "HABIT and the finding about order minimums, not timing. Or ADD-MONTHLY, ADD-WEEKLY and "
        "ADD-DAILY share one curve (the cadence never moved), which would be a dial that never "
        "turned, not a ladder. Or SPY-PARK and ADD-DAILY converge, in which case there is nothing "
        "to choose between parking and spending."
    ),
    candidates=(
        _v("HABIT", E1, "Control: today's rule, monthly with the 1% band, residual stays cash"),
        _v("SPY-PARK", PARK, "Same book, the unspent residual held in SPY until the re-pick"),
        _v("ADD-MONTHLY", ADD_MONTHLY, "Band shut, trims off, monthly: the deposit is spent at the next re-pick"),
        _v("ADD-WEEKLY", ADD_WEEKLY, "Band shut, trims off, checked weekly: the deposit waits at most a week"),
        _v("ADD-DAILY", ADD_DAILY, "Band shut, trims off, checked daily: the deposit is invested the day it lands"),
    ),
    seen_keys=(
        "concept:deposit-deployment-timing",
        "concept:invest-the-deposit-the-day-it-arrives",
    ),
)

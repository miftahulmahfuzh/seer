"""M0099 — Buy the dividend cut in the month it happens: a punished big company in its first three months.

Source: variation of M0080. Michaely, Thaler & Womack (1995), "Price reactions to dividend
initiations and omissions: overreaction or drift?", Journal of Finance 50(2) (NBER w4778, 1994).
Idea: M0080 held cutters 6-18 months on and found nothing; M0077 found that benching them for six
months cost about a point a year on the news-day book. The one window neither tested is the
first months, where the overreaction half of the papers' title would show up as a bounce and the
drift half as a further fall. No code is new: this reuses M0080's allocator with its window moved
to 0-91 days after the alarm and the own-trend filter off (a fresh cutter is below its average
almost by construction), so the picks are exactly M0077's alarm, held early.
"""

from __future__ import annotations

from datetime import date

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0080_dividend_cut_recovery import NOT20, RECOVERY, T20, RecoveryParams
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE

ADDED = date(2026, 10, 25)


def _v(suffix: str, params: RecoveryParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0099-{suffix}", family="M0099", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=RECOVERY, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0099",
    name="Buy the dividend cut in the month it happens: does a punished big company bounce rather than keep drifting down?",
    family="stock-dividend-cut-recovery",
    source_kind="variation",
    source_ref="M0080; M0077; Michaely, Thaler & Womack (1995), JF 50(2), https://www.nber.org/papers/w4778",
    parent_id="M0080",
    hypothesis=(
        "Michaely, Thaler & Womack (1995) titled their paper 'overreaction or drift?'; M0080 found "
        "that owning big index members 6-18 months after a dividend cut or omission adds nothing "
        "(picks alone 5.3% vs SPY 7.2% a year, 1 of 4 folds, -3.9 points a year in 2009-2015) and "
        "M0077 found benching them for 6 months cost about a point a year on the news-day book. "
        "The untested window is the first months: hold members whose cut or omission alarm "
        "(M0077's, announcement timing) fired 0-91 days ago, no own-trend filter, up to 20 at 5%, "
        "rest SPY, behind the SPY-200 switch, monthly, fractional at Gotrade's real fees, with the "
        "ex-date twin as control and a 0-182-day hold as a second horizon. The paper was published "
        "in 1995, so the dev window is after the crowd could know it. Variants: ANN-91-T (the "
        "rule), EX-91-T (control: alarm on the ex-date), ANN-182-T (second horizon, 0-182 days), "
        "ANN-91 (no SPY switch, always invested: with ANN-91-T it forms the switch on/off pair, so "
        "what acting behind the switch costs can be read off). Success: a variant beats total-"
        "return SPY on dev within the 20% worst fall with a positive 2009-2015 edge and a majority "
        "of walk-forward folds."
    ),
    expected_failure=(
        "Same scarcity as M0080: 2-8 names most years and a 2009 episode, so the book is mostly "
        "SPY and the folds are thin. The papers' drift says fresh cutters keep losing, and a "
        "fresh cutter is a falling stock, so the worst fall may break 20%, especially in 2008-09 "
        "when the cutters were banks. Announcement vs ex-date timing should differ by under half "
        "a point a year. An omission alarm can fire on a data gap or a switch to half-yearly "
        "payments, which adds noise. If it fails, the dividend-cut direction for big members is "
        "closed."
    ),
    candidates=(
        _v("ANN-91-T", RecoveryParams(T20, min_age=0, max_age=92, sma_n=0),
           "Members 0-91 days past a cut or omission alarm, up to 20 at 5%, rest SPY, behind the SPY-200 switch"),
        _v("EX-91-T", RecoveryParams(T20, timing="ex", min_age=0, max_age=92, sma_n=0),
           "Control: the same rule with the alarm timed on the ex-date"),
        _v("ANN-182-T", RecoveryParams(T20, min_age=0, max_age=183, sma_n=0),
           "Second horizon: held from the alarm to six months after it"),
        _v("ANN-91", RecoveryParams(NOT20, min_age=0, max_age=92, sma_n=0),
           "No SPY switch: always invested, the picking alone"),
    ),
    seen_keys=(
        "concept:dividend-cut-fresh-window",
        "concept:dividend-cut-recovery",
    ),
)

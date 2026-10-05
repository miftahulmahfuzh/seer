"""M0004 — Momentum, own-vol scaled, ranked and re-scaled on different clocks (M0001 variation).

Source: the lab's own journal, feature-wish "Weekly risk checks with monthly re-ranking"
(2026-10-04), raised by M0001's result. M0001-TV10 (monthly) scored PF 2.31 at 2.74 turnover;
M0001-TV10-W moved to a weekly clock and scored PF 1.49 at 5.93 turnover. The weekly variant
changed two things at once — which stocks it holds AND how much it holds — so the collapse
cannot be attributed. This method separates them with the ``TradeRules`` cadence split: the
basket is re-ranked on the slow clock, the exposure is re-scaled on the fast one.

The allocator is M0001's ``OWNVOL``, unchanged and imported (M0001's file is frozen: it has
trials). Only the rule set differs, which is exactly what makes this a new method rather than a
re-roll: the lab's config digest covers the rules.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0001_momentum_own_vol_scaling import MOM20_TREND, OWNVOL, OwnVolParams
from seer_engine.sim.rules import MONTHLY_HOLD, MONTHLY_RANK_WEEKLY_RESIZE, WEEKLY_HOLD
from seer_engine.strategies.f_factor import FactorParams

ADDED = date(2026, 10, 5)

# M0001's two clocks, and the three splits between them. Rank cadence first, resize cadence
# second: "MW" is a monthly rank re-scaled weekly.
MONTHLY_RANK_DAILY_RESIZE = replace(MONTHLY_HOLD, id="monthly-rank-daily-resize", resize_cadence="daily")
WEEKLY_RANK_DAILY_RESIZE = replace(WEEKLY_HOLD, id="weekly-rank-daily-resize", resize_cadence="daily")

TV10 = OwnVolParams(MOM20_TREND, Decimal("0.10"), 63)  # M0001-TV10's parameters exactly
TV12 = OwnVolParams(MOM20_TREND, Decimal("0.12"), 63)  # M0001-TV12's
NOTREND = OwnVolParams(FactorParams(rank="momentum", top=20, trend=None), Decimal("0.10"), 126)


def _v(suffix: str, params: OwnVolParams, rules, rationale: str) -> Candidate:
    return Candidate(id=f"M0004-{suffix}", family="M0004", rules=rules, allocator=OWNVOL,
                     params=params, rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0004",
    name="Own-vol scaled momentum on split rank and resize clocks",
    family="stock-momentum-risk-managed",
    parent_id="M0001",
    source_kind="variation",
    source_ref="M0001 (lab journal feature-wish, 2026-10-04: weekly risk checks with monthly re-ranking)",
    hypothesis=(
        "M0001-TV10-W's collapse (PF 2.31 -> 1.49) came from re-ranking weekly, not from re-scaling "
        "weekly: a fresh 12-1 momentum ranking every week churns the basket, and the turnover more "
        "than doubled (2.74 -> 5.93). Holding the monthly basket while re-scaling its exposure "
        "weekly buys the faster crash response without that churn, so M0004-TV10-MW lands max DD "
        "below M0001-TV10's 11.0% at a profit factor and turnover close to its 2.31 and 2.74."
    ),
    expected_failure=(
        "The re-scale alone is most of the turnover, because own-vol moves enough week to week that "
        "the book is traded back to a new exposure every Monday: turnover lands near 5 and the "
        "profit factor near the weekly variant's 1.49. Or the monthly basket is the thing that "
        "actually controls drawdown, and re-scaling faster neither helps nor hurts — every split "
        "variant scores within noise of M0001-TV10, and the feature buys nothing."
    ),
    candidates=(
        _v("TV10-MW", TV10, MONTHLY_RANK_WEEKLY_RESIZE,
           "M0001-TV10's basket clock with M0001-TV10-W's risk clock: the journal's exact question"),
        _v("TV12-MW", TV12, MONTHLY_RANK_WEEKLY_RESIZE,
           "Same split at 12% target vol: does the extra exposure survive faster risk checks"),
        _v("TV10-MD", TV10, MONTHLY_RANK_DAILY_RESIZE,
           "Monthly basket, daily re-scale: the fastest risk control the split allows"),
        _v("TV10-WD", TV10, WEEKLY_RANK_DAILY_RESIZE,
           "Weekly basket, daily re-scale: isolates re-ranking as M0001-TV10-W's cost, not re-scaling"),
        _v("NOTREND-MW", NOTREND, MONTHLY_RANK_WEEKLY_RESIZE,
           "Barroso's setup (no trend filter, 6-month vol) with weekly risk checks as the only guard"),
    ),
    seen_keys=(
        "concept:rank-resize-cadence-split",
        "insight:lab-journal-2026-10-04-weekly-risk-monthly-rerank",
    ),
)

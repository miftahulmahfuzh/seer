"""M0439 — Why the weekly schedule costs 1.3 points: the same momentum picks, weekly versus monthly.

Source: variation of M0089. M0089's HOST (monthly rules) earned 13.8% a year and its ONE-W (the very
same allocator, weekly rules) 12.5%, with 1,162 and 1,178 trades. The allocator is the same K=1
momentum book, so on both schedules it names the same 20 names on the same month-end data date.
The only thing the schedule changes is how often the book is looked at: every week the weekly book
trims or tops up holdings whose weight has drifted from their 5% slot (resize=True, equity band),
and every week it drops a name that has left the index. This method switches those off one at a
time. Published idea: none (a decomposition of a recorded gap), so there is no crowding to fade.

Idea. If the 1.3 points is trimming of winners, the weekly book with trimming switched off should
land on the monthly book's number, and a wide band on the weekly book should recover most of it. If
it does not, the gap is in something the arms here do not touch (the weekly index-membership drop
or fee timing), and that is itself the answer.

Arms (all fractional, Gotrade's real fees, the M0089 allocator with offsets=(0,), 20 names, trend
switch on SPY 200-day). HOST and ONE-W are not re-registered: they are M0089's recorded trials
(the same configurations, and a configuration runs once per window), read back with ``lab show
M0089`` as the controls on the same store.
    * W-NOTRIM: weekly rules, resize off. Names are bought when picked and sold when dropped, and
      never trimmed in between. This is the "no trimming" arm of the hypothesis.
    * W-BAND: weekly rules, resize on, band measured against each holding's own target (20%). A
      holding must drift a fifth off its slot before it trades.
    * M-NOTRIM: monthly rules, resize off. Is trimming worth anything on the monthly book either?
    * M-BAND: monthly rules, the 20% own-target band. The matching band on the monthly schedule.
The pair (weekly, monthly) is run at each of three trimming settings (equity band = M0089's two
recorded arms, own-target band, none), so the schedule's cost at each setting is a straight
difference, with the trimming rule cancelling inside each pair.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20
from seer_engine.lab.methods.m0089_two_half_books import (
    TRANCHES,
    WEEKLY_HOLD_FRAC_GOTRADE,
    TrancheParams,
)
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE, MONTHLY_HOLD_FRAC_GOTRADE_TBAND

ADDED = date(2026, 11, 1)

W_NOTRIM = replace(WEEKLY_HOLD_FRAC_GOTRADE, id="weekly-hold-frac-gotrade-notrim", resize=False)
W_BAND = replace(WEEKLY_HOLD_FRAC_GOTRADE, id="weekly-hold-frac-gotrade-tband", resize_basis="target")
M_NOTRIM = replace(MONTHLY_HOLD_FRAC_GOTRADE, id="monthly-hold-frac-gotrade-notrim", resize=False)
M_BAND = MONTHLY_HOLD_FRAC_GOTRADE_TBAND

_PARAMS = TrancheParams(N20, (0,))


def _v(suffix: str, rules: object, rationale: str) -> Candidate:
    return Candidate(id=f"M0439-{suffix}", family="M0439", rules=rules, allocator=TRANCHES,
                     params=_PARAMS, rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0439",
    name="Why the weekly schedule costs 1.3 points: the same momentum picks, decided weekly versus monthly",
    family="p7a-f4",
    source_kind="variation",
    source_ref="variation of M0089: its HOST and ONE-W arms, decomposed (no outside source)",
    parent_id="M0089",
    hypothesis=(
        "M0089 found the same 12-month momentum picks earned 13.8% a year on the monthly schedule "
        "and 12.5% on a weekly decision schedule with nearly the same trade count (1,162 vs 1,178). "
        "Something other than trades differs. With the allocator re-picking only at month end on "
        "both, the candidates are weekly trims of drifted holdings, and the weekly drop of a name "
        "that left the index. Arms: W-NOTRIM, W-BAND, M-NOTRIM and M-BAND, with M0089's recorded "
        "HOST and ONE-W as the equity-band controls (identical configurations, so not re-run). "
        "A definite yes: W-NOTRIM is within 0.4 points a year of the monthly book (HOST), and "
        "W-BAND recovers at least half of the 1.3 points. A definite no: W-NOTRIM is still more "
        "than 0.9 points a year below M-NOTRIM, so trimming is not the cause. Judged on funded "
        "CAGR vs SPY over the dev window and on 2009-2015, with the lab's screen unchanged."
    ),
    expected_failure=(
        "The gap is only trimming of winners, which a band removes. The more interesting failure is "
        "the opposite: no-trim books let winners run and concentrate, so the worst fall deepens "
        "and the screen's drawdown limit fails even where the return recovers. The 1.3 points "
        "may also be sampling noise from where the first trade lands, in which case all arms "
        "scatter within a point of each other and none says anything. None of the arms can clear "
        "the gate by itself, since the host's own fall is already over the screen."
    ),
    candidates=(
        _v("W-NOTRIM", W_NOTRIM, "Weekly schedule with no trimming: buy on pick, sell on drop only"),
        _v("W-BAND", W_BAND, "Weekly schedule, trim only when a holding is a fifth off its slot"),
        _v("M-NOTRIM", M_NOTRIM, "Monthly schedule with no trimming: the matching control for W-NOTRIM"),
        _v("M-BAND", M_BAND, "Monthly schedule, trim only when a holding is a fifth off its slot"),
    ),
    seen_keys=(
        "concept:weekly-schedule-cost-decomposition",
        "concept:momentum-trimming-versus-schedule",
    ),
)

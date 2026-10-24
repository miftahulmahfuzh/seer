"""M0332 — Intermediate momentum: rank on months 7 to 12 back, not the latest six.

Source: Novy-Marx (2012), "Is momentum really momentum?", Journal of Financial Economics.
Idea: the paper finds the past-return premium lives in the return from 12 to 7 months back and
that the most recent six months add little. The lab's momentum books all rank on 12-1, which
blends the two halves. If the paper is right, ranking on the old half alone should keep the
edge and the recent half alone should lose it. Published 2012, so the dev window (to 2015) only
partly sits after the crowd; the edge may be an early-years one.

Every arm reuses ``FACTOR`` on the F4 chassis (top 20, equal weight, monthly, F4's screen) at
Gotrade's real fees in fractional shares. Trading days stand in for months at 21 a month, so
months 7-12 back is ``mom_n=252, mom_skip=126`` and months 2-6 back is ``mom_n=126, mom_skip=21``.
Five variants, fixed before any result: the treatment, the recent-half arm, the plain 12-1
control, and the two no-switch twins of the treatment and the control. The twins are the
dressing arms: the SPY 200-day switch carries most of what these books earn (F4's 12-1 book
falls 68% without it), so a window that only wins behind the switch has told us about the switch.
Pure; reads only bars dated <= d.
"""

from __future__ import annotations

from datetime import date

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.f_factor import FACTOR, FactorParams

ADDED = date(2026, 10, 24)

SWITCH = ("SPY", 200)


def _v(suffix: str, rationale: str, mom_n: int, mom_skip: int, trend=SWITCH) -> Candidate:
    return Candidate(
        id=f"M0332-{suffix}", family="M0332", rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=FACTOR,
        params=FactorParams(rank="momentum", top=20, mom_n=mom_n, mom_skip=mom_skip, trend=trend),
        rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0332",
    name="Intermediate momentum: rank on months 7 to 12 back, not the latest six",
    family="stock-intermediate-momentum",
    source_kind="paper",
    source_ref="Novy-Marx 2012, Is momentum really momentum? (JFE)",
    parent_id=None,
    hypothesis=(
        "Novy-Marx (2012) finds the momentum premium is carried by the return from 12 to 7 months "
        "back, while the most recent six months add little. Top 20 by that return, equal weight, "
        "monthly, behind the SPY 200-day switch, in fractional shares at Gotrade's real fees. If "
        "the finding holds, the months 12-7 book should match or beat the plain 12-1 control and "
        "the months 6-2 book should trail it. Question: is the dev-window edge of the lab's "
        "momentum books carried by the old half of the lookback? Each arm is also run with the "
        "switch off, so the window effect can be told from the switch's effect. The paper is from "
        "2012, so a strong dev result may be the pre-publication years and fade after."
    ),
    expected_failure=(
        "The months 12-7 arm is indistinguishable from the 12-1 control, because the two share "
        "most of the same names and the SPY switch decides when the book is invested, so the "
        "difference is inside the noise of 20-name books. A second way it fails: like every "
        "momentum book here it falls 20%+ at a momentum crash (2009 rebound) and breaks the "
        "drawdown bar, and the no-switch twins fall far deeper. Behind the switch it still lags "
        "SPY in 2009-2015 through time spent in cash."),
    candidates=(
        _v("M12-7", "treatment: months 12 to 7 back, behind the switch", 252, 126),
        _v("M6-2", "recent half: months 6 to 2 back, behind the switch", 126, 21),
        _v("M12-1", "control: plain 12-1 momentum, behind the switch", 252, 21),
        _v("M12-7-NOSW", "treatment with the switch off, always invested", 252, 126, trend=None),
        _v("M12-1-NOSW", "control with the switch off, always invested", 252, 21, trend=None),
    ),
    seen_keys=("concept:intermediate-momentum-months-12-to-7", "concept:novy-marx-2012"),
)

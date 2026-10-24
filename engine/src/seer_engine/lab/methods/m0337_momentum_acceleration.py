"""M0337 — Momentum acceleration: rank on how much the last six months outran the six before.

Source: the momentum-acceleration literature (e.g. Chen & Yang, Review of Finance); the second
difference of price as a signal. Idea: a stock whose pace is speeding up (return over months 6-1
back minus return over months 12-7 back) may carry more of the momentum premium than one whose
pace merely stayed high, because the speed-up is the part the crowd has not yet extrapolated.
Published in the 2010s, so the dev window (to 2015) barely sits past the crowd.

Every arm sits on the F4 chassis (F4's screen, top 20, equal weight, monthly, SPY 200-day switch)
at Gotrade's real fees in fractional shares. Trading days stand in for months at 21 a month, so
months 6-1 is ``c[-22]/c[-127]`` and months 12-7 is ``c[-127]/c[-253]``. The screen comes from
``factor_rows`` unchanged, so only the ranking differs between arms.
Four variants, fixed before any result: acceleration, its mirror (deceleration), the no-opinion arm (the same book ranked on dollar volume,
which carries no view on past returns, so the cost of holding 20 monthly-rebalanced liquid names
behind the switch is priced), and acceleration with the switch off. The plain 12-1 control is
M0332-M12-1, the identical configuration already recorded on the dev window (the lab refuses a
second run of it), so the analysis compares against that trial. A mirror proves the signal,
not what acting on it costs; the no-opinion arm is what prices that.
Pure; reads only bars dated <= data_date.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    FactorParams,
    factor_lookback,
    factor_rows,
    trend_on,
)

ADDED = date(2026, 10, 24)

SWITCH = ("SPY", 200)
MODES = ("accel", "decel", "dvol")


@dataclass(frozen=True, slots=True)
class Params:
    mode: str = "accel"
    top: int = 20
    trend: tuple[str, int] | None = SWITCH

    def factor(self) -> FactorParams:
        # 12-1 window is the longest read, so the screen needs the same history as the control.
        return FactorParams(rank="momentum", top=self.top, mom_n=252, mom_skip=21, trend=self.trend)

    def as_dict(self) -> dict[str, str]:
        t = "none" if self.trend is None else f"{self.trend[0]}:{self.trend[1]}"
        return {"mode": self.mode, "top": str(self.top), "trend": t}


class Alloc:
    """Top ``top`` of F4's screened members by acceleration, deceleration or dollar volume.

    All cash unless the trend gate is on. Held symbols are not favoured: the book is re-ranked
    from scratch each month, like F4.
    """

    id = "M0337"

    def lookback(self, params: Params) -> int:
        return factor_lookback(params.factor())

    def symbols(self, params: Params) -> tuple[str, ...]:
        return () if params.trend is None else (params.trend[0],)

    def holds(self, params: Params) -> tuple[str, ...]:
        return ()

    def uses_members(self, params: Params) -> bool:
        return True

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Params) -> tuple[Target, ...]:
        if params.mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {params.mode!r}")
        fp = params.factor()
        if not trend_on(history, data_date, fp):
            return ()
        scored: list[tuple[float, str, float]] = []
        for row in factor_rows(history, members, data_date, fp):
            if params.mode == "dvol":
                score = row.dollar_volume
            else:
                h = history[row.symbol]
                i = h.index_of(data_date)
                c = h.close
                recent = float(c[i - 21] / c[i - 126] - 1.0)
                older = float(c[i - 126] / c[i - 252] - 1.0)
                score = recent - older
                if params.mode == "decel":
                    score = -score
            scored.append((-score, row.symbol, row.close))
        w = equal_weight(params.top)
        out: list[Target] = []
        for _, symbol, close in sorted(scored)[: params.top]:
            t = target_from_close(symbol, close, w)
            if t is not None:
                out.append(t)
        return tuple(out)

    def prepare(self, history: Mapping[str, History]) -> Any:
        return dict(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Params) -> tuple[Target, ...]:
        return self.targets(prepared, members, data_date, held, params)


ALLOC = Alloc()


def _v(suffix: str, mode: str, rationale: str, trend=SWITCH) -> Candidate:
    return Candidate(id=f"M0337-{suffix}", family="M0337", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=ALLOC, params=Params(mode=mode, trend=trend),
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0337",
    name="Momentum acceleration: rank on how much the last six months outran the six before",
    family="stock-momentum-acceleration",
    source_kind="knowledge",
    source_ref="",
    parent_id=None,
    hypothesis=(
        "Rank index members that pass F4's screen by the change in momentum: return over months "
        "6-1 back minus return over months 12-7 back. Top 20 equal weight, monthly, behind the SPY "
        "200-day switch, in fractional shares at Gotrade's real fees. Question: does a stock whose "
        "pace is speeding up beat one whose pace merely stayed high? Arms: acceleration, its "
        "mirror (deceleration), plain 12-1 as the control (M0332-M12-1, already recorded), a no-opinion arm (same chassis ranked "
        "on dollar volume) to price what acting on a ranking costs, and acceleration with the "
        "switch off. If the idea holds, acceleration beats the 12-1 control and deceleration "
        "trails the no-opinion arm. The literature is from the 2010s, so the dev window is "
        "mostly before the crowd; a strong dev result may fade after."),
    expected_failure=(
        "Acceleration is mostly a noisy reshuffle of 12-1 winners: it is within noise of the "
        "control, and any gap is the SPY switch plus fees on a book that turns over more than 12-1 "
        "(a difference of two six-month returns flips faster). Like every momentum book here it "
        "likely falls hard at the 2009 rebound, and the no-switch twin falls far deeper. Behind the "
        "switch it still lags SPY in 2009-2015 through time spent in cash."),
    candidates=(
        _v("ACC", "accel", "treatment: months 6-1 return minus months 12-7 return, behind the switch"),
        _v("DEC", "decel", "mirror: the lowest acceleration, behind the switch"),
        _v("DVOL", "dvol", "no opinion: same screen ranked on dollar volume, behind the switch"),
        _v("ACC-NOSW", "accel", "treatment with the switch off, always invested", trend=None),
    ),
    seen_keys=("concept:momentum-acceleration", "concept:second-difference-of-price"),
)

"""M0640 — Price-path convexity: quadratic curvature of the price path, against plain momentum.

Source: Gulen & Woeppel, "Price Path Convexity" (JFQA, forthcoming); Gettleman & Marks (2005),
momentum acceleration. Idea: two stocks can share the same 12-1 return yet have arrived there on
different-shaped paths -- one accelerating into the finish, one decelerating. The papers report
that the SHAPE (the sign of the quadratic term of a trend fit) predicts returns beyond the level.

Screen: the F4 eligibility test (liquidity, price floor, finite 12-1 momentum and 60-day vol) at
mom_n=252, mom_skip=21, vol_n=60, same as the lab's plain-12-1 control, so the pool this method
ranks from is the same pool M0332-M12-1 already ranked. Scoring is independent of that screen:
for each eligible symbol, take the trailing 126 trading days (~6 months) of log closes ending at
d, min-max normalize the series to run from 0 to 1 over the window (removes price level and the
size of the move), fit a quadratic in t in [0, 1], and rank on the t^2 coefficient. Convex
(positive) means the path front-loaded small moves and back-loaded larger ones -- accelerating;
concave is the mirror. A flat window (identical normalized start/end numerically, or the fit is
degenerate) scores NaN and the symbol drops out of the ranking that month, same treatment as an
ineligible symbol.

Three variants, fixed before any result: the convex book (treatment), its mirror the concave book
(same screen, opposite sign -- a reversal proves the SHAPE signal is real, not a lucky convex
pick), and the convex book with the switch off (durability of the signal itself, isolated from
the market-timing gate). Two controls are already recorded on this exact screen and are cited,
not re-run: the plain 12-1 book (M0332-M12-1, trial #1149, same top-20/equal-weight/monthly/
SPY-200-switch/Gotrade-fractional chassis) prices what curvature adds over plain momentum level,
and the no-opinion dollar-volume book on the same screen (M0337-DVOL, first recorded as book
30e404f78a69, also M0159-ANY20-TREND / M0490-CTRL-GATE / M0491-EW-SW) prices what the habit of
holding 20 liquid monthly-rebalanced names behind the switch costs on its own, with no view on
path shape at all.

Published forthcoming (not yet in print as of this write), so unlike most of the lab's momentum
variants this one is not yet crowd-known in the way a 2005 or 2012 paper might be -- but
Gettleman & Marks (2005) already describes the discrete version, so some of the mechanism has
been public for two decades.
Pure; reads only bars dated <= data_date.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import FactorParams, factor_lookback, factor_rows, trend_on

ADDED = date(2026, 11, 13)

SWITCH = ("SPY", 200)
MODES = ("convex", "concave")
WINDOW = 126  # trailing trading days the quadratic is fit over (~6 months)


@dataclass(frozen=True, slots=True)
class Params:
    mode: str = "convex"
    top: int = 20
    trend: tuple[str, int] | None = SWITCH

    def factor(self) -> FactorParams:
        # Same screen as the plain 12-1 control (M0332-M12-1): mom_n/mom_skip/vol_n unchanged,
        # so the pool this method ranks is the pool that control already ranked.
        return FactorParams(rank="momentum", top=self.top, mom_n=252, mom_skip=21, trend=self.trend)

    def as_dict(self) -> dict[str, str]:
        t = "none" if self.trend is None else f"{self.trend[0]}:{self.trend[1]}"
        return {"mode": self.mode, "top": str(self.top), "trend": t}


def _curvature(close: np.ndarray) -> float:
    """The standardized quadratic coefficient of ``close``'s trailing ``WINDOW`` log prices.

    ``close`` is the last ``WINDOW`` closes ending at d. The log-price path is min-max normalized
    to run 0 to 1 over the window (removes price level and move size), then fit to a quadratic in
    t in [0, 1]. Returns the t^2 coefficient, or NaN when the window's start and end normalize to
    the same value (a flat round trip) and no curvature direction is defined.
    """
    logp = np.log(close)
    span = logp[-1] - logp[0]
    if not np.isfinite(span) or span == 0.0:
        return float("nan")
    norm = (logp - logp[0]) / span
    t = np.linspace(0.0, 1.0, WINDOW)
    coeffs = np.polyfit(t, norm, 2)
    return float(coeffs[0])


class Alloc:
    """Top ``top`` of the F4 screen's members by price-path curvature, convex or concave.

    All cash unless the trend gate is on. Held symbols are not favoured: the book is re-ranked
    from scratch each month.
    """

    id = "M0640"

    def lookback(self, params: Params) -> int:
        return max(factor_lookback(params.factor()), WINDOW)

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
            h = history[row.symbol]
            i = h.index_of(data_date)
            curv = _curvature(h.close[i + 1 - WINDOW : i + 1])
            if not np.isfinite(curv):
                continue
            score = curv if params.mode == "convex" else -curv
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
    return Candidate(id=f"M0640-{suffix}", family="M0640", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=ALLOC, params=Params(mode=mode, trend=trend),
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0640",
    name="Price-path convexity: quadratic curvature of the price path, against plain momentum",
    family="stock-price-path-convexity",
    source_kind="paper",
    source_ref=(
        "Gulen & Woeppel, Price Path Convexity (JFQA, forthcoming); "
        "Gettleman & Marks (2005), momentum acceleration"
    ),
    parent_id=None,
    hypothesis=(
        "Among F4-screened index members (the same pool the plain-12-1 control ranks), score each "
        "by the standardized quadratic coefficient of its trailing 6-month log-price path "
        "(min-max normalized to [0,1], fit against t in [0,1]): positive means the path "
        "accelerated into the finish (convex), negative means it decelerated (concave). Top 20 "
        "equal weight, monthly, behind the SPY 200-day switch, fractional shares at Gotrade's "
        "real fees, the owner's monthly top-up. Question: does the SHAPE of the recent path "
        "separate winners from losers beyond what plain 12-1 momentum already captures? Arms: "
        "convex (treatment), concave (its mirror -- a reversal here would say the shape signal is "
        "real, not a lucky convex pick), and convex with the switch off (the signal's own "
        "durability, apart from the market-timing gate). Two controls on this identical screen "
        "are already recorded and are cited rather than re-run: plain 12-1 (M0332-M12-1, trial "
        "#1149, ELIGIBLE at DSR 0.913) prices what curvature adds over level, and the no-opinion "
        "dollar-volume book (M0337-DVOL, first recorded as book 30e404f78a69) prices the habit of "
        "holding 20 liquid monthly names behind the switch with no view on shape at all. If the "
        "idea holds, convex beats both cited controls and concave trails them."
    ),
    expected_failure=(
        "Convexity is mostly a noisy re-ranking within the same 12-1 winners the plain control "
        "already holds: the three arms share most of their names month to month, convex is "
        "within noise of M0332-M12-1, and concave does not clearly trail the dollar-volume "
        "no-opinion book either. A continuous quadratic fit on a 126-day window is sensitive to a "
        "handful of extreme days (a single large gap can swing the t^2 coefficient), so the book "
        "likely turns over faster than plain 12-1 and pays more in fees for a ranking that is "
        "substantially the same stocks in a different order. Like every momentum book in this "
        "lab it probably falls hard at the 2009 momentum crash, and the no-switch twin falls far "
        "deeper; behind the switch it likely still lags SPY in 2009-2015 through time spent in "
        "cash."
    ),
    candidates=(
        _v("CONVEX", "convex", "treatment: top 20 by standardized quadratic curvature, behind the switch"),
        _v("CONCAVE", "concave", "mirror: the most concave (decelerating) 20, behind the switch"),
        _v("CONVEX-NOSW", "convex", "treatment with the switch off, always invested", trend=None),
    ),
    seen_keys=(
        "concept:price-path-convexity",
        "concept:quadratic-price-curvature",
        "concept:standardized-quadratic-coefficient",
    ),
)

"""M0641 -- Price-path convexity, refit on month-end closes instead of daily closes.

M0640 scored the same shape idea (Gulen & Woeppel, "Price Path Convexity", JFQA forthcoming;
Gettleman & Marks 2005) off a continuous quadratic fit through all 126 trading days of a
6-month log-price window. It traded 2,777 times over twenty years for a twenty-name monthly
book (CONVEX, trial #2243) -- far more than a monthly-rebalanced book should -- and failed dev
on both "beats SPY TR" and DSR (0.463 at N=416). The read in that method's `expected_failure`
was that a single large daily gap can swing a continuous fit's t^2 coefficient, so the book was
likely re-ranking on jump noise rather than on a stable trajectory.

This method tests that mechanism directly: same screen (F4 at mom_n=252, mom_skip=21, vol_n=60),
same window (126 trading days, ~6 months), same normalization (log prices, min-max to [0, 1]),
same chassis (top 20, equal weight, monthly, SPY-200 switch, MONTHLY_HOLD_FRAC_GOTRADE) -- but
the quadratic is fit through 6 points sampled evenly across the window (about one every 21
trading days, roughly a month apart) instead of all 126 daily closes. If jump noise in the daily
fit, not the shape itself, drove M0640's poor DSR and high turnover, the coarser fit should turn
over less and separate more cleanly from the two controls already recorded on this exact screen:
the plain 12-1 book (M0332-M12-1, trial #1149, ELIGIBLE at DSR 0.913) and the no-opinion
dollar-volume book (M0337-DVOL, first recorded as book 30e404f78a69). Both are cited, not re-run.

Same three arms as M0640, for the same reasons: convex (treatment), concave (its mirror -- a
reversal says the shape is real, not a lucky convex pick), and convex with the switch off (the
signal's own durability, apart from the market-timing gate).

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
WINDOW = 126  # trailing trading days the window spans, same as M0640 (~6 months)
NPOINTS = 6  # points sampled evenly across WINDOW, roughly one per month


@dataclass(frozen=True, slots=True)
class Params:
    mode: str = "convex"
    top: int = 20
    trend: tuple[str, int] | None = SWITCH

    def factor(self) -> FactorParams:
        # Same screen as M0640 and the plain 12-1 control (M0332-M12-1): mom_n/mom_skip/vol_n
        # unchanged, so the pool this method ranks is the pool those methods already ranked.
        return FactorParams(rank="momentum", top=self.top, mom_n=252, mom_skip=21, trend=self.trend)

    def as_dict(self) -> dict[str, str]:
        t = "none" if self.trend is None else f"{self.trend[0]}:{self.trend[1]}"
        return {"mode": self.mode, "top": str(self.top), "trend": t}


_SAMPLE_IDX = np.linspace(0, WINDOW - 1, NPOINTS).round().astype(int)


def _curvature_monthly(close: np.ndarray) -> float:
    """The standardized quadratic coefficient fit through ``NPOINTS`` sampled closes.

    ``close`` is the last ``WINDOW`` closes ending at d. Instead of M0640's fit through all
    ``WINDOW`` daily log prices, this samples ``NPOINTS`` of them at even spacing across the
    window (roughly a month apart) before the same log, min-max-to-[0,1], and quadratic-in-t
    steps. Returns the t^2 coefficient, or NaN when the sampled window's start and end normalize
    to the same value (a flat round trip) and no curvature direction is defined.
    """
    sampled = close[_SAMPLE_IDX]
    logp = np.log(sampled)
    span = logp[-1] - logp[0]
    if not np.isfinite(span) or span == 0.0:
        return float("nan")
    norm = (logp - logp[0]) / span
    t = np.linspace(0.0, 1.0, NPOINTS)
    coeffs = np.polyfit(t, norm, 2)
    return float(coeffs[0])


class Alloc:
    """Top ``top`` of the F4 screen's members by monthly-sampled price-path curvature.

    All cash unless the trend gate is on. Held symbols are not favoured: the book is re-ranked
    from scratch each month.
    """

    id = "M0641"

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
            curv = _curvature_monthly(h.close[i + 1 - WINDOW : i + 1])
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
    return Candidate(id=f"M0641-{suffix}", family="M0641", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=ALLOC, params=Params(mode=mode, trend=trend),
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0641",
    name="Price-path convexity, monthly-sampled",
    family="stock-price-path-convexity",
    source_kind="variation",
    source_ref=(
        "Gulen & Woeppel, Price Path Convexity (JFQA, forthcoming); "
        "Gettleman & Marks (2005), momentum acceleration"
    ),
    parent_id="M0640",
    hypothesis=(
        "M0640's daily-sampled quadratic curvature book (CONVEX, trial #2243) traded 2,777 times "
        "over twenty years for a twenty-name monthly book and failed dev on both beats-SPY-TR and "
        "DSR (0.463 at N=416), consistent with the curvature score flipping on single-day price "
        "jumps rather than on a real change in trajectory. This method refits the identical "
        "standardized-quadratic-coefficient score -- same F4 screen (mom_n=252, mom_skip=21, "
        "vol_n=60), same 126-trading-day (~6-month) window, same log/min-max-to-[0,1] "
        "normalization, same top-20/equal-weight/monthly/SPY-200-switch/Gotrade-fractional "
        "chassis -- but through 6 points sampled evenly across the window (about one per month) "
        "instead of all 126 daily closes. If jump noise in the daily fit, not the shape itself, "
        "drove M0640's poor DSR and high turnover, the coarser fit should turn over less and "
        "separate more cleanly from the two controls already recorded on this exact screen: "
        "plain 12-1 (M0332-M12-1, trial #1149, ELIGIBLE at DSR 0.913) prices what curvature adds "
        "over level, and the no-opinion dollar-volume book (M0337-DVOL, first recorded as book "
        "30e404f78a69) prices the habit of holding 20 liquid monthly names behind the switch with "
        "no view on shape at all -- both cited, not re-run. Arms: convex (treatment), concave "
        "(its mirror -- a reversal says the shape is real, not a lucky convex pick), and convex "
        "with the switch off (the signal's own durability, apart from the market-timing gate). If "
        "the idea holds, convex turns over markedly less than M0640-CONVEX, beats both cited "
        "controls, and concave trails them."
    ),
    expected_failure=(
        "A quadratic has three free parameters; fit through only 6 points it has almost no slack, "
        "so one bad month can swing the t^2 coefficient as easily as one bad day swung M0640's "
        "daily fit -- the mechanism may simply move from daily jump noise to monthly jump noise "
        "rather than going away. Likely outcome: turnover drops some (fewer re-rankable inputs "
        "per month) but convex still loses to SPY TR and still misses the DSR bar, and the top-20 "
        "book still tracks the plain 12-1 control within noise because coarse sampling barely "
        "changes which names rank highest on a 6-month window. Like M0640, expect a hard fall "
        "around the 2009 momentum crash, deeper on the no-switch twin, and time spent in cash "
        "behind the switch costing the gated arms in 2009-2015."
    ),
    candidates=(
        _v("CONVEX", "convex",
           "treatment: top 20 by standardized quadratic curvature on 6 monthly-sampled points, "
           "behind the switch"),
        _v("CONCAVE", "concave",
           "mirror: the most concave (decelerating) 20 on the same 6-point fit, behind the switch"),
        _v("CONVEX-NOSW", "convex",
           "treatment with the switch off, always invested", trend=None),
    ),
    seen_keys=(
        "concept:price-path-convexity-monthly-sampled",
        "concept:quadratic-price-curvature-monthly",
        "concept:standardized-quadratic-coefficient-6-point",
    ),
)

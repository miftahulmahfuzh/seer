"""M0614 -- Gap-free momentum: 6-month winners that had no single-day shock, behind the 200-day switch.

Source: Clenow, Stocks on the Move (2015), who drops any stock with a recent big gap before ranking
on momentum. Momentum itself was published in 1993 (Jegadeesh & Titman), so dev may overstate it.
Idea: a winner that climbed steadily is more likely to keep climbing than one carried by a single
event (a takeover bid, an earnings jump) that will not repeat.

Frame is M0509's (so the comparison with its recorded books is like for like): N20 host (F4-screened
point-in-time index members, 20 equal monthly slots), fractional shares at Gotrade real fees, SPY
200-day switch. Rank = return over the last ``window`` (126) sessions. The gap filter removes any name
whose largest absolute one-day move in the last ``gap_window`` (90) sessions exceeded ``gap_pct`` (15)
percent, in either direction, BEFORE ranking. Pure: reads bars dated <= data_date only.

Arms (five):
  GAPFREE        treatment: 126-session winners among gap-free names.
  NOGAP          Control: the same 126-session book with no filter (M0509-W120-B100, trial 1779, is the
                 same book at 120 sessions; the window differs so this control is run, declared).
  GAPFREE-RAND-A / -B   Control: 20 hash draws (seeds 6141, 6142) from the SAME gap-free pool, no
                 opinion on momentum. GAPFREE vs these prices the ranking; the pool restriction alone
                 is separated from stock-picking.
  GAPFREE-NOSW   the treatment never switching to cash: prices what the 200-day switch's opinion
                 costs or earns on this book (the no-opinion arm owed by the lab's dressing rule).
The unfiltered blind draw at this frame is recorded (M0513-W120-RAND-A/B, trials 1997 and 1998) and is
cited, not re-run.
SUCCESS: GAPFREE beats NOGAP and the best gap-free draw by more than 2 points a year funded, beats
total-return SPY, and has a positive 2009-2015 edge.
"""
from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20
from seer_engine.lab.methods.m0091_lottery_avoidance import targets_from_rows
from seer_engine.lab.methods.m0509_keep_band_ladder import (
    MARKET,
    TimeParams,
    TimePrepared,
    choose,
    scored_names,
)
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorParams,
    factor_lookback,
    factor_rows,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 11, 13)
NOSW = replace(N20, trend=None)


@dataclass(frozen=True, slots=True)
class GapParams:
    """``inner`` is the host; ``gap_pct`` 0 turns the filter off; ``mode`` is win or blind."""

    inner: FactorParams
    mode: str = "win"
    seed: int = 0
    window: int = 126
    gap_window: int = 90
    gap_pct: int = 15

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if self.mode not in ("win", "blind"):
            raise ValueError(f"mode must be win or blind, got {self.mode!r}")
        for name in ("seed", "window", "gap_window", "gap_pct"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int) or v < 0:
                raise ValueError(f"{name} must be an int >= 0, got {v!r}")
        if self.window < 2 or self.gap_window < 2:
            raise ValueError("window and gap_window must be >= 2")

    def as_dict(self) -> dict[str, str]:
        out = {
            "mode": self.mode,
            "seed": str(self.seed),
            "window": str(self.window),
            "gap_window": str(self.gap_window),
            "gap_pct": str(self.gap_pct),
        }
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> GapParams:
    if not isinstance(params, GapParams):
        raise TypeError(f"params must be GapParams, got {type(params).__name__}")
    return params


def max_abs_day(history: Mapping[str, History], symbol: str, data_date: date, window: int) -> float | None:
    """Largest absolute one-day simple return over the trailing ``window`` sessions through d.

    None when there are too few bars or a close is non-finite (the name then cannot be vouched
    gap-free and is left out of the filtered pool).
    """
    h = history.get(symbol)
    if h is None:
        return None
    i = h.index_of(data_date)
    if i is None or i < window:
        return None
    closes = h.close[i - window : i + 1]
    with np.errstate(divide="ignore", invalid="ignore"):
        rets = closes[1:] / closes[:-1] - 1.0
    if not np.all(np.isfinite(rets)):
        return None
    return float(np.max(np.abs(rets)))


class GapFreeAllocator:
    """The M0509 index-member book with an optional gap filter applied before the ranking."""

    id = "M0614"

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return max(factor_lookback(p.inner), p.window + 1, p.gap_window + 1)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        fixed = {MARKET}
        if p.inner.trend is not None:
            fixed.add(p.inner.trend[0])
        return tuple(sorted(fixed))

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(
        self,
        prepared: TimePrepared | None,
        history: Mapping[str, History],
        members: AbstractSet[str],
        data_date: date,
        p: GapParams,
    ) -> tuple[Target, ...]:
        if not trend_on(history, data_date, p.inner):
            return ()
        if prepared is None:
            rows = factor_rows(history, members, data_date, p.inner)
        else:
            rows = prepared.factor.rows_on(members, data_date, p.inner)
        syms = sorted(r.symbol for r in rows if r.symbol not in EXCLUDED)
        scores = scored_names(history, syms, data_date, p.window)
        if p.gap_pct > 0:
            cut = p.gap_pct / 100.0
            clean = {}
            for s, v in scores.items():
                m = max_abs_day(history, s, data_date, p.gap_window)
                if m is not None and m <= cut:
                    clean[s] = v
            scores = clean
        tp = TimeParams(p.inner, p.mode, p.seed, 0, p.window)
        return targets_from_rows(choose(rows, scores, frozenset(), tp), tp)  # type: ignore[arg-type]

    def targets(
        self,
        history: Mapping[str, History],
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        return self._run(None, history, members, data_date, _check(params))

    def prepare(self, history: Mapping[str, History]) -> TimePrepared:
        return TimePrepared(history, prepare_factor(history))

    def targets_prepared(
        self,
        prepared: Any,
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        if not isinstance(prepared, TimePrepared):
            raise TypeError(f"prepared must be TimePrepared, got {type(prepared).__name__}")
        return self._run(prepared, prepared.history, members, data_date, _check(params))


GAPFREE = GapFreeAllocator()


def _v(suffix: str, params: GapParams, rationale: str) -> Candidate:
    return Candidate(
        id=f"M0614-{suffix}",
        family="M0614",
        rules=MONTHLY_HOLD_FRAC_GOTRADE,
        allocator=GAPFREE,
        params=params,
        rationale=rationale,
        added=ADDED,
        owner_inputs=(),
    )


METHOD = Method(
    id="M0614",
    name=(
        "Gap-free momentum: 6-month winners among members that had no single-day jump "
        "above 15% in the last 90 sessions, behind the 200-day switch"
    ),
    family="stock-gap-free-momentum",
    source_kind="blog",
    source_ref="Clenow, Stocks on the Move (2015): drop any stock with a recent big gap before ranking on momentum",
    hypothesis=(
        "Rank F4-screened point-in-time index members on 126-session return, but skip any name whose "
        "largest absolute one-day move in the last 90 sessions exceeded 15 percent, then hold the top "
        "20 equal-weight behind the SPY 200-day switch, monthly, fractional shares at Gotrade's real "
        "fees (M0509's frame). A winner that climbed without a shock should keep climbing more than "
        "one carried by a single event. Momentum was published in 1993 and Clenow's filter in 2015, "
        "so dev may overstate both. Arms: GAPFREE (treatment); NOGAP (Control: the same 126-session "
        "book unfiltered; M0509-W120-B100, trial 1779, is the 120-session neighbour, so this is run); "
        "GAPFREE-RAND-A/B (Control: hash draws of 20 from the gap-free pool, seeds 6141/6142, which "
        "separate the pool restriction from momentum ranking); GAPFREE-NOSW (the treatment never "
        "switching to cash, the no-opinion arm). The unfiltered blind draw is recorded as "
        "M0513-W120-RAND-A/B (trials 1997, 1998) and is cited, not re-run. The nearest filter "
        "cousins M0526 (filter beat its coin flips but lost to SPY) and M0438 (jump sort no better "
        "than random picks) are why the random draws from the filtered pool are owed. SUCCESS: "
        "GAPFREE beats NOGAP and the best gap-free draw by more than 2 points a year funded, beats "
        "total-return SPY, and has a positive 2009-2015 edge."
    ),
    expected_failure=(
        "The filter removes the very stocks momentum feeds on (big winners usually gap), so GAPFREE "
        "falls inside NOGAP's band or below it, and the gap-free blind draws match it: the pool "
        "restriction, not the ranking, is doing the work. Nothing beats SPY in 2009-2015. A strong "
        "dev result from a published anomaly is likely to fade after 2015."
    ),
    candidates=(
        _v("GAPFREE", GapParams(N20), "126-session winners among names with no >15% day in 90 sessions"),
        _v("NOGAP", GapParams(N20, gap_pct=0), "Control: same 126-session winners book, no gap filter"),
        _v("GAPFREE-RAND-A", GapParams(N20, "blind", 6141), "Control: hash draw of 20 from the gap-free pool, seed 6141"),
        _v("GAPFREE-RAND-B", GapParams(N20, "blind", 6142), "Control: hash draw of 20 from the gap-free pool, seed 6142"),
        _v("GAPFREE-NOSW", GapParams(NOSW), "the treatment never switching to cash: the no-opinion arm for the 200-day switch"),
    ),
    seen_keys=("concept:gap-free-momentum-filter",),
)

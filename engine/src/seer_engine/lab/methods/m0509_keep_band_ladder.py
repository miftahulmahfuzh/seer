"""M0509 — Break the keep-band lead: a band ladder on 40- and 120-session winners with blind draws.

Source: variation on M0506, whose BAND70 arm (60-session winners, keep band 70%) was the closest
call of that method (DSR just under the 0.90 bar). Short-horizon return momentum was published in
1993 (Jegadeesh & Titman), so dev may overstate it. This method tries to disprove the lead: does the
band's gain survive a different score window (40 and 120 sessions) and a looser band (85%, and 100%,
which means a holding is sold only when it drops out of the scored pool)? Frame is M0506's: N20 host,
20 equal monthly slots, fractional shares at Gotrade real fees, SPY 200-day switch.

Arms (six): W40-B85, W40-B100, W120-B70, W120-B100 (treatments) and R3, R4 (fresh blind draws, seeds
509 and 510, no band, behind the switch). Together with M0506's recorded R1 and R2 the draw band has
four draws. M0506-R1-NOSW (always invested, no opinion) is recorded and is the no-opinion comparison;
the unbanded 60-session book is M0503-RET60; neither is repeated. No arm mirrors another, so no
third arm is owed.
SUCCESS: a treatment beats the best of the four draws by more than 2 points a year funded, has a
positive 2009-2015 edge vs SPY, and the result holds at both windows (not one lucky window).
"""
from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field, replace
from datetime import date
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20
from seer_engine.lab.methods.m0091_lottery_avoidance import targets_from_rows
from seer_engine.lab.methods.m0293_calm_filter_on_a_host import draw
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorParams,
    FactorPrepared,
    FactorRow,
    factor_lookback,
    factor_rows,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 11, 7)
MODES = ("win", "lose", "blind")
MARKET = "SPY"
NEED = 61  # host-era default; arms below set their own window

NOSW = replace(N20, trend=None)


@dataclass(frozen=True, slots=True)
class TimeParams:
    """``inner`` is the host's screen, switch, book size and weighting; ``mode`` is the ranking."""

    inner: FactorParams
    mode: str = "win"
    seed: int = 0
    keep_pct: int = 0
    window: int = 60

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if self.mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {self.mode!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError(f"seed must be an int, got {type(self.seed).__name__}")
        if isinstance(self.keep_pct, bool) or not isinstance(self.keep_pct, int):
            raise TypeError(f"keep_pct must be an int, got {type(self.keep_pct).__name__}")
        if not 0 <= self.keep_pct <= 100:
            raise ValueError(f"keep_pct must be in [0, 100], got {self.keep_pct}")
        if isinstance(self.window, bool) or not isinstance(self.window, int) or self.window < 2:
            raise ValueError(f"window must be an int >= 2, got {self.window!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"mode": self.mode, "seed": str(self.seed), "keep_pct": str(self.keep_pct), "window": str(self.window)}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> TimeParams:
    if not isinstance(params, TimeParams):
        raise TypeError(f"params must be TimeParams, got {type(params).__name__}")
    return params


def scored_names(history: Mapping[str, History], symbols: list[str], data_date: date, window: int
                 ) -> dict[str, tuple[float, float]]:
    """(0.0, return over the last ``window`` sessions ending data_date); only bars <= data_date."""
    out: dict[str, tuple[float, float]] = {}
    for s in symbols:
        h = history.get(s)
        if h is None:
            continue
        i = h.index_of(data_date)
        if i is None or i < window:
            continue
        c, c0 = h.close[i], h.close[i - window]
        if not (np.isfinite(c) and np.isfinite(c0) and c > 0.0 and c0 > 0.0):
            continue
        out[s] = (0.0, float(c / c0 - 1.0))
    return out


def choose(rows: list[FactorRow], score: dict[str, tuple[float, float]], held: frozenset[str],
           params: TimeParams) -> list[FactorRow]:
    """Rank the scored pool, keep holdings under the band's rank fraction, fill from the top."""
    pool = [r for r in rows if r.symbol not in EXCLUDED and r.symbol in score]
    if params.mode == "win":
        key = {r.symbol: (-score[r.symbol][1], 0.0) for r in pool}
    elif params.mode == "lose":
        key = {r.symbol: (score[r.symbol][1], 0.0) for r in pool}
    else:
        key = {r.symbol: (float(draw(params.seed, r.symbol)), 0.0) for r in pool}
    pool.sort(key=lambda r: (key[r.symbol], r.symbol))
    top = params.inner.top
    if params.keep_pct == 0 or not pool:
        return pool[:top]
    frac = {r.symbol: k / len(pool) for k, r in enumerate(pool)}
    cut = params.keep_pct / 100.0
    kept = [r for r in pool if r.symbol in held and frac[r.symbol] < cut][:top]
    chosen = {r.symbol for r in kept}
    for r in pool:
        if len(kept) >= top:
            break
        if r.symbol not in chosen:
            kept.append(r)
    return kept


@dataclass
class TimePrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)
    cache: dict[tuple[date, int], dict[str, tuple[float, float]]] = field(default_factory=dict, repr=False)


class BandLadderAllocator:
    """The lab's index-member book ranked on a window return, with a keep band."""

    id = "M0509"

    def lookback(self, params: Any) -> int:
        return max(factor_lookback(_check(params).inner), _check(params).window + 1)

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

    def _run(self, prepared: TimePrepared | None, history: Mapping[str, History],
             members: AbstractSet[str], data_date: date, held: frozenset[str], p: TimeParams) -> tuple[Target, ...]:
        if not trend_on(history, data_date, p.inner):
            return ()
        if prepared is None:
            rows = factor_rows(history, members, data_date, p.inner)
        else:
            rows = prepared.factor.rows_on(members, data_date, p.inner)
        syms = sorted(r.symbol for r in rows if r.symbol not in EXCLUDED)
        if prepared is None:
            scores = scored_names(history, syms, data_date, p.window)
        else:
            scores = prepared.cache.get((data_date, p.window)) or scored_names(
                history, syms, data_date, p.window)
            prepared.cache[(data_date, p.window)] = scores
        return targets_from_rows(choose(rows, scores, held, p), p)  # type: ignore[arg-type]

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self._run(None, history, members, data_date, held, _check(params))

    def prepare(self, history: Mapping[str, History]) -> TimePrepared:
        return TimePrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, TimePrepared):
            raise TypeError(f"prepared must be TimePrepared, got {type(prepared).__name__}")
        return self._run(prepared, prepared.history, members, data_date, held, _check(params))


LADDER = BandLadderAllocator()


def _v(suffix: str, params: TimeParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0509-{suffix}", family="M0509",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=LADDER, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0509",
    name="Break the keep-band lead: band ladder on 40- and 120-session winners with fresh blind draws",
    family="stock-momentum-short-window",
    source_kind="variation",
    source_ref="M0506-BAND70: the closest call of the keep-band method; Jegadeesh & Titman (1993)",
    parent_id="M0506",
    hypothesis=(
        "M0506's BAND70 (20 best 60-session returns among F4-screened point-in-time index members, "
        "keep band 70%, monthly, fractional, Gotrade real fees, SPY 200-day switch) came within a "
        "hair of the DSR bar. Try to disprove it by moving the two dials it never moved: the score "
        "window (40 and 120 sessions instead of 60) and the band (85% and 100%, where 100% sells "
        "only when a name leaves the scored pool). Arms: W40-B85, W40-B100, W120-B70, W120-B100 and "
        "two fresh blind draws R3, R4 (seeds 509, 510, no band, switch on); with M0506's recorded R1 "
        "and R2 the draw band has four draws. M0506-R1-NOSW is the recorded always-invested "
        "comparison and M0503-RET60 the unbanded one. Judged first on 2009-2015. Short-horizon "
        "momentum was published in 1993; expect fading. SUCCESS: a treatment beats the best draw by "
        "more than 2 points a year funded, with a positive 2009-2015 edge vs SPY, and the lead shows "
        "at both windows. Predictions, written now: the lead is one window's luck, so at least one "
        "window's arms fall inside the draw band, and nothing beats SPY in 2009-2015."
    ),
    expected_failure=(
        "The M0506 lead was a single-window draw: the 40- and 120-session arms land inside the "
        "blind-draw band, or the 100% band sits in stale losers. A strong dev result from a "
        "published anomaly is likely to fade after 2015."
    ),
    candidates=(
        _v("W40-B85", TimeParams(N20, "win", 0, 85, 40), "40-session winners, keep band 85%"),
        _v("W40-B100", TimeParams(N20, "win", 0, 100, 40), "40-session winners, sell only on leaving the pool"),
        _v("W120-B70", TimeParams(N20, "win", 0, 70, 120), "120-session winners, keep band 70% (parent's band)"),
        _v("W120-B100", TimeParams(N20, "win", 0, 100, 120), "120-session winners, sell only on leaving the pool"),
        _v("R3", TimeParams(N20, "blind", 509), "Control: hash draw of 20, seed 509, behind the switch"),
        _v("R4", TimeParams(N20, "blind", 510), "Control: hash draw of 20, seed 510, widens the draw band"),
    ),
    seen_keys=(
        "concept:keep-band-ladder-window-sweep",
    ),
)

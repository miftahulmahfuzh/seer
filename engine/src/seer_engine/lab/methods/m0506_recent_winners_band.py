"""M0506 — Recent winners with a keep band: does cutting the monthly churn lift the 60-session return book?

Source: variation on M0506, whose plain 60-session return arm (RET60) earned the best funded return of
that method's six arms while paying about 1,960 trades against the blind draws' 340. Short-horizon
return momentum is well published (Jegadeesh & Titman 1993), so the dev window is exposed to the
crowd and an edge may fade; say so. Frame is M0506's: N20 host, 20 equal monthly slots, fractional
shares at Gotrade real fees, SPY 200-day switch. The new dial is a keep band: a holding stays while
its rank fraction among the screened, scored pool is under keep_pct, and the rest of the 20 slots
are filled from the top of the ranking. Score is M0506's 60-session return (its scored_names).

Arms (six): BAND40 and BAND70 (treatments: keep band 40% and 70%), LOSE40 (mirror: the 60-session
losers with the same 40% band), R1 and R2 (blind draws, seeds 507, 508, no band, behind the switch)
and R1-NOSW (always invested with no opinion: prices the switch and acting). The unbanded winners
book is M0506-RET60, already recorded; it is the comparison, not a new arm.
SUCCESS: BAND40 beats the better of R1/R2 by more than 2 points a year funded, BAND40 beats M0506-RET60
funded, LOSE40 loses to R1, positive 2009-2015 edge vs SPY, turnover falls by at least a third.
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
from seer_engine.lab.methods.m0503_close_location import scored_names
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
NEED = 61  # M0503 scoring window

NOSW = replace(N20, trend=None)


@dataclass(frozen=True, slots=True)
class TimeParams:
    """``inner`` is the host's screen, switch, book size and weighting; ``mode`` is the ranking."""

    inner: FactorParams
    mode: str = "win"
    seed: int = 0
    keep_pct: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if self.mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {self.mode!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError(f"seed must be an int, got {type(self.seed).__name__}")
        if isinstance(self.keep_pct, bool) or not isinstance(self.keep_pct, int):
            raise TypeError(f"keep_pct must be an int, got {type(self.keep_pct).__name__}")
        if not 0 <= self.keep_pct < 100:
            raise ValueError(f"keep_pct must be in [0, 100), got {self.keep_pct}")

    def as_dict(self) -> dict[str, str]:
        out = {"mode": self.mode, "seed": str(self.seed), "keep_pct": str(self.keep_pct)}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> TimeParams:
    if not isinstance(params, TimeParams):
        raise TypeError(f"params must be TimeParams, got {type(params).__name__}")
    return params


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
    cache: dict[date, dict[str, tuple[float, float]]] = field(default_factory=dict, repr=False)


class RecentWinnersBandAllocator:
    """The lab's index-member book ranked on 60-session return, with a keep band."""

    id = "M0506"

    def lookback(self, params: Any) -> int:
        return max(factor_lookback(_check(params).inner), NEED)

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
            scores = scored_names(history, syms, data_date)
        else:
            scores = prepared.cache.get(data_date) or scored_names(history, syms, data_date)
            prepared.cache[data_date] = scores
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


BANDBOOK = RecentWinnersBandAllocator()


def _v(suffix: str, params: TimeParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0506-{suffix}", family="M0506",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=BANDBOOK, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0506",
    name="Recent winners with a keep band: does cutting the monthly churn lift the three-month winners book?",
    family="stock-momentum-short-window",
    source_kind="variation",
    source_ref="M0503-RET60: the unbanded 60-session winners arm; Jegadeesh & Titman (1993)",
    parent_id="M0503",
    hypothesis=(
        "In M0503 the plain 60-session return arm (M0503-RET60) earned the best funded return of that "
        "method's arms while trading about 1,960 times against the blind draws' 340. Short-horizon "
        "return momentum is well published (Jegadeesh & Titman 1993), so dev may overstate it and an "
        "edge may fade. Test a keep band: hold the 20 best 60-session returns among F4-screened "
        "point-in-time index members, monthly, fractional, Gotrade real fees, behind SPY's 200-day "
        "switch, but a holding stays while its rank fraction is under 40% (BAND40) or 70% (BAND70). "
        "Arms: BAND40, BAND70, LOSE40 (mirror, the losers with the same band), R1 and R2 (blind draws, "
        "seeds 507, 508, no band, switch on) and R1-NOSW (always invested, no opinion). The unbanded "
        "winners book is recorded as M0503-RET60 and is the comparison. SUCCESS: BAND40 beats the "
        "better of R1/R2 by more than 2 points a year funded, beats M0503-RET60 funded, LOSE40 loses "
        "to R1, a positive 2009-2015 edge vs SPY, and turnover falls by at least a third. "
        "Predictions, written now: the band lowers turnover but does not raise the funded return "
        "(the churn was not the cost) and BAND40 does not beat SPY in 2009-2015."
    ),
    expected_failure=(
        "The band delays selling losers in a book that works through monthly refresh, so BAND40 "
        "trails M0503-RET60 and the blind draws; or it merely recovers the cost of churn and lands "
        "between them. Dev results for published momentum are likely overstated either way."
    ),
    candidates=(
        _v("BAND40", TimeParams(N20, "win", 0, 40), "60-session winners, keep band 40%"),
        _v("BAND70", TimeParams(N20, "win", 0, 70), "60-session winners, keep band 70%"),
        _v("LOSE40", TimeParams(N20, "lose", 0, 40), "Mirror: 60-session losers, keep band 40%"),
        _v("R1", TimeParams(N20, "blind", 507), "Control: hash draw of 20, seed 507, behind the switch"),
        _v("R2", TimeParams(N20, "blind", 508), "Control: hash draw of 20, seed 508, measures draw noise"),
        _v("R1-NOSW", TimeParams(NOSW, "blind", 507), "Always invested, no opinion: prices acting on either"),
    ),
    seen_keys=(
        "concept:short-window-momentum-keep-band",
    ),
)

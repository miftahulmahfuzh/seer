"""M0505 — Steady risk versus erratic risk: index members ranked on how much their own volatility moves.

Source: Baltussen, Van Bekkum & Van der Grient (2018), "Unknown unknowns: uncertainty about risk and
stock returns" (JFQA): stocks whose realised volatility is itself most variable (vol-of-vol) earn lower
subsequent returns. Published 2018, so the dev window (ends 2015) cannot have been crowded by it.
Score = the standard deviation, over the last 252 sessions, of 21-session realised volatility (the
volatility of each non-overlapping-start block, sampled every 21 sessions, 12 blocks), divided by
their mean so the score is vol-of-vol per unit of risk, not a restated volatility level. Frame is
M0505's: N20 host, 20 equal monthly slots, fractional shares at Gotrade real fees, SPY 200-day switch.
Names short of 253 closes, with a gap or a non-positive price are unscored in every arm alike.

Arms (six): STEADY (treatment: lowest vol-of-vol, the paper's long leg), ERRATIC (mirror), LEVEL
(control: lowest plain 252-session volatility, because steady risk is mostly calm risk, so the
score adds something only if it beats that), R1 and R2 (blind draws, seeds 505, 506, behind the
switch) and R1-NOSW (always invested with no opinion: prices the switch and acting).
SUCCESS: STEADY beats the better of R1/R2 by more than 2 points a year funded, ERRATIC loses to R1,
STEADY beats LEVEL, positive 2009-2015 edge vs SPY.
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
MODES = ("steady", "erratic", "level", "blind")
NEED = 253  # closes needed: 252 returns
BLOCK = 21
MARKET = "SPY"

NOSW = replace(N20, trend=None)


@dataclass(frozen=True, slots=True)
class TimeParams:
    """``inner`` is the host's screen, switch, book size and weighting; ``mode`` is the ranking."""

    inner: FactorParams
    mode: str = "steady"
    seed: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if self.mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {self.mode!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError(f"seed must be an int, got {type(self.seed).__name__}")

    def as_dict(self) -> dict[str, str]:
        out = {"mode": self.mode, "seed": str(self.seed), "need": str(NEED)}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> TimeParams:
    if not isinstance(params, TimeParams):
        raise TypeError(f"params must be TimeParams, got {type(params).__name__}")
    return params


def scored_names(history: Mapping[str, History], symbols: list[str], data_date: date
                 ) -> dict[str, tuple[float, float]]:
    """(vol-of-vol per unit of volatility, plain 252-session volatility), both daily-return based.

    Twelve 21-session blocks of daily returns each give one realised volatility; the first score is
    their standard deviation over their mean. Unscored on a gap or a non-positive price."""
    out: dict[str, tuple[float, float]] = {}
    for s in symbols:
        h = history.get(s)
        if h is None:
            continue
        i = h.index_of(data_date)
        if i is None or i < NEED - 1:
            continue
        c = h.close[i - NEED + 1 : i + 1]
        if not (np.all(np.isfinite(c)) and np.all(c > 0.0)):
            continue
        r = c[1:] / c[:-1] - 1.0
        blocks = np.std(r.reshape(-1, BLOCK), axis=1, ddof=1)
        mean = float(np.mean(blocks))
        if mean <= 0.0:
            continue
        out[s] = (float(np.std(blocks, ddof=1)) / mean, float(np.std(r, ddof=1)))
    return out


def choose(rows: list[FactorRow], score: dict[str, tuple[float, float]], params: TimeParams
           ) -> list[FactorRow]:
    pool = [r for r in rows if r.symbol not in EXCLUDED and r.symbol in score]
    if params.mode == "steady":
        key = {r.symbol: (score[r.symbol][0], 0.0) for r in pool}
    elif params.mode == "erratic":
        key = {r.symbol: (-score[r.symbol][0], 0.0) for r in pool}
    elif params.mode == "level":
        key = {r.symbol: (score[r.symbol][1], 0.0) for r in pool}
    else:
        key = {r.symbol: (float(draw(params.seed, r.symbol)), 0.0) for r in pool}
    pool.sort(key=lambda r: (key[r.symbol], r.symbol))
    return pool[: params.inner.top]


@dataclass
class TimePrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)
    cache: dict[date, dict[str, tuple[float, float]]] = field(default_factory=dict, repr=False)


class VolOfVolAllocator:
    """The lab's index-member book ranked on how much their own volatility moves."""

    id = "M0505"

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
             members: AbstractSet[str], data_date: date, p: TimeParams) -> tuple[Target, ...]:
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
        return targets_from_rows(choose(rows, scores, p), p)  # type: ignore[arg-type]

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self._run(None, history, members, data_date, _check(params))

    def prepare(self, history: Mapping[str, History]) -> TimePrepared:
        return TimePrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, TimePrepared):
            raise TypeError(f"prepared must be TimePrepared, got {type(prepared).__name__}")
        return self._run(prepared, prepared.history, members, data_date, _check(params))


VOLOFVOL = VolOfVolAllocator()


def _v(suffix: str, params: TimeParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0505-{suffix}", family="M0505",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=VOLOFVOL, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0505",
    name="Steady risk versus erratic risk: stocks whose own volatility barely moves",
    family="stock-vol-of-vol",
    source_kind="paper",
    source_ref="Baltussen, Van Bekkum & Van der Grient (2018), Unknown unknowns: uncertainty about risk and stock returns, JFQA",
    parent_id=None,
    hypothesis=(
        "Published 2018 (so the dev window ends before the crowd could trade it): stocks whose "
        "realised volatility is itself most variable earn lower subsequent returns, because "
        "uncertainty about risk is priced. Score = standard deviation across twelve 21-session "
        "blocks of the last 252 sessions of each block's realised volatility, divided by their "
        "mean. Hold the 20 steadiest F4-screened point-in-time index members monthly in equal "
        "fractional slots at Gotrade real fees behind SPY's 200-day switch. Arms: STEADY, ERRATIC "
        "(mirror), LEVEL (control: lowest plain 252-session volatility, since steady risk is mostly "
        "calm risk and the low-volatility books of the lab already exist), R1 and R2 (blind draws, "
        "seeds 505, 506, switch on) and R1-NOSW (always invested, no opinion: prices the switch and "
        "acting). SUCCESS: STEADY beats the better of R1/R2 by more than 2 points a year funded, "
        "ERRATIC loses to R1, STEADY beats LEVEL, positive 2009-2015 edge vs SPY. Predictions, "
        "written now: STEADY lands within 2 points a year of LEVEL and neither beats SPY in "
        "2009-2015 (the low-risk books lag in rising markets)."
    ),
    expected_failure=(
        "The scaled score is a stock's calmness or its ordinary-news cadence renamed: STEADY equals "
        "LEVEL, both trail SPY in the 2009-2015 rise, and the blind draws match them, as the lab's "
        "other low-volatility books did. Twelve blocks per name is a noisy standard deviation."
    ),
    candidates=(
        _v("STEADY", TimeParams(N20, "steady"), "Lowest vol-of-vol, behind the switch"),
        _v("ERRATIC", TimeParams(N20, "erratic"), "Highest vol-of-vol: the mirror"),
        _v("LEVEL", TimeParams(N20, "level"), "Control: lowest plain 252-session volatility"),
        _v("R1", TimeParams(N20, "blind", 505), "Control: hash draw of 20, seed 505, behind the switch"),
        _v("R2", TimeParams(N20, "blind", 506), "Control: hash draw of 20, seed 506, measures draw noise"),
        _v("R1-NOSW", TimeParams(NOSW, "blind", 505), "Always invested, no opinion: prices acting on either"),
    ),
    seen_keys=(
        "concept:volatility-of-volatility",
    ),
)

"""M0463 — Steady attention: coefficient of variation of 60-session dollar volume.

Source: knowledge. Volume-stability and attention-shock ideas (Gervais-Kaniel-Mingelgrin 2001
on volume shocks, Amihud illiquidity work) are old and widely traded, so a dev edge may
already be gone. No literature exact match; `lab seen` holds no coefficient-of-variation key.

The frame is the sibling M0461's: point-in-time members, the F4 screen, 20 equal slots (about a tenth of
the screened pool), monthly, fractional shares at Gotrade's real fees, SPY's 200-day switch on
four arms. The key is std over mean of close x volume across the last 60 sessions. Names with a
missing bar or a non-positive price or volume are not scored, in every arm alike.

Arms (six): STEADY holds the 20 lowest, ERRATIC the 20 highest (the mirror), R1 and R2 draw 20
of the same pool by hash, STEADY-NOSW and R1-NOSW have no switch. R1-NOSW is the always-invested
arm with no opinion in it.
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

ADDED = date(2026, 11, 1)
MODES = ("steady", "erratic", "blind")
WIN = 60  # sessions in the dollar-volume window
MARKET = "SPY"

NOSW = replace(N20, trend=None)


@dataclass(frozen=True, slots=True)
class SteadyParams:
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
        out = {"mode": self.mode, "seed": str(self.seed), "win": str(WIN)}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> SteadyParams:
    if not isinstance(params, SteadyParams):
        raise TypeError(f"params must be SteadyParams, got {type(params).__name__}")
    return params


def scored_names(history: Mapping[str, History], symbols: list[str], data_date: date
                 ) -> dict[str, float]:
    """Coefficient of variation (std over mean) of daily dollar volume over the last WIN sessions.

    Needs WIN bars ending on data_date. Names with a missing bar, or a non-positive price or
    volume anywhere in the window, are not scored, in every arm alike."""
    out: dict[str, float] = {}
    for s in symbols:
        h = history.get(s)
        if h is None:
            continue
        i = h.index_of(data_date)
        if i is None or i < WIN - 1:
            continue
        c = h.close[i - WIN + 1 : i + 1]
        v = h.volume[i - WIN + 1 : i + 1]
        if not (np.all(np.isfinite(c)) and np.all(c > 0.0)
                and np.all(np.isfinite(v)) and np.all(v > 0.0)):
            continue
        dv = c * v
        out[s] = float(np.std(dv) / np.mean(dv))
    return out


def choose(rows: list[FactorRow], score: dict[str, float], params: SteadyParams) -> list[FactorRow]:
    pool = [r for r in rows if r.symbol not in EXCLUDED and r.symbol in score]
    if params.mode == "steady":
        key = {r.symbol: score[r.symbol] for r in pool}
    elif params.mode == "erratic":
        key = {r.symbol: -score[r.symbol] for r in pool}
    else:
        key = {r.symbol: float(draw(params.seed, r.symbol)) for r in pool}
    pool.sort(key=lambda r: (key[r.symbol], r.symbol))
    return pool[: params.inner.top]

@dataclass
class SteadyPrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)
    cache: dict[date, dict[str, float]] = field(default_factory=dict, repr=False)


class SteadyAllocator:
    """The lab's index-member book ranked on the steadiness of its dollar volume."""

    id = "M0463"

    def lookback(self, params: Any) -> int:
        return max(factor_lookback(_check(params).inner), WIN)

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

    def _run(self, prepared: SteadyPrepared | None, history: Mapping[str, History],
             members: AbstractSet[str], data_date: date, p: SteadyParams) -> tuple[Target, ...]:
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

    def prepare(self, history: Mapping[str, History]) -> SteadyPrepared:
        return SteadyPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, SteadyPrepared):
            raise TypeError(f"prepared must be SteadyPrepared, got {type(prepared).__name__}")
        return self._run(prepared, prepared.history, members, data_date, _check(params))


STEADY = SteadyAllocator()


def _v(suffix: str, params: SteadyParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0463-{suffix}", family="M0463",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=STEADY, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0463",
    name="Steady attention: stocks whose daily dollar volume is the most stable, one tail against the mirror",
    family="stock-volume-stability",
    source_kind="knowledge",
    source_ref="",
    parent_id=None,
    hypothesis=(
        "Rank screened point-in-time index members by the coefficient of variation of daily "
        "dollar volume over 60 sessions. The steadiest tail (no spikes, orderly holders) is "
        "held against the erratic mirror tail (spike-driven crowding). 20 equal slots, about a "
        "tenth of the pool, monthly, fractional shares at Gotrade's real fees (a book of 20 "
        "needs fractions at a 20M IDR start). Volume-shock literature dates from 2001, so an "
        "edge may be traded away. Arms: STEADY, ERRATIC, R1 and R2 (hash draws of 20 from the "
        "same pool, the blind pair), STEADY-NOSW and R1-NOSW (no SPY switch; R1-NOSW is always "
        "invested with no opinion, the third arm that prices what acting costs). The other four "
        "sit behind SPY's 200-day switch. SUCCESS: STEADY beats the better of R1 and R2 by more "
        "than the blind pair's spread plus 2 points a year, ERRATIC loses to it, STEADY beats "
        "SPY total return with max drawdown at or under the lab's bar and a positive 2009-2015 "
        "edge vs SPY. Predictions, written now: STEADY and ERRATIC differ by under 2 points a "
        "year; neither beats the blind draw; all trail SPY in 2009-2015. Steadiness is mostly a "
        "size proxy (big names trade steadily), so STEADY may just be a large-cap tilt."
    ),
    expected_failure=(
        "The steady tail is a large-company tilt and the erratic tail a small or news-driven "
        "one; behind the switch the market's timing, not the sort, does the work (M0412, M0425, "
        "M0461). The no-switch arms fall past 35% in 2008 and 2000-02."
    ),
    candidates=(
        _v("STEADY", SteadyParams(N20, "steady"),
           "Lowest dollar-volume variation among screened members, behind the switch"),
        _v("ERRATIC", SteadyParams(N20, "erratic"),
           "Highest variation: the mirror tail"),
        _v("R1", SteadyParams(N20, "blind", 463),
           "Control: hash draw of 20 from the same pool, seed 463, behind the switch"),
        _v("R2", SteadyParams(N20, "blind", 464),
           "Control: hash draw of 20 from the same pool, seed 464, behind the switch"),
        _v("STEADY-NOSW", SteadyParams(NOSW, "steady"),
           "No-switch twin of STEADY: always invested, prices the switch's habit"),
        _v("R1-NOSW", SteadyParams(NOSW, "blind", 463),
           "Always invested, no opinion: blind draw with no switch, prices acting on either"),
    ),
    seen_keys=(
        "concept:dollar-volume-cv-60d",
    ),
)

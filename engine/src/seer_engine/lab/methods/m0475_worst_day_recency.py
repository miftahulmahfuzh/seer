"""M0475 — Old shocks versus fresh shocks: how long ago a stock's single worst day of the year fell.

Source: knowledge (the daily-return-ordering literature, Cakici et al. 2026: when in the window a
return happens carries information). Published 2026, so the dev window (ends 2015) cannot have been
crowded by it. Rank F4-screened point-in-time index members by sessions since the worst one-day
return of the last 250 sessions. A stale shock (long ago) may mean the bad news is digested; a fresh
one may mean it is still being repriced. Frame is M0469's: N20 host, 20 equal monthly slots,
fractional shares at Gotrade real fees, SPY 200-day switch. Needs 251 closes (250 returns); names
short of that, with a gap or a non-positive price are unscored in every arm alike. Ties on age break
toward the older shock by argmin's first hit, then the symbol.

Arms (six): OLD (treatment: oldest worst day), FRESH (mirror), LEVEL (control: the shallowest
worst day, the level sort that M0473 proposed, so age adds something only if it beats it), R1 and
R2 (blind draws, seeds 475 and 476, behind the switch, so the draw noise is measured) and R1-NOSW
(no switch: always invested with no opinion, it prices the switch and acting).
SUCCESS: OLD beats the better of R1/R2 by more than 2 points a year funded, FRESH loses to R1, OLD
beats LEVEL, positive 2009-2015 edge vs SPY.
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
MODES = ("old", "fresh", "level", "blind")
NEED = 251  # closes needed: 250 daily returns
MARKET = "SPY"

NOSW = replace(N20, trend=None)


@dataclass(frozen=True, slots=True)
class TimeParams:
    """``inner`` is the host's screen, switch, book size and weighting; ``mode`` is the ranking."""

    inner: FactorParams
    mode: str = "old"
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
    """(sessions since the worst one-day return of the last 250, that worst return).

    Needs NEED closes ending on data_date; names with a missing bar or a non-positive price in
    that span are not scored. Age 0 means the worst day was today."""
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
        k = int(np.argmin(r))
        out[s] = (float(len(r) - 1 - k), float(r[k]))
    return out


def choose(rows: list[FactorRow], score: dict[str, tuple[float, float]], params: TimeParams
           ) -> list[FactorRow]:
    pool = [r for r in rows if r.symbol not in EXCLUDED and r.symbol in score]
    if params.mode == "old":
        key = {r.symbol: (-score[r.symbol][0], 0.0) for r in pool}
    elif params.mode == "fresh":
        key = {r.symbol: (score[r.symbol][0], 0.0) for r in pool}
    elif params.mode == "level":
        key = {r.symbol: (score[r.symbol][1] * -1.0, 0.0) for r in pool}
    else:
        key = {r.symbol: (float(draw(params.seed, r.symbol)), 0.0) for r in pool}
    pool.sort(key=lambda r: (key[r.symbol], r.symbol))
    return pool[: params.inner.top]


@dataclass
class TimePrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)
    cache: dict[date, dict[str, tuple[float, float]]] = field(default_factory=dict, repr=False)


class WorstDayAllocator:
    """The lab's index-member book ranked on how long ago the year's worst day fell."""

    id = "M0475"

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


WORSTDAY = WorstDayAllocator()


def _v(suffix: str, params: TimeParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0475-{suffix}", family="M0475",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=WORSTDAY, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0475",
    name="Old shocks versus fresh shocks: stocks whose worst one-day fall of the last year is long behind them",
    family="stock-worst-day-recency",
    source_kind="knowledge",
    source_ref="",
    parent_id=None,
    hypothesis=(
        "When the worst day falls inside the year carries information (daily-return ordering "
        "literature, Cakici et al., published 2026). A stale shock may mean bad news is digested; a "
        "fresh one may mean it is still being repriced. Rank F4-screened point-in-time index members "
        "by sessions since the worst one-day return of the last 250; hold the 20 with the oldest worst "
        "day monthly in equal fractional slots at Gotrade real fees behind SPY's 200-day switch. Arms: "
        "OLD, FRESH (mirror), LEVEL (control: shallowest worst day, the M0473 level sort), R1 and R2 "
        "(blind draws, seeds 475, 476, switch on), and R1-NOSW (always invested, no opinion: prices "
        "the switch and acting). SUCCESS: OLD beats the better of R1/R2 by more "
        "than 2 points a year funded, FRESH loses to R1, OLD beats LEVEL, positive 2009-2015 edge vs "
        "SPY. Predictions, written now: OLD and LEVEL land within 2 points a year of each other, "
        "neither beats SPY in 2009-2015, FRESH trails R1."
    ),
    expected_failure=(
        "Staleness restates a calm year or distance from the low, so the book is a volatility "
        "screen renamed: OLD may equal LEVEL, and the random draws behind the same switch may match "
        "it, as in M0466 and M0469. The F4 screen and the switch likely carry whatever edge there is."
    ),
    candidates=(
        _v("OLD", TimeParams(N20, "old"), "Oldest worst day of the year, behind the switch"),
        _v("FRESH", TimeParams(N20, "fresh"), "Freshest worst day: the mirror"),
        _v("LEVEL", TimeParams(N20, "level"), "Control: shallowest worst day, behind the switch"),
        _v("R1", TimeParams(N20, "blind", 475), "Control: hash draw of 20, seed 475, behind the switch"),
        _v("R2", TimeParams(N20, "blind", 476), "Control: hash draw of 20, seed 476, measures draw noise"),
        _v("R1-NOSW", TimeParams(NOSW, "blind", 475), "Always invested, no opinion: prices acting on either"),
    ),
    seen_keys=(
        "concept:worst-day-recency",
    ),
)

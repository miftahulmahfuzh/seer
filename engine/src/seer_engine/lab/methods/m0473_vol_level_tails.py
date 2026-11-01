"""M0473 — The risk level on its own: the calmest and the wildest tenth of index members, against random draws.

Variation of M0468. That run asked whether *changes* in a stock's risk add anything beyond its risk
level, and found little, but its random controls were single draws, so the chance spread was not
measured. This one holds the level itself. Each month every F4-screened index member is scored on the
standard deviation of its last 250 daily returns. LOW holds the 30 lowest, HIGH the 30 highest (about a
tenth of the scored pool each, assumed as in M0468), equal weight, monthly, fractional shares at
Gotrade's real fees, behind SPY's 200-day switch. The opponents are independent hash draws from the
whole scored pool behind the same switch: the spread between them is how far chance alone moves a
30-name book here, and a tail is only read as an effect if it falls outside that spread.

The low-volatility anomaly was published long before the dev window ends (Haugen and Heins 1975, Ang,
Hodrick, Xing and Zhang 2006, Frazzini and Pedersen 2014), so an edge here may already be traded away.

Arms (six, the lab's cap): LOW and HIGH (the idea and its mirror), R1-R4 (four independent draws behind
the switch, seeds 473-476). The no-switch always-invested arm is dropped to buy a wider chance spread:
M0468's R1-NOSW already priced the switch on this same chassis, and every arm here pays it equally.
The SPY control is the lab's recorded benchmark, which pays the same fees in the same run.
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

MODES = ("low", "high", "blind")
SPAN = 250
BOOK = 30
MARKET = "SPY"

HOST = replace(N20, top=BOOK)


@dataclass(frozen=True, slots=True)
class LevelParams:
    """``inner`` is the host's screen, switch, book size and weighting; ``mode`` is the ranking."""

    inner: FactorParams
    mode: str = "low"
    seed: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if self.mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {self.mode!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError(f"seed must be an int, got {type(self.seed).__name__}")

    def as_dict(self) -> dict[str, str]:
        out = {"mode": self.mode, "seed": str(self.seed), "span": str(SPAN)}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> LevelParams:
    if not isinstance(params, LevelParams):
        raise TypeError(f"params must be LevelParams, got {type(params).__name__}")
    return params


def level_of(history: Mapping[str, History], symbols: list[str], data_date: date) -> dict[str, float]:
    """Standard deviation of the last 250 daily returns, only from bars dated <= data_date."""
    out: dict[str, float] = {}
    for s in symbols:
        h = history.get(s)
        if h is None:
            continue
        i = h.index_of(data_date)
        if i is None or i < SPAN:
            continue
        c = h.close[i - SPAN : i + 1]
        if not (np.all(np.isfinite(c)) and np.all(c > 0.0)):
            continue
        out[s] = float(np.std(c[1:] / c[:-1] - 1.0))
    return out


def choose(rows: list[FactorRow], vol: dict[str, float], params: LevelParams) -> list[FactorRow]:
    """Pick ``top`` names. Names with zero volatility or too little history leave every arm."""
    pool = [r for r in rows if r.symbol not in EXCLUDED and vol.get(r.symbol, 0.0) > 0.0]
    top = params.inner.top
    if params.mode == "blind":
        pool.sort(key=lambda r: (draw(params.seed, r.symbol), r.symbol))
        return pool[:top]
    sign = 1.0 if params.mode == "low" else -1.0
    pool.sort(key=lambda r: (sign * vol[r.symbol], r.symbol))
    return pool[:top]


@dataclass
class LevelPrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)
    cache: dict[date, dict[str, float]] = field(default_factory=dict, repr=False)


class LevelAllocator:
    """The lab's index-member book ranked on 250-day volatility itself."""

    id = "M0473"

    def lookback(self, params: Any) -> int:
        return max(factor_lookback(_check(params).inner), SPAN + 1)

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

    def _run(self, prepared: LevelPrepared | None, history: Mapping[str, History],
             members: AbstractSet[str], data_date: date, p: LevelParams) -> tuple[Target, ...]:
        if not trend_on(history, data_date, p.inner):
            return ()
        if prepared is None:
            rows = factor_rows(history, members, data_date, p.inner)
        else:
            rows = prepared.factor.rows_on(members, data_date, p.inner)
        syms = sorted(r.symbol for r in rows if r.symbol not in EXCLUDED)
        if prepared is None:
            vol = level_of(history, syms, data_date)
        else:
            vol = prepared.cache.get(data_date) or level_of(history, syms, data_date)
            prepared.cache[data_date] = vol
        return targets_from_rows(choose(rows, vol, p), p)  # type: ignore[arg-type]

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self._run(None, history, members, data_date, _check(params))

    def prepare(self, history: Mapping[str, History]) -> LevelPrepared:
        return LevelPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, LevelPrepared):
            raise TypeError(f"prepared must be LevelPrepared, got {type(prepared).__name__}")
        return self._run(prepared, prepared.history, members, data_date, _check(params))


LEVEL = LevelAllocator()


def _v(suffix: str, params: LevelParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0473-{suffix}", family="M0473",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=LEVEL, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0473",
    name="The risk level on its own: calm and wild large-company tenths against equal-level random picks, five independent draws",
    family="stock-volatility-level",
    source_kind="variation",
    source_ref="Variation of M0468; low-volatility anomaly (Ang, Hodrick, Xing, Zhang 2006; Frazzini and Pedersen 2014)",
    parent_id="M0468",
    hypothesis=(
        "M0468 found that ranking on how much a stock's risk changes added little beyond the risk level, "
        "and its random controls were single draws. The low-volatility effect was published well before "
        "2015 (2006, 2014), so the dev window can only show what the crowd had not fully traded. Hold the "
        "lowest and highest tenths of 250-day volatility itself (30 names each, about a tenth of the "
        "scored pool, assumed as in M0468), equal weight, monthly, behind SPY's 200-day switch, "
        "fractional shares at Gotrade real fees. Against them: four independent hash draws from the "
        "whole scored pool behind the same switch (the lab's six-arm cap leaves room for four, not five; "
        "the always-invested arm is dropped because M0468's R1-NOSW priced the switch on this chassis), so "
        "the chance spread of a 30-name book is measured and the level alone is priced. Predictions, "
        "written now: LOW and HIGH both land inside the range of the four draws on funded CAGR; the "
        "four draws differ from each other by more than 2 points a year; LOW has the shallower fall; "
        "no arm beats SPY in 2009-2015."
    ),
    expected_failure=(
        "The switch carries the fall and the time in cash, so every arm looks alike and the tails "
        "cannot be told from chance (M0347, M0417, M0350, M0459). LOW may beat SPY on the dev average "
        "through the 1996-2008 years and lag it from 2009, when the big-company drift is the opponent "
        "(insight 91). Four draws are still a thin spread: an arm outside it is a hint, not a proof. "
        "HIGH may hold stocks with no price history in bad years."
    ),
    candidates=(
        _v("LOW", LevelParams(HOST, "low"),
           "The 30 lowest 250-day-volatility names behind the switch: the calm tenth"),
        _v("HIGH", LevelParams(HOST, "high"),
           "The 30 highest 250-day-volatility names behind the switch: the wild tenth, the mirror"),
        _v("R1", LevelParams(HOST, "blind", 473), "Control: hash-drawn 30 from the scored pool, seed 473, behind the switch"),
        _v("R2", LevelParams(HOST, "blind", 474), "Control: hash-drawn 30 from the scored pool, seed 474, behind the switch"),
        _v("R3", LevelParams(HOST, "blind", 475), "Control: hash-drawn 30 from the scored pool, seed 475, behind the switch"),
        _v("R4", LevelParams(HOST, "blind", 476), "Control: hash-drawn 30 from the scored pool, seed 476, behind the switch"),
    ),
    seen_keys=("concept:stock-volatility-level",),
)

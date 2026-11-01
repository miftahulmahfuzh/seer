"""M0468 — Hold the stocks whose own volatility is steady, against the ones whose volatility lurches.

Idea from the volatility-of-volatility literature (Baltussen, Van Bekkum and Van Der Grient, "Unknown
Unknowns: Uncertainty About Risk and Stock Returns", JFQA 2018; vol-of-vol as a return predictor), so
the dev window ends after it was published and the edge it shows may already have faded. Each month
every F4-screened index member is scored on the standard deviation of its rolling 20-day volatility
over the last 250 sessions (270 daily returns): a stock whose risk keeps changing scores high, a
stock whose risk is steady scores low. The score is strongly tied to the volatility level itself, so
a plain low-volatility book would win or lose for the same reason. The matched arms remove that: the
pool is cut into five quintiles of mean 20-day volatility and the control holds as many hash-drawn
names from each quintile as its treatment arm holds.

Frame as M0350: point-in-time members, F4 screen, equal slots, monthly, fractional shares at Gotrade's
real fees, SPY 200-day switch. The book holds 30 names, roughly a tenth of the scored pool (assumed;
the pool size moves with the index and the screen). Arms (six, the lab's cap): CALM and ERRATIC (idea
and mirror), VM-CALM and VM-ERRATIC (level-matched random controls), R1 (hash order behind the
switch) and R1-NOSW (same order, no switch: the always-invested no-opinion arm). The SPY control is
the lab's recorded benchmark, which pays the same fees in the same run.
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

MODES = ("calm", "erratic", "vm-calm", "vm-erratic", "blind")
VWIN = 20
SPAN = 250
BOOK = 30
MARKET = "SPY"
BUCKETS = 5

HOST = replace(N20, top=BOOK)
NOSW = replace(HOST, trend=None)


@dataclass(frozen=True, slots=True)
class VovParams:
    """``inner`` is the host's screen, switch, book size and weighting; ``mode`` is the ranking."""

    inner: FactorParams
    mode: str = "calm"
    seed: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if self.mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {self.mode!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError(f"seed must be an int, got {type(self.seed).__name__}")

    def as_dict(self) -> dict[str, str]:
        out = {"mode": self.mode, "seed": str(self.seed), "vwin": str(VWIN), "span": str(SPAN), "buckets": str(BUCKETS)}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> VovParams:
    if not isinstance(params, VovParams):
        raise TypeError(f"params must be VovParams, got {type(params).__name__}")
    return params


def scored_names(history: Mapping[str, History], symbols: list[str], data_date: date
                 ) -> tuple[dict[str, float], dict[str, float]]:
    """(std of rolling 20-day volatility, mean rolling 20-day volatility) over the last 250 sessions."""
    need = SPAN + VWIN
    vov: dict[str, float] = {}
    lvl: dict[str, float] = {}
    for s in symbols:
        h = history.get(s)
        if h is None:
            continue
        i = h.index_of(data_date)
        if i is None or i < need:
            continue
        c = h.close[i - need : i + 1]
        if not (np.all(np.isfinite(c)) and np.all(c > 0.0)):
            continue
        ret = c[1:] / c[:-1] - 1.0
        rv = np.std(np.lib.stride_tricks.sliding_window_view(ret, VWIN), axis=1)
        vov[s] = float(np.std(rv))
        lvl[s] = float(np.mean(rv))
    return vov, lvl


def choose(rows: list[FactorRow], rng: dict[str, float], vol: dict[str, float],
           params: VovParams) -> list[FactorRow]:
    """Pick ``top`` names. Names with zero volatility or too little history are dropped from every arm."""
    pool = [r for r in rows if r.symbol not in EXCLUDED and r.symbol in rng and vol[r.symbol] > 0.0]
    top = params.inner.top
    ratio = rng
    if params.mode == "blind":
        pool.sort(key=lambda r: (float(draw(params.seed, r.symbol)), r.symbol))
        return pool[:top]
    sign = 1.0 if params.mode in ("calm", "vm-calm") else -1.0
    ranked = sorted(pool, key=lambda r: (sign * ratio[r.symbol], r.symbol))
    treat = ranked[:top]
    if params.mode in ("calm", "erratic"):
        return treat
    # level-matched control: same count per volatility quintile as the treatment holds
    by_vol = sorted(pool, key=lambda r: (vol[r.symbol], r.symbol))
    n = len(by_vol)
    bucket = {r.symbol: min(BUCKETS - 1, i * BUCKETS // n) for i, r in enumerate(by_vol)}
    need: dict[int, int] = {}
    for r in treat:
        need[bucket[r.symbol]] = need.get(bucket[r.symbol], 0) + 1
    out: list[FactorRow] = []
    for b in sorted(need):
        cand = [r for r in pool if bucket[r.symbol] == b]
        cand.sort(key=lambda r: (float(draw(params.seed, r.symbol)), r.symbol))
        out.extend(cand[: need[b]])
    return out


@dataclass
class VovPrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)
    cache: dict[date, tuple[dict[str, float], dict[str, float]]] = field(default_factory=dict, repr=False)


class VovAllocator:
    """The lab's index-member book ranked on mean daily range over close-to-close volatility."""

    id = "M0468"

    def lookback(self, params: Any) -> int:
        return max(factor_lookback(_check(params).inner), SPAN + VWIN + 1)

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

    def _run(self, prepared: VovPrepared | None, history: Mapping[str, History],
             members: AbstractSet[str], data_date: date, p: VovParams) -> tuple[Target, ...]:
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
        return targets_from_rows(choose(rows, scores[0], scores[1], p), p)  # type: ignore[arg-type]

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self._run(None, history, members, data_date, _check(params))

    def prepare(self, history: Mapping[str, History]) -> VovPrepared:
        return VovPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, VovPrepared):
            raise TypeError(f"prepared must be VovPrepared, got {type(prepared).__name__}")
        return self._run(prepared, prepared.history, members, data_date, _check(params))


VOV = VovAllocator()


def _v(suffix: str, params: VovParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0468-{suffix}", family="M0468",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=VOV, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0468",
    name="Calm risk, not just low risk: stocks whose 20-day volatility itself moves the least, one tail against the mirror",
    family="stock-volatility-of-volatility",
    source_kind="paper",
    source_ref="Baltussen, Van Bekkum, Van Der Grient, 'Unknown Unknowns: Uncertainty About Risk and Stock Returns', JFQA 2018",
    parent_id=None,
    hypothesis=(
        "Published 2018, so the dev window (ends 2015) can only show what the crowd had not yet traded. "
        "Every month each F4-screened index member is scored on the standard deviation of its rolling "
        "20-day volatility over the last 250 sessions. CALM holds the 30 lowest (steadiest risk, about "
        "a tenth of the pool), ERRATIC the 30 highest, equal weight, monthly, fractional shares at "
        "Gotrade's real fees, behind SPY's 200-day switch. Mechanism: unstable risk is priced as "
        "uncertainty the market dislikes, so steady-risk stocks should be cheaper to hold than their "
        "volatility level suggests. Because vol-of-vol is tied to the volatility level, VM-CALM and "
        "VM-ERRATIC hold random names with the same count per mean-volatility quintile as their "
        "treatment arm, so the ranking opinion is removed and the level kept. R1 (hash order, switch) "
        "and R1-NOSW (same, no switch) price the switch. SPY control is the lab's benchmark. Predictions, "
        "written now: CALM and ERRATIC each land within 2 points a year of their level-matched control "
        "(vol-of-vol adds nothing over the level); CALM trails SPY in 2009-2015; R1-NOSW falls over 40% "
        "so the switch carries the fall. Assumption: book size 30 as a tenth of the pool, no tuning."
    ),
    expected_failure=(
        "Vol-of-vol is mostly the volatility level in disguise, so CALM is a low-volatility book and "
        "inherits the lab's repeated finding that calm-stock books trail random picks of equal calm "
        "(M0347, M0417, M0350) and that the switch does the work (M0459). Any CALM-over-SPY result "
        "will sit inside the chance spread of random picks behind the switch. The score also flags "
        "stocks with one shock in the 250 sessions as erratic, which is event noise. Matched controls "
        "draw once per seed, a thin chance spread."
    ),
    candidates=(
        _v("CALM", VovParams(HOST, "calm"),
           "The 30 steadiest-risk names (lowest std of 20-day volatility over 250 sessions), behind the switch: the idea"),
        _v("ERRATIC", VovParams(HOST, "erratic"),
           "The 30 most erratic-risk names, behind the switch: the mirror"),
        _v("VM-CALM", VovParams(HOST, "vm-calm", 468),
           "Level-matched random control for CALM: same count per mean-volatility quintile, hash-drawn"),
        _v("VM-ERRATIC", VovParams(HOST, "vm-erratic", 469),
           "Level-matched random control for ERRATIC: same count per mean-volatility quintile, hash-drawn"),
        _v("R1", VovParams(HOST, "blind", 468),
           "Control: hash-ranked scored pool, seed 468, behind the switch"),
        _v("R1-NOSW", VovParams(NOSW, "blind", 468),
           "No-opinion always-invested arm: R1's order with no switch, prices the switch's habit"),
    ),
    seen_keys=("concept:stock-volatility-of-volatility",),
)

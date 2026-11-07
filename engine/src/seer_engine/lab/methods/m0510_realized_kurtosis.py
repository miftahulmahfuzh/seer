"""M0510 — Fat-tailed stocks: index members ranked on how extreme their worst and best days are.

Source: Amaya, Christoffersen, Jacobs & Vasquez (2015), "Does realized skewness and kurtosis predict
the cross-section of equity returns?" (JFE): stocks with high realised kurtosis (fat tails, lottery-like
extreme days) earn less afterwards. Published 2015, so the dev window (ends 2015-10-16) cannot have been
crowded by it. Score = excess kurtosis (fourth standardised moment minus 3) of the last 126 daily
returns. Frame is M0505's: N20 host, 20 equal monthly slots, fractional shares at Gotrade real fees,
SPY 200-day switch. Names short of 127 closes, with a gap or a non-positive price, or with zero
volatility are unscored in every arm alike.

Arms (six; the idea asked for five blind seeds, but a method carries at most six variants): LOWK
(treatment: the 20 lowest-kurtosis names, the paper's long leg), HIGHK (mirror), LOWK-VM (volatility
matched: the pool is cut into four equal-sized volatility bands and the 5 lowest-kurtosis names are
taken from each, so the book carries the pool's own risk mix and kurtosis is not calm stocks again,
the M0505 lesson), R1 and R2 (blind draws, seeds 510, 511, behind the switch) and R1-NOSW (always
invested with no opinion: prices the switch and acting).
SUCCESS: LOWK beats the better of R1/R2 by more than 2 points a year funded, HIGHK loses to R1,
LOWK-VM still beats the draws, positive 2009-2015 edge vs SPY.
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
MODES = ("lowk", "highk", "lowk_vm", "blind")
NEED = 127  # closes needed: 126 returns
BANDS = 4
MARKET = "SPY"

NOSW = replace(N20, trend=None)


@dataclass(frozen=True, slots=True)
class TimeParams:
    """``inner`` is the host's screen, switch, book size and weighting; ``mode`` is the ranking."""

    inner: FactorParams
    mode: str = "lowk"
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
    """(excess kurtosis, daily volatility) of the last 126 daily returns.

    Kurtosis is the mean fourth power of the standardised returns minus 3. Unscored on a gap, a
    non-positive price or zero volatility."""
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
        sd = float(np.std(r))
        if sd <= 0.0:
            continue
        z = (r - float(np.mean(r))) / sd
        out[s] = (float(np.mean(z**4)) - 3.0, float(np.std(r, ddof=1)))
    return out


def choose(rows: list[FactorRow], score: dict[str, tuple[float, float]], params: TimeParams
           ) -> list[FactorRow]:
    pool = [r for r in rows if r.symbol not in EXCLUDED and r.symbol in score]
    n = params.inner.top
    if params.mode == "lowk_vm":
        # four equal-sized volatility bands, the lowest-kurtosis names from each: the book keeps
        # the pool's own risk mix, so kurtosis cannot be calm stocks again.
        by_vol = sorted(pool, key=lambda r: (score[r.symbol][1], r.symbol))
        size = len(by_vol) / BANDS
        take = n // BANDS
        out: list[FactorRow] = []
        for b in range(BANDS):
            band = by_vol[round(b * size) : round((b + 1) * size)]
            band.sort(key=lambda r: (score[r.symbol][0], r.symbol))
            out.extend(band[:take])
        return out
    if params.mode == "lowk":
        key = {r.symbol: (score[r.symbol][0], 0.0) for r in pool}
    elif params.mode == "highk":
        key = {r.symbol: (-score[r.symbol][0], 0.0) for r in pool}
    else:
        key = {r.symbol: (float(draw(params.seed, r.symbol)), 0.0) for r in pool}
    pool.sort(key=lambda r: (key[r.symbol], r.symbol))
    return pool[:n]


@dataclass
class TimePrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)
    cache: dict[date, dict[str, tuple[float, float]]] = field(default_factory=dict, repr=False)


class KurtosisAllocator:
    """The lab's index-member book ranked on the fatness of each stock's tails."""

    id = "M0510"

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


KURTOSIS = KurtosisAllocator()


def _v(suffix: str, params: TimeParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0510-{suffix}", family="M0510",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=KURTOSIS, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0510",
    name="Fat-tailed stocks: index members whose daily returns have the heaviest extreme days over the last half year",
    family="stock-realized-kurtosis",
    source_kind="paper",
    source_ref="Amaya, Christoffersen, Jacobs & Vasquez (2015), Does realized skewness and kurtosis predict the cross-section of equity returns?, JFE",
    parent_id=None,
    hypothesis=(
        "Published 2015 (the dev window ends 2015-10-16, so the crowd had barely arrived): stocks "
        "with high realised kurtosis, meaning fat tails and lottery-like extreme days, earn less "
        "afterwards. Score = excess kurtosis of the last 126 daily returns. Hold the 20 lowest-"
        "kurtosis F4-screened point-in-time index members monthly in equal fractional slots at "
        "Gotrade real fees behind SPY's 200-day switch. Arms: LOWK, HIGHK (mirror), LOWK-VM "
        "(volatility matched: five lowest-kurtosis names from each of four volatility bands, so "
        "kurtosis is not calm stocks again, the M0505 lesson), R1 and R2 (blind draws, seeds 510, "
        "511, switch on; five seeds were wanted but a method carries at most six variants) and "
        "R1-NOSW (always invested, no opinion: prices the switch and acting). SUCCESS: LOWK beats the "
        "better of R1/R2 by more than 2 points a year funded, HIGHK loses to R1, LOWK-VM still "
        "beats the draws, positive 2009-2015 edge vs SPY. Predictions, written now: LOWK lands "
        "within 2 points a year of the draws, kin to the skewness and lottery books, and fades "
        "after publication; LOWK-VM is the arm that shows whether any edge is more than calm."
    ),
    expected_failure=(
        "Kurtosis over half a year is dominated by one or two earnings days, so it is a noisy "
        "stand-in for 'had an event recently' or for calm, and LOWK is the calm book renamed. "
        "Both trail SPY in the 2009-2015 rise and the blind draws match them, as the lab's other "
        "lottery and skewness books did. A strong dev result from a 2015 paper would be expected "
        "to fade."
    ),
    candidates=(
        _v("LOWK", TimeParams(N20, "lowk"), "Lowest 126-session excess kurtosis, behind the switch"),
        _v("HIGHK", TimeParams(N20, "highk"), "Highest kurtosis: the mirror"),
        _v("LOWK-VM", TimeParams(N20, "lowk_vm"), "Volatility matched: lowest kurtosis within each of four volatility bands"),
        _v("R1", TimeParams(N20, "blind", 510), "Control: hash draw of 20, seed 510, behind the switch"),
        _v("R2", TimeParams(N20, "blind", 511), "Control: hash draw of 20, seed 511, measures draw noise"),
        _v("R1-NOSW", TimeParams(NOSW, "blind", 510), "Always invested, no opinion: prices acting on either"),
    ),
    seen_keys=(
        "concept:realized-kurtosis",
    ),
)

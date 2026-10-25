"""M0358 — Hold the index members whose daily high-low range runs far above their close-to-close swings.

Source: Parkinson (1980), the extreme-value variance estimator from the daily high and low, and
Garman & Klass (1980). Old and widely known as a volatility estimator; as a stock-picking key
(range volatility over close volatility) it is not a famous anomaly, so decay is less the risk
than that the ratio is plain volatility or price level in another coat (M0348's range key was).

The frame is M0348's: point-in-time members, the $5 price and 20M-dollar volume screen, 20 equal
slots, monthly, fractional shares at Gotrade's real fees, the SPY 200-day switch on every arm but
two. The key is log(Parkinson volatility / close-to-close volatility) over the last 63 bars ending
on data_date, Parkinson = sqrt(mean(ln(hi/lo)^2) / (4 ln 2)), close volatility = std of daily
close-to-close returns. Names with any missing bar, a high below the low, or a zero close are not
scored, identically in every arm.

Arms (six, the lab's cap): LOW holds the 20 lowest ratio, HIGH the 20 highest (the mirror), R1 and
R2 hash-rank the pool behind the switch, LOW-NOSW is LOW's order with no switch (the always-invested
third arm that prices the switch's habit), R1-NOSW is the same for chance.
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

ADDED = date(2026, 10, 25)

MODES = ("low", "high", "blind")
WIN = 63  # bars in the volatility windows
MARKET = "SPY"

NOSW = replace(N20, trend=None)


@dataclass(frozen=True, slots=True)
class RangeParams:
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
        out = {"mode": self.mode, "seed": str(self.seed), "win": str(WIN)}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> RangeParams:
    if not isinstance(params, RangeParams):
        raise TypeError(f"params must be RangeParams, got {type(params).__name__}")
    return params


def scored_names(history: Mapping[str, History], symbols: list[str], data_date: date
                 ) -> dict[str, float]:
    """log(Parkinson vol / close-to-close vol) per scorable name over the last WIN bars."""
    out: dict[str, float] = {}
    for s in symbols:
        h = history.get(s)
        if h is None:
            continue
        i = h.index_of(data_date)
        if i is None or i < WIN:
            continue
        hi = h.high[i - WIN + 1 : i + 1]
        lo = h.low[i - WIN + 1 : i + 1]
        c = h.close[i - WIN : i + 1]
        if not (np.all(np.isfinite(hi)) and np.all(np.isfinite(lo)) and np.all(np.isfinite(c))):
            continue
        if not (np.all(lo > 0.0) and np.all(hi >= lo) and np.all(c > 0.0)):
            continue
        park = float(np.sqrt(np.mean(np.log(hi / lo) ** 2) / (4.0 * np.log(2.0))))
        cc = float(np.std(c[1:] / c[:-1] - 1.0))
        if park <= 0.0 or cc <= 0.0:
            continue
        out[s] = float(np.log(park / cc))
    return out


def choose(rows: list[FactorRow], ratio: dict[str, float], params: RangeParams) -> list[FactorRow]:
    pool = [r for r in rows if r.symbol not in EXCLUDED and r.symbol in ratio]
    if params.mode == "low":
        key = {r.symbol: ratio[r.symbol] for r in pool}
    elif params.mode == "high":
        key = {r.symbol: -ratio[r.symbol] for r in pool}
    else:
        key = {r.symbol: float(draw(params.seed, r.symbol)) for r in pool}
    pool.sort(key=lambda r: (key[r.symbol], r.symbol))
    return pool[: params.inner.top]


@dataclass
class RangePrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)
    cache: dict[date, dict[str, float]] = field(default_factory=dict, repr=False)


class RangeGapAllocator:
    """The lab's index-member book ranked on the Parkinson-to-close volatility ratio."""

    id = "M0358"

    def lookback(self, params: Any) -> int:
        return max(factor_lookback(_check(params).inner), WIN + 1)

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

    def _run(self, prepared: RangePrepared | None, history: Mapping[str, History],
             members: AbstractSet[str], data_date: date, p: RangeParams) -> tuple[Target, ...]:
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

    def prepare(self, history: Mapping[str, History]) -> RangePrepared:
        return RangePrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, RangePrepared):
            raise TypeError(f"prepared must be RangePrepared, got {type(prepared).__name__}")
        return self._run(prepared, prepared.history, members, data_date, _check(params))


RANGEGAP = RangeGapAllocator()


def _v(suffix: str, params: RangeParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0358-{suffix}", family="M0358",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=RANGEGAP, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0358",
    name="Quiet closes, wild ranges: stocks whose daily high-low range runs far above their close-to-close swings, held a month",
    family="stock-range-volatility-gap",
    source_kind="knowledge",
    source_ref="",
    parent_id=None,
    hypothesis=(
        "Close-to-close volatility sees only where a stock ended each day; the daily high-low "
        "range sees how hard it was pushed on the way (Parkinson 1980; Garman & Klass 1980, "
        "estimators, not a published anomaly). Stocks whose 63-session Parkinson volatility is far "
        "above their close-to-close volatility are pushed hard intraday and pulled back by the "
        "close. Every month the book scores each F4-screened index member by the log ratio and "
        "holds 20 equal weight, fractional shares at Gotrade's real fees, behind SPY's 200-day "
        "switch. Arms: LOW (20 lowest ratio, smooth movers), HIGH (20 highest, the mirror), R1 "
        "and R2 (hash order, same pool, same switch), LOW-NOSW (LOW's order, no switch: the "
        "always-invested arm that prices the switch's habit apart from the opinion) and R1-NOSW "
        "(chance, no switch). SUCCESS: one end beats the better of R1 and R2 by a clear margin "
        "(more than their spread plus 2 points a year) and the other end loses to it, with a "
        "positive 2009-2015 edge versus SPY. Predictions, written now: LOW and HIGH differ by "
        "under 2 points a year; neither beats the random pair; both trail SPY in 2009-2015; "
        "LOW-NOSW falls over 35%, so the switch and not the ranking limits the fall."
    ),
    expected_failure=(
        "In large caps the ratio is mostly a proxy for plain volatility and price level (a high "
        "ratio flags wide-spread, gappy names; a low ratio flags names that trade in a tight "
        "band), so both ends collapse into the calm-stock or lottery books the lab has already "
        "rejected (M0091, M0342, M0348), and the random control matches them behind the switch. "
        "Two hash draws are a thin chance spread. Highs and lows on back-adjusted early prices "
        "can carry errors; names failing the checks are dropped from every arm alike. If so, a "
        "follow-up residualises the ratio on plain volatility."
    ),
    candidates=(
        _v("LOW", RangeParams(N20, "low"),
           "The 20 lowest log(range vol / close vol) over 63 bars, behind the SPY switch"),
        _v("HIGH", RangeParams(N20, "high"),
           "The 20 highest ratio, behind the switch: the mirror"),
        _v("R1", RangeParams(N20, "blind", 358),
           "Control: hash-ranked scored pool, seed 358, behind the switch"),
        _v("R2", RangeParams(N20, "blind", 359),
           "Control: hash-ranked scored pool, seed 359, behind the switch"),
        _v("LOW-NOSW", RangeParams(NOSW, "low"),
           "No-switch twin of LOW: always invested, prices the switch's habit"),
        _v("R1-NOSW", RangeParams(NOSW, "blind", 358),
           "No-opinion always-invested arm: R1's order with no switch"),
    ),
    seen_keys=(
        "concept:parkinson-range-volatility-ratio",
        "concept:range-vs-close-volatility-gap",
    ),
)

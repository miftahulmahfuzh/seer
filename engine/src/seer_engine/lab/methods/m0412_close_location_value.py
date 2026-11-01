"""M0412 — Hold the index members whose days keep closing near their highs.

Source: Chaikin's close-location value (Marc Chaikin, money-flow / accumulation-distribution
line, 1970s-80s), a charting staple, widely known as a timing indicator and not a published
cross-sectional anomaly, so decay is less the risk than that the key is short-term momentum in
another coat (the lab's momentum placebo).

The frame is M0358's: point-in-time members, the $5 price and 20M-dollar volume screen, 20 equal
slots, monthly, fractional shares at Gotrade's real fees, the SPY 200-day switch on every arm but
two. The key is the mean over the last 63 bars ending on data_date of
((close - low) - (high - close)) / (high - low), +1 when a day closes on its high, -1 on its low;
a zero-range day counts 0. Names with any missing bar, a high below the low, or a non-positive
price are not scored, identically in every arm.

Arms (six, the lab's cap): HIGH holds the 20 highest mean CLV, LOW the 20 lowest (the reversed
arm), R1 and R2 hash-rank the pool behind the switch, HIGH-NOSW is HIGH's order with no switch
(the always-invested third arm that prices the switch's habit), R1-NOSW is the same for chance.
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
WIN = 63  # bars in the volatility windows
MARKET = "SPY"

NOSW = replace(N20, trend=None)


@dataclass(frozen=True, slots=True)
class CloseParams:
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


def _check(params: object) -> CloseParams:
    if not isinstance(params, CloseParams):
        raise TypeError(f"params must be CloseParams, got {type(params).__name__}")
    return params


def scored_names(history: Mapping[str, History], symbols: list[str], data_date: date
                 ) -> dict[str, float]:
    """Mean close-location value per scorable name over the last WIN bars.

    CLV = ((close - low) - (high - close)) / (high - low), in [-1, 1]: +1 when the day closed on
    its high. A day with high == low has no location and counts 0 (neutral). Names with a missing
    bar, a high below the low, or a non-positive price are not scored."""
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
        c = h.close[i - WIN + 1 : i + 1]
        if not (np.all(np.isfinite(hi)) and np.all(np.isfinite(lo)) and np.all(np.isfinite(c))):
            continue
        if not (np.all(lo > 0.0) and np.all(hi >= lo) and np.all(c > 0.0)):
            continue
        rng = hi - lo
        clv = np.where(rng > 0.0, ((c - lo) - (hi - c)) / np.where(rng > 0.0, rng, 1.0), 0.0)
        out[s] = float(np.mean(clv))
    return out


def choose(rows: list[FactorRow], ratio: dict[str, float], params: CloseParams) -> list[FactorRow]:
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
class ClosePrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)
    cache: dict[date, dict[str, float]] = field(default_factory=dict, repr=False)


class CloseLocAllocator:
    """The lab's index-member book ranked on mean close-location value."""

    id = "M0412"

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

    def _run(self, prepared: ClosePrepared | None, history: Mapping[str, History],
             members: AbstractSet[str], data_date: date, p: CloseParams) -> tuple[Target, ...]:
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

    def prepare(self, history: Mapping[str, History]) -> ClosePrepared:
        return ClosePrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, ClosePrepared):
            raise TypeError(f"prepared must be ClosePrepared, got {type(prepared).__name__}")
        return self._run(prepared, prepared.history, members, data_date, _check(params))


CLOSELOC = CloseLocAllocator()


def _v(suffix: str, params: CloseParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0412-{suffix}", family="M0412",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=CLOSELOC, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0412",
    name="Where the day closes inside its own range: hold the stocks that keep closing near their daily highs",
    family="stock-close-location",
    source_kind="knowledge",
    source_ref="concept:close-location-value",
    parent_id=None,
    hypothesis=(
        "Where a day closes inside its own high-low range says who won the session: a close "
        "near the high means buyers held the price up into the bell, a close near the low means "
        "sellers did (Chaikin close-location value, a charting indicator, not a published "
        "anomaly). Every month the book scores each F4-screened index member by its mean CLV "
        "over 63 sessions and holds the top 20 equal weight, fractional shares at Gotrade's "
        "real fees, behind SPY's 200-day switch. Arms: HIGH (20 highest mean CLV), LOW (20 "
        "lowest, the reversed arm), R1 and R2 (hash order, same pool, same switch), HIGH-NOSW "
        "(HIGH's order, no switch: the always-invested arm that prices the switch's habit apart "
        "from the opinion) and R1-NOSW (chance, no switch). SUCCESS: HIGH beats the better of "
        "R1 and R2 by more than their spread plus 2 points a year, LOW loses to it, with a "
        "positive 2009-2015 edge versus SPY. Predictions, written now: HIGH and LOW differ by "
        "under 2 points a year; neither beats the random pair; both trail SPY in 2009-2015; "
        "HIGH-NOSW falls over 35%, so the switch and not the ranking limits the fall."
    ),
    expected_failure=(
        "CLV is largely a restatement of short-term momentum: stocks that close near their highs "
        "are the ones that have been rising, so HIGH collapses into the momentum placebo the lab "
        "has already rejected (M0057, M0407), and the random control matches it behind the "
        "switch. Two hash draws are a thin chance spread. Highs and lows on back-adjusted early "
        "prices can carry errors; names failing the checks are dropped from every arm alike. If "
        "so, a follow-up residualises CLV on trailing return."
    ),
    candidates=(
        _v("HIGH", CloseParams(N20, "high"),
           "The 20 highest mean close-location value over 63 bars, behind the SPY switch"),
        _v("LOW", CloseParams(N20, "low"),
           "The 20 lowest mean CLV, behind the switch: the reversed arm"),
        _v("R1", CloseParams(N20, "blind", 412),
           "Control: hash-ranked scored pool, seed 412, behind the switch"),
        _v("R2", CloseParams(N20, "blind", 413),
           "Control: hash-ranked scored pool, seed 413, behind the switch"),
        _v("HIGH-NOSW", CloseParams(NOSW, "high"),
           "No-switch twin of HIGH: always invested, prices the switch's habit"),
        _v("R1-NOSW", CloseParams(NOSW, "blind", 412),
           "No-opinion always-invested arm: R1's order with no switch"),
    ),
    seen_keys=(
        "concept:close-location-value",
    ),
)

"""M0348 — Hold the index members whose last month swung least between its daily high and low.

Source: a 2024 journal study of the daily high-low price range as a proxy for the competition
between bulls and bears; stocks with a wide range over the month go on to earn less the next
month (decile spread near 0.86% a month; abstract read, full text not). Published 2024, so the
dev window (to 2015-10-16) cannot have been traded on it by anyone: the risk here is not decay
but that the range is close-to-close volatility in another coat, which the lab has priced
before (M0091, M0174, M0342: calm books behind the switch lean on the switch, not the picks).

The frame is the lab's usual book (M0091's): point-in-time members, the $5 price and 20M-dollar
volume screen, 20 equal slots, monthly, fractional shares at Gotrade's real fees, and the SPY
200-day switch on every arm but one. Only the ranking key differs. The key is the mean over the
last 21 bars (ending on data_date) of (high - low) / close; names with any missing bar or a
high below the low in the span are not scored, identically in every arm.

Arms (six, the lab's cap), all on one scored pool:
NARROW holds the 20 narrowest, WIDE the 20 widest (the mirror, same costs, opposite opinion),
CCVOL holds the 20 lowest close-to-close volatility over the same 21 bars (does the range say
anything the plain volatility does not), R1 and R2 hash-rank the pool (chance spreads behind the
switch), and R1-NOSW is R1's order with no switch, the always-invested no-opinion arm that
prices the switch's habit so the NARROW/WIDE reversal can be split into signal and dressing.
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

ADDED = date(2026, 10, 24)

MODES = ("narrow", "wide", "ccvol", "blind")
WIN = 21  # bars in the range window
MARKET = "SPY"

NOSW = replace(N20, trend=None)


@dataclass(frozen=True, slots=True)
class RangeParams:
    """``inner`` is the host's screen, switch, book size and weighting; ``mode`` is the ranking."""

    inner: FactorParams
    mode: str = "narrow"
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
                 ) -> tuple[dict[str, float], dict[str, float]]:
    """(mean daily range / close, close-to-close volatility) per scorable name over the last WIN bars."""
    rng: dict[str, float] = {}
    vol: dict[str, float] = {}
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
        rng[s] = float(np.mean((hi - lo) / c[1:]))
        vol[s] = float(np.std(c[1:] / c[:-1] - 1.0))
    return rng, vol


def choose(rows: list[FactorRow], rng: dict[str, float], vol: dict[str, float],
           params: RangeParams) -> list[FactorRow]:
    pool = [r for r in rows if r.symbol not in EXCLUDED and r.symbol in rng]
    if params.mode == "narrow":
        key = {r.symbol: rng[r.symbol] for r in pool}
    elif params.mode == "wide":
        key = {r.symbol: -rng[r.symbol] for r in pool}
    elif params.mode == "ccvol":
        key = {r.symbol: vol[r.symbol] for r in pool}
    else:
        key = {r.symbol: float(draw(params.seed, r.symbol)) for r in pool}
    pool.sort(key=lambda r: (key[r.symbol], r.symbol))
    return pool[: params.inner.top]


@dataclass
class RangePrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)
    cache: dict[date, tuple[dict[str, float], dict[str, float]]] = field(default_factory=dict, repr=False)


class PriceRangeAllocator:
    """The lab's index-member book ranked on the last month's mean daily high-low range."""

    id = "M0348"

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
        return targets_from_rows(choose(rows, scores[0], scores[1], p), p)  # type: ignore[arg-type]

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


PRICERANGE = PriceRangeAllocator()


def _v(suffix: str, params: RangeParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0348-{suffix}", family="M0348",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=PRICERANGE, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0348",
    name="Price-range competition: avoid the stocks whose last month swung widest between high and low",
    family="stock-price-range-competition",
    source_kind="paper",
    source_ref=("2024 journal study of the daily high-low price range as a proxy for bull-bear "
                "competition, next-month decile spread about 0.86% (abstract only; full text unread)"),
    parent_id=None,
    hypothesis=(
        "A wide daily high-low range marks a month of fierce bull-bear contest and is followed by "
        "lower returns; a narrow range is followed by higher ones (2024 study, decile spread near "
        "0.86% a month; published 2024, so the dev window predates any crowd). Every month the "
        "book scores each F4-screened index member by the mean of (high - low) / close over the "
        "last 21 bars and holds the 20 narrowest equal weight, monthly, fractional shares at "
        "Gotrade's real fees, behind SPY's 200-day switch. Arms: NARROW (the idea), WIDE (the "
        "mirror, same costs), CCVOL (the 20 lowest close-to-close volatility over the same 21 "
        "bars: does the range add to plain volatility), R1 and R2 (hash order on the same pool, "
        "same switch), R1-NOSW (R1's order, no switch: the no-opinion always-invested arm that "
        "prices the switch's habit apart from the opinion, so NARROW vs WIDE splits into signal "
        "and dressing). Predictions, written now: NARROW beats WIDE on funded CAGR; NARROW beats "
        "the better of R1 and R2 by less than their spread plus 2 points a year; NARROW and "
        "CCVOL differ by under 1.5 points a year because range is mostly volatility; NARROW "
        "trails SPY in 2009-2015; NARROW's worst fall is under 25% behind the switch; R1-NOSW "
        "falls over 40%, so the switch and not the ranking carries the fall."
    ),
    expected_failure=(
        "The range is volatility with a different denominator: NARROW and CCVOL pick nearly the "
        "same 20 calm large caps, the edge over random order is the lab's known calm-tilt-behind-"
        "the-switch pattern (M0342's random picks earned as much), and the book trails SPY in the "
        "2009-2015 growth run. Large index members span a narrow range of ranges, so the decile "
        "spread of a broad cross-section may shrink to noise among them. Two hash draws are a "
        "thin chance spread. Highs and lows on back-adjusted early prices can carry data errors; "
        "names failing the high >= low > 0 check are dropped from every arm alike."
    ),
    candidates=(
        _v("NARROW", RangeParams(N20, "narrow"),
           "The 20 narrowest mean daily range over 21 bars, behind the SPY switch: the idea"),
        _v("WIDE", RangeParams(N20, "wide"),
           "The 20 widest mean daily range, behind the switch: the mirror"),
        _v("CCVOL", RangeParams(N20, "ccvol"),
           "The 20 lowest close-to-close volatility over the same 21 bars: the equal-calm twin"),
        _v("R1", RangeParams(N20, "blind", 348),
           "Control: hash-ranked scored pool, seed 348, behind the switch"),
        _v("R2", RangeParams(N20, "blind", 349),
           "Control: hash-ranked scored pool, seed 349, behind the switch"),
        _v("R1-NOSW", RangeParams(NOSW, "blind", 348),
           "No-opinion always-invested arm: R1's order with no switch, prices the switch's habit"),
    ),
    seen_keys=(
        "concept:price-range-competition",
        "concept:high-low-range-bull-bear",
    ),
)

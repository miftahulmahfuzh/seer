"""M0432 — Momentum only in stocks whose daily returns trend.

Source: Lo and MacKinlay (1988) on serial correlation of returns (the variance ratio), and the
idea that information that arrives gradually leaves positive autocorrelation in daily returns
while jumpy, news-driven moves reverse. Published long ago; a cross-sectional momentum filter
built on it is less crowded than momentum itself, but the risk is that it is plain momentum in
another coat (the lab's momentum placebo) or a volatility proxy.

The frame is M0412's: point-in-time members, the F4 screen, 20 equal slots, monthly, fractional
shares at Gotrade's real fees, the SPY 200-day switch on every arm but one. The pool is the 40
highest 12-1 momentum names. The key is the first-order autocorrelation of daily log returns
over the last 126 bars ending on data_date. Names with a missing bar or a non-positive price
are not scored, in every arm alike.

Arms (six, the lab's cap): MOM holds the 20 top momentum names (the plain control), AUTO the 20
of the 40 with the highest autocorrelation, MIRROR the 20 with the lowest, R1 and R2 draw 20 of
the same 40 by hash, AUTO-NOSW is AUTO with no switch (prices the switch's habit).
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

MODES = ("mom", "low", "high", "blind")
WIN = 126  # bars in the autocorrelation window
POOL = 40  # top-momentum names the filter chooses among
MARKET = "SPY"

NOSW = replace(N20, trend=None)


@dataclass(frozen=True, slots=True)
class AutocorrParams:
    """``inner`` is the host's screen, switch, book size and weighting; ``mode`` is the ranking."""

    inner: FactorParams
    mode: str = "mom"
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


def _check(params: object) -> AutocorrParams:
    if not isinstance(params, AutocorrParams):
        raise TypeError(f"params must be AutocorrParams, got {type(params).__name__}")
    return params


def scored_names(history: Mapping[str, History], symbols: list[str], data_date: date
                 ) -> dict[str, float]:
    """First-order autocorrelation of daily log returns over the last WIN returns.

    Needs WIN + 1 closes ending on data_date. Names with a missing bar or a non-positive price,
    or with zero return variance, are not scored."""
    out: dict[str, float] = {}
    for s in symbols:
        h = history.get(s)
        if h is None:
            continue
        i = h.index_of(data_date)
        if i is None or i < WIN:
            continue
        c = h.close[i - WIN : i + 1]
        if not (np.all(np.isfinite(c)) and np.all(c > 0.0)):
            continue
        r = np.diff(np.log(c))
        a = r[:-1] - r[:-1].mean()
        b = r[1:] - r[1:].mean()
        den = float(np.sqrt(np.sum(a * a) * np.sum(b * b)))
        if den <= 0.0:
            continue
        out[s] = float(np.sum(a * b) / den)
    return out


def choose(rows: list[FactorRow], ratio: dict[str, float], params: AutocorrParams) -> list[FactorRow]:
    pool = [r for r in rows if r.symbol not in EXCLUDED and r.symbol in ratio]
    pool.sort(key=lambda r: (-r.momentum, r.symbol))
    if params.mode == "mom":
        return pool[: params.inner.top]
    pool = pool[:POOL]
    if params.mode == "low":
        key = {r.symbol: ratio[r.symbol] for r in pool}
    elif params.mode == "high":
        key = {r.symbol: -ratio[r.symbol] for r in pool}
    else:
        key = {r.symbol: float(draw(params.seed, r.symbol)) for r in pool}
    pool.sort(key=lambda r: (key[r.symbol], r.symbol))
    return pool[: params.inner.top]


@dataclass
class AutocorrPrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)
    cache: dict[date, dict[str, float]] = field(default_factory=dict, repr=False)


class AutocorrAllocator:
    """The lab's index-member book ranked on return autocorrelation among the top-momentum names."""

    id = "M0432"

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

    def _run(self, prepared: AutocorrPrepared | None, history: Mapping[str, History],
             members: AbstractSet[str], data_date: date, p: AutocorrParams) -> tuple[Target, ...]:
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

    def prepare(self, history: Mapping[str, History]) -> AutocorrPrepared:
        return AutocorrPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, AutocorrPrepared):
            raise TypeError(f"prepared must be AutocorrPrepared, got {type(prepared).__name__}")
        return self._run(prepared, prepared.history, members, data_date, _check(params))


AUTOCORR = AutocorrAllocator()


def _v(suffix: str, params: AutocorrParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0432-{suffix}", family="M0432",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=AUTOCORR, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0432",
    name="Momentum only in stocks whose daily returns trend (positive autocorrelation)",
    family="stock-return-autocorrelation",
    source_kind="knowledge",
    source_ref="concept:return-autocorrelation-filter",
    parent_id=None,
    hypothesis=(
        "Lo and MacKinlay (1988): information that reaches prices gradually leaves positive "
        "first-order autocorrelation in daily returns, while jumpy news-driven moves reverse. "
        "Among the 40 highest 12-1 momentum names of the F4-screened index members, keep the 20 "
        "whose daily log returns over 126 sessions show the highest autocorrelation, equal "
        "weight, monthly, fractional shares at Gotrade's real fees, behind SPY's 200-day switch. "
        "Arms: MOM (plain top-20 momentum, the control), AUTO (highest autocorrelation), MIRROR "
        "(lowest), R1 and R2 (hash draws of 20 from the same 40, the blind pair), AUTO-NOSW "
        "(AUTO with no switch, the always-invested arm that prices the switch's habit). "
        "SUCCESS: AUTO beats the better of MOM, R1 and R2 by more than the spread of the blind "
        "pair plus 2 points a year, MIRROR loses to it, with a positive 2009-2015 edge vs SPY. "
        "Predictions, written now: AUTO and MIRROR differ by under 2 points a year; neither "
        "beats the blind draw; all trail SPY in 2009-2015; AUTO-NOSW falls over 35%, so the "
        "switch and not the filter limits the fall."
    ),
    expected_failure=(
        "Autocorrelation of 126 daily returns has a standard error near 0.09, larger than the "
        "spread between names, so the ranking is mostly noise and AUTO matches the blind draw of "
        "the same pool; any residual is a volatility or liquidity proxy (low-vol names read "
        "trendier through stale prices). The pool of 40 caps the filter's reach, so all arms "
        "look like plain momentum behind the switch, which does the work (M0412, M0425). "
        "Published in 1988 and widely known, so any dev edge is likely to fade."
    ),
    candidates=(
        _v("MOM", AutocorrParams(N20, "mom"),
           "Control: plain top-20 12-1 momentum, behind the switch"),
        _v("AUTO", AutocorrParams(N20, "high"),
           "Top-20 by highest return autocorrelation among the 40 top-momentum names"),
        _v("MIRROR", AutocorrParams(N20, "low"),
           "Top-20 by lowest return autocorrelation among the same 40: the reversed arm"),
        _v("R1", AutocorrParams(N20, "blind", 432),
           "Control: hash draw of 20 from the same 40, seed 432, behind the switch"),
        _v("R2", AutocorrParams(N20, "blind", 433),
           "Control: hash draw of 20 from the same 40, seed 433, behind the switch"),
        _v("AUTO-NOSW", AutocorrParams(NOSW, "high"),
           "No-switch twin of AUTO: always invested, prices the switch's habit"),
    ),
    seen_keys=(
        "concept:return-autocorrelation-filter",
    ),
)

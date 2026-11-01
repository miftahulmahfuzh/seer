"""M0461 — Volume that disagrees with price: 20-day correlation of volume change and return.

Source: arXiv 2601.06499 (Cross-Market Alpha), the Alpha191 price-volume signals; the
correlation of volume change with return is a staple of that family. Published 2026 in this
form but the family is older, so a dev edge may already be traded away.

The frame is M0461's: point-in-time members, the F4 screen, 20 equal slots, monthly, fractional
shares at Gotrade's real fees, SPY's 200-day switch on four arms. The key is the Pearson
correlation, over the last 20 sessions, of the daily log change in volume with the daily simple
return. Names with a missing bar, a non-positive price or volume, or a flat series are not
scored, in every arm alike. Distinct from M0425, which sums volume on up days.

Arms (six): NEG holds the 20 most negative correlations (volume rising as price falls), POS the
20 most positive (the mirror), R1 and R2 draw 20 of the same pool by hash, NEG-NOSW and
R1-NOSW have no switch. R1-NOSW is the always-invested arm with no opinion in it.
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
MODES = ("neg", "pos", "blind")
WIN = 20  # sessions in the correlation window
MARKET = "SPY"

NOSW = replace(N20, trend=None)


@dataclass(frozen=True, slots=True)
class PVParams:
    """``inner`` is the host's screen, switch, book size and weighting; ``mode`` is the ranking."""

    inner: FactorParams
    mode: str = "neg"
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


def _check(params: object) -> PVParams:
    if not isinstance(params, PVParams):
        raise TypeError(f"params must be PVParams, got {type(params).__name__}")
    return params


def scored_names(history: Mapping[str, History], symbols: list[str], data_date: date
                 ) -> dict[str, float]:
    """Correlation of daily log volume change with daily return over the last WIN returns.

    Needs WIN + 1 bars ending on data_date. Names with a missing bar, non-positive price or
    volume, or zero variance in either series are not scored."""
    out: dict[str, float] = {}
    for s in symbols:
        h = history.get(s)
        if h is None:
            continue
        i = h.index_of(data_date)
        if i is None or i < WIN:
            continue
        c = h.close[i - WIN : i + 1]
        v = h.volume[i - WIN : i + 1]
        if not (np.all(np.isfinite(c)) and np.all(c > 0.0)
                and np.all(np.isfinite(v)) and np.all(v > 0.0)):
            continue
        r = c[1:] / c[:-1] - 1.0
        dv = np.diff(np.log(v))
        if float(np.std(r)) <= 0.0 or float(np.std(dv)) <= 0.0:
            continue
        out[s] = float(np.corrcoef(dv, r)[0, 1])
    return out


def choose(rows: list[FactorRow], score: dict[str, float], params: PVParams) -> list[FactorRow]:
    pool = [r for r in rows if r.symbol not in EXCLUDED and r.symbol in score]
    if params.mode == "neg":
        key = {r.symbol: score[r.symbol] for r in pool}
    elif params.mode == "pos":
        key = {r.symbol: -score[r.symbol] for r in pool}
    else:
        key = {r.symbol: float(draw(params.seed, r.symbol)) for r in pool}
    pool.sort(key=lambda r: (key[r.symbol], r.symbol))
    return pool[: params.inner.top]

@dataclass
class PVPrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)
    cache: dict[date, dict[str, float]] = field(default_factory=dict, repr=False)


class PVAllocator:
    """The lab's index-member book ranked on its 20-day price-volume correlation."""

    id = "M0461"

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

    def _run(self, prepared: PVPrepared | None, history: Mapping[str, History],
             members: AbstractSet[str], data_date: date, p: PVParams) -> tuple[Target, ...]:
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

    def prepare(self, history: Mapping[str, History]) -> PVPrepared:
        return PVPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, PVPrepared):
            raise TypeError(f"prepared must be PVPrepared, got {type(prepared).__name__}")
        return self._run(prepared, prepared.history, members, data_date, _check(params))


PV = PVAllocator()


def _v(suffix: str, params: PVParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0461-{suffix}", family="M0461",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=PV, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0461",
    name="Volume that disagrees with price: 20-day correlation of volume change and daily return",
    family="stock-price-volume-correlation",
    source_kind="paper",
    source_ref="arXiv 2601.06499, Cross-Market Alpha (Alpha191 price-volume signals)",
    parent_id=None,
    hypothesis=(
        "Alpha191-style price-volume signals: stocks whose volume has risen on falling prices "
        "(negative 20-day correlation of log volume change with return) are under distribution "
        "or forced selling and are priced to rebound; stocks where volume and price rise "
        "together are crowded. Rank the F4-screened point-in-time index members by that "
        "correlation, hold 20 equal slots, monthly, fractional shares at Gotrade's real fees. "
        "Arms: NEG (most negative, the long leg), POS (the mirror), R1 and R2 (hash draws of 20 "
        "from the same pool, the blind pair), NEG-NOSW and R1-NOSW (no SPY switch; R1-NOSW is "
        "always invested with no opinion, the third arm that prices what acting costs). The "
        "other four sit behind SPY's 200-day switch. SUCCESS: NEG beats the better of R1 and R2 "
        "by more than the blind pair's spread plus 2 points a year, POS loses to it, with a "
        "positive 2009-2015 edge vs SPY. Predictions, written now: NEG and POS differ by under "
        "2 points a year; neither beats the blind draw; all trail SPY in 2009-2015."
    ),
    expected_failure=(
        "A 20-day correlation of two noisy series has a standard error near 0.22, so the rank is "
        "mostly noise and the book is a random slice of the index; the switch, not the sort, "
        "does the work (M0412, M0425, M0438). Published price-volume anomalies fade, and the "
        "no-switch arms fall past 35%."
    ),
    candidates=(
        _v("NEG", PVParams(N20, "neg"),
           "Most negative price-volume correlation among screened members, behind the switch"),
        _v("POS", PVParams(N20, "pos"),
           "Most positive correlation: the reversed arm"),
        _v("R1", PVParams(N20, "blind", 461),
           "Control: hash draw of 20 from the same pool, seed 461, behind the switch"),
        _v("R2", PVParams(N20, "blind", 462),
           "Control: hash draw of 20 from the same pool, seed 462, behind the switch"),
        _v("NEG-NOSW", PVParams(NOSW, "neg"),
           "No-switch twin of NEG: always invested, prices the switch's habit"),
        _v("R1-NOSW", PVParams(NOSW, "blind", 461),
           "Always invested, no opinion: blind draw with no switch, prices acting on either"),
    ),
    seen_keys=(
        "concept:price-volume-correlation-20d",
    ),
)

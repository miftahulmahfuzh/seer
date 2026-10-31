"""M0407 — Which days of last month carry the signal: weight the 21 daily returns by recency.

Source: Cakici, Fieberg, Neszveda, Bianchi and Zaremba (2026), the daily-return information factor
(Alpha Architect summary, https://alphaarchitect.com/daily-stock-returns/; same research line as
M0353's SSRN 6005614). The full text was not opened. What the summaries agree on: the *order* of the
past month's daily returns matters, not only their sum.

M0353 tested the paper's joint score (decay-weighted sum plus MAX) and never isolated the
chronological part. It could not say whether recency weighting adds anything over the plain
one-month return it contains. This method does only that: one dial, the weight each day of age
carries in the sum, on M0353's chassis and screen.

    score(s) = sum over the last 21 daily returns r_a (a = 0 the newest) of  w**a * r_a

w = 1.0 is the plain one-month return (the control), 0.9 is M0353's decay, 0.7 puts nearly all
weight on the last week. The book holds the ``top`` lowest scores (reversal, the published sign for
the recent days). Frame is F4's: point-in-time members with the $5 and 20M-dollar screen, the SPY
200-day trend switch, monthly, fractional shares at Gotrade's real fees. Reads only bars dated <= d.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20, N20_NOTREND
from seer_engine.lab.methods.m0091_lottery_avoidance import targets_from_rows
from seer_engine.lab.methods.m0353_daily_return_profile import ProfilePrepared
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorParams,
    FactorRow,
    factor_lookback,
    factor_rows,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 10, 31)

Side = Literal["high", "low"]
_SIDES: tuple[str, ...] = ("high", "low")
W = 21
CLIP = 0.5


@dataclass(frozen=True, slots=True)
class WeightParams:
    """``inner`` is F4's screen, trend gate and book size; ``decay`` is the per-day weight factor
    (1.0 = plain sum); ``shuffle`` swaps the score for a pseudo-random draw (the noise yardstick)."""

    inner: FactorParams
    decay: float = 0.9
    side: Side = "low"
    shuffle: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if not 0.0 < self.decay <= 1.0:
            raise ValueError(f"decay must be in (0, 1], got {self.decay!r}")
        if self.side not in _SIDES:
            raise ValueError(f"side must be one of {_SIDES}, got {self.side!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"decay": repr(self.decay), "side": self.side, "shuffle": str(self.shuffle)}
        for key, v in self.inner.as_dict().items():
            out[f"inner.{key}"] = v
        return out


def _check(params: object) -> WeightParams:
    if not isinstance(params, WeightParams):
        raise TypeError(f"params must be WeightParams, got {type(params).__name__}")
    return params


def _score(h: History, data_date: date, p: WeightParams) -> float | None:
    i = h.index_of(data_date)
    if i is None or i < W:
        return None
    close = h.close[i - W : i + 1]
    if not (np.all(np.isfinite(close)) and np.all(close > 0.0)):
        return None
    if p.shuffle:
        digest = hashlib.sha256(f"{h.symbol}|{data_date.isoformat()}".encode()).digest()
        return int.from_bytes(digest[:8], "big") / 2.0**64
    r = np.clip(close[1:] / close[:-1] - 1.0, -CLIP, CLIP)  # calendar order, newest last
    return float(np.sum(p.decay ** np.arange(W)[::-1] * r))


def choose(rows: list[FactorRow], prepared: ProfilePrepared, data_date: date,
           p: WeightParams) -> list[FactorRow]:
    kept: list[tuple[FactorRow, float]] = []
    for r in rows:
        h = prepared.history.get(r.symbol)
        if r.symbol in EXCLUDED or h is None:
            continue
        s = _score(h, data_date, p)
        if s is not None:
            kept.append((r, s))
    sign = -1.0 if p.side == "high" else 1.0
    kept.sort(key=lambda t: (sign * t[1], t[0].symbol))
    return [r for r, _ in kept[: p.inner.top]]


class WeightAllocator:
    """F4's book ranked on a recency-weighted sum of the last month's daily returns.

    Held symbols get no special treatment: a name that leaves the chosen set is signal-exited.
    """

    id = "M0407"

    def lookback(self, params: Any) -> int:
        return max(factor_lookback(_check(params).inner), W + 1)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return (p.inner.trend[0],) if p.inner.trend is not None else ()

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def prepare(self, history: Mapping[str, History]) -> ProfilePrepared:
        return ProfilePrepared(history, prepare_factor(history))

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if not trend_on(history, data_date, p.inner):
            return ()
        rows = factor_rows(history, members, data_date, p.inner)
        prepared = ProfilePrepared(history, prepare_factor(history))
        return targets_from_rows(choose(rows, prepared, data_date, p), p)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, ProfilePrepared):
            raise TypeError(f"prepared must be ProfilePrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        rows = prepared.factor.rows_on(members, data_date, p.inner)
        return targets_from_rows(choose(rows, prepared, data_date, p), p)


WEIGHT = WeightAllocator()


def _v(suffix: str, params: WeightParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0407-{suffix}", family="M0407", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=WEIGHT, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0407",
    name=("Which days of last month carry the signal: rank stocks by recency-weighted daily "
          "returns, one dial at a time"),
    family="stock-daily-return-shape",
    source_kind="variation",
    source_ref=(
        "M0353; Cakici, Fieberg, Neszveda, Bianchi and Zaremba (2026), daily return information "
        "factor, https://alphaarchitect.com/daily-stock-returns/ (full text not opened)"
    ),
    parent_id="M0353",
    hypothesis=(
        "M0353 tested the paper's joint score and could not say whether weighting recent days "
        "adds anything over the plain one-month return. This isolates the one dial. Score = sum "
        "of the last 21 daily returns each weighted decay**age; hold the 20 lowest (reversal) "
        "among F4-screened point-in-time index members at 5% each, behind the SPY 200-day switch, "
        "monthly, fractional shares at Gotrade's real fees. The paper is January 2026, so any "
        "edge it reports is not yet crowded, but the dev window ends 2015 and cannot show that. "
        "Arms: DECAY9-LO-N20-T (decay 0.9, the treatment); FLAT-LO-N20-T (decay 1.0, the plain "
        "month, the control the treatment must beat); FAST7-LO-N20-T (decay 0.7, last week "
        "dominates); DECAY9-HI-N20-T (the mirror, must trail); DECAY9-LO-N20 (always invested, "
        "no switch: the third arm that prices the habit of acting behind the switch); "
        "RAND-N20-T (pseudo-random ranking, the draw-noise yardstick). To count, DECAY9 must beat "
        "SPY TR within the 20% limit, beat FLAT and RAND by more than draw noise, trail its "
        "mirror, and be positive in 2009-2015."
    ),
    expected_failure=(
        "M0353's plain one-month reversal arm was its worst (+3.2% a year), and its whole book "
        "only tied a random pick. Recency weighting mostly reshuffles the same reversal ranking, "
        "so expect DECAY9 within draw noise of FLAT and RAND, a fall above 20% as with M0028, "
        "and the switch rather than the score doing the work. Equal weighting inside the index "
        "tilts small against SPY's big-company drift."
    ),
    candidates=(
        _v("DECAY9-LO-N20-T", WeightParams(N20, 0.9, "low"),
           "Recency-weighted reversal behind the switch: the treatment"),
        _v("FLAT-LO-N20-T", WeightParams(N20, 1.0, "low"),
           "Plain one-month return, equal weights: the control"),
        _v("FAST7-LO-N20-T", WeightParams(N20, 0.7, "low"),
           "Steeper decay, last week dominates: does a faster window help"),
        _v("DECAY9-HI-N20-T", WeightParams(N20, 0.9, "high"),
           "Mirror, highest scores: must trail if the signal is real"),
        _v("DECAY9-LO-N20", WeightParams(N20_NOTREND, 0.9, "low"),
           "Always invested, no switch: prices the switch and its churn"),
        _v("RAND-N20-T", WeightParams(N20, 0.9, "low", True),
           "Pseudo-random 20 on the same chassis: draw-noise yardstick"),
    ),
    seen_keys=(
        "concept:daily-return-weights",
        "concept:recency-weighted-return",
    ),
)

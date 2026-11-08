"""M0520 — The shape of last month's daily returns, read through its tails only.

Source: Cakici, Fieberg, Neszveda, Bianchi and Zaremba (2026), the daily return information factor
(Alpha Architect summary, https://alphaarchitect.com/daily-stock-returns/). The full text was not
opened. What the summaries agree on: the *sorted* profile of the past month's daily returns, not
just their sum, carries information about the next month.

M0353 scored the chronological order and the single best day (MAX); M0407 isolated recency weight.
Neither looked at the sorted profile on both sides. This method does, with no fitted model:

    sort the last 21 daily returns; best5 = mean of the 5 largest, worst5 = mean of the 5 smallest
    TAILNET = best5 + worst5     (positive when the good days outweigh the bad ones)
    BEST5   = best5              WORST5 = worst5 (a less-negative worst5 is a milder bad tail)

The book holds the ``top`` highest scores ("looks like past winners") among F4-screened
point-in-time members, behind the SPY 200-day switch, monthly, fractional shares at Gotrade's real
fees. Reads only bars dated <= d. The pseudo-random arm reuses M0407's hash draw.
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

ADDED = date(2026, 11, 8)

Score = Literal["tailnet", "best5", "worst5"]
Side = Literal["high", "low"]
_SCORES: tuple[str, ...] = ("tailnet", "best5", "worst5")
_SIDES: tuple[str, ...] = ("high", "low")
W = 21
K = 5
CLIP = 0.5


@dataclass(frozen=True, slots=True)
class TailParams:
    """``inner`` is F4's screen, trend gate and book size; ``score`` picks the tail summary;
    ``shuffle`` swaps the score for a pseudo-random draw (the noise yardstick)."""

    inner: FactorParams
    score: Score = "tailnet"
    side: Side = "high"
    shuffle: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if self.score not in _SCORES:
            raise ValueError(f"score must be one of {_SCORES}, got {self.score!r}")
        if self.side not in _SIDES:
            raise ValueError(f"side must be one of {_SIDES}, got {self.side!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"score": self.score, "side": self.side, "shuffle": str(self.shuffle)}
        for key, v in self.inner.as_dict().items():
            out[f"inner.{key}"] = v
        return out


def _check(params: object) -> TailParams:
    if not isinstance(params, TailParams):
        raise TypeError(f"params must be TailParams, got {type(params).__name__}")
    return params


def _score(h: History, data_date: date, p: TailParams) -> float | None:
    i = h.index_of(data_date)
    if i is None or i < W:
        return None
    close = h.close[i - W : i + 1]
    if not (np.all(np.isfinite(close)) and np.all(close > 0.0)):
        return None
    if p.shuffle:
        digest = hashlib.sha256(f"{h.symbol}|{data_date.isoformat()}".encode()).digest()
        return int.from_bytes(digest[:8], "big") / 2.0**64
    r = np.sort(np.clip(close[1:] / close[:-1] - 1.0, -CLIP, CLIP))
    best5 = float(np.mean(r[-K:]))
    worst5 = float(np.mean(r[:K]))
    if p.score == "best5":
        return best5
    if p.score == "worst5":
        return worst5
    return best5 + worst5


def choose(rows: list[FactorRow], prepared: ProfilePrepared, data_date: date,
           p: TailParams) -> list[FactorRow]:
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


class TailAllocator:
    """F4's book ranked on a tail summary of the sorted last-month daily returns.

    Held symbols get no special treatment: a name that leaves the chosen set is signal-exited.
    """

    id = "M0520"

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


TAIL = TailAllocator()


def _v(suffix: str, params: TailParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0520-{suffix}", family="M0520", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=TAIL, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0520",
    name=("Shape of the last month's daily returns as the only signal: stocks whose recent "
          "day-by-day pattern looks like past winners"),
    family="stock-daily-return-information",
    source_kind="paper",
    source_ref=(
        "Cakici, Fieberg, Neszveda, Bianchi and Zaremba (2026), daily return information "
        "factor, https://alphaarchitect.com/daily-stock-returns/ (full text not opened)"
    ),
    hypothesis=(
        "Rank point-in-time index members (F4's $5 / 20M-dollar screen) by a fixed summary of the "
        "sorted past 21 daily returns, no fitted model: TAILNET = mean of the best 5 days plus mean "
        "of the worst 5 days. Hold the 20 highest at 5% each behind the SPY 200-day switch, "
        "monthly, fractional shares at Gotrade's real fees (MONTHLY_HOLD_FRAC_GOTRADE; 20 names "
        "need fractions at a 20M IDR start). The paper is January 2026 so the edge is not yet "
        "crowded, but the dev window ends 2015 and cannot show that. Arms: TAILNET-HI-T (the "
        "treatment); TAILNET-LO-T (mirror, must trail if the shape matters); BEST5-HI-T (upside "
        "tail alone, M0353's MAX relative, which tied a random pick) and WORST5-HI-T (the mildest "
        "bad tail alone) to say which half carries it; TAILNET-HI (always invested, no switch: the "
        "third arm that prices the habit of acting behind the switch; it may book-twin an earlier "
        "host and is not a new book); RAND-T (pseudo-random 20 on the same chassis: draw-noise "
        "yardstick). To count, TAILNET-HI-T must beat SPY TR within the 20% limit, beat RAND-T by "
        "more than draw noise, trail its mirror, and be positive in 2009-2015."
    ),
    expected_failure=(
        "M0353 and M0407 both only tied a random pick on this chassis, and M0510's tail-shape "
        "ranking lost to random. Expect TAILNET-HI-T within draw noise of RAND-T, the upside half "
        "to pick lottery-like names that revert, a fall above 20% as with M0028, and the switch "
        "rather than the score doing the work. Equal weighting inside the index tilts small "
        "against SPY's big-company drift."
    ),
    candidates=(
        _v("TAILNET-HI-T", TailParams(N20, "tailnet", "high"),
           "Best-5 plus worst-5 daily returns, highest 20 behind the switch: the treatment"),
        _v("TAILNET-LO-T", TailParams(N20, "tailnet", "low"),
           "Mirror, lowest 20: must trail if the shape carries information"),
        _v("BEST5-HI-T", TailParams(N20, "best5", "high"),
           "Upside tail alone: does the good half carry it"),
        _v("WORST5-HI-T", TailParams(N20, "worst5", "high"),
           "Mildest bad tail alone: does avoiding crash days carry it"),
        _v("TAILNET-HI", TailParams(N20_NOTREND, "tailnet", "high"),
           "Always invested, no switch: prices the switch and its churn"),
        _v("RAND-T", TailParams(N20, "tailnet", "high", True),
           "Pseudo-random 20 on the same chassis: draw-noise yardstick"),
    ),
    seen_keys=(
        "concept:daily-return-tail-profile",
        "concept:sorted-daily-returns",
    ),
)

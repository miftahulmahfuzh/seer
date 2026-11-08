"""M0522 — Downside beta: stocks that fall least on the days the market falls.

Source: Ang, Chen and Xing (2006), "Downside Risk", Review of Financial Studies. Published 2006, so
the edge is probably crowded and faded; the dev window ends 2015 and cannot say. M0110 already
tested downside participation as a *capture ratio* and M0278 plain beta; this is the paper's own
statistic, the average daily return of each stock on the sessions SPY closed down:

    score = mean( stock daily return  over the last 252 sessions where SPY's daily return < 0 )

The book holds the ``top`` highest scores (mildest losers on bad days) among F4-screened
point-in-time members behind the SPY 200-day switch, monthly, fractional shares at Gotrade's real
fees. Reads only bars dated <= d. A day counts only when both the stock and SPY have bars on
consecutive sessions, so a gap never inflates a return. At least 40 down days are needed.
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

Side = Literal["high", "low"]
_SIDES: tuple[str, ...] = ("high", "low")
W = 252
MIN_DOWN = 40
CLIP = 0.5
BENCH = "SPY"


@dataclass(frozen=True, slots=True)
class BetaParams:
    """``inner`` is F4's screen, trend gate and book size; ``side`` picks mildest (high) or
    harshest (low) losers; ``shuffle`` swaps the score for a pseudo-random draw."""

    inner: FactorParams
    side: Side = "high"
    shuffle: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if self.side not in _SIDES:
            raise ValueError(f"side must be one of {_SIDES}, got {self.side!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"side": self.side, "shuffle": str(self.shuffle)}
        for key, v in self.inner.as_dict().items():
            out[f"inner.{key}"] = v
        return out


def _check(params: object) -> BetaParams:
    if not isinstance(params, BetaParams):
        raise TypeError(f"params must be BetaParams, got {type(params).__name__}")
    return params


def _score(h: History, spy: History, data_date: date, p: BetaParams) -> float | None:
    i = h.index_of(data_date)
    j = spy.index_of(data_date)
    if i is None or j is None or i < W or j < W:
        return None
    if p.shuffle:
        digest = hashlib.sha256(f"{h.symbol}|{data_date.isoformat()}".encode()).digest()
        return int.from_bytes(digest[:8], "big") / 2.0**64
    sd = spy.dates[j - W : j + 1]
    sc = spy.close[j - W : j + 1]
    hd = h.dates[i - W : i + 1]
    hc = h.close[i - W : i + 1]
    if not (np.all(np.isfinite(hc)) and np.all(hc > 0.0)):
        return None
    # stock bar k pairs with SPY's bar on the same date, and only when the previous bars share a
    # date too (so both returns span the same single session)
    pos = np.searchsorted(sd, hd[1:])
    ok = pos < len(sd)
    pos = np.where(ok, pos, 0)
    ok &= sd[pos] == hd[1:]
    ok &= pos >= 1
    prev_pos = np.where(ok, pos - 1, 0)
    ok &= sd[prev_pos] == hd[:-1]
    if not ok.any():
        return None
    rs = np.clip(hc[1:] / hc[:-1] - 1.0, -CLIP, CLIP)
    rm = sc[pos] / sc[prev_pos] - 1.0
    down = ok & (rm < 0.0)
    if int(down.sum()) < MIN_DOWN:
        return None
    return float(np.mean(rs[down]))


def choose(rows: list[FactorRow], prepared: ProfilePrepared, data_date: date,
           p: BetaParams) -> list[FactorRow]:
    spy = prepared.history.get(BENCH)
    if spy is None:
        return []
    kept: list[tuple[FactorRow, float]] = []
    for r in rows:
        h = prepared.history.get(r.symbol)
        if r.symbol in EXCLUDED or h is None or r.symbol == BENCH:
            continue
        s = _score(h, spy, data_date, p)
        if s is not None:
            kept.append((r, s))
    sign = -1.0 if p.side == "high" else 1.0
    kept.sort(key=lambda t: (sign * t[1], t[0].symbol))
    return [r for r, _ in kept[: p.inner.top]]


class DownBetaAllocator:
    """F4's book ranked on average return over the days SPY fell.

    Held symbols get no special treatment: a name that leaves the chosen set is signal-exited.
    """

    id = "M0522"

    def lookback(self, params: Any) -> int:
        return max(factor_lookback(_check(params).inner), W + 1)

    def symbols(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return (BENCH,)

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


DOWN = DownBetaAllocator()


def _v(suffix: str, params: BetaParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0522-{suffix}", family="M0522", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=DOWN, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0522",
    name="Stocks that fall least on market down days: rank index members by how little they drop on the days SPY drops, over the last year",
    family="stock-downside-beta",
    source_kind="variation",
    source_ref="Ang, Chen and Xing (2006) Downside Risk, Review of Financial Studies; variation of M0520",
    parent_id="M0520",
    hypothesis=(
        "Ang, Chen and Xing (2006) downside risk. Over the past 252 sessions, average each "
        "member's daily return on the days SPY closed down; hold the 20 whose average is highest "
        "(mildest losers on bad days) among F4-screened members behind the SPY 200-day switch, "
        "monthly, fractional shares at Gotrade real fees (MONTHLY_HOLD_FRAC_GOTRADE; 20 names "
        "need fractions at a 20M IDR start). Arms: DOWN-HI-T (treatment); DOWN-LO-T (mirror, "
        "lowest 20, must trail if the statistic matters); DOWN-HI (always invested, no switch: "
        "the no-opinion third arm that prices the habit of acting behind the switch; it may "
        "book-twin an earlier host and is not a new book); RAND-T (pseudo-random 20 on the same "
        "chassis, the draw-noise yardstick, also a likely twin of M0520-RAND-T since the hash "
        "draw is the same). Measures a stock's link to the market, not the shape of its own "
        "days. Daily OHLCV only, <= 2015-10-16. Published 2006, so likely faded; judge "
        "2009-2015 first. To count, DOWN-HI-T must beat SPY TR within the 20% limit, beat RAND-T "
        "by more than draw noise, trail its mirror, and be positive in 2009-2015."
    ),
    expected_failure=(
        "M0278 (plain beta) and M0417 (calm stocks) tied or lost to random, and M0110 showed "
        "shelter costs 3 to 6 points a year of recovery after 2009. Expect DOWN-HI-T to be a "
        "low-beta book that lags SPY in the rising 2009-2015 decade, to sit near RAND-T, and the "
        "switch rather than the score to do the work. Equal weighting inside the index also "
        "tilts small against SPY's big-company drift."
    ),
    candidates=(
        _v("DOWN-HI-T", BetaParams(N20, "high"),
           "Highest mean return on SPY-down days, top 20 behind the switch: the treatment"),
        _v("DOWN-LO-T", BetaParams(N20, "low"),
           "Mirror, lowest 20: must trail if the statistic carries information"),
        _v("DOWN-HI", BetaParams(N20_NOTREND, "high"),
           "Always invested, no switch: prices the switch and its churn"),
        _v("RAND-T", BetaParams(N20, "high", True),
           "Pseudo-random 20 on the same chassis: draw-noise yardstick"),
    ),
    seen_keys=(
        "concept:downside-beta-spy-down-days",
        "concept:ang-chen-xing-downside-risk",
    ),
)

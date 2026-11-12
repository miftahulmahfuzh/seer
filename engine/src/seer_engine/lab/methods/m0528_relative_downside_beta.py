"""M0528 — Relative downside beta: strip ordinary beta out of downside beta.

Variation of M0522 (Ang, Chen and Xing 2006, "Downside Risk"), itself a variation of M0520. M0522
ranked index members by their mean return on the days SPY fell, held the 20 mildest losers, and
found its own mirror — the 20 harshest losers on bad days — earned *more*: the worst-fallers book
beat the best-sheltered one. That result does not separate two different explanations: either
falling hard on bad days is itself informative, or the worst-fallers book is simply a high-beta
book, and high beta paid in 2009-2015's rising decade regardless of what happens on down days.
M0522 never measured plain beta alongside its downside statistic, so it could not tell the two
apart.

Ang/Chen/Xing's own statistic is a downside *beta* — a regression slope computed only on the
market's down days — read against the stock's ordinary beta over the whole window. This method
computes both regression betas properly (M0522 used a mean-return proxy, not a regression) and
ranks on their difference, so the switch's screen holds a stock's down-day sensitivity *net of*
its everyday market link:

    beta_all  = cov(stock return, SPY return) / var(SPY return), last 252 sessions, every day
    beta_down = the same regression restricted to the sessions SPY closed down
    score     = beta_down - beta_all   (how much MORE beta a stock shows on bad days than its own
                average link to the market already predicts)

Reads only bars dated <= d. A day counts only when both the stock and SPY have bars on consecutive
sessions, so a gap never inflates a return. At least 40 down days are needed for beta_down, and
SPY's return must have positive variance in both windows or the stock is skipped that day.
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

ADDED = date(2026, 11, 12)

Side = Literal["high", "low"]
Mode = Literal["relative", "plain"]
_SIDES: tuple[str, ...] = ("high", "low")
_MODES: tuple[str, ...] = ("relative", "plain")
W = 252
MIN_DOWN = 40
CLIP = 0.5
BENCH = "SPY"


@dataclass(frozen=True, slots=True)
class RelBetaParams:
    """``inner`` is F4's screen, trend gate and book size. ``side`` picks lowest or highest
    score. ``mode`` "relative" ranks on (downside beta - ordinary beta); "plain" ranks on
    ordinary beta alone, ignoring the downside term (the plain-beta control). ``shuffle`` swaps
    the score for a pseudo-random draw."""

    inner: FactorParams
    side: Side = "low"
    mode: Mode = "relative"
    shuffle: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if self.side not in _SIDES:
            raise ValueError(f"side must be one of {_SIDES}, got {self.side!r}")
        if self.mode not in _MODES:
            raise ValueError(f"mode must be one of {_MODES}, got {self.mode!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"side": self.side, "mode": self.mode, "shuffle": str(self.shuffle)}
        for key, v in self.inner.as_dict().items():
            out[f"inner.{key}"] = v
        return out


def _check(params: object) -> RelBetaParams:
    if not isinstance(params, RelBetaParams):
        raise TypeError(f"params must be RelBetaParams, got {type(params).__name__}")
    return params


def _aligned(h: History, spy: History, data_date: date) -> tuple[np.ndarray, np.ndarray] | None:
    i = h.index_of(data_date)
    j = spy.index_of(data_date)
    if i is None or j is None or i < W or j < W:
        return None
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
    rs = np.clip(hc[1:] / hc[:-1] - 1.0, -CLIP, CLIP)[ok]
    rm = (sc[pos] / sc[prev_pos] - 1.0)[ok]
    return rs, rm


def _beta(rs: np.ndarray, rm: np.ndarray) -> float | None:
    var_m = float(np.var(rm))
    if var_m <= 0.0:
        return None
    cov = float(np.mean((rs - rs.mean()) * (rm - rm.mean())))
    return cov / var_m


def _score(h: History, spy: History, data_date: date, p: RelBetaParams) -> float | None:
    if p.shuffle:
        digest = hashlib.sha256(f"{h.symbol}|{data_date.isoformat()}".encode()).digest()
        return int.from_bytes(digest[:8], "big") / 2.0**64
    aligned = _aligned(h, spy, data_date)
    if aligned is None:
        return None
    rs, rm = aligned
    down = rm < 0.0
    if int(down.sum()) < MIN_DOWN:
        return None
    beta_all = _beta(rs, rm)
    if beta_all is None:
        return None
    if p.mode == "plain":
        return beta_all
    beta_down = _beta(rs[down], rm[down])
    if beta_down is None:
        return None
    return beta_down - beta_all


def choose(rows: list[FactorRow], prepared: ProfilePrepared, data_date: date,
           p: RelBetaParams) -> list[FactorRow]:
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


class RelDownBetaAllocator:
    """F4's book ranked on (downside beta - ordinary beta), or on ordinary beta alone.

    Held symbols get no special treatment: a name that leaves the chosen set is signal-exited.
    """

    id = "M0528"

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


REL = RelDownBetaAllocator()


def _v(suffix: str, params: RelBetaParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0528-{suffix}", family="M0528", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=REL, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0528",
    name="Relative downside beta: how much worse a stock falls on market down days than its overall market link predicts",
    family="stock-downside-beta",
    source_kind="variation",
    source_ref="Ang, Chen and Xing (2006) Downside Risk, Review of Financial Studies; variation of M0522",
    parent_id="M0522",
    hypothesis=(
        "M0522 found its mirror (the 20 harshest losers on SPY-down days) beat its treatment (the "
        "20 mildest losers), but never measured plain beta beside its downside statistic, so the "
        "win could be ordinary market exposure paying off in a rising decade rather than anything "
        "about down days specifically. This method regresses each F4-screened member's daily "
        "return on SPY's over the last 252 sessions twice: once over every day (ordinary beta) "
        "and once restricted to the days SPY closed down (downside beta), then ranks on the "
        "difference (downside beta minus ordinary beta) -- how much MORE beta a stock shows when "
        "the market is falling than its everyday link already predicts. Arms, all behind the SPY "
        "200-day switch unless named otherwise, monthly, fractional shares at Gotrade real fees "
        "(MONTHLY_HOLD_FRAC_GOTRADE; 20 names need fractions at a 20M IDR start): REL-LO-T holds "
        "the 20 with the lowest (downside beta - ordinary beta) -- stocks whose bad-day losses are "
        "no worse than their everyday beta already implies (the treatment); REL-HI-T is the "
        "mirror, the 20 with the highest excess (stocks that fall disproportionately harder than "
        "their beta on bad days); REL-PLAIN ranks on ordinary beta alone, same side (lowest 20, "
        "the plain-beta control: if this book moves like REL-LO-T, the relative term adds "
        "nothing M0278 did not already show); REL-LO-NOTREND repeats REL-LO-T's score always "
        "invested, no switch (the no-opinion arm that prices the switch and its churn); REL-RAND "
        "is a pseudo-random 20 on the same chassis (draw-noise yardstick). Published 2006, so "
        "likely faded; judge 2009-2015 first since that is where M0522's reversal was measured. "
        "To count, REL-LO-T must beat SPY TR within the 20% drawdown limit, beat REL-RAND by more "
        "than draw noise, beat REL-PLAIN (so the relative term earns its keep over plain beta "
        "alone), and be positive in 2009-2015."
    ),
    expected_failure=(
        "M0110 showed shelter from down days costs 3 to 6 points a year of lost recovery after "
        "2009, and M0278 (plain beta alone) tied or lost to random. Expect REL-LO-T to move "
        "closely with REL-PLAIN -- the relative term likely does not separate from plain beta in "
        "practice, because a stock's down-day beta and its everyday beta are highly correlated by "
        "construction -- and for REL-HI-T (the high-beta-on-bad-days mirror) to again beat the "
        "low-beta book in the rising 2009-2015 decade, confirming the win in M0522 was ordinary "
        "beta exposure rather than a down-day-specific effect. Equal weighting inside the index "
        "also tilts small against SPY's big-company drift, which works against REL-LO-T twice "
        "over if it ends up the lower-beta, more defensive book."
    ),
    candidates=(
        _v("REL-LO-T", RelBetaParams(N20, "low", "relative"),
           "Lowest 20 by (downside beta - ordinary beta) behind the switch: the treatment"),
        _v("REL-HI-T", RelBetaParams(N20, "high", "relative"),
           "Mirror, highest 20 by excess downside beta: must trail if the relative term carries "
           "information"),
        _v("REL-PLAIN", RelBetaParams(N20, "low", "plain"),
           "Ranks on ordinary beta alone, same side as the treatment: prices whether the "
           "relative term adds anything beyond plain beta"),
        _v("REL-LO-NOTREND", RelBetaParams(N20_NOTREND, "low", "relative"),
           "Always invested, no switch: prices the switch and its churn"),
        _v("REL-RAND", RelBetaParams(N20, "low", "relative", True),
           "Pseudo-random 20 on the same chassis: draw-noise yardstick"),
    ),
    seen_keys=(
        "concept:relative-downside-beta",
        "concept:excess-downside-beta-ang-chen-xing",
    ),
)

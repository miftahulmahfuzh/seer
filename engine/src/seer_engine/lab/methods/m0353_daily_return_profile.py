"""M0353 — One score from the whole month of daily returns: recent days and extremes together.

Source: Cakici, Fieberg, Neszveda, Bianchi and Zaremba (January 2026), A Unified Framework for
Anomalies Based on Daily Returns, SSRN 6005614. The full text could not be opened from here (SSRN
and the blog mirrors answered 403). What search summaries of the paper agree on, and not a reading
of its methods section: the previous month's ~21 daily returns enter in two forms, in calendar
order (the "chronological" part: short-term reversal and liquidity pressure) and sorted by size
(the "rank" part: MAX and lottery-style extremes); an elastic net learns how to weigh both against
next month's return, is refit yearly, and the book holds the highest predicted decile. That
learned model is NOT what runs here. The lab's allocator contract forces every arm to run on a
bounded lookback that the test fixture (473 sessions) can supply, so a model fit on all history
cannot be tested; a fit on a short rolling window would be noise. The stand-in below is fixed in
advance, with no fitted number in it, and the analysis must say it tests the paper's idea (one score
joining both parts) and not the paper's estimator.

Idea: MAX (M0091, M0093) and one-month reversal (M0028) read the same 21 returns and each failed
alone on large caps. If the information is in the combination, one score that adds a chronological
part to a rank part should beat each summary on its own.

    chrono(s) = sum over the last 21 daily returns r_a (a = 0 the newest) of 0.9**a * r_a
    rank(s)   = mean of the five largest of those 21 returns (MAX5)
    score(s)  = percentile of chrono among the screened members + percentile of rank

The book holds the ``top`` LOWEST scores: a recent loser (reversal) whose month held no lottery
spike (the MAX effect), the two published signs. Equal weights, the equal split between the parts
is a pre-registered guess, not a tuned value. Frame is M0091's: F4's point-in-time members with the
$5 and 20M-dollar screen, the SPY 200-day trend switch, monthly, fractional shares at Gotrade's real
fees. Bars are split- and dividend-adjusted. Reads only bars dated <= d.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20, N20_NOTREND
from seer_engine.lab.methods.m0091_lottery_avoidance import targets_from_rows
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

Score = Literal["combo", "max5", "rev1m", "random"]
Side = Literal["high", "low"]
_SCORES: tuple[str, ...] = ("combo", "max5", "rev1m", "random")
_SIDES: tuple[str, ...] = ("high", "low")
W = 21  # one trading month of daily returns
DECAY = 0.9
CLIP = 0.5


@dataclass(frozen=True, slots=True)
class ProfileParams:
    """``inner`` is F4's screen, trend gate and book size; ``score`` and ``side`` pick the ranking."""

    inner: FactorParams
    score: Score = "combo"
    side: Side = "low"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if self.score not in _SCORES:
            raise ValueError(f"score must be one of {_SCORES}, got {self.score!r}")
        if self.side not in _SIDES:
            raise ValueError(f"side must be one of {_SIDES}, got {self.side!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"score": self.score, "side": self.side}
        for key, v in self.inner.as_dict().items():
            out[f"inner.{key}"] = v
        return out


def _check(params: object) -> ProfileParams:
    if not isinstance(params, ProfileParams):
        raise TypeError(f"params must be ProfileParams, got {type(params).__name__}")
    return params


def profile_lookback(params: ProfileParams) -> int:
    return max(factor_lookback(params.inner), W + 1)


def _features(close: np.ndarray) -> np.ndarray | None:
    """The 42 inputs from W+1 closes: returns in calendar order, then the same returns sorted."""
    if not (np.all(np.isfinite(close)) and np.all(close > 0.0)):
        return None
    r = np.clip(close[1:] / close[:-1] - 1.0, -CLIP, CLIP)
    return np.concatenate([r, np.sort(r)])


@dataclass
class ProfilePrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)


def _raw(h: History, data_date: date, score: str) -> tuple[float, float] | float | None:
    """(chrono, rank) for ``combo``, else the single raw number; None when the window is unusable."""
    i = h.index_of(data_date)
    if i is None or i < W:
        return None
    x = _features(h.close[i - W : i + 1])
    if x is None:
        return None
    chrono = float(np.sum(DECAY ** np.arange(W)[::-1] * x[:W]))
    rank = float(np.mean(x[W:][-5:]))
    if score == "combo":
        return chrono, rank
    if score == "max5":
        return rank
    if score == "rev1m":
        return float(np.prod(1.0 + x[:W]) - 1.0)
    digest = hashlib.sha256(f"{h.symbol}|{data_date.isoformat()}".encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2.0**64


def _pct(v: np.ndarray) -> np.ndarray:
    """Percentile of each value among the screened names, ties sharing their mean rank."""
    order = v.argsort(kind="stable")
    r = np.empty(len(v))
    r[order] = np.arange(len(v), dtype=float)
    for u in np.unique(v):
        m = v == u
        if m.sum() > 1:
            r[m] = r[m].mean()
    return r / max(len(v) - 1, 1)


def choose(rows: list[FactorRow], prepared: ProfilePrepared, data_date: date,
           p: ProfileParams) -> list[FactorRow]:
    kept: list[tuple[FactorRow, Any]] = []
    for r in rows:
        h = prepared.history.get(r.symbol)
        if r.symbol in EXCLUDED or h is None:
            continue
        raw = _raw(h, data_date, p.score)
        if raw is not None:
            kept.append((r, raw))
    if not kept:
        return []
    if p.score == "combo":
        a = np.array([raw[0] for _, raw in kept])
        b = np.array([raw[1] for _, raw in kept])
        s = _pct(a) + _pct(b)
    else:
        s = np.array([raw for _, raw in kept], dtype=float)
    if p.side == "high":
        s = -s
    order = sorted(range(len(kept)), key=lambda k: (s[k], kept[k][0].symbol))
    return [kept[k][0] for k in order[: p.inner.top]]


class ProfileAllocator:
    """F4's book ranked on one score of the last month's daily returns.

    Held symbols get no special treatment: a name that leaves the chosen set is signal-exited.
    """

    id = "M0353"

    def lookback(self, params: Any) -> int:
        return profile_lookback(_check(params))

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


PROFILE = ProfileAllocator()


def _v(suffix: str, params: ProfileParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0353-{suffix}", family="M0353", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=PROFILE, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0353",
    name=("One score from the whole month of daily returns: extremes and recent days both "
          "counted, instead of the single max day or the monthly total"),
    family="stock-daily-return-profile",
    source_kind="paper",
    source_ref=(
        "Cakici, Fieberg, Neszveda, Bianchi and Zaremba (2026), A Unified Framework for Anomalies "
        "Based on Daily Returns, SSRN 6005614, doi:10.2139/ssrn.6005614 (full text not opened: "
        "definition taken from agreeing search summaries; estimator replaced by a fixed blend)"
    ),
    parent_id=None,
    hypothesis=(
        "MAX and one-month reversal read the same prior-month daily returns, and each alone failed "
        "in this lab on large caps (M0091's lowest-MAX book tied SPY and fell 30%, M0028's "
        "calm-faller book tied SPY and fell 27%). The paper (January 2026, so fresh; its 1937-2024 "
        "all-stock sample includes small caps this lab cannot hold) says one score built from all "
        "21 daily returns, in calendar order and sorted by size, subsumes both. Its estimator, an "
        "elastic net refit yearly, cannot run inside the lab's bounded-lookback contract, so this "
        "tests the idea and not the estimator: score = percentile of a decay-weighted sum of the "
        "21 returns (weight 0.9 per day of age, newest heaviest) plus percentile of the mean of "
        "the five largest, equal parts, no fitted number. Hold the 20 lowest scores (a recent "
        "loser with no lottery spike, the two published signs) among F4-screened point-in-time "
        "index members at 5% each, behind the SPY 200-day switch, monthly, fractional shares at "
        "Gotrade's real fees. Arms on the same chassis: COMBO-LO-N20-T (the book); COMBO-HI-N20-T "
        "(the mirror, highest scores, must trail); COMBO-LO-N20 (always invested, no switch: the "
        "third arm that prices the habit of acting behind the switch); MAX5-LO-N20-T (plain MAX); "
        "REV1M-LO-N20-T (plain one-month reversal, the 20 weakest last month); RAND-N20-T "
        "(pseudo-random ranking: the draw-noise yardstick). To count, the book must beat SPY TR "
        "on dev within the 20% limit, beat both plain arms and the random arm on its own, "
        "trail its mirror, and be positive in 2009-2015."
    ),
    expected_failure=(
        "The paper's edge is a spread between decile extremes across all stocks, much of it in "
        "small illiquid names; among 500 large index members the spread is narrow and a 20-name "
        "book is mostly noise plus SPY's trend switch. A fixed equal blend of the two parts is a "
        "guess at the weights the paper learned and may mostly reload one-month reversal, which "
        "this lab has seen only tie SPY. Equal weighting inside the index tilts small against "
        "SPY's big-company drift, and a monthly 20-name book pays several times SPY's fees. Expect "
        "the random arm to land within draw noise of the book and the always-invested arm to show "
        "the switch, not the score, drove the result. Worst fall likely above 20% as with M0091 "
        "and M0093."
    ),
    candidates=(
        _v("COMBO-LO-N20-T", ProfileParams(N20, "combo", "low"),
           "Lowest joint score of recent days and extremes, behind the switch: the book"),
        _v("COMBO-HI-N20-T", ProfileParams(N20, "combo", "high"),
           "Highest joint score, behind the switch: the mirror, expected to trail"),
        _v("COMBO-LO-N20", ProfileParams(N20_NOTREND, "combo", "low"),
           "Lowest joint score, always invested: prices the switch and its churn"),
        _v("MAX5-LO-N20-T", ProfileParams(N20, "max5", "low"),
           "The 20 lowest mean-of-top-5-days members: plain MAX, which the joint score must beat"),
        _v("REV1M-LO-N20-T", ProfileParams(N20, "rev1m", "low"),
           "The 20 weakest last-month members: plain reversal, which the joint score must beat"),
        _v("RAND-N20-T", ProfileParams(N20, "random", "low"),
           "A deterministic pseudo-random 20 on the same chassis: draw-noise yardstick"),
    ),
    seen_keys=(
        "concept:daily-return-profile",
        "concept:max-effect",
        "concept:one-month-reversal",
    ),
)

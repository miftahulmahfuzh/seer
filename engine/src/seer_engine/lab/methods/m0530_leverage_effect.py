"""M0530 — The leverage effect in the cross-section: stocks that get jumpier exactly when they fall.

Source: Doshi et al. (2026 working paper), "The leverage effect in the cross-section". Brand new, so
no crowd has had time to trade it, but the dev window ends 2015 and can only show the pre-paper
years. For each stock, over the last 252 of its own bars:

    score = corr( daily log return r_t , next-day change in Parkinson volatility pv_{t+1} - pv_t )

where pv_t = ln(high_t / low_t) / (2 * sqrt(ln 2)), the range-based daily volatility. The paper
argues the most negative correlations are the riskiest (volatility jumps just as the price drops)
and should be paid for it. M0522 ranked the market's down days and M0468 the volatility of
volatility; this ranks the stock's *own* return-volatility link, which the lab has not read.

The book holds the ``top`` most negative (or, for the mirror, most positive) among F4-screened
point-in-time members behind SPY's 200-day switch, monthly, fractional shares at Gotrade's real
fees. A held name stays while it ranks within ``top + KEEP_BAND``. Reads only bars dated <= d.
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

ADDED = date(2026, 11, 9)

Side = Literal["negative", "positive"]
_SIDES: tuple[str, ...] = ("negative", "positive")
W = 252
MIN_BARS = 200
KEEP_BAND = 10
CLIP = 0.5
_PARK = 1.0 / (2.0 * np.sqrt(np.log(2.0)))


@dataclass(frozen=True, slots=True)
class LevParams:
    """``inner`` is F4's screen, trend gate and book size; ``side`` picks the most negative or most
    positive return/volatility correlation; ``shuffle`` swaps the score for a pseudo-random draw."""

    inner: FactorParams
    side: Side = "negative"
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


def _check(params: object) -> LevParams:
    if not isinstance(params, LevParams):
        raise TypeError(f"params must be LevParams, got {type(params).__name__}")
    return params


def _score(h: History, data_date: date, p: LevParams) -> float | None:
    i = h.index_of(data_date)
    if i is None or i < W + 1:
        return None
    if p.shuffle:
        digest = hashlib.sha256(f"{h.symbol}|{data_date.isoformat()}".encode()).digest()
        return int.from_bytes(digest[:8], "big") / 2.0**64
    c = h.close[i - W : i + 1]
    hi = h.high[i - W : i + 1]
    lo = h.low[i - W : i + 1]
    if not (np.all(np.isfinite(c)) and np.all(c > 0.0) and np.all(np.isfinite(hi))
            and np.all(np.isfinite(lo)) and np.all(lo > 0.0) and np.all(hi >= lo)):
        return None
    pv = np.log(hi / lo) * _PARK
    r = np.clip(np.log(c[1:] / c[:-1]), -CLIP, CLIP)  # r[k] is the return on bar k+1
    dv = pv[2:] - pv[1:-1]  # change from bar k+1 to bar k+2
    r = r[:-1]
    if len(r) < MIN_BARS or float(np.std(r)) == 0.0 or float(np.std(dv)) == 0.0:
        return None
    return float(np.corrcoef(r, dv)[0, 1])


def choose(rows: list[FactorRow], history: Mapping[str, History], data_date: date,
           held: frozenset[str], p: LevParams) -> list[FactorRow]:
    kept: list[tuple[FactorRow, float]] = []
    for r in rows:
        h = history.get(r.symbol)
        if r.symbol in EXCLUDED or h is None:
            continue
        s = _score(h, data_date, p)
        if s is not None and np.isfinite(s):
            kept.append((r, s))
    sign = 1.0 if p.side == "negative" else -1.0
    kept.sort(key=lambda t: (sign * t[1], t[0].symbol))
    ranked = [r for r, _ in kept]
    top = p.inner.top
    keep = [r for r in ranked[: top + KEEP_BAND] if r.symbol in held][:top]
    have = {r.symbol for r in keep}
    for r in ranked:
        if len(keep) >= top:
            break
        if r.symbol not in have:
            keep.append(r)
            have.add(r.symbol)
    return keep


class LeverageAllocator:
    """F4's book ranked on each stock's return/next-day-volatility-change correlation."""

    id = "M0530"

    def lookback(self, params: Any) -> int:
        return max(factor_lookback(_check(params).inner), W + 2)

    def symbols(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

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
        return targets_from_rows(choose(rows, history, data_date, held, p), p)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, ProfilePrepared):
            raise TypeError(f"prepared must be ProfilePrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        rows = prepared.factor.rows_on(members, data_date, p.inner)
        return targets_from_rows(choose(rows, prepared.history, data_date, held, p), p)


LEV = LeverageAllocator()


def _v(suffix: str, params: LevParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0530-{suffix}", family="M0530", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=LEV, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0530",
    name="Stocks whose swings jump when they fall: rank members by how tightly their daily losses line up with rising volatility (the leverage effect)",
    family="stock-leverage-effect",
    source_kind="paper",
    source_ref="Doshi et al. (2026 working paper), The leverage effect in the cross-section, bauer.uh.edu/hdoshi/docs/DJS_LeverageEffect_2026.pdf",
    hypothesis=(
        "Doshi et al. (2026) leverage effect. Over each stock's last 252 sessions, correlate its "
        "daily log return with the next-day change in its Parkinson range volatility. The paper "
        "argues the most negative correlations are the riskiest (jumpier exactly when they fall) "
        "and earn more. Hold the 20 most negative among F4-screened point-in-time members behind "
        "SPY's 200-day switch, monthly, with a keep band (a held name stays while it ranks in the "
        "top 30), fractional shares at Gotrade's real fees on the owner's top-up "
        "(MONTHLY_HOLD_FRAC_GOTRADE; 20 names need fractions at a 20M IDR start). Arms: NEG-T "
        "(treatment); POS-T (mirror, most positive: must trail if the statistic matters); NEG "
        "(always invested, no switch: the no-opinion arm that prices the habit; it may book-twin "
        "an earlier host and is not a new book); RAND-T (a hash-drawn 20 on the same chassis and "
        "band, ONE draw, so only a yardstick and not a control with a width; it likely twins "
        "M0520-RAND-T's family of draws). Assumption written now: the matched-entry-count draw "
        "in the idea draft is replaced by the standing hash draw, because matching turnover "
        "needs a weight rule this chassis lacks. Never ranked in this lab (nearest: M0522 "
        "downside beta, coskewness, M0468 vol-of-vol). Published 2026, after the dev window, so "
        "no fade is visible; judge 2009-2015 first. To count, NEG-T must beat SPY TR within the "
        "20% limit, beat RAND-T by more than draw noise, trail its mirror, be positive in "
        "2009-2015."
    ),
    expected_failure=(
        "The score is a volatility/size proxy: stocks with strongly negative return-volatility "
        "correlation are the ones with big down moves, which are the high-beta names, so the book "
        "lands inside the blind draw's width, or it is the downside-beta book M0522 already "
        "measured dead (7.4% a year vs SPY 7.2%, fell 36%). Expect the switch, not the score, to "
        "do the work, a lag to SPY in 2009-2015, and a mirror that does as well."
    ),
    candidates=(
        _v("NEG-T", LevParams(N20, "negative"),
           "Most negative return/volatility-change correlation, top 20 behind the switch: the treatment"),
        _v("POS-T", LevParams(N20, "positive"),
           "Mirror, most positive 20: must trail if the statistic carries information"),
        _v("NEG", LevParams(N20_NOTREND, "negative"),
           "Always invested, no switch: prices the switch and its churn"),
        _v("RAND-T", LevParams(N20, "negative", True),
           "Hash-drawn 20 on the same chassis and band: one-draw yardstick, not a control"),
    ),
    seen_keys=(
        "concept:leverage-effect-cross-section",
        "concept:return-volatility-correlation-ranking",
    ),
)

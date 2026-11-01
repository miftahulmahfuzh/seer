"""M0438 — A signed jump-return sort on the index members.

Source: Jiang and Yao (2013), "Stock Price Jumps and Cross-Sectional Return Predictability",
JFQA 48(5). They find that stocks whose past year was dominated by large positive jump days
earn less afterwards (and the reverse), a signed measure that is neither momentum nor the
share-of-gain filter queued as M0436. Published 2013, so the dev window (to 2015) holds almost
no out-of-sample years of it, and any edge is likely to have faded since.

The frame is M0432's: point-in-time members, the F4 screen, 20 equal slots, monthly, fractional
shares at Gotrade's real fees, SPY's 200-day switch on four arms. Unlike M0432 the sort is
standalone: the pool is every screened member, not the top-momentum 40. The key is the sum of
daily simple returns on the days of the last 252 whose absolute return exceeded three times
the standard deviation of that same window's daily returns. A name with no such day scores 0.
Names with a missing bar or a non-positive price are not scored, in every arm alike.

Arms (six, the lab's cap): LOW holds the 20 lowest jump sums, HIGH the 20 highest (the mirror),
R1 and R2 draw 20 of the same pool by hash, LOW-NOSW and R1-NOSW are the two with no switch.
R1-NOSW is the always-invested arm with no opinion in it, so the lab can price what the switch
and the sort each add (the dressing question) instead of only telling signal from luck.
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
WIN = 252  # bars in the jump window
K = 3.0  # a jump is a day beyond K standard deviations of the window
MARKET = "SPY"

NOSW = replace(N20, trend=None)


@dataclass(frozen=True, slots=True)
class JumpParams:
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
        out = {"mode": self.mode, "seed": str(self.seed), "win": str(WIN), "k": str(K)}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> JumpParams:
    if not isinstance(params, JumpParams):
        raise TypeError(f"params must be JumpParams, got {type(params).__name__}")
    return params


def scored_names(history: Mapping[str, History], symbols: list[str], data_date: date
                 ) -> dict[str, float]:
    """Sum of simple daily returns on jump days over the last WIN returns.

    Needs WIN + 1 closes ending on data_date. Names with a missing bar, a non-positive price or
    zero return variance are not scored."""
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
        r = c[1:] / c[:-1] - 1.0
        sd = float(np.std(r))
        if sd <= 0.0:
            continue
        out[s] = float(r[np.abs(r) > K * sd].sum())
    return out


def choose(rows: list[FactorRow], score: dict[str, float], params: JumpParams) -> list[FactorRow]:
    pool = [r for r in rows if r.symbol not in EXCLUDED and r.symbol in score]
    if params.mode == "low":
        key = {r.symbol: score[r.symbol] for r in pool}
    elif params.mode == "high":
        key = {r.symbol: -score[r.symbol] for r in pool}
    else:
        key = {r.symbol: float(draw(params.seed, r.symbol)) for r in pool}
    pool.sort(key=lambda r: (key[r.symbol], r.symbol))
    return pool[: params.inner.top]

@dataclass
class JumpPrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)
    cache: dict[date, dict[str, float]] = field(default_factory=dict, repr=False)


class JumpAllocator:
    """The lab's index-member book ranked on its signed jump-return sum."""

    id = "M0438"

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

    def _run(self, prepared: JumpPrepared | None, history: Mapping[str, History],
             members: AbstractSet[str], data_date: date, p: JumpParams) -> tuple[Target, ...]:
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

    def prepare(self, history: Mapping[str, History]) -> JumpPrepared:
        return JumpPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, JumpPrepared):
            raise TypeError(f"prepared must be JumpPrepared, got {type(prepared).__name__}")
        return self._run(prepared, prepared.history, members, data_date, _check(params))


JUMP = JumpAllocator()


def _v(suffix: str, params: JumpParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0438-{suffix}", family="M0438",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=JUMP, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0438",
    name=("Signed jump returns as a standalone sort: last year's sum of days that moved more "
          "than three times the stock's usual swing"),
    family="stock-jump-return",
    source_kind="paper",
    source_ref="Jiang & Yao 2013, Stock Price Jumps and Cross-Sectional Return Predictability, JFQA 48(5)",
    parent_id=None,
    hypothesis=(
        "Jiang and Yao (2013): stocks whose past year was dominated by large positive jump days "
        "earn less afterwards, and those dominated by large negative jumps earn more. Rank the "
        "F4-screened point-in-time index members by the sum of daily returns on days beyond 3x "
        "the standard deviation of the last 252 daily returns, hold 20 equal slots, monthly, "
        "fractional shares at Gotrade's real fees. Arms: LOW (lowest jump sum, the paper's long "
        "leg), HIGH (the mirror), R1 and R2 (hash draws of 20 from the same pool, the blind "
        "pair), LOW-NOSW and R1-NOSW (no SPY switch; R1-NOSW is always invested with no opinion, "
        "the third arm that prices what acting costs). The other four sit behind SPY's 200-day "
        "switch. SUCCESS: LOW beats the better of R1 and R2 by more than the blind pair's "
        "spread plus 2 points a year, HIGH loses to it, with a positive 2009-2015 edge vs SPY. "
        "Predictions, written now: LOW and HIGH differ by under 2 points a year; neither beats "
        "the blind draw; all trail SPY in 2009-2015; both NOSW arms fall past 35%."
    ),
    expected_failure=(
        "Three-sigma days are a handful per name per year, so the sum is dominated by one or two "
        "events and is mostly noise; the standalone pool of ~500 index names is mostly large "
        "caps whose jumps are earnings days, and the ranking proxies recent losers or volatility. "
        "With no momentum pool, the book is a plain equal-weight index slice and the switch, not "
        "the sort, does the work (M0412, M0425, M0432). Published 2013, so any dev edge is "
        "likely to fade out of sample."
    ),
    candidates=(
        _v("LOW", JumpParams(N20, "low"),
           "Lowest signed jump-return sum among screened members, behind the switch"),
        _v("HIGH", JumpParams(N20, "high"),
           "Highest jump-return sum: the reversed arm"),
        _v("R1", JumpParams(N20, "blind", 438),
           "Control: hash draw of 20 from the same pool, seed 438, behind the switch"),
        _v("R2", JumpParams(N20, "blind", 439),
           "Control: hash draw of 20 from the same pool, seed 439, behind the switch"),
        _v("LOW-NOSW", JumpParams(NOSW, "low"),
           "No-switch twin of LOW: always invested, prices the switch's habit"),
        _v("R1-NOSW", JumpParams(NOSW, "blind", 438),
           "Always invested, no opinion: blind draw with no switch, prices acting on either"),
    ),
    seen_keys=(
        "concept:signed-jump-return-sort",
    ),
)

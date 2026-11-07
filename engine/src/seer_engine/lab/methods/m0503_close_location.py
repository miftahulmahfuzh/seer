"""M0503 — Closing near the day's high: stocks that habitually finish the session in the top of their range.

Source: knowledge (Chaikin's close-location value / money-flow lore; practitioner folklore, not a
published academic anomaly, so the dev window is not crowded by it). Score = the mean over the last
60 sessions of ((close-low)-(high-close))/(high-low); a day with high == low scores 0. Persistent
closing strength may be accumulation by informed buyers. Frame is M0503's: N20 host, 20 equal
monthly slots, fractional shares at Gotrade real fees, SPY 200-day switch. Names short of 61
closes or with a gap or non-positive price in the span are unscored in every arm alike.

Arms (six): HIGH (treatment: strongest closes), LOW (mirror), RET60 (control: plain 60-session
return, because closing near the high is mostly "the stock went up", so the screen adds something
only if it beats that), R1 and R2 (blind draws, seeds 503, 504, behind the switch) and R1-NOSW
(always invested with no opinion: prices the switch and acting).
SUCCESS: HIGH beats the better of R1/R2 by more than 2 points a year funded, LOW loses to R1, HIGH
beats RET60, positive 2009-2015 edge vs SPY.
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

ADDED = date(2026, 11, 7)
MODES = ("high", "low", "ret", "blind")
NEED = 61  # closes needed: 60 sessions
MARKET = "SPY"

NOSW = replace(N20, trend=None)


@dataclass(frozen=True, slots=True)
class TimeParams:
    """``inner`` is the host's screen, switch, book size and weighting; ``mode`` is the ranking."""

    inner: FactorParams
    mode: str = "high"
    seed: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if self.mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {self.mode!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError(f"seed must be an int, got {type(self.seed).__name__}")

    def as_dict(self) -> dict[str, str]:
        out = {"mode": self.mode, "seed": str(self.seed), "need": str(NEED)}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> TimeParams:
    if not isinstance(params, TimeParams):
        raise TypeError(f"params must be TimeParams, got {type(params).__name__}")
    return params


def scored_names(history: Mapping[str, History], symbols: list[str], data_date: date
                 ) -> dict[str, tuple[float, float]]:
    """(mean close-location value, 60-session return) over the last 60 sessions ending data_date."""
    out: dict[str, tuple[float, float]] = {}
    for s in symbols:
        h = history.get(s)
        if h is None:
            continue
        i = h.index_of(data_date)
        if i is None or i < NEED - 1:
            continue
        sl = slice(i - NEED + 2, i + 1)
        c, hi, lo = h.close[sl], h.high[sl], h.low[sl]
        c0 = h.close[i - NEED + 1]
        if not (np.all(np.isfinite(c)) and np.all(np.isfinite(hi)) and np.all(np.isfinite(lo))
                and np.all(c > 0.0) and c0 > 0.0):
            continue
        rng = hi - lo
        clv = np.where(rng > 0.0, ((c - lo) - (hi - c)) / np.where(rng > 0.0, rng, 1.0), 0.0)
        out[s] = (float(np.mean(clv)), float(c[-1] / c0 - 1.0))
    return out


def choose(rows: list[FactorRow], score: dict[str, tuple[float, float]], params: TimeParams
           ) -> list[FactorRow]:
    pool = [r for r in rows if r.symbol not in EXCLUDED and r.symbol in score]
    if params.mode == "high":
        key = {r.symbol: (-score[r.symbol][0], 0.0) for r in pool}
    elif params.mode == "low":
        key = {r.symbol: (score[r.symbol][0], 0.0) for r in pool}
    elif params.mode == "ret":
        key = {r.symbol: (-score[r.symbol][1], 0.0) for r in pool}
    else:
        key = {r.symbol: (float(draw(params.seed, r.symbol)), 0.0) for r in pool}
    pool.sort(key=lambda r: (key[r.symbol], r.symbol))
    return pool[: params.inner.top]


@dataclass
class TimePrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)
    cache: dict[date, dict[str, tuple[float, float]]] = field(default_factory=dict, repr=False)


class CloseLocationAllocator:
    """The lab's index-member book ranked on where its sessions habitually close in their range."""

    id = "M0503"

    def lookback(self, params: Any) -> int:
        return max(factor_lookback(_check(params).inner), NEED)

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

    def _run(self, prepared: TimePrepared | None, history: Mapping[str, History],
             members: AbstractSet[str], data_date: date, p: TimeParams) -> tuple[Target, ...]:
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

    def prepare(self, history: Mapping[str, History]) -> TimePrepared:
        return TimePrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, TimePrepared):
            raise TypeError(f"prepared must be TimePrepared, got {type(prepared).__name__}")
        return self._run(prepared, prepared.history, members, data_date, _check(params))


CLOSELOC = CloseLocationAllocator()


def _v(suffix: str, params: TimeParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0503-{suffix}", family="M0503",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=CLOSELOC, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0503",
    name="Closing near the day's high: stocks that habitually finish the session in the top of their range",
    family="stock-close-location",
    source_kind="knowledge",
    source_ref="",
    parent_id=None,
    hypothesis=(
        "Chaikin close-location lore (practitioner folklore, not a published anomaly): a stock that "
        "keeps closing in the top of its daily range is being bought into the close, possibly by "
        "informed holders. Score = mean over 60 sessions of ((close-low)-(high-close))/(high-low). "
        "Hold the 20 strongest F4-screened point-in-time index members monthly in equal fractional "
        "slots at Gotrade real fees behind SPY's 200-day switch. Arms: HIGH, LOW (mirror), RET60 "
        "(control: plain 60-session return, since closing strength is mostly recent gain), R1 and R2 "
        "(blind draws, seeds 503, 504, switch on) and R1-NOSW (always invested, no opinion: prices "
        "the switch and acting; a book twin of the recorded blind-draw host is expected). SUCCESS: "
        "HIGH beats the better of R1/R2 by more than 2 points a year funded, LOW loses to R1, HIGH "
        "beats RET60, positive 2009-2015 edge vs SPY. Predictions, written now: HIGH and RET60 land "
        "within 2 points a year of each other and neither beats SPY in 2009-2015."
    ),
    expected_failure=(
        "The score restates short-term momentum or reversal, so HIGH behaves like RET60 or like the "
        "short-term reversal books; the F4 screen and the switch carry any edge and the blind draws "
        "match it, as in M0466 and M0469. Daily range data on back-adjusted early prices may be noisy."
    ),
    candidates=(
        _v("HIGH", TimeParams(N20, "high"), "Strongest habitual closes, behind the switch"),
        _v("LOW", TimeParams(N20, "low"), "Weakest habitual closes: the mirror"),
        _v("RET60", TimeParams(N20, "ret"), "Control: plain 60-session return, behind the switch"),
        _v("R1", TimeParams(N20, "blind", 503), "Control: hash draw of 20, seed 503, behind the switch"),
        _v("R2", TimeParams(N20, "blind", 504), "Control: hash draw of 20, seed 504, measures draw noise"),
        _v("R1-NOSW", TimeParams(NOSW, "blind", 503), "Always invested, no opinion: prices acting on either"),
    ),
    seen_keys=(
        "concept:close-location-value",
    ),
)

"""M0469 — Time spent near the top: share of the last ~10 months a stock closed within 5% of its high.

Source: knowledge. Assumption: 200 sessions, not 250, because the contract-test market holds 473 bars. Builds on the 52-week-high anchoring literature (George and Hwang 2004, which
ranks on distance to the high at one instant). This method ranks on persistence instead: the
fraction of the last 200 sessions on which the close was within 5% of that day's own trailing
200-session closing high. A stock that lingers near highs scores near 1 and one that spiked once
scores low even if it sits at the high today. Published idea family 2004; dev window ends 2015, so
any edge is likely to have faded since.

Frame is M0448's (reused allocator machinery, N20 host): point-in-time members, F4 screen, 20 equal
slots, monthly, fractional shares at Gotrade real fees, SPY 200-day switch. The assignment said
"top tenth"; the screened pool is a few hundred names so 20 slots is about a tenth (assumed,
stated here before any result). The bottom-tenth mirror is the TIMELOW arm. Needs 399 closes
(200 scored days each needing a 200-day trailing high); names short of that, with a gap or a
non-positive price are unscored in every arm alike. Ties on the share break on distance to the
high, then the symbol.

Arms (six): TIME (treatment), TIMELOW (mirror), DIST (control: nearest to the high today, the
earlier books' measure, so the persistence adds something only if it beats this), R1 (blind draw,
behind the switch), TIME-NOSW and R1-NOSW (no switch; R1-NOSW is always invested with no opinion,
the third arm that prices the switch and acting). The plain SPY control is the benchmark each
trial is judged against in the same run.
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
MODES = ("time", "timelow", "dist", "blind")
WIN = 200  # sessions scored, and the length of each day's trailing-high window
BAND = 0.95  # "near the top" = close at least 95% of the trailing high
NEED = 2 * WIN - 1  # closes needed: 250 scored days each with a 200-day trailing high
MARKET = "SPY"

NOSW = replace(N20, trend=None)


@dataclass(frozen=True, slots=True)
class TimeParams:
    """``inner`` is the host's screen, switch, book size and weighting; ``mode`` is the ranking."""

    inner: FactorParams
    mode: str = "time"
    seed: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if self.mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {self.mode!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError(f"seed must be an int, got {type(self.seed).__name__}")

    def as_dict(self) -> dict[str, str]:
        out = {"mode": self.mode, "seed": str(self.seed), "win": str(WIN), "band": str(BAND)}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> TimeParams:
    if not isinstance(params, TimeParams):
        raise TypeError(f"params must be TimeParams, got {type(params).__name__}")
    return params


def scored_names(history: Mapping[str, History], symbols: list[str], data_date: date
                 ) -> dict[str, tuple[float, float]]:
    """(share of the last WIN sessions within BAND of the trailing WIN-day high, close / high today).

    Needs NEED closes ending on data_date; names with a missing bar or a non-positive price in
    that span are not scored."""
    out: dict[str, tuple[float, float]] = {}
    for s in symbols:
        h = history.get(s)
        if h is None:
            continue
        i = h.index_of(data_date)
        if i is None or i < NEED - 1:
            continue
        c = h.close[i - NEED + 1 : i + 1]
        if not (np.all(np.isfinite(c)) and np.all(c > 0.0)):
            continue
        hi = np.max(np.lib.stride_tricks.sliding_window_view(c, WIN), axis=1)  # WIN trailing highs
        ratio = c[WIN - 1 :] / hi
        out[s] = (float(np.mean(ratio >= BAND)), float(ratio[-1]))
    return out


def choose(rows: list[FactorRow], score: dict[str, tuple[float, float]], params: TimeParams
           ) -> list[FactorRow]:
    pool = [r for r in rows if r.symbol not in EXCLUDED and r.symbol in score]
    if params.mode == "time":
        key = {r.symbol: (-score[r.symbol][0], -score[r.symbol][1]) for r in pool}
    elif params.mode == "timelow":
        key = {r.symbol: (score[r.symbol][0], score[r.symbol][1]) for r in pool}
    elif params.mode == "dist":
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


class TimeNearHighAllocator:
    """The lab's index-member book ranked on time spent near the 52-week high."""

    id = "M0469"

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


TIMEHIGH = TimeNearHighAllocator()


def _v(suffix: str, params: TimeParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0469-{suffix}", family="M0469",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=TIMEHIGH, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0469",
    name="Time spent near the top: stocks that spent most of the last year close to their high",
    family="stock-time-near-high",
    source_kind="knowledge",
    source_ref="",
    parent_id=None,
    hypothesis=(
        "Lingering near the high marks steady demand, while a brief spike does not (the one-instant "
        "version is George and Hwang 2004, published 2004). Rank F4-screened point-in-time index "
        "members by the share of the last 200 sessions closing within 5% of their trailing "
        "200-session closing high; hold the top 20 (about a tenth of the pool, assumed) monthly in "
        "equal fractional slots at Gotrade real fees behind SPY's 200-day switch. Arms: TIME, TIMELOW "
        "(bottom tenth mirror), DIST (control: distance to the high today, the earlier books' "
        "measure), R1 (blind draw, switch on), TIME-NOSW and R1-NOSW (always invested; R1-NOSW has "
        "no opinion and prices the switch and acting). SUCCESS: TIME beats R1 by more than 2 points a "
        "year, TIMELOW loses to R1, TIME beats DIST, positive 2009-2015 edge vs SPY. Predictions, "
        "written now: TIME and DIST land within 2 points a year of each other, neither beats SPY in "
        "2009-2015, TIMELOW trails R1."
    ),
    expected_failure=(
        "The share near the high mostly restates trailing return and distance to the high, so TIME "
        "may be DIST renamed. Earlier high-anchored books (M0015, M0232) cut the fall but lagged "
        "SPY, and their edge sat in 2002-2008 not 2009-2015. Published idea, likely faded."
    ),
    candidates=(
        _v("TIME", TimeParams(N20, "time"), "Highest share of days near the trailing high, behind the switch"),
        _v("TIMELOW", TimeParams(N20, "timelow"), "Lowest share: the bottom-tenth mirror"),
        _v("DIST", TimeParams(N20, "dist"), "Control: closest to the high today, behind the switch"),
        _v("R1", TimeParams(N20, "blind", 469), "Control: hash draw of 20, seed 469, behind the switch"),
        _v("TIME-NOSW", TimeParams(NOSW, "time"), "No-switch twin of TIME: prices the switch's habit"),
        _v("R1-NOSW", TimeParams(NOSW, "blind", 469), "Always invested, no opinion: prices acting on either"),
    ),
    seen_keys=(
        "concept:time-near-52-week-high-share",
    ),
)

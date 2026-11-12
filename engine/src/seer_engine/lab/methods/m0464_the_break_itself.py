"""M0464 — Calm a month ago, then a single day whose range jumps past that calm.

Source: variation of M0459. M0459 held names quiet against their own year and found the quiet
itself carries no edge over random picks behind the same switch ("the switch, not the ranking,
does the work"). This method drops the "still coiled today" idea and tests the trigger instead:
a name no wider than its own median day a month ago (quiet enough that today's range is still a
real expansion, not an extreme decile that, stacked with a jump and a trend filter, left almost
no qualifying name across the dev-window F4 pool — see below), whose latest day prints a
single-day range at least 15% past that month-ago level — a trigger day. Direction then comes
from ranking, not a second hard cutoff: among triggered names, the ones whose close sits highest
in that day's own high-low span are the strong-close breakouts; the ones whose close sits lowest
are the weak-close breaks. (An original design hard-filtered the quiet reading to the bottom
tenth and the close to the top/bottom fifth; that stack of three independent rarities left most
months with no qualifying name at all — a brittle combination, not evidence the underlying idea
is empty — so quiet is loosened to "not above its own median" and the close's position is read
as a ranking key instead, the same way M0459 ranked WIDE by percentile rather than adding another
threshold. The jump condition carries the real weight of "trigger" here.)

Frame: the lab's usual F4-screened member book, 20 equal slots (an unfilled slot stays cash),
monthly, fractional shares at Gotrade's real fees, behind SPY's 200-day switch on every arm but
one. "Quiet a month ago" reuses M0459's measure — 20-day average true range as a share of close,
percentile against the same name's own last 250 daily readings, taken ~21 trading days (one
month) before data_date. "The jump" is today's single-day range (high-low, as a share of today's
close) divided by that quiet level. "Above trend" (close above the 50-day mean) is the same
per-name filter M0459 used.

Arms (six, the lab's cap), each scored on the pool of names with both a quiet-month-ago reading
and a usable trigger day:
UP holds the triggered above-trend names, strongest close first (the idea). DOWN is the mirror:
the same pool, weakest close first. UP-ALL drops the above-trend condition from UP (does the
50-day rule carry it, as M0459's SQZ-ALL asked of coiling). R1 and R2 hash-rank the triggered
above-trend pool with no opinion on direction (chance spreads, priced on the same trend
condition, behind the switch). R1-NOSW is R1's order with no switch: the always-invested
no-opinion arm that prices the switch's habit apart from any opinion, so a UP/DOWN reversal (if
one appears) splits into signal and dressing.
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

ADDED = date(2026, 11, 12)

MODES = ("up", "down", "upall", "blind")
ATR_WIN = 20  # bars in the average true range
HIST = 250  # daily ATR readings the quiet-month-ago percentile ranks against
TREND_WIN = 50  # bars in the above-trend mean
MONTH_LAG = 21  # trading days back to "a month ago"
QUIET_AT = 0.50  # quiet-month-ago percentile ceiling: no wider than its own median day
JUMP_AT = 1.15  # today's range / quiet-month-ago level, floor
PNEED = HIST + ATR_WIN  # bars ending on the month-ago day the quiet reading needs
NEED = PNEED + MONTH_LAG  # bars ending on data_date the whole score needs
MARKET = "SPY"

NOSW = replace(N20, trend=None)


@dataclass(frozen=True, slots=True)
class TriggerParams:
    """``inner`` is the host's screen, switch, book size and weighting; ``mode`` is the ranking."""

    inner: FactorParams
    mode: str = "up"
    seed: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if self.mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {self.mode!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError(f"seed must be an int, got {type(self.seed).__name__}")

    def as_dict(self) -> dict[str, str]:
        out = {"mode": self.mode, "seed": str(self.seed), "atr_win": str(ATR_WIN),
               "hist": str(HIST), "trend_win": str(TREND_WIN), "month_lag": str(MONTH_LAG),
               "quiet_at": str(QUIET_AT), "jump_at": str(JUMP_AT)}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> TriggerParams:
    if not isinstance(params, TriggerParams):
        raise TypeError(f"params must be TriggerParams, got {type(params).__name__}")
    return params


def scored_names(history: Mapping[str, History], symbols: list[str], data_date: date
                 ) -> dict[str, tuple[float, float, float, bool]]:
    """(quiet-month-ago ATR20/close percentile, today's jump ratio, today's close location in
    its own high-low span, close above the 50-day mean)."""
    out: dict[str, tuple[float, float, float, bool]] = {}
    for s in symbols:
        h = history.get(s)
        if h is None:
            continue
        i = h.index_of(data_date)
        if i is None or i < NEED:
            continue
        j = i - MONTH_LAG
        hi = h.high[j - PNEED + 1 : j + 1]
        lo = h.low[j - PNEED + 1 : j + 1]
        c = h.close[j - PNEED : j + 1]
        th, tl, tc = h.high[i], h.low[i], h.close[i]
        if not (np.all(np.isfinite(hi)) and np.all(np.isfinite(lo)) and np.all(np.isfinite(c))
                and np.isfinite(th) and np.isfinite(tl) and np.isfinite(tc)):
            continue
        if not (np.all(lo > 0.0) and np.all(hi >= lo) and np.all(c > 0.0)
                and tl > 0.0 and th > tl and tc > 0.0):
            continue
        pc = c[:-1]
        tr = np.maximum(hi - lo, np.maximum(np.abs(hi - pc), np.abs(lo - pc))) / c[1:]
        csum = np.concatenate(([0.0], np.cumsum(tr)))
        atr = (csum[ATR_WIN:] - csum[:-ATR_WIN]) / ATR_WIN  # HIST+1 readings, last = month-ago
        quiet_level = float(atr[-1])
        if quiet_level <= 0.0:
            continue
        pct = float(np.mean(atr <= quiet_level))
        jump = float((th - tl) / tc) / quiet_level
        loc = float((tc - tl) / (th - tl))
        above = bool(tc > float(np.mean(h.close[i - TREND_WIN + 1 : i + 1])))
        out[s] = (pct, jump, loc, above)
    return out


def choose(rows: list[FactorRow], scores: dict[str, tuple[float, float, float, bool]],
           params: TriggerParams) -> list[FactorRow]:
    pool = [r for r in rows if r.symbol not in EXCLUDED and r.symbol in scores]
    mode = params.mode

    def triggered(sym: str) -> bool:
        pct, jump, _loc, _above = scores[sym]
        return pct <= QUIET_AT and jump >= JUMP_AT

    if mode == "up":
        pool = [r for r in pool if triggered(r.symbol) and scores[r.symbol][3]]
        key = {r.symbol: -scores[r.symbol][2] for r in pool}  # strongest close (highest loc) first
    elif mode == "down":
        pool = [r for r in pool if triggered(r.symbol) and scores[r.symbol][3]]
        key = {r.symbol: scores[r.symbol][2] for r in pool}  # weakest close (lowest loc) first
    elif mode == "upall":
        pool = [r for r in pool if triggered(r.symbol)]
        key = {r.symbol: -scores[r.symbol][2] for r in pool}
    else:
        pool = [r for r in pool if triggered(r.symbol) and scores[r.symbol][3]]
        key = {r.symbol: float(draw(params.seed, r.symbol)) for r in pool}
    pool.sort(key=lambda r: (key[r.symbol], r.symbol))
    return pool[: params.inner.top]


@dataclass
class TriggerPrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)
    cache: dict[date, dict[str, tuple[float, float, float, bool]]] = field(
        default_factory=dict, repr=False)


class TheBreakItselfAllocator:
    """The lab's index-member book ranked on a single day's range jumping past a month-ago calm."""

    id = "M0464"

    def lookback(self, params: Any) -> int:
        return max(factor_lookback(_check(params).inner), NEED + 1)

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

    def _run(self, prepared: TriggerPrepared | None, history: Mapping[str, History],
             members: AbstractSet[str], data_date: date, p: TriggerParams) -> tuple[Target, ...]:
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

    def prepare(self, history: Mapping[str, History]) -> TriggerPrepared:
        return TriggerPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, TriggerPrepared):
            raise TypeError(f"prepared must be TriggerPrepared, got {type(prepared).__name__}")
        return self._run(prepared, prepared.history, members, data_date, _check(params))


TRIGGER = TheBreakItselfAllocator()


def _v(suffix: str, params: TriggerParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0464-{suffix}", family="M0464",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=TRIGGER, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0464",
    name="The break itself: calm stocks whose range suddenly jumps with a strong close",
    family="stock-volatility-compression",
    source_kind="variation",
    source_ref="M0459",
    parent_id="M0459",
    hypothesis=(
        "M0459 showed that a name merely sitting quiet against its own year carries no edge over "
        "random picks behind the same switch; the quiet itself was not the signal. This method "
        "tests the trigger instead of the state: a name whose 20-day average true range (as a "
        "share of close) sat no wider than its own median of the last 250 daily readings a month "
        "ago (~21 trading days back; not an extreme decile — that, stacked with a jump and a "
        "trend filter, left the dev-window F4 pool with almost no qualifying name at all, see "
        "expected_failure), and whose latest day prints a high-low range at least 15% past that "
        "month-ago level — the trigger. Direction comes from ranking the triggered pool by where "
        "today's close sits in its own high-low span, strongest close first or weakest close "
        "first, rather than a further hard cutoff on top of the quiet and jump filters. Every "
        "month the book scores each F4-screened index member and holds the triggered above-trend "
        "names, up to 20 equal slots (an unfilled slot stays cash), monthly, fractional shares at "
        "Gotrade's real fees, behind SPY's 200-day switch. Arms: UP (the idea, strongest close "
        "first), DOWN (the mirror: the same pool, weakest close first, same costs, opposite "
        "opinion), UP-ALL (UP with no above-trend condition: does the 50-day rule carry it), R1 "
        "and R2 (hash order on the triggered above-trend pool, no opinion on direction, behind "
        "the same switch), R1-NOSW (R1's order, no switch: the no-opinion always-invested arm "
        "that prices the switch's habit apart from the opinion). Predictions, written now: UP "
        "beats DOWN on funded CAGR; UP beats the better of R1 and R2 by less than their spread "
        "plus 2 points a year, repeating M0459's pattern where the random control matched the "
        "idea; UP trails SPY in 2009-2015; the triggered pool is uncommon in index members, so UP "
        "often holds fewer than 20 names and sits partly in cash; R1-NOSW falls over 40%, so the "
        "switch and not the ranking carries the fall."
    ),
    expected_failure=(
        "The trigger is rarer than the state it is built from: a tighter version of this design "
        "(bottom-tenth quiet, a 2x jump, and a top/bottom-fifth close, all three stacked) left "
        "almost no month in the dev-window F4 pool with a single qualifying name, which is why "
        "quiet is read here as 'no wider than its own median' and direction as a ranking rather "
        "than a fourth cutoff. Even loosened, the book still sits partly in cash on a thin month, "
        "and the cash drag in a rising decade costs points a year on its own, independent of "
        "whether the trigger means anything. Where the pool is non-empty, the same calm-tilt-"
        "behind-the-switch result that beat M0459, M0348 and M0350's ideas likely repeats here "
        "too: the switch does the work, not the pick, so R1 or R2 matches or beats UP. Ranking by "
        "close location rather than filtering on it means a 'strong close' here can be a mild one "
        "in a thin month, diluting the shape the hypothesis is built on; a single day's wide range "
        "can also be plain noise on an illiquid or thinly-traded name rather than a real "
        "breakout, and back-adjusted early prices can carry high/low errors; names failing the "
        "high > low > 0 check at either the month-ago span or today's bar are dropped from every "
        "arm alike."
    ),
    candidates=(
        _v("UP", TriggerParams(N20, "up"),
           "No wider than its own median a month ago, today's range >= 1.15x that level, above "
           "the 50-day mean, strongest close first, behind the switch: the idea"),
        _v("DOWN", TriggerParams(N20, "down"),
           "Same trigger pool, weakest close first, behind the switch: the mirror"),
        _v("UP-ALL", TriggerParams(N20, "upall"),
           "UP with no above-trend condition, behind the switch: does the 50-day rule matter"),
        _v("R1", TriggerParams(N20, "blind", 464),
           "Control: hash-ranked triggered above-trend pool, seed 464, behind the switch"),
        _v("R2", TriggerParams(N20, "blind", 465),
           "Control: hash-ranked triggered above-trend pool, seed 465, behind the switch"),
        _v("R1-NOSW", TriggerParams(NOSW, "blind", 464),
           "No-opinion always-invested arm: R1's order with no switch, prices the switch's habit"),
    ),
    seen_keys=(
        "concept:volatility-breakout-trigger",
        "concept:range-expansion-strong-close",
    ),
)

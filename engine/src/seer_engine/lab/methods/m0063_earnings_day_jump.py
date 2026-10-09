"""M0063 — Ride the earnings-day jump: buy big caps after a high-volume up gap, hold two months.

Source: Brandt, Kishore, Santa-Clara & Venkatachalam (2008), Earnings announcements are full of
surprises (SSRN 909563); Mohrschladt & Baars (a big one-day jump tied to news keeps going, one
with no news reverses); Garfinkel & Sokobin (2006), JAR.
Idea: the store has no earnings dates, but an announcement in a big company leaves a footprint
in daily bars: an opening gap on volume several times the stock's normal, about once a quarter.
Brandt et al. show the three-day return around the announcement predicts a drift for about 60
trading days. This book buys the names whose latest news day was a strong up gap and holds each
while its event is younger than ``hold`` sessions; whatever the slots leave is held in SPY.

An *event* of stock s is a session t (bar index) with, all from bars t-``vol_base``..t+1:

    * volume ratio  v(t) = volume[t] / median(volume[t-vol_base .. t-1]); kept when
      ``vol_min`` is None or v >= vol_min, and ``vol_max`` is None or v < vol_max;
    * gap           open[t] / close[t-1] - 1 > ``gap_min``;
    * jump          (close[t+1] / close[t-1]) - (SPY's close on the same two dates, the same
                    ratio) >= ``jump_min``: the market-adjusted three-day return, days -1..+1.

On data date d (bar index i of s), the stock's live event is the most recent event t with
i - ``hold`` < t <= i - 1 (so t+1 <= i: nothing after d is read). Inside F4's liquidity and
membership screen (and behind its SPY-200 trend switch when ``inner.trend`` is set: all cash
while it is off), live events are ranked by jump, held names first (a name keeps its slot until
its event ages out or it leaves the screen), and the ``inner.top`` best are held at equal weight
1/top. ``park`` puts the weight the empty slots leave into SPY.

Every piece reads only bars dated <= d. ``prepare`` computes the per-bar event columns once per
symbol over its whole history; each column entry at t reads bars t-vol_base..t+1 and the book
only reads entries with t+1 <= i, so the prepared and unprepared paths agree.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20, N20_NOTREND, N30
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE, WEEKLY_HOLD
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    FactorParams,
    FactorPrepared,
    factor_lookback,
    factor_rows,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 10, 9)

# Weekly re-pick in fractional shares at Gotrade's real fees. No preset of this id exists yet:
# it runs on dev, and `promote` would need one (a feature-wish if it wins).
WEEKLY_HOLD_FRAC_GOTRADE = replace(WEEKLY_HOLD, id="weekly-hold-frac-gotrade", fractional=True,
                                   cost_model="gotrade")


# --------------------------------------------------------------------------- params


@dataclass(frozen=True, slots=True)
class JumpParams:
    """``inner`` is F4's screen, trend switch and book size; the rest defines the event."""

    inner: FactorParams
    vol_min: Decimal | None = Decimal("3")  # event volume >= vol_min x its median (None = no floor)
    vol_max: Decimal | None = None  # event volume < vol_max x its median (None = no cap)
    vol_base: int = 60  # sessions in the volume median, ending the session before the event
    gap_min: Decimal = Decimal("0")  # open over the prior close, strictly above this
    jump_min: Decimal = Decimal("0.04")  # market-adjusted return, close t-1 -> close t+1
    hold: int = 60  # an event stays live while younger than this many sessions
    park: bool = True  # empty slots hold SPY (while the trend switch, if any, is on)
    market: str = "SPY"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        for name in ("vol_min", "vol_max"):
            v = getattr(self, name)
            if v is not None and (not isinstance(v, Decimal) or not v.is_finite() or v <= 0):
                raise ValueError(f"{name} must be None or a positive Decimal, got {v!r}")
        if self.vol_min is not None and self.vol_max is not None and self.vol_max <= self.vol_min:
            raise ValueError("vol_max must be above vol_min")
        for name in ("gap_min", "jump_min"):
            v = getattr(self, name)
            if not isinstance(v, Decimal) or not v.is_finite():
                raise ValueError(f"{name} must be a finite Decimal, got {v!r}")
        for name, low in (("vol_base", 5), ("hold", 2)):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int) or v < low:
                raise ValueError(f"{name} must be an int >= {low}, got {v!r}")
        if not isinstance(self.park, bool):
            raise TypeError(f"park must be a bool, got {type(self.park).__name__}")
        if not isinstance(self.market, str) or not self.market:
            raise ValueError(f"market must be a non-empty symbol, got {self.market!r}")

    def as_dict(self) -> dict[str, str]:
        out = {
            "vol_min": "none" if self.vol_min is None else str(self.vol_min),
            "vol_max": "none" if self.vol_max is None else str(self.vol_max),
            "vol_base": str(self.vol_base),
            "gap_min": str(self.gap_min),
            "jump_min": str(self.jump_min),
            "hold": str(self.hold),
            "park": str(self.park).lower(),
            "market": self.market,
        }
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> JumpParams:
    if not isinstance(params, JumpParams):
        raise TypeError(f"params must be JumpParams, got {type(params).__name__}")
    return params


def jump_lookback(params: JumpParams) -> int:
    return max(factor_lookback(params.inner), params.hold + params.vol_base + 2)


# --------------------------------------------------------------------------- the event columns


@dataclass(frozen=True, slots=True)
class EventCols:
    """Per bar t of one symbol: volume ratio, gap and market-adjusted jump (NaN when unknown)."""

    vratio: np.ndarray
    gap: np.ndarray
    jump: np.ndarray


def event_cols(h: History, market: History | None, vol_base: int) -> EventCols:
    """Each entry at t reads bars t-vol_base..t+1 of ``h`` and the market's closes on those dates."""
    n = len(h)
    vratio = np.full(n, np.nan)
    gap = np.full(n, np.nan)
    jump = np.full(n, np.nan)
    if n < vol_base + 2 or market is None:
        return EventCols(vratio, gap, jump)
    vol = h.volume
    med = np.median(sliding_window_view(vol[:-1], vol_base), axis=1)  # med[k] = median(vol[k..k+vb-1])
    t = np.arange(vol_base, n)
    base = med[t - vol_base]
    with np.errstate(divide="ignore", invalid="ignore"):
        vratio[t] = np.where(base > 0, vol[t] / base, np.nan)
        gap[1:] = h.open[1:] / h.close[:-1] - 1.0
        # market closes on this symbol's dates (NaN where the market has no bar that day)
        pos = np.searchsorted(market.dates, h.dates)
        ok = (pos < len(market)) & (market.dates[np.minimum(pos, len(market) - 1)] == h.dates)
        mclose = np.where(ok, market.close[np.minimum(pos, len(market) - 1)], np.nan)
        s = h.close[2:] / h.close[:-2]
        m = mclose[2:] / mclose[:-2]
        jump[1:-1] = s - m
    for arr in (vratio, gap, jump):
        arr[~np.isfinite(arr)] = np.nan
    return EventCols(vratio, gap, jump)


class JumpPrepared:
    """The F4 columns plus each symbol's event columns, computed on first use and cached."""

    def __init__(self, history: Mapping[str, History], factor: FactorPrepared | None) -> None:
        self.history = history
        self.factor = factor
        self._cache: dict[tuple[str, str, int], EventCols] = {}

    def cols(self, symbol: str, market: str, vol_base: int) -> EventCols | None:
        key = (symbol, market, vol_base)
        if key not in self._cache:
            h = self.history.get(symbol)
            if h is None:
                return None
            self._cache[key] = event_cols(h, self.history.get(market), vol_base)
        return self._cache[key]


def live_jump(cols: EventCols, i: int, p: JumpParams) -> float | None:
    """The jump of the most recent event t with i - hold < t <= i - 1, or None."""
    lo = max(i - p.hold + 1, p.vol_base)
    hi = i - 1
    if hi < lo:
        return None
    v = cols.vratio[lo : hi + 1]
    g = cols.gap[lo : hi + 1]
    j = cols.jump[lo : hi + 1]
    ok = np.isfinite(v) & np.isfinite(g) & np.isfinite(j)
    if p.vol_min is not None:
        ok &= v >= float(p.vol_min)
    if p.vol_max is not None:
        ok &= v < float(p.vol_max)
    ok &= g > float(p.gap_min)
    ok &= j >= float(p.jump_min)
    idx = np.flatnonzero(ok)
    if idx.size == 0:
        return None
    return float(j[idx[-1]])


# --------------------------------------------------------------------------- the allocator


class EarningsJumpAllocator:
    """Names whose latest news day was a strong up gap, held while the event is live; rest in SPY.

    Held names keep their slot ahead of new ones while their event is live and they pass the
    screen; the remaining slots go to the biggest live jumps.
    """

    id = "M0063"

    def lookback(self, params: Any) -> int:
        return jump_lookback(_check(params))

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        fixed = {p.market}
        if p.inner.trend is not None:
            fixed.add(p.inner.trend[0])
        return tuple(sorted(fixed))

    def holds(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return (p.market,) if p.park else ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _targets(self, prepared: JumpPrepared, rows: list[Any], data_date: date,
                 held: frozenset[str], p: JumpParams) -> tuple[Target, ...]:
        live: list[tuple[int, float, str]] = []
        for r in rows:
            h = prepared.history.get(r.symbol)
            if h is None or r.symbol == p.market:
                continue
            i = h.index_of(data_date)
            cols = prepared.cols(r.symbol, p.market, p.vol_base)
            if i is None or cols is None:
                continue
            j = live_jump(cols, i, p)
            if j is None:
                continue
            live.append((0 if r.symbol in held else 1, -j, r.symbol))
        w = equal_weight(p.inner.top)
        out: list[Target] = []
        for _, _, s in sorted(live)[: p.inner.top]:
            t = target_from_close(s, last_close(prepared.history[s], data_date), w)
            if t is not None:
                out.append(t)
        if p.park:
            rest = Decimal(1) - w * len(out)
            mh = prepared.history.get(p.market)
            if rest > 0 and mh is not None and mh.index_of(data_date) is not None:
                t = target_from_close(p.market, last_close(mh, data_date), rest)
                if t is not None:
                    out.append(t)
        return tuple(out)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if not trend_on(history, data_date, p.inner):
            return ()
        rows = factor_rows(history, members, data_date, p.inner)
        return self._targets(JumpPrepared(history, None), rows, data_date, held, p)

    def prepare(self, history: Mapping[str, History]) -> JumpPrepared:
        return JumpPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, JumpPrepared) or prepared.factor is None:
            raise TypeError(f"prepared must be a prepared JumpPrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        rows = prepared.factor.rows_on(members, data_date, p.inner)
        return self._targets(prepared, rows, data_date, held, p)


JUMP = EarningsJumpAllocator()


def _v(suffix: str, params: JumpParams, rationale: str, rules=WEEKLY_HOLD_FRAC_GOTRADE) -> Candidate:
    return Candidate(id=f"M0063-{suffix}", family="M0063", rules=rules, allocator=JUMP,
                     params=params, rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0063",
    name="Ride the earnings-day jump: buy big caps after a high-volume up gap, hold two months",
    family="stock-event-drift",
    source_kind="paper",
    source_ref="Brandt, Kishore, Santa-Clara & Venkatachalam (2008), Earnings announcements are "
               "full of surprises, SSRN 909563; Mohrschladt & Baars (MAX reverses unless tied to "
               "an announcement); Garfinkel & Sokobin (2006), JAR",
    parent_id=None,
    hypothesis=(
        "Published 2008, so the dev window (to 2015) can only show the edge from before and "
        "just after it was widely known; 2009-2015 is judged first. The store has no earnings "
        "dates, but an announcement in a big company leaves a footprint in daily bars: an "
        "opening gap on volume at least 3 times the stock's 60-day median. Brandt et al. show "
        "the three-day return around the announcement predicts a drift for about 60 trading "
        "days, and Mohrschladt and Baars find a big jump tied to news keeps going. So: inside "
        "F4's liquidity and membership screen, a stock qualifies when, in the last 60 sessions, "
        "it had a day with volume >= 3x its median, an up gap at the open, and a three-day "
        "return (day before to day after) at least 4 points above SPY's over the same days. The "
        "book holds up to 20 such names at 5% each (the biggest jumps first, held names keep "
        "their slot while their event is live), re-picked weekly, and puts the rest in SPY; it "
        "ranks on a news event, not on a year of past returns, so it should move apart from the "
        "failed momentum books. Fractional shares at Gotrade's real fees (weekly-hold-frac-"
        "gotrade, an assumed preset: replace(WEEKLY_HOLD, fractional, gotrade); M-N20-TREND "
        "runs the same signal on the existing monthly-hold-frac-gotrade preset). Variants: "
        "N20-TREND (behind the SPY-200 switch, all cash while it is off), N20-ALWAYS (no "
        "switch: measures the picking alone, SPY's 2008 fall included), N30-TREND (30 slots), "
        "QUIET-N20-TREND (control: the same up jumps on volume under 1.5x normal, i.e. no "
        "news, which the papers say reverse) and M-N20-TREND (monthly re-pick). Success: "
        "N20-TREND beats total-return SPY on dev with a worst fall under 20%, beats SPY in "
        "2009-2015, and QUIET is clearly worse than N20-TREND."
    ),
    expected_failure=(
        "The drift is a published anomaly and has faded since; in big caps it was already small "
        "(well under 1% a month), so with most of the book in SPY the excess may be a point a "
        "year or less, too small to clear the luck bar. The volume proxy also catches "
        "non-earnings news (takeover bids, index adds) whose jumps revert or freeze. Gotrade's "
        "fees on 5% slots of a small account cost several tenths of a percent a side and the "
        "book turns over about five times a year. The SPY-200 switch carries the crash years "
        "as it did for every trend-switched book, so the 1998 and 2011 fast falls may still "
        "push the worst fall near 20%, and N20-ALWAYS should take most of SPY's 2008 fall. If "
        "QUIET does as well as N20-TREND, the edge is plain short-term momentum, not news."
    ),
    candidates=(
        _v("N20-TREND", JumpParams(N20),
           "Up to 20 live news jumps at 5% each, rest SPY, behind the SPY-200 switch, weekly"),
        _v("N20-ALWAYS", JumpParams(N20_NOTREND),
           "No switch: the picking alone on top of SPY, always invested"),
        _v("N30-TREND", JumpParams(N30),
           "30 slots at 3.3%: more names, less single-stock risk, same signal"),
        _v("QUIET-N20-TREND", JumpParams(N20, vol_min=None, vol_max=Decimal("1.5")),
           "Control: the same up jumps on ordinary volume (no news), which should not drift"),
        _v("M-N20-TREND", JumpParams(N20),
           "Same as N20-TREND but re-picked monthly on the existing real-fee preset",
           rules=MONTHLY_HOLD_FRAC_GOTRADE),
    ),
    seen_keys=(
        "concept:earnings-announcement-drift",
        "concept:post-earnings-announcement-drift",
        "concept:high-volume-gap-drift",
        "concept:earnings-announcement-return",
        "ssrn:909563",
    ),
)

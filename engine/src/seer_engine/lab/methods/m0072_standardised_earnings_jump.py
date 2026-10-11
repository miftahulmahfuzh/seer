"""M0072 — Earnings-day jumps measured against the stock's own normal swing.

Source: variation of M0063 (the earnings-day jump detector: Brandt, Kishore, Santa-Clara &
Venkatachalam 2008, SSRN 909563), with the jump standardised the way standardised unexpected
earnings (SUE; Foster, Olsen & Shevlin 1984; Bernard & Thomas 1989) standardises a surprise.
Idea: M0063's monthly book takes any news day whose three-day market-adjusted jump is at least 4
points. Four points is a shock for a calm utility and an ordinary week for a volatile chip stock,
so the fixed threshold fills slots with the routine big days of jumpy names -- the names that fell
hardest in summer 1998, the one fall that broke M0063-M-N20-TREND's 20% limit. Dividing the jump
by the stock's own recent daily volatility keeps the days that were genuinely large *for that
stock* and drops the rest.

The event is M0063's (``JumpParams``: volume >= 3x the 60-day median, up gap, three-day jump
against SPY over closes t-1 -> t+1) plus one more column:

    * sigma  sd[t] = population standard deviation of the stock's daily close-to-close returns
             ending on bars t-``sd_base``+1 .. t-1 (the returns *into* those bars), i.e. read
             from closes t-``sd_base`` .. t-1: the swing before the news day, never the news day;
    * z      z[t] = jump[t] / sd[t]: how many of the stock's own normal days the jump was.

An event is live when it passes M0063's filters and ``z >= z_min``. The live event is the most
recent such event younger than ``hold`` sessions, exactly as in M0063. Slots go to held names
first, then by ``rank``: ``"z"`` (the standardised jump) or ``"raw"`` (M0063's raw jump), so the
filter and the ranking can be judged apart. Everything else -- F4's screen, the SPY-200 switch,
20 slots of 5%, SPY in the empty slots, the monthly real-fee fractional preset -- is M0063's.

Every column entry at t reads bars t-max(vol_base, sd_base)..t+1 and the book only reads entries
with t+1 <= i, so nothing dated after the data date is read and the prepared and unprepared paths
agree.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20
from seer_engine.lab.methods.m0063_earnings_day_jump import (
    EventCols,
    JumpParams,
    event_cols,
    jump_lookback,
)
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import factor_rows, prepare_factor, trend_on

ADDED = date(2026, 10, 11)


# --------------------------------------------------------------------------- params


@dataclass(frozen=True, slots=True)
class ZParams:
    """``jump`` is M0063's event, screen and book; ``z_min``/``sd_base``/``rank`` standardise it."""

    jump: JumpParams
    z_min: Decimal = Decimal("2")  # standardised jump floor: jump / own daily sd
    sd_base: int = 60  # daily returns in the sd, ending the session before the event
    rank: str = "z"  # "z" ranks by the standardised jump, "raw" by M0063's raw jump

    def __post_init__(self) -> None:
        if not isinstance(self.jump, JumpParams):
            raise TypeError(f"jump must be JumpParams, got {type(self.jump).__name__}")
        if not isinstance(self.z_min, Decimal) or not self.z_min.is_finite() or self.z_min < 0:
            raise ValueError(f"z_min must be a finite Decimal >= 0, got {self.z_min!r}")
        if isinstance(self.sd_base, bool) or not isinstance(self.sd_base, int) or self.sd_base < 10:
            raise ValueError(f"sd_base must be an int >= 10, got {self.sd_base!r}")
        if self.rank not in ("z", "raw"):
            raise ValueError(f"rank must be 'z' or 'raw', got {self.rank!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"z_min": str(self.z_min), "sd_base": str(self.sd_base), "rank": self.rank}
        for k, v in self.jump.as_dict().items():
            out[f"jump.{k}"] = v
        return out


def _check(params: object) -> ZParams:
    if not isinstance(params, ZParams):
        raise TypeError(f"params must be ZParams, got {type(params).__name__}")
    return params


# --------------------------------------------------------------------------- the sigma column


def sigma_col(h: History, sd_base: int) -> np.ndarray:
    """sd[t] reads closes t-sd_base..t-1 (sd_base-1 daily returns ending at bar t-1); NaN if unknown."""
    n = len(h)
    sd = np.full(n, np.nan)
    if n < sd_base + 1:
        return sd
    with np.errstate(divide="ignore", invalid="ignore"):
        ret = h.close[1:] / h.close[:-1] - 1.0  # ret[k-1] is the return into bar k
    # window over ret[t-sd_base .. t-2] = returns into bars t-sd_base+1 .. t-1
    win = sliding_window_view(ret, sd_base - 1)  # win[k] = ret[k .. k+sd_base-2]
    t = np.arange(sd_base, n)
    sd[t] = np.std(win[t - sd_base], axis=1)
    sd[~np.isfinite(sd) | (sd <= 0)] = np.nan
    return sd


class ZPrepared:
    """The F4 columns plus each symbol's event and sigma columns, computed on first use."""

    def __init__(self, history: Mapping[str, History], factor: Any) -> None:
        self.history = history
        self.factor = factor
        self._cache: dict[tuple[str, str, int, int], tuple[EventCols, np.ndarray]] = {}

    def cols(self, symbol: str, market: str, vol_base: int, sd_base: int) -> tuple[EventCols, np.ndarray] | None:
        key = (symbol, market, vol_base, sd_base)
        if key not in self._cache:
            h = self.history.get(symbol)
            if h is None:
                return None
            self._cache[key] = (event_cols(h, self.history.get(market), vol_base), sigma_col(h, sd_base))
        return self._cache[key]


def live_event(cols: EventCols, sd: np.ndarray, i: int, p: ZParams) -> tuple[float, float] | None:
    """(z, raw jump) of the most recent live event t with i - hold < t <= i - 1, or None."""
    jp = p.jump
    lo = max(i - jp.hold + 1, jp.vol_base, p.sd_base)
    hi = i - 1
    if hi < lo:
        return None
    v = cols.vratio[lo : hi + 1]
    g = cols.gap[lo : hi + 1]
    j = cols.jump[lo : hi + 1]
    s = sd[lo : hi + 1]
    ok = np.isfinite(v) & np.isfinite(g) & np.isfinite(j) & np.isfinite(s)
    if jp.vol_min is not None:
        ok &= v >= float(jp.vol_min)
    if jp.vol_max is not None:
        ok &= v < float(jp.vol_max)
    ok &= g > float(jp.gap_min)
    ok &= j >= float(jp.jump_min)
    with np.errstate(divide="ignore", invalid="ignore"):
        z = np.where(ok, j / s, np.nan)
    ok &= np.isfinite(z) & (z >= float(p.z_min))
    idx = np.flatnonzero(ok)
    if idx.size == 0:
        return None
    k = idx[-1]
    return float(z[k]), float(j[k])


# --------------------------------------------------------------------------- the allocator


class StandardisedJumpAllocator:
    """M0063's monthly news-day book, keeping only jumps large for the stock's own swing; rest SPY."""

    id = "M0072"

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return max(jump_lookback(p.jump), p.jump.hold + p.sd_base + 2)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params).jump
        fixed = {p.market}
        if p.inner.trend is not None:
            fixed.add(p.inner.trend[0])
        return tuple(sorted(fixed))

    def holds(self, params: Any) -> tuple[str, ...]:
        p = _check(params).jump
        return (p.market,) if p.park else ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _targets(self, prepared: ZPrepared, rows: list[Any], data_date: date,
                 held: frozenset[str], p: ZParams) -> tuple[Target, ...]:
        jp = p.jump
        live: list[tuple[int, float, str]] = []
        for r in rows:
            h = prepared.history.get(r.symbol)
            if h is None or r.symbol == jp.market:
                continue
            i = h.index_of(data_date)
            got = prepared.cols(r.symbol, jp.market, jp.vol_base, p.sd_base)
            if i is None or got is None:
                continue
            ev = live_event(got[0], got[1], i, p)
            if ev is None:
                continue
            score = ev[0] if p.rank == "z" else ev[1]
            live.append((0 if r.symbol in held else 1, -score, r.symbol))
        w = equal_weight(jp.inner.top)
        out: list[Target] = []
        for _, _, s in sorted(live)[: jp.inner.top]:
            t = target_from_close(s, last_close(prepared.history[s], data_date), w)
            if t is not None:
                out.append(t)
        if jp.park:
            rest = Decimal(1) - w * len(out)
            mh = prepared.history.get(jp.market)
            if rest > 0 and mh is not None and mh.index_of(data_date) is not None:
                t = target_from_close(jp.market, last_close(mh, data_date), rest)
                if t is not None:
                    out.append(t)
        return tuple(out)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if not trend_on(history, data_date, p.jump.inner):
            return ()
        rows = factor_rows(history, members, data_date, p.jump.inner)
        return self._targets(ZPrepared(history, None), rows, data_date, held, p)

    def prepare(self, history: Mapping[str, History]) -> ZPrepared:
        return ZPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, ZPrepared) or prepared.factor is None:
            raise TypeError(f"prepared must be a prepared ZPrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not trend_on(prepared.history, data_date, p.jump.inner):
            return ()
        rows = prepared.factor.rows_on(members, data_date, p.jump.inner)
        return self._targets(prepared, rows, data_date, held, p)


ZJUMP = StandardisedJumpAllocator()

JUMP20 = JumpParams(N20)  # M0063-M-N20-TREND's event, screen, switch, 20 slots, 60-session hold
JUMP20_NOFLOOR = JumpParams(N20, jump_min=Decimal("0"))  # the same, with no raw 4-point floor


def _v(suffix: str, params: ZParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0072-{suffix}", family="M0072", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=ZJUMP, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0072",
    name="Earnings-day jumps measured against the stock's own normal swing: only take a news day "
         "that is large for that stock",
    family="stock-event-drift",
    source_kind="variation",
    source_ref="variation of M0063-M-N20-TREND (Brandt, Kishore, Santa-Clara & Venkatachalam 2008, "
               "SSRN 909563), the jump standardised as in standardised unexpected earnings "
               "(Foster, Olsen & Shevlin 1984; Bernard & Thomas 1989)",
    parent_id="M0063",
    hypothesis=(
        "Published 2008 (the earnings-day drift) and 1984-1989 (standardised surprises), so the "
        "dev window can only show the edge from before and just after it was widely known; "
        "2009-2015 is judged first. M0063-M-N20-TREND beat SPY by 4.4 points a year on dev with "
        "gains 1.93x its losses and a luck score of 0.918, and failed only the worst fall: 25.2% "
        "funded, April-September 1998. M0071 showed volume alone carries no edge, so the jump is "
        "the signal. A fixed 4-point jump treats a calm utility and a volatile chip stock alike; "
        "dividing the three-day market-adjusted jump by the stock's own daily volatility over the "
        "60 sessions before the news day (z = jump / sd) keeps the genuinely surprising news days "
        "and drops routine big days of jumpy stocks, which should be the names that fell hardest "
        "in summer 1998. Same frame as M0063-M-N20-TREND exactly (volume >= 3x the 60-day median, "
        "up gap, 60-session hold, 20 slots of 5%, rest SPY, SPY-200 switch, re-picked monthly, "
        "fractional shares at Gotrade's real fees on monthly-hold-frac-gotrade). Variants: Z2 "
        "(raw jump >= 4 points AND z >= 2, ranked by z), Z3 (raw >= 4 AND z >= 3, ranked by z), "
        "Z2-RAWRANK (the Z2 filter, ranked by the raw jump as the parent did: separates the "
        "filter from the ranking), Z3-NOFLOOR (z >= 3 alone, no raw floor, ranked by z: admits "
        "calm stocks whose 2-3 point jump is a real shock for them). The raw-jump control is the "
        "parent's own recorded trial M0063-M-N20-TREND: same preset, same fees, same funding, so "
        "it is compared directly and not re-run (its configuration has already run on dev). I "
        "expect Z2 to be best. Success: a variant with a worst fall under 20% that still beats "
        "total-return SPY with DSR >= 0.90 and beats SPY in 2009-2015."
    ),
    expected_failure=(
        "The 1998 fall was market-wide (SPY fell about 19% July-August) and the monthly SPY-200 "
        "switch was late; with 20 slots and the rest in SPY the book's fall is mostly the market's, "
        "so better picks may not shrink it below 20%. Standardising tilts the book toward calm, "
        "low-volatility names (utilities, staples), which lag in strong rebounds like 2009 and "
        "the 1999 tech run, so the excess over SPY may shrink and the luck score fall under 0.90. "
        "Z3 may leave many slots empty and drift toward plain SPY. A z-score on a 60-day sd is "
        "noisy: a stock calm for two months then hit by news reads as a huge surprise even when "
        "the move was ordinary for it over a year. And this is a published anomaly, so a strong "
        "dev result may have faded in 2016-2026."
    ),
    candidates=(
        _v("Z2", ZParams(JUMP20, z_min=Decimal("2")),
           "Parent's news days, kept only when the jump is at least 2 of the stock's own daily swings; ranked by that"),
        _v("Z3", ZParams(JUMP20, z_min=Decimal("3")),
           "Stricter: at least 3 own daily swings, on top of the 4-point floor; ranked by z"),
        _v("Z2-RAWRANK", ZParams(JUMP20, z_min=Decimal("2"), rank="raw"),
           "The Z2 filter ranked by the raw jump as the parent did: is it the filter or the ranking?"),
        _v("Z3-NOFLOOR", ZParams(JUMP20_NOFLOOR, z_min=Decimal("3")),
           "No 4-point floor: any up news day of at least 3 own daily swings, so calm stocks can enter"),
    ),
    seen_keys=(
        "concept:standardised-earnings-jump",
        "concept:volatility-scaled-event-return",
        "concept:standardized-unexpected-earnings-proxy",
    ),
)

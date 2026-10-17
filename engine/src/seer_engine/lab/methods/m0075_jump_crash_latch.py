"""M0075 — The filtered news-day book behind a fast crash exit with slow, monthly re-entry.

Source: variation of M0092-SQRT-CAP10 (the earnings-day drift of Brandt, Kishore, Santa-Clara &
Venkatachalam 2008, SSRN 909563, with M0072's own-swing filter and M0092's square-root trading-value
sizing) with M0012's fast crash gate (SPY's own fall from its recent high, or under a shorter
average), on ``monthly-rank-weekly-resize-frac-gotrade`` and the owner's monthly top-up. The idea
row was first written against M0066's picks (parent M0063 by way of M0066); Sera's slate
(20261017-1607) moved it onto the filtered picks that fired the buy signal, so the parent here is
M0092.
Idea: M0092-SQRT-CAP10 cleared the luck bar and the walk-forward folds on dev, but its worst fall
(24.6% funded, 23.5% without deposits, March-August 1998) is the family's scar, and on the
survivorship-check store it fell 27.5% and lost its fold majority. Three attacks on picks and sizes
(M0066's brake, M0072's filter, M0092's sizing) moved the fall by a point or two; the one lever left
is the switch. M0066 showed the two halves of a switch want opposite speeds: a weekly exit is
needed to meet a fast crash inside the month, while re-reading the SPY-200 switch weekly whipsaws
(W-MTREND +5.0% -> +10.9% a year once the switch was read monthly). So split it: exit fast,
enter slow.

Mechanics. Rules ``monthly-rank-weekly-resize-frac-gotrade``. On the month's rank session (data
date = the anchor, the session before the month's first session) the basket is M0092's, chosen
exactly as M0092 chooses it, monthly SPY-200 switch included. On every weekly resize session the
runner keeps that basket and uses only the allocator's total weight: the full basket while the
latch is open, nothing (cash) once it has closed. The latch closes when the crash leg trips on ANY
session from the anchor through ``data_date`` and stays closed until the next anchor, so a crash
inside the month empties the book at the next weekly decision and nothing buys it back before the
next monthly check. The monthly check reads both legs on the anchor (SPY above its 200-day average
AND the crash leg clear), so the book never buys at a month's start only to be latched out a week
later on the same, still-tripped reading. The crash leg, per ``crash``:

    * ``"dd"``   SPY's close on day j at or more than ``dd_limit`` below the highest close of the
                 ``dd_n`` sessions through j (M0012-W-SMA200-DD8's leg);
    * ``"sma"``  SPY's close on day j at or under its ``sma_n``-session simple average
                 (M0012-W-SMA200-100's leg);
    * ``"none"`` never trips: the same basket on the same weekly preset, the machinery's control.

Tripped also when SPY has no bar dated j or too little history (the safe side). Assumptions
written before the run: the latch reads every session, not only the weekly data dates, so a trip
that clears by the week's end still counts (fast exit); on a resize session the anchor basket is
recomputed with the data date's members, as M0012 and M0066 do, which changes nothing the runner
reads, since the SPY park fills the basket to its full weight either way. Reads only bars dated <=
``data_date``.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0020_stop_with_weekly_reentry import _refreshed, anchor_date
from seer_engine.lab.methods.m0072_standardised_earnings_jump import ZPrepared
from seer_engine.lab.methods.m0092_jump_trading_value_weight import SIZED, Z2_RAW, SizeParams
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE
from seer_engine.strategies.base import History

ADDED = date(2026, 10, 17)


# --------------------------------------------------------------------------- params


@dataclass(frozen=True, slots=True)
class LatchParams:
    """``inner`` is M0092's picks, sizes and monthly switch; the rest is the weekly crash latch."""

    inner: SizeParams
    crash: str = "dd"  # "dd" (fall from the recent high), "sma" (under an average) or "none"
    dd_limit: Decimal = Decimal("0.08")
    dd_n: int = 126
    sma_n: int = 100
    market: str = "SPY"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, SizeParams):
            raise TypeError(f"inner must be SizeParams, got {type(self.inner).__name__}")
        if self.crash not in ("dd", "sma", "none"):
            raise ValueError(f"crash must be 'dd', 'sma' or 'none', got {self.crash!r}")
        if not isinstance(self.dd_limit, Decimal) or not 0 < self.dd_limit < 1:
            raise ValueError(f"dd_limit must be a Decimal in (0, 1), got {self.dd_limit!r}")
        for name in ("dd_n", "sma_n"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int) or v < 2:
                raise ValueError(f"{name} must be an int >= 2, got {v!r}")
        if not isinstance(self.market, str) or not self.market:
            raise ValueError(f"market must be a non-empty symbol, got {self.market!r}")

    def as_dict(self) -> dict[str, str]:
        out = {
            "crash": self.crash,
            "dd_limit": str(self.dd_limit),
            "dd_n": str(self.dd_n),
            "sma_n": str(self.sma_n),
            "market": self.market,
        }
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> LatchParams:
    if not isinstance(params, LatchParams):
        raise TypeError(f"params must be LatchParams, got {type(params).__name__}")
    return params


# --------------------------------------------------------------------------- the latch


def tripped(h: History, j: int, p: LatchParams) -> bool:
    """The crash leg on SPY's bar j (see the module docstring); reads bars <= j only."""
    if p.crash == "none":
        return False
    close = float(h.close[j])
    if p.crash == "dd":
        if j + 1 < p.dd_n:
            return True
        high = float(h.close[j + 1 - p.dd_n : j + 1].max())
        return not close > high * (1.0 - float(p.dd_limit))
    if j + 1 < p.sma_n:
        return True
    return not close > float(h.close[j + 1 - p.sma_n : j + 1].mean())


def latch_open(history: Mapping[str, History], anchor: date, data_date: date, p: LatchParams) -> bool:
    """True while the crash leg has not tripped on any session from ``anchor`` through ``data_date``."""
    h = history.get(p.market)
    if h is None:
        return False
    lo, hi = h.index_of(anchor), h.index_of(data_date)
    if lo is None or hi is None:
        return False
    return not any(tripped(h, j, p) for j in range(lo, hi + 1))


# --------------------------------------------------------------------------- the allocator


class LatchedJumpAllocator:
    """M0092's monthly basket while the month's crash latch is open, cash once it has closed."""

    id = "M0075"

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return max(SIZED.lookback(p.inner), p.dd_n, p.sma_n) + 25  # the anchor can sit ~23 back

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return tuple(sorted({p.market, *SIZED.symbols(p.inner)}))

    def holds(self, params: Any) -> tuple[str, ...]:
        return SIZED.holds(_check(params).inner)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        anchor = anchor_date(data_date)
        if not latch_open(history, anchor, data_date, p):
            return ()
        cut = {s: h.upto(anchor) for s, h in history.items()}
        basket = SIZED.targets(cut, members, anchor, held, p.inner)
        return _refreshed(basket, history, data_date, None)

    def prepare(self, history: Mapping[str, History]) -> ZPrepared:
        return SIZED.prepare(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, ZPrepared) or prepared.factor is None:
            raise TypeError(f"prepared must be a prepared ZPrepared, got {type(prepared).__name__}")
        p = _check(params)
        anchor = anchor_date(data_date)
        if not latch_open(prepared.history, anchor, data_date, p):
            return ()
        basket = SIZED.targets_prepared(prepared, members, anchor, held, p.inner)
        return _refreshed(basket, prepared.history, data_date, None)


LATCHED = LatchedJumpAllocator()
SQRT = SizeParams(Z2_RAW, weight="sqrt")  # M0092-SQRT-CAP10's book, exactly
EQUAL = SizeParams(Z2_RAW, weight="equal")  # M0072-Z2-RAWRANK's equal 5% slots, via M0092's code


def _v(suffix: str, params: LatchParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0075-{suffix}", family="M0075", rules=MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE,
                     allocator=LATCHED, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0075",
    name="The earnings-day book behind a fast crash exit with slow, monthly re-entry",
    family="stock-event-drift",
    source_kind="variation",
    source_ref="variation of M0092-SQRT-CAP10 (Brandt, Kishore, Santa-Clara & Venkatachalam 2008, "
               "SSRN 909563, with M0072's filter and M0092's sizing) + M0012's fast crash gate, "
               "read weekly as a latch that only the monthly check reopens; idea first queued "
               "from M0066",
    parent_id="M0092",
    hypothesis=(
        "Published 2008 (the earnings-day drift) and the crash gate's two-speed idea is the lab's "
        "own (M0012, 2026-10-07), so the dev window can only show the drift from before and just "
        "after it was widely known; 2009-2015 is judged first. M0092-SQRT-CAP10 (the filtered "
        "news-day picks sized by the square root of trading value, rest in SPY, SPY-200 switch "
        "read monthly) earned +12.4% a year vs SPY's +7.2% on the owner's deposits, DSR 0.911, "
        "3 of 4 folds, +1.7 pts a year over SPY in 2009-2015, and fell 24.6% funded (23.5% "
        "without deposits, March-August 1998); on the survivorship-check store 27.5% and 2 of 4 "
        "folds. M0066 showed a trailing-volatility brake never engaged in the calm April 1998 "
        "slide and then held cash through the 2009 rebound, and that re-reading the SPY-200 "
        "switch weekly whipsaws. So split the switch: keep M0092's monthly basket and monthly "
        "SPY-200 switch exactly, and add a weekly crash latch on "
        "monthly-rank-weekly-resize-frac-gotrade: once SPY's crash leg trips on any session in the "
        "month, the whole book (SPY park included) goes to cash at the next weekly decision and "
        "stays there until the next monthly check finds SPY above its 200-day average with the "
        "crash leg clear. Variants: SQRT-DD8 (leg: SPY 8% or more below its 126-session high, "
        "M0012's), SQRT-DD5 (5% below its 21-session high: a sudden fall over days, faster), "
        "SQRT-SMA100 (SPY at or under its 100-day average, M0012's other leg), EQ-DD8 (the DD8 "
        "latch on M0072-Z2-RAWRANK's equal 5% slots, the second host) and SQRT-NONE (no latch, "
        "the same weekly preset: the machinery's control, which should reproduce M0092-SQRT-CAP10). "
        "I expect SQRT-DD8 to be best: it should leave in the first week of August 1998 and stay "
        "out through the September-October bottom, cutting the 1998 fall to about 17-19% while "
        "giving up under a point a year. Success: worst fall (funded) under 20%, still beating "
        "total-return SPY on the owner's deposits with DSR >= 0.90, beating SPY in 2009-2015 and "
        "in a majority of walk-forward folds."
    ),
    expected_failure=(
        "About 10 of the 23.5 points of the 1998 fall were the picks lagging SPY from April to "
        "July while SPY itself rose to a new high on 17 July: no SPY-based leg can see that, so "
        "the latch can at best save the August crash (SPY fell about 19% from mid-July to 31 "
        "August), and the fall may stay near 20-21%. The DD8 leg trips only once SPY is already "
        "8% down, so it sells after a third of the drop. The fast legs (DD5, SMA100) trip on many "
        "5% pullbacks that snapped back (1997, 1999, 2004-2006, 2010, 2012, 2014) and each one "
        "costs up to a month in cash while SPY recovers, a few points a year in total, and at "
        "real fees each exit and re-entry pays Gotrade's charges on 20 small slots. The 2009 "
        "rebound, where the book made about +50%, was entered only when SPY crossed its 200-day "
        "average, so the latch adds nothing there and may add late re-entries after the 2010 and "
        "2011 falls. The luck score may drop under 0.90 if return falls. A published 2008 "
        "anomaly, so a strong dev result may have faded in 2016-2026."
    ),
    candidates=(
        _v("SQRT-DD8", LatchParams(SQRT, "dd", Decimal("0.08"), 126),
           "M0092-SQRT-CAP10 out to cash for the month once SPY is 8% below its 6-month high"),
        _v("SQRT-DD5", LatchParams(SQRT, "dd", Decimal("0.05"), 21),
           "The same latch on a sudden fall: SPY 5% below its one-month high"),
        _v("SQRT-SMA100", LatchParams(SQRT, "sma", sma_n=100),
           "The same latch tripped by SPY closing at or under its 100-day average"),
        _v("EQ-DD8", LatchParams(EQUAL, "dd", Decimal("0.08"), 126),
           "The DD8 latch on the equal 5% slots of M0072-Z2-RAWRANK: the second host"),
        _v("SQRT-NONE", LatchParams(SQRT, "none"),
           "No latch, same weekly preset: should reproduce M0092-SQRT-CAP10 (the control)"),
    ),
    seen_keys=(
        "concept:event-drift-crash-latch",
        "concept:fast-exit-slow-reentry",
        "concept:two-speed-switch-monthly-reentry",
    ),
)

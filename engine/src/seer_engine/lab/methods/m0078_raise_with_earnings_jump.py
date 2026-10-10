"""M0078 — A dividend raise on the same day as an earnings jump: is the pair stronger than either alone?

Source: variation of M0063 (the earnings-day jump detector) and M0070 (the dividend raise);
Kane, Lee & Marcus (1984), "Earnings and dividend announcements: is there a corroboration
effect?", Journal of Finance 39(4).
Idea: boards often declare the dividend with the quarterly results. A raise declared within a
few sessions of a high-volume up gap is good news told twice -- once in the earnings, once in
the cash the board commits -- and Kane, Lee and Marcus report the two announcements corroborate
each other. The store now carries declaration dates for most dividends (the one-month EODHD
pull), so the pair can be matched on the day the market learned of the raise, not weeks later
on its ex-date. Every variant has a twin timed on the ex-date: the paired difference is what the
announcement data is worth to this method.

Frame: F4's point-in-time S&P 500 / Nasdaq-100 screen and SPY-200 switch (all cash while it is
off), up to ``inner.top`` names at 1/top each, held names first, the rest parked in SPY,
re-picked weekly in fractional shares at Gotrade's real fees (M0063's assumed
weekly-hold-frac-gotrade preset).

Definitions, on data date d (bar index i of stock s):

    * a *jump* is M0063's event at bar t (volume >= 3x its 60-day median, up gap, three-day
      return >= 4 points over SPY's), read only when t + 1 <= i;
    * a *dividend* is known on its known date: ``arm="announce"`` reads
      ``Market.dividends.announced_on(s, d)`` (the declaration day when the store has one, else the
      ex-date); ``arm="ex"`` reads ``known_on(s, d)`` and treats the ex-date as the known date. k is
      the index of s's first bar on or after the known date;
    * the dividend is a *raise* when its amount is between (1 + ``raise_min``) and
      (1 + ``raise_max``) times the median of the up to four payments that went ex in the 400 days
      before its ex-date (among those known by d), or an *initiation* when none did and s has bars
      from before that window (M0070's rule);
    * ``mode="joint"``: s is live when a jump t with i - hold < t <= i - 1 and a raise with
      t - ``after`` <= k <= t + ``before`` (the jump at most ``before`` sessions before the raise
      became known and at most ``after`` sessions after it) are both known; its score is the jump.
      It stays live until the jump is ``hold`` sessions old;
    * ``mode="raise"``: s is live when a raise became known at k with i - hold < k <= i; ranked by the
      newest k.

Without the market's dividend calendar (the history-only path) nothing is targeted, which is
the market-aware allocator contract. Every read is of bars dated <= d and of dividends whose
known date is <= d.
"""

from __future__ import annotations

import statistics
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Literal

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import EMPTY_DIVIDENDS, Announcement, DividendCalendar
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20
from seer_engine.lab.methods.m0063_earnings_day_jump import (
    WEEKLY_HOLD_FRAC_GOTRADE,
    EventCols,
    JumpParams,
    JumpPrepared,
    jump_lookback,
)
from seer_engine.sim.book import Target, equal_weight
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import EXCLUDED, factor_rows, prepare_factor, trend_on

ADDED = date(2026, 10, 10)
BASE_DAYS = 400  # the window before an ex-date that sets the baseline / proves no prior payment
BASE_N = 4  # payments in the baseline median

Arm = Literal["announce", "ex"]
Mode = Literal["joint", "raise"]
_ARMS: tuple[str, ...] = ("announce", "ex")
_MODES: tuple[str, ...] = ("joint", "raise")


@dataclass(frozen=True, slots=True)
class PairParams:
    """``jump`` is M0063's event and F4 frame (its ``hold`` is the event's life); the rest pairs it."""

    jump: JumpParams
    arm: Arm = "announce"
    mode: Mode = "joint"
    before: int = 3  # sessions a jump may come before the raise's known date
    after: int = 3  # sessions a jump may come after it
    raise_min: Decimal = Decimal("0.10")
    raise_max: Decimal = Decimal("1.00")

    def __post_init__(self) -> None:
        if not isinstance(self.jump, JumpParams):
            raise TypeError(f"jump must be JumpParams, got {type(self.jump).__name__}")
        if not isinstance(self.arm, str) or self.arm not in _ARMS:
            raise ValueError(f"arm must be one of {_ARMS}, got {self.arm!r}")
        if not isinstance(self.mode, str) or self.mode not in _MODES:
            raise ValueError(f"mode must be one of {_MODES}, got {self.mode!r}")
        for name in ("before", "after"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int) or v < 0:
                raise ValueError(f"{name} must be an int >= 0, got {v!r}")
        for name in ("raise_min", "raise_max"):
            v = getattr(self, name)
            if not isinstance(v, Decimal) or not v.is_finite() or v < 0:
                raise ValueError(f"{name} must be a finite Decimal >= 0, got {v!r}")
        if self.raise_max <= self.raise_min:
            raise ValueError("raise_max must be above raise_min")

    def as_dict(self) -> dict[str, str]:
        out = {
            "arm": self.arm,
            "mode": self.mode,
            "before": str(self.before),
            "after": str(self.after),
            "raise_min": str(self.raise_min),
            "raise_max": str(self.raise_max),
        }
        for k, v in self.jump.as_dict().items():
            out[f"jump.{k}"] = v
        return out


def _check(params: object) -> PairParams:
    if not isinstance(params, PairParams):
        raise TypeError(f"params must be PairParams, got {type(params).__name__}")
    return params


# --------------------------------------------------------------------------- the dividend side


def known_dividends(calendar: DividendCalendar, symbol: str, data_date: date,
                    arm: str) -> tuple[Announcement, ...]:
    """``symbol``'s dividends known on or before ``data_date``, ascending by known date."""
    if arm == "announce":
        return calendar.announced_on(symbol, data_date)
    return tuple(Announcement(e, e, a, False) for e, a in calendar.known_on(symbol, data_date))


def is_raise(a: Announcement, known: tuple[Announcement, ...], first_bar: date | None,
             p: PairParams) -> bool:
    """A raise or an initiation, judged on the payments in ``known`` that went ex before ``a``."""
    since = a.ex_date - timedelta(days=BASE_DAYS)
    prior = sorted((x.ex_date, x.amount) for x in known if since < x.ex_date < a.ex_date)[-BASE_N:]
    if not prior:
        return first_bar is not None and first_bar <= since
    base = statistics.median(amt for _, amt in prior)
    return p.raise_min <= a.amount / base - 1 <= p.raise_max


def raise_bars(h: History, known: tuple[Announcement, ...], lo_day: date, p: PairParams) -> list[int]:
    """Bar index k (first bar on or after the known date) of every raise known on or after ``lo_day``."""
    first_bar = h.dates[0].astype(object) if len(h) else None
    out: list[int] = []
    for a in reversed(known):
        if a.known < lo_day:
            break
        if is_raise(a, known, first_bar, p):
            out.append(int(np.searchsorted(h.dates, np.datetime64(a.known, "D"), side="left")))
    return out


# --------------------------------------------------------------------------- the jump side


def jump_events(cols: EventCols, lo: int, hi: int, p: JumpParams) -> np.ndarray:
    """Bar indices t in [lo, hi] that are M0063 events."""
    lo = max(lo, p.vol_base)
    if hi < lo:
        return np.empty(0, dtype=int)
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
    return np.flatnonzero(ok) + lo


def live_score(h: History, cols: EventCols, known: tuple[Announcement, ...], i: int,
               p: PairParams) -> float | None:
    """The stock's score on bar i (higher first), or None when it has no live event."""
    jp = p.jump
    if p.mode == "raise":
        lo_i = max(i - jp.hold + 1, 0)
        ks = [k for k in raise_bars(h, known, h.dates[lo_i].astype(object), p) if lo_i <= k <= i]
        return float(max(ks)) if ks else None
    events = jump_events(cols, i - jp.hold + 1, i - 1, jp)
    if events.size == 0:
        return None
    lo_k = max(int(events[0]) - p.after, 0)
    ks = raise_bars(h, known, h.dates[lo_k].astype(object), p)
    if not ks:
        return None
    for t in events[::-1]:  # the most recent jump that pairs with a raise
        if any(t - p.after <= k <= t + p.before for k in ks):
            return float(cols.jump[t])
    return None


# --------------------------------------------------------------------------- the allocator


@dataclass
class PairPrepared:
    jumps: JumpPrepared = field(repr=False)
    calendar: DividendCalendar = field(repr=False)


class RaiseJumpAllocator:
    """Members with a dividend raise paired with an earnings-day jump, held while young; rest SPY."""

    id = "M0078"
    market_fields = ("dividends",)  # ranks on Market.dividends, never on Market.fundamentals

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return jump_lookback(p.jump) + p.before + p.after

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        fixed = {p.jump.market}
        if p.jump.inner.trend is not None:
            fixed.add(p.jump.inner.trend[0])
        return tuple(sorted(fixed))

    def holds(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return (p.jump.market,) if p.jump.park else ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(self, prepared: PairPrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: PairParams) -> tuple[Target, ...]:
        if len(prepared.calendar) == 0:  # no calendar: target nothing (market-aware contract)
            return ()
        jp = p.jump
        history = prepared.jumps.history
        if not trend_on(history, data_date, jp.inner):
            return ()
        if prepared.jumps.factor is None:
            rows = factor_rows(history, members, data_date, jp.inner)
        else:
            rows = prepared.jumps.factor.rows_on(members, data_date, jp.inner)
        live: list[tuple[int, float, str]] = []
        for r in rows:
            if r.symbol in EXCLUDED or r.symbol == jp.market:
                continue
            h = history.get(r.symbol)
            if h is None:
                continue
            i = h.index_of(data_date)
            cols = prepared.jumps.cols(r.symbol, jp.market, jp.vol_base)
            if i is None or cols is None:
                continue
            known = known_dividends(prepared.calendar, r.symbol, data_date, p.arm)
            if not known:
                continue
            score = live_score(h, cols, known, i, p)
            if score is None:
                continue
            live.append((0 if r.symbol in held else 1, -score, r.symbol))
        w = equal_weight(jp.inner.top)
        out: list[Target] = []
        for _, _, s in sorted(live)[: jp.inner.top]:
            t = target_from_close(s, last_close(history[s], data_date), w)
            if t is not None:
                out.append(t)
        if jp.park:
            rest = Decimal(1) - w * len(out)
            mh = history.get(jp.market)
            if rest > 0 and mh is not None and mh.index_of(data_date) is not None:
                t = target_from_close(jp.market, last_close(mh, data_date), rest)
                if t is not None:
                    out.append(t)
        return tuple(out)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no calendar, so no event and no target."""
        return self._run(PairPrepared(JumpPrepared(history, None), EMPTY_DIVIDENDS), members,
                         data_date, held, _check(params))

    def prepare(self, history: Mapping[str, History]) -> PairPrepared:
        return PairPrepared(JumpPrepared(history, prepare_factor(history)), EMPTY_DIVIDENDS)

    def prepare_market(self, market: Any) -> PairPrepared:
        calendar = getattr(market, "dividends", EMPTY_DIVIDENDS)
        if not isinstance(calendar, DividendCalendar):
            raise TypeError(f"market.dividends must be a DividendCalendar, got {type(calendar).__name__}")
        return PairPrepared(JumpPrepared(market.history, prepare_factor(market.history)), calendar)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, PairPrepared):
            raise TypeError(f"prepared must be PairPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params))


PAIR = RaiseJumpAllocator()
JUMP20 = JumpParams(N20)  # M0063-N20-TREND's event, screen, switch, 20 slots and 60-session hold


def _v(suffix: str, params: PairParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0078-{suffix}", family="M0078", rules=WEEKLY_HOLD_FRAC_GOTRADE,
                     allocator=PAIR, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0078",
    name="A dividend raise on the same day as an earnings jump: is the pair stronger than either signal alone?",
    family="stock-event-drift",
    source_kind="variation",
    source_ref=(
        "M0063 (earnings-day jump detector); M0070 (dividend raise drift); Kane, Lee & Marcus "
        "(1984), Earnings and dividend announcements: is there a corroboration effect?, JF 39(4)"
    ),
    parent_id="M0063",
    hypothesis=(
        "Published 1984 (the corroboration effect) and 2008 (the earnings-day drift M0063 copies), "
        "so the dev window sees the pair after both were known; 2009-2015 is judged first. Boards "
        "often declare the dividend with the quarterly results. A raise (10% or more over the "
        "median of the up-to-four payments in the prior 400 days, at most double, or a first "
        "payment) declared within 3 sessions of an M0063 news jump (volume >= 3x the 60-day "
        "median, an up gap, a three-day return >= 4 points over SPY's) is good news told twice, "
        "and should drift harder than either alone. Inside F4's liquidity and membership screen, "
        "behind the SPY-200 switch (all cash while it is off), hold up to 20 such names at 5% "
        "each until the jump is 60 sessions old (held names first, then the biggest jumps), the "
        "rest in SPY, re-picked weekly, fractional shares at Gotrade's real fees (M0063's assumed "
        "weekly-hold-frac-gotrade preset). BATCH RULE (sera-20261010-1742): each variant has a "
        "twin timed on the ex-date instead of the announcement, and the paired difference "
        "(announcement minus ex-date) on funded CAGR, worst fall, DSR, 2009-2015 and the "
        "walk-forward folds is the value of the announcement data. Dividends with no declaration "
        "date are known on their ex-date in both arms, so they are identical across a pair and "
        "cannot blur the difference (about 87% of 1996-2015 payments carry one). Variants: "
        "JOINT-ANN (raise known by declaration within 3 sessions either side of the jump) and "
        "JOINT-EX (the identical rule timed on the ex-date: almost no ex-date falls on an "
        "earnings day, so this book is expected to sit nearly all in SPY -- it is the literal "
        "control); WIN-ANN and WIN-EX (the realistic pair: the jump may come up to 45 sessions "
        "before the raise became known, so the ex-date twin is what one could trade without "
        "declaration dates -- see the raise on its ex-date, check for a jump in the two months "
        "before, hold until the jump is 60 sessions old; the announcement twin acts weeks "
        "earlier on the same pairs); RAISE-ANN and RAISE-EX (the raise alone, held 60 sessions "
        "from the day it became known, same frame and cadence: the 'raise alone' baseline). The "
        "'jump alone' baseline is M0063-N20-TREND's recorded trial (identical event, screen, "
        "switch, slots, hold and cadence; not re-run). Success for the idea: JOINT-ANN or WIN-ANN "
        "beats both RAISE-ANN and M0063-N20-TREND on funded CAGR and 2009-2015; success for the "
        "data: each ANN beats its EX twin."
    ),
    expected_failure=(
        "The joint events are too few among big caps (a few dozen a year at most) to fill 20 "
        "slots, so JOINT-ANN sits mostly in SPY behind the switch and its edge over SPY is too "
        "small to read or to clear the luck bar; the pair may beat SPY by a fraction of a point "
        "that the 1998 and 2011 fast falls (which land before the switch turns) swamp. The "
        "corroboration effect was measured on the announcement-day return, not on a two-month "
        "drift, and both parent signals are published anomalies that faded, so the pair may add "
        "nothing over the jump alone. JOINT-EX should be nearly SPY behind the switch, so a big "
        "JOINT-ANN minus JOINT-EX gap partly measures 'any picks vs none', which is why the WIN "
        "pair exists. For WIN, the ex-date twin buys the same names weeks later with less hold "
        "left, so most of the drift after an earnings day (front-loaded in the first weeks) may "
        "already be gone: the announcement twin should win, but by how much is the question. "
        "Weekly re-picks at Gotrade's real fees on $50-70 slots cost several tenths of a percent "
        "a side; M0063's weekly book lost to SPY on exactly that churn, so every variant may lag "
        "SPY however good the pairing is. Not modelled: US withholding tax on dividends."
    ),
    candidates=(
        _v("JOINT-ANN", PairParams(JUMP20),
           "A raise declared within 3 sessions of a news jump, timed on the declaration day"),
        _v("JOINT-EX", PairParams(JUMP20, arm="ex"),
           "Control: the identical rule timed on the ex-date (expected to find almost nothing)"),
        _v("WIN-ANN", PairParams(JUMP20, before=45),
           "A raise known up to 45 sessions after a news jump, timed on the declaration day"),
        _v("WIN-EX", PairParams(JUMP20, arm="ex", before=45),
           "Control: the same pairs seen on the ex-date, what one could trade without declaration dates"),
        _v("RAISE-ANN", PairParams(JUMP20, mode="raise"),
           "The raise alone, held 60 sessions from its declaration, same frame and weekly cadence"),
        _v("RAISE-EX", PairParams(JUMP20, arm="ex", mode="raise"),
           "Control: the raise alone held 60 sessions from its ex-date"),
    ),
    seen_keys=(
        "concept:earnings-dividend-corroboration",
        "concept:joint-earnings-dividend-announcement",
        "concept:dividend-announcement-timing",
        "doi:10.1111/j.1540-6261.1984.tb03888.x",
    ),
)

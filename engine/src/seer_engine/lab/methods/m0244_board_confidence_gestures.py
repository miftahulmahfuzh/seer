"""M0244 — Buy the companies whose boards most recently did something confident.

Source: variation of M0241 (the split book). Reserved by Sera batch 20261019-1014.

Ikenberry, Rankine & Stice (1996), JFQA 31(3) 357-375, on splits; Michaely, Thaler & Womack
(1995), JF 50(2), on dividend initiations; Pontiff & Woodgate (2008), JF 63(2) 921-945, on share
issuance. Three separate literatures, one claimed mechanism: a board spends money or credibility
to say it believes the current price is a floor rather than a ceiling.

WHY THIS FILE EXISTS. M0241 found that recent splitters beat a book matched to their exact shape
by about two points a year, that the lead decays with time since the split, and -- almost alone in
this lab -- that the effect gets *stronger* when the companies that went bust are added back. It
was rejected for one reason: after 2008 the store's members produce only 11-27 splits a year, so
the modern book is five to twenty names drawn from a nearly empty calendar, and it trailed SPY
from 2009. The reserved idea's fix was to pool every gesture of the same kind -- split, first-ever
dividend, a raise after a flat stretch, a large buyback -- into one calendar wide enough to hold
25-45 names where splits alone hold 5-20.

THE POOL IS NOT THIN. IT IS ENORMOUS. Counted on the dev store before this file was written
(pool sizes only, no returns, no backtest), the number of screened members carrying at least one
live gesture in the trailing 380 days, yearly medians:

    year  eligible  split  init  raise  buyback  POOL
    1997      114     33      0     52        8    66
    2003      220      8      4     45       20    74
    2008      322     16      4    147      116   213
    2012      357     12     13    167      106   214
    2015      395     21      5    187      107   239

Median pool over 2009-2015 is 213 of about 350 eligible members: three members in five. The
gesture is not rare, because the common one is not rare -- a routine annual dividend raise, 187 of
the 239 in 2015. So the reserved idea's premise is wrong in a way worth writing down before any
result: pooling does not fill a thin calendar, it floods it. An equal-weight book over the whole
pool would be a gated payout-weighted index with 213 names and $6 slots at a 20M IDR account, and
it would measure Gotrade's fee minimum rather than any board's confidence.

SO THE INSTRUMENT CHANGES, AND FRESHNESS BECOMES THE SELECTOR. This method holds the ``top``
members whose newest gesture of any enabled kind is the most recent. In 2015 that is roughly the
last five or six weeks of gestures; in 1997, when the pool is 66 names, roughly the last six
months. The pool's width is what makes the date do work: with 213 names live and 30 slots, the
only thing deciding who is held is how recently the board acted. That is exactly the quantity
M0241 found decays, measured on a calendar that no longer empties.

THE SIX ARMS. Four gesture kinds (``split``, ``init``, ``raise``, ``buyback``) partition the pool,
and the arms cut it four ways plus two controls:

    * FRESH30 -- all four kinds, the 30 freshest, equal weight, no name above 20%, behind the SPY
      200-day gate. The main arm.
    * NOBUY30 -- splits, initiations and raises. FRESH30 minus it prices the buyback arm, which
      M0230 already rejected as a core and which this lab has since found earns its keep only in
      the cheap half of repurchases that this method does not filter for.
    * HARD30 -- splits, initiations and buybacks: the pool with the *routine* gesture dropped. A
      board raising its dividend 10% for the eleventh year running is doing something ordinary;
      splitting the stock, starting a dividend after never paying one, or retiring 3% of the
      share count is not. If the thesis is right that these are one signal, this arm should carry
      the pool. If the pool only works with the common gesture in it, the thesis is wrong.
    * DIVONLY30 -- initiations and raises only. The direct test of the second expected failure:
      that the pooled book is the ``stock-dividend-change-drift`` family (68 trials, best MAR
      0.57) wearing an event costume.
    * STALE30 -- members whose newest gesture fell 380 to 760 days ago and which have had none
      since. The dose-response control on the date itself. If this earns what FRESH30 earns, the
      recency does nothing and the book is a quality-and-payout tilt, not an event book.
    * PLACEBO30 -- FRESH30's shape with none of its identities. For each trailing calendar month,
      newest first, how many screened members' newest gesture actually fell in that month, then
      that many names drawn from the same screened pool in a fixed hash order seeded on that month
      (M0187's ``draw``), skipping names a fresher month already took, stopping at exactly the
      number of names FRESH30 holds that day. Count, month-by-month composition, stickiness and
      turnover are FRESH30's by construction; the only thing FRESH30 has that this does not is
      *which* company acted. M0241 proved this control is not optional: roughly half of that
      book's lead over SPY was the shape of a gated equal-weight basket.

The reserved idea promised "each gesture type dropped in turn", which is four control arms and
leaves no room for the dose-response or the placebo. NOBUY30, HARD30 and DIVONLY30 partition the
pool between them (splits alone are already measured, by M0241 at the same fees on the same
tape), and the two controls are the arms that can actually disprove the thesis. That substitution
is deliberate and is the one assumption this file makes about its own brief.

WHAT EACH GESTURE IS, AND WHEN IT IS PUBLIC.

    * ``split`` -- a forward split whose *ex-date* falls in the trailing window. The store's
      ``splits.csv`` sits behind its own adjusted closes and ``ShareCounts.split_factor`` answers
      the product of the ratios effective in a half-open span, so the exact ex-date is recovered
      by binary search over that span (``split_day``) and never read from the future: the product
      of the splits the vendor applied *after* the store's window is held separately and is not
      reachable from here. Reverse splits (ratios of 0.1, 0.5) are distress, the opposite signal,
      and are never a buy. **The ex-date is not the announcement** -- the shares begin trading
      split-adjusted three to six weeks after the board speaks -- and that is M0241's central
      weakness, inherited here unchanged.
    * ``init`` -- a dividend in the window that is either the company's first in the store or
      follows the previous one by at least ``RESUME_DAYS``, and whose ex-date is at least
      ``BASE_DAYS`` after the symbol's first bar, so the first payment the store happens to see is
      not mistaken for a first payment.
    * ``raise`` -- a dividend in the window at least ``RAISE_MIN`` above the median of its up-to-
      four predecessors inside the ``BASE_DAYS`` before it, and no more than ``RAISE_MAX`` above,
      which drops one-off specials (M0242 rejected those separately).
    * ``buyback`` -- the newest share count public on the day, filed inside the window, whose
      split-adjusted count is at least ``SHRINK_MIN`` below the count public a year earlier. The
      event date is the *filing* day: a repurchase becomes news when the filing lands. M0227's
      guards are kept: the two figures must have been counted at least 180 days apart, a ratio
      near a common split ratio is read as a split the split table missed, and a ratio outside
      0.5-3.0 is read as a filing stated in different units.

Dividends are read by **ex-date** (``known_on``), never by declaration date (``announced_on``).
That is the conservative choice and it is also the robust one: ``dividend_announcements.csv`` is
optional and has twice vanished from a rebuilt store, and a method that silently falls back to
its own ex-date control is the failure mode ``preflight_data`` exists to make impossible. This
file never has that fallback because it never asks.

THE HOLD DIAL IS LIVE HERE, AND IT IS NOT IN ITS ANCESTORS. M0070's ``live_event`` reads only the
*latest* payment, so a company that raises and then pays three ordinary dividends stops counting
as a raiser about a quarter later whatever the hold is set to; the median gap to the next payment
is 91 days, which makes any hold above about 91 days inert across eighteen method files on that
chassis. ``dividend_day`` here scans backwards through every payment inside the window and
returns the newest one that really is an initiation or a raise, so a 380-day window holds for 380
days. Nothing else in this file depends on that, but the difference is real and the comparison
with the dividend family's trials is only fair with it said out loud.

SIZING AND RULES. Equal weight across however many names qualify, each capped at 20%, whatever
the cap leaves over stays in cash: a 30-name month is fully invested at 3.3% each, a three-name
month is 60% invested and the cash is reported rather than hidden. No preference for names
already held -- that would keep a name for a year while 200 fresher gestures queued behind it,
and it would break the placebo's shape match. ``MONTHLY_HOLD_FRAC_GOTRADE_TBAND`` on every arm:
fractional shares at Gotrade's real fees, resized against each holding's own target rather than
the whole account, because under the account-wide band a 30-name book is barely resized at all
and drifts into cash for reasons that have nothing to do with any board.

Pure: every read is of bars, membership, dividend ex-dates, share counts and split ex-dates dated
on or before ``data_date``; the placebo's hash is a function of its inputs.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import Market, ShareCounts
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0187_placebo_hash_order import draw
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE_TBAND
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorParams,
    FactorPrepared,
    FactorRow,
    factor_lookback,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 10, 19)

#: A split counts as forward when the ratio product clears this. A reverse split is distress.
FORWARD = 1.0001
#: Bars a symbol must have before a dividend for its "first" payment to be believed as a first.
BASE_DAYS = 400
#: How many predecessors the raise test takes the median of.
BASE_N = 4
#: A payment this far above its base is a raise; this far and more is a special, not a raise.
RAISE_MIN = Decimal("0.10")
RAISE_MAX = Decimal("1.00")
#: A gap at least this long before a payment makes it a resumption, which counts as an initiation.
RESUME_DAYS = 730
#: Calendar days between the two share counts a buyback is measured over, and the minimum gap
#: between the days those two figures were *counted* for the pair to say anything.
SHARE_LOOKBACK_DAYS = 365
MIN_COUNT_GAP_DAYS = 180
#: The share count must have fallen at least this far for the filing to read as a buyback.
SHRINK_MIN = 0.03
#: M0227's two guards against a filing that is not what it looks like.
SPLIT_RATIOS = (2.0, 3.0, 4.0, 1.5, 0.5, 1.0 / 3.0, 0.25, 2.0 / 3.0)
SPLIT_TOLERANCE = 0.03
RATIO_BAND = (0.5, 3.0)

KINDS = ("split", "init", "raise", "buyback")
ARMS = ("fresh", "stale", "placebo")

#: The screen every arm shares: the lab's usual liquidity and price floor, and the SPY 200-day
#: gate. ``top`` here is the screen's own cap and is not the book's size.
SCREEN = FactorParams(rank="momentum", top=1000)


@dataclass(frozen=True, slots=True)
class GestureParams:
    """Which gestures count, how fresh they must be, how many names, and which arm."""

    window_days: int = 380
    top: int = 30
    cap: float = 0.20
    kinds: tuple[str, ...] = KINDS
    arm: str = "fresh"
    seed: int = 0
    screen: FactorParams = SCREEN

    def __post_init__(self) -> None:
        if isinstance(self.window_days, bool) or not isinstance(self.window_days, int):
            raise TypeError(f"window_days must be an int, got {type(self.window_days).__name__}")
        if not 28 <= self.window_days <= 760:
            raise ValueError(f"window_days must lie in [28, 760], got {self.window_days}")
        if isinstance(self.top, bool) or not isinstance(self.top, int) or not 1 <= self.top <= 200:
            raise ValueError(f"top must be an int in [1, 200], got {self.top!r}")
        if isinstance(self.cap, bool) or not isinstance(self.cap, (int, float)):
            raise TypeError(f"cap must be a number, got {type(self.cap).__name__}")
        if not 0.01 <= self.cap <= 1.0:
            raise ValueError(f"cap must lie in [0.01, 1], got {self.cap}")
        if not isinstance(self.kinds, tuple) or not self.kinds:
            raise ValueError(f"kinds must be a non-empty tuple, got {self.kinds!r}")
        if len(set(self.kinds)) != len(self.kinds):
            raise ValueError(f"kinds must not repeat, got {self.kinds!r}")
        for k in self.kinds:
            if k not in KINDS:
                raise ValueError(f"each kind must be one of {KINDS}, got {k!r}")
        if self.arm not in ARMS:
            raise ValueError(f"arm must be one of {ARMS}, got {self.arm!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise ValueError(f"seed must be a non-negative int, got {self.seed!r}")
        if not isinstance(self.screen, FactorParams):
            raise TypeError(f"screen must be FactorParams, got {type(self.screen).__name__}")
        if self.arm == "stale" and self.window_days * 2 > 760:
            raise ValueError("the stale arm reads back 2 x window_days, which must stay <= 760")

    def as_dict(self) -> dict[str, str]:
        trend = self.screen.trend
        return {
            "window_days": str(self.window_days),
            "top": str(self.top),
            "cap": repr(float(self.cap)),
            "kinds": "+".join(sorted(self.kinds)),
            "arm": self.arm,
            "seed": str(self.seed),
            "forward_only": repr(FORWARD),
            "raise_min": str(RAISE_MIN),
            "raise_max": str(RAISE_MAX),
            "resume_days": str(RESUME_DAYS),
            "base_days": str(BASE_DAYS),
            "shrink_min": repr(SHRINK_MIN),
            "share_lookback_days": str(SHARE_LOOKBACK_DAYS),
            "min_count_gap_days": str(MIN_COUNT_GAP_DAYS),
            "dividend_timing": "ex-date",
            "trend": "none" if trend is None else f"{trend[0]}/{trend[1]}",
            "min_dollar_volume": repr(self.screen.min_dollar_volume),
            "min_price": repr(self.screen.min_price),
            "sizing": "equal-capped-rest-cash",
        }


def _check(params: object) -> GestureParams:
    if not isinstance(params, GestureParams):
        raise TypeError(f"params must be GestureParams, got {type(params).__name__}")
    return params


# --------------------------------------------------------------------------- the four gestures


def split_day(shares: ShareCounts, symbol: str, after: date, through: date) -> date | None:
    """The newest forward-split ex-date in ``(after, through]``, or None.

    ``split_factor(s, t, through)`` is the product of the ratios effective in ``(t, through]``, so
    it clears ``FORWARD`` exactly while ``t`` is before the newest such ex-date ``e``. Binary
    search for the largest ``t`` that still clears it; ``e`` is the next day. About nine probes,
    and only for the handful of symbols that split at all. The product of the splits applied after
    the store's window is held separately by ``ShareCounts`` and is unreachable from here, so a
    future split can never answer.
    """
    if after >= through or shares.split_factor(symbol, after, through) <= FORWARD:
        return None
    lo, hi = after, through  # split_factor(lo, through) > FORWARD; hi is the first that may not
    while (hi - lo).days > 1:
        mid = lo + timedelta(days=(hi - lo).days // 2)
        if shares.split_factor(symbol, mid, through) > FORWARD:
            lo = mid
        else:
            hi = mid
    return lo + timedelta(days=1)


def dividend_day(
    paid: tuple[tuple[date, Decimal], ...],
    first_bar: date | None,
    after: date,
    through: date,
    want_init: bool,
    want_raise: bool,
) -> date | None:
    """The newest ex-date in ``(after, through]`` that is an initiation or a raise, or None.

    Scans backwards through every payment inside the window rather than reading only the latest
    one, so a company that raised and then paid two ordinary dividends is still a raiser until the
    raise itself ages out. That is the difference from ``m0070.live_event``, and it is what makes
    ``window_days`` an actual dial rather than a decoration.
    """
    for i in range(len(paid) - 1, -1, -1):
        e, amount = paid[i]
        if e > through:
            continue
        if e <= after:
            return None
        since = e - timedelta(days=BASE_DAYS)
        prior = [a for d, a in paid[:i] if d > since][-BASE_N:]
        if not prior:
            if want_init and first_bar is not None and first_bar <= since:
                return e
            continue
        if i > 0 and (e - paid[i - 1][0]).days >= RESUME_DAYS:
            if want_init and first_bar is not None and first_bar <= since:
                return e
            continue
        if not want_raise:
            continue
        ratio = amount / statistics.median(prior) - 1
        if RAISE_MIN <= ratio <= RAISE_MAX:
            return e
    return None


def looks_like_split(ratio: float) -> bool:
    """True when ``ratio`` sits within ``SPLIT_TOLERANCE`` of a common split ratio (M0227)."""
    return any(abs(ratio / r - 1.0) <= SPLIT_TOLERANCE for r in SPLIT_RATIOS)


def buyback_day(shares: ShareCounts, symbol: str, after: date, through: date) -> date | None:
    """The filing day of a count that is ``SHRINK_MIN`` below the one a year earlier, or None.

    The filing day is the event: a repurchase becomes public when the filing lands, not when the
    board authorised it. Only the newest count is considered, so the gesture ages out of the
    window with the filing that reported it.
    """
    now_c = shares.count(symbol, through)
    if now_c is None or not (after < now_c.filed <= through):
        return None
    then = through - timedelta(days=SHARE_LOOKBACK_DAYS)
    old_c = shares.count(symbol, then)
    if old_c is None or (now_c.counted - old_c.counted).days < MIN_COUNT_GAP_DAYS:
        return None
    now_n, old_n = shares.shares_on(symbol, through), shares.shares_on(symbol, then)
    if now_n is None or old_n is None or not (now_n > 0.0 and old_n > 0.0):
        return None
    ratio = now_n / (old_n * shares.split_factor(symbol, then, through))
    if not math.isfinite(ratio) or not RATIO_BAND[0] < ratio < RATIO_BAND[1]:
        return None
    if looks_like_split(ratio):
        return None
    return now_c.filed if ratio <= 1.0 - SHRINK_MIN else None


def gesture_day(
    market: Market,
    symbol: str,
    first_bar: date | None,
    after: date,
    through: date,
    kinds: AbstractSet[str],
) -> date | None:
    """The newest event date among the enabled gestures inside ``(after, through]``, or None."""
    days: list[date] = []
    if "split" in kinds:
        d = split_day(market.shares, symbol, after, through)
        if d is not None:
            days.append(d)
    if "init" in kinds or "raise" in kinds:
        d = dividend_day(
            market.dividends.known_on(symbol, through), first_bar, after, through,
            "init" in kinds, "raise" in kinds,
        )
        if d is not None:
            days.append(d)
    if "buyback" in kinds:
        d = buyback_day(market.shares, symbol, after, through)
        if d is not None:
            days.append(d)
    return max(days) if days else None


# --------------------------------------------------------------------------- the three arms


def first_bar_of(h: History | None) -> date | None:
    if h is None or len(h) == 0:
        return None
    return h.dates[0].astype(object)


def pool_events(
    market: Market,
    history: Mapping[str, History],
    rows: list[FactorRow],
    data_date: date,
    after: date,
    kinds: AbstractSet[str],
) -> dict[str, date]:
    """Each screened symbol's newest gesture date inside ``(after, data_date]``."""
    out: dict[str, date] = {}
    for r in rows:
        d = gesture_day(
            market, r.symbol, first_bar_of(history.get(r.symbol)), after, data_date, kinds
        )
        if d is not None:
            out[r.symbol] = d
    return out


def freshest(events: Mapping[str, date], top: int) -> list[str]:
    """The ``top`` symbols with the newest gesture; ties break on the symbol."""
    return [s for _, s in sorted(((-d.toordinal(), s) for s, d in events.items()))][:top]


def month_index(event: date, data_date: date) -> int:
    """How many calendar months back from ``data_date``'s month ``event`` fell."""
    return (data_date.year - event.year) * 12 + (data_date.month - event.month)


def placebo_book(
    events: Mapping[str, date], rows: list[FactorRow], data_date: date, p: GestureParams
) -> list[str]:
    """The real book's month-by-month composition, with none of its identities.

    For each trailing calendar month, newest first, how many screened members' newest gesture
    actually fell in that month, then that many names from the same screened pool in a hash order
    seeded on that month, skipping names a fresher month already took, stopping at exactly the
    number of names the real book holds today. Count, composition by cohort, stickiness and
    turnover all match by construction.
    """
    target = min(p.top, len(events))
    pool = sorted(r.symbol for r in rows)
    if not pool or not target:
        return []
    counts: dict[int, int] = {}
    for e in events.values():
        k = month_index(e, data_date)
        counts[k] = counts.get(k, 0) + 1
    out: list[str] = []
    taken: set[str] = set()
    for k in sorted(counts):
        if len(out) >= target:
            break
        n = counts[k]
        y, m = data_date.year, data_date.month - k
        while m < 1:
            m += 12
            y -= 1
        stamp = date(y, m, 1)
        for s in sorted(pool, key=lambda s: (draw(p.seed, s, stamp), s)):
            if n <= 0 or len(out) >= target:
                break
            if s in taken:
                continue
            taken.add(s)
            out.append(s)
            n -= 1
    return out


def weights(n: int, cap: float) -> Decimal | None:
    """One name's weight in an ``n``-name equal book capped at ``cap``; the rest stays in cash."""
    if n < 1:
        return None
    w = min(equal_weight(n), Decimal(repr(float(cap))))
    return w if w > 0 else None


@dataclass(frozen=True, slots=True, eq=False)
class GesturePrepared:
    """The shared factor columns and the market whose calendars pick the names."""

    factor: FactorPrepared
    history: Mapping[str, History]
    market: Market | None


class BoardConfidenceAllocator:
    """Members whose boards most recently split, started or raised a dividend, or bought back
    stock -- or the stale / placebo control -- equal weight under a cap, behind the SPY gate."""

    id = "M0244"
    market_fields = ("dividends", "shares")

    def lookback(self, params: Any) -> int:
        return factor_lookback(_check(params).screen)

    def symbols(self, params: Any) -> tuple[str, ...]:
        trend = _check(params).screen.trend
        return () if trend is None else (trend[0],)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(
        self,
        prepared: GesturePrepared,
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        p: GestureParams,
    ) -> tuple[Target, ...]:
        market = prepared.market
        if market is None:  # the history-only path has no calendars: target nothing
            return ()
        if len(market.shares) == 0 or len(market.dividends) == 0:
            return ()
        if not trend_on(prepared.history, data_date, p.screen):
            return ()
        rows = [
            r
            for r in prepared.factor.rows_on(members, data_date, p.screen)
            if r.symbol not in EXCLUDED
        ]
        if not rows:
            return ()
        close = {r.symbol: r.close for r in rows}
        kinds = frozenset(p.kinds)
        recent = data_date - timedelta(days=p.window_days)
        if p.arm == "stale":
            older = data_date - timedelta(days=2 * p.window_days)
            events = pool_events(market, prepared.history, rows, data_date, older, kinds)
            events = {s: d for s, d in events.items() if d <= recent}
            chosen = freshest(events, p.top)
        else:
            events = pool_events(market, prepared.history, rows, data_date, recent, kinds)
            chosen = (
                placebo_book(events, rows, data_date, p)
                if p.arm == "placebo"
                else freshest(events, p.top)
            )
        w = weights(len(chosen), p.cap)
        if w is None:
            return ()
        out: list[Target] = []
        for s in chosen:
            t = target_from_close(s, close[s], w)
            if t is not None:
                out.append(t)
        return tuple(out)

    def targets(
        self,
        history: Mapping[str, History],
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        p = _check(params)
        return self._run(
            GesturePrepared(prepare_factor(history), history, None), members, data_date, held, p
        )

    def prepare(self, history: Mapping[str, History]) -> Any:
        return GesturePrepared(prepare_factor(history), history, None)

    def prepare_market(self, market: Market) -> Any:
        return GesturePrepared(prepare_factor(market.history), market.history, market)

    def targets_prepared(
        self,
        prepared: Any,
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        if not isinstance(prepared, GesturePrepared):
            raise TypeError(f"prepared must be GesturePrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params))


ALLOC = BoardConfidenceAllocator()

def _v(suffix: str, params: GestureParams, rationale: str) -> Candidate:
    return Candidate(
        id=f"M0244-{suffix}",
        family="M0244",
        rules=MONTHLY_HOLD_FRAC_GOTRADE_TBAND,
        allocator=ALLOC,
        params=params,
        rationale=rationale,
        added=ADDED,
        owner_inputs=(),
    )


METHOD = Method(
    id="M0244",
    name="Buy the companies whose boards most recently did something confident",
    family="stock-corporate-confidence",
    source_kind="variation",
    source_ref="M0241",
    parent_id="M0241",
    hypothesis=(
        "A share split, a first-ever dividend, a dividend raised after a flat stretch and a large "
        "buyback are the same gesture in four costumes: a board spending money or credibility to "
        "say it believes the current price is a floor rather than a ceiling. M0241 found that "
        "recent splitters beat a shape-matched book by about two points a year and that the lead "
        "decays with time since the split, but it failed because after 2008 the store's members "
        "produce only 11-27 splits a year. Counting the pooled calendar before writing this file "
        "showed the reserved idea's premise is wrong in a useful way: the pool is not thin, it is "
        "enormous -- a median of 213 of about 350 screened members carry a live gesture in "
        "2009-2015, because a routine annual dividend raise is not rare. So pooling cannot be the "
        "instrument; freshness is. Hold the 30 members whose newest gesture of any kind is the "
        "most recent, equal weight with no name above 20%, behind the SPY 200-day gate, monthly, "
        "in fractional shares at Gotrade's real fees on the owner's monthly top-up. With 213 "
        "names live and 30 slots the only thing choosing the book is how recently the board acted, "
        "which is exactly the quantity M0241 found decays, now measured on a calendar that never "
        "empties. Three arms cut the pool -- without buybacks, without the routine raise, and "
        "dividends only -- and two controls can disprove it: a stale arm holding gestures one to "
        "two years old and nothing since, and a placebo matched to the real book's count, cohort "
        "composition and turnover month by month."
    ),
    expected_failure=(
        "Three ways, in order of likelihood. First, the pool is three members in five, so the "
        "book is a gated equal-weight slice of the payout-paying index and lands on the placebo, "
        "which is how M0241 lost about half its apparent lead. Second, dividend raises are 187 of "
        "the 239 live gestures in 2015, so the pooled book is the stock-dividend-change-drift "
        "family (68 trials, best MAR 0.57) wearing an event costume, and DIVONLY30 will match "
        "FRESH30 while HARD30 -- the rare, genuinely costly gestures -- trails on a thinner book. "
        "Third, and specific to this instrument: with 213 names queued for 30 slots and no "
        "preference for names already held, roughly half the book turns over every month, and at "
        "a 20M IDR account a 30-way split is a $44 slot paying Gotrade's real fee twice a trade. "
        "That drag is several points a year and nothing here offsets it, so a small genuine edge "
        "in the freshest gestures can be true and still lose. The most likely verdict is a book "
        "that tracks its own placebo inside the noise, with whatever lead it has earned before "
        "2001 and nothing left after 2009 -- the era this lab weighs most. Published in 1995, "
        "1996 and 2008, all three anomalies had been in print for years before the dev window "
        "closes, so any strong dev result should be expected to fade."
    ),
    candidates=(
        _v("FRESH30", GestureParams(),
           "the 30 members whose newest gesture of any of the four kinds is the most recent"),
        _v("NOBUY30", GestureParams(kinds=("split", "init", "raise")),
           "the same without buybacks: does the repurchase arm add anything or only drag?"),
        _v("HARD30", GestureParams(kinds=("split", "init", "buyback")),
           "the rare, costly gestures only -- the routine annual raise dropped"),
        _v("DIVONLY30", GestureParams(kinds=("init", "raise")),
           "dividends only: is the pooled book just the dividend-change family in a costume?"),
        _v("STALE30", GestureParams(arm="stale"),
           "newest gesture one to two years old and none since: does the date do any work?"),
        _v("PLACEBO30", GestureParams(arm="placebo", seed=244),
           "FRESH30's count, cohort composition and turnover, hash-drawn names"),
    ),
    seen_keys=(
        "concept:pooled-board-confidence-gestures",
        "concept:gesture-recency-ranking",
        "concept:dividend-raise-plus-split-plus-buyback-pool",
    ),
)

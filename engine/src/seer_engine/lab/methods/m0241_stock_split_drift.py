"""M0241 — Buy the companies that just split their shares.

Source: Ikenberry, Rankine & Stice (1996), "What Do Stock Splits Really Signal?", JFQA 31(3)
357-375; Walker (2021), post-split underreaction, IRFA. Reserved by Sera 20261019-0853.

Why. A share split changes nothing a company owns. Two shares at $50 are one share at $100. So
a board that splits is spending money on a cosmetic act, and the finance literature reads that as
a signal: a board splits when it believes the price it is splitting from is a level the company
can hold, which is a statement about the future it will not otherwise make. Ikenberry, Rankine
and Stice measured US splitters beating matched peers by about 8% over the following year.

Why it is testable here at all. The research store carries ``splits.csv`` -- the split ex-dates
behind its own adjusted closes -- and ``Market.shares.split_factor(symbol, after, through)``
answers the product of the ratios effective in ``(after, through]``. A split ex-date is public on
the day it happens, so reading "did this member split in the last twelve months" on ``data_date``
reads nothing dated after it. The file stops at the store's window end, and the product of the
splits applied *after* the window is held separately and never read here, so no future split can
leak in. Declared ``market_fields = ("shares",)``: ``lab run`` refuses this on a store with no
split file, and the history-only path targets nothing.

THE EX-DATE IS NOT THE ANNOUNCEMENT. This is the method's central weakness and it is written
here before any result. Ikenberry measured from the *announcement*; the store knows only the day
the shares began trading split-adjusted, typically three to six weeks later. If the market prices
the signal when the board says it, the lab is buying after the news. Whether anything is left is
exactly what the twelve-month and six-month arms are asked.

How thin the signal is, measured on the dev store before this file was written (feasibility, not
a result): at a twelve-month window the book holds 5 names at its thinnest and 68 at its widest,
median 22, and never fewer than 5. At six months it holds nothing at all in eleven of 238
month-ends. Splits were common in the late nineties (50-95 a year across the store's members) and
became rare after 2008 (11-27 a year). So the twelve-month window is the main arm -- it is also
the horizon the paper measured -- and the six-month arm is asked whether the drift is front-loaded
enough to survive holding a much emptier book.

The six arms:

    * SPLIT12 -- every eligible member whose ex-date fell in the trailing 380 days, equal weight,
      no name above 20%, behind the SPY 200-day trend gate. The main arm.
    * SPLIT6 -- the same at 190 days. Is the drift front-loaded, and does the cash the thinner
      book sits in eat the answer?
    * FRESH20 -- the twelve-month pool cut to the 20 most recently split. Drift decays with time
      since the event, and a 68-name book at a 20M IDR account pays Gotrade's fee on $21 slots.
      This arm asks whether concentrating on the freshest both sharpens the signal and stops
      paying that fee.
    * STALE -- members whose ex-date fell 380 to 760 days ago and NOT in the trailing 380. The
      dose-response control. If the drift is a one-year effect, this arm is flat; if it earns the
      same, the split is only labelling a kind of company and the date is doing nothing.
    * PLACEBO -- a book with the split calendar's shape and none of its identities. For each of
      the trailing twelve calendar months it counts how many eligible members actually split in
      that month, then draws that many names from the same eligible pool in a fixed hash order
      seeded on that month (M0187's ``draw``), newest month first, skipping names a fresher
      month already drew and stopping at exactly the number of names SPLIT12 holds that day.
      Count, stickiness and turnover are SPLIT12's by construction, so the only thing SPLIT12
      has that this does not is *which* company split.
    * SPLIT12-NOGATE -- SPLIT12 with the SPY trend gate off. The gate helped 22 of 22 variants
      whole-window and 0 of 22 after 2009 (insight on the 200-day gate), and that was measured on
      momentum books; this asks whether an event book behaves the same.

Sizing. Equal weight across however many names qualify, each capped at 20%, and whatever the cap
leaves over stays in cash. So a five-name month is fully invested at 20% each and a three-name
month is 60% invested. Nothing invents concentration the rule did not ask for, and the cash a
thin month sits in is reported rather than hidden.

Rules. ``MONTHLY_HOLD_FRAC_GOTRADE_TBAND`` on every arm: fractional shares at Gotrade's real
fees, and the resize band measured against each holding's own target rather than the whole
account, because under the account-wide band a 20-to-68 name book is barely resized at all and
drifts into cash for reasons that have nothing to do with splits.

Pure: every read is of bars, membership and split ex-dates dated <= ``data_date``; the hash is a
function of its inputs.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import Market
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

#: A split counts as a forward split when the ratio product clears this. Reverse splits (the
#: store carries ratios of 0.1 and 0.5) are the opposite signal -- distress, not confidence --
#: and are never a buy here.
FORWARD = 1.0001

ARMS = ("recent", "stale", "placebo")

#: The screen every arm shares: the lab's usual liquidity and price floor, and the SPY 200-day
#: gate. Only ``trend`` differs between arms, and only on SPLIT12-NOGATE.
SCREEN = FactorParams(rank="momentum", top=1000)


@dataclass(frozen=True, slots=True)
class SplitParams:
    """Which split window buys, how wide the book may get, and whether the gate is on."""

    window_days: int = 380
    arm: str = "recent"
    cap: float = 0.20
    top: int | None = None
    seed: int = 0
    screen: FactorParams = SCREEN

    def __post_init__(self) -> None:
        if isinstance(self.window_days, bool) or not isinstance(self.window_days, int):
            raise TypeError(f"window_days must be an int, got {type(self.window_days).__name__}")
        if not 28 <= self.window_days <= 760:
            raise ValueError(f"window_days must lie in [28, 760], got {self.window_days}")
        if self.arm not in ARMS:
            raise ValueError(f"arm must be one of {ARMS}, got {self.arm!r}")
        if isinstance(self.cap, bool) or not isinstance(self.cap, (int, float)):
            raise TypeError(f"cap must be a number, got {type(self.cap).__name__}")
        if not 0.01 <= self.cap <= 1.0:
            raise ValueError(f"cap must lie in [0.01, 1], got {self.cap}")
        if self.top is not None:
            if isinstance(self.top, bool) or not isinstance(self.top, int):
                raise TypeError(f"top must be an int or None, got {type(self.top).__name__}")
            if self.top < 1:
                raise ValueError(f"top must be >= 1, got {self.top}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError(f"seed must be an int, got {type(self.seed).__name__}")
        if not isinstance(self.screen, FactorParams):
            raise TypeError(f"screen must be FactorParams, got {type(self.screen).__name__}")
        if self.arm == "stale" and self.window_days * 2 > 760:
            raise ValueError("the stale arm reads back 2 x window_days, which must stay <= 760")

    def as_dict(self) -> dict[str, str]:
        return {
            "window_days": str(self.window_days),
            "arm": self.arm,
            "cap": repr(float(self.cap)),
            "top": "all" if self.top is None else str(self.top),
            "seed": str(self.seed),
            "forward_only": repr(FORWARD),
            "trend": "none" if self.screen.trend is None else f"{self.screen.trend[0]}/{self.screen.trend[1]}",
            "min_dollar_volume": repr(self.screen.min_dollar_volume),
            "min_price": repr(self.screen.min_price),
            "sizing": "equal-capped-rest-cash",
        }


def _check(params: object) -> SplitParams:
    if not isinstance(params, SplitParams):
        raise TypeError(f"params must be SplitParams, got {type(params).__name__}")
    return params


@dataclass(frozen=True, slots=True)
class SplitPrepared:
    """The shared factor columns and the market whose split calendar picks the names."""

    factor: FactorPrepared
    history: Mapping[str, History]
    market: Market | None


def split_in(market: Market, symbol: str, after: date, through: date) -> bool:
    """Did ``symbol`` have a forward split with an ex-date in ``(after, through]``?

    Reads the store's in-window split list only. The product of the splits the vendor applied
    *after* the store's window is held separately by ``ShareCounts`` and is not reachable from
    here, so a future split cannot answer True.
    """
    return market.shares.split_factor(symbol, after, through) > FORWARD


def month_before(d: date, k: int) -> tuple[date, date]:
    """``(day before the month start, month end)`` of the calendar month ``k`` months before ``d``.

    Both bounds are plain dates, so ``split_in`` over them is "an ex-date inside that month".
    """
    y, m = d.year, d.month - k
    while m < 1:
        m += 12
        y -= 1
    start = date(y, m, 1)
    end = date(y + (m == 12), 1 if m == 12 else m + 1, 1) - timedelta(days=1)
    return start - timedelta(days=1), end


def recent_splitters(market: Market, rows: list[FactorRow], d: date, p: SplitParams) -> list[str]:
    """The eligible symbols whose ex-date fell in the trailing ``window_days``, freshest first.

    Freshness is the index of the trailing calendar month the split fell in, so the order is a
    pure function of the calendar and ties break on the symbol.
    """
    lo = d - timedelta(days=p.window_days)
    hit = [r.symbol for r in rows if split_in(market, r.symbol, lo, d)]
    months = max(1, round(p.window_days / 30.44))
    rank: dict[str, int] = {}
    for k in range(months + 1):
        a, b = month_before(d, k)
        for s in hit:
            if s not in rank and split_in(market, s, a, min(b, d)):
                rank[s] = k
    return sorted(hit, key=lambda s: (rank.get(s, months + 1), s))


def stale_splitters(market: Market, rows: list[FactorRow], d: date, p: SplitParams) -> list[str]:
    """Eligible symbols that split in the window *before* the recent one, and not since."""
    mid = d - timedelta(days=p.window_days)
    lo = d - timedelta(days=2 * p.window_days)
    return sorted(
        r.symbol
        for r in rows
        if split_in(market, r.symbol, lo, mid) and not split_in(market, r.symbol, mid, d)
    )


def placebo_book(market: Market, rows: list[FactorRow], d: date, p: SplitParams) -> list[str]:
    """SPLIT12's shape with none of its identities.

    For each trailing calendar month, newest first, how many eligible members really split that
    month, then that many names from the same pool in a hash order seeded on that month, skipping
    names a fresher month already took. The walk stops at exactly as many names as the real
    recent-splitter book holds that day, so the two match in size to the name; because the stop
    falls on the oldest cohort, a placebo name ages out of the book the same way a real splitter
    does, and the monthly draws are stable between rebalances, so the turnover matches too.
    """
    pool = sorted(r.symbol for r in rows)
    target = len(recent_splitters(market, rows, d, p))
    if not pool or not target:
        return []
    months = max(1, round(p.window_days / 30.44))
    out: list[str] = []
    taken: set[str] = set()
    for k in range(months + 1):
        if len(out) >= target:
            break
        a, b = month_before(d, k)
        b = min(b, d)
        if b <= a:
            continue
        n = sum(1 for s in pool if split_in(market, s, a, b))
        if not n:
            continue
        order = sorted(pool, key=lambda s: (draw(p.seed, s, b), s))
        for s in order:
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


class SplitDriftAllocator:
    """Members that recently split (or the stale / placebo control), equal weight under a cap."""

    id = "M0241"
    market_fields = ("shares",)

    def lookback(self, params: Any) -> int:
        return factor_lookback(_check(params).screen)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params).screen
        return () if p.trend is None else (p.trend[0],)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(
        self,
        prepared: SplitPrepared,
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        p: SplitParams,
    ) -> tuple[Target, ...]:
        market = prepared.market
        if market is None or len(market.shares) == 0:  # no split calendar: target nothing
            return ()
        if not trend_on(prepared.history, data_date, p.screen):
            return ()
        rows = [r for r in prepared.factor.rows_on(members, data_date, p.screen) if r.symbol not in EXCLUDED]
        if not rows:
            return ()
        close = {r.symbol: r.close for r in rows}
        if p.arm == "recent":
            chosen = recent_splitters(market, rows, data_date, p)
        elif p.arm == "stale":
            chosen = stale_splitters(market, rows, data_date, p)
        else:
            chosen = placebo_book(market, rows, data_date, p)
        if p.top is not None:
            chosen = chosen[: p.top]
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
            SplitPrepared(prepare_factor(history), history, None), members, data_date, held, p
        )

    def prepare(self, history: Mapping[str, History]) -> Any:
        return SplitPrepared(prepare_factor(history), history, None)

    def prepare_market(self, market: Market) -> Any:
        return SplitPrepared(prepare_factor(market.history), market.history, market)

    def targets_prepared(
        self,
        prepared: Any,
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        if not isinstance(prepared, SplitPrepared):
            raise TypeError(f"prepared must be SplitPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params))


ALLOC = SplitDriftAllocator()
NOGATE = replace(SCREEN, trend=None)


def _v(suffix: str, params: SplitParams, rationale: str) -> Candidate:
    return Candidate(
        id=f"M0241-{suffix}",
        family="M0241",
        rules=MONTHLY_HOLD_FRAC_GOTRADE_TBAND,
        allocator=ALLOC,
        params=params,
        rationale=rationale,
        added=ADDED,
        owner_inputs=(),
    )


METHOD = Method(
    id="M0241",
    name="Buy the companies that just split their shares",
    family="stock-split-drift",
    source_kind="paper",
    source_ref=(
        "Ikenberry, Rankine & Stice (1996), What Do Stock Splits Really Signal?, JFQA 31(3) "
        "357-375; Walker (2021), Post-split underreaction, IRFA"
    ),
    parent_id=None,
    hypothesis=(
        "A share split gives a shareholder nothing: two shares at $50 are the same stake as one "
        "at $100. So a board that pays to split is making a statement it will not otherwise "
        "make, that the price it is splitting from is a level the company can hold. Ikenberry, "
        "Rankine and Stice (1996) measured US splitters beating matched peers by about 8% over "
        "the following year. The research store carries the split ex-dates behind its own "
        "adjusted closes, so each monthly check can see which index members have split since a "
        "cut-off without reading anything dated after that day. Buy every eligible member whose "
        "ex-date fell in the trailing twelve months, equal weight with no name above 20%, behind "
        "the SPY 200-day trend gate, monthly, in fractional shares at Gotrade's real fees on the "
        "owner's monthly top-up. A six-month arm asks whether the drift is front-loaded, a "
        "twenty-name arm whether the freshest splitters carry it, a stale arm (split one to two "
        "years ago and not since) whether the date does any work at all, and a hash-order "
        "placebo built to match the split calendar's monthly count and twelve-month stickiness "
        "exactly whether the identity of the splitter matters or only the book's shape."
    ),
    expected_failure=(
        "Two ways, both likely. First, the store knows the ex-date, not the announcement, and "
        "the announcement is the event: the shares begin trading split-adjusted three to six "
        "weeks after the board speaks, so most of the drift Ikenberry measured may already be "
        "priced before this method can buy. Second, the finding was published in 1996 and the "
        "dev window ends in 2015, so it can only show an edge from before the crowd traded it; "
        "worse, US splits collapsed after 2008 (11-27 a year across the store's members against "
        "50-95 in the late nineties), so 2009-2015 -- the era this lab weighs most -- is a book "
        "of five to twenty names chosen from a nearly empty calendar, and any edge that survives "
        "there will be hard to tell from the luck of a handful of names. The most likely verdict "
        "is a good whole-window average earned entirely before 2001, with the placebo arm "
        "matching it once the book is thin enough that shape beats identity."
    ),
    candidates=(
        _v("SPLIT12", SplitParams(window_days=380, arm="recent"),
           "every eligible member that split in the trailing twelve months, equal weight, 20% cap, gated"),
        _v("SPLIT6", SplitParams(window_days=190, arm="recent"),
           "the same at six months: is the drift front-loaded enough to pay for a much emptier book?"),
        _v("FRESH20", SplitParams(window_days=380, arm="recent", top=20),
           "the twelve-month pool cut to the 20 freshest splits: sharper signal, and no $21 slots"),
        _v("STALE", SplitParams(window_days=380, arm="stale"),
           "split one to two years ago and not since: the dose-response control on the date itself"),
        _v("PLACEBO", SplitParams(window_days=380, arm="placebo", seed=241),
           "the split calendar's count and stickiness, hash-drawn names: does the identity matter?"),
        _v("SPLIT12-NOGATE", SplitParams(window_days=380, arm="recent", screen=NOGATE),
           "SPLIT12 with the SPY 200-day trend gate off, to price the gate on an event book"),
    ),
    seen_keys=(
        "concept:stock-split-drift",
        "concept:split-ex-date-event",
        "data:splits.csv-ex-dates",
    ),
)

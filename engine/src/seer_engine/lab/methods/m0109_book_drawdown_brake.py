"""M0109 — A brake on the account's own fall: trim in proportion to how far the book is below its own high.

Source: the constant-proportion floor idea (Black & Perold 1992, "Theory of constant proportion
portfolio insurance", JEDC 16(3-4)) and Grossman & Zhou (1993, "Optimal investment strategies for
controlling drawdowns", Mathematical Finance 3(3)), reduced to a proportional dial.
Idea: the lab has exactly one drawdown machine in service, the market-wide SPY-200 switch, and it
is binary -- it sells everything on a line crossing and buys everything back on another, which is
why it loses in dips that bounce before it can return. A proportional brake has no line to cross:
it reads how far the book is below its own running high and holds a fraction of full exposure
that falls as the book falls, so a 4% dip costs a small, quickly restored slice and a 2008 that
keeps grinding lower keeps cutting until little is left.

WHAT IS BEING MEASURED. This method is a measurement first and a candidate second. The brake is
priced on a deliberately neutral base -- an equal-weight book of the most-traded index members,
with no stock picking at all -- so that the number it produces is the cost and the saving of the
BRAKE, not of a ranking. Two controls run beside it (one per execution clock) and the braked runs
are read against them.

THE BASE BOOK, in full. On a rank session d, among the point-in-time index members that are not
ETFs, have at least 20 bars through d, a close of at least ``min_price`` and a 20-session mean
close x volume above ``min_dollar_volume``, take the ``top`` names with the HIGHEST dollar volume
and hold them at 1/``top`` each. Nothing is ranked on returns, volatility, fundamentals or
calendar: the only sort key is how much money changes hands in the name. The book is therefore a
crude, liquidity-weighted-by-selection, equal-weight-by-sizing slice of the large US market. It
has no trend gate and no stop: the brake is the only risk machine in the method, which is the
whole point.

THE SHADOW INDEX, and what it is not. An allocator sees bars, members, the data date and what the
book holds; it never sees the account's equity curve, so "how far the book is below its own high"
has to be rebuilt from bars. ``shadow_wealth`` rebuilds it: it re-picks the same book at every
month end of the market symbol's calendar and chains those equal-weight baskets day by day. Five
things about that reconstruction are worth stating plainly, because they are what could fool us:

  * It is the UNBRAKED book, deliberately. A brake that reads its own braked account is a
    ratchet: once trimmed, the account stops falling, so its drawdown stops recovering and the
    exposure never comes back. Reading the unbraked book asks the question the brake actually
    wants answered -- "how far is this kind of book below its high" -- and re-enters when the
    market recovers rather than when the trimmed account does. It also keeps the signal a pure
    function of bars.
  * It is MEMBERSHIP-FREE. Point-in-time membership reaches an allocator only through
    ``prepare_market``, which the lab reserves for the fundamentals, dividend and series panels,
    and a market-aware allocator's live path is not the path the contract test drives. So the
    shadow ranks every symbol in the store's price history except a fixed list of ETFs. Those
    symbols ARE the index members, past and present, plus a handful of funds that are excluded by
    name, so the shadow's basket and the book's basket are near-identical; where they differ the
    shadow is slightly broader. It is a signal, not an accounting.
  * It is GROSS: no fees, no deposits, no cash drag, no dividends. A deposit-funded account's own
    high is lifted by every top-up, which would make a brake read off the real account bite more
    often than a lump-sum backtest suggests; reading a gross index removes that distortion
    entirely, and means the same brake reads the same way at any account size.
  * The running high is TRAILING, over ``peak_n`` sessions, not since inception. An inception
    high leaves a book that has had one bad decade permanently braked. A one-year high was
    chosen over a longer one on measured behaviour, not taste: on this store a three-year high
    still holds the 2000 top against the book through 2003-2007 and the 2007 top through
    2010-2015, so average exposure in both recoveries sits near 0.6 and the brake would be
    guaranteed to lose the best-covered years before the run even starts. A one-year high leaves
    exposure near 0.8 in those stretches and still cuts to about 0.2 through 2000-2002 and
    2008-2009, because in a grinding bear each new low is still below the high of the year
    behind it.
  * It needs ``WARM`` sessions of calendar before it is allowed to act at all. Where that depth is
    absent the brake stands down and the variant IS its control -- a hard on/off on a fixed
    session count, never a shortened window, so the P4 identity holds either way. On the real dev
    store the calendar opens in January 1993 and the dev window opens at ``MEMBERSHIP_START``
    (1996-01-02), about 750 sessions later, so the brake is warm before the first scored session.
    The analysis verifies that rather than assuming it.

WHAT WAS CALIBRATED BEFORE THE RUN, and what was not. Two choices were made by looking at the
dev window: the book's size and the length of the running-high window. Both were made on
EXPOSURE and DRAWDOWN statistics of the unbraked shadow alone -- no braked return was computed
before the variants were fixed -- and both were made to stop the experiment from being
degenerate rather than to find a winner. The 30 most-traded names turned out not to be a neutral
base at all: in March 2000 that list was Microsoft, Cisco, Intel, Oracle, JDS Uniphase, Qualcomm,
Applied Materials, Ciena, VeriSign and Micron, and the book fell 70% from the 2000 top, worse
than SPY's 56%. Ranking on how much money changes hands is an attention tilt, so a brake priced
on it would have been flattered by a crash the base invited. Fifty names falls 58%, about SPY's
own fall, and is the broadest book whose slots are still big enough to trade: a 20M IDR account
split fifty ways is a $29 slot, which is exactly where Gotrade's fee schedule was measured. A
hundred names is more neutral still and was rejected because a $14 slot pays about a point a
side. Everything else -- the tapers, the floor, the clocks, the screen -- is as the idea was
reserved.

THE DIAL. At the data date's calendar index j, ``peak`` is the highest shadow wealth over the
``peak_n`` sessions through j and ``dd`` is how far below it the shadow sits. Exposure is
``1 - dd / taper``, clipped into ``[floor, 1]`` and rounded to the nearest ``STEP``: full exposure
at the high, ``floor`` by the time the shadow is down ``taper``, and a straight line between. Every
target weight is multiplied by it; the rest is cash. ``taper = None`` is the control, exposure 1.
``STEP`` exists so that a 1% wobble does not reprice thirty legs: it is a fixed property of the
method, not a dial, and it rounds to nearest so that exposure is still exactly 1 at the high.

THE CLOCK. The book engine calls an allocator on rank sessions and resize sessions only, so the
brake can be read no faster than the rule set's resize cadence. The two promotable fractional
real-fee presets give monthly and weekly; there is no daily-resize preset, so "read daily" -- the
reserved idea's fastest variant -- is not available without a new preset, and a feature wish is
journalled for one. Weekly is the fastest promotable clock and is what the -W variants use. The
shadow itself is still measured every session, so a fall between two checks is seen in full at the
next check; only the trimming waits for the clock.

Every piece reads only bars dated <= d.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field, replace
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import ReturnGrid, build_grid
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import (
    MONTHLY_HOLD_FRAC_GOTRADE,
    MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE,
)
from seer_engine.strategies.allocator import scale_weight, target_from_close
from seer_engine.strategies.base import History, as_day
from seer_engine.strategies.f_factor import DV_N, FactorPrepared, prepare_factor
from seer_engine.strategies.indicators import mean_dollar_volume_window

ADDED = date(2026, 10, 12)

ONE = Decimal(1)
STEP = Decimal("0.05")  # exposure is rounded to the nearest step, so a small wobble trades nothing
WARM = 504  # sessions of calendar the shadow needs before the brake may act (about two years)

#: Never a holding and never part of the shadow's universe. The store serves index members plus
#: these funds; a fund in a "most traded names" book would be the market, not a book of names.
EXCLUDED_ETFS: frozenset[str] = frozenset(
    {"SPY", "QQQ", "BIL", "DIA", "EFA", "IEF", "IWM", "TLT", "GLD",
     "XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"}
)


# --------------------------------------------------------------------------- params


@dataclass(frozen=True, slots=True)
class BrakeParams:
    """The base book's screen and size, plus the proportional drawdown brake on top of it."""

    top: int = 50  # names held, equal weight 1/top
    min_dollar_volume: float = 20_000_000.0  # 20-session mean close x volume > this (strict)
    min_price: float = 5.0  # close >= this
    taper: Decimal | None = None  # shadow drawdown at which exposure reaches `floor`; None = control
    floor: Decimal = Decimal("0")  # the least exposure the taper reaches
    peak_n: int = 252  # sessions the shadow's running high is taken over (about one year)
    market: str = "SPY"  # the calendar the shadow is laid on

    def __post_init__(self) -> None:
        if isinstance(self.top, bool) or not isinstance(self.top, int) or not 1 <= self.top <= 200:
            raise ValueError(f"top must be an int in 1..200, got {self.top!r}")
        for name in ("min_dollar_volume", "min_price"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise TypeError(f"{name} must be a float, got {type(v).__name__}")
            if not np.isfinite(float(v)) or float(v) < 0.0:
                raise ValueError(f"{name} must be finite and >= 0, got {v!r}")
            object.__setattr__(self, name, float(v))
        if self.taper is not None:
            if not isinstance(self.taper, Decimal) or not self.taper.is_finite():
                raise TypeError(f"taper must be None or a Decimal, got {self.taper!r}")
            if not 0 < self.taper <= 1:
                raise ValueError(f"taper must be in (0, 1], got {self.taper}")
        if not isinstance(self.floor, Decimal) or not self.floor.is_finite():
            raise TypeError(f"floor must be a Decimal, got {self.floor!r}")
        if not 0 <= self.floor < 1:
            raise ValueError(f"floor must be a Decimal in [0, 1), got {self.floor}")
        if isinstance(self.peak_n, bool) or not isinstance(self.peak_n, int) or self.peak_n < 20:
            raise ValueError(f"peak_n must be an int >= 20, got {self.peak_n!r}")
        if not isinstance(self.market, str) or not self.market:
            raise ValueError(f"market must be a non-empty symbol, got {self.market!r}")

    def as_dict(self) -> dict[str, str]:
        return {
            "top": str(self.top),
            "min_dollar_volume": format(Decimal(repr(self.min_dollar_volume)).normalize(), "f"),
            "min_price": format(Decimal(repr(self.min_price)).normalize(), "f"),
            "taper": "none" if self.taper is None else str(self.taper),
            "floor": str(self.floor),
            "peak_n": str(self.peak_n),
            "market": self.market,
        }


def _check(params: object) -> BrakeParams:
    if not isinstance(params, BrakeParams):
        raise TypeError(f"params must be BrakeParams, got {type(params).__name__}")
    return params


# --------------------------------------------------------------------------- the base book


@dataclass(frozen=True, slots=True)
class Row:
    """One eligible name at a data date's close: its price and how much of it trades."""

    symbol: str
    close: float
    dollar_volume: float


def _eligible(close: np.ndarray, dv: np.ndarray, p: BrakeParams) -> np.ndarray:
    return (
        np.isfinite(close)
        & np.isfinite(dv)
        & (dv > p.min_dollar_volume)
        & (close >= p.min_price)
    )


def book_rows(history: Mapping[str, History], universe: AbstractSet[str], data_date: date,
              p: BrakeParams) -> list[Row]:
    """Eligible names of ``universe`` on ``data_date``, sorted by symbol (the single-window path)."""
    as_day(data_date)
    symbols: list[str] = []
    ends: list[int] = []
    for symbol in sorted(universe):
        if symbol in EXCLUDED_ETFS:
            continue
        h = history.get(symbol)
        if h is None:
            continue
        i = h.index_of(data_date)
        if i is None or i + 1 < DV_N:
            continue
        symbols.append(symbol)
        ends.append(i + 1)
    if not symbols:
        return []
    close = np.stack([history[s].close[e - DV_N : e] for s, e in zip(symbols, ends, strict=True)])
    volume = np.stack([history[s].volume[e - DV_N : e] for s, e in zip(symbols, ends, strict=True)])
    with np.errstate(divide="ignore", invalid="ignore"):
        dv = mean_dollar_volume_window(close, volume, DV_N)
    last = close[:, -1]
    mask = _eligible(last, dv, p)
    return [Row(symbols[k], float(last[k]), float(dv[k])) for k in (int(j) for j in np.flatnonzero(mask))]


def prepared_rows(fp: FactorPrepared, universe: AbstractSet[str], data_date: date,
                  p: BrakeParams) -> list[Row]:
    """The same list from the precomputed columns (== ``book_rows`` on histories cut at the date)."""
    day = as_day(data_date)
    lo = int(np.searchsorted(fp.dates, day, side="left"))
    hi = int(np.searchsorted(fp.dates, day, side="right"))
    if lo == hi:
        return []
    close = fp.close[lo:hi]
    dv = fp.dollar_volume[lo:hi]
    mask = (fp.nbars[lo:hi] >= DV_N) & _eligible(close, dv, p)
    out: list[Row] = []
    for j in (int(j) for j in np.flatnonzero(mask)):
        symbol = fp.symbols[int(fp.sym[lo + j])]
        if symbol in EXCLUDED_ETFS or symbol not in universe:
            continue
        out.append(Row(symbol, float(close[j]), float(dv[j])))
    return out


def chosen(rows: list[Row], p: BrakeParams) -> list[Row]:
    """The ``top`` most-traded names, most traded first (ties by symbol ascending)."""
    return sorted(rows, key=lambda r: (-r.dollar_volume, r.symbol))[: p.top]


def book_targets(rows: list[Row], p: BrakeParams) -> tuple[Target, ...]:
    """``chosen(rows)`` at 1/top each, in rank order."""
    w = equal_weight(p.top)
    out: list[Target] = []
    for row in chosen(rows, p):
        t = target_from_close(row.symbol, row.close, w)
        if t is not None:
            out.append(t)
    return tuple(out)


# --------------------------------------------------------------------------- the shadow index


def month_end_marks(cal: np.ndarray) -> np.ndarray:
    """Indices m of ``cal`` whose next session is in a new calendar month (so always m < len - 1).

    Requiring a NEXT session is what makes the marks identical on a history cut at any date d:
    the final index of a truncated calendar is never a mark on either path, and every earlier
    mark is a mark on both.
    """
    months = cal.astype("datetime64[M]")
    return np.flatnonzero(months[1:] != months[:-1])


def _basket_path(grid: ReturnGrid, rows: np.ndarray, lo: int, hi: int, start: float) -> np.ndarray:
    """The equal-weight basket's wealth over sessions ``lo + 1 .. hi``, beginning at ``start``.

    A name with no usable return on a session is dropped from that session's mean rather than
    counted as zero; a session with no usable name at all earns nothing.
    """
    n = hi - lo
    if rows.size == 0:
        return np.full(n, start, dtype=np.float64)
    block = grid.rets[rows, lo + 1 : hi + 1]
    ok = np.isfinite(block)
    count = ok.sum(axis=0)
    total = np.where(ok, block, 0.0).sum(axis=0)
    daily = np.where(count > 0, total / np.maximum(count, 1), 0.0)
    return start * np.cumprod(1.0 + daily)


def shadow_wealth(grid: ReturnGrid, picks_at: Callable[[date], tuple[str, ...]]) -> np.ndarray:
    """The unbraked book's gross wealth index over ``grid.dates``, starting at 1.0.

    Re-picks at every month-end mark and chains the equal-weight baskets. Entry t depends only on
    marks before t and returns at or before t, so the entries at or before any date d are the same
    whether the grid was built from the whole history or from history cut at d.
    """
    n = len(grid.dates)
    wealth = np.ones(n, dtype=np.float64)
    marks = month_end_marks(grid.dates)
    if marks.size == 0 or n < 2:
        return wealth
    current = 1.0
    for k in range(marks.size):
        mark = int(marks[k])
        end = int(marks[k + 1]) if k + 1 < marks.size else n - 1
        if end <= mark:
            continue
        picks = picks_at(grid.dates[mark].astype(object))
        rows = np.asarray([grid.row[s] for s in picks if s in grid.row], dtype=np.int64)
        path = _basket_path(grid, rows, mark, end, current)
        wealth[mark + 1 : end + 1] = path
        current = float(path[-1])
    return wealth


def shadow_drawdown(grid: ReturnGrid | None, wealth: np.ndarray | None, data_date: date,
                    p: BrakeParams) -> float | None:
    """How far the shadow sits below its ``peak_n``-session high at ``data_date``, or None.

    None means "not measurable here": no grid, ``data_date`` is not a session of the market
    symbol's calendar, or the calendar is shallower than ``WARM``. The caller then leaves the book
    unbraked, which is the control.
    """
    if grid is None or wealth is None:
        return None
    day = as_day(data_date)
    j = int(np.searchsorted(grid.dates, day, side="right")) - 1
    if j < 0 or grid.dates[j] != day or j + 1 < WARM:
        return None
    peak = float(np.max(wealth[max(0, j - p.peak_n + 1) : j + 1]))
    here = float(wealth[j])
    if not (np.isfinite(peak) and np.isfinite(here)) or peak <= 0.0:
        return None
    return 1.0 - here / peak


def exposure(drawdown: float | None, p: BrakeParams) -> Decimal:
    """The share of the account the brake allows: 1 at the high, ``floor`` once down ``taper``."""
    if p.taper is None or drawdown is None or drawdown <= 0.0 or not np.isfinite(drawdown):
        return ONE
    raw = 1.0 - drawdown / float(p.taper)
    clipped = min(1.0, max(float(p.floor), raw))
    stepped = (Decimal(repr(clipped)) / STEP).quantize(ONE, rounding=ROUND_HALF_UP) * STEP
    return min(ONE, max(p.floor, stepped))


def braked(base: tuple[Target, ...], share: Decimal) -> tuple[Target, ...]:
    """``base`` with every weight multiplied by ``share``; the rest of the account is cash."""
    if share >= ONE:
        return base
    if share <= 0:
        return ()
    out: list[Target] = []
    for target in base:
        weight = scale_weight(target.weight, share)
        if weight is not None:
            out.append(replace(target, weight=weight))
    return tuple(out)


# --------------------------------------------------------------------------- the allocator


@dataclass
class BrakePrepared:
    """The history, the dollar-volume columns, and one shadow index per distinct book shape."""

    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)
    cache: dict[tuple[Any, ...], tuple[ReturnGrid | None, np.ndarray | None]] = field(
        default_factory=dict, repr=False
    )

    def shadow(self, p: BrakeParams) -> tuple[ReturnGrid | None, np.ndarray | None]:
        key = (p.market, p.top, p.min_dollar_volume, p.min_price)
        hit = self.cache.get(key)
        if hit is not None:
            return hit
        grid = build_grid(self.history, p.market)
        if grid is None:
            out: tuple[ReturnGrid | None, np.ndarray | None] = (None, None)
        else:
            universe = frozenset(self.history)

            def picks_at(d: date) -> tuple[str, ...]:
                return tuple(r.symbol for r in chosen(prepared_rows(self.factor, universe, d, p), p))

            out = (grid, shadow_wealth(grid, picks_at))
        self.cache[key] = out
        return out


class DrawdownBrake:
    """The most-traded index members at equal weight, trimmed by how far that book is below its high.

    Held symbols get no special treatment: every rank session is a fresh top set and every resize
    session re-reads the brake, so a held name that falls out of the most-traded list is exited.
    """

    id = "M0109"

    def lookback(self, params: Any) -> int:
        _check(params)
        return DV_N  # what the PICKS need; the brake's own depth is WARM and it stands down below it

    def symbols(self, params: Any) -> tuple[str, ...]:
        return (_check(params).market,)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        base = book_targets(book_rows(history, members, data_date, p), p)
        if not base or p.taper is None:
            return base
        grid = build_grid(history, p.market)
        if grid is None:
            return base
        universe = frozenset(history)

        def picks_at(d: date) -> tuple[str, ...]:
            return tuple(r.symbol for r in chosen(book_rows(history, universe, d, p), p))

        wealth = shadow_wealth(grid, picks_at)
        return braked(base, exposure(shadow_drawdown(grid, wealth, data_date, p), p))

    def prepare(self, history: Mapping[str, History]) -> BrakePrepared:
        return BrakePrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, BrakePrepared):
            raise TypeError(f"prepared must be BrakePrepared, got {type(prepared).__name__}")
        p = _check(params)
        base = book_targets(prepared_rows(prepared.factor, members, data_date, p), p)
        if not base or p.taper is None:
            return base
        grid, wealth = prepared.shadow(p)
        return braked(base, exposure(shadow_drawdown(grid, wealth, data_date, p), p))


BRAKE = DrawdownBrake()


def _v(suffix: str, params: BrakeParams, rules, rationale: str) -> Candidate:
    return Candidate(id=f"M0109-{suffix}", family="M0109", rules=rules, allocator=BRAKE,
                     params=params, rationale=rationale, added=ADDED, owner_inputs=())


MONTHLY = MONTHLY_HOLD_FRAC_GOTRADE
WEEKLY = MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE


METHOD = Method(
    id="M0109",
    name="A brake on the account's own fall: trim in proportion to how far the book is below its own high, priced on a plain equal-weight book",
    family="book-drawdown-brake",
    source_kind="knowledge",
    source_ref=(
        "Black & Perold (1992), Theory of constant proportion portfolio insurance, JEDC 16(3-4), "
        "403-426; Grossman & Zhou (1993), Optimal investment strategies for controlling drawdowns, "
        "Mathematical Finance 3(3), 241-276 -- both reduced here to a proportional dial"
    ),
    parent_id=None,
    hypothesis=(
        "The lab has exactly one drawdown machine in service, the market-wide SPY-200 switch, and "
        "it is binary: it sells everything on a line crossing and buys everything back on another, "
        "which is why it loses in dips that bounce before it can return. A proportional brake has "
        "no line to cross. Read the book's own equity curve and hold a fraction of full exposure "
        "that falls as the book falls below its own running high -- full exposure at the high, a "
        "straight line down to a floor by the time the book is down a set amount, the rest in cash "
        "-- so a 4% dip costs a small, quickly restored slice of the book instead of all of it, "
        "while a 2008 that keeps grinding lower keeps cutting until little is left. Price it on a "
        "deliberately neutral base, an equal-weight book of the 50 most-traded index members with "
        "no stock picking at all, so the measurement is of the brake and nothing else, and so the "
        "result transfers to every clean book in the lab rather than to one family. The brake "
        "reads a gross shadow index of that same book rebuilt from bars, never the funded account, "
        "for two reasons: a brake that reads its own braked account is a ratchet that never "
        "re-enters, and a deposit-fed account's high is lifted by every top-up, which would make "
        "the brake bite for a reason that has nothing to do with the market. Variants: TAPER-20-W "
        "and TAPER-30-W (full exposure at the high, all cash by a 20% or 30% book drawdown, read "
        "weekly), TAPER-20-M (the same 20% taper read monthly, to price the clock separately from "
        "the shape), TAPER-20-W-F50 (the same taper stopping at half exposure rather than cash), "
        "and two controls with the brake off, EW-ALL on the monthly clock and EW-ALL-W on the "
        "weekly one, so the braked runs are read against a yardstick that pays the same trading "
        "costs. Fractional shares at Gotrade's real fees on the owner's monthly deposits, the "
        "-frac-gotrade presets, which matters here because the brake trades on every move and a "
        "20M IDR book pays a minimum fee per order. Two things were calibrated on the dev window "
        "before the variants were fixed, on the unbraked book's exposure and falls alone and "
        "never on a braked return: the book holds 50 names rather than 30, because the 30 "
        "most-traded names in March 2000 were the dot-coms and that book fell 70% where SPY "
        "fell 56%, which is not a neutral base; and the running high is the last year's rather "
        "than the last three years', because a three-year high holds the 2000 top against the "
        "book all through the 2003-2007 recovery and would lose the best-covered years by "
        "construction. Success is a measurement first: state plainly "
        "what the brake costs per year over 2009-2015 and what it saves in 2000-2002 and 2008, "
        "against the same book unbraked. Eligibility would need a braked book to beat SPY TR on "
        "deposit-matched money with a worst fall under 20% and a majority of folds. Assumption "
        "recorded before the run: the reserved idea asked for a brake read DAILY, and the book "
        "engine cannot do that at a monthly rank cadence -- the two promotable fractional real-fee "
        "presets resize monthly and weekly and there is no daily-resize preset -- so weekly is the "
        "fastest clock here and a feature wish is journalled for the preset."
    ),
    expected_failure=(
        "A drawdown brake sells after the fall has already happened and buys back after the "
        "recovery has already happened, which is the whipsaw the market switch suffers, only paid "
        "continuously instead of occasionally; it may well cost more than it saves. The most likely "
        "shape of the result is that the braked books land 1-3 points a year below the controls "
        "with a worst fall that is better by less than that, because a V-shaped fall -- 1998, 2010, "
        "2011, and the second half of 2008's rebound -- trims on the way down and is still trimmed "
        "on the way up. The weekly clock should make this worse, not better: it reacts sooner and "
        "so is wrong sooner, and at 50 slots on a 20M IDR book every re-scale pays Gotrade's fee "
        "on fifty $29 orders, about half a point a side, which is why the weekly control exists "
        "at all. The second "
        "way it fails is quieter: an equal-weight book of the most-traded index members is a bet "
        "against SPY's big-company shape even before the brake, and every lab book of that shape "
        "lost to a deposit-matched SPY after 2018, so the base itself may trail SPY TR on dev and "
        "make the brake's cost academic. The third way is that the shadow index and the real book "
        "drift apart -- the shadow is membership-free and gross -- so the brake fires on a "
        "drawdown the account did not have; the analysis checks the two against each other rather "
        "than assuming they agree."
    ),
    candidates=(
        _v("EW-ALL", BrakeParams(), MONTHLY,
           "Control: the 50 most-traded index members at equal weight, rebalanced monthly, no brake"),
        _v("EW-ALL-W", BrakeParams(), WEEKLY,
           "Control for the weekly clock: the same book re-ranked monthly and re-scaled weekly, no brake"),
        _v("TAPER-20-W", BrakeParams(taper=Decimal("0.20")), WEEKLY,
           "Weekly brake: full exposure at the book's high, straight line to all cash by a 20% fall"),
        _v("TAPER-30-W", BrakeParams(taper=Decimal("0.30")), WEEKLY,
           "Weekly brake, gentler slope: all cash only once the book is down 30%"),
        _v("TAPER-20-M", BrakeParams(taper=Decimal("0.20")), MONTHLY,
           "The 20% taper read monthly instead of weekly: the clock priced on its own"),
        _v("TAPER-20-W-F50", BrakeParams(taper=Decimal("0.20"), floor=Decimal("0.50")), WEEKLY,
           "Weekly 20% taper that stops at half the account rather than going to cash"),
    ),
    seen_keys=(
        "concept:own-drawdown-proportional-brake",
        "concept:cppi-floor-dial",
        "concept:equal-weight-most-traded-members-base",
        "concept:gross-shadow-index-as-brake-signal",
    ),
)

"""``lab turnover``: what Gotrade's schedule charges a book for trading often. Report only.

The handover of 2026-10-13 (section 2, item 3) asked for a number before any CNN/LSTM work:
*compute the turnover a short-horizon chart model would need, and run that turnover through the
fee schedule the simulator already prices.* That is this module. It builds no model, runs no
backtest, opens no research store and reads no database. It takes a **book shape** -- how many
names, how often the book is re-picked, what share of it turns over at each re-pick -- plus the
owner's real funding plan, and prices every single order through ``sim.costs.fee_parts``.

**Why this is arithmetic and not a backtest.** A backtest would answer "what would this model
have returned", which nobody can know before the model exists. The question that can be answered
today is the other one: *how much must it return before it is merely level with doing nothing.*
That question needs only the order count, the order size and the fee schedule, all three of which
are known. If the answer is larger than any plausible edge, the idea is dead and no model has to
be written. It was, and it is.

**The shape of an order.** A re-pick that replaces a name is a SELL plus a BUY, never one trade:
the sell pays an extra uncapped ``sell_extra_rate`` on top of everything the buy pays, so a round
trip is strictly dearer than twice a buy. Both sides go through :func:`sim.costs.fee_parts`, which
owns the half-up trading fee with its ``$0.10`` minimum, the rounded-up regulatory fee with its
``$0.11`` cap, the uncapped sell extra, and PPN at 11% of the two rounded HALF-DOWN. None of that
arithmetic is re-derived here; it is called.

**The floor is a transient, and pretending otherwise would be the misleading number.** At the
owner's funding -- 10,000,000 IDR to start and 5,000,000 IDR more on the 25th of every month --
a twenty-name book opens with slots of about $28, and 0.2% of $28 is $0.06, below the $0.10
minimum. That order pays the floor, and the effective rate is not 0.2% but $0.10 a slot: a round
trip costs **1.035%** of the slot in month 0. But the owner keeps depositing. By month 2 the slot
has passed $47.50 -- the exact point where 0.2% of the amount rounds up to $0.10 and the floor
stops winning -- and by month 3 the round trip is down to **0.614%**, which is where
``lab/name_count.py``'s docstring left it. Those four numbers reproduce here digit for digit, and
``tests/test_lab_turnover.py`` pins them, so the two reports can never quietly disagree.

So the floor's bite **shrinks**, and a single static fee rate would be wrong in both directions.
This module therefore reports the floor as its own column and its own month-by-month table, and
the thing that actually kills a short-horizon model is the *other* half: once the floor is gone,
a round trip settles at about **0.503%** of the slot -- 0.2% a side, plus the sell's uncapped
0.04%, plus PPN -- and a model that re-picks its book every session pays that 252 times a year.

**This prices a CADENCE, not a name count.** The name axis is here only because the floor's bite
depends on slot size. The owner's standing instruction, recorded in ``lab/name_count.py``, binds
this module too: *"do not plan a name-count reduction on fee grounds; if the lab tests
concentration, test it on the merits."* Nothing here recommends a smaller book, and nothing here
may be read as doing so.

**The horizons are the lab's own.** ``sim.rules.Cadence`` offers exactly three rank cadences, and
``sim.rules.describe_rules`` says what each means: daily is every session, weekly the first
session of each ISO week, monthly the first session of each calendar month. So the re-pick counts
are 252, 52 and 12 a year, with 252 taken from ``paper.compare.SESSIONS_PER_YEAR`` rather than
invented. Monthly is the CONTROL: it is what every live roster book already pays for, so the
grid's own baseline is a cost the lab has already accepted rather than a number chosen to flatter.

**A report, not a trial.** Nothing here writes a ``trials`` row, a ``trial_moments`` row, an
``insights`` row or a status, so ``store.dev_trial_count`` (the lab's N) and ``store.test_looks``
are exactly what they were. That is also its limit, and it is the same limit ``lab names``,
``lab exposure`` and ``lab gate`` carry: a free sweep over twenty-seven cells is exactly the
search the luck gate exists to charge for, so this grid may *inform* a decision and may never
*be* one. Nothing it prints makes any configuration eligible, and the only way a cadence is ever
judged is a new method that pre-registers it and pays for its trials like everything else.

Pure: no clock, no randomness, no network, no database, no research store, no printing. The one
file it touches is the CSV the caller explicitly asks for.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from seer_engine.lab import store
from seer_engine.paper.capital import PAPER_INITIAL_IDR
from seer_engine.paper.compare import SESSIONS_PER_YEAR
from seer_engine.sim import costs
from seer_engine.sim.contributions import OWNER_MONTHLY
from seer_engine.sim.model import q

# --------------------------------------------------------------------------- what is swept

CENT = costs.CENT
_ONE = Decimal(1)
_ZERO = Decimal(0)
_EIGHT = Decimal("0.00000001")

#: The rank cadences ``sim.rules`` offers, slowest last. A chart model would trade at the first
#: two; the third is what the lab already pays for and is the control.
CADENCES: tuple[str, ...] = ("daily", "weekly", "monthly")

#: How often each cadence re-picks the book in a year. ``sim.rules.describe_rules`` defines each:
#: daily is every session, weekly the first session of each ISO week, monthly the first session of
#: each calendar month. 252 is ``paper.compare.SESSIONS_PER_YEAR``, the lab's own session year,
#: imported rather than restated so the two can never drift.
REPICKS_PER_YEAR: dict[str, int] = {"daily": SESSIONS_PER_YEAR, "weekly": 52, "monthly": 12}

#: The control: what every live roster book (``MONTHLY_HOLD_FRAC_GOTRADE``) already pays for.
CONTROL_CADENCE = "monthly"

#: What the paper roster holds, and what it keeps holding whatever this measures.
ROSTER_NAMES = 20

#: The book sizes the lab actually uses, bracketing the roster's 20 on both sides. This axis is
#: here because the fee FLOOR depends on slot size -- not because a name count is being chosen.
NAMES: tuple[int, ...] = (10, ROSTER_NAMES, 30)

#: The share of the book replaced at each re-pick: a quarter, a half, and the whole thing.
CHURNS: tuple[Decimal, ...] = (Decimal("0.25"), Decimal("0.50"), Decimal("1.00"))

#: The horizon, in years. Ten is the design's own §1 bar ("a 10-year backtest").
YEARS = 10

#: The rate the frozen production book started at, and the rate ``lab/name_count.py``'s docstring
#: measured its 1.035% / 0.614% figures at. Keeping it lets the two reports be reconciled.
USD_IDR = Decimal("17841")

#: The owner's opening capital. Imported from ``paper.capital`` rather than ``backtest.runner``
#: because the two hold the same number and ``paper.capital`` is stdlib-only, so this module stays
#: import-light and pure. ``tests/test_lab_turnover.py`` asserts the two still agree.
INITIAL_IDR = PAPER_INITIAL_IDR

#: The owner's real top-up: 5,000,000 IDR on the 25th of every month, indefinitely.
SCHEDULE = OWNER_MONTHLY

#: How many months of the funding ramp the floor table prints. Fourteen covers the whole of the
#: period in which the floor binds at any book size this module sweeps, with room to spare.
FLOOR_MONTHS = 14

MIN_NAMES, MAX_NAMES = 2, 60
MIN_YEARS, MAX_YEARS = 1, 50

#: A sanity bound on ``--growth``: this is a fee report, not a return forecast.
MAX_GROWTH = Decimal("1")


# --------------------------------------------------------------------------- validators


def check_cadences(cadences: str | Iterable[str] | None = None) -> tuple[str, ...]:
    """The swept cadences, in ``CADENCES`` order. Accepts ``"daily,weekly"`` or an iterable."""
    if cadences is None:
        return CADENCES
    if isinstance(cadences, str):
        parts = [p.strip().lower() for p in cadences.split(",") if p.strip()]
    else:
        parts = [str(c).strip().lower() for c in cadences]
    if not parts:
        raise store.LabError("--cadence is empty; give cadences like daily,weekly,monthly")
    for p in parts:
        if p not in REPICKS_PER_YEAR:
            raise store.LabError(
                f"unknown cadence {p!r}; sim.rules offers {', '.join(CADENCES)} and nothing else, "
                f"so those are the only horizons this prices"
            )
    return tuple(c for c in CADENCES if c in set(parts))


def check_names(ns: str | Iterable[int] | None = None) -> tuple[int, ...]:
    """The swept book sizes as a sorted, unique tuple. Accepts ``"10,20"`` or an iterable."""
    if ns is None:
        return NAMES
    if isinstance(ns, str):
        parts = [p.strip() for p in ns.split(",") if p.strip()]
        if not parts:
            raise store.LabError("--names is empty; give counts like 10,20,30")
        try:
            values = [int(p) for p in parts]
        except ValueError as e:
            raise store.LabError(f"--names must be whole numbers separated by commas, got {ns!r}") from e
    else:
        values = [int(n) for n in ns]
    out = tuple(sorted(set(values)))
    if not out:
        raise store.LabError("no book sizes to sweep")
    for n in out:
        if not MIN_NAMES <= n <= MAX_NAMES:
            raise store.LabError(
                f"a book size of {n} is outside {MIN_NAMES}..{MAX_NAMES}; this prices a book, "
                f"not a single stock or the whole index"
            )
    return out


def check_churns(churns: str | Iterable[object] | None = None) -> tuple[Decimal, ...]:
    """The swept turnover fractions as a sorted, unique tuple in (0, 1]."""
    if churns is None:
        return CHURNS
    if isinstance(churns, str):
        parts = [p.strip() for p in churns.split(",") if p.strip()]
        if not parts:
            raise store.LabError("--churn is empty; give fractions like 0.25,0.5,1.0")
    else:
        parts = [str(c).strip() for c in churns]
    try:
        values = [Decimal(p) for p in parts]
    except Exception as e:  # ArithmeticError and friends; Decimal is picky about junk
        raise store.LabError(f"--churn must be decimal fractions separated by commas, got {churns!r}") from e
    out = tuple(sorted(set(values)))
    if not out:
        raise store.LabError("no turnover fractions to sweep")
    for c in out:
        if not c.is_finite() or not (_ZERO < c <= _ONE):
            raise store.LabError(
                f"a turnover fraction of {c} is outside (0, 1]; 1.0 means the whole book is "
                f"replaced at every re-pick, and 0 means nothing is traded and there is no fee "
                f"to price"
            )
    return out


def check_years(years: object | None = None) -> int:
    """The horizon in whole years. ``None`` is :data:`YEARS`."""
    if years is None:
        return YEARS
    try:
        value = int(years)
    except (TypeError, ValueError) as e:
        raise store.LabError(f"--years must be a whole number of years, got {years!r}") from e
    if not MIN_YEARS <= value <= MAX_YEARS:
        raise store.LabError(f"--years must be {MIN_YEARS}..{MAX_YEARS}, got {value}")
    return value


def check_usd_idr(rate: object | None = None) -> Decimal:
    """The IDR/USD rate the owner's deposits are converted at. ``None`` is :data:`USD_IDR`."""
    if rate is None:
        return USD_IDR
    try:
        value = Decimal(str(rate))
    except Exception as e:
        raise store.LabError(f"--usd-idr must be a number of rupiah per dollar, got {rate!r}") from e
    if not value.is_finite() or value <= 0:
        raise store.LabError(f"--usd-idr must be > 0, got {value}")
    return value


def check_growth(growth: object | None = None) -> Decimal:
    """The annual rate the deposit path compounds at. ``None`` and ``0`` both mean no growth.

    Zero is the conservative default and the one the report is read at: a book that earns nothing
    stays small, its slots stay small, and the ``$0.10`` floor bites as hard as it ever will. The
    knob exists so the reader can check that the answer does not hinge on it. It does not.
    """
    if growth is None:
        return _ZERO
    try:
        value = Decimal(str(growth))
    except Exception as e:
        raise store.LabError(f"--growth must be an annual rate like 0.10, got {growth!r}") from e
    if not value.is_finite() or not (-_ONE < value <= MAX_GROWTH):
        raise store.LabError(
            f"--growth must be greater than -1 and at most {MAX_GROWTH}, got {value}; this is a "
            f"fee report, not a return forecast"
        )
    return value


# --------------------------------------------------------------------------- the money


def equity_usd(months: int, *, usd_idr: Decimal = USD_IDR, growth: Decimal = _ZERO) -> Decimal:
    """What the owner's book holds after ``months`` of his real funding plan, in dollars.

    The opening 10,000,000 IDR plus one 5,000,000 IDR deposit per elapsed month, converted at one
    rate -- the same single-rate convention ``backtest.runner`` uses, so the answer is about the
    schedule and not about the rupiah. ``growth`` compounds that deposit path at an annual rate;
    at the default of zero this is a pure deposit path, which is the conservative reading.
    """
    if isinstance(months, bool) or not isinstance(months, int):
        raise TypeError(f"months must be an int, got {type(months).__name__}")
    if months < 0:
        raise ValueError(f"months must be >= 0, got {months}")
    base = q((INITIAL_IDR + SCHEDULE.amount_idr * months) / usd_idr)
    if growth == _ZERO:
        return base
    return q(base * (_ONE + growth) ** (Decimal(months) / Decimal(12)))


def slot_usd(equity: Decimal, names: int) -> Decimal:
    """One slot of an equal-weight book of ``names`` holding ``equity`` dollars."""
    if names <= 0:
        raise ValueError(f"names must be > 0, got {names}")
    return q(equity / names)


def replaced_names(names: int, churn: Decimal) -> int:
    """How many names one re-pick replaces: ``names x churn``, half-up, at least one.

    At least one, because a model that re-picks and changes nothing is not re-picking. That floor
    matters: it is what makes the cheapest possible daily book -- one name of twenty swapped a
    session -- still cost 7% a year, which is the number that kills the idea even at its gentlest.
    """
    if churn <= _ZERO:
        return 0
    k = int((Decimal(names) * churn).quantize(_ONE, rounding=ROUND_HALF_UP))
    return max(1, min(int(names), k))


def floor_binds(amount: Decimal, *, regime: costs.FeeRegime | None = None) -> bool:
    """Does this order pay the ``$0.10`` trading-fee MINIMUM rather than the rate?

    This is the one line of ``FeeRegime.fees`` read back out -- the rate applied to the amount and
    compared with the minimum -- and nothing else here re-derives any fee arithmetic. The boundary
    under the current regime is a slot of $47.49 (the floor wins) against $47.50 (it does not):
    0.2% of $47.50 is exactly $0.095, which rounds half-up to $0.10 and ties the minimum.
    """
    r = costs.GOTRADE.current if regime is None else regime
    if r.trading_rate <= _ZERO:
        return False
    cents = max(Decimal(amount).quantize(CENT, rounding=ROUND_HALF_UP), CENT)
    return (cents * r.trading_rate).quantize(CENT, rounding=ROUND_HALF_UP) < r.trading_min


def round_trip(amount: Decimal) -> tuple[costs.FeeParts, costs.FeeParts]:
    """``(buy, sell)`` fees for replacing one slot of ``amount`` dollars, at the current regime.

    Two orders, not one: a re-pick that swaps a name sells the old one and buys the new one, and
    the sell pays an uncapped ``sell_extra_rate`` the buy does not. ``on=None`` means the current
    regime, which is what every backtest uses and so what every comparison in the lab is against.
    """
    return costs.fee_parts("buy", amount), costs.fee_parts("sell", amount)


# --------------------------------------------------------------------------- one priced cell


@dataclass(frozen=True)
class Point:
    """One (cadence, book size, turnover) cell: everything the grid and the CSV print."""

    cadence: str
    names: int
    churn: Decimal
    repicks_per_year: int
    replaced_per_repick: int
    orders: int
    floor_orders: int
    fees_usd: Decimal
    notional_usd: Decimal
    round_trip_rate: Decimal      # fees / slot notional: the 1.035%-style number
    breakeven_per_year: Decimal   # the headline: what it must add to be level with doing nothing
    breakeven_first_year: Decimal

    @property
    def floor_share(self) -> Decimal:
        """The share of orders that paid the floor rather than the rate."""
        if self.orders == 0:
            return _ZERO
        return (Decimal(self.floor_orders) / Decimal(self.orders)).quantize(_EIGHT)

    @property
    def orders_per_year(self) -> int:
        return 2 * self.replaced_per_repick * self.repicks_per_year


def price_one(
    cadence: str,
    names: int,
    churn: Decimal,
    *,
    years: int = YEARS,
    usd_idr: Decimal = USD_IDR,
    growth: Decimal = _ZERO,
) -> Point:
    """Price one book shape over ``years`` of the owner's funding. Writes nothing, reads nothing.

    The loop walks every re-pick EVENT rather than every month, because the fee depends on the
    cadence and the equity depends on the calendar, and only an event-by-event walk gets both
    right at once. At event ``k`` the elapsed months are ``k x 12 // repicks_per_year``.

    The break-even is the compounded one (plan P4-D7): each event costs ``f`` out of ``E``, so the
    book keeps ``(1 - f/E)``, and the annual return needed to be level with doing nothing is the
    product's reciprocal annualised. There is no extra assumption in it -- in particular no
    assumed return, which is the thing nobody knows yet.
    """
    if cadence not in REPICKS_PER_YEAR:
        raise store.LabError(f"unknown cadence {cadence!r}; expected one of {', '.join(CADENCES)}")
    repicks = REPICKS_PER_YEAR[cadence]
    replaced = replaced_names(names, churn)
    if replaced == 0:
        raise store.LabError(f"a turnover of {churn} replaces no names, so there is no fee to price")

    fees = _ZERO
    notional = _ZERO
    orders = 0
    floor_orders = 0
    survival = _ONE
    survival_year_one = _ONE
    for k in range(repicks * years):
        equity = equity_usd((k * 12) // repicks, usd_idr=usd_idr, growth=growth)
        slot = slot_usd(equity, names)
        buy, sell = round_trip(slot)
        event = (buy.total + sell.total) * replaced
        if event >= equity:
            raise store.LabError(
                f"a {cadence} re-pick of a {names}-name book at turnover {churn} costs "
                f"${event} out of ${equity} in one go, which is not a book but a bonfire; "
                f"this report cannot price it"
            )
        fees += event
        notional += slot * replaced
        orders += 2 * replaced
        if floor_binds(slot):
            floor_orders += 2 * replaced
        survival *= _ONE - event / equity
        if k < repicks:
            survival_year_one *= _ONE - event / equity

    breakeven = ((_ONE / survival) ** (_ONE / Decimal(years)) - _ONE).quantize(_EIGHT)
    breakeven_one = (_ONE / survival_year_one - _ONE).quantize(_EIGHT)
    return Point(
        cadence=cadence,
        names=int(names),
        churn=churn,
        repicks_per_year=repicks,
        replaced_per_repick=replaced,
        orders=orders,
        floor_orders=floor_orders,
        fees_usd=fees.quantize(CENT),
        notional_usd=notional.quantize(CENT),
        round_trip_rate=(fees / notional).quantize(_EIGHT),
        breakeven_per_year=breakeven,
        breakeven_first_year=breakeven_one,
    )


# --------------------------------------------------------------------------- the floor, explicitly


@dataclass(frozen=True)
class FloorRow:
    """One month of the owner's funding ramp at one book size: does the floor still win?"""

    month: int
    names: int
    equity_usd: Decimal
    slot_usd: Decimal
    buy_fee: Decimal
    sell_fee: Decimal
    round_trip_rate: Decimal
    floor: bool


def floor_table(
    names: Sequence[int],
    *,
    months: int = FLOOR_MONTHS,
    usd_idr: Decimal = USD_IDR,
    growth: Decimal = _ZERO,
) -> tuple[FloorRow, ...]:
    """The first ``months`` of the funding ramp, per book size: slot, both fees, and the floor.

    This is the part a single average would hide. The owner's book opens small enough that the
    ``$0.10`` minimum beats the 0.2% rate, and then it does not, and the month it stops depends on
    how many names the book holds. Printing the ramp is the only honest way to show a rate that
    changes by a factor of nearly two in three months.
    """
    out: list[FloorRow] = []
    for n in names:
        for m in range(int(months)):
            equity = equity_usd(m, usd_idr=usd_idr, growth=growth)
            slot = slot_usd(equity, n)
            buy, sell = round_trip(slot)
            out.append(FloorRow(
                month=m,
                names=int(n),
                equity_usd=equity,
                slot_usd=slot,
                buy_fee=buy.total,
                sell_fee=sell.total,
                round_trip_rate=((buy.total + sell.total) / slot).quantize(_EIGHT),
                floor=floor_binds(slot),
            ))
    return tuple(out)


# --------------------------------------------------------------------------- the whole grid


@dataclass(frozen=True)
class Sweep:
    """Every priced cell, plus the floor ramp, plus enough provenance to reproduce it."""

    cadences: tuple[str, ...]
    names: tuple[int, ...]
    churns: tuple[Decimal, ...]
    years: int
    usd_idr: Decimal
    growth: Decimal
    regime_since: date
    points: tuple[Point, ...]
    floor_rows: tuple[FloorRow, ...]

    def of(self, cadence: str) -> tuple[Point, ...]:
        """This cadence's cells, by book size then turnover."""
        return tuple(sorted(
            (p for p in self.points if p.cadence == cadence),
            key=lambda p: (p.names, p.churn),
        ))

    def at(self, cadence: str, names: int, churn: Decimal) -> Point | None:
        for p in self.points:
            if p.cadence == cadence and p.names == names and p.churn == churn:
                return p
        return None

    def control(self) -> Point | None:
        """The lab's own cadence on the roster's own book, at the gentlest turnover swept.

        The baseline every other cell is read against: a cost the lab has already accepted,
        rather than a number picked to make the comparison look good.
        """
        cells = [p for p in self.of(CONTROL_CADENCE) if p.names == ROSTER_NAMES]
        return min(cells, key=lambda p: p.churn) if cells else None

    def cheapest(self, cadence: str) -> Point | None:
        """The least a book can be traded at this cadence: the lowest break-even cell."""
        cells = self.of(cadence)
        return min(cells, key=lambda p: p.breakeven_per_year) if cells else None

    def dearest(self, cadence: str) -> Point | None:
        cells = self.of(cadence)
        return max(cells, key=lambda p: p.breakeven_per_year) if cells else None

    def floor_ends(self, names: int) -> int | None:
        """The first month at which the floor no longer binds for this book size.

        ``0`` means it never binds at all; ``None`` means it still binds at the end of the ramp
        the table covers, which would mean :data:`FLOOR_MONTHS` is too short.
        """
        rows = [r for r in self.floor_rows if r.names == names]
        for r in sorted(rows, key=lambda r: r.month):
            if not r.floor:
                return r.month
        return None


def measure(
    *,
    cadences: Sequence[str] | None = None,
    names: Sequence[int] | None = None,
    churns: Sequence[Decimal] | None = None,
    years: int = YEARS,
    usd_idr: Decimal = USD_IDR,
    growth: Decimal = _ZERO,
    floor_months: int = FLOOR_MONTHS,
) -> Sweep:
    """Price the whole grid. Opens nothing, writes nothing, anywhere."""
    cads = check_cadences(cadences)
    ns = check_names(names)
    chs = check_churns(churns)
    yrs = check_years(years)
    rate = check_usd_idr(usd_idr)
    g = check_growth(growth)
    points = tuple(
        price_one(c, n, ch, years=yrs, usd_idr=rate, growth=g)
        for c in cads for n in ns for ch in chs
    )
    return Sweep(
        cadences=cads,
        names=ns,
        churns=chs,
        years=yrs,
        usd_idr=rate,
        growth=g,
        regime_since=costs.GOTRADE.current.since,
        points=points,
        floor_rows=floor_table(ns, months=floor_months, usd_idr=rate, growth=g),
    )


# --------------------------------------------------------------------------- the report


def _pct(x: Decimal, places: int = 2) -> str:
    return f"{x * 100:.{places}f}%"


def _usd(x: Decimal) -> str:
    return f"${x:,.0f}"


_HEAD: tuple[str, ...] = (
    "cadence", "names", "turnover", "re-picks/yr", "names/re-pick", "orders",
    "fees", "round trip", "floor orders", "break-even/yr", "break-even yr 1",
)

_FLOOR_HEAD: tuple[str, ...] = (
    "month", "names", "equity", "slot", "buy fee", "sell fee", "round trip", "pays the floor",
)


def _cells(p: Point) -> tuple[str, ...]:
    return (
        p.cadence,
        str(p.names),
        _pct(p.churn, 0),
        str(p.repicks_per_year),
        str(p.replaced_per_repick),
        f"{p.orders:,}",
        _usd(p.fees_usd),
        _pct(p.round_trip_rate, 3),
        _pct(p.floor_share, 1),
        _pct(p.breakeven_per_year),
        _pct(p.breakeven_first_year),
    )


def _floor_cells(r: FloorRow) -> tuple[str, ...]:
    return (
        str(r.month),
        str(r.names),
        f"${r.equity_usd:,.2f}",
        f"${r.slot_usd:,.2f}",
        f"${r.buy_fee}",
        f"${r.sell_fee}",
        _pct(r.round_trip_rate, 3),
        "yes" if r.floor else "no",
    )


def _table(head: Sequence[str], rows: Sequence[Sequence[str]]) -> list[str]:
    body = [tuple(head), *(tuple(r) for r in rows)]
    widths = [max(len(r[i]) for r in body) for i in range(len(head))]
    out: list[str] = []
    for k, row in enumerate(body):
        out.append("    " + "  ".join(row[i].rjust(widths[i]) for i in range(len(head))))
        if k == 0:
            out.append("    " + "  ".join("-" * w for w in widths))
    return out


def _findings(sweep: Sweep) -> list[str]:
    """The mechanical readings. The prose a human reads is the write-up in docs/backtests/."""
    out = ["findings (mechanical; the write-up is docs/backtests/2026-10-13-chart-model-turnover.md)"]
    control = sweep.control()
    if control is not None:
        out.append(
            f"  the control -- the {CONTROL_CADENCE} cadence the lab already pays for, "
            f"{control.names} names, {_pct(control.churn, 0)} of the book re-picked -- costs "
            f"{_pct(control.breakeven_per_year)} a year"
        )
    for cadence in sweep.cadences:
        if cadence == CONTROL_CADENCE:
            continue
        cheap, dear = sweep.cheapest(cadence), sweep.dearest(cadence)
        if cheap is None or dear is None:
            continue
        out.append(
            f"  {cadence}: the gentlest cell swept ({cheap.names} names, "
            f"{_pct(cheap.churn, 0)}, {cheap.replaced_per_repick} name(s) a re-pick) must add "
            f"{_pct(cheap.breakeven_per_year)} a year just to be level with doing nothing; the "
            f"heaviest ({dear.names} names, {_pct(dear.churn, 0)}) must add "
            f"{_pct(dear.breakeven_per_year)}"
        )
        if control is not None and cheap.breakeven_per_year > control.breakeven_per_year:
            out.append(
                f"    even at its gentlest that is "
                f"{(cheap.breakeven_per_year / control.breakeven_per_year):.1f}x the control"
            )
    for n in sweep.names:
        ends = sweep.floor_ends(n)
        if ends == 0:
            out.append(f"  a {n}-name book never pays the $0.10 floor: its opening slot is already above $47.50")
        elif ends is None:
            out.append(f"  a {n}-name book still pays the floor at the end of the ramp printed above")
        else:
            out.append(f"  a {n}-name book pays the $0.10 floor through month {ends - 1} and not after")
    out.append(
        "  the floor is therefore a transient of the first months; once it is gone a round trip "
        "settles near 0.503% of the slot, and it is THAT rate, multiplied by the cadence, that "
        "decides a short-horizon model"
    )
    return out


def format_report(sweep: Sweep) -> str:
    """The terminal report. Ids and labels are fine here; the owner reads the docs page."""
    out = [
        f"lab turnover -- what Gotrade charges a book for trading often, over {sweep.years} years "
        f"of the owner's real funding plan",
        f"funding: {INITIAL_IDR:,.0f} IDR at the start, +{SCHEDULE.amount_idr:,.0f} IDR on the "
        f"{SCHEDULE.day_of_month}th of every month, at {sweep.usd_idr:,.0f} IDR/USD"
        + (f", compounded at {_pct(sweep.growth)} a year" if sweep.growth else ", no growth assumed"),
        f"fees: sim.costs.GOTRADE's current regime (since {sweep.regime_since}); every order "
        f"priced through sim.costs.fee_parts, a re-pick being one sell plus one buy",
        "report only: no trial row, no moments, no journal entry, no status change; the lab's N "
        "and the test-window looks do not move. A free sweep over this grid is the search the "
        "luck gate exists to charge for, so it informs a decision and is never one: acting on it "
        "means a new method that pre-registers the cadence and pays its trials.",
        "",
        "  the grid",
    ]
    out += _table(_HEAD, [_cells(p) for p in sweep.points])
    out += ["", "  the $0.10 floor, month by month, as the owner's deposits arrive"]
    out += _table(_FLOOR_HEAD, [_floor_cells(r) for r in sweep.floor_rows])
    out += [""] + _findings(sweep)
    return "\n".join(out)


# --------------------------------------------------------------------------- the grid as CSV


CSV_HEAD: tuple[str, ...] = (
    "kind", "cadence", "names", "churn", "month", "repicks_per_year", "replaced_per_repick",
    "orders", "floor_orders", "floor_share", "equity_usd", "slot_usd", "buy_fee", "sell_fee",
    "fees_usd", "notional_usd", "round_trip_rate", "breakeven_per_year", "breakeven_first_year",
    "pays_the_floor",
)


def csv_rows(sweep: Sweep) -> list[list[str]]:
    """The grid and the floor ramp as text rows, header first; every number at full precision."""
    rows: list[list[str]] = [list(CSV_HEAD)]
    for p in sweep.points:
        rows.append([
            "cell", p.cadence, str(p.names), str(p.churn), "",
            str(p.repicks_per_year), str(p.replaced_per_repick), str(p.orders),
            str(p.floor_orders), str(p.floor_share), "", "", "", "",
            str(p.fees_usd), str(p.notional_usd), str(p.round_trip_rate),
            str(p.breakeven_per_year), str(p.breakeven_first_year), "",
        ])
    for r in sweep.floor_rows:
        rows.append([
            "floor", "", str(r.names), "", str(r.month),
            "", "", "", "", "", str(r.equity_usd), str(r.slot_usd), str(r.buy_fee),
            str(r.sell_fee), "", "", str(r.round_trip_rate), "", "",
            "yes" if r.floor else "no",
        ])
    return rows


def write_csv(sweep: Sweep, path: Path) -> Path:
    """Write the grid to ``path`` (parents created). Returns the path written."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(csv_rows(sweep))
    return path

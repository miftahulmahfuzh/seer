"""The five-dollar price floor, and which close it is compared against.

Every stock screen in this lab asks whether a member's close is at least five dollars -- the
conventional penny-stock line, ``FactorParams.min_price``. The close it reads is the research
store's, and the store's closes are back-adjusted for every split the vendor applied since. So
the floor has never asked "did this share trade above five dollars"; it has asked "did this
share trade above five dollars *after* dividing by every split between then and now". A company
that split often reads far cheaper in the old years than it ever traded, and the companies that
split often are the companies that went up: the floor removes exactly the names a momentum book
is built to hold. M0383 measured the hole on the dev store over the 238 month-ends from
1996-01-31 to 2015-10-16 -- 1293 of 62923 member-months, 2.05%, across 40 companies, led by
Nvidia at 168 month-ends, Apple at 149, KLA at 137 and CSX at 132 -- and M0387 priced repairing
it.

**Why this module exists.** The arithmetic that recovers the printed close was written, verified
and committed inside two lab method files (``m0383_nominal_price_level_tilt.printed_close`` and
``m0387_printed_price_floor_repair.passes_floor``). Those files are pre-registrations: once the
lab has run them they are frozen to a recorded ``source_sha`` and may never be edited. The lab's
one verified printed-price helper therefore lived somewhere no supported code may change, and a
screen that wanted it had to import out of a frozen pre-registration. This module is that
helper's real home. It reproduces the frozen arithmetic exactly -- ``test_price_floor.py`` pins
the agreement, so the frozen copies cannot drift away from this one -- and adds only what a
shared, supported screen needs: a basis check, a vector path, and a refusal.

**The three rungs**, as M0387 pre-registered them. ``"adjusted"`` compares the stored,
back-adjusted close, which is what every screen in this lab does today and stays the default
everywhere. ``"printed"`` compares the close as it printed -- the stored close times every split
applied after that day -- which is the repair. ``"none"`` asks nothing, the far rung that bounds
what the floor costs in total. They are three rungs of one dial rather than three ideas: a
forward split makes ``raw_factor`` at least 1, so a printed close is at or above the adjusted
one and the pools nest, and only a reverse split can flip that.

**The caveat this module refuses to keep silent.** The printed close is
``close * Market.shares.raw_factor(symbol, d)``, and ``raw_factor`` answers 1.0 for every symbol
when the market carries no splits. The paper night builds its ``Market`` from history,
membership, fx and fundamentals and *no shares* (``paper/store.py``), so ``Market.shares`` is
``EMPTY_SHARES`` there: a printed-basis screen would degrade back to the adjusted basis with no
error and no warning, and the repair would be live, measured, and not actually running
(insights 778, 779). Supplying share counts to the paper night is a table, a migration, a loader
and a nightly job, and it is not built. So the silence is turned into a refusal here instead:
:func:`check_market` raises when a caller asks for the printed basis on a market that cannot
answer, and both shared screens call it once before their loop rather than once per symbol, so
the error names the decision date rather than whichever ticker happened to be first. An
allocator built on this must *also* declare ``market_fields = ("shares",)``, which is the lab's
existing mechanism for the same problem seen from the store side -- it makes ``lab run`` refuse
the allocator on a research store with no ``splits.csv`` rather than quietly scoring the wrong
basis. Neither check can be inferred from the other, so both are named here.

**What the basis never decides.** Which close a target is *priced* at. The basis moves the pool
and nothing else: ``FactorRow.close`` and ``FundamentalRow.close`` stay the store's close, which
is the number the book engine trades and the number every recorded trial was scored on. A
printed number in a row's ``close`` would price every order at a price that has not existed
since the split.

Pure: reads only bars and splits dated on or before ``data_date``. ``raw_factor`` is a property
of the store's own adjustment of the past, not a forecast -- it says what a newspaper printed
that morning, not what the stock did afterwards.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import date
from typing import Any

import numpy as np

from seer_engine.strategies.base import History

MIN_PRICE = 5.0
"""The conventional penny-stock line, and ``FactorParams.min_price``'s own default.

Not a dial this module introduces: 5.0 is the number the shared screens already default to and
the number ``m0387.MIN_PRICE`` holds. What this module changes is only which close it is
compared against."""

BASES: tuple[str, ...] = ("adjusted", "printed", "none")
"""The three rungs of the floor dial, in M0387's own order and spelling."""

ADJUSTED, PRINTED, NONE = BASES


class PrintedBasisUnavailable(ValueError):
    """The printed basis was asked for on a market that cannot supply splits.

    The failure this exists to prevent is not a crash, it is a silence: ``raw_factor`` answers
    1.0 for every symbol on a market with no splits, so the printed basis would collapse into
    the adjusted one and nothing would say so.
    """


def check_basis(basis: object) -> str:
    """``basis`` as one of :data:`BASES`, or an error naming what was asked for."""
    if not isinstance(basis, str):
        raise TypeError(f"price_basis must be a str, got {type(basis).__name__}")
    if basis not in BASES:
        raise ValueError(f"price_basis must be one of {BASES}, got {basis!r}")
    return basis


def market_can_print(market: Any) -> bool:
    """Can ``market`` answer a printed close at all -- does it carry any splits?

    Duck-typed on purpose: the history-only allocator path passes None, the lab passes a
    ``Market``, and a test passes anything with a ``shares``. Nothing here imports
    ``backtest.market``, which keeps ``strategies`` free of a dependency it does not otherwise
    have.
    """
    if market is None:
        return False
    shares = getattr(market, "shares", None)
    if shares is None:
        return False
    has = getattr(shares, "has_splits", None)
    return bool(has()) if callable(has) else False


def check_market(market: Any, basis: str) -> str:
    """``basis``, refusing ``"printed"`` on a market that would silently answer the adjusted one.

    Called once per screen call, before the loop, so the cost is one check per decision date and
    the error names the day it happened on rather than the first symbol it reached.
    """
    basis = check_basis(basis)
    if basis == PRINTED and not market_can_print(market):
        raise PrintedBasisUnavailable(
            "the printed price basis needs a market carrying splits, and this one has none "
            "(Market.shares is EMPTY_SHARES, so raw_factor answers 1.0 for every symbol and the "
            "printed floor would silently become the adjusted floor). Load a research store with "
            'a splits.csv, and declare market_fields = ("shares",) on the allocator'
        )
    return basis


def raw_factor(market: Any, symbol: str, data_date: date) -> float:
    """What ``symbol``'s stored close on ``data_date`` is multiplied by to give the printed price.

    ``ShareCounts.raw_factor``: the product of every split the vendor applied after that day,
    strictly after -- the ex-date's own bar is already adjusted. 1.0 when the market carries no
    splits for the symbol.
    """
    return float(market.shares.raw_factor(symbol, data_date))


def printed_close(h: History, market: Any, symbol: str, data_date: date) -> float | None:
    """The close as it printed on ``data_date``: the stored, split-adjusted close multiplied by
    every split the vendor applied after that day (``ShareCounts.raw_factor``).

    None when there is no bar dated ``data_date`` or the read is not finite and positive. Reads
    nothing dated after ``data_date``. This is ``m0383.printed_close``, verified against five
    known real-world closes before it was committed and reproduced here; ``test_price_floor.py``
    pins the two against each other so the frozen copy cannot drift away from this one.
    """
    i = h.index_of(data_date)
    if i is None:
        return None
    adj = float(h.close[i])
    if not (adj > 0.0 and adj == adj and adj != float("inf")):
        return None
    return adj * raw_factor(market, symbol, data_date)


def floor_value(adjusted: float, factor: float, basis: str) -> float:
    """The number the floor is compared against, from one adjusted close and one split factor.

    ``"adjusted"`` -> the close itself; ``"printed"`` -> close x factor; ``"none"`` -> infinity,
    which clears any finite floor and so is "ask nothing" without a second code path. The one
    piece of arithmetic both the scalar and the vector path go through.
    """
    if basis == ADJUSTED:
        return adjusted
    if basis == NONE:
        return math.inf
    return adjusted * factor


def passes_floor(
    h: History, market: Any, symbol: str, data_date: date, basis: str, min_price: float = MIN_PRICE
) -> bool:
    """Does ``symbol`` clear the price floor on ``data_date`` under ``basis``?

    ``"none"`` asks nothing. ``"adjusted"`` compares the store's back-adjusted close, which is
    what every screen in this lab does today. ``"printed"`` compares the close as it printed,
    which is the repair. False when the symbol has no bar dated ``data_date`` or the close is
    not finite. This is ``m0387.passes_floor`` with the floor made an argument instead of a
    module constant, defaulted to the same number; ``test_price_floor.py`` pins the two against
    each other across the three bases and across the floor itself.
    """
    if basis == NONE:
        return True
    i = h.index_of(data_date)
    if i is None:
        return False
    adj = float(h.close[i])
    if not math.isfinite(adj):
        return False
    if basis == ADJUSTED:
        return adj >= min_price
    p = printed_close(h, market, symbol, data_date)
    return p is not None and p >= min_price


def floor_closes(
    adjusted: np.ndarray, market: Any, symbols: Sequence[str], data_date: date, basis: str
) -> np.ndarray:
    """The floor price for each of ``symbols``, aligned with ``adjusted`` (the vector path).

    ``adjusted`` is one stored close per symbol, in the same order. Returns ``adjusted`` itself
    under ``"adjusted"`` -- the same object, no copy and no arithmetic, so the default path is
    exactly what it was before this argument existed -- an all-infinity array under ``"none"``,
    and close x raw_factor under ``"printed"``. ``raw_factor`` is always finite and positive
    (``ShareCounts`` validates every ratio on construction), so the printed array is finite
    wherever ``adjusted`` is and ``_eligible_mask``'s existing ``np.isfinite(close)`` term still
    carries the whole finiteness check.
    """
    if basis == ADJUSTED:
        return adjusted
    if basis == NONE:
        return np.full(adjusted.shape, np.inf, dtype=np.float64)
    factors = np.array([raw_factor(market, s, data_date) for s in symbols], dtype=np.float64)
    return adjusted * factors

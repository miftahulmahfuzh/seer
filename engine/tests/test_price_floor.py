"""The five-dollar floor's three bases (``strategies/price_floor.py``, R1).

The printed close, pinned against the five real-world closes M0383 checked by hand before it was
committed; the agreement between this module and the two frozen lab copies it was lifted from;
the refusal that stops the printed basis collapsing silently on a market with no splits; and the
proof that both shared screens behave exactly as they did when nobody asks for a basis.

**No research store is read.** The splits are a fixture -- a ``ShareCounts`` built from four real
split calendars -- and each stored close is the printed close divided by its own split factor,
which is exactly what a vendor's back-adjustment produces. So the suite does not depend on
``engine/.research`` being present, and the five closes are pinned by the store's own arithmetic
rather than by a file that may or may not be on this machine.
"""

from __future__ import annotations

import importlib
import inspect
from dataclasses import dataclass
from datetime import date

import numpy as np
import pytest
from stratkit import hist, session_days

from seer_engine.backtest.market import EMPTY_SHARES, ShareCounts
from seer_engine.lab.methods.m0383_nominal_price_level_tilt import (
    printed_close as m0383_printed_close,
)
from seer_engine.lab.methods.m0387_printed_price_floor_repair import (
    MIN_PRICE as M0387_MIN_PRICE,
)
from seer_engine.lab.methods.m0387_printed_price_floor_repair import (
    passes_floor as m0387_passes_floor,
)
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import FactorParams, _eligible_mask, factor_rows
from seer_engine.strategies.f_fundamental import FundamentalParams, fundamental_rows
from seer_engine.strategies.price_floor import (
    ADJUSTED,
    BASES,
    MIN_PRICE,
    NONE,
    PRINTED,
    PrintedBasisUnavailable,
    check_basis,
    check_market,
    floor_closes,
    floor_value,
    market_can_print,
    passes_floor,
    printed_close,
    raw_factor,
)


class FakeMarket:
    """Everything ``price_floor`` reads of a ``Market``: its ``shares``, and nothing else."""

    def __init__(self, shares: ShareCounts) -> None:
        self.shares = shares


# ``ShareCounts`` takes ``{symbol: ((ex_date, ratio), ...), after_window_factor)}`` and
# ``raw_factor(s, d)`` is the after-window factor times every in-window split dated strictly
# after ``d``. These four calendars are real: Apple's 2:1 in 2005 and 7:1 in 2014 with its 2020
# 4:1 outside a dev-length window; Alphabet's and Amazon's 2022 20:1s, both outside it; and
# Coca-Cola's 2012 2:1 inside it.
SPLITS: dict[str, tuple[tuple[tuple[date, float], ...], float]] = {
    "AAPL": (((date(2005, 2, 28), 2.0), (date(2014, 6, 9), 7.0)), 4.0),
    "GOOGL": ((), 20.0),
    "AMZN": (((date(1999, 9, 2), 2.0),), 20.0),
    "KO": (((date(2012, 8, 13), 2.0),), 1.0),
}

# (symbol, day, the close the store holds, the close that printed). The right-hand numbers are
# the five real-world closes M0383's docstring names; each stored close is that number divided
# by its own ``raw_factor``, which is what a back-adjustment produces.
REAL_CLOSES: tuple[tuple[str, date, float, float], ...] = (
    ("AAPL", date(2014, 6, 6), 23.056071428571432, 645.57),  # the Friday before the 7:1
    ("AAPL", date(2014, 6, 10), 23.5625, 94.25),  # the Tuesday after it
    ("GOOGL", date(2015, 10, 15), 34.650999999999996, 693.02),
    ("AMZN", date(2015, 10, 15), 28.122000000000003, 562.44),
    ("KO", date(2000, 1, 14), 30.53, 61.06),
)


@pytest.fixture(scope="module")
def market() -> FakeMarket:
    return FakeMarket(ShareCounts({}, SPLITS))


@pytest.fixture(scope="module")
def blind() -> FakeMarket:
    """A market built the way the paper night builds one: no shares, so no splits."""
    return FakeMarket(EMPTY_SHARES)


def one_bar(symbol: str, day: date, close: float) -> History:
    """A one-bar history, which is all the scalar helpers read."""
    c = np.array([close], dtype=np.float64)
    return History(
        symbol,
        np.array([day], dtype="datetime64[D]"),
        c.copy(),
        c.copy(),
        c.copy(),
        c.copy(),
        np.array([1_000_000.0], dtype=np.float64),
    )


# --------------------------------------------------------------------------- the printed close


@pytest.mark.parametrize(("symbol", "day", "stored", "printed"), REAL_CLOSES)
def test_the_printed_close_is_the_close_that_printed(market, symbol, day, stored, printed):
    """The five real-world closes M0383 verified by hand before it was committed, pinned.

    AAPL across its own 7:1 is the load-bearing pair: $645.57 the Friday before and $94.25 the
    Tuesday after, from two stored closes that differ by 2%. A repair that got the direction or
    the ex-date boundary wrong would pass one and fail the other.
    """
    h = one_bar(symbol, day, stored)
    assert printed_close(h, market, symbol, day) == printed


def test_the_boundary_is_the_split_day_itself(market):
    """``raw_factor`` counts splits dated strictly after ``d``: the ex-date's bar is adjusted."""
    assert raw_factor(market, "AAPL", date(2014, 6, 6)) == 28.0  # the 7:1 x the 4:1 after
    assert raw_factor(market, "AAPL", date(2014, 6, 9)) == 4.0  # the ex-date is not after itself
    assert raw_factor(market, "AAPL", date(2014, 6, 10)) == 4.0


def test_no_bar_and_a_bad_close_answer_none(market):
    h = one_bar("KO", date(2000, 1, 14), 30.53)
    assert printed_close(h, market, "KO", date(2000, 1, 13)) is None
    nan = one_bar("KO", date(2000, 1, 14), float("nan"))
    assert printed_close(nan, market, "KO", date(2000, 1, 14)) is None
    zero = one_bar("KO", date(2000, 1, 14), 0.0)
    assert printed_close(zero, market, "KO", date(2000, 1, 14)) is None


# ------------------------------------------------------- agreement with the two frozen copies


@pytest.mark.parametrize(("symbol", "day", "stored", "printed"), REAL_CLOSES)
def test_this_module_agrees_with_m0383(market, symbol, day, stored, printed):
    """``m0383.printed_close`` is frozen to a recorded ``source_sha`` and may never be edited.

    This module is where that arithmetic is supported from now on, so the two must not drift. If
    this ever fails, the supported copy moved -- the frozen one cannot.
    """
    h = one_bar(symbol, day, stored)
    assert printed_close(h, market, symbol, day) == m0383_printed_close(h, market, symbol, day)


@pytest.mark.parametrize("basis", BASES)
@pytest.mark.parametrize(("symbol", "day", "stored", "printed"), REAL_CLOSES)
def test_this_module_agrees_with_m0387(market, basis, symbol, day, stored, printed):
    """The same freeze and the same reason, for the three-rung dial.

    ``m0387.passes_floor`` compares its own module constant; this module takes the floor as an
    argument and defaults it to the same number, so the two answer identically at the default.
    """
    assert MIN_PRICE == M0387_MIN_PRICE
    h = one_bar(symbol, day, stored)
    assert passes_floor(h, market, symbol, day, basis) == m0387_passes_floor(
        h, market, symbol, day, basis
    )


@pytest.mark.parametrize("stored", [4.0, 4.999, 5.0, 5.001, 50.0, float("nan")])
def test_agreement_holds_across_the_floor_itself(market, stored):
    """The agreement that matters is at the boundary, not on the easy numbers."""
    day, symbol = date(2000, 1, 14), "KO"
    h = one_bar(symbol, day, stored)
    for basis in BASES:
        assert passes_floor(h, market, symbol, day, basis) == m0387_passes_floor(
            h, market, symbol, day, basis
        )


# --------------------------------------------------------------- the silence, made into a refusal


def test_a_market_with_no_splits_cannot_print(blind, market):
    assert market_can_print(market) is True
    assert market_can_print(blind) is False
    assert market_can_print(None) is False


def test_the_frozen_helper_collapses_silently_and_this_one_refuses(blind):
    """The standing caveat, pinned as a test so it cannot be forgotten.

    On the paper night ``Market.shares`` is ``EMPTY_SHARES``, ``raw_factor`` answers 1.0 for
    every symbol, and the printed basis becomes the adjusted basis with no error (insights 778,
    779). The first assertion is that silence, demonstrated. Every entry point in the supported
    module refuses it instead.
    """
    day, stored = date(2014, 6, 6), 23.056071428571432
    h = one_bar("AAPL", day, stored)
    assert m0383_printed_close(h, blind, "AAPL", day) == stored  # silent, and wrong by 28x
    with pytest.raises(PrintedBasisUnavailable):
        check_market(blind, PRINTED)
    with pytest.raises(PrintedBasisUnavailable):
        check_market(None, PRINTED)
    assert check_market(blind, ADJUSTED) == ADJUSTED  # the default never needs a market
    assert check_market(None, NONE) == NONE


def test_a_bad_basis_is_named_not_guessed():
    for bad in ("Printed", "raw", "", "adjusted "):
        with pytest.raises(ValueError, match="price_basis"):
            check_basis(bad)
    with pytest.raises(TypeError):
        check_basis(None)


def test_floor_value_is_the_one_piece_of_arithmetic():
    assert floor_value(23.0, 28.0, ADJUSTED) == 23.0
    assert floor_value(23.0, 28.0, PRINTED) == 23.0 * 28.0
    assert floor_value(23.0, 28.0, NONE) == float("inf")


def test_the_vector_path_matches_the_scalar_one(market):
    day = date(2014, 6, 6)
    symbols = ["AAPL", "KO"]
    adjusted = np.array([23.056071428571432, 30.53], dtype=np.float64)
    assert floor_closes(adjusted, market, symbols, day, ADJUSTED) is adjusted
    assert list(floor_closes(adjusted, market, symbols, day, PRINTED)) == [645.57, 30.53]
    assert list(floor_closes(adjusted, market, symbols, day, NONE)) == [float("inf")] * 2


# ------------------------------------------------------------------- f_factor: the shared screen

# lookback 20 (the dollar-volume window): mom = c[-2]/c[-6] - 1, vol over 3 returns, no trend.
SCREEN = FactorParams(
    "momentum", top=5, mom_n=5, mom_skip=1, vol_n=3, trend=None, min_dollar_volume=0.0
)
BARS = 25


def wiggle(first: float) -> list[float]:
    """25 closes drifting up with an alternating wiggle, so volatility > 0 and momentum finite."""
    return [first * 1.001**t * (1.002 if t % 2 else 0.998) for t in range(BARS)]


@pytest.fixture(scope="module")
def days() -> list[date]:
    """25 sessions ending 2014-06-06 -- the Friday before Apple's 7:1, so the fixture's AAPL
    reads a ``raw_factor`` of 28 on its last bar, exactly as the real one does."""
    return session_days(BARS, date(2014, 5, 2))


@pytest.fixture(scope="module")
def screen_history(days) -> dict[str, History]:
    """AAPL reads $0.92 adjusted and $25.76 printed on the last bar; KO reads $61.33 either way.

    AAPL is the shape of the hole: a company whose stored close is under five dollars only
    because of splits the vendor applied years later.
    """
    return {
        "AAPL": hist("AAPL", wiggle(0.9), days=days, spread=0.01),
        "KO": hist("KO", wiggle(60.0), days=days, spread=0.01),
    }


def test_the_adjusted_basis_is_the_default_and_the_default_changed_nothing(
    screen_history, days, market
):
    """The whole point of the keyword argument: 119 method files call this function directly and
    not one of them passes a basis, so not one of them may see a different pool."""
    d = days[-1]
    members = frozenset({"AAPL", "KO"})
    plain = factor_rows(screen_history, members, d, SCREEN)
    explicit = factor_rows(screen_history, members, d, SCREEN, price_basis=ADJUSTED)
    with_market = factor_rows(
        screen_history, members, d, SCREEN, price_basis=ADJUSTED, market=market
    )
    assert plain == explicit == with_market
    assert [r.symbol for r in plain] == ["KO"]  # AAPL's stored close is under $5


def test_the_printed_basis_keeps_the_company_the_adjusted_floor_removed(
    screen_history, days, market
):
    d = days[-1]
    members = frozenset({"AAPL", "KO"})
    rows = factor_rows(screen_history, members, d, SCREEN, price_basis=PRINTED, market=market)
    assert [r.symbol for r in rows] == ["AAPL", "KO"]


def test_the_row_price_is_always_the_stored_close(screen_history, days, market):
    """The basis decides who is eligible. It never decides what a target is priced at: the book
    trades the store's close, and a printed number in ``FactorRow.close`` would price every
    order at a price that has not existed since the split."""
    d = days[-1]
    members = frozenset({"AAPL", "KO"})
    rows = {
        r.symbol: r
        for r in factor_rows(screen_history, members, d, SCREEN, price_basis=PRINTED, market=market)
    }
    assert rows["AAPL"].close == float(screen_history["AAPL"].close[-1])
    assert rows["AAPL"].close < MIN_PRICE


def test_the_none_basis_asks_nothing(screen_history, days):
    d = days[-1]
    members = frozenset({"AAPL", "KO"})
    rows = factor_rows(screen_history, members, d, SCREEN, price_basis=NONE)
    assert [r.symbol for r in rows] == ["AAPL", "KO"]


def test_factor_rows_refuses_a_printed_basis_without_splits(screen_history, days, blind):
    d = days[-1]
    members = frozenset({"AAPL", "KO"})
    with pytest.raises(PrintedBasisUnavailable):
        factor_rows(screen_history, members, d, SCREEN, price_basis=PRINTED, market=blind)
    with pytest.raises(PrintedBasisUnavailable):
        factor_rows(screen_history, members, d, SCREEN, price_basis=PRINTED)


def test_the_mask_default_is_the_close_itself():
    close = np.array([4.0, 6.0], dtype=np.float64)
    ones = np.array([1.0, 1.0], dtype=np.float64)
    params = FactorParams("momentum", min_dollar_volume=0.0)
    implicit = _eligible_mask(close, ones, ones, ones, params)
    explicit = _eligible_mask(close, ones, ones, ones, params, floor_close=close)
    assert list(implicit) == list(explicit) == [False, True]
    lifted = _eligible_mask(
        close, ones, ones, ones, params, floor_close=np.array([40.0, 60.0], dtype=np.float64)
    )
    assert list(lifted) == [True, True]


# ------------------------------------------------------------- f_fundamental: the same, inline


@dataclass(frozen=True, slots=True)
class FakeSnapshot:
    """The seven ``Snapshot`` members the allocator reads."""

    filed: date
    equity: float
    assets: float
    shares_outstanding: float
    net_income: float
    gross_profit: float
    sue: float


class FakePanel:
    """The one method ``f_fundamental.Panel`` needs, over a constant set of facts."""

    def __init__(self, filed: date) -> None:
        self.filed = filed

    def as_of(self, symbol: str, data_date: date) -> FakeSnapshot | None:
        if data_date < self.filed:
            return None
        return FakeSnapshot(self.filed, 1.0e9, 2.0e9, 1.0e8, 1.0e8, 5.0e8, 0.5)


FND = FundamentalParams("value", top=5, min_dollar_volume=0.0, max_stale_days=4000)


@pytest.fixture(scope="module")
def panel(days) -> FakePanel:
    return FakePanel(days[0])


def test_the_fundamental_screen_default_is_unchanged(screen_history, panel, days, market):
    d = days[-1]
    members = frozenset({"AAPL", "KO"})
    plain = fundamental_rows(screen_history, panel, members, d, FND)
    explicit = fundamental_rows(
        screen_history, panel, members, d, FND, price_basis=ADJUSTED, market=market
    )
    assert plain == explicit
    assert [r.symbol for r in plain] == ["KO"]


def test_the_fundamental_screen_keeps_the_splitter_under_the_printed_basis(
    screen_history, panel, days, market
):
    d = days[-1]
    members = frozenset({"AAPL", "KO"})
    rows = fundamental_rows(
        screen_history, panel, members, d, FND, price_basis=PRINTED, market=market
    )
    assert [r.symbol for r in rows] == ["AAPL", "KO"]
    assert {r.symbol: r.close for r in rows}["AAPL"] == float(screen_history["AAPL"].close[-1])


def test_the_fundamental_screen_refuses_a_printed_basis_without_splits(
    screen_history, panel, days, blind
):
    d = days[-1]
    members = frozenset({"AAPL", "KO"})
    with pytest.raises(PrintedBasisUnavailable):
        fundamental_rows(
            screen_history, panel, members, d, FND, price_basis=PRINTED, market=blind
        )


def test_the_fundamental_none_basis_asks_nothing(screen_history, panel, days):
    d = days[-1]
    members = frozenset({"AAPL", "KO"})
    rows = fundamental_rows(screen_history, panel, members, d, FND, price_basis=NONE)
    assert [r.symbol for r in rows] == ["AAPL", "KO"]


# ----------------------------------------------------------------- the frozen sites, as a list

FROZEN_SITES: tuple[tuple[str, int], ...] = (
    ("m0052_turn_of_month_tilt", 145),
    ("m0109_book_drawdown_brake", 213),
    ("m0117_index_tenure_exclusion", 200),
    ("m0276_cheap_financial_health", 294),
)


def test_the_frozen_sites_still_read_the_adjusted_close():
    """Sites 3-6 are pre-registrations and are deliberately NOT repaired (docs/lab/price-floor.md).

    This is the record that they were looked at and left alone: each file still holds its own
    comparison against its own module's close. If one of them ever starts importing the
    supported helper, somebody edited a frozen file, and this says so in the same breath as
    ``test_a_method_that_ran_is_frozen_to_its_latest_recorded_sha``.
    """
    for module_name, _line in FROZEN_SITES:
        mod = importlib.import_module(f"seer_engine.lab.methods.{module_name}")
        source = inspect.getsource(mod)
        assert "min_price" in source or "MIN_PRICE" in source
        assert "price_floor" not in source, (
            f"{module_name} now imports the supported helper: a frozen pre-registration was edited"
        )

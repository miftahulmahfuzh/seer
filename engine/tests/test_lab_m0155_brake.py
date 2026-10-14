"""M0155's single-name brake: the three claims the method file makes about it.

``test_lab_methods`` already drives every lab allocator through ``allocatorkit`` (valid targets,
the P4 identity, no look-ahead, the declared lookback) and runs every candidate on a smoke
window. These are the checks that are specific to this brake and that the generic kit cannot
make:

1. **With the brake off this allocator IS the host book**, target for target, on every probe.
   That is why M0155 does not spend a trial on a control arm: M0128-RAW20 (trial #388) is the
   unbraked twenty-name book, recorded, and this test is what earns the right to quote it.
2. **The trigger is relative, not absolute.** A name that collapses on its own is braked; the
   same collapse happening to the whole market, index included, is not. This is the exact
   failure M0019's protective stop died of and the one thing the method claims to have fixed.
3. **The two shapes do different things.** ``fill=False`` leaves the braked name's slot in cash
   and the survivors at their original weight; ``fill=True`` refills it from the ranking, so the
   book still holds ``top`` names and still weighs 1.

A dedicated module rather than more cases inside the shared lab tests, because the fixtures here
are hand-built falls and the smoke market is deliberately not.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

import numpy as np
import pytest
from labkit import MEMBER_STOCKS, smoke_market

from seer_engine import dates
from seer_engine.backtest.dev import DEV_END
from seer_engine.lab.methods.m0007_residual_momentum import RESIDMOM, TREND, build_grid
from seer_engine.lab.methods.m0155_single_name_shortfall_brake import (
    HOST,
    SHORTFALL,
    ShortfallBrakeParams,
    braked_names,
    market_calm,
    shortfall_z,
)
from seer_engine.strategies.allocator import scale_weight
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import FactorParams

PROBES = dates.sessions(date(2015, 1, 2), DEV_END)[::20]
MEMBERS = frozenset(MEMBER_STOCKS)
OFF = ShortfallBrakeParams(HOST)
K2 = Decimal("2.0")


@pytest.fixture(scope="module")
def market():
    return smoke_market(("SPY",))


def test_the_brake_off_is_the_host_book_target_for_target(market):
    """M0155 with k None equals M0007-N20-RAW exactly: the control M0128-RAW20 recorded."""
    prepared_host = RESIDMOM.prepare(market.history)
    prepared_brake = SHORTFALL.prepare(market.history)
    seen = 0
    for session in PROBES:
        d = dates.prev_session(session)
        host = RESIDMOM.targets(market.history, MEMBERS, d, frozenset(), HOST)
        brake = SHORTFALL.targets(market.history, MEMBERS, d, frozenset(), OFF)
        assert brake == host, d
        host_p = RESIDMOM.targets_prepared(prepared_host, MEMBERS, d, frozenset(), HOST)
        brake_p = SHORTFALL.targets_prepared(prepared_brake, MEMBERS, d, frozenset(), OFF)
        assert brake_p == host_p == host, d
        seen += len(host)
    assert seen > 0, "every probe was empty, so the comparison proved nothing"


def test_the_brake_off_declares_the_hosts_lookback(market):
    assert SHORTFALL.lookback(OFF) == RESIDMOM.lookback(HOST)
    assert SHORTFALL.symbols(OFF) == RESIDMOM.symbols(HOST)
    assert SHORTFALL.holds(OFF) == ()
    assert SHORTFALL.uses_members(OFF) is True


def _falling(history: dict[str, History], symbols: tuple[str, ...], d: date, drop: float,
             n: int = 63) -> dict[str, History]:
    """``history`` with the last ``n`` sessions through ``d`` of each named symbol ramped to ``drop``.

    ``n = 21`` confines the fall to the sessions the host's 12-1 ranking SKIPS, so the ranking is
    unmoved and any change in the book is the brake's doing and nothing else. ``n = 63`` fills
    the whole brake window and moves the ranking too, which is the realistic case.
    """
    out = dict(history)
    for symbol in symbols:
        h = out[symbol]
        end = int(np.searchsorted(h.dates, np.datetime64(d, "D"), side="right"))
        close = h.close.copy()
        close[end - n : end] = close[end - n : end] * np.linspace(1.0, drop, n)
        out[symbol] = History(h.symbol, h.dates, h.open, h.high, h.low, close, h.volume)
    return out


def test_a_name_that_collapses_alone_is_braked(market):
    d = dates.prev_session(PROBES[-1])
    history = _falling(dict(market.history), ("AAA",), d, 0.45)
    grid = build_grid(history, "SPY")
    z = shortfall_z(grid, list(MEMBER_STOCKS), d, ShortfallBrakeParams(HOST, k=K2))
    assert z["AAA"] < -2.0, z["AAA"]
    assert braked_names(grid, list(MEMBER_STOCKS), d, ShortfallBrakeParams(HOST, k=K2)) == {"AAA"}


def test_a_fall_the_whole_market_shares_is_not_braked(market):
    """The same collapse, happening to every name AND to the index: nothing is braked."""
    d = dates.prev_session(PROBES[-1])
    history = _falling(dict(market.history), (*MEMBER_STOCKS, "SPY"), d, 0.45)
    grid = build_grid(history, "SPY")
    p = ShortfallBrakeParams(HOST, k=K2)
    assert braked_names(grid, list(MEMBER_STOCKS), d, p) == frozenset()


def test_market_up_stands_down_when_the_index_quarter_is_negative(market):
    d = dates.prev_session(PROBES[-1])
    history = _falling(dict(market.history), ("AAA", "SPY"), d, 0.45)
    grid = build_grid(history, "SPY")
    assert market_calm(grid, d, ShortfallBrakeParams(HOST, k=K2)) is True
    up = ShortfallBrakeParams(HOST, k=K2, fill=True, market_up=True)
    assert market_calm(grid, d, up) is False
    assert braked_names(grid, list(MEMBER_STOCKS), d, up) == frozenset()


def test_a_braked_name_leaves_its_slot_in_cash_and_the_survivors_untouched():
    """``fill=False``: the book holds one fewer name and every survivor keeps its original weight."""
    market = smoke_market(("SPY",))
    d = dates.prev_session(PROBES[-1])
    history = _falling(dict(market.history), ("AAA",), d, 0.45)
    base = SHORTFALL.targets(history, MEMBERS, d, frozenset(), OFF)
    assert any(t.symbol == "AAA" for t in base), "nothing to brake on this session"
    cash = SHORTFALL.targets(history, MEMBERS, d, frozenset(), ShortfallBrakeParams(HOST, k=K2))
    assert "AAA" not in {t.symbol for t in cash}
    assert len(cash) == len(base) - 1
    # the survivors are untouched: a brake must not re-concentrate into the names it kept
    assert {(t.symbol, t.weight) for t in cash} == {(t.symbol, t.weight) for t in base if t.symbol != "AAA"}


def test_a_half_cut_keeps_the_name_at_a_smaller_weight():
    market = smoke_market(("SPY",))
    d = dates.prev_session(PROBES[-1])
    history = _falling(dict(market.history), ("AAA",), d, 0.45)
    base = SHORTFALL.targets(history, MEMBERS, d, frozenset(), OFF)
    assert any(t.symbol == "AAA" for t in base), "nothing to brake on this session"
    half = SHORTFALL.targets(history, MEMBERS, d, frozenset(),
                             ShortfallBrakeParams(HOST, k=K2, cut=Decimal("0.5")))
    assert len(half) == len(base)
    was = next(t for t in base if t.symbol == "AAA").weight
    now = next(t for t in half if t.symbol == "AAA").weight
    assert now == scale_weight(was, Decimal("0.5"))


def test_fill_refills_the_slot_from_the_ranking():
    """``fill=True``: the book still holds ``top`` names, so only the swap is being priced.

    The method's own arms hold twenty names and the smoke market serves eight, so the refill
    cannot be seen at the configured width -- with fewer eligible names than slots ``fill=True``
    and ``fill=False`` give the same book. A four-name book on the same bars leaves four spare
    ranked names and makes the difference observable.
    """
    market = smoke_market(("SPY",))
    d = dates.prev_session(PROBES[-1])
    narrow = replace(HOST, inner=FactorParams(rank="momentum", top=4, trend=TREND))
    base = SHORTFALL.targets(market.history, MEMBERS, d, frozenset(), ShortfallBrakeParams(narrow))
    assert len(base) == 4
    worst = base[-1].symbol
    # The fall is confined to the 21 sessions the 12-1 ranking skips, so the ranking does not
    # move and the only thing that can change the book is the brake.
    history = _falling(dict(market.history), (worst,), d, 0.45, n=21)
    unbraked = SHORTFALL.targets(history, MEMBERS, d, frozenset(), ShortfallBrakeParams(narrow))
    assert [t.symbol for t in unbraked] == [t.symbol for t in base], "the ranking moved"
    cash = SHORTFALL.targets(history, MEMBERS, d, frozenset(), ShortfallBrakeParams(narrow, k=K2))
    full = SHORTFALL.targets(history, MEMBERS, d, frozenset(),
                             ShortfallBrakeParams(narrow, k=K2, fill=True))
    assert worst not in {t.symbol for t in cash}
    assert worst not in {t.symbol for t in full}
    assert len(cash) == 3, "the braked slot is cash"
    assert len(full) == 4, "the braked slot is refilled from the ranking"
    assert {t.weight for t in full} == {t.weight for t in base}
    assert set(t.symbol for t in full) - set(t.symbol for t in base), "nothing new was bought"


def test_a_contradictory_configuration_is_refused():
    with pytest.raises(ValueError, match="cut must be 0"):
        ShortfallBrakeParams(HOST, k=K2, fill=True, cut=Decimal("0.5"))
    with pytest.raises(ValueError, match="exactly one spelling"):
        ShortfallBrakeParams(HOST, fill=True)
    with pytest.raises(ValueError, match="k must be > 0"):
        ShortfallBrakeParams(HOST, k=Decimal("0"))

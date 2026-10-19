"""M0258's banded gate: the five claims the method file makes that the generic kit cannot check.

``test_lab_methods`` already drives every lab allocator through ``allocatorkit`` -- valid targets,
the P4 identity, no look-ahead -- and runs every candidate on a smoke window. These are the
properties specific to putting a price band around a gate on somebody else's book:

1. **A zero band IS the lab's gate**, session for session on the smoke tape. The method routes
   ``band = 0`` through ``f_factor.trend_on`` rather than through ``band_on`` at zero, and this is
   the test that earns the right to call the zero rung a reproduction rather than an approximation.
2. **The overlay declares the host's shape** -- above all the same lookback. A wider lookback would
   move the dev window's first scored session off M0072's 1996-01-03 and break every paired
   difference the method reports, and ``m0101.SCAN`` is the obvious thing someone would add.
3. **The params round-trip and the doses digest apart.** ``config_text`` reads the rules, the
   allocator id and the params only, so if ``as_dict`` dropped a field two different bands would
   record under one digest and the second would be refused as already run.
4. **With the band off this allocator IS the host book**, target for target, on both the
   history-only and the prepared path. That is why M0258 spends no trial on a separate control:
   M0072-Z2-RAWRANK is recorded, and this test is what earns the right to quote it.
5. **The band is actually wired in.** Every rung must change the gate's reading somewhere on the
   tape, or an arm that looks like a dose is running the bare gate under another name.

A dedicated module rather than more cases inside the shared lab tests: the smoke fixture's 473
sessions are a fixed budget every lab method is measured against, and a new method must fit it
rather than stretch it.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from labkit import MEMBER_STOCKS, SMOKE_FIRST, smoke_market

from seer_engine import dates
from seer_engine.backtest.dev import DEV_END, Candidate
from seer_engine.lab.method import config_digest
from seer_engine.lab.methods.m0063_earnings_day_jump import WEEKLY_HOLD_FRAC_GOTRADE
from seer_engine.lab.methods.m0072_standardised_earnings_jump import ZJUMP
from seer_engine.lab.methods.m0101_calm_raisers_banded_switch import band_on
from seer_engine.lab.methods.m0258_gate_price_band import (
    ADDED,
    B15,
    B30,
    B60,
    BANDED,
    BOOK,
    BandParams,
)
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.f_factor import trend_on

BENCH = "SPY"
SMA_N = 200
MEMBERS = frozenset(MEMBER_STOCKS)
PROBES = dates.sessions(date(2014, 12, 1), DEV_END)[::40]
OFF = BandParams(BOOK, Decimal(0))


@pytest.fixture(scope="module")
def market():
    return smoke_market((BENCH,))


def _spy_sessions(market):
    """Every smoke session SPY has a bar for, which on this fixture is all 473 of them."""
    h = market.history[BENCH]
    return [d for d in dates.sessions(SMOKE_FIRST, DEV_END) if h.index_of(d) is not None]


def test_a_zero_band_is_the_lab_gate_on_every_session(market):
    """``band_on(..., 0.0)`` equals ``trend_on`` on every smoke session, both readings seen.

    The method routes the zero rung through ``trend_on``, so this is not how M0258 runs -- it is
    the proof that the ladder has a genuine zero dose and that the rungs above it differ from the
    host by the band and by nothing else. ``band_on``'s fallback and its ``isfinite`` guard are
    one edge case away from ``trend_on``, which is exactly why this is asserted and not assumed.
    """
    h = market.history[BENCH]
    sessions = _spy_sessions(market)
    assert len(sessions) > 400, "the smoke fixture shrank; this check needs a tape to walk"
    on = 0
    for d in sessions:
        gate = trend_on(market.history, d, BOOK.jump.inner)
        assert band_on(h, d, SMA_N, 0.0) is gate, d
        on += int(gate)
    assert 0 < on < len(sessions), "the gate never changed its mind: the comparison proved nothing"


def test_the_overlay_declares_the_host_books_shape(market):
    """Lookback, symbols, holds and membership are M0072's, unchanged, at every band."""
    for band in (Decimal(0), B15, B30, B60):
        p = BandParams(BOOK, band)
        assert BANDED.lookback(p) == ZJUMP.lookback(BOOK), band
        assert BANDED.symbols(p) == ZJUMP.symbols(BOOK), band
        assert BANDED.holds(p) == ZJUMP.holds(BOOK), band
        assert BANDED.uses_members(p) is ZJUMP.uses_members(BOOK), band


def test_the_params_round_trip_and_the_doses_digest_apart():
    """``as_dict`` carries every field, and each arm is its own configuration."""
    p = BandParams(BOOK, B30)
    rendered = p.as_dict()
    assert set(rendered) == {"band"} | {f"book.{k}" for k in BOOK.as_dict()}
    assert rendered["band"] == "0.03"
    assert all(isinstance(v, str) for v in rendered.values())
    for k, v in BOOK.as_dict().items():
        assert rendered[f"book.{k}"] == v
    assert BandParams(BOOK, Decimal(0)).as_dict()["band"] == "0"

    def candidate(suffix, band, rules):
        return Candidate(id=f"M0258-{suffix}", family="M0258", rules=rules, allocator=BANDED,
                         params=BandParams(BOOK, band), rationale="a rung", added=ADDED,
                         owner_inputs=())

    digests = {
        config_digest(candidate("M-B0", Decimal(0), MONTHLY_HOLD_FRAC_GOTRADE)),
        config_digest(candidate("M-B15", B15, MONTHLY_HOLD_FRAC_GOTRADE)),
        config_digest(candidate("M-B30", B30, MONTHLY_HOLD_FRAC_GOTRADE)),
        config_digest(candidate("M-B60", B60, MONTHLY_HOLD_FRAC_GOTRADE)),
        config_digest(candidate("W-B0", Decimal(0), WEEKLY_HOLD_FRAC_GOTRADE)),
        config_digest(candidate("W-B30", B30, WEEKLY_HOLD_FRAC_GOTRADE)),
    }
    assert len(digests) == 6, "two arms share a configuration digest"


def test_the_band_off_is_the_host_book_target_for_target(market):
    """At ``band = 0`` M0258 equals M0072-Z2-RAWRANK, on both paths, at every probe."""
    prepared_host = ZJUMP.prepare(market.history)
    prepared_band = BANDED.prepare(market.history)
    seen = 0
    for session in PROBES:
        d = dates.prev_session(session)
        host = ZJUMP.targets(market.history, MEMBERS, d, frozenset(), BOOK)
        band = BANDED.targets(market.history, MEMBERS, d, frozenset(), OFF)
        host_p = ZJUMP.targets_prepared(prepared_host, MEMBERS, d, frozenset(), BOOK)
        band_p = BANDED.targets_prepared(prepared_band, MEMBERS, d, frozenset(), OFF)
        assert band == host, d
        assert band_p == host_p == host, d
        seen += len(host)
    assert seen > 0, "every probe was empty, so the comparison proved nothing"


def test_every_rung_actually_moves_the_gate(market):
    """Each band changes the reading somewhere, or it is the bare gate wearing a dose's name."""
    h = market.history[BENCH]
    sessions = _spy_sessions(market)
    for band in (B15, B30, B60):
        moved = sum(
            1 for d in sessions
            if band_on(h, d, SMA_N, float(band)) != band_on(h, d, SMA_N, 0.0)
        )
        assert moved > 0, f"band {band} never differs from the bare gate on the smoke tape"


def test_the_params_refuse_what_they_say_they_refuse():
    """The validator is part of the pre-registration: a band outside [0, 0.2) is not this method."""
    with pytest.raises(ValueError):
        BandParams(BOOK, Decimal("0.2"))
    with pytest.raises(ValueError):
        BandParams(BOOK, Decimal("-0.01"))
    with pytest.raises(ValueError):
        BandParams(BOOK, Decimal("NaN"))
    with pytest.raises(ValueError):
        BandParams(BOOK, 0.03)  # a float band, not a Decimal: ValueError, as M0101 raises it
    with pytest.raises(TypeError):
        BandParams(object(), Decimal(0))
    with pytest.raises(TypeError):
        BANDED.lookback(BOOK)

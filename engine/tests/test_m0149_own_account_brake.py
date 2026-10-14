"""M0149's own checks: the brake must execute, stand down, and stay P4-clean.

``test_lab_methods`` runs every lab method on ``labkit.smoke_market``, whose calendar is 473
sessions -- shorter than M0109's ``WARM`` of 504 -- so the drawdown brake stands down there and
the shared contract proves nothing about it. These tests build the same synthetic market over a
longer calendar, where the shadow is warm and the dial is live, and check the five things the
method's verdict will rest on:

1. with both brakes off, M0149 picks exactly what M0133-N40 picks (so the recorded parent trial
   is a legitimate yardstick);
2. the shadow is the UNBRAKED book -- it does not depend on the taper (the ratchet guard);
3. the brake actually bites somewhere on a calendar that contains a fall, and the harder taper
   bites harder (so a null result in the run is a finding, not a no-op);
4. below ``WARM`` the braked arms are byte-identical to the control (the hard on/off);
5. the P4 identity and the no-look-ahead contract hold with the brake LIVE, not merely
   stood down, and what the one relaxed check gives up is itself pinned.

Measured 2026-10-14 while this plan was written: all seven pass, and the shared contract in
``test_lab_methods`` passes for all six candidates on the smoke market as well.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from allocatorkit import assert_no_lookahead, assert_p4_identity, everyone, tail
from labkit import BASE_ETFS, MEMBER_STOCKS, smoke_history, smoke_market

from seer_engine import dates
from seer_engine.backtest.dev import DEV_END
from seer_engine.lab.methods.m0109_book_drawdown_brake import WARM, shadow_drawdown
from seer_engine.lab.methods.m0133_gated_updown_asymmetry import ASYM
from seer_engine.lab.methods.m0149_own_account_brake import (
    BOOK,
    BRAKED,
    AccountBrakeParams,
)

DEEP_FIRST = date(2007, 1, 3)  # ~2,200 NYSE sessions through DEV_END: comfortably past WARM

CONTROL = AccountBrakeParams(BOOK)
DD15 = AccountBrakeParams(BOOK, taper=Decimal("0.15"))
DD25 = AccountBrakeParams(BOOK, taper=Decimal("0.25"))
TV14 = AccountBrakeParams(BOOK, target_vol=Decimal("0.14"))


@pytest.fixture(scope="module")
def deep():
    """``smoke_market``'s generator over a calendar deep enough to warm the brake."""
    days = dates.sessions(DEEP_FIRST, DEV_END)
    assert len(days) > WARM + BOOK.window
    symbols = tuple(sorted(set(BASE_ETFS) - set(MEMBER_STOCKS))) + MEMBER_STOCKS
    return {s: smoke_history(s, k, days) for k, s in enumerate(symbols)}


@pytest.fixture(scope="module")
def probes(deep):
    sessions = [d for d in deep["SPY"].dates.astype(object)]
    return sessions[WARM + 20 :: 60]


def _total(targets) -> Decimal:
    return sum((t.weight for t in targets), Decimal(0))


def test_the_control_arm_picks_exactly_what_m0133_n40_picks():
    """With both brakes off, M0149 is M0133's ungated 40-name book, target for target."""
    history = smoke_market().history
    members = everyone(history)
    mine = BRAKED.prepare(history)
    theirs = ASYM.prepare(history)
    nonempty = 0
    for d in dates.sessions(date(2015, 1, 2), DEV_END)[::20]:
        a = BRAKED.targets_prepared(mine, members(d), d, frozenset(), CONTROL)
        b = ASYM.targets_prepared(theirs, members(d), d, frozenset(), BOOK)
        assert a == b, d
        nonempty += 1 if a else 0
    assert nonempty > 0, "the probe dates produced no targets, so nothing was compared"


def test_the_shadow_does_not_depend_on_the_brake(deep):
    """The ratchet guard: the shadow is the UNBRAKED book, so every taper reads the same one."""
    p = BRAKED.prepare(deep)
    first = p.shadow(BOOK)
    assert first is not None
    assert p.shadow(BOOK) is first  # cached, and keyed on the book alone
    assert list(p.shadows) == [BOOK]  # the taper is not part of the key


def test_the_brake_bites_and_the_harder_taper_bites_harder(deep, probes):
    """On a calendar containing a fall, the dial cuts somewhere, and 15% cuts at least as deep."""
    members = everyone(deep)
    p = BRAKED.prepare(deep)
    wealth = p.shadow(BOOK)
    grid = p.book.grid(BOOK.market)
    bit = 0
    for d in probes:
        base = BRAKED.targets_prepared(p, members(d), d, frozenset(), CONTROL)
        if not base:
            continue
        soft = BRAKED.targets_prepared(p, members(d), d, frozenset(), DD25)
        hard = BRAKED.targets_prepared(p, members(d), d, frozenset(), DD15)
        assert _total(hard) <= _total(soft) <= _total(base), d
        drawdown = shadow_drawdown(grid, wealth, d, DD25)
        if drawdown is not None and drawdown > 0.0:
            if _total(soft) < _total(base) or _total(hard) < _total(base):
                bit += 1
    assert bit > 0, "the brake never cut on any probe date: the dial is a no-op here"


def test_the_vol_dial_only_cuts(deep, probes):
    members = everyone(deep)
    p = BRAKED.prepare(deep)
    seen = 0
    for d in probes:
        base = BRAKED.targets_prepared(p, members(d), d, frozenset(), CONTROL)
        if not base:
            continue
        seen += 1
        assert _total(BRAKED.targets_prepared(p, members(d), d, frozenset(), TV14)) <= _total(base)
    assert seen > 0


def test_the_brake_stands_down_below_warm():
    """On the 473-session smoke calendar the dial is cold, so every braked arm IS the control."""
    history = smoke_market().history
    members = everyone(history)
    p = BRAKED.prepare(history)
    for d in dates.sessions(date(2015, 1, 2), DEV_END)[::20]:
        base = BRAKED.targets_prepared(p, members(d), d, frozenset(), CONTROL)
        assert BRAKED.targets_prepared(p, members(d), d, frozenset(), DD15) == base, d
        assert BRAKED.targets_prepared(p, members(d), d, frozenset(), DD25) == base, d


def test_p4_identity_and_no_lookahead_with_the_brake_live(deep, probes):
    """The shared contract, re-run where the dial is warm instead of stood down.

    ``check_lookback=False`` for the braked arms, and the reason is M0109's design rather than a
    weakened check. ``lookback`` declares what the PICKS need; the brake's own depth is ``WARM``
    and it stands down below it (M0109 does exactly this -- its ``lookback`` is ``DV_N``). A
    history cut to ``lookback`` bars is by construction shallower than ``WARM``, so on that cut
    the brake correctly stands down and the targets are the control's. Folding ``WARM + peak_n``
    into ``lookback`` would push it past the 473-bar smoke fixture and the method could never run
    at all. The next test pins the degradation itself, which is the stronger statement: below the
    declared depth the answer is the CONTROL's, never a third thing.
    """
    members = everyone(deep)
    held_sets = [frozenset(), frozenset(MEMBER_STOCKS[:2]) & frozenset(deep)]
    braked_params = [DD15, DD25, AccountBrakeParams(BOOK, taper=Decimal("0.25"),
                                                    target_vol=Decimal("0.14"))]
    back = [dates.prev_session(s) for s in probes]
    nonempty = assert_p4_identity(BRAKED, deep, members, back, held_sets, braked_params,
                                  check_lookback=False)
    # The vol dial reads only each holding's own last vol_n + 1 bars, so its lookback IS honest.
    nonempty += assert_p4_identity(BRAKED, deep, members, back, held_sets, [CONTROL, TV14])
    nonempty += assert_no_lookahead(BRAKED, deep, members, probes, held_sets,
                                    [*braked_params, CONTROL, TV14])
    assert nonempty > 0


def test_below_the_declared_lookback_the_brake_degrades_to_the_control(deep, probes):
    """A history cut to ``lookback`` bars is shallower than WARM, so the dial stands down.

    This is the honest statement of what ``check_lookback=False`` above gives up: the cut answer
    is not wrong, it is the unbraked one. A hard on/off on a fixed session count, never a
    shortened window.
    """
    members = everyone(deep)
    seen = 0
    for d in probes:
        short = tail(deep, d, BRAKED.lookback(DD15))
        for p in (DD15, DD25):
            cut = BRAKED.targets(short, members(d), d, frozenset(), p)
            assert cut == BRAKED.targets(short, members(d), d, frozenset(), CONTROL), (d, p)
            seen += 1 if cut else 0
    assert seen > 0

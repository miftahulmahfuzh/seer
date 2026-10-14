"""M0148's time lock, which the shared contract test cannot reach.

``tests/test_lab_methods.py`` drives a market-aware allocator's history-only path, where M0148
targets nothing by contract, so the three things that make this method what it is -- that K=0 is
M0143's decision verbatim, that a non-zero K actually pins the switch, and that the sell-only arm
leaves the buy-back free -- have no coverage there. They have it here, on a hand-built SPY
history whose shape is chosen so the unlocked switch whipsaws.
"""

from __future__ import annotations

from datetime import date

import numpy as np

from seer_engine.lab.methods.m0143_quarter_return_exit import SWITCH as M0143_SWITCH
from seer_engine.lab.methods.m0143_quarter_return_exit import AsymSwitchParams
from seer_engine.lab.methods.m0148_switch_time_lock import (
    BENCH,
    SWITCH,
    TimeLockParams,
    TimeLockedSwitch,
    past_checks,
)
from seer_engine.strategies.base import History

from seer_engine import dates

FIRST = date(2010, 1, 4)
LAST = date(2015, 10, 16)
SESSIONS = dates.sessions(FIRST, LAST)


def _history(close: np.ndarray) -> History:
    d = np.array([np.datetime64(s, "D") for s in SESSIONS], dtype="datetime64[D]")
    c = np.asarray(close, dtype=np.float64)
    return History(BENCH, d, c.copy(), c.copy(), c.copy(), c.copy(), np.ones(len(d)))


def _chop(period: int = 150, amplitude: float = 0.22) -> History:
    """A sine wave slow enough to cross its own 200-day average again and again."""
    i = np.arange(len(SESSIONS), dtype=np.float64)
    return _history(100.0 * (1.0 + amplitude * np.sin(2.0 * np.pi * i / period)))


def _checks(h: History) -> list[date]:
    """Every monthly check date this history carries, ascending."""
    return past_checks(h, SESSIONS[-1], 10_000)


def _trajectory(h: History, params: TimeLockParams) -> list[bool]:
    """The switch's state after each monthly check, driven through ``held`` as the book does."""
    history = {BENCH: h}
    state = False
    out: list[bool] = []
    for d in _checks(h):
        held = frozenset({BENCH}) if state else frozenset()
        state = SWITCH._on(history, d, held, params)
        out.append(state)
    return out


def _flips(states: list[bool]) -> int:
    return sum(1 for a, b in zip(states, states[1:]) if a != b)


def test_past_checks_returns_month_end_sessions_ascending():
    h = _chop()
    got = past_checks(h, date(2015, 6, 1), 4)
    assert got == [date(2015, 2, 27), date(2015, 3, 31), date(2015, 4, 30), date(2015, 5, 29)]
    assert all(dates.next_session(d).month != d.month for d in got)


def test_past_checks_is_strictly_before_the_data_date():
    h = _chop()
    assert date(2015, 5, 29) not in past_checks(h, date(2015, 5, 29), 4)
    assert past_checks(h, SESSIONS[0], 4) == []


def test_k0_asks_exactly_the_question_m0143_asks():
    """The K0 arm must be M0143-CALM-UP63's decision, not an approximation of it."""
    h = _chop()
    history = {BENCH: h}
    mine = TimeLockParams(0, "both")
    theirs = AsymSwitchParams("calm", "up", 63, "sma200", 0)
    seen = 0
    for d in _checks(h):
        for held in (frozenset(), frozenset({BENCH})):
            assert SWITCH._on(history, d, held, mine) is M0143_SWITCH._on(history, d, held, theirs)
            seen += 1
    assert seen > 0


class _NoReplay(TimeLockedSwitch):
    """The switch with its replay booby-trapped: reaching it at all is the failure."""

    def _settled(self, history, data_date, p):  # noqa: D102
        raise AssertionError("K=0 must decide without the replay")


def test_k0_never_consults_the_replay():
    """``_settled`` is not reached at K=0, which is what makes the reproduction exact."""
    h = _chop()
    history = {BENCH: h}
    switch = _NoReplay()
    for d in _checks(h):
        switch._on(history, d, frozenset(), TimeLockParams(0, "both"))
        switch._on(history, d, frozenset({BENCH}), TimeLockParams(0, "both"))


def test_a_longer_lock_flips_fewer_times_in_a_chop():
    h = _chop()
    counts = [_flips(_trajectory(h, TimeLockParams(k, "both"))) for k in (0, 1, 2, 3)]
    assert counts[0] > 0, "the fixture must whipsaw, or it proves nothing"
    assert counts[0] >= counts[1] >= counts[2] >= counts[3]
    assert counts[3] < counts[0], "a three-check lock must actually bind on this fixture"


def test_the_sell_only_arm_buys_back_inside_its_own_cool_off():
    """K3 locks both directions; K3-SELL must re-enter at least as often as K3 does."""
    h = _chop()
    both = _trajectory(h, TimeLockParams(3, "both"))
    sell = _trajectory(h, TimeLockParams(3, "sell"))
    entries_both = sum(1 for a, b in zip(both, both[1:]) if not a and b)
    entries_sell = sum(1 for a, b in zip(sell, sell[1:]) if not a and b)
    assert entries_sell >= entries_both
    assert sell != both, "on a whipsawing fixture the two arms must part somewhere"


def test_the_replay_reads_no_bar_after_the_data_date():
    h = _chop()
    d = date(2015, 5, 29)
    full = SWITCH._settled({BENCH: h}, d, TimeLockParams(3, "both"))
    cut = SWITCH._settled({BENCH: h.upto(d)}, d, TimeLockParams(3, "both"))
    assert full == cut

"""The kickoff: a book strategy's first decision lands on its first session, not its next cadence day."""

from __future__ import annotations

from datetime import date

import pytest

from seer_engine import dates
from seer_engine.paper.book import last_rank_session, needs_kickoff
from seer_engine.sim.rules import (
    DESIGN_V0,
    MONTHLY_HOLD,
    MONTHLY_RANK_WEEKLY_RESIZE,
    PRESETS,
    is_decision_session,
    is_rank_session,
    is_resize_session,
)

OCT1, OCT6, OCT7, OCT8 = date(2026, 10, 1), date(2026, 10, 6), date(2026, 10, 7), date(2026, 10, 8)
NOV2 = date(2026, 11, 2)


def test_a_mid_month_start_kicks_off_on_its_first_session():
    assert needs_kickoff(MONTHLY_HOLD, OCT6, OCT6, None)


def test_a_clock_started_before_the_rule_kicks_off_on_the_next_session():
    # Prod's clocks started 2026-10-06 with no decision; the next night decides 2026-10-07.
    assert needs_kickoff(MONTHLY_HOLD, OCT6, OCT7, None)


def test_only_once():
    assert not needs_kickoff(MONTHLY_HOLD, OCT6, OCT8, OCT7)


def test_no_kickoff_on_a_cadence_day_or_after_one():
    assert not needs_kickoff(MONTHLY_HOLD, OCT1, OCT1, None)  # the cadence decides it anyway
    assert not needs_kickoff(MONTHLY_HOLD, OCT1, OCT6, None)  # 2026-10-01 already ranked
    assert not needs_kickoff(MONTHLY_HOLD, OCT6, NOV2, None)


# ---- split cadence (monthly rank, weekly resize) ------------------------------------------------

OCT5, OCT12, OCT13, OCT19 = date(2026, 10, 5), date(2026, 10, 12), date(2026, 10, 13), date(2026, 10, 19)
NOV9 = date(2026, 11, 9)


def test_a_clock_starting_on_a_resize_only_monday_kicks_off_there():
    # 2026-10-12 is a week start but not a month start: a resize session, and nothing has ranked
    # yet, so run_book would not decide it. The kickoff ranks it instead.
    assert is_resize_session(MONTHLY_RANK_WEEKLY_RESIZE, OCT12)
    assert needs_kickoff(MONTHLY_RANK_WEEKLY_RESIZE, OCT12, OCT12, None)
    assert needs_kickoff(MONTHLY_RANK_WEEKLY_RESIZE, OCT6, OCT12, None)
    assert not needs_kickoff(MONTHLY_RANK_WEEKLY_RESIZE, OCT12, OCT13, OCT12)
    assert not needs_kickoff(MONTHLY_RANK_WEEKLY_RESIZE, OCT1, OCT12, None)  # 2026-10-01 already ranked
    assert not needs_kickoff(MONTHLY_RANK_WEEKLY_RESIZE, OCT12, NOV2, None)  # the cadence ranks it


def test_without_a_resize_cadence_the_kickoff_test_is_unchanged():
    # Before the split, needs_kickoff tested is_decision_session; for every rule set without a
    # resize_cadence that is is_rank_session, session for session.
    for rules in PRESETS:
        if rules.engine != "book" or rules.resize_cadence is not None:
            continue
        for start in (OCT1, OCT5, OCT6):
            for session in dates.sessions(start, NOV9):
                old = not is_decision_session(rules, session) and not any(
                    is_rank_session(rules, s) for s in dates.sessions(start, session) if s < session
                )
                assert needs_kickoff(rules, start, session, None) is old, (rules.id, start, session)


def test_last_rank_session_is_the_latest_rank_or_kickoff_before_the_session():
    r = MONTHLY_RANK_WEEKLY_RESIZE
    assert last_rank_session(r, OCT1, None, OCT12) == OCT1
    assert last_rank_session(r, OCT6, OCT6, OCT12) == OCT6  # the kickoff ranked
    assert last_rank_session(r, OCT12, OCT12, OCT19) == OCT12  # a kickoff on a resize Monday
    assert last_rank_session(r, OCT6, OCT6, NOV2) == OCT6  # strictly before the session
    assert last_rank_session(r, OCT6, OCT6, NOV9) == NOV2  # the cadence rank supersedes the kickoff
    assert last_rank_session(r, OCT6, None, OCT12) is None  # nothing ranked yet
    assert last_rank_session(r, OCT6, None, OCT6) is None


def test_last_rank_session_argument_checks():
    with pytest.raises(ValueError, match="book"):
        last_rank_session(DESIGN_V0, OCT1, None, OCT12)
    with pytest.raises(ValueError, match="NYSE session"):
        last_rank_session(MONTHLY_RANK_WEEKLY_RESIZE, OCT1, date(2026, 10, 10), OCT12)
    with pytest.raises(TypeError, match="date"):
        last_rank_session(MONTHLY_RANK_WEEKLY_RESIZE, OCT1, None, "2026-10-12")

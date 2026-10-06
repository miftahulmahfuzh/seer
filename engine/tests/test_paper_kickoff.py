"""The kickoff: a book strategy's first decision lands on its first session, not its next cadence day."""

from __future__ import annotations

from datetime import date

from seer_engine.paper.book import needs_kickoff
from seer_engine.sim.rules import MONTHLY_HOLD

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

"""The owner's contribution schedule (plan phase 5): ``sim.contributions``.

The schedule names calendar dates and nothing else; the runners turn them into sessions. Two
things are checked here and nowhere else: that the dates are the right calendar dates in every
month, including February and across a year end, and that the value object refuses a shape that
would silently skip a month. No market, no database.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest

from seer_engine.sim.contributions import (
    MAX_DAY_OF_MONTH,
    OWNER_MONTHLY,
    ContributionSchedule,
    credit_for,
)


def D(s: str) -> date:
    return date.fromisoformat(s)


def test_the_owner_plan_is_five_million_on_the_twenty_fifth():
    assert OWNER_MONTHLY == ContributionSchedule(amount_idr=Decimal("5000000"), day_of_month=25)
    assert OWNER_MONTHLY.amount_idr == Decimal("5000000")
    assert OWNER_MONTHLY.day_of_month == 25


def test_dates_in_covers_every_month_including_february_and_a_year_end():
    got = OWNER_MONTHLY.dates_in(D("2026-10-01"), D("2027-03-31"))
    assert got == (
        D("2026-10-25"), D("2026-11-25"), D("2026-12-25"),
        D("2027-01-25"), D("2027-02-25"), D("2027-03-25"),
    )


def test_dates_in_is_inclusive_at_both_ends_and_empty_backwards():
    assert OWNER_MONTHLY.dates_in(D("2026-10-25"), D("2026-10-25")) == (D("2026-10-25"),)
    assert OWNER_MONTHLY.dates_in(D("2026-10-26"), D("2026-11-24")) == ()
    assert OWNER_MONTHLY.dates_in(D("2026-11-01"), D("2026-10-01")) == ()


def test_due_is_exclusive_of_after_and_inclusive_of_through():
    # The runner's question: with data_date 2026-10-23 (Fri) and session 2026-10-26 (Mon), the
    # Sunday 25th is due; asked again the following session it is not.
    assert OWNER_MONTHLY.due(D("2026-10-23"), D("2026-10-26")) == (D("2026-10-25"),)
    assert OWNER_MONTHLY.due(D("2026-10-26"), D("2026-10-27")) == ()
    assert OWNER_MONTHLY.due(D("2026-10-25"), D("2026-10-26")) == ()


def test_due_can_carry_more_than_one_month_over_a_long_gap():
    assert OWNER_MONTHLY.due(D("2026-10-01"), D("2026-12-31")) == (
        D("2026-10-25"), D("2026-11-25"), D("2026-12-25")
    )


def test_usd_at_rounds_like_initial_cash_usd():
    from seer_engine.sim.model import initial_cash_usd

    rate = Decimal("17841")  # the rate the fee measurements in the plan index were taken at
    assert OWNER_MONTHLY.usd_at(rate) == Decimal("280.2533")
    assert OWNER_MONTHLY.usd_at(rate) == initial_cash_usd(OWNER_MONTHLY.amount_idr, rate)


def test_credit_usd_is_one_converted_deposit_per_due_date():
    rate = Decimal("16000")
    one = OWNER_MONTHLY.usd_at(rate)
    assert one == Decimal("312.5000")
    assert OWNER_MONTHLY.credit_usd(D("2026-10-23"), D("2026-10-26"), rate) == one
    assert OWNER_MONTHLY.credit_usd(D("2026-10-26"), D("2026-10-27"), rate) == Decimal("0")
    assert OWNER_MONTHLY.credit_usd(D("2026-10-01"), D("2026-12-31"), rate) == one * 3


def test_a_day_of_month_that_would_skip_a_month_is_refused():
    for day in (29, 30, 31):
        with pytest.raises(ValueError, match="no month is skipped"):
            ContributionSchedule(Decimal("5000000"), day)
    assert MAX_DAY_OF_MONTH == 28
    assert ContributionSchedule(Decimal("5000000"), 28).dates_in(D("2027-02-01"), D("2027-02-28")) == (
        D("2027-02-28"),
    )


def test_the_value_object_refuses_a_bad_amount_or_day():
    with pytest.raises(TypeError, match="amount_idr must be a Decimal"):
        ContributionSchedule(5000000, 25)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="amount_idr must be a Decimal"):
        ContributionSchedule(5000000.0, 25)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="amount_idr must be a finite amount > 0"):
        ContributionSchedule(Decimal("0"), 25)
    with pytest.raises(ValueError, match="amount_idr must be a finite amount > 0"):
        ContributionSchedule(Decimal("-5000000"), 25)
    with pytest.raises(TypeError, match="day_of_month must be an int"):
        ContributionSchedule(Decimal("5000000"), True)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="no month is skipped"):
        ContributionSchedule(Decimal("5000000"), 0)


def test_dates_and_rates_are_type_checked():
    with pytest.raises(TypeError, match="first must be a date"):
        OWNER_MONTHLY.dates_in(datetime(2026, 10, 1), D("2026-12-31"))
    with pytest.raises(TypeError, match="last must be a date"):
        OWNER_MONTHLY.dates_in(D("2026-10-01"), "2026-12-31")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="after must be a date"):
        OWNER_MONTHLY.due(datetime(2026, 10, 1), D("2026-12-31"))
    with pytest.raises(TypeError, match="usd_idr must be a Decimal"):
        OWNER_MONTHLY.usd_at(16000.0)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="usd_idr must be > 0"):
        OWNER_MONTHLY.usd_at(Decimal("0"))


def test_the_schedule_is_frozen_and_hashable():
    with pytest.raises(Exception):
        OWNER_MONTHLY.amount_idr = Decimal("1")  # type: ignore[misc]
    assert len({OWNER_MONTHLY, ContributionSchedule(Decimal("5000000"), 25)}) == 1


# --------------------------------------------------------------------------- credit_for (D18)


def test_credit_for_reads_a_plan_at_the_runs_rate():
    """A ContributionSchedule is a PLAN: the dollars are computed here, at this run's one rate."""
    rate = Decimal("16000")
    assert credit_for(OWNER_MONTHLY, D("2026-10-23"), D("2026-10-26"), rate) == Decimal("312.5000")
    assert credit_for(OWNER_MONTHLY, D("2026-10-26"), D("2026-10-27"), rate) == Decimal("0")


def test_credit_for_credits_a_record_unchanged_and_never_reconverts_it():
    """A record's dollars were frozen at the rate of the day each landed (phase 6, D6a).

    ``usd_idr`` is not consulted at all: a replay that re-converted would move a stepped book's
    history the first time the rupiah did, which is the one thing a replay may never do.
    """
    record = [(D("2026-10-26"), Decimal("280.2533")), (D("2026-11-25"), Decimal("312.5000"))]
    # The rate below is nothing like either deposit's own rate, and changes nothing.
    for rate in (Decimal("16000"), Decimal("17841"), Decimal("99999")):
        assert credit_for(record, D("2026-10-23"), D("2026-10-26"), rate) == Decimal("280.2533")
        assert credit_for(record, D("2026-11-24"), D("2026-11-25"), rate) == Decimal("312.5000")
        assert credit_for(record, D("2026-10-26"), D("2026-10-27"), rate) == Decimal("0")


def test_credit_for_refuses_a_malformed_record():
    rate = Decimal("16000")
    with pytest.raises(TypeError, match="contributions must be a ContributionSchedule"):
        credit_for("monthly", D("2026-10-23"), D("2026-10-26"), rate)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="contribution amount must be a Decimal"):
        credit_for([(D("2026-10-26"), 312.5)], D("2026-10-23"), D("2026-10-26"), rate)  # type: ignore[list-item]
    with pytest.raises(ValueError, match="contribution amount must be > 0"):
        credit_for([(D("2026-10-26"), Decimal("0"))], D("2026-10-23"), D("2026-10-26"), rate)
    with pytest.raises(ValueError, match="not strictly ascending"):
        credit_for(
            [(D("2026-11-25"), Decimal("1")), (D("2026-10-26"), Decimal("1"))],
            D("2026-10-23"), D("2026-12-31"), rate,
        )

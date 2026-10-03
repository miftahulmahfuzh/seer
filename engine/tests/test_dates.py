"""NYSE date logic under fixed UTC clocks (handover §6.4). No database needed."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from seer_engine import dates
from seer_engine.dates import RunDates, run_dates


def D(s: str) -> date:
    return date.fromisoformat(s)


@pytest.mark.parametrize(
    ("now", "data_date", "session_date"),
    [
        # Friday night run -> Monday.
        ((2026, 10, 2, 23), "2026-10-02", "2026-10-05"),
        # Friday before Labor Day (Mon 2026-09-07) -> Tuesday.
        ((2026, 9, 4, 23), "2026-09-04", "2026-09-08"),
        # Friday before Memorial Day (Mon 2026-05-25) -> Tuesday.
        ((2026, 5, 22, 23), "2026-05-22", "2026-05-26"),
        # Run on the holiday Monday itself: same answer as Friday's run.
        ((2026, 9, 7, 23), "2026-09-04", "2026-09-08"),
        ((2026, 5, 25, 23), "2026-05-22", "2026-05-26"),
        # Saturday and Sunday runs also target Monday.
        ((2026, 10, 3, 23), "2026-10-02", "2026-10-05"),
        ((2026, 10, 4, 23), "2026-10-02", "2026-10-05"),
        # Ordinary weeknight.
        ((2026, 10, 6, 23), "2026-10-06", "2026-10-07"),
        # Before the close on a weekday: data is the previous session, picks are for today.
        ((2026, 10, 7, 15), "2026-10-06", "2026-10-07"),
        # Early-morning UTC run (06:00 WIB is 23:00 UTC the day before; 01:00 UTC retry slot).
        ((2026, 10, 6, 1), "2026-10-05", "2026-10-06"),
        # Thanksgiving week: Wed run skips Thanksgiving (Thu 2026-11-26) to the half day.
        ((2026, 11, 25, 23), "2026-11-25", "2026-11-27"),
        ((2026, 11, 26, 23), "2026-11-25", "2026-11-27"),
        # Half day Fri 2026-11-27 closes 13:00 ET = 18:00 UTC; settled at 19:00 UTC.
        ((2026, 11, 27, 18, 30), "2026-11-25", "2026-11-27"),
        ((2026, 11, 27, 19), "2026-11-27", "2026-11-30"),
        ((2026, 11, 27, 23), "2026-11-27", "2026-11-30"),
        # Good Friday 2026-04-03 is a full NYSE holiday.
        ((2026, 4, 2, 23), "2026-04-02", "2026-04-06"),
        ((2026, 4, 3, 23), "2026-04-02", "2026-04-06"),
        # Year end: Thu 2026-12-31 -> Mon 2027-01-04 (New Year's Day is Friday).
        ((2026, 12, 31, 23), "2026-12-31", "2027-01-04"),
        ((2027, 1, 1, 23), "2026-12-31", "2027-01-04"),
    ],
)
def test_run_dates(utc, now, data_date, session_date):
    assert run_dates(utc(*now)) == RunDates(D(data_date), D(session_date))


@pytest.mark.parametrize(
    ("now", "data_date"),
    [
        # EDT (before 2026-11-01): close 20:00 UTC, settled from 21:00 UTC.
        ((2026, 10, 30, 20, 59), "2026-10-29"),
        ((2026, 10, 30, 21, 0), "2026-10-30"),
        # EST (after 2026-11-01): close 21:00 UTC, settled from 22:00 UTC.
        ((2026, 11, 2, 21, 30), "2026-10-30"),
        ((2026, 11, 2, 22, 0), "2026-11-02"),
        # EST before 2026-03-08: Fri 2026-03-06 settles at 22:00 UTC.
        ((2026, 3, 6, 21, 30), "2026-03-05"),
        ((2026, 3, 6, 22, 0), "2026-03-06"),
        # EDT after 2026-03-08: Mon 2026-03-09 settles at 21:00 UTC.
        ((2026, 3, 9, 20, 59), "2026-03-06"),
        ((2026, 3, 9, 21, 0), "2026-03-09"),
    ],
)
def test_last_completed_session_across_dst(utc, now, data_date):
    assert dates.last_completed_session(utc(*now)) == D(data_date)


def test_settle_margin_is_configurable(utc):
    # 20:30 UTC on an EDT day: closed but not settled with the default 1h margin.
    now = utc(2026, 10, 6, 20, 30)
    assert dates.last_completed_session(now) == D("2026-10-05")
    assert dates.last_completed_session(now, settle=timedelta(0)) == D("2026-10-06")


def test_non_utc_aware_now_is_converted():
    wib = timezone(timedelta(hours=7))
    # 06:00 WIB Saturday == 23:00 UTC Friday.
    assert run_dates(datetime(2026, 10, 3, 6, 0, tzinfo=wib)) == RunDates(
        D("2026-10-02"), D("2026-10-05")
    )


def test_naive_now_is_rejected():
    with pytest.raises(ValueError):
        dates.last_completed_session(datetime(2026, 10, 2, 23))


def test_datetime_is_not_a_date():
    with pytest.raises(TypeError):
        dates.is_session(datetime(2026, 10, 2, tzinfo=timezone.utc))


def test_sessions_inclusive_and_skip_holidays():
    assert dates.sessions(D("2026-04-01"), D("2026-04-07")) == [
        D("2026-04-01"),
        D("2026-04-02"),
        D("2026-04-06"),
        D("2026-04-07"),
    ]
    assert dates.sessions(D("2026-04-03"), D("2026-04-03")) == []
    assert dates.sessions(D("2026-04-07"), D("2026-04-01")) == []


def test_sessions_span_year_boundary():
    assert dates.sessions(D("2026-12-30"), D("2027-01-05")) == [
        D("2026-12-30"),
        D("2026-12-31"),
        D("2027-01-04"),
        D("2027-01-05"),
    ]


def test_is_session():
    assert dates.is_session(D("2026-11-27"))  # half day is a session
    assert not dates.is_session(D("2026-11-26"))  # Thanksgiving
    assert not dates.is_session(D("2026-04-03"))  # Good Friday
    assert not dates.is_session(D("2026-10-03"))  # Saturday


def test_next_and_prev_session():
    assert dates.next_session(D("2026-10-02")) == D("2026-10-05")
    assert dates.next_session(D("2026-10-03")) == D("2026-10-05")
    assert dates.prev_session(D("2026-10-05")) == D("2026-10-02")
    assert dates.prev_session(D("2026-09-08")) == D("2026-09-04")
    assert dates.prev_session(D("2027-01-04")) == D("2026-12-31")


def test_session_close_utc():
    assert dates.session_close_utc(D("2026-11-27")) == datetime(2026, 11, 27, 18, tzinfo=timezone.utc)
    assert dates.session_close_utc(D("2026-10-02")) == datetime(2026, 10, 2, 20, tzinfo=timezone.utc)
    assert dates.session_close_utc(D("2026-12-01")) == datetime(2026, 12, 1, 21, tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        dates.session_close_utc(D("2026-11-26"))


def test_run_dates_defaults_to_now():
    rd = run_dates()
    assert rd.session_date > rd.data_date
    assert dates.is_session(rd.data_date) and dates.is_session(rd.session_date)

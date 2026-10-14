"""Point-in-time membership from month-end dollar-volume ranks."""

from __future__ import annotations

import csv
from datetime import date

import pytest

from seer_engine import universe_rank as ur

D = date


def _samples(rows):
    return [ur.Sample(d, ranks) for d, ranks in rows]


def test_a_symbol_enters_when_it_first_ranks_inside_the_band():
    s = _samples([(D(2000, 1, 31), {"A": 1, "B": 5000}), (D(2000, 2, 29), {"A": 2, "B": 1500})])
    rows = ur.intervals(s, band=(1, 2000))
    assert ("DVOL", "A", D(2000, 1, 31), None) in rows
    assert ("DVOL", "B", D(2000, 2, 29), None) in rows


def test_membership_never_starts_before_the_symbol_qualified():
    """The whole point: a rank known on M may govern membership only from M onward."""
    s = _samples([(D(2000, 1, 31), {"A": 9000}), (D(2000, 2, 29), {"A": 10}),
                  (D(2000, 3, 31), {"A": 10})])
    rows = ur.intervals(s, band=(1, 2000))
    assert [r[2] for r in rows] == [D(2000, 2, 29)]
    assert ur.members_on(rows, D(2000, 1, 31)) == set()


def test_leaving_and_returning_makes_two_spells_not_one_long_one():
    """Collapsing to first-and-last-seen would make the symbol a member through a gap it was
    never liquid in -- a quiet look-ahead."""
    s = _samples([(D(2000, 1, 31), {"A": 10}), (D(2000, 2, 29), {"A": 9000}),
                  (D(2000, 3, 31), {"A": 10})])
    rows = [r for r in ur.intervals(s, band=(1, 2000)) if r[1] == "A"]
    assert len(rows) == 2
    assert rows[0][2:] == (D(2000, 1, 31), D(2000, 2, 29))   # end is exclusive
    assert rows[1][2:] == (D(2000, 3, 31), None)
    # Still a member through February: the exit is only knowable at the 2000-02-29 sample, and
    # dropping it earlier would be hindsight. The genuine gap is between the spells.
    assert ur.members_on(rows, D(2000, 2, 15)) == {"A"}
    assert ur.members_on(rows, D(2000, 3, 15)) == set()


def test_end_is_exclusive_so_the_leaving_sample_is_not_a_member_day():
    s = _samples([(D(2000, 1, 31), {"A": 10}), (D(2000, 2, 29), {"A": 9000})])
    rows = ur.intervals(s, band=(1, 2000))
    assert ur.members_on(rows, D(2000, 2, 28)) == {"A"}
    assert ur.members_on(rows, D(2000, 2, 29)) == set()


def test_a_symbol_still_inside_at_the_last_sample_stays_open():
    s = _samples([(D(2000, 1, 31), {"A": 10})])
    assert ur.intervals(s, band=(1, 2000))[0][3] is None


def test_the_band_is_inclusive_at_both_ends():
    s = _samples([(D(2000, 1, 31), {"LO": 500, "HI": 2000, "OUT": 2001, "ABOVE": 499})])
    rows = ur.intervals(s, band=(500, 2000))
    assert {r[1] for r in rows} == {"LO", "HI"}


def test_read_samples_groups_rows_by_date_and_sorts(tmp_path):
    p = tmp_path / "g.csv"
    with p.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["sample_date", "traded_date", "code", "close", "volume", "dollar_volume", "rank"])
        w.writerow(["2000-02-29", "2000-02-29", "B", "1", "1", "1", "2"])
        w.writerow(["2000-01-31", "2000-01-31", "A", "1", "1", "1", "1"])
        w.writerow(["2000-01-31", "2000-01-31", "B", "1", "1", "1", "3"])
    s = ur.read_samples(p)
    assert [x.sample_date for x in s] == [D(2000, 1, 31), D(2000, 2, 29)]
    assert s[0].ranks == {"A": 1, "B": 3}


@pytest.mark.parametrize("band,expected", [((1, 20), 20), ((1, 2000), 2000), ((500, 2000), 1501)])
def test_the_band_width_is_exactly_what_is_admitted_on_a_full_cross_section(band, expected):
    s = _samples([(D(2000, 1, 31), {f"S{i}": i for i in range(1, 5001)})])
    assert len(ur.intervals(s, band=band)) == expected


def test_the_committed_sweep_is_point_in_time_and_the_band_width_holds():
    """The live file, not a fixture: 214 month-ends, 1998-2015."""
    from pathlib import Path
    p = Path(__file__).resolve().parents[2] / "engine/.cache/eodhd-bulk/monthend_dollar_volume.csv"
    if not p.is_file():
        pytest.skip("the month-end sweep is not on this machine")
    samples = ur.read_samples(p)
    rows = ur.intervals(samples)
    first_ok = {}
    for s in samples:
        for c, rk in s.ranks.items():
            if 1 <= rk <= 2000 and c not in first_ok:
                first_ok[c] = s.sample_date
    assert all(start >= first_ok[sym] for _i, sym, start, _e in rows)
    assert len(ur.members_on(rows, D(2008, 6, 30))) == 2000

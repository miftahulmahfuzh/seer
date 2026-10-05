"""Phase 1: the vendored ticker -> CIK map (engine/src/seer_engine/cik.py)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from seer_engine import cik as c
from seer_engine import membership as m
from seer_engine.cik import CikError, CikRow, Gap

D = date.fromisoformat

HEADER_LINE = ",".join(c.HEADER)


def write(path: Path, *rows: str) -> Path:
    path.write_text("\n".join((HEADER_LINE, *rows)) + "\n", encoding="utf-8")
    return path


def csv_file(tmp_path: Path, *rows: str) -> Path:
    return write(tmp_path / "ticker_cik.csv", *rows)


# --- normalize_cik ---------------------------------------------------------------------


def test_normalize_cik_pads_and_strips():
    assert c.normalize_cik("356028") == "0000356028"
    assert c.normalize_cik(" 0000356028 ") == "0000356028"
    assert c.normalize_cik("CIK0000356028") == "0000356028"


@pytest.mark.parametrize("bad", ["", "   ", "abc", "12345678901", "0000000000", "35,028"])
def test_normalize_cik_rejects_rubbish(bad):
    with pytest.raises(CikError, match="not a CIK"):
        c.normalize_cik(bad)


# --- loading ---------------------------------------------------------------------------


def test_load_reads_a_row(tmp_path):
    path = csv_file(tmp_path, "MON,0001110783,2015-01-02,2018-06-07,MONSANTO CO /NEW/,manual,bayer")
    assert c.load_ticker_cik(path) == [
        CikRow("MON", "0001110783", D("2015-01-02"), D("2018-06-07"),
               "MONSANTO CO /NEW/", "manual", "bayer")
    ]


def test_load_empty_end_date_means_open(tmp_path):
    path = csv_file(tmp_path, "AAPL,0000320193,2015-01-02,,Apple Inc.,current,")
    (row,) = c.load_ticker_cik(path)
    assert row.end_date is None
    assert row.covers(D("2015-01-02")) and row.covers(D("2099-01-01"))
    assert not row.covers(D("2015-01-01"))


def test_load_rejects_a_bad_header(tmp_path):
    path = tmp_path / "ticker_cik.csv"
    path.write_text("symbol,cik\nAAPL,0000320193\n", encoding="utf-8")
    with pytest.raises(CikError, match="expected header"):
        c.load_ticker_cik(path)


def test_load_rejects_an_empty_file(tmp_path):
    with pytest.raises(CikError, match="no rows"):
        c.load_ticker_cik(csv_file(tmp_path))


@pytest.mark.parametrize("cell", ["320193", "00003201930", "abcdefghij", "0000000000", ""])
def test_load_rejects_a_cik_that_is_not_ten_digits(tmp_path, cell):
    path = csv_file(tmp_path, f"AAPL,{cell},2015-01-02,,Apple Inc.,current,")
    with pytest.raises(CikError, match="cik must be 10 digits"):
        c.load_ticker_cik(path)


def test_load_rejects_a_bad_symbol(tmp_path):
    path = csv_file(tmp_path, "Apple Inc,0000320193,2015-01-02,,Apple Inc.,current,")
    with pytest.raises(CikError, match="not a ticker"):
        c.load_ticker_cik(path)


def test_load_rejects_an_unknown_source(tmp_path):
    path = csv_file(tmp_path, "AAPL,0000320193,2015-01-02,,Apple Inc.,guessed,")
    with pytest.raises(CikError, match="source must be one of"):
        c.load_ticker_cik(path)


@pytest.mark.parametrize("source", ["fuzzy", "manual"])
def test_load_requires_a_note_for_fuzzy_and_manual(tmp_path, source):
    path = csv_file(tmp_path, f"AAPL,0000320193,2015-01-02,,Apple Inc.,{source},")
    with pytest.raises(CikError, match="note is required"):
        c.load_ticker_cik(path)


def test_load_requires_a_company_name_when_there_is_a_cik(tmp_path):
    path = csv_file(tmp_path, "AAPL,0000320193,2015-01-02,,,current,")
    with pytest.raises(CikError, match="company_name is required"):
        c.load_ticker_cik(path)


def test_load_rejects_end_before_start(tmp_path):
    path = csv_file(tmp_path, "AAPL,0000320193,2016-01-02,2015-01-02,Apple Inc.,current,")
    with pytest.raises(CikError, match="must be after start_date"):
        c.load_ticker_cik(path)


def test_load_rejects_a_duplicate_row(tmp_path):
    path = csv_file(
        tmp_path,
        "AAPL,0000320193,2015-01-02,2016-01-02,Apple Inc.,current,",
        "AAPL,0000320193,2015-01-02,,Apple Inc.,current,",
    )
    with pytest.raises(CikError, match="duplicate row for AAPL"):
        c.load_ticker_cik(path)


def test_load_rejects_overlapping_intervals_for_one_symbol(tmp_path):
    path = csv_file(
        tmp_path,
        "WRK,0001636023,2015-07-02,2019-01-01,WRKCo Inc.,manual,old",
        "WRK,0001732845,2018-11-02,2024-07-08,WestRock Co,manual,new",
    )
    with pytest.raises(CikError, match="intervals overlap"):
        c.load_ticker_cik(path)


def test_load_rejects_an_open_interval_that_is_not_last(tmp_path):
    path = csv_file(
        tmp_path,
        "WRK,0001636023,2015-07-02,,WRKCo Inc.,manual,old",
        "WRK,0001732845,2018-11-02,2024-07-08,WestRock Co,manual,new",
    )
    with pytest.raises(CikError, match="only the last row may be open"):
        c.load_ticker_cik(path)


def test_load_rejects_an_unsorted_file(tmp_path):
    path = csv_file(
        tmp_path,
        "MSFT,0000789019,2015-01-02,,Microsoft Corp,current,",
        "AAPL,0000320193,2015-01-02,,Apple Inc.,current,",
    )
    with pytest.raises(CikError, match="must be sorted"):
        c.load_ticker_cik(path)


def test_load_accepts_adjacent_intervals(tmp_path):
    path = csv_file(
        tmp_path,
        "WRK,0001636023,2015-07-02,2018-11-02,WRKCo Inc.,manual,old",
        "WRK,0001732845,2018-11-02,2024-07-08,WestRock Co,manual,new",
    )
    assert [r.cik for r in c.load_ticker_cik(path)] == ["0001636023", "0001732845"]


def test_none_row_must_be_the_only_row_for_its_symbol(tmp_path):
    path = csv_file(
        tmp_path,
        "NDOI,NONE,2015-01-02,2016-01-01,,manual,phantom",
        "NDOI,0000320193,2016-01-01,2016-07-18,Apple Inc.,manual,x",
    )
    with pytest.raises(CikError, match="must be the symbol's only row"):
        c.load_ticker_cik(path)


def test_none_row_requires_a_note(tmp_path):
    path = csv_file(tmp_path, "NDOI,NONE,2015-01-02,2016-07-18,,manual,")
    with pytest.raises(CikError, match="note is required"):
        c.load_ticker_cik(path)


# --- resolving -------------------------------------------------------------------------


def index(*rows: str) -> dict[str, tuple[CikRow, ...]]:
    import io

    import csv as _csv

    text = "\n".join((HEADER_LINE, *rows)) + "\n"
    reader = _csv.DictReader(io.StringIO(text))
    return c.build_index(
        CikRow(
            symbol=r["symbol"],
            cik=None if r["cik"] == c.NO_FILER else r["cik"],
            start_date=D(r["start_date"]),
            end_date=D(r["end_date"]) if r["end_date"] else None,
            company_name=r["company_name"],
            source=r["source"],
            note=r["note"],
        )
        for r in reader
    )


WRK_ROWS = (
    "WRK,0001636023,2015-07-02,2018-11-02,WRKCo Inc.,manual,old",
    "WRK,0001732845,2018-11-02,2024-07-08,WestRock Co,manual,new",
)


def test_resolve_picks_the_interval_the_date_falls_in():
    ix = index(*WRK_ROWS)
    assert c.resolve("WRK", D("2016-01-04"), ix) == "0001636023"
    assert c.resolve("WRK", D("2018-11-01"), ix) == "0001636023"
    assert c.resolve("WRK", D("2018-11-02"), ix) == "0001732845"
    assert c.resolve("WRK", D("2024-07-07"), ix) == "0001732845"


def test_resolve_before_and_after_every_interval_raises():
    ix = index(*WRK_ROWS)
    with pytest.raises(CikError, match="outside every known interval"):
        c.resolve("WRK", D("2015-01-02"), ix)
    with pytest.raises(CikError, match="outside every known interval"):
        c.resolve("WRK", D("2024-07-08"), ix)


def test_resolve_an_unknown_symbol_raises():
    with pytest.raises(CikError, match="no row in"):
        c.resolve("ZZZZ", D("2016-01-04"), index(*WRK_ROWS))


def test_resolve_a_no_filer_row_raises_with_the_note():
    ix = index("NDOI,NONE,2015-01-02,2016-07-18,,manual,phantom ticker in ndx_history.csv")
    with pytest.raises(CikError, match="phantom ticker"):
        c.resolve("NDOI", D("2016-01-04"), ix)


def test_filers_lists_each_cik_once_oldest_first():
    ix = index(*WRK_ROWS)
    assert c.filers("WRK", ix) == ("0001636023", "0001732845")
    assert c.filers("WRK", ix, D("2019-01-01"), D("2020-01-01")) == ("0001732845",)
    assert c.filers("WRK", ix, D("2015-01-02"), D("2016-01-02")) == ("0001636023",)
    assert c.filers("WRK", ix, D("2024-07-08"), None) == ()
    assert c.filers("ZZZZ", ix) == ()


def test_filers_skips_no_filer_rows():
    ix = index("NDOI,NONE,2015-01-02,2016-07-18,,manual,phantom")
    assert c.filers("NDOI", ix) == ()


def test_missing_and_no_filer_symbols():
    ix = index(*WRK_ROWS, "NDOI,NONE,2015-01-02,2016-07-18,,manual,phantom")
    assert c.missing_symbols(ix, ["WRK", "NDOI", "AAPL", "MSFT"]) == ("AAPL", "MSFT")
    assert c.no_filer_symbols(ix) == ("NDOI",)


# --- coverage --------------------------------------------------------------------------


def iv(symbol: str, start: str, end: str | None) -> m.Interval:
    return m.Interval(symbol, "SP500", D(start), D(end) if end else None, symbol)


def test_coverage_gaps_is_empty_when_the_rows_span_the_membership():
    ix = index(*WRK_ROWS)
    assert c.coverage_gaps(ix, [iv("WRK", "2015-07-02", "2024-07-08")]) == ()


def test_coverage_gaps_reports_an_uncovered_head():
    ix = index("WRK,0001732845,2018-11-02,2024-07-08,WestRock Co,manual,new")
    assert c.coverage_gaps(ix, [iv("WRK", "2015-07-02", "2024-07-08")]) == (
        Gap("WRK", D("2015-07-02"), D("2018-11-02")),
    )


def test_coverage_gaps_reports_an_uncovered_tail_as_open():
    ix = index("AAPL,0000320193,2015-01-02,2020-01-02,Apple Inc.,current,")
    assert c.coverage_gaps(ix, [iv("AAPL", "2015-01-02", None)]) == (
        Gap("AAPL", D("2020-01-02"), None),
    )


def test_coverage_gaps_reports_a_hole_between_two_rows():
    ix = index(
        "WRK,0001636023,2015-07-02,2017-01-02,WRKCo Inc.,manual,old",
        "WRK,0001732845,2018-11-02,2024-07-08,WestRock Co,manual,new",
    )
    assert c.coverage_gaps(ix, [iv("WRK", "2015-07-02", "2024-07-08")]) == (
        Gap("WRK", D("2017-01-02"), D("2018-11-02")),
    )


def test_coverage_gaps_ignores_membership_before_since():
    """The row opens exactly at the floor, so membership before it is not wanted.

    Anchored to ``c.SINCE`` rather than a literal: the floor moved 2015-01-02 -> 2009-01-01 on
    2026-10-05 and this test is about the clipping, not about the floor's value.
    """
    ix = index(f"CA,0000356028,{c.SINCE},2018-11-06,\"CA, INC.\",manual,recycled")
    assert c.coverage_gaps(ix, [iv("CA", "1996-01-02", "2018-11-06")]) == ()


def test_coverage_gaps_counts_a_no_filer_row_as_an_answer():
    """A NONE row is an explicit answer, so it covers. Anchored to ``c.SINCE``; see above."""
    ix = index(f"NDOI,NONE,{c.SINCE},2016-07-18,,manual,phantom")
    assert c.coverage_gaps(ix, [iv("NDOI", "2007-02-01", "2016-07-18")]) == ()


def test_coverage_gaps_merges_a_leave_and_rejoin():
    ix = index("AAPL,0000320193,2015-01-02,,Apple Inc.,current,")
    intervals = [iv("AAPL", "2015-01-02", "2017-01-02"), iv("AAPL", "2019-01-02", None)]
    assert c.coverage_gaps(ix, intervals) == ()


# --- the vendored file -------------------------------------------------------------------


@pytest.fixture(scope="module")
def vendored_index() -> dict[str, tuple[CikRow, ...]]:
    return c.load_index(c.DATA_DIR)


@pytest.fixture(scope="module")
def ever_members() -> frozenset[str]:
    return m.symbols_since(m.compute_universe(m.DATA_DIR), c.SINCE)


def test_vendored_file_loads_and_is_big_enough(vendored_index, ever_members):
    """913 ever-members at the 2009 floor, measured 2026-10-05; 795 at the retired 2015 one."""
    assert len(ever_members) >= 900
    assert len(vendored_index) == len(ever_members)


def test_vendored_covers_every_ever_member(vendored_index, ever_members):
    assert c.missing_symbols(vendored_index, ever_members) == ()


def test_vendored_has_no_coverage_gap(vendored_index):
    gaps = c.coverage_gaps(vendored_index, m.compute_universe(m.DATA_DIR))
    assert gaps == (), f"{len(gaps)} uncovered stretches, first: {gaps[:5]}"


def test_vendored_has_no_symbol_outside_the_universe(vendored_index, ever_members):
    assert set(vendored_index) <= set(ever_members)


def test_vendored_every_cik_is_ten_digits(vendored_index):
    bad = [
        (row.symbol, row.cik)
        for group in vendored_index.values()
        for row in group
        if row.cik is not None and (len(row.cik) != 10 or not row.cik.isdigit())
    ]
    assert bad == []


# symbol -> (a date inside its membership, the historical filer, the company EDGAR's ticker
# lookup answers with today -- None where EDGAR has no answer at all). Every CIK below was
# confirmed against data.sec.gov/submissions on 2026-10-05.
RECYCLED: dict[str, tuple[date, str, str | None]] = {
    "CA": (D("2016-06-01"), "0000356028", None),
    "MON": (D("2016-06-01"), "0001110783", "0001828325"),
    "PLL": (D("2015-06-01"), "0000075829", "0001728205"),
    "ALTR": (D("2015-06-01"), "0000768251", "0001701732"),
    "LLL": (D("2016-06-01"), "0001039101", "0001546383"),
    "DTV": (D("2015-06-01"), "0001465112", "0000936340"),
}


@pytest.mark.parametrize("symbol", sorted(RECYCLED))
def test_vendored_recycled_ticker_resolves_to_the_historical_company(symbol, vendored_index):
    """R1: during membership the map answers with the index member, never today's holder."""
    on, historical, current_holder = RECYCLED[symbol]
    assert c.resolve(symbol, on, vendored_index) == historical
    if current_holder is not None:
        assert c.resolve(symbol, on, vendored_index) != current_holder


@pytest.mark.parametrize("symbol", sorted(RECYCLED))
def test_vendored_recycled_ticker_has_no_answer_today(symbol, vendored_index):
    """And after the membership ended it refuses to answer rather than guessing."""
    with pytest.raises(CikError, match="outside every known interval"):
        c.resolve(symbol, D("2026-10-05"), vendored_index)


# symbol -> (date inside membership, CIK). Confirmed against data.sec.gov/submissions 2026-10-05.
SPOT_CHECKS: dict[str, tuple[date, str]] = {
    "ATVI": (D("2020-01-02"), "0000718877"),  # ACTIVISION BLIZZARD, INC.
    "TWTR": (D("2020-01-02"), "0001418091"),  # TWITTER, INC.
    "SIVB": (D("2020-01-02"), "0000719739"),  # SVB FINANCIAL GROUP
    "CELG": (D("2016-06-01"), "0000816284"),  # CELGENE CORP /DE/
    "K": (D("2020-01-02"), "0000055067"),     # KELLANOVA, formerly KELLOGG CO
    "PXD": (D("2020-01-02"), "0001038357"),   # PIONEER NATURAL RESOURCES CO
    "AAPL": (D("2020-01-02"), "0000320193"),  # Apple Inc.
}


@pytest.mark.parametrize("symbol", sorted(SPOT_CHECKS))
def test_vendored_spot_checks(symbol, vendored_index):
    on, expected = SPOT_CHECKS[symbol]
    assert c.resolve(symbol, on, vendored_index) == expected


def test_vendored_westrock_changes_filer_mid_membership(vendored_index):
    """WRK keeps its ticker across the 2018-11-02 KapStone close but changes registrant."""
    assert c.resolve("WRK", D("2016-01-04"), vendored_index) == "0001636023"
    assert c.resolve("WRK", D("2020-01-02"), vendored_index) == "0001732845"
    assert c.filers("WRK", vendored_index) == ("0001636023", "0001732845")


def test_vendored_alphabet_reorg_is_dated(vendored_index):
    for symbol in ("GOOG", "GOOGL"):
        assert c.resolve(symbol, D("2015-06-01"), vendored_index) == "0001288776"
        assert c.resolve(symbol, D("2020-01-02"), vendored_index) == "0001652044"


SHARE_CLASSES = [("GOOG", "GOOGL"), ("FOX", "FOXA"), ("NWS", "NWSA"), ("UA", "UAA")]


@pytest.mark.parametrize("a,b", SHARE_CLASSES)
def test_vendored_share_classes_share_a_cik(a, b, vendored_index):
    """One CIK backing two symbols is correct, not a duplicate to be de-duplicated."""
    on = D("2020-01-02")
    assert c.resolve(a, on, vendored_index) == c.resolve(b, on, vendored_index)


def test_vendored_notes_are_present_where_required(vendored_index):
    missing = [
        (row.symbol, row.source)
        for group in vendored_index.values()
        for row in group
        if not row.note and (row.source in c.NOTE_REQUIRED or row.cik is None)
    ]
    assert missing == []


def test_vendored_floor_is_2009_and_no_row_precedes_it():
    """R1: the map's floor is the first year SEC XBRL company facts exist at all."""
    assert c.SINCE == D("2009-01-01")


def test_vendored_no_row_starts_before_the_floor(vendored_index):
    early = [
        (row.symbol, row.start_date)
        for group in vendored_index.values()
        for row in group
        if row.start_date < c.SINCE
    ]
    assert early == []


def test_vendored_carries_no_row_at_the_retired_2015_clamp(vendored_index):
    """The old cik.SINCE wrote 525 rows claiming a start that was not the symbol's.

    Measured 2026-10-05: no symbol in the universe has 2015-01-02 as its real first-membership
    date, so after Fix A the date must not appear as a start_date at all. If a future
    re-vendoring produces a genuine 2015-01-02 handover, name it here rather than deleting the
    test -- the point is that the date is never again a default.
    """
    clamped = sorted(
        row.symbol
        for group in vendored_index.values()
        for row in group
        if row.start_date == D("2015-01-02")
    )
    assert clamped == []


def test_vendored_has_no_fuzzy_row(vendored_index):
    """SOURCES.md requires it. HAR is why: difflib matched 'Harman International Industries'
    to 'AMERICAN INTERNATIONAL INDUSTRIES' (0001073146), which filed 4 periodic reports inside
    the span and so passed the screen. The screen is a net, not a gate.
    """
    fuzzy = sorted(
        row.symbol
        for group in vendored_index.values()
        for row in group
        if row.source == "fuzzy"
    )
    assert fuzzy == []


def test_vendored_none_row_is_ndoi_and_it_is_alone(vendored_index):
    """NDOI is a phantom in the Wikipedia-derived ndx_history.csv and the file's only NONE."""
    none_rows = sorted(
        row.symbol
        for group in vendored_index.values()
        for row in group
        if row.cik is None
    )
    assert none_rows == ["NDOI"]
    assert len(vendored_index["NDOI"]) == 1

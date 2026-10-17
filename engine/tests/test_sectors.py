"""Sector labels: FF12 parsing, cik_sic.csv, (symbol, date) lookups, the capped selection helper,
the submissions parser and the refresh diff, and the vendored files' invariants (no network)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from seer_engine import cik as c
from seer_engine import membership as m
from seer_engine import sec, sectors
from seer_engine.commands import sectors as cmd
from seer_engine.sectors import SectorError, SectorMap, SicRow, select_capped

D = date.fromisoformat
FETCHED = D("2026-10-17")


@pytest.fixture(scope="module")
def ff12() -> sectors.Ff12:
    return sectors.load_ff12(sectors.DATA_DIR / sectors.FF12_FILE)


# --- FF12 -------------------------------------------------------------------------------------


def test_ff12_has_french_twelve_in_order(ff12):
    assert ff12.codes == (
        "NoDur", "Durbl", "Manuf", "Enrgy", "Chems", "BusEq",
        "Telcm", "Utils", "Shops", "Hlth", "Money", "Other",
    )


@pytest.mark.parametrize(
    ("sic", "code"),
    [
        (2911, "Enrgy"),   # petroleum refining: XOM, VLO, MPC, PSX
        (1311, "Enrgy"),   # crude petroleum & natural gas: APA, DVN, EOG, OXY, FANG
        (1381, "Enrgy"),   # drilling oil & gas wells
        (1389, "Enrgy"),   # oil & gas field services: HAL
        (1200, "Enrgy"), (1399, "Enrgy"), (2900, "Enrgy"), (2999, "Enrgy"),  # range edges
        (3571, "BusEq"),   # electronic computers: AAPL
        (3674, "BusEq"),   # semiconductors: NXPI
        (7372, "BusEq"),   # prepackaged software
        (3693, "Hlth"),    # the one-code hole inside BusEq's 3660-3699
        (3692, "BusEq"), (3694, "BusEq"),
        (2834, "Hlth"),    # pharmaceutical preparations
        (2830, "Hlth"), (2839, "Hlth"),
        (2829, "Chems"), (2840, "Chems"),  # chemicals wrap around Hlth's 2830-2839
        (2060, "NoDur"),   # sugar & confectionery: HSY
        (6021, "Money"), (6211, "Money"), (6798, "Money"),  # banks, brokers, REITs
        (4813, "Telcm"), (4911, "Utils"), (4949, "Utils"),
        (4950, "Other"),   # sanitary services sit just past Utils
        (5731, "Shops"),   # radio/TV/electronics stores: BBY
        (7011, "Other"),   # hotels: MAR
        (4922, "Utils"),   # natural gas transmission: TRGP's SIC on EDGAR, so FF12 calls it Utils
        (3711, "Durbl"), (3713, "Manuf"), (3714, "Durbl"), (3716, "Durbl"), (3717, "Manuf"),
        (1040, "Other"),   # gold mining is "Mines"
        (9995, "Other"), (100, "NoDur"), (999, "NoDur"),
    ],
)
def test_ff12_maps_sic(ff12, sic, code):
    assert ff12.industry_of(sic) == code


def test_ff12_unknown_sic_is_none(ff12):
    assert ff12.industry_of(None) is None


def _ff12_text(*lines: str) -> str:
    return "\n".join(lines) + "\n"


TWELVE = [f"{i:2d} X{i}  title {i}" for i in range(1, 12)] + ["12 Other  Other -- rest"]


def test_load_ff12_rejects_overlap(tmp_path):
    lines = list(TWELVE)
    lines.insert(1, "          0100-0200")
    lines.insert(3, "          0150-0300")
    path = tmp_path / "f.txt"
    path.write_text(_ff12_text(*lines))
    with pytest.raises(SectorError, match="overlaps"):
        sectors.load_ff12(path)


def test_load_ff12_rejects_missing_industry(tmp_path):
    path = tmp_path / "f.txt"
    path.write_text(_ff12_text(*TWELVE[:-1]))
    with pytest.raises(SectorError, match="1..12"):
        sectors.load_ff12(path)


def test_load_ff12_rejects_ranges_under_other(tmp_path):
    path = tmp_path / "f.txt"
    path.write_text(_ff12_text(*TWELVE, "          0100-0200"))
    with pytest.raises(SectorError, match="residual"):
        sectors.load_ff12(path)


# --- cik_sic.csv ---------------------------------------------------------------------------------

SIC_HEADER = ",".join(sectors.CIK_SIC_HEADER)


def sic_csv(tmp_path: Path, *rows: str) -> Path:
    path = tmp_path / "cik_sic.csv"
    path.write_text("\n".join((SIC_HEADER, *rows)) + "\n", encoding="utf-8")
    return path


def test_load_cik_sic_reads_and_allows_empty_sic(tmp_path):
    path = sic_csv(
        tmp_path,
        "0000034088,2911,PETROLEUM REFINING,EXXON MOBIL CORP,2026-10-17,edgar-submissions",
        "0000099999,,,SOME TRUST,2026-10-17,edgar-submissions",
    )
    rows = sectors.load_cik_sic(path)
    assert rows["0000034088"].sic == 2911
    assert rows["0000099999"].sic is None


@pytest.mark.parametrize(
    ("row", "msg"),
    [
        ("34088,2911,X,Y,2026-10-17,edgar-submissions", "10 digits"),
        ("0000034088,291,X,Y,2026-10-17,edgar-submissions", "4 digits"),
        ("0000034088,2911,,Y,2026-10-17,edgar-submissions", "sic_description"),
        ("0000034088,2911,X,Y,2026-10-17,guess", "unknown source"),
        ("0000034088,2911,X,Y,yesterday,edgar-submissions", "fetched"),
    ],
)
def test_load_cik_sic_rejects(tmp_path, row, msg):
    with pytest.raises(SectorError, match=msg):
        sectors.load_cik_sic(sic_csv(tmp_path, row))


def test_load_cik_sic_rejects_unsorted_or_duplicate(tmp_path):
    a = "0000034088,2911,X,Y,2026-10-17,edgar-submissions"
    b = "0000000020,2911,X,Y,2026-10-17,edgar-submissions"
    with pytest.raises(SectorError, match="sorted"):
        sectors.load_cik_sic(sic_csv(tmp_path, a, b))
    with pytest.raises(SectorError, match="sorted"):
        sectors.load_cik_sic(sic_csv(tmp_path, a, a))


def test_write_then_load_round_trips(tmp_path):
    rows = [
        SicRow("0000320193", 3571, "ELECTRONIC COMPUTERS", "Apple Inc.", FETCHED, "edgar-submissions"),
        SicRow("0000001800", 2834, "PHARMACEUTICAL PREPARATIONS", "ABBOTT LABORATORIES", FETCHED,
               "edgar-submissions"),
        SicRow("0000000777", None, "", "NO SIC TRUST", FETCHED, "edgar-submissions"),
    ]
    path = tmp_path / "cik_sic.csv"
    assert sectors.write_cik_sic(path, rows) == 3
    back = sectors.load_cik_sic(path)
    assert list(back) == sorted(r.cik for r in rows)
    assert back["0000001800"] == rows[1]
    assert back["0000000777"].sic is None


# --- SectorMap --------------------------------------------------------------------------------


def _row(symbol, cik, start, end=None, note=""):
    return c.CikRow(symbol, cik, D(start), D(end) if end else None, "X" if cik else "", "manual",
                    note or "n")


@pytest.fixture
def smap(ff12) -> SectorMap:
    index = c.build_index([
        # a recycled ticker: one company, then another
        _row("MON", "0001110783", "2009-01-01", "2018-06-07"),
        _row("MON", "0001828325", "2021-01-04"),
        _row("XOM", "0000034088", "1996-01-02"),
        _row("NDOI", None, "2007-02-01", "2016-07-18", note="phantom"),
        _row("NOSIC", "0000000777", "2000-01-03"),
    ])
    sics = {
        "0001110783": SicRow("0001110783", 2870, "AGRICULTURAL CHEMICALS", "MONSANTO", FETCHED,
                             "edgar-submissions"),
        "0001828325": SicRow("0001828325", 6770, "BLANK CHECKS", "MONUMENT CIRCLE", FETCHED,
                             "edgar-submissions"),
        "0000034088": SicRow("0000034088", 2911, "PETROLEUM REFINING", "EXXON", FETCHED,
                             "edgar-submissions"),
        "0000000777": SicRow("0000000777", None, "", "NO SIC", FETCHED, "edgar-submissions"),
    }
    return SectorMap(index=index, sics=sics, ff12=ff12)


def test_sector_follows_the_date_scoped_filer(smap):
    assert smap.sector_of("MON", D("2015-06-01")) == "Chems"
    assert smap.sic_of("MON", D("2015-06-01")) == 2870
    assert smap.sector_of("MON", D("2022-06-01")) == "Money"


def test_sector_is_none_between_tenures_and_outside_the_map(smap):
    assert smap.sector_of("MON", D("2019-06-01")) is None   # the ticker sat unused
    assert smap.sector_of("MON", D("2008-12-31")) is None   # before the first tenure
    assert smap.sector_of("ZZZZ", D("2015-06-01")) is None  # never in the map


def test_sector_is_none_for_no_filer_and_no_sic(smap):
    assert smap.sector_of("NDOI", D("2010-01-04")) is None
    assert smap.sector_of("NOSIC", D("2010-01-04")) is None
    assert smap.sic_of("NOSIC", D("2010-01-04")) is None


def test_map_ciks_skips_none_rows(smap):
    assert sectors.map_ciks(smap.index) == (
        "0000000777", "0000034088", "0001110783", "0001828325",
    )


# --- select_capped ----------------------------------------------------------------------------

ON = D("2026-10-16")
LABELS = {
    "XOM": "Enrgy", "CVX": "Enrgy", "EOG": "Enrgy", "OXY": "Enrgy",
    "AAPL": "BusEq", "NXPI": "BusEq", "HSY": "NoDur", "TROW": "Money",
}


def lab(symbol: str, on: date) -> str | None:
    assert on == ON
    return LABELS.get(symbol)


def test_select_capped_keeps_rank_order_and_caps():
    ranked = ["XOM", "CVX", "EOG", "AAPL", "OXY", "HSY", "NXPI", "TROW"]
    assert select_capped(ranked, ON, 5, 2, lab) == ["XOM", "CVX", "AAPL", "HSY", "NXPI"]


def test_select_capped_without_binding_cap_is_the_top_n():
    ranked = ["XOM", "AAPL", "HSY", "TROW"]
    assert select_capped(ranked, ON, 3, 5, lab) == ["XOM", "AAPL", "HSY"]


def test_select_capped_never_relaxes_the_cap_to_fill():
    assert select_capped(["XOM", "CVX", "EOG", "OXY"], ON, 4, 1, lab) == ["XOM"]


def test_select_capped_unknowns_share_one_bucket():
    ranked = ["U1", "U2", "U3", "XOM", "U4"]
    assert select_capped(ranked, ON, 4, 2, lab) == ["U1", "U2", "XOM"]


def test_select_capped_counts_a_repeat_once():
    assert select_capped(["XOM", "XOM", "CVX", "AAPL"], ON, 3, 1, lab) == ["XOM", "AAPL"]


def test_select_capped_zero_slots_and_bad_arguments():
    assert select_capped(["XOM"], ON, 0, 1, lab) == []
    with pytest.raises(ValueError, match="cap"):
        select_capped(["XOM"], ON, 1, 0, lab)
    with pytest.raises(ValueError, match="n must"):
        select_capped(["XOM"], ON, -1, 1, lab)


def test_select_capped_accepts_a_sector_map(smap):
    picks = select_capped(["XOM", "MON", "NOSIC"], D("2015-06-01"), 3, 1, smap.sector_of)
    assert picks == ["XOM", "MON", "NOSIC"]


# --- sec.parse_filer and the refresh diff -------------------------------------------------------


def test_parse_filer_reads_sic():
    payload = {"cik": "34088", "name": "EXXON MOBIL CORP", "sic": "2911",
               "sicDescription": "Petroleum Refining"}
    assert sec.parse_filer(payload, 34088) == sec.Filer(
        "0000034088", "EXXON MOBIL CORP", 2911, "Petroleum Refining"
    )


@pytest.mark.parametrize("raw", ["", None, "0000", "n/a"])
def test_parse_filer_without_a_sic(raw):
    filer = sec.parse_filer({"name": "SOME TRUST", "sic": raw, "sicDescription": "x"}, 1)
    assert filer.sic is None and filer.sic_description == ""


def test_parse_filer_refuses_a_misrouted_body():
    with pytest.raises(sec.SecError, match="body is for"):
        sec.parse_filer({"cik": "320193", "name": "Apple", "sic": "3571"}, 34088)


def test_submissions_requests_the_submissions_root():
    from test_sec import FakeTransport, _Resp, make

    transport = FakeTransport(_Resp(200, {"cik": "65100", "name": "MERRILL LYNCH & CO INC",
                                          "sic": "6211", "sicDescription": "Security Brokers"}))
    client, _ = make(transport)
    filer = client.submissions(65100)
    assert transport.calls[0]["url"] == "https://data.sec.gov/submissions/CIK0000065100.json"
    assert filer.sic == 6211


def test_submissions_404_is_not_found():
    from test_sec import FakeTransport, _Resp, make

    client, _ = make(FakeTransport(_Resp(404, text="nope")))
    with pytest.raises(sec.SecNotFound, match="no filer"):
        client.submissions(1)


def test_diff_rows_keeps_the_old_fetched_date_when_nothing_changed():
    old = {
        "0000034088": SicRow("0000034088", 2911, "PETROLEUM REFINING", "EXXON MOBIL CORP",
                             D("2026-01-01"), "edgar-submissions"),
        "0000000001": SicRow("0000000001", 6021, "NATIONAL COMMERCIAL BANKS", "BANK",
                             D("2026-01-01"), "edgar-submissions"),
    }
    fetched = {
        "0000034088": sec.Filer("0000034088", "EXXON MOBIL CORP", 2911, "PETROLEUM REFINING"),
        "0000000001": sec.Filer("0000000001", "BANK", 6022, "STATE COMMERCIAL BANKS"),
        "0000000002": sec.Filer("0000000002", "NEW CO", 7372, "SERVICES-PREPACKAGED SOFTWARE"),
    }
    merged, changes = cmd.diff_rows(old, fetched, FETCHED)
    assert merged["0000034088"].fetched == D("2026-01-01")
    assert merged["0000000001"].sic == 6022 and merged["0000000001"].fetched == FETCHED
    assert merged["0000000002"].fetched == FETCHED
    assert [line[0] for line in changes] == ["~", "+"]


def test_tally_counts_member_days_by_sector(smap):
    sessions = [D("2015-06-01"), D("2015-06-02"), D("2019-06-03"), D("2022-06-01")]
    intervals = [
        m.Interval("MON", "SP500", D("2015-01-02"), None, "MON"),
        m.Interval("XOM", "SP500", D("2015-06-02"), D("2019-06-04"), "XOM"),
    ]
    total, mix, unresolved = cmd.tally(intervals, smap, sessions)
    assert total == {2015: 3, 2019: 2, 2022: 1}
    assert mix[2015] == {"Chems": 2, "Enrgy": 1}
    assert mix[2019] == {"Enrgy": 1, sectors.UNKNOWN: 1}  # MON between tenures
    assert mix[2022] == {"Money": 1}
    assert unresolved == {"MON": 1}


# --- the vendored files ------------------------------------------------------------------------


@pytest.fixture(scope="module")
def vendored() -> SectorMap:
    return sectors.load(sectors.DATA_DIR)


@pytest.fixture(scope="module")
def universe() -> list[m.Interval]:
    return m.compute_universe(m.DATA_DIR)


def test_vendored_history_rows_end_by_the_seam():
    rows = c.load_history(c.DATA_DIR)
    assert rows and all(r.end_date is not None and r.end_date <= c.SINCE for r in rows)


def test_vendored_every_ever_member_is_covered_or_explicitly_none(vendored, universe):
    """Every S&P 500 / Nasdaq-100 membership day since 1996 has a tenure row (NONE counts)."""
    gaps = c.coverage_gaps(vendored.index, universe, since=D("1996-01-02"))
    assert gaps == ()


def test_vendored_no_overlapping_tenures(vendored):
    for symbol, group in vendored.index.items():
        for prev, cur in zip(group, group[1:]):
            assert prev.end_date is not None and prev.end_date <= cur.start_date, symbol


def test_vendored_every_map_cik_has_a_sic_row(vendored):
    missing = [k for k in sectors.map_ciks(vendored.index) if k not in vendored.sics]
    assert missing == []


def test_vendored_sic_file_holds_no_cik_outside_the_map(vendored):
    extra = set(vendored.sics) - set(sectors.map_ciks(vendored.index))
    assert extra == set()


def test_vendored_history_notes_are_present_where_required(vendored):
    rows = c.load_history(c.DATA_DIR)
    assert all(r.note for r in rows if r.source in c.NOTE_REQUIRED or r.cik is None)
    assert all(r.note for r in rows if r.source in ("carry", "exact"))


@pytest.mark.parametrize(
    ("symbol", "on", "code"),
    [
        ("XOM", "2026-10-16", "Enrgy"),
        ("AAPL", "2026-10-16", "BusEq"),
        ("HSY", "2026-10-16", "NoDur"),
        ("TROW", "2026-10-16", "Money"),
        ("MON", "2015-06-01", "Chems"),       # Monsanto, not the SPAC holding MON today
        ("LEHMQ", "2005-06-01", "Money"),     # Lehman Brothers
        ("ENRNQ", "2000-06-01", "Money"),     # Enron's EDGAR SIC is 6200, a trading house
        ("G", "2000-06-01", "Manuf"),         # Gillette (SIC 3420 razors), not Genpact
        ("X", "2000-06-01", "Enrgy"),         # USX: the documented latest-SIC artefact
        ("X", "2005-06-01", "Manuf"),         # United States Steel's own filer
    ],
)
def test_vendored_known_labels(vendored, symbol, on, code):
    assert vendored.sector_of(symbol, D(on)) == code


def test_vendored_cosk_oil_names_land_together(vendored):
    """The 2026-10-17 motivating book: its refiners and producers must share one bucket."""
    on = D("2026-10-16")
    oil = ["APA", "CVX", "DVN", "EOG", "FANG", "OXY", "XOM", "MPC", "PSX", "VLO", "HAL"]
    assert {vendored.sector_of(s, on) for s in oil} == {"Enrgy"}


def test_vendored_coverage_is_high_every_year(vendored, universe):
    sp = [iv for iv in universe if iv.index_id == "SP500"]
    from seer_engine import dates

    sessions = dates.sessions(D("1996-01-02"), D("2026-09-30"))
    total, mix, _ = cmd.tally(sp, vendored, sessions)
    for year, n in total.items():
        assert mix[year].get(sectors.UNKNOWN, 0) / n < 0.02, year

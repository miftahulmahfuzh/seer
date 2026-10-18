"""The per-class csv: closed quarters, the instance download against a fake Archives, the
filing selection, cache -> rows, the csv's invariants and the CLI wiring (no network)."""

from __future__ import annotations

import argparse
import gzip
import json
from datetime import date

import pytest

from seer_engine import cik as c
from seer_engine import membership as m
from seer_engine.commands import shares as shares_cmd
from seer_engine.shares import classes, edgar_index, fetch, history, instance

from test_shares_instance import META_2014

D = date.fromisoformat
META = "0001326801"
ACC = "0001326801-14-000032"
BASE = "https://www.sec.gov/Archives/edgar/data/1326801/000132680114000032/"


def _ref(cik=META, filed="2014-07-24", acc=ACC, form="10-Q", path="edgar/data/1326801/0001326801-14-000032.txt"):
    return edgar_index.FilingRef(cik, D(filed), form, acc, "FACEBOOK INC", path)


# --- quarters ---------------------------------------------------------------------------------


def test_only_closed_quarters_are_listed():
    qs = edgar_index.closed_quarters(D("2009-01-01"), D("2026-10-18"))
    assert qs[0] == (2009, 1) and qs[-1] == (2026, 3) and len(qs) == 71
    # Inside the grace week the quarter just ended still counts as open.
    assert edgar_index.closed_quarters(D("2009-01-01"), D("2026-10-03"))[-1] == (2026, 2)
    assert edgar_index.closed_quarters(D("2026-07-01"), D("2026-07-05")) == []
    assert edgar_index.quarter_end(2024, 1) == D("2024-03-31")
    assert edgar_index.quarter_end(2024, 4) == D("2024-12-31")


# --- download against a fake Archives -----------------------------------------------------------


class _Resp:
    def __init__(self, status: int, body: bytes = b"") -> None:
        self.status_code = status
        self.content = body

    def iter_content(self, chunk_size: int = 65536):
        yield self.content

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _Session:
    """Answers from a url -> (status, body) map; anything else is a 404. Records every url."""

    def __init__(self, routes: dict[str, tuple[int, bytes]], calls: list[str]) -> None:
        self.routes = routes
        self.calls = calls

    def get(self, url, timeout=None, stream=False):
        self.calls.append(url)
        status, body = self.routes.get(url, (404, b""))
        return _Resp(status, body)


def _archive(routes, calls):
    return fetch.Archive("tests@example.com", pacer=fetch.Pacer(0.0),
                         session_factory=lambda: _Session(routes, calls), sleep=lambda s: None)


def _listing(*names: str) -> bytes:
    return json.dumps({"directory": {"item": [{"name": n} for n in names]}}).encode()


def test_filing_dir_is_the_accession_folder():
    assert fetch.filing_dir(_ref()) == "edgar/data/1326801/000132680114000032/"


def test_instances_are_fetched_parsed_cached_and_not_asked_again(tmp_path):
    routes = {
        BASE + "index.json": (200, _listing("fb-20140630.xml", "fb-20140630.xsd", "fb-20140630_pre.xml")),
        BASE + "fb-20140630.xml": (200, META_2014),
    }
    calls: list[str] = []
    ref = _ref()
    t = fetch.fetch_instances(_archive(routes, calls), tmp_path, [ref, ref], workers=2)
    assert (t.wanted, t.fetched, t.missing, t.failed) == (1, 1, 0, [])
    assert calls == [BASE + "index.json", BASE + "fb-20140630.xml"]
    name, facts = fetch.read_instance(fetch.instance_path(tmp_path, META, ACC))
    assert name == "fb-20140630.xml" and tuple(instance.parse(META_2014)) == facts
    # Resumable: a second run asks nothing.
    calls.clear()
    t = fetch.fetch_instances(_archive(routes, calls), tmp_path, [ref])
    assert (t.cached, t.fetched, calls) == (1, 0, [])


def test_a_filing_without_an_instance_is_marked_with_its_reason(tmp_path):
    calls: list[str] = []
    no_xbrl = _ref(acc="0001326801-12-000001", path="edgar/data/1326801/0001326801-12-000001.txt")
    gone = _ref(acc="0001326801-12-000002", path="edgar/data/1326801/0001326801-12-000002.txt")
    routes = {
        "https://www.sec.gov/Archives/edgar/data/1326801/000132680112000001/index.json":
            (200, _listing("d123.htm", "FilingSummary.xml")),
    }
    t = fetch.fetch_instances(_archive(routes, calls), tmp_path, [no_xbrl, gone], workers=1)
    assert (t.fetched, t.missing) == (0, 2)
    assert fetch.read_missing(fetch.instance_missing_path(tmp_path, META, no_xbrl.accession)) == "no XBRL instance"
    assert fetch.read_missing(fetch.instance_missing_path(tmp_path, META, gone.accession)) == "no filing index"


def test_a_joint_filing_is_fetched_once_and_cached_for_each_filer(tmp_path):
    routes = {
        BASE + "index.json": (200, _listing("fb-20140630.xml", "fb-20140630.xsd")),
        BASE + "fb-20140630.xml": (200, META_2014),
    }
    calls: list[str] = []
    twin = _ref(cik="0000000002")
    t = fetch.fetch_instances(_archive(routes, calls), tmp_path, [_ref(), twin], workers=1)
    assert t.fetched == 1 and len(calls) == 2
    assert fetch.instance_path(tmp_path, "0000000002", ACC).exists()


def test_a_server_error_that_outlasts_the_retries_is_a_failure_not_a_marker(tmp_path):
    routes = {BASE + "index.json": (500, b"")}
    t = fetch.fetch_instances(_archive(routes, []), tmp_path, [_ref()], workers=1)
    assert len(t.failed) == 1 and t.missing == 0
    assert not fetch.instance_missing_path(tmp_path, META, ACC).exists()


def test_a_wrong_version_cache_file_is_refused(tmp_path):
    p = tmp_path / "x.json.gz"
    p.write_bytes(gzip.compress(b'{"version": 0, "facts": []}'))
    with pytest.raises(instance.InstanceError, match="version"):
        fetch.read_instance(p)


# --- selection --------------------------------------------------------------------------------


def _tenure(symbol, cik, start, end=None):
    return c.CikRow(symbol, cik, D(start), D(end) if end else None, "X", "manual", "n")


def test_member_windows_merge_the_sp500_and_the_nasdaq_100():
    ivs = [m.Interval("AAA", "SP500", D("2012-06-01"), D("2014-01-01"), "AAA"),
           m.Interval("AAA", "NDX", D("2015-06-01"), None, "AAA"),
           m.Interval("BBB", "NDX", D("2013-01-01"), None, "BBB"),
           m.Interval("OLD", "SP500", D("2001-01-01"), D("2005-01-01"), "OLD")]
    index = {"AAA": (_tenure("AAA", "0000000001", "1990-01-01"),),
             "BBB": (_tenure("BBB", "0000000002", "1990-01-01"),),
             "OLD": (_tenure("OLD", "0000000003", "1990-01-01"),)}
    wins = classes.member_windows(ivs, index, end=D("2026-09-30"))
    assert list(wins) == ["0000000001", "0000000002"]  # NDX-only filers too; none before 2009
    a = wins["0000000001"]
    assert (a.start, a.end) == (D("2011-04-28"), D("2026-09-30"))
    assert wins["0000000002"].start == D("2011-11-28")


def _fundamentals(tmp_path, rows):
    p = tmp_path / "fundamentals.csv"
    head = "symbol,taxonomy,tag,unit,period_start,period_end,val,accn,form,fy,fp,filed\n"
    p.write_text(head + "".join(
        f"{s},dei,{t},shares,,{end},{v},{a},10-Q,2014,Q2,{f}\n" for s, t, end, v, a, f in rows
    ))
    return p


def test_companyfacts_cover_accessions_and_multi_value_filers(tmp_path):
    index = {"AAA": (_tenure("AAA", "0000000001", "1990-01-01"),),
             "CCC": (_tenure("CCC", "0000000003", "1990-01-01"),)}
    p = _fundamentals(tmp_path, [
        ("AAA", "EntityCommonStockSharesOutstanding", "2014-07-20", "100.0", "0000000001-14-000001", "2014-07-25"),
        ("AAA", "WeightedAverageNumberOfSharesOutstandingBasic", "2014-06-30", "90.0", "0000000001-14-000002", "2014-07-25"),
        ("CCC", "EntityCommonStockSharesOutstanding", "2014-07-20", "70.0", "0000000003-14-000001", "2014-07-25"),
        ("CCC", "EntityCommonStockSharesOutstanding", "2014-07-20", "30.0", "0000000003-14-000001", "2014-07-25"),
        ("CCC", "EntityCommonStockSharesOutstanding", "2014-10-20", "0.0", "0000000003-14-000009", "2014-10-25"),
    ])
    got = classes.read_companyfacts(p, index)
    assert got.dei_accessions == frozenset({"0000000001-14-000001", "0000000003-14-000001"})
    assert got.multi_value_ciks == frozenset({"0000000003"})


def test_select_wants_uncounted_filings_and_every_filing_of_a_multi_class_filer():
    wins = {k: edgar_index.Window(k, D("2011-01-01"), D("2026-09-30"), ("X",))
            for k in ("0000000001", "0000000003")}
    counted = _ref(cik="0000000001", acc="0000000001-14-000001")
    uncounted = _ref(cik="0000000001", acc="0000000001-14-000005")
    multi = _ref(cik="0000000003", acc="0000000003-14-000001")
    outside = _ref(cik="0000000009", acc="0000000009-14-000001")
    facts = classes.CompanyFacts(frozenset({counted.accession, multi.accession}), frozenset())
    got = classes.select([counted, uncounted, multi, outside], wins, facts, frozenset({"0000000003"}))
    assert got == [uncounted, multi]


def test_cover_rows_with_classes_mark_a_multi_class_filer():
    row = history.ShareRow("0000000003", D("2009-05-01"), "0000000003-09-000001", "CCC", D("2009-04-20"),
                           "10-Q", 100, (("Class A", 70), ("Class B", 30)), (), "")
    single = history.ShareRow("0000000001", D("2009-05-01"), "0000000001-09-000001", "AAA", D("2009-04-20"),
                              "10-Q", 100, (), (), "")
    assert classes.cover_multi_class_ciks([row, single]) == frozenset({"0000000003"})


# --- cache -> rows -> csv -------------------------------------------------------------------------


def _cache_meta(tmp_path, ref):
    path = fetch.instance_path(tmp_path, ref.cik, ref.accession)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(fetch.instance_blob("fb-20140630.xml", instance.parse(META_2014)))


def test_build_rows_reads_meta_2014_as_the_exit_criterion_says(tmp_path):
    ref = _ref()
    _cache_meta(tmp_path, ref)
    missing = _ref(acc="0001326801-14-000040", path="edgar/data/1326801/0001326801-14-000040.txt")
    fetch.instance_missing_path(tmp_path, META, missing.accession).write_text("no XBRL instance\n")
    never = _ref(acc="0001326801-14-000050", path="edgar/data/1326801/0001326801-14-000050.txt")
    tenures = {META: [_tenure("FB", META, "2012-05-18", "2022-06-09"), _tenure("META", META, "2022-06-09")]}
    built = classes.build_rows(tmp_path, [ref, missing, never, ref], tenures)
    assert built.rows == [classes.ClassRow(
        cik=META, symbol="FB", filed=D("2014-07-24"), as_of=D("2014-07-22"), form="10-Q",
        accession=ACC, shares=2600051591,
        classes=(("CommonClassAMember", 2015048077), ("CommonClassBMember", 585003514)),
        tagged_total=False,
    )]
    assert built.skipped == {"on EDGAR without a count: no XBRL instance": 1, "not downloaded": 1}
    out = tmp_path / "data" / classes.CLASSES_FILE
    assert classes.write_rows(out, built.rows) == 1
    assert out.read_text() == (
        "cik,symbol,filed,as_of,form,accession,shares,classes,tagged_total\n"
        "0001326801,FB,2014-07-24,2014-07-22,10-Q,0001326801-14-000032,2600051591,"
        "CommonClassAMember=2015048077;CommonClassBMember=585003514,false\n"
    )
    assert classes.load_rows(out) == built.rows


def test_a_row_too_far_from_its_filing_date_is_dropped_not_written(tmp_path):
    late = _ref(filed="2015-06-01")  # 314 days after the 2014-07-22 count
    _cache_meta(tmp_path, late)
    built = classes.build_rows(tmp_path, [late], {})
    assert built.rows == [] and list(built.skipped) == ["dropped: as_of N too far from filed N"]


def _row(**kw):
    base = dict(cik=META, symbol="FB", filed=D("2014-07-24"), as_of=D("2014-07-22"), form="10-Q",
                accession=ACC, shares=300, classes=(("CommonClassAMember", 200), ("CommonClassBMember", 100)),
                tagged_total=False)
    base.update(kw)
    return classes.ClassRow(**base)


def test_csv_invariants():
    classes.check_rows([_row(), _row(accession="0001326801-14-000040", filed=D("2014-10-30"),
                                     as_of=D("2014-10-25"), shares=301, tagged_total=True)])
    with pytest.raises(classes.ClassesError, match="no rows"):
        classes.check_rows([])
    with pytest.raises(classes.ClassesError, match="sorted"):
        classes.check_rows([_row(filed=D("2014-10-30"), as_of=D("2014-10-25"),
                                 accession="0001326801-14-000040"), _row()])
    with pytest.raises(classes.ClassesError, match="duplicate"):
        classes.check_rows([_row(), _row()])
    with pytest.raises(classes.ClassesError, match="classes sum"):
        classes.check_rows([_row(shares=301)])
    with pytest.raises(classes.ClassesError, match="tagged total"):
        classes.check_rows([_row(shares=400, tagged_total=True)])
    with pytest.raises(classes.ClassesError, match="needs its classes"):
        classes.check_rows([_row(classes=(), tagged_total=True)])
    with pytest.raises(classes.ClassesError, match="before"):
        classes.check_rows([_row(filed=D("2008-12-31"), as_of=D("2008-12-20"))])
    with pytest.raises(classes.ClassesError, match="sorted by member"):
        classes.check_rows([_row(classes=(("CommonClassBMember", 100), ("CommonClassAMember", 200)))])
    classes.check_rows([_row(classes=(("CommonClassAMember", 300),))])  # one class is a fact too


def test_load_rows_refuses_a_bad_header_or_flag(tmp_path):
    p = tmp_path / classes.CLASSES_FILE
    p.write_text("cik,symbol\n")
    with pytest.raises(classes.ClassesError, match="header"):
        classes.load_rows(p)
    p.write_text(",".join(classes.HEADER) + "\n"
                 "0001326801,FB,2014-07-24,2014-07-22,10-Q,0001326801-14-000032,300,,yes\n")
    with pytest.raises(classes.ClassesError, match="tagged_total"):
        classes.load_rows(p)


# --- CLI ----------------------------------------------------------------------------------------


def test_the_shares_command_has_both_class_actions():
    p = argparse.ArgumentParser()
    shares_cmd.add_arguments(p)
    a = p.parse_args(["download-classes", "--fundamentals", "/x/fundamentals.csv", "--cik", "1326801",
                      "--through", "2026-10-18", "--limit", "5"])
    assert (a.action, a.cik, a.through, a.limit) == ("download-classes", ["1326801"], D("2026-10-18"), 5)
    b = p.parse_args(["build-classes"])
    assert b.action == "build-classes" and b.out == classes.DATA_DIR / classes.CLASSES_FILE
    p.format_help()

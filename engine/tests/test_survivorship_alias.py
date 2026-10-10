"""Alias fill: the EODHD client's by-code endpoints (fake transport), candidate codes, the
series test, the fetch (fake client), the alias series as phase 1's second source, the report and
the command. No network."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import date, timedelta

import pytest
import requests

from seer_engine import eodhd, research
from seer_engine import survivorship_alias as sa
from seer_engine.commands import survivorship_store as cmd
import test_research_store as rs
from test_dividend_announcements import FakeTransport, Resp, client

IV = ((date(2000, 1, 3), date(2002, 1, 2)),)


def weekdays(start, end):
    out, d = [], start
    while d <= end:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def eod_rows(start, end, close=10.0):
    return [
        {"date": d.isoformat(), "open": close, "high": close, "low": close, "close": close,
         "adjusted_close": close, "volume": 1000}
        for d in weekdays(start, end)
    ]


@dataclass(frozen=True)
class FakeResult:
    action: str
    reason: str


def fake_clean(series, intervals):
    """Stands in for ``sa.phase1_clean``: kept when the series has bars."""
    return FakeResult("kept", "clean") if series.bars else FakeResult("dropped", "no rows")


def L(code, name="X Corp", kind="Common Stock", delisted=True):
    return sa.Listing(code, name, kind, "NYSE", delisted)


def sources(listings, names=None, aliases=None, hints=None):
    return sa.Sources(
        listings=sa.Listings.of(listings),
        names={k: tuple(v) for k, v in (names or {}).items()},
        aliases={k: frozenset(v) for k, v in (aliases or {}).items()},
        hints={k: tuple(v) for k, v in (hints or {}).items()},
    )


# ---- client --------------------------------------------------------------------------------


def test_exchange_code_is_verbatim_and_refuses_store_symbols():
    assert eodhd.exchange_code("DELL_old") == "DELL_old.US"
    assert eodhd.exchange_code(" BRK-B ") == "BRK-B.US"
    with pytest.raises(ValueError):
        eodhd.exchange_code("BRK.B")
    with pytest.raises(ValueError):
        eodhd.exchange_code("")


def test_eod_splits_and_dividends_by_code_hit_their_endpoints():
    t = FakeTransport(
        Resp(200, [{"date": "2000-01-03", "close": 1.0}]),
        Resp(200, [{"date": "1999-03-01", "split": "2.000000/1.000000"}]),
        Resp(200, []),
        Resp(404, text="Ticker Not Found"),
    )
    c = client(t)
    assert c.eod("DELL_old") == [{"date": "2000-01-03", "close": 1.0}]
    assert c.splits("DELL_old") == [{"date": "1999-03-01", "split": "2.000000/1.000000"}]
    assert c.dividends_by_code("DELL_old") == []
    assert c.eod("GONE_old") is None
    (u1, p1), (u2, p2), (u3, p3), (u4, _) = t.calls
    assert u1.endswith("/eod/DELL_old.US") and p1["period"] == "d" and p1["from"] == "1993-01-01"
    assert u2.endswith("/splits/DELL_old.US") and p2["from"] == "1990-01-01"
    assert u3.endswith("/div/DELL_old.US")
    assert u4.endswith("/eod/GONE_old.US")
    assert all(p["api_token"] == "secret-token" and p["fmt"] == "json" for _, p in t.calls)


def test_eod_retries_and_never_leaks_the_token():
    t = FakeTransport(Resp(503), requests.ConnectionError("down"), Resp(200, []))
    assert client(t).eod("X_old") == []
    assert len(t.calls) == 3
    t = FakeTransport(Resp(403, text="Forbidden for api_token=secret-token"))
    with pytest.raises(eodhd.EodhdError) as exc:
        client(t).splits("X_old")
    assert "secret-token" not in str(exc.value)
    t = FakeTransport(Resp(200, {"message": "bad secret-token"}))
    with pytest.raises(eodhd.EodhdError) as exc:
        client(t).eod("X_old")
    assert "secret-token" not in str(exc.value) and "price list" in str(exc.value)


def test_dividends_by_store_symbol_is_unchanged():
    t = FakeTransport(Resp(200, []))
    assert client(t).dividends("BRK.B") == []
    assert t.calls[0][0].endswith("/div/BRK-B.US")
    assert "period" not in t.calls[0][1]


# ---- names and codes -----------------------------------------------------------------------


def test_code_root_strips_the_vendor_suffixes():
    assert sa.code_root("DELL_old") == "DELL"
    assert sa.code_root("AT_old1") == "AT"
    assert sa.code_root("TRW1") == "TRW"
    assert sa.code_root("MCWEQ") == "MCWEQ"
    assert sa.code_root("BRK-B") == "BRK-B"


def test_normalize_name_ignores_legal_forms_and_state_tags():
    assert sa.normalize_name("DOW CHEMICAL CO /DE/") == "DOW CHEMICAL"
    assert sa.normalize_name("The Dow Chemical Company") == "DOW CHEMICAL"
    assert sa.normalize_name("AT&T Inc.") == "AT T"
    assert sa.normalize_name("Inc.") == ""


def test_load_listings_skips_funds_and_prefers_the_delisted_row(tmp_path):
    (tmp_path / sa.DELISTED_FILE).write_text(json.dumps([
        {"Code": "DELL_old", "Name": "Dell Inc", "Type": "Common Stock", "Exchange": "NASDAQ"},
        {"Code": "PWER_old", "Name": "Power One Inc", "Type": "ETF", "Exchange": "NASDAQ"},
        {"Code": "ZZFUND", "Name": "Some Fund", "Type": "FUND", "Exchange": "PINK"},
        {"Code": "CHK", "Name": "Chesapeake Energy Corporation", "Type": "Common Stock", "Exchange": "NASDAQ"},
    ]))
    (tmp_path / sa.LIVE_FILE).write_text(json.dumps([
        {"Code": "DELL", "Name": "Dell Technologies Inc", "Type": "Common Stock", "Exchange": "NYSE"},
        {"Code": "CHK", "Name": "Somebody Else", "Type": "Common Stock", "Exchange": "NYSE"},
    ]))
    listings = sa.load_listings(tmp_path)
    assert set(listings.by_code) == {"DELL_old", "PWER_old", "CHK", "DELL"}
    assert listings.by_code["CHK"].delisted and listings.by_code["CHK"].name.startswith("Chesapeake")
    assert listings.by_root["DELL"] == ("DELL", "DELL_old")


def test_candidates_rank_by_match_kind_and_never_repeat_the_store_code():
    src = sources(
        [L("DELL", "Dell Technologies Inc", delisted=False), L("DELL_old", "Dell Inc"), L("DELL1"),
         L("MCWEQ", "WorldCom, Inc"), L("WCO", "Wco Holdings"),
         L("GFS", "Globalfoundries Inc"), L("GFSA", "Giant Food Inc"),
         L("ARNC", "Arconic"), L("ARNC_old", "Arconic Old"),
         L("AT_old"), L("AT_old1"), L("AT_old2"), L("AT1"), L("AT2")],
        names={"DELL": ["DELL INC"]},
        aliases={"HWM": {"ARNC"}},
        hints={"WCOEQ": ["MCWEQ"]},
    )
    assert [(c.code, c.matched_by) for c in sa.candidates("DELL", src)] == [
        ("DELL_old", "name"), ("DELL1", "code-variant")]
    assert [(c.code, c.matched_by) for c in sa.candidates("WCOEQ", src)] == [
        ("MCWEQ", "hint"), ("WCO", "bankruptcy")]
    assert [(c.code, c.matched_by) for c in sa.candidates("GFS.A", src)] == [
        ("GFS", "class"), ("GFSA", "class")]
    assert [(c.code, c.matched_by) for c in sa.candidates("HWM", src)] == [
        ("ARNC", "alias"), ("ARNC_old", "alias")]
    at = sa.candidates("AT", src)
    assert len(at) == sa.MAX_CANDIDATES and all(c.matched_by == "code-variant" for c in at)
    assert sa.candidates("NOPE", src) == ()


def test_a_hint_for_a_code_not_in_the_lists_is_not_a_candidate():
    src = sources([L("LEH")], hints={"LEHMQ": ["LEH", "NOTLISTED"]})
    assert [c.code for c in sa.candidates("LEHMQ", src)] == ["LEH"]


# ---- the series test -----------------------------------------------------------------------


def test_member_closes_keep_only_member_days_inside_the_dev_window():
    rows = eod_rows(date(1999, 12, 27), date(2002, 1, 4))
    closes = sa.member_closes(rows, IV)
    assert min(closes) == date(2000, 1, 3) and max(closes) == date(2002, 1, 1)  # 2002-01-02 is the exclusive end
    open_ended = sa.member_closes(eod_rows(date(2015, 10, 1), date(2015, 10, 30)), ((date(2015, 1, 2), None),))
    assert max(open_ended) == research.DEV_END  # clipped to the dev window
    assert sa.member_closes(None, IV) == {}


def probe(rows, splits=()):
    return {"eod": rows, "splits": list(splits)}


CANDS = (sa.Candidate("A_old", "A Inc", "code-variant"), sa.Candidate("A1", "A One", "code-variant"))


def test_choose_without_candidates_or_overlap_says_why():
    r = sa.choose("A", (), {}, IV, clean=fake_clean)
    assert not r.accepted and r.reason.startswith("no candidate code")
    r = sa.choose("A", CANDS, {"A_old": probe(eod_rows(date(2010, 1, 4), date(2011, 1, 4)))}, IV, clean=fake_clean)
    assert not r.accepted and "A_old has 0 rows on member days" in r.reason and "A1 not fetched" in r.reason


def test_choose_needs_splits_and_phase_one_cleaning():
    rows = eod_rows(date(2000, 1, 3), date(2001, 12, 31))
    r = sa.choose("A", CANDS[:1], {"A_old": {"eod": rows}}, IV, clean=fake_clean)
    assert not r.accepted and "splits not fetched" in r.reason
    r = sa.choose("A", CANDS[:1], {"A_old": probe(rows)}, IV, clean=lambda *a: FakeResult("dropped", "splice"))
    assert not r.accepted and "dropped (splice)" in r.reason


def test_choose_accepts_the_single_fit():
    rows = eod_rows(date(2000, 1, 3), date(2001, 12, 31))
    r = sa.choose("A", CANDS, {"A_old": probe(rows), "A1": probe(eod_rows(date(2012, 1, 2), date(2013, 1, 2)))}, IV, clean=fake_clean)
    assert r.accepted and r.code == "A_old" and r.matched_by == "code-variant"


def test_two_different_fitting_series_are_ambiguous_unless_one_is_named():
    a = eod_rows(date(2000, 1, 3), date(2001, 12, 31), close=10.0)
    b = eod_rows(date(2000, 1, 3), date(2001, 12, 31), close=50.0)
    r = sa.choose("A", CANDS, {"A_old": probe(a), "A1": probe(b)}, IV, clean=fake_clean)
    assert not r.accepted and r.code is None and r.reason.startswith("ambiguous")
    named = (sa.Candidate("GM_old", "General Motors Corp", "hint"), sa.Candidate("MTL", "Mechel", "bankruptcy"))
    r = sa.choose("MTLQQ", named, {"GM_old": probe(a), "MTL": probe(b)}, IV, clean=fake_clean)
    assert r.accepted and r.code == "GM_old" and "preferred over MTL" in r.reason


def test_one_company_under_two_codes_is_not_ambiguous():
    long = eod_rows(date(2000, 1, 3), date(2001, 12, 31))
    short = eod_rows(date(2000, 1, 3), date(2001, 6, 29))
    r = sa.choose("A", CANDS, {"A_old": probe(short), "A1": probe(long)}, IV, clean=fake_clean)
    assert r.accepted and r.code == "A1" and "same series as A_old" in r.reason


# ---- fetch ---------------------------------------------------------------------------------


class FakeClient:
    def __init__(self, eod, splits=None, divs=None, fail=()):
        self.eod_rows, self.split_rows, self.div_rows, self.fail = eod, splits or {}, divs or {}, set(fail)
        self.log = []

    def eod(self, code):
        self.log.append(("eod", code))
        if code in self.fail:
            raise eodhd.EodhdError(f"HTTP 500 for {code}.US")
        return self.eod_rows.get(code)

    def splits(self, code):
        self.log.append(("splits", code))
        return self.split_rows.get(code, [])

    def dividends_by_code(self, code):
        self.log.append(("div", code))
        return self.div_rows.get(code, [])


def fetch_setup():
    src = sources([L("AAA_old", "Aaa Inc"), L("AAA1", "Aaa One")])
    rows = eod_rows(date(2000, 1, 3), date(2001, 12, 31))
    fake = FakeClient({"AAA_old": rows, "AAA1": eod_rows(date(2010, 1, 4), date(2010, 6, 30))},
                      divs={"AAA_old": [{"date": "2000-06-01", "value": 0.1}]})
    return src, fake, rows


def test_fetch_probes_candidates_and_writes_the_accepted_alias(tmp_path):
    src, fake, rows = fetch_setup()
    stats = sa.fetch(fake, tmp_path, ["AAA"], sources=src, by_symbol={"AAA": IV}, clean=fake_clean)
    # both are code variants, ranked by code: "AAA1" < "AAA_old"
    assert fake.log == [("eod", "AAA1"), ("eod", "AAA_old"), ("splits", "AAA_old"), ("div", "AAA_old")]
    assert (stats.calls, stats.accepted, stats.failed) == (4, 1, [])
    doc = sa.read_alias(tmp_path, "AAA")
    assert doc["code"] == "AAA_old" and doc["eod"] == rows and doc["splits"] == []
    assert doc["dividends"] == [{"date": "2000-06-01", "value": 0.1}] and doc["matched_by"] == "code-variant"
    assert "splits" not in sa.read_probe(tmp_path, "AAA1")  # no member-day rows: no splits call

    fake.log.clear()
    again = sa.fetch(fake, tmp_path, ["AAA"], sources=src, by_symbol={"AAA": IV}, clean=fake_clean)
    assert fake.log == [] and again.skipped == 1
    sa.alias_path(tmp_path, "AAA").unlink()
    sa.fetch(fake, tmp_path, ["AAA"], sources=src, by_symbol={"AAA": IV}, clean=fake_clean)
    assert fake.log == [("div", "AAA_old")]  # probes reused, only the dividends call repeats
    fake.log.clear()
    sa.fetch(fake, tmp_path, ["AAA"], sources=src, by_symbol={"AAA": IV}, clean=fake_clean, refetch=True)
    assert ("eod", "AAA_old") in fake.log and ("eod", "AAA1") in fake.log


def test_fetch_records_a_failure_and_goes_on(tmp_path):
    src, fake, _ = fetch_setup()
    fake.fail = {"AAA_old"}
    stats = sa.fetch(fake, tmp_path, ["AAA"], sources=src, by_symbol={"AAA": IV}, clean=fake_clean)
    assert stats.failed == ["AAA"] and sa.read_alias(tmp_path, "AAA") is None


# ---- the second source and the report ------------------------------------------------------


@dataclass(frozen=True)
class Chosen:
    """Stands in for phase 1's ``Cleaned`` as ``BuildPlan.cleaned`` holds it."""

    action: str
    source: str


def test_alias_sources_offer_only_fetched_accepted_codes_and_the_report_follows_the_build(tmp_path):
    src, fake, rows = fetch_setup()
    sa.fetch(fake, tmp_path, ["AAA"], sources=src, by_symbol={"AAA": IV}, clean=fake_clean)
    by_symbol = {"AAA": IV, "CCC": IV}
    res = sa.resolve(["AAA", "CCC"], sources=src, alias_dir=tmp_path, by_symbol=by_symbol, clean=fake_clean)
    extra = sa.alias_sources(tmp_path, res)
    assert list(extra) == ["AAA"]
    (series,) = extra["AAA"]
    assert (series.symbol, series.source, series.code) == ("AAA", sa.ALIAS_SOURCE, "AAA_old.US")
    assert len(series.bars) == len(rows) and series.splits == ()
    assert [d.ex_date for d in series.dividends] == [date(2000, 6, 1)]

    taken = {"AAA": Chosen("kept", sa.ALIAS_SOURCE), "CCC": Chosen("dropped", "eodhd")}
    report = sa.report_rows(res, taken, alias_dir=tmp_path, by_symbol=by_symbol, clean=fake_clean)
    assert [(r.symbol, r.code, r.accepted) for r in report] == [("AAA", "AAA_old", True), ("CCC", "", False)]
    assert report[0].reason.startswith("kept: ") and report[1].reason.startswith("no candidate code")

    kept_original = {"AAA": Chosen("kept", "eodhd")}
    (row,) = sa.report_rows(res[:1], kept_original, alias_dir=tmp_path, by_symbol=by_symbol, clean=fake_clean)
    assert not row.accepted and row.reason.startswith("not used")

    sa.alias_path(tmp_path, "AAA").unlink()
    assert sa.alias_sources(tmp_path, res) == {}
    (row,) = sa.report_rows(res[:1], {}, alias_dir=tmp_path, by_symbol=by_symbol, clean=fake_clean)
    assert not row.accepted and "--fetch-aliases" in row.reason


def test_report_text_quotes_names_with_commas():
    text = sa.report_text([sa.ReportRow("WCOEQ", "MCWEQ", "WorldCom, Inc", "hint", True, "kept: 1000 rows")])
    assert text == (
        "symbol,code,name,matched_by,accepted,reason\n"
        'WCOEQ,MCWEQ,"WorldCom, Inc",hint,yes,kept: 1000 rows\n'
    )


# ---- the command (phase 1's real cleaning on a tiny cache) ---------------------------------


@pytest.fixture
def members(tmp_path):
    return rs.members_dir.__wrapped__(tmp_path)


def command_cache(tmp_path):
    cache = tmp_path / "eodhd"
    for sub in ("eod", "splits", "dividends"):
        (cache / sub).mkdir(parents=True)
    (cache / "eod" / "GONE.json").write_text("null")
    (cache / "splits" / "GONE.json").write_text("null")
    (cache / "dividends" / "GONE.json").write_text(json.dumps({"symbol": "GONE", "rows": None}))
    (cache / sa.DELISTED_FILE).write_text(json.dumps([
        {"Code": "GONE_old", "Name": "Gone Corp", "Type": "Common Stock", "Exchange": "NYSE"}]))
    (cache / sa.LIVE_FILE).write_text("[]")
    return cache


def cmd_args(store, cache, members, **kw):
    base = dict(cache=cache, source=store, data_dir=members, resolve_aliases=True, fetch_aliases=False,
                refetch=False, symbols=None, no_aliases=False, dry_run=False, verbose=0)
    return argparse.Namespace(**{**base, **kw})


def test_command_resolves_offline_from_cached_probes(tmp_path, members, capsys):
    store = tmp_path / "store"
    rs.build(store, members)
    cache = command_cache(tmp_path)
    rows = eod_rows(date(1997, 12, 31), date(1999, 12, 31), close=20.0)  # GONE is a member 1996..2000-01-03
    sa._write_json(sa.probe_path(cache / sa.ALIAS_DIR, "GONE_old"), {"code": "GONE_old", "eod": rows, "splits": []})
    assert cmd.run(cmd_args(store, cache, members)) == 0
    out = capsys.readouterr().out
    assert "appear under another EODHD code: 1" in out
    assert "GONE     GONE_old" in out and " yes " in out


def test_command_fetch_dry_run_makes_no_call_and_no_token_exits_2(tmp_path, members, monkeypatch, capsys):
    store = tmp_path / "store"
    rs.build(store, members)
    cache = command_cache(tmp_path)
    monkeypatch.setattr(cmd.config, "get", lambda name: "tok")

    def boom(*a, **k):
        raise AssertionError("no client in a dry run")

    monkeypatch.setattr(eodhd, "Client", boom)
    # the fixture store's unserved list is GONE and DDD (DDD has bars only after DEV_END and no
    # cache file, so it is a target with no candidate); --symbols keeps the count exact
    assert cmd.run(cmd_args(store, cache, members, fetch_aliases=True, dry_run=True, symbols="GONE")) == 0
    assert "dry run: would probe 1 codes for 1 members" in capsys.readouterr().out
    assert not (cache / sa.ALIAS_DIR).exists()

    monkeypatch.setattr(cmd.config, "get", lambda name: None)
    assert cmd.run(cmd_args(store, cache, members, fetch_aliases=True)) == 2
    assert eodhd.TOKEN_ENV in capsys.readouterr().out


def test_the_build_takes_a_fetched_alias_as_phase_ones_second_source(tmp_path, members):
    store = tmp_path / "store"
    rs.build(store, members)
    cache = command_cache(tmp_path)
    rows = eod_rows(date(1997, 12, 31), date(1999, 12, 31), close=20.0)  # GONE: member 1996..2000-01-03
    alias_dir = cache / sa.ALIAS_DIR
    sa._write_json(sa.probe_path(alias_dir, "GONE_old"), {"code": "GONE_old", "eod": rows, "splits": []})
    sa._write_json(sa.alias_path(alias_dir, "GONE"), {
        "symbol": "GONE", "code": "GONE_old", "name": "Gone Corp", "matched_by": "code-variant",
        "fetched": "2026-10-10T00:00:00+00:00", "eod": rows, "splits": [], "dividends": [],
    })
    fill = cmd.alias_fill(cmd_args(store, cache, members, resolve_aliases=False))
    assert list(fill.sources) == ["GONE"]
    plan = cmd.plan_build(store, cache, data_dir=members, extra_sources=fill.sources)
    gone = plan.cleaned["GONE"]
    assert (gone.source, gone.code) == (sa.ALIAS_SOURCE, "GONE_old.US") and gone.action in sa.USABLE_ACTIONS
    out = tmp_path / "store-sv"
    manifest = cmd.write_store(plan, out, cache, data_dir=members,
                               extra_reports={sa.REPORT_FILE: fill.report(plan)})
    assert sa.REPORT_FILE not in manifest["files"]
    report = (out / sa.REPORT_FILE).read_text(encoding="utf-8")
    assert "GONE,GONE_old,Gone Corp,code-variant,yes," in report
    assert "GONE" in research.load_store(out, data_dir=members).market.history
    assert cmd.alias_fill(cmd_args(store, cache, members, resolve_aliases=False, no_aliases=True)) is None

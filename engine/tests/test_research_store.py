"""Tests for the P7a research store (seer_engine.research), the dividends-aware yahoo
download/parse and the research_store command. No test touches the network or a database:
yfinance is an injected fake that builds yfinance-shaped ``actions=True`` frames, Frankfurter is
a fake, sleeps are recorded, and membership comes from a tiny CSV fixture (``data_dir``)."""

from __future__ import annotations

import ast
import dataclasses
import functools
import json
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from seer_engine import cli, config, db, research, yahoo
from seer_engine.backtest.benchmark import Dividend
from seer_engine.commands import research_store as research_cmd

COLS = ["Open", "High", "Low", "Close", "Adj Close", "Volume", "Dividends", "Stock Splits"]

PRE = date(1993, 1, 28)  # before STORE_START
D1 = date(1999, 1, 4)
D2 = date(1999, 1, 5)
D3 = date(2015, 10, 16)  # == DEV_END
POST = date(2015, 10, 19)  # first session after DEV_END

MEMBERS = ("AAA", "BBB", "BRK.B", "CCC", "DDD", "GONE")
SERVED = tuple(sorted(set(research.RESEARCH_ETFS) | {"AAA", "BBB", "BRK.B", "CCC"}))
REQUESTED = tuple(sorted(set(research.RESEARCH_ETFS) | set(MEMBERS)))


# ---- fakes ---------------------------------------------------------------------------------


def bar_rows(*days, base=10.0):
    return [(d, base, base + 1, base - 1, base + 0.5, 1000 + i) for i, d in enumerate(days)]


def ticker_frame(rows, divs):
    """One ticker's yfinance actions=True frame. rows: [(date, o, h, l, c, v)]; divs: {date: amount}."""
    index = pd.DatetimeIndex([pd.Timestamp(r[0]) for r in rows], name="Date")
    data = [
        [o, h, l, c, round(c * 0.9, 6), v, float(divs.get(d, 0.0)), 0.0]
        for (d, o, h, l, c, v) in rows
    ]
    return pd.DataFrame(data, index=index, columns=pd.Index(COLS, name="Price"), dtype=float)


def multi_frame(by_ticker):
    """yfinance 1.x group_by='ticker' shape: MultiIndex (Ticker, Price), NaN-filled."""
    frames = {t: ticker_frame(rows, divs) for t, (rows, divs) in by_ticker.items()}
    return pd.concat(
        list(frames.values()), axis=1, keys=list(frames), names=["Ticker", "Price"], sort=True
    )


def default_data():
    """yahoo ticker -> (rows, dividends). GONE is absent; DDD only after DEV_END."""
    data = {etf: (bar_rows(D1, D2, D3, base=50.0), {}) for etf in research.RESEARCH_ETFS}
    data["SPY"] = (bar_rows(PRE, D1, D2, D3, POST, base=100.0), {D2: 0.25, POST: 0.5})
    data["AAA"] = (bar_rows(D1, D2, D3), {D2: 2.65 / 28, D3: 0.0})
    data["BBB"] = (bar_rows(D1, D3, base=20.0), {})
    data["BRK-B"] = (bar_rows(D2, D3, base=70.123456), {})
    data["CCC"] = (bar_rows(D3, POST), {})
    data["DDD"] = (bar_rows(POST), {POST: 1.0})
    return data


class FakeYahoo:
    """Injected downloader. Ignores the date range on purpose (the store must clip)."""

    def __init__(self, data, *, rate_limits=0, missing=()):
        self.data = data
        self.rate_limits = rate_limits
        self.missing = set(missing)
        self.calls: list[tuple[list[str], date, date]] = []

    def __call__(self, tickers, start, end_exclusive):
        self.calls.append((list(tickers), start, end_exclusive))
        if self.rate_limits > 0:
            self.rate_limits -= 1
            raise yahoo.RateLimited("Too Many Requests. Rate limited.")
        by_ticker = {}
        for t in tickers:
            by_ticker[t] = ([], {}) if t in self.missing else self.data.get(t, ([], {}))
        return multi_frame(by_ticker)


def fake_fx(start, end):
    assert (start, end) == (research.FX_START, research.DEV_END)
    return [(D1, Decimal("8002")), (D2, 8010.5), (POST, Decimal("13600"))]


class Sleeps(list):
    def __call__(self, seconds):
        self.append(seconds)


@pytest.fixture
def members_dir(tmp_path):
    d = tmp_path / "members"
    d.mkdir()
    (d / "sp500_history.csv").write_text(
        "date,tickers\n"
        '1996-01-02,"AAA,BBB,GONE"\n'
        '2000-01-03,"AAA,BBB,BRK.B,CCC"\n'
        '2016-01-04,"AAA,CCC,NEW"\n',
        encoding="utf-8",
    )
    (d / "ndx_history.csv").write_text('date,tickers\n2007-02-01,"AAA,DDD"\n', encoding="utf-8")
    (d / "membership_overrides.csv").write_text("date,index_id,action,ticker,note\n", encoding="utf-8")
    (d / "ticker_aliases.csv").write_text("old,new,effective_date,note\n", encoding="utf-8")
    return d


def build(store, members_dir, *, fake=None, fetch_fx=fake_fx, sleeps=None, batch_size=40):
    return research.build_store(
        store,
        downloader=fake if fake is not None else FakeYahoo(default_data()),
        fetch_fx=fetch_fx,
        sleep=sleeps if sleeps is not None else Sleeps(),
        batch_size=batch_size,
        data_dir=members_dir,
    )


def read(store, name):
    return (store / name).read_text(encoding="utf-8")


def reseal(store):
    """Re-hash the data files into the manifest, as if the store had been built that way."""
    manifest = json.loads(read(store, research.MANIFEST_FILE))
    files = {n: research.file_sha256(store / n) for n in research.DATA_FILES}
    manifest["files"] = files
    manifest["fingerprint"] = research.fingerprint_of(files)
    (store / research.MANIFEST_FILE).write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )


# ---- constants and membership --------------------------------------------------------------


def test_constants_match_the_contract():
    assert research.DEV_END == date(2015, 10, 16)
    assert research.STORE_START == date(1993, 1, 29)
    assert research.MEMBERSHIP_START == date(1996, 1, 2)
    assert research.FX_START == date(1999, 1, 4)
    assert research.STORE_DIR == config.REPO_ROOT / "engine" / ".research"
    assert research.RESEARCH_ETFS == tuple(sorted(set(research.RESEARCH_ETFS)))
    assert len(research.RESEARCH_ETFS) == 21
    assert research.SECTOR_ETFS == ("XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY")
    assert set(research.SECTOR_ETFS) <= set(research.RESEARCH_ETFS)
    assert {"SPY", "QQQ", "BIL", "TLT", "SSO", "QLD"} <= set(research.RESEARCH_ETFS)


def test_store_dirs_are_gitignored():
    lines = (config.REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    for entry in ("engine/.research/", "engine/.research.tmp/", "engine/.research.old/"):
        assert entry in lines


def test_requested_symbols_are_etfs_and_dev_window_members(members_dir):
    assert research.requested_symbols(members_dir) == REQUESTED
    assert "NEW" not in research.requested_symbols(members_dir)


def test_research_membership_is_clipped_to_the_dev_window(members_dir):
    m = research.research_membership(members_dir)
    assert m.symbols() == tuple(sorted(MEMBERS))
    assert ("GONE", date(1996, 1, 2), date(2000, 1, 3)) in m.intervals
    assert ("BBB", date(1996, 1, 2), None) in m.intervals  # ended 2016-01-04: clipped to None
    assert ("AAA", date(1996, 1, 2), None) in m.intervals  # SP500 + NDX merged
    assert all(end is None or end <= research.DEV_END for _, _, end in m.intervals)
    assert m.members_on(date(2000, 1, 3)) == frozenset({"AAA", "BBB", "BRK.B", "CCC"})
    assert m.members_on(date(2010, 1, 4)) == frozenset({"AAA", "BBB", "BRK.B", "CCC", "DDD"})


# ---- yahoo: dividends-aware parse ----------------------------------------------------------


def test_parse_frame_actions_reads_bars_and_dividends():
    frame = multi_frame(
        {
            "AAA": (bar_rows(D1, D2), {D2: 2.65 / 28}),
            "BRK-B": (bar_rows(D1), {D1: 0.0}),
            "ZZZ": ([], {}),
        }
    )
    got = yahoo.parse_frame_actions(frame, ["AAA", "BRK-B", "ZZZ", "QQQQ"])
    assert list(got) == ["AAA", "BRK.B", "ZZZ", "QQQQ"]
    assert got["AAA"].bars == tuple(yahoo.parse_frame(frame, ["AAA", "BRK-B"])["AAA"])
    assert [b.date for b in got["AAA"].bars] == [D1, D2]
    assert got["AAA"].dividends == ((D2, Decimal("0.094643")),)
    assert got["BRK.B"].dividends == ()
    assert len(got["BRK.B"].bars) == 1
    assert got["ZZZ"] == yahoo.EMPTY_HISTORY
    assert got["QQQQ"] == yahoo.EMPTY_HISTORY


def test_parse_frame_actions_flat_frame_and_none():
    flat = ticker_frame(bar_rows(D1, D2), {D1: 0.5})
    got = yahoo.parse_frame_actions(flat, ["SPY"])
    assert got["SPY"].dividends == ((D1, Decimal("0.500000")),)
    assert len(got["SPY"].bars) == 2
    no_divs = flat.drop(columns=["Dividends"])
    assert yahoo.parse_frame_actions(no_divs, ["SPY"])["SPY"].dividends == ()
    assert yahoo.parse_frame_actions(None, ["SPY"]) == {"SPY": yahoo.EMPTY_HISTORY}


def test_download_actions_maps_tickers():
    fake = FakeYahoo(default_data())
    got = yahoo.download_actions(["brk.b", "AAA", "AAA"], D1, D2, downloader=fake)
    assert fake.calls == [(["BRK-B", "AAA"], D1, D2)]
    assert list(got) == ["BRK.B", "AAA"]
    assert got["BRK.B"].bars[0].symbol == "BRK.B"


# ---- build ---------------------------------------------------------------------------------


def test_build_writes_sorted_files_and_manifest(tmp_path, members_dir):
    store = tmp_path / "store"
    manifest = build(store, members_dir)
    assert sorted(p.name for p in store.iterdir()) == sorted(
        [*research.DATA_FILES, research.MANIFEST_FILE]
    )
    assert set(manifest) == research.MANIFEST_KEYS
    assert manifest == json.loads(read(store, research.MANIFEST_FILE))
    assert read(store, research.MANIFEST_FILE) == json.dumps(manifest, sort_keys=True, indent=2) + "\n"
    assert manifest["dev_end"] == "2015-10-16"
    assert manifest["store_start"] == "1993-01-29"
    assert manifest["symbols_requested"] == len(REQUESTED) == 27
    assert manifest["symbols_served"] == len(SERVED) == 25
    assert manifest["bar_rows"] == 71
    assert manifest["dividend_rows"] == 2
    assert manifest["fx_rows"] == 2
    assert manifest["files"] == {n: research.file_sha256(store / n) for n in research.DATA_FILES}
    assert manifest["fingerprint"] == research.fingerprint_of(manifest["files"])

    bar_lines = read(store, research.BARS_FILE).splitlines()
    assert bar_lines[0] == research.BARS_HEADER
    keys = [(line.split(",")[0], line.split(",")[1]) for line in bar_lines[1:]]
    assert keys == sorted(keys)
    assert [s for s in dict.fromkeys(k[0] for k in keys)] == list(SERVED)
    assert all(research.STORE_START.isoformat() <= d <= "2015-10-16" for _, d in keys)
    assert read(store, research.UNSERVED_FILE) == (
        "symbol,reason\n"
        f"DDD,{research.UNSERVED_REASON}\n"
        f"GONE,{research.UNSERVED_REASON}\n"
    )
    assert not (tmp_path / "store.tmp").exists()
    assert not (tmp_path / "store.old").exists()


def test_build_file_formats(tmp_path, members_dir):
    store = tmp_path / "store"
    build(store, members_dir)
    bars_text = read(store, research.BARS_FILE)
    assert "AAA,1999-01-04,10.0000,11.0000,9.0000,10.5000,1000\n" in bars_text
    assert "BRK.B,1999-01-05,70.1235,71.1235,69.1235,70.6235,1000\n" in bars_text
    assert "SPY,1993-01-28," not in bars_text  # before STORE_START
    assert "2015-10-19" not in bars_text  # after DEV_END
    assert read(store, research.DIVIDENDS_FILE) == (
        "symbol,ex_date,amount\nAAA,1999-01-05,0.094643\nSPY,1999-01-05,0.25\n"
    )
    assert read(store, research.FX_FILE) == "date,usd_idr\n1999-01-04,8002.0000\n1999-01-05,8010.5000\n"
    for name in research.DATA_FILES:
        assert "\r" not in read(store, name)


def test_build_is_deterministic_across_runs_and_batch_sizes(tmp_path, members_dir):
    a, b, c = tmp_path / "a", tmp_path / "b", tmp_path / "c"
    ma = build(a, members_dir, batch_size=40)
    mb = build(b, members_dir, batch_size=40)
    mc = build(c, members_dir, batch_size=5)
    assert ma == mb == mc
    for name in (*research.DATA_FILES, research.MANIFEST_FILE):
        assert (a / name).read_bytes() == (b / name).read_bytes() == (c / name).read_bytes()
    build(a, members_dir)  # rebuilding in place gives the same fingerprint
    assert json.loads(read(a, research.MANIFEST_FILE))["fingerprint"] == ma["fingerprint"]


def test_build_backs_off_and_retries_empties_individually(tmp_path, members_dir):
    fake = FakeYahoo(default_data(), rate_limits=1)
    sleeps = Sleeps()
    build(tmp_path / "store", members_dir, fake=fake, sleeps=sleeps)
    assert sleeps == [60.0, research.BATCH_PAUSE_S, research.BATCH_PAUSE_S]
    assert [call[0] for call in fake.calls] == [
        [yahoo.to_yahoo(s) for s in REQUESTED],
        [yahoo.to_yahoo(s) for s in REQUESTED],
        ["DDD"],
        ["GONE"],
    ]
    assert all(
        (start, end) == (research.STORE_START, research.DEV_END + timedelta(days=1))
        for _, start, end in fake.calls
    )


def test_build_aborts_on_unserved_etf_and_keeps_the_old_store(tmp_path, members_dir):
    store = tmp_path / "store"
    build(store, members_dir)
    before = {n: (store / n).read_bytes() for n in (*research.DATA_FILES, research.MANIFEST_FILE)}
    with pytest.raises(research.ResearchStoreError, match="GLD"):
        build(store, members_dir, fake=FakeYahoo(default_data(), missing={"GLD"}))
    assert {n: (store / n).read_bytes() for n in before} == before
    assert not (tmp_path / "store.tmp").exists()


def test_build_aborts_when_rate_limited_out(tmp_path, members_dir):
    store = tmp_path / "store"
    sleeps = Sleeps()
    with pytest.raises(research.ResearchStoreError, match="rate limited"):
        build(store, members_dir, fake=FakeYahoo(default_data(), rate_limits=10), sleeps=sleeps)
    assert sleeps == list(research.RATE_LIMIT_BACKOFF_S)
    assert not store.exists()
    assert not (tmp_path / "store.tmp").exists()


def test_build_rejects_bad_batch_size_and_bad_fx(tmp_path, members_dir):
    with pytest.raises(ValueError, match="batch_size"):
        build(tmp_path / "s0", members_dir, batch_size=0)

    def conflicting(start, end):
        return [(D1, Decimal("8002")), (D1, Decimal("8003"))]

    def nothing(start, end):
        return [(POST, Decimal("13600"))]

    with pytest.raises(research.ResearchStoreError, match="conflicting"):
        build(tmp_path / "s1", members_dir, fetch_fx=conflicting)
    with pytest.raises(research.ResearchStoreError, match="no USD/IDR rows"):
        build(tmp_path / "s2", members_dir, fetch_fx=nothing)
    assert not (tmp_path / "s1").exists() and not (tmp_path / "s2").exists()


# ---- load ----------------------------------------------------------------------------------


def test_load_store_round_trip(tmp_path, members_dir):
    store = tmp_path / "store"
    manifest = build(store, members_dir)
    data = research.load_store(store, data_dir=members_dir)
    assert data.fingerprint == manifest["fingerprint"]
    assert data.manifest == manifest
    assert tuple(data.market.history) == SERVED
    assert data.market.history["SPY"].dates.tolist() == [D1, D2, D3]
    assert data.market.bar("BRK.B", D2).close == Decimal("70.6235")
    assert data.market.bar("AAA", D1).volume == 1000
    assert data.market.fx == ((D1, Decimal("8002.0000")), (D2, Decimal("8010.5000")))
    assert data.dividends == {"AAA": {D2: Decimal("0.094643")}, "SPY": {D2: Decimal("0.25")}}
    assert data.spy_dividends == (Dividend(ex_date=D2, amount=Decimal("0.25")),)
    assert data.unserved == ("DDD", "GONE")
    assert data.market.membership.members_on(date(2000, 1, 3)) == frozenset(
        {"AAA", "BBB", "BRK.B", "CCC"}
    )


@pytest.mark.parametrize("name", research.DATA_FILES)
def test_load_store_rejects_a_tampered_file(tmp_path, members_dir, name):
    store = tmp_path / "store"
    build(store, members_dir)
    with (store / name).open("a", encoding="utf-8", newline="\n") as fh:
        fh.write("X\n")
    with pytest.raises(ValueError, match=f"{name}: sha256"):
        research.load_store(store, data_dir=members_dir)


def test_load_store_rejects_a_bad_fingerprint(tmp_path, members_dir):
    store = tmp_path / "store"
    build(store, members_dir)
    manifest = json.loads(read(store, research.MANIFEST_FILE))
    manifest["fingerprint"] = "0" * 64
    (store / research.MANIFEST_FILE).write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="fingerprint"):
        research.load_store(store, data_dir=members_dir)


def test_load_store_rejects_a_store_built_for_another_dev_end(tmp_path, members_dir):
    store = tmp_path / "store"
    build(store, members_dir)
    manifest = json.loads(read(store, research.MANIFEST_FILE))
    manifest["dev_end"] = "2015-12-31"
    (store / research.MANIFEST_FILE).write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="dev_end"):
        research.load_store(store, data_dir=members_dir)


@pytest.mark.parametrize(
    ("name", "old", "new"),
    [
        (research.BARS_FILE, "SPY,2015-10-16,", "SPY,2015-10-19,"),
        (research.DIVIDENDS_FILE, "SPY,1999-01-05,", "SPY,2015-10-19,"),
        (research.FX_FILE, "1999-01-05,", "2015-10-19,"),
    ],
)
def test_load_store_rejects_rows_after_dev_end(tmp_path, members_dir, name, old, new):
    store = tmp_path / "store"
    build(store, members_dir)
    text = read(store, name)
    assert text.count(old) == 1
    (store / name).write_text(text.replace(old, new), encoding="utf-8", newline="\n")
    reseal(store)  # hashes match again: only the D9 date guard can catch it
    with pytest.raises(ValueError, match="after DEV_END 2015-10-16"):
        research.load_store(store, data_dir=members_dir)


def test_load_store_rejects_a_missing_store(tmp_path):
    with pytest.raises(ValueError, match="no research store"):
        research.load_store(tmp_path / "nope")


def _imported_names(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            names.add(base)
            names |= {f"{base}.{a.name}" for a in node.names}
    return names


def test_no_neon_and_no_database_url_needed(tmp_path, members_dir, monkeypatch):
    def no_db(*args, **kwargs):
        raise AssertionError("the research store must never connect to a database")

    monkeypatch.setattr(db, "connect", no_db)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL_UNPOOLED", raising=False)
    store = tmp_path / "store"
    build(store, members_dir)
    assert research.load_store(store, data_dir=members_dir).fingerprint
    for module in (research, research_cmd):
        names = _imported_names(Path(module.__file__))
        assert not {n for n in names if n == "seer_engine.db" or n.startswith("psycopg")}, module


# ---- per-year unserved and verification ----------------------------------------------------


def test_unserved_by_year(members_dir):
    table = research.unserved_by_year(research.research_membership(members_dir), ["DDD", "GONE"])
    assert [y for y, _, _ in table] == list(range(1996, 2016))
    rows = {y: (m, u) for y, m, u in table}
    assert rows[1996] == (3, 1)  # AAA, BBB, GONE
    assert rows[2000] == (5, 1)  # GONE still a member until 2000-01-03
    assert rows[2001] == (4, 0)
    assert rows[2007] == (5, 1)  # DDD joins NDX
    assert rows[2015] == (5, 1)


def test_check_spy_sessions(tmp_path, members_dir):
    store = tmp_path / "store"
    build(store, members_dir)
    data = research.load_store(store, data_dir=members_dir)
    assert research.check_spy_sessions(data, start=D1, end=D2).ok
    full = research.check_spy_sessions(data)
    assert not full.ok
    assert full.name == "spy-sessions"
    assert "5721 NYSE sessions 1993-02-01..2015-10-16, 5718 without a SPY bar" in full.detail


def test_check_spy_dividends(tmp_path, members_dir):
    store = tmp_path / "store"
    build(store, members_dir)
    data = research.load_store(store, data_dir=members_dir)
    assert research.check_spy_dividends(data, (Dividend(D2, Decimal("0.250")),)).ok
    assert not research.check_spy_dividends(data, (Dividend(D2, Decimal("0.26")),)).ok
    assert not research.check_spy_dividends(
        data, (Dividend(D1, Decimal("0.1")), Dividend(D2, Decimal("0.25")))
    ).ok
    assert not research.check_spy_dividends(data, ()).ok


def test_check_dividend_scale(tmp_path, members_dir):
    store = tmp_path / "store"
    build(store, members_dir)
    data = research.load_store(store, data_dir=members_dir)
    good = research.check_dividend_scale(data, symbol="AAA", year=1999)
    assert good.ok and "0.094643 / close 10.5000" in good.detail
    assert not research.check_dividend_scale(data, symbol="BBB", year=1999).ok  # no dividends
    unadjusted = dataclasses.replace(data, dividends={"AAA": {D2: Decimal("2.65")}})
    assert not research.check_dividend_scale(unadjusted, symbol="AAA", year=1999).ok
    assert [c.name for c in research.run_checks(data, ())] == [
        "spy-sessions",
        "spy-dividends",
        "dividend-scale-AAPL-2012",
    ]


# ---- command -------------------------------------------------------------------------------


def test_command_verify_prints_fingerprint_and_checks(tmp_path, members_dir, capsys):
    store = tmp_path / "store"
    manifest = build(store, members_dir)
    code = cli.main(["research_store", "--verify", "--store", str(store)])
    out = capsys.readouterr().out
    assert code == 1  # the fake store fails the real-data checks
    assert f"fingerprint: {manifest['fingerprint']}" in out
    assert "symbols: 25 served of 27 requested, 2 unserved" in out
    assert "rows: 71 bars, 2 dividends, 2 fx" in out
    assert "check spy-sessions: FAIL" in out


def test_command_verify_missing_store_exits_2(tmp_path, capsys):
    assert cli.main(["research_store", "--verify", "--store", str(tmp_path / "nope")]) == 2
    assert capsys.readouterr().out == ""


def test_command_builds_the_store(tmp_path, members_dir, monkeypatch, capsys):
    fake = FakeYahoo(default_data())
    monkeypatch.setattr(
        research,
        "build_store",
        functools.partial(
            research.build_store, downloader=fake, fetch_fx=fake_fx, sleep=Sleeps(), data_dir=members_dir
        ),
    )
    store = tmp_path / "store"
    code = cli.main(["research_store", "--store", str(store), "--batch-size", "7"])
    out = capsys.readouterr().out
    assert code == 1  # built fine; the real-data checks fail on fake data
    manifest = json.loads(read(store, research.MANIFEST_FILE))
    assert f"fingerprint: {manifest['fingerprint']}" in out
    assert len(fake.calls) == 4 + 2  # ceil(27 / 7) batches + DDD and GONE individually


def test_command_dry_run_keeps_nothing(tmp_path, members_dir, monkeypatch, capsys):
    monkeypatch.setattr(
        research,
        "build_store",
        functools.partial(
            research.build_store,
            downloader=FakeYahoo(default_data()),
            fetch_fx=fake_fx,
            sleep=Sleeps(),
            data_dir=members_dir,
        ),
    )
    store = tmp_path / "store"
    cli.main(["--dry-run", "research_store", "--store", str(store)])
    out = capsys.readouterr().out
    assert "dry run: built in a temporary directory and discarded" in out
    assert not store.exists()

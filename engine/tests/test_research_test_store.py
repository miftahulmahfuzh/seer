"""Tests for the P7b test-window research store: building it, declaring its window, and the
refusal that keeps a dev store and a test store from being used for each other.

No test touches the network or a database. yfinance is an injected fake, Frankfurter is a fake,
sleeps are recorded, and membership comes from a tiny CSV fixture. Nothing here builds the real
test store: that is an operator action, taken the first time a method is promoted.

Deliberately separate from ``test_research_store.py``, which is shipped code this phase leaves
byte-identical -- in particular its ``set(manifest) == research.MANIFEST_KEYS`` assertion, which
is what forces this phase's window identity to be additive and absent on a dev build.
"""

from __future__ import annotations

import functools
import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pandas as pd
import pytest

from seer_engine import cli, config, research

COLS = ["Open", "High", "Low", "Close", "Adj Close", "Volume", "Dividends", "Stock Splits"]

D1 = date(1999, 1, 4)
D2 = date(1999, 1, 5)
D3 = date(2015, 10, 16)  # == DEV_END
POST = date(2015, 10, 19)  # == TEST_WINDOW_START, the first session after DEV_END
TEST_END = date(2016, 1, 4)  # an NYSE session, and the membership fixture's third snapshot


# ---- fakes ---------------------------------------------------------------------------------


def bar_rows(*days, base=10.0):
    return [(d, base, base + 1, base - 1, base + 0.5, 1000 + i) for i, d in enumerate(days)]


def ticker_frame(rows, divs):
    index = pd.DatetimeIndex([pd.Timestamp(r[0]) for r in rows], name="Date")
    data = [
        [o, h, lo, c, round(c * 0.9, 6), v, float(divs.get(d, 0.0)), 0.0]
        for (d, o, h, lo, c, v) in rows
    ]
    return pd.DataFrame(data, index=index, columns=pd.Index(COLS, name="Price"), dtype=float)


def multi_frame(by_ticker):
    frames = {t: ticker_frame(rows, divs) for t, (rows, divs) in by_ticker.items()}
    return pd.concat(
        list(frames.values()), axis=1, keys=list(frames), names=["Ticker", "Price"], sort=True
    )


def default_data():
    """yahoo ticker -> (rows, dividends). GONE and NEW are absent; DDD only after DEV_END."""
    data = {etf: (bar_rows(D1, D2, D3, TEST_END, base=50.0), {}) for etf in research.RESEARCH_ETFS}
    data["SPY"] = (bar_rows(D1, D2, D3, POST, TEST_END, base=100.0), {D2: 0.25, POST: 0.5})
    data["AAA"] = (bar_rows(D1, D2, D3), {D2: 2.65 / 28})
    data["BBB"] = (bar_rows(D1, D3, base=20.0), {})
    data["BRK-B"] = (bar_rows(D2, D3, base=70.123456), {})
    data["CCC"] = (bar_rows(D3, POST), {})
    data["DDD"] = (bar_rows(POST), {POST: 1.0})
    return data


class FakeYahoo:
    """Injected downloader. Ignores the date range on purpose (the store must clip)."""

    def __init__(self, data):
        self.data = data
        self.calls: list[tuple[list[str], date, date]] = []

    def __call__(self, tickers, start, end_exclusive):
        self.calls.append((list(tickers), start, end_exclusive))
        return multi_frame({t: self.data.get(t, ([], {})) for t in tickers})


def fx_for(end: date):
    """A Frankfurter fake that asserts the build asked for FX_START..``end``."""

    def fetch(start, got_end):
        assert (start, got_end) == (research.FX_START, end)
        return [(D1, Decimal("8002")), (D2, 8010.5), (POST, Decimal("13600")), (TEST_END, 13700)]

    return fetch


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
    (d / "membership_overrides.csv").write_text(
        "date,index_id,action,ticker,note\n", encoding="utf-8"
    )
    (d / "ticker_aliases.csv").write_text("old,new,effective_date,note\n", encoding="utf-8")
    return d


def build(store, members_dir, *, window=None):
    w = research.DEV_WINDOW if window is None else window
    return research.build_store(
        store,
        downloader=FakeYahoo(default_data()),
        fetch_fx=fx_for(w.end),
        sleep=Sleeps(),
        batch_size=40,
        data_dir=members_dir,
        window=w,
    )


def read(store, name):
    return (store / name).read_text(encoding="utf-8")


def reseal(store):
    manifest = json.loads(read(store, research.MANIFEST_FILE))
    files = {n: research.file_sha256(store / n) for n in research.DATA_FILES}
    manifest["files"] = files
    manifest["fingerprint"] = research.fingerprint_of(files)
    (store / research.MANIFEST_FILE).write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )


def patched_build(monkeypatch, members_dir, *, end=TEST_END, latest=None):
    """``research.build_store`` with the fakes bound, and a fixed ``latest_session``."""
    monkeypatch.setattr(
        research,
        "build_store",
        functools.partial(
            research.build_store,
            downloader=FakeYahoo(default_data()),
            fetch_fx=fx_for(end),
            sleep=Sleeps(),
            data_dir=members_dir,
        ),
    )
    fixed = end if latest is None else latest
    monkeypatch.setattr(research, "latest_session", lambda now_utc=None: fixed)


# ---- the window ------------------------------------------------------------------------------


def test_test_window_constants_and_constructor():
    assert research.TEST_WINDOW_START == date(2015, 10, 19)
    assert research.TEST_STORE_DIR == config.REPO_ROOT / "engine" / ".research-test"
    assert research.TEST_STORE_DIR != research.STORE_DIR
    w = research.test_window(TEST_END)
    assert (w.name, w.start, w.end) == ("test", research.TEST_WINDOW_START, TEST_END)
    assert w != research.DEV_WINDOW
    assert research.DEV_WINDOW.name == "dev" and research.DEV_WINDOW.end == research.DEV_END
    # Phase 1 owns Window.following; this asserts the two spellings have not drifted.
    assert w == research.DEV_WINDOW.following("test", TEST_END)
    # The window bounds scoring, the store bounds data: the test store still starts at 1993.
    assert research.STORE_START < research.TEST_WINDOW_START
    with pytest.raises(ValueError, match="must end after DEV_END"):
        research.test_window(research.DEV_END)
    with pytest.raises(ValueError, match="must end after DEV_END"):
        research.test_window(date(2015, 1, 2))
    with pytest.raises(ValueError, match="NYSE session"):
        research.test_window(date(2016, 1, 3))  # a Sunday
    with pytest.raises(TypeError):
        research.test_window(datetime(2016, 1, 4, tzinfo=timezone.utc))


def test_latest_session_is_the_last_settled_nyse_session():
    assert research.latest_session(datetime(2016, 1, 5, 23, 0, tzinfo=timezone.utc)) == date(
        2016, 1, 5
    )
    # Before the close + settle on the 5th, the latest settled session is the 4th.
    assert research.latest_session(datetime(2016, 1, 5, 12, 0, tzinfo=timezone.utc)) == date(
        2016, 1, 4
    )


def test_test_store_dirs_are_gitignored():
    lines = (config.REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    for entry in (
        "engine/.research-test/",
        "engine/.research-test.tmp/",
        "engine/.research-test.old/",
    ):
        assert entry in lines


def test_manifest_keys_stay_nine_and_the_window_is_optional():
    """The dev store on disk carries exactly these nine keys. Widening the required set would
    refuse it before any reader ran, and its fingerprint 399d0d25... is the sync identity."""
    assert research.MANIFEST_KEYS == frozenset(
        {
            "dev_end",
            "store_start",
            "files",
            "fingerprint",
            "bar_rows",
            "dividend_rows",
            "fx_rows",
            "symbols_requested",
            "symbols_served",
        }
    )
    assert research.OPTIONAL_MANIFEST_KEYS == frozenset(
        {"window_name", "window_start", "window_end"}
    )
    assert not research.MANIFEST_KEYS & research.OPTIONAL_MANIFEST_KEYS


# ---- build -----------------------------------------------------------------------------------


def test_a_dev_build_declares_no_window(tmp_path, members_dir):
    manifest = build(tmp_path / "dev", members_dir)
    assert set(manifest) == research.MANIFEST_KEYS
    assert not research.OPTIONAL_MANIFEST_KEYS & set(manifest)
    assert manifest["dev_end"] == "2015-10-16"


def test_a_test_build_declares_its_window(tmp_path, members_dir):
    store = tmp_path / "test"
    manifest = build(store, members_dir, window=research.test_window(TEST_END))
    assert set(manifest) == research.MANIFEST_KEYS | research.OPTIONAL_MANIFEST_KEYS
    assert manifest["window_name"] == "test"
    assert manifest["window_start"] == "2015-10-19"
    assert manifest["window_end"] == TEST_END.isoformat()
    assert manifest["dev_end"] == "2015-10-16"  # still the code-version pin, not the window
    # The data still starts in 1993: window_start bounds scoring, store_start bounds the files.
    assert manifest["store_start"] == "1993-01-29"
    assert manifest["fingerprint"] == research.fingerprint_of(manifest["files"])
    assert manifest == json.loads(read(store, research.MANIFEST_FILE))


def test_a_test_build_requests_the_test_windows_members(members_dir):
    """The universe is the test window's members at BOTH ends (reconciled; index Decisions)."""
    dev = research.requested_symbols(members_dir)
    test = research.requested_symbols(members_dir, window=research.test_window(TEST_END))
    assert "NEW" not in dev  # joined 2016-01-04, after DEV_END
    assert "NEW" in test  # the far end moves: a post-2015 joiner is a test-window member
    assert "GONE" in dev  # a 1996-2000 member is a dev-window member
    assert "GONE" not in test  # ... and is a member on no test-window session, so nothing reads it
    assert "AAA" in dev and "AAA" in test  # a member across both windows is in both universes
    assert set(research.RESEARCH_ETFS) <= set(test)  # the ETFs are unconditional


def test_a_test_store_clamps_membership_against_its_own_end(members_dir):
    dev = research.research_membership(members_dir)
    test = research.research_membership(members_dir, window=research.test_window(TEST_END))
    # BBB leaves the index on 2016-01-04. For the dev window that end is beyond the window and
    # becomes None (a member on every dev session). For the test window it must stay a real end,
    # or a company that left would read as a member for the rest of the test window.
    assert ("BBB", date(1996, 1, 2), None) in dev.intervals
    assert ("BBB", date(1996, 1, 2), TEST_END) in test.intervals
    assert "NEW" not in dev.symbols()
    assert "NEW" in test.symbols()
    assert all(end is None or end <= TEST_END for _, _, end in test.intervals)


def test_a_test_store_is_a_superset_of_the_dev_stores_date_range(tmp_path, members_dir):
    """The coordinator's decision: the test store carries the FULL history from STORE_START.

    If it began at the test window's start, a candidate needing ~252 sessions of run-up would
    have its single, permanent, append-only look open ~10 months late.

    The comparison is **per symbol**, not over the whole file: the test universe is the test
    window's members (index Decisions), so GONE -- a 1996-2000 member -- is in the dev store
    and deliberately not in the test one. For every symbol the two universes share, the test
    store holds every dev row and more.
    """
    dev, test = tmp_path / "dev", tmp_path / "test"
    build(dev, members_dir)
    build(test, members_dir, window=research.test_window(TEST_END))
    dev_bars = set(read(dev, research.BARS_FILE).splitlines()[1:])
    test_bars = set(read(test, research.BARS_FILE).splitlines()[1:])
    shared = set(research.requested_symbols(members_dir)) & set(
        research.requested_symbols(members_dir, window=research.test_window(TEST_END))
    )
    dev_shared = {line for line in dev_bars if line.split(",", 1)[0] in shared}
    assert dev_shared and dev_shared < test_bars  # every shared dev row, plus the post-DEV_END ones
    assert {line for line in test_bars if line.split(",", 1)[0] == "GONE"} == set()
    assert "SPY,1999-01-04," in read(test, research.BARS_FILE)  # the run-up is there
    assert "AAA,1999-01-05,0.094643" in read(test, research.DIVIDENDS_FILE)
    assert read(test, research.FX_FILE).startswith("date,usd_idr\n1999-01-04,")


def test_a_test_build_holds_the_post_dev_end_rows(tmp_path, members_dir):
    dev, test = tmp_path / "dev", tmp_path / "test"
    build(dev, members_dir)
    build(test, members_dir, window=research.test_window(TEST_END))
    assert "2015-10-19" not in read(dev, research.BARS_FILE)
    assert "SPY,2015-10-19," in read(test, research.BARS_FILE)
    assert f"SPY,{TEST_END.isoformat()}," in read(test, research.BARS_FILE)
    assert "SPY,2015-10-19,0.5" in read(test, research.DIVIDENDS_FILE)
    assert f"{TEST_END.isoformat()},13700" in read(test, research.FX_FILE)
    # DDD has only a post-DEV_END bar: unserved for the dev window, served for the test window.
    assert "DDD," in read(dev, research.UNSERVED_FILE)
    assert "DDD," not in read(test, research.UNSERVED_FILE)


def test_a_test_build_requests_bars_through_its_window_end(tmp_path, members_dir):
    fake = FakeYahoo(default_data())
    research.build_store(
        tmp_path / "test",
        downloader=fake,
        fetch_fx=fx_for(TEST_END),
        sleep=Sleeps(),
        data_dir=members_dir,
        window=research.test_window(TEST_END),
    )
    assert fake.calls
    for _tickers, start, end_exclusive in fake.calls:
        assert start == research.STORE_START
        assert end_exclusive == TEST_END + timedelta(days=1)


# ---- load: the refusal -------------------------------------------------------------------------


def test_load_store_round_trips_a_test_store(tmp_path, members_dir):
    store = tmp_path / "test"
    window = research.test_window(TEST_END)
    manifest = build(store, members_dir, window=window)
    data = research.load_store(store, data_dir=members_dir, window=window)
    assert data.window == window
    assert data.fingerprint == manifest["fingerprint"]
    assert data.market.bar("SPY", POST) is not None
    # The fixture's members on that session: the 2016-01-04 S&P snapshot (AAA, CCC, NEW) and
    # the never-closed Nasdaq-100 one (AAA, DDD). NEW is the post-DEV_END joiner the test
    # window's universe must carry; it is absent from the dev store's entirely.
    assert data.market.membership.members_on(date(2016, 1, 5)) == frozenset(
        {"AAA", "CCC", "NEW", "DDD"}
    )
    assert any(d.ex_date == POST for d in data.spy_dividends)


def test_load_store_refuses_a_test_store_where_a_dev_store_is_expected(tmp_path, members_dir):
    store = tmp_path / "test"
    build(store, members_dir, window=research.test_window(TEST_END))
    with pytest.raises(ValueError, match="not interchangeable"):
        research.load_store(store, data_dir=members_dir)  # the dev default
    with pytest.raises(ValueError, match="declares the test window"):
        research.load_store(store, data_dir=members_dir, window=research.DEV_WINDOW)


def test_load_store_refuses_a_dev_store_where_a_test_store_is_expected(tmp_path, members_dir):
    store = tmp_path / "dev"
    build(store, members_dir)
    with pytest.raises(ValueError, match="declares the dev window"):
        research.load_store(store, data_dir=members_dir, window=research.test_window(TEST_END))


def test_load_store_refuses_a_test_store_for_the_wrong_end(tmp_path, members_dir):
    store = tmp_path / "test"
    build(store, members_dir, window=research.test_window(TEST_END))
    with pytest.raises(ValueError, match="not interchangeable"):
        research.load_store(
            store, data_dir=members_dir, window=research.test_window(date(2016, 1, 5))
        )


def test_load_store_refuses_a_row_after_the_test_windows_end(tmp_path, members_dir):
    store = tmp_path / "test"
    window = research.test_window(TEST_END)
    build(store, members_dir, window=window)
    text = read(store, research.FX_FILE)
    assert text.count(f"{TEST_END.isoformat()},") == 1
    (store / research.FX_FILE).write_text(
        text.replace(f"{TEST_END.isoformat()},", "2016-01-05,"), encoding="utf-8", newline="\n"
    )
    reseal(store)  # hashes match again: only the window's date guard can catch it
    with pytest.raises(ValueError, match="after the store's window end 2016-01-04"):
        research.load_store(store, data_dir=members_dir, window=window)


def test_declared_window_reads_the_manifest_alone(tmp_path, members_dir):
    dev, test = tmp_path / "dev", tmp_path / "test"
    build(dev, members_dir)
    build(test, members_dir, window=research.test_window(TEST_END))
    assert research.declared_window(dev) == research.DEV_WINDOW
    assert research.declared_window(test) == research.test_window(TEST_END)
    with pytest.raises(ValueError, match="no research store"):
        research.declared_window(tmp_path / "nope")


@pytest.mark.parametrize("key", ["window_name", "window_start", "window_end"])
def test_a_manifest_with_a_partial_window_declaration_is_refused(tmp_path, members_dir, key):
    store = tmp_path / "test"
    build(store, members_dir, window=research.test_window(TEST_END))
    manifest = json.loads(read(store, research.MANIFEST_FILE))
    del manifest[key]
    (store / research.MANIFEST_FILE).write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="all three or none"):
        research.load_store(store, data_dir=members_dir, window=research.test_window(TEST_END))


def test_a_manifest_may_not_declare_the_dev_window_by_name(tmp_path, members_dir):
    """The dev window is declared by ABSENCE. Allowing a second spelling would let the live dev
    store and a hand-edited one disagree about what they are."""
    store = tmp_path / "test"
    build(store, members_dir, window=research.test_window(TEST_END))
    manifest = json.loads(read(store, research.MANIFEST_FILE))
    manifest["window_name"] = "dev"
    (store / research.MANIFEST_FILE).write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="never by name"):
        research.declared_window(store)


def test_a_declared_window_inside_the_dev_window_is_refused(tmp_path, members_dir):
    store = tmp_path / "test"
    build(store, members_dir, window=research.test_window(TEST_END))
    manifest = json.loads(read(store, research.MANIFEST_FILE))
    manifest["window_start"] = "2010-01-04"
    (store / research.MANIFEST_FILE).write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="must start after DEV_END"):
        research.declared_window(store)


# ---- checks -----------------------------------------------------------------------------------


def test_checks_use_the_stores_own_window(tmp_path, members_dir):
    store = tmp_path / "test"
    window = research.test_window(TEST_END)
    build(store, members_dir, window=window)
    data = research.load_store(store, data_dir=members_dir, window=window)
    sessions = research.check_spy_sessions(data)
    assert f"..{TEST_END.isoformat()}" in sessions.detail  # not ..2015-10-16
    assert research.check_spy_sessions(data, start=D1, end=D2).ok


# ---- command ------------------------------------------------------------------------------------


def test_command_refuses_the_test_window_on_the_dev_store():
    assert cli.main(["research_store", "--test-window", "--store", str(research.STORE_DIR)]) == 2
    assert cli.main(["research_store", "--store", str(research.TEST_STORE_DIR), "--verify"]) == 2


def test_command_refuses_coverage_and_window_end_misuse(tmp_path):
    assert (
        cli.main(["research_store", "--coverage", "--test-window", "--store", str(tmp_path / "s")])
        == 2
    )
    assert (
        cli.main(["research_store", "--window-end", "2016-01-04", "--store", str(tmp_path / "s")])
        == 2
    )
    assert (
        cli.main(
            [
                "research_store",
                "--test-window",
                "--verify",
                "--window-end",
                "2016-01-04",
                "--store",
                str(tmp_path / "s"),
            ]
        )
        == 2
    )


def test_command_verify_refuses_a_cross_window_store(tmp_path, members_dir, capsys):
    store = tmp_path / "test"
    build(store, members_dir, window=research.test_window(TEST_END))
    assert cli.main(["research_store", "--verify", "--store", str(store)]) == 2
    assert capsys.readouterr().out == ""


def test_command_builds_a_test_store(tmp_path, members_dir, monkeypatch, capsys):
    patched_build(monkeypatch, members_dir)
    store = tmp_path / "test"
    code = cli.main(["research_store", "--test-window", "--store", str(store)])
    out = capsys.readouterr().out
    assert code == 1  # built fine; the real-data checks fail on fake data
    manifest = json.loads(read(store, research.MANIFEST_FILE))
    assert manifest["window_end"] == TEST_END.isoformat()
    assert f"window: test, scored from 2015-10-19, data through {TEST_END.isoformat()}" in out
    assert "store_start: 1993-01-29" in out  # the data range is NOT the window
    assert f"fingerprint: {manifest['fingerprint']}" in out


def test_command_window_end_pins_the_build(tmp_path, members_dir, monkeypatch):
    patched_build(monkeypatch, members_dir, latest=date(2016, 1, 5))
    store = tmp_path / "test"
    cli.main(
        [
            "research_store",
            "--test-window",
            "--window-end",
            TEST_END.isoformat(),
            "--store",
            str(store),
        ]
    )
    assert json.loads(read(store, research.MANIFEST_FILE))["window_end"] == TEST_END.isoformat()


# ---- command: the cross-checkout clobber guard (build path) --------------------------------------


def test_command_build_refuses_a_cross_checkout_dev_store(
    tmp_path, members_dir, monkeypatch, caplog
):
    """R1 forward: --test-window over a dev store that belongs to ANOTHER checkout.

    ``tmp_path`` is outside the running checkout, so ``_same_dir(store, research.STORE_DIR)`` is
    False and the path guard at research_store.py:219 cannot fire. Only the content guard can
    refuse here, and before this phase the build proceeded and replaced the manifest (measured).
    """
    patched_build(monkeypatch, members_dir)
    store = tmp_path / "other-checkout" / "engine" / ".research"
    store.parent.mkdir(parents=True)
    build(store, members_dir)
    before = read(store, research.MANIFEST_FILE)
    assert store.resolve() != research.STORE_DIR.resolve()  # the path guard cannot fire

    code = cli.main(["research_store", "--test-window", "--store", str(store)])

    assert code == 2
    assert "already holds a store declaring" in caplog.text
    assert str(store) in caplog.text
    assert "the dev window" in caplog.text
    assert read(store, research.MANIFEST_FILE) == before  # not one byte written
    assert set(json.loads(before)) == research.MANIFEST_KEYS
    assert not (store.parent / ".research.tmp").exists()
    assert not (store.parent / ".research.old").exists()
    # A dry run is a rehearsal of the same destructive build and is refused the same way.
    assert cli.main(["--dry-run", "research_store", "--test-window", "--store", str(store)]) == 2
    assert read(store, research.MANIFEST_FILE) == before


def test_command_build_refuses_a_cross_checkout_test_store(
    tmp_path, members_dir, monkeypatch, caplog
):
    """R1 reverse: a dev build aimed at another checkout's test store. Lower stake, same defect.

    ``end=research.DEV_END`` because a dev build asks Frankfurter for FX through DEV_END and
    ``patched_build``'s fake asserts the range; with the default end a regression would fail inside
    the FX fetch and this test would pass for the wrong reason.
    """
    patched_build(monkeypatch, members_dir, end=research.DEV_END)
    store = tmp_path / "other-checkout" / "engine" / ".research-test"
    store.parent.mkdir(parents=True)
    build(store, members_dir, window=research.test_window(TEST_END))
    before = read(store, research.MANIFEST_FILE)
    assert store.resolve() != research.TEST_STORE_DIR.resolve()  # the path guard cannot fire

    code = cli.main(["research_store", "--store", str(store)])

    assert code == 2
    assert "already holds a store declaring" in caplog.text
    assert str(store) in caplog.text
    assert f"the test window 2015-10-19..{TEST_END.isoformat()}" in caplog.text
    assert read(store, research.MANIFEST_FILE) == before
    assert json.loads(before)["window_end"] == TEST_END.isoformat()
    assert not (store.parent / ".research-test.tmp").exists()


@pytest.mark.parametrize("shape", ["missing", "empty", "unparseable"])
def test_command_build_proceeds_when_the_window_cannot_be_told(
    tmp_path, members_dir, monkeypatch, capsys, shape
):
    """The three undecidable shapes fall through. ``missing`` is the first build of all, and it is
    also ``research.STORE_DIR`` in every worktree, which is why the guard may never refuse it."""
    patched_build(monkeypatch, members_dir)
    store = tmp_path / "target"
    if shape in ("empty", "unparseable"):
        store.mkdir()
    if shape == "unparseable":
        (store / research.MANIFEST_FILE).write_text("{not json", encoding="utf-8")

    code = cli.main(["research_store", "--test-window", "--store", str(store)])

    capsys.readouterr()
    assert code == 1  # built fine; the real-data checks fail on fake data
    manifest = json.loads(read(store, research.MANIFEST_FILE))
    assert manifest["window_end"] == TEST_END.isoformat()
    assert manifest["window_name"] == "test"


def test_command_build_allows_a_same_window_dev_rebuild(
    tmp_path, members_dir, monkeypatch, capsys
):
    """A rebuild over a store of the SAME window is legitimate and must not be refused:
    ``--with-fundamentals`` over an existing dev store is the documented routine."""
    patched_build(monkeypatch, members_dir, end=research.DEV_END)
    store = tmp_path / "dev"
    first = build(store, members_dir)

    code = cli.main(["research_store", "--store", str(store)])

    out = capsys.readouterr().out
    assert code == 1
    second = json.loads(read(store, research.MANIFEST_FILE))
    assert set(second) == research.MANIFEST_KEYS  # still nine keys, still no window key
    assert second["fingerprint"] == first["fingerprint"]  # it really rebuilt the same store
    assert "store_start: 1993-01-29" in out


def test_command_build_allows_a_same_window_test_rebuild(
    tmp_path, members_dir, monkeypatch, capsys
):
    patched_build(monkeypatch, members_dir)
    store = tmp_path / "test"
    build(store, members_dir, window=research.test_window(TEST_END))

    code = cli.main(["research_store", "--test-window", "--store", str(store)])

    capsys.readouterr()
    assert code == 1
    assert json.loads(read(store, research.MANIFEST_FILE))["window_end"] == TEST_END.isoformat()


# ---- R2: the sibling paths were never checkout-local, and these pin it -----------------------------


def test_command_verify_refuses_a_cross_checkout_dev_store(tmp_path, members_dir, capsys):
    """The direction ``test_command_verify_refuses_a_cross_window_store`` does not cover: a DEV
    store under --test-window. Content-based through ``_store_window``, with no edit to it."""
    store = tmp_path / "dev"
    build(store, members_dir)
    assert cli.main(["research_store", "--verify", "--test-window", "--store", str(store)]) == 2
    assert capsys.readouterr().out == ""


def test_command_refresh_fundamentals_refuses_a_cross_checkout_store(tmp_path, members_dir):
    """Both directions, and no database is reached: ``_run_refresh`` calls ``_store_window``
    before ``_read_facts``, so the refusal happens with no DATABASE_URL in the environment."""
    dev = tmp_path / "dev"
    build(dev, members_dir)
    assert (
        cli.main(["research_store", "--refresh-fundamentals", "--test-window", "--store", str(dev)])
        == 2
    )
    test = tmp_path / "test"
    build(test, members_dir, window=research.test_window(TEST_END))
    assert cli.main(["research_store", "--refresh-fundamentals", "--store", str(test)]) == 2
    assert read(dev, research.MANIFEST_FILE)  # both stores still there, unread and unwritten
    assert json.loads(read(test, research.MANIFEST_FILE))["window_end"] == TEST_END.isoformat()


def test_command_coverage_refuses_a_cross_checkout_test_store(tmp_path, members_dir, capsys):
    """--coverage has no ``_store_window`` call, but ``load_store`` defaults to DEV_WINDOW and
    ``_read_manifest`` compares the declaration before opening a single data file."""
    store = tmp_path / "test"
    build(store, members_dir, window=research.test_window(TEST_END))
    assert cli.main(["research_store", "--coverage", "--store", str(store)]) == 2
    assert capsys.readouterr().out == ""  # the number is never printed for a refused store


def test_command_lab_test_refuses_a_cross_checkout_dev_store(tmp_path, members_dir, monkeypatch):
    """``lab test --store`` was already content-guarded at commands/lab.py:484. Pinned, not edited.

    ``resolve_candidate`` and ``preflight_test`` are stubbed because they run before the store is
    read and would otherwise refuse first, for an unrelated reason; the window check is then the
    first thing that actually runs. The two imports are function-local so this file's import block
    stays byte-for-byte as it was. ``runner.run_test``'s second, independent refusal is already
    pinned by ``test_lab_test_window.py:215-221`` and is not duplicated here.
    """
    from seer_engine.lab import runner
    from seer_engine.lab import store as lab_store

    store = tmp_path / "dev"
    build(store, members_dir)
    monkeypatch.setattr(runner, "resolve_candidate", lambda cid: (None, tmp_path / "m.py", None))
    monkeypatch.setattr(runner, "preflight_test", lambda conn, method, path, candidate: None)
    db = tmp_path / "lab.sqlite"

    code = cli.main(["lab", "--db", str(db), "test", "M0001-A", "--store", str(store)])

    assert code == 2
    conn = lab_store.connect(db)
    try:
        assert lab_store.test_looks(conn) == 0  # the one counted look was not spent
    finally:
        conn.close()


# ---- the ex-date calendar on the market (M0051's plumbing) ------------------------------------


def test_both_windows_hand_the_market_their_own_dividend_calendar(tmp_path, members_dir):
    """``load_store`` puts the store's dividends on ``Market.dividends`` for either window, and
    the dev store's calendar holds nothing after DEV_END: the loader clips, the calendar never
    widens it."""
    dev, test = tmp_path / "dev", tmp_path / "test"
    build(dev, members_dir)
    window = research.test_window(TEST_END)
    build(test, members_dir, window=window)
    dev_data = research.load_store(dev, data_dir=members_dir)
    test_data = research.load_store(test, data_dir=members_dir, window=window)
    assert dev_data.market.dividends.known_on("SPY", TEST_END) == ((D2, Decimal("0.25")),)
    assert test_data.market.dividends.known_on("SPY", TEST_END) == (
        (D2, Decimal("0.25")), (POST, Decimal("0.5")),
    )
    # point in time: the day before an ex-date, that ex-date is not visible
    assert test_data.market.dividends.known_on("SPY", POST - timedelta(days=1)) == ((D2, Decimal("0.25")),)
    for data in (dev_data, test_data):
        cal = data.market.dividends
        assert len(cal) == sum(len(v) for v in data.dividends.values())
        for symbol, by_date in data.dividends.items():
            assert cal.known_on(symbol, data.window.end) == tuple(sorted(by_date.items()))

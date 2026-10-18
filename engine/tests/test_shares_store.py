"""Company size in the research store: ``shares.csv`` and ``splits.csv`` (``shares.store``), the
``ShareCounts`` reader, ``Market.shares_on`` / ``Market.market_value``, the store refresh that
leaves every price byte alone, ``lab run``'s refusal of a size method on a store without them, and
the survivorship cleaning's split list. No network."""

from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pytest
from labkit import smoke_data

import test_research_store as rs
from seer_engine import cik as c
from seer_engine import research
from seer_engine import survivorship as sv
from seer_engine.backtest.market import (
    EMPTY_SHARES,
    Market,
    Membership,
    ShareCount,
    ShareCounts,
)
from seer_engine.lab import runner, store
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0051_dividend_month_premium import METHOD as M0051
from seer_engine.lab.methods.m0051_dividend_month_premium import DividendMonthAllocator
from seer_engine.shares import history, splits
from seer_engine.shares import store as ss
from seer_engine.strategies.base import History
from test_research_store import build

D = date.fromisoformat


@pytest.fixture
def members(tmp_path):
    return rs.members_dir.__wrapped__(tmp_path)


# --- change points ------------------------------------------------------------------------


def _row(symbol, cik, start, end=None):
    return c.CikRow(symbol, cik, D(start), D(end) if end else None, "X", "manual", "n")


def srow(filed, shares, as_of=None, cik="0000000001", n=1):
    return history.ShareRow(
        cik=cik, filed=D(filed), accession=f"{cik}-{filed[2:4]}-{n:06d}", symbol="AAA",
        as_of=D(as_of) if as_of else None, form="10-Q", shares=shares, classes=(), flags=(), note="",
    )


@dataclass(frozen=True)
class XF:
    symbol: str
    tag: str
    period_end: date
    val: float
    accn: str
    filed: date


INDEX = {
    "AAA": (_row("AAA", "0000000001", "1990-01-01", "2005-01-01"), _row("AAA", "0000000009", "2005-01-01")),
    "BBB": (_row("BBB", None, "1990-01-01"),),
}
ROWS = [
    srow("2000-05-10", 100, "2000-04-30", n=1),
    srow("2000-08-10", 120, "2000-07-31", n=2),
    srow("2003-02-10", 130, None, n=3),  # no as-of date on the cover: counted on its filing day
    srow("2004-05-10", 140, "2004-04-30", n=4),
    srow("2005-02-10", 7, "2005-02-01", cik="0000000009", n=5),  # the ticker's new filer
    srow("2009-05-01", 9, "2009-04-20", cik="0000000009", n=6),
]
FACTS = [
    XF("AAA", "EntityCommonStockSharesOutstanding", D("2009-04-20"), 9.5, "0000000009-09-000006", D("2009-05-01")),
    XF("AAA", "EntityCommonStockSharesOutstanding", D("2009-10-20"), 11.0, "0000000009-09-000007", D("2009-11-01")),
]


def _hist():
    return history.SharesHistory(ROWS, INDEX, FACTS)


def _counts(tmp_path, hist, symbols, start, end):
    path = tmp_path / research.SHARES_FILE
    research._write_text(path, ss.SHARES_HEADER, ss.shares_lines(ss.change_points(hist, symbols, start, end)))
    return ShareCounts(ss.read_shares(path, end))


def test_change_points_answer_exactly_what_shares_on_answers_on_every_day(tmp_path):
    hist = _hist()
    start, end = D("1999-01-01"), D("2011-12-31")
    counts = _counts(tmp_path, hist, ["AAA", "BBB", "ZZZ"], start, end)
    d = start
    while d <= end:
        o = hist.shares_on("AAA", d)
        got = counts.count("AAA", d)
        assert (None if o is None else (o.shares, o.as_of or o.filed, o.filed, o.source)) == (
            None if got is None else tuple(got)
        ), d
        assert counts.count("BBB", d) is None and counts.count("ZZZ", d) is None
        d += timedelta(days=1)
    assert counts.symbols() == ("AAA",)  # never known: no rows at all


def test_the_rows_cover_the_seams_the_lookup_has():
    rows = ss.change_points(_hist(), ["AAA"], D("1999-01-01"), D("2011-12-31"))
    by = {r.start: r.obs for r in rows}
    assert by[D("2000-05-10")].shares == 100  # public from its filing day, not its as-of day
    assert by[D("2004-05-10")].shares == 140
    assert by[D("2005-01-01")] is None  # the new filer has filed nothing yet
    assert by[D("2005-02-10")].shares == 7
    assert (by[D("2009-05-01")].shares, by[D("2009-05-01")].source) == (9.5, history.SOURCE_XBRL)
    assert by[D("2010-11-25")] is None  # 2009-10-20 + 401 days: too old to answer
    assert all(r.obs is None or r.obs.filed <= r.start for r in rows)


@dataclass(frozen=True)
class FF:
    symbol: str
    tag: str
    period_end: date
    val: float
    accn: str
    filed: date
    form: str = "10-Q"


def test_usable_xbrl_drops_foreign_issuers_and_unit_errors():
    tag = "EntityCommonStockSharesOutstanding"
    yum = [FF("YUM", tag, D(f"2016-{m:02d}-01"), v, f"a{m}", D(f"2016-{m:02d}-10"))
           for m, v in ((2, 408_711_522.0), (4, 407_440_778.0), (7, 389_887_084.0),
                        (10, 367_005_511_000_000.0), (12, 353_844_095.0))]
    split = [FF("NVDA", tag, D("2024-04-01"), 2.5e9, "n1", D("2024-04-10")),
             FF("NVDA", tag, D("2024-07-01"), 24.5e9, "n2", D("2024-07-10")),  # ten-for-one: kept
             FF("NVDA", tag, D("2024-10-01"), 24.5e9, "n3", D("2024-10-10"))]
    ntes = [FF("NTES", tag, D("2016-12-31"), 3.28e9, "x", D("2017-04-21"), form="20-F")]
    kept, dropped = ss.usable_xbrl(yum + split + ntes)
    assert [f.accn for f in dropped["unit error"]] == ["a10"]
    assert [f.symbol for f in dropped["foreign filer"]] == ["NTES"]
    assert {f.accn for f in kept} == {"a2", "a4", "a7", "a12", "n1", "n2", "n3"}


def test_usable_class_rows_drops_a_reading_both_neighbours_disown():
    from seer_engine.shares.classes import ClassRow

    def row(cik, filed, acc, shares, classes=()):
        return ClassRow(cik, "X", D(filed), D(filed), "10-Q", acc, shares, tuple(classes), False)

    # Real readings, found refreshing the stores: Marriott's 10-Q of 2010-04-23 tags
    # 361,332,043,000,000 shares; TripAdvisor's of 2014-05-06 tags class B alone in dei.
    mar = [row("m", "2010-02-12", "m1", 358_522_350), row("m", "2010-04-23", "m2", 361_332_043_000_000),
           row("m", "2010-07-16", "m3", 362_811_812)]
    trip = [row("t", "2014-02-11", "t1", 142_232_795), row("t", "2014-05-06", "t2", 12_799_999,
                                                            [("CommonClassBMember", 12_799_999)]),
            row("t", "2014-07-28", "t3", 142_785_347)]
    # Berkshire's 50-for-1 class B split: the jump is kept, since its neighbours disagree.
    brk = [row("b", "2009-08-07", "b1", 15_902_240), row("b", "2009-11-06", "b2", 15_902_240),
           row("b", "2010-03-01", "b3", 815_453_685), row("b", "2010-05-07", "b4", 969_747_703)]
    # One reading alone, or at the end of a filer's run, has no two neighbours to judge it.
    edge = [row("e", "2014-01-01", "e1", 100), row("e", "2014-04-01", "e2", 100),
            row("e", "2014-07-01", "e3", 100_000)]
    # Viacom 2009-2010: a good reading between two bad ones is judged against the last good one.
    via = [row("v", "2009-07-28", "v1", 607_300_000), row("v", "2009-11-03", "v2", 607_400_000_000_000),
           row("v", "2010-02-11", "v3", 607_400_000), row("v", "2010-04-29", "v4", 607_377_009_000_000),
           row("v", "2010-08-05", "v5", 608_154_207)]
    kept, dropped = ss.usable_class_rows(mar + trip + brk + edge + via)
    assert [r.accession for r in dropped] == ["m2", "t2", "v2", "v4"]
    assert {r.accession for r in kept} == {"m1", "m3", "t1", "t3", "b1", "b2", "b3", "b4", "e1", "e2", "e3",
                                           "v1", "v3", "v5"}


def test_shares_lines_round_trip_and_the_reader_refuses_look_ahead(tmp_path):
    lines = ss.shares_lines(ss.change_points(_hist(), ["AAA"], D("1999-01-01"), D("2011-12-31")))
    assert lines[0] == "AAA,2000-05-10,100,2000-04-30,2000-05-10,edgar-cover,0000000001-00-000001"
    assert "AAA,2003-02-10,130,2003-02-10,2003-02-10,edgar-cover,0000000001-03-000003" in lines
    assert "AAA,2005-01-01,,,,," in lines
    path = tmp_path / "shares.csv"
    for bad, why in [
        ("AAA,2000-05-09,100,2000-04-30,2000-05-10,edgar-cover,x", "look-ahead"),
        ("AAA,2016-01-04,100,2015-12-30,2016-01-04,xbrl,x", "D9"),
        ("AAA,2000-05-10,100,2000-04-30,2000-05-10,guess,x", "unknown source"),
        ("AAA,2000-05-10,,2000-04-30,,,", "every other field empty"),
    ]:
        research._write_text(path, ss.SHARES_HEADER, [bad])
        with pytest.raises(ValueError, match=why):
            ss.read_shares(path, research.DEV_END)
    research._write_text(path, ss.SHARES_HEADER, ["BBB,2000-01-01,,,,,", "AAA,2000-01-01,,,,,"])
    with pytest.raises(ValueError, match="sorted"):
        ss.read_shares(path, research.DEV_END)


# --- splits -------------------------------------------------------------------------------

AAPL = (
    splits.Split(D("1987-06-16"), 2.0),
    splits.Split(D("2000-06-21"), 2.0),
    splits.Split(D("2005-02-28"), 2.0),
    splits.Split(D("2014-06-09"), 7.0),
    splits.Split(D("2020-08-31"), 4.0),
    splits.Split(D("2027-01-04"), 3.0),  # after the crawl: never applied to the bars
)


def test_split_lines_keep_the_window_dated_and_fold_what_came_after_it():
    lines = ss.split_lines({"AAPL": AAPL, "MSFT": ()}, store_start=research.STORE_START,
                           window_end=research.DEV_END, basis=D("2026-10-04"))
    assert lines == ["AAPL,2000-06-21,2.0", "AAPL,2005-02-28,2.0", "AAPL,2014-06-09,7.0", "AAPL,,4.0"]
    with pytest.raises(ValueError, match="basis"):
        ss.split_lines({}, store_start=research.STORE_START, window_end=research.DEV_END, basis=D("2015-01-01"))


def test_the_split_reader_refuses_a_row_after_the_window(tmp_path):
    path = tmp_path / "splits.csv"
    research._write_text(path, ss.SPLITS_HEADER, ["AAPL,2020-08-31,4.0"])
    with pytest.raises(ValueError, match="D9"):
        ss.read_splits(path, research.STORE_START, research.DEV_END)
    research._write_text(path, ss.SPLITS_HEADER, ["AAPL,,4.0", "AAPL,2014-06-09,7.0"])
    with pytest.raises(ValueError, match="after its undated"):
        ss.read_splits(path, research.STORE_START, research.DEV_END)
    research._write_text(path, ss.SPLITS_HEADER, ["AAPL,2014-06-09,0"])
    with pytest.raises(ValueError, match="positive"):
        ss.read_splits(path, research.STORE_START, research.DEV_END)


def test_a_listed_split_the_adjusted_closes_do_not_carry_is_left_out():
    days = [D("2026-09-29"), D("2026-09-30"), D("2026-10-01"), D("2026-10-02")]
    never = [(days, [60.0, 60.5, 9.1, 9.0])]  # fell by the listed 6.665: never applied
    carried = [(days, [9.0, 9.1, 9.05, 9.0])]  # continuous: applied
    big = splits.Split(D("2026-10-01"), 6.665)
    small = splits.Split(D("2026-10-01"), 1.033)  # too small to judge on one day: trusted
    assert ss.applied_by_vendor([big, small], never) == ([small], [big])
    assert ss.applied_by_vendor([big], carried) == ([big], [])
    assert ss.applied_by_vendor([splits.Split(D("2030-01-02"), 2.0)], never)[0]  # no evidence: kept


def test_read_yfinance_parses_the_cache_and_tells_unknown_from_never_fetched(tmp_path):
    def fetcher(ticker):
        return None if ticker == "GONE" else [(D("2014-06-09"), 7.0), (D("2005-02-28"), 2.0)]

    assert splits.fetch_yfinance(["AAPL", "GONE", "BRK.B"], tmp_path, fetcher=fetcher) == (3, 1, [])
    assert splits.read_yfinance(tmp_path, "AAPL") == (splits.Split(D("2005-02-28"), 2.0), splits.Split(D("2014-06-09"), 7.0))
    assert json.loads((tmp_path / "BRK.B.json").read_text())["ticker"] == "BRK-B"
    assert splits.read_yfinance(tmp_path, "GONE") is None
    assert splits.read_yfinance(tmp_path, "NEVER") is None
    assert splits.fetch_yfinance(["AAPL"], tmp_path, fetcher=fetcher) == (0, 0, [])  # cached


# --- the accessor -------------------------------------------------------------------------


def _history(symbol, rows):
    n = len(rows)
    closes = np.array([c for _, c in rows], dtype=np.float64)
    return History(
        symbol=symbol,
        dates=np.array([d for d, _ in rows], dtype="datetime64[D]"),
        open=closes, high=closes, low=closes, close=closes,
        volume=np.zeros(n, dtype=np.float64),
    )


def _apple_market():
    """Printed closes 100 (2005-02-25) and 50 (2005-02-28, after a 2-for-1), stored split-adjusted
    by everything up to the crawl: 2005's 2, 2014's 7 and (after the window) 2020's 4."""
    adj = 2.0 * 7.0 * 4.0
    hist = _history("AAPL", [(D("2005-02-25"), 100 / adj), (D("2005-02-28"), 50 / (7.0 * 4.0)),
                             (D("2005-03-31"), 60 / (7.0 * 4.0))])
    counts = ShareCounts(
        {"AAPL": [
            (D("2005-01-20"), ShareCount(400.0, D("2005-01-10"), D("2005-01-20"), "edgar-cover")),
            (D("2005-05-01"), ShareCount(820.0, D("2005-04-15"), D("2005-05-01"), "edgar-cover")),
        ]},
        {"AAPL": ([(D("2005-02-28"), 2.0), (D("2014-06-09"), 7.0)], 4.0)},
    )
    return Market(history={"AAPL": hist}, membership=Membership(()), fx=(), shares=counts)


def test_market_value_is_the_count_times_the_printed_close_across_a_split():
    m = _apple_market()
    assert m.market_value("AAPL", D("2005-02-25")) == pytest.approx(400 * 100)
    assert m.shares_on("AAPL", D("2005-02-25")) == 400
    # the pre-split count is carried across the split, and the close is the printed one
    assert m.shares_on("AAPL", D("2005-02-28")) == 800
    assert m.market_value("AAPL", D("2005-02-28")) == pytest.approx(800 * 50)
    assert m.market_value("AAPL", D("2005-03-31")) == pytest.approx(800 * 60)
    assert m.shares.raw_factor("AAPL", D("2005-02-25")) == 56.0
    assert history.unadjust(100 / 56.0, D("2005-02-25"), AAPL[:5], basis=D("2026-10-04")) == pytest.approx(100)


def test_market_value_reads_nothing_after_the_day():
    m = _apple_market()
    assert m.market_value("AAPL", D("2005-01-19")) is None  # counted, not yet filed
    assert m.shares_on("AAPL", D("2005-04-30")) == 800  # the 820 is filed on 2005-05-01
    assert m.market_value("AAPL", D("2005-04-07")) == pytest.approx(800 * 60)  # last close, a week old
    assert m.market_value("AAPL", D("2005-04-08")) is None  # older than a week: no size
    assert m.market_value("MSFT", D("2005-03-31")) is None


def test_a_count_dated_after_the_last_close_is_carried_back_to_it():
    m = _apple_market()
    counts = ShareCounts(
        {"AAPL": [(D("2005-03-01"), ShareCount(800.0, D("2005-03-01"), D("2005-03-01"), "xbrl"))]},
        {"AAPL": ([(D("2005-02-28"), 2.0)], 28.0)},
    )
    # asked on Sunday 2005-03-06 with the last close on Friday 2005-02-25 -- before the split
    hist = _history("AAPL", [(D("2005-02-25"), 100 / 56.0)])
    m = dataclasses.replace(m, history={"AAPL": hist}).with_shares(counts)
    assert m.market_value("AAPL", D("2005-03-03")) == pytest.approx(400 * 100)


def test_a_market_without_shares_answers_none():
    m = Market(history={}, membership=Membership(()), fx=())
    assert m.shares is EMPTY_SHARES
    assert m.shares_on("AAPL", D("2005-02-25")) is None and m.market_value("AAPL", D("2005-02-25")) is None
    with pytest.raises(TypeError):
        Market(history={}, membership=Membership(()), fx=(), shares={})


def test_share_counts_refuse_a_figure_read_before_it_was_filed():
    with pytest.raises(ValueError, match="before it was public"):
        ShareCounts({"A": [(D("2005-01-01"), ShareCount(1.0, D("2004-12-01"), D("2005-01-02"), "xbrl"))]})


# --- the store ------------------------------------------------------------------------------

SHARE_LINES = [
    "AAA,1999-01-04,1000,1998-12-20,1999-01-04,edgar-cover,0000000001-99-000001",
    "AAA,2001-01-04,,,,,",
    "BBB,1999-01-05,500,1999-01-05,1999-01-05,xbrl,0000000002-99-000001",
]
SPLIT_LINES = ["AAA,2000-06-01,2.0", "AAA,,3.0"]


def test_refresh_shares_writes_both_files_and_keeps_every_price_byte(tmp_path, members):
    store_dir = tmp_path / "store"
    before = build(store_dir, members, facts=rs.FACTS_A)
    carried = (*research.DATA_FILES, research.FUNDAMENTALS_FILE)
    before_bytes = {n: (store_dir / n).read_bytes() for n in carried}

    after = research.refresh_shares(store_dir, SHARE_LINES, SPLIT_LINES, data_dir=members)

    assert {n: (store_dir / n).read_bytes() for n in carried} == before_bytes
    assert {research.SHARES_FILE, research.SPLITS_FILE} <= set(after["files"])
    assert research.price_fingerprint_of(after["files"]) == research.price_fingerprint_of(before["files"])
    assert after["fingerprint"] != before["fingerprint"]
    data = research.load_store(store_dir, data_dir=members)
    m = data.market
    aaa = m.history["AAA"]
    d1 = aaa.dates[0].item()
    assert m.shares_on("AAA", d1) == 1000
    assert m.market_value("AAA", d1) == pytest.approx(1000 * float(aaa.close[0]) * 2.0 * 3.0)
    assert m.shares_on("AAA", D("2001-01-04")) is None
    assert m.shares.raw_factor("BBB", d1) == 1.0  # no splits listed
    # refreshing another optional file afterwards carries both over
    research.refresh_fundamentals(store_dir, rs.FACTS_A, data_dir=members)
    assert research.load_store(store_dir, data_dir=members).market.shares_on("AAA", d1) == 1000


def test_refresh_shares_refuses_a_row_after_the_window_and_writes_nothing(tmp_path, members):
    store_dir = tmp_path / "store"
    before = build(store_dir, members)
    with pytest.raises(ValueError, match="D9"):
        research.refresh_shares(store_dir, SHARE_LINES, ["AAA,2016-01-04,2.0"], data_dir=members)
    assert json.loads((store_dir / research.MANIFEST_FILE).read_text()) == before
    assert not (store_dir / research.SHARES_FILE).exists()


def test_a_store_without_the_files_loads_with_no_shares(tmp_path, members):
    store_dir = tmp_path / "store"
    build(store_dir, members)
    assert research.load_store(store_dir, data_dir=members).market.shares is EMPTY_SHARES


# --- the lab ------------------------------------------------------------------------------


class _SizeAllocator(DividendMonthAllocator):
    market_fields = ("shares",)


def _size_method(mid: str = "M0014") -> Method:
    cand = dataclasses.replace(M0051.candidates[0], id=f"{mid}-CAP", family=mid, allocator=_SizeAllocator())
    return Method(
        id=mid, name="size test", family="size", source_kind="knowledge", source_ref="",
        hypothesis="h", expected_failure="f", candidates=(cand,),
    )


def test_a_size_method_is_refused_on_a_store_without_shares():
    data = smoke_data()
    assert runner.market_aware_candidates(_size_method(), "shares") == ("M0014-CAP",)
    with pytest.raises(store.LabError, match="no share history"):
        runner.preflight_data(data, _size_method())


def test_a_size_method_passes_once_the_store_carries_shares():
    data = smoke_data()
    counts = ShareCounts({"AAA": [(D("1999-01-04"), ShareCount(1.0, D("1999-01-04"), D("1999-01-04"), "xbrl"))]})
    with_shares = dataclasses.replace(data, market=data.market.with_shares(counts))
    assert runner.preflight_data(with_shares, _size_method()) is None


# --- the survivorship cleaning's split list -------------------------------------------------


def test_the_survivorship_cleaning_lists_the_splits_it_divided_by():
    sessions = [d for d in (D("2000-01-03") + timedelta(days=i) for i in range(40)) if d.weekday() < 5]
    split_day = sessions[20]
    bars = tuple(
        sv.RawBar(d, *([100.0 if d < split_day else 50.0] * 4), 1000.0) for d in sessions
    )
    series = sv.SourceSeries(
        symbol="OLD", source=sv.EODHD_SOURCE, code="OLD.US", bars=bars,
        splits=(sv.Split(split_day, 2.0), sv.Split(D("2019-01-02"), 3.0)),
    )
    cleaned = sv.clean_symbol(series, sessions, sessions)
    assert cleaned.splits_applied == 1
    assert cleaned.splits == (sv.Split(split_day, 2.0),)
    assert {b.close for b in cleaned.bars} == {50}


def test_a_figure_already_post_split_is_not_carried_across_the_split_again():
    # Netflix, 10-Q for Q2 2015: XBRL dates the count 2015-06-30, files it 2015-07-17, and states
    # the post-split 426 million although the seven-for-one went ex on 2015-07-15.
    counts = ShareCounts(
        {"NFLX": [
            (D("2015-04-17"), ShareCount(60_620_721.0, D("2015-03-31"), D("2015-04-17"), "xbrl")),
            (D("2015-07-17"), ShareCount(426_004_831.0, D("2015-06-30"), D("2015-07-17"), "xbrl")),
        ]},
        {"NFLX": ([(D("2015-07-15"), 7.0)], 1.0)},
    )
    assert counts.shares_on("NFLX", D("2015-07-16")) == pytest.approx(60_620_721 * 7)
    assert counts.units_day("NFLX", D("2015-09-30")) == D("2015-07-17")
    assert counts.shares_on("NFLX", D("2015-09-30")) == 426_004_831
    # a figure that really was counted before the split is still carried across it
    pre = ShareCounts(
        {"NFLX": [
            (D("2015-04-17"), ShareCount(60_620_721.0, D("2015-03-31"), D("2015-04-17"), "xbrl")),
            (D("2015-07-17"), ShareCount(60_900_000.0, D("2015-07-10"), D("2015-07-17"), "edgar-cover")),
        ]},
        {"NFLX": ([(D("2015-07-15"), 7.0)], 1.0)},
    )
    assert pre.units_day("NFLX", D("2015-09-30")) == D("2015-07-10")
    assert pre.shares_on("NFLX", D("2015-09-30")) == pytest.approx(60_900_000 * 7)

"""Market series (EODHD plan set, phase 3, R8).

``MarketSeries`` is read point in time; ``market_series.csv`` is an optional store file that never
moves the price fingerprint; ``lab run`` refuses a series method on a store without series; and
the ``market_series`` command normalizes EODHD's cached closes. No network.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from labkit import smoke_data, smoke_market

import test_research_store as rs
from seer_engine import research
from seer_engine.backtest.market import EMPTY_SERIES, MarketSeries
from seer_engine.commands import market_series as cmd
from seer_engine.lab import runner, store
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0051_dividend_month_premium import METHOD as M0051
from seer_engine.lab.methods.m0051_dividend_month_premium import DividendMonthAllocator
from test_research_store import build


@pytest.fixture
def members(tmp_path):
    """``test_research_store``'s membership fixture, under a name that does not shadow it."""
    return rs.members_dir.__wrapped__(tmp_path)


# ---- MarketSeries --------------------------------------------------------------------------

VIX = [
    (date(2008, 9, 12), 25.66),
    (date(2008, 9, 15), 31.7),
    (date(2008, 9, 16), 30.3),
    (date(2008, 9, 19), 32.07),
]


def test_value_on_is_the_latest_value_dated_on_or_before_the_data_date():
    s = MarketSeries({"VIX": VIX})
    assert s.value_on("VIX", date(2008, 9, 11)) is None
    assert s.value_on("VIX", date(2008, 9, 12)) == 25.66
    assert s.value_on("VIX", date(2008, 9, 17)) == 30.3  # the last close, never the next one
    assert s.value_on("VIX", date(2020, 1, 1)) == 32.07
    assert s.value_on("T10Y", date(2008, 9, 15)) is None


def test_no_value_dated_after_the_data_date_is_ever_visible():
    s = MarketSeries({"VIX": VIX})
    d = date(2008, 9, 10)
    while d <= date(2008, 9, 22):
        seen = s.upto("VIX", d)
        assert all(x <= d for x, _ in seen)
        assert seen == tuple(r for r in VIX if r[0] <= d)
        assert s.value_on("VIX", d) == (seen[-1][1] if seen else None)
        d += timedelta(days=1)


def test_upto_last_keeps_only_the_tail():
    s = MarketSeries({"VIX": VIX})
    assert s.upto("VIX", date(2008, 9, 16), last=2) == (VIX[1], VIX[2])
    assert s.upto("VIX", date(2008, 9, 11), last=2) == ()
    assert s.upto("NOPE", date(2008, 9, 16)) == ()
    with pytest.raises(ValueError):
        s.upto("VIX", date(2008, 9, 16), last=0)


def test_names_first_date_and_len():
    s = MarketSeries({"VIX": VIX, "T13W": [(date(1993, 1, 29), 2.9)], "EMPTY": []})
    assert s.names() == ("T13W", "VIX")
    assert s.first_date("VIX") == date(2008, 9, 12)
    assert s.first_date("EMPTY") is None
    assert len(s) == 5
    assert len(EMPTY_SERIES) == 0 and EMPTY_SERIES.names() == ()


@pytest.mark.parametrize(
    "rows, err",
    [
        ([], TypeError),
        ({"": [(date(2008, 9, 12), 1.0)]}, ValueError),
        ({"VIX": [(date(2008, 9, 12), 1.0), (date(2008, 9, 12), 2.0)]}, ValueError),
        ({"VIX": [(date(2008, 9, 15), 1.0), (date(2008, 9, 12), 2.0)]}, ValueError),
        ({"VIX": [(date(2008, 9, 12), float("nan"))]}, ValueError),
        ({"VIX": [(date(2008, 9, 12), float("inf"))]}, ValueError),
        ({"VIX": [(date(2008, 9, 12), True)]}, TypeError),
        ({"VIX": [(date(2008, 9, 12), Decimal("1"))]}, TypeError),
        ({"VIX": [(datetime(2008, 9, 12), 1.0)]}, TypeError),
        ({"VIX": [(date(2008, 9, 12),)]}, TypeError),
    ],
)
def test_bad_rows_are_refused(rows, err):
    with pytest.raises(err):
        MarketSeries(rows)


def test_a_data_date_must_be_a_date():
    with pytest.raises(TypeError):
        MarketSeries({"VIX": VIX}).value_on("VIX", datetime(2008, 9, 15))


def test_a_market_carries_the_shared_empty_series_unless_given_one():
    m = smoke_market()
    assert m.series is EMPTY_SERIES
    s = MarketSeries({"VIX": VIX})
    m2 = m.with_series(s)
    assert m2.series is s
    assert m.series is EMPTY_SERIES
    assert m2.history is m.history
    with pytest.raises(TypeError):
        dataclasses.replace(m, series={"VIX": VIX})


# ---- the store file ------------------------------------------------------------------------

ROWS = (
    ("VIX", date(1999, 1, 5), Decimal("24.42")),
    ("T10Y", date(1999, 1, 4), Decimal("4.653")),
    ("VIX", date(1999, 1, 4), Decimal("26.17")),
    ("T13W", date(2015, 10, 16), Decimal("0.005")),
)


def test_lines_are_sorted_by_series_then_date_with_normalized_values():
    extra = (
        ("GOLD", date(1999, 1, 4), Decimal("287.50")),
        ("GOLD", date(1999, 1, 5), Decimal("300.00")),
    )
    assert research.market_series_lines(ROWS + extra) == [
        "GOLD,1999-01-04,287.5",
        "GOLD,1999-01-05,300",
        "T10Y,1999-01-04,4.653",
        "T13W,2015-10-16,0.005",
        "VIX,1999-01-04,26.17",
        "VIX,1999-01-05,24.42",
    ]


@pytest.mark.parametrize(
    "row, err",
    [
        (("SPX", date(1999, 1, 4), Decimal("1")), ValueError),
        (("VIX", date(2015, 10, 19), Decimal("1")), ValueError),  # after DEV_END
        (("VIX", date(1993, 1, 28), Decimal("1")), ValueError),  # before STORE_START
        (("VIX", date(1999, 1, 4), 1.0), ValueError),
        (("VIX", date(1999, 1, 4), Decimal("NaN")), ValueError),
        (("VIX", datetime(1999, 1, 4), Decimal("1")), TypeError),
    ],
)
def test_lines_refuse_a_bad_row(row, err):
    with pytest.raises(err):
        research.market_series_lines((row,))


def test_lines_refuse_two_values_for_one_day():
    with pytest.raises(ValueError, match="two values"):
        research.market_series_lines(ROWS + (("VIX", date(1999, 1, 4), Decimal("1")),))


def test_refresh_adds_the_file_and_keeps_every_price_byte(tmp_path, members):
    store_dir = tmp_path / "store"
    before = build(store_dir, members, facts=rs.FACTS_A)
    carried = (*research.DATA_FILES, research.FUNDAMENTALS_FILE)
    before_bytes = {n: (store_dir / n).read_bytes() for n in carried}

    after = research.refresh_market_series(store_dir, ROWS, data_dir=members)

    assert {n: (store_dir / n).read_bytes() for n in carried} == before_bytes
    assert research.MARKET_SERIES_FILE in after["files"]
    assert research.price_fingerprint_of(after["files"]) == research.price_fingerprint_of(before["files"])
    assert after["fingerprint"] != before["fingerprint"]
    assert (store_dir / research.MARKET_SERIES_FILE).read_text(encoding="utf-8") == (
        "series,date,value\n"
        "T10Y,1999-01-04,4.653\n"
        "T13W,2015-10-16,0.005\n"
        "VIX,1999-01-04,26.17\n"
        "VIX,1999-01-05,24.42\n"
    )
    data = research.load_store(store_dir, data_dir=members)
    assert data.market.series.names() == ("T10Y", "T13W", "VIX")
    assert data.market.series.value_on("VIX", date(1999, 1, 4)) == 26.17
    assert data.market.series.value_on("T10Y", date(2015, 10, 16)) == 4.653
    assert data.price_fingerprint == research.price_fingerprint_of(before["files"])

    # refreshing another optional file afterwards carries the series over
    research.refresh_fundamentals(store_dir, rs.FACTS_A, data_dir=members)
    assert len(research.load_store(store_dir, data_dir=members).market.series) == 4


def test_refresh_carries_the_side_reports_outside_the_manifest(tmp_path, members):
    # The survivorship-check store keeps its cleaning, coverage and alias reports beside the data,
    # outside the manifest. Phase 5's real run proved a refresh used to drop them on the swap.
    store_dir = tmp_path / "store"
    build(store_dir, members)
    reports = {"cleaning_report.csv": b"symbol,action\nAAA,kept\n", "coverage_report.txt": b"year 1996\n"}
    for name, body in reports.items():
        (store_dir / name).write_bytes(body)

    after = research.refresh_market_series(store_dir, ROWS, data_dir=members)

    assert {n: (store_dir / n).read_bytes() for n in reports} == reports
    assert not set(reports) & set(after["files"])
    research.load_store(store_dir, data_dir=members)


def test_a_store_without_the_file_loads_with_the_empty_series(tmp_path, members):
    store_dir = tmp_path / "store"
    build(store_dir, members)
    assert research.load_store(store_dir, data_dir=members).market.series is EMPTY_SERIES


def test_refresh_refuses_a_row_after_the_window_and_writes_nothing(tmp_path, members):
    store_dir = tmp_path / "store"
    before = build(store_dir, members)
    with pytest.raises(ValueError, match="after DEV_END"):
        research.refresh_market_series(
            store_dir, (("VIX", date(2015, 10, 19), Decimal("20")),), data_dir=members
        )
    assert json.loads((store_dir / research.MANIFEST_FILE).read_text()) == before
    assert not (store_dir / research.MARKET_SERIES_FILE).exists()


HEADER = research.MARKET_SERIES_HEADER


def _read(tmp_path, text):
    path = tmp_path / research.MARKET_SERIES_FILE
    path.write_bytes(text.encode("utf-8"))
    return research._read_market_series(path)


def test_the_reader_returns_ascending_rows_per_series(tmp_path):
    got = _read(tmp_path, f"{HEADER}\nT10Y,1999-01-04,4.653\nVIX,1999-01-04,20\nVIX,1999-01-05,-0.5\n")
    assert got == {
        "T10Y": [(date(1999, 1, 4), 4.653)],
        "VIX": [(date(1999, 1, 4), 20.0), (date(1999, 1, 5), -0.5)],
    }


@pytest.mark.parametrize(
    "text, match",
    [
        ("series,date,close\nVIX,1999-01-04,20\n", "header"),
        (f"{HEADER}\r\nVIX,1999-01-04,20\r\n", "header"),
        (f"{HEADER}\nVIX,1999-01-04,20", "LF"),
        (f"{HEADER}\nSPX,1999-01-04,20\n", "unknown series"),
        (f"{HEADER}\nVIX,1999-01-04\n", "3 fields"),
        (f"{HEADER}\nVIX,1999-13-04,20\n", "bad date"),
        (f"{HEADER}\nVIX,2015-10-19,20\n", "after DEV_END"),
        (f"{HEADER}\nVIX,1993-01-28,20\n", "before STORE_START"),
        (f"{HEADER}\nVIX,1999-01-04,nan\n", "finite"),
        (f"{HEADER}\nVIX,1999-01-04,x\n", "bad number"),
        (f"{HEADER}\nVIX,1999-01-04, 20\n", "bad number"),
        (f"{HEADER}\nVIX,1999-01-04,20\nVIX,1999-01-04,21\n", "sorted"),
        (f"{HEADER}\nVIX,1999-01-05,20\nVIX,1999-01-04,21\n", "sorted"),
        (f"{HEADER}\nVIX,1999-01-04,20\nT10Y,1999-01-04,4.6\n", "sorted"),
    ],
)
def test_the_reader_is_strict(tmp_path, text, match):
    with pytest.raises(ValueError, match=match):
        _read(tmp_path, text)


# ---- lab run refuses a series method on a store without series -----------------------------


class _SeriesAllocator(DividendMonthAllocator):
    market_fields = ("series",)


def _series_method(mid: str = "M0014") -> Method:
    c = dataclasses.replace(
        M0051.candidates[0], id=f"{mid}-VIX", family=mid, allocator=_SeriesAllocator()
    )
    return Method(
        id=mid, name="series test", family="regime", source_kind="knowledge", source_ref="",
        hypothesis="h", expected_failure="f", candidates=(c,),
    )


def test_a_series_method_is_refused_on_a_store_without_series():
    data = smoke_data()
    m = _series_method()
    assert runner.market_aware_candidates(m, "series") == ("M0014-VIX",)
    assert runner.market_aware_candidates(m) == ()  # not gated on the fundamentals panel
    assert len(data.market.series) == 0
    with pytest.raises(store.LabError, match="no market series"):
        runner.preflight_data(data, m)


def test_a_series_method_passes_once_the_store_carries_series():
    data = smoke_data()
    series = MarketSeries({"VIX": [(date(1999, 1, 4), 20.0)]})
    with_series = dataclasses.replace(data, market=data.market.with_series(series))
    assert runner.preflight_data(with_series, _series_method()) is None


# ---- the command ---------------------------------------------------------------------------

TICKERS = sorted({t for s in cmd.SOURCES for t in s.tickers})


def _eod(day, close):
    return {
        "date": day, "open": close, "high": close, "low": close, "close": close,
        "adjusted_close": close, "volume": 0,
    }


def _cache(tmp_path):
    """Two sessions per ticker, plus the edge cases on TNX (scale, holiday, both window edges),
    the VIX3M/VXV splice and a null close on IRX."""
    cache = tmp_path / "market"
    cache.mkdir()
    rows = {t: [_eod("1999-01-04", 20.0), _eod("1999-01-05", 21.5)] for t in TICKERS}
    rows["TNX.INDX"] = [
        _eod("1990-01-02", 79.9),  # before STORE_START
        _eod("1999-01-01", 46.0),  # New Year's Day: not an NYSE session
        _eod("1999-01-04", 46.53),
        _eod("2015-10-16", 20.23),
        _eod("2015-10-19", 20.3),  # after DEV_END
    ]
    rows["VXV.INDX"] = [_eod("1999-01-04", 25.0), _eod("1999-01-05", 26.0)]
    rows["VIX3M.INDX"] = [_eod("1999-01-05", 26.5)]
    rows["IRX.INDX"] = [_eod("1999-01-04", 4.4), _eod("1999-01-05", None)]
    for t, r in rows.items():
        (cache / f"{t}.json").write_text(json.dumps(r), encoding="utf-8")
    return cache


def _args(store_dir, cache, **kw):
    return argparse.Namespace(**{"store": store_dir, "cache": cache, "refresh": False, "dry_run": False, **kw})


EXPECTED = "\n".join(
    [
        research.MARKET_SERIES_HEADER,
        "GOLD,1999-01-04,20",
        "GOLD,1999-01-05,21.5",
        "T10Y,1999-01-04,4.653",
        "T10Y,2015-10-16,2.023",
        "T13W,1999-01-04,4.4",
        "T30Y,1999-01-04,2",
        "T30Y,1999-01-05,2.15",
        "T5Y,1999-01-04,2",
        "T5Y,1999-01-05,2.15",
        "VIX,1999-01-04,20",
        "VIX,1999-01-05,21.5",
        "VIX3M,1999-01-04,25",
        "VIX3M,1999-01-05,26.5",
        "VIX9D,1999-01-04,20",
        "VIX9D,1999-01-05,21.5",
        "VVIX,1999-01-04,20",
        "VVIX,1999-01-05,21.5",
        "VXN,1999-01-04,20",
        "VXN,1999-01-05,21.5",
    ]
) + "\n"


def test_sources_write_exactly_the_store_names_with_the_checked_scaling():
    assert tuple(s.series for s in cmd.SOURCES) == research.MARKET_SERIES_NAMES
    by = {s.series: s for s in cmd.SOURCES}
    assert by["T10Y"].divisor == by["T5Y"].divisor == by["T30Y"].divisor == Decimal(10)
    assert by["T13W"].divisor == Decimal(1)  # IRX is already in percent
    assert by["VIX3M"].tickers == ("VIX3M.INDX", "VXV.INDX")


@pytest.fixture
def store_dir(tmp_path, members, monkeypatch):
    path = tmp_path / "store"
    build(path, members)
    real_load = research.load_store
    monkeypatch.setattr(
        research, "load_store", lambda s, **kw: real_load(s, **{**kw, "data_dir": members})
    )
    return path


def test_the_report_writes_nothing(tmp_path, store_dir, capsys):
    assert cmd.run(_args(store_dir, _cache(tmp_path))) == 0
    out = capsys.readouterr().out
    assert "T10Y" in out and "off-session" in out
    assert "VIX3M: VIX3M.INDX wherever it has a close, else VXV.INDX" in out
    assert "they differ on 1, by at most 0.5 (1999-01-05)" in out
    assert not (store_dir / research.MARKET_SERIES_FILE).exists()


def test_refresh_writes_the_normalized_rows_and_keeps_the_price_fingerprint(tmp_path, store_dir, capsys):
    before = json.loads((store_dir / research.MANIFEST_FILE).read_text())
    assert cmd.run(_args(store_dir, _cache(tmp_path), refresh=True)) == 0
    assert (store_dir / research.MARKET_SERIES_FILE).read_text(encoding="utf-8") == EXPECTED
    after = json.loads((store_dir / research.MANIFEST_FILE).read_text())
    assert research.price_fingerprint_of(after["files"]) == research.price_fingerprint_of(before["files"])
    assert "(unchanged)" in capsys.readouterr().out


def test_dry_run_writes_nothing(tmp_path, store_dir, capsys):
    before = (store_dir / research.MANIFEST_FILE).read_text()
    assert cmd.run(_args(store_dir, _cache(tmp_path), refresh=True, dry_run=True)) == 0
    assert "dry run: would write 19 rows" in capsys.readouterr().out
    assert (store_dir / research.MANIFEST_FILE).read_text() == before
    assert not (store_dir / research.MARKET_SERIES_FILE).exists()


def test_a_missing_cache_file_exits_2_and_writes_nothing(tmp_path, store_dir, capsys):
    cache = _cache(tmp_path)
    (cache / "VXV.INDX.json").unlink()
    assert cmd.run(_args(store_dir, cache, refresh=True)) == 2
    assert "VXV.INDX.json" in capsys.readouterr().out
    assert not (store_dir / research.MARKET_SERIES_FILE).exists()

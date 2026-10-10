"""The survivorship-check store: the cleaning rules (``seer_engine.survivorship``), the build
(``commands/survivorship_store.py``), the ``purpose`` manifest mark (``research``) and the refusal
of a marked store by every trial-writing path. No network and no real cache: every vendor series
here is synthetic, laid on real NYSE sessions, and the source store is ``test_research_store``'s
tiny fixture."""

from __future__ import annotations

import argparse
import dataclasses
import json
from bisect import bisect_left
from datetime import date
from decimal import Decimal
from pathlib import Path

import numpy as np
import pytest
from labkit import smoke_data, smoke_test_data

import test_research_store as rs
from test_research_store import FACTS_A, build
from seer_engine import config, dates, research
from seer_engine import survivorship as sv
from seer_engine.commands import lab as lab_cmd
from seer_engine.commands import survivorship_store as cmd
from seer_engine.lab import remeasure as rm
from seer_engine.lab import runner, store
from seer_engine.lab.seed import seed

SESSIONS = dates.sessions(research.STORE_START, research.DEV_END)
MARK = research.SURVIVORSHIP_PURPOSE


def days_from(start: date, n: int) -> list[date]:
    i = bisect_left(SESSIONS, start)
    return SESSIONS[i : i + n]


def series(
    closes,
    *,
    start: date = date(2000, 1, 3),
    opens=None,
    volumes=None,
    splits=(),
    dividends=(),
    symbol: str = "ZZZ",
    day_list=None,
) -> sv.SourceSeries:
    """A synthetic raw series: one bar per session from ``start`` (or on ``day_list``)."""
    ds = day_list if day_list is not None else days_from(start, len(closes))
    opens = opens if opens is not None else closes
    volumes = volumes if volumes is not None else [1_000_000.0] * len(closes)
    bars = tuple(
        sv.RawBar(d, o, max(o, c) * 1.01, min(o, c) * 0.99, c, v)
        for d, o, c, v in zip(ds, opens, closes, volumes)
    )
    return sv.SourceSeries(
        symbol=symbol, source=sv.EODHD_SOURCE, code=sv.eodhd_code(symbol), bars=bars,
        splits=tuple(splits), dividends=tuple(dividends),
    )


def wave(n: int, base: float = 20.0) -> list[float]:
    """Gentle, deterministic prices: never a one-day move near 1.4x."""
    return [round(base * (1.0 + 0.02 * ((i % 7) - 3) / 3.0), 4) for i in range(n)]


def clean(s: sv.SourceSeries, member=None) -> sv.Cleaned:
    member = member if member is not None else tuple(b.date for b in s.bars)
    return sv.clean_symbol(s, tuple(member), SESSIONS)


def closes(c: sv.Cleaned) -> list[float]:
    return [float(b.close) for b in c.bars]


def max_move(c: sv.Cleaned) -> float:
    cs = closes(c)
    return max(max(b / a, a / b) for a, b in zip(cs, cs[1:]))


# ---- reading the cache ---------------------------------------------------------------------


def test_parse_split_reads_new_over_old_and_refuses_junk():
    assert sv.parse_split("2.000000/1.000000") == 2.0
    assert sv.parse_split("1.000000/10.000000") == pytest.approx(0.1)
    for bad in ("2", "0/1", "x/1", "1/0"):
        with pytest.raises(ValueError):
            sv.parse_split(bad)


def test_read_series_reads_the_three_cache_folders(tmp_path):
    (tmp_path / "eod").mkdir()
    (tmp_path / "splits").mkdir()
    (tmp_path / "dividends").mkdir()
    (tmp_path / "eod" / "BRK.B.json").write_text(json.dumps([
        {"date": "2000-01-04", "open": 10, "high": 11, "low": 9, "close": 10.5, "adjusted_close": 1, "volume": 100},
        {"date": "2000-01-03", "open": None, "high": 11, "low": 9, "close": 10, "adjusted_close": 1, "volume": None},
    ]))
    (tmp_path / "splits" / "BRK.B.json").write_text(json.dumps([{"date": "2010-01-21", "split": "50.000000/1.000000"}]))
    (tmp_path / "dividends" / "BRK.B.json").write_text(json.dumps(
        {"symbol": "BRK.B", "rows": [{"date": "2000-01-04", "value": 0.5, "currency": "USD"}]}
    ))
    (tmp_path / "eod" / "GONE.json").write_text("null")
    s = sv.read_series(tmp_path, "BRK.B")
    assert s.code == "BRK-B.US" and s.source == sv.EODHD_SOURCE
    assert [b.date for b in s.bars] == [date(2000, 1, 3), date(2000, 1, 4)]
    assert s.bars[0].open is None and s.bars[0].volume is None
    assert s.splits == (sv.Split(date(2010, 1, 21), 50.0),)
    assert s.dividends == (sv.RawDividend(date(2000, 1, 4), Decimal("0.5"), "USD"),)
    assert sv.read_series(tmp_path, "GONE").bars == ()
    assert sv.read_series(tmp_path, "NEVER") is None


def test_member_sessions_is_start_inclusive_end_exclusive():
    iv = (("AAA", date(2000, 1, 3), date(2000, 1, 6)), ("BBB", date(2000, 1, 3), None))
    assert sv.member_sessions(iv, "AAA", SESSIONS) == (date(2000, 1, 3), date(2000, 1, 4), date(2000, 1, 5))
    assert sv.member_sessions(iv, "BBB", SESSIONS)[-1] == research.DEV_END
    assert sv.member_sessions(iv, "CCC", SESSIONS) == ()


# ---- the cleaning rules --------------------------------------------------------------------


def test_a_clean_series_is_kept_in_the_dev_store_encoding():
    c = clean(series(wave(60)))
    assert c.action == sv.KEPT and c.reason == "clean"
    assert c.covered_days == c.member_days == 60
    b = c.bars[0]
    assert sv.bar_line("ZZZ", b).startswith("ZZZ,2000-01-03,")
    assert all(len(cell.split(".")[1]) == 4 for cell in sv.bar_line("ZZZ", b).split(",")[2:6])
    assert isinstance(b.volume, int)


def test_a_listed_split_the_raw_prices_need_is_applied():
    raw = wave(40) + [x / 2 for x in wave(40)]
    vols = [1e6] * 40 + [2e6] * 40
    split_day = days_from(date(2000, 1, 3), 80)[40]
    c = clean(series(raw, volumes=vols, splits=[sv.Split(split_day, 2.0)]))
    assert c.action == sv.KEPT and c.splits_applied == 1 and c.splits_skipped == 0
    assert max_move(c) < 1.1
    assert closes(c)[0] == pytest.approx(wave(40)[0] / 2, abs=1e-4)
    assert c.bars[0].volume == 2_000_000


def test_a_listed_split_already_in_the_raw_prices_is_skipped():
    split_day = days_from(date(2000, 1, 3), 80)[40]
    c = clean(series(wave(80), splits=[sv.Split(split_day, 2.0)]))
    assert c.splits_applied == 0 and c.splits_skipped == 1
    assert closes(c) == pytest.approx(wave(80), abs=1e-4)
    assert max_move(c) < 1.1


def test_an_unlisted_split_is_repaired_as_a_scale_break():
    raw = wave(40) + [x / 2 for x in wave(40)]
    vols = [1e6] * 40 + [2e6] * 40
    c = clean(series(raw, volumes=vols))
    assert c.action == sv.REPAIRED and c.scale_repairs == 1
    assert max_move(c) < 1.1
    assert closes(c)[0] == pytest.approx(wave(40)[0] / 2, abs=1e-4)


def test_a_crash_is_kept_even_when_its_close_is_near_a_simple_ratio():
    """CVH 2008-10-22: opened 36% down, closed 51% down, on ten times the volume."""
    pre, post = wave(40, 28.0), wave(40, 13.7)
    opens = pre + [18.3] + post[1:]
    vols = [1.5e6] * 40 + [19e6, 7e6] + [5e6] * 38
    c = clean(series(pre + post, opens=opens, volumes=vols))
    assert c.action == sv.KEPT and c.scale_repairs == 0 and c.moves_kept == 1
    assert closes(c)[40] == pytest.approx(13.7 * (1 + 0.02 * -1), abs=1e-3)


def test_a_spike_that_comes_straight_back_is_removed():
    raw = wave(60)
    raw[30] = raw[29] * 12
    c = clean(series(raw))
    assert c.action == sv.REPAIRED and c.rows_removed == 1
    assert len(c.bars) == 59 and max_move(c) < 1.1


def test_an_island_printed_at_the_wrong_scale_is_rescaled():
    raw = wave(300)
    for i in range(100, 200):
        raw[i] *= 15.0
    c = clean(series(raw))
    assert c.island_repairs == 1 and c.action == sv.REPAIRED
    assert max_move(c) < 1.1


def test_a_quiet_level_shift_inside_the_membership_rescales_the_earlier_rows():
    """EA 2003-11-18: x0.118 on ordinary volume. The later prices stand as printed."""
    raw = wave(100) + [x * 0.12 for x in wave(100)]
    c = clean(series(raw))
    assert c.level_repairs == 1 and c.action == sv.REPAIRED
    assert max_move(c) < 1.1
    assert closes(c)[-1] == pytest.approx(raw[-1], abs=1e-4)


def test_too_many_quiet_moves_drop_the_symbol():
    raw: list[float] = []
    for level in (1.0, 10.0, 2.5, 30.0, 4.0, 50.0):  # five quiet jumps, no two of them cancel
        raw += [x * level for x in wave(40)]
    c = clean(series(raw))
    assert c.action == sv.DROPPED and c.reason.startswith("absurd")
    assert c.bars == ()


def test_a_collapse_at_the_end_of_the_membership_is_kept_without_volume():
    """WAMUQ 2008-09-26: seized overnight, x0.095 two days before it left the index."""
    raw = wave(100) + [0.16, 0.15, 0.14]
    c = clean(series(raw, volumes=[1e6] * 100 + [5e5] * 3))
    assert c.action == sv.KEPT and c.moves_kept == 1
    assert closes(c)[-1] == pytest.approx(0.14, abs=1e-4)


def test_a_reused_ticker_after_a_long_hole_is_cut():
    member = days_from(date(2000, 1, 3), 80)
    later = days_from(date(2001, 1, 2), 40)
    s = series(wave(80) + wave(40, 5.0), day_list=member + later)
    c = clean(s, member=member)
    assert c.action == sv.TRIMMED and c.last == member[-1]
    assert "after the membership" in c.reason


def test_the_tail_ends_a_month_after_the_membership():
    ds = days_from(date(2000, 1, 3), 200)
    c = clean(series(wave(200), day_list=ds), member=ds[:100])
    assert c.last == ds[99 + sv.TAIL_GRACE_SESSIONS]


def test_a_series_that_never_trades_inside_the_membership_is_dropped():
    c = clean(series(wave(40), start=date(1999, 1, 4)), member=days_from(date(2007, 2, 1), 30))
    assert c.action == sv.DROPPED and "another company" in c.reason


def test_no_series_and_a_series_only_after_2015_are_dropped():
    empty = sv.SourceSeries("ZZZ", sv.EODHD_SOURCE, "ZZZ.US", ())
    assert clean(empty, member=days_from(date(2000, 1, 3), 5)).reason == "eodhd has no daily series for ZZZ.US"
    late = series(wave(5), day_list=[date(2020, 1, d) for d in (2, 3, 6, 7, 8)])
    c = clean(late, member=days_from(date(2000, 1, 3), 5))
    assert c.action == sv.DROPPED and "has no session inside" in c.reason


def test_rows_the_loader_would_refuse_are_removed_or_repaired():
    ds = days_from(date(2000, 1, 3), 6)
    bars = (
        sv.RawBar(ds[0], 10.0, 10.5, 9.5, 10.0, 1000.0),
        sv.RawBar(ds[1], 0.0, 10.5, 9.5, 10.1, 1000.0),  # open 0 -> the close
        sv.RawBar(ds[2], 10.0, 9.0, 11.0, 10.2, 1000.0),  # high < low -> widened
        sv.RawBar(ds[3], 10.2, 10.2, 10.2, 10.2, 0.0),  # a filler -> removed
        sv.RawBar(ds[4], None, None, None, None, None),  # no close -> removed
        sv.RawBar(ds[5], 10.0, 40.0, 9.9, 10.1, 1000.0),  # a wick beyond 3x the body -> cut
    )
    c = clean(sv.SourceSeries("ZZZ", sv.EODHD_SOURCE, "ZZZ.US", bars), member=ds)
    assert [b.date for b in c.bars] == [ds[0], ds[1], ds[2], ds[5]]
    assert c.rows_removed == 2 and c.fields_repaired >= 4
    for b in c.bars:
        assert Decimal(0) < b.low <= min(b.open, b.close) <= max(b.open, b.close) <= b.high
    assert c.bars[1].open == c.bars[1].close
    assert c.bars[3].high == Decimal("10.1000")


def test_a_price_that_rounds_to_zero_is_removed():
    raw = wave(30, 0.002)
    raw[10] = 0.00004
    c = clean(series(raw))
    assert all(b.close > 0 for b in c.bars)


def test_dividends_are_clipped_to_the_kept_bars_and_sanity_checked():
    ds = days_from(date(2000, 1, 3), 60)
    divs = [
        sv.RawDividend(date(1999, 6, 1), Decimal("0.1"), "USD"),  # before the bars
        sv.RawDividend(ds[10], Decimal("0.1234567"), "USD"),  # kept, 6 dp
        sv.RawDividend(ds[20], Decimal("9"), "USD"),  # 45% of the price: refused
        sv.RawDividend(ds[30], Decimal("0.1"), "CAD"),  # not USD: refused
        sv.RawDividend(ds[40], None, "USD"),  # no value: ignored
    ]
    c = clean(series(wave(60), day_list=ds, dividends=divs))
    assert c.dividends == ((ds[10], Decimal("0.123457")),)
    assert c.dividends_refused == 2
    assert sv.amount_text(Decimal("0.500000")) == "0.5"


def test_best_of_prefers_coverage_and_ties_go_to_the_first():
    a = sv.Cleaned("ZZZ", "eodhd", "ZZZ.US", sv.KEPT, "clean", covered_days=10)
    b = sv.Cleaned("ZZZ", "alias", "ZZZ1.US", sv.KEPT, "clean", covered_days=20)
    d = sv.Cleaned("ZZZ", "eodhd", "ZZZ.US", sv.DROPPED, "none")
    assert sv.best_of([a, b]) is b
    assert sv.best_of([a, dataclasses.replace(b, covered_days=10)]) is a
    assert sv.best_of([d, a]) is a
    with pytest.raises(ValueError):
        sv.best_of([])
    with pytest.raises(ValueError):
        sv.best_of([a, dataclasses.replace(b, symbol="YYY")])


def test_merge_sorted_lines_inserts_each_group_at_its_place():
    existing = ["AAA,1", "AAA,2", "CCC,1"]
    added = {"BBB": ["BBB,1"], "DDD": ["DDD,1"], "A": ["A,1"]}
    assert list(sv.merge_sorted_lines(existing, added)) == ["A,1", "AAA,1", "AAA,2", "BBB,1", "CCC,1", "DDD,1"]
    with pytest.raises(ValueError):
        list(sv.merge_sorted_lines(existing, {"AAA": ["AAA,3"]}))
    with pytest.raises(ValueError):
        list(sv.merge_sorted_lines(["CCC,1", "AAA,1"], {}))


def test_coverage_by_year_counts_member_days_with_a_bar():
    member = {"AAA": [date(1999, 12, 30), date(1999, 12, 31), date(2000, 1, 3)], "BBB": [date(2000, 1, 3)]}
    before = {"AAA": np.array([date(1999, 12, 31)], dtype="datetime64[D]")}
    after = {**before, "BBB": np.array([date(2000, 1, 3)], dtype="datetime64[D]")}
    assert sv.coverage_by_year(member, before, after) == (
        sv.YearCoverage(1999, 2, 1, 1),
        sv.YearCoverage(2000, 2, 0, 1),
    )


# ---- the purpose mark ----------------------------------------------------------------------


def test_the_survivorship_store_dirs_are_gitignored():
    lines = (config.REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    for entry in ("engine/.research-sv/", "engine/.research-sv.tmp/", "engine/.research-sv.old/"):
        assert entry in lines
    assert research.SV_STORE_DIR == config.REPO_ROOT / "engine" / ".research-sv"


def test_seal_refuses_an_unknown_purpose(tmp_path, members_dir):
    src = tmp_path / "store"
    build(src, members_dir)
    with pytest.raises(ValueError, match="purpose"):
        research._seal(src, {k: 0 for k in research._COUNT_KEYS}, purpose="dev-trials")


def test_an_unknown_purpose_is_refused_at_load(tmp_path, members_dir):
    src = tmp_path / "store"
    build(src, members_dir)
    path = src / research.MANIFEST_FILE
    manifest = json.loads(path.read_text())
    assert research.declared_purpose(src) is None
    assert research.load_store(src, data_dir=members_dir).purpose is None
    manifest["purpose"] = "something-else"
    path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    with pytest.raises(ValueError, match="purpose"):
        research.load_store(src, data_dir=members_dir)
    with pytest.raises(ValueError, match="purpose"):
        research.declared_purpose(src)


# ---- the build -----------------------------------------------------------------------------


@pytest.fixture
def members_dir(tmp_path):
    return rs.members_dir.__wrapped__(tmp_path)


def _write_cache(cache: Path) -> None:
    """GONE (a member 1996-01-02..2000-01-03 the source never served) has a clean EODHD
    series, a dividend with a declaration date, and a reused ticker after a long hole; DDD is
    unknown to EODHD."""
    for sub in ("eod", "splits", "dividends"):
        (cache / sub).mkdir(parents=True)
    gone_days = days_from(date(1997, 12, 31), 560)
    member_part = [d for d in gone_days if d < date(2000, 1, 3)]
    rows = [
        {"date": d.isoformat(), "open": p, "high": p * 1.01, "low": p * 0.99, "close": p,
         "adjusted_close": p, "volume": 500000}
        for d, p in zip(gone_days, wave(len(gone_days), 30.0))
    ]
    rows += [
        {"date": d.isoformat(), "open": 3.0, "high": 3.1, "low": 2.9, "close": 3.0, "adjusted_close": 3.0, "volume": 900}
        for d in days_from(date(2005, 1, 3), 20)
    ]
    (cache / "eod" / "GONE.json").write_text(json.dumps(rows))
    (cache / "splits" / "GONE.json").write_text("null")
    (cache / "dividends" / "GONE.json").write_text(json.dumps({
        "symbol": "GONE", "ticker": "GONE.US", "fetched": "2026-10-10T00:00:00+00:00",
        "rows": [{"date": member_part[100].isoformat(), "value": 0.25, "currency": "USD",
                  "declarationDate": member_part[80].isoformat()}],
    }))
    (cache / "eod" / "DDD.json").write_text("null")


@pytest.fixture
def built(tmp_path, members_dir):
    src = tmp_path / "store"
    build(src, members_dir, facts=FACTS_A)
    cache = tmp_path / "eodhd"
    _write_cache(cache)
    before = {p.name: p.read_bytes() for p in src.iterdir()}
    out = tmp_path / "store-sv"
    plan = cmd.plan_build(src, cache, data_dir=members_dir)
    manifest = cmd.write_store(plan, out, cache, data_dir=members_dir)
    return src, cache, out, plan, manifest, before


def test_the_build_adds_the_cleaned_member_and_marks_the_store(built, members_dir):
    src, _, out, plan, manifest, before = built
    assert {p.name: p.read_bytes() for p in src.iterdir()} == before, "the source is read only"
    assert manifest[research.PURPOSE_KEY] == MARK
    data = research.load_store(out, data_dir=members_dir)
    assert data.purpose == MARK and research.declared_purpose(out) == MARK
    assert "GONE" in data.market.history and data.unserved == ("DDD",)
    assert data.market.history["GONE"].last_date() == date(2000, 2, 1)  # 21 sessions of grace, then the hole
    source = research.load_store(src, data_dir=members_dir)
    assert data.price_fingerprint != source.price_fingerprint
    assert manifest["symbols_served"] == source.manifest["symbols_served"] + 1
    assert manifest["symbols_requested"] == source.manifest["symbols_requested"]
    assert (out / research.FUNDAMENTALS_FILE).read_bytes() == (src / research.FUNDAMENTALS_FILE).read_bytes()
    assert (out / research.FX_FILE).read_bytes() == (src / research.FX_FILE).read_bytes()
    assert data.market.dividends.declared_count() == 1
    assert "DDD,no usable EODHD series: eodhd has no daily series for DDD.US" in (out / research.UNSERVED_FILE).read_text()
    assert plan.cleaned["GONE"].action == sv.TRIMMED


def test_the_reports_sit_inside_the_store_and_outside_the_manifest(built):
    _, _, out, plan, manifest, _ = built
    for name in cmd.REPORT_FILES:
        assert (out / name).is_file() and name not in manifest["files"]
    report = (out / cmd.CLEANING_REPORT).read_text().splitlines()
    assert report[0] == sv.REPORT_HEADER
    assert [line.split(",")[0] for line in report[1:]] == ["DDD", "GONE"]
    assert [line.split(",")[3] for line in report[1:]] == [sv.DROPPED, sv.TRIMMED]
    text = (out / cmd.COVERAGE_REPORT).read_text()
    assert "Members still missing (no bar on any member day): 1" in text and "DDD" in text
    years = {y.year: y for y in plan.coverage}
    assert years[1998].after > years[1998].before


def test_every_bar_row_is_sorted_contiguous_and_dev_encoded(built):
    _, _, out, _, _, _ = built
    lines = (out / research.BARS_FILE).read_text().splitlines()[1:]
    symbols = [line.split(",", 1)[0] for line in lines]
    groups = [s for i, s in enumerate(symbols) if i == 0 or s != symbols[i - 1]]
    assert groups == sorted(set(symbols))
    gone = [line for line in lines if line.startswith("GONE,")]
    assert all(len(cell.split(".")[1]) == 4 for line in gone for cell in line.split(",")[2:6])


def test_a_refresh_keeps_the_mark(built, members_dir):
    _, _, out, _, _, _ = built
    after = research.refresh_fundamentals(out, FACTS_A, data_dir=members_dir)
    assert after[research.PURPOSE_KEY] == MARK
    assert research.load_store(out, data_dir=members_dir).purpose == MARK


def test_the_build_refuses_bad_paths_and_a_marked_source(built, tmp_path, members_dir):
    src, cache, out, plan, _, _ = built
    with pytest.raises(cmd.SurvivorshipStoreError, match="source"):
        cmd.write_store(plan, src, cache, data_dir=members_dir)
    link = tmp_path / "link"
    link.symlink_to(tmp_path / "elsewhere", target_is_directory=True)
    with pytest.raises(cmd.SurvivorshipStoreError, match="symlink"):
        cmd.write_store(plan, link, cache, data_dir=members_dir)
    other = tmp_path / "other"
    build(other, members_dir)
    with pytest.raises(cmd.SurvivorshipStoreError, match="not a survivorship-check store"):
        cmd.write_store(plan, other, cache, data_dir=members_dir)
    with pytest.raises(cmd.SurvivorshipStoreError, match="survivorship-check"):
        cmd.plan_build(out, cache, data_dir=members_dir)
    # rebuilding over an existing survivorship-check store is allowed
    cmd.write_store(plan, out, cache, data_dir=members_dir)


def test_the_command_prints_without_writing_and_reports_a_built_store(built, members_dir, monkeypatch, capsys):
    src, cache, out, _, _, _ = built
    real_load = research.load_store
    monkeypatch.setattr(research, "load_store", lambda s, **kw: real_load(s, **{"data_dir": members_dir, **kw}))
    fresh = out.parent / "fresh-sv"
    args = argparse.Namespace(build=False, report=False, out=fresh, source=src, cache=cache, dry_run=False)
    assert cmd.run(args) == 0
    assert "nothing written" in capsys.readouterr().out and not fresh.exists()
    assert cmd.run(argparse.Namespace(**{**vars(args), "build": True, "dry_run": True})) == 0
    assert not fresh.exists()
    assert cmd.run(argparse.Namespace(**{**vars(args), "out": out, "report": True})) == 0
    assert "member-days" in capsys.readouterr().out
    assert cmd.run(argparse.Namespace(**{**vars(args), "out": src, "report": True})) == 2


# ---- every trial-writing path refuses a marked store ---------------------------------------


@pytest.fixture()
def conn(tmp_path):
    c = store.connect(tmp_path / "lab.sqlite")
    seed(c)
    yield c
    c.close()


def _method():
    from test_lab_runner import _method as make

    return make()


def test_lab_run_refuses_a_marked_store_and_records_nothing(conn):
    n = store.dev_trial_count(conn)
    marked = dataclasses.replace(smoke_data(), purpose=MARK)
    with pytest.raises(store.LabError, match="lab survivorship"):
        runner.run_method(conn, _method(), Path(__file__), marked, git_sha="x", require_commit=False)
    assert store.dev_trial_count(conn) == n
    assert store.get_method(conn, "M0001") is None


def test_lab_test_refuses_a_marked_store_before_anything_else(conn):
    m = _method()
    looks = store.test_looks(conn)
    marked = dataclasses.replace(smoke_test_data(), purpose=MARK)
    with pytest.raises(store.LabError, match="lab survivorship"):
        runner.run_test(conn, m, Path(__file__), m.candidates[0], marked, git_sha="x", require_commit=False)
    assert store.test_looks(conn) == looks


def test_lab_remeasure_refuses_a_marked_store(conn):
    marked = dataclasses.replace(smoke_data(), purpose=MARK)
    rows = conn.execute("SELECT count(*) FROM trial_moments").fetchone()[0]
    with pytest.raises(store.LabError, match="lab survivorship"):
        rm.remeasure(conn, _method(), Path(__file__), marked, require_commit=False)
    with pytest.raises(store.LabError, match="lab survivorship"):
        rm.remeasure_seed(conn, None, marked)
    assert conn.execute("SELECT count(*) FROM trial_moments").fetchone()[0] == rows


def test_lab_run_command_refuses_a_marked_store_by_its_manifest(conn, built):
    _, _, out, _, _, _ = built
    with pytest.raises(store.LabError, match="lab survivorship"):
        lab_cmd._run(conn, argparse.Namespace(method="M0001", store=out, allow_coverage=0.8))


def test_an_unmarked_store_is_not_refused():
    runner.refuse_survivorship_store(smoke_data(), "lab run M0001")
    runner.refuse_survivorship_store(object(), "lab run M0001")

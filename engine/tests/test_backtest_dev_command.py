"""`backtest_dev` command: discovery and flags (no --end), the io writer, the committed-registry
check, the pure report pieces, and end-to-end runs on a synthetic research store written by
research.build_store with a fake downloader and a tiny fake registry: rows equal
dev.run_registry, byte-identical files across two runs, the dirty-registry refusal, --only
writes nothing, and store errors exit 2.

The store has long bars for SPY (from 1993-01-29) and QQQ (from 1999-03-10), short bars (from
2010-01-04) for every other research ETF (research.build_store refuses a store missing one), and
nothing for the index members, which are listed in unserved.csv.
"""

from __future__ import annotations

import functools
import hashlib
import logging
import math
import re
import shutil
import statistics
import subprocess
import zlib
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from seer_engine import cli, config, dates, research, yahoo
from seer_engine.backtest import dev, dev_report
from seer_engine.backtest import io as bio
from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.registry import REGISTRY, SECTOR_ETFS
from seer_engine.backtest.runner import survivorship
from seer_engine.commands import backtest_dev as cmd
from seer_engine.sim.model import Snapshot
from seer_engine.sim.rules import DAILY_SWITCH, DESIGN_V0, MONTHLY_HOLD
from seer_engine.strategies.f_index import TIMING, TimingParams
from seer_engine.strategies.f_rotation import ROTATION, RotationParams

# Every research ETF must be served (phase 4 aborts otherwise); only SPY and QQQ need history.
LAUNCH = {
    **{s: date(2010, 1, 4) for s in research.RESEARCH_ETFS},
    "SPY": date(1993, 1, 29),
    "QQQ": date(1999, 3, 10),
}
ALL_SESSIONS = tuple(dates.sessions(research.STORE_START, research.DEV_END))
FX_FIRST = date(1999, 1, 4)
RUN_DATE = date(2031, 1, 2)
DURATION = re.compile(r"\((\d+\.\d{2})s\)")
ADDED = date(2026, 10, 3)

FAKE_REGISTRY = (
    Candidate(
        id="T-REF-SPY-HOLD",
        family="REF",
        rules=MONTHLY_HOLD,
        allocator=TIMING,
        params=TimingParams(hold="SPY", signal="SPY", rule="always", n=1),
        rationale="test: SPY held monthly",
        added=ADDED,
        owner_inputs=(),
    ),
    Candidate(
        id="T-F1-SPY-SMA20-D",
        family="F1",
        rules=DAILY_SWITCH,
        allocator=TIMING,
        params=TimingParams(hold="SPY", signal="SPY", rule="sma", n=20),
        rationale="test: SPY above its 20-day SMA, checked nightly",
        added=ADDED,
        owner_inputs=(),
    ),
    Candidate(
        id="T-F2-SPYQQQ-3M",
        family="F2",
        rules=MONTHLY_HOLD,
        allocator=ROTATION,
        params=RotationParams(universe=("QQQ", "SPY"), lookback=63, top=1, absolute=True, fallback=None, trend=None),
        rationale="test: 3-month dual momentum over QQQ and SPY",
        added=ADDED,
        owner_inputs=(),
    ),
)
FAKE_IDS = tuple(c.id for c in FAKE_REGISTRY)


@functools.cache
def _series(symbol: str) -> pd.DataFrame:
    """One symbol's full synthetic yfinance frame (actions=True columns), launch..DEV_END."""
    sess = [d for d in ALL_SESSIONS if d >= LAUNCH[symbol]]
    n = len(sess)
    rng = np.random.default_rng(zlib.crc32(symbol.encode()))
    close = np.round(50.0 * np.exp(np.cumsum(rng.normal(0.0003, 0.011, n))), 2)
    prev = np.concatenate(([close[0]], close[:-1]))
    open_ = np.round(prev * (1.0 + rng.normal(0.0, 0.003, n)), 2)
    high = np.round(np.maximum(open_, close) * (1.0 + np.abs(rng.normal(0.0, 0.004, n))), 2)
    low = np.round(np.minimum(open_, close) * (1.0 - np.abs(rng.normal(0.0, 0.004, n))), 2)
    divs = np.zeros(n)
    paid: set[tuple[int, int]] = set()
    for i, d in enumerate(sess):
        if d.month in (3, 6, 9, 12) and d.day >= 15 and (d.year, d.month) not in paid:
            paid.add((d.year, d.month))
            divs[i] = 0.5 if symbol == "SPY" else 0.1
    return pd.DataFrame(
        {
            "Open": open_,
            "High": high,
            "Low": low,
            "Close": close,
            "Adj Close": close,
            "Volume": np.full(n, 1.0e7),
            "Dividends": divs,
            "Stock Splits": np.zeros(n),
        },
        index=pd.DatetimeIndex([pd.Timestamp(d) for d in sess]),
    )


def fake_download(tickers: list[str], start: date, end_exclusive: date) -> pd.DataFrame:
    """yfinance group_by='ticker' shape: MultiIndex (Ticker, Price), outer-joined dates."""
    parts: dict[str, pd.DataFrame] = {}
    for t in tickers:
        symbol = yahoo.from_yahoo(t)
        if symbol in LAUNCH:
            f = _series(symbol)
            mask = (f.index >= pd.Timestamp(start)) & (f.index < pd.Timestamp(end_exclusive))
            parts[t] = f[mask]
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, axis=1)


def fake_fx(start: date, end: date) -> list[tuple[date, Decimal]]:
    a = max(start, FX_FIRST)
    if end < a:
        return []
    return [(d, Decimal("9000")) for d in dates.sessions(a, end)]


def git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=seer-test", "-c", "user.email=seer-test@example.invalid",
         "-c", "commit.gpgsign=false", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


def committed_file(root: Path, name: str = "registry.py", text: str = "REGISTRY = ()\n") -> Path:
    repo = root / "repo"
    repo.mkdir(parents=True)
    git(repo, "init", "-q")
    path = repo / name
    path.write_text(text, encoding="utf-8")
    git(repo, "add", name)
    git(repo, "commit", "-q", "-m", "registry")
    return path


@pytest.fixture(scope="module")
def store(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("research") / "store"
    research.build_store(path, downloader=fake_download, fetch_fx=fake_fx, sleep=lambda _s: None)
    return path


@pytest.fixture(scope="module")
def data(store: Path) -> research.ResearchData:
    return research.load_store(store)


@pytest.fixture(scope="module")
def executed(store: Path, data: research.ResearchData):
    return cmd.execute(
        data,
        FAKE_REGISTRY,
        unserved=cmd.read_unserved(store),
        registry_digest="0" * 64,
        run_date=RUN_DATE,
    )


@pytest.fixture
def fake_registry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    path = committed_file(tmp_path)
    monkeypatch.setattr(cmd, "load_registry", lambda: FAKE_REGISTRY)
    monkeypatch.setattr(cmd, "REGISTRY_PATH", path)
    return path


def argv(store: Path, tmp_path: Path, tag: str, *extra: str) -> list[str]:
    return [
        "backtest_dev",
        "--store", str(store),
        "--out", str(tmp_path / f"out-{tag}"),
        "--plans", str(tmp_path / f"plans-{tag}"),
        "--run-date", RUN_DATE.isoformat(),
        *extra,
    ]


def expected_names() -> tuple[list[str], str]:
    stem = dev_report.report_stem(RUN_DATE)
    return [f"{stem}.md", f"{stem}-rows.csv", f"{stem}-curves.csv", f"{stem}-frontier.svg"], dev_report.preregistration_name(RUN_DATE)


# ------------------------------------------------------------------ contract and flags


def test_research_and_dev_constants_agree():
    # Plan index D-I: phase 9's pure dev.py cannot import research, so the duplicates are pinned here.
    assert research.DEV_END == dev.DEV_END == date(2015, 10, 16)
    assert research.MEMBERSHIP_START == dev.MEMBERSHIP_START
    assert research.FX_START == dev.FX_START


def test_registry_reads_only_research_etfs():
    # Plan index D-I: phase 11's pure registry.py cannot import research either.
    assert SECTOR_ETFS == research.SECTOR_ETFS
    needed: set[str] = set()
    for c in REGISTRY:
        if c.rules is DESIGN_V0:
            continue
        needed |= set(c.allocator.symbols(c.params)) | set(c.allocator.holds(c.params))
        if c.rules.idle_symbol is not None:
            needed.add(c.rules.idle_symbol)
    assert needed <= set(research.RESEARCH_ETFS), sorted(needed - set(research.RESEARCH_ETFS))


def test_discovered_with_defaults():
    assert "backtest_dev" in cli.discover()
    args = cli.build_parser().parse_args(["backtest_dev"])
    assert args._run is cmd.run
    assert args.store == research.STORE_DIR
    assert args.out == cmd.DEFAULT_OUT == config.REPO_ROOT / "docs" / "backtests"
    assert args.plans == cmd.DEFAULT_PLANS == config.REPO_ROOT / "docs" / "plans"
    assert (args.run_date, args.only) == (None, None)
    assert cmd.REGISTRY_PATH.name == "registry.py"
    assert cmd.REGISTRY_PATH.parent.name == "backtest"
    assert cmd.HELP


def test_help_lists_every_flag_and_no_end(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["backtest_dev", "--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    for flag in ("--store", "--out", "--plans", "--run-date", "--only"):
        assert flag in out, flag
    assert "--end" not in out


@pytest.mark.parametrize("extra", [["--end", "2016-01-04"], ["--run-date", "someday"], ["--only"]])
def test_bad_argument_is_a_usage_error(extra):
    with pytest.raises(SystemExit) as exc:
        cli.build_parser().parse_args(["backtest_dev", *extra])
    assert exc.value.code == 2


# ------------------------------------------------------------------ io writer


def test_write_dev_report_writes_five_files_in_order_with_lf(tmp_path, monkeypatch):
    texts = {
        "render_markdown": "# md\nline\n",
        "rows_csv": "id,family\n",
        "curves_csv": "date,spy_tr\n",
        "frontier_svg": "<svg>frontier</svg>\n",
        "render_preregistration": "# pre-registration\n",
    }
    for name, text in texts.items():
        monkeypatch.setattr(dev_report, name, lambda report, _t=text: _t)
    report = SimpleNamespace(run_date=RUN_DATE)
    paths = bio.write_dev_report(tmp_path / "nested" / "out", tmp_path / "nested" / "plans", report)
    names, prereg = expected_names()
    assert [p.name for p in paths] == [*names, prereg]
    assert [p.parent.name for p in paths] == ["out"] * 4 + ["plans"]
    assert [p.read_bytes() for p in paths] == [t.encode("utf-8") for t in texts.values()]


def test_write_dev_report_renders_everything_before_writing(tmp_path, monkeypatch):
    for name in ("render_markdown", "rows_csv", "curves_csv", "frontier_svg"):
        monkeypatch.setattr(dev_report, name, lambda report: "ok\n")

    def boom(report):
        raise RuntimeError("pre-registration render failed")

    monkeypatch.setattr(dev_report, "render_preregistration", boom)
    with pytest.raises(RuntimeError, match="pre-registration render failed"):
        bio.write_dev_report(tmp_path / "out", tmp_path / "plans", SimpleNamespace(run_date=RUN_DATE))
    assert not (tmp_path / "out").exists()
    assert not (tmp_path / "plans").exists()


# ------------------------------------------------------------------ registry state


def test_registry_problem_tracks_every_uncommitted_state(tmp_path):
    path = committed_file(tmp_path)
    assert cmd.registry_problem(path) is None
    path.write_text("REGISTRY = (1,)\n", encoding="utf-8")
    assert "uncommitted" in cmd.registry_problem(path)
    git(path.parent, "add", path.name)
    assert "uncommitted" in cmd.registry_problem(path)  # staged, not committed
    git(path.parent, "commit", "-q", "-m", "append")
    assert cmd.registry_problem(path) is None
    untracked = path.parent / "other.py"
    untracked.write_text("x = 1\n", encoding="utf-8")
    assert "uncommitted" in cmd.registry_problem(untracked)
    outside = tmp_path / "loose"
    outside.mkdir()
    (outside / "registry.py").write_text("REGISTRY = ()\n", encoding="utf-8")
    assert cmd.registry_problem(outside / "registry.py") is not None  # not a git repository


def test_registry_digest_is_the_sha256_of_the_file_bytes(tmp_path):
    path = tmp_path / "registry.py"
    path.write_bytes(b"REGISTRY = ()\n")
    assert cmd.registry_digest(path) == hashlib.sha256(b"REGISTRY = ()\n").hexdigest()


# ------------------------------------------------------------------ pure pieces


def test_select_keeps_registry_order_dedupes_and_rejects_unknown():
    assert cmd.select(FAKE_REGISTRY, None) == FAKE_REGISTRY
    picked = cmd.select(FAKE_REGISTRY, ["T-F2-SPYQQQ-3M", "T-REF-SPY-HOLD", "T-F2-SPYQQQ-3M"])
    assert [c.id for c in picked] == ["T-REF-SPY-HOLD", "T-F2-SPYQQQ-3M"]
    with pytest.raises(cmd.BacktestDevError, match="NOPE-1, NOPE-2"):
        cmd.select(FAKE_REGISTRY, ["NOPE-2", "T-REF-SPY-HOLD", "NOPE-1"])


def test_month_end_curve_normalizes_and_keeps_each_months_last_snapshot():
    snaps = [
        Snapshot(date(2015, 1, 30), Decimal("100"), Decimal("100")),
        Snapshot(date(2015, 2, 2), Decimal("0"), Decimal("110")),
        Snapshot(date(2015, 2, 27), Decimal("0"), Decimal("120")),
        Snapshot(date(2015, 3, 2), Decimal("0"), Decimal("90")),
    ]
    assert cmd.month_end_curve(snaps) == (
        (date(2015, 1, 30), 1.0),
        (date(2015, 2, 27), 1.2),
        (date(2015, 3, 2), 0.9),
    )
    with pytest.raises(ValueError):
        cmd.month_end_curve([])


def _row(cid: str, mar, years=(), returns=(), sharpe=None):
    return SimpleNamespace(
        candidate=SimpleNamespace(id=cid),
        mar=mar,
        stats=SimpleNamespace(year_returns=tuple(years), daily_returns=tuple(returns), sharpe=sharpe),
    )


def test_top_years_lists_finalists_first_then_by_mar():
    rows = [_row(f"C{k}", mar, years=((2000, k / 100),)) for k, mar in enumerate([0.5, None, 2.0, 1.0, 2.0, 0.1, 0.3])]
    finals = [rows[3]]  # C3, MAR 1.0, ranked below C2 and C4
    got = cmd.top_years(rows, finals)
    assert [cid for cid, _ in got] == ["C3", "C2", "C4", "C0", "C6"]
    assert got[0][1] == ((2000, 0.03),)
    assert [cid for cid, _ in cmd.top_years(rows, [])] == ["C2", "C4", "C3", "C0", "C6"]


def test_daily_moments_hand_checked():
    r = [0.01, -0.01, 0.02, 0.0, 0.03]
    mean = sum(r) / 5
    d = [x - mean for x in r]
    m2 = sum(x * x for x in d) / 5
    m3 = sum(x ** 3 for x in d) / 5
    m4 = sum(x ** 4 for x in d) / 5
    sr, skew, kurt = cmd.daily_moments(r)
    assert sr == pytest.approx(mean / math.sqrt(m2), rel=1e-12)
    assert skew == pytest.approx(m3 / m2 ** 1.5, rel=1e-12)
    assert kurt == pytest.approx(m4 / m2 ** 2, rel=1e-12)
    assert cmd.daily_moments([0.01]) is None
    assert cmd.daily_moments([0.01, 0.01, 0.01]) is None


def test_deflated_sharpes_use_every_trial_and_fall_back_to_the_best_sharpe():
    a = _row("A", 1.0, returns=[0.01, -0.005, 0.02, 0.0, 0.004], sharpe=1.5)
    b = _row("B", 0.5, returns=[0.002, -0.01, 0.005, 0.001, -0.002], sharpe=0.2)
    c = _row("C", None, returns=[], sharpe=None)
    sr_a, skew_a, kurt_a = cmd.daily_moments(a.stats.daily_returns)
    sr_b = cmd.daily_moments(b.stats.daily_returns)[0]
    var = statistics.variance([sr_a, sr_b])
    expected = dev.deflated_sharpe(sr_a, 3, var, 5, skew_a, kurt_a)
    assert cmd.deflated_sharpes([a, b, c], []) == (("A", expected),)
    assert cmd.deflated_sharpes([a, b, c], [b, a])[1] == ("A", expected)
    assert cmd.deflated_sharpes([c], []) == ()
    assert cmd.deflated_sharpes([a], [a]) == (("A", None),)  # one trial: undefined


def test_estimate_full_run_by_class():
    t = (
        cmd.Timing("T-REF-SPY-HOLD", cmd.estimate_class(FAKE_REGISTRY[0]), 12.0),
        cmd.Timing("T-F2-SPYQQQ-3M", cmd.estimate_class(FAKE_REGISTRY[2]), 23.0),
    )
    # REF (12) + F1 daily: no timed class -> mean of all, 17.5 + ROT (23).
    assert cmd.estimate_full_run(FAKE_REGISTRY, t) == pytest.approx(12.0 + 17.5 + 23.0)
    assert cmd.estimate_full_run(FAKE_REGISTRY, ()) == 0.0


def test_store_counts_and_unserved(store, data):
    counts = cmd.store_counts(data.manifest)
    assert tuple(counts) == cmd.STORE_COUNT_KEYS
    assert all(isinstance(v, int) and v >= 0 for v in counts.values())
    unserved = cmd.read_unserved(store)
    assert unserved == tuple(sorted(set(unserved)))
    assert "SPY" not in unserved and "QQQ" not in unserved
    assert unserved  # every vendored member is served nothing by the fake downloader
    with pytest.raises(ValueError, match="no 'bar_rows'"):
        cmd.store_counts({})


# ------------------------------------------------------------------ execute


def test_execute_rows_equal_run_registry_and_fields(store, data, executed):
    report, timings = executed
    assert report.rows == dev.run_registry(data.market, data.dividends, data.spy_dividends, FAKE_REGISTRY)
    assert tuple(r.candidate.id for r in report.rows) == FAKE_IDS
    assert report.finalists == dev.finalists(report.rows)
    assert report.survivorship == survivorship(data.market, dev.MEMBERSHIP_START, dev.DEV_END)
    assert report.spy_window == (min(r.start for r in report.rows), dev.DEV_END)
    assert report.store_fingerprint == data.fingerprint
    assert report.store_counts == cmd.store_counts(data.manifest)
    assert report.unserved == cmd.read_unserved(store)
    assert report.run_date == RUN_DATE
    assert tuple(cid for cid, _ in report.curves) == FAKE_IDS
    for _, curve in report.curves:
        assert curve[0][1] == 1.0
        assert curve[-1][0] == dev.DEV_END
    assert all(r.end == dev.DEV_END for r in report.rows)
    assert report.rows[2].start > LAUNCH["QQQ"]  # the rotation waits for QQQ's lookback
    assert report.top_years == cmd.top_years(report.rows, report.finalists)
    assert report.dsr == cmd.deflated_sharpes(report.rows, report.finalists)
    assert [t.candidate_id for t in timings] == list(FAKE_IDS)


def test_execute_twice_is_equal(store, data, executed):
    again = cmd.execute(
        data, FAKE_REGISTRY, unserved=cmd.read_unserved(store), registry_digest="0" * 64, run_date=RUN_DATE
    )
    assert again[0] == executed[0]


def test_run_candidates_logs_every_candidate_and_prepares_once(data, caplog, monkeypatch):
    calls: list[str] = []
    for allocator in (TIMING, ROTATION):
        real = allocator.prepare
        monkeypatch.setattr(
            allocator, "prepare", lambda history, _real=real, _id=allocator.id: (calls.append(_id), _real(history))[1]
        )
    caplog.set_level(logging.INFO, logger=cmd.__name__)
    rows, curves, timings = cmd.run_candidates(data.market, data.dividends, data.spy_dividends, FAKE_REGISTRY)
    messages = [r.getMessage() for r in caplog.records if r.name == cmd.__name__]
    for k, cid in enumerate(FAKE_IDS, start=1):
        line = [m for m in messages if m.startswith(f"[{k}/3] {cid} ")]
        assert len(line) == 1, cid
        assert DURATION.search(line[0])
    assert calls == ["F1", "ROT"]  # dev.run_registry: TIMING once for two candidates, ROTATION once
    assert [t.candidate_id for t in timings] == list(FAKE_IDS)
    assert all(t.seconds >= 0.0 for t in timings)
    assert tuple(cid for cid, _ in curves) == FAKE_IDS


# ------------------------------------------------------------------ end to end


def test_full_run_writes_byte_identical_files(store, tmp_path, fake_registry):
    assert cli.main(argv(store, tmp_path, "1")) == 0
    assert cli.main(argv(store, tmp_path, "2")) == 0
    names, prereg = expected_names()
    for tag in ("1", "2"):
        assert sorted(p.name for p in (tmp_path / f"out-{tag}").iterdir()) == sorted(names)
        assert [p.name for p in (tmp_path / f"plans-{tag}").iterdir()] == [prereg]
    pairs = [(tmp_path / "out-1" / n, tmp_path / "out-2" / n) for n in names]
    pairs.append((tmp_path / "plans-1" / prereg, tmp_path / "plans-2" / prereg))
    for a, b in pairs:
        assert a.read_bytes() == b.read_bytes(), a.name
        text = a.read_text(encoding="utf-8")
        # The run date is in file names only, and so in the links between the sibling files
        # (plan index Decisions, "Report file names"): strip those names, then nothing may remain.
        unlinked = text
        for name in (*names, prereg):
            unlinked = unlinked.replace(name, "")
        assert RUN_DATE.isoformat() not in unlinked, a.name
        assert "\r" not in text, a.name


@pytest.mark.parametrize("state", ["modified", "untracked"])
def test_full_run_refuses_an_uncommitted_registry(store, tmp_path, monkeypatch, state):
    if state == "modified":
        path = committed_file(tmp_path)
        path.write_text("REGISTRY = (1,)\n", encoding="utf-8")
    else:
        path = committed_file(tmp_path, name="other.py")
        path = path.parent / "registry.py"
        path.write_text("REGISTRY = ()\n", encoding="utf-8")
    monkeypatch.setattr(cmd, "REGISTRY_PATH", path)
    monkeypatch.setattr(cmd, "load_registry", lambda: FAKE_REGISTRY)

    def no_store(*_a, **_k):
        raise AssertionError("the store must not be loaded after a refusal")

    monkeypatch.setattr(research, "load_store", no_store)
    assert cli.main(argv(store, tmp_path, "x")) == 2
    assert not (tmp_path / "out-x").exists()
    assert not (tmp_path / "plans-x").exists()


def test_only_writes_nothing_even_with_a_dirty_registry(store, tmp_path, monkeypatch, caplog):
    path = committed_file(tmp_path)
    path.write_text("REGISTRY = (1,)\n", encoding="utf-8")
    monkeypatch.setattr(cmd, "REGISTRY_PATH", path)
    monkeypatch.setattr(cmd, "load_registry", lambda: FAKE_REGISTRY)
    assert cli.main(argv(store, tmp_path, "o", "--only", "T-F2-SPYQQQ-3M", "T-REF-SPY-HOLD")) == 0
    assert not (tmp_path / "out-o").exists()
    assert not (tmp_path / "plans-o").exists()
    messages = [r.getMessage() for r in caplog.records if r.name == cmd.__name__]
    assert any(m.startswith("[1/2] T-REF-SPY-HOLD ") for m in messages)
    assert any(m.startswith("[2/2] T-F2-SPYQQQ-3M ") for m in messages)
    assert any(m.startswith("estimated full run: ") for m in messages)


def test_only_unknown_id_exits_2(store, tmp_path, fake_registry):
    assert cli.main(argv(store, tmp_path, "u", "--only", "NOPE")) == 2
    assert not (tmp_path / "out-u").exists()


def test_missing_store_exits_2(tmp_path, fake_registry):
    assert cli.main(argv(tmp_path / "no-store", tmp_path, "m")) == 2
    assert not (tmp_path / "out-m").exists()


def test_tampered_store_exits_2(store, tmp_path, fake_registry):
    copy = tmp_path / "store"
    shutil.copytree(store, copy)
    bars_csv = copy / "bars.csv"
    raw = bars_csv.read_bytes()
    bars_csv.write_bytes(raw[:-2] + (b"9" if raw[-2:-1] != b"9" else b"8") + raw[-1:])
    assert cli.main(argv(copy, tmp_path, "t")) == 2
    assert not (tmp_path / "out-t").exists()

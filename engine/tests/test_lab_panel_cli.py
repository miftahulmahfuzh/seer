"""``lab panel``, ``lab panel-map`` and ``lab next-signal-id`` (SERA_SIGNAL_PANEL_PLAN.md phase 3).

What is proven here is the command, not the statistics (``test_lab_panel.py`` owns those): which
signals it measures, what it refuses before a store loads, that the two stores are never alive at
once, that a panel is recorded on both stores in one transaction or not at all, that a repeat loads
nothing, and that none of it moves the lab's N, the luck gate's N or the test-window looks.
"""

from __future__ import annotations

import json
import subprocess
import weakref
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from labkit import BASE_ETFS, LAB_PRICE_FINGERPRINT, smoke_data, smoke_history

from seer_engine import cli, dates, research
from seer_engine.backtest.dev import DEV_END
from seer_engine.backtest.market import Market, Membership
from seer_engine.lab import panel, signal, store
from seer_engine.lab.seed import seed

SV = research.SURVIVORSHIP_PURPOSE
# 2005, not 2007: F4's screen needs 253 bars, so a 2007 start gives the pre-2009 era exactly
# panel.MIN_ERA_MONTHS (12) months, one short of losing it. 2005 gives about 36.
WIDE_FIRST = date(2005, 1, 3)


# ---- fixtures ----------------------------------------------------------------------------------


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "commit.gpgsign=false", *args], cwd=cwd, check=True, capture_output=True)


def _last_close(history, market, pool, data_date):
    return {s: float(history[s].close[-1]) for s in pool if s in history and len(history[s].close)}


def _low_close(history, market, pool, data_date):
    return {s: -float(history[s].close[-1]) for s in pool if s in history and len(history[s].close)}


def _signal(sid: str, name: str, score=_last_close) -> signal.Signal:
    return signal.Signal(
        id=sid, name=name, family="test-family", source_kind="knowledge", source_ref="",
        hypothesis="h", expected_failure="f", lookback=1, score=score,
    )


@pytest.fixture()
def lab(tmp_path):
    path = tmp_path / "lab.sqlite"
    conn = store.connect(path)
    seed(conn)
    yield conn, path
    conn.close()


@pytest.fixture()
def signals(tmp_path, monkeypatch):
    """Three committed signal files in a tmp git repo; ``signal.discover`` answers with them."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "test")
    found: dict[str, tuple[signal.Signal, Path]] = {}
    for sid, name, score in (
        ("S0901", "Recent winners", _last_close),
        ("S0902", "Cheap names", _low_close),
        ("S0903", "Recent winners again", _last_close),
    ):
        path = repo / f"s{sid[1:]}_test.py"
        path.write_text(f"# {sid}\n", encoding="utf-8")
        found[sid] = (_signal(sid, name, score), path)
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "signals")
    monkeypatch.setattr(signal, "discover", lambda: dict(found))
    return repo, found


def _dirs(tmp_path: Path, dev_manifest=None, sv_manifest=None) -> tuple[Path, Path]:
    d, s = tmp_path / "dev-store", tmp_path / "sv-store"
    d.mkdir(exist_ok=True)
    s.mkdir(exist_ok=True)
    (d / "manifest.json").write_text(json.dumps({"fingerprint": "smoke"} if dev_manifest is None else dev_manifest))
    (s / "manifest.json").write_text(json.dumps(
        {"fingerprint": "smoke-sv", "purpose": SV} if sv_manifest is None else sv_manifest
    ))
    return d, s


def _dev() -> research.ResearchData:
    """The smoke store carrying the seeded benchmark's prices: D10 (``hardgate.pin_dev_store``)
    refuses any other dev store on a lab that has a benchmark, and ``seed()`` records one."""
    return replace(smoke_data(), price_fingerprint=LAB_PRICE_FINGERPRINT)


def _sv(data: research.ResearchData, fingerprint: str = "smoke-sv") -> research.ResearchData:
    return replace(data, fingerprint=fingerprint, price_fingerprint=fingerprint,
                   manifest={"purpose": SV}, purpose=SV)


def _loader(by_dir, alive_at_load=None):
    """research.load_store, keyed on the directory; a fresh object per call so a test can watch
    the previous store die before the next is handed out."""
    returned: list[weakref.ref] = []

    def load(store_dir, **kw):
        got = by_dir[Path(store_dir)]
        if isinstance(got, BaseException):
            raise got
        if alive_at_load is not None:
            alive_at_load.append(sum(1 for r in returned if r() is not None))
        fresh = replace(got)
        returned.append(weakref.ref(fresh))
        return fresh

    return load


def _boom(*a, **k):
    raise AssertionError("a store must not be loaded here")


def _reading(slope: float, picks: str) -> panel.PanelReading:
    stats = tuple(
        panel.EraStats(era=era, months=months, mean_pool=400.0, mean_scored=380.0, ic_mean=0.02,
                       ic_t=2.1, spread_top=0.03, spread_t=1.8, fm_slope=slope, fm_t=2.5,
                       top_turnover=0.4)
        for era, months in zip(panel.ERAS, (237, 168, 69))
    )
    return panel.PanelReading(stats=stats, picks_hash=picks, dropped_exits=0)


@pytest.fixture()
def fake_panel(monkeypatch):
    """Canned readings per signal id; every measure call is logged as (store fingerprint, id)."""
    readings = {"S0901": _reading(0.004, "a" * 64), "S0902": _reading(0.001, "b" * 64),
                "S0903": _reading(0.002, "a" * 64)}
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(panel, "build_frame", lambda data: ("frame", str(data.fingerprint)))
    monkeypatch.setattr(panel, "signal_scorer", lambda sig: sig.id)

    def measure(frame, scorer, *, mode="score"):
        calls.append((frame[1], scorer))
        return readings[scorer]

    monkeypatch.setattr(panel, "measure", measure)
    return readings, calls


@pytest.fixture()
def stores(tmp_path, monkeypatch):
    d, s = _dirs(tmp_path)
    monkeypatch.setattr(research, "load_store", _loader({d: _dev(), s: _sv(smoke_data())}))
    return d, s


def _lab(path: Path, *argv: str) -> int:
    return cli.main(["lab", "--db", str(path), *argv])


def _panel(path: Path, d: Path, s: Path, *argv: str) -> int:
    return _lab(path, "panel", *argv, "--store", str(d), "--sv-store", str(s))


def _results(conn) -> list[tuple]:
    return [tuple(r) for r in conn.execute(
        "SELECT signal_id, store_role, store_fingerprint, era FROM panel_results ORDER BY 1, 2, 4"
    )]


def _signal_ids(conn) -> list[str]:
    return [r[0] for r in conn.execute("SELECT id FROM panel_signals ORDER BY id")]


def _counts(conn) -> tuple[int, int, int]:
    return store.dev_trial_count(conn), store.gate(conn).n, store.test_looks(conn)


# ---- lab panel: recording ----------------------------------------------------------------------


def test_panel_records_both_stores_and_every_era_once(lab, signals, stores, fake_panel, capsys):
    conn, path = lab
    d, s = stores
    before = _counts(conn)
    assert _panel(path, d, s, "S0901") == 0
    out = capsys.readouterr().out
    assert _signal_ids(conn) == ["S0901"]
    assert _results(conn) == sorted(
        [("S0901", "dev", "smoke", era) for era in panel.ERAS]
        + [("S0901", "survivorship", "smoke-sv", era) for era in panel.ERAS],
        key=lambda r: (r[0], r[1], r[3]),
    )
    row = conn.execute(
        "SELECT months, ic_mean, ic_t, spread_top, spread_t, fm_slope, fm_t FROM panel_results "
        "WHERE signal_id = 'S0901' AND store_role = 'dev' AND era = 'all'"
    ).fetchone()
    assert tuple(row) == (237, 0.02, 2.1, 0.03, 1.8, 0.004, 2.5)
    sha = conn.execute("SELECT source_sha FROM panel_signals WHERE id = 'S0901'").fetchone()[0]
    assert sha == signal.source_sha(signals[1]["S0901"][1])
    assert _counts(conn) == before
    assert "1 signal(s) recorded" in out
    assert f"Lab N (dev trials): {before[0]} before, {before[0]} after" in out
    assert f"luck gate N = {before[1]} before, {before[1]} after" in out


def test_a_repeat_loads_no_store_and_records_nothing(lab, signals, stores, fake_panel, monkeypatch, capsys):
    conn, path = lab
    d, s = stores
    assert _panel(path, d, s, "S0901") == 0
    rows = _results(conn)
    monkeypatch.setattr(research, "load_store", _boom)
    capsys.readouterr()
    assert _panel(path, d, s, "S0901") == 0
    out = capsys.readouterr().out
    assert "already panelled" in out and "nothing to measure" in out
    assert _results(conn) == rows


def test_the_real_evaluator_records_what_it_measures(lab, signals, tmp_path, monkeypatch):
    conn, path = lab
    d, s = _dirs(tmp_path, {"fingerprint": "wide"}, {"fingerprint": "wide-sv", "purpose": SV})
    dev_data, sv_data = _wide_data(), _sv(_wide_data(), "wide-sv")
    monkeypatch.setattr(research, "load_store", _loader({d: dev_data, s: sv_data}))
    assert _panel(path, d, s, "S0901") == 0
    sig = signals[1]["S0901"][0]
    for role, data in (("dev", dev_data), ("survivorship", sv_data)):
        want = panel.measure(panel.build_frame(data), panel.signal_scorer(sig))
        got = conn.execute(
            "SELECT era, months, fm_slope, picks_hash FROM panel_results "
            "WHERE signal_id = 'S0901' AND store_role = ? ORDER BY era", (role,)
        ).fetchall()
        assert sorted((r[0], r[1], r[2], r[3]) for r in got) == sorted(
            (e.era, e.months, e.fm_slope, want.picks_hash) for e in want.stats
        )
        assert any(r[0] == "all" for r in got)


def test_jobs_change_only_the_time(signals, tmp_path, monkeypatch):
    d, s = _dirs(tmp_path, {"fingerprint": "wide"}, {"fingerprint": "wide-sv", "purpose": SV})
    monkeypatch.setattr(research, "load_store",
                        _loader({d: _wide_data(), s: _sv(_wide_data(), "wide-sv")}))
    got = []
    for jobs in ("1", "2"):
        path = tmp_path / f"lab-{jobs}.sqlite"
        conn = store.connect(path)
        assert _panel(path, d, s, "S0901", "S0902", "--jobs", jobs) == 0
        got.append([tuple(r) for r in conn.execute(
            "SELECT signal_id, store_role, era, months, ic_mean, spread_top, fm_slope, fm_t, "
            "picks_hash FROM panel_results ORDER BY 1, 2, 3"
        )])
        conn.close()
    assert got[0] == got[1] and got[0]


def test_the_two_stores_are_never_alive_at_once(lab, signals, tmp_path, fake_panel, monkeypatch):
    conn, path = lab
    d, s = _dirs(tmp_path)
    alive: list[int] = []
    monkeypatch.setattr(research, "load_store",
                        _loader({d: _dev(), s: _sv(smoke_data())}, alive))
    assert _panel(path, d, s, "S0901", "S0902") == 0
    assert alive == [0, 0]


def test_the_frame_is_built_once_per_store_and_every_signal_measured_on_both(lab, signals, stores, fake_panel):
    conn, path = lab
    d, s = stores
    _, calls = fake_panel
    assert _panel(path, d, s, "S0901", "S0902") == 0
    assert calls == [("smoke", "S0901"), ("smoke", "S0902"), ("smoke-sv", "S0901"), ("smoke-sv", "S0902")]


def test_a_survivorship_store_that_fails_after_the_dev_store_leaves_no_half_record(lab, signals, tmp_path, fake_panel, monkeypatch):
    conn, path = lab
    d, s = _dirs(tmp_path)
    monkeypatch.setattr(research, "load_store",
                        _loader({d: _dev(), s: ValueError("a file's sha256 does not match")}))
    before = _counts(conn)
    assert _panel(path, d, s, "S0901") == 2
    assert _signal_ids(conn) == [] and _results(conn) == []
    assert _counts(conn) == before


def test_an_unmeasurable_signal_is_printed_not_recorded_and_exits_2(lab, signals, stores, fake_panel):
    conn, path = lab
    d, s = stores
    readings, _ = fake_panel
    readings["S0902"] = panel.PanelReading(stats=(), picks_hash="c" * 64, dropped_exits=0)
    assert _panel(path, d, s, "S0901", "S0902") == 2
    assert _signal_ids(conn) == ["S0901"]


def test_pending_measures_only_committed_signals_with_no_panel(lab, signals, stores, fake_panel, capsys):
    conn, path = lab
    d, s = stores
    repo, found = signals
    _, calls = fake_panel
    assert _panel(path, d, s, "S0901") == 0
    draft = repo / "s0904_draft.py"
    draft.write_text("# draft\n", encoding="utf-8")
    found["S0904"] = (_signal("S0904", "A draft"), draft)
    calls.clear()
    capsys.readouterr()
    assert _panel(path, d, s, "--pending") == 0
    out = capsys.readouterr().out
    assert {sid for _, sid in calls} == {"S0902", "S0903"}
    assert "skipped S0904" in out
    assert _signal_ids(conn) == ["S0901", "S0902", "S0903"]


# ---- lab panel: refusals (exit 2, nothing loaded, nothing recorded) -----------------------------


def test_a_named_signal_that_is_not_committed_exits_2_and_records_nothing(lab, signals, stores, monkeypatch):
    conn, path = lab
    d, s = stores
    repo, found = signals
    monkeypatch.setattr(research, "load_store", _boom)
    draft = repo / "s0904_draft.py"
    draft.write_text("# draft\n", encoding="utf-8")
    found["S0904"] = (_signal("S0904", "A draft"), draft)
    assert _panel(path, d, s, "S0904") == 2                      # untracked
    found["S0901"][1].write_text("# S0901, edited\n", encoding="utf-8")
    assert _panel(path, d, s, "S0901") == 2                      # tracked, modified
    _git(repo, "add", found["S0901"][1].name)
    assert _panel(path, d, s, "S0901") == 2                      # staged, not committed
    assert _panel(path, d, s, "S0902", "S0904") == 2             # one bad name refuses the run
    assert _signal_ids(conn) == [] and _results(conn) == []


def test_a_signal_changed_after_its_panel_is_refused(lab, signals, stores, fake_panel, tmp_path, monkeypatch):
    conn, path = lab
    d, s = stores
    repo, found = signals
    assert _panel(path, d, s, "S0901") == 0
    found["S0901"][1].write_text("# S0901, a different idea\n", encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "edit")
    d2, s2 = tmp_path / "dev-2", tmp_path / "sv-2"
    for p, m in ((d2, {"fingerprint": "smoke-2"}), (s2, {"fingerprint": "smoke-sv", "purpose": SV})):
        p.mkdir()
        (p / "manifest.json").write_text(json.dumps(m))
    monkeypatch.setattr(research, "load_store", _boom)
    assert _panel(path, d2, s2, "S0901") == 2
    assert _signal_ids(conn) == ["S0901"]


def test_an_unknown_signal_or_no_selection_exits_2(lab, signals, stores, monkeypatch):
    _, path = lab
    d, s = stores
    monkeypatch.setattr(research, "load_store", _boom)
    assert _panel(path, d, s, "S0999") == 2
    assert _panel(path, d, s) == 2
    assert _panel(path, d, s, "S0901", "--pending") == 2


@pytest.mark.parametrize(
    ("dev_manifest", "sv_manifest"),
    [
        ({"fingerprint": "t", "window_name": "test", "window_start": "2015-10-19",
          "window_end": "2026-11-13"}, None),                                   # a test-window store
        ({"fingerprint": "smoke-sv", "purpose": SV}, None),                     # the check store as --store
        (None, {"fingerprint": "smoke-sv"}),                                    # check store unmarked
        (None, {"fingerprint": "u", "purpose": research.UNIVERSE_PURPOSE}),     # another marked store
    ],
)
def test_a_wrong_store_exits_2_before_loading(lab, signals, tmp_path, monkeypatch, dev_manifest, sv_manifest):
    conn, path = lab
    d, s = _dirs(tmp_path, dev_manifest, sv_manifest)
    monkeypatch.setattr(research, "load_store", _boom)
    assert _panel(path, d, s, "S0901") == 2
    assert _signal_ids(conn) == [] and _results(conn) == []


def test_a_missing_survivorship_store_or_the_same_store_twice_exits_2(lab, signals, tmp_path, monkeypatch):
    conn, path = lab
    d, _ = _dirs(tmp_path)
    monkeypatch.setattr(research, "load_store", _boom)
    assert _panel(path, d, tmp_path / "nowhere", "S0901") == 2
    assert _panel(path, d, d, "S0901") == 2
    assert _signal_ids(conn) == [] and _results(conn) == []


def test_a_dev_store_whose_prices_are_unknown_is_refused_by_d10(lab, signals, tmp_path, fake_panel, monkeypatch):
    conn, path = lab
    d, s = _dirs(tmp_path)
    monkeypatch.setattr(research, "load_store",
                        _loader({d: replace(_dev(), price_fingerprint=None), s: _sv(smoke_data())}))
    assert _panel(path, d, s, "S0901") == 2
    assert _results(conn) == []


# ---- lab panel-map -----------------------------------------------------------------------------


def test_panel_map_prints_an_empty_state_and_writes_nothing(lab, capsys):
    conn, path = lab
    before = _counts(conn)
    assert _lab(path, "panel-map") == 0
    out = capsys.readouterr().out
    assert "no panel recorded yet" in out
    assert f"luck gate N = {before[1]} before, {before[1]} after" in out
    assert _counts(conn) == before


def test_panel_map_ranks_by_controlled_slope_with_verdict_and_twin(lab, signals, stores, fake_panel, capsys):
    conn, path = lab
    d, s = stores
    assert _panel(path, d, s, "S0901", "S0902") == 0
    assert _panel(path, d, s, "S0903") == 0          # same pick set as S0901, recorded later
    before = _counts(conn)
    rows = _results(conn)
    capsys.readouterr()
    assert _lab(path, "panel-map") == 0
    out = capsys.readouterr().out
    lines = [ln for ln in out.splitlines() if ln[:6].strip().isdigit()]
    assert [ln.split()[1] for ln in lines] == ["S0901", "S0903", "S0902"]
    assert all(ln.split()[6] in ("clears", "no") for ln in lines)
    assert "S0901" in lines[1].split()[7:8]          # S0903's twin-of column
    assert "3 of 3 panel(s) shown" in out
    assert _counts(conn) == before and _results(conn) == rows


def test_panel_map_top_and_kind(lab, signals, stores, fake_panel, capsys):
    _, path = lab
    d, s = stores
    assert _panel(path, d, s, "S0901", "S0902") == 0
    capsys.readouterr()
    assert _lab(path, "panel-map", "--top", "1") == 0
    out = capsys.readouterr().out
    assert "1 of 2 panel(s) shown" in out and "S0902" not in out
    assert _lab(path, "panel-map", "--kind", "replay") == 0
    assert "no replay panel recorded yet" in capsys.readouterr().out


# ---- lab next-signal-id ------------------------------------------------------------------------


def test_next_signal_id_is_one_past_the_record_and_the_files(lab, signals, stores, fake_panel, monkeypatch, capsys):
    conn, path = lab
    d, s = stores
    capsys.readouterr()
    assert _lab(path, "next-signal-id") == 0
    assert capsys.readouterr().out.strip() == "S0904"            # files only
    assert _panel(path, d, s, "S0903") == 0
    monkeypatch.setattr(signal, "discover", lambda: {})
    capsys.readouterr()
    assert _lab(path, "next-signal-id") == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == "S0904"                       # the record alone
    assert "Lab N (dev trials)" in captured.err


def test_next_signal_id_on_an_empty_lab_is_s0001(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(signal, "discover", lambda: {})
    assert _lab(tmp_path / "lab.sqlite", "next-signal-id") == 0
    assert capsys.readouterr().out.strip() == "S0001"


# ---- phase 1 and phase 2 name the rule and the eras once each ----------------------------------


def test_the_record_and_the_evaluator_agree_on_the_rule_and_the_eras():
    """Phase 2 duplicates ``panel.RULE_ID`` and ``panel.ERAS`` so it need not import phase 1; this
    is the first module that sees both, so the pin lives here. A drift would record rows under a
    rule the verdict never reads, or an era the table's CHECK refuses."""
    from seer_engine.lab import panel_verdict

    assert panel.RULE_ID == panel_verdict.RULE_ID
    assert panel.ERAS == store.PANEL_ERAS


# ---- argparse ----------------------------------------------------------------------------------


@pytest.mark.parametrize("argv", [["lab", "--help"], ["lab", "panel", "--help"],
                                  ["lab", "panel-map", "--help"], ["lab", "next-signal-id", "--help"]])
def test_help_formats(argv, capsys):
    with pytest.raises(SystemExit) as e:
        cli.main(argv)
    assert e.value.code == 0


# ---- the wide synthetic market -----------------------------------------------------------------


def _wide_data() -> research.ResearchData:
    """Forty members priced like labkit's smoke names, 2005 through DEV_END: every one passes F4's
    screen (smoke volume x price is far above its 20M floor), so 40 >= phase 1's MIN_SCORED (30)
    names are scored each month, the top bucket is TOP_MIN (10), and every era has well over
    MIN_ERA_MONTHS (12) months. Built in memory."""
    days = dates.sessions(WIDE_FIRST, DEV_END)
    members = tuple(f"W{k:02d}" for k in range(40))
    symbols = tuple(BASE_ETFS) + members
    history = {sym: smoke_history(sym, k, days) for k, sym in enumerate(symbols)}
    membership = Membership(intervals=tuple((sym, days[0], None) for sym in members))
    market = Market(history=history, membership=membership, fx=((days[0], Decimal("2000")),))
    return replace(smoke_data(), market=market, fingerprint="wide",
                   price_fingerprint=LAB_PRICE_FINGERPRINT)

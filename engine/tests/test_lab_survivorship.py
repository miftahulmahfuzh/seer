"""``lab survivorship``: recorded methods re-run on the survivorship-check store (EODHD plan phase 4).

Report only: N, the looks and every trial-side table stay as they were; refusals come before any
store loads; the two stores are never alive at once; a collapse the dev store cannot see lowers the
result on the check store.
"""

from __future__ import annotations

import csv
import json
import os
import sqlite3
import weakref
from dataclasses import replace
from datetime import date
from pathlib import Path

import numpy as np
import pytest
from labkit import SMOKE_FIRST, smoke_data, smoke_history, smoke_test_data

from seer_engine import cli, dates, research
from seer_engine.backtest.dev import DEV_END, Candidate
from seer_engine.backtest.market import Membership
from seer_engine.commands import lab as lab_command
from seer_engine.lab import hardgate, runner, store
from seer_engine.lab import survivorship_check as svc
from seer_engine.lab.method import Method
from seer_engine.lab.seed import seed
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import FACTOR, FactorParams

HERE = Path(__file__)
COLLAPSE_AT, LAST_BAR = 300, 330  # session indices into the smoke window
PARAMS_A = FactorParams(rank="lowvol", top=9, mom_n=60, mom_skip=0, vol_n=20, trend=None)
PARAMS_B = FactorParams(rank="momentum", top=9, mom_n=40, mom_skip=0, vol_n=20, trend=None)


def _cand(cid: str, params: FactorParams) -> Candidate:
    return Candidate(
        id=cid, family="M0001", rules=MONTHLY_HOLD_FRAC, allocator=FACTOR, params=params,
        rationale="test", added=date(2026, 10, 10), owner_inputs=(),
    )


def _method(cands=None) -> Method:
    return Method(
        id="M0001", name="Quiet stocks held equally", family="factor", source_kind="knowledge",
        source_ref="", hypothesis="h", expected_failure="f",
        candidates=cands or (_cand("M0001-A", PARAMS_A), _cand("M0001-B", PARAMS_B)),
    )


def _collapsed(days: list[date]) -> History:
    """A member priced like the others until COLLAPSE_AT, then ~12% a session down to 2% of its
    price, and no bar after LAST_BAR: a bankruptcy the dev store never saw."""
    h = smoke_history("ZZZ", 99, days)
    f = np.ones(len(days))
    for i in range(COLLAPSE_AT, len(days)):
        f[i] = max(0.02, 1.0 - 0.12 * (i - COLLAPSE_AT + 1))
    cut = slice(0, LAST_BAR)

    def px(a: np.ndarray) -> np.ndarray:
        return np.round(a * f, 2)[cut]

    return History("ZZZ", h.dates[cut], px(h.open), px(h.high), px(h.low), px(h.close), h.volume[cut])


def _sv_data() -> research.ResearchData:
    base = smoke_data()
    days = dates.sessions(SMOKE_FIRST, DEV_END)
    history = dict(base.market.history)
    history["ZZZ"] = _collapsed(days)
    membership = Membership(intervals=base.market.membership.intervals + (("ZZZ", days[0], None),))
    return replace(
        base,
        market=replace(base.market, history=history, membership=membership),
        fingerprint="smoke-sv",
        price_fingerprint="smoke-sv",
        manifest={"purpose": svc.SV_PURPOSE},
        purpose=svc.SV_PURPOSE,
    )


@pytest.fixture(scope="module")
def dev_data():
    return smoke_data()


@pytest.fixture(scope="module")
def sv_data():
    return _sv_data()


@pytest.fixture()
def lab(tmp_path):
    path = tmp_path / "lab.sqlite"
    c = store.connect(path)
    seed(c)
    yield c, path
    c.close()


@pytest.fixture()
def recorded(lab, dev_data, monkeypatch):
    conn, _ = lab
    m = _method()
    runner.run_method(conn, m, HERE, dev_data, git_sha="x", require_commit=False)
    monkeypatch.setattr(svc, "discover", lambda: {"M0001": (m, HERE)})
    return m


def _dirs(tmp_path, dev_manifest=None, sv_manifest=None) -> tuple[Path, Path]:
    d, s = tmp_path / "dev-store", tmp_path / "sv-store"
    d.mkdir()
    s.mkdir()
    (d / "manifest.json").write_text(json.dumps({"fingerprint": "smoke"} if dev_manifest is None else dev_manifest))
    (s / "manifest.json").write_text(json.dumps(
        {"fingerprint": "smoke-sv", "purpose": svc.SV_PURPOSE} if sv_manifest is None else sv_manifest
    ))
    return d, s


def _loader(by_dir, alive_at_load=None):
    """A stand-in for research.load_store: a fresh ResearchData per call, so a test can watch
    the previous one die before the next is handed out."""
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


def _untouched(conn):
    """Everything `lab survivorship` must leave as it found it (insights excepted)."""
    return (
        store.dev_trial_count(conn),
        store.test_looks(conn),
        conn.execute("SELECT count(*) FROM trials").fetchone()[0],
        conn.execute("SELECT count(*) FROM trial_moments").fetchone()[0],
        conn.execute("SELECT count(*) FROM trial_funding").fetchone()[0],
        conn.execute("SELECT count(*) FROM trial_provenance").fetchone()[0],
        tuple(tuple(r) for r in conn.execute("SELECT id, status, verdict, source_sha FROM methods ORDER BY id")),
    )


def _insights(conn) -> int:
    return conn.execute("SELECT count(*) FROM insights").fetchone()[0]


def _measure(conn, dev_data, sv_data, tmp_path, monkeypatch):
    d, s = _dirs(tmp_path)
    monkeypatch.setattr(research, "load_store", _loader({d: dev_data, s: sv_data}))
    plans = svc.plan_methods(conn, ["M0001"])
    geo = hardgate.geometry(conn)
    svc.check_stores(d, s)
    dev_run = svc.measure_store(conn, plans, d, survivorship=False, bench=geo.bench)
    sv_run = svc.measure_store(conn, plans, s, survivorship=True, bench=geo.bench)
    return svc.compare(plans, dev_run, sv_run, geo), dev_run, sv_run, geo


# ---- the measurement ---------------------------------------------------------------------------


def test_the_collapse_lowers_the_result_and_nothing_is_written(lab, dev_data, sv_data, recorded, tmp_path, monkeypatch):
    conn, _ = lab
    before, notes = _untouched(conn), _insights(conn)
    reports, dev_run, sv_run, _geo = _measure(conn, dev_data, sv_data, tmp_path, monkeypatch)
    (rep,) = reports
    assert [r.variant.candidate.id for r in rep.rows] == ["M0001-A", "M0001-B"]
    a = rep.rows[0]
    assert a.reproduced is True
    assert a.variant.funded and a.dev.funded
    assert a.sv.total_return < a.dev.total_return
    assert a.sv.yearly < a.dev.yearly
    assert rep.worse >= 1
    assert a.dev.dsr is not None and a.variant.var_trials is not None  # moments were recorded
    assert (dev_run.fingerprint, sv_run.fingerprint) == ("smoke", "smoke-sv")
    assert _untouched(conn) == before and _insights(conn) == notes


def test_the_dev_rerun_runs_at_the_recorded_capital_and_funding(lab, dev_data, sv_data, recorded, tmp_path, monkeypatch):
    conn, _ = lab
    seen: list = []
    real = svc.dev.run_registry

    def spy(*a, **k):
        seen.append((k.get("initial_idr"), k.get("contributions")))
        return real(*a, **k)

    monkeypatch.setattr(svc.dev, "run_registry", spy)
    _measure(conn, dev_data, sv_data, tmp_path, monkeypatch)
    n = int(store.trials_of(conn, "M0001")[0]["n"])
    want = (runner.recorded_capital(conn, n), runner.recorded_contributions(conn, n))
    assert seen == [want, want]  # one call per store: both variants share capital and schedule


def test_the_two_stores_are_never_alive_at_once(lab, dev_data, sv_data, recorded, tmp_path, monkeypatch):
    _, path = lab
    d, s = _dirs(tmp_path)
    alive: list[int] = []
    monkeypatch.setattr(research, "load_store", _loader({d: dev_data, s: sv_data}, alive))
    argv = ["lab", "--db", str(path), "survivorship", "M0001", "--store", str(d), "--sv-store", str(s), "--no-journal"]
    assert cli.main(argv) == 0
    assert alive == [0, 0]  # the dev store was gone before the check store was loaded


def test_dsr_says_so_when_no_var_trials_was_recorded(lab, dev_data, sv_data, recorded, tmp_path, monkeypatch):
    conn, _ = lab
    monkeypatch.setattr(svc.store, "moments_of", lambda c, n: None)
    reports, dev_run, sv_run, geo = _measure(conn, dev_data, sv_data, tmp_path, monkeypatch)
    (rep,) = reports
    assert all(r.dev.dsr is None and r.sv.dsr is None for r in rep.rows)
    assert "no recorded var_trials" in svc.format_report(rep, dev_run, sv_run, len(geo.folds))


def test_a_variant_gone_from_the_file_is_listed_not_run(lab, dev_data, sv_data, recorded, tmp_path, monkeypatch):
    conn, _ = lab
    only_a = _method((_cand("M0001-A", PARAMS_A),))
    monkeypatch.setattr(svc, "discover", lambda: {"M0001": (only_a, HERE)})
    reports, dev_run, sv_run, geo = _measure(conn, dev_data, sv_data, tmp_path, monkeypatch)
    (rep,) = reports
    assert rep.missing == ("M0001-B",)
    assert [r.variant.candidate.id for r in rep.rows] == ["M0001-A"]
    assert "no longer in the method file): M0001-B" in svc.format_report(rep, dev_run, sv_run, len(geo.folds))


def test_high_coverage_matches_the_walkforward_command():
    assert svc.HIGH_COVERAGE == lab_command.HIGH_COVERAGE


# ---- the command -------------------------------------------------------------------------------


def test_cli_reports_journals_and_writes_the_grid(lab, dev_data, sv_data, recorded, tmp_path, monkeypatch, capsys):
    conn, path = lab
    before, notes = _untouched(conn), _insights(conn)
    d, s = _dirs(tmp_path)
    monkeypatch.setattr(research, "load_store", _loader({d: dev_data, s: sv_data}))
    grid = tmp_path / "out" / "grid.csv"
    argv = ["lab", "--db", str(path), "survivorship", "m0001", "M0001",
            "--store", str(d), "--sv-store", str(s), "--csv", str(grid)]
    assert cli.main(argv) == 0
    out = capsys.readouterr().out
    assert "report only" in out and "survivorship" in out and "reproduces it" in out
    assert "walk-forward vs the recorded SPY hold (4 folds)" in out
    assert f"Lab N (dev trials): {before[0]} before, {before[0]} after" in out
    assert _untouched(conn) == before
    assert _insights(conn) == notes + 1  # one method, named twice: one observation
    rows = list(csv.reader(grid.open(encoding="utf-8")))
    assert rows[0] == list(svc.CSV_HEADER)
    assert [(r[1], r[2]) for r in rows[1:]] == [
        ("M0001-A", "dev"), ("M0001-A", "survivorship"), ("M0001-B", "dev"), ("M0001-B", "survivorship"),
    ]
    assert float(rows[2][rows[0].index("total_return")]) < float(rows[1][rows[0].index("total_return")])


def test_no_journal_writes_nothing(lab, dev_data, sv_data, recorded, tmp_path, monkeypatch, capsys):
    conn, path = lab
    before, notes = _untouched(conn), _insights(conn)
    d, s = _dirs(tmp_path)
    monkeypatch.setattr(research, "load_store", _loader({d: dev_data, s: sv_data}))
    argv = ["lab", "--db", str(path), "survivorship", "M0001", "--store", str(d), "--sv-store", str(s), "--no-journal"]
    assert cli.main(argv) == 0
    assert "No journal entry" in capsys.readouterr().out
    assert _untouched(conn) == before and _insights(conn) == notes


def test_the_journal_entry_is_plain_words(lab, dev_data, sv_data, recorded, tmp_path, monkeypatch):
    conn, _ = lab
    (rep,), *_ = _measure(conn, dev_data, sv_data, tmp_path, monkeypatch)
    before = _untouched(conn)
    with conn:
        entry = svc.journal(conn, rep)
    row = conn.execute("SELECT * FROM insights WHERE id = ?", (entry,)).fetchone()
    assert row["kind"] == "observation" and row["method_id"] == "M0001"
    assert row["title"] == "Quiet stocks held equally: what the missing companies did to it"
    for text in (row["title"], row["body"]):
        for banned in ("M0001", "`", "_", "DSR", "MAR", "var"):
            assert banned not in text, banned
    assert "flattered it" in row["body"]
    assert "count of tries did not move" in row["body"]
    assert _untouched(conn) == before


# ---- refusals ----------------------------------------------------------------------------------


def _boom(*a, **k):
    raise AssertionError("a store must not be loaded for a refusal")


@pytest.mark.parametrize(
    ("dev_manifest", "sv_manifest"),
    [
        (None, {"fingerprint": "smoke-sv"}),                                   # check store unmarked
        (None, {"purpose": "something-else"}),                                 # wrong marker
        ({"purpose": svc.SV_PURPOSE}, None),                                   # the check store as --store
    ],
)
def test_cli_refuses_a_wrong_store_pair_before_loading(lab, recorded, tmp_path, monkeypatch, dev_manifest, sv_manifest):
    _, path = lab
    d, s = _dirs(tmp_path, dev_manifest, sv_manifest)
    monkeypatch.setattr(research, "load_store", _boom)
    assert cli.main(["lab", "--db", str(path), "survivorship", "M0001", "--store", str(d), "--sv-store", str(s)]) == 2


def test_cli_refuses_the_same_store_twice_and_a_missing_manifest(lab, recorded, tmp_path, monkeypatch):
    _, path = lab
    d, _s = _dirs(tmp_path)
    monkeypatch.setattr(research, "load_store", _boom)
    assert cli.main(["lab", "--db", str(path), "survivorship", "M0001", "--store", str(d), "--sv-store", str(d)]) == 2
    assert cli.main(["lab", "--db", str(path), "survivorship", "M0001", "--store", str(d),
                     "--sv-store", str(tmp_path / "nowhere")]) == 2


def test_cli_refuses_unknown_or_unrun_methods_before_loading(lab, recorded, tmp_path, monkeypatch):
    _, path = lab
    d, s = _dirs(tmp_path)
    monkeypatch.setattr(research, "load_store", _boom)
    for mid in ("M9999", "H-P7A", "nonsense"):
        assert cli.main(["lab", "--db", str(path), "survivorship", mid, "--store", str(d), "--sv-store", str(s)]) == 2
    conn = store.connect(path)
    try:
        other = Method(id="M0002", name="never ran", family="factor", source_kind="knowledge",
                       source_ref="", hypothesis="h", expected_failure="f",
                       candidates=(Candidate(id="M0002-A", family="M0002", rules=MONTHLY_HOLD_FRAC,
                                             allocator=FACTOR, params=PARAMS_A, rationale="t",
                                             added=date(2026, 10, 10), owner_inputs=()),))
        monkeypatch.setattr(svc, "discover", lambda: {"M0002": (other, HERE)})
        with pytest.raises(store.LabError, match="has no dev trial"):
            svc.plan_methods(conn, ["M0002"])
    finally:
        conn.close()


def test_a_trial_with_no_recorded_capital_is_refused_before_loading(lab, recorded, monkeypatch):
    conn, _ = lab

    def none(c, n):
        return None

    monkeypatch.setattr(store, "provenance_of", none)
    with pytest.raises(store.LabError, match="no recorded starting capital"):
        svc.plan_methods(conn, ["M0001"])


def test_load_checked_refuses_a_wrong_purpose_or_window(dev_data, sv_data, tmp_path, monkeypatch):
    d, s = _dirs(tmp_path)
    monkeypatch.setattr(research, "load_store", _loader({d: dev_data, s: sv_data}))
    with pytest.raises(store.LabError, match="not 'survivorship-check'"):
        svc.load_checked(d, survivorship=True)  # the manifest peek can lie; the loaded data cannot
    with pytest.raises(store.LabError, match="carries none"):
        svc.load_checked(s, survivorship=False)
    t = tmp_path / "test-store"
    monkeypatch.setattr(research, "load_store", _loader({t: smoke_test_data()}))
    with pytest.raises(store.LabError, match="dev window"):
        svc.load_checked(t, survivorship=False)
    monkeypatch.setattr(research, "load_store", _loader({t: ValueError("declares the 'test' window")}))
    with pytest.raises(store.LabError, match="test-window store is refused"):
        svc.load_checked(t, survivorship=False)


def test_cli_exits_2_when_the_dev_store_is_a_test_window_store(lab, recorded, sv_data, tmp_path, monkeypatch):
    _, path = lab
    d, s = _dirs(tmp_path)
    monkeypatch.setattr(research, "load_store", _loader({d: ValueError("declares the 'test' window"), s: sv_data}))
    before = _untouched(store.connect(path))
    assert cli.main(["lab", "--db", str(path), "survivorship", "M0001", "--store", str(d), "--sv-store", str(s)]) == 2
    assert _untouched(store.connect(path)) == before


# ---- opt-in: the real stores -------------------------------------------------------------------


@pytest.mark.skipif(
    not os.environ.get("SEER_LAB_SURVIVORSHIP_LIVE"),
    reason="set SEER_LAB_SURVIVORSHIP_LIVE=1 to run lab survivorship M0069 on the real stores",
)
def test_lab_survivorship_m0069_on_the_real_stores(tmp_path, capsys):
    dev_dir = Path(os.environ.get("SEER_RESEARCH_STORE") or "/home/miftah/seer/engine/.research")
    sv_dir = Path(os.environ.get("SEER_RESEARCH_SV_STORE") or "/home/miftah/seer/engine/.research-sv")
    live_db = Path(os.environ.get("SEER_LAB_DB") or store.COMMITTED_DB)
    db = tmp_path / "lab.sqlite"
    src = sqlite3.connect(f"file:{live_db}?mode=ro", uri=True)
    dst = sqlite3.connect(db)
    src.backup(dst)  # a consistent copy even while a Sera batch writes; the source is never written
    src.close()
    dst.close()
    argv = ["lab", "--db", str(db), "survivorship", "M0069", "--store", str(dev_dir),
            "--sv-store", str(sv_dir), "--no-journal"]
    assert cli.main(argv) == 0
    out = capsys.readouterr().out
    assert "lab survivorship M0069" in out and "No journal entry" in out

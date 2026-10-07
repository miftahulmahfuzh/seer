"""``lab test``: the one counted look at the test window (method lab design §3).

Nothing here touches ``lab/lab.sqlite`` or ``engine/.research-test``: every test runs against a
temp database and the synthetic test-window market in ``labkit``. Building the mechanism spends no
look, and the committed lab must still read "test-window looks used: 0" when this lands.
"""

from __future__ import annotations

import sqlite3
from datetime import date
from types import SimpleNamespace

import pytest
from labkit import TEST_FIRST, TEST_LAST, smoke_test_data, smoke_test_window

from seer_engine.backtest import dev
from seer_engine.backtest.book_runner import RunStats
from seer_engine.backtest.dev import Candidate, make_row
from seer_engine.backtest.metrics import Metrics
from seer_engine.lab import prereg, runner, store
from seer_engine.lab.method import Method, config_digest, config_text
from seer_engine.sim.rules import MONTHLY_HOLD
from seer_engine.strategies.f_index import TIMING, TimingParams

# ---- fixtures ---------------------------------------------------------------------------------


def _cand(cid: str, family: str, n: int = 50) -> Candidate:
    return Candidate(
        id=cid, family=family, rules=MONTHLY_HOLD, allocator=TIMING,
        params=TimingParams(hold="SPY", signal="SPY", rule="sma", n=n),
        rationale="the pre-registered variant", added=date(2026, 10, 6), owner_inputs=(),
    )


def _method(mid: str = "M0001", cands=None) -> Method:
    return Method(
        id=mid, name="SMA test", family="trend", source_kind="knowledge", source_ref="",
        hypothesis="A 50-day SMA on SPY beats buy-and-hold after costs.\nSecond line ignored.",
        expected_failure="whipsaw", candidates=tuple(cands or (_cand(f"{mid}-A", mid),)),
    )


def _prereg(c: Candidate, *, method: str = "M0001", digest: str | None = None) -> prereg.Prereg:
    """A real ``prereg.Prereg`` (phase 3) -- every field a ``str``, no ``path`` field.

    Built rather than faked: ``Prereg`` is a frozen dataclass of fifteen strings with no
    behaviour, so constructing the real one costs nothing and cannot drift from phase 3's
    field names the way a local stand-in would.
    """
    return prereg.Prereg(
        method=method,
        candidate=c.id,
        config_digest=config_digest(c) if digest is None else digest,
        rules_id=c.rules.id,
        allocator_id=str(c.allocator.id),
        dev_trial="1",
        dev_window="1996-01-02..2015-10-16",
        test_window="2015-10-19..data end",
        gate=prereg.gate_text(),
        mar="0.790000",
        dsr="0.960000",
        n_trials_at_run="56",
        store_fingerprint="fp",
        git_sha="abc",
        date="2026-10-06",
    )


@pytest.fixture()
def conn(tmp_path):
    c = store.connect(tmp_path / "lab.sqlite")
    yield c
    c.close()


def _dev_trial(m: Method, c: Candidate, **kw) -> store.TrialRow:
    base = dict(
        method_id=m.id, candidate_id=c.id, config_digest=config_digest(c), config_text=config_text(c),
        rules_id=c.rules.id, allocator_id=str(c.allocator.id), window="dev", start="1996-01-02",
        end="2015-10-16", store_fingerprint="fp", git_sha="abc",
        run_at="2026-10-06T00:00:00+00:00", total_return=3.0, cagr=0.11, max_drawdown=0.14,
        profit_factor=1.6, trades=180, sharpe=0.9, exposure=0.8, turnover=1.2, worst_year=2008,
        worst_year_return=-0.09, spy_tr_return=2.0, spy_tr_cagr=0.08, mar=0.79, failed="",
        eligible=True, dsr=0.96, n_trials_at_run=56, curve_json="[]",
    )
    base.update(kw)
    return store.TrialRow(**base)


@pytest.fixture()
def promoted(conn):
    """M0001 at ``promoted`` with a recorded dev trial for its variant -- the state ``lab test``
    requires and the only state ``lab promote`` (phase 3) leaves behind."""
    m = _method()
    c = m.candidates[0]
    with conn:
        store.add_method(conn, id=m.id, name=m.name, family=m.family, source_kind=m.source_kind,
                         hypothesis="h", status="registered")
        store.insert_trials(conn, [_dev_trial(m, c)])
        store.update_method(conn, m.id, status="dev-eligible")
        store.update_method(conn, m.id, status="promoted")
    return m


@pytest.fixture()
def prereg_ok(monkeypatch, promoted):
    """Phase 3's committed-prereg check, standing in for a real ``docs/lab/prereg/M0001.md``.

    ``preflight_test`` **calls** phase 3's ``require_committed``; it never reimplements the git
    or identity checks, so what a phase-4 test can honestly stub is its answer. ``check_digest``
    is phase 3's too and is **not** stubbed -- it is pure, so the real one runs here, which is
    what makes the stale-digest test below a real test.
    """
    c = promoted.candidates[0]
    pre = _prereg(c)

    def fake(candidate_id: str, *, directory=None):
        if candidate_id != c.id:
            raise prereg.PreregError(f"no pre-registration naming {candidate_id}")
        return pre

    monkeypatch.setattr(prereg, "require_committed", fake)
    return pre


@pytest.fixture(scope="module")
def data():
    return smoke_test_data()


# ---- the database refuses a second look --------------------------------------------------------


def test_the_database_refuses_a_second_look_without_any_python_guard(conn):
    """Design §3's "the database refuses a second look", proven against the schema.

    ``insert_trials`` makes the refusal readable (``store.py:542``), but the guarantee is
    ``UNIQUE(config_digest, window)`` (``store.py:169``): the same configuration, inserted with raw
    SQL past every Python check, is still refused -- and the append-only triggers mean the first
    row can never be deleted to make room.
    """
    m = _method()
    c = m.candidates[0]
    with conn:
        store.add_method(conn, id=m.id, name=m.name, family=m.family,
                         source_kind=m.source_kind, hypothesis="h")
        row = _dev_trial(m, c, window="test", start=TEST_FIRST.isoformat(), end=TEST_LAST.isoformat())
        store.insert_trials(conn, [row])
    assert store.test_looks(conn) == 1

    cols = ", ".join(f'"{x}"' for x in store.TRIAL_COLUMNS)
    marks = ", ".join("?" for _ in store.TRIAL_COLUMNS)
    values = [getattr(row, x) for x in store.TRIAL_COLUMNS]
    values[store.TRIAL_COLUMNS.index("eligible")] = int(row.eligible)
    values[store.TRIAL_COLUMNS.index("candidate_id")] = "M0001-SECOND"  # a new id does not help
    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
        conn.execute(f"INSERT INTO trials ({cols}) VALUES ({marks})", values)
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("DELETE FROM trials WHERE window = 'test'")
    assert store.test_looks(conn) == 1


# ---- the refusals ------------------------------------------------------------------------------


def test_a_method_that_is_not_promoted_is_refused(conn, prereg_ok, promoted, tmp_path):
    m2 = _method("M0002", cands=(_cand("M0002-A", "M0002"),))
    with conn:
        store.add_method(conn, id="M0002", name="n", family="f", source_kind="knowledge",
                         hypothesis="h", status="registered")
        store.update_method(conn, "M0002", status="dev-eligible")
    with pytest.raises(store.LabError, match="only a 'promoted' method"):
        runner.preflight_test(conn, m2, tmp_path / "m0002_x.py", m2.candidates[0],
                              require_commit=False)


def test_a_missing_prereg_is_refused(conn, monkeypatch, promoted, tmp_path):
    """`preflight_test` calls phase 3's `require_committed` and lets its refusal through.

    Phase 3's own tests prove *when* it refuses (missing, untracked, staged-only, modified,
    naming another method or another candidate) against a real git repository. What is this
    phase's to prove is that `lab test` asks, and that a `PreregError` is a `store.LabError`
    and so reaches exit 2 unchanged.
    """
    c = promoted.candidates[0]

    def missing(candidate_id, *, directory=None):
        raise prereg.PreregError(f"{candidate_id}: docs/lab/prereg/M0001.md does not exist")

    monkeypatch.setattr(prereg, "require_committed", missing)
    with pytest.raises(store.LabError, match="does not exist"):
        runner.preflight_test(conn, promoted, tmp_path / "x.py", c, require_commit=False)


def test_a_stale_digest_is_refused_by_phase_threes_check_digest(conn, promoted, tmp_path):
    """The configuration drifted after it was pre-registered. `check_digest` is not stubbed."""
    c = promoted.candidates[0]
    stale = _prereg(c, digest="0" * 64)
    with pytest.raises(prereg.PreregError, match="pre-registered 0{64}"):
        runner.preflight_test(conn, promoted, tmp_path / "x.py", c, pre=stale,
                              require_commit=False)


def test_a_configuration_with_no_dev_trial_is_refused(conn, promoted, tmp_path):
    fresh = _cand("M0001-B", "M0001", n=77)  # a variant that never ran on dev
    m = _method(cands=(promoted.candidates[0], fresh))
    with pytest.raises(store.LabError, match="no dev trial"):
        runner.preflight_test(conn, m, tmp_path / "x.py", fresh, pre=_prereg(fresh),
                              require_commit=False)


def test_a_dev_store_is_refused_before_anything_runs(conn, prereg_ok, promoted, tmp_path):
    """A mis-pointed store must never produce a 'test' trial measured on dev data."""
    from labkit import smoke_data

    with pytest.raises(store.LabError, match="research store was built for the 'dev' window"):
        runner.run_test(conn, promoted, tmp_path / "x.py", promoted.candidates[0], smoke_data(),
                        git_sha="x", require_commit=False)
    assert store.test_looks(conn) == 0


def test_resolve_candidate_refuses_a_method_id_and_an_unknown_variant():
    with pytest.raises(store.LabError, match="not a candidate id"):
        runner.resolve_candidate("M0007")
    with pytest.raises(store.LabError, match="no method file"):
        runner.resolve_candidate("M9999-A")


# ---- the look itself ---------------------------------------------------------------------------


def test_the_look_is_recorded_and_does_not_move_the_lab_s_n(conn, data, prereg_ok, promoted, tmp_path):
    before_n = store.dev_trial_count(conn)
    before_sharpes = store.dev_daily_sharpes(conn)
    c = promoted.candidates[0]
    tested = runner.run_test(conn, promoted, tmp_path / "x.py", c, data,
                             git_sha="cafe", require_commit=False)

    assert store.dev_trial_count(conn) == before_n          # the search's N did not move
    assert store.dev_daily_sharpes(conn) == before_sharpes  # nor the DSR's variance term
    assert store.test_looks(conn) == 1

    row = conn.execute("SELECT * FROM trials WHERE window = 'test'").fetchone()
    assert row["candidate_id"] == c.id
    assert row["config_digest"] == config_digest(c)
    assert row["git_sha"] == "cafe" and row["store_fingerprint"] == "smoke-test"
    assert row["n_trials_at_run"] == before_n
    assert date.fromisoformat(row["start"]) >= TEST_FIRST
    assert row["end"] == TEST_LAST.isoformat()
    assert store.DSR_LABEL not in row["failed"]  # DSR is recorded, never a condition
    assert tested.status == "test-failed"        # the fixture is ~3 years: far under 100 trades
    assert ">= 100 trades" in row["failed"]
    assert store.get_method(conn, "M0001")["status"] == "test-failed"


def test_a_second_look_is_refused_after_a_real_run(conn, data, prereg_ok, promoted, tmp_path):
    """Two independent noes, in the order ``preflight_test`` documents.

    After a real look the method is already ``test-failed``, so refusal 1 (the status) fires
    first and refusal 5 is never reached -- which is itself a second no: ``test-failed`` is
    final and ``TRANSITIONS`` has no edge back to ``promoted``. Refusal 5 guards the case the
    status cannot: a recorded ``test`` trial against a method still sitting at ``promoted``,
    which is what a parallel session's half-finished write looks like.
    """
    c = promoted.candidates[0]
    runner.run_test(conn, promoted, tmp_path / "x.py", c, data, git_sha="x", require_commit=False)
    assert store.test_looks(conn) == 1
    with pytest.raises(store.LabError, match="only a 'promoted' method"):
        runner.preflight_test(conn, promoted, tmp_path / "x.py", c, require_commit=False)
    assert store.test_looks(conn) == 1


def test_a_recorded_look_is_refused_even_while_the_method_is_still_promoted(
    conn, prereg_ok, promoted, tmp_path
):
    """``preflight_test``'s refusal 5, reached on its own: the trial exists, the status has not
    caught up. The database makes the same refusal (the raw-SQL test above); this is the early,
    readable form of it, made before a store is loaded and a backtest is run."""
    c = promoted.candidates[0]
    with conn:
        store.insert_trials(conn, [_dev_trial(promoted, c, window="test",
                                              start=TEST_FIRST.isoformat(),
                                              end=TEST_LAST.isoformat())])
    assert store.get_method(conn, "M0001")["status"] == "promoted"
    with pytest.raises(store.LabError, match="already had its look"):
        runner.preflight_test(conn, promoted, tmp_path / "x.py", c, require_commit=False)
    assert store.test_looks(conn) == 1


def test_test_failed_is_final(conn, data, prereg_ok, promoted, tmp_path):
    runner.run_test(conn, promoted, tmp_path / "x.py", promoted.candidates[0], data,
                    git_sha="x", require_commit=False)
    for nxt in ("test-passed", "promoted", "paper", "dev-eligible"):
        with pytest.raises(store.LabError, match="forward"):
            store.update_method(conn, "M0001", status=nxt)


# ---- the verdict and the pass branch -----------------------------------------------------------


def _stats(*, trades: int = 150, dd: float = 0.10, pf: float = 1.6, total: float = 1.2) -> RunStats:
    m = Metrics(total_return=total, win_rate=0.55, profit_factor=pf, max_drawdown=dd,
                trades=trades, months=38.0, cagr=0.14)
    return RunStats(metrics=m, exposure=0.7, turnover=1.5, costs_usd=10.0, gross_pnl_usd=100.0,
                    cost_drag=0.1, dividends_usd=0.0, sharpe=0.9,
                    daily_returns=(0.01, -0.004, 0.006), year_returns=((2016, 0.1),),
                    worst_year=(2016, 0.1))


_SPY_TR = Metrics(total_return=0.6, win_rate=None, profit_factor=None, max_drawdown=0.2, trades=0,
                  months=38.0, cagr=0.08)


def _test_row(c: Candidate, **kw):
    """A DevRow on the **test** window -- phase 1's ``make_row(window=...)``."""
    return make_row(c, TEST_FIRST, TEST_LAST, _stats(**kw), spy_tr=_SPY_TR, spy_price=_SPY_TR,
                    window=smoke_test_window())


def test_the_verdict_is_the_five_go_live_conditions(promoted):
    c = promoted.candidates[0]
    assert _test_row(c).eligible is True
    assert _test_row(c, trades=99).failed == (">= 100 trades",)
    assert _test_row(c, total=0.6).failed == ("beats SPY TR",)  # equal is not beating
    assert _test_row(c, dd=0.25).failed == (dev.FAILURE_LABELS[1],)  # "max DD <= 20%" (D13)
    assert _test_row(c, pf=1.2).failed == ("PF >= 1.3",)


def test_a_passing_look_records_test_passed_and_a_dsr_that_is_not_a_condition(
    conn, monkeypatch, prereg_ok, promoted, tmp_path
):
    """The pass branch, driven by a synthetic eligible row rather than by a fitted market."""
    c = promoted.candidates[0]
    row = _test_row(c)
    snaps = (SimpleNamespace(date=TEST_FIRST, equity_usd=100.0),
             SimpleNamespace(date=TEST_LAST, equity_usd=220.0))

    def fake_run_registry(market, dividends, spy_dividends, registry, *, on_result=None, window=None):
        assert window.name == "test" and tuple(registry) == (c,)
        on_result(0, SimpleNamespace(snapshots=snaps), row)
        return (row,)

    monkeypatch.setattr(runner.dev, "run_registry", fake_run_registry)
    tested = runner.run_test(conn, promoted, tmp_path / "x.py", c, smoke_test_data(),
                             git_sha="x", require_commit=False)
    assert tested.status == "test-passed"
    assert store.get_method(conn, "M0001")["status"] == "test-passed"
    t = conn.execute("SELECT * FROM trials WHERE window = 'test'").fetchone()
    assert t["eligible"] == 1 and t["failed"] == ""
    assert t["dsr"] is None or 0.0 <= t["dsr"] <= 1.0
    assert t["n_trials_at_run"] == store.dev_trial_count(conn)


def test_a_passed_method_can_still_reach_paper(conn, monkeypatch, prereg_ok, promoted, tmp_path):
    """``record_promotion`` already owns the ('test-passed', 'paper') edge; this phase only has to
    leave the method where that edge starts."""
    c = promoted.candidates[0]
    row = _test_row(c)
    snaps = (SimpleNamespace(date=TEST_FIRST, equity_usd=100.0),
             SimpleNamespace(date=TEST_LAST, equity_usd=220.0))
    monkeypatch.setattr(
        runner.dev, "run_registry",
        lambda *a, on_result=None, window=None, **k: (on_result(0, SimpleNamespace(snapshots=snaps), row), (row,))[1],
    )
    runner.run_test(conn, promoted, tmp_path / "x.py", c, smoke_test_data(),
                    git_sha="x", require_commit=False)
    with conn:
        status = store.record_promotion(
            conn, method_id="M0001", strategy_id="SMA", candidate_id=c.id,
            object_name="TIMING", spec_digest="d" * 64,
        )
    assert status == "paper"
    assert store.test_looks(conn) == 1  # a promotion is not a backtest: no trial was added


# ---- the hand-off ------------------------------------------------------------------------------


def test_the_promote_command_is_printed_filled_in(conn, monkeypatch, prereg_ok, promoted, tmp_path):
    from seer_engine.commands import lab as lab_cmd

    c = promoted.candidates[0]
    row = _test_row(c)
    snaps = (SimpleNamespace(date=TEST_FIRST, equity_usd=100.0),
             SimpleNamespace(date=TEST_LAST, equity_usd=220.0))
    monkeypatch.setattr(
        runner.dev, "run_registry",
        lambda *a, on_result=None, window=None, **k: (on_result(0, SimpleNamespace(snapshots=snaps), row), (row,))[1],
    )
    tested = runner.run_test(conn, promoted, tmp_path / "x.py", c, smoke_test_data(),
                             git_sha="x", require_commit=False)
    note = lab_cmd._gate_note(conn, tested)
    assert "Passed the quant backtest gate" in note
    assert "one pre-registered look" in note
    assert "100 closed paper trades" in note  # it still says what has not happened

    argv = lab_cmd._promote_argv(promoted, tested, roster_id="SMA", gate_note=note,
                                 lab_db=tmp_path / "lab.sqlite")
    assert argv[:5] == ["python", "-m", "seer_engine", "promote", "--method"]
    assert "--candidate" in argv and argv[argv.index("--candidate") + 1] == c.id
    assert argv[argv.index("--id") + 1] == "SMA"
    assert argv[argv.index("--gate-note") + 1] == note
    report = lab_cmd._verdict_report(conn, promoted, tested, roster_id="SMA",
                                     lab_db=tmp_path / "lab.sqlite")
    assert "TEST-PASSED" in report and "seer_engine promote" in report and "lab stage" in report


def test_a_failed_look_prints_no_promote_command(conn, data, prereg_ok, promoted, tmp_path):
    from seer_engine.commands import lab as lab_cmd

    tested = runner.run_test(conn, promoted, tmp_path / "x.py", promoted.candidates[0], data,
                             git_sha="x", require_commit=False)
    report = lab_cmd._verdict_report(conn, promoted, tested, roster_id="SMA",
                                     lab_db=tmp_path / "lab.sqlite")
    assert "TEST-FAILED" in report
    assert "test-failed is final" in report
    assert "seer_engine promote" not in report


# ---- the dry run spends nothing ----------------------------------------------------------------


def test_the_dry_run_loads_nothing_and_spends_nothing(conn, prereg_ok, promoted, tmp_path, capsys):
    from seer_engine.commands import lab as lab_cmd

    text = lab_cmd._test_plan(promoted, promoted.candidates[0], prereg_ok, tmp_path / ".research-test")
    assert config_digest(promoted.candidates[0]) in text
    assert "nothing is loaded, run or recorded" in text
    for label in dev.FAILURE_LABELS:
        assert label in text
    assert store.test_looks(conn) == 0

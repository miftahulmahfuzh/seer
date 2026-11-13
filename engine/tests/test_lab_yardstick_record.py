"""``trial_yardstick`` and ``lab yardstick`` (RANDOM_TWIN_YARDSTICK_PLAN.md phase 3).

The record half of the random-twin yardstick: the append-only side table, its readers, the bar,
the due rule, and the command that measures recorded dev arms and records what it found. The
simulator is phase 2's ``lab/yardstick.py`` with its own tests; here it is replaced at its boundary
by a deterministic stand-in, because what is under test is what the lab RECORDS -- one row per arm
and store, never a trial, never a look -- and what it REFUSES, not how twins are drawn.
"""

from __future__ import annotations

import dataclasses
import sqlite3
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from labkit import smoke_data, stamp_provenance

from seer_engine import cli, research
from seer_engine.backtest.dev import Candidate
from seer_engine.lab import control_shape, runner, store, yardstick
from seer_engine.lab import method as method_mod
from seer_engine.lab.method import Method
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC
from seer_engine.strategies.f_index import TIMING, TimingParams

HERE = Path(__file__)
FP = "fp-recorded"
OTHER_FP = "fp-rebuilt"
CONTROL_RATIONALE = "Control: hash draw of 20, seed 1, matched to M0001-A"

# (method, suffix, sharpe, max drawdown). Distinct Sharpes give the lab a trial-Sharpe variance, so
# every DSR is evaluable; C fails the 50% drawdown screen; M0001-E is a control by its rationale.
ROWS = (
    ("M0001", "A", 0.80, 0.20),
    ("M0001", "B", 0.94, 0.20),
    ("M0001", "C", 1.10, 0.55),
    ("M0001", "D", 1.20, 0.20),
    ("M0001", "E", 1.46, 0.20),
    ("M0002", "A", 0.70, 0.20),
    ("M0002", "B", 1.30, 0.20),
)
ELIGIBLE = {"M0001-A", "M0001-B", "M0001-D", "M0001-E", "M0002-A", "M0002-B"}


def _trial(mid: str, suffix: str, sharpe: float, max_drawdown: float) -> store.TrialRow:
    return store.TrialRow(
        method_id=mid, candidate_id=f"{mid}-{suffix}", config_digest=f"{mid}-{suffix}",
        config_text="t", rules_id="r", allocator_id="a", window="dev", start="2000-01-03",
        end="2015-10-16", store_fingerprint=FP, git_sha="abc",
        run_at="2026-11-01T00:00:00+00:00", total_return=1.0, cagr=0.1,
        max_drawdown=max_drawdown, profit_factor=1.5, trades=200, sharpe=sharpe, exposure=0.9,
        turnover=1.0, worst_year=2008, worst_year_return=-0.2, spy_tr_return=0.5,
        spy_tr_cagr=0.07, mar=0.5, failed="", eligible=True, dsr=0.95,
        n_trials_at_run=len(ROWS), curve_json="[]",
    )


def _cand(cid: str, n: int, rationale: str = "the idea arm") -> Candidate:
    return Candidate(
        id=cid, family=cid.split("-")[0], rules=MONTHLY_HOLD_FRAC, allocator=TIMING,
        params=TimingParams(hold="SPY", signal="SPY", rule="sma", n=n),
        rationale=rationale, added=date(2026, 11, 1), owner_inputs=(),
    )


def _methods() -> dict:
    out = {}
    for mid in ("M0001", "M0002"):
        cands = tuple(
            _cand(f"{m}-{s}", 10 + i, CONTROL_RATIONALE if f"{m}-{s}" == "M0001-E" else "the idea arm")
            for i, (m, s, _sr, _dd) in enumerate(ROWS)
            if m == mid
        )
        out[mid] = (
            Method(id=mid, name=f"{mid} test method", family="test", source_kind="knowledge",
                   source_ref="", hypothesis="h", expected_failure="f", candidates=cands),
            HERE,
        )
    return out


def _build(path: Path) -> tuple[sqlite3.Connection, dict[str, int]]:
    """A lab holding ROWS as recorded dev trials, every one with provenance at 10M IDR."""
    conn = store.connect(path)
    with conn:
        for mid in ("M0001", "M0002"):
            store.add_method(conn, id=mid, name="n", family="f", source_kind="knowledge",
                             hypothesis="h", status="registered")
        ns = store.insert_trials(conn, [_trial(*r) for r in ROWS])
        stamp_provenance(conn, ns)
    return conn, {f"{m}-{s}": n for (m, s, _sr, _dd), n in zip(ROWS, ns, strict=True)}


@pytest.fixture()
def wired(monkeypatch):
    """Everything outside the database the command reads, pinned for the test."""
    monkeypatch.setattr(store, "DSR_POLICY", "all-trials")
    monkeypatch.setattr(method_mod, "discover", _methods)
    monkeypatch.setattr(runner, "git_head", lambda cwd: "test-sha")


@pytest.fixture()
def lab(tmp_path, wired):
    path = tmp_path / "lab.sqlite"
    conn, ns = _build(path)
    g = store.gate(conn)
    assert g.n == len(ROWS), "the fixture's DSRs read back exactly only at N = the dev row count"
    for row in store.trials_of(conn, "M0001") + store.trials_of(conn, "M0002"):
        assert store.verdict(conn, row, at=g).eligible is (row["candidate_id"] in ELIGIBLE)
    assert control_shape.role_of(_methods()["M0001"][0].candidates[4]) == control_shape.ROLE_CONTROL
    yield conn, path, ns
    conn.close()


@pytest.fixture(scope="module")
def smoke():
    return smoke_data()


def _serve(monkeypatch, data) -> None:
    monkeypatch.setattr(research, "load_store", lambda *a, **k: data)


def _never_load(monkeypatch) -> None:
    def boom(*a, **k):
        raise AssertionError("the research store must not be loaded for this request")

    monkeypatch.setattr(research, "load_store", boom)


def _stand_in(calls: list, *, beaten: int = 18, raises: Exception | None = None):
    """A deterministic ``yardstick.measure``: same answer for any ``jobs``, every call logged."""

    def measure(market, dividends, spy_dividends, candidate, *, initial_idr, contributions,
                draws=yardstick.DRAWS, jobs=1, expect=None):
        calls.append({"candidate": candidate.id, "initial_idr": initial_idr,
                      "contributions": contributions, "draws": draws, "jobs": jobs,
                      "expect": expect})
        if raises is not None:
            raise raises
        return yardstick.Measurement(
            status=yardstick.STATUS_MEASURED, draws=draws, arm_rate=0.12,
            beaten=min(beaten, draws), percentile=min(beaten, draws) / draws,
            rates=tuple(0.001 * i for i in range(draws)), trade_ratio=1.02, turnover_ratio=0.97,
            reproduced=None if expect is None else True,
        )

    return measure


def _argv(path: Path, tmp_path: Path, *rest: str) -> list[str]:
    return ["lab", "--db", str(path), "yardstick", *rest, "--store", str(tmp_path / "store")]


def _rows(conn) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM trial_yardstick ORDER BY trial_n, store_fingerprint").fetchall()


def _untouched(conn) -> tuple:
    """Everything a yardstick must leave as it found it (R1.2)."""
    return (
        store.dev_trial_count(conn),
        store.test_looks(conn),
        store.gate(conn).n,
        conn.execute("SELECT count(*) FROM trials").fetchone()[0],
        conn.execute("SELECT count(*) FROM trial_moments").fetchone()[0],
        conn.execute("SELECT count(*) FROM insights").fetchone()[0],
        tuple(tuple(r) for r in conn.execute("SELECT id, status, analysis FROM methods ORDER BY id")),
    )


def _row(trial_n: int, **kw) -> store.YardstickRow:
    base = dict(
        trial_n=trial_n, rule_id="yardstick-test", store_fingerprint=FP, status="measured",
        draws=20, arm_rate=0.12, beaten=18, percentile=0.9, rates_json="[]", trade_ratio=1.0,
        turnover_ratio=1.0, reproduced=True, git_sha="abc", measured="2026-11-13T00:00:00+00:00",
    )
    base.update(kw)
    return store.YardstickRow(**base)


# ---- the table ---------------------------------------------------------------------------------


def test_the_table_arrives_without_a_schema_version_and_is_append_only(lab):
    conn, _, ns = lab
    assert store.schema_version(conn) == store.SCHEMA_VERSION == "8"
    with conn:
        assert store.insert_yardstick(conn, _row(ns["M0001-A"])) is True
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("UPDATE trial_yardstick SET beaten = 20")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("DELETE FROM trial_yardstick")


def test_the_status_list_is_the_engines():
    assert store.YARDSTICK_STATUSES == (
        yardstick.STATUS_MEASURED, yardstick.STATUS_NOT_APPLICABLE, yardstick.STATUS_UNMATCHED,
    )


def test_the_label_is_derived_from_the_bar():
    assert store.YARDSTICK_MIN_PERCENTILE == 0.90
    assert store.YARDSTICK_LABEL == "beats 90% of random twins"
    assert f"{store.YARDSTICK_MIN_PERCENTILE:.0%}" in store.YARDSTICK_LABEL


def test_the_control_role_spelled_in_store_is_control_shapes():
    assert control_shape.ROLE_CONTROL == "control"


def test_a_repeat_on_the_same_key_writes_nothing_and_another_store_is_a_new_row(lab):
    conn, _, ns = lab
    n = ns["M0001-A"]
    with conn:
        assert store.insert_yardstick(conn, _row(n)) is True
        assert store.insert_yardstick(conn, _row(n, beaten=3, percentile=0.15)) is False
        assert store.insert_yardstick(conn, _row(n, store_fingerprint=OTHER_FP)) is True
        assert store.insert_yardstick(conn, _row(n, rule_id="yardstick-other")) is True
    assert conn.execute("SELECT count(*) FROM trial_yardstick").fetchone()[0] == 3
    kept = conn.execute(
        "SELECT beaten FROM trial_yardstick WHERE trial_n = ? AND rule_id = 'yardstick-test' "
        "AND store_fingerprint = ?", (n, FP),
    ).fetchone()[0]
    assert kept == 18, "the first measurement is the one kept"
    assert store.has_yardstick(conn, n, "yardstick-test", FP)
    assert not store.has_yardstick(conn, n, "yardstick-test", "fp-never")


@pytest.mark.parametrize(
    ("kw", "match"),
    [
        (dict(trial_n=0), "trial number of a recorded trial"),
        (dict(trial_n=999), "no trial #999"),
        (dict(status="passed"), "must be one of"),
        (dict(status="not-applicable", draws=5, beaten=0, percentile=None), "simulated no twin"),
        (dict(status="not-applicable", draws=0, beaten=0, percentile=None, trade_ratio=1.0,
              turnover_ratio=None), "simulated no twin"),
        (dict(status="measured", percentile=None), "needs its twins"),
        (dict(status="unmatched", draws=0, beaten=0, percentile=None), "needs its twins"),
        (dict(status="measured", beaten=21), "needs its twins"),
    ],
)
def test_insert_refuses_what_the_record_cannot_mean(lab, kw, match):
    conn, _, ns = lab
    with pytest.raises(store.LabError, match=match):
        # A case may name its own trial number (the sentinel 0, a trial the lab does not hold).
        store.insert_yardstick(conn, _row(**{"trial_n": ns["M0001-A"], **kw}))
    assert conn.execute("SELECT count(*) FROM trial_yardstick").fetchone()[0] == 0


def test_insert_refuses_a_test_window_look(lab):
    conn, _, ns = lab
    look = dataclasses.replace(
        _trial("M0001", "A", 0.80, 0.20), config_digest="M0001-A-test", window="test"
    )
    with conn:
        (n,) = store.insert_trials(conn, [look])
    with pytest.raises(store.LabError, match="not a dev arm"):
        store.insert_yardstick(conn, _row(n))


def test_a_not_applicable_row_records_no_draws(lab):
    conn, _, ns = lab
    with conn:
        assert store.insert_yardstick(conn, _row(
            ns["M0001-A"], status="not-applicable", draws=0, beaten=0, percentile=None,
            arm_rate=0.1, trade_ratio=None, turnover_ratio=None, reproduced=None,
        ))
    got = store.yardstick_of(conn, ns["M0001-A"])
    assert (got["status"], got["draws"], got["beaten"], got["percentile"], got["reproduced"]) == (
        "not-applicable", 0, 0, None, None)


def test_from_measurement_takes_every_shape_the_engine_returns():
    """Decision D11: phase 2's ``Measurement`` constructor is the source of truth for a reading's
    shape, and every shape it admits becomes a row ``insert_yardstick`` accepts."""
    na = yardstick.Measurement(
        status=yardstick.STATUS_NOT_APPLICABLE, draws=0, arm_rate=0.1, beaten=0,
        percentile=None, rates=(), trade_ratio=None, turnover_ratio=None, reproduced=None,
    )
    odd = yardstick.Measurement(
        status=yardstick.STATUS_UNMATCHED, draws=4, arm_rate=0.1, beaten=3, percentile=0.75,
        rates=(0.01, 0.02, 0.03, 0.2), trade_ratio=2.6, turnover_ratio=1.0, reproduced=True,
    )
    for m, checked in ((na, True), (odd, True), (odd, False)):
        row = store.YardstickRow.from_measurement(
            m, trial_n=1, rule_id="r", store_fingerprint="fp", checked=checked, git_sha="g",
            measured="2026-11-14T00:00:00+00:00",
        )
        assert (row.status, row.draws, row.beaten, row.percentile) == (
            m.status, m.draws, m.beaten, m.percentile)
        assert row.reproduced is (None if not checked or m.reproduced is None else True)
    assert store.YardstickRow.from_measurement(
        na, trial_n=1, rule_id="r", store_fingerprint="fp", checked=True, git_sha="g", measured="t",
    ).rates_json == "[]"


def test_yardstick_of_is_the_newest_row(lab):
    conn, _, ns = lab
    n = ns["M0001-B"]
    assert store.yardstick_of(conn, n) is None
    with conn:
        store.insert_yardstick(conn, _row(n, measured="2026-11-13T00:00:00+00:00", beaten=4,
                                          percentile=0.2))
        store.insert_yardstick(conn, _row(n, store_fingerprint=OTHER_FP,
                                          measured="2026-11-14T00:00:00+00:00", beaten=19,
                                          percentile=0.95))
    got = store.yardstick_of(conn, n)
    assert (got["store_fingerprint"], got["beaten"]) == (OTHER_FP, 19)


def test_the_readers_answer_nothing_on_a_database_without_the_table(tmp_path):
    """A connect_readonly caller on a database no yardstick-aware code has opened for writing."""
    schema = store._SCHEMA
    for ddl in (store._YARDSTICK_TABLE, *store._YARDSTICK_TRIGGERS):
        assert f"{ddl};\n\n" in schema
        schema = schema.replace(f"{ddl};\n\n", "")
    assert "trial_yardstick" not in schema
    path = tmp_path / "old.sqlite"
    raw = sqlite3.connect(path)
    raw.executescript(schema)
    raw.commit()
    raw.close()
    ro = store.connect_readonly(path)
    try:
        assert store.yardstick_of(ro, 1) is None
        assert store.has_yardstick(ro, 1, "yardstick-v1", FP) is False
    finally:
        ro.close()


# ---- the bar and the due rule ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("row", "clears"),
    [
        (None, None),
        ({"status": "measured", "percentile": 0.90}, True),
        ({"status": "measured", "percentile": 0.95}, True),
        ({"status": "measured", "percentile": 0.895}, False),
        ({"status": "measured", "percentile": None}, False),
        ({"status": "not-applicable", "percentile": None}, True),
        ({"status": "unmatched", "percentile": 0.99}, False),
        ({"status": "something-new", "percentile": 0.99}, False),
    ],
)
def test_yardstick_clears(row, clears):
    assert store.yardstick_clears(row) is clears


def test_yardstick_clears_reads_a_row_a_dict_and_a_dataclass_alike(lab):
    """Phase 4 asks this on the ``sqlite3.Row`` ``yardstick_of`` returns, on plain dicts and on
    ``dataclasses.asdict(YardstickRow)``: one clearing rule, whatever the mapping."""
    conn, _, ns = lab
    passing, failing = _row(ns["M0001-A"]), _row(ns["M0001-B"], beaten=4, percentile=0.2)
    with conn:
        store.insert_yardstick(conn, passing)
        store.insert_yardstick(conn, failing)
    for row, clears in ((passing, True), (failing, False)):
        assert store.yardstick_clears(store.yardstick_of(conn, row.trial_n)) is clears
        assert store.yardstick_clears(dataclasses.asdict(row)) is clears
        assert store.yardstick_clears(
            {"status": row.status, "percentile": row.percentile}) is clears


def test_yardstick_due_is_an_eligible_dev_arm(lab):
    conn, _, ns = lab
    g = store.gate(conn)
    due = {
        t["candidate_id"]
        for t in store.trials_of(conn, "M0001") + store.trials_of(conn, "M0002")
        if store.yardstick_due(conn, t, at=g)
    }
    # M0001-E is eligible and a control by its rationale, but no role is RECORDED for it yet, and
    # yardstick_due reads the record only. The command skips it by its rationale (see below).
    assert due == ELIGIBLE
    row = store.trials_of(conn, "M0001")[0]
    assert store.yardstick_due(conn, {**dict(row), "window": "test"}, at=g) is False


def test_a_recorded_control_is_never_due_and_never_forced(lab, tmp_path, monkeypatch):
    conn, path, ns = lab
    with conn:
        store.insert_roles(conn, [store.RoleRow(
            trial_n=ns["M0001-B"], role="control", source="backfill", measured="test fixture",
        )])
    row = conn.execute("SELECT * FROM trials WHERE n = ?", (ns["M0001-B"],)).fetchone()
    assert store.yardstick_due(conn, row) is False
    _never_load(monkeypatch)
    assert cli.main(_argv(path, tmp_path, "--arm", "M0001-B")) == 2
    assert _rows(conn) == []


def test_an_arm_failing_only_on_the_yardstick_is_still_due(lab, monkeypatch):
    """Stays right once the yardstick is a condition in verdict (phase 4)."""
    conn, _, ns = lab
    row = conn.execute("SELECT * FROM trials WHERE n = ?", (ns["M0001-A"],)).fetchone()

    def reads(*failed):
        return lambda conn, trial, *, at=None, policy=None: store.Verdict(
            dsr=0.95, failed=failed, eligible=not failed, n=len(ROWS), policy="all-trials",
            derived=True,
        )

    monkeypatch.setattr(store, "verdict", reads(store.YARDSTICK_LABEL))
    assert store.yardstick_due(conn, row) is True
    monkeypatch.setattr(store, "verdict", reads(store.YARDSTICK_LABEL, store.DSR_LABEL))
    assert store.yardstick_due(conn, row) is False


# ---- the command -------------------------------------------------------------------------------


def test_cli_measures_each_due_arm_once_and_records_no_trial(lab, smoke, tmp_path, monkeypatch, capsys):
    conn, path, ns = lab
    before = _untouched(conn)
    calls: list = []
    monkeypatch.setattr(yardstick, "measure", _stand_in(calls))
    _serve(monkeypatch, dataclasses.replace(smoke, fingerprint=FP))
    assert cli.main(_argv(path, tmp_path, "M0001")) == 0
    out = capsys.readouterr().out
    # C fails the drawdown screen; E is a control by its rationale and is skipped with a reason.
    assert [c["candidate"] for c in calls] == ["M0001-A", "M0001-B", "M0001-D"]
    assert "skipped M0001-E: a control arm by its rationale" in out
    for c in calls:
        assert c["draws"] == yardstick.DRAWS and c["jobs"] == 1
        assert c["initial_idr"] == Decimal("10000000") and c["contributions"] is None
        assert c["expect"] == (200, 1.0), "recorded on the loaded store: reproduce it first"
    rows = _rows(conn)
    assert [r["trial_n"] for r in rows] == [ns["M0001-A"], ns["M0001-B"], ns["M0001-D"]]
    for r in rows:
        assert (r["rule_id"], r["store_fingerprint"], r["status"]) == (yardstick.RULE_ID, FP, "measured")
        assert (r["draws"], r["beaten"], r["reproduced"], r["git_sha"]) == (yardstick.DRAWS, 18, 1, "test-sha")
    assert "3 arm(s) recorded" in out and "never a trial" in out
    assert _untouched(conn) == before

    # A repeat on the same store simulates nothing and writes nothing (R1.5).
    assert cli.main(_argv(path, tmp_path, "M0001")) == 0
    out = capsys.readouterr().out
    assert len(calls) == 3
    assert len(_rows(conn)) == 3
    assert "already measured on store" in out and "0 arm(s) recorded" in out
    assert _untouched(conn) == before


def test_another_store_is_a_new_row_with_nothing_to_reproduce(lab, smoke, tmp_path, monkeypatch):
    conn, path, ns = lab
    calls: list = []
    monkeypatch.setattr(yardstick, "measure", _stand_in(calls))
    _serve(monkeypatch, dataclasses.replace(smoke, fingerprint=OTHER_FP))
    assert cli.main(_argv(path, tmp_path, "--arm", "M0001-A")) == 0
    assert calls[0]["expect"] is None
    (row,) = _rows(conn)
    assert (row["store_fingerprint"], row["reproduced"]) == (OTHER_FP, None)


def test_an_arm_that_does_not_reproduce_is_refused_with_exit_2_and_nothing_written(
    lab, smoke, tmp_path, monkeypatch, capsys
):
    conn, path, ns = lab
    before = _untouched(conn)
    calls: list = []
    monkeypatch.setattr(yardstick, "measure", _stand_in(
        calls, raises=yardstick.Unreproducible("199 trades against 200 recorded"),
    ))
    _serve(monkeypatch, dataclasses.replace(smoke, fingerprint=FP))
    assert cli.main(_argv(path, tmp_path, "--arm", "M0001-A")) == 2
    assert calls[0]["expect"] == (200, 1.0)
    assert _rows(conn) == []
    assert "does not reproduce" in capsys.readouterr().out
    assert _untouched(conn) == before


def test_a_not_applicable_arm_on_its_recording_store_is_recorded_with_reproduced_null(
    lab, smoke, tmp_path, monkeypatch
):
    """Decision D12: a bracket (or ETF-only) arm reads not-applicable and the engine never re-runs
    a bracket arm, so ``reproduced`` comes back None even with ``expect`` given. R1.6 cannot fire
    for it, and the row says "not checked", never "checked and passed"."""
    conn, path, ns = lab
    calls: list = []

    def measure(market, dividends, spy_dividends, candidate, *, initial_idr, contributions,
                draws=yardstick.DRAWS, jobs=1, expect=None):
        calls.append(expect)
        return yardstick.Measurement(
            status=yardstick.STATUS_NOT_APPLICABLE, draws=0, arm_rate=None, beaten=0,
            percentile=None, rates=(), trade_ratio=None, turnover_ratio=None, reproduced=None,
        )

    monkeypatch.setattr(yardstick, "measure", measure)
    _serve(monkeypatch, dataclasses.replace(smoke, fingerprint=FP))
    assert cli.main(_argv(path, tmp_path, "--arm", "M0001-A")) == 0
    assert calls == [(200, 1.0)], "recorded on the loaded store: expect was passed"
    (row,) = _rows(conn)
    assert (row["status"], row["draws"], row["beaten"], row["percentile"], row["reproduced"]) == (
        "not-applicable", 0, 0, None, None)
    assert store.yardstick_clears(row) is True


def test_a_refused_arm_does_not_stop_the_sweep_but_the_exit_is_2(lab, smoke, tmp_path, monkeypatch):
    conn, path, ns = lab
    calls: list = []
    good = _stand_in(calls)

    def measure(market, dividends, spy_dividends, candidate, **kw):
        if candidate.id == "M0001-B":
            calls.append({"candidate": candidate.id})
            raise yardstick.Unreproducible("return differs")
        return good(market, dividends, spy_dividends, candidate, **kw)

    monkeypatch.setattr(yardstick, "measure", measure)
    _serve(monkeypatch, dataclasses.replace(smoke, fingerprint=FP))
    assert cli.main(_argv(path, tmp_path, "M0001")) == 2
    assert [r["trial_n"] for r in _rows(conn)] == [ns["M0001-A"], ns["M0001-D"]]


def test_arm_forces_an_arm_that_is_not_due_but_never_a_control(lab, smoke, tmp_path, monkeypatch):
    conn, path, ns = lab
    calls: list = []
    monkeypatch.setattr(yardstick, "measure", _stand_in(calls))
    _serve(monkeypatch, dataclasses.replace(smoke, fingerprint=FP))
    assert cli.main(_argv(path, tmp_path, "--arm", "M0001-C")) == 0  # fails drawdown, forced
    assert [r["trial_n"] for r in _rows(conn)] == [ns["M0001-C"]]
    assert cli.main(_argv(path, tmp_path, "--arm", "M0001-E")) == 2  # control by its rationale
    assert cli.main(_argv(path, tmp_path, "--arm", "M0001-Z")) == 2  # no such arm
    assert [c["candidate"] for c in calls] == ["M0001-C"]
    assert len(_rows(conn)) == 1


def test_pending_takes_the_oldest_due_arms_first_and_limit_caps_them(
    lab, smoke, tmp_path, monkeypatch, capsys
):
    conn, path, ns = lab
    calls: list = []
    monkeypatch.setattr(yardstick, "measure", _stand_in(calls))
    _serve(monkeypatch, dataclasses.replace(smoke, fingerprint=FP))
    assert cli.main(_argv(path, tmp_path, "--pending", "--limit", "2")) == 0
    assert [c["candidate"] for c in calls] == ["M0001-A", "M0001-B"]
    assert "due arm(s) left for a later run" in capsys.readouterr().out
    assert cli.main(_argv(path, tmp_path, "--pending")) == 0
    assert [c["candidate"] for c in calls] == ["M0001-A", "M0001-B", "M0001-D", "M0002-A", "M0002-B"]
    assert len(_rows(conn)) == 5


@pytest.mark.parametrize("where", ["global", "local"])
def test_dry_run_measures_and_writes_nothing(lab, smoke, tmp_path, monkeypatch, capsys, where):
    conn, path, ns = lab
    calls: list = []
    monkeypatch.setattr(yardstick, "measure", _stand_in(calls))
    _serve(monkeypatch, dataclasses.replace(smoke, fingerprint=FP))
    argv = _argv(path, tmp_path, "--arm", "M0001-A")
    argv = ["--dry-run", *argv] if where == "global" else [*argv, "--dry-run"]
    assert cli.main(argv) == 0
    assert len(calls) == 1
    assert _rows(conn) == []
    assert "dry run: not recorded" in capsys.readouterr().out


def test_jobs_reaches_the_simulator_and_never_the_record(tmp_path, wired, smoke, monkeypatch):
    """R1.5's command half: J is passed through and is not part of what is recorded."""
    recorded = []
    for jobs in ("1", "3"):
        path = tmp_path / f"jobs{jobs}" / "lab.sqlite"
        conn, _ns = _build(path)
        calls: list = []
        monkeypatch.setattr(yardstick, "measure", _stand_in(calls))
        _serve(monkeypatch, dataclasses.replace(smoke, fingerprint=FP))
        assert cli.main(_argv(path, tmp_path, "--arm", "M0001-A", "--jobs", jobs)) == 0
        assert calls[0]["jobs"] == int(jobs)
        (row,) = _rows(conn)
        recorded.append({k: row[k] for k in row.keys() if k != "measured"})
        conn.close()
    assert recorded[0] == recorded[1]


def test_a_survivorship_check_store_is_refused(lab, smoke, tmp_path, monkeypatch):
    conn, path, _ = lab
    calls: list = []
    monkeypatch.setattr(yardstick, "measure", _stand_in(calls))
    _serve(monkeypatch, dataclasses.replace(smoke, fingerprint=FP, purpose="survivorship-check"))
    assert cli.main(_argv(path, tmp_path, "--arm", "M0001-A")) == 2
    assert calls == [] and _rows(conn) == []


@pytest.mark.parametrize(
    "rest",
    [
        (),                                 # no selector
        ("M0001", "--pending"),             # two selectors
        ("M0001", "--arm", "M0001-A"),      # two selectors
        ("M0099",),                         # no such method
        ("--arm", "M0099-A"),               # no such arm
    ],
)
def test_a_bad_request_is_exit_2_before_any_store(lab, tmp_path, monkeypatch, rest):
    conn, path, _ = lab
    _never_load(monkeypatch)
    assert cli.main(_argv(path, tmp_path, *rest)) == 2
    assert _rows(conn) == []


def test_nothing_due_loads_no_store(tmp_path, wired, monkeypatch, capsys):
    path = tmp_path / "lab.sqlite"
    conn, _ = _build(path)
    with conn:
        store.add_method(conn, id="M0003", name="n", family="f", source_kind="knowledge",
                         hypothesis="h", status="registered")
    _never_load(monkeypatch)
    assert cli.main(_argv(path, tmp_path, "M0003")) == 0
    assert "nothing to measure" in capsys.readouterr().out
    conn.close()


def test_the_yardstick_help_strings_still_format(capsys):
    """argparse %-interpolates every help= string; a bare % there kills `lab --help`."""
    with pytest.raises(SystemExit) as e:
        cli.main(["lab", "yardstick", "--help"])
    assert e.value.code == 0
    out = capsys.readouterr().out
    assert "--pending" in out and "--jobs" in out

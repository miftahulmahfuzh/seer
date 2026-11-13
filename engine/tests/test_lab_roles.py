"""Arm roles in the record (random-twin-yardstick phase 1, R3).

An arm registered to be beaten -- a placebo, a paired baseline, a mirror -- never makes its
method ``dev-eligible``. This file proves the four halves of that: ``lab run`` records each arm's
role and lets only a non-control arm decide the status (R3.1); ``store.verdict`` refuses a
recorded control and ``best_dev_eligible`` therefore never chooses one (R3.2); ``lab reevaluate
--demote`` moves a stale ``dev-eligible`` method back to ``rejected`` without touching a trial
(R3.3); and ``lab roles --backfill`` records the role of every readable recorded arm, once
(R3.4). Plus plan invariant 5: a database with no role row reads exactly as it did.

Every test builds its own temp lab. Nothing here opens the committed ``lab/lab.sqlite``.
"""

from __future__ import annotations

import argparse
import dataclasses
import sqlite3
import types
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pytest
from labkit import smoke_data

from seer_engine.backtest import dev as dev_module
from seer_engine.backtest.dev import Candidate
from seer_engine.commands import lab as lab_cmd
from seer_engine.lab import control_shape, runner, store
from seer_engine.lab.method import Amendment, Method
from seer_engine.lab.seed import seed
from seer_engine.sim.rules import DAILY_SWITCH, MONTHLY_HOLD
from seer_engine.strategies.f_index import TIMING, TimingParams

HERE = Path(__file__)
R_IDEA = "The idea: the twenty strongest names in the pool, equal slots, nothing timed"
R_CONTROL = "Control: the same book with the brake taken out, nothing else changed"

# `_lab` records exactly N dev rows, and every one carries n_trials_at_run=N, so judged at
# Gate(N) the derived DSR is the recorded one (``recover_dsr``'s identity) and an eligibility
# assertion means what it says.
N = 5
G = store.Gate(n=N, policy="all-trials")
STAMP = "2026-11-13T00:00:00+00:00"


@pytest.fixture(autouse=True)
def _clean_gate_cache():
    store._GATE_CACHE.clear()
    yield
    store._GATE_CACHE.clear()


@pytest.fixture()
def all_trials(monkeypatch):
    """For the paths that resolve the gate themselves (``demote_method``, the CLI): judge `_lab`
    by its row count, the policy its rows were stamped under, so ``gate(conn).n == N``."""
    monkeypatch.setattr(store, "DSR_POLICY", "all-trials")


@pytest.fixture()
def conn(tmp_path):
    c = store.connect(tmp_path / "lab.sqlite")
    yield c
    c.close()


# ---- a hand-built lab ------------------------------------------------------------------------


def _trial(**kw) -> store.TrialRow:
    base = dict(
        method_id="M0001", candidate_id="M0001-A", config_digest="d1", config_text="t",
        rules_id="r", allocator_id="a", window="dev", start="2000-01-03", end="2015-10-16",
        store_fingerprint="fp", git_sha="abc", run_at=STAMP,
        total_return=1.0, cagr=0.1, max_drawdown=0.12, profit_factor=1.5, trades=200,
        sharpe=0.94, exposure=0.9, turnover=1.0, worst_year=2008, worst_year_return=-0.2,
        spy_tr_return=0.5, spy_tr_cagr=0.07, mar=0.8, failed="", eligible=True,
        dsr=0.9156, n_trials_at_run=N, curve_json="[]",
    )
    base.update(kw)
    return store.TrialRow(**base)


# A 55% fall, outside the 50% dev screen: an owner-condition miss whatever the role.
DD_MISS = dict(max_drawdown=0.55, sharpe=1.46, mar=0.1,
               failed=dev_module.FAILURE_LABELS[1], eligible=False)

ROLES = {"M0001-A": "idea", "M0001-CTRL": "control", "M0002-A": "idea",
         "M0002-CTRL": "control", "M0003-A": "treatment"}


def _lab(conn) -> None:
    """Three methods, five dev trials, no role recorded yet.

    - M0001 (dev-eligible): its idea misses the drawdown screen; its control clears every
      condition -- the stale shape R3.3 exists for.
    - M0002 (dev-eligible): idea and control both clear every condition; the control out-MARs it.
    - M0003 (rejected): one arm, a drawdown miss.
    """
    for mid, path in (("M0001", ("registered", "dev-eligible")),
                      ("M0002", ("registered", "dev-eligible")),
                      ("M0003", ("registered", "rejected"))):
        with conn:
            store.add_method(conn, id=mid, name=f"name {mid}", family="fam",
                             source_kind="knowledge", hypothesis="h")
            for s in path:
                store.update_method(conn, mid, status=s)
    with conn:
        store.insert_trials(conn, [
            _trial(candidate_id="M0001-A", config_digest="d1a", **DD_MISS),
            _trial(candidate_id="M0001-CTRL", config_digest="d1c", mar=0.95),
            _trial(method_id="M0002", candidate_id="M0002-A", config_digest="d2a"),
            _trial(method_id="M0002", candidate_id="M0002-CTRL", config_digest="d2c", mar=0.95),
            _trial(method_id="M0003", candidate_id="M0003-A", config_digest="d3a", **DD_MISS),
        ])


def _n(conn, cid: str) -> int:
    return int(conn.execute(
        "SELECT n FROM trials WHERE candidate_id = ? AND window = 'dev'", (cid,)
    ).fetchone()[0])


def _row(conn, cid: str):
    return conn.execute(
        "SELECT * FROM trials WHERE candidate_id = ? AND window = 'dev'", (cid,)
    ).fetchone()


def _record_roles(conn, roles=ROLES, source="recorded") -> None:
    with conn:
        store.insert_roles(conn, [
            store.RoleRow(trial_n=_n(conn, cid), role=role, source=source, measured=STAMP)
            for cid, role in roles.items()
        ])


def _trials_table(conn) -> list[tuple]:
    return [tuple(r) for r in conn.execute("SELECT * FROM trials ORDER BY n")]


def _lab_cli(db: Path, *argv: str) -> int:
    """The real parser and the real handler, as `python -m seer_engine lab ...` runs them."""
    p = argparse.ArgumentParser(prog="lab")
    lab_cmd.add_arguments(p)
    return lab_cmd.run(p.parse_args(["--db", str(db), *argv]))


@dataclass(frozen=True)
class _Arm:
    """An arm as `control_shape` reads one: an id and its author's one line."""

    id: str
    rationale: str


def _declare(monkeypatch, **by_method: list) -> None:
    """Make `method.discover()` see these arms and no others (the seam `_roles` reads through)."""
    from seer_engine.lab import method as method_mod

    files = {
        mid: (types.SimpleNamespace(id=mid, all_candidates=lambda arms=arms: tuple(arms)),
              Path(f"{mid}.py"))
        for mid, arms in by_method.items()
    }
    monkeypatch.setattr(method_mod, "discover", lambda: files)


# ---- the record ------------------------------------------------------------------------------


def test_the_store_names_the_roles_control_shape_answers():
    assert store.TRIAL_ROLES == control_shape.ROLES
    assert store.CONTROL_ROLE == control_shape.ROLE_CONTROL
    assert not store.is_luck_label(store.CONTROL_LABEL)


def test_trial_roles_arrives_on_connect_without_a_schema_version(conn):
    assert conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'trial_roles'"
    ).fetchone() is not None
    assert store.SCHEMA_VERSION == "8" and store.schema_version(conn) == "8"


def test_a_role_row_is_checked_once_and_is_append_only(conn):
    _lab(conn)
    n = _n(conn, "M0001-CTRL")
    with pytest.raises(store.LabError, match="insert_trials assigned"):
        store.insert_roles(conn, [store.RoleRow(0, "control", "recorded", STAMP)])
    with pytest.raises(store.LabError, match="not a role"):
        store.insert_roles(conn, [store.RoleRow(n, "placebo", "recorded", STAMP)])
    with pytest.raises(store.LabError, match="source 'guess'"):
        store.insert_roles(conn, [store.RoleRow(n, "control", "guess", STAMP)])
    with conn:
        store.insert_roles(conn, [store.RoleRow(n, "control", "recorded", STAMP)])
    assert store.role_of_trial(conn, n) == "control"
    with pytest.raises(store.LabError, match="already has a recorded role"):
        store.insert_roles(conn, [store.RoleRow(n, "idea", "backfill", STAMP)])
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        with conn:
            conn.execute("UPDATE trial_roles SET role = 'idea' WHERE trial_n = ?", (n,))
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        with conn:
            conn.execute("DELETE FROM trial_roles WHERE trial_n = ?", (n,))
    assert store.role_of_trial(conn, n) == "control"


def test_role_of_trial_is_none_without_a_row_or_without_the_table(conn, tmp_path):
    _lab(conn)
    assert store.role_of_trial(conn, _n(conn, "M0001-A")) is None
    old = sqlite3.connect(tmp_path / "old.sqlite")
    try:
        old.execute("CREATE TABLE trials (n INTEGER PRIMARY KEY)")
        assert store.role_of_trial(old, 1) is None
    finally:
        old.close()


# ---- R3.2: a recorded control is never eligible and never chosen ------------------------------


def test_a_recorded_control_reads_not_eligible_after_every_other_label(conn):
    _lab(conn)
    _record_roles(conn)
    v = store.verdict(conn, _row(conn, "M0002-CTRL"), at=G)
    # Its numbers clear every condition, its luck test included: the role is the only reason.
    assert v.derived is True and v.dsr == pytest.approx(0.9156, abs=1e-12)
    assert v.failed == (store.CONTROL_LABEL,) and v.eligible is False
    assert store.verdict(conn, _row(conn, "M0002-A"), at=G).eligible is True
    # A control that also misses the luck test: the role label still comes last.
    with conn:
        store.insert_trials(conn, [_trial(method_id="M0002", candidate_id="M0002-PLC",
                                          config_digest="d2p", dsr=0.5, mar=0.2)])
        store.insert_roles(conn, [store.RoleRow(_n(conn, "M0002-PLC"), "control", "recorded",
                                                STAMP)])
    assert store.verdict(conn, _row(conn, "M0002-PLC"), at=G).failed == (
        store.DSR_LABEL, store.CONTROL_LABEL,
    )


def test_best_dev_eligible_never_chooses_a_recorded_control(conn):
    _lab(conn)
    # Before any role is recorded the control out-MARs the idea and is chosen, exactly as today.
    assert store.best_dev_eligible(conn, "M0002", at=G)["candidate_id"] == "M0002-CTRL"
    assert store.best_dev_eligible(conn, "M0001", at=G)["candidate_id"] == "M0001-CTRL"
    _record_roles(conn)
    assert store.best_dev_eligible(conn, "M0002", at=G)["candidate_id"] == "M0002-A"
    assert store.best_dev_eligible(conn, "M0001", at=G) is None


def test_with_no_role_row_every_verdict_reads_as_it_did(conn):
    """Plan invariant 5: no role row, or no table at all, and nothing moves."""
    _lab(conn)
    expected = {"M0001-A": False, "M0001-CTRL": True, "M0002-A": True, "M0002-CTRL": True,
                "M0003-A": False}

    def read() -> dict[str, store.Verdict]:
        return {cid: store.verdict(conn, _row(conn, cid), at=G) for cid in expected}

    no_rows = read()
    assert {cid: v.eligible for cid, v in no_rows.items()} == expected
    assert all(store.CONTROL_LABEL not in v.failed for v in no_rows.values())
    with conn:
        conn.execute("DROP TABLE trial_roles")
    assert read() == no_rows


# ---- R3.3: the demotion door -----------------------------------------------------------------


def test_demote_moves_a_method_whose_only_eligible_arm_is_a_control(conn, all_trials):
    _lab(conn)
    _record_roles(conn)
    before = _trials_table(conn)
    n_before, looks_before = store.gate(conn).n, store.test_looks(conn)
    with conn:
        r = store.demote_method(conn, "M0001")
    assert r.moved is True
    assert (r.status_before, r.status_after) == ("dev-eligible", "rejected")
    assert r.eligible_now == () and r.controls == 1 and r.dev_trials == 2
    m = store.get_method(conn, "M0001")
    assert m["status"] == "rejected"
    assert store.DEMOTION_MARKER in m["analysis"]
    assert f"### {date.today().isoformat()}" in m["analysis"]
    assert "comparison arm" in m["analysis"]
    assert _trials_table(conn) == before
    assert store.gate(conn).n == n_before and store.test_looks(conn) == looks_before


def test_demote_leaves_a_method_that_has_an_eligible_non_control_arm(conn, all_trials):
    _lab(conn)
    _record_roles(conn)
    analysis = store.get_method(conn, "M0002")["analysis"]
    with conn:
        r = store.demote_method(conn, "M0002")
    assert r.moved is False and r.eligible_now == ("M0002-A",)
    assert store.get_method(conn, "M0002")["status"] == "dev-eligible"
    assert store.get_method(conn, "M0002")["analysis"] == analysis


def test_demote_moves_only_from_dev_eligible_and_only_once(conn, all_trials):
    _lab(conn)
    _record_roles(conn)
    with conn:
        assert store.demote_method(conn, "M0003").moved is False      # already rejected
        assert store.demote_method(conn, "M0001").moved is True
    after = store.get_method(conn, "M0001")["analysis"]
    with conn:
        again = store.demote_method(conn, "M0001")
    assert again.moved is False and again.status_before == "rejected"
    assert store.get_method(conn, "M0001")["analysis"] == after
    with conn:
        store.add_method(conn, id="M0004", name="n", family="f", source_kind="knowledge",
                         hypothesis="h")
        store.update_method(conn, "M0004", status="registered")
        store.update_method(conn, "M0004", status="dev-eligible")
        assert store.demote_method(conn, "M0004").moved is False      # no dev trial to judge
    assert store.get_method(conn, "M0004")["status"] == "dev-eligible"
    with pytest.raises(store.LabError, match="no method M0999"):
        store.demote_method(conn, "M0999")


def test_an_unrecorded_control_still_counts_so_demotion_can_only_under_reach(conn, all_trials):
    _lab(conn)                                                         # no role rows
    with conn:
        r = store.demote_method(conn, "M0001")
    assert r.moved is False and r.eligible_now == ("M0001-CTRL",)
    assert store.get_method(conn, "M0001")["status"] == "dev-eligible"


def test_demote_sweeps_every_dev_eligible_method(conn, all_trials):
    _lab(conn)
    _record_roles(conn)
    with conn:
        results = store.demote(conn)
    assert [r.method_id for r in results] == ["M0001", "M0002"]
    assert [r.method_id for r in results if r.moved] == ["M0001"]


def test_plain_reevaluate_takes_a_demoted_method_back_when_its_arm_clears_again(
    conn, all_trials, monkeypatch
):
    """The door is reversible (Decision D10). M0002-A was recorded eligible (1), so without the
    demotion marker ``reevaluate_method`` would never look at it again."""
    _lab(conn)
    _record_roles(conn)
    monkeypatch.setattr(store, "DSR_MIN", 0.95)      # M0002-A's 0.9156 now misses the luck bar
    with conn:
        assert store.demote_method(conn, "M0002").moved is True
    assert _row(conn, "M0002-A")["eligible"] == 1
    monkeypatch.setattr(store, "DSR_MIN", 0.90)      # the bar moves back
    with conn:
        r = store.reevaluate_method(conn, "M0002")
    assert r.moved is True and r.unblocked == ("M0002-A",)   # never the control
    m = store.get_method(conn, "M0002")
    assert m["status"] == "dev-eligible"
    assert store.DEMOTION_MARKER in m["analysis"] and store.REEVALUATION_MARKER in m["analysis"]
    # A rejected method that was never demoted keeps the narrow rule: M0003's one arm misses the
    # drawdown screen and stays rejected.
    with conn:
        assert store.reevaluate_method(conn, "M0003").moved is False


def test_the_edge_back_is_a_transition_and_nothing_else_opened(conn):
    assert ("dev-eligible", "rejected") in store.TRANSITIONS
    assert conn.execute(
        "SELECT 1 FROM transitions WHERE src = 'dev-eligible' AND dst = 'rejected'"
    ).fetchone() is not None
    _lab(conn)
    with conn:
        store.update_method(conn, "M0002", status="rejected")
    with pytest.raises(store.LabError, match="forward"):
        store.update_method(conn, "M0003", status="promoted")


def test_reevaluate_demote_moves_the_stale_method_and_plain_reevaluate_does_not(
    tmp_path, all_trials, capsys
):
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _lab(c)
    _record_roles(c)
    before = _trials_table(c)
    c.close()

    assert _lab_cli(db, "reevaluate") == 0
    c = store.connect(db)
    assert store.get_method(c, "M0001")["status"] == "dev-eligible"   # plain never demotes
    c.close()
    capsys.readouterr()

    assert _lab_cli(db, "reevaluate", "--demote") == 0
    out = capsys.readouterr().out
    assert "M0001: dev-eligible -> rejected" in out
    assert "M0002: still dev-eligible (M0002-A)" in out
    assert "1 method(s) moved dev-eligible -> rejected" in out
    c = store.connect(db)
    assert store.get_method(c, "M0001")["status"] == "rejected"
    assert store.get_method(c, "M0002")["status"] == "dev-eligible"
    assert _trials_table(c) == before
    c.close()

    assert _lab_cli(db, "reevaluate", "--demote") == 0
    assert "0 method(s) moved dev-eligible -> rejected" in capsys.readouterr().out
    assert _lab_cli(db, "reevaluate", "--demote", "M0999") == 2


# ---- R3.4: the backfill ----------------------------------------------------------------------


def test_backfill_records_every_readable_arm_once_and_skips_the_rest(tmp_path, monkeypatch,
                                                                     all_trials, capsys):
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    seed(c)                                       # the P7a seed trials: no method file, ever
    _lab(c)
    with c:
        # A test-window look of M0001-A: never given a role.
        store.insert_trials(c, [_trial(candidate_id="M0001-A", config_digest="d1a",
                                       window="test")])
        # A role the run itself recorded: never offered to the backfill.
        store.insert_roles(c, [store.RoleRow(_n(c, "M0002-A"), "idea", "recorded", STAMP)])
    before = _trials_table(c)
    dev_before, n_before = store.dev_trial_count(c), store.gate(c).n
    c.close()
    # M0001's file declares both arms; M0002's only its idea; M0003 has no file at all.
    _declare(monkeypatch, M0001=[_Arm("M0001-A", R_IDEA), _Arm("M0001-CTRL", R_CONTROL)],
             M0002=[_Arm("M0002-A", R_IDEA)])

    assert _lab_cli(db, "roles", "--backfill") == 0
    out = capsys.readouterr().out
    skipped = dev_before - 3
    assert "recorded 2 role(s)" in out and f"skipped {skipped} dev arm(s)" in out
    c = store.connect(db)
    got = {r["candidate_id"]: (r["window"], r["role"], r["source"]) for r in c.execute(
        "SELECT t.candidate_id, t.window, r.role, r.source FROM trial_roles r "
        "JOIN trials t ON t.n = r.trial_n"
    )}
    assert got == {
        "M0001-A": ("dev", "idea", "backfill"),
        "M0001-CTRL": ("dev", "control", "backfill"),
        "M0002-A": ("dev", "idea", "recorded"),
    }
    assert _trials_table(c) == before
    assert store.dev_trial_count(c) == dev_before and store.gate(c).n == n_before
    c.close()

    assert _lab_cli(db, "roles", "--backfill") == 0                    # idempotent
    assert "recorded 0 role(s)" in capsys.readouterr().out
    c = store.connect(db)
    assert c.execute("SELECT count(*) FROM trial_roles").fetchone()[0] == 3
    c.close()

    assert _lab_cli(db, "roles") == 0
    assert f"no role recorded: {skipped} (0 readable now" in capsys.readouterr().out


def test_roles_lists_a_method_arm_by_arm_and_refuses_an_unknown_one(tmp_path, monkeypatch,
                                                                    capsys):
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _lab(c)
    _record_roles(c, {"M0001-CTRL": "control"})
    c.close()
    _declare(monkeypatch, M0001=[_Arm("M0001-A", R_IDEA), _Arm("M0001-CTRL", R_CONTROL)])
    assert _lab_cli(db, "roles", "M0999") == 2
    assert _lab_cli(db, "roles", "M0001") == 0
    lines = {line.split()[0]: line for line in capsys.readouterr().out.splitlines()
             if line.startswith("  ")}
    assert "control" in lines["M0001-CTRL"] and "recorded" in lines["M0001-CTRL"]
    assert "not recorded" in lines["M0001-A"] and "reads idea" in lines["M0001-A"]


def test_the_new_help_text_formats(capsys):
    p = argparse.ArgumentParser(prog="lab")
    lab_cmd.add_arguments(p)
    for argv in (["roles", "--help"], ["reevaluate", "--help"]):
        with pytest.raises(SystemExit) as e:
            p.parse_args(argv)
        assert e.value.code == 0
    assert "--backfill" in capsys.readouterr().out


# ---- R3.1: `lab run` records roles and only a non-control arm decides the status -------------


def _cand(cid: str, rules=MONTHLY_HOLD, n: int = 50, rationale: str = "test") -> Candidate:
    return Candidate(
        id=cid, family=cid.split("-")[0], rules=rules, allocator=TIMING,
        params=TimingParams(hold="SPY", signal="SPY", rule="sma", n=n),
        rationale=rationale, added=date(2026, 10, 4), owner_inputs=(),
    )


IDEA = _cand("M0001-A")
CONTROL = _cand("M0001-B", rules=DAILY_SWITCH, n=20, rationale=R_CONTROL)


def _method(cands=(IDEA, CONTROL), amendments=()) -> Method:
    return Method(id="M0001", name="SMA test", family="trend", source_kind="knowledge",
                  source_ref="", hypothesis="h", expected_failure="f",
                  candidates=tuple(cands), amendments=tuple(amendments))


@pytest.fixture()
def seeded(tmp_path):
    c = store.connect(tmp_path / "lab.sqlite")
    seed(c)
    yield c
    c.close()


@pytest.fixture(scope="module")
def data():
    return smoke_data()


def _force(monkeypatch, *, eligible: set[str]) -> None:
    """Make the D8 screen say what the test needs, and nothing else.

    The smoke market cannot be steered into clearing D8, so each simulated row is rewritten on its
    way out of ``dev.run_registry``: an arm in ``eligible`` clears all five conditions, every other
    arm misses one (the trade count). ``DSR_MIN`` drops below any DSR, so the luck test passes for
    every arm. What is left to decide eligibility is exactly the rule under test -- the role.
    """
    real = dev_module.run_registry
    trades = next(label for label in dev_module.FAILURE_LABELS if "trades" in label)

    def run_registry(*a, on_result=None, **k):
        def hook(i, result, row):
            if row.candidate.id in eligible:
                row = dataclasses.replace(row, failed=(), eligible=True, beats_spy=True)
            else:
                row = dataclasses.replace(row, failed=(trades,), eligible=False, beats_spy=True)
            on_result(i, result, row)

        return real(*a, on_result=hook, **k)

    monkeypatch.setattr(dev_module, "run_registry", run_registry)
    monkeypatch.setattr(store, "DSR_MIN", -1.0)


def _role_row(conn, n: int):
    return conn.execute("SELECT * FROM trial_roles WHERE trial_n = ?", (n,)).fetchone()


def test_a_method_whose_only_eligible_arm_is_its_control_is_rejected(seeded, data, monkeypatch):
    assert control_shape.role_of(CONTROL) == control_shape.ROLE_CONTROL      # the premise
    assert control_shape.role_of(IDEA) != control_shape.ROLE_CONTROL
    _force(monkeypatch, eligible={"M0001-B"})
    done = runner.run_method(seeded, _method(), HERE, data, git_sha="x", require_commit=False)
    by_id = {r.trial.candidate_id: r for r in done.ran}
    assert by_id["M0001-B"].trial.failed == store.CONTROL_LABEL
    assert by_id["M0001-B"].trial.eligible is False
    assert store.get_method(seeded, "M0001")["status"] == "rejected"
    rows = {r["candidate_id"]: r for r in store.trials_of(seeded, "M0001")}
    assert rows["M0001-B"]["eligible"] == 0 and rows["M0001-B"]["failed"] == store.CONTROL_LABEL
    for cid, role in (("M0001-A", control_shape.role_of(IDEA)), ("M0001-B", "control")):
        got = _role_row(seeded, rows[cid]["n"])
        assert (got["role"], got["source"], got["measured"]) == (role, "recorded",
                                                                 rows[cid]["run_at"])
    # ...and the verdict reads the record back the same way.
    assert store.verdict(seeded, rows["M0001-B"]).failed[-1] == store.CONTROL_LABEL


def test_a_method_with_an_eligible_non_control_arm_is_dev_eligible(seeded, data, monkeypatch):
    _force(monkeypatch, eligible={"M0001-A", "M0001-B"})
    done = runner.run_method(seeded, _method(), HERE, data, git_sha="x", require_commit=False)
    by_id = {r.trial.candidate_id: r for r in done.ran}
    assert by_id["M0001-A"].trial.eligible is True and by_id["M0001-A"].trial.failed == ""
    assert by_id["M0001-B"].trial.eligible is False
    assert store.get_method(seeded, "M0001")["status"] == "dev-eligible"


def test_an_amendment_records_its_arms_roles_and_moves_no_status(seeded, data, monkeypatch):
    _force(monkeypatch, eligible={"M0001-A", "M0001-C"})
    runner.run_method(seeded, _method(), HERE, data, git_sha="x", require_commit=False)
    amended = _method(amendments=(Amendment(
        added=date(2026, 10, 12), why="a later control", hypothesis="the idea beats its foil",
        expected_failure="the foil keeps up",
        candidates=(_cand("M0001-C", n=75, rationale=R_CONTROL),),
    ),))
    runner.run_method(seeded, amended, HERE, data, git_sha="y", require_commit=False, amend=True)
    c = store.trials_of(seeded, "M0001")[-1]
    assert c["candidate_id"] == "M0001-C" and c["failed"] == store.CONTROL_LABEL
    got = _role_row(seeded, c["n"])
    assert (got["role"], got["source"]) == ("control", "recorded")
    assert store.get_method(seeded, "M0001")["status"] == "dev-eligible"   # unchanged

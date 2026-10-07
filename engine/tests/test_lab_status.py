"""`lab status`'s promotion path, look budget and ratchet warning (lab-luck-gate phase 5).

Every test builds its own temp lab. The real one's state changes with every Sera batch and these
tests must keep passing through all of them -- so nothing here asserts a count the committed
database happens to have.

The recorded `failed` strings in these fixtures deliberately say "DSR >= 0.95", the text the 110
append-only rows carry, while `store.DSR_LABEL` now reads "DSR >= 0.90". That mismatch is the
hazard Decision D1 created and `_owner_misses` exists to handle.
"""

from __future__ import annotations

import argparse
import shutil

import pytest

from seer_engine.commands import lab as lab_cmd
from seer_engine.lab import store

OLD_LUCK_LABEL = "DSR >= 0.95"  # what the append-only rows say, forever


@pytest.fixture()
def status(capsys):
    def go(db) -> str:
        args = argparse.Namespace(db=db, lab_command="status")
        assert lab_cmd.run(args) == 0
        return capsys.readouterr().out

    return go


def _trial(**kw) -> store.TrialRow:
    base = dict(
        method_id="M0001", candidate_id="M0001-A", config_digest="d1", config_text="t",
        rules_id="MONTHLY_HOLD", allocator_id="TIMING", window="dev", start="1996-01-02",
        end="2015-10-16", store_fingerprint="399d0d25", git_sha="abc123",
        run_at="2026-10-06T00:00:00+00:00", total_return=3.0, cagr=0.12, max_drawdown=0.11,
        profit_factor=1.6, trades=250, sharpe=0.9, exposure=0.95, turnover=1.1, worst_year=2008,
        worst_year_return=-0.1, spy_tr_return=2.0, spy_tr_cagr=0.08, mar=0.8, failed="",
        eligible=True, dsr=0.97, n_trials_at_run=2, curve_json="[]",
    )
    base.update(kw)
    return store.TrialRow(**base)


# `n_trials_at_run=2` is load-bearing in this file, not arbitrary. Phase 4's `store.verdict`
# re-evaluates every recorded DSR **at the gate's current N**; these fixtures hold two dev trials,
# so the gate resolves to N = 2 under `all-trials` and the re-evaluation is the identity. Give a
# fixture a different N and its DSR moves under the assertions -- which is exactly the behaviour
# the gate is supposed to have, and exactly what makes a fixture that forgets it confusing.


def _method(c, mid: str, *, status: str, trials) -> None:
    """A method at ``status`` with ``trials`` recorded, walked along TRANSITIONS."""
    path = {
        "registered": ("registered",),
        "rejected": ("registered", "rejected"),
        "dev-eligible": ("registered", "dev-eligible"),
    }[status]
    with c:
        store.add_method(c, id=mid, name=f"name {mid}", family="fam",
                         source_kind="knowledge", hypothesis="h")
        store.insert_trials(c, list(trials))
        for s in path:
            store.update_method(c, mid, status=s)


# ------------------------------------------------------------------ the path prints when empty


def test_an_empty_promotion_path_still_prints_every_section(tmp_path, status):
    """R3 in one assertion: a lab in which `lab promote` and `lab test` are both unreachable
    says so, instead of printing nothing at all about the promotion path."""
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _method(c, "M0001", status="rejected", trials=[
        _trial(method_id="M0001", candidate_id="M0001-A", config_digest="a",
               failed=OLD_LUCK_LABEL, eligible=False, dsr=0.80),
        _trial(method_id="M0001", candidate_id="M0001-B", config_digest="b", sharpe=0.7,
               failed=f"max DD <= 15%; {OLD_LUCK_LABEL}", eligible=False, dsr=0.70),
    ])
    c.close()
    out = status(db)
    assert "Promotion path" in out
    for title in ("Dev-eligible", "Promoted (pre-registered)", "Test-passed", "Test-failed",
                  "Paper"):
        assert f"{title}: (none)" in out
    assert "Promotable now" in out
    assert "Test-window looks used: 0" in out
    assert "never given back" in out


def test_the_empty_dev_eligible_section_names_the_closest_candidate_and_the_bar(tmp_path, status):
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _method(c, "M0001", status="rejected", trials=[
        _trial(method_id="M0001", candidate_id="M0001-A", config_digest="a",
               failed=OLD_LUCK_LABEL, eligible=False, dsr=0.88),
        _trial(method_id="M0001", candidate_id="M0001-B", config_digest="b", sharpe=0.7, mar=0.7,
               failed=OLD_LUCK_LABEL, eligible=False, dsr=0.70),
    ])
    c.close()
    out = status(db)
    assert "held by the luck bar alone" in out
    assert "M0001-A" in out            # the closest, not the other one
    assert str(store.DSR_MIN) in out
    assert "lab luck" in out


def test_a_candidate_that_misses_an_owner_condition_is_named_as_unrescuable(tmp_path, status):
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _method(c, "M0001", status="rejected", trials=[
        _trial(method_id="M0001", candidate_id="M0001-A", config_digest="a",
               max_drawdown=0.31, failed=f"max DD <= 15%; {OLD_LUCK_LABEL}",
               eligible=False, dsr=0.99),
    ])
    c.close()
    out = status(db)
    assert "none passes the five go-live conditions" in out
    assert "max DD <= " in out
    assert "can rescue" in out


def test_a_historical_luck_label_is_not_read_as_an_owner_condition(tmp_path, status):
    """Decision D1's hazard: `store.DSR_LABEL` reads "DSR >= 0.90" while every recorded row says
    "DSR >= 0.95". A trial that missed only the old luck bar must still count as passing all five
    owner conditions, in the reason sentence and in the Closest-to-eligible table."""
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _method(c, "M0001", status="rejected", trials=[
        _trial(method_id="M0001", candidate_id="M0001-A", config_digest="a",
               failed=OLD_LUCK_LABEL, eligible=False, dsr=0.88),
        _trial(method_id="M0001", candidate_id="M0001-B", config_digest="b", sharpe=0.7, mar=0.7,
               failed=OLD_LUCK_LABEL, eligible=False, dsr=0.70),
    ])
    c.close()
    out = status(db)
    assert "held by the luck bar alone" in out
    assert "M0001-A" in out
    assert "misses 0" in out        # the Closest-to-eligible table agrees
    assert OLD_LUCK_LABEL not in out.split("Closest to eligible")[1].split("Promotion path")[0]


def test_an_empty_lab_says_nothing_has_run(tmp_path, status):
    db = tmp_path / "lab.sqlite"
    store.connect(db).close()
    out = status(db)
    assert "no method has run on the dev window yet" in out
    assert "Test-window looks used: 0" in out


# ------------------------------------------------------------------ promotable now


def test_promotable_now_lists_what_lab_promote_would_take(tmp_path, status):
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _method(c, "M0001", status="dev-eligible", trials=[
        _trial(method_id="M0001", candidate_id="M0001-A", config_digest="a", mar=0.9),
        _trial(method_id="M0001", candidate_id="M0001-B", config_digest="b", sharpe=0.7, mar=0.5),
    ])
    c.close()
    out = status(db)
    block = out.split("Promotable now")[1]
    assert "M0001-A" in block          # best by MAR, the one `lab promote` pre-registers
    assert "Dev-eligible (1)" in out


def test_a_derived_eligible_method_still_rejected_is_named_as_held(tmp_path, status):
    """`lab promote` refuses a rejected method however good its trial is, and the status says
    which command moves it rather than leaving the reader to guess."""
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _method(c, "M0001", status="rejected", trials=[
        _trial(method_id="M0001", candidate_id="M0001-A", config_digest="a", mar=0.9),
        _trial(method_id="M0001", candidate_id="M0001-B", config_digest="b", sharpe=0.7, mar=0.5),
    ])
    c.close()
    out = status(db)
    assert "held by the status machine" in out
    assert "'rejected'" in out
    assert "lab reevaluate M0001" in out   # the command that actually moves it, not `lab run`


# ------------------------------------------------------------------ D1b: the ratchet warning


def _near_the_bar(c) -> None:
    """A lab whose best luck-only candidate clears the bar by less than `_WARN_MARGIN`.

    Two trials so there is a Sharpe variance to deflate by, and `n_trials_at_run=2` so the gate's
    N is the trial's own N and `store.dsr_at` returns the recorded number unchanged -- the
    identity `recover_dsr` rests on. The warning then has a DSR of exactly `DSR_MIN + 0.01` to
    reason about, which is what makes these assertions deterministic.
    """
    _method(c, "M0001", status="dev-eligible", trials=[
        _trial(method_id="M0001", candidate_id="M0001-A", config_digest="a", sharpe=0.95,
               mar=0.9, failed="", eligible=True,
               dsr=store.DSR_MIN + 0.01, n_trials_at_run=2),
        _trial(method_id="M0001", candidate_id="M0001-B", config_digest="b", sharpe=0.40,
               mar=0.4, max_drawdown=0.31, failed=f"max DD <= 15%; {OLD_LUCK_LABEL}",
               eligible=False, dsr=0.55, n_trials_at_run=2),
    ])


def test_the_ratchet_warning_fires_and_names_the_n_that_sinks_the_candidate(tmp_path, status):
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _near_the_bar(c)
    c.close()
    out = status(db)
    assert "The luck bar is close" in out
    assert "M0001-A" in out
    assert "of margin" in out
    assert "falls below the bar at N =" in out
    assert "more dev trials" in out
    assert "lab luck" in out


def test_the_ratchet_warning_is_silent_when_the_margin_is_comfortable(tmp_path, status):
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _method(c, "M0001", status="dev-eligible", trials=[
        _trial(method_id="M0001", candidate_id="M0001-A", config_digest="a", sharpe=0.95,
               mar=0.9, failed="", eligible=True, dsr=0.999, n_trials_at_run=2),
        _trial(method_id="M0001", candidate_id="M0001-B", config_digest="b", sharpe=0.40,
               mar=0.4, max_drawdown=0.31, failed=f"max DD <= 15%; {OLD_LUCK_LABEL}",
               eligible=False, dsr=0.55, n_trials_at_run=2),
    ])
    c.close()
    assert "The luck bar is close" not in status(db)


def test_the_ratchet_warning_is_silent_when_nothing_is_above_the_bar(tmp_path, status):
    """Below the bar, the empty Dev-eligible section is already the sentence; a second one would
    be noise."""
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _method(c, "M0001", status="rejected", trials=[
        _trial(method_id="M0001", candidate_id="M0001-A", config_digest="a", sharpe=0.95,
               mar=0.9, failed=OLD_LUCK_LABEL, eligible=False, dsr=0.70, n_trials_at_run=2),
        _trial(method_id="M0001", candidate_id="M0001-B", config_digest="b", sharpe=0.40,
               mar=0.4, max_drawdown=0.31, failed=f"max DD <= 15%; {OLD_LUCK_LABEL}",
               eligible=False, dsr=0.55, n_trials_at_run=2),
    ])
    c.close()
    out = status(db)
    assert "The luck bar is close" not in out
    assert "held by the luck bar alone" in out


def test_sinks_at_finds_the_first_n_below_the_bar(tmp_path):
    """The bisection, directly: the N it returns is below the bar and the one before it is not."""
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _near_the_bar(c)
    found = lab_cmd._best_luck_only(c)
    assert found is not None
    trial, v = found
    var = lab_cmd._dev_var(c)
    n = lab_cmd._sinks_at(c, trial, v, var)
    c.close()
    assert n is not None and n > int(v.n)
    common = dict(sharpe_daily=float(trial["sharpe"]) / (252 ** 0.5),
                  dsr_at_run=float(v.dsr), n_at_run=int(v.n), var_trials=var)
    assert lab_cmd.recover_dsr(n_trials=n, **common) < store.DSR_MIN
    assert lab_cmd.recover_dsr(n_trials=n - 1, **common) >= store.DSR_MIN


# ------------------------------------------------------------------ the committed database


@pytest.mark.skipif(not store.COMMITTED_DB.is_file(), reason="no committed lab database here")
def test_status_runs_on_a_copy_of_the_committed_database(tmp_path, status):
    """The real shape, on the real data, without touching the committed file."""
    db = tmp_path / "lab.sqlite"
    shutil.copy(store.COMMITTED_DB, db)
    c = store.connect(db)
    looks = store.test_looks(c)
    c.close()
    out = status(db)
    assert "Promotion path" in out
    assert f"Test-window looks used: {looks}" in out

"""Pre-registration (method lab design §3): `lab promote`, docs/lab/prereg/ and the gate.

Every test builds its own temp lab database. The real one has no dev-eligible method, and these
tests must keep passing on the day it does.
"""

from __future__ import annotations

import argparse
import re
import subprocess
from datetime import date, timedelta
from pathlib import Path

import pytest

from seer_engine import dates
from seer_engine.backtest import dev
from seer_engine.lab import prereg, store
from seer_engine.lab.method import config_digest, discover, source_sha


@pytest.fixture(autouse=True)
def _at_the_policy_these_fixtures_were_recorded_under(monkeypatch):
    """Judge every lab in this module under ``all-trials``, the policy its rows were stamped with.

    Not a convenience and not a workaround for the shipped policy: it is the one assumption these
    fixtures already encode. Every trial they insert carries ``n_trials_at_run`` equal to the
    fixture's dev row count, which is what a lab recorded under ``all-trials`` looks like and
    nothing else. ``store.verdict`` re-evaluates a recorded DSR **at the gate's current N**, so
    the re-evaluation is the identity -- and an eligibility assertion means what it says -- only
    while the gate resolves to the N stamped on the rows. Judging a recorded lab under the policy
    it was recorded under is the condition, and naming it here is strictly more honest than
    inheriting it from whatever ``store.DSR_POLICY`` happens to be.

    Since 2026-10-08 it no longer is: ``DSR_POLICY`` is ``methods`` (lab-realistic-gate R1), which
    on a one-method lab resolves to ``max(1, ceil(participation ratio))`` -- 1 when the fixtures
    record no curves -- and ``dev.deflated_sharpe`` is undefined below two looks. Every derived
    verdict here would then collapse to "no evaluable luck test" for a reason that has nothing to
    do with this module's subject. What the shipped policy resolves to is pinned where it belongs,
    in ``test_lab_gate_policy.py`` and ``test_lab_npolicy.py``.

    Autouse rather than folded into a connection fixture, because the paths under test resolve the
    gate themselves -- ``prereg.promote_method`` and the ``lab promote`` CLI both call
    ``store.best_dev_eligible`` with no ``at=``, and several tests here open their own database.
    """
    monkeypatch.setattr(store, "DSR_POLICY", "all-trials")
    store._GATE_CACHE.clear()
    yield
    store._GATE_CACHE.clear()


@pytest.fixture()
def conn(tmp_path):
    c = store.connect(tmp_path / "lab.sqlite")
    yield c
    c.close()


@pytest.fixture()
def prereg_dir(tmp_path):
    """Where a test's pre-registrations go.

    Its own directory, not `tmp_path`: the `conn` fixture puts `lab.sqlite` in `tmp_path`, and
    several tests below assert that *nothing* was written, which has to mean nothing.
    It is deliberately not created -- `promote_method` creating it is part of what is tested.
    """
    return tmp_path / "prereg"


def _trial(**kw) -> store.TrialRow:
    base = dict(
        method_id="M0001", candidate_id="M0001-A", config_digest="d1", config_text="t",
        rules_id="MONTHLY_HOLD", allocator_id="TIMING", window="dev", start="1996-01-02",
        end="2015-10-16", store_fingerprint="399d0d25", git_sha="abc123",
        run_at="2026-10-06T00:00:00+00:00", total_return=3.0, cagr=0.12, max_drawdown=0.11,
        profit_factor=1.6, trades=250, sharpe=0.9, exposure=0.95, turnover=1.1, worst_year=2008,
        worst_year_return=-0.1, spy_tr_return=2.0, spy_tr_cagr=0.08, mar=0.8, failed="",
        eligible=True, dsr=0.97, n_trials_at_run=60, curve_json="[]",
    )
    base.update(kw)
    return store.TrialRow(**base)


def _ballast(mid: str = "M0001", **kw) -> store.TrialRow:
    """A second dev trial, so the fixture lab has a trial-Sharpe variance to deflate by.

    Since LAB_LUCK_GATE_PLAN.md phase 4 a trial's eligibility is *derived* at read time, and the
    luck half of it is ``store.dsr_at``, which deflates by ``store.dev_sharpe_variance`` -- the
    sample variance of the dev trials' daily Sharpes. A lab holding one dev trial has no such
    variance, so no DSR is evaluable and nothing is eligible. That is not a quirk of the derived
    verdict: ``runner.trial_rows`` has always recorded ``dsr = None`` for the first trial in a
    lab, for the same reason and in the same words.

    So a fixture that wants a *promotable* method has to look like a lab that could have one:
    at least two dev trials, with different Sharpes. This row is that second trial. It is
    deliberately ineligible on a 24.5% drawdown -- outside even the owner's new 20% bar -- and
    carries the lowest MAR, so it never wins ``best_dev_eligible`` and never changes an answer.
    """
    base = dict(
        method_id=mid, candidate_id=f"{mid}-BALLAST", config_digest=f"ballast-{mid}",
        sharpe=1.4, max_drawdown=0.245, mar=0.05, eligible=False,
        failed="max DD <= 15%; DSR >= 0.95",
    )
    base.update(kw)
    return _trial(**base)


_PATH_TO: dict[str, tuple[str, ...]] = {
    "idea": (),
    "registered": ("registered",),
    "rejected": ("registered", "rejected"),
    "blocked-data": ("blocked-data",),
}


def _at_status(conn, status: str, mid: str = "M0001") -> None:
    with conn:
        store.add_method(conn, id=mid, name="n", family="f", source_kind="knowledge",
                         hypothesis="h")
        for s in _PATH_TO[status]:
            store.update_method(conn, mid, status=s)


def _eligible(conn, mid: str = "M0001", trials=None) -> None:
    """A method at `dev-eligible` with trials recorded, the way `lab run` leaves one."""
    with conn:
        store.add_method(conn, id=mid, name="SMA test", family="trend",
                         source_kind="knowledge", hypothesis="h", status="registered")
        rows = list(trials if trials is not None else [_trial()])
        store.insert_trials(conn, [*rows, _ballast(mid)])
        store.update_method(conn, mid, status="dev-eligible")


def _months(start: date, end: date) -> list[date]:
    """Month-end dates in ``[start, end]`` -- the shape a recorded ``trials.curve_json`` has."""
    out, d = [], date(start.year, start.month, 1)
    while True:
        nxt = date(d.year + (d.month == 12), (d.month % 12) + 1, 1)
        last = nxt - timedelta(days=1)
        if last > end:
            return out
        if last >= start:
            out.append(last)
        d = nxt


def _curve(months: list[date], annual: float) -> str:
    """A ``curve_json`` compounding at ``annual`` from 1.0, one point per month end."""
    import json

    out, v = [], 1.0
    for d in months:
        out.append([d.isoformat(), round(v, 8)])
        v *= (1.0 + annual) ** (1.0 / 12.0)
    return json.dumps(out)


def _benchmark(conn) -> None:
    """The lab's recorded SPY buy-and-hold dev trial (``regime.BENCH_CANDIDATE``).

    Since the hard gate (`lab/hardgate.py`) a lab with no ``REF-SPY-HOLD`` dev trial can promote
    nothing: there is no benchmark to cut folds from, so no fold can be scored, and the gate
    fails closed rather than waving a method through. A fixture that wants a *promotable* method
    therefore has to look like a lab that could have one -- the same reason `_ballast` exists one
    gate earlier. Its span matches the real row's, 1993-02-01..2015-10-16, which is what yields
    the four folds the gate requires.

    Its own family and its own method id, so it is never kin to the method under test.
    """
    store.add_method(conn, id="H-P7A-REF", name="SPY buy and hold", family="reference",
                     source_kind="seed", hypothesis="h", status="registered")
    store.insert_trials(conn, [_trial(
        method_id="H-P7A-REF", candidate_id="REF-SPY-HOLD", config_digest="ref-spy-hold",
        start="1993-02-01", end="2015-10-16",
        curve_json=_curve(_months(date(1993, 2, 1), date(2015, 10, 16)), 0.08),
    )])


def _real_method(conn, mid: str = "M0001"):
    """What `lab run` would have left behind for the committed `mNNNN_*.py` file `mid`.

    The real file is used so `check_source` has something true to check: the trial's digest is
    the file's own `config_digest` and `source_sha` is the file's sha256.

    Its trial carries a real curve, and the lab carries a benchmark, because `lab promote` now
    runs the hard gate before `prereg.promote_method`: a method with no curve is scoreable on no
    fold and is refused. The curve compounds at 15% a year against the benchmark's 8%, so the
    method wins all four folds -- which is what the brief means by "a method winning a majority
    with a clean family promotes".
    """
    method, path = discover()[mid]
    c = method.candidates[0]
    with conn:
        _benchmark(conn)
        store.add_method(conn, id=mid, name=method.name, family=method.family,
                         source_kind=method.source_kind, source_ref=method.source_ref,
                         hypothesis="h", status="registered")
        store.insert_trials(conn, [
            _trial(method_id=mid, candidate_id=c.id, config_digest=config_digest(c),
                   rules_id=c.rules.id, allocator_id=str(c.allocator.id),
                   curve_json=_curve(_months(date(1996, 1, 2), date(2015, 10, 16)), 0.15)),
            _ballast(mid),
        ])
        store.update_method(conn, mid, source_sha=source_sha(path), status="dev-eligible")
    return c, path


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=seer-test", "-c", "user.email=seer-test@example.invalid",
         "-c", "commit.gpgsign=false", *args],
        cwd=cwd, check=True, capture_output=True,
    )


def _repo(tmp_path: Path) -> Path:
    """A git repo with an empty docs/lab/prereg/; returns that directory."""
    repo = tmp_path / "repo"
    directory = repo / "docs" / "lab" / "prereg"
    directory.mkdir(parents=True)
    _git(repo, "init", "-q")
    return directory


# ------------------------------------------------------------------ choosing the variant


def test_promote_pre_registers_the_best_eligible_variant_by_mar(conn, prereg_dir):
    _eligible(conn, trials=[
        _trial(candidate_id="M0001-A", config_digest="da", mar=0.60),
        _trial(candidate_id="M0001-B", config_digest="db", mar=0.90),
        # Ineligible on its NUMBERS, not on its recorded string: since phase 4 the four
        # threshold conditions are re-derived from the columns, so a 24.5% drawdown is what
        # keeps the top-MAR variant out. (At the fixture's old 0.11 it would now qualify.)
        _trial(candidate_id="M0001-C", config_digest="dc", mar=1.50, max_drawdown=0.245,
               eligible=False, failed="max DD <= 15%"),
    ])
    done = prereg.promote_method(conn, "M0001", git_sha="deadbeef", today=date(2026, 10, 6),
                                 directory=prereg_dir, check_method_file=False)
    assert done.prereg.candidate == "M0001-B"
    assert done.prereg.config_digest == "db"
    assert done.path == prereg_dir / "M0001.md"
    assert done.prereg.date == "2026-10-06"
    assert store.get_method(conn, "M0001")["status"] == "promoted"


def test_the_pre_registered_digest_is_the_recorded_dev_trials_digest(conn, prereg_dir):
    """The property this whole phase exists for.

    Not "a digest is present": the digest in the written file is byte-equal to the `trials`
    row's digest for that candidate, and equal to no other trial's, so the one look cannot be
    spent on a sibling that happens to look better.
    """
    _eligible(conn, trials=[
        _trial(candidate_id="M0001-A", config_digest="a" * 64, mar=0.60),
        _trial(candidate_id="M0001-B", config_digest="b" * 64, mar=0.90),
        # Ineligible on its NUMBERS (see above): a profit factor under the live
        # tuning.MIN_PROFIT_FACTOR, not merely a recorded "PF >= 1.3" label.
        _trial(candidate_id="M0001-C", config_digest="c" * 64, mar=1.50, profit_factor=1.1,
               eligible=False, failed="PF >= 1.3"),
    ])
    prereg.promote_method(conn, "M0001", git_sha="deadbeef", directory=prereg_dir,
                          check_method_file=False)
    p = prereg.parse((prereg_dir / "M0001.md").read_text(encoding="utf-8"))
    row = conn.execute(
        "SELECT * FROM trials WHERE candidate_id = ? AND window = 'dev'", (p.candidate,)
    ).fetchone()
    assert p.config_digest == row["config_digest"]
    assert p.dev_trial == str(row["n"])
    assert p.dev_window == f"{row['start']}..{row['end']}"
    assert p.n_trials_at_run == str(row["n_trials_at_run"])
    assert p.store_fingerprint == row["store_fingerprint"]
    others = [r["config_digest"] for r in store.trials_of(conn, "M0001")
              if r["candidate_id"] != p.candidate]
    assert others and p.config_digest not in others


def test_the_digest_is_checked_against_the_live_method_file(conn, prereg_dir):
    c, _ = _real_method(conn)
    done = prereg.promote_method(conn, "M0001", git_sha="deadbeef", directory=prereg_dir)
    assert done.prereg.candidate == c.id
    assert done.prereg.config_digest == config_digest(c)


def test_promote_refuses_a_method_file_that_changed_since_it_ran(conn, prereg_dir):
    """`source_sha` is written wrong from the start, never re-written.

    `methods_source_sha_once` (store.py:208) fires on any change once the column is non-NULL --
    NULL included -- so a test cannot set it and then correct it. It sets the sha of a file that
    is not this one, which is exactly the state a post-run edit would leave behind.
    """
    method, path = discover()["M0001"]
    c = method.candidates[0]
    with conn:
        store.add_method(conn, id="M0001", name=method.name, family=method.family,
                         source_kind=method.source_kind, source_ref=method.source_ref,
                         hypothesis="h", status="registered")
        store.insert_trials(conn, [
            _trial(candidate_id=c.id, config_digest=config_digest(c)), _ballast(),
        ])
        store.update_method(conn, "M0001", source_sha="0" * 64, status="dev-eligible")
    with pytest.raises(prereg.PreregError, match="has changed since"):
        prereg.promote_method(conn, "M0001", git_sha="deadbeef", directory=prereg_dir)
    assert not prereg_dir.exists()
    assert store.get_method(conn, "M0001")["status"] == "dev-eligible"


def test_promote_refuses_a_variant_whose_configuration_drifted(conn, prereg_dir):
    method, path = discover()["M0001"]
    c = method.candidates[0]
    with conn:
        store.add_method(conn, id="M0001", name=method.name, family=method.family,
                         source_kind=method.source_kind, source_ref=method.source_ref,
                         hypothesis="h", status="registered")
        store.insert_trials(conn, [
            _trial(candidate_id=c.id, config_digest="stale"), _ballast(),
        ])
        store.update_method(conn, "M0001", source_sha=source_sha(path), status="dev-eligible")
    with pytest.raises(prereg.PreregError, match="now digests to"):
        prereg.promote_method(conn, "M0001", git_sha="deadbeef", directory=prereg_dir)
    assert not prereg_dir.exists()


# ------------------------------------------------------------------ refusals


@pytest.mark.parametrize("status", sorted(_PATH_TO))
def test_promote_refuses_a_method_that_is_not_dev_eligible(conn, prereg_dir, status):
    _at_status(conn, status)
    with pytest.raises(prereg.PreregError, match="only a dev-eligible method"):
        prereg.promote_method(conn, "M0001", git_sha="x", directory=prereg_dir,
                              check_method_file=False)
    assert not prereg_dir.exists()
    assert store.get_method(conn, "M0001")["status"] == status


def test_promote_refuses_an_unknown_method(conn, prereg_dir):
    with pytest.raises(prereg.PreregError, match="no method M0099"):
        prereg.promote_method(conn, "M0099", git_sha="x", directory=prereg_dir,
                              check_method_file=False)
    assert not prereg_dir.exists()


def test_promote_refuses_a_dev_eligible_method_with_no_eligible_trial(conn, prereg_dir):
    # The miss has to be in the numbers: `failed` is append-only history, and phase 4 re-derives
    # the four threshold conditions from the columns against the live constants.
    _eligible(conn, trials=[_trial(profit_factor=1.1, eligible=False, failed="PF >= 1.3")])
    with pytest.raises(prereg.PreregError, match="nothing to pre-register"):
        prereg.promote_method(conn, "M0001", git_sha="x", directory=prereg_dir,
                              check_method_file=False)
    assert not prereg_dir.exists()


# ------------------------------------------------------------------ idempotence


def test_promote_is_idempotent_and_does_not_move_the_date(conn, prereg_dir):
    _eligible(conn)
    first = prereg.promote_method(conn, "M0001", git_sha="deadbeef", today=date(2026, 10, 6),
                                  directory=prereg_dir, check_method_file=False)
    assert first.wrote_file and first.moved_status
    text = (prereg_dir / "M0001.md").read_text(encoding="utf-8")

    second = prereg.promote_method(conn, "M0001", git_sha="cafe", today=date(2026, 12, 25),
                                   directory=prereg_dir, check_method_file=False)
    assert not second.wrote_file and not second.moved_status
    assert second.status == "promoted"
    assert second.prereg == first.prereg
    assert (prereg_dir / "M0001.md").read_text(encoding="utf-8") == text
    assert sorted(p.name for p in prereg_dir.iterdir()) == ["M0001.md"]
    assert store.get_method(conn, "M0001")["status"] == "promoted"
    assert store.get_method(conn, "M0001")["analysis"].count(prereg.MARKER) == 1
    assert conn.execute("SELECT count(*) FROM insights").fetchone()[0] == 1


def test_promote_rewrites_a_pre_registration_that_went_missing(conn, prereg_dir):
    _eligible(conn)
    prereg.promote_method(conn, "M0001", git_sha="deadbeef", directory=prereg_dir,
                          check_method_file=False)
    (prereg_dir / "M0001.md").unlink()
    done = prereg.promote_method(conn, "M0001", git_sha="deadbeef", directory=prereg_dir,
                                 check_method_file=False)
    assert done.wrote_file and not done.moved_status
    assert (prereg_dir / "M0001.md").is_file()
    assert store.get_method(conn, "M0001")["analysis"].count(prereg.MARKER) == 1
    assert conn.execute("SELECT count(*) FROM insights").fetchone()[0] == 1


def test_a_pre_registration_is_never_rewritten_for_a_better_variant(conn, prereg_dir):
    _eligible(conn, trials=[_trial(candidate_id="M0001-A", config_digest="da", mar=0.60)])
    prereg.promote_method(conn, "M0001", git_sha="x", directory=prereg_dir,
                          check_method_file=False)
    with conn:
        store.insert_trials(conn, [_trial(candidate_id="M0001-B", config_digest="db", mar=0.99)])
    with pytest.raises(prereg.PreregError, match="already pre-registers M0001-A"):
        prereg.promote_method(conn, "M0001", git_sha="x", directory=prereg_dir,
                              check_method_file=False)
    p = prereg.parse((prereg_dir / "M0001.md").read_text(encoding="utf-8"))
    assert p.candidate == "M0001-A" and p.config_digest == "da"


def test_a_lost_file_is_not_an_opening_to_pre_register_a_different_variant(conn, prereg_dir):
    """The analysis remembers the choice even when the file does not."""
    _eligible(conn, trials=[_trial(candidate_id="M0001-A", config_digest="da", mar=0.60)])
    prereg.promote_method(conn, "M0001", git_sha="x", directory=prereg_dir,
                          check_method_file=False)
    (prereg_dir / "M0001.md").unlink()
    with conn:
        store.insert_trials(conn, [_trial(candidate_id="M0001-B", config_digest="db", mar=0.99)])
    with pytest.raises(prereg.PreregError, match="already pre-registers M0001-A"):
        prereg.promote_method(conn, "M0001", git_sha="x", directory=prereg_dir,
                              check_method_file=False)
    assert not (prereg_dir / "M0001.md").exists()


# ------------------------------------------------------------------ it spends nothing


def test_promote_writes_no_trial_and_spends_no_look(conn, prereg_dir):
    _eligible(conn)
    before = store.dev_trial_count(conn)
    prereg.promote_method(conn, "M0001", git_sha="x", directory=prereg_dir,
                          check_method_file=False)
    assert store.dev_trial_count(conn) == before
    assert store.test_looks(conn) == 0


# ------------------------------------------------------------------ the gate phase 4 calls


def test_require_committed_refuses_a_missing_pre_registration(tmp_path):
    with pytest.raises(prereg.PreregError, match="does not exist"):
        prereg.require_committed("M0007-V2", directory=tmp_path)


def test_require_committed_wants_a_candidate_id_not_a_method_id(tmp_path):
    for bad in ("M0001", "M0001-", "momentum-A", "H-A"):
        with pytest.raises(prereg.PreregError, match="not a lab candidate id"):
            prereg.require_committed(bad, directory=tmp_path)


def test_require_committed_refuses_until_the_file_is_committed(conn, tmp_path):
    directory = _repo(tmp_path)
    _eligible(conn)
    prereg.promote_method(conn, "M0001", git_sha="x", directory=directory,
                          check_method_file=False)
    with pytest.raises(prereg.PreregError, match="uncommitted"):
        prereg.require_committed("M0001-A", directory=directory)  # untracked
    _git(directory, "add", "M0001.md")
    with pytest.raises(prereg.PreregError, match="uncommitted"):
        prereg.require_committed("M0001-A", directory=directory)  # staged is not committed
    _git(directory, "commit", "-q", "-m", "prereg")
    p = prereg.require_committed("M0001-A", directory=directory)
    assert p.candidate == "M0001-A" and p.config_digest == "d1"
    (directory / "M0001.md").write_text("---\n", encoding="utf-8")
    with pytest.raises(prereg.PreregError, match="uncommitted"):
        prereg.require_committed("M0001-A", directory=directory)  # modified after the commit


def test_require_committed_refuses_a_file_naming_another_candidate(conn, tmp_path):
    directory = _repo(tmp_path)
    _eligible(conn)
    prereg.promote_method(conn, "M0001", git_sha="x", directory=directory,
                          check_method_file=False)
    _git(directory, "add", "M0001.md")
    _git(directory, "commit", "-q", "-m", "prereg")
    with pytest.raises(prereg.PreregError, match="pre-registers M0001-A, not M0001-Z"):
        prereg.require_committed("M0001-Z", directory=directory)


def test_check_digest_matches_only_the_pre_registered_configuration(conn, prereg_dir):
    _eligible(conn)
    done = prereg.promote_method(conn, "M0001", git_sha="x", directory=prereg_dir,
                                 check_method_file=False)
    prereg.check_digest(done.prereg, "d1", directory=prereg_dir)  # no raise
    with pytest.raises(prereg.PreregError, match="pre-registered d1"):
        prereg.check_digest(done.prereg, "d2", directory=prereg_dir)


# ------------------------------------------------------------------ the format itself


def test_parse_round_trips_render(conn, prereg_dir):
    _eligible(conn)
    done = prereg.promote_method(conn, "M0001", git_sha="x", directory=prereg_dir,
                                 check_method_file=False)
    assert prereg.parse(prereg.render(done.prereg, "SMA test")) == done.prereg
    assert prereg.parse((prereg_dir / "M0001.md").read_text(encoding="utf-8")) == done.prereg


@pytest.mark.parametrize("text, message", [
    ("no front matter\n", "starts with"),
    ("---\nmethod: M0001\n", "is not closed"),
    ("---\nmethod: M0001\n---\n", "missing candidate"),
    ("---\nmethod M0001\n---\n", "not `key: value`"),
])
def test_parse_refuses_a_malformed_pre_registration(text, message):
    with pytest.raises(prereg.PreregError, match=re.escape(message)):
        prereg.parse(text)


def test_parse_refuses_an_unknown_or_repeated_field():
    good = "\n".join(f"{k}: x" for k in prereg.FIELDS)
    with pytest.raises(prereg.PreregError, match="unknown pre-registration field 'digest'"):
        prereg.parse(f"{prereg.FENCE}\n{good}\ndigest: x\n{prereg.FENCE}\n")
    with pytest.raises(prereg.PreregError, match="appears twice"):
        prereg.parse(f"{prereg.FENCE}\n{good}\nmethod: y\n{prereg.FENCE}\n")


def test_the_recorded_gate_names_every_condition_the_lab_applies(tmp_path):
    """The gate line is built from the engine's own labels, so it cannot drift from the code.

    Two forms. Without a connection it names the five conditions, the threshold and the policy.
    With one it also carries the N that policy resolved to and the evidence for it, which is what
    ``promote_method`` writes into the committed file.
    """
    text = prereg.gate_text()
    for label in dev.FAILURE_LABELS:
        assert label in text
    assert f"{store.DSR_MIN:.2f}" in text  # the bar the owner set (design §7.1)
    assert store.DSR_POLICY in text  # the policy that chooses N (design §7.2)

    conn = store.connect(tmp_path / "lab.sqlite")
    try:
        resolved = prereg.gate_text(conn)
    finally:
        conn.close()
    assert resolved.startswith(text)  # the conn form only appends
    assert "N = " in resolved
    assert "\n" not in resolved  # one `key: value` line in the committed file


def test_the_recorded_test_window_starts_the_session_after_dev_end():
    label = prereg.test_window_label()
    assert label == f"{dates.next_session(dev.DEV_END).isoformat()}..data end"
    assert label.startswith("2015-10-19")


# ------------------------------------------------------------------ the CLI


def test_lab_promote_command_writes_the_file_and_names_the_next_step(
    tmp_path, prereg_dir, capsys, monkeypatch
):
    from seer_engine.commands import lab as lab_cmd
    from seer_engine.lab import runner

    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    candidate, _ = _real_method(c)
    c.close()
    # `_promote` imports git_head inside the function, so the attribute is read at call time.
    monkeypatch.setattr(runner, "git_head", lambda cwd: "deadbeef")
    args = argparse.Namespace(db=db, lab_command="promote", method="M0001", dir=prereg_dir)
    assert lab_cmd.run(args) == 0
    out = capsys.readouterr().out
    assert candidate.id in out
    assert f"lab test {candidate.id}" in out
    assert "test-window looks used: 0" in out
    written = prereg_dir / "M0001.md"
    assert written.is_file()
    assert prereg.parse(written.read_text(encoding="utf-8")).candidate == candidate.id


def test_lab_promote_command_exits_2_when_the_lab_refuses(tmp_path, prereg_dir):
    from seer_engine.commands import lab as lab_cmd

    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _at_status(c, "registered")
    c.close()
    args = argparse.Namespace(db=db, lab_command="promote", method="M0001", dir=prereg_dir)
    assert lab_cmd.run(args) == 2
    assert not prereg_dir.exists()


# ------------------------------------------------------------------ the hard gate's two fields


def _block(**over) -> str:
    """A front-matter block carrying only the fifteen fields that predate the hard gate.

    This is the shape of the four files committed under docs/lab/prereg/ before the gate existed,
    rebuilt from `prereg.REQUIRED` rather than retyped so it cannot drift from the parser.
    """
    values = {k: f"<{k}>" for k in prereg.REQUIRED}
    values.update(over)
    body = "\n".join(f"{k}: {v}" for k, v in values.items())
    return f"{prereg.FENCE}\n{body}\n{prereg.FENCE}\n\n# prose\n"


def test_the_two_new_fields_are_written_and_round_trip(conn, prereg_dir):
    _eligible(conn)
    done = prereg.promote_method(conn, "M0001", git_sha="x", directory=prereg_dir,
                                 check_method_file=False)
    p = done.prereg
    assert p.folds and p.family_state
    assert "\n" not in p.folds and "\n" not in p.family_state  # one `key: value` line each
    text = (prereg_dir / "M0001.md").read_text(encoding="utf-8")
    assert f"folds: {p.folds}" in text
    assert f"family_state: {p.family_state}" in text
    assert prereg.parse(text) == p
    assert prereg.parse(prereg.render(p, "SMA test")) == p


def test_a_file_written_before_the_gate_still_parses_and_says_so(conn):
    """Decision D5: the four committed records are never migrated, so `parse` tolerates absence."""
    p = prereg.parse(_block(method="M0001", candidate="M0001-A"))
    assert p.method == "M0001"
    assert p.folds == prereg.LEGACY
    assert p.family_state == prereg.LEGACY


def test_a_legacy_file_read_back_and_re_rendered_round_trips_exactly(conn):
    p = prereg.parse(_block(method="M0001", candidate="M0001-A"))
    assert prereg.parse(prereg.render(p, "SMA test")) == p


def test_parse_still_refuses_a_file_missing_any_of_the_original_fifteen():
    for key in prereg.REQUIRED:
        if key == "method":
            continue  # the first line is what `_block` keys off; its absence is covered at :442
        text = "\n".join(
            line for line in _block().split("\n") if not line.startswith(f"{key}:")
        )
        with pytest.raises(prereg.PreregError, match=f"missing .*{key}"):
            prereg.parse(text)


def test_the_four_committed_pre_registrations_still_parse(conn):
    """The reason this module exists: a committed record stays readable forever.

    Not a fixture -- the real files in docs/lab/prereg/, which this phase must not edit. All four
    predate the hard gate, so all four report both new fields as not recorded.
    """
    files = sorted(prereg.PREREG_DIR.glob("M[0-9][0-9][0-9][0-9].md"))
    assert [f.stem for f in files] == ["M0002", "M0021", "M0022", "M0029"]
    for path in files:
        p = prereg.parse(path.read_text(encoding="utf-8"))
        assert p.method == path.stem
        assert p.folds == prereg.LEGACY
        assert p.family_state == prereg.LEGACY
        assert prereg.parse(prereg.render(p, "n")) == p


def test_the_fold_line_names_the_folds_won_the_folds_scored_and_the_stability(conn, monkeypatch):
    """R6's three facts, each present as a word rather than by absence."""
    from seer_engine.lab import hardgate, walkforward as wf

    def record(_conn, mid):
        fold = wf.Fold(1, date(2006, 1, 1), date(2006, 1, 31), date(2008, 12, 31))
        won = wf.Slice(36, 1.0, 0.2, 0.1, 2.0)
        lost = wf.Slice(36, 0.1, 0.03, 0.1, 0.3)
        return wf.Record(mid, (
            wf.FoldPick(fold, "M0001-A", 1.0, won, lost),
            wf.FoldPick(fold, "M0001-A", 1.0, won, lost),
            wf.FoldPick(fold, "M0001-A", 1.0, lost, won),
            wf.FoldPick(fold, "M0001-B", 1.0, won, lost),
        ))

    monkeypatch.setattr(hardgate, "fold_record", record)
    line = prereg.fold_text(conn, "M0001")
    assert line.startswith("3 of 4 ")
    assert "pick changed across folds" in line
    assert str(hardgate.MIN_FOLDS) in line
    assert "\n" not in line


def test_the_family_line_names_every_failed_relative(conn, monkeypatch):
    from seer_engine.lab import hardgate

    monkeypatch.setattr(hardgate, "failed_kin", lambda _c, _m: ("M0021", "M0029"))
    blocked = prereg.family_text(conn, "M0030", "stock-core-satellite")
    assert "blocked at promotion" in blocked
    assert "M0021" in blocked and "M0029" in blocked  # D4's live case has two, not one
    assert "stock-core-satellite" in blocked

    monkeypatch.setattr(hardgate, "failed_kin", lambda _c, _m: ())
    clean = prereg.family_text(conn, "M0030", "stock-core-satellite")
    assert "clean at promotion" in clean
    assert "test-failed" in clean


def test_a_gate_that_cannot_answer_is_recorded_rather_than_invented(conn, prereg_dir, monkeypatch):
    """The refusal belongs to `_promote` (Decision D1); this step records, and never raises.

    A fixture lab has no REF-SPY-HOLD curve, which is exactly the shape of the real refusal, so
    this also pins that a caller which reaches `promote_method` past the gate still writes a
    readable file -- and that the 31 pre-existing tests in this file keep passing either way.
    """
    from seer_engine.lab import hardgate

    def boom(_conn, _mid):
        raise store.LabError("no REF-SPY-HOLD dev trial")

    monkeypatch.setattr(hardgate, "fold_record", boom)
    _eligible(conn)
    done = prereg.promote_method(conn, "M0001", git_sha="x", directory=prereg_dir,
                                 check_method_file=False)
    assert done.prereg.folds.startswith("not recorded")
    assert "REF-SPY-HOLD" in done.prereg.folds
    assert "\n" not in done.prereg.folds
    assert prereg.parse((prereg_dir / "M0001.md").read_text(encoding="utf-8")) == done.prereg


def test_one_line_collapses_anything_a_refusal_message_can_carry():
    assert prereg.one_line("a\nb") == "a b"
    assert prereg.one_line("  a \n\n  b  ") == "a b"
    assert prereg.one_line("a") == "a"


def test_the_prose_says_the_family_state_is_not_rechecked_at_lab_test(conn, prereg_dir):
    """Decision D3, stated to the file's reader and not only in a plan."""
    _eligible(conn)
    done = prereg.promote_method(conn, "M0001", git_sha="x", directory=prereg_dir,
                                 check_method_file=False)
    text = (prereg_dir / "M0001.md").read_text(encoding="utf-8")
    assert "state **at promotion**" in text
    assert "`lab test` does not re-check it" in text
    assert "never a significance test" in text


def test_the_promote_command_prints_the_fold_record_and_the_family_state(
    tmp_path, prereg_dir, capsys, monkeypatch
):
    """The two lines phase 2 adds to `_promote`'s block, and nothing else in that file.

    `hardgate.check` is stubbed out so this test pins *these two printed lines* rather than phase
    1's refusal, which has its own tests in test_lab_hardgate.py.
    """
    from seer_engine.commands import lab as lab_cmd
    from seer_engine.lab import hardgate, runner

    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _real_method(c)
    c.close()
    monkeypatch.setattr(runner, "git_head", lambda cwd: "deadbeef")
    monkeypatch.setattr(hardgate, "check", lambda _conn, _mid: None)
    args = argparse.Namespace(db=db, lab_command="promote", method="M0001", dir=prereg_dir)
    assert lab_cmd.run(args) == 0
    out = capsys.readouterr().out
    p = prereg.parse((prereg_dir / "M0001.md").read_text(encoding="utf-8"))
    assert f"  folds          {p.folds}" in out
    assert f"  family         {p.family_state}" in out

"""``lab remeasure H-P7A`` (plan phase 9): the P7a seed's DSR inputs, recovered and luck-tested.

The 54 seed trials are real: ``seed(conn)`` imports them from the committed P7a report files, so
every test here runs against the lab's actual starting record rather than a fixture that resembles
it. What is faked is the backtest -- ``remeasure.run_chunk``, the one named seam -- because
re-running 54 candidates needs a 282 MB research store. ``perfect()`` builds the re-run that
reproduces each recorded row exactly; ``rounded()`` adds the 5e-07 decimal-rounding error the real
re-run exhibits; ``drifted()`` moves one metric past the tolerance.
"""

from __future__ import annotations

import inspect
import math
import statistics

import pytest

from seer_engine import research
from seer_engine.backtest import dev
from seer_engine.backtest.registry import REGISTRY
from seer_engine.lab import npolicy, remeasure, store
from seer_engine.lab.seed import seed

TD = math.sqrt(252)


@pytest.fixture()
def conn(tmp_path):
    c = store.connect(tmp_path / "lab.sqlite")
    seed(c)
    yield c
    c.close()


def _recorded(conn):
    return {
        str(r["candidate_id"]): r
        for r in conn.execute("SELECT * FROM trials WHERE window = 'dev' ORDER BY n")
    }


def perfect(conn, *, error: float = 0.0, drift: dict[str, tuple[str, float]] | None = None):
    """A ``run_chunk`` substitute that reproduces every recorded row, optionally imperfectly.

    ``error`` is added to every float metric (use 4.9e-07 for the real rounding error, 2e-06 to
    break the tolerance). ``drift`` moves one named metric of one named candidate by a delta,
    which is how a single divergent trial is produced without touching the other fifty-three.
    """
    rows = _recorded(conn)
    drift = drift or {}

    def run_chunk(data, candidates):
        out = {}
        for c in candidates:
            r = rows[c.id]
            bump = {}
            if c.id in drift:
                name, delta = drift[c.id]
                bump[name] = delta

            def val(name, base=None):
                v = r[name] if base is None else base
                if v is None:
                    return None
                return float(v) + error + bump.get(name, 0.0)

            out[c.id] = remeasure.Observed(
                t=4983,
                sr_daily=float(r["sharpe"]) / TD,
                skew=-0.3,
                kurt=9.0,
                sharpe=val("sharpe"),
                cagr=val("cagr"),
                max_drawdown=val("max_drawdown"),
                profit_factor=val("profit_factor"),
                total_return=val("total_return"),
                trades=int(r["trades"]) + int(bump.get("trades", 0)),
            )
        return out

    return run_chunk


class FakeData:
    """The dev window, and nothing else a re-run would reach: ``run_chunk`` is substituted."""

    window = research.DEV_WINDOW
    fingerprint = "399d0d254c7a"
    market = dividends = spy_dividends = None


class FakeTestData(FakeData):
    # `research` exposes no TEST_WINDOW constant -- the test window is built per data-end by
    # `research.test_window(end)` (it is a function of the end session, not a fixed pair). This
    # is the real one: name "test", start TEST_WINDOW_START, so the guard below sees exactly what
    # a genuine test store would present.
    window = research.test_window(research.TEST_WINDOW_START)


def _plan(conn, method_id="H-P7A", **kw):
    return remeasure.seed_preflight(conn, method_id, require_commit=False, **kw)


# ---- N must not move: the brief's CRITICAL --------------------------------------------------


def test_a_full_batch_does_not_move_n(conn, monkeypatch):
    """54 trial_moments rows, and the multiple-testing N is the same integer it was."""
    monkeypatch.setattr(remeasure, "run_chunk", perfect(conn))
    n_before = store.dev_trial_count(conn)
    policy_before = npolicy.effective_n(conn, "all-trials").n
    assert n_before == 54 and policy_before == 54  # a freshly seeded lab is the 54 alone

    report = remeasure.remeasure_seed(conn, _plan(conn), FakeData())

    assert len(report.written) == 54
    assert report.blocked == ()
    assert store.dev_trial_count(conn) == n_before
    assert npolicy.effective_n(conn, "all-trials").n == policy_before
    assert conn.execute("SELECT count(*) FROM trial_moments").fetchone()[0] == 54


def test_a_full_batch_does_not_move_the_trial_sharpe_variance(conn, monkeypatch):
    """var_trials cannot move: dev_daily_sharpes reads trials.sharpe, which this never writes."""
    monkeypatch.setattr(remeasure, "run_chunk", perfect(conn))
    sharpes_before = store.dev_daily_sharpes(conn)
    var_before = statistics.variance(sharpes_before)

    remeasure.remeasure_seed(conn, _plan(conn), FakeData())

    assert store.dev_daily_sharpes(conn) == sharpes_before
    assert statistics.variance(store.dev_daily_sharpes(conn)) == var_before


def test_a_full_batch_writes_only_trial_moments(conn, monkeypatch):
    monkeypatch.setattr(remeasure, "run_chunk", perfect(conn))
    trials_before = [tuple(r) for r in conn.execute("SELECT * FROM trials ORDER BY n")]
    methods_before = [tuple(r) for r in conn.execute("SELECT * FROM methods ORDER BY id")]

    remeasure.remeasure_seed(conn, _plan(conn), FakeData())

    assert [tuple(r) for r in conn.execute("SELECT * FROM trials ORDER BY n")] == trials_before
    assert [tuple(r) for r in conn.execute("SELECT * FROM methods ORDER BY id")] == methods_before
    assert store.test_looks(conn) == 0
    nulls = conn.execute("SELECT count(*) FROM trials WHERE window='dev' AND dsr IS NULL").fetchone()
    assert nulls[0] == 54  # trials.dsr is still NULL on every seed row, and stays that way


# ---- the var_trials written ------------------------------------------------------------------


def test_var_trials_is_the_seed_set_s_own_variance(conn, monkeypatch):
    monkeypatch.setattr(remeasure, "run_chunk", perfect(conn))
    want = statistics.variance(
        [float(r[0]) / TD for r in conn.execute(
            "SELECT sharpe FROM trials WHERE window='dev' AND dsr IS NULL ORDER BY n")]
    )
    assert remeasure.seed_var_trials(conn) == want

    remeasure.remeasure_seed(conn, _plan(conn), FakeData())

    written = {r[0] for r in conn.execute("SELECT DISTINCT var_trials FROM trial_moments")}
    assert written == {want}
    # and n_at_run is the trial's recorded N, not today's count
    assert {r[0] for r in conn.execute("SELECT DISTINCT n_at_run FROM trial_moments")} == {54}


def test_var_trials_does_not_depend_on_the_chunk_size(conn, tmp_path, monkeypatch):
    """The whole point of reading it off the database: chunking cannot change what is written."""
    monkeypatch.setattr(remeasure, "run_chunk", perfect(conn))
    one = remeasure.remeasure_seed(conn, _plan(conn), FakeData(), chunk=54)
    assert one.chunks == 1
    rows_one = {r["trial_n"]: tuple(r) for r in conn.execute("SELECT * FROM trial_moments")}

    other = store.connect(tmp_path / "other.sqlite")
    seed(other)
    monkeypatch.setattr(remeasure, "run_chunk", perfect(other))
    many = remeasure.remeasure_seed(other, _plan(other), FakeData(), chunk=7)
    assert many.chunks == 8
    rows_many = {r["trial_n"]: tuple(r) for r in other.execute("SELECT * FROM trial_moments")}
    other.close()

    assert set(rows_one) == set(rows_many)
    for n, row in rows_one.items():
        assert row[:-1] == rows_many[n][:-1]  # every column but the `measured` stamp


def _lab_dev_trials(conn, sharpes):
    """Append non-seed dev trials, each with a recorded ``dsr``, as the real lab has.

    ``seed(conn)`` imports the 54 P7a rows and nothing else, so on a bare fixture the two
    variances this phase contrasts are computed over the *same* 54 rows and are necessarily
    equal: ``seed_var_trials`` reads the dev trials whose ``dsr IS NULL`` (the seed) and
    ``store.dev_sharpe_variance`` reads every dev trial. They diverge only once the lab holds
    trials of both kinds -- which the committed lab does (54 seed + 56 lab-method, 2.0067e-04
    against 2.3950e-04). Two rows reproduce that contrast at the same ratio.

    INSERT only: ``trials`` is append-only by invariant 3, and the triggers forbid UPDATE and
    DELETE, not INSERT. These rows carry a ``dsr``, so ``seed_preflight`` does not see them --
    it selects ``method_id LIKE 'H-P7A-%'`` -- and the seed path never touches them.
    """
    with conn:
        store.add_method(  # trials.method_id is a foreign key into methods
            conn, id="M0001", name="a lab method", family="momentum",
            source_kind="knowledge", hypothesis="the lab holds trials that are not the seed",
        )
        for i, sharpe in enumerate(sharpes):
            conn.execute(
                "INSERT INTO trials (method_id, candidate_id, config_digest, config_text, "
                "rules_id, allocator_id, window, start, end, store_fingerprint, git_sha, run_at, "
                "trades, failed, eligible, n_trials_at_run, curve_json, sharpe, dsr) "
                "VALUES ('M0001', ?, ?, '', '', '', 'dev', '1993-01-29', '2015-10-16', '', '', "
                "'', 0, '', 0, 54, '[]', ?, 0.5)",
                (f"M0001-V{i}", f"{i:064d}", sharpe),
            )


def test_the_report_names_both_variances(conn, monkeypatch):
    """**Decision D12, kept visible.** The report shows the gate's number and the contrast number.

    `store.dsr_at` deflates by `store.dev_sharpe_variance(conn)` -- today's, over all dev trials
    -- on both of its routes, so `SeedVerdict.dsr` is the number that decides. The recorded
    `var_trials` (the P7a search's own 54) is history and never a verdict; it is printed beside
    the gate's number only so a candidate sitting on the bar is *visibly* sitting on it. On the
    committed lab those two variances are 2.0067e-04 and 2.3950e-04, far enough apart to move
    `F9-SPY200M70-MOM30` from 0.8567 (fails) to 0.9031 (would pass). A report that printed one of
    them is how that choice gets made silently by a constant nobody looked at.
    """
    _lab_dev_trials(conn, [1.2, 0.0])  # the lab holds both kinds of trial; see the helper
    monkeypatch.setattr(remeasure, "run_chunk", perfect(conn))
    report = remeasure.remeasure_seed(conn, _plan(conn), FakeData())
    verdicts = remeasure.seed_verdicts(conn, report)
    assert verdicts, "nothing was written, so there is nothing to report"

    today = store.dev_sharpe_variance(conn)
    assert today is not None
    assert report.var_trials is not None
    assert today != pytest.approx(report.var_trials), (
        "this fixture must keep the two variances apart, or the test proves nothing"
    )

    # The verdict's own DSR is the GATE's: today's variance, at the gate's N.
    g = store.gate(conn)
    for v in verdicts:
        m = store.moments_of(conn, v.trial_n)
        assert v.dsr == pytest.approx(
            dev.deflated_sharpe(float(m["sr_daily"]), g.n, today, int(m["t"]),
                                float(m["skew"]), float(m["kurt"]))
        ), v.candidate_id
        assert v.dsr_recorded_var == pytest.approx(
            dev.deflated_sharpe(float(m["sr_daily"]), g.n, float(m["var_trials"]), int(m["t"]),
                                float(m["skew"]), float(m["kurt"]))
        ), v.candidate_id
        assert v.dsr != pytest.approx(v.dsr_recorded_var), v.candidate_id

    text = remeasure.format_seed_report(conn, report, verdicts)
    assert "variance the GATE uses" in text and "var_trials WRITTEN" in text
    assert f"{today:.6g}"[:6] in text.replace(" ", "") or f"{today:e}"[:5] in text
    assert "recorded as-of-P7a variance" in text, "the contrast column must be labelled"
    for v in verdicts:
        # Against the report's own formatter, not a re-rounded prefix of it. `format_seed_report`
        # prints `_g(v.dsr)` at 12 significant digits; a `.6f` prefix ROUNDS at the 4th decimal,
        # so a DSR on that boundary yields a string the (correct) report cannot contain --
        # F6-ML-P50-N20-TREND is 0.840199760046, whose 4-decimal rounding is "0.8402". One
        # verdict of 54 sits there, and it is the assertion that is wrong, not the report.
        assert remeasure._g(v.dsr) in text, v.candidate_id
        assert remeasure._g(v.dsr_recorded_var) in text, v.candidate_id


# ---- resumable and idempotent ----------------------------------------------------------------


def test_an_interrupted_batch_keeps_what_it_wrote_and_resumes(conn, monkeypatch):
    """Kill it mid-job: the committed chunks survive and the re-run picks up exactly the rest."""
    monkeypatch.setattr(remeasure, "run_chunk", perfect(conn))

    class Stop(Exception):
        pass

    def die(index, total, written, blocked):
        if index == 3:
            raise Stop

    with pytest.raises(Stop):
        remeasure.remeasure_seed(conn, _plan(conn), FakeData(), chunk=10, on_chunk=die)
    assert conn.execute("SELECT count(*) FROM trial_moments").fetchone()[0] == 30
    first = {r["trial_n"]: tuple(r) for r in conn.execute("SELECT * FROM trial_moments")}

    resumed = remeasure.remeasure_seed(conn, _plan(conn), FakeData(), chunk=10)

    assert sorted(resumed.skipped) == sorted(first)
    assert len(resumed.written) == 24 and len(resumed.measured) == 24
    assert conn.execute("SELECT count(*) FROM trial_moments").fetchone()[0] == 54
    kept = {r["trial_n"]: tuple(r) for r in conn.execute("SELECT * FROM trial_moments")}
    for n, row in first.items():
        assert kept[n] == row  # nothing written before the interrupt was rewritten
    assert store.dev_trial_count(conn) == 54


def test_remeasure_seed_is_idempotent(conn, monkeypatch):
    monkeypatch.setattr(remeasure, "run_chunk", perfect(conn))
    remeasure.remeasure_seed(conn, _plan(conn), FakeData())
    before = {r["trial_n"]: tuple(r) for r in conn.execute("SELECT * FROM trial_moments")}

    plan = _plan(conn)
    assert plan.nothing_to_do and len(plan.present) == 54

    second = remeasure.remeasure_seed(conn, plan, FakeData())
    assert second.written == () and second.measured == () and second.chunks == 0
    assert {r["trial_n"]: tuple(r) for r in conn.execute("SELECT * FROM trial_moments")} == before


# ---- the tolerance ---------------------------------------------------------------------------


def test_the_real_rounding_error_reproduces(conn, monkeypatch):
    """4.9e-07 on every metric is what the real re-run shows; it must not read as divergence."""
    monkeypatch.setattr(remeasure, "run_chunk", perfect(conn, error=4.9e-07))
    report = remeasure.remeasure_seed(conn, _plan(conn), FakeData())
    assert len(report.written) == 54 and report.blocked == ()


def test_a_divergent_trial_is_reported_and_not_written_and_the_rest_are(conn, monkeypatch):
    """The brief's rule: a finding per trial, not a crash -- and it blocks that trial's write."""
    monkeypatch.setattr(
        remeasure, "run_chunk",
        perfect(conn, drift={"F9-SPY200M70-MOM30": ("max_drawdown", 2e-05)}),
    )
    report = remeasure.remeasure_seed(conn, _plan(conn), FakeData())

    bad = next(r for r in report.measured if r.candidate_id == "F9-SPY200M70-MOM30")
    assert not bad.ok
    assert [c.name for c in bad.misses] == ["max_drawdown"]
    assert bad.trial_n in report.blocked and bad.trial_n not in report.written
    assert store.moments_of(conn, bad.trial_n) is None
    assert len(report.written) == 53  # every other trial was written
    assert conn.execute("SELECT count(*) FROM trial_moments").fetchone()[0] == 53


def test_a_trade_count_must_match_exactly(conn, monkeypatch):
    """The sharpest of the six: one extra closed trade is a different trade sequence."""
    monkeypatch.setattr(
        remeasure, "run_chunk", perfect(conn, drift={"F9-SPY200M70-MOM30": ("trades", 1)})
    )
    report = remeasure.remeasure_seed(conn, _plan(conn), FakeData())
    bad = next(r for r in report.measured if r.candidate_id == "F9-SPY200M70-MOM30")
    assert [c.name for c in bad.misses] == ["trades"]
    assert report.blocked == (bad.trial_n,)


def test_a_null_metric_reproduces_only_as_none(conn):
    """REF-SPY-HOLD's profit_factor is NULL in the P7a file; None is a match, a number is not."""
    both_null = remeasure.MetricCheck(name="profit_factor", recorded=None, measured=None)
    assert both_null.ok and both_null.delta is None
    assert not remeasure.MetricCheck(name="profit_factor", recorded=None, measured=1.0).ok
    assert not remeasure.MetricCheck(name="profit_factor", recorded=1.0, measured=None).ok
    assert remeasure.MetricCheck(name="cagr", recorded=1.0, measured=1.0 + 9e-07).ok
    assert not remeasure.MetricCheck(name="cagr", recorded=1.0, measured=1.0 + 2e-06).ok


# ---- the refusals ----------------------------------------------------------------------------


def test_the_seed_path_is_refused_once_any_seed_family_has_had_its_look(conn, monkeypatch):
    import dataclasses

    monkeypatch.setattr(remeasure, "run_chunk", perfect(conn))
    row = conn.execute("SELECT * FROM trials WHERE n = 53").fetchone()
    with conn:
        conn.execute(
            "INSERT INTO trials (method_id, candidate_id, config_digest, config_text, rules_id, "
            "allocator_id, window, start, end, store_fingerprint, git_sha, run_at, trades, "
            "failed, eligible, n_trials_at_run, curve_json) "
            "VALUES (?, ?, ?, '', '', '', 'test', ?, ?, '', '', '', 0, '', 0, 54, '[]')",
            (row["method_id"], row["candidate_id"] + "-T", "0" * 64, row["start"], row["end"]),
        )
    assert store.test_looks(conn) == 1
    with pytest.raises(store.LabError, match="look at the test window"):
        _plan(conn)
    assert conn.execute("SELECT count(*) FROM trial_moments").fetchone()[0] == 0


def test_a_lab_method_id_and_an_unknown_family_are_refused(conn):
    assert remeasure.is_seed_id("H-P7A") and remeasure.is_seed_id("H-P7A-F9")
    assert not remeasure.is_seed_id("M0022") and not remeasure.is_seed_id("H-A")
    with pytest.raises(store.LabError, match="not a P7a seed id"):
        _plan(conn, "M0022")
    with pytest.raises(store.LabError, match="no dev trial"):
        _plan(conn, "H-P7A-F99")
    with pytest.raises(store.LabError, match="has no trial for"):
        _plan(conn, only=("NOT-A-CANDIDATE",))


def test_a_changed_registry_entry_is_refused(conn, monkeypatch):
    """A trial whose recorded ``config_digest`` no longer matches its REGISTRY entry is refused.

    The mismatch is made on the **registry** side, not the recorded one: ``trials`` is append-only
    by invariant 3 and its ``trials_no_update`` trigger refuses the UPDATE outright, so a test
    that edited ``trials.config_digest`` would be asserting against a write the schema forbids.
    Moving the hash the registry computes produces exactly the condition the guard exists for --
    the entry changed after the trial ran -- and leaves every recorded column untouched.
    """
    real = remeasure.config_digest
    monkeypatch.setattr(
        remeasure, "config_digest",
        lambda cand: "f" * 64 if cand.id == "F9-SPY200M70-MOM30" else real(cand),
    )
    with pytest.raises(store.LabError, match="registry entry hashes ffffffffffff"):
        _plan(conn)


# ---- the test window is unreachable, structurally ---------------------------------------------


def test_no_window_can_be_selected_anywhere_in_the_seed_path(conn, monkeypatch):
    # Captured BEFORE the seam is substituted below: the last assertion drives the real
    # `run_chunk` to prove it passes `dev.run_registry` no window, and `remeasure.run_chunk` is
    # the fake by then.
    real_run_chunk = remeasure.run_chunk
    for fn in (remeasure.run_chunk, remeasure.remeasure_seed, remeasure.seed_preflight):
        assert "window" not in inspect.signature(fn).parameters
    monkeypatch.setattr(remeasure, "run_chunk", perfect(conn))
    with pytest.raises(store.LabError, match="re-runs the dev window"):
        remeasure.remeasure_seed(conn, _plan(conn), FakeTestData())
    assert conn.execute("SELECT count(*) FROM trial_moments").fetchone()[0] == 0
    assert store.test_looks(conn) == 0
    calls: list[dict] = []
    monkeypatch.setattr(
        remeasure.dev, "run_registry",
        lambda *a, **k: (calls.append(dict(k)), [])[1],
    )
    real_run_chunk(FakeData(), [])
    assert calls and all("window" not in k for k in calls)

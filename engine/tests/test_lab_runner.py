"""``lab run`` (method lab design §2, §3) on a synthetic dev-window market."""

from __future__ import annotations

import dataclasses
import json
from datetime import date, timedelta
from pathlib import Path

import pytest
from labkit import smoke_data

from seer_engine.backtest import dev as dev_module
from seer_engine.backtest.dev import Candidate, deflated_sharpe
from seer_engine.backtest.market import Market
from seer_engine.fundamentals import Fact, FundamentalPanel, coverage
from seer_engine.commands.backtest_dev import month_end_curve
from seer_engine.lab import runner, store
from seer_engine.lab.method import Method, config_digest
from seer_engine.lab.runner import OWNER_SCHEDULE_TEXT
from seer_engine.lab.seed import seed
from seer_engine.sim.contributions import OWNER_MONTHLY
from seer_engine.sim.rules import DAILY_SWITCH, MONTHLY_HOLD
from seer_engine.strategies.f_fundamental import FUNDAMENTAL, FundamentalParams
from seer_engine.strategies.f_index import TIMING, TimingParams
from seer_engine.strategies.f_rotation import ROTATION, RotationParams

def _cand(cid: str, family: str, rules=MONTHLY_HOLD, n: int = 50) -> Candidate:
    return Candidate(
        id=cid, family=family, rules=rules, allocator=TIMING,
        params=TimingParams(hold="SPY", signal="SPY", rule="sma", n=n),
        rationale="test", added=date(2026, 10, 4), owner_inputs=(),
    )


def _method(mid="M0001", cands=None, **kw) -> Method:
    cands = cands or (_cand(f"{mid}-A", mid), _cand(f"{mid}-B", mid, rules=DAILY_SWITCH, n=20))
    base = dict(id=mid, name="SMA test", family="trend", source_kind="knowledge", source_ref="",
                hypothesis="h", expected_failure="f", candidates=tuple(cands))
    base.update(kw)
    return Method(**base)


@pytest.fixture()
def conn(tmp_path):
    c = store.connect(tmp_path / "lab.sqlite")
    seed(c)
    yield c
    c.close()


@pytest.fixture(scope="module")
def data():
    return smoke_data()


def test_run_records_trials_with_lab_wide_n(conn, data, tmp_path):
    """``n_trials_at_run`` is the lab-wide gate N projected over the batch -- NOT the row count.

    Derived from ``store.pending_gate`` rather than typed, because the two are only the same
    number under the ``all-trials`` policy. ``store.DSR_POLICY`` is ``methods``
    (lab-realistic-gate R1), so on this seeded lab the batch is judged at the distinct-method
    count plus one for M0001, while the row count goes to 56. Asserting the projection keeps
    this test about what ``trial_rows`` records -- the N the DSR was actually deflated by -- and
    keeps it true under whichever policy the lab ships next.

    The row count is asserted separately, so the two cannot be silently conflated again.
    """
    m = _method()
    projected = store.pending_gate(conn, m.id, len(m.candidates))
    ran = runner.run_method(conn, m, Path(__file__), data, git_sha="deadbeef", require_commit=False)
    assert [r.trial.candidate_id for r in ran] == ["M0001-A", "M0001-B"]
    rows = store.trials_of(conn, "M0001")
    assert [r["n"] for r in rows] == [55, 56]
    assert {r["n_trials_at_run"] for r in rows} == {projected.n}
    assert store.dev_trial_count(conn) == 56, "the row count is still the row count"
    assert all(r["git_sha"] == "deadbeef" and r["window"] == "dev" for r in rows)
    for r in rows:
        assert r["end"] == "2015-10-16"
        assert json.loads(r["curve_json"])[0][1] > 0
        if r["dsr"] is None or r["dsr"] < store.DSR_MIN:
            assert store.DSR_LABEL in r["failed"] and not r["eligible"]
    method = store.get_method(conn, "M0001")
    assert method["status"] in ("rejected", "dev-eligible")
    assert method["source_sha"]
    assert "Expected failure: f" in method["hypothesis"]


def test_a_run_records_the_dsrs_inputs_beside_every_trial(conn, data):
    """R2: the four inputs a re-evaluation needs are kept, and they are the ones that were used.

    Feeding the recorded moments back into ``deflated_sharpe`` at the recorded N must reproduce
    the recorded ``dsr`` exactly -- that equality is what makes a later re-evaluation at a
    different N the *same measurement under a different bar* rather than a new one.
    """
    runner.run_method(conn, _method(), Path(__file__), data, git_sha="x", require_commit=False)
    rows = store.trials_of(conn, "M0001")
    assert [r["n"] for r in rows] == [55, 56]
    for r in rows:
        mom = store.moments_of(conn, r["n"])
        assert mom is not None, "every dev trial with a dsr keeps its inputs"
        # The EQUALITY is the claim, not the number: the moments row and the trial row must
        # name the same N or the re-evaluation below is not the same measurement. The number
        # itself is whatever `store.DSR_POLICY` resolved to and is pinned in
        # `test_run_records_trials_with_lab_wide_n` against `store.pending_gate`.
        assert mom["n_at_run"] == r["n_trials_at_run"]
        assert mom["measured"] == r["run_at"]  # one measurement, one stamp
        assert mom["t"] >= 2 and mom["var_trials"] is not None
        again = deflated_sharpe(
            mom["sr_daily"], mom["n_at_run"], mom["var_trials"], mom["t"], mom["skew"], mom["kurt"]
        )
        assert again == r["dsr"]  # pins t, skew and kurt too: any of them wrong moves the DSR


def test_recording_the_inputs_did_not_move_the_verdict(conn, data):
    """The eligibility decision reads exactly as it did before this phase.

    ``trial_rows`` is called directly here so the comparison is against the numbers the gate
    actually used: ``dsr`` is the recorded ``dsr``, and ``failed`` carries the luck label if and
    only if that ``dsr`` is below ``DSR_MIN``.
    """
    runner.run_method(conn, _method(), Path(__file__), data, git_sha="x", require_commit=False)
    for r in store.trials_of(conn, "M0001"):
        below = r["dsr"] is None or r["dsr"] < store.DSR_MIN
        assert (store.DSR_LABEL in r["failed"]) is below
        assert bool(r["eligible"]) is (r["failed"] == "")
    assert store.get_method(conn, "M0001")["status"] in ("rejected", "dev-eligible")
    assert store.test_looks(conn) == 0


def test_a_method_runs_once_and_configs_never_repeat(conn, data):
    runner.run_method(conn, _method(), Path(__file__), data, git_sha="x", require_commit=False)
    with pytest.raises(store.LabError, match="runs once"):
        runner.preflight(conn, _method(), Path(__file__), require_commit=False)
    clone = _method("M0002", cands=(_cand("M0002-A", "M0002"),))  # same config as M0001-A
    with pytest.raises(store.LabError, match="repeats M0001-A"):
        runner.preflight(conn, clone, Path(__file__), require_commit=False)


def test_a_p7a_configuration_is_not_a_new_trial(conn):
    p7a = Candidate(id="M0003-A", family="M0003", rules=MONTHLY_HOLD, allocator=TIMING,
                    params=TimingParams(hold="SPY", signal="SPY", rule="sma", n=200),
                    rationale="F1-SPY-SMA200-M again", added=date(2026, 10, 4), owner_inputs=())
    with pytest.raises(store.LabError, match="repeats F1-SPY-SMA200-M"):
        runner.preflight(conn, _method("M0003", cands=(p7a,)), Path(__file__), require_commit=False)


def test_an_idea_row_is_registered_by_its_run(conn, data):
    with conn:
        store.add_method(conn, id="M0001", name="queued", family="trend", source_kind="knowledge", hypothesis="old")
    runner.run_method(conn, _method(), Path(__file__), data, git_sha="x", require_commit=False)
    row = store.get_method(conn, "M0001")
    assert row["name"] == "SMA test" and row["hypothesis"].startswith("h")


def test_an_uncommitted_method_file_is_refused(conn, tmp_path):
    f = tmp_path / "m0009_x.py"
    f.write_text("x = 1\n")
    with pytest.raises(store.LabError, match="pre-registration"):
        runner.preflight(conn, _method("M0009"), f)


def test_method_validation():
    with pytest.raises(ValueError, match="start with"):
        _method(cands=(_cand("M0002-A", "M0001"),))
    with pytest.raises(ValueError, match="family"):
        _method(cands=(_cand("M0001-A", "M0002"),))
    with pytest.raises(ValueError, match="repeats"):
        _method(cands=(_cand("M0001-A", "M0001"), _cand("M0001-B", "M0001")))
    with pytest.raises(ValueError, match="parent_id"):
        _method(source_kind="variation", source_ref="M0000")
    with pytest.raises(ValueError, match="source_ref"):
        _method(source_kind="paper")
    rot = Candidate(id="M0001-R", family="M0001", rules=MONTHLY_HOLD, allocator=ROTATION,
                    params=RotationParams(universe=("QQQ", "SPY"), lookback=63, top=1,
                                          absolute=True, fallback=None, trend=None),
                    rationale="r", added=_cand("M0001-A", "M0001").added, owner_inputs=())
    assert config_digest(rot) != config_digest(_cand("M0001-A", "M0001"))


# ---- the post-load coverage refusal (phase 1 of fundamental-panel-coverage) -------------------


def _fund_cand(cid: str, family: str, rank: str = "value") -> Candidate:
    """One ``FUNDAMENTAL`` variant: the only allocator in the tree that is ``MarketAware``."""
    return Candidate(
        id=cid, family=family, rules=MONTHLY_HOLD, allocator=FUNDAMENTAL,
        params=FundamentalParams(rank=rank, top=20),
        rationale="fundamental variant for the coverage gate", added=date(2026, 10, 5),
        owner_inputs=(),
    )


def _dense_panel(n: int = 25) -> FundamentalPanel:
    """A panel that can rank ``n`` symbols on every monthly sample of the dev window."""
    filings = [date(1995, 1, 2) + timedelta(days=365 * k) for k in range(22)]
    facts = [
        Fact(symbol=f"S{i:02d}", taxonomy="us-gaap", tag="Assets", unit="USD", period_start=None,
             period_end=d, val=1.0e9 + i, accn=f"0000000000-{k:02d}-{i:06d}", form="10-K",
             fy=d.year, fp="FY", filed=d)
        for i in range(n)
        for k, d in enumerate(filings)
    ]
    return FundamentalPanel.from_facts(facts)


def _with_panel(data, panel: FundamentalPanel):
    """``data`` with ``panel`` on its market. The module-scoped ``data`` fixture is not mutated."""
    market = Market(
        history=data.market.history,
        membership=data.market.membership,
        fx=data.market.fx,
        fundamentals=panel,
    )
    return dataclasses.replace(data, market=market)


def test_only_a_market_aware_allocator_is_gated():
    m = _method("M0010", cands=(_fund_cand("M0010-VAL", "M0010"), _cand("M0010-T", "M0010")))
    assert runner.market_aware_candidates(m) == ("M0010-VAL",)
    assert runner.market_aware_candidates(_method()) == ()


def test_a_price_only_method_is_never_refused(data):
    """M0001 and M0004 rank on bars; the smoke market carries EMPTY_PANEL and must stay runnable."""
    assert len(data.market.fundamentals) == 0
    assert runner.preflight_data(data, _method()) is None


def test_a_market_aware_method_is_refused_against_a_panel_that_cannot_rank(data):
    m = _method("M0011", cands=(_fund_cand("M0011-VAL", "M0011"),))
    with pytest.raises(store.LabError, match="M0011-VAL") as exc:
        runner.preflight_data(data, m)
    text = str(exc.value)
    assert "0.0%" in text
    assert "--allow-coverage" in text
    assert "BELOW" in text  # the per-year table travels with the refusal


def test_allow_coverage_lifts_the_refusal_and_still_measures(data):
    m = _method("M0012", cands=(_fund_cand("M0012-VAL", "M0012"),))
    cov = runner.preflight_data(data, m, min_coverage=0.0)
    assert cov is not None
    assert cov.fraction == 0.0
    assert cov.top == coverage.DEFAULT_TOP
    assert cov.max_stale_days == coverage.default_max_stale_days()
    assert "BELOW" in coverage.format_report(cov, floor=coverage.MIN_DEV_COVERAGE)


def test_a_market_aware_method_runs_when_the_panel_can_rank(data):
    rich = _with_panel(data, _dense_panel())
    m = _method("M0013", cands=(_fund_cand("M0013-VAL", "M0013"),))
    cov = runner.preflight_data(rich, m)
    assert cov is not None
    assert cov.fraction == 1.0
    assert cov.symbols == 25


def test_the_gate_measures_content_not_presence(data):
    """A panel of 50 symbols whose every fact is filed after the dev window covers nothing."""
    late = FundamentalPanel.from_facts([
        Fact(symbol=f"L{i:02d}", taxonomy="us-gaap", tag="Assets", unit="USD", period_start=None,
             period_end=date(2015, 11, 2), val=1.0e9, accn=f"0000000000-15-{i:06d}", form="10-K",
             fy=2015, fp="FY", filed=date(2015, 11, 2))
        for i in range(50)
    ])
    thin = _with_panel(data, late)
    assert len(thin.market.fundamentals) == 50  # the panel is not empty
    m = _method("M0014", cands=(_fund_cand("M0014-VAL", "M0014"),))
    with pytest.raises(store.LabError, match="0.0%"):
        runner.preflight_data(thin, m)


def test_run_method_itself_does_not_gate(conn, data):
    """The gate lives in ``commands/lab._run``; ``run_method`` stays callable from a test."""
    ran = runner.run_method(conn, _method(), Path(__file__), data, git_sha="x", require_commit=False)
    assert len(ran) == 2


# ---- R2: the search is funded like the owner's account ---------------------------------------


def test_a_run_records_one_funding_row_per_trial(conn, data):
    """R2: every trial a funded run records carries what its deposits were and what they earned.

    The existence of the row is the funded flag, so this asserts a row per trial and not a column
    on `trials`. The numbers are the ones `trial_funding`'s CHECKs insist on -- deposits_usd > 0
    and deposits_n >= 1 -- plus the money-weighted pair the gate reads.
    """
    ran = runner.run_method(conn, _method(), Path(__file__), data, git_sha="x", require_commit=False)
    rows = store.trials_of(conn, "M0001")
    assert len(rows) == len(ran) == 2
    assert conn.execute("SELECT count(*) FROM trial_funding").fetchone()[0] == 2
    for r in rows:
        f = store.funding_of(conn, r["n"])
        assert f is not None, "a funded run records its funding beside the trial it judged"
        assert f["trial_n"] == r["n"]
        assert f["deposits_usd"] > 0 and f["deposits_n"] >= 1
        assert f["mwr"] is not None and f["spy_tr_mwr"] is not None
        assert f["schedule"] == OWNER_SCHEDULE_TEXT == "+5,000,000 IDR on the 25th of each month"
        assert f["measured"] == r["run_at"]  # one measurement, one stamp
        # The lie this phase ends: the total return counts the owner's own deposits as growth.
        assert r["total_return"] > 1.0 and f["mwr"] < 1.0
    # A second measurement of the same trial is refused by the store, not by luck.
    with pytest.raises(store.LabError, match="already has recorded funding"):
        with conn:
            store.insert_funding(conn, [store.FundingRow(
                trial_n=int(rows[0]["n"]), mwr=0.1, spy_tr_mwr=0.1, deposits_usd=1.0,
                deposits_n=1, schedule="x", measured="2026-01-01T00:00:00Z",
            )])


def test_the_money_weighted_branch_judges_a_funded_trial(conn, data):
    """The gate's money-weighted branch (`store._blocking`) is reachable and is what decides.

    A funded trial is judged on `mwr` vs `spy_tr_mwr`; the same row with no funding falls back to
    `total_return` vs `spy_tr_return`. Both branches are exercised on the same row, so this pins
    that the switch is the funding row and nothing else.
    """
    runner.run_method(conn, _method(), Path(__file__), data, git_sha="x", require_commit=False)
    seen = set()
    for r in store.trials_of(conn, "M0001"):
        f = store.funding_of(conn, r["n"])
        funded = store._blocking(r, f)
        lump = store._blocking(r, None)
        beats_mw = not any("money-weighted return" in m for m in funded)
        beats_total = not any("total return" in m for m in lump)
        seen.add((beats_mw, beats_total))
        # Whichever way each decides, the funded branch must speak money-weighted and the
        # unfunded one must speak total return. That is the branch, named.
        assert all("total return" not in m for m in funded)
        assert all("money-weighted return" not in m for m in lump)
    assert seen, "at least one trial was judged"


def test_the_recorded_trials_are_not_backfilled(conn, data):
    """GOTRADE_FEE_REBUILD_PLAN.md D18: funding applies to newly run methods only.

    The 54 seed rows this fixture carries stand in for the committed database's 128. A run must
    add funding for its own trials and for nobody else's.
    """
    before = {r[0] for r in conn.execute("SELECT n FROM trials")}
    assert before and all(store.funding_of(conn, n) is None for n in before)
    runner.run_method(conn, _method(), Path(__file__), data, git_sha="x", require_commit=False)
    assert all(store.funding_of(conn, n) is None for n in before)
    assert {r[0] for r in conn.execute("SELECT trial_n FROM trial_funding")}.isdisjoint(before)
    assert store.test_looks(conn) == 0  # and no look was spent


def test_the_recorded_funding_is_what_a_rerun_must_use(conn, data):
    """`recorded_contributions` is the single answer every re-run path asks for.

    `lab remeasure` and `lab costs` reproduce a recorded trial and refuse to write when the
    re-run is not the same measurement; funding it wrongly is exactly that. The funded flag is the
    row, so the answer is None for a seed trial and OWNER_MONTHLY for a trial this run recorded.
    """
    seeds = sorted(r[0] for r in conn.execute("SELECT n FROM trials"))
    runner.run_method(conn, _method(), Path(__file__), data, git_sha="x", require_commit=False)
    for n in seeds:
        assert runner.recorded_contributions(conn, n) is None
    for r in store.trials_of(conn, "M0001"):
        assert runner.recorded_contributions(conn, r["n"]) is OWNER_MONTHLY


def test_trial_rows_with_no_deposits_records_no_funding(conn, data):
    """The default is still a lump-sum book, and a lump-sum book has no funding row.

    `deposits=()` is read as "no deposit anywhere", which is what makes every one of the 128
    recorded trials describable by this code without a NULL to read two ways.
    """
    results: list = []
    dev_rows = dev_module.run_registry(
        data.market, data.dividends, data.spy_dividends, _method().candidates,
        on_result=lambda i, result, row: results.append((row, month_end_curve(result.snapshots))),
    )
    assert len(dev_rows) == 2
    ran = runner.trial_rows(conn, _method(), results, fingerprint="smoke", git_sha="x")
    assert [r.funding for r in ran] == [None, None]

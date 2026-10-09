"""The hard gate (lab/hardgate.py): the fold rule, the kin walk, and the refusal at promote.

Every test builds its own temp lab database. The real one has no promotable method, and these
tests must keep passing on the day it does.
"""

from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from math import comb

import pytest

from seer_engine.backtest import regime
from seer_engine.lab import hardgate, store
from seer_engine.lab import walkforward as wf


@pytest.fixture(autouse=True)
def _at_the_policy_these_fixtures_were_recorded_under(monkeypatch):
    """Judge every lab here under ``all-trials``, the policy its rows are stamped with.

    The same reason `test_lab_prereg.py` pins it: these fixtures carry ``n_trials_at_run`` equal
    to a small dev row count, which is what a lab recorded under ``all-trials`` looks like.
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


def _months(start: date, end: date) -> list[date]:
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
    out, v = [], 1.0
    for d in months:
        out.append([d.isoformat(), round(v, 8)])
        v *= (1.0 + annual) ** (1.0 / 12.0)
    return json.dumps(out)


BENCH_SPAN = (date(1993, 2, 1), date(2015, 10, 16))
DEV_SPAN = (date(1996, 1, 2), date(2015, 10, 16))


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


def _benchmark(conn) -> None:
    with conn:
        store.add_method(conn, id="H-P7A-REF", name="SPY buy and hold", family="reference",
                         source_kind="seed", hypothesis="h", status="registered")
        store.insert_trials(conn, [_trial(
            method_id="H-P7A-REF", candidate_id=regime.BENCH_CANDIDATE,
            config_digest="ref-spy-hold", start="1993-02-01", end="2015-10-16",
            curve_json=_curve(_months(*BENCH_SPAN), 0.08),
        )])


def _method(conn, mid="M0001", *, family="trend", parent=None, status="dev-eligible",
            annual=0.15, span=DEV_SPAN, curves=True) -> None:
    """One method with one dev trial, walked to ``status`` through the real transitions."""
    with conn:
        store.add_method(conn, id=mid, name=f"n{mid}", family=family, parent_id=parent,
                         source_kind="variation" if parent else "knowledge", hypothesis="h",
                         status="registered")
        store.insert_trials(conn, [_trial(
            method_id=mid, candidate_id=f"{mid}-A", config_digest=f"d-{mid}",
            curve_json=_curve(_months(*span), annual) if curves else "[]",
        )])
        for step in {
            "registered": (),
            "dev-eligible": ("dev-eligible",),
            "promoted": ("dev-eligible", "promoted"),
            "test-failed": ("dev-eligible", "promoted", "test-failed"),
            "rejected": ("rejected",),
        }[status]:
            store.update_method(conn, mid, status=step)


# ------------------------------------------------------------------ the rule, stated


def test_the_minimum_is_four_and_the_coin_flip_table_is_the_binomial_tail():
    """MIN_FOLDS = 4, and COIN_FLIP_NULL is P(X > n/2) for X ~ Bin(n, 1/2), not a typed-in table.

    The table is the argument for 4 over 3: a strict majority of an odd count is a coin flip at
    every odd count, so "at least 3" would admit evidence no stronger than one fold.
    """
    assert hardgate.MIN_FOLDS == 4
    for n, stated in hardgate.COIN_FLIP_NULL:
        tail = sum(comb(n, k) for k in range(n // 2 + 1, n + 1)) / 2 ** n
        assert stated == pytest.approx(tail, abs=5e-5), n
    odd = {n: p for n, p in hardgate.COIN_FLIP_NULL if n % 2 == 1}
    assert set(odd.values()) == {0.5}
    assert dict(hardgate.COIN_FLIP_NULL)[4] < 0.5


def test_the_module_answers_the_four_open_questions():
    """The brief asked for the reason beside each answer, in the code. This is that check."""
    doc = hardgate.__doc__ or ""
    for marker in ("(D2)", "(D3)", "(D4)", "(D6)"):
        assert marker in doc
    assert "no override path" in doc.lower()


# ------------------------------------------------------------------ the geometry


def test_the_benchmark_cuts_four_folds_and_the_geometry_is_shared(conn):
    _benchmark(conn)
    geo = hardgate.geometry(conn)
    assert len(geo.folds) == hardgate.MIN_FOLDS
    assert geo.folds[0].eval_start.year == 2003
    assert geo.folds[-1].eval_end.year == 2015
    assert geo.bench[0][0] == date(1993, 2, 28)


def test_a_missing_benchmark_refuses_and_names_ref_spy_hold(conn):
    """D7: fail closed, and say it is the lab's fixture that is missing, not the method."""
    _method(conn)
    with pytest.raises(store.LabError) as e:
        hardgate.geometry(conn)
    assert regime.BENCH_CANDIDATE in str(e.value)
    with pytest.raises(store.LabError) as e:
        hardgate.check(conn, "M0001")
    assert regime.BENCH_CANDIDATE in str(e.value)


# ------------------------------------------------------------------ the fold record


def test_a_winning_curve_takes_every_fold(conn):
    _benchmark(conn)
    _method(conn, annual=0.15)
    rec = hardgate.fold_record(conn, "M0001")
    assert isinstance(rec, wf.Record)
    assert (rec.won, len(rec.scored)) == (4, 4)
    assert rec.majority
    assert hardgate.fold_summary(conn, "M0001") == "4 of 4 folds"
    hardgate.check(conn, "M0001")  # does not raise


def test_a_losing_curve_is_refused_and_the_message_names_the_record(conn):
    _benchmark(conn)
    _method(conn, annual=0.02)
    rec = hardgate.fold_record(conn, "M0001")
    assert rec.won == 0 and not rec.majority
    with pytest.raises(store.LabError) as e:
        hardgate.check(conn, "M0001")
    assert "0 of 4 folds" in str(e.value)
    assert "override" in str(e.value)


def test_a_short_curve_is_refused_even_when_it_wins_every_fold_it_is_scored_on(conn):
    """**The case that justifies the "every fold" clause** (D2), measured, not supposed.

    A curve starting 2007-04-10 -- ``H-P7A-F10``'s real shape -- is scoreable on 2 of the 4 folds
    and wins both. ``Record.majority`` is therefore **True**: the brief's literal rule, "wins a
    majority of its walk-forward folds", would promote it on two looks at the post-crisis decade
    alone. It is refused because it is scoreable on fewer folds than the geometry yields, which
    is the whole content of "fail closed on thin evidence".
    """
    _benchmark(conn)
    _method(conn, annual=0.15, span=(date(2007, 4, 10), date(2015, 10, 16)))
    rec = hardgate.fold_record(conn, "M0001")
    assert (rec.won, len(rec.scored)) == (2, 2)
    assert rec.majority  # and it is refused anyway
    with pytest.raises(store.LabError) as e:
        hardgate.check(conn, "M0001")
    assert "2 of the 4" in str(e.value)


def test_a_method_with_no_curve_is_refused_not_crashed(conn):
    """`walkforward.evaluate` raises ValueError on an empty curve; the gate must say a sentence."""
    _benchmark(conn)
    _method(conn, curves=False)
    with pytest.raises(store.LabError):
        hardgate.fold_record(conn, "M0001")
    with pytest.raises(store.LabError):
        hardgate.check(conn, "M0001")


# ------------------------------------------------------------------ the kin walk (D4)


def test_a_failed_sibling_in_the_family_blocks(conn):
    _benchmark(conn)
    _method(conn, "M0001", family="trend", annual=0.15)
    _method(conn, "M0002", family="trend", status="test-failed")
    assert hardgate.failed_kin(conn, "M0001") == ("M0002",)
    assert hardgate.family_state(conn, "M0001") == "blocked: M0002 read test-failed"
    with pytest.raises(store.LabError) as e:
        hardgate.check(conn, "M0001")
    assert "M0002" in str(e.value)


def test_a_failed_grandparent_blocks_even_when_the_family_is_clean(conn):
    """M0030's live case: family clean, parent and grandparent both test-failed (D4)."""
    _benchmark(conn)
    _method(conn, "M0021", family="blended", status="test-failed")
    _method(conn, "M0029", family="satellite", parent="M0021", status="test-failed")
    _method(conn, "M0030", family="core-satellite", parent="M0029", annual=0.15)
    assert hardgate.failed_kin(conn, "M0030") == ("M0021", "M0029")
    with pytest.raises(store.LabError) as e:
        hardgate.check(conn, "M0030")
    assert "M0021" in str(e.value) and "M0029" in str(e.value)


def test_a_failed_descendant_does_not_reach_up_through_parent_id(conn):
    """Not the connected component (D4): a child's failure is caught by `family`, not by walking
    down. A child in a *different* family does not block its parent."""
    _benchmark(conn)
    _method(conn, "M0001", family="trend", annual=0.15)
    _method(conn, "M0002", family="elsewhere", parent="M0001", status="test-failed")
    assert hardgate.failed_kin(conn, "M0001") == ()
    hardgate.check(conn, "M0001")  # does not raise


def test_the_method_itself_is_never_its_own_kin(conn):
    _benchmark(conn)
    _method(conn, "M0001", family="trend", status="test-failed")
    assert hardgate.failed_kin(conn, "M0001") == ()


def test_a_clean_kin_reads_clean_and_an_unknown_method_raises(conn):
    _benchmark(conn)
    _method(conn, "M0001", family="trend", annual=0.15)
    assert hardgate.failed_kin(conn, "M0001") == ()
    assert hardgate.family_state(conn, "M0001") == "clean"
    with pytest.raises(store.LabError):
        hardgate.failed_kin(conn, "M9999")


def test_a_parent_cycle_does_not_hang_the_kin_walk(conn):
    """`methods.parent_id` has no cycle constraint. The walk carries a `seen` set."""
    _benchmark(conn)
    _method(conn, "M0001", family="a", annual=0.15)
    _method(conn, "M0002", family="b", parent="M0001", annual=0.15)
    with conn:
        store.update_method(conn, "M0001", parent_id="M0002")
    assert hardgate.failed_kin(conn, "M0002") == ()


# ------------------------------------------------------------------ what other phases call


def test_summary_never_raises_and_says_why_it_is_blank(conn):
    """`lab status` (phase 3) calls this once per dev-eligible method and must keep printing."""
    _method(conn, "M0001")  # no benchmark at all
    line = hardgate.summary(conn, "M0001")
    assert regime.BENCH_CANDIDATE in line
    _benchmark(conn)
    _method(conn, "M0002", family="trend", annual=0.15)
    assert hardgate.summary(conn, "M0002") == "4 of 4 folds; kin clean"


def test_a_shared_geometry_gives_the_same_answer_as_a_fresh_one(conn):
    """Phase 3 computes the geometry once and passes it down; it must change no number."""
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    geo = hardgate.geometry(conn)
    assert hardgate.fold_summary(conn, "M0001", geo) == hardgate.fold_summary(conn, "M0001")
    assert hardgate.summary(conn, "M0001", geo) == hardgate.summary(conn, "M0001")


# ------------------------------------------------------------------ de-funding


def test_a_lump_sum_trial_has_no_deposits(conn):
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    row = conn.execute(
        'SELECT n, candidate_id, start, "end", curve_json FROM trials WHERE method_id = ?',
        ("M0001",),
    ).fetchone()
    curve = [(date.fromisoformat(d), float(v)) for d, v in json.loads(row["curve_json"])]
    assert hardgate.trial_deposits(conn, row, curve) == {}


def test_a_funded_trial_is_de_funded_before_it_is_scored(conn):
    """Every trial from M0032 on is funded; reading a deposit as edge is insight 72/75's bug.

    Two claims, both measured. The reconstruction credits ``amount_idr / INITIAL_IDR`` -- 0.5 --
    per deposit, **except** the one landing on or before the curve's first point, which
    ``regime.bucket`` drops because it is already in the opening balance rather than growth over
    it: 237 deposits, 236 credited steps, 118.0 and not 118.5. And the de-funding reaches the
    gate: the same method's record changes once the funding row exists. (It changes a long way --
    half the opening balance arriving every month for twenty years is not a realistic schedule
    against a curve that opens at 1.0, which is exactly why M0032's real curve opens at 1.5. The
    test asserts that it changed, not by how much.)
    """
    from seer_engine.sim.contributions import OWNER_MONTHLY

    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    unfunded = hardgate.fold_summary(conn, "M0001")
    assert unfunded == "4 of 4 folds"

    row = conn.execute(
        'SELECT n, candidate_id, start, "end", curve_json FROM trials WHERE method_id = ?',
        ("M0001",),
    ).fetchone()
    due = OWNER_MONTHLY.dates_in(date(1996, 1, 2), date(2015, 10, 16))
    with conn:
        store.insert_funding(conn, [store.FundingRow(
            trial_n=int(row["n"]), mwr=0.11, spy_tr_mwr=0.08, deposits_usd=1.0,
            deposits_n=len(due),
            schedule="+5,000,000 IDR on the 25th of each month", measured="test",
        )])

    curve = [(date.fromisoformat(d), float(v)) for d, v in json.loads(row["curve_json"])]
    deposits = hardgate.trial_deposits(conn, row, curve)
    assert len(deposits) == len(due) - 1  # the first lands in the opening balance
    assert sum(deposits.values()) == pytest.approx(0.5 * (len(due) - 1), rel=1e-9)
    assert set(deposits) <= {d for d, _v in curve}  # keyed on curve-step end dates
    assert hardgate.fold_summary(conn, "M0001") != unfunded


def test_a_moved_contribution_schedule_refuses_rather_than_guesses(conn):
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    row = conn.execute(
        'SELECT n, candidate_id, start, "end", curve_json FROM trials WHERE method_id = ?',
        ("M0001",),
    ).fetchone()
    with conn:
        store.insert_funding(conn, [store.FundingRow(
            trial_n=int(row["n"]), mwr=0.11, spy_tr_mwr=0.08, deposits_usd=1.0, deposits_n=3,
            schedule="+5,000,000 IDR on the 25th of each month", measured="test",
        )])
    curve = [(date.fromisoformat(d), float(v)) for d, v in json.loads(row["curve_json"])]
    with pytest.raises(store.LabError) as e:
        hardgate.trial_deposits(conn, row, curve)
    assert "cannot be de-funded safely" in str(e.value)


# ------------------------------------------------------------------ what the gate judges


def test_the_gate_is_silent_for_every_status_but_dev_eligible(conn):
    """`dev-eligible -> promoted` is the only edge into `promoted` that store.TRANSITIONS admits,
    so gating it gates every promotion -- and `promote_method`, one line later, refuses a wrong
    status with the better message it already has. A `promoted` method already cleared this gate
    and its pre-registration is a promise (D3), so a repair re-run is not re-judged."""
    _method(conn, "M0001", status="registered")  # no benchmark: the gate would refuse if it ran
    hardgate.check(conn, "M0001")
    _method(conn, "M0002", family="b", status="rejected")
    hardgate.check(conn, "M0002")
    _method(conn, "M0003", family="c", status="promoted")
    hardgate.check(conn, "M0003")
    with pytest.raises(store.LabError):
        hardgate.check(conn, "M9999")


# ------------------------------------------------------------------ the refusal at the CLI


def _cli(tmp_path, db, prereg_dir, method="M0001"):
    from seer_engine.commands import lab as lab_cmd

    return lab_cmd.run(argparse.Namespace(
        db=db, lab_command="promote", method=method, dir=prereg_dir,
    ))


def test_lab_promote_exits_2_and_writes_nothing_when_the_folds_are_lost(tmp_path):
    db, prereg_dir = tmp_path / "lab.sqlite", tmp_path / "prereg"
    c = store.connect(db)
    _benchmark(c)
    _method(c, "M0001", annual=0.02)
    before = db.read_bytes()
    c.close()

    assert _cli(tmp_path, db, prereg_dir) == 2
    assert not prereg_dir.exists()
    assert db.read_bytes() == before


def test_lab_promote_exits_2_and_writes_nothing_when_the_kin_has_failed(tmp_path):
    db, prereg_dir = tmp_path / "lab.sqlite", tmp_path / "prereg"
    c = store.connect(db)
    _benchmark(c)
    _method(c, "M0001", family="trend", annual=0.15)
    _method(c, "M0002", family="trend", status="test-failed")
    before = db.read_bytes()
    c.close()

    assert _cli(tmp_path, db, prereg_dir) == 2
    assert not prereg_dir.exists()
    assert db.read_bytes() == before


def test_lab_promote_exits_2_on_thin_evidence(tmp_path):
    db, prereg_dir = tmp_path / "lab.sqlite", tmp_path / "prereg"
    c = store.connect(db)
    _benchmark(c)
    _method(c, "M0001", annual=0.15, span=(date(2007, 4, 10), date(2015, 10, 16)))
    c.close()

    assert _cli(tmp_path, db, prereg_dir) == 2
    assert not prereg_dir.exists()


def test_there_is_no_override(tmp_path):
    """No flag, no environment variable, no 'promote anyway'. The brief forbids one in the
    sentence that decides the rule, and an override is the mechanism that produced 0-for-5."""
    import inspect
    import os

    src = inspect.getsource(hardgate)
    for word in ("force", "override", "skip_gate", "SEER_SKIP", "getenv", "environ"):
        assert word not in src.replace("no override", "").replace("There is no override", "")
    assert not any(k.startswith("SEER_HARDGATE") for k in os.environ)

"""R1: the walk-forward verdict every ``lab run`` now computes, records and prints.

The decision these tests pin is the one the handover asked to be made explicitly: a lost fold
majority **annotates** a run, it does not gate it (hardgate D15, store._FOLDS_TABLE). So the
assertions come in two halves -- the record is written, complete and append-only; and nothing
about eligibility, status or the promote gate moved because of it.

Every test builds its own temp lab. The fixtures are the hard gate's own (a ``REF-SPY-HOLD`` dev
trial whose span yields four folds, methods whose curves compound at a stated annual rate), so a
number here and a number in ``test_lab_hardgate.py`` mean the same thing.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pytest
from labkit import LAB_PRICE_FINGERPRINT, smoke_data, stamp_provenance

from seer_engine.backtest import regime
from seer_engine.backtest.dev import Candidate
from seer_engine.commands import lab as lab_cmd
from seer_engine.lab import hardgate, runner, store
from seer_engine.lab.method import Amendment, Method
from seer_engine.lab.seed import seed
from seer_engine.sim.rules import MONTHLY_HOLD
from seer_engine.strategies.f_index import TIMING, TimingParams

HERE = Path(__file__)
SAME_PRICES = LAB_PRICE_FINGERPRINT
OTHER_PRICES = "e" * 64
BENCH_SPAN = (date(1993, 2, 1), date(2015, 10, 16))
DEV_SPAN = (date(1996, 1, 2), date(2015, 10, 16))


@pytest.fixture(autouse=True)
def _at_the_policy_these_fixtures_were_recorded_under(monkeypatch):
    """The same pin ``test_lab_hardgate.py`` carries: these labs are shaped like one recorded
    under ``all-trials``, which is what their ``n_trials_at_run`` values mean."""
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


def _benchmark(conn, *, prices: str | None = SAME_PRICES, curve_json: str | None = None) -> int:
    """The lab's REF-SPY-HOLD dev trial; returns its ``trials.n``."""
    with conn:
        store.add_method(conn, id="H-P7A-REF", name="SPY buy and hold", family="reference",
                         source_kind="seed", hypothesis="h", status="registered")
        ns = store.insert_trials(conn, [_trial(
            method_id="H-P7A-REF", candidate_id=regime.BENCH_CANDIDATE,
            config_digest="ref-spy-hold", start="1993-02-01", end="2015-10-16",
            store_fingerprint="5451195f",
            curve_json=_curve(_months(*BENCH_SPAN), 0.08) if curve_json is None else curve_json,
        )])
        stamp_provenance(conn, ns, price_fingerprint=prices)
    return int(ns[0])


def _method_with_curve(conn, mid="M0001", *, annual=0.15, prices=SAME_PRICES,
                       curve_json: str | None = None) -> None:
    with conn:
        store.add_method(conn, id=mid, name=f"n{mid}", family="trend", source_kind="knowledge",
                         hypothesis="h", status="registered")
        ns = store.insert_trials(conn, [_trial(
            method_id=mid, candidate_id=f"{mid}-A", config_digest=f"d-{mid}",
            curve_json=_curve(_months(*DEV_SPAN), annual) if curve_json is None else curve_json,
        )])
        stamp_provenance(conn, ns, price_fingerprint=prices)
        store.update_method(conn, mid, status="dev-eligible")


# ---- the store side: the table is a side table and it is append-only -------------------------


def test_the_fold_columns_are_the_dataclass_fields_in_order(conn):
    """``FOLD_COLUMNS`` is derived from ``fields(FoldRow)``, and ``insert_folds`` lists its values
    in that same order. A field reordered in the dataclass without the INSERT following would
    silently write every value into the wrong column, so the two are compared here rather than
    trusted."""
    assert store.FOLD_COLUMNS == (
        "method_id", "seq", "run_at", "git_sha", "bench_n", "folds_total", "folds_scored",
        "folds_won", "majority", "stable", "picks_json", "summary", "reason", "recorded",
    )
    cols = [r[1] for r in conn.execute("PRAGMA table_info(method_folds)")]
    assert tuple(cols) == store.FOLD_COLUMNS


def test_a_recorded_fold_verdict_is_append_only_and_contiguous(conn):
    _method_with_curve(conn)
    row = store.FoldRow(
        method_id="M0001", seq=1, run_at="2026-10-13T00:00:00+00:00", git_sha="abc",
        bench_n=None, folds_total=None, folds_scored=None, folds_won=None, majority=None,
        stable=None, picks_json="[]", summary="not scoreable (no benchmark)",
        reason="no benchmark", recorded="2026-10-13T00:00:01+00:00",
    )
    with conn:
        store.insert_folds(conn, row)
    assert len(store.folds_of(conn, "M0001")) == 1
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("UPDATE method_folds SET summary = 'x'")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("DELETE FROM method_folds")
    with pytest.raises(store.LabError, match="seq must be 2"):
        with conn:
            store.insert_folds(conn, row)


def test_a_half_filled_verdict_is_refused_by_the_store_and_by_the_table(conn):
    """Numbers or a reason, never both and never neither -- the one invariant three guards
    restate (the dataclass docstring, ``insert_folds``, and the table's last CHECK)."""
    _method_with_curve(conn)
    both = store.FoldRow(
        method_id="M0001", seq=1, run_at="r", git_sha="g", bench_n=1, folds_total=4,
        folds_scored=4, folds_won=3, majority=True, stable=True, picks_json="[]",
        summary="3 of 4 folds", reason="and also a reason", recorded="x",
    )
    with pytest.raises(store.LabError, match="either the numbers or the reason"):
        with conn:
            store.insert_folds(conn, both)
    neither = store.FoldRow(
        method_id="M0001", seq=1, run_at="r", git_sha="g", bench_n=None, folds_total=None,
        folds_scored=None, folds_won=None, majority=None, stable=None, picks_json="[]",
        summary="?", reason=None, recorded="x",
    )
    with pytest.raises(store.LabError, match="either the numbers or the reason"):
        with conn:
            store.insert_folds(conn, neither)


def test_a_verdict_for_an_unknown_method_is_refused(conn):
    with pytest.raises(store.LabError, match="no method M9999"):
        with conn:
            store.insert_folds(conn, store.FoldRow(
                method_id="M9999", seq=1, run_at="r", git_sha="g", bench_n=None,
                folds_total=None, folds_scored=None, folds_won=None, majority=None, stable=None,
                picks_json="[]", summary="s", reason="r", recorded="x",
            ))


def test_latest_folds_is_the_newest_seq(conn):
    _method_with_curve(conn)
    for seq in (1, 2, 3):
        with conn:
            store.insert_folds(conn, store.FoldRow(
                method_id="M0001", seq=seq, run_at=f"r{seq}", git_sha="g", bench_n=None,
                folds_total=None, folds_scored=None, folds_won=None, majority=None, stable=None,
                picks_json="[]", summary=f"s{seq}", reason=f"why {seq}", recorded="x",
            ))
    assert store.latest_folds(conn, "M0001")["summary"] == "s3"
    assert store.latest_folds(conn, "M0002") is None


# ---- the lenient verdict: numbers, or the reason there are none ------------------------------


def test_the_verdict_is_the_strict_records_own_numbers(conn):
    """``fold_verdict`` must not be a second implementation of the gate's arithmetic: it calls
    ``geometry`` and ``fold_record``, and its numbers are theirs."""
    _benchmark(conn)
    _method_with_curve(conn, annual=0.15)
    geo = hardgate.geometry(conn)
    record = hardgate.fold_record(conn, "M0001", geo)
    v = hardgate.fold_verdict(conn, "M0001")
    assert v.scoreable and v.reason is None
    assert (v.won, v.scored, v.total) == (record.won, len(record.scored), len(geo.folds))
    assert (v.majority, v.stable) == (record.majority, record.stable)
    assert v.summary == record.summary()
    assert v.bench_n == geo.bench_n
    picks = json.loads(v.picks_json)
    assert len(picks) == len(record.picks)
    assert [p["beat"] for p in picks] == [p.beat for p in record.picks]


def test_no_benchmark_is_a_reason_and_never_a_refusal(conn):
    """D6, at the level of the function. ``fold_record`` raises here; ``fold_verdict`` does not."""
    _method_with_curve(conn)
    with pytest.raises(store.LabError):
        hardgate.fold_record(conn, "M0001")
    v = hardgate.fold_verdict(conn, "M0001")
    assert not v.scoreable
    assert regime.BENCH_CANDIDATE in v.reason
    assert (v.scored, v.won, v.total, v.bench_n) == (None, None, None, None)
    assert v.picks_json == "[]"
    assert v.line().startswith("not scoreable (")


def test_a_geometry_too_thin_for_min_folds_is_a_reason(conn):
    """``hardgate.MIN_FOLDS`` is 4; a benchmark spanning twelve years yields fewer."""
    _benchmark(conn, curve_json=_curve(_months(date(2004, 1, 1), date(2015, 10, 16)), 0.08))
    _method_with_curve(conn)
    v = hardgate.fold_verdict(conn, "M0001")
    assert not v.scoreable and str(hardgate.MIN_FOLDS) in v.reason


def test_a_method_with_no_curve_is_a_reason_and_the_geometry_still_counts(conn):
    """The geometry survived, so its fold count is recorded even though nothing could be scored:
    "the lab yields four folds and this method could be scored on none" is the useful row."""
    _benchmark(conn)
    _method_with_curve(conn, curve_json="[]")
    v = hardgate.fold_verdict(conn, "M0001")
    assert not v.scoreable and "no dev trial carrying a monthly curve" in v.reason
    assert v.total == len(hardgate.geometry(conn).folds) == 4
    assert v.scored is None


def test_prices_that_are_not_the_benchmarks_are_a_reason(conn):
    """D10 refuses the comparison; the run records why rather than crashing."""
    _benchmark(conn)
    _method_with_curve(conn, prices=OTHER_PRICES)
    v = hardgate.fold_verdict(conn, "M0001")
    assert not v.scoreable and "cannot be scored against" in v.reason


def test_a_verdict_round_trips_through_its_recorded_row(conn):
    """``lab run`` prints the value and ``lab show`` prints ``from_row`` of the row that value
    produced, so the two must be the same object field for field."""
    _benchmark(conn)
    _method_with_curve(conn)
    v = hardgate.fold_verdict(conn, "M0001")
    with conn:
        store.insert_folds(conn, store.FoldRow(
            method_id="M0001", seq=1, run_at="2026-10-13T00:00:00+00:00", git_sha="g",
            bench_n=v.bench_n, folds_total=v.total, folds_scored=v.scored, folds_won=v.won,
            majority=v.majority, stable=v.stable, picks_json=v.picks_json, summary=v.summary,
            reason=v.reason, recorded="2026-10-13T00:00:01+00:00",
        ))
    assert hardgate.FoldVerdict.from_row(store.latest_folds(conn, "M0001")) == v


# ---- the decision: it annotates, it does not gate ---------------------------------------------


def test_a_lost_majority_annotates_and_the_note_says_so(conn):
    """D1 in the words the reader actually sees. A lost majority prints a warning that names
    where the gate really is, and never claims the run was refused."""
    _benchmark(conn)
    _method_with_curve(conn, annual=0.02)  # under the benchmark's 8%: loses every fold
    v = hardgate.fold_verdict(conn, "M0001")
    assert v.scoreable and not v.majority and v.won == 0
    note = v.note()
    assert "does NOT make these trials ineligible" in note
    assert "`lab promote`" in note and "`lab test`" in note
    assert "refused" not in v.line()


def test_the_promote_gate_still_refuses_what_it_refused_before(conn):
    """The other half of D1: adding the record did not weaken the gate. The same lab whose run
    would only be annotated is still refused at ``lab promote``."""
    _benchmark(conn)
    _method_with_curve(conn, annual=0.02)
    assert hardgate.fold_verdict(conn, "M0001").scoreable
    with pytest.raises(store.LabError, match="strict majority"):
        hardgate.check(conn, "M0001")


# ---- the run records it, in the trials' own transaction ---------------------------------------


def _cand(cid: str, n: int = 50) -> Candidate:
    """A real ``Candidate``, spelled as ``test_lab_runner.py:30`` spells one.

    ``MONTHLY_HOLD`` and ``TIMING`` are what the existing runner tests use, and they clear
    ``runner.preflight``'s real-fee check (``real_cost_problem``), which runs even with
    ``require_commit=False``.
    """
    return Candidate(
        id=cid, family="M0001", rules=MONTHLY_HOLD, allocator=TIMING,
        params=TimingParams(hold="SPY", signal="SPY", rule="sma", n=n),
        rationale="test", added=date(2026, 10, 4), owner_inputs=(),
    )


def _lab_method(mid: str = "M0001", cands=None, **kw) -> Method:
    base = dict(id=mid, name="n", family="trend", source_kind="knowledge", source_ref="",
                hypothesis="h", expected_failure="f",
                candidates=tuple(cands or (_cand(f"{mid}-A"),)))
    base.update(kw)
    return Method(**base)


def _on_lab_prices():
    """``smoke_data()`` claiming the prices the lab's recorded benchmark was measured on.

    **Measured, and the reason this helper exists.** ``labkit.smoke_data`` names its prices
    ``"smoke"``, while the seeded ``REF-SPY-HOLD`` trial carries the P7a fingerprint. A run on the
    bare fixture is therefore refused by hardgate (D10) and records *that* as its reason -- which
    is true, is itself worth a test (below), and is not what the rest of these tests are about.
    One ``dataclasses.replace`` says the prices match, which is the state ``lab run`` enforces in
    production through ``hardgate.pin_dev_store`` before any backtest runs.
    """
    return dataclasses.replace(smoke_data(), price_fingerprint=store.P7A_PRICE_FINGERPRINT)


@pytest.fixture()
def seeded(tmp_path):
    """A seeded lab -- the P7a record, whose ``REF-SPY-HOLD`` trial is the real benchmark and
    yields exactly four folds (measured 2026-10-13: ``len(hardgate.geometry(conn).folds) == 4``,
    which is ``hardgate.MIN_FOLDS``)."""
    c = store.connect(tmp_path / "lab.sqlite")
    seed(c)
    yield c
    c.close()


def test_a_run_records_exactly_one_fold_row_stamped_like_its_trials(seeded):
    done = runner.run_method(seeded, _lab_method(), HERE, _on_lab_prices(), git_sha="deadbeef",
                             require_commit=False)
    rows = store.folds_of(seeded, "M0001")
    assert len(rows) == 1
    row = rows[0]
    assert int(row["seq"]) == 1
    assert row["git_sha"] == "deadbeef"
    assert {row["run_at"]} == {t["run_at"] for t in store.trials_of(seeded, "M0001")}
    assert done.folds.method_id == "M0001" and done.folds.seq == 1
    assert hardgate.FoldVerdict.from_row(row) == done.verdict


def test_the_verdict_scores_the_curves_the_run_just_recorded(seeded):
    """The transaction property, as a before/after.

    Before the run, M0001 has no row at all and the record cannot be built. After it, the recorded
    row carries no reason and names the benchmark trial the folds were cut from -- which is only
    possible because the verdict was computed on a connection that can see its own uncommitted
    trials and their provenance.

    **Measured on this fixture:** four folds are cut and *none* of them can be scored, because the
    smoke market starts 2013-12-02 and its monthly curve runs 2014-02-28..2015-10-16, inside the
    last fold's training slice. That is a scoreable-but-empty record, not a refusal -- summary
    ``"no fold could be scored"``, ``folds_scored == 0``, four picks with ``picked`` None -- and
    the assertions below say so rather than pretending a two-year curve wins folds.
    """
    assert not hardgate.fold_verdict(seeded, "M0001").scoreable
    runner.run_method(seeded, _lab_method(), HERE, _on_lab_prices(), git_sha="x",
                      require_commit=False)
    row = store.latest_folds(seeded, "M0001")
    assert row["reason"] is None
    assert int(row["bench_n"]) == hardgate.geometry(seeded).bench_n
    assert int(row["folds_total"]) == len(hardgate.geometry(seeded).folds) == hardgate.MIN_FOLDS
    assert int(row["folds_scored"]) == 0 and int(row["folds_won"]) == 0
    assert row["summary"] == "no fold could be scored"
    picks = json.loads(row["picks_json"])
    assert len(picks) == 4 and all(p["picked"] is None for p in picks)
    # And the sentence the reader gets says "never in the folds", not "lost the folds".
    note = hardgate.FoldVerdict.from_row(row).note()
    assert "none of them could be scored" in note and "lost a majority" not in note


def test_a_run_whose_store_prices_are_not_the_benchmarks_records_that_reason(seeded):
    """D10 at run level, on the bare ``smoke_data()`` fixture -- whose prices are ``"smoke"`` and
    the seeded benchmark's are the P7a store's. In production ``hardgate.pin_dev_store`` refuses
    such a store before any backtest; here the run is made directly, and the point is that the
    verdict records the mismatch instead of crashing a completed batch."""
    done = runner.run_method(seeded, _lab_method(), HERE, smoke_data(), git_sha="x",
                             require_commit=False)
    row = store.latest_folds(seeded, "M0001")
    assert row["reason"] is not None and "cannot be scored against" in row["reason"]
    assert row["folds_scored"] is None and row["picks_json"] == "[]"
    assert int(row["folds_total"]) == 4  # the geometry survived; only the comparison did not
    assert len(done.ran) == 1  # and the batch was still recorded


def test_a_rolled_back_run_leaves_neither_the_trials_nor_the_verdict(seeded, monkeypatch):
    """One record or neither. ``mark_seen`` is the last statement inside the ``with conn:`` block,
    so making it raise aborts a run whose trials, side rows and fold verdict are all written."""
    before_trials = store.dev_trial_count(seeded)

    def boom(*_a, **_k):
        raise RuntimeError("abort the run after everything is written")

    monkeypatch.setattr(store, "mark_seen", boom)
    m = _lab_method(seen_keys=("concept:rollback",))
    with pytest.raises(RuntimeError):
        runner.run_method(seeded, m, HERE, _on_lab_prices(), git_sha="x", require_commit=False)
    assert store.dev_trial_count(seeded) == before_trials
    assert store.folds_of(seeded, "M0001") == []
    assert store.get_method(seeded, "M0001") is None


def test_a_run_on_a_lab_with_no_benchmark_completes_and_records_the_reason(conn):
    """D6, end to end and the one the plan names explicitly. An empty lab has no ``REF-SPY-HOLD``
    trial, so no fold can be scored -- and the run must still finish, because a fresh lab has to
    be able to run before it has a benchmark (``hardgate.pin_dev_store``)."""
    assert hardgate.benchmark_n(conn) is None
    done = runner.run_method(conn, _lab_method(), HERE, smoke_data(), git_sha="x",
                             require_commit=False)
    assert len(done.ran) == 1
    assert store.get_method(conn, "M0001")["status"] in ("rejected", "dev-eligible")
    row = store.latest_folds(conn, "M0001")
    assert row is not None and row["reason"] is not None
    assert regime.BENCH_CANDIDATE in row["reason"]
    assert row["folds_scored"] is None and row["folds_total"] is None
    assert row["picks_json"] == "[]" and row["bench_n"] is None
    # The annotation changed nothing about the trials it annotates.
    assert [bool(t["eligible"]) for t in store.trials_of(conn, "M0001")] == [
        r.trial.eligible for r in done.ran
    ]


def test_the_amend_path_records_a_second_verdict(seeded):
    """An amendment is a second batch under the same method id, so it is a second row at seq 2 --
    and the first row is untouched, because the table is append-only."""
    runner.run_method(seeded, _lab_method(), HERE, _on_lab_prices(), git_sha="x",
                      require_commit=False)
    first = dict(store.latest_folds(seeded, "M0001"))
    amended = _lab_method(amendments=(Amendment(
        added=date(2026, 10, 13), why="a second question", hypothesis="h2",
        expected_failure="f2", candidates=(_cand("M0001-B", n=20),),
    ),))
    runner.run_method(seeded, amended, HERE, _on_lab_prices(), git_sha="y",
                      require_commit=False, amend=True)
    rows = store.folds_of(seeded, "M0001")
    assert [int(r["seq"]) for r in rows] == [1, 2]
    assert dict(rows[0]) == first
    assert rows[1]["git_sha"] == "y"


# ---- what the commands print -------------------------------------------------------------


def test_lab_show_prints_the_recorded_verdict(seeded, capsys):
    runner.run_method(seeded, _lab_method(), HERE, _on_lab_prices(), git_sha="x",
                      require_commit=False)
    capsys.readouterr()
    lab_cmd._show(seeded, argparse.Namespace(method="M0001"))
    out = capsys.readouterr().out
    row = store.latest_folds(seeded, "M0001")
    assert "Walk-forward, recorded at the run of" in out
    assert hardgate.FoldVerdict.from_row(row).line() in out


def test_lab_show_prints_no_fold_line_for_a_method_that_has_none(seeded, capsys):
    """Every one of the 145 methods the lab ran before schema v7 is in this state, and a line that
    says nothing is worse than no line."""
    lab_cmd._show(seeded, argparse.Namespace(method="H-P7A-F1"))
    assert "Walk-forward" not in capsys.readouterr().out

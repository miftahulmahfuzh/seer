"""The hard gate (lab/hardgate.py): the fold rule, the kin walk, and the refusal at promote.

Every test builds its own temp lab database. The real one has no promotable method, and these
tests must keep passing on the day it does.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from math import comb

import numpy as np
import pytest

from labkit import LAB_PRICE_FINGERPRINT, stamp_provenance
from seer_engine.backtest import regime
from seer_engine.lab import hardgate, survivorship_record, store
from seer_engine.lab import walkforward as wf

SAME_PRICES = LAB_PRICE_FINGERPRINT
OTHER_PRICES = "e" * 64


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


def _benchmark(conn, *, prices: str | None = SAME_PRICES, stamped: bool = True,
               curve_json: str | None = None) -> None:
    """The lab's REF-SPY-HOLD dev trial, recorded -- like the real trial #1 -- under the P7a store
    fingerprint while every method below carries ``399d0d25``. Same prices, different store: the
    committed lab's own shape, and the case D10 says must stay comparable."""
    with conn:
        store.add_method(conn, id="H-P7A-REF", name="SPY buy and hold", family="reference",
                         source_kind="seed", hypothesis="h", status="registered")
        ns = store.insert_trials(conn, [_trial(
            method_id="H-P7A-REF", candidate_id=regime.BENCH_CANDIDATE,
            config_digest="ref-spy-hold", start="1993-02-01", end="2015-10-16",
            store_fingerprint="5451195f",
            curve_json=_curve(_months(*BENCH_SPAN), 0.08) if curve_json is None else curve_json,
        )])
        if stamped:
            stamp_provenance(conn, ns, price_fingerprint=prices)


def _method(conn, mid="M0001", *, family="trend", parent=None, status="dev-eligible",
            annual=0.15, span=DEV_SPAN, curves=True, prices: str | None = SAME_PRICES,
            stamped: bool = True, curve_json: str | None = None) -> None:
    """One method with one dev trial, walked to ``status`` through the real transitions.

    The trial is stamped with provenance on ``prices`` unless ``stamped`` is False -- the gate
    refuses an unstamped trial (D10), which is a test of its own below, not a default.
    """
    with conn:
        store.add_method(conn, id=mid, name=f"n{mid}", family=family, parent_id=parent,
                         source_kind="variation" if parent else "knowledge", hypothesis="h",
                         status="registered")
        ns = store.insert_trials(conn, [_trial(
            method_id=mid, candidate_id=f"{mid}-A", config_digest=f"d-{mid}",
            curve_json=(
                "[]" if not curves
                else curve_json if curve_json is not None
                else _curve(_months(*span), annual)
            ),
        )])
        if stamped:
            stamp_provenance(conn, ns, price_fingerprint=prices)
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


def test_the_module_records_the_variant_and_ingredient_decisions():
    """Insights 82 and 84: each rule change is argued, measured, in the docstring (D11-D13)."""
    doc = hardgate.__doc__ or ""
    for marker in ("(D11)", "(D12)", "(D13)"):
        assert marker in doc
    assert "M0044-TV14-N21" in doc       # D11's live case, named
    assert "BLEND-RM" in doc             # D12's live case, named


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


# ------------------------------------------------------------------ (D11) the promoted variant


def _variant(conn, mid: str, suffix: str, *, annual: float, config_text: str = "t",
             curves: bool = True, curve_json: str | None = None) -> None:
    """A second dev trial of an existing method -- another variant -- stamped on the lab's prices."""
    with conn:
        ns = store.insert_trials(conn, [_trial(
            method_id=mid, candidate_id=f"{mid}-{suffix}", config_digest=f"d-{mid}-{suffix}",
            config_text=config_text,
            curve_json=(
                "[]" if not curves
                else curve_json if curve_json is not None
                else _curve(_months(*DEV_SPAN), annual)
            ),
        )])
        stamp_provenance(conn, ns, price_fingerprint=SAME_PRICES)


def test_a_variant_is_scored_on_its_own_curve_not_on_its_siblings_picks(conn):
    """Insight 82's shape: the picks win every fold, the variant that would be promoted loses all.

    Both curves are monotone, so every training slice ranks both at an infinite MAR and `pick`
    breaks the tie on the candidate id: `M0001-A` (the 15% curve) is picked in every fold. The
    2% curve `M0001-Z` is never picked -- and is what `variant_record` must score.
    """
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    _variant(conn, "M0001", "Z", annual=0.02)
    picks = hardgate.fold_record(conn, "M0001")
    own = hardgate.variant_record(conn, "M0001", "M0001-Z")
    assert picks.won == 4 and picks.majority
    assert own.won == 0 and not own.majority
    assert len(own.scored) == hardgate.MIN_FOLDS
    assert {p.picked for p in own.picks} == {"M0001-Z"}


def test_a_variant_with_no_curve_cannot_be_scored(conn):
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    with pytest.raises(store.LabError) as e:
        hardgate.variant_record(conn, "M0001", "M0001-Q")
    assert "M0001-Q" in str(e.value)


def test_a_variant_on_other_prices_is_refused(conn):
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    with conn:
        ns = store.insert_trials(conn, [_trial(
            method_id="M0001", candidate_id="M0001-Z", config_digest="d-z",
            curve_json=_curve(_months(*DEV_SPAN), 0.15),
        )])
        stamp_provenance(conn, ns, price_fingerprint=OTHER_PRICES)
    with pytest.raises(store.LabError) as e:
        hardgate.variant_record(conn, "M0001", "M0001-Z")
    assert "D10" in str(e.value)


def test_the_gate_is_silent_on_the_variant_when_nothing_would_be_pre_registered(conn, monkeypatch):
    """`promote_method` refuses a method with no eligible variant one line later (D11)."""
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    monkeypatch.setattr(store, "best_dev_eligible", lambda _c, _m, **_k: None)
    assert hardgate.promoted_variant(conn, "M0001") is None
    hardgate.check(conn, "M0001")  # the picks win 4 of 4, kin clean, no variant: no refusal here


def test_the_gate_refuses_when_the_promoted_variant_loses_its_own_folds(conn, monkeypatch):
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    _variant(conn, "M0001", "Z", annual=0.02)
    best = conn.execute("SELECT * FROM trials WHERE candidate_id = 'M0001-Z'").fetchone()
    monkeypatch.setattr(store, "best_dev_eligible", lambda _c, _m, **_k: best)
    with pytest.raises(store.LabError) as e:
        hardgate.check(conn, "M0001")
    msg = str(e.value)
    assert "M0001-Z" in msg and "0 of 4" in msg and "D11" in msg
    assert "4 of 4 folds" in msg            # the picks' record, which alone would have passed
    line = hardgate.summary(conn, "M0001")
    assert "M0001-Z alone 0 of 4 folds" in line


# ------------------------------------------------------------------ (D12) ingredients are kin

BLEND_OF = (
    "rules=TradeRules(id='monthly-hold-frac-gotrade')\nallocator=<BLEND>\n"
    "params=BlendParams(parts=(BlendPart(allocator=<{own}>,share=0.5),"
    "BlendPart(allocator=<{other}>,share=0.5)))\n"
)


def test_a_blend_with_a_disproven_engine_in_it_is_kin_of_the_failure(conn):
    """Insight 84's case: M0028-BLEND-RM runs M0007's engine; M0007's family failed via M0022."""
    _benchmark(conn)
    _method(conn, "M0022", family="residual", status="test-failed")
    _method(conn, "M0007", family="residual", annual=0.15)
    _method(conn, "M0028", family="reversal", annual=0.15)
    _variant(conn, "M0028", "BLEND-RM", annual=0.15,
             config_text=BLEND_OF.format(own="M0028", other="M0007"))
    assert hardgate.ingredients(conn, "M0028") == ("M0007",)
    assert hardgate.failed_kin(conn, "M0028") == ("M0022",)
    assert hardgate.family_state(conn, "M0028") == "blocked: M0022 read test-failed"
    with pytest.raises(store.LabError) as e:
        hardgate.check(conn, "M0028")
    assert "M0022" in str(e.value) and "ingredient" in str(e.value)


def test_a_disproven_ingredient_is_itself_kin(conn):
    _benchmark(conn)
    _method(conn, "M0029", family="blended", status="test-failed")
    _method(conn, "M0028", family="reversal", annual=0.15)
    _variant(conn, "M0028", "BLEND", annual=0.15,
             config_text=BLEND_OF.format(own="M0028", other="M0029"))
    assert hardgate.failed_kin(conn, "M0028") == ("M0029",)


def test_only_lab_methods_are_ingredients(conn):
    """`<BLEND>`, `<F1>` name seed allocators, not methods; `<M9999>` names no row; and a method's
    own allocator is not its own ingredient."""
    _benchmark(conn)
    _method(conn, "M0028", family="reversal", annual=0.15)
    _variant(conn, "M0028", "X", annual=0.15,
             config_text="allocator=<BLEND>\nparams=(<F1>,<M9999>,<M0028>)\n")
    assert hardgate.ingredients(conn, "M0028") == ()
    assert hardgate.failed_kin(conn, "M0028") == ()


def test_an_ingredients_other_variants_are_not_followed(conn):
    """One hop (D12): M0028 runs M0030's engine; a *different* variant of M0030 blends M0007,
    whose family failed. M0028 never runs M0007, so it is not M0007's kin. M0030 itself is."""
    _benchmark(conn)
    _method(conn, "M0022", family="residual", status="test-failed")
    _method(conn, "M0007", family="residual", annual=0.15)
    _method(conn, "M0030", family="core-satellite", annual=0.15)
    _variant(conn, "M0030", "C50", annual=0.15,
             config_text=BLEND_OF.format(own="M0030", other="M0007"))
    _method(conn, "M0028", family="reversal", annual=0.15)
    _variant(conn, "M0028", "ON-M0030", annual=0.15, config_text="allocator=<M0030>\n")
    assert hardgate.failed_kin(conn, "M0030") == ("M0022",)
    assert hardgate.failed_kin(conn, "M0028") == ()


def test_a_nested_blend_names_every_engine_it_runs(conn):
    """The config text renders nesting in full, so a blend of a blend still names M0007."""
    _benchmark(conn)
    _method(conn, "M0022", family="residual", status="test-failed")
    _method(conn, "M0007", family="residual", annual=0.15)
    _method(conn, "M0028", family="reversal", annual=0.15)
    nested = ("allocator=<BLEND>\nparams=BlendParams(parts=(BlendPart(allocator=<M0028>),"
              "BlendPart(allocator=<BLEND>,params=BlendParams(parts=(BlendPart(allocator=<M0007>),"
              "))),))\n")
    _variant(conn, "M0028", "NEST", annual=0.15, config_text=nested)
    assert hardgate.failed_kin(conn, "M0028") == ("M0022",)


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

    Two claims, both measured. The reconstruction credits ``amount_idr / <recorded capital>`` -- 0.5 --
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
    with conn:
        stamp_provenance(conn, [int(row["n"])])  # 10M: the 0.5-per-deposit unit asserted below

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
    with conn:
        stamp_provenance(conn, [int(row["n"])])  # 10M: the 0.5-per-deposit unit asserted below
    curve = [(date.fromisoformat(d), float(v)) for d, v in json.loads(row["curve_json"])]
    with pytest.raises(store.LabError) as e:
        hardgate.trial_deposits(conn, row, curve)
    assert "cannot be de-funded safely" in str(e.value)


def _funded_trial(conn, mid: str, *, capital: str | None):
    """A funded dev trial built directly (not through ``_method``), recorded at ``capital``."""
    from seer_engine.sim.contributions import OWNER_MONTHLY

    due = OWNER_MONTHLY.dates_in(date(1996, 1, 2), date(2015, 10, 16))
    with conn:
        store.add_method(conn, id=mid, name=f"n{mid}", family="trend", source_kind="knowledge",
                         hypothesis="h", status="registered")
        (n,) = store.insert_trials(conn, [_trial(
            method_id=mid, candidate_id=f"{mid}-A", config_digest=f"d-{mid}",
            curve_json=_curve(_months(*DEV_SPAN), 0.15),
        )])
        store.insert_funding(conn, [store.FundingRow(
            trial_n=n, mwr=0.11, spy_tr_mwr=0.08, deposits_usd=1.0, deposits_n=len(due),
            schedule="+5,000,000 IDR on the 25th of each month", measured="test",
        )])
        if capital is not None:
            stamp_provenance(conn, [n], initial_idr=Decimal(capital))
    row = conn.execute(
        'SELECT n, candidate_id, start, "end", curve_json FROM trials WHERE n = ?', (n,)
    ).fetchone()
    curve = [(date.fromisoformat(d), float(v)) for d, v in json.loads(row["curve_json"])]
    return row, curve, due


def test_a_deposit_is_measured_against_the_capital_the_trial_ran_on(conn):
    """Recorded at 20M, each 5M deposit is 0.25 of the opening balance, not the 0.5 the live
    INITIAL_IDR would say. The day the constant moves again, nothing recorded re-scales."""
    row, curve, due = _funded_trial(conn, "M0002", capital="20000000")
    deposits = hardgate.trial_deposits(conn, row, curve)
    assert len(deposits) == len(due) - 1
    assert set(deposits.values()) == {0.25}


def test_a_funded_trial_with_no_recorded_capital_is_refused_not_guessed(conn):
    row, curve, _due = _funded_trial(conn, "M0003", capital=None)
    with pytest.raises(store.LabError, match="no recorded starting capital"):
        hardgate.trial_deposits(conn, row, curve)


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


# ------------------------------------------------------------------ comparability (D10)


def test_the_module_records_the_comparability_decision():
    doc = hardgate.__doc__ or ""
    assert "(D10)" in doc
    assert "price fingerprint" in doc
    assert "store_fingerprint" in doc


def test_a_different_store_fingerprint_on_the_same_prices_is_comparable(conn):
    """M1/M5: the store fingerprint moves with fundamentals.csv; the prices do not. Refusing on
    the store fingerprint would strand all seven dev-eligible methods in the real lab."""
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    stores = {r[0] for r in conn.execute("SELECT store_fingerprint FROM trials")}
    assert len(stores) == 2
    assert hardgate.comparability(conn, "M0001") == ()
    hardgate.check(conn, "M0001")  # does not raise


def test_a_trial_on_other_prices_is_refused_and_both_fingerprints_are_named(conn):
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15, prices=OTHER_PRICES)
    problems = hardgate.comparability(conn, "M0001")
    assert len(problems) == 1
    assert "M0001-A" in problems[0]
    assert OTHER_PRICES[:12] in problems[0] and SAME_PRICES[:12] in problems[0]
    with pytest.raises(store.LabError) as e:
        hardgate.fold_record(conn, "M0001")
    assert "M0001-A" in str(e.value) and "D10" in str(e.value)
    with pytest.raises(store.LabError):
        hardgate.check(conn, "M0001")
    with pytest.raises(store.LabError):
        hardgate.fold_summary(conn, "M0001")
    assert hardgate.summary(conn, "M0001").startswith("not scoreable (")


def test_a_trial_whose_prices_are_unknown_is_refused(conn):
    """Fail closed: nobody recording the prices is not evidence that they match."""
    _benchmark(conn)
    _method(conn, "M0001", family="a", annual=0.15, prices=None)
    _method(conn, "M0002", family="b", annual=0.15, stamped=False)
    assert "records no price fingerprint" in hardgate.comparability(conn, "M0001")[0]
    assert "has no provenance row" in hardgate.comparability(conn, "M0002")[0]
    for mid in ("M0001", "M0002"):
        with pytest.raises(store.LabError):
            hardgate.check(conn, mid)


def test_a_benchmark_whose_prices_are_unknown_refuses_every_method(conn):
    _benchmark(conn, stamped=False)
    _method(conn, "M0001", annual=0.15)
    problems = hardgate.comparability(conn, "M0001")
    assert len(problems) == 1 and regime.BENCH_CANDIDATE in problems[0]
    with pytest.raises(store.LabError) as e:
        hardgate.check(conn, "M0001")
    assert regime.BENCH_CANDIDATE in str(e.value)


def test_one_variant_on_other_prices_refuses_the_whole_method(conn):
    """Every variant is a candidate in every fold's pick, so one on other prices taints them all."""
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    with conn:
        ns = store.insert_trials(conn, [_trial(
            method_id="M0001", candidate_id="M0001-B", config_digest="d-M0001-B",
            curve_json=_curve(_months(*DEV_SPAN), 0.10),
        )])
        stamp_provenance(conn, ns, price_fingerprint=OTHER_PRICES)
    problems = hardgate.comparability(conn, "M0001")
    assert [p.split(" ")[0] for p in problems] == ["M0001-B"]
    with pytest.raises(store.LabError):
        hardgate.check(conn, "M0001")


def test_describe_names_three_and_counts_the_rest():
    assert hardgate.describe(()) == ""
    assert hardgate.describe(("a", "b")) == "a; b"
    assert hardgate.describe(("a", "b", "c", "d", "e")) == "a; b; c; and 2 more"


def test_lab_promote_exits_2_and_writes_nothing_on_other_prices(tmp_path):
    db, prereg_dir = tmp_path / "lab.sqlite", tmp_path / "prereg"
    c = store.connect(db)
    _benchmark(c)
    _method(c, "M0001", annual=0.15, prices=OTHER_PRICES)  # wins 4 of 4, kin clean
    before = db.read_bytes()
    c.close()

    assert _cli(tmp_path, db, prereg_dir) == 2
    assert not prereg_dir.exists()
    assert db.read_bytes() == before


# ------------------------------------------------------------------ the store pin (D10)


def test_the_dev_store_pin_takes_the_benchmarks_prices(conn):
    _benchmark(conn)
    hardgate.pin_dev_store(conn, SAME_PRICES)  # does not raise


def test_the_dev_store_pin_refuses_other_prices_and_names_both(conn):
    _benchmark(conn)
    with pytest.raises(store.LabError) as e:
        hardgate.pin_dev_store(conn, OTHER_PRICES)
    msg = str(e.value)
    assert OTHER_PRICES[:12] in msg and SAME_PRICES[:12] in msg
    assert "Nothing ran" in msg


def test_the_dev_store_pin_refuses_when_the_benchmarks_prices_are_unknown(conn):
    _benchmark(conn, stamped=False)
    with pytest.raises(store.LabError) as e:
        hardgate.pin_dev_store(conn, SAME_PRICES)
    assert regime.BENCH_CANDIDATE in str(e.value)


def test_the_dev_store_pin_refuses_a_store_whose_prices_are_unknown(conn):
    """Fail closed (D10): ``ResearchData.price_fingerprint`` is None only on a hand-built store,
    and a trial recorded on it would carry NULL prices the gate refuses forever -- so it is
    refused with or without a benchmark."""
    with pytest.raises(store.LabError, match="carries no price fingerprint"):
        hardgate.pin_dev_store(conn, None)  # no benchmark yet
    _benchmark(conn)
    with pytest.raises(store.LabError, match="carries no price fingerprint"):
        hardgate.pin_dev_store(conn, None)


def test_the_dev_store_pin_is_silent_on_a_lab_with_no_benchmark(conn):
    """A fresh lab must be able to run before it has a yardstick; the gate refuses it anyway."""
    _method(conn, "M0001")
    assert hardgate.benchmark_n(conn) is None
    hardgate.pin_dev_store(conn, OTHER_PRICES)  # does not raise


def _run_args(db, tmp_path):
    return argparse.Namespace(
        db=db, lab_command="run", method="M0099", store=tmp_path / "store", allow_coverage=0.8,
    )


def _stub_run(monkeypatch, tmp_path, prices: str):
    """`lab run` up to the store load, with no method file, no store on disk and no backtest."""
    import types

    from seer_engine import research
    from seer_engine.lab import method as method_mod
    from seer_engine.lab import runner

    stub = types.SimpleNamespace(id="M0099")
    monkeypatch.setattr(method_mod, "discover", lambda: {"M0099": (stub, tmp_path / "m.py")})
    monkeypatch.setattr(runner, "preflight", lambda *a, **k: None)
    monkeypatch.setattr(
        research, "load_store",
        lambda _path: types.SimpleNamespace(fingerprint="f" * 64, price_fingerprint=prices),
    )


class _Reached(Exception):
    """Raised by a stubbed step to prove `_run` got that far."""


def test_lab_run_refuses_a_store_with_other_prices_before_any_backtest(tmp_path, monkeypatch):
    from seer_engine.commands import lab as lab_cmd
    from seer_engine.lab import runner

    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _benchmark(c)
    trials_before = c.execute("SELECT COUNT(*) FROM trials").fetchone()[0]
    c.close()

    _stub_run(monkeypatch, tmp_path, OTHER_PRICES)

    def no_backtest(*_a, **_k):
        raise AssertionError("the store pin must refuse before any backtest")

    monkeypatch.setattr(runner, "preflight_data", no_backtest)
    monkeypatch.setattr(runner, "run_method", no_backtest)

    assert lab_cmd.run(_run_args(db, tmp_path)) == 2
    c = store.connect(db)
    assert c.execute("SELECT COUNT(*) FROM trials").fetchone()[0] == trials_before
    c.close()


def test_lab_run_takes_a_store_with_the_benchmarks_prices(tmp_path, monkeypatch):
    from seer_engine.commands import lab as lab_cmd
    from seer_engine.lab import runner

    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _benchmark(c)
    c.close()

    _stub_run(monkeypatch, tmp_path, SAME_PRICES)

    def reached(*_a, **_k):
        raise _Reached()

    monkeypatch.setattr(runner, "preflight_data", reached)
    with pytest.raises(_Reached):
        lab_cmd.run(_run_args(db, tmp_path))


# ------------------------------------------------------------------ the reports warn (D10)


def test_report_warnings_name_each_incomparable_method_once(conn):
    from seer_engine.commands import lab as lab_cmd

    _benchmark(conn)
    _method(conn, "M0001", family="a", annual=0.15)
    _method(conn, "M0002", family="b", annual=0.15, prices=OTHER_PRICES)
    _method(conn, "M0003", family="c", annual=0.15, stamped=False)
    rows = list(conn.execute(
        "SELECT n, method_id, candidate_id FROM trials WHERE window = 'dev' "
        "ORDER BY method_id, n"
    ))
    bench_n = hardgate.benchmark_n(conn)
    lines = lab_cmd._comparability_warnings(conn, bench_n, rows, set())
    assert [line.split()[1] for line in lines] == ["M0002", "M0003"]
    assert all(line.startswith("WARNING ") for line in lines)
    assert lab_cmd._comparability_warnings(conn, bench_n, rows, {"M0001"}) == []


def test_lab_walkforward_warns_on_other_prices_and_still_reports(tmp_path, capsys):
    from seer_engine.commands import lab as lab_cmd

    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _benchmark(c)
    _method(c, "M0001", family="a", annual=0.15)
    _method(c, "M0002", family="b", annual=0.15, prices=OTHER_PRICES)
    c.close()

    rc = lab_cmd.run(argparse.Namespace(
        db=db, lab_command="walkforward", method=[], min_train_years=None, eval_years=None,
    ))
    assert rc == 0  # a report warns; it does not refuse
    lines = capsys.readouterr().out.splitlines()
    warned = [line for line in lines if line.startswith("WARNING")]
    assert len(warned) == 1 and "M0002" in warned[0]
    assert any(line.strip().startswith("M0002") for line in lines)  # its row is still printed
    assert any(line.strip().startswith("M0001") for line in lines)


def test_lab_walkforward_is_silent_when_everything_is_comparable(tmp_path, capsys):
    from seer_engine.commands import lab as lab_cmd

    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _benchmark(c)
    _method(c, "M0001", annual=0.15)
    c.close()

    assert lab_cmd.run(argparse.Namespace(
        db=db, lab_command="walkforward", method=[], min_train_years=None, eval_years=None,
    )) == 0
    assert "WARNING" not in capsys.readouterr().out


# ------------------------------------------------------------------ (D14) behaviour is kin
#
# The fixtures above record constant-growth curves, whose monthly returns are flat: they have no
# correlation with anything, which is exactly why every kin test before this section is untouched
# by (D14). The curves here move. ``_MARKET`` is one seeded draw of monthly returns, the benchmark
# is that draw alone, and a book is the market plus its own seeded "idea" -- two books that share
# an idea move together once the market is taken out; two that do not, do not.

_BENCH_MONTHS = _months(*BENCH_SPAN)


def _draw(seed: int, *, mean: float, sd: float) -> dict[date, float]:
    rng = np.random.default_rng(seed)
    return dict(zip(_BENCH_MONTHS, (float(r) for r in rng.normal(mean, sd, len(_BENCH_MONTHS)))))


_MARKET = _draw(0, mean=0.007, sd=0.04)
_IDEA_A = _draw(1, mean=0.006, sd=0.03)     # the failed book's idea
_IDEA_B = _draw(2, mean=0.006, sd=0.03)     # an unrelated idea
_NOISE = _draw(3, mean=0.0, sd=0.006)       # small, so a copy of an idea still tracks it
_EDGE = {d: 0.01 for d in _BENCH_MONTHS}    # a steady extra point a month: wins the folds, and
                                            # moves nothing, so it changes no correlation


def _moving(months: list[date], *ideas: dict[date, float]) -> str:
    """A recorded monthly curve that moves: the market's return plus each idea's, every month."""
    out, v = [], 1.0
    for i, d in enumerate(months):
        if i:
            v *= 1.0 + _MARKET[d] + sum(idea[d] for idea in ideas)
        out.append([d.isoformat(), round(v, 8)])
    return json.dumps(out)


def _moving_benchmark(conn) -> None:
    _benchmark(conn, curve_json=_moving(_BENCH_MONTHS))


def _tested(conn, mid: str) -> None:
    """``mid``'s one look at the test window, spent on its ``-A`` variant (the look it lost)."""
    with conn:
        store.insert_trials(conn, [_trial(
            method_id=mid, candidate_id=f"{mid}-A", config_digest=f"d-{mid}", window="test",
            start="2016-01-04", end="2026-09-30", eligible=False,
        )])


def _failed_momentum(conn, *, prices: str | None = SAME_PRICES) -> None:
    """M0002, a momentum book that read ``test-failed`` -- with the look it spent, recorded."""
    _method(conn, "M0002", family="stock-momentum-risk-managed", status="test-failed",
            curve_json=_moving(_months(*DEV_SPAN), _IDEA_A), prices=prices)
    _tested(conn, "M0002")


def test_the_module_records_the_behavioural_kin_decision():
    """Insight 92: kin follows what a book does, argued and measured in the docstring (D14)."""
    doc = hardgate.__doc__ or ""
    assert "(D14)" in doc
    assert "F4-MOM12-N20-TREND" in doc   # the plain momentum book it catches, named
    assert "M0060" in doc and "M0062" in doc
    assert hardgate.KIN_CORRELATION == 0.85
    assert hardgate.MIN_KIN_MONTHS == 36


def test_a_book_that_moves_with_a_failed_tested_book_is_kin_under_any_name(conn):
    """Insight 92's shape: a momentum book under a brand-new family, its parent a non-momentum
    method. Family, ancestry and ingredients all read clean; its curve does not."""
    _moving_benchmark(conn)
    _failed_momentum(conn)
    _method(conn, "M0057", family="stock-short-term-momentum", status="rejected")
    _method(conn, "M0060", family="stock-low-volume-momentum", parent="M0057",
            curve_json=_moving(_months(*DEV_SPAN), _IDEA_A, _NOISE, _EDGE))
    assert hardgate.fold_record(conn, "M0060").majority   # so the refusal below is (K), not (F)
    twins = hardgate.behavioural_kin(conn, "M0060")
    assert [(t.failed_id, t.candidate_id, t.failed_candidate_id) for t in twins] == [
        ("M0002", "M0060-A", "M0002-A")
    ]
    assert twins[0].correlation >= hardgate.KIN_CORRELATION
    assert hardgate.failed_kin(conn, "M0060") == ("M0002",)
    assert hardgate.family_state(conn, "M0060") == "blocked: M0002 read test-failed"
    with pytest.raises(store.LabError) as e:
        hardgate.check(conn, "M0060")
    msg = str(e.value)
    assert f"M0060-A moves with M0002's tested M0002-A at {twins[0].correlation:.2f}" in msg
    assert "residual correlation" in msg and "D14" in msg
    assert "override" in msg


def test_a_book_with_its_own_idea_is_clean(conn):
    _moving_benchmark(conn)
    _failed_momentum(conn)
    _method(conn, "M0060", family="stock-low-volume-momentum",
            curve_json=_moving(_months(*DEV_SPAN), _IDEA_B))
    assert hardgate.behavioural_kin(conn, "M0060") == ()
    assert hardgate.failed_kin(conn, "M0060") == ()


def test_every_dev_variant_is_compared_and_the_best_pair_is_named(conn):
    """Kin is about a method, not one variant (D12's reason): a tracking variant anywhere in it
    links the method, and the twin names that variant."""
    _moving_benchmark(conn)
    _failed_momentum(conn)
    _method(conn, "M0060", family="new", curve_json=_moving(_months(*DEV_SPAN), _IDEA_B))
    _variant(conn, "M0060", "MOM", annual=0.0,
             curve_json=_moving(_months(*DEV_SPAN), _IDEA_A, _NOISE))
    (twin,) = hardgate.behavioural_kin(conn, "M0060")
    assert twin.candidate_id == "M0060-MOM"


def test_a_failed_method_with_no_recorded_look_contributes_no_behaviour(conn):
    """The tested variant is the one the look was spent on; with no test trial there is none to
    compare -- the method is still kin by family, ancestry and ingredients (D4, D12)."""
    _moving_benchmark(conn)
    _method(conn, "M0002", family="momentum", status="test-failed",
            curve_json=_moving(_months(*DEV_SPAN), _IDEA_A))
    _method(conn, "M0060", family="new", curve_json=_moving(_months(*DEV_SPAN), _IDEA_A, _NOISE))
    assert hardgate.behavioural_kin(conn, "M0060") == ()
    assert hardgate.failed_kin(conn, "M0060") == ()


def test_flat_curves_are_not_measured_and_raise_no_warning(conn):
    """A constant-growth curve -- every fixture above -- has no variance, so no correlation. It is
    "not measured", never kin, and it never reaches np.polyfit or np.corrcoef to warn."""
    import warnings

    _benchmark(conn)                      # flat benchmark
    _method(conn, "M0002", family="momentum", status="test-failed",
            curve_json=_moving(_months(*DEV_SPAN), _IDEA_A))
    _tested(conn, "M0002")
    _method(conn, "M0060", family="new", curve_json=_moving(_months(*DEV_SPAN), _IDEA_A))
    _method(conn, "M0061", family="other", annual=0.15)  # flat book
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert hardgate.behavioural_kin(conn, "M0060") == ()   # the benchmark is flat
        assert hardgate.behavioural_kin(conn, "M0061") == ()
        flat = hardgate.monthly_returns(hardgate._curve_of(conn.execute(
            "SELECT curve_json FROM trials WHERE candidate_id = 'M0061-A'").fetchone()))
        moving = hardgate.monthly_returns([(d, 1.0 + 0.01 * (i % 7)) for i, d in
                                           enumerate(_months(*DEV_SPAN))])
        assert hardgate.residual(flat, moving) is None
        assert hardgate.correlation(flat, moving) is None


def test_fewer_than_the_minimum_common_months_is_not_measured(conn):
    _moving_benchmark(conn)
    _failed_momentum(conn)
    short = _months(date(2013, 1, 1), date(2015, 10, 16))  # 34 points, 33 monthly returns
    _method(conn, "M0060", family="new", span=(short[0], short[-1]),
            curve_json=_moving(short, _IDEA_A, _NOISE))
    assert len(short) - 1 < hardgate.MIN_KIN_MONTHS
    assert hardgate.behavioural_kin(conn, "M0060") == ()
    months = [(2000 + i // 12, 1 + i % 12) for i in range(hardgate.MIN_KIN_MONTHS)]
    a = {m: float(i % 5) for i, m in enumerate(months)}
    b = {m: float(i % 5) + 0.1 * (i % 3) for i, m in enumerate(months)}
    assert hardgate.correlation(a, b) is not None
    del a[months[0]]
    assert hardgate.correlation(a, b) is None


def test_behaviour_is_one_hop(conn):
    """Only failed tested books are compared. M0070 is M0002's kin by family; M0080 moves with
    M0070 and not with M0002, so it is nobody's kin -- kin of kin is (D4)'s blob."""
    _moving_benchmark(conn)
    _failed_momentum(conn)
    _method(conn, "M0070", family="stock-momentum-risk-managed", status="rejected",
            curve_json=_moving(_months(*DEV_SPAN), _IDEA_B))
    _method(conn, "M0080", family="unrelated",
            curve_json=_moving(_months(*DEV_SPAN), _IDEA_B, _NOISE))
    assert hardgate.failed_kin(conn, "M0070") == ("M0002",)
    assert hardgate.behavioural_kin(conn, "M0080") == ()
    assert hardgate.failed_kin(conn, "M0080") == ()


def test_a_failed_tested_book_on_other_prices_refuses_rather_than_reads_clean(conn):
    """Fail closed (D10): a comparison across two price histories measures the data."""
    _moving_benchmark(conn)
    _failed_momentum(conn, prices=OTHER_PRICES)
    _method(conn, "M0060", family="new", curve_json=_moving(_months(*DEV_SPAN), _IDEA_B))
    with pytest.raises(store.LabError) as e:
        hardgate.behavioural_kin(conn, "M0060")
    assert "M0002-A" in str(e.value) and "D10" in str(e.value)
    with pytest.raises(store.LabError):
        hardgate.failed_kin(conn, "M0060")
    with pytest.raises(store.LabError):
        hardgate.check(conn, "M0060")
    assert "kin unknown (" in hardgate.summary(conn, "M0060")


def test_the_method_itself_is_never_its_own_behavioural_kin(conn):
    _moving_benchmark(conn)
    _failed_momentum(conn)
    assert hardgate.behavioural_kin(conn, "M0002") == ()
    assert hardgate.failed_kin(conn, "M0002") == ()


def test_a_method_with_no_curve_has_nothing_measured(conn):
    """Nothing to compare, so its kin is (D4) and (D12) alone -- and no benchmark is needed to
    say so. The gate never reaches (K) for it anyway: (F) refuses a method with no curve."""
    _failed_momentum(conn)                # no benchmark at all
    _method(conn, "M0060", family="new", curves=False)
    assert hardgate.behavioural_kin(conn, "M0060") == ()
    assert hardgate.failed_kin(conn, "M0060") == ()
    with pytest.raises(store.LabError):
        hardgate.behavioural_kin(conn, "M9999")


def test_lab_walkforward_prints_a_kin_it_cannot_read_and_fires_nothing(tmp_path, capsys):
    """The report catches the kin's refusal (D10, D14) and hands it to the signal as the failed
    kin, so the signal cannot fire on a kin nobody could check -- walkforward.py unedited (D13)."""
    from seer_engine.commands import lab as lab_cmd

    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _moving_benchmark(c)
    _failed_momentum(c, prices=OTHER_PRICES)
    _method(c, "M0060", family="new", curve_json=_moving(_months(*DEV_SPAN), _IDEA_B))
    c.close()

    rc = lab_cmd.run(argparse.Namespace(
        db=db, lab_command="walkforward", method=[], min_train_years=None, eval_years=None,
    ))
    assert rc == 0
    out = capsys.readouterr().out
    row = next(line for line in out.splitlines() if line.strip().startswith("M0060"))
    assert "kin unknown (" in row
    assert "No buy signal" in out


def test_lab_tests_note_says_when_the_kin_cannot_be_read(conn):
    """A note, never a refusal (D3): a kin walk that cannot run is still information."""
    from seer_engine.lab import runner

    _moving_benchmark(conn)
    _failed_momentum(conn, prices=OTHER_PRICES)
    _method(conn, "M0060", family="new", status="promoted",
            curve_json=_moving(_months(*DEV_SPAN), _IDEA_B))
    note = runner.kin_note(conn, "M0060")
    assert note is not None
    assert "could not be read" in note and "not a refusal" in note


# --- (D16): a dev-store drawdown under the bar is not evidence the book clears it -------------


def _grid(tmp_path, rows):
    """A committed-grid lookalike: the real columns this reader uses, in the real order."""
    p = tmp_path / "grid.csv"
    head = "method_id,candidate_id,store,max_drawdown\n"
    p.write_text(head + "".join(f"{m},{c},{s},{d}\n" for m, c, s, d in rows), encoding="utf-8")
    return p


def test_the_survivorship_grid_reader_reads_only_the_fuller_history(tmp_path):
    """Both stores are in one file; only the survivorship rows are the second opinion."""
    g = _grid(tmp_path, [
        ("M0001", "M0001-A", "dev", "0.19"),
        ("M0001", "M0001-A", "survivorship", "0.2346"),
    ])
    assert survivorship_record.sv_drawdown("M0001", "M0001-A", g) == 0.2346
    assert survivorship_record.over_bar("M0001", "M0001-A", 0.20, g) == 0.2346
    assert survivorship_record.over_bar("M0001", "M0001-A", 0.25, g) is None


def test_an_unmeasured_variant_reads_none_and_never_refuses(tmp_path):
    """Absence is not evidence. `engine/.research-sv` is not on every machine, so refusing every
    unmeasured variant would stop the lab on a store the owner may not hold (D16)."""
    g = _grid(tmp_path, [("M0001", "M0001-A", "survivorship", "0.30")])
    assert survivorship_record.sv_drawdown("M0001", "M0001-NEVER-RUN", g) is None
    assert survivorship_record.over_bar("M0001", "M0001-NEVER-RUN", 0.20, g) is None
    assert survivorship_record.sv_drawdown("M9999", "M9999-A", g) is None


def test_a_missing_or_malformed_grid_is_an_empty_mapping_not_a_crash(tmp_path):
    """A checkout that never ran `lab survivorship` is a normal checkout."""
    assert survivorship_record.sv_drawdown("M0001", "M0001-A", tmp_path / "absent.csv") is None
    g = _grid(tmp_path, [
        ("M0001", "M0001-A", "survivorship", ""),
        ("M0001", "M0001-B", "survivorship", "not-a-number"),
    ])
    assert survivorship_record.sv_drawdown("M0001", "M0001-A", g) is None
    assert survivorship_record.sv_drawdown("M0001", "M0001-B", g) is None


def test_the_gate_refuses_a_promoted_variant_that_falls_past_the_bar_on_honest_data(
    conn, monkeypatch, tmp_path
):
    """THE RULE. The variant wins its own folds, its kin is clean and its dev-store fall clears
    the bar -- and it is still refused, because the history that fall was measured on is missing
    four in ten of the index's days (D16)."""
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    best = conn.execute("SELECT * FROM trials WHERE candidate_id = 'M0001-A'").fetchone()
    assert best is not None
    monkeypatch.setattr(store, "best_dev_eligible", lambda _c, _m, **_k: best)
    assert hardgate.promoted_variant(conn, "M0001") == "M0001-A"
    assert hardgate.failed_kin(conn, "M0001") == ()          # kin is NOT why it is refused
    hardgate.check(conn, "M0001")                            # clean before the grid says otherwise

    # The fall is 28.46% and not the 23.46% this fixture used until 2026-10-14: the owner raised
    # the real-money bar 20% -> 25% that day (design §18) and 23.46% now sits INSIDE it. D16 is a
    # real-money rule and keeps reading ``tuning.MAX_DRAWDOWN``, so the fixture moves with the bar
    # rather than the rule moving to the lab's looser dev screen.
    g = _grid(tmp_path, [("M0001", "M0001-A", "survivorship", "0.2846")])
    monkeypatch.setattr(survivorship_record, "GRID_PATH", g)
    with pytest.raises(store.LabError) as e:
        hardgate.check(conn, "M0001")
    msg = str(e.value)
    assert "M0001-A" in msg and "28.46%" in msg and "25%" in msg and "D16" in msg
    assert "grid.csv" in msg


def test_the_gate_still_promotes_a_variant_the_fuller_history_clears(conn, monkeypatch, tmp_path):
    """The rule refuses what was measured OVER the bar, not everything that was measured."""
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    best = conn.execute("SELECT * FROM trials WHERE candidate_id = 'M0001-A'").fetchone()
    monkeypatch.setattr(store, "best_dev_eligible", lambda _c, _m, **_k: best)
    g = _grid(tmp_path, [("M0001", "M0001-A", "survivorship", "0.1600")])
    monkeypatch.setattr(survivorship_record, "GRID_PATH", g)
    hardgate.check(conn, "M0001")  # does not raise


def test_the_committed_grid_still_holds_the_eleven_that_cross(tmp_path):
    """Pins the live evidence (D16). If `lab survivorship` is ever re-run and the grid rewritten,
    this goes red and the numbers in the docstring and design doc §17 must be re-read."""
    grid = survivorship_record.GRID_PATH
    if not grid.is_file():                     # a checkout without docs/ is not a failure
        pytest.skip("docs/lab/survivorship/grid.csv not in this checkout")
    for mid, cid, expected in (
        ("M0007", "M0007-N20-RAW", 0.2346),
        ("M0020", "M0020-W-NOSTOP", 0.2342),
        ("M0019", "M0019-RAW20-S15", 0.2448),
    ):
        dd = survivorship_record.sv_drawdown(mid, cid)
        assert dd is not None and round(dd, 4) == expected
        assert survivorship_record.over_bar(mid, cid, 0.20) is not None
    # and one that clears it, so the test cannot pass by refusing everything
    assert survivorship_record.over_bar("M0007", "M0007-N20", 0.20) is None


def test_the_module_records_the_survivorship_drawdown_decision():
    """(D16) is argued in the docstring, with the measurement, not merely asserted."""
    doc = hardgate.__doc__ or ""
    assert "(D16)" in doc
    assert "M0007-N20-RAW" in doc and "23.46" in doc
    assert "-9.03" in doc and "+14.44" in doc      # the spread that forbids a blanket haircut
    assert "absence is not evidence" in doc.lower()


# ------------------------------------------------------------------ control shape (D17)
#
# The seam these tests turn on: `control_shape.for_method` reads a method's arms from its
# `lab/methods/mNNNN_*.py` file, and every fixture in this module builds its method straight into
# the database with no file. Without `_declare` below, `for_method` returns () for a synthetic id
# -- or, for `M0001`, finds the REAL method file of that name and judges these rows against its
# candidate ids -- and D17 never fires, so every test here would pass while testing nothing.


R_IDEA = "The idea: the twenty strongest names in the pool, equal slots, nothing timed"
R_DRAW = "Placebo: the same frame with 20 hash-drawn names from the same scored pool"
R_DOSE = "the same names one to two years stale and none since: does the date do any work?"
R_PLAIN = "the same book, held a month longer"


@dataclass(frozen=True)
class _Arm:
    """An arm as `control_shape` sees one: an id and the one line of prose its author wrote.

    Detection is by the rationale and never by the id suffix -- `M0005-ALL-R` carries a `-R` and
    is a rank-weighting variant, not a control -- so these strings are load-bearing, not labels.
    """

    id: str
    rationale: str


def _declare(monkeypatch, **by_method: list) -> None:
    """Make `control_shape.for_method` and `survey` see `arms` for each method, with no file.

    See the section header: this is the seam, and it is the only way D17 can fire in this module.
    `for_method` imports `discover` inside its body, so patching the attribute on
    `seer_engine.lab.method` is enough.
    """
    import types
    from pathlib import Path

    from seer_engine.lab import method as method_mod

    files = {
        mid: (types.SimpleNamespace(id=mid, all_candidates=lambda arms=arms: tuple(arms)),
              Path(f"{mid}.py"))
        for mid, arms in by_method.items()
    }
    monkeypatch.setattr(method_mod, "discover", lambda: files)


def _control_arm(conn, mid: str, suffix: str, *, trades: int, turnover: float,
                 annual: float = 0.15) -> None:
    """A recorded control arm of ``mid``: one dev trial carrying a trade count and a turnover.

    The arm it controls is `{mid}-A`, which `_method` records with trades 250 and turnover 1.1.
    """
    with conn:
        ns = store.insert_trials(conn, [_trial(
            method_id=mid, candidate_id=f"{mid}-{suffix}", config_digest=f"d-{mid}-{suffix}",
            trades=trades, turnover=turnover,
            curve_json=_curve(_months(*DEV_SPAN), annual),
        )])
        stamp_provenance(conn, ns, price_fingerprint=SAME_PRICES)


def _with_control(monkeypatch, mid: str = "M0001") -> None:
    """The ordinary shape: one book that names itself the idea, one placebo drawn against it."""
    _declare(monkeypatch, **{mid: [_Arm(f"{mid}-A", R_IDEA), _Arm(f"{mid}-R", R_DRAW)]})


def test_the_module_records_the_control_shape_decision():
    """(D17) is written down where the other sixteen are, with its calibration in it."""
    doc = hardgate.__doc__ or ""
    assert "(D17)" in doc
    assert "M0248-R" in doc and "M0230-C50-R" in doc and "M0243-NEAR20-R" in doc
    assert "dose-response" in doc
    # The two cases the band has to separate, both named in the text.
    assert "M0226-RAND2" in doc and "M0241-PLACEBO" in doc
    # The reconciled fact, both halves, and the way back.
    assert "M0072" in doc and "M0047" in doc
    assert "amendment" in doc
    # The supersession rule, and the measurement that made it `ok` and not `ok or warn`.
    assert "SUPERSEDES" in doc or "superseded" in doc
    assert "M0047-PLC1-MV20" in doc


def test_a_mis_shaped_control_refuses_promotion_and_names_both_ratios(conn, monkeypatch):
    """M0248's shape: the blind draw trades about three times the book it controls."""
    from seer_engine.lab import control_shape as cs

    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)                      # M0001-A, 250 trades, turnover 1.1
    _control_arm(conn, "M0001", "R", trades=800, turnover=3.5)
    _with_control(monkeypatch)
    with pytest.raises(store.LabError) as e:
        hardgate.check(conn, "M0001")
    said = str(e.value)
    assert "M0001-R" in said and "M0001-A" in said
    assert "3.20x" in said and "3.18x" in said               # 800/250 and 3.5/1.1
    assert cs.RUNG_IDEA in said                              # describe() names the rung
    assert f"{cs.REFUSE_BAND[0]:.2f}x to {cs.REFUSE_BAND[1]:.2f}x" in said
    assert "D17" in said and "no override" in said
    assert "amendment" in said and "costs no method id" in said   # the way back is named


def test_a_control_handicapped_the_other_way_is_refused_too(conn, monkeypatch):
    """M0230's shape: a control that barely trades at all is just as unusable as one that churns."""
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    _control_arm(conn, "M0001", "R", trades=18, turnover=0.15)
    _with_control(monkeypatch)
    with pytest.raises(store.LabError) as e:
        hardgate.check(conn, "M0001")
    assert "M0001-R" in str(e.value)


def test_a_matched_control_promotes(conn, monkeypatch):
    """M0244-PLACEBO30's shape -- about 1.01x / 0.98x -- is what a control should look like."""
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    _control_arm(conn, "M0001", "R", trades=252, turnover=1.08)
    _with_control(monkeypatch)
    hardgate.check(conn, "M0001")                            # returns: no refusal


def test_an_honest_control_supersedes_the_handicapped_one_and_the_gate_passes(conn, monkeypatch):
    """(D17) The way back, tested rather than quoted.

    `M0001-R` is M0230's shape -- 18 trades against 250, 0.15 turnover against 1.1 -- and refuses.
    `M0001-A-PLC` is a later control of the same arm at 1.01x / 0.98x. The old arm cannot be
    removed: a method file's recorded trials pin its candidates and `trials` is append-only by
    trigger. Before this rule the re-draw changed nothing and the method stayed blocked forever.
    """
    from seer_engine.lab import control_shape as cs

    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)                      # M0001-A, 250 trades, turnover 1.1
    _control_arm(conn, "M0001", "R", trades=18, turnover=0.15)
    _control_arm(conn, "M0001", "A-PLC", trades=252, turnover=1.08)
    plc = _Arm("M0001-A-PLC", R_DRAW)
    object.__setattr__(plc, cs.SUPERSEDES_ATTR, ("M0001-R",))   # the declaration IS the rule
    _declare(monkeypatch, M0001=[_Arm("M0001-A", R_IDEA), _Arm("M0001-R", R_DRAW), plc])

    found = {f.control_id: f for f in cs.for_method(conn, "M0001")}
    assert found["M0001-A-PLC"].verdict == cs.OK
    assert found["M0001-R"].verdict == cs.REFUSE          # still measured, still reported
    assert found["M0001-R"].superseded_by == "M0001-A-PLC"
    assert found["M0001-R"].blocking is False

    assert hardgate.mis_shaped_controls(conn, "M0001") == ()
    hardgate.check(conn, "M0001")                            # and the gate no longer refuses


def test_a_clean_redraw_that_declares_nothing_does_not_pass_the_gate(conn, monkeypatch):
    """The condition that makes the rule a no-op on today's lab, at the gate.

    `M0001-A-PLC` is clean, is a placebo and resolves to the same arm `M0001-R` does. Under the
    target-equality rule the draft proposed, that would clear D17. It does not clear it here,
    because the arm never said it was replacing anything -- and the lab holds 46 placebo arms
    that were never asked to say so.
    """
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    _control_arm(conn, "M0001", "R", trades=18, turnover=0.15)
    _control_arm(conn, "M0001", "A-PLC", trades=252, turnover=1.08)
    _declare(monkeypatch, M0001=[_Arm("M0001-A", R_IDEA), _Arm("M0001-R", R_DRAW),
                                 _Arm("M0001-A-PLC", R_DRAW)])
    with pytest.raises(store.LabError) as e:
        hardgate.check(conn, "M0001")
    assert "M0001-R" in str(e.value)


def test_a_redraw_that_only_warns_does_not_supersede_at_the_gate(conn, monkeypatch):
    """1.40x / 1.41x is inside the refuse band and outside the match band: still a bent stick.

    Measured on the committed lab, the loose reading would retire M0047's 0.549x control with its
    own 0.545x twin and unblock the method with nothing honest drawn. The replacement has to clear
    WARN_BAND.
    """
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    _control_arm(conn, "M0001", "R", trades=18, turnover=0.15)
    _control_arm(conn, "M0001", "A-PLC", trades=350, turnover=1.55)
    from seer_engine.lab import control_shape as cs

    plc = _Arm("M0001-A-PLC", R_DRAW)
    object.__setattr__(plc, cs.SUPERSEDES_ATTR, ("M0001-R",))
    _declare(monkeypatch, M0001=[_Arm("M0001-A", R_IDEA), _Arm("M0001-R", R_DRAW), plc])
    with pytest.raises(store.LabError) as e:
        hardgate.check(conn, "M0001")
    assert "M0001-R" in str(e.value)


def test_an_unrun_redraw_does_not_supersede_at_the_gate(conn, monkeypatch):
    """The commit is the pre-registration, and it lands BEFORE the run. Between the two the new
    arm has no trial row, reads `unrecorded`, and must not clear the gate: otherwise D17 would be
    satisfied by an intention rather than by a measurement."""
    from seer_engine.lab import control_shape as cs

    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    _control_arm(conn, "M0001", "R", trades=18, turnover=0.15)
    plc = _Arm("M0001-A-PLC", R_DRAW)
    object.__setattr__(plc, cs.SUPERSEDES_ATTR, ("M0001-R",))   # declared, but never run
    _declare(monkeypatch, M0001=[_Arm("M0001-A", R_IDEA), _Arm("M0001-R", R_DRAW), plc])
    found = {f.control_id: f for f in cs.for_method(conn, "M0001")}
    assert found["M0001-A-PLC"].verdict == cs.UNRECORDED
    assert found["M0001-R"].superseded_by is None
    with pytest.raises(store.LabError):
        hardgate.check(conn, "M0001")


def test_a_dose_response_arm_is_never_refused_for_its_shape(conn, monkeypatch):
    """The permanent-false-alarm case. A dose arm trades a fifth as often BY DESIGN."""
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    _control_arm(conn, "M0001", "STALE", trades=50, turnover=0.22)
    _declare(monkeypatch, M0001=[_Arm("M0001-A", R_IDEA), _Arm("M0001-STALE", R_DOSE)])
    hardgate.check(conn, "M0001")                            # not-checked, never refuse


def test_a_method_with_no_control_arm_promotes_exactly_as_before(conn, monkeypatch):
    """Most of the lab draws no control. (D17) makes no claim about a book nobody drew one for."""
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    _variant(conn, "M0001", "B", annual=0.14)
    _declare(monkeypatch, M0001=[_Arm("M0001-A", R_IDEA), _Arm("M0001-B", R_PLAIN)])
    hardgate.check(conn, "M0001")


def test_a_shape_that_cannot_be_read_does_not_refuse(conn, monkeypatch):
    """Absence is not evidence (D16's sentence). Only a measured mismatch refuses.

    Two ways a shape goes unread, both pinned: the reader raising (the `except` in
    `mis_shaped_controls`), and the reader coming back with a verdict that is not `refuse` --
    here `unresolved`, because every arm of the method is itself a placebo and none of them
    controls another.
    """
    from seer_engine.lab import control_shape as cs

    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    _control_arm(conn, "M0001", "R", trades=800, turnover=3.5)

    _declare(monkeypatch, M0001=[_Arm("M0001-A", R_DRAW), _Arm("M0001-R", R_DRAW)])
    found = cs.for_method(conn, "M0001")
    assert {f.verdict for f in found} == {cs.UNRESOLVED}
    assert hardgate.mis_shaped_controls(conn, "M0001") == ()
    hardgate.check(conn, "M0001")                            # and the gate stays silent

    def refuses(*_a, **_k):
        raise store.LabError("cannot resolve what M0001-R controls")

    monkeypatch.setattr(cs, "for_method", refuses)
    assert hardgate.mis_shaped_controls(conn, "M0001") == ()
    hardgate.check(conn, "M0001")


# The nine dev-eligible methods D17 stops today, named in (D17)'s own text. Measured read-only on
# 2026-10-19 against this tree's committed lab: all nine refuse, on thirteen arms between them.
BLOCKED_NINE: tuple[str, ...] = (
    "M0047", "M0201", "M0202", "M0208", "M0215", "M0221", "M0225", "M0227", "M0243",
)


def test_supersession_unblocks_none_of_the_nine_until_an_honest_control_runs():
    """(D17) The no-op proof at the gate. A rule change that quietly promoted nine methods would
    be the worst possible outcome of this edit, so it is asserted rather than reasoned about.

    `store.COMMITTED_DB` -- this tree's `lab/lab.sqlite`, opened mode=ro and never through
    `store.connect`, which migrates and so dirties the file on a read. The bytes are hashed either
    side.

    Each method is allowed one of exactly two states, and never neither: still blocking, or holding
    the band-clean control that retired its refusal -- with the refusal still reported. On this
    tree today every one of the nine is in the first state.
    """
    from seer_engine.lab import control_shape as cs

    if not store.COMMITTED_DB.exists():
        pytest.skip("no lab database")
    before = hashlib.sha256(store.COMMITTED_DB.read_bytes()).hexdigest()
    conn = sqlite3.connect(f"file:{store.COMMITTED_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        for mid in BLOCKED_NINE:
            found = cs.for_method(conn, mid)
            if not found:
                pytest.skip(f"{mid} has no method file or no control arm in this tree")
            off = hardgate.mis_shaped_controls(conn, mid)
            retired = [f for f in found if f.superseded_by is not None]
            assert off or retired, f"{mid} is no longer read by D17 at all"
            assert off == cs.refusals(found)
            for f in retired:
                # Still reported, never dropped. A retired arm keeps whatever flagged verdict it
                # earned -- usually `refuse`, but `M0047-PLC1-MV20` was only ever a `warn` and is
                # superseded all the same, which is strictly the smaller claim of the two.
                assert f.flagged
                assert f.trade_ratio is not None or f.turnover_ratio is not None
    finally:
        conn.close()
    assert hashlib.sha256(store.COMMITTED_DB.read_bytes()).hexdigest() == before


def test_lab_promote_exits_2_and_writes_nothing_on_a_mis_shaped_control(tmp_path, monkeypatch):
    db, prereg_dir = tmp_path / "lab.sqlite", tmp_path / "prereg"
    c = store.connect(db)
    _benchmark(c)
    _method(c, "M0001", annual=0.15)
    _control_arm(c, "M0001", "R", trades=800, turnover=3.5)
    before = db.read_bytes()
    c.close()
    _with_control(monkeypatch)

    assert _cli(tmp_path, db, prereg_dir) == 2
    assert not prereg_dir.exists()
    assert db.read_bytes() == before


def _stub_full_run(monkeypatch, tmp_path, method_id: str, arms: list):
    """`lab run` all the way to its printing, with no method file, no store and no backtest.

    Extends `_stub_run` past the store pin: `preflight_data` returns None and `run_method` hands
    back the attributes `_run` reads off it. The verdict is the reason-carrying kind (D15's own
    bootstrap case), so no fold geometry is needed.

    The stub method carries `all_candidates`, because `_run`'s control-shape block reads the
    method's arms through `control_shape.for_method` -> this same `discover` -- the seam described
    at the top of this section. A bare `SimpleNamespace(id=...)` would raise `AttributeError`
    inside `_run` instead of printing the block.
    """
    import types

    from seer_engine import research
    from seer_engine.lab import runner

    _declare(monkeypatch, **{method_id: arms})
    monkeypatch.setattr(runner, "preflight", lambda *a, **k: None)
    monkeypatch.setattr(
        research, "load_store",
        lambda _path: types.SimpleNamespace(fingerprint="f" * 64, price_fingerprint=SAME_PRICES),
    )
    monkeypatch.setattr(runner, "preflight_data", lambda *a, **k: None)
    verdict = hardgate.FoldVerdict(
        method=method_id, bench_n=None, total=None, scored=None, won=None, majority=None,
        stable=None, picks_json="[]", summary="", reason="stubbed: no fold record in this test",
    )
    monkeypatch.setattr(
        runner, "run_method",
        lambda *a, **k: types.SimpleNamespace(ran=(), folds=None, verdict=verdict),
    )


def test_lab_run_prints_the_control_block_and_still_exits_zero(tmp_path, monkeypatch, capsys):
    """(D15), tested rather than quoted: the run ANNOTATES a handicapped control and completes.

    This is the decision, not an implementation detail. A run-time refusal would only spend method
    ids to say what `lab promote` already says, and a fresh lab has to be able to run before it
    has anything to compare -- so the block is loud and the exit code is 0.
    """
    from seer_engine.commands import lab as lab_cmd

    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _benchmark(c)
    _method(c, "M0099", annual=0.15)
    _control_arm(c, "M0099", "R", trades=800, turnover=3.5)
    c.close()

    _stub_full_run(monkeypatch, tmp_path, "M0099",
                   [_Arm("M0099-A", R_IDEA), _Arm("M0099-R", R_DRAW)])
    assert lab_cmd.run(argparse.Namespace(
        db=db, lab_command="run", method="M0099", store=tmp_path / "store", allow_coverage=0.8,
    )) == 0
    out = capsys.readouterr().out
    assert "Control shape:" in out
    assert "M0099-R" in out
    assert "outside" in out                  # the loud line fired
    assert "lab/hardgate.py, D17" in out     # and it names where the refusal lives


def test_lab_run_says_so_when_there_is_no_control_arm(tmp_path, monkeypatch, capsys):
    from seer_engine.commands import lab as lab_cmd

    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _benchmark(c)
    _method(c, "M0099", annual=0.15)
    c.close()

    _stub_full_run(monkeypatch, tmp_path, "M0099", [_Arm("M0099-A", R_IDEA)])
    assert lab_cmd.run(argparse.Namespace(
        db=db, lab_command="run", method="M0099", store=tmp_path / "store", allow_coverage=0.8,
    )) == 0
    assert "no control or placebo arm" in capsys.readouterr().out


# --------------------------------------------------------------------------- the mirror-pair block
#
# Insight 523: a rule run beside its own mirror proves the SIGNAL is real and says nothing about
# what ACTING on it costs, because both arms pay that cost equally and it cancels. `lab run`
# annotates that, beside the control-shape block and for the same reason (D15): the repair is an
# Amendment, which costs no method id, and the one moment it is cheap is before the write-up.
#
# The block is a FORWARDER over `dressing.survey`, so these tests pin the forwarding and the
# wording -- never the arithmetic, which `test_lab_dressing.py` owns.


def _mirror_config(**params) -> str:
    """A ``config_text`` in the shape `method.config_text` writes, for `dressing.fields_of`."""
    body = ",".join(f"{k}={v}" for k, v in params.items())
    return (
        "rules=TradeRules(id='monthly-hold-frac-gotrade',resize=True)\n"
        "allocator=<M0099>\n"
        f"params=FakeParams({body})\n"
    )


def _mirror_pair(conn, mid: str, *, annual_straight: float, annual_reversed: float) -> None:
    """Two arms of ``mid`` differing in exactly one reversing setting: `mirror` False -> True."""
    with conn:
        ns = store.insert_trials(conn, [
            _trial(method_id=mid, candidate_id=f"{mid}-GATE", config_digest=f"d-{mid}-gate",
                   config_text=_mirror_config(mirror="False"),
                   curve_json=_curve(_months(*DEV_SPAN), annual_straight)),
            _trial(method_id=mid, candidate_id=f"{mid}-MIRROR", config_digest=f"d-{mid}-mirror",
                   config_text=_mirror_config(mirror="True"),
                   curve_json=_curve(_months(*DEV_SPAN), annual_reversed)),
        ])
        stamp_provenance(conn, ns, price_fingerprint=SAME_PRICES)


def test_lab_run_names_a_reversed_pair_that_has_no_always_invested_arm(
    tmp_path, monkeypatch, capsys
):
    """The hole insight 523 measured, caught at the one moment the repair is still free.

    Of 28 reversed pairs across 23 methods recorded before this block existed, only six could be
    priced; the other 22 never registered the third arm, so their cost is unrecoverable from the
    record. The run has to say so, and it has to say the repair costs no method id -- a child
    that reads `lab run`'s output and not the skill is exactly the case this exists for.
    """
    from seer_engine.commands import lab as lab_cmd

    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _benchmark(c)
    _method(c, "M0099", annual=0.15)
    _mirror_pair(c, "M0099", annual_straight=0.18, annual_reversed=0.10)
    c.close()

    _stub_full_run(monkeypatch, tmp_path, "M0099",
                   [_Arm("M0099-A", R_IDEA), _Arm("M0099-GATE", R_IDEA),
                    _Arm("M0099-MIRROR", R_DRAW)])
    assert lab_cmd.run(argparse.Namespace(
        db=db, lab_command="run", method="M0099", store=tmp_path / "store", allow_coverage=0.8,
    )) == 0
    out = capsys.readouterr().out
    assert "Mirror pairs:" in out
    assert "M0099-GATE vs M0099-MIRROR" in out
    assert "cannot be priced" in out
    assert "no method id" in out          # the repair is an Amendment, and it is free
    assert "lab dressing M0099" in out    # and the report that says the rest


def test_lab_run_says_nothing_about_mirrors_when_no_arm_reverses_another(
    tmp_path, monkeypatch, capsys
):
    """The predicate that keeps the block off the 147 methods it does not apply to.

    A warning that fired on every stock screen would be wallpaper inside a week. It is structural
    -- two arms differing in exactly one reversing setting, read off recorded `config_text` and
    never off names -- which is 23 of the lab's 170 methods with dev trials, and falling, because
    the explore skill now asks for the third arm at design time.
    """
    from seer_engine.commands import lab as lab_cmd

    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _benchmark(c)
    _method(c, "M0099", annual=0.15)
    _control_arm(c, "M0099", "R", trades=250, turnover=1.1)
    c.close()

    _stub_full_run(monkeypatch, tmp_path, "M0099",
                   [_Arm("M0099-A", R_IDEA), _Arm("M0099-R", R_DRAW)])
    assert lab_cmd.run(argparse.Namespace(
        db=db, lab_command="run", method="M0099", store=tmp_path / "store", allow_coverage=0.8,
    )) == 0
    assert "Mirror pairs:" not in capsys.readouterr().out


def test_the_mirror_block_never_contradicts_lab_dressing(tmp_path, monkeypatch, capsys):
    """It forwards `dressing.survey` rather than re-deciding, so the two cannot drift.

    The temptation this closes is a second endpoint test living in `commands/lab.py`: dressing's
    bars were calibrated on the lab's ten always-invested arms and will move again when a stock
    book finally registers one. A copy would then say `unpriced` where the report says priced,
    and the run's output is the half a researcher actually reads.
    """
    from seer_engine.commands import lab as lab_cmd
    from seer_engine.lab import dressing

    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _benchmark(c)
    _method(c, "M0099", annual=0.15)
    _mirror_pair(c, "M0099", annual_straight=0.18, annual_reversed=0.10)
    c.close()

    _stub_full_run(monkeypatch, tmp_path, "M0099",
                   [_Arm("M0099-A", R_IDEA), _Arm("M0099-GATE", R_IDEA),
                    _Arm("M0099-MIRROR", R_DRAW)])
    assert lab_cmd.run(argparse.Namespace(
        db=db, lab_command="run", method="M0099", store=tmp_path / "store", allow_coverage=0.8,
    )) == 0
    out = capsys.readouterr().out

    c = store.connect(db)
    seen = dressing.survey(c, ["M0099"])
    c.close()
    assert len(seen.found) == 1
    assert len(seen.unpriced) == 1
    for d in seen.found:
        assert d.verdict in out


def test_lab_control_reports_every_arm_and_writes_nothing(tmp_path, monkeypatch, capsys):
    """Shape (A): N and the looks are printed either side, and the database bytes do not move."""
    from seer_engine.commands import lab as lab_cmd

    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _benchmark(c)
    _method(c, "M0001", family="a", annual=0.15)
    _control_arm(c, "M0001", "R", trades=800, turnover=3.5)
    _method(c, "M0002", family="b", annual=0.15)
    _control_arm(c, "M0002", "R", trades=252, turnover=1.08)
    n_before = store.dev_trial_count(c)
    looks_before = store.test_looks(c)
    c.close()
    before = db.read_bytes()

    _declare(
        monkeypatch,
        M0001=[_Arm("M0001-A", R_IDEA), _Arm("M0001-R", R_DRAW)],
        M0002=[_Arm("M0002-A", R_IDEA), _Arm("M0002-R", R_DRAW)],
    )

    rc = lab_cmd.run(argparse.Namespace(db=db, lab_command="control", method=[]))
    assert rc == 0
    out = capsys.readouterr().out
    assert "M0001-R" in out and "M0002-R" in out
    assert "refuse" in out and "ok" in out        # one of each, so the band is not refusing all
    assert f"recorded dev trials {n_before} -> {n_before}" in out
    assert f"test-window looks {looks_before} -> {looks_before}" in out
    assert db.read_bytes() == before

    rc = lab_cmd.run(argparse.Namespace(db=db, lab_command="control", method=["M0001"]))
    assert rc == 0
    one = capsys.readouterr().out
    assert "M0001-R" in one and "M0002-R" not in one

    assert lab_cmd.run(argparse.Namespace(db=db, lab_command="control", method=["M9999"])) == 2


# --- (D18): the arm that takes the money may not be the arm registered to be beaten ------------
#
# Same seam as (D17) above and for the same reason: `_declare` is what lets a synthetic arm's
# rationale be read at all. These tests turn on which arm `store.best_dev_eligible` names, which
# is MAR then `n`, so they move MAR -- `_control_arm` records at the fixture default and loses the
# tie-break to the book itself.

R_CONTROL = "Control: the same book with the brake taken out, nothing else changed"

# The nineteen dev-eligible methods whose pre-registered arm reads `control`, measured read-only
# on 2026-10-20 against this tree's committed lab. Named in (D18)'s own text.
CONTROL_PROMOTED: tuple[tuple[str, str], ...] = (
    ("M0033", "M0033-TV22-N21"), ("M0035", "M0035-CTRL"), ("M0044", "M0044-NOBRAKE"),
    ("M0047", "M0047-EQ"), ("M0076", "M0076-X-M-D"), ("M0083", "M0083-X-UP-D"),
    ("M0085", "M0085-EX-M"), ("M0101", "M0101-CTRL"), ("M0107", "M0107-HOST"),
    ("M0122", "M0122-CALM-EQ"), ("M0137", "M0137-EXP"), ("M0168", "M0168-CTRL"),
    ("M0169", "M0169-L20-SW"), ("M0187", "M0187-H3-SW"), ("M0193", "M0193-S2-SW"),
    ("M0202", "M0202-PLC1-HALF"), ("M0215", "M0215-CTRL"), ("M0223", "M0223-TOP20"),
    ("M0242", "M0242-R-H6"),
)

# The negative control, on real arms. Both of these pre-register a DOSE-RESPONSE rung, and both
# are methods the audit's refused fork (A) would have flipped to promotable -- so they are exactly
# the pair a careless widening of ROLE_CONTROL would catch. The rung IS the measurement (D17).
DOSE_PROMOTED: tuple[tuple[str, str], ...] = (
    ("M0174", "M0174-C40-SW"), ("M0179", "M0179-N40-SW"),
)


def _arm_row(conn, monkeypatch, mid: str, suffix: str, *, mar: float = 0.95, trades: int = 252,
             turnover: float = 1.08, annual: float = 0.15) -> None:
    """Record one more dev arm of ``mid`` AND make it the arm `lab promote` would pre-register.

    (D18) turns on exactly which arm `store.best_dev_eligible` names, so the arm has to be named
    rather than merely recorded. It is named the way every other `promoted_variant` test in this
    module names one -- by patching `store.best_dev_eligible` to the row -- and not by out-MARing
    the book, because this module's autouse fixture pins `DSR_POLICY` to `all-trials` and every
    synthetic trial here carries the same `sharpe`, so the dev-Sharpe variance is zero, `dsr_at`
    cannot invert a recorded DSR at the gate's N, and EVERY arm reads ineligible. A higher `mar`
    would therefore name nothing at all. The `mar` is still recorded, because the refusal's own
    argument is about what MAR rewards and a row that did not carry one would be a misleading
    fixture.

    The default shape -- 252 trades, 1.08 turnover against the book's 250 and 1.1 -- is inside
    `WARN_BAND`, so (D17) stays silent and only the clause under test can speak.
    """
    with conn:
        ns = store.insert_trials(conn, [_trial(
            method_id=mid, candidate_id=f"{mid}-{suffix}", config_digest=f"d-{mid}-{suffix}",
            mar=mar, trades=trades, turnover=turnover,
            curve_json=_curve(_months(*DEV_SPAN), annual),
        )])
        stamp_provenance(conn, ns, price_fingerprint=SAME_PRICES)
    row = conn.execute(
        "SELECT * FROM trials WHERE candidate_id = ?", (f"{mid}-{suffix}",)
    ).fetchone()
    monkeypatch.setattr(store, "best_dev_eligible", lambda _c, _m, **_k: row)


def _promote_the_book(conn, monkeypatch, mid: str = "M0001") -> None:
    """Name ``{mid}-A`` -- the book itself -- as the arm that would be pre-registered.

    Same seam and same reason as `_arm_row`: under this module's `all-trials` fixture nothing is
    eligible, so even the only arm a method holds has to be named explicitly.
    """
    row = conn.execute("SELECT * FROM trials WHERE candidate_id = ?", (f"{mid}-A",)).fetchone()
    monkeypatch.setattr(store, "best_dev_eligible", lambda _c, _m, **_k: row)


def test_the_module_records_the_promoted_arm_role_decision():
    """(D18) is argued where the other seventeen are, with its measurement and its live case."""
    doc = hardgate.__doc__ or ""
    assert "(D18)" in doc
    assert "M0202-PLC1-HALF" in doc                        # the live case, named
    assert "best_dev_eligible" in doc and "no role filter" in doc
    # The three the fold clauses already clear, stopped only by the kin rule -- the luck.
    assert "M0033" in doc and "M0035" in doc and "M0044" in doc
    assert "M0044-NOBRAKE" in doc
    # The fork the same audit refused, recorded beside the one it took.
    assert "M0174" in doc and "M0178" in doc and "walkforward.pick" in doc
    # Fails open, and says whose sentence that is.
    assert "absence is not evidence" in doc.lower()
    # The way back, and that it is free.
    assert "amendment" in doc and "costs no method id" in doc


def test_a_promotion_whose_variant_is_a_control_is_refused_and_quotes_the_rationale(
    conn, monkeypatch
):
    """M0202's shape: the highest-MAR eligible arm is the placebo, so the placebo takes the look."""
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)                    # M0001-A, the idea, MAR 0.8
    _arm_row(conn, monkeypatch, "M0001", "PLC1", mar=0.95)              # the placebo, higher MAR
    _declare(monkeypatch, M0001=[_Arm("M0001-A", R_IDEA), _Arm("M0001-PLC1", R_DRAW)])

    assert hardgate.promoted_variant(conn, "M0001") == "M0001-PLC1"
    with pytest.raises(store.LabError) as e:
        hardgate.check(conn, "M0001")
    said = str(e.value)
    assert "M0001-PLC1" in said
    assert "control arm" in said and "registered in order to beat it" in said
    assert "hash-drawn names" in said                      # the author's own sentence, quoted back
    assert "D18" in said
    assert "Nothing was written and no status moved" in said
    assert "There is no override" in said
    assert "amendment" in said and "costs no method id" in said


def test_a_control_arm_that_is_not_the_promoted_one_does_not_refuse(conn, monkeypatch):
    """The ordinary method: it holds a placebo and its idea out-MARs it. (D18) is silent.

    This is the half of the rule that matters most -- most of the lab holds a control arm, and a
    clause that refused all of them would be a stopped lab rather than a stricter one.
    """
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)                    # MAR 0.8
    _arm_row(conn, monkeypatch, "M0001", "PLC1", mar=0.50)              # the placebo, lower MAR
    _promote_the_book(conn, monkeypatch)                   # ...and the book out-MARs it
    _declare(monkeypatch, M0001=[_Arm("M0001-A", R_IDEA), _Arm("M0001-PLC1", R_DRAW)])

    assert hardgate.promoted_variant(conn, "M0001") == "M0001-A"
    hardgate.check(conn, "M0001")                          # returns: no refusal


def test_a_promoted_dose_rung_is_not_a_control(conn, monkeypatch):
    """(D17)'s dose-before-draw ordering, carried into this clause: the rung IS the measurement.

    `M0244-STALE30` is the live shape. A permanent false alarm on a correct arm is how a rule gets
    switched off, so the dose arms have to pass here as they pass the shape check.
    """
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    _arm_row(conn, monkeypatch, "M0001", "STALE30", mar=0.95)
    _declare(monkeypatch, M0001=[_Arm("M0001-A", R_IDEA), _Arm("M0001-STALE30", R_DOSE)])

    assert hardgate.promoted_variant(conn, "M0001") == "M0001-STALE30"
    hardgate.check(conn, "M0001")


def test_a_plain_treatment_arm_promotes_exactly_as_before(conn, monkeypatch):
    """A method whose only arm is the book itself: no role to object to, nothing refused."""
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    _promote_the_book(conn, monkeypatch)
    _declare(monkeypatch, M0001=[_Arm("M0001-A", R_PLAIN)])

    hardgate.check(conn, "M0001")


def test_an_arm_the_method_file_does_not_declare_does_not_refuse(conn, monkeypatch):
    """Fails OPEN, for (D16)'s reason: absence is not evidence.

    The recorded id is `M0001-A` and the file declares only `M0001-Z`, so the role cannot be read
    at all. A reader's limitation is not a verdict about a method, and the clauses below still run.
    """
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    _promote_the_book(conn, monkeypatch)
    _declare(monkeypatch, M0001=[_Arm("M0001-Z", R_DRAW)])

    assert hardgate.promoted_arm_role("M0001", "M0001-A") is None
    hardgate.check(conn, "M0001")


def test_a_method_with_no_file_does_not_refuse(conn, monkeypatch):
    """And deleting the file is not a way past the rule: `prereg` refuses a method with no file on
    its source sha long before this clause, so an empty answer here is a missing role, not a
    waiver."""
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    _promote_the_book(conn, monkeypatch)
    _declare(monkeypatch)                                   # discover() -> {}

    assert hardgate.promoted_arm_role("M0001", "M0001-A") is None
    hardgate.check(conn, "M0001")


def test_the_role_is_read_from_the_prose_and_never_from_the_id(conn, monkeypatch):
    """`control_shape`'s founding rule, asserted at the gate: `M0005-ALL-R`'s `-R` is a
    rank-weighting variant, not a control. An id-suffix rule would refuse this promotion."""
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    _arm_row(conn, monkeypatch, "M0001", "R", mar=0.95)
    _declare(monkeypatch, M0001=[
        _Arm("M0001-A", R_IDEA),
        _Arm("M0001-R", "The same composite with linear rank weights: does conviction pay"),
    ])

    assert hardgate.promoted_variant(conn, "M0001") == "M0001-R"
    hardgate.check(conn, "M0001")


def test_a_perfectly_shaped_control_is_still_a_control(conn, monkeypatch):
    """(D17) and (D18) ask different questions of one arm, and both have to be asked.

    A placebo drawn at exactly the book's trade count and turnover clears the shape band -- and is
    still the wrong thing to spend a counted look on.
    """
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    _arm_row(conn, monkeypatch, "M0001", "PLC1", mar=0.95, trades=250, turnover=1.1)
    _declare(monkeypatch, M0001=[_Arm("M0001-A", R_IDEA), _Arm("M0001-PLC1", R_DRAW)])

    assert not hardgate.mis_shaped_controls(conn, "M0001")   # 1.00x / 1.00x: (D17) is content
    with pytest.raises(store.LabError, match="D18"):
        hardgate.check(conn, "M0001")


def test_the_fold_clauses_still_speak_first(conn, monkeypatch):
    """Order inside `check`: evidence before identity.

    A control arm that also loses its own folds is refused by (D11b), which is the more basic thing
    wrong with it, and the researcher reads that sentence rather than this one.
    """
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    # promoted, and loses every fold
    _arm_row(conn, monkeypatch, "M0001", "PLC1", mar=0.95, annual=0.02)
    _declare(monkeypatch, M0001=[_Arm("M0001-A", R_IDEA), _Arm("M0001-PLC1", R_DRAW)])

    with pytest.raises(store.LabError) as e:
        hardgate.check(conn, "M0001")
    said = str(e.value)
    assert "(D11)" in said and "D18" not in said


def test_a_control_prefixed_rationale_is_a_control_here(conn, monkeypatch):
    """M0044's live shape -- "Control: M0036-BLEND re-stated under this allocator, no brake".

    Phase 1 widened `control_shape`'s vocabulary to the `Control:` prefix that most of the lab's
    control arms actually use; this is the gate asserting it reads one.
    """
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    _arm_row(conn, monkeypatch, "M0001", "NOBRAKE", mar=0.95)
    _declare(monkeypatch, M0001=[_Arm("M0001-A", R_IDEA), _Arm("M0001-NOBRAKE", R_CONTROL)])

    with pytest.raises(store.LabError, match="D18"):
        hardgate.check(conn, "M0001")


def test_lab_promote_exits_2_and_writes_nothing_when_the_variant_is_a_control(
    tmp_path, monkeypatch
):
    db, prereg_dir = tmp_path / "lab.sqlite", tmp_path / "prereg"
    c = store.connect(db)
    _benchmark(c)
    _method(c, "M0001", annual=0.15)
    _arm_row(c, monkeypatch, "M0001", "PLC1", mar=0.95)
    before = db.read_bytes()
    c.close()
    _declare(monkeypatch, M0001=[_Arm("M0001-A", R_IDEA), _Arm("M0001-PLC1", R_DRAW)])

    assert _cli(tmp_path, db, prereg_dir) == 2
    assert not prereg_dir.exists()
    assert db.read_bytes() == before


def test_the_nineteen_are_still_the_nineteen_or_have_moved_on(monkeypatch):
    """(D18)'s population, on the committed lab, allowed exactly two states and never neither.

    Each named method either still pre-registers the control arm (D18)'s text names, or has since
    amended an arm that out-MARs it -- the way back, working. Pinning only "still a control" would
    go red the day a method takes the remedy the refusal asks for, which is the wrong direction for
    a test to fail in.

    `store.COMMITTED_DB` opened `mode=ro` and never through `store.connect`, which migrates and so
    dirties the file on a read. The bytes are hashed either side. `DSR_POLICY` is put back to the
    lab's real default, because this module's autouse fixture pins it to the one its own synthetic
    rows were recorded under and the committed lab is not judged under that one.
    """
    from seer_engine.lab import npolicy

    if not store.COMMITTED_DB.exists():
        pytest.skip("no lab database")
    monkeypatch.setattr(store, "DSR_POLICY", npolicy.DEFAULT_POLICY)
    store._GATE_CACHE.clear()

    before = hashlib.sha256(store.COMMITTED_DB.read_bytes()).hexdigest()
    conn = sqlite3.connect(f"file:{store.COMMITTED_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        from seer_engine.lab import control_shape as cs

        for mid, named_arm in CONTROL_PROMOTED:
            if store.get_method(conn, mid) is None:
                pytest.skip(f"{mid} is not in this tree's lab")
            arm = hardgate.promoted_variant(conn, mid)
            if arm is None:
                pytest.skip(f"{mid} has no eligible dev variant in this tree")
            role = hardgate.promoted_arm_role(mid, arm)
            if role is None:
                pytest.skip(f"{mid} has no method file in this tree")
            if arm == named_arm:
                assert role[0] == cs.ROLE_CONTROL, f"{mid}: {arm} no longer reads as a control"
            else:
                # It moved. The only acceptable direction is away from a control arm.
                assert role[0] != cs.ROLE_CONTROL, (
                    f"{mid} now pre-registers {arm}, a different control arm"
                )
    finally:
        conn.close()
    assert hashlib.sha256(store.COMMITTED_DB.read_bytes()).hexdigest() == before


def test_a_dose_rung_on_the_committed_lab_is_not_refused(monkeypatch):
    """The negative control, on real arms rather than on a fixture's prose.

    M0174 and M0179 pre-register a dose-response rung. They are also the two methods the audit's
    refused fork (A) would have flipped to promotable, so they are precisely the pair that a
    widened `ROLE_CONTROL` would sweep up by accident -- and a permanent false alarm on a correct
    arm is how a rule gets switched off (D17). Nine of the 78 pre-register a rung; none of them may
    be refused here.

    Same read-only discipline as the test above: `mode=ro`, never `store.connect`, bytes hashed
    either side, and `DSR_POLICY` put back to the lab's real default.
    """
    from seer_engine.lab import control_shape as cs
    from seer_engine.lab import npolicy

    if not store.COMMITTED_DB.exists():
        pytest.skip("no lab database")
    monkeypatch.setattr(store, "DSR_POLICY", npolicy.DEFAULT_POLICY)
    store._GATE_CACHE.clear()

    before = hashlib.sha256(store.COMMITTED_DB.read_bytes()).hexdigest()
    conn = sqlite3.connect(f"file:{store.COMMITTED_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        for mid, named_arm in DOSE_PROMOTED:
            if store.get_method(conn, mid) is None:
                pytest.skip(f"{mid} is not in this tree's lab")
            arm = hardgate.promoted_variant(conn, mid)
            if arm != named_arm:
                pytest.skip(f"{mid} now pre-registers {arm}, not {named_arm}")
            role = hardgate.promoted_arm_role(mid, arm)
            if role is None:
                pytest.skip(f"{mid} has no method file in this tree")
            assert role[0] == cs.ROLE_DOSE, f"{mid}: {arm} reads {role[0]}, not a dose rung"
            assert role[0] != cs.ROLE_CONTROL
    finally:
        conn.close()
    assert hashlib.sha256(store.COMMITTED_DB.read_bytes()).hexdigest() == before


def test_this_rule_retires_no_promotion_that_already_happened():
    """(D3): a pre-registration is a promise, and `check` is silent for any status but
    `dev-eligible`. None of the nineteen is `promoted`, so nothing already committed to is
    re-judged -- asserted rather than reasoned about, because a rule that retroactively unpicked a
    promise would be the worst available outcome of this edit."""
    if not store.COMMITTED_DB.exists():
        pytest.skip("no lab database")
    before = hashlib.sha256(store.COMMITTED_DB.read_bytes()).hexdigest()
    conn = sqlite3.connect(f"file:{store.COMMITTED_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        for mid, _arm in CONTROL_PROMOTED:
            row = store.get_method(conn, mid)
            if row is None:
                continue
            assert str(row["status"]) != "promoted", mid
    finally:
        conn.close()
    assert hashlib.sha256(store.COMMITTED_DB.read_bytes()).hexdigest() == before


# ------------------------------------------------------------------ the era edge names its arm
#
# F5 of the 2026-10-20 fold-selector audit. The column reported whichever arm had the highest MAR
# over 2009-2015 itself; the buy signal spends its recommendation on the arm `lab promote` would
# pre-register. Over the committed lab those were different arms for 39 of 74 dev-eligible
# methods and disagreed on sign for 18. Both directions are pinned here, because the defect is
# not that the old number was generous -- it was wrong in both directions.

_ERA = (date(2009, 1, 1), date(2015, 10, 16))


def _broken(months: list[date], annual: float, when: date, loss: float) -> str:
    """``_curve``'s trend with one PERMANENT fall of ``loss`` at ``when``, never recovered.

    Unlike ``_dipped``, which leaves the book back on trend so only its drawdown moves, this
    moves the slice's CAGR for every slice that contains ``when`` and for none that does not.
    That is how an arm can win the folds outside one era and still trail the benchmark across an
    era that contains its one bad year -- the shape the era-edge condition exists to catch, and
    the only shape in which that condition, rather than a fold count, is what refuses.
    """
    out, v = [], 1.0
    for d in months:
        out.append([d.isoformat(), round(v * (1.0 - loss) if d >= when else v, 8)])
        v *= (1.0 + annual) ** (1.0 / 12.0)
    return json.dumps(out)


def _dipped(months: list[date], annual: float, dip: date, depth: float, recover: int = 6) -> str:
    """``_curve``'s trend with one temporary fall of ``depth`` beginning at ``dip``.

    The book leaves the fall exactly back on trend, so the slice's CAGR is the trend's and only its
    max drawdown -- and therefore its MAR -- moves. That is how an arm can earn the most over an
    era and still not be the era's highest-MAR arm, which is the whole shape of M0072.
    """
    def idx(d: date) -> int:
        return d.year * 12 + d.month

    out, v = [], 1.0
    for d in months:
        f = 1.0
        if idx(d) >= idx(dip):
            k = idx(d) - idx(dip)
            if k < recover:
                f = 1.0 - depth * (1.0 - k / recover)
        out.append([d.isoformat(), round(v * f, 8)])
        v *= (1.0 + annual) ** (1.0 / 12.0)
    return json.dumps(out)


def _wf_args(db):
    return argparse.Namespace(
        db=db, lab_command="walkforward", method=[], min_train_years=None, eval_years=None,
    )


def test_the_era_column_reports_the_promoted_variant_and_keeps_the_hindsight_arm(
    tmp_path, capsys, monkeypatch
):
    """M0197's live shape: the hindsight arm is positive, the promoted arm is not.

    `M0001-A` grows 15% a year and wins every fold; the hindsight column names it at +7.0%, and a
    buy signal fired on that number until 2026-10-20. The arm that would be pre-registered is
    `M0001-Z`, and that is what the signal is now handed.

    Z grows 10% a year -- comfortably past the 8% benchmark -- and loses 35% permanently in June
    2010. So it wins three of its four folds on its own curve and clears the own-arm clause added
    on 2026-10-21, and the era edge is still what refuses it: 2009-2015 is the one era that holds
    its bad year, and across it Z trails at -4.9 pts. Before that clause existed Z was a flat 2%
    arm, which lost every fold; it would now be caught one condition earlier and this test would
    no longer reach the condition it is about.
    """
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _benchmark(c)
    _method(c, "M0001", annual=0.15)
    _variant(c, "M0001", "Z", curve_json=_broken(
        _months(*DEV_SPAN), 0.10, date(2010, 6, 30), 0.35), annual=0.10)
    z = c.execute("SELECT * FROM trials WHERE candidate_id = 'M0001-Z'").fetchone()
    c.close()
    monkeypatch.setattr(store, "best_dev_eligible", lambda _c, _m, **_k: z)

    from seer_engine.commands import lab as lab_cmd

    assert lab_cmd.run(_wf_args(db)) == 0
    out = capsys.readouterr().out
    row = next(line for line in out.splitlines() if line.strip().startswith("M0001"))
    assert "4.9%" in row and "+7.0%" in row          # promoted left, hindsight right
    assert row.index("4.9%") < row.index("+7.0%")
    assert "3 of 4" in row                           # the promoted arm cleared the own-arm clause
    assert "negative 2009-2015 edge on the variant that would be promoted" in row
    # ...and the number it refuses on carries its own scale, so nobody reads -4.9 as settled.
    assert "SE 5.9, indistinguishable from zero" in row
    assert "No buy signal" in out
    assert "(hindsight)" in out
    assert "Nothing was recorded. No research store was opened." in out


def test_the_era_column_can_release_a_method_the_hindsight_arm_was_suppressing(
    tmp_path, capsys, monkeypatch
):
    """M0072's live shape, and the reason this is a correction rather than a tightening.

    `M0001-A` earns 15% a year through the era but falls 40% inside it, so its era MAR is 0.38;
    `M0001-Z` creeps along at 2% and never falls, so its era MAR is infinite and it is the
    hindsight arm at -6.0%. A is what `lab promote` would pre-register, and it reads +7.0%. The
    old column refused this method on an arm nobody would have traded.

    A is named the way every other `promoted_variant` test in this module names one -- by patching
    `store.best_dev_eligible` -- and not by out-MARing Z: this module's autouse fixture pins
    `DSR_POLICY` to `all-trials` and every synthetic trial carries the same `sharpe`, so the
    dev-Sharpe variance is zero and no arm is eligible at all. On the real lab the ranking does
    the naming; here the ranking has nothing to rank.
    """
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _benchmark(c)
    _method(c, "M0001", curve_json=_dipped(_months(*DEV_SPAN), 0.15, date(2013, 3, 31), 0.40))
    _variant(c, "M0001", "Z", annual=0.02)
    a = c.execute("SELECT * FROM trials WHERE candidate_id = 'M0001-A'").fetchone()
    c.close()
    monkeypatch.setattr(store, "best_dev_eligible", lambda _c, _m, **_k: a)

    from seer_engine.commands import lab as lab_cmd

    assert lab_cmd.run(_wf_args(db)) == 0
    out = capsys.readouterr().out
    row = next(line for line in out.splitlines() if line.strip().startswith("M0001"))
    assert "+7.0%" in row and "6.0%" in row
    assert row.index("+7.0%") < row.index("6.0%")
    assert "*** BUY SIGNAL: 1 distinct book from 1 method ***" in out
    assert "2009-2015 edge on the promoted variant +7.0 pts" in out
    # and the two arms are named underneath, because the signs disagree
    note = next(line for line in out.splitlines() if "hindsight M0001-Z" in line)
    assert "promoted M0001-A" in note


def test_a_method_with_no_promotable_variant_shows_a_dash_and_cannot_fire(
    tmp_path, capsys, monkeypatch
):
    """Five dev-eligible methods are in this state today (M0243 joined them when N reached 170).
    The hindsight column still carries their number, so no row loses information; the signal gets
    None for both the promoted arm's fold record and its era edge, and refuses on the first --
    which since 2026-10-21 is the fold record."""
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _benchmark(c)
    _method(c, "M0001", annual=0.15)
    c.close()
    monkeypatch.setattr(store, "best_dev_eligible", lambda _c, _m, **_k: None)

    from seer_engine.commands import lab as lab_cmd

    assert lab_cmd.run(_wf_args(db)) == 0
    out = capsys.readouterr().out
    row = next(line for line in out.splitlines() if line.strip().startswith("M0001"))
    assert "+7.0%" in row                               # the hindsight arm is still reported
    assert "no variant would be promoted" in row
    assert "No buy signal" in out


# The firing set on the committed lab, before and after 2026-10-20. Pinned because the correction
# is NOT one-way and that is the thing most easily lost: two methods stop firing and one starts.
# A test that only pinned the suppressions would let a later edit quietly re-break M0072 while
# still reading green.
BUY_SIGNAL_BEFORE: frozenset[str] = frozenset({"M0092", "M0197", "M0243", "M0258"})
BUY_SIGNAL_AFTER: frozenset[str] = frozenset({"M0072", "M0092", "M0258", "M0284"})
# (2026-10-23) M0284 joined, and it is the cleanest possible instance of what this block exists
# to collapse: its promoted arm's curve is byte-identical to M0072's -- trials 283, 914, 934 and
# 952 share one total return to fourteen digits, 1208 trades, the same fall and the same curve
# hash under four config digests. The header still says ONE book, which is the assertion that
# matters; the method count moved from three to four. Sera declined the look it fired, because
# the 2009-2015 edge it fired on reverses to -0.1 pts on the survivorship-check store.


def test_the_buy_signal_fires_on_the_promoted_arm_and_the_set_moved_both_ways(
    tmp_path, capsys, monkeypatch
):
    """`lab walkforward` over the committed lab names exactly M0072, M0092, M0258 and M0284.

    M0197 and M0243 stopped: each fired on an arm that is not the one `lab promote` would
    pre-register, and each of those promoted arms reads NEGATIVE over 2009-2015 -- the one era
    the condition exists to examine. M0072 started: its hindsight arm reads -1.09 pts and its
    promoted arm +2.26, so the old column was suppressing a true positive. Both directions are
    asserted, because "the fix makes the lab stricter" is the false summary of this change.

    The committed lab is COPIED first and the command run against the copy: a lab command migrates
    its database on connect, so even a read dirties the real file. The real file's bytes are
    hashed either side to prove it. `DSR_POLICY` goes back to the lab's real default, because this
    module's autouse fixture pins it to the one its own synthetic rows were recorded under.
    """
    import shutil

    from seer_engine.lab import npolicy

    if not store.COMMITTED_DB.exists():
        pytest.skip("no lab database")
    monkeypatch.setattr(store, "DSR_POLICY", npolicy.DEFAULT_POLICY)
    store._GATE_CACHE.clear()

    before = hashlib.sha256(store.COMMITTED_DB.read_bytes()).hexdigest()
    db = tmp_path / "lab-copy.sqlite"
    shutil.copy(store.COMMITTED_DB, db)

    from seer_engine.commands import lab as lab_cmd

    assert lab_cmd.run(_wf_args(db)) == 0
    out = capsys.readouterr().out
    assert hashlib.sha256(store.COMMITTED_DB.read_bytes()).hexdigest() == before

    # (2026-10-21) The block is one entry per distinct BOOK now, with the other names and their
    # own reasons printed underneath -- insight 529: these three ids are one strategy and three
    # rows read as three independent reasons to spend money. Every method that fires is still
    # named and still carries its five-condition sentence, so this parse reads both shapes: a
    # lead line `M0072: cleared all 5...` and an `M0092 -- written as a version of M0072` line.
    block = out.split("*** BUY SIGNAL", 1)
    fired = set()
    if len(block) == 2:
        for line in block[1].splitlines():
            head = line.strip().split(":", 1)[0].split(" ", 1)[0]
            if head.startswith("M") and head[1:].isdigit():
                fired.add(head)

    # The collapse itself, pinned: three method ids, ONE book, and the header says both numbers.
    assert "*** BUY SIGNAL: 1 distinct book from 4 methods ***" in out
    assert out.count("the same book under another name") == 1

    assert fired == set(BUY_SIGNAL_AFTER), (
        f"the buy signal now names {sorted(fired)}, not {sorted(BUY_SIGNAL_AFTER)}"
    )
    # the two false alarms are gone...
    assert not (fired & (BUY_SIGNAL_BEFORE - BUY_SIGNAL_AFTER)), "a suppressed false alarm is back"
    # ...and the true positive the old column was hiding is present. This half is the one a
    # one-way reading of the change would drop.
    assert "M0072" in fired, "M0072 is the true positive the hindsight column was suppressing"
    assert "M0072" not in BUY_SIGNAL_BEFORE

    # (2026-10-21) The own-arm fold majority, BUY_CONDITIONS[3]. The set above did NOT move when
    # it was added, and that is the assertion worth keeping: each of the three wins its folds on
    # the promoted arm ALONE, not merely on whatever variant each training slice happened to name.
    reasons = [ln for ln in block[1].splitlines() if "cleared all 5" in ln]
    assert len(reasons) == len(BUY_SIGNAL_AFTER), "a collapsed name lost its own reason"
    for line in reasons:
        assert "promoted arm 3 of 4 folds" in line, line
        assert "SE " in line and "indistinguishable from zero" in line, line

    # ...and M0243, the one verdict the clause moved, is refused by it. Two clauses can speak for
    # an absent arm -- it has no fold record of its own AND no era edge -- and since 2026-10-21
    # the fold clause is asked first. Either way the refusal must name the promoted arm, and
    # M0243 must never be in `fired`: pinned both ways so a later edit cannot re-break one half
    # while reading green.
    # (2026-10-23) The clause moved, and NOT because M0243 changed. Its best arm sits on the luck
    # bar: measured at 0.898278 on the pre-batch database at N=181 and 0.900449 on this one at
    # N=185, with the bar at 0.90. Adding four unrelated methods (a calm-stock mix, a volume
    # ladder, a re-weighting grid, a trend vote) moved it across, upward, even though a higher N
    # should make the bar harder -- the score reads the whole curve population's resemblance, not
    # N alone, and that moved from 0.643577 to 0.644004. So M0243 now HAS a promotable arm and is
    # refused by the fold clause instead of the absent-arm clause. Journal entry 579.
    #
    # Pinning one exact sentence here pins the lab's borderline population, which any later batch
    # re-rolls. What this test actually means to guarantee is in its own docstring: M0243 must
    # never fire, and whichever clause refuses it must speak about the arm that would be promoted.
    # Both clauses are asserted as acceptable, so the guarantee survives the next batch.
    m0243 = next(ln for ln in out.splitlines() if ln.strip().startswith("M0243 "))
    assert "M0243" not in fired
    assert (
        "no variant would be promoted" in m0243          # absent-arm clause
        or "the variant that would be promoted" in m0243  # fold clause, on its own curve
    ), m0243


def test_the_era_edge_carries_the_noise_scale_the_margin_study_measured(tmp_path, monkeypatch):
    """`era_edge_se` on the committed lab reproduces
    docs/plans/2026-10-21-gate-era-edge-margin-finding.md, to the tenth of a point it quotes.

    That document is why there is no margin: every candidate threshold is a quarter to two-thirds
    of one standard error, and the defensible one refuses the whole lab. An analysis nobody can
    reproduce cannot carry that weight, so the four numbers it leans on are pinned here against
    the real curves -- M0029 at SE 4.2 with a 95% interval of [-8.1, +8.5] around +0.22, and the
    three it is compared with. Same copy-first discipline as the test above: a lab command
    migrates its database on connect, so the committed file is hashed either side.
    """
    import shutil
    from datetime import date as _date

    from seer_engine.commands import lab as lab_cmd
    from seer_engine.lab import npolicy
    from seer_engine.lab import walkforward as wf

    if not store.COMMITTED_DB.exists():
        pytest.skip("no lab database")
    monkeypatch.setattr(store, "DSR_POLICY", npolicy.DEFAULT_POLICY)
    store._GATE_CACHE.clear()

    before = hashlib.sha256(store.COMMITTED_DB.read_bytes()).hexdigest()
    db = tmp_path / "lab-copy.sqlite"
    shutil.copy(store.COMMITTED_DB, db)
    conn = store.connect(db)
    try:
        rows = list(conn.execute(
            "SELECT n, method_id, candidate_id, start, end, curve_json FROM trials "
            "WHERE window = 'dev' AND curve_json IS NOT NULL"
        ))
        import json as _json

        def curve_of(row):
            return [(_date.fromisoformat(d), float(v)) for d, v in _json.loads(row["curve_json"])]

        bench = curve_of(next(r for r in rows if r["candidate_id"] == "REF-SPY-HOLD"))
        # The arms the study names. M0029's is its only arm; the other three are the arms
        # `best_dev_eligible` named for it, which is the column the gate reads since D18.
        expected = {
            "M0029-B70-RAW-FRAC": (+0.22, 4.2),
            "M0021-B70-RAW": (-0.17, 4.2),
            "M0072-Z2-RAWRANK": (+2.26, 3.0),
            "M0092-SQRT-CAP10": (+1.73, 3.0),
        }
        for cid, (edge_pts, se_pts) in expected.items():
            row = next(r for r in rows if r["candidate_id"] == cid)
            curve = curve_of(row)
            dep = {row["candidate_id"]: hardgate.trial_deposits(conn, row, curve)}[cid]
            edge = wf.era_edge(curve, bench, *lab_cmd.HIGH_COVERAGE, dep)
            se = wf.era_edge_se(curve, bench, *lab_cmd.HIGH_COVERAGE, dep)
            assert edge * 100 == pytest.approx(edge_pts, abs=0.05), cid
            assert se * 100 == pytest.approx(se_pts, abs=0.05), cid
            # and every one of them is reported as indistinguishable from zero, which is the
            # finding rather than a quirk of the phrasing.
            assert "indistinguishable from zero" in wf.describe_era_edge(edge, se), cid
    finally:
        conn.close()
    assert hashlib.sha256(store.COMMITTED_DB.read_bytes()).hexdigest() == before

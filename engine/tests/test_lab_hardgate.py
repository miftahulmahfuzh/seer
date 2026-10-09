"""The hard gate (lab/hardgate.py): the fold rule, the kin walk, and the refusal at promote.

Every test builds its own temp lab database. The real one has no promotable method, and these
tests must keep passing on the day it does.
"""

from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from decimal import Decimal
from math import comb

import numpy as np
import pytest

from labkit import LAB_PRICE_FINGERPRINT, stamp_provenance
from seer_engine.backtest import regime
from seer_engine.lab import hardgate, store
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

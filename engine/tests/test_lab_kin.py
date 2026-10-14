"""``hardgate.kin_matrix`` and ``lab kin``: every variant's own number, not only the best one.

The gate's ``behavioural_kin`` keeps ONE ``Twin`` per test-failed method -- the strongest
correlator across the method's variants -- which is exactly right for refusing a promotion and
exactly wrong for reading a particular variant's resemblance. A variant that is not the strongest
has no number in the gate's output at all.

MEASURED 2026-10-14, and the reason this module exists: M0133's 40-name arm inherited its 20-name
sibling's refusal. Its own correlation had never been computed, and it was the one arm whose worst
fall stayed under the owner's bar on the survivorship store -- the single configuration that could
have been funded, barred on a number measured from a different book. Obtaining it cost a whole
cycle, and the figure was in the recorded curves the entire time.

These tests pin the two properties that make ``kin_matrix`` trustworthy as the gate's companion:
it reports EVERY pair, and on the pairs the gate does report it agrees with the gate exactly. A
divergence between them would be worse than having no command at all, because the number would
look authoritative and refuse differently.
"""

from __future__ import annotations

import argparse

import pytest

from seer_engine.commands import lab as lab_cmd
from seer_engine.lab import hardgate, store

from test_lab_hardgate import (  # noqa: F401 -- fixtures are used by name
    DEV_SPAN,
    SAME_PRICES,
    _IDEA_A,
    _IDEA_B,
    _NOISE,
    _at_the_policy_these_fixtures_were_recorded_under,
    _benchmark,
    _method,
    _months,
    _moving,
    _moving_benchmark,
    _tested,
    _trial,
)
from labkit import stamp_provenance


@pytest.fixture()
def conn(tmp_path):
    """A fresh lab. Defined here rather than imported: importing the fixture by name would
    shadow every ``conn`` parameter below and ruff reads that as a redefinition (F811)."""
    c = store.connect(tmp_path / "lab.sqlite")
    yield c
    c.close()


def _a_lab_with_two_failed_books(conn) -> None:
    """Two test-failed books with the looks they spent, and one live method with two variants.

    The live method's variants are built to land on OPPOSITE sides of the bar on purpose: one
    copies the first failed book's idea (so it is kin), the other carries an unrelated idea (so it
    is not). That is the whole case this command exists for -- the gate would report only the
    first, and the second's own number would be unreadable.
    """
    _moving_benchmark(conn)
    _method(conn, "M0002", family="stock-momentum-risk-managed", status="test-failed",
            curve_json=_moving(_months(*DEV_SPAN), _IDEA_A))
    _tested(conn, "M0002")
    _method(conn, "M0003", family="stock-long-term-reversal", status="test-failed",
            curve_json=_moving(_months(*DEV_SPAN), _IDEA_B))
    _tested(conn, "M0003")
    _method(conn, "M0010", family="stock-updown-asymmetry",
            curve_json=_moving(_months(*DEV_SPAN), _IDEA_A, _NOISE))
    # A SECOND variant of the same method, carrying an unrelated idea. The gate will report only
    # whichever of the two correlates best with each failed book; this one's own number is the
    # thing that was unreadable before this module existed.
    with conn:
        ns = store.insert_trials(conn, [_trial(
            method_id="M0010", candidate_id="M0010-B", config_digest="d-M0010-B",
            curve_json=_moving(_months(*DEV_SPAN), _IDEA_B, _NOISE),
        )])
        stamp_provenance(conn, ns, price_fingerprint=SAME_PRICES)


def test_every_pair_is_reported_not_only_the_best(conn):
    """One row per (dev variant x test-failed tested variant), which is what the gate omits."""
    _a_lab_with_two_failed_books(conn)
    pairs = hardgate.kin_matrix(conn, "M0010")
    failed = {p.failed_id for p in pairs}
    variants = {p.candidate_id for p in pairs}
    assert failed == {"M0002", "M0003"}, failed
    assert variants == {"M0010-A", "M0010-B"}, variants
    assert len(pairs) == len(failed) * len(variants), (
        f"{len(pairs)} pairs for {len(variants)} variant(s) x {len(failed)} failed book(s): "
        "kin_matrix must report the whole grid, never a per-method best"
    )


def test_it_agrees_with_the_gate_on_every_pair_the_gate_reports(conn):
    """The companion must never disagree with the rule it explains. This is the load-bearing one."""
    _a_lab_with_two_failed_books(conn)
    pairs = hardgate.kin_matrix(conn, "M0010")
    for twin in hardgate.behavioural_kin(conn, "M0010"):
        mine = [
            p for p in pairs
            if p.failed_id == twin.failed_id and p.candidate_id == twin.candidate_id
        ]
        assert len(mine) == 1, f"no single pair for {twin.failed_id}/{twin.candidate_id}"
        assert mine[0].correlation == pytest.approx(twin.correlation), (
            f"{twin.candidate_id} vs {twin.failed_id}: kin_matrix reads "
            f"{mine[0].correlation}, the gate reads {twin.correlation}"
        )
        assert mine[0].crosses, "the gate only returns a Twin at or above the bar"


def test_the_best_pair_per_failed_book_is_exactly_the_gates_twin(conn):
    """Reducing the matrix the way the gate reduces it reproduces the gate's own answer."""
    _a_lab_with_two_failed_books(conn)
    pairs = hardgate.kin_matrix(conn, "M0010")
    best: dict[str, hardgate.KinPair] = {}
    for p in pairs:
        if not p.crosses:
            continue
        if p.failed_id not in best or (p.correlation or 0) > (best[p.failed_id].correlation or 0):
            best[p.failed_id] = p
    twins = {t.failed_id: t for t in hardgate.behavioural_kin(conn, "M0010")}
    assert set(best) == set(twins), (set(best), set(twins))
    for fid, p in best.items():
        assert p.candidate_id == twins[fid].candidate_id
        assert p.correlation == pytest.approx(twins[fid].correlation)


def test_crosses_is_the_bar_and_nothing_else(conn):
    """``crosses`` is the only field the gate would act on, so it must track KIN_CORRELATION."""
    _a_lab_with_two_failed_books(conn)
    for p in hardgate.kin_matrix(conn, "M0010"):
        expected = p.correlation is not None and p.correlation >= hardgate.KIN_CORRELATION
        assert p.crosses is expected, (p.candidate_id, p.failed_id, p.correlation)


def test_an_unmeasurable_pair_is_none_and_never_kin(conn):
    """Too few shared months is 'not measured', which must never read as clean-by-omission."""
    _a_lab_with_two_failed_books(conn)
    pairs = hardgate.kin_matrix(conn, "M0010")
    for p in pairs:
        if p.correlation is None:
            assert not p.crosses, "an unmeasured pair must never count as kin"


def test_a_lab_with_no_failed_book_returns_nothing(conn):
    """Empty, not an error: a lab that has never spent a look has no kin to measure."""
    _benchmark(conn)
    _method(conn, "M0010", status="dev-eligible")
    assert hardgate.kin_matrix(conn, "M0010") == ()


def test_an_unknown_method_refuses(conn):
    _benchmark(conn)
    with pytest.raises(store.LabError, match="no method M9999"):
        hardgate.kin_matrix(conn, "M9999")


def test_the_command_writes_nothing_and_mints_no_id(conn, capsys):
    """The post-run truth, which is the stronger statement: N and the looks are equal after."""
    _a_lab_with_two_failed_books(conn)
    before = (store.dev_trial_count(conn), store.test_looks(conn))
    methods_before = len(store.all_methods(conn)) if hasattr(store, "all_methods") else None

    rc = lab_cmd._kin(conn, argparse.Namespace(method=["M0010"], all=True))

    assert rc == 0
    assert (store.dev_trial_count(conn), store.test_looks(conn)) == before
    if methods_before is not None:
        assert len(store.all_methods(conn)) == methods_before, "kin must mint no method id"
    out = capsys.readouterr().out
    assert "M0010" in out
    assert f"{hardgate.KIN_CORRELATION:.2f}" in out, "the bar must be printed beside the numbers"
    assert "Nothing was written and no method id was minted." in out

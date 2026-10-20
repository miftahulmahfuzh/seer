"""M0208's two re-drawn controls, ``M0208-CGO-N20-PLC`` and ``-PLC2``: the free guards.

A dedicated module rather than more cases inside ``test_lab_control_draw``, which belongs to the
pilot phase and is being extended by four sibling sessions in the same checkout at the same time.
Everything here is an import-time property of the method file -- how D17 classifies the new arm,
which arm it resolves to, what it declares it supersedes, that it minted no params dataclass and
moved no recorded digest, and that its widened lookback still fits the smoke fixture.

**What this module deliberately does not claim.** ``labkit.smoke_market`` gives 473 sessions and
``overhangs`` needs 780 before it scores anything, so on the fixture ``scored`` returns ``{}``,
``_targets`` falls straight through to ``_book(..., (), ...)`` and neither the matched draw nor
the shadow replay above it is ever exercised -- which is already true of all four recorded M0208
arms. The draw's arithmetic is proved session by session in ``test_lab_control_draw``, the
replay's in ``test_lab_control_draw_shadow``; the only evidence that either matched *this* book's
shape is the recorded ``lab control M0208`` reading after the run.
"""

from __future__ import annotations

from dataclasses import fields
from datetime import date

from seer_engine.lab import control_draw as cd
from seer_engine.lab import control_shape as cs
from seer_engine.lab.hardgate import _INGREDIENT
from seer_engine.lab.method import config_digest, config_text
from seer_engine.lab.methods import m0208_capital_gains_overhang as m0208
from seer_engine.strategies.f_factor import factor_lookback

SMOKE_BARS = 473  # labkit.SMOKE_FIRST through DEV_END; the lookback cut every lab method clears
NEW = "M0208-CGO-N20-PLC"
OLD = "M0208-HASH-N20"
TARGET = "M0208-CGO-N20"
SHADOW = "M0208-CGO-N20-PLC2"

# The four digests trials 677-680 hold, read read-only from the committed lab on 2026-10-19.
RECORDED = {
    "M0208-CGO-N20": "13d7396048e9",
    "M0208-CGO-N40": "37badf26e71f",
    "M0208-CGO-LOW-N20": "12d558b814a4",
    "M0208-HASH-N20": "b9a9daff33d2",
}


def _arm(cid: str):
    return next(c for c in m0208.METHOD.all_candidates() if c.id == cid)


def test_the_new_arm_reads_as_a_placebo_on_the_book_it_means_to_control():
    """D17 classifies by prose and it tests dose BEFORE draw, so an arm worded as a dose-response
    one would carry no ratio at all and its refusal would vanish with the handicap still in place.
    That is gaming the check (plan invariant 3) and this is the test that forbids it."""
    arms = list(m0208.METHOD.all_candidates())
    new = _arm(NEW)
    text = new.rationale.lower()
    assert cs.kind_of(new) == cs.KIND_PLACEBO
    assert any(m in text for m in cs.DRAW_MARKERS)
    assert not any(m in text for m in cs.DOSE_MARKERS)
    assert cs.resolve_target(new, arms) == (TARGET, cs.RUNG_STEM)


def test_the_old_placebos_resolution_is_exactly_what_it_was():
    """``HASH-N20``'s stem is ``M0208-HASH``, which names no arm, so it falls to
    ``first-declared``. The new arm is a placebo and is excluded from ``_eligible_targets``, so
    its arrival moves no existing finding -- which is what makes this amendment additive."""
    arms = list(m0208.METHOD.all_candidates())
    assert cs.resolve_target(_arm(OLD), arms) == (TARGET, cs.RUNG_FIRST)


def test_the_new_allocator_is_a_new_id_and_names_no_ingredient():
    r"""``hardgate._INGREDIENT`` is ``<(M\d{4})>``, so ``<M0208-A1>`` matches nothing and D12's
    ingredient map is exactly what it was. A four-digit id would have made this arm declare its
    own method an ingredient of itself."""
    assert m0208.MATCHED.id == "M0208-A1"
    assert m0208.OVERHANG.id == "M0208"
    assert _INGREDIENT.findall("allocator=<M0208-A1>") == []


def test_the_matched_draw_reaches_back_one_extra_month_and_still_fits_the_fixture():
    """Plan invariant 11: the slack an allocator that reads at the previous decision adds is
    ``control_draw.PREVIOUS_DECISION_BARS`` through ``lookback_for``, never a number guessed per
    file. It costs this arm no window -- it declares only SPY, whose store history opens in 1993,
    and ``candidate_window`` floors a member-reading candidate at ``MEMBERSHIP_START``."""
    p = _arm(NEW).params
    inner = factor_lookback(p.inner)
    assert m0208.MATCHED.lookback(p) == cd.lookback_for(inner)
    assert m0208.OVERHANG.lookback(p) == inner
    assert m0208.MATCHED.lookback(p) <= SMOKE_BARS


def test_the_amendment_added_no_field_to_the_params_the_recorded_arms_use():
    """Plan invariant 1. ``registry._canon`` renders a dataclass by ``dataclasses.fields()``, so
    one more field on ``OverhangParams`` would move all four recorded M0208 digests."""
    assert [f.name for f in fields(m0208.OverhangParams)] == [
        "inner", "keep", "signal", "seed", "market"
    ]
    assert m0208.SIGNALS == ("high", "low", "hash")
    assert not hasattr(m0208, "MatchedParams"), "no new params dataclass: reuse, do not mint"


def test_every_recorded_m0208_digest_is_where_it_was():
    for cid, prefix in RECORDED.items():
        assert config_digest(_arm(cid)).startswith(prefix), cid


def test_the_new_arm_reuses_a_params_value_and_differs_on_the_allocator_line_alone():
    """The set's one params rule, with M0208's single named exception: every other phase reuses
    the value of the arm it REPLACES, this one reuses the value of the arm it CONTROLS, because
    ``_targets`` calls the shared ``scored`` and ``scored`` branches on ``p.signal`` -- handed
    ``"hash"`` it would match the churn of a placebo instead of the churn of the book."""
    new, target, old = _arm(NEW), _arm(TARGET), _arm(OLD)
    assert new.params == target.params
    assert new.params.signal == "high"
    assert old.params.signal == "hash"
    assert new.allocator.id != target.allocator.id
    assert config_digest(new) != config_digest(target)
    one, other = config_text(new).splitlines(), config_text(target).splitlines()
    assert [a == b for a, b in zip(one, other, strict=True)].count(False) == 1


def test_the_matched_draw_refuses_to_shadow_anything_but_the_high_side():
    """``signal`` names which arm this draw shadows, and the guard is in ``_targets`` because a
    ``"hash"`` value would silently make it a placebo of a placebo."""
    import pytest

    p = m0208.OverhangParams(m0208.N20, keep=40, signal="hash")
    rows = [m0208.FactorRow("AAA", 1.0, 0.0, 0.0, 0.0)]
    grid = object.__new__(m0208.WeekGrid)
    with pytest.raises(ValueError, match="signal must be 'high'"):
        m0208.MATCHED._targets({}, rows, grid, date(2015, 6, 30), frozenset(), p)


def test_the_new_arm_declares_the_arm_it_supersedes():
    """D17's supersession is DECLARED, never inferred from target equality, so an arm that
    declares nothing retires nothing and M0208 stays blocked on ``HASH-N20`` after all the
    measuring. The id comes from the plan index's supersession mapping."""
    assert _arm(NEW).supersedes == (OLD,)
    for c in m0208.METHOD.candidates:
        assert c.supersedes == (), f"{c.id}: an original arm declares nothing"


def test_the_declaration_is_outside_the_configuration():
    from dataclasses import replace as dc_replace

    new = _arm(NEW)
    assert config_text(dc_replace(new, supersedes=())) == config_text(new)
    assert "supersedes" not in config_text(new)


def test_m0208_carries_two_amendments_of_one_arm_each():
    """This used to pin "exactly one amendment", which is a pre-run fact about the database and
    goes red the moment the next amendment is pre-registered. Inverted to the post-run truth,
    which is the stronger assertion: both blocks exist, in order, the recorded one is still FIRST
    and still carries its own date, and neither grew a second arm. ``runner.pending_amendment``
    requires the record to be an exact prefix of the file, so an amendment that was reordered or
    reworded would refuse the next run; this is the import-time half of that check."""
    amendments = m0208.METHOD.amendments
    assert len(amendments) == 2
    assert amendments[0].added == date(2026, 10, 19)
    assert amendments[1].added == date(2026, 10, 20)
    assert [c.id for c in amendments[0].candidates] == [NEW]
    assert [c.id for c in amendments[1].candidates] == [SHADOW]
    assert len(m0208.METHOD.candidates) == 4
    assert len(m0208.METHOD.all_candidates()) == 6


def test_the_shadow_arm_reads_as_a_placebo_on_the_book_it_means_to_control():
    """Same guard as the A1 arm's, for the same reason: D17 tests dose BEFORE draw, so an arm
    worded as a dose-response one would carry no ratio at all and its refusal would vanish with
    the handicap still in place."""
    arms = list(m0208.METHOD.all_candidates())
    arm = _arm(SHADOW)
    text = arm.rationale.lower()
    assert cs.kind_of(arm) == cs.KIND_PLACEBO
    assert any(m in text for m in cs.DRAW_MARKERS)
    assert not any(m in text for m in cs.DOSE_MARKERS)
    assert cs.resolve_target(arm, arms) == (TARGET, cs.RUNG_STEM)


def test_the_shadow_arm_moves_neither_earlier_controls_resolution():
    """What makes this amendment additive. ``_eligible_targets`` excludes placebo arms, so a third
    placebo arriving cannot become anybody's target and no existing finding moves."""
    arms = list(m0208.METHOD.all_candidates())
    assert cs.resolve_target(_arm(OLD), arms) == (TARGET, cs.RUNG_FIRST)
    assert cs.resolve_target(_arm(NEW), arms) == (TARGET, cs.RUNG_STEM)


def test_the_shadow_allocator_is_a_third_id_and_names_no_ingredient():
    assert m0208.SHADOW.id == "M0208-A2"
    assert m0208.MATCHED.id == "M0208-A1" and m0208.OVERHANG.id == "M0208"
    assert _INGREDIENT.findall("allocator=<M0208-A2>") == []


def test_the_shadow_replay_fits_the_fixture_and_pays_for_every_step_it_takes():
    """The lookback is ``PREVIOUS_DECISION_BARS`` per replayed decision, through the module's own
    arithmetic and never a number guessed per file, and the cap is absolute: ``labkit.smoke_market``
    is 473 sessions, so 8 steps (461) is the deepest replay that can run at all. This arm asks for
    two, 305 bars, and leaves 168 of headroom."""
    p = _arm(SHADOW).params
    inner = factor_lookback(p.inner)
    assert m0208.SHADOW.lookback(p) == cd.shadow_lookback_for(inner, m0208.SHADOW_DEPTH)
    assert m0208.SHADOW.lookback(p) == inner + m0208.SHADOW_DEPTH * cd.PREVIOUS_DECISION_BARS
    assert cd.shadow_lookback_for(inner, 1) == cd.lookback_for(inner)
    assert 1 <= m0208.SHADOW_DEPTH <= cd.max_shadow_depth(inner) == 8
    assert m0208.SHADOW.lookback(p) <= SMOKE_BARS == cd.FIXTURE_BARS


def test_the_shadow_replays_the_calendar_this_chassis_actually_decides_on():
    """``shadow_selection`` derives its dates with ``control_draw.previous_decision_date``, while
    this file's own ``previous_month_end`` reads the market symbol's grid. On this chassis they are
    the same session -- the last one before the first of the month -- and the arm would be replaying
    a calendar the book never used if they were not. The free pre-run probe asserted it over every
    one of the dev window's 238 decisions before this file was committed; this pins the one-step
    identity so a later calendar change goes red here rather than inside a recorded trial."""
    for d in (date(2015, 6, 30), date(2009, 1, 30), date(2001, 2, 28)):
        assert cd.shadow_decision_dates(d, 1)[0] == cd.previous_decision_date(d)
        assert cd.shadow_decision_dates(d, 3) == [
            cd.previous_decision_date(cd.previous_decision_date(cd.previous_decision_date(d))),
            cd.previous_decision_date(cd.previous_decision_date(d)),
            cd.previous_decision_date(d),
            d,
        ]


def test_the_shadow_arm_declares_both_controls_it_replaces():
    """D17 supersedes a ``warn`` finding as well as a ``refuse`` one, so both earlier draws are
    named. Declared, never inferred: an arm that declares nothing retires nothing."""
    assert _arm(SHADOW).supersedes == ("M0208-CGO-N20-PLC", "M0208-HASH-N20")
    assert _arm(NEW).supersedes == (OLD,)
    for c in m0208.METHOD.candidates:
        assert c.supersedes == (), f"{c.id}: an original arm declares nothing"


def test_the_shadow_arm_minted_no_params_dataclass_and_moved_no_recorded_digest():
    """The set's one params rule. ``registry._canon`` renders a dataclass by
    ``dataclasses.fields()``, so one more field on ``OverhangParams`` would move all FIVE recorded
    M0208 digests, trial 853's included."""
    assert [f.name for f in fields(m0208.OverhangParams)] == [
        "inner", "keep", "signal", "seed", "market"
    ]
    assert not hasattr(m0208, "ShadowParams"), "no new params dataclass: reuse, do not mint"
    shadow, target, prior = _arm(SHADOW), _arm(TARGET), _arm(NEW)
    assert shadow.params == target.params == prior.params
    assert config_digest(shadow) not in {config_digest(target), config_digest(prior)}
    one, other = config_text(shadow).splitlines(), config_text(prior).splitlines()
    assert [a == b for a, b in zip(one, other, strict=True)].count(False) == 1


def test_the_shadow_draw_refuses_to_shadow_anything_but_the_high_side():
    import pytest

    p = m0208.OverhangParams(m0208.N20, keep=40, signal="hash")
    rows = [m0208.FactorRow("AAA", 1.0, 0.0, 0.0, 0.0)]
    grid = object.__new__(m0208.WeekGrid)
    with pytest.raises(ValueError, match="signal must be 'high'"):
        m0208.SHADOW._targets({}, rows, grid, date(2015, 6, 30), frozenset(), p)

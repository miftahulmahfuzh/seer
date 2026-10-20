"""The matched draw on the cap-weighted chassis: M0221-C50-PLC.

The guards at the foot of ``test_lab_control_draw`` pin the two pilot arms; these pin phase 3's,
in a module of its own so five concurrent phase sessions never edit one test file. They cost
nothing and see no return: classification, resolution, the allocator id, the params rule and the
supersession declaration are all read off the method file with no store and no database.

**Why there is only one arm here and not the twin pair the phase set out to record.** M0221 and
M0225 were planned together -- M0225 is M0221 on the repaired share-count store, so a
before-and-after measures the data fix and nothing else, which only works if both controls are
drawn by the identical rule under the identical hash namespace and seed. M0221-C50-PLC ran first
and recorded 371 trades against C50's 360 (**1.03x**, matched) and 0.8681 turnover against 0.445
(**1.95x**, missed). Turnover on a cap-weighted chassis is a property of the weight *vector*, not
of the names: M0221-E50 holds C50's exact names and records C50's exact 360 trades yet turns over
1.60x, and a blind draw from the sized pool is flatter still because it rarely holds a name big
enough for the 10% ceiling to bind. That was a recorded STOP (plan invariant 13) and M0225's block was
never written under it. Amendment 2 is what closes it: ``lab.control_weight`` pays the drawn names
C50's own weight vector down a ladder that puts this control's own entrants at the bottom, and
``WeightMatchedCapTopAllocator`` carries both halves. M0225's twin rides on it next, under
``M0225-A2`` -- which is what ``test_the_matched_allocator_is_reusable_by_a_twin`` was keeping
intact.
"""

from __future__ import annotations

from dataclasses import fields
from dataclasses import replace as dc_replace
from datetime import date

import pytest

from seer_engine.lab import control_draw as cd
from seer_engine.lab import control_shape as cs
from seer_engine.lab import control_weight as cw
from seer_engine.lab.hardgate import _INGREDIENT
from seer_engine.lab.method import config_digest, config_text
from seer_engine.lab.methods import m0221_cap_weighted_top_n as m0221
from seer_engine.lab.methods import m0225_cap_weighted_top_n_repaired as m0225

SMOKE_BARS = 473  # labkit.SMOKE_FIRST through DEV_END; the lookback cut every lab method clears
CONTROL_PARAMS = m0221.CapTopParams(50, pick="random", seed=1, trend=None)


def _arm(method, cid):
    return next(c for c in method.all_candidates() if c.id == cid)


def test_the_redrawn_control_reads_as_a_placebo_on_the_arm_it_means_to_control():
    """D17 classifies by prose, and it tests dose BEFORE draw. A re-drawn control that read as a
    dose-response arm would carry no ratio at all and its refusal would vanish without the
    handicap going anywhere; that is gaming the check and this is the test that forbids it.

    The resolution rung matters as much as the kind: ``sibling-stem`` is the strongest rung, and
    it is what the ``<target>-PLC`` name buys -- ``M0221-R50`` resolves to the same book on
    ``first-declared``, which the ladder itself reports as a guess."""
    arms = list(m0221.METHOD.all_candidates())
    control = _arm(m0221.METHOD, "M0221-C50-PLC")
    text = control.rationale.lower()
    assert cs.kind_of(control) == cs.KIND_PLACEBO
    assert any(m in text for m in cs.DRAW_MARKERS)
    assert not any(m in text for m in cs.DOSE_MARKERS)
    assert cs.resolve_target(control, arms) == ("M0221-C50", cs.RUNG_STEM)


def test_the_new_allocator_is_a_new_id_and_names_no_ingredient():
    r"""``hardgate._INGREDIENT`` is ``<(M\d{4})>``, so ``<M0221-A1>`` matches nothing and D12's
    ingredient map is exactly what it was. The originals keep their four-digit ids, which is what
    leaves every recorded trial's ``config_digest`` where it is."""
    assert m0221.MATCHED.id == "M0221-A1"
    assert m0221.CAPTOP.id == "M0221" and m0225.CAPTOP.id == "M0225"
    assert _INGREDIENT.findall("allocator=<M0221-A1>") == []


def test_the_matched_draw_allocator_reaches_back_one_extra_month_and_still_fits_the_fixture():
    """The draw reads the real arm at the previous decision as well as at this one, so the
    lookback is ``DV_N`` widened by ``control_draw.PREVIOUS_DECISION_BARS`` -- one number, in one
    place, rather than nine method files each guessing their own slack."""
    assert m0221.MATCHED.lookback(CONTROL_PARAMS) == cd.lookback_for(m0221.DV_N)
    assert m0221.MATCHED.lookback(CONTROL_PARAMS) <= SMOKE_BARS


def test_the_amendment_added_no_field_to_the_params_the_recorded_arms_use():
    """Plan invariant 1. ``registry._canon`` renders a dataclass by ``dataclasses.fields()``, so
    one more field on ``CapTopParams`` would move every recorded M0221 and M0225 digest -- both
    methods share the class, which is why no phase of this set mints a params dataclass."""
    assert [f.name for f in fields(m0221.CapTopParams)] == [
        "top", "weighting", "cap", "pick", "seed", "trend"
    ]
    assert m0221.PICKS == ("size", "random")
    assert m0221.WEIGHTINGS == ("cap", "equal")
    assert not hasattr(m0221, "MatchedParams"), "no new params dataclass: reuse, do not mint"


def test_the_new_arm_reuses_the_params_value_of_the_arm_it_replaces():
    """The set's one params rule: no new dataclass anywhere, the allocator id is the difference.

    ``config_text`` then differs on the ``allocator=`` line alone, which is enough for both
    ``Method.__post_init__``'s configuration-uniqueness check and ``trials``' global
    ``UNIQUE(config_digest, window)``."""
    new = _arm(m0221.METHOD, "M0221-C50-PLC")
    old = _arm(m0221.METHOD, "M0221-R50")
    assert type(new.params) is type(old.params)
    assert new.params == old.params == CONTROL_PARAMS
    assert new.params.pick == "random", "a blind book must not describe itself as a ranked one"
    assert new.allocator.id != old.allocator.id
    assert config_digest(new) != config_digest(old)


def test_a_control_that_claims_a_size_ranking_is_refused_at_construction():
    """``_check_control`` is the guard that keeps the reused params value honest: the config text
    is the public record of what an arm did, so a matched draw recorded as ``pick="size"`` would
    claim a ranking the allocator never performs."""
    with pytest.raises(ValueError, match="must be 'random'"):
        m0221.MATCHED.lookback(m0221.CapTopParams(50, pick="size", trend=None))


def test_the_new_arms_declare_the_arms_they_supersede():
    """D17's supersession is DECLARED, never inferred from target equality, so an arm that
    declares nothing retires nothing.

    C50-PLC's own declaration stands and still retires nothing: it came out `warn`, and
    `superseding_arm` requires an `OK` superseder, so what blocks M0221 was the measured turnover
    and not a missing tuple. C50-PLCW declares BOTH the arms it answers -- the `refuse` R50 that
    blocks D17 and the `warn` C50-PLC that does not -- because `control_shape` supersedes a warn
    too: a reader meeting the honest number has to be told the old one was answered.
    """
    assert _arm(m0221.METHOD, "M0221-C50-PLC").supersedes == ("M0221-R50",)
    assert _arm(m0221.METHOD, "M0221-C50-PLCW").supersedes == (
        "M0221-C50-PLC", "M0221-R50",
    ), "Candidate.__post_init__ requires the declaration sorted and unique"
    for c in m0221.METHOD.candidates:
        assert c.supersedes == (), f"{c.id}: an original arm declares nothing"
    for c in m0225.METHOD.candidates + tuple(m0225.E100_AMENDMENT.candidates):
        assert c.supersedes == (), f"{c.id}: an original or E100 arm declares nothing"


def test_the_supersedes_field_is_outside_every_recorded_digest():
    """Asserted rather than argued: ``config_text`` names its fields by hand and nothing passes a
    whole ``Candidate`` to ``registry._canon``, so a declaration can never move a recorded
    ``config_digest``."""
    c = _arm(m0221.METHOD, "M0221-C50-PLC")
    assert config_text(dc_replace(c, supersedes=())) == config_text(c)
    assert config_digest(dc_replace(c, supersedes=("M0221-C50",))) == config_digest(c)
    assert "supersedes" not in config_text(c)


def test_the_matched_allocator_is_reusable_by_a_twin():
    """``DRAW_KEY`` is the hash namespace and not the allocator id, so a subclass recorded under
    another method id draws the same names -- and, from amendment 2, pays them the same rungs --
    wherever both stores size the same company. M0225's ``M0225-A2`` is that subclass; this test
    is what kept the piece intact in the year it had no user."""
    assert m0221.DRAW_KEY == "M0221"
    assert "DRAW_KEY" not in m0221.MatchedCapTopAllocator.id
    assert cd.keep_key(m0221.DRAW_KEY, 1, "AAA") != cd.keep_key("M0225", 1, "AAA")


def test_the_amendment_blocks_are_the_expected_shape():
    """Two amendments on M0221, in declaration order, which is the order `pending_amendment`
    resolves them in: the record must be an exact prefix of the file, so a reordered or reworded
    block is a refusal and a recorded batch of trials can never be filed under a hypothesis nobody
    committed to before seeing it. M0225's second block lands in the next commit of this phase."""
    assert len(m0221.METHOD.amendments) == 2
    assert m0221.METHOD.amendments[0].added == date(2026, 10, 19)
    assert [c.id for c in m0221.METHOD.amendments[0].candidates] == ["M0221-C50-PLC"]
    assert m0221.METHOD.amendments[1].added == date(2026, 10, 20)
    assert [c.id for c in m0221.METHOD.amendments[1].candidates] == ["M0221-C50-PLCW"]
    assert len(m0221.METHOD.candidates) == 6
    assert len(m0221.METHOD.all_candidates()) == 8

    assert m0225.METHOD.amendments[0] is m0225.E100_AMENDMENT


def test_the_weight_matched_arm_reads_as_a_placebo_on_the_book_it_controls():
    """D17 classifies by prose and tests dose BEFORE draw, so an arm that read as dose-response
    would carry no ratio and its refusal would vanish with the handicap still in place. The rung
    matters as much as the kind: `sibling-stem` is what the `<target>-PLC...` name buys, and the
    new id keeps it -- `"M0221-C50-PLCW".rsplit("-", 1)[0]` is `"M0221-C50"`."""
    arm = _arm(m0221.METHOD, "M0221-C50-PLCW")
    text = arm.rationale.lower()
    assert cs.kind_of(arm) == cs.KIND_PLACEBO
    assert any(m in text for m in cs.DRAW_MARKERS)
    assert not any(m in text for m in cs.DOSE_MARKERS)
    assert cs.resolve_target(arm, list(m0221.METHOD.all_candidates())) == (
        "M0221-C50", cs.RUNG_STEM,
    )


def test_the_weight_allocator_is_a_new_id_that_names_no_ingredient():
    r"""``hardgate._INGREDIENT`` is ``<(M\d{4})>``, so ``<M0221-A2>`` matches nothing and D12's
    ingredient map is exactly what it was."""
    assert m0221.WMATCHED.id == "M0221-A2"
    assert _INGREDIENT.findall("allocator=<M0221-A2>") == []


def test_the_weight_rule_costs_no_extra_lookback():
    """The real arm's vector comes from the selection the matched draw already takes at
    ``data_date``, so amendment 2 reads no bar amendment 1 did not: one extra ``weights`` call per
    decision, not one extra pass of the pool. 473 is ``labkit.smoke_market``'s fixture and the cut
    every lab allocator clears."""
    assert m0221.WMATCHED.lookback(CONTROL_PARAMS) == m0221.MATCHED.lookback(CONTROL_PARAMS)
    assert m0221.WMATCHED.lookback(CONTROL_PARAMS) == cd.lookback_for(m0221.DV_N)
    assert m0221.WMATCHED.lookback(CONTROL_PARAMS) <= SMOKE_BARS


def test_the_weight_arm_reuses_the_params_value_and_mints_no_dataclass():
    """The set's one params rule, carried into the second amendment: no new dataclass anywhere,
    the allocator id is the whole difference. ``CapTopParams`` is shared by M0221 and M0225, so one
    added field -- even a defaulted one -- would move every recorded digest of both."""
    new = _arm(m0221.METHOD, "M0221-C50-PLCW")
    assert new.params == CONTROL_PARAMS
    assert new.params.pick == "random", "a blind book must not describe itself as a ranked one"
    assert [f.name for f in fields(m0221.CapTopParams)] == [
        "top", "weighting", "cap", "pick", "seed", "trend"
    ]
    assert config_digest(new) != config_digest(_arm(m0221.METHOD, "M0221-C50-PLC"))


def test_the_shipped_ladder_is_one_control_weight_recognises():
    """``WEIGHT_RULE`` is the record of which of four measured ladders this chassis pays the vector
    onto, and a method file naming its wiring must name something the module knows."""
    assert m0221.WEIGHT_RULE == "bottom-entry"
    assert m0221.WEIGHT_RULE in cw.ORDERS

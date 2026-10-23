"""The fixed-tape presets (measure-then-learn, phase 3).

Three rule sets carry the two Step 0 fixes: the resize band measured against the holding's own
target (``resize_basis="target"``) and idle cash earning the 13-week T-bill yield
(``cash_yield="T13W"``). They are new ids appended to ``PRESETS``, never edits, so these tests pin
two things: each preset is exactly its base plus the named levers, and nothing that was already
pinned (the old presets' canonical form, the promote mapping, the paper roster) moved.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from seer_engine.commands import promote
from seer_engine.paper import roster
from seer_engine.sim.rules import (
    LEVERS_SINCE_PINS,
    MONTHLY_HOLD,
    MONTHLY_HOLD_FRAC,
    MONTHLY_HOLD_FRAC_GOTRADE,
    MONTHLY_HOLD_FRAC_GOTRADE_TBAND,
    MONTHLY_HOLD_FRAC_GOTRADE_TBAND_CASH,
    MONTHLY_HOLD_FRAC_GOTRADE_TBAND00,
    PRESETS,
    WEEKLY_HOLD,
    WEEKLY_HOLD_FRAC_GOTRADE_TBAND_CASH,
    describe_rules,
    rule_owner_inputs,
)

TAPE = (
    MONTHLY_HOLD_FRAC_GOTRADE_TBAND,
    MONTHLY_HOLD_FRAC_GOTRADE_TBAND_CASH,
    WEEKLY_HOLD_FRAC_GOTRADE_TBAND_CASH,
)


def test_each_preset_is_its_base_plus_the_named_levers():
    assert MONTHLY_HOLD_FRAC_GOTRADE_TBAND == replace(
        MONTHLY_HOLD_FRAC_GOTRADE, id="monthly-hold-frac-gotrade-tband", resize_basis="target"
    )
    assert MONTHLY_HOLD_FRAC_GOTRADE_TBAND_CASH == replace(
        MONTHLY_HOLD_FRAC_GOTRADE, id="monthly-hold-frac-gotrade-tband-cash", resize_basis="target",
        cash_yield="T13W",
    )
    assert WEEKLY_HOLD_FRAC_GOTRADE_TBAND_CASH == replace(
        WEEKLY_HOLD, id="weekly-hold-frac-gotrade-tband-cash", fractional=True, cost_model="gotrade",
        resize_basis="target", cash_yield="T13W",
    )


def test_the_shared_levers():
    for r in TAPE:
        assert r.engine == "book", r.id
        assert r.resize is True and r.resize_cadence is None, r.id
        assert r.fractional is True and r.cost_model == "gotrade", r.id
        assert r.resize_basis == "target", r.id
        assert r.entry == "open_limit" and r.idle_symbol is None and r.dividends is True, r.id
    assert MONTHLY_HOLD_FRAC_GOTRADE_TBAND.cash_yield is None
    assert MONTHLY_HOLD_FRAC_GOTRADE_TBAND_CASH.cash_yield == "T13W"
    assert WEEKLY_HOLD_FRAC_GOTRADE_TBAND_CASH.cash_yield == "T13W"
    assert [r.cadence for r in TAPE] == ["monthly", "monthly", "weekly"]


def test_they_are_appended_last_in_order_and_nothing_else_moved():
    # (2026-10-23) A twentieth preset was appended for 023: MONTHLY_HOLD_FRAC_GOTRADE_TBAND00, the
    # target-basis tape with the band shut, which M0127 had defined inside its own method file and
    # which the roster could not name because `rules_for` resolves against PRESETS alone. It is
    # field-for-field equal to that T00, so no recorded trial's digest moves -- asserted below.
    # The three TAPE presets keep slots 16-18 and everything before 16 is untouched, which is what
    # this test is for.
    assert PRESETS[16:19] == TAPE
    assert PRESETS[19] is MONTHLY_HOLD_FRAC_GOTRADE_TBAND00
    assert len(PRESETS) == 20
    assert PRESETS[14] is MONTHLY_HOLD_FRAC_GOTRADE
    assert [r.resize_basis for r in PRESETS[:16]] == ["equity"] * 16
    assert [r.cash_yield for r in PRESETS[:16]] == [None] * 16


def test_the_band_zero_preset_is_m0127s_t00_field_for_field():
    """023 defines the band-zero tape in sim.rules so a roster entry can name it. M0127 keeps its
    own ``T00``: a method file is a pre-registration and is never edited. The two must stay equal,
    or a lab trial recorded on M0127's object and a paper entry running this one would be two
    different books wearing one id."""
    from dataclasses import asdict

    from seer_engine.lab.methods.m0127_slot_relative_resize_band import T00

    assert asdict(MONTHLY_HOLD_FRAC_GOTRADE_TBAND00) == asdict(T00)
    assert MONTHLY_HOLD_FRAC_GOTRADE_TBAND00.resize_band == 0
    assert MONTHLY_HOLD_FRAC_GOTRADE_TBAND00.resize_basis == "target"


def test_owner_inputs():
    # The target band is pure simulator arithmetic: nothing for the owner to verify.
    assert rule_owner_inputs(MONTHLY_HOLD_FRAC_GOTRADE_TBAND) == ()
    # Interest on idle dollars at Gotrade is not verified.
    assert rule_owner_inputs(MONTHLY_HOLD_FRAC_GOTRADE_TBAND_CASH) == ("cash-yield",)
    assert rule_owner_inputs(WEEKLY_HOLD_FRAC_GOTRADE_TBAND_CASH) == ("cash-yield",)


def test_canonical_form_names_the_new_levers_and_the_old_presets_still_omit_them():
    assert set(LEVERS_SINCE_PINS) >= {"resize_basis", "cash_yield"}
    for r in PRESETS[:16]:
        d = roster.rules_dict(r)
        assert "resize_basis" not in d and "cash_yield" not in d, r.id
    tband = roster.rules_dict(MONTHLY_HOLD_FRAC_GOTRADE_TBAND)
    assert tband["resize_basis"] == "target" and "cash_yield" not in tband
    for r in (MONTHLY_HOLD_FRAC_GOTRADE_TBAND_CASH, WEEKLY_HOLD_FRAC_GOTRADE_TBAND_CASH):
        d = roster.rules_dict(r)
        assert d["resize_basis"] == "target" and d["cash_yield"] == "T13W", r.id
    base = roster.rules_dict(MONTHLY_HOLD_FRAC_GOTRADE)
    assert {k: v for k, v in tband.items() if k not in ("id", "resize_basis")} == {
        k: v for k, v in base.items() if k != "id"
    }


def test_the_cash_free_preset_resolves_on_the_roster_and_the_promote_mapping_is_unchanged():
    assert roster.rules_for("monthly-hold-frac-gotrade-tband") is MONTHLY_HOLD_FRAC_GOTRADE_TBAND
    # a fractional preset is its own twin
    for r in TAPE:
        assert promote.fractional_twin(r) is r, r.id
    # the old whole-share presets still map where they did; none landed on a fixed-tape preset
    assert promote.fractional_twin(MONTHLY_HOLD) is MONTHLY_HOLD_FRAC
    with pytest.raises(promote.NotPromotable, match="no fractional preset"):
        promote.fractional_twin(WEEKLY_HOLD)


def test_promote_takes_the_band_preset_and_refuses_the_cash_presets():
    # phase 2's refusal fires for the real preset ids, not only for one-off test rule sets
    promote._check_rules(MONTHLY_HOLD_FRAC_GOTRADE_TBAND)
    for r in (MONTHLY_HOLD_FRAC_GOTRADE_TBAND_CASH, WEEKLY_HOLD_FRAC_GOTRADE_TBAND_CASH):
        with pytest.raises(promote.NotPromotable, match="interest on idle cash"):
            promote._check_rules(r)


def test_descriptions_differ_from_the_base_and_keep_twelve_lines():
    base = describe_rules(MONTHLY_HOLD_FRAC_GOTRADE)
    tband = describe_rules(MONTHLY_HOLD_FRAC_GOTRADE_TBAND)
    cash = describe_rules(MONTHLY_HOLD_FRAC_GOTRADE_TBAND_CASH)
    assert len(tband) == len(cash) == len(base) == 12
    # target band: only the rule-set name and the Rebalance line differ from the base
    assert [i for i in range(12) if tband[i] != base[i]] == [0, 7]
    # plus cash: and the Idle cash line
    assert [i for i in range(12) if cash[i] != tband[i]] == [0, 10]

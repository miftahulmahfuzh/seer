"""``TradeRules.resize_band``: the band's SIZE as a lever, and the pins that say it moved nothing.

Both resize bases hard-coded how far off target was far enough -- ``RESIZE_BAND`` (1% of equity)
under "equity", ``TARGET_RESIZE_BAND`` (20% of the holding's own target) under "target". M0127
needs a book that rebalances on 10%, 20% and 33% of a slot and one that rebalances fully, so the
size became a field (2026-10-20).

It is a lever added after the P7a registry, the lab trials and the paper roster were pinned, so
it sits in ``sim.rules.LEVERS_SINCE_PINS`` at ``None`` and drops out of every canonical text while
it is there. These tests are the proof, in the shape ``test_resize_basis_pins.py`` set:

- no preset uses it, so no live paper strategy's spec digest moves;
- every recorded candidate's registry text and lab config text is free of it;
- a rule set that USES it digests differently, which is the whole point;
- ``resize_band_of`` is the single reader, and the book engine and the rule-set description both
  go through it, so the three can never disagree.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from seer_engine import sim
from seer_engine.backtest.registry import REGISTRY, candidate_text
from seer_engine.lab.method import config_text, discover
from seer_engine.paper import roster
from seer_engine.sim import book
from seer_engine.sim.rules import (
    DAILY_SWITCH,
    DESIGN_V0,
    DESIGN_V0_GOTRADE,
    LEVERS_SINCE_PINS,
    MONTHLY_HOLD,
    MONTHLY_HOLD_FRAC_GOTRADE,
    MONTHLY_HOLD_FRAC_GOTRADE_TBAND,
    PRESETS,
    RESIZE_BAND,
    TARGET_RESIZE_BAND,
    V0_BOOK,
    TradeRules,
    describe_rules,
    is_pinned_default,
    resize_band_of,
)

T10 = replace(MONTHLY_HOLD_FRAC_GOTRADE_TBAND, id="x-t10", resize_band=Decimal("0.10"))
FULL = replace(MONTHLY_HOLD_FRAC_GOTRADE_TBAND, id="x-full", resize_band=Decimal("0"))


# ============================================================== the default is the old constant


def test_resize_band_defaults_to_the_basis_constant_everywhere():
    assert TradeRules(id="x", engine="book").resize_band is None
    assert DESIGN_V0.resize_band is None and V0_BOOK.resize_band is None
    assert all(r.resize_band is None for r in PRESETS)
    assert resize_band_of(MONTHLY_HOLD_FRAC_GOTRADE) == RESIZE_BAND
    assert resize_band_of(MONTHLY_HOLD_FRAC_GOTRADE_TBAND) == TARGET_RESIZE_BAND
    for r in PRESETS:
        expected = TARGET_RESIZE_BAND if r.resize_basis == "target" else RESIZE_BAND
        assert resize_band_of(r) == expected, r.id


def test_a_named_band_overrides_the_constant_on_either_basis():
    assert resize_band_of(T10) == Decimal("0.10")
    assert resize_band_of(FULL) == Decimal("0")
    equity = replace(MONTHLY_HOLD_FRAC_GOTRADE, id="x-e", resize_band=Decimal("0.005"))
    assert resize_band_of(equity) == Decimal("0.005")
    assert sim.resize_band_of is resize_band_of and "resize_band_of" in sim.__all__


def test_resize_band_validation():
    with pytest.raises(TypeError, match="resize_band"):
        replace(MONTHLY_HOLD, id="x", resize_band=0.1)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match=r"resize_band must be a Decimal in \[0, 1\)"):
        replace(MONTHLY_HOLD, id="x", resize_band=Decimal("1"))
    with pytest.raises(ValueError, match=r"resize_band must be a Decimal in \[0, 1\)"):
        replace(MONTHLY_HOLD, id="x", resize_band=Decimal("-0.01"))
    with pytest.raises(ValueError, match="needs resize=True"):
        replace(DAILY_SWITCH, id="x", resize_band=Decimal("0.1"))
    with pytest.raises(ValueError, match="book-engine lever"):
        replace(DESIGN_V0_GOTRADE, id="x", resize=True, resize_band=Decimal("0.1"))


# ============================================================== it moved nothing that was pinned


def test_resize_band_is_a_lever_since_the_pins():
    assert LEVERS_SINCE_PINS["resize_band"] is None
    assert is_pinned_default("resize_band", None) is True
    assert is_pinned_default("resize_band", Decimal("0.10")) is False


def test_no_preset_names_a_band_so_no_live_spec_digest_moves():
    """No preset carries the lever, which is also what keeps the web mirror honest.

    ``web/lib/cadence.ts`` sizes the owner's resize reminders from two hand-mirrored constants
    (``RESIZE_BAND``, ``TARGET_RESIZE_BAND``) and knows nothing of a per-rule-set band. It only
    ever sees roster rule sets, and a roster rule set must be a preset, so the mirror is exact for
    everything it can be handed. The day a preset names a band, this test goes red first and the
    TS side has to learn the lever before any paper strategy can carry it.
    """
    for r in PRESETS:
        assert "resize_band" not in roster.rules_dict(r), r.id
    assert roster.rules_dict(T10)["resize_band"] == "0.10"


def test_every_pinned_candidate_and_lab_config_is_free_of_the_lever():
    for c in REGISTRY:
        assert "resize_band" not in candidate_text(c), c.id
    for _mid, (method, _sha) in discover().items():
        for c in method.all_candidates():
            text = config_text(c)
            if c.rules.resize_band is None:
                assert "resize_band" not in text, c.id
            else:
                assert f"resize_band={c.rules.resize_band}" in text, c.id


# ============================================================== one reader, three users


def test_the_book_engine_reads_the_named_band():
    equity = Decimal("10000")
    weight = Decimal("0.02")  # a 50-name equal-weight book: a $200 slot
    last = Decimal("1")
    # 20% of a $200 slot is $40; 10% is $20. A $30 gap is beyond one band and inside the other.
    assert book._beyond_band(Decimal("30"), last, weight, equity, MONTHLY_HOLD_FRAC_GOTRADE_TBAND) is False
    assert book._beyond_band(Decimal("30"), last, weight, equity, T10) is True
    # A zero band trades any non-zero gap, and still never trades a gap of zero or less.
    assert book._beyond_band(Decimal("0.0001"), last, weight, equity, FULL) is True
    assert book._beyond_band(Decimal("0"), last, weight, equity, FULL) is False
    # Unchanged for the rule sets that name no band: 1% of equity is $100.
    assert book._beyond_band(Decimal("99"), last, weight, equity, MONTHLY_HOLD_FRAC_GOTRADE) is False
    assert book._beyond_band(Decimal("100"), last, weight, equity, MONTHLY_HOLD_FRAC_GOTRADE) is True


def test_the_description_states_the_named_band_and_keeps_its_shape():
    assert len(describe_rules(T10)) == len(describe_rules(MONTHLY_HOLD_FRAC_GOTRADE_TBAND))
    assert "10% of its own target value" in describe_rules(T10)[7]
    assert "20% of its own target value" in describe_rules(MONTHLY_HOLD_FRAC_GOTRADE_TBAND)[7]
    assert "1% of equity" in describe_rules(MONTHLY_HOLD_FRAC_GOTRADE)[7]
    assert "0% of its own target value" in describe_rules(FULL)[7]

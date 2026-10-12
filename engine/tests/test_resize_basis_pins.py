"""Invariant 2 of the measure-then-learn plan: adding ``TradeRules.resize_basis`` moves no
pinned digest.

``resize_basis`` is a lever added after the pins (``sim.rules.LEVERS_SINCE_PINS``), so at its
no-op value "equity" it is left out of every canonical form: the registry's ``candidate_text``,
the lab's ``config_text`` (every closed trial's ``config_digest``) and the paper roster's
``rules_dict`` (every live spec digest). A rule set that USES "target" canonicalizes differently,
which is the point. ``tests/test_cost_model_pins.py`` already recomputes every committed lab
trial's digest byte for byte; ``tests/test_registry.py`` and ``tests/test_paper_roster.py`` pin
theirs. This file asserts the lever's own absence and presence.
"""

from __future__ import annotations

from dataclasses import replace

from seer_engine.backtest.registry import REGISTRY, candidate_digest, candidate_text
from seer_engine.lab.method import config_digest, config_text, discover
from seer_engine.paper import roster
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE, PRESETS


def _all_candidates():
    out = list(REGISTRY)
    for m, _ in discover().values():
        out += list(m.candidates)
    return out


def _asserts_resize_basis(text: str, c) -> None:
    """"equity" is left out of a canonical form; "target" names itself, so it digests apart.

    Conditional on purpose: later methods built on a target-basis preset must name the lever,
    and asserting absence unconditionally would pin the lab to the old band.
    """
    if c.rules.resize_basis == "equity":
        assert "resize_basis" not in text, c.id
    else:
        assert f"resize_basis='{c.rules.resize_basis}'" in text, c.id


def test_equity_is_absent_from_every_canonical_form():
    for c in REGISTRY:
        _asserts_resize_basis(candidate_text(c), c)
    for c in _all_candidates():
        _asserts_resize_basis(config_text(c), c)
    for r in PRESETS:
        if r.resize_basis == "equity":
            assert "resize_basis" not in roster.rules_dict(r), r.id
        else:
            assert roster.rules_dict(r)["resize_basis"] == r.resize_basis, r.id


def test_target_digests_differently():
    resizing = [c for c in _all_candidates() if c.rules.engine == "book" and c.rules.resize]
    assert resizing
    for c in resizing[:25]:
        if c.rules.resize_basis == "target":
            continue
        t = replace(c, rules=replace(c.rules, resize_basis="target"))
        assert "resize_basis='target'" in config_text(t), c.id
        assert config_digest(t) != config_digest(c), c.id
        assert candidate_digest(t) != candidate_digest(c), c.id
    g = replace(MONTHLY_HOLD_FRAC_GOTRADE, id="monthly-hold-frac-gotrade-tband", resize_basis="target")
    assert roster.rules_dict(g)["resize_basis"] == "target"
    assert "resize_basis" not in roster.rules_dict(MONTHLY_HOLD_FRAC_GOTRADE)

"""The calculate-assets skill must run a rule set that is already the owner's money model by name.

M0555's four arms are fractional shares at Gotrade's real fees with a deposit-timing gate on top.
Before the table knew them the skill refused every arm as "no fractional Gotrade preset", which is
a gap in the table, not a verdict on the method. Swapping the gate away would answer a different
question, so each arm must come back exactly as recorded.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from seer_engine.lab.method import discover

SKILL = Path(__file__).resolve().parents[2] / ".claude/skills/calculate-assets/calculate_assets.py"


@pytest.fixture(scope="module")
def skill():
    spec = importlib.util.spec_from_file_location("calculate_assets", SKILL)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("variant", ["DIP", "IMMEDIATE", "DELAY3", "MIRROR"])
def test_m0555_arms_run_as_recorded(skill, variant):
    method, _ = discover()["M0555"]
    cand = next(c for c in method.candidates if c.id == f"M0555-{variant}")
    got, note = skill.realistic(cand)
    assert got is cand
    assert "already trades the way the owner does" in note

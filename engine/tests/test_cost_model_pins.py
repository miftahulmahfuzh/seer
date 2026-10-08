"""Invariant 2 of the Sean plan: adding ``TradeRules.cost_model`` moves no pinned digest.

``cost_model`` is a lever added after the pins (``sim.rules.LEVERS_SINCE_PINS``), so at its
no-op value "flat" it is left out of every canonical form: the registry's ``candidate_text``,
the lab's ``config_text`` (every closed trial's ``config_digest``) and the paper roster's
``rules_dict`` (every live spec digest). A rule set that USES "gotrade" canonicalizes
differently, which is the point. ``tests/test_registry.py`` and ``tests/test_paper_roster.py``
pin their digests already; this file adds the committed lab database, row by row.
"""

from __future__ import annotations

import sqlite3
from dataclasses import replace

import pytest

from seer_engine.backtest.registry import REGISTRY, candidate_digest, candidate_text
from seer_engine.lab import store
from seer_engine.lab.method import config_digest, config_text, discover
from seer_engine.paper import roster
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC, PRESETS


def _gotrade(c):
    return replace(c, rules=replace(c.rules, cost_model="gotrade"))


def _book_candidates():
    out = [c for c in REGISTRY if c.rules.engine == "book"]
    for m, _ in discover().values():
        out += [c for c in m.candidates if c.rules.engine == "book"]
    return out


def test_every_committed_lab_trial_recomputes_its_config_digest_byte_for_byte():
    if not store.COMMITTED_DB.exists():
        pytest.skip("no lab database")
    by_id = {c.id: c for c in REGISTRY}
    for m, _ in discover().values():
        for c in m.candidates:
            by_id[c.id] = c
    conn = sqlite3.connect(f"file:{store.COMMITTED_DB}?mode=ro", uri=True)
    try:
        rows = conn.execute("SELECT candidate_id, config_digest, config_text FROM trials").fetchall()
    finally:
        conn.close()
    checked = 0
    for candidate_id, digest, text in rows:
        c = by_id.get(candidate_id)
        if c is None:
            continue  # a sibling worktree's method: test_lab_methods says why that is allowed
        assert config_text(c) == text, candidate_id
        assert config_digest(c) == digest, candidate_id
        checked += 1
    assert checked > 0


def test_flat_is_absent_from_every_canonical_form():
    for c in REGISTRY:
        assert "cost_model" not in candidate_text(c), c.id
        assert "cost_model" not in config_text(c), c.id
    for m, _ in discover().values():
        for c in m.candidates:
            assert "cost_model" not in config_text(c), c.id
    for r in PRESETS:
        if r.cost_model == "flat":
            assert "cost_model" not in roster.rules_dict(r), r.id
        else:  # the real-fee presets (Sean phase 7) name their model, so they digest apart
            assert roster.rules_dict(r)["cost_model"] == "gotrade", r.id
    assert [r.id for r in PRESETS if r.cost_model != "flat"] == [
        "design-v0-gotrade",
        "monthly-hold-frac-gotrade",
        "monthly-rank-weekly-resize-frac-gotrade",
    ]


def test_gotrade_digests_differently():
    for c in _book_candidates()[:25]:
        g = _gotrade(c)
        assert "cost_model='gotrade'" in config_text(g)
        assert config_digest(g) != config_digest(c)
        assert candidate_digest(g) != candidate_digest(c)
    g = replace(MONTHLY_HOLD_FRAC, id="monthly-hold-frac-gotrade", cost_model="gotrade")
    assert roster.rules_dict(g)["cost_model"] == "gotrade"

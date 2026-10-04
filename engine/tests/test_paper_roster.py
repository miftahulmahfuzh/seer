"""The frozen paper roster (handover D1, D2, D4; plan contract C2).

- The display fields equal the rows migrations 003 and 004 (``C``) insert.
- Every entry is the object, params and rules the handover names; book entries are the
  registry's entries unchanged.
- The spec digests are pinned. A failing pin means a roster strategy changed: give it a NEW
  id (its own paper clock) instead of editing the pin.
- C (strategy-c-news-veto D1, D5, D9) is A's spec plus the frozen news check; its backtest gate
  says "not applicable"; the four earlier entries' digests and gate dicts are unchanged.
"""

from __future__ import annotations

import json
from datetime import date, timedelta

import pytest
from psycopg.types.json import Jsonb

from seer_engine import dates
from seer_engine.backtest.registry import REGISTRY, candidate_digest
from seer_engine.paper.roster import (
    BENCHMARK_ID,
    MAX_LOOKBACK_BARS,
    ROSTER,
    ROSTER_IDS,
    backtest_gate,
    entry,
    rules_dict,
    spec,
    spec_digest,
    spec_text,
    strategy_params,
)
from seer_engine.sim.rules import DESIGN_V0, MONTHLY_HOLD
from seer_engine.strategies.a import STRATEGY_A, STRATEGY_A_PARAMS
from seer_engine.strategies.c import (
    FROZEN_MODEL,
    PROMPT_VERSION,
    STRATEGY_C,
    STRATEGY_C_ID,
    STRATEGY_C_PARAMS,
    SYSTEM_PROMPT,
    USER_TEMPLATE,
)
from seer_engine.strategies.f_factor import FACTOR
from seer_engine.strategies.f_index import TIMING

F4 = "F4-MOM12-N20-TREND"
F1 = "F1-SPY-SMA200-M"

PINS = {
    "SPY": "ca309ea7f19d0b771f236c63309a2fcf28a82e16048528d738dc329a42d4d198",
    "A": "37cd89be4b4c82f9dc2d4f3bdd69551a7d31aef83119f23ee757f8ec6568362f",
    F4: "6c55c13acc487a6fccbe2c5c0eb91a36e39f3a5444555a0dbfba4ffba5b30deb",
    F1: "e7fbb32d1cc4e11b2d0d9b941ab01ac1a545e49a08c11bf8c70da5c54cad9e2f",
    "C": "6cea6cb8de993f6a3f2d7ef4b48c878654a57df16cab87f72a95e9dd49a1b762",
}

FACTOR_PARAMS_AS_DICT = {
    "rank": "momentum",
    "top": "20",
    "mom_n": "252",
    "mom_skip": "21",
    "vol_n": "60",
    "pool": "50",
    "sizing": "equal",
    "min_dollar_volume": "20000000",
    "min_price": "5",
    "trend": "SPY:200",
}


DISPLAY = ("id", "name", "sub", "icon", "is_champion", "is_benchmark", "sort", "engine", "rules_id")


def test_the_roster_is_the_handover_entries_in_sort_order():
    assert ROSTER_IDS == ("SPY", "A", F4, F1, "C")
    assert [e.sort for e in ROSTER] == [1, 2, 3, 4, 5]
    assert "B" not in ROSTER_IDS


def test_spy_is_the_only_champion_and_the_only_benchmark():
    assert [e.id for e in ROSTER if e.is_champion] == [BENCHMARK_ID]
    assert [e.id for e in ROSTER if e.is_benchmark] == [BENCHMARK_ID]


def test_display_fields_equal_the_migration_rows(pg):
    rows = pg.execute(f"SELECT {', '.join(DISPLAY)} FROM strategies ORDER BY sort").fetchall()
    assert rows == [tuple(getattr(e, f) for f in DISPLAY) for e in ROSTER]


def test_each_entry_is_the_named_object_params_and_rules():
    spy, a, f4, f1, c = (entry(i) for i in ROSTER_IDS)
    assert (spy.engine, spy.obj, spy.rules, spy.rules_id, spy.params) == ("benchmark", None, None, None, None)
    assert a.engine == "bracket"
    assert a.obj is STRATEGY_A and a.params is STRATEGY_A_PARAMS and a.rules is DESIGN_V0
    assert a.registry_id is None
    assert f4.engine == "book" and f4.obj is FACTOR and f4.rules == MONTHLY_HOLD
    assert f1.engine == "book" and f1.obj is TIMING and f1.rules == MONTHLY_HOLD
    assert (f4.registry_id, f1.registry_id) == (F4, F1)
    assert c.engine == "bracket" and c.rules is DESIGN_V0 and c.rules_id == "design-v0"
    assert c.obj is STRATEGY_C and c.params is STRATEGY_C_PARAMS and c.object_name == "STRATEGY_C"
    assert c.registry_id is None
    assert c.params.a is STRATEGY_A_PARAMS


def test_book_entries_are_the_registry_entries_unchanged():
    by_id = {c.id: c for c in REGISTRY}
    for e in ROSTER:
        if e.registry_id is None:
            continue
        c = by_id[e.registry_id]
        assert e.obj is c.allocator
        assert e.params == c.params
        assert e.rules == c.rules
        assert spec(e)["registry_digest"] == candidate_digest(c)


def test_digests_are_pinned():
    assert {e.id: spec_digest(spec(e)) for e in ROSTER} == PINS


def test_spec_is_strings_and_nulls_only():
    def leaves(x):
        if isinstance(x, dict):
            for v in x.values():
                yield from leaves(v)
        else:
            yield x

    for e in ROSTER:
        assert all(v is None or isinstance(v, str) for v in leaves(spec(e))), e.id


def test_spec_text_is_canonical_and_survives_a_json_round_trip():
    for e in ROSTER:
        s = spec(e)
        shuffled = dict(reversed(list(s.items())))
        assert spec_text(shuffled) == spec_text(s)
        assert spec_digest(json.loads(json.dumps(s))) == spec_digest(s)
        assert spec_text(s).isascii()


def test_the_spec_names_engine_object_rules_and_params():
    s = spec(entry(F4))
    assert (s["engine"], s["object"], s["object_id"], s["registry_id"], s["rules_id"]) == (
        "book", "FACTOR", "FAC", F4, "monthly-hold",
    )
    assert s["params"] == FACTOR_PARAMS_AS_DICT
    assert s["rules"] == rules_dict(MONTHLY_HOLD)
    assert s["initial_idr"] == "20000000"
    a = spec(entry("A"))
    assert a["params"] == STRATEGY_A_PARAMS.as_dict()
    assert a["rules"]["engine"] == "bracket_v0"


def test_a_changed_parameter_changes_the_digest():
    s = spec(entry(F4))
    changed = json.loads(json.dumps(s))
    changed["params"]["top"] = "10"
    assert spec_digest(changed) != spec_digest(s)


def test_strategy_params_is_contract_c2():
    for e in ROSTER:
        p = strategy_params(e)
        assert set(p) == {"spec", "digest", "backtest_gate"}
        assert p["digest"] == spec_digest(p["spec"])
        assert p["backtest_gate"] == backtest_gate(e)
        assert p["backtest_gate"]["passed"] is False and p["backtest_gate"]["note"] == e.gate_note
        assert e.gate_note
        json.dumps(p)


def test_strategy_params_round_trip_through_jsonb(pg):
    for e in ROSTER:
        p = strategy_params(e)
        pg.execute("UPDATE strategies SET params = %s WHERE id = %s", (Jsonb(p), e.id))
        back = pg.execute("SELECT params FROM strategies WHERE id = %s", (e.id,)).fetchone()[0]
        assert back == p
        assert spec_digest(back["spec"]) == back["digest"] == PINS[e.id]
    pg.rollback()


def test_lookbacks():
    assert {e.id: e.lookback for e in ROSTER} == {"SPY": 1, "A": 200, F4: 253, F1: 200, "C": 200}
    assert MAX_LOOKBACK_BARS == 253


def test_550_calendar_days_hold_the_longest_lookback():
    # Plan decision "History at night": bars since data_date − 550 calendar days.
    for d in dates.sessions(date(2026, 10, 1), date(2027, 12, 31)):
        assert len(dates.sessions(d - timedelta(days=550), d)) >= MAX_LOOKBACK_BARS


def test_entry_rejects_an_id_off_the_roster():
    with pytest.raises(KeyError):
        entry("B")


# ---- C (strategy-c-news-veto D1, D5, D9) ---------------------------------------------------------


def test_the_four_earlier_gate_dicts_are_unchanged():
    for sid in ("SPY", "A", F4, F1):
        e = entry(sid)
        assert e.gate_applicable is True
        gate = backtest_gate(e)
        assert gate == {"passed": False, "note": e.gate_note}
        assert list(gate) == ["passed", "note"]


def test_c_gate_is_not_applicable_and_not_passed():
    c = entry("C")
    assert c.gate_applicable is False
    assert c.gate_note == "Backtest gate: not applicable (LLM strategy, design §1 item 5)"
    assert backtest_gate(c) == {"passed": False, "applicable": False, "note": c.gate_note}
    assert strategy_params(c)["backtest_gate"] == backtest_gate(c)


def test_c_spec_is_a_plus_the_frozen_news_check():
    s = spec(entry("C"))
    assert (s["engine"], s["object"], s["object_id"], s["registry_id"], s["registry_digest"], s["rules_id"]) == (
        "bracket", "STRATEGY_C", STRATEGY_C_ID, None, None, "design-v0",
    )
    assert STRATEGY_C.id == STRATEGY_C_ID == "C-news-veto"
    assert s["rules"] == rules_dict(DESIGN_V0) == spec(entry("A"))["rules"]
    assert s["initial_idr"] == "20000000"
    p = s["params"]
    assert p == STRATEGY_C_PARAMS.as_dict()
    assert {k[2:]: v for k, v in p.items() if k.startswith("a.")} == STRATEGY_A_PARAMS.as_dict()
    assert (p["a_object"], p["a_object_id"]) == ("STRATEGY_A", STRATEGY_A.id)
    assert {k: p[k] for k in (
        "max_candidates", "news_days", "max_headlines", "max_summary_chars", "earnings_sessions",
        "model", "prompt_version", "temperature", "thinking", "max_tokens",
    )} == {
        "max_candidates": "10",
        "news_days": "3",
        "max_headlines": "20",
        "max_summary_chars": "280",
        "earnings_sessions": "5",
        "model": FROZEN_MODEL,
        "prompt_version": PROMPT_VERSION,
        "temperature": "0",
        "thinking": "disabled",
        "max_tokens": "1024",
    }
    assert (FROZEN_MODEL, PROMPT_VERSION) == ("glm-5.3", "c-veto-v1")
    assert (p["system_prompt"], p["user_template"]) == (SYSTEM_PROMPT, USER_TEMPLATE)


def test_c_digest_moves_with_the_model_and_the_prompt():
    s = spec(entry("C"))
    for key, value in (("model", "glm-9"), ("prompt_version", "c-veto-v2"), ("system_prompt", "x")):
        changed = json.loads(json.dumps(s))
        changed["params"][key] = value
        assert spec_digest(changed) != spec_digest(s), key


def test_the_roster_c_object_carries_no_verdicts():
    assert len(entry("C").obj.allowed) == 0

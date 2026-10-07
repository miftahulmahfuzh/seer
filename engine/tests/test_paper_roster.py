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

import dataclasses

import json
from datetime import date, timedelta

import psycopg
import pytest
from psycopg.types.json import Jsonb

from seer_engine import dates
from seer_engine.backtest.registry import REGISTRY, candidate_digest
from seer_engine.paper.roster import (
    BENCHMARK_ID,
    BENCHMARK_OBJECT,
    MAX_LOOKBACK_BARS,
    RESOLVER,
    ROSTER,
    ROSTER_IDS,
    SEED_ROWS,
    BadRosterRow,
    RosterRow,
    UnknownObject,
    UnknownRules,
    active,
    backtest_gate,
    entry,
    from_row,
    from_rows,
    resolve,
    resolver_names,
    rules_dict,
    spec,
    spec_digest,
    spec_text,
    strategy_params,
)
from seer_engine.sim.rules import DESIGN_V0, MONTHLY_HOLD, MONTHLY_HOLD_FRAC
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
from seer_engine.strategies.f_fundamental import FUNDAMENTAL
from seer_engine.strategies.f_index import TIMING

F4 = "F4-MOM12-N20-TREND"
F1 = "F1-SPY-SMA200-M"
FND = "FND"
F4_FR = "F4-MOM12-N20-TREND-FR"
F1_FR = "F1-SPY-SMA200-M-FR"
RM = "RM-FR"  # lab M0011-RAW20-TV14-N21 in fractional shares; replaces FND (010), retired by 011
RMW = "RMW-FR"  # lab M0022-W-TV16: RM with a weekly brake, split cadence; replaces RM (011)
# 013: the roster chosen for the first paper night. A, F4_FR and F1_FR are retired -- none of the
# three can satisfy design section 1 (A failed its own gate twice; F4's 22.2% max DD is outside
# the revised 20% bar; F1 closed 11 trades in 22 dev years against the 100 required) -- and these
# three join. See the 013 block comment in paper/roster.py for the full screen.
RAW = "RAW-FR"  # lab M0007-N20-RAW: RMW's engine with no brake, the controlled comparison
MOM = "MOM-FR"  # lab M0002-REL-85: total-return momentum inside the 20% bar; replaces F4_FR
MVW = "MVW-FR"  # lab M0008-N30-C07: minimum-variance weighting; replaces F1_FR
RETIRED = (F4, F1, FND, "RM-FR", "A", F4_FR, F1_FR)  # none of them ever traded a paper session
ACTIVE_IDS = ("SPY", "C", RMW, RAW, MOM, MVW)

# 2026-10-07: every digest moved once, on purpose, when the paper books' starting cash went from
# 20,000,000 to 10,000,000 IDR (spec "initial_idr"; the owner's own Gotrade money). Production's
# paper clocks were reset the same day, before any session had been stepped.
PINS = {
    "SPY": "9737a68ed0075b0a66bb076c12097f2ff54bd79c45fc6085b1bd8bf7fb110dab",
    "A": "ee49ea0bb1e972a1cf808456bb094fdbf3e97cce6efafdb115ae4e5273c287d5",
    F4: "0141e9833a5a26ae31ac969c758fb90b3d737d36d2b8d572a88eada6a2cea93c",
    F1: "a00d98e604427fcbba19b936c760eae653f859eb878a6469b1c23c7e9f680706",
    "C": "fc355c3fbbfe7589328c53521ea418ecab814c2a65fc9b0a6945ed28a9a8fb35",
    # FND joined the roster in phase 6 of roster-promotion-pipeline: composite-rank fundamentals,
    # top 20, equal sizing, under monthly-hold. Adding an entry must never re-digest another one.
    FND: "d6b262921285300d65fa78181c374464e34f664bd1f6d076e0686a65e75ecc20",
    # 010: F4 and F1 under monthly-hold-frac, and RM (lab M0011) replacing FND.
    F4_FR: "a553cf218e17b49f28d474bf8e0d9f00bdaf5ea2042722f45b9e31af7e7b1900",
    F1_FR: "38cfe989faadafa765058764e948583ed2f3cc28e174369b278e06fa65c25c44",
    RM: "fb435dc8d0a5e372d137938b1881b4558c94639ca3483e56f225751b82535264",
    # 011: RM's book with its brake read weekly (lab M0022-W-TV16), split cadence, fractional.
    RMW: "375e6f63d4b6a00842b330b8bfc9405a2e204f50bf5dac65b6a7bb2a706729ce",
    # 013: RAW (lab M0007-N20-RAW), MOM (lab M0002-REL-85) and MVW (lab M0008-N30-C07), all three
    # under monthly-hold-frac. Adding them must never re-digest an earlier entry: the ten digests
    # above are unchanged from 011, and that is what the pin proves.
    RAW: "e772830d223c96b8547c8224ad2d6d17254c051f701015b6eff8f67d53a57c5b",
    MOM: "7e027e48a405c73a619337bbd420f895e0663d295fd63f8dcb312f296b84480c",
    MVW: "4f208ce2ce23691cc8e992aadf3cb9337f90a0946cac60c389f470b964ff502e",
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
    assert ROSTER_IDS == ("SPY", "A", F4, F1, "C", FND, F4_FR, F1_FR, RM, RMW, RAW, MOM, MVW)
    assert [e.sort for e in ROSTER] == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]
    assert "B" not in ROSTER_IDS


def test_spy_is_the_only_champion_and_the_only_benchmark():
    assert [e.id for e in ROSTER if e.is_champion] == [BENCHMARK_ID]
    assert [e.id for e in ROSTER if e.is_benchmark] == [BENCHMARK_ID]


def test_display_fields_equal_the_migration_rows(pg):
    rows = pg.execute(f"SELECT {', '.join(DISPLAY)} FROM strategies ORDER BY sort").fetchall()
    assert rows == [tuple(getattr(e, f) for f in DISPLAY) for e in ROSTER]


def test_each_entry_is_the_named_object_params_and_rules():
    spy, a, f4, f1, c, fnd, f4_fr, f1_fr, rm, rmw, raw, mom, mvw = (entry(i) for i in ROSTER_IDS)
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
    # FND is the one entry whose object is neither a registry candidate nor a bracket
    # strategy: it resolves to FUNDAMENTAL by name with its own params (D1, D2).
    assert fnd.engine == "book" and fnd.obj is FUNDAMENTAL and fnd.rules == MONTHLY_HOLD
    assert fnd.object_name == "FUNDAMENTAL" and fnd.registry_id is None
    # 010: the fractional twins run the same objects and params under monthly-hold-frac. F4 and F1
    # are the same registry candidates, traded in fractional shares (roster._registered allows a
    # rule set that differs from the candidate's in the share granularity only).
    assert f4_fr.obj is FACTOR and f4_fr.params is f4.params and f4_fr.rules is MONTHLY_HOLD_FRAC
    assert f1_fr.obj is TIMING and f1_fr.params is f1.params and f1_fr.rules is MONTHLY_HOLD_FRAC
    assert (f4_fr.object_name, f1_fr.object_name) == ("FACTOR", "TIMING")
    assert (f4_fr.registry_id, f1_fr.registry_id) == (F4, F1)
    # RM: lab M0011's braked residual momentum, its RAW20-TV14-N21 variant, in fractional shares.
    from seer_engine.lab.methods.m0011_raw_residual_own_vol import METHOD as M0011
    from seer_engine.lab.methods.m0011_raw_residual_own_vol import RESIDVOL

    trial = next(c for c in M0011.candidates if c.id == "M0011-RAW20-TV14-N21")
    assert rm.obj is RESIDVOL and rm.params is trial.params and rm.object_name == "RESIDVOL"
    assert rm.rules is MONTHLY_HOLD_FRAC and trial.rules is MONTHLY_HOLD and rm.registry_id is None
    assert rm.status == "retired"  # 011: replaced by RMW before its first paper session
    from seer_engine.lab.methods.m0022_weekly_brake_residual import METHOD as M0022
    from seer_engine.lab.methods.m0022_weekly_brake_residual import WEEKLYBRAKE
    from seer_engine.sim.rules import MONTHLY_RANK_WEEKLY_RESIZE, MONTHLY_RANK_WEEKLY_RESIZE_FRAC

    w = next(c for c in M0022.candidates if c.id == "M0022-W-TV16")
    assert rmw.obj is WEEKLYBRAKE and rmw.params is w.params and rmw.object_name == "WEEKLYBRAKE"
    assert rmw.rules is MONTHLY_RANK_WEEKLY_RESIZE_FRAC and w.rules is MONTHLY_RANK_WEEKLY_RESIZE
    assert MONTHLY_HOLD_FRAC.fractional and MONTHLY_HOLD_FRAC == dataclasses.replace(
        MONTHLY_HOLD, id="monthly-hold-frac", fractional=True
    )


def test_book_entries_are_the_registry_entries_unchanged():
    by_id = {c.id: c for c in REGISTRY}
    for e in ROSTER:
        if e.registry_id is None:
            continue
        c = by_id[e.registry_id]
        assert e.obj is c.allocator
        assert e.params == c.params
        # The rules are the candidate's, or (010) the same rules in fractional shares.
        assert e.rules == c.rules or dataclasses.replace(e.rules, id=c.rules.id, fractional=False) == c.rules
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
    assert s["initial_idr"] == "10000000"
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
    assert {e.id: e.lookback for e in ROSTER} == {
        "SPY": 1, "A": 200, F4: 253, F1: 200, "C": 200, FND: 20, F4_FR: 253, F1_FR: 200, RM: 401,
        RMW: 426, RAW: 401, MOM: 379, MVW: 253,
    }
    # FND's lookback is the 20-bar dollar-volume window: a filing's availability is its `filed`
    # date, not a bar count. RM's 401 (a 378-session market-link estimate ending a month back)
    # is the roster's longest, which is why the night loads 640 calendar days, not 550.
    assert MAX_LOOKBACK_BARS == 426  # RMW: RM's 401 plus the month's anchor, up to ~23 sessions back


def test_the_night_window_holds_the_longest_lookback():
    # Plan decision "History at night": bars since data_date − MARKET_WINDOW_DAYS calendar days.
    from seer_engine.paper.store import MARKET_WINDOW_DAYS

    assert MARKET_WINDOW_DAYS == 640
    for d in dates.sessions(date(2026, 10, 1), date(2027, 12, 31)):
        assert len(dates.sessions(d - timedelta(days=MARKET_WINDOW_DAYS), d)) >= MAX_LOOKBACK_BARS


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
    assert s["initial_idr"] == "10000000"
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


# ---- the roster is data (roster-promotion-pipeline phase 1, R2, D2) ------------------------------


from seer_engine.paper import store  # noqa: E402

ROW_COLUMNS = (
    "id", "name", "sub", "icon", "is_champion", "is_benchmark", "sort", "engine", "rules_id",
    "object_name", "registry_id", "gate_note", "gate_applicable", "status", "paper_end",
)


def a_row(**overrides) -> RosterRow:
    """A valid bracket row, with the fields a test cares about overridden."""
    base = dict(
        id="X", name="X", sub="x", icon="x", is_champion=False, is_benchmark=False, sort=9,
        engine="bracket", rules_id="design-v0", object_name="STRATEGY_A", registry_id=None,
        gate_note="not a real strategy",
    )
    return RosterRow(**{**base, **overrides})


def test_the_roster_is_built_from_the_seed_rows_through_the_resolver():
    assert ROSTER == from_rows(SEED_ROWS)
    assert tuple(r.id for r in SEED_ROWS) == ROSTER_IDS
    assert {spec_digest(spec(e)) for e in from_rows(SEED_ROWS)} == set(PINS.values())


def test_every_seed_row_names_a_resolver_object():
    assert {r.object_name for r in SEED_ROWS} <= set(RESOLVER)
    assert resolver_names() == tuple(sorted(RESOLVER))
    assert resolve(BENCHMARK_OBJECT).obj is None
    assert resolve("FACTOR").from_registry and resolve("FACTOR").params is None
    assert resolve("STRATEGY_A").params is STRATEGY_A_PARAMS


def test_an_unresolvable_object_name_is_a_named_error_not_a_skip():
    with pytest.raises(UnknownObject, match="is not in paper.roster.RESOLVER"):
        from_row(a_row(object_name="STRATEGY_Z"))
    with pytest.raises(UnknownObject):
        from_row(a_row(object_name=None))
    with pytest.raises(UnknownObject):
        resolve("nope")
    # and one bad row poisons the whole build: nothing is silently dropped
    with pytest.raises(UnknownObject):
        from_rows([*SEED_ROWS, a_row(object_name="STRATEGY_Z")])


def test_an_unknown_rules_id_is_a_named_error():
    with pytest.raises(UnknownRules, match="is not a sim.rules preset"):
        from_row(a_row(rules_id="no-such-preset"))
    with pytest.raises(BadRosterRow, match="needs a rules_id"):
        from_row(a_row(rules_id=None))


def test_a_bad_engine_or_status_is_a_named_error():
    with pytest.raises(BadRosterRow, match="engine"):
        from_row(a_row(engine="quantum"))
    with pytest.raises(BadRosterRow, match="engine"):
        from_row(a_row(engine=None))
    with pytest.raises(BadRosterRow, match="status"):
        from_row(a_row(status="zombie"))
    with pytest.raises(BadRosterRow, match="gate_note"):
        from_row(a_row(gate_note=None))


def test_a_benchmark_row_carries_no_object_rules_or_registry_id():
    ok = a_row(id="B2", engine="benchmark", rules_id=None, object_name=BENCHMARK_OBJECT)
    assert (from_row(ok).obj, from_row(ok).params, from_row(ok).lookback) == (None, None, 1)
    with pytest.raises(BadRosterRow, match="benchmark row"):
        from_row(a_row(id="B2", engine="benchmark", rules_id="design-v0", object_name=BENCHMARK_OBJECT))
    with pytest.raises(BadRosterRow, match="benchmark engine"):
        from_row(a_row(engine="bracket", object_name=BENCHMARK_OBJECT))


def test_a_registry_backed_object_needs_its_registry_id_and_an_own_params_object_refuses_one():
    with pytest.raises(BadRosterRow, match="backtest.registry"):
        from_row(a_row(engine="book", rules_id="monthly-hold", object_name="FACTOR", registry_id=None))
    with pytest.raises(BadRosterRow, match="registry_id must be NULL"):
        from_row(a_row(registry_id=F4))


def test_from_rows_sorts_by_sort_and_refuses_duplicate_ids():
    shuffled = tuple(reversed(SEED_ROWS))
    assert tuple(e.id for e in from_rows(shuffled)) == ROSTER_IDS
    with pytest.raises(BadRosterRow, match="duplicate ids"):
        from_rows([*SEED_ROWS, dataclasses.replace(SEED_ROWS[1], sort=99)])


def test_the_seed_roster_retires_the_whole_share_three_with_no_paper_end():
    assert {e.id for e in ROSTER if e.status == "retired"} == set(RETIRED)
    assert all(e.paper_end is None for e in ROSTER)  # the paper night stamps paper_end
    assert tuple(e.id for e in active(ROSTER)) == ACTIVE_IDS
    assert active() == active(ROSTER)


def test_active_drops_retired_entries_and_keeps_order():
    # RMW, not A: A is retired in SEED_ROWS itself since 013, so retiring it again would assert
    # nothing. Retiring a live entry is the case that matters -- it is what `promote --retire`
    # does on every future swap.
    rows = tuple(
        dataclasses.replace(r, status="retired", paper_end=date(2026, 10, 2)) if r.id == RMW else r
        for r in SEED_ROWS
    )
    entries = from_rows(rows)
    assert [e.id for e in entries] == list(ROSTER_IDS)  # retired rows are never dropped from the roster
    assert [e.id for e in active(entries)] == ["SPY", "C", RAW, MOM, MVW]
    rmw = next(e for e in entries if e.id == RMW)
    assert (rmw.status, rmw.paper_end) == ("retired", date(2026, 10, 2))


def test_retiring_a_strategy_does_not_move_its_digest():
    """Invariant 2 and 3: status and paper_end are lifecycle, never spec."""
    retired = from_row(dataclasses.replace(SEED_ROWS[1], status="retired", paper_end=date(2026, 10, 2)))
    assert spec_digest(spec(retired)) == PINS["A"]
    assert strategy_params(retired) == strategy_params(entry("A"))


def test_a_corrected_gate_note_does_not_move_a_digest():
    corrected = from_row(dataclasses.replace(SEED_ROWS[1], gate_note="corrected, still failed"))
    assert spec_digest(spec(corrected)) == PINS["A"]
    assert backtest_gate(corrected)["note"] == "corrected, still failed"


def test_the_migration_rows_equal_the_seed_rows(pg):
    """Invariant 7, strengthened: not just the display fields, the whole row."""
    rows = pg.execute(
        f"SELECT {', '.join(ROW_COLUMNS)} FROM strategies ORDER BY sort, id"
    ).fetchall()
    assert tuple(RosterRow(**dict(zip(ROW_COLUMNS, r))) for r in rows) == SEED_ROWS


def test_the_database_rows_rebuild_the_roster_with_the_pinned_digests(pg):
    entries = from_rows(store.read_roster_rows(pg))
    assert entries == ROSTER
    assert {e.id: spec_digest(spec(e)) for e in entries} == PINS
    assert {e.id: strategy_params(e) for e in entries} == {e.id: strategy_params(e) for e in ROSTER}


def test_read_roster_rows_reads_the_new_columns_and_defaults_them(pg):
    rows = {r.id: r for r in store.read_roster_rows(pg)}
    assert [r.id for r in store.read_roster_rows(pg)] == list(ROSTER_IDS)
    assert {r.id for r in rows.values() if r.status == "retired"} == set(RETIRED)
    assert all(r.paper_end is None for r in rows.values())
    # promoted_from defaults to NULL for every row 003/004 seeded; FND is the one row written
    # by a promotion (007_fnd.sql mirrors what `promote --method M0005` writes on the live
    # database), so it is the one row that names its provenance.
    # RM-FR (010) is the second: lab M0011, promoted to replace FND. RMW-FR (011) and the three
    # 013 rows are the rest -- every lab-derived row added after `promote` existed names its
    # method here, and only F4, F1 and their fractional twins predate it.
    assert {r.id for r in rows.values() if r.promoted_from is not None} == {FND, RM, RMW, RAW, MOM, MVW}
    assert (rows[FND].promoted_from, rows[RM].promoted_from) == ("M0005", "M0011")
    assert (rows[RAW].promoted_from, rows[MOM].promoted_from, rows[MVW].promoted_from) == (
        "M0007", "M0002", "M0008",
    )
    assert (rows["A"].object_name, rows["A"].registry_id, rows["A"].gate_applicable) == ("STRATEGY_A", None, True)
    assert (rows[F4].object_name, rows[F4].registry_id) == ("FACTOR", F4)
    assert rows["C"].gate_applicable is False
    assert rows["SPY"].object_name == BENCHMARK_OBJECT
    pg.execute("UPDATE strategies SET status = 'retired', paper_end = %s WHERE id = 'A'", (date(2026, 10, 2),))
    retired = {r.id: r for r in store.read_roster_rows(pg)}["A"]
    assert (retired.status, retired.paper_end) == ("retired", date(2026, 10, 2))
    # A is retired in SEED_ROWS since 013, so retiring it in the database changes nothing about
    # who trades: the active set is still the five the owner chose plus the SPY yardstick.
    assert [e.id for e in active(from_rows(store.read_roster_rows(pg)))] == list(ACTIVE_IDS)
    pg.rollback()


def test_the_status_check_refuses_an_unknown_status(pg):
    with pytest.raises(psycopg.errors.CheckViolation):
        pg.execute("UPDATE strategies SET status = 'zombie' WHERE id = 'A'")
    pg.rollback()


# ---- lab provenance (lab-luck-gate R4, phase 6) --------------------------------------------------
#
# The roster states where each of its lab-derived entries came from; these tests check that
# statement against the committed lab database. Importing the lab here is free -- it is
# `paper/roster.py` that must never do it (a lab-side edit would otherwise re-digest a started
# paper strategy), which is exactly why the check lives in the test file and not in the module.

import sqlite3  # noqa: E402

from seer_engine.lab import store as lab_store  # noqa: E402
from seer_engine.paper.roster import (  # noqa: E402
    BASES,
    LAB_PROVENANCE,
    LabProvenance,
)

#: Every roster entry admitted from a recorded lab candidate. A promotion adds a SEED_ROWS row
#: AND a LAB_PROVENANCE entry in the same commit; this tuple is the third place that has to name
#: it, and that is the point -- forgetting is a failing test, not a silent gap.
LAB_DERIVED = (F4, F1, FND, F4_FR, F1_FR, RM, RMW, RAW, MOM, MVW)
#: And the three that are not: SPY is the benchmark, C is the LLM strategy the quant gate does not
#: apply to, and A predates the lab (H-A records the idea but has no trial).
NOT_LAB_DERIVED = ("SPY", "A", "C")


def _lab_reachable(src: str) -> set[str]:
    """Every lab status reachable from ``src`` along ``TRANSITIONS``, ``src`` included."""
    seen, stack = {src}, [src]
    while stack:
        cur = stack.pop()
        for a, b in lab_store.TRANSITIONS:
            if a == cur and b not in seen:
                seen.add(b)
                stack.append(b)
    return seen


def test_every_entry_either_names_its_lab_candidate_or_has_none():
    assert set(LAB_DERIVED) | set(NOT_LAB_DERIVED) == set(ROSTER_IDS)
    assert not set(LAB_DERIVED) & set(NOT_LAB_DERIVED)
    assert set(LAB_PROVENANCE) == set(LAB_DERIVED)
    assert {e.id for e in ROSTER if e.lab_provenance is not None} == set(LAB_DERIVED)
    assert all(entry(i).lab_provenance is None for i in NOT_LAB_DERIVED)


def test_the_entries_name_the_variants_the_roster_advertises():
    assert (entry(RM).lab_provenance.method_id, entry(RM).lab_provenance.candidate_id) == (
        "M0011", "M0011-RAW20-TV14-N21")
    assert (entry(RMW).lab_provenance.method_id, entry(RMW).lab_provenance.candidate_id) == (
        "M0022", "M0022-W-TV16")
    assert (entry(FND).lab_provenance.method_id, entry(FND).lab_provenance.candidate_id) == (
        "M0005", "M0005-ALL")
    # the fractional twins trade the same lab candidate as the whole-share entries they replaced
    assert entry(F4_FR).lab_provenance.candidate_id == entry(F4).lab_provenance.candidate_id == F4
    assert entry(F1_FR).lab_provenance.candidate_id == entry(F1).lab_provenance.candidate_id == F1


def test_every_override_states_its_basis_and_a_reason():
    for sid, p in LAB_PROVENANCE.items():
        assert p.basis in BASES, sid
        assert p.lab_status in lab_store.STATUSES, sid
        if p.basis == "owner-override":
            assert p.reason.strip(), f"{sid}: an override must say why"
    # today every roster entry is an override admitted at 'rejected': not one of them has had a
    # test-window look. When that stops being true, this assertion is the place to say so.
    assert {p.basis for p in LAB_PROVENANCE.values()} == {"owner-override"}
    assert {p.lab_status for p in LAB_PROVENANCE.values()} == {"rejected"}
    assert set(BASES) == set(lab_store.PROMOTION_BASES)


def test_a_malformed_provenance_is_refused_where_it_is_written():
    with pytest.raises(ValueError, match="basis"):
        LabProvenance(method_id="M0001", candidate_id="M0001-A", lab_status="rejected",
                      basis="vibes", reason="r")
    with pytest.raises(ValueError, match="reason"):
        LabProvenance(method_id="M0001", candidate_id="M0001-A", lab_status="rejected",
                      basis="owner-override", reason="   ")
    with pytest.raises(ValueError, match="method_id"):
        LabProvenance(method_id="", candidate_id="M0001-A", lab_status="rejected",
                      basis="owner-override", reason="r")
    passed = LabProvenance(method_id="M0001", candidate_id="M0001-A", lab_status="test-passed",
                           basis="test-passed", reason="")
    assert (passed.basis, passed.reason) == ("test-passed", "")


def test_lab_provenance_is_not_in_the_spec():
    """Invariant 5. Provenance is a recorded fact about admission, like gate_note -- never spec."""
    other = LabProvenance(method_id="M0099", candidate_id="M0099-X", lab_status="test-passed",
                          basis="test-passed", reason="")
    for e in ROSTER:
        moved = dataclasses.replace(e, lab_provenance=other)
        assert spec_digest(spec(moved)) == PINS[e.id]
        assert strategy_params(moved) == strategy_params(e)
        assert set(strategy_params(e)) == {"spec", "digest", "backtest_gate"}


def test_every_provenance_matches_the_committed_lab_database():
    """The check that would have caught the RM/RMW divergence on the night it happened.

    The committed database, not ``SEER_LAB_DB``: a sera worktree's shared database holds sibling
    methods this tree does not have (the same reason ``test_lab_methods.py`` reads it this way).
    """
    if not lab_store.COMMITTED_DB.exists():
        pytest.skip("no lab database")
    conn = sqlite3.connect(f"file:{lab_store.COMMITTED_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        for sid, p in sorted(LAB_PROVENANCE.items()):
            method = conn.execute(
                "SELECT id, status FROM methods WHERE id = ?", (p.method_id,)
            ).fetchone()
            assert method is not None, f"{sid}: no lab method {p.method_id} in the lab database"
            dev = conn.execute(
                "SELECT eligible, failed FROM trials WHERE method_id = ? AND candidate_id = ? "
                "AND window = 'dev'",
                (p.method_id, p.candidate_id),
            ).fetchone()
            assert dev is not None, (
                f"{sid}: {p.candidate_id!r} is not a recorded dev trial of {p.method_id}"
            )
            # `lab_status` is the status AT ADMISSION and never tracks the live row. What the
            # database can still prove is that the live status is that one or forward of it,
            # because the lab's status machine moves forward only.
            assert str(method["status"]) in _lab_reachable(p.lab_status), (
                f"{sid}: admitted at lab status {p.lab_status!r}, but {p.method_id} now reads "
                f"{method['status']!r}, which is not that status or forward of it"
            )
            if p.basis == "owner-override":
                assert dev["eligible"] == 0, (
                    f"{sid}: the basis says owner-override, but {p.candidate_id} passed the dev "
                    f"gate (failed={dev['failed']!r}). Nothing was overridden -- fix the basis"
                )
            else:
                passed = conn.execute(
                    "SELECT eligible FROM trials WHERE candidate_id = ? AND window = 'test'",
                    (p.candidate_id,),
                ).fetchone()
                assert passed is not None and passed["eligible"] == 1, (
                    f"{sid}: the basis says test-passed, but no passed test-window trial for "
                    f"{p.candidate_id} is recorded"
                )
    finally:
        conn.close()


def test_lab_provenance_agrees_with_the_promoted_from_column(pg):
    """The roster's own record and the one column ``promote`` writes name the same method."""
    rows = {r.id: r for r in store.read_roster_rows(pg)}
    for sid, p in LAB_PROVENANCE.items():
        if rows[sid].promoted_from is not None:
            assert rows[sid].promoted_from == p.method_id, sid
    # the six rows `promote` wrote are the only ones with a column to agree with; F4, F1 and
    # their fractional twins were seeded by migration before `promote` existed.
    assert {i for i, r in rows.items() if r.promoted_from is not None} == {FND, RM, RMW, RAW, MOM, MVW}

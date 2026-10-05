"""Trade rules as a value (P7a phase 1): validation, DESIGN_V0 == §5, presets, cadence,
owner inputs and the plain-English description. No database needed."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime
from decimal import Decimal

import pytest

from seer_engine import dates, sim
from seer_engine.sim import model, rules
from seer_engine.sim.rules import (
    DAILY_SWITCH,
    DAILY_SWITCH_TBILL,
    DESIGN_V0,
    MONTHLY_HOLD,
    MONTHLY_HOLD_TBILL,
    PRESETS,
    SWING_T10,
    SWING_T20,
    SWING_T20_OPEN,
    LEVERS_SINCE_PINS,
    MONTHLY_RANK_WEEKLY_RESIZE,
    MONTHLY_RANK_WEEKLY_RESIZE_TBILL,
    V0_BOOK,
    WEEKLY_HOLD,
    TradeRules,
    describe_rules,
    is_decision_session,
    is_pinned_default,
    is_rank_session,
    is_resize_session,
    rule_owner_inputs,
)


def D(s: str) -> date:
    return date.fromisoformat(s)


# ============================================================== DESIGN_V0 and the presets


def test_design_v0_agrees_with_the_model_constants():
    assert DESIGN_V0.engine == "bracket_v0"
    assert DESIGN_V0.max_positions == model.SLOTS
    assert DESIGN_V0.time_stop == model.TIME_STOP_DAYS
    assert DESIGN_V0.cost_rate == model.COST_RATE
    assert DESIGN_V0.cadence == "daily"
    assert DESIGN_V0.entry == "limit"
    assert (DESIGN_V0.resize, DESIGN_V0.fractional, DESIGN_V0.dividends) == (False, False, False)
    assert DESIGN_V0.idle_symbol is None


def test_v0_book_is_design_v0_on_the_book_engine():
    assert V0_BOOK.id == "v0-book"
    assert V0_BOOK.engine == "book"
    assert replace(V0_BOOK, id="design-v0", engine="bracket_v0") == DESIGN_V0
    assert V0_BOOK not in PRESETS


def test_constants():
    assert rules.OPEN_LIMIT_BAND == Decimal("0.02")
    assert rules.RESIZE_BAND == Decimal("0.01")
    assert rules.SHARE_QUANTUM == Decimal("0.0001")
    assert rules.DEFAULT_ETFS == frozenset({"SPY", "QQQ"})
    assert rules.LEVERAGED_ETFS == frozenset({"SSO", "QLD", "UPRO", "TQQQ"})


def test_preset_values_are_pinned():
    assert MONTHLY_HOLD == TradeRules(id="monthly-hold", engine="book", cadence="monthly", entry="open_limit", resize=True)
    assert MONTHLY_HOLD_TBILL == replace(MONTHLY_HOLD, id="monthly-hold-tbill", idle_symbol="BIL")
    assert WEEKLY_HOLD == TradeRules(id="weekly-hold", engine="book", cadence="weekly", entry="open_limit", resize=True)
    assert DAILY_SWITCH == TradeRules(id="daily-switch", engine="book", cadence="daily", entry="open_limit")
    assert DAILY_SWITCH_TBILL.idle_symbol == "BIL" and DAILY_SWITCH_TBILL.resize is False
    assert SWING_T10 == TradeRules(id="swing-t10", engine="book", entry="limit", time_stop=10)
    assert SWING_T20.time_stop == 20 and SWING_T20.entry == "limit"
    assert SWING_T20_OPEN.time_stop == 20 and SWING_T20_OPEN.entry == "open_limit"
    for r in PRESETS:
        if r is not DESIGN_V0:
            assert r.engine == "book"
            assert r.dividends is True
            assert r.cost_rate == Decimal("0.001")


def test_preset_ids_are_unique_and_in_order():
    ids = [r.id for r in PRESETS]
    assert ids == [
        "design-v0",
        "monthly-hold",
        "monthly-hold-tbill",
        "weekly-hold",
        "daily-switch",
        "daily-switch-tbill",
        "swing-t10",
        "swing-t20",
        "swing-t20-open",
        "monthly-rank-weekly-resize",
        "monthly-rank-weekly-resize-tbill",
    ]
    assert len(set(ids)) == len(ids)


def test_rules_are_exported_from_sim():
    assert sim.TradeRules is TradeRules
    assert sim.DESIGN_V0 is DESIGN_V0
    assert sim.V0_BOOK is V0_BOOK
    assert sim.PRESETS is PRESETS
    assert sim.MONTHLY_HOLD is MONTHLY_HOLD
    assert sim.SWING_T20_OPEN is SWING_T20_OPEN


def test_rules_are_frozen_and_hashable():
    with pytest.raises(FrozenInstanceError):
        MONTHLY_HOLD.cadence = "daily"  # type: ignore[misc]
    assert len({*PRESETS}) == len(PRESETS)


# ============================================================== validation


def test_bracket_v0_is_reserved_for_design_v0_both_ways():
    with pytest.raises(ValueError, match="reserved for DESIGN_V0"):
        replace(DESIGN_V0, time_stop=10)
    with pytest.raises(ValueError, match="reserved for DESIGN_V0"):
        replace(DESIGN_V0, id="other")
    with pytest.raises(ValueError, match="reserved for DESIGN_V0"):
        replace(V0_BOOK, id="design-v0")
    with pytest.raises(ValueError, match="reserved for DESIGN_V0"):
        TradeRules(id="x", engine="bracket_v0")
    # An equal-valued re-construction is DESIGN_V0 itself.
    assert replace(DESIGN_V0) == DESIGN_V0


@pytest.mark.parametrize("bad", ["", "Monthly", "monthly_hold", "-x", "x-", "a--b", "a b"])
def test_id_must_be_kebab_case(bad):
    with pytest.raises(ValueError, match="kebab-case"):
        TradeRules(id=bad, engine="book")


def test_id_must_be_a_str():
    with pytest.raises(TypeError):
        TradeRules(id=1, engine="book")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "field,value",
    [("engine", "bracket"), ("cadence", "yearly"), ("entry", "market")],
)
def test_unknown_literal_values(field, value):
    kwargs = {"id": "x", "engine": "book", field: value}
    with pytest.raises(ValueError, match=f"unknown {field}"):
        TradeRules(**kwargs)


@pytest.mark.parametrize("field", ["max_positions", "time_stop"])
def test_counts(field):
    assert getattr(TradeRules(id="x", engine="book", **{field: 1}), field) == 1
    assert getattr(TradeRules(id="x", engine="book", **{field: None}), field) is None
    with pytest.raises(ValueError, match=">= 1"):
        TradeRules(id="x", engine="book", **{field: 0})
    with pytest.raises(TypeError):
        TradeRules(id="x", engine="book", **{field: True})
    with pytest.raises(TypeError):
        TradeRules(id="x", engine="book", **{field: 2.0})


@pytest.mark.parametrize("field", ["resize", "fractional", "dividends"])
def test_flags_are_bools(field):
    with pytest.raises(TypeError, match=field):
        TradeRules(id="x", engine="book", **{field: 1})


def test_idle_symbol():
    assert TradeRules(id="x", engine="book", idle_symbol="BIL").idle_symbol == "BIL"
    with pytest.raises(ValueError):
        TradeRules(id="x", engine="book", idle_symbol="")
    with pytest.raises(TypeError):
        TradeRules(id="x", engine="book", idle_symbol=5)  # type: ignore[arg-type]


def test_cost_rate():
    assert TradeRules(id="x", engine="book", cost_rate=Decimal(0)).cost_rate == 0
    assert TradeRules(id="x", engine="book", cost_rate=Decimal("0.0499")).cost_rate == Decimal("0.0499")
    with pytest.raises(TypeError):
        TradeRules(id="x", engine="book", cost_rate=0.001)  # type: ignore[arg-type]
    for bad in (Decimal("0.05"), Decimal("-0.001"), Decimal("NaN")):
        with pytest.raises(ValueError, match="cost_rate"):
            TradeRules(id="x", engine="book", cost_rate=bad)


# ============================================================== cadence


def test_daily_cadence_decides_every_session():
    for d in ("2026-10-05", "2026-10-06", "2026-11-27"):
        assert is_decision_session(DAILY_SWITCH, D(d)) is True
    assert is_decision_session(DESIGN_V0, D("2026-10-07")) is True


def test_weekly_cadence_is_the_first_session_of_each_iso_week():
    assert is_decision_session(WEEKLY_HOLD, D("2026-10-05")) is True  # Monday
    assert is_decision_session(WEEKLY_HOLD, D("2026-10-06")) is False
    assert is_decision_session(WEEKLY_HOLD, D("2026-10-09")) is False  # Friday
    # MLK day 2026-01-19 is a holiday: Tuesday opens the week.
    assert is_decision_session(WEEKLY_HOLD, D("2026-01-20")) is True
    assert is_decision_session(WEEKLY_HOLD, D("2026-01-21")) is False
    # ISO week 53 of 2026 runs into 2027: Monday 2026-12-28 opens it, 2027-01-04 the next.
    assert is_decision_session(WEEKLY_HOLD, D("2026-12-28")) is True
    assert is_decision_session(WEEKLY_HOLD, D("2026-12-31")) is False
    assert is_decision_session(WEEKLY_HOLD, D("2027-01-04")) is True


def test_monthly_cadence_is_the_first_session_of_each_month():
    assert is_decision_session(MONTHLY_HOLD, D("2026-10-01")) is True  # Thursday
    assert is_decision_session(MONTHLY_HOLD, D("2026-10-02")) is False
    assert is_decision_session(MONTHLY_HOLD, D("2026-11-02")) is True  # Monday after Oct 30
    assert is_decision_session(MONTHLY_HOLD, D("2026-01-02")) is True  # Jan 1 is a holiday
    assert is_decision_session(MONTHLY_HOLD, D("2026-10-30")) is False


def test_decision_session_rejects_non_sessions_and_bad_types():
    with pytest.raises(ValueError, match="not an NYSE session"):
        is_decision_session(MONTHLY_HOLD, D("2026-10-04"))  # Sunday
    with pytest.raises(ValueError, match="not an NYSE session"):
        is_decision_session(DAILY_SWITCH, D("2026-11-26"))  # Thanksgiving
    with pytest.raises(TypeError):
        is_decision_session(MONTHLY_HOLD, datetime(2026, 10, 1))  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        is_decision_session("monthly-hold", D("2026-10-01"))  # type: ignore[arg-type]


# ============================================================== owner inputs


def test_owner_inputs_of_the_presets():
    for r in PRESETS:
        expected = ("etf:BIL",) if r.idle_symbol == "BIL" else ()
        assert rule_owner_inputs(r) == expected, r.id
    assert rule_owner_inputs(V0_BOOK) == ()


def test_owner_inputs_every_lever_sorted():
    r = TradeRules(
        id="x", engine="book", entry="open", fractional=True, idle_symbol="IEF", cost_rate=Decimal("0.0005")
    )
    assert rule_owner_inputs(r) == ("etf:IEF", "fee", "fractional", "market-on-open")
    assert rule_owner_inputs(replace(r, idle_symbol="SPY")) == ("fee", "fractional", "market-on-open")
    assert rule_owner_inputs(replace(r, cost_rate=Decimal("0.0010"))) == ("etf:IEF", "fractional", "market-on-open")
    assert rule_owner_inputs(replace(MONTHLY_HOLD, entry="open_limit")) == ()


# ============================================================== description


def test_describe_design_v0_golden():
    assert describe_rules(DESIGN_V0) == (
        "Rule set: design-v0.",
        "Engine: the design §5 bracket simulator, unchanged.",
        "Decisions: every session, from the previous session's close.",
        "Re-scaling: only on the decision sessions above.",
        "Entry: a buy limit at the strategy's limit price for the next session; it fills only when "
        "the low trades below the limit, at the lower of the open and the limit.",
        "Positions: at most 4 at a time (the idle instrument not counted).",
        "Time stop: sell at the next open once a position has been held 5 sessions.",
        "Rebalance: none; a held position keeps its shares until it exits.",
        "Shares: whole shares only.",
        "Dividends: not credited.",
        "Idle cash: held as cash, earning nothing.",
        "Costs: 0.1% per side.",
    )


def test_describe_monthly_hold_tbill_golden():
    assert describe_rules(MONTHLY_HOLD_TBILL) == (
        "Rule set: monthly-hold-tbill.",
        "Engine: the target-weight book; a position the strategy stops wanting is sold at the next "
        "open, and stops and take-profits are fixed at entry.",
        "Decisions: the first session of each calendar month, from the previous session's close.",
        "Re-scaling: only on the decision sessions above.",
        "Entry: a buy limit at the last close + 2% for the next session; it fills only when the low "
        "trades below the limit, at the lower of the open and the limit.",
        "Positions: as many as the strategy targets.",
        "Time stop: none.",
        "Rebalance: on decision sessions, a held position is traded back to its target weight at "
        "the open when it is off by at least 1% of equity.",
        "Shares: whole shares only.",
        "Dividends: cash dividends are credited on the ex-date.",
        "Idle cash: the unallocated weight is held in BIL on decision sessions.",
        "Costs: 0.1% per side.",
    )


def test_describe_other_levers():
    r = TradeRules(
        id="x", engine="book", cadence="weekly", entry="open", fractional=True, cost_rate=Decimal("0.0015")
    )
    lines = describe_rules(r)
    assert len(lines) == 12
    assert lines[2] == "Decisions: the first session of each ISO week, from the previous session's close."
    assert lines[3] == "Re-scaling: only on the decision sessions above."
    assert lines[4] == "Entry: a market order at the next open (needs owner verification: market-on-open)."
    assert lines[8] == "Shares: fractional, rounded down to 0.0001 share (needs owner verification)."
    assert lines[11] == "Costs: 0.15% per side."
    assert describe_rules(replace(r, cost_rate=Decimal(0)))[11] == "Costs: 0% per side."
    assert describe_rules(SWING_T20)[6] == "Time stop: sell at the next open once a position has been held 20 sessions."
    assert describe_rules(SWING_T20)[4] == (
        "Entry: a buy limit at the strategy's limit price for the next session; it fills only when "
        "the low trades below the limit, at the lower of the open and the limit. A new position the "
        "strategy gives no limit price is bought at a limit of the last close + 2% instead, filled "
        "the same way."
    )
    assert all(len(describe_rules(p)) == 12 for p in PRESETS)
    assert describe_rules(DAILY_SWITCH) == describe_rules(DAILY_SWITCH)


# ============================================================== the rank/resize cadence split


def test_resize_cadence_defaults_to_none_and_every_old_preset_keeps_one_cadence():
    assert MONTHLY_HOLD.resize_cadence is None and DESIGN_V0.resize_cadence is None
    for r in PRESETS:
        if r.resize_cadence is None:
            # Before the split, "decision" meant exactly "rank": every call site stays correct.
            for d in dates.sessions(D("2026-01-02"), D("2026-12-31")):
                assert is_decision_session(r, d) is is_rank_session(r, d)
                assert is_resize_session(r, d) is False


def test_monthly_rank_weekly_resize_preset():
    r = MONTHLY_RANK_WEEKLY_RESIZE
    assert (r.id, r.cadence, r.resize_cadence, r.resize) == (
        "monthly-rank-weekly-resize", "monthly", "weekly", True
    )
    assert MONTHLY_RANK_WEEKLY_RESIZE_TBILL.idle_symbol == "BIL"
    assert replace(MONTHLY_HOLD, id=r.id, resize_cadence="weekly") == r


def test_a_rank_session_is_never_also_a_resize_session():
    r = MONTHLY_RANK_WEEKLY_RESIZE
    # 2026-10-01 (Thu) opens October but not an ISO week; 2026-10-05 (Mon) opens a week only.
    assert (is_rank_session(r, D("2026-10-01")), is_resize_session(r, D("2026-10-01"))) == (True, False)
    assert (is_rank_session(r, D("2026-10-05")), is_resize_session(r, D("2026-10-05"))) == (False, True)
    assert (is_rank_session(r, D("2026-10-06")), is_resize_session(r, D("2026-10-06"))) == (False, False)
    # 2027-01-04 (Mon) opens both the month and the week: ranking supersedes.
    assert (is_rank_session(r, D("2027-01-04")), is_resize_session(r, D("2027-01-04"))) == (True, False)
    for d in dates.sessions(D("2026-01-02"), D("2026-12-31")):
        assert not (is_rank_session(r, d) and is_resize_session(r, d))
        assert is_decision_session(r, d) is (is_rank_session(r, d) or is_resize_session(r, d))


def test_resize_cadence_must_be_faster_than_the_rank_cadence():
    for bad in ("monthly", "yearly"):
        with pytest.raises(ValueError):
            replace(MONTHLY_HOLD, id="x", resize_cadence=bad)
    with pytest.raises(ValueError, match="faster than cadence"):
        replace(WEEKLY_HOLD, id="x", resize_cadence="weekly")
    with pytest.raises(ValueError, match="faster than cadence"):
        TradeRules(id="x", engine="book", cadence="daily", resize_cadence="daily", resize=True)
    with pytest.raises(TypeError, match="resize_cadence"):
        replace(MONTHLY_HOLD, id="x", resize_cadence=7)
    # Daily resizing under a weekly or monthly rank is fine.
    assert replace(MONTHLY_HOLD, id="x", resize_cadence="daily").resize_cadence == "daily"
    assert replace(WEEKLY_HOLD, id="x", resize_cadence="daily").resize_cadence == "daily"


def test_resize_cadence_needs_resize():
    with pytest.raises(ValueError, match="needs resize=True"):
        TradeRules(id="x", engine="book", cadence="monthly", resize_cadence="weekly", resize=False)


def test_design_v0_may_not_split_its_cadence():
    with pytest.raises(ValueError, match="bracket_v0"):
        replace(DESIGN_V0, cadence="monthly", resize_cadence="weekly", resize=True)


def test_a_split_rule_set_describes_both_cadences():
    lines = describe_rules(MONTHLY_RANK_WEEKLY_RESIZE)
    assert lines[2] == "Decisions: the first session of each calendar month, from the previous session's close."
    assert lines[3].startswith("Re-scaling: on the first session of each ISO week that is not a decision session,")
    assert "nothing is ranked, entered or signal-exited" in lines[3]
    assert describe_rules(replace(MONTHLY_HOLD, id="x", resize_cadence="daily"))[3].startswith(
        "Re-scaling: on every session that is not a decision session,"
    )


def test_a_lever_added_after_the_pins_is_left_out_of_canonical_text_at_its_default():
    assert is_pinned_default("resize_cadence", None) is True
    assert is_pinned_default("resize_cadence", "weekly") is False
    assert is_pinned_default("cadence", "monthly") is False  # only post-pin levers are skippable
    assert LEVERS_SINCE_PINS == {"resize_cadence": None}

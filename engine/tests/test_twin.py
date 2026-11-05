"""Claude twins, pure: the verdict cutoff, the two wrappers and the roster's twin rules.

Plan seer-adversarial phase 2; contracts C2 and C3. No database: every DB-backed claim is in
tests/test_paper_twins.py.
"""

from __future__ import annotations

import dataclasses
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from seer_engine import dates
from seer_engine.paper import roster
from seer_engine.paper.bracket import decide_bracket
from seer_engine.paper.roster import ROSTER, SEED_ROWS, active, from_row, from_rows, spec, spec_digest
from seer_engine.sim import Pick, new_portfolio
from seer_engine.sim.book import WEIGHT_QUANTUM, Target
from seer_engine.sim.rules import DESIGN_V0, MONTHLY_HOLD, MONTHLY_RANK_WEEKLY_RESIZE, is_resize_session
from seer_engine.strategies import twin
from seer_engine.strategies.allocator import Allocator, MarketAware
from seer_engine.strategies.base import Strategy
from seer_engine.strategies.c import NewsVeto
from seer_engine.strategies.f_fundamental import FUNDAMENTAL

UTC = timezone.utc
NOV4 = date(2026, 11, 4)
OPEN_NOV4 = datetime(2026, 11, 4, 14, 30, tzinfo=UTC)  # US winter: 09:30 New York = 14:30 UTC
JUL1 = date(2026, 7, 1)
OPEN_JUL1 = datetime(2026, 7, 1, 13, 30, tzinfo=UTC)  # US summer: 09:30 New York = 13:30 UTC


# ---- the cutoff (C3) ---------------------------------------------------------------------------


def test_the_open_is_the_cutoff_and_the_latest_review_before_it_stands():
    rows = [
        (NOV4, "AAA", "object", OPEN_NOV4 - timedelta(seconds=1), 1),  # a second before: counts
        (NOV4, "BBB", "object", OPEN_NOV4, 2),  # at the open: late, ignored
        (NOV4, "CCC", "object", OPEN_NOV4 - timedelta(hours=3), 3),
        (NOV4, "CCC", "agree", OPEN_NOV4 - timedelta(hours=1), 4),  # re-reviewed in time: kept
        (NOV4, "DDD", "agree", OPEN_NOV4 - timedelta(hours=3), 5),
        (NOV4, "DDD", "object", OPEN_NOV4 - timedelta(hours=1), 6),  # re-reviewed in time: dropped
        (NOV4, "EEE", "unsure", OPEN_NOV4 - timedelta(hours=1), 7),  # can't tell = keep
        (NOV4, "FFF", "object", OPEN_NOV4 - timedelta(hours=2), 8),
        (NOV4, "FFF", "agree", OPEN_NOV4 + timedelta(hours=1), 9),  # a late re-review changes nothing
    ]
    assert twin.objected_map(rows) == {NOV4: frozenset({"AAA", "DDD", "FFF"})}


def test_the_cutoff_follows_new_york_daylight_saving():
    rows = [
        (JUL1, "AAA", "object", OPEN_JUL1 - timedelta(minutes=1), 1),
        (JUL1, "BBB", "object", OPEN_JUL1, 2),
    ]
    assert twin.objected_map(rows) == {JUL1: frozenset({"AAA"})}


def test_a_tie_on_decided_at_goes_to_the_later_row_whatever_the_read_order():
    at = OPEN_NOV4 - timedelta(hours=1)
    rows = [(NOV4, "AAA", "object", at, 1), (NOV4, "AAA", "agree", at, 2)]
    assert twin.objected_map(rows) == {}
    assert twin.objected_map(list(reversed(rows))) == {}


def test_a_bad_verdict_row_is_refused_at_the_edge():
    with pytest.raises(ValueError, match="not one of"):
        twin.objected_map([(NOV4, "AAA", "veto", OPEN_NOV4 - timedelta(hours=1), 1)])
    with pytest.raises(ValueError, match="tz-aware"):
        twin.objected_map([(NOV4, "AAA", "object", datetime(2026, 11, 4, 12), 1)])


# ---- the bracket twin --------------------------------------------------------------------------

D = date(2026, 11, 3)  # data date; its picks are for NOV4


def pick(symbol: str) -> Pick:
    return Pick(
        symbol=symbol,
        last_price=Decimal("10.0000"),
        limit_price=Decimal("10.0000"),
        tp_price=Decimal("11.0000"),
        sl_price=Decimal("9.0000"),
    )


@dataclasses.dataclass(frozen=True)
class Fixed:
    """A bracket strategy that ranks the same five picks every night."""

    ranked: tuple[Pick, ...] = tuple(pick(s) for s in ("P1", "P2", "P3", "P4", "P5"))
    id: str = "FIXED"
    lookback: int = 1

    def picks(self, history, members, data_date, params):
        return list(self.ranked)

    def prepare(self, history):
        return None

    def picks_prepared(self, prepared, members, data_date, params):
        return list(self.ranked)


def test_a_bracket_twin_without_objections_is_its_original():
    t = twin.TwinStrategy(inner=Fixed())
    assert isinstance(t, Strategy) and (t.id, t.lookback) == ("FIXED", 1)
    assert t.picks({}, frozenset(), D, None) == Fixed().picks({}, frozenset(), D, None)


def test_an_objected_pick_is_skipped_and_the_next_ranked_takes_its_slot():
    inner = Fixed()
    t = twin.TwinStrategy(inner=inner).with_objected({NOV4: {"P2"}})
    assert [p.symbol for p in t.picks({}, frozenset(), D, None)] == ["P1", "P3", "P4", "P5"]
    assert [p.symbol for p in t.picks_prepared(None, frozenset(), D, None)] == ["P1", "P3", "P4", "P5"]
    # Keyed by the session being bought for: a night deciding another session is untouched.
    assert len(t.picks({}, frozenset(), NOV4, None)) == 5
    orig = decide_bracket(new_portfolio(Decimal("10000")), inner, None, {}, frozenset(), D, rules=DESIGN_V0)
    mine = decide_bracket(new_portfolio(Decimal("10000")), t, None, {}, frozenset(), D, rules=DESIGN_V0)
    assert DESIGN_V0.max_positions == 4
    assert [o.symbol for o in orig.placed] == ["P1", "P2", "P3", "P4"]
    assert [o.symbol for o in mine.placed] == ["P1", "P3", "P4", "P5"]


# ---- the book twin -----------------------------------------------------------------------------

RANK_DATA = date(2026, 10, 30)  # decides 2026-11-02, the first session of November: a rank session
RANK = date(2026, 11, 2)


def target(symbol: str, weight: str) -> Target:
    return Target(symbol=symbol, weight=Decimal(weight), last=Decimal("10.0000"))


BOOK = (target("AAA", "0.300000"), target("BBB", "0.300000"), target("CCC", "0.200000"))  # 0.8 invested


@dataclasses.dataclass(frozen=True)
class Weights:
    """A book allocator that wants the same targets every night."""

    wanted: tuple[Target, ...] = BOOK
    id: str = "WEIGHTS"

    def lookback(self, params):
        return 1

    def symbols(self, params):
        return ()

    def holds(self, params):
        return ()

    def uses_members(self, params):
        return True

    def targets(self, history, members, data_date, held, params):
        return self.wanted

    def prepare(self, history):
        return None

    def targets_prepared(self, prepared, members, data_date, held, params):
        return self.wanted


def test_a_book_objection_drops_the_name_and_spreads_its_weight_pro_rata():
    t = twin.twin_book(Weights(), MONTHLY_HOLD).with_objected({RANK: {"BBB"}})
    got = t.targets({}, frozenset(), RANK_DATA, frozenset(), None)
    # 0.3 and 0.2 of the 0.5 kept, scaled to the original's 0.8: 0.48 and 0.32.
    assert [(x.symbol, x.weight) for x in got] == [("AAA", Decimal("0.480000")), ("CCC", Decimal("0.320000"))]
    assert t.targets_prepared(None, frozenset(), RANK_DATA, frozenset(), None) == got


def test_pro_rata_rounds_down_so_the_twin_is_never_more_invested_than_the_original():
    thirds = (target("AAA", "0.333333"), target("BBB", "0.333333"), target("CCC", "0.333333"))
    got = twin.renormalised(thirds, {"CCC"})
    assert [x.weight for x in got] == [Decimal("0.499999"), Decimal("0.499999")]
    assert sum(x.weight for x in got) <= sum(x.weight for x in thirds)
    assert all(x.weight == x.weight.quantize(WEIGHT_QUANTUM) for x in got)


def test_every_target_objected_is_the_originals_empty_decision():
    t = twin.twin_book(Weights(), MONTHLY_HOLD).with_objected({RANK: {"AAA", "BBB", "CCC"}})
    assert t.targets({}, frozenset(), RANK_DATA, frozenset(), None) == ()


def test_a_book_twin_without_objections_for_the_session_is_its_original():
    t = twin.twin_book(Weights(), MONTHLY_HOLD).with_objected({NOV4: {"AAA"}})
    assert t.targets({}, frozenset(), RANK_DATA, frozenset(), None) == BOOK
    assert isinstance(t, Allocator) and t.id == "WEIGHTS"


def test_a_resize_only_session_ignores_objections():
    resize = date(2026, 11, 9)  # a Monday, not the month's first session
    assert is_resize_session(MONTHLY_RANK_WEEKLY_RESIZE, resize)
    t = twin.twin_book(Weights(), MONTHLY_RANK_WEEKLY_RESIZE).with_objected({resize: {"AAA", "BBB", "CCC"}})
    assert t.targets({}, frozenset(), dates.prev_session(resize), frozenset(), None) == BOOK


def test_a_book_twin_is_market_aware_exactly_when_its_original_is():
    assert isinstance(FUNDAMENTAL, MarketAware)
    assert isinstance(twin.twin_book(FUNDAMENTAL, MONTHLY_HOLD), MarketAware)
    assert not isinstance(twin.twin_book(Weights(), MONTHLY_HOLD), MarketAware)


def test_a_twin_never_wraps_a_twin():
    with pytest.raises(TypeError, match="never another twin"):
        twin.TwinStrategy(inner=twin.TwinStrategy(inner=Fixed()))
    with pytest.raises(TypeError, match="never another twin"):
        twin.twin_book(twin.twin_book(Weights(), MONTHLY_HOLD), MONTHLY_HOLD)


# ---- the roster's twin rules (C2) --------------------------------------------------------------


def seed(sid: str) -> roster.RosterRow:
    return next(r for r in SEED_ROWS if r.id == sid)


def test_twin_ids_and_names():
    assert roster.twin_id("RAW35-FR-GT") == "RAW35-FR-GT-CX"
    assert roster.twin_name("RAW35 · Momentum") == "RAW35+Claude · Momentum"
    assert roster.twin_name("X") == "X+Claude"


def test_every_eligible_active_original_gets_one_twin_and_c_and_the_benchmark_none():
    plan = roster.plan_twins(SEED_ROWS)
    expected = {
        roster.twin_id(e.id)
        for e in active(ROSTER)
        if e.engine != "benchmark" and not isinstance(e.obj, NewsVeto)
    }
    assert {r.id for r in plan.create} == expected == {"A-GT-CX", "RAW35-FR-GT-CX", "COSK-FR-GT-CX"}
    assert plan.retire == ()
    for r in plan.create:
        assert r == roster.twin_row(seed(r.twin_of))
        assert (r.gate_note, r.gate_applicable, r.is_champion, r.is_benchmark) == (
            roster.TWIN_GATE_NOTE, False, False, False,
        )
    # Applying the plan leaves nothing to do, and the result builds.
    rows = (*SEED_ROWS, *plan.create)
    assert roster.plan_twins(rows).empty()
    entries = {e.id: e for e in from_rows(rows)}
    assert isinstance(entries["A-GT-CX"].obj, twin.TwinStrategy)
    assert isinstance(entries["RAW35-FR-GT-CX"].obj, twin.TwinBook)


def test_a_twins_spec_is_its_originals_plus_the_twin_marker():
    original = from_row(seed("RAW35-FR-GT"))
    t = from_row(roster.twin_row(seed("RAW35-FR-GT")))
    assert spec(t) == {
        **spec(original),
        "id": "RAW35-FR-GT-CX",
        "twin": {"of": "RAW35-FR-GT", "filter": twin.FILTER_VERSION},
    }
    assert spec_digest(spec(t)) != spec_digest(spec(original))


def test_a_retired_original_retires_its_twin_and_gets_no_new_one():
    raw = dataclasses.replace(seed("RAW35-FR-GT"), status="retired")
    rows = [raw if r.id == raw.id else r for r in SEED_ROWS] + [roster.twin_row(seed("RAW35-FR-GT"))]
    plan = roster.plan_twins(rows)
    assert plan.retire == ("RAW35-FR-GT-CX",)
    assert "RAW35-FR-GT-CX" not in {r.id for r in plan.create}


def test_an_active_twin_of_a_twin_is_retired():
    cx = roster.twin_row(seed("RAW35-FR-GT"))
    cxcx = dataclasses.replace(roster.twin_row(cx), twin_of=cx.id)
    plan = roster.plan_twins([*SEED_ROWS, cx, cxcx])
    assert plan.retire == ("RAW35-FR-GT-CX-CX",)


def test_a_used_twin_id_is_never_reused():
    retired_twin = dataclasses.replace(roster.twin_row(seed("RAW35-FR-GT")), status="retired")
    with pytest.raises(roster.RosterError, match="already exists"):
        roster.plan_twins([*SEED_ROWS, retired_twin])


def test_the_benchmark_and_c_cannot_have_a_twin():
    spy = seed("SPY-GT")
    spy_twin = dataclasses.replace(spy, id="SPY-GT-CX", twin_of="SPY-GT", is_champion=False, is_benchmark=False)
    with pytest.raises(roster.BadRosterRow, match="benchmark"):
        from_row(spy_twin)
    c_twin = dataclasses.replace(seed("C-GT"), id="C-GT-CX", twin_of="C-GT")
    with pytest.raises(roster.BadRosterRow, match="LLM critic"):
        from_row(c_twin)


def test_a_twin_must_run_its_originals_method_under_its_own_name():
    wrong_method = dataclasses.replace(roster.twin_row(seed("RAW35-FR-GT")), object_name="COSKEW")
    with pytest.raises(roster.BadRosterRow, match="runs its original's method"):
        from_rows([*SEED_ROWS, wrong_method])
    wrong_name = dataclasses.replace(roster.twin_row(seed("RAW35-FR-GT")), id="RAW35-CLAUDE")
    with pytest.raises(roster.BadRosterRow, match="must be called"):
        from_rows([*SEED_ROWS, wrong_name])
    orphan = dataclasses.replace(roster.twin_row(seed("RAW35-FR-GT")), twin_of="NOPE")
    with pytest.raises(roster.BadRosterRow, match="not a roster row"):
        from_rows([*SEED_ROWS, orphan])

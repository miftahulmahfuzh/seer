"""The one chassis a panelled signal is booked on (lab/signal_book.py; SERA_SIGNAL_PANEL_PLAN.md
phase 5, R4).

Thirty synthetic members over labkit's 473 smoke sessions, so twenty of them is a real choice, and
a SPY whose 200-day switch is off at the March to June 2015 month ends and on at the rest, so both
arms are exercised. The book is held to the allocator contract (P4 identity, no look-ahead, the
lab's lookback cap) and to what it promises: the twenty best scores of F4's screened pool, equal
weight, ties by symbol, a held name kept only while it is still among them, the gated arm empty
exactly when the switch is off.
"""

from __future__ import annotations

import math
from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest
from allocatorkit import assert_no_lookahead, assert_p4_identity, everyone
from labkit import SMOKE_FIRST, SPY_EX_DATE, smoke_history, smoke_market

from seer_engine import dates
from seer_engine.backtest.benchmark import Dividend
from seer_engine.backtest.dev import DEV_END, run_candidate
from seer_engine.backtest.market import Market, Membership
from seer_engine.lab import control_shape, runner, signal_book, tree_rank
from seer_engine.lab import signal as signals
from seer_engine.lab.method import Method, config_digest, config_text
from seer_engine.lab.real_costs import real_cost_problem
from seer_engine.sim.book import equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import Allocator, MarketAware
from seer_engine.strategies.f_factor import trend_on

DAYS = dates.sessions(SMOKE_FIRST, DEV_END)
NAMES = tuple(f"S{i:02d}" for i in range(30))
HISTORY = {s: smoke_history(s, i, DAYS) for i, s in enumerate(NAMES)}
HISTORY["SPY"] = smoke_history("SPY", 4, DAYS)
MEMBERS = everyone({s: HISTORY[s] for s in NAMES})
MONTH_ENDS = tree_rank.month_ends(date(2014, 12, 1), DEV_END)
ADDED = date(2026, 11, 13)
GATED = signal_book.BookParams()
OPEN = signal_book.BookParams(trend=None)
ON_DAY = date(2015, 1, 30)  # a month end with the switch on
TOP_BY_NAME = [f"S{i:02d}" for i in range(29, 9, -1)]


def _ret21(history, market, pool, data_date):
    """Twenty-one-session return: reads only the bars it was handed, which end at data_date."""
    out = {}
    for s in pool:
        h = history.get(s)
        if h is not None and len(h) >= 22:
            out[s] = float(h.close[-1] / h.close[-22] - 1.0)
    return out


def _by_name(history, market, pool, data_date):
    """S29 best, S00 worst: a ranking whose top twenty is known in advance."""
    return {s: float(int(s[1:])) for s in pool if s[0] == "S" and s[1:].isdigit()}


def _flat(history, market, pool, data_date):
    return {s: 1.0 for s in pool}


def _signal(score, sid="S9001", lookback=22, market_fields=()):
    return signals.Signal(
        id=sid, name="test ranking", family="test", source_kind="knowledge", source_ref="",
        hypothesis="h", expected_failure="f", lookback=lookback, score=score,
        market_fields=market_fields,
    )


def _symbols(targets):
    return [t.symbol for t in targets]


# ---- the allocator ---------------------------------------------------------------------------


def test_the_book_is_an_allocator_that_reads_members_and_holds_no_fixed_instrument():
    book = signal_book.book_allocator(_signal(_ret21))
    assert isinstance(book, Allocator)
    assert not isinstance(book, MarketAware)
    assert book.id == "SB-S9001"
    assert book.uses_members(GATED) and book.uses_members(OPEN)
    assert book.holds(GATED) == () and book.holds(OPEN) == ()
    assert book.symbols(GATED) == ("SPY",) and book.symbols(OPEN) == ()


def test_p4_identity_and_no_look_ahead_on_both_arms():
    book = signal_book.book_allocator(_signal(_ret21))
    held = [frozenset(), frozenset({"S00", "S29"})]
    nonempty = assert_p4_identity(book, HISTORY, MEMBERS, MONTH_ENDS, held, [GATED, OPEN])
    nonempty += assert_no_lookahead(
        book, HISTORY, MEMBERS, [date(2015, 4, 1), date(2015, 8, 3)], held, [GATED, OPEN]
    )
    assert nonempty > 0


def test_the_lookback_stays_inside_the_lab_cap():
    assert signal_book.book_allocator(_signal(_ret21)).lookback(GATED) == 253  # F4's 12-1 momentum screen
    longest = signal_book.book_allocator(_signal(_ret21, lookback=signals.MAX_LOOKBACK))
    assert longest.lookback(GATED) == signals.MAX_LOOKBACK


def test_the_top_twenty_by_score_at_equal_weight():
    book = signal_book.book_allocator(_signal(_by_name))
    got = book.targets(HISTORY, MEMBERS(ON_DAY), ON_DAY, frozenset(), GATED)
    assert _symbols(got) == TOP_BY_NAME
    assert {t.weight for t in got} == {equal_weight(signal_book.WIDTH)}


def test_ties_are_broken_by_symbol():
    book = signal_book.book_allocator(_signal(_flat))
    got = book.targets(HISTORY, MEMBERS(ON_DAY), ON_DAY, frozenset(), OPEN)
    assert _symbols(got) == list(NAMES[:20])


def test_a_held_name_is_kept_only_while_it_is_still_top_twenty():
    book = signal_book.book_allocator(_signal(_by_name))
    got = set(_symbols(book.targets(HISTORY, MEMBERS(ON_DAY), ON_DAY, frozenset({"S00", "S29"}), GATED)))
    assert "S29" in got
    assert "S00" not in got


def test_a_name_with_no_opinion_is_skipped():
    def gappy(history, market, pool, data_date):
        out = _by_name(history, market, pool, data_date)
        out["S29"] = math.nan
        del out["S28"]
        return out

    book = signal_book.book_allocator(_signal(gappy))
    got = book.targets(HISTORY, MEMBERS(ON_DAY), ON_DAY, frozenset(), GATED)
    assert _symbols(got) == [f"S{i:02d}" for i in range(27, 7, -1)]


def test_only_f4s_screened_pool_is_ranked():
    thin = smoke_history("THIN", 31, DAYS)
    thin = replace(thin, volume=thin.volume * 1e-4)  # 20-day dollar volume far under F4's 20M floor
    history = {**HISTORY, "THIN": thin}
    members = everyone({s: history[s] for s in (*NAMES, "THIN")})

    def loves_thin(h, market, pool, data_date):
        out = _by_name(h, market, pool, data_date)
        if "THIN" in pool:
            out["THIN"] = 1e9
        return out

    book = signal_book.book_allocator(_signal(loves_thin))
    got = _symbols(book.targets(history, members(ON_DAY), ON_DAY, frozenset(), OPEN))
    assert "THIN" not in got
    assert got == TOP_BY_NAME


def test_the_gated_arm_steps_aside_exactly_when_spy_is_under_its_200_day_average():
    book = signal_book.book_allocator(_signal(_ret21))
    switch = replace(tree_rank.SCREEN, trend=signal_book.SWITCH)
    seen = set()
    for d in MONTH_ENDS:
        on = trend_on(HISTORY, d, switch)
        seen.add(on)
        gated = book.targets(HISTORY, MEMBERS(d), d, frozenset(), GATED)
        never = book.targets(HISTORY, MEMBERS(d), d, frozenset(), OPEN)
        assert len(never) == signal_book.WIDTH
        assert gated == (never if on else ())
    assert seen == {True, False}


def test_the_chassis_has_two_settings_only():
    with pytest.raises(ValueError, match="two settings"):
        signal_book.BookParams(trend=("SPY", 100))
    assert GATED.as_dict() == {"width": "20", "trend": "SPY:200"}
    assert OPEN.as_dict() == {"width": "20", "trend": "none"}


def test_a_market_aware_signal_gets_a_market_aware_book():
    book = signal_book.book_allocator(_signal(_by_name, market_fields=("series",)))
    assert isinstance(book, MarketAware)
    assert runner.market_fields(book) == ("series",)
    assert book.targets(HISTORY, MEMBERS(ON_DAY), ON_DAY, frozenset(), OPEN) == ()
    assert book.targets_prepared(book.prepare(HISTORY), MEMBERS(ON_DAY), ON_DAY, frozenset(), OPEN) == ()
    market = Market(history=HISTORY, membership=Membership(intervals=()), fx=())
    got = book.targets_prepared(book.prepare_market(market), MEMBERS(ON_DAY), ON_DAY, frozenset(), OPEN)
    assert _symbols(got) == TOP_BY_NAME


# ---- the two standard arms -------------------------------------------------------------------


def test_standard_candidates_are_the_two_arms_of_the_one_chassis():
    gated, never = signal_book.standard_candidates(_signal(_ret21), "M0001", ADDED)
    assert (gated.id, never.id) == ("M0001-N20", "M0001-N20-NOGATE")
    assert gated.family == never.family == "M0001"
    assert gated.rules is MONTHLY_HOLD_FRAC_GOTRADE and never.rules is MONTHLY_HOLD_FRAC_GOTRADE
    assert gated.allocator is never.allocator
    assert gated.allocator.id == "SB-S9001"
    assert gated.params == GATED and never.params == OPEN
    assert gated.owner_inputs == never.owner_inputs == ()
    assert "allocator=<SB-S9001>" in config_text(gated)
    assert config_digest(gated) != config_digest(never)


def test_neither_standard_arm_reads_as_a_control():
    for c in signal_book.standard_candidates(_signal(_ret21), "M0001", ADDED):
        assert control_shape.role_of(c) != control_shape.ROLE_CONTROL


def test_the_digest_names_the_signal_not_the_method_or_the_day():
    sig = _signal(_ret21)
    first = signal_book.standard_candidates(sig, "M0001", ADDED)
    again = signal_book.standard_candidates(sig, "M0002", date(2027, 1, 1))
    assert [config_digest(c) for c in first] == [config_digest(c) for c in again]
    other = signal_book.standard_candidates(_signal(_ret21, sid="S9002"), "M0001", ADDED)
    assert not {config_digest(c) for c in first} & {config_digest(c) for c in other}


def test_a_signal_method_built_from_them_validates_at_real_fees():
    m = Method(
        id="M0901", name="t", family="test", source_kind="knowledge", source_ref="",
        hypothesis="h", expected_failure="f", signal="S9001",
        candidates=signal_book.standard_candidates(_signal(_ret21), "M0901", ADDED),
    )
    assert real_cost_problem(m) is None


def test_both_arms_run_a_smoke_window():
    market = smoke_market()
    amount = Decimal("1.0300")
    for c in signal_book.standard_candidates(_signal(_ret21), "M0001", ADDED):
        result, row = run_candidate(
            market, {"SPY": {SPY_EX_DATE: amount}}, (Dividend(SPY_EX_DATE, amount),), c
        )
        assert row.end == DEV_END
        assert len(result.snapshots) >= 2

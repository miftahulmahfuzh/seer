"""M0491's live path: the contract kit drives only ``prepare(history)``, where a market-aware
allocator targets nothing, so this module drives ``prepare_market`` on the smoke fixture with a
stand-in share panel and checks what each arm actually holds."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from labkit import MEMBER_STOCKS, smoke_market

from seer_engine import dates
from seer_engine.backtest.dev import DEV_END
from seer_engine.lab.methods import m0491_liquid_leaders_switch as m
from seer_engine.strategies.f_factor import trend_on


@pytest.fixture(scope="module")
def live():
    market = smoke_market()
    # Every member gets a size; two members share one share count, so they read as one company.
    counts = {s: float(1_000 + 100 * k) for k, s in enumerate(MEMBER_STOCKS)}
    counts["BBB"] = counts["AAA"]

    def shares_on(s, d):
        return counts.get(s)

    def market_value(s, d):
        h = market.history.get(s)
        i = None if h is None else h.index_of(d)
        return None if i is None or s not in counts else counts[s] * float(h.close[i])

    panel = SimpleNamespace(history=market.history, shares={"x": 1}, shares_on=shares_on,
                            market_value=market_value)
    return panel, m.LEADERS.prepare_market(panel)


WINDOW = (date(2015, 1, 2), DEV_END)  # the fixture's members have a full screen history by then


def _days(panel, p):
    out = [d for d in dates.sessions(*WINDOW)[::15] if trend_on(panel.history, d, p.inner)]
    assert out, "the smoke fixture never turns the switch on"
    return out


def _book(prep, d, p, held=frozenset()):
    return m.LEADERS.targets_prepared(prep, frozenset(MEMBER_STOCKS), d, held, p)


def test_equal_arm_holds_the_most_traded_names_in_equal_slots(live):
    panel, prep = live
    p = m.LeadersParams("equal", top=4)
    for d in _days(panel, p):
        rows = m._rows(prep, frozenset(MEMBER_STOCKS), d, p)
        book = _book(prep, d, p)
        assert len(book) == 4
        assert [t.symbol for t in book] == [r.symbol for r in m.most_traded(rows, 4)]
        assert len({t.weight for t in book}) <= 1


def test_cap_arm_keeps_one_class_per_company_and_respects_the_ceiling(live):
    panel, prep = live
    p = m.LeadersParams("cap", top=4, cap=0.30)
    for d in _days(panel, p):
        book = _book(prep, d, p)
        names = {t.symbol for t in book}
        assert len(book) == 4
        assert not {"AAA", "BBB"} <= names
        assert sum(t.weight for t in book) <= Decimal(1)
        assert max(t.weight for t in book) <= Decimal("0.30")


def test_draw_arm_is_blind_but_matched_in_size(live):
    panel, prep = live
    p = m.LeadersParams("draw", top=4, seed=1)
    held: frozenset[str] = frozenset()
    for d in _days(panel, p):
        pool = {r.symbol for r in m._rows(prep, frozenset(MEMBER_STOCKS), d, p)}
        book = _book(prep, d, p, held)
        assert {t.symbol for t in book} <= pool
        assert len(pool) == 8 and len(book) == 4
        held = frozenset(t.symbol for t in book)


def test_spy_arm_holds_only_spy_and_only_while_the_switch_is_on(live):
    panel, prep = live
    p = m.LeadersParams("spy")
    for d in dates.sessions(*WINDOW)[::15]:
        book = _book(prep, d, p)
        if trend_on(panel.history, d, p.inner):
            assert [t.symbol for t in book] == ["SPY"]
        else:
            assert book == ()


def test_params_refuse_a_misplaced_dial():
    with pytest.raises(ValueError):
        m.LeadersParams("equal", cap=0.1)
    with pytest.raises(ValueError):
        m.LeadersParams("cap", seed=2, cap=0.1)
    with pytest.raises(ValueError):
        m.LeadersParams("draw")

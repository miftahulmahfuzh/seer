"""Interest on idle cash (measure-then-learn phase 2, R2): the ``cash_yield`` lever.

``TradeRules.cash_yield`` names a market series (only ``T13W``, the 13-week T-bill yield, percent)
whose rate idle cash earns: ``q(cash x rate x calendar days / 36500)`` at each open, on the cash
held at the previous close, before dividends, the rate as published by the previous session.
Every rule set without it must run exactly as before -- the preset pins below were taken on the
tree before the lever existed. No database needed.
"""

from __future__ import annotations

import hashlib
from dataclasses import replace
from decimal import Decimal

import pytest
from allocatorkit import FIXED, FixedParams
from simkit import D, P, bar
from stratkit import hist
from test_book_runner import FIXTURE_IDR, W_END, W_START, Scripted, wiring_market

from seer_engine import dates, research, sim
from seer_engine.backtest import registry
from seer_engine.backtest.book_runner import BookResult, cash_rate_on, run_book, run_rules
from seer_engine.backtest.market import Market, MarketSeries, Membership
from seer_engine.commands import promote
from seer_engine.paper import roster
from seer_engine.paper.book import decide_book, settle_book
from seer_engine.sim.book import Book, BookStep, Position, accrued_interest, new_book, step_book
from seer_engine.sim.contributions import OWNER_MONTHLY
from seer_engine.sim.rules import (
    CASH_YIELD_SERIES,
    DAILY_SWITCH,
    DESIGN_V0,
    DESIGN_V0_GOTRADE,
    LEVERS_SINCE_PINS,
    MONTHLY_HOLD,
    MONTHLY_HOLD_FRAC_GOTRADE,
    PRESETS,
    V0_BOOK,
    TradeRules,
    describe_rules,
    is_pinned_default,
    rule_owner_inputs,
)

CASH = replace(DAILY_SWITCH, id="daily-switch-cash", cash_yield="T13W")
SERIES = MarketSeries({"T13W": [(D("2025-02-13"), 4.0), (D("2025-02-28"), 5.0)]})


# ============================================================== the lever


def test_cash_yield_defaults_to_none_and_is_a_pinned_no_op():
    assert TradeRules(id="x", engine="book").cash_yield is None
    # Every preset that predates the lever (the first 16). Phase 3 appends cash-yield presets after
    # them; asserting over all of PRESETS would turn red the moment it does.
    assert len(PRESETS) >= 16
    assert all(r.cash_yield is None for r in PRESETS[:16])
    assert DESIGN_V0.cash_yield is None and V0_BOOK.cash_yield is None
    assert LEVERS_SINCE_PINS["cash_yield"] is None
    assert list(LEVERS_SINCE_PINS)[-1] == "cash_yield"
    assert is_pinned_default("cash_yield", None) is True
    assert is_pinned_default("cash_yield", "T13W") is False


def test_cash_yield_series_are_series_the_research_store_holds():
    assert CASH_YIELD_SERIES == ("T13W",)
    assert set(CASH_YIELD_SERIES) <= set(research.MARKET_SERIES_NAMES)
    assert sim.CASH_YIELD_SERIES is CASH_YIELD_SERIES and "CASH_YIELD_SERIES" in sim.__all__


def test_cash_yield_validation():
    with pytest.raises(ValueError, match="unknown cash_yield"):
        replace(DAILY_SWITCH, id="x", cash_yield="T10Y")
    with pytest.raises(TypeError, match="cash_yield"):
        replace(DAILY_SWITCH, id="x", cash_yield=4)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="book-engine"):
        replace(DESIGN_V0_GOTRADE, id="x", cash_yield="T13W")
    with pytest.raises(ValueError, match="book-engine"):
        replace(DESIGN_V0, cash_yield="T13W")
    with pytest.raises(ValueError, match="idle_symbol"):
        replace(DAILY_SWITCH, id="x", idle_symbol="BIL", cash_yield="T13W")
    assert CASH.cash_yield == "T13W"


def test_canonical_text_leaves_the_lever_out_at_none_and_names_it_when_set():
    assert "cash_yield" not in registry._canon(DAILY_SWITCH)
    assert "cash_yield='T13W'" in registry._canon(CASH)
    assert "cash_yield" not in roster.rules_dict(DAILY_SWITCH)
    assert roster.rules_dict(CASH)["cash_yield"] == "T13W"


def test_cash_yield_is_an_owner_input():
    assert rule_owner_inputs(CASH) == ("cash-yield",)
    assert rule_owner_inputs(replace(CASH, entry="open")) == ("cash-yield", "market-on-open")
    assert rule_owner_inputs(DAILY_SWITCH) == ()


def test_describe_rules_idle_cash_line():
    base = replace(MONTHLY_HOLD_FRAC_GOTRADE, id="cash-test")
    lines = describe_rules(replace(base, cash_yield="T13W"))
    plain = describe_rules(base)
    assert len(lines) == 12
    assert plain[10] == "Idle cash: held as cash, earning nothing."
    assert lines[10] == (
        "Idle cash: held as cash and credited the 13-week US Treasury bill yield, read at the "
        "previous session's close, for the calendar days since the last session, at each open "
        "(needs owner verification: cash-yield)."
    )
    assert lines[:10] == plain[:10] and lines[11:] == plain[11:]


# ============================================================== the accrual


def test_accrued_interest_is_simple_act_365():
    assert accrued_interest(P("1000"), Decimal("5"), 1) == P("0.1370")  # 1000 x 5 / 36500 = 0.136986
    assert accrued_interest(P("1000"), Decimal("5"), 3) == P("0.4110")  # a weekend: 0.410959
    assert accrued_interest(P("1000"), Decimal("4.057"), 1) == P("0.1112")  # 0.111150
    assert accrued_interest(P("0"), Decimal("5"), 3) == 0
    assert accrued_interest(P("-10"), Decimal("5"), 3) == 0
    assert accrued_interest(P("1000"), Decimal("0"), 3) == 0
    with pytest.raises(ValueError, match=">= 0"):
        accrued_interest(P("1000"), Decimal("-0.1"), 1)
    with pytest.raises(TypeError):
        accrued_interest(P("1000"), 5.0, 1)  # type: ignore[arg-type]


def _cash_book(cash: str, last: str) -> Book:
    return Book(cash=P(cash), equity=P(cash), positions=(), last_session=D(last))


def test_step_book_credits_interest_on_overnight_cash_at_the_open():
    # Fri 2026-10-09 -> Mon 2026-10-12: three calendar days at 5%.
    got = step_book(_cash_book("1000", "2026-10-09"), D("2026-10-12"), {}, None, CASH, cash_rate=Decimal("5"))
    assert got.interest == P("0.4110")
    assert got.book.cash == P("1000.4110") and got.snapshot.cash_usd == P("1000.4110")
    assert got.snapshot.equity_usd == P("1000.4110")


def test_a_deposit_credited_at_this_open_earns_nothing_for_the_gap():
    b = _cash_book("1312.5", "2026-10-09")  # 1000 overnight + 312.5 deposited at Monday's open
    got = step_book(b, D("2026-10-12"), {}, None, CASH, cash_rate=Decimal("5"), deposited=P("312.5"))
    assert got.interest == P("0.4110")
    assert got.book.cash == P("1312.9110")


def test_a_book_never_stepped_earns_nothing():
    got = step_book(new_book(P("1000")), D("2026-10-12"), {}, None, CASH, cash_rate=Decimal("5"))
    assert got.interest == 0 and got.book.cash == P("1000")


def test_interest_is_on_cash_only_and_dividends_do_not_earn_it():
    p = Position("AAA", Decimal(10), P("50"), D("2026-10-01"), P("50"), 3, P("500.5"), P("0"), None, None)
    b = Book(cash=P("1000"), equity=P("1500"), positions=(p,), last_session=D("2026-10-09"))
    bars = {"AAA": bar("AAA", "2026-10-12", 50, 51, 49, 50)}
    got = step_book(b, D("2026-10-12"), bars, None, CASH, {"AAA": Decimal("1")}, cash_rate=Decimal("5"))
    assert got.interest == P("0.4110")  # on the 1000 of cash, not on the 500 of stock or the dividend
    assert got.dividends == (("AAA", P("10")),)
    assert got.book.cash == P("1010.4110")


def test_rules_and_rate_must_agree():
    b = _cash_book("1000", "2026-10-09")
    with pytest.raises(ValueError, match="pass that yield"):
        step_book(b, D("2026-10-12"), {}, None, CASH)
    with pytest.raises(ValueError, match="cash_rate must be None"):
        step_book(b, D("2026-10-12"), {}, None, DAILY_SWITCH, cash_rate=Decimal("5"))
    with pytest.raises(ValueError, match="needs a cash_rate"):
        step_book(b, D("2026-10-12"), {}, None, DAILY_SWITCH, deposited=P("1"))
    with pytest.raises(ValueError, match=">= 0"):
        step_book(b, D("2026-10-12"), {}, None, CASH, cash_rate=Decimal("-1"))
    with pytest.raises(ValueError, match="deposited must be in"):
        step_book(b, D("2026-10-12"), {}, None, CASH, cash_rate=Decimal("5"), deposited=P("1000.0001"))
    with pytest.raises(TypeError):
        step_book(b, D("2026-10-12"), {}, None, CASH, cash_rate=5.0)  # type: ignore[arg-type]


def test_without_the_lever_a_step_credits_nothing():
    got = step_book(_cash_book("1000", "2026-10-09"), D("2026-10-12"), {}, None, DAILY_SWITCH)
    assert isinstance(got, BookStep) and got.interest == 0
    assert got.book.cash == P("1000")


# ============================================================== the runner


def _cash_market() -> Market:
    return wiring_market().with_series(SERIES)


def test_cash_rate_on_reads_the_series_point_in_time():
    m = _cash_market()
    assert cash_rate_on(m, "T13W", D("2025-02-27")) == Decimal("4.0")
    assert cash_rate_on(m, "T13W", D("2025-02-28")) == Decimal("5.0")
    assert cash_rate_on(m, "T13W", D("2025-03-03")) == Decimal("5.0")  # latest on or before
    with pytest.raises(ValueError, match="no value on or before"):
        cash_rate_on(m, "T13W", D("2025-02-12"))
    negative = wiring_market().with_series(MarketSeries({"T13W": [(D("2025-02-13"), -0.02)]}))
    assert cash_rate_on(negative, "T13W", D("2025-02-20")) == 0


def test_run_book_credits_idle_cash_from_the_previous_sessions_yield():
    """Nothing is targeted, so the book is pure cash. 2025-02-24 is the first session (no night
    before it in the book: no interest). 02-25: q(1250 x 4 / 36500) = 0.1370, then the 312.50
    deposit lands at that open and earns nothing for the gap. 02-26: q(1562.6370 x 4 / 36500) =
    0.1712. From 03-03 (data_date 02-28) the rate is 5%, and 02-28 -> 03-03 is three days."""
    r = run_book(
        _cash_market(), Scripted(), None, CASH, W_START, W_END,
        initial_idr=FIXTURE_IDR, contributions=OWNER_MONTHLY,
    )
    by_date = {s.date: s for s in r.snapshots}
    assert by_date[D("2025-02-24")].cash_usd == P("1250")
    assert by_date[D("2025-02-25")].cash_usd == P("1562.6370")
    assert by_date[D("2025-02-26")].cash_usd == P("1562.8082")
    expected = P("1250")
    prev = None
    total = Decimal(0)
    for s in dates.sessions(W_START, W_END):
        if prev is not None:
            rate = Decimal(5) if prev >= D("2025-02-28") else Decimal(4)
            gain = accrued_interest(expected, rate, (s - prev).days)
            expected += gain
            total += gain
        if s == D("2025-02-25"):
            expected += P("312.5")
        assert by_date[s].cash_usd == expected == by_date[s].equity_usd, s
        prev = s
    assert r.interest_usd == total > 0
    assert r.cashflows == ((D("2025-02-25"), P("312.5")),)  # interest is not a cashflow
    assert run_rules(
        _cash_market(), Scripted(), None, CASH, W_START, W_END,
        initial_idr=FIXTURE_IDR, contributions=OWNER_MONTHLY,
    ) == r


def test_run_book_refuses_a_market_without_the_series():
    with pytest.raises(ValueError, match="carries no T13W series"):
        run_book(wiring_market(), Scripted(), None, CASH, W_START, W_END, initial_idr=FIXTURE_IDR)


def test_a_rule_set_without_the_lever_ignores_the_series():
    plain = run_book(wiring_market(), Scripted(), None, DAILY_SWITCH, W_START, W_END, initial_idr=FIXTURE_IDR)
    seen = run_book(_cash_market(), Scripted(), None, DAILY_SWITCH, W_START, W_END, initial_idr=FIXTURE_IDR)
    assert plain == seen
    assert plain.interest_usd == 0
    assert BookResult.__dataclass_fields__["interest_usd"].default == 0


# ============================================================== every existing preset, unchanged

PIN_DAYS = dates.sessions(D("2024-12-02"), D("2025-05-30"))
PIN_START, PIN_END = D("2025-01-15"), D("2025-05-30")
PIN_PARAMS = FixedParams((("AAA", Decimal("0.45")), ("BBB", Decimal("0.35"))))
PIN_DIVIDENDS = {
    "AAA": {D("2025-02-20"): Decimal("0.10"), D("2025-05-15"): Decimal("0.12")},
    "BBB": {D("2025-03-03"): Decimal("0.20")},
}

# sha256 of each run's (snapshots, fills, trades, open_at_end, dividends, costs, rejections,
# cashflows) repr, taken on 5faa3cb, before the lever existed. A mismatch means an existing rule
# set's results moved: invariant 2 broken. Never re-pin to make this pass.
PRESET_RUN_PINS: dict[str, str] = {
    "v0-book": "7a3eeb8ae05944df3d78306114aac53201367f2a9c8054ffd1b94b6dd6d5a897",
    "monthly-hold": "008e8c6aeaf46ae553b79c377fe9b58972b380429a63d5895ad82c5bce75d6f0",
    "monthly-hold-tbill": "7ab3042f57019626dc02b24f92c58371fc07ec847b2b9a9fa8b7c6d44399a830",
    "weekly-hold": "60b1231fd8667e7a7efa594e1ed242d1bd93bd8fdc30265b960ab94aa705a50c",
    "daily-switch": "ef06b49ff7dc58939df6b101b295455dfd9003144d1d27231c16ca396420b708",
    "daily-switch-tbill": "b85aa67de685edbcfeafa7a5a7022ce7112fd19ee1fd9eb82a40a7cb8cf173ed",
    "swing-t10": "618019963efa2addb9742ab72d51020a1008d96f51641c05307780a654caefcb",
    "swing-t20": "bbc4f51f296b26bf368458e18e5f94b791a8d37fdad0022b0eaa87d1feea12fe",
    "swing-t20-open": "bbc4f51f296b26bf368458e18e5f94b791a8d37fdad0022b0eaa87d1feea12fe",
    "monthly-rank-weekly-resize": "8724812a6257a282a4339420802fd50be41d61beea0ea40a982b70e3dd5d391b",
    "monthly-rank-weekly-resize-tbill": "7ee7b496e7e4919efd28835fa26aa843bf87035d4f0a12141fbc1453b95d4475",
    "monthly-hold-frac": "7d345b779e67b46e78ef9799b67c35912d19e7a0d521046031e95c7f6ccffca8",
    "monthly-rank-weekly-resize-frac": "abc3dad0631fa93c79ee5c22f09b234f58eb32f256b96d4246cc537195204c10",
    "monthly-hold-frac-gotrade": "a9ea0460115f6aaf0c94ac8587331b541f08cecced150f4b8a12059fc411abed",
    "monthly-rank-weekly-resize-frac-gotrade": "b5a7ea5dd15653acd7db73237c8a2df22610bd1a267752ce2112f84b77ef4c2f",
}


def pin_market() -> Market:
    n = len(PIN_DAYS)
    aaa = hist("AAA", [round(10.0 + 0.05 * t + (1.5 if (t // 7) % 2 else 0.0), 2) for t in range(n)], days=PIN_DAYS)
    bbb = hist("BBB", [round(40.0 - 0.04 * t + (2.0 if (t // 11) % 2 else 0.0), 2) for t in range(n)], days=PIN_DAYS)
    bil = hist("BIL", [100.0] * n, days=PIN_DAYS, spread=0.05)
    return Market(
        history={"AAA": aaa, "BBB": bbb, "BIL": bil},
        membership=Membership((("AAA", D("2020-01-02"), None), ("BBB", D("2020-01-02"), None))),
        fx=((D("2024-11-29"), Decimal("16000")),),
    )


def run_digest(r: BookResult) -> str:
    text = repr((r.snapshots, r.fills, r.trades, r.open_at_end, r.dividends_usd, r.costs_usd, r.rejections, r.cashflows))
    return hashlib.sha256(text.encode()).hexdigest()


@pytest.mark.parametrize("rules_id", sorted(PRESET_RUN_PINS))
@pytest.mark.parametrize("with_series", [False, True], ids=["no-series", "series"])
def test_every_existing_book_preset_runs_exactly_as_before(rules_id, with_series):
    by_id = {r.id: r for r in (V0_BOOK, *PRESETS)}
    market = pin_market().with_series(SERIES) if with_series else pin_market()
    r = run_book(
        market, FIXED, PIN_PARAMS, by_id[rules_id], PIN_START, PIN_END,
        dividends=PIN_DIVIDENDS, contributions=OWNER_MONTHLY,
    )
    assert run_digest(r) == PRESET_RUN_PINS[rules_id]
    assert r.interest_usd == 0


def test_the_pins_cover_every_book_preset_that_predates_the_lever():
    # Presets added after this phase (phase 3's fixed-tape presets) are not pinned here; every
    # one that existed before the lever is.
    before = {"v0-book"} | {r.id for r in PRESETS if r.engine == "book"} - {
        r.id for r in PRESETS if r.cash_yield is not None or getattr(r, "resize_basis", "equity") != "equity"
    }
    assert before == set(PRESET_RUN_PINS)


# ============================================================== paper and promote refuse it


def test_paper_refuses_cash_yield_rules():
    with pytest.raises(ValueError, match="lab only"):
        decide_book(_cash_market(), Scripted(), None, CASH, D("2025-02-24"), frozenset())
    with pytest.raises(ValueError, match="lab only"):
        settle_book(
            _cash_book("1000", "2025-02-24"), D("2025-02-25"), {}, None, False, CASH, {}, (), lambda s: None
        )


def test_promote_refuses_cash_yield_rules():
    with pytest.raises(promote.NotPromotable, match="interest on idle cash"):
        promote._check_rules(CASH)
    promote._check_rules(MONTHLY_HOLD)  # an ordinary preset still passes


# ============================================================== the lab smoke market


def test_a_cash_yield_rule_set_runs_on_the_lab_smoke_market_given_its_series():
    from labkit import SMOKE_T13W, smoke_market

    from seer_engine.backtest.dev import DEV_END

    cash = replace(MONTHLY_HOLD_FRAC_GOTRADE, id="monthly-hold-frac-gotrade-cash-test", cash_yield="T13W")
    params = FixedParams((("AAA", Decimal("0.45")), ("BBB", Decimal("0.35"))))
    start = D("2015-01-02")
    with pytest.raises(ValueError, match="carries no T13W series"):
        run_book(smoke_market(), FIXED, params, cash, start, DEV_END)
    r = run_book(smoke_market().with_series(SMOKE_T13W), FIXED, params, cash, start, DEV_END)
    assert r.interest_usd > 0  # a fifth of the book waits in cash at 4% a year
    assert smoke_market().series.names() == ()  # opt-in: the shared fixture is unchanged

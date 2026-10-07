"""Point-in-time fundamental factors (phase 7; requirement R6).

Hand-computed features, eligibility (including the Gap-A case: filings but no bar), the five
rankings, both sizings, the staleness gate, the market-level prepared identity, no look-ahead
on bars and on ``filed``, and an end-to-end dev-window run of every SUE-free M0005 variant.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

import pytest
from allocatorkit import assert_no_lookahead, assert_p4_identity, everyone
from stratkit import hist, session_days

from seer_engine.backtest.benchmark import Dividend
from seer_engine.backtest.dev import DEV_END, run_candidate
from seer_engine.backtest.market import Market, Membership
# The TEST module imports phase 5 and phase 6 directly; the allocator under test imports
# neither (C4). A Market's `fundamentals` field is type-checked, so a fake will not do there.
from seer_engine.fundamentals import Fact, FundamentalPanel
from seer_engine.lab.methods.m0005_fundamental_factors import METHOD
from seer_engine.prices import to_decimal
from seer_engine.sim.book import equal_weight
from seer_engine.strategies.allocator import Allocator, MarketAware
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import FACTOR
from seer_engine.strategies.f_fundamental import (
    DV_N,
    EMPTY_PANEL,
    EXCLUDED,
    FACTORS,
    FUNDAMENTAL,
    FundamentalParams,
    FundamentalPrepared,
    Panel,
    composite_scores,
    factors_read,
    fundamental_lookback,
    fundamental_rows,
    fundamental_weights,
    rank_rows,
    targets_with_panel,
    zscores,
)

SYMBOLS: tuple[str, ...] = ("AAA", "BBB", "CCC", "DDD", "EEE")
# "No floor" is the lowest the validator allows, not zero: FundamentalParams rejects
# min_price < 0.01 (and test_params_reject_bad_values pins that). Every fixture close is
# >= 50, so 0.01 excludes nothing the test means to keep.
NO_FLOOR = {"min_dollar_volume": 0.0, "min_price": 0.01}


# --------------------------------------------------------------------------- a synthetic panel


class FakePanel:
    """A ``Panel`` over plain dicts, with ``filed`` honoured as the availability boundary.

    ``facts[symbol]`` is a list of ``(filed, {metric: value})``. A read at ``data_date`` takes
    the latest entry with ``filed <= data_date``; entries filed later are invisible, which is
    what the no-look-ahead tests exercise.

    It satisfies ``f_fundamental.Panel`` structurally -- one method, ``as_of`` (C1). It is used
    ONLY for the pure functions that take a panel as an argument. The tests that build a
    ``Market`` use a real ``seer_engine.fundamentals.FundamentalPanel`` instead, because phase
    6's ``Market.__post_init__`` type-checks the field and would reject this (C4).
    """

    def __init__(self, facts: dict[str, list[tuple[date, dict[str, float]]]]) -> None:
        self.facts = {s: sorted(rows, key=lambda r: r[0]) for s, rows in facts.items()}

    def as_of(self, symbol: str, data_date: date) -> FakeSnapshot | None:
        """The latest fixture row with ``filed <= data_date``.

        None when the fixture has never heard of the symbol -- the same distinction phase 5's
        ``FundamentalPanel.as_of`` draws. A symbol it knows but has nothing visible for yet
        also gets None here; phase 5 would return a snapshot of NaNs, and both make the symbol
        ineligible, which is the property the tests assert.
        """
        if symbol not in self.facts:
            return None
        found: tuple[date, dict[str, float]] | None = None
        for filed, values in self.facts[symbol]:
            if filed <= data_date:
                found = (filed, values)
        return None if found is None else FakeSnapshot(filed=found[0], **found[1])


@dataclass(frozen=True, slots=True)
class FakeSnapshot:
    """The seven Snapshot members the allocator reads. Flows are ANNUAL (C2), not TTM."""

    filed: date
    equity: float
    assets: float
    shares_outstanding: float
    net_income: float
    gross_profit: float
    sue: float


def facts(
    *,
    equity: float,
    assets: float,
    shares: float,
    net_income: float,
    gross_profit: float,
    sue: float,
) -> dict[str, float]:
    """One annual observation. ``net_income`` and ``gross_profit`` are FISCAL-YEAR figures."""
    return {
        "equity": equity,
        "assets": assets,
        "shares_outstanding": shares,
        "net_income": net_income,
        "gross_profit": gross_profit,
        "sue": sue,
    }


def _fact(symbol: str, taxonomy: str, tag: str, unit: str, period_start: date | None,
          period_end: date, val: float, filed: date) -> Fact:
    """One ``Fact``, with ``accn``/``form``/``fy``/``fp`` filled from the filed date."""
    return Fact(symbol=symbol, taxonomy=taxonomy, tag=tag, unit=unit, period_start=period_start,
                period_end=period_end, val=float(val), accn=f"{symbol}-{tag}-{filed:%Y%m%d}",
                form="10-K", fy=period_end.year, fp="FY", filed=filed)


def real_panel(rows: dict[str, list[tuple[date, dict[str, float]]]]) -> FundamentalPanel:
    """A genuine phase-5 panel from synthetic facts, for the tests that build a Market.

    Phase 6 type-checks Market.fundamentals, so FakePanel is rejected there. Going through
    real Facts is better coverage anyway: it exercises phase 5's point-in-time selection and
    its annual/instant classification rather than a dict lookup.

    SUE is deliberately not synthesisable this way: phase 5 computes it from a quarterly
    diluted-EPS series, which these annual facts do not carry, so ``Snapshot.sue`` is NaN on
    every panel this helper builds. That is what ``SUE_FREE`` below exists for.
    """
    out: list[Fact] = []
    for symbol, observations in rows.items():
        for filed, values in observations:
            year_end = date(filed.year - 1, 12, 31)
            year_start = date(year_end.year, 1, 1)
            out.append(_fact(symbol, "us-gaap", "Assets", "USD", None, year_end,
                             values["assets"], filed))
            out.append(_fact(symbol, "us-gaap", "StockholdersEquity", "USD", None, year_end,
                             values["equity"], filed))
            out.append(_fact(symbol, "dei", "EntityCommonStockSharesOutstanding", "shares",
                             None, year_end, values["shares_outstanding"], filed))
            out.append(_fact(symbol, "us-gaap", "NetIncomeLoss", "USD",
                             year_start, year_end, values["net_income"], filed))
            out.append(_fact(symbol, "us-gaap", "GrossProfit", "USD",
                             year_start, year_end, values["gross_profit"], filed))
    return FundamentalPanel.from_facts(tuple(out))


@pytest.fixture(scope="module")
def days() -> list[date]:
    return session_days(60, date(2015, 1, 2))


@pytest.fixture(scope="module")
def history(days) -> dict[str, History]:
    out: dict[str, History] = {}
    for k, symbol in enumerate(SYMBOLS):
        closes = [50.0 + 3.0 * k + 0.1 * t for t in range(len(days))]
        out[symbol] = hist(symbol, closes, days=days, volumes=[1_000_000.0] * len(days))
    out["SPY"] = hist("SPY", [200.0 + 0.2 * t for t in range(len(days))], days=days,
                      volumes=[5_000_000.0] * len(days))
    return out


@pytest.fixture(scope="module")
def panel(days) -> FakePanel:
    filed = days[0] - timedelta(days=30)
    # value = equity / (shares x close); close on day 19 is 50, 53, 56, 59, 62 + 1.9
    return FakePanel({
        "AAA": [(filed, facts(equity=1000.0, assets=4000.0, shares=100.0,
                              net_income=200.0, gross_profit=800.0, sue=1.0))],
        "BBB": [(filed, facts(equity=2000.0, assets=4000.0, shares=100.0,
                              net_income=100.0, gross_profit=400.0, sue=2.0))],
        "CCC": [(filed, facts(equity=3000.0, assets=4000.0, shares=100.0,
                              net_income=900.0, gross_profit=1200.0, sue=-1.0))],
        "DDD": [(filed, facts(equity=4000.0, assets=4000.0, shares=100.0,
                              net_income=400.0, gross_profit=200.0, sue=0.5))],
        # EEE files nothing: it has bars, no fundamentals (the inverse of the Gap-A case).
    })


@pytest.fixture(scope="module")
def real_panel_fx(days) -> FundamentalPanel:
    """The same observations as ``panel``, as a REAL phase-5 FundamentalPanel.

    Market.fundamentals is type-checked (C4), so the tests that construct a Market use this
    rather than FakePanel. Snapshot.sue is NaN here -- phase 5 computes SUE from a quarterly
    EPS series this synthetic panel does not carry -- so those tests rank on a non-SUE factor.
    """
    filed = days[0] - timedelta(days=30)
    return real_panel({
        "AAA": [(filed, facts(equity=1000.0, assets=4000.0, shares=100.0,
                              net_income=200.0, gross_profit=800.0, sue=1.0))],
        "BBB": [(filed, facts(equity=2000.0, assets=4000.0, shares=100.0,
                              net_income=100.0, gross_profit=400.0, sue=2.0))],
        "CCC": [(filed, facts(equity=3000.0, assets=4000.0, shares=100.0,
                              net_income=900.0, gross_profit=1200.0, sue=-1.0))],
        "DDD": [(filed, facts(equity=4000.0, assets=4000.0, shares=100.0,
                              net_income=400.0, gross_profit=200.0, sue=0.5))],
    })


@pytest.fixture(scope="module")
def members() -> frozenset[str]:
    return frozenset(SYMBOLS) | {"SPY"}


def day_of(days: list[date], i: int) -> date:
    return days[i]


# --------------------------------------------------------------------------- params


def test_params_defaults_and_as_dict():
    p = FundamentalParams(rank="composite")
    assert p.top == 20 and p.sizing == "equal" and p.trend is None and p.max_stale_days == 400
    assert p.as_dict() == {
        "rank": "composite",
        "top": "20",
        "sizing": "equal",
        "weights": "1:1:1:1",
        "min_dollar_volume": "20000000",
        "min_price": "5",
        "max_stale_days": "400",
        "trend": "none",
    }


@pytest.mark.parametrize("kwargs", [
    {"rank": "momentum"},
    {"rank": "value", "top": 0},
    {"rank": "value", "top": 1001},
    {"rank": "value", "sizing": "inverse_vol"},
    {"rank": "value", "weights": (1.0, 1.0, 1.0)},
    {"rank": "value", "weights": (0.0, 0.0, 0.0, 0.0)},
    {"rank": "value", "weights": (-1.0, 1.0, 1.0, 1.0)},
    {"rank": "value", "min_dollar_volume": -1.0},
    {"rank": "value", "min_price": 0.0},
    {"rank": "value", "max_stale_days": 0},
    {"rank": "value", "trend": ("SPY",)},
])
def test_params_reject_bad_values(kwargs):
    with pytest.raises((TypeError, ValueError)):
        FundamentalParams(**kwargs)


def test_lookback_is_the_dollar_volume_window_unless_a_trend_is_longer():
    assert fundamental_lookback(FundamentalParams(rank="value")) == DV_N
    assert fundamental_lookback(FundamentalParams(rank="value", trend=("SPY", 200))) == 200
    assert fundamental_lookback(FundamentalParams(rank="value", trend=("SPY", 5))) == DV_N


def test_factors_read():
    assert factors_read(FundamentalParams(rank="sue")) == ("sue",)
    assert factors_read(FundamentalParams(rank="composite")) == FACTORS


# --------------------------------------------------------------------------- features


def test_features_are_hand_computable(history, panel, members, days):
    d = day_of(days, 19)  # the 20th bar: exactly DV_N
    p = FundamentalParams(rank="composite", **NO_FLOOR)
    rows = {r.symbol: r for r in fundamental_rows(history, panel, members, d, p)}
    assert sorted(rows) == ["AAA", "BBB", "CCC", "DDD"]  # EEE files nothing, SPY is EXCLUDED
    aaa = rows["AAA"]
    close = 50.0 + 0.1 * 19
    assert aaa.close == pytest.approx(close)
    assert aaa.dollar_volume == pytest.approx(
        sum((50.0 + 0.1 * t) * 1_000_000.0 for t in range(0, 20)) / 20
    )
    assert aaa.market_cap == pytest.approx(100.0 * close)
    assert aaa.value == pytest.approx(1000.0 / (100.0 * close))
    assert aaa.quality == pytest.approx(200.0 / 1000.0)
    assert aaa.profitability == pytest.approx(800.0 / 4000.0)
    assert aaa.sue == pytest.approx(1.0)


def test_spy_is_never_a_row(history, panel, members, days):
    p = FundamentalParams(rank="value", **NO_FLOOR)
    rows = fundamental_rows(history, panel, members, day_of(days, 25), p)
    assert "SPY" in EXCLUDED
    assert all(r.symbol != "SPY" for r in rows)


def test_a_symbol_with_filings_but_no_bar_is_absent_not_zero(history, panel, members, days):
    """Gap A: 133 ever-members have fundamentals and no price bars. They must drop out silently."""
    d = day_of(days, 25)
    p = FundamentalParams(rank="value", **NO_FLOOR)
    with_bars = fundamental_rows(history, panel, members, d, p)
    no_bar_history = {s: h for s, h in history.items() if s != "CCC"}
    without = fundamental_rows(no_bar_history, panel, members | {"CCC"}, d, p)
    assert {r.symbol for r in with_bars} - {r.symbol for r in without} == {"CCC"}
    assert all(math.isfinite(r.value) and r.value > 0.0 for r in without)
    # and the allocator does not crash or target it
    targets = targets_with_panel(no_bar_history, panel, members | {"CCC"}, d, frozenset(), p)
    assert all(t.symbol != "CCC" for t in targets)


def test_a_symbol_with_bars_but_no_filings_is_absent(history, panel, members, days):
    p = FundamentalParams(rank="value", **NO_FLOOR)
    rows = fundamental_rows(history, panel, members, day_of(days, 25), p)
    assert all(r.symbol != "EEE" for r in rows)


def test_too_few_bars_is_not_eligible(history, panel, members, days):
    p = FundamentalParams(rank="value", **NO_FLOOR)
    assert fundamental_rows(history, panel, members, day_of(days, DV_N - 2), p) == []
    assert fundamental_rows(history, panel, members, day_of(days, DV_N - 1), p) != []


def test_price_and_liquidity_floors(history, panel, members, days):
    d = day_of(days, 25)
    high_price = FundamentalParams(rank="value", min_price=1e9, min_dollar_volume=0.0)
    assert fundamental_rows(history, panel, members, d, high_price) == []
    high_dv = FundamentalParams(rank="value", min_price=0.01, min_dollar_volume=1e15)
    assert fundamental_rows(history, panel, members, d, high_dv) == []


def test_stale_filings_drop_out(history, members, days):
    d = day_of(days, 25)
    stale = FakePanel({"AAA": [(d - timedelta(days=500),
                                facts(equity=1.0, assets=1.0, shares=1.0,
                                      net_income=1.0, gross_profit=1.0, sue=0.0))]})
    p = FundamentalParams(rank="value", **NO_FLOOR)
    assert fundamental_rows(history, stale, members, d, p) == []
    lenient = FundamentalParams(rank="value", max_stale_days=600, **NO_FLOOR)
    assert [r.symbol for r in fundamental_rows(history, stale, members, d, lenient)] == ["AAA"]


def test_an_empty_panel_makes_everything_ineligible(history, members, days):
    p = FundamentalParams(rank="composite", **NO_FLOOR)
    assert fundamental_rows(history, EMPTY_PANEL, members, day_of(days, 25), p) == []


def test_eligibility_only_requires_the_factors_the_ranking_reads(history, members, days):
    d = day_of(days, 25)
    filed = days[0] - timedelta(days=30)
    # FakeSnapshot's fields have no defaults, so a "partial" snapshot is one whose unknown
    # legs are NaN -- which is exactly what phase 5's Snapshot carries for an unresolved
    # concept. Omitting the keys would be a TypeError, not a partial snapshot.
    partial = FakePanel(
        {"AAA": [(filed, {"equity": 1000.0, "shares_outstanding": 100.0,
                          "assets": float("nan"), "net_income": float("nan"),
                          "gross_profit": float("nan"), "sue": float("nan")})]}
    )
    assert [r.symbol for r in fundamental_rows(history, partial, members, d,
                                               FundamentalParams(rank="value", **NO_FLOOR))] == ["AAA"]
    assert fundamental_rows(history, partial, members, d,
                            FundamentalParams(rank="sue", **NO_FLOOR)) == []
    assert fundamental_rows(history, partial, members, d,
                            FundamentalParams(rank="composite", **NO_FLOOR)) == []


# --------------------------------------------------------------------------- ranking and weights


def test_zscores():
    assert zscores([]) == []
    assert zscores([3.0]) == [0.0]
    assert zscores([2.0, 2.0, 2.0]) == [0.0, 0.0, 0.0]
    got = zscores([1.0, 2.0, 3.0])
    assert got[0] == pytest.approx(-math.sqrt(1.5))
    assert got[1] == pytest.approx(0.0)
    assert got[2] == pytest.approx(math.sqrt(1.5))


@pytest.mark.parametrize("rank,expected", [
    ("quality", ["CCC", "AAA", "DDD", "BBB"]),        # 0.30, 0.20, 0.10, 0.05
    ("profitability", ["CCC", "AAA", "BBB", "DDD"]),  # 0.30, 0.20, 0.10, 0.05
    ("sue", ["BBB", "AAA", "DDD", "CCC"]),            # 2.0, 1.0, 0.5, -1.0
])
def test_single_factor_rankings(history, panel, members, days, rank, expected):
    d = day_of(days, 25)
    p = FundamentalParams(rank=rank, top=4, **NO_FLOOR)
    rows = fundamental_rows(history, panel, members, d, p)
    assert [r.symbol for r in rank_rows(rows, p)] == expected


def test_value_ranking_is_book_over_market_cap(history, panel, members, days):
    d = day_of(days, 25)
    p = FundamentalParams(rank="value", top=4, **NO_FLOOR)
    rows = fundamental_rows(history, panel, members, d, p)
    by_value = sorted(rows, key=lambda r: (-r.value, r.symbol))
    assert [r.symbol for r in rank_rows(rows, p)] == [r.symbol for r in by_value]
    # equity rises 1000..4000 while close rises only 50..59, so DDD is the cheapest book
    assert by_value[0].symbol == "DDD"


def test_ties_break_by_symbol_ascending(history, members, days):
    d = day_of(days, 25)
    filed = days[0] - timedelta(days=30)
    same = facts(equity=1000.0, assets=1000.0, shares=100.0,
                 net_income=100.0, gross_profit=100.0, sue=7.0)
    flat = FakePanel({s: [(filed, dict(same))] for s in ("CCC", "AAA", "BBB")})
    p = FundamentalParams(rank="sue", top=3, **NO_FLOOR)
    rows = fundamental_rows(history, flat, members, d, p)
    assert [r.symbol for r in rank_rows(rows, p)] == ["AAA", "BBB", "CCC"]


def test_composite_uses_every_weighted_factor(history, panel, members, days):
    d = day_of(days, 25)
    p = FundamentalParams(rank="composite", top=4, **NO_FLOOR)
    rows = fundamental_rows(history, panel, members, d, p)
    scores = composite_scores(rows, p)
    assert len(scores) == len(rows)
    assert sum(scores) == pytest.approx(0.0, abs=1e-9)  # z-scores are centred, weights are equal
    only_sue = FundamentalParams(rank="composite", top=4, weights=(0.0, 0.0, 0.0, 1.0), **NO_FLOOR)
    assert composite_scores(rows, only_sue) == pytest.approx(
        zscores([r.sue for r in rows])
    )
    assert [r.symbol for r in rank_rows(rows, only_sue)] == \
           [r.symbol for r in rank_rows(rows, FundamentalParams(rank="sue", top=4, **NO_FLOOR))]


def test_top_truncates(history, panel, members, days):
    d = day_of(days, 25)
    p = FundamentalParams(rank="sue", top=2, **NO_FLOOR)
    rows = fundamental_rows(history, panel, members, d, p)
    assert [r.symbol for r in rank_rows(rows, p)] == ["BBB", "AAA"]


def test_equal_sizing_leaves_the_rest_in_cash(history, panel, members, days):
    d = day_of(days, 25)
    p = FundamentalParams(rank="sue", top=10, **NO_FLOOR)
    chosen = rank_rows(fundamental_rows(history, panel, members, d, p), p)
    weights = fundamental_weights(chosen, p)
    assert len(chosen) == 4
    assert weights == [equal_weight(10)] * 4
    assert sum(weights, Decimal(0)) == equal_weight(10) * 4


def test_rank_sizing_is_linear_and_matches_equal_exposure(history, panel, members, days):
    d = day_of(days, 25)
    p = FundamentalParams(rank="sue", top=10, sizing="rank", **NO_FLOOR)
    chosen = rank_rows(fundamental_rows(history, panel, members, d, p), p)
    weights = fundamental_weights(chosen, p)
    assert len(weights) == 4 and all(w is not None for w in weights)
    assert all(weights[i] > weights[i + 1] for i in range(3))
    equal = FundamentalParams(rank="sue", top=10, **NO_FLOOR)
    equal_total = sum(fundamental_weights(chosen, equal), Decimal(0))
    assert abs(sum(weights, Decimal(0)) - equal_total) <= Decimal("0.00001")


def test_weights_never_exceed_one(history, panel, members, days):
    d = day_of(days, 25)
    for sizing in ("equal", "rank"):
        p = FundamentalParams(rank="composite", top=4, sizing=sizing, **NO_FLOOR)
        chosen = rank_rows(fundamental_rows(history, panel, members, d, p), p)
        total = sum((w for w in fundamental_weights(chosen, p) if w is not None), Decimal(0))
        assert total <= Decimal(1)


# --------------------------------------------------------------------------- the trend gate


def test_trend_gate_blocks_everything_when_off(history, panel, members, days):
    d = day_of(days, 40)
    on = FundamentalParams(rank="sue", trend=("SPY", 20), **NO_FLOOR)
    assert targets_with_panel(history, panel, members, d, frozenset(), on) != ()
    falling = dict(history)
    falling["SPY"] = hist("SPY", [300.0 - 0.5 * t for t in range(len(days))], days=days,
                          volumes=[5_000_000.0] * len(days))
    assert targets_with_panel(falling, panel, members, d, frozenset(), on) == ()


def test_trend_gate_needs_a_bar_on_the_day(history, panel, members, days):
    d = day_of(days, 40)
    p = FundamentalParams(rank="sue", trend=("MISSING", 20), **NO_FLOOR)
    assert targets_with_panel(history, panel, members, d, frozenset(), p) == ()


# --------------------------------------------------------------------------- the allocator


def test_allocator_shape():
    assert isinstance(FUNDAMENTAL, Allocator)
    # The dispatch contract: defining prepare_market is what makes dev.py's prepare_for hand
    # this allocator the whole Market, and what the shared lab gate branches on (C3).
    assert isinstance(FUNDAMENTAL, MarketAware)
    # Adding prepare_market must NOT have been done by widening Allocator: that would make
    # isinstance False for every structural implementer and break eight production sites.
    # FACTOR is such an implementer -- an Allocator with no prepare_market -- so this pair is
    # the consequence, and it holds on every Python version.
    assert isinstance(FACTOR, Allocator) and not isinstance(FACTOR, MarketAware)
    # The same thing said directly on the member set: sharper, but `__protocol_attrs__` is a
    # CPython internal added in 3.12 and CI runs 3.11, so it is read through getattr and is
    # vacuous there. A skip is not available -- the CI step fails the job on any `^SKIPPED`.
    assert "prepare_market" not in getattr(Allocator, "__protocol_attrs__", frozenset())
    assert FUNDAMENTAL.id == "FND"
    p = FundamentalParams(rank="value")
    assert FUNDAMENTAL.symbols(p) == () and FUNDAMENTAL.holds(p) == ()
    assert FUNDAMENTAL.uses_members(p) is True
    assert FUNDAMENTAL.symbols(FundamentalParams(rank="value", trend=("SPY", 50))) == ("SPY",)


def test_history_only_path_targets_nothing(history, members, days):
    """The documented degenerate case: prepare(history) has no panel, so nothing is eligible."""
    p = FundamentalParams(rank="composite", **NO_FLOOR)
    d = day_of(days, 30)
    assert FUNDAMENTAL.targets(history, members, d, frozenset(), p) == ()
    prepared = FUNDAMENTAL.prepare(history)
    assert isinstance(prepared, FundamentalPrepared)
    assert prepared.panel is EMPTY_PANEL
    assert FUNDAMENTAL.targets_prepared(prepared, members, d, frozenset(), p) == ()


def test_prepare_market_carries_the_panel(history, real_panel_fx, members, days):
    """A REAL FundamentalPanel: Market type-checks the field, so FakePanel is rejected (C4)."""
    market = Market(
        history=history,
        membership=Membership(intervals=tuple((s, days[0], None) for s in SYMBOLS)),
        fx=((days[0], Decimal("14000")),),
        fundamentals=real_panel_fx,
    )
    prepared = FUNDAMENTAL.prepare_market(market)
    assert isinstance(prepared, FundamentalPrepared)
    assert prepared.panel is real_panel_fx
    # Phase 5's FundamentalPanel satisfies this module's one-method Panel protocol, which is
    # the whole point of keeping the protocol to `as_of`.
    assert isinstance(prepared.panel, Panel)


def test_prepare_market_tolerates_a_market_with_no_panel(history, days):
    market = Market(
        history=history,
        membership=Membership(intervals=tuple((s, days[0], None) for s in SYMBOLS)),
        fx=((days[0], Decimal("14000")),),
    )
    assert FUNDAMENTAL.prepare_market(market).panel is EMPTY_PANEL


def test_targets_prepared_rejects_a_foreign_prepared_value(members, days):
    with pytest.raises(TypeError):
        FUNDAMENTAL.targets_prepared({}, members, day_of(days, 30), frozenset(),
                                     FundamentalParams(rank="value"))


def test_market_identity_prepared_equals_single_window(history, real_panel_fx, members, days):
    """The identity that matters here: the prepared path equals the panel path, bit for bit.

    Over a REAL FundamentalPanel (C4), so this also exercises phase 5's point-in-time
    selection rather than a fixture dict. ``rank`` is "profitability" rather than "composite"
    because SUE is NaN on a synthetic panel with no quarterly EPS history -- see the module
    docstring and the SUE-ranking test, which covers the SUE leg over ``FakePanel``.
    """
    p = FundamentalParams(rank="profitability", top=3, **NO_FLOOR)
    market = Market(
        history=history,
        membership=Membership(intervals=tuple((s, days[0], None) for s in SYMBOLS)),
        fx=((days[0], Decimal("14000")),),
        fundamentals=real_panel_fx,
    )
    prepared = FUNDAMENTAL.prepare_market(market)
    nonempty = 0
    for d in days[DV_N - 1 :: 7]:
        for held in (frozenset(), frozenset({"AAA", "BBB"})):
            window = {s: h.upto(d) for s, h in history.items()}
            single = targets_with_panel(window, real_panel_fx, members, d, held, p)
            assert targets_with_panel(history, real_panel_fx, members, d, held, p) == single, d
            assert FUNDAMENTAL.targets_prepared(prepared, members, d, held, p) == single, d
            for t in single:
                assert t.last == to_decimal(float(history[t.symbol].close[history[t.symbol].index_of(d)]))
            nonempty += bool(single)
    assert nonempty > 0, "the identity check proved nothing"


def test_no_lookahead_on_filed(history, members, days):
    """A fact filed after d must not change d's targets, however early its period ended."""
    d = day_of(days, 30)
    early = days[0] - timedelta(days=30)
    base = {
        "AAA": [(early, facts(equity=1000.0, assets=4000.0, shares=100.0,
                              net_income=200.0, gross_profit=800.0, sue=1.0))],
        "BBB": [(early, facts(equity=2000.0, assets=4000.0, shares=100.0,
                              net_income=100.0, gross_profit=400.0, sue=2.0))],
    }
    p = FundamentalParams(rank="sue", top=2, **NO_FLOOR)
    before = targets_with_panel(history, FakePanel(base), members, d, frozenset(), p)
    assert before != ()
    restated = {s: list(rows) for s, rows in base.items()}
    restated["AAA"].append((d + timedelta(days=1),
                            facts(equity=9.0, assets=9.0, shares=9.0,
                                  net_income=9.0, gross_profit=9.0, sue=99.0)))
    assert targets_with_panel(history, FakePanel(restated), members, d, frozenset(), p) == before
    # and the same fact filed on d itself DOES change them
    on_the_day = {s: list(rows) for s, rows in base.items()}
    on_the_day["AAA"].append((d, facts(equity=9.0, assets=9.0, shares=9.0,
                                       net_income=9.0, gross_profit=9.0, sue=99.0)))
    assert targets_with_panel(history, FakePanel(on_the_day), members, d, frozenset(), p) != before


def test_allocator_contract_on_the_history_only_path(history, days):
    """allocatorkit, as every allocator gets it. Vacuous by design here; it must still hold."""
    p = FundamentalParams(rank="composite", **NO_FLOOR)
    probe = days[DV_N :: 9]
    assert assert_p4_identity(FUNDAMENTAL, history, everyone(history), probe,
                              [frozenset(), frozenset({"AAA"})], [p]) == 0
    assert assert_no_lookahead(FUNDAMENTAL, history, everyone(history), probe,
                               [frozenset(), frozenset({"AAA"})], [p]) == 0


# --------------------------------------------------------------------------- the lab method


def test_method_shape():
    assert METHOD.id == "M0005"
    assert 1 <= len(METHOD.candidates) <= 6
    assert {c.allocator.id for c in METHOD.candidates} == {"FND"}
    assert {c.family for c in METHOD.candidates} == {"M0005"}
    ranks = {c.params.rank for c in METHOD.candidates}
    assert {"value", "quality", "profitability", "sue", "composite"} <= ranks
    for c in METHOD.candidates:
        assert c.allocator.lookback(c.params) == DV_N  # fits the dev window and the smoke market


# The parametrisation is COMPUTED, not a hand-kept list of four ids. `factors_read` returns
# every factor a variant ranks on, and `rank="composite"` reads all of them -- so the SUE-free
# set is {value, quality, profitability} and the composites are NOT in it. An earlier draft
# parametrised over all six candidates while its own docstring said four; three of them would
# have ranked on NaN, returned no targets, and tripped `trades > 0`.
SUE_FREE = [c for c in METHOD.candidates if "sue" not in factors_read(c.params)]
SUE_RANKING = [c for c in METHOD.candidates if "sue" in factors_read(c.params)]


@pytest.mark.parametrize("c", SUE_FREE, ids=[c.id for c in SUE_FREE])
def test_every_sue_free_variant_runs_a_dev_window_with_a_real_panel(c):
    """End to end: a dev-window market that carries a panel, through dev.run_candidate."""
    days = [d for d in session_days(460, date(2014, 1, 2)) if d <= DEV_END]
    filed = days[0] - timedelta(days=30)
    history: dict[str, History] = {}
    rows: dict[str, list[tuple[date, dict[str, float]]]] = {}
    for k in range(30):
        symbol = f"S{k:02d}"
        history[symbol] = hist(symbol, [20.0 + k + 0.05 * t for t in range(len(days))],
                               days=days, volumes=[3_000_000.0] * len(days))
        rows[symbol] = [(filed, facts(equity=500.0 + 50.0 * k, assets=5000.0,
                                      net_income=100.0 + 10.0 * k, shares=200.0,
                                      gross_profit=300.0 + 20.0 * k, sue=float(k % 7) - 3.0))]
    # `sue` in the fixture is ignored by real_panel: phase 5 computes SUE from a quarterly EPS
    # series this synthetic panel does not have (it needs sue.MIN_QUARTERS of diluted EPS), so
    # Snapshot.sue is NaN. Hence SUE_FREE above; the SUE leg is covered by the FakePanel
    # ranking tests, which are pure-function tests that never touch a Market.
    history["SPY"] = hist("SPY", [180.0 + 0.05 * t for t in range(len(days))], days=days,
                          volumes=[9_000_000.0] * len(days))
    market = Market(
        history=history,
        membership=Membership(intervals=tuple((s, days[0], None) for s in history if s != "SPY")),
        fx=((days[0], Decimal("13000")),),
        fundamentals=real_panel(rows),
    )
    ex_date = days[len(days) // 2]
    amount = Decimal("1.0300")
    prepared = FUNDAMENTAL.prepare_market(market)
    result, row = run_candidate(market, {"SPY": {ex_date: amount}}, (Dividend(ex_date, amount),), c,
                                prepared=prepared)
    assert row.end == DEV_END
    assert len(result.snapshots) >= 2
    assert row.stats.metrics.trades > 0, f"{c.id} never traded, so the run proved nothing"


@pytest.mark.parametrize("c", SUE_RANKING, ids=[c.id for c in SUE_RANKING])
def test_a_sue_ranking_variant_on_a_sue_less_panel_ranks_nothing_and_does_not_crash(c):
    """The other half of the split, and the behaviour that matters operationally.

    A panel with no quarterly EPS series gives Snapshot.sue = NaN. `fundamental_rows` drops a
    row whose wanted factor is non-finite, so a SUE-ranking variant finds nobody eligible and
    returns (). It must do that quietly -- all cash, no exception, no NaN leaking into a
    weight -- because that is exactly what it will do in the lab until the ingest has enough
    quarters of history. Asserting it here is what stops that from looking like a bug later.

    The control assertion is what makes this load-bearing: the very same symbol, panel and day
    ARE eligible for a SUE-free ranking under the variant's own liquidity floors, so the only
    thing dropping it here is the non-finite ``sue``.
    """
    days = session_days(40, date(2015, 1, 2))
    d = days[-1]
    history = {"AAA": hist("AAA", [50.0] * len(days), days=days,
                           volumes=[1_000_000.0] * len(days))}
    names = frozenset({"AAA"})
    panel = real_panel({"AAA": [(days[0] - timedelta(days=30),
                                 facts(equity=1000.0, assets=5000.0, shares=200.0,
                                       net_income=100.0, gross_profit=300.0, sue=1.0))]})
    snap = panel.as_of("AAA", d)
    assert snap is not None and math.isnan(snap.sue)
    control = FundamentalParams(rank="profitability", top=c.params.top, sizing=c.params.sizing)
    assert [r.symbol for r in fundamental_rows(history, panel, names, d, control)] == ["AAA"]
    assert fundamental_rows(history, panel, names, d, c.params) == []
    assert targets_with_panel(history, panel, names, d, frozenset(), c.params) == ()

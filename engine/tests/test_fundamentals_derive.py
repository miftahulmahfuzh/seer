"""Pure derivation over SEC XBRL facts: the concept ladder, point-in-time selection, SUE (R3).

The 8-filer coverage test reproduces the measurement taken against ``data.sec.gov`` on
2026-10-05 over ATVI, TWTR, CELG, TWX, SIVB, PXD, WRK and K: which of the nine metrics each
filer tags, and with which element. Only those nine are measurements. The ``CostOfRevenue``
leg in the same fixture is a construction, not a measurement: it exists to exercise the three
gross-profit bases -- reported (CELG, WRK), derived (the five with a cost line) and none
(SIVB, a bank with no cost of revenue at all).
"""

from __future__ import annotations

import math
from datetime import date, timedelta

import numpy as np
import pytest

from seer_engine.fundamentals import ladder, sue
from seer_engine.fundamentals.panel import (
    EMPTY_PANEL,
    FACT_COLUMNS,
    GROSS_PROFIT_DERIVED,
    GROSS_PROFIT_NONE,
    GROSS_PROFIT_REPORTED,
    KIND_ANNUAL,
    KIND_INSTANT,
    KIND_QUARTER,
    Fact,
    FundamentalPanel,
    FundamentalsError,
    SymbolFundamentals,
    book_value_per_share,
    fact_from_row,
    facts_from_rows,
    gross_profitability,
    return_on_equity,
)

# ---- builders ------------------------------------------------------------------------------


def fact(
    symbol: str,
    tag: str,
    period_end: date,
    val: float,
    filed: date,
    *,
    start: date | None = None,
    taxonomy: str = "us-gaap",
    unit: str = "USD",
    accn: str = "0000000001-16-000001",
    form: str = "10-K",
    fy: int | None = None,
    fp: str | None = None,
) -> Fact:
    return Fact(symbol, taxonomy, tag, unit, start, period_end, float(val), accn, form, fy, fp, filed)


def annual_fact(symbol: str, tag: str, year: int, val: float, filed: date, **kw: object) -> Fact:
    return fact(symbol, tag, date(year, 12, 31), val, filed, start=date(year, 1, 1), **kw)  # type: ignore[arg-type]


FY15_FILED = date(2016, 2, 20)
T_AFTER_FY15 = date(2016, 6, 30)

# ---- the measured concept ladder -------------------------------------------------------------

MEASURED_REVENUE_TAG = {
    "ATVI": "Revenues",
    "TWTR": "Revenues",
    "CELG": "Revenues",
    "TWX": "Revenues",
    "SIVB": "RevenueFromContractWithCustomerExcludingAssessedTax",
    "PXD": "Revenues",
    "WRK": "Revenues",
    "K": "Revenues",
}
NO_OPERATING_INCOME = frozenset({"SIVB", "PXD"})
HAS_GROSS_PROFIT = frozenset({"CELG", "WRK"})
NO_COST_OF_REVENUE = frozenset({"SIVB"})  # fixture, not a measurement: a bank has no cost line
FILERS = tuple(MEASURED_REVENUE_TAG)


def measured_panel() -> FundamentalPanel:
    facts: list[Fact] = []
    for i, symbol in enumerate(FILERS):
        accn = f"000000000{i}-16-000001"
        facts.append(annual_fact(symbol, MEASURED_REVENUE_TAG[symbol], 2015, 1000.0, FY15_FILED, accn=accn))
        facts.append(annual_fact(symbol, "NetIncomeLoss", 2015, 120.0, FY15_FILED, accn=accn))
        facts.append(
            annual_fact(
                symbol, "NetCashProvidedByUsedInOperatingActivities", 2015, 150.0, FY15_FILED, accn=accn
            )
        )
        facts.append(
            annual_fact(
                symbol, "EarningsPerShareDiluted", 2015, 1.25, FY15_FILED, unit="USD/shares", accn=accn
            )
        )
        facts.append(fact(symbol, "Assets", date(2015, 12, 31), 5000.0, FY15_FILED, accn=accn))
        facts.append(fact(symbol, "StockholdersEquity", date(2015, 12, 31), 2000.0, FY15_FILED, accn=accn))
        facts.append(
            fact(
                symbol,
                "EntityCommonStockSharesOutstanding",
                date(2016, 2, 15),
                400.0,
                FY15_FILED,
                taxonomy="dei",
                unit="shares",
                accn=accn,
            )
        )
        if symbol not in NO_OPERATING_INCOME:
            facts.append(annual_fact(symbol, "OperatingIncomeLoss", 2015, 200.0, FY15_FILED, accn=accn))
        if symbol in HAS_GROSS_PROFIT:
            facts.append(annual_fact(symbol, "GrossProfit", 2015, 400.0, FY15_FILED, accn=accn))
        if symbol not in NO_COST_OF_REVENUE:
            facts.append(annual_fact(symbol, "CostOfRevenue", 2015, 600.0, FY15_FILED, accn=accn))
    return FundamentalPanel.from_facts(facts)


def test_the_ladder_reproduces_the_measured_coverage():
    panel = measured_panel()
    assert panel.names() == tuple(sorted(FILERS))
    for symbol in FILERS:
        s = panel.as_of(symbol, T_AFTER_FY15)
        assert s is not None
        assert s.tag(ladder.REVENUE) == MEASURED_REVENUE_TAG[symbol], symbol
        for concept in (
            ladder.NET_INCOME,
            ladder.ASSETS,
            ladder.EQUITY,
            ladder.OPERATING_CASH_FLOW,
            ladder.DILUTED_EPS,
            ladder.SHARES_OUTSTANDING,
        ):
            assert math.isfinite(s.value(concept)), f"{symbol}: {concept}"
        if symbol in NO_OPERATING_INCOME:
            assert math.isnan(s.operating_income), symbol
        else:
            assert s.operating_income == 200.0, symbol


def test_the_measured_coverage_counts_are_eight_eight_six_and_two():
    panel = measured_panel()
    snaps = [panel.as_of(symbol, T_AFTER_FY15) for symbol in FILERS]
    assert sum(math.isfinite(s.revenue) for s in snaps) == 8
    assert sum(math.isfinite(s.net_income) for s in snaps) == 8
    assert sum(math.isfinite(s.assets) for s in snaps) == 8
    assert sum(math.isfinite(s.equity) for s in snaps) == 8
    assert sum(math.isfinite(s.operating_cash_flow) for s in snaps) == 8
    assert sum(math.isfinite(s.diluted_eps) for s in snaps) == 8
    assert sum(math.isfinite(s.shares_outstanding) for s in snaps) == 8
    assert sum(math.isfinite(s.operating_income) for s in snaps) == 6
    assert sum(s.gross_profit_basis == GROSS_PROFIT_REPORTED for s in snaps) == 2
    assert {s.symbol for s in snaps if s.gross_profit_basis == GROSS_PROFIT_REPORTED} == HAS_GROSS_PROFIT


def test_the_revenue_tag_variant_is_sivbs_alone():
    panel = measured_panel()
    tags = {s: panel.as_of(s, T_AFTER_FY15).tag(ladder.REVENUE) for s in FILERS}
    assert sorted(set(tags.values())) == [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
    ]
    assert tags["SIVB"] == "RevenueFromContractWithCustomerExcludingAssessedTax"


# ---- gross profit: reported, derived, refused --------------------------------------------------


def test_gross_profit_is_read_when_the_filer_tags_it():
    s = measured_panel().as_of("CELG", T_AFTER_FY15)
    assert s.gross_profit == 400.0
    assert s.gross_profit_basis == GROSS_PROFIT_REPORTED
    assert s.tag(ladder.GROSS_PROFIT) == "GrossProfit"


def test_gross_profit_falls_back_to_revenue_minus_cost_of_revenue():
    s = measured_panel().as_of("ATVI", T_AFTER_FY15)
    assert s.gross_profit == 400.0  # 1000 - 600
    assert s.gross_profit_basis == GROSS_PROFIT_DERIVED
    assert s.observations[ladder.GROSS_PROFIT].derived is True
    assert gross_profitability(s) == pytest.approx(400.0 / 5000.0)


def test_gross_profit_is_nan_when_neither_the_tag_nor_a_cost_line_exists():
    s = measured_panel().as_of("SIVB", T_AFTER_FY15)
    assert math.isnan(s.gross_profit)
    assert s.gross_profit_basis == GROSS_PROFIT_NONE
    assert math.isnan(gross_profitability(s))


def test_gross_profit_is_not_derived_across_two_different_fiscal_years():
    facts = [
        annual_fact("X", "Revenues", 2015, 1000.0, date(2016, 2, 20)),
        annual_fact("X", "CostOfRevenue", 2014, 600.0, date(2015, 2, 20)),
    ]
    s = SymbolFundamentals("X", tuple(facts)).as_of(date(2016, 6, 30))
    assert math.isnan(s.gross_profit)
    assert s.gross_profit_basis == GROSS_PROFIT_NONE


def test_the_cost_of_revenue_ladder_accepts_the_three_documented_tags():
    for tag in ("CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold"):
        facts = (
            annual_fact("X", "Revenues", 2015, 1000.0, date(2016, 2, 20)),
            annual_fact("X", tag, 2015, 600.0, date(2016, 2, 20)),
        )
        s = SymbolFundamentals("X", facts).as_of(date(2016, 6, 30))
        assert s.gross_profit == 400.0, tag
        assert s.gross_profit_basis == GROSS_PROFIT_DERIVED, tag


# ---- point in time: filed, never period_end ----------------------------------------------------


RESTATED = (
    fact("ATVI", "Assets", date(2015, 12, 31), 15_246.0, date(2016, 2, 26), accn="0000718877-16-000045"),
    fact("ATVI", "Assets", date(2015, 12, 31), 15_300.0, date(2017, 2, 28), accn="0000718877-17-000012"),
)


def test_period_end_is_never_an_availability_date():
    sf = SymbolFundamentals("ATVI", RESTATED)
    # The period closed on 2015-12-31; the filing landed on 2016-02-26. Nothing before that.
    assert math.isnan(sf.as_of(date(2015, 12, 31)).assets)
    assert math.isnan(sf.as_of(date(2016, 2, 25)).assets)
    assert sf.as_of(date(2016, 2, 26)).assets == 15_246.0


def test_a_restatement_is_invisible_until_it_is_filed():
    sf = SymbolFundamentals("ATVI", RESTATED)
    early = sf.as_of(date(2016, 6, 30))
    late = sf.as_of(date(2017, 6, 30))
    assert early.assets == 15_246.0
    assert early.observations[ladder.ASSETS].accn == "0000718877-16-000045"
    assert late.assets == 15_300.0
    assert late.observations[ladder.ASSETS].accn == "0000718877-17-000012"
    assert early.fiscal_period_end is None  # no annual flow in this fixture
    assert early.filed == date(2016, 2, 26)
    assert late.filed == date(2017, 2, 28)


def test_both_restatements_stay_in_the_panel():
    sf = SymbolFundamentals("ATVI", RESTATED)
    assert len(sf.facts) == 2  # selection never discards a fact


def test_ties_on_filed_break_on_the_greater_accession():
    facts = (
        fact("X", "Assets", date(2015, 12, 31), 10.0, date(2016, 2, 20), accn="0000000001-16-000001"),
        fact("X", "Assets", date(2015, 12, 31), 11.0, date(2016, 2, 20), accn="0000000001-16-000002"),
    )
    s = SymbolFundamentals("X", facts).as_of(date(2016, 6, 30))
    assert s.assets == 11.0
    assert s.observations[ladder.ASSETS].accn == "0000000001-16-000002"


def test_ties_on_filed_and_period_break_on_the_preferred_ladder_rung():
    facts = (
        fact("X", "StockholdersEquity", date(2015, 12, 31), 2000.0, date(2016, 2, 20)),
        fact(
            "X",
            "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
            date(2015, 12, 31),
            2500.0,
            date(2016, 2, 20),
        ),
    )
    s = SymbolFundamentals("X", facts).as_of(date(2016, 6, 30))
    assert s.equity == 2000.0
    assert s.tag(ladder.EQUITY) == "StockholdersEquity"


def test_a_tag_switch_is_resolved_per_period_not_per_symbol():
    # A filer reports Revenues through FY2017 and the ASC 606 element from FY2018. Standing in
    # 2019 both tags are visible, and each fiscal year keeps the tag that actually reported it.
    facts = (
        annual_fact("X", "Revenues", 2017, 900.0, date(2018, 2, 20)),
        annual_fact(
            "X",
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            2018,
            1000.0,
            date(2019, 2, 20),
        ),
    )
    sf = SymbolFundamentals("X", facts)
    assert sf.as_of(date(2018, 6, 30)).tag(ladder.REVENUE) == "Revenues"
    later = sf.as_of(date(2019, 6, 30))
    assert later.revenue == 1000.0
    assert later.tag(ladder.REVENUE) == "RevenueFromContractWithCustomerExcludingAssessedTax"


def test_a_foreign_currency_fact_never_joins_a_usd_cross_section():
    facts = (annual_fact("X", "Revenues", 2015, 1000.0, date(2016, 2, 20), unit="EUR"),)
    s = SymbolFundamentals("X", facts).as_of(date(2016, 6, 30))
    assert math.isnan(s.revenue)


def test_a_year_to_date_duration_is_neither_a_quarter_nor_a_year():
    nine_months = fact(
        "X", "Revenues", date(2015, 9, 30), 750.0, date(2015, 11, 5), start=date(2015, 1, 1)
    )
    assert nine_months.kind() is None
    sf = SymbolFundamentals("X", (nine_months,))
    assert sf.annual(ladder.REVENUE, date(2016, 6, 30)) is None
    assert sf.quarters(ladder.REVENUE, date(2016, 6, 30)) == ()


def test_the_period_kind_boundaries():
    assert fact("X", "Revenues", date(2015, 3, 31), 1.0, date(2015, 5, 1), start=date(2015, 1, 1)).kind() == KIND_QUARTER
    assert fact("X", "Revenues", date(2015, 12, 31), 1.0, date(2016, 2, 1), start=date(2015, 1, 1)).kind() == KIND_ANNUAL
    assert fact("X", "Assets", date(2015, 12, 31), 1.0, date(2016, 2, 1)).kind() == KIND_INSTANT


# ---- quarterly series, Q4 derivation and gaps ---------------------------------------------------


def eps_quarters(symbol: str, values: list[float], *, start_year: int = 2013) -> list[Fact]:
    """``values`` as consecutive calendar quarters of diluted EPS, each filed 40 days after close."""
    out: list[Fact] = []
    bounds = [
        (date(y, m0, 1), date(y, m1, d1))
        for y in range(start_year, start_year + 8)
        for m0, m1, d1 in ((1, 3, 31), (4, 6, 30), (7, 9, 30), (10, 12, 31))
    ]
    for v, (s, e) in zip(values, bounds):
        out.append(
            fact(
                symbol,
                "EarningsPerShareDiluted",
                e,
                v,
                e + timedelta(days=40),
                start=s,
                unit="USD/shares",
                form="10-Q",
                accn=f"0000000001-{e.year % 100:02d}-{e.month:06d}",
            )
        )
    return out


def test_an_untagged_q4_is_derived_from_the_fiscal_year():
    facts = [
        fact("X", "EarningsPerShareDiluted", date(2015, 3, 31), 0.5, date(2015, 5, 1),
             start=date(2015, 1, 1), unit="USD/shares", form="10-Q", accn="0000000001-15-000001"),
        fact("X", "EarningsPerShareDiluted", date(2015, 6, 30), 0.6, date(2015, 8, 1),
             start=date(2015, 4, 1), unit="USD/shares", form="10-Q", accn="0000000001-15-000002"),
        fact("X", "EarningsPerShareDiluted", date(2015, 9, 30), 0.7, date(2015, 11, 1),
             start=date(2015, 7, 1), unit="USD/shares", form="10-Q", accn="0000000001-15-000003"),
        annual_fact("X", "EarningsPerShareDiluted", 2015, 2.6, date(2016, 2, 20), unit="USD/shares",
                    accn="0000000001-16-000001"),
    ]
    sf = SymbolFundamentals("X", tuple(facts))
    series = sf.quarters(ladder.DILUTED_EPS, date(2016, 6, 30))
    assert [o.period_end for o in series] == [
        date(2015, 3, 31), date(2015, 6, 30), date(2015, 9, 30), date(2015, 12, 31),
    ]
    q4 = series[-1]
    assert q4.derived is True
    assert q4.val == pytest.approx(0.8)
    assert q4.period_start == date(2015, 10, 1)
    assert q4.filed == date(2016, 2, 20)  # the newest of its four inputs


def test_a_derived_q4_is_invisible_before_the_fiscal_year_is_filed():
    facts = [
        fact("X", "EarningsPerShareDiluted", date(2015, 3, 31), 0.5, date(2015, 5, 1),
             start=date(2015, 1, 1), unit="USD/shares", form="10-Q"),
        fact("X", "EarningsPerShareDiluted", date(2015, 6, 30), 0.6, date(2015, 8, 1),
             start=date(2015, 4, 1), unit="USD/shares", form="10-Q"),
        fact("X", "EarningsPerShareDiluted", date(2015, 9, 30), 0.7, date(2015, 11, 1),
             start=date(2015, 7, 1), unit="USD/shares", form="10-Q"),
        annual_fact("X", "EarningsPerShareDiluted", 2015, 2.6, date(2016, 2, 20), unit="USD/shares"),
    ]
    sf = SymbolFundamentals("X", tuple(facts))
    assert [o.period_end for o in sf.quarters(ladder.DILUTED_EPS, date(2016, 1, 15))] == [
        date(2015, 3, 31), date(2015, 6, 30), date(2015, 9, 30),
    ]


def test_a_tagged_q4_is_never_overwritten_by_a_derived_one():
    facts = [
        fact("X", "EarningsPerShareDiluted", date(2015, 3, 31), 0.5, date(2015, 5, 1),
             start=date(2015, 1, 1), unit="USD/shares", form="10-Q"),
        fact("X", "EarningsPerShareDiluted", date(2015, 6, 30), 0.6, date(2015, 8, 1),
             start=date(2015, 4, 1), unit="USD/shares", form="10-Q"),
        fact("X", "EarningsPerShareDiluted", date(2015, 9, 30), 0.7, date(2015, 11, 1),
             start=date(2015, 7, 1), unit="USD/shares", form="10-Q"),
        fact("X", "EarningsPerShareDiluted", date(2015, 12, 31), 0.9, date(2016, 2, 20),
             start=date(2015, 10, 1), unit="USD/shares", form="10-K"),
        annual_fact("X", "EarningsPerShareDiluted", 2015, 2.6, date(2016, 2, 20), unit="USD/shares"),
    ]
    series = SymbolFundamentals("X", tuple(facts)).quarters(ladder.DILUTED_EPS, date(2016, 6, 30))
    assert series[-1].val == 0.9
    assert series[-1].derived is False


def test_a_gap_truncates_the_quarterly_series():
    values = [0.1 * i for i in range(1, 13)]
    facts = eps_quarters("X", values)
    del facts[5]  # drop 2014Q2: the step from 2014Q1 to 2014Q3 is 183 days
    series = SymbolFundamentals("X", tuple(facts)).quarters(ladder.DILUTED_EPS, date(2017, 1, 1))
    assert [o.period_end for o in series] == [
        date(2014, 9, 30), date(2014, 12, 31), date(2015, 3, 31), date(2015, 6, 30),
        date(2015, 9, 30), date(2015, 12, 31),
    ]


# ---- SUE ----------------------------------------------------------------------------------------


NINE = np.array([1.0, 1.0, 1.0, 1.0, 2.0, 1.5, 1.0, 0.5, 3.0], dtype=np.float64)


def test_surprises_are_the_seasonal_random_walk():
    assert sue.surprises(NINE).tolist() == [1.0, 0.5, 0.0, -0.5, 1.0]


def test_sue_is_the_latest_surprise_over_the_dispersion_of_the_prior_ones():
    # prior = [1, 0.5, 0, -0.5], mean 0.25, var (0.5625+0.0625+0.0625+0.5625)/4 = 0.3125
    # sd = sqrt(0.3125) = 0.5590169943749475 ; SUE = 1 / sd = 4 / sqrt(5)
    prior = np.array([1.0, 0.5, 0.0, -0.5], dtype=np.float64)
    assert sue.dispersion(prior) == pytest.approx(math.sqrt(0.3125), rel=1e-15)
    assert sue.sue(NINE) == pytest.approx(4.0 / math.sqrt(5.0), rel=1e-15)


def test_sue_needs_nine_contiguous_quarters_and_says_so():
    assert sue.MIN_QUARTERS == 9
    assert math.isnan(sue.sue(NINE[1:]))  # 8 quarters: only 3 prior surprises
    assert math.isfinite(sue.sue(NINE))


def test_sue_is_nan_when_the_prior_surprises_do_not_move():
    flat = np.array([1.0] * 8 + [2.0], dtype=np.float64)
    assert math.isnan(sue.sue(flat))  # prior surprises all 0 -> zero dispersion


def test_sue_uses_at_most_eight_prior_surprises():
    eps = np.array(
        [1.0, 2.0, 3.0, 4.0, 9.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 2.0, 1.5, 1.0, 0.5, 3.0],
        dtype=np.float64,
    )
    s = sue.surprises(eps)
    assert s.shape[0] > sue.MAX_SURPRISES + 1  # there are prior surprises the window must drop
    expected = float(s[-1]) / sue.dispersion(s[-1 - sue.MAX_SURPRISES : -1])
    assert sue.sue(eps) == pytest.approx(expected, rel=1e-15)
    moved = eps.copy()
    moved[0] = -50.0  # only the oldest surprise, far outside the window
    assert sue.sue(moved) == pytest.approx(expected, rel=1e-15)


def test_sue_rejects_a_non_float64_series():
    with pytest.raises(ValueError):
        sue.sue(np.array([1, 2, 3], dtype=np.int64))


def test_the_snapshot_carries_sue_and_the_length_of_the_run_behind_it():
    facts = eps_quarters("X", [1.0, 1.0, 1.0, 1.0, 2.0, 1.5, 1.0, 0.5, 3.0], start_year=2013)
    s = SymbolFundamentals("X", tuple(facts)).as_of(date(2016, 6, 30))
    assert s.sue_quarters == 9
    assert s.sue == pytest.approx(4.0 / math.sqrt(5.0), rel=1e-15)


def test_a_gap_makes_sue_nan():
    facts = eps_quarters("X", [1.0, 1.0, 1.0, 1.0, 2.0, 1.5, 1.0, 0.5, 3.0], start_year=2013)
    del facts[2]
    s = SymbolFundamentals("X", tuple(facts)).as_of(date(2016, 6, 30))
    assert s.sue_quarters == 6
    assert math.isnan(s.sue)


# ---- ratios ---------------------------------------------------------------------------------------


def test_the_ratio_helpers_refuse_a_zero_or_missing_denominator():
    s = measured_panel().as_of("ATVI", T_AFTER_FY15)
    assert return_on_equity(s) == pytest.approx(120.0 / 2000.0)
    assert book_value_per_share(s) == pytest.approx(2000.0 / 400.0)
    empty = SymbolFundamentals("X", ()).as_of(T_AFTER_FY15)
    assert math.isnan(return_on_equity(empty))
    assert math.isnan(book_value_per_share(empty))
    assert math.isnan(gross_profitability(empty))


# ---- construction, validation and determinism --------------------------------------------------


def test_a_fact_filed_before_its_period_closed_is_rejected():
    with pytest.raises(FundamentalsError):
        fact("X", "Assets", date(2015, 12, 31), 1.0, date(2015, 12, 30))


def test_a_non_finite_value_is_rejected():
    with pytest.raises(FundamentalsError):
        fact("X", "Assets", date(2015, 12, 31), float("nan"), date(2016, 2, 20))


def test_a_row_becomes_a_fact_in_the_declared_column_order():
    row = ("X", "us-gaap", "Assets", "USD", None, date(2015, 12, 31), 10.0,
           "0000000001-16-000001", "10-K", 2015, "FY", date(2016, 2, 20))
    assert len(FACT_COLUMNS) == len(row)
    by_name = dict(zip(FACT_COLUMNS, row))
    assert fact_from_row(row) == fact_from_row(by_name)
    assert fact_from_row(row).val == 10.0


def test_facts_from_rows_skips_and_counts_a_malformed_row():
    good = ("X", "us-gaap", "Assets", "USD", None, date(2015, 12, 31), 10.0,
            "0000000001-16-000001", "10-K", 2015, "FY", date(2016, 2, 20))
    bad = ("X", "us-gaap", "Assets", "USD", None, date(2015, 12, 31), 10.0,
           "0000000001-16-000001", "10-K", 2015, "FY", date(2015, 1, 1))
    facts, skipped = facts_from_rows([good, bad, good])
    assert len(facts) == 2
    assert skipped == 1
    with pytest.raises(FundamentalsError):
        facts_from_rows([bad], skip_invalid=False)


def test_a_fact_for_another_symbol_is_rejected():
    with pytest.raises(FundamentalsError):
        SymbolFundamentals("X", (fact("Y", "Assets", date(2015, 12, 31), 1.0, date(2016, 2, 20)),))


def test_the_panel_is_order_independent():
    facts = list(measured_panel().symbols["ATVI"].facts)
    forward = SymbolFundamentals("ATVI", tuple(facts)).as_of(T_AFTER_FY15)
    backward = SymbolFundamentals("ATVI", tuple(reversed(facts))).as_of(T_AFTER_FY15)
    assert forward.observations.keys() == backward.observations.keys()
    for concept in forward.observations:
        assert forward.observations[concept] == backward.observations[concept]


def test_an_empty_panel_is_a_normal_state():
    assert len(EMPTY_PANEL) == 0
    assert EMPTY_PANEL.names() == ()
    assert EMPTY_PANEL.as_of("AAPL", date(2016, 6, 30)) is None
    assert "AAPL" not in EMPTY_PANEL


def test_snapshots_on_covers_every_symbol_in_the_panel():
    panel = measured_panel()
    snaps = panel.snapshots_on(T_AFTER_FY15)
    assert sorted(snaps) == sorted(FILERS)
    assert all(s.asof == T_AFTER_FY15 for s in snaps.values())


def test_an_unknown_concept_is_an_error_not_a_nan():
    s = SymbolFundamentals("X", ()).as_of(date(2016, 6, 30))
    with pytest.raises(ladder.LadderError):
        s.value("ebitda")

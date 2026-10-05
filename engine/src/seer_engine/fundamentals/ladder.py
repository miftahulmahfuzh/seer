"""The XBRL concept ladder: which ``us-gaap``/``dei`` tags carry each metric, in preference order.

A filer tags the same economic quantity under different element names depending on its
industry, its auditor and which accounting standard was current when it filed. The ladder is
the fixed, ordered list of element names the derivation layer is willing to read for one
metric. It is data, not code: ``fundamental_facts`` stores raw facts (plan Decisions table), so
**reordering or dropping rungs among tags that are already ingested is a one-line change and
needs no re-ingest**.

**Adding a new tag rung does cost a full re-ingest.** ``LADDER_TAGS`` below is not only what the
derivation reads -- it is also the ingest allowlist that ``commands/fundamentals`` imports (plan
Decisions table: the list must sit in a module both the impure ingest and the pure derivation
can read, and impure-imports-pure is the only legal direction under invariant 5). A tag that is
not in ``LADDER_TAGS`` was never stored, so a rung added here reads nothing, silently, forever
until the facts are fetched again::

    delete from fundamentals_log;
    python -m seer_engine fundamentals --retry-failed

Every rung of every concept must therefore be in ``LADDER_TAGS``, including the
``CostOfRevenue`` variants the gross-profit fallback needs.

Measured coverage over 8 dead filers (ATVI, TWTR, CELG, TWX, SIVB, PXD, WRK, K), 2026-10-05::

    revenue              8/8   Revenues (7), RevenueFromContractWithCustomerExcludingAssessedTax (SIVB)
    net income           8/8   NetIncomeLoss
    assets               8/8   Assets
    equity               8/8   StockholdersEquity
    operating cash flow  8/8   NetCashProvidedByUsedInOperatingActivities
    diluted EPS          8/8   EarningsPerShareDiluted
    shares outstanding   8/8   dei:EntityCommonStockSharesOutstanding
    operating income     6/8   OperatingIncomeLoss -- absent for SIVB and PXD
    gross profit         2/8   GrossProfit -- present only for CELG and WRK

**Gross profit is the hole.** Novy-Marx gross profitability needs it for all 8, so
``panel.Snapshot`` derives it when the tag is absent:

    gross_profit = revenue - cost_of_revenue

reading ``cost_of_revenue`` from, in order, ``CostOfRevenue``, ``CostOfGoodsAndServicesSold``,
``CostOfGoodsSold``. Both legs must come from the **same** fiscal period end, or the derivation
is refused. When ``GrossProfit`` is absent and either leg is missing (a bank such as SIVB has no
cost of revenue at all), ``Snapshot.gross_profit`` is NaN and ``Snapshot.gross_profit_basis`` is
``"none"`` -- never zero, never a partial figure. The three bases are ``"reported"``,
``"derived"`` and ``"none"``.

The lower rungs below ``Revenues`` and friends were not needed by the 8-filer sample; they are
in the ladder because they are the standard alternates and cost nothing to try.

Every concept declares the one XBRL unit it accepts. A fact in any other unit (a EUR-reporting
filer, a per-share figure tagged in a foreign currency) is dropped rather than silently mixed
into a USD cross-section.

Pure: no database, network, clock or randomness (tests/test_strategy_purity.py).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

# --- period kinds ---------------------------------------------------------------------------

INSTANT = "instant"  # a balance at a moment: period_start is None
DURATION = "duration"  # a flow over a window: period_start is a date

# --- units ----------------------------------------------------------------------------------

USD = "USD"
USD_PER_SHARE = "USD/shares"
SHARES = "shares"

# --- concept names (the keys of LADDER and the field names of panel.Snapshot) -----------------

REVENUE = "revenue"
COST_OF_REVENUE = "cost_of_revenue"
GROSS_PROFIT = "gross_profit"
OPERATING_INCOME = "operating_income"
NET_INCOME = "net_income"
OPERATING_CASH_FLOW = "operating_cash_flow"
DILUTED_EPS = "diluted_eps"
DILUTED_SHARES = "diluted_shares"
ASSETS = "assets"
EQUITY = "equity"
SHARES_OUTSTANDING = "shares_outstanding"


class LadderError(ValueError):
    """The ladder was asked about a concept it does not define."""


@dataclass(frozen=True, slots=True)
class ConceptSpec:
    """One metric: its period kind, the unit it must be reported in, and its tag rungs."""

    name: str
    kind: str  # INSTANT or DURATION
    unit: str
    tags: tuple[tuple[str, str], ...]  # (taxonomy, tag), most preferred first

    def rung(self, taxonomy: str, tag: str) -> int | None:
        """The 0-based rung of ``(taxonomy, tag)``, or None when this concept does not use it."""
        for i, pair in enumerate(self.tags):
            if pair == (taxonomy, tag):
                return i
        return None


LADDER: Mapping[str, ConceptSpec] = {
    REVENUE: ConceptSpec(
        REVENUE,
        DURATION,
        USD,
        (
            ("us-gaap", "Revenues"),
            ("us-gaap", "RevenueFromContractWithCustomerExcludingAssessedTax"),
            ("us-gaap", "RevenueFromContractWithCustomerIncludingAssessedTax"),
            ("us-gaap", "SalesRevenueNet"),
        ),
    ),
    COST_OF_REVENUE: ConceptSpec(
        COST_OF_REVENUE,
        DURATION,
        USD,
        (
            ("us-gaap", "CostOfRevenue"),
            ("us-gaap", "CostOfGoodsAndServicesSold"),
            ("us-gaap", "CostOfGoodsSold"),
        ),
    ),
    GROSS_PROFIT: ConceptSpec(
        GROSS_PROFIT,
        DURATION,
        USD,
        (("us-gaap", "GrossProfit"),),
    ),
    OPERATING_INCOME: ConceptSpec(
        OPERATING_INCOME,
        DURATION,
        USD,
        (("us-gaap", "OperatingIncomeLoss"),),
    ),
    NET_INCOME: ConceptSpec(
        NET_INCOME,
        DURATION,
        USD,
        (("us-gaap", "NetIncomeLoss"),),
    ),
    OPERATING_CASH_FLOW: ConceptSpec(
        OPERATING_CASH_FLOW,
        DURATION,
        USD,
        (
            ("us-gaap", "NetCashProvidedByUsedInOperatingActivities"),
            ("us-gaap", "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"),
        ),
    ),
    DILUTED_EPS: ConceptSpec(
        DILUTED_EPS,
        DURATION,
        USD_PER_SHARE,
        (("us-gaap", "EarningsPerShareDiluted"),),
    ),
    DILUTED_SHARES: ConceptSpec(
        DILUTED_SHARES,
        DURATION,
        SHARES,
        (("us-gaap", "WeightedAverageNumberOfDilutedSharesOutstanding"),),
    ),
    ASSETS: ConceptSpec(
        ASSETS,
        INSTANT,
        USD,
        (("us-gaap", "Assets"),),
    ),
    EQUITY: ConceptSpec(
        EQUITY,
        INSTANT,
        USD,
        (
            ("us-gaap", "StockholdersEquity"),
            ("us-gaap", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"),
        ),
    ),
    SHARES_OUTSTANDING: ConceptSpec(
        SHARES_OUTSTANDING,
        INSTANT,
        SHARES,
        (
            ("dei", "EntityCommonStockSharesOutstanding"),
            ("us-gaap", "CommonStockSharesOutstanding"),
        ),
    ),
}

CONCEPTS: tuple[str, ...] = tuple(LADDER)
DURATION_CONCEPTS: tuple[str, ...] = tuple(c for c in CONCEPTS if LADDER[c].kind == DURATION)
INSTANT_CONCEPTS: tuple[str, ...] = tuple(c for c in CONCEPTS if LADDER[c].kind == INSTANT)


def spec(concept: str) -> ConceptSpec:
    """The ``ConceptSpec`` for ``concept``; ``LadderError`` when the ladder does not define it."""
    try:
        return LADDER[concept]
    except KeyError:
        raise LadderError(f"unknown concept {concept!r}; the ladder defines {CONCEPTS}") from None


def _build_index() -> Mapping[tuple[str, str], tuple[tuple[str, int], ...]]:
    index: dict[tuple[str, str], list[tuple[str, int]]] = {}
    for name in CONCEPTS:
        for i, pair in enumerate(LADDER[name].tags):
            index.setdefault(pair, []).append((name, i))
    return {pair: tuple(v) for pair, v in index.items()}


# (taxonomy, tag) -> ((concept, rung), ...). One tag serves one concept today, but the shape
# allows a future tag that feeds two (for example a combined revenue/other-income element).
TAG_INDEX: Mapping[tuple[str, str], tuple[tuple[str, int], ...]] = _build_index()

# Every (taxonomy, tag) the ladder reads, and -- see the module docstring -- the ingest allowlist
# `commands/fundamentals` imports. The ingest may store more; the derivation reads these.
LADDER_TAGS: frozenset[tuple[str, str]] = frozenset(TAG_INDEX)


def concepts_for(taxonomy: str, tag: str) -> tuple[tuple[str, int], ...]:
    """``((concept, rung), ...)`` that ``(taxonomy, tag)`` feeds; empty when the ladder ignores it."""
    return TAG_INDEX.get((taxonomy, tag), ())

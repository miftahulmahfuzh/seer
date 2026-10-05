"""Pure derivation over raw SEC XBRL facts: the concept ladder, point-in-time selection, SUE.

The ingest (``commands/fundamentals``) stores facts exactly as EDGAR served them, restatements
included. Everything that turns them into numbers a factor can rank on lives here, in pure
Python, so the ladder can be revised without a re-ingest (plan Decisions table).

* ``ladder`` -- which ``us-gaap``/``dei`` tags carry each metric, in preference order, and the
  measured coverage behind that list.
* ``panel`` -- ``Fact``, the point-in-time selection rule (``filed <= t``, never ``period_end``),
  ``Snapshot``, and ``FundamentalPanel``, which is what ``Market.fundamentals`` holds.
* ``sue`` -- standardized unexpected earnings on a seasonal random walk. Imported as a module,
  never re-exported here: ``seer_engine.fundamentals.sue`` must keep naming the module, not the
  function inside it. Use ``from seer_engine.fundamentals.sue import sue``.

Pure: no database, network, clock or randomness (tests/test_strategy_purity.py).
"""

from seer_engine.fundamentals.ladder import (
    ASSETS,
    CONCEPTS,
    COST_OF_REVENUE,
    DILUTED_EPS,
    DILUTED_SHARES,
    DURATION,
    DURATION_CONCEPTS,
    EQUITY,
    GROSS_PROFIT,
    INSTANT,
    INSTANT_CONCEPTS,
    LADDER,
    LADDER_TAGS,
    NET_INCOME,
    OPERATING_CASH_FLOW,
    OPERATING_INCOME,
    REVENUE,
    SHARES_OUTSTANDING,
    ConceptSpec,
    LadderError,
    concepts_for,
    spec,
)
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
    Obs,
    Snapshot,
    SymbolFundamentals,
    accrual_ratio,
    book_value_per_share,
    fact_from_row,
    facts_from_rows,
    gross_profitability,
    return_on_assets,
    return_on_equity,
)

__all__ = [
    "ASSETS",
    "CONCEPTS",
    "COST_OF_REVENUE",
    "DILUTED_EPS",
    "DILUTED_SHARES",
    "DURATION",
    "DURATION_CONCEPTS",
    "EMPTY_PANEL",
    "EQUITY",
    "FACT_COLUMNS",
    "GROSS_PROFIT",
    "GROSS_PROFIT_DERIVED",
    "GROSS_PROFIT_NONE",
    "GROSS_PROFIT_REPORTED",
    "INSTANT",
    "INSTANT_CONCEPTS",
    "KIND_ANNUAL",
    "KIND_INSTANT",
    "KIND_QUARTER",
    "LADDER",
    "LADDER_TAGS",
    "NET_INCOME",
    "OPERATING_CASH_FLOW",
    "OPERATING_INCOME",
    "REVENUE",
    "SHARES_OUTSTANDING",
    "ConceptSpec",
    "Fact",
    "FundamentalPanel",
    "FundamentalsError",
    "LadderError",
    "Obs",
    "Snapshot",
    "SymbolFundamentals",
    "accrual_ratio",
    "book_value_per_share",
    "concepts_for",
    "fact_from_row",
    "facts_from_rows",
    "gross_profitability",
    "return_on_assets",
    "return_on_equity",
    "spec",
]

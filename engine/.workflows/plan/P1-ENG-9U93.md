> Adopted from `EDGAR_FUNDAMENTALS_PLAN.md` phase 5. Source: `.workflows/plan/edgar-fundamentals/phase-5.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 5: Pure derivation — concept ladder, point-in-time selection, SUE

**Plan set:** `EDGAR_FUNDAMENTALS_PLAN.md`
**Analysis:** `20261005-081833-G7K2_code_analyzer.md`
**Satisfies:** R3 — the concept ladder over the measured tag variants, with gross profit derived and its fallback documented
**Depends on:** Phase 2 (schema — for the column semantics only; no code dependency)
**Depended on by:** Phase 4 (imports `ladder.LADDER_TAGS` as the ingest allowlist), Phase 6
(imports `Fact`, `FundamentalPanel`, `EMPTY_PANEL`, `panel.FACT_COLUMNS`), Phase 7 (ranks on
`FundamentalPanel.as_of`)
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/fundamentals`

---

## Reconciled input contract with Phase 2 (the original assumption was partly wrong)

`phase-2.md` did not exist when this plan was written, so the input contract below was inferred.
**The reconciler checked it against phase 2's shipped migration and corrected two things.** Both
corrections are confined to `panel.FACT_COLUMNS` and `fact_from_row`, exactly as this plan
predicted; nothing else in the package moves.

### What phase 2 actually ships

```sql
CREATE TABLE IF NOT EXISTS fundamental_facts (
  cik           bigint NOT NULL,
  taxonomy      text NOT NULL,          -- 'us-gaap' | 'dei'
  tag           text NOT NULL,
  unit          text NOT NULL,
  period_start  date NOT NULL,          -- = period_end for an INSTANTANEOUS fact
  period_end    date NOT NULL,
  accn          text NOT NULL,
  val           numeric NOT NULL,
  fy            int,
  fp            text,
  form          text NOT NULL,
  filed         date NOT NULL,
  PRIMARY KEY (cik, taxonomy, tag, unit, period_start, period_end, accn)
);
```

### Correction 1 — there is no `symbol` column; phase 6 supplies it

Facts are stored per **CIK**, because one ticker names several companies over time and one
company files under several tickers (invariant 4). A `symbol` column would duplicate every row
for a share-class pair and would make a recycled ticker smear two filers together.

**This package stays symbol-keyed and does not change.** `Fact.symbol`,
`SymbolFundamentals.symbol` and `FundamentalPanel.symbols` are what phase 7 ranks on, and this
package never sees a connection anyway — it takes rows. **Phase 6 owns the CIK→symbol join**
(`fundamental_facts JOIN ticker_cik ON cik, filed ∈ [start_date, end_date)`), projects
`m.symbol` as the first column, and hands the result here. Phase 2's contract section carries
the exact SQL. So `FACT_COLUMNS` keeps `symbol` at position 0 and is a contract with **phase 6's
projection**, not with the table.

### Correction 2 — `period_start` is `NOT NULL`; the equality is the instant marker

The original assumption had `period_start date NULL`, NULL meaning "instant". Phase 2 cannot do
that: a nullable column cannot sit in a PRIMARY KEY, and the period **must** be keyed, because
one 10-K reports `Revenues` for both the fiscal year (`start` 2015-01-01) and Q4
(`start` 2015-10-01) under the same `accn`, `tag`, `unit` and `period_end`. Phase 4 therefore
writes `period_start = period_end` when SEC omits `start`, and phase 2's comment block states
that no `us-gaap` or `dei` **duration** fact has a one-day period, so the encoding is
unambiguous.

**`Fact.period_start` stays `date | None` in memory** — `Fact.kind()`, `_derived_q4`,
`quarters()` and every test are written against `None` meaning instant, and that is the right
in-memory shape. The database encoding is translated at the one boundary that reads database
rows: **`fact_from_row` maps `period_start == period_end` to `None`.** Step 3 carries the
two-line change. Phase 6's `facts_from_frame` builds `Fact` objects directly rather than through
`fact_from_row`, so it applies the same rule in its COPY projection (phase 2's contract section
emits `''` for `period_start = period_end`), and the two paths agree by construction.

### `FACT_COLUMNS` — the reconciled order

Phase 6's `FACTS_COLUMNS` and this tuple **must be the same object**. The reconciler made phase
6 import it from here rather than restate it, so there is one owner:

| # | column | type | note |
|---|---|---|---|
| 0 | `symbol` | `text` | supplied by phase 6's `ticker_cik` join, not by the table |
| 1 | `taxonomy` | `text` | `us-gaap` or `dei` |
| 2 | `tag` | `text` | the XBRL element name, without the taxonomy prefix |
| 3 | `unit` | `text` | `USD`, `USD/shares`, `shares`, … |
| 4 | `period_start` | `date` / `None` | `None` once `fact_from_row` has mapped the instant marker |
| 5 | `period_end` | `date` | |
| 6 | `val` | `numeric` | arrives as a `Decimal`; converted to float64 here |
| 7 | `accn` | `text` | part of the primary key — restatements insert |
| 8 | `form` | `text` | `10-K`, `10-Q`, `8-K`, `20-F`, … |
| 9 | `fy` | `int` / None | metadata only; the selection never reads it |
| 10 | `fp` | `text` / None | metadata only; the selection never reads it |
| 11 | `filed` | `date` | **the availability date, and the only one** |

This phase does **not** read the database. It takes rows; phase 6 fetches them.

### This phase also owns the ingest tag allowlist (phase 4 imports it)

The index's Decisions table puts the ingest allowlist here, in `ladder.LADDER_TAGS`, because the
list must sit in a module both the impure ingest and the pure derivation can read and
impure-imports-pure is the only legal direction under invariant 5. **`LADDER_TAGS` is therefore
load-bearing beyond this package**: it is literally the set of `(taxonomy, tag)` pairs that will
exist in `fundamental_facts`. Two consequences the implementer must not lose:

- **Every rung of every concept must be in `LADDER_TAGS`**, including the `CostOfRevenue`
  variants the gross-profit fallback needs. A rung absent from the set reads nothing, silently,
  forever.
- **Adding a rung later costs a full re-ingest** (`fundamentals --symbols <all> --retry-failed`
  after `delete from fundamentals_log`). `ladder.py`'s module docstring must say so.

Phase 4 carried two extra tags in its own draft list that no ladder concept reads —
`us-gaap:Liabilities` and `us-gaap:EarningsPerShareBasic`. They are **not** added here: SUE and
the EPS series are defined on diluted EPS (8/8 in the measurement) and book equity is tagged
directly, so both would cost rows on a 0.5 GB tier and feed nothing.

## Goal

After this phase `seer_engine.fundamentals` exists: a pure package that turns raw XBRL facts
into a point-in-time panel. It knows which `us-gaap`/`dei` element carries each metric (the
ladder), which fact a backtest standing on day `t` is allowed to see (`filed <= t`, never
`period_end`, with a total deterministic tiebreak), how to reconstruct a gross profit that two
filers in eight actually tag, and how to compute SUE on a seasonal random walk with its minimum
history enforced rather than assumed. Nothing consumes it yet — phase 6 wires it into `Market`
and phase 7 ranks on it — but every number the lab will eventually trade on is decided here, and
every one of those decisions is covered by a test that runs without a database or a network.

## Interface Contract

**Creates (the package — `seer_engine/fundamentals/`):**

*`ladder.py`*
- `ladder.ConceptSpec` — frozen `(name, kind, unit, tags)`; `tags` is `((taxonomy, tag), ...)` in preference order; `ConceptSpec.rung(taxonomy, tag) -> int | None`
- `ladder.LadderError(ValueError)`
- `ladder.LADDER: Mapping[str, ConceptSpec]`, `ladder.CONCEPTS`, `ladder.DURATION_CONCEPTS`, `ladder.INSTANT_CONCEPTS`
- `ladder.TAG_INDEX`, `ladder.LADDER_TAGS: frozenset[tuple[str, str]]` — **also phase 4's ingest allowlist; see the reconciled contract above**, `ladder.concepts_for(taxonomy, tag)`, `ladder.spec(concept)`
- concept-name constants: `REVENUE`, `COST_OF_REVENUE`, `GROSS_PROFIT`, `OPERATING_INCOME`, `NET_INCOME`, `OPERATING_CASH_FLOW`, `DILUTED_EPS`, `DILUTED_SHARES`, `ASSETS`, `EQUITY`, `SHARES_OUTSTANDING`
- kind constants `INSTANT = "instant"`, `DURATION = "duration"`; unit constants `USD`, `USD_PER_SHARE`, `SHARES`

*`panel.py`* — **this is what phases 6 and 7 consume**
- `panel.FACT_COLUMNS: tuple[str, ...]` — the twelve-column input contract above
- `panel.Fact` — frozen, slots; `(symbol, taxonomy, tag, unit, period_start, period_end, val, accn, form, fy, fp, filed)`; `Fact.kind() -> str | None`
- `panel.FundamentalsError(ValueError)`
- `panel.fact_from_row(row)`, `panel.facts_from_rows(rows, *, skip_invalid=True) -> (facts, skipped)`
- `panel.Obs` — frozen, slots; one selected observation, with `derived: bool`
- `panel.Snapshot` — frozen, slots; **the per-symbol, per-day record the factor layer reads**
- `panel.SymbolFundamentals` — frozen; `.facts`, `.latest(concept, kind, t)`, `.instant(concept, t)`, `.annual(concept, t)`, `.quarters(concept, t, *, derive_q4=True)`, `.as_of(t) -> Snapshot`
- `panel.FundamentalPanel` — frozen; `.symbols`, `.names()`, `.get(symbol)`, `.as_of(symbol, t) -> Snapshot | None`, `.snapshots_on(t, symbols=None)`, `.from_facts(facts)` (staticmethod)
- `panel.EMPTY_PANEL: FundamentalPanel` — **phase 6 returns this when the store has no fundamentals rows**
- ratio helpers: `gross_profitability`, `return_on_equity`, `return_on_assets`, `accrual_ratio`, `book_value_per_share`
- constants `KIND_QUARTER`/`KIND_ANNUAL`/`KIND_INSTANT`, `GROSS_PROFIT_REPORTED`/`_DERIVED`/`_NONE`, the day-count bounds

*`sue.py`*
- `sue.sue(eps: np.ndarray) -> float`, `sue.surprises(eps)`, `sue.dispersion(prior)`
- `sue.SEASON = 4`, `sue.MAX_SURPRISES = 8`, `sue.MIN_SURPRISES = 4`, `sue.MIN_QUARTERS = 9`

*`__init__.py`* re-exports every public name of `ladder` and `panel`. It deliberately
**re-exports nothing from `sue`**, so that `seer_engine.fundamentals.sue` keeps naming the
module and not the function inside it. Callers write
`from seer_engine.fundamentals.sue import sue`.

**Signature changes:** none — nothing existing is called differently.
**Deletes:** none.
**Renames:** none.

**Modifies (one file, one package name, additive) — and this phase is its sole owner across
the set; no other phase touches it, and phase 6 must leave it byte-identical to what this phase
leaves:** `engine/tests/test_strategy_purity.py` —
`"fundamentals"` is added to the tuple in `_pure_sources()` (line 34) and the three new module
names to the glob assertion (line 62). See Step 5 for why this phase owns that edit and what
the reconciler should check.

**Requires (from earlier phases):** nothing at import or call time. Phase 2's
`fundamental_facts` *semantics* are what `FACT_COLUMNS` and `fact_from_row` encode (the
`period_start = period_end` instant marker in particular); see the reconciled contract above.

**Required by later phases (reconciled — this phase is a dependency of 4, 6 and 7):**
- Phase 4 imports `ladder.LADDER_TAGS` and nothing else. Wave order is
  `{1,2,3} → {5} → {4,6} → {7}`.
- Phase 6 imports `Fact`, `FundamentalPanel` (as its `Panel`), `EMPTY_PANEL` (as
  `EMPTY_FUNDAMENTALS`) and `panel.FACT_COLUMNS` (as its `FACTS_COLUMNS`). It needs
  `FundamentalPanel.from_facts(())` to be a valid empty panel — `EMPTY_PANEL` is exactly that —
  and it needs this package to import no `psycopg`/`requests`/`yfinance`, because
  `backtest/market.py` imports it and
  `test_strategy_purity.py::test_pure_modules_load_no_db_or_network_module` imports
  `seer_engine.backtest.market` in a fresh interpreter and asserts none of those landed in
  `sys.modules`. Step 5's glob extension makes that permanent.
- Phase 7 calls `FundamentalPanel.as_of(symbol, t) -> Snapshot | None` and reads `Snapshot`'s
  `filed`, `equity`, `assets`, `shares_outstanding`, `net_income`, `gross_profit` and `sue`
  fields. **It does not call `flow_ttm` / `stock_asof` / `filed_asof` / `sue_asof`** — those
  were phase 7's guesses and were rewritten against the surface above. Phase 7 also inherits
  decision 4 below: the level flows in `Snapshot` are **annual**, not trailing-twelve-month.

**Leaves alone (owned by others):**
- `engine/src/seer_engine/backtest/*` — `Market.fundamentals` and the panel load are Phase 6
- `engine/src/seer_engine/strategies/*` — `prepare_market` is Phase 6, `f_fundamental.py` is Phase 7
- `engine/src/seer_engine/commands/*`, `sec.py`, `cik.py`, `db.py`, `config.py` — Phases 1, 3, 4
- `db/migrations/*` — Phase 2
- `engine/src/seer_engine/lab/*`, `docs/runbooks/*` — Phase 7

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/fundamentals/__init__.py` | create | package docstring, re-exports of `ladder` and `panel` |
| `engine/src/seer_engine/fundamentals/ladder.py` | create | the concept ladder, the measured coverage, the gross-profit fallback, all in the docstring |
| `engine/src/seer_engine/fundamentals/sue.py` | create | seasonal-random-walk SUE with its minimum history |
| `engine/src/seer_engine/fundamentals/panel.py` | create | `Fact`, point-in-time selection, quarterly series, `Snapshot`, `FundamentalPanel` |
| `engine/tests/test_fundamentals_derive.py` | create | 39 tests: coverage, PIT, restatement, tiebreaks, Q4, gaps, SUE, validation |
| `engine/tests/test_strategy_purity.py` | modify | `_pure_sources()` line 34 and the glob assertion at line 62 gain `fundamentals` |

## The five decisions this phase makes, and why

These are not in the index's Decisions table because they are internal to R3. They are stated
here because phases 6 and 7 inherit them.

**1. Selection is per period, with the ladder as the third key, not the first.**
The naive ladder walks the rungs and takes the first tag that has any fact. That breaks on an
ASC 606 adoption: a filer that reported `Revenues` through 2017 and
`RevenueFromContractWithCustomerExcludingAssessedTax` from 2018 still has visible `Revenues`
facts in 2019, so rung 1 would pin the symbol to a stale tag forever. Instead the candidate set
is the union of every rung, grouped by `period_end`, and the winner of each period is the
maximum of `(filed, -rung, accn)`. The newest period wins the snapshot. A tag switch then
resolves itself: the 2018 period simply has no `Revenues` fact. A test pins this.

**2. The deterministic tiebreak is `(filed desc, rung asc, accn desc)`.**
`filed` descending is the restatement rule the user asked for. `rung` ascending is the ladder
preference, which only ever decides a tie. `accn` descending is lexicographic on
`<filer>-<yy>-<serial>`, so it picks the later-assigned accession of two filed the same day —
arbitrary, but total and stable, which is all a tiebreak owes.

**3. `fy` and `fp` are stored and never read.** Filers disagree about them across amendments and
restatements, and a fiscal label is not a date. A fact's period kind comes from its own dates:
`period_start is None` is an instant, an inclusive day count of 80–100 is a quarter, 330–400 is a
fiscal year. A 6- or 9-month year-to-date duration is **dropped** — this module does not
difference YTD facts (see Handoffs).

**4. Flow metrics in `Snapshot` are annual, not trailing-twelve-month.** *(Reconciled: phase 7
was planned against a `flow_ttm` accessor and lost. Its factor definitions were restated on an
annual basis.)*
Annual coverage is 8/8 in the measurement while a clean TTM needs four untroubled quarters, so a
TTM basis would be available for some names and not others and would put a systematic wedge
through the cross-section. The Fama-French convention is annual anyway. The quarterly series
still exists — it is what `quarters()` builds and SUE consumes — it is simply not what the level
metrics read. Balance-sheet figures are the latest instant visible, which for cover-page shares
outstanding is usually within days of `t`, so market cap stays genuinely point-in-time.

**5. An untagged Q4 is derived, and a gap truncates.**
Most filers never tag a Q4 duration: the 10-K carries the fiscal year and three 10-Qs carry
Q1–Q3. Without a reconstruction, SUE would be NaN for almost every filer, because the contiguous
quarterly run would never exceed three. `quarters()` therefore synthesises
`Q4 = FY − (Q1 + Q2 + Q3)` when the fiscal year and exactly three quarters tiling its start are
all visible, dating it `filed = max(filed of its four inputs)` so it can never appear before its
last input did. EPS is only approximately additive across quarters — the diluted share count
moves — so a derived EPS quarter is an estimate and carries `Obs.derived = True`. Any other gap
(a skipped quarter, a fiscal-year change, a hole in the ingest) truncates: the series is the
longest run ending at the newest quarter whose consecutive `period_end` steps are 60–120 days
apart, and SUE returns NaN when that run is shorter than `MIN_QUARTERS`.

## Implementation Steps

### Step 1: `engine/src/seer_engine/fundamentals/ladder.py`
**File:** `engine/src/seer_engine/fundamentals/ladder.py` (new file, create the package directory)
**Change:** The ladder, as data. One `ConceptSpec` per metric, carrying the period kind, the one
XBRL unit it accepts (so a EUR-reporting filer never joins a USD cross-section), and the ordered
tag rungs. The module docstring carries the measured 8-filer coverage table verbatim and
documents the gross-profit fallback and its three bases, as the exit criteria require.

Note the split that the measurement's "shares outstanding 8/8" line hides: the cover-page
`dei:EntityCommonStockSharesOutstanding` is an **instant** and
`us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding` is a **duration**, so they cannot be
rungs of one concept. They are `SHARES_OUTSTANDING` and `DILUTED_SHARES`.

**Code:**
```python
"""The XBRL concept ladder: which ``us-gaap``/``dei`` tags carry each metric, in preference order.

A filer tags the same economic quantity under different element names depending on its
industry, its auditor and which accounting standard was current when it filed. The ladder is
the fixed, ordered list of element names the derivation layer is willing to read for one
metric. It is data, not code: revising it is a one-line change and needs no re-ingest, because
``fundamental_facts`` stores raw facts (plan Decisions table).

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

# Every (taxonomy, tag) the ladder reads. The ingest may store more; the derivation reads these.
LADDER_TAGS: frozenset[tuple[str, str]] = frozenset(TAG_INDEX)


def concepts_for(taxonomy: str, tag: str) -> tuple[tuple[str, int], ...]:
    """``((concept, rung), ...)`` that ``(taxonomy, tag)`` feeds; empty when the ladder ignores it."""
    return TAG_INDEX.get((taxonomy, tag), ())
```
**Impact:** New module. Nothing imports it yet except `panel.py` and `__init__.py`. Revising a
rung later is a one-line change that needs no re-ingest, which is the whole point of the index's
"store raw facts, derive in pure Python" decision.

### Step 2: `engine/src/seer_engine/fundamentals/sue.py`
**File:** `engine/src/seer_engine/fundamentals/sue.py` (new file)
**Change:** SUE on a seasonal random walk, with the minimum history stated in the docstring and
enforced in the code. `MIN_QUARTERS = SEASON + 1 + MIN_SURPRISES = 4 + 1 + 4 = 9`: a surprise
needs the quarter four back, and the current surprise needs at least four prior surprises to be
scaled against, so nine contiguous quarters is the shortest series that can produce a number.
Fewer and the answer is NaN — never a partial figure.

The dispersion excludes the current surprise, so SUE is a z-score of the latest surprise against
recent history. The sum is an explicit left-to-right Python loop, exactly as
`strategies/indicators.py` does it and for the same reason: numpy's pairwise summation changes
the rounding with the array length, so `np.std` would give a symbol one SUE in a 9-quarter series
and a different last bit in a 60-quarter one. The surprise series itself is a single elementwise
subtraction, which is exact at any length.

`sue.py` imports nothing from `panel.py`, so there is no cycle: `panel` depends on `sue`, never
the reverse.

**Code:**
```python
"""SUE -- standardized unexpected earnings on a seasonal random walk (Foster-Olsen-Shevlin).

Analyst-consensus surprise is out of scope: Finnhub's free tier returns 4 quarters and is not
backfillable to 2015 (plan Scope). The free substitute, and the definition PEAD is documented
on, is the seasonal random walk::

    surprise_q = EPS_q - EPS_{q-4}
    SUE_q      = surprise_q / stdev(surprise_{q-1} ... surprise_{q-K})

that is: this quarter's year-on-year change in diluted EPS, divided by the dispersion of the
**prior** such changes. The current surprise is excluded from its own scale, so SUE is a
z-score of the latest surprise against recent history, not a studentised residual.

**Minimum history, stated and enforced.** ``K`` is at most ``MAX_SURPRISES`` (8) and at least
``MIN_SURPRISES`` (4) prior surprises. A surprise needs the quarter four back, so 1 current
plus 4 prior surprises needs ``MIN_QUARTERS`` = 4 + 1 + 4 = **9 contiguous quarters** of diluted
EPS ending at the latest one visible. Fewer than 9 -> NaN. Never a partial number.

The series handed in must already be contiguous in fiscal quarters and ascending; building it
(including deriving an untagged Q4 as FY minus Q1+Q2+Q3, and truncating at a gap) is
``panel.SymbolFundamentals.quarters``.

Bit-identity rule, as ``strategies.indicators``: the surprise series is one elementwise
subtraction, and the dispersion is summed with an explicit left-to-right Python loop -- never
``sum``/``mean``/``std``, whose pairwise summation changes the rounding with the array length.
So a symbol's SUE is the same float whether it is computed from a 9-quarter series or a
60-quarter one, which is what makes the backtest and the nightly job agree.

Pure: no database, network, clock or randomness (tests/test_strategy_purity.py).
"""

from __future__ import annotations

import numpy as np

SEASON = 4  # quarters back for the seasonal random walk
MAX_SURPRISES = 8  # the dispersion window, in prior surprises
MIN_SURPRISES = 4  # fewer prior surprises than this and SUE is NaN
MIN_QUARTERS = SEASON + 1 + MIN_SURPRISES  # 9: the shortest EPS series that can yield a SUE


def _series(eps: object) -> np.ndarray:
    if not isinstance(eps, np.ndarray) or eps.dtype != np.float64 or eps.ndim != 1:
        raise ValueError("eps must be a 1-D float64 array, ascending by fiscal quarter")
    return eps


def surprises(eps: np.ndarray) -> np.ndarray:
    """``eps[i] - eps[i-4]`` for every quarter that has one: length ``len(eps) - 4``, or empty.

    One elementwise subtraction, so each element is bit-identical however long ``eps`` is.
    """
    eps = _series(eps)
    if eps.shape[0] <= SEASON:
        return np.zeros(0, dtype=np.float64)
    return eps[SEASON:] - eps[:-SEASON]


def dispersion(prior: np.ndarray) -> float:
    """Population (ddof 0) standard deviation of ``prior``, summed left to right.

    NaN when ``prior`` is empty or holds a non-finite value.
    """
    prior = _series(prior)
    k = prior.shape[0]
    if k == 0:
        return float("nan")
    acc = prior[0]
    for i in range(1, k):
        acc = acc + prior[i]
    mean = acc / k
    dev = prior[0] - mean
    var = dev * dev
    for i in range(1, k):
        dev = prior[i] - mean
        var = var + dev * dev
    return float(np.sqrt(var / k))


def sue(eps: np.ndarray) -> float:
    """SUE of the last quarter of ``eps`` (ascending, contiguous diluted EPS).

    NaN when the series is shorter than ``MIN_QUARTERS``, when it holds a non-finite value, or
    when the dispersion of the prior surprises is zero or non-finite (a filer whose year-on-year
    change has not moved at all carries no information, and dividing by it would be infinite).
    """
    eps = _series(eps)
    if eps.shape[0] < MIN_QUARTERS:
        return float("nan")
    if not bool(np.all(np.isfinite(eps))):
        return float("nan")
    s = surprises(eps)
    n = s.shape[0]
    current = float(s[n - 1])
    first = n - 1 - MAX_SURPRISES
    if first < 0:
        first = 0
    prior = s[first : n - 1]
    if prior.shape[0] < MIN_SURPRISES:
        return float("nan")
    sd = dispersion(prior)
    if not np.isfinite(sd) or sd == 0.0:
        return float("nan")
    return current / sd
```
**Impact:** New module. `panel.Snapshot.sue` is its only caller in this phase; phase 7 ranks on
that field.

### Step 3: `engine/src/seer_engine/fundamentals/panel.py`
**File:** `engine/src/seer_engine/fundamentals/panel.py` (new file)
**Change:** The point-in-time layer. Reading order:

- `FACT_COLUMNS` — the twelve-column contract with phase 2, and the only place a column name appears.
- `Fact` — frozen, validated. A fact whose `filed` precedes its own `period_end` is rejected: that
  shape is look-ahead and should be loud. `Fact.kind()` classifies from the fact's own dates.
- `fact_from_row` / `facts_from_rows` — row → `Fact`, `Decimal` → float64. `skip_invalid=True`
  (the default) drops and **counts** a malformed row, so one bad fact out of a million cannot
  fail a backtest's data load; the count goes back to the caller, which is phase 6's to surface.
- `SymbolFundamentals.__post_init__` — builds the index. Facts are bucketed by
  `(concept, kind)`, dropping anything the ladder ignores, anything in the wrong unit, anything
  whose kind contradicts its concept's, and every duration that is neither a quarter nor a
  fiscal year. Each bucket is sorted by `filed`, with a parallel tuple of `filed` dates so a
  read is `bisect_right` to the visible prefix plus a scan of it.
- `_best_by_period` — the selection: group the visible prefix by `period_end`, keep the maximum
  of `(filed, -rung, accn)` in each group. This one function is the whole point-in-time rule.
- `quarters()` — the quarterly series: selected quarters, plus a derived Q4 where one can be
  reconstructed, truncated at the first gap walking back from the newest.
- `as_of()` — annual for every duration concept, latest instant for every instant concept, the
  gross-profit resolution (reported → derived → none, and the derivation refuses two legs from
  different fiscal years), then SUE over the quarterly diluted-EPS series.
- `FundamentalPanel` / `EMPTY_PANEL` — the type phase 6 stores on `Market`.

**Code:**
```python
"""Point-in-time selection over raw XBRL facts: the panel the lab ranks on.

``fundamental_facts`` stores every fact EDGAR served, restatements included (plan invariant 3).
This module is the only place that decides *which* of them a backtest standing on day ``t`` is
allowed to see, and what metric they add up to. Pure: no database, network, clock or randomness
(tests/test_strategy_purity.py).

**The point-in-time rule.** ``filed`` is the availability date and the only one. ``period_end``
is never an availability date -- a Q4 figure for the period ending 2015-12-31 is typically filed
in February 2016, and a backtest that read it on 2015-12-31 would be trading on a number nobody
had. So every read starts by discarding every fact with ``filed > t``.

**Selection, and its deterministic tiebreak.** Among the visible facts of one concept, of one
period kind, sharing one ``period_end``, the chosen fact is the maximum of

    (filed, -rung, accn)

- **``filed`` descending** -- the latest restatement available at ``t``. This is the rule the
  user asked for: two facts sharing a ``period_end`` and differing in ``filed`` and ``accn``
  resolve to the earlier value at an earlier ``t`` and the later value afterwards.
- **``rung`` ascending** -- same period, same filing date, two different ladder tags: the
  preferred tag wins (``ladder.ConceptSpec.tags`` order).
- **``accn`` descending, lexicographically** -- two facts filed the same day under the same tag.
  An accession number is ``<filer>-<yy>-<serial>``, so the lexicographic maximum is the
  later-assigned accession. Arbitrary, but total and stable, which is all a tiebreak owes.

Selection is **per period**, not per symbol: the ladder preference is only the third key. That
is what makes an ASC 606 tag switch work. A filer that reported ``Revenues`` through 2017 and
``RevenueFromContractWithCustomerExcludingAssessedTax`` from 2018 has both tags visible in 2019;
the 2018 period simply has no ``Revenues`` fact, so the lower rung wins it on its own merits
while the 2017 period keeps the higher rung. No per-symbol tag is ever pinned.

**Fiscal labels are metadata.** ``fy`` and ``fp`` are stored and never read by the selection:
filers disagree about them across restatements and amended filings. A fact's period kind comes
from its own dates -- ``period_start is None`` is an instant, 80-100 days is a quarter, 330-400
days is a fiscal year. Anything else (a 6- or 9-month year-to-date figure) is dropped; this
module does not difference YTD facts.

**Flow metrics are annual.** ``Snapshot``'s income-statement and cash-flow figures are the
latest *fiscal year* visible at ``t``, not a trailing twelve months. Annual coverage is 8/8 in
the measured sample while a clean TTM needs four untroubled quarters, and mixing an annual basis
for some names with a TTM basis for others would put a systematic wedge through the
cross-section. Balance-sheet figures are the latest instant visible, which for cover-page shares
outstanding is usually within days of ``t``. The quarterly series exists -- it is what
``quarters`` builds and ``sue`` consumes -- it is just not what the level metrics use.

**Deriving an untagged Q4.** Most filers never tag a Q4 duration: the 10-K carries the fiscal
year and the three 10-Qs carry Q1-Q3. ``quarters`` reconstructs it as ``FY - (Q1 + Q2 + Q3)``
when the annual fact and exactly three quarters tiling its start are all visible, dating the
synthetic fact ``filed = max(filed of its four inputs)`` so it can never appear before its last
input did. EPS is not exactly additive across quarters (the diluted share count moves), so a
derived Q4 EPS is an approximation -- ``Obs.derived`` flags it and the docstring of
``SymbolFundamentals.quarters`` says so.

**A gap truncates.** The quarterly series is the longest run of quarters ending at the latest
visible one whose consecutive ``period_end`` steps are 60-120 days apart. A filer that skipped a
quarter, changed its fiscal year, or has a hole in the ingest keeps only the run after the hole;
everything older is unreachable until the hole is filled. ``sue`` then returns NaN whenever that
run is shorter than ``sue.MIN_QUARTERS``.
"""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal

import numpy as np

from seer_engine.fundamentals import ladder
from seer_engine.fundamentals.sue import sue as sue_of

# The column order ``facts_from_rows`` expects. This is the contract with PHASE 6's projection,
# not with phase 2's table: `fundamental_facts` has no `symbol` column (facts are keyed by CIK),
# and phase 6's COPY joins `ticker_cik` to supply one. Phase 6 imports this tuple rather than
# restating it, so there is exactly one owner of the order. A row may also be a Mapping keyed
# by these names.
FACT_COLUMNS: tuple[str, ...] = (
    "symbol",
    "taxonomy",
    "tag",
    "unit",
    "period_start",
    "period_end",
    "val",
    "accn",
    "form",
    "fy",
    "fp",
    "filed",
)

KIND_QUARTER = "Q"
KIND_ANNUAL = "A"
KIND_INSTANT = "I"  # ladder.INSTANT is the spec kind; this is a fact's own classification

QUARTER_MIN_DAYS, QUARTER_MAX_DAYS = 80, 100  # inclusive day count of a fiscal quarter
ANNUAL_MIN_DAYS, ANNUAL_MAX_DAYS = 330, 400  # inclusive day count of a fiscal year
STEP_MIN_DAYS, STEP_MAX_DAYS = 60, 120  # period_end to period_end of consecutive quarters

GROSS_PROFIT_REPORTED = "reported"
GROSS_PROFIT_DERIVED = "derived"
GROSS_PROFIT_NONE = "none"

NAN = float("nan")


class FundamentalsError(ValueError):
    """A fact or a panel is malformed."""


def _check_date(name: str, d: object) -> date:
    if isinstance(d, datetime) or not isinstance(d, date):
        raise FundamentalsError(f"{name} must be a date, got {type(d).__name__}")
    return d


def _check_str(name: str, s: object) -> str:
    if not isinstance(s, str) or not s:
        raise FundamentalsError(f"{name} must be a non-empty str, got {s!r}")
    return s


@dataclass(frozen=True, slots=True)
class Fact:
    """One XBRL fact as EDGAR served it, for one symbol.

    ``period_start`` is None for an instant (a balance-sheet or cover-page figure). ``filed`` is
    the availability date and must not precede ``period_end``: a fact filed before its own
    period closed is look-ahead-shaped and is rejected rather than quietly trusted.
    """

    symbol: str
    taxonomy: str
    tag: str
    unit: str
    period_start: date | None
    period_end: date
    val: float
    accn: str
    form: str
    fy: int | None
    fp: str | None
    filed: date

    def __post_init__(self) -> None:
        _check_str("symbol", self.symbol)
        _check_str("taxonomy", self.taxonomy)
        _check_str("tag", self.tag)
        _check_str("unit", self.unit)
        _check_str("accn", self.accn)
        _check_str("form", self.form)
        _check_date("period_end", self.period_end)
        _check_date("filed", self.filed)
        if self.period_start is not None:
            _check_date("period_start", self.period_start)
            if self.period_start > self.period_end:
                raise FundamentalsError(
                    f"{self.symbol} {self.tag}: period_start {self.period_start} is after "
                    f"period_end {self.period_end}"
                )
        if self.filed < self.period_end:
            raise FundamentalsError(
                f"{self.symbol} {self.tag}: filed {self.filed} precedes period_end {self.period_end}"
            )
        if not isinstance(self.val, float):
            raise FundamentalsError(f"{self.symbol} {self.tag}: val must be a float, got {type(self.val).__name__}")
        if not np.isfinite(self.val):
            raise FundamentalsError(f"{self.symbol} {self.tag}: val must be finite, got {self.val!r}")
        if self.fy is not None and (isinstance(self.fy, bool) or not isinstance(self.fy, int)):
            raise FundamentalsError(f"{self.symbol} {self.tag}: fy must be an int or None, got {self.fy!r}")
        if self.fp is not None and not isinstance(self.fp, str):
            raise FundamentalsError(f"{self.symbol} {self.tag}: fp must be a str or None, got {self.fp!r}")

    def kind(self) -> str | None:
        """``KIND_INSTANT``, ``KIND_QUARTER``, ``KIND_ANNUAL``, or None for a duration that is neither."""
        if self.period_start is None:
            return KIND_INSTANT
        days = (self.period_end - self.period_start).days + 1
        if QUARTER_MIN_DAYS <= days <= QUARTER_MAX_DAYS:
            return KIND_QUARTER
        if ANNUAL_MIN_DAYS <= days <= ANNUAL_MAX_DAYS:
            return KIND_ANNUAL
        return None


def _to_float(name: str, v: object) -> float:
    if isinstance(v, bool):
        raise FundamentalsError(f"{name} must be a number, got a bool")
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (int, float)):
        return float(v)
    raise FundamentalsError(f"{name} must be a number, got {type(v).__name__}")


def fact_from_row(row: Mapping[str, object] | Sequence[object]) -> Fact:
    """A ``Fact`` from one ``fundamental_facts`` row: a Mapping, or a Sequence in ``FACT_COLUMNS`` order."""
    if isinstance(row, Mapping):
        missing = [c for c in FACT_COLUMNS if c not in row]
        if missing:
            raise FundamentalsError(f"row is missing {missing}")
        values = [row[c] for c in FACT_COLUMNS]
    elif isinstance(row, Sequence) and not isinstance(row, (str, bytes)):
        if len(row) != len(FACT_COLUMNS):
            raise FundamentalsError(f"row has {len(row)} values, expected {len(FACT_COLUMNS)} {FACT_COLUMNS}")
        values = list(row)
    else:
        raise FundamentalsError(f"row must be a Mapping or a Sequence, got {type(row).__name__}")
    symbol, taxonomy, tag, unit, period_start, period_end, val, accn, form, fy, fp, filed = values
    # phase 2 stores `period_start = period_end` for an INSTANTANEOUS fact, because the column
    # is NOT NULL and sits in the primary key (one 10-K tags Revenues for both the fiscal year
    # and Q4 under the same accn/tag/unit/period_end, so the period must be keyed). In memory
    # an instant is `period_start is None`, which is what `Fact.kind()` and `quarters()` read.
    # This is the one place the two encodings meet. No us-gaap or dei DURATION fact has a
    # one-day period, so the mapping is lossless.
    if period_start is not None and period_start == period_end:
        period_start = None
    return Fact(
        symbol=symbol,  # type: ignore[arg-type]
        taxonomy=taxonomy,  # type: ignore[arg-type]
        tag=tag,  # type: ignore[arg-type]
        unit=unit,  # type: ignore[arg-type]
        period_start=period_start,  # type: ignore[arg-type]
        period_end=period_end,  # type: ignore[arg-type]
        val=_to_float("val", val),
        accn=accn,  # type: ignore[arg-type]
        form=form,  # type: ignore[arg-type]
        fy=fy,  # type: ignore[arg-type]
        fp=fp,  # type: ignore[arg-type]
        filed=filed,  # type: ignore[arg-type]
    )


def facts_from_rows(
    rows: Iterable[Mapping[str, object] | Sequence[object]],
    *,
    skip_invalid: bool = True,
) -> tuple[tuple[Fact, ...], int]:
    """``(facts, skipped)`` from ``fundamental_facts`` rows.

    ``skip_invalid`` (the default) drops a malformed row and counts it, so one bad fact out of a
    million cannot fail a backtest's data load; the caller decides what to do with the count.
    ``skip_invalid=False`` raises ``FundamentalsError`` on the first bad row instead.
    """
    out: list[Fact] = []
    skipped = 0
    for row in rows:
        try:
            out.append(fact_from_row(row))
        except FundamentalsError:
            if not skip_invalid:
                raise
            skipped += 1
    return tuple(out), skipped


@dataclass(frozen=True, slots=True)
class Obs:
    """One selected observation: the value of a concept for one period, as known at some ``t``."""

    concept: str
    taxonomy: str
    tag: str
    period_start: date | None
    period_end: date
    filed: date
    accn: str
    val: float
    derived: bool = False


def _obs(concept: str, f: Fact) -> Obs:
    return Obs(concept, f.taxonomy, f.tag, f.period_start, f.period_end, f.filed, f.accn, f.val)


def _key(entry: tuple[Fact, int]) -> tuple[date, int, str]:
    f, rung = entry
    return (f.filed, -rung, f.accn)


@dataclass(frozen=True, slots=True)
class Snapshot:
    """Everything the factor layer reads about one symbol on one day.

    Every number is a float64; NaN means "not available at ``t``", never zero. Flow figures
    (``revenue`` .. ``diluted_shares``) are the latest **fiscal year** visible; balance figures
    (``assets``, ``equity``, ``shares_outstanding``) the latest **instant** visible. The two can
    and usually do have different ``period_end``s, which is correct: a balance sheet is newer
    than the fiscal year it closes.

    ``fiscal_period_end`` is the period end of the annual figures; ``filed`` the newest filing
    date behind any figure in the snapshot. ``observations`` maps concept name to the ``Obs``
    actually chosen, so a test or a report can say which tag and which accession a number came
    from. ``sue_quarters`` is the length of the contiguous quarterly EPS run behind ``sue``.
    """

    symbol: str
    asof: date
    fiscal_period_end: date | None
    filed: date | None
    revenue: float
    cost_of_revenue: float
    gross_profit: float
    gross_profit_basis: str
    operating_income: float
    net_income: float
    operating_cash_flow: float
    diluted_eps: float
    diluted_shares: float
    assets: float
    equity: float
    shares_outstanding: float
    sue: float
    sue_quarters: int
    observations: Mapping[str, Obs]

    def tag(self, concept: str) -> str | None:
        """The ladder tag behind ``concept`` in this snapshot, or None when it has no value."""
        o = self.observations.get(concept)
        return None if o is None else o.tag

    def value(self, concept: str) -> float:
        """``concept``'s value, or NaN. ``ladder.LadderError`` when the ladder has no such concept."""
        ladder.spec(concept)
        o = self.observations.get(concept)
        if o is None:
            return NAN
        return o.val


def _ratio(num: float, den: float) -> float:
    """``num / den``, NaN unless both are finite and ``den`` is non-zero."""
    if not np.isfinite(num) or not np.isfinite(den) or den == 0.0:
        return NAN
    return num / den


def gross_profitability(s: Snapshot) -> float:
    """Novy-Marx gross profitability: gross profit over total assets. NaN when either is missing."""
    return _ratio(s.gross_profit, s.assets)


def return_on_equity(s: Snapshot) -> float:
    """Net income over common equity. NaN when either is missing or equity is zero."""
    return _ratio(s.net_income, s.equity)


def return_on_assets(s: Snapshot) -> float:
    """Net income over total assets. NaN when either is missing."""
    return _ratio(s.net_income, s.assets)


def accrual_ratio(s: Snapshot) -> float:
    """``(net income - operating cash flow) / assets``: the Sloan accrual quality screen."""
    if not np.isfinite(s.net_income) or not np.isfinite(s.operating_cash_flow):
        return NAN
    return _ratio(s.net_income - s.operating_cash_flow, s.assets)


def book_value_per_share(s: Snapshot) -> float:
    """Common equity per share outstanding -- the book half of book-to-price (price is the caller's)."""
    return _ratio(s.equity, s.shares_outstanding)


@dataclass(frozen=True, eq=False)
class SymbolFundamentals:
    """One symbol's facts, indexed for point-in-time reads.

    ``facts`` may hold tags the ladder ignores; they are kept (the panel is the raw record) and
    skipped by every read. Construction is O(n log n); a read is a bisect to the visible prefix
    plus a scan of it.
    """

    symbol: str
    facts: tuple[Fact, ...]
    _entries: Mapping[tuple[str, str], tuple[tuple[Fact, int], ...]] = field(init=False, repr=False)
    _filed: Mapping[tuple[str, str], tuple[date, ...]] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        _check_str("symbol", self.symbol)
        if not isinstance(self.facts, tuple):
            raise FundamentalsError("facts must be a tuple")
        buckets: dict[tuple[str, str], list[tuple[Fact, int]]] = {}
        for f in self.facts:
            if not isinstance(f, Fact):
                raise FundamentalsError(f"expected a Fact, got {type(f).__name__}")
            if f.symbol != self.symbol:
                raise FundamentalsError(f"fact for {f.symbol!r} in the facts of {self.symbol!r}")
            kind = f.kind()
            if kind is None:
                continue  # a 6- or 9-month year-to-date duration: not a quarter, not a year
            for concept, rung in ladder.concepts_for(f.taxonomy, f.tag):
                cs = ladder.LADDER[concept]
                if f.unit != cs.unit:
                    continue  # a EUR filer's Revenues never joins a USD cross-section
                if cs.kind == ladder.INSTANT and kind != KIND_INSTANT:
                    continue
                if cs.kind == ladder.DURATION and kind == KIND_INSTANT:
                    continue
                buckets.setdefault((concept, kind), []).append((f, rung))
        entries: dict[tuple[str, str], tuple[tuple[Fact, int], ...]] = {}
        filed: dict[tuple[str, str], tuple[date, ...]] = {}
        for bucket, items in buckets.items():
            items.sort(key=lambda e: (e[0].filed, e[0].period_end, e[1], e[0].accn))
            entries[bucket] = tuple(items)
            filed[bucket] = tuple(e[0].filed for e in items)
        object.__setattr__(self, "_entries", entries)
        object.__setattr__(self, "_filed", filed)

    def _visible(self, concept: str, kind: str, t: date) -> tuple[tuple[Fact, int], ...]:
        items = self._entries.get((concept, kind))
        if not items:
            return ()
        cut = bisect_right(self._filed[(concept, kind)], t)
        return items[:cut]

    def _best_by_period(self, concept: str, kind: str, t: date) -> dict[date, tuple[Fact, int]]:
        best: dict[date, tuple[Fact, int]] = {}
        for entry in self._visible(concept, kind, t):
            period_end = entry[0].period_end
            current = best.get(period_end)
            if current is None or _key(entry) > _key(current):
                best[period_end] = entry
        return best

    def latest(self, concept: str, kind: str, t: date) -> Obs | None:
        """The newest period of ``concept`` (``kind`` is ``KIND_INSTANT``/``KIND_QUARTER``/``KIND_ANNUAL``) visible at ``t``."""
        ladder.spec(concept)
        _check_date("t", t)
        best = self._best_by_period(concept, kind, t)
        if not best:
            return None
        period_end = max(best)
        return _obs(concept, best[period_end][0])

    def instant(self, concept: str, t: date) -> Obs | None:
        """The newest balance of ``concept`` visible at ``t``."""
        if ladder.spec(concept).kind != ladder.INSTANT:
            raise FundamentalsError(f"{concept} is a duration concept, not an instant")
        return self.latest(concept, KIND_INSTANT, t)

    def annual(self, concept: str, t: date) -> Obs | None:
        """The newest fiscal-year figure of ``concept`` visible at ``t``."""
        if ladder.spec(concept).kind != ladder.DURATION:
            raise FundamentalsError(f"{concept} is an instant concept, not a duration")
        return self.latest(concept, KIND_ANNUAL, t)

    def _derived_q4(self, concept: str, t: date, quarterly: dict[date, tuple[Fact, int]]) -> list[Obs]:
        out: list[Obs] = []
        for period_end, (annual_fact, _) in self._best_by_period(concept, KIND_ANNUAL, t).items():
            if period_end in quarterly:
                continue
            start = annual_fact.period_start
            if start is None:
                continue
            legs = [
                f
                for pe, (f, _r) in quarterly.items()
                if f.period_start is not None and f.period_start >= start and pe < period_end
            ]
            if len(legs) != 3:
                continue
            legs.sort(key=lambda f: f.period_end)
            if legs[0].period_start != start:
                continue
            one_day = timedelta(days=1)
            if legs[1].period_start != legs[0].period_end + one_day:
                continue
            if legs[2].period_start != legs[1].period_end + one_day:
                continue
            val = annual_fact.val - legs[0].val
            val = val - legs[1].val
            val = val - legs[2].val
            filed = annual_fact.filed
            for leg in legs:
                if leg.filed > filed:
                    filed = leg.filed
            out.append(
                Obs(
                    concept=concept,
                    taxonomy=annual_fact.taxonomy,
                    tag=annual_fact.tag,
                    period_start=legs[2].period_end + one_day,
                    period_end=period_end,
                    filed=filed,
                    accn=annual_fact.accn,
                    val=val,
                    derived=True,
                )
            )
        return out

    def quarters(self, concept: str, t: date, *, derive_q4: bool = True) -> tuple[Obs, ...]:
        """``concept``'s quarterly series visible at ``t``: ascending, contiguous, ending at the newest.

        A quarter the filer never tagged is reconstructed from the fiscal year when the year and
        exactly three quarters tiling its start are all visible (``derive_q4``); the synthetic
        observation carries ``derived=True`` and is dated by the newest of its four inputs, so it
        appears no earlier than the last of them. EPS is only approximately additive across
        quarters -- the diluted share count moves -- so a derived EPS quarter is an estimate.

        The run is cut at the first step outside 60-120 days walking back from the newest
        quarter, so a skipped quarter or a fiscal-year change hides everything before it.
        """
        if ladder.spec(concept).kind != ladder.DURATION:
            raise FundamentalsError(f"{concept} is an instant concept and has no quarterly series")
        _check_date("t", t)
        quarterly = self._best_by_period(concept, KIND_QUARTER, t)
        by_period: dict[date, Obs] = {pe: _obs(concept, f) for pe, (f, _r) in quarterly.items()}
        if derive_q4:
            for o in self._derived_q4(concept, t, quarterly):
                by_period.setdefault(o.period_end, o)
        if not by_period:
            return ()
        series = [by_period[pe] for pe in sorted(by_period)]
        first = len(series) - 1
        while first > 0:
            step = (series[first].period_end - series[first - 1].period_end).days
            if not STEP_MIN_DAYS <= step <= STEP_MAX_DAYS:
                break
            first -= 1
        return tuple(series[first:])

    def as_of(self, t: date) -> Snapshot:
        """Everything known about this symbol on ``t``, with every unavailable figure NaN."""
        _check_date("t", t)
        obs: dict[str, Obs] = {}
        for concept in ladder.DURATION_CONCEPTS:
            o = self.annual(concept, t)
            if o is not None:
                obs[concept] = o
        for concept in ladder.INSTANT_CONCEPTS:
            o = self.instant(concept, t)
            if o is not None:
                obs[concept] = o

        basis = GROSS_PROFIT_NONE
        gp = obs.get(ladder.GROSS_PROFIT)
        if gp is not None:
            basis = GROSS_PROFIT_REPORTED
        else:
            rev = obs.get(ladder.REVENUE)
            cost = obs.get(ladder.COST_OF_REVENUE)
            if rev is not None and cost is not None and rev.period_end == cost.period_end:
                gp = Obs(
                    concept=ladder.GROSS_PROFIT,
                    taxonomy=rev.taxonomy,
                    tag=f"{rev.tag}-{cost.tag}",
                    period_start=rev.period_start,
                    period_end=rev.period_end,
                    filed=max(rev.filed, cost.filed),
                    accn=max(rev.accn, cost.accn),
                    val=rev.val - cost.val,
                    derived=True,
                )
                obs[ladder.GROSS_PROFIT] = gp
                basis = GROSS_PROFIT_DERIVED

        eps_series = self.quarters(ladder.DILUTED_EPS, t)
        eps = np.array([o.val for o in eps_series], dtype=np.float64)

        annual_ends = [o.period_end for c, o in obs.items() if ladder.LADDER[c].kind == ladder.DURATION]
        filed_dates = [o.filed for o in obs.values()]
        return Snapshot(
            symbol=self.symbol,
            asof=t,
            fiscal_period_end=max(annual_ends) if annual_ends else None,
            filed=max(filed_dates) if filed_dates else None,
            revenue=obs[ladder.REVENUE].val if ladder.REVENUE in obs else NAN,
            cost_of_revenue=obs[ladder.COST_OF_REVENUE].val if ladder.COST_OF_REVENUE in obs else NAN,
            gross_profit=gp.val if gp is not None else NAN,
            gross_profit_basis=basis,
            operating_income=obs[ladder.OPERATING_INCOME].val if ladder.OPERATING_INCOME in obs else NAN,
            net_income=obs[ladder.NET_INCOME].val if ladder.NET_INCOME in obs else NAN,
            operating_cash_flow=(
                obs[ladder.OPERATING_CASH_FLOW].val if ladder.OPERATING_CASH_FLOW in obs else NAN
            ),
            diluted_eps=obs[ladder.DILUTED_EPS].val if ladder.DILUTED_EPS in obs else NAN,
            diluted_shares=obs[ladder.DILUTED_SHARES].val if ladder.DILUTED_SHARES in obs else NAN,
            assets=obs[ladder.ASSETS].val if ladder.ASSETS in obs else NAN,
            equity=obs[ladder.EQUITY].val if ladder.EQUITY in obs else NAN,
            shares_outstanding=(
                obs[ladder.SHARES_OUTSTANDING].val if ladder.SHARES_OUTSTANDING in obs else NAN
            ),
            sue=sue_of(eps),
            sue_quarters=len(eps_series),
            observations=obs,
        )


@dataclass(frozen=True, eq=False)
class FundamentalPanel:
    """Every symbol's facts: what ``Market.fundamentals`` holds and what the factor layer reads.

    Empty is a normal state -- a store with no ``fundamental_facts`` rows yields ``EMPTY_PANEL``
    and every read returns None, so a backtest that predates the ingest keeps working.
    """

    symbols: Mapping[str, SymbolFundamentals]

    def __post_init__(self) -> None:
        if not isinstance(self.symbols, Mapping):
            raise FundamentalsError(f"symbols must be a Mapping, got {type(self.symbols).__name__}")
        for symbol, sf in self.symbols.items():
            if not isinstance(sf, SymbolFundamentals):
                raise FundamentalsError(f"symbols[{symbol!r}] must be a SymbolFundamentals")
            if sf.symbol != symbol:
                raise FundamentalsError(f"symbols[{symbol!r}] holds facts for {sf.symbol!r}")

    def __len__(self) -> int:
        return len(self.symbols)

    def __contains__(self, symbol: object) -> bool:
        return symbol in self.symbols

    def names(self) -> tuple[str, ...]:
        """Every symbol with at least one fact, sorted."""
        return tuple(sorted(self.symbols))

    def get(self, symbol: str) -> SymbolFundamentals | None:
        """``symbol``'s facts, or None when the panel has none."""
        return self.symbols.get(symbol)

    def as_of(self, symbol: str, t: date) -> Snapshot | None:
        """``symbol``'s snapshot on ``t``, or None when the panel has no facts for it."""
        sf = self.symbols.get(symbol)
        if sf is None:
            return None
        return sf.as_of(t)

    def snapshots_on(self, t: date, symbols: Iterable[str] | None = None) -> dict[str, Snapshot]:
        """``{symbol: Snapshot}`` on ``t`` for ``symbols`` (default: every symbol in the panel)."""
        _check_date("t", t)
        names = self.names() if symbols is None else tuple(symbols)
        out: dict[str, Snapshot] = {}
        for symbol in names:
            sf = self.symbols.get(symbol)
            if sf is not None:
                out[symbol] = sf.as_of(t)
        return out

    @staticmethod
    def from_facts(facts: Iterable[Fact]) -> FundamentalPanel:
        """A panel from facts in any order, grouped by symbol and sorted canonically."""
        grouped: dict[str, list[Fact]] = {}
        for f in facts:
            if not isinstance(f, Fact):
                raise FundamentalsError(f"expected a Fact, got {type(f).__name__}")
            grouped.setdefault(f.symbol, []).append(f)
        symbols: dict[str, SymbolFundamentals] = {}
        for symbol in sorted(grouped):
            rows = grouped[symbol]
            rows.sort(key=lambda f: (f.taxonomy, f.tag, f.period_end, f.filed, f.accn))
            symbols[symbol] = SymbolFundamentals(symbol, tuple(rows))
        return FundamentalPanel(symbols)


EMPTY_PANEL = FundamentalPanel({})
```
**Impact:** This is the module phases 6 and 7 import. `FundamentalPanel` and `Snapshot` are the
contract; everything else is reachable but not required.

### Step 4: `engine/src/seer_engine/fundamentals/__init__.py`
**File:** `engine/src/seer_engine/fundamentals/__init__.py` (new file)
**Change:** Package docstring and re-exports, in the style of `strategies/__init__.py`. The one
non-obvious rule is spelled out in the docstring: nothing from `sue` is re-exported, because
`from seer_engine.fundamentals.sue import sue` would rebind the package attribute `sue` from the
module to the function and `from seer_engine.fundamentals import sue` would then hand a caller
the function when it wanted the module. (This was not hypothetical — the prototype hit it.)

**Code:**
```python
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
```
**Impact:** `from seer_engine.fundamentals import FundamentalPanel, Snapshot, EMPTY_PANEL` works,
which is what phase 6 will write.

### Step 5: Extend the purity glob to cover the new package
**File:** `engine/tests/test_strategy_purity.py:1-9` (docstring), `:34` (`_pure_sources`), `:62-71` (the glob assertion)
**Change:** Three edits, all additive.

The gate currently globs `strategies/*.py`, `backtest/*.py` and `paper/*.py`.
`seer_engine/fundamentals/` is not in it, and this package is exactly the pure numeric code the
gate exists for — it must import no `psycopg`, `requests`, `time`, `random`, `logging`, `urllib`
or `socket`, read no clock, and call no `open`/`print`, or phase 6 would be wiring an impure
module into a frozen `Market`. Extending the glob makes that permanent for every module added to
the package later, instead of a convention someone has to remember.

`_module_name` already handles a two-level path (`path.parent.name` is `fundamentals`), so it
needs no change. The edit cannot weaken the gate: it only adds files to the set being checked.

Edit 1 — the docstring's first paragraph, lines 1–6:

```python
"""Strategy, backtest, fundamentals and paper core modules are pure (handover §6.8, plan
invariant 2; paper-trading-ship invariant 4; edgar-fundamentals phase 5).

Globs ``seer_engine/strategies/*.py``, ``seer_engine/backtest/*.py``,
``seer_engine/fundamentals/*.py`` and ``seer_engine/paper/*.py`` (every module except the impure
edges ``backtest/io.py`` and ``paper/store.py``), so modules added later are covered without
editing this file.
```

Edit 2 — `_pure_sources`, line 34:

```python
def _pure_sources() -> list[Path]:
    files = []
    for package in ("strategies", "backtest", "fundamentals", "paper"):
        files += [p for p in sorted((PKG / package).glob("*.py")) if (package, p.name) not in IMPURE]
    return files
```

Edit 3 — the glob assertion, lines 61–72:

```python
def test_the_glob_finds_the_strategy_modules():
    names = {_module_name(p) for p in _pure_sources()}
    assert {
        "seer_engine.strategies",
        "seer_engine.strategies.base",
        "seer_engine.strategies.indicators",
        "seer_engine.strategies.a",
        "seer_engine.backtest",
        "seer_engine.fundamentals",
        "seer_engine.fundamentals.ladder",
        "seer_engine.fundamentals.panel",
        "seer_engine.fundamentals.sue",
        "seer_engine.paper",
        "seer_engine.paper.roster",
    } <= names
    assert "seer_engine.backtest.io" not in names
    assert "seer_engine.paper.store" not in names
```

**Impact — reconciled and settled; do this, do not reopen it.** Invariant 5 was reworded to
"no phase weakens the purity gate", and it now says explicitly that **phase 5 MAY extend the
glob additively** and that **phase 6 must leave the file byte-identical**. Phase 6's exit
criterion reads "byte-identical to what phase 5 left", not "unmodified since `origin/main`".
Extending the glob strengthens the gate — it only adds files to the set being checked — so the
index's earlier literal wording was wrong, not this step. The fallback of putting the same AST
checks inside `test_fundamentals_derive.py` is **not** taken: it would not cover whatever lands
in the package next. The three new modules were checked against the gate's exact AST rules
during planning and pass clean.

### Step 6: `engine/tests/test_fundamentals_derive.py`
**File:** `engine/tests/test_fundamentals_derive.py` (new file)
**Change:** 39 tests, no database, no network, no fixtures from `conftest.py`.

The honesty rule in the header matters: the nine-metric coverage table **is** the 2026-10-05
measurement and the test reproduces it exactly, including which two filers tag `GrossProfit` and
which two lack `OperatingIncomeLoss`. The `CostOfRevenue` leg in the same fixture is **not** a
measurement — it was not measured — and the test says so; it is there to exercise the three
gross-profit bases, with SIVB (a bank, no cost of revenue at all) producing `"none"`.

What is covered:

| Group | Tests |
|---|---|
| measured coverage | the per-filer tag, the 8/8/8/8/8/8/8/6/2 counts, SIVB as the only revenue-tag variant |
| gross profit | reported (CELG), derived (ATVI), refused (SIVB), refused across two fiscal years, all three cost tags |
| point in time | `period_end` is not availability; a restatement is invisible until filed; both restatements stay in the panel |
| tiebreaks | equal `filed` → greater `accn`; equal `filed` and period → preferred rung; a tag switch resolved per period |
| filters | EUR dropped; a 9-month YTD is neither a quarter nor a year; the kind boundaries |
| quarterly series | Q4 derived; a derived Q4 invisible before the 10-K is filed; a tagged Q4 never overwritten; a gap truncates |
| SUE | the surprise series; the hand-computed value `4/√5`; `MIN_QUARTERS == 9` enforced; zero dispersion → NaN; the 8-surprise cap; a non-float64 series rejected; `Snapshot.sue`/`sue_quarters`; a gap → NaN |
| ratios | `return_on_equity`, `book_value_per_share`, `gross_profitability`, and each refusing a missing denominator |
| construction | `filed < period_end` rejected; non-finite rejected; row → `Fact` both ways; `facts_from_rows` skip-and-count; cross-symbol fact rejected; order independence; `EMPTY_PANEL`; `snapshots_on`; unknown concept raises |

The SUE arithmetic is pinned by hand, not by a golden file:
`eps = [1,1,1,1,2,1.5,1,0.5,3]` → surprises `[1, 0.5, 0, −0.5, 1]`; prior four have mean `0.25`
and population variance `(0.5625+0.0625+0.0625+0.5625)/4 = 0.3125`, so
`SUE = 1 / √0.3125 = 4/√5 = 1.7888543819998317`.

**Code:**
```python
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
```
**Impact:** The phase's whole exit criteria are observable from this one file.

## Verification

**Build:**
```sh
cd /home/miftah/.worktrees/seer/edgar-fundamentals
engine/.venv/bin/python -c "import seer_engine.fundamentals as f; print(len(f.CONCEPTS), f.EMPTY_PANEL)"
```

**Tests:**
```sh
cd /home/miftah/.worktrees/seer/edgar-fundamentals
engine/.venv/bin/python -m pytest engine/tests/test_fundamentals_derive.py -q
engine/.venv/bin/python -m pytest engine/tests/test_strategy_purity.py -q
engine/.venv/bin/python -m pytest engine/tests -q          # invariant 1: the whole suite still passes
engine/.venv/bin/ruff check engine/src/seer_engine/fundamentals engine/tests/test_fundamentals_derive.py
```

Expected: `39 passed` from the derivation suite; `3 passed` from the purity suite with the new
package in its glob; the full suite unchanged except for the 39 additions; ruff clean under the
project's `select = ["E9", "F"]`, `ignore = ["F401"]`.

**Manual check:** the gross-profit fallback and its tag candidates are in
`ladder.py`'s module docstring (the exit criterion says "documented in the module docstring", so
read it); `sue.py`'s docstring states `MIN_QUARTERS = 9` and derives it; `panel.py`'s docstring
states the tiebreak and that `period_end` is never an availability date.

**Exit criteria:**
1. `test_the_ladder_reproduces_the_measured_coverage` and
   `test_the_measured_coverage_counts_are_eight_eight_six_and_two` pass — revenue 8/8 over two tag
   variants, net income / assets / equity / OCF / diluted EPS / shares outstanding 8/8, operating
   income 6/8 missing exactly SIVB and PXD, gross profit reported for exactly CELG and WRK.
2. `test_a_restatement_is_invisible_until_it_is_filed` passes — two facts sharing `period_end`,
   differing in `filed` and `accn`; the earlier `t` sees the earlier value and the earlier `accn`.
3. `test_period_end_is_never_an_availability_date` passes — the FY2015 figure is NaN on
   2015-12-31 and on 2016-02-25, and present on 2016-02-26.
4. `test_sue_needs_nine_contiguous_quarters_and_says_so` passes with `sue.MIN_QUARTERS == 9`, and
   `test_a_gap_makes_sue_nan` shows what a gap does.
5. `pytest engine/tests -q` is green and `test_strategy_purity.py` now checks three more modules.

## Handoffs

- **Phase 6 — the panel load.** `FundamentalPanel.from_facts(facts_from_rows(cursor)[0])` is the
  whole construction. `EMPTY_PANEL` is the correct value when the store has no rows, so
  `load_market` keeps working against a database that predates the ingest. `facts_from_rows`
  returns a skipped count; surfacing it is phase 6's call.
- **Phase 6 — caching snapshots.** `as_of` is a bisect plus a scan of the visible prefix per
  concept, which is fine per rebalance and wasteful per session. `Allocator.prepare_market`
  should compute `panel.snapshots_on(t)` once per rebalance date and keep it. This phase
  deliberately adds no memo: a mutable cache on a frozen pure object is not worth the argument.
- **Phase 7 — price-based ratios.** `book_value_per_share(snapshot)` is the book half of
  book-to-price; the price half is the allocator's, because this package never sees a bar.
  `gross_profitability`, `return_on_equity`, `return_on_assets` and `accrual_ratio` are here;
  anything needing market cap (earnings yield, B/P) is phase 7's, built from
  `shares_outstanding` and the close.
- **Phase 7 — eligibility on `gross_profit_basis`.** The field is deliberately on `Snapshot` so
  the allocator can choose to rank only on `"reported"` + `"derived"` and exclude `"none"`, or to
  treat a derived figure as second-class. This phase takes no position.
- **Not done, deliberately: differencing year-to-date facts.** Some filers tag only a 6- or
  9-month YTD duration for Q2/Q3, most often in the cash-flow statement. Those facts are dropped
  rather than differenced. Doing it properly means pairing YTD facts within a fiscal year across
  restatements and is a phase of its own; the measurable symptom is a shorter quarterly run, which
  shows up honestly as `Snapshot.sue_quarters`.
- **Not done, deliberately: a TTM basis.** See decision 4. If phase 7 measures that the annual
  basis is too stale, the clean addition is a `ttm()` sibling of `annual()` plus a `flow_basis`
  field on `Snapshot` — additive, no change to anything written here.
- **Not done: ladder coverage beyond the eight sampled filers.** The lower rungs
  (`RevenueFromContractWithCustomerIncludingAssessedTax`, `SalesRevenueNet`,
  `StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest`,
  `NetCashProvidedByUsedInOperatingActivitiesContinuingOperations`,
  `WeightedAverageNumberOfDilutedSharesOutstanding`, `CommonStockSharesOutstanding`) are in the
  ladder on standard-practice grounds and were not exercised by the sample. After phase 4's
  ingest lands, a one-off count of `Snapshot.tag(concept)` over all 795 symbols will say which
  rungs actually fire; that belongs in phase 7's runbook note, not here.

## Rollback

This phase is one commit and touches nothing that existed before it except six lines of
`test_strategy_purity.py`.

```sh
cd /home/miftah/.worktrees/seer/edgar-fundamentals
git revert --no-edit <phase-5-sha>
# or, before it is committed:
rm -rf engine/src/seer_engine/fundamentals engine/tests/test_fundamentals_derive.py
git checkout -- engine/tests/test_strategy_purity.py
```

Nothing imports the package until phase 6, so reverting it in isolation leaves the tree green.
If phase 6 has already landed, revert phase 6 first — it is the only consumer.

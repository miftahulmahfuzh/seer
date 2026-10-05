# Phase 6: `Market.fundamentals` and the `prepare_market` hook

**Plan set:** `EDGAR_FUNDAMENTALS_PLAN.md`
**Analysis:** `20261005-081833-G7K2_code_analyzer.md`
**Satisfies:** R6 — factor exposure to the lab (this phase carries the panel to the allocator; phase 7 is the first consumer)
**Depends on:** Phase 2 (schema), Phase 5 (pure derivation)
**Difficulty:** HARD
**Package:** `seer_engine.backtest`, `seer_engine.strategies`

---

## Reconciled contracts with phases 2 and 5 (READ FIRST)

Neither plan file existed when this one was written, so the original A1–A4 were guesses.
**The reconciler checked all four and corrected two.** Both corrections land exactly where this
plan predicted — `io.FACTS_COPY_SQL`, `io.facts_from_frame`, and the `Panel` import in
`backtest/market.py` — so they are mechanical, not a redesign.

### C1 — `fundamental_facts` is keyed by `cik`; there is **no `symbol` column**

The original A1 assumed `symbol`. **Phase 2 owns the schema and it keys facts on `cik`**, because
one ticker names several companies over time and one company files under several tickers
(invariant 4); a `symbol` column would duplicate every row for a share-class pair. Phase 2's
shipped columns:

| column | type | note |
|---|---|---|
| `cik` | `bigint NOT NULL` | part of the PK |
| `taxonomy` | `text NOT NULL` | `us-gaap` or `dei` |
| `tag` | `text NOT NULL` | e.g. `Revenues` |
| `unit` | `text NOT NULL` | e.g. `USD`, `USD/shares`, `shares` |
| `period_start` | `date **NOT NULL**` | **`= period_end` means instantaneous** — see C2 |
| `period_end` | `date NOT NULL` | |
| `accn` | `text NOT NULL` | part of the PK — the restatement axis |
| `val` | `numeric NOT NULL` | |
| `fy` | `int NULL` | |
| `fp` | `text NULL` | `FY`, `Q1`..`Q4` |
| `form` | `text NOT NULL` | `10-K`, `10-Q`, … |
| `filed` | `date NOT NULL` | **the only no-look-ahead boundary** |

There is **no `frame` column** (phase 2 omitted it) and no `symbol` column.

**This phase owns the CIK→symbol join.** Phase 5's panel is symbol-keyed and phase 7 ranks
symbols, so `FACTS_COPY_SQL` joins `ticker_cik` and projects `m.symbol` as column 0. Step 2
carries the SQL, which is phase 2's contract text verbatim. The join is against `ticker_cik`,
**never against `bars`** — invariant 7.

**The join fans out, and the fingerprint must fan out with it.** The share-class pairs phase 1
documents (`GOOG`/`GOOGL`, `FOX`/`FOXA`, `NWS`/`NWSA`, `UA`/`UAA`, `CMCSA`/`CMCSK`,
`BATRA`/`BATRK`) mean one fact row legitimately becomes two rows of the panel. So
`facts_fingerprint` takes `count(*), max(f.filed)` **over the same join**, not over
`fundamental_facts` alone — otherwise the cache would not invalidate when `ticker_cik` changed,
and `_facts_frame`'s `len(frame) != rows` check would fire on every load. Step 2 carries both
queries.

### C2 — `period_start` is `NOT NULL`; `period_start = period_end` is the instant marker

The original A1 assumed `period_start date NULL`. Phases 2 and 4 converged independently on
`NOT NULL`: a nullable column cannot sit in a PRIMARY KEY and the period **must** be keyed,
because one 10-K reports `Revenues` for both the fiscal year and Q4 under the same
`accn`/`tag`/`unit`/`period_end`. Phase 4 writes `period_start = period_end` where SEC omitted
`start`.

Phase 5's in-memory `Fact.period_start` is still `date | None`, `None` meaning instant — that is
what `Fact.kind()`, `quarters()` and all 39 of its tests read. **The translation happens in this
phase's COPY projection**, which emits `''` when `period_start = period_end`; `facts_from_frame`
then turns `''` into `None` exactly as it already did. No Python in `facts_from_frame` changes.
(Phase 5's `fact_from_row` applies the same rule for callers that hand it raw rows; the two
paths agree by construction.)

### C3 — phase 5's real exports

The original A2 assumed `Fact` and a type literally named `Panel`. Phase 5 ships
`seer_engine.fundamentals` exporting:

```python
Fact                  # frozen, slots; (symbol, taxonomy, tag, unit, period_start, period_end,
                      #                 val, accn, form, fy, fp, filed)
FundamentalPanel      # frozen; .symbols, .names(), .get(s), .as_of(s, t), .snapshots_on(t),
                      #         .from_facts(facts)  [staticmethod]
SymbolFundamentals, Snapshot, Obs
EMPTY_PANEL           # FundamentalPanel; the shared valid empty panel
FACT_COLUMNS          # the twelve-column input contract, in order
```

**This phase keeps the local name `Panel` with one aliasing import** rather than renaming it in
twenty places:

```python
from seer_engine.fundamentals import EMPTY_PANEL, FACT_COLUMNS, Fact, FundamentalPanel as Panel
```

and `EMPTY_FUNDAMENTALS` **is** phase 5's `EMPTY_PANEL`, not a second empty panel built here —
one shared instance, one identity, so `market.fundamentals is EMPTY_PANEL` is a usable test.
`FACTS_COLUMNS` is likewise `FACT_COLUMNS` re-exported, **not** restated: phase 5 owns the
column order, and the original draft of this plan had `accn, fy, fp, form` where phase 5 has
`accn, form, fy, fp`. The COPY projection follows phase 5's order.

### C4 — phase 5's package is import-pure

Unchanged and confirmed. `seer_engine/fundamentals/` imports no `psycopg`, `requests` or
`yfinance`, because `backtest/market.py` imports it and
`test_strategy_purity.py::test_pure_modules_load_no_db_or_network_module` imports
`seer_engine.backtest.market` in a fresh interpreter and asserts none of those landed in
`sys.modules`. Phase 5's Step 5 extends the purity glob to cover the package, which makes this
permanent. **This phase must leave `test_strategy_purity.py` byte-identical to what phase 5
leaves** (invariant 5, as reworded).

### C5 — correction to the index's call-site list, confirmed

The index and the analysis name three `prepare(market.history)` call sites:
`backtest/dev.py:455`, `backtest/walkforward.py:200`, `backtest/runner.py:143`. **Only the first
is a call.** `walkforward.py:200` and `runner.py:143` are *docstring lines* describing the
`prepared` argument their callers pass in; neither module calls `prepare`. The real other
callers are `commands/backtest.py:193`, `commands/backtest_wf.py:212` and
`commands/backtest_b.py:282`, and all three are hard-wired to `STRATEGY_A` / `STRATEGY_A2`,
bracket `Strategy` objects that will never be `MarketAware`. This phase changes the one real
dispatch site (`dev.py:455`) and corrects the two docstrings; the three `commands/*` sites are
listed under **Handoffs** with the reason they are deliberately untouched.

### C6 — scope widened by the reconciler: every `Market(...)` site, and the research store

The original plan left the research store and the two `paper/` rebuilds as handoffs H1 and H2,
noting that H1 "blocks phase 7 and no phase in the set owns it". **The index assigns both to
this phase**, and phase 7 does not touch them. The reasoning is on the index's Decisions table:
this phase already owns `dev.py:367`, the identical "a `Market` is rebuilt and silently drops
the new field" fix, and already ships `with_fundamentals` precisely so the research-store
construction site is a one-line change. Leaving it out would ship a phase 7 that ranks nothing
in the lab, silently.

So this phase owns, in addition to the original scope:

- `seer_engine/research.py` — an **optional** fifth store file (`OPTIONAL_DATA_FILES`, not a
  widened `DATA_FILES`), the relaxed manifest `files` check, `build_store(facts=…)`,
  `_read_fundamentals`, and the `Market` construction at `research.py:472`;
- `seer_engine/commands/research_store.py` — a `--with-fundamentals` flag that reads the panel
  from the database and hands the facts to `build_store`;
- `paper/replay.py:281` and `commands/paper.py:254` — the two remaining `Market` rebuilds.

See Steps 7 and 8.

## Goal

`Market` carries a point-in-time fundamentals panel alongside bars, membership and FX, loaded by
`backtest/io.py` with the same table-fingerprint pickle cache that `bars` uses, and degrading to
an empty panel against a database that has no fundamentals rows or no fundamentals table at all.
An allocator that wants the panel declares `prepare_market(market)` and the dev/lab runner hands
it the whole `Market`; every one of the eleven existing implementers keeps working through
`prepare(history)` with no edit and no behaviour change.

## Interface Contract

**Deletes:** none
**Renames:** none

**Creates:**
- `seer_engine.backtest.market.EMPTY_FUNDAMENTALS` — `Panel`, the shared empty panel (`market.py`, module level)
- `seer_engine.backtest.market.Market.fundamentals` — field, `Panel`, **default `EMPTY_FUNDAMENTALS`**, declared after `fx` and before the two `init=False` fields (`market.py`)
- `seer_engine.backtest.market.Market.with_fundamentals(fundamentals: Panel) -> Market` (`market.py`)
- `seer_engine.strategies.allocator.MarketAware` — `@runtime_checkable Protocol` with the single member `prepare_market(self, market: Market) -> Any` (`allocator.py`)
- `seer_engine.strategies.allocator.prepare_for(obj: Any, market: Market) -> Any` — the dispatch helper (`allocator.py`)
- `seer_engine.backtest.io.FACTS_COLUMNS`, `.FACTS_COPY_SQL`, `.FACTS_CACHE_GLOB` (`io.py`)
- `seer_engine.backtest.io.facts_fingerprint(conn) -> tuple[int, date | None]` (`io.py`)
- `seer_engine.backtest.io.facts_cache_path(cache_dir, rows, max_filed) -> Path` (`io.py`)
- `seer_engine.backtest.io.read_facts_frame(conn) -> pd.DataFrame` (`io.py`)
- `seer_engine.backtest.io.facts_from_frame(frame) -> tuple[Fact, ...]` (`io.py`)
- `seer_engine.backtest.io.load_panel(conn, *, cache_dir=CACHE_DIR, refresh=False) -> Panel` (`io.py`)
- `engine/tests/test_market_fundamentals.py`

**Signature changes:**
- `Market.__init__` gains one trailing keyword with a default. `Market(history=…, membership=…, fx=…)` and `Market(history, membership, fx)` are both unchanged. **No existing construction site is edited.**
- `load_market(conn, *, cache_dir, refresh) -> tuple[Market, int]` — signature and return shape unchanged; the returned `Market` now carries `fundamentals`.
- `Allocator`'s member set is **NOT** changed. See Step 3 for why that is load-bearing.

**Requires (from earlier phases):**
- Phase 2: tables `fundamental_facts` (columns per C1) **and `ticker_cik`** (the join that supplies `symbol`), both reachable on the `search_path`, and both optional at run time — a database with no migration 005 must still load a market.
- Phase 5: `seer_engine.fundamentals` exports `Fact`, `FundamentalPanel`, `EMPTY_PANEL` and `FACT_COLUMNS`; `FundamentalPanel.from_facts(())` is valid; the package imports no `psycopg`/`requests`/`yfinance` (C3, C4).

**Also creates (reconciled scope, C6):**
- `seer_engine.research.FUNDAMENTALS_FILE`, `FUNDAMENTALS_HEADER`, a new `OPTIONAL_DATA_FILES`, `build_store`'s keyword-only `facts: Sequence[Fact] | None = None`, `_read_fundamentals`, and the `fundamentals.csv` artifact itself -- carried in the manifest's `files` map as an **optional** entry. **`DATA_FILES` is NOT widened**: that is what keeps every store built before this phase loading, with a bit-identical fingerprint, and keeps `engine/tests/test_research_store.py` byte-identical and green. See Step 7.
- the `fundamentals=` argument at the research store's `Market(...)` construction (`research.py:472`)
- `replace(...)`-based panel preservation at `paper/replay.py:281` and `commands/paper.py:254`

**Leaves alone (owned by others):**
- `strategies/f_fundamental.py`, `lab/methods/m0005_*.py` (Phase 7) — this phase adds **no** allocator and **no** lab method.
- `strategies/a.py`, `a2.py`, `b.py`, `c.py`, `f_factor.py`, `f_index.py`, `f_rotation.py`, `f_swing.py`, and `PicksAllocator`/`BlendAllocator`/`VolTargetAllocator` — not touched, not even their docstrings.
- `seer_engine/fundamentals/` (Phase 5), `db/migrations/` (Phase 2), `commands/fundamentals.py` (Phase 4).
- `engine/tests/test_strategy_purity.py` — **byte-identical to what phase 5 leaves** (invariant 5). This phase neither extends the glob nor relaxes it.
- `engine/tests/test_lab_methods.py` — read for evidence only; **phase 7 owns the one edit to it**.
- `docs/runbooks/data-pipeline.md` (Phase 7).

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/backtest/market.py` | modify | import `EMPTY_PANEL` and `FundamentalPanel as Panel` from phase 5, plus `replace`; add `EMPTY_FUNDAMENTALS` (after `SPY`, line 27); add the `fundamentals` field and its type check to `Market` (lines 93–138); add `with_fundamentals` |
| `engine/src/seer_engine/backtest/io.py` | modify | import `FACT_COLUMNS`/`Fact`/`FundamentalPanel as Panel` and `EMPTY_FUNDAMENTALS`; add the facts constants incl. the `ticker_cik` join (after `CACHE_GLOB`, line 61), `facts_fingerprint`, `facts_cache_path`, `read_facts_frame`, `_facts_frame` + its cache read/write, `facts_from_frame`, `load_panel`; call `load_panel` inside `load_market`'s transaction (line 95) and pass the panel to `Market(...)` (line 99) |
| `engine/src/seer_engine/strategies/allocator.py` | modify | `TYPE_CHECKING` import of `Market` (line 31); document the hook in the `Allocator` docstring (line 50) and the module docstring (line 18); add `MarketAware` and `prepare_for` after the `Allocator` protocol (line 80) |
| `engine/src/seer_engine/backtest/dev.py` | modify | import `prepare_for` (line 50); preserve the panel through the FX rebuild (line 367); dispatch through `prepare_for` (line 455) |
| `engine/src/seer_engine/backtest/runner.py` | modify | docstring only (line 143) |
| `engine/src/seer_engine/backtest/walkforward.py` | modify | docstring only (line 200) |
| `engine/src/seer_engine/research.py` | modify | `FUNDAMENTALS_FILE`, `FUNDAMENTALS_HEADER`, a **new** `OPTIONAL_DATA_FILES` (`DATA_FILES` is **not** touched), the relaxed `files` check in `_read_manifest`, `load_store` hashing the manifest's own keys, `_seal(extra_files=…)`, `build_store(facts=…)`, `_read_fundamentals`, and `fundamentals=` at the `Market(...)` construction (line 472) |
| `engine/src/seer_engine/commands/research_store.py` | modify | `--with-fundamentals`: read the panel from the database and pass the facts to `build_store` |
| `engine/src/seer_engine/paper/replay.py` | modify | line 281 — `replace(market, …)` so the rebuild keeps the panel |
| `engine/src/seer_engine/commands/paper.py` | modify | line 254 — same one-line fix |
| `engine/tests/test_market_fundamentals.py` | create | the whole phase's test module |

**Eleven files.** The index's draft said 6; it counted neither the research store (C6) nor the
two `paper/` rebuilds. The index's Files column now says 11.

## Implementation Steps

### Step 1: `Market` gains `fundamentals`

**File:** `engine/src/seer_engine/backtest/market.py:16-27` (imports and module constants), `:93-138` (the `Market` dataclass)

**Change:** add the field with a default so every existing construction site keeps compiling
untouched, validate it like every other field, and add the one helper that lets a Market built
without a panel acquire one.

`dataclasses` rules that make this safe, both verified against CPython 3.12 before writing this
plan: (a) a defaulted field may precede `_fx_dates`/`_last` because `__init__`'s
"non-default follows default" check skips `init=False` fields; (b) `dataclasses.replace` skips
`init=False` fields rather than rejecting them, so `__post_init__` re-derives `_fx_dates` and
`_last` correctly.

**Code — replace lines 16–27 (the import block and `SPY`):**

```python
from __future__ import annotations

from bisect import bisect_right
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from decimal import Decimal

from seer_engine.fundamentals import EMPTY_PANEL, FundamentalPanel as Panel
from seer_engine.prices import Bar, to_decimal
from seer_engine.strategies.base import History

SPY = "SPY"

EMPTY_FUNDAMENTALS: Panel = EMPTY_PANEL
"""The panel a ``Market`` carries when no fundamentals were loaded.

This IS ``seer_engine.fundamentals.EMPTY_PANEL``, not a second empty panel built here: one
shared instance means ``market.fundamentals is EMPTY_PANEL`` is a usable identity test and
there is exactly one object the whole tree means by "no fundamentals". It is immutable, so it
is a safe dataclass default. ``load_market`` returns it for a database with no
``fundamental_facts`` rows -- and for one where the table does not exist yet, which is every
database that has not run phase 2's migration.

``FundamentalPanel`` is aliased to ``Panel`` here and in ``io.py`` because that is the name
this phase's code, tests and docstrings use throughout; phase 5 owns the type.
"""
```

**Code — replace lines 93–138 (the `Market` header, docstring, fields and `__post_init__`) with
this, and keep every method from `bar` onward exactly as it is:**

```python
@dataclass(frozen=True, eq=False)
class Market:
    """Everything a backtest reads, in memory.

    ``history``: every symbol with bars (SPY included), keyed by symbol, each ``History``
    ascending. ``fx``: ``(date, usd_idr)`` rows, strictly ascending, ``usd_idr`` a Decimal > 0
    (publishing days only, so not every session has a row). ``fundamentals``: the point-in-time
    SEC fact panel built by ``seer_engine.fundamentals``, ``EMPTY_FUNDAMENTALS`` when none was
    loaded.

    ``fundamentals`` is deliberately independent of ``history``. A symbol may have facts and no
    bars (the 133 delisted ever-members, whose prices are blocked on Gap A) or bars and no facts
    (every ETF). Nothing here cross-checks the two and nothing may start to.
    """

    history: Mapping[str, History]
    membership: Membership
    fx: tuple[tuple[date, Decimal], ...]
    fundamentals: Panel = EMPTY_FUNDAMENTALS
    _fx_dates: tuple[date, ...] = field(init=False, repr=False)
    _last: Mapping[str, date] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.history, Mapping):
            raise TypeError(f"history must be a Mapping, got {type(self.history).__name__}")
        if not isinstance(self.membership, Membership):
            raise TypeError(f"membership must be a Membership, got {type(self.membership).__name__}")
        if not isinstance(self.fx, tuple):
            raise TypeError("fx must be a tuple of (date, Decimal) rows")
        if not isinstance(self.fundamentals, Panel):
            raise TypeError(f"fundamentals must be a Panel, got {type(self.fundamentals).__name__}")
        last: dict[str, date] = {}
        for symbol, h in self.history.items():
            if not isinstance(h, History):
                raise TypeError(f"history[{symbol!r}] must be a History, got {type(h).__name__}")
            if h.symbol != symbol:
                raise ValueError(f"history[{symbol!r}] holds bars for {h.symbol!r}")
            d = h.last_date()
            if d is not None:
                last[symbol] = d
        prev: date | None = None
        for row in self.fx:
            if not (isinstance(row, tuple) and len(row) == 2):
                raise TypeError(f"an fx row is (date, Decimal), got {row!r}")
            d, rate = row
            _check_date("fx date", d)
            if not isinstance(rate, Decimal):
                raise TypeError(f"usd_idr on {d} must be a Decimal, got {type(rate).__name__}")
            if not rate.is_finite() or rate <= 0:
                raise ValueError(f"usd_idr on {d} must be > 0, got {rate}")
            if prev is not None and d <= prev:
                raise ValueError(f"fx rows must be strictly ascending: {d} after {prev}")
            prev = d
        object.__setattr__(self, "_fx_dates", tuple(d for d, _ in self.fx))
        object.__setattr__(self, "_last", last)

    def with_fundamentals(self, fundamentals: Panel) -> Market:
        """This market with ``fundamentals`` attached; every other field is carried over.

        ``Market`` is frozen, so this returns a new value and leaves ``self`` untouched. It is
        the supported way to put a panel on a market that was built without one -- the research
        store, a paper replay, a test fixture -- without any of those having to know the field
        order.
        """
        return replace(self, fundamentals=fundamentals)
```

**Impact:** every existing `Market(...)` construction (`io.py:99`, `dev.py:367`,
`research.py:472`, `paper/replay.py:281`, `paper/store.py:1035`, `commands/paper.py:254`, and the
32 in `engine/tests/`) continues to compile and to produce a market whose `fundamentals` is
`EMPTY_FUNDAMENTALS`. `Market` stays `frozen=True, eq=False`; purity is unaffected as long as C4
holds.

### Step 2: `load_market` loads the panel, cached by table fingerprint

**File:** `engine/src/seer_engine/backtest/io.py:30-61` (imports and constants), `:86-108`
(`load_market`), and three new sections.

**Change:** mirror the bars path exactly — a cheap `count(*), max(filed)` fingerprint, a streamed
`COPY ... TO STDOUT` into a pandas frame, a pickle named for the fingerprint, stale pickles swept
— with two additions the bars path does not need: a `to_regclass` guard so a database without
phase 2's migration loads cleanly instead of aborting the read-only transaction, and `to_char`/
`coalesce` in the SQL so the COPY stream never carries a `\N`, which `na_filter=False` would turn
into the literal string `"\\N"`.

The **frame** is cached, not the `Panel` — the same choice the bars path makes (`bars` are cached
raw and `histories_from_frame` runs on every load). A change to phase 5's concept ladder then
needs no cache bust, and the cache key stays a pure function of the table.

**Code — replace lines 30–43 (the import block after `from pathlib import Path`):**

```python
from seer_engine import config
from seer_engine.backtest import b_report, dev_report, wf_report
from seer_engine.backtest.benchmark import Dividend, parse_dividends
from seer_engine.backtest.market import EMPTY_FUNDAMENTALS, Market, Membership
from seer_engine.backtest.report import (
    BacktestReport,
    equity_csv,
    equity_svg,
    render_markdown,
    report_stem,
)
from seer_engine.fundamentals import FACT_COLUMNS, Fact, FundamentalPanel as Panel
from seer_engine.prices import to_decimal
from seer_engine.strategies import b_model
from seer_engine.strategies.base import History
```

**Code — insert after line 61 (`CACHE_GLOB = "bars-*.pkl"`), before `Interval = ...`:**

```python
FACTS_TABLE = "fundamental_facts"
MAP_TABLE = "ticker_cik"

# Phase 5 owns the column order; this is its tuple, not a copy of it. If the two ever drifted,
# facts_from_frame's positional unpack would silently mis-assign form/fy/fp.
FACTS_COLUMNS = FACT_COLUMNS

# fundamental_facts is keyed by CIK and has NO symbol column (C1): one ticker names several
# companies over time, so a symbol column would let a recycled ticker smear two filers
# together. ticker_cik carries the dated bridge and this join is where a fact acquires the
# symbol phase 5's panel is keyed by. It is a JOIN AGAINST ticker_cik, NEVER against bars:
# invariant 7 forbids making a bar row a precondition for a fact, and the 133 delisted
# ever-members have facts and no bars.
#
# The join legitimately fans out: a share-class pair (GOOG/GOOGL, FOX/FOXA, NWS/NWSA, UA/UAA,
# CMCSA/CMCSK, BATRA/BATRK) is one CIK and two symbols, so one fact row becomes two panel rows.
# That is why facts_fingerprint counts over the same join.
#
# period_start = period_end IS the stored encoding of "instantaneous" (C2); it goes out as ''
# so facts_from_frame turns it back into None, which is what phase 5's Fact means by an
# instant. Other dates go out as to_char text and nullable columns as coalesce'd text, so the
# COPY stream never carries a \N for na_filter=False to mistake for the two-character string
# "\N". The ORDER BY is a total order over the fact identity, so the frame -- and therefore
# the pickle -- is byte-stable.
_FACTS_FROM = (
    "FROM fundamental_facts f "
    "JOIN ticker_cik m ON m.cik = f.cik "
    "  AND f.filed >= m.start_date "
    "  AND (m.end_date IS NULL OR f.filed < m.end_date) "
)
FACTS_COPY_SQL = (
    "COPY (SELECT m.symbol, f.taxonomy, f.tag, f.unit, "
    "CASE WHEN f.period_start = f.period_end THEN '' "
    "     ELSE to_char(f.period_start, 'YYYY-MM-DD') END AS period_start, "
    "to_char(f.period_end, 'YYYY-MM-DD') AS period_end, "
    "f.val, f.accn, f.form, "
    "coalesce(f.fy::text, '') AS fy, "
    "coalesce(f.fp, '') AS fp, "
    "to_char(f.filed, 'YYYY-MM-DD') AS filed "
    + _FACTS_FROM +
    "ORDER BY m.symbol, f.taxonomy, f.tag, f.unit, f.period_end, f.period_start, f.filed, f.accn"
    ") TO STDOUT"
)
FACTS_COUNT_SQL = "SELECT count(*), max(f.filed) " + _FACTS_FROM
FACTS_CACHE_GLOB = "fundamentals-*.pkl"
```

The projection order is **phase 5's** `FACT_COLUMNS`: `symbol, taxonomy, tag, unit,
period_start, period_end, val, accn, form, fy, fp, filed`. Note `accn, form, fy, fp` — the
original draft of this plan had `accn, fy, fp, form`, which would have mis-assigned three
columns.

**Code — replace lines 86–108, the body of `load_market` (its signature and docstring stay, with
the docstring's second paragraph extended):**

```python
    """(Market, number of bar rows) from ``bars``, ``universe`` and ``fx_rates``.

    ``conn`` must have autocommit off and no transaction in progress. Bars come from the
    cache in ``cache_dir`` when its name matches the table's ``count(*)`` and ``max(date)``
    (``refresh`` forces a re-download); universe and fx are always read fresh (small).
    Raises LoadError when ``bars`` is empty.

    ``fundamental_facts`` is read the same way, into ``market.fundamentals``, and is optional:
    a missing table or an empty one gives ``EMPTY_FUNDAMENTALS`` and no error, so a database
    that has not run ``005_fundamentals.sql`` still backs a backtest unchanged.
    """
    if conn.info.transaction_status != TransactionStatus.IDLE:
        raise ValueError("load_market needs a connection with no transaction in progress")
    try:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        rows, max_date = bars_fingerprint(conn)
        if rows == 0 or max_date is None:
            raise LoadError("the bars table is empty; run `backfill` first")
        frame = _bars_frame(conn, Path(cache_dir), rows, max_date, refresh)
        intervals = read_intervals(conn)
        fx_rows = read_fx(conn)
        panel = load_panel(conn, cache_dir=Path(cache_dir), refresh=refresh)
    finally:
        conn.rollback()
    history = histories_from_frame(frame)
    market = Market(
        history=history,
        membership=Membership(intervals=intervals),
        fx=fx_rows,
        fundamentals=panel,
    )
    log.info(
        "market: %d bar rows through %s, %d symbols with bars, %d membership intervals, %d fx rows",
        rows,
        max_date,
        len(history),
        len(intervals),
        len(fx_rows),
    )
    return market, rows
```

The existing `log.info` format string is left byte-identical on purpose; `load_panel` logs the
panel on its own line, so no log consumer sees a changed line.

**Code — insert after `read_fx` (currently ends at line 189), before the `# ---- cache` banner:**

```python
# ---- fundamentals -------------------------------------------------------------------------


def load_panel(
    conn: psycopg.Connection,
    *,
    cache_dir: Path = CACHE_DIR,
    refresh: bool = False,
) -> Panel:
    """The point-in-time fact panel from ``fundamental_facts``.

    Runs inside the caller's transaction and never commits or rolls back (``load_market`` owns
    the ``REPEATABLE READ, READ ONLY`` transaction and its rollback). Returns
    ``EMPTY_FUNDAMENTALS`` when either ``fundamental_facts`` or ``ticker_cik`` is missing, or
    when the join yields no rows -- the state of every database that has not applied
    ``db/migrations/005_fundamentals.sql``, and of one that has applied it but not yet run
    ``fundamentals``. Otherwise the facts come from the pickle in ``cache_dir`` named for
    ``(count(*), max(filed))`` over the join, or from one streamed COPY when that pickle is
    absent or ``refresh`` is set.
    """
    rows, max_filed = facts_fingerprint(conn)
    if rows == 0 or max_filed is None:
        log.info("fundamentals: no rows; the market gets an empty panel")
        return EMPTY_FUNDAMENTALS
    frame = _facts_frame(conn, Path(cache_dir), rows, max_filed, refresh)
    panel = Panel.from_facts(facts_from_frame(frame))  # FundamentalPanel.from_facts
    log.info("fundamentals: %d facts filed through %s", rows, max_filed)
    return panel


def facts_fingerprint(conn: psycopg.Connection) -> tuple[int, date | None]:
    """(count(*), max(filed)) over the ``fundamental_facts`` x ``ticker_cik`` join: the cache key.

    Counted over the **join**, not over ``fundamental_facts`` alone, for two reasons: the join
    fans a share-class CIK out to two symbols so the joined count is the real panel row count
    that ``_facts_frame`` checks against, and re-vendoring ``ticker_cik`` must invalidate the
    pickle even when no fact changed.

    (0, None) when **either** table is missing. The existence test is ``to_regclass``, which
    returns NULL instead of raising, because an ``UndefinedTable`` error would abort
    ``load_market``'s read-only transaction and there is no savepoint to recover it from.
    """
    for table in (FACTS_TABLE, MAP_TABLE):
        if conn.execute("SELECT to_regclass(%s)", (table,)).fetchone()[0] is None:
            return 0, None
    row = conn.execute(FACTS_COUNT_SQL).fetchone()
    return int(row[0]), row[1]


def facts_cache_path(cache_dir: Path, rows: int, max_filed: date) -> Path:
    return Path(cache_dir) / f"fundamentals-{max_filed.isoformat()}-{rows}.pkl"


def read_facts_frame(conn: psycopg.Connection) -> pd.DataFrame:
    """Every ``fundamental_facts`` row, in ``FACTS_COPY_SQL`` order, via one streamed COPY.

    Columns: ``FACTS_COLUMNS`` (phase 5's ``FACT_COLUMNS``). Every column is str except ``val``
    (float64, correctly rounded from the numeric text); ``fy`` and ``fp`` are "" where the
    column is NULL, and ``period_start`` is "" where it equals ``period_end`` -- the stored
    encoding of an instantaneous fact (C2). None of the text columns can hold a tab or a
    newline -- they are SEC tags, units, accession numbers, form types and tickers -- so the
    TSV needs no escaping pass.
    """
    buf = BytesIO()
    with conn.cursor() as cur:
        with cur.copy(FACTS_COPY_SQL) as copy:
            for chunk in copy:
                buf.write(chunk)
    if buf.tell() == 0:
        raise LoadError("COPY of fundamental_facts returned no rows")
    buf.seek(0)
    return pd.read_csv(
        buf,
        sep="\t",
        header=None,
        names=list(FACTS_COLUMNS),
        dtype={
            "symbol": str,
            "taxonomy": str,
            "tag": str,
            "unit": str,
            "period_start": str,
            "period_end": str,
            "val": np.float64,
            "accn": str,
            "form": str,
            "fy": str,
            "fp": str,
            "filed": str,
        },
        na_filter=False,
        float_precision="round_trip",
        engine="c",
    )


def facts_from_frame(frame: pd.DataFrame) -> tuple[Fact, ...]:
    """One ``fundamentals.Fact`` per frame row, in frame order.

    The frame's dates are ISO strings and its NULLs are empty strings (see ``FACTS_COPY_SQL``);
    this is the one place that turns them back into ``date`` and ``None``. ``filed`` is never
    optional: it is the no-look-ahead boundary, so a row without it is a loader bug, not a
    tolerable gap.
    """
    if len(frame) == 0:
        return ()
    out: list[Fact] = []
    for row in frame.itertuples(index=False, name=None):
        # FACT_COLUMNS order: ..., val, accn, FORM, FY, FP, filed. Phase 5 owns it.
        symbol, taxonomy, tag, unit, period_start, period_end, val, accn, form, fy, fp, filed = row
        if not filed:
            raise LoadError(f"{symbol} {tag} {accn}: a fact row has no filed date")
        out.append(
            Fact(
                symbol=str(symbol),
                taxonomy=str(taxonomy),
                tag=str(tag),
                unit=str(unit),
                period_start=date.fromisoformat(period_start) if period_start else None,
                period_end=date.fromisoformat(period_end),
                val=float(val),
                accn=str(accn),
                fy=int(fy) if fy else None,
                fp=str(fp) or None,
                form=str(form),
                filed=date.fromisoformat(filed),
            )
        )
    return tuple(out)


def _facts_frame(
    conn: psycopg.Connection, cache_dir: Path, rows: int, max_filed: date, refresh: bool
) -> pd.DataFrame:
    path = facts_cache_path(cache_dir, rows, max_filed)
    if not refresh and path.is_file():
        cached = _read_facts_cache(path, rows)
        if cached is not None:
            log.info("fundamentals cache hit: %s", path)
            return cached
    log.info(
        "fundamentals cache %s: streaming %d rows from the database",
        "refresh" if refresh else "miss",
        rows,
    )
    frame = read_facts_frame(conn)
    if len(frame) != rows:
        raise LoadError(f"COPY returned {len(frame)} fact rows but count(*) said {rows}")
    _write_facts_cache(path, frame)
    return frame


def _read_facts_cache(path: Path, rows: int) -> pd.DataFrame | None:
    try:
        frame = pd.read_pickle(path, compression=None)
    except Exception as e:  # noqa: BLE001 - a broken cache is re-downloaded, never fatal
        log.warning(
            "fundamentals cache %s unreadable (%s: %s); re-downloading", path, type(e).__name__, e
        )
        return None
    if (
        not isinstance(frame, pd.DataFrame)
        or len(frame) != rows
        or tuple(frame.columns) != FACTS_COLUMNS
    ):
        log.warning("fundamentals cache %s has the wrong shape; re-downloading", path)
        return None
    return frame


def _write_facts_cache(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    frame.to_pickle(tmp, compression=None)
    os.replace(tmp, path)
    log.info("fundamentals cache written: %s", path)
    for old in sorted(path.parent.glob(FACTS_CACHE_GLOB)):
        if old != path:
            old.unlink(missing_ok=True)
            log.info("removed stale fundamentals cache %s", old.name)
```

The bars cache helpers `_read_cache`/`_write_cache` are **not** generalised: they are shipped code
on the hot path of every backtest, and duplicating fifteen lines is cheaper than risking the
bars pickle. The de-duplication is noted under Handoffs.

**Impact:** `load_market` runs two extra `to_regclass` round trips and, against today's live
database, nothing else: both tables are absent, so there is no count query, no COPY, no pickle
and no new file in `engine/.cache`. The returned `Market` is identical except for a field that defaults to the same
object it would have had anyway. `facts_from_frame` iterates rows in Python
(`itertuples(index=False, name=None)` is the fastest pandas row iteration, roughly 1 µs/row), so
a few million facts cost a few seconds per process; if that becomes the dominant load cost the
answer is to cache the `Panel` instead of the frame, which is a one-function change.

**One behaviour the join makes explicit:** a fact whose `filed` date falls in no `ticker_cik`
interval for its CIK is dropped. That is correct — no symbol can name it, so no allocator could
ask for it — and it is the mechanism that keeps a recycled ticker's two filers apart. It also
means an incomplete `ticker_cik` silently shrinks the panel rather than corrupting it, which is
the failure mode to prefer.

### Step 3: the optional `prepare_market` hook

**File:** `engine/src/seer_engine/strategies/allocator.py:18` (module docstring), `:31` (imports),
`:50` (the `Allocator` docstring), insert after `:80`.

**Why `prepare_market` is a sibling protocol and not a member of `Allocator`.** `Allocator` is
`@runtime_checkable`, and the codebase leans on that at eight production sites —
`dev.py:154`, `dev.py:156`, `dev_report.py:263`, `book_runner.py:252`, `book_runner.py:385`,
`paper/book.py:160`, `allocator.py:373`, `allocator.py:529` — plus
`tests/test_allocator.py:249-251` and `tests/test_lab_methods.py:42,83-84`. `runtime_checkable`
isinstance checks **attribute presence on the instance, and nothing else**. Measured on CPython
3.12 before writing this plan:

- adding a member to a runtime_checkable Protocol makes `isinstance` **False** for every
  structural implementer that lacks it — all eleven of ours;
- giving that member a **default body in the Protocol** does not help: `isinstance` is still
  False, because a structural implementer never inherits the Protocol's body;
- conversely a wrong-arity method, a plain data attribute (`prepare_market = 5`) and an instance
  attribute set in `__init__` all pass. `runtime_checkable` gives presence, never a signature.

So adding `prepare_market` to `Allocator` would make `dev.py:156` reject every existing candidate
and `book_runner.py:252` reject every existing run — the opposite of "optional". The member set of
`Allocator` is therefore frozen, the hook lives in its own single-member protocol, and because
that protocol gives presence only, `prepare_for` guards callability itself rather than trusting
the isinstance result.

**Code — replace line 31:**

```python
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable
```

**Code — insert after line 42 (`TRADING_DAYS = 252  # ...`), as a new paragraph:**

```python
if TYPE_CHECKING:  # typing only: no runtime import, so no strategies -> backtest import cycle
    from seer_engine.backtest.market import Market
```

**Code — append to the module docstring, after the `prepare(history)` paragraph that currently
ends at line 20:**

```
An allocator that needs more than bars -- the point-in-time fundamentals panel, say -- declares
``prepare_market(market)`` instead and gets the whole ``Market``. ``prepare`` is unchanged and
stays the interface every existing allocator implements; the two are dispatched by
``prepare_for(obj, market)``, which the dev/lab runner calls.
```

**Code — replace the `Allocator` protocol's docstring (line 50) with:**

```python
    """Maps history at data_date's close (plus what is held) to target weights for the next session.

    ``prepare_market`` is NOT a member of this protocol, deliberately: this protocol is
    ``runtime_checkable`` and eight production sites test ``isinstance(x, Allocator)``, so adding
    a member -- even one with a default body -- would make every existing allocator fail the
    check. An allocator that wants the whole ``Market`` implements ``MarketAware`` alongside this
    protocol instead, and ``prepare_for`` picks the right one.
    """
```

**Code — insert after line 80 (the end of the `Allocator` protocol), before the
`# --- shared helpers` banner:**

```python
@runtime_checkable
class MarketAware(Protocol):
    """An allocator that prepares from the whole ``Market``, not only its bars.

    Optional and additive: an allocator implements this *in addition to* ``Allocator``, and
    ``prepare_for`` routes to ``prepare_market`` when it is present and to ``prepare`` when it is
    not. An implementer still needs ``prepare`` -- it is an ``Allocator`` member, and
    ``allocatorkit``'s P4 identity check drives the plain path.

    ``runtime_checkable`` tests attribute presence only. ``isinstance(x, MarketAware)`` is
    therefore exactly "``x`` has an attribute called ``prepare_market``": it does not check the
    arity, the annotations, the return type, or even that the attribute is callable. That is
    enough for dispatch and no more, which is why ``prepare_for`` checks callability itself.
    """

    def prepare_market(self, market: Market) -> Any: ...


def prepare_for(obj: Any, market: Market) -> Any:
    """``obj``'s prepared value for ``market``: the ``MarketAware`` path when it has one.

    ``obj.prepare_market(market)`` when ``obj`` defines ``prepare_market``, otherwise
    ``obj.prepare(market.history)`` -- which is what every call site did before the hook existed,
    so an allocator that does not define it sees no change at all. ``obj`` may be an
    ``Allocator`` or a bracket ``Strategy``; both have ``prepare``.

    Raises TypeError when ``prepare_market`` is present but not callable, because
    ``runtime_checkable`` cannot tell a method from a data attribute and a silent fallback there
    would hide a typo as a quietly bar-only allocator.
    """
    if not isinstance(obj, MarketAware):
        return obj.prepare(market.history)
    fn = obj.prepare_market
    if not callable(fn):
        raise TypeError(
            f"{type(obj).__name__}.prepare_market must be callable, got {type(fn).__name__}"
        )
    return fn(market)
```

**Impact:** `Allocator`'s member set is unchanged, so every `isinstance(x, Allocator)` in the tree
keeps its current answer. `strategies/allocator.py` gains no runtime import of `backtest`
(`TYPE_CHECKING` is False at run time and `from __future__ import annotations` keeps the
annotation a string), so there is no cycle and the purity test's AST scan sees only a
`from seer_engine.backtest.market import ...`, whose root `seer_engine` is not forbidden.

### Step 4: the dev/lab runner dispatches, and keeps the panel across the FX rebuild

**File:** `engine/src/seer_engine/backtest/dev.py:50`, `:367`, `:422-425`, `:455`

**Change:** `dev.run_registry` is the one place in the tree that computes a prepared value for an
`Allocator`; both `backtest_dev` (`commands/backtest_dev.py:345`) and the lab
(`lab/runner.py:165`) run through it, so this single line is what makes phase 7's allocator work.
Line 367 is a second, quieter requirement: `_run` rebuilds the `Market` when a candidate's window
opens before `FX_START`, and a positional/keyword rebuild would silently drop the panel for
exactly the long-window candidates. `dataclasses.replace` carries every field it is not asked to
change, so it cannot drop a field added later either.

**Code — replace line 50:**

```python
from seer_engine.strategies.allocator import Allocator, prepare_for
```

**Code — `dataclasses` is already imported at line 36 as `from dataclasses import dataclass`;
replace that line with:**

```python
from dataclasses import dataclass, replace
```

**Code — replace lines 365–367 (the FX rebuild inside `_run`):**

```python
    run_market = market
    if start < FX_START:
        # No USD/IDR before FX_START: the starting cash converts at the FX_START rate. replace()
        # carries history, membership and fundamentals over, so a long window keeps the panel.
        run_market = replace(market, fx=((start, rate),))
```

**Code — replace lines 422–425 (the `run_registry` docstring paragraph):**

```python
    ``prepare_for(allocator, market)`` runs once per allocator id within this call (a strategy's
    id for ``DESIGN_V0`` candidates) and is dropped after the last candidate that uses it: that
    is ``allocator.prepare_market(market)`` for a ``MarketAware`` allocator and
    ``allocator.prepare(market.history)`` for every other. Two different objects sharing an id
    are refused. ``on_result(index, result, row)``, when given, is called after each candidate.
```

**Code — replace line 455:**

```python
            cache[key] = prepare_for(c.allocator, market)
```

**Impact:** for all 54 registry candidates and both existing lab methods, `prepare_for` takes the
`isinstance(obj, MarketAware)`-False branch and evaluates to the identical
`c.allocator.prepare(market.history)` call, with the same prepared object cached under the same
key and freed at the same index. The FX-rebuild change is behaviour-neutral today (both sides of
it carry `EMPTY_FUNDAMENTALS`) and is what stops it from becoming a silent data loss once a panel
is loaded.

### Step 5: the two docstrings the index counted as call sites

**File:** `engine/src/seer_engine/backtest/runner.py:142-145`, `engine/src/seer_engine/backtest/walkforward.py:200`

**Change:** documentation only. Neither module calls `prepare`; both document the `prepared`
argument their callers compute. Point them at the helper so the next reader does not have to
rediscover the dispatch. No executable line changes in either file.

**Code — `runner.py`, replace lines 142–145:**

```python
    ``initial_cash_usd(initial_idr, market.usd_idr_on(start))``. With ``prepared`` (the value of
    ``allocator.prepare_for(strategy, market)`` -- ``strategy.prepare(market.history)`` unless
    the strategy is ``MarketAware``), picks come from ``strategy.picks_prepared``;
    without it, from ``strategy.picks`` on every history cut at ``data_date``. The strategy
    contract makes both give the same result.
```

**Code — `walkforward.py`, replace line 200:**

```python
    order. ``prepared`` is ``allocator.prepare_for(strategy, market)`` (which is
    ``strategy.prepare(market.history)`` for every strategy that is not ``MarketAware``) or None.
```

**Impact:** none at run time.

### Step 6: the test module

**File:** `engine/tests/test_market_fundamentals.py` (new)

**Change:** cover the field, the loader, the cache, the dispatch, the no-rows and no-table
degradations, and Gap A independence. The DB tests use the repo's existing `pg` fixture, which
applies every `db/migrations/*.sql` into a throwaway schema — so once phase 2 lands they get
`fundamental_facts` for free, and the "no table" case is produced by dropping it.

**Code — the complete file:**

```python
"""Phase 6: ``Market.fundamentals``, the panel load in ``backtest.io``, and ``prepare_market``.

The DB tests use the ``pg`` fixture (a throwaway schema with every migration applied), so they
skip when PG_TEST_URL is unset. The dispatch tests are pure and always run.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import FrozenInstanceError, replace as dc_replace
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from stratkit import hist, sawtooth

from seer_engine import dates, db, fx as fx_module
from seer_engine.backtest import dev, io as bio
from seer_engine.backtest.market import EMPTY_FUNDAMENTALS, Market, Membership
from seer_engine.fundamentals import FACT_COLUMNS, Fact, FundamentalPanel as Panel
from seer_engine.prices import to_decimal
from seer_engine.sim import q
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD
from seer_engine.strategies.allocator import Allocator, MarketAware, prepare_for
from seer_engine.strategies.base import History

D1, D2, D3 = date(2026, 9, 28), date(2026, 9, 29), date(2026, 9, 30)
Y2020 = date(2020, 1, 2)
DAYS = [D1, D2, D3]

BARS = [
    ("AAPL", D1, "100.1", "101.2", "99.5", "100.9", 1_000_000),
    ("AAPL", D2, "101", "102", "100", "101.5", 1_100_000),
    ("SPY", D1, "500", "505", "499", "501.1", 50_000_000),
    ("SPY", D2, "501", "506", "500", "502.2", 51_000_000),
]
UNIVERSE = [("AAPL", "SP500", Y2020, None), ("ATVI", "SP500", Y2020, D2)]
FX = [(D1, "16000"), (D2, "16100.5")]

# fundamental_facts is keyed by CIK (C1); the symbol arrives from the ticker_cik join.
CIK_AAPL, CIK_ATVI, CIK_GOOG = 320193, 718877, 1652044

# ATVI has facts and no bars: the Gap A case. AAPL has both. The two Assets rows for the same
# period_end differ only by accn and filed -- a restatement, which must survive the load.
# An instantaneous fact is stored period_start = period_end (C2) and must come back as None.
FACTS = [
    (CIK_AAPL, "us-gaap", "Assets", "USD", date(2015, 12, 31), date(2015, 12, 31),
     "352000000000", "0000320193-16-000001", 2016, "Q1", "10-Q", date(2016, 2, 1)),
    (CIK_AAPL, "us-gaap", "Revenues", "USD", date(2015, 10, 1), date(2015, 12, 31),
     "75872000000", "0000320193-16-000001", 2016, "Q1", "10-Q", date(2016, 2, 1)),
    (CIK_ATVI, "us-gaap", "Assets", "USD", date(2015, 12, 31), date(2015, 12, 31),
     "15274000000", "0000718877-16-000010", 2015, "FY", "10-K", date(2016, 2, 29)),
    (CIK_ATVI, "us-gaap", "Assets", "USD", date(2015, 12, 31), date(2015, 12, 31),
     "15300000000", "0000718877-17-000011", 2016, "FY", "10-K", date(2017, 3, 1)),
]
# One CIK, two symbols -- the share-class fan-out the join is expected to produce.
MAP = [
    ("AAPL", CIK_AAPL, date(2015, 1, 2), None, "Apple Inc.", "current", None),
    ("ATVI", CIK_ATVI, date(2015, 1, 2), date(2023, 10, 13), "Activision Blizzard, Inc.",
     "current", None),
    ("GOOG", CIK_GOOG, date(2015, 10, 2), None, "Alphabet Inc.", "current", None),
    ("GOOGL", CIK_GOOG, date(2015, 10, 2), None, "Alphabet Inc.", "current", None),
]
PANEL_ROWS = len(FACTS)  # no share class among FACTS' CIKs, so the join is 1:1 here


def market(**kwargs: Any) -> Market:
    base: dict[str, Any] = dict(
        history={"SPY": hist("SPY", sawtooth(len(DAYS), 200.0, 2.0, 1.5), days=DAYS)},
        membership=Membership((("AAA", Y2020, None),)),
        fx=((D1, Decimal("16000")),),
    )
    base.update(kwargs)
    return Market(**base)


def a_panel() -> Panel:
    return Panel.from_facts(
        (
            Fact(
                symbol="ATVI",
                taxonomy="us-gaap",
                tag="Assets",
                unit="USD",
                period_start=None,
                period_end=date(2015, 12, 31),
                val=15_274_000_000.0,
                accn="0000718877-16-000010",
                fy=2015,
                fp="FY",
                form="10-K",
                filed=date(2016, 2, 29),
            ),
        )
    )


# ---- the field ------------------------------------------------------------------------------


def test_market_defaults_to_the_empty_panel():
    m = market()
    assert m.fundamentals is EMPTY_FUNDAMENTALS
    assert isinstance(m.fundamentals, Panel)


def test_market_still_takes_three_positional_fields():
    """Every shipped construction site passes history, membership and fx and nothing else."""
    m = Market({"SPY": hist("SPY", sawtooth(3, 200.0, 2.0, 1.5), days=DAYS)}, Membership(()), ())
    assert m.fundamentals is EMPTY_FUNDAMENTALS


def test_market_stays_frozen():
    m = market()
    with pytest.raises(FrozenInstanceError):
        m.fundamentals = a_panel()  # type: ignore[misc]


def test_market_rejects_a_non_panel():
    with pytest.raises(TypeError, match="fundamentals must be a Panel"):
        market(fundamentals={"ATVI": []})


def test_with_fundamentals_carries_every_other_field():
    m = market()
    panel = a_panel()
    n = m.with_fundamentals(panel)
    assert n is not m
    assert m.fundamentals is EMPTY_FUNDAMENTALS  # the original is untouched
    assert n.fundamentals is panel
    assert n.history is m.history and n.membership is m.membership and n.fx == m.fx
    assert n.usd_idr_on(D1) == m.usd_idr_on(D1)  # the init=False caches were rebuilt
    assert n.last_bar_date("SPY") == m.last_bar_date("SPY")


def test_a_panel_symbol_needs_no_bars():
    """Gap A independence: ATVI has facts and no bars, and the Market accepts it."""
    m = market(fundamentals=a_panel())
    assert "ATVI" not in m.history
    assert m.last_bar_date("ATVI") is None
    assert m.fundamentals is not EMPTY_FUNDAMENTALS


# ---- the dispatch ----------------------------------------------------------------------------


class BarsOnly:
    """An allocator of the shipped shape: ``prepare`` only, no ``prepare_market``."""

    id = "FAKE_BARS_ONLY"

    def __init__(self) -> None:
        self.prepare_calls = 0

    def lookback(self, params: Any) -> int:
        return 1

    def symbols(self, params: Any) -> tuple[str, ...]:
        return ("SPY",)

    def holds(self, params: Any) -> tuple[str, ...]:
        return ("SPY",)

    def uses_members(self, params: Any) -> bool:
        return False

    def targets(self, history: Mapping[str, History], members: AbstractSet[str],
                data_date: date, held: frozenset[str], params: Any) -> tuple:
        return ()

    def prepare(self, history: Mapping[str, History]) -> Any:
        self.prepare_calls += 1
        return {"history": dict(history)}

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple:
        return ()


class PanelAware(BarsOnly):
    """The shape phase 7's allocator will have: ``prepare`` plus ``prepare_market``."""

    id = "FAKE_PANEL_AWARE"

    def __init__(self) -> None:
        super().__init__()
        self.prepare_market_calls = 0
        self.seen_panel: Any = None

    def prepare_market(self, m: Market) -> Any:
        self.prepare_market_calls += 1
        self.seen_panel = m.fundamentals
        return {"history": dict(m.history), "panel": m.fundamentals}


def test_adding_the_hook_does_not_change_the_allocator_check():
    """The whole point of a sibling protocol: Allocator's member set is untouched."""
    assert isinstance(BarsOnly(), Allocator)
    assert isinstance(PanelAware(), Allocator)


def test_market_aware_is_presence_only():
    assert not isinstance(BarsOnly(), MarketAware)
    assert isinstance(PanelAware(), MarketAware)

    class DataAttribute(BarsOnly):
        prepare_market = 5  # not callable, but runtime_checkable cannot tell

    assert isinstance(DataAttribute(), MarketAware)


def test_prepare_for_falls_back_to_prepare():
    a = BarsOnly()
    m = market(fundamentals=a_panel())
    prepared = prepare_for(a, m)
    assert a.prepare_calls == 1
    assert prepared == {"history": dict(m.history)}


def test_prepare_for_uses_prepare_market_and_passes_the_whole_market():
    a = PanelAware()
    panel = a_panel()
    m = market(fundamentals=panel)
    prepared = prepare_for(a, m)
    assert a.prepare_market_calls == 1 and a.prepare_calls == 0
    assert a.seen_panel is panel
    assert prepared["panel"] is panel


def test_prepare_for_rejects_a_non_callable_hook():
    class Broken(BarsOnly):
        prepare_market = 5

    with pytest.raises(TypeError, match="prepare_market must be callable"):
        prepare_for(Broken(), market())


# ---- the dev/lab runner ------------------------------------------------------------------------


DEV_DAYS = dates.sessions(date(2015, 6, 1), dev.DEV_END)  # 98 sessions ending at DEV_END
DEV_FX = ((date(2015, 1, 2), Decimal("12500")),)


class DevHoldOne(BarsOnly):
    """Weight 1 in SPY whenever SPY has a bar on data_date; enough for a real dev run."""

    id = "FAKE_DEV_HOLD"

    def _targets(self, history: Mapping[str, History], data_date: date) -> tuple:
        h = history.get("SPY")
        if h is None:
            return ()
        i = h.index_of(data_date)
        if i is None:
            return ()
        return (Target("SPY", Decimal("1"), q(to_decimal(float(h.close[i])))),)

    def symbols(self, params: Any) -> tuple[str, ...]:
        return ("SPY",)

    def targets(self, history, members, data_date, held, params) -> tuple:
        return self._targets(history, data_date)

    def targets_prepared(self, prepared, members, data_date, held, params) -> tuple:
        return self._targets(prepared["history"], data_date)


class DevPanelHoldOne(DevHoldOne):
    id = "FAKE_DEV_PANEL_HOLD"

    def __init__(self) -> None:
        super().__init__()
        self.prepare_market_calls = 0
        self.seen_panel: Any = None

    def prepare_market(self, m: Market) -> Any:
        self.prepare_market_calls += 1
        self.seen_panel = m.fundamentals
        return {"history": dict(m.history), "panel": m.fundamentals}


def dev_market(*, days=None, fx=DEV_FX, fundamentals=None) -> Market:
    d = DEV_DAYS if days is None else days
    kwargs: dict[str, Any] = dict(
        history={"SPY": hist("SPY", sawtooth(len(d), 200.0, 2.0, 1.5), days=d)},
        membership=Membership((("SPY", Y2020, None),)),
        fx=fx,
    )
    if fundamentals is not None:
        kwargs["fundamentals"] = fundamentals
    return Market(**kwargs)


def dev_candidate(allocator: Any) -> dev.Candidate:
    c = dev.Candidate(
        id="C-PHASE6",
        family="F1",
        rules=MONTHLY_HOLD,
        allocator=allocator,
        params=None,
        rationale="phase 6 dispatch test",
        added=date(2026, 10, 5),
        owner_inputs=(),
    )
    return dc_replace(c, owner_inputs=dev.candidate_owner_inputs(c))


def test_run_registry_keeps_the_bars_only_path_for_a_plain_allocator():
    a = DevHoldOne()
    m = dev_market(fundamentals=a_panel())
    rows = dev.run_registry(m, {}, (), (dev_candidate(a),))
    assert len(rows) == 1
    assert a.prepare_calls == 1
    assert not isinstance(a, MarketAware)


def test_run_registry_hands_a_market_aware_allocator_the_whole_market():
    a = DevPanelHoldOne()
    panel = a_panel()
    m = dev_market(fundamentals=panel)
    rows = dev.run_registry(m, {}, (), (dev_candidate(a),))
    assert len(rows) == 1
    assert a.prepare_market_calls == 1 and a.prepare_calls == 0
    assert a.seen_panel is panel


def test_the_two_paths_give_the_same_result():
    """prepare_market must not change the numbers when the extra data is unused."""
    panel = a_panel()
    plain = dev.run_registry(dev_market(fundamentals=panel), {}, (), (dev_candidate(DevHoldOne()),))
    aware = dev.run_registry(
        dev_market(fundamentals=panel), {}, (), (dev_candidate(DevPanelHoldOne()),)
    )
    assert plain[0].stats.metrics == aware[0].stats.metrics
    assert plain[0].start == aware[0].start and plain[0].end == aware[0].end


def test_the_fx_rebuild_keeps_the_panel():
    """dev._run rebuilds the Market for a pre-FX_START window; replace() carries the panel."""
    panel = a_panel()
    m = market(fundamentals=panel)
    rebuilt = dc_replace(m, fx=((date(1999, 1, 4), Decimal("8002")),))
    assert rebuilt.fundamentals is panel
    assert rebuilt.history is m.history and rebuilt.membership is m.membership


# ---- the loader --------------------------------------------------------------------------------


def seed_bars(conn):
    from seer_engine import bars

    with db.transaction(conn, False):
        bars.upsert_bars(conn, [bars.make_bar(*r) for r in BARS])


def seed_universe(conn):
    with db.transaction(conn, False):
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO universe (symbol, index_id, start_date, end_date, source_symbol) "
                "VALUES (%s, %s, %s, %s, %s)",
                [(s, i, a, b, s) for s, i, a, b in UNIVERSE],
            )


def seed_fx(conn):
    with db.transaction(conn, False):
        fx_module.upsert_fx(conn, FX)


def seed_facts(conn, rows=FACTS):
    with db.transaction(conn, False):
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO fundamental_facts "
                "(cik, taxonomy, tag, unit, period_start, period_end, val, accn, fy, fp, form, filed) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                rows,
            )


def seed_map(conn, rows=MAP):
    """``ticker_cik`` -- phase 4 writes it from phase 1's CSV; the panel load joins it."""
    with db.transaction(conn, False):
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO ticker_cik "
                "(symbol, cik, start_date, end_date, company, source, note) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                rows,
            )


def seed_panel(conn, rows=FACTS):
    """Both halves of the panel: facts and the dated bridge that names them."""
    seed_facts(conn, rows)
    seed_map(conn)


@pytest.fixture
def seeded(pg):
    seed_bars(pg)
    seed_universe(pg)
    seed_fx(pg)
    return pg


def test_load_market_without_any_fundamentals_rows(seeded, tmp_path):
    """The live database today: the table exists (migration applied) and holds nothing."""
    market_, rows = bio.load_market(seeded, cache_dir=tmp_path)
    assert rows == len(BARS)
    assert market_.fundamentals is EMPTY_FUNDAMENTALS
    assert list(tmp_path.glob("fundamentals-*.pkl")) == []


@pytest.mark.parametrize("missing", ["fundamental_facts", "ticker_cik"])
def test_load_market_without_the_tables_at_all(seeded, tmp_path, missing):
    """A database that has not run 005_fundamentals.sql still backs a backtest.

    Either table missing is enough: the panel load joins both, and ``to_regclass`` is used
    rather than catching ``UndefinedTable``, because that error would abort ``load_market``'s
    read-only transaction with no savepoint to recover from.
    """
    with db.transaction(seeded, False):
        seeded.execute(f"DROP TABLE {missing}")
    assert bio.facts_fingerprint(seeded) == (0, None)
    market_, rows = bio.load_market(seeded, cache_dir=tmp_path)
    assert rows == len(BARS)
    assert market_.fundamentals is EMPTY_FUNDAMENTALS


def test_facts_with_no_ticker_cik_row_are_dropped_not_guessed(seeded, tmp_path):
    """A fact whose filed date falls in no interval for its CIK has no symbol, so it is dropped.

    This is the mechanism that keeps a recycled ticker's two filers apart, and it is why an
    incomplete ticker_cik shrinks the panel rather than corrupting it.
    """
    seed_facts(seeded)
    seed_map(seeded, [("AAPL", CIK_AAPL, date(2015, 1, 2), None, "Apple Inc.", "current", None)])
    rows, _ = bio.facts_fingerprint(seeded)
    assert rows == 2  # AAPL's two facts; ATVI's two have no interval and vanish
    panel = bio.load_panel(seeded, cache_dir=tmp_path)
    assert panel.names() == ("AAPL",)


def test_a_share_class_pair_fans_one_fact_out_to_both_symbols(seeded, tmp_path):
    """One CIK, two tickers (GOOG/GOOGL). The join is 1:2 and the fingerprint counts the join."""
    seed_facts(
        seeded,
        [(CIK_GOOG, "us-gaap", "Assets", "USD", date(2015, 12, 31), date(2015, 12, 31),
          "147461000000", "0001652044-16-000012", 2015, "FY", "10-K", date(2016, 2, 11))],
    )
    seed_map(seeded)
    rows, _ = bio.facts_fingerprint(seeded)
    assert rows == 2  # one stored fact, two panel rows
    panel = bio.load_panel(seeded, cache_dir=tmp_path)
    assert panel.names() == ("GOOG", "GOOGL")


def test_re_vendoring_ticker_cik_invalidates_the_pickle(seeded, tmp_path):
    """The cache key counts over the join, so a map change busts it even with no new fact."""
    seed_panel(seeded)
    bio.load_market(seeded, cache_dir=tmp_path)
    before = sorted(p.name for p in tmp_path.glob("fundamentals-*.pkl"))
    seed_map(seeded, [("AAPL2", CIK_AAPL, date(2015, 1, 2), None, "Apple Inc.", "manual", None)])
    bio.load_market(seeded, cache_dir=tmp_path)
    after = sorted(p.name for p in tmp_path.glob("fundamentals-*.pkl"))
    assert after != before and len(after) == 1


def test_facts_fingerprint_and_load_panel(seeded, tmp_path):
    seed_panel(seeded)
    rows, max_filed = bio.facts_fingerprint(seeded)
    assert rows == PANEL_ROWS
    assert max_filed == date(2017, 3, 1)

    frame = bio.read_facts_frame(seeded)
    assert tuple(frame.columns) == bio.FACTS_COLUMNS == FACT_COLUMNS
    assert len(frame) == PANEL_ROWS
    facts = bio.facts_from_frame(frame)
    assert len(facts) == PANEL_ROWS
    by_symbol = {f.symbol for f in facts}
    assert by_symbol == {"AAPL", "ATVI"}

    instantaneous = [f for f in facts if f.tag == "Assets" and f.symbol == "ATVI"]
    assert [f.period_start for f in instantaneous] == [None, None]
    assert sorted(f.filed for f in instantaneous) == [date(2016, 2, 29), date(2017, 3, 1)]
    assert len({f.accn for f in instantaneous}) == 2  # the restatement is kept, not overwritten

    flow = next(f for f in facts if f.tag == "Revenues")
    assert flow.period_start == date(2015, 10, 1) and flow.period_end == date(2015, 12, 31)
    assert flow.fy == 2016 and flow.fp == "Q1" and flow.form == "10-Q"
    assert flow.val == pytest.approx(75_872_000_000.0)


def test_load_market_attaches_the_panel_and_caches_it(seeded, tmp_path, caplog):
    seed_panel(seeded)
    market_, _ = bio.load_market(seeded, cache_dir=tmp_path)
    assert market_.fundamentals is not EMPTY_FUNDAMENTALS
    cached = list(tmp_path.glob("fundamentals-*.pkl"))
    assert [p.name for p in cached] == [f"fundamentals-2017-03-01-{PANEL_ROWS}.pkl"]

    # a second load hits the pickle instead of the table
    with caplog.at_level("INFO"):
        again, _ = bio.load_market(seeded, cache_dir=tmp_path)
    assert "fundamentals cache hit" in caplog.text
    assert again.fundamentals == market_.fundamentals


def test_a_new_fingerprint_sweeps_the_stale_pickle(seeded, tmp_path):
    seed_panel(seeded)
    bio.load_market(seeded, cache_dir=tmp_path)
    seed_facts(
        seeded,
        [
            (CIK_AAPL, "us-gaap", "Assets", "USD", date(2016, 3, 31), date(2016, 3, 31),
             "305000000000", "0000320193-16-000002", 2016, "Q2", "10-Q", date(2016, 4, 27)),
        ],
    )
    bio.load_market(seeded, cache_dir=tmp_path)
    names = sorted(p.name for p in tmp_path.glob("fundamentals-*.pkl"))
    assert names == [f"fundamentals-2016-04-27-{PANEL_ROWS + 1}.pkl"]


def test_the_panel_holds_a_symbol_with_no_bars(seeded, tmp_path):
    """Gap A independence end to end: ATVI has facts in the panel and no row in history."""
    seed_panel(seeded)
    market_, _ = bio.load_market(seeded, cache_dir=tmp_path)
    assert "ATVI" not in market_.history
    frame = bio.read_facts_frame(seeded)
    assert "ATVI" in set(frame["symbol"])


def test_load_market_leaves_no_transaction_open(seeded, tmp_path):
    from psycopg.pq import TransactionStatus

    seed_panel(seeded)
    bio.load_market(seeded, cache_dir=tmp_path)
    assert seeded.info.transaction_status == TransactionStatus.IDLE


# ---- the research store (Step 7) ---------------------------------------------------------------


def test_data_files_is_not_widened():
    """The whole backward-compatibility argument in one assertion.

    research._read_manifest rejects a manifest whose `files` keys are not a superset of
    DATA_FILES and a subset of DATA_FILES | OPTIONAL_DATA_FILES, and load_store hashes the
    manifest's own keys. If fundamentals.csv ever joins DATA_FILES, every store on disk stops
    loading -- with a ValueError, before any reader runs.
    """
    from seer_engine import research

    assert research.FUNDAMENTALS_FILE not in research.DATA_FILES
    assert research.OPTIONAL_DATA_FILES == (research.FUNDAMENTALS_FILE,)
    assert research.FUNDAMENTALS_HEADER == ",".join(FACT_COLUMNS)


def test_a_store_without_fundamentals_loads_with_an_empty_panel(tmp_path):
    """A store built before this phase: four files, the old fingerprint, no error."""
    from seer_engine import research

    store = _build_tiny_store(tmp_path)                      # build_store(facts=None)
    before = research.fingerprint_of(research._read_manifest(store)["files"])
    data = research.load_store(store)
    assert sorted(data.manifest["files"]) == sorted(research.DATA_FILES)
    assert data.fingerprint == before
    assert data.market.fundamentals is EMPTY_FUNDAMENTALS


def test_a_store_with_fundamentals_round_trips_the_panel(seeded, tmp_path):
    """The store CSV and the database give the SAME facts, because both go through
    io.facts_from_frame. This is the assertion that would fail if the reader were routed
    through fundamentals.fact_from_row, which takes typed values and would silently drop
    every string row."""
    from seer_engine import research

    seed_panel(seeded)
    facts = bio.facts_from_frame(bio.read_facts_frame(seeded))
    store = _build_tiny_store(tmp_path / "with", facts=facts)
    data = research.load_store(store)
    assert research.FUNDAMENTALS_FILE in data.manifest["files"]
    assert data.market.fundamentals.names() == ("AAPL", "ATVI")
    assert data.market.fundamentals == Panel.from_facts(facts)
    # and the instant marker survived the CSV: '' in the file, None in memory
    assets = [f for f in facts if f.tag == "Assets"]
    assert assets and all(f.period_start is None for f in assets)
```

`_build_tiny_store` is a small local helper that calls `research.build_store` with a stub
`downloader` and `fetch_fx` — the same injection `engine/tests/test_research_store.py` already
uses. It is written in this module rather than imported, so `test_research_store.py` stays
byte-identical.

**Impact:** one new test module; no existing test is edited. In particular
`engine/tests/test_strategy_purity.py` is left byte-identical to what phase 5 leaves, and
`engine/tests/test_lab_methods.py` is not touched at all (phase 7 owns its one edit).

### Step 7: the research store carries a fundamentals panel

**File:** `engine/src/seer_engine/research.py` (`OPTIONAL_DATA_FILES`, the manifest, `_read_fundamentals`,
the `Market(...)` at `:472`), `engine/src/seer_engine/commands/research_store.py`

**Why this is in scope (C6).** `commands/lab.py:211` calls `research.load_store(...)` and
`lab/runner.py:165` runs `dev.run_registry(data.market, ...)`. The lab does **not** run against
Neon's `bars`; it runs against the research store. So without this step, phase 7's allocator
would be handed a market carrying `EMPTY_FUNDAMENTALS` every time it ran in the lab, would rank
nothing, and would record all-cash trials — **silently**, with every test green. That is the
single worst failure mode in the set, and it is why it is owned here rather than left as a
handoff: this phase already owns the identical fix at `dev.py:367`, and `with_fundamentals`
exists precisely to make the construction site a one-line change.

**`fundamentals.csv` is an OPTIONAL store file. It must not join `DATA_FILES`.** The draft of
this step said "added to `DATA_FILES`" and claimed in the same breath that "an existing store
built before this phase still loads". **Those two cannot both be true**, and the reconciler
measured why against the shipped code:

- `research._read_manifest` rejects a manifest whose `files` keys are not *exactly*
  `DATA_FILES` (`research.py:524-529`: `set(files) != set(DATA_FILES)` → `ValueError`).
- `research.load_store` then hashes `for name in DATA_FILES` (`research.py:441-443`), and
  `file_sha256` turns a missing file into
  `ValueError("fundamentals.csv is missing from the research store")` (`research.py:192-194`).

So widening `DATA_FILES` would make **every research store on disk today fail to load, with an
error, before any reader runs** — including the one this phase's own byte-identical
verification points both checkouts at. Not a changed fingerprint: a hard load failure.

The shape that satisfies the exit criterion instead:

1. `research.FUNDAMENTALS_FILE = "fundamentals.csv"`, `FUNDAMENTALS_HEADER = ",".join(FACT_COLUMNS)`,
   and a **new, separate** `OPTIONAL_DATA_FILES: tuple[str, ...] = (FUNDAMENTALS_FILE,)`.
   `DATA_FILES` is **not** touched.
2. `_read_manifest`'s check becomes
   `set(DATA_FILES) <= set(files) <= set(DATA_FILES) | set(OPTIONAL_DATA_FILES)` — the four
   required names must be there, the fifth may be.
3. `load_store` hashes **`manifest["files"]`'s own keys** rather than `DATA_FILES`, and
   `fingerprint_of(files)` is unchanged (it already hashes whatever mapping it is handed, in
   sorted order). An old four-file store therefore produces a **bit-identical fingerprint** to
   the one it produces on `origin/main`.
4. `_seal(tmp, counts, *, extra_files=())` includes the optional names it is given.
   **`_COUNT_KEYS` gains nothing**, deliberately: `MANIFEST_KEYS` is asserted whole at
   `engine/tests/test_research_store.py:233` (`set(manifest) == research.MANIFEST_KEYS`) and
   that file has no owner in this set, so the manifest's key set must not change.
5. `build_store(..., facts: Sequence[Fact] | None = None)` — when `facts` is None (every
   existing caller, including all of `test_research_store.py`) nothing is written, `_seal` gets
   no `extra_files`, and **the store is byte-identical to today's**. When facts are given, the
   CSV is written before `_seal`.
6. `_read_fundamentals(path) -> Panel` returns `EMPTY_FUNDAMENTALS` when
   `FUNDAMENTALS_FILE not in manifest["files"]`, so an existing store loads with an empty
   panel and no error — which is now actually true, not merely asserted.
7. `research.py:472` passes `fundamentals=` to the `Market(...)` it builds.
8. `commands/research_store.py` gains **`--with-fundamentals`**, off by default: it opens
   `db.connect()`, reads the panel through this phase's own `bt_io.read_facts_frame(conn)` and
   hands the facts to `build_store(facts=...)`.

**Why the reader is `io.facts_from_frame` and not `fact_from_row`, and this is load-bearing.**
The draft said the reader is "a straight `fact_from_row` over `csv.DictReader`". It cannot be.
The CSV is streamed from `FACTS_COPY_SQL`, whose instant marker is an **empty string** (C2),
and `csv.DictReader` yields **strings for every cell**. Phase 5's `fact_from_row` takes *typed*
values — it maps `period_start == period_end` where both are `date` objects, and `Fact`'s
`__post_init__` calls `_check_date`, which rejects `'2015-12-31'`. Every row would raise
`FundamentalsError`, and `facts_from_rows(skip_invalid=True)` would **drop all of them and
return an empty panel with no error at all**. That is precisely the silent all-cash-trials
failure this step exists to prevent, reintroduced one layer down. So:

```python
def _read_fundamentals(path: Path) -> Panel:
    """The store's fact panel, or EMPTY_FUNDAMENTALS when the store has no fundamentals.csv.

    The file is written from io.FACTS_COPY_SQL, so its cells are exactly what that COPY
    emits: ISO dates, '' for a NULL fy/fp, and '' for period_start when the fact is
    instantaneous. io.facts_from_frame is the ONE function in the tree that turns that text
    back into Fact objects, and reusing it here is what makes the store-backed panel and the
    database-backed panel identical by construction rather than by inspection. Do NOT route
    this through fundamentals.fact_from_row: that function takes typed values (date, Decimal)
    and would reject every string cell -- silently, because facts_from_rows skips what it
    cannot parse.
    """
    if not path.is_file():
        return EMPTY_FUNDAMENTALS
    frame = pd.read_csv(
        path, dtype={c: str for c in FACT_COLUMNS} | {"val": np.float64},
        na_filter=False, float_precision="round_trip",
    )
    if tuple(frame.columns) != FACT_COLUMNS:
        raise ValueError(f"{path.name}: header is {tuple(frame.columns)}, expected {FACT_COLUMNS}")
    return Panel.from_facts(facts_from_frame(frame))
```

`research.py` already imports from `seer_engine.backtest.io` (`research.py:50`), so adding
`facts_from_frame` to that import line introduces no new dependency. **`research.py` still
imports nothing from `seer_engine.db`** — its module docstring's "Never Neon" invariant is
intact, because the connection lives in the command, which hands `build_store` a plain
sequence of facts.

**The fingerprint consequence, stated because it is irreversible-looking and is not.**
`data.fingerprint` is sha256 over the sorted `name:sha256` lines of the manifest's `files`, and
`lab/runner.py` records it on every trial row. Under the optional-file design: **an existing
store's fingerprint does not change at all** — same four files, same hashes, same sorted text,
same digest — so no already-recorded trial is invalidated and the lab's history is untouched.
A store rebuilt *with* `--with-fundamentals` gets a fifth line and therefore a new fingerprint,
exactly as a rebuild with new bars would. Nothing reads the field as an equality gate against
a constant, and `runner.preflight` keys on `method_id` and `config_digest`, neither of which
includes it, so **no already-run method is re-run or blocked.** M0001 and M0004 are unaffected
either way.

**Impact:** a store rebuilt with `--with-fundamentals` carries the panel; every store built
before this phase loads unchanged, with the same fingerprint, and gets an empty one.
`engine/tests/test_research_store.py` is left **byte-identical and green**: none of its builds
passes `facts`, so every assertion it makes about `DATA_FILES`, the directory contents, the
manifest keys and the fingerprint still holds. The lab's existing two methods ignore the field
entirely — neither is `MarketAware`, so `prepare_for` hands them `market.history` as before.

---

### Step 8: the last two `Market` rebuilds

**File:** `engine/src/seer_engine/paper/replay.py:281`, `engine/src/seer_engine/commands/paper.py:254`

**Change:** both rebuild a `Market` field by field, exactly as `dev.py:367` did before Step 4,
and both would silently drop the panel. The fix is one line each. **The before-state is quoted
from the tree, not paraphrased** — the variable names matter, and an earlier draft of this step
had them wrong:

```python
# paper/replay.py:281, inside expected_bracket -- BEFORE
        fixed = Market(history=market.history, membership=market.membership, fx=((start, head.usd_idr),))
# AFTER
        fixed = replace(market, fx=((start, head.usd_idr),))

# commands/paper.py:254, the return of the market-rewind helper -- BEFORE
    return Market(history=history, membership=market.membership, fx=fx)
# AFTER
    return replace(market, history=history, fx=fx)
```

with `replace` imported from `dataclasses` in each module. Both are literal one-line
substitutions: neither call passes a field the `replace` form does not carry, and `membership`
drops out of the call precisely because `replace` carries it unchanged.

**Why now rather than "when paper trades a fundamental allocator".** Nothing paper-traded is
`MarketAware` today, so both changes are behaviour-neutral. That is exactly the argument for
making them in the same commit as the field: a positional rebuild that drops a new field is
invisible until the day it costs money, and the index assigns every `Market(...)` site to this
phase for that reason. `paper/store.py:1035` also builds a market from the database without a
panel; it is left alone deliberately — it is a *construction from scratch*, not a rebuild that
drops a field, and `load_panel(conn)` is callable there when paper needs one.

**Impact:** none today. `pytest engine/tests -q` is unchanged by both lines.

---

## Verification

**Build / lint:**

```bash
cd /home/miftah/.worktrees/seer/edgar-fundamentals
python -m ruff check engine/src engine/tests
python -c "import seer_engine.backtest.io, seer_engine.backtest.dev, seer_engine.strategies.allocator"
```

**Tests:**

```bash
cd /home/miftah/.worktrees/seer/edgar-fundamentals/engine
docker start seer-pg 2>/dev/null || docker run -d --name seer-pg -e POSTGRES_PASSWORD=pg -p 55432:5432 postgres:16
export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres
python -m pytest tests -q                                   # the whole suite must be green
python -m pytest tests/test_strategy_purity.py -q            # must pass with the file UNMODIFIED
git diff --exit-code tests/test_strategy_purity.py           # proves it was not edited
python -m pytest tests/test_market_fundamentals.py tests/test_backtest_io.py \
                 tests/test_backtest_market.py tests/test_backtest_dev.py \
                 tests/test_allocator.py tests/test_lab_methods.py -q
```

**Byte-identical backtest output — the pinned candidate.**

Pinned candidate: **`F4-MOM12-N10-TREND`** (`backtest/registry.py`) — a book-engine `Allocator`
(`f_factor.FACTOR`) running through `dev.run_registry`, i.e. through the exact line this phase
changed (`dev.py:455`), with a `MONTHLY_HOLD`-family rule set and a window that starts after
`FX_START` (so it also exercises the unmodified branch of the FX rebuild). Run the script below
in the `origin/main` checkout and in this worktree, pointing both at the **same** research store,
and diff the two outputs; they must be identical byte for byte.

```bash
# once, from the main checkout, if engine/.research does not exist (reads the database):
cd /home/miftah/seer/engine && python -m seer_engine research_store

cat > /tmp/phase6_pin.py <<'PY'
import hashlib, os
from pathlib import Path
from seer_engine import research
from seer_engine.backtest import dev
from seer_engine.backtest.registry import REGISTRY

PIN = "F4-MOM12-N10-TREND"
data = research.load_store(Path(os.environ["SEER_RESEARCH_STORE"]))
c = next(x for x in REGISTRY if x.id == PIN)
captured = {}
def on_result(i, result, row):
    captured["result"], captured["row"] = result, row
dev.run_registry(data.market, data.dividends, data.spy_dividends, (c,), on_result=on_result)
r, row = captured["result"], captured["row"]
h = hashlib.sha256()
for s in r.snapshots:
    h.update(f"{s.date}|{s.cash_usd}|{s.equity_usd}|{getattr(s, 'invested_usd', '')}\n".encode())
for f in r.fills:
    h.update(f"{f!r}\n".encode())
for t in r.trades:
    h.update(f"{t!r}\n".encode())
m = row.stats.metrics
print(f"candidate      {PIN}")
print(f"window         {row.start} .. {row.end}")
print(f"total_return   {m.total_return}")
print(f"max_drawdown   {m.max_drawdown}")
print(f"profit_factor  {m.profit_factor}")
print(f"trades         {m.trades}")
print(f"mar            {row.mar}")
print(f"snapshots      {len(r.snapshots)}  fills {len(r.fills)}  trades {len(r.trades)}")
print(f"run-sha256     {h.hexdigest()}")
PY

export SEER_RESEARCH_STORE=/home/miftah/seer/engine/.research
cd /home/miftah/seer/engine                           && python /tmp/phase6_pin.py > /tmp/pin-main.txt
cd /home/miftah/.worktrees/seer/edgar-fundamentals/engine && python /tmp/phase6_pin.py > /tmp/pin-branch.txt
diff -u /tmp/pin-main.txt /tmp/pin-branch.txt && echo "PHASE 6: byte-identical"
```

**`load_market` is byte-identical against the live database.** This one needs
`DATABASE_URL_UNPOOLED` and proves the loader change is inert against a database with no
fundamentals (today's state: migration 005 not applied, so the table is absent).

```bash
cat > /tmp/phase6_market.py <<'PY'
import hashlib
from seer_engine import db
from seer_engine.backtest import io as bio

conn = db.connect()
market, rows = bio.load_market(conn)
h = hashlib.sha256()
h.update(f"{rows}\n".encode())
for s in sorted(market.history):
    hh = market.history[s]
    h.update(s.encode()); h.update(hh.dates.tobytes())
    for a in (hh.open, hh.high, hh.low, hh.close, hh.volume):
        h.update(a.tobytes())
h.update(repr(market.membership.intervals).encode())
h.update(repr(market.fx).encode())
print(f"bar_rows       {rows}")
print(f"symbols        {len(market.history)}")
print(f"intervals      {len(market.membership.intervals)}")
print(f"fx_rows        {len(market.fx)}")
print(f"market-sha256  {h.hexdigest()}")
PY
cd /home/miftah/seer/engine                           && python /tmp/phase6_market.py > /tmp/mkt-main.txt
cd /home/miftah/.worktrees/seer/edgar-fundamentals/engine && python /tmp/phase6_market.py > /tmp/mkt-branch.txt
diff -u /tmp/mkt-main.txt /tmp/mkt-branch.txt && echo "PHASE 6: load_market unchanged"
# and no new cache file appeared, because the table is absent:
ls /home/miftah/.worktrees/seer/edgar-fundamentals/engine/.cache/fundamentals-*.pkl 2>/dev/null \
  && echo "UNEXPECTED: a fundamentals pickle was written against a database with no table"
```

**Manual check:** `engine/.cache/` holds exactly one `bars-*.pkl` and no `fundamentals-*.pkl`
after the live-database run; `git diff --stat` touches **ten** source files
(`backtest/market.py`, `backtest/io.py`, `backtest/dev.py`, `backtest/runner.py`,
`backtest/walkforward.py`, `strategies/allocator.py`, `research.py`,
`commands/research_store.py`, `paper/replay.py`, `commands/paper.py`) and adds one test file,
and touches nothing under `engine/src/seer_engine/strategies/` except `allocator.py`.

**The pre-existing store must still load, unchanged.** This is the check that proves Step 7 did
not break backward compatibility, and it is the precondition for the pinned-candidate diff
below being runnable at all — that diff loads `/home/miftah/seer/engine/.research`, which was
built before this phase:

```bash
cd /home/miftah/.worktrees/seer/edgar-fundamentals/engine
python -c "
from pathlib import Path
from seer_engine import research
d = research.load_store(Path('/home/miftah/seer/engine/.research'))
print('files      ', sorted(d.manifest['files']))
print('fingerprint', d.fingerprint)
print('panel      ', d.market.fundamentals.names())
"
```
Expect exactly the four original file names, the **same fingerprint the `origin/main` checkout
prints for the same directory**, and an empty `names()`. A `ValueError` here means `DATA_FILES`
was widened after all, and every research store on disk is unloadable.

**Exit criteria:**
1. `Market` is still `@dataclass(frozen=True, eq=False)` and `seer_engine.backtest.market` still
   imports no forbidden module.
2. `load_market` returns a `Market` whose `fundamentals` is a `Panel`, and returns
   `EMPTY_FUNDAMENTALS` without error against a database whose `fundamental_facts` is empty **or
   absent**.
3. `pytest engine/tests -q` is green and `git diff --exit-code engine/tests/test_strategy_purity.py`
   is clean.
4. `diff -u /tmp/pin-main.txt /tmp/pin-branch.txt` is empty for `F4-MOM12-N10-TREND`, and
   `diff -u /tmp/mkt-main.txt /tmp/mkt-branch.txt` is empty.
5. `isinstance(x, Allocator)` is True for every existing allocator, and
   `isinstance(x, MarketAware)` is False for every one of them.
6. **`research.load_store` on a store built before this phase succeeds, returns the same
   `fingerprint` string `origin/main` returns for the same directory, and yields a market whose
   `fundamentals` is `EMPTY_FUNDAMENTALS`.** `git diff --exit-code engine/tests/test_research_store.py`
   is clean — that file has no owner in this set and must not need one.
7. A store built with `--with-fundamentals` carries a fifth file, a new fingerprint, and a
   panel whose facts are **equal** to `io.load_panel(conn)`'s for the same database — the two
   go through the same `facts_from_frame`, so this is a round-trip assertion, not a tolerance.

## Handoffs

**H1 — resolved: the research store is owned by this phase (Step 7).** The original draft
flagged it as "blocks phase 7 and no phase in the set owns it" and offered two ways out. The
index's Decisions table picked the first — extend the research store — and assigned it here,
because this phase already owns the identical `Market`-rebuild-drops-the-field fix at
`dev.py:367` and already ships `with_fundamentals` to make the construction site one line. The
second option (a `lab run --fundamentals` flag loading from Neon) is **not** taken: the lab's
window opens in 1996 and Neon's `bars` start in 2015, so a DB-backed lab market would be a
different and much shorter backtest, not the same one with extra data.

**H2 — resolved: the two remaining `Market` rebuilds are owned by this phase (Step 8).**
`paper/replay.py:281` and `commands/paper.py:254` are fixed here, behaviour-neutrally, for the
reason the original draft already gave: both become silent data loss the moment a fundamental
allocator is paper-traded. `paper/store.py:1035` stays out of scope — it constructs a market
from scratch rather than rebuilding one, so it drops nothing; `load_panel(conn)` is callable
there when paper needs a panel.

**H3 — `io._read_cache`/`_write_cache` and `_read_facts_cache`/`_write_facts_cache` are near
duplicates.** Deliberate: the bars pair is on the hot path of every shipped backtest and this
phase must not perturb it. A later cleanup can parameterise one pair by glob and column tuple.

**H4 — `facts_from_frame` iterates in Python.** Fine at the measured scale (795 filers), and it
keeps the frame-level cache honest. If the panel build dominates load time, cache the `Panel`
pickle instead of the frame — one function, `_facts_frame`, changes.

**H5 — `commands/backtest.py:193`, `commands/backtest_wf.py:212`, `commands/backtest_b.py:282`
still call `strategy.prepare(market.history)` directly.** All three are hard-wired to
`STRATEGY_A`/`STRATEGY_A2`, bracket strategies that will never be `MarketAware`, so routing them
through `prepare_for` would change no behaviour and would widen this phase's diff into three
shipped commands. Left as-is on purpose; a future fundamentals-aware command should call
`prepare_for`.

**H5b — the `--with-fundamentals` flag is this phase's, its documentation is phase 7's.** Step
7 adds `python -m seer_engine research_store --with-fundamentals`; phase 7 owns
`docs/runbooks/data-pipeline.md` and carries the row for it, plus the warning that a store
rebuilt **without** the flag loads with an empty panel and no error. That silence is
deliberate — it is what keeps every store on disk loadable and its fingerprint unchanged — so
the check before `lab run M0005` is "does this store's manifest list `fundamentals.csv`", not
"has phase 6 landed". Phase 7's runbook section and the M0005 docstring both say so.

**H6 — phase 7 owns `satisfies: R6`'s visible half.** This phase adds no allocator, no lab
method, no runbook row, and makes no edit to `engine/tests/test_lab_methods.py` (phase 7 owns
that one edit) or to `engine/tests/test_strategy_purity.py` (phase 5 owns that one edit). If
anything in this plan starts ranking on a factor, it has crossed into phase 7.

**H7 — what phase 7 gets, exactly.** `Market.fundamentals` is a
`seer_engine.fundamentals.FundamentalPanel`, and `Market.__post_init__` **type-checks it**. A
phase-7 test cannot pass a hand-rolled fake panel into `Market(...)`; it must build a real
`FundamentalPanel.from_facts((Fact(...), ...))`. Fakes remain fine for the pure functions that
take a panel as an argument and never go through `Market`. The dispatch contract is
`strategies.allocator.MarketAware` + `prepare_for`, **not** a new member on `Allocator` — see
Step 3 for the measurement that forced it.

## Rollback

This phase is one commit on `feature/edgar-fundamentals`; `git revert` it. Nothing it adds is
depended on by phases 1–5, and the only consumer is phase 7, which is not merged before it.
It writes no schema and no data: the single on-disk artefact is
`engine/.cache/fundamentals-<max filed>-<count>.pkl`, which is gitignored and regenerated, and
which is never created at all against a database with no fundamentals rows. To undo by hand
rather than by revert: drop the `fundamentals` field, `EMPTY_FUNDAMENTALS` and
`with_fundamentals` from `market.py`; drop the fundamentals section, constants and the
`load_panel` call from `io.py`; drop `MarketAware`, `prepare_for` and the `TYPE_CHECKING` import
from `allocator.py`; restore `dev.py:50`, `:367` and `:455`; drop `FUNDAMENTALS_FILE`,
`FUNDAMENTALS_HEADER`, `OPTIONAL_DATA_FILES`, `_read_fundamentals`, `build_store`'s `facts`
keyword and `_seal`'s `extra_files` from `research.py` and the `--with-fundamentals` flag from
`commands/research_store.py`; restore the two `Market(...)` calls at `paper/replay.py:281` and
`commands/paper.py:254`; delete `engine/tests/test_market_fundamentals.py`.

**Reverting the research-store half is safe in both directions**, and that is a consequence of
`DATA_FILES` never being widened. A store built *before* this phase has four files and keeps
loading after a revert. A store built *with* `--with-fundamentals` has five, and after a revert
the restored `_read_manifest` rejects it (`set(files) != set(DATA_FILES)`) — so the one manual
step a revert needs is `python -m seer_engine research_store` to rebuild without the flag.
Trials recorded against the five-file fingerprint keep it; nothing reads it as an equality gate
and `runner.preflight` does not key on it, so no method is blocked either way. The verification in this plan is the signal: a diff in
`/tmp/pin-*.txt` or `/tmp/mkt-*.txt` means revert this phase alone, as the index's Rollback
section says.

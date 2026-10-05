> Adopted from `EDGAR_FUNDAMENTALS_PLAN.md` phase 7. Source: `.workflows/plan/edgar-fundamentals/phase-7.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 7: Fundamental factor allocator, lab method, runbook

**Plan set:** `EDGAR_FUNDAMENTALS_PLAN.md`
**Analysis:** `20261005-081833-G7K2_code_analyzer.md`
**Satisfies:** R6 — factor exposure to the lab: value, quality, profitability and SUE
**Depends on:** Phase 5 (pure derivation), Phase 6 (`Market.fundamentals` + `prepare_market`)
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine/strategies`, `engine/src/seer_engine/lab`, `docs`

---

## Reconciled contracts with phases 5 and 6 (READ FIRST — four of five assumptions were wrong)

Neither plan file existed at planning time, so A1–A5 below were written against the shapes the
index's phase descriptions implied. **The reconciler checked all five against the shipped
plans. A1–A4 were wrong and A5 was half wrong.** Phase 5 won every accessor question — it
executed its code and its 39 tests pass — and phase 6 won the dispatch question, because it
*measured* the failure the obvious design causes. This plan was rewritten to them; the
rewrites are confined to the two places this plan already named (the `Panel` Protocol and
`FundamentalAllocator.prepare_market`) plus the feature expressions in `_row`.

### C1 — phase 5's panel surface is `as_of(symbol, t) -> Snapshot | None`, not four accessors

A1–A4 assumed `flow_ttm`, `stock_asof`, `filed_asof` and `sue_asof`. **None of them exist.**
Phase 5 ships one point-in-time entry point per symbol and a record of everything visible on
that date:

```python
class FundamentalPanel:                       # seer_engine.fundamentals
    symbols: Mapping[str, SymbolFundamentals]
    def names(self) -> tuple[str, ...]: ...
    def get(self, symbol: str) -> SymbolFundamentals | None: ...
    def as_of(self, symbol: str, t: date) -> Snapshot | None: ...
    def snapshots_on(self, t, symbols=None) -> dict[str, Snapshot]: ...

@dataclass(frozen=True, slots=True)
class Snapshot:
    symbol: str
    asof: date
    fiscal_period_end: date | None
    filed: date | None            # the staleness gate reads this
    revenue: float
    cost_of_revenue: float
    gross_profit: float           # reported where tagged, else Revenues - CostOfRevenue
    gross_profit_basis: str       # "reported" | "derived" | "none"
    operating_income: float
    net_income: float
    operating_cash_flow: float
    diluted_eps: float
    diluted_shares: float
    assets: float
    equity: float
    shares_outstanding: float
    sue: float                    # NaN until phase 5's minimum history is met
    sue_quarters: int
    observations: Mapping[str, Obs]
```

Every field answers from facts with `filed <= t` and only those; a field phase 5 could not
resolve is **NaN**, never a zero and never None. `as_of` returns `None` only for a symbol the
panel has never heard of.

**This is a better fit than the four accessors were**, not merely a different one: one call per
symbol per rank session instead of five, and the staleness gate, the four factors and the
fallback basis all come from one consistent observation set rather than five independent
lookups that could straddle a filing.

### C2 — flows are **annual**, not trailing-twelve-month

A1 assumed TTM. Phase 5 deliberately produces annual flows, and its reasoning is recorded as
its decision 4: annual coverage is 8/8 in the measurement, while a clean TTM needs four
untroubled quarters, so a TTM basis would be available for some names and not others and would
put a **systematic wedge through the cross-section** — exactly the bias a cross-sectional
factor must not have. The Fama-French convention is annual anyway. Phase 5's quarterly series
still exists; it is what `quarters()` builds and SUE consumes, and it is simply not what the
level metrics read.

**Phase 5 wins. Every factor definition in this plan is restated on an annual basis** — see the
rewritten formula block under Goal, the rewritten `_row`, and the variant descriptions in
Step 2. `net_income` and `gross_profit` on a `Snapshot` are the latest *fiscal year* visible at
`t`.

### C3 — the dispatch contract is `MarketAware` + `prepare_for`, not a widened `Allocator`

A5 assumed phase 6 would add `prepare_market` to the `Allocator` protocol. **Phase 6 measured
that doing so makes `isinstance(x, Allocator)` False for every structural implementer**, because
`Allocator` is `@runtime_checkable` and a runtime-checkable protocol's `isinstance` is an
attribute-presence check over its full member set. Eight production sites lean on that check —
`dev.py:154`, `dev.py:156`, `dev_report.py:263`, `book_runner.py:252`, `book_runner.py:385`,
`paper/book.py:160`, `allocator.py:373`, `allocator.py:529` — plus `test_allocator.py:249-251`
and `test_lab_methods.py:42,83-84`. So phase 6 shipped a sibling protocol instead:

```python
@runtime_checkable
class MarketAware(Protocol):
    def prepare_market(self, market: Market) -> Any: ...

def prepare_for(obj: Any, market: Market) -> Any:
    """``obj.prepare_market(market)`` when obj is MarketAware, else ``obj.prepare(market.history)``."""
```

`Allocator`'s member set is **unchanged**. `dev.py:455` is the one real dispatch site and now
calls `prepare_for(c.allocator, market)`.

**What this changes here:** nothing in `FundamentalAllocator`'s body — it already defines
`prepare_market` as a plain method, so it satisfies `MarketAware` structurally, with no base
class and no registration. What changes is the *vocabulary*: this plan now says `MarketAware`
where it said "the widened protocol", the test module asserts
`isinstance(FUNDAMENTAL, MarketAware)` alongside `isinstance(FUNDAMENTAL, Allocator)`, and the
shared lab gate in Step 3 branches on `isinstance(c.allocator, MarketAware)` rather than on an
invented `uses_fundamentals` marker. **`uses_fundamentals` is deleted**: two sources of truth
for "my live path is `prepare_market`" is one too many, and phase 6's protocol is the real one.

### C4 — `Market.fundamentals` is type-checked, so tests cannot pass a fake panel into `Market`

A5 said the allocator "duck-types both, so only the attribute name matters". That is still true
of the **allocator**, and this module still imports neither `seer_engine.fundamentals` nor
`backtest.market`. It is **not** true of the test module: phase 6's `Market.__post_init__`
raises `TypeError` unless `fundamentals` is a `seer_engine.fundamentals.FundamentalPanel`.

So the test module splits its fakes:

- the pure functions that take a panel as an argument (`fundamental_rows`,
  `targets_with_panel`, and everything they call) keep `FakePanel` — they never see a `Market`,
  and a fake is what makes hand-computed features readable;
- the **four** `Market(...)` constructions in the module build a **real**
  `FundamentalPanel.from_facts((Fact(...), ...))` — three pass one explicitly
  (`test_prepare_market_carries_the_panel`, `test_market_identity_prepared_equals_single_window`,
  `test_every_sue_free_variant_runs_a_dev_window_with_a_real_panel`) and the fourth
  (`test_prepare_market_tolerates_a_market_with_no_panel`) passes none and therefore gets
  phase 6's default, which is phase 5's `EMPTY_PANEL` — still a real panel.
  `test_no_lookahead_on_filed` constructs no `Market` and keeps its `FakePanel`.
  That is strictly better coverage: it exercises phase 5's selection, the Q4
  derivation and the SUE minimum rather than a fake's `dict` lookup.

### C5 — the other call sites, corrected

A5 named `dev.py:455`, `walkforward.py:200` and `runner.py:143` as sites that must prefer
`prepare_market`. **Only `dev.py:455` is a call**; the other two are docstring lines describing
the `prepared` argument their callers pass in. Phase 6 verified this and updated both
docstrings. `commands/backtest.py:193`, `commands/backtest_wf.py:212` and
`commands/backtest_b.py:282` do call `prepare` directly but are hard-wired to
`STRATEGY_A`/`STRATEGY_A2`, which are bracket `Strategy` objects that will never be
`MarketAware`. Nothing here depends on any of them.

### C6 — the research store is phase 6's, and `lab run M0005` still must not be run here

Phase 6 now owns extending the research store with a `fundamentals.csv` artifact (its Step 7),
so the lab sees a real panel rather than `EMPTY_FUNDAMENTALS`. That removes the original H1
blocker from this plan. **It does not change the standing rule that this phase ships M0005
unrun** — `runner.preflight` refuses a second run of any method, so one premature run spends
the id permanently, and the id must be spent on a run against a store that has actually been
rebuilt with a panel. The warning stays in the method docstring and the runbook.

## Goal

After this phase the lab can rank index members on point-in-time fundamentals. A new sibling of
`f_factor`, `strategies/f_fundamental.py`, exposes one allocator (`FUNDAMENTAL`, id `"FND"`)
that ranks eligible members on book-to-price (value), return on equity (quality), Novy-Marx
gross profitability, SUE, or an equal-weighted z-score composite of all four, with eligibility
rules written in `f_factor`'s style. A new lab method `M0005` pre-registers six fixed variants
over it, and `docs/runbooks/data-pipeline.md` documents the `fundamentals` command, its exit
codes, the `SEC_CONTACT_EMAIL` setting and how to re-vendor `engine/data/ticker_cik.csv`.

---

## Measured facts this phase is built on

Run against this worktree's code and the repo's NYSE calendar on 2026-10-05. These numbers
decide three design choices, so they are recorded rather than assumed.

1. **The lab does not run on Neon's `bars`.** `commands/lab.py:211` calls
   `research.load_store(...)`; `research.py:57` sets `STORE_START = date(1993, 1, 29)` and
   `research.py:58` sets `MEMBERSHIP_START = date(1996, 1, 2)`. The task brief's "the dev window
   is only ~9.5 months" describes Neon's `bars` (which start 2015-01-02), **not** the lab. A lab
   candidate's dev window is `candidate_window(market, c)` → roughly 1996-01-03 … 2015-10-16.
2. **A 200-day trend gate is impossible on Neon's window and needless on the lab's.** Against
   bars starting 2015-01-02, SPY's 200th bar is 2015-10-16, so `candidate_window` would return
   start 2015-10-19 — one day into the untouched test window — and raise `DevWindowError`.
   Against the research store it is harmless. Either way the variants here use `trend=None`.

   | `lookback` | SPY's n-th bar (from 2015-01-02) | dev window start | ≤ DEV_END 2015-10-16 |
   |---|---|---|---|
   | 20 | 2015-01-30 | 2015-02-02 | yes |
   | 50 | 2015-03-16 | 2015-03-17 | yes |
   | 126 | 2015-07-02 | 2015-07-06 | yes |
   | **200** | **2015-10-16** | **2015-10-19** | **no — DevWindowError** |

3. **The smoke market caps `lookback` too.** `engine/tests/labkit.py:18`: `SMOKE_FIRST =
   date(2013, 12, 2)`, "473 NYSE sessions through DEV_END". `test_lab_methods.py::
   test_candidate_runs_a_smoke_window` calls `dev.run_candidate` on it, so every variant's
   `lookback` must be comfortably under 473. This phase's is **20** (`DV_N`, trend off).
4. **`test_lab_methods.py::test_allocator_contract` asserts `nonempty > 0`**
   (`engine/tests/test_lab_methods.py:93`). It exercises `prepare(history)` and
   `targets(history, …)` only — the history-only path, which for a fundamental allocator has no
   panel and therefore targets nothing. This is the one shared gate this phase must touch; see
   Step 3 and the Interface Contract.
5. **XBRL warm-up fits, price warm-up is what binds.** The four factors need, per symbol:
   one instantaneous fact (assets / equity / shares) and **one annual flow** with
   `filed <= t` (phase 5 ships annual, not TTM — C2), plus phase 5's SUE minimum (a seasonal random walk over `EPS_q − EPS_{q−4}`
   scaled by the dispersion of recent surprises needs roughly eight quarters of EPS). For a
   2015 data date those were filed 2012–2014, well inside XBRL's 2009 start, so **no variant
   here needs a calendar warm-up beyond what the ingest already covers**. The binding warm-up is
   the 20-bar dollar-volume window, hence `lookback = 20`.

---

## Interface Contract

**Creates:**
- `seer_engine.strategies.f_fundamental` (new module, `strategies/f_fundamental.py`)
- `f_fundamental.DV_N`, `.EXCLUDED`, `.MAX_TOP`, `.FACTORS`, `.Rank`, `.Sizing`
- `f_fundamental.Panel`, `f_fundamental.Snapshot` (runtime-checkable Protocols — the phase-5
  surface this phase needs: `Panel.as_of(symbol, t) -> Snapshot | None`, and the seven
  `Snapshot` members the four factors and the staleness gate read). See C1.
- (**not** an `EmptyPanel` of its own: `EMPTY_PANEL` is imported from `seer_engine.fundamentals`, phase 5's single instance, which is also what phase 6 makes `Market.fundamentals` default to)
- `f_fundamental.FundamentalParams`, `.FundamentalRow`, `.FundamentalPrepared`
- `f_fundamental.fundamental_lookback`, `.factors_read`, `.fundamental_rows`, `.trend_on`,
  `.zscores`, `.composite_scores`, `.rank_rows`, `.fundamental_weights`, `.targets_from_rows`,
  `.targets_with_panel`
- `f_fundamental.FundamentalAllocator`, `f_fundamental.FUNDAMENTAL` (**allocator id `"FND"`** —
  verified free: the ids in use today are `A A2 B BLEND F1 F7 F11 FAC FAKE_FIXED FAKE_MOM M0001
  PICKS ROT VOLTARGET`). It satisfies phase 6's `MarketAware` protocol structurally by defining
  `prepare_market`; there is **no** `uses_fundamentals` marker (C3).
- `seer_engine.lab.methods.m0005_fundamental_factors` exporting `METHOD` (**method id `M0005`**
  — verified free: `lab/methods/` holds only `m0001_momentum_own_vol_scaling.py` and
  `m0004_split_cadence_own_vol.py`)
- `engine/tests/test_f_fundamental.py`

**Deletes:** none
**Renames:** none
**Signature changes:** none

**Modifies (shared, claimed here — verified sole owner across the set):**
- `docs/runbooks/data-pipeline.md` — seven places (Step 5). **No other phase touches it**:
  phases 1, 2, 3 and 4 each state they leave it here, and phase 2 hands it over explicitly.
- `engine/tests/test_lab_methods.py:85–93` — the `nonempty > 0` assertion in
  `test_allocator_contract` gains a branch for allocators satisfying phase 6's `MarketAware`.
  The branch is *stricter*, not laxer: such an allocator must prove `nonempty == 0`. No existing
  method's gate changes by one character. See Step 3 for the reasoning and the exact diff.
  **No other phase touches this file** — phase 6 reads it for evidence only.

**Requires (from earlier phases):**
- Phase 5 (C1, C2): `seer_engine.fundamentals.FundamentalPanel.as_of(symbol, t) -> Snapshot |
  None`, and a `Snapshot` carrying `filed`, `net_income`, `gross_profit`, `assets`, `equity`,
  `shares_outstanding`, `sue`. Flows are **annual**. Unresolved fields are NaN.
- Phase 6 (C3, C4): `Market.fundamentals` (attribute name exact, type
  `FundamentalPanel`, **type-checked in `__post_init__`**);
  `seer_engine.strategies.allocator.MarketAware` and `prepare_for`; `dev.py:455` dispatching
  through `prepare_for`. `Allocator`'s member set is unchanged.
- Phase 6: `Market(...)` accepts `fundamentals=` as a keyword — `test_f_fundamental.py` builds
  a market with a **real** `FundamentalPanel` to run the end-to-end dev-window test (C4).
- Phase 6 (Step 7): the research store carries `fundamentals.csv`, so a lab run would see a
  real panel. **This phase still does not run `lab run M0005`** (C6).

**Leaves alone (owned by others):**
- `strategies/f_factor.py` — not read at runtime, not imported, not edited. The sibling
  relationship is by convention, not by code.
- `seer_engine/fundamentals/*` (Phase 5), `backtest/market.py`, `backtest/io.py`,
  `strategies/allocator.py`, `backtest/dev.py`, `backtest/walkforward.py`,
  `backtest/runner.py` (Phase 6).
- `seer_engine/commands/fundamentals.py` (Phase 4) — documented here, not written here.
- `engine/data/ticker_cik.csv`, `engine/data/SOURCES.md` (Phase 1) — the runbook points at
  `SOURCES.md` for the vendoring recipe rather than restating it.
- `engine/tests/allocatorkit.py` — unchanged.

---

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/strategies/f_fundamental.py` | create | the whole allocator (new file) |
| `engine/src/seer_engine/lab/methods/m0005_fundamental_factors.py` | create | method `M0005`, six variants (new file) |
| `engine/tests/test_f_fundamental.py` | create | unit + contract + end-to-end dev-window tests (new file) |
| `engine/tests/test_lab_methods.py` | modify | `test_allocator_contract`, at `:85–93` |
| `docs/runbooks/data-pipeline.md` | modify | architecture `:14`, commands table `:42`, exit codes `:53`, new "SEC fundamentals" section after `:76`, env table `:86`, health checks `:261`, rollback `:274` |

---

## Implementation Steps

### Step 1: The allocator

**File:** `engine/src/seer_engine/strategies/f_fundamental.py` (new)
**Change:** one new module, complete below. It is pure: no `psycopg`, `requests`, `yfinance`,
`time`, `random`, `logging`, `urllib`, `socket`, no `now`/`utcnow`/`today`/`fromtimestamp`/
`random` attribute, no `print`/`open`/`input`. `engine/tests/test_strategy_purity.py` globs
`strategies/*.py` and so covers this file with no test edit.

**Code:**

```python
"""Fundamental cross-sectional factors over index members (Gap B, R6).

One allocator, ``FUNDAMENTAL`` (id ``"FND"``). A sibling of ``f_factor``, not a rewrite of it:
``f_factor`` ranks on price history alone, this one ranks on point-in-time SEC filings.

THE PANEL AND THE TWO PATHS. Fundamentals do not live in ``Mapping[str, History]``, so they
cannot reach the allocator through ``prepare(history)``. They reach it through
``prepare_market(market)``, which reads ``market.fundamentals``. The consequence is explicit
and load-bearing:

    targets(history, ...) and prepare(history) see NO panel. With no panel no symbol has
    fundamental features, so no symbol is eligible, so both return (). That is the correct
    reading of "nothing is known about any filer", not a bug and not a silent zero.

    The live path is prepare_market(market) -> targets_prepared(prepared, ...).

``FundamentalPrepared`` is therefore a thin holder of ``(history, panel)``, and
``targets_prepared`` delegates to the same ``targets_with_panel`` the single-window path calls.
The Allocator contract's P4 identity
``targets_prepared(prepare(H), M, d, held, p) == targets(H.upto(d), M, d, held, p)`` then holds
by construction (both sides run the empty-panel case), and the identity that actually matters,
``targets_prepared(prepare_market(Market), ...) == targets_with_panel(H.upto(d), panel, ...)``,
holds bit for bit for the same reason. Defining ``prepare_market`` is what makes this class
satisfy phase 6's ``MarketAware`` protocol, which is how ``dev.py``'s ``prepare_for`` routes to
the live path and how the shared lab gate knows which identity to check.

On ``data_date`` d, a symbol is **eligible** when all of these hold:
    it is a member on d and is not ``"SPY"``; it has a bar dated d and at least
    ``fundamental_lookback(params)`` bars through d; close >= ``min_price``; its 20-day mean
    close x volume > ``min_dollar_volume`` (strict); the panel has a fact for it filed on or
    before d and no more than ``max_stale_days`` days before d; and every factor the chosen
    ranking reads (``factors_read(params)``) is finite.
A symbol with filings but no bar dated d - the 133 ever-members with no price history (Gap A) -
fails the bar test and is simply absent from the eligible set. It is never ranked, never
weighted, and never treated as a zero. A symbol with bars but no filings fails the panel test
the same way.

Features, all read from ONE phase-5 snapshot per symbol -- ``panel.as_of(symbol, d)`` -- which
answers from facts with ``filed <= d`` and only those. FLOWS ARE ANNUAL, not trailing-twelve-
month: phase 5 produces the latest visible fiscal year, because annual coverage is 8/8 while a
clean TTM needs four untroubled quarters and would put a systematic wedge through the
cross-section. The Fama-French convention is annual anyway.

    s             = panel.as_of(symbol, d)        (None -> the symbol is not eligible)
    market cap    = s.shares_outstanding x close(d)
                    (point-in-time only because the share count is filed-dated; when either
                    side is missing or <= 0 the cap is NaN and ``value`` is NaN with it)
    value         = s.equity / market cap                 (book-to-price, Fama-French)
    quality       = s.net_income / s.equity               (return on equity, ANNUAL income)
    profitability = s.gross_profit / s.assets             (ANNUAL gross profit)
                    (Novy-Marx gross profitability. ``s.gross_profit`` is phase 5's series and
                    may be derived: ``GrossProfit`` was tagged by only 2 of the 8 sampled
                    filers, so phase 5 falls back to ``Revenues - CostOfRevenue`` and records
                    which in ``s.gross_profit_basis``. This module consumes that series and
                    never re-derives it.)
    sue           = s.sue        (phase 5's seasonal random walk ``EPS_q - EPS_{q-4}`` scaled by
                    the dispersion of recent surprises; NaN until its minimum history is met,
                    which ``s.sue_quarters`` reports)
    staleness     = (d - s.filed).days            (the gate; s.filed is the no-look-ahead axis)

Phase 5 returns NaN, not None, for a field it could not resolve. ``_num`` maps both to NaN, so
the eligibility rule "every factor the ranking reads must be finite" is unchanged.
Analyst-consensus earnings surprise is deliberately absent: Finnhub's free tier returns four
quarters and cannot be backfilled to 2015 (plan index, Scope).

Ranking (ties broken by symbol ascending), the first ``top``:
    value | quality | profitability | sue  - that one feature, descending;
    composite                             - the cross-sectional z-score of each of the four over
                                            the eligible set, combined with ``params.weights``,
                                            descending. A factor whose eligible-set population
                                            standard deviation is zero, or that has fewer than
                                            two eligible rows, contributes 0.0 to every row.
Weights: ``equal`` gives every chosen name ``equal_weight(top)`` (fewer than ``top`` eligible
names leave the rest in cash); ``rank`` gives the i-th of k chosen (0-based)
``to_weight((k - i) / (k(k+1)/2) x k / top)`` - linear in rank, the same total exposure as
``equal`` - floor-quantized so the sum stays <= 1. A weight that floors to zero drops its name.
Trend gate: when ``trend = (symbol, n)``, nothing is targeted (all cash) unless that symbol has
a bar dated d, at least n bars through d, and close > SMA(n) (strict). Default ``None``:
measured, a 200-day gate over bars starting 2015-01-02 pushes the dev window start to
2015-10-19, past ``DEV_END``.
Held positions get no special treatment: the targets are exactly the new top set, so a held name
that falls out of it is signal-exited by the book engine (a rebalance).
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence, Set
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Literal, Protocol, runtime_checkable

import numpy as np

from seer_engine.fundamentals import EMPTY_PANEL
from seer_engine.sim.book import WEIGHT_QUANTUM, Target, equal_weight, to_weight
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History, as_day
from seer_engine.strategies.indicators import mean_dollar_volume_window, sma_window

DV_N = 20  # dollar-volume window, as f_factor and Strategy A
EXCLUDED: frozenset[str] = frozenset({"SPY"})  # never a factor target, even if listed as a member
MAX_TOP = 1000  # equal_weight(top) stays >= 0.001
FACTORS: tuple[str, ...] = ("value", "quality", "profitability", "sue")

Rank = Literal["value", "quality", "profitability", "sue", "composite"]
Sizing = Literal["equal", "rank"]
_RANKS: tuple[str, ...] = (*FACTORS, "composite")
_SIZINGS: tuple[str, ...] = ("equal", "rank")

_NAN = float("nan")


# --------------------------------------------------------------------------- the panel contract


@runtime_checkable
class Snapshot(Protocol):
    """One symbol's fundamentals as of one date -- phase 5's ``fundamentals.panel.Snapshot``.

    Every field answers from facts with ``filed <= t`` and only those. An unresolved field is
    NaN, never a zero. FLOWS ARE ANNUAL (the latest visible fiscal year), not TTM -- phase 5's
    decision 4, and the reason this module's quality and profitability legs are annual ratios.
    Only the seven members below are read here; the real Snapshot carries more.
    """

    filed: date | None
    net_income: float
    gross_profit: float
    assets: float
    equity: float
    shares_outstanding: float
    sue: float


@runtime_checkable
class Panel(Protocol):
    """What this allocator needs of a point-in-time fundamental panel (phase 5 supplies it).

    One call per symbol per rank session. ``None`` means "this panel has never heard of that
    symbol" -- distinct from a snapshot whose fields are NaN, which means "heard of it, knew
    nothing as of that date". Both make the symbol ineligible; the distinction is kept because
    the second is worth logging and the first is not.
    """

    def as_of(self, symbol: str, data_date: date) -> Snapshot | None: ...


# The "no fundamentals" panel is phase 5's EMPTY_PANEL, imported, NOT a local EmptyPanel
# class. An earlier draft of this file defined its own; that was a third object meaning the
# same thing (phase 5 owns EMPTY_PANEL, phase 6 re-exports it as backtest.market
# EMPTY_FUNDAMENTALS and uses it as Market.fundamentals' default), and the identity test
# `prepare_market(m).panel is EMPTY_PANEL` would then have been False for a Market built
# without a panel -- which is every Market in the tree before a store is rebuilt. One object,
# one identity. `seer_engine.fundamentals` is pure, so importing it here keeps
# test_strategy_purity.py green; it is the same import backtest/market.py makes.
#
# EMPTY_PANEL.as_of(symbol, t) returns None for every symbol, which is exactly the contract
# the Panel protocol above states and exactly what the history-only `prepare` path needs.


def _panel(obj: object) -> Panel:
    """``obj`` as a Panel, or ``EMPTY_PANEL`` when it is None.

    After phase 6, ``market.fundamentals`` is never None and never absent -- the field has a
    default and ``__post_init__`` type-checks it. The None branch is kept for the duck-typed
    ``prepare_market(market)`` contract (``market`` is deliberately ``Any`` so this module
    never imports ``backtest.market``), not because a real ``Market`` can reach it.
    """
    if obj is None:
        return EMPTY_PANEL
    if not isinstance(obj, Panel):
        raise TypeError(f"fundamentals must satisfy the Panel protocol, got {type(obj).__name__}")
    return obj


# --------------------------------------------------------------------------- params


def _plain(x: float | Decimal) -> str:
    """``x`` as a plain decimal string without trailing zeros: 5.0 -> "5", 20000000.0 -> "20000000"."""
    d = Decimal(repr(x)) if isinstance(x, float) else x
    return format(d.normalize(), "f")


def _check_int(name: str, v: object, lo: int) -> int:
    if isinstance(v, bool) or not isinstance(v, int):
        raise TypeError(f"{name} must be an int, got {type(v).__name__}")
    if v < lo:
        raise ValueError(f"{name} must be >= {lo}, got {v}")
    return v


def _check_float(name: str, v: object) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise TypeError(f"{name} must be a float, got {type(v).__name__}")
    out = float(v)
    if not math.isfinite(out):
        raise ValueError(f"{name} must be finite, got {out!r}")
    return out


@dataclass(frozen=True, slots=True)
class FundamentalParams:
    """Fundamental-factor parameters. ``weights`` is read only when ``rank == "composite"``."""

    rank: Rank
    top: int = 20  # holdings
    sizing: Sizing = "equal"
    weights: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0)  # value, quality, profitability, sue
    min_dollar_volume: float = 20_000_000.0  # 20-day mean close x volume > this (strict)
    min_price: float = 5.0  # close >= min_price
    max_stale_days: int = 400  # the latest fact used must be filed within this many days of d
    trend: tuple[str, int] | None = None  # all cash unless trend[0] close > SMA(trend[1]) on d

    def __post_init__(self) -> None:
        if not isinstance(self.rank, str):
            raise TypeError(f"rank must be a str, got {type(self.rank).__name__}")
        if self.rank not in _RANKS:
            raise ValueError(f"rank must be one of {_RANKS}, got {self.rank!r}")
        _check_int("top", self.top, 1)
        if self.top > MAX_TOP:
            raise ValueError(f"top must be <= {MAX_TOP}, got {self.top}")
        if not isinstance(self.sizing, str):
            raise TypeError(f"sizing must be a str, got {type(self.sizing).__name__}")
        if self.sizing not in _SIZINGS:
            raise ValueError(f"sizing must be one of {_SIZINGS}, got {self.sizing!r}")
        if not isinstance(self.weights, tuple) or len(self.weights) != len(FACTORS):
            raise TypeError(f"weights must be a tuple of {len(FACTORS)} floats, got {self.weights!r}")
        clean: list[float] = []
        total = 0.0
        for name, w in zip(FACTORS, self.weights, strict=True):
            value = _check_float(f"weights[{name}]", w)
            if value < 0.0:
                raise ValueError(f"weights[{name}] must be >= 0, got {value}")
            clean.append(value)
            total = total + value
        if total <= 0.0:
            raise ValueError(f"weights must not be all zero, got {self.weights!r}")
        object.__setattr__(self, "weights", (clean[0], clean[1], clean[2], clean[3]))
        dv = _check_float("min_dollar_volume", self.min_dollar_volume)
        if dv < 0.0:
            raise ValueError(f"min_dollar_volume must be >= 0, got {dv}")
        object.__setattr__(self, "min_dollar_volume", dv)
        price = _check_float("min_price", self.min_price)
        if price < 0.01:
            raise ValueError(f"min_price must be >= 0.01, got {price}")
        object.__setattr__(self, "min_price", price)
        _check_int("max_stale_days", self.max_stale_days, 1)
        if self.trend is not None:
            if not isinstance(self.trend, tuple) or len(self.trend) != 2:
                raise TypeError(f"trend must be None or a (symbol, n) tuple, got {self.trend!r}")
            symbol, n = self.trend
            if not isinstance(symbol, str) or not symbol:
                raise ValueError(f"trend symbol must be a non-empty str, got {symbol!r}")
            _check_int("trend n", n, 1)

    def as_dict(self) -> dict[str, str]:
        """Every parameter as a plain string, in a fixed key order (report and pre-registration)."""
        return {
            "rank": self.rank,
            "top": str(self.top),
            "sizing": self.sizing,
            "weights": ":".join(_plain(w) for w in self.weights),
            "min_dollar_volume": _plain(self.min_dollar_volume),
            "min_price": _plain(self.min_price),
            "max_stale_days": str(self.max_stale_days),
            "trend": "none" if self.trend is None else f"{self.trend[0]}:{self.trend[1]}",
        }


def _check_params(params: object) -> FundamentalParams:
    if not isinstance(params, FundamentalParams):
        raise TypeError(f"params must be FundamentalParams, got {type(params).__name__}")
    return params


def _check_held(held: object) -> None:
    if not isinstance(held, Set):
        raise TypeError(f"held must be a set of symbols, got {type(held).__name__}")


def fundamental_lookback(params: FundamentalParams) -> int:
    """Bars each read symbol needs through d: ``max(DV_N, trend n)``.

    Fundamentals need no bar warm-up of their own - a filing's availability is its ``filed``
    date, not a bar count - so the dollar-volume window is what binds. Measured: a 200-day
    trend gate over bars starting 2015-01-02 puts the dev window start at 2015-10-19, past
    ``backtest.dev.DEV_END``; keep ``trend`` None or short.
    """
    _check_params(params)
    trend_n = params.trend[1] if params.trend is not None else 0
    return max(DV_N, trend_n)


def factors_read(params: FundamentalParams) -> tuple[str, ...]:
    """The factor names ``params``' ranking reads: one of ``FACTORS``, or all four for composite."""
    p = _check_params(params)
    return FACTORS if p.rank == "composite" else (p.rank,)


# --------------------------------------------------------------------------- rows


@dataclass(frozen=True, slots=True)
class FundamentalRow:
    """One eligible symbol's features at a ``data_date`` close.

    A factor the ranking does not read may be NaN; a factor it does read is finite by
    construction (``fundamental_rows`` drops the row otherwise).
    """

    symbol: str
    close: float
    dollar_volume: float
    market_cap: float
    value: float
    quality: float
    profitability: float
    sue: float


def _num(x: object) -> float:
    """``x`` as a finite float, else NaN. None, a bool or a non-number all become NaN."""
    if x is None or isinstance(x, bool) or not isinstance(x, (int, float)):
        return _NAN
    out = float(x)
    return out if math.isfinite(out) else _NAN


def _pos(x: object) -> float | None:
    """``x`` as a finite float > 0, else None (a zero or negative denominator is "not known")."""
    out = _num(x)
    return out if out > 0.0 else None


def _dollar_volume(h: History, i: int) -> float:
    """``mean_dollar_volume_window`` over the ``DV_N`` bars ending at row ``i`` (inclusive)."""
    close = h.close[i + 1 - DV_N : i + 1].reshape(1, DV_N)
    volume = h.volume[i + 1 - DV_N : i + 1].reshape(1, DV_N)
    with np.errstate(divide="ignore", invalid="ignore"):
        return float(mean_dollar_volume_window(close, volume, DV_N)[0])


def _row(symbol: str, close: float, dollar_volume: float, snap: Snapshot) -> FundamentalRow:
    """One symbol's four factors from one phase-5 snapshot; anything unresolved becomes NaN.

    ``snap`` was built from facts with ``filed <= data_date`` and only those -- the
    no-look-ahead boundary is phase 5's and this module never second-guesses it. The two flow
    legs are ANNUAL (the latest visible fiscal year), not trailing-twelve-month; see C2.
    """
    shares = _pos(snap.shares_outstanding)
    equity = _pos(snap.equity)
    assets = _pos(snap.assets)
    net_income = _num(snap.net_income)
    gross_profit = _num(snap.gross_profit)
    market_cap = shares * close if shares is not None else _NAN
    value = equity / market_cap if (equity is not None and market_cap > 0.0) else _NAN
    quality = net_income / equity if (equity is not None and math.isfinite(net_income)) else _NAN
    profitability = gross_profit / assets if (assets is not None and math.isfinite(gross_profit)) else _NAN
    return FundamentalRow(
        symbol=symbol,
        close=close,
        dollar_volume=dollar_volume,
        market_cap=market_cap,
        value=value,
        quality=quality,
        profitability=profitability,
        sue=_num(snap.sue),
    )


def fundamental_rows(
    history: Mapping[str, History],
    panel: Panel,
    members: Set[str],
    data_date: date,
    params: FundamentalParams,
) -> list[FundamentalRow]:
    """Eligible members' features on ``data_date``, sorted by symbol (see the module docstring).

    Reads each member's last ``fundamental_lookback(params)`` bars ending at ``data_date`` and
    exactly one phase-5 snapshot per symbol, which answers from facts with
    ``filed <= data_date``; later bars and later filings are never read.
    """
    p = _check_params(params)
    as_day(data_date)
    panel = _panel(panel)
    lb = fundamental_lookback(p)
    wanted = factors_read(p)
    out: list[FundamentalRow] = []
    for symbol in sorted(members):
        if symbol in EXCLUDED:
            continue
        h = history.get(symbol)
        if h is None:
            continue
        i = h.index_of(data_date)
        if i is None or i + 1 < lb:
            continue
        close = float(h.close[i])
        if not math.isfinite(close) or close < p.min_price:
            continue
        dollar_volume = _dollar_volume(h, i)
        if not math.isfinite(dollar_volume) or not dollar_volume > p.min_dollar_volume:
            continue
        snap = panel.as_of(symbol, data_date)
        if snap is None:
            continue
        filed = snap.filed
        # filed > data_date would be a phase-5 bug, not a stale fact. Checked anyway: this is
        # the one assertion that stands between a look-ahead and a backtest that looks great.
        if filed is None or filed > data_date or (data_date - filed).days > p.max_stale_days:
            continue
        row = _row(symbol, close, dollar_volume, snap)
        if all(math.isfinite(getattr(row, name)) for name in wanted):
            out.append(row)
    return out


def trend_on(history: Mapping[str, History], data_date: date, params: FundamentalParams) -> bool:
    """The trend gate on ``data_date``: True when ``params.trend`` is None, else close > SMA(n) (strict).

    False when the trend symbol is absent, has no bar dated ``data_date`` or fewer than n bars
    through it. Reads only bars dated on or before ``data_date``.
    """
    p = _check_params(params)
    as_day(data_date)
    if p.trend is None:
        return True
    symbol, n = p.trend
    h = history.get(symbol)
    if h is None:
        return False
    i = h.index_of(data_date)
    if i is None or i + 1 < n:
        return False
    window = h.close[i + 1 - n : i + 1].reshape(1, n)
    with np.errstate(divide="ignore", invalid="ignore"):
        sma = sma_window(window, n)[0]
    return bool(window[0, -1] > sma)


# --------------------------------------------------------------------------- ranking


def zscores(values: Sequence[float]) -> list[float]:
    """Cross-sectional z-scores, population standard deviation, summed left to right.

    All zeros when there are fewer than two values or the standard deviation is not positive and
    finite. Accumulated in plain Python so the result depends only on the input order, which is
    the same (symbol ascending) on every path.
    """
    n = len(values)
    if n < 2:
        return [0.0] * n
    total = 0.0
    for x in values:
        total = total + x
    mean = total / n
    acc = 0.0
    for x in values:
        acc = acc + (x - mean) * (x - mean)
    sd = math.sqrt(acc / n)
    if not math.isfinite(sd) or sd <= 0.0:
        return [0.0] * n
    return [(x - mean) / sd for x in values]


def composite_scores(rows: Sequence[FundamentalRow], params: FundamentalParams) -> list[float]:
    """The weighted sum of each factor's z-score over ``rows``, one score per row, in row order."""
    p = _check_params(params)
    out = [0.0] * len(rows)
    for name, weight in zip(FACTORS, p.weights, strict=True):
        if weight == 0.0:
            continue
        column = zscores([float(getattr(r, name)) for r in rows])
        for k, z in enumerate(column):
            out[k] = out[k] + weight * z
    return out


def rank_rows(rows: Sequence[FundamentalRow], params: FundamentalParams) -> list[FundamentalRow]:
    """The chosen rows, in rank order (ties by symbol ascending)."""
    p = _check_params(params)
    if p.rank == "composite":
        scored = list(zip(composite_scores(rows, p), rows, strict=True))
        return [r for _, r in sorted(scored, key=lambda pair: (-pair[0], pair[1].symbol))][: p.top]
    return sorted(rows, key=lambda r: (-float(getattr(r, p.rank)), r.symbol))[: p.top]


def _floor_weight(x: float) -> Decimal | None:
    """``to_weight(x)``, or None when ``x`` floors to zero (or is not a finite positive float)."""
    if not math.isfinite(x) or Decimal(repr(x)) < WEIGHT_QUANTUM:
        return None
    return to_weight(x)


def fundamental_weights(chosen: Sequence[FundamentalRow], params: FundamentalParams) -> list[Decimal | None]:
    """One weight per chosen row (None = floors to zero, the row is dropped). Sum of non-None <= 1."""
    p = _check_params(params)
    if not chosen:
        return []
    if p.sizing == "equal":
        w = equal_weight(p.top)
        return [w for _ in chosen]
    k = len(chosen)
    denominator = float(k * (k + 1) // 2)
    scale = k / p.top
    return [_floor_weight((k - i) / denominator * scale) for i in range(k)]


def targets_from_rows(rows: Sequence[FundamentalRow], params: FundamentalParams) -> tuple[Target, ...]:
    """Rank, weigh and price ``rows``: Targets with no limit, stop or take, in rank order."""
    chosen = rank_rows(rows, params)
    out: list[Target] = []
    for row, weight in zip(chosen, fundamental_weights(chosen, params), strict=True):
        if weight is None:
            continue
        target = target_from_close(row.symbol, row.close, weight)
        if target is not None:
            out.append(target)
    return tuple(out)


def targets_with_panel(
    history: Mapping[str, History],
    panel: Panel,
    members: Set[str],
    data_date: date,
    held: frozenset[str],
    params: FundamentalParams,
) -> tuple[Target, ...]:
    """The one definition of this allocator's output. Both paths call it; nothing else does."""
    p = _check_params(params)
    _check_held(held)
    if not trend_on(history, data_date, p):
        return ()
    return targets_from_rows(fundamental_rows(history, panel, members, data_date, p), p)


# --------------------------------------------------------------------------- the allocator


@dataclass(frozen=True, slots=True, eq=False)
class FundamentalPrepared:
    """A history and the panel that goes with it. ``prepare`` supplies ``EMPTY_PANEL``.

    Deliberately thin: ``targets_prepared`` delegates to ``targets_with_panel``, so the prepared
    and single-window results are the same expression and cannot drift apart. The dollar-volume
    window is 20 bars over a few hundred members on a rank session, so there is nothing here
    worth precomputing.
    """

    history: Mapping[str, History] = field(repr=False)
    panel: Panel = field(repr=False)


class FundamentalAllocator:
    """Fundamental cross-sectional factors behind the ``Allocator`` protocol."""

    id = "FND"
    # Defining prepare_market is the whole declaration: it makes this class satisfy phase 6's
    # @runtime_checkable MarketAware protocol structurally, which is what dev.py's prepare_for
    # dispatches on and what the shared lab gate branches on. There is deliberately NO separate
    # `uses_fundamentals` flag -- two sources of truth for "my live path is prepare_market" is
    # one too many, and the protocol is the real one.

    def lookback(self, params: Any) -> int:
        return fundamental_lookback(_check_params(params))

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check_params(params)
        return () if p.trend is None else (p.trend[0],)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check_params(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check_params(params)
        return True

    def targets(
        self,
        history: Mapping[str, History],
        members: Set[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        """The history-only path. With no panel every symbol is ineligible, so this returns ().

        That is the contract, not a degradation, and the shared lab gate asserts it (Step 3).
        """
        return targets_with_panel(history, EMPTY_PANEL, members, data_date, held, _check_params(params))

    def prepare(self, history: Mapping[str, History]) -> FundamentalPrepared:
        return FundamentalPrepared(dict(history), EMPTY_PANEL)

    def prepare_market(self, market: Any) -> FundamentalPrepared:
        """The live path: the market's history plus its point-in-time fundamental panel.

        ``market`` is duck-typed on purpose - this module must not import ``backtest.market``.
        After phase 6 a real ``Market`` always carries a panel: the field defaults to
        ``backtest.market.EMPTY_FUNDAMENTALS``, which **is** the ``EMPTY_PANEL`` imported
        here. So a market built before a store was rebuilt yields that same object and this
        path degrades to exactly the ``prepare`` case, by identity rather than by accident.
        """
        return FundamentalPrepared(dict(market.history), _panel(getattr(market, "fundamentals", None)))

    def targets_prepared(
        self,
        prepared: Any,
        members: Set[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        if not isinstance(prepared, FundamentalPrepared):
            raise TypeError(f"prepared must be FundamentalPrepared, got {type(prepared).__name__}")
        return targets_with_panel(
            prepared.history, prepared.panel, members, data_date, held, _check_params(params)
        )


FUNDAMENTAL = FundamentalAllocator()
```

**Impact:** a new module under `strategies/`; nothing imports it yet except the new lab method
and the new test. `test_strategy_purity.py` picks it up automatically.

---

### Step 2: The lab method

**File:** `engine/src/seer_engine/lab/methods/m0005_fundamental_factors.py` (new)
**Change:** one new method file. `m0005` is the next free number — `lab/methods/` currently
holds `__init__.py`, `m0001_momentum_own_vol_scaling.py` and `m0004_split_cadence_own_vol.py`
(confirmed by listing the directory, not assumed). `METHOD.id` must be `M0005` to match the
filename (`lab/method.py:120`), and `_FAMILY` (`backtest/dev.py:70`) already accepts `M\d{4}`.

Six variants, the `MAX_VARIANTS` cap: the four single-factor rankings the requirement names,
plus the composite under both sizings. Each has a distinct `config_digest` (distinct params).
Every variant uses `MONTHLY_HOLD` and `trend=None`, so `lookback` is 20 for all six — well
inside the smoke market's 473 SPY bars and inside the lab's dev window.

**Code:**

```python
"""M0005 - Point-in-time fundamental factors: value, quality, gross profitability and SUE.

Source: Fama & French (1992), "The cross-section of expected stock returns", Journal of Finance
47(2) (book-to-market); Novy-Marx (2013), "The other side of value: the gross profitability
premium", Journal of Financial Economics 108(1); Bernard & Thomas (1989), "Post-earnings-
announcement drift", Journal of Accounting Research 27 (SUE on a seasonal random walk).

Idea: the lab has only ever ranked on price history. SEC EDGAR gives the four factor families
best documented after momentum, point in time, for free, including for the 133 ever-members
that no longer trade. Each fact's ``filed`` date is the availability boundary, so nothing here
can see a figure before the market could.

The allocator is ``strategies.f_fundamental.FUNDAMENTAL`` (id "FND"). Its live path is
``prepare_market``: fundamentals cannot travel through ``prepare(history)``, and the lab's
config digest forbids carrying bulk data in ``params``. With no panel the allocator targets
nothing, which is the honest reading of "no filing is known".

READ THIS BEFORE RUNNING: ``lab run`` loads the research store. Phase 6 taught the store to
carry a ``fundamentals.csv`` panel, but it is an OPTIONAL file: a store on disk that was built
before that phase, or rebuilt without ``--with-fundamentals``, loads cleanly with an EMPTY
panel and no warning. Running M0005 against such a store records six all-cash trials, freezes
this file's ``source_sha`` and burns the method id for good - ``runner.preflight`` refuses a
second run of any method. So the gate is not "has phase 6 landed" but "has THIS store been
rebuilt with a panel". Check it first::

    python -c "import json,pathlib; print('fundamentals.csv' in json.loads(pathlib.Path('engine/.research/manifest.json').read_text())['files'])"

Do not run ``lab run M0005`` until that prints True. See the phase 7 plan's Handoffs.
"""

from __future__ import annotations

from datetime import date

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.sim.rules import MONTHLY_HOLD
from seer_engine.strategies.f_fundamental import FUNDAMENTAL, FundamentalParams

ADDED = date(2026, 10, 5)

# Every variant: top 20, no trend gate, the shipped liquidity floors. lookback is DV_N = 20.
VALUE = FundamentalParams(rank="value", top=20)
QUALITY = FundamentalParams(rank="quality", top=20)
PROFITABILITY = FundamentalParams(rank="profitability", top=20)
SUE = FundamentalParams(rank="sue", top=20)
COMPOSITE = FundamentalParams(rank="composite", top=20)
COMPOSITE_RANK = FundamentalParams(rank="composite", top=20, sizing="rank")


def _v(suffix: str, params: FundamentalParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0005-{suffix}", family="M0005", rules=MONTHLY_HOLD, allocator=FUNDAMENTAL,
                     params=params, rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0005",
    name="Point-in-time fundamental factors from SEC EDGAR",
    family="stock-fundamental-cross-section",
    source_kind="paper",
    source_ref=(
        "Fama & French (1992), The cross-section of expected stock returns, JF 47(2); "
        "Novy-Marx (2013), The other side of value, JFE 108(1); "
        "Bernard & Thomas (1989), Post-earnings-announcement drift, JAR 27"
    ),
    hypothesis=(
        "Every lab method so far ranks on price alone. The four fundamental factor families with "
        "the longest out-of-sample record - book-to-price, return on equity, gross profitability "
        "and standardized unexpected earnings - are now available point in time from EDGAR, with "
        "each fact gated on its filed date. Ranking the top 20 index members on the equal-weighted "
        "z-score composite of the four, monthly, beats SPY total return over the dev window at a "
        "max drawdown below a price-momentum book's, because the four are weakly correlated with "
        "each other and with momentum."
    ),
    expected_failure=(
        "Large-cap index members are the segment where these premia are weakest: the universe is "
        "already screened for size and liquidity, so the cross-sectional spread in book-to-price "
        "and gross profitability is too narrow to pay for monthly turnover, and every variant "
        "lands within noise of SPY. Or the staleness gate bites: annual filers go more than 400 "
        "days between usable facts, the eligible set collapses below 20 names in parts of the "
        "window, and the book runs half in cash for reasons that have nothing to do with the signal."
    ),
    candidates=(
        _v("VAL", VALUE,
           "Book-to-price alone: equity over filed-dated shares times close, the Fama-French value leg"),
        _v("ROE", QUALITY,
           "Return on equity alone: annual net income over book equity, the quality leg"),
        _v("GP", PROFITABILITY,
           "Gross profitability alone: annual gross profit over assets, Novy-Marx's other side of value"),
        _v("SUE", SUE,
           "SUE alone: the seasonal random walk surprise, post-earnings-announcement drift"),
        _v("ALL", COMPOSITE,
           "Equal-weighted z-score composite of all four, equal position weights"),
        _v("ALL-R", COMPOSITE_RANK,
           "The same composite with linear rank weights: does conviction in the top names pay"),
    ),
    seen_keys=(
        "concept:point-in-time-fundamental-factor-composite",
        "url:https://doi.org/10.1016/j.jfineco.2013.01.003",
    ),
)
```

**Impact:** `lab.method.discover()` now returns three methods. `test_lab_methods.py` runs its
five parametrised gates over M0005 as well — purity, the smoke window, the allocator contract
(Step 3), id uniqueness, and the frozen-file check (which skips M0005: it has no `source_sha`
until it runs).

---

### Step 3: Teach the shared lab gate about a market-aware allocator

**File:** `engine/tests/test_lab_methods.py:85-93`
**Change:** `test_allocator_contract` ends with
`assert nonempty > 0, f"{c.id}: every probe returned no targets, so the contract check proved
nothing"`. `allocatorkit.assert_p4_identity` and `assert_no_lookahead` exercise
`prepare(history)` and `targets(history, …)` only, so a fundamental allocator — whose live path
is `prepare_market` — returns `()` on every probe and trips that assertion.

This is the only shared file this phase touches, and it has no other owner in the set. The
change is deliberately a *tightening*, not a loosening: a `MarketAware` allocator must now
**prove** it targets nothing without a panel. The existing two methods take the unchanged
branch, character for character. The live path is covered in full by `test_f_fundamental.py`
(Step 4), including the same no-look-ahead and prepared-identity properties over a real panel.

The branch keys on **`isinstance(c.allocator, MarketAware)`**, phase 6's runtime-checkable
protocol, not on an invented class attribute (C3). `MarketAware` is the tree's actual contract
for "my live path is `prepare_market`", it is what `dev.py`'s `prepare_for` dispatches on, and
using it here means this gate cannot disagree with the runner about which allocators are
market-aware.

Add `MarketAware` to the module's existing
`from seer_engine.strategies.allocator import Allocator` import, then replace exactly this (the
body after the two `assert_*` calls):

```python
    nonempty = assert_p4_identity(c.allocator, market.history, members, [dates.prev_session(s) for s in probe],
                       held_sets, [c.params])
    nonempty += assert_no_lookahead(c.allocator, market.history, members, probe, held_sets, [c.params])
    assert nonempty > 0, f"{c.id}: every probe returned no targets, so the contract check proved nothing"
```

with:

```python
    nonempty = assert_p4_identity(c.allocator, market.history, members, [dates.prev_session(s) for s in probe],
                       held_sets, [c.params])
    nonempty += assert_no_lookahead(c.allocator, market.history, members, probe, held_sets, [c.params])
    if isinstance(c.allocator, MarketAware):
        # A market-aware allocator reads its panel through prepare_market(market); the kit only
        # drives prepare(history), so by contract it must target nothing here. The checks above
        # still prove the history-only path never crashes and never looks ahead; the live path
        # is covered by the allocator's own test module.
        assert nonempty == 0, f"{c.id}: a market-aware allocator must target nothing with no panel"
        return
    assert nonempty > 0, f"{c.id}: every probe returned no targets, so the contract check proved nothing"
```

**Impact:** `test_allocator_contract[M0005-*]` passes for the right reason. Every other
parametrisation is unaffected.

---

### Step 4: The allocator's own tests

**File:** `engine/tests/test_f_fundamental.py` (new)
**Change:** one new test module, in the style of `test_f_factor.py`: hand-computed features,
eligibility, each ranking, both sizings, the trend gate, the no-bar case, the market-level
prepared identity, no look-ahead on both bars and `filed`, and one end-to-end dev-window run of
every M0005 variant over a synthetic market carrying a synthetic panel.

**Code:**

```python
"""Point-in-time fundamental factors (phase 7; requirement R6).

Hand-computed features, eligibility (including the Gap-A case: filings but no bar), the five
rankings, both sizings, the staleness gate, the market-level prepared identity, no look-ahead
on bars and on ``filed``, and an end-to-end dev-window run of every M0005 variant.
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
NO_FLOOR = {"min_dollar_volume": 0.0, "min_price": 0.0}


# --------------------------------------------------------------------------- a synthetic panel


class FakePanel:
    """A ``Panel`` over plain dicts, with ``filed`` honoured as the availability boundary.

    ``facts[symbol]`` is a list of ``(filed, {metric: value})``. A read at ``data_date`` takes
    the latest entry with ``filed <= data_date``; entries filed later are invisible, which is
    what the no-look-ahead tests exercise.

    It satisfies ``f_fundamental.Panel`` structurally -- one method, ``as_of`` (C1). It is used
    ONLY for the pure functions that take a panel as an argument. The three tests that build a
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

    Market.fundamentals is type-checked (C4), so the three tests that construct a Market use
    this rather than FakePanel. Snapshot.sue is NaN here -- phase 5 computes SUE from a
    quarterly EPS series this synthetic panel does not carry -- so those tests rank on a
    non-SUE factor.
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
    high_dv = FundamentalParams(rank="value", min_price=0.0, min_dollar_volume=1e15)
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
    ("quality", ["CCC", "DDD", "AAA", "BBB"]),        # 0.30, 0.10, 0.20, 0.05 -> CCC DDD AAA BBB
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
    assert "prepare_market" not in Allocator.__protocol_attrs__
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
    docstring and ``test_sue_ranking_*``, which cover the SUE leg over ``FakePanel``.
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
    days = [d for d in session_days(400, date(2014, 1, 2)) if d <= DEV_END]
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
    """
    panel = real_panel({"AAA": [(date(2014, 2, 3), facts(equity=1000.0, assets=5000.0,
                                                         net_income=100.0, shares=200.0,
                                                         gross_profit=300.0, sue=1.0))]})
    snap = panel.as_of("AAA", date(2015, 6, 1))
    assert snap is not None and math.isnan(snap.sue)
    assert fundamental_rows(panel, ("AAA",), date(2015, 6, 1), c.params) == ()
```

**Impact:** a new test module. Three of its tests (`test_prepare_market_carries_the_panel`,
`test_market_identity_prepared_equals_single_window`,
`test_every_sue_free_variant_runs_a_dev_window_with_a_real_panel`) construct `Market(..., fundamentals=)`
and so fail until phase 6 lands — which is correct: this phase declares phase 6 as a dependency
and is implemented on top of it.

**Those three tests must pass a real `FundamentalPanel`, not `FakePanel` (C4).** Build it with a
small helper beside the fixtures:

```python
def real_panel(rows: dict[str, list[tuple[date, dict[str, float]]]]) -> FundamentalPanel:
    """A genuine phase-5 panel from synthetic facts, for the tests that build a Market.

    Phase 6 type-checks Market.fundamentals, so FakePanel is rejected there. Going through
    real Facts is better coverage anyway: it exercises phase 5's point-in-time selection and
    its annual/instant classification rather than a dict lookup.
    """
    out: list[Fact] = []
    for symbol, observations in rows.items():
        for filed, values in observations:
            year_end = date(filed.year - 1, 12, 31)
            out.append(_fact(symbol, "us-gaap", "Assets", "USD", None, year_end,
                             values["assets"], filed))
            out.append(_fact(symbol, "us-gaap", "StockholdersEquity", "USD", None, year_end,
                             values["equity"], filed))
            out.append(_fact(symbol, "dei", "EntityCommonStockSharesOutstanding", "shares",
                             None, year_end, values["shares_outstanding"], filed))
            out.append(_fact(symbol, "us-gaap", "NetIncomeLoss", "USD",
                             date(year_end.year, 1, 1), year_end, values["net_income"], filed))
            out.append(_fact(symbol, "us-gaap", "GrossProfit", "USD",
                             date(year_end.year, 1, 1), year_end, values["gross_profit"], filed))
    return FundamentalPanel.from_facts(tuple(out))
```

with `_fact` a one-line `Fact(...)` constructor filling `accn`, `form`, `fy` and `fp` from the
filed date. **SUE is not synthesisable this way** — phase 5 needs `sue.MIN_QUARTERS` quarters of
diluted EPS before `Snapshot.sue` is finite — so the dev-window test is parametrised over
`SUE_FREE`, computed as `"sue" not in factors_read(c.params)` rather than hand-listed, and the
SUE-ranking variants get their own test asserting they rank nobody and raise nothing. Note that
`rank="composite"` reads **every** factor, SUE included, so the composites are SUE-ranking
variants for this purpose. The split is stated in both docstrings rather than quietly shipping
a variant that ranks on NaN.

---

### Step 5: The runbook

**File:** `docs/runbooks/data-pipeline.md`
**Change:** seven edits. Line numbers are against the file as it stands at `3df1b98`; each edit
gives the exact anchor text so it lands correctly even if an earlier phase shifted the file.

**5a — Architecture, `:14`.** After the sentence ending
`` …in `backfill_log`, so the backfill can resume. `` insert:

```
`fundamentals` loads SEC EDGAR XBRL company facts for every ever-member since 2015-01-02,
resolving each ticker to a CIK through the vendored `engine/data/ticker_cik.csv` (dated, because
tickers are recycled). Facts are stored raw in `fundamental_facts`, keyed including the
accession number so a restatement inserts beside the original rather than overwriting it; the
derived metrics the factors use are computed in pure Python at load time, not in SQL. Each
symbol's outcome goes to `fundamentals_log`, so it resumes exactly as `backfill` does. It needs
no price bars: the 133 ever-members Yahoo no longer serves still have complete filings.
```

**5b — Commands table, after the `nightly --now …` row at `:42`.** Add:

| Command | What it does | Writes |
|---|---|---|
| `… -m seer_engine fundamentals` | SEC EDGAR company facts for every ever-member since 2015-01-02, resolved through `engine/data/ticker_cik.csv` by **(ticker, date)**; the unit of work is the **CIK**, so a share-class pair (GOOG/GOOGL) is one fetch and one log row; skips every CIK already in `fundamentals_log` (any status), so a re-run resumes | `fundamental_facts`, `fundamentals_log`, `ticker_cik` |
| `… fundamentals --symbols AAPL,MSFT` | load specific symbols (comma-separated, dot form); still deduped to CIKs, but ignores `fundamentals_log` | same |
| `… fundamentals --retry-failed` | retry CIKs logged `failed`/`empty` (never touches `ok`) | same |
| `… fundamentals --no-sync-map` | skip mirroring `engine/data/ticker_cik.csv` into the `ticker_cik` table | `fundamental_facts`, `fundamentals_log` |
| `… -m seer_engine research_store --with-fundamentals` | rebuild the research store **with** a `fundamentals.csv` panel read from the database (phase 6). Without the flag the store is built exactly as before and the lab sees an empty panel — see "The lab and fundamentals" below | `engine/.research/` |

**5c — Exit codes table, after the `backfill` row at `:53`.** Add:

| Command | 0 | 1 | 2 |
|---|---|---|---|
| `fundamentals` | no symbol `failed` (`empty` = a filer EDGAR has no XBRL facts for, **or one `ticker_cik.csv` marks `NONE`**, is expected and fine) | some symbol `failed` (SEC 429/5xx after retries, a malformed `companyfacts` payload, **or no CIK for it in `ticker_cik.csv`**); facts already fetched are committed → re-run with `--retry-failed`, or re-vendor the CSV | `SEC_CONTACT_EMAIL` or `DATABASE_URL_UNPOOLED` missing, empty universe (run `universe refresh`), an empty `ticker_cik.csv`, or bad arguments |

**5d — new section, inserted after the Splits section (after `:76`, before the `Tests:` line
at `:78`).**

```markdown
## SEC fundamentals

- SEC's fair-access policy requires a declared `User-Agent` carrying a contact address and caps
  requests at 10/second. The engine reads the address from `SEC_CONTACT_EMAIL` and rate-limits
  from the *end* of the previous call, the way `massive.py` does. `http.py`'s shared session is
  not used, so the contact address never leaks into Massive or Finnhub calls.
- `filed` is the only availability boundary. Every read path exposes the latest fact with
  `filed <= t` and nothing else. A fact's `period_end` is never its availability date: a Q4
  figure for a period ending 2015-12-31 is typically filed in February 2016.
- Restatements are preserved, never overwritten: `accn` is part of a fact's identity, so a
  revised figure inserts beside the original and both stay queryable.
- Gross profit is derived. Only 2 of 8 sampled dead filers tagged `GrossProfit`, so the ladder
  falls back to `Revenues − CostOfRevenue`; the fallback is documented in the derivation
  package's module docstring. Revenue itself has two tag variants (`Revenues`,
  `RevenueFromContractWithCustomerExcludingAssessedTax`).
- Market capitalisation is point-in-time only because the share count is filed-dated
  (`dei:EntityCommonStockSharesOutstanding`) and is multiplied by the close from `bars`. When
  either side is missing the cap is undefined and the value factor drops that name for that day,
  rather than substituting a zero.

### Re-vendoring `engine/data/ticker_cik.csv`

A ticker alone never identifies a company: `CA` is now an Xtrackers ETF, `MON` a SPAC, `PLL`
Piedmont Lithium, `ALTR` Altair, `LLL` JX Luxventure, `DTV` DTE units. Every row therefore
carries a validity interval and the loader rejects overlaps for one ticker. The file is data,
generated once and committed — it is never rebuilt at runtime.

1. Re-vendor as `engine/data/SOURCES.md` describes for this file: the delisted reference gives
   the company name, SEC's `cik-lookup-data.txt` (about 39 MB, from `www.sec.gov`) maps name →
   CIK after stripping corporate suffixes. SEC's `company_tickers.json` resolves **0** of the
   133 delisted names and must not be relied on for them.
2. The automated pass resolved 98 of 133 (94 exact, 4 fuzzy) when it was built. The residue is
   mapped by hand, reviewed, and committed as data.
3. Validate and commit:
   `engine/.venv/bin/pytest engine/tests/test_cik.py -q` (it checks the header, rejects
   overlapping intervals and a CIK that is not 10 digits, and asserts each recycled ticker
   resolves to the company that held it during its membership, not to the current holder).
4. Update the file's sha256 block in `engine/data/SOURCES.md`.
5. Re-run `engine/.venv/bin/python -m seer_engine fundamentals --symbols <the changed tickers>`
   so their facts are reloaded under the corrected CIK.

### The lab and fundamentals

`lab run` loads the research store. `research.load_store` builds its `Market` with a
fundamental panel **only when the store holds a `fundamentals.csv`**, which is an optional
file written by `python -m seer_engine research_store --with-fundamentals`. A store built
before that flag existed, or rebuilt without it, loads cleanly with an **empty** panel and no
warning — that is deliberate (it keeps every store on disk loadable and its fingerprint
unchanged), and it is the trap. Method **M0005**
(`lab/methods/m0005_fundamental_factors.py`) ranks on that panel, so running it against an
empty one would record six all-cash trials, freeze the method file's `source_sha` and burn the
method id permanently (`runner.preflight` refuses a second run of any method).

**Before `lab run M0005`, confirm the store actually has the panel:**

```bash
python -c "import json,pathlib; print('fundamentals.csv' in json.loads(pathlib.Path('engine/.research/manifest.json').read_text())['files'])"
```

If that prints `False`, rebuild first:
`python -m seer_engine research_store --with-fundamentals` (needs `DATABASE_URL_UNPOOLED`, and
needs `python -m seer_engine fundamentals` to have run). **Do not run `lab run M0005` until it
prints `True`.**
```

**5e — Environment table, after the `MASSIVE_API_KEY` row at `:86`.** Add:

| Variable | Used by | Where |
|---|---|---|
| `SEC_CONTACT_EMAIL` | `fundamentals` only | `.env.local` locally; repo secret in Actions |

**5f — Health checks, `:261`.** Replace

```python
    for t in ["bars", "fx_rates", "runs", "universe", "split_adjustments", "backfill_log"]:
```

with

```python
    for t in ["bars", "fx_rates", "runs", "universe", "split_adjustments", "backfill_log",
              "ticker_cik", "fundamental_facts", "fundamentals_log"]:
```

**5g — Rollback (data), `:274`.** Replace

```sql
TRUNCATE bars, fx_rates, universe, split_adjustments, backfill_log;
```

with

```sql
TRUNCATE bars, fx_rates, universe, split_adjustments, backfill_log;
TRUNCATE fundamental_facts, fundamentals_log, ticker_cik;
```

and append to the paragraph below it:

```
Migration `005_fundamentals.sql` is additive too; dropping `fundamental_facts`,
`fundamentals_log` and `ticker_cik` and deleting its `schema_migrations` row reverses it.
```

**Impact:** documentation only.

---

## Verification

**Build:** `engine/.venv/bin/python -c 'import seer_engine.strategies.f_fundamental, seer_engine.lab.methods.m0005_fundamental_factors'`

**Lint:** `engine/.venv/bin/ruff check engine/src/seer_engine/strategies/f_fundamental.py engine/src/seer_engine/lab/methods/m0005_fundamental_factors.py engine/tests/test_f_fundamental.py`
(ruff selects `E9`, `F` only, ignores `F401`.)

**Tests, narrow then wide:**

```bash
cd /home/miftah/.worktrees/seer/edgar-fundamentals
engine/.venv/bin/pytest engine/tests/test_f_fundamental.py -q
engine/.venv/bin/pytest engine/tests/test_lab_methods.py -q
engine/.venv/bin/pytest engine/tests/test_strategy_purity.py engine/tests/test_registry.py -q
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q
```

The full run must stay green with **zero** behaviour change to any existing method or family:
`test_lab_methods.py::test_allocator_contract[M0001-*]` and `[M0004-*]` must still pass through
the unchanged `nonempty > 0` branch.

**Manual checks:**

1. Method discovery and the variant cap:
   ```bash
   engine/.venv/bin/python -c "
   from seer_engine.lab.method import discover
   for mid,(m,_) in discover().items():
       print(mid, len(m.candidates), sorted({c.allocator.id for c in m.candidates}))"
   ```
   Expect `M0001 4 ['M0001']`, `M0004 5 ['M0001']`, `M0005 6 ['FND']`.

2. Allocator-id uniqueness across the registry and every method:
   ```bash
   engine/.venv/bin/python -c "
   from seer_engine.backtest.registry import REGISTRY
   from seer_engine.lab.method import discover
   ids=[str(c.allocator.id) for c in REGISTRY]
   ids+=[str(c.allocator.id) for _,(m,_) in discover().items() for c in m.candidates]
   import collections; print(sorted(set(ids))); print('FND count', ids.count('FND'))"
   ```
   `FND` appears, and `test_allocator_ids_are_unique_across_methods` passes.

3. Every variant's lookback fits both windows:
   ```bash
   engine/.venv/bin/python -c "
   from seer_engine.lab.methods.m0005_fundamental_factors import METHOD
   print({c.id: c.allocator.lookback(c.params) for c in METHOD.candidates})"
   ```
   Every value is 20 — under the smoke market's 473 SPY bars and far under the 200 that would
   push a Neon-bars dev window past `DEV_END`.

4. Runbook renders: `grep -n "fundamentals\|SEC_CONTACT_EMAIL\|ticker_cik" docs/runbooks/data-pipeline.md`
   shows the command rows, the exit-code row, the new section, the env row, the health-check
   list and the rollback lines.

**Exit criteria:**

- [ ] `strategies/f_fundamental.py` exists, is pure (`test_strategy_purity.py` green, unmodified),
      and ranks on value, quality, profitability, SUE and their composite with eligibility rules
      in `f_factor`'s style — a symbol with filings but no bar is absent from the eligible set,
      never a zero, never a crash (`test_a_symbol_with_filings_but_no_bar_is_absent_not_zero`).
- [ ] Allocator id `"FND"` is unique across the registry and every lab method.
- [ ] `lab.method.discover()` returns `M0005` with exactly 6 variants, all distinct digests.
- [ ] Every **SUE-free** M0005 variant runs end to end on a dev window against a market that
      carries a real panel, trades, and ends on `DEV_END`
      (`test_every_sue_free_variant_runs_a_dev_window_with_a_real_panel`). The SUE-ranking
      variants cannot be asserted to trade here and are not: a synthetic annual panel has no
      quarterly EPS series, so `Snapshot.sue` is NaN by construction. They are held to the
      weaker, true criterion instead — they rank nobody and raise nothing
      (`test_a_sue_ranking_variant_on_a_sue_less_panel_ranks_nothing_and_does_not_crash`).
- [ ] `docs/runbooks/data-pipeline.md` documents the `fundamentals` command, its three exit
      codes, `SEC_CONTACT_EMAIL`, and how to re-vendor `engine/data/ticker_cik.csv`.
- [ ] `pytest engine/tests -q` is green with `PG_TEST_URL` set.

---

## Handoffs

**H1 — resolved: phase 6 extends the research store (its Step 7); `lab run M0005` is still
NOT executed here.** The reconciler assigned the research-store work to phase 6, taking
option (a): `research.py` gains a `fundamentals.csv` artifact and passes `fundamentals=` at
`research.py:472`, and `commands/research_store.py` writes the file. Option (b), a
`lab run --fundamentals` flag reading Neon, was rejected: the lab's window opens in 1996 and
Neon's `bars` start in 2015, so a DB-backed lab market would be a different and much shorter
backtest, not the same one with extra data. On the fingerprint worry — `data.fingerprint` is
recorded on each trial row and is not an equality gate; `runner.preflight` keys on `method_id`
and `config_digest`, so **no already-run method is re-run or blocked**.

**The standing rule is unchanged: this phase does not run `lab run M0005`.** The id must be
spent on a run against a research store that has actually been rebuilt with a panel. The
warning stays in the method docstring and in the runbook (5d).

**H2 — resolved: phase 6 owns every `Market` rebuild.** `backtest/dev.py:367` (the FX rebuild,
which fires for any candidate whose window opens before `FX_START` 1999-01-04 — i.e. every lab
candidate reading members from `MEMBERSHIP_START` 1996-01-02) is fixed in phase 6's Step 4 with
`dataclasses.replace(market, fx=…)`, which carries every field it is not asked to change and so
cannot drop a field added later either. Phase 6's Step 8 applies the same fix to
`paper/replay.py:281` and `commands/paper.py:254`. Phase 7's end-to-end test uses a 2014-start
window and does not hit the branch, which is exactly why this needed a phase-6 fix rather than
a phase-7 workaround.

**H3 — the dev window will start in 1996, long before XBRL exists.** Now that H1 is fixed,
`candidate_window` will still open M0005's window at 1996-01-03 (lookback 20 on SPY from
1993-01-29, floored by `MEMBERSHIP_START`), and the allocator will hold cash until the first
filing-backed ranking, around 2010. `lookback` is the only lever `candidate_window` offers and
it cannot be used here: a value large enough to reach 2010 (roughly 4,250 sessions) exceeds the
smoke market's 473 SPY bars and breaks `test_candidate_runs_a_smoke_window` for every variant.
The fix belongs with whoever owns the lab window — a per-candidate `min_start`, or a
data-availability floor on `candidate_window` — not with the allocator. Until then M0005's CAGR
and profit factor will be diluted by roughly fourteen dead years and should not be read as the
signal's verdict.

**H4 — `engine/tests/allocatorkit.py` has no market-aware contract helper.** Phase 7 added the
market-level identity and `filed` no-look-ahead checks inside `test_f_fundamental.py` rather
than generalising the kit, because phase 7 owns neither the kit nor the protocol. When a second
`prepare_market` allocator appears, an `assert_market_contract(allocator, market, …)` belongs in
the kit and these two tests should move into it.

**H5 — `TradeRules` idle instrument.** All six variants use `MONTHLY_HOLD`, so cash earns
nothing. `MONTHLY_HOLD_TBILL` (`sim/rules.py:168`) parks idle cash in `BIL`, which would make
the dilution in H3 less brutal, but it adds `etf:BIL` to `owner_inputs` and BIL's history starts
in 2007. Deliberately left for a follow-up variation method once H1 and H3 are resolved.

**H6 — analyst-consensus surprise stays out.** Decided in the index, re-stated here because it
is the obvious next factor someone will reach for: Finnhub's free tier returns 4 quarters
(measured AAPL 2025-09-30 → 2026-06-30) and cannot be backfilled to the 2015 window. SUE on a
seasonal random walk is the substitute and is what `M0005-SUE` ranks on.

---

## Rollback

This phase is one commit on `feature/edgar-fundamentals`; `git revert` it.

Three of its five files are new and unreferenced by anything outside the phase, so deleting them
is sufficient and safe:

```bash
cd /home/miftah/.worktrees/seer/edgar-fundamentals
git rm engine/src/seer_engine/strategies/f_fundamental.py \
       engine/src/seer_engine/lab/methods/m0005_fundamental_factors.py \
       engine/tests/test_f_fundamental.py
git checkout -- engine/tests/test_lab_methods.py docs/runbooks/data-pipeline.md
engine/.venv/bin/pytest engine/tests -q
```

Nothing else imports `f_fundamental`, no migration is involved, no shipped backtest changes
behaviour (no existing candidate's allocator, params or rules are touched), and the one shared
test edit is a pure addition of a branch that no existing allocator enters. **One caveat:** if
`lab run M0005` has been executed against the lab database, the method row and its trials
survive a code revert and the method id stays spent — see Handoff H1 for why it must not be run
before the research store carries a panel.

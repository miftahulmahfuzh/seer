> Adopted from `PAPER_TRADING_SHIP_PLAN.md` phase 1. Source: `.workflows/plan/paper-trading-ship/phase-1.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 1: Migration 003 and the frozen roster

**Plan set:** `PAPER_TRADING_SHIP_PLAN.md`
**Analysis:** `20261004-082027-P4S7_code_analyzer.md`
**Satisfies:** R2 — migration `003` plus the roster's `strategies` rows, with the frozen spec (D4) defined in code and ready for `paper` to write
**Depends on:** none
**Difficulty:** NORMAL
**Package:** `db/migrations`, `engine/src/seer_engine/paper`

---

## Goal

After this phase the schema has every column and table that paper trading needs (contract C1).
Migrating any database, Neon included, leaves exactly four roster rows in `strategies`, with SPY
as the only champion, and drops B/C when nothing references them.
`seer_engine.paper.roster` is the single pure source of what each roster entry is:
- its display fields, which a test proves equal to the migration's INSERT;
- its engine, its strategy/allocator object, its params and its rules;
- the canonical spec text and the sha256 digest that `paper` (phase 7) writes into `strategies.params` (contract C2), with the digests pinned in a test;
- the `backtest_gate` note;
- the longest history lookback the roster reads.

The demo purge also empties the new paper tables and resets the roster rows' paper clock
(`strategies.paper_start` NULL, `params` `{}`), which the demo seed sets.

## Interface Contract

**Deletes:** nothing in code. As data, migration 003 deletes the `strategies` rows `B` and `C` only when no `orders` or `equity_snapshots` row references them (C1).

**Renames:** the index names the lookback `paper_object_lookback`. In code it is the per-entry field `RosterEntry.lookback` and the module constant `roster.MAX_LOOKBACK_BARS` (an `int`, 253). There is no function by the index's name.

**Creates:**
- `db/migrations/003_paper.sql`. Its SQL is C1 byte for byte, with a 4-line header comment added.
  - It adds the columns `strategies.engine`, `strategies.rules_id`, `strategies.paper_start`, `orders.mark`, `runs.paper_status`, `runs.paper_error` and `runs.paper_finished_at`.
  - It adds the tables `paper_state`, `book_positions`, `book_targets`, `book_fills`, `book_trades` and `dividends`, and the index `book_trades_exit_idx`.
  - It upserts the roster's display rows and runs the guarded B/C delete.
- `seer_engine.paper` (`paper/__init__.py`): a docstring and nothing else, with no re-exports.
- `seer_engine.paper.roster` (`paper/roster.py`, pure):
  - `Engine = Literal["bracket", "book", "benchmark"]`
  - `BENCHMARK_ID = "SPY"`, `F4_ID = "F4-MOM12-N20-TREND"`, `F1_ID = "F1-SPY-SMA200-M"`
  - `@dataclass(frozen=True, slots=True) class RosterEntry`, with these fields:
    - `id`, `name`, `sub`, `icon`, `is_champion`, `is_benchmark`, `sort`, `engine`;
    - `rules: TradeRules | None`;
    - `obj: Strategy | Allocator | None`;
    - `object_name: str`;
    - `params: Any`;
    - `registry_id: str | None`;
    - `lookback: int`;
    - `gate_note: str`;
    - the property `rules_id -> str | None`.
  - `ROSTER: tuple[RosterEntry, ...]`, in `sort` order: SPY, A, F4, F1.
  - `ROSTER_IDS: tuple[str, ...]`
  - `MAX_LOOKBACK_BARS: int` (= 253)
  - `entry(strategy_id) -> RosterEntry`, which raises `KeyError` for an id that is not on the roster.
  - `rules_dict(rules) -> dict[str, str | None]`
  - `spec(e) -> dict[str, Any]`, the C2 `params.spec`.
  - `spec_text(s: Mapping) -> str`: canonical JSON with sorted keys, compact separators and ASCII only.
  - `spec_digest(s: Mapping) -> str`: sha256 hex of `spec_text`.
  - `backtest_gate(e) -> {"passed": False, "note": e.gate_note}`
  - `strategy_params(e) -> {"spec", "digest", "backtest_gate"}`, the whole C2 jsonb.
- `tests/test_paper_roster.py` (new).

**Signature changes:** none. `demo.DEMO_TABLES` keeps its name and type (`tuple[str, ...]`) and gains five tables.

**Behavior change (reconciled):** `demo.purge_demo`, when it purges, also runs `UPDATE strategies SET paper_start = NULL, params = '{}'`. The demo seed (phase 10) writes `paper_start` and `params` on the roster rows; without this reset the first real `paper` run after a purge would meet a started row under a demo digest and refuse (plan index Decisions, "Demo purge vs paper clock").

**C2 as implemented (the reconciler should check phase 7 and phase 10 against this):**
- `spec` keys: `id`, `engine`, `object` (the module-level name: `buy_and_hold`, `STRATEGY_A`, `FACTOR`, `TIMING`), `object_id` (`None`, `"A"`, `"FAC"`, `"F1"`), `registry_id`, `registry_digest` (the registry's own pinned `candidate_digest`, book entries only), `rules_id`, `rules` (every `TradeRules` field as a string), `params` (the object's `as_dict()`; for SPY `{symbol, entry, shares, dividends, cost_rate}`), `initial_idr`.
- Every leaf is a string or null, so a spec read back from jsonb recomputes to the same digest. A test proves it.
- C2's own example has the keys `engine`, `object`, `registry_id`, `rules_id` and `params`. This is a superset of them.
- `backtest_gate` is **not** part of the digest. Its note is a display fact, and correcting the note does not reset a paper clock.
- Pinned digests:
  - SPY `ca309ea7…d4d198`
  - A `37cd89be…68362f`
  - F4 `6c55c13a…b30deb`
  - F1 `e7fbb32d…cad9e2f`

  The full values are in `PINS` in Step 7.

**Requires (from earlier phases):** none.

**Leaves alone (owned by others):**
- `sim/*` (phase 2);
- `paper/bracket.py` and `paper/benchmark.py` (phase 3);
- `paper/book.py` (phase 4);
- `massive.py`, `dividends.py`, `splits.py`, `commands/nightly.py`, `universe.py` (phase 5);
- `paper/store.py` and `backtest/io.py` (phase 6);
- `commands/paper.py`, `runs.py` and `.github/workflows/nightly.yml` (phase 7);
- `paper/replay.py` and `commands/paper_check.py` (phase 8);
- `llm.py` and `commands/explain.py` (phase 9);
- `web/**`, `web/scripts/seed-demo.mjs` included (phases 10–12);
- `engine/package_readme.md`, `docs/**`, `engine/pyproject.toml` and `.github/workflows/engine-ci.yml` (phase 13);
- `backtest/registry.py`, which is a closed record and is read only.

## Files

| File | Action | What changes |
|---|---|---|
| `db/migrations/003_paper.sql` | create | contract C1 verbatim plus a header comment |
| `engine/src/seer_engine/paper/__init__.py` | create | package docstring only |
| `engine/src/seer_engine/paper/roster.py` | create | the four frozen entries, spec/digest/gate, `MAX_LOOKBACK_BARS` |
| `engine/src/seer_engine/demo.py` | modify | docstring (lines 1–6) explains the paper tables, the paper-clock reset and why `dividends` is kept; `DEMO_TABLES` (line 18) gains the five paper state tables; `purge_demo` also resets `strategies.paper_start`/`params` |
| `engine/tests/test_strategy_purity.py` | modify | glob also covers `paper/*.py` except `store.py` (docstring lines 1–10, `IMPURE` line 26, loop line 33, glob test lines 59–68) |
| `engine/tests/test_migrate.py` | modify | `test_repo_has_001_and_002` (line 20) becomes `test_repo_has_001_to_003`; line 26 asserts the new tables; new 003 tests appended after line 72 |
| `engine/tests/test_demo.py` | modify | seed no longer inserts `strategies` (the migration's roster rows conflict with it); seeds the paper tables, one dividend and a demo paper clock on the roster rows; asserts the purge empties them, keeps `strategies` (with `paper_start` NULL and `params` `{}`) and `dividends` |
| `engine/tests/test_paper_roster.py` | create | display fields equal the migration rows; objects and registry identity; pinned digests; C2 shape; jsonb round trip; lookbacks; 550-day window sanity |

## Implementation Steps

### Step 1: Migration 003
**File:** `db/migrations/003_paper.sql` (new)
**Change:** C1 verbatim. The only addition is the 4-line header comment, in the style of 002. The
SQL was trial-run against Postgres 16 in a throwaway schema on top of 001+002 with Neon's old
rows (A champion, B, C, SPY). It works, and running it a second time changes nothing: the
constraint count stays at 50, because `ADD COLUMN IF NOT EXISTS` skips the whole subcommand,
`CHECK` included.
**Code:**
```sql
-- Seer schema v3: nightly paper trading (plan paper-trading-ship, contract C1; handover D2, D4, D6, D8).
-- Additive only: nullable or defaulted columns, new tables and one index, plus two data
-- statements (the roster's display rows, and dropping the unreferenced B/C rows).
-- Written by engine/ (Python); web/ reads the strategies columns and the paper/book tables.

ALTER TABLE strategies ADD COLUMN IF NOT EXISTS engine text CHECK (engine IN ('bracket', 'book', 'benchmark'));
ALTER TABLE strategies ADD COLUMN IF NOT EXISTS rules_id text;         -- 'design-v0', 'monthly-hold', NULL for SPY
ALTER TABLE strategies ADD COLUMN IF NOT EXISTS paper_start date;      -- first paper session; NULL until `paper` starts it

ALTER TABLE orders ADD COLUMN IF NOT EXISTS mark numeric(12,4);        -- open order's last close, in the order's own (pre-split) units

ALTER TABLE runs ADD COLUMN IF NOT EXISTS paper_status text CHECK (paper_status IN ('running', 'success', 'failed'));
ALTER TABLE runs ADD COLUMN IF NOT EXISTS paper_error text;
ALTER TABLE runs ADD COLUMN IF NOT EXISTS paper_finished_at timestamptz;

-- One row per paper strategy (every engine): the state between nights.
CREATE TABLE IF NOT EXISTS paper_state (
  strategy_id       text PRIMARY KEY REFERENCES strategies(id),
  last_session      date NOT NULL,            -- last session stepped; prev_session(paper_start) right after init
  cash_usd          numeric(14,4) NOT NULL,
  equity_usd        numeric(14,4) NOT NULL,   -- equity at last_session's snapshot
  initial_cash_usd  numeric(14,4) NOT NULL,
  usd_idr           numeric(12,4) NOT NULL,   -- the rate initial cash was converted at
  pending_session   date,                     -- session the stored decision is for (next_session(last_session))
  pending_decision  boolean NOT NULL DEFAULT false, -- book: pending_session is a decision session (book_targets may be empty)
  updated_at        timestamptz NOT NULL DEFAULT now()
);

-- Open book positions (book strategies and the SPY benchmark holding). sim.book.Position fields.
CREATE TABLE IF NOT EXISTS book_positions (
  strategy_id   text NOT NULL REFERENCES strategies(id),
  symbol        text NOT NULL,
  shares        numeric(16,4) NOT NULL CHECK (shares > 0),
  mark          numeric(12,4) NOT NULL,
  entry_date    date NOT NULL,
  entry_price   numeric(12,4) NOT NULL,
  days_held     int NOT NULL CHECK (days_held >= 1),
  cost_usd      numeric(14,4) NOT NULL,
  income_usd    numeric(14,4) NOT NULL,
  stop_price    numeric(12,4),
  take_price    numeric(12,4),
  exit_pending  boolean NOT NULL DEFAULT false,
  PRIMARY KEY (strategy_id, symbol)
);

-- A book strategy's decision for one session, ranked (kept after execution as the decision record).
CREATE TABLE IF NOT EXISTS book_targets (
  strategy_id   text NOT NULL REFERENCES strategies(id),
  session_date  date NOT NULL,
  rank          int NOT NULL CHECK (rank >= 1),
  symbol        text NOT NULL,
  weight        numeric(8,6) NOT NULL CHECK (weight > 0 AND weight <= 1),
  last_price    numeric(12,4) NOT NULL,
  limit_price   numeric(12,4),
  stop_price    numeric(12,4),
  take_price    numeric(12,4),
  explanation   text,
  PRIMARY KEY (strategy_id, session_date, symbol),
  UNIQUE (strategy_id, session_date, rank)
);

CREATE TABLE IF NOT EXISTS book_fills (
  id            bigserial PRIMARY KEY,
  strategy_id   text NOT NULL REFERENCES strategies(id),
  session_date  date NOT NULL,
  seq           int NOT NULL,                 -- order within the session, from 1 (sim order: splits, open, trim, buy, intraday, forced)
  symbol        text NOT NULL,
  side          text NOT NULL CHECK (side IN ('buy', 'sell')),
  shares        numeric(16,4) NOT NULL CHECK (shares > 0),
  price         numeric(12,4) NOT NULL,
  cash_usd      numeric(14,4) NOT NULL,
  cost_usd      numeric(14,4) NOT NULL,
  reason        text NOT NULL CHECK (reason IN ('entry', 'add', 'trim', 'signal', 'time', 'gap', 'tp', 'sl', 'forced')),
  UNIQUE (strategy_id, session_date, seq)
);

CREATE TABLE IF NOT EXISTS book_trades (
  id            bigserial PRIMARY KEY,
  strategy_id   text NOT NULL REFERENCES strategies(id),
  symbol        text NOT NULL,
  entry_date    date NOT NULL,
  exit_date     date NOT NULL,
  entry_price   numeric(12,4) NOT NULL,
  exit_price    numeric(12,4) NOT NULL,
  days_held     int NOT NULL,
  cost_usd      numeric(14,4) NOT NULL,
  income_usd    numeric(14,4) NOT NULL,
  pnl_usd       numeric(14,4) NOT NULL,
  exit_reason   text NOT NULL CHECK (exit_reason IN ('signal', 'time', 'gap', 'tp', 'sl', 'forced')),
  idle          boolean NOT NULL DEFAULT false,
  UNIQUE (strategy_id, symbol, entry_date)
);
CREATE INDEX IF NOT EXISTS book_trades_exit_idx ON book_trades (strategy_id, exit_date);

-- Cash dividends by ex-date (Massive types CD + SC, summed per symbol and ex-date).
-- Same units as bars: splits.apply_splits rewrites earlier rows with the bars.
CREATE TABLE IF NOT EXISTS dividends (
  symbol       text NOT NULL,
  ex_date      date NOT NULL,
  amount       numeric(14,6) NOT NULL CHECK (amount > 0),
  recorded_at  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (symbol, ex_date)
);

-- Roster display rows (the frozen spec and paper_start are written by `paper`, phase 7).
-- SPY is the champion; nothing else is (D2).
INSERT INTO strategies (id, name, sub, icon, is_champion, is_benchmark, sort, engine, rules_id) VALUES
  ('SPY', 'SPY', 'S&P 500, buy and hold', 'landmark', true, true, 1, 'benchmark', NULL),
  ('A', 'A · Quant', 'Mean reversion, 5-day brackets', 'sigma', false, false, 2, 'bracket', 'design-v0'),
  ('F4-MOM12-N20-TREND', 'F4 · Momentum', 'Top 20 by 12-1 momentum, monthly', 'trending-up', false, false, 3, 'book', 'monthly-hold'),
  ('F1-SPY-SMA200-M', 'F1 · Trend', 'SPY above its 200-day average, monthly', 'shield', false, false, 4, 'book', 'monthly-hold')
ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, sub = EXCLUDED.sub, icon = EXCLUDED.icon,
  is_champion = EXCLUDED.is_champion, is_benchmark = EXCLUDED.is_benchmark, sort = EXCLUDED.sort,
  engine = EXCLUDED.engine, rules_id = EXCLUDED.rules_id;
-- B and C are not on the roster; drop their rows only when nothing references them.
DELETE FROM strategies s WHERE s.id IN ('B', 'C')
  AND NOT EXISTS (SELECT 1 FROM orders o WHERE o.strategy_id = s.id)
  AND NOT EXISTS (SELECT 1 FROM equity_snapshots e WHERE e.strategy_id = s.id);
```
**Impact:**
- **Every DB test that uses the `pg` fixture now starts with four `strategies` rows**: SPY, A, F4 and F1. `conftest.pg` applies every migration.
- The only existing test that inserted `strategies` rows is `test_demo.py`, which conflicts on `A`/`SPY`, and Step 6 fixes it.
- `test_backtest_command.checksums` includes `strategies`, but it compares before and after the command, so it is unaffected.
- The whole suite was run against the finished phase: 1717 passed, 0 skipped.
- On Neon (phase 13 applies it): A loses the champion flag, SPY becomes `sort 1` champion and benchmark, and B and C are deleted because Neon has 0 `orders` and 0 `equity_snapshots`.
- `web/scripts/seed-demo.mjs` still runs: it truncates `strategies ... CASCADE`, which now also empties the paper tables through their FKs, and inserts its old A/B/C/SPY rows with `engine` NULL. Phase 10 updates the seed.

### Step 2: The `paper` package
**File:** `engine/src/seer_engine/paper/__init__.py` (new)
**Change:** A docstring only. It has no imports, so `import seer_engine.paper` loads nothing and later phases' modules are imported directly.
**Code:**
```python
"""Nightly paper trading (roadmap P4, paper-only; plan paper-trading-ship).

Pure cores (``roster``, ``bracket``, ``book``, ``benchmark``, ``replay``) and the one impure
edge (``store``). Import the submodules directly; this package re-exports nothing.
"""
```
**Impact:** none. The purity test (Step 5) imports it.

### Step 3: The frozen roster
**File:** `engine/src/seer_engine/paper/roster.py` (new)
**Change:** A pure module.
- **The registry is only read.** `_registered` finds the entry by id in `REGISTRY`. It checks that the allocator is the expected object (`FACTOR`, `TIMING`) and that the rules equal `MONTHLY_HOLD`, so a registry surprise fails at import time. It returns `(allocator, params)`.
- **A** uses `STRATEGY_A`, `STRATEGY_A_PARAMS` and `DESIGN_V0`.
- **SPY** has no object or rules. Its spec params state the `buy_and_hold` rules: open entry, whole shares, dividends reinvested, `COST_RATE`.
- **Lookbacks:**
  - A: `STRATEGY_A.lookback` = 200;
  - F4: `FACTOR.lookback(params)` = `factor_lookback` = max(253, 61, 20, 200) = 253;
  - F1: `TIMING.lookback(params)` = 200;
  - SPY: 1.
- **Purity:** the module must not use `.now`, `.today` or `.random`, and must not call `print`, `open` or `input`; the purity test's AST check enforces this. `hashlib` and `json` are allowed.

Every display value below equals the C1 INSERT. Step 7's DB test checks that.
**Code:**
```python
"""The frozen paper roster (handover D1, D2, D4; plan contract C2).

Pure: no database, no clock, no I/O. Four portfolios paper-trade every night from the same
first paper day; this module is the single place that says what each one is.

- ``SPY``: buy-and-hold SPY with dividends reinvested (``backtest.benchmark.buy_and_hold``
  rules), the champion and the yardstick (D2).
- ``A``: Strategy A with ``STRATEGY_A_PARAMS`` under ``DESIGN_V0`` (the bracket engine).
- ``F4-MOM12-N20-TREND`` and ``F1-SPY-SMA200-M``: the P7a registry entries of those ids,
  taken from ``backtest.registry.REGISTRY`` as they are (the registry is read, never edited),
  under their own ``MONTHLY_HOLD`` rules (the book engine).

Each entry's display fields (``name`` .. ``sort``, ``engine``, ``rules_id``) equal the row that
``db/migrations/003_paper.sql`` inserts; ``tests/test_paper_roster.py`` checks that against a
migrated database.

**The frozen spec (D4).** :func:`spec` is the entry's trial-defining parts as a JSON-ready
dict of strings: engine, the strategy/allocator object (module-level name and its ``id``),
the registry id and the registry's own ``candidate_digest`` (book entries), every
``TradeRules`` field, every parameter (``as_dict``), and the starting capital in IDR.
:func:`spec_text` is its canonical text (sorted keys, no whitespace, ASCII) and
:func:`spec_digest` the sha256 hex of that text. Both take a plain mapping, so a spec read
back from ``strategies.params->'spec'`` recomputes to the same digest. The digests are
pinned in ``tests/test_paper_roster.py``: a changed strategy needs a **new id** with its own
paper clock, never an edited entry (``paper`` refuses a started id whose stored digest
differs).

``backtest_gate`` is a display fact for the go-live checklist (D12), not part of the spec:
correcting its note does not reset a paper clock. Every entry is ``passed: false`` today.

:data:`MAX_LOOKBACK_BARS` is the most bars through a data date any roster object reads
(FACTOR's ``factor_lookback`` = 253); the paper store's windowed history load must cover it.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, fields
from decimal import Decimal
from typing import Any, Literal

from seer_engine.backtest.registry import REGISTRY, candidate_digest
from seer_engine.backtest.runner import INITIAL_IDR
from seer_engine.sim import COST_RATE
from seer_engine.sim.rules import DESIGN_V0, MONTHLY_HOLD, TradeRules
from seer_engine.strategies.a import STRATEGY_A, STRATEGY_A_PARAMS
from seer_engine.strategies.allocator import Allocator
from seer_engine.strategies.base import Strategy
from seer_engine.strategies.f_factor import FACTOR
from seer_engine.strategies.f_index import TIMING

Engine = Literal["bracket", "book", "benchmark"]

BENCHMARK_ID = "SPY"
F4_ID = "F4-MOM12-N20-TREND"
F1_ID = "F1-SPY-SMA200-M"


@dataclass(frozen=True, slots=True)
class RosterEntry:
    """One paper portfolio.

    ``obj`` is the ``Strategy`` (bracket), the ``Allocator`` (book) or ``None`` (benchmark);
    ``object_name`` is its module-level name (``STRATEGY_A``, ``FACTOR``, ``TIMING``) or
    ``buy_and_hold`` for the benchmark. ``rules`` is ``None`` only for the benchmark.
    ``lookback`` is the bars through a data date ``obj`` reads (1 for the benchmark, which
    reads only the session's own bar).
    """

    id: str
    name: str
    sub: str
    icon: str
    is_champion: bool
    is_benchmark: bool
    sort: int
    engine: Engine
    rules: TradeRules | None
    obj: Strategy | Allocator | None
    object_name: str
    params: Any
    registry_id: str | None
    lookback: int
    gate_note: str

    @property
    def rules_id(self) -> str | None:
        """``strategies.rules_id``: the rules preset id, ``None`` for the benchmark."""
        return None if self.rules is None else self.rules.id


def _registered(registry_id: str, expected_obj: Allocator, rules: TradeRules) -> tuple[Allocator, Any]:
    """(allocator, params) of the registry entry ``registry_id``, checked against what the
    roster expects (the registry is a closed record; a mismatch is a programming error)."""
    found = [c for c in REGISTRY if c.id == registry_id]
    if len(found) != 1:
        raise LookupError(f"registry has {len(found)} entries with id {registry_id!r}, expected 1")
    c = found[0]
    if c.allocator is not expected_obj:
        raise LookupError(f"{registry_id}: registry allocator is <{c.allocator.id}>, expected <{expected_obj.id}>")
    if c.rules != rules:
        raise LookupError(f"{registry_id}: registry rules are {c.rules.id!r}, expected {rules.id!r}")
    return c.allocator, c.params


_F4_OBJ, _F4_PARAMS = _registered(F4_ID, FACTOR, MONTHLY_HOLD)
_F1_OBJ, _F1_PARAMS = _registered(F1_ID, TIMING, MONTHLY_HOLD)

# Sorted by ``sort``; every value is the 003 migration's INSERT row for the same id.
ROSTER: tuple[RosterEntry, ...] = (
    RosterEntry(
        id=BENCHMARK_ID,
        name="SPY",
        sub="S&P 500, buy and hold",
        icon="landmark",
        is_champion=True,
        is_benchmark=True,
        sort=1,
        engine="benchmark",
        rules=None,
        obj=None,
        object_name="buy_and_hold",
        params=None,
        registry_id=None,
        lookback=1,
        gate_note="Benchmark, not a strategy: it has no backtest gate and is never a Seer pick",
    ),
    RosterEntry(
        id="A",
        name="A · Quant",
        sub="Mean reversion, 5-day brackets",
        icon="sigma",
        is_champion=False,
        is_benchmark=False,
        sort=2,
        engine="bracket",
        rules=DESIGN_V0,
        obj=STRATEGY_A,
        object_name="STRATEGY_A",
        params=STRATEGY_A_PARAMS,
        registry_id=None,
        lookback=STRATEGY_A.lookback,
        gate_note=(
            "P3 gate failed out of sample (2022-01-03..2026-10-02): -15.0% vs SPY TR +71.9%, "
            "PF 0.92, max DD 33.3%"
        ),
    ),
    RosterEntry(
        id=F4_ID,
        name="F4 · Momentum",
        sub="Top 20 by 12-1 momentum, monthly",
        icon="trending-up",
        is_champion=False,
        is_benchmark=False,
        sort=3,
        engine="book",
        rules=MONTHLY_HOLD,
        obj=_F4_OBJ,
        object_name="FACTOR",
        params=_F4_PARAMS,
        registry_id=F4_ID,
        lookback=_F4_OBJ.lookback(_F4_PARAMS),
        gate_note="P7a dev window only; failed max DD <= 15% (22.2%)",
    ),
    RosterEntry(
        id=F1_ID,
        name="F1 · Trend",
        sub="SPY above its 200-day average, monthly",
        icon="shield",
        is_champion=False,
        is_benchmark=False,
        sort=4,
        engine="book",
        rules=MONTHLY_HOLD,
        obj=_F1_OBJ,
        object_name="TIMING",
        params=_F1_PARAMS,
        registry_id=F1_ID,
        lookback=_F1_OBJ.lookback(_F1_PARAMS),
        gate_note="P7a dev window only; failed max DD <= 15% (18.7%) and >= 100 trades (11)",
    ),
)

ROSTER_IDS: tuple[str, ...] = tuple(e.id for e in ROSTER)

MAX_LOOKBACK_BARS: int = max(e.lookback for e in ROSTER)


def entry(strategy_id: str) -> RosterEntry:
    """The roster entry ``strategy_id``; ``KeyError`` when it is not on the roster."""
    for e in ROSTER:
        if e.id == strategy_id:
            return e
    raise KeyError(f"{strategy_id!r} is not on the paper roster {ROSTER_IDS}")


def _rule_value(value: object) -> str | None:
    """One ``TradeRules`` field as a plain string (``None`` stays ``None``)."""
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, str, Decimal)):
        return str(value)
    raise TypeError(f"no spec text for a {type(value).__name__}: {value!r}")


def rules_dict(rules: TradeRules) -> dict[str, str | None]:
    """Every ``TradeRules`` field, in field order, as plain strings."""
    return {f.name: _rule_value(getattr(rules, f.name)) for f in fields(rules)}


def spec(e: RosterEntry) -> dict[str, Any]:
    """The frozen spec of ``e`` (contract C2 ``params.spec``): JSON-ready, strings and nulls only."""
    if e.engine == "benchmark":
        params: dict[str, str] = {
            "symbol": BENCHMARK_ID,
            "entry": "open",
            "shares": "whole",
            "dividends": "reinvest",
            "cost_rate": str(COST_RATE),
        }
        object_id = None
    else:
        params = dict(e.params.as_dict())
        object_id = e.obj.id
    registry_digest = None
    if e.registry_id is not None:
        registry_digest = candidate_digest(next(c for c in REGISTRY if c.id == e.registry_id))
    return {
        "id": e.id,
        "engine": e.engine,
        "object": e.object_name,
        "object_id": object_id,
        "registry_id": e.registry_id,
        "registry_digest": registry_digest,
        "rules_id": e.rules_id,
        "rules": None if e.rules is None else rules_dict(e.rules),
        "params": params,
        "initial_idr": str(INITIAL_IDR),
    }


def spec_text(s: Mapping[str, Any]) -> str:
    """The canonical text of a spec: JSON with sorted keys, no whitespace, ASCII only."""
    return json.dumps(s, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def spec_digest(s: Mapping[str, Any]) -> str:
    """sha256 (hex) of ``spec_text(s)`` in UTF-8."""
    return hashlib.sha256(spec_text(s).encode("utf-8")).hexdigest()


def backtest_gate(e: RosterEntry) -> dict[str, Any]:
    """Contract C2 ``params.backtest_gate``: no roster entry has passed a backtest gate."""
    return {"passed": False, "note": e.gate_note}


def strategy_params(e: RosterEntry) -> dict[str, Any]:
    """The whole ``strategies.params`` jsonb for ``e`` (contract C2), as ``paper`` writes it."""
    s = spec(e)
    return {"spec": s, "digest": spec_digest(s), "backtest_gate": backtest_gate(e)}
```
**Impact:** new module only. It imports `backtest.registry`, `backtest.runner`, `sim`, `sim.rules` and `strategies.*`, all of which are already covered by the purity tests. It edits nothing in them.

### Step 4: Demo purge covers the paper tables; `dividends` stays
**File:** `engine/src/seer_engine/demo.py:1-6` (docstring) and `:18` (`DEMO_TABLES`)
**Change:**
- **Paper state tables.** The five tables are demo-owned. The demo seed (phase 10) writes paper state, and real paper state never coexists with a demo run, because `paper` runs only after `nightly`, which purges first.
- **Paper clock on `strategies`.** The demo seed also writes `strategies.paper_start` and `params` (a demo spec with `digest: null`). The rows themselves are kept (orders reference them), but when the purge runs it resets those two columns with `UPDATE strategies SET paper_start = NULL, params = '{}'`, so the first real `paper` run starts the clock instead of refusing a foreign digest. Safe: a demo run never coexists with real paper state.
- **`dividends` is deliberately not in `DEMO_TABLES`.**
  - It is real data. Its rows are Massive facts keyed by (symbol, ex-date), fetched only for the sessions `nightly` is missing.
  - A purge would lose ex-dates for good, and the D7 replay could no longer reproduce a credit.
  - The demo seed never writes it, and `splits.apply_splits` (phase 5) rewrites it in step with the bars.

`TRUNCATE ... RESTART IDENTITY` over the longer list works because the only FKs out of the new tables point at `strategies`, which is not truncated. `RESTART IDENTITY` also resets the `book_fills` and `book_trades` sequences.
**Code:** the whole file after the change:
```python
"""Removal of the demo rows seeded by web/scripts/seed-demo.mjs.

Demo bars and FX rows are indistinguishable from real ones, so the trigger is the
existence of a demo run: while one exists, every row in the demo-owned tables is demo
data. ``strategies`` is kept because orders reference it and later phases reuse it.

The paper tables of migration 003 (``paper_state`` and the ``book_*`` tables) are
demo-owned too: the demo seed writes paper state, and real paper state never coexists with
a demo run (``paper`` runs only after ``nightly``, which purges first). The seed also sets
the roster rows' paper clock (``strategies.paper_start`` and ``params``); the purge keeps
the rows but resets those two columns, so the first real ``paper`` run starts cleanly.

``dividends`` is **not** demo-owned. Its rows are Massive facts keyed by (symbol,
ex-date), fetched only for the sessions ``nightly`` is missing, so a purge would lose
ex-dates for good and the replay check (D7) could no longer reproduce a dividend credit.
The demo seed never writes it, and ``splits.apply_splits`` rewrites it in step with the
bars, so a kept row never disagrees with them.
"""

from __future__ import annotations

import logging

import psycopg

from seer_engine import db

log = logging.getLogger(__name__)

DEMO_TABLES = (
    "action_dismissals",
    "orders",
    "equity_snapshots",
    "paper_state",
    "book_positions",
    "book_targets",
    "book_fills",
    "book_trades",
    "bars",
    "fx_rates",
    "runs",
)

# The demo seed sets the roster rows' paper clock; a purge resets it (the rows themselves stay).
RESET_PAPER_CLOCK = "paper_start = NULL, params = '{}'::jsonb"


def has_demo(conn: psycopg.Connection) -> bool:
    """True when any ``runs`` row is a demo run."""
    row = conn.execute("SELECT EXISTS (SELECT 1 FROM runs WHERE is_demo)").fetchone()
    return bool(row[0])


def purge_demo(conn: psycopg.Connection) -> bool:
    """Empty every demo-owned table when a demo run exists. Returns True when it purged.

    Does not commit: the caller's transaction makes it atomic.
    """
    if not has_demo(conn):
        return False
    conn.execute(f"TRUNCATE {', '.join(DEMO_TABLES)} RESTART IDENTITY")
    conn.execute(f"UPDATE strategies SET {RESET_PAPER_CLOCK}")
    log.warning("demo data found: truncated %s; reset strategies.paper_start/params", ", ".join(DEMO_TABLES))
    return True


def purge_demo_if_needed(conn: psycopg.Connection, dry_run: bool) -> bool:
    """purge_demo() in its own transaction, before a command's first real write.

    Under ``dry_run`` the purge runs and is rolled back; the return value still says
    whether it would have purged.
    """
    with db.transaction(conn, dry_run):
        purged = purge_demo(conn)
    if purged and dry_run:
        log.warning("dry-run: would purge demo data (%s)", ", ".join(DEMO_TABLES))
    return purged
```
**Impact:**
- `nightly`'s demo purge now also empties the five paper tables.
- `paper` (phase 7) inherits that if it calls `purge_demo_if_needed`, which is phase 7's choice.
- `strategies` rows are still kept, but their `paper_start` and `params` are reset to NULL / `{}` (the demo seed's paper clock).

### Step 5: Purity coverage for `paper/*.py` except `store.py`
**File:** `engine/tests/test_strategy_purity.py:1-10` (docstring), `:26` (`IMPURE`), `:33` (package loop), `:59-68` (glob test)
**Change:**
- Add `"paper"` to the globbed packages and `("paper", "store.py")` to `IMPURE`.
- Assert that the glob finds `seer_engine.paper` and `seer_engine.paper.roster` and never `seer_engine.paper.store`.

`store.py` does not exist yet, so its `IMPURE` entry has no effect until phase 6 creates it. `bracket.py`, `book.py`, `benchmark.py` and `replay.py` (phases 3, 4 and 8) are covered automatically when they land.
**Code:** the whole file after the change:
```python
"""Strategy, backtest and paper core modules are pure (handover §6.8, plan invariant 2;
paper-trading-ship invariant 4).

Globs ``seer_engine/strategies/*.py``, ``seer_engine/backtest/*.py`` and
``seer_engine/paper/*.py`` (every module except the impure edges ``backtest/io.py`` and
``paper/store.py``), so modules added later are covered without editing this file.

- Importing them in a fresh interpreter loads no psycopg, requests or yfinance, and never
  seer_engine.bars (which imports psycopg).
- Their source never reads the clock, draws random numbers, logs, prints or opens files.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import seer_engine

FORBIDDEN_MODULES = ("psycopg", "requests", "yfinance", "seer_engine.bars")
FORBIDDEN_IMPORT_ROOTS = {"psycopg", "requests", "yfinance", "time", "random", "logging", "urllib", "socket"}
FORBIDDEN_ATTRS = {"now", "utcnow", "today", "fromtimestamp", "random"}  # "random" catches numpy.random
FORBIDDEN_CALLS = {"print", "open", "input"}
IMPURE = {("backtest", "io.py"), ("paper", "store.py")}

PKG = Path(seer_engine.__file__).resolve().parent


def _pure_sources() -> list[Path]:
    files = []
    for package in ("strategies", "backtest", "paper"):
        files += [p for p in sorted((PKG / package).glob("*.py")) if (package, p.name) not in IMPURE]
    return files


def _module_name(path: Path) -> str:
    parts = ["seer_engine", path.parent.name]
    if path.stem != "__init__":
        parts.append(path.stem)
    return ".".join(parts)


def _fresh_python(code: str) -> str:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(PKG.parent) + os.pathsep + env.get("PYTHONPATH", "")
    out = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env=env,
        check=True,
        timeout=120,
    )
    return out.stdout.strip()


def test_the_glob_finds_the_strategy_modules():
    names = {_module_name(p) for p in _pure_sources()}
    assert {
        "seer_engine.strategies",
        "seer_engine.strategies.base",
        "seer_engine.strategies.indicators",
        "seer_engine.strategies.a",
        "seer_engine.backtest",
        "seer_engine.paper",
        "seer_engine.paper.roster",
    } <= names
    assert "seer_engine.backtest.io" not in names
    assert "seer_engine.paper.store" not in names


def test_pure_modules_load_no_db_or_network_module():
    modules = sorted(_module_name(p) for p in _pure_sources())
    code = (
        "import importlib, sys\n"
        f"for m in {modules!r}:\n"
        "    importlib.import_module(m)\n"
        f"bad = [m for m in {FORBIDDEN_MODULES!r} if m in sys.modules]\n"
        "print(','.join(bad))\n"
    )
    assert _fresh_python(code) == ""


def test_pure_sources_have_no_clock_randomness_or_io():
    problems: list[str] = []
    for path in _pure_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            where = f"{path.parent.name}/{path.name}:{getattr(node, 'lineno', '?')}"
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root in FORBIDDEN_IMPORT_ROOTS or alias.name == "seer_engine.bars":
                        problems.append(f"{where} import {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                root = node.module.split(".")[0]
                if root in FORBIDDEN_IMPORT_ROOTS or node.module == "seer_engine.bars":
                    problems.append(f"{where} from {node.module} import ...")
                if node.module == "seer_engine" and any(a.name == "bars" for a in node.names):
                    problems.append(f"{where} from seer_engine import bars")
            elif isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_ATTRS:
                problems.append(f"{where} .{node.attr}")
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
                problems.append(f"{where} {node.func.id}()")
    assert problems == []
```
**Impact:**
- From phase 3 onward, any `paper/*.py` other than `store.py` that imports psycopg, requests, yfinance, `logging`, `time` or `random`, or that calls `.now()`, `.today()` or `print`, fails this test.
- Phases 3, 4 and 8 must honor this. They already do under invariant 4.

### Step 6: Demo purge tests in the new shape
**File:** `engine/tests/test_demo.py` (whole file; old lines 15–39 `_seed`, 42–46 `_counts`, 49–56 and 75–81 strategy counts)
**Change:**
- `_seed` no longer inserts `strategies`. The `pg` fixture's migration 003 already inserted the roster, and the old `('A', …), ('SPY', …)` insert would now raise `UniqueViolation`.
- `_seed` adds one row to each paper table (for F4) and one `dividends` row.
- The tests assert:
  - the purge empties all `DEMO_TABLES`, the paper tables included;
  - `strategies` keeps `len(ROSTER)` rows, with `paper_start` NULL and `params` `{}` after a purge (and untouched without a demo run, under dry-run, or after a rollback);
  - `dividends` keeps its row;
  - `RESTART IDENTITY` resets `book_fills.id`;
  - `DEMO_TABLES` contains the five paper tables and not `dividends` or `strategies`.
**Code:**
```python
"""Demo purge: all-or-nothing, keyed on the existence of a demo run, strategies and dividends kept."""

from __future__ import annotations

from datetime import date

import psycopg

from seer_engine.demo import DEMO_TABLES, has_demo, purge_demo, purge_demo_if_needed
from seer_engine.paper.roster import ROSTER

D = date(2026, 10, 2)
S = date(2026, 10, 5)
F4 = "F4-MOM12-N20-TREND"
PAPER_TABLES = ("paper_state", "book_positions", "book_targets", "book_fills", "book_trades")


def _seed(conn, *, demo: bool) -> None:
    """A slice of what web/scripts/seed-demo.mjs writes, plus one real dividend.

    The roster's ``strategies`` rows come from migration 003 (the ``pg`` fixture applies it).
    """
    conn.execute(
        "INSERT INTO runs (status, data_date, session_date, is_demo, finished_at) "
        "VALUES ('success', %s, %s, %s, now())",
        (D, S, demo),
    )
    conn.execute("INSERT INTO fx_rates (date, usd_idr) VALUES (%s, 16530)", (D,))
    conn.execute("INSERT INTO bars VALUES ('NVDA', %s, 180, 180, 180, 180, 1000000)", (D,))
    order_id = conn.execute(
        "INSERT INTO orders (strategy_id, session_date, slot, symbol, company, last_price, "
        "limit_price, tp_price, sl_price, shares, status) "
        "VALUES ('A', %s, 1, 'NVDA', 'NVIDIA', 180, 178, 185, 172, 10, 'pending') RETURNING id",
        (S,),
    ).fetchone()[0]
    conn.execute("INSERT INTO action_dismissals (order_id) VALUES (%s)", (order_id,))
    conn.execute(
        "INSERT INTO equity_snapshots (strategy_id, date, cash_usd, equity_usd) VALUES ('A', %s, 1000, 1000)",
        (D,),
    )
    conn.execute(
        "INSERT INTO paper_state (strategy_id, last_session, cash_usd, equity_usd, initial_cash_usd, "
        "usd_idr, pending_session, pending_decision) VALUES (%s, %s, 1000, 1000, 1000, 16530, %s, true)",
        (F4, D, S),
    )
    conn.execute(
        "INSERT INTO book_positions (strategy_id, symbol, shares, mark, entry_date, entry_price, "
        "days_held, cost_usd, income_usd) VALUES (%s, 'NVDA', 5, 180, %s, 178, 1, 0.89, 0)",
        (F4, D),
    )
    conn.execute(
        "INSERT INTO book_targets (strategy_id, session_date, rank, symbol, weight, last_price) "
        "VALUES (%s, %s, 1, 'NVDA', 0.05, 180)",
        (F4, S),
    )
    conn.execute(
        "INSERT INTO book_fills (strategy_id, session_date, seq, symbol, side, shares, price, "
        "cash_usd, cost_usd, reason) VALUES (%s, %s, 1, 'NVDA', 'buy', 5, 178, 890.89, 0.89, 'entry')",
        (F4, D),
    )
    conn.execute(
        "INSERT INTO book_trades (strategy_id, symbol, entry_date, exit_date, entry_price, exit_price, "
        "days_held, cost_usd, income_usd, pnl_usd, exit_reason) "
        "VALUES (%s, 'AAPL', %s, %s, 200, 210, 20, 0.41, 0, 9.59, 'signal')",
        (F4, date(2026, 9, 1), D),
    )
    conn.execute("INSERT INTO dividends (symbol, ex_date, amount) VALUES ('SPY', %s, 1.888834)", (D,))
    # The demo seed's paper clock on the roster rows (web/scripts/seed-demo.mjs writes both columns).
    conn.execute(
        "UPDATE strategies SET paper_start = %s, params = '{\"demo\": true, \"digest\": null}'::jsonb", (S,)
    )
    conn.commit()


def _clock(conn) -> list[tuple]:
    return [tuple(r) for r in conn.execute("SELECT paper_start, params FROM strategies ORDER BY id").fetchall()]


def _counts(conn) -> dict[str, int]:
    return {
        t: conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        for t in (*DEMO_TABLES, "strategies", "dividends")
    }


def test_demo_tables_cover_the_paper_tables_and_not_dividends():
    assert set(PAPER_TABLES) <= set(DEMO_TABLES)
    assert "dividends" not in DEMO_TABLES
    assert "strategies" not in DEMO_TABLES
    assert len(set(DEMO_TABLES)) == len(DEMO_TABLES)


def test_purge_empties_demo_tables_and_keeps_strategies_and_dividends(pg):
    _seed(pg, demo=True)
    assert all(_counts(pg)[t] >= 1 for t in DEMO_TABLES)
    assert has_demo(pg)
    assert purge_demo(pg) is True
    pg.commit()
    counts = _counts(pg)
    assert all(counts[t] == 0 for t in DEMO_TABLES)
    assert counts["strategies"] == len(ROSTER)
    assert counts["dividends"] == 1
    assert _clock(pg) == [(None, {})] * len(ROSTER)  # the demo paper clock is reset, the rows stay


def test_purge_restarts_identity(pg):
    _seed(pg, demo=True)
    purge_demo(pg)
    new_id = pg.execute(
        "INSERT INTO runs (status, is_demo) VALUES ('running', false) RETURNING id"
    ).fetchone()[0]
    assert new_id == 1
    fill_id = pg.execute(
        "INSERT INTO book_fills (strategy_id, session_date, seq, symbol, side, shares, price, "
        "cash_usd, cost_usd, reason) VALUES (%s, %s, 1, 'NVDA', 'buy', 1, 178, 178.18, 0.18, 'entry') "
        "RETURNING id",
        (F4, S),
    ).fetchone()[0]
    assert fill_id == 1


def test_no_demo_run_is_a_no_op(pg):
    _seed(pg, demo=False)
    before = (_counts(pg), _clock(pg))
    assert purge_demo(pg) is False
    assert (_counts(pg), _clock(pg)) == before


def test_purge_if_needed_commits_in_its_own_transaction(pg, pg_schema):
    _seed(pg, demo=True)
    assert purge_demo_if_needed(pg, dry_run=False) is True
    with psycopg.connect(pg_schema.url) as other:
        assert other.execute("SELECT count(*) FROM runs").fetchone()[0] == 0
        assert other.execute("SELECT count(*) FROM paper_state").fetchone()[0] == 0
        assert other.execute("SELECT count(*) FROM strategies").fetchone()[0] == len(ROSTER)
        assert other.execute("SELECT count(*) FROM dividends").fetchone()[0] == 1
        assert other.execute("SELECT count(*) FROM strategies WHERE paper_start IS NOT NULL").fetchone()[0] == 0
    assert purge_demo_if_needed(pg, dry_run=False) is False


def test_purge_if_needed_dry_run_keeps_everything(pg):
    _seed(pg, demo=True)
    before = (_counts(pg), _clock(pg))
    assert purge_demo_if_needed(pg, dry_run=True) is True
    assert (_counts(pg), _clock(pg)) == before


def test_purge_is_atomic_with_the_callers_transaction(pg):
    _seed(pg, demo=True)
    before = (_counts(pg), _clock(pg))
    purge_demo(pg)
    pg.rollback()
    assert (_counts(pg), _clock(pg)) == before
```
**Impact:** test-only.

### Step 7: The roster test
**File:** `engine/tests/test_paper_roster.py` (new)
**Change:**
- **Display rows:** they equal a migrated database's rows. This proves the migration and the roster agree.
- **Identities:** the object, params and rules are the expected ones, and the book entries are the registry's entries unchanged (`is` the allocator, equal params and rules, `registry_digest == candidate_digest(c)`).
- **Pinned digests:** a failing pin means a roster strategy changed, and the fix is a new id, not a new pin.
- **Canonical spec:** key order does not change the text, a JSON round trip keeps the digest, and the text is ASCII.
- **Digest sensitivity:** changing one parameter changes the digest.
- **C2 shape:** checked, plus a `Jsonb` round trip through `strategies.params` that recomputes the digest.
- **Lookbacks:** pinned; `MAX_LOOKBACK_BARS == 253`.
- **History window:** the plan's 550-calendar-day history window holds at least `MAX_LOOKBACK_BARS` sessions for every data date from 2026-10 to 2027-12. The minimum measured was 376.
**Code:**
```python
"""The frozen paper roster (handover D1, D2, D4; plan contract C2).

- The display fields equal the rows migration 003 inserts.
- Every entry is the object, params and rules the handover names; book entries are the
  registry's entries unchanged.
- The spec digests are pinned. A failing pin means a roster strategy changed: give it a NEW
  id (its own paper clock) instead of editing the pin.
"""

from __future__ import annotations

import json
from datetime import date, timedelta

import pytest
from psycopg.types.json import Jsonb

from seer_engine import dates
from seer_engine.backtest.registry import REGISTRY, candidate_digest
from seer_engine.paper.roster import (
    BENCHMARK_ID,
    MAX_LOOKBACK_BARS,
    ROSTER,
    ROSTER_IDS,
    backtest_gate,
    entry,
    rules_dict,
    spec,
    spec_digest,
    spec_text,
    strategy_params,
)
from seer_engine.sim.rules import DESIGN_V0, MONTHLY_HOLD
from seer_engine.strategies.a import STRATEGY_A, STRATEGY_A_PARAMS
from seer_engine.strategies.f_factor import FACTOR
from seer_engine.strategies.f_index import TIMING

F4 = "F4-MOM12-N20-TREND"
F1 = "F1-SPY-SMA200-M"

PINS = {
    "SPY": "ca309ea7f19d0b771f236c63309a2fcf28a82e16048528d738dc329a42d4d198",
    "A": "37cd89be4b4c82f9dc2d4f3bdd69551a7d31aef83119f23ee757f8ec6568362f",
    F4: "6c55c13acc487a6fccbe2c5c0eb91a36e39f3a5444555a0dbfba4ffba5b30deb",
    F1: "e7fbb32d1cc4e11b2d0d9b941ab01ac1a545e49a08c11bf8c70da5c54cad9e2f",
}

FACTOR_PARAMS_AS_DICT = {
    "rank": "momentum",
    "top": "20",
    "mom_n": "252",
    "mom_skip": "21",
    "vol_n": "60",
    "pool": "50",
    "sizing": "equal",
    "min_dollar_volume": "20000000",
    "min_price": "5",
    "trend": "SPY:200",
}


DISPLAY = ("id", "name", "sub", "icon", "is_champion", "is_benchmark", "sort", "engine", "rules_id")


def test_the_roster_is_the_four_handover_entries_in_sort_order():
    assert ROSTER_IDS == ("SPY", "A", F4, F1)
    assert [e.sort for e in ROSTER] == [1, 2, 3, 4]
    assert "B" not in ROSTER_IDS and "C" not in ROSTER_IDS


def test_spy_is_the_only_champion_and_the_only_benchmark():
    assert [e.id for e in ROSTER if e.is_champion] == [BENCHMARK_ID]
    assert [e.id for e in ROSTER if e.is_benchmark] == [BENCHMARK_ID]


def test_display_fields_equal_the_migration_rows(pg):
    rows = pg.execute(f"SELECT {', '.join(DISPLAY)} FROM strategies ORDER BY sort").fetchall()
    assert rows == [tuple(getattr(e, f) for f in DISPLAY) for e in ROSTER]


def test_each_entry_is_the_named_object_params_and_rules():
    spy, a, f4, f1 = (entry(i) for i in ROSTER_IDS)
    assert (spy.engine, spy.obj, spy.rules, spy.rules_id, spy.params) == ("benchmark", None, None, None, None)
    assert a.engine == "bracket"
    assert a.obj is STRATEGY_A and a.params is STRATEGY_A_PARAMS and a.rules is DESIGN_V0
    assert a.registry_id is None
    assert f4.engine == "book" and f4.obj is FACTOR and f4.rules == MONTHLY_HOLD
    assert f1.engine == "book" and f1.obj is TIMING and f1.rules == MONTHLY_HOLD
    assert (f4.registry_id, f1.registry_id) == (F4, F1)


def test_book_entries_are_the_registry_entries_unchanged():
    by_id = {c.id: c for c in REGISTRY}
    for e in ROSTER:
        if e.registry_id is None:
            continue
        c = by_id[e.registry_id]
        assert e.obj is c.allocator
        assert e.params == c.params
        assert e.rules == c.rules
        assert spec(e)["registry_digest"] == candidate_digest(c)


def test_digests_are_pinned():
    assert {e.id: spec_digest(spec(e)) for e in ROSTER} == PINS


def test_spec_is_strings_and_nulls_only():
    def leaves(x):
        if isinstance(x, dict):
            for v in x.values():
                yield from leaves(v)
        else:
            yield x

    for e in ROSTER:
        assert all(v is None or isinstance(v, str) for v in leaves(spec(e))), e.id


def test_spec_text_is_canonical_and_survives_a_json_round_trip():
    for e in ROSTER:
        s = spec(e)
        shuffled = dict(reversed(list(s.items())))
        assert spec_text(shuffled) == spec_text(s)
        assert spec_digest(json.loads(json.dumps(s))) == spec_digest(s)
        assert spec_text(s).isascii()


def test_the_spec_names_engine_object_rules_and_params():
    s = spec(entry(F4))
    assert (s["engine"], s["object"], s["object_id"], s["registry_id"], s["rules_id"]) == (
        "book", "FACTOR", "FAC", F4, "monthly-hold",
    )
    assert s["params"] == FACTOR_PARAMS_AS_DICT
    assert s["rules"] == rules_dict(MONTHLY_HOLD)
    assert s["initial_idr"] == "20000000"
    a = spec(entry("A"))
    assert a["params"] == STRATEGY_A_PARAMS.as_dict()
    assert a["rules"]["engine"] == "bracket_v0"


def test_a_changed_parameter_changes_the_digest():
    s = spec(entry(F4))
    changed = json.loads(json.dumps(s))
    changed["params"]["top"] = "10"
    assert spec_digest(changed) != spec_digest(s)


def test_strategy_params_is_contract_c2():
    for e in ROSTER:
        p = strategy_params(e)
        assert set(p) == {"spec", "digest", "backtest_gate"}
        assert p["digest"] == spec_digest(p["spec"])
        assert p["backtest_gate"] == backtest_gate(e) == {"passed": False, "note": e.gate_note}
        assert e.gate_note
        json.dumps(p)


def test_strategy_params_round_trip_through_jsonb(pg):
    for e in ROSTER:
        p = strategy_params(e)
        pg.execute("UPDATE strategies SET params = %s WHERE id = %s", (Jsonb(p), e.id))
        back = pg.execute("SELECT params FROM strategies WHERE id = %s", (e.id,)).fetchone()[0]
        assert back == p
        assert spec_digest(back["spec"]) == back["digest"] == PINS[e.id]
    pg.rollback()


def test_lookbacks():
    assert {e.id: e.lookback for e in ROSTER} == {"SPY": 1, "A": 200, F4: 253, F1: 200}
    assert MAX_LOOKBACK_BARS == 253


def test_550_calendar_days_hold_the_longest_lookback():
    # Plan decision "History at night": bars since data_date − 550 calendar days.
    for d in dates.sessions(date(2026, 10, 1), date(2027, 12, 31)):
        assert len(dates.sessions(d - timedelta(days=550), d)) >= MAX_LOOKBACK_BARS


def test_entry_rejects_an_id_off_the_roster():
    with pytest.raises(KeyError):
        entry("B")
```
**Impact:** test-only. The DB tests use the `pg` fixture, and the jsonb test rolls back.

### Step 8: Migration tests for 003
**File:** `engine/tests/test_migrate.py`:
- line 20, `test_repo_has_001_and_002`, becomes `test_repo_has_001_to_003`;
- line 26 now asserts the paper tables too;
- the new helpers and 003 tests are appended after line 72.

**Change:**
- **Fresh schema:** 003 applies on a fresh schema and writes the roster with SPY as champion. `params` is `{}` and `paper_start` is NULL until `paper` runs.
- **Columns:** the new columns exist.
- **Idempotent:** re-running the 003 file text changes no column, constraint, table or `strategies` row.
- **Neon shape:** on a database shaped like Neon, A loses the champion flag and the unreferenced B/C rows go.
- **Guarded delete:** a B referenced by `orders`, or a C referenced by `equity_snapshots`, survives.
- **CHECK constraints:** they reject unknown `engine`, `paper_status` and `exit_reason` values.
**Code:** the whole file after the change:
```python
"""The Python migration runner (shares schema_migrations with web/scripts/migrate.mjs)."""

from __future__ import annotations

from datetime import date

import psycopg
import pytest

from seer_engine import cli
from seer_engine.commands.migrate import MIGRATIONS_DIR, apply_migrations, migration_files

ALL = [p.name for p in migration_files(MIGRATIONS_DIR)]
PAPER_TABLES = {"paper_state", "book_positions", "book_targets", "book_fills", "book_trades", "dividends"}
ROSTER_IDS = {"SPY", "A", "F4-MOM12-N20-TREND", "F1-SPY-SMA200-M"}


def _tables(conn) -> set[str]:
    rows = conn.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = current_schema()"
    ).fetchall()
    return {r[0] for r in rows}


def _columns(conn) -> list[tuple]:
    return conn.execute(
        "SELECT table_name, column_name, data_type, is_nullable, column_default "
        "FROM information_schema.columns WHERE table_schema = current_schema() "
        "ORDER BY table_name, ordinal_position"
    ).fetchall()


def _constraints(conn) -> list[tuple]:
    return conn.execute(
        "SELECT conrelid::regclass::text, conname FROM pg_constraint c "
        "JOIN pg_namespace n ON n.oid = c.connamespace WHERE n.nspname = current_schema() "
        "ORDER BY 1, 2"
    ).fetchall()


def _strategies(conn) -> list[tuple]:
    return conn.execute(
        "SELECT id, name, sub, icon, is_champion, is_benchmark, sort, engine, rules_id, params, paper_start "
        "FROM strategies ORDER BY id"
    ).fetchall()


def _neon_before_003(conn) -> None:
    """001 + 002 applied and recorded, with the strategies rows Neon had before 003."""
    conn.execute(
        "CREATE TABLE schema_migrations (name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
    )
    for name in ("001_init.sql", "002_engine.sql"):
        conn.execute((MIGRATIONS_DIR / name).read_text(encoding="utf-8"))
        conn.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (name,))
    conn.execute(
        "INSERT INTO strategies (id, name, sub, icon, is_champion, is_benchmark, sort) VALUES "
        "('A', 'A · Quant', 'Mean Reversion', 'sigma', true, false, 1), "
        "('B', 'B · ML', 'Gradient boosting', 'brain', false, false, 2), "
        "('C', 'C · LLM', 'Language model', 'sparkles', false, false, 3), "
        "('SPY', 'SPY', 'Benchmark', 'flag', false, true, 9)"
    )
    conn.commit()


def test_repo_has_001_to_003():
    assert ALL[:3] == ["001_init.sql", "002_engine.sql", "003_paper.sql"]


def test_applies_all_then_nothing(pg_empty):
    assert apply_migrations(pg_empty, MIGRATIONS_DIR) == ALL
    assert {"runs", "bars", "universe", "split_adjustments", "backfill_log"} | PAPER_TABLES <= _tables(pg_empty)
    names = [r[0] for r in pg_empty.execute("SELECT name FROM schema_migrations ORDER BY name")]
    assert names == ALL
    assert apply_migrations(pg_empty, MIGRATIONS_DIR) == []


def test_respects_rows_written_by_the_node_runner(pg_empty):
    pg_empty.execute(
        "CREATE TABLE schema_migrations (name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
    )
    pg_empty.execute((MIGRATIONS_DIR / "001_init.sql").read_text())
    pg_empty.execute("INSERT INTO schema_migrations (name) VALUES ('001_init.sql')")
    pg_empty.commit()
    assert apply_migrations(pg_empty, MIGRATIONS_DIR) == [n for n in ALL if n != "001_init.sql"]


def test_dry_run_writes_nothing(pg_empty):
    assert apply_migrations(pg_empty, MIGRATIONS_DIR, dry_run=True) == ALL
    assert _tables(pg_empty) == set()


def test_dry_run_after_apply_reports_nothing(pg_empty):
    apply_migrations(pg_empty, MIGRATIONS_DIR)
    assert apply_migrations(pg_empty, MIGRATIONS_DIR, dry_run=True) == []
    count = pg_empty.execute("SELECT count(*) FROM schema_migrations").fetchone()[0]
    assert count == len(ALL)


def test_failed_file_rolls_back_only_itself(pg_empty, tmp_path):
    (tmp_path / "001_ok.sql").write_text("CREATE TABLE ok_t (x int);")
    (tmp_path / "002_bad.sql").write_text("CREATE TABLE bad_t (x int); SELECT no_such_column FROM ok_t;")
    with pytest.raises(Exception):
        apply_migrations(pg_empty, tmp_path)
    assert "ok_t" in _tables(pg_empty)
    assert "bad_t" not in _tables(pg_empty)
    names = [r[0] for r in pg_empty.execute("SELECT name FROM schema_migrations")]
    assert names == ["001_ok.sql"]


def test_cli_dry_run_against_test_db(pg_schema, monkeypatch):
    monkeypatch.setenv("DATABASE_URL_UNPOOLED", pg_schema.url)
    assert cli.main(["--dry-run", "migrate"]) == 0
    assert _tables(pg_schema.conn) == set()
    assert cli.main(["migrate"]) == 0
    pg_schema.conn.rollback()  # see the other connection's committed work
    count = pg_schema.conn.execute("SELECT count(*) FROM schema_migrations").fetchone()[0]
    assert count == len(ALL)


# ---- 003_paper.sql ---------------------------------------------------------------------------


def test_003_on_a_fresh_schema_writes_the_roster_with_spy_champion(pg_empty):
    apply_migrations(pg_empty, MIGRATIONS_DIR)
    rows = pg_empty.execute(
        "SELECT id, is_champion, is_benchmark, engine, rules_id, params, paper_start FROM strategies ORDER BY sort"
    ).fetchall()
    assert rows == [
        ("SPY", True, True, "benchmark", None, {}, None),
        ("A", False, False, "bracket", "design-v0", {}, None),
        ("F4-MOM12-N20-TREND", False, False, "book", "monthly-hold", {}, None),
        ("F1-SPY-SMA200-M", False, False, "book", "monthly-hold", {}, None),
    ]


def test_003_adds_the_columns(pg):
    cols = {(t, c) for t, c, *_ in _columns(pg)}
    assert {
        ("strategies", "engine"),
        ("strategies", "rules_id"),
        ("strategies", "paper_start"),
        ("orders", "mark"),
        ("runs", "paper_status"),
        ("runs", "paper_error"),
        ("runs", "paper_finished_at"),
    } <= cols


def test_003_sql_is_idempotent(pg):
    before = (_columns(pg), _constraints(pg), _tables(pg), _strategies(pg))
    pg.execute((MIGRATIONS_DIR / "003_paper.sql").read_text(encoding="utf-8"))
    pg.commit()
    assert (_columns(pg), _constraints(pg), _tables(pg), _strategies(pg)) == before


def test_003_on_neon_flips_the_champion_and_drops_unreferenced_b_and_c(pg_empty):
    _neon_before_003(pg_empty)
    assert apply_migrations(pg_empty, MIGRATIONS_DIR) == ["003_paper.sql"]
    rows = {r[0]: r[1:] for r in pg_empty.execute(
        "SELECT id, name, sub, icon, is_champion, is_benchmark, sort FROM strategies"
    ).fetchall()}
    assert set(rows) == ROSTER_IDS
    assert rows["SPY"] == ("SPY", "S&P 500, buy and hold", "landmark", True, True, 1)
    assert rows["A"] == ("A · Quant", "Mean reversion, 5-day brackets", "sigma", False, False, 2)
    champions = pg_empty.execute("SELECT id FROM strategies WHERE is_champion").fetchall()
    assert champions == [("SPY",)]


@pytest.mark.parametrize("kept", ["orders", "equity_snapshots"])
def test_003_keeps_a_referenced_b_or_c(pg_empty, kept):
    _neon_before_003(pg_empty)
    if kept == "orders":
        pg_empty.execute(
            "INSERT INTO orders (strategy_id, session_date, slot, symbol, company, last_price, "
            "limit_price, tp_price, sl_price, shares, status) "
            "VALUES ('B', %s, 1, 'NVDA', 'NVIDIA', 180, 178, 185, 172, 10, 'pending')",
            (date(2026, 10, 5),),
        )
    else:
        pg_empty.execute(
            "INSERT INTO equity_snapshots (strategy_id, date, cash_usd, equity_usd) VALUES ('C', %s, 1, 1)",
            (date(2026, 10, 2),),
        )
    pg_empty.commit()
    apply_migrations(pg_empty, MIGRATIONS_DIR)
    ids = {r[0] for r in pg_empty.execute("SELECT id FROM strategies").fetchall()}
    survivor = "B" if kept == "orders" else "C"
    gone = "C" if kept == "orders" else "B"
    assert survivor in ids
    assert gone not in ids
    assert ROSTER_IDS <= ids


def test_003_checks_reject_unknown_values(pg):
    with pytest.raises(psycopg.errors.CheckViolation):
        pg.execute("UPDATE strategies SET engine = 'other' WHERE id = 'A'")
    pg.rollback()
    with pytest.raises(psycopg.errors.CheckViolation):
        pg.execute("INSERT INTO runs (status, paper_status) VALUES ('running', 'done')")
    pg.rollback()
    with pytest.raises(psycopg.errors.CheckViolation):
        pg.execute(
            "INSERT INTO book_trades (strategy_id, symbol, entry_date, exit_date, entry_price, exit_price, "
            "days_held, cost_usd, income_usd, pnl_usd, exit_reason) "
            "VALUES ('A', 'X', '2026-10-01', '2026-10-02', 1, 1, 1, 0, 0, 0, 'tp-hit')"
        )
    pg.rollback()
```
**Impact:** test-only.

## Verification

**Build:** `engine/.venv/bin/python -c "import seer_engine.paper.roster as r; print(r.ROSTER_IDS, r.MAX_LOOKBACK_BARS)"` prints `('SPY', 'A', 'F4-MOM12-N20-TREND', 'F1-SPY-SMA200-M') 253`.

**Tests:**
- `docker start seer-pg`
- `PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests/test_paper_roster.py engine/tests/test_migrate.py engine/tests/test_demo.py engine/tests/test_strategy_purity.py -q`: 39 passed when this plan was dry-run against a scratch copy.
- The full suite, `PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q`: 1717 passed, **0 skipped** in that dry run.
- `cd web && npx vitest run`: unaffected, because no web test reads migrations.

**Manual check:** none. Neon is not touched here; phase 13 applies 003 there.

**Exit criteria:**
- `migrate` applies `003_paper.sql` on a fresh schema and a second `migrate` applies nothing. The raw 003 text re-runs as a no-op.
- The roster display fields equal the migration's rows.
- The four spec digests are pinned in `test_paper_roster.py`.
- The purity test covers `paper/*.py` except `store.py`.
- `DEMO_TABLES` includes the five paper state tables and not `dividends`; a purge resets `strategies.paper_start`/`params`.
- The whole engine suite is green with 0 skipped.

## Handoffs

**Phase 7 (`paper` command):**
- Write `strategies.params` with `roster.strategy_params(e)`, verbatim.
- On a started id (`paper_start` set), refuse when the stored `params->>'digest'` differs from `strategy_params(e)["digest"]`. `spec_digest(stored["spec"])` recomputes the digest from the stored spec if a check is wanted.
- Iterate `roster.ROSTER` and dispatch on `e.engine`. Use `e.obj`, `e.params` and `e.rules`. The benchmark has `obj`, `params` and `rules` set to `None`.
- A demo purge resets `strategies.paper_start`/`params` (this phase, reconciled), so after a purge every roster row is "not started". A row with `paper_start` set but no `paper_state` can then only come from a hand edit, and `paper` refuses it (phase 7).

**Phase 6 (store):**
- The windowed history load (`since = data_date − 550 days`) must cover `roster.MAX_LOOKBACK_BARS` (253) bars. `test_paper_roster.py` already pins that 550 calendar days hold at least 253 sessions through 2027.
- Phase 6 owns the 550 constant itself.
- Roster rows can be read back through the `engine`, `rules_id` and `paper_start` columns.

**Phases 3, 4 and 8:**
- Their `paper/*.py` modules (other than `store.py`) are now under the purity test automatically. No edit to `test_strategy_purity.py` is needed.
- Book and benchmark rules come from `RosterEntry.rules` (`MONTHLY_HOLD`) and the benchmark's spec params.

**Phase 10 (web data + seed):**
- **`seed-demo.mjs`.** It must write the roster in the new shape: ids, name/sub/icon/sort, `engine`, `rules_id` and SPY as the only champion, exactly as in migration 003. `test_paper_roster.test_display_fields_equal_the_migration_rows` is the reference. The seed can also write C2 `params`, including `backtest_gate`.
- **Truncate list.** The seed currently truncates `strategies ... CASCADE`. With 003 that cascades to the five paper tables. That is fine, but the seed's explicit truncate list should name them.
- **Paper clock.** The seed may write `strategies.paper_start` and `params` freely: `purge_demo` resets both when it purges.
- **Dividends.** The seed must **not** write `dividends`. If it has to, the reconciler must add `dividends` to `demo.DEMO_TABLES` and reverse this phase's decision.
- **Web reads.** The web must treat `params = {}`, a fresh migrate before `paper` has run, as "gate not passed". `params->'backtest_gate'` is absent until phase 7 writes it.

**Phase 13 (docs):**
- **`engine/package_readme.md`:**
  - a `paper` section (roster, frozen spec and digest rule, "new id, new clock");
  - the 003 schema;
  - the `DEMO_TABLES` change and why `dividends` is not purged.
- **ROADMAP:** the champion flip to SPY.
- **Neon:** applying 003 there.

**Not done, by design:**
- **Champion flag on a kept B/C.** If a B or C row is kept because it is referenced, migration 003 does not clear its `is_champion` flag. Neither is champion on Neon, and invariant 3 allows only the two named data statements. If the reconciler wants that guarantee, it is a one-line `UPDATE strategies SET is_champion = false WHERE id NOT IN (…roster…)` added to 003 before 003 ever reaches Neon.

## Rollback

- **Code:** `git revert` the phase commit. That removes the migration file, the `paper` package and the test changes, and `DEMO_TABLES` returns to six tables. The tree stays green, because no other phase's code exists without this one.
- **A database that already applied 003** (a local dev database; Neon is touched only in phase 13):
  - The new columns and tables are additive and harmless to the old code.
  - To restore the old champion: `UPDATE strategies SET is_champion = (id = 'A')`.
  - To drop the paper schema completely: `DROP TABLE paper_state, book_positions, book_targets, book_fills, book_trades, dividends; ALTER TABLE strategies DROP COLUMN engine, DROP COLUMN rules_id, DROP COLUMN paper_start; ALTER TABLE orders DROP COLUMN mark; ALTER TABLE runs DROP COLUMN paper_status, DROP COLUMN paper_error, DROP COLUMN paper_finished_at; DELETE FROM schema_migrations WHERE name = '003_paper.sql'`.
  - Deleted B/C rows were unreferenced. If wanted, re-insert them by hand from `web/scripts/seed-demo.mjs`'s old list.

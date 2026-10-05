# Phase 1: The roster becomes data: `status`, `paper_end`, and a name→object resolver

**Plan set:** `ROSTER_PROMOTION_PIPELINE_PLAN.md`
**Analysis:** `20261005-165054-XGER_code_analyzer.md`
**Satisfies:** R2 — replace the four horsemen easily; swapping an approach must not require editing engine code
**Depends on:** none
**Difficulty:** HARD
**Package:** `db`, `engine/src/seer_engine/paper`

---

## Runtime preamble

Every phase plan opens with this block and every command in this set assumes it.

```bash
export SEER_WT=/home/miftah/.worktrees/seer/roster-promotion-pipeline
export SEER_PY=/home/miftah/seer/engine/.venv/bin/python
export PYTHONPATH=$SEER_WT/engine/src                        # wins over the editable .pth
export SEER_MAIN=/home/miftah/seer
export SEER_ENV_FILE=$SEER_MAIN/.env.local-train             # ABSOLUTE, always
export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres
cd "$SEER_WT"
"$SEER_PY" -c 'import seer_engine, pathlib; print(pathlib.Path(seer_engine.__file__).resolve())'
# must print $SEER_WT/engine/src/seer_engine/__init__.py
```

Measured on the `fundamental-panel-coverage` set that landed today: the worktree has **no venv of
its own**, `/home/miftah/seer/engine/.venv` is an *editable* install pointing at
`/home/miftah/seer/engine/src`, and `engine/pyproject.toml` sets `testpaths` but no `pythonpath`.
Without `PYTHONPATH` a phase can edit this worktree and watch `main`'s code pass the tests.

For `web/`: `cd $SEER_WT/web && npm ci` once, then `npm test` and `npm run build`.

---

## Goal

After this phase a paper roster entry is a **row**, not a literal. `strategies` carries the
lifecycle (`status`, `paper_end`, `promoted_from`) and the definition (`object_name`,
`registry_id`, `gate_note`, `gate_applicable`) alongside the display fields it already had, and
`paper.roster.from_rows` turns those rows into `RosterEntry` values through `RESOLVER`, the one
code-side table mapping a stable object name to the live Python object (Decisions D2). The
compiled `ROSTER` no longer *is* the roster: it is `from_rows(SEED_ROWS)` — the same builder,
over the same values the migration writes — so the five pinned `spec_digest` values are produced
by the data path itself, not merely alongside it.

Nothing yet *acts* on `status`: the paper night still steps `roster.ROSTER`. Phase 2 moves it.

## Interface Contract

The reconciler reads this section to detect cross-phase conflicts. Be exact and exhaustive.

**Creates (`db/migrations/006_roster.sql`, new file):**
- column `strategies.status` — `text NOT NULL DEFAULT 'active' CHECK (status IN ('active','retired'))`
- column `strategies.paper_end` — `date` (nullable)
- column `strategies.promoted_from` — `text` (nullable; the lab `methods.id` a row was promoted from)
- column `strategies.object_name` — `text` (nullable; a `paper.roster.RESOLVER` key)
- column `strategies.registry_id` — `text` (nullable; a `backtest.registry` id, book entries only)
- column `strategies.gate_note` — `text` (nullable)
- column `strategies.gate_applicable` — `boolean NOT NULL DEFAULT true`
- one `UPDATE … FROM (VALUES …)` backfilling the four definition columns on the five rows 003/004 inserted

**Creates (`engine/src/seer_engine/paper/roster.py`):**
- `roster.Status` — `Literal["active","retired"]`; `roster.STATUSES`; `roster.ENGINES`
- `roster.BENCHMARK_OBJECT` — `"buy_and_hold"`
- `roster.RosterError(LookupError)`, `roster.UnknownObject`, `roster.UnknownRules`, `roster.BadRosterRow`
- `roster.Binding` — `(obj, params, from_registry)`; `roster.RESOLVER: dict[str, Binding]`;
  `roster.resolve(object_name) -> Binding`; `roster.resolver_names() -> tuple[str, ...]`
- `roster.rules_for(rules_id) -> TradeRules | None` (over `sim.rules.PRESETS`)
- `roster.Row` — a `Protocol` naming the 15 attributes `from_row` reads
- `roster.RosterRow` — the plain-data row dataclass; `roster.SEED_ROWS: tuple[RosterRow, ...]`
- `roster.from_row(row) -> RosterEntry`; `roster.from_rows(rows) -> tuple[RosterEntry, ...]`
- `roster.active(entries=ROSTER) -> tuple[RosterEntry, ...]`

**Signature changes:**
- `roster.RosterEntry` gains two trailing defaulted fields: `status: Status = "active"`,
  `paper_end: date | None = None`. Every existing field, its order and its type are unchanged.
- `store.StrategyRow` gains nine fields: `sub`, `icon`, `status`, `paper_end`, `promoted_from`,
  `object_name`, `registry_id`, `gate_note`, `gate_applicable`. It is constructed by keyword in
  exactly one place (`store._strategy`); no positional construction exists.
- `store._STRATEGY_SQL` projects the nine new columns.
- `store.read_roster_rows(conn) -> tuple[StrategyRow, ...]` is **new**: rows with
  `engine IS NOT NULL`, ordered by `(sort, id)`. `StrategyRow` structurally satisfies
  `roster.Row`, so `roster.from_rows(store.read_roster_rows(conn))` is the whole data path.

**Deletes:** nothing. No column, no symbol, no row, no test.

**Renames:** none.

**Unchanged, byte for byte (invariant 2 — the hard constraint):**
`roster.spec`, `roster.spec_text`, `roster.spec_digest`, `roster.rules_dict`, `roster._rule_value`,
`roster.backtest_gate`, `roster.strategy_params`, `roster.entry`, `roster.ROSTER`,
`roster.ROSTER_IDS`, `roster.MAX_LOOKBACK_BARS`, `roster.BENCHMARK_ID`, `roster.F4_ID`,
`roster.F1_ID`, `roster.Engine`, `roster._registered`.
`ROSTER` is now *computed* from `SEED_ROWS`, and the computed value is element-wise equal to
today's literal — **verified against the live schema before this plan was written**: all five
`spec_digest` values match `test_paper_roster.py`'s `PINS`, `spec_text` is byte-identical to
`main`'s for all five, and `a.obj is STRATEGY_A`, `a.params is STRATEGY_A_PARAMS`,
`a.rules is DESIGN_V0`, `c.obj is STRATEGY_C`, `c.params is STRATEGY_C_PARAMS`,
`c.rules is DESIGN_V0`, `f4.obj is FACTOR`, `f1.obj is TIMING` all still hold by **identity**.

**Requires (from earlier phases):** nothing. Phase 1 is a wave-1 phase.

**Exposed to phase 2** (`commands/paper.py`, `store.py` write side, `paper_check.py`):
- `store.read_roster_rows(conn)` → `roster.from_rows(...)` replaces `roster.ROSTER` at
  `commands/paper.py:143` and `:149` and `commands/paper_check.py:102`.
- `roster.active(entries)` filters to `status == "active"`.
- `e.status` and `e.paper_end` are on `RosterEntry`.
- Writing `status`/`paper_end` is **phase 2's**: this phase adds no setter.

**Exposed to phase 5** (`commands/promote.py`): the insert shape. A promoted row is
`INSERT INTO strategies (id, name, sub, icon, is_champion, is_benchmark, sort, engine, rules_id,
object_name, registry_id, gate_note, gate_applicable, status, promoted_from)` with
`paper_start` and `paper_end` left NULL and `status = 'active'`. `object_name` must be a key of
`roster.RESOLVER` — `roster.resolver_names()` is the list to validate against, and
`roster.from_row` is the check to run before committing.

**Exposed to phase 6** (`FND`): the extension point is **one entry in `roster.RESOLVER` plus one
`RosterRow` in `SEED_ROWS`** — nothing else in `roster.py`, and no edit to `from_row`,
`from_rows`, `spec`, `spec_text`, `spec_digest` or any existing seed row. Concretely, phase 6:
- adds `from seer_engine.strategies.f_fundamental import FUNDAMENTAL, FundamentalParams,
  fundamental_lookback` and a module-level `FUNDAMENTAL_PARAMS`;
- adds `"FUNDAMENTAL": Binding(obj=FUNDAMENTAL, params=FUNDAMENTAL_PARAMS)` to `RESOLVER`
  (`from_registry` stays `False`, so the row must carry `registry_id = NULL`);
- appends a sixth `RosterRow` to `SEED_ROWS` with `sort=6`, `engine="book"`,
  `rules_id="monthly-hold"`, `object_name="FUNDAMENTAL"`, `registry_id=None` and its `gate_note`;
- writes `db/migrations/007_fnd.sql` carrying **exactly those column values**, because
  `test_the_migration_rows_equal_the_seed_rows` compares the whole `strategies` table to
  `SEED_ROWS`.

`ROSTER`, `ROSTER_IDS` and `MAX_LOOKBACK_BARS` then recompute themselves; the five pinned digests
cannot move, because adding a seed row touches no existing entry.

**`MAX_LOOKBACK_BARS` is this phase's, and it does not change** (reconciler's assignment; phase 2
and phase 6 both flagged it and neither owns it). It stays `max(e.lookback for e in ROSTER)` — the
max over the **seeded** roster, not over whatever rows a live database holds. That is deliberate:
no production path reads it (`commands/paper.py:_check_window` recomputes the max over tonight's
trading entries), its only consumers are `test_paper_roster.py:188` and `:194`, and the live guard
against promoting a strategy whose lookback the night's bar window cannot feed is phase 5's
`promote.check_lookback`. The docstring must say so (see Step 2's docstring text).

**Exposed to phase 4** (`web/`): `strategies.status` (`'active'`/`'retired'`) and
`strategies.paper_end` (`date`, nullable) are projectable from `web/lib/data.ts`.

**Leaves alone (owned by others):**
- `engine/src/seer_engine/commands/paper.py` — phase 2
- `engine/src/seer_engine/commands/paper_check.py` — phase 2
- `engine/tests/test_paper_command.py`, `test_paper_store.py`, `test_paper_c.py` — phase 2
- `engine/src/seer_engine/paper/compare.py` — phase 3
- `web/**` (including `web/scripts/seed-demo.mjs`) — phase 4
- `engine/src/seer_engine/commands/promote.py`, `lab/store.py` — phase 5
- `engine/src/seer_engine/strategies/f_fundamental.py` — phase 6
- `engine/src/seer_engine/backtest/registry.py` — **never** (Decisions D1)
- `engine/src/seer_engine/sim/rules.py` — the `rules_id → TradeRules` map lives in `roster.py`,
  built from the existing `sim.rules.PRESETS`; `sim/rules.py` is not edited

## Files

| File | Action | What changes |
|---|---|---|
| `db/migrations/006_roster.sql` | create | seven additive `ALTER TABLE strategies ADD COLUMN IF NOT EXISTS`, plus one `UPDATE … FROM (VALUES …)` backfilling the five existing rows |
| `engine/src/seer_engine/paper/roster.py` | rewrite | `:1-41` docstring, `:62-66` constants, `:69-101` `RosterEntry` (+2 fields), new resolver/row/builder block, `:122-212` `ROSTER` literal → `from_rows(SEED_ROWS)`. `spec`/`spec_text`/`spec_digest`/`rules_dict`/`backtest_gate`/`strategy_params`/`entry`/`_registered` unchanged |
| `engine/src/seer_engine/paper/store.py` | modify | `:107-152` — `StrategyRow` +9 fields, `_STRATEGY_SQL` +9 columns, `_strategy` updated, new `read_roster_rows` |
| `engine/tests/test_paper_roster.py` | modify | +15 tests (12 pure, 3 `pg`-gated). No existing test is edited; `PINS` is untouched |

---

## Implementation Steps

### Step 1: The migration

**File:** `db/migrations/006_roster.sql` (new file; `db/migrations/005_fundamentals.sql` is the
last existing one, 101 lines)

**Change:** add the lifecycle and definition columns to `strategies`, additively (invariant 5),
then backfill the four definition columns on the five rows migrations 003 and 004 inserted. The
backfilled values are byte-for-byte `roster.SEED_ROWS` from Step 2; `test_paper_roster.py` checks
that equality against a migrated database (invariant 7).

`§` in C's gate note is intentional and matches `roster.py`; the file is UTF-8 and
`conftest.pg` reads it with `encoding="utf-8"`.

**Code:**

```sql
-- Seer schema v6: the roster becomes data (plan roster-promotion-pipeline, phase 1; R2, D2, D3).
-- Additive only, matching 003_paper.sql's discipline: nullable or defaulted columns on
-- `strategies`, no column dropped, no CHECK narrowed, migrations 001-005 untouched.
-- Written by engine/ (Python); web/ reads `status` and `paper_end` from the leaderboard.
--
-- Until now `paper/roster.py` held a compiled-in tuple and the `strategies` row held only the
-- display fields. These columns move the rest of a roster row into the database, so adding,
-- replacing or retiring a horseman is a row, not a code edit. The one thing a row cannot hold
-- is the live Python object, so it holds the object's STABLE NAME instead and
-- `paper.roster.RESOLVER` maps that name to the object (Decisions D2). A name the resolver does
-- not know is a hard error when the roster is built, never a silently dropped portfolio
-- (invariant 9) -- an `eval`-ed import path would have made this column a code-execution surface.
--
-- Lifecycle (D3, invariants 3 and 4): a horseman is replaced by INSERTING a new row and setting
-- the old row's status to 'retired', in one transaction. Retirement NEVER deletes
-- equity_snapshots, orders, book_* or paper_state rows, and never clears paper_start;
-- `paper_end` records the last session actually traded, so the leaderboard keeps the whole
-- track record and can say the row is retired rather than hiding it.

-- Lifecycle.
ALTER TABLE strategies ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'active'
  CHECK (status IN ('active', 'retired'));      -- 'retired': keeps its history, stops trading
ALTER TABLE strategies ADD COLUMN IF NOT EXISTS paper_end date;        -- last session traded; NULL while active
ALTER TABLE strategies ADD COLUMN IF NOT EXISTS promoted_from text;    -- lab methods.id this row came from

-- The roster row's definition, read by paper.roster.from_row.
ALTER TABLE strategies ADD COLUMN IF NOT EXISTS object_name text;      -- a paper.roster.RESOLVER key
ALTER TABLE strategies ADD COLUMN IF NOT EXISTS registry_id text;      -- backtest.registry id (book entries), else NULL
ALTER TABLE strategies ADD COLUMN IF NOT EXISTS gate_note text;        -- the display fact the go-live checklist reads
ALTER TABLE strategies ADD COLUMN IF NOT EXISTS gate_applicable boolean NOT NULL DEFAULT true;

-- The five rows 003 and 004 inserted, given the definition fields they were missing. Every value
-- here is byte-for-byte paper/roster.py's SEED_ROWS; tests/test_paper_roster.py checks that
-- equality against a migrated database, and the spec digests pinned there must not move.
UPDATE strategies SET
  object_name = v.object_name,
  registry_id = v.registry_id,
  gate_note = v.gate_note,
  gate_applicable = v.gate_applicable
FROM (VALUES
  ('SPY', 'buy_and_hold', NULL,
   'Benchmark, not a strategy: it has no backtest gate and is never a Seer pick', true),
  ('A', 'STRATEGY_A', NULL,
   'P3 gate failed out of sample (2022-01-03..2026-10-02): -15.0% vs SPY TR +71.9%, PF 0.92, max DD 33.3%', true),
  ('F4-MOM12-N20-TREND', 'FACTOR', 'F4-MOM12-N20-TREND',
   'P7a dev window only; failed max DD <= 15% (22.2%)', true),
  ('F1-SPY-SMA200-M', 'TIMING', 'F1-SPY-SMA200-M',
   'P7a dev window only; failed max DD <= 15% (18.7%) and >= 100 trades (11)', true),
  ('C', 'STRATEGY_C', NULL,
   'Backtest gate: not applicable (LLM strategy, design §1 item 5)', false)
) AS v(id, object_name, registry_id, gate_note, gate_applicable)
WHERE strategies.id = v.id;
```

**Impact:** `conftest.pg` applies every `db/migrations/*.sql` in name order, so every `pg`-fixture
test now sees the new columns. Nothing reads them yet except the new tests and
`store.read_roster_rows`. Re-running the file is a no-op (verified: `ADD COLUMN IF NOT EXISTS`
skips the column and its inline CHECK; the `UPDATE` rewrites the same values). The `status` CHECK
is live (verified: `UPDATE strategies SET status='zombie'` raises `CheckViolation`).

---

### Step 2: `roster.py` — the resolver, the row, and `ROSTER` built from both

**File:** `engine/src/seer_engine/paper/roster.py` (complete replacement of the 309-line file)

**Change:** `ROSTER` stops being a literal and becomes `from_rows(SEED_ROWS)`. `SEED_ROWS` holds
exactly what the `strategies` table holds after migration 006; `from_row` is the single builder
both the seeds and the database rows go through, so a database-driven roster is proven correct by
the pinned digests rather than merely assumed to be.

Keep the file **pure**: `engine/tests/test_strategy_purity.py` globs `seer_engine/paper/*.py`
(every module but `store.py`) and asserts no `psycopg`/`requests`/`yfinance`/`time`/`random`/
`logging`/`urllib`/`socket` import, no `.now`/`.utcnow`/`.today`/`.fromtimestamp`/`.random`
attribute anywhere in the source, and no `print`/`open`/`input` call. `from datetime import date`
is fine (`datetime` is not a forbidden root). Do not add a `store` import — `from_row` takes a
duck-typed `Row`, so neither module imports the other and there is no cycle.

**Code:**

```python
"""The paper roster (handover D1, D2, D4; plan contract C2; roster-promotion-pipeline R2, D2, D3).

Pure: no database, no clock, no I/O. Every portfolio paper-trades every night on its own paper
clock; this module is the single place that says what each one *is*, given the row that says it
exists.

**The roster is data; the objects are code (D2).** A ``strategies`` row carries everything about
an entry except the live Python object: its display fields, its ``engine``, its ``rules_id``, its
``registry_id``, its gate note, its lifecycle (``status``, ``paper_end``) -- and ``object_name``,
a stable name. :data:`RESOLVER` maps that name to the object, and :func:`from_row` turns one row
plus the resolver into a :class:`RosterEntry`. A database cannot hold an ``Allocator``, and
``eval``-ing an import path out of a row would make the table a code-execution surface, so the
resolver is the smallest thing that must stay in code. **Adding a strategy is a row plus, at
most, one resolver entry** -- never an edit to this builder.

A row whose ``object_name`` is not in :data:`RESOLVER` raises :class:`UnknownObject`; an unknown
``rules_id`` raises :class:`UnknownRules`; anything else malformed raises :class:`BadRosterRow`.
All three are :class:`RosterError`, all three stop the night, and all three name **the strategy id
and the offending value**. A typo must never quietly drop a portfolio and leave a hole in its
equity curve, and the message must say which portfolio.

:data:`SEED_ROWS` is the five rows ``db/migrations/003_paper.sql``, ``004_news_veto.sql`` and
``006_roster.sql`` write, as data; :data:`ROSTER` is ``from_rows(SEED_ROWS)``. The compiled roster
and the stored roster therefore travel the *same* builder, and
``tests/test_paper_roster.py`` checks both against a migrated database.

- ``SPY``: buy-and-hold SPY with dividends reinvested (``backtest.benchmark.buy_and_hold``
  rules), the champion and the yardstick (D2).
- ``A``: Strategy A with ``STRATEGY_A_PARAMS`` under ``DESIGN_V0`` (the bracket engine).
- ``F4-MOM12-N20-TREND`` and ``F1-SPY-SMA200-M``: the P7a registry entries of those ids,
  taken from ``backtest.registry.REGISTRY`` as they are (the registry is read, never edited,
  and never appended to -- it is the dev run's fixed candidate set), under their own
  ``MONTHLY_HOLD`` rules (the book engine).
- ``C``: Strategy C (``strategies.c.STRATEGY_C`` with ``STRATEGY_C_PARAMS``) under
  ``DESIGN_V0``: A's ranked candidates minus every symbol the stored news check did not
  allow (strategy-c-news-veto handover D1, D5). The roster object carries no verdicts, so
  it never buys on its own; ``paper`` and ``paper_check`` hand the engine a copy carrying
  the stored verdicts.

**The frozen spec (D4).** :func:`spec` is the entry's trial-defining parts as a JSON-ready
dict of strings: engine, the strategy/allocator object (module-level name and its ``id``),
the registry id and the registry's own ``candidate_digest`` (book entries), every
``TradeRules`` field, every parameter (``as_dict``), and the starting capital in IDR.
:func:`spec_text` is its canonical text (sorted keys, no whitespace, ASCII) and
:func:`spec_digest` the sha256 hex of that text. Both take a plain mapping, so a spec read
back from ``strategies.params->'spec'`` recomputes to the same digest -- which is exactly what
makes a database-stored roster *checkable*. The digests are pinned in
``tests/test_paper_roster.py``: a changed strategy needs a **new id** with its own paper clock,
never an edited entry (``paper`` refuses a started id whose stored digest differs). ``status``,
``paper_end``, ``gate_note`` and ``gate_applicable`` are **not** in the spec, deliberately:
retiring a strategy or correcting a note must not move a live digest.

``backtest_gate`` is a display fact for the go-live checklist (D12), not part of the spec:
correcting its note does not reset a paper clock. Every entry is ``passed: false`` today.
An entry with ``gate_applicable=False`` (C, an LLM strategy: design §1 item 5, handover D9)
also says ``applicable: false``; the four quant/benchmark entries' gate dicts are unchanged.

``status`` is lifecycle, not definition (D3, invariants 3 and 4): a retired entry keeps every
row it ever wrote and stays on the leaderboard: it only stops trading. :func:`active` is the
filter the paper night uses.

:data:`MAX_LOOKBACK_BARS` is the most bars through a data date any object on the **seeded** roster
reads (FACTOR's ``factor_lookback`` = 253); the paper store's windowed history load must cover it.
It is a property of :data:`SEED_ROWS`, not of whatever a live database holds, and the paper night
does not read it: ``commands.paper._check_window`` recomputes the max over the entries that trade
tonight. The guard against admitting a strategy whose lookback the night's bar window cannot feed
belongs to ``commands.promote`` at promotion time, not here.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, fields
from datetime import date
from decimal import Decimal
from typing import Any, Literal, Protocol

from seer_engine.backtest.registry import REGISTRY, candidate_digest
from seer_engine.backtest.runner import INITIAL_IDR
from seer_engine.sim import COST_RATE
from seer_engine.sim.rules import PRESETS, TradeRules, is_pinned_default
from seer_engine.strategies.a import STRATEGY_A, STRATEGY_A_PARAMS
from seer_engine.strategies.allocator import Allocator
from seer_engine.strategies.base import Strategy
from seer_engine.strategies.c import STRATEGY_C, STRATEGY_C_PARAMS
from seer_engine.strategies.f_factor import FACTOR
from seer_engine.strategies.f_index import TIMING

Engine = Literal["bracket", "book", "benchmark"]
Status = Literal["active", "retired"]

BENCHMARK_ID = "SPY"
F4_ID = "F4-MOM12-N20-TREND"
F1_ID = "F1-SPY-SMA200-M"

#: ``object_name`` of the benchmark: ``backtest.benchmark.buy_and_hold``, which is rules, not an object.
BENCHMARK_OBJECT = "buy_and_hold"

#: ``strategies.engine``'s CHECK, as a Python value.
ENGINES: tuple[Engine, ...] = ("bracket", "book", "benchmark")

#: ``strategies.status``'s CHECK, as a Python value.
STATUSES: tuple[Status, ...] = ("active", "retired")


# --------------------------------------------------------------------------- errors


class RosterError(LookupError):
    """A ``strategies`` row cannot be turned into a roster entry.

    Always raised, never swallowed: ``paper`` turns it into a failed paper step for the whole
    night. A roster entry that cannot be built must stop the run, because the alternative --
    skipping it -- leaves a gap in that portfolio's equity curve that nothing later can fill.
    """


class UnknownObject(RosterError):
    """``object_name`` is not a key of :data:`RESOLVER` (a typo, or a strategy not deployed here)."""


class UnknownRules(RosterError):
    """``rules_id`` is not the id of a ``sim.rules`` preset."""


class BadRosterRow(RosterError):
    """The row is internally inconsistent (bad engine or status, missing or surplus fields)."""


# --------------------------------------------------------------------------- the entry


@dataclass(frozen=True, slots=True)
class RosterEntry:
    """One paper portfolio.

    ``obj`` is the ``Strategy`` (bracket), the ``Allocator`` (book) or ``None`` (benchmark);
    ``object_name`` is its :data:`RESOLVER` key -- its module-level name (``STRATEGY_A``,
    ``FACTOR``, ``TIMING``) or ``buy_and_hold`` for the benchmark. ``rules`` is ``None`` only
    for the benchmark. ``lookback`` is the bars through a data date ``obj`` reads (1 for the
    benchmark, which reads only the session's own bar). ``gate_applicable`` is ``False`` only
    for an entry the quant backtest gate does not apply to (C); it changes ``backtest_gate``,
    never the spec.

    ``status`` and ``paper_end`` are lifecycle, carried here so one value answers "what is this
    portfolio and is it still trading?". Neither is in :func:`spec`: retiring a strategy must
    not move its frozen digest.
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
    gate_applicable: bool = True
    status: Status = "active"
    paper_end: date | None = None

    @property
    def rules_id(self) -> str | None:
        """``strategies.rules_id``: the rules preset id, ``None`` for the benchmark."""
        return None if self.rules is None else self.rules.id


# --------------------------------------------------------------------------- the resolver (D2)


@dataclass(frozen=True, slots=True)
class Binding:
    """What a ``object_name`` resolves to: the live object and where its params come from.

    ``params`` is the object's own frozen params value, or ``None`` when ``from_registry`` --
    then the row's ``registry_id`` names the ``backtest.registry`` candidate the params (and
    the identity check) come from, exactly as F4 and F1 have always worked.
    """

    obj: Strategy | Allocator | None
    params: Any = None
    from_registry: bool = False


#: The one code-side table (D2). **This is the extension point**: a new strategy is a row in
#: ``strategies`` plus, if its object is not already here, one entry here. Nothing else in this
#: module changes to add a strategy. Keys are stable forever -- a stored spec names one, so
#: renaming a key would move a live digest. Append; never rename, never remove a key a started
#: strategy's spec still names.
RESOLVER: dict[str, Binding] = {
    BENCHMARK_OBJECT: Binding(obj=None),
    "STRATEGY_A": Binding(obj=STRATEGY_A, params=STRATEGY_A_PARAMS),
    "STRATEGY_C": Binding(obj=STRATEGY_C, params=STRATEGY_C_PARAMS),
    "FACTOR": Binding(obj=FACTOR, from_registry=True),
    "TIMING": Binding(obj=TIMING, from_registry=True),
}


def resolver_names() -> tuple[str, ...]:
    """Every ``object_name`` this build knows, sorted (what ``promote`` validates against)."""
    return tuple(sorted(RESOLVER))


def resolve(object_name: object) -> Binding:
    """The :class:`Binding` for ``object_name``; :class:`UnknownObject` when there is none.

    Never returns a default and never returns ``None``: an unresolvable name is a hard error
    (invariant 9), because a skipped portfolio is a silent hole in a track record.
    """
    if isinstance(object_name, str):
        found = RESOLVER.get(object_name)
        if found is not None:
            return found
    raise UnknownObject(
        f"roster object name {object_name!r} is not in paper.roster.RESOLVER; "
        f"known names: {', '.join(resolver_names())}"
    )


_PRESETS: dict[str, TradeRules] = {r.id: r for r in PRESETS}


def rules_for(rules_id: str | None) -> TradeRules | None:
    """The ``sim.rules`` preset ``rules_id`` (the same object, so ``is DESIGN_V0`` holds).

    ``None`` maps to ``None`` (the benchmark trades under no rule set). An id that is not a
    preset raises :class:`UnknownRules`.
    """
    if rules_id is None:
        return None
    found = _PRESETS.get(rules_id) if isinstance(rules_id, str) else None
    if found is None:
        raise UnknownRules(
            f"rules_id {rules_id!r} is not a sim.rules preset; known ids: {', '.join(sorted(_PRESETS))}"
        )
    return found


# --------------------------------------------------------------------------- the row


class Row(Protocol):
    """What :func:`from_row` reads off a ``strategies`` row.

    ``paper.store.StrategyRow`` satisfies this structurally, which is why this module imports
    nothing from ``store`` (and stays pure: ``tests/test_strategy_purity.py``). Types are the
    column types, nullables included -- validating them is :func:`from_row`'s job.
    """

    id: str
    name: str
    sub: str
    icon: str
    is_champion: bool
    is_benchmark: bool
    sort: int
    engine: str | None
    rules_id: str | None
    object_name: str | None
    registry_id: str | None
    gate_note: str | None
    gate_applicable: bool
    status: str
    paper_end: date | None


@dataclass(frozen=True, slots=True)
class RosterRow:
    """One ``strategies`` row as plain data: the :class:`Row` the seeds and the tests use."""

    id: str
    name: str
    sub: str
    icon: str
    is_champion: bool
    is_benchmark: bool
    sort: int
    engine: str | None
    rules_id: str | None
    object_name: str | None
    registry_id: str | None
    gate_note: str | None
    gate_applicable: bool = True
    status: str = "active"
    paper_end: date | None = None


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


def from_row(row: Row) -> RosterEntry:
    """One ``strategies`` row as a :class:`RosterEntry`, through :data:`RESOLVER`.

    Every failure is a :class:`RosterError` naming the row and what is wrong with it: there is
    no path through this function that returns a usable-looking entry for a row it did not fully
    understand, and no path that returns ``None``.
    """
    sid = row.id
    if not isinstance(sid, str) or not sid:
        raise BadRosterRow(f"a roster row needs a non-empty id, got {sid!r}")
    engine = row.engine
    if engine not in ENGINES:
        raise BadRosterRow(f"{sid!r}: engine {engine!r} is not one of {ENGINES}")
    # Every RosterError out of this function names the ROW, not just the bad value: `paper`'s
    # failed-step message is the only place an operator sees it, and "NO_SUCH_OBJECT is not in
    # RESOLVER" without an id does not say which portfolio stopped the night (invariant 9).
    try:
        binding = resolve(row.object_name)
    except UnknownObject as exc:
        raise UnknownObject(f"{sid!r}: {exc}") from exc
    object_name: str = row.object_name  # resolve() accepted it, so it is a str
    try:
        rules = rules_for(row.rules_id)
    except UnknownRules as exc:
        raise UnknownRules(f"{sid!r}: {exc}") from exc
    registry_id = row.registry_id
    if engine == "benchmark":
        if binding.obj is not None or rules is not None or registry_id is not None:
            raise BadRosterRow(
                f"{sid!r}: a benchmark row carries no object, rules_id or registry_id "
                f"(object_name {object_name!r}, rules_id {row.rules_id!r}, registry_id {registry_id!r})"
            )
        obj: Strategy | Allocator | None = None
        params: Any = None
        lookback = 1
    else:
        if rules is None:
            raise BadRosterRow(f"{sid!r}: a {engine} row needs a rules_id")
        if binding.obj is None:
            raise BadRosterRow(
                f"{sid!r}: object {object_name!r} has no object; it can only run the benchmark engine"
            )
        if binding.from_registry:
            if not isinstance(registry_id, str) or not registry_id:
                raise BadRosterRow(
                    f"{sid!r}: object {object_name!r} takes its params from backtest.registry; "
                    f"registry_id is {registry_id!r}"
                )
            obj, params = _registered(registry_id, binding.obj, rules)
        else:
            if registry_id is not None:
                raise BadRosterRow(
                    f"{sid!r}: object {object_name!r} carries its own params; registry_id must be "
                    f"NULL, got {registry_id!r}"
                )
            obj, params = binding.obj, binding.params
        # Strategy.lookback is an int attribute; Allocator.lookback is a method of its params.
        lookback = obj.lookback(params) if engine == "book" else obj.lookback
    gate_note = row.gate_note
    if not isinstance(gate_note, str) or not gate_note:
        raise BadRosterRow(
            f"{sid!r}: gate_note is {gate_note!r}; every roster row states its backtest gate, "
            f"and 'failed' or 'not applicable' is a complete answer"
        )
    status = row.status
    if status not in STATUSES:
        raise BadRosterRow(f"{sid!r}: status {status!r} is not one of {STATUSES}")
    paper_end = row.paper_end
    if paper_end is not None and not isinstance(paper_end, date):
        raise BadRosterRow(f"{sid!r}: paper_end must be a date or None, got {paper_end!r}")
    return RosterEntry(
        id=sid,
        name=row.name,
        sub=row.sub,
        icon=row.icon,
        is_champion=bool(row.is_champion),
        is_benchmark=bool(row.is_benchmark),
        sort=int(row.sort),
        engine=engine,
        rules=rules,
        obj=obj,
        object_name=object_name,
        params=params,
        registry_id=registry_id,
        lookback=int(lookback),
        gate_note=gate_note,
        gate_applicable=bool(row.gate_applicable),
        status=status,
        paper_end=paper_end,
    )


def from_rows(rows: Iterable[Row]) -> tuple[RosterEntry, ...]:
    """Every row as an entry, by ``(sort, id)``. Raises on the FIRST row it cannot build.

    No row is ever dropped: either every row given becomes an entry, or nothing is returned.
    """
    entries = tuple(sorted((from_row(r) for r in rows), key=lambda e: (e.sort, e.id)))
    ids = [e.id for e in entries]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise BadRosterRow(f"the roster rows carry duplicate ids: {dupes}")
    return entries


# --------------------------------------------------------------------------- the seeded roster

#: The rows ``003_paper.sql``, ``004_news_veto.sql`` and ``006_roster.sql`` write, as data.
#: ``tests/test_paper_roster.py`` checks this equals a migrated database's ``strategies`` rows.
SEED_ROWS: tuple[RosterRow, ...] = (
    RosterRow(
        id=BENCHMARK_ID,
        name="SPY",
        sub="S&P 500, buy and hold",
        icon="landmark",
        is_champion=True,
        is_benchmark=True,
        sort=1,
        engine="benchmark",
        rules_id=None,
        object_name=BENCHMARK_OBJECT,
        registry_id=None,
        gate_note="Benchmark, not a strategy: it has no backtest gate and is never a Seer pick",
    ),
    RosterRow(
        id="A",
        name="A · Quant",
        sub="Mean reversion, 5-day brackets",
        icon="sigma",
        is_champion=False,
        is_benchmark=False,
        sort=2,
        engine="bracket",
        rules_id="design-v0",
        object_name="STRATEGY_A",
        registry_id=None,
        gate_note=(
            "P3 gate failed out of sample (2022-01-03..2026-10-02): -15.0% vs SPY TR +71.9%, "
            "PF 0.92, max DD 33.3%"
        ),
    ),
    RosterRow(
        id=F4_ID,
        name="F4 · Momentum",
        sub="Top 20 by 12-1 momentum, monthly",
        icon="trending-up",
        is_champion=False,
        is_benchmark=False,
        sort=3,
        engine="book",
        rules_id="monthly-hold",
        object_name="FACTOR",
        registry_id=F4_ID,
        gate_note="P7a dev window only; failed max DD <= 15% (22.2%)",
    ),
    RosterRow(
        id=F1_ID,
        name="F1 · Trend",
        sub="SPY above its 200-day average, monthly",
        icon="shield",
        is_champion=False,
        is_benchmark=False,
        sort=4,
        engine="book",
        rules_id="monthly-hold",
        object_name="TIMING",
        registry_id=F1_ID,
        gate_note="P7a dev window only; failed max DD <= 15% (18.7%) and >= 100 trades (11)",
    ),
    RosterRow(
        id="C",
        name="C · News veto",
        sub="A's picks, LLM can veto on news",
        icon="gavel",
        is_champion=False,
        is_benchmark=False,
        sort=5,
        engine="bracket",
        rules_id="design-v0",
        object_name="STRATEGY_C",
        registry_id=None,
        gate_note="Backtest gate: not applicable (LLM strategy, design §1 item 5)",
        gate_applicable=False,
    ),
)

#: The seeded roster, sorted by ``sort``. Built through :func:`from_rows`, the SAME path a
#: database-read roster takes, so the pinned digests prove the data path and not just this tuple.
#: Callers that have not moved to ``store.read_roster_rows`` + :func:`from_rows` keep using it.
ROSTER: tuple[RosterEntry, ...] = from_rows(SEED_ROWS)

ROSTER_IDS: tuple[str, ...] = tuple(e.id for e in ROSTER)

MAX_LOOKBACK_BARS: int = max(e.lookback for e in ROSTER)


def active(entries: Sequence[RosterEntry] = ROSTER) -> tuple[RosterEntry, ...]:
    """``entries`` that are still trading, in order. A retired entry keeps every row it wrote."""
    return tuple(e for e in entries if e.status == "active")


def entry(strategy_id: str) -> RosterEntry:
    """The roster entry ``strategy_id``; ``KeyError`` when it is not on the roster."""
    for e in ROSTER:
        if e.id == strategy_id:
            return e
    raise KeyError(f"{strategy_id!r} is not on the paper roster {ROSTER_IDS}")


# --------------------------------------------------------------------------- the frozen spec (D4)


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
    """Every ``TradeRules`` field, in field order, as plain strings.

    A lever added after this roster's spec digests were pinned is left out while it holds its
    no-op value (``sim.rules.LEVERS_SINCE_PINS``), so a roster strategy that does not use the
    lever keeps the digest already written to its live ``strategies.params`` row. One that uses
    it needs a new roster id anyway (its own paper clock), and then digests differently.
    """
    return {
        f.name: _rule_value(getattr(rules, f.name))
        for f in fields(rules)
        if not is_pinned_default(f.name, getattr(rules, f.name))
    }


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
    """Contract C2 ``params.backtest_gate``: no roster entry has passed a backtest gate.

    An entry the gate does not apply to (C: design §1 item 5, handover D9) also says
    ``"applicable": False``; it still counts as not passed. The applicable entries' dict is
    exactly ``{"passed": False, "note": ...}``, as before C existed.
    """
    if not e.gate_applicable:
        return {"passed": False, "applicable": False, "note": e.gate_note}
    return {"passed": False, "note": e.gate_note}


def strategy_params(e: RosterEntry) -> dict[str, Any]:
    """The whole ``strategies.params`` jsonb for ``e`` (contract C2), as ``paper`` writes it."""
    s = spec(e)
    return {"spec": s, "digest": spec_digest(s), "backtest_gate": backtest_gate(e)}
```

**Impact:**
- `DESIGN_V0` and `MONTHLY_HOLD` are no longer imported by name (they come through `PRESETS` by
  id). `ruff`'s `F401` is in the `ignore` list, but they are genuinely unused now, so drop them
  from the import rather than leave dead names.
- `ROSTER`'s *construction* changes; its *value* does not. Verified before writing this plan,
  against this worktree's code: all five `spec_digest` values equal `PINS`, `spec_text` is
  byte-identical to `main`'s for all five, `strategy_params` is equal for all five, and the
  identity assertions in `test_paper_roster.py:test_each_entry_is_the_named_object_params_and_rules`
  (`is STRATEGY_A`, `is STRATEGY_A_PARAMS`, `is DESIGN_V0`, `is STRATEGY_C`,
  `is STRATEGY_C_PARAMS`, `is FACTOR`, `is TIMING`) all still hold. `MAX_LOOKBACK_BARS` is still
  `253`; lookbacks are still `{SPY: 1, A: 200, F4: 253, F1: 200, C: 200}`.
- `RosterEntry` gains two defaulted trailing fields. `paper.py`, `paper_check.py`, `veto.py` and
  every test construct it only through this module, so nothing else moves.

---

### Step 3: `store.py` — the read side carries the new columns

**File:** `engine/src/seer_engine/paper/store.py:104-152` (the `# --- roster rows` block, from the
section rule through `read_strategy`)

**Change:** project and carry the nine new columns, and add `read_roster_rows`. `StrategyRow`
gains `sub`/`icon` (which `roster.Row` needs and the row did not carry) plus the seven columns
migration 006 adds. Field order matches the SQL for readability; the row is constructed by
keyword in the one place it is constructed, so adding fields breaks no caller. This is the READ
side only — writing `status`/`paper_end` is phase 2's.

**Code** (replaces `store.py:104-152` exactly, section rule included):

```python
# --------------------------------------------------------------------------- roster rows


@dataclass(frozen=True)
class StrategyRow:
    """One ``strategies`` row as the paper command needs it.

    Structurally a ``paper.roster.Row``: ``roster.from_rows(read_roster_rows(conn))`` is the
    whole roster-from-data path, and neither module imports the other (``roster`` is pure;
    ``tests/test_strategy_purity.py`` globs it).

    ``status``, ``paper_end`` and ``promoted_from`` are migration 006's lifecycle columns;
    ``object_name``, ``registry_id``, ``gate_note`` and ``gate_applicable`` are its definition
    columns. They are nullable on rows that are not roster rows, and ``roster.from_row``
    validates them with a named error rather than defaulting them.
    """

    id: str
    name: str
    sub: str
    icon: str
    engine: str | None
    rules_id: str | None
    is_champion: bool
    is_benchmark: bool
    sort: int
    paper_start: date | None
    params: Mapping[str, Any]
    status: str = "active"
    paper_end: date | None = None
    promoted_from: str | None = None
    object_name: str | None = None
    registry_id: str | None = None
    gate_note: str | None = None
    gate_applicable: bool = True


_STRATEGY_SQL = (
    "SELECT id, name, sub, icon, engine, rules_id, is_champion, is_benchmark, sort, paper_start, "
    "params, status, paper_end, promoted_from, object_name, registry_id, gate_note, gate_applicable "
    "FROM strategies"
)


def _strategy(row: tuple) -> StrategyRow:
    (
        sid,
        name,
        sub,
        icon,
        engine,
        rules_id,
        champion,
        benchmark,
        sort,
        paper_start,
        params,
        status,
        paper_end,
        promoted_from,
        object_name,
        registry_id,
        gate_note,
        gate_applicable,
    ) = row
    return StrategyRow(
        id=sid,
        name=name,
        sub=sub,
        icon=icon,
        engine=engine,
        rules_id=rules_id,
        is_champion=bool(champion),
        is_benchmark=bool(benchmark),
        sort=int(sort),
        paper_start=paper_start,
        params=params if isinstance(params, dict) else {},
        status=status,
        paper_end=paper_end,
        promoted_from=promoted_from,
        object_name=object_name,
        registry_id=registry_id,
        gate_note=gate_note,
        gate_applicable=bool(gate_applicable),
    )


def read_strategies(conn: psycopg.Connection) -> tuple[StrategyRow, ...]:
    """Every ``strategies`` row, by (sort, id)."""
    rows = conn.execute(_STRATEGY_SQL + " ORDER BY sort, id").fetchall()
    return tuple(_strategy(r) for r in rows)


def read_roster_rows(conn: psycopg.Connection) -> tuple[StrategyRow, ...]:
    """The roster rows -- every ``strategies`` row with an ``engine`` -- by (sort, id).

    ``engine`` is the predicate because it is what the paper night dispatches on and what
    migration 003 set on exactly the roster's rows; a legacy display row that never traded has
    none. Retired rows ARE returned: a retired strategy keeps its history and its leaderboard
    place, and only ``roster.active`` drops it from a night. A row that has an ``engine`` but no
    usable ``object_name`` is NOT filtered out here -- ``roster.from_row`` raises
    ``UnknownObject`` for it, which is the point (invariant 9).
    """
    rows = conn.execute(_STRATEGY_SQL + " WHERE engine IS NOT NULL ORDER BY sort, id").fetchall()
    return tuple(_strategy(r) for r in rows)


def read_strategy(conn: psycopg.Connection, strategy_id: str) -> StrategyRow | None:
    """The ``strategies`` row ``strategy_id``, or None."""
    row = conn.execute(_STRATEGY_SQL + " WHERE id = %s", (strategy_id,)).fetchone()
    return None if row is None else _strategy(row)
```

**Impact:**
- `commands/paper.py:141` (`{row.id: row for row in store.read_strategies(conn)}`),
  `commands/paper_check.py:108` (`row.paper_start`), `store.freeze_spec:179` and
  `store.load_benchmark:918` read only fields that still exist. No caller moves in this phase.
- `engine/tests/test_paper_store.py:57` asserts `[r.id for r in rows]`, four fields on `rows[0]`,
  `rows[1].engine`/`rules_id`, and `all(r.paper_start is None and r.params == {} ...)`. Adding
  fields changes none of those; the test passes unchanged. **Do not edit that file** — phase 2
  owns `test_paper_store.py`.
- `commands/explain.py:87` defines its own unrelated `StrategyRow`; no collision.

---

### Step 4: Tests

**File:** `engine/tests/test_paper_roster.py` — append a new section at the end of the file
(after `test_the_roster_c_object_carries_no_verdicts`, currently the last test at `:261`), and
extend the import block at `:22-35`.

**Change:** no existing test is edited and `PINS` is not touched. Three of the fifteen new tests
take the `pg` fixture and are skipped without `PG_TEST_URL`.

**Code** — the import block at `:22-35` becomes:

```python
from seer_engine.paper.roster import (
    BENCHMARK_ID,
    BENCHMARK_OBJECT,
    MAX_LOOKBACK_BARS,
    RESOLVER,
    ROSTER,
    ROSTER_IDS,
    SEED_ROWS,
    BadRosterRow,
    RosterRow,
    UnknownObject,
    UnknownRules,
    active,
    backtest_gate,
    entry,
    from_row,
    from_rows,
    resolve,
    resolver_names,
    rules_dict,
    spec,
    spec_digest,
    spec_text,
    strategy_params,
)
```

and this section is appended to the end of the file:

```python
# ---- the roster is data (roster-promotion-pipeline phase 1, R2, D2) ------------------------------

import dataclasses  # noqa: E402 - section-local, kept beside the tests that use it

from seer_engine.paper import store  # noqa: E402

ROW_COLUMNS = (
    "id", "name", "sub", "icon", "is_champion", "is_benchmark", "sort", "engine", "rules_id",
    "object_name", "registry_id", "gate_note", "gate_applicable", "status", "paper_end",
)


def a_row(**overrides) -> RosterRow:
    """A valid bracket row, with the fields a test cares about overridden."""
    base = dict(
        id="X", name="X", sub="x", icon="x", is_champion=False, is_benchmark=False, sort=9,
        engine="bracket", rules_id="design-v0", object_name="STRATEGY_A", registry_id=None,
        gate_note="not a real strategy",
    )
    return RosterRow(**{**base, **overrides})


def test_the_roster_is_built_from_the_seed_rows_through_the_resolver():
    assert ROSTER == from_rows(SEED_ROWS)
    assert tuple(r.id for r in SEED_ROWS) == ROSTER_IDS
    assert {spec_digest(spec(e)) for e in from_rows(SEED_ROWS)} == set(PINS.values())


def test_every_seed_row_names_a_resolver_object():
    assert {r.object_name for r in SEED_ROWS} <= set(RESOLVER)
    assert resolver_names() == tuple(sorted(RESOLVER))
    assert resolve(BENCHMARK_OBJECT).obj is None
    assert resolve("FACTOR").from_registry and resolve("FACTOR").params is None
    assert resolve("STRATEGY_A").params is STRATEGY_A_PARAMS


def test_an_unresolvable_object_name_is_a_named_error_not_a_skip():
    with pytest.raises(UnknownObject, match="is not in paper.roster.RESOLVER"):
        from_row(a_row(object_name="STRATEGY_Z"))
    with pytest.raises(UnknownObject):
        from_row(a_row(object_name=None))
    with pytest.raises(UnknownObject):
        resolve("nope")
    # and one bad row poisons the whole build: nothing is silently dropped
    with pytest.raises(UnknownObject):
        from_rows([*SEED_ROWS, a_row(object_name="STRATEGY_Z")])


def test_an_unknown_rules_id_is_a_named_error():
    with pytest.raises(UnknownRules, match="is not a sim.rules preset"):
        from_row(a_row(rules_id="no-such-preset"))
    with pytest.raises(BadRosterRow, match="needs a rules_id"):
        from_row(a_row(rules_id=None))


def test_a_bad_engine_or_status_is_a_named_error():
    with pytest.raises(BadRosterRow, match="engine"):
        from_row(a_row(engine="quantum"))
    with pytest.raises(BadRosterRow, match="engine"):
        from_row(a_row(engine=None))
    with pytest.raises(BadRosterRow, match="status"):
        from_row(a_row(status="zombie"))
    with pytest.raises(BadRosterRow, match="gate_note"):
        from_row(a_row(gate_note=None))


def test_a_benchmark_row_carries_no_object_rules_or_registry_id():
    ok = a_row(id="B2", engine="benchmark", rules_id=None, object_name=BENCHMARK_OBJECT)
    assert (from_row(ok).obj, from_row(ok).params, from_row(ok).lookback) == (None, None, 1)
    with pytest.raises(BadRosterRow, match="benchmark row"):
        from_row(a_row(id="B2", engine="benchmark", rules_id="design-v0", object_name=BENCHMARK_OBJECT))
    with pytest.raises(BadRosterRow, match="benchmark engine"):
        from_row(a_row(engine="bracket", object_name=BENCHMARK_OBJECT))


def test_a_registry_backed_object_needs_its_registry_id_and_an_own_params_object_refuses_one():
    with pytest.raises(BadRosterRow, match="backtest.registry"):
        from_row(a_row(engine="book", rules_id="monthly-hold", object_name="FACTOR", registry_id=None))
    with pytest.raises(BadRosterRow, match="registry_id must be NULL"):
        from_row(a_row(registry_id=F4))


def test_from_rows_sorts_by_sort_and_refuses_duplicate_ids():
    shuffled = tuple(reversed(SEED_ROWS))
    assert tuple(e.id for e in from_rows(shuffled)) == ROSTER_IDS
    with pytest.raises(BadRosterRow, match="duplicate ids"):
        from_rows([*SEED_ROWS, dataclasses.replace(SEED_ROWS[1], sort=99)])


def test_the_seed_roster_is_all_active_with_no_paper_end():
    assert all(e.status == "active" and e.paper_end is None for e in ROSTER)
    assert active(ROSTER) == ROSTER
    assert active() == ROSTER


def test_active_drops_retired_entries_and_keeps_order():
    rows = tuple(
        dataclasses.replace(r, status="retired", paper_end=date(2026, 10, 2)) if r.id == "A" else r
        for r in SEED_ROWS
    )
    entries = from_rows(rows)
    assert [e.id for e in entries] == list(ROSTER_IDS)  # retired rows are never dropped from the roster
    assert [e.id for e in active(entries)] == ["SPY", F4, F1, "C"]
    a = next(e for e in entries if e.id == "A")
    assert (a.status, a.paper_end) == ("retired", date(2026, 10, 2))


def test_retiring_a_strategy_does_not_move_its_digest():
    """Invariant 2 and 3: status and paper_end are lifecycle, never spec."""
    retired = from_row(dataclasses.replace(SEED_ROWS[1], status="retired", paper_end=date(2026, 10, 2)))
    assert spec_digest(spec(retired)) == PINS["A"]
    assert strategy_params(retired) == strategy_params(entry("A"))


def test_a_corrected_gate_note_does_not_move_a_digest():
    corrected = from_row(dataclasses.replace(SEED_ROWS[1], gate_note="corrected, still failed"))
    assert spec_digest(spec(corrected)) == PINS["A"]
    assert backtest_gate(corrected)["note"] == "corrected, still failed"


def test_the_migration_rows_equal_the_seed_rows(pg):
    """Invariant 7, strengthened: not just the display fields, the whole row."""
    rows = pg.execute(
        f"SELECT {', '.join(ROW_COLUMNS)} FROM strategies ORDER BY sort, id"
    ).fetchall()
    assert tuple(RosterRow(**dict(zip(ROW_COLUMNS, r))) for r in rows) == SEED_ROWS


def test_the_database_rows_rebuild_the_roster_with_the_pinned_digests(pg):
    entries = from_rows(store.read_roster_rows(pg))
    assert entries == ROSTER
    assert {e.id: spec_digest(spec(e)) for e in entries} == PINS
    assert {e.id: strategy_params(e) for e in entries} == {e.id: strategy_params(e) for e in ROSTER}


def test_read_roster_rows_reads_the_new_columns_and_defaults_them(pg):
    rows = {r.id: r for r in store.read_roster_rows(pg)}
    assert [r.id for r in store.read_roster_rows(pg)] == list(ROSTER_IDS)
    assert all(r.status == "active" and r.paper_end is None and r.promoted_from is None for r in rows.values())
    assert (rows["A"].object_name, rows["A"].registry_id, rows["A"].gate_applicable) == ("STRATEGY_A", None, True)
    assert (rows[F4].object_name, rows[F4].registry_id) == ("FACTOR", F4)
    assert rows["C"].gate_applicable is False
    assert rows["SPY"].object_name == BENCHMARK_OBJECT
    pg.execute("UPDATE strategies SET status = 'retired', paper_end = %s WHERE id = 'A'", (date(2026, 10, 2),))
    retired = {r.id: r for r in store.read_roster_rows(pg)}["A"]
    assert (retired.status, retired.paper_end) == ("retired", date(2026, 10, 2))
    assert [e.id for e in active(from_rows(store.read_roster_rows(pg)))] == ["SPY", F4, F1, "C"]
    pg.rollback()


def test_the_status_check_refuses_an_unknown_status(pg):
    with pytest.raises(psycopg.errors.CheckViolation):
        pg.execute("UPDATE strategies SET status = 'zombie' WHERE id = 'A'")
    pg.rollback()
```

The file's existing imports at `:14-18` already give `date`, `pytest` and `json`;
`STRATEGY_A_PARAMS` and `F4` are already imported at `:38` and defined at `:49`. Add
`import psycopg` beside them (the file already imports `from psycopg.types.json import Jsonb`
at `:19`).

**Impact:** +15 tests. Twelve run always; three (`pg`) are skipped without `PG_TEST_URL`. No
existing test's result changes.

---

## Verification

**Build / import:**

```bash
"$SEER_PY" -c 'from seer_engine.paper import roster; print(roster.ROSTER_IDS, roster.MAX_LOOKBACK_BARS)'
# ('SPY', 'A', 'F4-MOM12-N20-TREND', 'F1-SPY-SMA200-M', 'C') 253
"$SEER_PY" -m ruff check engine/src engine/tests
```

**The invariant-2 check, run first and run alone:**

```bash
"$SEER_PY" -m pytest engine/tests/test_paper_roster.py -q
```

Every pinned digest in `PINS` must pass **unedited**. If a pin fails, the design is wrong — do
not touch `PINS`.

**Tests:**

```bash
"$SEER_PY" -m pytest engine/tests -q                       # without PG_TEST_URL
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres "$SEER_PY" -m pytest engine/tests -q
"$SEER_PY" -m pytest engine/tests/test_strategy_purity.py -q   # roster.py must stay pure
```

**Test DELTA** (off whatever this phase inherits — the set lands in a swarm, so never compare
absolutes):

| | passed | skipped |
|---|---|---|
| without `PG_TEST_URL` | **+12** | **+3** |
| with `PG_TEST_URL` | **+15** | 0 |

No existing test changes its result; no existing test is edited.

**Manual check:**

```bash
PGPASSWORD=pg psql -h localhost -p 55432 -U postgres -d postgres -c '\d strategies' | \
  grep -E 'status|paper_end|promoted_from|object_name|registry_id|gate_note|gate_applicable'
```

Seven rows, `status` and `gate_applicable` `not null` with defaults, the rest nullable.

**Exit criteria:**
- `006_roster.sql` adds the seven columns additively and backfills the five existing rows; no
  column is dropped, no CHECK narrowed, migrations 001–005 untouched (invariant 5).
- `roster.RESOLVER` maps a stable object name to the live object; `roster.from_rows` builds the
  whole roster from `strategies` rows, and `roster.ROSTER == from_rows(store.read_roster_rows(pg))`
  against a migrated database (invariant 7).
- All five pinned `spec_digest` values pass **unchanged** (invariant 2), and `spec_text` is
  byte-identical to `main`'s for `SPY`, `A`, `F4-MOM12-N20-TREND`, `F1-SPY-SMA200-M` and `C`.
- An unresolvable `object_name` raises `UnknownObject` and poisons the whole build rather than
  dropping one entry (invariant 9), covered by `test_an_unresolvable_object_name_is_a_named_error_not_a_skip`.
- `ROSTER`/`ROSTER_IDS`/`MAX_LOOKBACK_BARS`/`entry` keep working; `paper.py`, `paper_check.py`
  and `veto.py` are untouched and still pass.
- `roster.py` is still pure (`test_strategy_purity.py` passes).

---

## Handoffs

**To phase 2 (`commands/paper.py`, store write side, `paper_check.py`).**
- Swap `roster.ROSTER` at `commands/paper.py:143` and `:149` and `commands/paper_check.py:102`
  for `roster.from_rows(store.read_roster_rows(conn))`, then `roster.active(...)` to drop retired
  entries from the night. This phase deliberately does **not** make that swap: it would change
  which strategies trade, which is phase 2's exit criterion, not mine.
- `commands/paper.py:143-149` reads `store.read_strategies(conn)` into `rows` *and* iterates
  `roster.ROSTER`. Once the roster comes from rows, those are the same query; phase 2 should
  collapse them.
- Writing `status`/`paper_end` is phase 2's. I added **no setter** — `read_roster_rows` is read
  only, and nothing in this phase writes either column outside the migration's backfill.
- `paper_end` should be set to *the last session actually traded* (the entry's final
  `equity_snapshots.session_date`), not to the night retirement was noticed. Migration 006 adds
  no constraint tying `paper_end` to `paper_start` — I left that to phase 2, which owns the
  semantics; adding `CHECK (paper_end IS NULL OR paper_start IS NOT NULL)` in a 007 would be
  additive and is the natural place for it if phase 2 wants it.
- **Test-file boundary:** the index gives phase 2 `engine/tests/test_paper*.py`, which overlaps
  my `test_paper_roster.py`. I touch **only** `test_paper_roster.py`, and only by appending. I do
  not edit `test_paper_store.py`, `test_paper_command.py` or `test_paper_c.py` — verified each
  still passes with `StrategyRow`'s added fields.

**To phase 5 (`commands/promote.py`).** The insert shape and the validation hook are in the
Interface Contract. Two things phase 5 must take literally, because it planned against a guess:

- **`RESOLVER` is `dict[str, Binding]`, not `Mapping[str, object]`.** The live object is
  `binding.obj`, which is `None` for the benchmark. The inverse lookup `promote.object_name_of`
  must therefore scan `for name, b in roster.RESOLVER.items() if b.obj is obj`, and its
  "add one line" refusal message must quote a `Binding(...)` literal, not a bare object.
- **`promote` must call `roster.from_row` on the row it is about to write**, inside its
  transaction, and let `RosterError` abort it. That is a free, exact check that the row is
  buildable before it is committed, and it is why `from_row` takes a duck-typed `Row` rather than
  a connection. It also catches the one shape `promote` can otherwise get wrong: an INSERT that
  leaves `object_name`, `gate_note` or `gate_applicable` unset, which the night would then refuse
  with `UnknownObject`. `promoted_from` is the lab `methods.id`; nothing in this phase writes it.

**To phase 6 (`FND`).** The extension point is spelled out under *Exposed to phase 6* above —
one `RESOLVER` entry, one `SEED_ROWS` row, one migration carrying the same values. `from_row`,
`from_rows`, `spec` and the five pinned digests need no change. `ROSTER` is **not** a literal any
more, so there is no tuple to append an entry to: appending a `RosterRow` to `SEED_ROWS` is how a
sixth entry exists. If `FUNDAMENTAL`'s params value does not yet exist as a module-level constant
beside `FUNDAMENTAL`, phase 6 defines one in `roster.py` — it must not import `lab.methods.*`,
which would make a lab file an input to a paper spec digest.

**To phase 4 (`web/`).** `strategies.status` and `strategies.paper_end` are projectable now.
Two things I found and deliberately left:
- `web/scripts/seed-demo.mjs:307` inserts `strategies` with an explicit column list that does not
  include the new columns. The defaults make that safe (`status='active'`, `gate_applicable=true`),
  but `object_name` lands NULL in a demo database, so a demo leaderboard would show no
  `spec_object`-derived facts for them. `web/` is phase 4's, so I did not touch it.
- `web/lib/data.ts:67` projects `params->'spec'->>'object'`, which is NULL until a strategy has a
  `paper_start` — so a just-promoted row's `checksNews` reads NULL and the page loses a display
  fact for a night. With `object_name` now a column, phase 4 projects
  `COALESCE(params->'spec'->>'object', object_name) AS spec_object` instead. **Reconciled: phase 4
  makes that one-line change**; the frozen spec still wins where it exists, so nothing a started
  strategy shows can move.

**Not done, on purpose.** `engine/package_readme.md:1528` documents `StrategyRow`'s old field
list. Updating package docs is the `readme-updater`'s job at the end of the set, not a drive-by
edit inside a phase.

## Rollback

`git revert` the phase's single commit on `feature/roster-promotion-pipeline`. The code then no
longer reads the new columns.

The migration is additive, so reverting the code leaves seven harmless unused columns. To undo
the data as well:

```sql
UPDATE strategies SET status = 'active', paper_end = NULL, promoted_from = NULL;
```

Dropping the columns is possible but unnecessary and not recommended while any phase of this set
is still in flight:

```sql
ALTER TABLE strategies
  DROP COLUMN IF EXISTS status,
  DROP COLUMN IF EXISTS paper_end,
  DROP COLUMN IF EXISTS promoted_from,
  DROP COLUMN IF EXISTS object_name,
  DROP COLUMN IF EXISTS registry_id,
  DROP COLUMN IF EXISTS gate_note,
  DROP COLUMN IF EXISTS gate_applicable;
```

Nothing in this phase deletes a row, resets a paper clock, edits a started strategy's definition,
writes to Neon outside a migration, or touches the lab database. Production is unaffected until
the set is merged and a paper night runs.

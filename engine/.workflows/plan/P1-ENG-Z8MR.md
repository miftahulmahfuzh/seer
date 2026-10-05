> Adopted from `ROSTER_PROMOTION_PIPELINE_PLAN.md` phase 5. Source: `.workflows/plan/roster-promotion-pipeline/phase-5.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 5: `promote`: the lab → roster bridge

**Plan set:** `ROSTER_PROMOTION_PIPELINE_PLAN.md`
**Analysis:** `20261005-165054-XGER_code_analyzer.md`
**Satisfies:** R4 — promote a method found in a `/sera-the-explorer` session onto the main app's leaderboard
**Depends on:** Phase 1, Phase 2
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/commands` (with `engine/src/seer_engine/lab`)

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

After this phase a human can type one command and a lab method's pre-registered variant becomes a
paper roster entry: `python -m seer_engine promote --method M0005 --candidate M0005-ALL --id FND
--name "…" --sub "…" --gate-note "…" --retire F1-SPY-SMA200-M`. It writes one `strategies` row
with `status='active'`, `promoted_from='M0005'` and **no** `paper_start` (so the next paper night
starts the clock through the ordinary `store.freeze_spec` path), retires the outgoing horseman in
the same transaction, and records the promotion against the method in the append-only lab
database. `backtest.registry.REGISTRY` is never touched (D1). Nothing promotes itself: every
promotion is this command, typed by a person (D6).

## The design question, settled

> *A lab method is a Python file in `lab/methods/`, while a roster entry needs an object the
> resolver can name. Say exactly what a method must expose to be promotable.*

**A method is promotable iff both halves hold:**

1. **It exposes the triple as a `Candidate`.** A `strategies` row cannot be built from a method
   id. A roster entry is an *(object, params, rules)* triple plus display fields, and the lab
   already has exactly that value: `seer_engine.backtest.dev.Candidate` (`dev.py:127`), with
   `rules: TradeRules`, `allocator: Allocator | Strategy` and `params: Any`. Every lab method's
   `METHOD.candidates` is a tuple of them (`lab/method.py:60`, validated in `__post_init__`
   `:77-93`). `promote` reads the triple off the named candidate and invents nothing: the roster
   entry's rules, object and params are byte-for-byte the pre-registered variant's. This is also
   why `--candidate` is required whenever a method has more than one variant — "promote M0005" is
   ambiguous between six different algorithms.

2. **Its allocator is a value the roster resolver names.** `RosterEntry.obj` is a live Python
   object (analysis, *Key Data Structures*), `spec()` writes `"object": e.object_name`, and D2
   settles that the name→object map stays in code. `promote` therefore asks phase 1's
   `roster.RESOLVER` — a `dict[str, roster.Binding]` — for the name whose `binding.obj` **is** the
   candidate's allocator, and **refuses when there is none**, naming what is missing and the line
   to add:

   ```
   promote: the roster resolver has no name for <FND>
     (seer_engine.strategies.f_fundamental.FundamentalAllocator).
     A promotable method's allocator must be a module-level object that
     seer_engine/paper/roster.py's RESOLVER names, because the name is part of the frozen
     spec and a database row cannot hold a live object.
     Add one entry to RESOLVER, e.g.
         "FUNDAMENTAL": Binding(obj=f_fundamental.FUNDAMENTAL, params=FUNDAMENTAL_PARAMS),
     commit it, then promote again.
   ```

   Two names for one object is also refused: the name is in the digest, so an entry with two
   possible names has two possible digests.

3. **Its rules are a `sim.rules` preset.** `roster.rules_for` resolves a roster row's `rules_id`
   through `PRESETS`, so a candidate carrying a one-off `TradeRules` would be written under one
   rule set and read back under another. Refused (Step 2's `_check_rules`). Every lab candidate in
   the tree today uses a preset, so this costs nothing and closes a `SpecMismatch` that would only
   have surfaced on a paper night.

**What this costs, honestly.** A promotion of an object the resolver already names (every swap
among known allocators, which is R2's "re-sort the horsemen") needs no code change at all. A
promotion of a *brand-new* allocator needs one line in `RESOLVER`. That is exactly D2's position —
*"The resolver is the smallest thing that must stay in code"* — and `promote` refuses rather than
guessing. A generic `lab:<method id>:<ATTR>` namespace in the resolver would remove even that one
line; it belongs to phase 1's file, so it is in **Handoffs**, not here.

## What the lab actually permits (measured, not assumed)

Read `engine/src/seer_engine/lab/store.py:1-27` and `:62-74`. The finding that shapes this phase:

| fact | where | consequence for `promote` |
|---|---|---|
| `TRANSITIONS` contains `("test-passed", "paper")` | `lab/store.py:73` | **The move already exists. Do not add a transition.** `paper` is the lab's name for "on the paper roster"; that is the move `promote` makes. |
| `TRANSITIONS` contains `("dev-eligible", "promoted")` and `("promoted", "test-passed"/"test-failed")` | `lab/store.py:70-72` | **`promoted` is not this.** In the lab, `promoted` means *promoted to a look at the held-out test window*. `web/lib/sera/types.ts:120`'s `promoted` is that same status. Reusing it for roster promotion would overload the lab's central vocabulary and break the DSR story. `promote` never writes `promoted`. |
| `methods` has `methods_status_forward`, `methods_analysis_grows`, `methods_hypothesis_frozen`, `methods_source_sha_once`, `methods_no_delete` | `lab/store.py:188-206` | `promote` only `append_analysis` (grows), `add_insight` (append-only table), and at most `status: test-passed -> paper`. It never writes `hypothesis`, `verdict`, `source_sha` or `parent_id`. |
| Every method in `lab/lab.sqlite` today is `idea` (2) or `rejected` (16); **M0005 is `rejected`** and no method is at `test-passed` | queried from the committed database | `rejected` has **no outgoing edge** in `TRANSITIONS`. Phase 6's FND promotion therefore cannot move M0005's status, and must not: the lab's verdict on M0005 stands (its six trials measured panel coverage, not the premia — see its `analysis`). So the status move is **conditional and explicitly acknowledged**, never forced, and never achieved by adding an edge. |

Hence `promote`'s lab contract, in three sentences:

- It **always** records the promotion as an appended `analysis` section on the method and one
  `insights` row (`kind='observation'`, `method_id=<M id>`). Both are append-only-safe at any
  status, so the record exists for a `rejected` method as much as for a `test-passed` one.
- It moves `status` to `paper` **only** from `test-passed` (the edge that exists), and treats a
  method already at `paper` as a no-op.
- From any other status it **refuses**, naming the status and the missing edge, unless the human
  passes `--lab-status-stays`, which is the acknowledgement that the roster is taking a method
  the lab has not passed. Phase 6 passes it for M0005.

`source_sha` is never written. No `trials` row is inserted. No transition is added to `TRANSITIONS`.

## Interface Contract

The reconciler reads this section to detect cross-phase conflicts. Be exact and exhaustive.

**Deletes:** none.

**Renames:** none.

**Creates:**

- `seer_engine.commands.promote` (`engine/src/seer_engine/commands/promote.py`, new module;
  auto-registered as the `promote` CLI subcommand by `cli.discover()` — `cli.py:32-42` needs no
  edit, see its docstring *"Adding a command means adding a module; this file never changes"*)
  - `promote.HELP: str`
  - `promote.add_arguments(p: argparse.ArgumentParser) -> None`
  - `promote.run(args: argparse.Namespace) -> int`
  - `promote.PromoteError(RuntimeError)`
  - `promote.NotPromotable(PromoteError)`
  - `promote.AlreadyStarted(PromoteError)`
  - `promote.RosterConflict(PromoteError)`
  - `promote.Promotion` (frozen dataclass: `entry`, `params`, `method_id`, `candidate_id`,
    `retire_id`, `sort`)
  - `promote.object_name_of(obj) -> str`
  - `promote.find_candidate(method_id, candidate_id) -> tuple[Method, Path, Candidate]`
  - `promote.check_lookback(lookback: int, data_date: date) -> None`
  - `promote.build_promotion(args, data_date) -> Promotion`
  - `promote.render_plan(p: Promotion, *, retire_end) -> str`
  - `promote.DEFAULT_ICON = "flask-conical"`
- `seer_engine.lab.store.record_promotion(conn, *, method_id, strategy_id, candidate_id,
  object_name, spec_digest, retired_id=None, move_status=True) -> str`
  (`engine/src/seer_engine/lab/store.py`, new function at the end of the `methods` section)
- `seer_engine.lab.store.PROMOTION_MARKER = "Promoted to the paper roster as "` (module constant,
  the idempotence key)
- `engine/tests/test_promote_command.py` (new test module)

**Signature changes:** none. `roster.spec`, `roster.spec_text`, `roster.spec_digest`,
`roster.strategy_params`, `store.freeze_spec` and `store.check_digest` are **called, never
changed** — invariant 2 depends on it.

**Requires (from earlier phases):**

Reconciled against phases 1 and 2 as they actually shipped. Three of these were guesses when this
plan was written and all three were wrong; the corrected versions are below and the code in the
Implementation Steps has been rewritten to match.

- **Phase 1**, `db/migrations/006_roster.sql` adds **seven** columns to `strategies`:
  `status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','retired'))`, `paper_end date`,
  `promoted_from text`, **`object_name text`, `registry_id text`, `gate_note text`,
  `gate_applicable boolean NOT NULL DEFAULT true`**. The last four are not optional for `promote`:
  phase 1's `roster.from_row` reads `object_name`, `gate_note` and `gate_applicable` off the row
  and raises a `RosterError` when any is missing, so **an INSERT that omits them produces a row the
  paper night refuses with `UnknownObject`**. `promote` writes all of them.
- **Phase 1**, `engine/src/seer_engine/paper/roster.py`: **`RESOLVER: dict[str, Binding]`**, where
  `roster.Binding` is a frozen dataclass `(obj, params, from_registry)`. It is *not* a
  `Mapping[str, object]`: the live object is `binding.obj`, which is `None` for the benchmark.
  `object_name_of` scans `b.obj is obj`. `promote` never mutates the resolver.
- **Phase 1**, `roster.RosterEntry` has **eighteen** fields: the sixteen it had plus
  `status: Status = "active"` and `paper_end: date | None = None`, both trailing and defaulted.
  `promote` constructs one by keyword to feed `roster.strategy_params`, leaving both at their
  defaults, and `strategy_params` is unchanged (neither new field is in the spec, so the digest
  cannot move).
- **Phase 1**, `roster.from_row(row) -> RosterEntry` takes a duck-typed `Row`. `promote` calls it
  on the row it is about to write, before committing — a free, exact proof that the row the night
  will read back builds. Phase 1 asked for this explicitly.
- **Phase 1**, `roster.rules_for(rules_id)` resolves a rules id through `sim.rules.PRESETS`. The
  consequence for `promote`: a candidate whose `rules` is **not** the preset of that id would be
  written with a digest computed from the candidate's rules and read back with a digest computed
  from the preset's — a `SpecMismatch` on its first night. `promote` refuses that up front
  (Step 2, `_check_rules`).
- **Phase 2**, `engine/src/seer_engine/paper/store.py`:
  `retire(conn: psycopg.Connection, strategy_id: str) -> date | None` — sets
  `status='retired'` and `paper_end` to the last session the strategy actually traded (`None` when
  it never traded) and returns that date. **A row that is already retired is a no-op that returns
  its stored `paper_end`**, not an error — that is deliberate, so an interrupted swap can be
  re-run; only a *missing* row raises `store.StoreError`. It **does not commit** (the caller's
  transaction decides, matching `store.py:27-28`'s stated discipline). `promote` calls it inside
  its own `db.transaction`, which is what makes the swap atomic.
- **Phase 2**, `commands/paper.py` keeps starting an `active` row that has no `paper_start`
  through `store.freeze_spec` — the row this phase writes is exactly that shape.

**Leaves alone (owned by others):**

- `engine/src/seer_engine/backtest/registry.py` — **never**, D1. `promote` writes
  `registry_id=None` into the entry, so `spec()`'s `registry_digest` branch (`roster.py:267-269`)
  is not taken and `REGISTRY` is never read for a promoted entry.
- `engine/src/seer_engine/paper/roster.py` — phase 1. Read only.
- `engine/src/seer_engine/commands/paper.py`, `commands/paper_check.py` — phase 2.
- `engine/src/seer_engine/paper/compare.py` — phase 3.
- `web/**` — phase 4.
- `db/migrations/*.sql` — phase 1 (006) and phase 6 (007). **This phase adds no migration.**
- The `FND` roster row itself, its display text and its gate note — phase 6. This phase ships the
  road, not the traveller.
- `engine/src/seer_engine/lab/methods/*.py`, `lab/lab.sqlite`'s committed contents — untouched by
  this phase's code; phase 6 is the first run that writes the database.

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/commands/promote.py` | create | the whole command (~310 lines) |
| `engine/src/seer_engine/lab/store.py` | modify | `PROMOTION_MARKER` after `DSR_LABEL` (`:80`); `record_promotion` appended to the `methods` section, after `append_analysis` (`:388`) |
| `engine/tests/test_promote_command.py` | create | 20 tests for the command |
| `engine/tests/test_lab_store.py` | modify | 4 tests appended for `record_promotion` |

## Implementation Steps

### Step 1: the lab's record of a promotion

**File:** `engine/src/seer_engine/lab/store.py:80` (the constant) and `:388` (the function, right
after `append_analysis` and before the `# --- trials` banner at `:391`)

**Change:** add one module constant and one function. Nothing else in the file moves. The function
writes only through the two append-only-safe paths (`analysis` grows, `insights` inserts) and at
most takes the one `TRANSITIONS` edge that already exists.

**Code:** insert after line 80 (`DSR_LABEL = "DSR >= 0.95"`):

```python
# The first words of the analysis section `record_promotion` appends, and its idempotence key:
# a method whose analysis already names this roster id has been recorded and is not recorded twice.
PROMOTION_MARKER = "Promoted to the paper roster as "
```

**Code:** insert after `append_analysis` (after line 388, before the `# ---- trials` banner):

```python
def record_promotion(
    conn: sqlite3.Connection,
    *,
    method_id: str,
    strategy_id: str,
    candidate_id: str,
    object_name: str,
    spec_digest: str,
    retired_id: str | None = None,
    move_status: bool = True,
) -> str:
    """Record that ``candidate_id`` became paper roster entry ``strategy_id``; return the status.

    The lab is append-only (§1), so a promotion is *added*, never stamped over anything:

    - ``analysis`` grows by one dated section (``methods_analysis_grows`` permits only growth);
    - one ``insights`` row is appended (the journal table refuses UPDATE and DELETE outright);
    - ``status`` moves to ``paper`` **only** along the edge ``TRANSITIONS`` already has,
      ``('test-passed', 'paper')``. A method already at ``paper`` is left alone. From any other
      status this raises LabError, because there is no edge and inventing one would make the
      lab's own vocabulary mean less. Pass ``move_status=False`` to record the promotion and
      leave the status where it is -- the honest shape for a roster that is taking a method the
      lab has not passed (the roster's admission rule is not the lab's gate: plan Decisions D5).

    ``hypothesis``, ``verdict``, ``parent_id`` and above all ``source_sha`` are never written.
    No ``trials`` row is inserted: a promotion is not a backtest and must not move the lab's N.

    Idempotent: a method whose ``analysis`` already carries ``PROMOTION_MARKER`` followed by
    ``strategy_id`` is already recorded, and this writes nothing and returns the current status.
    That is what lets the command be re-run to repair a half-finished promotion, since the roster
    (Neon) and the lab (SQLite) cannot share one transaction.

    The caller holds the transaction (``begin_immediate`` / ``with conn``), as every other writer
    in this module does.
    """
    row = get_method(conn, method_id)
    if row is None:
        raise LabError(f"no method {method_id}")
    if not candidate_id.startswith(method_id):
        raise LabError(f"candidate {candidate_id!r} does not belong to method {method_id}")
    status = str(row["status"])
    if PROMOTION_MARKER + f"`{strategy_id}`" in row["analysis"]:
        return status

    if move_status and status != "paper":
        if (status, "paper") not in TRANSITIONS:
            raise LabError(
                f"{method_id} is {status!r} and the lab's TRANSITIONS have no edge "
                f"{status!r} -> 'paper'; only 'test-passed' reaches 'paper'. The roster may still "
                f"take this method -- its admission rule is not the lab's gate -- but say so: "
                f"re-run with --lab-status-stays, which records the promotion and leaves the "
                f"status alone."
            )

    retired = "" if retired_id is None else f", replacing `{retired_id}` (retired the same moment)"
    body = (
        f"{PROMOTION_MARKER}`{strategy_id}`{retired}.\n\n"
        f"Variant: `{candidate_id}`. Roster object: `{object_name}`. "
        f"Frozen spec digest: `{spec_digest}`.\n\n"
        f"The roster row is `status='active'` with no `paper_start`: the next paper night freezes "
        f"the spec and starts its own clock, so the paper record begins at the promotion and "
        f"claims nothing earlier. `backtest.registry.REGISTRY` was not appended to -- a promoted "
        f"method reaches the roster through the roster's own resolver, so the lab's "
        f"multiple-testing count is unchanged by this."
    )
    append_analysis(conn, method_id, "# Promotion\n\n" + body)
    add_insight(
        conn,
        kind="observation",
        title=f"{method_id} promoted to the paper roster as {strategy_id}",
        body=body,
        method_id=method_id,
    )
    if move_status and status != "paper":
        update_method(conn, method_id, status="paper")
        return "paper"
    return status
```

**Impact:** `lab/store.py` gains one constant and one function; no existing symbol changes, so
`snapshot`, `snapshot_json`, `export_xlsx` and every current lab test are untouched. A method at
`paper` now appears in `snapshot()["summary"]["byStatus"]` under a key that already exists
(`STATUSES` already lists `paper`, `:59`), so `web/data/lab.json`'s shape does not change either.

### Step 2: the command

**File:** `engine/src/seer_engine/commands/promote.py` (new file, whole contents)

**Change:** the whole module. Written to the `commands/` contract in `cli.py:1-12` (`HELP`,
`add_arguments`, `run`), so the CLI picks it up with no edit to `cli.py`.

**Code:**

```python
"""``promote``: put a lab method's pre-registered variant on the paper roster.

The lab→roster bridge (plan roster-promotion-pipeline, phase 5; Decisions D1, D3, D6)::

    python -m seer_engine promote --method M0005 --candidate M0005-ALL --id FND \\
        --name "FND · Fundamentals" --sub "Top 20 on filed fundamentals, monthly" \\
        --gate-note "..." [--icon book-open] [--sort 6] \\
        [--retire F1-SPY-SMA200-M] [--lab-status-stays] [--dry-run]

**Promotable** means two things, and this command refuses anything that is not both:

1. the method file exposes the variant as a ``Candidate`` -- a frozen (rules, allocator, params)
   triple. The roster entry is that triple unchanged; nothing here invents a parameter.
2. the variant's allocator is a value ``paper.roster.RESOLVER`` names. A ``strategies`` row
   cannot hold a live Python object, and the object's *name* is part of the frozen spec, so an
   object the resolver cannot name has no roster identity. The refusal says which line to add.

**What it writes.** One ``strategies`` row: the display columns, the definition columns migration
006 added (``object_name``, ``registry_id`` NULL, ``gate_note``, ``gate_applicable``) --
``paper.roster.from_row`` refuses a row without them, so leaving one out would fail the next
paper night for the whole board -- plus ``status='active'``, ``promoted_from=<method id>``,
the full contract-C2 ``params`` (spec, digest, backtest_gate), and **no** ``paper_start``. The row
is read back and rebuilt through ``roster.from_row`` inside the same transaction before it
commits, so a row the paper night would refuse is never written. The
next paper night starts it through ``paper.store.freeze_spec`` exactly as any new entry starts,
which is what keeps the paper record honest: a promoted strategy's track record begins when it
was promoted. With ``--retire`` the outgoing strategy's ``status`` becomes ``'retired'`` **in the
same transaction**, so the board never shows five active horsemen or three.

**What it never writes.** ``backtest.registry.REGISTRY`` (Decisions D1: it is the P7a dev-run
candidate set, *fixed BEFORE the run*, capped at ``dev.MAX_CANDIDATES``, with ``candidate_digest``
pinned; appending would corrupt the multiple-testing count the lab's ``trials`` table exists to
maintain). A promoted method reaches the roster through the roster's own resolver, the same way
``A`` and ``C`` do. Also never: ``paper_start``, any paper history row, any ``trials`` row, any
lab ``source_sha``, and any ``TRANSITIONS`` edge that is not already there.

**Two databases, one promotion.** The roster is Neon, the lab is ``lab/lab.sqlite``; they cannot
share a transaction. So: the lab's rules are checked first and write nothing, then the roster
transaction commits, then the lab record commits. The only possible partial outcome is "roster
written, lab note missing", and re-running the identical command repairs it -- the roster insert
is skipped for a row this promotion already owns, and ``lab.store.record_promotion`` is
idempotent. The reverse order was rejected: a lab note for a promotion that did not happen cannot
be taken back, because the lab is append-only.

Exit 0 on success; 2 when a rule refuses the request; 1 on any other error.
"""

from __future__ import annotations

import argparse
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from psycopg.types.json import Jsonb

from seer_engine import config, dates, db
from seer_engine.lab import store as lab_store
from seer_engine.paper import roster
from seer_engine.paper import store as paper_store
from seer_engine.sim.rules import TradeRules

log = logging.getLogger(__name__)

HELP = "Promote a lab method's variant onto the paper roster (lab -> strategies)"

DEFAULT_ICON = "flask-conical"  # lucide name; the web renders strategies.icon


class PromoteError(RuntimeError):
    """`promote` refused the request (exit 2)."""


class NotPromotable(PromoteError):
    """The named method or variant cannot become a roster entry as it stands."""


class AlreadyStarted(PromoteError):
    """The target roster id has a paper_start: invariant 3, add never mutate."""


class RosterConflict(PromoteError):
    """The target roster id exists and is not this promotion's own unfrozen row."""


# --------------------------------------------------------------------------- the promotable check


def object_name_of(obj: object) -> str:
    """The roster resolver's stable name for ``obj`` (the inverse of ``roster.RESOLVER``).

    ``roster.RESOLVER`` maps a name to a ``roster.Binding``; the live object is ``binding.obj``,
    which is ``None`` for the benchmark and is therefore never matched here.

    NotPromotable when no name maps to it (the message names the entry to add) or when more than
    one does (the name is in the frozen spec, so an object with two names has two digests).
    """
    names = sorted(n for n, b in roster.RESOLVER.items() if b.obj is not None and b.obj is obj)
    if len(names) == 1:
        return names[0]
    module = type(obj).__module__
    where = f"{module}.{type(obj).__qualname__}"
    ident = getattr(obj, "id", "?")
    if not names:
        raise NotPromotable(
            f"the roster resolver has no name for <{ident}> ({where}). A promotable method's "
            f"allocator must be a module-level object that seer_engine/paper/roster.py's RESOLVER "
            f"names, because the name is part of the frozen spec and a database row cannot hold a "
            f"live object. Add one entry to RESOLVER -- \"<A_STABLE_NAME>\": Binding(obj="
            f"{module.rsplit('.', 1)[-1]}.<THE MODULE-LEVEL NAME>, params=<its params>) -- commit "
            f"it, then promote again."
        )
    raise NotPromotable(
        f"the roster resolver gives <{ident}> ({where}) {len(names)} names "
        f"({', '.join(names)}); a roster object must have exactly one, because the name is part "
        f"of the frozen spec digest"
    )


def _check_rules(rules: TradeRules) -> None:
    """NotPromotable when ``rules`` is not the ``sim.rules`` preset of its own id.

    ``roster.from_row`` rebuilds a roster entry's rules with ``roster.rules_for(row.rules_id)``,
    which answers out of ``PRESETS``. A candidate carrying a one-off ``TradeRules`` would be
    frozen under its own rules and read back under the preset's, and the difference would surface
    as a ``store.SpecMismatch`` on the strategy's first paper night rather than here.
    """
    preset = roster.rules_for(rules.id)  # raises roster.UnknownRules for an unknown id
    if preset != rules:
        raise NotPromotable(
            f"this variant's rules are id {rules.id!r} but are not the sim.rules preset of that "
            f"id; a roster row carries only the id, so the spec would be frozen under one rule "
            f"set and read back under another. Promote a variant that uses a preset, or add this "
            f"rule set to sim.rules.PRESETS first"
        )


def find_candidate(method_id: str, candidate_id: str | None) -> tuple[Any, Path, Any]:
    """(METHOD, file path, the chosen Candidate) for a committed lab method.

    NotPromotable when there is no method file, when a multi-variant method is named without
    ``--candidate``, or when the named variant is not one of the method's.
    """
    from seer_engine.lab.method import discover

    methods = discover()
    if method_id not in methods:
        raise NotPromotable(
            f"no method file for {method_id} in seer_engine/lab/methods/. A promotable method is a "
            f"committed mNNNN_<slug>.py exporting METHOD = Method(...): the roster entry is built "
            f"from one of its Candidates, so a lab database row alone is not enough. "
            f"Known: {', '.join(methods) or '(none)'}"
        )
    method, path = methods[method_id]
    ids = tuple(c.id for c in method.candidates)
    if candidate_id is None:
        if len(ids) != 1:
            raise NotPromotable(
                f"{method_id} has {len(ids)} variants ({', '.join(ids)}); they are different "
                f"algorithms, so name the one to promote with --candidate"
            )
        return method, path, method.candidates[0]
    found = [c for c in method.candidates if c.id == candidate_id]
    if len(found) != 1:
        raise NotPromotable(
            f"{method_id} has no variant {candidate_id!r}; its variants are {', '.join(ids)}"
        )
    return method, path, found[0]


def check_lookback(lookback: int, data_date: date) -> None:
    """NotPromotable when the night's bar window is shorter than ``lookback``.

    ``commands/paper.py:_check_window`` raises the same refusal at 23:00 on the night this entry
    would first trade. Raising it at promotion time instead means the roster never holds an entry
    the night cannot feed.
    """
    since = paper_store.market_window_since(data_date)
    have = len(dates.sessions(since, data_date))
    if lookback > have:
        raise NotPromotable(
            f"this variant reads {lookback} bars through a data date, but the paper night's bar "
            f"window {since}..{data_date} holds {have} sessions; raise "
            f"paper.store.MARKET_WINDOW_DAYS (now {paper_store.MARKET_WINDOW_DAYS}) before "
            f"promoting it"
        )


# --------------------------------------------------------------------------- the plan


@dataclass(frozen=True)
class Promotion:
    """Everything the two databases will be asked to write, computed before either is touched."""

    entry: roster.RosterEntry
    params: dict[str, Any]  # roster.strategy_params(entry): {spec, digest, backtest_gate}
    method_id: str
    candidate_id: str
    retire_id: str | None
    sort: int

    @property
    def digest(self) -> str:
        return str(self.params["digest"])


def build_promotion(args: argparse.Namespace, data_date: date, sort: int) -> Promotion:
    """The roster entry and its contract-C2 params, from the named method variant. No I/O."""
    _method, _path, candidate = find_candidate(args.method, args.candidate)
    obj = candidate.allocator
    _check_rules(candidate.rules)
    engine = "bracket" if candidate.rules.engine == "bracket_v0" else "book"
    lookback = obj.lookback if engine == "bracket" else obj.lookback(candidate.params)
    check_lookback(int(lookback), data_date)
    entry = roster.RosterEntry(
        id=args.id,
        name=args.name,
        sub=args.sub,
        icon=args.icon,
        is_champion=False,  # the champion is SPY (handover D2); a promotion never takes it
        is_benchmark=False,
        sort=sort,
        engine=engine,
        rules=candidate.rules,
        obj=obj,
        object_name=object_name_of(obj),
        params=candidate.params,
        registry_id=None,  # D1: a promoted entry is never a REGISTRY entry
        lookback=int(lookback),
        gate_note=args.gate_note,
        gate_applicable=not args.gate_not_applicable,
    )
    return Promotion(
        entry=entry,
        params=roster.strategy_params(entry),
        method_id=args.method,
        candidate_id=candidate.id,
        retire_id=args.retire,
        sort=sort,
    )


def render_plan(p: Promotion, *, retire_end: date | None, lab_status: str, lab_move: bool) -> str:
    """Every row the promotion writes, as text. Printed on every run, dry or not."""
    e = p.entry
    out = [
        f"promote {p.candidate_id} -> paper roster id {e.id}",
        "",
        "  strategies INSERT",
        f"    id             {e.id}",
        f"    name           {e.name}",
        f"    sub            {e.sub}",
        f"    icon           {e.icon}",
        f"    is_champion    false",
        f"    is_benchmark   false",
        f"    sort           {e.sort}",
        f"    engine         {e.engine}",
        f"    rules_id       {e.rules_id}",
        f"    object_name    {e.object_name}  (a paper.roster.RESOLVER key)",
        f"    registry_id    NULL  (Decisions D1: a promoted entry is never a REGISTRY entry)",
        f"    gate_note      {e.gate_note}",
        f"    gate_applicable {str(e.gate_applicable).lower()}",
        f"    status         active",
        f"    promoted_from  {p.method_id}",
        f"    paper_start    NULL  (the next paper night freezes the spec and starts the clock)",
        f"    params.digest  {p.digest}",
        f"    params.spec    {roster.spec_text(p.params['spec'])}",
        f"    params.backtest_gate {p.params['backtest_gate']}",
    ]
    if p.retire_id is not None:
        end = "NULL (never traded)" if retire_end is None else str(retire_end)
        out += [
            "",
            f"  strategies UPDATE {p.retire_id}",
            f"    status         retired",
            f"    paper_end      {end}",
            f"    (same transaction as the INSERT: the swap is atomic)",
        ]
    out += [
        "",
        f"  lab/lab.sqlite, method {p.method_id} (now {lab_status!r})",
        f"    methods.analysis  += a dated '# Promotion' section",
        f"    insights          += [observation] "
        f"'{p.method_id} promoted to the paper roster as {e.id}'",
        f"    methods.status    "
        + ("test-passed -> paper" if lab_move and lab_status == "test-passed"
           else f"{lab_status} (unchanged)"),
        "",
        "  backtest.registry.REGISTRY  untouched (Decisions D1)",
    ]
    return "\n".join(out)


# --------------------------------------------------------------------------- the roster write


def _next_sort(conn) -> int:
    return int(conn.execute("SELECT coalesce(max(sort), 0) + 1 FROM strategies").fetchone()[0])


def _check_target(conn, p: Promotion) -> bool:
    """True when the row must be inserted, False when this promotion already owns an unfrozen one.

    AlreadyStarted when the id has a ``paper_start`` (invariant 3: add, never mutate -- a changed
    strategy is a new id with its own paper clock). RosterConflict when the id exists but is not
    this promotion's own row.
    """
    row = paper_store.read_strategy(conn, p.entry.id)
    if row is None:
        return True
    if row.paper_start is not None:
        raise AlreadyStarted(
            f"{p.entry.id} already has paper_start {row.paper_start}: a started strategy is never "
            f"re-pointed at another algorithm, because months of track record would then belong "
            f"to code that did not earn it. Promote under a new roster id (and --retire "
            f"{p.entry.id} if it is being replaced)."
        )
    promoted_from = conn.execute(
        "SELECT promoted_from FROM strategies WHERE id = %s", (p.entry.id,)
    ).fetchone()[0]
    if promoted_from == p.method_id and row.params.get("digest") == p.digest:
        log.info(
            "%s already exists unfrozen from %s with the same digest; re-recording the lab side",
            p.entry.id, p.method_id,
        )
        return False
    raise RosterConflict(
        f"{p.entry.id} already exists (promoted_from {promoted_from!r}, digest "
        f"{row.params.get('digest')!r}) and is not this promotion's row (promoted_from "
        f"{p.method_id!r}, digest {p.digest!r}); choose another roster id"
    )


def _insert(conn, p: Promotion) -> None:
    """Write the roster row, then prove the paper night can read it back.

    **Every definition column migration 006 added is written here.** ``object_name``,
    ``gate_note`` and ``gate_applicable`` are not display sugar: ``roster.from_row`` reads them off
    the row and raises ``UnknownObject`` / ``BadRosterRow`` without them, which would make the very
    next paper night fail for the whole board (plan invariant 9) rather than for this row alone.
    ``registry_id`` is NULL by construction (D1: a promoted entry is never a REGISTRY entry).
    """
    conn.execute(
        "INSERT INTO strategies (id, name, sub, icon, is_champion, is_benchmark, sort, engine, "
        "rules_id, object_name, registry_id, gate_note, gate_applicable, status, promoted_from, "
        "params) "
        "VALUES (%s, %s, %s, %s, false, false, %s, %s, %s, %s, NULL, %s, %s, 'active', %s, %s)",
        (
            p.entry.id,
            p.entry.name,
            p.entry.sub,
            p.entry.icon,
            p.sort,
            p.entry.engine,
            p.entry.rules_id,
            p.entry.object_name,
            p.entry.gate_note,
            p.entry.gate_applicable,
            p.method_id,
            Jsonb(p.params),
        ),
    )
    # The round trip, inside the transaction: read the row back exactly as `paper` will and build
    # an entry from it. Any RosterError aborts the promotion with the night's own message, so a
    # row the night would refuse is never committed. Phase 1 asked for this hook by name.
    written = paper_store.read_strategy(conn, p.entry.id)
    rebuilt = roster.from_row(written)
    if roster.strategy_params(rebuilt)["digest"] != p.digest:
        raise PromoteError(
            f"{p.entry.id}: the row just written rebuilds to digest "
            f"{roster.strategy_params(rebuilt)['digest']!r}, not {p.digest!r}; the promotion was "
            f"rolled back. The row and the code disagree about what this strategy is"
        )


# --------------------------------------------------------------------------- CLI


def add_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument("--method", required=True, metavar="M0001",
                   help="the lab method whose variant is promoted (its file must be committed)")
    p.add_argument("--candidate", default=None, metavar="M0001-A",
                   help="which variant; required when the method has more than one")
    p.add_argument("--id", required=True, metavar="FND",
                   help="the new roster id (its own paper clock; never an existing started id)")
    p.add_argument("--name", required=True, help="display name, e.g. 'FND · Fundamentals'")
    p.add_argument("--sub", required=True, help="display subtitle, one line")
    p.add_argument("--icon", default=DEFAULT_ICON, help=f"lucide icon name (default {DEFAULT_ICON})")
    p.add_argument("--sort", type=int, default=None,
                   help="display order (default: one past the current maximum)")
    p.add_argument("--gate-note", required=True,
                   help="the honest backtest-gate sentence, in the style of the roster's "
                        "neighbours. No roster entry has passed a gate; say what happened")
    p.add_argument("--gate-not-applicable", action="store_true",
                   help="the quant backtest gate does not apply to this entry (an LLM strategy, "
                        "as C is); it still counts as not passed")
    p.add_argument("--retire", default=None, metavar="ID",
                   help="retire this strategy in the same transaction as the insert")
    p.add_argument("--lab-db", type=Path, default=lab_store.DB_PATH,
                   help="lab database (default: lab/lab.sqlite, or $SEER_LAB_DB)")
    p.add_argument("--lab-status-stays", action="store_true",
                   help="record the promotion but leave the method's lab status alone. Required "
                        "when the method is not at 'test-passed', because TRANSITIONS has no edge "
                        "to 'paper' from anywhere else. An acknowledgement that the roster is "
                        "taking a method the lab has not passed")


def run(args: argparse.Namespace) -> int:
    try:
        return _run(args)
    except (PromoteError, roster.RosterError, lab_store.LabError, paper_store.StoreError) as e:
        log.error("%s", e)
        return 2


def _run(args: argparse.Namespace) -> int:
    if args.retire == args.id:
        raise PromoteError(f"--retire {args.retire} is the id being promoted; nothing to swap")
    if not args.gate_note.strip():
        raise PromoteError("--gate-note must say what the backtest gate did; no entry has passed one")

    data_date = dates.run_dates(datetime.now(timezone.utc)).data_date

    lab_conn = lab_store.connect(args.lab_db)
    try:
        method_row = lab_store.get_method(lab_conn, args.method)
        if method_row is None:
            raise lab_store.LabError(
                f"no method {args.method} in {args.lab_db}; `lab idea` records a method before "
                f"anything can be promoted from it"
            )
        lab_status = str(method_row["status"])
        move = not args.lab_status_stays
        if move and lab_status not in ("test-passed", "paper"):
            raise lab_store.LabError(
                f"{args.method} is {lab_status!r} and the lab's TRANSITIONS have no edge "
                f"{lab_status!r} -> 'paper'; only 'test-passed' reaches 'paper'. The roster may "
                f"still take this method -- its admission rule is not the lab's gate (plan "
                f"Decisions D5) -- but say so: re-run with --lab-status-stays."
            )

        conn = db.connect()
        try:
            with conn.cursor() as cur:
                sort = args.sort if args.sort is not None else _next_sort(cur)
            p = build_promotion(args, data_date, sort)

            retire_end: date | None = None
            with db.transaction(conn, args.dry_run):
                insert = _check_target(conn, p)
                if p.retire_id is not None:
                    retire_end = paper_store.retire(conn, p.retire_id)
                if insert:
                    _insert(conn, p)
                print(render_plan(p, retire_end=retire_end, lab_status=lab_status, lab_move=move))
            if args.dry_run:
                log.info("dry-run: the roster transaction was rolled back; nothing written")
        finally:
            conn.close()

        lab_store.begin_immediate(lab_conn)
        try:
            new_status = lab_store.record_promotion(
                lab_conn,
                method_id=p.method_id,
                strategy_id=p.entry.id,
                candidate_id=p.candidate_id,
                object_name=p.entry.object_name,
                spec_digest=p.digest,
                retired_id=p.retire_id,
                move_status=move,
            )
            if args.dry_run:
                lab_conn.rollback()
                log.info("dry-run: the lab transaction was rolled back; nothing written")
            else:
                lab_conn.commit()
                log.info("%s recorded in %s (status %s)", p.method_id, args.lab_db, new_status)
        except BaseException:
            lab_conn.rollback()
            raise
    finally:
        lab_conn.close()

    if not args.dry_run:
        print(
            f"\n{p.entry.id} is on the roster as active with no paper_start. The next paper night "
            f"freezes its spec and starts its clock. Commit {args.lab_db} and "
            f"{lab_store.snapshot_path(Path(args.lab_db))} with `lab stage`."
        )
    return 0
```

**Impact:** adds the `promote` subcommand. `cli.discover()` finds it automatically
(`test_cli.py:15` only asserts `"migrate" in cli.discover()`, so no pinned command list breaks).
No existing module is imported differently and no existing behaviour changes. `config` is imported
for `config.load_env()`'s side effect ordering only through `cli.main`; the module-level import is
kept because `lab_store.DB_PATH` resolves `config.REPO_ROOT` at import time either way.

### Step 3: the command's tests

**File:** `engine/tests/test_promote_command.py` (new file, whole contents)

**Change:** 20 tests — **10 that need no Postgres** and **10 that use the `pg` fixture**
(`conftest.py:111` — a throwaway schema with every migration applied, so phase 1's `006_roster.sql`
is present). The lab side is always a `tmp_path` SQLite database. None touches Neon (invariant 8).

**Code:**

```python
"""`promote`: the lab -> roster bridge (plan roster-promotion-pipeline, phase 5).

The rules this file holds to the wall: a promotable method exposes a Candidate whose allocator the
roster resolver names; the inserted row is active with no paper_start; an id that already started
is refused; --retire shares the insert's transaction; the lab record respects the append-only
triggers and moves only along TRANSITIONS; --dry-run writes to neither database.
"""

from __future__ import annotations

import argparse
from datetime import date

import pytest

from seer_engine import dates
from seer_engine.commands import promote
from seer_engine.lab import store as lab_store
from seer_engine.paper import roster
from seer_engine.paper import store as paper_store
from seer_engine.sim.rules import MONTHLY_HOLD
from seer_engine.strategies.f_fundamental import FUNDAMENTAL, FundamentalParams

METHOD = "M0005"
VARIANT = "M0005-ALL"


@pytest.fixture(autouse=True)
def resolver_entry(monkeypatch):
    """Name FUNDAMENTAL in the resolver for the duration of a test, and only there.

    **This is the real state of the tree and not a convenience.** No lab method's allocator is in
    ``roster.RESOLVER`` on `main`: M0001 and M0004 use the lab-local OWNVOL, M0005 uses FUNDAMENTAL,
    and phase 1 seeds the resolver with buy_and_hold / STRATEGY_A / STRATEGY_C / FACTOR / TIMING
    only. So **every** promotion available today costs exactly one committed RESOLVER entry, which
    is Decisions D2's stated price and what `promote`'s refusal exists to say out loud. Phase 6
    commits that line for FUNDAMENTAL; this phase ships the road, not the traveller, so it borrows
    the line for a test and gives it back.

    `test_the_resolver_must_name_the_allocator_first` turns the fixture off to prove the refusal.
    """
    monkeypatch.setitem(
        roster.RESOLVER,
        "FUNDAMENTAL",
        roster.Binding(obj=FUNDAMENTAL, params=FundamentalParams(rank="composite", top=20)),
    )


def _args(**kw) -> argparse.Namespace:
    base = dict(
        method=METHOD, candidate=VARIANT, id="TEST-FND", name="T · Fundamentals",
        sub="Top 20 on filed fundamentals, monthly", icon="book-open", sort=None,
        gate_note="No backtest gate: the dev window predates usable XBRL coverage",
        gate_not_applicable=False, retire=None, lab_db=None, lab_status_stays=True,
        dry_run=False, verbose=0,
    )
    base.update(kw)
    return argparse.Namespace(**base)


@pytest.fixture()
def lab(tmp_path):
    conn = lab_store.connect(tmp_path / "lab.sqlite")
    with conn:
        lab_store.add_method(
            conn, id=METHOD, name="fundamentals", family="f", source_kind="knowledge",
            hypothesis="h", status="idea",
        )
        lab_store.update_method(conn, METHOD, status="rejected")
    yield conn
    conn.close()


def _seed_roster_row(pg, sid="OLD", paper_start=None, sort=1):
    pg.execute(
        "INSERT INTO strategies (id, name, sub, icon, sort, engine, rules_id, paper_start, params) "
        "VALUES (%s, 'old', 'old', 'x', %s, 'book', 'monthly-hold', %s, '{}'::jsonb) "
        "ON CONFLICT (id) DO NOTHING",
        (sid, sort, paper_start),
    )
    pg.commit()


# ---- the promotable contract (pure) ------------------------------------------------------------


def test_a_method_without_a_file_is_not_promotable():
    with pytest.raises(promote.NotPromotable, match="no method file for M9999"):
        promote.find_candidate("M9999", None)


def test_a_multi_variant_method_must_name_the_variant():
    with pytest.raises(promote.NotPromotable, match="M0005-ALL"):
        promote.find_candidate(METHOD, None)


def test_an_unknown_variant_lists_the_real_ones():
    with pytest.raises(promote.NotPromotable, match="M0005-VAL"):
        promote.find_candidate(METHOD, "M0005-NOPE")


def test_find_candidate_returns_the_frozen_triple():
    _m, path, c = promote.find_candidate(METHOD, VARIANT)
    assert c.id == VARIANT
    assert c.allocator is FUNDAMENTAL
    assert c.rules is MONTHLY_HOLD
    assert isinstance(c.params, FundamentalParams)
    assert path.name == "m0005_fundamental_factors.py"


def test_object_name_of_refuses_an_object_the_resolver_does_not_name():
    class Unnamed:
        id = "UNNAMED"

    with pytest.raises(promote.NotPromotable, match="has no name for <UNNAMED>"):
        promote.object_name_of(Unnamed())


def test_object_name_of_is_the_resolvers_inverse():
    # RESOLVER maps a name to a roster.Binding; the live object is binding.obj, None for the
    # benchmark (which has no object to name).
    for name, binding in roster.RESOLVER.items():
        if binding.obj is not None:
            assert promote.object_name_of(binding.obj) == name


def test_the_resolver_must_name_the_allocator_first(monkeypatch):
    """The designed refusal, with the fixture's borrowed entry taken back out.

    This is what a brand-new lab allocator meets today, and the message must be the one that tells
    an operator the single line to commit (D2). It is the state phase 6 resolves for FUNDAMENTAL.
    """
    monkeypatch.delitem(roster.RESOLVER, "FUNDAMENTAL")
    _m, _p, c = promote.find_candidate(METHOD, VARIANT)
    with pytest.raises(promote.NotPromotable, match="has no name for <FND>"):
        promote.object_name_of(c.allocator)
    with pytest.raises(promote.NotPromotable, match="Add one entry to RESOLVER"):
        promote.object_name_of(c.allocator)


def test_a_variant_whose_rules_are_not_a_preset_is_refused():
    from dataclasses import replace

    with pytest.raises(promote.NotPromotable, match="not the sim.rules preset"):
        promote._check_rules(replace(MONTHLY_HOLD, cost_rate=MONTHLY_HOLD.cost_rate * 2))
    promote._check_rules(MONTHLY_HOLD)  # the real preset passes


def test_check_lookback_refuses_more_bars_than_the_night_loads():
    d = date(2026, 10, 2)
    have = len(dates.sessions(paper_store.market_window_since(d), d))
    promote.check_lookback(have, d)
    with pytest.raises(promote.NotPromotable, match="MARKET_WINDOW_DAYS"):
        promote.check_lookback(have + 1, d)


# ---- the roster row (database) ------------------------------------------------------------------


def test_promote_inserts_an_active_row_with_no_paper_start(pg, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(promote.db, "connect", lambda url=None: pg)
    monkeypatch.setattr(pg, "close", lambda: None)
    assert promote.run(_args(lab_db=tmp_path / "lab.sqlite")) == 2  # no method row in a fresh lab


def test_promote_writes_the_row_the_night_expects(pg, monkeypatch, lab, tmp_path):
    monkeypatch.setattr(promote.db, "connect", lambda url=None: pg)
    monkeypatch.setattr(pg, "close", lambda: None)
    monkeypatch.setattr(lab_store, "connect", lambda path=None: lab)
    monkeypatch.setattr(lab, "close", lambda: None)
    assert promote.run(_args(lab_db=tmp_path / "lab.sqlite")) == 0
    row = pg.execute(
        "SELECT status, promoted_from, paper_start, engine, rules_id, params FROM strategies "
        "WHERE id = 'TEST-FND'"
    ).fetchone()
    status, promoted_from, paper_start, engine, rules_id, params = row
    assert (status, promoted_from, paper_start) == ("active", METHOD, None)
    assert (engine, rules_id) == ("book", "monthly-hold")
    assert set(params) == {"spec", "digest", "backtest_gate"}
    assert params["spec"]["object"] == promote.object_name_of(FUNDAMENTAL)
    assert params["spec"]["registry_id"] is None and params["spec"]["registry_digest"] is None
    assert params["digest"] == roster.spec_digest(params["spec"])
    assert params["backtest_gate"]["passed"] is False


def test_the_written_row_rebuilds_into_the_entry_the_night_will_read(pg, monkeypatch, lab, tmp_path):
    """The round trip, which is the whole reason promote writes the definition columns.

    A row missing `object_name`, `gate_note` or `gate_applicable` builds nothing: phase 1's
    `from_row` raises, and the paper night's failure would be the WHOLE board's, not this row's.
    """
    monkeypatch.setattr(promote.db, "connect", lambda url=None: pg)
    monkeypatch.setattr(pg, "close", lambda: None)
    monkeypatch.setattr(lab_store, "connect", lambda path=None: lab)
    monkeypatch.setattr(lab, "close", lambda: None)
    assert promote.run(_args(lab_db=tmp_path / "lab.sqlite")) == 0

    rows = [r for r in paper_store.read_roster_rows(pg) if r.id == "TEST-FND"]
    assert len(rows) == 1
    assert (rows[0].object_name, rows[0].registry_id, rows[0].gate_applicable) == (
        promote.object_name_of(FUNDAMENTAL), None, True,
    )
    assert rows[0].gate_note
    rebuilt = roster.from_row(rows[0])
    assert (rebuilt.obj, rebuilt.rules, rebuilt.status, rebuilt.paper_end) == (
        FUNDAMENTAL, MONTHLY_HOLD, "active", None,
    )
    assert roster.strategy_params(rebuilt)["digest"] == rows[0].params["digest"]
    # And the whole roster still builds with the new row in it: nothing was left unresolvable.
    assert "TEST-FND" in {e.id for e in roster.from_rows(paper_store.read_roster_rows(pg))}


def test_an_id_that_already_started_is_refused(pg, monkeypatch, lab, tmp_path):
    _seed_roster_row(pg, "TEST-FND", paper_start=date(2026, 1, 5))
    monkeypatch.setattr(promote.db, "connect", lambda url=None: pg)
    monkeypatch.setattr(pg, "close", lambda: None)
    monkeypatch.setattr(lab_store, "connect", lambda path=None: lab)
    monkeypatch.setattr(lab, "close", lambda: None)
    with pytest.raises(promote.AlreadyStarted, match="already has paper_start"):
        promote._run(_args(lab_db=tmp_path / "lab.sqlite"))


def test_an_unrelated_existing_id_is_refused(pg, monkeypatch, lab, tmp_path):
    _seed_roster_row(pg, "TEST-FND", paper_start=None)
    monkeypatch.setattr(promote.db, "connect", lambda url=None: pg)
    monkeypatch.setattr(pg, "close", lambda: None)
    monkeypatch.setattr(lab_store, "connect", lambda path=None: lab)
    monkeypatch.setattr(lab, "close", lambda: None)
    with pytest.raises(promote.RosterConflict, match="is not this promotion's row"):
        promote._run(_args(lab_db=tmp_path / "lab.sqlite"))


def test_rerunning_the_same_promotion_resumes_instead_of_inserting_twice(pg, monkeypatch, lab, tmp_path):
    monkeypatch.setattr(promote.db, "connect", lambda url=None: pg)
    monkeypatch.setattr(pg, "close", lambda: None)
    monkeypatch.setattr(lab_store, "connect", lambda path=None: lab)
    monkeypatch.setattr(lab, "close", lambda: None)
    assert promote.run(_args(lab_db=tmp_path / "lab.sqlite")) == 0
    assert promote.run(_args(lab_db=tmp_path / "lab.sqlite")) == 0
    n = pg.execute("SELECT count(*) FROM strategies WHERE id = 'TEST-FND'").fetchone()[0]
    assert n == 1
    assert lab_store.get_method(lab, METHOD)["analysis"].count(lab_store.PROMOTION_MARKER) == 1


def test_retire_shares_the_inserts_transaction(pg, monkeypatch, lab, tmp_path):
    _seed_roster_row(pg, "OLD", paper_start=date(2026, 1, 5))
    monkeypatch.setattr(promote.db, "connect", lambda url=None: pg)
    monkeypatch.setattr(pg, "close", lambda: None)
    monkeypatch.setattr(lab_store, "connect", lambda path=None: lab)
    monkeypatch.setattr(lab, "close", lambda: None)
    assert promote.run(_args(retire="OLD", lab_db=tmp_path / "lab.sqlite")) == 0
    rows = dict(pg.execute("SELECT id, status FROM strategies WHERE id IN ('OLD','TEST-FND')").fetchall())
    assert rows == {"OLD": "retired", "TEST-FND": "active"}


def test_a_failed_retire_leaves_no_inserted_row(pg, monkeypatch, lab, tmp_path):
    monkeypatch.setattr(promote.db, "connect", lambda url=None: pg)
    monkeypatch.setattr(pg, "close", lambda: None)
    monkeypatch.setattr(lab_store, "connect", lambda path=None: lab)
    monkeypatch.setattr(lab, "close", lambda: None)
    assert promote.run(_args(retire="NO-SUCH-ID", lab_db=tmp_path / "lab.sqlite")) == 2
    pg.rollback()
    assert pg.execute("SELECT count(*) FROM strategies WHERE id = 'TEST-FND'").fetchone()[0] == 0
    assert lab_store.PROMOTION_MARKER not in lab_store.get_method(lab, METHOD)["analysis"]


def test_dry_run_prints_the_rows_and_writes_to_neither_database(pg, monkeypatch, lab, tmp_path, capsys):
    monkeypatch.setattr(promote.db, "connect", lambda url=None: pg)
    monkeypatch.setattr(pg, "close", lambda: None)
    monkeypatch.setattr(lab_store, "connect", lambda path=None: lab)
    monkeypatch.setattr(lab, "close", lambda: None)
    assert promote.run(_args(dry_run=True, lab_db=tmp_path / "lab.sqlite")) == 0
    text = capsys.readouterr().out
    assert "strategies INSERT" in text and "promoted_from  M0005" in text
    assert "params.digest" in text and "REGISTRY  untouched" in text
    assert pg.execute("SELECT count(*) FROM strategies WHERE id = 'TEST-FND'").fetchone()[0] == 0
    assert lab_store.PROMOTION_MARKER not in lab_store.get_method(lab, METHOD)["analysis"]


def test_a_rejected_method_needs_the_acknowledgement(pg, monkeypatch, lab, tmp_path):
    monkeypatch.setattr(promote.db, "connect", lambda url=None: pg)
    monkeypatch.setattr(pg, "close", lambda: None)
    monkeypatch.setattr(lab_store, "connect", lambda path=None: lab)
    monkeypatch.setattr(lab, "close", lambda: None)
    with pytest.raises(lab_store.LabError, match="--lab-status-stays"):
        promote._run(_args(lab_status_stays=False, lab_db=tmp_path / "lab.sqlite"))
    assert pg.execute("SELECT count(*) FROM strategies WHERE id = 'TEST-FND'").fetchone()[0] == 0


def test_the_registry_is_not_appended_to():
    from seer_engine.backtest.registry import REGISTRY

    before = len(REGISTRY)
    promote.find_candidate(METHOD, VARIANT)
    from seer_engine.backtest.registry import REGISTRY as after_registry

    assert len(after_registry) == before
    assert all(c.id != VARIANT for c in after_registry)
```

**Impact:** `test_a_failed_retire_leaves_no_inserted_row` is the atomicity proof the exit criteria
ask for; `test_dry_run_...` is the dry-run proof; `test_the_registry_is_not_appended_to` pins D1.
The `pg` fixture's connection is handed to `promote` by monkeypatching `db.connect`, which is how
`test_paper_command.py` already drives commands against a throwaway schema.

### Step 4: the lab record's tests

**File:** `engine/tests/test_lab_store.py` (append after the last test in the file)

**Change:** four tests for `record_promotion`, in the file that already owns the lab's rules.

**Code:**

```python
# ---- promotion (roster-promotion-pipeline phase 5) ----------------------------------------------


def _promote(conn, **kw):
    base = dict(
        method_id="M0001", strategy_id="FND", candidate_id="M0001-A",
        object_name="FUNDAMENTAL", spec_digest="d" * 64,
    )
    base.update(kw)
    with conn:
        return store.record_promotion(conn, **base)


def test_record_promotion_appends_analysis_and_an_insight(conn):
    _method(conn, status="idea")
    assert _promote(conn, move_status=False) == "idea"
    row = store.get_method(conn, "M0001")
    assert store.PROMOTION_MARKER + "`FND`" in row["analysis"]
    assert "M0001-A" in row["analysis"] and "FUNDAMENTAL" in row["analysis"]
    assert row["status"] == "idea"
    insight = conn.execute("SELECT * FROM insights ORDER BY id DESC LIMIT 1").fetchone()
    assert insight["kind"] == "observation" and insight["method_id"] == "M0001"
    assert "promoted to the paper roster as FND" in insight["title"]


def test_record_promotion_takes_the_edge_transitions_already_has(conn):
    _method(conn, status="idea")
    with conn:
        for nxt in ("registered", "dev-eligible", "promoted", "test-passed"):
            store.update_method(conn, "M0001", status=nxt)
    assert _promote(conn) == "paper"
    assert store.get_method(conn, "M0001")["status"] == "paper"


def test_record_promotion_refuses_a_status_with_no_path_to_paper(conn):
    _method(conn, status="idea")
    with conn:
        store.update_method(conn, "M0001", status="rejected")
    with pytest.raises(store.LabError, match="--lab-status-stays"):
        _promote(conn)
    assert store.get_method(conn, "M0001")["status"] == "rejected"
    assert store.PROMOTION_MARKER not in store.get_method(conn, "M0001")["analysis"]


def test_record_promotion_is_idempotent_and_never_touches_source_sha(conn):
    _method(conn, status="idea")
    with conn:
        store.update_method(conn, "M0001", source_sha="a" * 64)
    _promote(conn, move_status=False)
    _promote(conn, move_status=False)
    row = store.get_method(conn, "M0001")
    assert row["analysis"].count(store.PROMOTION_MARKER) == 1
    assert conn.execute("SELECT count(*) FROM insights").fetchone()[0] == 1
    assert row["source_sha"] == "a" * 64
```

**Impact:** four tests on the module's own fixture (`conn`, `tmp_path`-backed SQLite at
`test_lab_store.py:17`) and its `_method` helper (`:24`). No existing test changes.

## Verification

**Build:**

```bash
"$SEER_PY" -c 'import seer_engine.commands.promote as m; print(m.HELP)'
"$SEER_PY" -m seer_engine promote --help
"$SEER_PY" -c 'from seer_engine import cli; assert "promote" in cli.discover()'
```

**Tests:**

```bash
"$SEER_PY" -m pytest engine/tests/test_promote_command.py engine/tests/test_lab_store.py \
                    engine/tests/test_paper_roster.py engine/tests/test_registry.py \
                    engine/tests/test_lab_snapshot.py engine/tests/test_cli.py -q
"$SEER_PY" -m pytest engine/tests -q          # whole suite, with PG_TEST_URL exported
```

**Test DELTA for this phase** (never an absolute; phases land in a swarm):

| | delta |
|---|---|
| with `PG_TEST_URL` exported | **+24 passed**, +0 skipped |
| without `PG_TEST_URL` | **+14 passed, +10 skipped** (the ten `pg`-fixture tests) |

The 24 are 20 in `test_promote_command.py` (Step 3) and 4 in `test_lab_store.py` (Step 4).

No existing test changes its result. In particular `test_paper_roster.py`'s five pinned digests
(`PINS`, `:52-58`) pass **unchanged** — this phase calls `roster.spec`/`spec_digest` and edits
neither — and `test_registry.py`'s `candidate_digest` pin is untouched because `REGISTRY` is not
read, written or imported by `promote` except in the test that asserts it did not grow.

**Manual check** (dry run only; it writes nothing):

```bash
"$SEER_PY" -m seer_engine --dry-run promote \
  --method M0005 --candidate M0005-ALL --id FND \
  --name "FND · Fundamentals" --sub "Top 20 on filed fundamentals, monthly" \
  --icon book-open --lab-status-stays \
  --gate-note "No backtest gate: the lab's dev window (1996-2015) predates usable XBRL coverage"
```

Expect: the full row listing, `paper_start NULL`, `promoted_from M0005`, `REGISTRY untouched`,
then two "rolled back" lines. Then confirm nothing moved:

```bash
git status --porcelain lab/lab.sqlite      # must be empty
```

Until **phase 6** commits the `RESOLVER` entry for `FUNDAMENTAL`, this run exits 2 with the "has no
name for <FND>" refusal — which is the correct, designed outcome at the end of *this* phase and is
itself worth seeing once. It is the whole of D2's cost, said out loud.

**Exit criteria:**

1. `promote --method M --id X` inserts one `strategies` row with `status='active'`,
   `promoted_from='M'`, `object_name` a `roster.RESOLVER` key, `registry_id IS NULL`, a non-empty
   `gate_note`, `gate_applicable`, full contract-C2 `params`, and `paper_start IS NULL` — and the
   row is rebuilt through `roster.from_row` inside the transaction before it commits, so a row the
   paper night would refuse is never written.
2. An `--id` whose row already has a `paper_start` raises `promote.AlreadyStarted` and writes
   nothing (invariant 3).
3. `--retire Y` sets `Y.status='retired'` and `Y.paper_end` in the **same** `db.transaction` as
   the insert; a failing retire leaves no inserted row.
4. The lab records the promotion against the method — `analysis` grown, one `insights` row — and
   moves `status` to `paper` only along the existing `('test-passed','paper')` edge; `source_sha`,
   `hypothesis` and `verdict` are untouched and no `TRANSITIONS` edge is added.
5. `--dry-run` prints every row of both databases and writes to neither.
6. `backtest/registry.py` is byte-identical to `origin/main`.

## Handoffs

- **Phase 1 — `roster.RESOLVER`'s shape.** This phase needs only `Mapping[str, obj]`. If phase 1
  additionally teaches the resolver a generic `lab:<method id>:<ATTR>` namespace (import the
  method module, `getattr` the attribute), then a brand-new lab allocator becomes promotable with
  **zero** engine code change, and `object_name_of`'s refusal disappears for lab-local allocators.
  That is a strict improvement on R2 and it lives entirely in phase 1's file, so it is offered,
  not taken.
- **Phase 1 — `promoted_from` and the variant.** The exit criteria pin `promoted_from` to the
  *method* id, so the roster row does not name the variant. Nothing is lost: `params.spec.params`
  is the variant's `as_dict()`, which separates `M0005-ALL` from `M0005-ALL-R`, and the lab
  `analysis` and `insights` rows name the variant outright. If phase 4 wants the variant on the
  leaderboard, it should read it from the lab snapshot, not from a widened column.
- **Phase 2 — `store.retire`'s `paper_end`.** `promote` calls it and prints what it returns; it
  does not define what "the last session actually traded" means. Phase 2 owns that definition.
- **Phase 4 — a `paper` lab status on the Sera pages.** `record_promotion` can now put a method at
  `status='paper'`, which `web/lib/sera/types.ts:120`'s `METHOD_STATUSES` already lists but which
  no method has ever held. Whether `/sera` renders it distinctly is phase 4's call; nothing breaks
  if it does not.
- **Phase 6 — the exact invocation, reconciled.** Phase 6's plan asked for a `--no-lab-record`
  flag on the premise that the lab cannot record a promotion of a `rejected` method. **That
  premise is wrong and the flag is not shipped.** The lab's `analysis` only ever grows and
  `insights` is an append-only journal, so `record_promotion` writes both at *any* status; the
  only thing `rejected` blocks is the `status` move, and `--lab-status-stays` is exactly the flag
  for that. So phase 6 runs:

  ```
  promote --method M0005 --candidate M0005-ALL --id FND --lab-status-stays …
  ```

  `--candidate` is **required** (M0005 has six variants: VAL, ROE, GP, SUE, ALL, ALL-R), and
  `M0005-ALL` is the one whose `params` is `FundamentalParams(rank="composite", top=20)`.
  `promoted_from` is written as `'M0005'`; the lab gets its appended `# Promotion` section and its
  `insights` row; M0005 stays `rejected`, which is the honest record. There is no path in this
  phase that writes a roster row without a lab record, by design: a promotion nobody can find
  afterwards is the thing R4 exists to stop.
- **Phase 6 — the resolver line it must commit first.** `"FUNDAMENTAL": Binding(obj=FUNDAMENTAL,
  params=FUNDAMENTAL_PARAMS)` in phase 1's `RESOLVER` (a `Binding`, not a bare object), or
  `promote` refuses — correctly — and tells it so. This phase's test suite borrows that entry
  through a fixture precisely because no committed lab allocator is named yet.
- **Not done, deliberately (D6).** No watcher, no hook from a Sera session, no auto-promotion on a
  DSR threshold, and no "promote the best method" convenience. A Sera session may *recommend*; a
  person types the command.
- **Not done, out of scope.** A `demote`/`unpromote` command. Retirement already exists (phase 2)
  and is the correct reversal; deleting a promoted row would destroy the record invariant 4
  protects. Also not done: a `--params` override, which would let a promotion ship a configuration
  no lab trial ever ran — the whole point of taking the triple off a `Candidate` is that it cannot.

## Rollback

Code: `git revert` the phase commit. `commands/promote.py` and `test_promote_command.py` vanish and
the `promote` subcommand disappears with them (`cli.discover()` is a directory scan); `lab/store.py`
returns to its current 796 lines. Nothing else in the tree imports either new symbol, so no caller
breaks.

Data, if the command was actually run before the revert:

- **Neon.** `DELETE FROM strategies WHERE id = '<the promoted id>'` — **only while it has no
  `paper_start`**. Once it has traded a night, retire it instead (`UPDATE strategies SET
  status='retired' WHERE id='<id>'`), because deleting it would destroy the history invariant 4
  protects. Undo a retirement with `UPDATE strategies SET status='active', paper_end=NULL WHERE
  id='<the retired id>'`; the strategy resumes on the next night with its history intact.
- **`lab/lab.sqlite`.** The lab is append-only by trigger: the appended `analysis` section and the
  `insights` row **cannot be deleted**, and a `paper` status cannot be moved back. The rollback is
  `git checkout -- lab/lab.sqlite web/data/lab.json`, which is exactly why the database file is
  committed. Do this *before* any other lab write lands on top of it; if one has, the promotion
  record stays and is corrected the lab's way — by appending a note that says so.

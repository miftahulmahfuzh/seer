# Phase 1: Method amendments: pre-registered variants of a method that has already run

**Plan set:** `LAB_BRAKES_AND_GATE_PLAN.md`
**Analysis:** `docs/analyzer/20261012-124247-B4K9_code_analyzer.md`
**Satisfies:** R3 (variants of the existing method files, free in N, never a new method id) and R4
(the usual lab rules still bind: the commit is the pre-registration, `lab stage` for any database
commit, Postgres for DB tests, no hard-gate override, the test window never touched)
**Depends on:** none
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/lab`

---

## Goal

After this phase a lab method that has already run can accept **amendments**: additional
pre-registered variants, declared in its own method file, recorded under its own existing
`method_id`. `methods.source_sha` is still written exactly once and the `methods_source_sha_once`
trigger still means what it says; the freeze it used to provide is replaced by two checks that are
together stronger — the file hashes to the **latest** sha the lab recorded for it, and every
candidate a recorded trial names still digests to that trial's `config_digest`. Nothing runs here:
phases 3 and 4 write the amendment blocks, phase 5 executes `lab run --amend`.

## Interface Contract

The reconciler reads this section to detect cross-phase conflicts.

**Creates**

| Name | Where | Signature / shape |
|---|---|---|
| `lab.method.Amendment` | `lab/method.py` | `@dataclass(frozen=True)` with `added: date`, `why: str`, `hypothesis: str`, `expected_failure: str`, `candidates: tuple[Candidate, ...]` — all five positional-or-keyword, no defaults |
| `lab.method.Method.amendments` | `lab/method.py` | new field, `tuple[Amendment, ...] = field(default=())`, declared **last** (after `seen_keys`) |
| `lab.method.Method.all_candidates()` | `lab/method.py` | `def all_candidates(self) -> tuple[Candidate, ...]` — originals then each amendment's, in declaration order |
| `lab.store.AmendmentRow` | `lab/store.py` | `@dataclass(frozen=True)` with `method_id: str`, `seq: int`, `source_sha: str`, `added: str`, `why: str`, `hypothesis: str`, `expected_failure: str`, `run_at: str`, `git_sha: str` |
| `lab.store.AMENDMENT_COLUMNS` | `lab/store.py` | `tuple[str, ...]` from `fields(AmendmentRow)` |
| `lab.store._AMENDMENTS_TABLE` / `_AMENDMENTS_TRIGGERS` | `lab/store.py` | module-private DDL constants, same shape as `_PROVENANCE_TABLE` / `_PROVENANCE_TRIGGERS` |
| `lab.store.insert_amendment` | `lab/store.py` | `def insert_amendment(conn: sqlite3.Connection, row: AmendmentRow) -> None` |
| `lab.store.amendments_of` | `lab/store.py` | `def amendments_of(conn: sqlite3.Connection, method_id: str) -> list[sqlite3.Row]` — ordered by `seq`, `[]` when the table does not exist |
| `lab.store.latest_source_sha` | `lab/store.py` | `def latest_source_sha(conn: sqlite3.Connection, method_id: str) -> str \| None` |
| `lab.runner.AMEND_CLOSED` | `lab/runner.py` | `tuple[str, ...] = ("promoted", "test-passed", "test-failed", "paper")` |
| `lab.runner.pending_amendment` | `lab/runner.py` | `def pending_amendment(conn: sqlite3.Connection, method: Method) -> Amendment` |
| `method_amendments` table | `lab/lab.sqlite` schema (in `store.py`'s DDL) | columns `method_id, seq, source_sha, added, why, hypothesis, expected_failure, run_at, git_sha`; `PRIMARY KEY (method_id, seq)`; triggers `method_amendments_no_update`, `method_amendments_no_delete` |
| `lab run --amend` | `commands/lab.py` | `store_true` flag on the **existing** `run` subparser |
| `engine/tests/test_lab_amendments.py` | new test file | the mechanism's own tests (14) |

**Signature changes**

- `lab.runner.preflight(conn, method, path, *, require_commit=True)` →
  `lab.runner.preflight(conn, method, path, *, require_commit=True, amend=False) -> Amendment | None`
  (today it returns `None` implicitly; the annotation widens, existing callers are unaffected).
- `lab.runner.run_method(conn, method, path, data, *, git_sha, require_commit=True)` →
  `... , require_commit=True, amend=False)`.
- `lab.prereg.check_source(method_id, row, trial)` →
  `lab.prereg.check_source(conn, method_id, trial)` — it needs a connection to resolve
  `latest_source_sha`, and `row` becomes unused. One caller, `prereg.promote_method` at
  `prereg.py:667`.

**Behaviour changes, signatures untouched** (each is a strict no-op on today's tree, because
`all_candidates() == candidates` for every method with no amendment):

- `lab.runner.market_aware_candidates` reads `method.all_candidates()`
- `lab.runner.resolve_candidate` reads `method.all_candidates()`
- `lab.prereg.check_source` reads `method.all_candidates()`
- `lab.remeasure.preflight` reads `method.all_candidates()`
- `lab.real_costs.real_cost_problem` and `lab.real_costs.pick_candidate`'s `by_id` read
  `method.all_candidates()` — required so the M0031 real-fee rule governs an amendment too
- `lab.exposure.resolve_candidate`'s `by_id` (`exposure.py:500`) reads `method.all_candidates()`
- `lab.survivorship_check`'s `by_id` (`survivorship_check.py:133`) reads `method.all_candidates()`
- `commands.promote._resolve`'s `ids`, its single-variant shortcut and its lookup
  (`promote.py:205-213`) read `method.all_candidates()`

  The last three are the **completion** of the same migration, added by the reconciler (C6). They
  are one-line reads each, mechanically identical to the five above, and leaving them behind is a
  correctness bug with a delayed fuse: `lab exposure` on an amended method would silently report
  an incomplete book, `lab survivorship` would skip the amendment's variants, and `lab promote`
  would resolve against a stale candidate set. Every reader of "what variants does this method
  have" now asks `all_candidates()`; `candidates` is the original batch and nothing else, which is
  what the field's own docstring says. On today's tree all three are strict no-ops —
  `all_candidates() == candidates` for every committed method file.

**Deletes:** nothing. **Renames:** `engine/tests/test_lab_methods.py::test_a_method_that_ran_is_frozen`
→ `test_a_method_that_ran_is_frozen_to_its_latest_recorded_sha`, plus a second new test beside it.

**Schema version:** `store.SCHEMA_VERSION` moves `"5"` → `"6"`; `_v5_to_v6` is purely additive.

**Requires (from earlier phases):** none.

**Leaves alone (owned by others):**

- every `engine/src/seer_engine/lab/methods/mNNNN_*.py` (phases 3 and 4)
- `lab/gate_probe.py` and the `gate` subparser (phase 2) — this phase adds a flag to the
  **existing** `run` subparser only. **Phase 2 depends on this phase** (reconciler, C4): the two
  hunks in `commands/lab.py` are ~230 lines and ~2100 lines apart, but they are in one file in one
  shared worktree, so they are serialised rather than raced.
- `lab/exposure.py` — **one line only**, `exposure.py:500`'s `by_id` comprehension, and nothing
  else in the module. `ERAS`, `ERA_LABELS`, `WHOLE`, `Arm`, `StoreRun`, `Tally`,
  `ExposureAllocator`, `reweight`, `load_dev_store` and every message string are untouched, so
  phase 2 — which **imports** those and edits none of them — is unaffected.
- `lab/npolicy.py`, `store.gate`, `store.pending_gate` — read, never edited
- the ten `Lab N (dev trials)` strings in `commands/lab.py`, including the one at `:1399` inside
  `_run`, which this phase's new prints sit **after**
- `db/migrations/`, `web/`, `lab/lab.sqlite`

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/method.py` | modify | module docstring (`:11`); `Amendment` (new, after `config_digest`); `Method.amendments` (`:62`); `Method.all_candidates()`; validation loop (`:79-94`) |
| `engine/src/seer_engine/lab/store.py` | modify | module docstring (`:33`, `:38`); `SCHEMA_VERSION` (`:80`); `_AMENDMENTS_TABLE`/`_AMENDMENTS_TRIGGERS` (new, after `:325`); `_SCHEMA` (`:466`); `_v5_to_v6` (new, after `:652`); `_migrate` (`:655-700`); `AmendmentRow` + three helpers (new, after `:2057`) |
| `engine/src/seer_engine/lab/runner.py` | modify | module docstring (`:1-45`); `AMEND_CLOSED` + `pending_amendment` (new, before `preflight`); `preflight` (`:161-189`); `market_aware_candidates` (`:213`); `run_method` (`:437-553`); `resolve_candidate` (`:595-599`); `preflight_test` (`:717-718`) |
| `engine/src/seer_engine/lab/prereg.py` | modify | module docstring (`:18`); `check_source` (`:434-480`) |
| `engine/src/seer_engine/lab/remeasure.py` | modify | `preflight`'s sha comparison and `by_digest` (`:369-386`) |
| `engine/src/seer_engine/lab/real_costs.py` | modify | `real_cost_problem` (`:72`) and `pick_candidate`'s `by_id` (`:133`) read `all_candidates()` |
| `engine/src/seer_engine/lab/exposure.py` | modify | **one line**: `by_id` (`:500`) reads `all_candidates()`. Nothing else in the module. |
| `engine/src/seer_engine/lab/survivorship_check.py` | modify | **one line**: `by_id` (`:133`) reads `all_candidates()` |
| `engine/src/seer_engine/commands/promote.py` | modify | `_resolve`'s `ids`, its one-variant shortcut and its lookup (`:205-213`) read `all_candidates()` |
| `engine/src/seer_engine/lab/hardgate.py` | modify | one docstring sentence (`:342-345`) |
| `engine/src/seer_engine/commands/lab.py` | modify | `run` subparser gains `--amend` (after `:195`); `_run` (`:1365`, `:1395`, and new prints after `:1399`) |
| `engine/tests/test_lab_methods.py` | modify | `CANDIDATES` (`:32`); `test_a_method_that_ran_is_frozen` (`:113-129`) replaced by two tests |
| `engine/tests/test_lab_snapshot.py` | modify | `_without_amendments` helper + `V5_SCHEMA` (`:39`, `:286`); `== "5"` → `== "6"` (`:116`, `:357`); new v5 → v6 migration test |
| `engine/tests/test_lab_store.py` | modify | `test_source_sha_is_set_once` gains the amendment half (`:205-211`) |
| `engine/tests/test_lab_runner.py` | modify | `test_a_method_runs_once_and_configs_never_repeat` (`:133-139`) keeps its meaning, gains the amendment pointer |
| `engine/tests/test_lab_prereg.py` | modify | `test_promote_refuses_a_method_file_that_changed_since_it_ran` docstring (`:292-298`) names `latest_source_sha` |
| `engine/tests/test_lab_name_count.py` | modify | `_untouched` (`:46-56`) also counts `method_amendments` |
| `engine/tests/test_lab_costs.py` | modify | `_untouched` (`:72-80`) also counts `method_amendments` |
| `engine/tests/test_lab_survivorship.py` | modify | `_untouched` (`:144-155`) also counts `method_amendments` |
| `engine/tests/test_lab_exposure.py` | modify | `_untouched` (`:157-169`) also counts `method_amendments` |
| `engine/tests/test_lab_amendments.py` | create | the mechanism's own tests (14 of them) |

## Phase decisions

Settled here, inside the boundary the index's D1/D2/D3/D8 draw. Each is quoted where it lands.

- **P1 — `--amend` is a flag, not an index.** The amendment that runs is `method.amendments[k]`
  where `k` is the number of `method_amendments` rows already recorded for the method. There is no
  way to name an amendment out of order, so the record and the file stay a prefix match and the
  table stays append-only. *(Rung: invariant 4.)*
- **P2 — an amendment never moves `methods.status`.** `run_method` on the amendment path writes
  trials, moments, funding and provenance exactly as before, writes its `method_amendments` row,
  and leaves `status` and `source_sha` alone. A `rejected` method whose amendment comes back
  eligible is re-judged by `store.reevaluate_method`, which has its own guards and its own
  appended analysis; making `run_method` do it would put a second door on `rejected` → `dev-eligible`
  with none of them. The CLI prints the status and says it did not move. *(Rung: invariant 4, and
  `store.TRANSITIONS`' own comment that the edge is "admitted only by `reevaluate_method`".)*
- **P3 — a method that has had its look cannot be amended.** `AMEND_CLOSED` refuses
  `promoted`, `test-passed`, `test-failed` and `paper`, and a second check refuses any method with
  a `test` trial. The one look is spent once; a mechanism that let a book keep growing variants
  after it was tested would be the fishing design §3 exists to stop. *(Rung: index invariant 6.)*
- **P4 — the recorded amendments must be a prefix of the file's.** Before a run, every already
  recorded row is compared field for field against `method.amendments[seq-1]`. An amendment that
  was reordered, edited or deleted after it ran is a refusal, which is the amendment-level half of
  what `source_sha` used to give the whole file. *(Rung: index Decision D2.)*
- **P5 — schema v6, not a column on `methods`.** `ALTER TABLE methods ADD COLUMN` would move every
  recorded method row's bytes, and one column cannot hold a growing list. The same reasoning that
  made `trial_funding` and `trial_provenance` side tables. *(Rung: `store._FUNDING_TABLE`'s own
  docstring.)*

## Implementation Steps

### Step 1: `lab/method.py` — the `Amendment` value, the field, the accessor, the validation

**File:** `engine/src/seer_engine/lab/method.py:1-98`
**Change:** rewrite the module docstring's freeze sentence, add `from datetime import date`, add
`Amendment` after `config_digest`, add `Method.amendments` and `Method.all_candidates()`, and widen
the validation loop to run over the originals and every amendment in one pass.

**Code — replace `method.py` lines 1-98 (docstring through `Method.__post_init__`) with:**

```python
"""A lab method: one idea, 1-6 fixed variants (method lab design §2), plus its amendments.

A method is one file ``seer_engine/lab/methods/mNNNN_<slug>.py`` exporting ``METHOD``. New
signal logic is an ``Allocator`` in the same file (the protocol in ``strategies.allocator``);
an existing allocator with new params is a variation. Everything else (``TradeRules``, the
book engine, costs, dividends, whole shares) is reused unchanged.

``config_text``/``config_digest`` identify a trial by what it *does* (rules, allocator id,
params), not by its name: the same configuration under a new id is still a re-run, and the
lab database refuses it. Allocator ids are therefore unique across lab methods.

A method file used to be **frozen outright** once it had run: ``source_sha`` was written once and
every reader compared the file on disk against that one hash. Since 2026-10-12 it is frozen
*against its latest recorded sha* instead, and may grow ``Amendment`` blocks -- see ``Amendment``
for why the rule changed and what replaced it. ``methods.source_sha`` is still written exactly
once and ``methods_source_sha_once`` still refuses to let it move; the newer shas live in
``method_amendments``, one append-only row per amendment, and ``store.latest_source_sha`` is the
one place that answers "which sha is this file supposed to hash to today".
(tests/test_lab_methods.py checks the sha equality and the digest equality, which are the two
halves of the replacement.)
"""

from __future__ import annotations

import hashlib
import importlib
import pkgutil
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from types import ModuleType

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.registry import _canon

METHOD_ID = re.compile(r"M\d{4}")
MODULE_NAME = re.compile(r"m(\d{4})_[a-z0-9_]+")
SOURCE_KINDS: tuple[str, ...] = ("paper", "blog", "github", "knowledge", "variation")
MAX_VARIANTS = 6


def config_text(c: Candidate) -> str:
    """Canonical text of what ``c`` does: rules, allocator id and params (not id or family)."""
    return "\n".join(
        (f"rules={_canon(c.rules)}", f"allocator=<{c.allocator.id}>", f"params={_canon(c.params)}")
    ) + "\n"


def config_digest(c: Candidate) -> str:
    return hashlib.sha256(config_text(c).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Amendment:
    """More pre-registered variants of a method that has already run (design §2, 2026-10-12).

    **Why the freeze had to become something a file can grow under.** The old rule -- a method
    file is frozen once it has run, and a change is a new variation method id -- was written when
    the luck gate counted trial *rows*, so a new id cost the lab nothing it was not already paying.
    Under the ``methods`` policy (``store.DSR_POLICY``, since 2026-10-08) it costs the whole lab
    one more independent look. Measured 2026-10-12 on the committed database (130 methods, 354 dev
    trials): ``store.pending_gate`` prices a brand-new method at N = 75 against N = 74 for another
    variant of a method that has already run -- and that +1 is applied retroactively, to every
    recorded trial's published verdict. Asking one more question of an idea the lab has already
    counted should cost nothing, and under this policy it does.

    **What an amendment is.** More variants of the *same* idea, declared in the same method file,
    recorded under the same ``method_id``. It is pre-registered exactly as the original was: the
    commit that adds this block is the pre-registration (``lab run --amend`` refuses an
    uncommitted or dirty file through ``registry_problem``), and ``why``, ``hypothesis`` and
    ``expected_failure`` are written before any result is seen and frozen with that commit.

    **What replaced the freeze.** Two checks, together stronger than the one they replace:

    1. the file on disk hashes to the **latest** sha the lab recorded for it --
       ``store.latest_source_sha``: the newest ``method_amendments`` row, falling back to
       ``methods.source_sha``, which is never rewritten and whose trigger stays;
    2. every candidate a recorded trial names still digests to the ``config_digest`` that trial
       holds (``prereg.check_source``, ``remeasure.preflight``, and
       ``test_every_recorded_configuration_still_digests_to_its_recorded_digest``).

    Check 1 alone never covered an edit to an *imported* params dataclass or allocator, which can
    move a recorded digest without touching this file at all; check 2 is what covers that, and the
    two were always meant to be read together. Check 2 was measured on the committed lab on
    2026-10-12: 63 method files, 0 sha mismatches, 0 digests drifted.

    ``added`` is the day the block was written. ``why`` is one line naming the new question, for a
    reader who later finds two batches of trials under one id and needs to know why. ``candidates``
    is 1..``MAX_VARIANTS`` of them, counted **per amendment and not per method lifetime** (plan
    Decision D3): the cap is design §2's "one idea with 1-6 fixed variants per run", and an
    amendment is a run. ``Method.__post_init__`` additionally refuses a candidate id or a
    configuration that any other variant of this method -- original or amendment -- already uses.
    """

    added: date
    why: str
    hypothesis: str
    expected_failure: str
    candidates: tuple[Candidate, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.added, date):
            raise TypeError(f"an amendment's added must be a date, got {type(self.added).__name__}")
        for name in ("why", "hypothesis", "expected_failure"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"an amendment's {name} must be a non-empty str")
        if not isinstance(self.candidates, tuple):
            raise TypeError("an amendment's candidates must be a tuple")
        if not 1 <= len(self.candidates) <= MAX_VARIANTS:
            raise ValueError(
                f"an amendment carries 1..{MAX_VARIANTS} candidates, got {len(self.candidates)}"
            )


@dataclass(frozen=True)
class Method:
    """One lab idea and its pre-registered variants.

    ``hypothesis``: why it should beat SPY under design §1; ``expected_failure``: the way it
    most likely fails. Both are written before the run and frozen with the commit.
    Candidate ids are ``<id>-<suffix>`` and every candidate's family is the method id.

    ``amendments`` are the later, separately pre-registered batches of variants of this same idea
    (``Amendment``). They are a tuple in declaration order and the lab records them in that order,
    one ``method_amendments`` row each, so the record is always a prefix of the file. Every reader
    that asks "what variants does this method have" wants ``all_candidates()``, not ``candidates``:
    ``candidates`` is the original batch and nothing else.
    """

    id: str
    name: str
    family: str
    source_kind: str
    source_ref: str
    hypothesis: str
    expected_failure: str
    candidates: tuple[Candidate, ...]
    parent_id: str | None = None
    seen_keys: tuple[str, ...] = field(default=())
    amendments: tuple[Amendment, ...] = field(default=())

    def all_candidates(self) -> tuple[Candidate, ...]:
        """Every variant this method has ever pre-registered: the originals, then each amendment's.

        In declaration order, which is the order the lab recorded them in, so a reader can map a
        recorded trial back onto the block that pre-registered it by position as well as by id.
        Identical to ``candidates`` for a method with no amendment, which is every method file
        committed before 2026-10-12.
        """
        out: list[Candidate] = list(self.candidates)
        for a in self.amendments:
            out.extend(a.candidates)
        return tuple(out)

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or METHOD_ID.fullmatch(self.id) is None:
            raise ValueError(f"method id must look like M0001, got {self.id!r}")
        for name in ("name", "family", "hypothesis", "expected_failure"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{self.id}: {name} must be a non-empty str")
        if self.source_kind not in SOURCE_KINDS:
            raise ValueError(f"{self.id}: source_kind must be one of {SOURCE_KINDS}, got {self.source_kind!r}")
        if self.source_kind != "knowledge" and not self.source_ref.strip():
            raise ValueError(f"{self.id}: a {self.source_kind} method needs a source_ref (URL, citation or parent)")
        if self.source_kind == "variation" and not self.parent_id:
            raise ValueError(f"{self.id}: a variation needs parent_id")
        if not isinstance(self.candidates, tuple) or not 1 <= len(self.candidates) <= MAX_VARIANTS:
            raise ValueError(f"{self.id}: 1..{MAX_VARIANTS} candidates, got {len(self.candidates)}")
        if not isinstance(self.amendments, tuple):
            raise TypeError(f"{self.id}: amendments must be a tuple of Amendment values")
        for a in self.amendments:
            if not isinstance(a, Amendment):
                raise TypeError(f"{self.id}: amendments must be Amendment values, got {type(a).__name__}")
        # One pass over the originals and then each amendment, sharing the id and digest sets: a
        # candidate may not repeat an id or a configuration that any *other* batch of this same
        # method already used, or `has_trial` would refuse the run after the backtest was paid for.
        # The empty `where` for the originals keeps their messages byte-identical to the ones this
        # validation gave before amendments existed.
        ids: set[str] = set()
        digests: set[str] = set()
        batches: list[tuple[str, tuple[Candidate, ...]]] = [("", self.candidates)]
        for i, a in enumerate(self.amendments, start=1):
            batches.append((f" amendment {i} ({a.added.isoformat()})", a.candidates))
        for where, cands in batches:
            for c in cands:
                if not isinstance(c, Candidate):
                    raise TypeError(f"{self.id}{where}: candidates must be Candidate values")
                if not c.id.startswith(self.id + "-"):
                    raise ValueError(f"{self.id}{where}: candidate id {c.id} must start with {self.id}-")
                if c.family != self.id:
                    raise ValueError(f"{self.id}{where}: candidate {c.id} must have family {self.id}, got {c.family}")
                if c.id in ids:
                    raise ValueError(f"{self.id}{where}: candidate id {c.id} appears twice")
                digest = config_digest(c)
                if digest in digests:
                    raise ValueError(f"{self.id}{where}: candidate {c.id} repeats another variant's configuration")
                ids.add(c.id)
                digests.add(digest)
        for key in self.seen_keys:
            if not isinstance(key, str) or ":" not in key:
                raise ValueError(f"{self.id}: seen key {key!r} must look like kind:value")
```

Everything below line 98 in `method.py` (`methods_package`, `discover`, `source_sha`) is unchanged.

**Impact:** `Method` gains one field. `registry._canon` renders a dataclass by enumerating every
`compare=True` field — but `config_text` never passes a `Method` to `_canon`; it passes `c.rules`,
`c.allocator.id` and `c.params`. Invariant 3 therefore holds by construction, and Step 10's
`test_every_recorded_configuration_still_digests_to_its_recorded_digest` proves it against all 354
recorded dev trials rather than asserting it.

---

### Step 2: `lab/store.py` — the `method_amendments` table and its triggers

**File:** `engine/src/seer_engine/lab/store.py:325` (immediately after `_PROVENANCE_TRIGGERS`)
**Change:** add the DDL constants, in the same shape as the three side tables before them.

**Code — insert after `_PROVENANCE_TRIGGERS`'s closing `)` (currently line 325), before the
`#: The backfill's capital rule` comment block:**

```python
# The method_amendments table and its two triggers -- one definition of the v6 table, shared by
# ``_SCHEMA`` and ``_v5_to_v6`` for the same reason ``_PROVENANCE_TABLE`` is shared.
#
# **What it records and why (2026-10-12).** A method file was frozen outright once it ran:
# ``methods.source_sha`` was written once, ``methods_source_sha_once`` refused to let it move, and
# every reader hashed the file against it. That rule was built when the luck gate counted trial
# rows, so another variant of an idea the lab had already counted cost a whole new method id and
# the id cost nothing. Under ``DSR_POLICY = 'methods'`` (2026-10-08) it costs the lab one more
# independent look: measured 2026-10-12 on the committed database, ``pending_gate`` prices a
# brand-new method at N = 75 against 74 for a variant of one that has run, retroactively for all
# 130 methods.
#
# So the file may now grow ``method.Amendment`` blocks, and each one that runs appends a row here
# carrying the sha the file had when it ran. ``methods.source_sha`` is still never rewritten and
# the trigger stays: this table is strictly additional, and ``latest_source_sha`` is the one place
# that resolves "the sha this file is supposed to hash to today".
#
# A side table, not a column on ``methods``, for exactly the reason ``trial_funding`` and
# ``trial_provenance`` are: ``ALTER TABLE methods ADD COLUMN`` would move every recorded method
# row's bytes, and one column could not hold a list that grows.
#
# ``seq`` starts at 1 and is contiguous per method, so the recorded amendments are always a prefix
# of the file's ``Method.amendments`` tuple and ``runner.pending_amendment`` can compare them
# position for position. ``run_at`` and ``git_sha`` are the run's, not the file's: they are what
# joins this row to the ``trials`` rows it produced, which share the same ``run_at``.
_AMENDMENTS_TABLE = """CREATE TABLE IF NOT EXISTS method_amendments (
    method_id        TEXT NOT NULL REFERENCES methods(id),
    seq              INTEGER NOT NULL CHECK (seq >= 1),
    source_sha       TEXT NOT NULL CHECK (length(source_sha) = 64),
    added            TEXT NOT NULL CHECK (length(trim(added)) > 0),
    why              TEXT NOT NULL CHECK (length(trim(why)) > 0),
    hypothesis       TEXT NOT NULL CHECK (length(trim(hypothesis)) > 0),
    expected_failure TEXT NOT NULL CHECK (length(trim(expected_failure)) > 0),
    run_at           TEXT NOT NULL CHECK (length(trim(run_at)) > 0),
    git_sha          TEXT NOT NULL CHECK (length(trim(git_sha)) > 0),
    PRIMARY KEY (method_id, seq)
)"""
_AMENDMENTS_TRIGGERS: tuple[str, ...] = (
    """CREATE TRIGGER IF NOT EXISTS method_amendments_no_update BEFORE UPDATE ON method_amendments
BEGIN SELECT RAISE(ABORT, 'method_amendments are append-only: an amendment row is never updated'); END""",
    """CREATE TRIGGER IF NOT EXISTS method_amendments_no_delete BEFORE DELETE ON method_amendments
BEGIN SELECT RAISE(ABORT, 'method_amendments are append-only: an amendment row is never deleted'); END""",
)
```

**Impact:** no behaviour yet; `_SCHEMA` picks them up in Step 3.

---

### Step 3: `lab/store.py` — wire the table into `_SCHEMA` and bump the version

**File:** `engine/src/seer_engine/lab/store.py:80` and `:466`

**Code — replace line 80:**

```python
SCHEMA_VERSION = "6"  # 2: synthesis kind; 3: trial_moments; 4: trial_funding; 5: trial_provenance; 6: method_amendments (see _migrate)
```

**Code — in `_SCHEMA`, replace the paragraph**

```
{_PROVENANCE_TRIGGERS[1]};

CREATE TRIGGER IF NOT EXISTS trials_no_update BEFORE UPDATE ON trials
```

**with**

```
{_PROVENANCE_TRIGGERS[1]};

{_AMENDMENTS_TABLE};

{_AMENDMENTS_TRIGGERS[0]};

{_AMENDMENTS_TRIGGERS[1]};

CREATE TRIGGER IF NOT EXISTS trials_no_update BEFORE UPDATE ON trials
```

**Impact:** a fresh database carries the table. The one-statement-per-paragraph layout is what
`test_lab_snapshot.py`'s strip helpers depend on; Step 11 adds the matching `_without_amendments`.

---

### Step 4: `lab/store.py` — the migration

**File:** `engine/src/seer_engine/lab/store.py:652` (after `_v4_to_v5`, before `_migrate`)

**Code — insert this function:**

```python
def _v5_to_v6(conn: sqlite3.Connection) -> None:
    """Add the ``method_amendments`` side table and its two append-only triggers.

    Purely additive, exactly as ``_v2_to_v3`` and ``_v3_to_v4`` were and for the same reason: no
    ``methods``, ``trials``, ``trial_moments``, ``trial_funding`` or ``trial_provenance`` row is
    read, written, rebuilt or re-keyed, no column is altered, no verdict moves and no backfill
    runs -- a lab that has recorded no amendment has none to record. A v5 database that migrates
    and is then never written again differs from its v5 self only by an empty table, two triggers
    and the ``schema_version`` string, which
    ``test_connect_migrates_a_v5_database_adding_method_amendments_and_touching_no_row`` pins.

    In particular ``methods.source_sha`` is not read and not written here. It is still set once,
    ``methods_source_sha_once`` still refuses to let it move, and this table is what the file's
    *later* shas go into instead.
    """
    conn.execute(_AMENDMENTS_TABLE)
    for trigger in _AMENDMENTS_TRIGGERS:
        conn.execute(trigger)
```

**Code — replace `_migrate`'s docstring second paragraph and its ladder (`store.py:658-690`) with:**

```python
    A ladder: each step moves the database up exactly one version, so a v1 database reaches v6 in
    one open by running all five steps in order. v1 -> v2 adds the ``synthesis`` insight kind
    (``_v1_to_v2``); v2 -> v3 adds the ``trial_moments`` side table (``_v2_to_v3``); v3 -> v4 adds
    the ``trial_funding`` side table (``_v3_to_v4``); v4 -> v5 adds the ``trial_provenance`` side
    table and backfills it (``_v4_to_v5``) -- after v3 -> v4, because the backfill reads
    ``trial_funding``; v5 -> v6 adds the ``method_amendments`` side table (``_v5_to_v6``). A
    version this code does not know is refused rather than guessed at.

    Parallel sessions may connect at once, so the version is read again after
    ``BEGIN IMMEDIATE``: only the first one migrates, the others find the current version and do
    nothing. The backfill runs inside this same transaction, so a database is never seen at v5
    with its provenance half-written.
    """
    if schema_version(conn) == SCHEMA_VERSION:
        return
    begin_immediate(conn)
    try:
        found = schema_version(conn)
        version = found
        if version == "1":
            _v1_to_v2(conn)
            version = "2"
        if version == "2":
            _v2_to_v3(conn)
            version = "3"
        if version == "3":
            _v3_to_v4(conn)
            version = "4"
        if version == "4":
            _v4_to_v5(conn)
            version = "5"
        if version == "5":
            _v5_to_v6(conn)
            version = "6"
        if version != SCHEMA_VERSION:
            raise LabError(
                f"lab database schema version {found!r} is unknown to this code "
                f"(expects {SCHEMA_VERSION})"
            )
        conn.execute("UPDATE meta SET value = ? WHERE key = ?", (SCHEMA_VERSION, "schema_version"))
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
```

> The final `UPDATE` keeps its original form — `"UPDATE meta SET value = ? WHERE key = 'schema_version'", (SCHEMA_VERSION,)` is equally correct; use whichever matches the file byte for byte so the diff stays the ladder and nothing else.

**Impact:** the committed `lab/lab.sqlite` (schema 5 today, md5 `4a34ddb823ec88a5e86afeb5d7e1b7c9`,
measured 2026-10-12) migrates to v6 on the next `store.connect`. **This phase does not commit the
migrated file** — phase 5 does, through `lab stage`. `snapshot()` never reads `meta`, so
`web/data/lab.json` is byte-identical across the migration and CI's row-for-row check still passes.

---

### Step 5: `lab/store.py` — `AmendmentRow`, `insert_amendment`, `amendments_of`, `latest_source_sha`

**File:** `engine/src/seer_engine/lab/store.py:2057` (after `insert_provenance`, before the
`# --- ideas_seen` banner)

**Code — insert:**

```python
# --------------------------------------------------------------------------- method amendments


@dataclass(frozen=True)
class AmendmentRow:
    """One pre-registered amendment of a method that had already run (schema v6).

    The database half of ``method.Amendment``. One row per amendment that has actually been run;
    an amendment declared in a method file and not yet run has no row, and that absence is exactly
    how ``runner.pending_amendment`` knows which one is next.

    - ``method_id``        the method this amends. It must already exist and have run.
    - ``seq``              1 for the first amendment, 2 for the second, contiguous. The recorded
                           rows are therefore always a prefix of the file's ``Method.amendments``.
    - ``source_sha``       the method file's sha256 **at the moment this amendment ran**. This is
                           the sha the file is expected to hash to from now on
                           (``latest_source_sha``); ``methods.source_sha`` keeps the first one and
                           is never rewritten.
    - ``added``            the ``Amendment.added`` date, ISO, as the file declared it.
    - ``why``              the one line the file gives for asking this further question.
    - ``hypothesis`` /     the amendment's own, written before any result was seen and frozen with
      ``expected_failure`` the commit that pre-registered it. Kept here, and not folded into
                           ``methods.hypothesis``, because that column is frozen once the method
                           leaves ``idea`` and must stay the record of what the *original* run
                           claimed.
    - ``run_at``           the run's timestamp -- the same ``run_at`` every trial of this batch
                           carries, which is what joins the two.
    - ``git_sha``          the repository HEAD the run was made at.
    """

    method_id: str
    seq: int
    source_sha: str
    added: str
    why: str
    hypothesis: str
    expected_failure: str
    run_at: str
    git_sha: str


AMENDMENT_COLUMNS: tuple[str, ...] = tuple(f.name for f in fields(AmendmentRow))


def amendments_of(conn: sqlite3.Connection, method_id: str) -> list[sqlite3.Row]:
    """Every recorded amendment of ``method_id``, oldest first; ``[]`` when it has none.

    A database on schema v1-v5 has no ``method_amendments`` table at all and answers ``[]`` the
    same way -- ``connect`` migrates, so that can only be a ``connect_readonly`` caller or a raw
    read-only connection such as the one ``test_a_method_that_ran_is_frozen_to_its_latest_recorded_sha``
    opens on the committed file. ``provenance_of``, ``moments_of`` and ``funding_of`` carry the
    same branch for the same reason.
    """
    if conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'method_amendments'"
    ).fetchone() is None:
        return []
    return list(conn.execute(
        "SELECT * FROM method_amendments WHERE method_id = ? ORDER BY seq", (str(method_id),)
    ))


def latest_source_sha(conn: sqlite3.Connection, method_id: str) -> str | None:
    """The sha256 ``method_id``'s file is supposed to hash to today, or None when it has not run.

    **This is the replacement for "a method file is frozen once it has run".** It is the newest
    ``method_amendments`` row's ``source_sha``, falling back to ``methods.source_sha`` when the
    method has no amendment -- which is every method the lab recorded before 2026-10-12, so this
    returns exactly what ``row['source_sha']`` returned for all of them.

    ``methods.source_sha`` is never rewritten and ``methods_source_sha_once`` still enforces that:
    the first sha stays the record of what the original batch of trials measured, and the
    amendment rows record what each later batch measured. A reader that wants "has this file
    changed since the lab last ran it" asks this; a reader that wants "what did the original run
    measure" asks the column.
    """
    rows = amendments_of(conn, method_id)
    if rows:
        return str(rows[-1]["source_sha"])
    row = get_method(conn, method_id)
    if row is None or row["source_sha"] is None:
        return None
    return str(row["source_sha"])


def insert_amendment(conn: sqlite3.Connection, row: AmendmentRow) -> None:
    """Record one amendment (the caller holds the transaction).

    Append-only, contiguous and prefix-shaped: ``seq`` must be exactly one past the highest seq
    this method already has, so the recorded amendments can never be a set with a hole in it and
    ``runner.pending_amendment`` can compare them to the file position for position. The method
    must exist and must already have run (``methods.source_sha`` is not NULL) -- an amendment
    amends something, and a method whose first batch has not run has nothing to amend.

    The two triggers refuse UPDATE and DELETE exactly as ``trials`` does, so an amendment, like a
    trial, is written once and stands.
    """
    method = get_method(conn, row.method_id)
    if method is None:
        raise LabError(f"no method {row.method_id}: an amendment amends a method the lab has run")
    if method["source_sha"] is None:
        raise LabError(
            f"{row.method_id} has no recorded source_sha, so it has not run: there is nothing to "
            f"amend. `lab run {row.method_id}` records the first batch"
        )
    if not isinstance(row.source_sha, str) or len(row.source_sha) != 64:
        raise LabError(
            f"{row.method_id}: an amendment's source_sha is the method file's sha256 "
            f"(64 hex characters), got {row.source_sha!r}"
        )
    have = amendments_of(conn, row.method_id)
    expected = len(have) + 1
    if row.seq != expected:
        raise LabError(
            f"{row.method_id}: amendment seq must be {expected} (it has {len(have)} recorded), "
            f"got {row.seq}. method_amendments is append-only and contiguous, so the recorded "
            f"amendments stay a prefix of the method file's"
        )
    cols = ", ".join(f'"{c}"' for c in AMENDMENT_COLUMNS)
    marks = ", ".join("?" for _ in AMENDMENT_COLUMNS)
    conn.execute(
        f"INSERT INTO method_amendments ({cols}) VALUES ({marks})",
        [
            str(row.method_id), int(row.seq), row.source_sha, row.added, row.why,
            row.hypothesis, row.expected_failure, row.run_at, row.git_sha,
        ],
    )
```

**Code — module docstring, add to the table list after the `trial_provenance` bullet
(`store.py:33`):**

```
- ``method_amendments``: one row per *amendment* of a method -- a batch of further
  pre-registered variants of an idea the lab has already run, recorded under that method's own
  id so the luck gate's N does not move (``method.Amendment``). It carries the method file's
  sha256 at the moment that batch ran, so the file is frozen against its **latest** recorded sha
  rather than only its first; ``methods.source_sha`` is still written once and never rewritten.
  Triggers refuse every UPDATE and DELETE.
```

**Code — module docstring, replace the schema-versions paragraph (`store.py:38-42`) with:**

```
Schema versions (``meta.schema_version``): 1 is the first lab; 2 adds the ``synthesis`` insight
kind; 3 adds the ``trial_moments`` side table; 4 adds the ``trial_funding`` side table (the
money-weighted return of a trial that received deposits, and of the SPY fed the same ones); 5 adds
the ``trial_provenance`` side table and backfills it for every trial already recorded; 6 adds the
``method_amendments`` side table (empty: nothing is backfilled, because no amendment predates it).
``connect`` migrates an older database in place; ``connect_readonly`` never does.
```

**Impact:** three new public helpers; no existing one changes.

---

### Step 6: `lab/runner.py` — `AMEND_CLOSED`, `pending_amendment`, and `preflight`'s amendment path

**File:** `engine/src/seer_engine/lab/runner.py:67` (import), `:161-189` (`preflight`)

**Code — replace the import at `runner.py:67`:**

```python
from seer_engine.lab.method import METHOD_ID, Amendment, Method, config_digest, config_text, source_sha
```

**Code — insert immediately before `def preflight` (currently line 161), after `git_head`:**

```python
#: Statuses from which a method may not be amended. All four mean the one look at the test window
#: has been committed to or spent, and design §3 gives exactly one look per configuration: a
#: mechanism that let a tested book keep growing variants under its own id would be the fishing
#: the pre-registration exists to stop. A ``rejected`` or ``dev-eligible`` method is amendable --
#: those are search states, and an amendment is more search.
AMEND_CLOSED: tuple[str, ...] = ("promoted", "test-passed", "test-failed", "paper")


def pending_amendment(conn: sqlite3.Connection, method: Method) -> Amendment:
    """The next ``Amendment`` of ``method`` the lab has not recorded (``store.LabError`` if none).

    **The record must be a prefix of the file.** ``method_amendments`` is append-only and
    contiguous, so the amendment that runs next is always ``method.amendments[k]`` where ``k`` is
    the number of rows already recorded. Before returning it, every recorded row is compared field
    for field against the block it was written from. That comparison is the amendment-level half
    of what the old whole-file freeze gave: an amendment that was reordered, reworded or deleted
    after it ran is a refusal, so a recorded batch of trials can never end up filed under a
    hypothesis nobody committed to before seeing it.

    The *candidate* half of the freeze is checked elsewhere and against the recorded trials
    themselves -- ``prereg.check_source``, ``remeasure.preflight`` and
    ``test_every_recorded_configuration_still_digests_to_its_recorded_digest`` -- because a
    configuration can drift through an imported params dataclass without this file's bytes moving.
    """
    recorded = store.amendments_of(conn, method.id)
    if len(recorded) > len(method.amendments):
        raise store.LabError(
            f"{method.id}: the lab has recorded {len(recorded)} amendment(s) but the method file "
            f"declares {len(method.amendments)}. An amendment that has run is part of the record "
            f"and is never taken back out: restore the file from git"
        )
    for row, a in zip(recorded, method.amendments, strict=False):
        mine = (a.added.isoformat(), a.why.strip(), a.hypothesis.strip(), a.expected_failure.strip())
        theirs = (str(row["added"]), str(row["why"]), str(row["hypothesis"]), str(row["expected_failure"]))
        if mine != theirs:
            raise store.LabError(
                f"{method.id}: amendment {row['seq']} in the method file no longer matches the one "
                f"the lab recorded on {row['run_at']}. It was pre-registered by the commit that "
                f"added it and is frozen the same way the original batch is; restore the file from "
                f"git, or add a new amendment instead of editing a spent one"
            )
    if len(recorded) == len(method.amendments):
        if not method.amendments:
            raise store.LabError(
                f"{method.id}: `--amend` runs the next pre-registered Amendment and this method "
                f"file declares none. Add an `Amendment(...)` to its `amendments=` tuple, commit "
                f"it -- the commit is the pre-registration -- and run it then"
            )
        raise store.LabError(
            f"{method.id}: all {len(recorded)} of its amendments have already run. An amendment, "
            f"like a method, runs once; add another one to the method file and commit it first"
        )
    return method.amendments[len(recorded)]
```

**Code — replace `preflight` (`runner.py:161-189`) with:**

```python
def preflight(
    conn: sqlite3.Connection,
    method: Method,
    path: Path,
    *,
    require_commit: bool = True,
    amend: bool = False,
) -> Amendment | None:
    """Every refusal ``lab run`` makes before loading data (``store.LabError``).

    From M0031 on that includes a variant not priced at Gotrade's real fees
    (``real_costs.real_cost_problem``, which reads ``all_candidates()`` so an amendment is held to
    the same rule); methods up to M0030 are unaffected.

    ``amend`` switches the one refusal that used to be unconditional. Without it a method that has
    run is refused outright -- a method runs once. With it, the method **must** have run, must not
    have reached the test window, and the amendment that runs is the next one its file declares
    that the lab has not recorded (``pending_amendment``). Returns that ``Amendment``, so the
    caller runs its candidates and records its metadata, and None on the ordinary path.

    Either way the "this configuration already ran" check is made only against the candidates this
    run is about to execute: on an amendment the originals have dev trials by definition, and
    checking them would refuse every amendment that ever existed.
    """
    if require_commit:
        problem = registry_problem(path)
        if problem is not None:
            raise store.LabError(
                f"{method.id}: {problem}. Commit the method file first: the commit is its pre-registration"
            )
    cost_problem = real_cost_problem(method)
    if cost_problem is not None:
        raise store.LabError(f"{method.id}: {cost_problem}")
    row = store.get_method(conn, method.id)
    amendment: Amendment | None = None
    if amend:
        if row is None or row["source_sha"] is None:
            raise store.LabError(
                f"{method.id} has not run, so there is nothing to amend. `lab run {method.id}` "
                f"records its first batch; `--amend` adds a later, separately pre-registered one"
            )
        status = str(row["status"])
        if status in AMEND_CLOSED:
            raise store.LabError(
                f"{method.id} is {status!r}: a method that has reached the test window is not "
                f"amended. The look is spent once and never given back, and growing more variants "
                f"under the same id afterwards is exactly the fishing the pre-registration exists "
                f"to stop. A new question about this book is a new variation method "
                f"(source_kind='variation', parent_id={method.id})"
            )
        if conn.execute(
            "SELECT 1 FROM trials WHERE method_id = ? AND window = 'test' LIMIT 1", (method.id,)
        ).fetchone() is not None:
            raise store.LabError(
                f"{method.id} has a test trial: its one look is spent, so it is not amended"
            )
        amendment = pending_amendment(conn, method)
        running = amendment.candidates
    else:
        if row is not None and row["status"] not in ("idea", "registered"):
            raise store.LabError(
                f"{method.id} is already {row['status']}: a method runs once. More variants of "
                "this same idea are an Amendment in its method file, pre-registered by the commit "
                "that adds it and run with `lab run --amend` -- they record under this method id, "
                "so the luck gate's N does not move. A different idea is a new variation method "
                "(source_kind='variation', parent_id=...)"
            )
        running = method.candidates
    if method.parent_id is not None and store.get_method(conn, method.parent_id) is None:
        raise store.LabError(f"{method.id}: parent {method.parent_id} is not in the lab")
    for c in running:
        if store.has_trial(conn, config_digest(c), "dev"):
            hit = conn.execute(
                "SELECT candidate_id FROM trials WHERE config_digest = ? AND window = 'dev'",
                (config_digest(c),),
            ).fetchone()
            raise store.LabError(f"{c.id} repeats {hit[0]}, which already ran on the dev window")
    return amendment
```

**Impact:** `test_a_method_runs_once_and_configs_never_repeat` still matches `"runs once"` and
`"repeats M0001-A"`. The return type widens from implicit `None` to `Amendment | None`; no existing
caller reads the return value.

---

### Step 7: `lab/runner.py` — `market_aware_candidates`, `run_method`, `resolve_candidate`, `preflight_test`

**File:** `engine/src/seer_engine/lab/runner.py:213`

**Code — replace the body of `market_aware_candidates` (keep its docstring, append one paragraph):**

```python
def market_aware_candidates(method: Method, field: str = "fundamentals") -> tuple[str, ...]:
    """The ids of ``method``'s candidates whose allocator ranks on ``Market.<field>``, in order.

    ``strategies.allocator.MarketAware`` is ``runtime_checkable``, so being market-aware is
    having a ``prepare_market`` attribute -- exactly the dispatch ``allocator.prepare_for``
    makes. ``f_fundamental.FUNDAMENTAL`` satisfies it structurally and reads fundamentals; a
    price-only allocator such as ``f_index.TIMING`` or ``f_rotation.ROTATION`` does not, and a
    bracket ``Strategy`` does not either. Which field it reads is ``market_fields``.

    Every variant the method has ever pre-registered, amendments included (``all_candidates``),
    because the coverage gate this feeds is about what a store can rank and that question does not
    change batch by batch. For a method with no amendment -- every file committed before
    2026-10-12 -- this is identical to ``method.candidates``.
    """
    return tuple(c.id for c in method.all_candidates() if field in market_fields(c.allocator))
```

**Code — replace `run_method` (`runner.py:437-553`) with:**

```python
def run_method(
    conn: sqlite3.Connection,
    method: Method,
    path: Path,
    data: research.ResearchData,
    *,
    git_sha: str,
    require_commit: bool = True,
    amend: bool = False,
) -> list[Ran]:
    """Run ``method`` on the dev window and record it (see the module docstring).

    The run is given ``INITIAL_IDR`` -- passed to ``dev.run_registry`` explicitly rather than left
    to its default -- and that same value is written into each trial's ``trial_provenance`` row,
    with ``data.price_fingerprint``, in the transaction that inserts the trial. So the record can
    never name a capital the run was not given, and a later ``lab remeasure`` re-runs it at the
    capital it actually had, whatever ``INITIAL_IDR`` reads by then.

    A survivorship-check store (``data.purpose`` set) is refused first, before the preflight and
    before any backtest, so it can never produce a trial.

    ``amend=True`` runs the next pre-registered ``Amendment`` instead of the original candidates
    (``preflight``). Everything about the recording is the same -- the trials, their moments, their
    funding and their provenance all land under the method's own ``method_id``, which is the whole
    point: ``store.pending_gate`` prices a further batch for a method that already has dev trials
    at the N the lab already has, so the luck gate does not move and no method id is spent. Two
    things differ, and both are deliberate:

    - **``methods.source_sha`` is not written.** It is set once, when the method first ran, and
      ``methods_source_sha_once`` refuses to let it move. The sha the file has *now* is appended
      to ``method_amendments`` instead, and ``store.latest_source_sha`` is what every freeze check
      reads.
    - **``methods.status`` is not moved.** An amendment appends trials; it does not re-decide a
      verdict. A ``rejected`` method whose amendment comes back eligible is re-judged by
      ``store.reevaluate_method``, which is the one door on that edge and which appends its own
      dated reasoning to the analysis. Letting this function take that decision would put a second,
      silent door beside it (plan Decision P2).
    """
    refuse_survivorship_store(data, f"lab run {method.id}")
    amendment = preflight(conn, method, path, require_commit=require_commit, amend=amend)
    candidates = method.candidates if amendment is None else amendment.candidates
    capital = INITIAL_IDR
    results: list[tuple[DevRow, Any]] = []
    deposits: list[Sequence[tuple[date, float]]] = []

    def on_result(i: int, result: Any, row: DevRow) -> None:
        results.append((row, month_end_curve(result.snapshots)))
        cash = external_cashflows(result)
        deposits.append(cash)
        m = row.stats.metrics
        log.info(
            "[%d/%d] %s %s..%s: money-weighted %s vs DCA SPY TR %s (%d deposits, %.2f USD), "
            "max DD %s, PF %s, trades %d",
            i + 1, len(candidates), row.candidate.id, row.start, row.end,
            m.mwr, row.spy_tr.mwr, len(cash), float(sum(a for _, a in cash)),
            m.max_drawdown, m.profit_factor, m.trades,
        )

    dev.run_registry(
        data.market, data.dividends, data.spy_dividends, candidates,
        on_result=on_result, contributions=OWNER_MONTHLY, initial_idr=capital,
    )
    store.begin_immediate(conn)  # lab-wide N and the inserts, atomic against parallel sessions
    with conn:
        # A parallel session may have won a race. On the amendment path the re-check must resolve
        # the *same* amendment, or the trials just produced would be filed under another block's
        # hypothesis.
        again = preflight(conn, method, path, require_commit=False, amend=amend)
        if again is not amendment:
            raise store.LabError(
                f"{method.id}: another session recorded an amendment while this run was in "
                f"flight. Nothing has been written; re-run `lab run --amend {method.id}`"
            )
        ran = trial_rows(
            conn, method, results, fingerprint=data.fingerprint, git_sha=git_sha, deposits=deposits
        )
        status = "dev-eligible" if any(r.trial.eligible for r in ran) else "rejected"
        if store.get_method(conn, method.id) is None:
            store.add_method(
                conn,
                id=method.id,
                name=method.name,
                family=method.family,
                source_kind=method.source_kind,
                source_ref=method.source_ref,
                hypothesis=_hypothesis(method),
                parent_id=method.parent_id,
                status="registered",
            )
        else:
            row = store.get_method(conn, method.id)
            if row["status"] == "idea":
                store.update_method(
                    conn, method.id, hypothesis=_hypothesis(method), name=method.name,
                    family=method.family, source_kind=method.source_kind,
                    source_ref=method.source_ref, parent_id=method.parent_id,
                )
                store.update_method(conn, method.id, status="registered")
        ns = store.insert_trials(conn, [r.trial for r in ran])
        # The DSR's inputs, stamped with the trial numbers SQLite just assigned, in this same
        # transaction: a trial and the measurement that judged it are recorded together or not
        # at all. A variant with no computable moments contributes no row, exactly as it
        # contributes no dsr.
        store.insert_moments(conn, [
            replace(r.moments, trial_n=n)
            for n, r in zip(ns, ran, strict=True)
            if r.moments is not None
        ])
        # The deposits and what they earned, stamped the same way and in the same transaction, for
        # the same reason: the money-weighted verdict and the trial it judges are one record. A
        # variant that received no deposit contributes no row, and no row is how the lab says
        # "this run was not fed" -- the answer `funding_of` gives for all 128 trials recorded
        # before this, which this phase does not backfill (GOTRADE_FEE_REBUILD_PLAN.md D18).
        store.insert_funding(conn, [
            replace(r.funding, trial_n=n)
            for n, r in zip(ns, ran, strict=True)
            if r.funding is not None
        ])
        # The two inputs a re-run needs and no `trials` column carries -- the capital this batch
        # was given and the price fingerprint of the store it read -- one row per trial, in this
        # same transaction. Unlike funding, every trial gets a row: there is no run without a
        # starting capital.
        store.insert_provenance(conn, [
            store.ProvenanceRow(
                trial_n=n,
                initial_idr=capital,
                price_fingerprint=data.price_fingerprint,
                source="recorded",
                measured=r.trial.run_at,
            )
            for n, r in zip(ns, ran, strict=True)
        ])
        if amendment is None:
            store.update_method(conn, method.id, source_sha=source_sha(path), status=status)
        else:
            # The file's sha goes to `method_amendments`, never to `methods.source_sha`, and the
            # status is left where it is (see this function's docstring). Same transaction as the
            # trials: an amendment and the batch it pre-registered are one record or neither.
            store.insert_amendment(conn, store.AmendmentRow(
                method_id=method.id,
                seq=len(store.amendments_of(conn, method.id)) + 1,
                source_sha=source_sha(path),
                added=amendment.added.isoformat(),
                why=amendment.why.strip(),
                hypothesis=amendment.hypothesis.strip(),
                expected_failure=amendment.expected_failure.strip(),
                run_at=ran[0].trial.run_at if ran else store.now_iso(),
                git_sha=git_sha,
            ))
        for key in method.seen_keys:
            store.mark_seen(conn, key, method.id)
    return ran
```

**Code — replace `resolve_candidate`'s lookup (`runner.py:595-599`):**

```python
    found = [c for c in method.all_candidates() if c.id == candidate_id]
    if len(found) != 1:
        raise store.LabError(
            f"{method_id} has no variant {candidate_id!r}; its variants are "
            f"{', '.join(c.id for c in method.all_candidates())}"
        )
```

**Code — replace `preflight_test`'s sha comparison (`runner.py:716-724`):**

```python
        recorded = store.latest_source_sha(conn, method.id)
        actual = source_sha(path)
        if recorded is not None and recorded != actual:
            raise store.LabError(
                f"{method.id}: the method file hashes {actual[:12]} but the lab last ran it under "
                f"{recorded[:12]}; the file changed after it ran. A changed method is a new "
                f"variation method (source_kind='variation', parent_id={method.id}), not a second look"
            )
```

**Code — module docstring, replace `runner.py` lines 5-6 and add a paragraph after the ``lab run``
numbered list (before the ``lab test`` heading):**

```
1. Refuse when the method file is not committed (its commit is the pre-registration), when the
   method has already run **and ``--amend`` was not given**, or when any variant this run is about
   to execute already has a dev trial.
```

```
**``lab run --amend MNNNN``** runs the next ``method.Amendment`` the file declares and the lab has
not recorded: further pre-registered variants of an idea the lab has already counted, landing
under that method's own id. Everything about the recording is identical except two things --
``methods.source_sha`` is not rewritten (the file's current sha is appended to
``method_amendments`` instead, and ``store.latest_source_sha`` resolves which sha a reader should
expect) and ``methods.status`` is not moved (``store.reevaluate_method`` is the one door on
``rejected`` -> ``dev-eligible``). The reason the mechanism exists is the gate: under
``DSR_POLICY = 'methods'`` a new method id costs the whole lab one more look -- measured
2026-10-12 on the committed database, N = 75 against 74, retroactively for all 130 methods --
while another variant of a counted idea costs nothing.
```

**Impact:** `_run` is the only production caller of `run_method`; Step 9 passes the flag.

---

### Step 8: `lab/prereg.py`, `lab/remeasure.py`, `lab/real_costs.py`, `lab/exposure.py`, `lab/survivorship_check.py`, `commands/promote.py`, `lab/hardgate.py`

**File:** `engine/src/seer_engine/lab/prereg.py:18-19` (docstring) and `:434-480` (`check_source`)

**Code — replace the docstring bullet 2:**

```
2. the live method file still hashes to the sha the lab last ran it under
   (``store.latest_source_sha``: the newest ``method_amendments`` row, else the
   ``methods.source_sha`` frozen when the method first ran), and the named candidate still digests
   to the recorded digest (``check_source``);
```

**Code — replace `check_source` (`prereg.py:434-480`) with:**

`sqlite3.Row` carries no connection, so `check_source` must be handed one. It has exactly **one**
caller — `prereg.promote_method` at `prereg.py:667`, which already holds `conn` — and one
docstring reference at `:645`. Its `row` argument then goes unused and must be dropped, or ruff's
`F` rules flag it. Final signature:
`def check_source(conn: sqlite3.Connection, method_id: str, trial: sqlite3.Row) -> Path:`, and the
call site becomes `check_source(conn, method_id, trial)`.

```python
def check_source(conn: sqlite3.Connection, method_id: str, trial: sqlite3.Row) -> Path:
    """The method file still is what the trial measured; returns its path.

    Two equalities, both ``PreregError`` when broken:

    - the file's sha256 is the sha the lab last ran it under -- ``store.latest_source_sha``: the
      newest ``method_amendments`` row, falling back to the ``methods.source_sha`` frozen when the
      method first ran, which ``lab run`` set once and ``methods_source_sha_once`` keeps. For a
      method with no amendment, and that is every method recorded before 2026-10-12, the two are
      the same value;
    - the candidate the trial names still digests to the trial's ``config_digest``, so the thing
      about to be pre-registered is the thing that was measured.

    The second is implied by the first for most edits, and is checked anyway: ``config_digest``
    canonicalizes ``TradeRules`` and allocator params defined in *other* files, so the method
    file's own bytes do not pin it. It is also the half that an amendment cannot loosen -- a file
    may grow new blocks, but no recorded trial's configuration may move.

    No git call. ``lab run`` already refused an uncommitted method file before recording these
    trials, and the sha answers "has it changed since" exactly, without a subprocess.

    It takes ``conn`` rather than the method ``row`` it used to, because the sha a reader should
    expect is no longer one column: ``latest_source_sha`` has to look at ``method_amendments``
    first.
    """
    from seer_engine.lab.method import discover

    methods = discover()
    if method_id not in methods:
        raise PreregError(f"no method file for {method_id} in seer_engine/lab/methods/")
    method, path = methods[method_id]
    recorded = store.latest_source_sha(conn, method_id)
    actual = source_sha(path)
    if recorded and actual != recorded:
        raise PreregError(
            f"{repo_path(path)} has changed since {method_id} last ran (sha256 {actual[:12]}, "
            f"recorded {str(recorded)[:12]}). Pre-registering it would name a file that is no "
            f"longer what produced these trials: restore the file from git, or make the change a "
            f"new variation method with its own dev trials"
        )
    candidates = {c.id: c for c in method.all_candidates()}
    cid = str(trial["candidate_id"])
    if cid not in candidates:
        raise PreregError(
            f"{repo_path(path)} no longer defines {cid}, which dev trial #{trial['n']} ran"
        )
    digest = config_digest(candidates[cid])
    if digest != trial["config_digest"]:
        raise PreregError(
            f"{cid} now digests to {digest[:12]}, but dev trial #{trial['n']} recorded "
            f"{str(trial['config_digest'])[:12]}: its rules, allocator or params changed after "
            f"it ran"
        )
    return path
```

**Code — replace the call at `prereg.py:667`:**

```python
        if check_method_file:
            check_source(conn, method_id, trial)
```

(`row` is still read elsewhere in `promote_method`, so leave the local alone; only the call
changes. `prereg.py:645`'s docstring mention of `check_source` needs no edit.)

**File:** `engine/src/seer_engine/lab/remeasure.py:369-386`

**Code — replace:**

```python
    recorded_sha = store.latest_source_sha(conn, method.id)
    if recorded_sha is None:
        raise store.LabError(
            f"{method.id} has no recorded source_sha, so nothing proves the method file on disk is "
            f"the one its trials ran under; a re-run would measure a different thing"
        )
    actual = source_sha(path)
    if actual != recorded_sha:
        raise store.LabError(
            f"{method.id}: the method file hashes {actual[:12]} but the lab last ran it under "
            f"{str(recorded_sha)[:12]}; the file changed after it ran. Re-running it would measure "
            f"a different configuration, not recover the recorded one"
        )
    # Every variant the method ever pre-registered, amendments included: `lab remeasure` re-runs
    # the trials the lab holds, and a method with an amendment holds trials from more than one
    # batch.
    by_digest = {config_digest(c): c for c in method.all_candidates()}
```

(The `row` local is still used above this block for other checks; leave it.)

**File:** `engine/src/seer_engine/lab/real_costs.py:70-73` and `:133` (inside `pick_candidate`, which starts at `:105`)

**Code — replace the comprehension in `real_cost_problem`:**

```python
    flat = [
        c.id
        for c in method.all_candidates()
        if c.rules.engine != "book" or getattr(c.rules, "cost_model", FLAT) != REAL
    ]
```

**Code — replace line 133:**

```python
    by_id = {c.id: c for c in method.all_candidates()}
```

**Code — `real_cost_problem`'s docstring, append one sentence:**

```
    An amendment's candidates are held to exactly the same rule, because ``all_candidates`` covers
    them: a method numbered M0031 or later cannot slip a flat-cost variant in through a later
    pre-registration.
```

**File:** `engine/src/seer_engine/lab/exposure.py:500`

Added by the reconciler (C6): the last three readers of `method.candidates` that mean "every
variant this method has". Each is one line, and each is a strict no-op until a method actually
carries an amendment — but after phase 5 lands, a reader left behind here reports an incomplete
book without saying so. `exposure.py` is otherwise **untouched** by this phase; phase 2 imports
this module and edits none of it, so the two do not collide.

**Code — replace line 500:**

```python
    by_id = {c.id: c for c in method.all_candidates()}
```

**Code — the enclosing function's docstring, append one sentence:**

```
    Every variant the method ever pre-registered, amendments included: a recorded trial may come
    from a later batch (``method.Amendment``), and a diagnostic that skipped those would report an
    incomplete book with no sign that it had.
```

**File:** `engine/src/seer_engine/lab/survivorship_check.py:133`

**Code — replace line 133:**

```python
    by_id = {c.id: c for c in method.all_candidates()}
```

**File:** `engine/src/seer_engine/commands/promote.py:205-213`

**Code — replace those three reads inside `_resolve`:**

```python
    ids = tuple(c.id for c in method.all_candidates())
    if candidate_id is None:
        if len(ids) != 1:
            raise NotPromotable(
                f"{method_id} has {len(ids)} variants ({', '.join(ids)}); they are different "
                f"algorithms, so name the one to promote with --candidate"
            )
        return method, path, method.all_candidates()[0]
    found = [c for c in method.all_candidates() if c.id == candidate_id]
```

This is the owner's real-money promotion path. No amendment candidate can reach it today —
`AMEND_CLOSED` refuses to amend a method that has reached the test window, and nothing promotes
without one — but the comprehension would be wrong the moment that changed, and getting it right
costs one word. Nothing else in `promote.py` moves; the `--candidate` flag, the roster write and
every message are unchanged.

**File:** `engine/src/seer_engine/lab/hardgate.py:342-345`

**Code — replace those four lines:**

```
**Why not (a), and so not (c).** The field cannot live in the method files: a file that has run is
frozen against the sha the lab last recorded for it (``runner.preflight``, ``store.latest_source_sha``,
``test_a_method_that_ran_is_frozen_to_its_latest_recorded_sha``), and that is all 30 files on disk,
the four ``test-failed`` methods among them -- so the very methods kin has to point at could never
carry it. (Since 2026-10-12 a file may grow ``Amendment`` blocks, but only for a method that has
not reached the test window: ``runner.AMEND_CLOSED`` refuses the four ``test-failed`` books
outright, so this paragraph's argument is unchanged.)
```

**Impact:** three freeze readers now resolve the sha the same way; **every** reader of "what
variants does this method have" now asks `all_candidates()`, with none left behind; one docstring
stops asserting a rule the tree no longer has.

**Verification for the three added reads** — `grep` must come back empty afterwards:

```bash
grep -rn "method\.candidates" engine/src/seer_engine/ | grep -v "lab/methods/"
```

Expect exactly **two** hits, both in `runner.py` and both deliberate, because both mean *the
original batch and not the amendment's*:

- `preflight`'s `running = method.candidates` on the non-amend branch (Step 6);
- `run_method`'s `candidates = method.candidates if amendment is None else amendment.candidates`
  (Step 7).

Steps 6 and 7 also remove the two incidental reads at `runner.py:477` and `:483` (the progress
counter and the `run_registry` argument), which become `len(candidates)` and `candidates`.

---

### Step 9: `commands/lab.py` — `--amend` on the existing `run` subparser, and the summary

**File:** `engine/src/seer_engine/commands/lab.py:181-195` (subparser) and `:1365`, `:1395`,
after `:1399` (`_run`)

**Code — insert into the `run` subparser, after the `--allow-coverage` argument (currently
ending at line 195), before the blank line that precedes `promote`:**

```python
    s.add_argument(
        "--amend",
        action="store_true",
        help=(
            "run the next pre-registered Amendment this method file declares, instead of its "
            "original candidates. The trials land under the same method id, so the luck gate's N "
            "does not move and no method id is spent; `methods.source_sha` is left alone and the "
            "file's current sha is appended to `method_amendments`. The method must have run, "
            "must not have reached the test window, and the amendment must be committed -- the "
            "commit is its pre-registration. The method's status is not moved: use `lab "
            "reevaluate` if an amendment's trial clears every condition"
        ),
    )
```

**Code — replace `_run` line 1365:**

```python
    amendment = runner.preflight(conn, method, path, amend=args.amend)
```

**Code — replace `_run` line 1395:**

```python
    ran = runner.run_method(
        conn, method, path, data, git_sha=runner.git_head(config.REPO_ROOT), amend=args.amend
    )
```

**Code — replace `_run` lines 1399-1400 (the untouched §5.1 print, then `return 0`) with:**

```python
    print(f"\nLab N (dev trials) is now {store.dev_trial_count(conn)}; test-window looks used: {store.test_looks(conn)}")
    if amendment is not None:
        g = store.gate(conn)
        seq = len(store.amendments_of(conn, method.id))
        print(
            f"\n{method.id} amendment {seq} recorded: {len(ran)} trial(s) under {method.id}'s own "
            f"id, so no method id was spent."
        )
        print(f"  added           {amendment.added.isoformat()}")
        print(f"  why             {amendment.why.strip()}")
        print(f"  file sha        {store.latest_source_sha(conn, method.id)}")
        print(f"  luck gate       N = {g.n} (policy {g.policy})")
        print(
            f"  status          {status} (unchanged -- an amendment appends trials, it never moves "
            f"a verdict; `lab reevaluate {method.id}` is the one door on rejected -> dev-eligible)"
        )
    return 0
```

> Line 1399 itself is reproduced **verbatim** above and must stay byte-identical: it is one of the
> ten §5.1 strings this plan set does not touch. Its line *number* shifts by the lines the new
> subparser argument adds; phase 6 quotes those ten numbers at base commit `d3c1ec4`.

**Impact:** `lab run --amend M0030` becomes runnable. `args.amend` is `False` for every other
invocation, so `_run`'s behaviour is unchanged without the flag.

---

### Step 10: `engine/tests/test_lab_methods.py` — the freeze test becomes two

**File:** `engine/tests/test_lab_methods.py:9-10` (docstring), `:32` (`CANDIDATES`), `:113-129`

**Code — replace the docstring's last bullet (lines 9-10):**

```
- a method that has run is frozen against the sha the lab last ran it under: its file's sha256
  equals ``store.latest_source_sha`` (the newest ``method_amendments`` row, else the
  ``methods.source_sha`` recorded when it first ran), **and** every configuration the committed
  lab has a trial for still digests to the ``config_digest`` that trial recorded. The two together
  replaced the old whole-file freeze when amendments arrived (``method.Amendment``).
```

**Code — replace line 32:**

```python
CANDIDATES = [(mid, c) for mid, (m, _) in METHODS.items() for c in m.all_candidates()]
```

**Code — replace `test_a_method_that_ran_is_frozen` (lines 113-129) with:**

```python
def _committed_lab():
    """A read-only connection to the committed lab, or None when this tree has no database.

    The committed database, not ``SEER_LAB_DB``: in a sera worktree the shared database already
    holds sibling methods whose files this tree does not have yet. Raw ``sqlite3`` rather than
    ``store.connect``, because connecting migrates -- and a test must never rewrite the committed
    file (``store.connect_readonly`` would do, but this predates it and the explicit URI says what
    it does).
    """
    if not store.COMMITTED_DB.exists():
        return None
    conn = sqlite3.connect(f"file:{store.COMMITTED_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def test_a_method_that_ran_is_frozen_to_its_latest_recorded_sha():
    """Half one of the freeze: the file on disk is the file the lab last ran, or the one it is
    about to run next.

    Not ``methods.source_sha`` directly but ``store.latest_source_sha``, which is that column
    until the method gains an amendment and the newest ``method_amendments`` row afterwards. The
    column is still written once and never rewritten, so for a method with no amendment -- which
    is every method recorded before 2026-10-12 -- this asserts exactly what it asserted before.

    **The pre-registration window, and why it is tolerated.** An amendment is pre-registered by
    the commit that writes it and recorded only by the ``lab run --amend`` that executes it, so
    between those two moments the file legitimately hashes to something no row holds. That window
    is the mechanism, not a hole in it: the commit has to land first, because the commit *is* the
    pre-registration. So a sha mismatch is accepted on exactly one condition --
    ``runner.pending_amendment`` resolves, which means the file declares an ``Amendment`` the lab
    has not recorded **and** every amendment it *has* recorded still matches the block it was
    written from, field for field. Any other mismatch is the old failure, unchanged.

    What is never tolerated is the thing the freeze exists to protect, and it is checked
    separately and unconditionally by
    ``test_every_recorded_configuration_still_digests_to_its_recorded_digest``: a recorded trial's
    configuration may not move, amendment or no amendment. That test has no window.
    """
    conn = _committed_lab()
    if conn is None:
        pytest.skip("no lab database")
    try:
        ran = conn.execute(
            "SELECT id FROM methods WHERE id GLOB 'M*' AND source_sha IS NOT NULL"
        ).fetchall()
        for row in ran:
            mid = str(row["id"])
            assert mid in METHODS, f"{mid} ran but its method file is gone"
            method, path = METHODS[mid]
            expected = store.latest_source_sha(conn, mid)
            actual = source_sha(path)
            if actual == expected:
                continue
            try:
                runner.pending_amendment(conn, method)
            except store.LabError as e:
                raise AssertionError(
                    f"{mid} changed after the lab last ran it (file {actual[:12]}, recorded "
                    f"{str(expected)[:12]}) and it has no committed, unrecorded Amendment to "
                    f"explain the difference: {e}. A method file is frozen against its latest "
                    "recorded sha: a further question about the same idea is an Amendment "
                    "(committed first, run with `lab run --amend`), a different idea is a new "
                    "variation method"
                ) from e
    finally:
        conn.close()


def test_every_recorded_configuration_still_digests_to_its_recorded_digest():
    """Half two of the freeze, and the one an amendment cannot loosen.

    ``config_digest`` canonicalizes ``TradeRules`` and allocator params defined in *other* files,
    so a method file's own sha does not pin what its candidates do. This is the check that does,
    and it is also the proof of plan invariant 3: ``Method`` gained an ``amendments`` field, and
    ``registry._canon`` renders a dataclass by enumerating every ``compare=True`` field -- but
    ``config_text`` never passes a ``Method`` to ``_canon``, only ``c.rules``, ``c.allocator.id``
    and ``c.params``. Measured on the committed lab 2026-10-12, before the field existed: 63
    method files, 0 digests drifted. This test keeps that at 0.
    """
    conn = _committed_lab()
    if conn is None:
        pytest.skip("no lab database")
    try:
        drifted: list[str] = []
        for row in conn.execute(
            "SELECT id FROM methods WHERE id GLOB 'M*' AND source_sha IS NOT NULL"
        ).fetchall():
            mid = str(row["id"])
            method, _ = METHODS[mid]
            have = {config_digest(c) for c in method.all_candidates()}
            for t in conn.execute(
                "SELECT candidate_id, config_digest FROM trials WHERE method_id = ?", (mid,)
            ):
                if str(t["config_digest"]) not in have:
                    drifted.append(f"{mid}/{t['candidate_id']}")
        assert drifted == [], (
            f"{', '.join(drifted)}: a recorded trial's configuration is no longer one the method "
            "file produces. Its rules, allocator or params changed after it ran, which rewrites "
            "history the lab has already published"
        )
    finally:
        conn.close()
```

**Code — add `config_digest` to the import at `test_lab_methods.py:29`, and import `runner`
beside `store` (the pending-amendment tolerance needs both):**

```python
from seer_engine.lab import runner, store
from seer_engine.lab.method import config_digest, discover, source_sha
```

(`store` is already imported in this module; add `runner` to that line rather than a second one.)

**Impact:** `CANDIDATES` grows to cover amendment candidates, so phases 3 and 4 get the purity,
allocator-contract, smoke-window and unique-allocator-id checks on their new variants for free —
with no further test work in those phases.

**Impact — this is the check that lets phases 3 and 4 land at all.** Both M0030's and M0053's
files hash to exactly their recorded `methods.source_sha` today (measured 2026-10-12: M0030
`3b6aad38e1f1…`, M0053 `2289c49024df…`, both `dev-eligible`). The moment phase 3 or phase 4 writes
its amendment block, the file differs from every recorded sha — and the row that would make the
new sha "the latest recorded" is written by **phase 5**, which cannot start until those blocks
exist. Without the `pending_amendment` branch above this test is red for the whole interval
between phase 3/4 landing and phase 5 running, through no fault of either phase, and the set
deadlocks. The branch is deliberately narrow: it accepts a mismatch only when the file carries a
committed `Amendment` with no `method_amendments` row, and only while every amendment that *does*
have a row still matches it field for field.

**The other three freeze readers keep the strict comparison, and that is correct.**
`prereg.check_source`, `remeasure.preflight` and `runner.preflight_test` compare against
`latest_source_sha` with no pending-amendment branch: each of them is about to spend something
irreversible (a pre-registration file, a re-measure of the record, the one test-window look) on a
file state the lab has not recorded. Refusing there is the right answer, and no step of this plan
set reaches any of them — phase 5 runs `lab run --amend`, `lab gate` and `lab walkforward` only.

---

### Step 11: `engine/tests/test_lab_snapshot.py` — the v5 → v6 migration

**File:** `engine/tests/test_lab_snapshot.py:27-40`, `:116`, `:275-286`, `:357`, and a new test

**Code — insert before `_without_moments` (line 27):**

```python
def _without_amendments(schema: str) -> str:
    """``schema`` as it read at v5: the ``method_amendments`` table and its triggers removed.

    Derived from ``store._SCHEMA`` exactly as ``_without_moments`` and ``_without_provenance`` are,
    for the same reason: a fixture that is supposed to be an older database must not quietly carry
    a newer table.
    """
    for ddl in (store._AMENDMENTS_TABLE, *store._AMENDMENTS_TRIGGERS):
        assert f"{ddl};\n\n" in schema
        schema = schema.replace(f"{ddl};\n\n", "")
    assert "method_amendments" not in schema
    return schema


V5_SCHEMA = _without_amendments(store._SCHEMA)
```

**Code — replace line 39:**

```python
V2_SCHEMA = _without_moments(V5_SCHEMA)
```

**Code — replace line 286:**

```python
V4_SCHEMA = _without_provenance(V5_SCHEMA)
```

**Code — replace line 116 and the assertions after it:**

```python
        assert store.schema_version(conn) == store.SCHEMA_VERSION == "6"
```

and add, beside the two existing `sqlite_master` table assertions in that test:

```python
        assert conn.execute(
            "SELECT count(*) FROM sqlite_master WHERE type = 'table' AND name = 'method_amendments'"
        ).fetchone()[0] == 1
```

**Code — replace line 357:**

```python
        assert store.schema_version(conn) == store.SCHEMA_VERSION == "6"
```

**Code — append this test after
`test_connect_migrates_a_v4_database_backfilling_provenance_and_touching_no_trial`:**

```python
def _amendments_schema(conn) -> list[tuple[str, str, str]]:
    return [tuple(r) for r in conn.execute(
        "SELECT type, name, sql FROM sqlite_master WHERE tbl_name = 'method_amendments' "
        "ORDER BY type, name"
    )]


def _v5_db(path):
    """A schema-v5 database: one method that has run, one dev trial, no amendments table."""
    c = sqlite3.connect(path)
    c.executescript(V5_SCHEMA)
    c.executemany("INSERT INTO transitions (src, dst) VALUES (?, ?)", store.TRANSITIONS)
    c.execute("INSERT INTO meta (key, value) VALUES ('schema_version', '5')")
    c.execute(
        "INSERT INTO methods (id, name, family, source_kind, hypothesis, status, source_sha, "
        "created, updated) VALUES ('M0001', 'n', 'f', 'knowledge', 'h', 'dev-eligible', ?, "
        "'2026-10-01T00:00:00+00:00', '2026-10-01T00:00:00+00:00')",
        ("a" * 64,),
    )
    c.execute(
        'INSERT INTO trials (method_id, candidate_id, config_digest, config_text, rules_id, '
        'allocator_id, window, start, "end", store_fingerprint, git_sha, run_at, trades, '
        "sharpe, mar, failed, eligible, dsr, n_trials_at_run, curve_json) VALUES "
        "('M0001', 'M0001-A', 'd1', 't', 'r', 'a', 'dev', '2000-01-03', '2015-10-16', 'fp', "
        "'abc', '2026-10-05T00:00:00+00:00', 200, 0.945, 0.82, '', 0, 0.9, 110, '[]')"
    )
    c.execute(
        "INSERT INTO trial_provenance (trial_n, initial_idr, price_fingerprint, source, measured) "
        "VALUES (1, '20000000', NULL, 'backfill', '2026-10-09T00:00:00+00:00')"
    )
    c.commit()
    c.close()


def test_connect_migrates_a_v5_database_adding_method_amendments_and_touching_no_row(tmp_path):
    """v5 -> v6 is purely additive: a table, two triggers, a version string, and nothing else.

    No method row and no trial row moves -- in particular ``methods.source_sha`` is not read,
    rewritten or backfilled, because the amendment mechanism never rewrites it. The table that
    arrives by migration is as append-only as one a fresh database creates.
    """
    db = tmp_path / "lab.sqlite"
    _v5_db(db)
    before = _trials_bytes(db)
    methods_before = sqlite3.connect(db).execute("SELECT * FROM methods ORDER BY id").fetchall()

    conn = store.connect(db)
    fresh = store.connect(tmp_path / "fresh.sqlite")
    try:
        assert store.schema_version(conn) == store.SCHEMA_VERSION == "6"
        assert _trials_bytes(db) == before
        assert [tuple(r) for r in conn.execute("SELECT * FROM methods ORDER BY id")] == [
            tuple(r) for r in methods_before
        ]
        assert _amendments_schema(conn) == _amendments_schema(fresh)
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        assert conn.execute("SELECT count(*) FROM method_amendments").fetchone()[0] == 0
        assert store.amendments_of(conn, "M0001") == []
        assert store.latest_source_sha(conn, "M0001") == "a" * 64
        with conn:
            store.insert_amendment(conn, store.AmendmentRow(
                method_id="M0001", seq=1, source_sha="b" * 64, added="2026-10-12",
                why="w", hypothesis="h", expected_failure="e",
                run_at="2026-10-12T00:00:00+00:00", git_sha="deadbeef",
            ))
        assert store.latest_source_sha(conn, "M0001") == "b" * 64
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute("UPDATE method_amendments SET why = 'x'")
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute("DELETE FROM method_amendments")
        assert _trials_bytes(db) == before
        assert conn.execute("SELECT source_sha FROM methods WHERE id = 'M0001'").fetchone()[0] == "a" * 64
    finally:
        conn.close()
        fresh.close()

    again = store.connect(db)  # idempotent: a second connect adds nothing
    try:
        assert store.schema_version(again) == store.SCHEMA_VERSION
        assert again.execute("SELECT count(*) FROM method_amendments").fetchone()[0] == 1
        assert _trials_bytes(db) == before
    finally:
        again.close()
```

**Impact:** the v1/v2/v4 fixtures stay faithful to their own versions, and v6 gets the same
byte-identical-trials proof its three predecessors have.

---

### Step 12: the four lab-state snapshot helpers and the three other pinned tests

**File:** `engine/tests/test_lab_name_count.py:46-56`, `test_lab_costs.py:72-80`,
`test_lab_survivorship.py:144-155`, `test_lab_exposure.py:157-169`

**Change:** each `_untouched` helper already snapshots `(id, status, verdict, source_sha)` per
method. Add the amendment count beside it, so these report-only diagnostics are proved not to
append an amendment either, now that appending one is a thing the lab can do.

**Code — in each of the four, add this line to the returned tuple, immediately before the
`tuple(tuple(r) for r in conn.execute("SELECT id, status, verdict, source_sha FROM methods ...` entry:**

```python
        conn.execute("SELECT count(*) FROM method_amendments").fetchone()[0],
```

**File:** `engine/tests/test_lab_store.py:205-211`

**Code — replace `test_source_sha_is_set_once` with:**

```python
def test_source_sha_is_set_once_and_later_shas_go_to_method_amendments(conn):
    """The column is written once; an amended file's newer shas live in the side table.

    This is plan Decision D2 in one test: the trigger stays and keeps meaning what it says, and
    ``latest_source_sha`` -- not the column -- is what a freeze check reads.
    """
    _method(conn)
    with conn:
        store.update_method(conn, "M0001", source_sha="a" * 64)
    with pytest.raises(store.LabError, match="set once"):
        store.update_method(conn, "M0001", source_sha="b" * 64)
    assert store.latest_source_sha(conn, "M0001") == "a" * 64
    with conn:
        store.insert_amendment(conn, store.AmendmentRow(
            method_id="M0001", seq=1, source_sha="c" * 64, added="2026-10-12",
            why="the brakes are the drag", hypothesis="h", expected_failure="e",
            run_at="2026-10-12T00:00:00+00:00", git_sha="deadbeef",
        ))
    assert store.get_method(conn, "M0001")["source_sha"] == "a" * 64
    assert store.latest_source_sha(conn, "M0001") == "c" * 64
```

**File:** `engine/tests/test_lab_runner.py:133-139`

**Code — replace with:**

```python
def test_a_method_runs_once_and_configs_never_repeat(conn, data):
    """Without ``--amend`` the old refusal stands, and it now names the way through.

    The amendment path is tested in ``test_lab_amendments.py``; this keeps the default closed.
    """
    runner.run_method(conn, _method(), Path(__file__), data, git_sha="x", require_commit=False)
    with pytest.raises(store.LabError, match="runs once") as e:
        runner.preflight(conn, _method(), Path(__file__), require_commit=False)
    assert "--amend" in str(e.value)
    clone = _method("M0002", cands=(_cand("M0002-A", "M0002"),))  # same config as M0001-A
    with pytest.raises(store.LabError, match="repeats M0001-A"):
        runner.preflight(conn, clone, Path(__file__), require_commit=False)
```

**File:** `engine/tests/test_lab_prereg.py:292-298`

**Change:** the docstring says "`source_sha` is written wrong from the start, never re-written" and
cites `store.py:208`. Update the citation and add the amendment sentence; the test body is
unchanged (a method with no amendment resolves `latest_source_sha` to the column).

**Code — replace the docstring:**

```python
    """`source_sha` is written wrong from the start, never re-written.

    `methods_source_sha_once` fires on any change once the column is non-NULL -- NULL included --
    so a test cannot set it and then correct it. It sets the sha of a file that is not this one,
    which is exactly the state a post-run edit would leave behind. M0001 has no amendment here, so
    `store.latest_source_sha` resolves to that column and `check_source` reads the same wrong sha
    it always did.
    """
```

**Impact:** all four diagnostics, the two freeze tests and the runs-once test keep their meaning
under the new mechanism.

---

### Step 13: `engine/tests/test_lab_amendments.py` — the mechanism's own tests

**File:** `engine/tests/test_lab_amendments.py` (new)

**Code:**

```python
"""``lab run --amend``: a further pre-registered batch of variants of a method that has run.

The whole point of the mechanism is the gate: under ``store.DSR_POLICY = 'methods'`` a new method
id costs the lab one more independent look, retroactively, while another variant of an idea it has
already counted costs nothing. So the assertion that matters most here is that an amendment's
trials land under the method's own id and ``store.pending_gate`` does not move -- everything else
is the pre-registration discipline that keeps that cheapness honest.
"""

from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

import pytest
from labkit import smoke_data

from seer_engine.lab import runner, store
from seer_engine.lab.method import Amendment, Method, config_digest
from seer_engine.lab.seed import seed
from seer_engine.sim.rules import DAILY_SWITCH, MONTHLY_HOLD
from seer_engine.strategies.f_index import TIMING, TimingParams
from seer_engine.backtest.dev import Candidate

HERE = Path(__file__)


def _cand(cid: str, family: str, rules=MONTHLY_HOLD, n: int = 50) -> Candidate:
    return Candidate(
        id=cid, family=family, rules=rules, allocator=TIMING,
        params=TimingParams(hold="SPY", signal="SPY", rule="sma", n=n),
        rationale="test", added=date(2026, 10, 4), owner_inputs=(),
    )


def _amendment(*cands: Candidate, added: date = date(2026, 10, 12)) -> Amendment:
    return Amendment(
        added=added,
        why="the parked market money is the drag",
        hypothesis="the satellite at full size beats the blend after 2009",
        expected_failure="the worst fall goes past 20% and nothing is eligible",
        candidates=tuple(cands),
    )


def _method(mid="M0001", cands=None, amendments=(), **kw) -> Method:
    cands = cands or (_cand(f"{mid}-A", mid), _cand(f"{mid}-B", mid, rules=DAILY_SWITCH, n=20))
    base = dict(id=mid, name="SMA test", family="trend", source_kind="knowledge", source_ref="",
                hypothesis="h", expected_failure="f", candidates=tuple(cands),
                amendments=tuple(amendments))
    base.update(kw)
    return Method(**base)


def _amended(mid="M0001") -> Method:
    return _method(mid, amendments=(_amendment(_cand(f"{mid}-C", mid, n=75)),))


@pytest.fixture()
def conn(tmp_path):
    c = store.connect(tmp_path / "lab.sqlite")
    seed(c)
    yield c
    c.close()


@pytest.fixture(scope="module")
def data():
    return smoke_data()


# ---- the value ---------------------------------------------------------------------------------


def test_all_candidates_is_the_originals_then_each_amendments_in_order():
    m = _method(amendments=(
        _amendment(_cand("M0001-C", "M0001", n=75)),
        _amendment(_cand("M0001-D", "M0001", n=76), _cand("M0001-E", "M0001", n=77)),
    ))
    assert [c.id for c in m.all_candidates()] == ["M0001-A", "M0001-B", "M0001-C", "M0001-D", "M0001-E"]
    assert m.all_candidates()[:2] == m.candidates
    assert _method().all_candidates() == _method().candidates


def test_an_amendment_may_not_repeat_an_id_or_a_configuration_of_any_batch():
    with pytest.raises(ValueError, match="appears twice"):
        _method(amendments=(_amendment(_cand("M0001-A", "M0001", n=99)),))
    with pytest.raises(ValueError, match="repeats another variant's configuration"):
        _method(amendments=(_amendment(_cand("M0001-C", "M0001", n=50)),))
    with pytest.raises(ValueError, match="must have family M0001"):
        _method(amendments=(_amendment(_cand("M0001-C", "M0002", n=75)),))
    with pytest.raises(ValueError, match="must start with M0001-"):
        _method(amendments=(_amendment(_cand("M0009-C", "M0001", n=75)),))


def test_an_amendment_carries_one_to_six_candidates_of_its_own():
    """Decision D3: the cap is per amendment, not per method lifetime."""
    six = tuple(_cand(f"M0001-X{i}", "M0001", n=60 + i) for i in range(6))
    assert len(_method(amendments=(_amendment(*six),)).all_candidates()) == 8
    with pytest.raises(ValueError, match="1..6 candidates"):
        _amendment(*(_cand(f"M0001-Y{i}", "M0001", n=70 + i) for i in range(7)))
    with pytest.raises(ValueError, match="1..6 candidates"):
        Amendment(added=date(2026, 10, 12), why="w", hypothesis="h",
                  expected_failure="e", candidates=())


def test_adding_the_amendments_field_moves_no_config_digest():
    """Plan invariant 3, from the other side of ``test_lab_methods``'s recorded-trial check.

    ``config_text`` reads ``c.rules``, ``c.allocator.id`` and ``c.params`` and never the ``Method``
    that holds the candidate, so a field added to ``Method`` cannot reach ``registry._canon``.
    """
    plain = _method()
    amended = _amended()
    assert [config_digest(c) for c in plain.candidates] == [config_digest(c) for c in amended.candidates]


# ---- the record --------------------------------------------------------------------------------


def test_an_amendment_run_lands_under_the_same_method_id_and_moves_no_gate(conn, data):
    before = store.gate(conn)
    runner.run_method(conn, _method(), HERE, data, git_sha="x", require_commit=False)
    after_first = store.gate(conn)
    projected = store.pending_gate(conn, "M0001", 1)
    runner.run_method(conn, _amended(), HERE, data, git_sha="y", require_commit=False, amend=True)
    rows = store.trials_of(conn, "M0001")
    assert [r["candidate_id"] for r in rows] == ["M0001-A", "M0001-B", "M0001-C"]
    assert {str(r["method_id"]) for r in rows} == {"M0001"}
    # The batch was judged at the N `pending_gate` projected for an already-counted method, and
    # the lab's own N did not move because no new method was looked at.
    assert rows[-1]["n_trials_at_run"] == projected.n
    assert store.gate(conn) == after_first
    assert after_first.n >= before.n


def test_an_amendment_records_its_sha_and_leaves_methods_source_sha_alone(conn, data):
    runner.run_method(conn, _method(), HERE, data, git_sha="x", require_commit=False)
    first = store.get_method(conn, "M0001")["source_sha"]
    status_before = store.get_method(conn, "M0001")["status"]
    runner.run_method(conn, _amended(), HERE, data, git_sha="y", require_commit=False, amend=True)
    assert store.get_method(conn, "M0001")["source_sha"] == first
    assert store.get_method(conn, "M0001")["status"] == status_before  # Decision P2
    rows = store.amendments_of(conn, "M0001")
    assert [int(r["seq"]) for r in rows] == [1]
    assert str(rows[0]["source_sha"]) == first  # the same file, so the same sha, recorded anyway
    assert str(rows[0]["added"]) == "2026-10-12"
    assert str(rows[0]["why"]) == "the parked market money is the drag"
    assert str(rows[0]["git_sha"]) == "y"
    # The join back to the batch it pre-registered.
    assert str(rows[0]["run_at"]) == str(store.trials_of(conn, "M0001")[-1]["run_at"])
    assert store.latest_source_sha(conn, "M0001") == first


def test_method_amendments_is_append_only(conn, data):
    runner.run_method(conn, _method(), HERE, data, git_sha="x", require_commit=False)
    runner.run_method(conn, _amended(), HERE, data, git_sha="y", require_commit=False, amend=True)
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("UPDATE method_amendments SET why = 'something else'")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("DELETE FROM method_amendments")


def test_seq_must_be_contiguous(conn, data):
    runner.run_method(conn, _method(), HERE, data, git_sha="x", require_commit=False)
    with pytest.raises(store.LabError, match="amendment seq must be 1"):
        with conn:
            store.insert_amendment(conn, store.AmendmentRow(
                method_id="M0001", seq=2, source_sha="c" * 64, added="2026-10-12",
                why="w", hypothesis="h", expected_failure="e",
                run_at="2026-10-12T00:00:00+00:00", git_sha="z",
            ))


def test_an_amendment_needs_a_method_that_has_run(conn, data):
    with pytest.raises(store.LabError, match="has not run"):
        runner.preflight(conn, _amended(), HERE, require_commit=False, amend=True)
    with pytest.raises(store.LabError, match="nothing to amend"):
        with conn:
            store.insert_amendment(conn, store.AmendmentRow(
                method_id="M0001", seq=1, source_sha="c" * 64, added="2026-10-12",
                why="w", hypothesis="h", expected_failure="e",
                run_at="2026-10-12T00:00:00+00:00", git_sha="z",
            ))


def test_amend_refuses_a_method_file_that_declares_none(conn, data):
    runner.run_method(conn, _method(), HERE, data, git_sha="x", require_commit=False)
    with pytest.raises(store.LabError, match="declares none"):
        runner.preflight(conn, _method(), HERE, require_commit=False, amend=True)


def test_a_committed_but_unrun_amendment_is_the_one_tolerated_sha_mismatch(conn, data):
    """The pre-registration window, as a unit.

    ``pending_amendment`` resolving is exactly the predicate
    ``test_a_method_that_ran_is_frozen_to_its_latest_recorded_sha`` accepts a sha mismatch on, and
    it is the state phases 3 and 4 leave the tree in until phase 5 runs. It opens when the
    amendment is committed and closes the moment it is recorded; it is not a state a method can
    sit in twice for the same block.
    """
    runner.run_method(conn, _method(), HERE, data, git_sha="x", require_commit=False)
    m = _amended()
    assert store.amendments_of(conn, "M0001") == []      # committed, not yet run
    assert runner.pending_amendment(conn, m) == m.amendments[0]
    runner.run_method(conn, m, HERE, data, git_sha="y", require_commit=False, amend=True)
    with pytest.raises(store.LabError, match="have already run"):
        runner.pending_amendment(conn, m)                # window closed: the row exists now


def test_an_amendment_runs_once(conn, data):
    runner.run_method(conn, _method(), HERE, data, git_sha="x", require_commit=False)
    runner.run_method(conn, _amended(), HERE, data, git_sha="y", require_commit=False, amend=True)
    with pytest.raises(store.LabError, match="have already run"):
        runner.preflight(conn, _amended(), HERE, require_commit=False, amend=True)


def test_a_spent_amendment_may_not_be_edited(conn, data):
    """Plan Decision P4: the record is a prefix of the file, checked field for field."""
    runner.run_method(conn, _method(), HERE, data, git_sha="x", require_commit=False)
    runner.run_method(conn, _amended(), HERE, data, git_sha="y", require_commit=False, amend=True)
    edited = _method(amendments=(
        Amendment(added=date(2026, 10, 12), why="a different reason", hypothesis="h2",
                  expected_failure="e2", candidates=(_cand("M0001-C", "M0001", n=75),)),
        _amendment(_cand("M0001-D", "M0001", n=76)),
    ))
    with pytest.raises(store.LabError, match="no longer matches the one the lab recorded"):
        runner.preflight(conn, edited, HERE, require_commit=False, amend=True)
    dropped = _method()  # the amendment removed from the file entirely
    with pytest.raises(store.LabError, match="recorded 1 amendment"):
        runner.preflight(conn, dropped, HERE, require_commit=False, amend=True)


def test_a_method_that_reached_the_test_window_is_not_amended(conn, data):
    runner.run_method(conn, _method(), HERE, data, git_sha="x", require_commit=False)
    with conn:
        store.update_method(conn, "M0001", status="dev-eligible")
        store.update_method(conn, "M0001", status="promoted")
    with pytest.raises(store.LabError, match="not amended"):
        runner.preflight(conn, _amended(), HERE, require_commit=False, amend=True)


def test_an_amendment_may_not_repeat_a_recorded_configuration(conn, data):
    """``Method.__post_init__`` refuses it before any backtest is paid for.

    The database would refuse it too -- ``preflight``'s ``has_trial`` loop, and in the last resort
    ``trials``'s ``UNIQUE (config_digest, window)`` -- but the method file is the cheaper no, and
    it is the one a phase-3 or phase-4 author hits while writing the amendment.
    """
    runner.run_method(conn, _method(), HERE, data, git_sha="x", require_commit=False)
    with pytest.raises(ValueError, match="repeats another variant's configuration"):
        _method(amendments=(_amendment(_cand("M0001-C", "M0001", n=50)),))
```

**Impact:** 14 tests covering the value, the record, the refusals, the pre-registration window and the gate.

---

## Verification

Run everything from the worktree root with the main checkout's venv, with Postgres up.

**Setup**

```bash
docker start seer-pg
export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres
export PYTHONPATH=/home/miftah/.worktrees/seer/lab-brakes-and-gate/engine/src
cd /home/miftah/.worktrees/seer/lab-brakes-and-gate
md5sum lab/lab.sqlite      # expect 4a34ddb823ec88a5e86afeb5d7e1b7c9 (measured 2026-10-12)
```

**Build / import**

```bash
/home/miftah/seer/engine/.venv/bin/python -c "import seer_engine.lab.runner, seer_engine.lab.store, seer_engine.commands.lab; print('ok')"
```

**Lint**

```bash
/home/miftah/seer/engine/.venv/bin/ruff check engine
```

**Tests — the phase's own first, then the whole suite**

```bash
/home/miftah/seer/engine/.venv/bin/python -m pytest engine/tests/test_lab_amendments.py \
  engine/tests/test_lab_methods.py engine/tests/test_lab_store.py \
  engine/tests/test_lab_snapshot.py engine/tests/test_lab_runner.py \
  engine/tests/test_lab_prereg.py engine/tests/test_lab_remeasure.py \
  engine/tests/test_lab_costs.py engine/tests/test_lab_exposure.py \
  engine/tests/test_lab_survivorship.py engine/tests/test_lab_name_count.py \
  engine/tests/test_promote_command.py -q

/home/miftah/seer/engine/.venv/bin/python -m pytest engine/tests -q
```

CI fails if the DB tests skip, so confirm the summary says `0 skipped` beyond the three opt-in
live-store skips. Baseline on `main` @ `d3c1ec4` was **4364 passed / 3 skipped**; re-measure rather
than carrying that figure forward, and expect roughly +14 from Steps 11 and 13.

**CLI help still formats** (argparse `%` escaping, invariant):

```bash
/home/miftah/seer/engine/.venv/bin/python -m seer_engine lab run --help
```

**N has not moved** — a read-only probe, no `lab` command, so the database is never migrated:

```bash
/home/miftah/seer/engine/.venv/bin/python - <<'PY'
import sqlite3
from seer_engine.lab import store, npolicy
c = sqlite3.connect('file:lab/lab.sqlite?mode=ro', uri=True); c.row_factory = sqlite3.Row
print(store.gate(c))                                 # expect Gate(n=74, policy='methods')
print(store.pending_gate(c, 'M0030', 3))             # expect Gate(n=74, policy='methods')
print(store.pending_gate(c, 'M0053', 3))             # expect Gate(n=74, policy='methods')
print(npolicy.dev_method_count(c))                   # expect 74
PY
md5sum lab/lab.sqlite      # must still be 4a34ddb823ec88a5e86afeb5d7e1b7c9
```

**Manual check**

- `git status --porcelain lab/lab.sqlite web/data/lab.json` is **empty**. This phase commits
  neither; only phase 5 does, through `lab stage`.
- `git diff` touches no file under `engine/src/seer_engine/lab/methods/`.
- `git diff --stat engine/src/seer_engine/lab/exposure.py` shows **one** changed line.
- `git diff engine/src/seer_engine/commands/lab.py` shows the ten `Lab N (dev trials)` strings
  unchanged: `git diff -U0 engine/src/seer_engine/commands/lab.py | grep 'Lab N (dev trials)'`
  prints nothing, or only context lines, never a `-`/`+` pair.

**Exit criteria**

1. `store.SCHEMA_VERSION == "6"`, a fresh database carries `method_amendments`, and a v5 database
   migrates to it without a single `trials` or `methods` byte moving.
2. `Method` has `amendments` and `all_candidates()`; every recorded configuration in the committed
   lab still digests to its recorded `config_digest` (0 drifted, asserted by
   `test_every_recorded_configuration_still_digests_to_its_recorded_digest`).
3. `methods.source_sha` is still written once; `methods_source_sha_once` is still in `_SCHEMA`;
   `store.latest_source_sha` is what `prereg.check_source`, `remeasure.preflight` and
   `runner.preflight_test` read.
4. `lab run --amend MNNNN` exists, refuses a method that has not run, one that has reached the test
   window, a file that declares no amendment, an amendment that has already run, and an amendment
   that was edited after it ran — each at exit code 2.
5. Every reader of "what variants does this method have" asks `all_candidates()`:
   `grep -rn "method\.candidates" engine/src/seer_engine/ | grep -v "lab/methods/"` returns
   exactly the two deliberate hits in `runner.py` named in Step 8.
6. The freeze test is **green on a tree where a method file carries a committed `Amendment` that
   has no `method_amendments` row** — the state phases 3 and 4 leave behind. Prove it locally
   before handing off: add an `Amendment` to any already-run method file, commit it, run
   `pytest engine/tests/test_lab_methods.py -q`, and `git checkout --` the file afterwards.
7. `ruff check engine` clean; `pytest engine/tests` green with Postgres up; `lab/lab.sqlite` and
   `web/data/lab.json` unmodified in the working tree.

## Handoffs

- **`lab/exposure.py:500`, `lab/survivorship_check.py:133` and `commands/promote.py:205-213` are
  now this phase's** (reconciler, C6). They were handed off as follow-ups when this plan was
  written; the reconciler widened the scope instead, because a reader that silently skips an
  amendment's variants is a correctness bug the moment phase 5 lands. Step 8 holds all three, and
  the `grep` after it proves none is left. `exposure.py` is otherwise untouched, so phase 2 —
  which imports that module and edits none of it — is unaffected.
- **`exposure.load_dev_store`'s refusal text hardcodes "lab exposure"** and will read oddly when
  `lab gate` is what raised it. **Deliberately not fixed** (reconciler, C13): making the message
  name its caller is a signature change on a function phase 2 only imports, the exit code and the
  meaning of the refusal are already correct, and this phase's single line in `exposure.py` is an
  unrelated comprehension. Recorded in the index's Decisions rather than left as a silent gap.
- **`engine/package_readme.md`** gains a `lab run --amend` line as well as phase 2's `lab gate`
  line. **Phase 2 owns the file and writes both** (reconciler, C4/C5), which is safe because
  phase 2 now depends on this phase. This phase does not touch it. (The lab package has no
  `package_readme.md` of its own — `engine/package_readme.md` is the one, and its module map is
  where both lines go.)
- **R5 / §5.1** — the ten `Lab N (dev trials)` strings are untouched by this phase, as the user
  required. Their *line numbers* shift, because Step 9 adds an argument to the `run` subparser
  above them. Phase 6 should quote them at base commit `d3c1ec4`, as the handover does, or
  re-measure them on the branch.
- **Phases 3 and 4 depend on this phase's freeze test tolerating a pending amendment** — Step 10's
  `pending_amendment` branch. Without it both are red from the moment they land until phase 5
  runs, and phase 5 cannot run until they land. This is the one cross-phase dependency that
  decides whether the set executes at all; it is implemented here, in Step 10, not deferred.
- **Phases 3 and 4 need nothing beyond `Amendment` and `Method.amendments`.** Their new candidates
  get the purity, allocator-contract, smoke-window and unique-allocator-id checks for free from
  `test_lab_methods.py`'s widened `CANDIDATES`; neither phase needs to add a test for those.
- **Phase 5 should expect the coverage gate to run over `all_candidates()`.** If M0030's original
  candidates rank on `Market.fundamentals`, `preflight_data` will re-measure the panel against
  today's dev store (fingerprint `77c37d55…`, not the one M0030 ran on) and may want
  `--allow-coverage`. Measure before assuming.
- **Phase 5 is the only phase that commits `lab/lab.sqlite`**, and the first `lab` command it runs
  will migrate the committed file from v5 to v6. That migration must go into the `lab stage`
  commit, not a stray one; `web/data/lab.json` is unaffected (`snapshot` never reads `meta`).

## Rollback

This phase is one or more commits on `feature/lab-brakes-and-gate` touching only engine source and
tests. `git revert` them, in reverse order, and the tree is back at `d3c1ec4`'s lab behaviour:
`SCHEMA_VERSION` returns to `"5"`, `Method` loses the field, `preflight` refuses every already-run
method again.

The one asymmetry is the **database**, and only if a later phase has already run against it. A
database migrated to v6 and then reverted to v5 code is refused outright by `_migrate` —
`"lab database schema version '6' is unknown to this code"` — rather than silently misread. If that
happens before phase 5 has committed anything, restore the committed file by explicit path
(`git checkout -- lab/lab.sqlite`), whose md5 is `4a34ddb823ec88a5e86afeb5d7e1b7c9`. If phase 5 has
already landed, revert phase 5 first: the lab is append-only and its committed blob is the record,
so reverting that commit restores the whole v5 database, after which `lab stage` must be re-run so
`web/data/lab.json` agrees row for row again, and trial `n` must be checked for contiguity.

Nothing outside the branch is written: `engine/.research` is read-only to this phase, and
`lab/lab.sqlite` is never committed by it.

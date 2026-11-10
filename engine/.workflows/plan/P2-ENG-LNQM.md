> Adopted from `.workflows/plan/LAB_RUN_REFUSES_REPEAT_BOOKS_PLAN.md` phase 1. Source: `.workflows/plan/lab-run-refuses-repeat-books/phase-1.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 1: Refuse repeat books in `lab run`; neighbours in `lab idea`; skills

**Plan set:** `LAB_RUN_REFUSES_REPEAT_BOOKS_PLAN.md`
**Analysis:** `.workflows/analyze/20261110-091649-R7QX_code_analyzer.md`
**Satisfies:** R1, R2, R3, R4. A method Sera runs cannot record, without saying so, a book the lab already holds under another method. The check needs no owner step, compares the curve bytes, and uses no embeddings, network or new dependency.
**Depends on:** none
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine/lab`

---

## Goal

Today `lab run` writes every arm and only afterwards prints a "Book twins" block. After this
phase it compares each finished arm's curve with the record **before anything is written**. An
arm that repeats a book another method recorded first, without declaring it, makes the run exit 2.
Nothing is recorded, no N is spent and no arm metric is printed. A batch in which every arm
repeats a recorded book is refused even when every arm is declared. `lab idea` also prints, on
stderr, the five methods already in the lab whose words overlap the new idea most, so the agent
reserving an id sees likely repeats. The Sera and explore skills say what an agent does on the
refusal, with no owner step.

Measured this session on the committed `lab/lab.sqlite` at `22d1051`: 1,952 dev trials. 213 of them
carry a `(trades, curve_json)` an earlier dev trial already carried, and in 207 of those 213 the
earliest recording belongs to another method.

## Interface Contract

**Deletes:** the per-arm metrics `log.info` inside `runner.run_method`'s `on_result` closure (`lab/runner.py:714-721`). The same line moves to `runner._log_arm` and fires only after the repeat check.
**Renames:** none
**Creates:**
- `twins.Recorded` (dataclass), `twins.recorded_as(conn, curve_json, trades, window="dev")`, `twins.Repeat` (dataclass), `twins.declaration(arm, method_id)`, `twins.repeats(conn, method_id, batch, window="dev")`, `twins.refused(found, batch_size)`, `twins.refusal(method_id, blocked, batch_size, *, amend)` (`lab/twins.py`)
- `runner._log_arm(i, total, row, cash)` (`lab/runner.py`)
- `commands.lab._Neighbour` (NamedTuple), `_idea_words`, `_nearest_methods`, `_print_idea_neighbours`, constants `_IDEA_STOPWORDS`, `_IDEA_WORD`, `_IDEA_NEIGHBOURS` (`commands/lab.py`)
- `engine/tests/test_lab_repeat_refusal.py`

**Signature changes:** none. `run_method`, `preflight`, `trial_rows`, `twins_of`, `first_recorded`, `for_method` and `report_lines` keep their signatures and behaviour. `lab idea` stdout is still the new id and nothing else; the neighbour list goes to **stderr**.
**New refusal:** `runner.run_method` raises `store.LabError` (CLI exit 2) after the simulation and before `insert_trials`, on both the plain path and `--amend`.
**Requires (from earlier phases):** none
**Leaves alone:** `lab/lab.sqlite` and every recorded row, `db/migrations/*`, `store` schema, `method.config_digest`, `store.DSR_POLICY` / `lab/npolicy.py`, `lab/hardgate.py` (D15 and D19 text included), `lab/control_shape.py`, `web/`, every `lab/methods/m*.py`.

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/twins.py` | modify | docstring section "Not a refusal at `lab run`" (l.34-36) rewritten; imports (l.44-51); new lookup and refusal rule added after `for_method` (after l.181) |
| `engine/src/seer_engine/lab/runner.py` | modify | module docstring step 1 (l.5-7); import `twins` (l.87); `run_method` body l.706-741: no metrics in `on_result`, check inside the write lock before `insert_trials`, then log; new `_log_arm` after `_hypothesis` (l.861-862) |
| `engine/src/seer_engine/commands/lab.py` | modify | imports (l.193-203); Book twins comment (l.2127-2131); `_idea` (l.3810-3819) + neighbour helpers |
| `engine/tests/test_lab_repeat_refusal.py` | create | rule, refusal, run-level and `lab idea` tests |
| `.claude/skills/sera-the-explorer/SKILL.md` | modify | slate rule "A wrapped host is not a new book" (l.93-103); Never-table row (l.244) |
| `.claude/skills/explore-and-experiment-new-method/SKILL.md` | modify | step 4 last bullet (l.200-204); step 6 (after l.218); step 9 (l.275-276); Never table (after l.546); Quick reference (l.565) |
| `.claude/skills/verify-seer/features/lab-cli.md` | modify | sub-features (l.5-7), drive block (l.24-25), gotchas (l.35) |

## Implementation Steps

### Step 0: Environment (no code)

The worktree has no `engine/.venv`. Either create one
(`python3.11 -m venv engine/.venv && engine/.venv/bin/pip install -e 'engine[dev]'`) or use the main
checkout's interpreter with `PYTHONPATH`. Every pytest and python command in this plan runs **from
the worktree root with `PYTHONPATH=$PWD/engine/src`**. Without it pytest quietly tests the main
checkout. Below, `PY` is the interpreter (`engine/.venv/bin/python` or
`/home/miftah/seer/engine/.venv/bin/python`).

Run the baseline first so a later failure is known to be new:
`PYTHONPATH=$PWD/engine/src $PY -m pytest engine/tests/test_lab_twins.py engine/tests/test_lab_runner.py engine/tests/test_lab_amendments.py -q`

### Step 1: twins.py: rewrite the "Not a refusal" docstring section
**File:** `engine/src/seer_engine/lab/twins.py:34-36`
**Change:** replace the three-line paragraph that starts `**Not a refusal at ``lab run``.**` with:
```python
**Refused at ``lab run`` unless declared (2026-11-10).** The paragraph this replaces said a twin
"costs compute and nothing else". That was wrong on two counts. Measured on the committed lab
that day: 207 of 1,952 dev trials carried a curve and trade count another method had already
recorded. Every one of them was a Sera slot spent re-measuring a known book. And a method whose
only new arms are copies still gets a dev trial, so it raises N for every method after it. So
``runner.run_method`` now asks, after the simulation and before ``insert_trials``, whether each
arm's curve is already in the record (``recorded_as``). If the earliest recording belongs to
**another** method and the arm does not declare it (``declaration``: a control by
``control_shape.role_of``, or a rationale that names that method's id), the run is refused with
``store.LabError``. A batch in which **every** arm repeats a recorded book is refused even when
each one is declared, because it would measure nothing new (M0447). The refusal happens before
the trials are written, and N counts methods *with a dev trial*, so a refused run spends no N. No
arm's metrics are printed first, so the fix is chosen without seeing the result. The file is then
edited, re-committed (the new pre-registration) and run again.

**What stays an annotation.** A twin of an earlier arm of the **same** method (an amendment equal
to its original, a treatment equal to its own control) is recorded and flagged by
``report_lines`` exactly as before, because it is the method's own measurement. A declared repeat
is recorded too, and ``lab run``'s Book twins block still names it. ``lab promote`` still refuses
both cases that matter (hardgate D19). A near-twin (one trade apart) is a different book here, as
it is everywhere in this module.
```
**Impact:** docstring only.

### Step 2: twins.py: imports
**File:** `engine/src/seer_engine/lab/twins.py:44-51`
**Change:** replace the import block with:
```python
from __future__ import annotations

import hashlib
import re
import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from seer_engine.lab.control_shape import ROLE_CONTROL, Arm, role_of
```
**Impact:** `control_shape` imports only stdlib and `backtest.metrics`, so this adds no cycle. The "imports nothing that opens a database" promise in the module docstring still holds.

### Step 3: twins.py: lookup by an unrecorded curve and the refusal rule
**File:** `engine/src/seer_engine/lab/twins.py`. Insert after `for_method` (ends l.181) and before `report_lines` (l.184).
**Code:**
```python
@dataclass(frozen=True, slots=True)
class Recorded:
    """One recorded trial of a book, as the ``lab run`` refusal names it.

    ``Twin`` describes a recorded trial *relative to another recorded trial* (its ``of_*`` fields),
    so it cannot describe an arm that has not been written yet: there is no ``of_n`` to compare
    with. This is the half of ``Twin`` that exists before the write.
    """

    n: int
    method_id: str
    candidate_id: str
    store_fingerprint: str
    run_at: str

    def provenance(self) -> str:
        """``"trial 690, M0205, run 2026-10-17, store 77c37d55"``."""
        return (
            f"trial {self.n}, {self.method_id}, run {self.run_at[:10]}, "
            f"store {self.store_fingerprint[:8]}"
        )


def recorded_as(
    conn: sqlite3.Connection, curve_json: str, trades: int, window: str = "dev"
) -> tuple[Recorded, ...]:
    """Every recorded trial on ``window`` whose curve is ``curve_json`` byte for byte and whose
    trade count is ``trades``, earliest first. ``()`` for an empty curve (two absences are not one
    book) and when nothing matches. Never writes.

    ``curve_json`` must be the text ``store.curve_json`` produced, because that is what the
    ``trials`` row would carry. The runner passes ``TrialRow.curve_json`` from ``trial_rows`` for
    exactly that reason: what is checked is what would have been written.
    """
    if curve_json.strip() in _NO_CURVE:
        return ()
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM trials "
        "WHERE window = ? AND trades = ? AND curve_json = ? ORDER BY n",
        (window, int(trades), curve_json),
    ).fetchall()
    return tuple(
        Recorded(
            n=int(r[0]),
            method_id=str(r[1]),
            candidate_id=str(r[2]),
            store_fingerprint=str(r[5]),
            run_at=str(r[6]),
        )
        for r in rows
    )


@dataclass(frozen=True, slots=True)
class Repeat:
    """An arm about to be recorded whose book another method recorded first.

    ``declared`` is the reason the arm may run anyway, in words for the refusal message, or ``""``
    when it says nothing. A single string rather than a flag plus a reason, so "declared with no
    reason" and "undeclared with a reason" cannot be built.
    """

    candidate_id: str
    first: Recorded
    declared: str


def declaration(arm: Arm, method_id: str) -> str:
    """Why ``arm`` may repeat ``method_id``'s recorded book, or ``""`` when it does not say so.

    Two ways to say it, both pre-registered because both live in the committed method file.
    (1) The arm is a control by ``control_shape.role_of``, the same reader D17 and the Book twins
    block use. A paired control re-run on the treatment's frame is how the protocol prices the
    treatment, and it usually is a recorded book. (2) The arm's rationale names ``method_id`` on
    word boundaries, so ``M0125-DV-C10`` names M0125 and ``M01250`` does not. The author knew the
    host and said so.
    """
    if role_of(arm) == ROLE_CONTROL:
        return "a control arm"
    if re.search(rf"\b{re.escape(method_id)}\b", str(arm.rationale)):
        return f"its rationale names {method_id}"
    return ""


def repeats(
    conn: sqlite3.Connection,
    method_id: str,
    batch: Sequence[tuple[Arm, str, int]],
    window: str = "dev",
) -> tuple[Repeat, ...]:
    """The arms of ``batch`` (``(arm, curve_json, trades)``, in run order) whose earliest recorded
    twin belongs to a method other than ``method_id``, declared or not, in batch order.

    An arm whose earliest recording is this method's own is left out. That is an amendment
    re-measuring its original, the case ``report_lines`` already flags as an annotation, and a
    method's own record is not a repeat of somebody else's. Store fingerprints are not compared,
    for the reason in the module docstring.
    """
    out: list[Repeat] = []
    for arm, curve, trades in batch:
        found = recorded_as(conn, curve, trades, window)
        if not found or found[0].method_id == method_id:
            continue
        first = found[0]
        out.append(Repeat(
            candidate_id=str(arm.id), first=first, declared=declaration(arm, first.method_id),
        ))
    return tuple(out)


def refused(found: Sequence[Repeat], batch_size: int) -> tuple[Repeat, ...]:
    """The repeats that refuse the batch: every one of them when **every** arm repeats a recorded
    book (the batch would measure nothing new, declared or not), otherwise the undeclared ones.
    ``()`` means the batch may be recorded. Pure: reads nothing, writes nothing.
    """
    if len(found) > batch_size:
        raise ValueError(f"{len(found)} repeats in a batch of {batch_size}")
    if batch_size and len(found) == batch_size:
        return tuple(found)
    return tuple(r for r in found if not r.declared)


def refusal(
    method_id: str, blocked: Sequence[Repeat], batch_size: int, *, amend: bool
) -> str:
    """The ``store.LabError`` text for a refused batch. It names each refused arm, the first
    recording of its book, and the way through, which needs no owner. It carries no metric of any
    arm, because the fix has to be chosen before the result is seen.
    """
    again = f"lab run --amend {method_id}" if amend else f"lab run {method_id}"
    if batch_size and len(blocked) == batch_size:
        head = (
            f"{method_id}: every one of its {batch_size} arm(s) holds a book another method "
            f"already recorded, so this batch would measure nothing new. Nothing was recorded "
            f"and no N was spent."
        )
        fix = (
            "Declaring a repeat does not lift this one: add at least one arm that holds a book "
            "the lab has not recorded, or drop the idea (`lab drop`)."
        )
    else:
        head = (
            f"{method_id}: {len(blocked)} of {batch_size} arm(s) hold a book another method "
            f"already recorded, and do not say so. Nothing was recorded and no N was spent."
        )
        fix = (
            "Change each arm named here so it holds a different book, or, when re-measuring that "
            "book is the point, declare it truthfully: a control's rationale opens with "
            "\"Control:\", and any other arm names the method it repeats."
        )
    lines = [head]
    for r in blocked:
        note = f"  [declared: {r.declared}]" if r.declared else ""
        lines.append(
            f"  {r.candidate_id} = {r.first.candidate_id}, first recorded "
            f"({r.first.provenance()}){note}"
        )
    lines.append(f"  {fix}")
    lines.append(
        f"  Then commit the method file (that commit is the new pre-registration) and run "
        f"`{again}` again. A repeat is the same window, the same trade count and a byte-identical "
        f"equity curve: the same targets on every decision date (lab/twins.py)."
    )
    return "\n".join(lines)
```
**Impact:** additive. Nothing calls these until Step 5.

### Step 4: runner.py: module docstring and import
**File:** `engine/src/seer_engine/lab/runner.py:5-7`
**Change:** replace step 1 of the `lab run` list with:
```python
1. Refuse when the method file is not committed (its commit is the pre-registration), when the
   method has already run **and ``--amend`` was not given**, or when any variant this run is about
   to execute already has a dev trial. After the simulation and before anything is written,
   refuse a batch with an arm whose book another method recorded first and that does not declare
   it, or a batch in which every arm repeats a recorded book (``lab/twins.py``,
   ``twins.refused``). No arm's metrics are logged until that check passes.
```
**File:** `engine/src/seer_engine/lab/runner.py:87`
**Change:** `from seer_engine.lab import store` -> `from seer_engine.lab import store, twins`

### Step 5: runner.py: check before `insert_trials`, log after
**File:** `engine/src/seer_engine/lab/runner.py:706-741`. Replace from `capital = INITIAL_IDR` through the line `status = "dev-eligible" if any(r.trial.eligible for r in ran) else "rejected"` with:
```python
    capital = INITIAL_IDR
    results: list[tuple[DevRow, Any]] = []
    deposits: list[Sequence[tuple[date, float]]] = []

    def on_result(i: int, result: Any, row: DevRow) -> None:
        # Progress only. An arm's metrics are logged after the repeat check below (`_log_arm`),
        # because a refused batch is edited and re-run, and that edit must not be made after
        # seeing the result.
        results.append((row, month_end_curve(result.snapshots)))
        deposits.append(external_cashflows(result))
        log.info("[%d/%d] %s simulated", i + 1, len(candidates), row.candidate.id)

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
        # The repeat check (lab/twins.py). It reads the exact `curve_json` and `trades` these rows
        # would write, and it runs under the write lock for the same reason the preflight above is
        # repeated here: two Sera children running the same book in parallel must not both pass.
        # Raising inside `with conn` rolls back the IMMEDIATE transaction, which has written
        # nothing yet, so a refused batch leaves no method row, no trial and no N behind.
        batch = [(r.row.candidate, r.trial.curve_json, r.trial.trades) for r in ran]
        blocked = twins.refused(twins.repeats(conn, method.id, batch), len(batch))
        if blocked:
            raise store.LabError(
                twins.refusal(method.id, blocked, len(batch), amend=amendment is not None)
            )
        for i, (r, cash) in enumerate(zip(ran, deposits, strict=True)):
            _log_arm(i, len(ran), r.row, cash)
        status = "dev-eligible" if any(r.trial.eligible for r in ran) else "rejected"
```
**File:** `engine/src/seer_engine/lab/runner.py`. Insert directly after `_hypothesis` (l.861-862):
```python
def _log_arm(i: int, total: int, row: DevRow, cash: Sequence[tuple[date, float]]) -> None:
    """One recorded arm's result at INFO: the line ``on_result`` used to log as each arm finished.

    It moved here so it fires only after ``run_method``'s repeat check has passed. A refused batch
    prints no metric of any arm, so the redesign is made blind to the result.
    """
    m = row.stats.metrics
    log.info(
        "[%d/%d] %s %s..%s: money-weighted %s vs DCA SPY TR %s (%d deposits, %.2f USD), "
        "max DD %s, PF %s, trades %d",
        i + 1, total, row.candidate.id, row.start, row.end,
        m.mwr, row.spy_tr.mwr, len(cash), float(sum(a for _, a in cash)),
        m.max_drawdown, m.profit_factor, m.trades,
    )
```
**Impact:**
- The check runs **inside** the IMMEDIATE transaction, not before `begin_immediate` as the phase brief worded it. The brief's goal (refuse before `insert_trials`, write nothing) is unchanged. Inside the lock, two parallel sessions recording one book cannot both pass, and the rollback is the existing `with conn` one.
- `run_test`'s own `on_result` (l.1208) is not touched.
- Measured this session with a probe that wrapped `store.insert_trials`, against every test file that reaches the real `run_method` (`test_lab_costs`, `_exposure`, `_fold_verdict`, `_amendments`, `_remeasure`, `_runner`, `_gate_probe`, `_survivorship`, `test_survivorship_store`): 222 passed and **no** cross-method repeat was inserted, so no existing test hits the new refusal. The CLI-level twin tests (`test_lab_twins.py`, `test_lab_hardgate.py`) stub `run_method` and are unaffected.

### Step 6: commands/lab.py: imports
**File:** `engine/src/seer_engine/commands/lab.py:193-203`
**Change:** replace the stdlib import block with:
```python
import argparse
import dataclasses
import hashlib
import logging
import math
import os
import re
import statistics
import sys
import time
from collections import Counter
from datetime import date
from collections.abc import Sequence
from pathlib import Path
from typing import NamedTuple
```

### Step 7: commands/lab.py: Book twins comment
**File:** `engine/src/seer_engine/commands/lab.py:2127-2131` (the paragraph starting `# It ANNOTATES; it does not gate (hardgate D15). The protocol runs` inside the Book twins block, just above `from seer_engine.lab import twins` at l.2132)
**Change:** replace that paragraph (five comment lines) with:
```python
    # What reaches this block is what `runner.run_method` let through: twins of this method's own
    # earlier arms, and repeats of another method's book that the arm declared (a control, or a
    # rationale naming that method). An undeclared cross-method repeat, or a batch of nothing but
    # repeats, was refused before the write and never gets here (lab/twins.py). So this block
    # still ANNOTATES (hardgate D15) and `lab promote` still refuses the two cases that matter
    # (D19). Always printed, `none` included, because the Sera skills read this line. A FORWARDER
    # like the blocks above: the same `report_lines` `lab twins` prints, so the two can never
    # disagree about one arm.
```
**Impact:** comment only. The printed text is unchanged and the twins tests that match it still pass.

### Step 8: commands/lab.py: `lab idea` prints its nearest methods
**File:** `engine/src/seer_engine/commands/lab.py:3810-3819`. Replace `_idea` with the block below; the helpers sit directly above it.
**Code:**
```python
#: Words too common in the lab's prose to say two ideas are alike.
_IDEA_STOPWORDS = frozenset("""
a about after all also an and any are as at be been before beside both but by can each every for
from has have how if in into is it its last more most no not of on one only or over same so than
that the their them then there these they this those to under up very was were what when where
which while will with without would
""".split())
_IDEA_WORD = re.compile(r"[a-z][a-z0-9]+")
_IDEA_NEIGHBOURS = 5


class _Neighbour(NamedTuple):
    score: float
    id: str
    name: str
    status: str
    shared: tuple[str, ...]


def _idea_words(text: str) -> frozenset[str]:
    """The words an idea is compared on: lower-case, three letters or more, stopwords out."""
    return frozenset(
        w for w in _IDEA_WORD.findall(text.lower()) if len(w) > 2 and w not in _IDEA_STOPWORDS
    )


def _nearest_methods(
    rows: Sequence[tuple[str, str, str, str, str]], text: str, *, limit: int = _IDEA_NEIGHBOURS
) -> list[_Neighbour]:
    """The ``limit`` methods in ``rows`` (``(id, name, family, hypothesis, status)``) whose words
    are closest to ``text``'s, best first. A method sharing no word is left out.

    Cosine similarity over word sets, each word weighted by its inverse document frequency across
    ``rows``. A word every method uses ("book", "spy") says little, and a word two methods share
    ("hurst", "m0125") says a lot. The norm divides out a long hypothesis, so an essay does not
    outrank a short exact match. Stdlib and deterministic: no embeddings, no network, no model.
    The owner asked for something realistic on a free tier (R4). This is a hint for the agent
    reserving an id, and ``lab run``'s repeat check (lab/twins.py) is the guarantee. Measured
    2026-11-10 on the committed lab: an idea worded like M0115's dead-zone brake lists M0115 and
    M0109, and M0115's own text puts M0109 first.
    """
    docs = [
        (str(mid), str(name), str(status), _idea_words(f"{name} {family} {hypothesis}"))
        for mid, name, family, hypothesis, status in rows
    ]
    df = Counter(w for *_, words in docs for w in words)
    n = len(docs)

    def idf(w: str) -> float:
        return math.log((1 + n) / (1 + df.get(w, 0))) + 1.0

    query = _idea_words(text)
    qnorm = math.sqrt(sum(idf(w) ** 2 for w in query)) or 1.0
    out: list[_Neighbour] = []
    for mid, name, status, words in docs:
        shared = query & words
        if not shared:
            continue
        dnorm = math.sqrt(sum(idf(w) ** 2 for w in words)) or 1.0
        score = sum(idf(w) ** 2 for w in shared) / (qnorm * dnorm)
        top = tuple(sorted(shared, key=lambda w: (-idf(w), w))[:4])
        out.append(_Neighbour(score, mid, name, status, top))
    out.sort(key=lambda x: (-x.score, x.id))
    return out[:limit]


def _print_idea_neighbours(conn, mid: str, text: str) -> None:
    """Print, on stderr, the methods already in the lab closest in wording to ``mid``'s idea.

    On stderr so stdout stays the bare id that scripts capture with ``$(lab idea ...)``. It never
    refuses and never fails the command, because the id is already committed by the time this
    runs, and a hint that crashed would turn a good reservation into an error.
    """
    try:
        rows = [
            (str(r[0]), str(r[1]), str(r[2]), str(r[3] or ""), str(r[4]))
            for r in conn.execute(
                "SELECT id, name, family, hypothesis, status FROM methods WHERE id <> ?", (mid,)
            ).fetchall()
        ]
        near = _nearest_methods(rows, text)
    except Exception as e:  # noqa: BLE001 -- a hint must never fail a reservation already made
        print(f"Closest methods: not read ({e}). {mid} is reserved either way.", file=sys.stderr)
        return
    if not near:
        print(f"Closest methods: none share a word with {mid}'s name, family or hypothesis.",
              file=sys.stderr)
        return
    print(f"Closest methods already in the lab, by shared words. A hint, not a check: "
          f"`lab run` refuses a repeated book. If one is the same idea, `lab drop {mid}`; "
          f"otherwise name the closest in the hypothesis:", file=sys.stderr)
    for x in near:
        name = x.name if len(x.name) <= 90 else x.name[:87] + "..."
        print(f"  {x.id}  {x.score:.2f}  [{x.status}]  {name}", file=sys.stderr)
        print(f"         shares: {', '.join(x.shared)}", file=sys.stderr)


def _idea(conn, args) -> int:
    store.begin_immediate(conn)  # the next id and its insert, atomic against parallel sessions
    with conn:
        mid = store.next_method_id(conn)
        store.add_method(
            conn, id=mid, name=args.name, family=args.family, source_kind=args.source_kind,
            source_ref=args.source_ref, hypothesis=args.hypothesis, parent_id=args.parent,
        )
    print(mid)
    _print_idea_neighbours(conn, mid, f"{args.name} {args.family} {args.hypothesis}")
    return 0
```
**Impact:** stdout is unchanged (`M0552\n`). Callers reading stdout keep working. The new stderr lines show up in the agent's Bash output, which is where an agent reads them.

### Step 9: tests
**File:** `engine/tests/test_lab_repeat_refusal.py` (create)
**Code:**
```python
"""`lab run` refuses an arm that repeats a book another method recorded (lab/twins.py, runner).

Two halves. The rule is read off hand-built trial rows (the `test_lab_twins` fixtures: `_curve` is
deterministic, so two rows built with one ``annual`` and ``trades`` are one book). The refusal is
then driven through `runner.run_method` on the smoke market. A first lab records three arms, their
curves are copied into a second lab under another method id (M0090), and the second lab runs the
same arms again. Copying a curve the runner really produced is the only honest way to make the
simulator repeat a book on purpose: a hand-written curve would never match a simulated one.
"""

from __future__ import annotations

import argparse
import dataclasses
import logging
from datetime import date
from pathlib import Path

import pytest
from labkit import smoke_data

from seer_engine.commands import lab as lab_cmd
from seer_engine.lab import runner, store, twins
from seer_engine.lab.method import Amendment
from seer_engine.lab.seed import seed
from seer_engine.sim.rules import DAILY_SWITCH
from test_lab_hardgate import DEV_SPAN, R_DRAW, R_IDEA, _Arm, _curve, _months, _trial
from test_lab_runner import _cand, _method
from test_lab_twins import R_STEP, _arm, _method_row

HERE = Path(__file__)
HOST = "M0090"
CURVE = _curve(_months(*DEV_SPAN), 0.15)  # what `_arm` records at its defaults


# ------------------------------------------------------------------ the rule, on recorded rows


@pytest.fixture()
def conn(tmp_path):
    c = store.connect(tmp_path / "lab.sqlite")
    _method_row(c, "M0001")
    _method_row(c, "M0002")
    yield c
    c.close()


def test_recorded_as_finds_every_trial_of_an_unrecorded_book_earliest_first(conn):
    first = _arm(conn, "M0001", "A")
    second = _arm(conn, "M0002", "A")
    found = twins.recorded_as(conn, CURVE, 250)
    assert [(r.n, r.candidate_id) for r in found] == [(first, "M0001-A"), (second, "M0002-A")]
    assert found[0].provenance() == f"trial {first}, M0001, run 2026-10-06, store 640fc25e"
    assert twins.recorded_as(conn, CURVE, 251) == ()
    assert twins.recorded_as(conn, CURVE, 250, "test") == ()
    assert twins.recorded_as(conn, "[]", 250) == ()


def test_an_undeclared_repeat_of_another_methods_book_is_refused(conn):
    n = _arm(conn, "M0001", "A")
    found = twins.repeats(conn, "M0002", [(_Arm("M0002-X", R_STEP), CURVE, 250)])
    assert [(r.candidate_id, r.first.candidate_id, r.first.n, r.declared) for r in found] == [
        ("M0002-X", "M0001-A", n, ""),
    ]
    assert twins.refused(found, 2) == found


def test_a_control_arm_is_a_declared_repeat(conn):
    _arm(conn, "M0001", "A")
    found = twins.repeats(conn, "M0002", [(_Arm("M0002-NEVER", R_DRAW), CURVE, 250)])
    assert found[0].declared == "a control arm"
    assert twins.refused(found, 2) == ()


def test_naming_the_first_recording_method_declares_the_repeat(conn):
    _arm(conn, "M0001", "A")
    arm = _Arm("M0002-HOST", "M0001-A's book, run again so the pair shares one frame")
    found = twins.repeats(conn, "M0002", [(arm, CURVE, 250)])
    assert found[0].declared == "its rationale names M0001"
    assert twins.refused(found, 2) == ()


def test_naming_another_id_that_merely_contains_it_declares_nothing(conn):
    _arm(conn, "M0001", "A")
    arm = _Arm("M0002-HOST", "M00011's book, which is not this one")
    found = twins.repeats(conn, "M0002", [(arm, CURVE, 250)])
    assert found[0].declared == ""


def test_an_idea_arm_is_not_a_declaration(conn):
    _arm(conn, "M0001", "A")
    found = twins.repeats(conn, "M0002", [(_Arm("M0002-A", R_IDEA), CURVE, 250)])
    assert found[0].declared == ""


def test_every_arm_repeating_a_recorded_book_is_refused_even_when_declared(conn):
    _arm(conn, "M0001", "A")
    _arm(conn, "M0001", "B", annual=0.30)
    batch = [
        (_Arm("M0002-NEVER", R_DRAW), CURVE, 250),
        (_Arm("M0002-B", "M0001's other arm, named"), _curve(_months(*DEV_SPAN), 0.30), 250),
    ]
    found = twins.repeats(conn, "M0002", batch)
    assert all(r.declared for r in found)
    assert twins.refused(found, 2) == found


def test_a_book_first_recorded_by_this_same_method_is_not_a_repeat(conn):
    """An amendment re-measuring its original stays an annotation (`report_lines`)."""
    _arm(conn, "M0002", "A")  # the method's own earlier arm
    _arm(conn, "M0001", "A")  # the same book, recorded later by another method
    assert twins.repeats(conn, "M0002", [(_Arm("M0002-C", R_STEP), CURVE, 250)]) == ()


def test_a_repeat_across_store_fingerprints_is_still_a_repeat(conn):
    _arm(conn, "M0001", "A", store_fp="77c37d55aa")
    found = twins.repeats(conn, "M0002", [(_Arm("M0002-X", R_STEP), CURVE, 250)])
    assert found and "store 77c37d55" in found[0].first.provenance()


def test_the_refusal_names_each_arm_its_first_recording_and_the_way_through(conn):
    n = _arm(conn, "M0001", "A")
    found = twins.repeats(conn, "M0002", [(_Arm("M0002-X", R_STEP), CURVE, 250)])
    blocked = twins.refused(found, 2)
    said = twins.refusal("M0002", blocked, 2, amend=False)
    assert f"M0002-X = M0001-A, first recorded (trial {n}, M0001" in said
    assert "1 of 2 arm(s)" in said
    assert "Nothing was recorded and no N was spent" in said
    assert "`lab run M0002`" in said and "--amend" not in said
    assert "`lab run --amend M0002`" in twins.refusal("M0002", blocked, 2, amend=True)


def test_more_repeats_than_arms_is_a_caller_error():
    rec = twins.Recorded(n=1, method_id="M0001", candidate_id="M0001-A",
                         store_fingerprint="x", run_at="2026-11-10")
    with pytest.raises(ValueError):
        twins.refused([twins.Repeat("M0002-A", rec, ""), twins.Repeat("M0002-B", rec, "")], 1)


# ------------------------------------------------------------------ `lab run` itself


@pytest.fixture(scope="module")
def data():
    return smoke_data()


def _three() -> tuple:
    return (
        _cand("M0001-A", "M0001"),
        _cand("M0001-B", "M0001", rules=DAILY_SWITCH, n=20),
        _cand("M0001-C", "M0001", n=75),
    )


def _said(c, rationale: str):
    return dataclasses.replace(c, rationale=rationale)


@pytest.fixture(scope="module")
def books(tmp_path_factory, data):
    """``candidate -> (curve_json, trades)`` for the three arms, as a real run records them."""
    c = store.connect(tmp_path_factory.mktemp("books") / "lab.sqlite")
    seed(c)
    try:
        runner.run_method(c, _method(cands=_three()), HERE, data, git_sha="x", require_commit=False)
        out = {
            str(r["candidate_id"]): (str(r["curve_json"]), int(r["trades"]))
            for r in store.trials_of(c, "M0001")
        }
    finally:
        c.close()
    assert len(set(out.values())) == 3, "the fixture needs three different books"
    return out


@pytest.fixture()
def lab(tmp_path):
    c = store.connect(tmp_path / "lab.sqlite")
    seed(c)
    yield c
    c.close()


def _host(conn, books, *suffixes) -> list[int]:
    """Record ``books`` for ``suffixes`` under HOST, as if another method had run them first."""
    with conn:
        store.add_method(conn, id=HOST, name="the host", family="host",
                         source_kind="knowledge", hypothesis="h", status="registered")
        return store.insert_trials(conn, [
            _trial(method_id=HOST, candidate_id=f"{HOST}-{s}", config_digest=f"host-{s}",
                   curve_json=books[f"M0001-{s}"][0], trades=books[f"M0001-{s}"][1])
            for s in suffixes
        ])


def _metric_lines(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records if "money-weighted" in r.getMessage()]


def test_lab_run_refuses_an_undeclared_repeat_and_writes_nothing(lab, data, books, caplog):
    (n,) = _host(lab, books, "A")
    rows_before = store.dev_trial_count(lab)
    caplog.set_level(logging.INFO, logger="seer_engine.lab.runner")
    with pytest.raises(store.LabError) as e:
        runner.run_method(lab, _method(), HERE, data, git_sha="x", require_commit=False)
    said = str(e.value)
    assert f"M0001-A = {HOST}-A, first recorded (trial {n}, {HOST}" in said
    assert "M0001-B =" not in said
    assert store.dev_trial_count(lab) == rows_before
    assert store.trials_of(lab, "M0001") == []
    assert store.get_method(lab, "M0001") is None
    assert not lab.in_transaction
    assert _metric_lines(caplog) == [], "a refused batch must not show any arm's result"


def test_a_refused_idea_stays_an_idea_and_runs_once_the_arm_is_declared(lab, data, books, caplog):
    _host(lab, books, "A")
    with lab:
        store.add_method(lab, id="M0001", name="queued", family="trend",
                         source_kind="knowledge", hypothesis="old")
    with pytest.raises(store.LabError):
        runner.run_method(lab, _method(), HERE, data, git_sha="x", require_commit=False)
    assert store.get_method(lab, "M0001")["status"] == "idea"

    caplog.set_level(logging.INFO, logger="seer_engine.lab.runner")
    a, b = _method().candidates
    fixed = _method(cands=(_said(a, "Control: the host's book, run beside B"), b))
    ran = runner.run_method(lab, fixed, HERE, data, git_sha="y", require_commit=False).ran
    assert [r.trial.candidate_id for r in ran] == ["M0001-A", "M0001-B"]
    assert store.get_method(lab, "M0001")["status"] in ("rejected", "dev-eligible")
    assert len(_metric_lines(caplog)) == 2, "a recorded batch still logs every arm's result"


def test_naming_the_host_in_the_rationale_lets_the_arm_record(lab, data, books):
    _host(lab, books, "A")
    a, b = _method().candidates
    named = _method(cands=(_said(a, f"{HOST}-A's book again, so B is read on one frame"), b))
    ran = runner.run_method(lab, named, HERE, data, git_sha="x", require_commit=False).ran
    assert [r.trial.candidate_id for r in ran] == ["M0001-A", "M0001-B"]


def test_lab_run_refuses_a_batch_that_measures_nothing_new_even_when_declared(lab, data, books):
    _host(lab, books, "A", "B")
    a, b = _method().candidates
    both = _method(cands=(_said(a, "Control: the host's first book"),
                          _said(b, f"{HOST}'s second book, named")))
    with pytest.raises(store.LabError, match="measure nothing new"):
        runner.run_method(lab, both, HERE, data, git_sha="x", require_commit=False)
    assert store.trials_of(lab, "M0001") == []


def test_an_amendment_that_repeats_another_methods_book_is_refused_the_same_way(lab, data, books):
    runner.run_method(lab, _method(), HERE, data, git_sha="x", require_commit=False)
    (n,) = _host(lab, books, "C")
    amended = _method(amendments=(Amendment(
        added=date(2026, 11, 10), why="a slower average", hypothesis="h", expected_failure="e",
        candidates=(_cand("M0001-C", "M0001", n=75),),
    ),))
    rows_before = store.dev_trial_count(lab)
    with pytest.raises(store.LabError) as e:
        runner.run_method(lab, amended, HERE, data, git_sha="y", require_commit=False, amend=True)
    said = str(e.value)
    assert f"M0001-C = {HOST}-C, first recorded (trial {n}" in said
    assert "every one of its 1 arm(s)" in said
    assert "`lab run --amend M0001`" in said
    assert store.dev_trial_count(lab) == rows_before
    assert store.amendments_of(lab, "M0001") == []


# ------------------------------------------------------------------ `lab idea` neighbours


def _idea_args(db, **kw) -> argparse.Namespace:
    base = dict(
        db=db, lab_command="idea", name="A dead zone on the drawdown brake",
        family="drawdown-brake",
        hypothesis="Trim the book in proportion to its fall below its own high, ignoring small falls",
        source_kind="knowledge", source_ref="", parent=None,
    )
    base.update(kw)
    return argparse.Namespace(**base)


def test_lab_idea_prints_the_id_alone_on_stdout_and_its_nearest_methods_on_stderr(
    tmp_path, capsys
):
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    with c:
        store.add_method(c, id="M0001", name="A brake on the account's own fall",
                         family="drawdown-brake", source_kind="knowledge",
                         hypothesis="Trim in proportion to how far the book is below its own high",
                         status="registered")
        store.add_method(c, id="M0002", name="Buy last month's losers", family="reversal",
                         source_kind="knowledge", hypothesis="Short-term reversal on residuals",
                         status="registered")
    c.close()
    assert lab_cmd.run(_idea_args(db)) == 0
    got = capsys.readouterr()
    assert got.out == "M0003\n"
    listed = [ln.split()[0] for ln in got.err.splitlines() if ln.startswith("  M")]
    assert listed == ["M0001"]
    assert "lab drop M0003" in got.err


def test_lab_idea_never_refuses_in_an_empty_lab(tmp_path, capsys):
    db = tmp_path / "lab.sqlite"
    store.connect(db).close()
    assert lab_cmd.run(_idea_args(db)) == 0
    got = capsys.readouterr()
    assert got.out == "M0001\n"
    assert "none share a word" in got.err


def test_nearest_methods_weighs_rare_words_and_divides_out_a_long_hypothesis():
    rows = [
        ("M0001", "Quiet uptrend brake", "timing", "step aside in a quiet uptrend", "rejected"),
        ("M0002", "A long essay", "misc",
         "brake " + " ".join(f"filler{i}" for i in range(200)), "rejected"),
        ("M0003", "Nothing alike", "misc", "dividends calendar", "idea"),
    ]
    near = lab_cmd._nearest_methods(rows, "quiet uptrend brake")
    assert [x.id for x in near] == ["M0001", "M0002"]
    assert near[0].shared[:2] == ("quiet", "uptrend")
```
**Impact:** new module. It imports the fixtures of `test_lab_hardgate`, `test_lab_runner` and `test_lab_twins` the same way `test_lab_twins.py` imports `test_lab_hardgate`. The smoke fixture's 473-bar lookback cap is irrelevant: the arms are `TIMING` sma 20/50/75.
**Facts checked this session:** on the smoke market the three arms A, B and C give three different books (trades 4, 27, 2), and none matches a seed trial. `M0090` is not a seed id (seed ids are `H-*`). `status="registered"` on insert is the form the twins tests use.
**Test-fixture note:** `test_nearest_methods_...` expects `near[0].shared[:2] == ("quiet", "uptrend")`. Both words have df 1 and tie on idf, and the sort's alphabetical tiebreak makes that order deterministic. If the stopword list is changed, re-check this assert.

### Step 10: sera-the-explorer skill
**File:** `.claude/skills/sera-the-explorer/SKILL.md:93-103`. Replace the bullet `- **A wrapped host is not a new book.** …` (through `prints it again at any time.`) and the following `- **Reserve** …` bullet with:
```markdown
   - **A repeated book is refused, not recorded.** `lab run` compares every arm's finished
     equity curve and trade count with the record *before* it writes anything. If an arm's book
     was first recorded by **another** method and the arm does not say so, the run exits 2 and
     names the arm and the first recording (`M0246-SPY200 = M0205-SPY200, first recorded (trial
     690, …)`). Nothing is recorded, no arm's result is printed and no N is spent. An arm says
     so in one of two ways, both in its committed rationale: it is a control ("Control: …"), or
     it names the method it repeats (M0488's never-aside arm names M0125). A batch whose **every**
     arm repeats a recorded book is refused even when all are declared, because it would measure
     nothing new (every arm of M0447 did). A wrapper allocator or params class that gives a host a
     new digest no longer slips past. The refusal reads the curve, not the digest.
   - **Read the neighbour list before you settle a slate.** `lab idea …` prints the new id on
     stdout and, on stderr, up to five methods already in the lab whose name, family and
     hypothesis share the most words with it. It is a hint and never refuses. If one is the same
     idea, `lab drop MNNNN --why "same idea as M00xx"` (an idea with no trial costs no N) and
     choose another. Otherwise write the closest one into the hypothesis ("closest recorded:
     M00xx, which …") so the child designs against it.
   - **Reserve** each new idea with `lab idea …`, which prints its id. A backlog row keeps its id.
     The hypothesis can be a draft; the child sharpens it before its pre-registration commit.
```
**File:** `.claude/skills/sera-the-explorer/SKILL.md:244`. Replace the table row starting `| "This follow-up wraps a recorded host, so skip it" or "so count it as a new book" |` with:
```markdown
| "This follow-up wraps a recorded host, so skip it" or "so count it as a new book" | Neither. Re-measuring the host is fine as a *declared* control, which runs beside the treatment. Undeclared, `lab run` refuses it. Name the host in the hypothesis and the arm's rationale, and never count the arm as a new book. |
| "`lab run` refused a repeated book, ask the owner" or "mark the treatment as a control to get it through" | Neither. The child changes the arm so it holds a new book, or declares it truthfully if re-measuring is the point, re-commits the method file (the new pre-registration) and re-runs. No owner step, and nothing was spent. Relabelling a treatment as a control to pass the check falsifies the pre-registration. |
```

### Step 11: explore-and-experiment-new-method skill
**File:** `.claude/skills/explore-and-experiment-new-method/SKILL.md:200-204`. Replace the paragraph from `That no-opinion arm usually repeats a book the lab already ran.` through `never count the arm as a new book.` with:
```markdown
     That no-opinion arm usually repeats a book the lab already ran. `lab run` checks each arm's
     finished curve against the record before writing (step 6). A copy of another method's book
     is recorded only when the arm says so in its rationale: it opens "Control: …", or it names
     the method it repeats ("M0125-DV-C10's book, never stepping aside"). Write that now, in the
     pre-registration. Name the recorded host in the hypothesis too, and never count the arm as a
     new book. A method whose every arm repeats a recorded book is refused however it is labelled.
```
**File:** `.claude/skills/explore-and-experiment-new-method/SKILL.md`. Insert after step 6's last line (`with no live trigger is the failure.`, l.218) as a new paragraph inside step 6:
```markdown
   **Exit 2 naming a repeated book** (`MNNNN-X = M00yy-Z, first recorded (trial …)`) means
   `lab run` found an arm whose book another method recorded first, and the arm did not declare
   it, or found that every arm repeats a recorded book. Nothing was recorded, no result was
   printed, no N was spent, and the method is still `idea`/`registered`. Fix it without asking
   anyone. (a) Change the arm so it holds a different book: another dial, another pool, or drop
   the arm. (b) If re-measuring that book is the point (a paired control), say so truthfully: a
   control's rationale opens "Control: …", and any other arm names the method it repeats.
   (c) If every arm was a repeat, the idea measures nothing new: add an arm that does, or
   `lab drop MNNNN --why "repeats M00yy"` and report it. Then commit the method file again (that
   commit is the new pre-registration, so say in its message what changed and why) and run
   `lab run MNNNN` again (`--amend` for an amendment). Never relabel a treatment as a control to
   get past the check.
```
**File:** `.claude/skills/explore-and-experiment-new-method/SKILL.md:275-276`. Replace step 9 with:
```markdown
9. **Queue at least one next idea**: `lab idea --name … --family … --source-kind … --hypothesis …`
   (plus `--parent`), drawn from what this result taught. It prints the new id on stdout and, on
   stderr, the five methods already in the lab whose wording is closest. Read them. If one is
   the same idea, `lab drop` the new id with the reason. Otherwise name the closest recorded
   method in the hypothesis so the next session designs against it.
```
**File:** `.claude/skills/explore-and-experiment-new-method/SKILL.md`. Insert in the **Never** table after the row starting `| "Compare my numbers with that old trial's" |` (l.546):
```markdown
| "`lab run` refused a repeated book, ask the owner" | Never. Change the arm, or declare it truthfully, re-commit (the new pre-registration) and re-run (step 6). Nothing was spent. |
| "Label the treatment a control so the repeat check passes" | Never. The rationale is the pre-registration. A treatment that is another method's book has measured nothing new. |
```
**File:** `.claude/skills/explore-and-experiment-new-method/SKILL.md:565`. Replace the quick-reference line `lab idea --name "..." --family ... --source-kind variation --parent M0007 --hypothesis "..."` with:
```
lab idea --name "..." --family ... --source-kind variation --parent M0007 --hypothesis "..."   # id on stdout; 5 closest methods on stderr
```
and replace `lab run M0007                     # needs a committed method file` with:
```
lab run M0007                     # needs a committed method file; exit 2 if an undeclared arm repeats another method's book
```

### Step 12: feature map
**File:** `.claude/skills/verify-seer/features/lab-cli.md:5-7`. Replace the three sub-feature bullets with:
```markdown
- Read: `lab status` (near-miss and closest-to-eligible rows end in `[role; = first-recorded twin]` tags), `lab show MNNNN`, `lab next-id`, `lab luck`, `lab twins MNNNN|CANDIDATE ...` (which arms are a book the lab already recorded under another id) and the report-only commands (`costs`, `timing`, `kin`, ...).
- Write (to the run's private copy only): `lab idea` (prints the id on stdout and the five closest methods by shared words on stderr), `note`, `insight`, `block`/`unblock`, `drop`, `run` (a committed method on the dev window; prints a `Book twins:` block after the mirror pairs).
- Refused: `lab run` when an arm repeats a book another method recorded first and does not declare it (a control, or a rationale naming that method), or when every arm repeats a recorded book (exit 2, nothing written, no arm metric printed); `lab test`, `promote`, `stage`, `export`, `export-json`, `seed`, and any `--db`.
```
**File:** `.claude/skills/verify-seer/features/lab-cli.md:24-25`. Replace the `idea` drive line's comment `# prints M0490; exit 0` with:
```
                           # stdout: the new id; stderr: "Closest methods already in the lab ..." and up to 5 ids; exit 0
```
**File:** `.claude/skills/verify-seer/features/lab-cli.md`. Append to **Gotchas**:
```markdown
- The repeat refusal cannot be driven through `$V lab RUN run`: that needs a committed method file, and a verify run never commits. Drive `runner.run_method` with a throwaway method built from a recorded method's arms instead, against the run's lab copy (`~/.local/state/seer-verify/RUN/lab.sqlite`) and the main checkout's dev store, with `SEER_ENV_FILE=~/.local/state/seer-verify/RUN/engine.env` and `PYTHONPATH=<checkout>/engine/src`. The phase-1 plan of `lab-run-refuses-repeat-books` carries such a script (`repeat_drive.py`). An SPY-only arm loads the whole dev store and takes minutes.
```

## Principles applied

- Laziness protocol: no new module, no cache, no pre-commit precheck and no new table. The check reuses the simulation `lab run` already does, the `trials.curve_json` bytes `twins.py` already defines as a twin, and `control_shape.role_of` for "is it a control". The idea-level hint is three stdlib helpers inside `commands/lab.py`, not a module.
- Make illegal states unrepresentable: `Repeat.declared` is one string (`""` = undeclared) instead of a flag plus a reason that could contradict each other. `refused()` raises on more repeats than arms rather than returning a wrong all-repeat verdict.
- Fix root causes: the digest guard can never see a wrapper (twins.py docstring). So the refusal reads the outcome (`TrialRow.curve_json` / `trades` taken from `trial_rows`, the exact bytes that would be written) and does not try to normalise configs.
- Prove it works: Proof drives the real `runner.run_method` on the real dev store against a verify-seer lab copy, reproduces the old behaviour on the base commit, and reads the result back with `labsql`.
- Test behavior, not implementation: the run-level tests use a curve the simulator really produced (copied from a first lab), not a mocked `twins` call, and assert on the observable record (trial count, method row, amendment rows, log lines).
- Encode lessons in structure: "a repeat costs nothing, it just annotates" was a docstring claim, and it let 207 cross-method repeats in. It becomes a refusal plus tests, not another sentence in the skills.

## Verification

**Build:** `PYTHONPATH=$PWD/engine/src $PY -m ruff check engine` (or `engine/.venv/bin/ruff check engine`), from the worktree root.
**Tests:**
- `PYTHONPATH=$PWD/engine/src $PY -m pytest engine/tests/test_lab_repeat_refusal.py -n0 -q`
- `PYTHONPATH=$PWD/engine/src $PY -m pytest engine/tests/test_lab_twins.py engine/tests/test_lab_runner.py engine/tests/test_lab_amendments.py engine/tests/test_lab_fold_verdict.py engine/tests/test_lab_remeasure.py -q`
- Full: `PYTHONPATH=$PWD/engine/src $PY -m pytest engine/tests -q` (DB tests need `PG_TEST_URL`; CI fails if they skip). If a `test_lab_*` failure names a frozen record, re-run that file alone before believing it (CLAUDE.md, concurrent `lab run`).

**Proof:**
- Harness: `.claude/skills/verify-seer` (`V=.claude/skills/verify-seer/scripts/verify.sh`), run from the worktree. `lab run` needs a committed method file, so the run-level journeys drive `runner.run_method` through the script below against the run's lab copy and the real dev store. Nothing touches the committed `lab/lab.sqlite`.
- Feature-map entries: `.claude/skills/verify-seer/features/lab-cli.md`
- Setup (stranger-runnable):
  ```sh
  cd /home/miftah/.worktrees/seer/lab-run-refuses-repeat-books
  V=.claude/skills/verify-seer/scripts/verify.sh
  PY=/home/miftah/seer/engine/.venv/bin/python          # or engine/.venv/bin/python if created
  STORE=/home/miftah/seer/engine/.research
  S=<your scratchpad dir>
  $V up --no-web --empty                                 # note RUN=
  D=~/.local/state/seer-verify/$RUN
  ```
  Save this as `$S/repeat_drive.py`:
  ```python
  """Drive runner.run_method on the real dev store with a throwaway method built from M0205's arms.

  --arms is a comma list of:
    treat    M0205-SPY200's book, rationale a plain treatment (an undeclared repeat)
    control  M0205-SPY200's book, rationale opens "Control:" (a declared repeat)
    fresh    SPY's 187-day switch, a book the lab has not recorded
  Exit 0 when the batch was recorded, 2 when the lab refused it, 1 on any other error.
  """
  import argparse
  import dataclasses
  import logging
  import sys
  from pathlib import Path

  from seer_engine import research
  from seer_engine.lab import runner, store
  from seer_engine.lab.method import Method, discover


  def main() -> int:
      p = argparse.ArgumentParser()
      p.add_argument("--db", type=Path, required=True)
      p.add_argument("--store", type=Path, required=True)
      p.add_argument("--id", required=True)
      p.add_argument("--arms", required=True)
      a = p.parse_args()
      logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                          format="%(levelname)s %(name)s: %(message)s")
      host, host_path = discover()["M0205"]
      spy200 = next(c for c in host.candidates if c.id == "M0205-SPY200")

      def arm(suffix, rationale, **params):
          ps = dataclasses.replace(spy200.params, **params) if params else spy200.params
          return dataclasses.replace(spy200, id=f"{a.id}-{suffix}", family=a.id,
                                     rationale=rationale, params=ps)

      menu = {
          "treat": arm("SPY200", "Cash while SPY is under its 200-day average"),
          "control": arm("SPY200", "Control: the lab's SPY 200-day switch on the fresh arm's frame"),
          "fresh": arm("SPY187", "Cash while SPY is under its 187-day average", sma=187),
      }
      method = Method(
          id=a.id, name=f"verify-seer repeat drive {a.id}", family="verify-repeat",
          source_kind="knowledge", source_ref="", hypothesis="harness drive, never real",
          expected_failure="none", candidates=tuple(menu[k] for k in a.arms.split(",")),
      )
      conn = store.connect(a.db)
      try:
          data = research.load_store(a.store)
          done = runner.run_method(conn, method, host_path, data, git_sha="verify",
                                   require_commit=False)
      except store.LabError as e:
          print(f"REFUSED (exit 2):\n{e}")
          return 2
      finally:
          conn.close()
      print("RECORDED:", ", ".join(r.trial.candidate_id for r in done.ran))
      return 0


  if __name__ == "__main__":
      sys.exit(main())
  ```
  Drive it as:
  `SEER_ENV_FILE=$D/engine.env PYTHONPATH=<src> $PY $S/repeat_drive.py --db $D/lab.sqlite --store $STORE --id <ID> --arms <ARMS> > $D/evidence/<name>.txt 2>&1; echo "exit $?" >> $D/evidence/<name>.txt`
  Precondition, read it back before J0: `$V labsql RUN "select n, method_id from trials where window='dev' and curve_json=(select curve_json from trials where candidate_id='M0205-SPY200' and window='dev') order by n limit 1"` gives `690 | M0205`. If it does not, use the `n` and method shown instead of 690/M0205 in the end states below.
- Journeys:
  - **J0: the bug, on the base commit (must FAIL the J1 condition).** `git -C /home/miftah/seer worktree add --detach $S/base 22d1051`. In a **second** run (`$V up --no-web --empty`, call it RUN0, `D0=~/.local/state/seer-verify/$RUN0`), drive with `PYTHONPATH=$S/base/engine/src`, `--db $D0/lab.sqlite --id M9990 --arms treat,fresh`. End state on the base code: `exit 0`, the output contains `RECORDED: M9990-SPY200, M9990-SPY187` and `money-weighted` lines, and `$V labsql $RUN0 "select count(*) from trials where method_id='M9990'"` = 2. This is the repeat being recorded. Then `$V down $RUN0` and `git -C /home/miftah/seer worktree remove $S/base`.
  - **J1: an undeclared cross-method repeat is refused, writes nothing, prints nothing.** In RUN, `PYTHONPATH=$PWD/engine/src`, `--id M9990 --arms treat,fresh`. Passes when the output ends `exit 2` and contains `M9990-SPY200 = M0205-SPY200, first recorded (trial 690, M0205` and `1 of 2 arm(s)`, does **not** contain `money-weighted` (`grep -c money-weighted` = 0), and `$V labsql RUN "select count(*) from trials where method_id='M9990'"` = 0 and `$V labsql RUN "select count(*) from methods where id='M9990'"` = 0.
  - **J2: a declared control repeat records, and Book twins still names it.** Same RUN, `--id M9990 --arms control,fresh`. Passes when `exit 0`, the output contains `RECORDED: M9990-SPY200, M9990-SPY187` and two `money-weighted` lines (after the `simulated` progress lines), `$V labsql RUN "select candidate_id from trials where method_id='M9990' order by n"` lists both, and `$V lab RUN twins M9990` prints `M9990-SPY200 = M0205-SPY200, first recorded (trial 690, M0205` (no role label, because there is no method file) and exit 0. If the output instead shows `M9990-SPY187` refused as a repeat, the 187-day switch was already recorded: change `sma=187` to another unused length, say so in the report, and re-run J1 and J2.
  - **J3: a batch of nothing but repeats is refused even when declared.** Same RUN, `--id M9991 --arms control`. Passes when `exit 2`, the output contains `every one of its 1 arm(s)` and `M9991-SPY200 = M0205-SPY200`, with no `money-weighted` line, and `$V labsql RUN "select count(*) from trials where method_id='M9991'"` = 0.
  - **J4: `lab idea` lists neighbours and never refuses.** `$V lab RUN next-id` (call it NEXT), then `$V lab RUN idea --name "A dead zone on the drawdown brake" --family drawdown-brake --hypothesis "Trim the book in proportion to how far it is below its own high, and ignore small falls" --source-kind knowledge`. Passes when exit 0, the first output line is NEXT, a `Closest methods already in the lab` line follows, and at least one of `M0115`, `M0109` is among the listed ids (measured 2026-11-10: M0550, M0115, M0109, M0097, M0149). `$V labsql RUN "select status from methods where id='<NEXT>'"` = `idea`.
- Neighbor check: `$V lab RUN twins M0488` still prints `M0488-DVC10-NEVER (control) = M0125-DV-C10, first recorded (trial 519, M0125` and exits 0 (twins.py was edited). `$V lab RUN status` exits 0. Then `sha1sum lab/lab.sqlite` matches the value from before `up`, and `git status --porcelain lab web/data` is empty.
- Cost: no paid drives (no `--llm`, no `--net`). J0-J3 each load the dev store and simulate one or two SPY-only arms: minutes each, CPU only. Run them one at a time (memory: concurrent heavy runs crash this laptop).

**Exit criteria:** `test_lab_repeat_refusal.py`, the lab test files above and ruff are green. J0 records on the base commit and J1 refuses on the branch with zero rows written and no metric printed. J2 records a declared repeat and `lab twins` names it. J3 refuses an all-repeat batch. J4 prints the id on stdout and neighbours on stderr.

## Handoffs

- **Owner question, not this phase (R1 scope):** under this rule a *control* that repeats another method's book is still recorded, e.g. M0115-CTRL = M0109-EW-ALL-W (trial 354) in batch sera-20261110-0808, one of the four cases the owner objected to. The phase brief fixes "control = declared" (the protocol runs controls beside treatments, and memory says the roster always keeps a control). Refusing re-run controls in favour of *reusing* the recorded control's curve is listed as out of scope in the plan index ("Reusing a recorded control's curve instead of re-simulating it"). If the owner wants it, it is a separate plan.
- **`lab twins` / `report_lines` wording** still says nothing about the refusal. It reports what was recorded, which stays correct. No change made.
- **`hardgate.py` D15/D19 docstrings** mention that `lab run` only annotates twins. Left alone per the brief ("hardgate.py (D19 stays)"). A docs-only follow-up can align the wording.

## Rollback

Revert the phase's commit(s). The change writes nothing to `lab/lab.sqlite` and has no schema
step, so there is no data rollback. Trials recorded while it was live are ordinary trials and
stay valid.

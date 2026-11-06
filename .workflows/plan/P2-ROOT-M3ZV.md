> Adopted from `.workflows/plan/LAB_BOOK_TWINS_PLAN.md` phase 2. Source: `.workflows/plan/lab-book-twins/phase-2.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 2: calculate-assets names controls and twins

**Plan set:** `LAB_BOOK_TWINS_PLAN.md`
**Analysis:** `.workflows/analyze/20261106-151026-T7WN_code_analyzer.md`
**Satisfies:** R2 — calculate-assets stops presenting a control arm, or a book the lab already recorded, as a new book
**Depends on:** Phase 1 (`seer_engine.lab.twins.first_recorded`)
**Difficulty:** NORMAL
**Package:** `.claude/skills/calculate-assets`

---

## Goal

Before the money, calculate-assets prints one short block saying whether the arm the owner named
is a control arm (from `control_shape.role_of`, pure, rationale-based) and whether the book that
actually ran was first recorded under a different candidate id (from Phase 1's
`twins.first_recorded`, over a read-only SQLite connection). The `--out` JSON gains `role` and
`twin_of`. Every money figure is byte-identical to before, and a missing or unreadable lab DB
degrades to `twin not checked (<reason>)`, never to an error.

## Interface Contract

**Deletes:** none
**Renames:** none
**Creates (all in `.claude/skills/calculate-assets/calculate_assets.py`):**
`TwinCheck` (frozen dataclass), constants `TWIN_FOUND = "twin"`, `TWIN_FIRST = "first"`,
`TWIN_NONE = "none"`, `TWIN_UNCHECKED = "not checked"`, functions `check_twin(candidate_id: str, db_path: Path) -> TwinCheck`,
`identity_lines(method_id: str, recorded: Candidate, check: TwinCheck) -> list[str]`,
`twin_json(check: TwinCheck) -> dict`. `--out` JSON keys `role` (str) and `twin_of` (object, see Step 3).
**Signature changes:** none (`main(argv)` unchanged)
**Requires (from earlier phases):**
- Phase 1: module `seer_engine.lab.twins` with
  `first_recorded(conn: sqlite3.Connection, candidate_id: str, window: str = "dev") -> Twin | None`.
  `Twin` has at least `candidate_id: str`, `method_id: str`, `n: int`, `store_fingerprint: str`,
  the property `earlier: bool`,
  `run_at` (ISO-8601 text as stored in `trials.run_at`, e.g. `2026-10-16T13:45:54+00:00`; this
  phase reads it through `str(...)[:10]`, so a `datetime` works too).
- Phase 1 semantics (fixed by the reconciler): `first_recorded` returns the earliest OTHER trial
  (lowest `n`) with the same window, trades and curve bytes, never the candidate's own trial, or
  `None` when no other trial holds the book. `Twin.earlier` (`twin.n < twin.of_n`) is True when
  that trial was recorded before the one asked about. Step 2 maps the three outcomes exactly:
  `None` -> `TWIN_NONE`; `earlier` -> `TWIN_FOUND` ("Same book as X, first recorded ...");
  not `earlier` -> `TWIN_FIRST` (the asked-about arm is itself the first recording; X is a
  later copy, printed "also recorded later as X"). Never say "first recorded as X" unless
  `twin.earlier`.
- Phase 1's reader issues SELECTs only. On this phase's `mode=ro` connection any write raises,
  and Step 2 turns that into `twin not checked`.
- `seer_engine.lab.control_shape.role_of` and `ROLE_CONTROL` (already on disk, `control_shape.py:415,587`).
**Leaves alone (owned by others):** `engine/**` incl. `lab/twins.py`, `commands/lab.py`,
`hardgate.py` (Phase 1); `.claude/skills/verify-seer/features/lab-cli.md` (Phase 1);
`.claude/skills/sera-the-explorer/SKILL.md`, `.claude/skills/explore-and-experiment-new-method/SKILL.md`
(Phase 3); `build_page.py`, `build_audit.py` (nobody; must keep working unchanged).

## Files

| File | Action | What changes |
|---|---|---|
| `.claude/skills/calculate-assets/calculate_assets.py:10-14, 29-59, 398-399, 470-473, 503-504, 526-529` | modify | docstring point 1; imports; new twin/role helpers; one stdout block before the money; `role`/`twin_of` JSON keys |
| `.claude/skills/calculate-assets/SKILL.md:31, 49-52, 136-137` | modify | "Four rules" -> "Five rules"; rule 4 allows one read-only read and says why; new rule 5; `--out` key list |

## Implementation Steps

### Step 1: Docstring point 1 and imports
**File:** `.claude/skills/calculate-assets/calculate_assets.py:10-14` and `:29-59`
**Change:** Point 1 of the module docstring stops claiming the script never opens the database:
it opens it once, read-only, through plain `sqlite3`, never through `lab.store.connect`. Add
`sqlite3`, `dataclass` and the role import.

Replace lines 10-14 with:
```python
Three things this deliberately does NOT do:

1. **It never connects to the lab database the way ``lab`` commands do.** ``lab.store.connect``
   migrates ``lab.sqlite`` on connect, so even a read through it dirties the file. Methods and
   candidates come from ``lab.method.discover()``, which reads the committed method files on
   disk. The one exception is a single read-only look (``sqlite3`` with ``mode=ro``, which cannot
   write) to ask whether the book that ran was already recorded under another name -- see
   ``check_twin``. A missing or unreadable database only means that line says "not checked".
```

Replace the import block at lines 29-59 with:
```python
import argparse
import json
import sqlite3
import sys
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from pathlib import Path

import numpy as np
from seer_engine import dates, research
from seer_engine.backtest import dev
from seer_engine.backtest.benchmark import spy_curves
from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.registry import REGISTRY
from seer_engine.backtest.market import Market
from seer_engine.backtest.metrics import money_weighted_return
from seer_engine.lab import runner
from seer_engine.lab import store as lab_store
from seer_engine.lab.control_shape import ROLE_CONTROL, role_of
from seer_engine.lab.method import discover
from seer_engine.lab.methods.m0039_vix_term_structure_gate import DAILY_HOLD_FRAC_GOTRADE
from seer_engine.lab.methods.m0063_earnings_day_jump import WEEKLY_HOLD_FRAC_GOTRADE
from seer_engine.lab.methods.m0065_rebalance_day_residual import DAILY_RESIZE_FRAC_GOTRADE
from seer_engine.lab.methods.m0127_slot_relative_resize_band import T00
from seer_engine.sim.contributions import OWNER_MONTHLY
from seer_engine.sim.rules import (
    MONTHLY_HOLD_FRAC_GOTRADE,
    MONTHLY_HOLD_FRAC_GOTRADE_TBAND,
    MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE,
)
from seer_engine.strategies.allocator import prepare_for
from seer_engine.strategies.base import History
```
`seer_engine.lab.twins` is deliberately NOT imported at module top: it is imported inside
`check_twin` so an engine without it (Phase 1 reverted) still answers the money question.
**Impact:** none at runtime; `control_shape` imports only `backtest.metrics`.

### Step 2: The role and twin helpers
**File:** `.claude/skills/calculate-assets/calculate_assets.py`, insert after `monthly()` (after line 398, before the `# ---- the report` banner at line 401)
**Change:** New section. `check_twin` is the only code that opens the database. The DB path is
`lab_store.DB_PATH`, the module constant that already honours `SEER_LAB_DB` (`store.py:107`);
reading the constant opens nothing. The twin is looked up for the candidate that RAN, because the
money printed is that book's money: a `-REAL` lookalike built by `realistic()` has no trial and
says so; a registered twin (e.g. `M0032-N20-RAW-FRAC-GT`) has its own trial and is checked.
The role is taken from the arm the owner NAMED (`recorded`), because "is this a control?" is a
question about what he asked for; the `swap` line already says which arm ran.

**Code:**
```python
# --------------------------------------------------------------------------- what the book is

TWIN_FOUND = "twin"
TWIN_FIRST = "first"
TWIN_NONE = "none"
TWIN_UNCHECKED = "not checked"


@dataclass(frozen=True)
class TwinCheck:
    """Whether the book that ran was first recorded under another candidate id.

    ``status`` is one of ``TWIN_FOUND`` (``twin`` holds phase 1's ``Twin``, recorded EARLIER under
    another id), ``TWIN_FIRST`` (``twin`` holds a LATER copy: this arm is itself the first
    recording), ``TWIN_NONE`` (looked, no other trial holds this book), or ``TWIN_UNCHECKED``
    (``reason`` says why the look did not happen). Built only through ``check_twin``, which sets
    ``twin`` only with ``TWIN_FOUND``/``TWIN_FIRST`` and ``reason`` only with ``TWIN_UNCHECKED``.
    """

    status: str
    reason: str | None = None
    twin: object | None = None


def check_twin(candidate_id: str, db_path: Path) -> TwinCheck:
    """The first-recorded dev-window book with ``candidate_id``'s exact curve, read-only.

    ``mode=ro`` is the point: ``lab.store.connect`` migrates the file on connect, so this never goes
    through it, and a read-only SQLite handle cannot write even if something downstream tried.
    Everything that can go wrong -- no file, no twin reader in this engine, a locked or foreign
    file, a candidate the lab never ran -- comes back as ``TWIN_UNCHECKED`` with a reason. The
    money is the answer the owner asked for; this line is context, so it may never cost him the
    answer.
    """
    if not db_path.is_file():
        return TwinCheck(TWIN_UNCHECKED, reason=f"no lab database at {db_path}")
    try:
        from seer_engine.lab import twins
    except ImportError:
        return TwinCheck(TWIN_UNCHECKED, reason="this engine has no twin reader")
    try:
        conn = sqlite3.connect(f"{db_path.resolve().as_uri()}?mode=ro", uri=True)
    except sqlite3.Error as e:
        return TwinCheck(TWIN_UNCHECKED, reason=f"could not open {db_path} read-only: {e}")
    try:
        ran = conn.execute(
            "SELECT 1 FROM trials WHERE candidate_id = ? AND window = 'dev' LIMIT 1",
            (candidate_id,),
        ).fetchone()
        if ran is None:
            return TwinCheck(
                TWIN_UNCHECKED,
                reason=f"{candidate_id} has no dev-window trial, so no recorded book to compare",
            )
        found = twins.first_recorded(conn, candidate_id, "dev")
    except Exception as e:  # context only: a failed look must never fail the money
        return TwinCheck(TWIN_UNCHECKED, reason=f"the lab database could not be read: {e}")
    finally:
        conn.close()
    # `first_recorded` returns the earliest OTHER trial of this book (phase 1). It came first
    # only when `earlier`; otherwise the arm asked about is itself the first recording.
    if found is None:
        return TwinCheck(TWIN_NONE)
    if found.earlier:
        return TwinCheck(TWIN_FOUND, twin=found)
    return TwinCheck(TWIN_FIRST, twin=found)


def identity_lines(method_id: str, recorded: Candidate, check: TwinCheck) -> list[str]:
    """The plain-language block printed before the money: is it a control, is it a known book.

    A control arm's money is real money, but it is the yardstick the method was registered to be
    beaten against, and relaying it as "a new book" is exactly how one book got reported under
    three names. A twin's money is the first-recorded book's money, so it is named by that book.
    """
    lines: list[str] = []
    if role_of(recorded) == ROLE_CONTROL:
        lines.append(
            f"  {recorded.id} is a control arm of {method_id}: it is the yardstick that method's "
            f"idea was registered\n  to beat, not a new book to trade."
        )
    if check.status == TWIN_FOUND:
        t = check.twin
        lines.append(
            f"  Same book as {t.candidate_id} ({t.method_id}), first recorded "
            f"{str(t.run_at)[:10]}: its money is that\n  book's money, not a new book."
        )
    elif check.status == TWIN_FIRST:
        t = check.twin
        lines.append(
            f"  The first recording of this book; the lab recorded it again later as "
            f"{t.candidate_id} ({t.method_id})."
        )
    elif check.status == TWIN_NONE:
        lines.append("  Not a book the lab recorded earlier under another name.")
    else:
        lines.append(f"  twin not checked ({check.reason})")
    return lines


def twin_json(check: TwinCheck) -> dict:
    """``check`` for the ``--out`` file: one shape per status, keyed by ``status``."""
    if check.status == TWIN_FOUND:
        t = check.twin
        return {
            "status": TWIN_FOUND,
            "candidate": t.candidate_id,
            "method": t.method_id,
            "trial": t.n,
            "first_recorded": str(t.run_at),
            "store_fingerprint": t.store_fingerprint,
        }
    if check.status == TWIN_FIRST:
        t = check.twin
        return {"status": TWIN_FIRST, "later_copy": t.candidate_id, "method": t.method_id,
                "trial": t.n}
    if check.status == TWIN_NONE:
        return {"status": TWIN_NONE}
    return {"status": TWIN_UNCHECKED, "reason": check.reason}
```
**Impact:** new code only; nothing calls it until Step 3.

### Step 3: Print the block before the money; add the JSON keys
**File:** `.claude/skills/calculate-assets/calculate_assets.py:470-473`, `:503-504`, `:526-529`
**Change:** Compute role and twin once, after the `try/except Refused` block (a refused run prints
nothing new). Print the block on stdout immediately before the money header (line 504), followed
by a blank line. Add `role` and `twin_of` to the JSON after `swap`. No money line is touched.

Replace lines 470-473:
```python
    ran_from, ran_to = real_row.start, real_row.end
    n_deposits, total_in = deposits_idr(ran_from, ran_to)
    open_rate = real_res.usd_idr
    end_rate = market.usd_idr_on(ran_to)
```
with:
```python
    ran_from, ran_to = real_row.start, real_row.end
    n_deposits, total_in = deposits_idr(ran_from, ran_to)
    open_rate = real_res.usd_idr
    end_rate = market.usd_idr_on(ran_to)
    role = role_of(recorded)
    twin = check_twin(candidate.id, lab_store.DB_PATH)
```

Replace line 504:
```python
    print(f"  {candidate.id}   {ran_from} to {ran_to}   ({years:.1f} years)")
```
with:
```python
    for line in identity_lines(method_id, recorded, twin):
        print(line)
    print()
    print(f"  {candidate.id}   {ran_from} to {ran_to}   ({years:.1f} years)")
```

Replace lines 526-529:
```python
        args.out.write_text(json.dumps({
            "candidate": candidate.id,
            "method": method_id,
            "swap": swap,
```
with:
```python
        args.out.write_text(json.dumps({
            "candidate": candidate.id,
            "method": method_id,
            "swap": swap,
            "role": role,
            "twin_of": twin_json(twin),
```
**Impact:** stdout gains 2-4 lines before the money header; every later line is unchanged. The
JSON gains two keys; `build_page.py` and `build_audit.py` read only `start`, `series`,
`total_in_idr`, `end_*_idr`, `mwr_*` and other existing keys, so they are unaffected.

### Step 4: SKILL.md — rule 4 and a fifth rule
**File:** `.claude/skills/calculate-assets/SKILL.md:31` and `:49-52`, `:136-137`
**Change:**

Line 31, replace `## Four rules this skill does not bend` with:
```markdown
## Five rules this skill does not bend
```

Replace lines 49-52 (rule 4) with:
```markdown
**4. It never connects to the lab database the way `lab` commands do.** `lab` commands migrate
`lab.sqlite` on connect, so even a read through them dirties the file. Methods come from
`lab.method.discover()`, reading committed method files on disk. The one database read allowed is
a single `sqlite3` connection opened with `mode=ro` (it honours `SEER_LAB_DB`), used only to ask
whether the book that ran was first recorded under another name. A read-only handle cannot write,
so the file stays byte-identical; never replace it with `lab.store.connect`. If the database is
missing or unreadable the output says `twin not checked (<reason>)` and the money is unaffected.
Nothing is recorded: no trial, no observation, no status move. It is a report, in the sense
`lab costs` is a report.

**5. A control is a control, and a recorded book keeps its first name.** Before the money the
output says whether the arm you named is a control arm (the yardstick its method was registered
to beat) and whether its book is the same book as one the lab recorded earlier ("Same book as
M0125-DV-C10, first recorded 2026-10-16"). When you relay the answer, call a control a control,
and name the first-recorded twin instead of presenting the arm as a new book: its money is that
book's money. To see every arm of a method that repeats a recorded book, run
`python -m seer_engine lab twins MNNNN`.
```

Replace lines 136-137 (the `--out` sentence) with:
```markdown
`--out FILE` writes the series as JSON: `book_real`, `book_fixed`, `spy`, `deposited`, monthly
points in rupiah, plus `role` (the named arm's role: `control`, `dose`, `idea` or `treatment`) and
`twin_of` (`{"status": "twin", "candidate", "method", "trial", "first_recorded",
"store_fingerprint"}` when an earlier trial holds this book, `{"status": "first", "later_copy",
"method", "trial"}` when this arm is itself the first recording, `{"status": "none"}` or
`{"status": "not checked", "reason"}`).
`build_page.py` turns that JSON into the artifact page:
```
**Impact:** documentation only. The example ids in rule 5 are the handover's measured pair
(trial 519, run 2026-10-16, read back from `lab/lab.sqlite` this session).

## Principles applied

- Laziness protocol: reuse `lab_store.DB_PATH` (already honours `SEER_LAB_DB`) and `role_of`; no new engine helper, no module split; three small functions in the one script.
- Make illegal states unrepresentable: the twin result is one `TwinCheck` with a `status`, and the JSON `twin_of` is one object keyed by `status`, instead of a nullable `twin_of` beside a separate "checked" flag that could contradict it.
- Boundary discipline: every failure of the DB look (missing file, missing module, ro open, query, reader) is caught once in `check_twin` and becomes a reason; `identity_lines` and `twin_json` trust the typed value.
- Prove it works: Proof runs the real script on the real test store and diffs the money section against the base commit's script, not just "it imports".

## Verification

**Build:** `cd /home/miftah/.worktrees/seer/lab-book-twins && /home/miftah/seer/engine/.venv/bin/ruff check --select E9,F --ignore F401 .claude/skills/calculate-assets/calculate_assets.py`
**Tests:** `cd /home/miftah/.worktrees/seer/lab-book-twins && PYTHONPATH=engine/src PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres /home/miftah/seer/engine/.venv/bin/pytest engine/tests -q -k "twins or control_shape"` (this phase adds no engine code; this confirms Phase 1's reader it imports is green)
**Proof:**
- Harness: `no harness`. `verify-seer` never touches the test window, and calculate-assets reads
  only the test-window store. The real artifact is the script's own stdout and `--out` JSON.
  The worktree has no `engine/.venv` and no `engine/.research-test`: use the main checkout's
  venv and pass `--store /home/miftah/seer/engine/.research-test` (memory: research store is not
  in worktrees).
- Feature-map entries: none. The verify-seer map covers lab CLI, web and engine-night; it has
  no calculate-assets entry and cannot drive the test window.
- Setup (shared by all journeys):
  ```bash
  W=/home/miftah/.worktrees/seer/lab-book-twins
  PY=/home/miftah/seer/engine/.venv/bin/python
  ST=/home/miftah/seer/engine/.research-test
  O=/tmp/claude-1000/phase2-proof; mkdir -p $O
  sha256sum $W/lab/lab.sqlite > $O/db.before
  git -C $W show 3b87070:.claude/skills/calculate-assets/calculate_assets.py > $O/old_calculate_assets.py
  ```
- Journey 1 — money byte-identical (COSK, treatment, no twin):
  ```bash
  cd $W
  PYTHONPATH=$W/engine/src $PY $O/old_calculate_assets.py M0179-N20 1-4-2018 6-10-2026 --store $ST > $O/old.txt 2>/dev/null
  PYTHONPATH=$W/engine/src $PY .claude/skills/calculate-assets/calculate_assets.py M0179-N20 1-4-2018 6-10-2026 --store $ST --out $O/cosk.json > $O/new.txt 2>/dev/null; echo exit=$?
  grep -n "Rp 1,783,094,603" $O/new.txt
  diff $O/old.txt $O/new.txt
  ```
  Passes when: `exit=0`; the grep hits the `your book, at real rupiah rates` line; `diff` shows
  ONLY added (`>`) lines, all before the `M0179-N20   2018-...` header: exactly
  `>   Not a book the lab recorded earlier under another name.` and `> ` (blank), plus the
  `chart data:` line (old run had no `--out`). No `<` line. `jq -r '.role, .twin_of.status' $O/cosk.json`
  prints `treatment` and `none`.
- Journey 2 — control arm and its first-recorded twin (the handover's book):
  ```bash
  cd $W
  PYTHONPATH=$W/engine/src $PY .claude/skills/calculate-assets/calculate_assets.py M0488-DVC10-NEVER 1-4-2018 6-10-2026 --store $ST --out $O/never.json > $O/never.txt 2>/dev/null; echo exit=$?
  head -8 $O/never.txt
  jq -c '{role, twin_of}' $O/never.json
  ```
  Passes when: `exit=0`; stdout contains `M0488-DVC10-NEVER is a control arm of M0488` and
  `Same book as M0125-DV-C10 (M0125), first recorded 2026-10-16`, both before the
  `M0488-DVC10-NEVER   2018-` header; JSON prints
  `{"role":"control","twin_of":{"status":"twin","candidate":"M0125-DV-C10","method":"M0125","trial":519,...}}`.
  (Trial 519 / 2026-10-16 / M0125 read back from `lab/lab.sqlite` this session; it is the
  lowest-`n` other trial of this book, which is phase 1's `first_recorded`, and `earlier` is True.)
- Journey 3 — degrade, never fail (no DB, cheap, no backtest):
  ```bash
  cd $W
  SEER_LAB_DB=/nonexistent/lab.sqlite PYTHONPATH=$W/engine/src:$W/.claude/skills/calculate-assets $PY -c "
  import calculate_assets as ca
  from seer_engine.lab import store
  c = ca.check_twin('M0488-DVC10-NEVER', store.DB_PATH); print(c.status, '|', c.reason)
  c = ca.check_twin('M0007-N20-RAW-REAL', ca.lab_store.COMMITTED_DB); print(c.status, '|', c.reason)
  print(ca.twin_json(c))
  c = ca.check_twin('M0125-DV-C10', ca.lab_store.COMMITTED_DB); print(c.status, '|', c.twin.candidate_id)"
  ```
  Passes when: line 1 is `not checked | no lab database at /nonexistent/lab.sqlite`; line 2 is
  `not checked | M0007-N20-RAW-REAL has no dev-window trial, so no recorded book to compare`;
  line 3 is `{'status': 'not checked', 'reason': '...'}`; line 4 is `first | M0442-DVC10-NEVER`
  (trial 519 is the first recording; its earliest later copy is trial 1536).
- Journey 4 — the DB was never written, and the chart page still builds:
  ```bash
  sha256sum -c $O/db.before
  git -C $W status --porcelain lab/
  python3 $W/.claude/skills/calculate-assets/build_page.py $O/never.json $O/never.html && test -s $O/never.html && echo page-ok
  ```
  Passes when: `lab.sqlite: OK`; `git status` prints nothing for `lab/`; `page-ok`.
- Neighbor check: a swapped arm (rule 1 path) still resolves and reports — Journey 3 line 2
  covers the `-REAL` lookalike's twin line without a 1-minute run; the money path for it is
  unchanged code.
- Cost: no LLM turns. Two full runs (~1 min each) plus the old-script run (~1 min).
**Exit criteria:** On `M0488-DVC10-NEVER` the script prints that it is a control arm of M0488 and
the same book as `M0125-DV-C10`; on `M0179-N20` it prints no twin and `Rp 1,783,094,603` with a
money section byte-identical to the base commit's script; `lab/lab.sqlite`'s sha256 is unchanged.

## Handoffs

- R2 for `lab promote`, `lab status`, `lab run` and the `lab twins` command: Phase 1. Rule 5's
  text names `python -m seer_engine lab twins MNNNN`; reconciler confirmed this matches Phase 1's
  subparser (`sub.add_parser("twins", ...)`, positional `ids nargs="+"`, `--window dev|test`).
- R2 Sera relay rule ("never relay a control's money as a new book"): Phase 3 owns the Sera
  skills; this phase only gives them the line to read.
- `role_of` reads `M0488-DVC10-FIXED730` ("Clock control: M0442's two-year curve watch") as
  `treatment`, not `control`. Left unchanged in this plan set (index Decisions: smallest change;
  D19's cross-method clause refuses that arm anyway); queued as a follow-up card.

## Rollback

`git revert` this phase's single commit (two files under `.claude/skills/calculate-assets/`).
Nothing is written to `lab.sqlite` or the store, so there is no data to undo.

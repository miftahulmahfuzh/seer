> Adopted from `/home/miftah/seer/.workflows/orchestration/lab-shortfall-and-control-shape/PLAN.md` phase 3. Source: `.workflows/plan/lab-shortfall-and-control-shape/phase-3.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 3: `lab note` cannot double-append, and says what it did

**Plan set:** `LAB_SHORTFALL_AND_CONTROL_SHAPE_PLAN.md`
**Analysis:** `docs/analyzer/20261019-110502-S4KQ_code_analyzer.md`
**Satisfies:** R3 — `lab note` must not be able to double-append an identical analysis, and a success must not be silent
**Depends on:** Phase 1 — **file serialisation only**, no semantic dependency (see *Assumptions*)
**Difficulty:** EASY
**Package:** `engine/seer_engine/lab`

---

## Goal

After this phase, a second `lab note M0245 --file F` with the same body cannot land: the analysis
is append-only, so `store.append_analysis` refuses an identical re-append *before* the write and
exits 2 with a message that names the method, says nothing was appended, and says how to confirm.
And `lab note` prints one confirmation line on success, so a piped invocation has output to match
and "no output" stops being indistinguishable from "failed" — which is the root cause that made
the retry look necessary in the first place.

This phase prevents the **next** duplicate. It does not repair the last one: M0245's analysis
already holds the M0245 duplicate, `methods_analysis_grows` permits only growth, and a direct
`UPDATE` to de-duplicate it was correctly refused. That row stays exactly as it is.

## Interface Contract

The reconciler reads this section to detect cross-phase conflicts.

**Deletes:** none.

**Renames:** none.

**Creates:**
- `seer_engine.lab.store._analysis_key` (`engine/src/seer_engine/lab/store.py`, module-private,
  inserted directly above `append_analysis`)

  ```python
  def _analysis_key(text: str) -> str: ...
  ```

**Signature changes:** none. `append_analysis` keeps its exact signature:

```python
def append_analysis(conn: sqlite3.Connection, method_id: str, text: str) -> None
```

**Raising behaviour after this phase** (`store.LabError` in every case; the first two are
unchanged, the third is new):

| When | Message matches |
|---|---|
| the method does not exist | `no method {method_id}` |
| `text.strip()` is empty | `empty analysis` |
| **new** — the normalised headed section equals the newest stored section | `{method_id}: this is already the newest section of the analysis, so nothing was appended and the stored copy is untouched.` … `lab show {method_id}` |

The refusal happens **before** `conn.execute(UPDATE …)`, so nothing is written and the caller's
enclosing `with conn:` rolls back. `append_analysis` still returns `None` on success and still
writes exactly `(old + "\n\n" if old else "") + text + "\n"`.

**Exact lines added to `engine/src/seer_engine/commands/lab.py`** — so phase 4 can quote the file
correctly. `_note` is the **only** function this phase touches in that file. It grows from 11 lines
to 25 (a docstring plus the confirmation line); nothing above or below it moves, no parser is
touched, no `_HANDLERS` entry is touched, and no import is added. After this phase `_note` reads
exactly as given in Step 2 below.

**Requires (from earlier phases):** nothing semantic. Phase 1 must have **landed and been
committed** before this phase edits `commands/lab.py`, because the swarm shares one worktree and
one git index.

**Leaves alone (owned by others):**
- the `shortfall` subparser and its `_HANDLERS` entry — Phase 1
- the `control` subparser, its `_HANDLERS` entry, and `_run`'s annotation block — Phase 4
- `engine/src/seer_engine/lab/hardgate.py` — Phase 4
- `engine/src/seer_engine/lab/shortfall.py` — Phase 1
- `engine/src/seer_engine/lab/control_shape.py` — Phase 2
- `engine/tests/test_lab_shortfall.py`, `test_lab_control_shape.py`, `test_lab_hardgate.py`
- `engine/tests/test_lab_unblock.py` — not in this phase's file set; the unblock regression lives
  in `test_lab_store.py` instead (see Step 3)
- every `lab/methods/mNNNN_*.py`, every recorded `lab.sqlite` row, `backtest/registry.py`, `web/`
- **everything under `.claude/`** — the skill files are dirty in the owner's main checkout with
  work that is not ours, and the plan index puts them out of scope

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/store.py` | modify | new `_analysis_key` helper above `append_analysis` (:964 today); `append_analysis` gains the duplicate refusal and an extended docstring |
| `engine/src/seer_engine/commands/lab.py` | modify | `_note` (:2741 today, **shifts by phase 1's insertion**) gains a docstring and one confirmation line |
| `engine/tests/test_lab_store.py` | modify | three imports, one docstring clause, and seven new tests |

**Line numbers.** `store.py` is untouched by every other phase, so `append_analysis` is at `:964`
and stays there. `commands/lab.py` **is** edited by phase 1 before this phase runs: phase 1 adds a
`shortfall` subparser inside `add_arguments` (today `:170`–`:642`) and one `_HANDLERS` entry
(today `:2886`). Both are outside `_note`, so `_note`'s body is textually unchanged — but its line
number moves down by however many lines phase 1 added. **Re-read the file and anchor the edit on
the exact text below, never on the line number.**

## Implementation Steps

### Step 1: `store.append_analysis` refuses an identical re-append

**File:** `engine/src/seer_engine/lab/store.py:964`
**Change:** Replace the whole of `append_analysis` (today lines 964–984, from
`def append_analysis(` down to and including the closing `)` of the `conn.execute` call) with the
helper below plus the new function. `update_method` ends at `:962`; `record_promotion` begins at
`:987`. Neither moves.

Nothing new is imported: `date`, `sqlite3`, `Any`, `LabError`, `get_method` and `now_iso` are all
already in scope in this module.

**Code:**

```python
def _analysis_key(text: str) -> str:
    r"""Normalise one analysis section so two writings of the same note compare equal.

    Only the *comparison* is normalised; what gets stored is the author's own bytes. Line
    endings are folded to ``\n`` and trailing spaces dropped per line, because a file re-saved
    by a different editor between two tries of the same note is still the same note, and the
    retry this guards against is seconds old rather than a revision. Nothing visible is
    collapsed -- no blank-line squashing, no case folding, no punctuation stripping -- so two
    notes a reader would call different can never normalise to one string, and the refusal
    built on this can never swallow a real addition to the record.
    """
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return "\n".join(line.rstrip() for line in lines).strip()


def append_analysis(conn: sqlite3.Connection, method_id: str, text: str) -> None:
    """Append a dated section to a method's analysis (never rewrites what is there).

    The author's own ``### <today>`` opening line counts as the section head. A note written
    that way used to land under a second, identical heading, and the site then showed the date
    twice; the analysis is append-only, so the duplicate could never be taken back out.

    The same append-only rule has since bitten one layer up, twice. ``lab note`` printed
    nothing at all on success, so a piped invocation handed its exit code to the filter in the
    pipe; the filter matched no lines, failed, and the terminal said the write had failed when
    it had not. The retry appended ten thousand characters of M0245's analysis a second time,
    ``methods_analysis_grows`` permits only growth, and the duplicate is on the site for good.
    So an append whose section is already the newest one on the record is refused **here**,
    before the write -- the only place a duplicate can still be stopped, because afterwards
    there is no statement that removes it. There is no override: a second identical section is
    never the act anyone intended, and a flag to force one would only be reached by the same
    confused retry this refusal exists to catch.

    The comparison is against the **newest section only**, and the section carries its
    ``### <today>`` head, so the refusal reads "this is already what was written today". That is
    the shape of the damage -- a retry minutes later -- and it leaves a deliberate re-note on a
    later day free to land, which is a different act on a different date and belongs on an
    append-only record. Whitespace around the body, trailing spaces on a line and CRLF endings
    do not make it a new note (:func:`_analysis_key`); the bytes that get stored are still the
    author's.
    """
    row = get_method(conn, method_id)
    if row is None:
        raise LabError(f"no method {method_id}")
    text = text.strip()
    if not text:
        raise LabError("empty analysis")
    head = f"### {date.today().isoformat()}"
    if text != head and not text.startswith(head + "\n"):
        text = head + "\n\n" + text
    stored, section = _analysis_key(row["analysis"]), _analysis_key(text)
    if stored and (stored == section or stored.endswith("\n" + section)):
        raise LabError(
            f"{method_id}: this is already the newest section of the analysis, so nothing was "
            f"appended and the stored copy is untouched. The analysis is append-only, so a "
            f"second copy could never be taken back out -- an identical re-append is refused "
            f"rather than written, and there is no override. If the command that wrote this "
            f"looked like it failed, the exit code belonged to something else in the pipeline "
            f"and not to the write: confirm with `python -m seer_engine lab show {method_id}`. "
            f"To add to the record, change the text."
        )
    new = (row["analysis"] + "\n\n" if row["analysis"] else "") + text + "\n"
    conn.execute(
        "UPDATE methods SET analysis = ?, updated = ? WHERE id = ?", (new, now_iso(), method_id)
    )
```

**Why `endswith("\n" + section)` is the right test, and why it is safe.** The stored column is
built by repeated `old + "\n\n" + text + "\n"`, so sections are not separable by splitting on a
blank line — a section's own body contains blank lines. There is no need to split: after
normalisation the stored column *ends with* the newest section, so one `endswith` against a
newline boundary identifies it exactly. Verified against a scratch database before this plan was
written:

```
first append ok
identical:  refused
whitespace: refused        ("\n\n  " + body + "   \n\n")
crlf:       refused        (body with \r\n endings)
unrelated:  appended
stale date re-append: refused
```

A false positive would need the incoming section to be a line-aligned suffix of the stored column.
Because the incoming section always begins with `### <today>`, the match is anchored at a heading,
and a note that merely *ends* with the same words as the previous one does not trip it.

**Decisions this step makes, and why:**

1. **Newest section only, not the whole analysis.** The damage is the retry: same command, same
   file, minutes apart, landing as the newest section. Scanning the whole column would make the
   refusal grow stricter as a method's record grows, and would refuse a deliberate re-note the lab
   has never had a reason to forbid. Comparing the *headed* section gives the scoping for free:
   today's retry collides, the same body tomorrow carries a different `### <date>` and lands as
   what it is — a second, separately dated act on an append-only record.
2. **What counts as identical: the normalisation in `_analysis_key`.** `append_analysis` already
   `strip()`s, so leading and trailing whitespace on the whole body could never have differed; the
   brief's requirement is met by that alone. Line-ending folding and per-line trailing-space
   stripping are added on top because an editor re-save between two tries of the same note is not
   a new note, and neither change can make two visibly-different notes compare equal. Nothing
   beyond that is normalised — no blank-line collapsing, no case folding — because a refusal that
   swallowed a real addition would be worse than the duplicate it prevents.
3. **No escape hatch.** `lab/hardgate.py:21` states the lab's convention outright: *"There is no
   override path, in any form — no flag, no variable in the shell"*, and every refusal in that
   module repeats "There is no override". Nobody has ever wanted a deliberate identical
   re-append, and the only caller who would reach for a `--force` is the confused retry this
   refusal exists to catch. The message carries the escape that is actually wanted instead: change
   the text, or run `lab show` to see that the write already landed.

**Impact:** `store.append_analysis` gains one refusal. The two existing tests in
`test_lab_store.py` that call it (`test_append_analysis_does_not_double_the_authors_own_date_heading`
at `:175`, `test_analysis_grows_and_hypothesis_freezes` at `:189`) append only *different* bodies
and stay green unchanged. Four other callers exist and are analysed in *Assumptions* below; none
can reach the refusal in normal use.

### Step 2: `_note` prints one confirmation line

**File:** `engine/src/seer_engine/commands/lab.py:2741` *(line number shifts by phase 1's
insertion — anchor on the text)*
**Change:** Replace the whole of `_note` (today lines 2741–2750) with the version below. The
function immediately above is `_idea`; the function immediately below is `_block` at today's
`:2752`. Neither moves, and no import is added (`Path` is already imported and already used here).

The text being replaced, exactly as it reads today:

```python
def _note(conn, args) -> int:
    if args.file is None and args.verdict is None:
        raise store.LabError("give --file and/or --verdict")
    with conn:
        if args.file is not None:
            store.append_analysis(conn, args.method, Path(args.file).read_text(encoding="utf-8"))
        if args.verdict is not None:
            store.update_method(conn, args.method, verdict=args.verdict.strip())
    return 0
```

**Code:**

```python
def _note(conn, args) -> int:
    """Append a dated analysis section and/or set the verdict, and say on one line what landed.

    The confirmation is not decoration. Both writes are irreversible -- the analysis is
    append-only and the verdict is the method's standing summary -- and this command used to
    succeed in complete silence. Piped through any filter, silence and failure are the same
    observation and the filter owns the exit code; that is how the same ten-thousand-character
    note came to be appended to M0245 twice. One line of output gives a pipeline something to
    match, and makes ``store.append_analysis``'s refusal visible to anyone who retries anyway.

    The line is printed after the transaction commits, so a refused analysis never reports a
    verdict that rolled back with it.
    """
    if args.file is None and args.verdict is None:
        raise store.LabError("give --file and/or --verdict")
    wrote: list[str] = []
    with conn:
        if args.file is not None:
            body = Path(args.file).read_text(encoding="utf-8")
            store.append_analysis(conn, args.method, body)
            wrote.append(f"analysis appended ({len(body.strip()):,} characters)")
        if args.verdict is not None:
            verdict = args.verdict.strip()
            store.update_method(conn, args.method, verdict=verdict)
            shown = verdict if len(verdict) <= 72 else verdict[:69].rstrip() + "..."
            wrote.append(f'verdict set to "{shown}"')
    print(f"{args.method}: " + "; ".join(wrote) + ".")
    return 0
```

The line reads, in the register `_unblock` already uses (`print(f"{args.method}: blocked-data -> idea")`):

```
M0245: analysis appended (9,912 characters); verdict set to "rejected -- the wrappers killed the signal".
M0245: verdict set to "rejected -- the wrappers killed the signal".
M0245: analysis appended (9,912 characters).
```

The character count is the one number that distinguishes "the note landed" from "an empty file
landed", and it is the figure the owner will recognise from the bug. The verdict is echoed so the
confirmation shows the text that was actually stored (after `strip()`), truncated at 72 characters
so the line stays one line on a terminal.

**Impact:** `lab note` now writes one line to stdout on success. Nothing parses that output today
(`grep -rn "lab note" engine web .workflows` finds only prose), so no caller breaks. The parser at
`add_arguments` (today `:605`) is **not** touched — phase 1 is editing that region of the file.

### Step 3: the tests

**File:** `engine/tests/test_lab_store.py`
**Change:** three things — the module docstring gains one clause, three imports are added, and
seven test functions are added.

**(3a) The module docstring** at `:1`–`:2`. Replace:

```python
"""The lab database's rules (method lab design §1): append-only trials, forward-only status,
growing analysis, one test look per configuration, the seed import and the export."""
```

with:

```python
"""The lab database's rules (method lab design §1): append-only trials, forward-only status,
growing analysis that refuses an identical re-append, one test look per configuration, the seed
import and the export.

The duplicate-note refusal is tested from both ends here: at ``store.append_analysis``, and
through ``lab note`` itself, because the bug it exists to stop was half a store bug and half a
silent command."""
```

**(3b) The imports.** The import block today reads:

```python
from __future__ import annotations

import sqlite3
from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from seer_engine.backtest.registry import REGISTRY
from seer_engine.lab import store
from seer_engine.lab import seed as seed_mod
from seer_engine.lab.method import config_digest
from seer_engine.lab.seed import seed
```

Replace it with:

```python
from __future__ import annotations

import argparse
import logging
import sqlite3
from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from seer_engine.backtest.registry import REGISTRY
from seer_engine.commands import lab as lab_cmd
from seer_engine.lab import store
from seer_engine.lab import seed as seed_mod
from seer_engine.lab.method import config_digest
from seer_engine.lab.seed import seed
```

(`test_lab_unblock.py` imports `seer_engine.commands.lab` at module level already, so this import
is known to be safe under the autouse `_isolated_env` fixture.)

**(3c) Three store-level tests**, inserted after `test_analysis_grows_and_hypothesis_freezes`
(which ends today at `:201`, just before `def test_insight_journal_...`). They reuse the file's
existing `conn` fixture and `_method` helper.

```python
def test_append_analysis_refuses_an_identical_re_append(conn):
    """The M0245 bug: the same body twice, minutes apart, because the terminal said it failed."""
    _method(conn)
    body = "The six arms all beat the placebo.\n\n- FRESH30 +1.5\n- STALE30 +3.9\n"
    with conn:
        store.append_analysis(conn, "M0001", body)
    before = store.get_method(conn, "M0001")["analysis"]
    with pytest.raises(store.LabError, match="already the newest section"):
        with conn:
            store.append_analysis(conn, "M0001", body)
    assert store.get_method(conn, "M0001")["analysis"] == before


def test_append_analysis_catches_a_retry_that_only_differs_in_whitespace(conn):
    """A re-save between two tries is not a new note; the stored bytes stay the author's own."""
    _method(conn)
    body = "A note with trailing spaces   \nand a second line\n"
    with conn:
        store.append_analysis(conn, "M0001", body)
    before = store.get_method(conn, "M0001")["analysis"]
    for retry in (
        "\n\n  " + body + "   \n\n",                          # surrounding whitespace
        body.replace("\n", "\r\n"),                           # CRLF endings
        "A note with trailing spaces\nand a second line",     # per-line trailing spaces gone
    ):
        with pytest.raises(store.LabError, match="nothing was appended"):
            with conn:
                store.append_analysis(conn, "M0001", retry)
    assert store.get_method(conn, "M0001")["analysis"] == before
    assert "trailing spaces   \n" in before  # normalised for the compare, never for the record


def test_append_analysis_still_takes_a_different_body_and_still_heads_it(conn):
    """Newest section only: a body that is no longer the newest one is a new act and lands."""
    today = date.today().isoformat()
    _method(conn)
    with conn:
        store.append_analysis(conn, "M0001", "first")
        store.append_analysis(conn, "M0001", "second")
        store.append_analysis(conn, "M0001", "first")
    text = store.get_method(conn, "M0001")["analysis"]
    assert text.count(f"### {today}") == 3
    assert f"### {today}\n\n### {today}" not in text
    assert text.index("second") < text.rindex("first")
```

**(3d) Four command-level and caller-safety tests**, appended at the **end** of the file (after
`test_seed_records_the_p7a_capital_and_price_fingerprint`, today `:451`), under a section comment
matching the file's style:

```python
# ----------------------------------------------------------- the duplicate note, end to end


def _note_db(tmp_path):
    db = tmp_path / "note.sqlite"
    c = store.connect(db)
    with c:
        store.add_method(
            c, id="M0001", name="placebo shape", family="control",
            source_kind="knowledge", hypothesis="h",
        )
    c.close()
    return db


def _lab(db, command, **kw):
    return lab_cmd.run(argparse.Namespace(db=db, lab_command=command, **kw))


def _read(db, mid="M0001"):
    c = store.connect(db)
    try:
        return dict(store.get_method(c, mid))
    finally:
        c.close()


def test_lab_note_says_what_it_wrote(tmp_path, capsys):
    """One line, naming the method and both halves of what landed. A pipe can match this."""
    db = _note_db(tmp_path)
    note = tmp_path / "note.md"
    note.write_text("The placebo is a control, not a constant.\n", encoding="utf-8")

    assert _lab(db, "note", method="M0001", file=note,
                verdict="  rejected -- the wrapper, not the signal  ") == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) == 1
    assert out[0] == (
        'M0001: analysis appended (41 characters); '
        'verdict set to "rejected -- the wrapper, not the signal".'
    )
    row = _read(db)
    assert "The placebo is a control, not a constant." in row["analysis"]
    assert row["verdict"] == "rejected -- the wrapper, not the signal"


def test_lab_note_with_only_a_verdict_still_prints_one_line(tmp_path, capsys):
    db = _note_db(tmp_path)
    assert _lab(db, "note", method="M0001", file=None,
                verdict="rejected: the control was handicapped") == 0
    assert capsys.readouterr().out.strip() == (
        'M0001: verdict set to "rejected: the control was handicapped".'
    )
    row = _read(db)
    assert row["verdict"] == "rejected: the control was handicapped"
    assert row["analysis"] == ""


def test_lab_note_exits_2_on_the_second_identical_file_and_writes_nothing(tmp_path, capsys, caplog):
    """Exit 2 (the lab's rules refused), the refusal on the log, and the whole row untouched."""
    db = _note_db(tmp_path)
    note = tmp_path / "note.md"
    note.write_text("The placebo is a control, not a constant.\n", encoding="utf-8")
    assert _lab(db, "note", method="M0001", file=note, verdict="first verdict") == 0
    capsys.readouterr()
    before = _read(db)

    with caplog.at_level(logging.ERROR):
        assert _lab(db, "note", method="M0001", file=note, verdict="a different verdict") == 2
    assert "already the newest section" in caplog.text
    assert "lab show M0001" in caplog.text
    assert "no override" in caplog.text
    assert capsys.readouterr().out == ""          # nothing claims success

    after = _read(db)
    assert after["analysis"] == before["analysis"]
    assert after["verdict"] == "first verdict"    # the whole transaction rolled back


def test_the_duplicate_refusal_leaves_the_lab_s_own_generated_notes_alone(tmp_path, capsys):
    """``lab unblock`` and ``record_promotion`` both guard themselves before they ever append."""
    db = _note_db(tmp_path)
    assert _lab(db, "block", method="M0001", on="CBOE VIX3M daily closes") == 0
    assert _lab(db, "unblock", method="M0001", note="Covers 46.8% of the dev window.") == 0
    assert _lab(db, "block", method="M0001", on="EODHD split ex-dates") == 0
    assert _lab(db, "unblock", method="M0001", note="splits.csv arrived; the whole window.") == 0
    row = _read(db)
    assert row["status"] == "idea"
    assert row["analysis"].count("Unblocked: the missing data arrived.") == 2
    capsys.readouterr()

    c = store.connect(db)
    try:
        for _ in range(2):  # the second call returns on PROMOTION_MARKER, never reaching the append
            with c:
                store.record_promotion(
                    c, method_id="M0001", strategy_id="FND", candidate_id="M0001-A",
                    object_name="FUNDAMENTAL", spec_digest="d" * 64, move_status=False,
                    reason="the lab has not passed it; on paper to test it forward",
                )
        assert store.get_method(c, "M0001")["analysis"].count(store.PROMOTION_MARKER) == 1
    finally:
        c.close()
```

**The `41 characters` literal.** `"The placebo is a control, not a constant.\n"` is 42 characters;
`.strip()` drops the trailing newline, leaving 41 — measured, not estimated. Should the fixture
text ever be edited, re-measure rather than guessing: the assertion is what moves, never the
format string.

**Impact:** the suite gains seven tests. No existing test changes behaviour; two existing tests
exercise `append_analysis` and both append distinct bodies.

## Verification

**Build (lint):**
```bash
cd /home/miftah/.worktrees/seer/lab-shortfall-and-control-shape
engine/.venv/bin/ruff check engine
```

**Tests.** **`engine/.venv` ALREADY EXISTS in this worktree and is installed — do NOT create it
and do NOT `pip install` into it.** The plan index's "Working environment" section is binding, and
`python3.11` is not on this machine's PATH (the interpreter is
`/home/miftah/miniconda3/bin/python3.12`). `PYTHONPATH=engine/src` must be set or pytest silently
tests the main checkout instead of this branch:
```bash
cd /home/miftah/.worktrees/seer/lab-shortfall-and-control-shape
# Postgres for the DB tests -- CI fails if they skip:
docker start seer-pg 2>/dev/null || docker run -d --name seer-pg \
  -e POSTGRES_PASSWORD=pg -p 55432:5432 postgres:16
export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres

PYTHONPATH=engine/src engine/.venv/bin/pytest engine/tests/test_lab_store.py \
                                               engine/tests/test_lab_unblock.py -q
PYTHONPATH=engine/src engine/.venv/bin/pytest engine/tests
```
Keep the default `-n auto` from `addopts`; never pass `-o addopts`.

**Manual check** — against a **scratch** database, never `lab/lab.sqlite`:
```bash
cd /home/miftah/.worktrees/seer/lab-shortfall-and-control-shape
md5sum lab/lab.sqlite                      # 2962b4134720c003f85695faa976d693 at plan time
T=$(mktemp -d); printf 'A scratch note.\n' > "$T/note.md"
PYTHONPATH=engine/src engine/.venv/bin/python -m seer_engine lab --db "$T/lab.sqlite" \
  idea --name n --family f --hypothesis h --source-kind knowledge
PYTHONPATH=engine/src engine/.venv/bin/python -m seer_engine lab --db "$T/lab.sqlite" \
  note M0001 --file "$T/note.md" --verdict "a scratch verdict"
# -> M0001: analysis appended (15 characters); verdict set to "a scratch verdict".
PYTHONPATH=engine/src engine/.venv/bin/python -m seer_engine lab --db "$T/lab.sqlite" \
  note M0001 --file "$T/note.md" ; echo "exit $?"
# -> ERROR ... M0001: this is already the newest section ... lab show M0001 ...
# -> exit 2
# and the whole point, the pipeline that started this:
PYTHONPATH=engine/src engine/.venv/bin/python -m seer_engine lab --db "$T/lab.sqlite" \
  note M0001 --verdict v 2>&1 | grep -v "nothing-matches-this"; echo "PIPESTATUS ${PIPESTATUS[@]}"
# -> the confirmation line is matched, so grep exits 0 and the pipeline does not lie
rm -rf "$T"
md5sum lab/lab.sqlite                      # must be unchanged; git checkout -- lab/lab.sqlite if not
git status --porcelain lab/lab.sqlite      # must be empty
```

**Exit criteria:**
- `store.append_analysis` raises `store.LabError` on a byte-identical re-append, on a
  whitespace-only variation of one, and on a CRLF variation of one, and in every case the stored
  `analysis` column is byte-identical afterwards.
- A different body still appends, still gets exactly one `### <today>` head, and the author's own
  `### <today>` opening line is still not doubled.
- `lab note` prints exactly one line on success and exits 0; a duplicate exits 2, prints nothing
  on stdout, logs a refusal naming the method and `lab show <id>`, and leaves the verdict at its
  previous value.
- `lab unblock` and a repeated `record_promotion` are unaffected.
- `ruff check engine` clean; `pytest engine/tests` green with Postgres up and no DB test skipped.
- `git status --porcelain lab/lab.sqlite` is empty.

## Assumptions

- **Phase 1 has landed and is committed.** Its `shortfall` subparser sits inside `add_arguments`
  (today `:170`–`:642`) and its `_HANDLERS` entry near today's `:2886`; both are outside `_note`,
  so `_note`'s text is quoted here exactly as phase 1 leaves it, only at a higher line number.
  Re-read the file before editing. The dependency is file serialisation on one shared git index,
  nothing more: this phase would behave identically if phase 1 had never been written.
- **The other three callers of `append_analysis` cannot reach the new refusal in normal use.**
  All four were read, not assumed:
  - `commands/lab.py:_unblock` (today `:2780`) composes
    `"Unblocked: the missing data arrived. {note}"` plus the blocking reason. Reaching it twice
    requires a `block` in between, and a second cycle on the **same day** with the **same note**
    *and* the **same blocked_on** would now be refused. That is not normal use, and it is the
    correct answer when it happens — the record would be claiming the same arrival twice. The
    failure is safe: the `LabError` is raised inside `_unblock`'s `with conn:`, so the status
    stays `blocked-data` and nothing is half-written. The test in Step 3d pins two cycles with
    different notes working, which is the realistic repeat.
  - `lab/store.py:record_promotion` (the append at `:1077`) returns early when
    `PROMOTION_MARKER + f"`{strategy_id}`"` is already in the analysis, so a re-run never reaches
    the append. Pinned in Step 3d.
  - `lab/store.py` re-evaluation (the append at `:1947`) runs only when `status == "rejected"` and
    something was unblocked, and moves the status to `dev-eligible` on the next line, so a second
    call returns before building its lines at all.
  - `lab/prereg.py:727` is guarded by `if recorded is None`, where `recorded` comes from
    `_recorded_candidate(row["analysis"])` — non-`None` after the first write. A pre-registration
    is written once by construction.
- **The research store is not needed.** This phase loads no store, runs no backtest, reads no
  market data and never passes `window="test"`.
- **Nothing is recorded.** No trial, no status move, no insight, no look, no `web/data/lab.json`,
  no `lab stage`. The refusal changes a rule, not a row.

## Handoffs

- **The skill-file prose warning (`check PIPESTATUS, or don't pipe`).** The handover's §5 names it
  and `.claude/skills/explore-and-experiment-new-method/SKILL.md` already carries it, but those
  skill files are dirty in the owner's main checkout with work that is not ours and the plan index
  puts them out of scope. **No phase of this set edits anything under `.claude/`.** The engine-side
  fix here is strictly better anyway: it makes the failure mode impossible rather than warning
  about it. Left to the owner.
- **The M0245 duplicate already on the record.** `methods.analysis` is append-only and a direct
  `UPDATE` to de-duplicate was correctly refused. This phase prevents the next one; it does not
  repair the last one, and no phase of this set should try. Left as it is, permanently.
- **Every other silent `lab` subcommand.** `_block`, `_drop` and `_insight`'s sibling paths are
  equally silent, and the same pipeline trap applies to them. Out of scope: this phase owns `_note`
  only, and `_block`/`_drop` write a reversible column rather than an append-only one. Worth a
  follow-up card; not R3.
- **Trial 828's decomposition, the control-shape table, insight 461, the memory note and the
  `/sera` page** — R1 (phase 1), R2 (phases 2 and 4), and the owner-visible corrections the plan
  index puts out of scope entirely.

## Rollback

`git revert` this phase's single commit. The phase is additive and self-contained: one new
module-private helper, one new refusal inside an existing function, one `print`, and seven tests.
Reverting restores the previous behaviour exactly — including, deliberately, the ability to
double-append. No row, no method file, no frozen record and no `lab.sqlite` byte is touched, so
there is nothing to undo in the database.

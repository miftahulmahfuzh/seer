# Phase 2: Writer CLI: `lab insight --supersedes`, `lab link`

**Plan set:** `JOURNAL_VERSIONING_PLAN.md`
**Analysis:** `docs/analyzer/20261020-162050-J7K2_code_analyzer.md`
**Satisfies:** R3 — thread the duplicates that already exist. This phase builds the tool; phase 6
pulls the trigger with it.
**Depends on:** Phase 1
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine/commands`

---

## Goal

After this phase the lab has two ways to say *"this entry replaces that one"* from the shell:
`lab insight --supersedes ID` writes the link on a **new** entry at birth, and a new
`lab link ID --supersedes OLDER` writes it on an entry **already in the journal** — the one
UPDATE phase 1's narrowed trigger permits, and the only tool phase 6 will have. Both refuse
through the store and surface a refusal as exit **2**, never 1, so the backfill can tell
*"the journal forbids this"* from *"the tool is broken"*.

Nothing in this phase reads, writes or migrates data. It adds one subcommand, two flags, and
the tests that pin the exit-code contract across the phase-1 boundary.

## Interface Contract

**Deletes:** nothing.

**Renames:** nothing.

**Creates:**
- `lab link` subcommand — parser in `commands/lab.py::add_arguments`, handler
  `commands/lab.py::_link`, dispatch entry `_HANDLERS["link"]`
- `lab insight --supersedes ID` flag (`args.supersedes`, `int | None`)
- `lab insight --doc-key KEY` flag (`args.doc_key`, `str | None`)
- `engine/tests/test_lab_link.py` (new test module)

**Signature changes:**
- `commands/lab._insight(conn, args)` — unchanged signature; now reads `args.supersedes` and
  `args.doc_key` off the namespace. **Any test or caller that builds an
  `argparse.Namespace(lab_command="insight", ...)` by hand must add both keys** — there are
  none in the tree today (grepped: `lab_command="insight"` appears nowhere in `engine/tests`),
  but a peer phase that adds one must include them.

**Requires (from earlier phases) — Phase 1, and these are load-bearing:**
1. `store.add_insight(conn, *, kind, title, body, method_id=None, doc_key=None, supersedes=None) -> int`
   — accepts both new keyword arguments and **validates `supersedes` on the insert path** with
   the same invariants as `set_supersedes`, raising `store.LabError`.
2. `store.set_supersedes(conn, insight_id, supersedes) -> None` — performs the single permitted
   UPDATE, and raises **`store.LabError`** (never a bare `sqlite3.IntegrityError`, never
   `ValueError`) for every refusal: no such entry, no such predecessor, predecessor under a
   different `method_id`, `supersedes >= insight_id`, self-reference, predecessor already
   superseded, entry already linked.
   **The `insights_one_successor` index is the backstop, not the contract.** If the
   already-superseded case reaches the CLI as `sqlite3.IntegrityError`, `run()` does not catch
   it and the process exits **1** — which is exactly the failure the exit-code contract exists
   to prevent. `test_link_refuses_a_predecessor_that_already_has_a_successor` below is the
   cross-phase check for this; if it reports 1, the fix belongs in phase 1's `set_supersedes`,
   not here.
3. Neither store function commits; the caller wraps the call in `with conn:` as every other lab
   handler does.
4. `store.SCHEMA_VERSION == "8"`; `insights` carries `supersedes INTEGER REFERENCES insights(id)`
   and `doc_key TEXT`.

*Phase 1's plan file did not exist when this was written* (`.workflows/plan/journal-versioning/`
held only `.` and `..` at 16:24 on 2026-10-20). The four requirements above are the signatures
named in the phase-2 brief and in `JOURNAL_VERSIONING_PLAN.md` §Phase 1. See **Contingency**
under Step 2 for the one-line change if (1) does not land as specified.

**Leaves alone (owned by others):**
- `engine/src/seer_engine/lab/store.py` — Phase 1. No validation is restated in the command
  layer and no second code path writes `supersedes`.
- `lab/real_costs.py`, `survivorship_check.py`, `gate_probe.py`, `exposure.py`, `prereg.py` —
  Phase 3. They call `store.add_insight` directly; they do not go through this CLI, and the
  `--no-supersede` escape on each of those subcommands is phase 3's.
- `store.snapshot`, `store.summary_rows`, `web/lib/sera/types.ts` — Phase 4.
- `web/app/sera/journal/*` — Phase 5.
- `lab/lab.sqlite` and `web/data/lab.json` — Phase 6. **This phase runs no backfill, no
  `lab stage`, and no `lab link` against the real database.**
- `engine/src/seer_engine/lab/hardgate.py` — a concurrent session.
- `commands/lab.py:843`, the `"Latest insights:"` loop in `_status` — see **Handoffs**. It is in
  this phase's file but counts rows, which is phase 4's axis.

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/commands/lab.py` | modify | usage line at `:130`; `insight` subparser at `:761-766` gains two flags; new `link` subparser after it; `_insight` at `:3156` passes the two new arguments through; new `_link` handler after `:3164`; `_HANDLERS` at `:3244` gains `"link"` |
| `engine/tests/test_lab_link.py` | create | both commands, every refusal as exit 2, every refusal proven inert |

## Implementation Steps

### Step 1: The usage line

**File:** `engine/src/seer_engine/commands/lab.py:130`

**Change:** the module docstring is the command's own map; it lists every subcommand and is what
a reader sees before `--help`. `lab link` must appear there or it does not exist as far as the
next session is concerned. The block's description column starts at index 36 (`lab stage` at
`:131` sets it) — hold that alignment.

This is the module docstring, not an argparse `help=` string, so `%` needs no doubling here.
There is no `%` in the new text either way.

Replace the single line:

```
    lab insight --kind K --title T (--body B | --file F) [--method M]   the lab journal
```

with:

```
    lab insight --kind K --title T (--body B | --file F) [--method M] [--doc-key K]
                [--supersedes ID]   the lab journal. --supersedes says this new entry is the
                                    newer version of entry ID; ID keeps every word it has
    lab link ID --supersedes OLDER  thread an entry already written onto the one it replaces:
                                    the only change the append-only journal allows, and only
                                    once, from nothing to a link
```

**Impact:** documentation only. The docstring is not passed to argparse (`cli.build_parser` uses
`module.HELP`, `cli.py:72`), so nothing re-formats.

### Step 2: The `insight` flags and the `link` subparser

**File:** `engine/src/seer_engine/commands/lab.py:761-766`

**Change:** the existing six-line `insight` block is replaced by the block below, which keeps all
five existing arguments byte-identical and appends two, then adds the `link` parser immediately
after — before the `stage` parser at `:768`, so the journal's three commands sit together.

Two conventions hold here. First, **no literal `%` in any `help=` string**: argparse runs every
one through `%`-interpolation in `HelpFormatter._expand_help`, and a bare `%` kills `lab --help`
(the comments at `:326`, `:472` and `:600` are three separate scars from this). None of the new
strings contain one; if a later edit needs a percentage, double it to `%%`. `description=` is
**not** interpolated and stays single. Second, the repo lets argparse derive `args.doc_key` from
`--doc-key` rather than passing `dest=` (as `--min-train-years` does at `:465`).

**Code:**

```python
    s = sub.add_parser("insight", help="append to the lab journal (food for thought)")
    s.add_argument("--kind", required=True, choices=store.INSIGHT_KINDS)
    s.add_argument("--title", required=True)
    s.add_argument("--body", default=None)
    s.add_argument("--file", type=Path, default=None)
    s.add_argument("--method", default=None)
    s.add_argument(
        "--doc-key", default=None, metavar="KEY",
        help="stable identity of the document this entry is a version of, e.g. "
             "real-costs:M0260-M-G3. Two entries sharing one key are versions of one thing; "
             "two entries with different keys are two things, whatever their titles say",
    )
    s.add_argument(
        "--supersedes", type=int, default=None, metavar="ID",
        help="this new entry is the newer version of journal entry ID. ID is not rewritten, "
             "not hidden and not deleted: it keeps its place and gains a successor",
    )

    s = sub.add_parser(
        "link",
        help="thread a journal entry already written onto the one it replaces",
        description=(
            "Set the supersedes link on an insight that is already in the journal. This is the "
            "one UPDATE the append-only triggers permit, and only from nothing to a link, once: "
            "no word of either entry changes, and the link can never afterwards be moved or "
            "removed. It exists for entries written before the journal had versions, where the "
            "fact that one note replaces another is recorded only in the prose inside it."
        ),
    )
    s.add_argument("insight", type=int, metavar="ID",
                   help="the newer entry: the one being threaded onto its predecessor")
    s.add_argument(
        "--supersedes", type=int, required=True, metavar="OLDER",
        help="the older entry that ID replaces. It must be the same method and a lower id, "
             "and it must not already have a successor",
    )
```

**Impact:** `lab insight` gains two optional flags and keeps every existing invocation working
unchanged. `lab link` becomes reachable from the shell and from `lab --help`.
`engine/tests/test_cli.py::test_every_parser_formats_its_help` (the walk at `test_cli.py:147-159`)
now covers both new parsers automatically — that is the `%`-interpolation guard, and it is why
this phase adds no help-formatting test of its own.

### Step 3: `_insight` carries the two new arguments

**File:** `engine/src/seer_engine/commands/lab.py:3156-3164`

**Change:** pass `doc_key` and `supersedes` through to `store.add_insight`. The handler gains a
docstring, because every refusal a reader might expect to find here is deliberately somewhere
else and the file's convention is to say why.

**Code — the complete replacement function:**

```python
def _insight(conn, args) -> int:
    """Append one entry to the lab journal, optionally as the newer version of an entry already
    in it.

    ``--supersedes`` writes the link on the NEW row at birth rather than inserting and then
    calling ``lab link``: a row that is never unlinked for an instant cannot be read mid-write
    by a parallel session, and the whole insert is one transaction, so a refused link leaves no
    orphan entry behind.

    Every rule about what may supersede what -- the predecessor must exist, belong to the same
    method, carry a lower id and have no successor yet -- lives in the store. Restating any of
    them here would give the lab two places to disagree about its own rules, and the five
    auto-journalling writers do not come through this function at all."""
    if (args.body is None) == (args.file is None):
        raise store.LabError("give exactly one of --body or --file")
    body = args.body if args.body is not None else Path(args.file).read_text(encoding="utf-8")
    with conn:
        n = store.add_insight(
            conn,
            kind=args.kind,
            title=args.title,
            body=body,
            method_id=args.method,
            doc_key=args.doc_key,
            supersedes=args.supersedes,
        )
    print(n)
    return 0
```

**Impact:** `lab insight` with neither new flag behaves exactly as before — both default to
`None`, which is what `add_insight` already stores for an unlinked row. The `with conn:` block
is the existing one; if `add_insight` raises `LabError` after the INSERT, the context manager
rolls the transaction back and no partial entry survives. `run()` at `:778-786` turns the
`LabError` into **2**.

**Contingency (read this if phase 1 landed differently).** If `store.add_insight` ships without
validating its `supersedes` argument — i.e. it stores the value but all the checks live only in
`set_supersedes` — do **not** add checks here. Change the body of the `with conn:` block to:

```python
    with conn:
        n = store.add_insight(
            conn,
            kind=args.kind,
            title=args.title,
            body=body,
            method_id=args.method,
            doc_key=args.doc_key,
        )
        if args.supersedes is not None:
            store.set_supersedes(conn, n, args.supersedes)
```

That is still one transaction and still one validation path; it costs one extra UPDATE, which
the narrowed trigger permits (NULL to value, once). The tests in Step 5 pass unchanged under
either shape, which is deliberate: they assert the exit code and the stored row, never which
store function produced it.

### Step 4: the `_link` handler and its dispatch entry

**File:** `engine/src/seer_engine/commands/lab.py` — new function immediately after `_insight`
(after the current `:3164`), before `_stage` at `:3166`.

**Code:**

```python
def _link(conn, args) -> int:
    """Thread an entry already in the journal onto the one it replaces.

    ``lab insight --supersedes`` covers everything written from here on. This covers what was
    written before the journal had versions, where the only record that one note replaces
    another is a sentence inside it -- insight 126 says so in prose, because the schema had
    nowhere to put it.

    It is a subcommand of its own rather than a flag on ``lab note`` on purpose: this is the
    single UPDATE the append-only triggers allow, and it deserves a name in the shell history,
    so an audit of what moved in this database can find it by reading the commands that ran.

    Every refusal -- no such entry, no such predecessor, a predecessor under a different method,
    an entry that is already linked, a predecessor that already has a successor, a link pointing
    forward or at itself -- is the store's, raised as ``LabError`` and turned into exit 2 by
    ``run``. Nothing is re-checked here."""
    with conn:
        store.set_supersedes(conn, args.insight, args.supersedes)
    print(f"{args.insight} supersedes {args.supersedes}")
    return 0
```

**File:** `engine/src/seer_engine/commands/lab.py:3244`

**Change:** add the dispatch entry directly under `"insight"`.

**Code — the two lines, in place:**

```python
    "insight": _insight,
    "link": _link,
```

**Impact:** success prints one short line and nothing else — phase 6 runs this five times and
wants a quiet log it can read at a glance. A refusal prints the store's own message through
`log.error` in `run()` and exits 2.

### Step 5: the tests

**File:** `engine/tests/test_lab_link.py` (new)

**Change:** cover the happy path of both commands and **every** invariant as an exit-2 path,
each one re-reading the row afterwards to prove the refusal changed nothing. The module follows
`engine/tests/test_lab_unblock.py`'s shape — a tiny `_lab` fixture, a `_run` that calls
`lab_cmd.run` with a hand-built namespace, and assertions on the return code.

**Code — the complete file:**

```python
"""``lab insight --supersedes`` and ``lab link``: the journal's two ways to say "this replaces
that".

Both write one column through the store, so what these tests really pin is the **exit code**.
The lab's contract is 0 ok, 2 the lab's rules refused, 1 something broke. Phase 6's backfill
reads that contract to tell "I asked the journal for something it forbids" from "the tool is
broken", and a refusal that leaked out as 1 -- a bare ``sqlite3.IntegrityError`` from the
one-successor index, say -- would look like the second. So every refusal below asserts **2**,
and then re-reads the row to prove nothing moved.

The happy paths assert the stored value, never which store function stored it: ``lab insight
--supersedes`` may link on the insert or immediately after it, and both are correct."""

from __future__ import annotations

import argparse

from seer_engine.commands import lab as lab_cmd
from seer_engine.lab import store


def _lab(tmp_path):
    """Two methods, so the "a link may not cross methods" case has somewhere to cross to."""
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    with c:
        store.add_method(
            c, id="M0001", name="VIX gate", family="regime", source_kind="knowledge",
            hypothesis="h",
        )
        store.add_method(
            c, id="M0002", name="Dividend hold", family="income", source_kind="knowledge",
            hypothesis="h",
        )
    c.close()
    return db


def _run(db, command, **kw):
    return lab_cmd.run(argparse.Namespace(db=db, lab_command=command, **kw))


def _insight(db, *, title, body, method=None, doc_key=None, supersedes=None, kind="observation"):
    return _run(
        db, "insight", kind=kind, title=title, body=body, file=None, method=method,
        doc_key=doc_key, supersedes=supersedes,
    )


def _rows(db):
    c = store.connect(db)
    try:
        return {int(r["id"]): dict(r) for r in c.execute("SELECT * FROM insights ORDER BY id")}
    finally:
        c.close()


def _two(db, method="M0001"):
    """Two unlinked entries under one method: 1 the older, 2 the newer."""
    assert _insight(db, title="what the fees did", body="first reading", method=method) == 0
    assert _insight(db, title="what the fees did", body="second reading", method=method) == 0
    ids = sorted(_rows(db))
    assert len(ids) == 2
    return ids


# ---- lab insight --------------------------------------------------------------------------

def test_insight_without_the_new_flags_is_unchanged(tmp_path):
    db = _lab(tmp_path)
    assert _insight(db, title="a thought", body="a body", method="M0001") == 0
    row = _rows(db)[1]
    assert row["title"] == "a thought"
    assert row["body"] == "a body"
    assert row["supersedes"] is None
    assert row["doc_key"] is None


def test_insight_stores_a_doc_key(tmp_path):
    db = _lab(tmp_path)
    assert _insight(db, title="t", body="b", method="M0001", doc_key="real-costs:M0001-N20") == 0
    assert _rows(db)[1]["doc_key"] == "real-costs:M0001-N20"


def test_insight_supersedes_links_the_new_entry_and_leaves_the_old_one_whole(tmp_path):
    db = _lab(tmp_path)
    assert _insight(db, title="what the fees did", body="first reading", method="M0001") == 0
    before = _rows(db)[1]

    assert _insight(db, title="what the fees did", body="a better reading", method="M0001",
                    supersedes=1) == 0

    rows = _rows(db)
    assert rows[2]["supersedes"] == 1
    assert rows[1] == before, "the superseded entry must not change in any column"


def test_insight_supersedes_a_missing_entry_is_refused_and_writes_nothing(tmp_path):
    db = _lab(tmp_path)
    assert _insight(db, title="t", body="b", method="M0001", supersedes=99) == 2
    assert _rows(db) == {}, "a refused link must not leave the new entry behind"


def test_insight_still_demands_exactly_one_of_body_and_file(tmp_path):
    db = _lab(tmp_path)
    assert _run(db, "insight", kind="observation", title="t", body=None, file=None,
                method=None, doc_key=None, supersedes=None) == 2
    assert _run(db, "insight", kind="observation", title="t", body="b",
                file=tmp_path / "b.txt", method=None, doc_key=None, supersedes=None) == 2
    assert _rows(db) == {}


# ---- lab link -----------------------------------------------------------------------------

def test_link_threads_an_entry_already_written(tmp_path):
    db = _lab(tmp_path)
    older, newer = _two(db)
    before = _rows(db)[older]

    assert _run(db, "link", insight=newer, supersedes=older) == 0

    rows = _rows(db)
    assert rows[newer]["supersedes"] == older
    assert rows[older] == before


def test_link_builds_a_chain_of_three(tmp_path):
    """320 -> 499 -> 500, the shape phase 6 backfills, in id order."""
    db = _lab(tmp_path)
    for body in ("first", "second", "third"):
        assert _insight(db, title="the same note", body=body, method="M0001") == 0

    assert _run(db, "link", insight=2, supersedes=1) == 0
    assert _run(db, "link", insight=3, supersedes=2) == 0

    rows = _rows(db)
    assert [rows[i]["supersedes"] for i in (1, 2, 3)] == [None, 1, 2]


def test_link_refuses_a_missing_entry(tmp_path):
    db = _lab(tmp_path)
    older, _newer = _two(db)
    assert _run(db, "link", insight=99, supersedes=older) == 2
    assert all(r["supersedes"] is None for r in _rows(db).values())


def test_link_refuses_a_missing_predecessor(tmp_path):
    db = _lab(tmp_path)
    _older, newer = _two(db)
    assert _run(db, "link", insight=newer, supersedes=99) == 2
    assert _rows(db)[newer]["supersedes"] is None


def test_link_refuses_a_predecessor_at_or_above_the_entry(tmp_path):
    """A journal reads forward. A link that points forward would make the chain a cycle or a
    fork in time, and the version number unresolvable."""
    db = _lab(tmp_path)
    older, newer = _two(db)
    assert _run(db, "link", insight=older, supersedes=newer) == 2
    assert all(r["supersedes"] is None for r in _rows(db).values())


def test_link_refuses_an_entry_superseding_itself(tmp_path):
    db = _lab(tmp_path)
    _older, newer = _two(db)
    assert _run(db, "link", insight=newer, supersedes=newer) == 2
    assert _rows(db)[newer]["supersedes"] is None


def test_link_refuses_a_predecessor_that_already_has_a_successor(tmp_path):
    """One predecessor, one successor: a fork has no version number.

    This is the cross-phase check. If it returns 1 rather than 2, the refusal escaped as a bare
    ``sqlite3.IntegrityError`` from ``insights_one_successor`` instead of as a ``LabError`` from
    ``store.set_supersedes``, and the fix belongs in phase 1's store, not in the CLI."""
    db = _lab(tmp_path)
    assert _insight(db, title="t", body="first", method="M0001") == 0
    assert _insight(db, title="t", body="second", method="M0001") == 0
    assert _insight(db, title="t", body="third", method="M0001") == 0
    assert _run(db, "link", insight=2, supersedes=1) == 0

    assert _run(db, "link", insight=3, supersedes=1) == 2

    rows = _rows(db)
    assert rows[2]["supersedes"] == 1
    assert rows[3]["supersedes"] is None


def test_link_refuses_an_entry_that_is_already_linked(tmp_path):
    """Once set, the link is frozen -- it cannot be moved to a different predecessor."""
    db = _lab(tmp_path)
    assert _insight(db, title="t", body="first", method="M0001") == 0
    assert _insight(db, title="t", body="second", method="M0001") == 0
    assert _insight(db, title="t", body="third", method="M0001") == 0
    assert _run(db, "link", insight=3, supersedes=2) == 0

    assert _run(db, "link", insight=3, supersedes=1) == 2

    assert _rows(db)[3]["supersedes"] == 2


def test_link_refuses_crossing_methods(tmp_path):
    """A version of a note about M0001 cannot be a note about M0002."""
    db = _lab(tmp_path)
    assert _insight(db, title="t", body="first", method="M0001") == 0
    assert _insight(db, title="t", body="second", method="M0002") == 0

    assert _run(db, "link", insight=2, supersedes=1) == 2

    assert _rows(db)[2]["supersedes"] is None


def test_link_is_registered_in_the_dispatch_table(tmp_path):
    """The parser and the handler table are edited separately; a subcommand that parses and then
    dies on a KeyError exits 1, which phase 6 would read as a broken tool."""
    assert "link" in lab_cmd._HANDLERS
```

**Impact:** 15 tests, no research store, no network, no fixtures beyond a `tmp_path` database.
They run in the parallel suite without special handling.

## Verification

Run from the worktree. `PYTHONPATH` is not optional here: without it pytest silently imports the
installed `seer_engine` from the main checkout and tests the wrong branch.

**Build / lint:**
```bash
PYTHONPATH=/home/miftah/.worktrees/seer/journal-versioning/engine/src \
  /home/miftah/seer/engine/.venv/bin/ruff check engine
```

**Tests:**
```bash
cd /home/miftah/.worktrees/seer/journal-versioning
PYTHONPATH=/home/miftah/.worktrees/seer/journal-versioning/engine/src \
  /home/miftah/seer/engine/.venv/bin/python -m pytest \
  engine/tests/test_lab_link.py engine/tests/test_cli.py -q

# then the whole suite
PYTHONPATH=/home/miftah/.worktrees/seer/journal-versioning/engine/src \
  /home/miftah/seer/engine/.venv/bin/python -m pytest engine/tests -q
```

`test_cli.py::test_every_parser_formats_its_help` is the `%`-interpolation guard and must be in
the first run: it is the only thing that renders the new `help=` strings.

**Manual check** — against a throwaway database, never `lab/lab.sqlite`:
```bash
cd /home/miftah/.worktrees/seer/journal-versioning
PYTHONPATH=engine/src /home/miftah/seer/engine/.venv/bin/python -m seer_engine lab --help | head -60
PYTHONPATH=engine/src /home/miftah/seer/engine/.venv/bin/python -m seer_engine lab link --help
```
Look for: `link` in the subcommand list; `--supersedes` and `--doc-key` on `lab insight --help`;
the new lines in the module docstring aligned at column 36.

**Exit criteria:**
- `lab link --help` prints, and `lab link ID --supersedes OLDER` sets the link on an existing
  entry under a throwaway database, printing one line.
- Every invariant phase 1 enforces returns **2** from the CLI, and the row is provably unchanged
  after each refusal.
- `lab insight` with no new flags behaves byte-for-byte as it did before.
- `ruff check engine` clean and `pytest engine/tests` green.
- `lab/lab.sqlite` and `web/data/lab.json` are **untouched** by this phase
  (`git status --short lab/ web/data/` is empty); the test-window look count still reads 4.

## Handoffs

- **`_status`'s journal block, `commands/lab.py:843-845`.** The `"Latest insights:"` loop prints
  the newest eight **rows**. Once chains exist it will show a superseded entry beside its own
  replacement, as two separate lines, with nothing saying so. That is the same row-vs-document
  bug phase 4 fixes in `store.summary_rows` and `snapshot["summary"]["insights"]`, and it should
  be fixed on the same axis and in the same phase. It is **in this phase's file**, which is why
  it is flagged rather than silently left: the reconciler should assign `commands/lab.py:843` to
  **phase 4** explicitly, or the terminal status block will contradict `/sera/journal`.
- **`--no-supersede` escapes on the five auto-journalling subcommands** (`lab real-costs`,
  `lab survivorship`, `lab gate`, `lab exposure`, the prereg path) — **phase 3**. Those parsers
  are in this file too, but the flag only means something once the writers auto-link, so it
  lands with them.
- **Running the backfill** — **phase 6**, over 227→230, 289→290, 493→498, 320→499, 499→500,
  then `lab stage` and one commit carrying `lab.sqlite` and `web/data/lab.json` together. This
  phase deliberately does not run it: moving `lab.sqlite` here would move it out from under
  phase 6 and strand its commit.
- **`doc_key` for hand-written entries.** `lab insight --doc-key` exists but nothing teaches a
  human which key to use; the generated keys are phase 3's (`real-costs:<candidate_id>`,
  `prereg:<method_id>`). If a convention for hand-written keys is wanted, it belongs beside
  phase 3's key shapes, not here.

## Rollback

One commit on `feature/journal-versioning`; `git revert` it. Nothing to undo beyond the code:
this phase writes no row, moves no database, and regenerates no snapshot. After the revert
`lab link` is gone and `lab insight` loses two optional flags whose absence changes no existing
invocation.

The only ordering note: if phase 6 has already run, revert phase 6's data commit **first** —
not because the revert needs the command, but because `lab link` is the only tool that writes
that column, and a reviewer reading the history backwards should see the tool outlive its use.

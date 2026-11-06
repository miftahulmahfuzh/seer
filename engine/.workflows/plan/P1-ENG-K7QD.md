> Adopted from `.workflows/plan/LAB_BOOK_TWINS_PLAN.md` phase 1. Source: `.workflows/plan/lab-book-twins/phase-1.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 1: Twin reader and lab CLI surfaces (run, twins, status, promote D19)

**Plan set:** `LAB_BOOK_TWINS_PLAN.md`
**Analysis:** `.workflows/analyze/20261106-151026-T7WN_code_analyzer.md`
**Satisfies:** R1, R2. The lab names a book it already recorded under another id (R1), and its own
surfaces (`lab run`, `lab twins`, `lab status`, `lab promote`) stop presenting a control or an
already-recorded book as a new candidate (R2, the engine half).
**Depends on:** none
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/lab` and `engine/src/seer_engine/commands`

---

## Goal

After this phase a pure, read-only module `seer_engine.lab.twins` answers "which other recorded
trial is this same book?" from the `curve_json` every trial already carries. That covers all
existing duplicates retroactively and writes nothing. `lab run` prints a `Book twins` block after
every run. A new `lab twins` subcommand reports the same thing on demand. `lab status` tags its
near-miss and closest-to-eligible rows with each arm's role and its first-recorded twin.
`lab promote` refuses (hard gate D19) when the arm it would pre-register is a book that another
method recorded first, or a book identical to this method's own control.

## Measured at planning time (base `3b87070`, committed `lab/lab.sqlite`, read `mode=ro`)

These come from a read-only Python pass in this planning session (sha256 of `curve_json`, grouped
by `window` + `trades`, which is equivalent to byte equality). They were not copied from the
analysis. **The implementer re-measures them with the script in Proof journey J6 before quoting
any of them in the D19 docstring** (CLAUDE.md, Claim verification; memory
`plan-impact-measurements-go-stale-when-a-peer-phase-lands`).

- 1,739 trials (1,734 dev). **80 groups of twins, 260 rows, 180 duplicate rows** under the twin
  definition (any store). 76 of the groups span two or more methods, and 44 span two or more
  store fingerprints. Restricted to one store fingerprint the count is 74 groups / 195 rows / 121
  duplicates; the coordinator measured both, and they are two cuts of one lab, not a
  disagreement. The D19 docstring quotes the any-store figure (the twin definition), re-measured
  by J6.
- The handover's book: `M0125-DV-C10` (trial **519**, store `77c37d55`, run 2026-10-16),
  `M0442-DVC10-NEVER` (1536), `M0447-DVC10-NEVER` (1674), `M0447-DVC10-RECOVER` (1676),
  `M0447-DVC10-RECOVER-CAP730` (1677) and `M0488-DVC10-NEVER` (1734). The last five are on store
  `640fc25e`.
- `M0442-DVC10-FIXED730` (1537) = `M0447-DVC10-FIXED730` (1675) = `M0488-DVC10-FIXED730` (1735).
- `M0488-DVC10-DEEP15` (1736) = `-DEEP15-NOFALL730` (1737) = `-DEEP10` (1738) = `-DEEP20` (1739).
- Roles (`control_shape.role_of`): `M0447-DVC10-NEVER` and `M0488-DVC10-NEVER` read **control**.
  `M0447-DVC10-RECOVER` and `-RECOVER-CAP730` read **treatment**, so they are treatments
  identical to their own control: the treatment never acted. `M0258-M-B0` reads **dose**.
- `M0179-N20` (trial 577) has no twin.
- 152 methods are `dev-eligible`. For **42** of them the arm `best_dev_eligible` names has an
  earlier twin under another method. None is caught only by the same-method-control rule.
- `hardgate.check` passes 9 methods today: M0072, M0092, M0173, M0197, M0243, M0258, M0284,
  M0363, M0383. **D19 stops three of them**:
  - `M0173-EXP00` = `M0038-DIV-WATCH`
  - `M0258-M-B0` = `M0072-Z2-RAWRANK`
  - `M0284-VOL30` = `M0072-Z2-RAWRANK`

  M0072 stays promotable. M0258's zero rung equals M0072 by construction
  (`test_lab_m0258_band.py:128`), so a look at it would be M0072's look under M0258's name.

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.
**Creates:**
- `seer_engine.lab.twins` (`engine/src/seer_engine/lab/twins.py`), containing:
  - `Twin` (frozen dataclass). Fields: `candidate_id: str`, `method_id: str`, `n: int`,
    `store_fingerprint: str`, `run_at: str`, `window: str`, `trades: int`, `book: str` (the first
    12 hex chars of the sha256 of the curve), `of_candidate_id: str`, `of_method_id: str`,
    `of_n: int`, `of_store_fingerprint: str`. Properties: `earlier`, `same_method`, `same_store`.
    Method: `provenance()`.
  - `fingerprint(curve_json: str) -> str`
  - `twins_of(conn: sqlite3.Connection, candidate_id: str, window: str = "dev") -> tuple[Twin, ...]`
  - **`first_recorded(conn: sqlite3.Connection, candidate_id: str, window: str = "dev") -> Twin | None`**.
    This is the stable interface for Phase 2. It returns the earliest OTHER trial (lowest `n`)
    with the same book. `Twin.earlier` is True when that trial was recorded before the one asked
    about.
  - `for_method(conn, method_id: str, window: str = "dev") -> dict[str, tuple[Twin, ...]]`
  - `report_lines(found: Mapping[str, Sequence[Twin]], roles: Mapping[str, str], *, limit: int = 3) -> list[str]`
- `seer_engine.lab.hardgate.book_twin_refusal(conn, method_id: str, candidate_id: str) -> str | None`
  (`hardgate.py`), and the **(D19)** clause in `hardgate.check`.
- In `commands/lab.py`: the CLI subcommand `lab twins ID [ID ...] [--window dev|test]`, the
  handler `_twins`, and the helpers `_roles`, `_roles_by_candidate`, `_twin_lines` and
  `_book_tags`.

**Signature changes:** none. `_arm_roles(method_ids)` keeps its signature and output. Its body now
delegates to `_roles`.
**Requires (from earlier phases):** none.
**Provides to Phase 2:** `twins.first_recorded`, as above. It works on a bare
`sqlite3.connect("file:...?mode=ro", uri=True)` connection with no `row_factory`, because rows are
read by position. It never writes. It imports only `hashlib`, `sqlite3` and
`seer_engine.lab.control_shape.ROLE_CONTROL`. Phase 2 should say "first recorded as X" only when
`twin.earlier` is True. When it is False, the candidate asked about is itself the first recording.
**Provides to Phase 3:**
- The command `python -m seer_engine lab twins MNNNN|CANDIDATE ...`.
- A `lab run` block whose heading starts `Book twins:` and comes right after the `Mirror pairs`
  block. It is always printed: `Book twins: none. ...` when there are no twins.
- Per-arm lines in the forms `<arm> (<role>) = <id>, first recorded (trial N, MNNNN, run
  YYYY-MM-DD, store xxxxxxxx[, this arm's store yyyyyyyy])` and `<arm> (<role>) = <id>, an earlier
  arm of this method (...)`.
- A flag line containing `the treatment never acted`.
- A `lab promote` refusal that contains `(D19)`.

**Leaves alone (owned by others):** `.claude/skills/calculate-assets/*` (Phase 2),
`.claude/skills/sera-the-explorer/SKILL.md` and
`.claude/skills/explore-and-experiment-new-method/SKILL.md` (Phase 3). Also out of scope:
`store.best_dev_eligible`, `method.config_digest`/`config_text`, `runner.preflight`, the
schema/migrations, every method file, `walkforward.buy_signal`, `firings.py` and `web/`.

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/twins.py` | create | the pure twin reader and its report formatter |
| `engine/tests/test_lab_twins.py` | create | reader, formatter, `lab twins`, `lab run` block, `lab status` tags, live checks on the frozen trials |
| `engine/src/seer_engine/lab/hardgate.py` | modify | (D19) docstring section before the module docstring closes (line 820); `book_twin_refusal` after `promoted_arm_role` (before `def mismatches`, line 1117); one sentence of `check`'s docstring (lines 1959-1962); the D19 clause before `sv_dd = ...` (line 2053) |
| `engine/tests/test_lab_hardgate.py` | modify | a (D19) test section appended at end of file |
| `engine/src/seer_engine/commands/lab.py` | modify | usage line (after line 153); `twins` parser (after line 889); `_status` near-miss/closest blocks (lines 1002-1023); `Book twins` block in `_run` (before line 2081); `_roles`/`_arm_roles`/`_roles_by_candidate`/`_twin_lines`/`_book_tags` (replacing lines 2808-2842); `_twins` handler (before `def _exposure`, line 3457); `_HANDLERS` (line 3838) |
| `.claude/skills/verify-seer/features/lab-cli.md` | modify | `lab twins` and the status tags in Sub-features and in Driving; a gotcha on proving D19 |

## Implementation Steps

### Step 1: The twin reader
**File:** `engine/src/seer_engine/lab/twins.py` (new)
**Change:** Create the module. It is pure. It never writes, and it takes any `sqlite3.Connection`,
read-only or not, with or without a `row_factory`. Equality is tested in SQL with
`curve_json = ?`. SQLite compares TEXT under BINARY collation with `memcmp`, so this is exact byte
equality, and no hash is needed to decide twin-ness. sha256 is computed in Python only to print a
short book id. Python's `sqlite3` has no `sha3()`.
**Code:**
```python
"""Book twins: one book the lab recorded under more than one candidate id.

**Why this exists.** A trial's identity is ``method.config_digest`` -- sha256 of ``rules``, the
allocator's id and the params text. A follow-up method that wraps a host book in its own allocator
class and its own params dataclass (M0442's watched allocator, M0447's and M0488's wrapper params
around M0125's host) hands the *same* book a new digest. The only re-run guards --
``runner.preflight``'s "repeats" refusal and ``UNIQUE(config_digest, window)`` -- compare digests,
so they compare wrappers and never fire. The 2026-11-06 handover met the result as one book
relayed under four names: ``M0125-DV-C10`` (trial 519), ``M0442-DVC10-NEVER``,
``M0447-DVC10-NEVER`` and ``M0488-DVC10-NEVER``, the last three reported as if each were new.

**What a twin is.** Two trials are twins when they share the ``window``, the ``trades`` count and
a byte-identical ``curve_json``. An identical equity curve on the same window is the strongest
statement the record can make that two configurations held the same targets on every decision
date -- which is the handover's own definition -- and it reads the outcome rather than guessing
from the inputs. The trade count is a second, independent witness: a curve is sampled, and two
trade paths that happened to land on the same sampled values are not one book.

**"First recorded" is the lowest ``n``.** ``trials`` is append-only by trigger and ``n`` is
AUTOINCREMENT, so ``n`` is the order the lab recorded things in, and a later copy can never change
who came first: the answer for a recorded trial is fixed the moment it is recorded.

**Store fingerprints are reported, never compared.** The handover's book is recorded on two
stores -- trial 519 on ``77c37d55``, the other three on ``640fc25e`` -- with the same curve to the
byte. A curve that survived a store rebuild unchanged is the same book, so a twin across
fingerprints is still a twin; both fingerprints are printed so a reader can see the crossing.

**Derived on read, written nowhere.** Every trial already carries ``curve_json``, so every
duplicate the lab holds is covered retroactively, with no schema change, no new column and no
backfill. The alternative -- an "effective config" digest that strips inert wrapper fields -- would
have to move recorded digests (memory: shared params cannot gain a field) and reach inside frozen
method files to learn which fields are inert; the curve already knows.

**Not a refusal at ``lab run``.** The protocol runs a method's controls beside its treatment, and N
counts methods, not arms, so a twin costs compute and nothing else. ``lab run`` prints the twins
(hardgate D15: it annotates, it does not gate) and ``lab promote`` refuses on them (hardgate D19).

**Connection-agnostic on purpose.** Rows are read by position, never by name, so a bare
``sqlite3.connect("file:...?mode=ro", uri=True)`` -- which is how the calculate-assets skill opens
the lab, because ``store.connect`` migrates and so dirties the file on a read -- gets the same
answer ``lab`` does through ``store.connect``. This module imports nothing that opens a database.
"""

from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from seer_engine.lab.control_shape import ROLE_CONTROL

#: The columns a twin is described by, in this order. Read by position (see the module docstring).
_COLUMNS = "n, method_id, candidate_id, window, trades, store_fingerprint, run_at"

#: What a trial with no recorded curve carries. Two of them are not one book, they are two
#: absences, and absence is not evidence (hardgate D16) -- so a trial with no curve has no twins.
_NO_CURVE = frozenset({"", "[]"})


@dataclass(frozen=True, slots=True)
class Twin:
    """Another recorded trial of the same book as trial ``of_n`` (``of_candidate_id``).

    The ``of_*`` fields describe the trial that was asked about, so one value carries both store
    fingerprints and both trial numbers. Whether this twin came first is derived from the two
    ``n`` values (``earlier``) rather than stored beside them, so the two cannot disagree.
    """

    candidate_id: str
    method_id: str
    n: int
    store_fingerprint: str
    run_at: str
    window: str
    trades: int
    book: str
    of_candidate_id: str
    of_method_id: str
    of_n: int
    of_store_fingerprint: str

    @property
    def earlier(self) -> bool:
        """True when this twin was recorded before the trial asked about."""
        return self.n < self.of_n

    @property
    def same_method(self) -> bool:
        return self.method_id == self.of_method_id

    @property
    def same_store(self) -> bool:
        return self.store_fingerprint == self.of_store_fingerprint

    def provenance(self) -> str:
        """``"trial 519, M0125, run 2026-10-16, store 77c37d55, this arm's store 640fc25e"``."""
        where = f"store {self.store_fingerprint[:8]}"
        if not self.same_store:
            where += f", this arm's store {self.of_store_fingerprint[:8]}"
        return f"trial {self.n}, {self.method_id}, run {self.run_at[:10]}, {where}"


def fingerprint(curve_json: str) -> str:
    """sha256 of the recorded curve text, hex. The same hash ``lab walkforward``'s buy-signal block
    already prints for "this very book", so a book id read in one report can be found in the other.
    """
    return hashlib.sha256(curve_json.encode("utf-8")).hexdigest()


def twins_of(
    conn: sqlite3.Connection, candidate_id: str, window: str = "dev"
) -> tuple[Twin, ...]:
    """Every other recorded trial of ``candidate_id``'s book on ``window``, earliest first.

    ``()`` when the candidate has no trial on that window, when its curve is empty, or when no
    other trial shares its window, trade count and curve bytes. Never raises on a missing row and
    never writes.
    """
    me = conn.execute(
        f"SELECT {_COLUMNS}, curve_json FROM trials WHERE candidate_id = ? AND window = ?",
        (candidate_id, window),
    ).fetchone()
    if me is None:
        return ()
    curve = str(me[7])
    if curve.strip() in _NO_CURVE:
        return ()
    book = fingerprint(curve)[:12]
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM trials "
        "WHERE window = ? AND trades = ? AND curve_json = ? AND n <> ? ORDER BY n",
        (window, int(me[4]), curve, int(me[0])),
    ).fetchall()
    return tuple(
        Twin(
            candidate_id=str(r[2]),
            method_id=str(r[1]),
            n=int(r[0]),
            store_fingerprint=str(r[5]),
            run_at=str(r[6]),
            window=str(r[3]),
            trades=int(r[4]),
            book=book,
            of_candidate_id=str(me[2]),
            of_method_id=str(me[1]),
            of_n=int(me[0]),
            of_store_fingerprint=str(me[5]),
        )
        for r in rows
    )


def first_recorded(
    conn: sqlite3.Connection, candidate_id: str, window: str = "dev"
) -> Twin | None:
    """The earliest OTHER recorded trial of ``candidate_id``'s book, or None when it has none.

    The stable entry point for callers outside ``lab`` (the calculate-assets skill). Read
    ``.earlier`` before saying "first recorded as": when it is False, the candidate asked about is
    itself the first recording and the twin returned is a later copy.
    """
    found = twins_of(conn, candidate_id, window)
    return found[0] if found else None


def for_method(
    conn: sqlite3.Connection, method_id: str, window: str = "dev"
) -> dict[str, tuple[Twin, ...]]:
    """``candidate_id -> twins`` for every recorded arm of ``method_id`` that has any, in recorded
    order. An arm with no twin is absent, so an empty dict means no arm repeats a recorded book."""
    out: dict[str, tuple[Twin, ...]] = {}
    for r in conn.execute(
        "SELECT candidate_id FROM trials WHERE method_id = ? AND window = ? ORDER BY n",
        (method_id, window),
    ).fetchall():
        cid = str(r[0])
        found = twins_of(conn, cid, window)
        if found:
            out[cid] = found
    return out


def report_lines(
    found: Mapping[str, Sequence[Twin]], roles: Mapping[str, str], *, limit: int = 3
) -> list[str]:
    """The lines ``lab run`` and ``lab twins`` print, one block per arm in ``found``.

    ``roles`` is ``candidate_id -> control_shape role``, read by the caller from the method files;
    an arm missing from it is printed without a role. An arm whose earliest twin came first is
    printed ``= <that id>``; an arm that is itself the first recording says so and lists its later
    copies. A **treatment** identical to its own method's **control** is flagged: the treatment
    never acted. Only a role both sides could read flags anything -- absence is not evidence.
    """
    out: list[str] = []
    for cid, those in found.items():
        if not those:
            continue
        role = roles.get(cid)
        me = f"{cid} ({role})" if role else cid
        first = those[0]
        if first.earlier:
            whose = "an earlier arm of this method" if first.same_method else "first recorded"
            out.append(f"  {me} = {first.candidate_id}, {whose} ({first.provenance()})")
            rest = list(those[1:])
        else:
            out.append(f"  {me} is the first recording of this book (book {first.book})")
            rest = list(those)
        if rest:
            names = [t.candidate_id for t in rest[:limit]]
            more = len(rest) - len(names)
            out.append(
                "      also recorded as " + ", ".join(names) + (f" and {more} more" if more else "")
            )
        controls = [
            t.candidate_id for t in those
            if t.same_method and roles.get(t.candidate_id) == ROLE_CONTROL
        ]
        if controls and role is not None and role != ROLE_CONTROL:
            out.append(
                f"      *** the same book as this method's own control {controls[0]}: the "
                f"treatment never acted, so its margin over that control is zero by construction"
            )
    return out
```
**Impact:** New module. No caller exists until Steps 3-7. It imports `control_shape`, which
imports only `backtest.metrics`. This is a leaf import, so it adds no cycle.

### Step 2: Tests for the reader, formatter and CLI surfaces
**File:** `engine/tests/test_lab_twins.py` (new)
**Change:** Create it. The fixture helpers are imported from `test_lab_hardgate`, following the
repo's precedent (`test_backtest_walkforward.py:27` imports from `test_backtest_runner`). That
module's autouse fixture is not imported, so this module sets its own DSR policy pin for the
status test.
**Code:**
```python
"""Book twins (lab/twins.py): one book recorded under several candidate ids, named on read.

Every fixture builds its own temp lab. `_curve` is deterministic, so two trials recorded with the
same ``annual`` and ``trades`` carry byte-identical curves -- which is the whole fixture. The live
tests at the bottom read the committed lab ``mode=ro`` through a bare ``sqlite3.connect`` (the way
the calculate-assets skill opens it) and hash the file either side: the twins they name are
append-only trial rows, so a later batch can add names after them but never move them.
"""

from __future__ import annotations

import argparse
import hashlib
import sqlite3

import pytest

from seer_engine.commands import lab as lab_cmd
from seer_engine.lab import store, twins
from test_lab_hardgate import (
    DEV_SPAN,
    R_DRAW,
    R_IDEA,
    _Arm,
    _curve,
    _declare,
    _months,
    _stub_full_run,
    _trial,
)

R_STEP = "Step aside when the book falls 10 pct and come back when it recovers"


def _method_row(conn, mid: str) -> None:
    with conn:
        store.add_method(conn, id=mid, name=f"n{mid}", family="twins", source_kind="knowledge",
                         hypothesis="h", status="registered")


def _arm(conn, mid: str, suffix: str, *, annual: float = 0.15, trades: int = 250,
         window: str = "dev", store_fp: str = "640fc25e00", curve: str | None = None) -> int:
    """Record one trial of ``mid`` and return its ``n``."""
    with conn:
        (n,) = store.insert_trials(conn, [_trial(
            method_id=mid, candidate_id=f"{mid}-{suffix}",
            config_digest=f"d-{mid}-{suffix}-{window}", window=window, trades=trades,
            store_fingerprint=store_fp,
            curve_json=_curve(_months(*DEV_SPAN), annual) if curve is None else curve,
        )])
    return n


@pytest.fixture()
def conn(tmp_path):
    c = store.connect(tmp_path / "lab.sqlite")
    _method_row(c, "M0001")
    _method_row(c, "M0002")
    yield c
    c.close()


# ------------------------------------------------------------------ what a twin is


def test_the_same_curve_and_trades_on_one_window_is_one_book(conn):
    first = _arm(conn, "M0001", "A")
    second = _arm(conn, "M0002", "A")

    found = twins.twins_of(conn, "M0002-A")
    assert [t.candidate_id for t in found] == ["M0001-A"]
    t = twins.first_recorded(conn, "M0002-A")
    assert t is not None
    assert (t.n, t.of_n, t.method_id, t.of_method_id) == (first, second, "M0001", "M0002")
    assert t.earlier and not t.same_method and t.same_store
    assert t.book == twins.fingerprint(_curve(_months(*DEV_SPAN), 0.15))[:12]


def test_the_first_recording_sees_its_later_copy_and_knows_it_came_first(conn):
    _arm(conn, "M0001", "A")
    _arm(conn, "M0002", "A")

    t = twins.first_recorded(conn, "M0001-A")
    assert t is not None and t.candidate_id == "M0002-A"
    assert not t.earlier


def test_a_different_trade_count_is_a_different_book(conn):
    _arm(conn, "M0001", "A", trades=250)
    _arm(conn, "M0002", "A", trades=251)
    assert twins.twins_of(conn, "M0002-A") == ()
    assert twins.first_recorded(conn, "M0002-A") is None


def test_a_curve_one_byte_different_is_a_different_book(conn):
    curve = _curve(_months(*DEV_SPAN), 0.15)
    _arm(conn, "M0001", "A", curve=curve)
    _arm(conn, "M0002", "A", curve=curve[:-1] + " ]")
    assert twins.twins_of(conn, "M0002-A") == ()


def test_another_window_is_not_a_twin(conn):
    _arm(conn, "M0001", "A", window="dev")
    _arm(conn, "M0002", "A", window="test")
    assert twins.twins_of(conn, "M0002-A", "test") == ()
    assert twins.twins_of(conn, "M0001-A", "dev") == ()


def test_a_twin_across_store_fingerprints_is_a_twin_and_both_are_reported(conn):
    """The handover's own case: trial 519 on one store, its three copies on another."""
    _arm(conn, "M0001", "A", store_fp="77c37d55aa")
    _arm(conn, "M0002", "A", store_fp="640fc25ebb")

    t = twins.first_recorded(conn, "M0002-A")
    assert t is not None and not t.same_store
    assert (t.store_fingerprint, t.of_store_fingerprint) == ("77c37d55aa", "640fc25ebb")
    said = t.provenance()
    assert "store 77c37d55" in said and "this arm's store 640fc25e" in said


def test_a_trial_with_no_curve_has_no_twins(conn):
    _arm(conn, "M0001", "A", curve="[]")
    _arm(conn, "M0002", "A", curve="[]")
    assert twins.twins_of(conn, "M0002-A") == ()


def test_an_unknown_candidate_has_no_twins(conn):
    assert twins.twins_of(conn, "M9999-Z") == ()
    assert twins.first_recorded(conn, "M9999-Z") is None


def test_for_method_lists_only_arms_with_twins_in_recorded_order(conn):
    _arm(conn, "M0001", "A", annual=0.15)
    _arm(conn, "M0002", "X", annual=0.30)           # its own book
    _arm(conn, "M0002", "B", annual=0.15)           # M0001-A's book
    _arm(conn, "M0002", "C", annual=0.15)           # and again, same method
    found = twins.for_method(conn, "M0002")
    assert list(found) == ["M0002-B", "M0002-C"]
    assert [t.candidate_id for t in found["M0002-C"]] == ["M0001-A", "M0002-B"]
    assert list(twins.for_method(conn, "M0001")) == ["M0001-A"]


def test_it_reads_a_bare_read_only_connection_and_writes_nothing(tmp_path):
    """The calculate-assets path: no `store.connect`, no row factory, `mode=ro`."""
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _method_row(c, "M0001")
    _method_row(c, "M0002")
    _arm(c, "M0001", "A")
    _arm(c, "M0002", "A")
    c.close()
    before = hashlib.sha256(db.read_bytes()).hexdigest()

    ro = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        t = twins.first_recorded(ro, "M0002-A")
        assert t is not None and t.candidate_id == "M0001-A"
        assert list(twins.for_method(ro, "M0002")) == ["M0002-A"]
    finally:
        ro.close()
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before


# ------------------------------------------------------------------ the report


def test_report_lines_name_the_first_recording_and_an_inert_treatment(conn):
    _arm(conn, "M0001", "A")                        # first recording, another method
    _arm(conn, "M0002", "NEVER")                    # this method's control
    _arm(conn, "M0002", "RECOVER")                  # the treatment, identical to it
    found = twins.for_method(conn, "M0002")
    lines = "\n".join(twins.report_lines(found, {
        "M0001-A": "treatment", "M0002-NEVER": "control", "M0002-RECOVER": "treatment",
    }))
    assert "M0002-NEVER (control) = M0001-A, first recorded (trial 1, M0001" in lines
    assert "M0002-RECOVER (treatment) = M0001-A, first recorded" in lines
    assert "own control M0002-NEVER: the treatment never acted" in lines


def test_an_unread_role_flags_nothing(conn):
    _arm(conn, "M0002", "NEVER")
    _arm(conn, "M0002", "RECOVER")
    lines = "\n".join(twins.report_lines(twins.for_method(conn, "M0002"), {}))
    assert "M0002-RECOVER = M0002-NEVER, an earlier arm of this method" in lines
    assert "never acted" not in lines


def test_the_first_recording_lists_its_later_copies(conn):
    for suffix in ("D15", "D15N", "D10", "D20", "D25"):
        _arm(conn, "M0002", suffix)
    lines = twins.report_lines({"M0002-D15": twins.twins_of(conn, "M0002-D15")}, {})
    assert lines[0].startswith("  M0002-D15 is the first recording of this book")
    assert lines[1] == "      also recorded as M0002-D15N, M0002-D10, M0002-D20 and 1 more"


# ------------------------------------------------------------------ `lab twins`


def test_lab_twins_reports_a_method_and_a_candidate_and_writes_nothing(
    tmp_path, monkeypatch, capsys
):
    _declare(monkeypatch)                            # no method files: no role labels
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _method_row(c, "M0001")
    _method_row(c, "M0002")
    _arm(c, "M0001", "A")
    _arm(c, "M0002", "A")
    _arm(c, "M0002", "OWN", annual=0.30)
    c.close()
    before = hashlib.sha256(db.read_bytes()).hexdigest()

    args = argparse.Namespace(db=db, lab_command="twins", ids=["M0002", "M0001-A"], window="dev")
    assert lab_cmd.run(args) == 0
    out = capsys.readouterr().out
    assert "M0002 (2 dev arms): 1 arm(s) are a book the lab already holds" in out
    assert "M0002-A = M0001-A, first recorded (trial 1, M0001" in out
    assert "M0001-A: 1 arm(s) are a book the lab already holds" in out
    assert "M0001-A is the first recording of this book" in out
    assert "Nothing was written" in out
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before


def test_lab_twins_says_none_for_an_arm_with_no_twin(tmp_path, monkeypatch, capsys):
    _declare(monkeypatch)
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _method_row(c, "M0001")
    _arm(c, "M0001", "A")
    c.close()
    args = argparse.Namespace(db=db, lab_command="twins", ids=["M0001"], window="dev")
    assert lab_cmd.run(args) == 0
    assert "M0001 (1 dev arm): no other dev trial holds the same book" in capsys.readouterr().out


def test_lab_twins_refuses_an_id_it_cannot_find_rather_than_reading_clean(tmp_path):
    """"No twins" for a typo would be a false all-clear -- the failure `lab control` was caught in."""
    db = tmp_path / "lab.sqlite"
    store.connect(db).close()
    args = argparse.Namespace(db=db, lab_command="twins", ids=["M0001-TYPO"], window="dev")
    assert lab_cmd.run(args) == 2


# ------------------------------------------------------------------ `lab run` prints them (D15)


def test_lab_run_names_the_first_recording_and_still_exits_zero(tmp_path, monkeypatch, capsys):
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _method_row(c, "M0001")
    _method_row(c, "M0099")
    _arm(c, "M0001", "A")                            # recorded first, by another method
    _arm(c, "M0099", "NEVER")                        # this run's control: the same book
    _arm(c, "M0099", "RECOVER")                      # this run's treatment: the same book again
    c.close()

    _stub_full_run(monkeypatch, tmp_path, "M0099",
                   [_Arm("M0099-NEVER", R_DRAW), _Arm("M0099-RECOVER", R_STEP)])
    assert lab_cmd.run(argparse.Namespace(
        db=db, lab_command="run", method="M0099", store=tmp_path / "store", allow_coverage=0.8,
    )) == 0
    out = capsys.readouterr().out
    block = out.split("Book twins:")[1]
    assert "2 arm(s) of M0099" in block
    assert "M0099-NEVER (control) = M0001-A, first recorded" in block
    assert "own control M0099-NEVER: the treatment never acted" in block
    assert "lab twins M0099" in block and "D19" in block


def test_lab_run_says_none_when_no_arm_repeats_a_book(tmp_path, monkeypatch, capsys):
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _method_row(c, "M0099")
    _arm(c, "M0099", "A", annual=0.15)
    _arm(c, "M0099", "B", annual=0.20)
    c.close()

    _stub_full_run(monkeypatch, tmp_path, "M0099",
                   [_Arm("M0099-A", R_IDEA), _Arm("M0099-B", R_STEP)])
    assert lab_cmd.run(argparse.Namespace(
        db=db, lab_command="run", method="M0099", store=tmp_path / "store", allow_coverage=0.8,
    )) == 0
    assert "Book twins: none." in capsys.readouterr().out


# ------------------------------------------------------------------ `lab status` tags


def test_lab_status_tags_role_and_first_recorded_twin(tmp_path, monkeypatch, capsys):
    """Both lists rank raw trial rows; before this, a copy read as a fresh near miss."""
    monkeypatch.setattr(store, "DSR_POLICY", "all-trials")
    store._GATE_CACHE.clear()
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _method_row(c, "M0001")
    _method_row(c, "M0002")
    _arm(c, "M0001", "A")
    _arm(c, "M0002", "A")
    c.close()
    _declare(monkeypatch, M0001=[_Arm("M0001-A", R_IDEA)], M0002=[_Arm("M0002-A", R_DRAW)])

    assert lab_cmd.run(argparse.Namespace(db=db, lab_command="status")) == 0
    out = capsys.readouterr().out
    store._GATE_CACHE.clear()
    near = out.split("Near misses")[1].split("Closest to eligible")[0]
    line_b = next(ln for ln in near.splitlines() if ln.strip().startswith("M0002-A"))
    line_a = next(ln for ln in near.splitlines() if ln.strip().startswith("M0001-A"))
    assert line_b.endswith("[control; = M0001-A]")
    assert line_a.endswith("[idea; first of 2]")


# ------------------------------------------------------------------ the committed lab, read-only


def _committed_ro():
    if not store.COMMITTED_DB.exists():
        pytest.skip("no lab database")
    return sqlite3.connect(f"file:{store.COMMITTED_DB}?mode=ro", uri=True)


def test_the_handovers_book_was_first_recorded_as_m0125_dv_c10():
    """Trial 519, on another store, before the three wrappers that re-recorded it."""
    before = hashlib.sha256(store.COMMITTED_DB.read_bytes()).hexdigest() \
        if store.COMMITTED_DB.exists() else None
    ro = _committed_ro()
    try:
        if ro.execute("SELECT 1 FROM trials WHERE candidate_id = 'M0488-DVC10-NEVER'").fetchone() is None:
            pytest.skip("M0488 is not in this tree's lab")
        t = twins.first_recorded(ro, "M0488-DVC10-NEVER")
        assert t is not None
        assert (t.candidate_id, t.method_id, t.n) == ("M0125-DV-C10", "M0125", 519)
        assert t.earlier and not t.same_store
        assert t.store_fingerprint.startswith("77c37d55")
        assert t.of_store_fingerprint.startswith("640fc25e")
        names = [x.candidate_id for x in twins.twins_of(ro, "M0488-DVC10-NEVER")]
        assert names[:5] == ["M0125-DV-C10", "M0442-DVC10-NEVER", "M0447-DVC10-NEVER",
                             "M0447-DVC10-RECOVER", "M0447-DVC10-RECOVER-CAP730"]
        fixed = twins.first_recorded(ro, "M0488-DVC10-FIXED730")
        assert fixed is not None and fixed.candidate_id == "M0442-DVC10-FIXED730"
    finally:
        ro.close()
    assert hashlib.sha256(store.COMMITTED_DB.read_bytes()).hexdigest() == before
```
**Impact:** Test-only. The CLI tests call `_declare(monkeypatch)` (no arms) so that the real
method files for `M0001`/`M0002` cannot lend a role label to a fixture arm and shift the asserted
strings.

### Step 3: (D19) argued in the hard gate's docstring
**File:** `engine/src/seer_engine/lab/hardgate.py:819-820`. Insert this text after the last D18
paragraph (the one ending "...rather than after the owner is holding the book.") and before the
closing `"""` on line 820.
**Change:** Add the D19 section. **Before you commit, replace every number in it with what
journey J6 prints.** Two test constraints apply. `test_there_is_no_override` greps this file's
source, so the text must not contain the substrings `force` (which rules out "enforce"),
`override` (except inside "no override"), `environ` (which rules out "environment") or `getenv`.
`test_the_module_records_the_book_twin_decision` (Step 6) asserts the strings `(D19)`,
`M0442-DVC10-FIXED730`, `M0125-DV-C10`, `byte-identical` and `absence is not evidence`.
**Code:**
```text

**(D19) Does the gate check WHOSE book the variant is? -- Yes, and from 2026-11-06 ``check``
REFUSES a promotion whose pre-registered variant is a book the lab already recorded: first under
another method, or as this method's own control.**

(D18) asks what the arm *is*. It never asks whether the lab has already measured it. A trial's
identity is ``method.config_digest``, and a follow-up method that wraps a host book in its own
allocator and params dataclass hands the same book a new digest, so neither ``runner.preflight``'s
"repeats" refusal nor ``UNIQUE(config_digest, window)`` ever fires. The 2026-11-06 handover met it
as one book relayed under four names: ``M0125-DV-C10`` (trial 519, store ``77c37d55``) recorded it
first, and ``M0442-DVC10-NEVER``, ``M0447-DVC10-NEVER`` and ``M0488-DVC10-NEVER`` recorded it again
on store ``640fc25e``. Worse for this gate: M0447 and M0488 are both ``dev-eligible``, and the arm
``best_dev_eligible`` names for each is ``DVC10-FIXED730`` -- the curve of
``M0442-DVC10-FIXED730``, to the byte. Three dev-eligible methods, one book.

**What a twin is** is ``lab/twins.py``'s definition and nothing else: the same window, the same
trade count, a byte-identical ``curve_json``; the earliest recording is the lowest ``n``. It is read
from curves every trial already carries, so it covers every duplicate retroactively and writes
nothing. Measured on the committed lab at ``3b87070``: 1,739 trials, 80 groups of twins, 260 rows,
180 of them copies; 76 groups span two or more methods and 44 span two store fingerprints.

**Two refusals, one question.**

- **Another method recorded it first.** The arm's earliest twin is a trial of a different method
  with a lower ``n``. A counted look spent here is that method's measurement taken again under a
  new name, so the refusal names the first recording and says ``lab promote <that method>`` is the
  way to spend a look on this book -- where it answers to this same gate. A later copy elsewhere
  never refuses the arm that recorded the book first.
- **It is this method's own control.** A twin inside the same method whose role
  (``control_shape.role_of``, via ``promoted_arm_role``) is ``control``. The treatment never acted:
  whatever it was registered to change did not change one decision on the dev window, so its
  margin over that control is zero by construction. ``M0447-DVC10-RECOVER`` and
  ``-RECOVER-CAP730`` are the live shape -- treatments, each the curve of ``M0447-DVC10-NEVER``.
  The way back is (D18)'s: register an arm that acts and run it as an amendment, which costs no
  method id.

Two arms of one method that are one book, neither of them a control -- M0488's ``DEEP10``,
``DEEP15`` and ``DEEP20`` rungs, one curve -- are a finding for ``lab twins`` and ``lab run`` to
print, not a refusal: the dial never moved, and the arm is still this method's own measurement.

**Who it stops today, measured.** Of 152 dev-eligible methods, 42 would pre-register an arm whose
book another method recorded first; none is caught by the control rule alone. Of the nine the gate
passed before this clause, three stop here: M0173 (``M0173-EXP00`` is ``M0038-DIV-WATCH``), M0258
(``M0258-M-B0`` is ``M0072-Z2-RAWRANK``) and M0284 (``M0284-VOL30`` is ``M0072-Z2-RAWRANK``). M0072
itself stays promotable. M0258's zero rung equals M0072 by construction -- its own test says so --
which is the clause working: the look would have been M0072's look, under M0258's name.

**Absence is not evidence.** A trial with no curve has no twins. A same-method twin whose role
cannot be read refuses nothing, for (D18)'s reason. A twin across store fingerprints is still a
twin -- trial 519 is -- and both fingerprints are printed so the crossing is visible.

**Why not at ``lab run``, and why not a new digest.** (D15)'s reason: the protocol runs a method's
controls beside its treatment and N counts methods, so a twin at run time costs compute and
nothing else; ``lab run`` prints a ``Book twins`` block and refuses nothing. An "effective config"
digest that ignored inert wrapper fields would move recorded digests and need every frozen method
file to declare which of its fields are inert; the recorded curve already knows.

**Why in ``check`` and not in ``best_dev_eligible``.** (D18)'s reason exactly: a filter in the
ranking would silently move what every recorded sentence means by "its best version". A clause
refuses by name and is argued here.

**What it does not reach.** ``walkforward.buy_signal`` -- (D13)'s reason; the buy-signal block in
``lab walkforward`` already prints "the same book under another name" for a fired curve. Whether
the signal should follow this clause is another edit and the owner's call. It moves no recorded
row, no digest and no closed verdict.

**Where it sits in ``check``.** Right after (D18) and before (D16): "what is this arm" and "whose
book is it" are both about the arm's identity, and read in front of "is its fall honest".
```
**Impact:** Docstring only. Existing docstring tests look for other markers, which are unaffected.

### Step 4: `book_twin_refusal`
**File:** `engine/src/seer_engine/lab/hardgate.py:1115`. Insert after `promoted_arm_role` ends
(its `return None` at line 1114) and before `def mismatches(` (line 1117). Keep two blank lines
on each side.
**Change:** Add the function. It imports `twins` inside its body under the alias `book_twins`.
**Do not import `twins` at module scope.** `check` already binds a local called `twins`
(`twins = behavioural_kin(...)`, in the kin block). That assignment makes the name local
throughout `check`, so any module-level `twins` would be shadowed there. The alias also keeps it
apart from this module's own D14 `Twin` class.
**Code:**
```python
def book_twin_refusal(
    conn: sqlite3.Connection, method_id: str, candidate_id: str
) -> str | None:
    """Why (D19) will not pre-register ``candidate_id`` for ``method_id``; None when it will.

    The sentence, without the "Nothing was written" tail ``check`` adds. Two cases, in this order:
    the arm's earliest twin is a trial of ANOTHER method recorded before it (the book is that
    method's measurement); or a twin inside this method reads as a control in the method file (the
    treatment never acted). A same-method twin whose role cannot be read refuses nothing --
    absence is not evidence (D16) -- and two non-control arms of one method that are one book are a
    finding for ``lab twins``, not a refusal.

    Reads ``trials`` and, for the second case only, the method file through ``promoted_arm_role``.
    Writes nothing; takes any connection, read-only included.
    """
    from seer_engine.lab import control_shape
    from seer_engine.lab import twins as book_twins

    found = book_twins.twins_of(conn, candidate_id, "dev")
    if not found:
        return None
    first = found[0]
    if first.earlier and not first.same_method:
        return (
            f"{candidate_id} -- the variant `lab promote` would pre-register -- is the same book "
            f"as {first.candidate_id}, which {first.method_id} recorded first "
            f"({first.provenance()}): the same window, the same {first.trades} trades and a "
            f"byte-identical equity curve, so the same targets on every decision date. A new "
            f"method id wrapped around a recorded book does not make it a new candidate, and a "
            f"counted look spent here would be {first.method_id}'s measurement taken again under "
            f"{method_id}'s name. The evidence belongs to the method that recorded it: "
            f"`lab promote {first.method_id}` is the way to spend a look on this book, and it "
            f"answers to this same gate. `lab twins {method_id}` lists every arm of this method "
            f"the lab already holds"
        )
    for twin in found:
        if not twin.same_method:
            continue
        arm_role = promoted_arm_role(method_id, twin.candidate_id)
        if arm_role is not None and arm_role[0] == control_shape.ROLE_CONTROL:
            return (
                f"{candidate_id} -- the variant `lab promote` would pre-register -- is the same "
                f"book as {twin.candidate_id}, this method's own control arm "
                f"({twin.provenance()}): the same window, the same {twin.trades} trades and a "
                f"byte-identical equity curve. The treatment never acted -- whatever it was "
                f"registered to change did not change one decision on the dev window -- so its "
                f"record is the control's record and its margin over that control is zero by "
                f"construction. The way back is (D18)'s: register an arm that actually acts and "
                f"run it as an amendment, which costs no method id"
            )
    return None
```
**Impact:** New public function in `hardgate`. Nothing calls it until Step 5.

### Step 5: The (D19) clause in `check`
**File:** `engine/src/seer_engine/lab/hardgate.py:1959-1962` (docstring) and `:2053` (clause).
**Change A (docstring of `check`):** Replace this text:
```text
    *is* and refuses a control arm, before (D16) and (D17) ask whether its fall is honest and its
    own control is shaped right -- all three are statements about the same one arm, and "what is
    it" reads in front of the other two. All of it is cheap -- SQL, arithmetic on recorded curves
```
with:
```text
    *is* and refuses a control arm, and (D19) asks whose book it is -- one another method recorded
    first, or this method's own control's -- before (D16) and (D17) ask whether its fall is honest
    and its own control is shaped right. All four are statements about the same one arm, and "what
    is it" and "whose is it" read in front of the other two. All of it is cheap -- SQL, arithmetic on recorded curves
```
**Change B (clause):** Insert right before the line
`        sv_dd = survivorship_record.over_bar(method_id, candidate, tuning.MAX_DRAWDOWN)`. It goes
inside the `if candidate is not None:` block, after the D18 `if arm_role is not None:` block,
at 8-space indentation:
```python
        # (D19) The arm that takes the look may not be a book the lab already holds: one another
        # method recorded first (promote that method instead), or this method's own control (the
        # treatment never acted). Read from recorded curves by `lab/twins.py`; a twin across store
        # fingerprints is still a twin, and a same-method twin whose role cannot be read refuses
        # nothing. `lab run` prints the same twins and refuses nothing (D15).
        twin_said = book_twin_refusal(conn, method_id, candidate)
        if twin_said is not None:
            raise store.LabError(
                f"{method_id} is not promoted: {twin_said} (D19). Nothing was written and no "
                f"status moved. There is no override -- if the rule is wrong, change it in "
                f"seer_engine/lab/hardgate.py and argue for it in the commit"
            )
```
**Impact:** `lab promote` and `lab status`'s promotion path (`_hard_gate_states` calls `check`)
now refuse M0173, M0258 and M0284 on the committed lab (measured above). `walkforward.buy_signal`
and `firings.py` do not call `check`, so the buy signal and `web/data/lab.json` do not move.
Existing D18 tests stay green. `test_a_perfectly_shaped_control_is_still_a_control` records a
same-method twin, but D18 refuses it first. All other fixtures differ in trades (250 vs 252) or
carry empty curves. Promote tests in `test_lab_prereg.py` and `test_lab_status.py` use one method
plus a `[]`-curve ballast, so they have no twins.

### Step 6: (D19) tests
**File:** `engine/tests/test_lab_hardgate.py`, appended at end of file. It uses the existing
helpers `_benchmark`, `_method`, `_arm_row`, `_promote_the_book`, `_declare`, `_Arm`, `R_IDEA`,
`R_DRAW`, `R_CONTROL` and `_cli`.
**Code:**
```python


# --- (D19): the arm that takes the look may not be a book the lab already holds -------------------
#
# `_method` and `_arm_row` record `_curve(...)`, which is deterministic, so two arms with the same
# `annual` and the same trade count carry byte-identical curves: that is how a twin is built here.
# `_method` records 250 trades, `_arm_row` 252 by default, so the existing (D18) fixtures are not
# twins of their own book by accident.

R_STEP = "Step aside when the book falls 10 pct and come back when it recovers"


def test_the_module_records_the_book_twin_decision():
    """(D19) is argued where the other eighteen are, with its live case and its measurement."""
    doc = hardgate.__doc__ or ""
    assert "(D19)" in doc
    assert "M0442-DVC10-FIXED730" in doc and "M0125-DV-C10" in doc   # the live case
    assert "byte-identical" in doc
    assert "absence is not evidence" in doc.lower()
    assert "lab promote" in doc and "costs no method id" in doc


def test_an_arm_another_method_recorded_first_is_refused_and_both_are_named(conn, monkeypatch):
    """M0447's and M0488's shape: their promoted arm is M0442's curve, to the byte."""
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)                    # the first recording
    _method(conn, "M0002", annual=0.15)                    # the same book, recorded second
    _promote_the_book(conn, monkeypatch, "M0002")
    _declare(monkeypatch, M0001=[_Arm("M0001-A", R_IDEA)], M0002=[_Arm("M0002-A", R_IDEA)])

    with pytest.raises(store.LabError) as e:
        hardgate.check(conn, "M0002")
    said = str(e.value)
    assert "(D19)" in said
    assert "M0002-A" in said and "M0001-A, which M0001 recorded first" in said
    assert "lab promote M0001" in said
    assert "byte-identical" in said
    assert "Nothing was written and no status moved" in said
    assert "There is no override" in said


def test_the_first_recording_is_never_refused_by_a_later_copy(conn, monkeypatch):
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    _method(conn, "M0002", annual=0.15)
    _promote_the_book(conn, monkeypatch, "M0001")
    _declare(monkeypatch, M0001=[_Arm("M0001-A", R_IDEA)], M0002=[_Arm("M0002-A", R_IDEA)])

    assert hardgate.book_twin_refusal(conn, "M0001", "M0001-A") is None
    hardgate.check(conn, "M0001")                          # returns: no refusal


def test_a_treatment_identical_to_its_own_control_never_acted_and_is_refused(conn, monkeypatch):
    """M0447-DVC10-RECOVER's shape: a treatment whose curve is its own method's control."""
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    _arm_row(conn, monkeypatch, "M0001", "NEVER", mar=0.90, annual=0.12)
    _arm_row(conn, monkeypatch, "M0001", "RECOVER", mar=0.95, annual=0.12)   # named; == NEVER
    _declare(monkeypatch, M0001=[
        _Arm("M0001-A", R_IDEA), _Arm("M0001-NEVER", R_CONTROL), _Arm("M0001-RECOVER", R_STEP),
    ])

    assert hardgate.promoted_variant(conn, "M0001") == "M0001-RECOVER"
    with pytest.raises(store.LabError) as e:
        hardgate.check(conn, "M0001")
    said = str(e.value)
    assert "(D19)" in said and "M0001-NEVER" in said
    assert "this method's own control arm" in said and "never acted" in said
    assert "amendment" in said and "costs no method id" in said


def test_a_control_twin_whose_role_cannot_be_read_refuses_nothing(conn, monkeypatch):
    """Absence is not evidence: the file does not declare M0001-NEVER, so nothing is refused."""
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    _arm_row(conn, monkeypatch, "M0001", "NEVER", mar=0.90, annual=0.12)
    _arm_row(conn, monkeypatch, "M0001", "RECOVER", mar=0.95, annual=0.12)
    _declare(monkeypatch, M0001=[_Arm("M0001-A", R_IDEA), _Arm("M0001-RECOVER", R_STEP)])

    assert hardgate.book_twin_refusal(conn, "M0001", "M0001-RECOVER") is None
    hardgate.check(conn, "M0001")


def test_rungs_of_one_method_that_are_one_book_are_not_refused(conn, monkeypatch):
    """M0488's DEEP10/15/20: the dial never moved. A finding for `lab twins`, not a refusal."""
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    _arm_row(conn, monkeypatch, "M0001", "DEEP10", mar=0.90, annual=0.12)
    _arm_row(conn, monkeypatch, "M0001", "DEEP20", mar=0.95, annual=0.12)
    _declare(monkeypatch, M0001=[
        _Arm("M0001-A", R_IDEA), _Arm("M0001-DEEP10", R_STEP), _Arm("M0001-DEEP20", R_STEP),
    ])

    hardgate.check(conn, "M0001")


def test_one_more_trade_is_another_book(conn, monkeypatch):
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)                    # 250 trades
    _method(conn, "M0002", annual=0.20)
    _arm_row(conn, monkeypatch, "M0002", "B", mar=0.95, trades=251, annual=0.15)
    _declare(monkeypatch, M0001=[_Arm("M0001-A", R_IDEA)],
             M0002=[_Arm("M0002-A", R_IDEA), _Arm("M0002-B", R_STEP)])

    hardgate.check(conn, "M0002")


def test_d18_speaks_before_d19_when_the_arm_is_both(conn, monkeypatch):
    """Order inside `check`: what the arm is, then whose book it is."""
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)                    # M0001-A, 250 trades
    _method(conn, "M0002", annual=0.20)
    _arm_row(conn, monkeypatch, "M0002", "PLC1", mar=0.95, trades=250, annual=0.15)  # == M0001-A
    _declare(monkeypatch, M0001=[_Arm("M0001-A", R_IDEA)],
             M0002=[_Arm("M0002-A", R_IDEA), _Arm("M0002-PLC1", R_DRAW)])

    with pytest.raises(store.LabError) as e:
        hardgate.check(conn, "M0002")
    said = str(e.value)
    assert "D18" in said and "(D19)" not in said


def test_lab_promote_exits_2_and_writes_nothing_when_the_book_is_another_methods(
    tmp_path, monkeypatch
):
    db, prereg_dir = tmp_path / "lab.sqlite", tmp_path / "prereg"
    c = store.connect(db)
    _benchmark(c)
    _method(c, "M0001", annual=0.15)
    _method(c, "M0002", annual=0.15)
    row = c.execute("SELECT * FROM trials WHERE candidate_id = 'M0002-A'").fetchone()
    before = db.read_bytes()
    c.close()
    monkeypatch.setattr(store, "best_dev_eligible", lambda _c, _m, **_k: row)
    _declare(monkeypatch, M0001=[_Arm("M0001-A", R_IDEA)], M0002=[_Arm("M0002-A", R_IDEA)])

    assert _cli(tmp_path, db, prereg_dir, method="M0002") == 2
    assert not prereg_dir.exists()
    assert db.read_bytes() == before


def test_m0488s_promoted_book_is_m0442s_on_the_committed_lab():
    """The live case, on frozen rows: trials are append-only, so who recorded a book first never
    moves. `mode=ro`, never `store.connect`, bytes hashed either side."""
    if not store.COMMITTED_DB.exists():
        pytest.skip("no lab database")
    before = hashlib.sha256(store.COMMITTED_DB.read_bytes()).hexdigest()
    conn = sqlite3.connect(f"file:{store.COMMITTED_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        if conn.execute(
            "SELECT 1 FROM trials WHERE candidate_id = 'M0488-DVC10-FIXED730' AND window = 'dev'"
        ).fetchone() is None:
            pytest.skip("M0488 is not in this tree's lab")
        said = hardgate.book_twin_refusal(conn, "M0488", "M0488-DVC10-FIXED730")
        assert said is not None
        assert "M0442-DVC10-FIXED730, which M0442 recorded first" in said
        assert "lab promote M0442" in said
        # M0447's inert treatment: the cross-method case speaks first, naming trial 519.
        said = hardgate.book_twin_refusal(conn, "M0447", "M0447-DVC10-RECOVER")
        assert said is not None and "M0125-DV-C10, which M0125 recorded first" in said
    finally:
        conn.close()
    assert hashlib.sha256(store.COMMITTED_DB.read_bytes()).hexdigest() == before
```
**Impact:** Test-only. `hashlib` and `sqlite3` are already imported at the top of the module.

### Step 7: `commands/lab.py`, the CLI surfaces
**File:** `engine/src/seer_engine/commands/lab.py`

**7a. Usage docstring:** insert after line 153 (the last line of the `lab control` entry,
`change: N and the looks do not move`) and before `    lab idea --name ...` (line 154):
```text
    lab twins M0488 [M0447-DVC10-NEVER ...] [--window dev|test]
                                    report only: every arm that is a book the lab already holds
                                    under another id -- same window, same trade count,
                                    byte-identical equity curve -- with the first recording named
                                    and its store fingerprint beside this arm's, and a treatment
                                    identical to its own control flagged as never having acted.
                                    `lab promote` refuses on both (lab/hardgate.py, D19); `lab
                                    run` prints the same lines. No trial row, no status change: N
                                    and the looks do not move
```

**7b. Parser:** insert after line 889 (the `lab control` parser's
`s.add_argument("method", nargs="*", ...)` line, which ends on line 890). Insert before
`    s = sub.add_parser("idea", ...)` (line 891), keeping one blank line before `idea`:
```python
    s = sub.add_parser(
        "twins",
        # No literal `%` in any `help=` string below: argparse %-interpolates every `help=`.
        help="report only: which arms are a book the lab already recorded under another id",
        description=(
            "A trial's identity is its config digest, and a follow-up method that wraps a host "
            "book in its own allocator and params gives the same book a new digest, so the "
            "re-run guards never fire and one book collects several names. This lists, for every "
            "recorded arm of each named method (or each named candidate), every other trial on "
            "the same window with the same trade count and a byte-identical equity curve -- the "
            "same targets on every decision date -- with the earliest recording first, and its "
            "trial number, method, run date and store fingerprint beside this arm's. A treatment "
            "identical to its own method's control is flagged: the treatment never acted. "
            "lab promote refuses both cases (lab/hardgate.py, D19). Derived on read from the "
            "recorded curves: nothing is written, no research store is opened and no method id "
            "is minted, so the lab's N and the test-window looks cannot move."
        ),
    )
    s.add_argument("ids", nargs="+", metavar="ID",
                   help="methods (every recorded arm) or candidate ids to report")
    s.add_argument("--window", choices=store.WINDOWS, default="dev",
                   help="which window's recordings to compare (default: dev)")
```

**7c. `_status`:** replace lines 1002-1023 (from `    out.append("Near misses (beat SPY TR on dev, by MAR):")`
through the closing `)` of the closest-to-eligible `out.append(...)`) with:
```python
    out.append("Near misses (beat SPY TR on dev, by MAR):")
    near = conn.execute(
        "SELECT * FROM trials WHERE window = 'dev' AND total_return > spy_tr_return AND mar IS NOT NULL "
        "ORDER BY mar DESC LIMIT 12"
    ).fetchall()
    rows = conn.execute("SELECT * FROM trials WHERE window = 'dev' AND mar IS NOT NULL").fetchall()
    closest = sorted(rows, key=lambda r: (len(_owner_misses(r)), -r["mar"], r["n"]))[:8]
    # Both lists rank raw trial rows, so a control arm and a book the lab already recorded under
    # another id used to read here as fresh candidates (handover 2026-11-06: one book, four ids).
    # Each row now ends in its role and its first-recorded twin; see `_book_tags`.
    tags = _book_tags(conn, [*near, *closest])
    for r in near:
        out.append(
            f"  {r['candidate_id']:<28} MAR {fmt_num(r['mar'])}  CAGR {fmt_signed_pct(r['cagr'])} vs "
            f"{fmt_signed_pct(r['spy_tr_cagr'])}  maxDD {fmt_pct(r['max_drawdown'])}  PF {fmt_pf(r['profit_factor'])}  "
            f"trades {r['trades']}  DSR {fmt_num(r['dsr'], 3)}  failed: {r['failed'] or '-'}"
            f"{tags.get(str(r['candidate_id']), '')}"
        )
    out.append("")
    out.append("Closest to eligible (fewest failed go-live conditions, DSR aside, then MAR):")
    for r in closest:
        out.append(
            f"  {r['candidate_id']:<28} misses {len(_owner_misses(r))}: "
            f"{'; '.join(_owner_misses(r)) or '-'}  "
            f"CAGR {fmt_signed_pct(r['cagr'])} vs {fmt_signed_pct(r['spy_tr_cagr'])}  maxDD "
            f"{fmt_pct(r['max_drawdown'])}  PF {fmt_pf(r['profit_factor'])}  trades {r['trades']}  DSR {fmt_num(r['dsr'], 3)}"
            f"{tags.get(str(r['candidate_id']), '')}"
        )
```
(The `for title, status in (("Backlog (idea)", ...` loop that follows is unchanged.)

**7d. `_run`:** insert before line 2081 (`    if amendment is not None:`), after the mirror-pair
block's last `print`, at 4-space indentation:
```python
    # The run's book-twin reading, from the rows that were just recorded (lab/twins.py). A method
    # that wraps a host book in its own allocator and params gives that book a new digest, so the
    # re-run guard never fires and the same book is recorded again under a new id -- four times,
    # for the 2026-11-06 handover's book -- and relayed as if it were new. This names, per arm, the
    # earliest other recording of the same curve, and flags a treatment identical to this method's
    # own control: the treatment never acted.
    #
    # It ANNOTATES; it does not gate (hardgate D15). The protocol runs controls beside the
    # treatment and N counts methods, so a twin costs compute and nothing else; `lab promote`
    # refuses on the two cases that matter (D19). Always printed, `none` included, because the
    # Sera skills read this line. A FORWARDER like the blocks above: the same `report_lines`
    # `lab twins` prints, so the two can never disagree about one arm.
    from seer_engine.lab import twins

    try:
        twin_found = twins.for_method(conn, method.id)
        twin_lines = _twin_lines(twin_found) if twin_found else []
    except Exception as e:  # pragma: no cover - a reader must never fail a recorded run
        print(f"\nBook twins: not read ({e}). The trials above are recorded either way.")
    else:
        if not twin_found:
            print(f"\nBook twins: none. No arm of {method.id} repeats a book the lab already "
                  f"holds.")
        else:
            print(f"\nBook twins: {len(twin_found)} arm(s) of {method.id} are a book the lab "
                  f"already holds under another id --")
            print("      same window, same trade count, byte-identical equity curve, so the same "
                  "targets on every decision date.")
            for line in twin_lines:
                print(line)
            print("  A twin is the same measurement taken again, not new evidence: quote it by "
                  "the id that recorded it first.")
            print("  `lab promote` refuses an arm another method recorded first, or one identical "
                  "to this method's own control")
            print(f"  (lab/hardgate.py, D19); these trials are recorded either way (D15). "
                  f"`lab twins {method.id}` reprints this.")
```

**7e. Roles and tag helpers:** replace the whole of `_arm_roles` (lines 2808-2842, from
`def _arm_roles(` through its `return out`) with:
```python
def _roles(method_ids: Sequence[str]) -> dict[tuple[str, str], str]:
    """``(method, candidate) -> role`` (a ``control_shape.ROLE_*`` value) for every arm of ``method_ids``.

    The raw half of ``_arm_roles``, split out so ``lab run``, ``lab twins`` and ``lab status`` ask
    "is this arm a control" by value instead of parsing the label ``_arm_roles`` prints. Same
    reader and the same failure rule: it swallows everything, and an arm it cannot read is absent.
    See ``_arm_roles``.
    """
    try:
        from seer_engine.lab import control_shape
        from seer_engine.lab.method import discover

        found = discover()
    except Exception:  # noqa: BLE001 -- a reader, deliberately: see `_arm_roles`
        return {}
    out: dict[tuple[str, str], str] = {}
    for mid in method_ids:
        entry = found.get(mid)
        if entry is None:
            continue
        method, _path = entry
        for arm in method.all_candidates():
            try:
                out[(mid, arm.id)] = control_shape.role_of(arm)
            except Exception:  # noqa: BLE001
                continue
    return out


def _arm_roles(method_ids: Sequence[str]) -> dict[tuple[str, str], str]:
    """``(method, candidate) -> " (control)"`` for every arm of ``method_ids``; ``{}`` when unreadable.

    An arm's role is written in its rationale and nowhere else -- never in its id, which is why
    ``control_shape`` reads the prose (``M0005-ALL-R``'s ``-R`` is a rank weighting, not a
    control). Reading it needs the method files, so this is the one part of ``lab walkforward``
    that opens anything outside the database. It is called **only** when the footnote below has
    rows, so a lab with no sign disagreement -- every test fixture -- never imports a method module
    at all. Measured on the committed lab: 0.96s for the first ``discover()``, 0.005s after.

    It swallows everything. A method with no file, a file that will not import, a
    ``control_shape`` without ``role_of`` because this phase landed before the one that adds it --
    all come back as no label, and the footnote still names both arms and both numbers. The label
    is the adjective on a line that is already complete without it, and a report that crashed
    while annotating a footnote would be a worse answer than a report with a plainer footnote.
    """
    return {key: f" ({role})" for key, role in _roles(method_ids).items()}


def _roles_by_candidate(method_ids: Sequence[str]) -> dict[str, str]:
    """``candidate -> role`` over ``method_ids``. A candidate id is unique across the lab -- every
    arm's id carries its method's -- so the method half of ``_roles``' key can be dropped."""
    return {cid: role for (_mid, cid), role in _roles(sorted(set(method_ids))).items()}


def _twin_lines(found) -> list[str]:
    """``twins.report_lines`` for ``found``, with every arm's role read from its method's file:
    the arms asked about and every twin, so "the treatment never acted" can be said."""
    from seer_engine.lab import twins

    mids = {t.method_id for ts in found.values() for t in ts}
    mids |= {t.of_method_id for ts in found.values() for t in ts}
    return twins.report_lines(found, _roles_by_candidate(sorted(mids)))


def _book_tags(conn, rows) -> dict[str, str]:
    """``candidate -> "  [control; = M0125-DV-C10]"`` for the trial rows ``lab status`` lists.

    The tag says what the arm IS -- its role, from the method file's own prose
    (``control_shape.role_of``) -- and whose book it is: ``= X`` names the earliest other recording
    when X came first, and ``first of k`` says this row is the first of k recordings of one book.
    A row with neither gets no tag.

    It never raises: ``lab status`` runs on every lab there is, and a tag is an adjective on a line
    that is complete without it -- ``_arm_roles``' rule.
    """
    try:
        from seer_engine.lab import twins

        found = {
            str(r["candidate_id"]): twins.twins_of(conn, str(r["candidate_id"]), "dev")
            for r in rows
        }
        roles = _roles_by_candidate([str(r["method_id"]) for r in rows])
    except Exception:  # noqa: BLE001 -- a reader, deliberately: see the docstring
        return {}
    out: dict[str, str] = {}
    for cid, those in found.items():
        bits: list[str] = []
        role = roles.get(cid)
        if role:
            bits.append(role)
        if those:
            first = those[0]
            bits.append(f"= {first.candidate_id}" if first.earlier else f"first of {len(those) + 1}")
        if bits:
            out[cid] = f"  [{'; '.join(bits)}]"
    return out
```

**7f. Handler:** insert before `def _exposure(conn, args) -> int:` (line 3457), after
`_control`'s `return 0` and two blank lines:
```python
def _twins(conn, args) -> int:
    """``lab twins M0488 [M0447-DVC10-NEVER ...]``: which arms are a book the lab already holds.

    Report only, in the sense ``lab kin`` and ``lab control`` are reports: SQL over recorded trial
    rows (``lab/twins.py``) and one read of the method files for each arm's role. No research
    store, no backtest, no trial, no status and no journal entry; N and the looks are printed
    either side, so the invariant is on the terminal rather than merely asserted. ``lab run``
    prints the same lines through the same ``twins.report_lines`` after every run, and ``lab
    promote`` refuses on the two cases they flag (hardgate D19), so the three cannot disagree.

    An id that names a method reports every recorded arm of it; any other id is read as a
    candidate. An id that is neither is refused (exit 2): "no twins" for a typo would be a false
    all-clear, the failure ``lab control`` was once caught in.
    """
    from seer_engine.lab import twins

    window = args.window
    n_before = store.dev_trial_count(conn)
    looks_before = store.test_looks(conn)
    for ident in args.ids:
        print()
        if store.get_method(conn, ident) is not None:
            arms = conn.execute(
                "SELECT count(*) FROM trials WHERE method_id = ? AND window = ?", (ident, window)
            ).fetchone()[0]
            found = twins.for_method(conn, ident, window)
            head = f"{ident} ({arms} {window} arm{'' if arms == 1 else 's'})"
        elif conn.execute(
            "SELECT 1 FROM trials WHERE candidate_id = ? AND window = ?", (ident, window)
        ).fetchone() is not None:
            those = twins.twins_of(conn, ident, window)
            found = {ident: those} if those else {}
            head = ident
        else:
            raise store.LabError(
                f"no method and no recorded {window} trial called {ident}: nothing to compare, "
                f"and reading that as 'no twins' would be a false all-clear"
            )
        if not found:
            print(f"{head}: no other {window} trial holds the same book.")
            continue
        print(f"{head}: {len(found)} arm(s) are a book the lab already holds under another id "
              f"(same window, same trade count, byte-identical equity curve)")
        for line in _twin_lines(found):
            print(line)
    print()
    print("A twin is the same measurement taken again, not new evidence: quote it by the id that "
          "recorded it first. `lab promote` refuses an arm another method recorded first, or one "
          "identical to its own method's control (lab/hardgate.py, D19).")
    print(f"recorded dev trials {n_before} -> {store.dev_trial_count(conn)}; "
          f"test-window looks {looks_before} -> {store.test_looks(conn)}. "
          f"Nothing was written, no research store was opened and no method id was minted.")
    return 0
```

**7g. `_HANDLERS`:** after `    "control": _control,` (line 3838), add:
```python
    "twins": _twins,
```
**Impact:**
- `lab status` output gains a trailing `  [role; = X]` / `  [role; first of k]` / `  [role]` on
  near-miss and closest rows. It now runs `discover()` once more, about 1 s cold and cached after
  that. Status's `_promotion_path` already calls it through `hardgate.check`.
- `lab run` output gains one block.
- `_arm_roles` output is unchanged, so `lab walkforward` is unchanged.
- The new subcommand appears in `lab --help`. Its help strings contain no `%`.

### Step 8: Feature map
**File:** `.claude/skills/verify-seer/features/lab-cli.md`. Replace the whole file.
**Code:**
````markdown
# The lab CLI

## Sub-features

- Read: `lab status` (near-miss and closest-to-eligible rows end in `[role; = first-recorded twin]` tags), `lab show MNNNN`, `lab next-id`, `lab luck`, `lab twins MNNNN|CANDIDATE ...` (which arms are a book the lab already recorded under another id) and the report-only commands (`costs`, `timing`, `kin`, ...).
- Write (to the run's private copy only): `lab idea`, `note`, `insight`, `block`/`unblock`, `drop`, `run` (a committed method on the dev window; prints a `Book twins:` block after the mirror pairs).
- Refused: `lab test`, `promote`, `stage`, `export`, `export-json`, `seed`, and any `--db`.

## How to get to it (user POV)

The owner reads the lab through `/sera`. The CLI is what the exploration sessions (`sera-the-explorer`) drive, and its writes reach Sera only through `lab stage` + a commit, which a verify run never does.

## Driving it with verify.sh

```sh
$V up --no-web --empty
$V lab RUN status          # "dev trials (one row per recorded backtest): 1690", "test-window looks used: 5", "methods: 503"
$V lab RUN show M0007      # "M0007 Residual momentum: ... [dev-eligible]", then "Hypothesis:"
$V lab RUN next-id         # M0490
$V lab RUN twins M0488     # "M0488-DVC10-NEVER (control) = M0125-DV-C10, first recorded (trial 519, M0125, ..."; exit 0
$V lab RUN twins M0447     # "*** the same book as this method's own control M0447-DVC10-NEVER: the treatment never acted"
$V lab RUN twins M0001-TYPO   # exit 2: an unknown id is refused, never read as "no twins"
$V lab RUN idea --name "verify-seer smoke idea" --family verify-smoke --hypothesis "harness check, never run" --source-kind knowledge
                           # prints M0490; exit 0
$V labsql RUN "select id, name, status from methods where family = 'verify-smoke'"   # M0490 | verify-seer smoke idea | idea
sha1sum lab/lab.sqlite; git status --porcelain lab web/data                       # hash unchanged, nothing listed
$V lab RUN test M0007      # verify: engine: 'lab test' is never driven (...)
$V lab RUN stage           # verify: engine: 'lab stage' is never driven (...)
```

## Gotchas

- The counts above are the committed lab's at the commit under test. Read them back with `labsql` instead of quoting these (CLAUDE.md, Claim verification).
- The copy is taken read-only at `up`, so a peer's later `lab run` against the shared DB is invisible to the run, and the run's writes are invisible to everyone.
- `lab run` reads the dev research store from the main checkout (`SEER_RESEARCH_STORE`) and refuses an uncommitted method file, exactly as in real use. It takes minutes.
- Never prove anything with the test window. `lab test` is refused because a look spends the budget and contaminates every later method.
- `lab promote` is refused here, so a hard-gate clause (D19 included) is proven through `lab status`'s "Refused by the hard gate" block, which runs the same `hardgate.check`, plus read-only Python against the run's copy (`~/.local/state/seer-verify/RUN/lab.sqlite`, `mode=ro`).
````
**Impact:** Docs only. It records the user-facing change, as CLAUDE.md requires.

## Principles applied

- **Laziness protocol:** twin-ness is derived on read with one SQL equality (`curve_json = ?`)
  over a column every trial already has. There is no stored column, no table, no migration, no
  digest change and no `--all` sweep flag. D19 reuses D18's shape and `promoted_arm_role` rather
  than adding a role pipeline of its own.
- **Subtract before you add / one source:** `_arm_roles` is split into `_roles` (the raw role)
  plus a label wrapper. `lab run`, `lab twins` and `lab status` then compare roles by value
  instead of parsing `" (control)"`. `lab run` and `lab twins` print through one formatter
  (`twins.report_lines`), so they cannot drift apart.
- **Make illegal states unrepresentable:** `Twin` carries both trials' `n` and derives `earlier`,
  `same_method` and `same_store` from them. No stored "is_first" flag exists that could contradict
  `n`.
- **Boundary discipline:** the reader reads columns by position, so the one module works on
  `store.connect` connections and on Phase 2's bare `mode=ro` connection alike. `lab twins`
  rejects an unknown id at the CLI boundary (exit 2) rather than printing a false all-clear.
- **Encode lessons in structure:** the mistake was a control's money relayed as a new book, made
  four times on one book. It becomes a gate clause (D19) with fixture tests. A live test pins
  `M0488-DVC10-FIXED730 = M0442-DVC10-FIXED730` and `M0488-DVC10-NEVER -> M0125-DV-C10 (519)`
  on frozen, append-only rows.
- **Build the lever:** the D19 docstring's figures are produced by a rerunnable read-only script
  (journey J6), not typed in from this plan.
- **Prove it works / sequence into verifiable units:** each surface has a CLI-level test, and
  the Proof drives the real `lab` CLI on a verify-seer copy. The first journey fails on `main`.

## Verification

**Build:** `/home/miftah/seer/engine/.venv/bin/ruff check /home/miftah/.worktrees/seer/lab-book-twins/engine`
**Tests:**
```sh
cd /home/miftah/.worktrees/seer/lab-book-twins/engine && \
PYTHONPATH=/home/miftah/.worktrees/seer/lab-book-twins/engine/src \
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
/home/miftah/seer/engine/.venv/bin/python -m pytest -q \
  tests/test_lab_twins.py tests/test_lab_hardgate.py tests/test_lab_status.py \
  tests/test_lab_prereg.py tests/test_lab_control_shape.py tests/test_lab_fold_verdict.py
```
Then run the full suite with the same env: `... -m pytest -q tests`. Quote pass/skip counts. A
nonzero skip count means Postgres is down: `docker start seer-pg`. Without `PYTHONPATH` the run
tests the main checkout (memory `seer-worktree-tests-need-pythonpath`).

**Proof:**
- Harness: `.claude/skills/verify-seer` (`scripts/verify.sh`), run from the worktree root
  `/home/miftah/.worktrees/seer/lab-book-twins`. Engine and lab drives use the live checkout
  (`PYTHONPATH=<checkout>/engine/src`). `lab promote` is refused by the harness, so D19 is driven
  through `lab status` (same `hardgate.check`) and read-only Python on the run's copy.
- Feature-map entries: `.claude/skills/verify-seer/features/lab-cli.md`
- Setup:
  ```sh
  cd /home/miftah/.worktrees/seer/lab-book-twins
  V=.claude/skills/verify-seer/scripts/verify.sh
  $V up --no-web --empty            # note RUN=...
  sha1sum lab/lab.sqlite > /tmp/claude-1000/twins-before.sha1
  ```
- **J1 (fails before the fix): `lab twins` names the handover's book.**
  `$V lab $RUN twins M0488`. On `main` (or before Step 7) this fails: argparse prints
  `invalid choice: 'twins'` and exits 2. After the change it exits 0 and the output contains:
  - `M0488 (6 dev arms): 6 arm(s) are a book the lab already holds`
  - `M0488-DVC10-NEVER (control) = M0125-DV-C10, first recorded (trial 519, M0125, run 2026-10-16, store 77c37d55, this arm's store 640fc25e)`
  - `M0488-DVC10-FIXED730 (treatment) = M0442-DVC10-FIXED730, first recorded (trial 1537, M0442,`
  - `M0488-DVC10-DEEP15 (treatment) is the first recording of this book`
  - `M0488-DVC10-DEEP10 (treatment) = M0488-DVC10-DEEP15, an earlier arm of this method`
  - `Nothing was written`
- **J2: an inert treatment is flagged.** `$V lab $RUN twins M0447` exits 0. The output contains
  `M0447-DVC10-RECOVER (treatment) = M0125-DV-C10, first recorded` and, under it,
  `*** the same book as this method's own control M0447-DVC10-NEVER: the treatment never acted`.
- **J3: no twin, and a typo is not an all-clear.** `$V lab $RUN twins M0179-N20` exits 0 and
  prints `M0179-N20: no other dev trial holds the same book.` `$V lab $RUN twins M0001-TYPO`
  exits 2 with `no method and no recorded dev trial called M0001-TYPO`.
- **J4: `lab status` tags and the D19 refusal.** `$V lab $RUN status` exits 0.
  - Near-miss and closest-to-eligible rows end in `[...]` tags. At least one row reads
    `[<role>; = <id>]`. Grep the evidence file for `; = M`.
  - In `Promotion path`, the `Promotable now` block no longer lists `M0258`. Under `Refused by
    the hard gate`, the line after `M0258` contains `(D19)` and `M0072-Z2-RAWRANK`.
  - The same holds for `M0284` (`M0072-Z2-RAWRANK`) and `M0173` (`M0038-DIV-WATCH`).
  - If M0258's `best_dev_eligible` arm has moved since planning (the methods N policy grows with
    each batch), J6 says which arms D19 now names. Use those, and mark the M0258 line
    inconclusive rather than failing it.
- **J5: D19 on the live case, read-only on the run's copy.**
  ```sh
  PYTHONPATH=engine/src /home/miftah/seer/engine/.venv/bin/python - "$HOME/.local/state/seer-verify/$RUN/lab.sqlite" <<'EOF'
  import sqlite3, sys
  from seer_engine.lab import hardgate
  c = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True); c.row_factory = sqlite3.Row
  print(hardgate.book_twin_refusal(c, "M0488", "M0488-DVC10-FIXED730"))
  print(hardgate.book_twin_refusal(c, "M0447", "M0447-DVC10-FIXED730"))
  print(hardgate.book_twin_refusal(c, "M0442", "M0442-DVC10-FIXED730"))
  EOF
  ```
  Pass:
  - The first two lines each contain `M0442-DVC10-FIXED730, which M0442 recorded first` and
    `lab promote M0442`.
  - The third prints `None`, because the first recording is never refused.
  - `$V note $RUN "J5: D19 names M0442 for M0488 and M0447; M0442 itself clear"`.
- **J6: re-measure the figures the D19 docstring quotes (the lever).** This is read-only on the
  committed lab, `mode=ro`:
  ```sh
  PYTHONPATH=engine/src /home/miftah/seer/engine/.venv/bin/python - lab/lab.sqlite <<'EOF'
  import sqlite3, sys, collections, hashlib
  from seer_engine.lab import store, hardgate
  c = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True); c.row_factory = sqlite3.Row
  rows = c.execute("SELECT n, method_id, window, trades, store_fingerprint, curve_json FROM trials").fetchall()
  g = collections.defaultdict(list)
  for r in rows:
      if r["curve_json"].strip() in ("", "[]"): continue
      g[(r["window"], r["trades"], hashlib.sha256(r["curve_json"].encode()).hexdigest())].append(r)
  d = [v for v in g.values() if len(v) > 1]
  print("trials", len(rows), "groups", len(d), "rows", sum(map(len, d)), "copies", sum(len(v) - 1 for v in d),
        "cross-method", sum(len({r["method_id"] for r in v}) > 1 for v in d),
        "cross-store", sum(len({r["store_fingerprint"] for r in v}) > 1 for v in d))
  ms = [r["id"] for r in c.execute("SELECT id FROM methods WHERE status='dev-eligible' ORDER BY id")]
  hits, passed, d19 = 0, [], []
  for m in ms:
      b = store.best_dev_eligible(c, m)
      if b is not None and hardgate.book_twin_refusal(c, m, b["candidate_id"]): hits += 1
      try:
          hardgate.check(c, m); passed.append(m)
      except store.LabError as e:
          if "(D19)" in str(e): d19.append((m, b["candidate_id"]))
  print("dev-eligible", len(ms), "D19-twin", hits, "promotable", passed, "stopped by D19", d19)
  EOF
  ```
  Pass:
  - The script exits 0.
  - Every figure in the D19 docstring (Step 3) equals what it prints.
  - At base `3b87070` it should print `trials 1739 groups 80 rows 260 copies 180 cross-method 76
    cross-store 44`, `dev-eligible 152 D19-twin 42`, and `stopped by D19` holding M0173, M0258
    and M0284.
  - `promotable` should be the six that remain: M0072, M0092, M0197, M0243, M0363, M0383.
- **Write-nothing check:** `sha1sum -c /tmp/claude-1000/twins-before.sha1` reports OK, and
  `git status --porcelain lab web/data` lists nothing.
- **Neighbor check:** `lab walkforward` reads `_arm_roles`, which this phase refactors.
  - `$V lab $RUN walkforward` exits 0 and still prints its buy-signal block. D19 does not reach
    `buy_signal`.
  - `tests/test_lab_hardgate.py::test_the_buy_signal_fires_on_the_promoted_arm_and_the_set_moved_both_ways`
    stays green.
  - In `lab status`, the `Promotable now` block still lists M0072.
- Cost: none. These are offline drives with no LLM and no research-store load. `lab run` is not
  driven in Proof because it would need a new committed method; the `Book twins` block is proven
  by `test_lab_twins.py`'s `lab run` tests.
- Teardown: `$V down $RUN`.

**Exit criteria:**
- `lab twins M0488` prints `M0488-DVC10-NEVER (control) = M0125-DV-C10, first recorded (trial
  519, ...)` and `M0488-DVC10-FIXED730 ... = M0442-DVC10-FIXED730`.
- `lab status` refuses M0258 with `(D19)` naming `M0072-Z2-RAWRANK`.
- `book_twin_refusal(M0488, M0488-DVC10-FIXED730)` names M0442.
- ruff and the full engine suite pass with 0 skips.
- The committed `lab/lab.sqlite` hash is unchanged.

## Handoffs

- **Phase 2 (calculate-assets):** call `twins.first_recorded(conn, candidate_id, "dev")` on a
  `sqlite3.connect(f"file:{path}?mode=ro", uri=True)` connection. Say "first recorded as X" only
  when `twin.earlier`. Otherwise the candidate is itself the first recording and `twin` is a later
  copy, so say "also recorded as X". The plan index's draft signature `first_recorded(conn, n)` is
  superseded by the candidate-id signature in this plan, per the phase scope.
- **Phase 3 (Sera skills):** the strings to quote are the `Book twins:` block heading in `lab
  run` (always printed; `Book twins: none.` when clean), the `lab twins MNNNN` command, the
  phrase `the treatment never acted`, and the `(D19)` refusal at `lab promote`. R3 (the
  slate-selection warning) is Phase 3's. This phase adds no `lab idea` warning.
- **Duplicate counts (reconciled):** 80 / 260 / 180 is the twin definition (any store); 74 / 195 /
  121 is the same pass restricted to one store fingerprint. Both are correct; J6 re-measures the
  any-store figure the D19 docstring quotes.
- **Decided (index Decisions), not changed here:** `walkforward.buy_signal` (and so `/sera`'s buy
  signal) does not follow D19 in this plan set. Today it fires on M0258 and M0284, both of which
  D19 now refuses at promote; the buy-signal block already prints "the same book under another
  name". (D19) records this as not reached, following (D13) and (D18). Queued as a follow-up.
- **Decided (index Decisions), not changed here:** `control_shape.role_of` reads
  `M0488-DVC10-FIXED730` ("Clock control: ...") as `treatment`. D19's cross-method clause refuses
  that arm anyway (its earliest twin is `M0442-DVC10-FIXED730`). Queued as a follow-up.
- **Left alone (drive-by):** `lab walkforward`'s own sha256-of-`curve_json` comparison
  (`commands/lab.py` around line 2972, `promoted_curve`) could reuse `twins.fingerprint`. It
  ignores `trades` and is not wrong for its sentence. That is a separate cleanup.
- **Memory to correct (not this phase's file):** `seer-control-arm-repeats-across-methods` says
  DVC10-NEVER ran 3x. It is 4x counting `M0125-DV-C10` (trial 519), and 6 rows counting
  M0447's two inert RECOVER arms.

## Rollback

This phase is one commit: `git revert <sha>`. That removes `lab/twins.py`, the tests, the D19
clause and docstring, the `lab twins`/status/run surfaces and the feature-map edit. Nothing was
written to `lab/lab.sqlite`, no schema or digest moved, and `web/data/lab.json` is untouched, so
there is no data to roll back. If only D19 must go, delete the Step 5 clause and the Step 3/6
D19 sections. The reader and CLI surfaces stand alone.

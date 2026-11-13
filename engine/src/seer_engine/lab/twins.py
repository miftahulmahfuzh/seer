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

**A recorded control is cited, not copied (2026-11-13).** Sera batch 20261113-0721 re-ran eight arms
(M0545's SMA200 and ALWAYS, M0561's D3 and D6, four of M0606's) whose books M0084, M0558, M0108,
M0232, M0313 and M0337 had recorded first. Each was a declared control, so ``lab run`` accepted it, and
each cost a simulation and a dev trial row that said nothing new. The recorded trial already holds what
the re-run recomputes, byte for byte, so the next method cites it by first-recorded trial (``lab idea``
lists them) and runs only arms that hold a book the lab has not recorded. Nothing is written for a
citation, so the append-only rows, N (methods with a dev trial), DSR (stamped moments of recorded rows)
and D17/D19 (no twin arm exists) are all untouched. Citing is valid only when the control would be the
same rules, allocator and params on the same window and the book is on the current store; otherwise it
is re-run as a declared control, exactly as before. This refusal logic is unchanged.

**Connection-agnostic on purpose.** Rows are read by position, never by name, so a bare
``sqlite3.connect("file:...?mode=ro", uri=True)`` -- which is how the calculate-assets skill opens
the lab, because ``store.connect`` migrates and so dirties the file on a read -- gets the same
answer ``lab`` does through ``store.connect``. This module imports nothing that opens a database.
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from seer_engine.lab.control_shape import ROLE_CONTROL, Arm, role_of

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

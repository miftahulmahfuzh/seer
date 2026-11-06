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

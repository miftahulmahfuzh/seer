"""One definition of what a journal *document* is, shared by every command that journals.

The lab journal is append-only: a row is never rewritten. That is the anti-self-deception rule --
nobody can revise what a method predicted after seeing how it turned out. But append-only says
nothing about how the rows should *read*, and today a command run twice on the same subject puts
two cards in front of the owner. Schema 8 adds ``doc_key`` (what a row is about) and ``supersedes``
(which row this one replaces), so a chain of rows renders as one versioned document while the
store stays immutable. Superseding ADDS a row; it never mutates one.

The hard part is not the linking, it is the KEY, and the lab has a measured incident that settles
it. Insights 466, 467 and 468 share one title, were written 25 and 30 seconds apart, and look
exactly like an accidental triple-write. They are not: they are ``M0260-M-NATIVE``,
``M0260-M-G12`` and ``M0260-M-G3``, confirmed against trials n=835/838/836 by their recorded max
drawdown and profit factor. ``real_costs`` titles on the method NAME and never on the
``candidate_id`` it is holding. A key taken from the method, or from the generated title, would
have buried a 23.8% drawdown underneath a 33.6% one and shown the owner only the last -- a
measurement disappearing off the rendered page, which is the exact failure the append-only rule
exists to prevent, arriving through the front door of the feature written to respect it.

So the key is the SUBJECT the command measured, in one grammar for all five writers:

    <prefix>:<method id>:<scope>

``scope`` is the sorted ``+``-joined list of the arms measured when the run was narrowed to
particular arms, and the literal ``all`` when it was not. See ``doc_key``.

The method id is in every key on purpose, even where it is redundant inside a candidate id.
``store._check_supersedes`` refuses a link whose two rows disagree about ``method_id``, so a key
whose scope could span methods would raise rather than chain; putting the method in the key makes
a cross-method document unrepresentable instead of merely refused.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable

from seer_engine.lab import store

#: The scope of a run that was not narrowed to particular arms: everything the command could see
#: of this method. A later run over a grown set of arms is a new VERSION of that document, not a
#: rival to it -- the question ("what does this command say about this method?") did not change.
ALL = "all"


def doc_key(
    prefix: str, method_id: str, candidate_ids: Iterable[str] | None = None
) -> str:
    """The stable identity of the document a journal row is a version of.

    ``candidate_ids`` is ``None`` when the writer measured every recorded dev variant it could
    find. ``prefix`` names the command, so two different commands never collide on one method.

    Pass the arm list whenever the run WAS narrowed -- ``--only``, ``--gated-only``, or
    ``lab costs``, which always reports exactly one arm. A narrowed run is a deliberate question
    about those arms, and a later narrowed run about different arms must stand beside it rather
    than on top of it. That branch is what keeps M0260's three arms three documents.

    The list is sorted and de-duplicated, so ``--only A,B`` and ``--only B,A`` are one document.
    """
    if candidate_ids is None:
        scope = ALL
    else:
        ids = sorted(set(candidate_ids))
        if not ids:
            raise store.LabError(
                "a narrowed journal document needs at least one candidate id; pass None for a "
                "run that measured every recorded variant"
            )
        scope = "+".join(ids)
    return f"{prefix}:{method_id}:{scope}"


def head_for(
    conn: sqlite3.Connection, key: str, *, method_id: str | None
) -> int | None:
    """The id of the current version of document ``key``, or ``None`` if it has none yet.

    The head is the row carrying this ``doc_key`` that no other row supersedes; ``store`` owns
    that query (``store.head_for_doc_key``) so the writers and the reader cannot drift apart about
    what a head is. The 500 rows written before schema 8 carry ``doc_key IS NULL`` and never match
    a key, so no writer can accidentally supersede a historical row.

    What this adds on top is the method guard. ``store._check_supersedes`` refuses a link whose
    two rows disagree about ``method_id``, so a head belonging to another method is not a chain
    this writer may join -- it is a ``LabError`` waiting to be raised in the middle of a journal
    write. Answering ``None`` instead appends a fresh document and leaves the stray visible as its
    own, which is the set's invariant 2: nothing is ever hidden. Under the ``prefix:method:scope``
    grammar the case is unreachable anyway; it is a floor under hand-written keys.
    """
    row = store.head_for_doc_key(conn, key)
    if row is None:
        return None
    if row["method_id"] != method_id:
        return None
    return int(row["id"])


def append(
    conn: sqlite3.Connection,
    *,
    kind: str,
    title: str,
    body: str,
    method_id: str | None,
    key: str,
    supersede: bool = True,
) -> tuple[int, int | None]:
    """Write one journal row as the newest version of document ``key``.

    Returns ``(new id, the id it supersedes or None)``. The second element is ``None`` when this
    is version 1 of the document, or when ``supersede`` is False -- the ``--no-supersede`` escape,
    for a genuinely new observation that happens to share a document key and must stand beside its
    predecessor instead of replacing it on the page.

    The link is written on the INSERT, so the narrowed append-only trigger is never reached and no
    row is ever updated. If a concurrent session (``SEER_LAB_DB`` is shared) linked to the same
    head between the read and the insert, the unique index ``insights_one_successor`` refuses this
    row; the head is re-read once and the row is written against theirs, so the two runs chain
    rather than fork. A second failure is a real error and is raised.

    The caller owns the transaction (``with conn:``).
    """
    previous = head_for(conn, key, method_id=method_id) if supersede else None
    try:
        new_id = store.add_insight(
            conn, kind=kind, title=title, body=body, method_id=method_id,
            doc_key=key, supersedes=previous,
        )
    except (sqlite3.IntegrityError, store.LabError):
        if previous is None:
            raise
        previous = head_for(conn, key, method_id=method_id)
        new_id = store.add_insight(
            conn, kind=kind, title=title, body=body, method_id=method_id,
            doc_key=key, supersedes=previous,
        )
    return new_id, previous


def entry_label(new_id: int, superseded: int | None) -> str:
    """How a written entry is reported to the owner: ``#471``, or ``#471 (revises #468)``.

    Plain words and plain numbers -- the owner reads this line, so it says what happened to his
    page rather than naming a column.
    """
    return f"#{new_id}" if superseded is None else f"#{new_id} (revises #{superseded})"

"""Which methods the buy signal fires on, and how many distinct **books** that really is.

``walkforward.buy_signal`` answers "should the owner pay for survivorship-free price history?"
for one method. This module is the lab-wide reading of that answer, and it exists for two
reasons.

**One definition, two readers.** ``lab walkforward`` prints the signal in a terminal report and
``/sera`` now shows it on the page the owner actually reads. Those are not allowed to disagree:
a page saying "buy" while the report says "not yet" is worse than either answer, which is the
lesson Decision D9 in ``lab/hardgate.py`` already paid for over the kin rule. So the per-method
work lives here once -- ``verdict`` -- and both callers read it.

**Methods are not books.** Until 2026-10-21 the signal was printed one line per method id, and on
that day it printed three: M0072, M0092 and M0258. They are one book. ``M0258-M-B0`` is
``M0072-Z2-RAWRANK``'s curve with a no-op band, their residual correlation is +1.0000, and both
younger methods record M0072 as ``parent_id`` -- the lineage was declared before the behaviour
confirmed it. The owner was shown three independent reasons to spend real money and owned one,
an error in the direction that encourages spending. ``books.group`` is the collapse; insight 529
and ``docs/backtests/2026-10-21-lab-book-clustering.md`` are the measurement.

Nothing here writes, journals, or moves a status, and no research store is opened: every number
comes from ``trials.curve_json`` and the recorded deposit schedule.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from seer_engine.lab import books, hardgate, store
from seer_engine.lab import walkforward as wf

#: The era the dev store prices best -- 48% of index members in 1996 against 74% in 2014, and the
#: 522 it cannot price are disproportionately the companies that died. The fifth buy condition is
#: the sign of the promoted arm's edge over it. Lived in ``commands/lab.py`` until the snapshot
#: needed the same window; it is here so the report and the page cannot read two different eras.
HIGH_COVERAGE = (date(2009, 1, 1), date(2015, 10, 16))


@dataclass(frozen=True, slots=True)
class Verdict:
    """One method's buy-signal answer, and every number the report prints beside it.

    ``record`` is the SELECTOR's fold record -- at each fold the lab's own rule names a variant
    knowing nothing past the train end. ``own`` is the narrower question (D11) asks of a
    promotion: did the one variant that would take the pre-registration, the counted look and the
    owner's money win those folds by itself. They are an AND inside ``buy_signal``, never a swap.

    ``edge`` and ``edge_se`` are the promoted arm's 2009-2015 lead over the benchmark and that
    lead's own year-to-year noise. The noise is printed and never tested against.
    """

    method_id: str
    record: wf.Record
    own: wf.Record | None
    promoted: str | None
    edge: float | None
    edge_se: float | None
    eligible: bool
    family_failed: str | None
    fired: bool
    why: str


def verdict(
    conn: sqlite3.Connection,
    method_id: str,
    curves: dict[str, list[tuple[date, float]]],
    deps: dict[str, dict[date, float] | None],
    bench: Sequence[tuple[date, float]],
    folds: Sequence[wf.Fold],
) -> Verdict:
    """Run every buy condition for one method over ``folds``, and say what it decided.

    ``curves`` and ``deps`` are the method's recorded dev variants, already de-fundable -- the
    caller has them because it is also printing a table from them, and re-reading the rows here
    would be a second chance to disagree about which rows a method has.

    The promoted arm's record is built inline rather than through ``hardgate.variant_record``
    because ``lab walkforward`` takes ``--min-train-years`` and ``--eval-years``, so its folds are
    not always the gate's fixed geometry. Everything else -- the de-funding, the benchmark, the
    one-entry mapping -- is the gate's own path.

    The kin question goes to ``hardgate.failed_kin``, the **same** rule ``lab promote`` enforces
    (family, union transitive ancestors, union blend ingredients and theirs (D12), union the
    tested books a variant moves with (D14)), never a second query beside it; Decision D9 is what
    happened the one time those two drifted apart. When the kin cannot be read at all -- (D10)
    refuses a comparison across two price fingerprints -- the reason goes in *as* the failed kin,
    so the signal can never fire on a kin nobody could check.
    """
    rec = wf.Record(method_id, wf.evaluate(curves, bench, folds, deps))
    promoted = hardgate.promoted_variant(conn, method_id)
    if promoted is None or promoted not in curves:
        own, edge, se = None, None, None
    else:
        own = wf.Record(
            method_id,
            wf.evaluate({promoted: curves[promoted]}, bench, folds, {promoted: deps.get(promoted)}),
        )
        edge = wf.era_edge(curves[promoted], bench, *HIGH_COVERAGE, deps.get(promoted))
        se = wf.era_edge_se(curves[promoted], bench, *HIGH_COVERAGE, deps.get(promoted))

    row = store.get_method(conn, method_id)
    eligible = row is not None and row["status"] == "dev-eligible"
    if row is None:
        family_failed = None
    else:
        try:
            kin = hardgate.failed_kin(conn, method_id)
        except store.LabError as e:
            family_failed = f"kin unknown ({e})"
        else:
            family_failed = ", ".join(kin) if kin else None

    fired, why = wf.buy_signal(eligible, rec, edge, family_failed, own_record=own, edge_se=se)
    return Verdict(
        method_id, rec, own, promoted, edge, se, eligible, family_failed, fired, why
    )


def _curve_of(row: sqlite3.Row) -> list[tuple[date, float]]:
    return hardgate._curve_of(row)


def firing(conn: sqlite3.Connection) -> tuple[list[books.Book], dict[str, str]]:
    """Every method the buy signal fires on at the gate's own geometry, collapsed to books.

    Returns ``(books, why)``: one ``books.Book`` per distinct book, newest evidence collapsed onto
    the method the others descend from, and the ``why`` sentence ``buy_signal`` returned for each
    firing method id -- so a reader can show the reason for the row it is standing on and still
    reach the others underneath.

    **Only ``dev-eligible`` methods are evaluated.** That is not an optimisation with a behaviour
    risk attached: ``dev-eligible`` is ``buy_signal``'s *first* condition and it refuses on it
    before reading anything else, so a method that is not eligible cannot fire however its folds
    came out. Skipping the rest turns a whole-lab pass over 286 methods into one over the ~78 that
    could possibly fire, which is what makes this affordable inside ``lab stage``.

    ``([], {})`` -- not "nothing fired", but "there is nothing to read" -- when the lab has no
    recorded benchmark curve to cut folds from. Every fresh fixture is in that state, and the
    snapshot is documented to answer on a database that has never been migrated, so this fails
    quiet rather than taking the export down with it.
    """
    try:
        geo = hardgate.geometry(conn)
    except store.LabError:
        return [], {}

    eligible = [
        str(r["id"])
        for r in conn.execute("SELECT id FROM methods WHERE status = 'dev-eligible' ORDER BY id")
    ]
    bench = list(geo.bench)
    why: dict[str, str] = {}
    for mid in eligible:
        rows = hardgate._dev_curves(conn, mid)
        if not rows:
            continue
        curves = {str(r["candidate_id"]): _curve_of(r) for r in rows}
        deps = {
            str(r["candidate_id"]): hardgate.trial_deposits(
                conn, r, curves[str(r["candidate_id"])]
            )
            for r in rows
        }
        v = verdict(conn, mid, curves, deps, bench, list(geo.folds))
        if v.fired:
            why[mid] = v.why
    return books.group(conn, why), why


def test_look_books(conn: sqlite3.Connection) -> list[books.Book]:
    """The methods that have spent a test-window look, collapsed to the books they bought.

    Four looks are spent and all four failed, which the lab has been quoting as a 0-for-4 record
    against its own approach. Three of the four are one book -- M0021, M0022 and M0029 agree at
    0.93 to 0.99, M0029 *is* M0021's child and both it and M0022 grew out of M0011 -- so the
    record is 0-for-2 on distinct books and the scarcest resource the lab owns was spent twice on
    the same thing. Both halves of that matter and they cut opposite ways: the evidence against
    the lab's approach is half as strong as it has been quoted, and the budget leaked.

    Ordered by the look that was spent first, so the list reads as the history it is.
    """
    spent = [
        str(r["method_id"])
        for r in conn.execute(
            "SELECT method_id, min(n) AS first_n FROM trials WHERE window = 'test' "
            "GROUP BY method_id ORDER BY first_n"
        )
    ]
    order = {m: i for i, m in enumerate(spent)}
    return sorted(books.group(conn, spent), key=lambda bk: min(order[m] for m in bk.members))

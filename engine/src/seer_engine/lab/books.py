"""How many *distinct books* a list of method ids actually contains.

The lab counts methods. The owner spends money on books, and a method id is not a book: two ids
can be one strategy wearing two names. On 2026-10-21 that gap was measured (insight 529,
``docs/backtests/2026-10-21-lab-book-clustering.md``) and it was costing the owner in both
directions at once.

- The buy signal named **M0072, M0092 and M0258**. ``M0258-M-B0`` is ``M0072-Z2-RAWRANK``'s curve
  with a no-op band -- their residual correlation is +1.0000 -- and both M0092 and M0258 record
  M0072 as ``parent_id``. Three rows on the page that gates a real purchase, one book underneath
  them. Wrong in the direction that encourages spending.
- The lab's scarcest resource reads "four test-window looks spent, all four failed". M0021, M0022
  and M0029 agree at 0.925-0.992, M0029 *is* M0021's child and all three descend from M0011. Only
  M0002 is separate. So four looks bought **two** books, the out-of-sample record is 0-for-2 and
  not 0-for-4, and three of the four looks bought nearly the same information.

Both halves matter and they cut opposite ways, which is why this module reports a count rather
than a verdict. Nothing here refuses anything: no status moves, no trial is written, the hard
gate is untouched. It is a *presentation* rule -- collapse a lineage to one row, keep every name
reachable underneath it.

**The rule, and why it is shaped this way.** The brief is "prefer the structural fact, confirm it
with behaviour":

1. **Lineage proposes.** ``parent_id`` is declared by the author before the run and costs one
   query to read. Two methods related through a chain of ``parent_id`` links are *claimed* to be
   the same lineage.
2. **The recorded curves confirm or refuse.** A lineage link merges only when the two methods'
   dev curves actually move together at ``hardgate.KIN_CORRELATION``. A child that changed the
   idea is a new book even though its parent is declared, and this is the clause that stops the
   lineage pass chaining: M0007 is a transitive ancestor of a large part of the lab, so a bare
   transitive closure over ``parent_id`` would swallow dozens of unrelated books.
3. **Behaviour also catches twins that are not relatives** -- two authors arriving at one book by
   different roads. A pair with no declared relation merges on correlation alone.
4. **When the curves cannot be read, the declaration stands.** (D10) refuses a comparison across
   two price fingerprints, and a method may have no curve at all. Lineage then merges unchecked,
   because for a spending decision the conservative answer is *fewer* apparent independent
   confirmations, not more.

Every number comes from ``lab/hardgate.py``: ``geometry``, ``mismatches`` (D10), ``trial_deposits``,
``monthly_returns``, ``residual``, ``correlation`` and the ``KIN_CORRELATION`` bar itself. There
is deliberately no second definition of "two books move together" in this repository -- the
clustering pass that found the bug reused them too, and agreed with ``hardgate.correlation`` to
1.2e-15 over 400 spot-checked pairs.

**Linkage is complete, not single.** A group forms only when **every** pair inside it clears the
bar. The clustering report's first correction was that single linkage chains: at 0.85 its
transitive closure put 147 of 171 methods in one component in which only 12.1% of the pairs
actually cleared the bar and the minimum was -0.372 -- two members of the "same" book moving in
opposite directions. Complete linkage cannot do that. The sets this module is asked about are
small (three firings, four spent looks), so the greedy order below is not load-bearing; it is
still seeded by degree and then by id so the answer is deterministic.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from seer_engine.lab import hardgate, store


#: ``Same.kind`` -> how the site says it, with ``{lead}`` left for the lead's **name**. The site
#: writes names and the report writes ids, so the shape of the sentence lives here once and the
#: two callers fill it differently. Every one of these is readable by someone who has never seen
#: a method id: that is the house rule for anything the owner reads.
SAME_BOOK_TEXT = {
    "child": "written as a version of {lead}",
    "version": "a later version of {lead}",
    "sibling": "grew out of the same earlier method as {lead}",
    "twin": "not related on paper, but it trades the same way as {lead}",
    "declared": "written as a version of {lead}, and its record is too thin to check against",
}


@dataclass(frozen=True, slots=True)
class Same:
    """Why one method is the same book as the lead it collapsed onto.

    ``kind`` is a key of ``SAME_BOOK_TEXT``, so a caller can phrase it with ids or with names.
    ``via`` is the shared earlier method, present only for ``"sibling"``. ``correlation`` is the
    residual correlation that confirmed it, or ``None`` when the curves could not be compared and
    the declaration stood alone -- which is the ``"declared"`` kind.
    """

    kind: str
    via: str | None = None
    correlation: float | None = None

    def sentence(self, lead: str) -> str:
        """The reason with ids in it, for a terminal report: ``"written as a version of M0072"``."""
        text = SAME_BOOK_TEXT[self.kind].format(lead=lead)
        if self.kind == "sibling" and self.via is not None:
            text = f"grew out of {self.via}, as {lead} did"
        if self.correlation is not None:
            text += f" (they move together at {self.correlation:.2f})"
        return text


@dataclass(frozen=True, slots=True)
class Book:
    """One distinct book, and every method id that is really it.

    ``lead`` is the member the row is shown under: the member the others descend from when the
    group has one, else the lowest id -- the earliest, which is the one the others were derived
    from. ``others`` are the same book under another name, in id order, and ``why`` says of each
    how it is known to be the same book, so the collapsed row can be opened rather than trusted.
    """

    lead: str
    others: tuple[str, ...]
    why: dict[str, Same]

    @property
    def members(self) -> tuple[str, ...]:
        """Every id in the book, ``lead`` first."""
        return (self.lead, *self.others)

    def __len__(self) -> int:
        return 1 + len(self.others)


def count(books: Sequence[Book]) -> int:
    """How many distinct books ``books`` is -- the number the owner should be reading."""
    return len(books)


def names_text(ids: Sequence[str]) -> str:
    """``('M0092', 'M0258')`` -> ``'M0092 and M0258'``; three or more take commas."""
    if not ids:
        return ""
    if len(ids) == 1:
        return ids[0]
    return f"{', '.join(ids[:-1])} and {ids[-1]}"


# --------------------------------------------------------------------------- the two signals

def _ancestors(conn: sqlite3.Connection, method_id: str) -> list[str]:
    """``method_id``'s transitive ancestors through ``parent_id``, nearest first.

    Carries a ``seen`` set for the same reason ``hardgate._lineage`` does: ``methods.parent_id``
    is a self-referencing foreign key with no cycle constraint, so a cycle would hang the walk.
    """
    out: list[str] = []
    seen = {method_id}
    row = store.get_method(conn, method_id)
    cur = None if row is None else row["parent_id"]
    while cur is not None and str(cur) not in seen:
        seen.add(str(cur))
        out.append(str(cur))
        parent = store.get_method(conn, str(cur))
        cur = None if parent is None else parent["parent_id"]
    return out


def _relation(conn: sqlite3.Connection, lead: str, other: str) -> Same | None:
    """How ``other`` is declared a relative of ``lead``; ``None`` when they are not relatives.

    Directional, because the row the owner reads is the lead's and the sentence under it is about
    the other one. Three shapes: ``other`` is a direct child of ``lead`` (``"child"``), it
    descends from ``lead`` further back or the other way about (``"version"``), or the two descend
    from a third method (``"sibling"``). The sibling case is what holds M0021, M0022 and M0029
    together -- M0029 is M0021's child, and M0021 and M0022 are both M0011's.

    ``correlation`` is left unset here; ``group`` fills it in once the curves have confirmed the
    declaration, so the sentence can carry the number that checked it.
    """
    up_lead, up_other = _ancestors(conn, lead), _ancestors(conn, other)
    if up_other[:1] == [lead]:
        return Same("child")
    if lead in up_other or other in up_lead:
        return Same("version")
    shared = next((x for x in up_other if x in up_lead), None)
    return None if shared is None else Same("sibling", via=shared)


def _residuals(
    conn: sqlite3.Connection, method_ids: Sequence[str], geo: hardgate.Geometry
) -> dict[str, list[tuple[str, dict]]]:
    """Each method's dev variants as market-removed monthly return series. See (D14).

    ``hardgate``'s own path end to end: ``trial_deposits`` to de-fund, ``monthly_returns`` for the
    month-on-month steps, ``residual`` for the ordinary least-squares fit on SPY's own month. A
    variant whose residual cannot be measured -- too few shared months, or a flat series -- is
    dropped here, exactly as ``behavioural_kin`` drops it, so it can never read as agreement.

    (D10) is applied per method rather than per pair: a method carrying any row measured on prices
    other than the benchmark's is left out of the dictionary entirely, which makes every pair it
    is in unmeasurable, which makes the declaration stand. Failing closed on an id the gate itself
    would refuse to compare is the same answer the gate gives, reached one step earlier.
    """
    bench = hardgate.monthly_returns(list(geo.bench))
    out: dict[str, list[tuple[str, dict]]] = {}
    for mid in method_ids:
        rows = hardgate._dev_curves(conn, mid)
        if not rows or hardgate.mismatches(conn, geo.bench_n, rows):
            continue
        series: list[tuple[str, dict]] = []
        for r in rows:
            curve = hardgate._curve_of(r)
            res = hardgate.residual(
                hardgate.monthly_returns(curve, hardgate.trial_deposits(conn, r, curve)), bench
            )
            if res is not None:
                series.append((str(r["candidate_id"]), res))
        if series:
            out[mid] = series
    return out


def _best_correlation(
    mine: list[tuple[str, dict]], theirs: list[tuple[str, dict]]
) -> float | None:
    """The highest residual correlation between any variant of one method and any of the other.

    "Best twin" semantics, which is what (D14) already means by two methods moving together, and
    what the clustering report's method-level link used. ``None`` when no pair could be measured
    at all -- never 0.0, which would read as "measured, and unrelated".
    """
    best: float | None = None
    for _a, x in mine:
        for _b, y in theirs:
            rho = hardgate.correlation(x, y)
            if rho is not None and (best is None or rho > best):
                best = rho
    return best


# --------------------------------------------------------------------------- the grouping

def group(conn: sqlite3.Connection, method_ids: Iterable[str]) -> list[Book]:
    """``method_ids`` collapsed to one ``Book`` per distinct book, in id order.

    Lineage proposes, the recorded curves confirm, and a pair with no declared relation can still
    merge on behaviour alone (the module docstring has the full rule and why each clause is
    there). Linkage is complete: a method joins a group only when it clears the bar -- or is an
    unmeasurable relative -- against **every** member already in it.

    Degrades to the declaration alone rather than raising. ``store.LabError`` out of ``geometry``
    -- a lab with no recorded benchmark, which is every fresh fixture -- leaves every pair
    unmeasurable, and rule 4 then stands: declared relatives collapse, unrelated ids do not. The
    caller is a report or a page, so a lab whose curves cannot be read must still answer, and the
    answer it gives is the conservative one -- fewer apparent independent confirmations, never
    more.
    """
    ids = sorted({str(m).upper() for m in method_ids})
    if len(ids) < 2:
        return [Book(m, (), {}) for m in ids]

    try:
        geo = hardgate.geometry(conn)
        residuals = _residuals(conn, ids, geo)
    except store.LabError:
        residuals = {}

    # (a, b) -> the best residual correlation of their dev variants, measured once. The pairwise
    # correlation is the expensive half and the greedy pass below reads each pair many times.
    rho: dict[tuple[str, str], float | None] = {}
    for i, a in enumerate(ids):
        for b in ids[i + 1 :]:
            rho[(a, b)] = (
                None
                if a not in residuals or b not in residuals
                else _best_correlation(residuals[a], residuals[b])
            )

    def same(lead: str, other: str) -> Same | None:
        """Is ``other`` the same book as ``lead``, and how is that known? See the module docstring.

        Lineage proposes and the curves confirm; a pair that is not declared can still merge on
        behaviour alone; and when the curves cannot be read the declaration stands, because for a
        spending decision the safe error is to count fewer independent confirmations, not more.
        """
        r = rho[(lead, other)] if lead < other else rho[(other, lead)]
        rel = _relation(conn, lead, other)
        if rel is not None and r is None:
            return Same("declared", via=rel.via)
        if rel is not None and r >= hardgate.KIN_CORRELATION:
            return Same(rel.kind, via=rel.via, correlation=r)
        if rel is None and r is not None and r >= hardgate.KIN_CORRELATION:
            return Same("twin", correlation=r)
        return None

    def link(a: str, b: str) -> bool:
        return same(a, b) is not None

    degree = {m: sum(1 for o in ids if o != m and link(m, o)) for m in ids}
    groups: list[list[str]] = []
    placed: set[str] = set()
    # Complete linkage, greedy: seed on the most-connected id, then admit any id that clears the
    # bar against every member already admitted. Seeding by degree and then by id makes the
    # partition deterministic; it is still an approximation of the optimal partition, and the
    # module docstring says so. The memberships are exact either way -- every pair inside every
    # group really does link.
    for seed in sorted(ids, key=lambda m: (-degree[m], m)):
        if seed in placed:
            continue
        member = [seed]
        placed.add(seed)
        for other in ids:
            if other in placed:
                continue
            if all(link(other, m) for m in member):
                member.append(other)
                placed.add(other)
        groups.append(sorted(member))

    books: list[Book] = []
    for member in groups:
        lead = _lead(conn, member)
        others = tuple(m for m in member if m != lead)
        reasons = {m: same(lead, m) for m in others}
        books.append(Book(lead, others, {m: r for m, r in reasons.items() if r is not None}))
    return sorted(books, key=lambda bk: bk.lead)


def _lead(conn: sqlite3.Connection, member: Sequence[str]) -> str:
    """Which id a book is shown under: the one the others descend from, else the earliest.

    A member that is a transitive ancestor of every other is the book's origin and the obvious
    row to collapse onto -- M0072 for the three firings. When there is no such member (two twins
    that are not relatives, or siblings whose shared ancestor is not in the set) the lowest id
    wins: ids are allocated in order, so it is the one that came first.
    """
    for m in sorted(member):
        if all(m in _ancestors(conn, o) for o in member if o != m):
            return m
    return sorted(member)[0]

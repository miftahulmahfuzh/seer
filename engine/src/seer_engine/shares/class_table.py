"""Which listed symbol each share class of a multi-class filer answers for, and at what ratio. Pure.

Vendored source (``engine/data``, documented in ``SOURCES.md``):

* ``share_classes.csv`` -- ``cik,member,symbol,ratio,from,to,note``. One row per (filer, share
  class, span): over counts taken in ``[from, to)`` (``to`` exclusive, empty while current), the
  filer's class ``member`` counts toward ``symbol`` at ``ratio`` of that symbol's shares per share
  of the class. ``ratio`` 0 is a class with no economic interest in the listed line (Accenture's
  class X ordinary shares carry votes only; Liberty Interactive's Ventures tracking stock is a
  different company's worth on the same filer). ``note`` cites the filing the row rests on.

**Why a table at all.** A filer's cover states one count per class. Summed 1:1 they are the
whole company, which is right for Meta (class B converts into class A share for share and only
class A trades) and wrong in three ways the sum cannot see: a class that converts at another
ratio (Berkshire's class A is 1,500 class B; Visa's class B converts at a rate its litigation
escrow keeps lowering), a class with no claim on the listed line (Accenture class X), and two
listed classes that are both index members (GOOGL and GOOG), where the whole company on each line
counts the company twice. The table says, for exactly those filers and spans, which classes each
listed symbol stands for. A filer with no row answers as before: every class summed, the whole
company on each of its symbols. A method then weights a company once without a list of its own.

**Keyed on the day the filer counted, not the day asked.** A count is stated in the share units
and class structure of its own date; the splits after it are carried by the split list
(``history.split_factor``), so the ratio that turns class A into class B units is the one in force
when the count was taken (30 for a 2009 Berkshire count, 1,500 for a 2010 one, and the 2009 count
read in 2010 is then carried across the 50-for-1 class B split like any pre-split count). The same
date decides which symbol a class answers: a sibling's rows start at the first count the sibling
needs, so a span begins a little before the sibling joins an index (the notes say which count).

**Class labels are matched by their words.** Per-class XBRL names a class by its axis member's
local name (``CommonClassAMember``, ``CapitalClassCMember``, ``v:CommonClassB1Member``) and the
pre-2010 cover parser by its cover text (``class a common``, ``series c``). :func:`class_key`
splits either into lowercase words (camel case and punctuation both split), drops the words that
name no class (``common``, ``stock``, ``member``, ...), reads ``series`` as ``class`` and sorts what
is left, so ``CommonClassAMember``, ``class A``, ``series a common`` and ``ClassAOrdinarySharesMember``
are one key, ``("a", "class")``. Filers' own spellings that carry no letter stay distinct
(Liberty Global's class A is ``ClassOrdinarySharesMember``, key ``("class",)``; Comcast's special
class is ``ClassaSpecialCommonStockMember``) and the table names them as the filing does. A context
with a second axis (a tracking-stock group) arrives as both members' names in one label; sorting
the words makes the key independent of the order and the separator.

**Fail loud where the table speaks, sum where it does not.** A filer with no row on a count's
date has its classes summed one for one (the caller records it in ``SharesHistory.summed``, and
``shares store`` prints the list). Where the table speaks for a filer on a count's date, every
class of that count must match a row: an unmatched class (``shares.instance.NO_AXIS_MEMBER``
included, until a row says which class the bare figure is) makes the answer unknown, never a
guess, and the caller lists it (``SharesHistory.problems``, printed by ``shares store``). A figure
with no class breakdown (an axis-less XBRL tag, a cover that gave one total) cannot be split and
is unknown there too.

Nothing in this module reads the network, the clock or the database.
"""

from __future__ import annotations

import csv
import math
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import NamedTuple

TABLE_FILE = "share_classes.csv"
HEADER: tuple[str, ...] = ("cik", "member", "symbol", "ratio", "from", "to", "note")

#: What separates the member names of a multi-axis context (any run of characters that is not
#: part of a name or a namespace prefix).
_PARTS = re.compile(r"[^A-Za-z0-9:_-]+")
_WORD = re.compile(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|\d+")
#: Words that never tell one class from another.
NOISE = frozenset({"member", "common", "stock", "shares", "share", "ordinary", "capital"})


class ClassTableError(ValueError):
    """The vendored class table is inconsistent."""


def class_key(label: str) -> tuple[str, ...]:
    """The words that identify a share class, lowercased and sorted (module docstring).

    ``"us-gaap:CommonClassAMember"``, ``"class A"`` and ``"series a common"`` all give
    ``("a", "class")``; ``"v:CommonClassB1Member"`` and ``"class B-1"`` give ``("1", "b", "class")``.
    Anything before a namespace colon is dropped. An empty key means the label names no class.
    """
    out: list[str] = []
    for part in _PARTS.split(label):
        local = part.rpartition(":")[2]
        for word in _WORD.findall(local):
            w = word.lower()
            if w in NOISE:
                continue
            out.append("class" if w == "series" else w)
    return tuple(sorted(out))


@dataclass(frozen=True)
class ClassRule:
    """One row of the table: ``member`` of ``cik`` counts toward ``symbol`` at ``ratio``."""

    cik: str
    member: str
    key: tuple[str, ...]
    symbol: str
    ratio: float
    start: date
    end: date | None  # exclusive; None while current
    note: str

    def covers(self, counted: date) -> bool:
        """True when a count taken on ``counted`` falls in ``[start, end)``."""
        return self.start <= counted and (self.end is None or counted < self.end)


class Attribution(NamedTuple):
    """What :meth:`ClassTable.attribute` answers: the shares (None: unknown) and, when the
    answer is unknown for a reason the table's keeper should see, that reason."""

    shares: float | None
    problem: str | None


class ClassTable:
    """The class rules by filer, queried on a count's date."""

    def __init__(self, rules: Iterable[ClassRule] = ()) -> None:
        by: dict[str, list[ClassRule]] = {}
        for r in rules:
            by.setdefault(r.cik, []).append(r)
        self._by = {k: tuple(sorted(v, key=lambda r: (r.key, r.start))) for k, v in by.items()}

    def __len__(self) -> int:
        return sum(len(v) for v in self._by.values())

    def ciks(self) -> frozenset[str]:
        """Every filer the table speaks for on some date."""
        return frozenset(self._by)

    def rules(self, cik: str, counted: date) -> tuple[ClassRule, ...]:
        """The rows of ``cik`` covering a count taken on ``counted``."""
        return tuple(r for r in self._by.get(cik, ()) if r.covers(counted))

    def attribute(
        self,
        cik: str | None,
        symbol: str,
        counted: date,
        total: float,
        classes: Sequence[tuple[str, int]],
    ) -> Attribution:
        """The part of one count that ``symbol`` stands for, in ``symbol``'s share units.

        ``total`` is the reading's whole-company figure (the classes summed, or the tagged
        total) and ``classes`` its per-class breakdown (empty when it has none). With no row for
        ``cik`` on ``counted`` the answer is ``total``: the behaviour of every filer before the
        table existed. Otherwise each class counts ``n x ratio`` toward the symbol its row names
        and nothing toward any other; a symbol none of whose classes appear in the count (GOOG in
        a count taken before class C existed) is unknown. Unknown, with a ``problem``, when the
        table names no class of the filer for ``symbol``, when the figure has no breakdown, or
        when a class has no row.
        """
        rules = self.rules(cik, counted) if cik is not None else ()
        if not rules:
            return Attribution(float(total), None)
        if symbol not in {r.symbol for r in rules}:
            return Attribution(None, f"the class table names no class of this filer for {symbol}")
        if not classes:
            return Attribution(None, "a figure without its classes where the class table speaks")
        by_key = {r.key: r for r in rules}
        value = 0.0
        missing: list[str] = []
        for label, n in classes:
            rule = by_key.get(class_key(label))
            if rule is None:
                missing.append(label)
            elif rule.symbol == symbol:
                value += n * rule.ratio
        if missing:
            return Attribution(None, "no class-table row for " + ", ".join(sorted(missing)))
        return Attribution(value if value > 0 else None, None)


# --- the csv ----------------------------------------------------------------------------


def _date(raw: str, where: str) -> date:
    try:
        return date.fromisoformat(raw.strip())
    except ValueError as exc:
        raise ClassTableError(f"{where}: bad date {raw!r}") from exc


def load_table(path: Path) -> ClassTable:
    """Read and validate the vendored table (invariants in :func:`check_rules`)."""
    rules: list[ClassRule] = []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if tuple(reader.fieldnames or ()) != HEADER:
            raise ClassTableError(f"{path}: expected header {','.join(HEADER)}, got {reader.fieldnames}")
        for lineno, raw in enumerate(reader, start=2):
            where = f"{path.name}:{lineno}"
            cik = (raw["cik"] or "").strip()
            if len(cik) != 10 or not cik.isdigit():
                raise ClassTableError(f"{where}: cik must be 10 digits, got {cik!r}")
            member = (raw["member"] or "").strip()
            symbol = (raw["symbol"] or "").strip()
            if not symbol or symbol != symbol.upper() or any(ch.isspace() for ch in symbol):
                raise ClassTableError(f"{where}: symbol must be an upper-case ticker, got {symbol!r}")
            try:
                ratio = float((raw["ratio"] or "").strip())
            except ValueError as exc:
                raise ClassTableError(f"{where}: bad ratio {raw['ratio']!r}") from exc
            end_text = (raw["to"] or "").strip()
            rules.append(ClassRule(
                cik=cik,
                member=member,
                key=class_key(member),
                symbol=symbol,
                ratio=ratio,
                start=_date(raw["from"] or "", where),
                end=_date(end_text, where) if end_text else None,
                note=(raw["note"] or "").strip(),
            ))
    check_rules(rules, path.name)
    return ClassTable(rules)


def check_rules(rules: Sequence[ClassRule], name: str = TABLE_FILE) -> None:
    """The table's invariants: at least one row; a member that names a class (non-empty key); a
    finite ratio of at least 0; ``to`` after ``from``; a note on every row; and one row at most
    per (filer, class key) on any date -- a class counting toward two symbols at once, or at two
    ratios, is the double count this table exists to remove."""
    if not rules:
        raise ClassTableError(f"{name}: no rows")
    for i, r in enumerate(rules, start=2):
        where = f"{name}:{i}"
        if not r.key:
            raise ClassTableError(f"{where}: member {r.member!r} names no class")
        if not (math.isfinite(r.ratio) and r.ratio >= 0):
            raise ClassTableError(f"{where}: ratio must be a finite number >= 0, got {r.ratio!r}")
        if r.end is not None and r.end <= r.start:
            raise ClassTableError(f"{where}: to {r.end} is not after from {r.start}")
        if not r.note:
            raise ClassTableError(f"{where}: every row needs a note citing its source")
    by: dict[tuple[str, tuple[str, ...]], list[ClassRule]] = {}
    for r in rules:
        by.setdefault((r.cik, r.key), []).append(r)
    for (cik, key), group in by.items():
        group = sorted(group, key=lambda r: r.start)
        for a, b in zip(group, group[1:]):
            if a.end is None or a.end > b.start:
                raise ClassTableError(
                    f"{name}: {cik} class {' '.join(key)!r} has overlapping rows "
                    f"[{a.start}, {a.end or ''}) and [{b.start}, {b.end or ''})"
                )

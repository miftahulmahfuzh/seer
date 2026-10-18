"""Share counts per class out of a filing's own XBRL instance document.

Why this exists. From 2009 the stores' share counts come from SEC's ``companyfacts`` API (through
each store's ``fundamentals.csv``), and ``companyfacts`` drops every *dimensional* fact. A filer
that tags ``dei:EntityCommonStockSharesOutstanding`` once per share class -- each fact in a
context whose segment names a ``StatementClassOfStockAxis`` member, with no undimensioned total --
therefore has no 2009+ count in the stores at all: Meta (class A 2,015,048,077 and class B
585,003,514 on its 2014-07-24 10-Q), Visa, Mastercard, Alphabet from 2014. The instance document
the filer submitted still carries every fact, so the count is read from there.

Two steps, both pure:

* :func:`parse` -- the share facts and the contexts they point at, out of the instance bytes.
  Only ``EntityCommonStockSharesOutstanding`` (the cover figure, ``dei``) and
  ``CommonStockSharesOutstanding`` (the balance-sheet figure, ``us-gaap``) are kept, each with its
  context's instant, entity identifier and dimension members. This is what the download cache
  keeps (``fetch.fetch_instances``), so the reading rule below can change without a refetch.
* :func:`reading` -- one filing's count from those facts: the cover tag when the filing has it
  (the balance-sheet tag only when it has none), the filer's own facts only, each class at its
  newest instant, and the undimensioned total when the filer tagged one that agrees with its
  classes. An undimensioned figure that is *not* their total is either one class tagged twice
  (with and without the axis: dropped) or a class tagged without one (a filer that tags its main
  class bare and the other on the axis; ``companyfacts`` kept only such bare figures, which is
  why Berkshire read class A alone there): it is then counted as a class of its own,
  :data:`NO_AXIS_MEMBER`, never thrown away, because dropping it would undercount the company by
  that class.
* Tracking stocks (Liberty Interactive, Liberty Media 2016, Liberty Global's LiLAC) tag each
  class once per group, on a group axis beside the class axis. Such a fact is kept, labelled with
  both member names (``CommonClassAMember+InteractiveGroupMember``), because which group a
  class belongs to decides which listed symbol it is (``shares.class_table``).

**Matching by namespace, not prefix.** Prefixes are the filer's choice (Berkshire's 2011
instance puts the XBRL instance namespace in the default namespace, with no ``xbrli:`` at all),
and the taxonomy namespaces are versioned (``http://xbrl.us/dei/2009-01-31``,
``http://xbrl.sec.gov/dei/2013-01-31``), so an element is a cover fact when its namespace URI has
a ``/dei/`` path segment and its local name is the tag. Dimension and member QNames
(``us-gaap:StatementClassOfStockAxis``, ``goog:CapitalClassCMember``) are kept by local name: the
axis is recognised by name, and the member's local name (``CommonClassAMember``) is what the
per-class csv records.

**Why ``xml.etree`` and not ``defusedxml``.** The engine does not depend on ``defusedxml``, and
the only input is SEC's own Archives, fetched over HTTPS. ``xml.etree`` never fetches external
entities or DTDs, and the expat bundled with Python 3.11 refuses billion-laughs expansion; an
XBRL instance has no DOCTYPE at all, so :func:`parse` refuses any document that declares one
before parsing it. ``iterparse`` keeps memory flat: the cover facts sit at the *end* of the file
(byte 1,173,860 of Meta's 1,178,188), so the whole instance is read, but each top-level element
is dropped as soon as it has been looked at.

Nothing here reads the network, the clock or the disk.
"""

from __future__ import annotations

import io
import json
import re
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

XBRLI = "http://www.xbrl.org/2003/instance"
XBRLDI = "http://xbrl.org/2006/xbrldi"
XSI = "http://www.w3.org/2001/XMLSchema-instance"

COVER_TAG = "EntityCommonStockSharesOutstanding"
BALANCE_TAG = "CommonStockSharesOutstanding"
#: (taxonomy, local name) of the facts kept, in preference order. The taxonomy is matched as a
#: path segment of the namespace URI (module docstring).
TAGS: tuple[tuple[str, str], ...] = (("dei", COVER_TAG), ("us-gaap", BALANCE_TAG))

#: Axes whose members are share classes. ``StatementClassOfStockAxis`` is the one the dei
#: taxonomy pairs with the cover count; a few filers use the older ``ClassOfStockAxis``.
CLASS_AXES: frozenset[str] = frozenset({"StatementClassOfStockAxis", "ClassOfStockAxis"})

#: Axes that split a filer's classes into tracking-stock groups (Liberty Interactive's
#: ``TrackingStockAxis``, Liberty Media's ``EconomicPerformanceGroupAxis``, Liberty Global's LiLAC
#: on ``StatementBusinessSegmentsAxis``). A fact on one of these *and* a class axis is one class of
#: one group; any other second axis (``RangeAxis``, ``LegalEntityAxis``) is not the filer's count.
GROUP_AXES: frozenset[str] = frozenset(
    {"TrackingStockAxis", "EconomicPerformanceGroupAxis", "StatementBusinessSegmentsAxis"}
)
#: Joins the member names of a two-axis label, in axis-name order. Outside ``[A-Za-z0-9:_-]`` and
#: none of the csv's ``=;,"``, so ``class_table.class_key`` splits on it and the csv keeps it.
GROUP_JOIN = "+"

#: The label of an undimensioned figure that is neither the classes' total nor one of them: a
#: class the filer tagged without an axis (rule 4 of :func:`reading`).
NO_AXIS_MEMBER = "NoClassAxisMember"

#: A class whose newest fact is more than this many days older than the filing's newest is a
#: comparative (a prior period end on the balance sheet, a class retired since) and is dropped.
MEMBER_SPREAD_DAYS = 31

#: Relative gap within which an undimensioned figure is the total of the class figures.
TOTAL_TOL = 0.005

#: Bytes at the head of a document searched for a DOCTYPE declaration (module docstring).
DOCTYPE_SCAN = 4096

#: Files of an XBRL submission that are never the instance: the linkbases, EDGAR's rendering
#: (``FilingSummary.xml``, and the ``R1.xml``.. pages and ``defnref.xml`` of 2009-2011 filings).
_SUPPORT_SUFFIXES = ("_cal.xml", "_def.xml", "_lab.xml", "_pre.xml", "_ref.xml")
_RENDERED = re.compile(r"^(R\d+|defnref|filingsummary)\.xml$", re.IGNORECASE)


class InstanceError(ValueError):
    """The bytes are not a readable XBRL instance (or not a readable filing index)."""


@dataclass(frozen=True)
class Fact:
    """One share-count fact with its context resolved.

    ``taxonomy`` is ``"dei"`` or ``"us-gaap"``; ``dims`` is ``((axis, member), ...)`` by local
    name, sorted; ``typed`` is True when the context also has a typed dimension (never a plain
    class count); ``instant`` is None for a duration context (never a share count; kept so the
    cache records what the filing said).
    """

    taxonomy: str
    tag: str
    value: int
    instant: date | None
    identifier: str
    dims: tuple[tuple[str, str], ...]
    typed: bool = False

    def to_json(self) -> dict[str, object]:
        return {
            "x": self.taxonomy,
            "t": self.tag,
            "v": self.value,
            "i": self.instant.isoformat() if self.instant else None,
            "e": self.identifier,
            "d": [list(d) for d in self.dims],
            "y": self.typed,
        }

    @classmethod
    def from_json(cls, raw: object) -> Fact:
        if not isinstance(raw, dict):
            raise InstanceError(f"cached fact is not an object: {raw!r}")
        try:
            dims = tuple((str(a), str(m)) for a, m in raw["d"])
            value = raw["v"]
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise InstanceError(f"cached fact has a bad value: {value!r}")
            instant = date.fromisoformat(raw["i"]) if raw["i"] else None
            return cls(str(raw["x"]), str(raw["t"]), value, instant, str(raw["e"]), dims,
                       bool(raw["y"]))
        except (KeyError, TypeError, ValueError) as exc:
            if isinstance(exc, InstanceError):
                raise
            raise InstanceError(f"cached fact is malformed: {raw!r}") from exc


@dataclass(frozen=True)
class Reading:
    """One filing's share count, as :func:`reading` decides it.

    ``classes`` is ``((member, count), ...)`` sorted by member, empty when the filing tagged only
    an undimensioned figure. ``shares`` is that figure, the classes summed one for one, or (when
    ``tagged_total``) the undimensioned total tagged beside the classes. ``set_aside`` is an
    undimensioned figure that was *not* within :data:`TOTAL_TOL` of the classes' sum: dropped as
    a class tagged twice, or counted as :data:`NO_AXIS_MEMBER` (None when there was none, or it
    was the tagged total). ``build-classes`` prints every one for review.
    """

    tag: str
    as_of: date
    shares: int
    classes: tuple[tuple[str, int], ...]
    tagged_total: bool
    set_aside: int | None = None


# --- the filing index ---------------------------------------------------------------------


def filing_files(index_json: bytes) -> list[str]:
    """The file names an Archives ``<accession-dir>/index.json`` lists."""
    try:
        doc = json.loads(index_json)
    except ValueError as exc:
        raise InstanceError(f"filing index is not JSON: {exc}") from exc
    directory = doc.get("directory") if isinstance(doc, dict) else None
    items = directory.get("item") if isinstance(directory, dict) else None
    if not isinstance(items, list):
        raise InstanceError("filing index has no directory.item list")
    return [i["name"] for i in items if isinstance(i, dict) and isinstance(i.get("name"), str)]


def instance_name(names: Sequence[str]) -> str | None:
    """Which of a filing's files is its XBRL instance, or None when it has none.

    Inline XBRL (2019+) ships the extracted instance as ``<stem>_htm.xml``; a traditional
    submission names the instance after its schema (``fb-20140630.xsd`` -> ``fb-20140630.xml``).
    Failing both, a single candidate left after the linkbases and EDGAR's rendered pages are
    removed is the instance; several are ambiguous and give None.
    """
    xml = [
        n for n in names
        if n.lower().endswith(".xml")
        and not n.lower().endswith(_SUPPORT_SUFFIXES)
        and not _RENDERED.match(n)
    ]
    inline = [n for n in xml if n.lower().endswith("_htm.xml")]
    if len(inline) == 1:
        return inline[0]
    stems = {n[: -len(".xsd")] for n in names if n.lower().endswith(".xsd")}
    named = [n for n in xml if n[: -len(".xml")] in stems]
    if len(named) == 1:
        return named[0]
    if len(xml) == 1:
        return xml[0]
    return None


# --- the instance ---------------------------------------------------------------------------


def _local(qname: str) -> str:
    """``us-gaap:CommonClassAMember`` -> ``CommonClassAMember`` (also for Clark ``{uri}name``)."""
    qname = qname.strip()
    if qname.startswith("{"):
        return qname.rpartition("}")[2]
    return qname.rpartition(":")[2]


def _iso(text: str | None) -> date | None:
    raw = (text or "").strip()[:10]
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _count(text: str | None) -> int | None:
    """A positive share count, or None. XBRL values are plain decimals (``585003514``,
    ``2013000000``, rarely ``1.5E9``); a fractional one is rounded."""
    try:
        d = Decimal((text or "").strip())
    except InvalidOperation:
        return None
    if not d.is_finite() or d <= 0:
        return None
    n = int(d.to_integral_value())
    return n if n > 0 else None


def _taxonomy(uri: str, name: str) -> str | None:
    for taxonomy, tag in TAGS:
        if name == tag and f"/{taxonomy}/" in uri:
            return taxonomy
    return None


_Context = tuple[date | None, str, tuple[tuple[str, str], ...], bool]


def _context(el: ET.Element) -> _Context:
    ident = el.find(f"{{{XBRLI}}}entity/{{{XBRLI}}}identifier")
    instant = el.find(f"{{{XBRLI}}}period/{{{XBRLI}}}instant")
    dims = tuple(sorted(
        (_local(m.get("dimension", "")), _local(m.text or ""))
        for m in el.iter(f"{{{XBRLDI}}}explicitMember")
    ))
    typed = next(el.iter(f"{{{XBRLDI}}}typedMember"), None) is not None
    return (
        _iso(instant.text) if instant is not None else None,
        (ident.text or "").strip() if ident is not None else "",
        dims,
        typed,
    )


def parse(blob: bytes) -> list[Fact]:
    """Every cover and balance-sheet share-count fact of an instance, its context resolved.

    Contexts may come before or after the facts that cite them (XBRL 2.1 does not order them), so
    facts are collected with their ``contextRef`` and resolved at the end; a fact citing a
    context the document lacks is dropped. Nil facts and non-positive values are dropped.
    """
    head = blob[:DOCTYPE_SCAN].lower()
    if b"<!doctype" in head or b"<!entity" in head:
        raise InstanceError("the document declares a DOCTYPE; an XBRL instance never does")
    contexts: dict[str, _Context] = {}
    raw: list[tuple[str, str, int, str]] = []
    root: ET.Element | None = None
    depth = 0
    try:
        for event, el in ET.iterparse(io.BytesIO(blob), events=("start", "end")):
            if event == "start":
                if root is None:
                    root = el
                    if el.tag != f"{{{XBRLI}}}xbrl":
                        raise InstanceError(f"root element is {el.tag!r}, not an XBRL instance")
                depth += 1
                continue
            depth -= 1
            if depth != 1:
                continue
            if el.tag == f"{{{XBRLI}}}context":
                cid = el.get("id")
                if cid:
                    contexts[cid] = _context(el)
            elif el.tag.startswith("{"):
                uri, _, name = el.tag[1:].partition("}")
                taxonomy = _taxonomy(uri, name)
                if taxonomy is not None and el.get(f"{{{XSI}}}nil") != "true":
                    ref = el.get("contextRef")
                    value = _count(el.text)
                    if ref and value is not None:
                        raw.append((taxonomy, name, value, ref))
            # Drop every finished top-level element: memory stays flat however big the file.
            assert root is not None
            root.clear()
    except ET.ParseError as exc:
        raise InstanceError(f"not well-formed XML: {exc}") from exc
    if root is None:
        raise InstanceError("empty document")
    out: list[Fact] = []
    for taxonomy, name, value, ref in raw:
        ctx = contexts.get(ref)
        if ctx is None:
            continue
        instant, ident, dims, typed = ctx
        out.append(Fact(taxonomy, name, value, instant, ident, dims, typed))
    return out


# --- one filing's count ---------------------------------------------------------------------


def _same_filer(identifier: str, cik: str) -> bool:
    """The context's entity is ``cik`` (an identifier that is not a number cannot say no)."""
    ident = identifier.strip()
    if not ident.isdigit():
        return True
    return int(ident) == int(cik)


def _counts_for_filer(f: Fact) -> bool:
    """No dimension; one class-axis member; or one class-axis and one tracking-group member."""
    if f.typed:
        return False
    if not f.dims:
        return True
    axes = [a for a, _ in f.dims]
    if len(axes) == 1:
        return axes[0] in CLASS_AXES
    return (len(axes) == 2 and sum(a in CLASS_AXES for a in axes) == 1
            and sum(a in GROUP_AXES for a in axes) == 1)


def _label(f: Fact) -> str:
    """The member names of ``f``'s context in axis-name order (``""`` with no dimension)."""
    return GROUP_JOIN.join(m for _, m in f.dims)


def reading(facts: Iterable[Fact], cik: str) -> Reading | None:
    """The filing's share count from its cached facts, or None when it states none for ``cik``.

    The rules, in order:

    1. Only facts with an instant, whose context entity is ``cik``, and with no dimension, a
       single class-axis member, or a class-axis member beside a tracking-group member
       (:data:`GROUP_AXES`; the label keeps both names joined by :data:`GROUP_JOIN`). A
       co-registrant's count, a ``LegalEntityAxis`` subsidiary or a class split by any other
       second axis is not the filer's count. When a filing has group-and-class facts, its
       class-only facts are the same shares again and are dropped.
    2. The cover tag (``dei``) if any such fact has it; the balance-sheet tag otherwise.
    3. Each class label (and the undimensioned figure) at its own newest instant; the filing's
       ``as_of`` is the newest of those, and a label more than :data:`MEMBER_SPREAD_DAYS` older
       is a comparative and dropped. The same value repeated counts once; several values of the
       undimensioned figure at one instant are classes tagged without an axis and are summed
       (``history.xbrl_by_symbol``'s rule); several of one class label, the largest.
    4. With classes and an undimensioned figure within :data:`TOTAL_TOL` of their sum, that
       figure is the tagged total and is the count. An undimensioned figure within
       :data:`TOTAL_TOL` of one class is that class tagged twice and is dropped. Any other
       undimensioned figure is a class tagged without an axis: it joins the classes as
       :data:`NO_AXIS_MEMBER` and the count is their sum (the same reading
       ``history.xbrl_by_symbol`` gives several bare figures). In both of the last two cases the
       figure is reported in ``set_aside`` for review.
    """
    mine = [f for f in facts if f.instant is not None and _same_filer(f.identifier, cik)
            and _counts_for_filer(f)]
    for taxonomy, tag in TAGS:
        group = [f for f in mine if f.taxonomy == taxonomy and f.tag == tag]
        if any(len(f.dims) == 2 for f in group):
            group = [f for f in group if len(f.dims) != 1]
        if group:
            return _read(tag, group)
    return None


def _read(tag: str, group: Sequence[Fact]) -> Reading:
    by_key: dict[str, list[Fact]] = {}
    for f in group:
        by_key.setdefault(_label(f), []).append(f)
    newest = {k: max(f.instant for f in v if f.instant) for k, v in by_key.items()}
    as_of = max(newest.values())
    floor = as_of - timedelta(days=MEMBER_SPREAD_DAYS)
    values: dict[str, int] = {}
    for key, fs in by_key.items():
        if newest[key] < floor:
            continue
        distinct = {f.value for f in fs if f.instant == newest[key]}
        values[key] = sum(distinct) if key == "" else max(distinct)
    total = values.pop("", None)
    classes = tuple(sorted(values.items()))
    if not classes:
        assert total is not None  # the newest key survives the floor
        return Reading(tag, as_of, total, (), False)
    class_sum = sum(n for _, n in classes)
    if total is None:
        return Reading(tag, as_of, class_sum, classes, False)
    if abs(total - class_sum) <= TOTAL_TOL * class_sum:
        return Reading(tag, as_of, total, classes, True)
    if any(abs(total - n) <= TOTAL_TOL * n for _, n in classes):
        # One class tagged with and without the axis: counted once.
        return Reading(tag, as_of, class_sum, classes, False, total)
    # A class tagged without an axis (rule 4): counted as a class of its own.
    merged = tuple(sorted(classes + ((NO_AXIS_MEMBER, total),)))
    return Reading(tag, as_of, class_sum + total, merged, False, total)

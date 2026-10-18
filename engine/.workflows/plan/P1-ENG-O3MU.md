> Adopted from `MULTI_CLASS_COMPANY_SIZE_PLAN.md` phase 1. Source: `.workflows/plan/multi-class-company-size/phase-1.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 1: Per-class counts from XBRL instances

**Plan set:** `MULTI_CLASS_COMPANY_SIZE_PLAN.md`
**Analysis:** `20261018-171434-MCS7_code_analyzer.md`
**Satisfies:** R1 (the reading half) — per-class XBRL share counts, summed or the tagged total, dated by filing date, written to a committed-format csv that phase 2 turns into the store's history
**Depends on:** none
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/shares`

---

## Goal

After this phase the engine can read the share-count facts that SEC's `companyfacts` API drops:
for every 2009+ 10-K/10-Q of an S&P 500 or Nasdaq-100 member's filer that lacks a cover count in
the dev store's `fundamentals.csv` (or whose filer has several classes), `shares download-classes`
fetches the filing's own XBRL instance into the EDGAR cache (parsed share facts only), and
`shares build-classes` turns the cache into `engine/data/shares_xbrl_classes.csv`: one row per
filing with its per-class counts (`CommonClassAMember=2015048077;CommonClassBMember=585003514`),
their 1:1 sum or the tagged total, the context instant (`as_of`) and the filing date (`filed`,
the only availability date). Nothing reads that csv yet. Phase 2 wires it into `SharesHistory`
and phase 3 runs the download and commits the csv.

All the code below was prototyped in a scratch copy of the tree and run before this plan was
written: the new tests and the existing shares tests pass, `ruff check engine` is clean, and a
live three-filing sample through `fetch.fetch_instances` + `classes.build_rows` gave Meta 2014-07-24
`as_of=2014-07-22 shares=2600051591 CommonClassAMember=2015048077;CommonClassBMember=585003514`,
Meta 2021 (inline XBRL, `fb-20210630_htm.xml`) `2819444501`, and Berkshire 2011-08-05
`CommonClassAMember=939981;CommonClassBMember=1066954104` (1:1 sum 1067894085; phase 2 converts A).
The reader was also checked on Google's 2014-07-25 10-Q (A, B and `goog:CapitalClassCMember`) and
Visa's 2012-07-27 10-Q (A, B, C).

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.
**Creates:**
- `seer_engine.shares.instance` (`shares/instance.py`, new, pure): `InstanceError`, `Fact`
  (`taxonomy, tag, value, instant, identifier, dims, typed`; `to_json` / `from_json`), `Reading`
  (`tag, as_of, shares, classes, tagged_total, set_aside`), `parse(blob) -> list[Fact]`,
  `reading(facts, cik) -> Reading | None`, `filing_files(index_json) -> list[str]`,
  `instance_name(names) -> str | None`; constants `COVER_TAG`, `BALANCE_TAG`, `TAGS`, `CLASS_AXES`,
  `GROUP_AXES`, `GROUP_JOIN = "+"`, `NO_AXIS_MEMBER = "NoClassAxisMember"`,
  `MEMBER_SPREAD_DAYS = 31`, `TOTAL_TOL = 0.005`, `DOCTYPE_SCAN`.
- `seer_engine.shares.classes` (`shares/classes.py`, new): **the contract phase 2 imports**
  - `ClassRow(cik: str, symbol: str, filed: date, as_of: date, form: str, accession: str, shares: int, classes: tuple[tuple[str, int], ...], tagged_total: bool)` — frozen dataclass, field order exactly this.
  - `load_rows(path: Path) -> list[ClassRow]` — strict reader; raises `ClassesError` on a bad header, a bad field, an empty file, unsorted or duplicate rows.
  - `CLASSES_FILE = "shares_xbrl_classes.csv"`, `DATA_DIR = history.DATA_DIR` (so the default path is `classes.DATA_DIR / classes.CLASSES_FILE` = `engine/data/shares_xbrl_classes.csv`).
  - `HEADER = ("cik","symbol","filed","as_of","form","accession","shares","classes","tagged_total")`; `classes` cell `member=count;...` sorted by member (the XBRL member's local name, e.g. `CommonClassAMember`, `CapitalClassCMember`), empty when the filing tagged only an undimensioned figure; `tagged_total` cell `true`/`false`.
  - Member labels phase 2 can rely on: a single class-axis member's local name (`CommonClassAMember`); for a context with a class axis **and** a tracking-group axis (`instance.GROUP_AXES`), both members' local names in axis-name order joined by `+` (`CommonClassAMember+InteractiveGroupMember`); and the reserved `NoClassAxisMember` for an undimensioned figure that is neither the classes' total nor one of them (a class the filer tagged without an axis; rule 4 of `instance.reading`).
  - Row semantics phase 2 can rely on: `classes` may hold **one** entry (a filer that tags one class only); when `tagged_total` is false and `classes` is non-empty, `shares == sum(classes)`; when true, `classes` is non-empty and `shares` is the filer's own undimensioned total, within 0.5% of the sum; `filed >= 2009-01-01`; `filed - 200 d <= as_of <= filed + 10 d`; sorted by `(cik, filed, accession)`, unique per `(cik, accession)`; `symbol` may be empty.
  - Also: `ClassesError`, `INDEX_IDS`, `FIRST_FILED`, `member_windows`, `CompanyFacts`, `read_companyfacts`, `cover_multi_class_ciks`, `select`, `cached_index_refs`, `Built`, `row_problem`, `build_rows`, `check_rows`, `render`, `write_rows`, `add_arguments`, `run`, `download`, `build`.
- `seer_engine.shares.fetch` (additions): `INSTANCE_DIR = "xbrl-instance"`, `INSTANCE_CACHE_VERSION = 1`, `instance_path(cache, cik, accession)`, `instance_missing_path(cache, cik, accession)`, `filing_dir(ref)`, `InstanceFetch`, `fetch_instance(archive, ref)`, `instance_blob(name, facts)`, `read_instance(path) -> (name, facts)`, `read_missing(path)`, `fetch_instances(archive, cache, refs, *, workers, progress_every) -> Tally`.
- `seer_engine.shares.edgar_index` (additions): `XBRL_START = date(2009, 1, 1)`, `CLOSED_GRACE_DAYS = 7`, `quarter_end(year, quarter)`, `closed_quarters(start, today, *, grace_days)`.
- CLI: `python -m seer_engine shares download-classes --fundamentals <csv> [--cache] [--through] [--cik ...] [--workers] [--limit]` and `shares build-classes [--cache] [--through] [--cik ...] [--out]`.
- Cache layout: `<edgar cache>/xbrl-instance/<cik>/<accession>.json.gz` (versioned JSON of parsed facts) and `<accession>.missing` (reason text).
- `engine/data/SOURCES.md`: a new `shares_xbrl_classes.csv` section appended at the end of the file (format and generation; the counts, date and sha256 are left for phase 3). Phase 2 appends its `share_classes.csv` section after this one.

**Signature changes:** none. `fetch.fetch_indexes` keeps its signature (only its docstring changes).
**Requires (from earlier phases):** none.
**Leaves alone (owned by others):** `shares/history.py`, `shares/store.py`, `shares/integrate.py`,
`backtest/market.py`, `engine/data/share_classes.csv` (Phase 2); every research store, the
committed full `engine/data/shares_xbrl_classes.csv`, `shares/__init__.py` docstring,
`engine/package_readme.md`, the skill notes, the lab (Phase 3).

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/shares/instance.py` | create | pure XBRL instance reader: share facts with resolved contexts, the per-filing reading rule, the filing-index pick |
| `engine/src/seer_engine/shares/fetch.py` | modify | docstring cache list (`:11-13`), `import json` (`:35`), `instance` import (`:48`), cache constants after `END_DOC` (`:69`), path helpers before `_atomic_write` (`:114`), `fetch_indexes` docstring (`:206-209`), instance download/cache functions before `read_head` (`:308`) |
| `engine/src/seer_engine/shares/edgar_index.py` | modify | docstring paragraph (`:21`), `XBRL_START` / `CLOSED_GRACE_DAYS` after `HORIZON_END` (`:39`), `quarter_end` / `closed_quarters` before `index_url` (`:80`) |
| `engine/src/seer_engine/shares/classes.py` | create | selection, cache -> rows, the csv writer/reader and `ClassRow`, the two CLI actions |
| `engine/src/seer_engine/commands/shares.py` | modify | docstring (`:25`), register `classes.add_arguments` (`:69`), route the two actions in `run` (`:72-75`) |
| `engine/data/SOURCES.md` | modify | append the `shares_xbrl_classes.csv` section after `:470` (end of file) |
| `engine/tests/test_shares_instance.py` | create | reader tests on a trimmed real Meta 2014 instance and Berkshire-shaped default-namespace documents |
| `engine/tests/test_shares_classes.py` | create | closed quarters, download against a fake Archives session, selection, cache -> rows -> csv, invariants, CLI wiring |

## Implementation Steps

### Step 0: Worktree venv
**File:** none (environment)
**Change:** the worktree has no `engine/.venv`. Create it before running anything:
```bash
cd /home/miftah/.worktrees/seer/multi-class-company-size
python3.11 -m venv engine/.venv && engine/.venv/bin/pip install -e 'engine[dev]'
```
(The planner already created it once; re-run only if it is missing.) `defusedxml` is **not** a
dependency (`engine/pyproject.toml`) and none is added: the reader uses `xml.etree.iterparse`,
with the reasons in its docstring.
**Impact:** none on the tree.

### Step 1: The pure instance reader
**File:** `engine/src/seer_engine/shares/instance.py` (new)
**Change:** create the module. `parse` streams the instance with `iterparse`, keeps only the
cover (`dei:EntityCommonStockSharesOutstanding`) and balance-sheet
(`us-gaap:CommonStockSharesOutstanding`) facts, matched by namespace-URI path segment and local
name, and resolves each fact's context (instant, entity identifier, explicit members by local
name, typed-member flag) at the end, since contexts may follow facts. `reading` applies the
documented rule (filer's own facts; no dimension, a single class axis, or a class axis plus one
tracking-group axis whose label keeps both member names joined by `+`; cover tag before
balance-sheet tag; each class at its newest instant, stale comparatives dropped; tagged total
when within 0.5%; an undimensioned figure equal to one class is that class tagged twice and is
dropped; any other undimensioned figure is a class tagged without an axis, counted under
`NO_AXIS_MEMBER`; either way the figure is reported in `set_aside`).
`instance_name` picks the instance from a filing's `index.json` listing (`_htm.xml` inline first,
then the file named after the `.xsd`, then a sole candidate after linkbases and EDGAR's rendered
`R*.xml` / `defnref.xml` / `FilingSummary.xml` are removed — the 2011 Berkshire 10-K lists 85
`R*.xml` beside its instance).
**Code:**
```python
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
```
**Impact:** new module, imported only by `fetch` and `classes`.

### Step 2: Quarters past 2010, closed ones only
**File:** `engine/src/seer_engine/shares/edgar_index.py`
**Change:** three insertions; nothing existing changes (`quarters()` defaults, `windows`,
`select`, `FORMS`, `INDEX_ID` are untouched, so the cover pipeline and its tests are unaffected).

(a) Module docstring — insert after line 21 (`horizon runs two years past ...`), before the blank
line and `Pure: no network, clock or database.`:
```python

**Past 2010** (``shares.classes``, the per-class XBRL reader) the quarters run from
:data:`XBRL_START` to the last *closed* one (:func:`closed_quarters`): EDGAR keeps appending to the
current quarter's master index until the quarter is over, and the downloader caches an index
once and never asks again, so an open quarter's index would hide every filing made after it was
fetched.
```

(b) After line 39 (`HORIZON_END = date(2010, 12, 31)`):
```python

#: First filing date the per-class XBRL reader looks at: the dei cover tag starts with the large
#: accelerated filers' fiscal-2009 reports.
XBRL_START = date(2009, 1, 1)

#: Days after a quarter ends before its master index is treated as final: a filing accepted on
#: the quarter's last evening is disseminated, and indexed, the next business day.
CLOSED_GRACE_DAYS = 7
```

(c) Before `def index_url(` (line 80):
```python
def quarter_end(year: int, quarter: int) -> date:
    """The last day of ``quarter`` (1-4) of ``year``."""
    if quarter == 4:
        return date(year, 12, 31)
    return date(year, 3 * quarter + 1, 1) - timedelta(days=1)


def closed_quarters(start: date, today: date, *, grace_days: int = CLOSED_GRACE_DAYS) -> list[tuple[int, int]]:
    """Every (year, quarter) from ``start``'s through the last one closed on ``today``.

    A quarter is closed once ``grace_days`` have passed since its last day (module docstring);
    empty when none has closed since ``start``.
    """
    y, q = today.year, (today.month - 1) // 3 + 1
    while quarter_end(y, q) + timedelta(days=grace_days) >= today:
        y, q = (y - 1, 4) if q == 1 else (y, q - 1)
    last = quarter_end(y, q)
    return quarters(start, last) if last >= start else []


```
(`timedelta` is already imported at line 31.) `today` is a parameter, so the module stays pure.
**Impact:** additive. On 2026-10-18 `closed_quarters(XBRL_START, today)` is 2009Q1..2026Q3 (71
quarters); 2009Q1..2010Q4 are already in the real cache, so a first real run downloads 63 indexes.

### Step 3: Instance download and cache
**File:** `engine/src/seer_engine/shares/fetch.py`
**Change:** additive; the cover-head and companyconcept paths are untouched.

(a) Module docstring, replace lines 11-13 (the `xbrl/<cik>.json` bullet) with that bullet plus a
new one:
```python
* ``xbrl/<cik>.json`` -- ``data.sec.gov`` ``companyconcept`` for
  ``dei:EntityCommonStockSharesOutstanding``, the 2009+ overlap the parser is checked against;
  ``<cik>.missing`` when the filer never tagged it.
* ``xbrl-instance/<cik>/<accession>.json.gz`` -- the share-count facts of a 2009+ filing's own
  XBRL instance (``shares.instance``), for the per-class csv (``shares.classes``). Only the parsed
  facts are kept, never the instance: the cover facts sit at the end of a 1-4 MB document, so the
  whole of it is downloaded (gzip on the wire, ~60 KB for Meta's 1.2 MB) and parsed in memory.
  ``<accession>.missing`` holds the reason a filing gave none (no filing index, no instance file,
  an unreadable instance), so a re-run does not ask again.
```

(b) Imports: line 35-36 becomes
```python
import gzip
import json
import logging
```
and line 48 becomes
```python
from seer_engine.shares import edgar_index, instance
```
(`instance` imports nothing from `fetch`, so there is no cycle.)

(c) After line 69 (`END_DOC = b"</DOCUMENT>"`):
```python
#: Cache directory of the per-class instance facts, and the version of their JSON layout
#: (``instance.Fact.to_json``); a file of another version is refused, never misread.
INSTANCE_DIR = "xbrl-instance"
INSTANCE_CACHE_VERSION = 1
```

(d) Before `def _atomic_write(` (line 114):
```python
def instance_path(cache: Path, cik: str, accession: str) -> Path:
    return cache / INSTANCE_DIR / cik / f"{accession}.json.gz"


def instance_missing_path(cache: Path, cik: str, accession: str) -> Path:
    return cache / INSTANCE_DIR / cik / f"{accession}.missing"


def filing_dir(ref: FilingRef) -> str:
    """The filing's Archives directory, relative to :data:`ARCHIVES`:
    ``edgar/data/1326801/0001326801-14-000032.txt`` -> ``edgar/data/1326801/000132680114000032/``."""
    parent, _, _ = ref.path.rpartition("/")
    return f"{parent}/{ref.accession.replace('-', '')}/"


```

(e) `fetch_indexes` docstring, lines 206-209, becomes:
```python
    """Every wanted-form filing of the horizon's quarters, downloading indexes not yet cached.

    A quarter that is still open on EDGAR (the current one) would change after caching, so
    callers pass only closed quarters: the cover horizon ends in 2010, and the per-class reader
    asks ``edgar_index.closed_quarters``.
    """
```

(f) Before `def read_head(` (line 308):
```python
@dataclass(frozen=True)
class InstanceFetch:
    """What one filing's instance gave: its file name and share facts, or why there are none."""

    name: str
    facts: tuple[instance.Fact, ...] | None
    size: int = 0
    reason: str = ""


def fetch_instance(archive: Archive, ref: FilingRef) -> InstanceFetch:
    """The filing's index, then its instance, parsed (two requests; module docstring).

    Raises :class:`FetchError` only for what a retry may fix (the network, SEC's rate block);
    a filing that has no instance, or whose instance is unreadable, answers with a reason.
    """
    base = ARCHIVES + filing_dir(ref)
    listing = archive.get(base + "index.json")
    if listing is None:
        return InstanceFetch("", None, reason="no filing index")
    try:
        name = instance.instance_name(instance.filing_files(listing))
    except instance.InstanceError as exc:
        return InstanceFetch("", None, reason=f"bad filing index: {exc}")
    if name is None:
        return InstanceFetch("", None, reason="no XBRL instance")
    body = archive.get(base + name)
    if body is None:
        return InstanceFetch(name, None, reason=f"{name} not found")
    try:
        facts = instance.parse(body)
    except instance.InstanceError as exc:
        return InstanceFetch(name, None, len(body), reason=f"{name} unreadable: {exc}")
    return InstanceFetch(name, tuple(facts), len(body))


def instance_blob(name: str, facts: Sequence[instance.Fact]) -> bytes:
    """The cache file for one filing's facts: versioned JSON, gzipped."""
    doc = {"version": INSTANCE_CACHE_VERSION, "instance": name, "facts": [f.to_json() for f in facts]}
    text = json.dumps(doc, sort_keys=True, separators=(",", ":"))
    return gzip.compress(text.encode("utf-8"), compresslevel=6)


def read_instance(path: Path) -> tuple[str, tuple[instance.Fact, ...]]:
    """A cached filing's (instance file name, share facts)."""
    try:
        doc = json.loads(gzip.decompress(path.read_bytes()).decode("utf-8"))
    except (OSError, ValueError) as exc:
        raise instance.InstanceError(f"{path}: unreadable cache file: {exc}") from exc
    if not isinstance(doc, dict) or doc.get("version") != INSTANCE_CACHE_VERSION:
        raise instance.InstanceError(f"{path}: not a version-{INSTANCE_CACHE_VERSION} cache file")
    facts = doc.get("facts")
    if not isinstance(facts, list):
        raise instance.InstanceError(f"{path}: no facts list")
    return str(doc.get("instance", "")), tuple(instance.Fact.from_json(f) for f in facts)


def read_missing(path: Path) -> str:
    """The reason a ``.missing`` marker records."""
    return path.read_text(encoding="utf-8").strip() or "missing"


def fetch_instances(archive: Archive, cache: Path, refs: Sequence[FilingRef], *,
                    workers: int = WORKERS, progress_every: int = 500) -> Tally:
    """Download and parse the instance of every ref not yet cached (module docstring).

    A filing made jointly by several wanted filers is fetched once and cached under each.
    """
    by_acc: dict[str, list[FilingRef]] = {}
    for ref in refs:
        group = by_acc.setdefault(ref.accession, [])
        if all(r.cik != ref.cik for r in group):
            group.append(ref)
    tally = Tally(wanted=len(by_acc))
    todo: list[list[FilingRef]] = []
    for acc, group in by_acc.items():
        if all(instance_path(cache, r.cik, acc).exists()
               or instance_missing_path(cache, r.cik, acc).exists() for r in group):
            tally.cached += 1
        else:
            todo.append(group)
    log.info("edgar: %d instances wanted, %d cached, %d to fetch", tally.wanted, tally.cached, len(todo))
    t0 = time.monotonic()

    def one(group: list[FilingRef]) -> tuple[list[FilingRef], InstanceFetch]:
        return group, fetch_instance(archive, group[0])

    done = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(one, group) for group in todo]
        for fut in as_completed(futures):
            try:
                group, got = fut.result()
            except FetchError as exc:
                tally.failed.append(str(exc))
                continue
            for r in group:
                if got.facts is None:
                    _atomic_write(instance_missing_path(cache, r.cik, r.accession),
                                  (got.reason + "\n").encode("utf-8"))
                else:
                    _atomic_write(instance_path(cache, r.cik, r.accession),
                                  instance_blob(got.name, got.facts))
            if got.facts is None:
                tally.missing += 1
            else:
                tally.fetched += 1
                tally.bytes_raw += got.size
            done += 1
            if done % progress_every == 0:
                rate = done / max(1e-9, time.monotonic() - t0)
                log.info("edgar: %d/%d instances (%.1f/s, eta %.0f min)", done, len(todo), rate,
                         (len(todo) - done) / max(rate, 1e-9) / 60)
    tally.seconds = time.monotonic() - t0
    return tally
```
**Impact:** additive. Each wanted filing costs two paced requests (its `index.json`, then the
instance); `Archive.get` already sends `Accept-Encoding: gzip`, which SEC honours for `.xml`
(Meta's 1,178,188-byte instance arrives as 61,018 bytes). Parsing runs in the worker threads
(~10 ms per instance measured), well under the 0.12 s request spacing.

### Step 4: Selection, cache -> rows, the csv, the CLI actions
**File:** `engine/src/seer_engine/shares/classes.py` (new)
**Change:** create the module.
- `member_windows` calls `edgar_index.windows` once per index id in `("SP500", "NDX")` with
  `horizon_start=2009-01-01, horizon_end=through` and merges per CIK.
- `read_companyfacts` scans the dev store's `fundamentals.csv` read-only: the accessions with a
  positive `EntityCommonStockSharesOutstanding` value, and the filers with several values for
  one (symbol, accession, period) (none in today's dev store; kept because the index's selection
  names it and it costs nothing).
- `select` = window filter + (no cover count for the accession, **or** a multi-class filer: any
  pre-2010 cover row lists classes — 88 filers today — or the companyfacts multi-value rule,
  **or** a filer named with `--cik`, whose every member filing is read). Phase 3 passes every CIK
  of phase 2's `engine/data/share_classes.csv` as `--cik` (Alphabet 0001652044, Fox Corp
  0001754301 and Liberty Media 0001560385 have no pre-2010 cover rows, so nothing else selects
  their counted filings); this module never reads that file.
  Measured on the dev store: 2,646 of its 34,771 10-K/10-Q accessions lack a cover count, and
  filings of filers absent from the dev store add to that, so a full run is in the order of
  5,000-10,000 filings, ~2 requests each at 8.3 req/s, roughly 30-45 minutes.
- `build_rows` does **not** re-run the companyfacts selection: it reads every in-window member
  filing whose instance is cached, so the csv depends only on the cache and the vendored maps.
  A row that fails the per-row invariants (`row_problem`, e.g. `as_of` more than 200 days
  before filing) is dropped and counted, never written.
- `symbol` comes from `build.symbol_for(build.tenures(index)[cik], filed)` — the same rule as the
  cover csv.
**Code:**
```python
"""Per-class share counts from the filings' own XBRL instances, 2009-today: the vendored csv.

Why this exists. The stores' 2009+ share counts come from SEC's ``companyfacts`` API, which drops
every dimensional fact (``shares.instance``), so a filer that tags its cover count once per share
class has none: Meta, Visa, Mastercard, Alphabet from 2014. Those filings are read again from
their own instance documents and the result is committed as
``engine/data/shares_xbrl_classes.csv`` (documented in ``SOURCES.md``), exactly as the cover-page
history is: nothing at backtest or paper time reads the cache or the network.

**Which filings** (:func:`select`). Every 10-K/10-Q (``edgar_index.FORMS``) filed by the filer
behind an S&P 500 *or* Nasdaq-100 member, from ``edgar_index.LEAD_DAYS`` before its first member
day to its last, from 2009-01-01 (:data:`edgar_index.XBRL_START`) through the last closed quarter,
that either

* has no positive ``dei:EntityCommonStockSharesOutstanding`` for its accession in the dev store's
  ``fundamentals.csv`` (Meta, Visa, Alphabet 2011-2014, and the smaller filers whose cover tag
  companyfacts never carried), or
* was filed by a filer with more than one class: its pre-2010 cover rows list classes
  (Berkshire, Comcast, Ford, Brown-Forman, ...), or companyfacts gave several values for one
  accession and period, or
* was filed by a filer named with ``--cik``: a sample run, and the class table's filers
  (``engine/data/share_classes.csv``), whose every filing is wanted because a companyfacts figure
  cannot be split by class. This module does not read the class table; the store-refresh recipe
  (``docs/runbooks/data-pipeline.md``) passes its filers as ``--cik``.

The Nasdaq-100 is included because the lab sizes its members too; ``edgar_index.windows`` takes
one index, so the two are merged per filer (:func:`member_windows`; a filer that left one index
and joined the other later is wanted across the gap, which costs a few requests and nothing
else). Only closed quarters' master indexes are read (``edgar_index`` module docstring).

``build-classes`` does not re-run that selection: it reads every member filing in the windows
whose instance is in the cache, so the csv depends only on the cache and the vendored maps, not
on whichever ``fundamentals.csv`` the download was steered by.

**The row** (:class:`ClassRow`): ``cik,symbol,filed,as_of,form,accession,shares,classes,
tagged_total``, sorted by (cik, filed, accession). ``filed`` is the master index's filing date
and the **only** availability date, as in the cover csv; ``as_of`` is the context instant the
filer counted on. ``classes`` is ``member=count;...`` by the XBRL member's local name
(``CommonClassAMember``), sorted, empty when the filing tagged only an undimensioned figure.
``shares`` is that figure, or the classes summed one for one, or -- ``tagged_total`` true -- the
undimensioned total the filer tagged beside its classes (within half a percent of their sum).
One for one is the *filing's* arithmetic only: which listed symbol each class trades as, and at
what ratio (a Berkshire A share is 1,500 B), is the share history's business, not this file's.
``symbol`` is the ticker the filer traded as on the filing date (empty with no tenure covering it).

``download-classes`` is the network edge (``fetch.fetch_instances``); ``build-classes`` reads only
local files and rewrites the csv.
"""

from __future__ import annotations

import argparse
import csv
import io
import logging
import math
import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from seer_engine import cik as cikmod
from seer_engine import membership, sec
from seer_engine.cik import CikError
from seer_engine.shares import build as cover_build
from seer_engine.shares import edgar_index, fetch, history, instance
from seer_engine.shares.edgar_index import FilingRef, Window

log = logging.getLogger(__name__)

DATA_DIR = history.DATA_DIR
CLASSES_FILE = "shares_xbrl_classes.csv"

HEADER: tuple[str, ...] = (
    "cik", "symbol", "filed", "as_of", "form", "accession", "shares", "classes", "tagged_total",
)

#: The indexes whose members' filers are read (module docstring).
INDEX_IDS: tuple[str, ...] = ("SP500", "NDX")

#: Filing dates the csv may hold start here (``edgar_index.XBRL_START``).
FIRST_FILED = edgar_index.XBRL_START
#: ``as_of`` bounds relative to ``filed``, the cover csv's (``history.AS_OF_MAX_AGE`` / ``_LEAD``).
AS_OF_MAX_AGE = history.AS_OF_MAX_AGE
AS_OF_MAX_LEAD = history.AS_OF_MAX_LEAD

_BOOL = {"true": True, "false": False}


class ClassesError(ValueError):
    """The per-class csv, or an input to it, is inconsistent."""


@dataclass(frozen=True)
class ClassRow:
    """One filing's share count from its XBRL instance (module docstring for every field)."""

    cik: str
    symbol: str
    filed: date
    as_of: date
    form: str
    accession: str
    shares: int
    classes: tuple[tuple[str, int], ...]
    tagged_total: bool


# --- which filings ------------------------------------------------------------------------


def member_windows(
    intervals: Sequence[membership.Interval],
    index: Mapping[str, Sequence[cikmod.CikRow]],
    *,
    end: date,
    start: date = FIRST_FILED,
    index_ids: Sequence[str] = INDEX_IDS,
) -> dict[str, Window]:
    """Per filer CIK, the filing-date window of :data:`INDEX_IDS` membership, merged.

    ``edgar_index.windows`` per index, clipped to ``[start, end]``; a filer in both gets the
    earlier start, the later end and both indexes' symbols.
    """
    merged: dict[str, Window] = {}
    for index_id in index_ids:
        wins = edgar_index.windows(intervals, index, index_id=index_id,
                                   horizon_start=start, horizon_end=end)
        for key, w in wins.items():
            prev = merged.get(key)
            merged[key] = w if prev is None else Window(
                key, min(prev.start, w.start), max(prev.end, w.end),
                tuple(sorted(set(prev.symbols) | set(w.symbols))),
            )
    return dict(sorted(merged.items()))


@dataclass(frozen=True)
class CompanyFacts:
    """What the selection needs from a store's ``fundamentals.csv``."""

    dei_accessions: frozenset[str]  # accessions with a positive cover count
    multi_value_ciks: frozenset[str]  # filers with several cover values for one accession+period


def read_companyfacts(path: Path, index: Mapping[str, Sequence[cikmod.CikRow]]) -> CompanyFacts:
    """The cover-count accessions of a ``fundamentals.csv`` (read-only), and its multi-class filers.

    A symbol is turned into its filer through the date-scoped ticker map on the fact's filing
    date; a symbol the map cannot place on that day is left out of the multi-class set (its
    filings are still judged by their accessions).
    """
    accessions: set[str] = set()
    values: dict[tuple[str, str, str], tuple[str, set[float]]] = {}
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        need = {"symbol", "tag", "val", "accn", "period_end", "filed"}
        lacking = need - set(reader.fieldnames or ())
        if lacking:
            raise ClassesError(f"{path}: not a fundamentals.csv (no {', '.join(sorted(lacking))})")
        for raw in reader:
            if raw["tag"] != instance.COVER_TAG:
                continue
            try:
                val = float(raw["val"])
            except ValueError:
                continue
            if not (math.isfinite(val) and val > 0):
                continue
            accessions.add(raw["accn"])
            key = (raw["symbol"], raw["accn"], raw["period_end"])
            values.setdefault(key, (raw["filed"], set()))[1].add(val)
    multi: set[str] = set()
    for (symbol, _accn, _end), (filed, vals) in values.items():
        if len(vals) < 2:
            continue
        try:
            multi.add(cikmod.resolve(symbol, date.fromisoformat(filed), index))
        except (CikError, ValueError):
            continue
    return CompanyFacts(frozenset(accessions), frozenset(multi))


def cover_multi_class_ciks(rows: Iterable[history.ShareRow]) -> frozenset[str]:
    """Filers any of whose pre-2010 cover rows lists more than one class."""
    return frozenset(r.cik for r in rows if r.classes)


def select(
    refs: Iterable[FilingRef],
    wins: Mapping[str, Window],
    facts: CompanyFacts,
    multi_class: frozenset[str],
) -> list[FilingRef]:
    """The member filings whose instance is wanted (module docstring), sorted by (cik, filed)."""
    return [
        r for r in edgar_index.select(refs, wins)
        if r.cik in multi_class or r.accession not in facts.dei_accessions
    ]


def cached_index_refs(cache: Path, through: date) -> list[FilingRef]:
    """The periodic reports of every closed quarter 2009..``through``, from cached indexes only."""
    refs: list[FilingRef] = []
    for y, q in edgar_index.closed_quarters(FIRST_FILED, through):
        p = fetch.index_path(cache, y, q)
        if not p.exists():
            raise ClassesError(f"{p} missing; run `shares download-classes` first")
        refs.extend(edgar_index.read_master_gz(p.read_bytes()))
    return refs


# --- cache -> rows ------------------------------------------------------------------------


@dataclass
class Built:
    """What :func:`build_rows` read: the rows, and a count of every filing that gave none."""

    rows: list[ClassRow] = field(default_factory=list)
    skipped: Counter[str] = field(default_factory=Counter)
    balance_sheet: int = 0  # rows read from the us-gaap fallback tag
    set_aside: list[tuple[ClassRow, int]] = field(default_factory=list)


def row_problem(row: ClassRow) -> str | None:
    """Why a row may not be written, or None: the per-row invariants of :func:`check_rows`."""
    if len(row.cik) != 10 or not row.cik.isdigit():
        return f"cik must be 10 digits, got {row.cik!r}"
    parts = row.accession.split("-")
    if len(parts) != 3 or [len(p) for p in parts] != [10, 2, 6] or not all(p.isdigit() for p in parts):
        return f"bad accession {row.accession!r}"
    if row.form not in edgar_index.FORMS:
        return f"form {row.form!r} is not a periodic report"
    if row.filed < FIRST_FILED:
        return f"filed {row.filed} before {FIRST_FILED}"
    if not (row.filed - timedelta(days=AS_OF_MAX_AGE) <= row.as_of
            <= row.filed + timedelta(days=AS_OF_MAX_LEAD)):
        return f"as_of {row.as_of} too far from filed {row.filed}"
    if row.shares <= 0:
        return "shares must be positive"
    members = [m for m, _ in row.classes]
    if members != sorted(set(members)):
        return "classes must be sorted by member, each once"
    for m, n in row.classes:
        if not m or any(ch in m for ch in "=;,\"") or n <= 0:
            return f"bad class entry {m!r}={n!r}"
    class_sum = sum(n for _, n in row.classes)
    if row.tagged_total:
        if not row.classes:
            return "a tagged total needs its classes"
        if abs(row.shares - class_sum) > instance.TOTAL_TOL * class_sum:
            return f"tagged total {row.shares} is not the classes' sum {class_sum}"
    elif row.classes and row.shares != class_sum:
        return f"classes sum to {class_sum}, shares is {row.shares}"
    return None


def build_rows(
    cache: Path,
    refs: Iterable[FilingRef],
    tenures: Mapping[str, Sequence[cikmod.CikRow]],
) -> Built:
    """One row per (filer, filing) among ``refs`` whose cached instance states a count."""
    out = Built()
    seen: set[tuple[str, str]] = set()
    for ref in refs:
        key = (ref.cik, ref.accession)
        if key in seen:
            continue
        seen.add(key)
        path = fetch.instance_path(cache, ref.cik, ref.accession)
        if not path.exists():
            miss = fetch.instance_missing_path(cache, ref.cik, ref.accession)
            out.skipped[f"on EDGAR without a count: {fetch.read_missing(miss)}"
                        if miss.exists() else "not downloaded"] += 1
            continue
        try:
            _name, facts = fetch.read_instance(path)
        except instance.InstanceError as exc:
            out.skipped[f"unreadable cache file ({exc})"] += 1
            continue
        got = instance.reading(facts, ref.cik)
        if got is None:
            out.skipped["the instance states no count for the filer"] += 1
            continue
        row = ClassRow(
            cik=ref.cik,
            symbol=cover_build.symbol_for(tenures.get(ref.cik, ()), ref.filed),
            filed=ref.filed,
            as_of=got.as_of,
            form=ref.form,
            accession=ref.accession,
            shares=got.shares,
            classes=got.classes,
            tagged_total=got.tagged_total,
        )
        problem = row_problem(row)
        if problem is not None:
            out.skipped["dropped: " + re.sub(r"\d[\d-]*", "N", problem)] += 1
            log.info("classes: %s %s dropped: %s", ref.cik, ref.accession, problem)
            continue
        if got.tag == instance.BALANCE_TAG:
            out.balance_sheet += 1
        if got.set_aside is not None:
            out.set_aside.append((row, got.set_aside))
        out.rows.append(row)
    out.rows.sort(key=lambda r: (r.cik, r.filed, r.accession))
    return out


# --- the csv ------------------------------------------------------------------------------


def _date(raw: str, where: str) -> date:
    try:
        return date.fromisoformat((raw or "").strip())
    except ValueError as exc:
        raise ClassesError(f"{where}: bad date {raw!r}") from exc


def check_rows(rows: Sequence[ClassRow], name: str = CLASSES_FILE) -> None:
    """The csv invariants: at least one row; sorted by (cik, filed, accession) and unique per
    (cik, accession); every row passing :func:`row_problem`."""
    if not rows:
        raise ClassesError(f"{name}: no rows")
    seen: set[tuple[str, str]] = set()
    prev: tuple[str, date, str] | None = None
    for i, r in enumerate(rows, start=2):
        where = f"{name}:{i}"
        key = (r.cik, r.filed, r.accession)
        if prev is not None and key < prev:
            raise ClassesError(f"{where}: rows must be sorted by (cik, filed, accession)")
        prev = key
        if (r.cik, r.accession) in seen:
            raise ClassesError(f"{where}: duplicate {r.cik} {r.accession}")
        seen.add((r.cik, r.accession))
        problem = row_problem(r)
        if problem is not None:
            raise ClassesError(f"{where}: {problem}")


def render(rows: Iterable[ClassRow]) -> str:
    """The csv text of ``rows`` (sorted, checked)."""
    ordered = sorted(rows, key=lambda r: (r.cik, r.filed, r.accession))
    check_rows(ordered)
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(HEADER)
    for r in ordered:
        w.writerow([
            r.cik, r.symbol, r.filed.isoformat(), r.as_of.isoformat(), r.form, r.accession,
            r.shares, history.format_classes(r.classes), "true" if r.tagged_total else "false",
        ])
    return buf.getvalue()


def write_rows(path: Path, rows: Iterable[ClassRow]) -> int:
    """Rewrite ``path`` with ``rows`` atomically; the number written."""
    text = render(rows)
    fetch._atomic_write(path, text.encode("utf-8"))
    return text.count("\n") - 1


def load_rows(path: Path) -> list[ClassRow]:
    """Read and validate the vendored csv (invariants in :func:`check_rows`)."""
    rows: list[ClassRow] = []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if tuple(reader.fieldnames or ()) != HEADER:
            raise ClassesError(f"{path}: expected header {','.join(HEADER)}, got {reader.fieldnames}")
        for lineno, raw in enumerate(reader, start=2):
            where = f"{path.name}:{lineno}"
            shares_text = (raw["shares"] or "").strip()
            if not shares_text.isdigit():
                raise ClassesError(f"{where}: shares must be a positive integer, got {shares_text!r}")
            flag = (raw["tagged_total"] or "").strip()
            if flag not in _BOOL:
                raise ClassesError(f"{where}: tagged_total must be true or false, got {flag!r}")
            try:
                classes = history.parse_classes(raw["classes"], where)
            except history.SharesError as exc:
                raise ClassesError(str(exc)) from exc
            rows.append(ClassRow(
                cik=(raw["cik"] or "").strip(),
                symbol=(raw["symbol"] or "").strip(),
                filed=_date(raw["filed"], where),
                as_of=_date(raw["as_of"], where),
                form=(raw["form"] or "").strip(),
                accession=(raw["accession"] or "").strip(),
                shares=int(shares_text),
                classes=classes,
                tagged_total=_BOOL[flag],
            ))
    check_rows(rows, path.name)
    return rows


# --- the CLI ------------------------------------------------------------------------------


def add_arguments(sub) -> None:
    d = sub.add_parser("download-classes",
                       help="fetch the XBRL instances of member filings that lack a per-class count (network)")
    d.add_argument("--cache", type=Path, default=None,
                   help="cache dir (default $SEER_EDGAR_CACHE or engine/.cache/edgar)")
    d.add_argument("--fundamentals", type=Path, required=True,
                   help="the dev store's fundamentals.csv (read-only): filings it already counts "
                        "are skipped unless their filer has several classes")
    d.add_argument("--through", type=date.fromisoformat, default=None, metavar="YYYY-MM-DD",
                   help="read the quarters closed by this day (default today)")
    d.add_argument("--cik", action="append", default=[],
                   help="only this filer, and every one of its member filings whether or not "
                        "companyfacts counts it (repeatable): a sample, or the class table's filers")
    d.add_argument("--workers", type=int, default=fetch.WORKERS)
    d.add_argument("--limit", type=int, default=0, help="fetch at most this many filings (0 = all)")

    b = sub.add_parser("build-classes",
                       help="rewrite the per-class csv from the cached instances (no network)")
    b.add_argument("--cache", type=Path, default=None,
                   help="cache dir (default $SEER_EDGAR_CACHE or engine/.cache/edgar)")
    b.add_argument("--through", type=date.fromisoformat, default=None, metavar="YYYY-MM-DD",
                   help="read the quarters closed by this day (default today)")
    b.add_argument("--cik", action="append", default=[],
                   help="only this filer (repeatable), for a sample")
    b.add_argument("--out", type=Path, default=DATA_DIR / CLASSES_FILE,
                   help="the csv to write (default engine/data/shares_xbrl_classes.csv)")


def run(args: argparse.Namespace) -> int:
    if args.action == "download-classes":
        return download(args)
    return build(args)


def _cache(args: argparse.Namespace) -> Path:
    from seer_engine.commands.shares import default_cache

    return args.cache or default_cache()


def _only(raw: Sequence[str]) -> frozenset[str]:
    return frozenset(cikmod.normalize_cik(c, "--cik") for c in raw)


def _windows(args: argparse.Namespace, through: date) -> tuple[dict[str, Window], Mapping[str, Sequence[cikmod.CikRow]]]:
    universe = membership.compute_universe(membership.DATA_DIR)
    index = cikmod.load_index_with_history(cikmod.DATA_DIR)
    wins = member_windows(universe, index, end=through)
    only = _only(args.cik)
    if only:
        wins = {k: v for k, v in wins.items() if k in only}
    return wins, index


def download(args: argparse.Namespace) -> int:
    cache = _cache(args)
    through: date = args.through or date.today()
    wins, index = _windows(args, through)
    facts = read_companyfacts(args.fundamentals, index)
    multi = cover_multi_class_ciks(history.load_rows(history.DATA_DIR / history.SHARES_FILE))
    # A filer named with --cik is read in full (module docstring).
    multi |= facts.multi_value_ciks | _only(args.cik)
    archive = fetch.Archive(sec.require_contact())
    refs = fetch.fetch_indexes(archive, cache, edgar_index.closed_quarters(FIRST_FILED, through))
    in_windows = edgar_index.select(refs, wins)
    wanted = select(refs, wins, facts, multi)
    print(f"shares download-classes: {len(wins)} filers, {len(in_windows)} member filings "
          f"{FIRST_FILED}..{through}; {len(wanted)} wanted ({sum(r.cik in multi for r in wanted)} "
          f"of filers with several classes or named with --cik, the rest lacking a cover count in "
          f"{args.fundamentals.name})")
    if args.limit:
        wanted = wanted[: args.limit]
    if getattr(args, "dry_run", False):
        print("dry run: nothing fetched beyond the indexes")
        return 0
    t = fetch.fetch_instances(archive, cache, wanted, workers=args.workers)
    print(f"instances: {t.wanted} wanted, {t.cached} already cached, {t.fetched} fetched "
          f"({t.bytes_raw / 1e6:.0f} MB of XML), {t.missing} without a count on EDGAR, "
          f"{len(t.failed)} failed, {t.seconds / 60:.1f} min; {archive.calls} requests")
    for line in t.failed[:20]:
        print("  failed: " + line)
    return 1 if t.failed else 0


def build(args: argparse.Namespace) -> int:
    cache = _cache(args)
    through: date = args.through or date.today()
    wins, index = _windows(args, through)
    try:
        refs = cached_index_refs(cache, through)
    except ClassesError as exc:
        print(f"shares build-classes: {exc}")
        return 1
    in_windows = edgar_index.select(refs, wins)
    built = build_rows(cache, in_windows, cover_build.tenures(index))
    multi = sum(1 for r in built.rows if r.classes)
    print(f"shares build-classes: {len(in_windows)} member filings {FIRST_FILED}..{through}; "
          f"{len(built.rows)} rows from {len({r.cik for r in built.rows})} filers ({multi} with "
          f"classes, {sum(r.tagged_total for r in built.rows)} with a tagged total, "
          f"{built.balance_sheet} from the balance-sheet tag)")
    for why, n in built.skipped.most_common():
        print(f"  no row: {n:>6}  {why}")
    for row, figure in built.set_aside:  # every one: phase 3 reviews them all
        how = ("counted as a class without an axis" if any(m == instance.NO_AXIS_MEMBER for m, _ in row.classes)
               else "dropped as a class tagged twice")
        print(f"  set aside: {row.cik} {row.symbol or '-'} {row.accession} undimensioned "
              f"{figure} {how}; count {row.shares}")
    if not built.rows:
        print("no rows; nothing written")
        return 1
    if getattr(args, "dry_run", False):
        print(f"dry run: {args.out} not written")
        return 0
    n = write_rows(args.out, built.rows)
    print(f"wrote {n} rows to {args.out}")
    return 0
```
**Impact:** new module. It imports `shares.build` (for `symbol_for` / `tenures`), which imports
nothing from `classes`, so there is no cycle. `fetch._atomic_write` is reused for the csv write
(same package; the cover csv's `history.write_rows` writes in place, this one atomically).

### Step 5: Wire the subcommand
**File:** `engine/src/seer_engine/commands/shares.py`
**Change:**

(a) Module docstring: after line 25 (`` ``store`` carries every other store file byte for byte, so the price fingerprint never moves. ``), before the closing `"""` on line 26, insert:
```python

``download-classes`` and ``build-classes`` add the 2009+ counts ``companyfacts`` cannot give:
filers that tag their cover count once per share class (Meta, Visa, Alphabet from 2014). The
first fetches each such filing's XBRL instance into the same cache (network, resumable; needs
``SEC_CONTACT_EMAIL``), the second rewrites ``engine/data/shares_xbrl_classes.csv`` from the cache
alone (``shares.classes``):

    python -m seer_engine shares download-classes --fundamentals /abs/engine/.research/fundamentals.csv
    python -m seer_engine shares build-classes
```

(b) `add_arguments`, after line 69 (`integrate.add_arguments(sub)`):
```python
    from seer_engine.shares import classes

    classes.add_arguments(sub)
```

(c) `run`, lines 72-81 become:
```python
def run(args: argparse.Namespace) -> int:
    if args.action == "download":
        return download(args)
    if args.action in ("download-classes", "build-classes"):
        from seer_engine.shares import classes

        return classes.run(args)
    if args.action in ("fetch-splits", "store", "store-report"):
        from seer_engine.shares import integrate

        return integrate.run(args)
    from seer_engine.shares import build

    return build.run(args)
```
No `%` appears in any new help string (argparse formatting is exercised by the CLI test).
**Impact:** two new actions; existing actions unchanged.

### Step 6: Document the csv
**File:** `engine/data/SOURCES.md` — append after line 470 (end of file):
```markdown

## shares_xbrl_classes.csv: shares outstanding per class from XBRL instances, 2009-today

| | |
|---|---|
| Upstream | SEC EDGAR full index `https://www.sec.gov/Archives/edgar/full-index/<YYYY>/QTR<n>/master.gz` (2009Q1 through the last closed quarter); per filing, `https://www.sec.gov/Archives/edgar/data/<cik>/<accession without dashes>/index.json` and the XBRL instance it lists (`<stem>.xml`, or `<stem>_htm.xml` for inline XBRL) |
| Generated by | `python -m seer_engine shares download-classes --fundamentals <dev store>/fundamentals.csv`, then the same with `--cik <each filer of share_classes.csv>` (network, into the gitignored `engine/.cache/edgar/xbrl-instance/`), then `python -m seer_engine shares build-classes` (no network) |
| Fetched | (set when the file is first committed) |
| Scope | every 10-K/10-Q filed by the filer behind an S&P 500 or Nasdaq-100 member (date-scoped through `cik.load_index_with_history`) from 400 days before its first member day to its last, inside 2009-01-01 .. the last closed quarter, that has no positive `dei:EntityCommonStockSharesOutstanding` for its accession in the dev store's `fundamentals.csv`, or whose filer has more than one class of common stock (classes on its pre-2010 cover rows, several companyfacts values for one filing, or a row in `share_classes.csv`); counts set when the file is first committed |
| Rows | (set when the file is first committed) |
| License | US government work, public domain (SEC) |
| sha256 | (set when the file is first committed) |

`cik,symbol,filed,as_of,form,accession,shares,classes,tagged_total`, sorted by (cik, filed,
accession). Why it exists: SEC's `companyfacts` API, the source of every store's 2009+ share
counts, drops dimensional facts, so a filer that tags its cover count once per share class (a
`StatementClassOfStockAxis` member on each fact, no undimensioned total: Meta, Visa, Mastercard,
Alphabet from 2014) has no count there at all. This file reads the same cover facts from the
filing's own instance document. `filed` is the master index's filing date and the **only**
availability date; `as_of` is the context instant the filer counted on. `classes` lists each
class as `member=count` by the XBRL member's local name (`CommonClassAMember=2015048077;
CommonClassBMember=585003514` for Meta's 10-Q of 2014-07-24), sorted, and is empty when the filing
tagged only an undimensioned figure. A tracking-stock class (a group axis beside the class axis:
Liberty Interactive, Liberty Media 2016, LiLAC) is labelled with both member names joined by `+`
(`CommonClassAMember+InteractiveGroupMember`). `shares` is that figure, or the classes summed one
for one, or, when `tagged_total` is `true`, the undimensioned total the filer tagged beside its
classes (used only when it is within 0.5% of their sum). An undimensioned figure that is not their
total is dropped when it equals one class (the class tagged twice) and otherwise counted as a
class tagged without an axis, `NoClassAxisMember`; `build-classes` prints every such figure for
review. One for one is the filing's arithmetic only: which listed symbol a
class trades as, and at what ratio (a Berkshire A share converts into 1,500 B), is decided where
the file is read, not here. The balance-sheet `us-gaap:CommonStockSharesOutstanding` is read
only from a filing that has no cover tag at all. A filing whose count is dated more than 200 days
before, or 10 days after, its filing date gets no row. `symbol` is the ticker the filer traded as
on the filing date (empty with no tenure covering it). Read by `seer_engine.shares.classes`;
nothing at backtest or paper time touches the network.
```
**Impact:** docs only. Phase 3 replaces the three "set when ..." cells and adds the measured
coverage when it commits the real csv.

### Step 7: Tests
**File:** `engine/tests/test_shares_instance.py` (new)
**Code:**
```python
"""The per-class XBRL instance reader: real instance shapes trimmed to their share facts (Meta's
2014 10-Q with its two class-axis cover facts, Berkshire's default-namespace 2011 file, a 2009
``xbrl.us`` namespace), the reading rules, the filing-index pick, and the cache round trip (no
network)."""

from __future__ import annotations

from datetime import date

import pytest

from seer_engine.shares import instance

D = date.fromisoformat
META = "0001326801"

# Meta's 10-Q of 2014-07-24 (0001326801-14-000032, fb-20140630.xml), cut to the contexts and
# facts the reader looks at plus one of each kind it must ignore. The cover facts come after the
# balance-sheet ones and after a fact citing a context declared later, as in the real file.
META_2014 = b"""<?xml version="1.0" encoding="US-ASCII"?>
<!--XBRL Document Created with Wdesk from Workiva, formerly WebFilings-->
<xbrli:xbrl xmlns:dei="http://xbrl.sec.gov/dei/2013-01-31" xmlns:fb="http://www.facebook.com/20140630" xmlns:iso4217="http://www.xbrl.org/2003/iso4217" xmlns:link="http://www.xbrl.org/2003/linkbase" xmlns:us-gaap="http://fasb.org/us-gaap/2013-01-31" xmlns:xbrldi="http://xbrl.org/2006/xbrldi" xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:xlink="http://www.w3.org/1999/xlink">
  <link:schemaRef xlink:href="fb-20140630.xsd" xlink:type="simple" />
  <xbrli:context id="FD2014Q2YTD">
    <xbrli:entity>
      <xbrli:identifier scheme="http://www.sec.gov/CIK">0001326801</xbrli:identifier>
    </xbrli:entity>
    <xbrli:period>
      <xbrli:startDate>2014-01-01</xbrli:startDate>
      <xbrli:endDate>2014-06-30</xbrli:endDate>
    </xbrli:period>
  </xbrli:context>
  <xbrli:context id="FI2014Q2_us-gaap_StatementClassOfStockAxis_us-gaap_CommonClassAMember">
    <xbrli:entity>
      <xbrli:identifier scheme="http://www.sec.gov/CIK">0001326801</xbrli:identifier>
      <xbrli:segment>
        <xbrldi:explicitMember dimension="us-gaap:StatementClassOfStockAxis">us-gaap:CommonClassAMember</xbrldi:explicitMember>
      </xbrli:segment>
    </xbrli:entity>
    <xbrli:period>
      <xbrli:instant>2014-06-30</xbrli:instant>
    </xbrli:period>
  </xbrli:context>
  <xbrli:context id="FI2014Q2_us-gaap_StatementClassOfStockAxis_us-gaap_CommonClassBMember">
    <xbrli:entity>
      <xbrli:identifier scheme="http://www.sec.gov/CIK">0001326801</xbrli:identifier>
      <xbrli:segment>
        <xbrldi:explicitMember dimension="us-gaap:StatementClassOfStockAxis">us-gaap:CommonClassBMember</xbrldi:explicitMember>
      </xbrli:segment>
    </xbrli:entity>
    <xbrli:period>
      <xbrli:instant>2014-06-30</xbrli:instant>
    </xbrli:period>
  </xbrli:context>
  <xbrli:context id="FI2013Q4_us-gaap_StatementClassOfStockAxis_us-gaap_CommonClassAMember">
    <xbrli:entity>
      <xbrli:identifier scheme="http://www.sec.gov/CIK">0001326801</xbrli:identifier>
      <xbrli:segment>
        <xbrldi:explicitMember dimension="us-gaap:StatementClassOfStockAxis">us-gaap:CommonClassAMember</xbrldi:explicitMember>
      </xbrli:segment>
    </xbrli:entity>
    <xbrli:period>
      <xbrli:instant>2013-12-31</xbrli:instant>
    </xbrli:period>
  </xbrli:context>
  <xbrli:context id="I2014Q2SharesOutstanding_us-gaap_StatementClassOfStockAxis_us-gaap_CommonClassBMember">
    <xbrli:entity>
      <xbrli:identifier scheme="http://www.sec.gov/CIK">0001326801</xbrli:identifier>
      <xbrli:segment>
        <xbrldi:explicitMember dimension="us-gaap:StatementClassOfStockAxis">us-gaap:CommonClassBMember</xbrldi:explicitMember>
      </xbrli:segment>
    </xbrli:entity>
    <xbrli:period>
      <xbrli:instant>2014-07-22</xbrli:instant>
    </xbrli:period>
  </xbrli:context>
  <xbrli:unit id="shares">
    <xbrli:measure>xbrli:shares</xbrli:measure>
  </xbrli:unit>
  <us-gaap:CommonStockSharesOutstanding contextRef="FI2014Q2_us-gaap_StatementClassOfStockAxis_us-gaap_CommonClassBMember" decimals="-6" id="Fact-5E940445BC685324D26D1AA65586EF9D" unitRef="shares">562000000</us-gaap:CommonStockSharesOutstanding>
  <us-gaap:CommonStockSharesOutstanding contextRef="FI2014Q2_us-gaap_StatementClassOfStockAxis_us-gaap_CommonClassAMember" decimals="-6" id="Fact-CD3569BC3E7A0CB67A521AA655A152E4" unitRef="shares">2013000000</us-gaap:CommonStockSharesOutstanding>
  <us-gaap:CommonStockSharesOutstanding contextRef="FI2013Q4_us-gaap_StatementClassOfStockAxis_us-gaap_CommonClassAMember" decimals="-6" id="Fact-63AA3BF9E2DFDC3FD0AB1AA6559331F8" unitRef="shares">1970000000</us-gaap:CommonStockSharesOutstanding>
  <dei:DocumentType contextRef="FD2014Q2YTD" id="Fact-7832F0FFBC2AB8405A701AA654EF855C">10-Q</dei:DocumentType>
  <dei:EntityCommonStockSharesOutstanding contextRef="I2014Q2SharesOutstanding_us-gaap_StatementClassOfStockAxis_us-gaap_CommonClassBMember" decimals="INF" id="Fact-9EDC6B302C9E595028231AA654F5CEAE" unitRef="shares">585003514</dei:EntityCommonStockSharesOutstanding>
  <dei:EntityCommonStockSharesOutstanding contextRef="I2014Q2SharesOutstanding_us-gaap_StatementClassOfStockAxis_us-gaap_CommonClassAMember" decimals="INF" id="Fact-DB1A5E8D6A4AAB1E16671AA654F366F3" unitRef="shares">2015048077</dei:EntityCommonStockSharesOutstanding>
  <xbrli:context id="I2014Q2SharesOutstanding_us-gaap_StatementClassOfStockAxis_us-gaap_CommonClassAMember">
    <xbrli:entity>
      <xbrli:identifier scheme="http://www.sec.gov/CIK">0001326801</xbrli:identifier>
      <xbrli:segment>
        <xbrldi:explicitMember dimension="us-gaap:StatementClassOfStockAxis">us-gaap:CommonClassAMember</xbrldi:explicitMember>
      </xbrli:segment>
    </xbrli:entity>
    <xbrli:period>
      <xbrli:instant>2014-07-22</xbrli:instant>
    </xbrli:period>
  </xbrli:context>
</xbrli:xbrl>
"""


def _doc(body: str, *, dei: str = "http://xbrl.sec.gov/dei/2011-01-31",
         gaap: str = "http://fasb.org/us-gaap/2011-01-31") -> bytes:
    """A default-namespace instance (Berkshire's 2011 shape: no ``xbrli:`` prefix at all)."""
    return f"""<?xml version="1.0" encoding="us-ascii" standalone="yes"?>
<xbrl xmlns="http://www.xbrl.org/2003/instance" xmlns:xbrldi="http://xbrl.org/2006/xbrldi" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:dei="{dei}" xmlns:us-gaap="{gaap}" xmlns:co="http://example.com/20110630">
{body}
</xbrl>
""".encode("ascii")


def _ctx(cid: str, instant: str, *members: tuple[str, str], ident: str = "0001067983") -> str:
    seg = ""
    if members:
        seg = "<segment>" + "".join(
            f'<xbrldi:explicitMember dimension="{a}">{m}</xbrldi:explicitMember>' for a, m in members
        ) + "</segment>"
    return (f'<context id="{cid}"><entity><identifier scheme="http://www.sec.gov/CIK">{ident}'
            f"</identifier>{seg}</entity><period><instant>{instant}</instant></period></context>")


def _fact(tag: str, cid: str, value: str, prefix: str = "dei", extra: str = "") -> str:
    return f'<{prefix}:{tag} contextRef="{cid}" unitRef="shares" decimals="INF"{extra}>{value}</{prefix}:{tag}>'


AXIS = "us-gaap:StatementClassOfStockAxis"
COVER = instance.COVER_TAG
BAL = instance.BALANCE_TAG


# --- parse ------------------------------------------------------------------------------------


def test_meta_2014_class_axis_cover_facts_are_kept_with_their_members():
    facts = instance.parse(META_2014)
    cover = sorted((f.dims, f.value, f.instant) for f in facts if f.tag == COVER)
    assert cover == [
        ((("StatementClassOfStockAxis", "CommonClassAMember"),), 2015048077, D("2014-07-22")),
        ((("StatementClassOfStockAxis", "CommonClassBMember"),), 585003514, D("2014-07-22")),
    ]
    assert {f.taxonomy for f in facts if f.tag == COVER} == {"dei"}
    assert sum(f.tag == BAL for f in facts) == 3
    assert all(f.identifier == META for f in facts)
    assert not any(f.tag == "DocumentType" for f in facts)


def test_meta_2014_reads_the_classes_summed_at_the_cover_date():
    got = instance.reading(instance.parse(META_2014), META)
    assert got == instance.Reading(
        tag=COVER,
        as_of=D("2014-07-22"),
        shares=2600051591,
        classes=(("CommonClassAMember", 2015048077), ("CommonClassBMember", 585003514)),
        tagged_total=False,
    )


def test_prefixes_and_taxonomy_versions_are_the_filers_choice():
    blob = _doc(
        _ctx("c1", "2009-10-20") + _fact(COVER, "c1", "1550000", prefix="d9"),
        dei="http://xbrl.us/dei/2009-01-31",
    ).replace(b'xmlns:dei="http://xbrl.us/dei/2009-01-31"', b'xmlns:d9="http://xbrl.us/dei/2009-01-31"')
    got = instance.reading(instance.parse(blob), "0001067983")
    assert got is not None and got.shares == 1550000 and got.classes == () and got.as_of == D("2009-10-20")


def test_member_qnames_keep_their_local_name_whatever_the_prefix():
    blob = _doc(
        _ctx("a", "2014-07-17", (AXIS, "us-gaap:CommonClassAMember"))
        + _ctx("c", "2014-07-17", (AXIS, "co:CapitalClassCMember"))
        + _fact(COVER, "a", "283356281") + _fact(COVER, "c", "338209995")
    )
    got = instance.reading(instance.parse(blob), "0001067983")
    assert got.classes == (("CapitalClassCMember", 338209995), ("CommonClassAMember", 283356281))
    assert got.shares == 621566276


def test_nil_unknown_context_and_non_positive_facts_are_dropped():
    blob = _doc(
        _ctx("c1", "2011-07-28")
        + _fact(COVER, "c1", "", extra=' xsi:nil="true"')
        + _fact(COVER, "nowhere", "100")
        + _fact(COVER, "c1", "0")
        + _fact(COVER, "c1", "-5")
    )
    assert instance.parse(blob) == []


def test_a_doctype_is_refused_before_parsing():
    with pytest.raises(instance.InstanceError, match="DOCTYPE"):
        instance.parse(b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]><x>&a;</x>')


def test_not_an_instance_or_not_xml_is_refused():
    with pytest.raises(instance.InstanceError, match="root element"):
        instance.parse(b"<html><body>404</body></html>")
    with pytest.raises(instance.InstanceError, match="well-formed"):
        instance.parse(META_2014[:3000])


# --- reading ----------------------------------------------------------------------------------


def test_the_cover_tag_wins_and_the_balance_sheet_tag_is_the_fallback():
    with_cover = _doc(
        _ctx("bs", "2011-06-30") + _ctx("cv", "2011-07-28")
        + _fact(BAL, "bs", "1065766445", prefix="us-gaap") + _fact(COVER, "cv", "1066954104")
    )
    got = instance.reading(instance.parse(with_cover), "0001067983")
    assert (got.tag, got.shares, got.as_of) == (COVER, 1066954104, D("2011-07-28"))
    balance_only = _doc(
        _ctx("bs", "2011-06-30") + _ctx("old", "2010-12-31")
        + _fact(BAL, "bs", "1065766445", prefix="us-gaap") + _fact(BAL, "old", "1050990468", prefix="us-gaap")
    )
    got = instance.reading(instance.parse(balance_only), "0001067983")
    assert (got.tag, got.shares, got.as_of) == (BAL, 1065766445, D("2011-06-30"))


def test_a_tagged_total_that_agrees_with_the_classes_is_the_count():
    blob = _doc(
        _ctx("t", "2012-07-19") + _ctx("a", "2012-07-19", (AXIS, "us-gaap:CommonClassAMember"))
        + _ctx("b", "2012-07-19", (AXIS, "us-gaap:CommonClassBMember"))
        + _fact(COVER, "t", "1000000500") + _fact(COVER, "a", "800000000") + _fact(COVER, "b", "200000000")
    )
    got = instance.reading(instance.parse(blob), "0001067983")
    assert got.tagged_total and got.shares == 1000000500 and got.set_aside is None
    assert got.classes == (("CommonClassAMember", 800000000), ("CommonClassBMember", 200000000))


def test_a_bare_figure_that_is_no_total_is_a_class_without_an_axis():
    # The main class tagged bare, the other on the axis: dropping the bare one would leave the
    # company at its smaller class.
    blob = _doc(
        _ctx("t", "2012-07-19") + _ctx("b", "2012-07-19", (AXIS, "us-gaap:CommonClassBMember"))
        + _fact(COVER, "t", "800000000") + _fact(COVER, "b", "200000000")
    )
    got = instance.reading(instance.parse(blob), "0001067983")
    assert not got.tagged_total and got.shares == 1000000000 and got.set_aside == 800000000
    assert got.classes == (("CommonClassBMember", 200000000), (instance.NO_AXIS_MEMBER, 800000000))


def test_a_class_tagged_with_and_without_the_axis_counts_once():
    blob = _doc(
        _ctx("t", "2011-04-21") + _ctx("a", "2011-04-21", (AXIS, "us-gaap:CommonClassAMember"))
        + _ctx("b", "2011-04-21", (AXIS, "us-gaap:CommonClassBMember"))
        + _fact(COVER, "t", "1100000") + _fact(COVER, "a", "1100000") + _fact(COVER, "b", "1050000000")
    )
    got = instance.reading(instance.parse(blob), "0001067983")
    assert got.classes == (("CommonClassAMember", 1100000), ("CommonClassBMember", 1050000000))
    assert got.shares == 1051100000 and not got.tagged_total and got.set_aside == 1100000


def test_a_tracking_group_beside_the_class_axis_keeps_both_member_names():
    track = "linta:TrackingStockAxis"
    blob = _doc(
        _ctx("ia", "2013-07-31", (track, "linta:InteractiveGroupMember"), (AXIS, "us-gaap:CommonClassAMember"))
        + _ctx("va", "2013-07-31", (track, "linta:VenturesGroupMember"), (AXIS, "us-gaap:CommonClassAMember"))
        + _ctx("a", "2013-07-31", (AXIS, "us-gaap:CommonClassAMember"))
        + _fact(COVER, "ia", "500") + _fact(COVER, "va", "40") + _fact(COVER, "a", "540")
    )
    got = instance.reading(instance.parse(blob), "0001067983")
    # Axis-name order (StatementClassOfStockAxis < TrackingStockAxis); the class-only fact beside
    # the group facts is the same shares again and is dropped.
    assert got.classes == (("CommonClassAMember+InteractiveGroupMember", 500),
                           ("CommonClassAMember+VenturesGroupMember", 40))
    assert got.shares == 540 and not got.tagged_total


def test_classes_tagged_without_an_axis_are_summed_and_repeats_counted_once():
    blob = _doc(
        _ctx("x", "2010-02-01") + _ctx("y", "2010-02-01")
        + _fact(COVER, "x", "240000000") + _fact(COVER, "y", "80000000") + _fact(COVER, "y", "80000000")
    )
    got = instance.reading(instance.parse(blob), "0001067983")
    assert got.shares == 320000000 and got.classes == ()


def test_a_stale_class_comparative_is_dropped():
    blob = _doc(
        _ctx("a", "2014-07-22", (AXIS, "us-gaap:CommonClassAMember"))
        + _ctx("b_old", "2013-12-31", (AXIS, "us-gaap:CommonClassBMember"))
        + _fact(COVER, "a", "2015048077") + _fact(COVER, "b_old", "577000000")
    )
    got = instance.reading(instance.parse(blob), "0001067983")
    assert got.classes == (("CommonClassAMember", 2015048077),) and got.shares == 2015048077


def test_another_registrant_and_other_axes_are_not_the_filers_count():
    blob = _doc(
        _ctx("sub", "2011-07-28", ident="0000012345")
        + _ctx("legal", "2011-07-28", ("dei:LegalEntityAxis", "co:SubsidiaryMember"))
        + _ctx("two", "2011-07-28", (AXIS, "us-gaap:CommonClassAMember"), ("us-gaap:RangeAxis", "co:XMember"))
        + _fact(COVER, "sub", "5") + _fact(COVER, "legal", "6") + _fact(COVER, "two", "7")
    )
    assert instance.reading(instance.parse(blob), "0001067983") is None
    # The same file read for the co-registrant answers its own count.
    assert instance.reading(instance.parse(blob), "0000012345").shares == 5


# --- the filing index -------------------------------------------------------------------------


def _index(*names: str) -> bytes:
    import json

    return json.dumps({"directory": {"name": "/Archives/x", "item": [
        {"name": n, "type": "text.gif", "size": "1"} for n in names]}}).encode()


def test_instance_name_traditional_inline_and_rendered_filings():
    meta_2014 = ["0001326801-14-000032.txt", "0001326801-14-000032-xbrl.zip", "fb-20140630.xml",
                 "fb-20140630.xsd", "fb-20140630_cal.xml", "fb-20140630_def.xml", "fb-20140630_lab.xml",
                 "fb-20140630_pre.xml", "FilingSummary.xml", "R1.htm"]
    assert instance.instance_name(instance.filing_files(_index(*meta_2014))) == "fb-20140630.xml"
    meta_2021 = ["0001326801-21-000049-xbrl.zip", "fb-20210630.xsd", "fb-20210630_cal.xml",
                 "fb-20210630_htm.xml", "fb-20210630_lab.xml", "FilingSummary.xml"]
    assert instance.instance_name(meta_2021) == "fb-20210630_htm.xml"
    brk_2011 = ["brka-20101231.xml", "brka-20101231.xsd", "defnref.xml", "R1.xml", "R2.xml",
                "brka-20101231_pre.xml"]
    assert instance.instance_name(brk_2011) == "brka-20101231.xml"
    assert instance.instance_name(["d123.htm", "FilingSummary.xml"]) is None
    assert instance.instance_name(["a.xml", "b.xml"]) is None


def test_a_filing_index_that_is_not_json_is_refused():
    with pytest.raises(instance.InstanceError):
        instance.filing_files(b"<html>")
    with pytest.raises(instance.InstanceError):
        instance.filing_files(b'{"directory": {}}')


# --- cache form -------------------------------------------------------------------------------


def test_fact_json_round_trip():
    facts = instance.parse(META_2014)
    assert [instance.Fact.from_json(f.to_json()) for f in facts] == facts
    with pytest.raises(instance.InstanceError):
        instance.Fact.from_json({"x": "dei", "t": COVER, "v": 0, "i": None, "e": "", "d": [], "y": False})
```

**File:** `engine/tests/test_shares_classes.py` (new). It imports the Meta fixture from
`test_shares_instance` (the tests directory is on `sys.path`, as `labkit` imports show).
**Code:**
```python
"""The per-class csv: closed quarters, the instance download against a fake Archives, the
filing selection, cache -> rows, the csv's invariants and the CLI wiring (no network)."""

from __future__ import annotations

import argparse
import gzip
import json
from datetime import date

import pytest

from seer_engine import cik as c
from seer_engine import membership as m
from seer_engine.commands import shares as shares_cmd
from seer_engine.shares import classes, edgar_index, fetch, history, instance

from test_shares_instance import META_2014

D = date.fromisoformat
META = "0001326801"
ACC = "0001326801-14-000032"
BASE = "https://www.sec.gov/Archives/edgar/data/1326801/000132680114000032/"


def _ref(cik=META, filed="2014-07-24", acc=ACC, form="10-Q", path="edgar/data/1326801/0001326801-14-000032.txt"):
    return edgar_index.FilingRef(cik, D(filed), form, acc, "FACEBOOK INC", path)


# --- quarters ---------------------------------------------------------------------------------


def test_only_closed_quarters_are_listed():
    qs = edgar_index.closed_quarters(D("2009-01-01"), D("2026-10-18"))
    assert qs[0] == (2009, 1) and qs[-1] == (2026, 3) and len(qs) == 71
    # Inside the grace week the quarter just ended still counts as open.
    assert edgar_index.closed_quarters(D("2009-01-01"), D("2026-10-03"))[-1] == (2026, 2)
    assert edgar_index.closed_quarters(D("2026-07-01"), D("2026-07-05")) == []
    assert edgar_index.quarter_end(2024, 1) == D("2024-03-31")
    assert edgar_index.quarter_end(2024, 4) == D("2024-12-31")


# --- download against a fake Archives -----------------------------------------------------------


class _Resp:
    def __init__(self, status: int, body: bytes = b"") -> None:
        self.status_code = status
        self.content = body

    def iter_content(self, chunk_size: int = 65536):
        yield self.content

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _Session:
    """Answers from a url -> (status, body) map; anything else is a 404. Records every url."""

    def __init__(self, routes: dict[str, tuple[int, bytes]], calls: list[str]) -> None:
        self.routes = routes
        self.calls = calls

    def get(self, url, timeout=None, stream=False):
        self.calls.append(url)
        status, body = self.routes.get(url, (404, b""))
        return _Resp(status, body)


def _archive(routes, calls):
    return fetch.Archive("tests@example.com", pacer=fetch.Pacer(0.0),
                         session_factory=lambda: _Session(routes, calls), sleep=lambda s: None)


def _listing(*names: str) -> bytes:
    return json.dumps({"directory": {"item": [{"name": n} for n in names]}}).encode()


def test_filing_dir_is_the_accession_folder():
    assert fetch.filing_dir(_ref()) == "edgar/data/1326801/000132680114000032/"


def test_instances_are_fetched_parsed_cached_and_not_asked_again(tmp_path):
    routes = {
        BASE + "index.json": (200, _listing("fb-20140630.xml", "fb-20140630.xsd", "fb-20140630_pre.xml")),
        BASE + "fb-20140630.xml": (200, META_2014),
    }
    calls: list[str] = []
    ref = _ref()
    t = fetch.fetch_instances(_archive(routes, calls), tmp_path, [ref, ref], workers=2)
    assert (t.wanted, t.fetched, t.missing, t.failed) == (1, 1, 0, [])
    assert calls == [BASE + "index.json", BASE + "fb-20140630.xml"]
    name, facts = fetch.read_instance(fetch.instance_path(tmp_path, META, ACC))
    assert name == "fb-20140630.xml" and tuple(instance.parse(META_2014)) == facts
    # Resumable: a second run asks nothing.
    calls.clear()
    t = fetch.fetch_instances(_archive(routes, calls), tmp_path, [ref])
    assert (t.cached, t.fetched, calls) == (1, 0, [])


def test_a_filing_without_an_instance_is_marked_with_its_reason(tmp_path):
    calls: list[str] = []
    no_xbrl = _ref(acc="0001326801-12-000001", path="edgar/data/1326801/0001326801-12-000001.txt")
    gone = _ref(acc="0001326801-12-000002", path="edgar/data/1326801/0001326801-12-000002.txt")
    routes = {
        "https://www.sec.gov/Archives/edgar/data/1326801/000132680112000001/index.json":
            (200, _listing("d123.htm", "FilingSummary.xml")),
    }
    t = fetch.fetch_instances(_archive(routes, calls), tmp_path, [no_xbrl, gone], workers=1)
    assert (t.fetched, t.missing) == (0, 2)
    assert fetch.read_missing(fetch.instance_missing_path(tmp_path, META, no_xbrl.accession)) == "no XBRL instance"
    assert fetch.read_missing(fetch.instance_missing_path(tmp_path, META, gone.accession)) == "no filing index"


def test_a_joint_filing_is_fetched_once_and_cached_for_each_filer(tmp_path):
    routes = {
        BASE + "index.json": (200, _listing("fb-20140630.xml", "fb-20140630.xsd")),
        BASE + "fb-20140630.xml": (200, META_2014),
    }
    calls: list[str] = []
    twin = _ref(cik="0000000002")
    t = fetch.fetch_instances(_archive(routes, calls), tmp_path, [_ref(), twin], workers=1)
    assert t.fetched == 1 and len(calls) == 2
    assert fetch.instance_path(tmp_path, "0000000002", ACC).exists()


def test_a_server_error_that_outlasts_the_retries_is_a_failure_not_a_marker(tmp_path):
    routes = {BASE + "index.json": (500, b"")}
    t = fetch.fetch_instances(_archive(routes, []), tmp_path, [_ref()], workers=1)
    assert len(t.failed) == 1 and t.missing == 0
    assert not fetch.instance_missing_path(tmp_path, META, ACC).exists()


def test_a_wrong_version_cache_file_is_refused(tmp_path):
    p = tmp_path / "x.json.gz"
    p.write_bytes(gzip.compress(b'{"version": 0, "facts": []}'))
    with pytest.raises(instance.InstanceError, match="version"):
        fetch.read_instance(p)


# --- selection --------------------------------------------------------------------------------


def _tenure(symbol, cik, start, end=None):
    return c.CikRow(symbol, cik, D(start), D(end) if end else None, "X", "manual", "n")


def test_member_windows_merge_the_sp500_and_the_nasdaq_100():
    ivs = [m.Interval("AAA", "SP500", D("2012-06-01"), D("2014-01-01"), "AAA"),
           m.Interval("AAA", "NDX", D("2015-06-01"), None, "AAA"),
           m.Interval("BBB", "NDX", D("2013-01-01"), None, "BBB"),
           m.Interval("OLD", "SP500", D("2001-01-01"), D("2005-01-01"), "OLD")]
    index = {"AAA": (_tenure("AAA", "0000000001", "1990-01-01"),),
             "BBB": (_tenure("BBB", "0000000002", "1990-01-01"),),
             "OLD": (_tenure("OLD", "0000000003", "1990-01-01"),)}
    wins = classes.member_windows(ivs, index, end=D("2026-09-30"))
    assert list(wins) == ["0000000001", "0000000002"]  # NDX-only filers too; none before 2009
    a = wins["0000000001"]
    assert (a.start, a.end) == (D("2011-04-28"), D("2026-09-30"))
    assert wins["0000000002"].start == D("2011-11-28")


def _fundamentals(tmp_path, rows):
    p = tmp_path / "fundamentals.csv"
    head = "symbol,taxonomy,tag,unit,period_start,period_end,val,accn,form,fy,fp,filed\n"
    p.write_text(head + "".join(
        f"{s},dei,{t},shares,,{end},{v},{a},10-Q,2014,Q2,{f}\n" for s, t, end, v, a, f in rows
    ))
    return p


def test_companyfacts_cover_accessions_and_multi_value_filers(tmp_path):
    index = {"AAA": (_tenure("AAA", "0000000001", "1990-01-01"),),
             "CCC": (_tenure("CCC", "0000000003", "1990-01-01"),)}
    p = _fundamentals(tmp_path, [
        ("AAA", "EntityCommonStockSharesOutstanding", "2014-07-20", "100.0", "0000000001-14-000001", "2014-07-25"),
        ("AAA", "WeightedAverageNumberOfSharesOutstandingBasic", "2014-06-30", "90.0", "0000000001-14-000002", "2014-07-25"),
        ("CCC", "EntityCommonStockSharesOutstanding", "2014-07-20", "70.0", "0000000003-14-000001", "2014-07-25"),
        ("CCC", "EntityCommonStockSharesOutstanding", "2014-07-20", "30.0", "0000000003-14-000001", "2014-07-25"),
        ("CCC", "EntityCommonStockSharesOutstanding", "2014-10-20", "0.0", "0000000003-14-000009", "2014-10-25"),
    ])
    got = classes.read_companyfacts(p, index)
    assert got.dei_accessions == frozenset({"0000000001-14-000001", "0000000003-14-000001"})
    assert got.multi_value_ciks == frozenset({"0000000003"})


def test_select_wants_uncounted_filings_and_every_filing_of_a_multi_class_filer():
    wins = {k: edgar_index.Window(k, D("2011-01-01"), D("2026-09-30"), ("X",))
            for k in ("0000000001", "0000000003")}
    counted = _ref(cik="0000000001", acc="0000000001-14-000001")
    uncounted = _ref(cik="0000000001", acc="0000000001-14-000005")
    multi = _ref(cik="0000000003", acc="0000000003-14-000001")
    outside = _ref(cik="0000000009", acc="0000000009-14-000001")
    facts = classes.CompanyFacts(frozenset({counted.accession, multi.accession}), frozenset())
    got = classes.select([counted, uncounted, multi, outside], wins, facts, frozenset({"0000000003"}))
    assert got == [uncounted, multi]


def test_cover_rows_with_classes_mark_a_multi_class_filer():
    row = history.ShareRow("0000000003", D("2009-05-01"), "0000000003-09-000001", "CCC", D("2009-04-20"),
                           "10-Q", 100, (("Class A", 70), ("Class B", 30)), (), "")
    single = history.ShareRow("0000000001", D("2009-05-01"), "0000000001-09-000001", "AAA", D("2009-04-20"),
                              "10-Q", 100, (), (), "")
    assert classes.cover_multi_class_ciks([row, single]) == frozenset({"0000000003"})


# --- cache -> rows -> csv -------------------------------------------------------------------------


def _cache_meta(tmp_path, ref):
    path = fetch.instance_path(tmp_path, ref.cik, ref.accession)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(fetch.instance_blob("fb-20140630.xml", instance.parse(META_2014)))


def test_build_rows_reads_meta_2014_as_the_exit_criterion_says(tmp_path):
    ref = _ref()
    _cache_meta(tmp_path, ref)
    missing = _ref(acc="0001326801-14-000040", path="edgar/data/1326801/0001326801-14-000040.txt")
    fetch.instance_missing_path(tmp_path, META, missing.accession).write_text("no XBRL instance\n")
    never = _ref(acc="0001326801-14-000050", path="edgar/data/1326801/0001326801-14-000050.txt")
    tenures = {META: [_tenure("FB", META, "2012-05-18", "2022-06-09"), _tenure("META", META, "2022-06-09")]}
    built = classes.build_rows(tmp_path, [ref, missing, never, ref], tenures)
    assert built.rows == [classes.ClassRow(
        cik=META, symbol="FB", filed=D("2014-07-24"), as_of=D("2014-07-22"), form="10-Q",
        accession=ACC, shares=2600051591,
        classes=(("CommonClassAMember", 2015048077), ("CommonClassBMember", 585003514)),
        tagged_total=False,
    )]
    assert built.skipped == {"on EDGAR without a count: no XBRL instance": 1, "not downloaded": 1}
    out = tmp_path / "data" / classes.CLASSES_FILE
    assert classes.write_rows(out, built.rows) == 1
    assert out.read_text() == (
        "cik,symbol,filed,as_of,form,accession,shares,classes,tagged_total\n"
        "0001326801,FB,2014-07-24,2014-07-22,10-Q,0001326801-14-000032,2600051591,"
        "CommonClassAMember=2015048077;CommonClassBMember=585003514,false\n"
    )
    assert classes.load_rows(out) == built.rows


def test_a_row_too_far_from_its_filing_date_is_dropped_not_written(tmp_path):
    late = _ref(filed="2015-06-01")  # 314 days after the 2014-07-22 count
    _cache_meta(tmp_path, late)
    built = classes.build_rows(tmp_path, [late], {})
    assert built.rows == [] and list(built.skipped) == ["dropped: as_of N too far from filed N"]


def _row(**kw):
    base = dict(cik=META, symbol="FB", filed=D("2014-07-24"), as_of=D("2014-07-22"), form="10-Q",
                accession=ACC, shares=300, classes=(("CommonClassAMember", 200), ("CommonClassBMember", 100)),
                tagged_total=False)
    base.update(kw)
    return classes.ClassRow(**base)


def test_csv_invariants():
    classes.check_rows([_row(), _row(accession="0001326801-14-000040", filed=D("2014-10-30"),
                                     as_of=D("2014-10-25"), shares=301, tagged_total=True)])
    with pytest.raises(classes.ClassesError, match="no rows"):
        classes.check_rows([])
    with pytest.raises(classes.ClassesError, match="sorted"):
        classes.check_rows([_row(filed=D("2014-10-30"), as_of=D("2014-10-25"),
                                 accession="0001326801-14-000040"), _row()])
    with pytest.raises(classes.ClassesError, match="duplicate"):
        classes.check_rows([_row(), _row()])
    with pytest.raises(classes.ClassesError, match="classes sum"):
        classes.check_rows([_row(shares=301)])
    with pytest.raises(classes.ClassesError, match="tagged total"):
        classes.check_rows([_row(shares=400, tagged_total=True)])
    with pytest.raises(classes.ClassesError, match="needs its classes"):
        classes.check_rows([_row(classes=(), tagged_total=True)])
    with pytest.raises(classes.ClassesError, match="before"):
        classes.check_rows([_row(filed=D("2008-12-31"), as_of=D("2008-12-20"))])
    with pytest.raises(classes.ClassesError, match="sorted by member"):
        classes.check_rows([_row(classes=(("CommonClassBMember", 100), ("CommonClassAMember", 200)))])
    classes.check_rows([_row(classes=(("CommonClassAMember", 300),))])  # one class is a fact too


def test_load_rows_refuses_a_bad_header_or_flag(tmp_path):
    p = tmp_path / classes.CLASSES_FILE
    p.write_text("cik,symbol\n")
    with pytest.raises(classes.ClassesError, match="header"):
        classes.load_rows(p)
    p.write_text(",".join(classes.HEADER) + "\n"
                 "0001326801,FB,2014-07-24,2014-07-22,10-Q,0001326801-14-000032,300,,yes\n")
    with pytest.raises(classes.ClassesError, match="tagged_total"):
        classes.load_rows(p)


# --- CLI ----------------------------------------------------------------------------------------


def test_the_shares_command_has_both_class_actions():
    p = argparse.ArgumentParser()
    shares_cmd.add_arguments(p)
    a = p.parse_args(["download-classes", "--fundamentals", "/x/fundamentals.csv", "--cik", "1326801",
                      "--through", "2026-10-18", "--limit", "5"])
    assert (a.action, a.cik, a.through, a.limit) == ("download-classes", ["1326801"], D("2026-10-18"), 5)
    b = p.parse_args(["build-classes"])
    assert b.action == "build-classes" and b.out == classes.DATA_DIR / classes.CLASSES_FILE
    p.format_help()
```
**Impact:** 34 new tests, no network (the download tests drive `fetch.Archive` through a fake
`session_factory` with `Pacer(0.0)` and a no-op `sleep`), no Postgres.

## Verification

**Build:** `cd /home/miftah/.worktrees/seer/multi-class-company-size && engine/.venv/bin/ruff check engine`
**Tests:** `engine/.venv/bin/pytest engine/tests/test_shares_instance.py engine/tests/test_shares_classes.py engine/tests/test_shares.py engine/tests/test_shares_store.py engine/tests/test_cli.py -n0`, then the full `engine/.venv/bin/pytest engine/tests` (with `PG_TEST_URL` set; CI fails on skipped DB tests).
**Manual check (live, optional, small; writes only the real cache and a scratch csv):**
```bash
cd /home/miftah/.worktrees/seer/multi-class-company-size
export SEER_ENV_FILE=/home/miftah/seer/.env.local SEER_EDGAR_CACHE=/home/miftah/seer/engine/.cache/edgar
engine/.venv/bin/python -m seer_engine shares download-classes \
  --fundamentals /home/miftah/seer/engine/.research/fundamentals.csv --cik 1326801 --limit 12
engine/.venv/bin/python -m seer_engine shares build-classes --cik 1326801 \
  --out /tmp/claude-1000/-home-miftah-seer/64e9ed16-1c43-4f55-baf1-13b0a12c0465/scratchpad/meta_classes.csv
grep 0001326801-14-000032 /tmp/claude-1000/-home-miftah-seer/64e9ed16-1c43-4f55-baf1-13b0a12c0465/scratchpad/meta_classes.csv
```
The first command downloads the 63 missing master indexes 2011Q1..2026Q3 into the real cache
once (they are needed by phase 3 anyway). `--limit 12` takes Meta's first twelve wanted filings
in filing order, from its first 10-Q after the 2012 listing; 2014-07-24 is the ninth.
Never pass `--out` pointing into `engine/data/` in this phase.
**Exit criteria:** ruff clean, full suite green; the live sample prints
`0001326801,FB,2014-07-24,2014-07-22,10-Q,0001326801-14-000032,2600051591,CommonClassAMember=2015048077;CommonClassBMember=585003514,false`;
no `engine/data/shares_xbrl_classes.csv` in the commit.

## Handoffs

- **Phase 2 (R1-R3):** reading `shares_xbrl_classes.csv` into `SharesHistory` as source
  `"xbrl-class"`, every class -> symbol attribution and ratio (Berkshire A x 1,500 / x 30, Visa
  B/C, Accenture X at 0, Alphabet C -> GOOG), and the same-accession precedence rule against the
  companyfacts reading. This phase deliberately sums classes **1:1** in `shares` and keeps the
  member names so phase 2 can redo the arithmetic; phase 2 should weight from `classes`, not
  `shares`, whenever `classes` is non-empty (except that a `tagged_total` row's `shares` is the
  filer's own total).
- **Phase 2:** the csv does not exist in the tree until phase 3 commits it. Phase 2's `shares
  store` default (`classes.DATA_DIR / classes.CLASSES_FILE`) must cope with its absence (or
  phase 2/3 reconcile the order); phase 2's tests should write their own csv with
  `classes.write_rows` / `classes.render`.
- **Phase 2:** class member names vary by filer (`CommonClassAMember`, `CapitalClassCMember`,
  `CommonStockMember`, filer-specific `xx:ClassASpecialMember` local names). Two-axis
  (tracking-group) labels arrive as both names joined by `+`; a bare figure counted as a class
  arrives as `NoClassAxisMember` (Interface Contract). `share_classes.csv`'s `member` column is
  matched by words (`class_table.class_key`), so either spelling works.
- **Phase 3 (R4/R5):** the full `download-classes` run, a second run with `--cik` for every CIK
  of `engine/data/share_classes.csv`, then `build-classes`, committing
  `engine/data/shares_xbrl_classes.csv`, filling the `Fetched` / `Scope` / `Rows` / `sha256`
  cells of the new `SOURCES.md` section, and reviewing every `set aside:` line `build-classes`
  prints (a bare figure counted as a class without an axis is right when the filer tagged its
  main class bare; when the filing's cover shows the bare figure is instead the company total
  beside a partial class breakdown, that is a phase 3 Step 6 fix with a test).
- **Phase 3:** the `shares/__init__.py` module map (add `instance` and `classes`) and
  `engine/package_readme.md`, which the index assigns to phase 3's docs pass.

## Rollback

Revert this phase's commit. It adds two modules, two test files and a docs section, and only
appends to `edgar_index.py`, `fetch.py` and `commands/shares.py`; nothing reads the new code
outside the new actions. A live sample run leaves `engine/.cache/edgar/xbrl-instance/` and the
2011Q1+ master indexes in the gitignored cache; they are harmless and reused by phase 3 (delete
`xbrl-instance/` to force a refetch).

# Phase 2: Class-aware share history

**Plan set:** `MULTI_CLASS_COMPANY_SIZE_PLAN.md`
**Analysis:** `20261018-171434-MCS7_code_analyzer.md`
**Satisfies:** R1, R2, R3 — a multi-class company gets one point-in-time size: classes summed (R1), Berkshire's class A in class B units (R2), each listed class its own count (R3)
**Depends on:** Phase 1
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/shares` (plus `backtest/market.py` docstrings)

---

## Goal

`history.SharesHistory` reads phase 1's per-class XBRL rows as a third source, `xbrl-class`, and
attributes every count (per-class rows and pre-2010 cover rows alike) to the asked symbol through
a new hand-kept class table, `engine/data/share_classes.csv`. After this phase a filer with
class-axis counts (Meta) answers the classes summed, BRK.B answers class A x 1,500 + class B
(x 30 before 2010-01-21), Visa answers its as-converted count, GOOGL and GOOG each answer their
own classes and sum to the company, and a filer with no table rows and no per-class rows answers
exactly as before. `shares store` joins `engine/data/shares_xbrl_classes.csv` (or `--classes`),
and `shares store-report --symbols` prints chosen symbols' size. No store is touched.

## Decisions made in this phase (for the reconciler)

1. **The class table is keyed on the count's date**, never the day asked. A count is stated in
   the class structure and share units of the day it was taken; later splits are carried by the
   split list. So Berkshire's ratio is 30 for a count dated before 2010-01-21 and 1,500 from it,
   and a 2009 count read in 2010 is then carried across the 50-for-1 split (verified: 2,327.6M
   carried vs 2,470.0M in the next count). Because the table adds no day of its own,
   `store._candidates` stays exact with one added loop (the per-class rows' filing and age-out
   days).
2. **Sibling rows start at the count the sibling first needs**, not at the class's creation.
   Before a filer's first row its symbols answer the whole company, as today: FOXA is the whole
   of Twenty-First Century Fox until FOX joins (rows from 2014-09-01, so the November 2014 count
   already splits). That keeps a company counted once whenever only one of its lines is a member,
   and R3's own-class split wherever two are.
3. **Fail loud only where the table speaks; sum 1:1 everywhere else** (settled by the
   reconciler: index Decisions and R5's Done-means names). A filer with **no** table row on a
   count's date — META, MA, CMCSA (outside its 2015 span), UPS, F, EL, TSN, RL, BF.B and every
   other multi-class filer not in the seed — has its classes summed one for one and each of its
   symbols answers the whole company; the filer is recorded in `SharesHistory.summed`, which
   `shares store` prints, and is never refused. Where the table **does** have rows for the filer
   on the count's date, every class in the count must match a row; an unmatched class (including
   phase 1's `NoClassAxisMember`), a figure without a class breakdown (an axis-less companyfacts
   fact, a one-total cover) or a symbol the table names no class for makes the answer unknown
   and is kept in `SharesHistory.problems`, which `shares store` prints. Inside a tabled filer
   there is no 1:1 fallback, single-listed or not: a tracking stock (Liberty Ventures) summed 1:1
   into QRTEA is exactly the error the table exists to stop.
4. **Same-day precedence:** `xbrl-class` > `xbrl` > `edgar-cover` (`history.SOURCE_RANK`). With
   no per-class rows this is the old rule (XBRL wins a same-day tie) unchanged. Invariant 5 holds
   because phase 1 reads an instance only where companyfacts has no count for the accession or the
   filer is multi-class; for a single-class filer with a companyfacts count there is no per-class
   row to compete, and where both exist the instance's figure is the same tagged total.
5. **Class labels are matched by their words** (`class_table.class_key`): split camel case and
   punctuation, lowercase, drop `common/stock/shares/share/ordinary/capital/member`, read `series`
   as `class`, sort. `CommonClassAMember`, `class a common` (cover text) and `series a` are one
   key, so one table row serves pre-2010 cover rows and XBRL members alike (Berkshire's cover rows
   are converted by the same two rows as its XBRL rows). Sorting makes a two-axis label (tracking
   group + class) independent of member order and separator.
6. **Member names in the seed table were read from the filers' own instance documents**
   (2026-10-18, under 5 req/s): Meta `CommonClassA/BMember`; Berkshire, Visa (`v:CommonClassB1Member`,
   `v:CommonClassB2Member` from 2024), Alphabet (`goog:CapitalClassCMember`), Accenture
   (`acn:CommonClassXMember`), Comcast (`cmcsa:ClassaSpecialCommonStockMember` - no letter split,
   so its own row), Liberty Global (`lbtya:ClassOrdinarySharesMember` for class A - typo kept, own
   row; LiLAC on `us-gaap:StatementBusinessSegmentsAxis`), Liberty Media 2016
   (`lmca:EconomicPerformanceGroupAxis`), Liberty Interactive (`linta:TrackingStockAxis` in 2013,
   single-axis `QvcGroupCommonClassMember` in 2017), Under Armour (`ConvertibleCommonStockMember`
   for class B), Discovery, News Corp, Fox, Fox Corp. Visa's conversion rates come from its 8-Ks,
   each cited in `note`. Sibling rows are seeded only for filers with two or more index-member
   symbols in `sp500_history.csv`/`ndx_history.csv` (checked against the date-scoped ticker map;
   the test `test_every_vendored_row_names_a_symbol_its_filer_traded_as` keeps it so).

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.
**Creates:**
- `seer_engine.shares.class_table` (`engine/src/seer_engine/shares/class_table.py`): `TABLE_FILE = "share_classes.csv"`, `HEADER`, `NOISE`, `ClassTableError(ValueError)`, `class_key(label) -> tuple[str, ...]`, `ClassRule` (frozen dataclass: `cik, member, key, symbol, ratio, start, end, note`; `covers(counted)`), `Attribution(NamedTuple: shares: float | None, problem: str | None)`, `ClassTable(rules=())` with `__len__`, `ciks()`, `rules(cik, counted)`, `attribute(cik, symbol, counted, total, classes) -> Attribution`, `load_table(path) -> ClassTable`, `check_rules(rules, name)`.
- `engine/data/share_classes.csv` (header `cik,member,symbol,ratio,from,to,note`; 99 rows, 14 filers).
- `history.SOURCE_XBRL_CLASS = "xbrl-class"`, `history.SOURCE_RANK`, `history.ClassReading` (Protocol: `cik, filed, accession, as_of, shares, classes`), `SharesHistory.latest_class(cik, on)`, `SharesHistory.problems: dict[(cik, accession, symbol), str]`, `SharesHistory.summed: set[str]` (filers with several classes and no table row, summed 1:1), `SharesHistory.table`.
- `integrate.sizes(data, on, symbols)`; CLI `shares store --classes FILE`; CLI `shares store-report --symbols A,B`.
- `engine/tests/test_share_class_table.py`.
- `engine/data/SOURCES.md` section `## share_classes.csv: which listed symbol each share class answers for` (appended at the end of the file).
**Signature changes (all backward compatible, keyword-only additions):**
- `history.SharesHistory(rows, index, xbrl=(), *, max_age_days=..., class_rows=(), table=None)`
- `history.load(data_dir=DATA_DIR, xbrl=(), *, max_age_days=..., class_rows=())` — now also loads the vendored class table.
- `store.history_for(xbrl, data_dir=DATA_DIR, *, class_rows=())` — now also loads the vendored class table.
- `store.SOURCES` gains `"xbrl-class"` (so `read_shares` accepts it).
**Requires (from earlier phases):**
- Phase 1: `seer_engine.shares.classes` with `CLASSES_FILE = "shares_xbrl_classes.csv"` and `load_rows(path) -> list[ClassRow]`; `ClassRow` has `cik: str` (10 digits), `filed: date`, `as_of: date` (or None), `accession: str`, `shares: int` (> 0), `classes: tuple[tuple[str, int], ...]` (member local names; empty when the instance had no class axis). `load_rows` raises a `ValueError` subclass on a bad file (integrate catches `ValueError`). Imported **lazily** inside `integrate.write` only, so this phase's tests do not import it.
- Phase 1: a context with a class axis **and** a tracking-group axis (`instance.GROUP_AXES`: `TrackingStockAxis`, `EconomicPerformanceGroupAxis`, `StatementBusinessSegmentsAxis` — Liberty Global/LiLAC 2015-2017, Liberty Media 2016, Liberty Interactive 2012-2014) arrives as both member local names in axis-name order joined by `+` (`CommonClassAMember+InteractiveGroupMember`); the parser of `classes` (`label=count;...`) keeps everything before the last `=`, and `class_key` sorts the words, so order and separator do not matter.
- Phase 1: an undimensioned figure that is neither the classes' total nor one of them arrives as a class labelled `NoClassAxisMember` (key `("axis", "class", "no")`). For a filer with no table row it is summed like any class; for a tabled filer it matches no seed row and is reported in `problems` until phase 3 adds a cited row naming which class it is.
- Phase 1: `download-classes --cik X` (repeatable) reads **every** 2009+ member 10-K/10-Q of filer X, counted by companyfacts or not. Phase 3 runs it for every CIK in `engine/data/share_classes.csv`, because for those filers a companyfacts figure cannot be split and a filing without a per-class row answers unknown. Phase 1 never reads this file.
**Leaves alone (owned by others):** `shares/instance.py`, `shares/fetch.py`, `shares/edgar_index.py`, `shares/classes.py` (import only), `commands/shares.py` (Phase 1); every store, `engine/data/shares_xbrl_classes.csv`, the lab, `shares/__init__.py` docstring, `package_readme.md`, the skill notes (Phase 3); `lab/methods/*.py`, `backtest/registry.py` (frozen).

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/shares/class_table.py` | create | the class table: key normaliser, rules, attribution, strict loader |
| `engine/data/share_classes.csv` | create | 99 hand-kept rows, each citing its filing |
| `engine/src/seer_engine/shares/history.py` | modify (whole file below; changes at `:1-35` docstring, `:48-49` imports, `:76-77` sources, `:109` Observation comment, `:130` new Protocol, `:280-340` `SharesHistory`, `:343-355` `load`) | third source, attribution, problems |
| `engine/src/seer_engine/shares/store.py` | modify (`:1-20` docstring, `:44` import, `:48` `SOURCES`, `:80-81` `_candidates`, `:382-388` `history_for`) | new source, candidates, history_for |
| `engine/src/seer_engine/shares/integrate.py` | modify (`:1-22` docstring, `:59` `--classes`, `:69` `--symbols`, `:151-154` load per-class rows, `:188-189` report counts and problems, `:253` `sizes`, `:319` print chosen symbols) | CLI wiring |
| `engine/src/seer_engine/backtest/market.py` | modify (`:285-294` `ShareCount` doc, `:304-309` `ShareCounts` doc) | docstrings only |
| `engine/data/SOURCES.md` | modify (append after line 470, the end of the file) | the class table's section |
| `engine/tests/test_share_class_table.py` | create | 11 test functions, 26 cases (keys, loader, attribution, vendored table, spot checks, invariant, change-point exactness) |

## Implementation Steps

Every code block below was run before this plan was written: applied to a copy of the worktree's
`engine/` (base `1297681`), `ruff check engine` clean, and `test_share_class_table.py`,
`test_shares.py` and `test_shares_store.py` passed (86 tests), with the whole suite showing no
failure outside the tests that need the repo root (`lab/`, `docs/`, `web/`, absent from the copy).

### Step 1: The class table module
**File:** `engine/src/seer_engine/shares/class_table.py` (new)
**Change:** create the file with exactly this content.
**Code:**
```python
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
```
**Impact:** none on its own; pure module, imports only the standard library (no cycle with `history`).

### Step 2: The vendored class table
**File:** `engine/data/share_classes.csv` (new)
**Change:** create the file with exactly this content (LF line endings, trailing newline;
sha256 `5c67b05b2028a810ac0b86281bfcf9802316217171111020f245f1ba68f08e0d`).
**Code:**
```csv
cik,member,symbol,ratio,from,to,note
0001067983,class A,BRK.B,30,2009-01-01,2010-01-21,1 class A converts into 30 class B until the 50-for-1 class B split of 2010-01-21 (cover of 10-Q 0001157523-09-007839 lists both classes)
0001067983,class A,BRK.B,1500,2010-01-21,,1 class A converts into 1500 class B from the 50-for-1 class B split of 2010-01-21 (10-Q 0001193125-12-449402 tags CommonClassAMember and CommonClassBMember)
0001067983,class B,BRK.B,1,2009-01-01,,BRK.B is the class B line; a count before the 2010-01-21 split is carried across it by the split list
0001166691,class A,CMCSA,1,2015-04-01,2016-01-01,CMCSK (class A special) was a member 2015-09-21..2015-12-14; from the count of 10-Q 0001193125-15-260886 (as of 2015-06-30) class A answers CMCSA; before it CMCSA answers the whole company
0001166691,class B,CMCSA,1,2015-04-01,2016-01-01,class B is unlisted and converts share for share into class A (10-Q 0001193125-15-260886)
0001166691,ClassaSpecialCommonStockMember,CMCSK,1,2015-04-01,2016-01-01,Comcast's own member name for class A special (10-Q 0001193125-15-260886); reclassified into class A 2015-11-20
0001166691,class A special,CMCSK,1,2015-04-01,2016-01-01,the same class as ClassaSpecialCommonStockMember spelled as the cover text and us-gaap would spell it
0001288776,class A,GOOGL,1,2014-04-03,,GOOGL is class A from the class C dividend (GOOG trades class C from 2014-04-03); before it GOOG and GOOGL are one share and both answer the whole company (10-Q 0001288776-14-000065)
0001288776,class B,GOOGL,1,2014-04-03,,class B is unlisted and converts share for share into class A (10-Q 0001288776-14-000065)
0001288776,class C,GOOG,1,2014-04-03,,class C (goog:CapitalClassCMember) created by the stock dividend of 2014-04-02 (10-Q 0001288776-14-000065)
0001308161,class A,FOXA,1,2014-09-01,,FOX (class B voting) joined the Nasdaq-100 2014-12-22; from the count before it class A answers FOXA and class B FOX; earlier FOXA answers the whole company (10-Q 0001564590-15-000522)
0001308161,class B,FOX,1,2014-09-01,,class B voting is FOX (10-Q 0001564590-15-000522)
0001336917,class A,UAA,1,2016-01-01,,class C (UA) created by the stock dividend of 2016-04-07 and a member from 2016-04-08; class A is UAA (10-Q 0001336917-16-000077)
0001336917,class B,UAA,1,2016-01-01,,class B converts share for share into class A; spelled as us-gaap would
0001336917,ConvertibleCommonStockMember,UAA,1,2016-01-01,,Under Armour's member name for class B (10-Q 0001336917-16-000077); converts share for share into class A
0001336917,class C,UA,1,2016-01-01,,class C is UA (10-Q 0001336917-16-000077)
0001355096,InteractiveGroupMember CommonClassAMember,QRTEA,1,2012-08-01,2018-03-10,Liberty Interactive group series A is QRTEA; tracking-stock axis linta:TrackingStockAxis (10-Q 0001355096-13-000063)
0001355096,InteractiveGroupMember CommonClassBMember,QRTEA,1,2012-08-01,2018-03-10,Liberty Interactive group series B converts share for share into series A (10-Q 0001355096-13-000063)
0001355096,QvcGroupMember CommonClassAMember,QRTEA,1,2012-08-01,2018-03-10,the Interactive group renamed QVC Group in 2014; series A is QRTEA
0001355096,QvcGroupMember CommonClassBMember,QRTEA,1,2012-08-01,2018-03-10,QVC Group series B converts share for share into series A
0001355096,QvcGroupCommonClassMember,QRTEA,1,2012-08-01,2018-03-10,Liberty Interactive's own member name for QVC Group series A (10-Q 0001558370-17-003997)
0001355096,VenturesGroupMember CommonClassAMember,QRTEA,0,2012-08-01,2018-03-10,Liberty Ventures is a separate tracking stock (LVNTA) and never an index member: no claim on QRTEA (10-Q 0001355096-13-000063)
0001355096,VenturesGroupMember CommonClassBMember,QRTEA,0,2012-08-01,2018-03-10,Liberty Ventures series B: no claim on QRTEA (10-Q 0001558370-17-003997)
0001355096,VenturesGroupCommonClassMember,QRTEA,0,2012-08-01,2018-03-10,Liberty Interactive's own member name for Liberty Ventures series A (10-Q 0001558370-17-003997): no claim on QRTEA
0001403161,class A,V,1,2008-03-19,,V is the class A line (10-Q 0001384108-12-000008 tags CommonClassAMember/BMember/CMember)
0001403161,class B,V,0.7143,2008-03-19,2008-12-19,class B conversion rate at the IPO (10-Q 0001193125-09-022518)
0001403161,class B,V,0.6296,2008-12-19,2009-07-16,escrow deposit of 2008-12-19 (10-Q 0001193125-09-022518)
0001403161,class B,V,0.5824,2009-07-16,2010-05-28,escrow deposit announced 2009-07-16 (8-K 0001193125-09-150142)
0001403161,class B,V,0.5550,2010-05-28,2010-10-08,escrow deposit of 2010-05-28 (8-K 0000950130-10-002056)
0001403161,class B,V,0.5102,2010-10-08,2011-03-31,escrow deposit of 2010-10-08 (8-K 0001193125-10-227618)
0001403161,class B,V,0.4881,2011-03-31,2011-12-29,escrow deposit of 2011-03-31 (8-K 0001193125-11-089724)
0001403161,class B,V,0.4254,2011-12-29,2012-07-24,effective 2011-12-29 (8-K 0001193125-12-042735)
0001403161,class B,V,0.4206,2012-07-24,2014-09-24,effective 2012-07-24 (8-K 0001193125-12-314435)
0001403161,class B,V,0.4121,2014-09-24,2015-03-19,effective 2014-09-24 (8-K 0001193125-14-351610)
0001403161,class B,V,1.6483,2015-03-19,2018-06-28,x4 with the 4-for-1 class A split of 2015-03-19 (8-K 0001193125-15-025534)
0001403161,class B,V,1.6298,2018-06-28,2019-09-27,effective 2018-06-28 (8-K 0001403161-18-000024)
0001403161,class B,V,1.6228,2019-09-27,2021-12-29,effective 2019-09-27 (8-K 0001403161-19-000036)
0001403161,class B,V,1.6181,2021-12-29,2022-06-29,effective 2021-12-29 (8-K 0001403161-21-000072)
0001403161,class B,V,1.6059,2022-06-29,2022-12-29,effective 2022-06-29 (8-K 0001403161-22-000045)
0001403161,class B,V,1.5991,2022-12-29,2023-06-28,effective 2022-12-29 (8-K 0001403161-23-000003)
0001403161,class B,V,1.5902,2023-06-28,2023-09-28,effective 2023-06-28 (8-K 0001403161-23-000064)
0001403161,class B,V,1.5875,2023-09-28,,effective 2023-09-28 (8-K 0001403161-23-000085); class B renamed B-1 in January 2024
0001403161,class B-1,V,1.5875,2024-01-01,2024-09-26,class B renamed B-1 (8-K 0001403161-24-000005); rate per 8-K 0001403161-24-000050
0001403161,class B-1,V,1.5653,2024-09-26,2025-03-27,effective 2024-09-26 (8-K 0001403161-24-000050)
0001403161,class B-1,V,1.5609,2025-03-27,2025-09-25,effective 2025-03-27 (8-K 0001403161-25-000028)
0001403161,class B-1,V,1.5549,2025-09-25,2025-12-23,effective 2025-09-25 (8-K 0001403161-25-000061)
0001403161,class B-1,V,1.5491,2025-12-23,2026-02-26,effective 2025-12-23 (8-K 0001403161-25-000137)
0001403161,class B-1,V,1.5475,2026-02-26,2026-06-25,effective 2026-02-26 (8-K 0001403161-26-000063)
0001403161,class B-1,V,1.5445,2026-06-25,2026-09-18,effective 2026-06-25 (8-K 0001403161-26-000086)
0001403161,class B-1,V,1.5400,2026-09-18,,effective 2026-09-18 (8-K 0001403161-26-000121)
0001403161,class B-2,V,1.5875,2024-01-01,2024-09-26,class B-2 issued in the exchange offer settled 2024-05-08 (8-K 0001193125-24-133824) at the B-1 rate (8-K 0001403161-24-000050)
0001403161,class B-2,V,1.5430,2024-09-26,2025-03-27,effective 2024-09-26 (8-K 0001403161-24-000050)
0001403161,class B-2,V,1.5342,2025-03-27,2025-09-25,effective 2025-03-27 (8-K 0001403161-25-000028)
0001403161,class B-2,V,1.5223,2025-09-25,2025-12-23,effective 2025-09-25 (8-K 0001403161-25-000061)
0001403161,class B-2,V,1.5108,2025-12-23,2026-02-26,effective 2025-12-23 (8-K 0001403161-25-000137)
0001403161,class B-2,V,1.5075,2026-02-26,2026-06-25,effective 2026-02-26 (8-K 0001403161-26-000063)
0001403161,class B-2,V,1.5014,2026-06-25,2026-09-18,effective 2026-06-25 (8-K 0001403161-26-000086)
0001403161,class B-2,V,1.4924,2026-09-18,,effective 2026-09-18 (8-K 0001403161-26-000121)
0001403161,class B-3,V,1.5075,2026-01-01,2026-06-25,class B-3 issued in the exchange offer settled 2026-05-12 (8-K 0001193125-26-219432); initial rate per 8-K 0001403161-26-000086
0001403161,class B-3,V,1.4953,2026-06-25,2026-09-18,effective 2026-06-25 (8-K 0001403161-26-000086)
0001403161,class B-3,V,1.4773,2026-09-18,,effective 2026-09-18 (8-K 0001403161-26-000121)
0001403161,class C,V,1,2008-03-19,2015-03-19,class C converts share for share into class A before the 2015 split (8-K 0001193125-15-025534)
0001403161,class C,V,4,2015-03-19,,class C converts into 4 class A from the 4-for-1 split of 2015-03-19 (8-K 0001193125-15-025534)
0001437107,class A,WBD,1,2008-09-17,2022-04-08,Discovery series A traded as DISCA (WBD in the store's names); series C is DISCK; both index members (10-Q 0001437107-12-000015)
0001437107,class B,WBD,1,2008-09-17,2022-04-08,series B converts share for share into series A (10-Q 0001437107-12-000015)
0001437107,class C,DISCK,1,2008-09-17,2022-04-08,series C is DISCK; the classes became one WBD common stock at the WarnerMedia close of 2022-04-08 (10-Q 0001437107-12-000015)
0001467373,class A,ACN,1,2009-09-01,,Accenture plc class A ordinary shares are ACN (10-Q 0001467373-12-000009)
0001467373,class X,ACN,0,2009-09-01,,class X ordinary shares carry votes and no economic interest (10-Q 0001467373-12-000009 tags acn:CommonClassXMember)
0001560385,class A,LMCA,1,2014-07-01,2016-04-15,series C (LMCK) created by the dividend of 2014-07-23; from then series A is LMCA (10-Q 0001560385-14-000067); earlier both answer the whole company
0001560385,class B,LMCA,1,2014-07-01,2016-04-15,series B converts share for share into series A (10-Q 0001560385-14-000067)
0001560385,class C,LMCK,1,2014-07-01,2016-04-15,series C is LMCK (10-Q 0001560385-14-000067)
0001560385,LibertyMediaGroupMember CommonClassAMember,LMCA,1,2016-04-15,2017-01-01,the 2016-04-15 recapitalization into three tracking groups on lmca:EconomicPerformanceGroupAxis; Liberty Media group series A kept LMCA (10-Q 0001558370-16-005688)
0001560385,LibertyMediaGroupMember CommonClassBMember,LMCA,1,2016-04-15,2017-01-01,Liberty Media group series B converts into series A (10-Q 0001558370-16-005688)
0001560385,LibertyMediaGroupMember CommonClassCMember,LMCK,1,2016-04-15,2017-01-01,Liberty Media group series C kept LMCK (10-Q 0001558370-16-005688)
0001560385,LibertyBravesGroupMember CommonClassAMember,BATRA,1,2016-04-15,2017-01-01,Liberty Braves group series A is BATRA (10-Q 0001558370-16-005688)
0001560385,LibertyBravesGroupMember CommonClassBMember,BATRA,1,2016-04-15,2017-01-01,Liberty Braves group series B converts into series A (10-Q 0001558370-16-005688)
0001560385,LibertyBravesGroupMember CommonClassCMember,BATRK,1,2016-04-15,2017-01-01,Liberty Braves group series C is BATRK (10-Q 0001558370-16-005688)
0001560385,LibertySiriusXmGroupMember CommonClassAMember,LMCA,0,2016-04-15,2017-01-01,Liberty SiriusXM group (LSXMA) is never an index member: no claim on LMCA (10-Q 0001558370-16-005688)
0001560385,LibertySiriusXmGroupMember CommonClassBMember,LMCA,0,2016-04-15,2017-01-01,Liberty SiriusXM group series B: no claim on LMCA (10-Q 0001558370-16-005688)
0001560385,LibertySiriusXmGroupMember CommonClassCMember,LMCA,0,2016-04-15,2017-01-01,Liberty SiriusXM group series C (LSXMK): no claim on LMCA (10-Q 0001558370-16-005688)
0001564708,class A,NWSA,1,2015-07-01,,NWS (class B voting) joined the S&P 500 2015-09-21; from the count of the 2015 10-K class A answers NWSA and class B NWS; earlier NWSA answers the whole company (10-Q 0001193125-15-369166)
0001564708,class B,NWS,1,2015-07-01,,class B voting is NWS (10-Q 0001193125-15-369166)
0001570585,ClassOrdinarySharesMember,LBTYA,1,2014-09-01,,Liberty Global's own member name for class A (lbtya:ClassOrdinarySharesMember in 10-Q 0001570585-14-000197); LBTYK joined the Nasdaq-100 2014-12-22; earlier LBTYA answers the whole company
0001570585,class A,LBTYA,1,2014-09-01,,class A spelled as us-gaap would
0001570585,class B,LBTYA,1,2014-09-01,,class B converts share for share into class A (10-Q 0001570585-14-000197)
0001570585,class C,LBTYK,1,2014-09-01,,class C is LBTYK (10-Q 0001570585-14-000197)
0001570585,LibertyGlobalGroupMember ClassOrdinarySharesMember,LBTYA,1,2015-07-01,2018-01-01,the LiLAC tracking stock (2015-07-01 to the 2017-12-29 split-off) adds us-gaap:StatementBusinessSegmentsAxis; Liberty Global group class A (10-Q 0001570585-16-000637)
0001570585,LibertyGlobalGroupMember ClassAOrdinarySharesMember,LBTYA,1,2015-07-01,2018-01-01,Liberty Global group class A spelled with its letter
0001570585,LibertyGlobalGroupMember ClassBOrdinarySharesMember,LBTYA,1,2015-07-01,2018-01-01,Liberty Global group class B converts into class A (10-Q 0001570585-16-000637)
0001570585,LibertyGlobalGroupMember ClassCOrdinarySharesMember,LBTYK,1,2015-07-01,2018-01-01,Liberty Global group class C is LBTYK (10-Q 0001570585-16-000637)
0001570585,LiLACGroupMember ClassOrdinarySharesMember,LILA,1,2015-07-01,2018-01-01,LiLAC group class A is LILA (10-Q 0001570585-16-000637)
0001570585,LiLACGroupMember ClassAOrdinarySharesMember,LILA,1,2015-07-01,2018-01-01,LiLAC group class A spelled with its letter
0001570585,LiLACGroupMember ClassBOrdinarySharesMember,LILA,1,2015-07-01,2018-01-01,LiLAC group class B converts into class A (10-Q 0001570585-16-000637)
0001570585,LiLACGroupMember ClassCOrdinarySharesMember,LILAK,1,2015-07-01,2018-01-01,LiLAC group class C is LILAK (10-Q 0001570585-16-000637)
0001652044,class A,GOOGL,1,2015-10-02,,Alphabet took over Google's classes at the holding company reorganization of 2015-10-02 (10-Q 0001652044-16-000021)
0001652044,class B,GOOGL,1,2015-10-02,,class B is unlisted and converts share for share into class A (10-Q 0001652044-16-000021)
0001652044,class C,GOOG,1,2015-10-02,,class C (goog:CapitalClassCMember) is GOOG (10-Q 0001652044-16-000021)
0001754301,class A,FOXA,1,2019-03-01,,Fox Corp class A non-voting is FOXA (10-Q 0001564590-19-018565)
0001754301,class B,FOX,1,2019-03-01,,Fox Corp class B voting is FOX (10-Q 0001564590-19-018565)
```
**Impact:** read by `history.load` and `store.history_for` from Step 3/4 on. Nothing else.

### Step 3: `history.py` — third source and attribution
**File:** `engine/src/seer_engine/shares/history.py` (whole file; the changed regions are listed in the Files table)
**Change:** replace the file with exactly this content. Unchanged: the csv I/O (`ShareRow`,
`load_rows`, `check_rows`, `write_rows`, `parse_classes`), `xbrl_by_symbol`, `_Xbrl`, and the
market-value helpers.
**Code:**
```python
"""Point-in-time shares outstanding, 1996-today, and the market value they imply.

Vendored sources (``engine/data``, documented in ``SOURCES.md``):

* ``shares_outstanding_pre2009.csv`` -- ``cik,symbol,filed,as_of,form,accession,shares,classes,
  flags,note``. One row per 10-K/10-Q of an S&P 500 member's filer, filed 1995-10 through
  2010-12, with the share count its cover page states. Built by ``python -m seer_engine shares
  build`` from EDGAR (``shares.cover`` parses, ``shares.checks`` validates); every value a check
  flagged and that was kept says why in ``note``, and every value a check threw out is listed,
  with its reason, in ``shares_outstanding_pre2009_excluded.csv`` instead.
* ``shares_xbrl_classes.csv`` (``shares.classes``) -- one row per 10-K/10-Q filed from 2009 whose
  share count ``companyfacts`` cannot give: the filing's own XBRL instance read with its class
  axis, ``classes`` per class member. Passed in as ``class_rows``.
* ``share_classes.csv`` (``shares.class_table``) -- which listed symbol each class of a
  multi-class filer stands for, and at what ratio. Passed in as ``table``.

**Two dates, and only one of them is an availability date.** ``as_of`` is the day the filer
counted ("As of March 2, 1997, ... outstanding"), usually weeks after the period ended and days
before filing. ``filed`` is the day EDGAR disseminated the report. A figure is usable on day t
only when ``filed <= t`` -- never from its ``as_of``, which would read a count the market had not
yet been told. :meth:`SharesHistory.latest` enforces exactly that and nothing looser, the same
rule ``fundamentals.panel`` applies to XBRL facts. ``as_of`` is still needed: a split between the
count and the day it is used changes what the count means (:func:`market_value`).

**One API across the 2009 seam, three readings of one cover.** XBRL's
``dei:EntityCommonStockSharesOutstanding`` is the same cover-page figure, tagged. The store's
``fundamentals.csv`` carries it per symbol from 2009 (source ``xbrl``) -- but ``companyfacts``,
where that file comes from, drops every fact tagged with a class axis, so a filer that states its
count per class (Meta, Visa, Alphabet from 2014, Berkshire) has none there. Those filings are read
from their own instance documents instead (source ``xbrl-class``). :meth:`SharesHistory.shares_on`
takes all three, resolves ``symbol`` to its filer on the day asked through the date-scoped ticker
map (never a bare ticker; ``cik``'s docstring), and returns whichever figure was filed last. Filed
the same day -- the same report, read more than once -- the per-class reading wins, then the
companyfacts tag, then the cover text: each is the more complete reading of the one before.

**One company, one size.** A per-class or cover reading lists its classes. Where the class table
has no row for the filer on the count's date the classes are summed and every symbol of the
filer answers the whole company, as before the table existed. Where it has rows, each symbol
answers only the classes the table attributes to it, each times its ratio (``class_table``'s
docstring): Berkshire's class A counts 1,500 class B shares toward BRK.B, GOOGL answers class A
and B and GOOG class C. A figure the table cannot attribute is not answered, and why is kept in
:attr:`SharesHistory.problems`.

**Market value needs the unadjusted close, and the splits since the count.** A count of
pre-split shares times a post-split price is half the company after a 2-for-1. So
``market_value = shares x (product of split ratios after as_of, through t) x raw close(t)``. The
research stores keep only split-adjusted closes and no split list; :func:`unadjust` rebuilds the
raw close from an adjusted one given the splits that adjusted it, and the result says so in the
caller's hands, not here.

Nothing in this module reads the network, the clock or the database.
"""

from __future__ import annotations

import bisect
import csv
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Protocol

from seer_engine import cik as cikmod
from seer_engine.cik import CikError
from seer_engine.shares import class_table
from seer_engine.shares.class_table import ClassTable

DATA_DIR = cikmod.DATA_DIR
SHARES_FILE = "shares_outstanding_pre2009.csv"
EXCLUDED_FILE = "shares_outstanding_pre2009_excluded.csv"

HEADER: tuple[str, ...] = (
    "cik", "symbol", "filed", "as_of", "form", "accession", "shares", "classes", "flags", "note",
)
EXCLUDED_HEADER: tuple[str, ...] = (
    "cik", "symbol", "filed", "as_of", "form", "accession", "shares", "reason",
)

#: Filing dates the csv may hold (``edgar_index`` horizon).
FIRST_FILED = date(1995, 10, 1)
LAST_FILED = date(2010, 12, 31)
#: ``as_of`` bounds relative to ``filed`` (``cover.MAX_AGE_DAYS`` / ``MAX_LEAD_DAYS``).
AS_OF_MAX_AGE = 200
AS_OF_MAX_LEAD = 10
#: A figure older than this on the day asked is not answered: a filer that stopped reporting
#: (taken private, merged away) must not keep a size forever. Two missed quarterly reports and
#: then some.
DEFAULT_MAX_AGE_DAYS = 400

#: The tags read from XBRL, in preference order (``fundamentals.ladder.SHARES_OUTSTANDING``).
XBRL_TAGS: tuple[str, ...] = ("EntityCommonStockSharesOutstanding", "CommonStockSharesOutstanding")

SOURCE_COVER = "edgar-cover"
SOURCE_XBRL = "xbrl"
SOURCE_XBRL_CLASS = "xbrl-class"
#: Which reading wins when two were filed the same day (higher wins): the per-class instance
#: reading has every class, the companyfacts tag may have lost some, the cover text was parsed.
SOURCE_RANK = {SOURCE_COVER: 0, SOURCE_XBRL: 1, SOURCE_XBRL_CLASS: 2}


class SharesError(ValueError):
    """The vendored shares data is inconsistent."""


@dataclass(frozen=True, order=True)
class ShareRow:
    """One filing's cover count. ``classes`` is ``((label, shares), ...)``; empty for one class."""

    cik: str
    filed: date
    accession: str
    symbol: str
    as_of: date | None
    form: str
    shares: int
    classes: tuple[tuple[str, int], ...]
    flags: tuple[str, ...]
    note: str


@dataclass(frozen=True)
class Observation:
    """What :meth:`SharesHistory.shares_on` answers."""

    symbol: str
    on: date
    shares: float
    as_of: date | None  # when the filer counted; None when the cover gave no date
    filed: date  # when it became public: always <= ``on``
    source: str  # SOURCE_COVER, SOURCE_XBRL or SOURCE_XBRL_CLASS
    accession: str
    cik: str | None

    @property
    def age_days(self) -> int:
        """Days from the count (or, without one, from filing) to ``on``."""
        return (self.on - (self.as_of or self.filed)).days


class XbrlFact(Protocol):
    """The fields read from a ``fundamentals.Fact`` (or anything shaped like one)."""

    symbol: str
    tag: str
    period_end: date
    val: float
    accn: str
    filed: date


class ClassReading(Protocol):
    """The fields read from a ``classes.ClassRow`` (one filing's XBRL instance, per class).

    ``shares`` is the whole-company figure (the tagged total, else the classes summed);
    ``classes`` is ``((member, count), ...)``, empty when the instance had no class axis.
    """

    cik: str
    filed: date
    accession: str
    as_of: date | None
    shares: int
    classes: tuple[tuple[str, int], ...]


class SplitLike(Protocol):
    """A split: ``ratio`` new shares per old (2.0 for 2-for-1), effective from ``date``."""

    date: date
    ratio: float


# --- the csv ----------------------------------------------------------------------------


def _date(raw: str, where: str) -> date:
    try:
        return date.fromisoformat(raw.strip())
    except ValueError as exc:
        raise SharesError(f"{where}: bad date {raw!r}") from exc


def format_classes(classes: Sequence[tuple[str, int]]) -> str:
    return ";".join(f"{label}={n}" for label, n in classes)


def parse_classes(raw: str, where: str) -> tuple[tuple[str, int], ...]:
    out: list[tuple[str, int]] = []
    for part in filter(None, (raw or "").split(";")):
        label, sep, n = part.rpartition("=")
        if not sep or not label.strip() or not n.isdigit() or int(n) <= 0:
            raise SharesError(f"{where}: bad class entry {part!r}")
        out.append((label.strip(), int(n)))
    return tuple(out)


def load_rows(path: Path) -> list[ShareRow]:
    """Read and validate the vendored csv (invariants in :func:`check_rows`)."""
    rows: list[ShareRow] = []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if tuple(reader.fieldnames or ()) != HEADER:
            raise SharesError(f"{path}: expected header {','.join(HEADER)}, got {reader.fieldnames}")
        for lineno, raw in enumerate(reader, start=2):
            where = f"{path.name}:{lineno}"
            key = (raw["cik"] or "").strip()
            if len(key) != 10 or not key.isdigit():
                raise SharesError(f"{where}: cik must be 10 digits, got {key!r}")
            shares_text = (raw["shares"] or "").strip()
            if not shares_text.isdigit():
                raise SharesError(f"{where}: shares must be a positive integer, got {shares_text!r}")
            as_of_text = (raw["as_of"] or "").strip()
            rows.append(ShareRow(
                cik=key,
                filed=_date(raw["filed"], where),
                accession=(raw["accession"] or "").strip(),
                symbol=(raw["symbol"] or "").strip(),
                as_of=_date(as_of_text, where) if as_of_text else None,
                form=(raw["form"] or "").strip(),
                shares=int(shares_text),
                classes=parse_classes(raw["classes"], where),
                flags=tuple(f for f in (raw["flags"] or "").split(";") if f),
                note=(raw["note"] or "").strip(),
            ))
    check_rows(rows, path.name)
    return rows


def check_rows(rows: Sequence[ShareRow], name: str = SHARES_FILE) -> None:
    """The csv invariants: sorted by (cik, filed, accession) and unique per (cik, accession);
    a positive count equal to the sum of its classes (when listed, at least two); a filing date
    inside the horizon; an as-of date within [filed - 200 d, filed + 10 d]; an accession in
    EDGAR's shape; a note on every row whose flags say a value was changed."""
    if not rows:
        raise SharesError(f"{name}: no rows")
    seen: set[tuple[str, str]] = set()
    prev: tuple[str, date, str] | None = None
    for i, r in enumerate(rows, start=2):
        where = f"{name}:{i}"
        key = (r.cik, r.filed, r.accession)
        if prev is not None and key < prev:
            raise SharesError(f"{where}: rows must be sorted by (cik, filed, accession)")
        prev = key
        if (r.cik, r.accession) in seen:
            raise SharesError(f"{where}: duplicate {r.cik} {r.accession}")
        seen.add((r.cik, r.accession))
        parts = r.accession.split("-")
        if len(parts) != 3 or [len(p) for p in parts] != [10, 2, 6] or not all(p.isdigit() for p in parts):
            raise SharesError(f"{where}: bad accession {r.accession!r}")
        if r.shares <= 0:
            raise SharesError(f"{where}: shares must be positive")
        if r.classes:
            if len(r.classes) < 2:
                raise SharesError(f"{where}: classes lists one class; leave it empty instead")
            if sum(n for _, n in r.classes) != r.shares:
                raise SharesError(f"{where}: classes sum to {sum(n for _, n in r.classes)}, "
                                  f"shares is {r.shares}")
        if not (FIRST_FILED <= r.filed <= LAST_FILED):
            raise SharesError(f"{where}: filed {r.filed} outside {FIRST_FILED}..{LAST_FILED}")
        if r.as_of is not None and not (
            r.filed - timedelta(days=AS_OF_MAX_AGE) <= r.as_of <= r.filed + timedelta(days=AS_OF_MAX_LEAD)
        ):
            raise SharesError(f"{where}: as_of {r.as_of} too far from filed {r.filed}")
        if any(f.startswith("fixed") for f in r.flags) and not r.note:
            raise SharesError(f"{where}: a fixed value needs a note saying why")


def write_rows(path: Path, rows: Iterable[ShareRow]) -> int:
    ordered = sorted(rows, key=lambda r: (r.cik, r.filed, r.accession))
    check_rows(ordered, path.name)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(HEADER)
        for r in ordered:
            w.writerow([
                r.cik, r.symbol, r.filed.isoformat(), r.as_of.isoformat() if r.as_of else "",
                r.form, r.accession, r.shares, format_classes(r.classes), ";".join(r.flags), r.note,
            ])
    return len(ordered)


# --- the lookup -------------------------------------------------------------------------


@dataclass(frozen=True)
class _Xbrl:
    filed: date
    accession: str
    period_end: date
    shares: float


def xbrl_by_symbol(facts: Iterable[XbrlFact]) -> dict[str, tuple[_Xbrl, ...]]:
    """XBRL share facts per symbol, one per accession, ascending by (filed, accession).

    Within an accession the preferred tag's latest ``period_end`` is used. Several values for
    that one (tag, period) are separate share classes reported without a class axis and are
    summed; the same value repeated is counted once.
    """
    by: dict[tuple[str, str], list[XbrlFact]] = {}
    for f in facts:
        if f.tag in XBRL_TAGS and math.isfinite(f.val) and f.val > 0:
            by.setdefault((f.symbol, f.accn), []).append(f)
    out: dict[str, list[_Xbrl]] = {}
    for (symbol, accn), group in by.items():
        rank = min(XBRL_TAGS.index(f.tag) for f in group)
        best = [f for f in group if XBRL_TAGS.index(f.tag) == rank]
        end = max(f.period_end for f in best)
        vals = sorted({f.val for f in best if f.period_end == end})
        out.setdefault(symbol, []).append(
            _Xbrl(min(f.filed for f in best), accn, end, float(sum(vals)))
        )
    return {s: tuple(sorted(v, key=lambda x: (x.filed, x.accession))) for s, v in out.items()}


class SharesHistory:
    """Cover rows and per-class XBRL rows by filer, plus companyfacts XBRL facts by symbol,
    queried point in time and attributed to the asked symbol through the class table."""

    def __init__(
        self,
        rows: Iterable[ShareRow],
        index: Mapping[str, Sequence[cikmod.CikRow]],
        xbrl: Iterable[XbrlFact] = (),
        *,
        max_age_days: int | None = DEFAULT_MAX_AGE_DAYS,
        class_rows: Iterable[ClassReading] = (),
        table: ClassTable | None = None,
    ) -> None:
        by: dict[str, list[ShareRow]] = {}
        for r in rows:
            by.setdefault(r.cik, []).append(r)
        self._rows = {k: sorted(v, key=lambda r: (r.filed, r.accession)) for k, v in by.items()}
        self._filed = {k: [r.filed for r in v] for k, v in self._rows.items()}
        self._xbrl = xbrl_by_symbol(xbrl)
        self._xfiled = {k: [x.filed for x in v] for k, v in self._xbrl.items()}
        cby: dict[str, list[ClassReading]] = {}
        for c in class_rows:
            if c.shares > 0:
                cby.setdefault(c.cik, []).append(c)
        self._class_rows = {k: sorted(v, key=lambda c: (c.filed, c.accession)) for k, v in cby.items()}
        self._cfiled = {k: [c.filed for c in v] for k, v in self._class_rows.items()}
        self.table = table if table is not None else ClassTable()
        self.index = index
        self.max_age_days = max_age_days
        #: ``(cik, accession, symbol) -> why`` for every reading that won on some day asked but
        #: that the class table could not attribute to the symbol (answered as unknown).
        self.problems: dict[tuple[str, str, str], str] = {}
        #: Filers whose winning reading listed several classes on a count date the class table
        #: has no row for: summed one for one, every symbol the whole company (``class_table``'s
        #: docstring). Reported by ``shares store``, never refused.
        self.summed: set[str] = set()
        self._attributed: dict[tuple[str, str, str | None, str], float | None] = {}

    def latest(self, cik: str, on: date) -> ShareRow | None:
        """The cover row of ``cik`` filed last on or before ``on`` (never one filed after)."""
        filed = self._filed.get(cik)
        if not filed:
            return None
        i = bisect.bisect_right(filed, on) - 1
        return self._rows[cik][i] if i >= 0 else None

    def latest_class(self, cik: str, on: date) -> ClassReading | None:
        """The per-class XBRL row of ``cik`` filed last on or before ``on``."""
        filed = self._cfiled.get(cik)
        if not filed:
            return None
        i = bisect.bisect_right(filed, on) - 1
        return self._class_rows[cik][i] if i >= 0 else None

    def _latest_xbrl(self, symbol: str, on: date) -> _Xbrl | None:
        filed = self._xfiled.get(symbol)
        if not filed:
            return None
        i = bisect.bisect_right(filed, on) - 1
        return self._xbrl[symbol][i] if i >= 0 else None

    def _attribute(
        self,
        source: str,
        accession: str,
        cik: str | None,
        symbol: str,
        counted: date,
        total: float,
        classes: Sequence[tuple[str, int]],
    ) -> float | None:
        """``class_table.ClassTable.attribute`` for one reading, memoised; a problem is kept."""
        key = (source, accession, cik, symbol)
        if key in self._attributed:
            return self._attributed[key]
        got = self.table.attribute(cik, symbol, counted, total, classes)
        if got.problem is not None and cik is not None:
            self.problems[(cik, accession, symbol)] = got.problem
        elif cik is not None and len(classes) >= 2 and not self.table.rules(cik, counted):
            self.summed.add(cik)
        self._attributed[key] = got.shares
        return got.shares

    def shares_on(self, symbol: str, on: date) -> Observation | None:
        """The share count public on ``on`` for the company -- or, where the class table splits
        it, the listed class -- trading as ``symbol`` that day.

        None when no source has a figure filed on or before ``on``, when the newest one is older
        than ``max_age_days``, or when the class table cannot attribute it to ``symbol``.
        """
        try:
            row_cik = cikmod.resolve(symbol, on, self.index)
        except CikError:
            row_cik = None
        # (filed, rank) of the winner so far, and its reading:
        # (source, accession, as_of, filed, whole-company shares, classes).
        best: tuple[date, int] | None = None
        pick: tuple[str, str, date | None, date, float, tuple[tuple[str, int], ...]] | None = None
        cover = self.latest(row_cik, on) if row_cik else None
        if cover is not None:
            best = (cover.filed, SOURCE_RANK[SOURCE_COVER])
            pick = (SOURCE_COVER, cover.accession, cover.as_of, cover.filed, float(cover.shares),
                    cover.classes)
        # Filed later wins; filed the same day (the same report, read twice) the richer reading wins.
        x = self._latest_xbrl(symbol, on)
        if x is not None and (best is None or (x.filed, SOURCE_RANK[SOURCE_XBRL]) > best):
            best = (x.filed, SOURCE_RANK[SOURCE_XBRL])
            pick = (SOURCE_XBRL, x.accession, x.period_end, x.filed, x.shares, ())
        k = self.latest_class(row_cik, on) if row_cik else None
        if k is not None and (best is None or (k.filed, SOURCE_RANK[SOURCE_XBRL_CLASS]) > best):
            best = (k.filed, SOURCE_RANK[SOURCE_XBRL_CLASS])
            pick = (SOURCE_XBRL_CLASS, k.accession, k.as_of, k.filed, float(k.shares), tuple(k.classes))
        if pick is None:
            return None
        source, accession, as_of, filed, total, classes = pick
        if self.max_age_days is not None and (on - (as_of or filed)).days > self.max_age_days:
            return None
        shares = self._attribute(source, accession, row_cik, symbol, as_of or filed, total, classes)
        if shares is None:
            return None
        return Observation(symbol, on, shares, as_of, filed, source, accession, row_cik)


def load(
    data_dir: Path = DATA_DIR,
    xbrl: Iterable[XbrlFact] = (),
    *,
    max_age_days: int | None = DEFAULT_MAX_AGE_DAYS,
    class_rows: Iterable[ClassReading] = (),
) -> SharesHistory:
    """The vendored cover rows, ticker map and class table, plus any XBRL facts and per-class
    rows given."""
    return SharesHistory(
        load_rows(data_dir / SHARES_FILE),
        cikmod.load_index_with_history(data_dir),
        xbrl,
        max_age_days=max_age_days,
        class_rows=class_rows,
        table=class_table.load_table(data_dir / class_table.TABLE_FILE),
    )


# --- market value -----------------------------------------------------------------------


def split_factor(splits: Iterable[SplitLike], after: date, through: date) -> float:
    """Product of the ratios of the splits effective in ``(after, through]``.

    A split's ``date`` is its ex-date, the first session priced post-split. A count dated before
    it is in pre-split shares; one dated on or after it, post-split.
    """
    f = 1.0
    for s in splits:
        if after < s.date <= through:
            f *= float(s.ratio)
    return f


def shares_at(obs: Observation, on: date, splits: Iterable[SplitLike]) -> float:
    """``obs``'s count restated in the share units of ``on`` (splits since the count applied)."""
    return obs.shares * split_factor(splits, obs.as_of or obs.filed, on)


def market_value(obs: Observation, on: date, raw_close: float, splits: Iterable[SplitLike]) -> float:
    """Shares x **unadjusted** close on ``on``, the count carried across any split since it."""
    if not (raw_close > 0 and math.isfinite(raw_close)):
        raise ValueError(f"raw_close must be a positive price, got {raw_close!r}")
    return shares_at(obs, on, splits) * raw_close


def unadjust(adj_close: float, on: date, splits: Iterable[SplitLike], basis: date = date.max) -> float:
    """The raw close behind a split-adjusted one: multiplied back by every split after ``on``
    up to the adjustment's ``basis`` date (the series' last date; open-ended by default)."""
    return adj_close * split_factor(splits, on, basis)
```
**Impact:** `SharesHistory(...)` calls without the new keywords behave exactly as before (empty
table: `attribute` returns the reading's total; no per-class rows; `SOURCE_RANK` reproduces "XBRL
wins a same-day tie"). `history.load()` now needs `engine/data/share_classes.csv` (Step 2).

### Step 4: `store.py` — the new source in candidates, readers and `history_for`
**File:** `engine/src/seer_engine/shares/store.py` (`:1-20`, `:44`, `:48`, `:80-81`, `:382-388`)
**Change:** apply exactly this diff.
**Code:**
```diff
--- a/engine/src/seer_engine/shares/store.py
+++ b/engine/src/seer_engine/shares/store.py
@@ -2,8 +2,9 @@
 
 Company size on day t is ``shares x the close as it printed on t``. Both halves have to be in the
 store, fingerprinted, for a lab trial that ranks on size to be reproducible: the share history
-(``engine/data/shares_outstanding_pre2009.csv`` joined to the store's XBRL facts through the
-date-scoped ticker map, ``history.SharesHistory``) and the split list that turns the store's
+(``engine/data/shares_outstanding_pre2009.csv`` and ``shares_xbrl_classes.csv`` joined to the
+store's XBRL facts through the date-scoped ticker map and attributed to each listed class through
+``share_classes.csv``, ``history.SharesHistory``) and the split list that turns the store's
 split-adjusted closes back into printed ones (``splits`` module docstring).
 
 ``shares.csv`` -- ``symbol,from,shares,counted,filed,source,accession``, sorted by symbol then
@@ -11,10 +12,12 @@
 from ``from`` until the symbol's next row, with ``shares`` (and the rest) empty where the answer is
 "unknown" (no figure filed yet, the newest one older than 400 days, or no filer behind the ticker
 that day). Writing the resolved answers instead of the raw filings is what lets the reader be a
-bisect: the join rule (later filing wins, XBRL wins a same-day tie), the ticker-to-filer map and the
-age limit are applied once, here, and a store reader can never apply them differently. The rows are
-exact, not sampled: ``shares_on``'s answer can only change on a filing date, a ticker-map boundary
-or the day a figure ages out, and :func:`change_points` evaluates it on every one of those days
+bisect: the join rule (later filing wins; a same-day tie goes to the per-class reading, then the
+companyfacts tag), the ticker-to-filer map, the class table and the age limit are applied once,
+here, and a store reader can never apply them differently. The rows are exact, not sampled:
+``shares_on``'s answer can only change on a filing date, a ticker-map boundary or the day a figure
+ages out -- the class table is keyed on each figure's own count date, so it adds no day of its
+own -- and :func:`change_points` evaluates it on every one of those days
 (``tests/test_shares_store.py`` checks it against a day-by-day evaluation). ``from >= filed`` on
 every row: nothing is readable before it was public.
 
@@ -41,11 +44,11 @@
 
 from seer_engine import cik as cikmod
 from seer_engine.backtest.market import ShareCount, ShareCounts
-from seer_engine.shares import history
+from seer_engine.shares import class_table, history
 
 SHARES_HEADER = "symbol,from,shares,counted,filed,source,accession"
 SPLITS_HEADER = "symbol,date,ratio"
-SOURCES = (history.SOURCE_COVER, history.SOURCE_XBRL)
+SOURCES = (history.SOURCE_COVER, history.SOURCE_XBRL, history.SOURCE_XBRL_CLASS)
 
 
 @dataclass(frozen=True)
@@ -79,6 +82,8 @@
             continue
         for r in hist._rows.get(row.cik, ()):
             figures.append((r.filed, r.as_of or r.filed))
+        for k in hist._class_rows.get(row.cik, ()):
+            figures.append((k.filed, k.as_of or k.filed))
     for x in hist._xbrl.get(symbol, ()):
         figures.append((x.filed, x.period_end))
     for filed, counted in figures:
@@ -379,10 +384,18 @@
     return ShareCounts(rows, splits)
 
 
-def history_for(xbrl: Iterable[history.XbrlFact], data_dir: Path = history.DATA_DIR) -> history.SharesHistory:
-    """The vendored cover rows and ticker map joined to ``xbrl``, at the default age limit."""
+def history_for(
+    xbrl: Iterable[history.XbrlFact],
+    data_dir: Path = history.DATA_DIR,
+    *,
+    class_rows: Iterable[history.ClassReading] = (),
+) -> history.SharesHistory:
+    """The vendored cover rows, ticker map and class table joined to ``xbrl`` and the per-class
+    rows, at the default age limit."""
     return history.SharesHistory(
         history.load_rows(data_dir / history.SHARES_FILE),
         cikmod.load_index_with_history(data_dir),
         xbrl,
+        class_rows=class_rows,
+        table=class_table.load_table(data_dir / class_table.TABLE_FILE),
     )
```
**Impact:** `read_shares` now accepts `xbrl-class` rows (a store written with them is refused
by older code: phase 3's concern). `change_points` stays exact (test in Step 7).

### Step 5: `integrate.py` — `--classes` and `--symbols`
**File:** `engine/src/seer_engine/shares/integrate.py` (`:1-22`, `:59`, `:69`, `:151-154`, `:188-189`, `:253`, `:319`)
**Change:** apply exactly this diff. `shares store` refuses (exit 2) when the per-class csv is
absent — it is committed only in phase 3, and writing a store without it would silently drop
every multi-class filer. `store-report --symbols` prints, for each `--dates` day, each symbol's
market value, shares, source, count date and filing date.
**Code:**
```diff
--- a/engine/src/seer_engine/shares/integrate.py
+++ b/engine/src/seer_engine/shares/integrate.py
@@ -7,16 +7,18 @@
 through ``research.refresh_shares``: every other file is carried over byte for byte, so the price
 fingerprint -- the one every recorded lab trial is compared on -- does not move; the store's full
 fingerprint does, as it did for every optional file before. The share rows are the point-in-time
-answers of ``history.SharesHistory`` (the vendored cover-page csv joined to the store's own XBRL
-facts in ``fundamentals.csv``, or ``--xbrl``'s for a store without a panel) for every index member
-of the store's window; the split rows are yfinance's list for every symbol with bars, cut at
+answers of ``history.SharesHistory`` (the vendored cover-page csv and per-class XBRL csv,
+``shares_xbrl_classes.csv`` or ``--classes``, joined to the store's own XBRL facts in
+``fundamentals.csv``, or ``--xbrl``'s for a store without a panel, and attributed to each listed
+class by ``share_classes.csv``) for every index member of the store's window; the split rows are yfinance's list for every symbol with bars, cut at
 ``--basis``, the day the store's bars were downloaded (``splits`` module docstring). The
 survivorship-check store is refused here: its added symbols were adjusted by its own cleaning, so it
 is refreshed by ``survivorship_store --refresh-shares``, which merges their lists in.
 
 ``store-report`` (no network, writes nothing) loads a store and prints what the size accessor
 gives: per year, the share of index member-days with a market value (and, separately, with a share
-count and with a close), the largest companies by market value on chosen dates, and -- the check
+count and with a close), the largest companies by market value on chosen dates, the size of any
+symbols named with ``--symbols`` on those dates (with the source of each count), and -- the check
 that the split list really is the one behind the adjusted closes -- every member-day close rebuilt
 from the store (``adjusted x raw_factor``) against EODHD's raw close for the same day.
 """
@@ -57,6 +59,8 @@
     s.add_argument("--xbrl", type=Path, default=None,
                    help="a fundamentals.csv to join (default: the store's own; required when it has none)")
     s.add_argument("--data-dir", type=Path, default=history.DATA_DIR)
+    s.add_argument("--classes", type=Path, default=None,
+                   help="the per-class XBRL csv to join (default: shares_xbrl_classes.csv in --data-dir)")
     s.add_argument("--evidence-store", type=Path, action="append", default=[],
                    help="another store of the same vendor whose bars run past this one's window (the "
                         "test store, for the dev store): its closes judge the listed splits after the "
@@ -67,6 +71,8 @@
     r.add_argument("--dates", default=",".join(d.isoformat() for d in DEFAULT_REPORT_DATES),
                    help="comma-separated dates for the largest-companies tables")
     r.add_argument("--top", type=int, default=10)
+    r.add_argument("--symbols", default="",
+                   help="comma-separated symbols whose size is printed on each of --dates")
     r.add_argument("--eodhd-cache", type=Path, default=prices.EODHD_CACHE)
     r.add_argument("--edgar-cache", type=Path, default=None,
                    help="the shares download cache (default $SEER_EDGAR_CACHE or engine/.cache/edgar)")
@@ -148,10 +154,21 @@
                   "(the dev store's panel runs to 2026 and serves the test window too)")
             return 2
         xbrl = store / research.FUNDAMENTALS_FILE
+    from seer_engine.shares import classes as xbrl_classes
     from seer_engine.shares.build import read_store_facts
 
-    facts, left_out = share_store.usable_xbrl(read_store_facts(Path(xbrl)))
-    hist = share_store.history_for(facts, Path(args.data_dir))
+    classes_path = Path(args.classes) if args.classes else Path(args.data_dir) / xbrl_classes.CLASSES_FILE
+    if not classes_path.is_file():
+        print(f"shares store: no per-class XBRL csv at {classes_path}; run `shares build-classes` "
+              "first or pass --classes")
+        return 2
+    try:
+        class_rows = xbrl_classes.load_rows(classes_path)
+        facts, left_out = share_store.usable_xbrl(read_store_facts(Path(xbrl)))
+        hist = share_store.history_for(facts, Path(args.data_dir), class_rows=class_rows)
+    except ValueError as exc:
+        print(f"shares store: {exc}")
+        return 2
     members = sorted(set(research.requested_symbols(window=window)) - set(research.RESEARCH_ETFS))
     rows = share_store.change_points(hist, members, history.FIRST_FILED, window.end)
     shares_lines = share_store.shares_lines(rows)
@@ -186,7 +203,15 @@
     )
     print(f"shares store {store} ({window.name} window ending {window.end}):")
     print(f"  {len(members)} index members, {len({r.symbol for r in rows})} with a share count, "
-          f"{len(shares_lines)} share rows ({len(facts)} XBRL share facts joined from {xbrl})")
+          f"{len(shares_lines)} share rows ({len(facts)} XBRL share facts joined from {xbrl}, "
+          f"{len(class_rows)} per-class rows from {classes_path}, {len(hist.table)} class-table rows)")
+    if hist.problems:
+        print(f"  {len(hist.problems)} readings the class table could not attribute, answered as unknown:")
+        for (cik, accession, symbol), why in sorted(hist.problems.items())[:25]:
+            print(f"    {symbol:<6} {cik} {accession}: {why}")
+    if hist.summed:
+        print(f"  {len(hist.summed)} filers with several classes and no class-table row (classes summed "
+              f"one for one, each symbol the whole company): {' '.join(sorted(hist.summed))}")
     for why, dropped_facts in left_out.items():
         if dropped_facts:
             names = sorted({f.symbol for f in dropped_facts})
@@ -250,6 +275,16 @@
     return d, rows[:n]
 
 
+def sizes(
+    data: research.ResearchData, on: date, symbols: list[str]
+) -> tuple[date, list[tuple[str, float | None, float | None, object]]]:
+    """``symbols``' size on the last session on or before ``on``: ``(symbol, market value,
+    shares in that day's units, the ShareCount behind them)``, each None when unknown."""
+    d = dates.sessions(date(on.year - 1, 1, 1), on)[-1]
+    m = data.market
+    return d, [(s, m.market_value(s, d), m.shares_on(s, d), m.shares.count(s, d)) for s in symbols]
+
+
 def split_check(data: research.ResearchData, eodhd_cache: Path, edgar_cache: Path):
     """Rebuilt raw closes vs EODHD's, on member days: (pairs, within 0.5%, within 2%, per-symbol
     median |log ratio| of the symbols beyond 2%, symbols checked)."""
@@ -317,6 +352,18 @@
         print(f"\nLargest {args.top} members by market value on {d}")
         for k, (s, mv, sh) in enumerate(rows, 1):
             print(f"  {k:>2}. {s:<6} ${mv / 1e9:>8.1f}B  ({sh / 1e9:.3f}B shares)")
+    chosen = [s.strip() for s in args.symbols.split(",") if s.strip()]
+    if chosen:
+        for raw in filter(None, args.dates.split(",")):
+            d, rows = sizes(data, date.fromisoformat(raw.strip()), chosen)
+            print(f"\nChosen symbols on {d}")
+            for s, mv, sh, count in rows:
+                if count is None or sh is None:
+                    print(f"  {s:<6} no share count")
+                    continue
+                value = f"${mv / 1e9:>8.1f}B" if mv is not None else "  no close"
+                print(f"  {s:<6} {value}  ({sh / 1e9:.3f}B shares, {count.source}, counted "
+                      f"{count.counted}, filed {count.filed})")
     if not args.no_check:
         from seer_engine.commands.shares import default_cache
 
```
**Impact:** `shares store` now requires `shares_xbrl_classes.csv` (phase 1's `build-classes`
output) or `--classes`. All other flags unchanged (phase 3 relies on that).

### Step 6: `backtest/market.py` — docstrings only
**File:** `engine/src/seer_engine/backtest/market.py` (`:285-294`, `:304-309`)
**Change:** apply exactly this diff. No code changes.
**Code:**
```diff
--- a/engine/src/seer_engine/backtest/market.py
+++ b/engine/src/seer_engine/backtest/market.py
@@ -288,8 +288,12 @@
     ``shares`` is the figure the filer stated, in the share units of ``counted`` -- the day the
     filer counted (the cover's "as of" date, or the filing date when the cover gave none).
     ``filed`` is when it became public, always on or before the day it is read for. ``source``
-    is ``"edgar-cover"`` (a 10-K/10-Q cover page, 1995-2010) or ``"xbrl"`` (the same figure,
-    tagged, 2009 on).
+    is ``"edgar-cover"`` (a 10-K/10-Q cover page, 1995-2010), ``"xbrl"`` (the same figure, tagged,
+    2009 on, from SEC's companyfacts) or ``"xbrl-class"`` (the filing's own XBRL instance read per
+    share class, 2009 on, for filers companyfacts has no count for). Where a filer has several
+    classes the count is the part the symbol's own listed class stands for, in that class's share
+    units (``shares.class_table``): GOOGL and GOOG each answer their own classes, BRK.B counts
+    class A as 1,500 class B shares, so a company is weighted once across its symbols.
     """
 
     shares: float
@@ -304,9 +308,11 @@
     ``rows`` maps a symbol to ``(from_day, ShareCount | None)`` change points, strictly ascending:
     the count public from ``from_day`` until the next row (None: no usable figure from that day).
     The research store writes them already resolved (``shares.store``): a figure counts only from
-    its filing date, the later filing wins, XBRL wins a same-day tie, the symbol is resolved to its
-    filer on each day through the date-scoped ticker map, and a figure older than 400 days is not
-    answered. Nothing here re-derives any of that; it only reads.
+    its filing date, the later filing wins, a same-day tie goes to the per-class XBRL reading and
+    then the companyfacts tag over the cover text, the symbol is resolved to its filer on each day
+    through the date-scoped ticker map, a multi-class filer's classes are attributed to the listed
+    class each stands for, and a figure older than 400 days is not answered. Nothing here
+    re-derives any of that; it only reads.
 
     ``splits`` maps a symbol to ``(dated, after_window)``: the splits the vendor applied to that
     symbol's adjusted closes inside the store's window, ascending ``(ex_date, ratio)``, and the
```
**Impact:** none.

### Step 7: Tests
**File:** `engine/tests/test_share_class_table.py` (new)
**Change:** create with exactly this content. Existing `test_shares.py` and `test_shares_store.py`
are **not** edited and must pass unchanged (the invariant).
**Code:**
```python
"""Multi-class company size: the class table (``shares.class_table``), its vendored csv, the
per-class XBRL rows as a third source in ``history.SharesHistory``, the attribution of classes to
listed symbols, and the store's change points over all of it (no network).

The figures are the filers' own: Meta's 10-Q of 2014-07-24, Alphabet's of 2014-07-25, Berkshire's
of 2012-11-02 and its 2009-2010 covers, Visa's of 2012-07-27, Accenture's of 2012-06-29."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import pytest

from seer_engine import cik as c
from seer_engine import research
from seer_engine.backtest.market import ShareCounts
from seer_engine.shares import class_table as ct
from seer_engine.shares import history
from seer_engine.shares import store as ss

D = date.fromisoformat


@dataclass(frozen=True)
class CR:
    """Shaped like ``shares.classes.ClassRow`` (the per-class XBRL csv's row)."""

    cik: str
    symbol: str
    filed: date
    as_of: date | None
    form: str
    accession: str
    shares: int
    classes: tuple[tuple[str, int], ...]
    tagged_total: bool = False


def cr(cik, filed, as_of, accession, classes, shares=None, symbol="X"):
    return CR(cik, symbol, D(filed), D(as_of) if as_of else None, "10-Q", accession,
              shares if shares is not None else sum(n for _, n in classes), tuple(classes))


@dataclass(frozen=True)
class XF:
    symbol: str
    tag: str
    period_end: date
    val: float
    accn: str
    filed: date


def rule(cik, member, symbol, ratio, start, end=None, note="n"):
    return ct.ClassRule(cik, member, ct.class_key(member), symbol, float(ratio), D(start),
                        D(end) if end else None, note)


def _row(symbol, cik, start, end=None):
    return c.CikRow(symbol, cik, D(start), D(end) if end else None, "X", "manual", "n")


# --- class keys ------------------------------------------------------------------------------


@pytest.mark.parametrize("label, key", [
    ("us-gaap:CommonClassAMember", ("a", "class")),
    ("CommonClassAMember", ("a", "class")),
    ("class a common", ("a", "class")),
    ("class A", ("a", "class")),
    ("series a common", ("a", "class")),
    ("ClassAOrdinarySharesMember", ("a", "class")),
    ("goog:CapitalClassCMember", ("c", "class")),
    ("v:CommonClassB1Member", ("1", "b", "class")),
    ("class B-1", ("1", "b", "class")),
    ("lbtya:ClassOrdinarySharesMember", ("class",)),
    ("cmcsa:ClassaSpecialCommonStockMember", ("classa", "special")),
    ("class a special", ("a", "class", "special")),
    ("LiLACGroupMember+ClassBOrdinarySharesMember", ("b", "class", "group", "lac", "li")),
    ("ClassBOrdinarySharesMember LiLACGroupMember", ("b", "class", "group", "lac", "li")),
    ("us-gaap:CommonStockMember", ()),
])
def test_class_key_reads_member_names_and_cover_text_alike(label, key):
    assert ct.class_key(label) == key


# --- the table -------------------------------------------------------------------------------


def _csv(tmp_path, *lines):
    path = tmp_path / ct.TABLE_FILE
    path.write_text("\n".join([",".join(ct.HEADER), *lines]) + "\n", encoding="utf-8")
    return path


def test_the_loader_reads_spans_and_refuses_what_would_double_count(tmp_path):
    t = ct.load_table(_csv(tmp_path, "0000000001,class A,AAA,30,2009-01-01,2010-01-21,before",
                                     "0000000001,CommonClassAMember,AAA,1500,2010-01-21,,after"))
    assert len(t) == 2 and t.ciks() == {"0000000001"}
    assert [r.ratio for r in t.rules("0000000001", D("2010-01-20"))] == [30.0]
    assert [r.ratio for r in t.rules("0000000001", D("2010-01-21"))] == [1500.0]
    bad = {
        "overlapping": "0000000001,class A,AAA,1,2009-01-01,,x\n0000000001,class a common,BBB,1,2012-01-01,,y",
        "names no class": "0000000001,CommonStockMember,AAA,1,2009-01-01,,x",
        "finite number": "0000000001,class A,AAA,-1,2009-01-01,,x",
        "not after": "0000000001,class A,AAA,1,2009-01-01,2009-01-01,x",
        "note": "0000000001,class A,AAA,1,2009-01-01,,",
        "10 digits": "1,class A,AAA,1,2009-01-01,,x",
        "upper-case": "0000000001,class A,aaa,1,2009-01-01,,x",
    }
    for why, line in bad.items():
        with pytest.raises(ct.ClassTableError, match=why):
            ct.load_table(_csv(tmp_path, line))
    path = tmp_path / "wrong.csv"
    path.write_text("cik,member\n", encoding="utf-8")
    with pytest.raises(ct.ClassTableError, match="header"):
        ct.load_table(path)


def test_attribution_splits_converts_excludes_and_refuses_to_guess():
    t = ct.ClassTable([
        rule("0000000002", "class A", "GGL", 1, "2014-04-03"),
        rule("0000000002", "class B", "GGL", 1, "2014-04-03"),
        rule("0000000002", "class C", "GG", 1, "2014-04-03"),
        rule("0000000003", "class A", "XA", 1, "2009-01-01"),
        rule("0000000003", "class X", "XA", 0, "2009-01-01"),
    ])
    abc = (("CommonClassAMember", 283356281), ("CapitalClassCMember", 338209995),
           ("CommonClassBMember", 54825710))
    day = D("2014-07-17")
    assert t.attribute("0000000002", "GGL", day, 0, abc).shares == 283356281 + 54825710
    assert t.attribute("0000000002", "GG", day, 0, abc).shares == 338209995
    # Before the table speaks, every symbol of the filer is the whole company.
    assert t.attribute("0000000002", "GG", D("2014-01-31"), 500.0, abc[::2]).shares == 500.0
    # No class C in the count: GG is unknown, and that is no problem to report.
    assert t.attribute("0000000002", "GG", day, 0, abc[::2]) == (None, None)
    # Ratio 0: votes without economic interest.
    ax = (("CommonClassAMember", 634800693), ("acn:CommonClassXMember", 44998365))
    assert t.attribute("0000000003", "XA", D("2012-05-31"), 0, ax).shares == 634800693
    # Unknown, and why, rather than a guess.
    assert t.attribute("0000000003", "XA", D("2012-05-31"), 5, ()).problem.startswith("a figure without")
    odd = t.attribute("0000000003", "XA", D("2012-05-31"), 0, ax + (("CommonClassDMember", 3),))
    assert odd.shares is None and "CommonClassDMember" in odd.problem
    assert "names no class" in t.attribute("0000000003", "ZZ", D("2012-05-31"), 0, ax).problem
    # A filer with no row answers its total, classes or not.
    assert t.attribute("0000000009", "M", day, 7.0, abc) == (7.0, None)
    assert t.attribute(None, "M", day, 7.0, ()) == (7.0, None)


# --- the vendored table ---------------------------------------------------------------------


@pytest.fixture(scope="module")
def vendored_table() -> ct.ClassTable:
    return ct.load_table(history.DATA_DIR / ct.TABLE_FILE)


@pytest.fixture(scope="module")
def index():
    return c.load_index_with_history()


def test_every_vendored_row_names_a_symbol_its_filer_traded_as(vendored_table, index):
    tenures = {(r.cik, r.symbol) for g in index.values() for r in g if r.cik}
    rows = [r for k in vendored_table.ciks() for r in vendored_table._by[k]]
    assert len(rows) == len(vendored_table)
    assert {(r.cik, r.symbol) for r in rows} <= tenures


def test_vendored_berkshire_and_visa_ratios(vendored_table):
    brk = "0001067983"
    a = ct.class_key("class A")

    def ratio(cik, key, on):
        (r,) = [r for r in vendored_table.rules(cik, D(on)) if r.key == key]
        return r.ratio

    assert ratio(brk, a, "2010-01-20") == 30.0
    assert ratio(brk, a, "2010-01-21") == 1500.0
    b = ct.class_key("class B")
    assert ratio("0001403161", b, "2012-07-19") == 0.4254
    assert ratio("0001403161", b, "2012-07-24") == 0.4206
    assert ratio("0001403161", b, "2015-03-19") == 1.6483
    assert ratio("0001403161", ct.class_key("class C"), "2015-03-19") == 4.0
    assert ratio("0001467373", ct.class_key("acn:CommonClassXMember"), "2012-05-31") == 0.0


def _vendored_history(index, vendored_table, class_rows=(), rows=(), xbrl=()):
    return history.SharesHistory(rows, index, xbrl, class_rows=class_rows, table=vendored_table)


def test_spot_checks_on_the_filers_own_figures(index, vendored_table):
    meta = cr("0001326801", "2014-07-24", "2014-07-22", "0001326801-14-000032",
              [("CommonClassBMember", 585003514), ("CommonClassAMember", 2015048077)])
    goog = cr("0001288776", "2014-07-25", "2014-07-17", "0001288776-14-000065",
              [("CommonClassAMember", 283356281), ("CapitalClassCMember", 338209995),
               ("CommonClassBMember", 54825710)])
    brk = cr("0001067983", "2012-11-02", "2012-10-25", "0001193125-12-449402",
             [("CommonClassBMember", 1099792631), ("CommonClassAMember", 919298)])
    visa = cr("0001403161", "2012-07-27", "2012-07-19", "0001384108-12-000008",
              [("CommonClassAMember", 527426677), ("CommonClassBMember", 245513385),
               ("CommonClassCMember", 38225522)])
    h = _vendored_history(index, vendored_table, [meta, goog, brk, visa])
    on = D("2014-08-01")
    m = h.shares_on("META", on)
    assert (m.shares, m.source, m.as_of, m.filed) == (2600051591.0, history.SOURCE_XBRL_CLASS,
                                                      D("2014-07-22"), D("2014-07-24"))
    googl, goog_c = h.shares_on("GOOGL", on), h.shares_on("GOOG", on)
    assert (googl.shares, goog_c.shares) == (338181991.0, 338209995.0)
    assert googl.shares + goog_c.shares == goog.shares  # the company, once
    assert h.shares_on("BRK.B", D("2012-11-05")).shares == 919298 * 1500 + 1099792631
    assert h.shares_on("V", D("2012-07-30")).shares == pytest.approx(
        527426677 + 245513385 * 0.4254 + 38225522)
    assert h.problems == {}


def test_berkshire_cover_rows_are_converted_at_the_ratio_of_their_count_date(index, vendored_table):
    def cover(filed, as_of, acc, a, b, label):
        return history.ShareRow("0001067983", D(filed), acc, "BRK.B", D(as_of), "10-Q", a + b,
                                ((f"class a{label}", a), (f"class b{label}", b)), ("multi_class",), "")

    rows = [cover("2009-11-06", "2009-10-29", "0001157523-09-007839", 1056884, 14845356, ""),
            cover("2010-03-01", "2010-02-18", "0001193125-10-043450", 1103764, 814349921, " common")]
    h = _vendored_history(index, vendored_table, rows=rows)
    pre = h.shares_on("BRK.B", D("2010-02-16"))  # the first member day: the pre-split count
    assert (pre.shares, pre.source) == (1056884 * 30 + 14845356, history.SOURCE_COVER)
    # The pre-split count carried across the 50-for-1 class B split meets the post-split one.
    split = [type("S", (), {"date": D("2010-01-21"), "ratio": 50.0})()]
    carried = history.shares_at(pre, D("2010-02-16"), split)
    post = h.shares_on("BRK.B", D("2010-03-01")).shares
    assert post == 1103764 * 1500 + 814349921
    assert abs(carried / post - 1) < 0.1


def test_companyfacts_class_a_alone_loses_to_the_per_class_reading_of_the_same_filing(index, vendored_table):
    acc = "0001193125-12-449402"
    class_a_only = XF("BRK.B", "EntityCommonStockSharesOutstanding", D("2012-10-25"), 919298.0, acc,
                      D("2012-11-02"))
    later = XF("BRK.B", "EntityCommonStockSharesOutstanding", D("2013-01-31"), 900000.0,
               "0001193125-13-000001", D("2013-02-20"))
    k = cr("0001067983", "2012-11-02", "2012-10-25", acc,
           [("CommonClassBMember", 1099792631), ("CommonClassAMember", 919298)])
    h = _vendored_history(index, vendored_table, [k], xbrl=[class_a_only, later])
    same = h.shares_on("BRK.B", D("2012-11-02"))
    assert (same.source, same.shares) == (history.SOURCE_XBRL_CLASS, 919298 * 1500 + 1099792631)
    # A later companyfacts figure still wins by date -- and, with no classes, cannot be split.
    assert h.shares_on("BRK.B", D("2013-02-20")) is None
    assert h.problems[("0001067983", "0001193125-13-000001", "BRK.B")].startswith("a figure without")


# --- the invariant: a filer the new sources do not touch answers as before --------------------

INDEX = {
    "AAA": (_row("AAA", "0000000001", "1990-01-01", "2005-01-01"), _row("AAA", "0000000009", "2005-01-01")),
    "MMM": (_row("MMM", "0000000007", "2008-01-01"),),
    "GGL": (_row("GGL", "0000000002", "2008-01-01"),),
    "GG": (_row("GG", "0000000002", "2008-01-01"),),
}


def srow(filed, shares, as_of=None, cik="0000000001", n=1, classes=()):
    return history.ShareRow(
        cik=cik, filed=D(filed), accession=f"{cik}-{filed[2:4]}-{n:06d}", symbol="AAA",
        as_of=D(as_of) if as_of else None, form="10-Q", shares=shares, classes=tuple(classes),
        flags=(), note="",
    )


ROWS = [
    srow("2000-05-10", 100, "2000-04-30", n=1),
    srow("2003-02-10", 130, None, n=3),
    srow("2005-02-10", 7, "2005-02-01", cik="0000000009", n=5),
    srow("2009-05-01", 9, "2009-04-20", cik="0000000009", n=6),
    srow("2009-05-02", 300, "2009-04-20", cik="0000000002", n=7,
         classes=(("class a", 200), ("class b", 100))),
]
FACTS = [
    XF("AAA", "EntityCommonStockSharesOutstanding", D("2009-04-20"), 9.5, "0000000009-09-000006", D("2009-05-01")),
    XF("AAA", "EntityCommonStockSharesOutstanding", D("2009-10-20"), 11.0, "0000000009-09-000007", D("2009-11-01")),
    XF("GGL", "EntityCommonStockSharesOutstanding", D("2014-01-31"), 360.0, "0000000002-14-000001", D("2014-02-03")),
]
CLASS_ROWS = [
    cr("0000000007", "2012-08-01", "2012-07-25", "0000000007-12-000001", [("CommonClassAMember", 50), ("CommonClassBMember", 25)]),
    cr("0000000007", "2013-08-01", "2013-07-25", "0000000007-13-000001", [("CommonClassAMember", 60), ("CommonClassBMember", 25)]),
    cr("0000000002", "2014-02-03", "2014-01-31", "0000000002-14-000001", [("CommonClassAMember", 250), ("CommonClassBMember", 110)]),
    cr("0000000002", "2014-04-25", "2014-04-20", "0000000002-14-000002",
       [("CommonClassAMember", 250), ("CommonClassBMember", 110), ("CapitalClassCMember", 361)]),
    cr("0000000002", "2014-07-25", "2014-07-20", "0000000002-14-000003",
       [("CommonClassAMember", 251), ("CommonClassBMember", 110), ("CommonClassDMember", 1),
        ("CapitalClassCMember", 362)]),
]
TABLE = ct.ClassTable([
    rule("0000000002", "class A", "GGL", 1, "2014-04-03"),
    rule("0000000002", "class B", "GGL", 1, "2014-04-03"),
    rule("0000000002", "class C", "GG", 1, "2014-04-03"),
])


def _answers(h, symbol, start, end):
    out, d = [], start
    while d <= end:
        o = h.shares_on(symbol, d)
        out.append(None if o is None else (o.shares, o.as_of, o.filed, o.source, o.accession, o.cik))
        d += timedelta(days=1)
    return out


def test_a_filer_with_no_table_rows_and_no_class_rows_answers_exactly_as_before():
    old = history.SharesHistory(ROWS, INDEX, FACTS)
    new = history.SharesHistory(ROWS, INDEX, FACTS, class_rows=CLASS_ROWS, table=TABLE)
    start, end = D("1999-01-01"), D("2011-12-31")
    assert _answers(old, "AAA", start, end) == _answers(new, "AAA", start, end)
    assert new.problems == {}


def test_class_axis_rows_answer_the_sum_from_their_filing_date():
    h = history.SharesHistory(ROWS, INDEX, FACTS, class_rows=CLASS_ROWS, table=TABLE)
    assert h.shares_on("MMM", D("2012-07-31")) is None  # counted, not yet public
    o = h.shares_on("MMM", D("2012-08-01"))
    assert (o.shares, o.source, o.as_of) == (75.0, history.SOURCE_XBRL_CLASS, D("2012-07-25"))
    assert h.shares_on("MMM", D("2013-08-01")).shares == 85.0
    assert h.shares_on("MMM", D("2014-08-30")) is None  # 2013-07-25 + 401 days
    # No table row: summed one for one, recorded, never a problem.
    assert "0000000007" in h.summed and not any(k[0] == "0000000007" for k in h.problems)


def test_sibling_classes_split_the_company_from_the_table_date():
    h = history.SharesHistory(ROWS, INDEX, FACTS, class_rows=CLASS_ROWS, table=TABLE)
    # Before the table speaks: both symbols are the whole company, and the per-class reading
    # beats the companyfacts tag of the same filing.
    for s in ("GGL", "GG"):
        o = h.shares_on(s, D("2014-03-01"))
        assert (o.shares, o.source) == (360.0, history.SOURCE_XBRL_CLASS)
    on = D("2014-05-01")
    assert h.shares_on("GGL", on).shares == 360.0
    assert h.shares_on("GG", on).shares == 361.0
    # A class with no row: both unknown, and the reason kept for the table's keeper.
    assert h.shares_on("GGL", D("2014-08-01")) is None and h.shares_on("GG", D("2014-08-01")) is None
    assert "CommonClassDMember" in h.problems[("0000000002", "0000000002-14-000003", "GG")]


def test_change_points_stay_exact_with_class_rows_and_the_table(tmp_path):
    h = history.SharesHistory(ROWS, INDEX, FACTS, class_rows=CLASS_ROWS, table=TABLE)
    start, end = D("1999-01-01"), D("2015-12-31")
    rows = ss.change_points(h, ["AAA", "MMM", "GGL", "GG"], start, end)
    path = tmp_path / research.SHARES_FILE
    research._write_text(path, ss.SHARES_HEADER, ss.shares_lines(rows))
    counts = ShareCounts(ss.read_shares(path, end))
    for symbol in ("AAA", "MMM", "GGL", "GG"):
        d = start
        while d <= end:
            o = h.shares_on(symbol, d)
            got = counts.count(symbol, d)
            assert (None if o is None else (o.shares, o.as_of or o.filed, o.filed, o.source)) == (
                None if got is None else tuple(got)
            ), (symbol, d)
            d += timedelta(days=1)
    assert history.SOURCE_XBRL_CLASS in ss.SOURCES
    assert any(",xbrl-class," in line for line in ss.shares_lines(rows))
```
**Impact:** none beyond coverage. No network, no store, no database.

### Step 8: `SOURCES.md` section
**File:** `engine/data/SOURCES.md` — append at the end of the file, which after phase 1 is the end
of phase 1's `## shares_xbrl_classes.csv: ...` section (phase 1 appended it after the original
line 470). Do not edit phase 1's section; phase 3 fills its placeholder cells.
**Change:** append exactly this text (it begins with a blank line).
**Code:**
```markdown

## share_classes.csv: which listed symbol each share class answers for

| | |
|---|---|
| Upstream | the filers' own 10-K, 10-Q and 8-K filings on SEC EDGAR, cited row by row in `note` (accession numbers); the XBRL member names read from each cited instance document |
| Generated by | hand, by the engine; checked by `seer_engine.shares.class_table.load_table` and `tests/test_share_class_table.py` |
| Fetched | 2026-10-18 |
| Scope | the multi-class filers whose classes do not simply sum to the listed line: two listed classes that are both index members (Alphabet, Twenty-First Century Fox and Fox Corp, News Corp, Comcast's class A special, Discovery, Liberty Global and its LiLAC tracking stock, Liberty Media and its 2016 tracking groups, Under Armour), classes that convert at a ratio other than one (Berkshire class A, Visa class B, B-1, B-2, B-3 and C) and classes with no claim on the listed line (Accenture class X, Liberty Ventures, Liberty SiriusXM): **14** filers, **99** rows |
| License | US government work, public domain (SEC); the table itself is the engine's |

`cik,member,symbol,ratio,from,to,note`. Over counts taken in `[from, to)` (`to` exclusive, empty
while current) the filer's class `member` counts toward `symbol` at `ratio` of that symbol's
shares per share of the class; `ratio` 0 is a class with no economic interest in the line.
`member` is matched by its words, not its spelling (`seer_engine.shares.class_table.class_key`):
`class A`, `CommonClassAMember`, `series a common` and `ClassAOrdinarySharesMember` are one class;
a filer's own spelling with no letter in it (Liberty Global's `ClassOrdinarySharesMember`,
Comcast's `ClassaSpecialCommonStockMember`) is written as the filing writes it, and a context
with a tracking-stock axis as both member names (`LiLACGroupMember ClassCOrdinarySharesMember`).

**Keyed on the count date.** A row applies to a count by the day the filer counted, because that
is the class structure and the share units the count is stated in: Berkshire's class A is 30
class B before the 50-for-1 class B split of 2010-01-21 and 1,500 from it, and a 2009 count read
in 2010 is carried across the split by the split list like any other. A sibling's rows start at
the first count that sibling needs (FOX joined the Nasdaq-100 on 2014-12-22, so Fox's rows start
2014-09-01 and the count of November 2014 already splits the classes); before a filer's first
row its symbols answer the whole company, as they did before the table existed.

**Fail loud where the table speaks.** A filer with no row here has its classes summed one for
one, every symbol the whole company (`shares store` lists those filers). A count of a filer the
table speaks for that has a class with no row (including `NoClassAxisMember`, a figure the filer
tagged without a class axis), or no class breakdown at all, is answered as unknown, and `shares
store` lists each one; the fix is a row here, with its source.

**Known limits.** For the three weeks between the class C dividend (2014-04-03) and Google's first
count with class C (its 10-Q of late April 2014), GOOGL and GOOG each answer the whole company:
the newest count predates the table's rows, and the dividend is in the split lists as a
2-for-1, so the company counts twice across the two lines. Under Armour's class C dividend of
2016-04-07 has the same shape for UAA (UA is unknown until the first count with class C). Visa's cover rows of 2008
and 2009 pair the class labels with the wrong counts; the per-class XBRL reading of the same
filing replaces them from 2009.
```
**Impact:** docs only.

## Verification

**Build:** `engine/.venv/bin/ruff check engine` (create the worktree venv first: `python3.11 -m venv engine/.venv && engine/.venv/bin/pip install -e 'engine[dev]'`)
**Tests:** `engine/.venv/bin/pytest engine/tests/test_share_class_table.py engine/tests/test_shares.py engine/tests/test_shares_store.py -n0`, then the whole suite `engine/.venv/bin/pytest engine/tests` (DB tests need `PG_TEST_URL`; CI fails if they skip).
**Manual check:**
- `engine/.venv/bin/python -m seer_engine shares store --help` shows `--classes`; `shares store-report --help` shows `--symbols` (no `%` in either help string).
- `engine/.venv/bin/python -c "from seer_engine.shares import class_table as c, history as h; t=c.load_table(h.DATA_DIR/c.TABLE_FILE); print(len(t), len(t.ciks()))"` prints `99 14`.
**Exit criteria:** tests green, including: Meta-like class-axis rows answer the sum
(`test_class_axis_rows_answer_the_sum_from_their_filing_date`, `test_spot_checks_on_the_filers_own_figures`:
META 2,600,051,591); GOOGL/GOOG answer A+B and C and sum to the company (338,181,991 + 338,209,995);
BRK.B answers A x 1,500 + B after 2010-01-21 (2,478,739,631 on 2012-11-05) and A x 30 + B before
(46,551,876 on 2010-02-16); Visa answers A + B x 0.4254 + C on 2012-07-30; a filer with no table
rows and no class rows answers exactly as before on every day 1999-2011; a multi-class filer with
no table row answers its classes summed and is listed in `SharesHistory.summed`, not in
`problems`; `change_points` equals
the day-by-day answer for all four test symbols through 2015; existing shares tests unchanged and
passing.

## Handoffs

- **Phase 3 (selection).** Every CIK in `share_classes.csv` must have **all** its 2009+ 10-K/10-Q
  read into `shares_xbrl_classes.csv`, not only filings whose accession lacks a companyfacts
  count: for these filers a companyfacts figure cannot be split and answers unknown. The CIKs:
  0001067983, 0001166691, 0001288776, 0001308161, 0001336917, 0001355096, 0001403161, 0001437107,
  0001467373, 0001560385, 0001564708, 0001570585, 0001652044, 0001754301. Phase 3 Step 2 runs
  `download-classes --cik` for each (phase 1's `--cik` reads every member filing of the filer);
  re-run it whenever a filer is added to the table.
- **Phase 3 (bare figures).** A tabled filer whose instance tags one class without an axis
  (Berkshire 2010-2011, whose companyfacts figures are class A alone; possibly Visa 2009-2010)
  arrives with a `NoClassAxisMember` class and is reported unknown until a cited row in
  `share_classes.csv` says which class the bare figure is (for Berkshire, class A at 30 / 1,500 by
  count date).
- **Phase 3 (unattributed readings).** `shares store` prints "N readings the class table could not
  attribute". Each must be resolved before the stores are refreshed for good: add a cited row to
  `share_classes.csv` (a spelling the seed lacks, e.g. Visa's 2009-2010 class C series members or
  Liberty Global's post-2018 names), or accept and record why. Any fix is a data-file change plus,
  if it is code, a test. Expected magnitudes on 2014-06-30 from this phase's tests and the
  filings: Meta 2.600B shares, BRK.B ≈ 2.47B B-equivalents, V ≈ 0.61B as-converted (pre-split),
  GOOGL 0.338B + GOOG 0.338B.
- **Phase 3 (Visa cover rows).** Visa's 2008-2009 10-K cover rows in `shares_outstanding_pre2009.csv`
  pair labels with the wrong counts (e.g. `class c common=470210301;class a common=245513385` on
  2009-11-20). The table converts them by label, so V's value on 2009-12-21..2010-02-02 is right
  only if phase 1 has a per-class row for accession 0001193125-09-239249 (same filing wins).
  Check V there in the `--symbols` report; if the row is missing, add it or note it. Editing the
  pre-2009 csv is out of this plan set's scope.
- **Phase 3 (docs).** The `shares/__init__.py` module map (add `class_table`), `package_readme.md`
  and the skill's size-accessor notes, as phase 3 already plans.
- **Out of every phase (noted, not fixed):** pre-2009 tracking stocks on one filer (Liberty Media
  Corp 0001355096's 2007-2008 LMCK/QRTEA, USX, Loews) remain as `SOURCES.md` already describes;
  the GOOGL/GOOG and UAA three-week dividend windows (`SOURCES.md` Known limits) are an accepted,
  recorded limitation (index Decisions): starting the table's rows before the dividend would
  leave GOOG with no count for those weeks, which phase 3's continuity check forbids.

## Rollback

Revert this phase's commit: delete `class_table.py`, `share_classes.csv` and
`test_share_class_table.py`; restore `history.py`, `store.py`, `integrate.py`, `market.py` and
`SOURCES.md` from the parent commit. No store or committed data outside `engine/data/share_classes.csv`
is touched, so nothing else needs undoing. (A store already refreshed by phase 3 with `xbrl-class`
rows would then be refused by `read_shares`; roll phase 3 back first.)

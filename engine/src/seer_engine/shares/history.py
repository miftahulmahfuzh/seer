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
#: Holding-company reorganisations that swapped every share one for one, class for class, into
#: a new registrant whose first count was filed weeks later: successor CIK -> (predecessor CIK,
#: the day the ticker moved). Until the successor's first per-class reading, its symbols answer
#: the predecessor's last one, attributed through the predecessor's class-table rows -- the same
#: shares under a new name, filed before the day it is read, so nothing is looked ahead at. Not a
#: general rule: a merger or a combination also moves a ticker to a new filer, and there the count
#: changes. Alphabet: 8-K12B of 2015-10-02 (each Google class A, B and C share became one Alphabet
#: share of that class); its first count is in its 10-Q of 2015-10-29.
ONE_FOR_ONE_SUCCESSORS: dict[str, tuple[str, date]] = {"0001652044": ("0001288776", date(2015, 10, 2))}


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
        k_cik = row_cik
        if k is None and row_cik in ONE_FOR_ONE_SUCCESSORS:
            before, moved = ONE_FOR_ONE_SUCCESSORS[row_cik]
            if on >= moved:
                k, k_cik = self.latest_class(before, on), before
        if k is not None and (best is None or (k.filed, SOURCE_RANK[SOURCE_XBRL_CLASS]) > best):
            best = (k.filed, SOURCE_RANK[SOURCE_XBRL_CLASS])
            pick = (SOURCE_XBRL_CLASS, k.accession, k.as_of, k.filed, float(k.shares), tuple(k.classes))
        if pick is None:
            return None
        source, accession, as_of, filed, total, classes = pick
        if self.max_age_days is not None and (on - (as_of or filed)).days > self.max_age_days:
            return None
        cik = k_cik if source == SOURCE_XBRL_CLASS else row_cik
        shares = self._attribute(source, accession, cik, symbol, as_of or filed, total, classes)
        if shares is None:
            return None
        return Observation(symbol, on, shares, as_of, filed, source, accession, cik)


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

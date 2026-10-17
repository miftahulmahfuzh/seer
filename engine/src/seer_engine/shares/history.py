"""Point-in-time shares outstanding, 1996-today, and the market value they imply.

Vendored source (``engine/data``, documented in ``SOURCES.md``):

* ``shares_outstanding_pre2009.csv`` -- ``cik,symbol,filed,as_of,form,accession,shares,classes,
  flags,note``. One row per 10-K/10-Q of an S&P 500 member's filer, filed 1995-10 through
  2010-12, with the share count its cover page states. Built by ``python -m seer_engine shares
  build`` from EDGAR (``shares.cover`` parses, ``shares.checks`` validates); every value a check
  flagged and that was kept says why in ``note``, and every value a check threw out is listed,
  with its reason, in ``shares_outstanding_pre2009_excluded.csv`` instead.

**Two dates, and only one of them is an availability date.** ``as_of`` is the day the filer
counted ("As of March 2, 1997, ... outstanding"), usually weeks after the period ended and days
before filing. ``filed`` is the day EDGAR disseminated the report. A figure is usable on day t
only when ``filed <= t`` -- never from its ``as_of``, which would read a count the market had not
yet been told. :meth:`SharesHistory.latest` enforces exactly that and nothing looser, the same
rule ``fundamentals.panel`` applies to XBRL facts. ``as_of`` is still needed: a split between the
count and the day it is used changes what the count means (:func:`market_value`).

**One API across the 2009 seam.** XBRL's ``dei:EntityCommonStockSharesOutstanding`` is the same
cover-page figure, tagged; the store's ``fundamentals.csv`` carries it per symbol from 2009.
:meth:`SharesHistory.shares_on` takes both sources, resolves ``symbol`` to its filer on the day
asked through the date-scoped ticker map (never a bare ticker; ``cik``'s docstring), and returns
whichever figure was filed last. When a cover row and an XBRL fact share an accession -- the same
report, read twice -- the tagged figure wins.

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
    source: str  # SOURCE_COVER or SOURCE_XBRL
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
    """Cover rows by filer plus (optionally) XBRL facts by symbol, queried point in time."""

    def __init__(
        self,
        rows: Iterable[ShareRow],
        index: Mapping[str, Sequence[cikmod.CikRow]],
        xbrl: Iterable[XbrlFact] = (),
        *,
        max_age_days: int | None = DEFAULT_MAX_AGE_DAYS,
    ) -> None:
        by: dict[str, list[ShareRow]] = {}
        for r in rows:
            by.setdefault(r.cik, []).append(r)
        self._rows = {k: sorted(v, key=lambda r: (r.filed, r.accession)) for k, v in by.items()}
        self._filed = {k: [r.filed for r in v] for k, v in self._rows.items()}
        self._xbrl = xbrl_by_symbol(xbrl)
        self._xfiled = {k: [x.filed for x in v] for k, v in self._xbrl.items()}
        self.index = index
        self.max_age_days = max_age_days

    def latest(self, cik: str, on: date) -> ShareRow | None:
        """The cover row of ``cik`` filed last on or before ``on`` (never one filed after)."""
        filed = self._filed.get(cik)
        if not filed:
            return None
        i = bisect.bisect_right(filed, on) - 1
        return self._rows[cik][i] if i >= 0 else None

    def _latest_xbrl(self, symbol: str, on: date) -> _Xbrl | None:
        filed = self._xfiled.get(symbol)
        if not filed:
            return None
        i = bisect.bisect_right(filed, on) - 1
        return self._xbrl[symbol][i] if i >= 0 else None

    def shares_on(self, symbol: str, on: date) -> Observation | None:
        """The share count public on ``on`` for the company trading as ``symbol`` that day.

        None when neither source has a figure filed on or before ``on``, or when the newest one
        is older than ``max_age_days``.
        """
        try:
            row_cik = cikmod.resolve(symbol, on, self.index)
        except CikError:
            row_cik = None
        cover = self.latest(row_cik, on) if row_cik else None
        x = self._latest_xbrl(symbol, on)
        obs: Observation | None = None
        if cover is not None:
            obs = Observation(symbol, on, float(cover.shares), cover.as_of, cover.filed,
                              SOURCE_COVER, cover.accession, row_cik)
        # Filed later wins; filed the same day (the same report, read twice) the tag wins.
        if x is not None and (obs is None or x.filed >= obs.filed):
            obs = Observation(symbol, on, x.shares, x.period_end, x.filed, SOURCE_XBRL,
                              x.accession, row_cik)
        if obs is None:
            return None
        if self.max_age_days is not None and obs.age_days > self.max_age_days:
            return None
        return obs


def load(
    data_dir: Path = DATA_DIR,
    xbrl: Iterable[XbrlFact] = (),
    *,
    max_age_days: int | None = DEFAULT_MAX_AGE_DAYS,
) -> SharesHistory:
    """The vendored cover rows and the date-scoped ticker map, plus any XBRL facts given."""
    return SharesHistory(
        load_rows(data_dir / SHARES_FILE),
        cikmod.load_index_with_history(data_dir),
        xbrl,
        max_age_days=max_age_days,
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

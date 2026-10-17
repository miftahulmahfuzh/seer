"""Point-in-time sector labels: (symbol, date) -> SEC filer -> SIC -> Fama-French 12 industry.

Why this exists. A ranked book can fill its slots from one corner of the market: COSK's live book
on 2026-10-17 came out 12 of 20 in oil and gas, and the lab had no sector data at all to notice,
let alone cap it. EODHD's fundamentals endpoint (which carries GICS) is not on the owner's plan,
so the labels are built from free SEC EDGAR data instead.

Three vendored inputs, all in ``engine/data`` and documented in ``SOURCES.md``:

* ``ticker_cik.csv`` + ``ticker_cik_pre2009.csv`` (``cik.load_index_with_history``) -- the
  date-scoped ticker -> CIK map. **A ticker alone never identifies a company** (``cik``'s
  docstring has the cases), so a sector is always asked for a (symbol, date) pair and there is
  no bare-ticker API here either.
* ``cik_sic.csv`` -- ``cik,sic,sic_description,entity_name,fetched,source``: the Standard
  Industrial Classification EDGAR's ``data.sec.gov/submissions/CIK##########.json`` gives each
  filer, one row per CIK in the map. Rebuilt by ``python -m seer_engine sectors refresh``;
  nothing at backtest or paper time reads the network.
* ``Siccodes12.txt`` -- Ken French's 12-industry SIC definition, vendored byte for byte from
  his data library (https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/Siccodes12.zip,
  linked from "Detail for 12 Industry Portfolios" at
  https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/det_12_ind_port.html).
  Twelve industries is coarse on purpose: a cap of K names per sector over a 20-slot book only
  means something when the buckets are few and broad, and FF12 is the standard academic
  grouping, so a cap measured here reads the same as one in the literature. Any SIC outside
  the listed ranges falls to industry 12, ``Other``, exactly as French's file says.

**EDGAR's SIC is the filer's latest, not point-in-time.** The submissions API carries one
``sic`` per CIK, the code SEC's Office of Corporation Finance assigned most recently, with no
history. For a company that stayed in its line of business (almost all index members) that is
the right answer for every date. For one that changed trade it labels the whole tenure with the
end state: a filer that changed trade but kept its CIK reads as the new business for dates
when it was still the old one. USX Corp, whose U.S. Steel Group traded as X until 2001, is
Marathon Oil on EDGAR today (SIC 1311), so X reads as energy for 1996-2001; Fluor's pre-2000
CIK is Massey Energy's (coal), Ohio Edison's carries an asset-backed-securities code. The
history file's notes name every such case found. This is an accepted bias of the free source,
small in count (a handful of the 1,320 filers), and it can only blur a cap, never leak future
prices: the SIC says nothing about returns. Where the ticker
itself moved to a different filer the date-scoped map already switches CIK, so the large cases
(a recycled ticker, a holdco reorg) are point-in-time.

Unknown is a real answer. ``sector_of`` returns None when the symbol has no row covering the
date, when the row is ``NONE`` (no EDGAR filer), or when EDGAR holds no SIC for the filer; the
caller decides what None means. ``select_capped`` makes that decision once for the lab.

Nothing in this module reads the network, the clock or the database, like ``cik``.
"""

from __future__ import annotations

import csv
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from seer_engine import cik as cikmod
from seer_engine.cik import CikError, CikRow

DATA_DIR = cikmod.DATA_DIR
CIK_SIC_FILE = "cik_sic.csv"
FF12_FILE = "Siccodes12.txt"

CIK_SIC_HEADER: tuple[str, ...] = (
    "cik",
    "sic",
    "sic_description",
    "entity_name",
    "fetched",
    "source",
)

#: The only ``source`` the csv carries today: the ``sic`` field of EDGAR's submissions JSON.
SIC_SOURCES: tuple[str, ...] = ("edgar-submissions",)

#: The FF12 industry an SIC outside every listed range falls into (French: "Other").
OTHER = "Other"

#: The bucket :func:`select_capped` puts every symbol with no known sector into.
UNKNOWN = "Unknown"


class SectorError(ValueError):
    """The vendored sector data is inconsistent."""


@dataclass(frozen=True)
class Industry:
    """One FF12 industry: ``number`` 1-12, ``code`` (``Enrgy``), ``title`` (French's words)."""

    number: int
    code: str
    title: str


@dataclass(frozen=True)
class Ff12:
    """The parsed definition: industries in French's order, and the SIC ranges of 1-11."""

    industries: tuple[Industry, ...]
    ranges: tuple[tuple[int, int, str], ...]  # (lo, hi, code), inclusive, ascending by lo

    @property
    def codes(self) -> tuple[str, ...]:
        return tuple(i.code for i in self.industries)

    def industry_of(self, sic: int | None) -> str | None:
        """The FF12 code for ``sic``; ``Other`` outside every range; None when ``sic`` is None."""
        if sic is None:
            return None
        for lo, hi, code in self.ranges:
            if lo <= sic <= hi:
                return code
        return OTHER


@dataclass(frozen=True)
class SicRow:
    cik: str
    sic: int | None
    sic_description: str
    entity_name: str
    fetched: date
    source: str


_INDUSTRY_RE = re.compile(r"^\s*(\d{1,2})\s+(\S+)\s+(.+?)\s*$")
_RANGE_RE = re.compile(r"^\s+(\d{4})-(\d{4})\s*$")


def load_ff12(path: Path) -> Ff12:
    """Parse French's ``Siccodes12.txt``. Rejects anything that is not 12 industries in order,
    a range that is inverted, ranges that overlap, or ranges under the residual ``Other``."""
    industries: list[Industry] = []
    ranges: list[tuple[int, int, str]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        m = _RANGE_RE.match(line)
        if m:
            if not industries:
                raise SectorError(f"{path.name}:{lineno}: a range before any industry")
            lo, hi = int(m.group(1)), int(m.group(2))
            if hi < lo:
                raise SectorError(f"{path.name}:{lineno}: inverted range {lo}-{hi}")
            ranges.append((lo, hi, industries[-1].code))
            continue
        m = _INDUSTRY_RE.match(line)
        if not m:
            raise SectorError(f"{path.name}:{lineno}: unreadable line {line!r}")
        industries.append(Industry(int(m.group(1)), m.group(2), m.group(3)))
    if [i.number for i in industries] != list(range(1, 13)):
        raise SectorError(f"{path.name}: expected industries 1..12 in order")
    if industries[-1].code != OTHER:
        raise SectorError(f"{path.name}: industry 12 must be {OTHER}")
    if any(code == OTHER for _, _, code in ranges):
        raise SectorError(f"{path.name}: {OTHER} is the residual and lists no ranges")
    ranges.sort()
    for (lo1, hi1, c1), (lo2, hi2, c2) in zip(ranges, ranges[1:]):
        if lo2 <= hi1:
            raise SectorError(f"{path.name}: {c1} {lo1}-{hi1} overlaps {c2} {lo2}-{hi2}")
    return Ff12(tuple(industries), tuple(ranges))


def load_cik_sic(path: Path) -> dict[str, SicRow]:
    """Read ``cik_sic.csv``: header exactly :data:`CIK_SIC_HEADER`, 10-digit CIKs, one row each,
    sorted, ``sic`` four digits or empty (EDGAR has none), a description whenever there is a
    ``sic``, a known ``source``."""
    out: dict[str, SicRow] = {}
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if tuple(reader.fieldnames or ()) != CIK_SIC_HEADER:
            raise SectorError(
                f"{path}: expected header {','.join(CIK_SIC_HEADER)}, got {reader.fieldnames}"
            )
        prev = ""
        for lineno, raw in enumerate(reader, start=2):
            where = f"{path.name}:{lineno}"
            key = (raw["cik"] or "").strip()
            if len(key) != 10 or not key.isdigit():
                raise SectorError(f"{where}: cik must be 10 digits, got {key!r}")
            if key <= prev:
                raise SectorError(f"{where}: rows must be sorted by cik and unique ({key})")
            prev = key
            sic_text = (raw["sic"] or "").strip()
            if sic_text and (len(sic_text) != 4 or not sic_text.isdigit()):
                raise SectorError(f"{where}: sic must be 4 digits or empty, got {sic_text!r}")
            desc = (raw["sic_description"] or "").strip()
            if sic_text and not desc:
                raise SectorError(f"{where}: sic_description is required with a sic")
            source = (raw["source"] or "").strip()
            if source not in SIC_SOURCES:
                raise SectorError(f"{where}: unknown source {source!r}")
            try:
                fetched = date.fromisoformat((raw["fetched"] or "").strip())
            except ValueError as exc:
                raise SectorError(f"{where}: bad fetched date {raw['fetched']!r}") from exc
            out[key] = SicRow(
                cik=key,
                sic=int(sic_text) if sic_text else None,
                sic_description=desc,
                entity_name=(raw["entity_name"] or "").strip(),
                fetched=fetched,
                source=source,
            )
    if not out:
        raise SectorError(f"{path}: no rows")
    return out


def write_cik_sic(path: Path, rows: Iterable[SicRow]) -> int:
    """Write ``rows`` sorted by CIK in the format :func:`load_cik_sic` reads. Returns the count."""
    ordered = sorted(rows, key=lambda r: r.cik)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(CIK_SIC_HEADER)
        for r in ordered:
            writer.writerow([
                r.cik,
                "" if r.sic is None else f"{r.sic:04d}",
                r.sic_description,
                r.entity_name,
                r.fetched.isoformat(),
                r.source,
            ])
    return len(ordered)


def map_ciks(index: Mapping[str, Sequence[CikRow]]) -> tuple[str, ...]:
    """Every distinct CIK the map can resolve to, sorted. ``NONE`` rows contribute nothing."""
    return tuple(sorted({r.cik for group in index.values() for r in group if r.cik}))


@dataclass(frozen=True)
class SectorMap:
    """The three inputs joined. Build with :func:`load` or directly in a test."""

    index: Mapping[str, Sequence[CikRow]]
    sics: Mapping[str, SicRow]
    ff12: Ff12

    def row(self, symbol: str, on: date) -> CikRow | None:
        """The ticker_cik row covering ``symbol`` on ``on`` with a filer, else None."""
        try:
            return cikmod.resolve_row(symbol, on, self.index)
        except CikError:
            return None

    def sic_of(self, symbol: str, on: date) -> int | None:
        """The raw four-digit SIC of the filer trading as ``symbol`` on ``on``, else None."""
        row = self.row(symbol, on)
        if row is None or row.cik is None:
            return None
        hit = self.sics.get(row.cik)
        return None if hit is None else hit.sic

    def sector_of(self, symbol: str, on: date) -> str | None:
        """The FF12 code (``Enrgy``, ``BusEq``, ...) of ``symbol`` on ``on``, else None."""
        return self.ff12.industry_of(self.sic_of(symbol, on))


def load(data_dir: Path = DATA_DIR) -> SectorMap:
    """The vendored map, loaded and validated."""
    return SectorMap(
        index=cikmod.load_index_with_history(data_dir),
        sics=load_cik_sic(data_dir / CIK_SIC_FILE),
        ff12=load_ff12(data_dir / FF12_FILE),
    )


def select_capped(
    ranked: Iterable[str],
    on: date,
    n: int,
    cap: int,
    sector_of: Callable[[str, date], str | None],
) -> list[str]:
    """The first ``n`` of ``ranked`` (best first) with at most ``cap`` names per sector.

    Walks the ranking once and skips a name whose sector already holds ``cap``; it never
    relaxes the cap to fill slots, so fewer than ``n`` come back when the ranking runs out --
    an unfilled slot is cash, which is what a method that respects the cap should hold rather
    than a quietly broken cap. A repeated symbol counts once.

    **Every symbol with no known sector shares one bucket, ``Unknown``, capped like any other.**
    The alternative, each unknown as its own bucket, lets a book be all unknowns and so
    switches the cap off exactly where the data is worst; one shared bucket can only make the
    book more spread, never less. It costs little: from 1996 the map resolves almost every
    member-day, so the bucket is small, and a method sees the same rule on every date.

    ``sector_of`` is anything with :meth:`SectorMap.sector_of`'s shape -- pass that bound
    method, or a dict lookup in a test.
    """
    if n < 0:
        raise ValueError(f"n must be >= 0, got {n}")
    if cap < 1:
        raise ValueError(f"cap must be >= 1, got {cap}")
    picked: list[str] = []
    seen: set[str] = set()
    held: dict[str, int] = {}
    for symbol in ranked:
        if len(picked) >= n:
            break
        if symbol in seen:
            continue
        seen.add(symbol)
        bucket = sector_of(symbol, on) or UNKNOWN
        if held.get(bucket, 0) >= cap:
            continue
        held[bucket] = held.get(bucket, 0) + 1
        picked.append(symbol)
    return picked

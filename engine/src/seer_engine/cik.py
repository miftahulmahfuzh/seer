"""Point-in-time ticker -> SEC CIK map.

Vendored source (``engine/data``, documented in ``SOURCES.md``):

* ``ticker_cik.csv`` -- ``symbol,cik,start_date,end_date,company_name,source,note``. One row per
  (symbol, filer) tenure: the SEC Central Index Key of the company whose shares traded under
  ``symbol`` over ``[start_date, end_date)``. ``end_date`` is **exclusive** and empty while the
  mapping is still current, exactly like ``universe.end_date``. ``cik`` is the literal ``NONE``
  for a symbol with no EDGAR filer at all; ``note`` then says why.

**A ticker alone never identifies a company.** Measured 2026-10-05, EDGAR's own ticker lookup
(``browse-edgar?action=getcompany&CIK=<ticker>``) answers MON with Monument Circle Acquisition
Corp (0001828325), PLL with Piedmont Lithium (0001728205), ALTR with Altair Engineering
(0001701732) and LLL with JX Luxventure (0001546383) -- in every case the company holding the
recycled ticker *today*, not the index member that held it in the backtest window. Two symbols
also change filer *inside* the window without changing ticker: WRK (WestRock 0001636023 ->
0001732845 at the 2018-11-02 KapStone close) and GOOG/GOOGL (Google Inc 0001288776 -> Alphabet
0001652044 at the 2015-10-02 holdco reorg). Every lookup here is therefore scoped by date, and
there is deliberately no bare-ticker API.

The reverse is not true: one CIK legitimately backs several symbols at once. Among the
ever-members GOOG/GOOGL, FOX/FOXA, NWS/NWSA, UA/UAA, CMCSA/CMCSK and BATRA/BATRK are share
classes of a single filer, so no uniqueness check is applied to ``cik``.

Nothing in this module reads the network, the clock or the database. ``membership`` is imported
for ``normalize_ticker`` and ``Interval``; ``membership`` must never import this module.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from seer_engine import membership
from seer_engine.membership import Interval, MembershipError

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
TICKER_CIK_FILE = "ticker_cik.csv"

#: First day of the backtest window. The map is only guaranteed from here on.
SINCE = date(2015, 1, 2)

HEADER: tuple[str, ...] = (
    "symbol",
    "cik",
    "start_date",
    "end_date",
    "company_name",
    "source",
    "note",
)

#: How a row was produced. ``current`` = SEC company_tickers.json, ``edgar`` = EDGAR's
#: browse-edgar ticker lookup, ``exact``/``fuzzy`` = company-name match against
#: cik-lookup-data.txt, ``manual`` = hand-audited in build_ticker_cik.py.
SOURCES: tuple[str, ...] = ("current", "edgar", "exact", "fuzzy", "manual")

#: Sources whose rows a human must justify in ``note``.
NOTE_REQUIRED = frozenset({"fuzzy", "manual"})

#: ``cik`` sentinel: this symbol has no EDGAR filer. ``note`` is then mandatory.
NO_FILER = "NONE"

#: Internal stand-in for an open ``end_date`` so interval arithmetic stays total.
_OPEN = date.max


class CikError(ValueError):
    """The vendored ticker -> CIK data is inconsistent, or a lookup has no answer."""


@dataclass(frozen=True, order=True)
class CikRow:
    """One (symbol, filer) tenure. ``end_date`` is exclusive; None means still current."""

    symbol: str
    cik: str | None
    start_date: date
    end_date: date | None
    company_name: str
    source: str
    note: str

    def covers(self, on: date) -> bool:
        """True when ``on`` falls in ``[start_date, end_date)``."""
        if on < self.start_date:
            return False
        return self.end_date is None or on < self.end_date


@dataclass(frozen=True, order=True)
class Gap:
    """A stretch of a symbol's membership that ``ticker_cik.csv`` does not answer for."""

    symbol: str
    start_date: date
    end_date: date | None


Index = Mapping[str, tuple[CikRow, ...]]


def normalize_cik(raw: str, where: str = "") -> str:
    """``'356028'`` -> ``'0000356028'``. Raises on anything that is not a CIK.

    The vendored file must already carry the 10-digit form -- ``load_ticker_cik`` rejects
    anything else. This helper exists for the ingest path (Phase 4), which sees CIKs as bare
    integers in SEC payloads and on the command line.
    """
    text = raw.strip()
    prefix = f"{where}: " if where else ""
    if text.upper().startswith("CIK"):
        text = text[3:]
    if not text or not text.isdigit() or len(text) > 10:
        raise CikError(f"{prefix}not a CIK: {raw!r}")
    padded = text.zfill(10)
    if padded == "0" * 10:
        raise CikError(f"{prefix}not a CIK: {raw!r}")
    return padded


def _parse_date(raw: str, where: str) -> date:
    try:
        return date.fromisoformat(raw.strip())
    except ValueError as exc:
        raise CikError(f"{where}: bad date {raw!r}") from exc


def _parse_cik_cell(raw: str, where: str) -> str | None:
    text = raw.strip()
    if text == NO_FILER:
        return None
    if len(text) != 10 or not text.isdigit() or text == "0" * 10:
        raise CikError(
            f"{where}: cik must be 10 digits or {NO_FILER}, got {raw!r}"
        )
    return text


def _parse_symbol(raw: str, where: str) -> str:
    try:
        return membership.normalize_ticker(raw)
    except MembershipError as exc:
        raise CikError(f"{where}: {exc}") from exc


def load_ticker_cik(path: Path) -> list[CikRow]:
    """Read ``ticker_cik.csv`` into rows, rejecting anything inconsistent.

    Rejected: a header that is not exactly :data:`HEADER`; a symbol that is not a ticker; a
    ``cik`` that is not 10 digits (or ``NONE``); a bad or non-increasing date; an unknown
    ``source``; a missing ``note`` where one is required; a missing ``company_name`` on a row
    that has a CIK; a file not sorted by ``(symbol, start_date)``; a duplicate
    ``(symbol, start_date)``; two overlapping intervals for one symbol; an open interval that is
    not the symbol's last row; and a ``NONE`` row that is not the symbol's only row.
    """
    rows: list[CikRow] = []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if tuple(reader.fieldnames or ()) != HEADER:
            raise CikError(
                f"{path}: expected header {','.join(HEADER)}, got {reader.fieldnames}"
            )
        for lineno, raw in enumerate(reader, start=2):
            where = f"{path.name}:{lineno}"
            symbol = _parse_symbol(raw["symbol"], where)
            cik = _parse_cik_cell(raw["cik"], where)
            start_date = _parse_date(raw["start_date"], where)
            end_text = (raw["end_date"] or "").strip()
            end_date = _parse_date(end_text, where) if end_text else None
            if end_date is not None and end_date <= start_date:
                raise CikError(
                    f"{where}: end_date {end_date} must be after start_date {start_date}"
                )
            source = (raw["source"] or "").strip()
            if source not in SOURCES:
                raise CikError(
                    f"{where}: source must be one of {'|'.join(SOURCES)}, got {source!r}"
                )
            company_name = (raw["company_name"] or "").strip()
            if cik is not None and not company_name:
                raise CikError(f"{where}: company_name is required")
            note = (raw["note"] or "").strip()
            if not note and (source in NOTE_REQUIRED or cik is None):
                reason = f"source {source}" if source in NOTE_REQUIRED else NO_FILER
                raise CikError(f"{where}: note is required for {reason}")
            rows.append(
                CikRow(
                    symbol=symbol,
                    cik=cik,
                    start_date=start_date,
                    end_date=end_date,
                    company_name=company_name,
                    source=source,
                    note=note,
                )
            )
    if not rows:
        raise CikError(f"{path}: no rows")
    _check_order(rows, path)
    _check_intervals(rows, path)
    return rows


def _check_order(rows: Sequence[CikRow], path: Path) -> None:
    for i in range(1, len(rows)):
        prev, cur = rows[i - 1], rows[i]
        if (cur.symbol, cur.start_date) < (prev.symbol, prev.start_date):
            raise CikError(
                f"{path.name}:{i + 2}: rows must be sorted by (symbol, start_date); "
                f"{cur.symbol} {cur.start_date} follows {prev.symbol} {prev.start_date}"
            )


def _check_intervals(rows: Sequence[CikRow], path: Path) -> None:
    grouped: dict[str, list[CikRow]] = {}
    for row in rows:
        grouped.setdefault(row.symbol, []).append(row)
    for symbol, group in grouped.items():
        if any(r.cik is None for r in group) and len(group) > 1:
            raise CikError(
                f"{path.name}: {symbol} has a {NO_FILER} row alongside {len(group) - 1} other "
                f"row(s); {NO_FILER} must be the symbol's only row"
            )
        for i in range(1, len(group)):
            prev, cur = group[i - 1], group[i]
            if prev.start_date == cur.start_date:
                raise CikError(f"{path.name}: duplicate row for {symbol} {cur.start_date}")
            if prev.end_date is None:
                raise CikError(
                    f"{path.name}: {symbol} has an open interval from {prev.start_date} "
                    f"before the row starting {cur.start_date}; only the last row may be open"
                )
            if prev.end_date > cur.start_date:
                raise CikError(
                    f"{path.name}: {symbol} intervals overlap: "
                    f"[{prev.start_date}, {prev.end_date}) and [{cur.start_date}, "
                    f"{cur.end_date or ''})"
                )


def build_index(rows: Iterable[CikRow]) -> dict[str, tuple[CikRow, ...]]:
    """Group rows by symbol, each group ascending by ``start_date``."""
    grouped: dict[str, list[CikRow]] = {}
    for row in rows:
        grouped.setdefault(row.symbol, []).append(row)
    return {
        symbol: tuple(sorted(group, key=lambda r: r.start_date))
        for symbol, group in sorted(grouped.items())
    }


def load_index(data_dir: Path = DATA_DIR) -> dict[str, tuple[CikRow, ...]]:
    """The vendored map, loaded and validated, ready for :func:`resolve`."""
    return build_index(load_ticker_cik(data_dir / TICKER_CIK_FILE))


def resolve_row(symbol: str, on: date, index: Index) -> CikRow:
    """The row covering ``symbol`` on ``on``. Raises :class:`CikError` when there is none."""
    group = index.get(symbol)
    if not group:
        raise CikError(f"{symbol}: no row in {TICKER_CIK_FILE}")
    for row in group:
        if row.covers(on):
            if row.cik is None:
                raise CikError(f"{symbol} on {on}: no EDGAR filer ({row.note})")
            return row
    spans = ", ".join(
        f"[{r.start_date}, {r.end_date or ''})" for r in group
    )
    raise CikError(
        f"{symbol} on {on}: outside every known interval ({spans}); the ticker may have been "
        f"reissued -- do not fall back to a bare-ticker lookup"
    )


def resolve(symbol: str, on: date, index: Index) -> str:
    """The 10-digit CIK of the company trading as ``symbol`` on ``on``."""
    return resolve_row(symbol, on, index).cik  # type: ignore[return-value]


def filers(
    symbol: str, index: Index, start: date | None = None, end: date | None = None
) -> tuple[str, ...]:
    """Every distinct CIK behind ``symbol`` whose tenure meets ``[start, end)``, oldest first.

    ``start`` defaults to the beginning of time and ``end`` to the end of it, so a bare call
    returns every filer the symbol ever had. This is the ingest entry point: Phase 4 fetches
    ``companyfacts`` once per CIK returned here.
    """
    lo = date.min if start is None else start
    hi = _OPEN if end is None else end
    out: list[str] = []
    for row in index.get(symbol, ()):
        if row.cik is None:
            continue
        row_end = _OPEN if row.end_date is None else row.end_date
        if row.start_date < hi and lo < row_end and row.cik not in out:
            out.append(row.cik)
    return tuple(out)


def missing_symbols(index: Index, symbols: Iterable[str]) -> tuple[str, ...]:
    """Those of ``symbols`` with no row at all, sorted."""
    return tuple(sorted(s for s in set(symbols) if s not in index))


def no_filer_symbols(index: Index) -> tuple[str, ...]:
    """Symbols deliberately recorded as having no EDGAR filer, sorted."""
    return tuple(
        sorted(s for s, group in index.items() if any(r.cik is None for r in group))
    )


def _merge(spans: Sequence[tuple[date, date]]) -> list[tuple[date, date]]:
    out: list[tuple[date, date]] = []
    for start, end in sorted(spans):
        if out and start <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], end))
        else:
            out.append((start, end))
    return out


def coverage_gaps(
    index: Index, intervals: Iterable[Interval], since: date = SINCE
) -> tuple[Gap, ...]:
    """Membership time on or after ``since`` that the map does not answer for.

    Each :class:`~seer_engine.membership.Interval` is clipped to ``[since, ...)`` and matched
    against the symbol's rows. A ``NONE`` row counts as covered: it is an explicit answer.
    An empty result is the R1 guarantee -- every ever-member has a CIK (or a documented
    absence) for every day it was in an index inside the backtest window.
    """
    wanted: dict[str, list[tuple[date, date]]] = {}
    for iv in intervals:
        start = max(iv.start_date, since)
        end = _OPEN if iv.end_date is None else iv.end_date
        if start < end:
            wanted.setdefault(iv.symbol, []).append((start, end))
    gaps: list[Gap] = []
    for symbol in sorted(wanted):
        covered = sorted(
            (row.start_date, _OPEN if row.end_date is None else row.end_date)
            for row in index.get(symbol, ())
        )
        for start, end in _merge(wanted[symbol]):
            cursor = start
            for c_start, c_end in covered:
                if cursor >= end:
                    break
                if c_end <= cursor:
                    continue
                if c_start > cursor:
                    gap_end = min(c_start, end)
                    gaps.append(
                        Gap(symbol, cursor, None if gap_end == _OPEN else gap_end)
                    )
                    cursor = gap_end
                cursor = max(cursor, min(c_end, end))
            if cursor < end:
                gaps.append(Gap(symbol, cursor, None if end == _OPEN else end))
    return tuple(gaps)

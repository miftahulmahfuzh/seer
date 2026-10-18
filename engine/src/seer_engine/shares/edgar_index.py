"""EDGAR's quarterly master index, and which periodic reports the shares history needs.

EDGAR publishes one ``master.idx`` per calendar quarter under
``https://www.sec.gov/Archives/edgar/full-index/<YYYY>/QTR<n>/`` (gzipped as ``master.gz``):
pipe-delimited ``CIK|Company Name|Form Type|Date Filed|Filename`` with one line per filing
ever disseminated that quarter. It is the only complete list of pre-2001 filings -- the
``data.sec.gov/submissions`` API pages a large filer's history behind ``files`` and was built
for the XBRL era -- and sixty quarters (1995Q4-2010Q4) are about 70 MB compressed, so the whole
list is read once and filtered locally rather than asked filer by filer.

**Which forms.** The original periodic reports whose cover page states the shares outstanding:
``10-K``, ``10-K405`` (a 10-K whose filer ticked the Item 405 box; the variant was retired in
2003 but is a quarter of all 1997 annual reports), ``10-KT``/``10-QT`` (transition periods),
``10-Q``, and the small-business ``10-KSB``/``10-QSB``. Amendments (``/A``) are left out on
purpose: an amendment repeats or corrects the original's cover often months later, and it would
shadow a fresher 10-Q filed in between with a stale count under "latest filed wins".

**Which window.** A filer's reports matter only around the days it was in the index: from
:data:`LEAD_DAYS` before its first member day (so the first member day already has a figure
that was public on it) to its last member day, inside ``[HORIZON_START, HORIZON_END]``. The
horizon runs two years past the 2009 XBRL floor so the two sources overlap for validation.

**Past 2010** (``shares.classes``, the per-class XBRL reader) the quarters run from
:data:`XBRL_START` to the last *closed* one (:func:`closed_quarters`): EDGAR keeps appending to the
current quarter's master index until the quarter is over, and the downloader caches an index
once and never asks again, so an open quarter's index would hide every filing made after it was
fetched.

Pure: no network, clock or database.
"""

from __future__ import annotations

import gzip
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta

from seer_engine import cik as cikmod
from seer_engine import membership

#: First and last filing date fetched. 1995Q4 so a January-1996 member day can already see a
#: report filed before it; through 2010 so every 2009-2010 XBRL figure has a text twin.
HORIZON_START = date(1995, 10, 1)
HORIZON_END = date(2010, 12, 31)

#: First filing date the per-class XBRL reader looks at: the dei cover tag starts with the large
#: accelerated filers' fiscal-2009 reports.
XBRL_START = date(2009, 1, 1)

#: Days after a quarter ends before its master index is treated as final: a filing accepted on
#: the quarter's last evening is disseminated, and indexed, the next business day.
CLOSED_GRACE_DAYS = 7

#: How far before a filer's first member day its reports are wanted. A little over a year, so
#: even a filer with a long gap between reports has one filed before its first member day.
LEAD_DAYS = 400

#: Original periodic reports carrying the cover-page share count (module docstring).
FORMS: frozenset[str] = frozenset(
    {"10-K", "10-K405", "10-KT", "10-KSB", "10-KSB40", "10-Q", "10-QT", "10-QSB"}
)

#: The index the history is built for.
INDEX_ID = "SP500"


class IndexError_(ValueError):
    """A master.idx line or file is not in EDGAR's format."""


@dataclass(frozen=True, order=True)
class FilingRef:
    """One filing from ``master.idx``. ``path`` is relative to ``https://www.sec.gov/Archives/``."""

    cik: str  # ten digits
    filed: date
    form: str
    accession: str  # 0000040545-97-000005
    company: str
    path: str  # edgar/data/40545/0000040545-97-000005.txt


def quarters(start: date = HORIZON_START, end: date = HORIZON_END) -> list[tuple[int, int]]:
    """Every (year, quarter) whose days meet ``[start, end]``, ascending."""
    out: list[tuple[int, int]] = []
    y, q = start.year, (start.month - 1) // 3 + 1
    while (y, q) <= (end.year, (end.month - 1) // 3 + 1):
        out.append((y, q))
        y, q = (y + 1, 1) if q == 4 else (y, q + 1)
    return out


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


def index_url(year: int, quarter: int) -> str:
    return f"https://www.sec.gov/Archives/edgar/full-index/{year}/QTR{quarter}/master.gz"


def accession_of(path: str) -> str:
    """``edgar/data/40545/0000040545-97-000005.txt`` -> ``0000040545-97-000005``."""
    name = path.rsplit("/", 1)[-1]
    if not name.endswith(".txt"):
        raise IndexError_(f"not a submission path: {path!r}")
    acc = name[: -len(".txt")]
    parts = acc.split("-")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise IndexError_(f"not an accession number: {acc!r}")
    return acc


def parse_master(lines: Iterable[str], forms: frozenset[str] = FORMS) -> Iterator[FilingRef]:
    """The ``forms`` filings of one ``master.idx``, in file order.

    The file opens with a free-text preamble and a dashed rule; everything after the rule is
    data. Lines of other forms are skipped before any parsing, which is most of the file.
    """
    body = False
    for line in lines:
        if not body:
            if line.startswith("-----"):
                body = True
            continue
        parts = line.rstrip("\r\n").split("|")
        if len(parts) != 5:
            continue
        raw_cik, company, form, filed, path = parts
        if form.strip() not in forms:
            continue
        yield FilingRef(
            cik=cikmod.normalize_cik(raw_cik),
            filed=date.fromisoformat(filed.strip()),
            form=form.strip(),
            accession=accession_of(path.strip()),
            company=company.strip(),
            path=path.strip(),
        )


def read_master_gz(blob: bytes, forms: frozenset[str] = FORMS) -> list[FilingRef]:
    """A downloaded ``master.gz`` body as FilingRefs. EDGAR writes it in latin-1."""
    text = gzip.decompress(blob).decode("latin-1")
    return list(parse_master(text.splitlines(), forms))


@dataclass(frozen=True)
class Window:
    """The filing dates wanted for one filer, and the symbols it traded as while a member."""

    cik: str
    start: date
    end: date
    symbols: tuple[str, ...]


def windows(
    intervals: Sequence[membership.Interval],
    index: Mapping[str, Sequence[cikmod.CikRow]],
    *,
    index_id: str = INDEX_ID,
    horizon_start: date = HORIZON_START,
    horizon_end: date = HORIZON_END,
    lead_days: int = LEAD_DAYS,
) -> dict[str, Window]:
    """Per filer CIK, the filing-date window its reports are wanted for (module docstring).

    Each membership interval of ``index_id`` is cut by the date-scoped ticker map into
    (filer, member span) pieces; a filer's window is ``[first span start - lead_days, last span
    end]`` clipped to the horizon. ``NONE`` tenures contribute nothing.
    """
    spans: dict[str, list[tuple[date, date, str]]] = {}
    hz_end = horizon_end + timedelta(days=1)
    for iv in intervals:
        if iv.index_id != index_id:
            continue
        for row in index.get(iv.symbol, ()):
            if row.cik is None:
                continue
            lo = max(iv.start_date, row.start_date)
            ends = [e for e in (iv.end_date, row.end_date) if e is not None]
            hi = min([*ends, hz_end])
            if lo >= hi or hi <= horizon_start:
                continue
            spans.setdefault(row.cik, []).append((lo, hi, iv.symbol))
    out: dict[str, Window] = {}
    for key, group in sorted(spans.items()):
        first = min(s[0] for s in group)
        last = max(s[1] for s in group)
        start = max(horizon_start, first - timedelta(days=lead_days))
        end = min(horizon_end, last)
        if start > end:
            continue
        out[key] = Window(key, start, end, tuple(sorted({s[2] for s in group})))
    return out


def select(refs: Iterable[FilingRef], wins: Mapping[str, Window]) -> list[FilingRef]:
    """The refs filed inside their filer's window, sorted by (cik, filed), duplicates dropped.

    A filing made jointly by several registrants is listed once per co-registrant CIK and keeps
    one ref per filer that wants it: the cover may state each registrant's count, and the
    downloader fetches the accession once whatever the number of refs.
    """
    out = {
        (ref.cik, ref.accession): ref
        for ref in refs
        if (win := wins.get(ref.cik)) is not None and win.start <= ref.filed <= win.end
    }
    return sorted(out.values())

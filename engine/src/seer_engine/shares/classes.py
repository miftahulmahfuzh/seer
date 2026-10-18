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

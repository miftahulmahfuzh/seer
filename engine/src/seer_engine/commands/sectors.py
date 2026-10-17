"""sectors -- refresh the vendored CIK -> SIC file from EDGAR, and report sector coverage.

``refresh`` asks ``data.sec.gov/submissions`` for every CIK the date-scoped ticker map
(``ticker_cik.csv`` + ``ticker_cik_pre2009.csv``) can resolve to, about 1,150 filers at SEC's
10 requests/second -- two to three minutes -- and rewrites ``engine/data/cik_sic.csv``. A row
whose SIC, description and name come back unchanged keeps its old ``fetched`` date, so a
refresh that finds nothing new leaves the file byte-identical and the diff of a real refresh is
exactly the filers that moved. Under the global ``--dry-run`` it fetches and prints that diff and
writes nothing. ``--missing-only`` fetches just the CIKs the file does not have yet, which is
what a new ticker_cik row needs.

The committed csv is the source of truth: backtests and paper read it through
``seer_engine.sectors`` and nothing at backtest or paper time touches the network. Refreshing
is a deliberate, reviewed change to a vendored input, like re-vendoring the membership files.

``report`` needs no network. Per calendar year from 1996, it prints the share of S&P 500
member-days (and of all-index member-days) whose symbol resolves to a sector, the Fama-French
12 mix of the S&P 500 by count, the symbols costing the most unresolved member-days, and, with
``--picks``, the sector of each named symbol on ``--on`` -- the sanity check that a book's oil
names land in one bucket.
"""

from __future__ import annotations

import argparse
import bisect
import logging
from collections import Counter
from collections.abc import Sequence
from datetime import date, datetime, timezone
from pathlib import Path

from seer_engine import cik as cikmod
from seer_engine import dates, membership, sec, sectors

log = logging.getLogger(__name__)

HELP = "Refresh engine/data/cik_sic.csv from EDGAR, or report sector coverage (no network)."

REPORT_FROM = date(1996, 1, 2)


def add_arguments(p: argparse.ArgumentParser) -> None:
    sub = p.add_subparsers(dest="action", metavar="<action>", required=True)
    r = sub.add_parser("refresh", help="fetch every map CIK's SIC from EDGAR and rewrite the csv")
    r.add_argument("--out", type=Path, default=sectors.DATA_DIR / sectors.CIK_SIC_FILE)
    r.add_argument(
        "--missing-only",
        action="store_true",
        help="fetch only CIKs absent from the current file",
    )
    rep = sub.add_parser("report", help="coverage by year, FF12 mix, and optional picks")
    rep.add_argument("--through", type=date.fromisoformat, default=None,
                     help="last day counted (default: today, UTC)")
    rep.add_argument("--picks", default="", help="comma-separated symbols to label on --on")
    rep.add_argument("--on", type=date.fromisoformat, default=None,
                     help="date for --picks (default: --through)")
    rep.add_argument("--top", type=int, default=15, help="unresolved symbols to list (default 15)")


def run(args: argparse.Namespace) -> int:
    if args.action == "refresh":
        return refresh(args)
    return report(args)


# --- refresh --------------------------------------------------------------------------------


def diff_rows(
    old: dict[str, sectors.SicRow], fetched: dict[str, sec.Filer], today: date
) -> tuple[dict[str, sectors.SicRow], list[str]]:
    """Merge freshly fetched filers over ``old``; keep ``old.fetched`` where nothing changed.

    Returns the merged rows (``old`` rows not refetched are kept as they are) and one line per
    added or changed CIK. Pure, so the keep-the-date rule is tested without a network.
    """
    merged = dict(old)
    changes: list[str] = []
    for key, filer in sorted(fetched.items()):
        new = sectors.SicRow(
            cik=key,
            sic=filer.sic,
            sic_description=filer.sic_description,
            entity_name=filer.name,
            fetched=today,
            source="edgar-submissions",
        )
        prev = old.get(key)
        if prev is not None and (prev.sic, prev.sic_description, prev.entity_name) == (
            new.sic, new.sic_description, new.entity_name
        ):
            continue
        merged[key] = new
        if prev is None:
            changes.append(f"+ {key} {new.sic} {new.entity_name}")
        else:
            changes.append(
                f"~ {key} {prev.sic} -> {new.sic} {prev.entity_name!r} -> {new.entity_name!r}"
            )
    return merged, changes


def refresh(args: argparse.Namespace) -> int:
    out: Path = args.out
    index = cikmod.load_index_with_history(cikmod.DATA_DIR)
    wanted = sectors.map_ciks(index)
    old = sectors.load_cik_sic(out) if out.exists() else {}
    todo = [c for c in wanted if c not in old] if args.missing_only else list(wanted)
    print(f"sectors refresh: {len(wanted)} CIKs in the map, {len(old)} in {out.name}, "
          f"fetching {len(todo)}")
    client = sec.Client(sec.require_contact())
    fetched: dict[str, sec.Filer] = {}
    missing: list[str] = []
    for i, key in enumerate(todo, start=1):
        try:
            fetched[key] = client.submissions(key)
        except sec.SecNotFound:
            missing.append(key)
        if i % 100 == 0:
            log.info("sectors refresh: %d/%d", i, len(todo))
    if missing:
        print(f"sectors refresh: EDGAR has no filer for {len(missing)} map CIK(s): "
              f"{', '.join(missing)}; fix ticker_cik first, nothing written")
        return 1
    today = datetime.now(timezone.utc).date()
    merged, changes = diff_rows(old, fetched, today)
    stale = sorted(set(merged) - set(wanted))
    for key in stale:
        del merged[key]
        changes.append(f"- {key} (no longer in the map)")
    for line in changes:
        print("  " + line)
    no_sic = sorted(k for k in wanted if merged[k].sic is None)
    print(f"sectors refresh: {len(changes)} change(s); {len(no_sic)} filer(s) with no SIC on EDGAR"
          + (f": {', '.join(no_sic)}" if no_sic else ""))
    if getattr(args, "dry_run", False):
        print(f"dry run: would write {len(merged)} rows to {out}")
        return 0
    n = sectors.write_cik_sic(out, merged.values())
    print(f"wrote {out}: {n} rows")
    return 0


# --- report ---------------------------------------------------------------------------------


def _count(sessions: Sequence[date], start: date, end: date | None) -> int:
    """Sessions in ``[start, end)``; ``end`` None is open."""
    lo = bisect.bisect_left(sessions, start)
    hi = len(sessions) if end is None else bisect.bisect_left(sessions, end)
    return max(0, hi - lo)


def _per_year(sessions: Sequence[date], start: date, end: date | None) -> Counter[int]:
    lo = bisect.bisect_left(sessions, start)
    hi = len(sessions) if end is None else bisect.bisect_left(sessions, end)
    return Counter(d.year for d in sessions[lo:hi])


def tally(
    intervals: Sequence[membership.Interval],
    smap: sectors.SectorMap,
    sessions: Sequence[date],
) -> tuple[Counter[int], dict[int, Counter[str]], Counter[str]]:
    """Member-days per year, member-days per year per sector (None -> ``Unknown``), and the
    unresolved member-days per symbol. Exact interval arithmetic, no per-day lookups."""
    total: Counter[int] = Counter()
    by_sector: dict[int, Counter[str]] = {}
    unresolved: Counter[str] = Counter()
    for iv in intervals:
        days = _per_year(sessions, iv.start_date, iv.end_date)
        total.update(days)
        covered: Counter[int] = Counter()
        for row in smap.index.get(iv.symbol, ()):
            lo = max(iv.start_date, row.start_date)
            ends = [e for e in (iv.end_date, row.end_date) if e is not None]
            hi = min(ends) if ends else None
            if hi is not None and hi <= lo:
                continue
            label = smap.sector_of(iv.symbol, lo)
            if label is None:
                continue
            part = _per_year(sessions, lo, hi)
            covered.update(part)
            for year, n in part.items():
                by_sector.setdefault(year, Counter())[label] += n
        for year, n in days.items():
            gap = n - covered.get(year, 0)
            if gap:
                by_sector.setdefault(year, Counter())[sectors.UNKNOWN] += gap
                unresolved[iv.symbol] += gap
    return total, by_sector, unresolved


def report(args: argparse.Namespace) -> int:
    through = args.through or datetime.now(timezone.utc).date()
    smap = sectors.load()
    universe = membership.compute_universe(membership.DATA_DIR)
    sessions = dates.sessions(REPORT_FROM, through)
    sp = [iv for iv in universe if iv.index_id == "SP500"]
    total, mix, unresolved = tally(sp, smap, sessions)
    all_total, all_mix, _ = tally(universe, smap, sessions)
    codes = list(smap.ff12.codes)

    print(f"S&P 500 member-days resolving to a sector, {REPORT_FROM.year}-{through.year} "
          f"(through {through})")
    print(f"{'year':>4} {'SP500 days':>10} {'SP500 %':>8} {'all-index %':>11}  FF12 mix of the "
          f"S&P 500 by count, % of member-days")
    print(" " * 37 + " ".join(f"{c:>5}" for c in [*codes, "Unkn"]))
    for year in sorted(total):
        n = total[year]
        known = n - mix[year].get(sectors.UNKNOWN, 0)
        a_n = all_total[year]
        a_known = a_n - all_mix[year].get(sectors.UNKNOWN, 0)
        shares = " ".join(
            f"{100 * mix[year].get(c, 0) / n:5.1f}" for c in [*codes, sectors.UNKNOWN]
        )
        print(f"{year:>4} {n:>10} {100 * known / n:>7.2f}% {100 * a_known / a_n:>10.2f}%  {shares}")
    n_all = sum(total.values())
    n_known = n_all - sum(m.get(sectors.UNKNOWN, 0) for m in mix.values())
    print(f"all  {n_all:>10} {100 * n_known / n_all:>7.2f}%")
    if unresolved:
        print(f"\nmost unresolved S&P 500 member-days (top {args.top}):")
        for symbol, n in unresolved.most_common(args.top):
            print(f"  {symbol:8s} {n:>6}  {_why(smap, symbol)}")

    picks = [s.strip().upper() for s in args.picks.split(",") if s.strip()]
    if picks:
        on = args.on or through
        print(f"\nsectors of {len(picks)} picks on {on}:")
        groups: dict[str, list[str]] = {}
        for symbol in picks:
            label = smap.sector_of(symbol, on)
            sic = smap.sic_of(symbol, on)
            row = smap.row(symbol, on)
            desc = smap.sics[row.cik].sic_description if row and row.cik in smap.sics else ""
            print(f"  {symbol:6s} {label or '-':6s} {sic if sic is not None else '-':>4}  {desc}")
            groups.setdefault(label or sectors.UNKNOWN, []).append(symbol)
        print("  mix: " + "; ".join(
            f"{k} {len(v)} ({', '.join(v)})"
            for k, v in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0]))
        ))
    return 0


def _why(smap: sectors.SectorMap, symbol: str) -> str:
    group = smap.index.get(symbol)
    if not group:
        return "no ticker_cik row"
    if any(r.cik is None for r in group):
        return "NONE: " + next(r.note for r in group if r.cik is None)[:80]
    if any(r.cik not in smap.sics or smap.sics[r.cik].sic is None for r in group):
        return "filer has no SIC on EDGAR"
    return "membership outside every tenure"

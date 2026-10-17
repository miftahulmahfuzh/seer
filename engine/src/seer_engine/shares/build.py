"""``shares build`` and ``shares report``: cache -> parsed, checked csv; csv -> coverage.

``build`` is the impure glue between the cache (``fetch``), the parser (``cover``), the price
files (``prices``) and the pure checks (``checks``). It reads only local files -- no network --
and writes the two vendored csvs plus, with ``--flags``, every flagged value with its
disposition for review. It prints the measures the history is judged by: the parse rate, the
XBRL overlap match rate and error distribution, and how many values were flagged, fixed and
excluded.

``report`` reads only the committed csv and the vendored maps: per year 1996-2015, the share of
S&P 500 member-days with a usable figure under the point-in-time rule, and the median age of the
figure used (count date to the day it is used). After 2010 the cover rows run out and coverage
falls unless the XBRL facts are joined (``--xbrl`` reads a store's ``fundamentals.csv``,
read-only), which is the 1996-today view the lab would get.
"""

from __future__ import annotations

import argparse
import bisect
import csv
import json
import logging
import statistics
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from concurrent.futures import ProcessPoolExecutor
from datetime import date, timedelta
from pathlib import Path

from seer_engine import cik as cikmod
from seer_engine import dates, membership
from seer_engine.shares import checks, cover, edgar_index, fetch, history, prices
from seer_engine.shares.edgar_index import FilingRef

log = logging.getLogger(__name__)

REPORT_FROM = date(1996, 1, 2)
REPORT_THROUGH = date(2015, 12, 31)


def add_arguments(sub) -> None:
    b = sub.add_parser("build", help="parse and check the cache, rewrite the vendored csvs")
    b.add_argument("--cache", type=Path, default=None)
    b.add_argument("--out-dir", type=Path, default=history.DATA_DIR)
    b.add_argument("--flags", type=Path, default=None, help="write every flagged value here (csv)")
    b.add_argument("--workers", type=int, default=6)
    r = sub.add_parser("report", help="coverage by year from the committed csv (no network)")
    r.add_argument("--data-dir", type=Path, default=history.DATA_DIR)
    r.add_argument("--xbrl", type=Path, default=None,
                   help="a store's fundamentals.csv to join (read-only), for the 1996-today view")
    r.add_argument("--max-age", type=int, default=history.DEFAULT_MAX_AGE_DAYS)


def run(args: argparse.Namespace) -> int:
    if args.action == "build":
        return build(args)
    return report(args)


def _cache(args: argparse.Namespace) -> Path:
    from seer_engine.commands.shares import default_cache

    return args.cache or default_cache()


# --- parse ------------------------------------------------------------------------------


def _parse_one(job: tuple[str, str, str, str]) -> tuple[str, str, object]:
    path, cik, filed, accession = job
    p = Path(path)
    if not p.exists():
        return cik, accession, "not cached"
    try:
        return cik, accession, cover.parse(fetch.read_head(p), date.fromisoformat(filed), cik)
    except cover.CoverError as exc:
        return cik, accession, str(exc)


def parse_all(cache: Path, refs: Sequence[FilingRef], workers: int) -> dict[tuple[str, str], object]:
    jobs = []
    for r in refs:
        if fetch.missing_path(cache, r).exists():
            continue
        jobs.append((str(fetch.filing_path(cache, r)), r.cik, r.filed.isoformat(), r.accession))
    out: dict[tuple[str, str], object] = {}
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for cik, acc, res in pool.map(_parse_one, jobs, chunksize=64):
            out[(cik, acc)] = res
    return out


# --- inputs for the checks ---------------------------------------------------------------


def read_xbrl(cache: Path, cik: str) -> dict[str, float]:
    """accession -> tagged shares for one filer (``xbrl_by_symbol``'s rule: latest period end
    within the accession, distinct values summed)."""
    path = fetch.xbrl_path(cache, cik)
    if not path.exists():
        return {}
    doc = json.loads(path.read_text(encoding="utf-8"))
    rows = (doc.get("units") or {}).get("shares") or []
    by: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if isinstance(r, dict) and r.get("accn") and isinstance(r.get("val"), (int, float)) and r["val"] > 0:
            by[r["accn"]].append(r)
    out: dict[str, float] = {}
    for accn, group in by.items():
        end = max(g.get("end", "") for g in group)
        out[accn] = float(sum({g["val"] for g in group if g.get("end", "") == end}))
    return out


def tenures(index: Mapping[str, Sequence[cikmod.CikRow]]) -> dict[str, list[cikmod.CikRow]]:
    by: dict[str, list[cikmod.CikRow]] = defaultdict(list)
    for group in index.values():
        for row in group:
            if row.cik:
                by[row.cik].append(row)
    return by


def symbol_for(rows: Sequence[cikmod.CikRow], on: date) -> str:
    """The symbol whose tenure with this filer covers ``on``, else the nearest tenure's."""
    best: tuple[int, str] | None = None
    for r in rows:
        if r.covers(on):
            return r.symbol
        end = r.end_date or date.max
        gap = (r.start_date - on).days if on < r.start_date else (on - end).days
        if best is None or gap < best[0]:
            best = (gap, r.symbol)
    return best[1] if best else ""


def _within(r: cikmod.CikRow, d: date, before: int, after: int) -> bool:
    end = r.end_date or date.max
    return r.start_date - timedelta(days=before) <= d <= (end if end == date.max else end + timedelta(days=after))


def build(args: argparse.Namespace) -> int:
    cache = _cache(args)
    universe = membership.compute_universe(membership.DATA_DIR)
    index = cikmod.load_index_with_history(cikmod.DATA_DIR)
    wins = edgar_index.windows(universe, index)
    refs_all: list[FilingRef] = []
    for y, q in edgar_index.quarters():
        p = fetch.index_path(cache, y, q)
        if not p.exists():
            print(f"shares build: {p} missing; run `shares download` first")
            return 1
        refs_all.extend(edgar_index.read_master_gz(p.read_bytes()))
    refs = edgar_index.select(refs_all, wins)
    missing = sum(1 for r in refs if fetch.missing_path(cache, r).exists())
    parsed = parse_all(cache, refs, args.workers)
    errors = Counter(v for v in parsed.values() if isinstance(v, str))
    n_ok = sum(1 for v in parsed.values() if isinstance(v, cover.Cover))
    print(f"shares build: {len(refs)} wanted filings ({missing} 404 on EDGAR); parsed {n_ok} of "
          f"{len(parsed)} ({100 * n_ok / max(1, len(parsed)):.1f}%)")
    for why, n in errors.most_common():
        print(f"  not parsed: {n:>6}  {why}")

    by_cik_rows = tenures(index)
    ref_of = {(r.cik, r.accession): r for r in refs}
    items: dict[str, list[checks.Item]] = defaultdict(list)
    for (key, acc), res in sorted(parsed.items()):
        if not isinstance(res, cover.Cover):
            continue
        ref = ref_of[(key, acc)]
        flags = list(res.flags)
        items[key].append(checks.Item(
            cik=key, accession=acc, filed=ref.filed, as_of=res.as_of,
            symbol=symbol_for(by_cik_rows.get(key, ()), ref.filed), form=ref.form,
            shares=res.shares,
            classes=tuple((c.label, c.shares) for c in res.classes) if len(res.classes) > 1 else (),
            flags=flags,
        ))

    # 1. XBRL overlap.
    compared: list[tuple[checks.Item, bool, float]] = []
    for key, group in items.items():
        compared.extend(checks.apply_xbrl(group, read_xbrl(cache, key)))

    # Prices and splits per filer, read only inside its tenures.
    price_cache: dict[str, prices.PriceSeries | None] = {}

    def series(sym: str) -> prices.PriceSeries | None:
        if sym not in price_cache:
            price_cache[sym] = prices.load(sym, cache, cache.parent / "eodhd")
        return price_cache[sym]

    no_price = 0
    bad_series: list[str] = []
    for key, group in items.items():
        rows = by_cik_rows.get(key, [])
        splits: list[checks.Split] = []
        for r in rows:
            s = series(r.symbol)
            if s is None:
                continue
            for sp in s.splits:
                if _within(r, sp.date, 400, 30) and not any(abs((x.date - sp.date).days) <= 5 for x in splits):
                    splits.append(checks.Split(sp.date, float(sp.ratio)))
        splits.sort(key=lambda s: s.date)
        for it in group:
            for r in rows:
                if _within(r, it.counted, 200, 30):
                    s = series(r.symbol)
                    c = s.close_on(it.counted) if s else None
                    if c is not None:
                        it.raw_close = c
                        break
            if it.raw_close is None:
                no_price += 1
        # A price series that makes most of a filer's counts implausible is another company's
        # (a reused ticker): the counts are not judged by it.
        priced = [it for it in group if it.raw_close is not None]
        if priced and sum(not (checks.MV_SOFT[0] <= it.mv <= checks.MV_SOFT[1]) for it in priced) > 0.3 * len(priced):
            for it in priced:
                it.raw_close = None
            bad_series.append(key)
            no_price += len(priced)
        # 2/3. series, 4. market value.
        checks.unit_checks(group)
        checks.series_checks(group, splits)
        checks.mv_checks(group)
        checks.finalize(group)

    all_items = [it for g in items.values() for it in g]
    kept = [it for it in all_items if not it.excluded]
    excluded = [it for it in all_items if it.excluded]
    flagged = [it for it in all_items if it.flags or it.excluded]
    fixed = [it for it in kept if any(f.startswith("fixed") for f in it.flags)]

    # Report the XBRL overlap before writing.
    if compared:
        rels = sorted(abs(rel) for _, _, rel in compared)
        ok = sum(1 for _, m, _ in compared if m)
        q = lambda p: rels[min(len(rels) - 1, int(p * len(rels)))]  # noqa: E731
        print(f"XBRL overlap: {len(compared)} filings with both readings; {ok} match within "
              f"{checks.XBRL_TOL:.1%} ({100 * ok / len(compared):.1f}%); |error| median {q(0.5):.4%}, "
              f"p90 {q(0.9):.3%}, p99 {q(0.99):.2%}, max {rels[-1]:.1%}")
        bands = Counter(
            "exact" if r == 0 else "<0.5%" if r <= 0.005 else "<5%" if r <= 0.05 else "<50%" if r <= 0.5 else ">=50%"
            for r in rels
        )
        print("  |error| bands: " + ", ".join(f"{k} {bands[k]}" for k in ("exact", "<0.5%", "<5%", "<50%", ">=50%")))
    flag_counts = Counter(f for it in all_items for f in it.flags)
    print(f"checks: {len(all_items)} values; {len(flagged)} flagged; {len(fixed)} fixed; "
          f"{len(excluded)} excluded; {len(kept)} kept; {no_price} without a raw close to check MV "
          f"({len(bad_series)} filers whose price series disagreed with most of their counts)")
    print("  flags: " + ", ".join(f"{k} {v}" for k, v in flag_counts.most_common()))
    reasons = Counter(it.excluded.split(":")[0].split(" ")[0] for it in excluded)
    print("  excluded by: " + ", ".join(f"{k} {v}" for k, v in reasons.most_common()))

    rows_out = [
        history.ShareRow(
            cik=it.cik, filed=it.filed, accession=it.accession, symbol=it.symbol, as_of=it.as_of,
            form=it.form, shares=it.shares, classes=it.classes, flags=tuple(it.flags),
            note="; ".join(it.notes),
        )
        for it in kept
    ]
    if getattr(args, "dry_run", False):
        print("dry run: nothing written")
        return 0
    out_dir: Path = args.out_dir
    n = history.write_rows(out_dir / history.SHARES_FILE, rows_out)
    with open(out_dir / history.EXCLUDED_FILE, "w", encoding="utf-8", newline="\n") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(history.EXCLUDED_HEADER)
        for it in sorted(excluded, key=lambda i: (i.cik, i.filed, i.accession)):
            w.writerow([it.cik, it.symbol, it.filed.isoformat(), it.as_of.isoformat() if it.as_of else "",
                        it.form, it.accession, it.shares, it.excluded])
    print(f"wrote {out_dir / history.SHARES_FILE}: {n} rows; {out_dir / history.EXCLUDED_FILE}: "
          f"{len(excluded)} rows")
    if args.flags:
        with open(args.flags, "w", encoding="utf-8", newline="\n") as fh:
            w = csv.writer(fh, lineterminator="\n")
            w.writerow(["cik", "symbol", "filed", "as_of", "accession", "shares", "xbrl", "mv_bn",
                        "flags", "disposition", "why"])
            for it in sorted(flagged, key=lambda i: (i.cik, i.filed)):
                disp = "excluded" if it.excluded else ("fixed" if it in fixed else "kept")
                w.writerow([it.cik, it.symbol, it.filed, it.as_of or "", it.accession, it.shares,
                            "" if it.xbrl is None else int(it.xbrl),
                            "" if it.mv is None else f"{it.mv / 1e9:.3f}", ";".join(it.flags), disp,
                            it.excluded or "; ".join(it.notes)])
        print(f"wrote {args.flags}: {len(flagged)} flagged values")
    return 0


# --- report -----------------------------------------------------------------------------


def read_store_facts(path: Path) -> list[history.XbrlFact]:
    """The share-count facts of a store's ``fundamentals.csv`` (read-only)."""
    from seer_engine.fundamentals.panel import fact_from_row

    out = []
    with open(path, newline="", encoding="utf-8") as fh:
        for raw in csv.DictReader(fh):
            if raw["tag"] not in history.XBRL_TAGS:
                continue
            row = dict(raw)
            row["val"] = float(row["val"])
            for k in ("period_start", "period_end", "filed"):
                row[k] = date.fromisoformat(row[k]) if row[k] else None
            row["fy"] = int(row["fy"]) if row["fy"] else None
            row["fp"] = row["fp"] or None
            out.append(fact_from_row(row))
    return out


def coverage(
    hist: history.SharesHistory,
    intervals: Iterable[membership.Interval],
    sessions: Sequence[date],
    *,
    step: int = 5,
) -> dict[int, tuple[int, int, list[int]]]:
    """Per year: (member-days sampled, with a usable figure, ages in days). Every ``step``-th
    session is sampled -- a figure changes at most once a quarter, so a weekly sample measures
    the same share as a daily one at a fifth of the lookups."""
    sample = sessions[::step]
    out: dict[int, tuple[int, int, list[int]]] = {}
    for iv in intervals:
        lo = bisect.bisect_left(sample, iv.start_date)
        hi = len(sample) if iv.end_date is None else bisect.bisect_left(sample, iv.end_date)
        for d in sample[lo:hi]:
            n, k, ages = out.setdefault(d.year, (0, 0, []))
            obs = hist.shares_on(iv.symbol, d)
            if obs is None:
                out[d.year] = (n + 1, k, ages)
            else:
                ages.append(obs.age_days)
                out[d.year] = (n + 1, k + 1, ages)
    return out


def report(args: argparse.Namespace) -> int:
    facts = read_store_facts(args.xbrl) if args.xbrl else []
    hist = history.load(args.data_dir, facts, max_age_days=args.max_age)
    universe = membership.compute_universe(membership.DATA_DIR)
    sp = [iv for iv in universe if iv.index_id == "SP500"]
    sessions = dates.sessions(REPORT_FROM, REPORT_THROUGH)
    cov = coverage(hist, sp, sessions)
    src = "EDGAR cover pages" + (" + XBRL facts" if facts else "")
    print(f"S&P 500 member-days with a usable share count ({src}; figure filed on or before the "
          f"day, at most {args.max_age} days old; weekly sample)")
    print(f"{'year':>4} {'member-days':>11} {'covered':>8} {'median age (d)':>15}")
    for year in sorted(cov):
        n, k, ages = cov[year]
        med = statistics.median(ages) if ages else float("nan")
        print(f"{year:>4} {n:>11} {100 * k / n:>7.2f}% {med:>15.0f}")
    return 0

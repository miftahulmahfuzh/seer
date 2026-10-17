"""``shares fetch-splits``, ``shares store`` and ``shares store-report``: company size in the stores.

``fetch-splits`` (network) caches yfinance's split list for every symbol a store has bars for
(``splits.fetch_yfinance``; ``engine/.cache/yfinance/splits``, gitignored, resumable).

``store`` (no network) writes ``shares.csv`` and ``splits.csv`` into an existing dev or test store
through ``research.refresh_shares``: every other file is carried over byte for byte, so the price
fingerprint -- the one every recorded lab trial is compared on -- does not move; the store's full
fingerprint does, as it did for every optional file before. The share rows are the point-in-time
answers of ``history.SharesHistory`` (the vendored cover-page csv joined to the store's own XBRL
facts in ``fundamentals.csv``, or ``--xbrl``'s for a store without a panel) for every index member
of the store's window; the split rows are yfinance's list for every symbol with bars, cut at
``--basis``, the day the store's bars were downloaded (``splits`` module docstring). The
survivorship-check store is refused here: its added symbols were adjusted by its own cleaning, so it
is refreshed by ``survivorship_store --refresh-shares``, which merges their lists in.

``store-report`` (no network, writes nothing) loads a store and prints what the size accessor
gives: per year, the share of index member-days with a market value (and, separately, with a share
count and with a close), the largest companies by market value on chosen dates, and -- the check
that the split list really is the one behind the adjusted closes -- every member-day close rebuilt
from the store (``adjusted x raw_factor``) against EODHD's raw close for the same day.
"""

from __future__ import annotations

import argparse
import logging
import math
import statistics
from collections import defaultdict
from datetime import date
from pathlib import Path

from seer_engine import dates, research
from seer_engine.shares import history, prices, splits
from seer_engine.shares import store as share_store

log = logging.getLogger(__name__)

DEFAULT_REPORT_DATES = (date(1999, 12, 31), date(2007, 12, 31), date(2015, 9, 30))
AGREE_TIGHT = 0.005  # a rebuilt close within 0.5% of EODHD's raw close
AGREE_LOOSE = 0.02


def add_arguments(sub) -> None:
    f = sub.add_parser("fetch-splits", help="cache yfinance's split list for a store's symbols (network)")
    f.add_argument("--store", type=Path, required=True, help="the store whose bars name the symbols")
    f.add_argument("--splits-cache", type=Path, default=splits.CACHE_DIR)
    f.add_argument("--refetch", action="store_true", help="fetch cached symbols again")

    s = sub.add_parser("store", help="write shares.csv and splits.csv into a dev or test store (no network)")
    s.add_argument("--store", type=Path, required=True,
                   help="the store to extend, an absolute path to the real directory (never a symlink)")
    s.add_argument("--basis", type=date.fromisoformat, required=True, metavar="YYYY-MM-DD",
                   help="the day the store's bars were downloaded: splits after it were not applied")
    s.add_argument("--splits-cache", type=Path, default=splits.CACHE_DIR)
    s.add_argument("--xbrl", type=Path, default=None,
                   help="a fundamentals.csv to join (default: the store's own; required when it has none)")
    s.add_argument("--data-dir", type=Path, default=history.DATA_DIR)
    s.add_argument("--evidence-store", type=Path, action="append", default=[],
                   help="another store of the same vendor whose bars run past this one's window (the "
                        "test store, for the dev store): its closes judge the listed splits after the "
                        "window as well (repeatable)")

    r = sub.add_parser("store-report", help="size coverage, the largest companies, and the split check")
    r.add_argument("--store", type=Path, required=True)
    r.add_argument("--dates", default=",".join(d.isoformat() for d in DEFAULT_REPORT_DATES),
                   help="comma-separated dates for the largest-companies tables")
    r.add_argument("--top", type=int, default=10)
    r.add_argument("--eodhd-cache", type=Path, default=prices.EODHD_CACHE)
    r.add_argument("--edgar-cache", type=Path, default=None,
                   help="the shares download cache (default $SEER_EDGAR_CACHE or engine/.cache/edgar)")
    r.add_argument("--no-check", action="store_true", help="skip the EODHD raw-close check")


def run(args: argparse.Namespace) -> int:
    if args.action == "fetch-splits":
        return fetch_splits(args)
    if args.action == "store":
        return write(args)
    return report(args)


def bar_symbols(store: Path) -> list[str]:
    """Every symbol in ``bars.csv``, in file order (the file is grouped by symbol)."""
    out: list[str] = []
    with open(store / research.BARS_FILE, encoding="utf-8") as fh:
        next(fh)
        for line in fh:
            s = line.split(",", 1)[0]
            if not out or out[-1] != s:
                out.append(s)
    return out


def closes_by_symbol(store: Path, symbols: list[str]) -> dict[str, tuple[list[date], list[float]]]:
    """``symbol -> (dates, closes)`` from a store's ``bars.csv``, for ``symbols`` only. Read-only;
    the manifest is not checked here (``refresh_shares`` verifies the store it writes)."""
    want = set(symbols)
    out: dict[str, tuple[list[date], list[float]]] = {}
    with open(store / research.BARS_FILE, encoding="utf-8") as fh:
        next(fh)
        for line in fh:
            s, rest = line.split(",", 1)
            if s not in want:
                continue
            f = rest.split(",")
            days, closes = out.setdefault(s, ([], []))
            days.append(date.fromisoformat(f[0]))
            closes.append(float(f[4]))
    return out


def fetch_splits(args: argparse.Namespace) -> int:
    symbols = bar_symbols(Path(args.store))
    if getattr(args, "dry_run", False):
        print(f"dry run: would fetch the split lists of up to {len(symbols)} symbols")
        return 0
    fetched, unknown, failed = splits.fetch_yfinance(symbols, Path(args.splits_cache), refetch=args.refetch)
    print(f"splits: {len(symbols)} symbols, {fetched} fetched, {unknown} unknown to Yahoo, "
          f"{len(failed)} failed{': ' + ', '.join(failed[:20]) if failed else ''}")
    return 1 if failed else 0


def write(args: argparse.Namespace) -> int:
    store = Path(args.store)
    if store.is_symlink():
        print(f"shares store: {store} is a symlink; pass the real directory")
        return 2
    try:
        window = research.declared_window(store)
        purpose = research.declared_purpose(store)
        before = research._manifest_json(store)[1]
    except ValueError as exc:
        print(f"shares store: {exc}")
        return 2
    if purpose is not None:
        print(f"shares store: {store} is a {purpose!r} store; its added symbols carry their own "
              "split lists -- use `survivorship_store --refresh-shares`")
        return 2
    if args.basis < window.end:
        print(f"shares store: --basis {args.basis} is before the store's window end {window.end}")
        return 2
    xbrl = args.xbrl
    if xbrl is None:
        if research.FUNDAMENTALS_FILE not in before["files"]:
            print(f"shares store: {store} has no {research.FUNDAMENTALS_FILE}; pass --xbrl with one "
                  "(the dev store's panel runs to 2026 and serves the test window too)")
            return 2
        xbrl = store / research.FUNDAMENTALS_FILE
    from seer_engine.shares.build import read_store_facts

    facts = read_store_facts(Path(xbrl))
    hist = share_store.history_for(facts, Path(args.data_dir))
    members = sorted(set(research.requested_symbols(window=window)) - set(research.RESEARCH_ETFS))
    rows = share_store.change_points(hist, members, history.FIRST_FILED, window.end)
    shares_lines = share_store.shares_lines(rows)

    served = bar_symbols(store)
    by_symbol: dict[str, tuple[splits.Split, ...]] = {}
    missing: list[str] = []
    unknown: list[str] = []
    for symbol in served:
        got = splits.read_yfinance(Path(args.splits_cache), symbol)
        if got is None:
            path = Path(args.splits_cache) / f"{symbol}.json"
            (unknown if path.is_file() else missing).append(symbol)
            continue
        by_symbol[symbol] = got
    if missing:
        print(f"shares store: {len(missing)} symbols have no cached split list ({', '.join(missing[:10])}"
              f"{'...' if len(missing) > 10 else ''}); run `shares fetch-splits --store {store}` first")
        return 2
    evidence = [closes_by_symbol(store, sorted(by_symbol))]
    evidence += [closes_by_symbol(Path(e), sorted(by_symbol)) for e in args.evidence_store]
    dropped: list[tuple[str, object]] = []
    for symbol, listed in list(by_symbol.items()):
        if not listed:
            continue
        series = [ev[symbol] for ev in evidence if symbol in ev]
        applied, never = share_store.applied_by_vendor(listed, series)
        by_symbol[symbol] = tuple(applied)
        dropped += [(symbol, x) for x in never]
    split_lines = share_store.split_lines(
        by_symbol, store_start=research.STORE_START, window_end=window.end, basis=args.basis
    )
    print(f"shares store {store} ({window.name} window ending {window.end}):")
    print(f"  {len(members)} index members, {len({r.symbol for r in rows})} with a share count, "
          f"{len(shares_lines)} share rows ({len(facts)} XBRL share facts joined from {xbrl})")
    print(f"  {len(served)} symbols with bars, {len(by_symbol)} with a yfinance split list "
          f"({len(unknown)} unknown to Yahoo), {len(split_lines)} split rows, basis {args.basis}")
    if dropped:
        print(f"  {len(dropped)} listed splits the adjusted closes do not carry, left out:")
        for symbol, x in sorted(dropped, key=lambda t: (t[1].date, t[0])):
            print(f"    {symbol:<6} {x.date} ratio {x.ratio:g}")
    if getattr(args, "dry_run", False):
        print("  dry run: nothing written")
        return 0
    try:
        manifest = research.refresh_shares(store, shares_lines, split_lines, window=window)
    except (research.ResearchStoreError, ValueError) as exc:
        print(f"shares store: refused, nothing written: {exc}")
        return 2
    old_p = research.price_fingerprint_of(before["files"])
    new_p = research.price_fingerprint_of(manifest["files"])
    print(f"  fingerprint {before['fingerprint']} -> {manifest['fingerprint']}")
    print(f"  price fingerprint {old_p} -> {new_p} ({'unchanged' if old_p == new_p else 'MOVED'})")
    return 0 if old_p == new_p else 1


# --- report -----------------------------------------------------------------------------


def coverage(data: research.ResearchData) -> list[tuple[int, int, int, int, int]]:
    """Per year: (member-days, with a share count, with a close, with a market value). Every
    session of the window from ``MEMBERSHIP_START``; ETFs excluded; both indices' members."""
    m = data.market
    etfs = set(research.RESEARCH_ETFS)
    start = research.MEMBERSHIP_START
    out: dict[int, list[int]] = defaultdict(lambda: [0, 0, 0, 0])
    for d in dates.sessions(start, data.window.end):
        row = out[d.year]
        for s in m.membership.members_on(d):
            if s in etfs:
                continue
            row[0] += 1
            row[1] += m.shares_on(s, d) is not None
            h = m.history.get(s)
            row[2] += h is not None and h.index_of(d) is not None
            row[3] += m.market_value(s, d) is not None
    return [(y, *v) for y, v in sorted(out.items())]


def top(data: research.ResearchData, on: date, n: int) -> tuple[date, list[tuple[str, float, float]]]:
    """The ``n`` largest index members by market value on the last session on or before ``on``:
    ``(symbol, market value, shares)``."""
    d = dates.sessions(date(on.year - 1, 1, 1), on)[-1]
    m = data.market
    rows = []
    for s in m.membership.members_on(d):
        mv = m.market_value(s, d)
        if mv is not None:
            rows.append((s, mv, m.shares_on(s, d) or math.nan))
    rows.sort(key=lambda r: -r[1])
    return d, rows[:n]


def split_check(data: research.ResearchData, eodhd_cache: Path, edgar_cache: Path):
    """Rebuilt raw closes vs EODHD's, on member days: (pairs, within 0.5%, within 2%, per-symbol
    median |log ratio| of the symbols beyond 2%, symbols checked)."""
    m = data.market
    days_by: dict[str, list[date]] = defaultdict(list)
    for d in dates.sessions(research.MEMBERSHIP_START, data.window.end):
        for s in m.membership.members_on(d):
            days_by[s].append(d)
    pairs = tight = loose = 0
    bad: list[tuple[str, float, int]] = []
    checked = 0
    for s, days in sorted(days_by.items()):
        h = m.history.get(s)
        if h is None:
            continue
        series = prices.load(s, edgar_cache, eodhd_cache)
        if series is None:
            continue
        raw_by = dict(zip(series.dates, series.closes))
        errs = []
        for d in days:
            i = h.index_of(d)
            raw = raw_by.get(d)
            if i is None or raw is None:
                continue
            rebuilt = float(h.close[i]) * m.shares.raw_factor(s, d)
            errs.append(abs(math.log(rebuilt / raw)))
        if not errs:
            continue
        checked += 1
        pairs += len(errs)
        tight += sum(e <= math.log1p(AGREE_TIGHT) for e in errs)
        loose += sum(e <= math.log1p(AGREE_LOOSE) for e in errs)
        med = statistics.median(errs)
        if med > math.log1p(AGREE_LOOSE):
            bad.append((s, math.expm1(med), len(errs)))
    bad.sort(key=lambda b: -b[1])
    return pairs, tight, loose, bad, checked


def report(args: argparse.Namespace) -> int:
    store = Path(args.store)
    try:
        data = research.load_store(store, window=research.declared_window(store))
    except ValueError as exc:
        print(f"shares store-report: {exc}")
        return 2
    m = data.market
    print(f"research store {store}: fingerprint {data.fingerprint}, price fingerprint "
          f"{data.price_fingerprint}, {data.window.name} window ending {data.window.end}")
    if len(m.shares) == 0:
        print(f"  no {research.SHARES_FILE}; run `shares store` first")
        return 2
    print(f"  {len(m.shares.symbols())} symbols with share rows, {len(m.shares)} rows")
    print("\nIndex member-days (S&P 500 and Nasdaq-100, ETFs excluded) with a market value")
    print(f"{'year':>4} {'member-days':>11} {'shares':>8} {'close':>8} {'mkt value':>9}")
    total = [0, 0, 0, 0]
    for y, n, sh, cl, mv in coverage(data):
        print(f"{y:>4} {n:>11} {sh / n:>8.1%} {cl / n:>8.1%} {mv / n:>9.1%}")
        total = [a + b for a, b in zip(total, (n, sh, cl, mv))]
    n = total[0]
    print(f"{'all':>4} {n:>11} {total[1] / n:>8.1%} {total[2] / n:>8.1%} {total[3] / n:>9.1%}")
    for raw in filter(None, args.dates.split(",")):
        d, rows = top(data, date.fromisoformat(raw.strip()), args.top)
        print(f"\nLargest {args.top} members by market value on {d}")
        for k, (s, mv, sh) in enumerate(rows, 1):
            print(f"  {k:>2}. {s:<6} ${mv / 1e9:>8.1f}B  ({sh / 1e9:.3f}B shares)")
    if not args.no_check:
        from seer_engine.commands.shares import default_cache

        edgar = args.edgar_cache or default_cache()
        pairs, tight, loose, bad, checked = split_check(data, Path(args.eodhd_cache), edgar)
        print("\nRebuilt closes (store close x splits after the day) vs EODHD's raw close, member days")
        if not pairs:
            print("  no EODHD raw closes found for this store's symbols")
        else:
            print(f"  {checked} symbols, {pairs:,} member-days: {tight / pairs:.2%} within 0.5%, "
                  f"{loose / pairs:.2%} within 2%")
            print(f"  {len(bad)} symbols whose median disagreement is above 2%"
                  + (":" if bad else ""))
            for s, med, k in bad[:25]:
                print(f"    {s:<6} off by {med:.1%} (median) over {k} days")
    return 0

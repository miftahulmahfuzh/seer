"""dividend_announcements — fetch dividend declaration dates from EODHD into the research store.

The one-month workflow (insight 109): subscribe to EODHD, put ``EODHD_API_TOKEN=...`` in the
repo-root ``.env.local``, then

    python -m seer_engine dividend_announcements --fetch       # ~1 call per store symbol, resumable
    python -m seer_engine dividend_announcements               # coverage report only, no writes
    python -m seer_engine dividend_announcements --refresh     # write dividend_announcements.csv

and cancel. ``--fetch`` saves every raw answer under ``engine/.cache/eodhd/dividends/`` (gitignored:
the repo is public and the vendor's licence is personal use), one JSON file per symbol, and skips
symbols already cached unless ``--refetch``; an interrupted fetch just runs again. It fetches every
symbol in the store's ``dividends.csv`` plus every requested member the store could not serve, so
the cache also covers the test-window store when that is built later.

The report and ``--refresh`` read only the cache and the store -- no network. ``--refresh``
writes through ``research.refresh_announcements``: every other store file is carried over byte
for byte, so the price fingerprint the lab compares trials on does not move. ``--store`` points
at another store (the test window's, once built). ``--demo`` uses EODHD's public demo token,
which answers for a few tickers such as AAPL and MSFT -- enough to try the path before paying.
The global ``--dry-run`` fetches nothing and writes nothing.

Exit codes: 0 ok; 1 a fetch failed for some symbols (the rest are cached); 2 no token, or the
store is missing or does not verify.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from seer_engine import config, research
from seer_engine import dividend_announcements as da
from seer_engine import eodhd

log = logging.getLogger(__name__)

HELP = (
    "Fetch dividend declaration dates from EODHD into a local cache, report their coverage, "
    "and write them into the research store (--refresh)."
)

CACHE_DIR = config.REPO_ROOT / "engine" / ".cache" / "eodhd" / "dividends"


def add_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument("--fetch", action="store_true", help="download missing symbols into the cache")
    p.add_argument("--refetch", action="store_true", help="with --fetch: download cached symbols again")
    p.add_argument("--refresh", action="store_true", help="write dividend_announcements.csv into the store")
    p.add_argument("--demo", action="store_true", help="use EODHD's public demo token (a few tickers only)")
    p.add_argument(
        "--symbols",
        default=None,
        help="comma-separated store symbols to fetch instead of all of them (e.g. AAPL,MSFT)",
    )
    p.add_argument("--store", type=Path, default=None, help=f"store directory (default {research.STORE_DIR})")
    p.add_argument("--cache", type=Path, default=CACHE_DIR, help=f"raw answer cache (default {CACHE_DIR})")


def _cache_file(cache: Path, symbol: str) -> Path:
    return cache / f"{symbol}.json"


def read_cache(cache: Path, symbols: list[str]) -> dict[str, list[eodhd.Declaration] | None]:
    """Cached vendor rows per symbol; absent from the result when the symbol was never fetched."""
    out: dict[str, list[eodhd.Declaration] | None] = {}
    for symbol in symbols:
        path = _cache_file(cache, symbol)
        if not path.is_file():
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        rows = doc.get("rows")
        out[symbol] = None if rows is None else eodhd.parse_dividends(rows)
    return out


def _write_cache(cache: Path, symbol: str, rows: list | None) -> None:
    cache.mkdir(parents=True, exist_ok=True)
    doc = {
        "symbol": symbol,
        "ticker": eodhd.ticker(symbol),
        "fetched": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rows": rows,  # None: EODHD has no such ticker
    }
    path = _cache_file(cache, symbol)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def fetch(
    client: eodhd.Client, cache: Path, symbols: list[str], *, refetch: bool
) -> tuple[int, int, list[str]]:
    """Download ``symbols`` into ``cache``; return (fetched, not found, failed symbols)."""
    fetched = missing = 0
    failed: list[str] = []
    for n, symbol in enumerate(symbols, 1):
        if not refetch and _cache_file(cache, symbol).is_file():
            continue
        try:
            rows = client.dividends(symbol)
        except eodhd.EodhdError as exc:
            log.error("eodhd: %s failed: %s", symbol, exc)
            failed.append(symbol)
            continue
        _write_cache(cache, symbol, rows)
        fetched += 1
        missing += rows is None
        if n % 50 == 0:
            log.info("eodhd: %d of %d symbols done", n, len(symbols))
    return fetched, missing, failed


def run(args: argparse.Namespace) -> int:
    store = Path(args.store) if args.store else research.STORE_DIR
    dry_run = bool(getattr(args, "dry_run", False))
    try:
        window = research.declared_window(store)
        data = research.load_store(store, window=window)
    except ValueError as exc:
        print(f"dividend_announcements: {exc}")
        return 2
    status = 0

    if args.fetch:
        token = eodhd.DEMO_TOKEN if args.demo else config.get(eodhd.TOKEN_ENV)
        if not token:
            print(
                f"dividend_announcements: {eodhd.TOKEN_ENV} is not set (checked the environment "
                f"and {config.env_file()}); add it, or pass --demo to try AAPL/MSFT"
            )
            return 2
        symbols = (
            [s.strip() for s in args.symbols.split(",") if s.strip()]
            if args.symbols
            else sorted(set(data.dividends) | set(data.unserved))
        )
        if dry_run:
            print(f"dry run: would fetch up to {len(symbols)} symbols into {args.cache}")
        else:
            fetched, missing, failed = fetch(
                eodhd.Client(token), Path(args.cache), symbols, refetch=args.refetch
            )
            print(
                f"fetched {fetched} symbols ({missing} unknown to EODHD) into {args.cache}; "
                f"{len(failed)} failed" + (f": {', '.join(failed)}" if failed else "")
            )
            if failed:
                status = 1

    vendor = read_cache(Path(args.cache), sorted(data.dividends))
    result = da.match(
        data.dividends, vendor, skip=research.RESEARCH_ETFS, years=(1996, window.end.year)
    )
    print(da.format_report(result))
    print(f"symbols in the cache: {len(vendor)} of {len(data.dividends)} with store dividends")

    if args.refresh:
        if dry_run:
            print(f"dry run: would write {len(result.rows)} rows to {store / research.ANNOUNCEMENTS_FILE}")
            return status
        del data
        try:
            manifest = research.refresh_announcements(store, result.rows, window=window)
        except (research.ResearchStoreError, ValueError) as exc:
            print(f"dividend_announcements: {exc}")
            return 2
        print(
            f"wrote {len(result.rows)} announcement dates into {store}; fingerprint "
            f"{manifest['fingerprint']} (price fingerprint unchanged)"
        )
    return status

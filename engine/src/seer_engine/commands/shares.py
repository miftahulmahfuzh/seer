"""shares -- the pre-2009 shares-outstanding history from EDGAR cover pages.

``download`` fills the gitignored cache (``engine/.cache/edgar/``, or ``--cache``): the sixty
quarterly master indexes 1995Q4-2010Q4, the head of every 10-K/10-Q filed by an S&P 500
member's filer inside its window (``shares.edgar_index``), and each filer's 2009+ XBRL
``dei:EntityCommonStockSharesOutstanding`` for the overlap check. Resumable: re-running fetches
only what is missing. It needs ``SEC_CONTACT_EMAIL``.

``build`` needs no network. It parses every cached head (``shares.cover``), validates the
parsed figures against XBRL, split history and price (``shares.checks``) and rewrites
``engine/data/shares_outstanding_pre2009.csv``; ``--flags`` writes every flagged value with its
disposition. ``report`` reads only the committed csv (and the vendored maps) and prints, per
year, the share of S&P 500 member-days with a usable figure and the median age of that figure.

The committed csv is the source of truth: nothing at backtest or paper time reads the cache or
the network, exactly as with ``cik_sic.csv``.

``fetch-splits``, ``store`` and ``store-report`` put the history into a research store, where the
lab reads it as ``Market.shares_on`` / ``Market.market_value`` (``shares.integrate``):

    python -m seer_engine shares fetch-splits --store /abs/engine/.research       # network, cached
    python -m seer_engine shares store --store /abs/engine/.research --basis 2026-10-04
    python -m seer_engine shares store-report --store /abs/engine/.research

``store`` carries every other store file byte for byte, so the price fingerprint never moves.
"""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

from seer_engine import cik as cikmod
from seer_engine import membership, sec
from seer_engine.shares import edgar_index, fetch

log = logging.getLogger(__name__)

HELP = (
    "Pre-2009 shares outstanding from EDGAR cover pages: download, build, report, and write the "
    "share history and split list into a research store."
)

CACHE_ENV = "SEER_EDGAR_CACHE"


def default_cache() -> Path:
    override = os.environ.get(CACHE_ENV)
    return Path(override) if override else fetch.CACHE_DIR


def add_arguments(p: argparse.ArgumentParser) -> None:
    sub = p.add_subparsers(dest="action", metavar="<action>", required=True)
    d = sub.add_parser("download", help="fill the EDGAR cache (indexes, filing heads, XBRL)")
    d.add_argument("--cache", type=Path, default=None, help=f"cache dir (default ${CACHE_ENV} "
                   "or engine/.cache/edgar)")
    d.add_argument("--workers", type=int, default=fetch.WORKERS)
    d.add_argument("--limit", type=int, default=0, help="fetch at most this many filings (0 = all)")
    d.add_argument("--skip-xbrl", action="store_true", help="do not fetch the XBRL overlap")
    try:
        from seer_engine.shares import build
    except ImportError:  # pragma: no cover - build lands after the downloader
        return
    build.add_arguments(sub)
    from seer_engine.shares import integrate

    integrate.add_arguments(sub)


def run(args: argparse.Namespace) -> int:
    if args.action == "download":
        return download(args)
    if args.action in ("fetch-splits", "store", "store-report"):
        from seer_engine.shares import integrate

        return integrate.run(args)
    from seer_engine.shares import build

    return build.run(args)


def plan() -> tuple[dict[str, edgar_index.Window], list[membership.Interval]]:
    universe = membership.compute_universe(membership.DATA_DIR)
    index = cikmod.load_index_with_history(cikmod.DATA_DIR)
    return edgar_index.windows(universe, index), universe


def download(args: argparse.Namespace) -> int:
    cache: Path = args.cache or default_cache()
    wins, _ = plan()
    archive = fetch.Archive(sec.require_contact())
    refs = fetch.fetch_indexes(archive, cache)
    wanted = edgar_index.select(refs, wins)
    n_acc = len({r.accession for r in wanted})
    print(f"shares download: {len(wins)} filers, {len(refs)} periodic reports in the indexes, "
          f"{len(wanted)} wanted ({n_acc} distinct filings)")
    if args.limit:
        wanted = wanted[: args.limit]
    if getattr(args, "dry_run", False):
        print("dry run: nothing fetched beyond the indexes")
        return 0
    t = fetch.fetch_filings(archive, cache, wanted, workers=args.workers)
    print(f"filings: {t.wanted} wanted, {t.cached} already cached, {t.fetched} fetched "
          f"({t.bytes_raw / 1e6:.0f} MB of text), {t.missing} missing on EDGAR, "
          f"{len(t.failed)} failed, {t.seconds / 60:.1f} min")
    for line in t.failed[:20]:
        print("  failed: " + line)
    if not args.skip_xbrl:
        x = fetch.fetch_xbrl(archive, cache, sorted(wins))
        print(f"xbrl: {x.wanted} filers, {x.cached} cached, {x.fetched} fetched, "
              f"{x.missing} never tagged, {len(x.failed)} failed, {x.seconds / 60:.1f} min")
    files, size = fetch.cache_size(cache)
    print(f"cache {cache}: {files} files, {size / 1e6:.0f} MB; {archive.calls} requests this run")
    return 1 if t.failed else 0

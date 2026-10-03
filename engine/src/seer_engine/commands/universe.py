"""`universe refresh` / `universe check`: point-in-time index membership.

refresh  Rebuild the ``universe`` table from the vendored files in ``engine/data``. Full replace
         in one transaction; a no-op (nothing written) when the computed rows equal the stored
         rows.
check    Compare the computed current members with Wikipedia's current component tables.
         Read-only. Exit 1 on any difference, so the weekly workflow fails loudly on drift.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable, Sequence

from seer_engine import db, demo, http, membership
from seer_engine.membership import Interval

HELP = "Point-in-time S&P 500 / Nasdaq-100 membership: refresh the universe table, check drift"

SINCE = date(2015, 1, 1)
WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"

Fetch = Callable[[str], str]


@dataclass(frozen=True)
class RefreshResult:
    changed: bool
    rows: int


def add_arguments(p: argparse.ArgumentParser) -> None:
    sub = p.add_subparsers(dest="action", required=True, metavar="{refresh,check}")
    refresh = sub.add_parser("refresh", help="rebuild the universe table from engine/data")
    check = sub.add_parser(
        "check", help="compare current members with Wikipedia; exit 1 on any difference"
    )
    for action in (refresh, check):
        action.add_argument(
            "--data-dir",
            type=Path,
            default=membership.DATA_DIR,
            help="membership data directory (default: engine/data)",
        )
        # Accept the global flags after the action too (`universe refresh --dry-run`).
        # SUPPRESS keeps an absent flag from resetting the value parsed earlier.
        action.add_argument("--dry-run", action="store_true", default=argparse.SUPPRESS)
        action.add_argument("-v", "--verbose", action="count", default=argparse.SUPPRESS)


def run(args: argparse.Namespace) -> int:
    intervals = membership.compute_universe(args.data_dir)
    if args.action == "refresh":
        return _run_refresh(intervals, args.dry_run)
    if args.action == "check":
        return check(intervals, fetch_wikitext)
    raise ValueError(f"unknown universe action {args.action!r}")


def _run_refresh(intervals: Sequence[Interval], dry_run: bool) -> int:
    conn = db.connect()
    try:
        demo.purge_demo_if_needed(conn, dry_run)
        result = refresh(conn, intervals, dry_run)
    finally:
        conn.close()
    print_summary(intervals)
    if not result.changed:
        print("universe: unchanged, nothing written")
    elif dry_run:
        print(f"universe: would replace table with {result.rows} rows (dry run, rolled back)")
    else:
        print(f"universe: replaced table with {result.rows} rows")
    return 0


def refresh(conn, intervals: Sequence[Interval], dry_run: bool) -> RefreshResult:
    """Replace the ``universe`` table with ``intervals`` unless it already holds exactly them."""
    with db.transaction(conn, dry_run):
        if membership.stored_intervals(conn) == set(intervals):
            return RefreshResult(changed=False, rows=len(intervals))
        rows = membership.replace_universe(conn, intervals)
    return RefreshResult(changed=True, rows=rows)


def print_summary(intervals: Sequence[Interval]) -> None:
    sp = membership.current_members(intervals, "SP500")
    ndx = membership.current_members(intervals, "NDX")
    print(
        f"universe: {len(intervals)} intervals, "
        f"{len({iv.symbol for iv in intervals})} distinct symbols, "
        f"{len(membership.symbols_since(intervals, SINCE))} since {SINCE.isoformat()}"
    )
    print(f"universe: current SP500={len(sp)} NDX={len(ndx)} union={len(sp | ndx)}")


def fetch_wikitext(page: str) -> str:
    """Raw wikitext of a Wikipedia page via the MediaWiki parse API."""
    body = http.get_json(
        WIKIPEDIA_API,
        {
            "action": "parse",
            "page": page,
            "prop": "wikitext",
            "format": "json",
            "formatversion": "2",
            "redirects": "1",
        },
    )
    if "error" in body:
        raise RuntimeError(f"Wikipedia API error for {page!r}: {body['error']}")
    return body["parse"]["wikitext"]


def check(intervals: Sequence[Interval], fetch: Fetch, out=None) -> int:
    """Print the difference between computed and Wikipedia current members; 1 if any."""
    out = out or sys.stdout
    computed: dict[str, frozenset[str]] = {
        index_id: membership.current_members(intervals, index_id)
        for index_id in membership.INDEX_IDS
    }
    reference: dict[str, frozenset[str]] = {
        index_id: membership.parse_constituents(fetch(page))
        for index_id, page in membership.WIKIPEDIA_PAGES.items()
    }
    diffs = membership.diff_members(computed, reference)
    for index_id in membership.INDEX_IDS:
        line = (
            f"{index_id}: computed {len(computed[index_id])}, "
            f"Wikipedia {len(reference[index_id])}"
        )
        if index_id not in diffs:
            print(f"{line} -- identical", file=out)
            continue
        missing, extra = diffs[index_id]
        print(f"{line} -- DIFFERENT", file=out)
        if missing:
            print(f"  on Wikipedia, not computed: {' '.join(missing)}", file=out)
        if extra:
            print(f"  computed, not on Wikipedia: {' '.join(extra)}", file=out)
    if diffs:
        print(
            "universe check: drift -- add dated rows to engine/data/membership_overrides.csv "
            "(or ticker_aliases.csv for a rename), then run `universe refresh`",
            file=out,
        )
        return 1
    return 0

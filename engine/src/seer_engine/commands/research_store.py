"""research_store — build (or verify) the local P7a research store (handover D5).

Downloads split-adjusted daily bars and cash dividends from yfinance for the L9 ETF set and
every S&P 500 / Nasdaq-100 member since 1996, and USD/IDR from Frankfurter, all through
``research.DEV_END`` (2015-10-16), into ``engine/.research/`` (gitignored). Then it loads the
store back, runs the three verifications (SPY on every NYSE session; SPY dividends equal the
vendored file on the overlap; AAPL 2012 dividend scale) and prints counts, the fingerprint and
the unserved members per year.

Never touches Neon and needs no DATABASE_URL.

    python -m seer_engine research_store [--store DIR] [--batch-size N] [--verify]

``--verify`` loads an existing store only (no network). The global ``--dry-run`` builds into a
temporary directory and discards it. Exit codes: 0 ok; 1 build failed or a check failed;
2 the store is missing or invalid.
"""

from __future__ import annotations

import argparse
import logging
import tempfile
from collections.abc import Sequence
from pathlib import Path

from seer_engine import research
from seer_engine.backtest import io as bt_io

log = logging.getLogger(__name__)

HELP = (
    "Build the local P7a research store (yfinance bars + dividends, Frankfurter USD/IDR) "
    "through 2015-10-16; never Neon."
)


def _positive_int(text: str) -> int:
    try:
        value = int(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"not an integer: {text!r}") from exc
    if value < 1:
        raise argparse.ArgumentTypeError("must be >= 1")
    return value


def add_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--store",
        type=Path,
        default=research.STORE_DIR,
        help=f"store directory (default {research.STORE_DIR})",
    )
    p.add_argument(
        "--batch-size",
        type=_positive_int,
        default=research.DEFAULT_BATCH_SIZE,
        help=f"symbols per yfinance call (default {research.DEFAULT_BATCH_SIZE})",
    )
    p.add_argument(
        "--verify",
        action="store_true",
        help="load and check an existing store only (no network)",
    )


def run(args: argparse.Namespace) -> int:
    store = Path(args.store)
    if args.verify:
        return _verify(store, note="")
    if getattr(args, "dry_run", False):
        with tempfile.TemporaryDirectory(prefix="seer-research-") as tmp:
            target = Path(tmp) / "store"
            code = _build(target, int(args.batch_size))
            if code != 0:
                return code
            return _verify(target, note=" (dry run: built in a temporary directory and discarded)")
    code = _build(store, int(args.batch_size))
    if code != 0:
        return code
    return _verify(store, note="")


def _build(store: Path, batch_size: int) -> int:
    try:
        research.build_store(store, batch_size=batch_size)
    except research.ResearchStoreError as exc:
        log.error("research_store: build failed, nothing written: %s", exc)
        return 1
    return 0


def _verify(store: Path, *, note: str) -> int:
    try:
        data = research.load_store(store)
    except ValueError as exc:
        log.error("research_store: %s", exc)
        return 2
    checks = research.run_checks(data, bt_io.read_dividends())
    print(format_summary(store, data, checks, note=note))
    return 0 if all(c.ok for c in checks) else 1


def format_summary(
    store: Path,
    data: research.ResearchData,
    checks: Sequence[research.Check],
    *,
    note: str = "",
) -> str:
    m = data.manifest
    lines = [
        f"research store {store}{note}",
        f"  dev_end: {m['dev_end']}  store_start: {m['store_start']}",
        f"  fingerprint: {data.fingerprint}",
        f"  symbols: {m['symbols_served']} served of {m['symbols_requested']} requested, "
        f"{len(data.unserved)} unserved",
        f"  rows: {m['bar_rows']:,} bars, {m['dividend_rows']:,} dividends, {m['fx_rows']:,} fx",
        "  unserved members by year (unserved of members):",
    ]
    for year, members, unserved in research.unserved_by_year(data.market.membership, data.unserved):
        lines.append(f"    {year}: {unserved} of {members}")
    for check in checks:
        lines.append(f"  check {check.name}: {'ok' if check.ok else 'FAIL'}: {check.detail}")
    return "\n".join(lines)

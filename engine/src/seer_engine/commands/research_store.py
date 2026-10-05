"""research_store — build (or verify) the local P7a research store (handover D5).

Downloads split-adjusted daily bars and cash dividends from yfinance for the L9 ETF set and
every S&P 500 / Nasdaq-100 member since 1996, and USD/IDR from Frankfurter, all through
``research.DEV_END`` (2015-10-16), into ``engine/.research/`` (gitignored). Then it loads the
store back, runs the three verifications (SPY on every NYSE session; SPY dividends equal the
vendored file on the overlap; AAPL 2012 dividend scale) and prints counts, the fingerprint and
the unserved members per year.

Never touches Neon and needs no DATABASE_URL.

    python -m seer_engine research_store [--store DIR] [--batch-size N] [--verify]
                                        [--coverage] [--with-fundamentals]

``--verify`` loads an existing store only (no network). ``--coverage`` also loads an existing
store only and measures what its fundamental panel can rank across the dev window
(``fundamentals.coverage``): a per-year table and one fraction, printed whatever the number is.
It needs no network and no database, and it wins when both it and ``--verify`` are given. It
exits 0 when the fraction is at or above ``coverage.MIN_DEV_COVERAGE`` and 1 when it is below --
the same convention ``--verify`` uses for a failed check. ``--with-fundamentals`` additionally
reads the SEC point-in-time fact panel from the database (``DATABASE_URL_UNPOOLED``, the one
place in this command that needs it) and writes it as the store's optional fifth file, so
``lab run`` sees a non-empty ``Market.fundamentals``; without the flag the store carries no
fundamentals and the lab ranks on bars alone, silently. The global ``--dry-run`` builds into a
temporary directory and discards it. Exit codes: 0 ok; 1 build failed, a check failed or
coverage is below the floor; 2 the store is missing or invalid.
"""

from __future__ import annotations

import argparse
import logging
import tempfile
from collections.abc import Sequence
from pathlib import Path

from seer_engine import research
from seer_engine.backtest import io as bt_io
from seer_engine.fundamentals import Fact, coverage

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
    p.add_argument(
        "--coverage",
        action="store_true",
        help=(
            "load an existing store and measure what its fundamental panel can rank over the "
            "dev window (no network, no database); exit 1 when it is below the lab's floor"
        ),
    )
    p.add_argument(
        "--with-fundamentals",
        action="store_true",
        help=(
            "also write fundamentals.csv from fundamental_facts (needs DATABASE_URL_UNPOOLED); "
            "without it the store carries no panel and the lab ranks on bars alone"
        ),
    )


def run(args: argparse.Namespace) -> int:
    store = Path(args.store)
    if getattr(args, "coverage", False):
        return _coverage(store)
    if args.verify:
        return _verify(store, note="")
    facts = _read_facts() if getattr(args, "with_fundamentals", False) else None
    if getattr(args, "dry_run", False):
        with tempfile.TemporaryDirectory(prefix="seer-research-") as tmp:
            target = Path(tmp) / "store"
            code = _build(target, int(args.batch_size), facts)
            if code != 0:
                return code
            return _verify(target, note=" (dry run: built in a temporary directory and discarded)")
    code = _build(store, int(args.batch_size), facts)
    if code != 0:
        return code
    return _verify(store, note="")


def _read_facts() -> tuple[Fact, ...]:
    """The SEC panel, as plain values, from ``bt_io`` -- which owns the connection.

    Neither this module nor ``research.py`` may name ``seer_engine.db`` or ``psycopg``:
    ``test_research_store.py::test_no_neon_and_no_database_url_needed`` AST-scans both and
    fails on either name. ``bt_io.read_facts`` is the backtest's declared impure edge and runs
    the same read ``bt_io.load_panel`` does, so the store's panel equals the database's.
    """
    return bt_io.read_facts()


def _build(store: Path, batch_size: int, facts: Sequence[Fact] | None) -> int:
    try:
        research.build_store(store, batch_size=batch_size, facts=facts)
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


def _coverage(store: Path) -> int:
    """``--coverage``: load the store and measure what its panel can rank. No network, no database.

    Deliberately does **not** run ``research.run_checks``: this mode answers one question and
    answers it cheaply. It is the replacement for the copy-paste snippet in
    ``docs/runbooks/data-pipeline.md``, and the reason M0005's successor cannot be run blind.

    Exit 0 when the measured fraction is at or above ``coverage.MIN_DEV_COVERAGE``, 1 when it is
    below (``--verify``'s convention for a failed check), 2 when the store will not load. The
    number is printed either way: this command reports, it never hides.
    """
    try:
        data = research.load_store(store)
    except ValueError as exc:
        log.error("research_store: %s", exc)
        return 2
    cov = coverage.measure(data.market.fundamentals)
    print(f"research store {store}")
    print(f"  fingerprint: {data.fingerprint}")
    print(coverage.format_report(cov))
    return 0 if cov.fraction >= coverage.MIN_DEV_COVERAGE else 1


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

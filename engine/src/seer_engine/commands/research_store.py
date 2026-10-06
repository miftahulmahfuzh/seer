"""research_store — build (or verify) the local research store (handover D5).

Downloads split-adjusted daily bars and cash dividends from yfinance for the L9 ETF set and
every S&P 500 / Nasdaq-100 member since 1996, and USD/IDR from Frankfurter, into a gitignored
store directory. Then it loads the store back, runs the three verifications (SPY on every NYSE
session; SPY dividends equal the vendored file on the overlap; AAPL 2012 dividend scale) and
prints counts, the window, the fingerprint and the unserved members per year.

Never touches Neon and needs no DATABASE_URL.

    python -m seer_engine research_store [--store DIR] [--batch-size N] [--verify]
                                        [--coverage] [--with-fundamentals]
                                        [--refresh-fundamentals]
                                        [--test-window [--window-end YYYY-MM-DD]]

Two windows, two stores:

- the **dev window** (1993-01-29..2015-10-16) in ``engine/.research`` -- the default, what
  ``lab run`` and ``backtest_dev`` read, and the store whose fingerprint every recorded lab
  trial was measured against;
- the **test window** (2015-10-19..data end) in ``engine/.research-test``, behind
  ``--test-window`` -- built the first time something is promoted and never before (design S3),
  read only by ``lab test``.

``--test-window`` builds through the latest completed NYSE session and records that date in the
manifest (``window_start`` / ``window_end``); ``--window-end`` pins it instead, so an
interrupted build can be resumed to the same end rather than silently moving. The two stores
are **not** interchangeable: ``research.load_store`` refuses a store whose declared window is
not the one the caller asked for, this command refuses to build one window into the other's
directory, and ``--verify`` / ``--refresh-fundamentals`` refuse a store whose declared window
disagrees with ``--test-window``.

``--verify`` loads an existing store only (no network). ``--coverage`` also loads an existing
store only and measures what its fundamental panel can rank across the dev window
(``fundamentals.coverage``): a per-year table and one fraction, printed whatever the number is.
It needs no network and no database, and it wins when both it and ``--verify`` are given. It
exits 0 when the fraction is at or above ``coverage.MIN_DEV_COVERAGE`` and 1 when it is below --
the same convention ``--verify`` uses for a failed check. It is a dev-window measure and is
refused with ``--test-window``. ``--with-fundamentals`` additionally reads the SEC
point-in-time fact panel from the database (``DATABASE_URL_UNPOOLED``, the one place in this
command that needs it) and writes it as the store's optional fifth file, so ``lab run`` sees a
non-empty ``Market.fundamentals``; without the flag the store carries no fundamentals and the
lab ranks on bars alone, silently. The global ``--dry-run`` builds into a temporary directory
and discards it. Exit codes: 0 ok; 1 build failed, a check failed or coverage is below the
floor; 2 the store is missing or invalid, or the flags refuse.

``--refresh-fundamentals`` rewrites **only** ``fundamentals.csv`` in an existing store and
needs no network: ``bars.csv``, ``dividends.csv``, ``fx.csv`` and ``unserved.csv`` are carried
over byte for byte, so the price history every recorded lab trial was run against survives
untouched while the panel moves. It reads the facts the same way ``--with-fundamentals`` does
(``DATABASE_URL_UNPOOLED`` -- point ``SEER_ENV_FILE`` at the train env file, and give it an
ABSOLUTE path: a relative one is resolved against the cwd and falling through to the ambient
environment means Neon) and refuses with exit 2 if the store is missing or fails verification.
The store's fingerprint changes -- a new ``fundamentals.csv`` is new content -- but not one bar
does, and the window it declares does not move. Under ``--dry-run`` it refreshes a copy in a
temporary directory and discards it. Not combinable with ``--verify`` or ``--coverage``.
"""

from __future__ import annotations

import argparse
import logging
import shutil
import tempfile
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from seer_engine import dates, research
from seer_engine.backtest import io as bt_io
from seer_engine.fundamentals import Fact, coverage

log = logging.getLogger(__name__)

HELP = (
    "Build the local research store (yfinance bars + dividends, Frankfurter USD/IDR): the dev "
    "window by default, the test window with --test-window; never Neon."
)


def _positive_int(text: str) -> int:
    try:
        value = int(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"not an integer: {text!r}") from exc
    if value < 1:
        raise argparse.ArgumentTypeError("must be >= 1")
    return value


def _session_date(text: str) -> date:
    try:
        value = date.fromisoformat(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"not an ISO date (YYYY-MM-DD): {text!r}") from exc
    if not dates.is_session(value):
        raise argparse.ArgumentTypeError(f"{text} is not an NYSE session")
    return value


def add_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--store",
        type=Path,
        default=None,
        help=(
            f"store directory (default {research.STORE_DIR} without --test-window, "
            f"{research.TEST_STORE_DIR} with it)"
        ),
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
    p.add_argument(
        "--refresh-fundamentals",
        action="store_true",
        help=(
            "rewrite only fundamentals.csv in an existing store, keeping every bar byte for "
            "byte (needs DATABASE_URL_UNPOOLED); the fingerprint changes, the price history "
            "does not; not combinable with --verify"
        ),
    )
    p.add_argument(
        "--test-window",
        action="store_true",
        help=(
            f"act on the P7b test store ({research.TEST_STORE_DIR}): the window "
            f"{research.TEST_WINDOW_START.isoformat()}..data end, not the dev window. Build it "
            "only when something is being promoted (design S3)"
        ),
    )
    p.add_argument(
        "--window-end",
        type=_session_date,
        default=None,
        help=(
            "end the test window on this NYSE session instead of the latest completed one; "
            "only with --test-window, and only for a build (use it to resume an interrupted "
            "build to the same end)"
        ),
    )


def _same_dir(a: Path, b: Path) -> bool:
    try:
        return a.resolve() == b.resolve()
    except OSError:  # pragma: no cover - an unresolvable path is simply not the same one
        return a == b


def run(args: argparse.Namespace) -> int:
    test = bool(getattr(args, "test_window", False))
    refresh = bool(getattr(args, "refresh_fundamentals", False))
    coverage_mode = bool(getattr(args, "coverage", False))
    read_only = coverage_mode or bool(args.verify)
    window_end = getattr(args, "window_end", None)

    if refresh and read_only:
        log.error(
            "research_store: --refresh-fundamentals cannot be combined with --verify or "
            "--coverage; those two only read a store, --refresh-fundamentals rewrites its "
            "fundamentals.csv"
        )
        return 2
    if coverage_mode and test:
        log.error(
            "research_store: --coverage measures the fundamental panel over the DEV window "
            "(fundamentals.coverage.WINDOW_END) and has no meaning for a test store; run it "
            "against %s",
            research.STORE_DIR,
        )
        return 2
    if window_end is not None and not test:
        log.error(
            "research_store: --window-end applies only to --test-window; the dev window ends "
            "at %s and never moves (D9)",
            research.DEV_END.isoformat(),
        )
        return 2
    if window_end is not None and (read_only or refresh):
        log.error(
            "research_store: --window-end sets the window a BUILD writes; --verify, --coverage "
            "and --refresh-fundamentals read the window the store already declares"
        )
        return 2

    store = (
        Path(args.store)
        if args.store is not None
        else (research.TEST_STORE_DIR if test else research.STORE_DIR)
    )
    # The dev store's fingerprint is the identity the sync-research-store skill keys on and
    # every recorded lab trial was measured against. Writing the test window into it would be
    # unrecoverable, so refuse it even when the operator names the directory explicitly.
    if test and _same_dir(store, research.STORE_DIR):
        log.error(
            "research_store: refusing to act on the dev store %s with --test-window; the test "
            "store is %s",
            research.STORE_DIR,
            research.TEST_STORE_DIR,
        )
        return 2
    if not test and _same_dir(store, research.TEST_STORE_DIR):
        log.error(
            "research_store: %s is the test store; pass --test-window to act on it",
            research.TEST_STORE_DIR,
        )
        return 2

    if coverage_mode:
        return _coverage(store)
    if args.verify:
        return _verify(store, note="", test=test)
    if refresh:
        return _run_refresh(store, bool(getattr(args, "dry_run", False)), test)

    window = research.DEV_WINDOW
    if test:
        try:
            window = research.test_window(
                window_end if window_end is not None else research.latest_session()
            )
        except (TypeError, ValueError) as exc:
            log.error("research_store: %s", exc)
            return 2
        log.info(
            "research_store: building the test window %s..%s into %s",
            window.start.isoformat(),
            window.end.isoformat(),
            store,
        )

    facts = _read_facts() if getattr(args, "with_fundamentals", False) else None
    if getattr(args, "dry_run", False):
        with tempfile.TemporaryDirectory(prefix="seer-research-") as tmp:
            target = Path(tmp) / "store"
            code = _build(target, int(args.batch_size), facts, window)
            if code != 0:
                return code
            return _verify(
                target, note=" (dry run: built in a temporary directory and discarded)", test=test
            )
    code = _build(store, int(args.batch_size), facts, window)
    if code != 0:
        return code
    return _verify(store, note="", test=test)


def _read_facts() -> tuple[Fact, ...]:
    """The SEC panel, as plain values, from ``bt_io`` -- which owns the connection.

    Neither this module nor ``research.py`` may name ``seer_engine.db`` or ``psycopg``:
    ``test_research_store.py::test_no_neon_and_no_database_url_needed`` AST-scans both and
    fails on either name. ``bt_io.read_facts`` is the backtest's declared impure edge and runs
    the same read ``bt_io.load_panel`` does, so the store's panel equals the database's.
    """
    return bt_io.read_facts()


def _build(
    store: Path, batch_size: int, facts: Sequence[Fact] | None, window: research.Window
) -> int:
    try:
        research.build_store(store, batch_size=batch_size, facts=facts, window=window)
    except research.ResearchStoreError as exc:
        log.error("research_store: build failed, nothing written: %s", exc)
        return 1
    return 0


def _store_window(store: Path, test: bool) -> tuple[research.Window | None, int]:
    """``(window, 0)`` when ``store``'s declared window matches ``test``; ``(None, 2)`` logged.

    The one place a read-only or refresh mode learns which window it is working with. It reads
    the manifest and nothing else; ``research.load_store`` still verifies the declaration
    against what it is handed, so this cannot become a way past that refusal.
    """
    try:
        window = research.declared_window(store)
    except ValueError as exc:
        log.error("research_store: %s", exc)
        return None, 2
    is_test = window != research.DEV_WINDOW
    if is_test != test:
        have = (
            f"the test window {window.start.isoformat()}..{window.end.isoformat()}"
            if is_test
            else "the dev window"
        )
        want = "a test store (--test-window)" if test else "a dev store"
        log.error(
            "research_store: %s declares %s, but this invocation is for %s; a dev store and a "
            "test store are not interchangeable",
            store,
            have,
            want,
        )
        return None, 2
    return window, 0


def _run_refresh(store: Path, dry_run: bool, test: bool) -> int:
    """``--refresh-fundamentals``: rewrite fundamentals.csv in place, keeping every bar.

    The facts are read **before** the store is opened, so a database failure refuses while the
    store is still untouched. A dry run copies the whole store into a temporary directory,
    refreshes the copy and discards it: the real store is never opened for writing, which is
    what ``--dry-run`` promises everywhere else in this CLI. The refreshed store keeps the
    window it declared.
    """
    if not store.is_dir():
        log.error(
            "research_store: %s is not a directory; --refresh-fundamentals needs an existing "
            "store to refresh",
            store,
        )
        return 2
    window, code = _store_window(store, test)
    if window is None:
        return code
    facts = _read_facts()
    if dry_run:
        with tempfile.TemporaryDirectory(prefix="seer-research-") as tmp:
            target = Path(tmp) / "store"
            shutil.copytree(store, target)
            code = _refresh(target, facts, window)
            if code != 0:
                return code
            return _verify(
                target,
                note=" (dry run: refreshed a copy in a temporary directory and discarded it)",
                test=test,
            )
    code = _refresh(store, facts, window)
    if code != 0:
        return code
    return _verify(store, note="", test=test)


def _refresh(store: Path, facts: Sequence[Fact], window: research.Window) -> int:
    try:
        research.refresh_fundamentals(store, facts, window=window)
    except research.ResearchStoreError as exc:
        log.error("research_store: refresh refused, nothing written: %s", exc)
        return 2
    return 0


def _verify(store: Path, *, note: str, test: bool = False) -> int:
    window, code = _store_window(store, test)
    if window is None:
        return code
    try:
        data = research.load_store(store, window=window)
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
    w = data.window
    # The window says what is SCORED; store_start says what is HELD. They differ on a test
    # store (data from 1993, scoring from 2015-10-19), and printing both stops anyone reading
    # the test store as if it began at its window start.
    scored_from = (
        "each candidate's first tradable session" if w.start == date.min else w.start.isoformat()
    )
    lines = [
        f"research store {store}{note}",
        f"  window: {w.name}, scored from {scored_from}, data through {w.end.isoformat()}",
        f"  dev_end: {m['dev_end']}  store_start: {m['store_start']}",
        f"  fingerprint: {data.fingerprint}",
        f"  symbols: {m['symbols_served']} served of {m['symbols_requested']} requested, "
        f"{len(data.unserved)} unserved",
        f"  rows: {m['bar_rows']:,} bars, {m['dividend_rows']:,} dividends, {m['fx_rows']:,} fx",
        "  unserved members by year (unserved of members):",
    ]
    for year, members, unserved in research.unserved_by_year(
        data.market.membership, data.unserved, window=data.window
    ):
        lines.append(f"    {year}: {unserved} of {members}")
    for check in checks:
        lines.append(f"  check {check.name}: {'ok' if check.ok else 'FAIL'}: {check.detail}")
    return "\n".join(lines)

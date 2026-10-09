"""The P7a research store: a local, gitignored dataset for the development window.

Handover D3, D4, D5, D9 and D11. Impure edge: yfinance (bars + cash dividends), Frankfurter
(USD/IDR) and local files. **Never Neon**: this module imports nothing from ``seer_engine.db``,
opens no database connection, and needs no ``DATABASE_URL``.

``build_store`` requests every :data:`RESEARCH_ETFS` symbol and every S&P 500 / Nasdaq-100
member whose membership interval overlaps ``[MEMBERSHIP_START, DEV_END]`` (from the vendored
CSVs via ``membership.compute_universe``). It downloads daily bars ``STORE_START..DEV_END``
with yfinance ``auto_adjust=False, actions=True`` (split-adjusted OHLC exactly like Neon's
``bars``; split-adjusted cash dividends), and USD/IDR ``FX_START..DEV_END`` from Frankfurter.
It writes plain sorted CSV files and ``manifest.json`` into ``<store>.tmp``, then swaps the
directory in: all or nothing.

Files (UTF-8, LF, sorted, deterministic; no timestamps anywhere):

- ``bars.csv``      ``symbol,date,open,high,low,close,volume``  (ORDER BY symbol, date; 4 dp)
- ``dividends.csv`` ``symbol,ex_date,amount``  (ORDER BY symbol, ex_date; at most 6 dp)
- ``fx.csv``        ``date,usd_idr``  (ascending; 4 dp)
- ``unserved.csv``  ``symbol,reason``  (requested members yfinance returned no bars for)
- ``manifest.json`` counts, per-file sha256 and the fingerprint (sha256 of the sorted
  ``name:sha256`` lines of the four data files); ``json.dumps(sort_keys=True, indent=2)``.

``load_store`` verifies every sha256 and the fingerprint, refuses any row dated after
``DEV_END`` (the data-level half of D9), and returns a :class:`ResearchData` whose ``Market``
is built exactly like ``backtest.io.load_market`` builds one from Neon
(``histories_from_frame`` + ``merge_intervals``).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from seer_engine import config, dates, fx, membership, yahoo
from seer_engine.backtest.benchmark import Dividend
from seer_engine.backtest.io import (
    BAR_COLUMNS,
    LoadError,
    facts_from_frame,
    histories_from_frame,
    merge_intervals,
)
from seer_engine.backtest.market import EMPTY_FUNDAMENTALS, DividendCalendar, Market, Membership
from seer_engine.backtest.window import WINDOW_NAMES, Window
from seer_engine.fundamentals import FACT_COLUMNS, Fact, FundamentalPanel as Panel
from seer_engine.prices import to_decimal

log = logging.getLogger(__name__)

DEV_END = date(2015, 10, 16)  # == backtest.dev.DEV_END (phase 9 tests the equality)
STORE_START = date(1993, 1, 29)  # SPY's first session
MEMBERSHIP_START = date(1996, 1, 2)  # first sp500_history.csv row (== backtest.dev.MEMBERSHIP_START)
FX_START = date(1999, 1, 4)  # first Frankfurter USD/IDR row (== backtest.dev.FX_START)
STORE_DIR = config.REPO_ROOT / "engine" / ".research"  # gitignored; the dev window
TEST_STORE_DIR = config.REPO_ROOT / "engine" / ".research-test"  # gitignored; the P7b test window
TEST_WINDOW_START = date(2015, 10, 19)  # the first NYSE session after DEV_END (design S3)
"""The first session the test window TRADES. Not where the test store's data starts.

Both stores hold bars from :data:`STORE_START` (1993-01-29): a candidate evaluated from
2015-10-19 still needs ``lookback`` bars before that date, and a test store opening at its own
window start would push a 12-1 momentum candidate's only look ~10 months late. A test-window
trial is append-only and there is exactly one look per configuration, so that error would be
permanent. The window's ``start`` bounds scoring; ``STORE_START`` bounds the files.
"""

DEV_WINDOW = Window(name="dev", start=date.min, end=DEV_END)
"""The window every helper here defaults to; ``== backtest.dev.DEV_WINDOW`` (a test pins it).

``start`` is ``date.min`` -- the dev window has no lower bound. The membership lower bound is
``MEMBERSHIP_START``, a property of the vendored CSVs rather than of the window, and the
helpers below apply it with ``max(window.start, MEMBERSHIP_START)``.
"""

RESEARCH_ETFS: tuple[str, ...] = (
    "BIL", "DIA", "EFA", "GLD", "IEF", "IWM", "QLD", "QQQ", "SHY", "SPY", "SSO",
    "TLT", "XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY",
)  # sorted; launch-limited by yfinance
SECTOR_ETFS: tuple[str, ...] = ("XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY")

BARS_FILE = "bars.csv"
DIVIDENDS_FILE = "dividends.csv"
FX_FILE = "fx.csv"
UNSERVED_FILE = "unserved.csv"
FUNDAMENTALS_FILE = "fundamentals.csv"
MANIFEST_FILE = "manifest.json"
DATA_FILES: tuple[str, ...] = (BARS_FILE, DIVIDENDS_FILE, FX_FILE, UNSERVED_FILE)

OPTIONAL_DATA_FILES: tuple[str, ...] = (FUNDAMENTALS_FILE,)
"""Store files a build MAY write. Deliberately separate from ``DATA_FILES``.

``fundamentals.csv`` is optional, never a fifth required file: ``_read_manifest`` requires the
four ``DATA_FILES`` names and ``load_store`` hashes the manifest's own keys, so a store built
before fundamentals existed keeps loading with a **bit-identical fingerprint** and every
recorded lab trial stays valid. Widening ``DATA_FILES`` instead would make every store on disk
raise ``ValueError`` before any reader ran.
"""

BARS_HEADER = "symbol,date,open,high,low,close,volume"
DIVIDENDS_HEADER = "symbol,ex_date,amount"
FX_HEADER = "date,usd_idr"
UNSERVED_HEADER = "symbol,reason"
FUNDAMENTALS_HEADER = ",".join(FACT_COLUMNS)


def unserved_reason(start: date = STORE_START, end: date = DEV_END) -> str:
    """What ``unserved.csv`` records for a requested member yfinance returned no bars for."""
    return f"yfinance returned no bars for {start.isoformat()}..{end.isoformat()}"


UNSERVED_REASON = unserved_reason()  # the dev store's: "...for 1993-01-29..2015-10-16"

_COUNT_KEYS: tuple[str, ...] = (
    "bar_rows",
    "dividend_rows",
    "fx_rows",
    "symbols_requested",
    "symbols_served",
)
MANIFEST_KEYS: frozenset[str] = frozenset({"dev_end", "store_start", "files", "fingerprint", *_COUNT_KEYS})
"""The keys every manifest carries, whatever window the store was built for.

``dev_end`` is a **code-version pin**, not the store's window: it records the ``DEV_END`` the
building code was compiled against, so a store built before ``DEV_END`` moved (it never has)
is refused. A test store carries the same ``"2015-10-16"``. The store's own window lives in
:data:`OPTIONAL_MANIFEST_KEYS`.
"""

WINDOW_NAME_KEY = "window_name"
WINDOW_START_KEY = "window_start"
WINDOW_END_KEY = "window_end"
OPTIONAL_MANIFEST_KEYS: frozenset[str] = frozenset(
    {WINDOW_NAME_KEY, WINDOW_START_KEY, WINDOW_END_KEY}
)
"""The window a non-dev store declares: a name and two ISO dates, all three or none.

They describe what the store is **scored** on, never what it holds: ``store_start`` is
``"1993-01-29"`` on a test store too.

**Absent means the dev window.** That is not a convenience, it is the only shape that keeps the
dev store on disk loadable: ``engine/.research`` was sealed with exactly ``MANIFEST_KEYS`` and
its fingerprint ``399d0d25...`` is the identity the ``sync-research-store`` skill keys on and
every recorded lab trial was measured against. Requiring a window key would reject it before
any reader ran -- exactly the precedent ``OPTIONAL_DATA_FILES`` already sets for a four-file
manifest from before fundamentals existed.

A dev build therefore writes none of them (see :func:`_seal`). The fingerprint is unaffected
either way: :func:`fingerprint_of` hashes the ``files`` map alone, never the manifest's other
keys.
"""

DEFAULT_BATCH_SIZE = 40
BATCH_PAUSE_S = 3.0
RATE_LIMIT_BACKOFF_S: tuple[float, ...] = (60.0, 120.0, 240.0)

# verification (the real build's three checks; see run_checks)
SPY_CHECK_START = date(1993, 2, 1)
SCALE_CHECK_SYMBOL = "AAPL"
SCALE_CHECK_YEAR = 2012
SCALE_MIN_YIELD = Decimal("0.001")  # a dividend below 0.1% of the prior close: price scale too big
SCALE_MAX_YIELD = Decimal("0.02")  # above 2% for one quarterly payment: dividend not split-adjusted

Sleep = Callable[[float], None]
FetchFx = Callable[[date, date], "Sequence[tuple[date, Decimal | float | int | str]]"]


class ResearchStoreError(RuntimeError):
    """The build could not finish; nothing was written and any previous store is intact."""


@dataclass(frozen=True)
class ResearchData:
    """A loaded, verified research store.

    ``price_fingerprint`` is ``price_fingerprint_of(manifest["files"])`` -- the fingerprint of the
    four price files, fundamentals excluded -- and ``load_store`` always sets it. It defaults to
    None only so a hand-built fixture need not invent one; a None reaches ``trial_provenance`` as
    NULL, which reads as "price data unknown", never as a match.
    """

    market: Market  # history from bars.csv, membership clipped to ``window``, fx from fx.csv
    dividends: dict[str, dict[date, Decimal]]  # symbol -> ex_date -> amount (ascending)
    spy_dividends: tuple[Dividend, ...]  # SPY's, as benchmark.Dividend, ascending
    fingerprint: str
    manifest: Mapping[str, Any]
    unserved: tuple[str, ...] = ()  # requested members with no bars, sorted
    window: Window = DEV_WINDOW  # the window this store declares; its ``end`` is the D9 bound
    price_fingerprint: str | None = None  # price_fingerprint_of(files): fundamentals excluded


@dataclass(frozen=True)
class Check:
    """One verification of a built store: a stable name, the verdict, and what was seen."""

    name: str
    ok: bool
    detail: str


# ---- windows -------------------------------------------------------------------------------


def _window(name: str, start: date, end: date) -> Window:
    """A research window.

    Built with ``dataclasses.replace`` from ``DEV_WINDOW`` rather than by calling ``Window``:
    this module then never names the backtest package's constructor, so a ``Window`` that grows
    a field stays buildable here without an edit.
    """
    if name not in WINDOW_NAMES:
        raise ValueError(f"window name must be one of {WINDOW_NAMES}, got {name!r}")
    return replace(DEV_WINDOW, name=name, start=start, end=end)


def _is_dev_window(window: Window) -> bool:
    return (window.name, window.start, window.end) == (
        DEV_WINDOW.name,
        DEV_WINDOW.start,
        DEV_WINDOW.end,
    )


def _window_label(window: Window) -> str:
    """``"dev window ending 2015-10-16"`` / ``"test window ending 2026-10-02"``.

    The end, not ``start..end``: ``DEV_WINDOW.start`` is ``date.min`` and printing it is noise.
    The name alone separates the two windows; the end separates two test stores built on
    different days.
    """
    return f"{window.name} window ending {window.end.isoformat()}"


def test_window(end: date) -> Window:
    """The P7b test window: :data:`TEST_WINDOW_START` (2015-10-19) through ``end``.

    ``end`` is the last session **scored**, and design S3 fixes it as "data end" -- the latest
    session available when the store is built (see :func:`latest_session`), recorded in the
    manifest. It is deliberately **not** a constant: a hardcoded end goes stale and would
    silently change what a recorded test trial meant. The store still holds bars from
    ``STORE_START``; see :data:`TEST_WINDOW_START`.

    Equivalent to ``DEV_WINDOW.following("test", end)`` and asserted equal to it in
    ``test_research_test_store.py``, so the two spellings cannot drift. Spelled out here
    because this module owns the validation and the ``TEST_WINDOW_START`` constant.

    ``ValueError`` when ``end`` is not after ``DEV_END`` (that is the dev window's territory,
    and a "test" store ending inside it would be a dev store wearing the wrong label) or is not
    an NYSE session (the window's end must be a session a bar can exist for).
    """
    if isinstance(end, datetime) or not isinstance(end, date):
        raise TypeError(f"end must be a date, got {type(end).__name__}")
    if end <= DEV_END:
        raise ValueError(
            f"the test window must end after DEV_END {DEV_END.isoformat()}, got {end.isoformat()}"
        )
    if not dates.is_session(end):
        raise ValueError(
            f"the test window must end on an NYSE session, and {end.isoformat()} is not one"
        )
    return _window("test", TEST_WINDOW_START, end)


def latest_session(now_utc: datetime | None = None) -> date:
    """The latest NYSE session whose close has settled -- "data end" at build time.

    Thin, injectable wrapper over ``dates.last_completed_session`` so a caller (and a test) can
    fix the clock. It is the default end of a ``--test-window`` build.
    """
    now = datetime.now(timezone.utc) if now_utc is None else now_utc
    return dates.last_completed_session(now)


# ---- symbols and membership ----------------------------------------------------------------


def _universe(data_dir: Path | None) -> list[membership.Interval]:
    return membership.compute_universe(data_dir if data_dir is not None else membership.DATA_DIR)


def _members_start(window: Window) -> date:
    """The window's membership lower bound: its own start, but never before the CSVs begin.

    ``DEV_WINDOW.start`` is ``date.min``, so for the dev window this is ``MEMBERSHIP_START``
    and every result below is exactly what it was before the window became a parameter.
    """
    return max(window.start, MEMBERSHIP_START)


def _overlaps_window(iv: membership.Interval, window: Window = DEV_WINDOW) -> bool:
    lo = _members_start(window)
    return iv.start_date <= window.end and (iv.end_date is None or iv.end_date > lo)


def requested_symbols(data_dir: Path | None = None, *, window: Window = DEV_WINDOW) -> tuple[str, ...]:
    """RESEARCH_ETFS ∪ every member whose interval overlaps the window, sorted.

    The overlap is ``[max(window.start, MEMBERSHIP_START), window.end]``, which is
    ``[MEMBERSHIP_START, DEV_END]`` for the dev window. The test window's members are a
    different set -- everything that joined after October 2015 is in it and everything that
    left before is not -- so a store must be built with its own window's universe.
    """
    members = {iv.symbol for iv in _universe(data_dir) if _overlaps_window(iv, window)}
    return tuple(sorted(set(RESEARCH_ETFS) | members))


def research_membership(data_dir: Path | None = None, *, window: Window = DEV_WINDOW) -> Membership:
    """Point-in-time membership for ``window``, from the vendored CSVs (no Neon).

    Only intervals overlapping the window are kept, and an end after ``window.end`` becomes
    None (the company is a member on every session of this window), so nothing dated after
    ``window.end`` is visible even through membership. An end *inside* the window is kept as
    it is -- that is what makes this correct for the test window, where a company that left
    the index in 2018 must stop being a member in 2018. Both indices are merged with
    ``io.merge_intervals``, exactly like ``io.read_intervals`` does for Neon's ``universe``.
    """
    rows: list[tuple[str, date, date | None]] = []
    for iv in _universe(data_dir):
        if not _overlaps_window(iv, window):
            continue
        end = iv.end_date if iv.end_date is not None and iv.end_date <= window.end else None
        rows.append((iv.symbol, iv.start_date, end))
    return Membership(intervals=merge_intervals(rows))


def unserved_by_year(
    members: Membership,
    unserved: Iterable[str],
    *,
    window: Window = DEV_WINDOW,
) -> tuple[tuple[int, int, int], ...]:
    """Per calendar year of the window: (year, distinct members that year, of which unserved).

    The years run ``max(window.start, MEMBERSHIP_START).year .. window.end.year`` -- 1996..2015
    for the dev window. A symbol counts in a year when one of its intervals overlaps that
    year's part of the window."""
    missing = set(unserved)
    lo_bound = _members_start(window)
    out: list[tuple[int, int, int]] = []
    for year in range(lo_bound.year, window.end.year + 1):
        lo = max(date(year, 1, 1), lo_bound)
        hi = min(date(year, 12, 31), window.end)
        seen = {
            symbol
            for symbol, start, end in members.intervals
            if start <= hi and (end is None or end > lo)
        }
        out.append((year, len(seen), len(seen & missing)))
    return tuple(out)


# ---- hashing -------------------------------------------------------------------------------


def file_sha256(path: Path) -> str:
    """sha256 hex of a file's bytes; ValueError when the file is missing."""
    digest = hashlib.sha256()
    try:
        with Path(path).open("rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                digest.update(chunk)
    except FileNotFoundError as exc:
        raise ValueError(f"{Path(path).name} is missing from the research store") from exc
    return digest.hexdigest()


def fingerprint_of(files: Mapping[str, str]) -> str:
    """sha256 of the sorted ``name:sha256`` lines (LF-terminated) of the store's data files."""
    text = "".join(f"{name}:{files[name]}\n" for name in sorted(files))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def price_fingerprint_of(files: Mapping[str, str]) -> str:
    """``fingerprint_of`` over the four price files alone (``DATA_FILES``): the store's identity
    as far as a backtest is concerned.

    **Why this exists, measured 2026-10-09 (trial-reproducibility analysis M1).** ``fingerprint_of``
    hashes the store's whole ``files`` map, so adding or refreshing ``fundamentals.csv`` moves it
    without moving a single bar. That is the correct identity for *the store* -- the
    ``sync-research-store`` skill keys on it, and a store whose panel changed is a different store
    -- and the wrong identity for *a price-only comparison*. The lab's 148 dev trials were recorded
    under three store fingerprints (``5451195f…`` 58 trials, ``e597367b…`` 6, ``399d0d25…`` 84),
    and this function over today's ``399d0d25…`` manifest returns exactly ``5451195f…``, the P7a
    store's fingerprint: the three carry byte-identical bars, dividends, FX and unserved rows, and
    differ only in the panel. Keying a comparability rule on ``store_fingerprint`` would refuse
    every promotion in the lab for a difference no price-only method can see; keying it on this
    strands nothing.

    For a four-file store (one built before fundamentals existed) the two fingerprints are the
    same hash, because the file map *is* ``DATA_FILES``. ``ValueError`` when ``files`` lacks one
    of the four -- which ``_read_manifest`` already refuses for any store that loads, so in
    practice only a hand-built map can reach it.
    """
    missing = [name for name in DATA_FILES if name not in files]
    if missing:
        raise ValueError(
            f"a price fingerprint covers all of {list(DATA_FILES)}; the file map lacks {missing}"
        )
    return fingerprint_of({name: files[name] for name in DATA_FILES})


# ---- fundamentals --------------------------------------------------------------------------


def fundamentals_lines(facts: Sequence[Fact]) -> list[str]:
    """``facts`` as ``FUNDAMENTALS_HEADER`` rows, sorted, in ``io.FACTS_COPY_SQL``'s encoding.

    The cells are exactly what that COPY emits, because ``_read_fundamentals`` parses them with
    ``io.facts_from_frame`` -- the one text -> ``Fact`` path in the tree. So: ISO dates, ``''``
    for ``period_start`` when the fact is instantaneous (``Fact.period_start is None``), and
    ``''`` for a null ``fy``/``fp``. ``val`` is written with ``repr``, which round-trips a
    float64 exactly under ``float_precision="round_trip"``.

    The sort is the COPY's ``ORDER BY``, so a store rebuilt from the same facts is byte-stable
    and its fingerprint is a function of the data alone. No cell can hold a comma: they are
    tickers, SEC tags, units, accession numbers, form types, ISO dates and float reprs.
    """
    rows = []
    for f in facts:
        if not isinstance(f, Fact):
            raise TypeError(f"facts must hold fundamentals.Fact, got {type(f).__name__}")
        rows.append(
            (
                f.symbol,
                f.taxonomy,
                f.tag,
                f.unit,
                f.period_start.isoformat() if f.period_start is not None else "",
                f.period_end.isoformat(),
                repr(float(f.val)),
                f.accn,
                f.form,
                "" if f.fy is None else str(f.fy),
                "" if f.fp is None else f.fp,
                f.filed.isoformat(),
            )
        )
    rows.sort(key=lambda r: (r[0], r[1], r[2], r[3], r[5], r[4], r[11], r[7]))
    return [",".join(r) for r in rows]


def _read_fundamentals(path: Path) -> Panel:
    """The store's fact panel, or EMPTY_FUNDAMENTALS when the store has no fundamentals.csv.

    The file is written from ``fundamentals_lines`` in ``io.FACTS_COPY_SQL``'s encoding, so its
    cells are exactly what that COPY emits: ISO dates, ``''`` for a NULL fy/fp, and ``''`` for
    ``period_start`` when the fact is instantaneous. ``io.facts_from_frame`` is the ONE function
    in the tree that turns that text back into ``Fact`` objects, and reusing it here is what
    makes the store-backed panel and the database-backed panel identical by construction rather
    than by inspection. Do NOT route this through ``fundamentals.fact_from_row``: that function
    takes typed values (date, Decimal) and would reject every string cell -- silently, because
    ``facts_from_rows`` skips what it cannot parse.
    """
    if not path.is_file():
        return EMPTY_FUNDAMENTALS
    frame = pd.read_csv(
        path,
        dtype={c: str for c in FACT_COLUMNS} | {"val": np.float64},
        na_filter=False,
        float_precision="round_trip",
    )
    if tuple(frame.columns) != FACT_COLUMNS:
        raise ValueError(f"{path.name}: header is {tuple(frame.columns)}, expected {FACT_COLUMNS}")
    return Panel.from_facts(facts_from_frame(frame))


# ---- build ---------------------------------------------------------------------------------


def build_store(
    store_dir: Path,
    *,
    downloader: yahoo.Downloader | None = None,
    fetch_fx: FetchFx | None = None,
    sleep: Sleep = time.sleep,
    batch_size: int = DEFAULT_BATCH_SIZE,
    data_dir: Path | None = None,
    facts: Sequence[Fact] | None = None,
    window: Window = DEV_WINDOW,
) -> dict[str, Any]:
    """Build the research store at ``store_dir``; return its manifest.

    ``downloader`` defaults to ``yahoo.yf_download_actions`` and ``fetch_fx`` to
    ``fx.fetch_range`` (both injectable for tests); ``data_dir`` is the membership CSV
    directory (default ``membership.DATA_DIR``). Raises ResearchStoreError when the build
    cannot finish (rate limited out, a download error, an unserved ETF, no or conflicting FX);
    then nothing is written and a previous store at ``store_dir`` is left untouched.

    ``window`` is the window the store is built for and declares; it defaults to ``DEV_WINDOW``,
    so every caller that predates it builds exactly the store it built before -- same symbols,
    same date range, same ``unserved.csv`` text, same nine manifest keys, same fingerprint.
    Pass ``test_window(latest_session())`` to build the P7b test store.

    **The data range follows ``window.end`` alone.** It is always ``STORE_START..window.end``
    for bars and ``FX_START..window.end`` for FX, on either window. A test store therefore
    carries the *same* deep history as the dev store plus everything after it -- a candidate
    evaluated from 2015-10-19 still needs ``lookback`` bars before that date, and the test
    window grants exactly one look per configuration, so a store that started at its own window
    start would make that one look permanently wrong.

    **The universe follows the window at both ends.** ``requested_symbols(data_dir,
    window=window)`` is every member whose interval overlaps
    ``[max(window.start, MEMBERSHIP_START), window.end]`` -- ``[MEMBERSHIP_START, DEV_END]`` on
    the dev window, unchanged, and ``[2015-10-19, window.end]`` on the test window. Every
    company that joined the index after October 2015 is in; every company that left it before
    2015-10-19 is out, because no test-window session ever ranks, holds or exits one, so its
    bars would be rows nothing reads. ``members_on(t)`` for every ``t`` in the test window is
    the same set either way; only the size of the crawl differs. A membership interval that
    closes in 2018 also stays closed instead of being read as open.

    ``facts`` is the SEC point-in-time panel, as a plain sequence of ``fundamentals.Fact`` --
    never a database connection, because this module imports nothing from ``seer_engine.db``
    (see the module docstring's "Never Neon"). ``commands/research_store.py`` reads them behind
    ``--with-fundamentals`` and passes them in. ``None`` -- the default, and every caller that
    predates fundamentals -- writes no ``fundamentals.csv`` at all, so the store is
    byte-identical to the one this function built before the field existed. Facts are **not**
    filtered by ``window``: ``FundamentalPanel`` selects point-in-time on ``filed <= t`` at read
    time, so a later filing in the file is invisible on an earlier session, and filtering here
    would rewrite ``fundamentals.csv`` and move the dev store's fingerprint for no gain.
    """
    if isinstance(batch_size, bool) or not isinstance(batch_size, int) or batch_size < 1:
        raise ValueError(f"batch_size must be an int >= 1, got {batch_size!r}")
    if window.end < STORE_START:
        raise ValueError(
            f"the window ends {window.end.isoformat()}, before STORE_START {STORE_START.isoformat()}; "
            "there is nothing to build"
        )
    store_dir = Path(store_dir)
    fetch = downloader if downloader is not None else yahoo.yf_download_actions
    fetch_rates = fetch_fx if fetch_fx is not None else fx.fetch_range
    symbols = requested_symbols(data_dir, window=window)

    store_dir.parent.mkdir(parents=True, exist_ok=True)
    tmp = store_dir.with_name(store_dir.name + ".tmp")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir()
    try:
        fx_rows = _fetch_fx_rows(fetch_rates, window.end)
        _write_text(tmp / FX_FILE, FX_HEADER, [f"{d.isoformat()},{v}" for d, v in fx_rows])
        served, unserved, bar_rows, dividend_lines = _write_bars(
            tmp, symbols, fetch, sleep, batch_size, window.end
        )
        lost_etfs = [s for s in RESEARCH_ETFS if s in set(unserved)]
        if lost_etfs:
            raise ResearchStoreError(
                f"yfinance served no bars for ETF(s) {', '.join(lost_etfs)}; every family needs them"
            )
        _write_text(tmp / DIVIDENDS_FILE, DIVIDENDS_HEADER, dividend_lines)
        # STORE_START, not window.start: this names the range the DOWNLOAD covered, and both
        # windows download from 1993. unserved_reason(STORE_START, DEV_END) is byte-identical
        # to UNSERVED_REASON, so the dev store's unserved.csv -- and therefore its fingerprint
        # -- does not move.
        reason = unserved_reason(STORE_START, window.end)
        _write_text(tmp / UNSERVED_FILE, UNSERVED_HEADER, [f"{s},{reason}" for s in unserved])
        extra_files: tuple[str, ...] = ()
        if facts is not None:
            _write_text(tmp / FUNDAMENTALS_FILE, FUNDAMENTALS_HEADER, fundamentals_lines(facts))
            extra_files = (FUNDAMENTALS_FILE,)
        counts = {
            "bar_rows": bar_rows,
            "dividend_rows": len(dividend_lines),
            "fx_rows": len(fx_rows),
            "symbols_requested": len(symbols),
            "symbols_served": len(served),
        }
        manifest = _seal(tmp, counts, extra_files=extra_files, window=window)
        _swap_in(tmp, store_dir)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    log.info(
        "research: store %s built for the %s: %d of %d symbols served, %d bar rows, %d dividends, "
        "%d fx rows, fingerprint %s",
        store_dir,
        _window_label(window),
        counts["symbols_served"],
        counts["symbols_requested"],
        counts["bar_rows"],
        counts["dividend_rows"],
        counts["fx_rows"],
        manifest["fingerprint"],
    )
    return manifest


def _fetch_fx_rows(fetch_rates: FetchFx, end: date) -> list[tuple[date, Decimal]]:
    try:
        raw = list(fetch_rates(FX_START, end))
    except Exception as exc:  # noqa: BLE001 - any FX failure aborts the build
        raise ResearchStoreError(f"USD/IDR fetch failed: {exc!r}") from exc
    items: dict[date, Decimal] = {}
    for d, rate in raw:
        if not FX_START <= d <= end:
            continue
        value = to_decimal(rate)
        if value <= 0:
            raise ResearchStoreError(f"USD/IDR on {d.isoformat()} is not positive: {value}")
        if d in items and items[d] != value:
            raise ResearchStoreError(f"conflicting USD/IDR rates for {d.isoformat()}")
        items[d] = value
    if not items:
        raise ResearchStoreError(f"Frankfurter returned no USD/IDR rows for {FX_START}..{end}")
    log.info("research: %d USD/IDR rows %s..%s", len(items), min(items), max(items))
    return sorted(items.items())


def _write_bars(
    tmp: Path,
    symbols: Sequence[str],
    fetch: yahoo.Downloader,
    sleep: Sleep,
    batch_size: int,
    end: date,
) -> tuple[list[str], list[str], int, list[str]]:
    """Stream bars.csv batch by batch; return (served, unserved, bar rows, dividend lines)."""
    served: list[str] = []
    unserved: list[str] = []
    dividend_lines: list[str] = []
    bar_rows = 0
    batches = [list(symbols[i : i + batch_size]) for i in range(0, len(symbols), batch_size)]
    log.info(
        "research: %d symbols in %d batches, %s..%s",
        len(symbols),
        len(batches),
        STORE_START,
        end,
    )
    with (tmp / BARS_FILE).open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(BARS_HEADER + "\n")
        for number, batch in enumerate(batches, start=1):
            if number > 1:
                sleep(BATCH_PAUSE_S)
            got = _fetch_batch(batch, fetch, sleep, end)
            batch_rows = 0
            for symbol in batch:
                history = got[symbol]
                if not history.bars:
                    unserved.append(symbol)
                    continue
                served.append(symbol)
                for b in history.bars:
                    fh.write(
                        f"{b.symbol},{b.date.isoformat()},{b.open},{b.high},{b.low},{b.close},{b.volume}\n"
                    )
                batch_rows += len(history.bars)
                dividend_lines.extend(
                    f"{symbol},{d.isoformat()},{_amount_text(a)}" for d, a in history.dividends
                )
            bar_rows += batch_rows
            log.info(
                "research: batch %d/%d: %d served, %d unserved, %d bar rows",
                number,
                len(batches),
                sum(1 for s in batch if got[s].bars),
                sum(1 for s in batch if not got[s].bars),
                batch_rows,
            )
    return served, unserved, bar_rows, dividend_lines


def _fetch_batch(
    batch: Sequence[str], fetch: yahoo.Downloader, sleep: Sleep, end: date
) -> dict[str, yahoo.TickerHistory]:
    """One batch, clipped to [STORE_START, end]; empties get one individual retry."""
    got = _download_with_backoff(batch, fetch, sleep, end)
    out = {s: _in_window(got.get(s, yahoo.EMPTY_HISTORY), end) for s in batch}
    if len(batch) > 1:  # a one-symbol batch already was the individual attempt
        for symbol in batch:
            if out[symbol].bars:
                continue
            sleep(BATCH_PAUSE_S)
            again = _download_with_backoff([symbol], fetch, sleep, end)
            out[symbol] = _in_window(again.get(symbol, yahoo.EMPTY_HISTORY), end)
    return out


def _download_with_backoff(
    symbols: Sequence[str], fetch: yahoo.Downloader, sleep: Sleep, end: date
) -> dict[str, yahoo.TickerHistory]:
    end_exclusive = end + timedelta(days=1)
    waits: tuple[float | None, ...] = (*RATE_LIMIT_BACKOFF_S, None)
    for wait in waits:
        try:
            return yahoo.download_actions(symbols, STORE_START, end_exclusive, downloader=fetch)
        except yahoo.RateLimited as exc:
            if wait is None:
                raise ResearchStoreError(
                    f"yfinance rate limited after {len(RATE_LIMIT_BACKOFF_S)} retries: {exc}"
                ) from exc
            log.warning("research: rate limited; sleeping %.0f s", wait)
            sleep(wait)
        except Exception as exc:  # noqa: BLE001 - a download error aborts the build (no partial store)
            raise ResearchStoreError(
                f"yfinance download of {len(symbols)} symbol(s) failed: {exc!r}"
            ) from exc
    raise AssertionError("unreachable")  # pragma: no cover


def _in_window(history: yahoo.TickerHistory, end: date) -> yahoo.TickerHistory:
    """Drop anything outside [STORE_START, end] (defensive: the request already ends at ``end``
    + 1 day, but no row outside the store's declared window may ever reach it)."""
    return yahoo.TickerHistory(
        bars=tuple(b for b in history.bars if STORE_START <= b.date <= end),
        dividends=tuple((d, a) for d, a in history.dividends if STORE_START <= d <= end),
    )


def _amount_text(amount: Decimal) -> str:
    """At most 6 decimals, no exponent, no trailing zeros: 0.25, 0.094643, 10."""
    q = amount.quantize(yahoo.DIVIDEND_QUANTUM, rounding=ROUND_HALF_UP).normalize()
    return format(q, "f")


def _write_text(path: Path, header: str, lines: Sequence[str]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(header + "\n")
        for line in lines:
            fh.write(line + "\n")


def _seal(
    tmp: Path,
    counts: Mapping[str, int],
    *,
    extra_files: Sequence[str] = (),
    window: Window = DEV_WINDOW,
) -> dict[str, Any]:
    """The manifest for the store under ``tmp``, written and returned.

    ``extra_files`` are the ``OPTIONAL_DATA_FILES`` this build actually wrote; they join
    ``files`` (and therefore the fingerprint) and nothing else. ``_COUNT_KEYS`` deliberately
    gains nothing: ``MANIFEST_KEYS`` is asserted as a whole set by
    ``engine/tests/test_research_store.py``, which no phase of this plan set owns.

    ``window`` is written as the three ``OPTIONAL_MANIFEST_KEYS`` **only when it is not the dev
    window**. A dev build therefore seals exactly the nine ``MANIFEST_KEYS`` it always has, so
    ``engine/.research``'s manifest stays byte-identical and the test above stays green. The
    fingerprint is unaffected either way -- ``fingerprint_of`` hashes the ``files`` map alone --
    but the manifest's bytes are not, and they are what that test reads.

    ``store_start`` is ``STORE_START`` for both windows: it is where the DATA starts, and the
    test store holds the same deep history the dev store does. Only ``window_start`` says where
    scoring begins.
    """
    files = {name: file_sha256(tmp / name) for name in (*DATA_FILES, *extra_files)}
    manifest: dict[str, Any] = {
        "dev_end": DEV_END.isoformat(),
        "store_start": STORE_START.isoformat(),
        **{key: int(counts[key]) for key in _COUNT_KEYS},
        "files": files,
        "fingerprint": fingerprint_of(files),
    }
    if not _is_dev_window(window):
        manifest[WINDOW_NAME_KEY] = window.name
        manifest[WINDOW_START_KEY] = window.start.isoformat()
        manifest[WINDOW_END_KEY] = window.end.isoformat()
    with (tmp / MANIFEST_FILE).open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    return manifest


def _swap_in(tmp: Path, store_dir: Path) -> None:
    old = store_dir.with_name(store_dir.name + ".old")
    if old.exists():
        shutil.rmtree(old)
    if store_dir.exists():
        os.replace(store_dir, old)
    os.replace(tmp, store_dir)
    shutil.rmtree(old, ignore_errors=True)


# ---- refresh -------------------------------------------------------------------------------


def refresh_fundamentals(
    store_dir: Path,
    facts: Sequence[Fact],
    *,
    data_dir: Path | None = None,
    window: Window = DEV_WINDOW,
) -> dict[str, Any]:
    """Rewrite an existing store's ``fundamentals.csv`` from ``facts``; return the new manifest.

    This is ``build_store``'s panel half without its download half. ``bars.csv``,
    ``dividends.csv``, ``fx.csv`` and ``unserved.csv`` are carried over **byte for byte** from
    the store already at ``store_dir``; only ``fundamentals.csv`` is written anew, the manifest
    is re-sealed and the directory is swapped in with the same ``.tmp`` / ``.old`` /
    ``os.replace`` discipline ``build_store`` uses -- so on any failure nothing is written and
    the store on disk is left exactly as it was.

    Why this exists rather than ``build_store(facts=new_facts)``: ``build_store`` always fetches
    FX and downloads every symbol's bars from yfinance before it writes anything, and yfinance
    answers differently day to day. A rebuild would therefore replace every bar row and break
    comparability with the lab trials already recorded against this store's fingerprint.
    Copying -- not rebuilding -- is what keeps one comparable price history while the panel
    moves underneath it.

    The fingerprint **does** change, and that is correct: ``fundamentals.csv`` changed and
    ``fingerprint_of`` hashes the whole file map. What does not change is a single bar.

    ``window`` must be the window the store declares; pass ``declared_window(store_dir)``.
    ``load_store`` below refuses a mismatch, so a dev refresh can never be aimed at the test
    store or the reverse, and ``_seal`` re-declares the same window the store had -- refreshing
    a store never changes which window it is for.

    ``facts`` is a plain sequence of ``fundamentals.Fact``, exactly as ``build_store`` takes it
    -- never a database connection, because this module imports nothing from ``seer_engine.db``
    (see the module docstring's "Never Neon"). ``commands/research_store.py`` reads them behind
    ``--refresh-fundamentals`` and passes them in. An empty sequence is legal and writes a
    header-only ``fundamentals.csv`` (an explicitly empty panel); ``None`` is not, because
    "refresh with nothing" is ambiguous -- keep the panel, or clear it? -- and the caller must
    say which.

    The source store is verified with ``load_store`` first: every sha256, the fingerprint, the
    five ``_COUNT_KEYS`` counts and the window's date guards. A store that fails any of them is
    refused with ``ResearchStoreError`` and nothing is written. Refusing to refresh a store that
    cannot be verified is the point of doing it this way round: a silently half-valid store is
    exactly the failure this plan set exists to end. A store with **no** ``fundamentals.csv`` at
    all -- one built before the optional fifth file existed -- is a legal source: it loads with
    an empty panel, and the refresh legitimately adds the file to it.

    The five ``_COUNT_KEYS`` values are carried over from the verified manifest rather than
    recomputed, and the two are the same number by construction: ``load_store`` has just
    compared every one of them against the files this call then copies byte for byte, so
    recomputing could only restate a check that has already passed. They are never re-derived
    from a download -- there is no download.
    """
    store_dir = Path(store_dir)
    if facts is None:
        raise ValueError(
            "refresh_fundamentals needs a sequence of fundamentals.Fact; pass () to write an "
            "empty panel"
        )
    try:
        data = load_store(store_dir, data_dir=data_dir, window=window)
    except ValueError as exc:
        raise ResearchStoreError(
            f"{store_dir}: refusing to refresh a store that does not verify: {exc}"
        ) from exc
    # Keep the manifest, drop the Market: the real store holds 2.49M bar rows and nothing below
    # needs them -- only the recorded counts and the per-file digests.
    before = dict(data.manifest)
    del data
    counts = {key: int(before[key]) for key in _COUNT_KEYS}

    tmp = store_dir.with_name(store_dir.name + ".tmp")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir()
    try:
        for name in DATA_FILES:
            shutil.copyfile(store_dir / name, tmp / name)
            copied = file_sha256(tmp / name)
            if copied != before["files"][name]:
                raise ResearchStoreError(
                    f"{name}: the carried-over copy hashes {copied}, the verified store hashes "
                    f"{before['files'][name]}; the copy is not byte-identical, nothing written"
                )
        _write_text(tmp / FUNDAMENTALS_FILE, FUNDAMENTALS_HEADER, fundamentals_lines(facts))
        manifest = _seal(tmp, counts, extra_files=(FUNDAMENTALS_FILE,), window=window)
        _swap_in(tmp, store_dir)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    log.info(
        "research: store %s panel refreshed: %d facts written, %d bar rows carried over "
        "unchanged, fingerprint %s -> %s",
        store_dir,
        len(facts),
        counts["bar_rows"],
        before["fingerprint"],
        manifest["fingerprint"],
    )
    return manifest


# ---- load ----------------------------------------------------------------------------------


def load_store(
    store_dir: Path, *, data_dir: Path | None = None, window: Window = DEV_WINDOW
) -> ResearchData:
    """Load and verify the store at ``store_dir`` (no network, no database).

    ``window`` is the window the **caller** expects. It defaults to ``DEV_WINDOW``, so every
    dev path -- ``lab run``, ``backtest_dev``, this module's own refresh -- gets the dev
    guarantee without passing anything, and a mis-pointed ``SEER_RESEARCH_STORE`` aimed at the
    test store fails loudly here instead of silently running the dev pipeline on test data.
    A test-window caller must ask for it explicitly; ``declared_window(store_dir)`` reads what
    a store is for, and passing that back in is the normal opening.

    ValueError when: the manifest is missing or malformed, or was built for another DEV_END or
    STORE_START; **the store declares a different window than the caller asked for**; a file's
    sha256 or the fingerprint does not match the manifest; any bar, dividend or FX row is dated
    after ``window.end`` (D9, data level); the counts disagree.
    """
    store_dir = Path(store_dir)
    manifest = _read_manifest(store_dir, window)
    files: dict[str, str] = manifest["files"]
    # The manifest's OWN keys, not DATA_FILES: a store built before fundamentals existed lists
    # four files and must hash exactly those four, so its fingerprint is bit-identical to the
    # one origin/main computes for the same directory.
    for name in sorted(files):
        actual = file_sha256(store_dir / name)
        if actual != files[name]:
            raise ValueError(
                f"{name}: sha256 {actual} does not match the manifest ({files[name]}); the store "
                "was modified after it was built; rebuild it with `python -m seer_engine research_store`"
            )
    fingerprint = fingerprint_of(files)
    if fingerprint != manifest["fingerprint"]:
        raise ValueError(
            f"fingerprint {fingerprint} does not match the manifest ({manifest['fingerprint']})"
        )
    frame = _read_bars(store_dir / BARS_FILE, window.end)
    dividends = _read_dividends(store_dir / DIVIDENDS_FILE, window.end)
    fx_rows = _read_fx(store_dir / FX_FILE, window.end)
    unserved = _read_unserved(store_dir / UNSERVED_FILE)
    fundamentals = (
        _read_fundamentals(store_dir / FUNDAMENTALS_FILE)
        if FUNDAMENTALS_FILE in files
        else EMPTY_FUNDAMENTALS
    )
    served = int(frame["symbol"].nunique()) if len(frame) else 0
    actual_counts = {
        "bar_rows": int(len(frame)),
        "dividend_rows": sum(len(v) for v in dividends.values()),
        "fx_rows": len(fx_rows),
        "symbols_requested": served + len(unserved),
        "symbols_served": served,
    }
    for key in _COUNT_KEYS:
        if manifest[key] != actual_counts[key]:
            raise ValueError(f"{key}: the manifest says {manifest[key]}, the files hold {actual_counts[key]}")
    try:
        history = histories_from_frame(frame)
    except LoadError as exc:
        raise ValueError(f"{BARS_FILE}: {exc}") from exc
    market = Market(
        history=history,
        membership=research_membership(data_dir, window=window),
        fx=fx_rows,
        fundamentals=fundamentals,
        dividends=DividendCalendar.from_map(dividends),
    )
    spy_dividends = tuple(
        Dividend(ex_date=d, amount=a) for d, a in sorted(dividends.get("SPY", {}).items())
    )
    log.info(
        "research: loaded %s for the %s: %d symbols with bars, %d bar rows, %d dividends, "
        "%d fx rows, %d unserved, fingerprint %s",
        store_dir,
        _window_label(window),
        len(history),
        actual_counts["bar_rows"],
        actual_counts["dividend_rows"],
        actual_counts["fx_rows"],
        len(unserved),
        fingerprint,
    )
    return ResearchData(
        market=market,
        dividends=dividends,
        spy_dividends=spy_dividends,
        fingerprint=fingerprint,
        manifest=manifest,
        unserved=unserved,
        window=window,
        price_fingerprint=price_fingerprint_of(files),
    )


def _manifest_json(store_dir: Path) -> tuple[Path, dict[str, Any]]:
    """``manifest.json``'s parsed object and its path; ValueError when missing or not an object."""
    path = store_dir / MANIFEST_FILE
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ValueError(
            f"{store_dir}: no research store ({MANIFEST_FILE} missing); build it with "
            "`python -m seer_engine research_store`"
        ) from exc
    try:
        manifest = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: not valid JSON ({exc})") from exc
    if not isinstance(manifest, dict):
        raise ValueError(
            f"{path}: expected keys {sorted(MANIFEST_KEYS)}, got {type(manifest).__name__}"
        )
    return path, manifest


def _declared_window(path: Path, manifest: Mapping[str, Any]) -> Window:
    """The window ``manifest`` declares. **No window keys means the dev window.**

    That default is the compatibility hinge: ``engine/.research`` was sealed with nine keys and
    must keep loading untouched, exactly as a four-file manifest from before fundamentals
    existed keeps loading (see :data:`OPTIONAL_DATA_FILES`).
    """
    if WINDOW_END_KEY not in manifest:
        return DEV_WINDOW
    name = manifest.get(WINDOW_NAME_KEY)
    raw_start = manifest.get(WINDOW_START_KEY)
    raw_end = manifest[WINDOW_END_KEY]
    if name not in WINDOW_NAMES or name == DEV_WINDOW.name:
        allowed = tuple(n for n in WINDOW_NAMES if n != DEV_WINDOW.name)
        raise ValueError(
            f"{path}: {WINDOW_NAME_KEY!r} must be one of {allowed}, got {name!r}; the dev "
            "window is declared by leaving these keys out, never by name"
        )
    try:
        start = date.fromisoformat(raw_start)
        end = date.fromisoformat(raw_end)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"{path}: {WINDOW_START_KEY!r} and {WINDOW_END_KEY!r} must be ISO dates, got "
            f"{raw_start!r} and {raw_end!r}"
        ) from exc
    if start <= DEV_END or end < start:
        raise ValueError(
            f"{path}: declares the window {start.isoformat()}..{end.isoformat()}; a store that "
            f"declares a window must start after DEV_END {DEV_END.isoformat()} (a window ending "
            "inside the dev window is the dev window, and is declared by leaving the keys out) "
            "and must not end before it starts"
        )
    return _window(name, start, end)


def declared_window(store_dir: Path) -> Window:
    """The window the store at ``store_dir`` is for, from its manifest alone.

    Reads no data file and verifies nothing: it answers "which window is this store for?" so a
    caller can pass the matching ``window`` to :func:`load_store`, which does the verifying.
    A store with no window keys declares ``DEV_WINDOW``.

    This is not a way around the refusal in :func:`load_store`. It reports what the store says
    about itself; a caller that wants the dev window still passes ``DEV_WINDOW`` and is still
    refused a test store. ``lab run`` and ``backtest_dev`` never call this.

    ValueError when the store or its manifest is missing, unparseable, or declares a window
    that is not a window.
    """
    path, manifest = _manifest_json(Path(store_dir))
    return _declared_window(path, manifest)


def _read_manifest(store_dir: Path, window: Window = DEV_WINDOW) -> dict[str, Any]:
    path, manifest = _manifest_json(store_dir)
    keys = set(manifest)
    if keys != MANIFEST_KEYS and keys != MANIFEST_KEYS | OPTIONAL_MANIFEST_KEYS:
        raise ValueError(
            f"{path}: expected keys {sorted(MANIFEST_KEYS)}, optionally also "
            f"{sorted(OPTIONAL_MANIFEST_KEYS)} (all three or none), got {sorted(keys)}"
        )
    if manifest["dev_end"] != DEV_END.isoformat():
        raise ValueError(
            f"{path}: the store was built for dev_end {manifest['dev_end']!r}; this code expects "
            f"{DEV_END.isoformat()}; rebuild it"
        )
    if manifest["store_start"] != STORE_START.isoformat():
        raise ValueError(
            f"{path}: the store was built for store_start {manifest['store_start']!r}; this code "
            f"expects {STORE_START.isoformat()}; rebuild it"
        )
    declared = _declared_window(path, manifest)
    if (declared.name, declared.start, declared.end) != (window.name, window.start, window.end):
        raise ValueError(
            f"{path}: this store declares the {_window_label(declared)}, but the caller asked "
            f"for the {_window_label(window)}. A dev store and a test store are not "
            "interchangeable: the test store holds the same history AND every session after "
            f"{DEV_END.isoformat()}, so loading one where the other is expected would run the "
            "dev pipeline on unseen data (D9). Point --store at the matching store directory "
            f"({STORE_DIR.name} for the dev window, {TEST_STORE_DIR.name} for the test window)."
        )
    files = manifest["files"]
    # The four DATA_FILES are required; the OPTIONAL_DATA_FILES may be there and nothing else
    # may. This is what keeps a store built before fundamentals existed loadable -- widening
    # DATA_FILES instead would reject every such store with a ValueError before any reader ran.
    if (
        not isinstance(files, dict)
        or not set(DATA_FILES) <= set(files) <= set(DATA_FILES) | set(OPTIONAL_DATA_FILES)
        or not all(isinstance(v, str) for v in files.values())
    ):
        raise ValueError(
            f"{path}: 'files' must map {list(DATA_FILES)} (optionally also "
            f"{list(OPTIONAL_DATA_FILES)}) to sha256 hex strings"
        )
    if not isinstance(manifest["fingerprint"], str):
        raise ValueError(f"{path}: 'fingerprint' must be a string")
    for key in _COUNT_KEYS:
        value = manifest[key]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{path}: {key!r} must be a non-negative int, got {value!r}")
    return manifest


def _after_window_end(name: str, what: str, d: date, end: date) -> ValueError:
    """The D9 data-level refusal. The dev message is reproduced verbatim.

    ``test_research_store.py`` matches ``"after DEV_END 2015-10-16"``; that test is shipped
    code this phase must leave green and must not edit, so the dev branch keeps the exact
    string it has today.
    """
    if end == DEV_END:
        return ValueError(
            f"{name}: {what} dated {d.isoformat()} is after DEV_END {DEV_END.isoformat()}; the "
            "research store must never hold a test-window row (D9)"
        )
    return ValueError(
        f"{name}: {what} dated {d.isoformat()} is after the store's window end "
        f"{end.isoformat()}; a store must never hold a row after the window it declares (D9)"
    )


def _read_bars(path: Path, end: date = DEV_END) -> pd.DataFrame:
    with path.open(encoding="utf-8") as fh:
        header = fh.readline().rstrip("\n")
    if header != BARS_HEADER:
        raise ValueError(f"{path.name}: expected header {BARS_HEADER!r}, got {header!r}")
    frame = pd.read_csv(
        path,
        sep=",",
        header=0,
        dtype={
            "symbol": str,
            "date": str,
            "open": np.float64,
            "high": np.float64,
            "low": np.float64,
            "close": np.float64,
            "volume": np.int64,
        },
        na_filter=False,
        float_precision="round_trip",
        engine="c",
    )
    if tuple(frame.columns) != BAR_COLUMNS:
        raise ValueError(f"{path.name}: columns {list(frame.columns)}, expected {list(BAR_COLUMNS)}")
    frame["date"] = pd.to_datetime(frame["date"], format="%Y-%m-%d")
    if len(frame):
        latest = frame["date"].max().date()
        if latest > end:
            symbol = str(frame.loc[frame["date"].idxmax(), "symbol"])
            raise _after_window_end(path.name, f"a {symbol} bar", latest, end)
        earliest = frame["date"].min().date()
        if earliest < STORE_START:
            raise ValueError(f"{path.name}: a bar dated {earliest} is before STORE_START {STORE_START}")
    return frame


def _data_lines(path: Path, header: str) -> list[tuple[int, str]]:
    """(1-based line number, line) for every row after the header; strict LF text."""
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    if not text.endswith("\n") or lines[0] != header:
        raise ValueError(f"{path.name}: expected header {header!r} and LF-terminated lines")
    rows = list(enumerate(lines[1:-1], start=2))
    for number, line in rows:
        if not line:
            raise ValueError(f"{path.name}:{number}: empty line")
    return rows


def _parse_date(raw: str, where: str) -> date:
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(f"{where}: bad date {raw!r}") from exc


def _parse_positive(raw: str, where: str) -> Decimal:
    try:
        value = Decimal(raw)
    except InvalidOperation as exc:
        raise ValueError(f"{where}: bad number {raw!r}") from exc
    if not value.is_finite() or value <= 0:
        raise ValueError(f"{where}: {raw!r} must be a finite number > 0")
    return value


def _read_dividends(path: Path, end: date = DEV_END) -> dict[str, dict[date, Decimal]]:
    out: dict[str, dict[date, Decimal]] = {}
    for number, line in _data_lines(path, DIVIDENDS_HEADER):
        where = f"{path.name}:{number}"
        fields = line.split(",")
        if len(fields) != 3:
            raise ValueError(f"{where}: expected 3 fields, got {len(fields)}")
        symbol, raw_date, raw_amount = fields
        ex_date = _parse_date(raw_date, where)
        if ex_date > end:
            raise _after_window_end(where, f"a {symbol} dividend", ex_date, end)
        amount = _parse_positive(raw_amount, where)
        per_symbol = out.setdefault(symbol, {})
        if ex_date in per_symbol:
            raise ValueError(f"{where}: duplicate {symbol} dividend on {ex_date}")
        per_symbol[ex_date] = amount
    return {symbol: dict(sorted(rows.items())) for symbol, rows in sorted(out.items())}


def _read_fx(path: Path, end: date = DEV_END) -> tuple[tuple[date, Decimal], ...]:
    rows: list[tuple[date, Decimal]] = []
    for number, line in _data_lines(path, FX_HEADER):
        where = f"{path.name}:{number}"
        fields = line.split(",")
        if len(fields) != 2:
            raise ValueError(f"{where}: expected 2 fields, got {len(fields)}")
        d = _parse_date(fields[0], where)
        if d > end:
            raise _after_window_end(where, "a USD/IDR rate", d, end)
        rows.append((d, to_decimal(_parse_positive(fields[1], where))))
    return tuple(rows)


def _read_unserved(path: Path) -> tuple[str, ...]:
    symbols: list[str] = []
    for number, line in _data_lines(path, UNSERVED_HEADER):
        symbol, sep, _reason = line.partition(",")
        if not sep or not symbol:
            raise ValueError(f"{path.name}:{number}: expected symbol,reason")
        symbols.append(symbol)
    return tuple(symbols)


# ---- verification --------------------------------------------------------------------------


def check_spy_sessions(
    data: ResearchData, start: date = SPY_CHECK_START, end: date | None = None
) -> Check:
    """SPY has a bar on every NYSE session in [start, end].

    ``end`` defaults to the store's own window end, so a dev store is still checked to
    2015-10-16 and a test store is checked to the session it was built through.
    """
    if end is None:
        end = data.window.end
    sess = dates.sessions(start, end)
    h = data.market.history.get("SPY")
    if h is None:
        return Check("spy-sessions", False, "no SPY bars in the store")
    have = set(h.dates.tolist())
    missing = [d for d in sess if d not in have]
    detail = f"{len(sess)} NYSE sessions {start.isoformat()}..{end.isoformat()}, {len(missing)} without a SPY bar"
    if missing:
        detail += " (first: " + ", ".join(d.isoformat() for d in missing[:5]) + ")"
    return Check("spy-sessions", not missing, detail)


def check_spy_dividends(data: ResearchData, vendored: Sequence[Dividend]) -> Check:
    """The store's SPY dividends equal the vendored file on the overlap of the two.

    The overlap is [first vendored ex_date, min(window end, last vendored ex_date)] --
    2015-03-20..2015-10-16 for the dev store, where the vendored file (which runs well past
    DEV_END) is the longer of the two. For a test store built past the vendored file's last row
    the clamp is what stops a store dividend the file simply does not have yet from reading as
    a mismatch. It cannot weaken the dev check: there, the window end is the earlier bound and
    nothing changes.
    """
    if not vendored:
        return Check("spy-dividends", False, "the vendored SPY dividend file is empty")
    lo = vendored[0].ex_date
    hi = min(data.window.end, vendored[-1].ex_date)
    ours = [(d.ex_date, d.amount) for d in data.spy_dividends if lo <= d.ex_date <= hi]
    theirs = [(d.ex_date, d.amount) for d in vendored if lo <= d.ex_date <= hi]
    ok = bool(theirs) and ours == theirs
    detail = (
        f"{lo.isoformat()}..{hi.isoformat()}: store "
        + ", ".join(f"{d.isoformat()}={a}" for d, a in ours)
        + " | vendored "
        + ", ".join(f"{d.isoformat()}={a}" for d, a in theirs)
    )
    return Check("spy-dividends", ok, detail)


def check_dividend_scale(
    data: ResearchData, symbol: str = SCALE_CHECK_SYMBOL, year: int = SCALE_CHECK_YEAR
) -> Check:
    """Every ``symbol`` dividend in ``year`` is between SCALE_MIN_YIELD and SCALE_MAX_YIELD of the
    close before its ex-date: split-adjusted dividends on split-adjusted prices (AAPL 2012:
    about 0.43%; an unadjusted $2.65 on a $22 adjusted close would be about 12%)."""
    name = f"dividend-scale-{symbol}-{year}"
    h = data.market.history.get(symbol)
    divs = [(d, a) for d, a in data.dividends.get(symbol, {}).items() if d.year == year]
    if h is None or not divs:
        return Check(name, False, f"no {symbol} bars or no {symbol} dividends in {year}")
    ok = True
    parts: list[str] = []
    for d, amount in divs:
        i = int(np.searchsorted(h.dates, np.datetime64(d, "D"))) - 1
        if i < 0:
            ok = False
            parts.append(f"{d.isoformat()}: no bar before the ex-date")
            continue
        close = to_decimal(float(h.close[i]))
        ratio = amount / close
        good = SCALE_MIN_YIELD < ratio < SCALE_MAX_YIELD
        ok = ok and good
        parts.append(f"{d.isoformat()}: {amount} / close {close} = {ratio:.4%}")
    return Check(name, ok, "; ".join(parts))


def run_checks(data: ResearchData, vendored: Sequence[Dividend]) -> tuple[Check, ...]:
    """The real build's three verifications, in a fixed order."""
    return (
        check_spy_sessions(data),
        check_spy_dividends(data, vendored),
        check_dividend_scale(data),
    )

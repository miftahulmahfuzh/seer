# Phase 3: yfinance + FX history backfill

**Plan set:** `ENGINE_DATA_PIPELINE_PLAN.md`
**Analysis:** `20261003-121931-K7P2_code_analyzer.md`
**Spec:** `docs/handover/2026-10-03-data-pipeline.md` (§2.1, §3 "Bars"/"History source"/"FX"/"Demo data", §6.2, §6.3, §6.6, §6.7)
**Satisfies:** R1, R4, R6. R1: 10+ years of split-adjusted daily bars for every fetchable ever-member, with unfetchable symbols logged. R4: re-running changes nothing. R6: tests and `--dry-run`.
**Depends on:** Phase 1
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine` (`yahoo.py`, `commands/backfill.py`)

---

## Goal

After this phase, `python -m seer_engine backfill` loads split-adjusted (not dividend-adjusted)
daily bars from yfinance for every symbol in `universe.all_symbols(conn, since=start)` plus SPY,
from 2015-01-02 to the last completed NYSE session. It loads in throttled, individually committed
batches, records every symbol's outcome in `backfill_log`, resumes by skipping symbols already
logged, and loads USD/IDR history from Frankfurter into `fx_rates`. Re-running with the same
arguments changes no `bars`/`fx_rates` rows. `--dry-run` computes everything and then rolls it all
back. The tests run without the network.

## Facts verified while planning (yfinance 1.7.0, live, 2026-10-03)

The planner installed `yfinance==1.7.0` in a throwaway venv and called
`yf.download(tickers=["SPY","AAPL","BRK-B"], start="2026-09-24", end="2026-10-03", interval="1d",
auto_adjust=False, actions=False, group_by="ticker", threads=False, progress=False, repair=False)`:

1. **Columns are always a 2-level `MultiIndex` named `("Ticker", "Price")`**, even for a single
   ticker (because `multi_level_index=True` is the default). Price level values:
   `Open, High, Low, Close, Adj Close, Volume`.
2. **The index is tz-naive** (`datetime64[s]`, midnight, named `Date`), because `ignore_tz`
   defaults to True for daily bars. `Timestamp.date()` is the exchange date. No local timezone is
   involved.
3. **Per-ticker errors are swallowed.** A bad ticker (`ZZZZNOPE`) comes back as all-NaN columns,
   and `download()` only *logs* `"['ZZZZNOPE']: possibly delisted; no timezone found"` at ERROR on
   the `yfinance` logger. `YFRateLimitError` raised inside `Ticker.history` is caught in
   `multi._download_one` the same way and logged as
   `"['SPY']: YFRateLimitError('Too Many Requests. Rate limited. Try after a while.')"`.
   There is no public error dict (`shared._ERRORS` is gone in 1.x). **So the real downloader
   attaches a temporary handler to the `yfinance` logger and turns any captured rate-limit message
   into `yahoo.RateLimited`.** It also converts a directly raised `YFRateLimitError`.
4. yfinance upper-cases and de-duplicates tickers, and the column order is arbitrary (it uses a
   `set`). Parsing is therefore by label, never by position.
5. The planned `yahoo.py` (Step 1, verbatim) was run against that live call. SPY, AAPL and BRK.B
   each got 7 bars, keyed in dot form (`BRK.B`), and `ZZZZNOPE` came back `[]`. SPY 2026-10-01
   closed at `763.9900`, which matches Massive's split-adjusted `c 763.99` in the analysis, so the
   two sources agree on adjustment.
6. The whole Step 1–3 code was run against a local Postgres 16 with stand-ins for the phase-1
   modules that follow the shared contract. **32 tests passed.**

## Split timing (why the backfill records no splits)

yfinance's `Open/High/Low/Close/Volume` with `auto_adjust=False` are adjusted for every split up to
the moment of the download. A split that executes **after** the backfill ran is handled by the
nightly command (phase 4). It applies Massive's split to stored history through `split_adjustments`,
using a price-ratio heuristic to avoid double application. So this phase writes nothing to
`split_adjustments` and does not need to know about splits. If the backfill is re-run after a
split, `upsert_bars` overwrites the history with yfinance's newly adjusted values. Those values are
consistent, so this is correct too. Phase 4 should account for this ordering; see Handoffs.

## Assumptions (about phase 1, planned in parallel; from the plan index "Shared interface contract")

| # | Assumption | Used where |
|---|---|---|
| A1 | `bars.Bar` is a frozen dataclass with attributes `symbol, date, open, high, low, close, volume`. `bars.make_bar(symbol, d, o, h, l, c, v)` accepts `Decimal` prices and an `int` volume, rounds to 4 dp and returns `Bar`. | `yahoo.frame_to_bars`, `backfill._write_batch` (`.date`) |
| A2 | `bars.upsert_bars(conn, rows)` takes any iterable (including an empty list), runs on `conn` **without committing**, and returns the number of rows inserted or changed (0 for identical rows). | `_write_batch` |
| A3 | `fx.fetch_range(start, end) -> list[tuple[date, Decimal]]` and `fx.upsert_fx(conn, rows) -> int` (no commit, 0 for identical rows). | `_backfill_fx` |
| A4 | `db.transaction(conn, dry_run)` is a context manager that commits on clean exit, rolls back on `dry_run` or on an exception, and expects the connection to be idle on entry. This phase calls `conn.rollback()` after its own read-only queries (`_end_read`), so `db.transaction` always starts at top level whether it is built on `conn.commit()` or on `conn.transaction()`. | `_write_batch`, `_backfill_fx`, `_end_read` |
| A5 | `db.connect()` returns a `psycopg.Connection` with `autocommit=False`. | `run` |
| A6 | `demo.purge_demo_if_needed(conn, dry_run) -> bool` runs in its own transaction and is a no-op when no demo run exists. Under `dry_run` it runs the TRUNCATE and rolls it back (phase 1), so nothing persists. | `backfill()` |
| A7 | `universe.BENCHMARK == "SPY"`. `universe.all_symbols(conn, since: date) -> list[str]` is sorted, uses the dot form and always includes SPY. It is called with the **keyword** `since=`. | `select_symbols` |
| A8 | `dates.last_completed_session(now_utc) -> date`. | `options_from_args` |
| A9 | Migration 002 creates `backfill_log(symbol text PRIMARY KEY, status text NOT NULL CHECK (status IN ('ok','empty','failed')), first_date date, last_date date, rows int, error text, updated_at timestamptz NOT NULL DEFAULT now())` (phase 1 Step 2; `rows` is nullable there, and this phase always writes it). The column is literally named `rows`, which this phase double-quotes. | `_LOG_UPSERT`, tests |
| A10 | `engine/tests/conftest.py` has a fixture `pg` that yields an open, **idle** (committed) `psycopg.Connection` to a fresh schema built from `db/migrations/*.sql`, and that skips with a reason if `PG_TEST_URL` is unset. | DB tests |
| A11 | `cli.py` adds the global `--dry-run` and `-v` before the subcommand, discovers `commands/backfill.py` automatically, calls `add_arguments(subparser)`, then `run(args)`, and uses its return value as the exit code. It also configures `logging`. | `run`, `add_arguments` |
| A12 | `pyproject.toml` already depends on `yfinance>=1.0` and `pandas>=2.2`. This phase adds no dependency. | — |

**Reconciled against phase 1's plan:** A1–A12 all hold as written in phase 1 (`make_bar` accepts
`Decimal`; `upsert_bars` raises `ValueError` on a duplicate `(symbol, date)` in one batch, which
cannot happen here because `frame_to_bars` keys by date and `download` de-duplicates symbols;
`db.transaction` re-raises after rollback; the `pg` fixture commits its migrations, so the
connection is idle). `run()` holds the connection with `try/finally: conn.close()`, which is
equivalent to phase 1's recommended `contextlib.closing(db.connect())`.

## Decisions taken in this phase

- **Resume semantics.** By default the backfill skips every symbol that already has a
  `backfill_log` row (`ok`, `empty` or `failed`), so a re-run after a crash only fetches what was
  never attempted. `--retry-failed` re-attempts `failed` and `empty` and still skips `ok`.
  `--symbols` ignores `backfill_log` entirely. This is how the index's "skip `ok`" and
  "`--retry-failed` re-attempts failed/empty" fit together: without it the flag would do nothing.
- **A failure never downgrades `ok`.** If a forced re-fetch (`--symbols`) of an `ok` symbol is
  rate-limited, its `ok` row (and its bars) stay.
- **`backfill_log` upsert is change-only.** Its `WHERE ... IS DISTINCT FROM` stops a re-run from
  touching `updated_at`, so a re-run with the same args leaves `backfill_log` byte-identical as well
  as `bars`.
- **One-symbol batches get no individual retry.** That call already was the individual attempt.
- **Exit code:** `0` when nothing failed. `1` when any symbol is `failed` or the FX fetch failed;
  bars that were fetched are still committed. `2` for a usage or precondition error (empty
  universe, `--start` after `--end`). `empty` is an expected outcome (delisted or unknown to Yahoo)
  and does not fail the run.
- **FX failure does not discard bars.** It is reported in the summary and the exit code.
- `yf_download` passes `multi_level_index=True` explicitly, in addition to the parameters the index
  lists. That is the 1.x default, and stating it pins the frame shape against future default changes.

## Interface Contract

**Deletes:** nothing
**Renames:** nothing
**Creates:**
- `seer_engine.yahoo` (`engine/src/seer_engine/yahoo.py`): `RateLimited(Exception)`, `Downloader` (type alias `Callable[[list[str], date, date], pd.DataFrame | None]`), `to_yahoo(symbol) -> str`, `from_yahoo(ticker) -> str`, `yf_download(tickers, start, end_exclusive) -> pd.DataFrame | None`, `download(symbols, start, end_exclusive, *, downloader=None) -> dict[str, list[Bar]]`, `parse_frame(frame, tickers) -> dict[str, list[Bar]]`, `frame_to_bars(symbol, sub) -> list[Bar]`, `PRICE_COLUMNS`, `VOLUME_COLUMN`
- `seer_engine.commands.backfill` (`engine/src/seer_engine/commands/backfill.py`): `HELP`, `add_arguments(p)`, `run(args) -> int`, `backfill(conn, opts, *, downloader=None, sleep=time.sleep, fetch_fx=None) -> Summary`, `Options`, `Summary`, `SymbolResult`, `BackfillError`, `options_from_args(args, now=None)`, `select_symbols(conn, opts)`, `fetch_batch(batch, start, end, *, downloader, sleep)`, `format_summary(summary, opts)`, constants `DEFAULT_START = date(2015, 1, 2)`, `DEFAULT_BATCH_SIZE = 40`, `BATCH_PAUSE_S = 3.0`, `RATE_LIMIT_BACKOFF_S = (60.0, 120.0, 240.0)`
- CLI: `python -m seer_engine [--dry-run] backfill [--start YYYY-MM-DD] [--end YYYY-MM-DD] [--symbols A,B] [--retry-failed] [--skip-fx | --fx-only] [--batch-size N]`
- `engine/tests/test_backfill.py`

**Signature changes:** none
**Requires (from earlier phases):** Phase 1: `bars.Bar`, `bars.make_bar`, `bars.upsert_bars`, `fx.fetch_range`, `fx.upsert_fx`, `db.connect`, `db.transaction`, `demo.purge_demo_if_needed`, `universe.all_symbols(conn, since=)`, `universe.BENCHMARK`, `dates.last_completed_session`, table `backfill_log` (A9), `pg` fixture (A10), command auto-discovery and global `--dry-run` (A11), and the `yfinance`/`pandas` deps (A12). Phase 2 is needed at **run time only**, not for tests: a populated `universe` table. Without one, `backfill` exits 2 and says to run `universe refresh`.
**Writes tables:** `bars` (upsert), `backfill_log` (upsert), `fx_rates` (upsert). Reads `backfill_log` and `universe` (through `universe.all_symbols`). Does **not** write `runs`, `split_adjustments` or `universe`.
**Leaves alone (owned by others):** every phase-1 file (`cli/config/db/http/dates/demo/universe/bars/fx/runs.py`, `commands/migrate.py`, `conftest.py`, `pyproject.toml`, migration 002); `membership.py`, `commands/universe.py`, `engine/data/*` (phase 2); `massive.py`, `splits.py`, `commands/nightly.py` (phase 4); `.github/`, `web/`, `docs/runbooks/` (phase 5).

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/yahoo.py` | create (line 1) | Yahoo ticker mapping, real `yf.download` wrapper with rate-limit detection, frame → `Bar` parsing |
| `engine/src/seer_engine/commands/backfill.py` | create (line 1) | `backfill` command: args, symbol selection/resume, batching, backoff, empty retry, per-batch transactions, `backfill_log`, FX history, summary |
| `engine/tests/test_backfill.py` | create (line 1) | 32 tests (14 pure, 18 against `pg`) |

## Implementation Steps

### Step 1: Yahoo access module
**File:** `engine/src/seer_engine/yahoo.py:1` (new file)
**Change:** Create the module. Everything Yahoo-specific lives here: the dash/dot ticker mapping, the
real downloader, and frame parsing. The downloader is a plain callable, so tests inject fakes.
**Code:**
```python
"""Yahoo Finance (yfinance) access for the one-off history backfill.

This module is the only place that knows Yahoo's ticker spelling: Seer's canonical
symbols use a dot (``BRK.B``), Yahoo uses a dash (``BRK-B``).

Prices are taken from yfinance's ``Open/High/Low/Close/Volume`` columns with
``auto_adjust=False``: split-adjusted, NOT dividend-adjusted. ``Adj Close`` (the
dividend-adjusted close) is ignored on purpose, so stored prices match what a broker
showed on that day apart from later splits.

The network call is a plain callable (:data:`Downloader`) so tests inject fakes and
never touch Yahoo.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Callable, Sequence
from datetime import date
from decimal import Decimal

import pandas as pd

from seer_engine import bars
from seer_engine.bars import Bar

log = logging.getLogger(__name__)

PRICE_COLUMNS: tuple[str, ...] = ("Open", "High", "Low", "Close")
VOLUME_COLUMN = "Volume"

# (yahoo_tickers, start, end_exclusive) -> raw yfinance frame (or None)
Downloader = Callable[[list[str], date, date], "pd.DataFrame | None"]

_RATE_LIMIT_MARKERS: tuple[str, ...] = ("YFRateLimitError", "Too Many Requests", "Rate limited")


class RateLimited(Exception):
    """Yahoo answered 'Too Many Requests' for at least one ticker in the call."""


def to_yahoo(symbol: str) -> str:
    """Canonical (dot) symbol -> Yahoo ticker: ``BRK.B`` -> ``BRK-B``."""
    return symbol.strip().upper().replace(".", "-")


def from_yahoo(ticker: str) -> str:
    """Yahoo ticker -> canonical (dot) symbol: ``BRK-B`` -> ``BRK.B``."""
    return ticker.strip().upper().replace("-", ".")


class _ErrorCapture(logging.Handler):
    """Collects ERROR records yfinance logs while a download runs.

    ``yf.download`` swallows per-ticker exceptions (including ``YFRateLimitError``)
    and only logs them, returning all-NaN columns for those tickers. Capturing the
    log is the only public way to tell "rate limited" apart from "no data".
    """

    def __init__(self) -> None:
        super().__init__(level=logging.ERROR)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.messages.append(record.getMessage())
        except Exception:  # pragma: no cover - a malformed record must not break the download
            pass


def yf_download(tickers: list[str], start: date, end_exclusive: date) -> pd.DataFrame | None:
    """The real downloader: one ``yf.download`` call for a batch of Yahoo tickers.

    Raises :class:`RateLimited` if yfinance raised or logged a rate-limit error for
    any ticker in the batch.
    """
    import yfinance as yf
    from yfinance.exceptions import YFRateLimitError

    yf_logger = logging.getLogger("yfinance")
    capture = _ErrorCapture()
    yf_logger.addHandler(capture)
    try:
        frame = yf.download(
            tickers=list(tickers),
            start=start.isoformat(),
            end=end_exclusive.isoformat(),
            interval="1d",
            auto_adjust=False,
            actions=False,
            group_by="ticker",
            threads=False,
            progress=False,
            repair=False,
            multi_level_index=True,
        )
    except YFRateLimitError as exc:
        raise RateLimited(str(exc)) from exc
    finally:
        yf_logger.removeHandler(capture)

    for message in capture.messages:
        if any(marker in message for marker in _RATE_LIMIT_MARKERS):
            raise RateLimited(message)
    return frame


def download(
    symbols: Sequence[str],
    start: date,
    end_exclusive: date,
    *,
    downloader: Downloader | None = None,
) -> dict[str, list[Bar]]:
    """Fetch daily bars for canonical ``symbols`` in ``[start, end_exclusive)``.

    Returns ``{canonical_symbol: [Bar, ...]}`` with an entry (possibly empty) for
    every requested symbol, bars sorted by date. Date filtering against the caller's
    inclusive range is the caller's job: Yahoo can return a partial current-day bar.
    """
    canonical = list(dict.fromkeys(s.strip().upper() for s in symbols))
    tickers = [to_yahoo(s) for s in canonical]
    fetch = downloader if downloader is not None else yf_download
    frame = fetch(tickers, start, end_exclusive)
    parsed = parse_frame(frame, tickers)
    return {s: parsed.get(s, []) for s in canonical}


def parse_frame(frame: pd.DataFrame | None, tickers: Sequence[str]) -> dict[str, list[Bar]]:
    """Turn a yfinance frame into ``{canonical_symbol: [Bar, ...]}``.

    Accepts the yfinance 1.x shape (``MultiIndex`` columns ``(Ticker, Price)`` with
    ``group_by='ticker'``, used even for one ticker), the ``group_by='column'`` shape
    ``(Price, Ticker)``, and flat ``Open/High/...`` columns when exactly one ticker
    was requested.
    """
    out: dict[str, list[Bar]] = {from_yahoo(t): [] for t in tickers}
    if frame is None or len(frame.index) == 0:
        return out
    single = len(tickers) == 1
    for ticker in tickers:
        sub = _ticker_frame(frame, ticker, single=single)
        if sub is None:
            log.debug("yahoo: %s not present in frame", ticker)
            continue
        symbol = from_yahoo(ticker)
        out[symbol] = frame_to_bars(symbol, sub)
    return out


def _price_level(columns: pd.MultiIndex) -> int | None:
    """Index of the column level holding Open/High/Low/Close (case-sensitive)."""
    for level in range(columns.nlevels):
        values = {str(v) for v in columns.get_level_values(level)}
        if set(PRICE_COLUMNS) <= values:
            return level
    return None


def _ticker_frame(frame: pd.DataFrame, ticker: str, *, single: bool) -> pd.DataFrame | None:
    columns = frame.columns
    if isinstance(columns, pd.MultiIndex):
        if columns.nlevels != 2:
            log.warning("yahoo: unexpected %d-level column index", columns.nlevels)
            return None
        price_level = _price_level(columns)
        if price_level is None:
            log.warning("yahoo: no Open/High/Low/Close level in columns")
            return None
        ticker_level = 1 - price_level
        wanted = ticker.upper()
        for label in columns.get_level_values(ticker_level).unique():
            if str(label).upper() == wanted:
                return frame.xs(label, axis=1, level=ticker_level)
        return None
    if single and set(PRICE_COLUMNS) <= {str(c) for c in columns}:
        return frame
    return None


def _dec(value: float) -> Decimal:
    return Decimal(str(value))


def frame_to_bars(symbol: str, sub: pd.DataFrame) -> list[Bar]:
    """One ticker's OHLCV frame -> sorted bars.

    Rows with any missing/non-finite OHLC are dropped, rows with a non-positive
    price are skipped, a missing volume becomes 0. Dates come from the tz-naive
    index (yfinance daily bars are exchange-local midnight); a tz-aware index is
    made naive *without* conversion, so the exchange-local date is kept. The
    machine's local timezone is never involved.
    """
    if not set(PRICE_COLUMNS) <= {str(c) for c in sub.columns}:
        return []
    index = pd.DatetimeIndex(sub.index)
    if index.tz is not None:
        index = index.tz_localize(None)
    prices = sub.loc[:, list(PRICE_COLUMNS)].to_numpy(dtype=float)
    if VOLUME_COLUMN in sub.columns:
        volumes = sub[VOLUME_COLUMN].to_numpy(dtype=float)
    else:
        volumes = [math.nan] * len(index)

    by_date: dict[date, Bar] = {}
    for ts, row, vol in zip(index, prices, volumes):
        if pd.isna(ts):
            continue
        o, h, l, c = (float(x) for x in row)
        if not all(math.isfinite(x) for x in (o, h, l, c)):
            continue
        if min(o, h, l, c) <= 0:
            log.debug("yahoo: %s %s non-positive price skipped", symbol, ts)
            continue
        vol = float(vol)
        volume = int(round(vol)) if math.isfinite(vol) and vol > 0 else 0
        d = ts.date()
        by_date[d] = bars.make_bar(symbol, d, _dec(o), _dec(h), _dec(l), _dec(c), volume)
    return [by_date[d] for d in sorted(by_date)]
```
**Impact:** New module, imported only by `commands/backfill.py`. `import yfinance` is deferred into
`yf_download`, so importing `seer_engine.yahoo` (and therefore `cli` command discovery) stays fast
and does not touch the network.

### Step 2: The backfill command
**File:** `engine/src/seer_engine/commands/backfill.py:1` (new file)
**Change:** Create the command module in the phase-1 shape (`HELP`, `add_arguments`, `run`). The
work itself is in `backfill(conn, opts, *, downloader, sleep, fetch_fx)` so tests can drive it on
the `pg` connection with fakes.

Flow of `backfill()`:
1. Unless `--fx-only`, `select_symbols` builds the list. `--symbols` is used as given. Otherwise it
   takes `universe.all_symbols(conn, since=start)` and raises `BackfillError` (exit 2) if that is
   only SPY, then drops symbols already in `backfill_log` (only `ok` ones with `--retry-failed`).
2. `_end_read(conn)` ends the implicit read transaction (A4).
3. `demo.purge_demo_if_needed(conn, dry_run)` runs **before any write**. It is not reached when the
   universe is empty.
4. Batches of `--batch-size` (default 40), with a 3 s pause between batches. Each batch is one
   `yahoo.download` call. On `RateLimited` the backoff is 60/120/240 s, then the batch's symbols are
   marked `failed`. Any other exception marks the batch `failed` without stopping the run. Bars are
   filtered to `start <= date <= end`. A symbol left empty gets one individual retry (after a 3 s
   pause), then is `empty`.
5. Each batch is committed in its own `db.transaction`: `bars.upsert_bars` plus a `backfill_log`
   upsert for exactly that batch's symbols. A crash loses at most one batch.
6. Unless `--skip-fx`, `fx.fetch_range(start, end)` and then `fx.upsert_fx` run in one transaction.
7. `SELECT pg_total_relation_size('bars')` goes into the summary.

**Code:**
```python
"""backfill — one-off, resumable load of history.

* Daily bars from yfinance (split-adjusted, not dividend-adjusted) for every symbol
  that was in the universe on or after ``--start``, plus SPY, in throttled batches.
  Each batch is written in its own transaction together with its ``backfill_log``
  rows, so a crash loses at most one batch and a re-run resumes where it stopped.
* USD/IDR history from Frankfurter into ``fx_rates``.

Splits: yfinance history is adjusted for every split up to the moment the backfill
runs. A split that executes *after* the backfill is applied to stored history by the
nightly command (``split_adjustments``), so this command records no splits.

Idempotent: every write is an upsert; re-running with the same arguments changes no
``bars`` / ``fx_rates`` rows (``upsert_bars`` / ``upsert_fx`` return 0).
"""

from __future__ import annotations

import argparse
import logging
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

import psycopg

from seer_engine import bars, dates, db, demo, fx, universe, yahoo
from seer_engine.bars import Bar

log = logging.getLogger(__name__)

HELP = "Backfill daily bars (yfinance) and USD/IDR history (Frankfurter); resumable."

DEFAULT_START = date(2015, 1, 2)
DEFAULT_BATCH_SIZE = 40
BATCH_PAUSE_S = 3.0
RATE_LIMIT_BACKOFF_S: tuple[float, ...] = (60.0, 120.0, 240.0)
ERROR_MAX_LEN = 500

STATUS_OK = "ok"
STATUS_EMPTY = "empty"
STATUS_FAILED = "failed"

Sleep = Callable[[float], None]
FetchFx = Callable[[date, date], "list[tuple[date, object]]"]


class BackfillError(Exception):
    """A user-facing reason the backfill cannot start (exit code 2)."""


@dataclass(frozen=True)
class Options:
    start: date
    end: date
    symbols: tuple[str, ...] | None = None
    retry_failed: bool = False
    skip_fx: bool = False
    fx_only: bool = False
    batch_size: int = DEFAULT_BATCH_SIZE
    dry_run: bool = False


@dataclass(frozen=True)
class SymbolResult:
    symbol: str
    status: str
    bars: tuple[Bar, ...] = ()
    error: str | None = None


@dataclass
class Summary:
    ok: list[str] = field(default_factory=list)
    empty: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    skipped: int = 0
    rows_fetched: int = 0
    rows_written: int = 0
    fx_rows_written: int = 0
    fx_error: str | None = None
    bars_bytes: int | None = None

    def exit_code(self) -> int:
        return 1 if (self.failed or self.fx_error) else 0


# --------------------------------------------------------------------------- CLI


def _iso_date(text: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"not a YYYY-MM-DD date: {text!r}") from exc


def _symbol_list(text: str) -> list[str]:
    items = [yahoo.from_yahoo(part) for part in text.split(",") if part.strip()]
    if not items:
        raise argparse.ArgumentTypeError("--symbols needs at least one symbol")
    return list(dict.fromkeys(items))


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
        "--start",
        type=_iso_date,
        default=DEFAULT_START,
        help=f"first date to load, YYYY-MM-DD (default {DEFAULT_START.isoformat()})",
    )
    p.add_argument(
        "--end",
        type=_iso_date,
        default=None,
        help="last date to load, YYYY-MM-DD (default: last completed NYSE session)",
    )
    p.add_argument(
        "--symbols",
        type=_symbol_list,
        default=None,
        help="comma list (e.g. AAPL,BRK.B) instead of the universe; ignores backfill_log",
    )
    p.add_argument(
        "--retry-failed",
        action="store_true",
        help="also re-attempt symbols logged as failed or empty",
    )
    fx_group = p.add_mutually_exclusive_group()
    fx_group.add_argument("--skip-fx", action="store_true", help="do not load USD/IDR history")
    fx_group.add_argument("--fx-only", action="store_true", help="load USD/IDR history only")
    p.add_argument(
        "--batch-size",
        type=_positive_int,
        default=DEFAULT_BATCH_SIZE,
        help=f"symbols per yfinance call (default {DEFAULT_BATCH_SIZE})",
    )


def options_from_args(args: argparse.Namespace, now: datetime | None = None) -> Options:
    end = args.end
    if end is None:
        end = dates.last_completed_session(now if now is not None else datetime.now(timezone.utc))
    if args.start > end:
        raise BackfillError(f"--start {args.start} is after --end {end}")
    return Options(
        start=args.start,
        end=end,
        symbols=tuple(args.symbols) if args.symbols else None,
        retry_failed=bool(args.retry_failed),
        skip_fx=bool(args.skip_fx),
        fx_only=bool(args.fx_only),
        batch_size=int(args.batch_size),
        dry_run=bool(args.dry_run),
    )


def run(args: argparse.Namespace) -> int:
    try:
        opts = options_from_args(args)
    except BackfillError as exc:
        log.error("backfill: %s", exc)
        return 2
    conn = db.connect()
    try:
        summary = backfill(conn, opts)
    except BackfillError as exc:
        log.error("backfill: %s", exc)
        return 2
    finally:
        conn.close()
    print(format_summary(summary, opts))
    return summary.exit_code()


# ---------------------------------------------------------------------- the work


def backfill(
    conn: psycopg.Connection,
    opts: Options,
    *,
    downloader: yahoo.Downloader | None = None,
    sleep: Sleep = time.sleep,
    fetch_fx: FetchFx | None = None,
) -> Summary:
    """Run the backfill on ``conn``. Network access is injectable for tests."""
    summary = Summary()
    todo: list[str] = []
    if not opts.fx_only:
        todo, summary.skipped = select_symbols(conn, opts)
    _end_read(conn)

    demo.purge_demo_if_needed(conn, opts.dry_run)

    if not opts.fx_only:
        _backfill_bars(conn, opts, todo, summary, downloader, sleep)
    if not opts.skip_fx:
        _backfill_fx(conn, opts, summary, fetch_fx if fetch_fx is not None else fx.fetch_range)

    summary.bars_bytes = _bars_size(conn)
    _end_read(conn)
    return summary


def select_symbols(conn: psycopg.Connection, opts: Options) -> tuple[list[str], int]:
    """Symbols still to fetch, and how many were skipped as already logged."""
    if opts.symbols:
        return list(opts.symbols), 0
    candidates = universe.all_symbols(conn, since=opts.start)
    if not set(candidates) - {universe.BENCHMARK}:
        raise BackfillError(
            "the universe table is empty; run `python -m seer_engine universe refresh` first"
        )
    logged = _logged_statuses(conn, candidates)
    done = {STATUS_OK} if opts.retry_failed else {STATUS_OK, STATUS_EMPTY, STATUS_FAILED}
    todo = [s for s in candidates if logged.get(s) not in done]
    return todo, len(candidates) - len(todo)


def _logged_statuses(conn: psycopg.Connection, symbols: Sequence[str]) -> dict[str, str]:
    rows = conn.execute(
        "SELECT symbol, status FROM backfill_log WHERE symbol = ANY(%s)",
        (list(symbols),),
    ).fetchall()
    return {symbol: status for symbol, status in rows}


def _backfill_bars(
    conn: psycopg.Connection,
    opts: Options,
    todo: list[str],
    summary: Summary,
    downloader: yahoo.Downloader | None,
    sleep: Sleep,
) -> None:
    size = opts.batch_size
    batches = [todo[i : i + size] for i in range(0, len(todo), size)]
    log.info(
        "backfill: %d symbols to fetch in %d batches (%d skipped), %s..%s",
        len(todo), len(batches), summary.skipped, opts.start, opts.end,
    )
    for number, batch in enumerate(batches, start=1):
        if number > 1:
            sleep(BATCH_PAUSE_S)
        results = fetch_batch(batch, opts.start, opts.end, downloader=downloader, sleep=sleep)
        written = _write_batch(conn, results, opts.dry_run)
        summary.rows_written += written
        for result in results:
            summary.rows_fetched += len(result.bars)
            if result.status == STATUS_OK:
                summary.ok.append(result.symbol)
            elif result.status == STATUS_EMPTY:
                summary.empty.append(result.symbol)
            else:
                summary.failed.append(result.symbol)
        log.info(
            "backfill: batch %d/%d done: %d ok, %d empty, %d failed, %d rows changed",
            number, len(batches),
            sum(r.status == STATUS_OK for r in results),
            sum(r.status == STATUS_EMPTY for r in results),
            sum(r.status == STATUS_FAILED for r in results),
            written,
        )


def fetch_batch(
    batch: Sequence[str],
    start: date,
    end: date,
    *,
    downloader: yahoo.Downloader | None,
    sleep: Sleep,
) -> list[SymbolResult]:
    """Download one batch; symbols that come back empty get one individual retry."""
    end_exclusive = end + timedelta(days=1)
    try:
        got = _download_with_backoff(batch, start, end_exclusive, downloader, sleep)
    except yahoo.RateLimited as exc:
        error = _error_text(f"rate limited after {len(RATE_LIMIT_BACKOFF_S)} retries: {exc}")
        log.warning("backfill: batch of %d failed: %s", len(batch), error)
        return [SymbolResult(s, STATUS_FAILED, error=error) for s in batch]
    except Exception as exc:  # noqa: BLE001 - any download error fails the batch, not the run
        error = _error_text(repr(exc))
        log.warning("backfill: batch of %d failed: %s", len(batch), error)
        return [SymbolResult(s, STATUS_FAILED, error=error) for s in batch]

    results: dict[str, SymbolResult] = {}
    empties: list[str] = []
    for symbol in batch:
        kept = _in_range(got.get(symbol, []), start, end)
        if kept:
            results[symbol] = SymbolResult(symbol, STATUS_OK, kept)
        else:
            empties.append(symbol)

    for symbol in empties:
        if len(batch) > 1:  # a one-symbol batch already was the individual attempt
            sleep(BATCH_PAUSE_S)
            try:
                again = _download_with_backoff([symbol], start, end_exclusive, downloader, sleep)
            except yahoo.RateLimited as exc:
                results[symbol] = SymbolResult(
                    symbol,
                    STATUS_FAILED,
                    error=_error_text(f"rate limited after {len(RATE_LIMIT_BACKOFF_S)} retries: {exc}"),
                )
                continue
            except Exception as exc:  # noqa: BLE001
                results[symbol] = SymbolResult(symbol, STATUS_FAILED, error=_error_text(repr(exc)))
                continue
            kept = _in_range(again.get(symbol, []), start, end)
            if kept:
                results[symbol] = SymbolResult(symbol, STATUS_OK, kept)
                continue
        results[symbol] = SymbolResult(
            symbol, STATUS_EMPTY, error=f"yfinance returned no bars for {start}..{end}"
        )
    return [results[s] for s in batch]


def _download_with_backoff(
    symbols: Sequence[str],
    start: date,
    end_exclusive: date,
    downloader: yahoo.Downloader | None,
    sleep: Sleep,
) -> dict[str, list[Bar]]:
    waits: tuple[float | None, ...] = (*RATE_LIMIT_BACKOFF_S, None)
    for wait in waits:
        try:
            return yahoo.download(symbols, start, end_exclusive, downloader=downloader)
        except yahoo.RateLimited:
            if wait is None:
                raise
            log.warning("backfill: rate limited; sleeping %.0f s", wait)
            sleep(wait)
    raise AssertionError("unreachable")  # pragma: no cover


def _in_range(found: Sequence[Bar], start: date, end: date) -> tuple[Bar, ...]:
    return tuple(b for b in found if start <= b.date <= end)


def _error_text(text: str) -> str:
    return text if len(text) <= ERROR_MAX_LEN else text[: ERROR_MAX_LEN - 3] + "..."


_LOG_UPSERT = """
INSERT INTO backfill_log (symbol, status, first_date, last_date, "rows", error, updated_at)
VALUES (%s, %s, %s, %s, %s, %s, now())
ON CONFLICT (symbol) DO UPDATE SET
    status = EXCLUDED.status,
    first_date = EXCLUDED.first_date,
    last_date = EXCLUDED.last_date,
    "rows" = EXCLUDED."rows",
    error = EXCLUDED.error,
    updated_at = EXCLUDED.updated_at
WHERE (backfill_log.status, backfill_log.first_date, backfill_log.last_date,
       backfill_log."rows", backfill_log.error)
      IS DISTINCT FROM
      (EXCLUDED.status, EXCLUDED.first_date, EXCLUDED.last_date,
       EXCLUDED."rows", EXCLUDED.error)
  AND NOT (backfill_log.status = 'ok' AND EXCLUDED.status = 'failed')
"""


def _write_batch(conn: psycopg.Connection, results: Sequence[SymbolResult], dry_run: bool) -> int:
    rows = [b for r in results for b in r.bars]
    params = [
        (
            r.symbol,
            r.status,
            r.bars[0].date if r.bars else None,
            r.bars[-1].date if r.bars else None,
            len(r.bars),
            r.error,
        )
        for r in results
    ]
    with db.transaction(conn, dry_run):
        written = bars.upsert_bars(conn, rows)
        with conn.cursor() as cur:
            cur.executemany(_LOG_UPSERT, params)
    return written


def _backfill_fx(conn: psycopg.Connection, opts: Options, summary: Summary, fetch_fx: FetchFx) -> None:
    try:
        rows = fetch_fx(opts.start, opts.end)
    except Exception as exc:  # noqa: BLE001 - FX failure is reported, bars already committed
        summary.fx_error = _error_text(repr(exc))
        log.error("backfill: FX history fetch failed: %s", summary.fx_error)
        return
    with db.transaction(conn, opts.dry_run):
        summary.fx_rows_written = fx.upsert_fx(conn, rows)
    log.info("backfill: fx_rates %d fetched, %d changed", len(rows), summary.fx_rows_written)


def _bars_size(conn: psycopg.Connection) -> int:
    row = conn.execute("SELECT pg_total_relation_size('bars')").fetchone()
    return int(row[0])


def _end_read(conn: psycopg.Connection) -> None:
    """Close the implicit read-only transaction so db.transaction starts at top level."""
    conn.rollback()


# ----------------------------------------------------------------------- output


def format_summary(summary: Summary, opts: Options) -> str:
    lines = [
        f"backfill {opts.start.isoformat()}..{opts.end.isoformat()}"
        + (" (dry run: every write rolled back)" if opts.dry_run else ""),
    ]
    if not opts.fx_only:
        lines.append(
            f"  symbols: {len(summary.ok)} ok, {len(summary.empty)} empty, "
            f"{len(summary.failed)} failed, {summary.skipped} skipped (already logged)"
        )
        lines.append(
            f"  bar rows: {summary.rows_fetched:,} fetched, {summary.rows_written:,} inserted or changed"
        )
        if summary.failed:
            lines.append(f"  failed: {', '.join(summary.failed)}  (re-run with --retry-failed)")
        if summary.empty:
            lines.append(f"  empty: {', '.join(summary.empty)}")
    if not opts.skip_fx:
        if summary.fx_error:
            lines.append(f"  fx: FAILED: {summary.fx_error}")
        else:
            lines.append(f"  fx rows: {summary.fx_rows_written:,} inserted or changed")
    if summary.bars_bytes is not None:
        lines.append(
            f"  bars table: {summary.bars_bytes / (1024 * 1024):.1f} MB (pg_total_relation_size)"
        )
    return "\n".join(lines)
```
**Impact:** Adds the `backfill` subcommand (auto-discovered, A11). Writes `bars`, `backfill_log` and
`fx_rates`. Its first write-capable action is the demo purge, which is a no-op once demo data is gone.

### Step 3: Tests
**File:** `engine/tests/test_backfill.py:1` (new file)
**Change:** 14 pure tests (ticker mapping, frame parsing for multi-ticker / single-ticker MultiIndex /
flat / `group_by='column'` / tz-aware / NaN / non-positive / rounding, rate-limit detection in the
real wrapper with `yfinance.download` monkeypatched, argument parsing) and 18 tests against `pg`
(batching + resume skip, date filtering, dot/dash storage, backoff then success, backoff exhausted →
failed and continue, `ok` never downgraded, empty → individual retry → `empty`, empty recovered on
retry, `--retry-failed`, second run → 0 changed rows for bars, FX and `backfill_log`, `--dry-run`
leaves `bars`/`backfill_log`/`fx_rates` empty, demo purge before any write, empty universe fails
before purge or download, `--fx-only`, FX failure reported, summary text and table size). Universe
contents come from monkeypatching `universe.all_symbols`, so the tests do not depend on phase 2 or on
the `universe` table's columns.
**Code:**
```python
"""Tests for yahoo.py (frame parsing, ticker mapping, rate-limit detection) and the
backfill command (batching, resume, backoff, empty retry, date filter, idempotency,
dry run, demo purge ordering). No test touches the network: the yfinance call is an
injected fake, sleeps are recorded instead of slept, FX history is a fake."""

from __future__ import annotations

import argparse
import logging
from datetime import date, datetime, timezone
from decimal import Decimal

import pandas as pd
import pytest

from seer_engine import bars, dates, demo, fx, universe, yahoo
from seer_engine.commands import backfill as backfill_cmd

COLS = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]

D0 = date(2023, 12, 29)  # before --start
D1 = date(2024, 1, 2)
D2 = date(2024, 1, 3)
D3 = date(2024, 1, 4)  # == --end
D4 = date(2024, 1, 5)  # after --end (a "partial current-day" bar)
START, END = D1, D3


def ticker_df(rows):
    """One ticker's yfinance-shaped frame. rows: [(date, o, h, l, c, v), ...]."""
    index = pd.DatetimeIndex([pd.Timestamp(r[0]) for r in rows], name="Date")
    data = [[o, h, l, c, round(c * 0.9, 6), v] for (_, o, h, l, c, v) in rows]
    return pd.DataFrame(data, index=index, columns=pd.Index(COLS, name="Price"), dtype=float)


def multi_frame(rows_by_ticker):
    """yfinance 1.x group_by='ticker' shape: MultiIndex (Ticker, Price), NaN-filled."""
    frames = {t: ticker_df(rows) for t, rows in rows_by_ticker.items()}
    return pd.concat(
        list(frames.values()), axis=1, keys=list(frames), names=["Ticker", "Price"], sort=True
    )


def rows_for(*days, base=10.0):
    return [(d, base, base + 1, base - 1, base + 0.5, 1000 + i) for i, d in enumerate(days)]


class FakeYahoo:
    """Injected downloader. data: yahoo ticker -> rows. Unknown tickers come back all-NaN."""

    def __init__(self, data, *, rate_limits=0, always_limited=(), empty_first=None):
        self.data = data
        self.rate_limits = rate_limits
        self.always_limited = set(always_limited)
        self.empty_first = dict(empty_first or {})
        self.calls: list[list[str]] = []

    def __call__(self, tickers, start, end_exclusive):
        self.calls.append(list(tickers))
        if self.rate_limits > 0:
            self.rate_limits -= 1
            raise yahoo.RateLimited("Too Many Requests. Rate limited.")
        if self.always_limited & set(tickers):
            raise yahoo.RateLimited("Too Many Requests. Rate limited.")
        out = {}
        for t in tickers:
            if self.empty_first.get(t, 0) > 0:
                self.empty_first[t] -= 1
                out[t] = []
            else:
                out[t] = self.data.get(t, [])
        return multi_frame(out)


class Sleeps(list):
    def __call__(self, seconds):
        self.append(seconds)


def opts(**kw):
    base = dict(start=START, end=END, skip_fx=True)
    base.update(kw)
    return backfill_cmd.Options(**base)


def no_fx(start, end):
    raise AssertionError("FX must not be fetched in this test")


@pytest.fixture
def the_universe(monkeypatch):
    def set_symbols(symbols):
        monkeypatch.setattr(universe, "all_symbols", lambda conn, since: sorted(symbols))

    return set_symbols


def count(conn, table):
    n = conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    conn.rollback()
    return n


def log_rows(conn):
    rows = conn.execute(
        'SELECT symbol, status, first_date, last_date, "rows", error FROM backfill_log ORDER BY symbol'
    ).fetchall()
    conn.rollback()
    return {r[0]: r[1:] for r in rows}


def bar_rows(conn):
    rows = conn.execute(
        "SELECT symbol, date, open, high, low, close, volume FROM bars ORDER BY symbol, date"
    ).fetchall()
    conn.rollback()
    return rows


# ------------------------------------------------------------ yahoo.py: mapping


def test_symbol_mapping_dot_dash():
    assert yahoo.to_yahoo("BRK.B") == "BRK-B"
    assert yahoo.to_yahoo(" aapl ") == "AAPL"
    assert yahoo.from_yahoo("BRK-B") == "BRK.B"
    assert yahoo.from_yahoo(yahoo.to_yahoo("BF.B")) == "BF.B"


# ------------------------------------------------------- yahoo.py: frame parsing


def test_parse_multi_ticker_frame_uses_close_not_adj_close():
    frame = multi_frame({"AAA": rows_for(D1, D2), "BRK-B": rows_for(D1, base=400.0)})
    out = yahoo.parse_frame(frame, ["AAA", "BRK-B"])
    assert set(out) == {"AAA", "BRK.B"}
    assert [b.date for b in out["AAA"]] == [D1, D2]
    first = out["AAA"][0]
    assert isinstance(first.date, date) and not isinstance(first.date, datetime)
    assert first.close == Decimal("10.5000")  # Close, not Adj Close (9.45)
    assert first.open == Decimal("10.0000")
    assert first.volume == 1000
    assert out["BRK.B"][0].symbol == "BRK.B"
    assert out["BRK.B"][0].close == Decimal("400.5000")


def test_parse_single_ticker_multiindex_frame():
    frame = multi_frame({"SPY": rows_for(D1, D2, D3)})
    out = yahoo.parse_frame(frame, ["SPY"])
    assert [b.date for b in out["SPY"]] == [D1, D2, D3]


def test_parse_single_ticker_flat_frame():
    frame = ticker_df(rows_for(D1, D2))
    out = yahoo.parse_frame(frame, ["SPY"])
    assert [b.date for b in out["SPY"]] == [D1, D2]


def test_parse_flat_frame_is_ambiguous_for_many_tickers():
    frame = ticker_df(rows_for(D1))
    assert yahoo.parse_frame(frame, ["AAA", "BBB"]) == {"AAA": [], "BBB": []}


def test_parse_group_by_column_shape():
    frame = multi_frame({"AAA": rows_for(D1), "BBB": rows_for(D2)})
    frame.columns = frame.columns.swaplevel(0, 1)
    out = yahoo.parse_frame(frame, ["AAA", "BBB"])
    assert [b.date for b in out["AAA"]] == [D1]
    assert [b.date for b in out["BBB"]] == [D2]


def test_parse_drops_nan_and_nonpositive_rows_and_zeroes_nan_volume():
    nan = float("nan")
    frame = multi_frame(
        {
            "AAA": [
                (D1, 10.0, 11.0, 9.0, 10.5, nan),  # NaN volume -> 0
                (D2, nan, 11.0, 9.0, 10.5, 100),  # NaN open -> dropped
                (D3, 10.0, 11.0, 0.0, 10.5, 100),  # non-positive low -> skipped
                (D4, 10.123456, 11.0, 9.0, 10.5, 99.6),  # rounding
            ]
        }
    )
    out = yahoo.parse_frame(frame, ["AAA"])["AAA"]
    assert [b.date for b in out] == [D1, D4]
    assert out[0].volume == 0
    assert out[1].open == Decimal("10.1235")
    assert out[1].volume == 100


def test_parse_tz_aware_index_keeps_exchange_date():
    frame = ticker_df(rows_for(D1, D2))
    frame.index = frame.index.tz_localize("America/New_York")
    out = yahoo.parse_frame(frame, ["AAA"])["AAA"]
    assert [b.date for b in out] == [D1, D2]


def test_parse_absent_or_all_nan_ticker_is_empty():
    frame = multi_frame({"AAA": rows_for(D1), "DEAD": []})
    out = yahoo.parse_frame(frame, ["AAA", "DEAD", "GONE"])
    assert out["DEAD"] == [] and out["GONE"] == []
    assert yahoo.parse_frame(None, ["AAA"]) == {"AAA": []}
    assert yahoo.parse_frame(pd.DataFrame(), ["AAA"]) == {"AAA": []}


def test_download_maps_symbols_both_ways():
    fake = FakeYahoo({"BRK-B": rows_for(D1)})
    out = yahoo.download(["BRK.B", "brk.b"], D1, D4, downloader=fake)
    assert fake.calls == [["BRK-B"]]
    assert list(out) == ["BRK.B"]
    assert out["BRK.B"][0].symbol == "BRK.B"


# ------------------------------------------- yahoo.py: real downloader wrapper


def test_yf_download_turns_logged_rate_limit_into_exception(monkeypatch):
    import yfinance

    def fake_download(**kwargs):
        assert kwargs["auto_adjust"] is False and kwargs["group_by"] == "ticker"
        assert kwargs["threads"] is False and kwargs["actions"] is False
        logging.getLogger("yfinance").error(
            "['SPY']: YFRateLimitError('Too Many Requests. Rate limited. Try after a while.')"
        )
        return multi_frame({"SPY": []})

    monkeypatch.setattr(yfinance, "download", fake_download)
    with pytest.raises(yahoo.RateLimited):
        yahoo.yf_download(["SPY"], D1, D4)


def test_yf_download_turns_raised_rate_limit_into_exception(monkeypatch):
    import yfinance
    from yfinance.exceptions import YFRateLimitError

    def fake_download(**kwargs):
        raise YFRateLimitError()

    monkeypatch.setattr(yfinance, "download", fake_download)
    with pytest.raises(yahoo.RateLimited):
        yahoo.yf_download(["SPY"], D1, D4)


def test_yf_download_other_errors_are_not_rate_limits(monkeypatch):
    import yfinance

    def fake_download(**kwargs):
        logging.getLogger("yfinance").error("['DEAD']: possibly delisted; no timezone found")
        return multi_frame({"DEAD": []})

    monkeypatch.setattr(yfinance, "download", fake_download)
    frame = yahoo.yf_download(["DEAD"], D1, D4)
    assert yahoo.parse_frame(frame, ["DEAD"]) == {"DEAD": []}


# ------------------------------------------------------------- CLI arguments


def parse(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    backfill_cmd.add_arguments(p)
    return p.parse_args(argv)


def test_arguments_defaults_and_symbol_normalisation():
    args = parse([])
    assert args.start == date(2015, 1, 2) and args.end is None
    assert args.batch_size == 40 and args.symbols is None
    args = parse(["--symbols", "brk-b, aapl,AAPL", "--start", "2020-01-02", "--batch-size", "5"])
    assert args.symbols == ["BRK.B", "AAPL"]
    assert args.start == date(2020, 1, 2) and args.batch_size == 5


def test_arguments_reject_bad_input():
    with pytest.raises(SystemExit):
        parse(["--skip-fx", "--fx-only"])
    with pytest.raises(SystemExit):
        parse(["--batch-size", "0"])
    with pytest.raises(SystemExit):
        parse(["--start", "01/02/2015"])


def test_options_default_end_is_last_completed_session():
    now = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
    o = backfill_cmd.options_from_args(parse(["--dry-run"]), now=now)
    assert o.end == dates.last_completed_session(now)
    assert o.dry_run is True and o.symbols is None
    with pytest.raises(backfill_cmd.BackfillError):
        backfill_cmd.options_from_args(parse(["--start", "2030-01-02"]), now=now)


# ----------------------------------------------------------- backfill (DB)


def test_batches_and_resume_skip_ok(pg, the_universe):
    the_universe(["AAA", "BBB", "CCC", "DDD", "SPY"])
    pg.execute(
        "INSERT INTO backfill_log (symbol, status, first_date, last_date, \"rows\") "
        "VALUES ('AAA', 'ok', %s, %s, 3)",
        (D1, D3),
    )
    pg.commit()
    data = {t: rows_for(D1, D2, D3) for t in ["AAA", "BBB", "CCC", "DDD", "SPY"]}
    fake, sleeps = FakeYahoo(data), Sleeps()

    s = backfill_cmd.backfill(pg, opts(batch_size=2), downloader=fake, sleep=sleeps, fetch_fx=no_fx)

    assert fake.calls == [["BBB", "CCC"], ["DDD", "SPY"]]
    assert sleeps == [backfill_cmd.BATCH_PAUSE_S]
    assert s.ok == ["BBB", "CCC", "DDD", "SPY"] and s.skipped == 1
    assert s.rows_written == 12 and s.exit_code() == 0
    assert count(pg, "bars") == 12
    logged = log_rows(pg)
    assert logged["SPY"] == ("ok", D1, D3, 3, None)

    # Second run: everything is logged ok -> nothing fetched.
    fake2 = FakeYahoo(data)
    s2 = backfill_cmd.backfill(pg, opts(batch_size=2), downloader=fake2, sleep=Sleeps(), fetch_fx=no_fx)
    assert fake2.calls == [] and s2.skipped == 5 and s2.rows_written == 0


def test_date_filter_drops_bars_outside_start_end(pg):
    fake = FakeYahoo({"AAA": rows_for(D0, D1, D2, D3, D4)})
    s = backfill_cmd.backfill(pg, opts(symbols=("AAA",)), downloader=fake, sleep=Sleeps(), fetch_fx=no_fx)
    assert s.rows_fetched == 3
    assert [r[1] for r in bar_rows(pg)] == [D1, D2, D3]
    assert log_rows(pg)["AAA"][:4] == ("ok", D1, D3, 3)


def test_dot_symbols_fetched_as_dash_and_stored_as_dot(pg):
    fake = FakeYahoo({"BRK-B": rows_for(D1, base=400.0)})
    backfill_cmd.backfill(pg, opts(symbols=("BRK.B",)), downloader=fake, sleep=Sleeps(), fetch_fx=no_fx)
    assert fake.calls == [["BRK-B"]]
    assert {r[0] for r in bar_rows(pg)} == {"BRK.B"}
    assert "BRK.B" in log_rows(pg)


def test_rate_limit_backoff_then_success(pg):
    fake, sleeps = FakeYahoo({"AAA": rows_for(D1)}, rate_limits=2), Sleeps()
    s = backfill_cmd.backfill(pg, opts(symbols=("AAA",)), downloader=fake, sleep=sleeps, fetch_fx=no_fx)
    assert sleeps == [60.0, 120.0]
    assert len(fake.calls) == 3 and s.ok == ["AAA"]


def test_rate_limit_exhausted_marks_batch_failed_and_continues(pg):
    data = {t: rows_for(D1) for t in ["AAA", "BBB", "CCC"]}
    fake, sleeps = FakeYahoo(data, always_limited={"AAA"}), Sleeps()
    s = backfill_cmd.backfill(
        pg, opts(symbols=("AAA", "BBB", "CCC"), batch_size=2), downloader=fake, sleep=sleeps, fetch_fx=no_fx
    )
    assert sleeps == [60.0, 120.0, 240.0, backfill_cmd.BATCH_PAUSE_S]
    assert fake.calls == [["AAA", "BBB"]] * 4 + [["CCC"]]
    assert s.failed == ["AAA", "BBB"] and s.ok == ["CCC"] and s.exit_code() == 1
    logged = log_rows(pg)
    assert logged["AAA"][0] == "failed" and "rate limited" in logged["AAA"][4]
    assert [r[0] for r in bar_rows(pg)] == ["CCC"]


def test_failed_attempt_never_downgrades_an_ok_symbol(pg):
    fake = FakeYahoo({"AAA": rows_for(D1)})
    backfill_cmd.backfill(pg, opts(symbols=("AAA",)), downloader=fake, sleep=Sleeps(), fetch_fx=no_fx)
    limited = FakeYahoo({}, always_limited={"AAA"})
    backfill_cmd.backfill(pg, opts(symbols=("AAA",)), downloader=limited, sleep=Sleeps(), fetch_fx=no_fx)
    assert log_rows(pg)["AAA"][0] == "ok"
    assert count(pg, "bars") == 1


def test_empty_symbol_retried_individually_then_logged_empty(pg):
    fake, sleeps = FakeYahoo({"AAA": rows_for(D1, D2)}), Sleeps()
    s = backfill_cmd.backfill(
        pg, opts(symbols=("AAA", "DEAD")), downloader=fake, sleep=sleeps, fetch_fx=no_fx
    )
    assert fake.calls == [["AAA", "DEAD"], ["DEAD"]]
    assert sleeps == [backfill_cmd.BATCH_PAUSE_S]
    assert s.ok == ["AAA"] and s.empty == ["DEAD"] and s.exit_code() == 0
    status, first, last, n, error = log_rows(pg)["DEAD"]
    assert (status, first, last, n) == ("empty", None, None, 0)
    assert "no bars" in error


def test_empty_in_batch_recovered_by_individual_retry(pg):
    fake = FakeYahoo({"AAA": rows_for(D1), "BBB": rows_for(D1)}, empty_first={"BBB": 1})
    s = backfill_cmd.backfill(pg, opts(symbols=("AAA", "BBB")), downloader=fake, sleep=Sleeps(), fetch_fx=no_fx)
    assert s.ok == ["AAA", "BBB"] and s.empty == []


def test_retry_failed_reattempts_failed_and_empty_only(pg, the_universe):
    the_universe(["AAA", "BBB", "CCC", "SPY"])
    pg.execute(
        "INSERT INTO backfill_log (symbol, status, \"rows\") VALUES "
        "('AAA', 'ok', 1), ('BBB', 'failed', 0), ('CCC', 'empty', 0)"
    )
    pg.commit()
    data = {t: rows_for(D1) for t in ["AAA", "BBB", "CCC", "SPY"]}

    plain = FakeYahoo(data)
    backfill_cmd.backfill(pg, opts(), downloader=plain, sleep=Sleeps(), fetch_fx=no_fx)
    assert plain.calls == [["SPY"]]

    retry = FakeYahoo(data)
    s = backfill_cmd.backfill(pg, opts(retry_failed=True), downloader=retry, sleep=Sleeps(), fetch_fx=no_fx)
    assert retry.calls == [["BBB", "CCC"]]
    assert s.ok == ["BBB", "CCC"]
    assert log_rows(pg)["BBB"][0] == "ok"


def test_second_run_with_same_args_writes_zero_rows(pg):
    data = {"AAA": rows_for(D1, D2, D3), "BRK-B": rows_for(D1, D2, base=400.0)}
    o = opts(symbols=("AAA", "BRK.B"), skip_fx=False)
    fx_rows = [(D1, Decimal("15500.0000")), (D2, Decimal("15510.5000"))]

    s1 = backfill_cmd.backfill(pg, o, downloader=FakeYahoo(data), sleep=Sleeps(), fetch_fx=lambda a, b: fx_rows)
    before = bar_rows(pg)
    logged_before = log_rows(pg)
    s2 = backfill_cmd.backfill(pg, o, downloader=FakeYahoo(data), sleep=Sleeps(), fetch_fx=lambda a, b: fx_rows)

    assert s1.rows_written == 5 and s1.fx_rows_written == 2
    assert s2.rows_written == 0 and s2.fx_rows_written == 0
    assert bar_rows(pg) == before
    assert log_rows(pg) == logged_before


def test_dry_run_writes_nothing(pg, the_universe):
    the_universe(["AAA", "SPY"])
    data = {"AAA": rows_for(D1, D2), "SPY": rows_for(D1, D2)}
    fx_rows = [(D1, Decimal("15500.0000"))]
    s = backfill_cmd.backfill(
        pg,
        opts(dry_run=True, skip_fx=False),
        downloader=FakeYahoo(data),
        sleep=Sleeps(),
        fetch_fx=lambda a, b: fx_rows,
    )
    assert s.rows_written == 4 and s.fx_rows_written == 1  # computed, then rolled back
    assert count(pg, "bars") == 0
    assert count(pg, "backfill_log") == 0
    assert count(pg, "fx_rates") == 0


def test_demo_purge_runs_before_any_write(pg, monkeypatch):
    events = []
    real_upsert_bars, real_upsert_fx = bars.upsert_bars, fx.upsert_fx

    def fake_purge(conn, dry_run):
        events.append(("purge", dry_run))
        return False

    def spy_upsert_bars(conn, rows):
        events.append(("bars",))
        return real_upsert_bars(conn, rows)

    def spy_upsert_fx(conn, rows):
        events.append(("fx",))
        return real_upsert_fx(conn, rows)

    monkeypatch.setattr(demo, "purge_demo_if_needed", fake_purge)
    monkeypatch.setattr(bars, "upsert_bars", spy_upsert_bars)
    monkeypatch.setattr(fx, "upsert_fx", spy_upsert_fx)

    backfill_cmd.backfill(
        pg,
        opts(symbols=("AAA",), skip_fx=False),
        downloader=FakeYahoo({"AAA": rows_for(D1)}),
        sleep=Sleeps(),
        fetch_fx=lambda a, b: [(D1, Decimal("15500"))],
    )
    assert events == [("purge", False), ("bars",), ("fx",)]


def test_empty_universe_fails_clearly_before_any_write(pg, the_universe, monkeypatch):
    the_universe(["SPY"])
    purged = []
    monkeypatch.setattr(demo, "purge_demo_if_needed", lambda conn, dry_run: purged.append(1))
    fake = FakeYahoo({})
    with pytest.raises(backfill_cmd.BackfillError, match="universe refresh"):
        backfill_cmd.backfill(pg, opts(), downloader=fake, sleep=Sleeps(), fetch_fx=no_fx)
    assert fake.calls == [] and purged == []


def test_fx_only_loads_fx_and_skips_bars(pg, monkeypatch):
    def no_universe(conn, since):
        raise AssertionError("universe must not be read with --fx-only")

    monkeypatch.setattr(universe, "all_symbols", no_universe)
    fake = FakeYahoo({})
    s = backfill_cmd.backfill(
        pg,
        opts(fx_only=True, skip_fx=False),
        downloader=fake,
        sleep=Sleeps(),
        fetch_fx=lambda a, b: [(D1, Decimal("15500")), (D2, Decimal("15600"))],
    )
    assert fake.calls == [] and s.fx_rows_written == 2
    assert count(pg, "fx_rates") == 2 and count(pg, "bars") == 0


def test_fx_failure_is_reported_not_raised(pg):
    def broken(start, end):
        raise RuntimeError("frankfurter down")

    s = backfill_cmd.backfill(
        pg,
        opts(symbols=("AAA",), skip_fx=False),
        downloader=FakeYahoo({"AAA": rows_for(D1)}),
        sleep=Sleeps(),
        fetch_fx=broken,
    )
    assert s.ok == ["AAA"] and "frankfurter down" in s.fx_error and s.exit_code() == 1
    assert count(pg, "bars") == 1


def test_summary_reports_counts_and_table_size(pg):
    s = backfill_cmd.backfill(
        pg, opts(symbols=("AAA", "DEAD")), downloader=FakeYahoo({"AAA": rows_for(D1)}),
        sleep=Sleeps(), fetch_fx=no_fx,
    )
    assert s.bars_bytes is not None and s.bars_bytes > 0
    text = backfill_cmd.format_summary(s, opts(symbols=("AAA", "DEAD")))
    assert "1 ok, 1 empty, 0 failed" in text
    assert "empty: DEAD" in text
    assert "bars table:" in text
```
**Impact:** The DB tests skip cleanly when `PG_TEST_URL` is unset (A10). The pure tests always run.

### Step 4: Live verification of the yfinance frame shape (implementation-time check, no code change)
**File:** none (run from `engine/`)
**Change:** After Steps 1–3 pass, confirm that the installed yfinance still produces the shape
`parse_frame` expects, using a tiny live call:
```bash
cd engine && .venv/bin/python - <<'PY'
from datetime import date
import yfinance
from seer_engine import yahoo
print("yfinance", yfinance.__version__)
frame = yahoo.yf_download(["SPY", "AAPL", "BRK-B"], date(2026, 9, 24), date(2026, 10, 3))
print(type(frame.columns).__name__, frame.columns.names, frame.index.dtype, frame.index.tz)
out = yahoo.download(["SPY", "AAPL", "BRK.B", "ZZZZNOPE"], date(2026, 9, 24), date(2026, 10, 3))
for symbol, rows in out.items():
    print(symbol, len(rows), rows[-1] if rows else None)
PY
```
Expected (observed while planning): `MultiIndex ['Ticker', 'Price'] datetime64[s] None`. SPY, AAPL
and BRK.B each have 7 bars, the last dated 2026-10-02 (SPY close `769.6400`). `ZZZZNOPE 0 None`.
If the columns or index differ, fix `parse_frame`/`frame_to_bars`, add a test that reproduces the
new shape, and record it in the phase notes.

Optionally, against the throwaway `PG_TEST_URL` database (never Neon in this phase), run an end-to-end
dry-run smoke test:
`SEER_ENV_FILE=/nonexistent DATABASE_URL_UNPOOLED=$PG_TEST_URL .venv/bin/python -m seer_engine --dry-run backfill --symbols SPY,BRK.B --start 2026-09-01 --skip-fx`
It should print a summary with `2 ok` and exit 0. The test database must already be migrated
(`SEER_ENV_FILE=/nonexistent DATABASE_URL_UNPOOLED=$PG_TEST_URL .venv/bin/python -m seer_engine migrate`). `SEER_ENV_FILE=/nonexistent` keeps `.env.local` (which holds the Neon URL) out of this phase.

## Verification

**Build:** `cd engine && .venv/bin/python -c "import seer_engine.yahoo, seer_engine.commands.backfill" && .venv/bin/python -m seer_engine backfill --help`
**Tests:** with phase 1's test database (`docker start seer-pg`, see phase 1 Verification): `cd engine && PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres .venv/bin/pytest tests/test_backfill.py -q -rs`. Then run the full suite: `PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres .venv/bin/pytest tests -q -rs`.
**Manual check:** Step 4's live frame-shape check. `python -m seer_engine --help` lists `backfill`.
**Exit criteria:**
- `pytest tests/test_backfill.py` reports 32 passed with `PG_TEST_URL` set (14 passed and 18 skipped without it), and the full `engine/tests` suite stays green.
- `backfill --help` shows `--start`, `--end`, `--symbols`, `--retry-failed`, `--skip-fx`/`--fx-only` (mutually exclusive) and `--batch-size`.
- The live check in Step 4 shows dot-form keys and the expected bar counts.

## Handoffs

- **Phase 5 (runbook + live run), R1:** run order on Neon is `migrate` → `universe refresh` →
  `backfill` → `backfill --retry-failed` (once, for rate-limited symbols) → record the summary
  (`ok/empty/failed` counts, the `empty` list as the "can't fetch" log for §6.2, and
  `pg_total_relation_size('bars')`). Exit code 1 means some symbols `failed` (retry) or FX failed
  (`backfill --fx-only`). Exit code 2 means the universe is empty (or bad arguments). `empty`
  symbols (delisted/acquired, ~145 expected per phase 2) do **not** affect the exit code, so a
  normal full backfill exits 0. The `backfill.yml` `workflow_dispatch` exposes `start`, `symbols`
  (comma-separated, dot form), `retry_failed`, `batch_size` and `dry_run` inputs (reconciled into
  phase 5 Step 4). Resume passes on a later day should pin `--end` to the first pass's end date so
  every symbol ends on the same session (reconciled into phase 5 Step 12).
- **Phase 5, R1 (risk to document in the runbook):** Neon free-tier compute auto-suspends after
  about 5 minutes idle, which closes open connections. A full rate-limit backoff (60+120+240 s =
  7 min with no DB activity) can therefore make the next batch's transaction fail with
  `psycopg.OperationalError`. The command then exits with a traceback, having lost at most the
  in-flight batch. The remedy is to re-run the same command, which resumes from `backfill_log`.
  Reconnect logic was deliberately not built; resumability is the designed answer.
- **Phase 5, R1:** symbols that join an index after the backfill have bars only from when the
  nightly starts covering them. After a `universe refresh` that adds names, run
  `backfill --symbols NEW1,NEW2`.
- **Phase 4 (nightly), R3/R4 (reconciled, consistent):** the backfill records no splits (see "Split
  timing"). Bars it loaded are already adjusted for every split up to its run date. Phase 4 never
  re-applies such a split: it only fetches splits for sessions after SPY's latest stored bar (that
  is, after the backfill's end), and its deterministic guard treats a symbol whose latest stored bar
  is on or after the split's execution date as already adjusted, before the price-ratio heuristic
  (`|ln f| ≥ ln 1.25`) is consulted. If the backfill is re-run after a split, yfinance's newly
  adjusted values overwrite history; those values are consistent.
- **Phase 1, R4/R6:** contract assumptions A1–A12 above, especially A4 (`db.transaction` commits at
  top level), A9 (`backfill_log."rows"` column name and nullable `first_date`/`last_date`/`error`)
  and A10 (the `pg` fixture yields an idle connection).

## Rollback

Delete the three new files (`git revert` of the phase commit). Nothing else references them, and
command discovery simply stops listing `backfill`. Data written by a real run, if any:
`TRUNCATE bars, fx_rates, backfill_log;` (phase 5's rollback covers restoring demo data).

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

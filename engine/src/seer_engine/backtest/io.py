"""Impure edge of the backtest: read the database once, read the vendored SPY dividends,
write the report files (v1's ``write_report``, the walk-forward ``write_wf_report``, Strategy B's
``write_b_report``) and Strategy B's model artifact (``write_model_artifact``).

The only module in ``seer_engine.backtest`` that touches the database or the filesystem;
``test_strategy_purity.py`` skips it by name. Read-only: ``load_market`` runs one
``REPEATABLE READ, READ ONLY`` transaction and always ends it with a rollback.

Bars are loaded with one streamed ``COPY (SELECT ... ORDER BY symbol, date) TO STDOUT``
into a pandas frame, which is cached as a pickle under ``cache_dir`` named
``bars-<max(date)>-<count(*)>.pkl``. A cheap ``count(*), max(date)`` query decides whether
the cache is still valid, so a grid of runs never re-downloads the ~180 MB table.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterable
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path

import numpy as np
import pandas as pd
import psycopg
from psycopg.pq import TransactionStatus

from seer_engine import config
from seer_engine.backtest import b_report, wf_report
from seer_engine.backtest.benchmark import Dividend, parse_dividends
from seer_engine.backtest.market import Market, Membership
from seer_engine.backtest.report import (
    BacktestReport,
    equity_csv,
    equity_svg,
    render_markdown,
    report_stem,
)
from seer_engine.prices import to_decimal
from seer_engine.strategies import b_model
from seer_engine.strategies.base import History

log = logging.getLogger(__name__)

CACHE_DIR = config.REPO_ROOT / "engine" / ".cache"
DIVIDENDS_CSV = config.REPO_ROOT / "engine" / "data" / "spy_dividends.csv"
MODELS_DIR = config.REPO_ROOT / "engine" / "data" / "models"

BAR_COLUMNS = ("symbol", "date", "open", "high", "low", "close", "volume")
FLOAT_COLUMNS = ("open", "high", "low", "close", "volume")
BARS_COPY_SQL = (
    "COPY (SELECT symbol, date, open, high, low, close, volume FROM bars "
    "ORDER BY symbol, date) TO STDOUT"
)
CACHE_GLOB = "bars-*.pkl"

Interval = tuple[str, date, date | None]


class LoadError(RuntimeError):
    """The database cannot back a backtest (no bars, or an inconsistent load)."""


# ---- database ------------------------------------------------------------------------------


def load_market(
    conn: psycopg.Connection,
    *,
    cache_dir: Path = CACHE_DIR,
    refresh: bool = False,
) -> tuple[Market, int]:
    """(Market, number of bar rows) from ``bars``, ``universe`` and ``fx_rates``.

    ``conn`` must have autocommit off and no transaction in progress. Bars come from the
    cache in ``cache_dir`` when its name matches the table's ``count(*)`` and ``max(date)``
    (``refresh`` forces a re-download); universe and fx are always read fresh (small).
    Raises LoadError when ``bars`` is empty.
    """
    if conn.info.transaction_status != TransactionStatus.IDLE:
        raise ValueError("load_market needs a connection with no transaction in progress")
    try:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        rows, max_date = bars_fingerprint(conn)
        if rows == 0 or max_date is None:
            raise LoadError("the bars table is empty; run `backfill` first")
        frame = _bars_frame(conn, Path(cache_dir), rows, max_date, refresh)
        intervals = read_intervals(conn)
        fx_rows = read_fx(conn)
    finally:
        conn.rollback()
    history = histories_from_frame(frame)
    market = Market(history=history, membership=Membership(intervals=intervals), fx=fx_rows)
    log.info(
        "market: %d bar rows through %s, %d symbols with bars, %d membership intervals, %d fx rows",
        rows,
        max_date,
        len(history),
        len(intervals),
        len(fx_rows),
    )
    return market, rows


def bars_fingerprint(conn: psycopg.Connection) -> tuple[int, date | None]:
    """(count(*), max(date)) of ``bars``: the cache key."""
    row = conn.execute("SELECT count(*), max(date) FROM bars").fetchone()
    return int(row[0]), row[1]


def cache_path(cache_dir: Path, rows: int, max_date: date) -> Path:
    return Path(cache_dir) / f"bars-{max_date.isoformat()}-{rows}.pkl"


def read_bars_frame(conn: psycopg.Connection) -> pd.DataFrame:
    """Every bar, ordered by (symbol, date), via one streamed COPY ... TO STDOUT.

    Columns: symbol (str), date (datetime64), open/high/low/close (float64, correctly
    rounded from the numeric text), volume (int64).
    """
    buf = BytesIO()
    with conn.cursor() as cur:
        cur.execute("SET LOCAL datestyle TO 'ISO, YMD'")
        with cur.copy(BARS_COPY_SQL) as copy:
            for chunk in copy:
                buf.write(chunk)
    if buf.tell() == 0:
        raise LoadError("COPY of bars returned no rows")
    buf.seek(0)
    frame = pd.read_csv(
        buf,
        sep="\t",
        header=None,
        names=list(BAR_COLUMNS),
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
    frame["date"] = pd.to_datetime(frame["date"], format="%Y-%m-%d")
    return frame


def read_intervals(conn: psycopg.Connection) -> tuple[Interval, ...]:
    """Membership intervals [start, end) per symbol, both indices merged."""
    rows = conn.execute(
        "SELECT symbol, start_date, end_date FROM universe ORDER BY symbol, start_date"
    ).fetchall()
    return merge_intervals((r[0], r[1], r[2]) for r in rows)


def merge_intervals(rows: Iterable[Interval]) -> tuple[Interval, ...]:
    """Union of overlapping or touching [start, end) intervals per symbol (end None = open),
    sorted by (symbol, start). Membership in either index counts once."""
    out: list[Interval] = []
    for symbol, start, end in sorted(rows, key=lambda r: (r[0], r[1])):
        if out and out[-1][0] == symbol:
            _, cur_start, cur_end = out[-1]
            if cur_end is None or start <= cur_end:
                merged_end = None if cur_end is None or end is None else max(cur_end, end)
                out[-1] = (symbol, cur_start, merged_end)
                continue
        out.append((symbol, start, end))
    return tuple(out)


def read_fx(conn: psycopg.Connection) -> tuple[tuple[date, Decimal], ...]:
    """Every (date, usd_idr) row, ascending, as 4-dp Decimals."""
    rows = conn.execute("SELECT date, usd_idr FROM fx_rates ORDER BY date").fetchall()
    return tuple((r[0], to_decimal(r[1])) for r in rows)


# ---- cache ---------------------------------------------------------------------------------


def _bars_frame(
    conn: psycopg.Connection, cache_dir: Path, rows: int, max_date: date, refresh: bool
) -> pd.DataFrame:
    path = cache_path(cache_dir, rows, max_date)
    if not refresh and path.is_file():
        cached = _read_cache(path, rows)
        if cached is not None:
            log.info("bars cache hit: %s", path)
            return cached
    log.info(
        "bars cache %s: streaming %d rows from the database",
        "refresh" if refresh else "miss",
        rows,
    )
    frame = read_bars_frame(conn)
    if len(frame) != rows:
        raise LoadError(f"COPY returned {len(frame)} bar rows but count(*) said {rows}")
    _write_cache(path, frame)
    return frame


def _read_cache(path: Path, rows: int) -> pd.DataFrame | None:
    try:
        frame = pd.read_pickle(path, compression=None)
    except Exception as e:  # noqa: BLE001 - a broken cache is re-downloaded, never fatal
        log.warning("bars cache %s unreadable (%s: %s); re-downloading", path, type(e).__name__, e)
        return None
    if (
        not isinstance(frame, pd.DataFrame)
        or len(frame) != rows
        or tuple(frame.columns) != BAR_COLUMNS
    ):
        log.warning("bars cache %s has the wrong shape; re-downloading", path)
        return None
    return frame


def _write_cache(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    frame.to_pickle(tmp, compression=None)
    os.replace(tmp, path)
    log.info("bars cache written: %s", path)
    for old in sorted(path.parent.glob(CACHE_GLOB)):
        if old != path:
            old.unlink(missing_ok=True)
            log.info("removed stale bars cache %s", old.name)


# ---- frame -> histories --------------------------------------------------------------------


def histories_from_frame(frame: pd.DataFrame) -> dict[str, History]:
    """One History per symbol (float64 arrays, datetime64[D] dates), sorted by symbol.

    ``frame`` must be ordered by (symbol, date) as the COPY returns it. Raises LoadError
    when a symbol's rows are not contiguous or its dates are not strictly ascending.
    """
    if len(frame) == 0:
        return {}
    symbols = frame["symbol"].to_numpy(dtype=object)
    days = frame["date"].to_numpy().astype("datetime64[D]")
    cols = {c: np.ascontiguousarray(frame[c].to_numpy(dtype=np.float64)) for c in FLOAT_COLUMNS}
    starts = np.concatenate(([0], np.flatnonzero(symbols[1:] != symbols[:-1]) + 1))
    ends = np.append(starts[1:], len(symbols))
    out: dict[str, History] = {}
    for s, e in zip(starts.tolist(), ends.tolist()):
        symbol = str(symbols[s])
        if symbol in out:
            raise LoadError(f"bars for {symbol} are not contiguous; expected ORDER BY symbol, date")
        d = days[s:e]
        if len(d) > 1 and not bool(np.all(d[1:] > d[:-1])):
            raise LoadError(f"bars for {symbol} are not strictly ascending by date")
        out[symbol] = History(
            symbol=symbol,
            dates=d,
            open=cols["open"][s:e],
            high=cols["high"][s:e],
            low=cols["low"][s:e],
            close=cols["close"][s:e],
            volume=cols["volume"][s:e],
        )
    return dict(sorted(out.items()))


# ---- files ---------------------------------------------------------------------------------


def read_dividends(path: Path = DIVIDENDS_CSV) -> tuple[Dividend, ...]:
    """The vendored SPY dividends (``ex_date,amount_usd``), parsed by benchmark.parse_dividends."""
    return parse_dividends(Path(path).read_text(encoding="utf-8"))


def write_report(out_dir: Path, report: BacktestReport) -> list[Path]:
    """Write <stem>.md, <stem>-equity.csv, <stem>-equity.svg into ``out_dir`` (created if
    needed) with LF line endings; return the paths in that order. All three are rendered
    before any is written, so a render error leaves no partial set."""
    out_dir = Path(out_dir)
    stem = report_stem(report.data_end)
    files = (
        (f"{stem}.md", render_markdown(report)),
        (f"{stem}-equity.csv", equity_csv(report)),
        (f"{stem}-equity.svg", equity_svg(report)),
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for name, text in files:
        path = out_dir / name
        path.write_text(text, encoding="utf-8", newline="\n")
        paths.append(path)
    return paths


def write_wf_report(out_dir: Path, report: wf_report.WalkForwardReport) -> list[Path]:
    """Write the walk-forward report set into ``out_dir`` (created if needed) with LF line
    endings and return the paths in this order: <stem>.md, <stem>-equity.csv,
    <stem>-equity.svg, <stem>-variants.svg, <stem>-grid.csv. All five are rendered before any
    is written, so a render error leaves no partial set."""
    out_dir = Path(out_dir)
    stem = wf_report.report_stem(report.data_end)
    files = (
        (f"{stem}.md", wf_report.render_markdown(report)),
        (f"{stem}-equity.csv", wf_report.equity_csv(report)),
        (f"{stem}-equity.svg", wf_report.equity_svg(report)),
        (f"{stem}-variants.svg", wf_report.variants_svg(report)),
        (f"{stem}-grid.csv", wf_report.grid_csv(report)),
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for name, text in files:
        path = out_dir / name
        path.write_text(text, encoding="utf-8", newline="\n")
        paths.append(path)
    return paths


def write_b_report(out_dir: Path, report: b_report.BReport) -> list[Path]:
    """Write Strategy B's walk-forward report set into ``out_dir`` (created if needed) with LF
    line endings and return the paths in this order: <stem>.md, <stem>-equity.csv,
    <stem>-equity.svg. All three are rendered before any is written, so a render error leaves
    no partial set."""
    out_dir = Path(out_dir)
    stem = b_report.report_stem(report.data_end)
    files = (
        (f"{stem}.md", b_report.render_markdown(report)),
        (f"{stem}-equity.csv", b_report.equity_csv(report)),
        (f"{stem}-equity.svg", b_report.equity_svg(report)),
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for name, text in files:
        path = out_dir / name
        path.write_text(text, encoding="utf-8", newline="\n")
        paths.append(path)
    return paths


def write_model_artifact(model_dir: Path, data_end: date, model: b_model.BModel) -> tuple[Path, str]:
    """Write ``b_model.dumps(model)`` to ``<model_dir>/<data_end>-strategy-b.pkl`` (the directory
    is created if needed) and return ``(path, sha256 hex of the written bytes)``.

    The bytes are serialized first and land through a temporary file plus ``os.replace``, so a
    failure never leaves a truncated artifact. Re-writing the same model gives the same bytes.
    """
    if isinstance(data_end, datetime) or not isinstance(data_end, date):
        raise TypeError(f"data_end must be a date, got {type(data_end).__name__}")
    if not isinstance(model, b_model.BModel):
        raise TypeError(f"model must be a b_model.BModel, got {type(model).__name__}")
    data = b_model.dumps(model)
    model_dir = Path(model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)
    path = model_dir / f"{data_end.isoformat()}-strategy-b.pkl"
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)
    return path, b_model.sha256(data)

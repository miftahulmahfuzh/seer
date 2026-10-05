"""Impure edge of the backtest: read the database once, read the vendored SPY dividends,
write the report files (v1's ``write_report``, the walk-forward ``write_wf_report``, Strategy B's
``write_b_report``, P7a's ``write_dev_report``) and Strategy B's model artifact (``write_model_artifact``).

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

from seer_engine import config, db
from seer_engine.backtest import b_report, dev_report, wf_report
from seer_engine.backtest.benchmark import Dividend, parse_dividends
from seer_engine.backtest.market import EMPTY_FUNDAMENTALS, Market, Membership
from seer_engine.backtest.report import (
    BacktestReport,
    equity_csv,
    equity_svg,
    render_markdown,
    report_stem,
)
from seer_engine.fundamentals import FACT_COLUMNS, Fact, FundamentalPanel as Panel
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
BARS_COPY_SINCE_SQL = (
    "COPY (SELECT symbol, date, open, high, low, close, volume FROM bars "
    "WHERE date >= %s ORDER BY symbol, date) TO STDOUT"
)
CACHE_GLOB = "bars-*.pkl"

FACTS_TABLE = "fundamental_facts"
MAP_TABLE = "ticker_cik"

# Phase 5 owns the column order; this is its tuple, not a copy of it. If the two ever drifted,
# facts_from_frame's positional unpack would silently mis-assign form/fy/fp.
FACTS_COLUMNS = FACT_COLUMNS

# fundamental_facts is keyed by CIK and has NO symbol column (C1): one ticker names several
# companies over time, so a symbol column would let a recycled ticker smear two filers
# together. ticker_cik carries the dated bridge and this join is where a fact acquires the
# symbol phase 5's panel is keyed by. It is a JOIN AGAINST ticker_cik, NEVER against bars:
# invariant 7 forbids making a bar row a precondition for a fact, and the 133 delisted
# ever-members have facts and no bars.
#
# The join legitimately fans out: a share-class pair (GOOG/GOOGL, FOX/FOXA, NWS/NWSA, UA/UAA,
# CMCSA/CMCSK, BATRA/BATRK) is one CIK and two symbols, so one fact row becomes two panel rows.
# That is why facts_fingerprint counts over the same join.
#
# period_start = period_end IS the stored encoding of "instantaneous" (C2); it goes out as ''
# so facts_from_frame turns it back into None, which is what phase 5's Fact means by an
# instant. Other dates go out as to_char text and nullable columns as coalesce'd text, so the
# COPY stream never carries a \N for na_filter=False to mistake for the two-character string
# "\N". The ORDER BY is a total order over the fact identity, so the frame -- and therefore
# the pickle -- is byte-stable.
_FACTS_FROM = (
    "FROM fundamental_facts f "
    "JOIN ticker_cik m ON m.cik = f.cik "
    "  AND f.filed >= m.start_date "
    "  AND (m.end_date IS NULL OR f.filed < m.end_date) "
)
FACTS_COPY_SQL = (
    "COPY (SELECT m.symbol, f.taxonomy, f.tag, f.unit, "
    "CASE WHEN f.period_start = f.period_end THEN '' "
    "     ELSE to_char(f.period_start, 'YYYY-MM-DD') END AS period_start, "
    "to_char(f.period_end, 'YYYY-MM-DD') AS period_end, "
    "f.val, f.accn, f.form, "
    "coalesce(f.fy::text, '') AS fy, "
    "coalesce(f.fp, '') AS fp, "
    "to_char(f.filed, 'YYYY-MM-DD') AS filed "
    + _FACTS_FROM
    + "ORDER BY m.symbol, f.taxonomy, f.tag, f.unit, f.period_end, f.period_start, f.filed, f.accn"
    ") TO STDOUT"
)
FACTS_COUNT_SQL = "SELECT count(*), max(f.filed) " + _FACTS_FROM
FACTS_CACHE_GLOB = "fundamentals-*.pkl"

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

    ``fundamental_facts`` is read the same way, into ``market.fundamentals``, and is optional:
    a missing table or an empty one gives ``EMPTY_FUNDAMENTALS`` and no error, so a database
    that has not run ``005_fundamentals.sql`` still backs a backtest unchanged.
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
        panel = load_panel(conn, cache_dir=Path(cache_dir), refresh=refresh)
    finally:
        conn.rollback()
    history = histories_from_frame(frame)
    market = Market(
        history=history,
        membership=Membership(intervals=intervals),
        fx=fx_rows,
        fundamentals=panel,
    )
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


def read_bars_frame(conn: psycopg.Connection, *, since: date | None = None) -> pd.DataFrame:
    """Every bar (or, with ``since``, every bar dated on or after it), ordered by (symbol, date),
    via one streamed COPY ... TO STDOUT.

    Columns: symbol (str), date (datetime64), open/high/low/close (float64, correctly
    rounded from the numeric text), volume (int64). ``since`` None (the default) runs
    ``BARS_COPY_SQL`` exactly as before; a date runs ``BARS_COPY_SINCE_SQL`` with it bound.
    """
    if since is not None and (isinstance(since, datetime) or not isinstance(since, date)):
        raise TypeError(f"since must be a date or None, got {type(since).__name__}")
    buf = BytesIO()
    with conn.cursor() as cur:
        cur.execute("SET LOCAL datestyle TO 'ISO, YMD'")
        copy_cm = cur.copy(BARS_COPY_SQL) if since is None else cur.copy(BARS_COPY_SINCE_SQL, (since,))
        with copy_cm as copy:
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


# ---- fundamentals -------------------------------------------------------------------------


def load_panel(
    conn: psycopg.Connection,
    *,
    cache_dir: Path = CACHE_DIR,
    refresh: bool = False,
) -> Panel:
    """The point-in-time fact panel from ``fundamental_facts``.

    Runs inside the caller's transaction and never commits or rolls back (``load_market`` owns
    the ``REPEATABLE READ, READ ONLY`` transaction and its rollback). Returns
    ``EMPTY_FUNDAMENTALS`` when either ``fundamental_facts`` or ``ticker_cik`` is missing, or
    when the join yields no rows -- the state of every database that has not applied
    ``db/migrations/005_fundamentals.sql``, and of one that has applied it but not yet run
    ``fundamentals``. Otherwise the facts come from the pickle in ``cache_dir`` named for
    ``(count(*), max(filed))`` over the join, or from one streamed COPY when that pickle is
    absent or ``refresh`` is set.
    """
    rows, max_filed = facts_fingerprint(conn)
    if rows == 0 or max_filed is None:
        log.info("fundamentals: no rows; the market gets an empty panel")
        return EMPTY_FUNDAMENTALS
    frame = _facts_frame(conn, Path(cache_dir), rows, max_filed, refresh)
    panel = Panel.from_facts(facts_from_frame(frame))  # FundamentalPanel.from_facts
    log.info("fundamentals: %d facts filed through %s", rows, max_filed)
    return panel


def read_facts(*, conninfo: str | None = None) -> tuple[Fact, ...]:
    """Every fact ``load_panel`` would see, as plain values, over a connection opened here.

    This lives in ``io.py`` -- the only module in ``seer_engine.backtest`` that touches the
    database, and the one ``test_strategy_purity.py`` skips by name -- rather than in
    ``commands/research_store.py``, which is where the plan first put it.
    ``test_research_store.py::test_no_neon_and_no_database_url_needed`` AST-scans **both**
    ``research.py`` and the ``research_store`` command and fails either one that names
    ``seer_engine.db`` or ``psycopg``; that test is byte-identical shipped code this phase must
    leave green, so the connection moves one module down instead of into the command. The
    "Never Neon" invariant it protects is unaffected: ``research.py`` still imports nothing from
    ``seer_engine.db`` and ``build_store`` still takes a plain sequence of facts.

    Read-only and self-contained: it opens the connection, runs the same
    ``facts_fingerprint`` + ``read_facts_frame`` + ``facts_from_frame`` trio ``load_panel`` uses
    -- so the facts it returns equal the panel's by construction -- and always rolls back.
    Returns () when either table is missing or the join is empty.
    """
    with db.connect(conninfo) as conn:  # None -> DATABASE_URL_UNPOOLED
        try:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            rows, max_filed = facts_fingerprint(conn)
            if rows == 0 or max_filed is None:
                log.warning(
                    "fundamentals: the database has no fundamental_facts rows joinable to "
                    "ticker_cik; run `python -m seer_engine fundamentals` first"
                )
                return ()
            facts = facts_from_frame(read_facts_frame(conn))
        finally:
            conn.rollback()
    log.info("fundamentals: %d facts read from the database, filed through %s", len(facts), max_filed)
    return facts


def facts_fingerprint(conn: psycopg.Connection) -> tuple[int, date | None]:
    """(count(*), max(filed)) over the ``fundamental_facts`` x ``ticker_cik`` join: the cache key.

    Counted over the **join**, not over ``fundamental_facts`` alone, for two reasons: the join
    fans a share-class CIK out to two symbols so the joined count is the real panel row count
    that ``_facts_frame`` checks against, and re-vendoring ``ticker_cik`` must invalidate the
    pickle even when no fact changed.

    (0, None) when **either** table is missing. The existence test is ``to_regclass``, which
    returns NULL instead of raising, because an ``UndefinedTable`` error would abort
    ``load_market``'s read-only transaction and there is no savepoint to recover it from.
    """
    for table in (FACTS_TABLE, MAP_TABLE):
        if conn.execute("SELECT to_regclass(%s)", (table,)).fetchone()[0] is None:
            return 0, None
    row = conn.execute(FACTS_COUNT_SQL).fetchone()
    return int(row[0]), row[1]


def facts_cache_path(cache_dir: Path, rows: int, max_filed: date) -> Path:
    return Path(cache_dir) / f"fundamentals-{max_filed.isoformat()}-{rows}.pkl"


def read_facts_frame(conn: psycopg.Connection) -> pd.DataFrame:
    """Every ``fundamental_facts`` row, in ``FACTS_COPY_SQL`` order, via one streamed COPY.

    Columns: ``FACTS_COLUMNS`` (phase 5's ``FACT_COLUMNS``). Every column is str except ``val``
    (float64, correctly rounded from the numeric text); ``fy`` and ``fp`` are "" where the
    column is NULL, and ``period_start`` is "" where it equals ``period_end`` -- the stored
    encoding of an instantaneous fact (C2). None of the text columns can hold a tab or a
    newline -- they are SEC tags, units, accession numbers, form types and tickers -- so the
    TSV needs no escaping pass.
    """
    buf = BytesIO()
    with conn.cursor() as cur:
        with cur.copy(FACTS_COPY_SQL) as copy:
            for chunk in copy:
                buf.write(chunk)
    if buf.tell() == 0:
        raise LoadError("COPY of fundamental_facts returned no rows")
    buf.seek(0)
    return pd.read_csv(
        buf,
        sep="\t",
        header=None,
        names=list(FACTS_COLUMNS),
        dtype={
            "symbol": str,
            "taxonomy": str,
            "tag": str,
            "unit": str,
            "period_start": str,
            "period_end": str,
            "val": np.float64,
            "accn": str,
            "form": str,
            "fy": str,
            "fp": str,
            "filed": str,
        },
        na_filter=False,
        float_precision="round_trip",
        engine="c",
    )


def facts_from_frame(frame: pd.DataFrame) -> tuple[Fact, ...]:
    """One ``fundamentals.Fact`` per frame row, in frame order.

    The frame's dates are ISO strings and its NULLs are empty strings (see ``FACTS_COPY_SQL``);
    this is the one place that turns them back into ``date`` and ``None``. ``filed`` is never
    optional: it is the no-look-ahead boundary, so a row without it is a loader bug, not a
    tolerable gap.
    """
    if len(frame) == 0:
        return ()
    out: list[Fact] = []
    for row in frame.itertuples(index=False, name=None):
        # FACT_COLUMNS order: ..., val, accn, FORM, FY, FP, filed. Phase 5 owns it.
        symbol, taxonomy, tag, unit, period_start, period_end, val, accn, form, fy, fp, filed = row
        if not filed:
            raise LoadError(f"{symbol} {tag} {accn}: a fact row has no filed date")
        out.append(
            Fact(
                symbol=str(symbol),
                taxonomy=str(taxonomy),
                tag=str(tag),
                unit=str(unit),
                period_start=date.fromisoformat(period_start) if period_start else None,
                period_end=date.fromisoformat(period_end),
                val=float(val),
                accn=str(accn),
                fy=int(fy) if fy else None,
                fp=str(fp) or None,
                form=str(form),
                filed=date.fromisoformat(filed),
            )
        )
    return tuple(out)


def _facts_frame(
    conn: psycopg.Connection, cache_dir: Path, rows: int, max_filed: date, refresh: bool
) -> pd.DataFrame:
    path = facts_cache_path(cache_dir, rows, max_filed)
    if not refresh and path.is_file():
        cached = _read_facts_cache(path, rows)
        if cached is not None:
            log.info("fundamentals cache hit: %s", path)
            return cached
    log.info(
        "fundamentals cache %s: streaming %d rows from the database",
        "refresh" if refresh else "miss",
        rows,
    )
    frame = read_facts_frame(conn)
    if len(frame) != rows:
        raise LoadError(f"COPY returned {len(frame)} fact rows but count(*) said {rows}")
    _write_facts_cache(path, frame)
    return frame


def _read_facts_cache(path: Path, rows: int) -> pd.DataFrame | None:
    try:
        frame = pd.read_pickle(path, compression=None)
    except Exception as e:  # noqa: BLE001 - a broken cache is re-downloaded, never fatal
        log.warning(
            "fundamentals cache %s unreadable (%s: %s); re-downloading", path, type(e).__name__, e
        )
        return None
    if (
        not isinstance(frame, pd.DataFrame)
        or len(frame) != rows
        or tuple(frame.columns) != FACTS_COLUMNS
    ):
        log.warning("fundamentals cache %s has the wrong shape; re-downloading", path)
        return None
    return frame


def _write_facts_cache(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    frame.to_pickle(tmp, compression=None)
    os.replace(tmp, path)
    log.info("fundamentals cache written: %s", path)
    for old in sorted(path.parent.glob(FACTS_CACHE_GLOB)):
        if old != path:
            old.unlink(missing_ok=True)
            log.info("removed stale fundamentals cache %s", old.name)


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


def dev_report_files(
    out_dir: Path, plans_dir: Path, report: dev_report.DevReport
) -> tuple[tuple[Path, str], ...]:
    """Every file of the P7a dev report set, rendered, as ``(path, text)`` in write order:
    <stem>.md, <stem>-rows.csv, <stem>-curves.csv, <stem>-frontier.svg in ``out_dir``, then the
    P7b pre-registration in ``plans_dir``. Nothing is written; ``backtest_dev --only`` renders
    through this to exercise the renderers without touching ``docs/``."""
    out_dir = Path(out_dir)
    plans_dir = Path(plans_dir)
    stem = dev_report.report_stem(report.run_date)
    return (
        (out_dir / f"{stem}.md", dev_report.render_markdown(report)),
        (out_dir / f"{stem}-rows.csv", dev_report.rows_csv(report)),
        (out_dir / f"{stem}-curves.csv", dev_report.curves_csv(report)),
        (out_dir / f"{stem}-frontier.svg", dev_report.frontier_svg(report)),
        (plans_dir / dev_report.preregistration_name(report.run_date), dev_report.render_preregistration(report)),
    )


def write_dev_report(out_dir: Path, plans_dir: Path, report: dev_report.DevReport) -> list[Path]:
    """Write the P7a dev report set into ``out_dir`` and the pre-registration into ``plans_dir``
    (both created if needed) with LF line endings; return the paths in ``dev_report_files``
    order. All five are rendered before any directory is created or file written, so a render
    error leaves no partial set."""
    files = dev_report_files(out_dir, plans_dir, report)
    for directory in sorted({path.parent for path, _ in files}):
        directory.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for path, text in files:
        path.write_text(text, encoding="utf-8", newline="\n")
        paths.append(path)
    return paths

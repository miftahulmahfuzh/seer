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
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

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


# ---- dividends-aware download (the P7a research store) -------------------------------------
#
# Same price convention as above (auto_adjust=False: split-adjusted, NOT dividend-adjusted),
# plus yfinance's ``Dividends`` column (actions=True): cash dividends per share on the ex-date,
# split-adjusted by Yahoo to the same scale as the prices (verified: AAPL 2012-08-09 is 0.094643
# = $2.65 / 28). ``Stock Splits`` and ``Capital Gains`` are ignored: prices are already
# split-adjusted, and capital-gain distributions are not cash dividends.

DIVIDENDS_COLUMN = "Dividends"
DIVIDEND_QUANTUM = Decimal("0.000001")


@dataclass(frozen=True)
class TickerHistory:
    """One ticker's split-adjusted bars and split-adjusted cash dividends, both ascending."""

    bars: tuple[Bar, ...]
    dividends: tuple[tuple[date, Decimal], ...]


EMPTY_HISTORY = TickerHistory(bars=(), dividends=())


def yf_download_actions(tickers: list[str], start: date, end_exclusive: date) -> pd.DataFrame | None:
    """Like :func:`yf_download`, with ``actions=True`` (adds ``Dividends`` / ``Stock Splits``).

    Raises :class:`RateLimited` if yfinance raised or logged a rate-limit error for any
    ticker in the batch.
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
            actions=True,
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


def download_actions(
    symbols: Sequence[str],
    start: date,
    end_exclusive: date,
    *,
    downloader: Downloader | None = None,
) -> dict[str, TickerHistory]:
    """Fetch bars AND cash dividends for canonical ``symbols`` in ``[start, end_exclusive)``.

    Returns ``{canonical_symbol: TickerHistory}`` with an entry (possibly
    :data:`EMPTY_HISTORY`) for every requested symbol. Date filtering against the caller's
    inclusive range is the caller's job.
    """
    canonical = list(dict.fromkeys(s.strip().upper() for s in symbols))
    tickers = [to_yahoo(s) for s in canonical]
    fetch = downloader if downloader is not None else yf_download_actions
    frame = fetch(tickers, start, end_exclusive)
    parsed = parse_frame_actions(frame, tickers)
    return {s: parsed.get(s, EMPTY_HISTORY) for s in canonical}


def parse_frame_actions(frame: pd.DataFrame | None, tickers: Sequence[str]) -> dict[str, TickerHistory]:
    """Turn a yfinance ``actions=True`` frame into ``{canonical_symbol: TickerHistory}``.

    Accepts the same column shapes as :func:`parse_frame`. Bars are exactly what
    :func:`frame_to_bars` makes; dividends come from :func:`frame_to_dividends`.
    """
    out: dict[str, TickerHistory] = {from_yahoo(t): EMPTY_HISTORY for t in tickers}
    if frame is None or len(frame.index) == 0:
        return out
    single = len(tickers) == 1
    for ticker in tickers:
        sub = _ticker_frame(frame, ticker, single=single)
        if sub is None:
            log.debug("yahoo: %s not present in frame", ticker)
            continue
        symbol = from_yahoo(ticker)
        out[symbol] = TickerHistory(
            bars=tuple(frame_to_bars(symbol, sub)),
            dividends=frame_to_dividends(sub),
        )
    return out


def frame_to_dividends(sub: pd.DataFrame) -> tuple[tuple[date, Decimal], ...]:
    """One ticker's frame -> ascending ``(ex_date, amount)`` cash dividends.

    Only finite amounts > 0 are kept (yfinance writes 0.0 on every other day and NaN where
    the ticker has no row). Amounts go through the float's shortest repr and are rounded
    half-up to 6 decimals (:data:`DIVIDEND_QUANTUM`); one that rounds to 0 is dropped. Dates
    are the exchange-local index dates, as in :func:`frame_to_bars`.
    """
    if DIVIDENDS_COLUMN not in {str(c) for c in sub.columns}:
        return ()
    index = pd.DatetimeIndex(sub.index)
    if index.tz is not None:
        index = index.tz_localize(None)
    values = sub[DIVIDENDS_COLUMN].to_numpy(dtype=float)
    by_date: dict[date, Decimal] = {}
    for ts, raw in zip(index, values):
        if pd.isna(ts):
            continue
        value = float(raw)
        if not math.isfinite(value) or value <= 0:
            continue
        amount = Decimal(repr(value)).quantize(DIVIDEND_QUANTUM, rounding=ROUND_HALF_UP)
        if amount <= 0:
            continue
        by_date[ts.date()] = amount
    return tuple((d, by_date[d]) for d in sorted(by_date))

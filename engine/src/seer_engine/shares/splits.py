"""The split lists behind the research stores' split-adjusted closes, cached from the vendor.

Why this exists. A store keeps only split-adjusted closes (``research`` module docstring), and a
company's size needs the close **as it printed** (``history.market_value``). The adjustment can be
undone exactly -- ``history.unadjust`` -- given the very list of splits the vendor applied. The dev
and test stores' bars are yfinance's (``auto_adjust=False``: split-adjusted, not
dividend-adjusted), so their list is yfinance's own; the survivorship-check store's added symbols
were adjusted by ``survivorship.clean_symbol`` from EODHD's list, and their list is the one that
function applied (``survivorship.Cleaned.splits``).

**The adjustment basis is the day the bars were downloaded, not the window end.** Yahoo divides
every earlier price by each split on its ex-date, so a dev store crawled in October 2026 carries
Apple's 2020 four-for-one inside its 2015 closes. A split list for a store is therefore every split
the vendor listed **up to the crawl** (``basis``); one effective after the crawl was not applied to
the bars and must not be undone. ``store_lines`` in ``shares.store`` keeps the ones inside the
store's window as dated rows and folds the rest into one undated row per symbol, so the store
holds no row dated after its window (D9).

This module is the network edge: :func:`fetch_yfinance` calls ``yfinance.Ticker(...).splits`` once
per symbol and caches each answer as JSON under ``<cache>/<SYM>.json`` (gitignored, resumable,
``null`` when Yahoo has no such ticker). :func:`read_yfinance` reads the cache and nothing else.
"""

from __future__ import annotations

import json
import logging
import math
import os
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from seer_engine import config, yahoo

log = logging.getLogger(__name__)

CACHE_DIR = config.REPO_ROOT / "engine" / ".cache" / "yfinance" / "splits"


@dataclass(frozen=True, order=True)
class Split:
    """``ratio`` new shares per old (2.0 for 2-for-1, 0.1 for 1-for-10), effective from ``date``
    (the ex-date, the first session priced post-split). Shaped like ``history.SplitLike``."""

    date: date
    ratio: float


#: (yahoo ticker) -> [(ex-date, ratio)], or None when Yahoo has no such ticker.
SplitFetcher = Callable[[str], "Sequence[tuple[date, float]] | None"]


def yf_splits(ticker: str) -> list[tuple[date, float]] | None:
    """yfinance's split list for one Yahoo ticker; None when the ticker is unknown to Yahoo."""
    import yfinance as yf

    series = yf.Ticker(ticker).splits
    if series is None:
        return None
    return [(ts.date(), float(r)) for ts, r in series.items()]


def _cache_file(cache: Path, symbol: str) -> Path:
    return cache / f"{symbol}.json"


def fetch_yfinance(
    symbols: Iterable[str],
    cache: Path = CACHE_DIR,
    *,
    refetch: bool = False,
    fetcher: SplitFetcher | None = None,
) -> tuple[int, int, list[str]]:
    """Cache yfinance's split list for every symbol not cached yet; (fetched, unknown, failed)."""
    get = fetcher if fetcher is not None else yf_splits
    cache.mkdir(parents=True, exist_ok=True)
    fetched = unknown = 0
    failed: list[str] = []
    todo = [s for s in sorted(set(symbols)) if refetch or not _cache_file(cache, s).is_file()]
    for n, symbol in enumerate(todo, 1):
        ticker = yahoo.to_yahoo(symbol)
        try:
            rows = get(ticker)
        except Exception as exc:  # noqa: BLE001 - one failed symbol never stops the crawl
            log.warning("splits: %s failed: %r", symbol, exc)
            failed.append(symbol)
            continue
        doc = {
            "symbol": symbol,
            "ticker": ticker,
            "fetched": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "rows": None if rows is None else [[d.isoformat(), float(r)] for d, r in rows],
        }
        path = _cache_file(cache, symbol)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(doc, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp, path)
        fetched += 1
        unknown += rows is None
        if n % 50 == 0:
            log.info("splits: %d of %d symbols fetched", n, len(todo))
    return fetched, unknown, failed


def read_yfinance(cache: Path, symbol: str) -> tuple[Split, ...] | None:
    """The cached split list (ascending), () when Yahoo lists none, None when never fetched or
    when Yahoo has no such ticker. A non-positive or non-finite ratio is refused."""
    path = _cache_file(cache, symbol)
    if not path.is_file():
        return None
    rows = json.loads(path.read_text(encoding="utf-8")).get("rows")
    if rows is None:
        return None
    out = []
    for raw_day, raw_ratio in rows:
        ratio = float(raw_ratio)
        if not (math.isfinite(ratio) and ratio > 0):
            raise ValueError(f"{path.name}: split ratio {raw_ratio!r} on {raw_day}")
        out.append(Split(date.fromisoformat(raw_day), ratio))
    return tuple(sorted(out))

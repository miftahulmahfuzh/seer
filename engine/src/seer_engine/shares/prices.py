"""Raw (unadjusted) closes and split lists for checking the cover-page share counts.

A share count is checked against price in two ways (``checks``): the implied market value
``shares x raw close`` must look like an S&P 500 member's, and a count must move by a split's
ratio across that split. Both need prices **as they printed that day**, which the research
stores do not keep: ``engine/.research`` holds yfinance closes and ``engine/.research-sv`` cleaned
EODHD closes, both split-adjusted, and neither stores the split list that adjusted them.

EODHD's ``/eod`` rows carry the raw close beside an adjusted one, and ``/splits`` lists the
splits, so the checks read those:

* ``engine/.cache/eodhd/{eod,splits}/<SYM>.json`` -- the survivorship month's pull, 522 symbols
  the dev store never served, read in place and never written;
* ``<edgar cache>/prices/{eod,splits}/<SYM>.json`` -- the same two documents for the rest of the
  S&P 500 symbols of 1996-2010, fetched here (:func:`fetch_missing`) under the store symbol's
  own code, exactly as the survivorship pull fetched its 522.

A store symbol's EODHD code can belong to a later company that reused the ticker; the checks
therefore only ever read a symbol's prices on the days the symbol was an index member, when the
membership files guarantee which company it was.

The EODHD fundamentals endpoint is not on the owner's plan and is never called.
"""

from __future__ import annotations

import bisect
import json
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from seer_engine import config, eodhd
from seer_engine import survivorship as sv

log = logging.getLogger(__name__)

EODHD_CACHE = config.REPO_ROOT / "engine" / ".cache" / "eodhd"
#: Earliest raw close fetched: a quarter before the first cover the history uses.
PRICE_FROM = date(1995, 1, 1)


@dataclass(frozen=True)
class PriceSeries:
    """One symbol's raw closes (ascending dates) and listed splits."""

    symbol: str
    dates: tuple[date, ...]
    closes: tuple[float, ...]
    splits: tuple[sv.Split, ...]

    def close_on(self, on: date, max_gap_days: int = 7) -> float | None:
        """The raw close on ``on`` or the last session before it (within ``max_gap_days``)."""
        i = bisect.bisect_right(self.dates, on) - 1
        if i < 0 or (on - self.dates[i]).days > max_gap_days:
            return None
        return self.closes[i]


def _series(symbol: str, root: Path) -> PriceSeries | None:
    raw = sv.read_series(root, symbol)
    if raw is None:
        return None
    rows = [(b.date, b.close) for b in raw.bars if b.close is not None and b.close > 0]
    return PriceSeries(
        symbol=symbol,
        dates=tuple(d for d, _ in rows),
        closes=tuple(c for _, c in rows),
        splits=raw.splits,
    )


def _renamed(symbol: str, eodhd_cache: Path) -> PriceSeries | None:
    """The survivorship pull's accepted series under another EODHD code (``DOW_old`` for the
    Dow Chemical that traded as DOW until 2017), when it found one: the store-symbol code is
    then a later company and must not be read."""
    path = eodhd_cache / "alias" / f"{symbol}.json"
    if not path.is_file():
        return None
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        return None
    bars = sv.parse_bars(doc.get("eod"))
    rows = [(b.date, b.close) for b in bars if b.close is not None and b.close > 0]
    return PriceSeries(symbol, tuple(d for d, _ in rows), tuple(c for _, c in rows),
                       sv.parse_splits(doc.get("splits")))


def load(symbol: str, edgar_cache: Path, eodhd_cache: Path = EODHD_CACHE) -> PriceSeries | None:
    """The symbol's series: the survivorship pull's renamed-code series when it accepted one,
    else its store-symbol series, else this module's own fetch."""
    s = _renamed(symbol, eodhd_cache)
    if s is not None and s.dates:
        return s
    for root in (eodhd_cache, edgar_cache / "prices"):
        s = _series(symbol, root)
        if s is not None and s.dates:
            return s
    return None


def fetch_missing(symbols: Iterable[str], edgar_cache: Path, token: str,
                  eodhd_cache: Path = EODHD_CACHE) -> dict[str, int]:
    """Fetch ``/eod`` and ``/splits`` for every symbol neither cache holds. ``null`` on 404."""
    client = eodhd.Client(token)
    root = edgar_cache / "prices"
    (root / "eod").mkdir(parents=True, exist_ok=True)
    (root / "splits").mkdir(parents=True, exist_ok=True)
    tally = {"cached": 0, "fetched": 0, "missing": 0}
    for symbol in sorted(set(symbols)):
        if (eodhd_cache / "eod" / f"{symbol}.json").is_file() or (root / "eod" / f"{symbol}.json").is_file():
            tally["cached"] += 1
            continue
        code = eodhd.ticker(symbol)[: -len(".US")]
        rows = client.eod(code, start=PRICE_FROM)
        splits = client.splits(code, start=PRICE_FROM)
        (root / "splits" / f"{symbol}.json").write_text(json.dumps(splits), encoding="utf-8")
        (root / "eod" / f"{symbol}.json").write_text(json.dumps(rows), encoding="utf-8")
        tally["missing" if rows is None else "fetched"] += 1
    log.info("prices: %s (%d EODHD calls)", tally, client.calls)
    return tally

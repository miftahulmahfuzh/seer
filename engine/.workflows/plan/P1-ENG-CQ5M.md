> Adopted from `TRADE_RULES_DEV_SEARCH_PLAN.md` phase 4. Source: `.workflows/plan/trade-rules-dev-search/phase-4.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 4: Research store — build, load, verify, command, real build

**Plan set:** `TRADE_RULES_DEV_SEARCH_PLAN.md`
**Analysis:** `20261003-195606-T7R2_code_analyzer.md`
**Satisfies:** R2 (the research store command: pre-2015 member bars, the L9 ETFs, dividends from the start, unserved members per year, no Neon writes, deterministic, fingerprinted), R4 (the data-level half of the dev-window guard: the store never holds, and `load_store` rejects, a row after 2015-10-16)
**Depends on:** none
**Difficulty:** HARD (the network build takes 30–60 min and must be checked against real data)
**Package:** `engine/src/seer_engine` (root: `research.py`, `yahoo.py`) and `engine/src/seer_engine/commands`

---

## Goal

After this phase, `python -m seer_engine research_store` builds a local, gitignored store in
`engine/.research/`. It holds:
- split-adjusted daily bars from 1993-01-29 to 2015-10-16 for the 21 L9 ETFs and every
  S&P 500 / Nasdaq-100 member since 1996;
- split-adjusted cash dividends;
- Frankfurter USD/IDR from 1999-01-04;
- the list of members yfinance could not serve;
- a manifest with per-file sha256 and a fingerprint.

`research.load_store` turns the store into a `ResearchData` value without Neon or the network.
Its `Market` is built the same way `backtest.io.load_market` builds one. It refuses a tampered
file and any row dated after `DEV_END`. The real store is built in the worktree and checked
three ways, and its counts and fingerprint are logged.

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.

**Creates:**

`seer_engine/research.py` (new, impure edge: yfinance, Frankfurter, local files; never Neon):
- **Constants, exactly as the index contract:**
  - `DEV_END = date(2015, 10, 16)`
  - `STORE_START = date(1993, 1, 29)`
  - `STORE_DIR = config.REPO_ROOT / "engine" / ".research"`
  - `RESEARCH_ETFS` (the 21 sorted tickers)
  - `SECTOR_ETFS` (the 9 sector SPDRs)
- **Additional constants:**
  - `MEMBERSHIP_START = date(1996, 1, 2)` and `FX_START = date(1999, 1, 4)`, which repeat
    `backtest.dev`'s values;
  - the file names `BARS_FILE`, `DIVIDENDS_FILE`, `FX_FILE`, `UNSERVED_FILE` and
    `MANIFEST_FILE`, and `DATA_FILES`;
  - the headers `BARS_HEADER`, `DIVIDENDS_HEADER`, `FX_HEADER` and `UNSERVED_HEADER`;
  - `UNSERVED_REASON`, `MANIFEST_KEYS` and `DEFAULT_BATCH_SIZE = 40`;
  - `BATCH_PAUSE_S = 3.0` and `RATE_LIMIT_BACKOFF_S = (60.0, 120.0, 240.0)`;
  - `SPY_CHECK_START = date(1993, 2, 1)`, `SCALE_CHECK_SYMBOL = "AAPL"` and
    `SCALE_CHECK_YEAR = 2012`;
  - `SCALE_MIN_YIELD = Decimal("0.001")` and `SCALE_MAX_YIELD = Decimal("0.02")`.
- **Types:**
  - `class ResearchStoreError(RuntimeError)`: a build that cannot finish.
  - `@dataclass(frozen=True) class ResearchData`, with fields `market: Market`,
    `dividends: dict[str, dict[date, Decimal]]`, `spy_dividends: tuple[Dividend, ...]`,
    `fingerprint: str`, `manifest: Mapping[str, Any]` and
    **`unserved: tuple[str, ...] = ()`**. The last field is an additive extension of the
    index contract; see the notes below.
  - `@dataclass(frozen=True) class Check(name: str, ok: bool, detail: str)`.
- **Functions:**
  - `def build_store(store_dir: Path, *, downloader=None, fetch_fx=None, sleep=time.sleep, batch_size=DEFAULT_BATCH_SIZE, data_dir: Path | None = None) -> dict[str, Any]`
    is the contract signature plus the keyword `data_dir`, which defaults to
    `membership.DATA_DIR`.
  - `def load_store(store_dir: Path, *, data_dir: Path | None = None) -> ResearchData` is the
    contract signature plus the keyword `data_dir`.
  - `def requested_symbols(data_dir: Path | None = None) -> tuple[str, ...]`
  - `def research_membership(data_dir: Path | None = None) -> Membership`
  - `def file_sha256(path: Path) -> str`
  - `def fingerprint_of(files: Mapping[str, str]) -> str`
  - `def unserved_by_year(members: Membership, unserved: Iterable[str]) -> tuple[tuple[int, int, int], ...]`
  - `def check_spy_sessions(data, start=SPY_CHECK_START, end=DEV_END) -> Check`
  - `def check_spy_dividends(data, vendored: Sequence[Dividend]) -> Check`
  - `def check_dividend_scale(data, symbol=SCALE_CHECK_SYMBOL, year=SCALE_CHECK_YEAR) -> Check`
  - `def run_checks(data, vendored) -> tuple[Check, ...]`

`seer_engine/yahoo.py` (additive only; every existing function is byte-unchanged):
- `DIVIDENDS_COLUMN = "Dividends"` and `DIVIDEND_QUANTUM = Decimal("0.000001")`;
- `@dataclass(frozen=True) class TickerHistory(bars: tuple[Bar, ...], dividends: tuple[tuple[date, Decimal], ...])`
  and `EMPTY_HISTORY`;
- `yf_download_actions(tickers, start, end_exclusive)`, which is `yf_download` with
  `actions=True`;
- `download_actions(symbols, start, end_exclusive, *, downloader=None) -> dict[str, TickerHistory]`;
- `parse_frame_actions(frame, tickers) -> dict[str, TickerHistory]`;
- `frame_to_dividends(sub) -> tuple[tuple[date, Decimal], ...]`.

`seer_engine/commands/research_store.py` (new):
- `HELP`, `add_arguments`, `run` and `format_summary`;
- the CLI is `python -m seer_engine research_store [--store DIR] [--batch-size N] [--verify]`,
  and it honours the global `--dry-run`.

**Signature changes:** none to existing code.

**Requires (from earlier phases):** none.

**Leaves alone (owned by others):**
- these files are not changed: `membership.py`, `fx.py`, `commands/backfill.py`,
  `backtest/io.py`, `backtest/benchmark.py` and `backtest/market.py`. `research.py` only
  imports from them;
- every frozen-set file;
- Neon;
- `backtest/dev.py` (phase 9): it owns its own `DEV_END`, `MEMBERSHIP_START` and `FX_START`,
  and the equality test;
- `commands/backtest_dev.py` and `io.write_dev_report` (phase 12), which call `load_store`.

**Interface notes for the reconciler:**
1. **`ResearchData.unserved`** is added as the last field, with a default. Phase 10's
   `DevReport.unserved: tuple[str, ...]` needs it, and phase 12 would otherwise have to parse
   `unserved.csv` itself. Phase 12 should pass `data.unserved` and
   `{k: data.manifest[k] for k in ("bar_rows", "symbols_served", "symbols_requested", "dividend_rows", "fx_rows")}`
   as `store_counts`.
2. **The `data_dir` keyword** on `build_store` and `load_store` exists so the tests can use a
   tiny membership fixture. Production callers omit it.
3. **The constants are duplicated on purpose.** `backtest/dev.py` is pure and must not import
   `research`, because `research` imports `yahoo`, which imports `seer_engine.bars`, which
   imports `psycopg`. Phase 9 therefore has its own `DEV_END`, `MEMBERSHIP_START` and
   `FX_START`. The equality of all three with `research.*` is asserted in **phase 12's**
   `tests/test_backtest_dev_command.py` (plan index D-I: phase 12 depends on both 4 and 9),
   together with `registry.SECTOR_ETFS == research.SECTOR_ETFS` and the registry's fixed
   symbols ⊆ `RESEARCH_ETFS`. This phase's tests pin only `research`'s own values.
4. **`research_membership`'s intervals are clipped to the dev window.**
   - Only intervals with `start_date <= DEV_END` and `end_date` in (`None`, or
     `> MEMBERSHIP_START`) are kept.
   - An `end_date > DEV_END` becomes `None`, so nothing after `DEV_END` is visible, even
     through membership.
   - Intervals are merged with `io.merge_intervals`.
   - `market.membership.symbols()` is exactly the set of dev-window members.
5. **Unserved ETFs abort the build.** An unserved `RESEARCH_ETFS` symbol raises
   `ResearchStoreError`. So `unserved` only ever holds index members, and every ETF in
   `RESEARCH_ETFS` has bars in any store that loads.

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/yahoo.py` | modify (additive) | imports at lines 17–26 gain `dataclass`/`ROUND_HALF_UP`; new block appended after line 220: `TickerHistory`, `yf_download_actions`, `download_actions`, `parse_frame_actions`, `frame_to_dividends` |
| `engine/src/seer_engine/research.py` | create | the store: constants, build, load, verification checks |
| `engine/src/seer_engine/commands/research_store.py` | create | the CLI command |
| `.gitignore` | modify | after line 18: `engine/.research/`, `engine/.research.tmp/`, `engine/.research.old/` |
| `engine/tests/test_research_store.py` | create | 29 test functions (34 collected items) |
| `engine/.research/` | generated, gitignored | the real store, built in Step 6; never committed |

## Implementation Steps

### Step 1: Dividends-aware download and parse in `yahoo.py`
**File:** `engine/src/seer_engine/yahoo.py:17-26` (imports), then append after `:220`
(end of `frame_to_bars`).

**Change:**
- In the imports, add `from dataclasses import dataclass` and make the decimal import
  `from decimal import ROUND_HALF_UP, Decimal`.
- Append the block below.
- `yf_download`, `download`, `parse_frame`, `_price_level`, `_ticker_frame`, `_dec` and
  `frame_to_bars` stay byte-identical.

Facts verified by a live probe (2026-10-03, yfinance 1.7.0):
- `yf.download(..., auto_adjust=False, actions=True, group_by="ticker", multi_level_index=True)`
  returns MultiIndex `(Ticker, Price)` columns. The Price level is
  `Open, High, Low, Close, Adj Close, Volume, Dividends, Stock Splits`, plus `Capital Gains`
  for funds such as SPY.
- `Dividends` is 0.0 on non-ex-dates and **split-adjusted**. AAPL's 2012-08-09 dividend is
  `0.094643`, which is $2.65 / 28, the same scale as its ~$22.17 split-adjusted close.
- SPY's dividends on 2015-03-20, 2015-06-19 and 2015-09-18 are `0.931`, `1.03` and `1.033`,
  identical to `engine/data/spy_dividends.csv`.
- SPY has 5722 bars from 1993-01-29 to 2015-10-16. That is exactly the 5721 NYSE sessions from
  1993-02-01 to 2015-10-16 that `dates.sessions` returns, plus 1993-01-29.

Imports, replacing lines 17–26:
```python
import logging
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

import pandas as pd

from seer_engine import bars
from seer_engine.bars import Bar
```

Appended after line 220:
```python


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
```

**Impact:** additive only. `backfill` and `nightly` still call `yf_download`/`download`
unchanged, and the existing tests in `tests/test_backfill.py` are unaffected.

### Step 2: The research store module
**File:** `engine/src/seer_engine/research.py` (new)

**Change:** create the module below.

These are the decisions it encodes:
- **Symbols.**
  - The build requests `RESEARCH_ETFS` ∪ every `compute_universe()` symbol whose interval
    overlaps `[MEMBERSHIP_START, DEV_END]`, sorted. That is 1041 members today, about 1060
    symbols in all.
  - It fetches `[STORE_START, DEV_END + 1 day)` for every symbol. Rows outside
    `[STORE_START, DEV_END]` are dropped defensively.
- **Batches.**
  - Batches are consecutive chunks of the sorted symbol list, and bars are streamed to
    `bars.csv` batch by batch. That bounds memory, since about 3M rows would not fit as `Bar`
    objects.
  - Each chunk is written in symbol order, so the file is globally sorted.
  - The output therefore does not depend on `batch_size`. A test proves this.
- **Network policy, deterministic by construction.**
  - A rate limit backs off 60 s, 120 s and 240 s, then aborts the build.
  - Any other download exception aborts the build.
  - A symbol that comes back empty in a batch gets one individual retry, like `backfill`. If it
    is still empty, it is recorded in `unserved.csv` with the single, deterministic reason
    `UNSERVED_REASON`.
  - Transient failures never become rows in the store. They abort it, and the previous store
    is kept.
  - An unserved ETF aborts the build, because every family depends on the ETFs.
- **FX.**
  - FX is fetched first, from `FX_START` to `DEV_END`, so the build fails fast.
  - Rows outside that range are dropped, and conflicting duplicate dates abort the build.
  - Values are written with `to_decimal`, 4 dp, the same as `fx_rates`.
- **Writing.**
  - Every file goes into `<store>.tmp`, then `manifest.json` is sealed.
  - The old store is renamed to `<store>.old`, the temp directory is renamed into place, and
    the old one is removed. This is all-or-nothing.
- **File text.**
  - Encoding is UTF-8 with LF line endings and a trailing newline.
  - Bar prices are `str()` of the 4-dp `Decimal` that `bars.make_bar` produces, exactly the
    `bars` convention.
  - A dividend amount is `format(amount.quantize(1e-6).normalize(), "f")`, so it has at most
    6 dp and no exponent.
- **The fingerprint** is `sha256("".join(f"{name}:{sha}\n" for name in sorted(files)))`, over
    the four data files. The manifest is not one of them.
- **`load_store`** checks, in order:
  1. that the manifest's shape, `dev_end` and `store_start` are right;
  2. each file's sha256;
  3. the fingerprint;
  4. that no row is dated after `DEV_END` (and no bar is dated before `STORE_START`);
  5. that the counts match.

  Then it builds the value. Every failure is a `ValueError`.

**Code:**
```python
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
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from seer_engine import config, dates, fx, membership, yahoo
from seer_engine.backtest.benchmark import Dividend
from seer_engine.backtest.io import BAR_COLUMNS, LoadError, histories_from_frame, merge_intervals
from seer_engine.backtest.market import Market, Membership
from seer_engine.prices import to_decimal

log = logging.getLogger(__name__)

DEV_END = date(2015, 10, 16)  # == backtest.dev.DEV_END (phase 9 tests the equality)
STORE_START = date(1993, 1, 29)  # SPY's first session
MEMBERSHIP_START = date(1996, 1, 2)  # first sp500_history.csv row (== backtest.dev.MEMBERSHIP_START)
FX_START = date(1999, 1, 4)  # first Frankfurter USD/IDR row (== backtest.dev.FX_START)
STORE_DIR = config.REPO_ROOT / "engine" / ".research"  # gitignored

RESEARCH_ETFS: tuple[str, ...] = (
    "BIL", "DIA", "EFA", "GLD", "IEF", "IWM", "QLD", "QQQ", "SHY", "SPY", "SSO",
    "TLT", "XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY",
)  # sorted; launch-limited by yfinance
SECTOR_ETFS: tuple[str, ...] = ("XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY")

BARS_FILE = "bars.csv"
DIVIDENDS_FILE = "dividends.csv"
FX_FILE = "fx.csv"
UNSERVED_FILE = "unserved.csv"
MANIFEST_FILE = "manifest.json"
DATA_FILES: tuple[str, ...] = (BARS_FILE, DIVIDENDS_FILE, FX_FILE, UNSERVED_FILE)

BARS_HEADER = "symbol,date,open,high,low,close,volume"
DIVIDENDS_HEADER = "symbol,ex_date,amount"
FX_HEADER = "date,usd_idr"
UNSERVED_HEADER = "symbol,reason"
UNSERVED_REASON = f"yfinance returned no bars for {STORE_START.isoformat()}..{DEV_END.isoformat()}"

_COUNT_KEYS: tuple[str, ...] = (
    "bar_rows",
    "dividend_rows",
    "fx_rows",
    "symbols_requested",
    "symbols_served",
)
MANIFEST_KEYS: frozenset[str] = frozenset({"dev_end", "store_start", "files", "fingerprint", *_COUNT_KEYS})

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
    """A loaded, verified research store."""

    market: Market  # history from bars.csv, membership clipped to the dev window, fx from fx.csv
    dividends: dict[str, dict[date, Decimal]]  # symbol -> ex_date -> amount (ascending)
    spy_dividends: tuple[Dividend, ...]  # SPY's, as benchmark.Dividend, ascending
    fingerprint: str
    manifest: Mapping[str, Any]
    unserved: tuple[str, ...] = ()  # requested members with no bars, sorted


@dataclass(frozen=True)
class Check:
    """One verification of a built store: a stable name, the verdict, and what was seen."""

    name: str
    ok: bool
    detail: str


# ---- symbols and membership ----------------------------------------------------------------


def _universe(data_dir: Path | None) -> list[membership.Interval]:
    return membership.compute_universe(data_dir if data_dir is not None else membership.DATA_DIR)


def _overlaps_window(iv: membership.Interval) -> bool:
    return iv.start_date <= DEV_END and (iv.end_date is None or iv.end_date > MEMBERSHIP_START)


def requested_symbols(data_dir: Path | None = None) -> tuple[str, ...]:
    """RESEARCH_ETFS ∪ every member whose interval overlaps [MEMBERSHIP_START, DEV_END], sorted."""
    members = {iv.symbol for iv in _universe(data_dir) if _overlaps_window(iv)}
    return tuple(sorted(set(RESEARCH_ETFS) | members))


def research_membership(data_dir: Path | None = None) -> Membership:
    """Point-in-time membership for the dev window, from the vendored CSVs (no Neon).

    Only intervals overlapping [MEMBERSHIP_START, DEV_END] are kept, and an end after DEV_END
    becomes None (still a member on every dev session), so nothing dated after DEV_END is
    visible even through membership. Both indices are merged with ``io.merge_intervals``,
    exactly like ``io.read_intervals`` does for Neon's ``universe``.
    """
    rows: list[tuple[str, date, date | None]] = []
    for iv in _universe(data_dir):
        if not _overlaps_window(iv):
            continue
        end = iv.end_date if iv.end_date is not None and iv.end_date <= DEV_END else None
        rows.append((iv.symbol, iv.start_date, end))
    return Membership(intervals=merge_intervals(rows))


def unserved_by_year(members: Membership, unserved: Iterable[str]) -> tuple[tuple[int, int, int], ...]:
    """Per calendar year MEMBERSHIP_START.year..DEV_END.year: (year, distinct members that year,
    of which unserved). A symbol counts in a year when one of its intervals overlaps that year's
    part of [MEMBERSHIP_START, DEV_END]."""
    missing = set(unserved)
    out: list[tuple[int, int, int]] = []
    for year in range(MEMBERSHIP_START.year, DEV_END.year + 1):
        lo = max(date(year, 1, 1), MEMBERSHIP_START)
        hi = min(date(year, 12, 31), DEV_END)
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


# ---- build ---------------------------------------------------------------------------------


def build_store(
    store_dir: Path,
    *,
    downloader: yahoo.Downloader | None = None,
    fetch_fx: FetchFx | None = None,
    sleep: Sleep = time.sleep,
    batch_size: int = DEFAULT_BATCH_SIZE,
    data_dir: Path | None = None,
) -> dict[str, Any]:
    """Build the research store at ``store_dir``; return its manifest.

    ``downloader`` defaults to ``yahoo.yf_download_actions`` and ``fetch_fx`` to
    ``fx.fetch_range`` (both injectable for tests); ``data_dir`` is the membership CSV
    directory (default ``membership.DATA_DIR``). Raises ResearchStoreError when the build
    cannot finish (rate limited out, a download error, an unserved ETF, no or conflicting FX);
    then nothing is written and a previous store at ``store_dir`` is left untouched.
    """
    if isinstance(batch_size, bool) or not isinstance(batch_size, int) or batch_size < 1:
        raise ValueError(f"batch_size must be an int >= 1, got {batch_size!r}")
    store_dir = Path(store_dir)
    fetch = downloader if downloader is not None else yahoo.yf_download_actions
    fetch_rates = fetch_fx if fetch_fx is not None else fx.fetch_range
    symbols = requested_symbols(data_dir)

    store_dir.parent.mkdir(parents=True, exist_ok=True)
    tmp = store_dir.with_name(store_dir.name + ".tmp")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir()
    try:
        fx_rows = _fetch_fx_rows(fetch_rates)
        _write_text(tmp / FX_FILE, FX_HEADER, [f"{d.isoformat()},{v}" for d, v in fx_rows])
        served, unserved, bar_rows, dividend_lines = _write_bars(tmp, symbols, fetch, sleep, batch_size)
        lost_etfs = [s for s in RESEARCH_ETFS if s in set(unserved)]
        if lost_etfs:
            raise ResearchStoreError(
                f"yfinance served no bars for ETF(s) {', '.join(lost_etfs)}; every family needs them"
            )
        _write_text(tmp / DIVIDENDS_FILE, DIVIDENDS_HEADER, dividend_lines)
        _write_text(tmp / UNSERVED_FILE, UNSERVED_HEADER, [f"{s},{UNSERVED_REASON}" for s in unserved])
        counts = {
            "bar_rows": bar_rows,
            "dividend_rows": len(dividend_lines),
            "fx_rows": len(fx_rows),
            "symbols_requested": len(symbols),
            "symbols_served": len(served),
        }
        manifest = _seal(tmp, counts)
        _swap_in(tmp, store_dir)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    log.info(
        "research: store %s built: %d of %d symbols served, %d bar rows, %d dividends, %d fx rows, "
        "fingerprint %s",
        store_dir,
        counts["symbols_served"],
        counts["symbols_requested"],
        counts["bar_rows"],
        counts["dividend_rows"],
        counts["fx_rows"],
        manifest["fingerprint"],
    )
    return manifest


def _fetch_fx_rows(fetch_rates: FetchFx) -> list[tuple[date, Decimal]]:
    try:
        raw = list(fetch_rates(FX_START, DEV_END))
    except Exception as exc:  # noqa: BLE001 - any FX failure aborts the build
        raise ResearchStoreError(f"USD/IDR fetch failed: {exc!r}") from exc
    items: dict[date, Decimal] = {}
    for d, rate in raw:
        if not FX_START <= d <= DEV_END:
            continue
        value = to_decimal(rate)
        if value <= 0:
            raise ResearchStoreError(f"USD/IDR on {d.isoformat()} is not positive: {value}")
        if d in items and items[d] != value:
            raise ResearchStoreError(f"conflicting USD/IDR rates for {d.isoformat()}")
        items[d] = value
    if not items:
        raise ResearchStoreError(f"Frankfurter returned no USD/IDR rows for {FX_START}..{DEV_END}")
    log.info("research: %d USD/IDR rows %s..%s", len(items), min(items), max(items))
    return sorted(items.items())


def _write_bars(
    tmp: Path,
    symbols: Sequence[str],
    fetch: yahoo.Downloader,
    sleep: Sleep,
    batch_size: int,
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
        DEV_END,
    )
    with (tmp / BARS_FILE).open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(BARS_HEADER + "\n")
        for number, batch in enumerate(batches, start=1):
            if number > 1:
                sleep(BATCH_PAUSE_S)
            got = _fetch_batch(batch, fetch, sleep)
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


def _fetch_batch(batch: Sequence[str], fetch: yahoo.Downloader, sleep: Sleep) -> dict[str, yahoo.TickerHistory]:
    """One batch, clipped to [STORE_START, DEV_END]; empties get one individual retry."""
    got = _download_with_backoff(batch, fetch, sleep)
    out = {s: _in_window(got.get(s, yahoo.EMPTY_HISTORY)) for s in batch}
    if len(batch) > 1:  # a one-symbol batch already was the individual attempt
        for symbol in batch:
            if out[symbol].bars:
                continue
            sleep(BATCH_PAUSE_S)
            again = _download_with_backoff([symbol], fetch, sleep)
            out[symbol] = _in_window(again.get(symbol, yahoo.EMPTY_HISTORY))
    return out


def _download_with_backoff(
    symbols: Sequence[str], fetch: yahoo.Downloader, sleep: Sleep
) -> dict[str, yahoo.TickerHistory]:
    end_exclusive = DEV_END + timedelta(days=1)
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


def _in_window(history: yahoo.TickerHistory) -> yahoo.TickerHistory:
    """Drop anything outside [STORE_START, DEV_END] (defensive: the request already ends at
    DEV_END + 1 day, but no test-window row may ever reach the store)."""
    return yahoo.TickerHistory(
        bars=tuple(b for b in history.bars if STORE_START <= b.date <= DEV_END),
        dividends=tuple((d, a) for d, a in history.dividends if STORE_START <= d <= DEV_END),
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


def _seal(tmp: Path, counts: Mapping[str, int]) -> dict[str, Any]:
    files = {name: file_sha256(tmp / name) for name in DATA_FILES}
    manifest: dict[str, Any] = {
        "dev_end": DEV_END.isoformat(),
        "store_start": STORE_START.isoformat(),
        **{key: int(counts[key]) for key in _COUNT_KEYS},
        "files": files,
        "fingerprint": fingerprint_of(files),
    }
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


# ---- load ----------------------------------------------------------------------------------


def load_store(store_dir: Path, *, data_dir: Path | None = None) -> ResearchData:
    """Load and verify the store at ``store_dir`` (no network, no database).

    ValueError when: the manifest is missing or malformed, or was built for another DEV_END or
    STORE_START; a file's sha256 or the fingerprint does not match the manifest; any bar,
    dividend or FX row is dated after DEV_END (D9, data level); the counts disagree.
    """
    store_dir = Path(store_dir)
    manifest = _read_manifest(store_dir)
    files: dict[str, str] = manifest["files"]
    for name in DATA_FILES:
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
    frame = _read_bars(store_dir / BARS_FILE)
    dividends = _read_dividends(store_dir / DIVIDENDS_FILE)
    fx_rows = _read_fx(store_dir / FX_FILE)
    unserved = _read_unserved(store_dir / UNSERVED_FILE)
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
    market = Market(history=history, membership=research_membership(data_dir), fx=fx_rows)
    spy_dividends = tuple(
        Dividend(ex_date=d, amount=a) for d, a in sorted(dividends.get("SPY", {}).items())
    )
    log.info(
        "research: loaded %s: %d symbols with bars, %d bar rows, %d dividends, %d fx rows, "
        "%d unserved, fingerprint %s",
        store_dir,
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
    )


def _read_manifest(store_dir: Path) -> dict[str, Any]:
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
    if not isinstance(manifest, dict) or set(manifest) != MANIFEST_KEYS:
        got = sorted(manifest) if isinstance(manifest, dict) else type(manifest).__name__
        raise ValueError(f"{path}: expected keys {sorted(MANIFEST_KEYS)}, got {got}")
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
    files = manifest["files"]
    if (
        not isinstance(files, dict)
        or set(files) != set(DATA_FILES)
        or not all(isinstance(v, str) for v in files.values())
    ):
        raise ValueError(f"{path}: 'files' must map exactly {list(DATA_FILES)} to sha256 hex strings")
    if not isinstance(manifest["fingerprint"], str):
        raise ValueError(f"{path}: 'fingerprint' must be a string")
    for key in _COUNT_KEYS:
        value = manifest[key]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{path}: {key!r} must be a non-negative int, got {value!r}")
    return manifest


def _after_dev_end(name: str, what: str, d: date) -> ValueError:
    return ValueError(
        f"{name}: {what} dated {d.isoformat()} is after DEV_END {DEV_END.isoformat()}; the "
        "research store must never hold a test-window row (D9)"
    )


def _read_bars(path: Path) -> pd.DataFrame:
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
        if latest > DEV_END:
            symbol = str(frame.loc[frame["date"].idxmax(), "symbol"])
            raise _after_dev_end(path.name, f"a {symbol} bar", latest)
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


def _read_dividends(path: Path) -> dict[str, dict[date, Decimal]]:
    out: dict[str, dict[date, Decimal]] = {}
    for number, line in _data_lines(path, DIVIDENDS_HEADER):
        where = f"{path.name}:{number}"
        fields = line.split(",")
        if len(fields) != 3:
            raise ValueError(f"{where}: expected 3 fields, got {len(fields)}")
        symbol, raw_date, raw_amount = fields
        ex_date = _parse_date(raw_date, where)
        if ex_date > DEV_END:
            raise _after_dev_end(where, f"a {symbol} dividend", ex_date)
        amount = _parse_positive(raw_amount, where)
        per_symbol = out.setdefault(symbol, {})
        if ex_date in per_symbol:
            raise ValueError(f"{where}: duplicate {symbol} dividend on {ex_date}")
        per_symbol[ex_date] = amount
    return {symbol: dict(sorted(rows.items())) for symbol, rows in sorted(out.items())}


def _read_fx(path: Path) -> tuple[tuple[date, Decimal], ...]:
    rows: list[tuple[date, Decimal]] = []
    for number, line in _data_lines(path, FX_HEADER):
        where = f"{path.name}:{number}"
        fields = line.split(",")
        if len(fields) != 2:
            raise ValueError(f"{where}: expected 2 fields, got {len(fields)}")
        d = _parse_date(fields[0], where)
        if d > DEV_END:
            raise _after_dev_end(where, "a USD/IDR rate", d)
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


def check_spy_sessions(data: ResearchData, start: date = SPY_CHECK_START, end: date = DEV_END) -> Check:
    """SPY has a bar on every NYSE session in [start, end]."""
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
    """The store's SPY dividends equal the vendored file on the overlap
    [first vendored ex_date, DEV_END] (2015-03-20..2015-10-16 today)."""
    if not vendored:
        return Check("spy-dividends", False, "the vendored SPY dividend file is empty")
    lo = vendored[0].ex_date
    ours = [(d.ex_date, d.amount) for d in data.spy_dividends if lo <= d.ex_date <= DEV_END]
    theirs = [(d.ex_date, d.amount) for d in vendored if lo <= d.ex_date <= DEV_END]
    ok = bool(theirs) and ours == theirs
    detail = (
        f"{lo.isoformat()}..{DEV_END.isoformat()}: store "
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
```

**Impact:** this is a new module, imported only by the new command and by phase 12. Purity
globs cover `strategies/*.py`, `backtest/*.py` and `sim/*.py` only, so this root-level impure
module is outside them, as intended.

### Step 3: The `research_store` command
**File:** `engine/src/seer_engine/commands/research_store.py` (new)

**Change:** create the command below. `cli.discover()` picks it up automatically, so
`cli.py` is not touched.

**Behaviour:**
- **Default:** build into `--store`, then load and verify it, then print the summary.
- **`--verify`:** load only (no network), run the checks and print the summary.
- **Global `--dry-run`:** build into a temporary directory, print the summary, then discard it.
  Nothing persists.
- **Exit codes:**
  - 0: everything is OK;
  - 1: the build failed (`ResearchStoreError`) or a check failed;
  - 2: the store is missing or invalid (`ValueError` from `load_store`).

**Code:**
```python
"""research_store — build (or verify) the local P7a research store (handover D5).

Downloads split-adjusted daily bars and cash dividends from yfinance for the L9 ETF set and
every S&P 500 / Nasdaq-100 member since 1996, and USD/IDR from Frankfurter, all through
``research.DEV_END`` (2015-10-16), into ``engine/.research/`` (gitignored). Then it loads the
store back, runs the three verifications (SPY on every NYSE session; SPY dividends equal the
vendored file on the overlap; AAPL 2012 dividend scale) and prints counts, the fingerprint and
the unserved members per year.

Never touches Neon and needs no DATABASE_URL.

    python -m seer_engine research_store [--store DIR] [--batch-size N] [--verify]

``--verify`` loads an existing store only (no network). The global ``--dry-run`` builds into a
temporary directory and discards it. Exit codes: 0 ok; 1 build failed or a check failed;
2 the store is missing or invalid.
"""

from __future__ import annotations

import argparse
import logging
import tempfile
from collections.abc import Sequence
from pathlib import Path

from seer_engine import research
from seer_engine.backtest import io as bt_io

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


def run(args: argparse.Namespace) -> int:
    store = Path(args.store)
    if args.verify:
        return _verify(store, note="")
    if getattr(args, "dry_run", False):
        with tempfile.TemporaryDirectory(prefix="seer-research-") as tmp:
            target = Path(tmp) / "store"
            code = _build(target, int(args.batch_size))
            if code != 0:
                return code
            return _verify(target, note=" (dry run: built in a temporary directory and discarded)")
    code = _build(store, int(args.batch_size))
    if code != 0:
        return code
    return _verify(store, note="")


def _build(store: Path, batch_size: int) -> int:
    try:
        research.build_store(store, batch_size=batch_size)
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
```

**Impact:**
- A new CLI command.
- `test_cli.py` only asserts `"migrate" in cli.discover()` and uses its own fake commands, so
  it is unaffected.
- No existing command changes.

### Step 4: Ignore the store
**File:** `.gitignore:18` (after the `engine/.cache/` line)

**Change:** insert this block between line 18 and the blank line 19:
```gitignore

# P7a research store (seer_engine.research; rebuilt by `python -m seer_engine research_store`)
engine/.research/
engine/.research.tmp/
engine/.research.old/
```

**Impact:** the store and the build's temp and old directories never reach git.
`git status --short` must stay clean after the real build in Step 6.

### Step 5: Tests
**File:** `engine/tests/test_research_store.py` (new)

**Change:**
- There are 29 test functions, which collect as **34 items** (27 plain, one parametrized ×4 and one ×3).
- No network and no database are used:
  - yfinance is a fake that builds yfinance-shaped `actions=True` frames;
  - Frankfurter is a fake;
  - sleeps are recorded instead of slept;
  - membership comes from a tiny CSV fixture passed as `data_dir`.
- The command tests run through `cli.main`.

Fixture membership (`members_dir`):
- SP500 snapshots on 1996-01-02 `{AAA, BBB, GONE}`, on 2000-01-03 `{AAA, BBB, BRK.B, CCC}`
  and on 2016-01-04 `{AAA, CCC, NEW}`.
- An NDX snapshot on 2007-02-01 `{AAA, DDD}`.

So the requested symbols are the 21 ETFs plus `AAA, BBB, BRK.B, CCC, DDD, GONE` (27 in all).
`NEW` starts after `DEV_END` and is not requested.

What the fake serves:
- every ETF on 1999-01-04, 1999-01-05 and 2015-10-16;
- SPY additionally on 1993-01-28 (before `STORE_START`) and 2015-10-19 (after `DEV_END`), with
  dividends 0.25 on 1999-01-05 and 0.5 on 2015-10-19;
- AAA, with a dividend of 2.65/28 on 1999-01-05;
- BBB, BRK-B, and CCC on 2015-10-16 and 2015-10-19;
- DDD only on 2015-10-19.

GONE is absent. So the served symbols number 25, the unserved are `DDD, GONE`, and the
counts are 71 bar rows, 2 dividend rows and 2 fx rows.

**Code:**
```python
"""Tests for the P7a research store (seer_engine.research), the dividends-aware yahoo
download/parse and the research_store command. No test touches the network or a database:
yfinance is an injected fake that builds yfinance-shaped ``actions=True`` frames, Frankfurter is
a fake, sleeps are recorded, and membership comes from a tiny CSV fixture (``data_dir``)."""

from __future__ import annotations

import ast
import dataclasses
import functools
import json
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from seer_engine import cli, config, db, research, yahoo
from seer_engine.backtest.benchmark import Dividend
from seer_engine.commands import research_store as research_cmd

COLS = ["Open", "High", "Low", "Close", "Adj Close", "Volume", "Dividends", "Stock Splits"]

PRE = date(1993, 1, 28)  # before STORE_START
D1 = date(1999, 1, 4)
D2 = date(1999, 1, 5)
D3 = date(2015, 10, 16)  # == DEV_END
POST = date(2015, 10, 19)  # first session after DEV_END

MEMBERS = ("AAA", "BBB", "BRK.B", "CCC", "DDD", "GONE")
SERVED = tuple(sorted(set(research.RESEARCH_ETFS) | {"AAA", "BBB", "BRK.B", "CCC"}))
REQUESTED = tuple(sorted(set(research.RESEARCH_ETFS) | set(MEMBERS)))


# ---- fakes ---------------------------------------------------------------------------------


def bar_rows(*days, base=10.0):
    return [(d, base, base + 1, base - 1, base + 0.5, 1000 + i) for i, d in enumerate(days)]


def ticker_frame(rows, divs):
    """One ticker's yfinance actions=True frame. rows: [(date, o, h, l, c, v)]; divs: {date: amount}."""
    index = pd.DatetimeIndex([pd.Timestamp(r[0]) for r in rows], name="Date")
    data = [
        [o, h, l, c, round(c * 0.9, 6), v, float(divs.get(d, 0.0)), 0.0]
        for (d, o, h, l, c, v) in rows
    ]
    return pd.DataFrame(data, index=index, columns=pd.Index(COLS, name="Price"), dtype=float)


def multi_frame(by_ticker):
    """yfinance 1.x group_by='ticker' shape: MultiIndex (Ticker, Price), NaN-filled."""
    frames = {t: ticker_frame(rows, divs) for t, (rows, divs) in by_ticker.items()}
    return pd.concat(
        list(frames.values()), axis=1, keys=list(frames), names=["Ticker", "Price"], sort=True
    )


def default_data():
    """yahoo ticker -> (rows, dividends). GONE is absent; DDD only after DEV_END."""
    data = {etf: (bar_rows(D1, D2, D3, base=50.0), {}) for etf in research.RESEARCH_ETFS}
    data["SPY"] = (bar_rows(PRE, D1, D2, D3, POST, base=100.0), {D2: 0.25, POST: 0.5})
    data["AAA"] = (bar_rows(D1, D2, D3), {D2: 2.65 / 28, D3: 0.0})
    data["BBB"] = (bar_rows(D1, D3, base=20.0), {})
    data["BRK-B"] = (bar_rows(D2, D3, base=70.123456), {})
    data["CCC"] = (bar_rows(D3, POST), {})
    data["DDD"] = (bar_rows(POST), {POST: 1.0})
    return data


class FakeYahoo:
    """Injected downloader. Ignores the date range on purpose (the store must clip)."""

    def __init__(self, data, *, rate_limits=0, missing=()):
        self.data = data
        self.rate_limits = rate_limits
        self.missing = set(missing)
        self.calls: list[tuple[list[str], date, date]] = []

    def __call__(self, tickers, start, end_exclusive):
        self.calls.append((list(tickers), start, end_exclusive))
        if self.rate_limits > 0:
            self.rate_limits -= 1
            raise yahoo.RateLimited("Too Many Requests. Rate limited.")
        by_ticker = {}
        for t in tickers:
            by_ticker[t] = ([], {}) if t in self.missing else self.data.get(t, ([], {}))
        return multi_frame(by_ticker)


def fake_fx(start, end):
    assert (start, end) == (research.FX_START, research.DEV_END)
    return [(D1, Decimal("8002")), (D2, 8010.5), (POST, Decimal("13600"))]


class Sleeps(list):
    def __call__(self, seconds):
        self.append(seconds)


@pytest.fixture
def members_dir(tmp_path):
    d = tmp_path / "members"
    d.mkdir()
    (d / "sp500_history.csv").write_text(
        "date,tickers\n"
        '1996-01-02,"AAA,BBB,GONE"\n'
        '2000-01-03,"AAA,BBB,BRK.B,CCC"\n'
        '2016-01-04,"AAA,CCC,NEW"\n',
        encoding="utf-8",
    )
    (d / "ndx_history.csv").write_text('date,tickers\n2007-02-01,"AAA,DDD"\n', encoding="utf-8")
    (d / "membership_overrides.csv").write_text("date,index_id,action,ticker,note\n", encoding="utf-8")
    (d / "ticker_aliases.csv").write_text("old,new,effective_date,note\n", encoding="utf-8")
    return d


def build(store, members_dir, *, fake=None, fetch_fx=fake_fx, sleeps=None, batch_size=40):
    return research.build_store(
        store,
        downloader=fake if fake is not None else FakeYahoo(default_data()),
        fetch_fx=fetch_fx,
        sleep=sleeps if sleeps is not None else Sleeps(),
        batch_size=batch_size,
        data_dir=members_dir,
    )


def read(store, name):
    return (store / name).read_text(encoding="utf-8")


def reseal(store):
    """Re-hash the data files into the manifest, as if the store had been built that way."""
    manifest = json.loads(read(store, research.MANIFEST_FILE))
    files = {n: research.file_sha256(store / n) for n in research.DATA_FILES}
    manifest["files"] = files
    manifest["fingerprint"] = research.fingerprint_of(files)
    (store / research.MANIFEST_FILE).write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )


# ---- constants and membership --------------------------------------------------------------


def test_constants_match_the_contract():
    assert research.DEV_END == date(2015, 10, 16)
    assert research.STORE_START == date(1993, 1, 29)
    assert research.MEMBERSHIP_START == date(1996, 1, 2)
    assert research.FX_START == date(1999, 1, 4)
    assert research.STORE_DIR == config.REPO_ROOT / "engine" / ".research"
    assert research.RESEARCH_ETFS == tuple(sorted(set(research.RESEARCH_ETFS)))
    assert len(research.RESEARCH_ETFS) == 21
    assert research.SECTOR_ETFS == ("XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY")
    assert set(research.SECTOR_ETFS) <= set(research.RESEARCH_ETFS)
    assert {"SPY", "QQQ", "BIL", "TLT", "SSO", "QLD"} <= set(research.RESEARCH_ETFS)


def test_store_dirs_are_gitignored():
    lines = (config.REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    for entry in ("engine/.research/", "engine/.research.tmp/", "engine/.research.old/"):
        assert entry in lines


def test_requested_symbols_are_etfs_and_dev_window_members(members_dir):
    assert research.requested_symbols(members_dir) == REQUESTED
    assert "NEW" not in research.requested_symbols(members_dir)


def test_research_membership_is_clipped_to_the_dev_window(members_dir):
    m = research.research_membership(members_dir)
    assert m.symbols() == tuple(sorted(MEMBERS))
    assert ("GONE", date(1996, 1, 2), date(2000, 1, 3)) in m.intervals
    assert ("BBB", date(1996, 1, 2), None) in m.intervals  # ended 2016-01-04: clipped to None
    assert ("AAA", date(1996, 1, 2), None) in m.intervals  # SP500 + NDX merged
    assert all(end is None or end <= research.DEV_END for _, _, end in m.intervals)
    assert m.members_on(date(2000, 1, 3)) == frozenset({"AAA", "BBB", "BRK.B", "CCC"})
    assert m.members_on(date(2010, 1, 4)) == frozenset({"AAA", "BBB", "BRK.B", "CCC", "DDD"})


# ---- yahoo: dividends-aware parse ----------------------------------------------------------


def test_parse_frame_actions_reads_bars_and_dividends():
    frame = multi_frame(
        {
            "AAA": (bar_rows(D1, D2), {D2: 2.65 / 28}),
            "BRK-B": (bar_rows(D1), {D1: 0.0}),
            "ZZZ": ([], {}),
        }
    )
    got = yahoo.parse_frame_actions(frame, ["AAA", "BRK-B", "ZZZ", "QQQQ"])
    assert list(got) == ["AAA", "BRK.B", "ZZZ", "QQQQ"]
    assert got["AAA"].bars == tuple(yahoo.parse_frame(frame, ["AAA", "BRK-B"])["AAA"])
    assert [b.date for b in got["AAA"].bars] == [D1, D2]
    assert got["AAA"].dividends == ((D2, Decimal("0.094643")),)
    assert got["BRK.B"].dividends == ()
    assert len(got["BRK.B"].bars) == 1
    assert got["ZZZ"] == yahoo.EMPTY_HISTORY
    assert got["QQQQ"] == yahoo.EMPTY_HISTORY


def test_parse_frame_actions_flat_frame_and_none():
    flat = ticker_frame(bar_rows(D1, D2), {D1: 0.5})
    got = yahoo.parse_frame_actions(flat, ["SPY"])
    assert got["SPY"].dividends == ((D1, Decimal("0.500000")),)
    assert len(got["SPY"].bars) == 2
    no_divs = flat.drop(columns=["Dividends"])
    assert yahoo.parse_frame_actions(no_divs, ["SPY"])["SPY"].dividends == ()
    assert yahoo.parse_frame_actions(None, ["SPY"]) == {"SPY": yahoo.EMPTY_HISTORY}


def test_download_actions_maps_tickers():
    fake = FakeYahoo(default_data())
    got = yahoo.download_actions(["brk.b", "AAA", "AAA"], D1, D2, downloader=fake)
    assert fake.calls == [(["BRK-B", "AAA"], D1, D2)]
    assert list(got) == ["BRK.B", "AAA"]
    assert got["BRK.B"].bars[0].symbol == "BRK.B"


# ---- build ---------------------------------------------------------------------------------


def test_build_writes_sorted_files_and_manifest(tmp_path, members_dir):
    store = tmp_path / "store"
    manifest = build(store, members_dir)
    assert sorted(p.name for p in store.iterdir()) == sorted(
        [*research.DATA_FILES, research.MANIFEST_FILE]
    )
    assert set(manifest) == research.MANIFEST_KEYS
    assert manifest == json.loads(read(store, research.MANIFEST_FILE))
    assert read(store, research.MANIFEST_FILE) == json.dumps(manifest, sort_keys=True, indent=2) + "\n"
    assert manifest["dev_end"] == "2015-10-16"
    assert manifest["store_start"] == "1993-01-29"
    assert manifest["symbols_requested"] == len(REQUESTED) == 27
    assert manifest["symbols_served"] == len(SERVED) == 25
    assert manifest["bar_rows"] == 71
    assert manifest["dividend_rows"] == 2
    assert manifest["fx_rows"] == 2
    assert manifest["files"] == {n: research.file_sha256(store / n) for n in research.DATA_FILES}
    assert manifest["fingerprint"] == research.fingerprint_of(manifest["files"])

    bar_lines = read(store, research.BARS_FILE).splitlines()
    assert bar_lines[0] == research.BARS_HEADER
    keys = [(line.split(",")[0], line.split(",")[1]) for line in bar_lines[1:]]
    assert keys == sorted(keys)
    assert [s for s in dict.fromkeys(k[0] for k in keys)] == list(SERVED)
    assert all(research.STORE_START.isoformat() <= d <= "2015-10-16" for _, d in keys)
    assert read(store, research.UNSERVED_FILE) == (
        "symbol,reason\n"
        f"DDD,{research.UNSERVED_REASON}\n"
        f"GONE,{research.UNSERVED_REASON}\n"
    )
    assert not (tmp_path / "store.tmp").exists()
    assert not (tmp_path / "store.old").exists()


def test_build_file_formats(tmp_path, members_dir):
    store = tmp_path / "store"
    build(store, members_dir)
    bars_text = read(store, research.BARS_FILE)
    assert "AAA,1999-01-04,10.0000,11.0000,9.0000,10.5000,1000\n" in bars_text
    assert "BRK.B,1999-01-05,70.1235,71.1235,69.1235,70.6235,1000\n" in bars_text
    assert "SPY,1993-01-28," not in bars_text  # before STORE_START
    assert "2015-10-19" not in bars_text  # after DEV_END
    assert read(store, research.DIVIDENDS_FILE) == (
        "symbol,ex_date,amount\nAAA,1999-01-05,0.094643\nSPY,1999-01-05,0.25\n"
    )
    assert read(store, research.FX_FILE) == "date,usd_idr\n1999-01-04,8002.0000\n1999-01-05,8010.5000\n"
    for name in research.DATA_FILES:
        assert "\r" not in read(store, name)


def test_build_is_deterministic_across_runs_and_batch_sizes(tmp_path, members_dir):
    a, b, c = tmp_path / "a", tmp_path / "b", tmp_path / "c"
    ma = build(a, members_dir, batch_size=40)
    mb = build(b, members_dir, batch_size=40)
    mc = build(c, members_dir, batch_size=5)
    assert ma == mb == mc
    for name in (*research.DATA_FILES, research.MANIFEST_FILE):
        assert (a / name).read_bytes() == (b / name).read_bytes() == (c / name).read_bytes()
    build(a, members_dir)  # rebuilding in place gives the same fingerprint
    assert json.loads(read(a, research.MANIFEST_FILE))["fingerprint"] == ma["fingerprint"]


def test_build_backs_off_and_retries_empties_individually(tmp_path, members_dir):
    fake = FakeYahoo(default_data(), rate_limits=1)
    sleeps = Sleeps()
    build(tmp_path / "store", members_dir, fake=fake, sleeps=sleeps)
    assert sleeps == [60.0, research.BATCH_PAUSE_S, research.BATCH_PAUSE_S]
    assert [call[0] for call in fake.calls] == [
        [yahoo.to_yahoo(s) for s in REQUESTED],
        [yahoo.to_yahoo(s) for s in REQUESTED],
        ["DDD"],
        ["GONE"],
    ]
    assert all(
        (start, end) == (research.STORE_START, research.DEV_END + timedelta(days=1))
        for _, start, end in fake.calls
    )


def test_build_aborts_on_unserved_etf_and_keeps_the_old_store(tmp_path, members_dir):
    store = tmp_path / "store"
    build(store, members_dir)
    before = {n: (store / n).read_bytes() for n in (*research.DATA_FILES, research.MANIFEST_FILE)}
    with pytest.raises(research.ResearchStoreError, match="GLD"):
        build(store, members_dir, fake=FakeYahoo(default_data(), missing={"GLD"}))
    assert {n: (store / n).read_bytes() for n in before} == before
    assert not (tmp_path / "store.tmp").exists()


def test_build_aborts_when_rate_limited_out(tmp_path, members_dir):
    store = tmp_path / "store"
    sleeps = Sleeps()
    with pytest.raises(research.ResearchStoreError, match="rate limited"):
        build(store, members_dir, fake=FakeYahoo(default_data(), rate_limits=10), sleeps=sleeps)
    assert sleeps == list(research.RATE_LIMIT_BACKOFF_S)
    assert not store.exists()
    assert not (tmp_path / "store.tmp").exists()


def test_build_rejects_bad_batch_size_and_bad_fx(tmp_path, members_dir):
    with pytest.raises(ValueError, match="batch_size"):
        build(tmp_path / "s0", members_dir, batch_size=0)

    def conflicting(start, end):
        return [(D1, Decimal("8002")), (D1, Decimal("8003"))]

    def nothing(start, end):
        return [(POST, Decimal("13600"))]

    with pytest.raises(research.ResearchStoreError, match="conflicting"):
        build(tmp_path / "s1", members_dir, fetch_fx=conflicting)
    with pytest.raises(research.ResearchStoreError, match="no USD/IDR rows"):
        build(tmp_path / "s2", members_dir, fetch_fx=nothing)
    assert not (tmp_path / "s1").exists() and not (tmp_path / "s2").exists()


# ---- load ----------------------------------------------------------------------------------


def test_load_store_round_trip(tmp_path, members_dir):
    store = tmp_path / "store"
    manifest = build(store, members_dir)
    data = research.load_store(store, data_dir=members_dir)
    assert data.fingerprint == manifest["fingerprint"]
    assert data.manifest == manifest
    assert tuple(data.market.history) == SERVED
    assert data.market.history["SPY"].dates.tolist() == [D1, D2, D3]
    assert data.market.bar("BRK.B", D2).close == Decimal("70.6235")
    assert data.market.bar("AAA", D1).volume == 1000
    assert data.market.fx == ((D1, Decimal("8002.0000")), (D2, Decimal("8010.5000")))
    assert data.dividends == {"AAA": {D2: Decimal("0.094643")}, "SPY": {D2: Decimal("0.25")}}
    assert data.spy_dividends == (Dividend(ex_date=D2, amount=Decimal("0.25")),)
    assert data.unserved == ("DDD", "GONE")
    assert data.market.membership.members_on(date(2000, 1, 3)) == frozenset(
        {"AAA", "BBB", "BRK.B", "CCC"}
    )


@pytest.mark.parametrize("name", research.DATA_FILES)
def test_load_store_rejects_a_tampered_file(tmp_path, members_dir, name):
    store = tmp_path / "store"
    build(store, members_dir)
    with (store / name).open("a", encoding="utf-8", newline="\n") as fh:
        fh.write("X\n")
    with pytest.raises(ValueError, match=f"{name}: sha256"):
        research.load_store(store, data_dir=members_dir)


def test_load_store_rejects_a_bad_fingerprint(tmp_path, members_dir):
    store = tmp_path / "store"
    build(store, members_dir)
    manifest = json.loads(read(store, research.MANIFEST_FILE))
    manifest["fingerprint"] = "0" * 64
    (store / research.MANIFEST_FILE).write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="fingerprint"):
        research.load_store(store, data_dir=members_dir)


def test_load_store_rejects_a_store_built_for_another_dev_end(tmp_path, members_dir):
    store = tmp_path / "store"
    build(store, members_dir)
    manifest = json.loads(read(store, research.MANIFEST_FILE))
    manifest["dev_end"] = "2015-12-31"
    (store / research.MANIFEST_FILE).write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="dev_end"):
        research.load_store(store, data_dir=members_dir)


@pytest.mark.parametrize(
    ("name", "old", "new"),
    [
        (research.BARS_FILE, "SPY,2015-10-16,", "SPY,2015-10-19,"),
        (research.DIVIDENDS_FILE, "SPY,1999-01-05,", "SPY,2015-10-19,"),
        (research.FX_FILE, "1999-01-05,", "2015-10-19,"),
    ],
)
def test_load_store_rejects_rows_after_dev_end(tmp_path, members_dir, name, old, new):
    store = tmp_path / "store"
    build(store, members_dir)
    text = read(store, name)
    assert text.count(old) == 1
    (store / name).write_text(text.replace(old, new), encoding="utf-8", newline="\n")
    reseal(store)  # hashes match again: only the D9 date guard can catch it
    with pytest.raises(ValueError, match="after DEV_END 2015-10-16"):
        research.load_store(store, data_dir=members_dir)


def test_load_store_rejects_a_missing_store(tmp_path):
    with pytest.raises(ValueError, match="no research store"):
        research.load_store(tmp_path / "nope")


def _imported_names(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            names.add(base)
            names |= {f"{base}.{a.name}" for a in node.names}
    return names


def test_no_neon_and_no_database_url_needed(tmp_path, members_dir, monkeypatch):
    def no_db(*args, **kwargs):
        raise AssertionError("the research store must never connect to a database")

    monkeypatch.setattr(db, "connect", no_db)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL_UNPOOLED", raising=False)
    store = tmp_path / "store"
    build(store, members_dir)
    assert research.load_store(store, data_dir=members_dir).fingerprint
    for module in (research, research_cmd):
        names = _imported_names(Path(module.__file__))
        assert not {n for n in names if n == "seer_engine.db" or n.startswith("psycopg")}, module


# ---- per-year unserved and verification ----------------------------------------------------


def test_unserved_by_year(members_dir):
    table = research.unserved_by_year(research.research_membership(members_dir), ["DDD", "GONE"])
    assert [y for y, _, _ in table] == list(range(1996, 2016))
    rows = {y: (m, u) for y, m, u in table}
    assert rows[1996] == (3, 1)  # AAA, BBB, GONE
    assert rows[2000] == (5, 1)  # GONE still a member until 2000-01-03
    assert rows[2001] == (4, 0)
    assert rows[2007] == (5, 1)  # DDD joins NDX
    assert rows[2015] == (5, 1)


def test_check_spy_sessions(tmp_path, members_dir):
    store = tmp_path / "store"
    build(store, members_dir)
    data = research.load_store(store, data_dir=members_dir)
    assert research.check_spy_sessions(data, start=D1, end=D2).ok
    full = research.check_spy_sessions(data)
    assert not full.ok
    assert full.name == "spy-sessions"
    assert "5721 NYSE sessions 1993-02-01..2015-10-16, 5718 without a SPY bar" in full.detail


def test_check_spy_dividends(tmp_path, members_dir):
    store = tmp_path / "store"
    build(store, members_dir)
    data = research.load_store(store, data_dir=members_dir)
    assert research.check_spy_dividends(data, (Dividend(D2, Decimal("0.250")),)).ok
    assert not research.check_spy_dividends(data, (Dividend(D2, Decimal("0.26")),)).ok
    assert not research.check_spy_dividends(
        data, (Dividend(D1, Decimal("0.1")), Dividend(D2, Decimal("0.25")))
    ).ok
    assert not research.check_spy_dividends(data, ()).ok


def test_check_dividend_scale(tmp_path, members_dir):
    store = tmp_path / "store"
    build(store, members_dir)
    data = research.load_store(store, data_dir=members_dir)
    good = research.check_dividend_scale(data, symbol="AAA", year=1999)
    assert good.ok and "0.094643 / close 10.5000" in good.detail
    assert not research.check_dividend_scale(data, symbol="BBB", year=1999).ok  # no dividends
    unadjusted = dataclasses.replace(data, dividends={"AAA": {D2: Decimal("2.65")}})
    assert not research.check_dividend_scale(unadjusted, symbol="AAA", year=1999).ok
    assert [c.name for c in research.run_checks(data, ())] == [
        "spy-sessions",
        "spy-dividends",
        "dividend-scale-AAPL-2012",
    ]


# ---- command -------------------------------------------------------------------------------


def test_command_verify_prints_fingerprint_and_checks(tmp_path, members_dir, capsys):
    store = tmp_path / "store"
    manifest = build(store, members_dir)
    code = cli.main(["research_store", "--verify", "--store", str(store)])
    out = capsys.readouterr().out
    assert code == 1  # the fake store fails the real-data checks
    assert f"fingerprint: {manifest['fingerprint']}" in out
    assert "symbols: 25 served of 27 requested, 2 unserved" in out
    assert "rows: 71 bars, 2 dividends, 2 fx" in out
    assert "check spy-sessions: FAIL" in out


def test_command_verify_missing_store_exits_2(tmp_path, capsys):
    assert cli.main(["research_store", "--verify", "--store", str(tmp_path / "nope")]) == 2
    assert capsys.readouterr().out == ""


def test_command_builds_the_store(tmp_path, members_dir, monkeypatch, capsys):
    fake = FakeYahoo(default_data())
    monkeypatch.setattr(
        research,
        "build_store",
        functools.partial(
            research.build_store, downloader=fake, fetch_fx=fake_fx, sleep=Sleeps(), data_dir=members_dir
        ),
    )
    store = tmp_path / "store"
    code = cli.main(["research_store", "--store", str(store), "--batch-size", "7"])
    out = capsys.readouterr().out
    assert code == 1  # built fine; the real-data checks fail on fake data
    manifest = json.loads(read(store, research.MANIFEST_FILE))
    assert f"fingerprint: {manifest['fingerprint']}" in out
    assert len(fake.calls) == 4 + 2  # ceil(27 / 7) batches + DDD and GONE individually


def test_command_dry_run_keeps_nothing(tmp_path, members_dir, monkeypatch, capsys):
    monkeypatch.setattr(
        research,
        "build_store",
        functools.partial(
            research.build_store,
            downloader=FakeYahoo(default_data()),
            fetch_fx=fake_fx,
            sleep=Sleeps(),
            data_dir=members_dir,
        ),
    )
    store = tmp_path / "store"
    cli.main(["--dry-run", "research_store", "--store", str(store)])
    out = capsys.readouterr().out
    assert "dry run: built in a temporary directory and discarded" in out
    assert not store.exists()
```

**Notes for the implementer:**
- **`test_command_builds_the_store`:** `functools.partial(research.build_store, ...)` is
  evaluated before `monkeypatch.setattr` replaces the attribute, so the partial wraps the real
  function. The command calls `research.build_store(target, batch_size=7)`, which reaches the
  partial.
- **`test_command_dry_run_keeps_nothing`:** `cli` sets `args.dry_run` from the flag placed
  before the command name.
- **The command tests call `load_store(store)` without `data_dir`.** It reads the real
  vendored membership CSVs offline. That only affects membership (and the per-year table),
  not the counts or the fingerprint.
- **`test_check_spy_sessions` calls `dates.sessions`.** That uses `pandas_market_calendars`
  offline, as `backtest.benchmark` does in other tests. The 5721 figure was measured
  2026-10-03.
- **Other tests are unaffected.** `conftest._isolated_env` points `DATABASE_URL_UNPOOLED` at
  an invalid host. `test_no_neon_and_no_database_url_needed` deletes it and patches
  `db.connect`, which proves no code path reaches a connection.

**Impact:** +34 collected tests, none skipped.

### Step 6: The real build (network) and the three verifications
**Where:** the worktree root `/home/miftah/.worktrees/seer/trade-rules-dev-search`, using the
worktree's own venv. It needs no `DATABASE_URL` and no `SEER_ENV_FILE`.

1. **Run the build in the background** (about 27 batches; the ~400 unserved members each get a
   3 s pause plus an individual call, so expect 30–60 min):
   ```bash
   cd /home/miftah/.worktrees/seer/trade-rules-dev-search
   engine/.venv/bin/python -m seer_engine research_store 2>&1 | tee <scratchpad>/research_store_build.log
   ```
   - Exit 0 means the build succeeded **and** all three checks passed.
   - Exit 1 after a successful build means a check failed. Read the `check ...: FAIL` line and
     investigate. **Do not relax a check to make it pass.**
   - If the build was rate limited out (exit 1, `ResearchStoreError`), wait and re-run. The
     previous store, if any, is intact.
2. **Re-verify offline** and confirm the store is stable:
   ```bash
   engine/.venv/bin/python -m seer_engine research_store --verify
   git status --short          # must not list engine/.research*
   du -sh engine/.research     # record the size
   ```
3. **Record in the phase log:**
   - the fingerprint;
   - `symbols_requested` and `symbols_served`, and the unserved count;
   - `bar_rows`, `dividend_rows` and `fx_rows`;
   - the "unserved members by year" table;
   - the three check lines verbatim;
   - the build's wall time and the store size.

The three checks, and what passing means:

| Check | Pass condition | Expected on real data |
|---|---|---|
| `spy-sessions` | SPY has a bar on every NYSE session from 1993-02-01 to 2015-10-16 | 5721 sessions, 0 missing (probed: 5722 SPY bars from 1993-01-29) |
| `spy-dividends` | the store's SPY dividends from 2015-03-20 to 2015-10-16 equal `engine/data/spy_dividends.csv` on the same range | 2015-03-20=0.931, 2015-06-19=1.03, 2015-09-18=1.033 on both sides (probed) |
| `dividend-scale-AAPL-2012` | each 2012 AAPL dividend is between 0.1% and 2% of the prior split-adjusted close | 2012-08-09: 0.094643 / ~22.17 ≈ 0.43%; 2012-11-07 similar (probed: the yfinance dividend is split-adjusted) |

**Impact:** a gitignored directory of about 150–250 MB appears in `engine/.research/`. Nothing
is committed and nothing touches Neon.

## Verification

**Build:** `cd /home/miftah/.worktrees/seer/trade-rules-dev-search && engine/.venv/bin/python -c "import seer_engine.research, seer_engine.commands.research_store"`

**Tests:**
```bash
docker start seer-pg
cd /home/miftah/.worktrees/seer/trade-rules-dev-search
engine/.venv/bin/pytest engine/tests/test_research_store.py -q             # 35 passed
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q
```
- The full suite must report **0 skipped**.
- Its passed count is the phase-start count + 34. That is 970 + 34 = 1004 if this phase lands
  first on `2546a92`. Otherwise, add 34 to whatever the tree held when the phase began.

**Frozen set:** `git diff --stat 2546a92 -- engine/src/seer_engine/membership.py engine/src/seer_engine/fx.py engine/src/seer_engine/commands/backfill.py engine/src/seer_engine/backtest/runner.py engine/src/seer_engine/backtest/market.py engine/src/seer_engine/backtest/benchmark.py engine/src/seer_engine/backtest/metrics.py engine/src/seer_engine/backtest/walkforward.py engine/src/seer_engine/backtest/wf_report.py engine/src/seer_engine/backtest/report.py engine/src/seer_engine/backtest/tuning.py engine/src/seer_engine/backtest/labels.py engine/src/seer_engine/backtest/b_walkforward.py engine/src/seer_engine/backtest/b_report.py engine/src/seer_engine/backtest/io.py engine/src/seer_engine/sim/model.py engine/src/seer_engine/sim/lifecycle.py engine/src/seer_engine/sim/sizing.py engine/src/seer_engine/strategies/base.py engine/src/seer_engine/cli.py`
must print nothing.

`git diff 2546a92 -- engine/src/seer_engine/yahoo.py` must show only:
- the two import lines;
- the appended block.

**Manual check:** Step 6. The real build, `--verify` exiting 0, and the logged counts,
fingerprint and per-year unserved table.

**Exit criteria:**
- The suite is green with 0 skipped.
- `build_store` run twice on the same fake downloads gives byte-identical files and the same
  fingerprint, even across batch sizes.
- `load_store` rejects a tampered file and a row dated after 2015-10-16 in each of the bars,
  dividends and fx files.
- Unserved members are recorded in `unserved.csv`.
- Nothing imports `seer_engine.db`.
- The real store in the worktree passes all three checks: `research_store --verify` exits 0.
- Its fingerprint and counts are in the phase log.

## Handoffs

- **Phase 9 (`backtest/dev.py`, R4 code-level guard):**
  - It must define its own `DEV_END = date(2015, 10, 16)`, `MEMBERSHIP_START` and `FX_START`.
    It must not import `seer_engine.research`, because that would break `dev.py`'s purity:
    `research` → `yahoo` → `bars` → `psycopg`.
  - The equality tests (`dev.DEV_END == research.DEV_END`, `MEMBERSHIP_START`, `FX_START`)
    live in phase 12's test file (plan index D-I), not in phase 9's.
- **Phase 12 (`commands/backtest_dev.py`):**
  - Load with `research.load_store(args.store)`, where `--store` defaults to
    `research.STORE_DIR`.
  - Pass `data.market`, `data.dividends` and `data.spy_dividends` to `dev.run_registry`.
  - Pass `data.fingerprint` as `DevReport.store_fingerprint`.
  - Pass `data.unserved` as `DevReport.unserved`.
  - Pass the five manifest count keys as `store_counts`.
  - On a `ValueError` from `load_store`, exit 2 with its message. A missing store is a
    `ValueError` ("no research store … manifest.json missing"), not a `FileNotFoundError`.
  - Its test fixture builds a synthetic store with `build_store`; the fake downloader must serve
    **every** `RESEARCH_ETFS` symbol, or the build aborts (interface note 5).
- **Phase 10 / 13 (report text):**
  - The survivorship caveat (D4) should cite the per-year table, which `research_store
    --verify` prints and phase 4's log records. It should also say that yfinance's surviving
    tickers can be reused tickers.
  - Example from the 2026-10-03 symbol list: `ARNC` and `AT` exist in the 1996 snapshot. A
    reused ticker can silently map an old member to a different company's history. That is
    not detectable here.
- **Not owned by any phase (optional cleanup, deliberately not done):**
  - `yahoo.yf_download` and `yahoo.yf_download_actions` differ only in `actions=`. Merging them
    would edit an existing function, which this phase's scope forbids.
  - `research._download_with_backoff` mirrors `backfill._download_with_backoff` for the same
    reason: `backfill.py` must not be touched.

## Rollback

- `git revert` this phase's commit(s). That removes:
  - `research.py`, `commands/research_store.py` and `tests/test_research_store.py`;
  - the appended `yahoo.py` block and its two import changes;
  - the three `.gitignore` lines.
- `rm -rf engine/.research engine/.research.tmp engine/.research.old` deletes the local store.
- Neon is never touched, so there is nothing to undo there.

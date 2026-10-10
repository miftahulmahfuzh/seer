# Phase 3: Market series store file, `Market.series`, `lab unblock`

**Plan set:** `EODHD_SURVIVORSHIP_MARKET_PLAN.md`
**Analysis:** `20261010-181548-E7HD_code_analyzer.md`
**Satisfies:** R8 (market series that allocators read point in time, price fingerprint fixed, scaling checked against known yields — the real stores get the file in phase 5 (SV) and post-landing L1 (dev)), R9 (`lab unblock` and the measured coverage notes; the two status moves run as post-landing L2, once the data loads on `main`)
**Depends on:** Phase 1 (both phases edit `research.py`; phase 1 adds `SV_STORE_DIR`, the `purpose` manifest key and `ResearchData.purpose`)
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine` (`research`, `backtest/market`, `lab/runner`, `commands/market_series`, `commands/lab`)

---

## Goal

A research store can carry an optional `market_series.csv` holding ten market series: VIX, VIX3M
(VXV before it), VIX9D, VXN, VVIX, T13W, T5Y, T10Y, T30Y and GOLD. Yields are in percent, the VIX
family in points and gold in USD/oz. `research.load_store` reads the file into
`Market.series`, a `MarketSeries` that never shows a value dated after the allocator's `data_date`.
The price fingerprint (`DATA_FILES` only) does not move. A cache-only command writes the file into
a store; this phase proves it on scratch copies of the dev store and the survivorship-check store.
`lab unblock` moves an idea from `blocked-data` back to `idea` with a note.

**What this phase does NOT do to real data (Decision D8, D9):** the main checkout's code — which
the live Sera batch runs — refuses any store whose manifest lists a file outside its own
`OPTIONAL_DATA_FILES`, so writing `market_series.csv` into `/home/miftah/seer/engine/.research`
before this code is on `main` would break every `lab run` in the main checkout. The real dev store
refresh, its Blob push and the two `lab unblock` calls for M0039/M0038 are therefore the set's
**post-landing steps L1-L3** (plan index), run by the lander in the main checkout, with its venv, right after the set merges to `main`.
The real SV store gets the file in phase 5, after its final rebuild (phase 2 may rebuild it in
parallel with this phase).

## Measured facts this plan relies on (probed 2026-10-10 from `/home/miftah/seer/engine/.cache/eodhd/market/`)

Every cache file is a bare JSON list of `{date, open, high, low, close, adjusted_close, volume}`,
sorted ascending, with unique dates and no null or non-finite closes. (The reader still handles
nulls.) Rules applied: keep `STORE_START (1993-01-29) <= date <= 2015-10-16`, keep NYSE sessions
only (`dates.is_session`), and use `close`.

| Series | Source (preference order) | Divisor | Rows kept | First..last kept | Off-session rows dropped | Member sessions covered (of 4,984, 1996-01-02..2015-10-16) | Min..max after normalization |
|---|---|---|---|---|---|---|---|
| GOLD | XAUUSD.FOREX | 1 | 5,722 | 1993-01-29..2015-10-16 | 192 | 4,984 (100.0%) | 252.55..1898.1 |
| T10Y | TNX.INDX | 10 | 5,508 | 1993-11-02..2015-10-16 | 1 (2011-09-05) | 4,966 (99.6%) | 1.404..8.023 |
| T13W | IRX.INDX | 1 | 5,722 | 1993-01-29..2015-10-16 | 204 | 4,984 (100.0%) | 0.003..6.22 |
| T30Y | TYX.INDX | 10 | 5,529 | 1993-11-03..2015-10-16 | 62 | 4,984 (100.0%) | 2.251..8.159 |
| T5Y | FVX.INDX | 10 | 5,508 | 1993-11-02..2015-10-16 | 1 | 4,966 (99.6%) | 0.551..7.896 |
| VIX | VIX.INDX | 1 | 5,722 | 1993-01-29..2015-10-16 | 3 (2001-09-11, 2004-06-11, 2011-09-05) | 4,984 (100.0%) | 9.31..80.86 |
| VIX3M | VIX3M.INDX, else VXV.INDX | 1 | 2,331 (VIX3M 1,996 + VXV 335) | 2006-07-17..2015-10-16 | 1 | 2,331 (46.8%) | 11.03..69.24 |
| VIX9D | VIX9D.INDX | 1 | 1,206 | 2011-01-03..2015-10-16 | 0 | 1,206 (24.2%) | 8.54..68 |
| VVIX | VVIX.INDX | 1 | 2,362 | 2006-03-06..2015-10-16 | 0 | 2,362 (47.4%) | 15.71..168.75 |
| VXN | VXN.INDX | 1 | 3,707 | 2001-01-23..2015-10-16 | 1 | 3,707 (74.4%) | 11.36..82.49 |
| **total** | | | **43,317** | | | | |

**Scaling checks against known yields** (vendor close, then normalized, then the published U.S.
Treasury constant-maturity yield for the same day):
- TNX 2000-01-03: 65.48 → **6.548%** (published 10-year 6.58%). 2012-07-25: 14.06 → **1.406%**
  (that summer's record low of about 1.43%). 2015-10-16: 20.23 → **2.023%** (published 2.03%).
- FVX 2012-07-25: 5.55 → **0.555%** (published 5-year 0.55%). 2000-01-03: 64.57 → 6.457%.
- TYX 2008-12-18: 25.46 → **2.546%** (the December 2008 30-year low of about 2.5%).
  2000-01-03: 65.98 → 6.598%.
- IRX is already in percent: 2000-01-03 5.27; 2008-12-18 0.005; minimum in the window 0.003 on
  2013-09-16. It is never zero or negative in the window.
- VIX 2008-11-20: 80.86, the record close. Gold 2011-09-06: 1873.72. (2011-09-05 was Labor Day, so
  the 1900.49 row is dropped as off-session.)

**VIX3M and VXV agreement:** in the dev window they overlap on 1,996 sessions, 2007-11-13 to
2015-10-16. They agree on 1,987 of them and differ on 9. The **max absolute difference is 1.05
points, on 2014-10-15** (VXV 22.77, VIX3M 23.82). The other differences are 0.34 (2014-12-09),
0.25, 0.08, 0.06, 0.03, 0.02, 0.01 and 0.01, all in 2014. VIX3M is preferred on every date it has
a value, so VXV supplies only the 335 sessions from 2006-07-17 to 2007-11-12. In the full cache,
outside the window, the max difference is still 1.05; the next largest is 0.44 on 2019-09-23.

**Coverage for the unblock notes:** the dev window holds members on 4,984 sessions, 1996-01-02 to
2015-10-16, which is 19.79 years.
- M0039 (VIX vs VIX3M): both series exist on 2,331 of the 4,984 sessions (46.8%), 2006-07-17 to
  2015-10-16, which is 9.25 of 19.79 years. The mid-1998 fall the hypothesis cites is **not**
  covered, and neither is 2000-2002.
- M0038 (term spread T10Y − T13W): both series exist on 4,966 of the 4,984 sessions (99.6%). The 18
  sessions without a 10-year value are bond-market holidays (Columbus Day and Veterans Day; see the
  probe list). On those days `value_on` returns the previous close. The spread is therefore
  available across the whole dev member window (19.79 of 19.79 years), and its data starts
  1993-11-02. There is no 2-year series and no credit spread (BAA10Y) or real yield (DFII10): the
  paid plan returns 403 on `.GBOND` and has no corporate-yield index.

**Data caveat (not acted on):** VVIX's first weeks look implausible: 2006-03-15 15.71, then 27.94,
28.6, 37.93 and 37.35. VVIX normally sits around 60-200. D5 says "as-is", and neither M0038 nor
M0039 reads VVIX, so the rows are written unchanged and the caveat goes under Handoffs.

**Store state:** the dev store `/home/miftah/seer/engine/.research` has full fingerprint
`fd2bc190e915b0528be1520bc35ae562c5567608f581481d6e329d9143dfa753` and price fingerprint
`5451195fd552e208eaadfc6bc89241b9b8e3e6ccb0f4c447a84bbc4f32e7d90a`, with six files.
`/home/miftah/seer/engine/.research-test` **exists** (window_end 2026-10-06). This phase never
touches it.

## Interface Contract

**Deletes:** nothing.

**Renames:** nothing.

**Creates:**
- `research.MARKET_SERIES_FILE = "market_series.csv"` (`research.py`, beside `ANNOUNCEMENTS_FILE`)
- `research.MARKET_SERIES_HEADER = "series,date,value"`
- `research.MARKET_SERIES_NAMES = ("GOLD", "T10Y", "T13W", "T30Y", "T5Y", "VIX", "VIX3M", "VIX9D", "VVIX", "VXN")` (sorted)
- `research.market_series_lines(rows, *, end=DEV_END) -> list[str]`
- `research._read_market_series(path, end=DEV_END) -> dict[str, list[tuple[date, float]]]`
- `research._parse_finite(raw, where) -> float`, `research._series_value_text(value) -> str`
- `research.refresh_market_series(store_dir, rows, *, data_dir=None, window=DEV_WINDOW) -> dict`
- `backtest.market.MarketSeries` with `value_on(name, data_date) -> float | None`,
  `upto(name, data_date, *, last=None) -> tuple[tuple[date, float], ...]`, `names()`,
  `first_date(name)` and `__len__`
- `backtest.market.EMPTY_SERIES`
- `Market.series: MarketSeries = EMPTY_SERIES` (a new last dataclass field) and `Market.with_series(series)`
- New command module `commands/market_series.py`: `HELP`, `CACHE_DIR`, `Source`, `SOURCES`,
  `CacheError`, `read_ticker`, `SeriesReport`, `normalize`, `rows_for_store`, `format_report`,
  `add_arguments`, `run`
- `lab unblock MNNNN --note "..."`: subparser, `commands/lab.py:_unblock`, and the `_HANDLERS["unblock"]` entry
- New tests: `engine/tests/test_market_series.py`, `engine/tests/test_lab_unblock.py`

**Signature changes:**
- `research.OPTIONAL_DATA_FILES`: `(FUNDAMENTALS_FILE, ANNOUNCEMENTS_FILE)` -> `(FUNDAMENTALS_FILE, ANNOUNCEMENTS_FILE, MARKET_SERIES_FILE)`
- `research.load_store` now also builds `Market.series` (behaviour change only; the signature is unchanged)
- `runner.preflight_data` now also refuses a candidate whose `market_fields` includes `"series"`
  when `len(data.market.series) == 0` (the signature is unchanged)

**Requires (from earlier phases):**
- Phase 1 has landed: `research.SV_STORE_DIR`, the optional manifest key `purpose`,
  `ResearchData.purpose`, and `_seal`/`_read_manifest` accepting `purpose`.
- Phase 1's `_refresh_optional` re-seals with `purpose=before.get(PURPOSE_KEY)` (phase 1 Step 2,
  confirmed by the reconciler; phase 1's `test_a_refresh_keeps_the_mark` tests it through
  `refresh_fundamentals`). So `refresh_market_series` on a survivorship-check store keeps its
  mark; Step 13c re-checks it on a scratch copy only.
- Phase 1's SV build copies every `OPTIONAL_DATA_FILES` member the **source manifest lists** (except
  `dividend_announcements.csv`, which it re-matches). The dev store gains `market_series.csv` only
  post-landing (L1), so phase 2's and phase 5's rebuilds do not carry it; phase 5 runs
  `market_series --refresh` on the SV store after its final rebuild. Any rebuild after L1 carries it.

**Leaves alone (owned by others):** `survivorship.py`, `commands/survivorship_store.py` (phases 1
and 2); `eodhd.py` (phase 2); the purpose marker logic in `_seal`, `_read_manifest`,
`ResearchData` and `SV_STORE_DIR` (phase 1); the `run_method`/`run_test`/`remeasure` refusals
(phase 1); the `_run` refusal message in `commands/lab.py` (phase 1); the `survivorship`
subcommand and `lab/survivorship_check.py` (phase 4); every file under `lab/methods/`; the skill
docs (phase 5); `/home/miftah/seer/engine/.research-test` (nobody).

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/backtest/market.py` | modify | `import math`; `MarketSeries` + `EMPTY_SERIES` after `EMPTY_DIVIDENDS` (:168-169); `Market.series` field, type check, `with_series`, docstring (:249-320) |
| `engine/src/seer_engine/research.py` | modify | docstring file list (:16-21); `import math` (:33); market import (:56); `MARKET_SERIES_FILE` (:99); `OPTIONAL_DATA_FILES` widened + doc (:103-117); `MARKET_SERIES_HEADER`/`MARKET_SERIES_NAMES` (:124); new "market series" section after `_read_announcements` (:538); `refresh_market_series` after `refresh_announcements` (:974); `load_store` `Market(...)` gains `series=` (:1092-1105) |
| `engine/src/seer_engine/lab/runner.py` | modify | `preflight_data` (:215-256): refuse a series method on a store with no series; docstrings of `market_fields`/`preflight_data` |
| `engine/src/seer_engine/commands/market_series.py` | create | cache-only report + `--refresh` |
| `engine/src/seer_engine/commands/lab.py` | modify | module docstring line (:63); `unblock` subparser after `block` (:342-344); `_unblock` after `_block` (:2116-2119 at base; phase 1's `_run` refusal adds 8 lines at :1259, so it reads :2124-2127 after phase 1); `_HANDLERS` entry after `"block"` (:2218 base, :2226 after phase 1). Locate by the quoted anchor text |
| `engine/tests/test_market_fundamentals.py` | modify | `test_data_files_is_not_widened` (:629-640): pin the widened tuple deliberately, with a comment |
| `engine/tests/test_market_series.py` | create | `MarketSeries`, store file, reader, refresh, preflight, command |
| `engine/tests/test_lab_unblock.py` | create | `lab unblock` |

Line numbers are today's (`5e5ec5c`). Phase 1 inserts lines into `research.py` above several of
these anchors (`SV_STORE_DIR` near :69, the `purpose` key near :153, `ResearchData.purpose` near
:208, `_seal` and `_read_manifest` changes). **Locate every `research.py` edit by its anchor text,
not by its number.**

## Executor environment (do this first)

```bash
cd /home/miftah/.worktrees/seer/eodhd-survivorship-market
git branch --show-current            # must print feature/eodhd-survivorship-market
git log --oneline -3                 # phase 1's commits must be present (depends_on: [1])
grep -n "SV_STORE_DIR\|purpose" engine/src/seer_engine/research.py | head   # phase 1 landed

# 1. Phase 1 Step 0's recipe, idempotent. /home/miftah/seer/engine/.venv is an editable install
#    of the MAIN checkout and would silently test main's code (memory: worktree-needs-own-venv).
test -x engine/.venv/bin/python || { /home/miftah/.pyenv/versions/3.11.0/bin/python -m venv engine/.venv && engine/.venv/bin/pip install -e 'engine[dev]'; }
engine/.venv/bin/python -c "import seer_engine; print(seer_engine.__file__)"
#    -> must print a path under /home/miftah/.worktrees/seer/eodhd-survivorship-market/engine/src

# 2. Read-only convenience symlinks and their exclude lines (phase 1 made them). NEVER pass a
#    symlink path to a refresh: _swap_in would os.replace the link, not the store.
[ -e engine/.research ] || ln -s /home/miftah/seer/engine/.research engine/.research
[ -e engine/.cache ]    || ln -s /home/miftah/seer/engine/.cache engine/.cache
EXCL=$(git rev-parse --git-path info/exclude)
for p in engine/.cache engine/.research; do grep -qxF "$p" "$EXCL" || echo "$p" >> "$EXCL"; done
#    Stage files by explicit path only; never `git add -A` or `git add .`.

# 3. Paths used below. SEER_LAB_DB is not set: this phase writes no lab row (the M0039/M0038
#    unblocks are post-landing step L2 of the plan index).
export MAIN=/home/miftah/seer
export CACHE=$MAIN/engine/.cache/eodhd/market
export SCR=/tmp/claude-1000/phase3
```

## Implementation Steps

### Step 1: `MarketSeries`, `EMPTY_SERIES` and `Market.series`

**File:** `engine/src/seer_engine/backtest/market.py`

**1a.** At the import block (:17-23), add `import math` so that it reads:

```python
from __future__ import annotations

import math
from bisect import bisect_right
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from decimal import Decimal
from typing import NamedTuple
```

**1b.** Directly after the two lines

```python
EMPTY_DIVIDENDS = DividendCalendar({})
"""The calendar a ``Market`` carries when no dividends were loaded (one shared instance)."""
```

(:168-169), insert:

```python


class MarketSeries:
    """Market-wide daily series by name (VIX, Treasury yields, gold), read point in time.

    ``rows`` maps a series name to ``(date, value)`` pairs, strictly ascending by date, each value a
    finite float in the unit an allocator reasons in: the VIX family in index points, Treasury
    yields in percent (``T10Y`` 6.548 means 6.548%), gold in USD per ounce. Names with no rows are
    dropped, as ``DividendCalendar`` drops a symbol with no dividends.

    Every read takes the allocator's ``data_date`` and sees only rows dated on or before it. That
    is the same contract ``History`` keeps for bars and ``DividendCalendar.known_on`` keeps for
    dividends, and ``tests/test_market_series.py`` holds it.

    ``value_on`` is the **latest** value on or before ``data_date``, not only one dated exactly
    then: a Treasury index has no close on Columbus Day while the stock market trades, and the
    last published yield is what a trader knew that morning. An allocator that must know how old
    the value is reads ``upto(name, data_date, last=1)`` and compares the date.

    Built from the research store's optional ``market_series.csv`` by ``research.load_store``.
    A market built any other way -- the database path, a paper replay, a fixture -- carries
    ``EMPTY_SERIES``.
    """

    __slots__ = ("_rows", "_dates")

    def __init__(self, rows: Mapping[str, Iterable[tuple[date, float]]]) -> None:
        if not isinstance(rows, Mapping):
            raise TypeError(f"rows must be a Mapping, got {type(rows).__name__}")
        out: dict[str, tuple[tuple[date, float], ...]] = {}
        for name in sorted(rows):
            if not isinstance(name, str) or not name:
                raise ValueError(f"series name must be a non-empty str, got {name!r}")
            items: list[tuple[date, float]] = []
            prev: date | None = None
            for item in rows[name]:
                if not (isinstance(item, tuple) and len(item) == 2):
                    raise TypeError(f"a {name} row is (date, float), got {item!r}")
                d, value = item
                _check_date(f"{name} date", d)
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise TypeError(f"{name} on {d}: value must be a float, got {type(value).__name__}")
                value = float(value)
                if not math.isfinite(value):
                    raise ValueError(f"{name} on {d}: value must be finite, got {value!r}")
                if prev is not None and d <= prev:
                    raise ValueError(f"{name} rows must be strictly ascending: {d} after {prev}")
                prev = d
                items.append((d, value))
            if items:
                out[name] = tuple(items)
        self._rows: Mapping[str, tuple[tuple[date, float], ...]] = out
        self._dates: Mapping[str, tuple[date, ...]] = {n: tuple(d for d, _ in r) for n, r in out.items()}

    def __len__(self) -> int:
        return sum(len(r) for r in self._rows.values())

    def names(self) -> tuple[str, ...]:
        """Every series with at least one row, sorted."""
        return tuple(self._rows)

    def first_date(self, name: str) -> date | None:
        """The date of ``name``'s first row, or None when the series is absent."""
        dates_ = self._dates.get(name)
        return dates_[0] if dates_ else None

    def value_on(self, name: str, data_date: date) -> float | None:
        """``name``'s latest value dated on or before ``data_date``; None when there is none yet."""
        d = _check_date("data_date", data_date)
        dates_ = self._dates.get(name)
        if dates_ is None:
            return None
        i = bisect_right(dates_, d)
        return self._rows[name][i - 1][1] if i else None

    def upto(
        self, name: str, data_date: date, *, last: int | None = None
    ) -> tuple[tuple[date, float], ...]:
        """``name``'s ``(date, value)`` rows dated on or before ``data_date``, ascending.

        ``last`` keeps only the final ``last`` of them (a lookback window without copying the
        whole history on every rank day).
        """
        if last is not None and (isinstance(last, bool) or not isinstance(last, int) or last < 1):
            raise ValueError(f"last must be a positive int or None, got {last!r}")
        d = _check_date("data_date", data_date)
        dates_ = self._dates.get(name)
        if dates_ is None:
            return ()
        i = bisect_right(dates_, d)
        lo = 0 if last is None else max(0, i - last)
        return self._rows[name][lo:i]


EMPTY_SERIES = MarketSeries({})
"""The series a ``Market`` carries when no market series were loaded (one shared instance)."""
```

**1c.** In `class Market` (:249), add this paragraph to the class docstring, directly after the
paragraph that begins ``dividends``: the point-in-time ex-date calendar …:

```
    ``series``: the point-in-time market-wide series (``MarketSeries``: VIX, VIX3M, Treasury
    yields, gold), ``EMPTY_SERIES`` unless the research store carries ``market_series.csv``. An
    allocator that reads it declares ``market_fields = ("series",)`` so ``lab run`` refuses it on
    a store without series.
```

**1d.** In the field list (:270-276), add `series` directly after `dividends`, so that it reads:

```python
    history: Mapping[str, History]
    membership: Membership
    fx: tuple[tuple[date, Decimal], ...]
    fundamentals: Panel = EMPTY_FUNDAMENTALS
    dividends: DividendCalendar = EMPTY_DIVIDENDS
    series: MarketSeries = EMPTY_SERIES
    _fx_dates: tuple[date, ...] = field(init=False, repr=False)
    _last: Mapping[str, date] = field(init=False, repr=False)
```

**1e.** In `__post_init__`, directly after the `dividends` type check (:288-289), add:

```python
        if not isinstance(self.series, MarketSeries):
            raise TypeError(f"series must be a MarketSeries, got {type(self.series).__name__}")
```

**1f.** Directly after `with_dividends` (:318-320), add:

```python

    def with_series(self, series: MarketSeries) -> Market:
        """This market with ``series`` attached; every other field is carried over."""
        return replace(self, series=series)
```

**Impact:** additive. Every existing `Market(...)` call passes keywords or the first three
positional fields (`research.py:1092`, `backtest/io.py:156`, `paper/store.py:1518`), so the new
defaulted field breaks none of them.

### Step 2: research constants and the widened `OPTIONAL_DATA_FILES`

**File:** `engine/src/seer_engine/research.py`

**2a.** Module docstring, files list (:16-21). Directly after the `unserved.csv` bullet, add:

```
- ``market_series.csv`` ``series,date,value``  (optional; ORDER BY series, date; NYSE sessions
  only; the VIX family in points, Treasury yields in percent, gold in USD/oz; written by
  ``python -m seer_engine market_series --refresh``, never by a build)
```

**2b.** Imports (:30-40). Add `import math` after `import logging`, so the stdlib block reads:

```python
import hashlib
import json
import logging
import math
import os
import shutil
import time
```

**2c.** Replace the market import line (:56)

```python
from seer_engine.backtest.market import EMPTY_FUNDAMENTALS, DividendCalendar, Market, Membership
```

with

```python
from seer_engine.backtest.market import (
    EMPTY_FUNDAMENTALS,
    EMPTY_SERIES,
    DividendCalendar,
    Market,
    MarketSeries,
    Membership,
)
```

**2d.** After `ANNOUNCEMENTS_FILE = "dividend_announcements.csv"` (:99), add:

```python
MARKET_SERIES_FILE = "market_series.csv"
```

**2e.** Replace the `OPTIONAL_DATA_FILES` assignment (:103) with the following, keeping its
existing docstring and appending one paragraph to it:

```python
OPTIONAL_DATA_FILES: tuple[str, ...] = (FUNDAMENTALS_FILE, ANNOUNCEMENTS_FILE, MARKET_SERIES_FILE)
```

Append this paragraph at the end of the docstring that follows it (before the closing `"""`, after
the paragraph ending ``dividend_announcements --refresh``.):

```
``market_series.csv`` (EODHD month, R8) is the third: market-wide daily series -- the VIX family,
Treasury yields, gold -- read point in time through ``Market.series``. It is optional for the
same reason: ``price_fingerprint_of`` hashes ``DATA_FILES`` alone, so writing it moves the store's
full fingerprint and never the price fingerprint every recorded trial is compared on. A full
``build_store`` does not write it; re-run ``market_series --refresh`` after a rebuild.
```

**2f.** After `ANNOUNCEMENTS_HEADER = "symbol,ex_date,declared"` (:124), add:

```python
MARKET_SERIES_HEADER = "series,date,value"
MARKET_SERIES_NAMES: tuple[str, ...] = (
    "GOLD", "T10Y", "T13W", "T30Y", "T5Y", "VIX", "VIX3M", "VIX9D", "VVIX", "VXN",
)  # sorted; the only names market_series.csv may hold (commands/market_series.SOURCES writes them)
```

**Impact:** `_read_manifest` now admits `market_series.csv` in `files` (it reads
`OPTIONAL_DATA_FILES`). `_refresh_optional` now carries it over when another optional file is
refreshed (it iterates `OPTIONAL_DATA_FILES`). `DATA_FILES` is unchanged, so every store on disk
loads exactly as before.

### Step 3: the store file's writer and reader

**File:** `engine/src/seer_engine/research.py`, a new section inserted directly after the end of
`_read_announcements` (:538, the line `    return out` that ends it) and before
`# ---- build ----`:

```python


# ---- market series -------------------------------------------------------------------------


def _series_value_text(value: Decimal) -> str:
    """A finite Decimal as plain fixed-point text with no trailing zeros: 6.5480 -> ``6.548``."""
    text = format(value.normalize(), "f")
    return "0" if text == "-0" else text


def market_series_lines(
    rows: Sequence[tuple[str, date, Decimal]], *, end: date = DEV_END
) -> list[str]:
    """``market_series.csv``'s data lines, sorted by series then date.

    ``rows`` are ``(series, date, value)`` with ``series`` one of :data:`MARKET_SERIES_NAMES` and
    ``value`` a finite Decimal already in the series' unit. The text is deterministic (sorted,
    normalized decimals), so the same rows always hash to the same file.

    ValueError when a row names an unknown series, is dated after ``end`` (D9) or before
    ``STORE_START``, holds a value that is not a finite Decimal, or repeats a ``(series, date)``.
    """
    seen: set[tuple[str, date]] = set()
    for item in rows:
        if not (isinstance(item, tuple) and len(item) == 3):
            raise TypeError(f"a market series row is (series, date, Decimal), got {item!r}")
        name, d, value = item
        if name not in MARKET_SERIES_NAMES:
            raise ValueError(
                f"unknown market series {name!r}; expected one of {list(MARKET_SERIES_NAMES)}"
            )
        if isinstance(d, datetime) or not isinstance(d, date):
            raise TypeError(f"{name}: date must be a date, got {type(d).__name__}")
        if d > end:
            raise _after_window_end(MARKET_SERIES_FILE, f"a {name} value", d, end)
        if d < STORE_START:
            raise ValueError(
                f"{MARKET_SERIES_FILE}: a {name} value dated {d} is before STORE_START {STORE_START}"
            )
        if not isinstance(value, Decimal) or not value.is_finite():
            raise ValueError(f"{name} {d}: value must be a finite Decimal, got {value!r}")
        if (name, d) in seen:
            raise ValueError(f"{name} {d}: two values")
        seen.add((name, d))
    return [
        f"{name},{d.isoformat()},{_series_value_text(value)}"
        for name, d, value in sorted(rows, key=lambda r: (r[0], r[1]))
    ]


def _parse_finite(raw: str, where: str) -> float:
    if not raw or raw != raw.strip():
        raise ValueError(f"{where}: bad number {raw!r}")
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{where}: bad number {raw!r}") from exc
    if not math.isfinite(value):
        raise ValueError(f"{where}: {raw!r} must be a finite number")
    return value


def _read_market_series(path: Path, end: date = DEV_END) -> dict[str, list[tuple[date, float]]]:
    """``series -> [(date, value)]`` from ``market_series.csv``, each list ascending.

    Strict, like every other store reader: LF text under the exact header, three fields, a known
    series name, an ISO date no later than ``end`` (D9) and no earlier than ``STORE_START``, a
    finite number, and rows sorted by series then date with no date repeated within a series.
    Values may be zero or negative (a yield can be); they may not be NaN or infinite.
    """
    out: dict[str, list[tuple[date, float]]] = {}
    prev: tuple[str, date] | None = None
    for number, line in _data_lines(path, MARKET_SERIES_HEADER):
        where = f"{path.name}:{number}"
        fields = line.split(",")
        if len(fields) != 3:
            raise ValueError(f"{where}: expected 3 fields, got {len(fields)}")
        name, raw_date, raw_value = fields
        if name not in MARKET_SERIES_NAMES:
            raise ValueError(
                f"{where}: unknown series {name!r}; expected one of {list(MARKET_SERIES_NAMES)}"
            )
        d = _parse_date(raw_date, where)
        if d > end:
            raise _after_window_end(where, f"a {name} value", d, end)
        if d < STORE_START:
            raise ValueError(f"{where}: a {name} value dated {d} is before STORE_START {STORE_START}")
        value = _parse_finite(raw_value, where)
        if prev is not None and (name, d) <= prev:
            raise ValueError(
                f"{where}: rows must be sorted by series then date, each date once per series; "
                f"{name} {d} follows {prev[0]} {prev[1]}"
            )
        prev = (name, d)
        out.setdefault(name, []).append((d, value))
    return out
```

**Impact:** no existing caller. `datetime` and `Sequence` are already imported in `research.py`
(:37 and :35).

### Step 4: `refresh_market_series`

**File:** `engine/src/seer_engine/research.py`. Insert directly after the end of
`refresh_announcements` (:974, its `return manifest`) and before `def _refresh_optional(`:

```python


def refresh_market_series(
    store_dir: Path,
    rows: Sequence[tuple[str, date, Decimal]],
    *,
    data_dir: Path | None = None,
    window: Window = DEV_WINDOW,
) -> dict[str, Any]:
    """Rewrite an existing store's ``market_series.csv``; return the new manifest.

    ``rows`` are ``(series, date, value)`` already normalized by ``commands/market_series``
    (yields in percent, the VIX family in points, NYSE sessions only, clipped to the window).
    Same discipline as :func:`refresh_announcements`: the rows are checked before anything is
    written (:func:`market_series_lines` refuses a row after ``window.end``); the store is verified
    with ``load_store``; every other file -- the four price files and any other optional file -- is
    carried over byte for byte, so the price fingerprint does not move; the directory is swapped in
    whole or not at all. ``window`` must be the window the store declares
    (``declared_window(store_dir)``).
    """
    store_dir = Path(store_dir)
    lines = market_series_lines(rows, end=window.end)
    before, manifest = _refresh_optional(
        store_dir,
        MARKET_SERIES_FILE,
        MARKET_SERIES_HEADER,
        lines,
        data_dir=data_dir,
        window=window,
    )
    log.info(
        "research: store %s market series refreshed: %d rows in %d series, %d bar rows carried "
        "over unchanged, fingerprint %s -> %s",
        store_dir,
        len(lines),
        len({line.split(",", 1)[0] for line in lines}),
        before["bar_rows"],
        before["fingerprint"],
        manifest["fingerprint"],
    )
    return manifest
```

**Impact:** goes through `_refresh_optional` unchanged (as phase 1 leaves it). See the critical
**Requires** item: the `purpose` marker must survive the re-seal.

### Step 5: `load_store` builds `Market.series`

**File:** `engine/src/seer_engine/research.py`, in `load_store`, the `market = Market(` call
(:1092-1105). Add the `series=` keyword as the last argument, so the call reads:

```python
    market = Market(
        history=history,
        membership=research_membership(data_dir, window=window),
        fx=fx_rows,
        fundamentals=fundamentals,
        dividends=DividendCalendar.from_map(
            dividends,
            declared=(
                _read_announcements(store_dir / ANNOUNCEMENTS_FILE, dividends)
                if ANNOUNCEMENTS_FILE in files
                else None
            ),
        ),
        series=(
            MarketSeries(_read_market_series(store_dir / MARKET_SERIES_FILE, window.end))
            if MARKET_SERIES_FILE in files
            else EMPTY_SERIES
        ),
    )
```

Leave everything else in `load_store` (including phase 1's `purpose=` on the returned
`ResearchData`) untouched.

**Impact:** a store without the file loads exactly as before (`EMPTY_SERIES`). There is no count
key for series rows: `_COUNT_KEYS` is pinned as a set by `test_research_store.py`, and the sha256
in `files` already guards the file's bytes.

### Step 6: `preflight_data` refuses a series method on a store with no series

**File:** `engine/src/seer_engine/lab/runner.py`

**6a.** In `market_fields`' docstring (:191-199), replace its first paragraph with:

```
    """The ``Market`` fields a ``MarketAware`` allocator ranks on; () for any other allocator.

    An allocator declares them as a ``market_fields`` class attribute (``("dividends",)`` for
    M0051's calendar book, ``("series",)`` for one that reads ``Market.series``). One that declares
    nothing is taken to read ``fundamentals``: that is what every market-aware allocator read
    before the dividend calendar existed, so the fundamentals coverage gate keeps refusing exactly
    what it refused before.
    """
```

**6b.** In `preflight_data` (:215), directly after the dividends refusal block

```python
    calendar = market_aware_candidates(method, "dividends")
    if calendar and len(data.market.dividends) == 0:
        raise store.LabError(
            ...
        )
```

(:236-242), insert:

```python
    reads_series = market_aware_candidates(method, "series")
    if reads_series and len(data.market.series) == 0:
        raise store.LabError(
            f"{method.id}: {', '.join(reads_series)} read Market.series, and this store carries no "
            f"market series ({research.MARKET_SERIES_FILE}); running it would measure the missing "
            "series, not the hypothesis. Nothing has been spent. Write them with "
            "`python -m seer_engine market_series --refresh --store <store>`"
        )
```

(`research` is already imported in `runner.py`: `preflight_data` takes `research.ResearchData`.)

**6c.** In `preflight_data`'s docstring, replace the sentence that begins "Returns None for a
method with no candidate that ranks on fundamentals" with:

```
    Returns None for a method with no candidate that ranks on fundamentals -- a price-only method
    ranks on bars, a calendar method on the dividend calendar, a series method on
    ``Market.series``, and all three must stay runnable against a store with no panel at all. A
    calendar method on a store with no dividend calendar, and a series method on a store with no
    market series, are refused outright. Otherwise it returns the
```

and keep the rest of that paragraph ("measurement, so the caller can print it …") unchanged.

**Impact:** no recorded method declares `"series"` today (`grep market_fields lab/methods`
shows only `("dividends",)`), so no existing method's preflight changes.

### Step 7: the cache-only command `market_series`

**File:** `engine/src/seer_engine/commands/market_series.py` (new; `cli.discover` picks it up
automatically)

```python
"""market_series -- the market-wide daily series (VIX family, Treasury yields, gold) in the store.

    python -m seer_engine market_series                          # coverage report only, no writes
    python -m seer_engine market_series --refresh                # write market_series.csv
    python -m seer_engine market_series --refresh --store /home/miftah/seer/engine/.research-sv

Reads only EODHD's raw answers already cached under ``engine/.cache/eodhd/market/<TICKER>.json``
during the paid month (gitignored; the licence is personal, so raw rows never enter git or
``web/``). No network and no token: this command cannot fetch a missing file.

Normalization (plan Decision D5), each verified against published yields when it was written:

- VIX, VIX9D, VXN, VVIX: the close as-is, in index points.
- VIX3M: ``VIX3M.INDX`` wherever it has a close, else ``VXV.INDX`` (its name until 2007-11-13).
  The two agree on 1,987 of the 1,996 dev-window sessions both have, and differ by at most 1.05
  points (2014-10-15); the report prints the agreement on every run.
- T13W: ``IRX.INDX`` close, already a yield in percent.
- T5Y, T10Y, T30Y: ``FVX`` / ``TNX`` / ``TYX`` close divided by 10. The vendor index is the yield
  times ten: TNX 65.48 on 2000-01-03 is a 6.548% ten-year yield.
- GOLD: ``XAUUSD.FOREX`` close, USD per ounce.

Rows dated before ``research.STORE_START`` or after the store's window end, rows on a day that
was not an NYSE session (bond and FX markets publish on some stock-market holidays), and rows
with no close are dropped and counted in the report. ``--refresh`` writes through
``research.refresh_market_series``: every other store file is carried over byte for byte, so the
price fingerprint the lab compares trials on does not move. The global ``--dry-run`` writes
nothing.

Exit codes: 0 ok; 2 the store's manifest is missing or unreadable, a cache file is missing or
unreadable, a series has no row in the window, or the refresh was refused.
"""

from __future__ import annotations

import argparse
import json
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from seer_engine import config, dates, research
from seer_engine.backtest.window import Window

log = logging.getLogger(__name__)

HELP = (
    "Report the market series (VIX family, Treasury yields, gold) cached from EODHD and write "
    "them into a research store as market_series.csv (--refresh). Cache only, no network."
)

CACHE_DIR = config.REPO_ROOT / "engine" / ".cache" / "eodhd" / "market"

_ONE = Decimal(1)
_TEN = Decimal(10)


@dataclass(frozen=True)
class Source:
    """One store series and where it comes from.

    ``tickers`` are cache file stems in preference order: on each date the first one with a close
    supplies the value. ``divisor`` turns the vendor close into ``unit``.
    """

    series: str
    tickers: tuple[str, ...]
    divisor: Decimal
    unit: str


SOURCES: tuple[Source, ...] = (
    Source("GOLD", ("XAUUSD.FOREX",), _ONE, "USD/oz"),
    Source("T10Y", ("TNX.INDX",), _TEN, "percent"),
    Source("T13W", ("IRX.INDX",), _ONE, "percent"),
    Source("T30Y", ("TYX.INDX",), _TEN, "percent"),
    Source("T5Y", ("FVX.INDX",), _TEN, "percent"),
    Source("VIX", ("VIX.INDX",), _ONE, "points"),
    Source("VIX3M", ("VIX3M.INDX", "VXV.INDX"), _ONE, "points"),
    Source("VIX9D", ("VIX9D.INDX",), _ONE, "points"),
    Source("VVIX", ("VVIX.INDX",), _ONE, "points"),
    Source("VXN", ("VXN.INDX",), _ONE, "points"),
)  # in research.MARKET_SERIES_NAMES order; tests/test_market_series.py pins the equality


class CacheError(ValueError):
    """A cache file is missing, unreadable, or not EODHD's /eod answer shape."""


def _close(raw: object) -> Decimal | None:
    """A vendor close as a finite Decimal, or None when there is none."""
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return Decimal(raw)
    if isinstance(raw, Decimal):
        return raw if raw.is_finite() else None
    return None


def read_ticker(cache: Path, ticker: str) -> dict[date, Decimal | None]:
    """``date -> close`` from ``<cache>/<ticker>.json``, decimals exact (``parse_float=Decimal``)."""
    path = Path(cache) / f"{ticker}.json"
    try:
        doc = json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal)
    except FileNotFoundError as exc:
        raise CacheError(
            f"{path}: not in the cache; it was downloaded during the paid EODHD month and this "
            "command never fetches"
        ) from exc
    except json.JSONDecodeError as exc:
        raise CacheError(f"{path}: not valid JSON ({exc})") from exc
    if doc is None:
        raise CacheError(f"{path}: EODHD returned nothing for {ticker}")
    if not isinstance(doc, list):
        raise CacheError(f"{path}: expected a list of daily rows, got {type(doc).__name__}")
    out: dict[date, Decimal | None] = {}
    for i, row in enumerate(doc):
        if not isinstance(row, dict) or "date" not in row:
            raise CacheError(f"{path}[{i}]: expected an object with a date")
        try:
            d = date.fromisoformat(row["date"])
        except (TypeError, ValueError) as exc:
            raise CacheError(f"{path}[{i}]: bad date {row['date']!r}") from exc
        if d in out:
            raise CacheError(f"{path}: two rows dated {d}")
        out[d] = _close(row.get("close"))
    return out


@dataclass(frozen=True)
class SeriesReport:
    """One series after normalization: the rows to store and what was dropped on the way."""

    series: str
    unit: str
    rows: tuple[tuple[date, Decimal], ...]  # ascending, already divided into ``unit``
    by_ticker: tuple[tuple[str, int], ...]  # rows each ticker supplied, in preference order
    outside: int  # dated before STORE_START or after the window end
    off_session: int  # inside the window, not an NYSE session
    no_close: int  # an NYSE session in the window where no ticker had a close
    overlap: int  # kept sessions where two or more tickers had a close (0 for one ticker)
    differ: int  # of those, sessions where the closes were not equal
    max_diff: Decimal | None  # the largest close spread among them, vendor units
    max_diff_date: date | None


def normalize(
    source: Source, raw: Mapping[str, Mapping[date, Decimal | None]], window: Window
) -> SeriesReport:
    """``source``'s rows for ``window``: clipped, NYSE sessions only, divided into its unit."""
    all_dates = sorted({d for t in source.tickers for d in raw[t]})
    rows: list[tuple[date, Decimal]] = []
    taken = {t: 0 for t in source.tickers}
    outside = off_session = no_close = overlap = differ = 0
    max_diff: Decimal | None = None
    max_diff_date: date | None = None
    for d in all_dates:
        if d < research.STORE_START or d > window.end:
            outside += 1
            continue
        if not dates.is_session(d):
            off_session += 1
            continue
        closes = [(t, raw[t][d]) for t in source.tickers if raw[t].get(d) is not None]
        if not closes:
            no_close += 1
            continue
        ticker, close = closes[0]
        rows.append((d, close / source.divisor))
        taken[ticker] += 1
        if len(closes) > 1:
            overlap += 1
            values = [c for _, c in closes]
            spread = max(values) - min(values)
            if spread:
                differ += 1
            if max_diff is None or spread > max_diff:
                max_diff, max_diff_date = spread, d
    return SeriesReport(
        series=source.series,
        unit=source.unit,
        rows=tuple(rows),
        by_ticker=tuple((t, taken[t]) for t in source.tickers),
        outside=outside,
        off_session=off_session,
        no_close=no_close,
        overlap=overlap,
        differ=differ,
        max_diff=max_diff,
        max_diff_date=max_diff_date,
    )


def rows_for_store(reports: Sequence[SeriesReport]) -> list[tuple[str, date, Decimal]]:
    """Every report's rows as ``research.refresh_market_series`` takes them."""
    return [(r.series, d, v) for r in reports for d, v in r.rows]


def format_report(
    reports: Sequence[SeriesReport],
    *,
    cache: Path,
    store: Path,
    window: Window,
    members: Sequence[date],
) -> str:
    """The per-series coverage table, then one agreement line per spliced series."""
    have = set(members)
    lines = [
        f"market series from {cache}, for {store} ({window.name} window): rows "
        f"{research.STORE_START.isoformat()}..{window.end.isoformat()}, NYSE sessions only",
        (
            f"member days: {len(members)} sessions, {members[0].isoformat()}..{members[-1].isoformat()}"
            if members
            else "member days: none in this window"
        ),
        "",
        f"{'series':<6} {'unit':<8} {'rows':>5}  {'first':<10}  {'last':<10}  "
        f"{'member days':>15}  {'off-session':>11} {'outside':>7} {'no close':>8}  source",
    ]
    for r in reports:
        covered = sum(1 for d, _ in r.rows if d in have)
        share = f"{covered} ({covered / len(members):.1%})" if members else "-"
        first = r.rows[0][0].isoformat() if r.rows else "-"
        last = r.rows[-1][0].isoformat() if r.rows else "-"
        source = ", ".join(f"{t} {n}" for t, n in r.by_ticker)
        lines.append(
            f"{r.series:<6} {r.unit:<8} {len(r.rows):>5}  {first:<10}  {last:<10}  {share:>15}  "
            f"{r.off_session:>11} {r.outside:>7} {r.no_close:>8}  {source}"
        )
    for r in reports:
        if len(r.by_ticker) < 2:
            continue
        preferred, *others = (t for t, _ in r.by_ticker)
        head = f"{r.series}: {preferred} wherever it has a close, else {', '.join(others)}"
        if r.overlap:
            lines.append(
                f"{head}; on the {r.overlap} sessions both have, they differ on {r.differ}, by at "
                f"most {r.max_diff} ({r.max_diff_date.isoformat()})"
            )
        else:
            lines.append(f"{head}; they never overlap in this window")
    lines.append(f"{sum(len(r.rows) for r in reports)} rows in {len(reports)} series")
    return "\n".join(lines)


def add_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument("--refresh", action="store_true", help="write market_series.csv into the store")
    p.add_argument(
        "--store", type=Path, default=None, help=f"store directory (default {research.STORE_DIR})"
    )
    p.add_argument("--cache", type=Path, default=CACHE_DIR, help=f"EODHD market cache (default {CACHE_DIR})")


def run(args: argparse.Namespace) -> int:
    store = Path(args.store) if args.store else research.STORE_DIR
    cache = Path(args.cache)
    dry_run = bool(getattr(args, "dry_run", False))
    try:
        window = research.declared_window(store)
    except ValueError as exc:
        print(f"market_series: {exc}")
        return 2
    try:
        raw = {t: read_ticker(cache, t) for s in SOURCES for t in s.tickers}
    except CacheError as exc:
        print(f"market_series: {exc}")
        return 2
    reports = tuple(normalize(s, raw, window) for s in SOURCES)
    members = dates.sessions(max(window.start, research.MEMBERSHIP_START), window.end)
    print(format_report(reports, cache=cache, store=store, window=window, members=members))
    if not args.refresh:
        return 0
    empty = [r.series for r in reports if not r.rows]
    if empty:
        print(f"market_series: no rows in the window for {', '.join(empty)}; nothing written")
        return 2
    rows = rows_for_store(reports)
    if dry_run:
        print(f"dry run: would write {len(rows)} rows to {store / research.MARKET_SERIES_FILE}")
        return 0
    before = json.loads((store / research.MANIFEST_FILE).read_text(encoding="utf-8"))
    try:
        manifest = research.refresh_market_series(store, rows, window=window)
    except (research.ResearchStoreError, ValueError) as exc:
        print(f"market_series: {exc}")
        return 2
    price_before = research.price_fingerprint_of(before["files"])
    price_after = research.price_fingerprint_of(manifest["files"])
    print(
        f"wrote {len(rows)} rows ({len(reports)} series) into {store}; fingerprint "
        f"{before['fingerprint']} -> {manifest['fingerprint']}; price fingerprint "
        f"{price_after} ({'unchanged' if price_after == price_before else 'CHANGED from ' + price_before}); "
        f"purpose {manifest.get('purpose', '-')}"
    )
    return 0 if price_after == price_before else 2
```

**Impact:** a new CLI command. `test_cli.py` checks only that some commands are discovered, so
adding a module breaks nothing.

### Step 8: `lab unblock`

**File:** `engine/src/seer_engine/commands/lab.py`

**8a.** Module docstring. Directly after the line
`    lab block M0007 --on "what data"       an idea the store cannot test` (:63), add:

```
    lab unblock M0007 --note "..."         the missing data arrived: blocked-data -> idea, the
                                           note (what arrived, how much of the window it covers)
                                           appended to the analysis
```

**8b.** Parser. Directly after the `block` subparser (:342-344), add:

```python
    s = sub.add_parser("unblock", help="the missing data arrived: move a blocked idea back to idea")
    s.add_argument("method")
    s.add_argument("--note", required=True,
                   help="what arrived and how much of the dev window it covers (appended to the analysis)")
```

**8c.** Handler. Directly after `_block` (:2116-2119), add:

```python


def _unblock(conn, args) -> int:
    """``blocked-data -> idea`` (``store.TRANSITIONS``: "the missing data arrived").

    The note is appended to the method's analysis with ``store.append_analysis``, the way
    ``lab note`` records one, together with what the method was blocked on. ``blocked_on`` is
    then cleared, so the analysis is the only place that history survives.
    """
    note = args.note.strip()
    if not note:
        raise store.LabError("give --note: what data arrived and how much of the dev window it covers")
    row = store.get_method(conn, args.method)
    if row is None:
        raise store.LabError(f"no method {args.method}")
    if row["status"] != "blocked-data":
        raise store.LabError(
            f"{args.method} is {row['status']}, not blocked-data; only an idea blocked on data "
            "can be unblocked"
        )
    text = f"Unblocked: the missing data arrived. {note}"
    if row["blocked_on"]:
        text += f"\n\nIt was blocked on: {row['blocked_on']}"
    with conn:
        store.append_analysis(conn, args.method, text)
        store.update_method(conn, args.method, status="idea", blocked_on="")
    print(f"{args.method}: blocked-data -> idea")
    return 0
```

**8d.** `_HANDLERS` (:2203). Directly after `    "block": _block,` (:2218), add:

```python
    "unblock": _unblock,
```

**Impact:** a new subcommand only. Phase 4 (after this phase) adds `survivorship` to the module
docstring (after the `lab costs` block), the parser (after `walkforward`), the handlers (after
`_walkforward`) and `_HANDLERS` (after `"names"`): different anchors from these.

### Step 9: the pinned optional-file test, updated deliberately

**File:** `engine/tests/test_market_fundamentals.py:629-640`. Replace the whole test with:

```python
def test_data_files_is_not_widened():
    """The whole backward-compatibility argument in one assertion.

    research._read_manifest requires the four DATA_FILES names and allows only the optional
    ones beyond them, and load_store hashes the manifest's own keys. If fundamentals.csv ever
    joins DATA_FILES, every store on disk stops loading -- with a ValueError, before any reader
    runs.

    OPTIONAL_DATA_FILES was widened on purpose by the EODHD plan set (phase 3, R8):
    market_series.csv is a third *optional* file. That is the shape this test protects, not a
    breach of it -- DATA_FILES stays the four price files, so price_fingerprint_of (which hashes
    DATA_FILES alone) does not move when a store gains the series, and a store without the file
    loads exactly as before.
    """
    assert research.FUNDAMENTALS_FILE not in research.DATA_FILES
    assert research.ANNOUNCEMENTS_FILE not in research.DATA_FILES
    assert research.MARKET_SERIES_FILE not in research.DATA_FILES
    assert research.DATA_FILES == (
        research.BARS_FILE, research.DIVIDENDS_FILE, research.FX_FILE, research.UNSERVED_FILE
    )
    assert research.OPTIONAL_DATA_FILES == (
        research.FUNDAMENTALS_FILE, research.ANNOUNCEMENTS_FILE, research.MARKET_SERIES_FILE
    )
    assert research.FUNDAMENTALS_HEADER == ",".join(FACT_COLUMNS)
```

### Step 10: tests for the series, the store file and the command

**File:** `engine/tests/test_market_series.py` (new)

```python
"""Market series (EODHD plan set, phase 3, R8).

``MarketSeries`` is read point in time; ``market_series.csv`` is an optional store file that never
moves the price fingerprint; ``lab run`` refuses a series method on a store without series; and
the ``market_series`` command normalizes EODHD's cached closes. No network.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from labkit import smoke_data, smoke_market

import test_research_store as rs
from seer_engine import research
from seer_engine.backtest.market import EMPTY_SERIES, MarketSeries
from seer_engine.commands import market_series as cmd
from seer_engine.lab import runner, store
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0051_dividend_month_premium import METHOD as M0051
from seer_engine.lab.methods.m0051_dividend_month_premium import DividendMonthAllocator
from test_research_store import build


@pytest.fixture
def members(tmp_path):
    """``test_research_store``'s membership fixture, under a name that does not shadow it."""
    return rs.members_dir.__wrapped__(tmp_path)


# ---- MarketSeries --------------------------------------------------------------------------

VIX = [
    (date(2008, 9, 12), 25.66),
    (date(2008, 9, 15), 31.7),
    (date(2008, 9, 16), 30.3),
    (date(2008, 9, 19), 32.07),
]


def test_value_on_is_the_latest_value_dated_on_or_before_the_data_date():
    s = MarketSeries({"VIX": VIX})
    assert s.value_on("VIX", date(2008, 9, 11)) is None
    assert s.value_on("VIX", date(2008, 9, 12)) == 25.66
    assert s.value_on("VIX", date(2008, 9, 17)) == 30.3  # the last close, never the next one
    assert s.value_on("VIX", date(2020, 1, 1)) == 32.07
    assert s.value_on("T10Y", date(2008, 9, 15)) is None


def test_no_value_dated_after_the_data_date_is_ever_visible():
    s = MarketSeries({"VIX": VIX})
    d = date(2008, 9, 10)
    while d <= date(2008, 9, 22):
        seen = s.upto("VIX", d)
        assert all(x <= d for x, _ in seen)
        assert seen == tuple(r for r in VIX if r[0] <= d)
        assert s.value_on("VIX", d) == (seen[-1][1] if seen else None)
        d += timedelta(days=1)


def test_upto_last_keeps_only_the_tail():
    s = MarketSeries({"VIX": VIX})
    assert s.upto("VIX", date(2008, 9, 16), last=2) == (VIX[1], VIX[2])
    assert s.upto("VIX", date(2008, 9, 11), last=2) == ()
    assert s.upto("NOPE", date(2008, 9, 16)) == ()
    with pytest.raises(ValueError):
        s.upto("VIX", date(2008, 9, 16), last=0)


def test_names_first_date_and_len():
    s = MarketSeries({"VIX": VIX, "T13W": [(date(1993, 1, 29), 2.9)], "EMPTY": []})
    assert s.names() == ("T13W", "VIX")
    assert s.first_date("VIX") == date(2008, 9, 12)
    assert s.first_date("EMPTY") is None
    assert len(s) == 5
    assert len(EMPTY_SERIES) == 0 and EMPTY_SERIES.names() == ()


@pytest.mark.parametrize(
    "rows, err",
    [
        ([], TypeError),
        ({"": [(date(2008, 9, 12), 1.0)]}, ValueError),
        ({"VIX": [(date(2008, 9, 12), 1.0), (date(2008, 9, 12), 2.0)]}, ValueError),
        ({"VIX": [(date(2008, 9, 15), 1.0), (date(2008, 9, 12), 2.0)]}, ValueError),
        ({"VIX": [(date(2008, 9, 12), float("nan"))]}, ValueError),
        ({"VIX": [(date(2008, 9, 12), float("inf"))]}, ValueError),
        ({"VIX": [(date(2008, 9, 12), True)]}, TypeError),
        ({"VIX": [(date(2008, 9, 12), Decimal("1"))]}, TypeError),
        ({"VIX": [(datetime(2008, 9, 12), 1.0)]}, TypeError),
        ({"VIX": [(date(2008, 9, 12),)]}, TypeError),
    ],
)
def test_bad_rows_are_refused(rows, err):
    with pytest.raises(err):
        MarketSeries(rows)


def test_a_data_date_must_be_a_date():
    with pytest.raises(TypeError):
        MarketSeries({"VIX": VIX}).value_on("VIX", datetime(2008, 9, 15))


def test_a_market_carries_the_shared_empty_series_unless_given_one():
    m = smoke_market()
    assert m.series is EMPTY_SERIES
    s = MarketSeries({"VIX": VIX})
    m2 = m.with_series(s)
    assert m2.series is s
    assert m.series is EMPTY_SERIES
    assert m2.history is m.history
    with pytest.raises(TypeError):
        dataclasses.replace(m, series={"VIX": VIX})


# ---- the store file ------------------------------------------------------------------------

ROWS = (
    ("VIX", date(1999, 1, 5), Decimal("24.42")),
    ("T10Y", date(1999, 1, 4), Decimal("4.653")),
    ("VIX", date(1999, 1, 4), Decimal("26.17")),
    ("T13W", date(2015, 10, 16), Decimal("0.005")),
)


def test_lines_are_sorted_by_series_then_date_with_normalized_values():
    extra = (
        ("GOLD", date(1999, 1, 4), Decimal("287.50")),
        ("GOLD", date(1999, 1, 5), Decimal("300.00")),
    )
    assert research.market_series_lines(ROWS + extra) == [
        "GOLD,1999-01-04,287.5",
        "GOLD,1999-01-05,300",
        "T10Y,1999-01-04,4.653",
        "T13W,2015-10-16,0.005",
        "VIX,1999-01-04,26.17",
        "VIX,1999-01-05,24.42",
    ]


@pytest.mark.parametrize(
    "row, err",
    [
        (("SPX", date(1999, 1, 4), Decimal("1")), ValueError),
        (("VIX", date(2015, 10, 19), Decimal("1")), ValueError),  # after DEV_END
        (("VIX", date(1993, 1, 28), Decimal("1")), ValueError),  # before STORE_START
        (("VIX", date(1999, 1, 4), 1.0), ValueError),
        (("VIX", date(1999, 1, 4), Decimal("NaN")), ValueError),
        (("VIX", datetime(1999, 1, 4), Decimal("1")), TypeError),
    ],
)
def test_lines_refuse_a_bad_row(row, err):
    with pytest.raises(err):
        research.market_series_lines((row,))


def test_lines_refuse_two_values_for_one_day():
    with pytest.raises(ValueError, match="two values"):
        research.market_series_lines(ROWS + (("VIX", date(1999, 1, 4), Decimal("1")),))


def test_refresh_adds_the_file_and_keeps_every_price_byte(tmp_path, members):
    store_dir = tmp_path / "store"
    before = build(store_dir, members, facts=rs.FACTS_A)
    carried = (*research.DATA_FILES, research.FUNDAMENTALS_FILE)
    before_bytes = {n: (store_dir / n).read_bytes() for n in carried}

    after = research.refresh_market_series(store_dir, ROWS, data_dir=members)

    assert {n: (store_dir / n).read_bytes() for n in carried} == before_bytes
    assert research.MARKET_SERIES_FILE in after["files"]
    assert research.price_fingerprint_of(after["files"]) == research.price_fingerprint_of(before["files"])
    assert after["fingerprint"] != before["fingerprint"]
    assert (store_dir / research.MARKET_SERIES_FILE).read_text(encoding="utf-8") == (
        "series,date,value\n"
        "T10Y,1999-01-04,4.653\n"
        "T13W,2015-10-16,0.005\n"
        "VIX,1999-01-04,26.17\n"
        "VIX,1999-01-05,24.42\n"
    )
    data = research.load_store(store_dir, data_dir=members)
    assert data.market.series.names() == ("T10Y", "T13W", "VIX")
    assert data.market.series.value_on("VIX", date(1999, 1, 4)) == 26.17
    assert data.market.series.value_on("T10Y", date(2015, 10, 16)) == 4.653
    assert data.price_fingerprint == research.price_fingerprint_of(before["files"])

    # refreshing another optional file afterwards carries the series over
    research.refresh_fundamentals(store_dir, rs.FACTS_A, data_dir=members)
    assert len(research.load_store(store_dir, data_dir=members).market.series) == 4


def test_a_store_without_the_file_loads_with_the_empty_series(tmp_path, members):
    store_dir = tmp_path / "store"
    build(store_dir, members)
    assert research.load_store(store_dir, data_dir=members).market.series is EMPTY_SERIES


def test_refresh_refuses_a_row_after_the_window_and_writes_nothing(tmp_path, members):
    store_dir = tmp_path / "store"
    before = build(store_dir, members)
    with pytest.raises(ValueError, match="after DEV_END"):
        research.refresh_market_series(
            store_dir, (("VIX", date(2015, 10, 19), Decimal("20")),), data_dir=members
        )
    assert json.loads((store_dir / research.MANIFEST_FILE).read_text()) == before
    assert not (store_dir / research.MARKET_SERIES_FILE).exists()


HEADER = research.MARKET_SERIES_HEADER


def _read(tmp_path, text):
    path = tmp_path / research.MARKET_SERIES_FILE
    path.write_bytes(text.encode("utf-8"))
    return research._read_market_series(path)


def test_the_reader_returns_ascending_rows_per_series(tmp_path):
    got = _read(tmp_path, f"{HEADER}\nT10Y,1999-01-04,4.653\nVIX,1999-01-04,20\nVIX,1999-01-05,-0.5\n")
    assert got == {
        "T10Y": [(date(1999, 1, 4), 4.653)],
        "VIX": [(date(1999, 1, 4), 20.0), (date(1999, 1, 5), -0.5)],
    }


@pytest.mark.parametrize(
    "text, match",
    [
        ("series,date,close\nVIX,1999-01-04,20\n", "header"),
        (f"{HEADER}\r\nVIX,1999-01-04,20\r\n", "header"),
        (f"{HEADER}\nVIX,1999-01-04,20", "LF"),
        (f"{HEADER}\nSPX,1999-01-04,20\n", "unknown series"),
        (f"{HEADER}\nVIX,1999-01-04\n", "3 fields"),
        (f"{HEADER}\nVIX,1999-13-04,20\n", "bad date"),
        (f"{HEADER}\nVIX,2015-10-19,20\n", "after DEV_END"),
        (f"{HEADER}\nVIX,1993-01-28,20\n", "before STORE_START"),
        (f"{HEADER}\nVIX,1999-01-04,nan\n", "finite"),
        (f"{HEADER}\nVIX,1999-01-04,x\n", "bad number"),
        (f"{HEADER}\nVIX,1999-01-04, 20\n", "bad number"),
        (f"{HEADER}\nVIX,1999-01-04,20\nVIX,1999-01-04,21\n", "sorted"),
        (f"{HEADER}\nVIX,1999-01-05,20\nVIX,1999-01-04,21\n", "sorted"),
        (f"{HEADER}\nVIX,1999-01-04,20\nT10Y,1999-01-04,4.6\n", "sorted"),
    ],
)
def test_the_reader_is_strict(tmp_path, text, match):
    with pytest.raises(ValueError, match=match):
        _read(tmp_path, text)


# ---- lab run refuses a series method on a store without series -----------------------------


class _SeriesAllocator(DividendMonthAllocator):
    market_fields = ("series",)


def _series_method(mid: str = "M0014") -> Method:
    c = dataclasses.replace(
        M0051.candidates[0], id=f"{mid}-VIX", family=mid, allocator=_SeriesAllocator()
    )
    return Method(
        id=mid, name="series test", family="regime", source_kind="knowledge", source_ref="",
        hypothesis="h", expected_failure="f", candidates=(c,),
    )


def test_a_series_method_is_refused_on_a_store_without_series():
    data = smoke_data()
    m = _series_method()
    assert runner.market_aware_candidates(m, "series") == ("M0014-VIX",)
    assert runner.market_aware_candidates(m) == ()  # not gated on the fundamentals panel
    assert len(data.market.series) == 0
    with pytest.raises(store.LabError, match="no market series"):
        runner.preflight_data(data, m)


def test_a_series_method_passes_once_the_store_carries_series():
    data = smoke_data()
    series = MarketSeries({"VIX": [(date(1999, 1, 4), 20.0)]})
    with_series = dataclasses.replace(data, market=data.market.with_series(series))
    assert runner.preflight_data(with_series, _series_method()) is None


# ---- the command ---------------------------------------------------------------------------

TICKERS = sorted({t for s in cmd.SOURCES for t in s.tickers})


def _eod(day, close):
    return {
        "date": day, "open": close, "high": close, "low": close, "close": close,
        "adjusted_close": close, "volume": 0,
    }


def _cache(tmp_path):
    """Two sessions per ticker, plus the edge cases on TNX (scale, holiday, both window edges),
    the VIX3M/VXV splice and a null close on IRX."""
    cache = tmp_path / "market"
    cache.mkdir()
    rows = {t: [_eod("1999-01-04", 20.0), _eod("1999-01-05", 21.5)] for t in TICKERS}
    rows["TNX.INDX"] = [
        _eod("1990-01-02", 79.9),  # before STORE_START
        _eod("1999-01-01", 46.0),  # New Year's Day: not an NYSE session
        _eod("1999-01-04", 46.53),
        _eod("2015-10-16", 20.23),
        _eod("2015-10-19", 20.3),  # after DEV_END
    ]
    rows["VXV.INDX"] = [_eod("1999-01-04", 25.0), _eod("1999-01-05", 26.0)]
    rows["VIX3M.INDX"] = [_eod("1999-01-05", 26.5)]
    rows["IRX.INDX"] = [_eod("1999-01-04", 4.4), _eod("1999-01-05", None)]
    for t, r in rows.items():
        (cache / f"{t}.json").write_text(json.dumps(r), encoding="utf-8")
    return cache


def _args(store_dir, cache, **kw):
    return argparse.Namespace(**{"store": store_dir, "cache": cache, "refresh": False, "dry_run": False, **kw})


EXPECTED = "\n".join(
    [
        research.MARKET_SERIES_HEADER,
        "GOLD,1999-01-04,20",
        "GOLD,1999-01-05,21.5",
        "T10Y,1999-01-04,4.653",
        "T10Y,2015-10-16,2.023",
        "T13W,1999-01-04,4.4",
        "T30Y,1999-01-04,2",
        "T30Y,1999-01-05,2.15",
        "T5Y,1999-01-04,2",
        "T5Y,1999-01-05,2.15",
        "VIX,1999-01-04,20",
        "VIX,1999-01-05,21.5",
        "VIX3M,1999-01-04,25",
        "VIX3M,1999-01-05,26.5",
        "VIX9D,1999-01-04,20",
        "VIX9D,1999-01-05,21.5",
        "VVIX,1999-01-04,20",
        "VVIX,1999-01-05,21.5",
        "VXN,1999-01-04,20",
        "VXN,1999-01-05,21.5",
    ]
) + "\n"


def test_sources_write_exactly_the_store_names_with_the_checked_scaling():
    assert tuple(s.series for s in cmd.SOURCES) == research.MARKET_SERIES_NAMES
    by = {s.series: s for s in cmd.SOURCES}
    assert by["T10Y"].divisor == by["T5Y"].divisor == by["T30Y"].divisor == Decimal(10)
    assert by["T13W"].divisor == Decimal(1)  # IRX is already in percent
    assert by["VIX3M"].tickers == ("VIX3M.INDX", "VXV.INDX")


@pytest.fixture
def store_dir(tmp_path, members, monkeypatch):
    path = tmp_path / "store"
    build(path, members)
    real_load = research.load_store
    monkeypatch.setattr(
        research, "load_store", lambda s, **kw: real_load(s, **{**kw, "data_dir": members})
    )
    return path


def test_the_report_writes_nothing(tmp_path, store_dir, capsys):
    assert cmd.run(_args(store_dir, _cache(tmp_path))) == 0
    out = capsys.readouterr().out
    assert "T10Y" in out and "off-session" in out
    assert "VIX3M: VIX3M.INDX wherever it has a close, else VXV.INDX" in out
    assert "they differ on 1, by at most 0.5 (1999-01-05)" in out
    assert not (store_dir / research.MARKET_SERIES_FILE).exists()


def test_refresh_writes_the_normalized_rows_and_keeps_the_price_fingerprint(tmp_path, store_dir, capsys):
    before = json.loads((store_dir / research.MANIFEST_FILE).read_text())
    assert cmd.run(_args(store_dir, _cache(tmp_path), refresh=True)) == 0
    assert (store_dir / research.MARKET_SERIES_FILE).read_text(encoding="utf-8") == EXPECTED
    after = json.loads((store_dir / research.MANIFEST_FILE).read_text())
    assert research.price_fingerprint_of(after["files"]) == research.price_fingerprint_of(before["files"])
    assert "(unchanged)" in capsys.readouterr().out


def test_dry_run_writes_nothing(tmp_path, store_dir, capsys):
    before = (store_dir / research.MANIFEST_FILE).read_text()
    assert cmd.run(_args(store_dir, _cache(tmp_path), refresh=True, dry_run=True)) == 0
    assert "dry run: would write 19 rows" in capsys.readouterr().out
    assert (store_dir / research.MANIFEST_FILE).read_text() == before
    assert not (store_dir / research.MARKET_SERIES_FILE).exists()


def test_a_missing_cache_file_exits_2_and_writes_nothing(tmp_path, store_dir, capsys):
    cache = _cache(tmp_path)
    (cache / "VXV.INDX.json").unlink()
    assert cmd.run(_args(store_dir, cache, refresh=True)) == 2
    assert "VXV.INDX.json" in capsys.readouterr().out
    assert not (store_dir / research.MARKET_SERIES_FILE).exists()
```

Note: `EXPECTED` has 19 data rows. T10Y has 2 (1999-01-01 is off-session, 1990 and 2015-10-19
are outside, and there is no 1999-01-05 row). T13W has 1 (1999-01-05 has a null close). The other
eight series have 2 each. That gives 2 + 1 + 16 = 19.

### Step 11: tests for `lab unblock`

**File:** `engine/tests/test_lab_unblock.py` (new)

```python
"""`lab unblock`: the missing data arrived (EODHD plan set, phase 3, R9)."""

from __future__ import annotations

import argparse

from seer_engine.commands import lab as lab_cmd
from seer_engine.lab import store


def _lab(tmp_path):
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    with c:
        store.add_method(
            c, id="M0001", name="VIX gate", family="regime", source_kind="knowledge", hypothesis="h"
        )
    c.close()
    return db


def _run(db, command, **kw):
    return lab_cmd.run(argparse.Namespace(db=db, lab_command=command, **kw))


def _row(db, mid="M0001"):
    c = store.connect(db)
    try:
        return dict(store.get_method(c, mid))
    finally:
        c.close()


def test_unblock_moves_a_blocked_idea_back_and_keeps_why_it_was_blocked(tmp_path):
    db = _lab(tmp_path)
    assert _run(db, "block", method="M0001", on="CBOE VIX3M daily closes") == 0
    assert _row(db)["status"] == "blocked-data"

    assert _run(db, "unblock", method="M0001", note="Covers 46.8% of the dev window.") == 0

    row = _row(db)
    assert row["status"] == "idea"
    assert row["blocked_on"] == ""
    assert "Unblocked: the missing data arrived. Covers 46.8% of the dev window." in row["analysis"]
    assert "It was blocked on: CBOE VIX3M daily closes" in row["analysis"]


def test_unblock_refuses_a_method_that_is_not_blocked(tmp_path):
    db = _lab(tmp_path)
    assert _run(db, "unblock", method="M0001", note="n") == 2
    row = _row(db)
    assert row["status"] == "idea"
    assert row["analysis"] == ""


def test_unblock_refuses_an_empty_note_and_an_unknown_method(tmp_path):
    db = _lab(tmp_path)
    assert _run(db, "block", method="M0001", on="x") == 0
    assert _run(db, "unblock", method="M0001", note="   ") == 2
    assert _row(db)["status"] == "blocked-data"
    assert _run(db, "unblock", method="M0099", note="n") == 2
```

### Step 12: build, test, commit the code (before touching any real store)

```bash
cd /home/miftah/.worktrees/seer/eodhd-survivorship-market
engine/.venv/bin/python -m pytest engine/tests/test_market_series.py engine/tests/test_lab_unblock.py \
  engine/tests/test_market_fundamentals.py engine/tests/test_dividend_announcements.py \
  engine/tests/test_research_store.py engine/tests/test_lab_runner.py engine/tests/test_market_dividends.py -q
engine/.venv/bin/ruff check engine/src engine/tests
engine/.venv/bin/python -m pytest engine/tests -q          # the full suite (xdist: -n auto)
git add engine/src/seer_engine/backtest/market.py engine/src/seer_engine/research.py \
        engine/src/seer_engine/lab/runner.py engine/src/seer_engine/commands/market_series.py \
        engine/src/seer_engine/commands/lab.py engine/tests/test_market_fundamentals.py \
        engine/tests/test_market_series.py engine/tests/test_lab_unblock.py
git commit -m "$(cat <<'EOF'
engine: market series store file, Market.series, market_series command, lab unblock (EODHD phase 3)

Optional market_series.csv (series,date,value) read point in time through MarketSeries; the
price fingerprint (DATA_FILES only) never moves. VIX family in points, Treasury yields in
percent (TNX/FVX/TYX / 10), VIX3M with VXV before 2007-11-13, NYSE sessions only, cache only.
lab run refuses a series method on a store without series. lab unblock: blocked-data -> idea.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
EOF
)"
```

Commit only on `feature/eodhd-survivorship-market`. Do not merge or push to `main`; the
coordinator or completion handler does that.

### Step 13: prove the refresh on scratch copies (cache only, real stores untouched)

The real dev store is **not** refreshed in this phase (Decision D8): until this branch is on
`main`, the main checkout's `_read_manifest` refuses a manifest listing `market_series.csv`, and the
live Sera batch loads `/home/miftah/seer/engine/.research` with that code. The real SV store is
refreshed by phase 5 after its final rebuild (Decision D9). This step proves the command on copies
of both, so L1 (post-landing) and phase 5 run a command already measured on the real data.

**13a. Copy the dev store (a real directory, never a symlink) and report:**

```bash
cd /home/miftah/.worktrees/seer/eodhd-survivorship-market
rm -rf $SCR && mkdir -p $SCR
cp -r $MAIN/engine/.research $SCR/dev        # ~200 MB; read only on the source
cp $SCR/dev/manifest.json $SCR/dev-manifest-before.json
engine/.venv/bin/python -m seer_engine market_series --store $SCR/dev --cache $CACHE
#   expect the table in "Measured facts": 43317 rows in 10 series; VIX3M 2331 rows
#   (VIX3M.INDX 1996, VXV.INDX 335); "they differ on 9, by at most 1.05 (2014-10-15)";
#   T10Y member days 4966 (99.6%); VIX3M member days 2331 (46.8%)
engine/.venv/bin/python -m seer_engine --dry-run market_series --refresh --store $SCR/dev --cache $CACHE
engine/.venv/bin/python -m seer_engine market_series --refresh --store $SCR/dev --cache $CACHE
#   must print "price fingerprint 5451195fd552e208eaadfc6bc89241b9b8e3e6ccb0f4c447a84bbc4f32e7d90a (unchanged)"
#   and a full fingerprint fd2bc190e915... -> <new>; exit code 0. Record <new> in the completion
#   note: L1 compares the real store's against it (a mismatch is recorded there, not a stop).
```

**13b. Verify the copy:**

```bash
engine/.venv/bin/python - <<'EOF2'
import json
from datetime import date
from seer_engine import research
scr = "/tmp/claude-1000/phase3/dev"
d = research.load_store(scr)
assert d.price_fingerprint == "5451195fd552e208eaadfc6bc89241b9b8e3e6ccb0f4c447a84bbc4f32e7d90a", d.price_fingerprint
s = d.market.series
assert s.names() == research.MARKET_SERIES_NAMES and len(s) == 43317, (s.names(), len(s))
assert s.value_on("T10Y", date(2000, 1, 3)) == 6.548
assert s.value_on("T13W", date(2000, 1, 3)) == 5.27
assert s.value_on("VIX", date(2008, 11, 20)) == 80.86
assert s.first_date("VIX3M") == date(2006, 7, 17)
assert s.value_on("VIX3M", date(2014, 10, 15)) == 23.82   # VIX3M preferred over VXV's 22.77
assert s.value_on("T10Y", date(2015, 10, 12)) == s.value_on("T10Y", date(2015, 10, 9))  # Columbus Day carries
a = json.load(open("/tmp/claude-1000/phase3/dev-manifest-before.json"))["files"]
b = json.load(open(f"{scr}/manifest.json"))["files"]
assert all(b[k] == v for k, v in a.items()), "a carried file changed"
assert set(b) - set(a) == {"market_series.csv"}, set(b) - set(a)
print("dev copy OK", d.fingerprint)
EOF2
```

**13c. The SV store's mark survives a refresh (check only, on a copy; skipped if no SV store yet):**

```bash
# phase 2 (parallel) may be swapping the real SV store in: wait for quiet first with a Monitor
# until-loop, never a foreground sleep:
#   until ! pgrep -f '[s]eer_engine.*survivorship_store'; do sleep 60; done
# A copy torn by a swap fails the load_store sha check below: wait for quiet again, re-copy once,
# and only then treat a failure as a defect.
if [ -f $MAIN/engine/.research-sv/manifest.json ]; then
  rm -rf $SCR/sv && cp -r $MAIN/engine/.research-sv $SCR/sv
  cp $SCR/sv/manifest.json $SCR/sv-manifest-before.json
  engine/.venv/bin/python -m seer_engine market_series --refresh --store $SCR/sv --cache $CACHE
  engine/.venv/bin/python - <<'EOF2'
import json
from seer_engine import research as r
before = json.load(open("/tmp/claude-1000/phase3/sv-manifest-before.json"))
after = json.load(open("/tmp/claude-1000/phase3/sv/manifest.json"))
assert r.price_fingerprint_of(after["files"]) == r.price_fingerprint_of(before["files"]), "SV price fingerprint moved"
assert after.get("purpose") == before.get("purpose") == "survivorship-check", (before.get("purpose"), after.get("purpose"))
d = r.load_store("/tmp/claude-1000/phase3/sv")
assert d.purpose == "survivorship-check" and len(d.market.series) == 43317
print("SV copy OK", r.price_fingerprint_of(after["files"]))
EOF2
  cmp $SCR/dev/market_series.csv $SCR/sv/market_series.csv && echo "same series bytes in both"
fi
rm -rf $SCR/dev $SCR/sv          # keep only the two manifest copies and the notes
```

A failed `purpose` assertion would be a phase-1 defect (its `_refresh_optional` carries the key);
it touches only the copy, so stop the phase, report it, and do not commit around it.

**Never** run `market_series --refresh` in this phase against `/home/miftah/seer/engine/.research`,
`/home/miftah/seer/engine/.research-sv`, `/home/miftah/seer/engine/.research-test`, or the
worktree's `engine/.research` symlink.

### Step 14: hand the real refresh and the unblocks to the post-landing steps

Nothing runs here. The plan index's **Post-landing** section carries L1 (refresh the real dev
store and push it with the sync skill), L2 (`lab unblock M0039` / `M0038` with the coverage notes
measured above) and L3 (stage per D6). Do not edit the plan index (the coordinator holds its own
copy). Put in the completion note: the new full fingerprint from 13a, and, if 13a's report
differs from "Measured facts", the printed numbers. L2 re-reads the coverage from the real store
and substitutes any differing number into its notes itself. Do **not** `git add lab/lab.sqlite`; this phase writes no lab row.

## Verification

**Build:** `engine/.venv/bin/ruff check engine/src engine/tests` (the worktree venv, never main's)

**Tests:** `engine/.venv/bin/python -m pytest engine/tests -q`. The full suite must pass. The
handover baseline was 3,513 tests, plus phase 1's tests, plus this phase's roughly 50.

**Manual check (Step 13, on scratch copies only):**
- `market_series --store <copy of the dev store>` prints 43,317 rows in 10 series, VIX3M 2,331
  rows (VIX3M.INDX 1,996, VXV.INDX 335), "differ on 9, by at most 1.05 (2014-10-15)", T10Y member
  days 4,966 (99.6%), and VIX3M 2,331 (46.8%).
- After the refresh of the copy, its price fingerprint is `5451195fd552e208…7d90a`, and the six
  carried files' sha256 values equal the copy's manifest before.
- The SV copy (if an SV store exists) keeps its price fingerprint and `purpose: survivorship-check`,
  and holds the same `market_series.csv` bytes as the dev copy.
- `/home/miftah/seer/engine/.research/manifest.json` still reads `fd2bc190…` (this phase never
  wrote it).

**Exit criteria:** `market_series --refresh` proven on copies of both stores with neither price
fingerprint moving and the SV mark kept. `Market.series.value_on(name, d)` never returns a value
dated after `d` (tested). `lab run` refuses a series method on a store without series (tested).
`lab unblock` works (tested). The real dev store and the lab DB are untouched; the real refresh
and the M0039/M0038 unblocks are post-landing L1-L2. The full engine suite passes. The code is
committed on `feature/eodhd-survivorship-market`.

## Handoffs

- **Phase 1 (Requires, confirmed):** `_refresh_optional` re-seals with `purpose=before.get(PURPOSE_KEY)`
  (phase 1 Step 2). This phase does not edit `_seal`, `_refresh_optional` or `_read_manifest`
  beyond the `OPTIONAL_DATA_FILES` constant they read.
- **Phase 5 (SV store):** after its final offline rebuild, run
  `market_series --refresh --store /home/miftah/seer/engine/.research-sv --cache /home/miftah/seer/engine/.cache/eodhd/market`
  (the dev store does not carry the file until L1, so the rebuild cannot copy it).
- **Phase 4:** `commands/lab.py` gains `unblock` here (docstring line after `lab block`, parser
  after `block`, `_unblock` after `_block`, a `_HANDLERS` entry after `"block"`). Phase 4's
  `survivorship` insertions sit at different anchors (after the `lab costs` docstring block, after
  `walkforward`, after `_walkforward`, after `"names"`).
- **Phase 5 (docs):** in the explore skill, name `lab unblock MNNNN --note` beside `lab block`
  (:70, :346) and document `Market.series` with `market_fields = ("series",)`, the ten series
  names and units (phase 5 Step 9, Edits C and D).
- **Post-landing L1-L3 (plan index):** the real dev store refresh, its Blob push, the two unblock
  notes (drafted from "Measured facts"), and staging per D6.
- **Data caveat for whoever builds a VVIX method:** VVIX's first weeks (2006-03-15 15.71 through
  2006-03-21 37.35, and 2006-11-13 36.14) sit far below its normal 60-200 range. They are written
  as-is (D5). A method that reads VVIX should start after 2006-12 or treat those rows as suspect.
  No requirement covers repairing them, so nobody does it in this plan set.
- **Future, outside this plan set:** the test-window store (`engine/.research-test`) does not get
  `market_series.csv`. If a series method is ever promoted, its `lab test` preflight refuses until
  someone runs `market_series --refresh --store /home/miftah/seer/engine/.research-test` against
  that store's own window. The cache runs to 2026-10, so the series cover the test window.

## Rollback

- **Code:** `git revert <phase-3 commit>` on the feature branch. Nothing else depends on it until
  phase 4 lands.
- **Stores and lab DB:** nothing to undo; this phase wrote only scratch copies under
  `/tmp/claude-1000/phase3/`. The post-landing L1/L2 rollback is in the plan index.

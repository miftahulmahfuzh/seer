# Vendored data sources

Vendored inputs for `seer_engine.membership` / `python -m seer_engine universe refresh`, and the
SPY dividend history for the backtest benchmark (`seer_engine.backtest`).
Owner of this directory: the engine. Read by nothing else.

## sp500_history.csv: S&P 500

| | |
|---|---|
| Upstream | https://github.com/fja05680/sp500, file `S&P 500 Historical Components & Changes (Updated).csv` |
| Pinned commit | `a2430f2af0c79ddf0748e91de11bdeb1616ab5a7` (2026-09-07) |
| Raw URL | https://raw.githubusercontent.com/fja05680/sp500/a2430f2af0c79ddf0748e91de11bdeb1616ab5a7/S%26P%20500%20Historical%20Components%20%26%20Changes%20(Updated).csv |
| License | MIT, Copyright (c) 2019-2020 Farrell J. Aultman |
| Rows | 2,720 snapshots, 1996-01-02 .. **2026-08-18** (503 members on the last row) |
| sha256 | `36326709d46d6cd25834de5df457b16f5f96fad3a06b9beac28f7b88aa0b0d54` |

## ndx_history.csv: Nasdaq-100

| | |
|---|---|
| Upstream | https://github.com/thuningxu/sp500nq100, file `nasdaq100_components_history.csv` |
| Pinned commit | `1cc1de2770874293597a418b41b079e5337b260c` (2026-06-07) |
| Raw URL | https://raw.githubusercontent.com/thuningxu/sp500nq100/1cc1de2770874293597a418b41b079e5337b260c/nasdaq100_components_history.csv |
| License | **None declared** (no LICENSE file; GitHub API reports no license as of 2026-10-03). The file is derived from Wikipedia's "List of NASDAQ-100 companies" component and change tables, which are CC BY-SA 4.0; attribute Wikipedia and its contributors. |
| Rows | 112 snapshots, 2007-02-01 .. **2026-05-18** (101 members on the last row) |
| sha256 | `c7de3905bfdd228eefbd3c7df1539a1178bee9006a04688fb319314a646e18e8` |

## Format (both files)

`date,tickers`. `tickers` is a quoted comma list holding the **full** membership effective on
that date. Membership on day D is the latest row with `date <= D`. Share classes use a dot
(`BRK.B`, `BF.B`), the canonical form everywhere in Seer.

## membership_overrides.csv

`date,index_id,action,ticker,note`, where `index_id` is `SP500|NDX` and `action` is `add|remove`.
Index changes that happened **after** a snapshot file's last row, read from Wikipedia's change
tables. Each date's rows become one extra snapshot appended to that index. An override
dated on or before the snapshot file's last row is an **error**: once the upstream file covers
that date the change would be applied twice. When re-vendoring a newer upstream file, delete the
overrides it now covers.

## ticker_aliases.csv

`old,new,effective_date,note`. A ticker `old` in a snapshot dated **before** `effective_date` is
stored under `new`, the ticker yfinance and Massive use today (`universe.symbol` = `bars.symbol`).
`universe.source_symbol` keeps the ticker(s) the source used, oldest first, joined with `/`
(`FB/META`). A rename followed directly by its new ticker gives one continuous interval. Every
`old` points straight at the **current** ticker (chains such as HCP->PEAK->DOC are written
HCP->DOC and PEAK->DOC; the loader rejects chains). On/after `effective_date` the old ticker is
taken literally, so a ticker reused by another company later (ARNC) stays correct.
`tests/test_membership.py::test_vendored_aliases_check_out` checks every row against the
snapshot files.

## Known gaps

- **Nasdaq-100 before 2017:** two removals are missing from Wikipedia's change table, so
  **ENDP** (added 2015-12-21) and **CMCSK** (added 2014-12-22) are absent for the windows
  they should cover. Some 2007-2014 departures may carry a later symbol. 2015-2017 shows
  105-108 lines (multi-class Google/Fox/Discovery/Liberty). 2017 onward is clean (upstream README).
- **Ticker renames:** fja05680 sometimes back-fills the current ticker (BKNG appears in the S&P
  file from 2009, never PCLN). thuningxu keeps some old tickers until removal (CTRP until
  2021). Renames not listed in `ticker_aliases.csv` are stored under the historical ticker.
  yfinance does not know those, so the backfill logs them as unfetchable.
- **Delisted / acquired names** (and mergers where the ticker died, such as WRK, CELG, TWX) have
  no yfinance history. This is the survivorship bias the handover (section 3) already accepts.
- **Freshness:** the snapshots end on 2026-08-18 (S&P) and 2026-05-18 (NDX). Later changes
  live in `membership_overrides.csv`. The weekly `universe check` compares the computed current
  members with Wikipedia and fails on any drift.

## Re-vendoring

```sh
cd engine/data
SP_SHA=<new full sha>; NDX_SHA=<new full sha>
curl -fsSL -o sp500_history.csv \
  "https://raw.githubusercontent.com/fja05680/sp500/${SP_SHA}/S%26P%20500%20Historical%20Components%20%26%20Changes%20(Updated).csv"
curl -fsSL -o ndx_history.csv \
  "https://raw.githubusercontent.com/thuningxu/sp500nq100/${NDX_SHA}/nasdaq100_components_history.csv"
```

Then update this file: commit, last row, sha256. Drop the overrides the new files now cover,
then run `pytest tests/test_membership.py`, `python -m seer_engine universe check` and
`python -m seer_engine universe refresh`.

## spy_dividends.csv: SPY cash dividends (backtest benchmark)

| | |
|---|---|
| Upstream | Yahoo Finance via yfinance `Ticker("SPY").dividends` (per-share cash distributions by ex-date) |
| Fetched | 2026-10-03, yfinance 1.7.0 |
| Range | ex-dates 2015-01-01 onward; 47 rows, 2015-03-20 .. 2026-09-18 |
| License | Yahoo Finance data, personal/research use; not redistributed beyond this repo |
| sha256 | `3251a8525bfcb6e1e3fe7b74db88326122826c808be5a6005eba767fbb5b598a` |

`ex_date,amount_usd`, ascending, one row per ex-date. `amount_usd` is USD per share as yfinance
reports it (shortest float repr, not rounded). SPY has had no split since 2015, so no adjustment
applies. Read by `seer_engine.backtest.io.read_dividends` -> `benchmark.parse_dividends`, which
rejects a bad header, a non-positive amount or a non-ascending date. Used only for the
total-return SPY curve (`spy_tr`), which the P3 gate compares against; `bars` are not
dividend-adjusted, so the price-only curve understates SPY by roughly 1.3-1.8 %/yr.
`tests/test_benchmark.py::test_vendored_spy_dividends_parse_and_cover_2015_2026` checks 4 rows a
year 2015-2025, every ex-date an NYSE session, every amount in (0.5, 3).

Never edit rows by hand. To refresh (for a later backtest end date), re-run the fetch with the
engine venv and update the table above:

```sh
engine/.venv/bin/python - engine/data/spy_dividends.csv <<'EOF'
import sys
from datetime import date
from decimal import Decimal
import yfinance as yf

START = date(2015, 1, 1)
out_path = sys.argv[1]
s = yf.Ticker("SPY").dividends
if s is None or len(s) == 0:
    sys.exit("yfinance returned no SPY dividends; stop and report")
rows = []
for ts, amount in s.items():
    d = ts.date()
    if d < START:
        continue
    a = Decimal(repr(float(amount)))
    if not a.is_finite() or a <= 0:
        sys.exit(f"bad amount {amount!r} on {d}; stop and report")
    rows.append((d, a))
rows.sort()
if any(b[0] <= a[0] for a, b in zip(rows, rows[1:])):
    sys.exit("duplicate ex_date; stop and report")
with open(out_path, "w", encoding="utf-8", newline="\n") as f:
    f.write("ex_date,amount_usd\n")
    for d, a in rows:
        f.write(f"{d.isoformat()},{format(a, 'f')}\n")
print(f"{len(rows)} rows {rows[0][0]} .. {rows[-1][0]}")
EOF
```

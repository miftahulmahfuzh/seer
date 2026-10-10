# Vendored data sources

Vendored inputs for `seer_engine.membership` / `python -m seer_engine universe refresh`, the
SPY dividend history for the backtest benchmark (`seer_engine.backtest`), and the ticker -> SEC
CIK map for the fundamentals pipeline (`seer_engine.cik`).
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

## ticker_cik.csv: ticker -> SEC CIK, point in time

| | |
|---|---|
| Upstream | SEC EDGAR: `https://www.sec.gov/files/company_tickers.json`, `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=<ticker>&output=atom`, `https://www.sec.gov/Archives/edgar/cik-lookup-data.txt`, `https://data.sec.gov/submissions/CIK<cik>.json`; company names for dead tickers from Massive `/v3/reference/tickers?market=stocks&active=false` |
| Generated by | `engine/scripts/build_ticker_cik.py` (committed; run by hand, never imported) |
| Fetched | 2026-10-05 |
| Scope | every S&P 500 / Nasdaq-100 ever-member on or after 2009-01-01 — `membership.symbols_since(membership.compute_universe(), date(2009, 1, 1))`, **913** symbols on 2026-10-05. The floor is `seer_engine.cik.SINCE`; it was 2015-01-02 until 2026-10-05, which clamped 525 starts to a date that was not theirs. |
| Rows | 944 rows covering 913 symbols (`manual` 152, `current` 628, `edgar` 49, `exact` 84, `fuzzy` 0); 540 rows start at the 2009-01-01 floor and **none** starts at 2015-01-02 |
| License | US government work, public domain (SEC). Massive is used only for company names, which are facts, not for redistributed data. |
| sha256 | `15b86213e280972093f8bf6f9183e27b850c33b6946b1ecb07583a3b3dd2535a` |

`symbol,cik,start_date,end_date,company_name,source,note`, sorted by `(symbol, start_date)`.
One row per **(symbol, filer) tenure**: `cik` is the SEC Central Index Key of the company whose
shares traded under `symbol` over `[start_date, end_date)`. `end_date` is **exclusive** and
empty while the mapping is still current — the same semantics as `universe.end_date`. `cik` is
exactly 10 digits, zero-padded, or the literal `NONE` for a symbol with no EDGAR filer at all
(`note` is then mandatory and the row must be the symbol's only one). `source` is how the row
was produced: `current` (company_tickers.json), `edgar` (EDGAR's ticker lookup), `exact` /
`fuzzy` (company-name match against cik-lookup-data.txt), `manual` (hand-audited in
`build_ticker_cik.py`). `note` is mandatory for `fuzzy` and `manual`.

**Why there is an interval and not a bare pair.** A ticker alone never identifies a company.
Measured 2026-10-05, EDGAR's own ticker lookup answers `MON` with Monument Circle Acquisition
Corp (`0001828325`), `PLL` with Piedmont Lithium (`0001728205`), `ALTR` with Altair Engineering
(`0001701732`) and `LLL` with JX Luxventure (`0001546383`) — in every case the company holding
the recycled ticker today, not the index member that held it in the backtest window. `CA` and
`DTV` have been reissued too (an Xtrackers ETF share class and DTE Energy corporate units).
Separately, two symbols change filer *inside* the window without changing ticker: `WRK`
(WestRock `0001636023` → `0001732845` at the 2018-11-02 KapStone close) and `GOOG`/`GOOGL`
(Google Inc `0001288776` → Alphabet `0001652044` at the 2015-10-02 holdco reorg).

The reverse is not an error: **one CIK legitimately backs several symbols.** Among the
ever-members `GOOG`/`GOOGL`, `FOX`/`FOXA`, `NWS`/`NWSA`, `UA`/`UAA`, `CMCSA`/`CMCSK` and
`BATRA`/`BATRK` are share classes of a single filer. No uniqueness check is applied to `cik`.

`seer_engine.cik.load_ticker_cik` rejects a header that is not exactly the seven columns above,
a `cik` that is not 10 digits (or `NONE`), a bad or non-increasing date, an unknown `source`, a
missing required `note`, a file not sorted by `(symbol, start_date)`, a duplicate
`(symbol, start_date)`, two overlapping intervals for one symbol, an open interval that is not
the symbol's last row, and a `NONE` row that shares its symbol with another row.
`tests/test_cik.py` additionally asserts that the vendored file covers every ever-member with no
coverage gap, and that each of `CA`, `MON`, `PLL`, `ALTR`, `LLL` and `DTV` resolves to the
company that held the ticker during its membership and raises for a date after it.

### Re-vendoring

```sh
export SEC_CONTACT_EMAIL='<a contact address, as SEC's fair-access policy requires>'
export MASSIVE_API_KEY='<from .env.local>'
python engine/scripts/build_ticker_cik.py --out engine/data/ticker_cik.csv --cache engine/.cache/cik
```

Network artifacts are cached under `--cache` (gitignored), so re-runs after editing `MANUAL`
cost nothing; delete the cache to refetch. From a cold cache the first pass takes 20–40 minutes,
almost all of it SEC's 10 req/s fair-access pacing and Massive's free-tier 5 calls/min.

The script exits 1 and writes nothing when any of three lists is non-empty:

- **`UNRESOLVED`** — no tier answered. Find the CIK by hand and add a `MANUAL` entry.
- **`SCREEN`** — the candidate filed no periodic report anywhere inside the span. Wrong company,
  a filer change mid-span, or a genuinely silent filer.
- **`EARLY`** — the candidate filed none within `EARLY_WINDOW_DAYS` (450) of the span's **start**,
  so the start reaches back past this filer. Split the tenure into two dated `MANUAL` rows, or
  exempt it in `EARLY_EXEMPT` with the reason.

Resolve each against `https://data.sec.gov/submissions/CIK<cik>.json` and record what you read in
the row's `note` — that column is the audit trail, and
`awk -F, '$6=="manual" || $6=="fuzzy"' ticker_cik.csv` is the review. In a `MANUAL` entry an
**empty `start` means "the symbol's membership start, from `spans()`"**; write a literal date only
when the tenure genuinely begins later. An `end` is always literal, and **an end is never pushed
forward** — a truncated end is the whole defence against a recycled ticker resolving to a later
holder. Then update the Scope, Rows and sha256 lines above and run
`"$SEER_PY" -m pytest engine/tests/test_cik.py -q`.

### The 2026-10-05 hand audit

The automated tiers alone do not produce a trustworthy file, and the two tiers a reader should
distrust are `fuzzy` and `exact`. On the **first** 2026-10-05 vendoring, at the 2015-01-02
floor, the generator needed three passes and **70 hand-audited `manual` rows**; the re-floor to
2009-01-01 later the same day took it to **152 symbols / 183 rows** (see the re-floor subsection
below), and the categories in the table are the first vendoring's. Every row carries its
evidence in the CSV's own
`note` column — that column is the audit trail, and it is mandatory for `manual` and `fuzzy`, so
`awk -F, '$6=="manual" || $6=="fuzzy"' ticker_cik.csv` is the review. The categories were:

| Category | Rows | What went wrong |
|---|---|---|
| Seeded recycled tickers and in-window filer changes | 9 | `CA`, `MON`, `PLL`, `ALTR`, `LLL`, `DTV`, plus `WRK` and `GOOG`/`GOOGL` which change filer mid-span |
| Reached no automated tier at all | 33 | mostly acquired or renamed S&P names whose company name does not match `cik-lookup-data.txt` after suffix stripping |
| Caught by the periodic-filing screen | 27 | 16 recycled tickers where tiers 1-2 answered with today's holder, and 11 where name matching hit a defunct same-name entity |
| Caught by reading the `fuzzy` rows | 1 | `HAR` — see below |

**The screen is a net, not a gate, in both directions.** It missed `LLL` and `DTV` (the wrong
company had filed inside the span) and it also missed `HAR`: difflib matched Massive's
`Harman International Industries` to `AMERICAN INTERNATIONAL INDUSTRIES` (`0001073146`), an
unrelated company that filed 4 periodic reports inside the span and so passed. The real Harman is
`0000800459`. **There are now zero `fuzzy` rows in the file, and a future re-vendoring must read
every one it produces** rather than trusting the screen to catch them.

Conversely the screen flags correct rows, so `build_ticker_cik.py` carries a `SCREEN_EXEMPT`
table — 11 symbols whose absence of a periodic filing was verified and explained, each with its
reason in the code. Three distinct reasons appear, and they recur: a **bank** rather than a bank
holding company files its periodic reports with the FDIC under Exchange Act s12(i) and not with
the SEC at all (`FRC`, `SBNY`); a **short span** can end before the next 10-K falls due (`SWY`
25 days, `PETM` 10 weeks, `FCPT` 7 days, `VSNT` 4 days); and a **current member** whose span
opened weeks ago has had no filing due yet (`BE`, `NBIS`, `P`, `RDDT`, `VMRK`).

`NDOI` is the file's only `NONE`. It is a phantom in the Wikipedia-derived `ndx_history.csv`,
present in every snapshot from 2007-02-01 to 2016-07-18 and absent from `company_tickers.json`,
from browse-edgar's ticker lookup, from `cik-lookup-data.txt` and from all 21,250 of Massive's
delisted US tickers. The same file carries `NLTI`, a transposition of `NTLI` (NTL Inc), so
mangled tickers are a known defect of that source; correcting it belongs in
`membership_overrides.csv`, not here.

### The 2026-10-05 re-floor, from 2015-01-02 to 2009-01-01

`cik.SINCE` was the first day of the **bars** window borrowed as a **map** floor. `spans()`
clips every membership start to it, so 525 of the 798 shipped rows claimed a `start_date` of
2015-01-02 that was not those companies' first membership date — and because the projection in
`backtest/io.py` joins `fundamental_facts.filed >= ticker_cik.start_date`, the map discarded
every fact filed before 2015, 181,491 of which were already stored. The floor is now 2009-01-01,
the first year SEC XBRL company facts exist at all; 1996 was rejected because no fundamentals
exist there at any price and it would cost ~470 further hand audits (1265 ever-members against
913).

Measured: 913 symbols (up from 795), 118 entirely new, **0 lost**, 541 existing starts moved
earlier, 540 rows now sitting at the floor, and **0 rows at 2015-01-02** — no symbol
in the universe has that as its real first-membership date, which is what made the clamp
visible.

Moving starts backwards creates a hazard the old file did not have: a start that reaches back
past a handover attributes the *later* filer's fundamentals to the *earlier* company's prices.
The `SCREEN` net cannot see it, because the later filings still fall inside the span. That is
what `EARLY_WINDOW_DAYS` and the `EARLY` screen are for, and what the `EARLY_EXEMPT` table
records exceptions to. `EARLY` still cannot see a handover between two filers that both reported
throughout — `GOLD` (Randgold in 2011–2013, Barrick's ticker today) and `S` (Sprint Nextel, now
SentinelOne) are that case and live in `MANUAL`.

## eodhd_alias_hints.csv

`symbol,code,note`. Hand-checked EODHD codes for index members whose store symbol is not the code
EODHD keeps their history under (a bankruptcy `Q` ticker, a rename, a re-listing). Read only by
`seer_engine.survivorship_alias`, which treats each row as one more *candidate*: it is accepted only
when the fetched series has rows on the member's own index days and passes the survivorship-check
cleaning, exactly like a code found by name or suffix. Each `code` was checked against the `Name`
in EODHD's `exchange-symbol-list/US` (live and delisted) on 2026-10-10; the note says which company
it is. Owner of this file: the engine. No vendor data in it, codes and names only.

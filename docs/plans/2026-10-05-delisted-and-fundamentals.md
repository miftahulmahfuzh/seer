# Delisted stocks and fundamentals — decision doc

Status: diagnostic run 2026-10-05, decision pending owner sign-off.

Raised by the `/sera` lab note "Delisted stocks and fundamentals" (2026-10-04): the store has no
delisted names and no fundamentals, so every stock result carries survivorship bias and the
best-documented factors after momentum (value, quality, profitability, earnings surprise) cannot
be tested at all.

**The headline the lab note understated:** `runner.survivorship()` — the engine's own gap report,
which already exists — says **23.8 % of member-sessions in the development window have no bar**.
Every single-stock result in P7a's 54 trials was computed on a cross-section missing roughly one
name in four.

**Recommendation.** Three actions, in this order: (1) recover ~10 names for free with
`ticker_aliases.csv` rows; (2) build the SEC EDGAR fundamentals pipeline, also free; (3) buy one
month of **Massive Advanced ($199)** for flat files and re-backfill, then cancel. Massive
Developer ($79) is **not** a viable fallback — see §2.3.

---

## 1. What the diagnostic found

Run against the live Neon store and the vendored membership files on 2026-10-05. Reproduction in
the appendix.

### 1.1 The hole is exactly 133 symbols

| | |
|---|---|
| Ever-members of SP500 ∪ NDX since 2015-01-02 | 819 |
| `backfill_log` status `ok` | 663 |
| `backfill_log` status `empty` | **133** |
| `backfill_log` status `failed` | 0 |

All 133 were index members on or after 2015-01-02, so every one sits inside the backtest window.
By index: SP500 only 100, NDX only 10, both 23. Exits run ~11/year, every year, 2015 through
2026 — there is no "skip a bad year" workaround.

### 1.2 All 133 are genuinely dead — this is not a fetch bug

Worth checking, because the list contains names that read as alive (CMA, SEE, TGNA, HBI, CTRA,
HOLX). Three independent confirmations:

- **Massive grouped-daily for 2026-10-02** returned 12,601 tickers that traded. **0 of the 133
  appear.**
- **Yahoo's chart API 404s all of them** under raw `curl`, no client library involved, while the
  same call for AAPL returns HTTP 200.
- yfinance `download()` returns 21 rows for `["AAPL","MSFT"]` and 0 for CMA / SEE / TGNA in the
  same session.

The apparent survivors are simply exits that closed after mid-2026. The `empty` classification in
`backfill_log` is accurate.

### 1.3 Size of the hole, from the engine's own report

`survivorship(market, 2015-01-02, 2026-10-02)` over 1,817,429 loaded bar rows:

| year | member-sessions | missing | never fetched | other | gap |
|---|---:|---:|---:|---:|---:|
| 2015 | 132,295 | 31,037 | 25,333 | 5,704 | **23.5 %** |
| 2016 | 133,339 | 26,299 | 21,690 | 4,609 | 19.7 % |
| 2017 | 131,396 | 21,315 | 18,047 | 3,268 | 16.2 % |
| 2018 | 131,497 | 18,413 | 15,840 | 2,573 | 14.0 % |
| 2019 | 131,191 | 14,280 | 12,506 | 1,774 | 10.9 % |
| 2020 | 132,794 | 11,969 | 10,704 | 1,265 | 9.0 % |
| 2021 | 132,785 | 10,108 | 8,848 | 1,260 | 7.6 % |
| 2022 | 132,264 | 7,876 | 6,832 | 1,044 | 6.0 % |
| 2023 | 130,471 | 5,487 | 4,686 | 801 | 4.2 % |
| 2024 | 130,865 | 4,137 | 3,381 | 756 | 3.2 % |
| 2025 | 129,370 | 2,618 | 1,867 | 751 | 2.0 % |
| 2026 | 97,750 | 697 | 241 | 456 | 0.7 % |
| **all** | **1,546,017** | **154,236** | **129,975** | **24,261** | **10.0 %** |

**Development window 2015-01-02 → 2015-10-16: 104,913 member-sessions, 24,959 missing — 23.8 %.**

The gap decays monotonically toward the present because a name delisted in 2016 is absent for
every session before it died. That puts the worst of it precisely where the lab develops.
`docs/plans/2026-10-04-method-lab-design.md` sets the dev window at ≤ 2015-10-16 and holds
2015-10-19 → data end as the untouched test window, so the damage is concentrated in the only
window P7a was allowed to look at.

A secondary issue the same report surfaces: `missing_other` = 24,261 member-sessions where the
symbol *has* bars, just not that day. Partial histories, separate from delisting, worth a look
after the main fix.

### 1.4 One correction to the lab note

Survivorship here is **not** purely optimistic. The exit population mixes acquisitions that
closed at a premium (ATVI, CELG, PXD, ANSS, JNPR, HES) with collapses (SIVB, FRC, ENDP, MNK,
FTR, CHK). What is certain is that the cross-section is distorted at both tails — which is
exactly where momentum and reversal load — not that results are uniformly flattered.

### 1.5 A live correctness bug: recycled tickers

Resolving the 133 against Massive's delisted-ticker reference (23,462 US tickers) turned up
names where **the ticker now belongs to a completely different company**:

| Ticker | Was (S&P member) | Is now |
|---|---|---|
| `CA` | CA Inc. | Xtrackers California Municipal Bonds ETF |
| `MON` | Monsanto | Monument Circle Acquisition Corp. |
| `PLL` | Pall Corp | Piedmont Lithium |
| `ALTR` | Altera | Altair Engineering |
| `LLL` | L3 Technologies | JX Luxventure Limited |
| `DTV` | DirecTV | DTE Energy 2016 Corporate Units |

The preregistration doc already flagged this risk (§31). It is now confirmed with specific names.
**Any fix must key on (ticker, date) or on a stable identifier — composite FIGI or CIK — never on
ticker alone.** Sourcing by bare ticker would silently graft an ETF's price history onto
CA Inc.'s index membership. This is worse than missing data, because it produces a number
instead of a gap.

---

## 2. Gap A — prices for the 133 dead names

### 2.1 Free recovery first: ~10 names are renames, not deaths

Some of the 133 are companies that still trade under a different ticker. Confirmed against the
live ticker set:

| Old | New | | Old | New |
|---|---|---|---|---|
| ADS | BFH | | VIAB | PARA |
| CCE | CCEP | | CHK | EXE |
| CTL | LUMN | | ESV | VAL |
| GPS | GAP | | DWDP | DD |
| WYND | TNL | | DISCK | WBD |

Adding rows to `engine/data/ticker_aliases.csv` recovers these at zero cost, using the mechanism
the repo already has.

**Caveat, and it matters:** only *pure* renames are safe to alias (CTL→LUMN, GPS→GAP, WYND→TNL,
ADS→BFH, ESV→VAL). The merger cases are not clean continuations — DWDP→DD in particular, since
DowDuPont split into DD / DOW / CTVA, so pre-split DWDP prices are not DD's history in any simple
sense. Alias the pure renames; handle the merger cases as delistings with a terminal value.

That leaves roughly 120 names genuinely needing price data.

### 2.2 Ruled out by measurement

| Source | Result |
|---|---|
| yfinance / Yahoo | hard 404 for all 133 — this is the status quo and retrying will not fix it |
| Stooq per-symbol CSV | `stooq.com/q/d/l/?s=<sym>.us&i=d` returns a JavaScript anti-bot challenge, not CSV |
| Stooq bulk | `stooq.com/db/h/d_us_txt.zip` returns HTTP 404 |
| Massive free tier | `HTTP 403 NOT_AUTHORIZED — "Your plan doesn't include this data timeframe"` for ATVI 2015→2023 |

Stooq was the one plausible free bulk route and it is closed. I could not verify any free source
of daily history for delisted US equities today.

### 2.3 Massive has the data; it is purely a plan gate — and only Advanced works

Inside the free tier's 2-year window the delisted names are served normally: `CMA` 2024-10-01 →
2026-09-30 returned **331 bars**. The data is there, behind the timeframe gate.

| Plan | /mo | History | Reaches back to | Covers dev window (2015-01-02 → 2015-10-16)? |
|---|---|---|---|---|
| Basic (current) | $0 | 2 years | 2024-10 | no |
| Starter | $29 | 5 years | 2021-10 | no |
| Developer | $79 | 10 years | 2016-10 | **no** |
| **Advanced** | **$199** | 20+ years | 2006 or earlier | **yes** |

This is the key constraint and it kills the cheap fallback. Ten years back from today is
2016-10-05 — it does not reach 2016-01-01, let alone the dev window, which sits entirely in the
first ten months of 2015. **Developer buys nothing for the window that actually matters.**

All paid plans include flat files (`day_aggs_v1`): one gzipped CSV per session holding every
ticker that traded, survivorship-free by construction, ~2,950 files for 2015→now. Those files
carry the ticker-as-of-that-date, which is also the clean answer to the recycling bug in §1.5.

**This is a one-time purchase, not a subscription.** Pull the flat files, land them in Neon,
cancel. The free-tier nightly keeps working afterwards because it only ever asks for today.

Verify before buying: that the flat-file archive honours the same history window as the API on a
given plan, and Massive's terms on retaining downloaded historical data after cancellation
(internal use is normally fine; redistribution is not).

### 2.4 Side benefit worth real money

Flat-file day aggregates are **unadjusted**. Combined with the `split_adjustments` table the
engine already maintains, that gives reproducible point-in-time adjustment. The current backfill
stores yfinance prices "adjusted as of the moment of download" — a latent correctness wart
already flagged in `docs/runbooks/data-pipeline.md`. Re-backfilling from flat files retires it.

### 2.5 Alternatives

| Option | Cost | Verdict |
|---|---|---|
| EODHD EOD All World | $19.99/mo | **no** — delisted depth is solid only from 2018, leaving 75 of the 133 exits unsolved and the entire dev window untouched |
| Norgate Platinum | $630/yr | survivorship-free US EOD **plus** historical index constituents to 1990; would also replace the vendored membership CSVs. Desktop delivery, no fundamentals. Viable but 3× the cost for this job |
| Sharadar SEP + SF1 | low hundreds/mo | solves Gap A and Gap B together; worth revisiting if the EDGAR pipeline proves harder than §3 suggests |
| Delisting-return table only | $0 | partial, see below — do it regardless |

### 2.6 The $0 partial fix, worth doing regardless

Build `engine/data/delisting_returns.csv`: ~120 rows of `symbol, last_date, terminal_value,
reason`. Acquisitions have a published deal price; bankruptcies terminate near zero. This is
exactly CRSP's `DLRET` field and it is the single thing most retail backtests lack.

It does not give the price *path*, so it cannot fix momentum ranking — but it stops the backtest
silently dropping each name's terminal return. It stays useful after the flat files land, as a
validation set against which to check the purchased data.

---

## 3. Gap B — fundamentals

**This half is free and the data is complete.** SEC EDGAR never deletes a filer, so dead
companies are fully present.

### 3.1 Verified coverage for dead filers

`data.sec.gov/api/xbrl/companyconcept/...`, `us-gaap:Assets` on 10-K/10-Q:

| | Facts | Filed range |
|---|---|---|
| ATVI (CIK 718877) | 114 | 2009-08-07 → 2023-07-31 |
| TWTR (CIK 1418091) | 68 | 2014-05-08 → 2022-07-26 |
| CELG (CIK 816284) | 84 | 2009-07-31 → 2019-10-31 |
| K (CIK 39899) | 138 | 2009-07-30 → 2026-03-02 |

Each fact carries `accn`, `form`, `fy`, `fp` and **`filed`**. `filed` is the no-look-ahead
boundary: take the latest fact with `filed <= t`. Restatements appear as separate facts, so
as-reported is reconstructible rather than overwritten.

Bulk access: `companyfacts.zip` is **1.41 GB**, one download, every filer. The DERA quarterly
Financial Statement Data Sets (2009Q2→now, `sub.txt`/`num.txt`) are the relational alternative.

### 3.2 Concept coverage across 8 dead filers

| Metric | Covered | Tag variants |
|---|---|---|
| revenue | 8/8 | 2 (`Revenues`, `RevenueFromContractWithCustomerExcludingAssessedTax`) |
| net income | 8/8 | 1 |
| assets | 8/8 | 1 |
| equity | 8/8 | 1 |
| operating cash flow | 8/8 | 1 |
| diluted EPS | 8/8 | 1 |
| shares outstanding | 8/8 | 1 (`dei:EntityCommonStockSharesOutstanding`) |
| operating income | 6/8 | missing for SIVB, PXD |
| **gross profit** | **2/8** | missing for ATVI, TWTR, TWX, SIVB, PXD, K |

Better than the folklore suggests — the concept ladder is a real but bounded job for large-cap
filers. **Gross profit is the exception**, so gross-profitability (Novy-Marx) needs
`Revenues − CostOfRevenue` derived rather than read, with a documented fallback.

Shares outstanding is cover-page tagged and filed-dated, so **market cap is point-in-time too** —
value factors are fully supported.

### 3.3 ticker → CIK: 74 % automated, 35 names manual

**0 of the 133 resolve** through SEC's `company_tickers.json` (10,440 current pairs). The bridge
is required for every missing name. Measured result of the two-step recipe:

1. Massive delisted reference (23,462 tickers) → company name. **130/133 found** (ADS, CCE and
   NDOI are absent, being renames rather than delistings).
2. Name → CIK against SEC's `cik-lookup-data.txt` (39 MB, **1,061,750** pairs, includes every
   dead filer), after stripping corporate suffixes.

| | |
|---|---|
| exact name match | 94 |
| fuzzy match (ratio ≥ 0.90) | 4 |
| **automated total** | **98 / 133 (74 %)** |
| needs manual mapping | 35 |

The 35 split into three groups: share-class oddities (CMCSK, LMCA, LMCK, QRTEA, DISCK, BRCM),
recycled tickers where the automated match found the *wrong* company (§1.5 — these must be
hand-checked, not accepted), and vendor name quirks ("Shire pic", "Michael Kors Holding Lmtd").
A day's work including verification, vendored as `engine/data/ticker_cik.csv` in the same style
as the existing `ticker_aliases.csv`.

### 3.4 What EDGAR cannot give: analyst consensus

Earnings *surprise versus consensus* needs estimates, which the SEC does not hold. The existing
Finnhub key returns only **4 quarters** (`/stock/earnings` for AAPL: 2025-09-30 → 2026-06-30).
Not backfillable for a 2015-start backtest.

- **SUE from EDGAR, free — recommended.** Standardized unexpected earnings on a seasonal random
  walk (EPS_q − EPS_{q−4}, scaled by the dispersion of recent surprises) is computable entirely
  from the facts above. Foster-Olsen-Shevlin; PEAD is documented on this definition.
- **Consensus surprise, paid.** Needs Sharadar, Zacks via Nasdaq Data Link, or similar. Defer.

Start logging Finnhub's 4-quarter window nightly from today regardless — it costs nothing, and in
three years it becomes a real consensus history.

---

## 4. Decision

| | Gap A (prices) | Gap B (fundamentals) |
|---|---|---|
| Blocked on money? | yes — no free route survives | no — $0 |
| Cost | $199 once (Massive Advanced, one month) | $0 |
| Unlocks | honest momentum/reversal; every stock result | value, quality, profitability, SUE |
| Effort | S3 downloader + re-backfill | concept ladder + ticker→CIK map + loader |

Independent tracks; they can run in parallel. **Gap B is the larger research unlock and costs
nothing, so it must not wait on the purchase decision.**

Recommended order:

1. **Alias rows for the ~5 pure renames** ($0, hours) — immediate, uses existing machinery.
2. **Delisting-return table**, ~120 rows ($0) — partial fix for Gap A and a validation set for
   whatever lands later.
3. **SEC EDGAR fundamentals pipeline** ($0) — biggest unlock, longest lead time, no dependency on
   any purchase.
4. **One month of Massive Advanced** ($199) — flat files 2015→now, re-backfill all 796 symbols
   unadjusted, apply splits from the existing table, cancel the plan.

---

## 5. Open questions for the owner

1. **Approve $199 for one month of Massive Advanced?** There is no cheaper option that reaches
   the dev window. The alternatives are Advanced, Norgate at $630/yr, or accepting a 23.8 % gap.
2. **What happens to P7a's 54 trials?** They were run on a dev-window cross-section missing
   roughly one name in four. Once the data lands, are single-stock results re-run, or is the
   existing frontier retired? This is a lab-integrity question, not a data question, and it
   should be answered before P7b spends a test-window look.
3. **Re-backfill all 796 symbols from flat files, or only the ~120?** All 796 gives one
   consistent, unadjusted, reproducible adjustment regime. Only the 120 is cheaper but leaves two
   regimes in one table. Recommend all 796.
4. **Does the recycled-ticker finding (§1.5) warrant an immediate guard** in `universe refresh` —
   rejecting a symbol whose Massive reference name disagrees with the index member's name —
   independent of everything else here?

---

## Appendix — reproducing the diagnostic

```sh
python3 -m venv engine/.venv && engine/.venv/bin/pip install -e 'engine[dev]'

# the hole
engine/.venv/bin/python -c "
from seer_engine import config, db
config.load_env()
with db.connect() as c, c.cursor() as cur:
    cur.execute(\"select status, count(*) from backfill_log group by status\")
    print(cur.fetchall())"

# the authoritative gap, per year and for the dev window
engine/.venv/bin/python -c "
from datetime import date
from seer_engine import config, db
from seer_engine.backtest.io import load_market
from seer_engine.backtest.runner import survivorship
config.load_env()
with db.connect() as conn:
    conn.autocommit = False
    market, n = load_market(conn)
for g in survivorship(market, date(2015,1,2), date(2026,10,2)):
    print(g)"

# confirm they are dead: grouped daily for the last session, intersect with the empty list
# https://api.massive.com/v2/aggs/grouped/locale/us/market/stocks/2026-10-02?adjusted=true

# delisted reference (23,462 tickers, ~24 pages at 5 calls/min on the free tier)
# https://api.massive.com/v3/reference/tickers?market=stocks&active=false&limit=1000

# confirm EDGAR has a dead filer
curl -A "seer-research <email>" \
  "https://data.sec.gov/api/xbrl/companyconcept/CIK0000718877/us-gaap/Assets.json"

# name -> CIK for dead filers
curl -A "seer-research <email>" -O \
  "https://www.sec.gov/Archives/edgar/cik-lookup-data.txt"
```

Scratch outputs from the 2026-10-05 run (the 133 symbols with membership windows, the live-ticker
set, the 98-row CIK map, concept coverage) are not committed; regenerate with the commands above.

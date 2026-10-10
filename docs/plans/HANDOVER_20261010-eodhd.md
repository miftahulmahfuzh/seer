# Handover: 2026-10-10, getting the most out of the paid EODHD month

**For:** an `/analyze` session that plans this work and then builds it.
**Targets:** **§5.1**, a separate store that adds the delisted companies, so we can measure how much
survivorship bias flatters lab results. **§5.2**, market-wide series (VIX, Treasury-yield indexes)
as data that strategies can read. Do §5.1 first; §5.2 is smaller and independent.
**State at handover:** `main` @ `18dad84` or later. 3,513 engine tests passing. A Sera batch
(`sera-20261010-1742`, tmux window `@6`) is running and writing to `lab/lab.sqlite`; see §6.

**Done (2026-10-10):** §5.1 and §5.2 are built on `feature/eodhd-survivorship-market`. The
survivorship check's results, coverage table and the journaled answer are in
`docs/lab/survivorship/` (README, grid, insight; lab synthesis insight 149). The check store stays
a cross-check, not a gate (plan D1).

---

## 1. Why this exists

The owner paid **$19.99 for one month of EODHD's "EOD Historical, All-World" plan** (personal
licence) and canceled the same day. **The key stays valid until 2026-11-10.** It is
`EODHD_API_TOKEN` in the repo-root `.env.local`, with 100,000 calls a day; about 3,000 are used so
far. The owner's instruction: *exploit this paid data as much as possible, and get a definite answer
on whether it can improve our methods.* Passing the gate is not required. Clarity is.

Three things came out of the month so far:

1. **Dividend announcement dates.** Built, shipped, and in the dev store (commit `6699ad0`, lab
   insight 112). The Sera batch is testing whether they help, with paired controls. Not this
   handover's job.
2. **Daily prices for the 522 index members the store could not serve.** Mostly delisted:
   bankruptcies, buyouts, renamed tickers. This is §5.1.
3. **Market series:** the VIX family, Treasury-yield indexes, index levels, gold and USD/IDR. This is §5.2.

## 2. What is already downloaded

All of it is in `engine/.cache/eodhd/` (gitignored, about 215 MB, **on the PC only, not on the GPD**).
Copy the folder if you work on the other laptop. The repo is public and the licence is personal use,
so **never commit raw vendor data** and never put it in `web/data/`. Derived results are fine.

| Path | What | Notes |
|---|---|---|
| `dividends/<SYM>.json` | `/api/div` for every store symbol + every unserved member | Already used by `python -m seer_engine dividend_announcements`; the format is in `commands/dividend_announcements.py` |
| `eod/<SYM>.json` | `/api/eod/<SYM>.US?from=1993-01-01`, the full history through 2026-10-09, for all 522 entries in `unserved.csv` | A JSON list of `{date, open, high, low, close, adjusted_close, volume}`, or `null` (404). **`close`/`open`/`high`/`low` are RAW, not split-adjusted.** `adjusted_close` is split **and** dividend adjusted (AAPL 2008-09-15: close 140.36, adjusted_close 4.198). |
| `splits/<SYM>.json` | `/api/splits/<SYM>.US?from=1990-01-01` for the same 522 | `[{date, split: "2.000000/1.000000"}]` or `null` |
| `market/<T>.json` | `/api/eod/<T>?from=1990-01-01` | VIX.INDX (from 1990), VIX3M.INDX (from 2007-11), VXV.INDX (2006-07..2020-07, the old VIX3M name), VIX9D.INDX (2011), VXN.INDX (2001), VVIX.INDX (2006), TNX/FVX/TYX.INDX (10y/5y/30y yield indexes, from 1993-11), IRX.INDX (13-week bill, 1990), GSPC/NDX/DJI.INDX, USDIDR.FOREX, XAUUSD.FOREX |
| `symbols-US-delisted.json`, `symbols-US-live.json` | `/api/exchange-symbol-list/US` (with and without `delisted=1`) | Code + company name; useful for identity checks |

The plan **cannot** give (all return 403): fundamentals, the earnings calendar, insider
transactions, government bond yields (`.GBOND`), intraday prices, options, index constituents,
technicals. `news` works but only for recent items. `eod-bulk-last-day/US?date=YYYY-MM-DD` **does**
work: the whole US market for one day, delisted names included (LEH, WM and BSC are there on
2008-09-12). Each bulk call costs 100 calls, so about 1,000 calls a day are affordable. It could fill
gaps, but bulk rows are keyed by EODHD's *current* code (Enron is `ENRNQ`, not `ENE`), so matching
needs the alias work.

## 3. What the probe measured (scripts were throwaway; re-derive, don't trust blindly)

Coverage of **index-member days**: sessions 1996-01-02..2015-10-16 on which a symbol was in the
S&P 500 ∪ Nasdaq-100 per `research._universe(None)`, ETFs excluded. "Store now" means the symbol has
a bar in `engine/.research/bars.csv` that day.

| | store now | + EODHD (any) |
|---|---|---|
| all 1996-2015 | 58.6% | 81.8% |
| 1996 / 1997 | 39.9% / 42.1% | 46.5% / 48.7% (EODHD's delisted series mostly **start 1997-12-31**) |
| 1998 | 45.5% | 71.7% |
| 2008 | 62.5% | 88.1% |
| 2009-2015 | 65-76% | 90-94% |

Per symbol, over its own membership days, with this rule: no hole over 10 sessions, and no
1-session move in `adjusted_close` beyond 2× either way.
- **260 clean.** 444,946 of 493,653 member-days covered. These alone take coverage to about 76%.
- **61 suspect** (145,831 member-days). Three kinds of fault:
  - **Unadjusted splits.** Many jumps are exactly 2.0× (AVP, BCR, CTX, CVH): fixable from `splits/`.
  - **Absurd data errors.** CFC 4540×, ACS 267×, FBF 775×, CBE 167×.
  - **Reused tickers spliced into one series.** A long hole inside or around the membership: MER
    jumps 2008-12-31 → 2018-08-28; CGP, FPC, IACI, JH, BGEN are similar. A new company took the code.
- **201 with nothing** in their membership, among them WorldCom (`WCOEQ`), ABX, DOW, DELL, CHK,
  CEG and CA. Many are tickers now held by a different live company.
- Spot checks: Enron (`ENRNQ`) 1997-12-31..2004; WaMu (`WAMUQ`) from 1997-12-31; Countrywide (`CFC`)
  from 1999; Bear Stearns (`BSC`) **only from 2008-03-17**, its collapse week; Compaq (`CPQ`) from 1999.
- The 136 series with a >2.5× one-day move include real collapses as well as errors, so a jump
  filter alone cannot tell them apart. Real bankruptcies must stay in. Dropping them would bring
  survivorship bias back by the side door.

## 4. How the store works (read before designing)

- `engine/src/seer_engine/research.py` is the store: `bars.csv`, `dividends.csv`, `fx.csv`,
  `unserved.csv` (the four `DATA_FILES`) plus `OPTIONAL_DATA_FILES` (`fundamentals.csv`,
  `dividend_announcements.csv`). The manifest holds per-file sha256 values and a `fingerprint`;
  `price_fingerprint_of` hashes the four `DATA_FILES` only.
- **The price fingerprint is the lab's comparability key.** Every recorded trial carries one
  (`trial_provenance`), and `lab/hardgate.py` refuses to compare trials across price fingerprints.
  The dev store's is `5451195f…`. **Changing `bars.csv` in `engine/.research` would orphan every
  recorded trial.** So §5.1 must be a **separate store directory**, not an edit of the dev store.
- `bars.csv` is **split-adjusted, not dividend-adjusted** (yfinance with dividends kept separate in
  `dividends.csv`). EODHD rows must be brought to the same convention: raw OHLC divided by the
  cumulative split factor after each date, volume multiplied by it, and dividends from
  `dividends/<SYM>.json` (EODHD `value` is split-adjusted already; check this against overlapping
  served symbols before trusting it).
- Windows: `load_store` refuses a store whose declared window is not the caller's. D9 forbids any
  row after `window.end` in a dev store. The test-window store (`engine/.research-test`) is built
  only at the first promotion (design §3) and must never be built early. The EODHD cache holds
  data through 2026, so **clip to 2015-10-16 when building any dev-window store.**
- Membership comes from `data/` CSVs via `research_membership`. The unserved members are already
  in the membership; they simply have no bars, so today the lab cannot hold them. Check how
  `lab run` and the allocators treat a member with no bars before assuming anything.
- Store movement between machines: the `sync-research-store` skill (Vercel Blob, keyed on the full
  fingerprint). A second store needs its own key prefix or a flag, so it never overwrites `LATEST.json`.
- Prior art for the shape of a new optional file plus a refresh command:
  `commands/dividend_announcements.py`, `research.refresh_announcements` and `_refresh_optional`.

## 5. Targets

### 5.1 A survivorship-check store, and the measurement it exists for

**The question it answers:** *how much does the missing-dead-companies gap flatter lab results?*
Every lab result so far was measured on a store that holds about 59% of index-member days, and
mostly the survivors. The buy signal in the explore skill's Promotion step 0b names
survivorship-free history as the thing worth buying, and we now own a large piece of it.

What to build (the design is the analyzer's call; these are the owner-level requirements):

1. **A separate dev-window store**, e.g. `engine/.research-sv`: today's dev store plus EODHD bars
   for the unserved members, in the same conventions, clipped to the dev window. It needs its own
   price fingerprint, and the existing `engine/.research` stays byte-identical. Prefer building it
   from the cache by script, with no network.
2. **Cleaning that is honest about bankruptcies:**
   - Split-adjust from `splits/`.
   - Detect reused-ticker splices and keep only the segment that overlaps the membership, or drop
     the symbol. Use the delisted symbol list's names, the series' end vs the membership end, and holes.
   - Drop or repair the absurd errors.
   - Keep genuine collapses. A company that went to near zero while a member is exactly what this
     store is for.
   - Every dropped symbol is listed with its reason in a report file inside the store, never silently.
3. **A coverage report**: year by year, member-days covered before and after, and the list of
   members still missing.
4. **The measurement.** A **report-only** command, in the spirit of `lab costs` and `lab regime`
   (no new trial row, no change to N, no status change, journaled with `lab note`/`lab insight`).
   It reruns a recorded method's variants on the survivorship-check store and prints them side by
   side with the dev-store result: funded CAGR vs SPY, max DD, PF, DSR inputs, 2009-2015 era,
   walk-forward folds. Run it on the roster and the near misses (M0007, M0021, M0022, M0029, M0032,
   M0020, M0019, M0011, M0033, M0063, M0070, M0069) and on this Sera batch's dividend-date methods.
   **M0069 (buying long-term losers) is the sharpest test**: its children said bankruptcies missing
   from the store flatter it most.
5. **A plain-words lab insight** (the owner is not a trader; no ids or code) saying how much
   survivorship flattered results, which methods it changed, and what 1996-97 and the 201
   still-missing members leave uncertain.

Open decisions for the analyzer (decide, don't ask; the owner's rule is no human in the loop):
- Whether the gate should ever *use* this store, or it stays a report-only cross-check. The
  default is report-only; any change to promotion rules is an argued commit in
  `lab/hardgate.py`, per the explore skill.
- Whether to spend bulk calls (before 2026-11-10) to fill the 201 empty members, e.g. via the
  delisted symbol list's alternate codes. Worth checking how many of the 201 appear under another code.

### 5.2 Market series strategies can read

- Add the market series as data available to allocators. That could be an optional store file
  (like `dividend_announcements.csv`) or a separate small file with its own loader; either way it
  must be read point in time (only values dated on or before the allocator's `data_date`), and it
  must not move the price fingerprint.
- Minimum set: VIX (1990+), VIX3M (2007-11+, with VXV 2006-07+ as its earlier name), IRX, FVX, TNX
  and TYX (to derive a term spread: TNX/10 − IRX; check the scaling of each index against known
  yields before trusting it).
- This unblocks parked ideas: **M0039** (VIX term structure, testable from about 2006-2007 only,
  so half the dev window) and the term-spread half of **M0038** (credit spreads remain unavailable).
  Move their status from `blocked-data` back to `idea` once the data loads, with a note saying how
  much of the dev window each covers.

## 6. Things that will bite

- **The Sera batch is live.** Children commit method files to `main`; Sera commits `lab/lab.sqlite`
  only through `lab stage`. **Never `git add lab/lab.sqlite` directly**, never pull into the main
  checkout while a lab run may be writing (insight 104), and work in a worktree. Worktrees have no
  `engine/.venv` (make one) and no `engine/.research` or `engine/.cache` (symlink or copy them from
  the main checkout, read-only).
- **Don't rebuild the dev store** (`research_store` without flags re-downloads from yfinance and
  changes every bar). Use copy-and-add, as the refresh functions do.
- `_read_manifest` allows only the `DATA_FILES` plus the `OPTIONAL_DATA_FILES`; a new optional file
  must be added to that tuple, and `tests/test_market_fundamentals.py::test_data_files_is_not_widened`
  pins the tuple on purpose.
- EODHD codes: the store's `BRK.B` is EODHD's `BRK-B.US` (`eodhd.ticker`). Bulk rows use current
  codes, which can differ from the store's historical ticker.
- Survivorship-check results must never be written as dev trials of the original methods. Mixing
  price fingerprints inside one method's trial set is what the hard gate exists to refuse.
- The owner commits and pushes to `main` once a change is verified (memory: auto commit & push);
  run the full engine test suite before each push.

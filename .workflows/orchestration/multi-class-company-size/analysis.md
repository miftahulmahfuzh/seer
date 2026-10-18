# Code Analysis: company size for firms with more than one share class

**Type:** Feature Update (data pipeline: `seer_engine.shares` and the research stores)
**Date:** 2026-10-18 17:14
**Session ID:** 20261018-171434-MCS7
**Plan:** `MULTI_CLASS_COMPANY_SIZE_PLAN.md` (3 phases)
**Worktree:** `/home/miftah/.worktrees/seer/multi-class-company-size`, branch `feature/multi-class-company-size` (base `origin/main` @ `1297681`)

---

## User Input

### Original User Request

```
/analyze docs/plans/HANDOVER_20261018-company-size-for-multi-class-firms.md
```

The handover is the specification. Its task section, verbatim:

> ## The task for this session: fix multi-class share counts (insight 399, unblocks M0225)
>
> **No purchase needed.** The source is free SEC EDGAR. The owner asked; the answer was no.
>
> Evidence from the stores (rows in `shares.csv`, same in `.research` and `.research-sv`):
>
> ```
> META 0   FB 0   V 6   MA 12   BRK.B 8   (a normal member has dozens)
> CMCSA 62  UPS 36  (present but the batch saw gaps around 2012)
> ```
>
> Prices are NOT the problem for the check store: CELG, ESRX, WBA, TWX have full bars in
> `engine/.research-sv` (EODHD, key valid to **2026-11-10** — finish before then in case any name
> needs a refetch). They are missing only from the dev store, which is by design.
>
> What is wrong, per the size-accessor notes in
> `.claude/skills/explore-and-experiment-new-method/SKILL.md` and insight 399:
> 1. Companies that tag `dei:EntityCommonStockSharesOutstanding` **per class** (class-axis
>    dimension) in XBRL go unknown — Alphabet from 2014, Meta, Visa, Mastercard, Ford, ~20 more in
>    2012. Sum the classes (or use the cover total), point in time, from the filing date.
> 2. **BRK.B 2010-11** counts class A only. Convert: 1 A = 1,500 B (1 A = 30 B before the 2010
>    50:1 B split). Value the company once.
> 3. Two listed classes (GOOG/GOOGL, FOX/FOXA, NWS/NWSA) each answer whole-company count × that
>    class's price. Better: each listed class valued at its own count × its own price, so a
>    method can weight the company once without a hand-kept list.
>
> Code lives in `engine/src/seer_engine/shares/` (`cover.py` already sums classes on pre-2010 cover
> pages; `checks.py` drops class fragments; `integrate.py` joins XBRL facts; `store.py`/`build.py`
> write `shares.csv`). `Market.shares_on` / `market_value` are in `backtest/market.py`.
>
> Rules that bind (CLAUDE.md):
> - `research.refresh_shares` must keep every other store file byte for byte: the **price
>   fingerprint must not move**, so recorded trials still compare. Only `shares.csv` changes, and
>   the store fingerprint will move from `b683da41` — say so in the commit.
> - No look-ahead: a figure is usable only from its filing date.
> - Refresh all three stores (`.research`, `.research-sv`, and the test-window store) and push via
>   the `sync-research-store` skill.
> - Tests must not reach production; DB tests need Postgres (`PG_TEST_URL`).
>
> **Done means:** META/V/MA/GOOGL/BRK.B have continuous point-in-time counts 2009-2015 with the
> right magnitude (spot-check Apple ≈ $560B and Meta ≈ $200B on 2014-06-30, Visa ≈ $130B,
> Berkshire ≈ $310B); `shares store-report` coverage of 2009-2015 member-days rises; then
> `lab unblock M0225` and record a `lab note` with the new coverage. Running M0225 itself is a
> lab run (pre-register first) and can go to the next Sera batch.

### User-Provided Context
The handover's "Other leftovers" (M0223/M0224/M0226 ideas, the size-weighted random twin wish,
idle tmux windows and old `agent-*` worktrees) are explicitly not this session's task.

### User-Provided Files
- `docs/plans/HANDOVER_20261018-company-size-for-multi-class-firms.md`

### Requirement IDs

| ID | What the user asked for |
|---|---|
| R1 | Companies that tag their share count per class in XBRL get a point-in-time count: classes summed (or the cover total), usable only from the filing date |
| R2 | Berkshire valued once: class A converted to B units (1 A = 1,500 B; 30 before the 2010-01-21 50:1 B split) |
| R3 | Each listed class valued at its own count × its own price (GOOG/GOOGL, FOX/FOXA, NWS/NWSA), so a method weights the company once without keeping its own list |
| R4 | All three stores refreshed (`.research`, `.research-sv`, `.research-test`) with the price fingerprint unchanged, pushed via `sync-research-store`, the fingerprint move stated in the commit |
| R5 | Done: META/V/MA/GOOGL/BRK.B continuous 2009-2015 at the right magnitude (spot checks), 2009-2015 coverage rises, `lab unblock M0225` plus a `lab note` with the new coverage |

---

## Detailed Requirements Understanding

**Problem statement.** The store's 2009+ share counts come only from SEC's `companyfacts` API,
ingested into each store's `fundamentals.csv` by `commands/fundamentals.py`. `companyfacts`
**omits every dimensional fact**. A filer that tags `dei:EntityCommonStockSharesOutstanding`
only with a `us-gaap:StatementClassOfStockAxis` member (one fact per class, no total) therefore
has no 2009+ share count in the store at all. Measured on the dev store:

- `META`: 181 share-ish facts in `fundamentals.csv`, all `WeightedAverage...`; **zero**
  `EntityCommonStockSharesOutstanding` / `CommonStockSharesOutstanding`. Its 10-Q of
  2014-07-24 (`0001326801-14-000032`, `fb-20140630.xml`) tags two facts, both class-axis:
  class A 2,015,048,077 and class B 585,003,514, instant 2014-07-22. Sum 2.600B × $67.29 ≈ $175B.
- `V` 1 fact (2010-02), `MA` 4 (2009-11..2010-11), `CMCSA` 2, `UPS` 2, `F` 8 (to 2011-05),
  `BRK.B` 6 (2010-03..2011-05, **class A only**, 1.10M → 0.94M; one of them is 0.0).
- `GOOGL`/`GOOG`: dei to 2010-02 only; both symbols read the same 0.674B whole-company count
  (from another tag) on 2014-06-30 and are both in the top 4. Both go unknown in 2015.
- BRK.B's pre-2010 **cover rows** are wrong too: `BRK.B,2010-02-16,15902240,...edgar-cover`
  is the B count (pre-split) summed 1:1 with A, so ×$3,000 ≈ $48B instead of ≈ $150B.

Gap census (`dev store`, 2009-01-02..2015-10-16, member-days with a close but no share count):
**138 symbols, 45,339 member-days**. Largest US-filer gaps: ACN 1079, MKC 1014, LEN/CMCSA/STZ
992, EXPE 982, CME 979, EL 978, WBD (Discovery) 975, MA 974, TAP/TSN/UPS 973, RL 968, V 964,
HRL 950, BRK.B 849, F 849, SPG 756, META 717, REGN 709, GHC 697, NWSA 580, MOS 579, KMI 437,
UAA 370, PRU 352, UHS 271, TRIP 251, LBTYK 207, BF.B 156, GOOGL/GOOG 115, LILA/LILAK 75.
`store-report` 2009-2015 coverage (member-days with a market value): 61.7, 65.1, 66.2, 64.7,
66.4, 67.7, 68.7 % against a close coverage of 65.4..76.2 %; share-count coverage drops from
96.1 % (2011) to 91.0 % (2012).

The rest of the 138 are **not** multi-class and are out of scope: foreign filers on 20-F/40-F
(BIDU, CHKP, VOD, INFY, TEVA, QGEN, LOGI, RYAAY, TCOM, VIP, NXPI) and successor tickers whose
date-scoped CIK history does not reach back (PSKY, VTRS, DXC). Short 2009-2010 gaps (LRCX,
STX, ILMN, HSIC, JBHT, IRM, VRTX) are pre-dei-tagging smaller filers; the new reader may close
some of them for free because it reads any member filing whose accession lacks a count.

**Success criteria.** Point-in-time per-class counts for every member filer whose companyfacts
lacks them, read from SEC's own XBRL instance documents; Berkshire converted; each listed class
its own line; store refreshes with the price fingerprint unchanged; spot checks at the right
magnitude; coverage up; M0225 unblocked with a note.

**Spot-check truths (computed here, the bands the plan uses):**
Apple 2014-06-30 ≈ $560B (store already reads $560.3B — must not move); Meta ≈ $175B
(A 2.015B + B 0.585B at $67.29; the handover's "≈ $200B" was a round figure); Visa ≈ $130B
as-converted; Berkshire ≈ $310-320B (A ≈ 0.86M × 1,500 + B ≈ 1.24B, at ≈ $126.5);
GOOGL + GOOG together ≈ $390B (A + B + C).

**Constraints.**
- No look-ahead: an instance's count is usable from its filing date only, counted at its
  context instant (the cover's "as of"), exactly like `history.Observation`.
- `research.refresh_shares` already carries every non-size file byte for byte; only
  `shares.csv` (and `splits.csv`, regenerated identically from cache) may change.
- The survivorship-check store is refreshed only through `survivorship_store --refresh-shares`
  (`integrate.write` refuses it).
- The test-window store has no `fundamentals.csv`; `shares store` takes `--xbrl` with the dev
  store's (it runs to 2026).
- Closed records are frozen: existing method files (M0047/M0201/M0221/M0222 dedupe GOOG/GOOGL by
  "identical share count") are not edited; recorded trials keep comparing on the price
  fingerprint.
- The worktree has no `engine/.venv` and no stores or caches. Stores, the EDGAR cache and the
  yfinance split cache live under `/home/miftah/seer/engine/` and are passed by absolute path.

**Assumptions.**
- SEC Archives serve each filing's `index.json` and its instance (`<prefix>-<date>.xml`, or
  `<primary>_htm.xml` for inline XBRL from 2019) — verified live for Meta 2014 and 2021.
  dei facts sit at the **end** of the instance (byte 1,173,860 of 1,178,188 for Meta 2014), so
  the whole instance is fetched; only the dei share facts and their contexts are cached.
- Unlisted classes convert 1:1 into the listed class unless the class table says otherwise
  (true for META B, MA B, CMCSA B, UPS A, F B, EL B, RL B, TSN B, …). Visa B/C, Berkshire A and
  Accenture X (votes only, no economic interest) are the known exceptions.

---

## Analysis Scope

### Explicitly Mentioned Files
- `docs/plans/HANDOVER_20261018-company-size-for-multi-class-firms.md`

### Discovered Related Files
- `engine/src/seer_engine/shares/__init__.py` — package docstring, module map
- `engine/src/seer_engine/shares/history.py` — `SharesHistory`, `xbrl_by_symbol`, `Observation`, csv I/O
- `engine/src/seer_engine/shares/store.py` — `change_points`, `_candidates`, `shares_lines`, `read_shares`, `usable_xbrl`, `history_for`, `SOURCES`
- `engine/src/seer_engine/shares/integrate.py` — `shares store` / `store-report` / `fetch-splits`
- `engine/src/seer_engine/shares/fetch.py` — `Archive`, `Pacer`, cache layout, `fetch_xbrl`
- `engine/src/seer_engine/shares/edgar_index.py` — `quarters`, `FilingRef`, `windows`, `select`, `FORMS`, horizon 1995Q4-2010Q4
- `engine/src/seer_engine/shares/build.py` — `shares build` / `report`, `read_store_facts`
- `engine/src/seer_engine/shares/cover.py` — pre-2010 cover parser (sums classes 1:1)
- `engine/src/seer_engine/shares/checks.py` — cover validation
- `engine/src/seer_engine/commands/shares.py` — subcommand wiring (`download`, then `build.add_arguments`, `integrate.add_arguments`)
- `engine/src/seer_engine/commands/fundamentals.py`, `engine/src/seer_engine/sec.py` — the `companyfacts` ingest (the reason dimensional facts are missing)
- `engine/src/seer_engine/backtest/market.py` — `ShareCount`, `ShareCounts`, `Market.shares_on`, `Market.market_value`
- `engine/src/seer_engine/research.py:1203` — `refresh_shares`, `_refresh_files`
- `engine/src/seer_engine/commands/survivorship_store.py:437` — `refresh_shares` for the check store
- `engine/src/seer_engine/lab/methods/m0221_cap_weighted_top_n.py` — the yardstick; dedupes classes by identical share count
- `engine/data/SOURCES.md`, `engine/data/shares_outstanding_pre2009.csv`, `engine/data/ticker_cik*.csv`
- `engine/tests/test_shares.py`, `engine/tests/test_shares_store.py`, `engine/tests/test_backtest_market.py`, `engine/tests/test_survivorship_store.py`
- `.claude/skills/explore-and-experiment-new-method/SKILL.md:78-84` — the size-accessor caveats children read

---

## Current Dataflow

### Entry Point: `python -m seer_engine shares store --store <abs> --basis <day> [--xbrl <fundamentals.csv>]`

**Location:** `engine/src/seer_engine/shares/integrate.py:125` (`write`)
**Trigger:** CLI, by hand
**Validation:** refuses a symlink, a survivorship-check store (`declared_purpose`), `--basis` before the window end, a store with no `fundamentals.csv` and no `--xbrl`
**Next Step:** `build.read_store_facts(xbrl)` → `store.usable_xbrl(facts)`

### Processing Chain

1. **`store.usable_xbrl(facts)`** — `store.py:183`. Drops foreign-form facts and unit errors (a value ≥ `SCALE_LIMIT`× the symbol's median of facts filed within `SCALE_WINDOW_DAYS`). Keeps only `history.XBRL_TAGS` = (`EntityCommonStockSharesOutstanding`, `CommonStockSharesOutstanding`). **Input here never contains class-axis facts** — `companyfacts` dropped them upstream.
2. **`store.history_for(facts)`** — `store.py:382` → `history.SharesHistory(load_rows(pre2009 csv), cik.load_index_with_history(), facts)`.
3. **`history.xbrl_by_symbol(facts)`** — `history.py:255`. One `_Xbrl(filed, accession, period_end, shares)` per (symbol, accession): preferred tag, latest period, *distinct values summed* (axis-less class facts).
4. **`SharesHistory.shares_on(symbol, on)`** — `history.py:305`. Resolves `symbol` → CIK through the date-scoped ticker map; latest cover row (by CIK) vs latest XBRL fact (by **symbol**); later filing wins, XBRL wins a same-day tie; `None` past `max_age_days` (400).
5. **`store.change_points(hist, members, FIRST_FILED, window.end)`** — `store.py:91`. Evaluates `shares_on` on every candidate day (`_candidates`, `store.py:66`: ticker-map boundaries, every filing date, every age-out day) and keeps change points.
6. **`store.shares_lines(rows)`** — `store.py:122`. `symbol,from,shares,counted,filed,source,accession`.
7. Splits: `splits.read_yfinance` per served symbol, `store.applied_by_vendor`, `store.split_lines`.
8. **`research.refresh_shares(store, shares_lines, split_lines, window=...)`** — `research.py:1203`. Parses both back with the strict readers, then `_refresh_files` verifies the store, carries every other file byte for byte and swaps the directory; prints old/new fingerprint and price fingerprint (exit 1 if the price fingerprint moved).

### Read side

- `research.load_store` → `store.load_counts(shares.csv, splits.csv)` → `ShareCounts(rows, splits)` (`market.py:301`).
- `store.read_shares` (`store.py:310`) refuses a `source` not in `SOURCES = (SOURCE_COVER, SOURCE_XBRL)`.
- `ShareCounts._units_days` (`market.py:369`) decides per count whether the figure is in the count day's or the filing day's share units (split between them).
- `Market.shares_on(symbol, d)` (`market.py:630`) and `Market.market_value(symbol, d)` (`market.py:635`) = count × split factor × last close (≤ 7 days old) × `raw_factor`.

### Survivorship-check store

`survivorship_store --refresh-shares` (`survivorship_store.py:437`) copies the **source (dev) store's** `shares.csv` lines verbatim and merges split lists; so the check store follows the dev store automatically once the dev store is refreshed.

### Data Persistence
- Research stores (gitignored): `/home/miftah/seer/engine/.research` (dev, fingerprint `b683da41…`), `.research-sv` (survivorship-check, `7017e311…`), `.research-test` (test window 2015-10-19..2026-10-06, `b9269bfa…`, **no** `fundamentals.csv`).
- EDGAR cache (gitignored): `/home/miftah/seer/engine/.cache/edgar/{index,filings,xbrl,prices}`; indexes cached for 1995Q4..2010Q4 only.
- Vendored, committed: `engine/data/shares_outstanding_pre2009.csv` (+ `_excluded.csv`), documented in `engine/data/SOURCES.md:410`.
- Blob mirror of the stores via the `sync-research-store` skill.

### Exit Points
- `shares store` prints the counts and both fingerprints; exit 0 / 1 (price fingerprint moved) / 2 (refused).
- `shares store-report` prints per-year coverage, top-N by market value on chosen dates, and an EODHD raw-close check.

---

## Key Data Structures

### `history.ShareRow` — `history.py:83`
`cik, filed, accession, symbol, as_of, form, shares, classes ((label, n), ...), flags, note` — one cover row; `classes` empty for one class, else ≥ 2 entries summing to `shares`.

### `history.Observation` — `history.py:99`
`symbol, on, shares, as_of, filed, source, accession, cik` — the answer of `shares_on`.

### `history._Xbrl` — `history.py:247`
`filed, accession, period_end, shares` — one companyfacts reading per (symbol, accession).

### `store.ShareLine` — `store.py:51`
`symbol, start, obs` — one change point.

### `market.ShareCount` — `market.py:285`
`shares, counted, filed, source` — `source` documented as `"edgar-cover"` or `"xbrl"`.

### `market.ShareCounts` — `market.py:301`
Change points per symbol plus `(dated splits, after-window product)` per symbol.

### `edgar_index.FilingRef` — `edgar_index.py`
`cik, filed, form, accession, company, path`.

---

## Dependencies

- **SEC EDGAR Archives** (`www.sec.gov/Archives/edgar/data/<cik>/<acc-no-dashes>/index.json` and the instance file), `full-index/<Y>/QTR<n>/master.gz` for 2011Q1..2026Q3. Needs `SEC_CONTACT_EMAIL` (set in `/home/miftah/seer/.env.local`; the worktree's `config.env_file()` resolves `.env.local` at its own repo root — pass `SEER_ENV_FILE=/home/miftah/seer/.env.local`). Under 10 req/s (`fetch.Pacer`).
- yfinance split cache `/home/miftah/seer/engine/.cache/yfinance/splits` (already full; `shares store` needs it, `--splits-cache`).
- EODHD key valid to 2026-11-10 (only for `store-report`'s raw-close check; `--no-check` skips it).
- The lab CLI (`lab unblock`, `lab note`, `lab stage`) and `lab/lab.sqlite`, `web/data/lab.json`.

---

## Reference List

| Symbol / key | File:line | Kind | Package |
|---|---|---|---|
| `XBRL_TAGS` | `shares/history.py:74` | def | shares |
| `SOURCE_COVER`, `SOURCE_XBRL` | `shares/history.py:76-77` | def | shares |
| `xbrl_by_symbol` | `shares/history.py:255` | def | shares |
| `SharesHistory.__init__` / `latest` / `_latest_xbrl` / `shares_on` | `shares/history.py:279-326` | def | shares |
| `history.load` | `shares/history.py:330` | def | shares |
| `SOURCES` | `shares/store.py:45` | def | shares |
| `_candidates` (reads `hist._rows`, `hist._xbrl`) | `shares/store.py:66` | def | shares |
| `change_points` | `shares/store.py:91` | def | shares |
| `usable_xbrl` | `shares/store.py:183` | def | shares |
| `read_shares` (source check) | `shares/store.py:310` | def | shares |
| `history_for` | `shares/store.py:382` | def · call | shares |
| `integrate.write` | `shares/integrate.py:125` | call | shares |
| `integrate.coverage` / `top` / `report` | `shares/integrate.py:219-293` | call | shares |
| `fetch.Archive`, `fetch._atomic_write`, `CACHE_DIR` | `shares/fetch.py` | def | shares |
| `edgar_index.quarters`, `HORIZON_END`, `FORMS`, `windows`, `select` | `shares/edgar_index.py` | def | shares |
| `commands/shares.py` `add_arguments` / `run` | `commands/shares.py:56-83` | config | commands |
| `ShareCount.source` doc | `backtest/market.py:285` | doc | backtest |
| `ShareCounts` doc ("XBRL wins a same-day tie") | `backtest/market.py:301` | doc | backtest |
| `research.refresh_shares` | `research.py:1203` | call | engine |
| `survivorship_store.refresh_shares` | `commands/survivorship_store.py:437` | call | commands |
| M0221 class rule "identical-share-count" | `lab/methods/m0221_cap_weighted_top_n.py:20-22,73,114` | frozen | lab |
| size-accessor caveats | `.claude/skills/explore-and-experiment-new-method/SKILL.md:78-84` | doc | skills |
| `shares_outstanding_pre2009.csv` section | `engine/data/SOURCES.md:410` | doc | data |
| tests | `engine/tests/test_shares.py`, `test_shares_store.py`, `test_backtest_market.py` | test | tests |

---

## Impact Points (files that WILL need changes)

1. `engine/src/seer_engine/shares/instance.py` (new) — pure reader of an XBRL instance's dei share facts per class. Phase 1.
2. `engine/src/seer_engine/shares/fetch.py` — instance download into the cache. Phase 1.
3. `engine/src/seer_engine/shares/edgar_index.py` — quarters past 2010 for the instance selection. Phase 1.
4. `engine/src/seer_engine/shares/classes.py` (new) — selection of filings to read, the vendored per-class csv's I/O, `shares download-classes` / `build-classes`. Phase 1.
5. `engine/data/shares_xbrl_classes.csv` (new, generated and committed) + `engine/data/SOURCES.md`. Phases 1 (format, doc) and 3 (the real file).
6. `engine/data/share_classes.csv` (new, hand-kept class table: sibling listed classes, conversion ratios, excluded classes) + its loader. Phase 2.
7. `engine/src/seer_engine/shares/history.py` — third source, per-class attribution, conversion of cover rows. Phase 2.
8. `engine/src/seer_engine/shares/store.py` — `SOURCES`, `_candidates`, `history_for`. Phase 2.
9. `engine/src/seer_engine/shares/integrate.py` — `store` loads the per-class csv; `store-report` spot checks. Phase 2.
10. `engine/src/seer_engine/backtest/market.py` — `ShareCount` / `ShareCounts` docstrings for the new source. Phase 2.
11. `engine/src/seer_engine/commands/shares.py` — wire new actions; docstring. Phase 1.
12. Tests: `engine/tests/test_shares_instance.py` (new), `test_shares_classes.py` (new), `test_shares.py`, `test_shares_store.py`. Phases 1-2.
13. The three stores, the Blob mirror, `lab/lab.sqlite`, `web/data/lab.json`, the skill's size-accessor notes, `shares` package docs, handover close-out. Phase 3.

**This document describes. The plan files prescribe.**

# Code Analysis: EODHD month — survivorship-check store and market series

**Type:** Feature Implementation
**Date:** 2026-10-10 18:15
**Session ID:** 20261010-181548-E7HD
**Plan:** `EODHD_SURVIVORSHIP_MARKET_PLAN.md` (5 phases)
**Worktree:** `/home/miftah/.worktrees/seer/eodhd-survivorship-market`, branch `feature/eodhd-survivorship-market` (base `origin/main` @ `5e5ec5c`)

---

## User Input

### Original User Request

```
/analyze docs/plans/HANDOVER_20261010-eodhd.md
```

The handover is the specification. Its owner-level requirements are quoted verbatim in the plan
index's **Why** section; the file itself is `docs/plans/HANDOVER_20261010-eodhd.md` on this branch.

### User-Provided Context

- The owner paid for one month of EODHD "EOD Historical, All-World" (personal licence), key valid
  until 2026-11-10, `EODHD_API_TOKEN` in the repo-root `.env.local`, 100,000 calls/day.
- Owner's instruction: *exploit this paid data as much as possible, and get a definite answer on
  whether it can improve our methods.* Passing the gate is not required. Clarity is.
- A Sera batch is live and writing `lab/lab.sqlite` in the main checkout.

### User-Provided Files
- `docs/plans/HANDOVER_20261010-eodhd.md`

### Requirement IDs

| ID | What the user asked for |
|---|---|
| R1 | A separate dev-window survivorship-check store (`engine/.research-sv`): today's dev store plus EODHD bars for the unserved members, same conventions, clipped to the dev window, its own price fingerprint, the dev store byte-identical, built from the cache with no network |
| R2 | Cleaning honest about bankruptcies: split-adjust from `splits/`, detect reused-ticker splices, drop or repair absurd errors, keep genuine collapses, every dropped symbol listed with its reason in a report file inside the store |
| R3 | A coverage report: year by year member-days covered before and after, and the list of members still missing |
| R4 | A report-only measurement command that reruns a recorded method's variants on the survivorship-check store beside the dev-store result (funded CAGR vs SPY, max DD, PF, DSR inputs, 2009-2015 era, walk-forward folds); no trial, no N change, no status change; journaled |
| R5 | Run it on the roster and near misses (M0007, M0021, M0022, M0029, M0032, M0020, M0019, M0011, M0033, M0063, M0070, M0069) and the Sera batch's dividend-date methods; M0069 is the sharpest test |
| R6 | A plain-words lab insight: how much survivorship flattered results, which methods it changed, what 1996-97 and the still-missing members leave uncertain |
| R7 | Decide (not ask): whether the gate ever uses this store, and whether to spend calls to fill the 201 empty members via alternate codes |
| R8 | Market series (VIX, VIX3M with VXV before it, IRX, FVX, TNX, TYX at minimum) as data allocators can read point in time, without moving the price fingerprint, scaling checked against known yields |
| R9 | Move M0039 and M0038 from `blocked-data` back to `idea` once the data loads, with a note on how much of the dev window each covers |

---

## Detailed Requirements Understanding

**Problem/Requirement Statement.** Every lab result was measured on `engine/.research`, which holds
bars for 539 of 1061 requested symbols — about 59% of S&P 500 ∪ Nasdaq-100 member-days 1996-2015,
mostly survivors. The paid month downloaded raw EODHD daily history, splits and dividends for all
522 unserved members into `engine/.cache/eodhd/`. The work turns that cache into (a) a second,
clearly marked dev-window store that can never be confused with the dev store or recorded as dev
trials, (b) a report-only command that measures how each recorded method's numbers move on it, and
(c) an optional market-series store file that allocators can read point in time.

**Success Criteria.**
- `engine/.research` is byte-identical before and after (manifest fingerprint `fd2bc190…`, price
  fingerprint `5451195f…`) except for the deliberate optional `market_series.csv` added by R8.
- `engine/.research-sv` loads with `research.load_store`, has a different price fingerprint, is
  marked as a survivorship-check store, and every trial-writing path refuses it.
- A cleaning report and coverage report sit inside the SV store; every symbol not added has a reason.
- `lab survivorship M0069 …` prints dev vs SV side by side and journals plain-words observations;
  `store.dev_trial_count` and `store.test_looks` unchanged.
- A plain-words insight records the answer; M0039 and M0038 read `idea` with a coverage note.

**Key Considerations.**
- Bars in the store are split-adjusted, not dividend-adjusted (yfinance `auto_adjust=False`).
  EODHD `open/high/low/close` are raw; `adjusted_close` is split **and** dividend adjusted.
- Real collapses must stay: a jump filter alone cannot tell AIG-style falls from data errors.
- The licence is personal: raw vendor rows never go into git or `web/data/`.
- Worktrees lack `engine/.venv`, `engine/.research`, `engine/.cache`, `.env.local`.
- `_swap_in` uses `os.replace` on the store path; a symlinked store path would move the link, not
  the store.

---

## Analysis Scope

### Explicitly Mentioned Files
- `docs/plans/HANDOVER_20261010-eodhd.md`

### Discovered Related Files
- `engine/src/seer_engine/research.py` — store build/refresh/load (1469 lines)
- `engine/src/seer_engine/backtest/market.py` — `Market`, `DividendCalendar`, `Membership`
- `engine/src/seer_engine/backtest/book_runner.py` — book engine, `_gone` force-close
- `engine/src/seer_engine/backtest/io.py` — `histories_from_frame`, `merge_intervals`
- `engine/src/seer_engine/strategies/allocator.py` — `Allocator`, `MarketAware`, `prepare_for`
- `engine/src/seer_engine/lab/runner.py` — `run_method`, `run_test`, `preflight_data`, `market_fields`
- `engine/src/seer_engine/lab/real_costs.py` — the report-only rerun precedent (`lab costs`)
- `engine/src/seer_engine/lab/remeasure.py` — rerun with reproducibility checks
- `engine/src/seer_engine/lab/walkforward.py`, `engine/src/seer_engine/lab/hardgate.py`
- `engine/src/seer_engine/lab/store.py` — `INSIGHT_KINDS`, status transitions, `DB_PATH`
- `engine/src/seer_engine/commands/lab.py` — subcommands `costs`, `regime`, `walkforward`, `block`
- `engine/src/seer_engine/commands/dividend_announcements.py`, `engine/src/seer_engine/dividend_announcements.py`
- `engine/src/seer_engine/eodhd.py` — EODHD client (dividends only)
- `engine/src/seer_engine/commands/research_store.py`, `engine/src/seer_engine/cli.py`
- `engine/data/*.csv` — membership history, `ticker_cik.csv` (company names), `ticker_aliases.csv`
- `engine/scripts/survivorship_coverage.py` — existing era-coverage script
- `engine/tests/test_market_fundamentals.py:629` — pins `OPTIONAL_DATA_FILES`
- `.claude/skills/sync-research-store/sync_store.py` — Blob sync, `PREFIX = "seer/research-store"`
- `.claude/skills/explore-and-experiment-new-method/SKILL.md` — Promotion step 0b

---

## Current Dataflow

### Entry Point: building the dev store

**Location:** `commands/research_store.py:run` → `research.build_store` (`research.py:541`)
**Trigger:** `python -m seer_engine research_store` (CLI auto-discovers `commands/*` in `cli.py`).
**Transform:** yfinance per batch → `bars.csv` (`symbol,date,open,high,low,close,volume`, 4 dp,
ORDER BY symbol,date), `dividends.csv` (`symbol,ex_date,amount`, ≤6 dp via `_amount_text`),
`fx.csv`, `unserved.csv` (`symbol,reason`; reason `yfinance returned no bars for 1993-01-29..2015-10-16`).
**Exit:** `_seal` writes `manifest.json` (keys `MANIFEST_KEYS` = `dev_end, store_start, files,
fingerprint, bar_rows, dividend_rows, fx_rows, symbols_requested, symbols_served`, optionally the
three window keys), `_swap_in` replaces the directory atomically (`.tmp`/`.old`, `os.replace`).

### Refresh path for optional files

`research._refresh_optional` (`research.py:976`): verifies the store via `load_store`, copies every
other file byte for byte (sha-checked), writes one `OPTIONAL_DATA_FILES` member, re-seals with the
same counts and window, swaps in. Used by `refresh_fundamentals` and `refresh_announcements`.
`OPTIONAL_DATA_FILES = (fundamentals.csv, dividend_announcements.csv)` and the tuple is pinned by
`tests/test_market_fundamentals.py::test_data_files_is_not_widened`.

### Loading

`research.load_store(store_dir, data_dir=None, window=DEV_WINDOW)` (`research.py:1033`):
1. `_read_manifest` — key set must equal `MANIFEST_KEYS` or `MANIFEST_KEYS | OPTIONAL_MANIFEST_KEYS`
   exactly; `dev_end`/`store_start` pinned; declared window must equal the caller's; `files` must
   contain the 4 `DATA_FILES` and only `OPTIONAL_DATA_FILES` beyond them.
2. sha256 of every listed file; `fingerprint_of(files)`.
3. `_read_bars` (rejects rows after `window.end` or before `STORE_START`), `_read_dividends`,
   `_read_fx`, `_read_unserved`, optional fundamentals and announcements.
4. Count check against the manifest.
5. `Market(history=histories_from_frame(frame), membership=research_membership(data_dir, window),
   fx, fundamentals, dividends=DividendCalendar.from_map(…, declared=…))`.
6. Returns `ResearchData(market, dividends, spy_dividends, fingerprint, manifest, unserved, window,
   price_fingerprint=price_fingerprint_of(files))`.

Files present in the store directory but absent from the manifest are ignored by the loader.

**Membership is independent of the store.** `research_membership` reads `engine/data/` CSVs. The 522
unserved members are already members on their dates; they have no `History`, so `bars_on` returns
nothing for them and allocators that rank only symbols with history skip them.

### The book engine and a symbol whose bars stop

`book_runner.run_book` (`book_runner.py:247`): each session, on rank sessions, `members_on(data_date)`
is passed to `allocator.targets[_prepared]`; after `step_book`, any held symbol with
`market.last_bar_date(symbol) < session` is force-closed by `close_book_unpriced` (`_gone`,
`book_runner.py:231`). A delisted company's position is therefore closed after its last bar, at its
last mark. A held symbol with a gap inside its history simply has no bar that session.

### Lab paths that write trials

- `runner.run_method` (`runner.py:407`) — `lab run`; records `trials`, `trial_moments`,
  `trial_funding`, `trial_provenance` (with `data.price_fingerprint`). Store loaded by
  `commands/lab.py:_run` from `--store` (default `$SEER_RESEARCH_STORE` or `research.STORE_DIR`).
- `runner.run_test` (`runner.py:780`) — `lab test` on the test store.
- `remeasure.remeasure` — writes `trial_moments` only, after reproducing recorded Sharpe/DSR.

Nothing today identifies a store as "not the dev store" other than its declared window; a second
dev-window store would load anywhere `DEV_WINDOW` is expected.

### Report-only precedent: `lab costs`

`commands/lab.py:_costs` → `real_costs.resolve_method` (method file via `lab.method.discover`) →
`pick_candidate` (best recorded dev trial by MAR) → `runner.recorded_capital` /
`recorded_contributions` (the recorded trial's capital and funding) → `research.load_store` →
`dev.run_registry(market, dividends, spy_dividends, candidates, on_result=…, contributions=…,
initial_idr=…)` → `format_report` → `journal` (one `observation` via `store.add_insight`). Prints N
and test looks before and after.

### Walk-forward and the 2009-2015 era

`commands/lab.py:_walkforward`: recorded monthly curves (`trials.curve_json`), benchmark
`REF-SPY-HOLD` curve, `wf.folds(bench dates)`, `hardgate.trial_deposits(conn, row, curve)` to
de-fund funded curves (needs the recorded trial row), `wf.evaluate(curves, bench, folds, deps)` →
`wf.Record` (`won`, `scored`, `majority`, `stable`). `HIGH_COVERAGE = (2009-01-01, 2015-10-16)`
and `wf.measure(curve, start, end, deposits)` gives the era slice (cagr, max fall, mar).
`runner` builds curves with `commands.backtest_dev.month_end_curve(result.snapshots)`;
`daily_moments(row.stats.daily_returns)` gives `(sr_daily, skew, kurt)`;
`dev.deflated_sharpe(sr, n, var_trials, T, skew, kurt)`.

### Market-aware allocators

`strategies.allocator.MarketAware` (`allocator.py:99`) is a runtime-checkable protocol with
`prepare_market(market)`; `prepare_for` dispatches to it. `runner.market_fields(allocator)` reads a
`market_fields` class attribute (`("dividends",)` on ten methods M0051…M0085), defaulting to
`("fundamentals",)`. `runner.preflight_data` refuses a calendar method when
`len(data.market.dividends) == 0`, and gates fundamentals methods on panel coverage.

### EODHD

`eodhd.Client.dividends(symbol)` is the only endpoint; `ticker("BRK.B") -> "BRK-B.US"`; token from
`config.get("EODHD_API_TOKEN")`, which reads `config.env_file()` = `$SEER_ENV_FILE` or
`<REPO_ROOT>/.env.local` (a worktree's REPO_ROOT has none).
`commands/dividend_announcements.py` fetches `/div` into `engine/.cache/eodhd/dividends/<SYM>.json`
(`{"symbol","ticker","fetched","rows"}`) and `--refresh` matches onto `dividends.csv` through
`dividend_announcements.match(store_dividends, vendor, skip=RESEARCH_ETFS, years=…)`.

### Lab status transitions

`store.py:95-99` allows `blocked-data → idea` ("the missing data arrived"); `commands/lab.py` has
`block` (sets `blocked-data` + `blocked_on`) and no command for the reverse.

---

## Measured facts (this session)

| Fact | Value |
|---|---|
| Dev store manifest | 2,490,793 bar rows, 28,206 dividends, 4,300 fx rows, 1061 requested, 539 served, fingerprint `fd2bc190…`, six files incl. fundamentals and announcements |
| Cache | `eod/` 522 files, `splits/` 522, `dividends/` 976, `market/` 15 series, `symbols-US-delisted.json` 60,418 entries (`Code, Name, Country, Exchange, Currency, Type, Isin`) |
| `eod/<SYM>.json` | list of `{date, open, high, low, close, adjusted_close, volume}`, file named by the **store** symbol (e.g. `AAMRQ`, `ENRNQ`) |
| `splits/<SYM>.json` | `[{"date": "1996-06-04", "split": "2.000000/1.000000"}]` or `null` |
| TNX / FVX / TYX | yield × 10 (TNX 65.48 on 2000-01-03 ≈ 6.5% 10-year; 19.6 on 2012-01-03 ≈ 1.96%) |
| IRX | yield in percent (5.27 on 2000-01-03; 0.005 on 2012-01-02) |
| VIX3M vs VXV | identical on overlap samples (23.6 on 2008-01-02, 26.05 on 2012-01-03); VXV 2006-07-17..2020-07-09, VIX3M 2007-11-13.. |
| Non-session dates in market files | present (IRX 1990-01-01, TYX 2015-01-01) |
| Bar format | `AAPL,2012-01-04,14.6429,14.8100,14.6171,14.7657,260022000` — fixed 4 dp, split-adjusted volume |
| `ticker_cik.csv` | `symbol,cik,start_date,end_date,company_name,source,note` — company names per store symbol |
| Statuses | M0038, M0039 `blocked-data`; dividend-date methods M0076-M0079, M0081, M0082, M0085 `rejected`, M0083 `dev-eligible`, M0086 pre-registered |
| Live sessions | tmux `sera-20261010-1651`, `sera-20261010-1742`, `explore-M0082`, `explore-M0086` |

---

## Key Data Structures

### `ResearchData` — `research.py:192`
`market, dividends, spy_dividends, fingerprint, manifest, unserved=(), window=DEV_WINDOW, price_fingerprint=None`.

### `Market` — `backtest/market.py:249`
`history, membership, fx, fundamentals=EMPTY_FUNDAMENTALS, dividends=EMPTY_DIVIDENDS`; frozen;
`with_fundamentals`, `with_dividends`, `bar`, `bars_on`, `last_bar_date`, `usd_idr_on`, `spy`.

### `DividendCalendar` — `backtest/market.py:56`
Point-in-time reads `known_on(symbol, data_date)` and `announced_on(symbol, data_date)` with
`bisect_right`; `EMPTY_DIVIDENDS` shared instance. The template for a point-in-time series type.

### `real_costs.Comparison` / `Side` — `lab/real_costs.py`
The shape of a two-column report row (total return, CAGR, SPY TR, max DD, PF, trades, Sharpe, MAR…).

---

## Dependencies

- **Environment:** `EODHD_API_TOKEN` (repo-root `.env.local`; worktrees need `SEER_ENV_FILE`
  pointing at `/home/miftah/seer/.env.local`), `SEER_LAB_DB` (worktree sessions share the main
  checkout's lab DB this way; `store.py:74-76`), `SEER_RESEARCH_STORE`.
- **External:** EODHD REST (`/api/eod/<CODE>`, `/api/splits/<CODE>`, `/api/div/<CODE>`), Vercel
  Blob (sync skill).
- **Data on disk, main checkout only:** `engine/.research`, `engine/.cache/eodhd`, `engine/.venv`.

---

## Reference List

| Symbol / key | File:line | Kind | Package |
|---|---|---|---|
| `DATA_FILES`, `OPTIONAL_DATA_FILES` | `research.py:101-103` | def | research |
| `MANIFEST_KEYS`, `OPTIONAL_MANIFEST_KEYS` | `research.py:141,153` | def | research |
| `_read_manifest` | `research.py:1208` | def | research |
| `_seal` | `research.py:793` | def | research |
| `_refresh_optional` | `research.py:976` | def | research |
| `load_store` | `research.py:1033` | def | research |
| `ResearchData` | `research.py:192` | def | research |
| `test_data_files_is_not_widened` | `tests/test_market_fundamentals.py:629` | test | tests |
| `Market` | `backtest/market.py:249` | def | backtest |
| `market_fields`, `preflight_data` | `lab/runner.py:190,215` | def | lab |
| `run_method`, `run_test` | `lab/runner.py:407,780` | def | lab |
| `remeasure` | `lab/remeasure.py` | def | lab |
| `_costs`, `_regime`, `_walkforward`, `_block`, `_HANDLERS` | `commands/lab.py` | def | commands |
| `HIGH_COVERAGE` | `commands/lab.py` (above `_walkforward`) | def | commands |
| `trial_deposits` | `lab/hardgate.py:513` | def | lab |
| `eodhd.Client`, `ticker`, `parse_dividends` | `eodhd.py` | def | eodhd |
| `da.match` | `dividend_announcements.py` | def | — |
| store transitions `blocked-data → idea` | `lab/store.py:95-99` | def | lab |
| Promotion step 0b | `.claude/skills/explore-and-experiment-new-method/SKILL.md:225-280` | doc | skills |
| `PREFIX`, `store_dir` | `.claude/skills/sync-research-store/sync_store.py:35,66` | def | skills |

---

## Impact Points (files that WILL need changes)

1. `engine/src/seer_engine/survivorship.py` (new) — pure cleaning and merge library. Phase 1.
2. `engine/src/seer_engine/commands/survivorship_store.py` (new) — build + coverage report. Phases 1, 2.
3. `engine/src/seer_engine/research.py` — `purpose` manifest key, `SV_STORE_DIR` (phase 1);
   `market_series.csv` optional file, reader, refresh (phase 3).
4. `engine/src/seer_engine/lab/runner.py`, `lab/remeasure.py` — refuse a survivorship-check store (phase 1);
   `preflight_data` refuses a series method on a store with no series (phase 3).
5. `engine/src/seer_engine/eodhd.py` — generic `eod` / `splits` endpoints (phase 2).
6. `engine/src/seer_engine/backtest/market.py` — `MarketSeries` + `Market.series` (phase 3).
7. `engine/src/seer_engine/commands/market_series.py` (new) (phase 3).
8. `engine/src/seer_engine/commands/lab.py` — `lab unblock` (phase 3); `lab survivorship` (phase 4).
9. `engine/src/seer_engine/lab/survivorship_check.py` (new) (phase 4).
10. `engine/tests/test_market_fundamentals.py` — the pinned tuple, widened deliberately (phase 3).
11. `.claude/skills/explore-and-experiment-new-method/SKILL.md`, `.claude/skills/sync-research-store/` — docs/flag (phases 1, 5).
12. `docs/lab/survivorship/` (new, derived results only) (phase 5).

**This document describes. The plan files prescribe.**

# Code Analysis: Fundamental panel coverage

**Type:** Feature Update (data re-vendoring + a new engine gate)
**Date:** 2026-10-05T13:36:48+07:00
**Session ID:** 20261005-133648-2XUM
**Plan:** `FUNDAMENTAL_PANEL_COVERAGE_PLAN.md` (5 phases)
**Worktree:** `/home/miftah/.worktrees/seer/fundamental-panel-coverage`, branch `feature/fundamental-panel-coverage` (base `HEAD` @ `2dad9ff`)

Base is `HEAD`, not `origin/main`: at the moment `/analyze` started, `main` carried an
uncommitted fix to `paper/store.py` (decision doc §6.1). That fix was committed as `2dad9ff`
while the exploration ran, so the tree this analysis describes **is** `2dad9ff`, and the plans
quote it.

---

## User Input

### Original User Request

```
/analyze docs/plans/2026-10-05-fundamental-panel-coverage.md
```

The target file is the specification. It is reproduced here only by reference — it is committed
at `a0e4a20` and unchanged — but its §8 **Decision** and its three success criteria are the
contract, and its §5 and §4 are the boundary the plan must not cross:

> **Do Fix A and Fix B, and build the coverage gate.** All three are free, all three are local,
> and Fix A corrects a factual error in shipped data (525 rows claiming a membership date that
> is not theirs).
>
> The success criterion is **not** "a fundamentals method beats SPY". It is:
>
> 1. `ticker_cik.csv` carries each symbol's real first-membership interval, with every invariant
>    in §2 still enforced by tests.
> 2. The panel's coverage is measured and reported across the whole dev window, by a check that
>    lives in the engine rather than in a runbook snippet.
> 3. That number is honest — if it lands near 30%, the plan says so and does not claim the test
>    problem is solved.
>
> Explicitly **not** in this plan:
> - The test-window decision (§5). It is one irreversible spend and deserves its own doc.
> - Pre-2009 fundamentals from any paid vendor (§4).
> - Gap A / delisted price bars / the $199 Massive gate. Unrelated.
> - Re-running M0005. Its id is spent; a re-test is a new variation method, and it should not be
>   minted until the coverage gate reports a number worth testing.

### User-Provided Context

- `docs/plans/2026-10-05-fundamental-panel-coverage.md` — the decision doc, in full.
- Its predecessor `docs/plans/2026-10-05-delisted-and-fundamentals.md` §3 (Gap B), landed as
  `EDGAR_FUNDAMENTALS_PLAN.md` / merge `cf08103`.

### User-Provided Files

None marked with `@`. The decision doc names the files, and Step 2 followed them.

### Requirement IDs

| ID | What the user asked for |
|---|---|
| R1 | **Fix A** (§2): re-vendor `engine/data/ticker_cik.csv` so each symbol carries its *real* first-membership interval instead of the 2015-01-02 scope clamp, with every invariant in §2 still enforced by tests — recycled tickers still truncated at the handover, `K`→Kellanova, the single `NONE` row still alone, zero `fuzzy` rows, the 11 `SCREEN_EXEMPT` symbols still exempt, and no end date ever extended forward. |
| R2 | **Fix B** (§3): re-ingest EDGAR at `--since-filed 2009-01-01`, and **measure** how much 2009–2012 XBRL actually exists before anything depends on it. |
| R3 | **The coverage gate** (§6.2): the corrected coverage check moves out of the runbook snippet and into the engine, as a `lab run` preflight refusal and/or a subcommand, so no future method can be run against a panel that cannot rank. |
| R4 | **Honest reporting** (§8.3): the coverage number that results is measured across the whole dev window and reported as it is — if it lands near 30%, say so, and do not claim the test problem is solved. |
| R5 | **§6.1**: `paper/store.py:load_market_window` must not silently build a `Market` with `EMPTY_PANEL`. |

§6.3 (`http.get_json` takes no `headers`) is **not** minted as a requirement. The decision doc
scopes it conditionally — *"Noted by phase 3, owned by nobody, serves no requirement here. Fold
in only if a phase is already touching `http.py`."* — and no phase of this set touches
`engine/src/seer_engine/http.py` (measured below: the generator uses `urllib.request` directly
through its own `SecFetcher`, and `sec.py` has its own retry loop). It is recorded under
`## Decisions` in the plan index rather than left as an unowned R.

---

## Detailed Requirements Understanding

**Problem statement.** The point-in-time fundamentals panel the lab ranks on covers 2.5–4% of
the 19.8-year dev window, and nothing in the engine says so. Two cuts compose, and the dominant
one is self-inflicted: every interval in the vendored `ticker_cik.csv` starts on or after
2015-01-02 because the generator clamps every membership start to `cik.SINCE = 2015-01-02`, so
the date-keyed join `fundamental_facts ⋈ ticker_cik` discards 181,491 facts that are already in
the local database. The second cut is the ingest's `DEFAULT_SINCE_FILED = 2013-01-01`, which is
free to lower because `companyfacts` returns a filer's whole history in one call either way.

**What must change.**

1. `cik.SINCE` moves from 2015-01-02 to 2009-01-01, and the generator stops writing the clamp
   into the data. 525 existing rows gain an earlier, true `start_date`; 118 symbols enter scope
   for the first time and need a CIK each.
2. `commands/fundamentals.py`'s two floors move to 2009-01-01, and the ingest is re-run against
   the **local** train database.
3. A coverage measure lands in the engine as pure code, with a CLI surface and a `lab run`
   refusal, replacing the copy-paste snippet in `docs/runbooks/data-pipeline.md`.
4. The research store's `fundamentals.csv` is refreshed **without re-downloading bars**, because
   a full rebuild would change every bar and break comparability with the 64 trials already
   recorded. No such capability exists today.
5. The resulting coverage is measured across the whole dev window and written down as it is.

**Success criteria.**

- `engine/.venv/bin/pytest engine/tests -q` is green at the end of every phase, and green with
  `PG_TEST_URL` set as well.
- `cik.load_index()` loads a 913-symbol file whose 2015-01-02 start dates are gone except where
  2015-01-02 is genuinely a symbol's first membership date.
- `python -m seer_engine research_store --coverage` prints a per-year rankable count over
  1996..2015 and a single coverage fraction, from code in `seer_engine/fundamentals/`.
- `lab run` on a method whose allocator reads the panel refuses when that fraction is below the
  floor, naming the measured number.
- The decision doc's §4 table has its `~14%` / `~30%` estimates replaced by measurements.

**Key considerations, edge cases and constraints.**

- **Extending starts backwards can create pre-2015 ticker recycling.** `cik._check_intervals`
  already rejects overlapping intervals for one symbol, so a genuine pre-2015 handover must be
  split into two dated rows. Expect new cases; the further back the intervals reach, the more
  recycling they cross.
- **`end_date` must never move forward.** That is the whole defence against a recycled ticker
  resolving to today's holder, and it lives in the data, not in code.
- **The periodic-filing screen is a net, not a gate.** It passed a wrong company once (`HAR` →
  `0001073146`), and missed `LLL` and `DTV`. Every new `exact`/`fuzzy` row has to be read.
- **Zero `fuzzy` rows may ship.** `engine/data/SOURCES.md` requires it.
- **The local `universe` table is empty** (measured: 0 rows). The ingest reads it; `universe
  refresh` must run first, and it needs no network.
- **Neon must not be touched.** `fundamental_facts` and `fundamentals_log` are deliberately
  truncated there; train/eval reads `.env.local-train`.
- **A full research-store rebuild is forbidden.** Two rebuilds produce two different
  fingerprints because yfinance answers differently day to day.
- **M0005 must not be re-run.** Its id is spent (`runner.preflight` refuses), and a re-test is a
  new variation method that should not be minted until the gate reports a number worth testing.
- **PG_TEST_URL and `.env.local-train` point at the same container.** Measured safe: the `pg`
  fixture gives each DB test its own throwaway schema `t_<hex>` and never touches `public`,
  where the 1.2M facts live.

**Assumptions, stated.**

- The floor is **2009-01-01**, not 1996. Measured: `symbols_since(1996-01-02)` is 1265 symbols,
  against 913 at 2009 and 795 today. Reaching 1996 would cost ~470 new hand-audited CIK rows and
  buy nothing, because §4 says no XBRL exists before 2009 at any price. The rung is the decision
  doc's own §4 accounting table, whose `~30% (2009 →)` row presumes exactly this floor.
- "Coverage" means *the fraction of sampled dev-window dates on which the panel can actually
  rank* — a date counts when at least `top` symbols carry non-empty `Snapshot.observations`.
  Presence of a `Snapshot` is not coverage; that is the §1.3 failure.

---

## Analysis Scope

### Explicitly Mentioned Files

- `docs/plans/2026-10-05-fundamental-panel-coverage.md` (the spec)
- `engine/src/seer_engine/commands/fundamentals.py:67` (`DEFAULT_SINCE_FILED`)
- `engine/data/ticker_cik.csv`
- `engine/data/sp500_history.csv`, `engine/data/ndx_history.csv`
- `engine/src/seer_engine/paper/store.py:1035` (§6.1)
- `docs/runbooks/data-pipeline.md`
- `engine/data/SOURCES.md`

### Discovered Related Files

- `engine/src/seer_engine/cik.py` — owns `SINCE`, the loader, the interval invariants
- `engine/scripts/build_ticker_cik.py` — the generator; `spans()` is where the clamp is applied
- `engine/src/seer_engine/membership.py` — `compute_universe`, `build_intervals`, `symbols_since`
- `engine/src/seer_engine/fundamentals/panel.py` — `Snapshot`, `FundamentalPanel.as_of`
- `engine/src/seer_engine/fundamentals/ladder.py`, `sue.py`
- `engine/src/seer_engine/backtest/io.py:93` — `_FACTS_FROM`, the dated join
- `engine/src/seer_engine/backtest/market.py` — `Market`, `EMPTY_FUNDAMENTALS`
- `engine/src/seer_engine/research.py` — the store: `build_store`, `load_store`, `_seal`, `_swap_in`
- `engine/src/seer_engine/commands/research_store.py` — `--with-fundamentals`, `--verify`
- `engine/src/seer_engine/commands/lab.py:198` (`_run`), `engine/src/seer_engine/lab/runner.py:46` (`preflight`)
- `engine/src/seer_engine/strategies/f_fundamental.py` — the `FND` allocator and its eligibility rules
- `engine/src/seer_engine/lab/methods/m0005_fundamental_factors.py`
- `engine/src/seer_engine/commands/universe.py` — `universe refresh`
- `engine/src/seer_engine/universe.py:41` — `all_symbols`, the scope predicate
- `engine/tests/test_cik.py`, `test_fundamentals_command.py`, `test_research_store.py`,
  `test_market_fundamentals.py`, `test_lab_runner.py`, `test_paper_store.py`, `conftest.py`

---

## Current Dataflow

### Entry point A — `build_ticker_cik.py` (the generator, run by hand)

**Location:** `engine/scripts/build_ticker_cik.py:729` (`build`)
**Trigger:** `python engine/scripts/build_ticker_cik.py --out engine/data/ticker_cik.csv`
**Inputs:** `SEC_CONTACT_EMAIL`, `MASSIVE_API_KEY`, the vendored membership CSVs, a disk cache
at `engine/.cache/cik` (**measured empty today** — a re-run re-fetches everything).

Chain:

1. `membership.compute_universe(DATA_DIR)` → 1544 intervals (measured), back to 1996-01-02.
2. `spans(intervals)` → `symbol -> (start, end)`, **the hull of its membership clipped to
   `[SINCE, ...)`** — `engine/scripts/build_ticker_cik.py:708-727`. `start = max(iv.start_date,
   SINCE)` at line 716 **is the clamp**. With `SINCE = 2015-01-02` that yields 795 symbols, 525
   of which have `start_date == 2015-01-02`.
3. Tier 0 `MANUAL` (`:67-474`) — 70 hand-audited symbols, each carrying **literal** start/end
   strings. 60-odd of them hardcode `"2015-01-02"`, i.e. they carry a *copy* of the clamp rather
   than being derived from `spans()`.
4. Tier 1 `tier_current` → `company_tickers.json`; tier 2 `tier_edgar` → browse-edgar; tiers 3–4
   `massive_delisted_names` + `cik-lookup-data.txt` by name, `difflib` cutoff 0.90. Tiers 1–4
   all call `_row(..., span)` (`:839`), which reads `span[symbol]` — so they inherit the clamp.
5. Unresolved symbols → printed, exit 1.
6. **The periodic-filing screen** (`filed_inside`, `:685`): every row with a CIK and not in
   `SCREEN_EXEMPT` must show at least one `10-K/10-K405/10-KSB/10-Q/20-F/40-F` with
   `start <= filingDate < end`. Zero → printed, exit 1.
7. Sort by `(symbol, start_date)`, write the CSV.

**Exit points:** `engine/data/ticker_cik.csv`; exit 0/1/2.

### Entry point B — `cik.load_index()` (every reader)

**Location:** `engine/src/seer_engine/cik.py:237`
**Validation** (`load_ticker_cik`, `:139`): exact header; 10-digit CIK or `NONE`; parseable
dates; `end_date > start_date`; `source` in the five tiers; `note` mandatory for `fuzzy`,
`manual` and `NONE`; `company_name` mandatory when there is a CIK; file sorted by
`(symbol, start_date)`; no duplicate `(symbol, start_date)`; **no overlapping intervals for one
symbol** (`_check_intervals`, `:212`); only the last row of a symbol may be open; a `NONE` row
must be its symbol's only row.

**Exit points:** `resolve_row`/`resolve` (date-scoped, raises rather than guessing),
`filers` (the ingest entry point), `coverage_gaps` (clipped at `SINCE`).

### Entry point C — `fundamentals` (the ingest)

**Location:** `engine/src/seer_engine/commands/fundamentals.py:270` (`run`)
**Trigger:** `python -m seer_engine fundamentals [--since D] [--since-filed D] [--retry-failed]`
**Two floors:** `DEFAULT_SINCE = 2015-01-02` (`:63`) and `DEFAULT_SINCE_FILED = 2013-01-01`
(`:67`). `options_from_args` (`:249`) refuses `since_filed > since`.

Chain:

1. `membership_windows(conn, since, today)` — `_WINDOWS_SQL` (`:389`) over the **`universe`
   table**, `greatest(min(start_date), since)`. **Measured: the local train database has 0
   `universe` rows**, so this currently returns nothing and `select_symbols` (`:413`) raises
   *"the universe table holds no member on or after …"*.
2. `plan_jobs` (`:432`) → `resolve_window_ciks` (`:331`) → `cik.filers`, grouped by CIK, already
   logged CIKs skipped.
3. `fetch_cik` → `sec.Client.company_facts(cik, tags=LADDER_TAGS)`; `select_facts` (`:512`)
   keeps `(taxonomy, tag) in LADDER_TAGS and filed >= since_filed`.
4. `_write_batch` → `upsert_facts` (`:643`), one transaction per batch of 20 CIKs, with its
   `fundamentals_log` rows.

**State changes:** `fundamental_facts` (PK `(cik, taxonomy, tag, unit, period_start, period_end,
accn)`), `fundamentals_log` (keyed by `cik`), and `ticker_cik` via `sync_ticker_cik` (`:742`).

### Entry point D — the panel projection

**Location:** `engine/src/seer_engine/backtest/io.py:93`

```sql
FROM fundamental_facts f
JOIN ticker_cik m ON m.cik = f.cik
  AND f.filed >= m.start_date
  AND (m.end_date IS NULL OR f.filed < m.end_date)
```

This is the join that discards the 181,491 pre-2015 facts: **`f.filed >= m.start_date`** against
525 rows whose `m.start_date` is 2015-01-02. `load_panel` caches the result as a pickle keyed by
`(count(*), max(filed))` over this same join, so it self-invalidates on a re-vendoring.

Readers: `io.load_market` (`:156`), `paper/store.load_market_window` (`:1058`),
`research.load_store` (`:583`) — all three now pass `fundamentals=`.

### Entry point E — the research store

**Location:** `engine/src/seer_engine/research.py:290` (`build_store`)
**Trigger:** `python -m seer_engine research_store [--with-fundamentals] [--verify]`

`build_store` **always** fetches FX and downloads every symbol's bars from yfinance before it
writes anything; `facts` is an optional fifth file. `_seal` (`:500`) hashes
`(*DATA_FILES, *extra_files)` and the fingerprint is `sha256` of that sorted map; `_swap_in`
(`:521`) renames `.tmp` over the store. **There is no path that refreshes `fundamentals.csv`
alone** — that is the gap phase 4 fills.

Measured store on disk: `fingerprint e597367b…`, `bar_rows 2490793`, `symbols_requested 1061`,
`symbols_served 539`, five files including `fundamentals.csv`.

### Entry point F — `lab run`

**Location:** `engine/src/seer_engine/commands/lab.py:198` (`_run`)

```
runner.preflight(conn, method, path)      # refuses: uncommitted, already run, repeated digest
research.DEV_END == dev.DEV_END           # refuses
data = research.load_store(args.store)    # <- the panel first exists HERE
runner.run_method(conn, method, path, data, git_sha=...)
```

`runner.preflight` (`lab/runner.py:46`) runs **before** the store is loaded, so it cannot see
the panel. A coverage refusal therefore needs a second checkpoint after `load_store` — the
shape phase 1 adopts.

### Exit points and side effects

- `lab run` writes trials, `source_sha` and a terminal method status in one transaction. **This
  is the irreversible step**: `preflight` refuses a second run of any method and refuses a
  repeated `config_digest` on the dev window. That is what M0005 spent.
- `fundamentals` writes facts and log rows to whichever database `SEER_ENV_FILE` selects.
- `research_store` replaces `engine/.research/` atomically and changes the fingerprint.

---

## Key Data Structures

### `cik.CikRow` — `engine/src/seer_engine/cik.py:70`

`symbol, cik: str | None, start_date, end_date: date | None, company_name, source, note`.
`end_date` exclusive; `None` = still current; `cik is None` is the `NONE` sentinel.
**Used in:** `resolve_row`, `filers`, `coverage_gaps`, `commands/fundamentals.resolve_cik`,
`sync_ticker_cik`.

### `cik.SINCE` — `engine/src/seer_engine/cik.py:41`

`date(2015, 1, 2)`, *"First day of the backtest window. The map is only guaranteed from here on."*
**Used in:** `coverage_gaps`'s default, `build_ticker_cik.spans()` (the clamp),
`build_ticker_cik.build` (the `MANUAL`-membership assertion and the log line), and
`engine/tests/test_cik.py:316` (the `ever_members` fixture every vendored-file test reads).
**This single constant is the dominant cut.**

### `membership.Interval` — `engine/src/seer_engine/membership.py:51`

`symbol, index_id, start_date, end_date: date | None, source_symbol`. Produced by
`build_intervals` from the snapshot CSVs; `end_date` exclusive.

### `fundamentals.Snapshot` — `engine/src/seer_engine/fundamentals/panel.py:~300`

Every figure is float64, NaN = not available. **`observations: Mapping[str, Obs]` is the only
honest emptiness test**: `SymbolFundamentals.as_of(t)` always returns a `Snapshot`, with
`observations == {}` when no fact is visible at `t`.

`FundamentalPanel.as_of(symbol, t)` returns `None` only when the symbol has **no fact at all**,
ever. The measured panel holds 780 such symbols, so `as_of(...) is not None` is true for all 780
on every date in 1996 — which is precisely the vacuous check §1.3 describes.

### `research.ResearchData` — `engine/src/seer_engine/research.py:126`

`market: Market`, `dividends`, `spy_dividends`, `fingerprint`, `manifest`, `unserved`. The panel
is reached as `data.market.fundamentals`.

### `Market` — `engine/src/seer_engine/backtest/market.py:~110`

`history`, `membership`, `fx`, `fundamentals: Panel = EMPTY_FUNDAMENTALS`. **The default is the
hazard**: a construction site that omits the field gets a working, silent, empty panel.

### `FundamentalParams` — `engine/src/seer_engine/strategies/f_fundamental.py:214`

`max_stale_days: int = 400`, `top`, `rank`, `sizing`, liquidity floors. A symbol is eligible only
when the panel has a fact for it filed within `max_stale_days` of `d` — so coverage measured with
a 400-day staleness window is the number that actually predicts rankability.

---

## Dependencies

### Configuration / environment

| Variable | Used by | Where |
|---|---|---|
| `SEER_ENV_FILE` | `config.env_file()` | selects `.env.local-train` for train/eval |
| `DATABASE_URL_UNPOOLED` | every engine DB command | `.env.local-train` → `postgresql://postgres:pg@localhost:55432/postgres` |
| `SEC_CONTACT_EMAIL` | `sec.Client`, `build_ticker_cik.SecFetcher` | `.env.local`, `.env.local-train`; not a credential |
| `MASSIVE_API_KEY` | `build_ticker_cik` tiers 3–4 only | `.env.local`; free tier, 5 calls/min |
| `PG_TEST_URL` | `engine/tests/conftest.py:45` | DB tests; each gets a throwaway schema `t_<hex>` |

### External services

- `data.sec.gov` / `www.sec.gov` — free, fair-access paced (`SEC_MIN_INTERVAL = 0.15`).
- `api.massive.com` v3 reference tickers — free tier, `MASSIVE_MIN_INTERVAL = 12.5`, 50 pages.
- yfinance, Frankfurter — **not needed by this plan** and deliberately avoided (phase 4).

### Database schema

`005_fundamentals.sql`, applied and recorded in `schema_migrations`. Local train database
measured to hold: `fundamental_facts` 1,228,822 rows / 773 distinct CIKs, `fundamentals_log`
773 `ok` + 3 `empty`, `ticker_cik` 797 rows, **`universe` 0 rows, `bars` 0 rows**.

---

## Measurements taken during this analysis

All run on this host, 2026-10-05, against `2dad9ff`.

**Ever-member counts by floor** (`membership.symbols_since`):

| floor | symbols |
|---|---|
| 1996-01-02 | 1265 |
| 2005-01-01 | 1034 |
| **2009-01-01** | **913** |
| 2011-01-01 | 870 |
| 2013-01-01 | 827 |
| 2015-01-02 (today) | 795 |

**The clamp, in the shipped file:** 795 symbols / 798 rows; `start_date` histogram tops out at
**525 rows at exactly 2015-01-02**, then 8 at 2021-12-20, 6 at 2025-12-22, 6 at 2019-12-23.

**Re-running `spans()` with the floor at 2009-01-01:** 913 symbols, 540 clamped at the new floor,
**118 symbols entirely new**, **0 symbols lost**, **525 existing rows whose `start_date` moves
earlier**. The 118:

```
ACAS ACS AKS ANF ANRZQ APOL ATGE AYE BDK BEAM BIG BJS BMC BMS BNI BTUUQ CBE CEPH CITGQ CLF
CPWR CTX CVG CVH DDR DF DYN EKDKQ EP EQ FHN FII FMCN FRX FWLT GENZ GHC GOLD GR HANS HNZ HSH
IACI IGT INFY ITT JAVA JCP JNS JNY JOYG KBH KFT KG LIFE LOGI LSI LXK MBI MDP MEE MER MFE MHS
MI MICC MIL MMI MOLX MTLQQ MTW MWW NCC NIHD NOVL NSM NUAN NVLS NYT NYX ODP PBG PGN PPDI PTV
QGEN QLGC RDC RIMM ROH RRD RSHCQ RX RYAAY S SGP SHLD SII SLM SOV STR STRZA SUN SUNEQ SVU TEVA
TIE TLAB UST VIAV VMED WB WCRX WFT WPX WYE X XTO
```

Seven of these carry bankruptcy-era `Q` suffixes (`ANRZQ`, `BTUUQ`, `CITGQ`, `EKDKQ`, `MTLQQ`,
`RSHCQ`, `SUNEQ`) and none will be in `company_tickers.json`, so tiers 2–4 and `MANUAL` carry them.

**Stored facts by `filed` year** (local train database):

| year | facts | | year | facts |
|---|---|---|---|---|
| 2013 | 89,913 | | 2020 | 98,431 |
| 2014 | 91,578 | | 2021 | 91,870 |
| 2015 | 91,921 | | 2022 | 84,183 |
| 2016 | 91,655 | | 2023 | 83,277 |
| 2017 | 90,595 | | 2024 | 83,970 |
| 2018 | 92,259 | | 2025 | 83,504 |
| 2019 | 98,506 | | 2026 | 57,160 |

2013 + 2014 = **181,491**, exactly the figure §1.2 reports as dropped by the join. `min(filed)`
2013-01-02, `max(filed)` 2026-10-02; `min(period_end)` 2008-06-30.

**Baseline panel coverage** (store `e597367b…`, 780 panel symbols, semiannual samples
1996-01-01 .. 2015-07-01, "rankable" = `Snapshot.observations` non-empty):

```
1996-01-01 .. 2015-01-01:     0 rankable  (39 of 40 sample dates — all zero)
2015-07-01                : 507 rankable
dates with >= 20 rankable : 1/40 = 2.5%
```

**Test baseline at `2dad9ff`:** `engine/.venv/bin/pytest engine/tests -q` →
**2216 passed, 332 skipped** in 136s. The 332 skips are the DB tests (`PG_TEST_URL` unset).

**`engine/.cache/cik` is empty**, so a re-vendoring re-fetches `company_tickers.json`,
`cik-lookup-data.txt`, one browse-edgar call per unresolved symbol, one `submissions` call per
screened row (≈913 at 0.15 s ≈ 2.5 min, plus overflow files), and up to 50 Massive pages at
12.5 s ≈ 10 min. All free.

---

## Reference List

Every site that touches the thing being changed.

### `cik.SINCE` (= 2015-01-02 → 2009-01-01)

| Symbol / key | File:line | Kind | Package |
|---|---|---|---|
| `SINCE` definition | `engine/src/seer_engine/cik.py:41` | def | `seer_engine` |
| `coverage_gaps(..., since=SINCE)` | `engine/src/seer_engine/cik.py:339` | def (default) | `seer_engine` |
| `from seer_engine.cik import HEADER, NO_FILER, SINCE` | `engine/scripts/build_ticker_cik.py:43` | import | `scripts` |
| `spans()` clamp `max(iv.start_date, SINCE)` | `engine/scripts/build_ticker_cik.py:716` | call | `scripts` |
| `spans()` drop `end <= SINCE` | `engine/scripts/build_ticker_cik.py:717` | call | `scripts` |
| `log(f"ever-members since {SINCE}…")` | `engine/scripts/build_ticker_cik.py:737` | call | `scripts` |
| `BuildError(f"MANUAL has {symbol}, … since {SINCE}")` | `engine/scripts/build_ticker_cik.py:746` | call | `scripts` |
| `ever_members` fixture | `engine/tests/test_cik.py:316` | test | `tests` |

### `engine/data/ticker_cik.csv` (the data)

| Symbol / key | File:line | Kind | Package |
|---|---|---|---|
| `TICKER_CIK_FILE` | `engine/src/seer_engine/cik.py:38` | config | `seer_engine` |
| `load_ticker_cik` / `load_index` | `engine/src/seer_engine/cik.py:139,237` | def | `seer_engine` |
| `load_cik_map` (the only call into `cik`) | `engine/src/seer_engine/commands/fundamentals.py:301` | call | `commands` |
| `sync_ticker_cik` (the one writer of the table) | `engine/src/seer_engine/commands/fundamentals.py:742` | call | `commands` |
| `ticker_cik` table + `source` CHECK | `db/migrations/005_fundamentals.sql` | config | `db` |
| the dated join `_FACTS_FROM` | `engine/src/seer_engine/backtest/io.py:93` | call | `backtest` |
| vendored-file tests (`vendored_index`, `RECYCLED`, `SPOT_CHECKS`, `SHARE_CLASSES`) | `engine/tests/test_cik.py:305-425` | test | `tests` |
| `ticker_cik.csv` section (row counts, tier counts, re-vendoring recipe) | `engine/data/SOURCES.md:142-240` | doc | `data` |
| re-vendoring + the join explanation | `docs/runbooks/data-pipeline.md:~240-260` | doc | `docs` |

### `MANUAL` / `SCREEN_EXEMPT` (the hand-audit surfaces)

| Symbol / key | File:line | Kind | Package |
|---|---|---|---|
| `MANUAL` (70 symbols, literal start/end strings) | `engine/scripts/build_ticker_cik.py:67-474` | def | `scripts` |
| `SCREEN_EXEMPT` (11 symbols) | `engine/scripts/build_ticker_cik.py:475-491` | def | `scripts` |
| `filed_inside` (the screen) | `engine/scripts/build_ticker_cik.py:685` | def | `scripts` |
| `_row(..., span)` — tiers 1–4 inherit the clamp | `engine/scripts/build_ticker_cik.py:839` | def | `scripts` |
| `FUZZY_CUTOFF`, `match_name` | `engine/scripts/build_ticker_cik.py:55,666` | def | `scripts` |
| "zero `fuzzy` rows ship" requirement | `engine/data/SOURCES.md:227` | doc | `data` |

### The ingest floors

| Symbol / key | File:line | Kind | Package |
|---|---|---|---|
| `DEFAULT_SINCE = 2015-01-02` | `engine/src/seer_engine/commands/fundamentals.py:63` | def | `commands` |
| `DEFAULT_SINCE_FILED = 2013-01-01` | `engine/src/seer_engine/commands/fundamentals.py:67` | def | `commands` |
| `--since` / `--since-filed` help strings | `engine/src/seer_engine/commands/fundamentals.py:210-224` | config | `commands` |
| `options_from_args` (`since_filed <= since`) | `engine/src/seer_engine/commands/fundamentals.py:249` | def | `commands` |
| `_WINDOWS_SQL` (reads `universe`) | `engine/src/seer_engine/commands/fundamentals.py:389` | call | `commands` |
| `select_symbols` refusal | `engine/src/seer_engine/commands/fundamentals.py:413` | call | `commands` |
| module docstring "since 2015-01-02" | `engine/src/seer_engine/commands/fundamentals.py:4` | doc | `commands` |
| `SINCE = date(2015, 1, 2)` test constant | `engine/tests/test_fundamentals_command.py:24` | test | `tests` |
| `universe refresh` (populates `universe`) | `engine/src/seer_engine/commands/universe.py:86` | call | `commands` |

### The coverage check (today: a runbook snippet)

| Symbol / key | File:line | Kind | Package |
|---|---|---|---|
| the corrected snippet | `docs/runbooks/data-pipeline.md:208-232` | doc | `docs` |
| `FundamentalPanel.as_of` (returns None only for an absent symbol) | `engine/src/seer_engine/fundamentals/panel.py` | def | `fundamentals` |
| `Snapshot.observations` (the honest emptiness test) | `engine/src/seer_engine/fundamentals/panel.py` | def | `fundamentals` |
| `runner.preflight` (runs **before** the store loads) | `engine/src/seer_engine/lab/runner.py:46` | def | `lab` |
| `_run`: preflight → `load_store` → `run_method` | `engine/src/seer_engine/commands/lab.py:198-224` | call | `commands` |
| `MarketAware` protocol / `prepare_for` | `engine/src/seer_engine/strategies/allocator.py:99,117` | def | `strategies` |
| `FUNDAMENTAL.prepare_market` | `engine/src/seer_engine/strategies/f_fundamental.py:602` | impl | `strategies` |
| `max_stale_days = 400` | `engine/src/seer_engine/strategies/f_fundamental.py:214` | config | `strategies` |
| "READ THIS BEFORE RUNNING" preamble | `engine/src/seer_engine/lab/methods/m0005_fundamental_factors.py:17-30` | doc | `lab` |

### The research store

| Symbol / key | File:line | Kind | Package |
|---|---|---|---|
| `build_store` (always downloads bars) | `engine/src/seer_engine/research.py:290` | def | `seer_engine` |
| `_seal` / `fingerprint_of` / `_swap_in` | `engine/src/seer_engine/research.py:500,216,521` | def | `seer_engine` |
| `DATA_FILES` / `FUNDAMENTALS_FILE` / `MANIFEST_KEYS` | `engine/src/seer_engine/research.py:79,86,107` | config | `seer_engine` |
| `fundamentals_lines` / `_read_fundamentals` | `engine/src/seer_engine/research.py:225,262` | def | `seer_engine` |
| `load_store` → `ResearchData.market.fundamentals` | `engine/src/seer_engine/research.py:534,583` | def | `seer_engine` |
| `--with-fundamentals` / `--verify` / `_read_facts` | `engine/src/seer_engine/commands/research_store.py:72,67,100` | config | `commands` |
| manifest-shape assertions | `engine/tests/test_research_store.py` | test | `tests` |
| `/sync-research-store` (push/pull) | `~/.claude/skills/sync-research-store` | doc | — |

### §6.1 — already landed

| Symbol / key | File:line | Kind | Package |
|---|---|---|---|
| `load_market_window(..., cache_dir=...)` with `fundamentals=` | `engine/src/seer_engine/paper/store.py:1025-1063` | def | `paper` |
| `test_market_window_carries_the_fundamental_panel_not_an_empty_one` | `engine/tests/test_paper_store.py:554` | test | `tests` |
| `test_market_window_panel_equals_the_full_loads_panel` | `engine/tests/test_paper_store.py:573` | test | `tests` |
| `test_market_window_panel_is_empty_when_no_facts_are_stored` | `engine/tests/test_paper_store.py:585` | test | `tests` |

Committed as `2dad9ff`. **No phase re-implements it; phase 5 verifies it.**

**Corrected 2026-10-05 by the plan reconciler.** This table originally listed **two** tests, the
second named `test_market_window_panel_is_empty_when_the_facts_tables_are_absent` at `:536`.
**No test by that name exists anywhere in the tree** — the name came from an uncommitted draft.
`2dad9ff` added **three** tests, at `:554`, `:573` and `:585`, and the real third name is
`test_market_window_panel_is_empty_when_no_facts_are_stored`. The second,
`test_market_window_panel_equals_the_full_loads_panel`, asserts that windowing the bars does not
window the facts — which is what SUE's `MIN_QUARTERS` lookback needs. Verified by
`grep -n 'def test_market_window' engine/tests/test_paper_store.py`. See the plan index's
`## Decisions`, row C4c.

---

## Impact Points (files that WILL need changes)

| # | File | Why | Phase |
|---|---|---|---|
| 1 | `engine/src/seer_engine/fundamentals/coverage.py` *(new)* | the pure coverage measure — the thing that would have saved M0005 | 1 |
| 2 | `engine/src/seer_engine/fundamentals/__init__.py` | export the new names | 1 |
| 3 | `engine/src/seer_engine/commands/research_store.py` | `--coverage`; later the fundamentals-only refresh flag | 1, 4 |
| 4 | `engine/src/seer_engine/lab/runner.py` | the post-load coverage refusal | 1 |
| 5 | `engine/src/seer_engine/commands/lab.py` | call the refusal between `load_store` and `run_method`; the `--allow-coverage` escape | 1 |
| 6 | `engine/tests/test_fundamentals_coverage.py` *(new)* | the measure's own tests | 1 |
| 7 | `engine/tests/test_lab_runner.py` | the refusal's tests | 1 |
| 8 | `engine/src/seer_engine/cik.py` | `SINCE` → 2009-01-01, and its docstring | 2 |
| 9 | `engine/scripts/build_ticker_cik.py` | the `MANUAL` start sentinel; the 118 new audits; `SCREEN_EXEMPT` additions; the docstring's measured counts | 2 |
| 10 | `engine/data/ticker_cik.csv` | **regenerated** — 913 symbols, ≥916 rows | 2 |
| 11 | `engine/data/SOURCES.md` | row/tier counts, the new floor, the re-vendoring recipe | 2 |
| 12 | `engine/tests/test_cik.py` | the vendored-file assertions against the new floor | 2 |
| 13 | `engine/src/seer_engine/commands/fundamentals.py` | both floors → 2009-01-01, docstrings, help strings | 3 |
| 14 | `engine/tests/test_fundamentals_command.py` | the `SINCE` constant and the window assertions | 3 |
| 15 | `engine/src/seer_engine/research.py` | refresh `fundamentals.csv` without re-downloading bars | 4 |
| 16 | `engine/tests/test_research_store.py` | the refresh's tests (bars byte-identical, fingerprint changes) | 4 |
| 17 | `docs/runbooks/data-pipeline.md` | the snippet is replaced by the command; the measured numbers | 5 |
| 18 | `docs/plans/2026-10-05-fundamental-panel-coverage.md` | §4's estimates replaced by measurements | 5 |
| 19 | `engine/src/seer_engine/lab/methods/m0005_fundamental_factors.py` | the "READ THIS BEFORE RUNNING" preamble now points at the gate | 5 |
| 20 | `engine/package_readme.md` | the new command and the new floor | 5 |
| 21 | `engine/.research/` *(untracked)* | the refreshed panel + pushed to Blob | 5 |

**This document describes. The plan files prescribe.**

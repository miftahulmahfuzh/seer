# Code Analysis: SEC EDGAR point-in-time fundamentals (Gap B)

**Type:** Feature Implementation
**Date:** 2026-10-05 08:18:33
**Session ID:** 20261005-081833-G7K2
**Plan:** `EDGAR_FUNDAMENTALS_PLAN.md` (7 phases)
**Worktree:** `/home/miftah/.worktrees/seer/edgar-fundamentals`, branch `feature/edgar-fundamentals` (base `origin/main` @ `3df1b98`)

---

## User Input

### Original User Request

> Gap B — SEC EDGAR point-in-time fundamentals pipeline for the Seer engine, as specified in docs/plans/2026-10-05-delisted-and-fundamentals.md §3.
>
> Scope to analyze and plan:
> 1. ticker -> CIK bridge for the 133 delisted ever-members (0/133 resolve via SEC's current company_tickers.json). Measured recipe: Massive delisted reference (23,462 tickers) -> company name -> SEC cik-lookup-data.txt (1,061,750 pairs) with corporate-suffix stripping = 98/133 automated (94 exact + 4 fuzzy), 35 need manual mapping. Must be vendored as engine/data/ticker_cik.csv in the style of the existing engine/data/ticker_aliases.csv. CRITICAL: recycled tickers (CA -> an Xtrackers ETF, MON -> a SPAC, PLL -> Piedmont Lithium, ALTR -> Altair, LLL -> JX Luxventure, DTV -> DTE units) mean the map must key on (ticker, date) or CIK, never bare ticker.
> 2. Bulk ingest of SEC XBRL facts. companyfacts.zip is 1.41 GB; DERA quarterly Financial Statement Data Sets (2009Q2+, sub.txt/num.txt) are the relational alternative. Each fact carries accn, form, fy, fp and filed. `filed` is the no-look-ahead boundary: the loader must only ever expose the latest fact with filed <= t. Restatements appear as separate facts and must stay queryable rather than being overwritten.
> 3. Concept ladder. Measured coverage over 8 dead filers: revenue 8/8 (2 tag variants: Revenues, RevenueFromContractWithCustomerExcludingAssessedTax), net income 8/8, assets 8/8, equity 8/8, operating cash flow 8/8, diluted EPS 8/8, shares outstanding 8/8 (dei:EntityCommonStockSharesOutstanding), operating income 6/8, gross profit only 2/8. Gross profitability (Novy-Marx) must therefore derive Revenues - CostOfRevenue with a documented fallback.
> 4. New Postgres schema + migration in db/migrations, written by the engine over DATABASE_URL_UNPOOLED, consistent with how bars/universe/dividends/split_adjustments are handled.
> 5. A new seer_engine command (sibling of backfill/nightly/universe) to load and refresh fundamentals, with resumability in the style of backfill_log, and SEC's fair-access rules (User-Agent required, 10 req/s) respected in the http layer.
> 6. Factor exposure to the lab: value, quality, profitability, and SUE (standardized unexpected earnings, seasonal random walk EPS_q - EPS_q-4 scaled by dispersion of recent surprises) — analyst-consensus surprise is NOT available free (Finnhub free tier returns only 4 quarters) and is explicitly out of scope.
>
> Out of scope: Gap A (delisted price bars) — that is blocked on a $199 Massive Advanced purchase that cannot happen for at least two weeks. The fundamentals work must not depend on it. Note that fundamentals for the 133 delisted names are fully available from EDGAR even though their prices are not, so the pipeline should be built for all 795 ever-members, not just the 663 with bars.
>
> Relevant existing code: engine/src/seer_engine/ (config.py, db.py, http.py, massive.py, finnhub.py, commands/backfill.py, universe.py, membership.py, lab/), engine/data/ (SOURCES.md, ticker_aliases.csv), db/migrations/, docs/runbooks/data-pipeline.md.

### User-Provided Context

Blocking constraint stated by the owner in conversation: the credit card needed for the $199
Massive Advanced purchase cannot be used for at least two weeks (card expired, re-delivery
failing). Gap B is the $0 track and must therefore be fully independent of Gap A.

### User-Provided Files

None by `@`; the request names modules and `docs/plans/2026-10-05-delisted-and-fundamentals.md`
(copied into this worktree) as the specification.

### Requirement IDs

| ID | What the user asked for |
|---|---|
| R1 | ticker → CIK bridge for the delisted ever-members, vendored as `engine/data/ticker_cik.csv`, keyed so a recycled ticker can never resolve to the wrong company |
| R2 | Bulk ingest of SEC XBRL facts with `filed` as the no-look-ahead boundary and restatements kept queryable rather than overwritten |
| R3 | Concept ladder over the measured tag variants, with gross profit derived (`Revenues − CostOfRevenue`) and a documented fallback |
| R4 | New Postgres schema + migration in `db/migrations`, written by the engine over `DATABASE_URL_UNPOOLED`, consistent with `bars`/`universe`/`dividends`/`split_adjustments` |
| R5 | A new `seer_engine` command (sibling of `backfill`/`nightly`/`universe`), resumable in the style of `backfill_log`, respecting SEC fair access (User-Agent, 10 req/s) |
| R6 | Factor exposure to the lab: value, quality, profitability and SUE (seasonal random walk); analyst-consensus surprise explicitly out of scope |

---

## Detailed Requirements Understanding

**Problem statement.** The Seer store holds prices and point-in-time index membership but no
fundamentals at all, so the factor families best documented after momentum — value, quality,
profitability, post-earnings-announcement drift — cannot be tested. SEC EDGAR serves these for
free, including for the 133 ever-members that no longer trade, because EDGAR is an archive and
never deletes a filer. The work is to turn that archive into a point-in-time panel the lab can
rank on, without ever exposing a fact before the date it was filed.

**What must change.**

- A new vendored `ticker_cik.csv` and its loader, because `company_tickers.json` resolves 0 of
  the 133 dead names.
- A new SEC client in the engine's impure layer, honouring SEC's declared fair-access rules.
- Two new tables and a migration, following the additive style of `002_engine.sql`.
- A new command module in `seer_engine/commands/`, which `cli.py` discovers automatically.
- A pure derivation layer that turns raw XBRL facts into the handful of metrics the factors need.
- An extension to `Market` so a lab allocator can see fundamentals the same way it sees bars.

**Success criteria.**

1. For any symbol and any date `t`, the panel exposes only facts with `filed <= t`. A test proves
   this on a known restatement.
2. All 795 ever-members are attempted, including the 133 with no bars; `fundamentals_log` records
   the outcome per symbol so a re-run resumes.
3. The concept ladder's measured coverage is reproduced by tests over the 8 sampled dead filers.
4. A recycled ticker (CA, MON, PLL, ALTR, LLL, DTV) resolves to the company that held it during
   the membership interval, never to the current holder, and a test asserts this.
5. A lab method using a fundamental factor runs end to end on the dev window.

**Key considerations and constraints.**

- **Purity.** `engine/tests/test_strategy_purity.py` globs `strategies/*.py`, `backtest/*.py` and
  `paper/*.py` and forbids `psycopg`, `requests`, `yfinance`, `time`, `random`, `logging`,
  `urllib`, `socket`, clock reads and `open()` in all of them except `backtest/io.py` and
  `paper/store.py`. Anything added under those directories inherits the rule automatically, with
  no test edit — so the derivation layer must be pure and the SEC client must live outside them.
- **No look-ahead is the whole point.** `filed` is the only safe boundary. `period_end` is not:
  a Q4 figure for period ending 2015-12-31 is typically filed in February 2016.
- **Restatements.** A company can report `Assets` for the same period in several filings. They
  differ by accession number, so the primary key must include `accn` or restatements silently
  overwrite each other and as-reported becomes unrecoverable.
- **SEC fair access.** A declared `User-Agent` carrying contact information is required, and the
  rate ceiling is 10 requests/second. `http.py`'s module-level session sets
  `User-Agent: seer-engine/<version>`, which carries no contact address.

**Assumptions, stated rather than asked.**

- The 795 ever-members since 2015-01-02 are the ingest scope, not the 1,265 rows in `universe`
  (which runs back to 1996). Pre-2015 members are outside every backtest window and XBRL barely
  covers them.
- XBRL coverage effectively begins 2009 and is complete from 2011. The backtest window opens
  2015-01-02, so no filer in scope predates coverage.
- The manual residue of the CIK map (35 names) is produced by a human-reviewed one-off script and
  committed as data, not resolved at runtime.

---

## Analysis Scope

### Explicitly Mentioned Files

`engine/src/seer_engine/config.py`, `db.py`, `http.py`, `massive.py`, `finnhub.py`,
`commands/backfill.py`, `universe.py`, `membership.py`, `lab/`; `engine/data/SOURCES.md`,
`engine/data/ticker_aliases.csv`; `db/migrations/`; `docs/runbooks/data-pipeline.md`.

### Discovered Related Files

- `engine/src/seer_engine/cli.py` — command discovery; adding a command means adding a module
- `engine/src/seer_engine/backtest/io.py` — the only DB/FS edge of the backtest
- `engine/src/seer_engine/backtest/market.py` — `Market`, `Membership`; pure
- `engine/src/seer_engine/strategies/allocator.py:49` — the `Allocator` protocol
- `engine/src/seer_engine/strategies/f_factor.py` — the existing cross-sectional factor allocator
- `engine/src/seer_engine/strategies/base.py:34` — `History`
- `engine/src/seer_engine/lab/method.py`, `lab/store.py`, `lab/methods/` — the lab
- `engine/tests/test_strategy_purity.py` — the purity gate
- `db/migrations/002_engine.sql` — the table style to follow

---

## Current Dataflow

### Entry Point: `python -m seer_engine <command>`

**Location:** `engine/src/seer_engine/cli.py`
**Trigger:** CLI
**Mechanism:** `discover()` walks `pkgutil.iter_modules(commands.__path__)` and takes every public
non-package module exposing a callable `run`. Each module supplies `HELP`, optional
`add_arguments(p)`, and `run(args) -> int` used as the process exit code. Global `--dry-run` and
`-v` are injected on both sides of the command name.
**Consequence for this work:** a new command is a new module under `commands/`. `cli.py` is not
edited.

### Configuration

**Location:** `config.py`
`load_env()` reads the repo-root `.env.local` via python-dotenv without overriding the
environment; `REPO_ROOT` is `parents[3]` of `config.py`. `get(name)` returns None when unset or
empty; `require(name)` raises `ConfigError` (exit code is the CLI's missing-setting path).

### Database access

**Location:** `db.py`
`connect(url=None)` opens psycopg with `autocommit=False` against `DATABASE_URL_UNPOOLED`
(Neon's direct endpoint; the pooled one cannot hold session state). `transaction(conn, dry_run)`
is the one write helper: commit on success, rollback on error, and rollback *after* running every
statement when `dry_run` is set.

### HTTP layer

**Location:** `http.py`
Module-level `_session` with `User-Agent: seer-engine/<version>`; `_sleep = time.sleep`, both
replaceable by tests. `get_json(url, params, retries=3, backoff=5.0, timeout=30)` retries
connection errors, timeouts, 429 and 5xx with exponential backoff, honours a longer numeric
`Retry-After`, and raises `HttpError` otherwise. **It returns only `dict`** — a JSON array or a
binary body is rejected. `redact()` strips `apikey`/`token`/`key` query values from every logged
or raised URL.

### Existing vendor clients — the pattern to copy

**`massive.py`** — `BASE_URL`, `MIN_INTERVAL = 12.5` (free tier 5/min) enforced from the end of
the previous call, `RETRIES`, `BACKOFF`, `MAX_PAGES`, a `Protocol` for the source so tests inject
a fake, and the key travelling only as a query parameter handed to `http.get_json`.

**`finnhub.py`** — the same shape with the key in the `X-Finnhub-Token` **header**, injectable
transport/`clock`/`sleep`, and every error string passed through a `scrub` built from
`http.redact` plus the key itself.

A SEC client needs neither a key nor redaction, but does need its own session so the
contact-carrying `User-Agent` does not leak into Massive and Finnhub calls.

### Resumable bulk load — `commands/backfill.py`

**Location:** `engine/src/seer_engine/commands/backfill.py`
`Options` (frozen) carries `start`, `end`, `symbols`, `retry_failed`, `batch_size`, `dry_run`.
Symbols are fetched in batches of 40; **each batch is written in its own transaction together
with its `backfill_log` rows**, so a crash loses at most one batch. `SymbolResult` carries
`status` ∈ {`ok`, `empty`, `failed`}; `Summary` accumulates and computes `exit_code()` — 1 when
anything failed, 0 otherwise, with `empty` explicitly not an error. `--retry-failed` re-attempts
only `failed`/`empty`; a plain re-run skips every symbol already logged with any status. Every
write is an upsert, so re-running changes no rows.

### State: the universe

**Location:** `universe.py`, `membership.py`, `db/migrations/002_engine.sql`
`membership.DATA_DIR = Path(__file__).resolve().parents[2] / "data"`. Snapshots, overrides and
aliases are parsed from CSV with `csv.DictReader`, validated hard (`MembershipError` on a bad
header, a duplicate, `old == new`, or an alias chain), and swept into `[start, end)` intervals
written to `universe` in one transaction. `ticker_aliases.csv` is `old,new,effective_date,note`,
and every `old` must point straight at the **current** ticker — chains are rejected.

### The backtest's data edge

**Location:** `backtest/io.py`
`load_market(conn, cache_dir, refresh)` is the only module in `seer_engine.backtest` touching the
database or filesystem (`test_strategy_purity.py` exempts it by name). It requires a connection
with no transaction in progress, sets `REPEATABLE READ, READ ONLY`, streams
`COPY (SELECT symbol, date, open, high, low, close, volume FROM bars ORDER BY symbol, date) TO
STDOUT` into a pandas frame cached as `bars-<max(date)>-<count(*)>.pkl` under
`engine/.cache`, reads `universe` and `fx_rates` fresh, and always ends with `conn.rollback()`.
Returns `(Market, row_count)`.

### The pure market

**Location:** `backtest/market.py`
`Market` is a frozen dataclass of `history: Mapping[str, History]`, `membership: Membership`,
`fx`. `Membership` sweeps intervals once into constant segments so a day lookup is one bisect.
`History` (`strategies/base.py:34`) is `symbol` plus six aligned arrays — `dates`
(`datetime64[D]`, strictly ascending) and float64 `open/high/low/close/volume`.

### The allocator contract — the load-bearing interface for R6

**Location:** `strategies/allocator.py:49`

```python
@runtime_checkable
class Allocator(Protocol):
    id: str
    def lookback(self, params: Any) -> int: ...
    def symbols(self, params: Any) -> tuple[str, ...]: ...
    def holds(self, params: Any) -> tuple[str, ...]: ...
    def uses_members(self, params: Any) -> bool: ...
    def targets(self, history, members, data_date, held, params) -> tuple[Target, ...]: ...
    def prepare(self, history: Mapping[str, History]) -> Any: ...
    def targets_prepared(self, prepared, members, data_date, held, params) -> tuple[Target, ...]: ...
```

`prepare` receives **only** `Mapping[str, History]`. Call sites, all passing `market.history`:

| File:line | Call |
|---|---|
| `backtest/book_runner.py:287` | `allocator.targets(history, members, data_date, mine, params)` |
| `backtest/book_runner.py:289` | `allocator.targets_prepared(prepared, members, data_date, mine, params)` |
| `backtest/dev.py:455` | `cache[key] = c.allocator.prepare(market.history)` |
| `backtest/walkforward.py:200` | `strategy.prepare(market.history)` |
| `backtest/runner.py:143` | `strategy.prepare(market.history)` |

Implementers: `PicksAllocator`, `BlendAllocator`, `VolTargetAllocator` (`allocator.py`), plus
`strategies/a.py`, `a2.py`, `b.py`, `c.py`, `f_factor.py`, `f_index.py`, `f_rotation.py`,
`f_swing.py`. **Widening `prepare`'s signature would touch all of them.**

`params` is not a carrier for the panel: `lab/method.py:config_text` canonicalises `params` into
the trial digest via `backtest/registry._canon`, so embedding bulk data there would change every
digest and break the lab's re-run detection.

### The lab

**Location:** `lab/method.py`, `lab/store.py`, `lab/methods/`
A method is one file `lab/methods/mNNNN_<slug>.py` exporting `METHOD`, with 1–6 fixed variants.
New signal logic is an `Allocator` in the same file. `config_digest` identifies a trial by what
it does — rules, allocator id, params — so allocator ids must be unique across lab methods, and a
method file is frozen once it has run (`source_sha`).

### The purity gate

**Location:** `engine/tests/test_strategy_purity.py`
Globs `strategies/*.py`, `backtest/*.py`, `paper/*.py`; exempts only `backtest/io.py` and
`paper/store.py`. Forbids importing `psycopg`, `requests`, `yfinance`, `time`, `random`,
`logging`, `urllib`, `socket`; forbids `now`/`utcnow`/`today`/`fromtimestamp`/`random` attribute
access and `print`/`open`/`input` calls. Modules added later are covered without editing the
test — so a new pure module under those directories needs no test change, and an impure one
placed there would fail CI.

---

## Key Data Structures

### `Market` — `backtest/market.py`
Frozen; `history: Mapping[str, History]`, `membership: Membership`, `fx`. Pure.

### `History` — `strategies/base.py:34`
`symbol: str`; `dates: np.ndarray[datetime64[D]]` strictly ascending; `open/high/low/close/volume:
np.ndarray[float64]`, all the same length as `dates`.

### `backfill_log` — `db/migrations/002_engine.sql`
`symbol text PRIMARY KEY`, `status text CHECK (status IN ('ok','empty','failed'))`, `first_date`,
`last_date`, `rows int`, `error text`, `updated_at timestamptz DEFAULT now()`.

### The SEC fact shape (measured, `data.sec.gov`)
`companyfacts/CIK##########.json` → `facts.<taxonomy>.<tag>.units.<unit>[]`, each element
carrying `start` (absent for instantaneous facts), `end`, `val`, `accn`, `fy`, `fp`, `form`,
`filed`, and sometimes `frame`. Taxonomies in scope: `us-gaap` and `dei`.

---

## Dependencies

### Configuration / Environment
`DATABASE_URL_UNPOOLED` (required for writes). **A new setting is required**: SEC's fair-access
policy wants a contact address in the User-Agent. No existing variable carries one.

### External Services
`data.sec.gov` — no key, no quota beyond 10 req/s and the declared User-Agent. `www.sec.gov` for
`cik-lookup-data.txt` (39 MB) and `company_tickers.json`. Both already reachable from this
machine (verified 2026-10-05).

### Python packages
`pyproject.toml` already pins `psycopg[binary]`, `pandas`, `numpy`, `pandas_market_calendars`,
`yfinance`, `requests`, `python-dotenv`, `scikit-learn`, `openpyxl`; dev adds `pytest`, `ruff`.
**Nothing new is needed** — `zipfile`, `json` and `csv` are stdlib.

### Lint
ruff `select = ["E9", "F"]`, `ignore = ["F401"]`, `target-version = "py311"`. Style families are
deliberately not selected.

---

## Reference List

Every site a fundamentals pipeline touches.

| Symbol / key | File:line | Kind | Package |
|---|---|---|---|
| `discover()` | `cli.py:30` | def — auto-picks up a new command module | `seer_engine` |
| `commands/` | `commands/__init__.py` | pkg — new module lands here | `seer_engine.commands` |
| `config.get` / `config.require` | `config.py:45`, `config.py` | def — new setting read here | `seer_engine` |
| `http._session` | `http.py:21` | config — UA lacks a contact address | `seer_engine` |
| `http.get_json` | `http.py:50` | def — dict-only; no binary, no array | `seer_engine` |
| `db.connect` / `db.transaction` | `db.py:18`, `db.py:31` | def — write path | `seer_engine` |
| `membership.DATA_DIR` | `membership.py:29` | config — vendored CSV root | `seer_engine` |
| `ticker_aliases.csv` | `engine/data/` | data — the style `ticker_cik.csv` follows | — |
| `SOURCES.md` | `engine/data/` | doc — every vendored file documented with sha256 | — |
| `backfill_log` | `db/migrations/002_engine.sql:33` | schema — resumability pattern | `db` |
| `Options`/`SymbolResult`/`Summary` | `commands/backfill.py:57,68,75` | def — command shape | `seer_engine.commands` |
| `Summary.exit_code` | `commands/backfill.py:85` | def — `empty` is not a failure | `seer_engine.commands` |
| `load_market` | `backtest/io.py:73` | def — must also load fundamentals | `seer_engine.backtest` |
| `CACHE_DIR` | `backtest/io.py` | config — pickle cache keyed by table fingerprint | `seer_engine.backtest` |
| `Market` | `backtest/market.py` | struct — gains a `fundamentals` field | `seer_engine.backtest` |
| `Allocator` | `strategies/allocator.py:49` | protocol — gains `prepare_market` | `seer_engine.strategies` |
| `prepare(market.history)` | `dev.py:455` | call — the ONLY real call site; `walkforward.py:200` and `runner.py:143` are docstrings. Other callers: `commands/backtest.py:193`, `backtest_wf.py:212`, `backtest_b.py:282` | `seer_engine.backtest` |
| `f_factor.FACTOR` | `strategies/f_factor.py` | impl — the sibling the fundamental allocator copies | `seer_engine.strategies` |
| `config_text` / `config_digest` | `lab/method.py:33,41` | def — params must stay small | `seer_engine.lab` |
| `FORBIDDEN_*` / `IMPURE` | `tests/test_strategy_purity.py` | test — auto-covers new modules | `engine.tests` |
| `migrate` | `commands/migrate.py`, `schema_migrations` | def — applies `db/migrations/*.sql` | `seer_engine.commands` |

---

## Impact Points (files that WILL need changes)

| # | Path | Why | Phase |
|---|---|---|---|
| 1 | `engine/data/ticker_cik.csv` *(new)* | the bridge; 0/133 dead names resolve otherwise | 1 |
| 2 | `engine/data/SOURCES.md` | every vendored file is documented with upstream + sha256 | 1 |
| 3 | `engine/src/seer_engine/cik.py` *(new)* | loader + validation, mirroring `membership.load_aliases` | 1 |
| 4 | `db/migrations/005_fundamentals.sql` *(new)* | `ticker_cik`, `fundamental_facts`, `fundamentals_log` | 2 |
| 5 | `engine/src/seer_engine/sec.py` *(new)* | SEC client: contact UA, 10 req/s, injectable transport | 3 |
| 6 | `engine/src/seer_engine/config.py` | new `SEC_CONTACT_EMAIL` setting | 3 |
| 7 | `engine/src/seer_engine/commands/fundamentals.py` *(new)* | the resumable command | 4 |
| 8 | `engine/src/seer_engine/fundamentals/` *(new pkg)* | pure concept ladder, PIT selection, SUE | 5 |
| 9 | `engine/src/seer_engine/backtest/market.py` | `Market` gains `fundamentals` | 6 |
| 10 | `engine/src/seer_engine/backtest/io.py` | `load_market` loads the panel, cached | 6 |
| 11 | `engine/src/seer_engine/strategies/allocator.py` | `Allocator` gains optional `prepare_market` | 6 |
| 12 | `engine/src/seer_engine/backtest/dev.py:455` (+ `dev.py:367`, `research.py:472`, `paper/replay.py:281`, `commands/paper.py:254` rebuild `Market` and would drop the field) | prefer `prepare_market`; carry the panel through every `Market(...)` site | 6 |
| 13 | `engine/src/seer_engine/strategies/f_fundamental.py` *(new)* | the fundamental factor allocator | 7 |
| 14 | `engine/src/seer_engine/lab/methods/m0005_*.py` *(new)* | a lab method that uses it | 7 |
| 15 | `docs/runbooks/data-pipeline.md` | the new command, its exit codes, its re-vendoring steps | 7 |
| 16 | `engine/tests/` | one test module per phase | all |

**This document describes. The plan files prescribe.**

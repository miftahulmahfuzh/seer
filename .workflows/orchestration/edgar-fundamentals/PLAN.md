# Plan: SEC EDGAR point-in-time fundamentals (Gap B)

**Slug:** edgar-fundamentals
**Date:** 2026-10-05 08:18:33
**Analysis:** `20261005-081833-G7K2_code_analyzer.md`
**Worktree:** `/home/miftah/.worktrees/seer/edgar-fundamentals`
**Branch:** `feature/edgar-fundamentals` (base: `origin/main` @ `3df1b98`)
**Phases:** 7
**Status:** reconciled
**Coordinator:** —
**Reconciled:** 2026-10-05, rounds 1 and 2 (`plan-reconciler`) — round 2 was the verify pass

---

## Why

> Gap B — SEC EDGAR point-in-time fundamentals pipeline for the Seer engine, as specified in
> docs/plans/2026-10-05-delisted-and-fundamentals.md §3.
>
> 1. ticker -> CIK bridge for the 133 delisted ever-members (0/133 resolve via SEC's current
>    company_tickers.json). Measured recipe: Massive delisted reference (23,462 tickers) ->
>    company name -> SEC cik-lookup-data.txt (1,061,750 pairs) with corporate-suffix stripping =
>    98/133 automated (94 exact + 4 fuzzy), 35 need manual mapping. Must be vendored as
>    engine/data/ticker_cik.csv in the style of the existing engine/data/ticker_aliases.csv.
>    CRITICAL: recycled tickers (CA -> an Xtrackers ETF, MON -> a SPAC, PLL -> Piedmont Lithium,
>    ALTR -> Altair, LLL -> JX Luxventure, DTV -> DTE units) mean the map must key on
>    (ticker, date) or CIK, never bare ticker.
> 2. Bulk ingest of SEC XBRL facts. companyfacts.zip is 1.41 GB; DERA quarterly Financial
>    Statement Data Sets (2009Q2+, sub.txt/num.txt) are the relational alternative. Each fact
>    carries accn, form, fy, fp and filed. `filed` is the no-look-ahead boundary: the loader must
>    only ever expose the latest fact with filed <= t. Restatements appear as separate facts and
>    must stay queryable rather than being overwritten.
> 3. Concept ladder. Measured coverage over 8 dead filers: revenue 8/8 (2 tag variants: Revenues,
>    RevenueFromContractWithCustomerExcludingAssessedTax), net income 8/8, assets 8/8, equity 8/8,
>    operating cash flow 8/8, diluted EPS 8/8, shares outstanding 8/8
>    (dei:EntityCommonStockSharesOutstanding), operating income 6/8, gross profit only 2/8. Gross
>    profitability (Novy-Marx) must therefore derive Revenues - CostOfRevenue with a documented
>    fallback.
> 4. New Postgres schema + migration in db/migrations, written by the engine over
>    DATABASE_URL_UNPOOLED, consistent with how bars/universe/dividends/split_adjustments are
>    handled.
> 5. A new seer_engine command (sibling of backfill/nightly/universe) to load and refresh
>    fundamentals, with resumability in the style of backfill_log, and SEC's fair-access rules
>    (User-Agent required, 10 req/s) respected in the http layer.
> 6. Factor exposure to the lab: value, quality, profitability, and SUE (standardized unexpected
>    earnings, seasonal random walk EPS_q - EPS_q-4 scaled by dispersion of recent surprises) —
>    analyst-consensus surprise is NOT available free (Finnhub free tier returns only 4 quarters)
>    and is explicitly out of scope.
>
> Out of scope: Gap A (delisted price bars) — that is blocked on a $199 Massive Advanced purchase
> that cannot happen for at least two weeks. The fundamentals work must not depend on it. Note
> that fundamentals for the 133 delisted names are fully available from EDGAR even though their
> prices are not, so the pipeline should be built for all 795 ever-members, not just the 663 with
> bars.

## Requirements

| ID | What the user asked for | Phases |
|---|---|---|
| R1 | ticker → CIK bridge, vendored as `engine/data/ticker_cik.csv`, keyed so a recycled ticker can never resolve to the wrong company | 1, 4 |
| R2 | Bulk ingest of SEC XBRL facts, `filed` as the no-look-ahead boundary, restatements kept queryable | 3, 4 |
| R3 | Concept ladder over the measured tag variants, gross profit derived with a documented fallback | 5 |
| R4 | Postgres schema + migration consistent with `bars`/`universe`/`dividends`/`split_adjustments` | 2 |
| R5 | New resumable `seer_engine` command respecting SEC fair access (User-Agent, 10 req/s) | 3, 4 |
| R6 | Factor exposure to the lab: value, quality, profitability, SUE; consensus surprise out of scope | 6, 7 |

R1 picked up phase 4 in reconciliation: phase 1 owns the vendored CSV and its loader, and phase
4 owns `sync_ticker_cik`, the one writer of the `ticker_cik` **table** from it (Decisions). The
requirement is not met until the bridge reaches the database the ingest and the panel load both
read. Every other row is unchanged — no requirement moved phases and none was dropped.

## Scope

**In scope:** a vendored ticker→CIK map with validity intervals; a SEC `data.sec.gov` client; two
new tables and a migration; a resumable `fundamentals` command; a pure derivation package
(concept ladder, point-in-time selection, SUE); `Market.fundamentals` and the allocator hook; one
fundamental factor allocator and one lab method; runbook updates.

**Out of scope, and why:**
- **Gap A — delisted price bars.** Blocked on a $199 purchase the owner cannot make for at least
  two weeks. No phase may import, assume or wait on it. Fundamentals for the 133 dead names come
  from EDGAR regardless of whether their prices ever arrive.
- **Analyst-consensus earnings surprise.** Finnhub's free tier returns 4 quarters; not
  backfillable. SUE on a seasonal random walk is the free substitute and is in scope.
- **Pre-2015 members.** `universe` runs back to 1996; XBRL effectively starts 2009 and the
  backtest window opens 2015-01-02.
- **Rebuilding the existing `f_factor` allocator.** The fundamental allocator is a sibling, not a
  rewrite.

## Invariants

1. **The tree builds and `pytest engine/tests -q` passes at the end of every phase.**
2. **No look-ahead, ever.** Every read path exposes only facts with `filed <= t`. A fact's
   `period_end` is never used as its availability date.
3. **Restatements are preserved, not overwritten.** `accn` is part of the fact identity.
4. **A ticker alone never identifies a company.** Every ticker→CIK resolution is scoped by date.
5. **No phase weakens the purity gate.** Nothing under `strategies/`, `backtest/`, `paper/` or
   the new `fundamentals/` imports `psycopg`, `requests`, `time`, `random`, `logging`, `urllib`
   or `socket`, reads the clock, or calls `open`/`print` — except `backtest/io.py`. Phase 5 MAY
   extend `test_strategy_purity.py`'s glob additively to cover `fundamentals/` (a strengthening);
   no other phase touches that file, and phase 6 in particular must leave it byte-identical.
6. **No new third-party dependency.** `zipfile`, `json`, `csv` are stdlib; everything else is
   already in `pyproject.toml`.
7. **Gap A independence.** No phase references `bars` as a precondition. A symbol with zero bars
   must still get fundamentals.
8. **Every write goes through `db.transaction`** and honours `--dry-run` by running every
   statement and rolling back.

## Phases

| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID | Card |
|---|-------|-----------|---------|-------|-----------|------------|------|--------|------|
| 1 | Vendored ticker→CIK map and loader | R1 | `engine/data`, `seer_engine` | 5 | — | NORMAL | `.workflows/plan/edgar-fundamentals/phase-1.md` | — | — |
| 2 | Schema: `ticker_cik`, `fundamental_facts`, `fundamentals_log` | R4 | `db/migrations` | 2 | — | EASY | `.workflows/plan/edgar-fundamentals/phase-2.md` | — | — |
| 3 | SEC client (`sec.py`) and `SEC_CONTACT_EMAIL` | R2, R5 | `seer_engine` | 3 | — | NORMAL | `.workflows/plan/edgar-fundamentals/phase-3.md` | — | — |
| 4 | `fundamentals` command — resumable ingest | R1, R2, R5 | `seer_engine.commands` | 2 | 1, 2, 3, 5 | HARD | `.workflows/plan/edgar-fundamentals/phase-4.md` | — | — |
| 5 | Pure derivation: concept ladder, PIT selection, SUE | R3 | `seer_engine.fundamentals` | 6 | 2 | HARD | `.workflows/plan/edgar-fundamentals/phase-5.md` | — | — |
| 6 | `Market.fundamentals` + the `MarketAware` hook | R6 | `seer_engine.backtest`, `seer_engine.strategies`, `seer_engine.research` | 11 | 2, 5 | HARD | `.workflows/plan/edgar-fundamentals/phase-6.md` | — | — |
| 7 | Fundamental factor allocator, lab method, runbook | R6 | `seer_engine.strategies`, `seer_engine.lab`, `docs` | 5 | 5, 6 | NORMAL | `.workflows/plan/edgar-fundamentals/phase-7.md` | — | — |

Waves the `Depends on` column implies: **{1, 2, 3} → {5} → {4, 6} → {7}**.

File counts corrected in reconciliation: **1** 4→5 (`engine/scripts/build_ticker_cik.py`, a new
directory `ruff check engine` lints); **3** 4→3 (`config.py` is not edited — it exposes no named
accessors, so `sec.require_contact()` is the local accessor, as `finnhub.load_key` is);
**4** 3→2 (it defines no `INGEST_TAGS`, so its only files are the command module and its test);
**5** 5→6 (the `test_strategy_purity.py` glob extension it owns); **6** 6→11 (the research store
and the two `paper/` `Market` rebuilds, both assigned here).

**Phases 1 and 4 must both land before `python -m seer_engine fundamentals` exits 0.** Phase 4
classifies a symbol missing from the map as `failed`, deliberately, so that phase 1's coverage
criterion is machine-checkable. Neither phase's own `pytest engine/tests -q` depends on the
other. Both plans carry the note.

### Phase 1 — Vendored ticker→CIK map and loader
**Satisfies:** R1
**Owns:** `engine/data/ticker_cik.csv` (the data, generated once and committed), its
documentation block in `engine/data/SOURCES.md`, a new `seer_engine/cik.py` loader validating it
in the style of `membership.load_aliases`, and `engine/tests/test_cik.py`.
**Owns, also:** `engine/scripts/build_ticker_cik.py`, the committed one-off generator (a new
directory, linted by `ruff check engine`).
**Does not touch:** the database and the `ticker_cik` **table** (phase 2 declares it, phase 4
writes it), the SEC client, any command, `.env.example`.
**Exit criteria:** the CSV covers every ever-member the scope predicate selects (**795** on
2026-10-05; the tests derive the set from `membership.symbols_since(...)` and never assert a
literal count) with explicit validity intervals; the loader rejects a bad header, an overlapping
interval for one ticker, and a CIK that is not 10 digits; a test asserts that each of CA, MON,
PLL, ALTR, LLL and DTV resolves to the company that held the ticker during its S&P/NDX
membership and **not** to the current holder; Kellanova resolves to `0000055067`, and a test
pins that `0000039899` (TEGNA) is **not** it.

### Phase 2 — Schema
**Satisfies:** R4
**Owns:** `db/migrations/005_fundamentals.sql`, and the two `test_migrate.py` assertions that
assume 004 is the last migration (`:300` and `:318`, repointed at
`_upto(tmp_path, "004_news_veto.sql")`) plus the new 005 block. **No other phase touches
`engine/tests/test_migrate.py`.**
**Does not touch:** any `engine/src` Python; `docs/runbooks/data-pipeline.md` (phase 7 owns it
entirely — the runbook has no schema-list section to add a row to).
**Exit criteria:** `migrate` applies it cleanly and is idempotent; `fundamental_facts`'s primary
key is `(cik, taxonomy, tag, unit, period_start, period_end, accn)` — `accn` so a restatement
inserts rather than overwrites, `period_start` so a 10-K's Q4 figure cannot collide with its
full-year figure; `period_start` is `NOT NULL` with `period_start = period_end` meaning
*instantaneous*; `fundamentals_log` mirrors `backfill_log`'s shape but is keyed by **`cik`**
(invariant 4); `ticker_cik.source`'s CHECK matches phase 1's tier labels; every table is
additive (`CREATE TABLE IF NOT EXISTS`) in the style of `002_engine.sql`; `test_migrate.py` is
green.

### Phase 3 — SEC client
**Satisfies:** R2, R5
**Owns:** `seer_engine/sec.py`, the `SEC_CONTACT_EMAIL` key in `.env.example` (the **only**
phase that edits that file), and `engine/tests/test_sec.py`. `config.py` is **not** edited:
it exposes no named accessors, so `sec.require_contact()` is the local accessor, exactly as
`finnhub.load_key` is.
**Does not touch:** `http.py`'s module-level session (Massive and Finnhub must not inherit the
contact User-Agent), the database, the command module.
**Exit criteria:** the client fetches `companyfacts/CIK##########.json`, enforces ≤ 10 req/s from
the end of the previous call, sends a `User-Agent` carrying `SEC_CONTACT_EMAIL`, retries 429/5xx
with backoff honouring `Retry-After`, raises a typed error otherwise, and takes an injectable
transport/clock/sleep so tests never touch the network.

### Phase 4 — `fundamentals` command
**Satisfies:** R1 (the `ticker_cik` table writer), R2, R5
**Owns:** `seer_engine/commands/fundamentals.py` and `engine/tests/test_fundamentals_command.py`,
including `sync_ticker_cik` — the one writer of the `ticker_cik` **table** from phase 1's CSV.
**Does not touch:** `cli.py` (discovery is automatic), the backtest, `engine/data/*`,
`db/migrations/*`, the runbook. It **imports** the ingest tag allowlist as
`fundamentals.ladder.LADDER_TAGS` from phase 5's pure package — it defines no list of its own —
and derives nothing itself.
**Exit criteria:** `python -m seer_engine fundamentals` loads facts for every ever-member the
scope predicate selects (795 on 2026-10-05, SPY excluded), resolved through phase 1's map by
**date**; writes facts and `fundamentals_log` rows in one transaction per batch. **The unit of
work is the CIK, not the symbol**: `plan_jobs` resolves every in-scope symbol first, groups
them by CIK, and skips the CIKs already logged, so a share-class pair (GOOG/GOOGL) is one
`companyfacts` call, one log row and one `rows` count — but **both** symbols still appear in
the summary, because `CikResult.per_symbol()` fans the outcome back out. `batch_size` counts
CIKs. `--symbols` is still deduped to CIKs but ignores the log outright; `--retry-failed`
re-attempts `failed` and `empty` CIKs; `--dry-run` rolls everything back. `Summary.exit_code`
is **unchanged** from `backfill`'s: 0 when nothing `failed`, 1 on any failure, 2 on a missing
setting or an empty universe — an `empty` filer is not an error. A symbol with **no** CIK (the
map has no row, or marks it `NONE`) gets **no log row at all**, because the table's primary key
is a bigint CIK; it is therefore re-evaluated every run. **A symbol missing from the map is
`failed` by design**, so an incomplete CSV exits 1 — see the landing-order note above; a symbol
the map marks `NONE` is `empty` and exits 0.

### Phase 5 — Pure derivation
**Satisfies:** R3
**Owns:** `seer_engine/fundamentals/` (`__init__.py`, `ladder.py`, `panel.py`, `sue.py`),
`engine/tests/test_fundamentals_derive.py`, and the additive extension of
`engine/tests/test_strategy_purity.py`'s glob to cover the new package. **It is the sole owner
of that shared test file**; phase 6 must leave it byte-identical to what this phase leaves.
It also owns `ladder.LADDER_TAGS`, which phase 4 imports as the ingest allowlist — so a rung
added here later costs a full re-ingest, and `ladder.py`'s docstring must say so.
**Does not touch:** the database, the network, `Market`, any allocator.
**Exit criteria:** the concept ladder reproduces the measured coverage over the 8 sampled filers
(revenue 2 variants; net income, assets, equity, OCF, diluted EPS, shares outstanding 1 each;
operating income missing for SIVB and PXD; gross profit present for only CELG and WRK, derived as
`Revenues − CostOfRevenue` elsewhere with the fallback documented in the module docstring);
point-in-time selection returns the latest fact with `filed <= t` and a test proves it on a real
restatement; SUE is the seasonal random walk `EPS_q − EPS_{q−4}` scaled by the dispersion of
recent surprises, with the minimum history it needs stated and enforced.

### Phase 6 — `Market.fundamentals` and the allocator hook
**Satisfies:** R6
**Owns:** the new `fundamentals` field on `Market`, the panel load in `backtest/io.py` (cached
by table fingerprint like `bars`, reading `fundamental_facts` **joined to `ticker_cik`** because
facts are CIK-keyed and the panel is symbol-keyed), the `MarketAware` protocol + `prepare_for`
helper, the single real call site `dev.py:455`, the two docstrings at `runner.py:143` and
`walkforward.py:200`, **every other place a `Market` is constructed and would silently drop the
new field** (`dev.py:367`, `research.py:472`, `paper/replay.py:281`, `commands/paper.py:254`) —
including the research store's **optional** `fundamentals.csv` artifact (`research.py`,
`commands/research_store.py` + a new `--with-fundamentals` flag), without which the lab sees an
empty panel — and `engine/tests/test_market_fundamentals.py`.
**Does not touch:** the existing allocators' behaviour — every one of them must keep working
through `prepare(history)` unchanged; `Allocator`'s member set, which must not gain
`prepare_market` (measured: `runtime_checkable` `isinstance` would then be False for every
structural implementer, breaking eight production sites); `test_strategy_purity.py`;
`test_lab_methods.py`; **`research.DATA_FILES`** and **`engine/tests/test_research_store.py`**
— the new store file is optional, carried in `OPTIONAL_DATA_FILES`, precisely so that neither
has to change and no store on disk stops loading.
**Exit criteria:** `Market` stays frozen and pure; `load_market` returns a panel and still works
against a database with **neither** `fundamental_facts` nor `ticker_cik`; `isinstance(x,
Allocator)` is still True for all eleven existing implementers; `test_strategy_purity.py` is
byte-identical to what phase 5 left and so is `test_research_store.py`; a store rebuilt with
`--with-fundamentals` carries a panel equal to `io.load_panel(conn)`'s, and **a store built
before this phase still loads with the same fingerprint `origin/main` computes for it** (the
check is in the plan's Verification); every existing backtest produces byte-identical output to
`origin/main` for one pinned candidate.

### Phase 7 — Factor allocator, lab method, runbook
**Satisfies:** R6
**Owns:** `seer_engine/strategies/f_fundamental.py`, a lab method
`seer_engine/lab/methods/m0005_<slug>.py`, the `fundamentals` rows in
`docs/runbooks/data-pipeline.md`, and `engine/tests/test_f_fundamental.py`.
**Owns, also:** the one branch added to `engine/tests/test_lab_methods.py:85–93` — **no other
phase touches that file.**
**Does not touch:** `f_factor.py`; `seer_engine/fundamentals/*`; `backtest/*`;
`strategies/allocator.py`; `seer_engine/research.py` (phase 6 owns the research store).
**Exit criteria:** the allocator ranks on value, quality, profitability and SUE with eligibility
rules in the style of `f_factor`, reading phase 5's **annual** flows through one
`panel.as_of(symbol, t)` call per symbol; it implements phase 6's `MarketAware` by defining
`prepare_market` and does **not** widen `Allocator`; its id (`FND`) is unique across lab
methods; the method declares 6 fixed variants, and the **SUE-free** ones pass a hermetic
end-to-end dev-window test over a **real** `FundamentalPanel` while the SUE-ranking ones (which
include both composites — `rank="composite"` reads every factor) are held to the criterion a
synthetic annual panel can actually meet: they rank nobody and raise nothing, because
`Snapshot.sue` is NaN without a quarterly EPS series. **`lab run M0005` is NOT executed by this
phase** — `runner.preflight` refuses a second run of any method, so one premature run against a
store without fundamentals would record all-cash trials and burn the method id permanently; the
warning goes in the method docstring and the runbook. The runbook documents the command, its exit
codes and how to re-vendor `ticker_cik.csv`.

## Reconciliation Log

Round 1. 24 conflicts found, 24 resolved, 0 deferred. Every row was fixed by **editing the
losing plan file**, not by annotating it.

| # | Class | Conflict | Resolution (and which plan file was edited) |
|---|---|---|---|
| 1 | Contract drift | Phase 6's `requires` assumed `fundamental_facts(symbol, …)`; phases 2 and 4 key it on `cik` | **Phase 2 owns the schema and wins.** Phase 6's `FACTS_COPY_SQL` rewritten to `JOIN ticker_cik` and project `m.symbol`; the "swap for A1-mismatch" block promoted to the primary SQL; `MAP_TABLE` added; phase-6 test fixtures rewritten to CIK-keyed rows plus a `ticker_cik` seed. **phase-6.md** |
| 2 | Broken-build / cache correctness | The CIK→symbol join fans a share-class CIK out to two symbols, so a fingerprint over `fundamental_facts` alone would never invalidate on a `ticker_cik` change and `len(frame) != rows` would fire every load | `facts_fingerprint` now counts over the **same join**, and checks both tables with `to_regclass`. Two new tests: the fan-out, and re-vendoring the map busting the pickle. **phase-6.md**, contract text in **phase-2.md** |
| 3 | Contract drift | Phase 6 assumed `period_start` nullable; phases 2 and 4 converged on `NOT NULL` with `period_start = period_end` meaning instantaneous | **Phases 2/4 win** (a nullable column cannot sit in a PK and the period must be keyed). Phase 6's COPY emits `''` for the equality; `facts_from_frame` is unchanged. **phase-6.md** |
| 4 | Contract drift | Phase 5 assumed the same nullable `period_start` | `fact_from_row` now maps `period_start == period_end` → `None` at the one DB-row boundary; `Fact.period_start` stays `date | None` in memory, so all 39 of phase 5's tests stand. **phase-5.md** |
| 5 | Contract drift | Phase 5's `FACT_COLUMNS` order (`… accn, form, fy, fp, filed`) vs phase 6's `FACTS_COLUMNS` (`… accn, fy, fp, form, filed`) — a silent three-column mis-assignment | **Phase 5 owns the order.** Phase 6 now imports it (`FACTS_COLUMNS = FACT_COLUMNS`) instead of restating it; the COPY projection and the `facts_from_frame` unpack follow it. **phase-6.md** |
| 6 | Contract drift | Phase 5's assumed table had a `symbol` column | Corrected: the table has none; phase 6's join supplies it. `FACT_COLUMNS` is documented as a contract with **phase 6's projection**, not with the table. **phase-5.md** |
| 7 | Unmet assumption | Phase 7 assumed `flow_ttm / stock_asof / filed_asof / sue_asof`; none exist | **Phase 5 wins** (executed code, 39 passing tests). Phase 7's `Panel` Protocol collapsed to one method, `as_of(symbol, t) -> Snapshot \| None`; a `Snapshot` Protocol added; `_row` and `fundamental_rows` rewritten to one snapshot per symbol; `EmptyPanel` and `FakePanel` rewritten. **phase-7.md** |
| 8 | Contract drift | Phase 7 expected TTM flows; phase 5 deliberately ships **annual** | **Phase 5 wins** (annual coverage is 8/8; TTM would put a systematic wedge through the cross-section). Phase 7's formula block, `_row` and two variant descriptions restated on an annual basis. **phase-7.md** |
| 9 | Contract drift | Phase 7's A5 had `prepare_market` as an `Allocator` member | **Phase 6 wins** — it *measured* that adding a member to the `runtime_checkable` `Allocator` makes `isinstance` False for every structural implementer, breaking eight sites. Phase 7 now implements `MarketAware`; a test asserts `"prepare_market" not in Allocator.__protocol_attrs__`. **phase-7.md** |
| 10 | Duplicate concept | Phase 7's invented `uses_fundamentals` marker duplicated `MarketAware` | Marker **deleted**; the shared lab gate branches on `isinstance(c.allocator, MarketAware)`. One source of truth, and it is the one `dev.py` dispatches on. **phase-7.md** |
| 11 | Broken test | Phase 7's tests pass a `FakePanel` into `Market(...)`, which phase 6 type-checks | Split: `FakePanel` for the pure functions, a real `FundamentalPanel.from_facts(...)` (new `real_panel` helper + `real_panel_fx` fixture) for the three `Market`-constructing tests. The dev-window run drops to non-SUE variants, since phase 5's SUE needs a quarterly EPS series a synthetic panel lacks — stated, not hidden. **phase-7.md** |
| 12 | Gap | The research store carries no fundamentals, so a lab run would rank nothing — flagged by phases 6 and 7, owned by neither | Assigned to **phase 6** as its Step 7 (`research.py`, `commands/research_store.py`). Phase 6's H1 and phase 7's H1 rewritten from "decision needed" to "resolved". Fingerprint worry answered: `runner.preflight` keys on `method_id`+`config_digest`, so no run method is blocked. **phase-6.md**, **phase-7.md** |
| 13 | Gap | `paper/replay.py:281` and `commands/paper.py:254` rebuild a `Market` and would drop the panel — phase 6 left them as H2 | Assigned to **phase 6** as its Step 8 (one `replace(...)` line each). `paper/store.py:1035` stays out: it constructs rather than rebuilds. **phase-6.md** |
| 14 | Duplicate work | Phase 4 defined `INGEST_TAGS`; the index puts the allowlist in phase 5's `ladder.LADDER_TAGS` | Phase 4's list **deleted** and replaced with the import; `select_facts` and two tests repointed; its H2 rewritten as resolved. Phase 4 gains a dependency on phase 5. **phase-4.md**, contract note in **phase-5.md** |
| 15 | Ordering violation | Phase 4's `Depends on` omitted phase 5 | Added. Waves confirmed `{1,2,3} → {5} → {4,6} → {7}`. **phase-4.md**, index |
| 16 | Scope loss | Two tags in phase 4's draft list (`Liabilities`, `EarningsPerShareBasic`) are not ladder rungs | Dropped, with the reason recorded in both plans: nothing reads them and every stored tag costs rows on a 0.5 GB tier. **phase-4.md**, **phase-5.md** |
| 17 | Contract drift | Phase 4 assumed `fundamentals_log(symbol PK, cik, first_date, last_date)` | **Phase 2 wins** (invariant 4). `_LOG_UPSERT` rekeyed to `cik` with `first_filed`/`last_filed`; `_write_batch` and the test helper rewritten. **The resume rule changes with it** — it now dedupes to CIKs before fetching, so GOOG/GOOGL is one fetch and one row; two tests added for that. **phase-4.md** |
| 18 | Contract drift | Phase 4 wrote a `frame` column and `cik text`; phase 2 has no `frame` and `cik bigint` | `_FACTS_COPY`/`_FACTS_UPSERT` cut to twelve columns; `upsert_facts` takes an `int` CIK. **phase-4.md** |
| 19 | Contract drift | Phase 4's assumed `sec.Fact(start, end, …)` with no `cik`; phase 3 ships `cik, period_start, period_end` and returns a `CompanyFacts` | **Phase 3 wins** (it owns `sec.py`). Phase 4's `_period_start`, `select_facts`, `upsert_facts`, `FactsSource` and the test fact factory rewritten. **phase-4.md**, cross-note in **phase-3.md** |
| 20 | Contract drift | Phase 4's assumed `cik.load_map` / `.ticker` / `.company`; phase 1 ships `load_ticker_cik` / `.symbol` / `.company_name` | **Phase 1 wins** (it owns `cik.py`). `load_cik_map`, `resolve_cik`, `resolve_window_cik`, `sync_ticker_cik` rewritten. **phase-4.md** |
| 21 | Gap | Phase 1's CSV `cik` sentinel `NONE` has no representation in phase 2's `NOT NULL bigint` column, and no phase handled it | Settled: `sync_ticker_cik` **skips** `NONE` rows; `resolve_window_cik` returns `empty` for them, not `failed`. Mapping table added to phase 1; Decisions row added. **phase-1.md**, **phase-4.md**, **phase-2.md** |
| 22 | Contract drift | Phase 1's `source` labels (`current, edgar, exact, fuzzy, manual`) vs phase 2's CHECK (`company_tickers, cik_lookup, fuzzy, manual`) | **Phase 1's data wins**, per phase 2's own "widen the CHECK rather than rename phase 1's data" rule. CHECK widened. **phase-2.md** |
| 23 | Stale measurement | 819 ever-members in phases 2, 3, 4, 5, 6 | Corrected to **795** everywhere (phase 1 measured it; `663 ok + 133 empty + SPY = 796`). No plan hardcodes the count in code — the scope is a SQL predicate. **phase-2/3/4/5/6.md** |
| 24 | Contract drift | Phase 2 claimed "its note in the runbook's schema list"; phase 2's plan hands the runbook entirely to phase 7 | Index corrected to match the plan. `docs/runbooks/data-pipeline.md` has exactly one owner: **phase 7**. index |

**Shared-file ownership, verified after the edits — each has exactly one writer:**

| File | Owner | Checked against |
|---|---|---|
| `engine/tests/test_migrate.py` | phase 2 | 1, 3, 4, 5, 6, 7 — none mentions it |
| `engine/tests/test_strategy_purity.py` | phase 5 | 3, 4, 6, 7 reference it; none edits it. Phase 6's exit criterion is "byte-identical to what phase 5 left" |
| `engine/tests/test_lab_methods.py` | phase 7 | phase 6 cites `:42,83-84` as evidence for the `runtime_checkable` measurement and edits nothing |
| `docs/runbooks/data-pipeline.md` | phase 7 | 2 hands it over explicitly; 1, 3, 4 state they do not touch it |
| `engine/data/SOURCES.md` | phase 1 | 2 leaves it alone; 7 points at it |
| `.env.example` | phase 3 | 1 reads `SEC_CONTACT_EMAIL` from `os.environ`/`--contact` and does not edit the file |
| `engine/src/seer_engine/config.py` | **nobody** | phase 3 measured that no named accessor exists to add one to |
| every `Market(...)` construction site | phase 6 | 7 constructs one only in its own test module |

**Build-green check, per phase, after the edits.** Each leaves `pytest engine/tests -q` green on
its own: 1 (new module + new test, no shared edit); 2 (migration + its own `test_migrate.py`
fix, which is required or the tree is red); 3 (new module, new test, `.env.example`); 4 (new
command + test; imports phase 5, which lands first); 5 (new package, new test, additive purity
glob); 6 (additive field with a default, so no construction site breaks; `to_regclass` guards
make it green against a database with neither new table); 7 (new allocator + method + test, and
one *tightening* branch in `test_lab_methods.py` that no existing method takes).

**Impact-point coverage.** All 16 rows of the analysis's Impact Points table are owned, and
row 12's parenthetical (`dev.py:367`, `research.py:472`, `paper/replay.py:281`,
`commands/paper.py:254`) is now owned in full by phase 6 rather than half-owned. No
reference-list entry is unowned.

### Round 2 — the verify pass

Round 1 reported `contract_changed: true`. Round 2 re-read the ledger against the edited plans
and found **11 conflicts, all of them created or left behind by round 1's own rewrites**. Every
one is resolved by editing the plan file; none is deferred. The pattern is uniform and worth
naming: round 1 rewrote **contract prose** and left the **code blocks and test blocks** that
implement it on the old contract. Rows 25–29 are one instance of that in phase 4, rows 32–34
another in phase 6.

| # | Class | Conflict | Resolution (and which plan file was edited) |
|---|---|---|---|
| 25 | Broken build | Phase 4's C2 rewrote the resume rule to dedupe by CIK, but **Step 6's code was never rewritten**: `_logged_statuses` still ran `SELECT symbol, status FROM fundamentals_log` — a column phase 2 does not have | Step 6 replaced: `select_symbols` now only answers "what is in scope", and a new **`plan_jobs`** resolves every symbol to a CIK, groups symbols by CIK, consults the log **by `cik`**, and returns `(jobs, unresolved, skipped)`. `_logged_statuses` rekeyed to `cik = ANY(...)` with `int()`/`sec.cik10()` at the boundary. **phase-4.md** |
| 26 | Contract drift | Phase 4's Step 9 `_ingest_facts` still iterated **symbols** and called `fetch_symbol` per symbol, so GOOG and GOOGL were two fetches — while `_write_batch`'s own docstring asserted "`results` is already deduplicated to one entry per CIK by `ingest`", which nothing did | The unit of work is now the CIK throughout: new `CikJob` and `CikResult` dataclasses (Step 3), `fetch_symbol` **deleted** and replaced by `fetch_cik`, `_ingest_facts` loops over jobs, and `CikResult.per_symbol()` is the single fan-out point back to symbols. `Summary` gains `ciks_fetched`; `facts_fetched` accumulates per CIK so a share-class pair is not double-counted. **phase-4.md** |
| 27 | Contract drift | Phase 4's C4 says `company_facts` returns a `CompanyFacts` and that `fetch_symbol` reads `.facts` off it; Step 7's code did `select_facts(source.company_facts(number), …)`, iterating an object with no `__iter__` | `fetch_cik` reads `response.facts`. The `FakeSec` in Step 11 now returns a real `sec.CompanyFacts` too — it previously returned a `list`, which would have made the whole test module pass against a client the shipped code cannot use. `sec.SecNotFound → empty` also written out as its own branch (C4 states it; the broad handler was swallowing it into `failed`, which changes the exit code). **phase-4.md** |
| 28 | Broken build | Phase 4's Step 11 test module was entirely on the old model: the `Mapping` fake had `.ticker`/`.company` (phase 1 ships `.symbol`/`.company_name`, C5) and no `.source`; `CIK_10` was referenced and never defined; `ladder` was used unimported; `log_rows` was keyed by symbol; two fixtures ran `INSERT INTO fundamentals_log (symbol, …)`; `resolve_window_cik` was unpacked as a 2-tuple when Step 5 returns 3 | Whole module corrected. `Mapping` now mirrors `cik.CikRow` field for field; `CIK_10` defined; `ladder` imported locally; `log_rows` keyed by `cik10`; both log fixtures rewritten to `(cik, status, "rows")`; every `resolve_window_cik` call unpacked as `(cik, status, error)`. **phase-4.md** |
| 29 | Gap | C2 promised "two tests" for the fan-out and round 1 added none | Four added: one CIK / one fetch / one log row / un-doubled `rows` for GOOG+GOOGL with **both** symbols reported; a second run skipping that CIK for both, and `--symbols GOOG` alone fetching once and reporting one; `NONE` → `empty` with **no** log row; an unmapped symbol → `failed` with no log row and re-attempted every run. Test count in the Files table 18 → 22. **phase-4.md** |
| 30 | Contract drift | Phase 4's exit criterion 1 still said "leaves **every ever-member** with a `fundamentals_log` row" — impossible once the log is CIK-keyed: a symbol with no CIK has no row, and a share-class pair shares one | Criterion rewritten to the checkable form: one row per **distinct CIK**, equal to `count(distinct cik)` over the in-scope `ticker_cik` rows, with `NONE` and unresolvable symbols explicitly rowless. The runbook rows phase 4 hands to phase 7 were corrected to match, and phase 7's copy of them with them. **phase-4.md**, **phase-7.md**, index |
| 31 | Contract drift | Phase 2's `source` CHECK was widened to phase 1's five labels in round 1 (row 22), but phase 2's **own test fixtures** still passed `source="cik_lookup"` (the `_bridge` default, so every call) and `source="company_tickers"` — both now outside the CHECK, so two 005 tests would raise `CheckViolation` on the first insert. Phase 2's Handoffs still advertised the retired vocabulary, and phase 1's Handoff still told phase 2 to use `cik char(10)` and `company_name` | Fixtures repointed to `exact` and `current`; both stale Handoff paragraphs rewritten to the settled contract, with the old→new label mapping recorded so an earlier draft is still readable. **phase-2.md**, **phase-1.md** |
| 32 | **Broken build, highest severity** | Phase 6's Step 7 said `fundamentals.csv` is "added to `DATA_FILES`" **and** that "an existing store built before this phase still loads". Measured against the shipped code, those are mutually exclusive: `research._read_manifest` raises unless `set(files) == set(DATA_FILES)` (`research.py:524-529`) and `load_store` hashes `for name in DATA_FILES` with `file_sha256` raising on a missing file (`:441-443`, `:192-194`). Widening it makes **every research store on disk unloadable** — not a changed fingerprint, a hard `ValueError` — including the one this phase's own byte-identical verification points both checkouts at | `fundamentals.csv` made an **optional** store file: a new `OPTIONAL_DATA_FILES`, `DATA_FILES` untouched, `_read_manifest`'s check relaxed to `DATA_FILES ⊆ files ⊆ DATA_FILES ∪ OPTIONAL`, `load_store` hashing the manifest's own keys, `_seal(extra_files=…)`, and `build_store(facts=None)` defaulting to today's behaviour exactly. Consequences, all verified: an old store's fingerprint is **bit-identical**, so no recorded trial is invalidated; `engine/tests/test_research_store.py` stays byte-identical and green (no build in it passes `facts`); `MANIFEST_KEYS` is unchanged, so its whole-set assertion at `:233` still holds. **phase-6.md**, index |
| 33 | **Silent data corruption** | Phase 6's Step 7 said the store reader is "a straight `fact_from_row` over `csv.DictReader`". It cannot be. The CSV is written from `FACTS_COPY_SQL`, whose instant marker is `''`, and `DictReader` yields strings; phase 5's `fact_from_row` takes **typed** values and `Fact.__post_init__` rejects `'2015-12-31'`. Every row would raise, and `facts_from_rows(skip_invalid=True)` would **drop all of them and return an empty panel with no error** — reintroducing, one layer down, exactly the silent all-cash-trials failure Step 7 exists to prevent | `_read_fundamentals` written out in full, reading the CSV with `pd.read_csv(na_filter=False)` and routing it through **`io.facts_from_frame`** — the one function in the tree that turns that text back into `Fact`s, so the store-backed panel and the DB-backed panel are identical by construction. A round-trip test asserts `data.market.fundamentals == Panel.from_facts(facts)` and that the instant marker survives as `None`. **phase-6.md** |
| 34 | Contract drift | Phase 6's Step 8 claimed two one-line `paper/` fixes and quoted neither correctly: it wrote `run_market = replace(market, fx=fx_rows)` where the tree has `fixed = Market(history=market.history, membership=market.membership, fx=((start, head.usd_idr),))` at `paper/replay.py:281`, and `run_market = replace(market, history=history, fx=fx_rows)` where `commands/paper.py:254` has `return Market(history=history, membership=market.membership, fx=fx)` | Both quoted from the tree, before and after. They **are** genuinely one line each, as claimed — `membership` drops out of the call precisely because `replace` carries it. **phase-6.md** |
| 35 | Duplicate concept | Phase 7's `f_fundamental.py` defined its own `class EmptyPanel` / `EMPTY_PANEL` — a **third** object meaning "no fundamentals", after phase 5's `EMPTY_PANEL` and phase 6's `EMPTY_FUNDAMENTALS` (which is phase 5's). Its test `assert prepare_market(m).panel is EMPTY_PANEL` would then be **False** for a `Market` built without a panel, which after phase 6 is every `Market` in the tree until a store is rebuilt | `EmptyPanel` **deleted**; `f_fundamental.py` imports `EMPTY_PANEL` from `seer_engine.fundamentals` (pure, so the purity gate stays green — the same import `backtest/market.py` makes). One object, one identity, and the test is true by construction. The `prepare_market` docstring's "`fundamentals` absent or None" reworded: after phase 6 it is never either. **phase-7.md** |

**Round 2's smaller corrections, applied without a log row each** (each is a one-line
inconsistency with a round-1 decision, not a fork): phase 7's "four quarters of flows" → one
**annual** flow (decision 4 says annual); phase 7's `FakePanel` partial-snapshot fixture, which
omitted four `FakeSnapshot` fields that have no defaults (`TypeError`, not a partial snapshot);
phase 7's stale counts of `Market`-constructing tests (three/two → four); phase 7's two claims
that "the research store carries no fundamentals today", now false in phase 6 and replaced with
the *correct* gate ("does this store's manifest list `fundamentals.csv`") while keeping the
standing do-not-run directive; phase 7's Modifies block, which omitted the runbook; phase 4's
Step 1 imports, missing `Collection` and `CompanyFacts` used in Step 2's annotations; phase 6's
"six source files" in its manual check, now ten.

**One conflict found and resolved in phase 7's own test design, worth reading before executing
it:** the dev-window test was parametrised over **all six** M0005 variants while its own
docstring said "the four non-SUE variants". Both were wrong. A synthetic annual panel has no
quarterly EPS series, so `Snapshot.sue` is NaN; `fundamental_rows` drops a row whose wanted
factor is non-finite; and `rank="composite"` reads **every** factor — so **three** variants
(`sue` and both composites) would have ranked nobody and tripped `assert trades > 0`. The
parametrisation is now **computed** (`SUE_FREE = [c for c in METHOD.candidates if "sue" not in
factors_read(c.params)]`) rather than hand-listed, and the SUE-ranking variants get their own
test holding them to the criterion they can actually meet: rank nobody, raise nothing. The
index's phase-7 exit criterion was rewritten to match; as it stood ("Every M0005 variant …
trades") it was unachievable.

**Re-verified after round 2's edits, with nothing outstanding:**

- **`FACT_COLUMNS` / `FACTS_COLUMNS`** — one definition (phase 5's `panel.FACT_COLUMNS`), one
  re-export (phase 6's `FACTS_COLUMNS = FACT_COLUMNS`). No third copy anywhere, and no
  surviving `accn, fy, fp, form` ordering: the only two mentions of it in phase 6 say "the
  original draft had". Phase 6's test `INSERT` uses the **table**'s column list, named
  explicitly, which is a different tuple and correctly so. Phase 2's
  `FUNDAMENTAL_FACTS_COLUMNS` matches its own DDL.
- **`period_start = period_end` ⇒ instantaneous** — the round trip is consistent at all four
  boundaries now. Phase 4 writes the equality (`_period_start`); phase 6's COPY emits `''`;
  phase 6's `facts_from_frame` maps `''` → `None`; phase 5's `fact_from_row` maps
  `date == date` → `None` for callers handing it raw psycopg rows. The fifth boundary — the
  research-store CSV — was the one that did **not** round-trip and is row 33 above; it now
  goes through `facts_from_frame` like the other text path.
- **`ladder.LADDER_TAGS`** — defined once, in phase 5. Phase 4 imports it and has no surviving
  `INGEST_TAGS`. The two dropped tags (`us-gaap:Liabilities`, `us-gaap:EarningsPerShareBasic`)
  appear nowhere as live code; the single `"Liabilities"` hit in phase 3 is a deliberately
  malformed `units` node in a parser test, not an allowlist.
- **`MarketAware` / `prepare_for`** — defined once, in phase 6. Phase 7 implements
  `prepare_market` structurally, imports `MarketAware` for one assertion, and has no surviving
  `uses_fundamentals` marker as live code. `Allocator`'s member set is genuinely unchanged:
  phase 7 never redefines the protocol, and its test asserts
  `"prepare_market" not in Allocator.__protocol_attrs__`.
- **Shared-file ownership** — unchanged from round 1 and re-checked file by file:
  `test_migrate.py` (2), `test_strategy_purity.py` (5), `test_lab_methods.py` (7),
  `SOURCES.md` (1), `.env.example` (3), `docs/runbooks/data-pipeline.md` (7). Round 2 adds one
  row: **`engine/tests/test_research_store.py` has no owner, and after row 32 it needs none.**
- **File counts** — index vs each plan's Files table: 1→5 ✓, 2→2 ✓, 3→3 ✓ (its table has four
  rows, one of which is `config.py` marked **no change**), 4→2 ✓, 5→6 ✓, 6→11 ✓, 7→5 ✓.
- **Requirement map** — unchanged by round 2. No step moved between phases, so no `R` moved.

## Decisions

| Fork | Chosen | Rung |
|---|---|---|
| Bulk `companyfacts.zip` (1.41 GB) vs per-CIK `companyfacts` API | **per-CIK API**; the zip documented as the fallback for a full-market expansion | 5: user's raw input offers both — scope is 795 filers not 10,000, SEC's 10 req/s makes it ~82 s, and per-symbol fetch is what gives R5's `backfill_log`-style resumability |
| Widen `Allocator.prepare(history)` vs add an optional `prepare_market(market)` | **add `prepare_market`**; `prepare` untouched | 6: surrounding convention — widening edits 11 implementers, and `params` cannot carry the panel because `lab/method.config_text` canonicalises it into the trial digest |
| Materialise derived metrics in SQL vs derive in pure Python at load | **store raw facts, derive in pure Python** | 6: surrounding convention — `bars` are stored raw and `indicators` derive in pure code; the ladder stays versionable and testable without a re-ingest |
| `fundamental_facts` PK with or without `accn` | **with `accn`** | 5: user's raw input — "restatements … must stay queryable rather than being overwritten" |
| Ingest all 1,265 `universe` symbols vs the 795 ever-members since 2015-01-02 | **795** | 5: user's raw input ("all 795 ever-members") plus XBRL coverage starting 2009 |
| `ticker_cik.csv` as a bare pair vs with a validity interval | **validity interval** | 5: user's raw input, marked CRITICAL — recycled tickers (CA, MON, PLL, ALTR, LLL, DTV) |
| SEC contact address hardcoded vs a setting | **`SEC_CONTACT_EMAIL` setting**, required by the `fundamentals` command only | 6: surrounding convention — `massive.py` and `finnhub.py` each require their own key via `config.require`, raising `ConfigError` |
| Who owns the ingest tag allowlist, and may phase 4 ingest every tag | **the allowlist lives in phase 5's pure `fundamentals/ladder.py`; phase 4 imports it and gains a dependency on 5** | 1: invariant 5 (purity) — the list must sit in a module both can read, and impure-imports-pure is the only legal direction. Ingesting every tag was measured by phases 2 and 4 at 50-100x the size budget against a 0.5 GB tier already holding 177 MB of bars |
| `fundamentals_log` keyed by `symbol` (phase 4) vs by `cik` (phase 2) | **`cik`**; the command's summary reports per symbol by joining `ticker_cik` | 1: invariant 4 ("a ticker alone never identifies a company") — one CIK backs several tickers (GOOG/GOOGL, LMCA/LMCK, CMCSK) so symbol-keying double-counts `rows`, and one ticker maps to several CIKs over time (ARNC is the documented in-tree case) so one row would carry two companies' outcomes |
| Who writes `ticker_cik` the table from `ticker_cik.csv` | **phase 4**, via `sync_ticker_cik` with `--no-sync-map`; phase 1 owns only the CSV and its loader | 6: surrounding convention — `backfill` likewise reads a vendored CSV and writes rows without a separate refresh command, and a standalone `ticker-cik refresh` would be a command with one caller |
| Phase 5 edits `test_strategy_purity.py`'s glob vs invariant 5's "with no edit" and phase 6's "passes unmodified" | **phase 5 extends the glob additively**; invariant 5 reworded to "no phase weakens the gate"; phase 6 still leaves the file untouched | 1: the invariant's intent was that no phase weaken purity — extending the glob to cover `fundamentals/` strengthens it, so the literal wording was mine and wrong, not phase 5's action |
| Who extends the research store so the lab sees a non-empty panel (flagged as a gap by phases 6 and 7; owned by neither) | **phase 6** | 6: surrounding convention — phase 6 already owns `dev.py:367`, the identical "a `Market` is rebuilt and drops the field" fix, and `research.py:472` is the same class of site. It also already has `with_fundamentals` |
| Whether phase 7 runs `lab run M0005` to prove the method end to end | **no** — ship the method file unrun with a hermetic test | 5: the user's standing lab rules — `runner.preflight` refuses a second run, so one run against a fundamentals-free store permanently spends the id on an all-cash result |

Added in reconciliation (round 1) — behavioural forks between two plans, each settled on the
highest rung that spoke, with the losing side **edited out** of its plan file:

| Fork | Chosen | Rung |
|---|---|---|
| `fundamental_facts` keyed by `symbol` (phase 6's assumption) vs by `cik` (phases 2 and 4) | **`cik`**, with phase 6 joining `ticker_cik` to supply the symbol its panel is keyed by | 1: invariant 4 ("a ticker alone never identifies a company"). A `symbol` column would duplicate every row for a share-class pair and let a recycled ticker name two filers' facts |
| `period_start` nullable (phase 6's assumption) vs `NOT NULL` with `period_start = period_end` meaning instantaneous (phases 2 and 4) | **`NOT NULL`**; the equality is the instant marker, translated to `None` at the one row-reading boundary | 3: the plans' code blocks — a nullable column cannot sit in a PRIMARY KEY, and the period *must* be keyed, because one 10-K reports `Revenues` for both the fiscal year and Q4 under the same `accn`/`tag`/`unit`/`period_end` |
| The panel's read surface: four accessors `flow_ttm / stock_asof / filed_asof / sue_asof` (phase 7) vs one `as_of(symbol, t) -> Snapshot` (phase 5) | **`as_of`** | 2: phase 5's exit criteria, which its executed code and 39 passing tests already meet. It is also the better contract — one call per symbol per session, and the staleness gate, the four factors and the gross-profit basis all come from one consistent observation set rather than five lookups that could straddle a filing |
| Flow metrics trailing-twelve-month (phase 7) vs **annual** (phase 5) | **annual** | 2: phase 5's exit criteria and its recorded decision 4 — annual coverage is 8/8 in the measurement, while a clean TTM needs four untroubled quarters and so would be available for some names and not others, putting a systematic wedge through the cross-section. Fama-French is annual anyway |
| `prepare_market` as a member of the `runtime_checkable` `Allocator` protocol (phase 7) vs a sibling `MarketAware` protocol + a `prepare_for` helper (phase 6) | **`MarketAware` + `prepare_for`**; `Allocator`'s member set unchanged | 3: phase 6's code block records the measurement — a `runtime_checkable` protocol's `isinstance` checks the *full* member set, so adding one member makes `isinstance(x, Allocator)` False for all eleven structural implementers and breaks eight production call sites |
| Phase 7's `uses_fundamentals = True` class marker vs `isinstance(allocator, MarketAware)` | **`MarketAware`**; the marker is deleted | 6: surrounding convention — the tree already dispatches on the protocol at `dev.py:455`, and a second source of truth for "my live path is `prepare_market`" can only drift from the first |
| Who writes `ticker_cik.csv`'s `NONE` rows into the `ticker_cik` table, and what status a `NONE` symbol gets | **nobody writes them** (the column is `NOT NULL bigint`, so `sync_ticker_cik` skips them); a `NONE` symbol is **`empty`**, not `failed` | 2: phase 4's own exit criterion — "an `empty` filer is not an error". The map *answered*; the answer was "there is nothing at EDGAR to fetch", which is the `backfill`-style `empty`, not a map gap |
| `ticker_cik.source`'s domain: phase 1's tier labels (`current, edgar, exact, fuzzy, manual`) vs phase 2's CHECK (`company_tickers, cik_lookup, fuzzy, manual`) | **phase 1's labels**; phase 2's CHECK widened to them | 3: phase 2's own code block states the rule — "if phase 1 chose different labels, widen this CHECK rather than renaming phase 1's data" |
| Ingesting `us-gaap:Liabilities` and `us-gaap:EarningsPerShareBasic` (phase 4's draft list) vs only the ladder's rungs (phase 5) | **only the ladder's rungs**; both tags dropped | 2: phase 5's exit criteria define the concept set, and no concept reads either tag — SUE and the EPS series are on **diluted** EPS (8/8 measured) and book equity is tagged directly. Every stored tag costs rows against a 0.5 GB tier already holding 177 MB of bars |
| Where the research store's fundamentals artifact lives: phase 6, phase 7, or a new phase 8 | **phase 6** | 6: surrounding convention — phase 6 already owns `dev.py:367`, the identical "a `Market` is rebuilt and drops the field" fix, and already ships `with_fundamentals` to make the construction site one line. The alternative (a `lab run --fundamentals` flag reading Neon) was rejected on the measurement that the lab's window opens in 1996 while Neon's `bars` start in 2015 — it would be a different backtest, not the same one with extra data |
| Whether phase 7's tests may hand a `FakePanel` to `Market(...)` | **no** — a real `FundamentalPanel` for the three `Market`-constructing tests, `FakePanel` only for the pure functions | 3: phase 6's code block — `Market.__post_init__` type-checks the field and raises `TypeError`. The real panel is also strictly better coverage |


Added in reconciliation (round 2) — forks round 1 did not face, each settled on the highest
rung that spoke:

| Fork | Chosen | Rung |
|---|---|---|
| `fundamentals.csv` as a fifth **required** store file (`DATA_FILES`) vs an **optional** one (`OPTIONAL_DATA_FILES`) | **optional** | 2: phase 6's own exit criterion — "a store built before this phase still loads". Measured against `research.py:524-529`, `:441-443` and `:192-194`, widening `DATA_FILES` makes that criterion false by `ValueError` for every store on disk, and takes `engine/tests/test_research_store.py` (which no phase owns) down with it. Optional satisfies the criterion exactly: same four files, same hashes, **same fingerprint**, so the lab's recorded history is untouched |
| Who opens the database connection that fills `fundamentals.csv` — `research.build_store` or the `research_store` command | **the command**, behind an opt-in `--with-fundamentals`; `build_store` takes a plain `facts` sequence | 6: surrounding convention — `research.py`'s module docstring states "**Never Neon**: this module imports nothing from `seer_engine.db`", and every impure connection in the tree lives in `commands/`. Passing facts in keeps that invariant literally true while still meeting the exit criterion, and the default-off flag keeps every existing `build_store` caller, including all of `test_research_store.py`, byte-identical |
| The research-store CSV reader: phase 5's `fact_from_row` over `csv.DictReader` vs phase 6's `io.facts_from_frame` | **`facts_from_frame`** | 3: the plans' code blocks — `fact_from_row` takes typed values and `Fact.__post_init__`'s `_check_date` rejects a string, so `DictReader`'s all-string rows would be dropped wholesale by `facts_from_rows(skip_invalid=True)`: an empty panel, no error. `facts_from_frame` is already the one text→`Fact` path, so reusing it makes the store panel and the DB panel identical by construction |
| Phase 7's own `EmptyPanel` vs phase 5's `EMPTY_PANEL` | **phase 5's**, imported | 1: invariant 5 permits it (`fundamentals` is pure) and rule "one owner per concept" requires it. Decisive measurement: phase 6 makes `Market.fundamentals` default to phase 5's object, so a locally-built third empty panel would make phase 7's own `is EMPTY_PANEL` identity test False for every `Market` built without a panel |
| Phase 4's dev-window-equivalent question — does `--symbols` consult `fundamentals_log` once the log is CIK-keyed | **no**, `--symbols` ignores the log outright | 4: the plan index's own text and the flag's shipped help string ("ignores `fundamentals_log`"). Consulting it would also hollow out two of phase 4's tests, which use `--symbols` precisely to force a re-fetch over an existing `ok` row |
| Phase 7's dev-window test over all six variants vs the SUE-free subset | **the SUE-free subset, computed from `factors_read`**, with a separate test pinning that the SUE-ranking variants rank nobody and raise nothing | 2: phase 5's exit criteria — SUE needs `sue.MIN_QUARTERS` quarters of diluted EPS, which a synthetic **annual** panel cannot have, so `Snapshot.sue` is NaN and `assert trades > 0` is unachievable for three of the six. Hand-listing "four" was already wrong twice over (it is three, and `rank="composite"` reads SUE), so the subset is computed, not written down |

## Open Questions

_(none, after two rounds. Every fork above was decided from the ladder and the losing side was
edited out of its plan file; every requirement id is owned by at least one phase and no step
moved phases in round 2, so the Requirements table above is final. This section is empty
because the ladder spoke on all seventeen forks — only a fork where **every** branch is
irreversible belongs here, and none of these was. The nearest candidate was row 32: adding
`fundamentals.csv` to `DATA_FILES` would have been irreversible-looking, since it invalidates
stores on disk. It is not irreversible — a store is rebuilt by one command — and the optional
design makes the question moot, so it was decided rather than parked.)_

## Rollback

Per phase: each phase is one commit on `feature/edgar-fundamentals`; `git revert` it. Phase 2 is
the only one touching the schema — its migration creates three new tables and alters nothing, so
reverting means `DROP TABLE fundamental_facts, fundamentals_log, ticker_cik` and deleting the
`schema_migrations` row. Phase 6 is the only one touching shipped behaviour; its exit criteria
require byte-identical backtest output, so a diff there is the signal to revert it alone.

Two ordering consequences of reconciliation, for whoever is reverting:
- **Phase 4 now depends on phase 5** (it imports `ladder.LADDER_TAGS`). Reverting phase 5 alone
  leaves phase 4 with an unresolvable import. Revert 4 first, or not at all.
- **Phase 6 also touches `research.py` and `commands/research_store.py`.** `fundamentals.csv`
  is an **optional** store file (`OPTIONAL_DATA_FILES`), never a member of `DATA_FILES`, so a
  store built before phase 6 keeps its exact fingerprint and no recorded trial is invalidated.
  Reverting phase 6 restores the strict manifest check, which then rejects a store that *was*
  rebuilt with `--with-fundamentals`; the one manual step is
  `python -m seer_engine research_store` to rebuild without it. Trials recorded in between keep
  the fingerprint they were written with; nothing reads it as an equality gate and
  `runner.preflight` does not key on it, so no method is blocked either way.

As a whole: the branch is never merged, or `git branch -D feature/edgar-fundamentals` and
`git worktree remove`. Nothing on `main` changes until the set lands.

## Next

Execute the phases one at a time, starting at phase 1:

    /implement -f EDGAR_FUNDAMENTALS_PLAN.md --phase 1

Or run the whole set as a swarm — a session per phase, concurrent wherever `Depends on` allows,
resumable on any machine:

    /analyze-orchestrator -f EDGAR_FUNDAMENTALS_PLAN.md

Or put them on the board first (GitHub repos only):

    /create-task --from-plan EDGAR_FUNDAMENTALS_PLAN.md

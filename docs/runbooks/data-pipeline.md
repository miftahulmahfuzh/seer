# Runbook — Seer data pipeline (P1)

Spec: [handover 2026-10-03](../handover/2026-10-03-data-pipeline.md) ·
Plan: `ENGINE_DATA_PIPELINE_PLAN.md` · Roadmap: [P1](../ROADMAP.md)

## Architecture

`engine/` is a Python 3.11 package, `seer_engine`, that writes into the same Neon Postgres the
web app reads. Writes go over `DATABASE_URL_UNPOOLED` with psycopg. `universe refresh` turns the
vendored point-in-time S&P 500 and Nasdaq-100 histories in `engine/data/` (plus
`membership_overrides.csv` and `ticker_aliases.csv`) into the `universe` table. `backfill` loads
split-adjusted daily bars for every symbol that was ever a member since 2015-01-02, plus SPY,
from yfinance, and USD/IDR history from Frankfurter. Each symbol's outcome is recorded in
`backfill_log`, so the backfill can resume.
`fundamentals` loads SEC EDGAR XBRL company facts for every ever-member on or after
2009-01-01 (`seer_engine.cik.SINCE`), 913 symbols,
resolving each ticker to a CIK through the vendored `engine/data/ticker_cik.csv` (dated, because
tickers are recycled). Facts are stored raw in `fundamental_facts`, keyed including the
accession number so a restatement inserts beside the original rather than overwriting it; the
derived metrics the factors use are computed in pure Python at load time, not in SQL. Each
symbol's outcome goes to `fundamentals_log`, so it resumes exactly as `backfill` does. It needs
no price bars: the 133 ever-members Yahoo no longer serves still have complete filings.
`nightly` runs after every US session. It computes
`data_date`/`session_date` from the NYSE calendar, fetches the missing sessions from Massive
grouped-daily (universe ∪ SPY, plus any symbol held or pending in paper state), applies new
splits once (`split_adjustments`), records each session's cash dividends (`dividends`), records the
FX rate, and finishes one `runs` row per session, all in one transaction. A failure marks the
run `failed` and writes no bars. Every write command first deletes the demo rows in its own
transaction, once. GitHub Actions supplies the schedule; Vercel only reads.

Paper trading (P4) runs after `nightly` in the same job: see [paper-trading.md](paper-trading.md).

## Commands

Install once: `python -m venv engine/.venv && engine/.venv/bin/pip install -e 'engine[dev]'`.
Locally the engine reads the repo-root `.env.local` itself. **Never `source .env.local`**:
`DATABASE_URL` contains an unquoted `&`. Raw `psql` hangs from this WSL machine (IPv6), so every
check below goes through Python.

| Command | What it does | Writes |
|---|---|---|
| `engine/.venv/bin/python -m seer_engine migrate` | applies `db/migrations/*.sql` not yet in `schema_migrations` (same table as `npm run db:migrate`) | schema |
| `… -m seer_engine universe refresh` | rebuilds `universe` from `engine/data/` in one transaction; no-op when unchanged | `universe` |
| `… -m seer_engine universe check` | compares today's computed members with Wikipedia's current lists; exits 1 on any difference | nothing |
| `… -m seer_engine backfill` | yfinance bars from 2015-01-02 to the last completed session for every ever-member ∪ SPY, plus Frankfurter FX; skips every symbol already in `backfill_log` (any status), so a re-run resumes | `bars`, `fx_rates`, `backfill_log` |
| `… backfill --symbols NEW1,NEW2` | backfill specific symbols (comma-separated, dot form); ignores `backfill_log` | same |
| `… backfill --retry-failed` | retry symbols logged `failed`/`empty` (never touches `ok`) | same |
| `… backfill --end YYYY-MM-DD` / `--batch-size N` | pin the last date (keep it fixed across resume passes on different days) / symbols per yfinance call (default 40) | same |
| `… backfill --fx-only` / `--skip-fx` | only / everything but the FX history | same |
| `… -m seer_engine nightly` | the nightly run for "now"; no-op if that session already succeeded | `bars`, `split_adjustments`, `dividends`, `fx_rates`, `runs` |
| `… nightly --now 2026-10-05T23:00:00Z` | replay the nightly as of a given UTC instant (format: `nightly --help`) | same |
| `… -m seer_engine fundamentals` | SEC EDGAR company facts for every ever-member on or after 2009-01-01 (`seer_engine.cik.SINCE`), 913 symbols, resolved through `engine/data/ticker_cik.csv` by **(ticker, date)**; the unit of work is the **CIK**, so a share-class pair (GOOG/GOOGL) is one fetch and one log row; skips every CIK already in `fundamentals_log` (any status), so a re-run resumes | `fundamental_facts`, `fundamentals_log`, `ticker_cik` |
| `… fundamentals --symbols AAPL,MSFT` | load specific symbols (comma-separated, dot form); still deduped to CIKs, but ignores `fundamentals_log` | same |
| `… fundamentals --retry-failed` | retry CIKs logged `failed`/`empty` (never touches `ok`) | same |
| `… fundamentals --no-sync-map` | skip mirroring `engine/data/ticker_cik.csv` into the `ticker_cik` table | `fundamental_facts`, `fundamentals_log` |
| `… -m seer_engine research_store --with-fundamentals` | rebuild the research store **with** a `fundamentals.csv` panel read from the database. Without the flag the store is built exactly as before and the lab sees an empty panel — see "The lab and fundamentals" below | `engine/.research/` |

### Train/eval on a local database, Neon for inference

`research_store` downloads bars and dividends from **yfinance** and FX from **Frankfurter**, so
the only database read in the whole train/eval pipeline is `fundamental_facts` x `ticker_cik`.
Pointing that one read at a local Postgres takes Neon out of train/eval entirely -- and keeps
384 MB of facts off a 0.5 GB production tier. MEASURED 2026-10-05: Neon went 571 MB -> 187 MB.

Nothing in production reads `fundamental_facts`. `paper/store.py:load_market_window` builds its
`Market` without the field (so it gets `EMPTY_PANEL`) and the web app never queries the table,
so the facts were only ever staged in Neon to build a local artifact.

`config.env_file()` already supports selecting a different settings file, so this needs no code
change. `.env.local-train` (gitignored) points `DATABASE_URL_UNPOOLED` at the local container:

```bash
docker start seer-pg    # postgres:16 on 55432, per "Local test database" below
SEER_ENV_FILE=.env.local-train engine/.venv/bin/python -m seer_engine migrate
SEER_ENV_FILE=.env.local-train engine/.venv/bin/python -m seer_engine fundamentals
SEER_ENV_FILE=.env.local-train engine/.venv/bin/python -m seer_engine research_store --with-fundamentals
```

Neon stays the default (`.env.local`) for `migrate`, `nightly`, `paper`, `veto` and the web.
`ticker_cik` is kept in Neon (224 kB) because any future inference slice must join against it;
`fundamental_facts` and `fundamentals_log` are truncated there. The log is truncated too and
that matters: a stale log would make a later `fundamentals` run against Neon skip every CIK as
"already logged".

When `FND` eventually enters paper's live roster, inference WILL need fundamentals -- but only
the latest annual figures per symbol, which is kilobytes, not the full 1.23M-row history. Note
also that `paper/store.py:1035` does not pass `fundamentals` to `Market`, so a `MarketAware`
allocator in paper would silently rank nobody until that site is fixed.

The two laptops share the store rather than each rebuilding it: `/sync-research-store`
(`push`/`pull`, content-addressed on the manifest fingerprint). Two rebuilds produce two
different fingerprints, because yfinance answers differently from one day to the next.

Global flags go **before** the command: `--dry-run` does every read and computes every write,
then rolls back (nothing is written; the demo purge also runs and is rolled back, and is logged
as "would purge"). `-v` gives debug logs.
Example: `engine/.venv/bin/python -m seer_engine --dry-run -v nightly`.

Exit codes:

| Command | 0 | 1 | 2 |
|---|---|---|---|
| `backfill` | no symbol `failed`, FX loaded (`empty` = delisted/unknown to Yahoo is expected and fine) | some symbol `failed` (rate limit, download error) or FX failed; fetched bars are committed → re-run with `--retry-failed` (or `--fx-only`) | empty universe (run `universe refresh`) or bad arguments |
| `fundamentals` | no symbol `failed` (`empty` = a filer EDGAR has no XBRL facts for, **or one `ticker_cik.csv` marks `NONE`**, is expected and fine) | some symbol `failed` (SEC 429/5xx after retries, a malformed `companyfacts` payload, **or no CIK for it in `ticker_cik.csv`**); facts already fetched are committed → re-run with `--retry-failed`, or re-vendor the CSV | `SEC_CONTACT_EMAIL` or `DATABASE_URL_UNPOOLED` missing, empty universe (run `universe refresh`), an empty `ticker_cik.csv`, or bad arguments |
| `nightly` | run `success`, or the session already succeeded (no-op) | run marked `failed` with `error`; no bars written for it | `MASSIVE_API_KEY` or `DATABASE_URL_UNPOOLED` missing |
| `universe check` | identical to Wikipedia | drift (or a fetch/parse error) | — |
| any | — | uncaught error | missing setting (`ConfigError`) |

## Splits

- `backfill` records no splits: yfinance's `Open/High/Low/Close/Volume` (`auto_adjust=False`) are
  split-adjusted (not dividend-adjusted) as of the moment of the download.
- `nightly` fetches Massive's splits for every session it fetches (only sessions after SPY's
  latest stored bar, so never a split the backfill already saw). In one transaction it first
  applies **every** split in the gap to the history stored before this run (prices ÷
  `split_to/split_from`, volume ×), then upserts the fetched bars, which Massive already adjusted
  as of fetch time.
- Guard, in order: a split already in `split_adjustments` is never applied again; a symbol whose
  latest stored bar is on or after the execution date is already adjusted (recorded with
  `applied=false`); otherwise, for factors with `|ln f| ≥ ln 1.25` the price-ratio heuristic
  (`prev close` vs the first fetched open) decides, and smaller factors (stock dividends such as
  21:20) are applied because the stored history predates them by construction.
- Only splits of universe ∪ SPY symbols, or of symbols that already have bars, are recorded.
- Stored `dividends` rows with an ex-date before a split's execution date are rewritten with the
  bars (`amount × split_from / split_to`, 6 decimals), so dividends stay in the bars' units.
- Re-running `backfill --symbols X` after a split overwrites X's history with yfinance's newly
  adjusted values, which are consistent with what the nightly applied.

## SEC fundamentals

- SEC's fair-access policy requires a declared `User-Agent` carrying a contact address and caps
  requests at 10/second. The engine reads the address from `SEC_CONTACT_EMAIL` and rate-limits
  from the *end* of the previous call, the way `massive.py` does. `http.py`'s shared session is
  not used, so the contact address never leaks into Massive or Finnhub calls. Measured from this
  host, `data.sec.gov` answers a `companyfacts` request in **7–60 s**, not the sub-second the
  10 req/s cap would suggest — a full 795-member run is hours, not minutes, and the pacing floor
  is never the binding constraint.
- `filed` is the only availability boundary. Every read path exposes the latest fact with
  `filed <= t` and nothing else. A fact's `period_end` is never its availability date: a Q4
  figure for a period ending 2015-12-31 is typically filed in February 2016.
- Restatements are preserved, never overwritten: `accn` is part of a fact's identity, so a
  revised figure inserts beside the original and both stay queryable.
- Gross profit is derived. Only 2 of 8 sampled dead filers tagged `GrossProfit`, so the ladder
  falls back to `Revenues − CostOfRevenue`; the fallback is documented in the derivation
  package's module docstring. Revenue itself has two tag variants (`Revenues`,
  `RevenueFromContractWithCustomerExcludingAssessedTax`).
- Market capitalisation is point-in-time only because the share count is filed-dated
  (`dei:EntityCommonStockSharesOutstanding`) and is multiplied by the close from `bars`. When
  either side is missing the cap is undefined and the value factor drops that name for that day,
  rather than substituting a zero.

### Re-vendoring `engine/data/ticker_cik.csv`

A ticker alone never identifies a company: `CA` is now an Xtrackers ETF, `MON` a SPAC, `PLL`
Piedmont Lithium, `ALTR` Altair, `LLL` JX Luxventure, `DTV` DTE units. Every row therefore
carries a validity interval and the loader rejects overlaps for one ticker. The file is data,
generated once and committed — it is never rebuilt at runtime.

The recipe lives in **`engine/data/SOURCES.md`**, under `ticker_cik.csv` — one copy, kept
current by whoever re-vendors the file, carrying the live row and tier counts, the three refusal
lists (`UNRESOLVED`, `SCREEN`, `EARLY`), the `MANUAL` empty-start sentinel and the rule that an
`end_date` is never pushed forward. Do not duplicate it here; a second copy goes stale silently
and this one did.

Two things that are true whatever the counts say, and are the reason the file is hand-audited:

- **Read every fuzzy row by hand before committing it.** The shipped file carries *zero* fuzzy
  rows deliberately: the automated name screen once matched "Harman International" to AMERICAN
  INTERNATIONAL INDUSTRIES (`0001073146`) — a different company entirely; the real HAR is
  `0000800459`. A fuzzy name match is a suggestion, never evidence.
- **Validate before committing:** `engine/.venv/bin/pytest engine/tests/test_cik.py -q`. It
  checks the header, rejects overlapping intervals and a CIK that is not 10 digits, and asserts
  each recycled ticker resolves to the company that held it during its membership rather than to
  the current holder.

Then update the sha256 block in `engine/data/SOURCES.md`, and re-ingest the changed tickers'
facts under their corrected CIKs with
`engine/.venv/bin/python -m seer_engine fundamentals --symbols <the changed tickers>` —
`--symbols` ignores `fundamentals_log`, which is what makes it the tool for this.

### The lab and fundamentals

`lab run` loads the research store. `research.load_store` builds its `Market` with a
fundamental panel **only when the store holds a `fundamentals.csv`**, which is an optional
file written by `python -m seer_engine research_store --with-fundamentals`. A store built
before that flag existed, or rebuilt without it, loads cleanly with an **empty** panel and no
warning — that is deliberate (it keeps every store on disk loadable and its fingerprint
unchanged), and it is the trap. Method **M0005**
(`lab/methods/m0005_fundamental_factors.py`) ranks on that panel, so running it against an
empty one would record six all-cash trials, freeze the method file's `source_sha` and burn the
method id permanently (`runner.preflight` refuses a second run of any method).

**Before any fundamentals method, measure the panel's COVERAGE. Do not check for its presence.**

```bash
engine/.venv/bin/python -m seer_engine research_store --coverage
```

That prints, for the store at `engine/.research`, how many symbols the panel can actually rank on
each sampled dev-window date, and one fraction: the share of **monthly** sample dates on which it
can rank at least `top` names (default 20) from facts filed within `max_stale_days` of the date
(400, taken from `FundamentalParams`'s own default rather than restated). It is the same
eligibility gate `strategies/f_fundamental.py` applies, so the number predicts *rankability*
rather than mere fact-existence.

**The number is an upper bound.** The measure is pure: it takes a panel and reads no bars, so it
applies neither index membership on the date nor `min_price`, twenty sessions of history or
`min_dollar_volume` — every one of which can only remove symbols. A fraction *below* the floor is
therefore conclusive (the panel cannot rank); a fraction *above* it is necessary and not
sufficient. The command's own last output line says so.

`lab run` runs the same measure after it loads the store and **refuses** a method whose allocator
is `MarketAware` when the fraction is below `fundamentals.coverage.MIN_DEV_COVERAGE` (0.80). A
price-only method is never refused — M0001 and M0004 rank on price and must stay runnable against
a store with no panel at all. `--allow-coverage F` lowers the floor for one run and prints the
measured number loudly; it is an acknowledgement, not a bypass, and it does not suppress the
table.

**The gate this replaced was vacuous, and M0005 was spent proving it.** It asked "does
`manifest.json` list `fundamentals.csv`" — binary where the risk is continuous: a store carrying
a panel over a sliver of the dev window passes it. MEASURED 2026-10-05 — M0005 ran against the
store `e597367b…`, whose panel covered **2015-01-06..2015-10-16, about 9 months of the 19.8-year
dev window**. All six variants were recorded, all six "failed", and the verdict measured
cash-holding, not the factor premia. The tell was in the output: 15–32 trades over 19.8 years
against a `>= 100` gate, and "worst year 1996 +0.0%" for a year the book could not have held
anything.

**Presence is never evidence of coverage anywhere in this subsystem.** `panel.as_of(symbol, t)`
**always returns a `Snapshot`** — an empty husk with `observations == {}` when nothing is known —
so it never returns `None`, and `sum(1 for s in syms if panel.as_of(s, t) is not None)` counts
every symbol in every year and measures nothing. That is deliberate and defensible: the
fundamentals layer answers every query and encodes "I know nothing yet" as *empty content*, which
is what lets `Market` carry `EMPTY_PANEL` and every allocator keep working. The cost is that every
existence check here is a lie. **Check content, not presence.**

**What the measure reports now.** MEASURED 2026-10-05, store
`399d0d254c7a90b8cdb49f7ce598269087d38730f795cae90453eeb580b07cf8`, 869 panel symbols — after
Fix A (`ticker_cik.csv` re-vendored from the clamped 2015-01-02 scope date to each symbol's real
first-membership interval, 795 → 913 symbols) and Fix B (both ingest floors lowered to
2009-01-01):

```
panel coverage 1996-01-02 .. 2015-10-02: 238 monthly samples, 869 symbols in the panel
  rankable: non-empty observations AND a filing within 400 days; covered: at least 20 rankable symbols
  year    covered/sampled    most rankable
  1996        0/12                0
  1997        0/12                0
  1998        0/12                0
  1999        0/12                0
  2000        0/12                0
  2001        0/12                0
  2002        0/12                0
  2003        0/12                0
  2004        0/12                0
  2005        0/12                0
  2006        0/12                0
  2007        0/12                0
  2008        0/12                0
  2009        5/12              378
  2010       12/12              526
  2011       12/12              548
  2012       12/12              546
  2013       12/12              548
  2014       12/12              547
  2015       10/10              550
  covered 75 of 238 sampled dates = 0.3151 (BELOW the 0.80 floor)
  an upper bound: index membership, min_price and min_dollar_volume can only remove symbols
```

Dev-window coverage, as an **upper bound**: **0.3151** (75 of 238 monthly samples). The first
sampled date on which the panel can rank 20 names is **2009-08-02**. The same measure run against
the pre-fix store (`e597367b…`) reports **0.0378** (9 of 238).

Three numbers are in circulation for "coverage" and only one of them is this measure. **This
one** is monthly sampling, `top = 20`, `max_stale_days = 400`, 1996-01-02 .. 2015-10-02 (238
samples over the dev window, which ends 2015-10-16), content checked through
`Snapshot.observations`. The `2.5%` recorded in the 2026-10-05 analysis was a **semiannual**
sample (1 of 40 dates); the `4%` in `docs/plans/2026-10-05-fundamental-panel-coverage.md` §4 is a
**span estimate** (nine months of 19.8 years). Both are retired. Do not compare across them.

**What Fix A alone would have reached: 0.1387** (33 of 238) — the same measure over the same
refreshed panel with facts filtered to `filed >= 2013-01-01`. So the two fixes contribute
separately: Fix A buys 2013–2014 (which the clamped map had dropped entirely, despite the facts
being stored), and Fix B buys 2009–2012.

**The real floor is roughly 2011, not 2009, and the early years are large-cap-skewed.** Facts by
`filed` year after Fix B, against the ~90k/year the 2013-onward baseline holds: 2009 **22,219**
from 403 filers (~25% of a full year), 2010 **60,550** from 670 (~67%), 2011 **90,505** from 729
— the first year to reach baseline — and 2012 **99,641** from 738. XBRL phased in by filer size
(large accelerated filers from roughly FY2009, all filers by FY2011), so 2009–2010 are thin **and
size-biased by construction**. For a *ranking* method that skew matters more than the raw count:
a 2009 cross-section is a large-cap cross-section, not the index.

**Fix A unblocked facts that were already stored, and it was hiding wrong answers as well as
missing ones.** The dated `ticker_cik` join had **zero** panel rows for 2013 and 2014 before the
re-vendoring and has 74,248 and 74,339 now; the panel went 831,725 rows / 780 symbols to
1,213,351 / 869. The audit that produced those intervals also found rows that were simply
**wrong** and that nothing had ever queried: `MFE` pointed at MCAFEE COM CORP (no filings after
2000), `JNS` at an entity with no periodic filings, `AKS` at a non-filing subsidiary, `WFT` at
Weatherford Enterra (filings end 1998), and `DIS`, `XRX` and `SNDK` at 2019 holdcos and a 2025
spinoff — `SNDK` resolving to the 2025 Sandisk spinoff rather than the SanDisk that was in the
index. Those shipped in `main`; the clamp meant nothing ever queried the range that would expose
them.

**This does not make a fundamentals method testable on the dev window, and nothing here should be
read as saying it does.** The dev window opens **1996-01-03**. XBRL does not exist before roughly
**2009**, so about **thirteen of its nineteen years are permanently uncoverable from EDGAR** — at
any price, by any amount of work. (Compustat sells point-in-time pre-2009 fundamentals; it is
expensive, licence-encumbered, carries its own restatement-vintage problems, and is **out of
scope**.) A book that holds cash for most of the window cannot reach the lab's `>= 100 trades`
gate, so **that gate remains unreachable for a fundamentals method on this dev window.** Fix A
and Fix B made the *data* honest; they did not make the *test* valid.

**The test-window decision is UNMADE and out of scope.** The only window on which these premia
could be tested validly is the post-2015 held-out test window, which this lab has never used
(`test-window looks used: 0`). It can be spent exactly once, and spending it is a separate
decision with its own doc. Giving fundamentals methods a shorter dev window of their own is the
other candidate and is also deferred: it breaks comparability with the 64 trials recorded against
1996–2015 and changes the DSR's `N`.

**M0005 is `rejected` and its six `config_digest`s are spent.** The hypothesis is untested, not
refuted. A re-test is a **new** method with `source_kind='variation'` and `parent_id='M0005'`, and
it must not be minted until the gate above reports a number worth testing.

**`m0005_fundamental_factors.py`'s own "READ THIS BEFORE RUNNING" docstring still prints the
retired manifest one-liner, and it cannot be corrected.** A method file is frozen once it has
trials: `test_lab_methods.py::test_a_method_that_ran_is_frozen` compares `source_sha(path)` with
the sha recorded in the committed lab database, and a docstring edit moves it (measured — the
edit was made, the test failed, the edit was reverted). Editing the file to fix its own warning
would therefore mean minting a variation method, which is the very thing the warning says not to
do. **This section is the current instruction; the docstring in that file is not.**

**Refreshing the panel without re-downloading bars.** `research_store --with-fundamentals` goes
through `build_store`, which always downloads every symbol's bars first: it would replace all
2,490,793 bar rows with whatever yfinance answers today and produce a different fingerprint,
breaking comparability with every recorded trial. Use the fundamentals-only refresh instead:

```bash
# From the repo root. SEER_ENV_FILE is resolved against your cwd, so run it from there or
# give it an absolute path -- a relative one that misses falls through to the ambient
# DATABASE_URL_UNPOOLED, which is Neon.
SEER_ENV_FILE=.env.local-train \
  engine/.venv/bin/python -m seer_engine research_store --refresh-fundamentals
engine/.venv/bin/python -m seer_engine research_store --verify     # the new fingerprint
engine/.venv/bin/python -m seer_engine research_store --coverage   # the new number
python3 ~/.claude/skills/sync-research-store/sync_store.py push --keep 0
```

It copies `bars.csv`, `dividends.csv`, `fx.csv` and `unserved.csv` byte for byte, writes a new
`fundamentals.csv`, re-seals and swaps atomically; only the panel and the fingerprint change.
`push --keep 0` matters: a plain `push` prunes to the newest three versions
(`sync_store.py:294` calls `_prune(tok, keep=args.keep)` with `KEEP_VERSIONS = 3`), and the
version it drops is the oldest — possibly the one you would roll back to.

Tests: `PG_TEST_URL=… engine/.venv/bin/pytest engine/tests -q` (see "Local test database").
Without `PG_TEST_URL` the DB tests are skipped with a reason.

### Starting capital, price fingerprints and rebuilds

The lab's 152 trials carry three different `trials.store_fingerprint` values, and on 2026-10-09
that looked like three different stores. **It is not.** `research.fingerprint_of` hashes the whole
`files` map of `manifest.json`, so adding or refreshing `fundamentals.csv` moves the fingerprint
without moving a single bar. MEASURED 2026-10-09: the fingerprint of the current store's four
price files alone (`bars.csv`, `dividends.csv`, `fx.csv`, `unserved.csv`, `fundamentals.csv` left
out) is `5451195fd552e208eaadfc6bc89241b9b8e3e6ccb0f4c447a84bbc4f32e7d90a` — exactly the P7a
store's. `e597367b…` added the 2015-only panel and `399d0d25…` rebuilt the panel from 2009 with
`--refresh-fundamentals`, which copies the price files byte for byte. **The dev store's prices
have never changed.**

So the lab keeps two fingerprints and they answer different questions:

| | what it hashes | what it is for |
|---|---|---|
| store fingerprint (`trials.store_fingerprint`, `ResearchData.fingerprint`) | every file in the manifest, panel included | re-running a method that reads the fundamentals panel: only the same store fingerprint reproduces it |
| price fingerprint (`trial_provenance.price_fingerprint`, `ResearchData.price_fingerprint`, `research.price_fingerprint_of`) | the four price files only | comparing recorded curves: two curves are comparable when their price fingerprints are equal |

**Starting capital is recorded per trial.** What actually broke reproduction was not the store but
`backtest.runner.INITIAL_IDR`, which `d79fc83` moved from 20,000,000 to 10,000,000 IDR on
2026-10-08. Whole-share lot rounding makes capital a result-moving input, and before schema 5
nothing recorded it — a curve is normalised to opening cash. `lab/lab.sqlite` schema 5 adds the
append-only `trial_provenance` table: one row per trial with `initial_idr` and
`price_fingerprint`. New trials write it in the same transaction as the trial
(`source = 'recorded'`); the 152 trials that existed at migration were back-filled
(`source = 'backfill'`) by a rule that is exact on all of them, checked against git ancestry of
`d79fc83`: a lump-sum trial ran at 20,000,000, a funded trial (one with a `trial_funding` row) at
10,000,000. The price fingerprint was back-filled as `5451195f…` for all 148 dev trials, as
itself for the two test trials on `56e83810…`, and as unknown (NULL) for the two on `bbe7abfb…`,
whose file map is not on this machine. `lab remeasure` and `lab costs` re-run a recorded trial at
its recorded capital; `INITIAL_IDR` is only the default for a **new** run.

**A rebuild is refused by `lab run`.** `build_store` re-downloads every bar, and yfinance answers
differently from one day to the next, so a rebuilt store gets a new price fingerprint. `lab run`
compares the loaded store's price fingerprint with the one recorded for the `REF-SPY-HOLD`
benchmark trial and refuses, before any backtest, when they differ or when the store names no
price fingerprint (`hardgate.pin_dev_store`; the rule is decision D10 in `lab/hardgate.py`) — a
trial recorded on a rebuilt store could not be compared with the benchmark, and the hard gate
would refuse it anyway. There is no flag to run anyway. To move machines, **copy** the store (`.claude/skills/sync-research-store/`),
which keeps both fingerprints. A fundamentals-only refresh (`--refresh-fundamentals`) changes the
store fingerprint and leaves the price fingerprint alone, so `lab run` still accepts it.

**What the gate and the reports do with it.** The hard gate refuses (`lab promote` exits 2) when
the benchmark's price fingerprint and any of the method's dev trials' price fingerprints differ or
are unknown; it fails closed and has no override. `lab walkforward` and `lab regime` only report,
so they print a warning line for such a method instead. MEASURED 2026-10-09: the rule strands 0
trials and changes 0 verdicts on the committed lab, because every dev trial shares one price
fingerprint; refusing on `store_fingerprint` instead would have closed every promotion path.

## Environment and secrets

| Variable | Used by | Where |
|---|---|---|
| `DATABASE_URL_UNPOOLED` | every engine command | `.env.local` locally; repo secret in Actions |
| `MASSIVE_API_KEY` | `nightly` only | `.env.local` locally; repo secret in Actions |
| `SEC_CONTACT_EMAIL` | `fundamentals` only | `.env.local` locally; repo secret in Actions |
| `PG_TEST_URL` | tests only | your shell locally; set by `engine-ci.yml` in CI |

### Owner steps (need the owner's approval; not done by the pipeline session)

Run these from the main checkout `/home/miftah/seer` after the feature branch is merged into
`main`. The two secret commands pipe each value straight from `.env.local` through the engine's
dotenv parser, so nothing is echoed and nothing is `source`d:

```bash
cd /home/miftah/seer
test -x engine/.venv/bin/python || { python3.11 -m venv engine/.venv && engine/.venv/bin/pip install -q -e 'engine[dev]'; }
engine/.venv/bin/python -c 'from dotenv import dotenv_values; print(dotenv_values(".env.local")["DATABASE_URL_UNPOOLED"], end="")' \
  | gh secret set DATABASE_URL_UNPOOLED --repo miftahulmahfuzh/seer
engine/.venv/bin/python -c 'from dotenv import dotenv_values; print(dotenv_values(".env.local")["MASSIVE_API_KEY"], end="")' \
  | gh secret set MASSIVE_API_KEY --repo miftahulmahfuzh/seer
gh secret list --repo miftahulmahfuzh/seer          # both names listed
git push origin main
gh workflow run nightly.yml --repo miftahulmahfuzh/seer -f dry_run=true
gh run watch --repo miftahulmahfuzh/seer             # dry run must end green
gh workflow run universe.yml --repo miftahulmahfuzh/seer
```

Schedules only run from the default branch (`main`), so nothing is scheduled until that push.

## Workflows and schedule

| Workflow | Trigger | UTC | WIB (UTC+7) | New York |
|---|---|---|---|---|
| `nightly.yml` | cron `17 6 * * 2-6` | 06:17 Tue–Sat | 13:17 Tue–Sat | 02:17 EDT / 01:17 EST Tue–Sat |
| `nightly.yml` retry 1 | cron `41 9 * * 2-6` | 09:41 Tue–Sat | 16:41 Tue–Sat | 05:41 EDT / 04:41 EST Tue–Sat |
| `nightly.yml` retry 2 | cron `41 12 * * 2-6` | 12:41 Tue–Sat | 19:41 Tue–Sat | 08:41 EDT / 07:41 EST Tue–Sat |
| `universe.yml` | cron `30 0 * * 1` | 00:30 Mon | 07:30 Mon | 20:30 EDT / 19:30 EST Sun |
| `backfill.yml` | manual only (`start`, `symbols`, `retry_failed`) | — | — | — |
| `engine-ci.yml` | push / PR touching `engine/`, `db/`, `web/`, `.github/workflows/` | — | — | — |

- **The night runs the morning after the session, not the evening of it.** The NYSE close is
  20:00 UTC in summer and 21:00 UTC in winter, and the engine's one hour of settle time clears
  it — but the close is not the binding constraint. Massive's plan refuses the grouped
  aggregate for any date that is still *today* in Eastern time, with HTTP 403
  `NOT_AUTHORIZED` / "Attempted to request today's data before end of day". Session D unlocks at
  ET midnight: 04:00 UTC in EDT, 05:00 UTC in EST. Every slot therefore sits after 05:00 UTC, so
  it holds in both offsets. This is why the original 23:00 / 01:00 UTC pair could never work —
  19:00 and 21:00 ET are the same ET day as the session.
- The far edge is the next US open, 13:30 UTC in EDT and 14:30 UTC in EST: picks for session
  `session_date` must exist before it. `last_completed_session` returns the same `data_date` for
  any instant between the session's close + settle and the *next* session's close + settle, so
  anything in the 05:00–13:30 UTC band yields the same correct pair. Half days close earlier
  and are covered too.
- GitHub cron often starts late — nominally minutes to about an hour, but this repo has seen
  5h33m (`universe.yml` asked for 00:30 UTC on 2026-10-05 and ran at 06:03). That is why the
  minutes are off the hour (`:17`, `:41`) rather than `:00` or `:30`, and why there are two
  retries: even a badly delayed 06:17 lands before the open, and a lost slot is covered twice.
- Nightly, universe and backfill share the concurrency group `seer-db-writer`, so only one of
  them writes to Neon at a time. A run that is in progress is never cancelled. While a long
  backfill runs, a queued 06:17 nightly may be replaced by a retry, which does the same work.
- Weekday holidays (for example Thanksgiving): the run the next morning finds the same
  `session_date` that already succeeded, and exits without writing anything.
- **60-day inactivity.** GitHub disables scheduled workflows in a public repo after 60 days
  without repository activity. The nightly job commits nothing, so this *will* happen. GitHub
  emails a warning about a week ahead. Re-enable with
  `gh workflow enable nightly.yml --repo miftahulmahfuzh/seer` (and `universe.yml`), or push any
  commit before the deadline.

## Failure modes and what the web shows

The web reads the latest `runs` row with `status='success'`. It shows the stale-data screen when
that row's `session_date` is earlier than the next US session (`web/lib/session.ts` `isStale`).

| Failure | Engine result | Workflow | Web | Fix |
|---|---|---|---|---|
| Massive down, 429, or not yet published | run row `failed` + `error`, **no bars** for that date | red; GitHub emails | stale screen (previous session's data) | nothing: a retry slot reuses the failed row. Otherwise `gh workflow run nightly.yml` |
| Nightly run before ET midnight | 403 `NOT_AUTHORIZED` "Attempted to request today's data before end of day", run `failed` | red | stale screen | wait for the scheduled slot; a hand-run before 05:00 UTC always fails this way |
| Frankfurter down | same as above (FX is part of the nightly transaction) | red | stale screen | same |
| Secret missing or wrong | "Check secrets" step fails before Python starts, or the connection fails | red | stale screen | Owner steps above |
| Neon storage full (0.5 GB) | insert fails, run `failed` | red | stale screen | see Storage budget |
| Membership drift | — | `universe.yml` red | unaffected | see Membership maintenance |
| Backfill rate-limited or timed out | symbols stay non-`ok` in `backfill_log` | red (manual run) | unaffected | run it again (it resumes), then `--retry-failed` |
| Schedules disabled (60 days) | nothing runs | — | stale screen | `gh workflow enable …` |

Check the latest runs at any time:

```bash
cd /home/miftah/seer
engine/.venv/bin/python - <<'PY'
from seer_engine import config, db
config.load_env()
with db.connect() as conn:
    for r in conn.execute("SELECT id, status, data_date, session_date, started_at, finished_at, left(error, 120) "
                          "FROM runs WHERE NOT is_demo ORDER BY id DESC LIMIT 10"):
        print(r)
PY
```

## Membership maintenance

- `universe.yml` runs every Monday. A red run means Wikipedia's current S&P 500 or Nasdaq-100
  list differs from what `engine/data/` computes for today. The job log prints the added and
  removed symbols.
- Fix: append one line per change to `engine/data/membership_overrides.csv` as
  `date,index_id,action,ticker,note` (`index_id` is `SP500` or `NDX`, `action` is `add` or
  `remove`, ticker in dot form; see `engine/data/SOURCES.md`). The date must be after the
  snapshot file's last row, or `refresh` rejects it. Take the effective date from Wikipedia's "Selected changes" table, not
  from the date you noticed. Then run locally:
  `engine/.venv/bin/python -m seer_engine universe refresh && engine/.venv/bin/python -m seer_engine universe check`
  (it must exit 0). Commit the CSV and push.
- New members have bars only from the day the nightly started covering them. Load their history
  with `engine/.venv/bin/python -m seer_engine backfill --symbols NEW1,NEW2`, or use the Backfill
  workflow with `symbols` set.
- When an upstream snapshot is refreshed (fja05680/sp500, thuningxu/sp500nq100), re-vendor it as
  `engine/data/SOURCES.md` describes, and delete any overrides the new snapshot already contains.

## Renames going forward

yfinance and Massive only know a company's *current* ticker. When a member renames (FB→META style):

1. Add `OLD,NEW,<effective date>,<note>` to `engine/data/ticker_aliases.csv`
   (`old,new,effective_date,note`; see `engine/data/SOURCES.md`), so membership before the rename
   is stored under the symbol that has the bars. Every `old` must point at the **current**
   ticker: if an existing row already maps something to `OLD`, repoint it to `NEW` (the loader
   rejects chains).
2. Move the stored history to the new symbol, dropping any day the nightly already wrote under
   the new name:

   ```bash
   cd /home/miftah/seer
   OLD=FB NEW=META engine/.venv/bin/python - <<'PY'
   import os
   from seer_engine import config, db
   config.load_env()
   old, new = os.environ["OLD"], os.environ["NEW"]
   with db.connect() as conn:
       with conn.transaction():
           d = conn.execute("DELETE FROM bars o USING bars n WHERE o.symbol = %s AND n.symbol = %s AND n.date = o.date",
                            (old, new)).rowcount
           u = conn.execute("UPDATE bars SET symbol = %s WHERE symbol = %s", (new, old)).rowcount
           conn.execute("UPDATE backfill_log SET symbol = %s WHERE symbol = %s "
                        "AND NOT EXISTS (SELECT 1 FROM backfill_log WHERE symbol = %s)", (new, old, new))
       print(f"dropped {d} overlapping rows, moved {u} rows {old} -> {new}")
   PY
   ```
3. `engine/.venv/bin/python -m seer_engine universe refresh`, then commit the alias line.

## Storage budget

Neon free is 0.5 GB. Estimated before the backfill: about 1.9 M rows, about 250 MB for `bars`,
growing about 21 MB a year (universe ∪ SPY only, not the whole market). Measured after the first
backfill: see First run. Check:

```bash
cd /home/miftah/seer
engine/.venv/bin/python - <<'PY'
from seer_engine import config, db
config.load_env()
with db.connect() as conn:
    print(conn.execute("SELECT pg_size_pretty(pg_total_relation_size('bars')), "
                       "pg_size_pretty(pg_database_size(current_database()))").fetchone())
PY
```

Above 400 MB for `bars`: don't widen the universe. Instead consider dropping symbols that were
never members after the backtest window, or moving to a paid tier.

## Local test database

```bash
docker start seer-pg 2>/dev/null || docker run -d --name seer-pg -e POSTGRES_PASSWORD=pg -p 55432:5432 postgres:16
docker exec seer-pg pg_isready -U postgres -t 60
export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres
engine/.venv/bin/pytest engine/tests -q -rs     # DB tests must run, not skip
docker rm -f seer-pg             # when done
```

With no Docker, use `/usr/lib/postgresql/16/bin/initdb` and `pg_ctl` on a scratch directory and
point `PG_TEST_URL` at it. CI uses a `postgres:16` service with
`PG_TEST_URL=postgresql://postgres:postgres@localhost:5432/seer_test`.

## Health checks

Per-table fingerprint, used to prove a re-run changed nothing. The fingerprint is the row count
plus an order-independent sum of per-row md5 hashes. `string_agg` over about 2 M rows would hold
more than 100 MB in memory on Neon's free compute.

```bash
cd /home/miftah/seer
engine/.venv/bin/python - <<'PY'
from seer_engine import config, db
config.load_env()
with db.connect() as conn:
    for t in ["bars", "fx_rates", "runs", "universe", "split_adjustments", "backfill_log",
              "ticker_cik", "fundamental_facts", "fundamentals_log"]:
        n, h = conn.execute(f"SELECT count(*), coalesce(sum(('x' || left(md5(r::text), 15))::bit(60)::bigint), 0) "
                            f"FROM {t} r").fetchone()
        print(f"{t:18} rows={n:>9} hash={h}")
PY
```

## Rollback (data)

Restores the demo state, for example to re-test the purge:

```sql
DELETE FROM runs WHERE NOT is_demo;
TRUNCATE bars, fx_rates, universe, split_adjustments, backfill_log;
TRUNCATE fundamental_facts, fundamentals_log, ticker_cik;
```

Run it through Python (`conn.execute(...)` in a `with conn.transaction():` block), then
`cd web && npm run db:seed-demo`. The seed now refuses only while real runs or more than 100
bars exist. Migration 002 is additive; dropping its three tables and the `runs_real_session_uidx`
index reverses it. Migration `005_fundamentals.sql` is additive too; dropping
`fundamental_facts`, `fundamentals_log` and `ticker_cik` and deleting its
`schema_migrations` row reverses it.

## First run — 2026-10-03

Run locally from the worktree `/home/miftah/.worktrees/seer/engine-data-pipeline`, against Neon.

**Workflow lint:** actionlint 1.7.12 (`rhysd/actionlint:latest` via Docker, shellcheck included): clean, exit 0, no findings for all four workflows.

**Tests:** `216 passed in 10.93s` (0 skipped; `PG_TEST_URL` = container `seer-pg`, Postgres 16); `vitest`: 4 files, `20 passed`.

**Before (demo state):** runs is_demo 1 (real 0) · orders 219 · equity_snapshots 264 · action_dismissals 0 · bars 6 · fx_rates 1 · strategies 4; `schema_migrations` = `001_init.sql`.

**migrate:** `--dry-run migrate` → "would apply 002_engine.sql", exit 0, nothing written; `migrate` → "apply 002_engine.sql", exit 0; second `migrate` → "nothing to apply". `schema_migrations` = `001_init.sql, 002_engine.sql`; tables `backfill_log, split_adjustments, universe` and index `runs_real_session_uidx` exist; demo counts unchanged by migrate (runs is_demo 1, bars 6, orders 219).

**universe refresh:** dry run logged "would purge demo data" and "would replace table with 1544 rows (dry run, rolled back)"; fingerprints before/after identical (`diff` empty). Real refresh: "1544 intervals, 1265 distinct symbols, 795 since 2015-01-01; current SP500=503 NDX=101 union=518; replaced table with 1544 rows". Second refresh: "unchanged, nothing written".
**Demo purge:** the real refresh logged "demo data found: truncated action_dismissals, orders, equity_snapshots, bars, fx_rates, runs". After: runs is_demo 0, orders 0, equity_snapshots 0, action_dismissals 0, bars 0, fx_rates 0; strategies unchanged (4); universe 1544 rows / 1265 symbols.
**universe check:** exit 0 — "SP500: computed 503, Wikipedia 503 -- identical", "NDX: computed 101, Wikipedia 101 -- identical". No override lines needed.

**backfill:** 06:02:28–06:15:21 UTC (13 min), one invocation `backfill --end 2026-10-02` (end pinned in `.workflows/live/backfill-end.txt`), 796 symbols in 20 batches of 40, 0 rate-limit failures. Then one `--retry-failed --end 2026-10-02` pass (exit 0): it re-tried the 133 `empty` symbols, all still empty, 663 `ok` skipped, 0 rows changed.
- backfill_log: ok 663 · empty 133 · failed 0
- not fetchable: 133 symbols, all `empty` ("yfinance returned no bars for 2015-01-02..2026-10-02"), none `failed`. They are delisted or acquired names whose history Yahoo no longer serves; **none of them is a current member** (`members_on(2026-10-02) ∩ empty = ∅`). `GPS` is the one rename among them (Gap Inc. now trades as `GAP`; no alias row yet, see Renames going forward). Full list: AABA (empty), ABMD (empty), ADS (empty), AET (empty), AGN (empty), ALTR (empty), ALXN (empty), ANDV (empty), ANSS (empty), ARG (empty), ATVI (empty), AVP (empty), BCR (empty), BRCM (empty), BXLT (empty), CA (empty), CCE (empty), CELG (empty), CERN (empty), CFN (empty), CHK (empty), CMA (empty), CMCSK (empty), COL (empty), COV (empty), CPGX (empty), CTL (empty), CTLT (empty), CTRA (empty), CTRX (empty), CTXS (empty), CVC (empty), CXO (empty), DAY (empty), DFS (empty), DISCK (empty), DISH (empty), DNB (empty), DNR (empty), DO (empty), DRE (empty), DTV (empty), DWDP (empty), ENDP (empty), ESRX (empty), ESV (empty), ETFC (empty), EVHC (empty), FDO (empty), FL (empty), FLIR (empty), FRC (empty), FTR (empty), GAS (empty), GGP (empty), GMCR (empty), GPS (empty), HAR (empty), HBI (empty), HCBK (empty), HES (empty), HOLX (empty), HOT (empty), HSP (empty), IPG (empty), JNPR (empty), JOY (empty), JWN (empty), K (empty), KORS (empty), KRFT (empty), KSU (empty), LLL (empty), LLTC (empty), LM (empty), LMCA (empty), LMCK (empty), LO (empty), LVLT (empty), MJN (empty), MNK (empty), MON (empty), MRO (empty), MWV (empty), MXIM (empty), NBL (empty), NDOI (empty), NLSN (empty), PBCT (empty), PCP (empty), PDCO (empty), PETM (empty), PLL (empty), PX (empty), PXD (empty), QEP (empty), QRTEA (empty), RAI (empty), RHT (empty), RTN (empty), SATS (empty), SCG (empty), SEE (empty), SGEN (empty), SHPG (empty), SIAL (empty), SIVB (empty), SNI (empty), SPLK (empty), SRCL (empty), STJ (empty), SWN (empty), SWY (empty), TEG (empty), TGNA (empty), TIF (empty), TSS (empty), TWC (empty), TWTR (empty), TWX (empty), VAR (empty), VIAB (empty), WBA (empty), WCG (empty), WFM (empty), WFMI (empty), WIN (empty), WRK (empty), WYND (empty), XEC (empty), XL (empty), XLNX (empty), YHOO (empty)
- bars: 1,817,429 rows across 663 symbols; SPY 2015-01-02 → 2026-10-02, 2,955 rows of 2,955 NYSE sessions in that range (no gap)
- coverage: `all_symbols(since=2015-01-02)` = 796 (ever-members ∪ SPY), of which 663 have bars; 133 missing, all logged `empty`; unexplained missing: none (`unexplained=[]`); no symbol in `bars` outside `all_symbols`. 99 of the 663 start after 2015-01-02 (listed or spun off later), so they hold their full available history rather than 10 years
- fx_rates: 3,009 rows, 2015-01-02 → 2026-10-02 (Frankfurter, every day it publishes)
- `pg_total_relation_size('bars')`: 177 MB (185,729,024 bytes), under the 400 MB stop line · database: 186 MB
- seed guard: `npm run db:seed-demo` → "Error: Real bars exist (backfill ran); refusing to overwrite with demo data." (thrown at `seed-demo.mjs:103`, before `BEGIN`), exit 1; bars still 1,817,429, strategies 4, runs 0

**nightly:** run 1 (06:23 UTC Sat) "now 2026-10-03T06:23:27Z -> data_date 2026-10-02, session_date 2026-10-05; bars already reach 2026-10-02; no sessions to fetch; wrote 0 bars over 0 session(s), 0 split(s) recorded (0 applied), fx 2026-10-02=17950.0000 (0 changed), run 1 success", exit 0. Because the backfill already reached `data_date`, run 1 made no Massive call. A separate read-only probe (`massive.Client.grouped(2026-10-02)` with the real key) returned closes identical to the backfilled bars (SPY 769.64, AAPL 333.69, MSFT 517.53, BRK.B 502.65) and 8 splits for that day, so the key and endpoint work. The first Massive write happens on the first scheduled nightly (Mon 2026-10-05 23:00 UTC) · run 2 "session 2026-10-05 already succeeded; nothing to do", exit 0 · dry run "already succeeded; nothing to do", transactions rolled back, exit 0
- runs row: id 1, status success, data_date 2026-10-02, session_date 2026-10-05 (the only real row) = `dates.run_dates(now)` `RunDates(data_date=2026-10-02, session_date=2026-10-05)`; assertion "runs dates: ok"
- fingerprints after run 1 / run 2 / dry run:

| table | rows | after run 1 | after run 2 | after dry run |
|---|---|---|---|---|
| bars | 1,817,429 | 1048483982293959805141698 | 1048483982293959805141698 | 1048483982293959805141698 |
| fx_rates | 3,009 | 1744655359371504148756 | 1744655359371504148756 | 1744655359371504148756 |
| runs | 1 | 43327952163727168 | 43327952163727168 | 43327952163727168 |
| universe | 1,544 | 890326075855417493314 | 890326075855417493314 | 890326075855417493314 |
| split_adjustments | 0 | 0 | 0 | 0 |
| backfill_log | 796 | 461998260082261274523 | 461998260082261274523 | 461998260082261274523 |

**Web read path:** over the pooled `DATABASE_URL` with `@neondatabase/serverless`: `run {session_date: 2026-10-05, data_date: 2026-10-02, is_demo: false}`, `fx {2026-10-02, usd_idr 17950.0000}`, `spy {2026-10-02, close 769.6400}`, `demoRuns 0`. `web/lib/session.ts` evaluated at 2026-10-03T06:26Z: `nextUsSession = 2026-10-05`, `isStale(2026-10-05) = false`, so no stale screen and no "Demo data" badge

### Acceptance (handover §6)

- [x] 1. Migration `002_engine.sql` adds `universe` (symbol, index, start/end) plus `split_adjustments`, `backfill_log`, `runs_real_session_uidx`; applied by the Python runner through `schema_migrations`. Evidence: migrate line above (`001_init.sql, 002_engine.sql`, three tables and the index present, second migrate "nothing to apply"); `engine/tests/test_migrate.py` (7 tests)
- [x] 2. `bars` holds ≥ 10 years for every fetchable ever-member; the rest are logged. Evidence: backfill lines above. 663 symbols / 1,817,429 rows from 2015-01-02 (later listings from their first day), SPY 2,955/2,955 sessions; the 133 unfetchable symbols are all in `backfill_log` as `empty` and listed above; 0 `failed`; no current member missing
- [x] 3. Nightly run twice for the same date leaves identical contents. Evidence: fingerprint table above, identical after run 1, run 2 and the dry run (`diff` empty); run 2 logged "already succeeded"; plus `test_same_now_twice_leaves_identical_tables`
- [x] 4. Friday → Monday (Tuesday after a Monday holiday); pre-holiday skips the holiday. Evidence: `test_run_dates` (25 cases: Fri→Mon, Labor Day / Memorial Day Fri→Tue, runs on the holiday Monday, Thanksgiving skip to the half day, Good Friday, year end), `test_last_completed_session_across_dst`, `test_sessions_inclusive_and_skip_holidays`, `test_next_and_prev_session` in `engine/tests/test_dates.py`, plus the live row (2026-10-02 Fri → 2026-10-05 Mon)
- [x] 5. A failed fetch writes `failed` + `error` and no partial bars; the web shows stale. Evidence: `test_massive_failure_marks_run_failed_and_writes_no_bars_then_rerun_reuses_row`, `test_fx_failure_marks_run_failed_and_writes_no_bars`, `test_empty_grouped_marks_run_failed`, `test_coverage_below_90_percent_fails`, `test_dry_run_failure_writes_nothing` in `engine/tests/test_nightly.py`. Stale display: a failed run is not `status='success'`, so the web keeps the previous session and `isStale` is true; not forced on Neon on purpose (it would leave a failed row for a real session)
- [x] 6. First real run removes all `is_demo` data atomically. Evidence: Before/Demo purge lines above
- [x] 7. Unit tests for dates, adjustment, idempotent upserts; dry-run writes nothing. Evidence: 216 passed, 0 skipped. Collected per file: dates 37 (parametrised), splits/adjustment 20, bars 12, fx 7, runs 8, backfill 32, nightly 22, membership 29 plus the unchanged dry-run fingerprints for universe refresh and nightly

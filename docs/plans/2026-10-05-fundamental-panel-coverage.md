# Fundamental panel coverage — decision doc

**Date:** 2026-10-05
**Status:** ready to plan
**Predecessor:** `docs/plans/2026-10-05-delisted-and-fundamentals.md` §3 (Gap B), landed as
`EDGAR_FUNDAMENTALS_PLAN.md` / merge `cf08103`
**Input to:** `/analyze`

The EDGAR fundamentals pipeline shipped and works. The first real use of it — lab method
M0005 — produced six rejected trials that measure **nothing about fundamental factors**,
because the panel it ranked on covers 4% of the lab's dev window. This doc is the measured
case for fixing that, and the boundary of what fixing it can achieve.

**Everything proposed here is free.** No subscription, no vendor, no purchase. The $199
Massive Advanced gate in the predecessor doc is Gap A (delisted price *bars*) and is unrelated
to anything below.

---

## 1. What the M0005 run found

### 1.1 The panel can rank nobody for 19 of 19.8 years

The lab's dev window is **1996-01-03 .. 2015-10-16**. Measured against the store built
2026-10-05 (`fingerprint e597367b…`), counting symbols whose snapshot actually carries
observations:

```
1996-06-30 .. 2014-06-30:    0 of 780 rankable   (sampled every 2 years — all zero)
2015-01-28 :   25 of 780
2015-02-28 :  428 of 780
2015-03-28 :  489 of 780
2015-06-28 :  507 of 780
2015-10-28 :  521 of 780
```

Coverage is not thin, it is **zero** until 2015-01. The book held cash for 19 of 19.8 years and
then had roughly eight months of signal.

That is what the six trials recorded. All six "failed: beats SPY TR; >= 100 trades", with
15–32 trades over 19.8 years against a `>= 100` gate, CAGR +0.2% at maxDD 8–13%, and
"worst year 1996 +0.0%" for a year in which the strategy could not have held anything. The
method's own pre-registered "Expected failure" paragraph predicted exactly this, and nobody
checked it before running.

`lab show M0005` carries the full analysis as two notes. **M0005 is `rejected` and its six
`config_digest`s are spent; the hypothesis is untested, not refuted.** `runner.preflight`
permits a re-test as `source_kind='variation'`, `parent_id='M0005'`.

### 1.2 Two cuts compose, and neither is visible from the store

1. **The ingest's filed-date floor.** `commands/fundamentals.py:67` sets
   `DEFAULT_SINCE_FILED = date(2013, 1, 1)`. The run kept 1,228,822 facts filed
   2013-01-02 .. 2026-10-02.
2. **The CIK map's interval floor.** The panel is `fundamental_facts` JOINED to `ticker_cik`
   **by date**, and **525 of 798** rows in `engine/data/ticker_cik.csv` start exactly
   `2015-01-02` — because the set's scope predicate was "ever-members since 2015-01-02". The
   join therefore drops the **181,491 facts filed before 2015-01-02 that are already stored**,
   and has no map row at all to join anything earlier to.

So the panel could never have reached past 2015, however the ingest was run. Cut 2 dominates
cut 1.

### 1.3 Presence is never evidence of coverage in this subsystem

Two gates were applied before the run and both are vacuous:

- **The runbook's gate** — "does the manifest list `fundamentals.csv`" — is binary where the
  risk is continuous. A store carrying 4% coverage passes it.
- **A snapshot-presence check.** `panel.as_of(symbol, t)` **always returns a `Snapshot`**: an
  empty husk with `observations == {}` when no fact is known. It never returns `None`. So
  `sum(1 for s in syms if panel.as_of(s, t) is not None)` counts every symbol in every year.
  The run was pre-flighted with exactly that, sampled at `2015-06-30` — a date inside the
  covered sliver — and reported "400/400 snapshots", which would have read 780/780 for 1996.

The root cause is a deliberate and defensible design: the fundamentals layer answers every
query and encodes "nothing known yet" as *empty content* rather than an absent result, which is
what lets `Market` carry `EMPTY_PANEL` and every allocator keep working. The cost is that every
existence check in this subsystem is a lie. **Check content.**

`docs/runbooks/data-pipeline.md` now carries the corrected snippet and this failure next to it
(commit `83c13b4`).

---

## 2. Fix A — re-vendor `ticker_cik.csv` with real membership intervals

**This is the dominant fix and it needs no downloads.** The 2013–2014 facts are already in the
local database; they are being discarded by a join against dates we clamped ourselves.

The clamp is also **simply wrong as data**. `ticker_cik.csv` claims 525 symbols became
identifiable on 2015-01-02. They did not — that is the date the *scope predicate* starts, not
the date those companies were index members. `engine/data/sp500_history.csv` carries **2,720
snapshots back to 1996-01-02** and `ndx_history.csv` 112 back to 2007-02-01, so the real
first-membership date for each symbol is already in the tree, and `membership.build_intervals`
already computes intervals from them.

What the re-vendor must preserve, because it is the reason the file exists:

- **A recycled ticker must still resolve to the holder during membership, never the current
  one.** The six measured cases are `CA`, `MON`, `PLL`, `ALTR`, `LLL`, `DTV`. They are defended
  against in the **data**, by truncating the row at the handover and omitting the new holder
  entirely — extending a *start* date backwards does not weaken that, but the generator must not
  extend an *end* date forwards.
- `K` → `0000055067` (Kellanova), and `0000039899` (TEGNA) must not be it.
- The single `NONE` row (`NDOI`) must stay the symbol's only row.
- `source` stays in the five tier labels (`current`, `edgar`, `exact`, `fuzzy`, `manual`); the
  `ticker_cik` CHECK constraint is already widened to them.
- **Zero `fuzzy` rows ship.** The periodic-filing screen passed a *wrong company* once
  (`difflib` matched "Harman International Industries" to "AMERICAN INTERNATIONAL INDUSTRIES",
  `0001073146`; real HAR is `0000800459`). `engine/data/SOURCES.md` requires every fuzzy row be
  read by hand, and the shipped file has none.
- `SCREEN_EXEMPT`'s 11 symbols stay exempt, each for its recorded reason: FDIC §12(i) bank
  filers absent from EDGAR (`FRC`, `SBNY`), spans shorter than a reporting cycle (`SWY`,
  `PETM`, `FCPT`, `VSNT`), and recently-opened current spans (`BE`, `NBIS`, `P`, `RDDT`,
  `VMRK`).

A new risk this fix introduces, which did not exist while every interval started in 2015:
**extending starts backwards can create a ticker that was held by two different companies
inside one longer window.** `cik.load_ticker_cik` already rejects overlapping intervals for one
ticker, and `resolve_window_ciks` now returns *every* filer in the window rather than refusing —
so a genuine pre-2015 handover must be split into two dated rows, not merged. Expect new cases:
the further back the intervals reach, the more recycling they cross.

## 3. Fix B — re-ingest at `--since-filed 2009-01-01`

Also free, and **the same 776 SEC requests**: `companyfacts` returns a filer's entire history in
one call regardless of our floor, so lowering it only stops us discarding rows we already
fetched.

```bash
SEER_ENV_FILE=.env.local-train engine/.venv/bin/python -m seer_engine fundamentals \
    --since-filed 2009-01-01 --retry-failed
```

The flag already exists (`commands/fundamentals.py:219`) and its help string already says
"widening costs a re-ingest". Measured rate on this host: **1–3 s per filer**, so the whole run
is ~13 minutes, not the 7–60 s/request the original plan feared.

**Unmeasured, and phase 1 of the new plan should measure it before anything depends on it:** how
much 2009–2012 data actually exists. XBRL phased in by filer size (large accelerated filers from
roughly FY2009, all filers by FY2011), so coverage in 2009–2010 will be partial and
size-biased. The current store holds ~90k facts per year from 2013 on; if 2009–2012 come in much
thinner, that is the real floor rather than 2009.

## 4. The hard limit: pre-2009 does not exist

**No amount of money or work recovers 1996–2008 fundamentals from EDGAR.** XBRL did not exist.
That is thirteen of the dev window's nineteen years, permanently unavailable from this source.
Compustat sells point-in-time pre-2009 fundamentals; it is expensive, licence-encumbered, and
has its own restatement-vintage problems. **Out of scope — do not plan for it.**

Honest accounting of what the two fixes reach:

| State | Cost | Coverage of the 19.8-year dev window |
|---|---|---|
| today | — | **4%** (zero until 2015) |
| + Fix A (re-vendor intervals) | a CSV regeneration, no downloads | ~14% (2013 →) |
| + Fix B (`--since-filed 2009`) | ~13 min, 776 free requests, ~250 MB **local** | **~30%** (2009 →), XBRL-limited |
| 1996–2008 | impossible at any price | — |

## 5. What this does NOT fix

**30% coverage will not produce a method that passes this lab's gates**, and the plan must not
pretend otherwise. `>= 100 trades` over a window two-thirds of which holds cash is not
reachable. Fix A and Fix B make the *data* honest; they do not make the *test* valid.

The test problem is a window mismatch and it is a **separate decision, deliberately out of scope
here**: this lab's dev window opens in 1996 and its fundamentals start in 2009 at best. The three
options were recorded in the runbook; the only one that yields a valid test is running
fundamentals methods on the **post-2015 held-out test window**, which this lab has never used
(`test-window looks used: 0`). That window can be spent once. **Do not spend it in this plan.**

Giving fundamentals methods their own shorter dev window is the other candidate, and its cost is
concrete: it breaks comparability with the 64 trials recorded against 1996–2015 and changes the
DSR's `N`.

## 6. Known defects to fold in

Found during the first live run; none is fixed, all are cheap, all are in this area.

1. **`paper/store.py:1035` drops the new field.** `load_market_window` builds
   `Market(history=…, membership=…, fx=…)` with no `fundamentals`, so it silently gets
   `EMPTY_PANEL`. Phase 6 of the predecessor plan enumerated five `Market`-construction sites
   and missed this one — the site where the *nightly paper run* builds its `Market`. Latent
   today (`FND` is not in `paper/roster.py` and M0005 is unrun), but the day a `MarketAware`
   allocator enters paper it ranks nobody, silently. **This is the fourth instance of one
   pattern: an interface that exists but is not adopted at every site.** The other three were
   fixed in `20dd7ab` and `b76b38d`.
2. **A `--coverage` check has no home.** The corrected snippet lives in the runbook as copy-paste
   Python. It belongs in the engine — a `lab run` preflight refusal, or a
   `fundamentals coverage` subcommand — so that no future method can be run against a panel
   that cannot rank. This is the single highest-value item in this doc: it is what would have
   saved M0005.
3. **`http.get_json` takes no `headers` argument**, which is why `finnhub.py` and `sec.py` each
   reimplement its retry loop. Noted by phase 3, owned by nobody, serves no requirement here.
   Fold in only if a phase is already touching `http.py`.

## 7. Current state of the system

So a planner does not have to rediscover it.

- **`main` is at `83c13b4`.** The set merged at `cf08103`; `005_fundamentals.sql` is applied to
  production and verified against the database (three tables, PK
  `(cik, taxonomy, tag, unit, period_start, period_end, accn)`, `period_start NOT NULL`,
  `fundamentals_log` keyed by `cik`).
- **Neon is 187 MB**, down from 571 MB. `fundamental_facts` and `fundamentals_log` are
  **truncated there**; `ticker_cik` (797 rows, 224 kB) is kept because any future inference
  slice must join against it. `005` remains recorded in `schema_migrations`, so the schema is
  honest: the tables exist and are empty.
- **Train/eval is local.** `.env.local-train` (gitignored) points `DATABASE_URL_UNPOOLED` at the
  `seer-pg` container on 55432. `config.env_file()` already supported this, so no code change
  was needed. The local database holds all 1,228,822 facts, verified identical to what Neon
  held by an order-independent per-row hash.
- **Nothing in production reads `fundamental_facts`** — `research_store` pulls bars and
  dividends from yfinance and FX from Frankfurter, so the only database read in the whole
  train/eval pipeline is `fundamental_facts ⋈ ticker_cik`. That is why moving it local cost
  nothing.
- **The store syncs between laptops** via `/sync-research-store` (`push`/`pull`,
  content-addressed on the manifest fingerprint, Vercel Blob). The current store is pushed at
  41.8 MB compressed. Two rebuilds produce two different fingerprints because yfinance answers
  differently day to day, so copying — not rebuilding — is what keeps one comparable history.
- **`SEC_CONTACT_EMAIL` is set** in `.env.local` and `.env.local-train`. It is not a credential:
  SEC's fair-access policy just wants a reachable contact in the `User-Agent`.
- **28 facts carry `filed < period_end`** — EDGAR's own tagging errors, e.g. CIK 6201 reporting
  shares outstanding for period 2027-07-17 in a filing dated 2026-07-23. `facts_from_frame`
  drops and counts them (`b76b38d`); 18 survive the `ticker_cik` join and are logged on every
  load. Expect that count to rise as the window widens.

## 8. Decision

**Do Fix A and Fix B, and build the coverage gate.** All three are free, all three are local,
and Fix A corrects a factual error in shipped data (525 rows claiming a membership date that is
not theirs).

Explicitly **not** in this plan:

- The test-window decision (§5). It is one irreversible spend and deserves its own doc.
- Pre-2009 fundamentals from any paid vendor (§4).
- Gap A / delisted price bars / the $199 Massive gate. Unrelated.
- Re-running M0005. Its id is spent; a re-test is a new variation method, and it should not be
  minted until the coverage gate reports a number worth testing.

The success criterion is **not** "a fundamentals method beats SPY". It is:

1. `ticker_cik.csv` carries each symbol's real first-membership interval, with every invariant
   in §2 still enforced by tests.
2. The panel's coverage is measured and reported across the whole dev window, by a check that
   lives in the engine rather than in a runbook snippet.
3. That number is honest — if it lands near 30%, the plan says so and does not claim the test
   problem is solved.

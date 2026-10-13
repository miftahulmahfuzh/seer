# Scoping: a new data source for the lab

*2026-10-13. Scoping note — no code, no purchase, no trial, no test look. Every number is read
from the committed lab, the committed survivorship report, or the repo's own source. Read-only:
`lab/lab.sqlite` was opened `mode=ro` and its hash did not change.*

## The question

The lab has 81 recorded methods and **zero** are promotable. Two learning methods have failed
(M0130 could not pick, M0132 could not size). The kin gate turns out not to be over-reaching: the
books the lab would actually test correlate **0.93 to 0.96** with books that already spent a test
look and failed. That is a property of the strategy space, not of the rules guarding it — so the
question is whether a different *universe* can produce a candidate that is genuinely new.

## What the lab has today

| | |
|---|---|
| **Universe** | S&P 500 ∪ Nasdaq-100, point-in-time, from vendored CSV snapshots (`engine/data/sp500_history.csv`, `ndx_history.csv`) — **large caps by construction** |
| **Screen** | top 20 by **dollar volume** (market cap is unusable: unadjusted share count × split-adjusted close) |
| **Bars** | yfinance, free. Prices **59%** of index-member days 1996–2015 |
| **Fundamentals** | SEC EDGAR, **starts 2009** — a panel-gated method is all-cash for 13 of the dev window's 20 years |
| **Side** | long only |

The universe is the thing nothing has varied. Every one of the 81 methods ranks the same few
hundred large caps on the same seven price-and-dividend signals, long only. That is a sufficient
explanation for 0.93–0.96 correlations without anyone doing anything wrong.

## What was already bought, and what it said

**This is the part that changes the scoping, and it is easy to miss: the paid data was already
bought once.** In October 2026 one month of EODHD US history filled the **522** index members
yfinance never served — mostly bankruptcies, buyouts and renamed tickers — into a second store
`engine/.research-sv`. 102 variants of 22 strategies were re-run on both histories. Every one
reproduced its recorded result exactly on the old history first, so the differences are the added
companies and nothing else.

Coverage went **59% → 89%** of index-member days. What it found
(`docs/lab/survivorship/insight.md`):

- Average edge loss **~0.5 points a year** — small, and the headline nobody should stop at.
- **Momentum drawdowns deepened by 2.6 points on average**, and **nine** momentum versions that
  had sat inside the 20% line went over it.
- **Eleven** versions in total crossed the 20% drawdown line; **none** moved the other way.
- **Six** versions stopped beating SPY; one started. All six had been under two points ahead.
- Several lost walk-forward folds: the earnings-jump book and the dividend-cut alarm 3 → 1.

**What is still missing even in the fuller history:** 111 members (~5% of index days), and 1996–97
remain under 50% covered, because the bought histories for dead companies mostly begin end-1997.

## The measurement nobody has acted on

The §1 real-money bar is **max drawdown ≤ 20%**. The survivorship check says momentum drawdowns run
**2.6 points deeper** on honest data. Those two facts have never been put together. Doing it now,
over all 399 recorded dev trials:

| Drawdown band | trials | methods |
|---|---|---|
| ≤ 15.0% — safe even if 5 points deeper | 23 | 8 |
| 15.0–17.4% — safe at −2.6 points | 16 | 11 |
| **17.4–20.0% — passes today, fails if 2.6 points deeper** | **54** | **31** |
| ≥ 20.0% — already fails | 306 | 70 |

**306 of 399 dev trials (77%) already fail the drawdown bar. Of the 93 that pass, 54 — 58% — sit in
the band the already-bought data says would push them over.** More than half of the lab's drawdown
passes may be survivorship artifacts, and this is knowable today without buying anything.

**Superseded, and sharpened — measured per variant rather than averaged (2026-10-13).** The table
above reasons with the 2.6-point momentum average; the committed `grid.csv` holds the real
per-variant numbers, and they are better evidence. Of the **28** variants that pass the 20% bar on
the dev store, **11 cross it on the fuller history — 39%**. The deltas run **−9.03 to +14.44
points**, mean **+1.42**, so no single haircut can stand in for the measurement. The books that
break are the lab's best: `M0007-N20-RAW` 19.59% → **23.46%**, `M0020-W-NOSTOP` 19.27% → **23.42%**,
`M0019-RAW20-S15` 18.56% → **24.48%**. This is recorded as §17 of the design doc, with the rule it
implies. The 2.6-point reasoning below is kept only to show what the average suggested before the
per-variant numbers were read.

It lands on the methods that matter. Among the ten dev-eligible, kin-blocked methods, the
at-risk band holds `M0030-C50T` (18.56%), `M0030-C70T` (18.77%), `M0020-W-S20` (18.88%),
`M0019-RAW20-S15` (18.56%), `M0053-TOTON20-TV16` (18.78%). And the variants with the *safest*
drawdowns are mostly the twins — `M0019-TV14N21-S20` at 12.5% is a 0.980 twin of a failed book.

## The three gaps, scoped

### Gap A — finish the existing universe
111 symbols, ~5% of index days, plus thin 1996–97. **Cost:** another EODHD month and a store
rebuild. **Benefit: low.** The headline finding is already in hand and another 5% will not
overturn it. **Not recommended as a first move.**

### Gap B — small caps
The untested dimension the lab's own journal names, and where the published research that
motivated several of these ideas finds most of its edge.

- **You probably do not need an index-membership source.** The lab already ranks by dollar volume,
  not market cap. A small-cap universe can be defined as *dollar-volume rank N…M* over a wide bar
  set — no Russell 2000 point-in-time licence required.
- **But survivorship is the whole problem, not a caveat.** Free data already loses 41% of
  *large-cap* member-days. Small-cap delisting rates are multiples higher, so a free small-cap
  universe would be dominated by the bias — strictly worse than useless, because it would look
  like an edge.
- **It therefore requires paid full history including delisted names**, which is exactly what the
  October EODHD month proved the repo can ingest: `eodhd.py`, the cache layout, and
  `survivorship.py`'s cleaning rules all exist and are tested.
- **Unknown to price before buying:** how far back EODHD's delisted small-cap coverage actually
  goes, and how many symbols and API calls a rank-500–2000 universe needs. That is a feasibility
  check against the demo token and the symbol lists, not a purchase.

### Gap C — the short side — CLOSED, 2026-10-13
**Answered: Gotrade does not support short selling.** Not an inference — the vendor's own help
centre says so outright (`help.heygotrade.com/en/articles/5985254-can-i-short-sell-a-stock`:
*"No, short selling is not available on the Gotrade platform at this time."*). Recorded as design
doc §16. The short side leaves the roadmap until the vendor changes, and the published edges that
live there are out of reach by construction.

This matters because §1 requires the strategy to be deployable with real money. A short-side method
that cannot be traded burns a method id for a book the owner can never hold — the same mistake as
a fundamentals-gated method that is all-cash for 13 of 20 years. **One question to the app settles
whether this gap exists. Ask it before spending anything on it.**

## The constraint that governs all of it — and the precedent that avoids it

§12 of the design doc gives the standing reason not to buy: *"rebuilding `engine/.research` from a
different source changes every `config_digest`, which resets all recorded trials and their DSRs."*
That is real and it would cost the entire lab record — 81 methods, 399 dev trials, every DSR, the
N policy's denominator.

**But the survivorship store is the precedent that it does not have to.** It added a whole
corrected price history as a **second, separately fingerprinted store**, left the dev store frozen,
re-ran 102 variants as a *report*, and moved neither the trial count nor the test looks. A
small-cap universe can be added the same way: a new store, a new universe source, new methods
pre-registered against it, and the existing record untouched.

So "buy data" and "reset the lab" are not the same decision, and the second one is avoidable.

## Recommendation, in order

1. ~~**Ask whether Gotrade supports short selling.**~~ **DONE 2026-10-13 — the answer is no**, from
   Gotrade's help centre. Gap C is closed and recorded as design doc §16.
2. **Act on the drawdown finding before buying anything.** 54 trials across 31 methods pass the
   20% bar on data known to be optimistic by ~2.6 points for momentum books. Deciding how the lab
   should treat that band — a haircut, a flag, or a required re-check against the fuller history
   before promotion — costs no money and changes which methods are worth testing at all. The
   survivorship report's own closing instruction already points here: *"the next batch should do
   so before trusting any momentum result whose worst fall sits just under 20%."*
3. **Then price Gap B as a feasibility check, not a purchase.** How far back EODHD's delisted
   small-cap history goes, how many symbols a dollar-volume rank-500–2000 universe needs, and what
   that costs in API calls and plan tier. The ingestion path already exists and is tested.
4. **Do not rebuild `engine/.research`.** Anything new goes in a new store.

## What this note deliberately does not do

It spends no test look, promotes nothing, records no trial, and buys nothing. It does not revisit
the §1 bar, and it does not claim the survivorship check settles whether the lab's edges are real —
that check was explicitly a second opinion, and 1996–97 remain under half covered in both
histories.

---

## Gap B priced, 2026-10-13: it fits only if the universe is kept small

Measured on this machine, not estimated.

**What a small-cap store would cost to buy.** Nothing that matters.

| | |
|---|---|
| EODHD tier with 30+ years of US end-of-day | **Historian, $19.99/month** (Sandbox is free but 1 year of history and 20 calls/day) |
| API budget | 100,000 calls/day, 1,000/minute on every paid tier |
| Calls needed | 3 per symbol (`eod`, `splits`, `dividends`) — **~4,500 calls for a 1,500-symbol universe**, under 5% of one day's budget |
| Symbol discovery | `exchange-symbol-list/US` for active names, the same endpoint with `delisted=1` for dead ones. The two sets do not overlap, so both are needed. ~51,600 active US tickers across all venues |

The purchase is one month, under $20, and the ingestion path already exists and is tested
(`eodhd.py`, the `engine/.cache/eodhd` layout, `survivorship.py`'s cleaning rules). **Money and API
limits are not the constraint.**

**What is the constraint: memory.** The research store is loaded whole into RAM. Measured on the
committed dev store:

| | |
|---|---|
| `engine/.research` | 2,490,793 bar rows, 539 symbols served, 271 MB on disk |
| Peak RSS to load it | **965 MB**, in 13.6 s |
| Derived | **388 bytes per bar row**, ~4,620 rows per symbol, **~1.79 MB of RAM per symbol** |
| This machine | 16 GB total, **~12 GB available**, 768 GB disk free |

Disk is irrelevant. RAM decides it:

| universe size (distinct symbols over 1996–2015) | bar rows | RAM to load | verdict |
|---|---|---|---|
| 1,500 | ~7M | **~2.7 GB** | comfortable |
| 3,000 | ~14M | ~5.4 GB | workable, less headroom for the simulation itself |
| 5,000 | ~23M | ~8.9 GB | tight — little left for the run |
| 8,000 | ~37M | **~14.3 GB** | **does not fit** |

A dollar-volume rank 500–2000 universe is 1,500 names *live at any moment*; over twenty years of
turnover and delisting the distinct-symbol count is several times that — the large-cap universe
needed 1,061 requested symbols to cover ~500 live members, and small caps turn over far faster. So
the natural reading of "small caps" lands in the 5,000–8,000 band, which is exactly where this
machine stops.

*(The estimate is deliberately pessimistic: small-cap names have shorter histories than S&P 500
members, so rows-per-symbol will come in under 4,620. It errs toward not fitting.)*

**What that means for the shape of the work.** Do not attempt the whole small-cap tail. Two ways to
stay inside the budget, both of which still deliver a genuinely new universe:

1. **A narrow slice.** Dollar-volume rank 500–1000 — 500 live names, perhaps 1,200–1,800 distinct
   over the window, **~2.2–3.2 GB**. Still completely disjoint from the twenty names every current
   method ranks, which is the entire point.
2. **A shorter window.** The EDGAR panel starts in 2009 regardless, so a 2009–2015 small-cap store
   is roughly a third of the rows for the same symbol count.

**The one thing to confirm before paying.** Whether EODHD's *delisted* US coverage actually reaches
back to 1996 for small caps. It reached back far enough for the 522 dead large caps bought in
October 2026, but those histories mostly began at the end of 1997 — which is why 1996–97 is still
under half covered in both stores. Small caps are likelier to be worse, not better. The free
Sandbox tier answers this for a handful of known-dead small-cap tickers before any money is spent,
and that check is the honest next step rather than a subscription.

**Still true, and still the governing constraint:** whatever is built goes in a **new store** with
its own fingerprint. Rebuilding `engine/.research` would move every recorded `config_digest` and
reset 399 trials and their DSRs, and the survivorship store already proves a second store avoids it.

---

## The coverage check, done 2026-10-13 — and the free route does not exist

**Correction to the step proposed above.** The previous section said the free Sandbox tier could
answer "does delisted coverage reach 1996?" before paying. **It cannot**, tested directly:

| request (public `demo` token) | result |
|---|---|
| `eod/AAPL.US` from 1996-01-01 | **served** — `1996-01-02` open 32.2448. 30-year depth is real |
| `eod/ENRNQ.US` (a dead ticker) | **`Forbidden`** |
| `exchange-symbol-list/US?delisted=1` | **`Forbidden`** |

The `demo` token answers only a whitelist of large living tickers, and the free Sandbox tier holds
**1 year** of history — so neither can speak about a dead small cap in 1996. There is no free path
to that question. No EODHD token is present in this checkout either; the October subscription
lapsed and its token was removed.

**But the question is already answered, by the month that was bought.** The check store's
coverage-by-year table (`docs/lab/survivorship/README.md`) is a direct measurement of how far
EODHD's *delisted* US history reaches, over 522 dead names:

| window | check-store coverage of index-member days |
|---|---|
| 1996 | 47.0% |
| 1997 | 49.1% |
| **1998** | **84.4%** ← the cliff |
| 2002 | 88.6% |
| 2008 | 95.7% |
| 2009 | 96.8% |
| 2015 | 98.8% |

**Delisted histories effectively begin at the end of 1997.** That is a property of the vendor's
data start, not of company size, so a small-cap pull will not do better before 1998 and may do
worse. **The 1996-start question is settled: no, and no purchase was needed to settle it.**

### What that does to the window — and it resolves the memory problem

The memory ceiling and the coverage cliff pull the same way, and together they pick the window:

| window | years | rows/symbol | RAM/symbol | 3,000 symbols | 5,000 | 8,000 |
|---|---|---|---|---|---|---|
| 1996–2015 (as now) | 20 | 4,620 | 1.79 MB | 5.4 GB | 8.9 GB | **14.3 GB ✗** |
| **1998–2015** | 18 | ~4,160 | ~1.61 MB | **4.8 GB ✓** | 8.1 GB (tight) | 12.9 GB ✗ |
| 2009–2015 | 7 | ~1,617 | ~0.63 MB | 1.9 GB | 3.1 GB | **5.0 GB ✓** |

**Recommended: 1998–2015, about 3,000 distinct symbols, ~4.8 GB.** It keeps both crashes — the
dot-com bust and 2008 — sits above the coverage cliff at 84%+ rising to 98.8%, and fits this
machine with headroom for the simulation itself.

**Why not 2009–2015, even though it fits far more symbols.** That window contains **no crash**, and
the lab's whole measured edge is crash insurance: §12 found these books make 7–9% a year in
2002–2008 while SPY loses 1.4%, and *trail* SPY by about two points in 2009–2015. The SPY 200-day
gate likewise helped 0 of 22 variants after 2009. A drawdown bar of 20% tested on a window with no
crash is not a test. The extra symbols are not worth losing the only two falls in the record.

### The remaining unknown, stated honestly

How many *distinct* small-cap symbols a dollar-volume rank 500–1000 or 500–2000 screen actually
yields over 1998–2015 is still an estimate — it needs the delisted symbol list, which is behind the
paywall. If the real count lands above ~5,000 for the 1998 window, the slice must narrow (rank
500–1000 rather than 500–2000) or the window shorten. **That is a first-day question inside the
paid month, not a reason to delay it:** one $19.99 month covers the symbol list, the feasibility
count and the full pull, since 3,000 symbols × 3 calls is 9,000 of 100,000 daily calls.

**And that month is probably already running** — see the correction above. This is therefore urgent
rather than expensive: the cheapest version of this whole plan is to pull inside the subscription
that is already paid for.

## Do not let the next pull evaporate: sync the derived store to Blob

The October month's work is gone from the machine that made it. Verified 2026-10-13 on `pc` — the
very machine `docs/lab/survivorship/README.md` says the check store "lives only on":

| | |
|---|---|
| `engine/.research-sv` | absent |
| `engine/.cache/eodhd` (1,192,432 raw rows) | absent — only a `yfinance` cache remains |
| Vercel Blob, `seer/research-store/` and every other prefix | **empty: 0 blobs** |
| `.env.local`, its `2026-10-08` backup, `.env.local-train`, `.env.example` | no `EODHD_API_TOKEN` in any of them |
| git | never committed, by design — raw vendor data is under personal licence |

**What that cost, concretely.** The (D16) promote gate added today can only judge the **102
variants** recorded in `grid.csv`. With the cache intact, `lab survivorship` could measure any
method on demand and the gate would bite across the whole lab; the "unmeasured → silent" hole in
(D16) exists *because* this store is gone. Re-pulling restores a capability, not just a file.

**The rule, from here: before a paid month ends, push the derived store to Blob.** The raw vendor
data cannot be committed — that is the licence — but `engine/.research-sv` is the repo's own
cleaned artifact, Blob is private, and `engine/.research` already syncs there through
`.claude/skills/sync-research-store` at key `seer/research-store/<fingerprint>.tar.gz`. Nothing in
the licence or the tooling stands in the way; it simply was not done. **A store that exists on
exactly one machine and in no backup is one `rm` away from being a repeat purchase.** The same goes
for the token: keep it in `.env.local` for the life of the subscription, since losing it mid-month
wastes the month as surely as losing the data.

**Check the other machines before paying anything.** This check covered `pc` only. If the Lenovo or
the GPD still holds `engine/.cache/eodhd` or `engine/.research-sv`, that is the cheapest recovery
available, and `sync-research-store` is the tool for moving it here.

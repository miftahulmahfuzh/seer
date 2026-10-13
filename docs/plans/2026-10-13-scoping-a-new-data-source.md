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

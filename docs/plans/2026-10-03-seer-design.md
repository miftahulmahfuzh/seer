# Seer — Design (v0.1.0)

**Seer** = Strategic Econometric Ensemble Resolver. Personal-use web app that proposes up to
4 US stocks to buy on the next US session, each with a Limit Buy, Take Profit and Stop Loss
that map 1:1 onto a Gotrade bracket ticket.

Status: validated in brainstorming, 2026-10-03.

## 1. Goal and success criteria

The goal is **not** "make predictions". It is to **prove or disprove an edge** cheaply on
paper before real money (20,000,000 IDR) is risked.

- Benchmark: SPY buy-and-hold over the same period, net of costs.
- A strategy may trade real money only when **all** of these hold (fixed; moved only by a dated
  owner revision — see §11):
  1. ≥ 3 months of forward paper trading **and** ≥ 100 closed trades
  2. Total return beats SPY buy-and-hold over the same forward period
  3. Profit factor ≥ 1.3
  4. Max drawdown ≤ 20%  *(revised 2026-10-07; was 15% — see §11)*
  5. Passed a 10-year backtest under identical rules (quant strategies only)

## 2. Constraints from Gotrade (verified from the app)

- Limit Buy supports an exit strategy "Take profit + Stop loss" in the same ticket (bracket).
- **Whole shares only** for limit orders.
- No time-based exit → time stop is a manual action Seer reminds about.
- "Trade in all market hours" stays **off** (regular session only).
- Unverified, **assumed** (user, 2026-10-03): unfilled limit orders expire end of day; fees + slippage = 0.1% per side.

## 3. Architecture

```
GitHub Actions (cron ~06:00 WIB / 23:00 UTC, Python)
  1. Fetch EOD bars (Polygon/Massive grouped-daily) → Neon
  2. Settle pending/open mock orders for every strategy
  3. Each strategy proposes picks for its free slots (0..4)
  4. LLM writes plain-language explanation per pick
  5. Write orders, positions, equity snapshots, run log → Neon
        │
Neon Postgres (single source of truth)
        │
Vercel — Next.js, read-only UI — seertrade.site
```

- Compute lives in GitHub Actions (free, no function timeouts, Python ecosystem).
- Vercel only renders; it never computes signals.
- Home screen shows **only the champion strategy's picks**. Other strategies run silently
  and compete on the leaderboard.

### Services (all free tier)

| Need | Service |
|---|---|
| Hosting / UI | Vercel (Hobby) |
| Database | Neon Postgres |
| Scheduler + compute | GitHub Actions cron |
| EOD prices (nightly + last ~2 yrs) | Massive (ex-Polygon) free: grouped-daily = whole market in 1 call; 5 calls/min; **history limited to ~2 years** (verified 2026-10-03) |
| EOD prices (10-yr backtest backfill) | yfinance, one-off backfill run locally/in Actions (free, unofficial; no delisted tickers → survivorship caveat, **measured in §12**) |
| News (Strategy C) | Finnhub free tier |
| LLM | GLM via z.ai (Anthropic-compatible endpoint, `LLM_*` env) |
| Auth | Auth.js, **Google provider only**, single allowlisted email (`ALLOWED_EMAIL`) |
| Icons | Lucide (MIT) |
| Domain | seertrade.site (Domainesia DNS → Vercel) |
| Market calendar | `pandas_market_calendars` |

## 4. Strategies (the ensemble)

| ID | Strategy | Validation |
|---|---|---|
| A | Quant mean-reversion (initial champion) | 10-yr backtest + forward paper |
| B | ML cross-sectional ranker | walk-forward backtest + forward paper |
| C | A's candidates filtered by LLM news veto | forward paper only (LLM backtests are contaminated by training data) |

Strategy A starting rules (to be tuned in backtest, then frozen):

- Setup: close > SMA200, RSI(2) < 10, avg daily dollar volume > $20M
- Limit = prior close − 0.5 × ATR(14)
- TP = limit + 1.0 × ATR(14)
- SL = limit − 1.5 × ATR(14)
- Rank by deepest RSI(2); fill free slots

The LLM also writes a plain-language explanation for every pick (all strategies).

## 5. Shared trade rules (all strategies, backtest and live identical)

**Universe:** S&P 500 ∪ Nasdaq-100, using point-in-time membership for backtests.

**Portfolio:** 20,000,000 IDR converted to USD at start-date FX; tracked in USD, displayed
in both. 4 slots; slot size = equity ÷ 4, recomputed daily. Shares = floor(slot / limit).
Ineligible if < 1 share fits. No adding to an existing holding. 0 picks is valid.

**Order lifecycle:**

| Step | Rule |
|---|---|
| Place | Limit + TP + SL for next US session |
| Fill | Filled only if session low **<** limit (strict). If open < limit, fill at open |
| Unfilled | Expires end of session, slot freed |
| TP / SL | Evaluated from the session after fill. Both in range same day → **SL first**. Gap through either → fill at open |
| Time stop | Not exited by close of trading day 5 → exit at next open (user: cancel bracket, market sell) |
| Costs | 0.1% per side (fees + slippage) |

## 6. UI

Iron rule: **every button is icon-only** (Lucide) with `aria-label` + tooltip/long-press.
Mobile-first for iPhone XS Max (414pt, safe areas), responsive to desktop, system dark/light,
PWA standalone (manifest + apple-touch-icon).

Screens: Sign-in (single Google icon button) · Today (champion picks with copyable
Limit/TP/SL/Shares, est. cost/profit/loss USD+IDR, expandable LLM explanation, day-5
action items, empty and stale-data states) · Positions · Leaderboard (equity curves vs
SPY, metrics, go-live checklist, champion crown) · History. Bottom tab bar, 4 icons.

## 7. Data model (Neon)

`bars`, `universe`, `strategies`, `orders`, `positions`, `equity_snapshots`,
`explanations`, `runs`. Auth.js uses JWT sessions (no auth tables).

## 8. Failure handling

- Data fetch fails → retry, then mark run failed; UI shows stale-data warning and
  "do not trade". Never show picks without a successful run.
- Market holiday → no session, no picks, no day counted.
- LLM fails → explanation "unavailable"; Strategy C treats failed veto check as **no trade**.
- Splits → split-adjusted bars; open orders recomputed.
- All pipeline steps idempotent on (strategy, date).

## 9. Testing

- Fill simulator: exhaustive unit tests on synthetic bars (touch vs penetrate, gaps,
  same-bar TP+SL, time stop, holidays). Highest-priority code in the repo.
- Backtest and live paper trading share one simulator code path.
- UI: smoke tests for auth allowlist and screen rendering.

## 10. Out of scope for v0.1.0

Real-trade journal (later phase), notifications, multi-user, settings UI, intraday data,
extended-hours trading.

## 11. Revision 2026-10-07 (owner): the go-live drawdown bar is 20%

- **Go-live condition #4 is now "Max drawdown ≤ 20%."** The original sentence, preserved: *"4. Max
  drawdown ≤ 15%"*, written 2026-10-03 under the clause "fixed now, never moved".
- **Who and why.** The owner, on stated risk appetite: *"i am thinking of my risk appetite, and i
  think let's set the Max drawdown to 20% instead of 15%."* Asked explicitly whether this was a
  lab-screen change or the real-money bar as well, the owner chose **both**, after being told it
  is a real-money safety setting and shown what it touches.
- **What it does not change.** Conditions 1, 2, 3 and 5 are untouched. The no-real-money rule
  stands: nothing trades real money without ≥ 3 months of forward paper and ≥ 100 closed trades.
  The development/test window split, the one-look test-window rule and the lab's luck check are
  separate mechanisms and are not affected by this item.
- **Where it is implemented.** `backtest.metrics.MAX_DRAWDOWN`, re-exported as
  `backtest.tuning.MAX_DRAWDOWN`, is the one Python definition; `web/lib/golive.ts` is the one
  TypeScript definition, pinned to it by `web/lib/golive.test.ts` through `data/lab.json`'s gate.
  It decides the P3, P3b and P6a backtest gates, the dev lab's D8 drawdown condition, the
  in-sample grid's selection rule and the leaderboard's go-live checklist.
- **The clause that said "never moved"** is now "moved only by a dated owner revision". That is a
  weakening of a stated guarantee and is recorded here deliberately rather than edited away: the
  bar has moved exactly once, on this date, by the owner, on the record.
- **Measured effect on the lab's 110 recorded dev trials** (bar alone, holding everything else as
  committed): 30 trials change from missing the drawdown condition to meeting it. Two of them
  clear every other condition and have a recorded DSR above 0.90 — `M0020-W-NOSTOP` (fall 19.3%,
  CAGR +15.3%, MAR 0.79) and `M0007-N20-RAW` (fall 19.6%, MAR 0.77). `M0019-RAW20-S25` (fall
  20.7%) still misses it.

## 12. Measured 2026-10-07: the size of the survivorship hole

The §3 services table has always carried "no delisted tickers → survivorship caveat" as a
parenthetical. This section replaces the parenthetical with the number, because a caveat nobody
has measured is indistinguishable from one nobody has taken seriously.

**The hole.** Of the 1,041 symbols that held point-in-time S&P 500 / Nasdaq-100 membership over
the dev window, **522 have no bars in `engine/.research`** — `unserved.csv` lists them, all for
the same reason (`yfinance returned no bars`). Coverage of the index as it actually stood:

| date | members | priced | coverage |
|---|---|---|---|
| 1996-06-30 | 487 | 236 | **48.5%** |
| 2000-06-30 | 492 | 264 | 53.7% |
| 2004-06-30 | 495 | 290 | 58.6% |
| 2008-06-30 | 544 | 344 | 63.2% |
| 2012-06-30 | 525 | 374 | 71.2% |
| 2015-10-16 | 527 | 409 | **77.6%** |

Coverage rises monotonically with time, which is the signature of the bias rather than an
accident: the further back you look, the more of the index has since merged, delisted or gone
bankrupt and been dropped by a free data source. 32 of the missing symbols carry the `Q`
bankruptcy suffix (`AAMRQ`, `ABKFQ`, `DPHIQ`, …) — exactly the names a momentum book would have
bought on the way up and ridden down.

**Whether it is what produces the lab's results: apparently not.** Edge over total-return SPY,
by era, for the four quant roster entries, sliced from the recorded dev curves (no re-run, so no
trial and no movement in the lab's N):

| | SPY | RMW | RAW | MOM | MVW |
|---|---|---|---|---|---|
| 1996–2001 (~50% coverage) | +11.9%/yr, fall 30.4% | +12.8%, 12.4% | +17.8%, 16.1% | +18.1%, 11.1% | +12.6%, 14.0% |
| 2002–2008 (~60%) | **−1.4%**/yr, fall 40.5% | +8.4%, 10.1% | +9.4%, 15.2% | +6.8%, 11.7% | +7.4%, 11.6% |
| 2009–2015 (~70%) | **+16.7%**/yr, fall 16.2% | +14.6%, 9.0% | +19.3%, 10.7% | +14.4%, 10.0% | +14.6%, 10.0% |

If missing bankruptcies were inflating the results, the inflation would be **largest where
coverage is worst**. It is not: 1996–2001 is the weakest era for three of the four, and the edge
peaks in the middle-coverage era that contains two crashes.

**The limit of that test, stated rather than buried.** Coverage rises with time, so it is
collinear with regime; this cannot separate "better data" from "different market", and it has
limited power. It is evidence against the simple story, not proof the hole is harmless. A test
that isolates the mechanism — injecting synthetic delistings at the historical rate and solving
for the break-even delisting return — remains unrun and is the right next step if a decision ever
turns on this.

**Two findings that outrank the one we went looking for.**

1. The edge is crash insurance. It lives in 2002–2008, where SPY lost 1.4% a year and fell 40.5%
   while these books made 7–9% a year falling 10–15%. In 2009–2015, a bull market with no crash,
   three of the four *trail* SPY by about 2 points a year at ~60% of its drawdown. That is the
   trend gate's price, not a defect, and the leaderboard should be read knowing it.
2. `RAW-FR` (lab M0007-N20-RAW) is the only entry ahead of SPY in all three eras, at a third to
   two-thirds of the drawdown throughout.

**Why we are not buying survivorship-free data yet** (owner, 2026-10-07): the check above did not
find the damage a paid feed would repair; such a feed costs money monthly; and rebuilding
`engine/.research` from a different source changes every `config_digest`, which resets all 110
recorded trials and their DSRs. Revisit when a decision actually hinges on it. The standing answer
to this worry is forward paper trading, which cannot be flattered by survivors because the
survivors are not yet known.

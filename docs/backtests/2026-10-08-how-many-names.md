# How many names should the book hold?

**Measured:** 2026-10-08 · **Window:** 1996-01-03 → 2015-10-16 (the lab's dev window)
**Research store:** `399d0d254c7a` · **Grid:** [`2026-10-08-how-many-names-grid.csv`](2026-10-08-how-many-names-grid.csv)

## The short answer

**Twenty is fine. Keep it.** At Gotrade's real fees, on the money you will actually have, twenty
names earned more per rupiah than any other count tested and fell less from a peak than any count
below it. Holding fewer names is clearly worse — five names gave up 1.3 points of return a year and
fell 37% from a peak instead of 20%. Holding more than twenty changes almost nothing: twenty-five and
thirty land within half a point of return and a hair of the same risk-adjusted score.

That is a result, not a failure to find something. The question was whether concentration helps, and
the measurement says it does not.

## What was compared

The book the roster already trades — lab `M0007-N20-RAW`, residual momentum ranked on the raw
cumulative residual with a 200-day SPY filter — at **six** different name counts: **5, 10, 15, 20, 25
and 30**. Only the number of names changed. Same signal, same filter, same monthly rebalance, same
fractional shares.

Each count was run twice, and the whole grid was run on the money you will really have: 10,000,000
IDR at the start and 5,000,000 IDR added on the 25th of every month. The two runs differ only in what
the trades cost — Gotrade's measured fees against the flat 0.1% the lab used to assume — so the
second is a control that says whether the fees change the answer.

Because the account is fed every month, the return is **money-weighted** rather than a plain CAGR. A
deposit raises the ending balance without being a profit, so the plain yearly figure on a fed account
is meaningless: every row of this grid shows a CAGR near 37% and a total return in the tens of
thousands of percent, and none of that is money the strategy made. The money-weighted return is the
rate your own money actually earned, and it is the only return column worth reading here. SPY is
bought on the identical schedule, so "beats SPY" compares two accounts holding the same money on the
same days — and on this run it is itself a money-weighted comparison.

**SPY, fed exactly the same money, earned 7.19% a year.** Every count in the grid beat it.

## What came out

Gotrade's real fees, on the real funding schedule. "Money-weighted" is the honest return; "worst
fall" is the deepest drop from a peak; "MAR" is return divided by that worst fall, which is the lab's
own ranking measure.

| names | money-weighted | worst fall | profit factor | MAR | trades | fees | go-live misses |
|---:|---:|---:|---:|---:|---:|---:|:---|
| 5 | +12.41% | 37.1% | 1.75 | 0.33 | 430 | $79,720 | max DD ≤ 20% |
| 10 | +12.89% | 27.6% | 1.82 | 0.47 | 845 | $83,820 | max DD ≤ 20% |
| 15 | +12.83% | 21.8% | 1.89 | 0.59 | 1,222 | $85,431 | max DD ≤ 20% |
| **20** | **+13.68%** | **20.1%** | **1.98** | **0.68** | 1,607 | $90,883 | max DD ≤ 20% |
| 25 | +13.04% | 19.6% | 2.00 | 0.66 | 1,935 | $81,528 | none |
| 30 | +12.89% | 19.1% | 2.02 | 0.68 | 2,245 | $78,906 | none |

The flat 0.1% control, same runs, same schedule, only the fee model changed:

| names | money-weighted | worst fall | profit factor | MAR | fees |
|---:|---:|---:|---:|---:|---:|
| 5 | +13.75% | 36.8% | 1.86 | 0.37 | $36,526 |
| 10 | +14.19% | 27.3% | 1.94 | 0.52 | $38,284 |
| 15 | +14.18% | 21.6% | 2.03 | 0.66 | $39,058 |
| 20 | +14.96% | 20.1% | 2.11 | 0.74 | $41,273 |
| 25 | +14.31% | 19.4% | 2.14 | 0.74 | $36,969 |
| 30 | +14.13% | 18.9% | 2.16 | 0.75 | $35,595 |

**The shape.** Going from twenty names down to five costs 1.3 points of return a year and nearly
doubles the worst fall, from 20.1% to 37.1%. That is the whole finding about concentration: it is not
a trade-off with a good side, it is worse on both axes at once. Going the other way — twenty to
thirty — buys a slightly shallower fall (20.1% down to 19.1%) and gives back 0.8 points of return,
which is close enough to a wash that it should not drive a decision.

**Which count wins.** At Gotrade's fees, twenty has the highest money-weighted return (13.68%) and
the highest MAR (0.682), with thirty a whisker behind at 0.676. At the flat rate, thirty edges ahead
(0.748 against 0.744 at twenty). **That gap is 0.004 — about half a percent of the 0.35 spread
between five names and twenty.** The two fee models are choosing between three counts that are
tied; they are not disagreeing about anything that matters. The lump-sum control settles it: funded
once instead of monthly, **both** fee models pick twenty outright.

**One honest caveat.** On this funded run twenty misses the go-live condition "worst fall ≤ 20%" —
by 0.07 of a percentage point, at 20.07%. Twenty-five and thirty clear it. This is a dev-window
report and not a gate run, so it decides nothing on its own, but it is the one place in the grid
where twenty is not the plain winner and it should not be hidden.

## What it means

Keep twenty names. The measurement says concentration would cost you return and risk together, and
that the alternatives above twenty are not different enough to be worth a rebuild.

**This grid informs a decision and is not one.** Six free looks at six name counts is exactly the
kind of search the lab's luck gate exists to charge for, and this run deliberately paid nothing: it
recorded no trial, so the lab's N stayed at 126 and its test-window looks stayed at 2. Nothing here
can make any configuration eligible. If a future session wants to act on another name count, that
means a new method that pre-registers the count up front and pays for its trials like every other
method — from `M0031` on, the lab already forces such a method to run at Gotrade's real fees. The
rebuilt roster carries twenty either way.

## Why the fee argument is not the answer here

An earlier session told you that Gotrade's $0.10 per-order floor stops binding around $50 an order,
so this account should cut to ten or twelve names and save roughly 40% of its costs. That was wrong
once the funding plan is included. Measured at 17,841 IDR/USD:

| month | balance | 20 names, per order | as a % | 11 names, per order | as a % |
|---|---|---|---|---|---|
| 0 | 10M IDR | $28.03 | 1.035% | $50.96 | 0.628% |
| 1 | 15M IDR | $42.04 | 0.737% | $76.43 | 0.641% |
| 2 | 20M IDR | $56.05 | 0.660% | $101.91 | 0.618% |
| 3 | 25M IDR | $70.06 | 0.614% | $127.39 | 0.612% |
| 12 | 70M IDR | $196.18 | 0.607% | $356.69 | 0.558% |

By month three the two counts are two thousandths of one percent apart. The fee saving is a two-month
transient; the diversification it would cost is permanent. So the name count is a question about
returns, which is what this page measures.

The grid above is the measured version of the same claim. Under the lump-sum control both fee models
pick the same count, and under the funding schedule they split between twenty and thirty by four
thousandths of a MAR point while the name count itself moves MAR by 0.35 across the range. The fees
do not choose how many names you hold.

## The scale of the fees, from real money

Your own twenty Gotrade buys on 2026-10-07 cost **$2.60 in fees to put $558 to work — 0.466%, before
a single sale**. That is not a backtest; it is your receipts, reproduced through `sim.costs.fee_parts`
to the cent. It is the right number to keep in mind beside anything on this page: at a $27.90 slot,
nearly half a percent of the book is gone just opening it.

The grid says the same thing in the other direction. Compare the two tables above at any name count:
Gotrade's fees cost this book about **1.3 points of money-weighted return a year** — 13.68% against
14.96% at twenty names — while the entire range of name counts from five to thirty moves it by about
1.3 points as well. **What you pay to trade matters as much as how many names you hold.** That is the
larger finding, and it is the one the whole roster rebuild exists to deal with.

## How to reproduce this

```
PYTHONPATH=engine/src engine/.venv/bin/python -m seer_engine lab names \
  --store /home/miftah/seer/engine/.research \
  --csv docs/backtests/2026-10-08-how-many-names-grid.csv
```

The funding control is the same command with `--lump` added, which funds the account once and never
feeds it. The research store is gitignored and lives in the main checkout, so `--store` points there;
rebuilding it costs about thirty minutes for a byte-identical copy. The whole sweep takes about
thirty seconds.

Nothing on this page was recorded in the lab. The run writes no trial, no journal entry and no status
change, so the lab's N stayed at 126 and its test-window looks stayed at 2 — the report prints both,
before and after.

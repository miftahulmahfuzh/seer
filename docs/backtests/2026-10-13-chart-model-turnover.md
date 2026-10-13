# What a short-horizon chart model would pay Gotrade

**Measured:** 2026-10-13 · **Window:** ten years of the owner's funding plan, forward
**Fees:** `sim/costs.py`'s current Gotrade regime (since 2026-06-16), fitted to the owner's own
order receipts · **Rate:** 17,841 IDR/USD
**Grid:** [`2026-10-13-chart-model-turnover-grid.csv`](2026-10-13-chart-model-turnover-grid.csv) —
the same rows at full precision
**Command:** `lab turnover --csv docs/backtests/2026-10-13-chart-model-turnover-grid.csv`

## The short answer

The cheapest daily book the owner could possibly run — one name out of twenty swapped per
session — must earn **7.0% a year before it has made him a single rupiah**, which is roughly what
simply owning the market returns. A model that actually re-picks its book every session, the way
a short-horizon chart model would, must earn **290% a year**. Trading weekly instead brings that
down to **32%**. The cadence the lab already trades, on the same twenty names, costs **1.6%**.

So the short-horizon chart model is dead on arrival. Not because the model could not learn
anything — nobody knows that yet — but because the account is small enough that trading it often
costs more than any plausible edge is worth. No pattern-recognition model was written, and none
needs to be.

## Why this was measured instead of built

The alternative was weeks of model code to answer a question an hour of arithmetic settles. The
fee schedule is already measured from the owner's real receipts, the funding plan is known, and
the number of orders a cadence implies is just counting — so the cost side can be computed exactly
today, before a single line of the model exists.

There was always a second reason to doubt the idea, and it has not gone away: the data is about
five hundred names over twenty years of strongly correlated monthly samples, which is far too
little for a large pattern-recognition model to find anything that is not noise. That constraint
is real but expensive to prove. This one is cheap, it is arithmetic rather than judgement, and it
is sufficient on its own. The idea does not have to clear the learning bar, because it cannot
clear the cost bar.

## How it was measured

The account grows the way the owner's really does: 10,000,000 rupiah at the start and 5,000,000
rupiah more on the 25th of every month, converted at one fixed rate. **No return is assumed
anywhere** — the account is credited with deposits only. That is deliberately the harsh reading:
a book that earns nothing keeps the smallest positions, and small positions are where the
per-order minimum bites hardest.

The money is split equally between however many names the book holds. Each time the book is
re-picked, some share of it is replaced, and replacing a name is **two orders, not one** — the old
one is sold and the new one bought — with the sell costing a little more than the buy because it
carries an extra uncapped charge. Every single order is priced by the same code the simulator and
the paper book use, so this report and a backtest can never disagree about what an order costs.

"Break even" means this: each trade takes a slice out of the account, the slices compound over ten
years, and the number quoted is the yearly return that would exactly undo them. Nothing else is
assumed — in particular no return, which is the thing nobody knows.

## The $0.10 floor, and why it is only the first chapter

Every order pays a minimum of ten cents, so while a position is small, that minimum beats the
percentage rate and the effective cost is much higher. At twenty names the account's opening
positions are about $28, and a round trip costs **1.035%** of the position. One month later it is
0.737%, and by the third month it is **0.614%** — those two figures reproduce, digit for digit,
what the lab's name-count report already had on the record. The floor stops winning the moment a
position passes **$47.50**, which at twenty names is the owner's third month, at thirty names his
fifth, and at ten names never, because a ten-name book opens above that line already.

An earlier reading called that floor the whole answer. Measured, it is the whole answer for the
owner's first two months and almost none of the answer for his tenth year. Once the floor lets
go, a round trip settles at about **0.503%** of a position — a fifth of a percent each way, the
sell's extra, and tax on both — and that is the rate that does the killing. Multiplied by 252
round trips a year it is fatal on its own, with the floor playing no part at all. Over the full
ten years only 1.7% of a twenty-name book's orders ever pay the floor.

## The grid

Break-even — what the strategy must earn each year to be level with doing nothing — over ten
years, by how often the book is re-picked and how much of it changes each time. The lab's own
cadence is marked.

| book | re-picked | ¼ of the book | ½ of the book | all of it |
|---|---|---|---|---|
| 10 names | every session | 47.76% | 91.76% | 268.35% |
| 20 names | every session | 40.47% | 97.41% | **290.45%** |
| 30 names | every session | 45.96% | 103.32% | 314.23% |
| 10 names | every week | 8.39% | 14.38% | 30.88% |
| 20 names | every week | 7.27% | 15.08% | 32.49% |
| 30 names | every week | 8.13% | 15.79% | 34.14% |
| 10 names | every month | 1.88% | 3.15% | 6.41% |
| 20 names | every month | **1.63%** ← the lab's own | 3.29% | 6.70% |
| 30 names | every month | 1.82% | 3.44% | 7.00% |

The gentlest daily book the grid itself can express — twenty names, a quarter replaced, so five
names a session — already needs 40% a year, twenty-five times the control. Pushed below what the
table shows, to a single name of twenty swapped per session, it still needs **7.03%**; weekly at
that same single-name pace needs 1.41%, and monthly 0.32%.

The first year is worse than the ten-year average in every cell, because that is when positions
are smallest: a twenty-name book re-picked daily needs 443.66% in year one against 290.45%
averaged over ten.

## What this changes

1. **The short-horizon chart model is not pursued.** The handover's third item asked for this
   number so the idea could be killed or kept on evidence; the answer is no, and the reason is
   the cost of trading that often on an account this size, not the model.
2. **Nothing else moves.** The roster keeps its cadence and its twenty names. This report prices
   *how often a book trades*, not *how many names it holds*, and it recommends no change to the
   latter. The owner's standing instruction binds here and is quoted in full: *"do not plan a
   name-count reduction on fee grounds; if the lab tests concentration, test it on the merits."*
   The name column exists only because the per-order minimum depends on position size.
3. **A faster cadence is not forbidden — it now has a price.** Any future method that wants to
   trade weekly or daily has to register that choice in advance like everything else, and it now
   has a number to clear: weekly costs about four and a half times what the lab currently pays,
   and daily about twenty-five times.

## What this could not see

It splits the money equally and replaces the same number of names every time; a real model would
trade in uneven sizes. It assumes no price impact and no spread — both make the answer worse, not
better, so the real cost is above this one. It assumes today's fee schedule holds for ten years,
which is what every backtest here assumes. The extra charge on the sell side rests on a single
receipt and is deliberately set at the conservative end, so every sell priced here may be a shade
dear. And it says nothing at all about whether a chart model would have an edge — only how large
that edge would have to be before it was worth having.

## What was and was not recorded

Nothing. No trial, no measurements, no funding row, no status change, no journal entry. The lab's
count of development trials was **394 before the run and 394 after**, and its four spent
test-window looks were **4 before and 4 after**; the trial, measurement, funding, provenance and
journal tables all held exactly the same number of rows on both sides. The test window was never
read.

That is also this report's limit. A free sweep over twenty-seven configurations is exactly the
kind of searching the luck gate exists to charge for, so this grid may inform a decision and may
never be one. Acting on it means a new method that registers its cadence in advance and pays for
its trials like everything else.

# Learning the fall instead of the pick

**Measured:** 2026-10-13 · **Window:** 1996-01-03 → 2015-10-16 (the lab's development window)
**Research store:** `77c37d553508` (dev, unmarked) · **Prices:** `5451195fd552`
**Command:** `lab run M0132 --store engine/.research`

## The short answer

A model that forecasts how far a basket of big, heavily traded companies will fall over the coming
quarter, and holds only the share of the basket that forecast says is safe, is **much better than
having no brake at all and clearly worse than the one brake this lab already has**. Owning the
twenty names flat out was the worst thing in the run: a 74% worst fall for 4.9% a year on the
owner's real deposits. The model's sizing cut that fall to 29% for the same 4.9% a year — a large
reduction in the fall bought for nothing. But the plain SPY 200-day switch, sizing exactly the same
twenty names, cut the fall further still, to 21%, **and** earned 8.2% a year, which is more than
the same deposits put into SPY would have returned. So on the question the handover actually asked
— can a learned downside forecast improve on the switch? — the answer is no, and not narrowly: the
model gave up 7.5 points of drawdown and 3.3 points a year at the same time. Running the model
*behind* the switch gave the shallowest fall of the five arms, 18.1%, and the thinnest return,
4.7%. No variant cleared design section 1, and the method is recorded **rejected**.

## Why this was measured

The lab's own record says the constraint that binds is the fall, not the pick. Of the 394 dev
trials with a recorded return before this run, 256 (65%) beat SPY total return but only 92 (23%)
kept the worst fall at or under 20% — and out of sample it inverts, with all four spent test looks
failing on return rather than on drawdown. A two-thirds dev hit rate that vanishes out of sample is
the signature of selection, and more selection is the one thing this lab should stop buying.

Against that the lab has exactly one risk control, the SPY 200-day switch, and it has never been
improved on. So the same walk-forward, point-in-time machinery M0130 used for ranking was pointed
at a different question: not *which* names to hold, but *how much* of the book to hold.

## What was run

Five arms, fixed before any result was seen. Every arm holds the **same twenty companies** — the
screen-eligible index members with the largest 20-day dollar volume, equal weight. Dollar volume
forecasts nothing, so the only thing that differs between arms is how much of that same book is
held, and every comparison below is the sizing alone.

| Arm | How much of the book is held |
|---|---|
| `FALL20` | the model's own sizing: the share of the twenty slots the date is calmer than |
| `FALL20-REG` | the same, from the one fixed regularised tree |
| `FALL20-GATE` | the same model, and also nothing at all while the market is below its 200-day average |
| `GATE20` | **control.** Everything, or nothing at all while the market is below its 200-day average |
| `ON20` | **control.** Everything, always. No risk control of any kind |

The label is the **raw forward fall as a level** — the worst peak-to-trough drop over the next 63
sessions, in fractions — not a rank of it. The feature matrix is the lab's seven rank-normalised
per-name features plus **three un-normalised market-level columns** (the market's distance below
its trailing one-year high, its 60-session realised volatility, and the day's own momentum
dispersion), without which a level label would have nothing to read. The head locates the date's
cross-sectional *mean* forecast in the model's own training distribution of date-level means, so
**no number in the exposure ladder was chosen** — it is the model's in-sample empirical CDF, and
nothing in it was read off the dev window.

All five arms hold SPY until the end of 1999, because with a quarter-long label and 35 required
labelled month-ends the first refit with enough history is 1999-12-31.

## Did the head actually move the book? Measured twice, before the id was spent

This is the measurement that could have stopped the method for free, and it was deliberately run
twice on different days: once as phase 2's own exit criterion, and again immediately before the
pre-registration commit. Both runs are on the real dev store, read-only, and print exposure only —
no return, no drawdown.

The second run, on the January decision date of every year 2000-2015:

| | 2000 | 2001 | 2002 | 2003 | 2004 | 2005 | 2006 | 2007 |
|---|---|---|---|---|---|---|---|---|
| exposure | 0.500 | 0.350 | **0.250** | 0.450 | 0.950 | 0.850 | 0.700 | **1.000** |
| size-off control | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

| | 2008 | 2009 | 2010 | 2011 | 2012 | 2013 | 2014 | 2015 |
|---|---|---|---|---|---|---|---|---|
| exposure | **0.400** | 0.450 | 0.500 | 0.950 | 0.350 | 0.650 | 0.700 | 0.950 |
| size-off control | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

Ten distinct exposures between 0.250 and 1.000; 2008 reads 0.400 against 2005's 0.850; the size-off
control is flat at 1.000 on all sixteen lines. That reproduces phase 2's own reading line for line.
**The head works.** Whatever is wrong with this method, it is not a book that could not change its
size — and that matters, because the version of this idea that was planned first (a label ranked
within each date) would have been exactly that, and was removed before anything was pre-registered.

## The result

| Arm | Return | Worst fall | PF | MAR | Sharpe | DSR (N=81) | Owner's money | Worst year |
|---|---|---|---|---|---|---|---|---|
| `FALL20` | +19,868.6% | 28.9% | 1.58 | 0.17 | 0.65 | 0.682 | **+4.9%/yr** | 2008 −14.1% |
| `FALL20-REG` | +21,628.8% | 24.8% | 1.72 | 0.23 | 0.71 | 0.769 | **+5.7%/yr** | 2008 −12.5% |
| `FALL20-GATE` | +19,460.4% | **18.1%** | 1.90 | 0.26 | 0.71 | 0.767 | **+4.7%/yr** | 2007 −4.8% |
| `GATE20` *(control)* | **+28,802.8%** | 21.4% | **2.63** | **0.38** | 0.66 | 0.697 | **+8.2%/yr** | 2005 −8.1% |
| `ON20` *(control)* | +19,807.4% | 74.4% | 1.09 | 0.07 | 0.30 | 0.143 | **+4.9%/yr** | 2008 −44.6% |

SPY total return over the same window was +25,724.5%, and the same 237 deposits put into SPY TR
earned **+7.2% a year**. Only `GATE20` beat that.

The recorded fold verdict, quoted as `lab run` printed it:

> Walk-forward, recorded at the run of 2026-10-13T02:50:08+00:00: 1 of 4 folds, pick changed

| Fold | Scored | Picked | Got | SPY TR | |
|---|---|---|---|---|---|
| 1 | 2003-01-31 → 2005-12-30 | `FALL20-REG` | +10.4% | +52.1% | lost |
| 2 | 2006-01-31 → 2008-12-31 | `FALL20-REG` | −5.5% | −24.6% | **won** |
| 3 | 2009-01-30 → 2011-12-30 | `GATE20` | +21.3% | +60.8% | lost |
| 4 | 2012-01-31 → 2014-12-31 | `GATE20` | +59.1% | +65.9% | lost |

Two things in that table are worth more than the 1-of-4 headline. The one fold the method won is
the one containing 2008 — the model's sizing really did help through the crash. And in the two most
recent folds the selector did not pick a model arm at all; it picked the plain switch.

## What each comparison isolates

| Comparison | Worst fall | Owner's money | MAR | Reading |
|---|---|---|---|---|
| `GATE20` − `ON20` | 74.4% → 21.4% | 4.9% → 8.2%/yr | 0.07 → 0.38 | What the lab's existing brake is worth on this exact book: a great deal, on both axes at once. |
| `FALL20` − `ON20` | 74.4% → 28.9% | 4.9% → 4.9%/yr | 0.07 → 0.17 | What the learned forecast adds over nothing: 45 points of fall, for free. Real, and not nothing. |
| **`FALL20` − `GATE20`** | **28.9% vs 21.4%** | **4.9% vs 8.2%/yr** | **0.17 vs 0.38** | **The question. No** — worse on the fall *and* worse on the money, simultaneously. |
| `FALL20-GATE` − `GATE20` | 21.4% → 18.1% | 8.2% → 4.7%/yr | 0.38 → 0.26 | The model does see a little the switch had not already taken — 3.3 points of fall — and charges 3.5 points a year for it. |
| `FALL20-REG` − `FALL20` | 28.9% → 24.8% | 4.9% → 5.7%/yr | 0.17 → 0.23 | The regularised tree is better on **every** axis. See below; this one was pre-registered as a warning sign. |

## Against the hypothesis

The pre-registered bar for "the model added something", frozen before the run, was all three of:

1. `FALL20`'s worst fall at least **5 points shallower** than `GATE20`'s — it is **7.5 points
   deeper** (28.9% against 21.4%). **Failed.**
2. `FALL20`'s funded return **no more than 2 points a year behind** `GATE20`'s — it is **3.3 points
   behind** (4.9% against 8.2%). **Failed.**
3. `FALL20` beats `ON20` on MAR — 0.17 against 0.07. **Met.**

One of three. The hypothesis is not supported, and it failed on the two clauses that were the
question rather than on the floor. The separate "what counts as a method" bar — every design
section 1 criterion at DSR ≥ 0.90 — is not met by any arm: the best DSR in the run is 0.769, every
arm fails `DSR >= 0.90`, four of five fail `beats SPY TR`, and three of five breach the 20%
drawdown rule. The method is recorded **rejected** and no variant was promoted; the test window was
not touched and `test_looks` still reads 4.

## Against the expected failure

Eight failure modes were written down before the run. Which happened:

- **A slow volatility target wearing a new name** — *consistent with what happened, not proven
  here.* The shape fits: the model cut hardest in 2002, 2008 and 2012, all after volatility had
  already risen, and held a full book in January 2007. But this run measured outcomes, not the
  forecast's correlation with trailing volatility, so this stays a reading rather than a finding.
- **The ladder too coarse to matter** — **did not happen, and this is the cleanest negative
  result here.** The predicted failure was a book sitting between eighteen and twenty slots on nine
  dates in ten. It held between **five and twenty** slots, ten distinct values. The question was
  asked loudly enough to hear the answer; the answer was just no.
- **The switch winning on 2008 alone** — **partly.** `GATE20`'s worst calendar year is 2005 at
  −8.1%, so 2008 is not where its drawdown lives, and its advantage over the model is spread across
  the window rather than concentrated in the crash. The crash is in fact the one place the model
  competed: fold 2, the only fold it won, is the 2006-2008 fold.
- **The fall being broader than one crash** — **happened.** Three of five arms breach 20%, and the
  model's own sizing (28.9%) breaches it comfortably despite pulling back through 2008. A forecast
  that helps in the crash is not the same as a forecast that keeps the fall under a fifth.
- **Cutting exposure costs return with idle cash earning nothing** — **happened, and it is the
  main cost.** `FALL20` gave up nothing against `ON20` but 3.3 points a year against `GATE20`, and
  `FALL20-GATE` — the most defensive arm, shallowest fall of all five — earned the least of all
  five. Being out of the market was expensive in a window SPY roughly quadrupled over.
- **Survivorship making the model optimistic** — **unmeasured.** The store is the same
  survivorship-bearing dev store every lab method uses; nothing here isolates it.
- **Overlapping quarter-long labels shrinking the effective sample** — **unmeasured directly**, but
  the DSR ceiling of 0.769 is consistent with it: no arm separates from luck at the lab's N.
- **The regularised arm landing outside the model-to-control range** — **happened, and the
  pre-registration said what to make of it.** `FALL20-REG` beats `FALL20` on return, fall, profit
  factor, MAR *and* DSR, all at once. The frozen text reads: *"if the regularised tree is clearly
  better, that is evidence the base tree was overfitting the label and the right reading is that
  neither setting found anything."* That is the reading taken here.

## One inaccuracy in the frozen pre-registration, recorded not corrected

The hypothesis says "BEFORE THE FIRST MODEL every variant holds SPY ... the pre-model era is
identical everywhere and cancels out". For the three ungated arms that is exactly right. For the
two gated arms it is not: the gate is evaluated **before** the calendar rule, so `GATE20` and
`FALL20-GATE` hold SPY-or-cash through 1996-1999 rather than SPY. The pre-model era therefore does
not cancel perfectly out of the `FALL20` − `GATE20` comparison.

It is recorded rather than fixed, for three reasons. The method file is frozen against its recorded
source hash the moment the run exits 0. The code is what was committed and what ran, so the
pre-registration describes it in every respect that matters except this sentence. And the gap being
explained away is 7.5 points of drawdown and 3.3 points a year, which four pre-model years of a
200-day switch on SPY cannot account for. A follow-up that wanted this clean would make the gated
arms' pre-model era explicit — and that is a new method, not a revision of this one.

## What this does and does not license

It tested **one** way of forecasting a fall: the worst drop over the coming quarter, as a level,
learned from signals the lab already had, on big American companies, long only, monthly decisions,
after the fees the owner really pays, with idle cash earning nothing. It says that this forecast,
used this way, is worse than the brake the lab has.

It does not say forecasting the fall is the wrong idea — the 74% → 29% reduction against no brake
at all is real, and the only fold this method won is the one with the crash in it. It is also no
endorsement of the switch: the switch is still one rule, on one index, and the lab has already
measured that most of its whole-window value is a single year and that it has been a drag since
2009.

The honest next questions, all of them **new methods** rather than revisions of this one: the same
head on realised downside volatility instead of drawdown; a decision cadence faster than monthly,
now that `lab turnover` has priced what that costs (7% a year at its cheapest); and a rule set that
credits idle cash, which would change the sign of the largest cost measured here — though the owner
cannot trade that one today.

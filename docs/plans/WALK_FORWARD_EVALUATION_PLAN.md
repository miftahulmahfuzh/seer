# Plan: walk-forward evaluation — many out-of-sample looks, from the data we already have

**Slug:** walk-forward-evaluation
**Date:** 2026-10-09
**Branch:** not started (base: `main` @ `39d2927` or later)
**Status:** proposed
**Prerequisite:** none. No new data, no store rebuild, no test-window contact.

---

## Why

On 2026-10-09 the lab spent its third and fourth test-window looks. The score is now:

| Candidate | Failed |
|---|---|
| M0021-B70-RAW | beats SPY TR |
| M0029-B70-RAW-FRAC | beats SPY TR; max DD <= 20% |
| M0022-W-TV14 | beats SPY TR; max DD <= 20%; PF >= 1.3 |
| M0002-REL-85 | beats SPY TR; max DD <= 20%; PF >= 1.3 |

Four for four, all on the same condition. Separately, all four strategies on the paper roster lost
to a SPY fed the owner's identical deposits over 2018-2026, every one of them falling 29-34% where
the roster's own rule allows 20%. The owner mirrors that roster with real money.

The deflated Sharpe did not survive the move out of sample either: M0022 went 0.912 on dev to 0.136
on test, M0002 0.854 to 0.204. Whatever the dev luck test was measuring, it was not durable edge.

**The root cause is structural, not a bad method.** Every method is chosen on one twenty-year
window and then gets exactly one out-of-sample observation, spent at the very end, after the
decision to promote has already been made. One observation per method cannot tell luck from skill,
and by the time it arrives the method is on the roster and the owner's money is in it.

Insight 58 records the first diagnosis and the fact that it was wrong. The obvious fix -- split dev
results by market breadth, since the residual-momentum family is a bet against narrow markets --
was built as `lab regime` and **does not discriminate**: on month-by-month breadth labels almost
every recorded method reads "pays in both", M0007-N20-RAW included, at +6.6% in narrow months and
+7.7% in broad. What separates the eras is how long narrowness *lasts*, and the dev window does not
contain a sustained spell at anything like 2023-2026's strength (6 of 202 three-year windows
positive, peak +0.17% a month, against a peak of +0.68% ending December 2025).

So no cleverer dev *statistic* will fix this. The only thing that would have caught it is more
out-of-sample evidence, earlier. This plan manufactures that evidence from data already on disk.

## The idea

Walk-forward evaluation. Instead of one train/test split, roll many:

```
fold 1   train 1996..2005   evaluate 2006..2008
fold 2   train 1996..2008   evaluate 2009..2011
fold 3   train 1996..2011   evaluate 2012..2014
fold 4   train 1996..2014   evaluate 2015
```

In each fold, apply **the lab's own selection rule** to the training slice only -- pick the variant
a researcher would have picked knowing nothing after the train end -- then score that pick on the
evaluation slice it has never seen. The result is a per-method record of how its selection
*process* behaved out of sample, four times over, on the dev window, costing no counted look.

A method that wins its dev average but loses three of four folds is not a method. The lab has had
no way to notice that.

## It re-runs nothing

This is the part that makes it cheap, and it is the same trick `lab regime` uses. Every recorded
trial carries its **monthly** equity curve (`trials.curve_json`, 131 of 131 rows have one). A fold
is a date slice of that curve, so per-fold CAGR, max drawdown and MAR are arithmetic on rows the
database already holds. No backtest, no research store for the metrics themselves, no trial row, no
status move, no look.

**A funded curve must have its deposits taken out first.** This is not optional and it is not a
detail: from M0032 on every trial is funded with the owner's 5,000,000 IDR a month, and a recorded
curve counts each deposit as if the book had earned it. Sliced raw against `REF-SPY-HOLD`, which
received nothing, the batch of 2026-10-09 read as beating the market by seventy to eighty points a
year in the early era -- 148,000 dollars of the owner's own money counted as profit on one side of
a comparison and not the other. Use `regime.bucket` and `lab.runner.recorded_contributions`, which
already do this correctly for `lab regime` and `survivorship_coverage.py`: a recorded curve is
normalised to the opening cash, so one deposit is `amount_idr / INITIAL_IDR` -- 0.5 for the owner's
schedule -- and no exchange rate enters, because the run converted both at one rate. **Every trial
from here on will be funded**, so a walk-forward that skips this is wrong by default rather than in
an edge case.

Two further honest limits of the curve shortcut, which the implementation must state in its output
rather than paper over:

- **Profit factor and trade count cannot be sliced** from a monthly curve; they need fills. So the
  per-fold selection rule ranks on MAR among candidates whose *whole-window* record cleared the
  non-sliceable conditions. That is a proxy for the real rule, not the real rule.
- **Folds share training data**, so they are not independent observations. Four overlapping folds
  are a sanity check, not a significance test, and nothing here should be fed into a DSR.

## Design

**Where it lives.** `engine/src/seer_engine/backtest/walkforward.py`, with `lab walkforward` in
`commands/lab.py` beside `regime` and `costs`. Report only, in the sense those are: it writes
nothing to the database.

**Fold geometry.** Expanding train window, fixed 3-year evaluation slices, minimum 10 years of
training before the first fold. On `DEV_WINDOW` (1996-01-03..2015-10-16) that is the four folds
above. Parameters `--min-train-years` and `--eval-years` so the geometry can be argued with.

**Selection rule per fold.** Among a method's candidates, rank by MAR computed on the training
slice alone; the winner is the fold's pick. Record its evaluation-slice MAR, CAGR, max drawdown,
and whether it beat `REF-SPY-HOLD` on the same slice.

**What it reports.** Per method, one row:

```
method   folds   picked          won   eval MAR   vs SPY   verdict
M0007        4   N20-RAW x3        1/4      0.31    -4.2%   loses out of sample
```

plus a lab-wide summary: how many methods win a majority of their folds. If that number is near
zero the finding is about the lab, not about any method, and belongs in a synthesis insight.

**Does the pick stay stable?** Worth reporting: a method whose fold winner changes every fold is
telling you the choice between its variants is noise.

## The buy signal: the one moment data is worth paying for

The owner asked to be told, automatically, when buying survivorship-free price history stops being
premature and starts being worth it. This is that rule, and `lab walkforward` is where it gets
computed, because condition (b) is the piece only this plan can supply.

**A method fires the buy signal when all three hold at once:**

| | Condition | Where it comes from |
|---|---|---|
| **(a)** | dev-eligible at the bars in force | `lab show` / the lab's five conditions + DSR |
| **(b)** | beats SPY in a **majority of walk-forward folds** | `lab walkforward`, phase 2 of this plan |
| **(c)** | a **positive edge in the highest-coverage era** (2009-2015) | `engine/scripts/survivorship_coverage.py` |

**Why that conjunction and not something simpler.** Condition (c) is the one that makes the
purchase *about data*. The dev store prices 48% of index members in 1996 and 74% in 2014, and the
522 it cannot price are disproportionately the companies that died -- AABA (ex-Yahoo!), AAMRQ (AMR
in bankruptcy), and 520 more. A method whose edge lives in the thin early years and dies by
2009-2015 is probably reading that hole, and no purchase is needed to reject it: it already failed
for free. Three of the four roster strategies were negative in 2009-2015 on the dev window, years
before the test window said the same thing out loud, and nobody looked.

But a method that passes (a), (b) **and** (c) has used up the free evidence. The missing half is
then the live question, and the next two things that happen are a counted test look -- which is
spent once and never returned -- and the owner's real money. Roughly $30-150 for a one-month bulk
download (Norgate, Sharadar via Nasdaq Data Link, or EOD Historical Data; all subscription, so
pull the history and cancel, and read the licence before relying on continued use) is cheap against
either.

**Until the signal fires, do not buy.** That is the point of the rule: it stops the purchase being
made out of enthusiasm, and it stops it being deferred out of thrift when it finally matters.

**Where it is enforced.** `lab walkforward` prints the verdict per method and a one-line summary.
The explore skill's Promotion **step 0b** requires all three before a look is spent, and Sera's
synthesis must state the answer every batch, even when it is "no buy signal this batch" -- both
already updated. Sera reports it and never blocks on it: the iron rule is still that she asks
nobody anything.

## Phases

1. **`walkforward.py`** — folds, per-fold metrics from a monthly curve, the selection rule, and the
   per-method record. Pure: takes curves and dates, no I/O. It must accept a deposits series per
   the warning above and subtract it before measuring any fold. Unit tests with synthetic curves,
   including a method built to win on average and lose every fold, and one funded book that earned
   nothing and must read as nothing (`test_backtest_regime.py` has that test to copy).
2. **`lab walkforward`** — reads `trials.curve_json` and `REF-SPY-HOLD`, prints the table. Needs no
   research store. Follow `_regime` for the shape; it is deliberately the same kind of command.
   **It must also print the buy signal**: conditions (a) and (b) it can decide itself; (c) it can
   decide too, since the era split is the same curve-slicing arithmetic `survivorship_coverage.py`
   already does. Emit one obvious line per method -- `BUY SIGNAL: MNNNN cleared (a)(b)(c)` or
   `no buy signal (fails b: 1 of 4 folds)` -- so neither a human nor Sera has to assemble the
   judgement by hand.
3. **Run it on all 29 methods and write the synthesis** as a `lab insight --kind synthesis`. Expect
   the headline to be uncomfortable.
4. **Only if phase 3 justifies it:** make a walk-forward majority a *reported* condition on
   `lab status` and in the pre-registration gate line. Not a hard gate without the owner's say-so
   -- that is a policy change about what the lab is allowed to promote, and it belongs to him.

Phases 1-3 are a weekend. Phase 4 is a conversation first.

## Picking this up on the GPD laptop

- `git pull` gets everything. The code and the lab database are in the repo.
- **Phases 1-3 need no research store at all** — the curves are in `lab/lab.sqlite`. This is the
  main reason to do walk-forward before anything on the blocked-data list.
- If a later phase does need a store: `engine/.research/` syncs with
  `.claude/skills/sync-research-store/sync_store.py pull`. **The test store does not.**
  `engine/.research-test/` (built 2026-10-09, 390MB, fingerprint `bbe7abfb4a12`, window
  2015-10-19..2026-10-08) is not covered by that script, so on a second machine it is either a
  35-minute rebuild with `python -m seer_engine research_store --test-window --with-fundamentals`
  (which needs `SEER_ENV_FILE` pointing at an **absolute** path to `.env.local-train`), or extend
  `sync_store.py` to carry both stores. Extending the script is the better weekend job of the two.
- Lab tests: `cd engine && PYTHONPATH=$PWD/src .venv/bin/python -m pytest -q tests/test_lab_*.py`.
  `test_lab_snapshot.py` fails whenever `lab/lab.sqlite` moved without `lab stage`; that is a
  staging reminder, not a bug.
- Do not run this while a Sera batch is live. She owns `lab/lab.sqlite` commits and pushes to main
  after every child.

## What this does not fix

Walk-forward tests the *selection process* against history. It cannot tell you about a regime
history does not contain -- and 2023-2026's sustained mega-cap concentration is exactly that, which
is the whole lesson of insight 58. It will catch a method that is fragile across time. It will not
catch a method that is a bet against a market that has not happened yet.

For that there is no statistic, only humility about position size and the test window used early.

## Related

- Insight 58 (risk): four of four test looks failed, and the dev window cannot see why.
- Insight 59 (data-wish): four free datasets, one purchase worth making.
- `lab regime` — the breadth panel, and the documented negative result that it does not discriminate.
- `.claude/skills/calculate-assets/` — what a method would have done to the owner's actual money.
- `docs/plans/CALCULATE_ASSETS_SKILL_PLAN.md` — the design that started this thread.

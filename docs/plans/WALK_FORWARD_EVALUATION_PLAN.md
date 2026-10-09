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

Two honest limits of that shortcut, which the implementation must state in its output rather than
paper over:

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

## Phases

1. **`walkforward.py`** — folds, per-fold metrics from a monthly curve, the selection rule, and the
   per-method record. Pure: takes curves and dates, no I/O. Unit tests with synthetic curves,
   including a method built to win on average and lose every fold.
2. **`lab walkforward`** — reads `trials.curve_json` and `REF-SPY-HOLD`, prints the table. Needs no
   research store. Follow `_regime` for the shape; it is deliberately the same kind of command.
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

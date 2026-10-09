# Plan: walk-forward evaluation — many out-of-sample looks, from the data we already have

**Slug:** walk-forward-evaluation
**Date:** 2026-10-09
**Branch:** not started (base: `main` @ `39d2927` or later)
**Status:** phases 1-3 done 2026-10-09; phase 4 open
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

**Where it lives.** `engine/src/seer_engine/lab/walkforward.py`, with `lab walkforward` in
`commands/lab.py` beside `regime` and `costs`. Report only, in the sense those are: it writes
nothing to the database.

**Not `backtest/walkforward.py` — that name is taken, and by something real.** The repo already
has an anchored yearly walk-forward: P3b's, for Strategy A2 on the bracket engine, which re-runs
`run_backtest` over a 324-combination tuning grid and selects parameters per fold. That is a
different engine answering a different question, and it is worth reading before building this one
(`folds`, `select_fold`, `walk_forward`, `gate_p3b` are all there). This module never runs a
backtest and tunes nothing: it slices curves the lab already recorded, and the only thing it
selects is which variant the lab's own rule would have named at each point in time.

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
| **(a2)** | **no method in the same family has test-failed** | `methods.family` + `status` |
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

**Condition (a2) was added after running it, and it is the most important thing phase 3 found.**
Without it the signal fired on M0007, M0019 and M0020, and every one of the three belongs to a
family that had *already* failed out of sample. M0007 reads `dev-eligible` only because no formal
look was ever spent on it, while its own realistic twin M0032 lost 415 million rupiah to a
deposit-matched SPY over 2018-2026. A status column is not the evidence. With (a2) the answer
across the whole lab today is **no buy signal**, which is what the evidence says.

**Until the signal fires, do not buy.** That is the point of the rule: it stops the purchase being
made out of enthusiasm, and it stops it being deferred out of thrift when it finally matters.

**Where it is enforced.** `lab walkforward` prints the verdict per method and a one-line summary.
The explore skill's Promotion **step 0b** requires all three before a look is spent, and Sera's
synthesis must state the answer every batch, even when it is "no buy signal this batch" -- both
already updated. Sera reports it and never blocks on it: the iron rule is still that she asks
nobody anything.

## Phases

1. **`lab/walkforward.py`** — folds, per-fold metrics from a monthly curve, the selection rule, and
   the per-method record. **Done 2026-10-09**, 23 tests. Pure: takes curves and dates, no I/O. It must accept a deposits series per
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
3. **Run it on all methods and write the synthesis.** **Done 2026-10-09**, insight 76. Measured:
   of the four methods already known to have failed the test window it flags three (M0021, M0022
   and M0002 each won 2 of 4 folds); M0029 won 3 of 4 and slips through. Twelve of thirty-three
   methods win a majority, so it is not a filter that rejects everything. The buy signal gained a
   fourth condition because running it fired on three methods whose families had already failed --
   see below.
4. **The hard gate.** Specified in full below. **The owner decided it on 2026-10-09**: a
   majority of folds AND a clean family, enforced as a refusal, not a report.

Phases 1-3 took an afternoon. Phase 4 is the next session's work.

---

# Phase 4 — the hard gate

**Decided 2026-10-09 by the owner**, after seeing what it costs. This section is the brief; it is
written to be picked up cold.

## The rule

`lab promote` refuses a method unless **both** hold:

- **(F) folds** — the method beat the recorded SPY benchmark in a **majority** of its scoreable
  walk-forward folds (`lab/walkforward.py`, `Record.majority`);
- **(K) kin** — **no other method in the same `family` reads `test-failed`**.

Both are already computed and tested. Phase 4 is about where the refusal lives, what gets recorded
when it passes, and what happens to everything that now cannot move.

## What it costs, stated before anyone is surprised

**It blocks every promotion in the lab as of today.** Every dev-eligible method -- M0007, M0019,
M0020, M0033 -- is in a family that has already failed the test window, so every one fails (K).
The lab will promote nothing until a genuinely new family appears.

That is the intended effect, not a side effect. Five out-of-sample results, five failures; and the
surviving ideas are all cousins of the methods that produced them. A lab that keeps promoting
cousins of disproven families is not learning. If this proves too strict in practice the answer is
a recorded, argued change to the rule -- not an override path, which is precisely the mechanism
that produced the 0-for-5 roster in the first place.

## Why at promote and not at test

`lab promote` is where the lab commits: it writes the pre-registration, moves the method to
`promoted`, and `promoted` has only two exits, both final. Refusing at `lab test` would leave a
method stranded in a state it can never leave. Refuse before the commitment, not after it.

The check is cheap and adds no dependency: it reads recorded curves and the methods table, needs
no research store, and runs in under a second.

## What the pre-registration must record

The lab's idiom is to pin the rule in git *before* any test number exists -- `docs/lab/prereg/
MNNNN.md` already records the five conditions, the DSR bar and the N in force. The fold record
belongs there for the same reason: so a reader a year from now can see the bar this method actually
cleared, not today's bar. Add the folds won and scored, whether the pick was stable across folds,
and the family's state at promotion.

## Open questions the implementer must answer, not assume

1. **Fail closed on thin evidence.** A method with no scoreable folds, or fewer than some minimum,
   must be **refused**, never waved through. Decide the minimum and say why in the code.
2. **Is (K) evaluated at promote time only?** A family can fail *after* a method is promoted but
   before its look is spent. Decide whether `lab test` re-checks (K) or honours the pre-registration
   as written. The design's instinct is that a pre-registration is a promise and is not re-opened,
   but say which you chose.
3. **Does (K) look at ancestry as well as `family`?** M0032 is M0007's realistic twin by
   `parent_id`, not by family string. A method whose *parent* failed is as disproven as one whose
   sibling did. Decide whether to walk `parent_id` too.
4. **Is there any path back?** `reevaluate` exists for `rejected -> dev-eligible` when the bars
   move. Nothing equivalent exists for a family unblocked by later evidence. Do not invent one in
   this phase; note whether it will be needed.

## Also update, or the gate is invisible until it bites

- `explore-and-experiment-new-method` **Promotion step 0b** currently *advises* a fold majority.
  It must say the gate will refuse, so a child does not waste a cycle discovering it.
- `sera-the-explorer` promotion path and the Never table, for the same reason.
- `lab status` should show the fold record beside the dev-eligible list, so "why can nothing be
  promoted" is answerable without running a second command.

## Tests this phase is not done without

- a method winning a majority with a clean family **promotes** (the existing promote tests must
  still pass unchanged);
- one losing the folds **refuses**, naming the record;
- one in a family with a `test-failed` member **refuses**, naming the member;
- one with too few scoreable folds **refuses**;
- the refusal happens **before** the pre-registration file is written and before any status moves
  -- a refused promote must leave the repository and database byte-identical.

## Context the implementer needs and will not guess

- Five out-of-sample results, five failures: M0021, M0029, M0022, M0002 on `beats SPY TR`, and
  M0032 losing 415 million rupiah to a deposit-matched SPY over 2018-2026 (insight 58, 76).
- The fold detector flags three of those four recorded failures and misses M0029. It is not
  infallible; it is better than what preceded it, which was nothing.
- **A funded curve must be de-funded before it is measured** (`regime.defunded`). Every trial from
  M0032 on is funded. Getting this wrong reads the owner's deposits as edge -- it did, by seventy
  to eighty points a year, until it was fixed (insight 72, 75).
- `backtest/walkforward.py` is a **different module** -- P3b's anchored walk-forward for Strategy
  A2 on the bracket engine. The lab one is `lab/walkforward.py`. Do not edit the wrong file.

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

# The SPY-200 gate's reading cadence — the prior, and the anchor proved

**Produced:** 2026-10-19 · **Script:** `docs/backtests/2026-10-19-gate-reading-cadence.py`
**Store:** `/home/miftah/seer/engine/.research` (the dev store, 1993-01-29 .. 2015-10-16)
**Records nothing in the lab.** No method, no trial, no N, no test-window look.

    PYTHONPATH=/home/miftah/.worktrees/seer/gate-reading-cadence/engine/src \
      /home/miftah/seer/engine/.venv/bin/python \
      docs/backtests/2026-10-19-gate-reading-cadence.py \
      --store /home/miftah/seer/engine/.research

**Every return below is UNFUNDED.** This is a weight path on SPY's own closes — no monthly top-up,
no Gotrade fee, no fills. The lab's money number is `trial_funding.mwr`, what `lab show` prints as
"your money earned", and nothing on this page is that. The figures here are a prior for M0260's
hypothesis and a feasibility table for its anchor, in the same genre as M0245's episode ledger and
M0241's split-count table.

Unlike `docs/backtests/2026-10-19-gate-band-cadence.py`, which reads a relative store path and so
has to be run from the main checkout, this script takes an **absolute `--store`** and was run from
the worktree. That is a deliberate correction of the precedent, not a divergence from it; the older
file is a committed record of a finished study and is not edited to match.

## Output

```text
SPY from /home/miftah/seer/engine/.research/bars.csv: 5722 bars, 1993-01-29 .. 2015-10-16

Table 1 -- the prior grid: SPY alone, bare 200-day gate, read at a month-end anchor
ALL FIGURES UNFUNDED: a weight path on SPY's own closes. No deposits, no fees, no fills.

gate read                  book acts    CAGR*    worst   09-15*     inv  flips
------------------------------------------------------------------------------
native (at data_date)        monthly    9.08%   -19.0%   10.07%   71.9%     22
k=1  every month end         monthly    9.08%   -19.0%   10.07%   71.9%     22
k=2  Feb/Apr/.../Dec         monthly    8.56%   -19.7%    7.86%   72.7%     20
k=3  calendar quarters       monthly    6.71%   -24.5%    6.31%   70.0%     20
k=6  Jun/Dec                 monthly    8.39%   -25.9%    7.88%   72.5%     11
k=12 December only           monthly    7.06%   -19.4%    7.25%   67.9%      9
native (at data_date)         weekly    5.51%   -34.6%    5.82%   70.8%     80
k=1  every month end          weekly    8.49%   -19.0%    8.98%   71.9%     22

* unfunded price-return CAGR. The lab's money number is trial_funding.mwr; this is not it.

Table 2 -- each anchored rung minus the native monthly reading (UNFUNDED)
A positive drawdown difference means the anchored rung fell LESS.

rung                          CAGR diff    worst-fall diff    flips
--------------------------------------------------------------------
k=1  every month end             +0.00              +0.0       +0
k=2  Feb/Apr/.../Dec             -0.52              -0.7       -2
k=3  calendar quarters           -2.37              -5.5       -2
k=6  Jun/Dec                     -0.69              -6.9      -11
k=12 December only               -2.02              -0.4      -13

Table 3 -- Appendix B's decomposition, in its SPY-alone shadow (UNFUNDED)
A = monthly book, native reading.  B = weekly book, native reading.
C = weekly book, monthly-anchored reading (k=1): the decomposition arm.
(A - C) is re-pick frequency with the gate held; (C - B) is gate cadence with the
re-pick held; they sum to (A - B) by construction, not by luck.

term                                  CAGR diff    worst-fall diff
------------------------------------------------------------------
A - B   total (M0258's number)           +3.58             +15.5
A - C   re-pick frequency                +0.59              +0.0
C - B   gate reading cadence             +2.99             +15.5

Table 3b -- reproduction of the lab's own recorded SPY-only trials (worst fall, %)

recorded trial                            recorded  this grid
--------------------------------------------------------------
M0084-MONTHLY  bare gate, read monthly      18.89%      19.0%
M0084-WEEKLY   bare gate, read weekly       33.13%      34.6%

Table 4 -- the anchor probe on the real dev store, every decision session 1996-01-03..2015-10-16

rule set  rung                        sessions  reads  fallbacks  late  min bars  max stale
--------------------------------------------------------------------------------------------
monthly   k=1  every month end             237    237          0     0       760         0d
monthly   k=2  Feb/Apr/.../Dec             237    119          0     0       738        33d
monthly   k=3  calendar quarters           237     80          0     0       738        64d
monthly   k=6  Jun/Dec                     237     40          0     0       738       154d
monthly   k=12 December only               237     20          0     0       738       336d
weekly    k=1  every month end            1032    238          0     0       738        29d
weekly    k=2  Feb/Apr/.../Dec            1032    119          0     0       738        59d
weekly    k=3  calendar quarters          1032     80          0     0       738        91d
weekly    k=6  Jun/Dec                    1032     40          0     0       738       182d
weekly    k=12 December only              1032     20          0     0       738       364d

reads      = distinct anchor dates used, i.e. how often the gate was actually re-read
fallbacks  = sessions where no qualifying month end was on hand (MUST be 0)
late       = sessions where the anchor was later than data_date (MUST be 0: invariant 9)
min bars   = fewest SPY bars behind any resolved anchor (MUST be >= 200, or trend_on
             returns False and the arm is all-cash for a reason the market never gave)

Table 5 -- the identity the arm table rests on: on a MONTHLY book, anchor(k=1) == data_date

  decision sessions checked : 237
  disagreements             : 0

  Every monthly decision session reads the gate at its own data_date at k=1, so the
  anchored k=1 monthly arm would collide with M0260-M-NATIVE. Appendix A is right to
  drop it and assert it in the test module instead of spending a trial on it.

Table 6 -- the decomposition: a WEEKLY book's k=1 anchor vs the MONTHLY book's reading

  decision sessions checked : 1032
  agreements                : 1032
  disagreements             : 0

  Arm C literally reuses arm A's gate reading at every weekly decision session, so
  (A - C) moves re-pick frequency and nothing else, and (A - C) + (C - B) = (A - B).

Table 7 -- the two month-end tests agree (the cheap interior test is safe on this symbol)

  bars compared                     : 5721
  bars-vs-calendar disagreements    : 0

CHECKS
--------------------------------------------------------
  PASS  anchor always resolves (no fall-back)
  PASS  anchor never later than data_date
  PASS  every anchor has >= 200 SPY bars behind it
  PASS  monthly k=1 anchor == data_date
  PASS  weekly k=1 anchor == the monthly arm's reading
  PASS  bars and calendar month-end tests agree

6 of 6 structural checks passed.
```

## What the grid predicts for M0260's six arms

**1. The shape of the ladder: it falls, and it does not hump.** On SPY alone the gate read at its
own decision date earns an unfunded 9.08%/yr with a 19.0% worst fall, and every slower rung is
worse on return: 8.56% unfunded at two months, 6.71% unfunded at a quarter, 8.39% unfunded at half
a year, 7.06% unfunded at a year. The fall deepens too, to 25.9% unfunded at the half-yearly rung,
before recovering at the yearly one. **Nothing above monthly beats monthly here.** So M0260's
hypothesis is framed as *find where the axis turns*, and the honest prior says the turn is at or
near the fastest rung — not "slower is better". This is a prediction for the stock book, not a
result about it: SPY alone has no stock picking in it at all, and the 3.6 points a year the safety
gate is worth after 2009 was measured on books that hold stocks. The stock book may well put its
turn somewhere else. What this grid forbids is pre-registering a slow-gate win, because that would
be predicting against the only evidence that exists.

**1b. The two-month rung is measured here as a prior only, and is not one of M0260's arms.** This
grid runs five monthly rungs — one, two, three, six and twelve months — because a prior may be
wider than the ladder it informs, and because the two-month row is the only thing that tells a
reader whether the drop from one month to a quarter is a cliff or a slope (it is a slope: −0.52
then −2.37 unfunded points). But `lab.method.MAX_VARIANTS = 6` caps a `Method` at six candidates
(`engine/src/seer_engine/lab/method.py:40`, enforced in `Method.__post_init__`, which raises at
import rather than at review), and M0260 spends its six on `M-NATIVE`, `M-G3`, `M-G6`, `M-G12`,
`W-NATIVE` and `W-G1`. **So the two-month rung measured on this page is deferred to an `Amendment`
under the same method id** — an amendment costs no method id, and it is the right home for it if
the funded ladder comes back humped between the native monthly arm and the quarterly one. No
two-month trial is coming. **M0260 is six arms, not seven.**

**2. The yearly rung: "barely a gate at all" is now a number.** A book reading the gate every
December re-reads it **20 times** across the twenty-year dev window, and at the moment it acts, its
reading is **up to 336 days old** on a monthly book and **up to 364 days old** on a weekly one. The
half-yearly rung re-reads 40 times with a reading up to 154 days old; the quarterly rung 80 times
at up to 64 days; the native monthly rung 237 times at zero days old, because at one month the
anchor *is* the decision date. That is the dose, measured, and it is what makes this a
dose-response ladder in a real quantity rather than a label.

**3. The decomposition, and what phase 3 will measure it against.** On SPY alone the whole
+3.58 unfunded points a year between a monthly reading and a weekly one splits **+2.99 unfunded
points to the gate's reading cadence and +0.59 unfunded points to the re-pick frequency**, and
**every one of the 15.5 points of worst fall is the gate cadence** — the re-pick frequency
contributes exactly zero to the fall. The real split will be measured on the funded, fee-paying,
deposit-matched stock book in phase 3, as `trial_funding.mwr` and worst fall, and it may differ in
size. It **cannot** differ in structure: Table 6 proved that at every one of the 1032 weekly
decision sessions, the weekly book's monthly-anchored arm reads exactly the bar the monthly book is
reading, so the re-pick term moves re-pick frequency and nothing else, and the two terms sum to the
total by construction rather than by luck.

**4. What the anchor probe settles.** Across all ten rows — two rule sets by five rungs, every
decision session from 1996-01-03 to 2015-10-16 — the anchor fell back to the decision date **zero
times**, landed later than the decision date **zero times**, and never had fewer than **738 SPY
bars** behind it against the gate's requirement of 200 (760 on the monthly one-month rung). So no
anchored arm is ever all-cash for a reason the market never gave, and plan invariant 9 holds by
measurement rather than by argument. The monthly one-month identity is exact across all 237 monthly
decision sessions, which is why the arm table is right to drop that arm rather than spend a trial
on it — it would be the native arm under a different digest. And the two month-end tests agree on
all 5721 comparable bars, so the cheap interior comparison is safe on this symbol and the allocator
needs the calendar form only for the newest bar it holds.

**That 738-bar minimum is also what makes phase 2's widened lookback safe.** Reading a 200-bar
average at an anchor up to 253 sessions old needs 453 bars on hand, so M0260 runs at a lookback of
454 rather than M0072's 253. The binding rule is **`lookback <= 739`**, never "do not widen":
`dev.candidate_window` floors index members at `MEMBERSHIP_START` and raises `ready` only for a
candidate's *fixed* symbols, and this book's fixed symbol list is SPY alone, whose 739th dev-store
bar is 1996-01-02 and whose 740th is 1996-01-03. So any lookback up to 739 leaves the first scored
session at 1996-01-03 and the paired comparison with M0258's recorded rows intact. The operative
ceiling from the other side is the 473-session smoke fixture, which 454 clears with 19 sessions to
spare.

**5. What this page is not.** It is not a lab result and must not be cited as one. Every return on
it is **unfunded** — a weight path on SPY's own closes, with no deposits, no fees and no fills —
and the lab's own money number, `trial_funding.mwr`, appears nowhere on it. It is SPY alone, so it
contains no stock picking. And it was produced **before** any M0260 trial was recorded, which is
the entire point: a pre-registration is frozen by its own commit and may not quote a number that
was guessed.

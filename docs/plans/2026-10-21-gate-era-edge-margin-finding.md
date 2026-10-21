# Does the promotion gate's 2009-2015 condition need a margin?

**Verdict: No. Do not add a threshold T. The premise behind the question does not survive
measurement, and the condition cannot be calibrated at all with the evidence the lab owns.**

Read-only, on a copy of `lab/lab.sqlite`. No research store opened, no look spent, no `lab
survivorship` run. 86 methods scored, 28 positive -- both reproduce insight 508 exactly, which is
how I know the replication is faithful.

---

## 1. The ground-truth table in insight 508 is the hindsight column, not the gate's

This is the finding that reframes everything else. Insight 508 records the four edges as
-1.4, -2.2, -3.0, +0.2. Those are `best_era_arm` numbers -- the arm with the highest MAR over
2009-2015 *itself*, chosen after seeing that era. That is the column the gate read **until
2026-10-20**, when D18 moved it to the promoted arm.

On the arm the gate reads **today** (`best_dev_eligible`, the arm the money goes into):

| method | fold record | edge, HINDSIGHT arm | edge, PROMOTED arm (today's gate) |
|--------|-------------|---------------------|-----------------------------------|
| M0002  | 2 of 4      | -1.40               | **no promotable arm at all** |
| M0021  | 2 of 4      | -2.24               | **-0.17** |
| M0022  | 2 of 4      | -2.99               | **-2.02** |
| M0029  | 3 of 4      | +0.22               | +0.22 (one arm only) |

The hypothesis under test was: *"the three caught were each more than a point on the wrong side;
the one missed scraped through on two tenths."* On the gate's own arm that is **false**. M0021 is
0.17 pts on the wrong side -- the mirror image of M0029's 0.22 on the right side.

## 2. The era-edge condition caught none of the four

`buy_signal` returns on the first failing condition, and `majority` is checked **before** the
edge. So for each of the four, the counterfactual catch is:

- M0002 -- 2 of 4 folds -> refused on **folds**. (Edge never reached; also unmeasurable.)
- M0021 -- 2 of 4 folds -> refused on **folds**. (Edge -0.17 never reached.)
- M0022 -- 2 of 4 folds -> refused on **folds**. (Edge -2.02 never reached.)
- M0029 -- 3 of 4 folds -> passes majority -> edge +0.22 passes -> **MISSED**.

**All three catches belong to the fold-majority condition. The era edge has never been the
binding constraint on any outcome the lab owns.** It is 0 for 4, not 3 for 4.

A margin T would therefore be fitted to **n = 1**, not n = 4 -- and that one point is the single
method the condition was already going to be asked about.

## 3. The distribution: a continuum, and +0.22 sits in its densest part

86 scoreable methods, era edge on the promoted arm:

    min -10.21   25th -3.24   median -2.12   75th -0.26   max +4.54
    mean -1.83   sd 2.88

Deciles: -5.37 -4.55 -3.24 -2.59 -2.12 -1.06 +0.26 +1.10 +1.90

**No natural gap.** The largest gap anywhere in [-1, +3] is 0.52 pts (M0135 +1.74 -> M0072
+2.26). Around zero the spacing is tighter still: M0056 -0.25, M0021 -0.17, M0152 +0.21,
**M0029 +0.22**, M0204 +0.26, M0223 +0.31, M0077 +0.36. Seven methods inside 0.6 of a point.
There is no seam to cut on.

## 4. Cost table

Only methods clearing **every other** condition (dev-eligible, kin-clean, fold-majority,
measurable edge) can be affected by T. There are five, and two already have negative edges:

    M0072  +2.26   3/4   M0072-Z2-RAWRANK
    M0258  +2.26   3/4   M0258-M-B0
    M0092  +1.73   3/4   M0092-SQRT-CAP10
    M0197  -3.34   3/4   (already refused)
    M0243  -3.92   3/4   (already refused)

| T (pts/yr) | still fires | newly refused | names | catches M0029? |
|------------|-------------|---------------|-------|----------------|
| 0.0 (today)| 3           | 0             | --    | no (MISSED) |
| +0.5       | 3           | 0             | --    | yes |
| +1.0       | 3           | 0             | --    | yes |
| +1.5       | 3           | 0             | --    | yes |
| +2.0       | 2           | 1             | M0092 | yes |

Note: **M0072 and M0258 have byte-identical yearly edges** -- same book. The "three methods
firing" are two distinct books.

So any T in (0.22, 1.5] catches M0029 and costs nothing today. That is exactly what makes it
tempting, and it is not a reason.

## 5. The era edge is not stable enough to carry any of these thresholds

Year-by-year decomposition of the era edge, promoted arm, annualised lead over SPY per calendar
year:

    M0029  (+0.22)  2009:-16.6  2010:-4.0  2011:+3.8  2012:+17.6  2013:+8.9  2014:+1.6  2015:-7.6
    M0021  (-0.17)  2009:-18.0  2010:-4.2  2011:+4.6  2012:+15.9  2013:+7.1  2014:+1.9  2015:-7.4
    M0072  (+2.26)  2009:+20.3  2010:+4.0  2011:+0.6  2012: -1.3  2013:+3.6  2014:-3.7  2015:-0.4
    M0092  (+1.73)  2009:+13.5  2010:+1.5  2011:-1.6  2012: -2.0  2013:+7.1  2014:-9.1  2015:+10.6

Standard error of the mean annual edge: **3.0 to 4.2 pts/yr** for these; lab-wide median
**3.1 pts/yr** across all 168 methods (IQR 2.4 to 4.2).

Every one of these era edges has a 95% interval straddling zero by many points. M0029's is
`[-8.1, +8.5]`. M0072's is `[-3.7, +8.2]`.

**Paired year-by-year test** (differencing out the shared market -- the strongest test available):

| comparison | mean diff | SE | t (6 df) | result |
|------------|-----------|----|----------|--------|
| M0072 (+2.26) - M0029 (+0.22) | +2.8 | 6.6 | +0.42 | not distinguishable |
| M0258 (+2.26) - M0029 (+0.22) | +2.8 | 6.6 | +0.42 | not distinguishable |
| M0092 (+1.73) - M0029 (+0.22) | +2.3 | 6.5 | +0.36 | not distinguishable |

**+0.2% and +1.7% are not distinguishable. Neither is distinguishable from zero.** That is the
answer to the question the task said matters more than any T, and it is unambiguous: t = 0.36 to
0.42, against a 2.45 bar.

In noise units, every candidate threshold is a rounding error on the current bar:

    T=+0.5 -> 0.16 SE    T=+1.0 -> 0.32 SE    T=+1.5 -> 0.48 SE    T=+2.0 -> 0.65 SE

**What a defensible margin would actually cost.** A one-sided 95% claim that an edge is truly
positive needs `edge > 1.645 x SE` ~ **+5.1 pts/yr**. Methods in the lab clearing that: **0 of
86.** At one SE (+3.1): 1 of 86, and it clears no other condition. The lab's single best era edge
is +4.54 (M0133). A statistically honest margin refuses the entire lab including its best method
-- which is the clearest possible statement that this quantity cannot support a bar.

## 6. MIN_FOLDS, by contrast, has a stated null -- the asymmetry is real but not the expected one

`MIN_FOLDS = 4` is justified in `hardgate.py` (D2) by an explicit null model, with the table
written into the code as `COIN_FLIP_NULL` and a test pinning it against the binomial:

    folds:  1      2      3      4      5      6
    P(strict majority | coin flip):  0.5000 0.2500 **0.5000** **0.3125** 0.5000 0.3438

The argument is sharp -- "a minimum of 3 would admit evidence strictly weaker than 4" -- and it is
careful about its own limits: explicitly a **bound, not a p-value**, because folds share training
data, and barred from entering a DSR.

So the asymmetry is *not* "folds measured, edge guessed". Both are arguments rather than
measurements against outcomes. The asymmetry is narrower and sharper:

**The folds condition has a stated null and a stated reason its threshold sits where it does. The
era-edge condition has neither a null nor any stated noise scale -- which is precisely why a
0.22-pt margin could be printed as "cleared all 4" without anything in the system objecting.**

The gate states `MIN_FOLDS`'s uncertainty and hides the era edge's.

---

## Recommendation: a reporting change, not a threshold

**Do not add T.** Three independent reasons, any one sufficient:

1. It would be fitted to n = 1 (M0029 is the only outcome the condition ever bound on), not n = 4.
2. Every candidate T is inside a quarter to two-thirds of one standard error. It is not a bar; it
   is noise with a number written on it.
3. The honest T (+5.1) refuses the whole lab. A threshold that is either cosmetic or total is not
   a threshold.

**What the evidence does support** -- and this is the owner's pre-registered narrower finding,
which measurement confirms and strengthens:

> A sub-noise era edge must not be reported as "cleared".

Concretely, if a change is wanted later (NOT implemented here, and it is the owner's call):

- `buy_signal`'s success string reads `2009-2015 edge on the promoted variant +0.2 pts`. It
  should carry the scale that makes that number readable -- the arm's own year-to-year SE -- so
  `+0.2 pts (SE 4.2, indistinguishable from zero)` rather than a bare figure inside "cleared all 4".
- Cost: zero methods change status. No method id. No look. It is a string and a number already
  computable from `curve_json`, the same arithmetic in this analysis.
- It would **not** have caught M0029. Nothing available would have, honestly. It would have
  stopped M0029 being *described* as having passed something.

**A fourth option worth naming, which the measurement actually argues for more strongly than any
margin:** the era-edge condition is 0 for 4 as a catcher while the folds condition is 3 for 4.
If the gate is to be strengthened against the evidence the lab owns, the measurement points at
the folds clause, not this one. That is a separate question and I have not measured it.

---

## Pre-registered predictions: scorecard

**Owner's** (sealed in the task):
- "+1% catches M0029 and costs nothing currently valuable, because the three firing methods sit at
  +1.7, +2.3, +2.3" -- **HELD, exactly.** Confirmed at +2.26, +2.26, +1.73; T=+1.0 costs nothing.
- "n=4 cannot justify a specific T; the defensible finding is that a sub-noise margin should not
  be reported as cleared" -- **HELD, and stronger than predicted.** It is n=1, not n=4.

**Mine** (sealed before measuring the shape):
- (1) Continuum, no gap -- **held**. Mass centred below zero -- **held in sign, wrong in
  magnitude**: I said -3 to -4, it is -2.12 median. My specific claim "no gap wider than ~0.5 in
  [-1,+3]" is **marginally wrong** -- there is one of 0.52.
- (2) T=+1.0 free, T=+2.0 kills the +1.7 method, single-digit affected set -- **held** (5 methods,
  M0092 lost at +2.0).
- (3) SE of several points, 3-8, making +0.2 and +1.7 indistinguishable -- **held**, at the bottom
  of my range (3.1 median).
- (4) MIN_FOLDS justified analytically by a binomial null rather than empirically -- **held,
  precisely** (`COIN_FLIP_NULL`).

**What neither of us predicted, and it is the main result:** the ground-truth table is the
hindsight column; on the gate's own arm the era edge caught **none** of the four, and M0021 sits
at -0.17 -- a known-bad book that the condition "caught" by two tenths of a point in the same way
it "missed" M0029 by two tenths. Two known-bad books straddling zero at +/-0.2, one refused and
one passed, both of which failed the test window, is the cleanest demonstration available that
this condition's sign near zero carries no information at all.

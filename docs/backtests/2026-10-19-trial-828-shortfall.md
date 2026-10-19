# Trial 828's eight points, named

**Measured:** 2026-10-19 · **Trial:** #828 `M0244-PLACEBO30` (M0244's shape-matched placebo)
**Era:** 2009-01-01 → 2015-10-16 · **Whole window:** 1996-01-03 → 2015-10-16
**Research store:** `640fc25e5c7b8f42` (dev, unmarked) · **Prices:** `5451195fd552e208`
**Commands:**
`lab shortfall 828 --store /home/miftah/seer/engine/.research`,
`lab shortfall 828 --era whole --store ...`,
`lab shortfall 828 --against M0244-FRESH30 --store ...`,
`lab control`
**Nothing was recorded.** N (dev trials) 824 before and after; test-window looks 4 before and
after. No journal entry, so seertrade.site/sera is unchanged by this measurement itself.

## The short answer

The eight points this book lost to the market after 2009 are mostly two things that have nothing
to do with how the money was split between the names it held. Standing out of the market under
the 200-day trend rule cost 3.59 points a year, and the fees on trading fifteen times a year cost
3.78. Those two account for 7.37 of the 8.24. What is left for the pool the names were drawn from
and the equal slices they were held in — together, because one trial row cannot separate them — is
0.87 points a year, and measured against its own sibling `M0244-FRESH30` only 0.48 of that is this
arm's own weighting and selection at all. The published figure named the whole 8.2 after the one
ingredient that turns out to carry the least of it.

## What was published, and why it is being checked

On 2026-10-19 the lab published this trial's 2009-2015 shortfall as an **8.2-point equal-weight
handicap** — in insight 461, in the memory note
`seer-equal-weight-shape-costs-8pts-since-2009`, and on the `/sera` synthesis page. The arm is not
"thirty index members in equal slices". It is thirty names drawn from the fifty strongest 12-1
momentum stocks, turning over 15.05 times a year, behind the SPY 200-day gate at a recorded
whole-window exposure of 0.692. Three ingredients the published name does not mention sit inside
the number.

As a *control for M0244* the placebo is sound — its 15.05 turns against FRESH30's 15.3 is a
genuinely good match, and `lab control` now scores it 1.01x / 0.98x, clean on both axes — so
"+1.5 and +3.9 against the placebo" stands. The error was lifting one matched pair's absolute
shortfall and promoting it to a universal constant. It is a good control and a bad constant.

## The decomposition

```
Trial #828  M0244-PLACEBO30  (method M0244), dev window 1996-01-03 to 2015-10-16.
Era 2009-2015: 2009-01-01 to 2015-10-16, 82 months of the recorded monthly curve.
The owner's 236 deposits are removed from the curve before it is cut, so a deposit is never read as a gain.

  what this book earned a year                      +8.36%
  what SPY total return earned a year              +16.60%
  gap to SPY TR                                     -8.24 pts/yr

Where the gap went. Each line below is computed on its own -- one from the recorded exposure,
one from the recorded turnover and the fee schedule -- and the residual is whatever those two
do not explain. It is a residual and is never named after a cause.

  gate premium    (1 - 0.784) x 16.60%        -3.59 pts/yr
  fee drag        15.05 turns x 0.2510%       -3.78 pts/yr
  pool + weighting residual                       -0.87 pts/yr
  ----------------------------------------------------------
  these add back to the gap                       -8.24 pts/yr

Exposure. The row records 0.692 for the whole window, and this report prices the
gate at 0.784 for this era -- era-resolved, because
the gate was on 80.6% of this era's sessions against 71.2% of the whole window's, and the book was about 97.2% invested whenever the gate let it in.
Using the whole-window 0.692 instead would price the gate at -5.11 pts/yr
and leave a residual of +0.65 -- which is why this distinction is made at all.

Fees. Modelled, not recovered: what the run really paid is not a column in the trials
table. The model takes 30 names (read from the recorded configuration's outermost `top=`, which is a guess), the owner's real funding plan at
months 156 to 237 of the dev window, and prices one round trip of one slot through
Gotrade's schedule. At 10, 20, 30, 50 names the drag would be 10: -3.71, 20: -3.74, 30: -3.78, 50: -3.85 pts/yr,
so the book size is not what this answer rests on.

Cash. The gate premium assumes money out of the market earned nothing. For
2009-2015, the assumption holds here: T-bills paid about nothing after 2008, so money out of the market really did earn nothing and the gate premium below is the right size.

Read this as an attribution under stated assumptions, not an identity. The two named terms
are worked out independently and the residual absorbs the error of both, so a small residual
means the two named causes account for the gap -- not that the residual's own ingredients are
zero.

Nothing was recorded. Lab N (dev trials): 824 before, 824 after; test-window looks used: 4 before, 4 after. No journal entry, so seertrade.site/sera is unchanged and `lab stage` is not needed.
```

Whole window, for contrast:

```
Trial #828  M0244-PLACEBO30  (method M0244), dev window 1996-01-03 to 2015-10-16.
Era whole window: 1996-01-03 to 2015-10-16, 238 months of the recorded monthly curve.
The owner's 236 deposits are removed from the curve before it is cut, so a deposit is never read as a gain.

  what this book earned a year                      +7.33%
  what SPY total return earned a year               +7.91%
  gap to SPY TR                                     -0.58 pts/yr

Where the gap went. Each line below is computed on its own -- one from the recorded exposure,
one from the recorded turnover and the fee schedule -- and the residual is whatever those two
do not explain. It is a residual and is never named after a cause.

  gate premium    (1 - 0.692) x 7.91%        -2.44 pts/yr
  fee drag        15.05 turns x 0.2667%       -4.01 pts/yr
  pool + weighting residual                       +5.87 pts/yr
  ----------------------------------------------------------
  these add back to the gap                       -0.58 pts/yr

Exposure. The row records 0.692 for the whole window, and this report prices the
gate at 0.692 for this era -- era-resolved, because
the gate was on 71.2% of this era's sessions against 71.2% of the whole window's, and the book was about 97.2% invested whenever the gate let it in.
Using the whole-window 0.692 instead would price the gate at -2.44 pts/yr
and leave a residual of +5.87 -- which is why this distinction is made at all.

Fees. Modelled, not recovered: what the run really paid is not a column in the trials
table. The model takes 30 names (read from the recorded configuration's outermost `top=`, which is a guess), the owner's real funding plan at
months 0 to 237 of the dev window, and prices one round trip of one slot through
Gotrade's schedule. At 10, 20, 30, 50 names the drag would be 10: -3.80, 20: -3.91, 30: -4.01, 50: -4.22 pts/yr,
so the book size is not what this answer rests on.

Cash. The gate premium assumes money out of the market earned nothing. For
whole window, this era spans both: before 2008 the money the gate held back earned a real rate in T-bills, and after 2008 it earned about nothing. So the gate premium here is somewhat larger than the truth.

Read this as an attribution under stated assumptions, not an identity. The two named terms
are worked out independently and the residual absorbs the error of both, so a small residual
means the two named causes account for the gap -- not that the residual's own ingredients are
zero.

Nothing was recorded. Lab N (dev trials): 824 before, 824 after; test-window looks used: 4 before, 4 after. No journal entry, so seertrade.site/sera is unchanged and `lab stage` is not needed.
```

Against its sibling FRESH30, which splits the residual into the part the pool and frame carry and
the part that is this arm's own:

```
Trial #828  M0244-PLACEBO30  (method M0244), dev window 1996-01-03 to 2015-10-16.
Era 2009-2015: 2009-01-01 to 2015-10-16, 82 months of the recorded monthly curve.
The owner's 236 deposits are removed from the curve before it is cut, so a deposit is never read as a gain.

  what this book earned a year                      +8.36%
  what SPY total return earned a year              +16.60%
  gap to SPY TR                                     -8.24 pts/yr

Where the gap went. Each line below is computed on its own -- one from the recorded exposure,
one from the recorded turnover and the fee schedule -- and the residual is whatever those two
do not explain. It is a residual and is never named after a cause.

  gate premium    (1 - 0.784) x 16.60%        -3.59 pts/yr
  fee drag        15.05 turns x 0.2510%       -3.78 pts/yr
  pool + frame (shared with M0244-FRESH30)     -0.39 pts/yr
  this arm's own weighting and selection           -0.48 pts/yr
  ----------------------------------------------------------
  these add back to the gap                       -8.24 pts/yr

Exposure. The row records 0.692 for the whole window, and this report prices the
gate at 0.784 for this era -- era-resolved, because
the gate was on 80.6% of this era's sessions against 71.2% of the whole window's, and the book was about 97.2% invested whenever the gate let it in.
Using the whole-window 0.692 instead would price the gate at -5.11 pts/yr
and leave a residual of +0.65 -- which is why this distinction is made at all.

Fees. Modelled, not recovered: what the run really paid is not a column in the trials
table. The model takes 30 names (read from the recorded configuration's outermost `top=`, which is a guess), the owner's real funding plan at
months 156 to 237 of the dev window, and prices one round trip of one slot through
Gotrade's schedule. At 10, 20, 30, 50 names the drag would be 10: -3.71, 20: -3.74, 30: -3.78, 50: -3.85 pts/yr,
so the book size is not what this answer rests on.

Cash. The gate premium assumes money out of the market earned nothing. For
2009-2015, the assumption holds here: T-bills paid about nothing after 2008, so money out of the market really did earn nothing and the gate premium below is the right size.

Read this as an attribution under stated assumptions, not an identity. The two named terms
are worked out independently and the residual absorbs the error of both, so a small residual
means the two named causes account for the gap -- not that the residual's own ingredients are
zero.

Nothing was recorded. Lab N (dev trials): 824 before, 824 after; test-window looks used: 4 before, 4 after. No journal entry, so seertrade.site/sera is unchanged and `lab stage` is not needed.
```

### What each term is, and what it is not

- **Gate premium, −3.59 pts/yr.** Priced at an **era-resolved** exposure of **0.784**, not the
  recorded whole-window 0.692: the gate was on 80.6% of this era's sessions against 71.2% of the
  whole window's, and the book was about 97.2% invested whenever the gate let it in. The
  distinction is load-bearing and not polish — at the recorded 0.692 the gate would price at
  −5.11 and the residual would flip sign to **+0.65**. The 2009-2015 window contains no bear
  market at all (M0245 counted the exits), so every post-2009 exit was a false alarm, and cash
  earned about nothing after 2008 (`seer-idle-cash-credit-worth-08-before-2008-only`). The same
  batch measured the gate's false-alarm premium directly and then attributed the same money to
  equal weighting in the same document.
- **Fee drag, −3.78 pts/yr** = 15.05 turns a year × 0.2510% per dollar of notional, the mean rate
  over the era's own month offsets 156..237. A model of the fees at the era's slot size, not the
  fees the run paid — `RunStats.costs_usd` is not a `trials` column. The name count is **30**,
  read out of trial 828's own recorded configuration with no `--names` flag passed, and the
  report's sensitivity band says the guess cannot change the answer: at 10/20/30/50 names the drag
  reads −3.71 / −3.74 / −3.78 / −3.85. The independent check: the model predicts a ~2.9 pt
  difference between this arm and `M0244-STALE30` (3.57 turns), against an observed gap difference
  of 3.94 pts (−8.24 vs −4.30).
- **Pool + weighting residual, −0.87 pts/yr.** Nothing in a trial row names the pool a book was
  drawn from, so these two cannot be separated from one row; the `--against M0244-FRESH30` run
  above is the only honest split and it is a *peer* split, not an identity — **−0.39 shared pool
  and frame, −0.48 this arm's own weighting and selection**.
- **This is an attribution under stated assumptions, not an identity.** The terms are computed
  independently and the residual absorbs their error.

**One number differs from the plan's expectation block, and the run is what is recorded here.**
The plan expected a gate premium of −3.60; the report prints **−3.59** at the same exposure of
0.784. It is a rounding difference in the last digit of a term computed from the era's own
on-share, it moves nothing, and the reconciled gap / fees / residual (−8.24 / −3.78 / −0.87)
reproduced to the digit.

## The control table

```
control shape -- does each placebo carry the shape of the book it controls?
a control is clean inside 0.80-1.25 on both trades and turnover, flagged outside that, and refused outside 0.50-2.00; the band was cut from the lab's own control arms, where clean ones sit at 0.98-1.02 and every mis-shaped one is past 2.9x or under 0.14x on at least one axis
read from recorded dev trials only: nothing is run, nothing is written, and the test window is not touched.

    method  control               kind                  controls          resolved by     trades x  turnover x      verdict
    ------  --------------------  --------------------  ----------------  --------------  --------  ----------  -----------
    M0047   M0047-PLC1-MV10       placebo               M0047-EQ          first-declared      0.55        0.50       refuse
    M0047   M0047-PLC1-MV20       placebo               M0047-EQ          first-declared      0.55        0.51         warn
    M0187   M0187-H1              placebo               —                 —                      —           —   unresolved
    M0187   M0187-H2              placebo               —                 —                      —           —   unresolved
    M0187   M0187-H3              placebo               —                 —                      —           —   unresolved
    M0187   M0187-H1-SW           placebo               —                 —                      —           —   unresolved
    M0187   M0187-H2-SW           placebo               —                 —                      —           —   unresolved
    M0187   M0187-H3-SW           placebo               —                 —                      —           —   unresolved
    M0193   M0193-S1-SW           placebo               —                 —                      —           —   unresolved
    M0193   M0193-S2-SW           placebo               —                 —                      —           —   unresolved
    M0193   M0193-S3-SW           placebo               —                 —                      —           —   unresolved
    M0193   M0193-S1-40-SW        placebo               —                 —                      —           —   unresolved
    M0193   M0193-S1              placebo               —                 —                      —           —   unresolved
    M0195   M0195-PLC-B100-FAST   placebo               M0195-B100-FAST   first-declared      1.01        1.00           ok
    M0201   M0201-PLC1-MV10       placebo               M0201-Y20-MV10    first-declared      2.27        2.13       refuse
    M0201   M0201-PLC2-MV10       placebo               M0201-Y20-MV10    first-declared      2.26        2.12       refuse
    M0202   M0202-PLC1-HALF       placebo               M0202-Y20-HALF    first-declared      2.25        2.01       refuse
    M0202   M0202-PLC2-HALF       placebo               M0202-Y20-HALF    first-declared      2.25        1.99       refuse
    M0202   M0202-PLC1-HALF-FAST  placebo               M0202-Y20-HALF    first-declared      2.25        2.20       refuse
    M0203   M0203-HASH-N20        placebo               M0203-TF-N20      first-declared      1.56        1.60         warn
    M0207   M0207-B1              placebo               —                 —                      —           —   unresolved
    M0207   M0207-B2              placebo               —                 —                      —           —   unresolved
    M0207   M0207-B3              placebo               —                 —                      —           —   unresolved
    M0207   M0207-B1-SW           placebo               —                 —                      —           —   unresolved
    M0207   M0207-P50-1           placebo               —                 —                      —           —   unresolved
    M0208   M0208-HASH-N20        placebo               M0208-CGO-N20     first-declared      4.41        5.20       refuse
    M0210   M0210-HASH-N20        placebo               M0210-RESID-N20   first-declared      1.86        2.00         warn
    M0213   M0213-HASH-CAP4       placebo               M0213-HASH        sibling-stem        1.01        1.01           ok
    M0214   M0214-H3-20           placebo               M0214-C3-20       first-declared      1.51        1.67         warn
    M0215   M0215-HASH            placebo               M0215-CTRL        first-declared      0.34        0.43       refuse
    M0215   M0215-HASH-CAP4       placebo               M0215-CTRL        first-declared      0.34        0.43       refuse
    M0216   M0216-HASH-T3-W6      placebo               M0216-T3-W6       first-declared      1.03        1.01           ok
    M0221   M0221-R50             placebo               M0221-C50         first-declared      0.21        0.50       refuse
    M0222   M0222-RAND1           placebo               M0222-CORE        declared-idea       0.98        4.45       refuse
    M0222   M0222-RAND2           placebo               M0222-CORE        declared-idea       1.06        8.86       refuse
    M0223   M0223-PLC1-B5X4       placebo               M0223-B5X4        first-declared      0.82        0.77         warn
    M0225   M0225-R50             placebo               M0225-C50         first-declared      0.19        0.42       refuse
    M0226   M0226-RAND1           placebo               M0226-CORE        declared-idea       0.98        6.93       refuse
    M0226   M0226-RAND2           placebo               M0226-CORE        declared-idea       1.33       14.53       refuse
    M0227   M0227-R20             placebo               M0227-S20         first-declared      0.07        0.12       refuse
    M0230   M0230-C70             dose-response         —                 —                      —           —  not-checked
    M0230   M0230-C30             dose-response         —                 —                      —           —  not-checked
    M0230   M0230-C50-R           placebo               M0230-C50         sibling-stem        0.07        0.14       refuse
    M0232   M0232-PLC1            placebo               M0232-NEAR-HIVOL  first-declared      1.28        1.30         warn
    M0241   M0241-STALE           dose-response         —                 —                      —           —  not-checked
    M0241   M0241-PLACEBO         placebo               M0241-SPLIT12     first-declared      1.37        1.13         warn
    M0243   M0243-NEAR20-T3       dose-response         —                 —                      —           —  not-checked
    M0243   M0243-NEAR20-R        placebo               M0243-NEAR20      sibling-stem        3.01        2.98       refuse
    M0244   M0244-STALE30         dose-response         —                 —                      —           —  not-checked
    M0244   M0244-PLACEBO30       placebo               M0244-FRESH30     first-declared      1.01        0.98           ok
    M0245   M0245-FALL63          dose-response         —                 —                      —           —  not-checked
    M0248   M0248-B100            within-frame control  —                 —                      —           —  not-checked
    M0248   M0248-D100            within-frame control  —                 —                      —           —  not-checked
    M0248   M0248-R               placebo               M0248-EQ          declared-idea       3.18        3.08       refuse

    what to read before quoting a control gap
      M0047-PLC1-MV10 (against M0047-EQ, resolved by first-declared): trades 0.55x and turns over 0.50x the arm it controls, outside the 0.50-2.00 band: the control carries a different cost and a different cadence, so the gap between them is not evidence about the signal
      M0047-PLC1-MV20 (against M0047-EQ, resolved by first-declared): trades 0.55x and turns over 0.51x the arm it controls, outside the 0.80-1.25 match band: read the gap with that in mind
      M0201-PLC1-MV10 (against M0201-Y20-MV10, resolved by first-declared): trades 2.27x and turns over 2.13x the arm it controls, outside the 0.50-2.00 band: the control carries a different cost and a different cadence, so the gap between them is not evidence about the signal
      M0201-PLC2-MV10 (against M0201-Y20-MV10, resolved by first-declared): trades 2.26x and turns over 2.12x the arm it controls, outside the 0.50-2.00 band: the control carries a different cost and a different cadence, so the gap between them is not evidence about the signal
      M0202-PLC1-HALF (against M0202-Y20-HALF, resolved by first-declared): trades 2.25x and turns over 2.01x the arm it controls, outside the 0.50-2.00 band: the control carries a different cost and a different cadence, so the gap between them is not evidence about the signal
      M0202-PLC2-HALF (against M0202-Y20-HALF, resolved by first-declared): trades 2.25x and turns over 1.99x the arm it controls, outside the 0.50-2.00 band: the control carries a different cost and a different cadence, so the gap between them is not evidence about the signal
      M0202-PLC1-HALF-FAST (against M0202-Y20-HALF, resolved by first-declared): trades 2.25x and turns over 2.20x the arm it controls, outside the 0.50-2.00 band: the control carries a different cost and a different cadence, so the gap between them is not evidence about the signal
      M0203-HASH-N20 (against M0203-TF-N20, resolved by first-declared): trades 1.56x and turns over 1.60x the arm it controls, outside the 0.80-1.25 match band: read the gap with that in mind
      M0208-HASH-N20 (against M0208-CGO-N20, resolved by first-declared): trades 4.41x and turns over 5.20x the arm it controls, outside the 0.50-2.00 band: the control carries a different cost and a different cadence, so the gap between them is not evidence about the signal
      M0210-HASH-N20 (against M0210-RESID-N20, resolved by first-declared): trades 1.86x and turns over 2.00x the arm it controls, outside the 0.80-1.25 match band: read the gap with that in mind
      M0214-H3-20 (against M0214-C3-20, resolved by first-declared): trades 1.51x and turns over 1.67x the arm it controls, outside the 0.80-1.25 match band: read the gap with that in mind
      M0215-HASH (against M0215-CTRL, resolved by first-declared): trades 0.34x and turns over 0.43x the arm it controls, outside the 0.50-2.00 band: the control carries a different cost and a different cadence, so the gap between them is not evidence about the signal
      M0215-HASH-CAP4 (against M0215-CTRL, resolved by first-declared): trades 0.34x and turns over 0.43x the arm it controls, outside the 0.50-2.00 band: the control carries a different cost and a different cadence, so the gap between them is not evidence about the signal
      M0221-R50 (against M0221-C50, resolved by first-declared): trades 0.21x and turns over 0.50x the arm it controls, outside the 0.50-2.00 band: the control carries a different cost and a different cadence, so the gap between them is not evidence about the signal
      M0222-RAND1 (against M0222-CORE, resolved by declared-idea): trades 0.98x and turns over 4.45x the arm it controls, outside the 0.50-2.00 band: the control carries a different cost and a different cadence, so the gap between them is not evidence about the signal
      M0222-RAND2 (against M0222-CORE, resolved by declared-idea): trades 1.06x and turns over 8.86x the arm it controls, outside the 0.50-2.00 band: the control carries a different cost and a different cadence, so the gap between them is not evidence about the signal
      M0223-PLC1-B5X4 (against M0223-B5X4, resolved by first-declared): trades 0.82x and turns over 0.77x the arm it controls, outside the 0.80-1.25 match band: read the gap with that in mind
      M0225-R50 (against M0225-C50, resolved by first-declared): trades 0.19x and turns over 0.42x the arm it controls, outside the 0.50-2.00 band: the control carries a different cost and a different cadence, so the gap between them is not evidence about the signal
      M0226-RAND1 (against M0226-CORE, resolved by declared-idea): trades 0.98x and turns over 6.93x the arm it controls, outside the 0.50-2.00 band: the control carries a different cost and a different cadence, so the gap between them is not evidence about the signal
      M0226-RAND2 (against M0226-CORE, resolved by declared-idea): trades 1.33x and turns over 14.53x the arm it controls, outside the 0.50-2.00 band: the control carries a different cost and a different cadence, so the gap between them is not evidence about the signal
      M0227-R20 (against M0227-S20, resolved by first-declared): trades 0.07x and turns over 0.12x the arm it controls, outside the 0.50-2.00 band: the control carries a different cost and a different cadence, so the gap between them is not evidence about the signal
      M0230-C50-R (against M0230-C50, resolved by sibling-stem): trades 0.07x and turns over 0.14x the arm it controls, outside the 0.50-2.00 band: the control carries a different cost and a different cadence, so the gap between them is not evidence about the signal
      M0232-PLC1 (against M0232-NEAR-HIVOL, resolved by first-declared): trades 1.28x and turns over 1.30x the arm it controls, outside the 0.80-1.25 match band: read the gap with that in mind
      M0241-PLACEBO (against M0241-SPLIT12, resolved by first-declared): trades 1.37x and turns over 1.13x the arm it controls, outside the 0.80-1.25 match band: read the gap with that in mind
      M0243-NEAR20-R (against M0243-NEAR20, resolved by sibling-stem): trades 3.01x and turns over 2.98x the arm it controls, outside the 0.50-2.00 band: the control carries a different cost and a different cadence, so the gap between them is not evidence about the signal
      M0248-R (against M0248-EQ, resolved by declared-idea): trades 3.18x and turns over 3.08x the arm it controls, outside the 0.50-2.00 band: the control carries a different cost and a different cadence, so the gap between them is not evidence about the signal

19 control arm(s) sit outside 0.50x..2.00x on at least one
axis. `lab promote` refuses a method holding one (lab/hardgate.py, D17), and any
sentence already written about one of those margins is quoted against a
handicapped opponent. The way back costs no method id: re-draw the control at the
book's own trade count and turnover and run it again as an amendment.

recorded dev trials 824 -> 824; test-window looks 4 -> 4. Nothing was written, no research store was opened and no method id was minted.
```

Nineteen of the lab's 46 placebo arms sit outside the refuse band — measured on this branch,
**19 refuse, 7 warn, 4 clean, 16 with no arm to compare against**, beside 6 dose-response and 2
within-frame arms that are listed and never flagged (54 rows in all). Two of the nineteen were
known — `M0230-C50-R` (0.07x / 0.14x against `M0230-C50`) and `M0248-R` (3.18x / 3.08x against
`M0248-EQ`). `M0243-NEAR20-R` (3.01x / 2.98x against `M0243-NEAR20`) was found by writing the
rule down. The handover knew of two; the measurement finds nineteen. From this phase,
`lab promote` refuses a method holding one (hardgate D17) and `lab run` prints the reading without
refusing (D15).

**The reconciled fact about who this stops — both halves, stated the same way here as in D17 and
in the plan index:**

> **`Promotable now:` is unchanged by D17, AND nine dev-eligible methods would be refused at
> `lab promote` if they ever reached it.**

`Promotable now:` reads `M0072 M0072-Z2-RAWRANK`, `M0092 M0092-SQRT-CAP10` and
`M0197 M0197-Y20-SW` before this phase and the identical three after it — the `lab status` taken
before the first edit and the one taken after the clause landed differ in nothing (`diff` →
`PROMOTABLE UNCHANGED`). None of those three methods holds a control arm at all. The nine
dev-eligible methods that do hold a refuse-band control arm are **M0047, M0201, M0202, M0208,
M0215, M0221, M0225, M0227, M0243** — each verified individually with `lab control MNNNN` and each
confirmed `dev-eligible` against the committed database. M0222, M0226, M0230 and M0248 all hold
refuse-band arms too and are already `rejected`, so they change nothing either way; M0241 is
dev-eligible and warn-only (1.37x / 1.13x).

Those nine are the point of the feature, not a side effect: each of them quotes, or could quote,
"this beat its control by X" against a control that was not the shape of the book, which is the
unsound sentence this whole plan set exists to stop. **Every one of them has the same way back and
it costs no method id** — re-draw the control at the book's own trade count and turnover and record
it as an amendment under the existing method id, which is exactly what the handover's §2 asks for
on M0248. D17's refusal message names that path, so a researcher who meets it is not at a dead
end.

## The three corrections this note asks for

**This note states them; it does not apply them.** `insights` is append-only, a `/sera` correction
runs through the `update-stale-sera-methods-page` skill, and a memory note is the owner's file.

### 1. `MEMORY.md` line 70 and `seer-equal-weight-shape-costs-8pts-since-2009.md`

Standing text (line 70):

> `- [An equal-weight book loses 8 pts/yr to SPY by shape alone](seer-equal-weight-shape-costs-8pts-since-2009.md) — measured on a coin-flip placebo in 2009-2015; subtract it before blaming the signal.`

Replace with:

> `- [The "8 pt equal-weight handicap" was the gate and the fees](seer-equal-weight-shape-costs-8pts-since-2009.md) — decomposed 2026-10-19: ~3.6 of trial 828's 8.2 was the SPY-200 gate and ~3.8 was fee drag on 15 turns/yr; pool and weighting together are bounded under 0.9. Never subtract it as a constant.`

The note body's three load-bearing claims and their replacements:

| Standing claim | Replacement |
|---|---|
| "**−8.2 pts/yr vs SPY TR over 2009-2015**, with no signal in it at all" | stands as the *gap*, but it is not the shape: **−3.59** is the gate at an era-resolved exposure of **0.784**, **−3.78** is fees on 15.05 turns/yr, and **−0.87** is everything pool and weighting can account for together |
| "an equal-weight book starts ~8 points behind before it picks anything" | withdrawn. External check points the other way: equal-weight S&P 500 beat cap-weight over 2009-2015 by roughly 2-3 pts/yr |
| "when a method's 2009-2015 lead is −4 to −9 pts/yr … subtract the placebo first" | stands **only** for a placebo matched to that book's own shape, which is what `lab control` now measures; it is not a constant to carry between methods |

The sound half survives verbatim: "+1.5 and +3.9 against the placebo in that era: the signal
worked, the vehicle lost."

### 2. Insight 461

Two passages. First, in the board-confidence paragraph:

> "But the whole book was thirty index members in equal slices, and that shape lost 8.2 points a
> year to the market after 2009 — more than every stock-picking edge the lab has measured. An
> equal-weight book starts eight points behind before it picks a single company. That number now
> explains more of the lab's record than any signal failure."

Replacement:

> "But the whole book was thirty momentum-screened names in equal slices, traded fifteen times a
> year behind the 200-day rule, and it lost 8.2 points a year to the market after 2009. Decomposed
> on 2026-10-19: about **3.6 points** of that was standing out of the market under the 200-day
> rule and about **3.8 points** was the fees on trading that often. What is left for the pool and
> the equal slices together is **under 0.9 points**, and against its own sibling only **0.48** of
> it is this arm's own weighting. The shape was not the handicap; the gate and the fees were, and
> this batch measured the gate's premium directly in the same document."

Second, in "What would unlock the most":

> "Second, the equal-weight handicap: every stock book the lab builds is measured against a
> cap-weighted index while holding equal slices, and the gap is now measured at eight points a
> year."

Replacement:

> "Second — withdrawn. The eight points were the gate and the fees, not the equal slices. What the
> lab should build instead is a control that matches the book it controls on trade count and
> turnover, which `lab control` now measures and `lab promote` now refuses on."

`insights` is append-only, so this is appended as a correction row (`lab insight --kind correction`
quoting this note), never an edit of 461. That act is the owner's.

### 3. The `/sera` synthesis page

`seertrade.site/sera` renders `web/data/lab.json`, which carries insight 461's body. It changes
when the correction row above is journaled and `lab stage` is run from the main checkout. Run it
through the `update-stale-sera-methods-page` skill, which is the path for a published page that
reads against evidence the lab no longer holds. **No phase of this plan stages `web/data/lab.json`.**

## What this does not say

- It does not say equal weighting is free. It says this trial's eight points are not evidence about
  it, and a method that wants to know should measure it against a control matched on both axes.
- It does not re-run any arm. The handover's §1 also suggested re-running the placebo with
  `trend=None`, at STALE-like turnover, and on a non-momentum pool. Those are three new trials and
  three method ids; this decomposition answers the same question from recorded rows for free. If
  anyone disputes the residual, those re-runs are the next step.
- It does not move `MAX_DRAWDOWN`, re-open a verdict, or touch a recorded row.

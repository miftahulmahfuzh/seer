# M0270 — the exposure/return curve, both stores, fees on and off

2026-10-21. Report only: no trial, no status change, no test-window look. The raw output of
`2026-10-21-m0270-exposure-return-curve.py` is in the `.txt` beside this file.

## Why the script exists

`lab survivorship` prints each variant on both stores, but its grid carries no **exposure** and no
**turnover** column — and exposure is this method's x axis. So the cross-store curve could not be
drawn from the lab's own report. The script loads each store once, runs the six recorded arms plus
six zero-fee twins against it in ONE `dev.run_registry` sweep at the recorded capital and funding,
and prints exposure, turnover, fees, money-weighted return, worst fall and profit factor per rung.
Both stores in one process, so insight 482's rule (a ratio across two store vintages is not a
comparison) is satisfied by construction; both fingerprints are printed.

## The four curves

Global slope, in points a year of money-weighted return per point of the account invested, over
the realised range 69.1% → 98.6%:

| curve | slope | bend (bottom rung pair ÷ top rung pair) | worst-fall slope |
|---|---|---|---|
| dev, fees paid | **0.0623** | 0.0656 / 0.0590 = +11% | 0.4512 |
| dev, fees off | 0.0709 | 0.0743 / 0.0669 = +11% | — |
| check store, fees paid | **0.0375** | 0.0414 / 0.0343 = +21% | 0.5093 |
| check store, fees off | 0.0473 | 0.0512 / 0.0440 = +16% | 0.5189 |

Straight-line error over every one of the 15 rung pairs, on all four curves: **at most 0.034
points a year**, including the widest pair at 29.5 points of exposure. No sign flip anywhere.

* **Fees are a level effect, not a shape effect.** They cost about 0.009 points a year per point
  of exposure on both stores — roughly an eighth of the gross value of being invested — and the
  bend is the same size with them switched off. The pre-registered worry that the curve was
  Gotrade's per-order minimum biting a smaller book is refuted.
* **Dividing by exposure over-corrects.** The chord from the origin reads 0.0705 (dev) and 0.0479
  (check) against measured global slopes of 0.0623 and 0.0375, so the multiplicative correction
  over-states a gap's cost by 13% and 28%. Subtract the measured slope instead.
* **M0266's factor of eight is not real.** Its two-point reading of 0.0078 on the check store has
  no counterpart anywhere on this ladder, whose five consecutive readings there run 0.0343 to
  0.0414. On the dev store M0266's 0.0661 agrees with this ladder's 0.062-0.064 in the same
  stretch to within 5%, so the disagreement is the two-point reading, not the chassis.

## The era table (`lab timing`, de-funded lead against SPY)

Lead in points a year at each rung, and the slope across the full 29.5-point exposure span:

| era | S100 | S094 | S088 | S082 | S076 | S070 | slope | SPY's own return |
|---|---|---|---|---|---|---|---|---|
| 1996–2002 | +2.06 | +1.65 | +1.21 | +0.77 | +0.31 | −0.17 | 0.0756 | +6.57%/yr |
| 2003–2008 | −1.49 | −1.50 | −1.52 | −1.55 | −1.59 | −1.64 | **0.0051** | +2.28%/yr |
| 2009–2015 | +0.52 | −0.50 | −1.52 | −2.54 | −3.57 | −4.59 | **0.1732** | +15.03%/yr |

A 34-fold range between eras, against a 1.66-fold range between stores and a 1.14-fold range
between fees on and off. **The era is by far the biggest thing that moves this number.**

`lab shortfall` already prices time out of the market at the era's own market return and uses
16.60%/yr for 2009–2015, i.e. 0.166 per point. The ladder measures 0.1732 — agreement to 4%, so
that model is now measured rather than assumed, *for an era claim*. For a whole-window claim it
would say 0.081 where the truth is 0.062.

## The tolerance (the pre-registered deliverable)

An uncorrected exposure gap of Δ points costs Δ × slope. At a tenth of a point a year:

| claim | slope | gap allowed |
|---|---|---|
| whole window, dev store | 0.0623 | 1.6 points |
| whole window, check store | 0.0375 | 2.7 points |
| 2009–2015 | 0.1732 | **0.6 points** |

The recommendation in the method's analysis is the strict one: **match to half a point and do not
correct at all.** Half a point costs 0.087 points a year even in the expensive era, and a
tolerance that needs no slope cannot be wrong about which slope to use.

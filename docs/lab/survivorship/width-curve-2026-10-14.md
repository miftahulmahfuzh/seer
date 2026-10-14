# The width curve, measured on both histories (2026-10-14)

*Report only: no trial was recorded, the lab's trial count and its test-window looks did not move.
Produced by M0147. The grids are `width-curve-2026-10-14.csv` (M0147's six arms) and
`width-curve-cross-family-2026-10-14.csv` (M0139, M0128 and M0110, re-read with `--no-journal`).
All dev re-runs reproduced their recorded trials exactly.*

## Why this is separate from `grid.csv`

`grid.csv` is the 2026-10-10 record of 102 variants and D16 reads it directly. These rows were
measured four days later for a different purpose — a *paired curve in book width* — and are kept
beside it rather than merged into it, so the file D16 reads stays the one it was written against.
Merging them is a deliberate decision for whoever next revises D16, not a side effect of a run.

## Worst fall from a peak, by number of names held

The gated up/down-asymmetry book (M0147, `monthly-hold-frac-gotrade-tband`, funded on the owner's
plan). Money in its own picks was 69.9–70.0% at *every* width, so none of this is a cash artefact.

| names | dev store | check store | gap | funded %/yr dev | funded %/yr check | MAR dev | MAR check |
|---|---|---|---|---|---|---|---|
| 20 | 22.7% | 29.4% | +6.7 | +15.6 | +16.4 | 0.69 | 0.56 |
| 30 | 21.0% | 26.2% | +5.3 | +14.7 | +15.3 | **0.70** | 0.58 |
| 40 | 21.5% | 23.1% | +1.6 | +13.8 | +14.9 | 0.64 | 0.65 |
| 55 | 20.2% | 20.4% | +0.2 | +12.6 | +13.9 | 0.62 | **0.68** |
| 70 | 20.6% | 20.3% | −0.3 | +11.9 | +13.2 | 0.58 | 0.65 |
| 70, gate off | 63.5% | 66.3% | +2.9 | +9.0 | +9.1 | 0.14 | 0.14 |

The residual-momentum book the roster holds, same preset, at the widths already recorded
(M0128-RAW20 and M0139's three `-TBAND` arms):

| names | dev store | check store | gap | MAR dev | MAR check |
|---|---|---|---|---|---|
| 20 | 20.7% | 25.1% | +4.4 | 0.66 | 0.48 |
| 35 | 19.6% | 20.1% | +0.5 | **0.67** | **0.60** |
| 50 | 20.7% | 20.0% | −0.7 | 0.55 | 0.60 |
| 70 | 19.9% | 19.8% | −0.1 | 0.55 | 0.55 |

The equity-basis (`-EBAND`) twins differ from these by at most 0.5 of a point of fall, so the
rebalance basis is not what produces the curve.

## What it shows

1. **The dev store is flat in width; the check store is not.** 2.1 points of movement across
   20→70 names on dev, 9.1 on the check store, monotone at every rung. The roster's family shows
   the same shape: 0.8 points on dev, 5.3 on the check store.
2. **The gap between the two histories is itself a function of width**, closing from +6.7 points
   at 20 names to nothing by 55. Width is protection against one company failing alone, and the
   dev store prices no delisted name, so behind a market gate there is nothing left on that tape
   for width to protect against.
3. **The ranking inverts.** Dev-store MAR picks 30 names and rates 20 second; check-store MAR
   picks 55 and rates 20 *last*. Same for the roster's family: dev rates 20 and 35 level, the
   check store puts 20 a clear last.
4. **The gate is what hides it.** With the gate off, width moves the dev-store fall 10.5 points
   (74.0% at 20 names → 69.1% at 40 → 63.5% at 70) and the check-store fall 9.6 points
   (75.9% → 66.3%). The gate removes market-wide falls; the dev store removes single-name
   collapses; behind the gate on dev, both are gone.

## Limits

- The check store adds *most* of the members the dev store cannot price, not all, and real
  collapses were kept while data errors were cleaned — a judgement call, not ground truth.
- **The report does not date a drawdown**, so "the width effect is one bad year" cannot be ruled
  out from these rows alone. A feature-wish is journaled for peak and trough dates.
- M0110-DP40 ranks on downside participation, not the up/down spread, so it is *not* the ungated
  40-name twin; the 69.1% figure in point 4 is M0133-N40.

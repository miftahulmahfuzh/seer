# M0271 — the SPY 200-day switch: cash, or judgement?

Three report-only scripts, no trial, no look, nothing written to the lab.

| script | what it answers | output |
|---|---|---|
| `2026-10-21-m0271-gate-cash-or-judgement.py` | the re-entry-delay ladder, per era, on both stores, with zero-fee twins | `…-gate-cash-or-judgement.txt` |
| `2026-10-21-m0271-where-the-cost-sits.py` | where the 2009–2015 cost actually comes out, month by month and episode by episode | `…-where-the-cost-sits.txt` |
| `2026-10-21-m0271-across-the-lab.py` | the same arithmetic on twelve recorded gated books spanning twelve ideas | `…-across-the-lab.txt` |

## The pre-registered question

Insight 532: the switch's famous 3.6 points a year since 2009 (insight 463) may be nothing but its
time in cash, priced at M0270's measured 0.1732 points a year per point of cash in that era.
3.6 / 0.1732 = 20.8 points, which is about what a 200-day rule sits out in a decade with no crash.

## The ladder (dev store `640fc25e5c7b`, de-funded lead over SPY TR, net of Gotrade's real fees)

| arm | wait | whole-window cash | lead | 2009–15 cash | 2009–15 lead |
|---|---|---|---|---|---|
| `M0271-OFF` | gate off | 1.43 | +0.39 | 0.80 | **+0.52** |
| `M0271-D000` | 0 sessions | 29.18 | **+2.55** | 20.94 | **−6.19** |
| `M0271-D006` | 6 | 35.64 | −1.03 | 22.30 | −7.62 |
| `M0271-D016` | 16 | 40.22 | −1.61 | 28.38 | −8.54 |
| `M0271-D030` | 30 | 45.18 | −3.03 | 33.08 | −9.96 |
| `M0271-D042` | 42 | 48.18 | −3.77 | 38.16 | −11.60 |

`M0271-OFF` reproduces `M0270-S100` to the digit (+6.949% money-weighted, 59.55% fall, 1338
trades), which is what licenses using 0.1732 here at all. Realised cash is monotone in the dial on
both windows and within 2 points of the switch's own calendar, so the x axis is sound — except in
1996–2002, where the 30- and 42-session rungs saturate at the same value.

## The residual, era by era

`R = (the gate's measured cost) − 0.1732 × (its points of cash)`, against the rms residual of the
five delay rungs about their own fitted line.

| era | measured | predicted by cash | **R** | rung scatter | slope of episodic cash |
|---|---|---|---|---|---|
| whole window | **−2.16** (it earned) | +1.73 | **−3.89** | 0.52 | 0.3145 |
| 1996–2002 | −4.58 | +2.67 | **−7.25** | 0.84 | 0.4410 |
| 2003–2008 | −6.78 | +0.14 | **−6.92** | 0.35 | 0.2537 |
| 2009–2015 | **+6.71** | +3.49 | **+3.22** | 0.35 | **0.2832** |

Pre-registered: |R| ≤ 0.5 confirms, |R| ≥ 1.0 falsifies. Every era falsifies, by 6–20× the scatter,
and the sign flips between decades. **Robustness:** 2009–2015 R is +3.30 with fees switched off
entirely and +2.66 on the survivorship-check store `f3dc6ff52994`. Neither fees nor the missing dead
companies explain it.

## The three-way split of the 2009–2015 bill (6.71 pts/yr)

| | pts/yr | how it was obtained |
|---|---|---|
| simply holding 20.1 points of cash | 3.49 | M0270's 0.1732 × 20.14 |
| holding it in lumps at the switch's boundary rather than evenly | 1.79 | the delay line's own slope, 0.2832 |
| the switch's own choice of which lumps | 1.44 | the delay line extrapolated to `OFF`: P −0.92 against A +0.52 |

## Where it comes out, month by month

94% of the gap is the months the switch was out; 6% is fees plus the different fifty names it owns
after each round trip. The book ran at ~28%/yr in the 16 out-months and ~14%/yr in the 65 in-months
(SPY: 24% against 15%). Four out-episodes; **February–June 2009 carries 1.54 of the 2.28 points of
episode cost — 68%.** The size of the judgement term rests on one absence; its direction does not.

## Across the lab — twelve books, twelve ideas

Measured gate cost ÷ what cash explains, each run as recorded and again gate-off in one sweep:

| era | median ratio | range |
|---|---|---|
| whole window | **−0.80** | −2.90 to +0.65 |
| 1996–2002 | −0.23 | −3.48 to +2.16 |
| 2003–2008 | **−53** | −72 to −27 |
| 2009–2015 | **1.42** | 0.59 to 3.05 |

**The decisive dispersion.** In 2009–2015 the measured cost runs 0.60 → 10.37 pts/yr (17×); the cash
model's prediction runs 0.92 → 3.47, and 2.83 → 3.47 across the eleven fully invested books (1.23×).
The constancy of the 3.6 is the constancy of the formula. `M0007-N20-RAW` — the roster's own book
and one of the four spent test looks — happens to land at a ratio of 1.02, which is probably why the
model looked right.

## Verdict

The hypothesis is refuted in every era. The switch is a large, real timing rule whose value is an
era variable spanning about ten points a year, not a cash dial. The lab should stop quoting the
model's output as the switch's measured cost, and stop tuning *when* the switch is read.

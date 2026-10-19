# The band's worth is a function of how often the gate is read, and at the lab's own cadence it is zero

**Measured:** 2026-10-19 · **Instrument:** SPY alone, no stock picking
**Window:** 1993-01-29 → 2015-10-16 (dev store `engine/.research`), 200-bar warmup
**Script:** `2026-10-19-gate-band-cadence.py` (re-runnable)
**Nothing was recorded.** No method, no trial, no N, no test-window look. This is a study on
market data, not a lab result. It is a prior, and the method that tests it is M0258.

**This note corrects the framing of `2026-10-19-gate-band-study.md` and of insight 464.** Neither
is wrong about what it measured. Both compared a price band against a gate read **every day**, and
no book in this lab reads its gate every day. Against the gate the lab actually runs, the band's
advantage is gone.

## The question

The gate-band study acts on SPY's close daily: 151 flips, 76 off-episodes, and a 3% band that beats
the bare gate on every axis. But every lab book reads its gate at its own rank session — monthly
for M0070, M0088, M0101, M0241 and M0245, weekly for M0063, M0072 and M0078 — and holds that
reading until the next one. A reading held for a month already suppresses every flip shorter than a
month. That is most of what a band does. So: how much of the study's finding is the band, and how
much is the daily reading nobody runs?

Cross the two axes. Same bars, same warmup, same one-session lag, same arithmetic; only the cadence
moves.

## The grid

| signal | gate read | whole CAGR | whole worst fall | 2009-2015 | invested | flips |
|---|---|---|---|---|---|---|
| bare gate | daily | 6.05% | −28.7% | 6.96% | 71.6% | 152 |
| bare gate | weekly | 5.51% | −34.6% | 5.82% | 70.8% | 80 |
| **bare gate** | **monthly** | **9.08%** | **−19.0%** | **10.07%** | 71.9% | 22 |
| band 1.5% | daily | 7.35% | −19.5% | 9.44% | 70.8% | 46 |
| band 1.5% | weekly | 6.95% | −24.5% | 8.42% | 70.9% | 46 |
| band 1.5% | monthly | 7.94% | −19.0% | 10.07% | 70.4% | 32 |
| band 3% | daily | 7.87% | −20.3% | 8.83% | 72.4% | 20 |
| band 3% | weekly | 8.03% | −19.0% | 8.84% | 72.4% | 20 |
| band 3% | monthly | 8.96% | −20.7% | 9.46% | 72.4% | 18 |
| band 6% | daily | 7.91% | −20.4% | 7.02% | 70.3% | 12 |
| band 6% | weekly | 8.15% | −21.8% | 6.91% | 70.4% | 12 |
| band 6% | monthly | 7.86% | −20.7% | 6.72% | 69.7% | 12 |

The band's worth is monotone in how often the gate is read, and it reaches zero at the lab's own
monthly cadence:

| gate read | band 3% − bare gate, return | band 3% − bare gate, worst fall |
|---|---|---|
| daily | **+1.82 pts/yr** | **8.4 pts better** |
| weekly | **+2.53 pts/yr** | **15.5 pts better** |
| monthly | **−0.12 pts/yr** | **1.7 pts worse** |

(Those differences are taken at full precision, which is what the script prints and what a reader
re-running it will see. Differencing the two-decimal grid above instead gives the weekly pair as
+2.52 and 15.6 — the same facts, one hundredth and one tenth apart.)

And the sentence that matters: **the monthly bare gate beats the daily 3% band on every axis in the
original study's own table** — return 9.08% against 7.87%, worst fall −19.0% against −20.3%, and
2009-2015 10.07% against 8.83%.

## The mechanism is not new, it is the same one

A band suppresses flips shorter than the band is wide. A monthly reading suppresses flips shorter
than a month. They are two ways of doing one thing, and once one of them is in place the other has
almost nothing left to do. The study's own numbers say so and it read them the other way round: its
3% band leaves "exactly 11 episodes — the number insight 452 reports", and insight 452 counted the
gate **at its monthly checks**. The study took that coincidence as evidence that the lab had been
reasoning about a cleaner gate than the one it runs. It is the reverse. The monthly reading *is*
the cleaner gate, and it is already cleaner than the band.

## Why this grid is trusted: it reproduces four recorded trials it shares no code with

The lab has already run both signals at both cadences on SPY alone, through the full simulator, on
the owner's monthly top-ups at Gotrade's real fees. This grid is a weight path on raw closes and
shares nothing with that machinery. The worst falls line up anyway:

| recorded trial | recorded worst fall | this grid |
|---|---|---|
| the bare gate read monthly | 18.89% | 19.0% |
| the 3% band read monthly | 20.69% | 20.7% |
| the bare gate read weekly | 33.13% | 34.6% |
| the 3% band read weekly | 18.92% | 19.0% |

And the money agrees, which is what matters. Those four trials are funded with the owner's real
monthly top-ups, so the number to read is what his money earned — against the same deposits put
into SPY, which earned 7.69% a year over that window:

| gate read | bare gate | 3% band | the band is worth | and on worst fall |
|---|---|---|---|---|
| weekly | 4.35%/yr | **7.78%/yr** | **+3.42 pts/yr** | **14.22 points shallower** |
| monthly | **9.13%/yr** | 8.73%/yr | **−0.40 pts/yr** | **1.80 points deeper** |

**A 3.82-point swing in what the band is worth, from the reading cadence alone — already recorded,
in money, and never named.** Read weekly, the bare gate loses to its own deposits in SPY by more
than three points a year and the band rescues it. Read monthly, the bare gate is the better of the
two and the band is a small, consistent cost. That is this note's claim, measured twice by
machinery that shares no code.

One more thing those rows settle. **The band did not cut turnover at monthly cadence.** It cut it
by 75% on the weekly SPY book (0.861 against 3.383), and by essentially nothing on the monthly one
(0.826 against 0.826). On M0101's monthly stock book the same holds: 4.727 against 4.780, 525
trades against 528. So "a band trades less" is a weekly-cadence fact. At monthly cadence a band
changes *when* the gate acts, not *how often*.

## What this does not establish

- **It is SPY only.** So was the study it corrects. Whether a band helps a book that holds stocks
  is the open question, and it is the question M0258 was built to answer.
- **It is the dev window**, in-sample for this lab. No test-window look was spent and none should
  be until a method exists and clears the dev screen.
- **It does not say the band is useless.** It says the band and a slow reading are substitutes, and
  the lab already has the slow reading. A book that must read its gate often — one re-picking
  weekly, say — is exactly where a band should still pay, and the recorded weekly pair agrees, by
  3.42 points a year of the owner's own money.
- **The curve-shape columns are not quoted here at all.** These books are funded, and the lab's own
  note on that is blunt: a funded book's CAGR is a lie, and `total_return` on a funded curve is not
  a return. Every figure above is either an unfunded study path (the grid) or the money-weighted
  return on the owner's deposits (the recorded trials). The two are never mixed in one sentence.
- **It is not the lab's band.** `m0101.band_on` scans back at most 504 sessions for the last
  crossing; the state machine here carries state from the first bar. The two can differ in the
  opening months of a run and agree thereafter.

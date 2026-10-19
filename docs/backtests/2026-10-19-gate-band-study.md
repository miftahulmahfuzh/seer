# The gate's premium is paid on the wrong days, not on too many of them

**Measured:** 2026-10-19 · **Instrument:** SPY alone, no stock picking
**Window:** 1993-01-29 → 2015-10-16 (dev store `engine/.research`), 200-bar warmup
**Scripts:** `2026-10-19-gate-band-variants.py` (the variant grid, re-runnable)
**Nothing was recorded.** No method, no trial, no N, no test-window look. This is a study on
market data, not a lab result — no arm of this has been through `lab run`, and until one is,
everything below is a prior and not evidence the gate accepts.

## The question

Insight 463 measured the SPY-200 gate's premium at ~3.6 pts/yr in 2009-2015 and framed it as
arithmetic: the gate is out of the market about a fifth of the time, the market rose 16.6%/yr,
(1 − 0.782) × 16.60 = 3.62. That accounting is right. The *implication* drawn from it — that the
lever is how much time a book spends out — is **wrong**, and this note withdraws it.

## The gate flips 151 times, not 11

Reconstructing `close > SMA(200)` on SPY and acting at the next close gives **76 gate-off
episodes** over the window, not the eleven insight 452 counts. 43 of them last five days or
fewer; 2000 alone contains a dozen one- to three-day flips. Three episodes carry a 20%+ dip —
those are the insurance.

The 73 short episodes sat out **+106%** of cumulative market movement between them.

## A price band fixes it, and fixes something else as well

Exit only when price closes `b%` **below** the average, re-enter only `b%` **above** it. This is a
band in price, not a lock in time — which matters, because the measured failure of a time lock was
that it suppressed the 2008 exit: baseline episode 58 ends 2008-05-19 and episode 59 begins
2008-05-21, so any "wait N days after re-entry" rule eats the crash.

| | whole return | whole DD | dot-com DD | GFC DD | 2009-15 | premium | flips |
|---|---|---|---|---|---|---|---|
| baseline gate | 6.05% | −28.7% | −21.3% | −9.7% | 6.96% | −5.27 | 151 |
| **band 3%** | **7.87%** | **−20.3%** | **−11.4%** | **−8.2%** | **8.83%** | **−3.39** | **19** |
| SPY buy-and-hold | 7.01% | −56.5% | — | — | 12.22% | — | 0 |

Better than the baseline on every axis measured, and better than buy-and-hold on return *and*
drawdown over the whole window.

## Why — and it is not the reason I went looking for

The band is invested **less**, not more, and still earns more:

| 2009-2015 | time invested | cagr | avg return on IN days | avg return on OUT days |
|---|---|---|---|---|
| baseline | 80.6% | 6.96% | 9.23%/yr | **31.57%/yr** |
| band 3% | 79.4% | 8.83% | 11.56%/yr | **21.28%/yr** |

The baseline gate systematically sits out the best days. That is the premium's real source, and it
is why "spend less time out" was the wrong lever.

The second half is bigger and was not the target at all. The baseline **fragments both crashes**
and buys back in during them — the dot-com exit is two episodes with a re-entry between (314d +
261d) and the GFC is 98d + 259d. The band holds each as one exit: 2000-10-10 → 2003-04-22 (633
days, −44.2% dip sat out) and 2007-11-13 → 2009-06-09 (395 days, −52.6%). That is why the dot-com
drawdown falls from −24.5% to −11.4%. **The gate's worst habit is re-entering during a crash, not
exiting during a calm.**

Band 3% leaves exactly **11 episodes** — the number insight 452 reports. The lab has been
reasoning about a cleaner gate than the one it actually runs.

## Attempts to disprove it

- **Smooth in the parameter, not a spike.** Across b = 1.5% … 6% the whole-window return sits
  between 7.16% and 8.50% and max drawdown between −19.1% and −21.6%, against the baseline's
  6.04% / −28.7%. A broad plateau, so 3% is not a knife-edge — read the finding as "a band of a
  few percent", never as the value 3.
- **Holds era by era**, not one lucky stretch: better on return in 4 of 5 eras and on drawdown in
  3 of 5. The one loss is 1994-1999 (−0.58 pts, −3.4 DD), a calm bull run where any exit hurts.
  The big win is 2000-2002: **+7.37 pts of return and +13.1 pts of drawdown**.
- **Leave-one-crash-out.** Excluding 2008-2009 entirely: still +1.87 pts and +9.1 pts DD.
  Excluding the dot-com entirely: still +1.39 pts and +0.6 pts DD. Neither crash carries it alone.
- **Fees fall too.** 151 flips become 19, so the gate's own turnover drops ~87%, and fees were the
  second container term in the 824-trial sweep.

## What this does not establish

- **It is SPY only.** Every lab method holds stocks; the gate is a market-level switch so it
  should carry over, but the interaction with selection is untested and that is the whole question.
- **It is the dev window**, which is in-sample for this lab. No test-window look was spent and
  none should be until a method exists and clears the dev screen.
- **The parameter was chosen after seeing results.** The plateau is the defence, not the value.
- **The premium is cut, not cured**: 5.27 → 3.39 pts/yr on SPY. Worth having; not a solution.

## Implementation, when someone builds it

`FactorParams.trend` is `tuple[str, int] | None` and `config_text` renders it `"SPY:200"`.
Widening it to carry a band would move **every recorded config digest in the lab**. So the band
belongs in a new method file behind a **new allocator id**, exactly as the shared-params rule
requires — which costs one method id, and that is the correct price for testing this.

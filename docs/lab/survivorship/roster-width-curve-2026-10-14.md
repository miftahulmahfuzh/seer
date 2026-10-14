# The roster's width curve, dated (2026-10-14)

*Report only: no trial was recorded by the measurements in this file, the lab's trial count and
its test-window looks did not move. Produced by M0152. The grid is
`roster-width-curve-2026-10-14.csv`. The three new rungs (25, 30, 45) are recorded dev trials
#471-#473; the other four are quoted from #388, #437, #438 and #439 and were not re-run under new
digests. All seven dev re-runs on the check store reproduced their recorded trials.*

## Why this file is separate from the others

`grid.csv` is the 2026-10-10 record of 102 variants and hard gate D16 reads it directly.
`width-curve-2026-10-14.csv` is M0147's six arms on the up/down-asymmetry engine.
This file is the same paired-curve measurement on **the engine the paper roster actually holds**
— M0007-N20-RAW's picks, traded fractionally at Gotrade's real fees on
`monthly-hold-frac-gotrade-tband`, funded on the owner's plan — and it carries two columns the
other two do not: **when** each worst fall happened, and the worst fall inside each era.

Keeping it beside the others rather than merged into them leaves the file D16 reads unchanged.

## The curve

Worst fall is de-funded (the owner's deposits removed, so a monthly top-up does not flatter it).
"per year" is money-weighted on the owner's plan; deposit-matched SPY TR earns **+7.2%/yr** on
both stores. Money actually invested is **0.694 at every width on both stores** — identical to
four decimal places, so nothing here is a cash artefact. The 30.6% in cash is the SPY 200-day
gate, equally for all of them.

| names | source | dev fall | check fall | gap | dev %/yr | check %/yr | dev MAR | check MAR | trades |
|---|---|---|---|---|---|---|---|---|---|
| 20 | #388 M0128-RAW20 | 20.65% | **25.05%** | +4.40 | +13.68 | +11.98 | 0.663 | 0.478 | 1607 |
| 25 | **#471 M0152-N25** | 20.07% | 21.99% | +1.92 | +13.11 | +11.85 | 0.653 | 0.539 | 1935 |
| 30 | **#472 M0152-N30** | 19.56% | 22.05% | +2.49 | +13.02 | +12.20 | 0.666 | 0.553 | 2245 |
| 35 | #437 M0139-N35-TBAND | 19.60% | **20.11%** | +0.51 | +13.05 | +12.11 | 0.666 | **0.602** | 2548 |
| 45 | **#473 M0152-N45** | 20.05% | 20.35% | +0.30 | +11.66 | +11.84 | 0.582 | 0.582 | 3086 |
| 50 | #438 M0139-N50-TBAND | 20.70% | 19.97% | −0.73 | +11.33 | +11.89 | 0.547 | 0.595 | 3367 |
| 70 | #439 M0139-N70-TBAND | 19.89% | 19.75% | −0.14 | +10.89 | +10.88 | 0.548 | 0.551 | 4169 |

**The dev column is noise** (20.7 / 20.1 / 19.6 / 19.6 / 20.1 / 20.7 / 19.9 — one point of range
across a 3.5× widening, unordered). **The check column is not** (25.1 → 19.8, 5.3 points). The gap
between the two histories is itself a function of width and closes by 45 names. This reproduces
M0147's finding on a second, independent engine.

**The decline is a staircase, not a slope.** 25 and 30 are the same book for this purpose (22.0%
and 22.1%); the protection arrives in two steps, 20→25 and 30→35. M0152 pre-registered a monotone
decline and was wrong about the shape.

## When — the column nothing else has

Worst fall inside each stretch, de-funded, month-end granularity, check store:

| names | 1998 (Russia/LTCM) | 2000–02 (dot-com) | **spring 2006** | 2008–09 (GFC) | 2010–15 |
|---|---|---|---|---|---|
| 20 | 21.6% | 9.4% | **21.8%** | 9.1% | 9.9% |
| 25 | 19.2% | 6.7% | 18.9% | 9.3% | 10.2% |
| 30 | 19.9% | 4.3% | 18.8% | 9.5% | 10.1% |
| 35 | 19.7% | 5.0% | 16.2% | 10.1% | 10.4% |
| 45 | 19.4% | 6.5% | 15.1% | 10.0% | 11.1% |
| 50 | 18.7% | 6.6% | 14.8% | 9.7% | 10.7% |
| 70 | 18.0% | 5.1% | 12.9% | 8.2% | 10.6% |

Every width's whole-window worst fall is dated **1998-06-30 → 1998-08-31** on both stores, with
exactly one exception: **20 names on the check store, dated 2006-03-31 → 2006-07-31**. That single
episode is what puts the roster's own book outside the owner's 25% bar.

Over that 2006 window the benchmark went 3.71 → 3.62: the market **dipped about 2% and made a new
high by September**. The SPY 200-day gate never fired and was right not to. The 2006 column is the
only strongly width-sensitive one — 8.9 points across 20→70, against 3.6 in 1998 and none at all
in the crisis years.

So the two defences do different jobs, and this is the first measurement that separates them:

- **The 200-day gate handles market falls, and it works.** The dot-com collapse and the GFC are
  this book's two *mildest* episodes (4–9% and 8–10%).
- **1998 is the floor.** Too fast for a 200-day average, and nearly width-insensitive. No width
  takes this book's worst fall much below 18%.
- **Width handles the single-holding blowup, and spring 2006 is the only one in twenty years.**

## The recommendation, and the pre-registered rule it departs from

M0152 fixed this rule before the run: *the narrowest rung whose check-store fall is ≤ 23.0% (the
owner's 25% bar less a 2-point cushion) whose check-store return is within 1.0 pt/yr of the
20-name book's.* **That rule answers 25 names.**

**The recorded recommendation is 35**, and the departure is deliberate and stated: the rule
assumes width *costs* return, so it buys the least width that reaches safety. Between 25 and 35
width costs nothing, and 35 dominates 25 on every axis — check fall 20.1% vs 22.0%, dev fall 19.6%
vs 20.1%, check return +12.1% vs +11.9%, dev return equal to within 0.06 pt. 35 is also the
check-store MAR peak and ties for the dev-store peak. Following the rule's letter here would mean
obeying a premise the data falsified.

**Cost of moving the roster from 20 to 35:** nothing on the check store (+12.1% vs +12.0% a year,
five points gentler fall); **0.6 pt/yr on the dev store** (13.7% → 13.1%). Past 35 the trade-off
is real again: 45 gives up 1.4 pt/yr for nothing and 70 gives up 2.8.

## Limits

- **The width effect rests on one episode.** Spring 2006 is essentially the whole of it. One
  episode in twenty years is thin, and M0152's verdict calls the recommendation a well-founded
  leaning rather than a proven optimum. What makes it more than a coin flip is that the episode is
  the *ordinary* kind — a single-company failure in a rising market — not a crisis that may not
  repeat.
- **Month-end granularity.** The era columns are read off month-end values, so each is a floor on
  the daily figure. The dates, which are the point, are unaffected.
- **The check store is a cross-check, not truth** (`EODHD_SURVIVORSHIP_MARKET_PLAN.md` D1). It
  adds most of the members the dev store cannot price and not all; real collapses were kept and
  data errors cleaned, which is a judgement call.
- **This is a width finding, not a verdict on the picking rule.** The line runs through M0007,
  which is test-failed; promotion is refused on kin and was never sought. `lab kin M0152` reads
  0.96 / 0.95 / 0.94 against the 0.85 bar at 25 / 30 / 45 names: a wider version of this book is
  still the same book.
- **The roster's other book (M0002-REL-85) has no survivorship row at all** and has never been
  read this way. Queued as M0156.

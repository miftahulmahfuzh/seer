# The single-name brake, measured against the width curve (2026-10-14)

*Report only: no trial was recorded by the measurements in this file, and the lab's test-window
looks did not move (4 before, 4 after). Produced by M0155. The grid is
`single-name-brake-eras-2026-10-14.csv`. The six brake arms are recorded dev trials #485–#490;
the seven widths are quoted candidates re-measured here, not re-recorded. All six arms reproduced
their recorded dev trials.*

## Why this file sits beside `grid.csv` rather than inside it

`survivorship_record.GRID_PATH` points hard gate D16 at `grid.csv` exactly. Appending to it would
change which promotions the gate refuses as a side effect of a research run, so new measurements
land as their own dated files. `grid.csv` is untouched by this work.

## The question

M0152 dated the roster's damage. On the price history that keeps the companies which went bankrupt
or were bought, the twenty-name book's worst fall in twenty years is **spring 2006 — 21.8%
month-end, 25.1% daily** — a stretch in which the market index dipped about 2% and made a new high
by September. The 200-day market rule never fired and was right not to. 2006 is the only stretch in
the window where holding more names helps much.

Width is one answer and M0152 priced it. This asked whether a cheaper and more direct one exists:
let go of a holding that has fallen hard **relative to the index** while the market itself is fine.

## The answer: the brake does not touch the fall

Worst fall inside each stretch, de-funded, month-end granularity. The honest price history:

| | names | 1998 | 2000–02 | **spring 2006** | 2008–09 | 2010–15 | daily fall | %/yr | trades |
|---|---|---|---|---|---|---|---|---|---|
| **the book today** | 20 | 21.2% | 9.5% | **21.8%** | 9.1% | 9.9% | 25.1% | +11.98 | 1640 |
| Z2 — let it go | 20 | 21.2% | 9.5% | **21.8%** | 9.1% | 9.9% | 25.1% | +12.01 | 1640 |
| Z2-FILL — swap it out | 20 | 21.2% | 9.5% | **21.8%** | 9.1% | 9.9% | 25.1% | +11.96 | 1644 |
| Z15-FILL — more sensitive | 20 | 20.7% | 9.4% | **21.8%** | 9.1% | 9.9% | 25.1% | +12.29 | 1653 |
| Z25-FILL — more patient | 20 | 21.2% | 9.5% | **21.8%** | 9.1% | 9.9% | 25.1% | +11.97 | 1642 |
| Z2-HALF — half position | 20 | 21.2% | 9.5% | **21.8%** | 9.1% | 9.9% | 25.1% | +11.99 | 1640 |
| Z2-FILL-UP — market rising | 20 | 21.2% | 9.5% | **21.8%** | 9.1% | 9.9% | 25.1% | +11.93 | 1639 |
| *holding 35 instead* | *35* | *19.3%* | *5.0%* | ***16.2%*** | *10.1%* | *10.4%* | *20.1%* | *+12.11* | *2671* |

**Every arm's 2006 fall is 21.83%, identical to the unbraked book's to four decimal places.** Five
of the six are identical on every era column on both histories. The brake changes nothing it was
built to change. Holding thirty-five names, in the last row, takes 5.6 points off the same episode.

## Why — and this is the finding worth keeping

The brake is not too timid. It fires constantly: on **135 of 175 monthly decisions (77%)** it named
at least one name, **820 names** over twenty years.

Of those 820, the book actually held **11**.

In spring 2006 — the episode this method exists for — the brake named 36 names across ten monthly
decisions, and **held none of them**.

The reason is structural, not a tuning accident. The book ranks on twelve months of residual
momentum and buys the top twenty. The brake looks for a name two standard deviations behind the
index over the last quarter. **A name that has fallen that far is, by construction, already out of
the top twenty.** The two screens select nearly disjoint sets: the brake spends its life reading
names the book does not own and will not buy. The momentum screen has already done the letting-go,
earlier and more cheaply, and the brake arrives to sell what was never bought.

That generalises beyond this method id: **a per-holding relative-shortfall brake mounted on a
momentum book is near-inert by construction**, and any future variant of this shape should expect
the same result unless the host ranks on something other than past return.

## Against the pre-registered decision rule

The rule was fixed in the hypothesis before the run and the result does not get to choose it.

| test | threshold | result |
|---|---|---|
| (b) the 2006 episode shrinks by 4 points | ≤ 17.8% | **failed** — 21.83%, unchanged, every arm |
| (b) without costing a point a year | ≥ 10.98%/yr | passed — 11.93–12.29% |
| (c) is it width in disguise? | inside M0152's line | **no — it is not width at all**; it does not move |
| (d) exposure, not selection? | Z2 vs Z2-FILL | neither moves; the question does not arise |
| (e) overfitted to one spring? | other eras | no — nothing moved, in either direction |
| (f) reversal bet with the sign wrong? | 1–3 pts/yr drag | no — returns are flat to slightly up |
| (g) churn | > 2,300 trades | no — 1,639–1,653 against 1,640 |
| (h) threshold curve monotone and shallow | — | flat: 1.5, 2.0 and 2.5 give the same 2006 fall |

The brake neither closes the hole nor costs anything. It is a **null result**, and the honest
answer to the question that prompted it remains **thirty-five names**.

## Limits

- **One convention, stated.** M0152's committed month-end era columns were produced by a scratchpad
  script that was not kept. This file re-measures all seven widths under its own single convention
  rather than quoting numbers it cannot reproduce, so the arms and the widths here are computed
  identically and the comparison above is exact. The control reproduces its *recorded trial* — the
  de-funded daily fall (25.05% / 20.65%), the funded return and the trade count — to six digits,
  which is the check that matters. Against M0152's published figures the re-measured 2006 column
  agrees to within 0.0003 (21.83/18.87/18.79/16.20/15.07/14.81/12.95 at 20/25/30/35/45/50/70); the
  whole-window month-end figure differs by up to 0.0035, and that difference is the convention, not
  the measurement.
- **The clock is a ceiling, accepted before the run.** This tape re-reads the book once a month.
  A name can collapse and be gone inside one month. A faster preset would need a rebalance band
  the lab has measured as barely firing, so no result on it would line up with the width curve. A
  feature wish is journalled.
- **The check history is a cross-check, not truth.** It adds most of the members the dev history
  cannot price and not all of them, and real collapses were kept while data errors were cleaned.
- **Promotion was never available on this line** and was not sought: the book it is built on has
  already failed out of sample, so the gate refuses the family whatever it scores.

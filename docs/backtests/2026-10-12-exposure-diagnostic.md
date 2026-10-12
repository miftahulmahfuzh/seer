# What the five live books actually picked

**Measured:** 2026-10-12 · **Window:** 1996-01-03 → 2015-10-16 (the lab's development window)
**Research store:** `77c37d553508` (dev, unmarked) · **Prices:** `5451195fd552`
**Grid:** [`2026-10-12-exposure-diagnostic-grid.csv`](2026-10-12-exposure-diagnostic-grid.csv) — the same rows at full precision
**Command:** `lab exposure M0024 M0028 M0030 M0044 M0053 --store engine/.research`

## The short answer

The four books that are not the market-core one do have a picking edge of their own, and this is
not what the dividend family looked like. Three of them park no money in the market at all — every
name they hold is a name they chose — and their own picks, given the whole book with the brakes
switched off, beat the market over the whole window by about four to eight points a year. The
market-core book is the only one that parks, and there the parked money turns out to be the drag
rather than the edge: its own sleeve of picks, at full size, beats the market by seven and a half
points a year, against four and a half for the book as it actually ran. So the lab's live space is
not empty. But two things should temper that. Almost every one of these books stops buying when the
market falls below its long-term average, and that one shared rule — the same rule, on the same
index, on the same dates — is what produced a thirty-five point lead in 2008 for every single one
of them; it is one trade shared five ways, not five separate discoveries. And over the most recent
stretch, from 2009 to the end of the window, the best version of every one of the five is behind
the market, and with the brakes off only two of the five climb back above it, by under three points
a year. The
live space is real but thinner than five separate books make it look, and none of it has yet shown
it can beat the market in the most recent third of the record.

## Why this was measured

Every number the lab records about a book is a number about the whole book: what it returned, how
far it fell, how much of the time it was invested. None of them separates the two different things
a book is made of — the names it **picked**, and the money it **parked** in the market or left as
cash. A book whose picks have no edge can still post a good whole-book number when most of its
money is market beta, and until now the lab could not see the difference.

That is exactly what happened to the dividend family: thirty-five variations over three batches,
and when a control arm finally stripped the parked market holding out, the picks lost to the
market in every era — behind 4.4 points a year through 2002, ahead about a point to 2008, behind
5.7 points from 2009. The family is closed. This measurement asks the same question of everything
still alive.

## How it was measured

Each book was re-run four ways, on the same window, at the same starting money and the same
monthly top-up it was originally recorded with. Only one thing changed between the four: what the
book was allowed to hold.

- **As recorded** — the book exactly as the lab holds it. The reference.
- **Its own picks only** — the parked market holding dropped, the picks kept at the size the book
  gave them, the rest left in cash. This is the share of the money that was ever in the book's own
  names.
- **Its own picks at full size** — the same picks, rescaled to fill the whole book, with the
  brakes off. This is the fair test of the picking itself.
- **The parked money only** — just the market holding, filling the book. What the spare money
  earned on its own.

The market comparison receives the same deposits on the same days, so "ahead" and "behind" below
compare two accounts holding the same money. The eras are the same split that exposed the problem
in the dividend family: 1996–2002, 2003–2008, 2008 on its own, and 2009 to the end of the
development window.

All twenty-three recorded versions reproduced their recorded total return exactly, digit for digit,
on this store. Even so, every comparison below is between the four arms of one run, never against a
number the lab recorded earlier.

## What it could not see

A safety rule that works by holding **nothing at all** cannot be undone by this measurement. When a
book's rule says "not today", it hands back no names, and no amount of re-weighting can invent the
basket it would have bought if the rule had been off. So instead of faking that, the measurement
reports **how often each book held nothing** — and that number is in the grid below.

That number deserves a closer look than it first invites, because it is nearly the same for every
book here: 28.3% of decision days. That is not a coincidence and it is not a bug. Four of the five
books sit behind the *same* gate — the market's own 200-day average — read on the same dates, so
they go to cash together. Those four share the figure exactly: 67 of 237 monthly decisions. The
fifth book decides far more often than monthly and so has its own denominator, 328 of 1157, which
happens to round to almost the same place. And the two versions in the grid that drop the gate
(`M0024-SAME-N20-NOTREND` and `M0030-C50A`) correctly report 0.0%, which is what shows the number
is measuring the gate rather than an artefact of the measurement.

This matters for reading everything below. The gate is worth a great deal in one year and costs
afterwards, and the lab has a recorded control that prices it directly: the seasonality book with
the gate removed. With the gate it leads the market by 2.7 points a year over the whole window;
without it, 1.0. But the gated version's lead in 2008 is +34.8 and the ungated version's is −2.1 —
and after 2009 the ordering flips, the gated version trailing by 5.4 points a year while the
ungated one *leads* by 1.5. Nearly all of the gate's whole-window value is a single year, and it
has been a drag ever since.

## Book by book

### The seasonality book — buys what did best in this calendar month last year

56.0% of its money was in its own names. It parks nothing: the rest of the book was cash, and most
of that cash is the shared market gate firing, not unfilled slots. Switching the brakes off lifts
its whole-window lead from +2.6 to +4.4 points a year and pulls 2009–2015 from −4.7 up to −1.7 —
better, but still behind. Its picks beat the market in three of the four eras they can be judged
on, and the one they lose is the most recent.

Headline version `M0024-SAME-N20-BLEND-RM` — the best recorded eligible version by MAR, or the best by MAR where none is eligible:

| | as recorded | its own picks only | its own picks at full size |
|---|---:|---:|---:|
| share of the book invested | 56.0% | 56.0% | 63.4% |
| share of days it held nothing | — | 28.3% | 28.3% |
| names held, on average | — | 25.6 | 25.6 |
| return a year | 10.5% | 10.5% | 12.3% |
| the market, same money | 7.9% | 7.9% | 7.9% |
| worst fall | 15.1% | 15.1% | 18.0% |
| profit factor | 1.65 | 1.65 | 1.69 |

| lead over the market, points a year | whole window | 1996–2002 | 2003–2008 | 2008 | 2009–2015 |
|---|---:|---:|---:|---:|---:|
| as recorded | +2.6 | +6.1 | +4.7 | +34.8 | -4.7 |
| its own picks only | +2.6 | +6.1 | +4.7 | +34.8 | -4.7 |
| its own picks at full size | +4.4 | +7.6 | +5.5 | +34.8 | -1.7 |

### The bounce book — buys last month's biggest fallers among calm, uptrending stocks

69.1% of its money was in its own names, the highest of the five, and it parks nothing. It is also
the book the brakes barely touch: switching them off moves its whole-window lead from +3.5 to +3.6
and leaves 2009–2015 unchanged at −3.3. That is the cleanest reading in the grid — what this book
earns is what its picking earns, with almost nothing to subtract. It is also the only one of the
four whose picks could not be improved by releasing anything, and it is behind the market after
2009 on every arm.

Headline version `M0028-BLEND-RM` — the best recorded eligible version by MAR, or the best by MAR where none is eligible:

| | as recorded | its own picks only | its own picks at full size |
|---|---:|---:|---:|
| share of the book invested | 69.1% | 69.1% | 69.2% |
| share of days it held nothing | — | 28.3% | 28.3% |
| names held, on average | — | 27.4 | 27.4 |
| return a year | 10.6% | 10.6% | 10.8% |
| the market, same money | 7.2% | 7.2% | 7.2% |
| worst fall | 17.2% | 17.2% | 17.2% |
| profit factor | 1.77 | 1.77 | 1.77 |

| lead over the market, points a year | whole window | 1996–2002 | 2003–2008 | 2008 | 2009–2015 |
|---|---:|---:|---:|---:|---:|
| as recorded | +3.5 | +5.1 | +6.1 | +34.8 | -3.3 |
| its own picks only | +3.5 | +5.1 | +6.1 | +34.8 | -3.3 |
| its own picks at full size | +3.6 | +5.7 | +6.1 | +34.8 | -3.3 |

### The market-core book — holds the market itself and adds a momentum sleeve on top

This book holds the market on purpose, so a large parked share is the design and not the finding.
The finding is what the momentum sleeve did on its own, and it is the most interesting result here.
Only 35.6% of the book was ever in its own picks. Those picks, left at the size the book gave them
with the rest in cash, barely match the market (−0.1 points a year). But given the whole book with
the brakes off they lead by +7.5 points a year — better than the book as recorded (+4.7) — and at
+2.7 points a year after 2009 they are the strongest reading anywhere in the grid on that era. The
parked market money, priced on its own, leads by only +1.8 and trails by 5.8 after 2009.

So this book is the inverse of the dividend family. There, the parked market money was carrying a
set of picks that had no edge. Here, the picks have the edge and the parked market money is
diluting them.

Headline version `M0030-C50T` — the best recorded eligible version by MAR, or the best by MAR where none is eligible:

| | as recorded | its own picks only | its own picks at full size | the parked money only |
|---|---:|---:|---:|---:|
| share of the book invested | 70.6% | 35.6% | 70.0% | 71.1% |
| share of days it held nothing | — | 28.3% | 28.3% | 28.3% |
| names held, on average | — | 14.3 | 14.3 | 0.7 |
| return a year | 12.7% | 7.8% | 15.4% | 9.7% |
| the market, same money | 7.9% | 7.9% | 7.9% | 7.9% |
| worst fall | 18.6% | 10.6% | 20.4% | 19.0% |
| profit factor | 2.79 | 2.17 | 2.11 | inf |

| lead over the market, points a year | whole window | 1996–2002 | 2003–2008 | 2008 | 2009–2015 |
|---|---:|---:|---:|---:|---:|
| as recorded | +4.7 | +7.1 | +7.2 | +34.8 | -1.7 |
| its own picks only | -0.1 | +1.8 | +3.0 | +34.8 | -7.0 |
| its own picks at full size | +7.5 | +9.7 | +8.7 | +34.8 | +2.7 |
| the parked money only | +1.8 | +3.8 | +5.7 | +34.8 | -5.8 |

### The quiet-blend book — the low-turnover blend under a volatility brake

This book parks nothing, so "its own picks at full size" is simply the same picks with the
volatility brake switched off. The brake is expensive: it holds the book at 56.3% invested instead
of 69.7%, and costs 3.3 points a year of lead (+1.5 against +4.8) to save 3.1 points of worst fall
(19.2% against 22.3%). The lab already has the control that confirms this — the recorded no-brake
version — and the brakes-off arm of every braked version lands on it exactly, which is a useful
check that the re-weighting is doing what it claims. Even with the brake off, this book is behind
the market by 4.8 points a year after 2009, the worst of the five on that era.

Headline version `M0044-TV14-N21` — the best recorded eligible version by MAR, or the best by MAR where none is eligible:

| | as recorded | its own picks only | its own picks at full size |
|---|---:|---:|---:|
| share of the book invested | 56.3% | 56.3% | 69.7% |
| share of days it held nothing | — | 28.3% | 28.3% |
| names held, on average | — | 14.3 | 14.3 |
| return a year | 8.7% | 8.7% | 12.0% |
| the market, same money | 7.2% | 7.2% | 7.2% |
| worst fall | 19.2% | 19.2% | 22.3% |
| profit factor | 2.07 | 2.07 | 2.17 |

| lead over the market, points a year | whole window | 1996–2002 | 2003–2008 | 2008 | 2009–2015 |
|---|---:|---:|---:|---:|---:|
| as recorded | +1.5 | +4.9 | +5.8 | +34.8 | -7.1 |
| its own picks only | +1.5 | +4.9 | +5.8 | +34.8 | -7.1 |
| its own picks at full size | +4.8 | +12.0 | +8.0 | +34.8 | -4.8 |

### The overnight book — momentum winners whose gain came overnight, under a weekly brake

This book parks nothing either, so again the full-size arm is the same picks with the weekly
volatility brake off. It has the strongest picking of the four non-core books: brakes off, +7.2
points a year over the whole window against +3.0 as recorded, and it is one of only two arms
anywhere in the grid that is above the market after 2009 (+0.5). The brake costs 4.2 points a year
of lead to save 4.9 points of worst fall (17.5% against 22.4%) — the same trade the quiet-blend
book makes, at roughly the same price.

Headline version `M0053-RESON20-TV16` — the best recorded eligible version by MAR, or the best by MAR where none is eligible:

| | as recorded | its own picks only | its own picks at full size |
|---|---:|---:|---:|
| share of the book invested | 59.0% | 59.0% | 69.6% |
| share of days it held nothing | — | 28.3% | 28.3% |
| names held, on average | — | 14.3 | 14.3 |
| return a year | 10.2% | 10.2% | 14.4% |
| the market, same money | 7.2% | 7.2% | 7.2% |
| worst fall | 17.5% | 17.5% | 22.4% |
| profit factor | 1.83 | 1.83 | 2.02 |

| lead over the market, points a year | whole window | 1996–2002 | 2003–2008 | 2008 | 2009–2015 |
|---|---:|---:|---:|---:|---:|
| as recorded | +3.0 | +5.4 | +7.0 | +34.8 | -4.9 |
| its own picks only | +3.0 | +5.4 | +7.0 | +34.8 | -4.9 |
| its own picks at full size | +7.2 | +10.9 | +8.8 | +34.8 | +0.5 |

## Every version tested

Every recorded development version of all five books, each run four ways. The committed grid beside
this file — [`2026-10-12-exposure-diagnostic-grid.csv`](2026-10-12-exposure-diagnostic-grid.csv) —
carries the same rows at full precision, with the per-era returns and the market's own per-era
returns alongside. "Invested" is the mean share of the book with money at work; for the *own picks
only* arm that is the share that was ever in the book's own names. The four era columns are the
lead over deposit-matched SPY in points a year.

| version | arm | invested | names | held nothing | return/yr | market/yr | worst fall | whole | 1996–2002 | 2003–2008 | 2008 | 2009–2015 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **M0024-SAME-N20**<br/>twenty names, ranked on the same calendar month last year | as recorded | 65.2% | — | — | 10.6% | 7.9% | 22.3% | +2.7 | +7.9 | +3.7 | +34.8 | -5.4 |
|  | own picks only | 65.2% | 14.3 | 28.3% | 10.6% | 7.9% | 22.3% | +2.7 | +7.9 | +3.7 | +34.8 | -5.4 |
|  | own picks at full size | 65.2% | 14.3 | 28.3% | 10.6% | 7.9% | 22.3% | +2.7 | +7.9 | +3.7 | +34.8 | -5.4 |
| **M0024-NET-N20**<br/>twenty names, same-month rank with the market move stripped out | as recorded | 65.1% | — | — | 9.6% | 7.9% | 23.9% | +1.7 | +7.0 | +2.5 | +34.8 | -6.4 |
|  | own picks only | 65.1% | 14.3 | 28.3% | 9.6% | 7.9% | 23.9% | +1.7 | +7.0 | +2.5 | +34.8 | -6.4 |
|  | own picks at full size | 65.1% | 14.3 | 28.3% | 9.6% | 7.9% | 23.9% | +1.7 | +7.0 | +2.5 | +34.8 | -6.4 |
| **M0024-SAME-N40**<br/>forty names, same-month rank | as recorded | 60.3% | — | — | 9.1% | 7.9% | 19.3% | +1.1 | +5.2 | +2.9 | +34.8 | -6.5 |
|  | own picks only | 60.3% | 28.7 | 28.3% | 9.1% | 7.9% | 19.3% | +1.1 | +5.2 | +2.9 | +34.8 | -6.5 |
|  | own picks at full size | 60.3% | 28.7 | 28.3% | 9.1% | 7.9% | 19.3% | +1.1 | +5.2 | +2.9 | +34.8 | -6.5 |
| **M0024-SAME-N20-NOTREND**<br/>twenty names, same-month rank, market-trend gate removed | as recorded | 89.8% | — | — | 8.9% | 7.9% | 61.0% | +1.0 | +4.9 | -2.7 | -2.1 | +1.5 |
|  | own picks only | 89.8% | 20.0 | 0.0% | 8.9% | 7.9% | 61.0% | +1.0 | +4.9 | -2.7 | -2.1 | +1.5 |
|  | own picks at full size | 89.8% | 20.0 | 0.0% | 8.9% | 7.9% | 61.0% | +1.0 | +4.9 | -2.7 | -2.1 | +1.5 |
| **M0024-SAME-N20-RANKSUM**<br/>twenty names, same-month rank summed across years | as recorded | 65.8% | — | — | 12.0% | 7.9% | 18.4% | +4.1 | +9.2 | +6.1 | +34.8 | -4.8 |
|  | own picks only | 65.8% | 14.3 | 28.3% | 12.0% | 7.9% | 18.4% | +4.1 | +9.2 | +6.1 | +34.8 | -4.8 |
|  | own picks at full size | 65.8% | 14.3 | 28.3% | 12.0% | 7.9% | 18.4% | +4.1 | +9.2 | +6.1 | +34.8 | -4.8 |
| **M0024-SAME-N20-BLEND-RM**<br/>the same-month book blended with the momentum book | as recorded | 56.0% | — | — | 10.5% | 7.9% | 15.1% | +2.6 | +6.1 | +4.7 | +34.8 | -4.7 |
|  | own picks only | 56.0% | 25.6 | 28.3% | 10.5% | 7.9% | 15.1% | +2.6 | +6.1 | +4.7 | +34.8 | -4.7 |
|  | own picks at full size | 63.4% | 25.6 | 28.3% | 12.3% | 7.9% | 18.0% | +4.4 | +7.6 | +5.5 | +34.8 | -1.7 |
| **M0028-CALM-RESID**<br/>biggest fallers among calm stocks, market move stripped out | as recorded | 69.0% | — | — | 7.5% | 7.2% | 27.2% | +0.3 | +2.0 | +4.6 | +34.8 | -7.8 |
|  | own picks only | 69.0% | 14.3 | 28.3% | 7.5% | 7.2% | 27.2% | +0.3 | +2.0 | +4.6 | +34.8 | -7.8 |
|  | own picks at full size | 69.2% | 14.3 | 28.3% | 7.6% | 7.2% | 27.2% | +0.5 | +2.9 | +4.7 | +34.8 | -7.8 |
| **M0028-CALM-RAW**<br/>biggest fallers among calm stocks, raw fall | as recorded | 69.0% | — | — | 7.6% | 7.2% | 30.0% | +0.4 | +1.9 | +3.8 | +34.8 | -6.8 |
|  | own picks only | 69.0% | 14.3 | 28.3% | 7.6% | 7.2% | 30.0% | +0.4 | +1.9 | +3.8 | +34.8 | -6.8 |
|  | own picks at full size | 69.2% | 14.3 | 28.3% | 7.8% | 7.2% | 30.0% | +0.6 | +2.7 | +3.8 | +34.8 | -6.8 |
| **M0028-PLAIN-RESID**<br/>biggest fallers, no calm screen | as recorded | 68.6% | — | — | 3.5% | 7.2% | 35.5% | -3.7 | -0.1 | +0.8 | +34.8 | -11.4 |
|  | own picks only | 68.6% | 14.3 | 28.3% | 3.5% | 7.2% | 35.5% | -3.7 | -0.1 | +0.8 | +34.8 | -11.4 |
|  | own picks at full size | 68.6% | 14.3 | 28.3% | 3.5% | 7.2% | 35.5% | -3.7 | -0.1 | +0.8 | +34.8 | -11.4 |
| **M0028-CALM-RESID-N10**<br/>ten names instead of twenty | as recorded | 69.5% | — | — | 7.4% | 7.2% | 23.0% | +0.2 | +5.5 | +3.7 | +34.8 | -8.5 |
|  | own picks only | 69.5% | 7.2 | 28.3% | 7.4% | 7.2% | 23.0% | +0.2 | +5.5 | +3.7 | +34.8 | -8.5 |
|  | own picks at full size | 69.5% | 7.2 | 28.3% | 7.4% | 7.2% | 23.0% | +0.2 | +5.5 | +3.7 | +34.8 | -8.5 |
| **M0028-BLEND-RM**<br/>the bounce book blended with the momentum book | as recorded | 69.1% | — | — | 10.6% | 7.2% | 17.2% | +3.5 | +5.1 | +6.1 | +34.8 | -3.3 |
|  | own picks only | 69.1% | 27.4 | 28.3% | 10.6% | 7.2% | 17.2% | +3.5 | +5.1 | +6.1 | +34.8 | -3.3 |
|  | own picks at full size | 69.2% | 27.4 | 28.3% | 10.8% | 7.2% | 17.2% | +3.6 | +5.7 | +6.1 | +34.8 | -3.3 |
| **M0030-C70T**<br/>70% market core under its 200-day gate, 30% momentum sleeve | as recorded | 70.9% | — | — | 11.5% | 7.9% | 18.8% | +3.6 | +5.9 | +6.6 | +34.8 | -3.4 |
|  | own picks only | 21.6% | 14.3 | 28.3% | 4.8% | 7.9% | 6.4% | -3.1 | -1.0 | +0.7 | +34.8 | -10.9 |
|  | own picks at full size | 70.0% | 14.3 | 28.3% | 15.4% | 7.9% | 20.4% | +7.5 | +9.7 | +8.7 | +34.8 | +2.7 |
|  | parked money only | 71.1% | 0.7 | 28.3% | 9.7% | 7.9% | 19.0% | +1.8 | +3.8 | +5.7 | +34.8 | -5.8 |
| **M0030-C50T**<br/>50% market core under its 200-day gate, 50% momentum sleeve | as recorded | 70.6% | — | — | 12.7% | 7.9% | 18.6% | +4.7 | +7.1 | +7.2 | +34.8 | -1.7 |
|  | own picks only | 35.6% | 14.3 | 28.3% | 7.8% | 7.9% | 10.6% | -0.1 | +1.8 | +3.0 | +34.8 | -7.0 |
|  | own picks at full size | 70.0% | 14.3 | 28.3% | 15.4% | 7.9% | 20.4% | +7.5 | +9.7 | +8.7 | +34.8 | +2.7 |
|  | parked money only | 71.1% | 0.7 | 28.3% | 9.7% | 7.9% | 19.0% | +1.8 | +3.8 | +5.7 | +34.8 | -5.8 |
| **M0030-C50A**<br/>50% market core held always, 50% momentum sleeve | as recorded | 84.6% | — | — | 11.9% | 7.9% | 34.0% | +4.0 | +5.4 | +4.4 | +16.0 | +1.4 |
|  | own picks only | 35.6% | 14.3 | 0.0% | 7.8% | 7.9% | 10.6% | -0.1 | +1.8 | +3.0 | +34.8 | -7.0 |
|  | own picks at full size | 70.0% | 14.3 | 0.0% | 15.4% | 7.9% | 20.4% | +7.5 | +9.7 | +8.7 | +34.8 | +2.7 |
|  | parked money only | 99.0% | 1.0 | 0.0% | 7.9% | 7.9% | 55.0% | -0.0 | +0.0 | +0.0 | -0.1 | +0.0 |
| **M0044-TV22-N21**<br/>volatility brake set loose (22) | as recorded | 66.7% | — | — | 11.1% | 7.2% | 22.0% | +3.9 | +9.0 | +8.0 | +34.8 | -5.2 |
|  | own picks only | 66.7% | 14.3 | 28.3% | 11.1% | 7.2% | 22.0% | +3.9 | +9.0 | +8.0 | +34.8 | -5.2 |
|  | own picks at full size | 69.7% | 14.3 | 28.3% | 12.0% | 7.2% | 22.3% | +4.8 | +12.0 | +8.0 | +34.8 | -4.8 |
| **M0044-TV18-N21**<br/>volatility brake set medium (18) | as recorded | 63.9% | — | — | 10.2% | 7.2% | 21.9% | +3.0 | +6.8 | +8.0 | +34.8 | -6.2 |
|  | own picks only | 63.9% | 14.3 | 28.3% | 10.2% | 7.2% | 21.9% | +3.0 | +6.8 | +8.0 | +34.8 | -6.2 |
|  | own picks at full size | 69.7% | 14.3 | 28.3% | 12.0% | 7.2% | 22.3% | +4.8 | +12.0 | +8.0 | +34.8 | -4.8 |
| **M0044-TV14-N21**<br/>volatility brake set tight (14) | as recorded | 56.3% | — | — | 8.7% | 7.2% | 19.2% | +1.5 | +4.9 | +5.8 | +34.8 | -7.1 |
|  | own picks only | 56.3% | 14.3 | 28.3% | 8.7% | 7.2% | 19.2% | +1.5 | +4.9 | +5.8 | +34.8 | -7.1 |
|  | own picks at full size | 69.7% | 14.3 | 28.3% | 12.0% | 7.2% | 22.3% | +4.8 | +12.0 | +8.0 | +34.8 | -4.8 |
| **M0044-NOBRAKE**<br/>the control: no volatility brake at all | as recorded | 69.7% | — | — | 12.0% | 7.2% | 22.3% | +4.8 | +12.0 | +8.0 | +34.8 | -4.8 |
|  | own picks only | 69.7% | 14.3 | 28.3% | 12.0% | 7.2% | 22.3% | +4.8 | +12.0 | +8.0 | +34.8 | -4.8 |
|  | own picks at full size | 69.7% | 14.3 | 28.3% | 12.0% | 7.2% | 22.3% | +4.8 | +12.0 | +8.0 | +34.8 | -4.8 |
| **M0053-TOTON20-TV14**<br/>twenty overnight winners, brake set tight (14) | as recorded | 52.0% | — | — | 9.3% | 7.2% | 16.3% | +2.1 | +4.8 | +4.5 | +34.8 | -4.7 |
|  | own picks only | 52.0% | 14.3 | 28.3% | 9.3% | 7.2% | 16.3% | +2.1 | +4.8 | +4.5 | +34.8 | -4.7 |
|  | own picks at full size | 69.8% | 14.3 | 28.3% | 14.9% | 7.2% | 22.8% | +7.7 | +14.2 | +8.2 | +34.8 | +0.8 |
| **M0053-TOTON20-TV16**<br/>twenty overnight winners, brake set medium (16) | as recorded | 56.8% | — | — | 10.5% | 7.2% | 18.8% | +3.3 | +6.3 | +5.8 | +34.8 | -3.6 |
|  | own picks only | 56.8% | 14.3 | 28.3% | 10.5% | 7.2% | 18.8% | +3.3 | +6.3 | +5.8 | +34.8 | -3.6 |
|  | own picks at full size | 69.8% | 14.3 | 28.3% | 14.9% | 7.2% | 22.8% | +7.7 | +14.2 | +8.2 | +34.8 | +0.8 |
| **M0053-TOTON20-TV18**<br/>twenty overnight winners, brake set loose (18) | as recorded | 60.2% | — | — | 11.1% | 7.2% | 21.0% | +3.9 | +7.6 | +6.2 | +34.8 | -3.0 |
|  | own picks only | 60.2% | 14.3 | 28.3% | 11.1% | 7.2% | 21.0% | +3.9 | +7.6 | +6.2 | +34.8 | -3.0 |
|  | own picks at full size | 69.8% | 14.3 | 28.3% | 14.9% | 7.2% | 22.8% | +7.7 | +14.2 | +8.2 | +34.8 | +0.8 |
| **M0053-TOTON30-TV16**<br/>thirty overnight winners, brake set medium (16) | as recorded | 59.6% | — | — | 10.6% | 7.2% | 19.0% | +3.5 | +6.5 | +6.5 | +34.8 | -3.8 |
|  | own picks only | 59.6% | 21.5 | 28.3% | 10.6% | 7.2% | 19.0% | +3.5 | +6.5 | +6.5 | +34.8 | -3.8 |
|  | own picks at full size | 69.6% | 21.5 | 28.3% | 13.5% | 7.2% | 23.6% | +6.4 | +11.5 | +8.3 | +34.8 | -0.9 |
| **M0053-RESON20-TV16**<br/>twenty overnight winners scored on residual return, brake medium (16) | as recorded | 59.0% | — | — | 10.2% | 7.2% | 17.5% | +3.0 | +5.4 | +7.0 | +34.8 | -4.9 |
|  | own picks only | 59.0% | 14.3 | 28.3% | 10.2% | 7.2% | 17.5% | +3.0 | +5.4 | +7.0 | +34.8 | -4.9 |
|  | own picks at full size | 69.6% | 14.3 | 28.3% | 14.4% | 7.2% | 22.4% | +7.2 | +10.9 | +8.8 | +34.8 | +0.5 |

## What this changes

The lab's live space is not empty, which is the good news and was not guaranteed — the handover
raised the possibility that all four non-core books were parked market money like the dividend
family, and they are not. Three of them park nothing whatsoever, and the one that parks is being
held back by what it parks rather than propped up by it. A next batch is therefore worth running.

But the three findings that should shape it are all cautions. First, the books are far less
independent than five method ids suggest: one shared market-trend gate produced a thirty-five point
lead in 2008 for all of them, and the lab's own recorded control shows that gate has been a drag
every year since 2009. Second, the volatility brakes are costing roughly a point of annual lead for
every point of drawdown they save, which is a trade worth making explicit rather than tuning
blindly — the grid now prices it for every braked version. Third, and most serious: in the most
recent third of the development window the best version of every one of the five books is behind
the market, and only two of them recover with their brakes removed, by under three points a year.
Whatever is chosen for the next
slate should be judged on 2009 onward first, because that is where every book here is weakest and
where the held-out years begin.

The diagnostic itself is now a standing command and takes method ids, so running it across the
closed families — the dividend family above all, to check it reproduces what that hand-built
control arm found — costs nothing in the lab's luck budget and is one command away.

## What was and was not recorded

Nothing in this measurement was recorded as a trial. The lab's count of development trials stayed
at 354 before and after, the test-window look budget stayed at 4, and no method's status changed.
The only rows written were six journal entries: one observation per book and one synthesis. Checked
independently of the command's own report, with a read-only connection, before and after.

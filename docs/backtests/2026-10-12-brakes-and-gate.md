# The brakes off, and the market switch off

**Measured:** 2026-10-12 · **Window:** 1996-01-03 → 2015-10-16 (the lab's development window)
**Research store:** `77c37d553508` (dev, unmarked) · **Prices:** `5451195fd552`
**Money:** 10,000,000 IDR to start, 5,000,000 IDR on the 25th of each month — the owner's real schedule
**Grid:** [`2026-10-12-brakes-and-gate-grid.csv`](2026-10-12-brakes-and-gate-grid.csv) — the same rows at full precision
**Roster-wide gate pricing:** [`2026-10-12-brakes-and-gate-gate-grid.csv`](2026-10-12-brakes-and-gate-gate-grid.csv)
**Commands:** `lab run --amend M0030`, `lab run --amend M0053`, `lab gate M0024 M0028 M0030 M0044 M0053`, `lab walkforward M0030 M0053`

## The short answer

Both books earned a great deal more with their safety mechanism removed, and both then fell further
than you allow. That was predicted in writing before either ran, and it held. The satellite book
alone earned **15.0% a year on your money against 7.2% for the same deposits in the market** — the
widest gap this lab has ever recorded — and is the first version of that book to pass the luck test,
at 0.96 against a 0.90 bar. It fails one condition and one only: a **20.6% worst fall against your
20% limit**. It misses by six tenths of a point.

That is not a disappointment, and it should not be read as one. Until today the only configuration
in this lab with a real recent edge existed as a column in a diagnostic report — an arrangement that
lived in memory for the length of one run and that nothing could carry forward or ever test on the
held-out years. The lab now **holds** it, pre-registered and recorded, and what it holds is a
specific and useful fact: the best recent idea this lab has found exists only just above the line
you drew.

The second finding is the opposite of what we went looking for. The 200-day market switch was
supposed to be the drag. Priced across every recorded version that carries it, **it helped 22 of 22
over the whole window and 0 of 22 after 2009** — and every single version we actually ran with it
switched off was worse on return *and* on worst fall at the same time. The switch is not a drag to
remove. It is one enormous 2008 trade that four books share, and it has cost a little every year
since.

## Why this was measured

The exposure diagnostic found exactly two configurations anywhere in its grid with a positive edge
over the market in the most recent third of the window, and both were diagnostic columns rather than
anything the lab held. Nothing could walk them forward, test them on the held-out years, or ever act
on them.

And four of the five live books share one rule — stop buying when the market is below its long-term
average. That one rule produced an identical +34.8-point lead in 2008 for every one of them, which
is one trade shared four ways, not four discoveries. Since 2009 the lab's own control said it had
been a drag.

This measurement turns both findings into things the lab holds rather than things it inferred.

## What it cost, and why that is the headline

**Nothing.** That is the point of the mechanism built for this.

The luck hurdle counts *books*, not runs. Adding versions to a book the lab already has is free; a
brand-new book raises the bar for all 130 at once, retroactively. So these six versions were
recorded as **amendments** to the two books the lab already held, rather than as new books.

Measured on the committed database, before and after the six runs:

| | before | after |
|---|---|---|
| luck hurdle | **74** (methods policy) | **74** (methods policy) |
| distinct books with a dev trial | 74 | 74 |
| hurdle if M0030 adds 3 more | 74 | 74 |
| hurdle if M0053 adds 3 more | 74 | 74 |
| development trial *rows* | 354 | 360 |
| held-out-year looks spent | **4** | **4** |

The only line that moved is the row count, and it is a different number from the hurdle. Every one
of the six new trials carries `74` as the hurdle its luck score was judged against, recorded in the
row itself. Had these been minted as two new books instead, the bar would have risen to 76 for every
book in the lab.

The held-out years were never opened.

## How it was measured

A book the lab has already run can now gain a dated, written-down set of new versions, committed
before they run and recorded under the book's own name. The commit *is* the pre-registration: the
prediction is on the record before any result exists, and the runner refuses an uncommitted file.

Six versions, three on each book:

- **The satellite at full size** — the momentum picker alone, filling the book, with the parked
  market money taken out.
- **The same, with the market switch off**, and **the always-held-core version with the switch off
  on both halves** — what the switch is worth on this book.
- **The weekly brake off**, on each of the overnight book's two pools.
- **The overnight book with the market switch off instead**, brake left exactly where it is.

All six ran funded, at 10,000,000 IDR plus 5,000,000 on the 25th of each month, 237 deposits. The
satellite book pays the flat cost its earlier versions were measured at; the overnight book pays
Gotrade's real fees, as its earlier versions did. **The two books' numbers are therefore not directly
comparable with each other.**

### The funding caveat — read this before the tables

The satellite book's three earlier versions were **lump-sum runs of 20,000,000 IDR with no monthly
top-up**, recorded before the lab's runner was funded. They carry no funding row at all. The three
new ones are funded at 10,000,000 plus 5,000,000 a month.

So the new numbers **cannot be put in the same column** as the old ones, and the 20.4% worst fall the
diagnostic reported for this book was itself a lump-sum figure, because the diagnostic re-runs each
trial at its own recorded capital. Below, the satellite book's old and new versions are kept in
separate tables for that reason.

The overnight book's five earlier versions and its three new ones share the same money, the same
schedule and the same fees, and **are** directly comparable. Its tables are combined.

## What was predicted, before anything ran

Both pre-registrations predicted **every candidate ineligible on the worst-fall condition**, while
clearing beats-the-market, the gains-to-losses ratio and the trade count.

The satellite book's pre-registration went further and marked its own prediction as the weak one:
the 20.4% it rested on was an unfunded figure, the new run would be funded, and a 0.4-point margin
is well inside what that change alone can move. It said in advance that a reading of 19.6% would
**not** be a refutation and 21% would **not** be a confirmation of a sharp prediction. It named the
claim worth holding it to instead: whether the satellite alone keeps a wide lead over
deposit-matched market money when actually run rather than re-weighted.

The overnight book's prediction was sharp, because its figures were like-for-like: 22.4% to 22.8%
against a 20% limit.

## What happened

### The satellite book — new versions only (funded, 10,000,000 IDR + 237 deposits)

| version | what it is | your money | same deposits in SPY | worst fall | gains:losses | trades | luck (bar 0.90) | clears |
|---|---|---:|---:|---:|---:|---:|---:|---|
| `M0030-SAT100` | the picker alone, filling the book | **+15.0%/yr** | +7.2%/yr | **20.64%** | 2.11 | 1,607 | **0.956** | **no — worst fall only** |
| `M0030-SAT100-NOGATE` | the same, market switch off | +11.0%/yr | +7.2%/yr | 66.74% | 1.49 | 2,126 | 0.584 | no |
| `M0030-C50A-NOGATE` | always-held core, switch off both halves | +8.9%/yr | +7.2%/yr | 61.40% | 1.52 | 2,123 | 0.536 | no |

The satellite book's three *earlier* versions, for reference only — **unfunded, 20,000,000 IDR lump
sum, not comparable with the table above**: `M0030-C70T` 11.5%/yr at an 18.77% fall, `M0030-C50T`
12.7%/yr at 18.56%, `M0030-C50A` 11.9%/yr at 33.98%, all three against SPY's 7.9%/yr on the same
lump-sum basis.

**Against the prediction, both ways round.** The prediction got right: ineligible on worst fall, and
on that condition alone; beats-the-market, gains-to-losses and trade count all cleared. The
prediction got wrong — or rather, understated — two things. First, it did not predict the **luck
score would clear**, and 0.956 against a 0.90 bar is the first time any version of this book has
passed that test. Second, it treated the switch-off arms as a secondary question; they turned out to
be the clearest result in the whole measurement.

The drawdown landed at 20.64% against a predicted 20.4% — six hundredths of a point worse, squarely
inside the band the pre-registration said in advance would settle nothing. The claim it *did* stake
itself on held: the satellite alone keeps its lead when actually run, and widens it.

### The overnight book — all eight versions, funded alike and comparable

| version | what it is | your money | same deposits in SPY | worst fall | gains:losses | trades | luck | clears |
|---|---|---:|---:|---:|---:|---:|---:|---|
| `M0053-TOTON20-TV14` | brake on, tightest | +9.3%/yr | +7.2%/yr | 16.33% | 2.12 | 1,100 | 0.917 | **yes** |
| `M0053-TOTON20-TV16` | brake on | +10.5%/yr | +7.2%/yr | 18.78% | 2.16 | 1,100 | 0.931 | **yes** |
| `M0053-TOTON20-TV18` | brake on, loosest | +11.1%/yr | +7.2%/yr | 21.04% | 2.13 | 1,100 | 0.931 | no |
| `M0053-TOTON30-TV16` | brake on, wider book | +10.6%/yr | +7.2%/yr | 18.99% | 2.27 | 1,551 | 0.949 | **yes** |
| `M0053-RESON20-TV16` | brake on, residual pool | +10.2%/yr | +7.2%/yr | 17.53% | 1.83 | 1,500 | 0.934 | **yes** |
| `M0053-TOTON20-NOBRAKE` | **brake off** | **+14.9%/yr** | +7.2%/yr | **22.79%** | 2.37 | 1,100 | 0.928 | no — worst fall only |
| `M0053-RESON20-NOBRAKE` | **brake off**, residual pool | **+14.4%/yr** | +7.2%/yr | **22.41%** | 2.02 | 1,500 | 0.938 | no — worst fall only |
| `M0053-RESON20-TV16-NOGATE` | brake on, **switch off** | +8.7%/yr | +7.2%/yr | 37.12% | 1.55 | 1,984 | 0.689 | no |

**Against the prediction: it held to the decimal.** 22.8% and 22.4% were predicted; 22.79% and
22.41% were measured. Nothing in that was a surprise, and because these eight share the same money
and the same fees, the trade is clean to state:

> **The weekly brake costs about four and a half points a year and buys about four points of worst
> fall.** That is the whole of it. It is a price you can look at and judge.

The third version is the one worth pausing on. Leaving the brake alone and removing the **market
switch** instead made the book worse on both counts simultaneously — return fell to 8.7%, barely
ahead of the market, and the worst fall more than doubled to 37.1%. The brake and the switch are not
two flavours of the same caution. The brake is selling something that pays. The switch is buying
something worth having.

## The market switch, priced across the roster

Every recorded version of the five live books was re-run twice: as the lab recorded it, and with
SPY's 200-day switch removed and nothing else moved. **Twenty-two versions carry the switch.** Before
anything ran, the transform was checked against the six switched-off pairs the lab already holds and
reproduced all six.

| era | what the switch was worth, on average | how many of the 22 it helped |
|---|---:|---|
| whole window | **+2.1% a year** | **22 of 22** |
| 1996–2002 | +2.1% a year | 20 of 22 |
| 2003–2008 | +5.1% a year | 22 of 22 |
| **2008 alone** | **+31.0%** | **22 of 22** |
| **2009–2015** | **−3.2% a year** | **0 of 22** |

**The same question asked of the whole lab, later the same day** — all 228 versions that carry the
switch, not just the five live books' 22. The companion file
`2026-10-12-brakes-and-gate-gate-grid.csv` now holds that wider run rather than the 22-version one
the table above was built from:

| era | what the switch was worth, on average | how many of the 228 it helped |
|---|---:|---|
| whole window | **+1.3% a year** | **174 of 228** |
| 1996–2002 | +0.9% a year | 144 of 228 |
| 2003–2008 | +5.1% a year | 212 of 228 |
| **2008 alone** | **+32.9%** | **226 of 228** |
| **2009–2015** | **−4.4% a year** | **10 of 228** |

The shape survives the wider sample and sharpens in one place: across the five live books the switch
helped *every* version over the whole window, while across the whole lab it helps **three in four**.
The 2009–2015 collapse holds — 10 of 228 — and 2008 is still one shared trade, now visible in 226 of
228 books at once.

Per book, taking each one's steadiest recorded version:

| book | lead over SPY, switch on | switch off | 2009–2015 | 2008 | worst fall |
|---|---:|---:|---|---|---|
| seasonality (`M0024`) | +2.6%/yr | +2.6%/yr | −4.7% → −0.1% | +34.8% → +11.8% | 15.1% → 41.7% |
| calm-stock (`M0028`) | +3.5%/yr | +0.1%/yr | −3.3% → −1.4% | +34.8% → −5.5% | 17.2% → 57.0% |
| core-satellite (`M0030`) | +4.7%/yr | +2.3%/yr | −1.7% → **+2.8%** | +34.8% → −6.4% | 18.6% → 61.4% |
| braked momentum (`M0044`) | +1.5%/yr | +0.2%/yr | −7.1% → −5.7% | +34.8% → +19.2% | 19.2% → 34.1% |
| overnight (`M0053`) | +3.0%/yr | +1.5%/yr | −4.9% → −2.8% | +34.8% → +14.9% | 17.5% → 37.1% |

**The 2008 column is the one to read.** Every book shows the same +34.8% — not because each
discovered something, but because it is the same rule reading the same index on the same dates. It
is one trade that four books share.

And the unanimity cuts both ways. The switch helped every single version over the whole window, and
helped **none** of them after 2009. That is as clean a statement of "this stopped working" as this
lab can produce — but it is still *one* rule measured once, not twenty-two independent confirmations
of anything.

The practical conclusion is firm, and it is the opposite of the one we set out to test: **removing
the switch is not available as an improvement.** Every book gets a far worse worst fall for it, and
four of the five get less return as well.

### One of the lab's "controls" was never a control

The lab holds a recorded pair on `M0001` that has been read as a clean switch-on against
switch-off comparison. **It is not one.** The switched-off sibling also widens the book's own
volatility window from 63 sessions to 126, so the recorded pair moves two things at once and nothing
in it isolates the switch at all.

The probe excludes that pair from the controls it validates itself against, with that reason and its
date recorded beside it, and then measures the clean comparison `M0001` never had. This is one bad
control, not a bad method — the other five recorded pairs the probe reproduces exactly.

### What the gate probe could not price

Measured across the whole lab on 2026-10-12, **re-measured later the same day** once the defect
below was fixed: of **360** recorded development trial rows, **306** are still described by a method
file. Of those 306:

- **228** carry the switch and can have it cleanly removed;
- **72** carry no switch this probe can see;
- **6** carry it and *refuse* to run without it — `M0054-PARK-SPY`, `M0054-HALF-PARK`, `M0101-CTRL`,
  `M0101-BAND-3`, `M0101-BAND-5` and `M0101-FABER`. Each is a book built around the switch being on:
  there is no "same book without it" to measure, so none was guessed at.

That last point matters more than it looks. A number that resembles a switched-off result but is not
one is worse than no number, so the probe lists its refusals by name and reason instead of filling
the gap.

The remaining **54** recorded versions have no method file to read. All 54 are the pre-lab seed
import, whose ids are not book names at all. *(The first measurement, taken before the fix, read 300
live versions at 225/69/6 and put 60 in that last bucket, six of them this document's own new
trials. That was the defect, not a fact about the lab.)*

### Nineteen versions declare no switch and still sit in cash — and that is not a gap

The probe flags any version that declares no switch yet still holds nothing on a real share of its
decision days, on the principle that such a row must not be read as "ungated". Nineteen are flagged.
**None of them is a switch the probe missed.** Each book carries a different risk machine on purpose,
and in every case the switched-off comparison is either meaningless or already sitting in the lab
under its own name:

| book | what its brake really is | the switched-off comparison |
|---|---|---|
| `M0005` (6) | no market switch at all — its empty days are the fundamentals panel, which starts in 2009 | there is no switch to remove |
| `M0012` (3) | its own crash gate, read weekly rather than monthly; its params *assert* the inner book carries no switch, because this allocator **is** the gate | removing it leaves the raw-residual book bare, already recorded as `M0007-N20-RAW` |
| `M0084` (5) | the switch **is** the method — it holds SPY when the switch reads on and cash when it reads off, four readings priced against each other | `M0084-ALWAYS`, a recorded trial and the method's own control |
| `M0107` (2) | a per-stock 200-day exit, deliberately not the market-wide switch: holdings drop one at a time | `M0107-NONE`, a recorded trial and the method's own control |
| `M0109` (3) | a book drawdown brake — exposure falls as the book falls from its own high; no switch and no stop, by design | there is no switch to remove |

So refusing to transform these is the correct answer rather than a hole in the measurement. The
probe now records that reasoning next to each flag instead of reporting only that the brake is
somewhere it cannot reach.

## Does it survive out of sample

Walk-forward over four folds, 2003 to 2014, scoring each book on months it has never seen:

| book | folds won | stable | 2009–2015 edge |
|---|---|---|---:|
| core-satellite (`M0030`) | 2 of 4 | no | +2.6% |
| overnight (`M0053`) | **3 of 4** | **yes** | +0.5% |

The overnight book is the stronger of the two and the only one to win a majority. The promotion gate
was **not run**, nothing was promoted, and the fold geometry was left exactly as the gate defines it.

This cuts against the satellite book specifically. It has the widest edge and the best luck score of
anything measured today, and it wins only half its folds without stability — so its headline number
deserves more caution than its size invites.

## What this changes

Nothing to act on, and one thing to know.

The standing rule is that survivorship-free price history is worth buying only when a method clears
dev-eligible **and** a majority of walk-forward folds **and** shows a positive edge after 2009. Today
moved that needle in an awkward way: the third condition is now met by configurations that fail the
first, and the overnight book meets the second and third while failing the first. **No book meets all
three, so the answer on buying data is still no.** But the shape of the gap is now known, which it
was not yesterday: it is the drawdown limit, by a small margin, and nothing else.

Two questions this raises are yours to decide, not the lab's to settle:

1. **The satellite book misses your 20% limit by six tenths of a point**, while beating the market by
   nearly eight points a year and passing the luck test. No intermediate core split was tried, and
   none will be — picking the split that squeaks under 20% after seeing this result is tuning to a
   result, which the design forbids. If the limit itself is worth revisiting, that is a dated owner
   revision, not a lab decision.
2. **The weekly brake costs about four and a half points a year** to buy about four points of worst
   fall. That is now a measured price rather than an assumption. No intermediate brake setting was
   tried, for the same reason.

## What was and was not recorded

Recorded: six development trials under the two existing book names (`n` 359–364), each with its
funding, provenance and luck inputs; two amendment records; seven journal entries, five written by
the roster-wide pricing and two by hand; and two verdicts.

The luck hurdle read **74 before and 74 after**. The held-out-year look budget read **4 before and 4
after**.

Not done: no new book was created and no book id was spent; no earlier run's fingerprint changed —
all eight previously recorded versions of these two books still digest to exactly what the lab has on
file; no status moved, both books remain dev-eligible; no promotion was attempted and the promotion
gate was never overridden; and the held-out years were never opened.

### One defect found while running this

The roster-wide probe resolves a recorded version by looking only at a book's *original* list of
versions, not at its amendments. So it reported today's six new trials as "recorded, but no longer in
a method file", which is wrong — they are in the file, inside the amendment. The effect is cosmetic
here and does not touch a single number in this document: the six are each recorded trials in their
own right, and the three switch-off arms among them are reported above from those trials directly.
It does mean the six were not *also* priced by the probe's own switch-off transform. It was logged
for the owning change rather than patched from the run.

**Fixed later the same day.** Both of the probe's version readers now read a book's amendments as
well as its original list, the grid was re-measured across the whole lab, and a regression test
fails against the old reader. The six are priced like any other version now.

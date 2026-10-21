# Handover — 2026-10-21: re-read the back catalogue through `lab timing`

> ## CORRECTED 2026-10-21 09:14, by the session this handover commissioned (`024b2ac`)
>
> **Read this box before anything below it.** Three of this file's framings were wrong, and the
> measurements refuting them are in that commit. The sections are corrected in place, but the
> short version:
>
> 1. **The eight reversals need NO correction — that job is void.** All eight already carry
>    `beats SPY TR` in their `failed` column, because that condition reads the **funded,
>    deposit-matched** curve. The lab has judged on the owner's money since the beginning. The
>    de-funded "paper lead" is the NEWCOMER, introduced by `lab timing` this morning. I had it
>    backwards: I was using a new tool's headline to audit records that were already more honest
>    than it.
> 2. **The gate is NOT the front-loaded ingredient — the stock picking is.** Seven gate/no-gate
>    pairs, each book run twice with nothing different but the rule: **six of seven delivered
>    103-129% of their paper lead.** For a cash-stepping gate the payday is 2008, at 66.1% of
>    deposits, not 2000-2002 at 36%. Inside M0203 the split is explicit — picking alone delivers
>    **−78%** of its paper lead, the gate alone **+125%**.
> 3. **I cited the wrong entry.** The gate premium is **insight 463**, not 494 (494 is the resize
>    band). And my instruction to qualify its 3.6 pts/yr was backwards: that is a **2009-2015
>    rate**, by which point 100% of the owner's deposits have arrived, making it the most
>    money-faithful headline in the journal. The real asymmetry is sharper — **the gate's COST
>    sits on 100% of the money, its PAYOUT on 66%.** 463 stands unchanged; entry 522 records the
>    addition beside it.
>
> Two supersedes were written as a result: **515 → 521** (its M0267 numbers all kept; only the
> generalisation from one chassis to crash rules in general was wrong) and **397 → 520** (a
> genuinely wrong row — it judged M0201 against control arms retired three days later as
> arbitrary to within seven points a year, and one of its two margins had the OPPOSITE SIGN).
>
> Written by `sera-20261020-1417` after a two-day run. Nothing is half-finished: every session is
reaped, every worktree removed, the tree is clean and everything is pushed. This is what is open
and what the evidence says to do next.

## State

- Head `8705205`, branch `main`, tree clean, no worktrees, no child sessions.
- **Trials 1..891, contiguous. Test-window looks = 4, untouched across both days.** No promotion
  was attempted and none should be without re-reading this file.
- Journal: 511 documents from 519 entries (schema 8 versioning is live and working).
- Engine 6540 passed / 4 skipped (PG up). Web `tsc` clean, 725 tests pass.
- Content digest over insight rows 1-500: `04af46875bef3498f783a3154265b760cd2c4471d018a740d82e0113721673ed`.
  Recipe is in `docs/runbooks/journal-content-digest.md` — **use it, do not invent your own**.

## The finding that reframes everything else

**`lab timing --all`: 436 of 509 funded trials (85.7%) earned half their lead before half the
owner's money had arrived.** Median trial: half its lead by **33.9%** of deposits.

Half is the neutral point and the reasoning is clean: deposits are level, so the money-in line is
straight, and a lead earned at a steady rate per dollar held crosses halfway exactly there.
Everything under 50% means the twenty-year average is flattering the method.

**Front-loading is not a rare failure to watch for. It is the normal shape of this lab's entire
record, and until 2026-10-21 nobody had measured it.** (Insight 519.)

**But it belongs to the STOCK PICKING, not to the safety gate** — corrected the same day; see
section 3 and the box at the top. Insight 515, which generalised it to crash rules, is superseded
by 521.

The floor does not make the answer — re-counted at four lead thresholds, the median and the 50%
count hold (33.9/33.9/34.7/34.7% and 478/436/377/288). The tight tail does not (46/22/13/7), so
**quote the stable two and ignore the tail**.

## THE NEXT JOB — re-read the back catalogue, and name names

`lab timing` is report-only, journals nothing on any path, opens no store and spends no look. It
can be re-run freely. Use it.

### 1. ~~The eight reversals~~ — DONE, AND THERE WAS NOTHING TO CORRECT

**Resolved 2026-10-21. Do not re-run this.** All eight already carry `beats SPY TR` in their
`failed` column — that condition reads the funded deposit-matched curve, not the de-funded one.
Every verdict and every journal claim on those seven methods was checked against
`trial_funding.mwr`, claim by claim, and they all hold; several quote `mwr` exactly (M0203's
"+10.4% vs +7.2% at best" is `TF-N40`'s 10.404 against 7.188; M0222's "+6.3% against SPY's +7.2%"
is `TILT1`'s 6.318; M0201's "about 2.4 points" is 2.395 and 2.474). Insight 217 even names
`M0130-P20-GATE` directly, at 7.0 vs 7.2 "on the same deposits", and records it as a near miss.

**The lab's verdicts were written on the money column from the start.** Zero supersedes on this
ground.

**The real finding here, which is more interesting than the one I asked for:** the disagreement
between the two columns runs **both ways — 30 of 761**. Eight lead on prices and lose on money;
**twenty-two lose on prices and win on money.** And the one place the price column actually gates
a decision is the walk-forward fold majority (`walkforward.measure` de-funds before it slices,
`walkforward.py:135`). All 15 methods that ever won a majority were audited: every fold-picked
arm beat SPY on the owner's money by **+1.4 to +11.8 pts/yr**. Real in principle, never once
opened in practice — worth re-checking only if that test changes.

The original (wrong) framing, kept so the error is legible:

~~No threshold involved: two recorded columns and a subtraction.~~

| candidate | paper | delivered |
|---|---|---|
| `M0203-TF-N20-NOSW` | +0.59 | **−0.46** |
| `M0125-DV-C10` | +0.54 | **−0.28** |
| `M0080-EX-S200-T` | +0.54 | **−0.25** |
| `M0130-P20-GATE` | +0.87 | **−0.17** |
| `M0201-Y20-MV10-PLC2` | +0.85 | **−0.12** |
| `M0172-LO5-P100-N20-T` | +0.73 | **−0.10** |
| `M0222-TILT2-T` | +1.07 | **−0.05** |
| `M0201-Y20-MV10-PLC1` | +0.71 | **−0.04** |

Check each one's recorded verdict against this. **A verdict that reads as a positive result on a
trial that lost the owner money is a verdict that needs a superseding entry** — the journal
supports that now (`lab insight --supersedes`, or `lab link` for one already written).

### 2. The four methods with M0267's shape at the 25% bar

Named by the sweep's headline-arm pass: start from `M0054` (two arms, `-ALWAYS-IN` at 20.9% and
`-PARK-SPY` at 21.8%), `M0176-BIG` (21.8%), `M0110-DP20-UP` (21.8%), `M0201-Y20-MV10-PLC2`
(20.5%). Run `lab timing <trial> --against <control>` on each and read the era table.

### 3. The gate — CORRECTED. It is NOT the front-loaded ingredient; the stock picking is.

**My framing here was backwards and the measurement is unambiguous.** Seven gate/no-gate pairs
were run — each one book, run twice, nothing different but the rule. **Six of seven delivered
103-129% of their paper lead:** `M0030-SAT100` +3.10 paper → **+4.01 delivered** (129%),
`M0054-PARK-SPY` 127%, `M0203-TF-N20` 125%, `M0130-P20-GATE` 118%, `M0080-ANN-S200-T` 103%. Only
`M0222-TILT2-T` came in under, at 72%.

The reason is in the era table: **for a cash-stepping gate the payday is 2008, at 66.1% of
deposits** — not 2000-2002 at 36%. Inside M0203 the decomposition is explicit: the **picking**
alone (`NOSW` vs SPY) delivers **−78%** of its paper lead; the **gate** alone delivers **+125%**.

So the 85.7% front-loading finding stands, but **it belongs to the stock picking, not to the
safety rule.** M0267's 21% is a property of its chassis: it steps sideways into another share
fund, so 2008 could not separate the two arms and only the early crash could.

- **Insight 515 is superseded by 521** on exactly that sentence. All its M0267 numbers are kept;
  only the generalisation from one chassis to crash rules in general was wrong.
- **Insight 516 STANDS and was deliberately not superseded.** The sticky-imitator study (20,000
  uninformed switches at the gate's own transition rates — arithmetic, no trial spent) put the
  real gate at the **38th percentile of its own imitators** over 2009-2015, +3.47 against the
  average placebo's +3.87. Nothing measured since contradicts it, and it was never run on a stock
  book — so superseding it would be disagreeing with its reach, not correcting a fact. **That
  distinction is the right one and should be kept.**
- **Insight 463** (NOT 494 — 494 is the resize band) is the 824-trial gate-premium row, and its
  3.6 pts/yr **should not be qualified.** It is a 2009-2015 rate, and 100% of the owner's
  deposits have arrived by then, so it is the most money-faithful headline in the journal. 463
  stands unchanged; entry **522** records the addition beside it.

**The asymmetry, stated correctly:** the gate's **cost** sits on 100% of the money; its **payout**
sits on 66%.

## Decided, do not re-litigate

- **A third permitted fund: NO.** Measured 2026-10-21 (insight 518, full study at
  `docs/plans/2026-10-21-third-fund-study.md`). The store already holds 15 ETFs in all four
  copies — this was never a data question. The spread really is ~1.7x wider through TLT/GLD, and
  **it does not matter**: post-2009 the gate's timing contribution is ~0 through every instrument
  on the menu (GLD +0.77, IEF +0.11, SHY −0.07, TLT −0.20, cash −0.05). Wired to cash the gate
  costs −2.90 pts/yr in that era; wired to the best third fund, −2.27. A third fund repairs a
  fifth of the hole and still loses to doing nothing. **Do not re-propose this on "the spread is
  narrow" — that half is true and it is not the binding half.**
  If the owner ever wants the option anyway: **TLT**, best on every axis and the only strong
  candidate colliding with no frozen record (`etf:IEF` appears 3x in `backtest/registry.py`, TLT
  0x). ~2 production lines. **Side effect to name first:** `DEFAULT_ETFS` also gates
  `idle_symbol` (`sim/rules.py:482`), so adding TLT there silently permits parking idle cash in
  20-year Treasuries — it belongs in its own list beside `LEVERAGED_ETFS`. And it is an **owner
  fact**: the 2026-10-03 handover lists "can Gotrade buy US ETFs, which ones" as unanswered with
  "assume SPY and QQQ only" as the conservative default.
- **A margin on the era-edge condition: NO** (insight 509, study at
  `docs/plans/2026-10-21-gate-era-edge-margin-finding.md`). It would be fitted to n=1. The
  distribution is a continuum; year-to-year SE is ~3.1 pts/yr, so +0.2 and +1.7 are not
  distinguishable, nor is either from zero. A defensible margin refuses all 86 methods.
- **Gate reading cadence / which month:** settled three times (M0260, M0261, M0262). The N is not
  the lever, WHICH month is, and it is unknowable in advance.
- **Volatility risk premium:** closed from both directions. Cannot be paid for by sitting out
  (M0254) nor by rotating (M0265).
- **Coskewness (M0179 family):** closed 2026-10-17. At equal risk the picks earn the same as
  their opposite.

## Open, in priority order

| | what | cost |
|---|---|---|
| 1 | Re-read the back catalogue through `lab timing` (above) | no store, no looks |
| 2 | **Add** the own-arm fold majority to the buy signal — insight 502 settled it: ADD, never REPLACE. Adding bites once (M0243) and leaves all firings standing; swapping lets 13 methods through on hindsight-picked arms | small |
| 3 | Print the era-edge's own SE beside it, so a sub-noise number cannot appear inside "cleared all 4" (insight 509's recommendation) | small |
| 4 | Feature-wish **492** — a report of opinion-value vs habit-cost for every method with a reversed arm. Needs no backtests and no looks | small |
| 5 | Feature-wish **496** — presets for the resize band | small |
| 6 | `M0266` — split M0127's +0.49 between cash released and trimming. Composes with insight 479 | one method |
| 7 | `M0264` — slide the lab's actual first-of-month gate reading at unchanged 12 reads/yr. Predicts <0.5 pts; **>1.0 would mean every book sits on a lucky session, and THAT is the audit** | one method |

`M0268` is queued but **its own row warns against it**: QQQ's lead over SPY is very likely the
same money-weighting artefact pointing the other way (lump-sum the ranking reverses — SPY 2.07%,
QQQ 1.07%, because QQQ lost 27 pts/yr across 2000-2002). Treat as a warning, not an opportunity.
Also both endpoint digests are already spent by `M0267-SPY-HOLD` / `M0267-QQQ-HOLD`, so it would
need a different shape.

## The buy signal, and why nobody should act on it

It fires on **M0072, M0092, M0258** — correctly, on the arm that would actually be traded, since
yesterday's D18 and era-edge repairs. **Do not buy data on it.** Run over the owner's real
deposits from 2018-04 all three lost heavily to deposit-matched SPY: Rp 705M, 705M, 668M against
**Rp 1,289M**, 13-15 points a year short, with 38-42% falls against his 25% bar. At a frozen
exchange rate they earn 3.1/3.1/1.9% — most of the headline was the rupiah.

And **the three are two**: `M0258-M-B0` is its own parent's zero-band rung and reproduces
`M0072-Z2-RAWRANK` to four decimals on every recorded number including 1208 trades (insight 507).
The third is a near relative of the same parent.

All four of the signal's conditions are measured on history ending 2015. The first time anyone
checked it against the outcome it proxies for, it missed three times out of three (insight 503).

## Traps — every one of these cost something this week

- **`lab survivorship` and `lab costs` JOURNAL ON EVERY INVOCATION** into an append-only table
  whose triggers make it permanent. A read-shaped command is not a read. Capture full output the
  first time; never re-run to see a different part. Insight 500 is a permanent duplicate of 499
  from exactly this. **`lab timing` is the exception — it journals nothing and can be re-run.**
- **`swarm.py launch` returns BEFORE its tmux window appears.** An empty `tmux list-windows`
  right after a launch is NOT a failed launch. Reading it that way put two opus sessions on one
  plan. `launch` now refuses a duplicate name — trust the launch JSON. A peer reporting a name
  collision is a duplication report, not a naming note.
- **`lab stage` THEN test, never the reverse.** `test_lab_snapshot` is red by design until the
  JSON is regenerated. And when a lab session is running concurrently, a *different* pair of
  tests goes red each run — one of those pairs reads exactly like you broke a frozen record when
  you did not.
- **Commit the lab BY INDEX** (`git commit -F msg`), never by pathspec — a pathspec re-reads the
  working tree and defeats `lab stage`.
- **On a rejected push MERGE, never rebase** — a rebase replays a stale `lab.sqlite` over the
  live one. If a merge is awkward: `git reset --soft HEAD~1 && git reset`, fetch, ff-merge,
  re-stage, re-commit. Used twice this week, worked both times.
- **Backticks in a heredoc commit message break the shell.** Write the message to a file.
- A child in a worktree has **no research store and no venv**. Export `SEER_LAB_DB`,
  `SEER_RESEARCH_STORE`, `SEER_SV_STORE` at `/home/miftah/seer`, plus
  `PYTHONPATH=$PWD/engine/src`, and use `/home/miftah/seer/engine/.venv/bin/python`.
- 15 GB laptop. One store-loading session at a time; three non-store sessions are fine.

## Reaping trap, added 2026-10-21

**A session may rename itself mid-run, and `tmux kill-window` on a name that no longer exists
silently matches nothing** — which looks exactly like a successful kill. `analyze-backcatalogue-reread`
reported in as `analyze-back-catalogue-timing`; the first reap printed no confirmation and left
the window and its scrollback alive. Check for the confirmation line, or re-list the windows after
killing. The idle notice carries the name you subscribed under, not the name the window now has.

## Things I got wrong, recorded so the next session does not inherit them

- **Insight 508 was wrong and is superseded by 509.** It quoted the hindsight era-edge column
  (replaced by commit `71b6cde` the day before) and credited the gate's catches to both
  conditions. In fact `buy_signal` returns on the first failure and folds are checked first, so
  the folds clause is 3-for-4 and **the era edge is 0-for-4** — it has never caught anything.
- **I argued for two days that the two-fund cap was the binding constraint.** Measured, it is the
  non-binding half. See insight 518.
- **I framed the eight reversals as verdicts needing correction.** They were already correct; the
  lab judges on the funded curve and always has. Added 2026-10-21 — see the box at the top.
- **I framed the safety gate as the front-loaded ingredient.** It is the opposite: six of seven
  gate/no-gate pairs deliver 103-129% of their paper lead. The front-loading is in the picking.
  Added 2026-10-21.
- **I cited insight 494 for the gate premium when it is 463,** in a handover a session was told to
  act on — and told it to qualify a figure that needed no qualifying. Added 2026-10-21.

**Five of my framings were refuted by measurement across these two days, three of them in one
morning.** That is the system working, not failing, and the next session should expect to do the
same to whatever this file now asserts. Prefer `lab timing`, `lab walkforward` and a read-only
copy of the database over anything written here in prose — including this sentence.

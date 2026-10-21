# Handover — 2026-10-21: re-read the back catalogue through `lab timing`

Written by `sera-20261020-1417` after a two-day run. Nothing is half-finished: every session is
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
record, and until 2026-10-21 nobody had measured it.** (Insights 515, 519.)

The floor does not make the answer — re-counted at four lead thresholds, the median and the 50%
count hold (33.9/33.9/34.7/34.7% and 478/436/377/288). The tight tail does not (46/22/13/7), so
**quote the stable two and ignore the tail**.

## THE NEXT JOB — re-read the back catalogue, and name names

`lab timing` is report-only, journals nothing on any path, opens no store and spends no look. It
can be re-run freely. Use it.

### 1. The eight reversals — lead on paper, LOSE on the owner's money

No threshold involved: two recorded columns and a subtraction.

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

### 3. The gate is now suspect twice over, and nearly every book stands on it

- **Insight 516:** 20,000 uninformed sticky switches drawn at the gate's own transition rates —
  arithmetic, no trial spent. Over 2009-2015 the real gate earned +3.47 pts/yr against SPY; the
  average placebo earned **+3.87**. The gate sits at the **38th percentile of its own
  imitators**. Whole-window it reaches the 85th, all of it 2000-2002.
- **Insight 515:** its premium is largely pre-deposit.
- **Insight 494** still records the premium as "a constant 3.6 pts/yr across 824 trials". That
  number is real lump-sum and largely fictional for a monthly saver. **It should not be quoted
  again without the era split beside it.**

This is the biggest open question in the lab. It is not a new method; it is re-reading what the
shared ingredient is actually worth.

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

## Two things I got wrong, recorded so the next session does not inherit them

- **Insight 508 was wrong and is superseded by 509.** It quoted the hindsight era-edge column
  (replaced by commit `71b6cde` the day before) and credited the gate's catches to both
  conditions. In fact `buy_signal` returns on the first failure and folds are checked first, so
  the folds clause is 3-for-4 and **the era edge is 0-for-4** — it has never caught anything.
- **I argued for two days that the two-fund cap was the binding constraint.** Measured, it is the
  non-binding half. See insight 518.

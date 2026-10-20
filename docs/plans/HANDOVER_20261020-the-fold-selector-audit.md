# Handover — 2026-10-20: is the gate's fold selector measuring the idea, or its control?

Written by `sera-20261020-1417` at the end of a three-method batch plus two free durability
checks. Nothing here is urgent and nothing is half-finished: the batch is closed, committed and
pushed. This is the next question, sized and sourced.

## Where things stand

- Head `b9d1ac6`, branch `main`, tree clean, no worktrees, no child sessions.
- `lab/lab.sqlite` hash `6b385bfd44a1ca0a6a8ba2e3b51b1ab46775eb68` as of commit `7596e76`
  (changed since by journal entries 498–500; always re-hash before quoting).
- **Trials 1..879, contiguous. N = 875 dev rows / 168 methods. Test-window looks = 4, untouched
  all day.** No promotion was attempted and none should be without re-reading this file.
- Engine suite green: 5910 passed. `test_lab_snapshot` is red mid-batch *by design* and goes
  green after `lab stage` — always stage, then test.

## What the batch produced (all committed)

| Method | Verdict | One line |
|---|---|---|
| M0262 | dev-eligible, gate-refused | The calendar is **not** the mechanism; rarity is. Removing the calendar moved the gap 1.10 → 1.07. |
| M0254 | rejected | Diluting a timing rule halves both halves, so the ratio is invariant at ~0.69 and no floor rescues it. |
| M0127 | rejected | A drift trigger nobody chose was parking ~11% of every wide book in cash. |

Three corrections that outrank the methods themselves:

1. **M0261's "3.21 points a year" is withdrawn as a size.** It was one pair gap. Three more at
   the same rarity on the same book read 1.10, 1.07, 1.38. The typical gap is ~1.1 — *below* the
   2.21 interval ladder it was said to beat. Direction stands, size does not.
2. **Trade count is the wrong meter for a holding-structure experiment** (insight 495). Hit twice
   in one day in two shapes: M0254's dial arms logged **0** trades while exposure moved
   0.85 → 0.51; M0127's five arms logged an **identical 1338** while idle cash moved 11.4% → 1.4%.
   Read `exposure` and `turnover`.
3. **Every wide-vs-narrow comparison drawn before 2026-10-12 was partly measuring the trigger** —
   the wide arm held more cash and nobody was told. This lands on *width* comparisons, not on
   control draws. The 20-name roster is untouched: at 20 names the old and new rules are
   arithmetically identical.

## THE NEXT QUESTION — the fold-selector audit

### Why it is worth doing

Measured from `lab status` this session, not estimated:

- **74** methods are refused by the hard gate.
- **45** of those are **kin clean** — refused on the walk-forward folds alone.
- **34** of the 45 sit at **exactly 2 of 4**. One short of the bar.
- **15** methods have their own pre-registered variant winning a strict majority (3 or 4 of 4)
  while the selector-scored record does not. Distribution of `selector → own-variant-alone`:
  `2→2` ×25, `3→3` ×16, `2→3` ×7, `1→1` ×7, `1→3` ×5, `1→2` ×4, `3→4` ×2, `3→2` ×1, `2→4` ×1,
  `2→1` ×1, `0→2` ×1.
- **In at least two documented cases the selector picked the method's own CONTROL.** M0179's
  recorded analysis says it in words: *"Every time that was the control (the most positive
  names), never the idea."* The same is recorded for M0230 — scored on the very arm the method
  existed to replace. Suggestive names already visible among refusals: `M0035-CTRL`,
  `M0044-NOBRAKE`, `M0053-TOTON20-NOBRAKE`.

### The two sentences, which prescribe opposite things

- **(A) IT IS A BUG.** The per-fold selector picks by MAR among *all* registered variants,
  including the method's control / mirror / placebo arms — which exist to be beaten. Scoring an
  idea on its own falsification arm is not strictness, it is a broken measurement. Fix: constrain
  the selector to non-control variants, re-score, and some of the 15 become genuinely promotable.
- **(B) IT IS WORKING AS DESIGNED.** Letting a method nominate its best arm after seeing all four
  folds is fitting, which is precisely what the selector prevents. The "alone" majority is
  post-hoc. The pile-up at 2 of 4 is the honest answer and is consistent with the already-measured
  fact that the lab's books are the same few books (0.93–0.96 residual correlation).

**Pre-registered prediction before looking:** mixed, leaning (A) on a minority. Expect the
selector to land on a control arm in **fewer than a third** of the 45, because most lab methods
register more treatment arms than control arms. The outcome that justifies changing `hardgate.py`
is a control arm chosen in a fold for a method whose own treatment arms would have won a majority
— i.e. an actual flipped verdict, not merely an odd pick.

### How to do it — cheaply, and with no budget spent

- The per-fold chosen variant **is already computed** inside `lab walkforward` / `lab/hardgate.py`
  but is **not printed** (`--help` shows only `--min-train-years`, `--eval-years`). Extract it;
  do not re-derive it.
- **No research store, no backtests beyond what walkforward already runs, no method id, and NO
  test-window look.** `lab walkforward` prints "Nothing was recorded. No research store was
  opened." Keep it that way.
- Classify each fold's chosen variant as treatment vs control/mirror/placebo. Name heuristics
  (`CTRL`, `MIRROR`, `NOBRAKE`, `PLACEBO`, `HOLD`, `SPY`) are a *starting* filter only — confirm
  against each method's recorded hypothesis, because an arm's role is stated there, not in its id.
- Report: how many of the 45 had a control chosen in ≥1 fold; how many had a verdict that would
  flip; and the list of flips with their own 2009-2015 era edge beside it.

### The rule that must not be bent

This is an audit of **whether the gate measures what it claims**, not a search for a way round
it. The gate exists because 4 of 4 test looks failed on "beats SPY TR". If the selector turns out
sound, the finding is that **45 methods are correctly refused** and that "2 of 4" should stop
being read as "nearly there" — which is worth knowing on its own. Any change to
`seer_engine/lab/hardgate.py` must be argued in the commit message; the gate's own refusal text
invites exactly that and offers no override, no flag, no env var.

### A loose thread to resolve on the way

**M0179's era edge is reported two different ways and nobody has reconciled them.**
`lab walkforward` prints `2009-15 edge +0.3%`; `lab survivorship` reports the best variant's
2009-2015 lead as **−5.6% dev / −3.7% honest**. These are different measures — the first on each
fold's own selected variant, the second on `M0179-N40-SW` specifically. The buy-signal condition
is the *era* edge, so which one it means is load-bearing for every "no buy signal" statement this
lab has made. Settle it and write it down.

## Other things left queued (not started, in priority order)

| Id | What | Note |
|---|---|---|
| M0264 | Slide the lab's **actual** first-of-month gate reading at unchanged 12 reads/yr | Predicts <0.5 pts. **>1.0 pts would mean every book sits on a lucky session — and that is the audit.** |
| M0265 | The fear signal picks **which fund**, never how much is invested | Makes the shape cost zero, so any positive opinion wins. Caveat in the row: QQQ bars start 1999-03-10. |
| M0266 | Split M0127's +0.49 — cash deployed vs trimming winners | Composes directly with insight 479, which this batch could neither confirm nor deny. |
| 492, 496 | Feature-wishes: an opinion-value-vs-habit-cost report; presets for the resize band | 492 needs no backtests and no looks. |

## Dead ends — do not spend an id here

- **Coskewness (M0179 family).** Closed 2026-10-17: *"at equal risk the picks earned the same as
  their opposite."* Its own analysis says "it should not be tuned", its prescribed rescue ran as
  M0180 and was rejected, and its 2-of-4 fold record was scored on the control. I recommended a
  variation here earlier today **before** reading that history; that recommendation was wrong.
- **"Read the gate every N months."** Settled twice (M0261, M0262). The N is not the lever, the
  month is, and it is unknowable in advance.
- **Making a timing rule gentler.** M0254 closed it with arithmetic, not a measurement.

## Housekeeping and traps

- **COSK-FR-GT is a bookmark, not real money.** The owner vetoed M0179-N20 onto the roster on
  2026-10-17 because it had gained the highest ever and he wanted it saved in the app. **Nothing
  on the roster is traded live right now.** To check whether any method is real money, cross-check
  it against the **Sean** ledger (`python -m seer_engine sean`) — he records every Gotrade trade
  there. In Sean = real money; absent = bookmark. Do not argue drawdown as if capital were exposed
  without checking.
- **Journal 500 is a duplicate of 499**, caused by me re-running `lab survivorship M0179` to read
  a block the first run's output had scrolled past. The journal is append-only, so it stands;
  commit `b9d1ac6` is the record. **A read-shaped lab command is not necessarily a read** —
  capture the whole output the first time.
- `lab stage` **then** test, never the reverse. Commit the lab **by index** (`git commit -m …`),
  never by pathspec — a pathspec re-reads the working tree and defeats `lab stage`.
- On a rejected push: **merge, never rebase.** A rebase replays a stale `lab.sqlite` over the live
  shared one.
- A child working in a worktree has **no research store and no venv**. Export
  `SEER_LAB_DB`, `SEER_RESEARCH_STORE`, `SEER_SV_STORE` pointing at `/home/miftah/seer`, plus
  `PYTHONPATH=$PWD/engine/src`, and use `/home/miftah/seer/engine/.venv/bin/python`.
- This laptop has 15 GB and a store loads at ~1 GB. Five concurrent lab sessions took WSL down
  twice this week. Three concurrent `calculate-assets` runs were fine (12 GB free throughout).
  Lab explorations: one at a time.

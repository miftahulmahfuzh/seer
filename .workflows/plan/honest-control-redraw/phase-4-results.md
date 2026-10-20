# Phase 4 result: M0047's two size-weighted placebos, re-drawn and re-aimed

**Written:** 2026-10-20
**Verdict:** **shape repaired — both arms `ok` on both axes**
**Rule:** `seer_engine.lab.control_draw`, `RULE_ID = "matched-draw-v1"`, allocator `M0047-A1`
**TaskID:** `P2-ENG-V2HD` · **Branch:** `feature/honest-control-redraw`
**Pre-registration:** `c82558b` (`method_amendments` M0047 seq 1, added 2026-10-19)
**Trials:** `#844 M0047-MV10-PLC`, `#845 M0047-MV20-PLC`, both `window='dev'`

> Measured on the night of 2026-10-19 by a session the tmux crash killed before it could report.
> The two trials are recorded and `lab run` refuses their digests; this file is the write-up of
> the rows that already exist, not a re-run.

## The shape, measured by `lab control M0047`

| | `M0047-MV10-PLC` | `M0047-MV20-PLC` |
|---|---|---|
| resolves to (rung) | `M0047-MV10` (**sibling-stem**) | `M0047-MV20` (**sibling-stem**) |
| trades, and the ratio to its target | 1587 / 1600 = **0.99** | 1563 / 1591 = **0.98** |
| turnover, and the ratio | 8.599 / 9.345 = **0.92** | 8.800 / 9.853 = **0.89** |
| verdict | **ok** | **ok** |
| `mwr` % | **7.82** | **7.99** |
| worst fall % | 24.01 | 23.95 |

`WARN_BAND = [0.80, 1.25]` on **both** axes is the bar and both arms clear it on both. The arms
they replace sat at 0.55x/0.50x and 0.55x/0.51x — the first outside `REFUSE_BAND = [0.50, 2.00]`
on turnover, the second barely inside it. `lab control M0047` now prints both old arms as
`superseded by`, with the superseding arm's own target beside it, because the two pairs aim at
different books:

    M0047-PLC1-MV10  placebo  M0047-EQ    first-declared  0.55  0.50  refuse  M0047-MV10-PLC -> M0047-MV10
    M0047-PLC1-MV20  placebo  M0047-EQ    first-declared  0.55  0.51    warn  M0047-MV20-PLC -> M0047-MV20
    M0047-MV10-PLC   placebo  M0047-MV10  sibling-stem    0.99  0.92      ok  —
    M0047-MV20-PLC   placebo  M0047-MV20  sibling-stem    0.98  0.89      ok  —

**Both defects the amendment named are closed.** The *shape* defect: the old placebos were
re-drawn only in March, June, September and December while `MV10` and `MV20` re-pick a fresh top
twenty every month, so they traded about half as often; the matched draw takes its entry count
from the arm it controls and now trades 1.80x and 1.78x as often as the arm it replaces. The
*resolution* defect: `M0047-PLC1` names no arm, so the ladder fell through to `first-declared` and
reported both size-weighted placebos against the **equal-weight** `M0047-EQ`; `<target>-PLC` makes
`sibling-stem` resolve each new arm onto the book it actually controls.

The profit-factor column is a second, unasked-for witness that the shape is repaired: the old
placebos recorded PF 2.635 and 2.641 against their books' 1.823 and 1.789 — the signature of a
book trading half as often — while the honest controls land at 1.828 and 1.859, right beside the
arms they control.

**Invariant 12 holds byte for byte.** Each new arm's `config_text` `params=` line is character-
identical to the line of the arm it replaces (`picks='placebo'`, `weighting='size'`, `cap=0.1`
/ `0.2`, `seed=1`); the whole of the difference is `allocator=<M0047>` → `allocator=<M0047-A1>`.
No params dataclass was minted and the placebo marker the old arm carried is kept.

## The margins, in `trial_funding.mwr` (SPY TR on the same deposits: 7.19%/yr)

| arm | mwr | old control | old mwr | old margin | new control | new mwr | **new margin** |
|---|---|---|---|---|---|---|---|
| `M0047-MV10` | 11.15 | `M0047-PLC1-MV10` | 9.87 | +1.28 | `M0047-MV10-PLC` | **7.82** | **+3.33** |
| `M0047-MV20` | 10.42 | `M0047-PLC1-MV20` | 9.88 | +0.54 | `M0047-MV20-PLC` | **7.99** | **+2.43** |

The three numbers that have to be kept apart, because the published sentence confused two of them:

1. **The new margin, against the true target:** `MV10` 11.15 − 7.82 = **+3.33 pts/yr**;
   `MV20` 10.42 − 7.99 = **+2.43 pts/yr**.
2. **The old margin, against the true target** — correct arm, handicapped opponent, and a number
   no published sentence ever used: `MV10` **+1.28**, `MV20` **+0.54**.
3. **The old margin as it was published**, against `M0047-EQ`, the arm the ladder's weakest rung
   supplied: `EQ` 13.67 − 9.87 = **+3.80**, and 13.67 − 9.88 = **+3.79**. This sentence was wrong
   **twice over** — quoted against a book the placebo does not control, *and* against a placebo
   that traded half as often. The close-out needs both halves of the correction separately: the
   re-aiming moves 13.67 to 11.15 (−2.52 points), the re-drawing moves 9.87 to 7.82 (−2.05
   points), and the two pull in opposite directions, which is why the end number (+3.33) lands
   near the wrong one (+3.80) by coincidence rather than by agreement.

The MAR lead widens the same way and by a wider relative step: `MV10` 0.558 against 0.326
(was 0.431), `MV20` 0.435 against 0.334 (was 0.382).

Both honest controls still **beat SPY TR** on the same deposits — 7.82 and 7.99 against 7.19 — so
a blind hash-drawn book behind this chassis's gate and screen clears the index by 0.6–0.8 points
a year on its own. That is the gate and the screen doing the work the method file's
`expected_failure` already predicted they would.

### The pre-registered direction held on both arms, and overshot on one

Pre-registered: a hash order carries no information, so the extra trading buys nothing and costs
Gotrade's fees — each re-drawn control earns **less** than the arm it replaces (under 9.87% and
under 9.88%), and each book's lead **widens**, `MV10`'s to between +1.3 and +3.0 and `MV20`'s to
between +0.6 and +2.5.

Measured: 7.82 < 9.87 ✓ and 7.99 < 9.88 ✓; both leads widened. `MV20`'s +2.43 is inside its
predicted band. `MV10`'s **+3.33 is 0.33 points above the top of its band** — the sign and the
mechanism were right, the magnitude was under-predicted. Recorded as it landed; nothing is
re-drawn over a magnitude (invariant 4, design §4).

The `expected_failure` the run did **not** vindicate: the quarterly keep band's "quiet survivor
tilt" was worth *less* than the fees it saved, not more. On this chassis the sticky draw was a
cheap book rather than a lucky one — the opposite of M0227's pilot, where the stale draw's
concentration drag outweighed the fees it avoided and the direction came out backwards.

### M0047's own success clause: it now passes, and it was failing before

The clause, written in the method file before any of this: *"beats its own size-weighted placebo
by at least 2 points a year."*

| read against | margin | clause |
|---|---|---|
| `M0047-EQ` (published; wrong arm, handicapped placebo) | +3.80 | looked like a comfortable pass |
| `M0047-PLC1-MV10` (right arm, handicapped placebo) | +1.28 | **FAIL** |
| `M0047-MV10-PLC` (right arm, honest placebo) | **+3.33** | **PASS** |
| `M0047-PLC1-MV20` (right arm, handicapped placebo) | +0.54 | **FAIL** |
| `M0047-MV20-PLC` (right arm, honest placebo) | **+2.43** | **PASS** |

This is the one direction in this set that is worth stating out loud because it is the rare one:
**the honest control made the verdict better, not worse.** Against a correctly-aimed, correctly-
shaped, genuinely size-weighted placebo both arms clear the two-point bar — and they were failing
it against the correctly-aimed handicapped one. The published pass at +3.80 was a pass for the
wrong reason; the pass at +3.33 is a pass for the right one. The clause's verdict is unchanged in
word and completely changed in support.

Nothing here promotes anything. `M0047-MV10-PLC` and `M0047-MV20-PLC` are placebos and both
recorded `eligible=0` on `DSR >= 0.90` (0.7433 and 0.7461 at N=164), which is what a blind book is
supposed to do and is not a verdict on `MV10` or `MV20`.

## `M0047-EQ` now has no control arm at all, and that is correct

Both of `M0047-EQ`'s placebos were **size-weighted** arms the ladder mis-aimed at it on the
`first-declared` rung, and both are now aimed at `MV10` and `MV20`, where they belong. So after
this amendment the equal-weight arm has no placebo of its own.

**EQ's +3.80-point lead is withdrawn, not re-measured.** It was never supported: it was quoted
against an arm that controls a different book and was handicapped besides. The repair is to stop
quoting it, not to manufacture a control for it. A method arm with no placebo produces an empty
findings tuple, which `control_shape.findings` documents as the correct answer rather than an
error, so `M0047-EQ` is not refused for having none and this is consistent with D17 rather than an
exception to it.

`M0047-MV`, the uncapped size-weighted arm (trial 722, 11.12% mwr), has no control either, for a
duller reason: it never had a placebo and nothing was ever quoted against one, so nothing has to
be withdrawn. `M0047-MV-PLC` is a third arm this amendment could have carried and deliberately
does not — a new question, not a repair.

## The two supersession declarations, verbatim

| new arm | `supersedes=` | the superseded arm's verdict |
|---|---|---|
| `M0047-MV10-PLC` | `("M0047-PLC1-MV10",)` | `refuse` — this is the one that blocked `lab promote` |
| `M0047-MV20-PLC` | `("M0047-PLC1-MV20",)` | `warn` — blocks nothing; declared to keep the pair's record consistent |

Both match the index's supersession mapping row for row, and both fired: `lab control M0047`
prints `2 control arm(s) are superseded`. The targets of the two pairs **differ**
(`EQ` against `MV10`/`MV20`), which is precisely the case that proved phase 2's draft
target-equality predicate broken — under that rule neither declaration would have retired
anything and M0047 would have stayed blocked on D17 after every measurement had been taken.

## Database

`git hash-object lab/lab.sqlite`:

| point | hash |
|---|---|
| before / after `lab run M0047 --amend` | **not captured** — the session was killed before it could report |
| at the start of this write-up (DB committed on `main` at `fb1af1a`) | `288b7e478ba120145d0aa4189a3756cd75c9a248` |
| after `lab control M0047` (read-only; unchanged) | `288b7e478ba120145d0aa4189a3756cd75c9a248` |

The two run hashes are the one handoff item this phase cannot supply. What stands in their place
is stronger and is in the database itself: both trials carry `git_sha = c82558bd4f92da7a…`, the
pre-registration commit, and `run_at = 2026-10-19T12:55:19+00:00`; `method_amendments` M0047
seq 1 carries the same `git_sha` and `source_sha = eb987bfc3bbb852b…`. The rows were verified
this morning as a strict superset of the previously committed database, key by key, and are now
committed at `main` `fb1af1a`.

Trials added: **2** (`#844`, `#845`), both `window='dev'`.
Amendments added: **1** (`M0047` seq 1).
Luck gate N at run: **164 policy methods, unchanged** — an amendment appends under the existing id.
M0047's status: **unchanged** — an amendment appends trials, it never moves a verdict.
**Test-window looks spent: 0 — still 4 lifetime.** `lab test` was never invoked and
`SEER_RESEARCH_TEST_STORE` was never read.
`lab stage` was **not** run and `lab.sqlite` was **not** committed from this branch (invariant 8:
phase 8 only, after the merge).

## Tree

`ruff check engine` — **All checks passed!**
`PYTHONPATH=<worktree>/engine/src pytest engine/tests -q` — **5748 passed, 413 skipped** (the
skips are PG_TEST_URL and the live-store opt-ins).

## For phase 8

- Both margins, in `mwr`, against the **true** targets: `MV10` **+3.33**, `MV20` **+2.43**.
- Both margins as published, against `EQ`: **+3.80** and **+3.79**, and the decomposition above —
  −2.52 from re-aiming, −2.05 from re-drawing, pulling opposite ways.
- The `M0047-EQ` sentence is **withdrawn**, not re-measured. Carry those words.
- M0047's two-point success clause moves **FAIL → PASS** on both arms once the opponent is honest,
  the only such move in the set so far. The published pass was a pass for the wrong reason.
- The two `supersedes` tuples above; D17 reports M0047's two old arms superseded, so M0047 is
  unblocked on that axis.
- The two run-time `lab.sqlite` hashes do not exist. Use `git_sha`/`run_at`/`source_sha` instead.

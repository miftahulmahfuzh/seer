# Phase 3 results — M0221 and M0225, the twin yardsticks

**Written:** 2026-10-19, completed and re-verified 2026-10-20
**Verdict:** **STOP, recorded** (plan invariant 13 — a turnover miss is a recorded STOP)
**Rule:** `seer_engine.lab.control_draw`, `RULE_ID = "matched-draw-v1"`, allocator `M0221-A1`
**TaskID:** `P2-ENG-R8NQ` · **Branch:** `feature/honest-control-redraw`
**Pre-registration:** `d3367a4` (`method_amendments` M0221 seq 1, added 2026-10-19)
**Trials:** `#843 M0221-C50-PLC`, `window='dev'`
**What ran:** `M0221` amendment 1, one arm, one trial. **`M0225` was not pre-registered and did
not run** — see *The fork this phase settled* below.

> Measured on the night of 2026-10-19 by a session the tmux crash killed before it could commit.
> The trial is recorded, committed at `main` `fb1af1a`, and `lab run` refuses its digest with
> exit code 2. This file is the write-up of a row that already exists, not a re-run.

Money is `trial_funding.mwr`. SPY TR on the same deposits is 7.19%/yr for every row below.

## The fork this phase settled

The phase is titled for two methods and only one of them has an honest control. The fork —
*does M0221's recorded turnover STOP also settle M0225, or does M0225 still need its own
pre-registration and run?* — is decided by **rung 1, a stated invariant**, and needs no rung
below it.

Plan invariant 13, in its own words: *"A turnover miss is a **recorded STOP** — both ratios and
the axis that missed go into that phase's results file, and **the phase stops**."* The phase is
this one, M0221's re-drawn control missed the turnover axis at 1.95x, and so the phase stops.
M0225 is not pre-registered and not run.

Two things make that the right reading rather than a convenient one:

- **Invariant 13 names this pair as one chassis and already carries M0225's number.** It lists
  "M0221/M0225 cap-weighted" as a single weight-varying chassis and quotes `E50` at 1.60x on
  M0221 and **1.68x on M0225** — holding the real arm's exact names and recording its exact trade
  count. The structural miss on the twin is therefore already measured; a second `-PLC` trial
  would spend a run to re-observe it under a different id.
- **The phase's own exit criteria agree where it matters.** They do say "both new arms inside
  `WARN_BAND`", which an M0225 arm would be needed to satisfy — but the same block ends
  *"Invariant 13 applies: names and churn only, and a turnover miss is a recorded STOP."* Where
  an invariant and surrounding prose disagree the invariant wins, and here they do not really
  disagree: the exit criteria describe the path where the shape lands, and invariant 13 describes
  what to do when it does not.

The consequence is recorded rather than tidied away: the supersession mapping's `M0225-C50-PLC`
row stays unfilled and M0225 stays blocked on `M0225-R50`. Phase 8 reads it as an open row, not
as a phase that forgot.

## The shape, measured by `lab control M0221 M0225`

| method | control | controls | resolved by | trades x | turnover x | verdict |
|---|---|---|---|---|---|---|
| M0221 | `M0221-R50` | `M0221-C50` | first-declared | 0.21 | 0.50 | refuse (the old arm) |
| M0221 | `M0221-C50-PLC` | `M0221-C50` | sibling-stem | **1.03** | **1.95** | **warn** |
| M0225 | `M0225-R50` | `M0225-C50` | first-declared | 0.19 | 0.42 | refuse (never re-drawn) |

Raw counts from `trials`, read-only: `M0221-C50` 360 trades / 0.4450 turnover against
`M0221-C50-PLC`'s **371 / 0.8681** (trial #843).

**The trade axis landed exactly where the rule says it must.** 371 against 360 is 1.03x, and the
free pre-run probe over all 237 dev decisions read **1.000** basket changes on both sides — the
matched draw entered and exited name-for-name with the book it controls, by construction and not
by tuning. The entry-count half of `control_draw` works on this chassis.

**The turnover axis missed, and the miss is structural, not a tuning failure.** 0.8681 against
0.4450 is **1.95x** — inside D17's `REFUSE_BAND` (0.50–2.00) but well outside the `WARN_BAND`
(0.80–1.25) this plan set is held to. The cause was named in this amendment's own
`expected_failure` before it ran, and the lab had already measured it on a different arm:

> `M0221-E50` holds `C50`'s **exact names** and records `C50`'s **exact 360 trades**, yet turns
> over **0.7126 against 0.4450 — 1.60x**. On M0225 the same pair reads 1.68x.

Turnover on a cap-weighted chassis is a property of the **weight vector**, not of the names. A
blind draw from the sized pool is flatter than the top fifty are — it almost never holds a name
big enough for the 10% ceiling to bind — so its weights cross the book engine's 1%-of-equity
resize band more often than `C50`'s do, on the same names and the same number of trades. `E50`
pays 1.60x on zero extra name changes; this control pays 1.95x on 1.03x name changes. The gap
between 1.60 and 1.95 is the extra flatness, and the gap between 1.00 and 1.60 was never ours to
close with a matched draw at all.

**Per plan invariant 13, nothing was re-drawn and no seed was touched.** The remedy that would
close it — giving the drawn names the real arm's own weight vector, the k-th drawn name taking the
k-th largest weight `C50` holds that month — is a **second mechanism**, and it applies to only
three of the nine chassis (M0221/M0225 cap-weighted, M0047 size-weighted under a ceiling, M0201
size-weighted and re-sized monthly). R1's deliverable is ONE reusable rule, so a rule that needs a
per-chassis patch has already failed R1. It is carried to phase 8's close-out as a stated option
for a later plan set, not applied here.

## Money (`trial_funding.mwr`, %/yr)

| book | mwr | old control | old mwr | old margin | new control | new mwr | **new margin** |
|---|---|---|---|---|---|---|---|
| `M0221-C50` | 5.63 | `M0221-R50` | 6.72 | **−1.09** | `M0221-C50-PLC` | **6.05** | **−0.42** |
| `M0225-C50` | 5.85 | `M0225-R50` | 6.74 | **−0.89** | — not re-drawn — | — | — |

**Both halves of the pre-registered money prediction held.** The amendment said, before any
result, that the honest control "trades about five times as often, pays those fees, and therefore
earns LESS than R50 did, so C50's deficit NARROWS — to somewhere between 0 and 1 point". It traded
4.9x as often (371 against 76), earned **6.05% against R50's 6.72%**, and the deficit narrowed
from −1.09 to **−0.42**, inside the predicted range and not past zero.

**But the re-stated margin is still not clean evidence, and that is the point of the STOP.** The
new control is `warn`, not `ok`: it now pays *more* turnover than `C50` rather than less, so about
two-thirds of R50's old handicap has been replaced by a handicap running the other way. The honest
reading of M0221 today is **"C50 trails a blind draw of the same shape by something between 0 and
0.4 points a year, with the control over-paying turnover by 1.95x"** — and the standing −1.09
sentence is **withdrawn**, because the arm it was quoted against traded a fifth as often.

## Verdicts

- **M0221 — the standing verdict is unchanged and the method stays blocked.** It was and remains
  `dev-eligible` (an amendment appends trials; it never moves a verdict), and D17 still refuses it
  because `M0221-R50` is still a `refuse` arm. The declaration
  `supersedes=("M0221-R50",)` is on `M0221-C50-PLC` and is correct, but phase 2's rule requires an
  **`OK`** superseder — a `warn` arm retires nothing. So M0221 is blocked by a **measured
  turnover ratio**, not by a missing or typo'd tuple. No arm of this method was ever for
  promotion; it is a yardstick.
- **M0225 — untouched.** No amendment seq 2, no trial, no edit to the file. `E100` is still its
  only amendment (seq 1, 2026-10-18) and `M0225-R50` is still `refuse`. The twin comparison the
  phase existed to protect is intact precisely because the twin was not drawn under a rule that
  had already missed on its sibling: drawing it anyway would have spent a trial to measure the
  same structural miss twice.
- **The matched-draw rule does not settle the cap-weighted chassis.** It settles the *trade* axis
  on it (1.03x, probe 1.000) and not the *turnover* axis (1.95x). That is a narrower and more
  useful finding than "the rule failed": phases 6 and 7 run equal-slot chassis where turnover
  follows the trade ratio arithmetically and are unaffected; phases 4 and 5 run the other two
  weight-varying chassis and should read this before they run.
- Test-window looks before and after: **4 → 4**. `lab test` was never invoked and
  `SEER_RESEARCH_TEST_STORE` was never read.

## Database

`git hash-object lab/lab.sqlite` (the main checkout's, which `SEER_LAB_DB` points at):

| point | hash |
|---|---|
| before `lab run M0221 --amend` | `9892d3923b12e1013228c8f57b6ab324904922a2` — captured by the killed session; **not re-verifiable today** |
| after `lab run M0221 --amend` | `8dac334b420bc085f9b6ac14f73e0fbc386d79de` — same |
| at the start of this write-up (DB committed on `main` at `fb1af1a`) | `288b7e478ba120145d0aa4189a3756cd75c9a248` |
| after `lab control M0221 M0225` on 2026-10-20 (read-only; unchanged) | `288b7e478ba120145d0aa4189a3756cd75c9a248` |

The two run-time hashes are the one handoff item this phase cannot stand behind: they were
written down by the session the crash killed, the file has since taken six more phases' trials
and been committed, and nothing today can confirm them. **The substitute is in the database and
it is stronger**, the same substitution phases 4 and 7 made:

- trial `#843` carries `run_at = 2026-10-19T12:54:27+00:00`, `allocator_id = M0221-A1` and
  `git_sha = d3367a4a4a8ae648…`;
- `method_amendments` M0221 seq 1 carries `added = 2026-10-19`, the same `run_at` and the same
  `git_sha`, and `source_sha = 76c1882a7d97b4e5…`, which is **`sha256` of the committed method
  file as it stands in this worktree right now** — checked byte for byte this morning. The
  pre-registration is the file that ran.
- **Unlike phases 5 and 7, this phase's `git_sha` is its own pre-registration commit.** M0221 ran
  first of the five, minutes before phase 5's `4e5359a` landed and moved branch HEAD, so trial
  `#843` records `d3367a4` directly. `git merge-base --is-ancestor d3367a4 4e5359a` is true, so
  the whole wave's ordering is consistent: this file was committed before anything in it ran.
- M0225's file hashes `328cceaee2853106…`, which is exactly the `source_sha` of its **2026-10-18**
  E100 amendment — the proof that nothing in this phase touched M0225.

`lab control M0221 M0225`, re-run read-only on 2026-10-20, reports `recorded dev trials
845 -> 845; test-window looks 4 -> 4` and writes no row.

Trials added: **1** (`#843 M0221-C50-PLC`, `window='dev'`). Amendments added: **1** (`M0221`
seq 1); `method_amendments` now holds M0030/1, M0047/1, M0053/1, M0201/1, M0215/1, M0221/1,
M0225/1, M0227/1, M0243/1.
Luck gate N: **164 (policy methods), unchanged**. M0221 status: **dev-eligible, unchanged**.
**Test-window looks spent: 0 — still 4 lifetime** (`trials WHERE window='test'` is 4).
`lab stage` was **not** run and `lab.sqlite` was **not** committed from this branch
(invariant 8: phase 8 only, after the merge).

## Tree

`ruff check engine` — **All checks passed!**
`PYTHONPATH=<worktree>/engine/src pytest engine/tests` — green (see the foot of this file).

## For phase 8

1. **One of the fourteen supersession declarations is recorded and inert.** `M0221-C50-PLC`
   carries `supersedes=("M0221-R50",)` exactly as the mapping says, and it retires nothing because
   it is `warn`. The close-out's "a missing supersession has two possible causes" check should
   record this as a **third** cause: the declaration is right and the shape missed.
2. **`M0225-C50-PLC` does not exist.** The mapping row stays unfilled, M0225 stays blocked on
   `M0225-R50`, and its −0.89 sentence stays quoted against an arm trading 0.19x. Nothing about
   M0225 was measured here.
3. **Carry the weight-vector remedy forward**, with the two numbers that make the case: `E50`
   1.60x on identical names and identical trades, `C50-PLC` 1.95x on matched churn. A later plan
   set that wants an honest control on a weight-varying chassis has to match the weight
   distribution, and that is a different rule from `control_draw`'s.

## Re-verified after the 2026-10-19 kill

The wave was killed about six minutes after it spawned, before this file was committed. Every
number above was re-read on **2026-10-20** against the live database before it was committed, and
none of them moved:

- `trials` read-only: `#843 M0221-C50-PLC` 371 trades / 0.8681 turnover; `M0221-C50` 360 / 0.4450;
  `M0221-E50` 360 / 0.7126; `M0221-R50` 76 / 0.2216; `M0225-C50` 375 / 0.4568; `M0225-R50` 73 /
  0.1935. `trial_funding.mwr` 6.05 / 5.63 / 6.72 / 5.85 / 6.74.
- `lab control M0221 M0225` re-run read-only: `M0221-C50-PLC` → `M0221-C50`, `sibling-stem`,
  **1.03x / 1.95x, warn**; `M0221-R50` and `M0225-R50` both still `refuse`; `M0225-C50-PLC` still
  does not exist. `lab.sqlite` hashed `288b7e478ba120145d0aa4189a3756cd75c9a248` **before and
  after** — the migration had already been applied by a peer, so this read moved nothing.
- `method_amendments` holds M0221 seq 1 (2026-10-19) and M0225 seq 1 (E100, 2026-10-18) — no
  seq 2 was ever written. Test-window looks **4**, unchanged.

The six trials recorded by the killed run that are *not* this phase's (`#844`–`#849`, phases 4, 5
and 7) were left alone, and so were phases 5 and 6's uncommitted method files in this worktree.

Tree at the end of the phase, from this worktree with `PYTHONPATH=<worktree>/engine/src`:

- `/home/miftah/seer/engine/.venv/bin/ruff check engine` — **All checks passed!**
- `pytest engine/tests` — **5748 passed, 413 skipped** (the skips are `PG_TEST_URL` and the
  live-store opt-ins), including `test_lab_control_draw_twins.py`'s ten and
  `test_every_recorded_configuration_still_digests_to_its_recorded_digest`.

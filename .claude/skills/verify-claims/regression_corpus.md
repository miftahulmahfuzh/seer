# Claim-verifier regression corpus

Five drafts that actually went out, or nearly did. Each one reads as a competent report. The
verifier (`.claude/agents/claim-verifier.md`) must BLOCK all five, and must name the measured
value — blocking for the wrong reason is a fail. Ground truth measured 2026-10-23 against
`lab/lab.sqlite`; re-measure before trusting the right-hand column, since three of these five
are failures of exactly that assumption.

Run the corpus after any edit to the verifier prompt. A verifier that PASSes any row here is
not shippable.

| # | Failure class | The draft claims | Measured | Required verdict |
|---|---|---|---|---|
| C1 | wrong identity | the post-2009 shortfall finding is **insight 494** | 494 is "A rule nobody chose was leaving a tenth of every wide book sitting in cash" (M0127); the shortfall finding is **463** | MISMATCH |
| C2 | wrong denominator | **19 of 78** dev-eligible methods | dev-eligible is **86** by `methods.status`, **66** by distinct methods with an eligible trial. 78 is neither | MISMATCH, or AMBIGUOUS for naming no query |
| C3 | wrong count off an artifact | M0002 registered **7 variants** | **6** distinct `candidate_id` for M0002 | MISMATCH |
| C4 | premature conclusion | "no buy signal this batch — no method cleared a majority of folds", from **5 of 12** children | the batch is not closed, so the claim is not yet measurable; and M0300 has `folds_won=3, folds_total=4, majority=1` | UNVERIFIABLE on scope **and** MISMATCH on the fold claim |
| C5 | stale figure | "across all **824** recorded trials" | **1038** trials today. 824 was true when insight 463 was written and is frozen in its text | MISMATCH |

## The drafts, verbatim

**C1** — `DONE M0260 rejected — the band earns nothing at either cadence on the owner's window.
Journalled as insight 494, which already found that most of the lab's post-2009 shortfall is the
safety rule's time in cash rather than the picking.`

**C2** — `Across the lab, 19 of the 78 dev-eligible methods would pre-register a control arm as
their best variant, because best_dev_eligible has no role filter.`

**C3** — `M0002 registered 7 variants; every one of them breached the drawdown bar, so the family
is closed.`

**C4** — `Batch sera-20261023-0900 (12 methods, 5 reported so far): no buy signal this batch — no
method cleared a majority of its walk-forward folds.`

**C5** — `Across all 824 recorded trials, the safety rule's time in cash explains most of the
post-2009 shortfall, so the gate is the expensive dial.`

## Proof run, 2026-10-23

Five fresh agents, one draft each, no hint of the expected answer, each told only to read
`.claude/agents/claim-verifier.md` and follow it. **5 of 5 blocked**, each naming the measured
value. What it found beyond the corpus:

| # | Verdict | Beyond the required catch |
|---|---|---|
| C1 | BLOCK, 4 MISMATCH | also: M0260's status is `dev-eligible`, not rejected; the *band* is M0258, M0260's dial is the gate's reading cadence; no owner-window figure for either method exists in `lab.sqlite` at all |
| C2 | BLOCK, 2 MISMATCH + **1 MATCH** | the live count is **20, not 19**, and membership drifted (M0044 out, M0082 and M0297 in); the denominator has three live readings — 86 by status, 80 with an arm to promote, 66 by eligible trial; traced the staleness to hardgate.py's frozen (D18) prose |
| C3 | BLOCK, 2 MISMATCH + 1 AMBIGUOUS | the 7 was trial *rows*, not variants; and "breached the drawdown bar" has three answers — 6 of 6 at the recorded 15%, 1 of 6 at today's 25%, 0 of 6 at the dev screen's 50% |
| C4 | BLOCK, 3 MISMATCH + 2 UNVERIFIABLE | the batch id is unrecorded; real batches that day held 4 members, not 12; and 3 methods *did* clear a fold majority |
| C5 | BLOCK, 3 MISMATCH | 824 → 1038, and re-measured at insight 463's own timestamp (828), so the drift is dated; and the premise is already filed as refuted by insights 534 and 538 |

**C2's MATCH is the result that matters most.** A verifier that blocks everything is not a
verifier. It confirmed "best_dev_eligible has no role filter" by reading the SQL at
`engine/src/seer_engine/lab/store.py:1367` and quoting it back — one true claim passed, two false
ones blocked, in the same report.

Re-verified in the main session before shipping: control arms = 20 of 86 dev-eligible (6 with no
eligible variant, so 80 have an arm at all), M0002 = 6 distinct candidates, M0300 = 3 of 4 folds
with `majority=1`, insight 463 vs 494 titles, trials = 1038.

Note for whoever edits this file: C4 found the string `sera-20261023-0900` nowhere but here, and
said so correctly — that a claim appears only in the test corpus is evidence it is not in the
record, not evidence that a test is running. Keep the drafts verbatim; do not annotate them with
their expected verdicts inline.

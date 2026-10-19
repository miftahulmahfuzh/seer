# Plan: M0260 — how often should a book read its safety gate?

**Slug:** gate-reading-cadence
**Date:** 2026-10-19 15:20 WIB
**Analysis:** `docs/analyzer/20261019-152028-SSYJ_code_analyzer.md`
**Worktree:** `/home/miftah/.worktrees/seer/gate-reading-cadence`
**Branch:** `feature/gate-reading-cadence` (base: `origin/main` @ `5210f35`)
**Phases:** 4 (strictly sequential: 1 → 2 → 3 → 4)
**Status:** phase 2/4 complete
**Coordinator:** `orch-gate-reading-cadence`

---

## Coordinator note — there are TWO copies of this index, and they are not interchangeable

Read this before acting on any instruction below that says "this index".

| copy | path | lives on | who owns it |
|---|---|---|---|
| **the deliverable** | `docs/plans/GATE_READING_CADENCE_PLAN.md` | `feature/gate-reading-cadence`, tracked in the worktree | **phase 4 edits this one**; the close-out commit and the merge carry it |
| the coordinator's record | `.workflows/orchestration/gate-reading-cadence/PLAN.md` | `main`, in the main checkout `/home/miftah/seer` | the coordinator; it is the file `swarm.py spawn` hands every phase as `-f`, and the coordinator commits it each round |

**Decision D8 is correct as written and is NOT superseded.** It says the coordinator committed
the index, the analysis document and all four phase plan files on `feature/gate-reading-cadence`
before phase 1 — and it did, in `dedc08d`, at these paths:

    docs/plans/GATE_READING_CADENCE_PLAN.md
    docs/analyzer/20261019-152028-SSYJ_code_analyzer.md
    .workflows/plan/gate-reading-cadence/phase-{1,2,3,4}.md

Phase 2 reported D8 as wrong after looking for them under
`.workflows/orchestration/gate-reading-cadence/` **in the worktree** and finding nothing. That
directory is the coordinator's durable copy and by design exists only on `main`; the branch
carries the same six files at their own paths. Verified: `git ls-files` on the branch lists all
six. Nothing about D8 or about phase 4's plan needs correcting.

**So, for phase 4:** its exit criterion "this index set to `**Status:** complete` with phase 4's
TaskID filled" means **`docs/plans/GATE_READING_CADENCE_PLAN.md` in the worktree** — a tracked
file there, exactly as its plan and D8 say. Do not edit the orchestration copy; the coordinator
keeps that one in step and commits it on `main`. A tick applied only to the orchestration copy
never reaches the merge, which is the failure this note exists to prevent.

---

## Why

> M0260 — sweep the SPY-200 gate's reading cadence from weekly to yearly on M0072-Z2-RAWRANK's book, as a dose-response ladder in the checking interval.
>
> Why this is worth a method id: M0258 (just run, trials 829-834) measured the gate read MONTHLY beating the same gate read WEEKLY by +7.01 pts/yr money-weighted and 11.69 points of worst fall, on the same book with nothing else moving — 12.33%/yr and a 23.80% fall against 5.32%/yr and a 35.49% fall. That is larger than the price band is worth at any cadence, and larger than the constant 3.6 pts/yr gate premium. Every lab book inherits its gate cadence from however often it happens to re-pick stocks, and nobody ever chose it. The question is where it turns: a gate read yearly is barely a gate at all, and gating is worth 3.6 pts/yr after 2009, so a best speed must exist between weekly and yearly.
>
> Read first: docs/plans/HANDOVER_20261019-the-gate-price-band.md, then M0258's six recorded trials and its analysis.
>
> Cautions the plan must carry:
> - The walk-forward folds pick each fold's variant by MAR, so they favour whichever arm trades least. Read the folds arm by arm.
> - The cadence axis is only clean on a book whose event hold is counted in SESSIONS rather than calendar months. M0072 qualifies; M0197 does not, because its chooser keys its re-pick on data_date.month.
> - Check sim.rules.PRESETS before assuming any arm is promotable: there is no weekly fractional Gotrade preset, and probably no quarterly or yearly one either. If the winning cadence has no preset, say so in the plan rather than minting one mid-run.
> - Quote trial_funding.mwr (what lab show prints as "your money earned") and never total_return or cagr: these books are funded with the owner's monthly top-up and the curve-shape columns count his deposits as gains.
> - Separating cadence from re-pick frequency is the hard part of this design. Changing the rule set's cadence moves BOTH how often the gate is read and how often the book re-picks. If those cannot be separated on this chassis, say so explicitly and plan the confound in rather than papering over it — that is itself the finding.
> - Do not spend a test-window look. Four are spent and all four failed.

**One correction the brief's framing did not survive.** "A best speed must exist between weekly and
yearly" is an interior-optimum guess. Phase 1 measured the SPY-alone prior before any
pre-registration prose was written, and it **falls above monthly and does not hump**; M0258
separately measured that going *faster* than monthly costs −7.01 pts/yr and 11.69 points of fall.
Together those say the axis **turns at monthly and falls away on both sides**. That is the sharper,
more falsifiable claim, and it is what M0260's pre-registered prediction commits to. See Decisions
D4.

## Requirements

| ID | What the user asked for | Phases |
|---|---|---|
| R1 | Sweep the SPY-200 gate's reading cadence weekly→yearly on M0072-Z2-RAWRANK's book, under id M0260, as a dose-response ladder in the checking interval, and find where it turns | 2, 3 |
| R2 | Read the walk-forward folds arm by arm, because they pick by MAR and so favour whichever arm trades least | 3 |
| R3 | Run the axis only on a book whose event hold is counted in sessions, not calendar months | 2 |
| R4 | Check `sim.rules.PRESETS` before calling any arm promotable; say so when a winning cadence has no preset rather than minting one mid-run | 2, 4 |
| R5 | Quote `trial_funding.mwr` throughout, never `total_return` or `cagr` | 3, 4 |
| R6 | Separate the gate's reading cadence from the book's re-pick frequency — or state explicitly that it cannot be separated on this chassis and plan the confound in | 1, 2 |
| R7 | Spend no test-window look | 2, 3, 4 |

Every `R` is owned. Nothing is parked.

## Scope

**In scope**

- One new committed study script and its committed output (the prior grid and the anchor probe).
- One new lab method file, `M0260`, with a new allocator id and a new params dataclass, plus a
  dedicated test module. **Six candidates**, which is the cap.
- One `lab run M0260` on the dev window, its walk-forward, control-shape and cost reads, a
  recorded verdict, a plain-language analysis, and one or more journalled insights.
- A handover, todo bookkeeping, and a memory write.

**Out of scope, and why**

- **A seventh arm.** `lab/method.py:40` sets `MAX_VARIANTS = 6` and `Method.__post_init__` raises
  outside `1..6`. The `k = 2` rung is measured by phase 1 as a **prior** and deferred to an
  `Amendment` under the same id, which costs no method id. Appendix A.
- **`lab test`. No test-window look is spent, under any outcome** (R7). Four are spent and all
  four failed.
- **Minting a `weekly-hold-frac-gotrade` preset** (R4). `sim.rules.PRESETS` does not hold it and
  `lab promote` requires membership. Both weekly arms are diagnostic forever, by design, and that
  is written into the method file rather than worked around mid-run.
- **Adding a `"quarterly"` or `"yearly"` member to `sim.rules.Cadence`.** It would move
  `_CADENCE_ORDER`, `_first_of`, every `TradeRules` canonical text and the web mirror. The slow
  rungs live in the allocator's params precisely so that they do not need this — which is also
  what keeps them promotable.
- **Editing any existing source file.** Method discovery is automatic.
- **`m0258_gate_price_band.py` and `m0072_standardised_earnings_jump.py`.** Both are frozen
  against recorded `source_sha`s. M0260 imports from M0072 and copies M0258's *shape*; it edits
  neither and does not import M0258 at all.
- **Editing `docs/backtests/2026-10-19-gate-band-cadence.py`.** It is a committed record of a
  finished study. Its relative `--store` path is corrected by writing a *new* file, never by
  changing that one.
- **The price band.** Measured three times and buried by the handover. No rung of this ladder
  carries one.
- **Creating or committing this index, the analysis document, or the four phase plan files.** The
  coordinator committed all six on `feature/gate-reading-cadence` before phase 1 starts. Phase 4
  edits this index in the worktree, where it is already tracked.

## Invariants

Every phase must hold all of these.

1. **The tree builds and `pytest -n0 engine/tests` is green at the end of every phase**, with
   `PYTHONPATH=<worktree>/engine/src`.
2. **Nothing writes to a worktree copy of `lab/lab.sqlite`.** Every `lab` command runs with
   `SEER_LAB_DB=/home/miftah/seer/lab/lab.sqlite`, and `lab stage` targets the main checkout.
3. **The research store is never rebuilt.** `SEER_RESEARCH_STORE=/home/miftah/seer/engine/.research`.
4. **Money is `trial_funding.mwr`** — what `lab show` prints as "your money earned" — in every
   artifact a human reads. `total_return` and `cagr` are never quoted as returns, and neither are
   `lab walkforward`'s fold `total_return` or the fold reader's `cagr`/`MAR`: the folds are
   reported as **which arm, won or lost**, never as a percentage. Where an *unfunded* figure is
   quoted (the SPY-alone prior grid in phase 1 has no deposits), it is labelled unfunded in the
   same sentence.
5. **No test-window look.** `lab test` is not invoked. `SEER_RESEARCH_TEST_STORE` is not read.
   Phase 3 asserts the count is still 4 after the run; phase 4 hard-stops if it is not.
6. **The method file is frozen by its pre-registration commit.** Nothing in `m0260_*.py` changes
   after `lab run M0260` has recorded a trial — not a typo, not a docstring. A later addition is
   an `Amendment`, pre-registered by its own commit. **Phase 2 makes that commit; phase 3 verifies
   it and never amends or rebases it.**
7. **No `lab` command is judged by a piped exit code.** Redirect to a file and echo `$?`; a
   `grep`/`head` owns the pipeline's status. Exit 0 = ok, 2 = the lab refused, 1 = an error.
8. **The allocator stays pure**: no clock, no randomness, no network, no file, no printing; it
   reads only bars dated on or before `data_date`, plus the published NYSE calendar.
9. **The gate anchor is never later than `data_date`.**
10. **`as_dict` renders every params field**, or two arms collide on one config digest and the
    second is refused as already run.
11. **`lookback <= 739`, and the first scored session is `1996-01-03`.** A lab allocator on an
    index-member book may widen its lookback freely up to 739 bars: `dev.candidate_window`
    (`dev.py:292-306`) checks only the candidate's FIXED symbols — `ZJUMP.symbols(BOOK)` is
    `("SPY",)` — and index members are floored separately at `MEMBERSHIP_START = 1996-01-02`. On
    the dev store SPY's 454th bar is 1994-11-14 and its 739th is 1996-01-02, so any lookback up to
    739 leaves `ready` at the membership floor and the window still opens at
    `next_session(1996-01-02) = 1996-01-03`. M0260 runs at **454**. The operative ceiling from the
    other side is the 473-session smoke fixture, which 454 clears with 19 sessions to spare.
    **The rule is "never cross 739", not "never widen"** — M0258's file forbids widening because
    its own proposed `+SCAN` would have reached 757, which genuinely would have moved its start.
    **The check is an assertion, not a comment:** every M0260 arm's first scored session must read
    `1996-01-03`, or the paired comparison with M0258's recorded rows is void and nothing in this
    method may be quoted as a reproduction.
12. **Every candidate `rationale` carries the literal lowercase phrase `dose-response`.**
    `control_shape.kind_of` (`lab/control_shape.py:191-200`, `DOSE_MARKERS`) classifies an arm by
    searching its rationale text, and D17 reads a dose-response arm as its own control and never
    shape-checks it. An arm without the marker is invisible to the ladder's classification — and
    the method file is frozen the instant a trial is recorded, so this is checked before the
    pre-registration commit, never after.
13. **All six arms, or none.** `MAX_VARIANTS = 6` is enforced at import. The ladder is
    `M-NATIVE`, `M-G3`, `M-G6`, `M-G12`, `W-NATIVE`, `W-G1` and nothing else.

## Phases

| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID | Card |
|---|-------|-----------|---------|-------|-----------|------------|------|--------|------|
| 1 | Measure the prior and prove the anchor | R6 | `docs/backtests` | 2 | — | NORMAL | `.workflows/plan/gate-reading-cadence/phase-1.md` | P1-ROOT-Q7MF (done 2026-10-19) | — |
| 2 | The method file, its dedicated tests, and the pre-registration commit | R1, R3, R4, R6, R7 | `engine/src/seer_engine/lab/methods`, `engine/tests` | 2 | 1 | HARD | `.workflows/plan/gate-reading-cadence/phase-2.md` | P1-ROOT-V3KD (done 2026-10-19) | — |
| 3 | Run and record the verdict | R1, R2, R5, R7 | `lab/` (main checkout) | 2 | 2 | HARD | `.workflows/plan/gate-reading-cadence/phase-3.md` | P1-ROOT-N8PZ | — |
| 4 | Handover, bookkeeping and the standing correction | R4, R5, R7 | `docs/plans`, `.workflows` | 3 | 3 | NORMAL | `.workflows/plan/gate-reading-cadence/phase-4.md` | P1-ROOT-C5RB | — |

### Phase 1 — Measure the prior and prove the anchor
**Satisfies:** R6
**Owns:** `docs/backtests/2026-10-19-gate-reading-cadence.py` and its committed output
`docs/backtests/2026-10-19-gate-reading-cadence.md`. A standalone study, sharing no code with the
simulator, that (a) runs the SPY-alone gate at reading intervals of 1, 2, 3, 6 and 12 months
against the native monthly and weekly readings, as the feasibility table and prior the method file
must quote; and (b) probes the real dev store to prove the month-end anchor always resolves inside
the bars on hand and always has at least 200 SPY bars behind it, for every rung, on every decision
session of the dev window. It takes an **absolute `--store`** and runs from the worktree —
deliberately unlike the M0258 precedent.
**Does not touch:** anything under `engine/src`, anything under `engine/tests`, the lab database
(not even a read — a read migrates the file on connect), this index, the analysis document, or the
phase plan files.
**Exit criteria:** both files committed; the grid reproduces `M0084-MONTHLY` and `M0084-WEEKLY` in
sign and magnitude the way M0258's grid did; the probe reports zero fallbacks, zero late anchors
and a minimum SPY bar count ≥ 200 at every rung, or reports the exact sessions where it does not;
the monthly `k = 1` identity and the weekly decomposition identity both report zero disagreements;
the committed `.md` says in one sentence that **`k = 2` is measured here as a prior only and is
deferred to an `Amendment`**, speaks of **six** arms, and carries the `min bars` measurement as
what makes phase 2's widened lookback safe, stating the ceiling as `lookback <= 739`; the word
**unfunded** sits beside every return it quotes.

### Phase 2 — The method file, its dedicated tests, and the pre-registration commit
**Satisfies:** R1, R3, R4, R6, R7
**Owns:** `engine/src/seer_engine/lab/methods/m0260_gate_reading_cadence.py`,
`engine/tests/test_lab_m0260_cadence.py`, **and the pre-registration commit carrying exactly those
two files.**
**Does not touch:** `m0258_gate_price_band.py`, `m0072_standardised_earnings_jump.py`,
`m0063_earnings_day_jump.py`, `sim/rules.py`, `test_lab_m0258_band.py` — all frozen or
out of scope. It does not run `lab run`, and it writes nothing to the lab.
**Exit criteria:** `pytest -n0 engine/tests` green with DB tests not skipped; `ruff check engine`
clean; the file declares **exactly six** candidates — `M0260-M-NATIVE`, `M0260-M-G3`,
`M0260-M-G6`, `M0260-M-G12`, `M0260-W-NATIVE`, `M0260-W-G1` — with six distinct config digests;
**all six rationales contain the literal lowercase `dose-response`** (invariant 12, checked
mechanically); `lookback` is **454**, the same at every rung, and the first scored session reads
**`1996-01-03`** (invariant 11); the docstring's prior-grid table has been diffed against phase 1's
committed `.md` and **phase 1's numbers taken on any disagreement**, with every figure in it
labelled UNFUNDED; the docstring states the confound, the decomposition, the promotability table,
the M0072-not-M0197 argument, the lookback measurement, the pre-registered prediction with signs
and sizes, the walk-forward MAR caution and the no-test-look rule in its own words; one commit
exists containing exactly those two files, unamended.

### Phase 3 — Run and record the verdict
**Satisfies:** R1, R2, R5, R7
**Owns:** `lab run M0260`, `lab walkforward M0260`, `lab control M0260`, `lab costs`, `lab note`,
`lab insight`, `lab stage`, the result commit in the main checkout, and the capture directory
`/tmp/m0260` (copied to `/home/miftah/.cache/seer-captures-m0260` before close-out, because `/tmp`
does not survive a reboot).
**Does not touch:** the pre-registration commit (**phase 2 made it**; this phase verifies it and
never amends or rebases it), the method file or its test module (frozen), `lab test` (never
invoked), the test-window store, this index, the handover, `.workflows/todos.md`.
**Exit criteria:** **six** trials recorded under M0260 with six distinct config digests; `trials.n`
read back, never assumed; `methods.source_sha` equals the committed method file's sha256 and every
`trials.git_sha` equals phase 2's pre-registration commit; the reproduction arms checked against
`M0258-M-B0` and `M0258-W-B0` on mwr, worst fall, trades, turnover, exposure and PF — or the drift
recorded as the method's headline finding; the decomposition computed on both axes with
`(A−C) + (C−B) = (A−B)` to machine precision; the ladder reported arm by arm with an explicit
sentence saying whether it is humped, monotone or flat and where it turns; **the folds reported arm
by arm** with the MAR caveat stated and no fold percentage quoted as the owner's money; `lab
control` read and its verdict recorded; a verdict and a plain-language analysis recorded, quoting
`trial_funding.mwr` only; at least one insight journalled; `lab stage` run and `lab.sqlite` +
`web/data/lab.json` committed from the main checkout **with no pathspec**; test-window trial count
still **4**.

### Phase 4 — Handover, bookkeeping and the standing correction
**Satisfies:** R4, R5, R7
**Owns:** `docs/plans/HANDOVER_20261019-the-gate-reading-cadence.md`, `.workflows/todos.md` (root
only), the `**Status:**` tick on this index, a memory file under
`/home/miftah/.claude/projects/-home-miftah-seer/memory/` with its `MEMORY.md` pointer, the merge
of `feature/gate-reading-cadence` to `main`, and the push.
**Does not touch:** the lab database and `web/data/lab.json` (phase 3 closed them in the main
checkout; the branch never carried them), the method file, the study script,
`engine/.workflows/todos.md`.
**Exit criteria:** handover written in the house style with the lab-state table (**836** dev
trials, test looks still 4), the **six**-row ladder with no `M-G2` row, the decomposition with its
arithmetic shown, an explicit paragraph naming the **four** monthly arms as promotable and both
weekly arms as never promotable, a sentence on why the ladder is six arms and where the two-month
rung went, a sentence on the widened lookback and the unchanged `1996-01-03` start, the dead list
carried forward and extended and the leftovers list carried forward and re-prioritised, and **no
surviving `«` placeholder**; every number traced to a named `/tmp/m0260` capture file; at least one
memory file written with its `MEMORY.md` line, and the parent memory superseded in place rather
than duplicated; this index set to `**Status:** complete` with phase 4's TaskID filled; branch
merged to `main` and pushed, with no `lab.sqlite` or `lab.json` in the merge's diffstat, no
rebase, and the worktree and branch deleted.

## Reconciliation Log

| # | Conflict | Class | Phases | Resolution |
|---|---|---|---|---|
| C1 | Appendix A listed **seven arms**, but `lab/method.py:40` sets `MAX_VARIANTS = 6` and `Method.__post_init__` raises outside `1..6`. Phase 2 had already dropped `M0260-M-G2`; phases 1, 3, 4 and this index had not | Contract drift / duplicate-count | 1, 2, 3, 4 | Propagated **six** everywhere. Appendix A rewritten to six rows with the `MAX_VARIANTS` note and the `k = 2` amendment handoff; this index's phase-3 exit criteria "seven trials" → six; phase 3's goal, Interface Contract (`#831..#836`), capture table, arm dump (`candidates: 6`, four monthly), `lab run` progress lines (`[n/6]`), digest count, `lab costs` ladder list, analysis sections, commit message, projections (6 × one arm ≈ 40 s) and exit criteria all moved to six; phase 4's lab-state table (**836**), ladder table (`M-G2` row deleted), memory ladder table, promotability paragraph ("four monthly arms"), todos result lines and exit criteria 4 and 7 all moved to six/four; phase 1's `.md` reading section moved to "six arms" and told to say the `k = 2` rung is a prior only |
| C2 | The original instruction "`lookback` = `ZJUMP.lookback(p.book)` with nothing added (253)" is **wrong** — the anchor gap reaches 253 sessions at `k = 12`, so `trend_on` needs 453 bars and three of four slow rungs fail `assert_p4_identity`'s lookback cut. Phase 2 measured it and set 454; the index still carried the old instruction | Contract drift (instruction vs measured code) | 2, 3 | The instruction is **struck**. Added as **invariant 11** and Decision D2: the rule is `lookback <= 739`, with `1996-01-03` as the assertion. Phase 2's D-B now states the rule in those words, says the brief's instruction was measured and is wrong, and carries it into **exit criterion 9**. Phase 3's step 3 gained a third question (`row.start` must read `1996-01-03`), its Requires line names 454, and its probe expectations now assert the start before the six figures |
| C3 | Phase 3 writes captures to `/tmp/m0260/`; phase 4 read them from `$HOME/.cache/seer-captures/gate-reading-cadence/` under seven invented filenames | File collision / unmet assumption | 3, 4 | **Phase 3's paths win** — it is the phase that creates them. Phase 4's Step 1 table rewritten against phase 3's real filenames, each number attributed to the file it comes from (`04-show.txt`, `06-ladder.tsv`, `06-decomp.txt`, `07-walkforward.txt`, `08-folds.txt`, `09-control.txt`, `10-costs-*.txt`, `16-final.txt`, `05-verify.txt`, `02-probe*.txt`, `11-note.txt`, `12-insight-*.txt`, `13-idea.txt`, `01-prereg.txt`, `15-commit.txt`), and every in-body `capture NN` reference replaced with the filename. Phase 3's capture table gained the two rows it was missing (`00-arms.txt`, `02-probe-w.txt`). **`/tmp` does not survive a reboot**, so phase 3 now copies the directory to `/home/miftah/.cache/seer-captures-m0260` before close-out and phase 4 tries that path second and a read-only lab re-read third — with the note that `08-folds.txt` cannot be re-derived by any `lab` command, because `lab walkforward` never prints which arm a fold picked |
| C4 | D17 classifies an arm by finding the literal `dose-response` in its `rationale` (`control_shape.py:191-200`, `kind_of`). Phase 2's four monthly rungs carried it; **`W-NATIVE` and `W-G1` did not**, so a six-arm ladder would have been read as a four-arm one | Gap (unowned behaviour) | 2, 3 | Both weekly rationales rewritten so the phrase reads as English inside sentences that already existed: *"the fast end of the same dose-response ladder"* and *"the decomposition arm of the dose-response ladder"*. Phase 2 gained decision **D-B2** explaining the mechanism and confirming no `DRAW_MARKERS`/`ABLATION_MARKERS`/`IDEA_MARKERS` phrase is tripped, plus **exit criterion 8** checking all six mechanically. Added as **invariant 12**. Phase 3's pre-commit `dose=` check kept and tightened to "every one of the six rows"; its step-9 expectation moved from "four to seven rows" to **six** |
| C5 | Phase 1 and phase 2 independently measured the same SPY-alone prior grid (+3.58 vs +3.57) and both wrote it down | Duplicate work (deliberate) | 1, 2 | **Kept deliberately duplicated** — the two implementations are independent and agreement to rounding is the evidence. But ownership is now explicit: **phase 1's committed `.md` is the citable record and wins any disagreement.** Phase 2's Requires already said so; it is now also **exit criterion 10**, with the instruction to re-commit before phase 3 runs, and with every figure labelled UNFUNDED in the same sentence (invariant 4) |
| C6 | The brief's framing ("a best speed must exist between weekly and yearly") implies an interior optimum; phase 1's measured prior falls above monthly and M0258 measured the fast side at −7.01 pts/yr. A pre-registration predicting against its own prior is worthless | Contract drift (framing vs prior) | 2 | **Verified** phase 2's prediction is already grounded, signed, sized and honest — prediction 1 says the turn is **at** `k = 1` and names that outcome as "the lab has been running the best available cadence by accident". **Sharpened, not weakened:** both the docstring and the `hypothesis` string now state the shape outright — *the axis turns at monthly and falls away on both sides* — cite M0258's fast-side measurement, and name the single falsifier (one slow rung beating `M-NATIVE` on money). The index's **Why** carries the correction so the two cannot drift apart again. Decision D4 |
| C7 | The repo's last six commits use `Claude Opus 5 (1M context)`; this session's attribution instruction specifies the plain form and overrides earlier guidance | Convention conflict | 1, 2, 3, 4 | **Audited: already correct in all four plans.** Every commit message in phases 1, 2, 3 and 4 (including phase 4's three message files) already ends with exactly `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`. No edit needed; recorded as Decision D5 so no phase "fixes" it toward the repo's older trailer. CLAUDE.md's "follow the existing style" governs subject lines (`lab: M00NN pre-registered — …`), not trailers |
| C8 | This index and the analysis document were untracked at base; phase 4 carried a three-branch "where does the index live" fork, and it was ambiguous which phase committed them | Unowned artifact / irreversible-looking fork | 1, 4 | **The coordinator commits the index, the analysis document and all four phase plan files on `feature/gate-reading-cadence` before phase 1 starts.** Phase 1's "Leaves alone" now names all six and forbids `git add`ing them. Phase 4's three-branch fork collapsed to one line: the index is a **tracked file in this worktree**, edited here and carried by the close-out commit and the merge; the Requires block states it; the `git add` of the index in Step 8b is now unconditional. Added to Scope's out-of-scope list |
| C9 | **Both phase 2 and phase 3 claimed authorship of the pre-registration commit.** Phase 2's step 3 committed the two files; phase 3's Requires said they must be "uncommitted" and its step 2 committed them again, with a different message that said "Seven arms" | Duplicate work / ordering | 2, 3 | **Phase 2 owns it** (rule 3: earlier phase; and on the ladder, phase 2's exit criterion 7 speaks while phase 3's exit criteria never claimed it). Phase 3's step 2 rewritten from *make the commit* to *verify the commit*: `git log -1 --stat` into `01-prereg.txt`, assert the subject and the two-file diffstat, stop if absent. Phase 3's Depends-on, Requires, Files table, step-1 heading and failure-branch A wording all moved to "already committed by phase 2". Phase 2's Interface Contract now lists the commit as something it creates and owns, and its step-3 Impact says phase 3 verifies rather than makes it |
| C10 | Phase 3's failure branch C and phase 4's environment notes both said the cadence study "reads a relative store path, so run it from the main checkout" — **false**: phase 1 deliberately gave it an absolute `--store` and runs it from the worktree | Contract drift (stale inherited fact) | 1, 3, 4 | Both corrected to the real invocation (`PYTHONPATH=<worktree>/engine/src … --store /home/miftah/seer/engine/.research`, from the worktree), with the reason stated — it is a deliberate correction of the M0258 precedent, and `docs/backtests/2026-10-19-gate-band-cadence.py` is a committed record that must **not** be edited to match. Phase 3's block was also missing `PYTHONPATH` entirely, which would have failed on import |
| C11 | **Invariant 4 breach latent in phase 3's fold reader.** `08-folds.txt` prints `total_return` per fold and `cagr`/`MAR` per arm, and phase 3 told the implementer to put the fold reading "into the analysis verbatim" | Gap (invariant not enforced where it bites) | 3, 4 | Phase 3's step 8 gained an explicit guard: those columns are curve-shape figures on a deposit-matched curve and **are not the owner's money**; folds are reported as *which arm, won or lost*, never as a percentage, and every percentage in the analysis stays on `trial_funding.mwr`. Added to phase 3's exit criterion 7 and to phase 4's handover fold table. Invariant 4 widened to name the walk-forward columns |
| C12 | Phase 4 addressed the index by line number (`:9` Status, `:103` the phase-4 TaskID row) and expected `**Status:** draft` | Contract drift (the reconciler rewrites the file) | 4 | All line-number references to this index removed and replaced with content matches; the expected status moved from `draft` to **`planned`**, which is what this rewrite sets. Phase 4's Files table says explicitly that line numbers are not quoted for this file |
| C13 | Phase 4's **Satisfies** line was R4, R5, while its steps carry an R7 hard stop (test looks > 4 ⇒ stop) and an R7 exit criterion | Requirement creep (under-claimed) | 4 | R7 added to phase 4's **Satisfies** line, its todos entry and this index's Requirements table and phase table. The work was already there and already scoped — this is the Satisfies line catching up to the steps, not a step moving |

**Checked and clean:** no deleted-then-used symbol (all four phases declare `Deletes: none` and
`Renames: none`); no `Requires` unmet by an earlier phase; every dependency points backward
(1 → 2 → 3 → 4); no file region owned by two phases after C9; every analysis **Impact Point**
owned (1–2 phase 1, 3–4 phase 2, 5 phase 3, 6–7 phase 4); every **Reference List** entry is a
read-only import or call, so nothing in the set can break the tree; no phase leaves the build red —
phases 1 and 4 touch no source, phase 2's two files are additive and run the full suite before its
commit, phase 3 writes no source at all; and **nothing in any phase spends a test-window look** —
`lab test` is never invoked, `SEER_RESEARCH_TEST_STORE` is never read, `lab walkforward` slices
recorded dev curves, and `lab costs` re-runs on the dev store.

**One stale reference left deliberately unedited:** the analysis document
(`docs/analyzer/20261019-152028-SSYJ_code_analyzer.md`) says "seven candidates" at Impact Point 3.
The reconciler edits plans, not the analyzer's record. **The plan files prescribe; that document
describes** — and it says so itself in its last line. Any phase that reads it should take Appendix
A here as binding.

## Decisions

| # | The fork | Chosen | Rung |
|---|---|---|---|
| D1 | Seven arms (the brief's Appendix A) vs six (`MAX_VARIANTS = 6`) | **Six.** `M-NATIVE`, `M-G3`, `M-G6`, `M-G12`, `W-NATIVE`, `W-G1`. `M0260-M-G2` is dropped to a free `Amendment`, and phase 1 still measures `k = 2` as a prior so the amendment has evidence behind it if the ladder comes back humped | **A measured fact in the code**, which outranks the original instruction. `engine/src/seer_engine/lab/method.py:40` sets `MAX_VARIANTS = 6` and `Method.__post_init__` raises outside `1..6` — a seventh arm would fail at import, not at review |
| D2 | `lookback = 253` ("nothing added", copying M0258) vs `lookback = 454` | **454.** The binding rule is `lookback <= 739`, never 253 dogmatically. The check is that the first scored session reads `1996-01-03` | **A measured fact in the code**, which outranks the original instruction. At 253 three of the four ladder rungs fail `allocatorkit.assert_p4_identity`'s lookback cut outright. `dev.candidate_window` (`dev.py:292-306`) checks only the candidate's fixed symbols (`("SPY",)`) and floors index members at `MEMBERSHIP_START`; SPY's 454th dev-store bar is 1994-11-14 and its 739th is 1996-01-02. M0258's "never widen" was correct **for M0258**, whose `+SCAN` would have reached 757 |
| D3 | Leave the two weekly rationales as written vs put `dose-response` in all six | **All six carry it**, phrased as English inside the sentences that were already there | **A measured fact in the code**, which outranks the drafters' prose choices. `control_shape.kind_of` searches the lowercased `rationale` for `DOSE_MARKERS` (`control_shape.py:191-200`); without the marker D17 does not read the arm as part of the ladder, and the method file is unfixable once a trial lands |
| D4 | The brief's "a best speed must exist between weekly and yearly" (an interior optimum) vs the prior's "the turn is at or near the fastest rung" | **The axis turns at monthly and falls away on both sides.** The pre-registered prediction commits to that shape, names the falsifier (one slow rung beating `M-NATIVE` on money), and states plainly that it coming true means the lab has been running the best cadence by accident | **The plans' code blocks** — phase 1's measured SPY-alone grid (9.08 → 8.56 → 6.71 → 8.39 → 7.06, fall deepening to 25.9%) plus M0258's recorded −7.01 pts/yr on the fast side — over the index's **Why** prose. A pre-registration may not predict against the only prior that exists; the losing framing is struck from the plan and corrected in **Why** so the two cannot drift apart |
| D5 | `Co-Authored-By: Claude Opus 5 (1M context)` (the repo's last six commits) vs `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>` (this session's attribution instruction) | **The plain form**, in all eight commit messages across the four phases. Audited: all four plans were already correct, so nothing was edited and nothing should be "fixed" toward the older trailer | **The user's raw input** — the session attribution instruction states the plain form and explicitly overrides earlier attribution guidance. CLAUDE.md's "commit messages follow the existing style" governs **subject lines** (`lab: M00NN pre-registered — …`), which every phase keeps, not trailers |
| D6 | Phase 2 makes the pre-registration commit vs phase 3 does | **Phase 2.** Phase 3 verifies it (`git log -1 --stat`, the two-file diffstat, an empty porcelain) and runs against it; it never amends or rebases it | **The phases' exit criteria.** Phase 2's exit criterion 7 requires the commit to exist unamended and its rollback section is written around it; phase 3's eleven exit criteria never claimed it. Reinforced by the earlier-phase-owns rule and by the fact that an unamendable commit belongs with the phase that can still fix the file |
| D7 | `$HOME/.cache/seer-captures/gate-reading-cadence/` (phase 4's assumption) vs `/tmp/m0260/` (phase 3's actual) | **`/tmp/m0260/`, with phase 3's own filenames**, plus a copy to `/home/miftah/.cache/seer-captures-m0260` before close-out because `/tmp` dies on reboot | **The plans' code blocks** — phase 3's shell blocks write those paths and names; phase 4 only assumed them. The phase that creates an artifact names it |
| D8 | Which phase creates and commits this index and the analysis document | **Neither — the coordinator commits both, plus all four phase plan files, on `feature/gate-reading-cadence` before phase 1 starts.** Phase 4 edits this index in the worktree as a tracked file and the close-out commit carries it | **The user's raw input**, which states it directly. This overrides the standing convention that an orchestration `PLAN.md` lives on `main` and is ticked in the main checkout; phase 4 records the deviation rather than branching on it |
| D9 | Report the walk-forward folds with their returns vs with won/lost only | **Won or lost, by arm.** No fold `total_return`, `cagr` or `MAR` figure is quoted as a return on the owner's money, in the analysis or the handover | **A stated invariant** — invariant 4. The fold reader's columns are curve-shape figures on a deposit-matched curve, which is precisely what invariant 4 exists to keep out of a sentence about the owner's money |
| D10 | Let phase 1 and phase 2 each own their measurement of the prior grid vs give one of them the record | **Both measure it independently — that is the evidence — but phase 1's committed `.md` is the citable record and wins any disagreement**, and phase 2 must diff and re-commit before phase 3 runs | **The phases' exit criteria.** Phase 1 owns `docs/backtests/2026-10-19-gate-reading-cadence.md` by its exit criteria; phase 2's file only quotes it. Agreement to rounding (+3.58/+0.59/+2.99 against +3.57/+0.59/+2.98) is worth keeping precisely because neither implementation is the other |

## Open Questions

*(none — every fork above was decided and recorded under Decisions, and every requirement id is
owned by at least one phase)*

## Rollback

Per phase: `git revert` the phase's commit. Phases 1, 2 and 4 are additive files only.

Phase 3 is the one that is not reversible by git: `lab.sqlite` is append-only and
trigger-enforced, so a recorded trial stays recorded. The rollback for a mis-run is the lab's own:
leave the trials, record a correcting `lab note` and a `lab insight`, and spend no second method
id. **This is a property of the lab, not a defect in the plan**, and it is why the method file is
frozen before the run rather than after — and why phase 3 runs its reproduction probe *outside* the
lab, at step 3, where a stop still costs nothing.

Whole set: delete the worktree and the branch; nothing outside `lab.sqlite` and `web/data/lab.json`
has left the branch until phase 4 merges.

## Next

Execute the phases one at a time, starting at phase 1:

    /implement -f docs/plans/GATE_READING_CADENCE_PLAN.md --phase 1

Or run the whole set as a swarm — a session per phase. **The phases are strictly sequential**
(1 → 2 → 3 → 4), so nothing here runs concurrently; the swarm buys resumability and bookkeeping,
not parallelism:

    /analyze-orchestrator -f docs/plans/GATE_READING_CADENCE_PLAN.md

---

## Appendix A — the arm table (binding on phase 2)

**Six arms. Not seven.** `engine/src/seer_engine/lab/method.py:40` sets `MAX_VARIANTS = 6`, and
`Method.__post_init__` raises on anything outside `1..6`:

    if not isinstance(self.candidates, tuple) or not 1 <= len(self.candidates) <= MAX_VARIANTS:
        raise ValueError(f"{self.id}: 1..{MAX_VARIANTS} candidates, got {len(self.candidates)}")

`lab run` executes `method.candidates` only, so a seventh arm is not a review question — it fails
at import.

All six hold `M0072-Z2-RAWRANK`'s book verbatim — M0063's standardised earnings-day jump kept at
two of the stock's own daily swings and ranked by the raw jump, F4's five-dollar and twenty-million
screen, 20 slots at 5%, SPY in the empty ones, a 60-session hold, fractional at Gotrade's real fees
on the owner's monthly top-ups. **Only the rule set's cadence and the gate's reading interval
move.** `lookback` is **454** at every rung (invariant 11), so no arm's scored window differs from
another's.

| arm | rule set | `gate_months` | what it is | promotable |
|---|---|---|---|---|
| `M0260-M-NATIVE` | `monthly-hold-frac-gotrade` | `None` | the ladder's fastest monthly rung; must reproduce `M0258-M-B0` = `M0072-Z2-RAWRANK` | **yes** |
| `M0260-M-G3` | `monthly-hold-frac-gotrade` | `3` | quarterly — Mar/Jun/Sep/Dec | **yes** |
| `M0260-M-G6` | `monthly-hold-frac-gotrade` | `6` | half-yearly — Jun/Dec | **yes** |
| `M0260-M-G12` | `monthly-hold-frac-gotrade` | `12` | yearly, December only — "barely a gate at all" | **yes** |
| `M0260-W-NATIVE` | `weekly-hold-frac-gotrade` | `None` | the fast end of the axis; must reproduce `M0258-W-B0` | **never** |
| `M0260-W-G1` | `weekly-hold-frac-gotrade` | `1` | **the decomposition arm**: weekly re-pick, monthly gate | **never** |

**Every one of the six rationales carries the literal phrase `dose-response`** (invariant 12).

**The two rungs that are not arms, and why neither costs a trial:**

- **The anchored `k = 1` rung on a monthly book is an identity, not an arm.** A monthly book's
  `data_date` is always a calendar month end, so it resolves to `data_date` itself and is
  identical to `M-NATIVE`. Phase 2 asserts that in the test module and phase 1's grid shows it
  measured (its monthly native and monthly `k = 1` rows agree to the digit).
- **`k = 2` is a prior, deferred to an `Amendment`.** It is the seventh arm `MAX_VARIANTS` refuses.
  Phase 1 still measures it on SPY alone (8.56% / −19.7% unfunded), so if phase 3's ladder comes
  back humped between `M-NATIVE` and `M-G3` the follow-up is an `Amendment` block committed on its
  own and run with `lab run --amend M0260` — **which costs no method id.** Phase 3 must **not** add
  it by editing `candidates`: that moves the file's sha after the run and trips
  `test_a_method_that_ran_is_frozen_to_its_latest_recorded_sha`.

The monthly ladder is therefore a **four-rung** dose-response curve: native, 3, 6, 12. Say so in
the analysis and the handover, or a reader takes a four-rung ladder for a five-rung one with a hole
in it.

## Appendix B — the confound, and exactly how far it is broken

**The two axes are the same event as the chassis stands.** `book_runner.run_book` calls the
allocator only on decision sessions, with `data_date = prev_session(S)`, and the gate is read
inside that call. So the rule set's `cadence` sets both how often the gate is read and how often
the book re-picks. M0258's +7.01 pts/yr is the sum of the two and names neither.

**Slower than the re-pick: separable, and promotable.** Nothing stops the allocator reading the
gate at a date earlier than `data_date`. Anchoring it to a month-end grid leaves `TradeRules`
untouched, so every slow arm still runs on `monthly-hold-frac-gotrade`, which **is** in
`sim.rules.PRESETS`.

**Faster than the re-pick: not separable, by construction.** A monthly book cannot act on a gate
reading taken between its rank sessions. Making it act weekly *is* a rule-set change, which also
re-picks weekly. **The sub-monthly rung of this ladder is inseparably confounded on this chassis,
and that is a property of the simulator rather than a gap in the design.** It is stated in the
method file in those words.

**The confound is decomposed rather than papered over.** With A = `M-NATIVE`, B = `W-NATIVE`,
C = `W-G1`:

    (A - B)   =   (A - C)                +   (C - B)
     +7.01         re-pick frequency          gate reading cadence
     measured      (gate held monthly)        (re-pick held weekly)

and the first bracket is clean because at a weekly rank session in month *M*, arm C's anchor is
the newest month end on or before its `data_date` — the **same month-end session** arm A read at
its own rank session that month. Arm C literally reuses arm A's gate reading, so `A − C` moves
re-pick frequency and nothing else. Phase 1 proved that session by session on the real dev store
(1032 of 1032 weekly decision sessions agree); phase 2 asserts it in the test module; phase 3
reports the split as the method's headline alongside the ladder, on both money and worst fall,
with a sum residual at machine epsilon.

## Appendix C — the gate anchor

    month_index(d) = (d.year - 1970) * 12 + (d.month - 1)

    anchor(h, data_date, k) = the newest bar a of h with a <= data_date such that
                                (i)  a is the last session of its calendar month, and
                                (ii) month_index(a) % k == k - 1
                              falling back to data_date when no such bar is on hand

Phase `k - 1` makes the grid calendar-natural: `k=1` every month end, `k=2` Feb/Apr/…/Dec, `k=3`
Mar/Jun/Sep/Dec (calendar quarters), `k=6` Jun/Dec, `k=12` December only.

Condition (i) is decidable point-in-time: for an interior bar *j* it is
`month(dates[j]) != month(dates[j+1])`; for the newest bar on hand it is the calendar question
`dates.next_session(d).month != d.month`, which reads the published NYSE calendar and no price.
A calendar read inside a lab allocator is established practice (`m0052_turn_of_month_tilt.py`,
`m0120_calendar_clock.py`, and seven others), and `allocatorkit.assert_no_lookahead` perturbs
*bars*, not the calendar.

The anchor is never later than `data_date`, so every anchored arm is strictly safer on look-ahead
than the native reading the lab already runs.

**The fallback never fires inside the dev window.** Measured on the dev store's whole SPY tape
(5722 bars, 1993-01-29 → 2015-10-16): `k = 12` is unresolvable on the first 233 sessions only,
every one of them before 1993-12-31; `k = 6` on the first 105, `k = 3` on the first 42, `k = 2` on
the first 19, `k = 1` on none. The dev window opens on 1996-01-03, more than two years later. On
the 473-session smoke fixture the fallback *does* fire for `k = 12` and `k = 6`, and the test
module asserts its exact shape there rather than pretending it cannot happen.

## Appendix D — the lookback, and the 739-bar ceiling

Reading a 200-bar average **at** an anchor up to `k` months old needs `200 + gap` bars on hand.
Measured on the dev store's whole SPY tape, the worst anchor gap is 22 sessions at `k = 1`, 43 at
`k = 2`, 63 at `k = 3`, 127 at `k = 6` and **253 at `k = 12`** (1995-12-29 → 1996-12-30). So 453
bars is the true requirement; `MAX_ANCHOR_GAP = 254` carries one session of margin and
`lookback = max(ZJUMP.lookback(book), 200 + 254) = 454`, **the same at every rung**.

| lookback | SPY's nth dev-store bar | first scored session |
|---|---|---|
| 253 (M0072's) | 1994-01-27 | 1996-01-03 |
| **454 (M0260's)** | 1994-11-14 | **1996-01-03** |
| 739 (the ceiling) | 1996-01-02 | 1996-01-03 |
| 740 | 1996-01-03 | **1996-01-04 — the window finally moves** |
| 757 (M0258's refused `+SCAN`) | 1996-01-26 | 1996-01-29 |

`dev.candidate_window` sets `ready = MEMBERSHIP_START` (1996-01-02, because this book reads index
members) and raises it to the `lookback`-th bar date of each **fixed** symbol — and
`ZJUMP.symbols(BOOK)` is `("SPY",)`. So any lookback up to 739 leaves `ready` at the membership
floor. **The rule is "never cross 739", not "never widen"** (invariant 11). M0258's file forbids
widening because *its* proposed addition reached 757, which genuinely would have moved its start
and turned its `band = 0` arm from a reproduction into an approximation.

The operative ceiling from the other side is the **473-session smoke fixture**
(`labkit.SMOKE_FIRST = 2013-12-02`): `candidate_window` on the smoke market refuses any lookback
above 473, and 454 clears it with 19 sessions to spare. Every rung still runs a smoke window to
`DEV_END`.

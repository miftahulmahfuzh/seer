# Plan: guard the arm that gets the money, not the arm that gets reported

**Slug:** fold-selector-audit
**Date:** 2026-10-20 16:27:54
**Analysis:** `docs/analyzer/20261020-162754-F0LD_code_analyzer.md`
**Worktree:** none — written against `main` @ `89b4220`
**Branch:** `main`
**Phases:** 3
**Status:** planned — **not launched.** The brief asked for an audit and a recommendation, not an
implementation; phases 2 and 3 change what the lab will promote and when it fires a buy signal,
which is the owner's call. Launch with the command at the bottom when he says so.
**Coordinator:** —

---

## Why

The audit asked whether the hard gate's walk-forward fold selector measures a method's idea or its
control arm. **The answer is (B): the selector is working as designed.** The argument is in
*Decisions* below. But the same question, asked of the clause that actually spends the counted
look and the owner's money, has the opposite answer — and nothing guards it.

From the brief, preserved because it is the specification for what may and may not change:

> THE RULE THAT MUST NOT BE BENT: this is an audit of whether the gate measures what it CLAIMS,
> not a search for a way round it. The gate exists because 4 of 4 test looks failed on beats SPY
> TR. If the selector is sound, the finding is that 45 methods are CORRECTLY refused and that 2
> of 4 should stop being read as nearly there — which is worth knowing on its own. Any change to
> engine/src/seer_engine/lab/hardgate.py must be argued in the commit message. There is no
> override flag and you must not add one.

Every change below makes the lab **stricter about promotion**. No phase adds an override, a flag
or an env var, and no phase makes a refused method promotable — `hardgate.check()` has no era
clause, so phase 3 cannot move a promotion either way.

**One carve-out, measured, not a tightening:** phase 3 corrects the buy signal, which is a
recommendation to *buy price data*, not a promotion. Today it fires on `{M0092, M0197, M0243,
M0258}`; after the fix it fires on `{M0072, M0092, M0258}`. M0197 and M0243 stop — both were
firing on an arm that is not the one that would be promoted, whose promoted arm has a negative
era edge — and **M0072 starts**, because the same bug was running the other way on it. A winner
and two losers, not a one-way clamp. The two methods the audit found would flip under (A)
— M0174 and M0178 — stay refused, because (A) is not adopted.

## Requirements

| ID | What the user asked for | Phases |
|---|---|---|
| R1 | Count of the 45 with a control chosen in ≥1 fold | delivered in the analysis (24 of 44, 55%) |
| R2 | Flipped verdicts, listed, with era edges | delivered in the analysis (2: M0174 −0.6%, M0178 −2.1%) |
| R3 | A recommendation on `hardgate.py` with the argument | this plan — *Decisions*, and phases 1-2 |
| R4 | Resolve the M0179 era-edge thread | delivered in the analysis (F5); phase 3 fixes it |
| R5 | Report the verdict to `sera-20261020-1417` | done by the analysing session |

## Scope

**In scope:** the role of the variant `lab promote` pre-registers; the arm the `2009-15 edge`
column and the buy signal's 4th condition are measured on; widening `control_shape`'s role
vocabulary so both can be asked.

**Out of scope, deliberately:**
- `hardgate._dev_curves` and `walkforward.pick` — the fold selector's candidate set. Unchanged.
  See *Decisions* row 1.
- `store.best_dev_eligible` — unchanged. The fix belongs in the gate, which is where the lab's
  refusals are argued and where the refusal text can explain itself. Changing the ranking would
  silently move which variant every historical record refers to.
- Any recorded trial, verdict, digest or lab row. Nothing is re-run and no method id is spent.

## Invariants

1. The engine suite is green at the end of every phase (`lab stage` **then** `pytest`).
2. **Test-window looks stay at 4.** No phase runs `lab test` or `lab promote`.
3. No phase spends a method id, writes a trial, or moves a status.
4. No override flag, env var or bypass is added to `hardgate.py`. The gate's own refusal text
   invites an argued change in git and offers nothing else; that stays true.
5. No phase makes a currently-refused method promotable. Phase 2 refuses *more*; phase 3 moves
   no promotion at all. **This invariant is about promotion, not about the buy signal** — phase 3
   deliberately changes which methods the signal fires on (see *Why*), and that is a corrected
   measurement, not a loosened gate.
6. `control_shape`'s convention is honoured: every marker added carries its measured hit count
   over the lab's method files, because *"a constant with no measurement behind it is a guess,
   and this lab writes down where its numbers came from."*

## Phases

| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID |
|---|-------|-----------|---------|-------|-----------|------------|------|--------|
| 1 | Widen `control_shape`'s role vocabulary | R3 | `lab/` | 2 | — | NORMAL | `.workflows/plan/fold-selector-audit/phase-1.md` | P2-ENG-D9KX |
| 2 | D18: refuse a promotion whose pre-registered variant is a control | R3 | `lab/` | 2 | 1 | HARD | `.workflows/plan/fold-selector-audit/phase-2.md` | P2-ENG-Q4LP |
| 3 | Measure the era edge on the promoted variant | R4 | `lab/`, `commands/` | 3 | 1 | NORMAL | `.workflows/plan/fold-selector-audit/phase-3.md` | P2-ENG-X7WG |

### Phase 1 — Widen `control_shape`'s role vocabulary
**Owns:** `DRAW_MARKERS` and a new `ROLE_*` vocabulary plus `role_of(arm) -> control|dose|idea|treatment`.
**Does not touch:** `kind_of`, `findings`, `refusals`, `REFUSE_BAND`, or anything D17 reads — the
shape check keeps its present population exactly, so no promotion changes on this phase.
**Why it is needed:** `kind_of` finds 11 controls among the 176 audited picks; the rationales
contain 62. Its markers cover `placebo` / `hash order` / `hash-drawn` but not the `Control:` /
`Paired control:` / `Yardstick:` prefixes that most of the lab's control arms actually use.
**Exit criteria:** `role_of` reproduces the audit's 189-control classification over all 821 arms;
every new marker carries its measured hit count; `lab control`'s output is byte-identical.

### Phase 2 — D18: refuse a promotion whose pre-registered variant is a control
**Satisfies:** R3
**Owns:** a new clause in `hardgate.check()`, placed after D11b and before D16, plus its Decision
D18 prose in the module docstring.
**Does not touch:** the fold selector, `_dev_curves`, `pick`, or `best_dev_eligible`.
**Why it is needed:** 19 of 78 dev-eligible methods would pre-register a control arm — M0202's is
a hash-order placebo. Three (M0033, M0035, M0044) already clear both fold clauses and are stopped
only by kin, which is luck.
**Exit criteria:** the 19 are refused with a sentence naming the arm and quoting its rationale;
no method that is promotable today becomes refused for any *other* reason; the commit message
carries the argument, as the brief requires.

### Phase 3 — Measure the era edge on the promoted variant
**Satisfies:** R4
**Owns:** the `2009-15 edge` column in `commands/lab.py:_walkforward` and the `high_coverage_edge`
the buy signal is handed.
**Does not touch:** `buy_signal`'s signature or its other three conditions.
**Why it is needed:** the column reports the hindsight-best arm on the era itself. For 39 of 74
that is a different arm from the promoted one, for 18 they disagree on sign, and for 19 it is a
control. M0201 reports +1.82 pts on a placebo while its promoted arm is at −7.82.
**Exit criteria:** the column reports the promoted variant's edge (the hindsight-best stays
visible, clearly labelled, because it is what every past record quoted); the firing set moves from
`{M0092, M0197, M0243, M0258}` to exactly `{M0072, M0092, M0258}` and the commit message says so;
no promotion outcome moves (`check()` has no era clause — verify it, do not assume);
`BUY_CONDITIONS` says which arm it means.

## Reconciliation Log

| Conflict | Phases | Resolution |
|---|---|---|
| Both 2 and 3 need a role answer for the promoted arm | 1, 2, 3 | phase 1 owns `role_of`; 2 and 3 import it |
| Phase 3's edge change could alter phase 2's refusal set | 2, 3 | it cannot — `check()` has no era clause; stated as a phase-3 exit criterion |

## Decisions

| Fork | Chosen | Rung |
|---|---|---|
| (A) constrain the fold selector vs (B) leave it | **(B), leave it** | 1: measured evidence — see the argument below |
| Fix the control-promotion hole in `best_dev_eligible` or in `hardgate.check` | **in `check`** | 5: the brief ("argued in the commit message"); a ranking change would silently move what every historical record refers to |
| Phase 3: replace the era-edge column or add to it | **add, label both** | 6: convention — past records quote the existing number, so it must stay readable |

### The argument for (B), written out — R3

**1. The selector is faithfully simulating the lab's actual selection rule.** `walkforward.pick`
ranks every registered variant by MAR. So does `store.best_dev_eligible`, the call
`prereg.promote_method` actually makes — `ORDER BY mar DESC, n ASC`, with an eligibility filter
and **no role filter**. The fold's stated question is *"which variant would the lab's own rule
have named at this point in time"*. Today that rule would, for 19 of 78 methods, name a control.
A selector that excluded controls would be simulating a promotion rule the lab does not have, and
would report a cleaner out-of-sample record than the lab's real behaviour deserves. That is the
opposite of what a gate is for.

**2. The 2-of-4 pile-up is the era, not the selector.** Across all 167 methods with four scoreable
folds, fold 2 (2006-2008) is won by 88% and fold 3 (2009-2011) by 10%. The modal pattern is
`.T..` (36%) and `.T.T` (24%): win the crash, lose the rebound. Nearly every lab book sits behind
the same SPY 200-day gate, whose best years are the famous crashes. **No choice of arm moves a
fold that 90% of the lab loses.** "2 of 4" is the lab's modal outcome and the signature of a
shared gate — it should stop being read as "nearly there".

**3. Measured, (A)'s fix changes two verdicts, and both for the worse.** Constraining the
selector to treatment arms leaves 31 of 44 records unchanged and flips the complete gate verdict
for exactly two: M0174 and M0178. Both would become promotable with a **negative** 2009-2015 era
edge (−0.6% and −2.1%) — the era the dev store covers best. That edge is negative precisely
because their advantage lives in the thin early years the store cannot price, which is the failure
mode the buy signal's 4th condition exists to catch. (A) would spend two of the lab's counted
looks on it. The gate exists because 4 of 4 looks already failed.

**4. The restriction is not a correction; it is a different measurement with its own losers.**
M0107 goes 2 of 4 → **1 of 4** under (A): the arms it was winning on were its controls. And for
four methods (M0187, M0193, M0260, M0261) there is no treatment arm at all — they are entirely
placebo calibrations or dose ladders, and (A) is undefined for them.

**5. D11 already does the job (A) is proposing, and does it better.** Three of the five methods
whose picks' record reaches a majority under (A) — M0179, M0184, M0202 — are still refused,
because the variant that would actually be pre-registered loses its own folds. D11b asks the right
question directly: not *"was the selector's taste good?"* but *"did the arm that gets the money win
its own folds?"* The one method where that question is being asked of a placebo is M0202 — and
that is phase 2's bug, not the selector's.

**So: 44 methods are correctly refused.** The finding the brief anticipated is the finding.

### What the audit found instead, and why it is worse

The gate asks whether a method's *own* chosen variant won its folds (D11b) but never asks **what
that variant is**. For 19 of 78 dev-eligible methods it is a control arm — an arm registered to be
beaten. M0202's is `M0202-PLC1-HALF`, a hash-ordered draw. M0033, M0035 and M0044 clear both fold
clauses at 3 of 4 and are stopped only by the kin rule.

That is the audit's question — *is this measuring the idea or its control?* — asked of the clause
that spends the look and the money. There the answer is **yes, it is measuring the control**, and
unlike the selector it is not guarded by anything. Phase 2 guards it.

## Open Questions

None. Every fork above was decided from measured evidence or the brief.

## Rollback

Each phase is one commit touching 2-3 files and adding tests; `git revert` restores the prior
behaviour exactly. No migration, no recorded row, no lab state. Phase 2 is the only one that
changes a promotion outcome, and it only ever refuses — reverting it cannot retroactively promote
anything, because nothing is promoted without a human running `lab promote`.

## Next

Execute the phases one at a time, starting at phase 1:

    /implement -f docs/plans/FOLD_SELECTOR_AUDIT_PLAN.md --phase 1

Or run the whole set as a swarm — a session per phase, concurrent wherever `Depends on` allows:

    /analyze-orchestrator -f docs/plans/FOLD_SELECTOR_AUDIT_PLAN.md

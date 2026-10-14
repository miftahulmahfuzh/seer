# Plan: one number was doing two jobs — split the screen from the bar

**Slug:** split-screen-from-bar
**Date:** 2026-10-14 09:52:18 +07
**Analysis:** `docs/analyzer/20261014-095218-B7QD_code_analyzer.md`
**Worktree:** `/home/miftah/.worktrees/seer/split-screen-from-bar` (removed on landing)
**Branch:** `feature/split-screen-from-bar` (base: `origin/main` @ `49287bb`) — merged and deleted
**Phases:** 2
**Status:** complete
**Coordinator:** `orch-split-screen-from-bar` (landed 2026-10-14 at `e93fa85`)
**Reconciled:** 2026-10-14 (round 1)

---

## Why

The owner, 2026-10-14, verbatim:

> "i agree with you. this is what i am afraid of. beating SPY is so hard already, yet we still
> impose these strict constraints . you know what, let's do your suggestion, and in fact, raise my
> risk appetite more to 25%"

"Your suggestion" is the decoupling he is agreeing to: keep the figure as the **real-money** bar
applied at promotion, and loosen it on the **dev screen**, whose job is to surface candidates
worth studying — so a method can be found, measured and understood while still being refused real
money. He then went further and raised the real-money bar itself to 25%.

The measurement behind it: of 399 recorded dev trials, **257 beat SPY TR and the 20% bar rejects
188 of them — 73%.** Nothing else in the lab rejects at that rate. Meanwhile **SPY itself fell
56.5%** over the dev window at 7.86%/yr, so the lab has been requiring its strategies to fall less
than a third as far as the benchmark they must beat.

## Requirements

Final after reconciliation. Every `R` is owned; none moved between phases, because no step moved
between phases — the reconciliation corrected figures, ownership rulings, one ordering and one
in-scope fix, and all of that landed inside the phase that already owned the file.

| ID | What the user asked for | Phases |
|---|---|---|
| R1 | Raise the real-money drawdown bar from 20% to 25% (§1 condition 4, the promote gate, the leaderboard) | **1** (the constant and every reader), **2** (the dated record) |
| R2 | Split the lab's dev-eligibility screen off from that bar, so a method can be studied without being fundable | **1** (the new constant, its four decision sites, `:1904`'s prose, the new test), **2** (the dated record) |
| R3 | Record it as a dated owner revision, the way §11 and §13 record their predecessors | **2** |
| R4 | Keep engine and web agreeing — the bar reaches the web as a TS constant **and** through `lab.json` | **1** |

## Scope

**In scope:**

- `metrics.MAX_DRAWDOWN` 0.20 → **0.25**, re-exported through `tuning` as today.
- A new `metrics.DEV_MAX_DRAWDOWN` (proposed **0.50**), re-exported through `tuning`. It is
  **one decision written at four call sites** — `dev.py:96`, `dev.py:440`, `store.py:1463`,
  `store.py:1801` — see invariant 2. A fifth site, `store.py:1904`, interpolates it into prose
  rather than deciding anything, and must name it so the prose is true.
- The ~40 engine tests the change moves, including re-expressing the historical claims in
  `test_lab_gate_policy.py`.
- `web/lib/golive.ts` + `golive.test.ts`, and a regenerated `web/data/lab.json` committed with
  `lab/lab.sqlite` — all in the same commit as the engine change.
- A dated `## 18.` revision in `docs/plans/2026-10-03-seer-design.md`.

**Out of scope, and why:**

- **Nothing is promoted and nothing is tested.** This change makes more methods *eligible*;
  spending a test look is a separate, later, owner-initiated act. `store.test_looks(conn)` reads
  4 before and after (Decision D4).
- **No recorded row is edited.** `eligible` and `failed` are re-derived from recorded columns
  against live constants, so verdicts legitimately move without an `UPDATE`. The recorded
  `failed` text of the 30 rows judged at 15% keeps its wording (Decision D5).
- **`web/lib/cadence.ts` is not touched.** Its `0.20` is `TARGET_RESIZE_BAND`, a coincidental
  same number (Decision D6).
- **`test_sean_mirrors.py` is not extended.** It covers resize band, target resize band, owner
  monthly and USD/IDR; the drawdown bar is mirrored through `golive.test.ts` instead, and adding
  a second mirror mechanism for one constant is work nobody asked for.
- **The other four §1 conditions do not move**, and neither does `MIN_PROFIT_FACTOR`, `DSR_MIN`
  or the N policy.
- **`web/lib/sera/derive.ts:172` is NOT fixed.** It prints the real-money bar as the drawdown
  target on every trial, so `/sera` will read "25% or less" beside a studied-only trial at 40%
  that it also, correctly, ticks. Cosmetic — nothing mis-judged, nothing written, no test red —
  but owner-facing, so it is **named in §18 as a known rough edge** rather than left in a report
  (Decision D12). The real fix is a `gate.devMaxDrawdown` through `store.snapshot`,
  `web/lib/sera/types.ts` and `test_lab_snapshot`'s schema pin: none of it in R1/R2/R4.
- **`store.py:1904` IS fixed, in phase 1.** It was drafted as a follow-up; reconciliation moved it
  in (Decision D13). `reevaluate_method` writes its sentence through `append_analysis` into
  `methods.analysis`, which can only be appended to, so the first `lab reevaluate` after this plan
  set would have recorded an irreversible falsehood. One line, in a file phase 1 already owns.

## Invariants

1. **The two constants never collapse back into one.** `MAX_DRAWDOWN` is the real-money bar;
   `DEV_MAX_DRAWDOWN` is the screen. A change that makes the screen read `MAX_DRAWDOWN` again
   undoes R2 entirely.
2. **FOUR call sites read the screen, and that is one decision written four times.** CORRECTED
   2026-10-14 — the original wording said "exactly one" and named the wrong functions; measured,
   `store.py:1463` is inside **`owner_failures`** (def `:1411`) and `:1801` is inside
   **`_blocking`** (def `:1769`), and `eligible` is `not owner_failures(...)`. The screen sites
   are `backtest/dev.py:96` (`FAILURE_LABELS[1]`, or the label lies), `backtest/dev.py:440`
   (`make_row`, or new trials record `eligible=0` while `store.verdict` reads them eligible),
   `lab/store.py:1463` and `lab/store.py:1801` (or `lab reevaluate` **crashes** — 7 recorded
   trials across M0050, M0058, M0082, M0085 read derived-eligible and then hit `_blocking`'s
   deliberate `LabError`). The real-money bar keeps `store.py:1904`, `store.py:2894`,
   `hardgate.py:1569` and `metrics.checklist`. RECONCILED 2026-10-14: `store.py:1904` is a **fifth**
   occurrence but not a fifth decision — it interpolates the number into `reevaluate_method`'s
   append-only `analysis` prose, and phase 1 Step 5b makes it name the screen so that prose is
   true. Four decisions, five occurrences; do not pin a grep count, pin the four names.
3. **Engine and web agree in the same commit.** `web/lib/golive.ts`'s constant, its label, and
   `web/data/lab.json`'s `gate.maxDrawdown` all read 0.25 when the engine does.
   `web/lib/golive.test.ts` is the tripwire and must be green.
4. **No recorded row is edited.** `trials`, `trial_*`, `methods`, `insights`, `method_folds` are
   append-only. No `UPDATE`.
5. **No recorded `config_digest` moves.**
   `test_lab_methods.py::test_every_recorded_configuration_still_digests_to_its_recorded_digest`
   is the tripwire.
6. **The test window is never read.** No `lab test`, no `lab promote`, no `engine/.research-test`.
   `store.test_looks(conn)` reads 4 before and after.
7. **The lab database is committed with `lab stage` and a BARE commit, no pathspec.** A pathspec
   commit re-reads the working tree and can pick up a newer `lab.sqlite` beside an older
   `lab.json`. Check `git status --short` first so the bare commit sweeps nothing else.
8. **Every other commit is by explicit pathspec, `-m` BEFORE `--`.** `git reset --hard`,
   `git clean`, `git checkout .`, `git restore .` and bare `git stash` are banned, including in
   any subagent dispatched — say so verbatim in such a prompt.
9. **A test whose premise this change retires is RE-EXPRESSED, never deleted.** Several tests
   assert `tuning.MAX_DRAWDOWN == 0.20` as their own guard. Invert each to the post-change truth,
   which is the stronger statement; losing the coverage is not acceptable.
10. **The suite is green and the skip count is quoted beside the pass count.** Run as
    `cd <worktree>/engine && PYTHONPATH=<worktree>/engine/src
    PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres
    /home/miftah/seer/engine/.venv/bin/python -m pytest -q`. Baseline **in this worktree** is
    **4756 passed, 4 skipped** (`test_universe_rank` skips here: the month-end sweep CSV is
    gitignored and lives only in the main checkout). Quote what you measure, not this number. `docker start seer-pg` if the container is down. Lint with
    `ruff check engine` (CI is E9 and F, minus F401). Web: `cd web && npx tsc --noEmit && npm test`.
11. **Modules carry prose docstrings that argue for the shape of the code.** Both constants get
    docstrings explaining *why* there are now two, with the measurement.
12. **Owner-facing text is plain** — the §18 revision carries no ids, digests or jargon.

## Phases

| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID | Card |
|---|-------|-----------|---------|-------|-----------|------------|------|--------|------|
| 1 | Two constants, and everything that reads them | R1, R2, R4 | `engine/backtest`, `engine/lab`, `web`, `lab/` | ~45 | — | HARD | `.workflows/plan/split-screen-from-bar/phase-1.md` | P1-ENG-QK7F (done 2026-10-14) | — |
| 2 | The dated owner revision, and the before/after | R1, R2, R3 | `docs` | 1 | 1 | NORMAL | `.workflows/plan/split-screen-from-bar/phase-2.md` | P1-ROOT-M2XZ (done 2026-10-14) | — |

**Why the web is in phase 1 and not its own.** `web/lib/golive.test.ts` pins the TS constant to
`web/data/lab.json`'s gate, which `store.snapshot` writes from `tuning.MAX_DRAWDOWN`. An
engine-only phase would leave `npm test` red, and CI runs both — so it would not be a shippable
phase (Decision D2).

### Phase 1 — Two constants, and everything that reads them
**Satisfies:** R1, R2, R4
**Owns:** `backtest/metrics.py`, `backtest/tuning.py`, `backtest/dev.py` (`FAILURE_LABELS`,
`make_row`, the D8 docstring bullet), `lab/store.py` (`owner_failures` and its docstring,
`_blocking` and its docstring, and `reevaluate_method`'s analysis prose at `:1904`), the ~40 engine
tests the change moves — **including `test_dev_trades_bar.py`'s `HELD_OUT_BY_THE_TRADES_BAR`
constant list** — `web/lib/golive.ts`, `web/lib/golive.test.ts`, `web/lib/sera/fixture.ts`, and the
regenerated `web/data/lab.json` + `lab/lab.sqlite`.
**Does not touch:** `metrics.checklist`, `MAX_DRAWDOWN_LABEL`, `hardgate.check`'s D16 rule,
`tuning.qualifies`/`gate`, `walkforward.gate_p3b`, `b_walkforward.gate_p6a`, `store.snapshot`
(`:2894`) — all of which keep the **real-money** bar — plus `npolicy`, `web/lib/cadence.ts`,
`web/lib/sera/derive.ts`, `test_sean_mirrors.py`, any method file, any recorded row, the design doc.
CORRECTED 2026-10-14: the draft listed `owner_failures` here, which was the swapped-names error —
`owner_failures` **is** the screen and phase 1 moves it.
**Exit criteria:**
1. `tuning.MAX_DRAWDOWN == 0.25` and `tuning.DEV_MAX_DRAWDOWN == 0.50`, read at exactly the four
   decision sites `dev.FAILURE_LABELS`, `dev.make_row`, `store.owner_failures`, `store._blocking`
   — proved by grep, quoted, by name and not by count (invariant 2).
2. The real-money bar still refuses what the owner cannot hold — proved by a test that a trial
   at 30% drawdown is **dev-eligible** and is **refused by `metrics.checklist`'s go-live item 4**.
   CORRECTED: the original criterion said "fails `owner_failures`", which is impossible, because
   `eligible` IS `not owner_failures(...)` — the two cannot disagree by construction.
3. `web/lib/golive.ts` reads 0.25, its label reads `Max drawdown ≤ 25%`, `web/data/lab.json`'s
   `gate.maxDrawdown` is 0.25, and `golive.test.ts` is green.
4. Every re-expressed test still asserts its original historical claim; none deleted.
5. `store.test_looks(conn)` reads 4 before and after; the digest tripwire green;
   `git status --short` clean after the bare lab commit.
6. `ruff` clean; pytest green with the skip count quoted; `npx tsc --noEmit && npm test` green.
7. **Report the measured before/after**: how many recorded trials and distinct methods are
   dev-eligible under the old screen and the new one, **and** the browsable (drawdown-condition)
   pair beside it, clearly labelled. Phase 2 quotes these. Reconciled values, independently
   re-derived read-only (lab md5 `00f7ebec1b3134e67e3b087226d308b7`, gate `methods` N = 81):
   dev-eligible **26 / 16 → 67 / 32**; browsable **93 / 37 → 319 / 76**; at a 0.25 screen,
   60 / 30. Phase 1 re-measures on the landed tree and quotes what it measures.
8. `store.py:1904`'s re-evaluation prose names the **screen** (Step 5b):
   `grep -n "a max drawdown bar of" engine/src/seer_engine/lab/store.py` returns nothing, so
   `lab reevaluate` can no longer write a false sentence into append-only `methods.analysis`.
9. **The source is committed by pathspec BEFORE the bare `lab stage` commit.** A bare commit sweeps
   every tracked modification; running it first would have folded the whole phase into the lab
   commit. Phase 1's steps are ordered 10 (new test) → 11 (pathspec commit) → 12 (bare lab commit).

### Phase 2 — The dated owner revision, and the before/after
**Satisfies:** R1, R2, R3
**Owns:** `docs/plans/2026-10-03-seer-design.md` — a new `## 18.` appended after `## 17.`, plus
**exactly one line above it**: §1 condition 4's inline revision marker at `:20`, which is house
convention and not an improvisation (Decision D10).
**Does not touch:** anything else above `## 18.` — §1's conditions are quoted, never edited; the
revision series works by appending, as §11 and §13 do. The §1 preamble pointer at `:14` stays on
§11. **§13 is edited by nobody** (D9). No source file, no test, no `web/`, no lab database.
**Exit criteria:**
1. `## 18. Revision 2026-10-14 (owner): …` exists, in the house shape of `## 11.` and `## 13.` —
   what changed with the original sentence preserved, who and why with the owner quoted verbatim,
   and what it does **not** change.
2. It states plainly that condition 4 now reads 25%, that the dev screen is a **separate** number
   and why, and that the change promotes and tests nothing.
3. It carries the measurement: 257 of 399 beat SPY TR and the old bar rejected 188 of them; SPY
   itself fell 56.5% at 7.86%/yr; and phase 1's measured before/after. **The headline is the
   full-verdict eligibility pair, 26 → 67 trials over 16 → 32 methods (Decision D8).** The
   browsable pair, 93 → 319 trials, may appear only beside it and labelled as "clears the drawdown
   condition". It also says plainly that a 0.25 screen already reaches 30 of those 32 methods and
   that 0.40 → 0.50 adds none (Decision D11).
4. It states the residual risk honestly: a looser screen means more candidates to study and more
   chances to fool oneself, which is what the DSR and the N policy price — and N is unaffected,
   because `dev_method_count` counts methods tried rather than methods that passed.
5. The §13 re-measurement bullet says the trades-bar held-out set grows **five → twelve** (not
   eight — see the Reconciliation Log), attributes the growth to the **screen** rather than the
   money bar, and states that all twelve still sit below the luck bar so §13's finding survives.
   §13 itself is edited by nobody (Decision D9).
6. §18 names the `/sera` drawdown-target rough edge in plain language (Decision D12), and carries
   **no** "do not run `lab reevaluate`" caveat — phase 1 Step 5b removed that hazard (D13).
7. Step 0's precondition check is a **hard stop**: `DEV_MAX_DRAWDOWN` imports, `MAX_DRAWDOWN` is
   0.25, the screen is looser than the bar, and `store.py:1904` names the screen. If any fails the
   phase stops and reports rather than writing a permanent record of a change that did not land.
8. Plain language throughout. Suite and lint unaffected but re-run and quoted — the number on
   entering this phase is **4757 passed, 4 skipped** (phase 1's 4756/4 baseline plus its one new
   test), not the draft's 4757/3.

## Reconciliation Log

Round 1, 2026-10-14. Both phase plans edited in place; this index rewritten from draft to final.
Every measurement below was re-derived by the reconciler **read-only** against the committed
`lab/lab.sqlite` — md5 `00f7ebec1b3134e67e3b087226d308b7`, sha256 `2c8c9669ad7664…`, identical
before and after; `store.gate` = `methods` N = 81; `store.test_looks` = 4. No source file touched,
no row written, no test-window look spent.

| # | Class | Conflict | Resolution |
|---|---|---|---|
| **C1** | Contradictory measurement | Phase 2 said `HELD_OUT_BY_THE_TRADES_BAR` grows **5 → 8** and named three joiners; phase 1, measuring on the applied change, said **5 → 12**. Both cannot be right. | **12 stands.** Re-derived independently: at a 0.50 screen the set is 12 and phase 1's list matches the reconciler's row for row and in order. Phase 2's script patched `tuning.MAX_DRAWDOWN`; after phase 1 `store.owner_failures`'s drawdown comparison reads `tuning.DEV_MAX_DRAWDOWN`, so 8 is the count at a **0.25 screen**, which does not land. Phase 2's slot, its §18 bullet, its handoff and its script were all corrected; phase 1's Step 9c gained the confirmation. Rung **2** — a measurement, re-taken. |
| **C2** | Contract drift | The same bullet attributed the growth to "raising the bar to 25%". It is the **screen** moving that grows it — a trial that missed both the fall limit and the trade count now misses only the trade count. | §18's bullet reworded to say so. Rung **3** — phase 1's Step 4 code block is what decides it. |
| **C3** | Gap / unowned | `store.py:1904` interpolates the drawdown number into `reevaluate_method`'s append-only `analysis` prose. After phase 1 it would write "25%" for a re-judgement made at 50% — an irreversible falsehood on the first `lab reevaluate`. Phase 1 had it parked as "a follow-up phase". | **Assigned to phase 1 as new Step 5b** (Decision D13), with an exit criterion and a grep. The "do not run `lab reevaluate`" caveat is retired everywhere, phase 2 included. Rung **1** — invariant 4. |
| **C4** | Gap / unowned | `web/lib/sera/derive.ts:172` will show "25% or less" beside a studied-only trial at 40% it also ticks. Phase 1 had it parked as "a follow-up phase". | **Named, not fixed** (Decision D12): phase 2's §18 states it in plain language under "what it does not change"; the index records it in Scope. The real fix touches `snapshot`, `sera/types.ts` and `test_lab_snapshot`'s schema pin — outside R1–R4 and outside shippable phase 1. Rung **4**. |
| **C5** | Broken-build / ordering | Phase 1's BARE `lab stage` commit was Step 10, **before** the source pathspec commit at Step 12. A bare commit sweeps every tracked modification, so the whole phase would have landed inside the lab commit — invariant 8 broken, two-commit rollback gone. | **Steps reordered:** 10 = the new test, 11 = pathspec commit, 12 = bare lab commit. Cross-references and the Rollback revert order fixed (newest first is now the lab commit). Decision D14, rung **1**. |
| **C6** | Contract drift | Phase 2's Requires and §18 both said the screen is "read by exactly one call site". Corrected invariant 2 says four. | Both rewritten to "one decision written at four call sites", naming them. §18's owner-facing wording keeps its plain register. Rung **1** — invariant 2. |
| **C7** | Contract drift | This index's phase-1 **Does not touch** listed `owner_failures` — the swapped-names error. `owner_failures` *is* the screen and phase 1 moves it. | Rewritten to the real-money readers: `metrics.checklist`, `hardgate`'s D16 rule, `tuning.qualifies`/`gate`, `walkforward.gate_p3b`, `b_walkforward.gate_p6a`, `store.snapshot`. Rung **1**. |
| **C8** | Contract drift | This index's phase-1 **Owns** and exit criterion 1 still said "exactly one call site in `lab/`", and Owns omitted `backtest/dev.py`, `sera/fixture.ts` and the trades-bar constant list. | Both rewritten; exit criterion 1 now pins the **four names** rather than a grep count, since `:1904` makes it five occurrences and four decisions. Rung **1**. |
| **C9** | Duplicate work risk | Phase 1's Handoff 1 told phase 2 it "must either amend §13's list or state in §18 that it is superseded" — the first branch contradicts D9 (§13 edited by nobody) and would have had both phases write the same statement. | Handoff 1 rewritten as the three-way ruling: phase 1 owns the constant list, §13 is edited by nobody, phase 2 records it in §18. Rung **1** — the append-only convention. |
| **C10** | Unmet assumption | Phase 2's Step 0 precondition was prose, not a stop, and did not check `MAX_DRAWDOWN == 0.25` or Step 5b. | Rewritten as a hard stop: `set -e`, an importable-and-looser-than-the-bar check that exits non-zero, a grep for `:1904`'s new wording, and an explicit "stop and report". Added as phase 2 exit criterion 7. Rung **2**. |
| **C11** | Contract drift | Phase 2's suite baseline was the draft's 4757 passed / 3 skipped. | Corrected to 4756/4 in this worktree, so **4757 passed / 4 skipped** on entering phase 2 (phase 1's one new test). Phase 1's Verification states the same target. Rung **2**. |
| **C12** | Contract drift (D8/D11) | Phase 2's §18 quoted only the eligibility pair and never carried the browsable pair or D11's honest counter-argument, which D11 says §18 "says out loud". | §18 gained a labelled browsable sentence (93 → 319 trials) **beside** the eligibility headline (26 → 67 trials, 16 → 32 methods), plus a bullet stating that a 0.25 screen already reaches 30 of the 32 methods and 0.40 → 0.50 adds none. New slots defined and pre-resolved in Step 3. Rung **2** — D8 and D11. |
| **C13** | Latent defect in a measurement script | Phase 2's Step 3 eligibility script patched `metrics.MAX_DRAWDOWN`/`tuning.MAX_DRAWDOWN`. On the **landed** tree that changes nothing and would have printed the same row for every screen value. | Both Step 3 scripts rewritten to patch `tuning.DEV_MAX_DRAWDOWN`, with the trap called out in bold at the head of the step. Rung **3**. |

**Checked and found clean:** no symbol is deleted anywhere in the set, so there is no
deleted-then-used conflict; the two phases share no file (phase 2 touches exactly one, which phase
1 explicitly disclaims, and phase 1 touches nothing under `docs/plans/`); dependencies point
backward only (2 → 1); every impact point in the analysis is owned, and the two impact points the
analysis omits — `dev.py:96`/`:440` and `store.py:1801` — are owned by phase 1 under corrected
invariant 2; both phases commit by explicit pathspec except phase 1's one mandated bare lab commit,
which now runs last behind a `git status --short` guard; `store.test_looks` is 4 throughout.

**One stale document left deliberately unedited.** `docs/analyzer/20261014-095218-B7QD_code_analyzer.md`'s
Reference List still labels `store.py:1801-1802` as `owner_failures` / "call — stays" and omits
`dev.py:96` and `dev.py:440`. The analysis describes; the plans prescribe, and phase 1's Interface
Contract is the authority on which sites move. The analyzer file is not the reconciler's to edit and
was not edited.

**Phase 2's §17 survivorship figures were spot-checked** against `docs/lab/survivorship/grid.csv`
and are correct as written: at 25%, 49 variants pass on the dev store and 7 cross on the fuller
history (14%); at 20% it was 11 of 28 (39%).

## Decisions

Rungs: **1** stated invariant · **2** phase exit criteria / a measurement · **3** the plan's code
blocks · **4** the index's Why and Requirements · **5** the user's raw input · **6** convention.

| # | Fork | Choice | Rung |
|---|---|---|---|
| **D1** | The screen's value: 0.25, 0.40, 0.45, 0.50, or SPY's own 0.5665. | **0.50.** SPY fell 56.5% over the dev window at 7.86%/yr, so a book falling by half offers no risk control buy-and-hold does not already give away free — the screen draws the line just inside what doing nothing costs. On the **drawdown condition alone** it admits 319 of 399 trials against 93; as **dev-eligible** (all conditions plus the luck test) roughly 67 trials / 32 methods against ~26 / ~16. The implementer may argue another value **from measurement**, but may not collapse the two constants. | **2** — measurements M3 and M3b, bounded by invariant 1. |
| **D8** | Which number does §18 quote — the drawdown-condition count (93 → 319) or dev-eligibility (~26 → ~67)? | **Dev-eligibility.** The first answers "how many trials clear this one condition", which is not what a reader of §18 will think it means; §17 already quotes 93 for a different purpose. A permanent owner record must carry the number that matches its sentence. Phase 1 re-derives it and phase 2 quotes phase 1, never the projection. | **2** — M3b, and the risk of a wrong-kind number in a frozen record. |
| **D9** | Splitting the screen off grows `HELD_OUT_BY_THE_TRADES_BAR` in `test_dev_trades_bar.py:66` from 5 trials to **12**, and its failure message says to update both that list **and** design §13. (FIGURE CORRECTED 2026-10-14: the draft said 8. It is the **screen** moving 0.20 → 0.50 that grows the set, not the money bar moving to 0.25 — `store.owner_failures`'s drawdown comparison reads `DEV_MAX_DRAWDOWN` after phase 1, so 8 is the count at a 0.25 screen, which does not land. Re-derived read-only; Reconciliation Log row C1.) | **Phase 1 owns the constant list; §13 is edited by NOBODY; phase 2 records the re-measurement in a §18 bullet.** §13 is a dated record of what was true on 2026-10-07; amending it would rewrite history rather than extend it. All **12** still sit below `DSR_MIN` or carry no luck score (`clearing the luck bar = 0`, measured at the 0.50 screen), so §13's "zero verdicts change" finding survives — **and if that is ever false on the landed tree, phase 2 stops and rewrites rather than publishing it.** | **1** — the append-only convention the whole revision series rests on. |
| **D11** | 0.50 versus 0.25 for the screen, now that full-verdict eligibility is measured: 0.25 reaches 30 of 32 methods and 0.40 → 0.50 adds nothing. | **0.50 stands**, and §18 says this out loud. The marginal two methods are not the argument; the argument is that the screen should not be *the same number as the bar*, or the split is cosmetic and drifts back the next time the bar moves. The browsable count still rises 196 → 319 trials, and browsing is what the screen is for. | **4** — the index's Why: the two numbers answer different questions. |
| **D12** | `web/lib/sera/derive.ts:172` prints the real-money bar as every trial's drawdown target, so `/sera` will say "25% or less" beside a studied-only trial at 40% that it also ticks. Fix it in phase 1, card it, or name it? | **Name it in §18; fix it in neither phase.** The real fix needs `gate.devMaxDrawdown` through `store.snapshot` (`:2894`), `web/lib/sera/types.ts` and `test_lab_snapshot`'s schema pin — none of that is in R1, R2, R3 or R4, and `snapshot` is precisely what R4 pins the TS constant to, so touching it widens phase 1 past shippable. But it is owner-facing and the owner reads that page, so it does not stay in a planner's return value either: phase 2's §18 states it in one plain-language clause under "what it does not change". Cosmetic — nothing mis-judged, nothing written, no test red. | **4** — the index's Why and Requirements table: no R covers the Sera target, and R3's record is where owner-facing facts belong. |
| **D13** | `store.py:1904` writes `f"a max drawdown bar of {tuning.MAX_DRAWDOWN:.0%}"` into `methods.analysis` through `append_analysis`, describing a re-judgement that after phase 1 is made against the **screen**. Follow-up phase, loud comment, or fix it now? | **Phase 1 fixes it, Step 5b.** `methods.analysis` can only be appended to, so the first `lab reevaluate` after this plan set would record an irreversible falsehood. A comment does not help: the command is shipped and takes no argument. The fix is one interpolation and two words, in a file phase 1 already owns, and it retires the "do not run `lab reevaluate`" caveat rather than carrying it into a permanent record. | **1** — invariant 4, the append-only contract. A false sentence appended is as unfixable as an edited row. |
| **D14** | Phase 1's draft ran the BARE `lab stage` commit (Step 10) before the source pathspec commit (Step 12). | **Reordered: pathspec commit first, bare commit last.** A bare `git commit` sweeps every **tracked** modification, so as drafted it would have folded `metrics.py`, `tuning.py`, `dev.py`, `store.py`, ~40 tests and `golive.ts` into the "restage the snapshot" commit — breaking invariant 8 and the two-commit rollback this index depends on. Untracked files (this plan set, the analysis) are never swept, so only tracked edits were at risk. Phase 1's steps are now 10 (new test) → 11 (pathspec commit) → 12 (bare lab commit). | **1** — invariants 7 and 8, which only cohere in that order. |
| **D10** | Does phase 2 edit condition 4's inline marker at `:20`, above its own section? | **Yes — it is the house convention, verified.** Both §11 and §13 rewrote their condition's inline marker (`:16` and `:20`). Leaving it stale would make §1 claim 20% for ever. The §1 preamble pointer at `:14` stays on §11: §18 exercises that clause rather than weakening it again. | **6** — what §11 and §13 actually did. |
| **D2** | Web in its own phase, or inside phase 1? | **Inside phase 1.** `golive.test.ts` pins the TS constant to `lab.json`'s gate, which the engine writes; an engine-only phase leaves `npm test` red and CI runs both, so it would not be shippable. | **1** — invariant 3, and the "a phase passes tests on its own" rule. |
| **D3** | Does `hardgate.check`'s (D16) survivorship rule read the screen or the bar? | **The bar.** It refuses a variant whose fall on honest prices breaches what the owner may hold; that is a real-money question, not a research-budget one. It therefore gets looser with the owner's appetite, which is correct and deliberate. | **4** — the index's Why: the bar is the owner's risk appetite. |
| **D4** | The change makes more methods eligible. Promote one? | **No.** The owner raised a bar; he did not ask for a promotion. A test look is spend-once and four are already gone. | **5** — the user's raw input says nothing about promoting. |
| **D5** | The 30 rows recorded with `max DD <= 15%` in their `failed` text. Rewrite to 25%? | **No.** `trials.failed` is append-only and records what was true when judged; the live labels are re-derived for display. This is the existing contract and the 15%→20% move kept it. | **1** — invariant 4. |
| **D6** | `web/lib/cadence.ts` also contains `0.20`. | **Leave it.** That is `TARGET_RESIZE_BAND`, an unrelated constant that happens to share the number. Touching it would change the resize behaviour for no reason. | **6** — the source is the authority on its own names. |
| **D7** | Should the screen apply to the test window too? | **Out of scope, and the question is moot.** `runner.preflight_test` refuses any method that is not `promoted`, and promotion reads the real-money bar — so the test window is already behind the bar, not the screen. No change needed. | **3** — the existing code path. |

## Open Questions

**None.** Every fork was decided above, and reconciliation added three more (D12, D13, D14) rather
than parking any. Every requirement R1–R4 is owned by a named phase. The one irreversible act in
this area — spending a test look — is explicitly out of scope (D4); the one irreversible *write* —
`reevaluate_method` appending to `methods.analysis` — is closed by D13 rather than left as a
warning. No branch of any decision here is irreversible: both phases are commits that `git revert`
backs out.

## Rollback

- **Per phase:** each phase is one or more commits bounded by an explicit pathspec (plus one bare
  lab commit in phase 1), so `git revert <sha>` backs it out. **Never** `git reset --hard`.
- **Phase 1's lab commit** must be reverted together with its source commit: reverting the source
  alone would leave `web/data/lab.json` claiming a 25% bar the code no longer sets, and
  `golive.test.ts` would go red. Back the two out together, oldest last.
- **Phase 2** reverts cleanly; it is append-only prose.
- **No recorded row changes**, so there is no database state to unwind — the verdicts are derived
  and return to their old values the moment the constants do.

## Next

Execute the phases one at a time, starting at phase 1:

    /implement -f docs/plans/SPLIT_SCREEN_FROM_BAR_PLAN.md --phase 1

Or run the whole set as a swarm — a session per phase, concurrent wherever `Depends on` allows,
resumable on any machine:

    /analyze-orchestrator -f docs/plans/SPLIT_SCREEN_FROM_BAR_PLAN.md

Or put them on the board first (GitHub repos only):

    /create-task --from-plan docs/plans/SPLIT_SCREEN_FROM_BAR_PLAN.md

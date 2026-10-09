# Plan: the go-live checklist counts what it renders

**Slug:** `golive-checklist-count`
**Date:** 2026-10-09 12:30:10 +07:00
**Analysis:** `20261009-123010-G6K4_code_analyzer.md`
**Worktree:** `/home/miftah/.worktrees/seer/golive-checklist-count`
**Branch:** `feature/golive-checklist-count` (base: `origin/main` @ `d8c0cab`)
**Phases:** 1
**Status:** planned
**Coordinator:** —

---

## Why

The user's whole prompt was `the bug`, naming the defect reported at the end of the previous
turn. Verbatim:

> **I found a real bug while writing the checklist section, and did not fix it.**
> `web/app/(app)/leaderboard/view.ts:378` has `CHECKS = 6`, but `lib/metrics.ts` `checklist()`
> returns **5** items — the `≥ 100 trades` row went away with the 2026-10-07 revision that
> replaced "≥ 3 months and ≥ 100 trades" with "≥ 18 months". So the page renders 5 rows under a
> score of `x/6`, and `ready` (`items.length === CHECKS`) is unreachable: a strategy that passed
> everything would read 5/6 and never say "Ready for real money". `view.test.ts` misses it
> because `scoreOf` is tested with hand-built 6-element arrays rather than with `checklist()`'s
> output. The fix is probably `CHECKS = 5` plus rewording "all six", but which way it goes is a
> design-§1 call, so I left it alone and wrote the README's table as the five rules the app
> actually checks.

That "design-§1 call" is settled, and not by this plan: design §1 as it stands after the owner's
own §13 revision of 2026-10-07 lists **five** conditions, the backtest gate among them.
`lib/metrics.ts` already implements exactly those five and says so in its own docstring. The
code that disagrees is the display layer, which was never updated. So this is not a decision
about the rules; it is making three stale spellings agree with the rule the owner already set.

## Requirements

| ID | What the user asked for | Phases |
|---|---|---|
| R1 | Fix the reported bug: the Leaderboard scores out of 6 while rendering 5 rows, and can never reach "Ready for real money" | 1 |
| R2 | *Inferred.* The same §13 revision left `/sera/how` saying the paper bar is "At least 3 months and 100 trades"; fix it too, so the app does not state one rule two ways | 1 |

**R2 is an inference and is marked as one.** The user said "the bug", singular. Tracing the
cause (commit `ba8a05b`) showed the same revision left two display spellings behind, not one.
Both are the same defect, in the same package, in one commit's worth of work. To take the literal
reading instead: delete R2 from this table and skip step 5 of the phase plan — nothing else
depends on it.

## Scope

**In scope** — seven files, all in `web/`, all pure TypeScript or markdown:

- the count's single definition, placed beside the list it counts (`lib/metrics.ts`);
- the Leaderboard's score denominator and its "all six" copy (`leaderboard/view.ts`);
- the tests that let the drift through (`leaderboard/view.test.ts`, `lib/metrics.test.ts`);
- two stale docstrings (`lib/golive.ts`, and `view.ts`'s own);
- `/sera/how`'s paper-stage wording (`app/sera/how/view.ts`) — R2;
- `web/package_readme.md`, six stale statements (the sixth found by the phase planner, in Gotchas).

**Out of scope, and why:**

- **Everything under `engine/`.** The engine's `checklist` returns four items on purpose — the
  fifth rule reads `strategies.params.backtest_gate`, a roster fact no backtest can evaluate.
  The engine/web parity test compares labels, not lengths. Nothing there is wrong.
- **The lab's six hurdles.** `lib/sera/derive.ts`'s `CONDITION_KEYS` and
  `app/sera/how/view.test.ts:116`'s `'At least 100 trades'` belong to the **dev gate**, whose
  `gate.minTrades` is still 100 in `data/lab.json`. Two different gates both had a "six" and a
  "100 trades"; only the go-live one changed. Touching the lab's is the main way this goes wrong.
- **`docs/plans/2026-10-03-seer-design.md`.** §1 and §13 are already correct. This change makes
  the code agree with the design, never the reverse.
- **Any threshold value.** 18 months, 20%, 1.3 all stay exactly as they are. Only the *count of
  rules* and the words naming it move.
- **`data/lab.json`, `db/migrations/`, any database read or write.**
- **`package_readme.md`'s `note?: string` on `CheckItem`** (lines ~180 and ~186). The phase
  planner found this documented field no longer exists — a *different* stale revision of the
  same file, from the same week. It serves neither R1 nor R2, so phase 1 preserves those clauses
  verbatim rather than quietly widening the diff; the exact fix is recorded in the phase plan's
  Handoffs for whoever picks it up.
- **`docs/media/leaderboard.png`**, which still shows `1/6`. `docs/` is out of scope; re-shoot it
  with `npm run shoot` after this lands if the screenshot matters.

## Invariants

1. **No file under `engine/` is modified.** A diff touching `engine/` fails this plan.
2. **No threshold changes value.** `MIN_PAPER_MONTHS` stays 18, `MAX_DRAWDOWN` stays 0.2,
   profit factor stays 1.3, `gate.minTrades` stays 100.
3. **The count has exactly one definition in `web/`.** Any other spelling of it must be derived
   from that one, and a test must fail if the definition and `checklist()`'s real length ever
   disagree. A plain `CHECKS = 5` that re-arms the same trap does not satisfy this plan.
4. **`scoreOf` keeps a fixed denominator and its length guard.** `page.tsx` passes `items = []`
   for a strategy with no gate; that must keep reading `0/5` and must never be `ready`.
   `total: items.length` would render `0/0` and is forbidden.
5. **The tree builds and both suites pass at the end of the phase**: `npx tsc --noEmit` clean,
   `npm test` green in `web/`.
6. **No user-visible change beyond the two corrected statements.** Row labels, values, tooltips,
   colours, layout and the month-by-month sheet are untouched.

## Phases

| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID | Card |
|---|-------|-----------|---------|-------|-----------|------------|------|--------|------|
| 1 | Count the rules once, where the rules are | R1, R2 | `web` | 7 | — | NORMAL | `.workflows/plan/golive-checklist-count/phase-1.md` | — | — |

### Phase 1 — Count the rules once, where the rules are

**Satisfies:** R1, R2
**Owns:** `web/lib/metrics.ts`, `web/lib/metrics.test.ts`, `web/lib/golive.ts`,
`web/app/(app)/leaderboard/view.ts`, `web/app/(app)/leaderboard/view.test.ts`,
`web/app/sera/how/view.ts`, `web/package_readme.md`.
**Does not touch:** anything under `engine/`, `db/`, `docs/plans/`, `web/data/`,
`web/lib/sera/derive.ts`, `web/app/sera/how/view.test.ts`, `web/app/(app)/leaderboard/page.tsx`.
**Exit criteria:**
- `web/lib/metrics.ts` exports the rule count beside `checklist`, and `metrics.test.ts` asserts
  `checklist(...)` has exactly that many items.
- `view.ts`'s `CHECKS` is that constant, not a literal, and the "all six" strings are built from
  it so the words cannot outlive the number.
- `view.test.ts`'s `scoreOf` suite drives real `checklist()` output for at least the two cases
  that matter — five passing rules is `ready`, and `[]` is `0/<count>` and not ready — and the
  test that asserted "never ready with fewer than six items" is gone.
- `/sera/how`'s paper stage states design §1's bar in months, with no trades clause, reading
  `MIN_PAPER_MONTHS` rather than a second constant.
- `npx tsc --noEmit` clean and `npm test` green in `web/`.

## Reconciliation Log

single phase — nothing to reconcile.

The phase planner's read of the same files turned up three things this plan's analysis had not,
all inside files phase 1 already owns, so none of them changed the phase boundary:

| Found | Where | Disposition |
|---|---|---|
| a second stale clause, "even if the five forward rules pass" | `leaderboard/view.ts:391` | folded into step 3 — there are four forward rules |
| a sixth stale README statement, "(3 months, 100 trades)" | `package_readme.md:829`, Gotchas | folded into step 7 (R2) |
| an 18-character cap on every pipeline `detail` line | `app/sera/how/view.test.ts:79–85` | the new wording measures 18 / 17 / 13 and fits; that test file stays untouched |

## Decisions

| Fork | Chosen | Rung |
|---|---|---|
| `CHECKS = 5` (literal) vs a count derived from `checklist()` | derived, defined in `lib/metrics.ts` beside the list, pinned by a test | 1: plan invariant 3 — a literal re-arms the exact trap that produced this bug |
| Fixed denominator vs `total: items.length` | fixed, keeping the length guard | 4: the user's raw input names `items.length === CHECKS` as the unreachable condition, not as the thing to delete; `package_readme.md:791` pins the `0/6` empty-gate line |
| Treat the user's "the bug" as one symptom or as its cause | its cause — R1 and R2, with R2 marked inferred and droppable in one line | 5: the user's raw input names design §13 as the origin, and §13's other victim is one line away |
| Is `/sera/how`'s "100 trades" the same stale rule? | **No** for `how/view.test.ts:116` and `derive.ts` (lab dev gate, `minTrades` still 100); **yes** for `how/view.ts`'s `PAPER_TRADES` (design §1 paper bar) | 6: `data/lab.json` `gate.minTrades = 100` is live, so the lab's hurdle is current |
| Whether to re-litigate the rule count against design §1 | not re-litigated: §1 after §13 is five conditions, and `lib/metrics.ts` already implements them | 4: the owner's §13 revision is the authority; the code that disagrees is the display layer |

## Open Questions

None. The rule count was settled by the owner on 2026-10-07; this change only makes three stale
spellings agree with it, and every fork above was decided from a rung of the ladder.

## Rollback

`git revert` of the single commit. Nothing is persisted, migrated or published: the change is
pure TypeScript, its tests, and markdown. Reverting restores a Leaderboard that reads `x/6` over
five rows — the behaviour on `main` at `d8c0cab`.

## Next

Execute the phase:

    /implement -f GOLIVE_CHECKLIST_COUNT_PLAN.md --phase 1

Or put it on the board first (GitHub repos only):

    /create-task --from-plan GOLIVE_CHECKLIST_COUNT_PLAN.md

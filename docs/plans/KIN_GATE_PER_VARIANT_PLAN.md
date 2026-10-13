# Plan: the kin gate reads the book that would actually be tested

**Slug:** kin-gate-per-variant
**Date:** 2026-10-13 10:22:09 +07
**Analysis:** `docs/analyzer/20261013-102209-K2M7_code_analyzer.md`
**Worktree:** `/home/miftah/.worktrees/seer/kin-gate-per-variant`
**Branch:** `feature/kin-gate-per-variant` (base: `origin/main` @ `f390c08`)
**Phases:** 1
**Status:** planned — NOT RECOMMENDED FOR EXECUTION, see Decision D7
**Coordinator:** —

---

## Why

The user's request, verbatim:

> The lab's kin gate blocks every method it has, and the measurement says the block is mostly a
> proxy over-reaching. Change it, as a dated owner revision.
>
> [...] 81 recorded methods. 66 not dev-eligible, 5 fail the folds, 10 are dev-eligible AND clear
> the folds but are blocked by kin. ZERO are promotable. [...] The behavioural arm catches all 10.
> Correlations run 0.889 to 0.983 — these are genuinely the same books, so the 0.85 threshold is
> NOT mis-calibrated. But the gate blocks the whole METHOD when ANY variant is a twin, while a test
> look is spent on ONE variant.
>
> THE CHANGE THE OWNER DECIDED:
> 1. The behavioural arm becomes PER-VARIANT: a method is refused only when the variant that would
>    actually be pre-registered is itself a twin.
> 2. Lineage and ingredients become a PROXY that DEFERS to a clean direct behavioural reading of
>    that promoted variant. [...] MUST FAIL CLOSED [...]
> 3. KIN_CORRELATION 0.85 -> 0.90. The owner was told this admits only M0024 at -4.7% and chose it
>    anyway; record that honestly rather than overstating its value.

The owner's framing in the conversation that produced this: *"i also suspects this kin question.
can we make it 'less strict'?"* — and, when shown that the threshold was sound but the scope was
not, the choice to change both scope and threshold, recorded as a dated revision.

## Requirements

| ID | What the user asked for | Phases |
|---|---|---|
| R1 | The behavioural arm becomes per-variant: refuse only when the variant that would actually be pre-registered is itself a twin | 1 |
| R2 | Lineage and ingredients defer to a clean direct behavioural reading of that variant, and fail closed when the reading cannot be made | 1 |
| R3 | `KIN_CORRELATION` 0.85 → 0.90, recorded honestly as admitting only M0024 at −4.7% | 1 |
| R4 | A dated owner revision in `docs/plans/2026-10-03-seer-design.md` with the measurement as evidence and an explicit statement of what it does not do | 1 |

## Scope

**In scope:**

- `KIN_CORRELATION` 0.85 → 0.90 in `engine/src/seer_engine/lab/hardgate.py`.
- `failed_kin` answers at the granularity of **the book that would actually be tested**:
  the promoted variant must be clean, **and** no fold pick in the method's own fold record may be
  a twin. Lineage and ingredients become a proxy that defers to that direct reading, and block
  exactly as today whenever the reading cannot be made honestly.
- A new `(D16)` section in `hardgate.py`'s module docstring recording the decision, the
  measurement behind it, and the expiry of `(D12)`'s "the cost is identical today".
- Tests for the new rule in `engine/tests/test_lab_hardgate.py`, including the fail-closed path and
  the fold-pick leak.
- `## 16. Revision 2026-10-13 (owner)` in `docs/plans/2026-10-03-seer-design.md`.
- `docs/backtests/2026-10-13-kin-gate-per-variant.md` — the before/after measurement and the
  residual-risk statement.

**Out of scope, and why:**

- **Nothing is promoted and nothing is tested.** This change makes a method *eligible* to be
  promoted; promoting it and spending a test look is a separate, later, owner-initiated act. No
  `lab test`, no `lab promote`, no `engine/.research-test` (Decision D5).
- **`walkforward.py` is not edited.** `(D13)` holds: the buy signal's kin condition widens through
  its caller, and `buy_signal` itself is untouched — exactly as the last two kin revisions left it.
- **`runner.py`, `commands/lab.py`, `prereg.py` are not edited.** They call `failed_kin` and inherit
  its new answer; that is the `(D9)` single-definition property working, and forking a per-variant
  variant of the function for some callers would break it (Decision D2).
- **No recorded row, digest or prereg file changes.** `docs/lab/prereg/MNNNN.md` files already
  written are frozen records of what was true the day the promise was made (`(D3)`); this change
  does not rewrite history, it changes what the gate will say next time.
- **`web/` is not touched and no engine constant is mirrored.** `KIN_CORRELATION` has no `web/`
  twin, so the `test_sean_mirrors.py` rule is not engaged.
- **The §1 real-money bar does not move.**

## Invariants

1. **`failed_kin` stays THE one definition of kin.** `(D9)`/`(D13)`. Its four callers —
   `hardgate.check` (`:1527`), `family_state` (`:1194`), `runner.py:907`, `commands/lab.py:2429` —
   must keep giving the same answer about one method. Do not add a second function that some
   callers use and others do not.
2. **The gate fails closed.** Whenever the behavioural reading cannot be made honestly — no
   benchmark, a curve on other or unknown prices (the existing `(D10)` refusal), fewer than
   `MIN_KIN_MONTHS` shared months, or `promoted_variant` returning `None` or raising — provenance
   blocks exactly as it does today. A rule that reads "clean" because it could not measure is the
   one failure mode worse than being too strict.
3. **No recorded row is edited.** `trials`, `trial_*`, `methods`, `insights`, `method_folds` and
   the written prereg files are append-only.
4. **No recorded `config_digest` moves.**
   `test_lab_methods.py::test_every_recorded_configuration_still_digests_to_its_recorded_digest`
   is the tripwire and must stay green.
5. **The test window is never read.** No `lab test`, no `lab promote`, no `--store` pointing at
   `engine/.research-test`, and `store.test_looks(conn)` reads 4 before and after.
6. **`lab.sqlite` migrates on connect, even for a read.** Use `sqlite3 'file:lab/lab.sqlite?mode=ro'`
   or `store.connect_readonly`. If the file is dirtied, restore it by path — it carries no change
   this phase is entitled to make.
7. **The suite is green and the skip count is quoted beside the pass count.** Run as
   `cd <worktree>/engine && PYTHONPATH=<worktree>/engine/src
   PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres
   /home/miftah/seer/engine/.venv/bin/python -m pytest -q`. Baseline at `f390c08` is
   **4725 passed, 3 skipped** (the three opt-in `*_LIVE` sweeps). Without `PG_TEST_URL` 385 tests
   skip silently and CI fails; without `PYTHONPATH` pytest imports the main checkout.
   Lint with `ruff check engine` (CI is bugs only: E9 and F, minus F401).
8. **Modules carry prose docstrings that argue for the shape of the code.** `hardgate.py` keeps a
   numbered decision record; the new rule gets `(D16)` in that style, not a code comment.
9. **Owner-facing text is plain.** The design-doc revision and the write-up carry no digests or
   code identifiers where a sentence will do.
10. **`argparse` `help=` strings are %-interpolated**: a literal `%` must be written `%%`. (No CLI
    change is planned, but the write-up quotes percentages into prose, not into `help=`.)

## Phases

| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID | Card |
|---|-------|-----------|---------|-------|-----------|------------|------|--------|------|
| 1 | The kin gate reads the book that would actually be tested | R1, R2, R3, R4 | `engine/lab`, `docs` | 4 | — | HARD | `.workflows/plan/kin-gate-per-variant/phase-1.md` | — | — |

### Phase 1 — The kin gate reads the book that would actually be tested
**Satisfies:** R1, R2, R3, R4
**Owns:**
- `engine/src/seer_engine/lab/hardgate.py` — `KIN_CORRELATION` 0.85 → 0.90; the new rule inside
  `failed_kin`; a `(D16)` module-docstring section.
- `engine/tests/test_lab_hardgate.py` — tests for the new rule.
- `docs/plans/2026-10-03-seer-design.md` — a new `## 16. Revision 2026-10-13 (owner)` section,
  appended after `## 15.`; nothing above it is edited.
- `docs/backtests/2026-10-13-kin-gate-per-variant.md` — new.

**Does not touch:** `walkforward.py`, `runner.py`, `commands/lab.py`, `prereg.py`, `store.py`, any
method file, `lab/lab.sqlite`, `web/`, any recorded row or written prereg file.

**Exit criteria:**
1. `KIN_CORRELATION == 0.90`.
2. `lab walkforward` re-run over all 81 methods shows **ZERO methods become promotable** and the
   verdict column changes on exactly two rows (M0024 `kin already failed` → `fails the folds:
   2 of 4`; M0053's kin list narrows to M0002). No buy signal fires; 24 of 81 still beat the
   benchmark in a majority of folds. Quote the before/after diff. **See Decision D7 — this is the
   measured effect, and it is nothing.**
3. A test proves the fold-pick leak is closed: a method whose promoted variant is clean but whose
   fold record was won by a twin is still refused.
4. A test proves the fail-closed path: when the behavioural reading raises `(D10)` or
   `promoted_variant` is `None`, provenance blocks.
5. All four callers still agree — one definition, demonstrated by a test that asks
   `check`, `family_state` and the buy-signal path about the same method and gets consistent
   answers.
6. The digest tripwire green; `store.test_looks(conn)` reads 4 before and after;
   `git status --short lab/ web/data/` empty.
7. `ruff` clean; suite green with the skip count quoted beside the pass count.
8. The design-doc revision states what the change does **not** do, and the write-up states the
   residual risk in the owner's plain language.

## Reconciliation Log

single phase — nothing to reconcile

## Decisions

Rungs: **1** stated invariant · **2** phase exit criteria / a measurement · **3** the plan's code
blocks · **4** the index's Why and Requirements · **5** the user's raw input · **6** surrounding
convention.

| # | Fork | Choice | Rung |
|---|---|---|---|
| **D1** | The user specified "refuse only when the promoted variant is a twin". Measurement M5 shows that rule would free M0030 and M0053 on fold records **won by their twins** — M0053's promoted variant never won a fold. Follow the instruction literally, or close the leak? | **Close the leak.** The rule is: the promoted variant must be clean **AND** no fold pick may be a twin. The user's own binding constraint is that this must not launder a failed book into a fresh test look, and `(D12)`'s surviving reason — *"every variant is a candidate in every fold's pick"* — is exactly this hazard, stated by the original design. Freeing M0053 on a 0.922 twin's four fold wins would defeat the purpose the user gave for the change. | **5**, then **2** — the user's own constraint ("that is a separate, later act"; the residual-risk requirement), against measurement M5. |
| **D2** | Keep one `failed_kin`, or add a per-variant sibling that only `check` calls? | **One function.** `(D9)`/`(D13)` make the single definition a stated invariant: two commands giving opposite answers about one method is worse than either answer. The per-variant logic goes *inside* `failed_kin`. | **1** — invariant 1. |
| **D3** | `promoted_variant` returns `None` for M0019 and M0044. Read that as "no twin, therefore clean", or as "cannot tell, therefore blocked"? | **Blocked.** A method with no promotable variant has no book that would be tested, so the question the new rule asks has no answer — and the gate's standing behaviour on an unanswerable question is to refuse (`(D10)`). It also costs nothing: both are blocked for other reasons today. | **1** — invariant 2, fail closed. |
| **D7** | **The whole change frees nothing.** After the plan was drafted, `behavioural_kin` was found to report only the BEST-correlating variant per failed book, so every earlier "clean promoted variant" reading was a membership test against a set that never held runners-up. Correlated directly: `M0020-W-NOSTOP` is **0.9385** against M0021 and **0.9329** against M0029; `M0030-C50T` is **0.9620** against M0029. Both are twins at any threshold this plan contemplates. `M0053` and `M0024` are clean on the promoted variant but blocked by condition (b) / the fold majority. Measured end to end: **0 methods become promotable, no buy signal, a 2-row cosmetic verdict diff.** | **Do not execute without a fresh owner decision.** The plan is kept as the record of a measurement, not as work to do. Shipping it would retire a recorded decision `(D12)`, add a subtler rule a future reader can get wrong, and buy nothing. The finding it produced is the valuable part: the lab is blocked because its methods genuinely ARE the same few books — 0.93 to 0.96 correlated with books that already failed — not because the gate over-reaches. | **2** — a direct measurement beats the indirect one it corrects. |
| **D4** | Report the change as freeing three methods (what the user was told) or one (what the coherent rule frees)? | **One, stated plainly, with the other two named and the reason given.** M0020 is freed; M0024 is freed only by the threshold move and has a −4.7% post-2009 edge. M0030 and M0053 stay blocked on their fold records. The write-up says so rather than quoting the earlier three-method figure. | **2** — measurement M5 beats the estimate it corrects. |
| **D5** | The change makes M0020 promotable. Promote it in this phase? | **No.** The user's constraint is explicit: *"This change makes methods promotable; it does NOT promote or test any of them. That is a separate, later, owner-initiated act."* A test look is spend-once and there are four already gone. | **5** — the user's raw input. |
| **D6** | Where does the `(D16)` record go — a code comment, or the module docstring's numbered decision record? | **The module docstring**, extending the `(D1)`…`(D15)` series, and it must name `(D12)`'s expired premise explicitly rather than silently contradicting it. | **6** — the module's own convention. |

## Open Questions

**None.** Every fork was decided above. The one irreversible act in this area — spending a test
look — is explicitly out of scope (D5), so no branch of any decision here is irreversible: the
whole phase is one commit that `git revert` backs out.

## Rollback

- The phase is one or more commits bounded by an explicit pathspec, so `git revert <sha>` backs it
  out. **Never** `git reset --hard` in this worktree.
- Nothing in the lab database changes, so there is no schema or record to unwind. Reverting the
  source restores the old gate answer exactly, because `failed_kin` is a pure read.
- The design-doc revision is append-only prose; reverting the commit removes the section. If the
  change is reverted *after* a method has been promoted under it, the promotion stands as a
  recorded fact and the revision section must stay, with a newer revision explaining the reversal
  — the design doc is a record, not a current-state file.

## Next

Execute the phase:

    /implement -f docs/plans/KIN_GATE_PER_VARIANT_PLAN.md --phase 1

Or put it on the board first (GitHub repos only):

    /create-task --from-plan docs/plans/KIN_GATE_PER_VARIANT_PLAN.md

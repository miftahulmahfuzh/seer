# Code Analysis: lab book twins (one book recorded under many candidate ids)

**Type:** Bug Investigation (with a Feature Update to the reporting surfaces)
**Date:** 2026-11-06 15:10 WIB
**Session ID:** 20261106-151026-T7WN
**Plan:** `.workflows/plan/LAB_BOOK_TWINS_PLAN.md` (3 phases)
**Worktree:** `/home/miftah/.worktrees/seer/lab-book-twins`, branch `feature/lab-book-twins` (base `origin/main` @ `3b87070`)

---

## User Input

### Original User Request
```
/analyze docs/plans/2026-11-06-handover-repeated-control-arms.md
```
The handover file is the specification. It was untracked in the main checkout and has been
copied verbatim into this worktree at `docs/plans/2026-11-06-handover-repeated-control-arms.md`.
Its "What to analyze and fix, robustly" section, verbatim:

> 1. **Identity of a book, apart from the method that wraps it.** The goal is to detect that a
>    candidate is behaviourally the same book as a recorded trial (same targets on every decision
>    date on the same store), not just the same params text. Options to weigh:
>    - a canonical "effective config" digest (strip inert wrapper fields, for example `mode=never`
>      makes the watch fields dead),
>    - a result fingerprint (curve hash and trade count) checked after the run,
>    - or a cheap pre-run probe of targets on a sample of dates.
>    Decide what happens on a match: reuse the recorded trial as the control (with provenance), or
>    run it anyway and mark it a duplicate. **Constraints:** the protocol requires controls to run
>    beside the treatment, so a reused control must stay attached to the new method. N policy
>    counts methods, not arms (memory `seer-lab-n-policy-overcounts-looks`). Closed records and
>    existing digests are frozen: never rewrite trials 1536/1674/1734.
> 2. **Reporting surfaces that present a control as a new candidate.** The calculate-assets skill
>    ran the "main + control" arms and Sera relayed the control's money as if it were a new book.
>    Related known gaps: `lab promote` and `best_dev_eligible` have no role filter (memories
>    `seer-promoted-variant-can-be-a-control-arm`,
>    `seer-promote-has-no-role-filter-for-diagnostic-arms`). Check whether one role-aware
>    "is this a control, and is it a book already recorded?" helper should feed promote,
>    calculate-assets, `lab status` near-miss lists and the Sera skill.
> 3. **Sera's slate selection.** The sera-the-explorer skill picks follow-ups from the backlog
>    without asking whether a new method's arms re-measure a recorded book. Decide whether the
>    skill or `lab idea` should warn.
> 4. **A related reproducibility question (cause unverified).** COSK (M0179-N20) read
>    Rp 1,783.1M to 2026-10-06 in an earlier session's run and Rp 1,819.7M to 2026-10-08 today,
>    while LONGHAUL, STAYPUT and DEEPTAPE all ended lower than before. [...] Re-run COSK to
>    2026-10-06 and say whether calculate-assets output changed for a fixed end date (store
>    change, code change, or nondeterminism).
>
> Follow CLAUDE.md: smallest change that fixes it, prove it with the `verify-seer` skill, keep
> `lab.sqlite` append-only, and use explicit pathspecs when committing.

### User-Provided Files
- `docs/plans/2026-11-06-handover-repeated-control-arms.md`

### Requirement IDs

| ID | What the user asked for |
|---|---|
| R1 | Detect that a candidate is behaviourally a book the lab already recorded, and decide what happens on a match, without touching frozen records |
| R2 | Stop reporting surfaces (promote, calculate-assets, `lab status`, the Sera relay) presenting a control or an already-recorded book as a new candidate |
| R3 | Decide whether Sera's slate selection (skill or `lab idea`) warns about arms that re-measure a recorded book |
| R4 | Re-run COSK to 2026-10-06 and say whether calculate-assets output changed for a fixed end date |

---

## Detailed Requirements Understanding

**Problem.** A trial's identity is `config_digest` = sha256 of `rules`, `allocator.id` and
`params` text (`engine/src/seer_engine/lab/method.py:43-51`). Every follow-up method that wraps a
host book in its own allocator class (`WatchedVolumeBookAllocator.id = "M0442"`,
`m0442_curve_watch_on_size_weighted_book.py:87`) and its own params dataclass
(`WatchHostParams`, `DeepWatchParams`) gives the *same book* a new digest. The only re-run guard,
`runner.preflight` (`runner.py:331-337`) and `UNIQUE(config_digest, window)` (`trials` schema),
compare digests, so they never fire.

**Measured on the committed `lab/lab.sqlite` this session** (sha3 of `curve_json`, grouped by
window + `trades`):

- 1,739 trials (1,734 dev, 5 test). Under the plan's twin definition (same window, same trades,
  byte-identical curve, any store): **80 groups, 260 rows, 180 duplicate rows.** Restricted to
  one store fingerprint: 74 groups, 195 rows, 121 duplicates. The duplicates span the lab, not just M0442/M0447/M0488 (largest group: 14
  momentum hosts, `M0387-ADJ20 ... M0362-BASE`).
- The handover's book has **four** recordings, not three: `M0125-DV-C10` (trial 519, store
  `77c37d55…`, run 2026-10-16) carries the same curve hash `BA11D768…`, total_return
  249.05533983053, 1210 trades, as trials 1536/1674/1734 (store `640fc25e…`). So identical curves
  occur across store fingerprints too.
- **Treatment arms identical to their own control.** `M0447-DVC10-RECOVER` and
  `M0447-DVC10-RECOVER-CAP730` = `M0447-DVC10-NEVER`; `M0447-SQRT-RECOVER` = `M0447-SQRT-NEVER`.
  The treatment never acted. `M0488-DVC10-DEEP10/15/20` and `DEEP15-NOFALL730` are one curve
  (`964AB029…`): the dose ladder never moved.
- **The promotable arm is a cross-method twin of a treatment.** M0447 and M0488 are both
  `dev-eligible`, and their highest-MAR eligible arm is `DVC10-FIXED730` (MAR 0.53, curve
  `733CF0AB…`), the same curve as `M0442-DVC10-FIXED730`. Three dev-eligible methods, one book.

**What must change.**
1. A "book twin" reader: for any trial, the earliest recorded trial with the same window, same
   `trades` and byte-identical `curve_json`, with both store fingerprints reported.
2. `lab run` names twins after the run (same-method twins as "these arms are one book", inert
   treatment called out; cross-method twins as "first recorded as X").
3. `lab status` near-miss / closest-to-eligible rows show an arm's role and twin.
4. `lab promote` refuses when the arm it would pre-register is a twin of an earlier method's
   recorded trial or of a same-method control arm.
5. calculate-assets labels a control arm as a control and names the first-recorded twin.
6. Sera skills: never relay a control's money as a new book; read the twin line.

**Success criteria.** `lab run` of a method whose arm repeats a recorded book prints the twin
with provenance; `lab promote M0488` (and M0447) refuses naming `M0442-DVC10-FIXED730`;
`lab status` near-miss rows tag roles/twins; calculate-assets on `M0488-DVC10-NEVER` prints that
it is a control and the same book as `M0125-DV-C10`; no trial, digest or frozen file changes.

**Constraints/assumptions.** Nothing is written to `lab.sqlite`: twin-ness is *derived on read*
from `curve_json`, which every trial already carries, so all 180 existing duplicate rows (any store) are covered
retroactively and no schema migration is needed. calculate-assets may not open the DB through
`lab.store` (it migrates on connect, SKILL rule 4), so it opens `lab/lab.sqlite` with
`file:...?mode=ro` and calls the same pure reader.

### R4 — measured here (no phase needed)

`calculate_assets.py M0179-N20 1-4-2018 6-10-2026`, run in this session from `3b87070` against
`engine/.research-test` (files dated 2026-10-19, unchanged since):
**Rp 1,783,094,603** real-rupiah, SPY Rp 1,292,101,103, 182 trades, 31.0% fall. That is
note J-60F's earlier "Rp 1,783.1M to 2026-10-06" exactly. The same command to 8-10-2026 gives
**Rp 1,819,685,721**, J-60F's today figure, exactly. So output for a fixed end date did not
change: no store change, no code change (the one engine change since, `a6322d7` 2026-11-05,
touches bracket sizing only, and M0179 runs on the book engine), no nondeterminism. COSK's book
rose about 2.05% over the two sessions 2026-10-07/08 while the SPY line fell about 0.2%.
J-60F's caveat "differed ... by more than two sessions of market move would explain" is wrong.
Correcting that note is the owner's call; the plan does not edit notes.

---

## Analysis Scope

### Explicitly Mentioned Files
- `engine/src/seer_engine/lab/runner.py` (`preflight` 263-338, digest check 331-337)
- `engine/src/seer_engine/lab/methods/m0442_*.py`, `m0447_*.py`, `m0488_*.py`, `m0125_index_book_volume_weight.py`
- `.claude/skills/calculate-assets/calculate_assets.py`, `SKILL.md`
- `.claude/skills/sera-the-explorer/SKILL.md`

### Discovered Related Files
- `engine/src/seer_engine/lab/method.py:43-51` — `config_text`/`config_digest`
- `engine/src/seer_engine/backtest/dev.py:180-211` — `Candidate` (`rationale` outside the digest)
- `engine/src/seer_engine/lab/control_shape.py:587` — `role_of(arm)`: control/dose/idea/treatment from rationale; pure, opens nothing
- `engine/src/seer_engine/lab/hardgate.py:1076` `promoted_arm_role`, `:1943` `check` (D18 control refusal at ~2021-2052)
- `engine/src/seer_engine/lab/store.py:1367` — `best_dev_eligible` (no role filter, by design; D18 lives in `check`)
- `engine/src/seer_engine/lab/books.py` — distinct-book counting by lineage + residual correlation (presentation only)
- `engine/src/seer_engine/commands/lab.py:983` `_status`, `:1879` `_run` (post-run annotations: walk-forward, control shape, mirror pairs), `:2099` `_promote`, `:2808` `_arm_roles`, `:235` subparsers
- `.claude/skills/verify-seer/features/lab-cli.md` — feature-map entry for the lab CLI
- `.claude/skills/explore-and-experiment-new-method/SKILL.md` — Sera children run this
- `engine/tests/test_lab_control_shape.py`, `test_lab_hardgate.py`, `test_lab_books.py`

---

## Current Dataflow

### Entry: `lab run MNNNN` (`commands/lab.py:_run`)
1. `runner.preflight` (`runner.py:263`): commit check, cost check, status check, then for each
   candidate `store.has_trial(conn, config_digest(c), "dev")` → refusal "repeats X". Digest only.
2. `research.load_store`, `hardgate.pin_dev_store`, `preflight_data`.
3. `runner.run_method` backtests every arm and inserts one `trials` row each (with `curve_json`,
   `trades`, `store_fingerprint`); `UNIQUE(config_digest, window)` is the DB backstop.
4. Prints `_show`, walk-forward, control shape (`control_shape.for_method`), mirror pairs
   (`dressing.survey`). Each annotation is a forwarder wrapped in try/except; none gates (D15).
   **Nothing compares the new curves with recorded ones.**

### Entry: `lab promote MNNNN` (`_promote` → `prereg.promote_method` → `hardgate.check`)
`store.best_dev_eligible` picks the highest-MAR eligible dev arm with no role filter;
`hardgate.check` refuses on folds (D11), control role (D18, via `promoted_arm_role` reading the
method file's rationale), survivorship fall (D16), etc. **Nothing asks whether that arm's book
was first recorded by a different method.**

### Entry: `lab status` (`_status`)
"Near misses" (top 12 by MAR beating SPY) and "Closest to eligible" (8) list raw trial rows by
`candidate_id`; no role, no twin.

### Entry: calculate-assets (`calculate_assets.py main`)
`resolve(target)` → `discover()` method files → `realistic()` swaps to fractional/Gotrade or a
registered twin by name → runs on the test store → prints money. Never opens `lab.sqlite`.
**Prints nothing about the arm's role or whether its book is already recorded elsewhere.**

### Sera skills
`sera-the-explorer` picks slates from the backlog; children run
`explore-and-experiment-new-method`, which reports arms' money/metrics to the coordinator. No
step asks about controls or twins.

### Data persistence
`lab/lab.sqlite` `trials` (append-only by trigger, `UNIQUE(config_digest, window)`,
`UNIQUE(candidate_id, window)`). `curve_json` text is the equity curve; byte-identical text ⇔
identical book outcome on that window.

---

## Key Data Structures
- `trials` row: `n, method_id, candidate_id, config_digest, window, store_fingerprint, trades, curve_json, mar, ...`
- `Candidate(id, family, rules, allocator, params, rationale, ...)` — `rationale` is the role source.
- `control_shape.ROLE_CONTROL/DOSE/IDEA/TREATMENT`.

## Dependencies
`SEER_LAB_DB` (lab DB path), `engine/.research-test` (calculate-assets), Python sqlite3 (sha256 done in Python; `sha3()` used above is the sqlite3 CLI's extension and is NOT available to `sqlite3` in Python).

---

## Reference List

| Symbol / key | File:line | Kind | Package |
|---|---|---|---|
| `config_digest` | `lab/method.py:50` | def | lab |
| digest re-run refusal | `lab/runner.py:331` | call | lab |
| `role_of` | `lab/control_shape.py:587` | def | lab |
| `promoted_arm_role` | `lab/hardgate.py:1076` | def | lab |
| D18 control refusal | `lab/hardgate.py:~2021` | call | lab |
| `best_dev_eligible` | `lab/store.py:1367` | def | lab |
| `_run` annotations | `commands/lab.py:1879-2096` | call | commands |
| `_status` near misses | `commands/lab.py:1003-1023` | call | commands |
| `_arm_roles` | `commands/lab.py:2808` | def | commands |
| `resolve`/`main` | `.claude/skills/calculate-assets/calculate_assets.py:144,404` | def | skill |
| lab CLI feature map | `.claude/skills/verify-seer/features/lab-cli.md` | doc | skill |

## Impact Points (files that WILL need changes)
1. `engine/src/seer_engine/lab/twins.py` (new) — the derived twin reader. Phase 1.
2. `engine/tests/test_lab_twins.py` (new) — Phase 1.
3. `engine/src/seer_engine/commands/lab.py` — `lab run` annotation, `lab twins` subcommand, `lab status` tags. Phase 1.
4. `engine/src/seer_engine/lab/hardgate.py` — D19 promote refusal. Phase 1.
5. `engine/tests/test_lab_hardgate.py` — D19 tests. Phase 1.
6. `.claude/skills/verify-seer/features/lab-cli.md` — feature map. Phase 1.
7. `.claude/skills/calculate-assets/calculate_assets.py`, `SKILL.md` — role + twin label. Phase 2.
8. `.claude/skills/sera-the-explorer/SKILL.md`, `.claude/skills/explore-and-experiment-new-method/SKILL.md` — Phase 3.

**This document describes. The plan files prescribe.**

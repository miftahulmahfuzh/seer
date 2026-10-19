# Plan: Honest controls — re-draw the arms D17 refuses, as amendments under nine existing ids

**Slug:** honest-control-redraw
**Date:** 2026-10-19 18:17:12
**Analysis:** `docs/analyzer/20261019-181712-C4K9_code_analyzer.md`
**Worktree:** `/home/miftah/.worktrees/seer/honest-control-redraw`
**Branch:** `feature/honest-control-redraw` (base: `origin/main` @ `465fcfd`)
**Phases:** 8
**Status:** reconciled
**Coordinator:** —

---

## Why

> Re-draw the thirteen mis-shaped control arms that D17 refuses, as amendments under the nine existing method ids — M0047, M0201, M0202, M0208, M0215, M0221, M0225, M0227, M0243.
>
> Why this is worth doing and why it costs no method id: `lab control` on the nine (run read-only 2026-10-19, output below) reports thirteen control arms outside D17's [0.50, 2.00] refuse band on trades or turnover. `lab promote` refuses a method holding one, so nine dev-eligible methods are blocked, and every sentence already written about one of those margins was quoted against a handicapped opponent. The remedy is an `Amendment` block on the existing method file, which appends trials under the same `method_id` and costs no new method id and no extra N.
>
> Read first: docs/plans/HANDOVER_20261019-the-gate-reading-cadence.md (leftover item 1 is this job), engine/src/seer_engine/lab/control_shape.py, engine/src/seer_engine/lab/hardgate.py (D17), and `Amendment` in engine/src/seer_engine/lab/method.py.
>
> The measured state, from `lab control M0047 M0201 M0202 M0208 M0215 M0221 M0225 M0227 M0243`:
>
>     method  control               controls        trades x  turnover x  verdict
>     M0047   M0047-PLC1-MV10       M0047-EQ            0.55        0.50  refuse
>     M0047   M0047-PLC1-MV20       M0047-EQ            0.55        0.51  warn
>     M0201   M0201-PLC1-MV10       M0201-Y20-MV10      2.27        2.13  refuse
>     M0201   M0201-PLC2-MV10       M0201-Y20-MV10      2.26        2.12  refuse
>     M0202   M0202-PLC1-HALF       M0202-Y20-HALF      2.25        2.01  refuse
>     M0202   M0202-PLC2-HALF       M0202-Y20-HALF      2.25        1.99  refuse
>     M0202   M0202-PLC1-HALF-FAST  M0202-Y20-HALF      2.25        2.20  refuse
>     M0208   M0208-HASH-N20        M0208-CGO-N20       4.41        5.20  refuse
>     M0215   M0215-HASH            M0215-CTRL          0.34        0.43  refuse
>     M0215   M0215-HASH-CAP4       M0215-CTRL          0.34        0.43  refuse
>     M0221   M0221-R50             M0221-C50           0.21        0.50  refuse
>     M0225   M0225-R50             M0225-C50           0.19        0.42  refuse
>     M0227   M0227-R20             M0227-S20           0.07        0.12  refuse
>     M0243   M0243-NEAR20-R        M0243-NEAR20        3.01        2.98  refuse
>
> They split into two structurally different failures and the plan should treat them as two families, not thirteen one-offs: five controls trade TOO LITTLE (0.07x-0.55x: M0227, M0225, M0221, M0215, M0047) and four trade TOO MUCH (2.25x-5.20x: M0202, M0201, M0243, M0208). A re-draw rule that fixes one family will not fix the other.
>
> The hard part, and what phase 1 must settle before anything is pre-registered: there is probably ONE reusable way to derive a shape-matched control, and getting it wrong in nine parallel sessions is the expensive failure. The established rule in this lab is to derive the control's name count and stickiness from the real book's OWN calendar each rebalance rather than fixing them (see memory seer-placebo-matched-to-a-books-exact-shape and M0241's SPLIT12 placebo, which matched name-for-name every month and split a 3.8 pt lead into 1.9 shape and 1.9 signal). Prove the rule lands inside the [0.80, 1.25] MATCH band — not merely inside the refuse band — on one pilot method before fanning out.
>
> Cautions the plan must carry:
>
> - Adding an `Amendment` block must NOT move any existing candidate's recorded `config_digest`. `prereg.check_source` and `test_every_recorded_configuration_still_digests_to_its_recorded_digest` enforce it. A new control that needs a new params field must be wrapped behind a NEW allocator id local to the method file — never by adding a field to a shared params dataclass, which moves every recorded digest in the lab (memory: seer-shared-params-cannot-gain-a-field).
> - `Method.__post_init__` refuses a candidate id OR a configuration that any other variant of the method already uses, original or amendment. The re-drawn control must differ in configuration from the one it replaces.
> - D17 classifies by the candidate's `rationale` PROSE, never an id suffix, and it classifies dose-response BEFORE placebo — a dose-response arm carries no ratio at all and reads `not-checked`. Phrasing a re-drawn control as dose-response would make the refusal disappear without fixing anything. That is gaming the check, and the plan must forbid it explicitly.
> - Amendment candidates are capped at 1..6 PER AMENDMENT (not per method lifetime), and the commit that adds the block is the pre-registration — `lab run --amend` refuses an uncommitted or dirty file. `why`, `hypothesis` and `expected_failure` are written before any result is seen.
> - M0225 already carries an amendment (seq 1, 2026-10-18); M0030 and M0053 carry the other two. Check `method_amendments` for each of the nine rather than assuming seq 1, and remember `store.latest_source_sha` reads the newest amendment row before `methods.source_sha`.
> - Quote `trial_funding.mwr` (what `lab show` prints as "your money earned") and never `total_return` or `cagr`: these books are funded with the owner's monthly top-up and the curve-shape columns count his deposits as gains.
> - A re-drawn control may well make a method's recorded margin WORSE or reverse it. That is the point and it must be reported as the finding, never tuned away. Re-drawing until a margin survives is exactly what design section 4 forbids.
> - Do not spend a test-window look. Four are spent and all four failed. `lab test` is never invoked and `SEER_RESEARCH_TEST_STORE` is never read.
>
> Environment: `SEER_LAB_DB=/home/miftah/seer/lab/lab.sqlite`, `SEER_RESEARCH_STORE=/home/miftah/seer/engine/.research`, never rebuild a store. A read-only `sqlite3 "file:...?mode=ro"` query never migrates the database; any `lab` command does, so hash before and restore by path after. `lab stage` targets the main checkout and its commit takes no pathspec. Never judge a `lab` command by a piped exit code.
>
> Scope note for the phase split: nine methods is too many to design nine times. Expect a pilot phase that settles the re-draw rule on the single clearest case and proves it inside the match band, then a fan-out across the rest, then one close-out that reports which of the nine standing verdicts actually survived their honest control.

## Requirements

| ID | What the user asked for | Phases |
|---|---|---|
| R1 | Settle ONE reusable way to derive a shape-matched control, and prove it inside the [0.80, 1.25] MATCH band on a pilot before anything else is pre-registered | 1 |
| R2 | Re-draw every mis-shaped control arm as an `Amendment` under the nine existing method ids — no new method id, no extra N, no moved `config_digest`, no test-window look | 1, 3, 4, 5, 6, 7 |
| R3 | Report which of the nine standing verdicts survive their honest control, in `trial_funding.mwr`, including margins that worsen or reverse | 1, 3, 4, 5, 6, 7, 8 |
| R4 | *(derived — see Decisions)* `lab promote` must actually stop refusing the nine | 1, 2, 8 |

R4 gains phase 1 in reconciliation. The supersession rule is an **explicit declaration** made by
the re-drawn arm, so the half of R4 that lives in a method file — `Candidate.supersedes`, and the
fourteen declarations that use it — is created by phase 1 and written by phases 1 and 3–7. Phase
2 owns the rule that reads it; phase 8 proves the nine are unblocked. No phase's `Satisfies` was
widened to legalise a step: the step moved, and so did the id.

## Scope

**In scope**

- One new helper module, `engine/src/seer_engine/lab/control_draw.py`, holding the matched-draw
  rule and nothing else.
- Nine `Amendment` blocks, one per method, carrying **fourteen** re-drawn control arms
  (thirteen that refuse plus `M0047-PLC1-MV20`, which only warns but is the twin of a refused arm
  on the same book).
- Nine `lab run --amend` dev runs.
- One change to D17's refusal rule so a book that now holds an honest control is not refused on
  account of a worse earlier draw it has already replaced (R4), plus its tests.
- **One trailing defaulted field on `backtest.dev.Candidate`** — `supersedes: tuple[str, ...] =
  ()` — which is how a re-drawn arm declares what it replaces, and the fourteen declarations that
  use it. Phase 1 creates the field and validates it; phase 2 reads it duck-typed. It is outside
  `config_digest` by construction and moves no recorded digest (invariant 1, and the `_canon`
  grep in phase 1's Step 5a).
- **No new params dataclass anywhere.** Each re-drawn arm reuses the params value of the arm it
  replaces and is made distinct by its new allocator id alone (invariant 12).
- Seven `phase-N-results.md` files, one per method phase plus the pilot's, which is also the
  GO/STOP gate (invariant 15).
- One close-out document, the two `lab stage` runs that commit the database and
  `web/data/lab.json`, and the merge to `main`.

**Out of scope, and why**

- **Any test-window look.** `lab test` is never invoked; `SEER_RESEARCH_TEST_STORE` is never read.
  Four looks are spent and all four failed.
- **Any store rebuild.** Both research stores are read as they are.
- **Any new method id.** An amendment appends under the existing id and the luck gate's N does
  not move.
- **Moving `WARN_BAND` or `REFUSE_BAND`.** The bands are calibrated on the lab's own arms; this
  plan works to the band, never on it.
- **Promoting anything.** The plan measures and unblocks; whether a method is then promoted is
  the owner's call on a separate day.
- **`web/`.** Grepped 2026-10-19: nothing under `web/` references `control_shape`, `controlShape`
  or `mis_shaped`. D17 has no web surface.
- **M0030 and M0053**, the lab's other two amended methods. Not blocked, not in the nine.

## Invariants

Every phase holds all of these. A phase that cannot is a phase that stops and says so.

1. **No recorded `config_digest` moves.** No field is added to, removed from or reordered in any
   existing params dataclass — `registry._canon` renders a dataclass by `dataclasses.fields()`,
   not by `as_dict()`, so even a defaulted field local to one method file moves every digest that
   used it. `engine/.venv/bin/pytest engine/tests/test_lab_methods.py` is green at the end of
   every phase, including
   `test_every_recorded_configuration_still_digests_to_its_recorded_digest`.
2. **The commit is the pre-registration.** `why`, `hypothesis` and `expected_failure` — including
   the predicted *direction* of the margin move — are written and committed **before**
   `lab run --amend` is invoked. `registry_problem` refuses a dirty or untracked method file.
3. **No re-drawn control is phrased as a dose-response arm.** Every re-drawn arm's `rationale`
   carries a `DRAW_MARKERS` phrase (`"placebo"`, `"hash-drawn"` or `"hash order"`) and **none** of
   `DOSE_MARKERS` (`"dose-response"`, `"dose:"`, `"and not since"`, `"and none since"`,
   `"does the date do any work"`, `"on the date itself"`). Making the refusal vanish by wording is
   gaming the check and is forbidden outright.
4. **One re-draw per book.** A second amendment on the same book is admissible only when the
   *shape* missed `WARN_BAND`, never because the margin came out wrong. A margin that worsens or
   reverses is the finding and is reported as such (design §4).
5. **Money is `trial_funding.mwr`.** Never `total_return`, never `cagr`, never a fold's
   `its return`. SPY TR on the same deposits is 7.19%/yr for every trial in this set.
6. **No test-window look.** `lab test` is never invoked; `SEER_RESEARCH_TEST_STORE` is never read;
   `control_shape.WINDOW` stays `'dev'`.
7. **The lab database is touched by `lab` commands only.** Any read for reporting uses
   `sqlite3 "file:/home/miftah/seer/lab/lab.sqlite?mode=ro"`. Before and after any `lab` command,
   `git hash-object lab/lab.sqlite` is recorded; a `lab` command migrates on connect, so a
   read-only inspection must not be done with one. A `lab` command's exit code is never judged
   through a pipe.
8. **`lab stage` runs in phase 8 only, after the merge to `main`, and it runs TWICE there.** No
   phase before 8 runs it at all, and the snapshot test is red mid-batch by design — no phase
   before 8 may try to make it green. Inside phase 8 the order is fixed and the draft index had
   it wrong: **merge → read-only verification sweep → `lab stage` → the full suite → the four
   `lab insight` rows → `lab stage` again → write the handover → commit → push.** The suite sits
   *after* the first staging because `test_the_committed_snapshot_is_the_export_of_the_committed_database`
   is red by construction until `web/data/lab.json` has been regenerated — the draft's "pytest
   green on main after the merge" was an unsatisfiable guard. The second staging exists because
   the insights are journalled after the first one and `web/data/lab.json` must carry them;
   phase 8's final snapshot-agreement check against the committed pair is what enforces it. And
   the closing suite runs with **`PYTHONPATH=/home/miftah/seer/engine/src`**, the *main*
   checkout: `config.REPO_ROOT` is `Path(__file__).resolve().parents[3]`, so `store.COMMITTED_DB`
   follows `PYTHONPATH`, and running that suite with the worktree on the path would compare the
   worktree's stale pair and prove nothing.
9. **Commits are by pathspec, one method file at a time.** The checkout is shared. No
   `git add -A`, no `git reset --hard`, no `git pull --rebase` while the batch is running — a
   rebase replays a stale `lab.sqlite` over the live one.
10. **The tree is green at the end of every phase.**
    `PYTHONPATH=<worktree>/engine/src /home/miftah/seer/engine/.venv/bin/pytest engine/tests` and
    `/home/miftah/seer/engine/.venv/bin/ruff check engine` both pass (CI lint is E9 and F minus
    F401).
11. **Lookback stays ≤ 473.** The smoke fixture is 473 bars and `test_allocator_contract` runs
    `assert_p4_identity` and `assert_no_lookahead` against it. A matched-draw allocator that needs
    the previous decision session must still clear that cut, and the slack it adds is
    `control_draw.PREVIOUS_DECISION_BARS` (26, measured by phase 1 over every monthly decision of
    the dev window) through `control_draw.lookback_for` — never a number guessed per file.
12. **One params value, one new allocator id.** A re-drawn arm reuses, byte for byte, the params
    **value** of the arm it replaces, and its **new allocator id is the whole of the difference**.
    No phase mints a params dataclass. Checked field by field on 2026-10-19: all nine chassis'
    existing params already carry every input a matched draw reads, so a new dataclass would have
    been nine ways of saying one thing, and `config_text`'s `allocator=` line alone is enough for
    both `Method.__post_init__`'s digest set and `trials`' `UNIQUE(config_digest, window)`. The
    reused value must also stay **honest**: it keeps the placebo marker the replaced arm carried
    (`side="random"`, `pick="random"`, `picks="placebo"`, `order="hash"`), because the config
    text is the public record of what an arm did and a blind book must not describe itself as a
    ranked one. Each phase's params guard enforces it. **One exception, and only one:** M0208's
    allocator calls the shared `scored()` to compute the *real* overhang ranking and `scored`
    branches on `p.signal`, so `M0208-CGO-N20-PLC` reuses the value of the arm it **controls**
    (`OverhangParams(N20, keep=40)`, `signal="high"`) rather than of the arm it replaces. Phase 6
    states the reason at the point of use.
13. **Names and churn are matched; the weight vector is not.** Every phase derives its control's
    **entry count** from the book it controls and nothing else. A turnover miss is a **recorded
    STOP** — both ratios and the axis that missed go into that phase's results file, and the
    phase stops. No phase gives its drawn names the real arm's own weight vector, however
    tempting: that is a second mechanism, it applies to only three of the nine chassis
    (M0221/M0225 cap-weighted, M0047 size-weighted under a ceiling, M0201 size-weighted and
    re-sized monthly), and it would leave those three running a different rule from the other
    six — which fails R1's "ONE reusable rule" rather than rescuing it. The risk is real and
    measured: phase 3 found `M0221-E50` holding `C50`'s **exact names** and recording `C50`'s
    **exact 360 trades** while turning over **1.60x** (1.68x on M0225), because on a
    weight-varying chassis turnover is a property of the weight vector. On the other six, equal
    slots of the same count make the turnover ratio follow the trade ratio arithmetically. The
    weight-vector remedy is carried into phase 8's close-out as a stated option for a later plan
    set, never applied here.
14. **Every re-drawn arm declares what it supersedes.** `supersedes=("<the mis-shaped arm's id>",)`
    on the `Candidate`, in the commit that pre-registers it. D17's supersession is an explicit
    declaration and never an inference from target equality (see **Decisions** and **The
    supersession mapping**), so an arm that declares nothing retires nothing and its method stays
    blocked after all the measuring. The mapping below is the ground truth; copy the row.
15. **Every phase writes `.workflows/plan/honest-control-redraw/phase-N-results.md`** (N in 1..7)
    and commits it by pathspec. That is the set's one results-file convention and the only place
    phase 8 collects a phase's numbers from. Phase 1's doubles as the GO/STOP gate phases 3–7
    read. Phase 2 writes none — it measures nothing and records no trial. Phase 8 reads all six
    but trusts none of them: its completeness check is derived from the database.
16. **Every command runs `/home/miftah/seer/engine/.venv/bin/python` with
    `PYTHONPATH=<worktree>/engine/src`**, and records `git hash-object lab/lab.sqlite` either
    side of any `lab` command. Without `PYTHONPATH` pytest silently tests the main checkout
    instead of the branch. The one exception is phase 8's post-merge work, which runs on the main
    checkout with `PYTHONPATH=/home/miftah/seer/engine/src` (invariant 8).

## The supersession mapping

The fourteen declarations, enumerated once. Each re-drawn arm carries
`supersedes=("<the id in the right column>",)` on its `Candidate`, written into the commit that
pre-registers it. **This table is the ground truth**: every phase copies its rows, and phase 8
checks the method files against it rather than against any plan's claim.

| new arm | supersedes | phase | note |
|---|---|---|---|
| `M0227-S20-PLC` | `M0227-R20` | 1 | |
| `M0243-NEAR20-PLC` | `M0243-NEAR20-R` | 1 | |
| `M0221-C50-PLC` | `M0221-R50` | 3 | |
| `M0225-C50-PLC` | `M0225-R50` | 3 | |
| `M0047-MV10-PLC` | `M0047-PLC1-MV10` | 4 | the two targets **differ** (`MV10` vs `EQ`) |
| `M0047-MV20-PLC` | `M0047-PLC1-MV20` | 4 | targets differ; the old arm only **warns** |
| `M0201-Y20-MV10-PLC1` | `M0201-PLC1-MV10` | 5 | |
| `M0201-Y20-MV10-PLC2` | `M0201-PLC2-MV10` | 5 | |
| `M0202-Y20-HALF-PLC1` | `M0202-PLC1-HALF` | 5 | |
| `M0202-Y20-HALF-PLC2` | `M0202-PLC2-HALF` | 5 | |
| `M0202-Y20-HALF-FAST-PLC1` | `M0202-PLC1-HALF-FAST` | 5 | the two targets **differ** (`Y20-HALF-FAST` vs `Y20-HALF`) |
| `M0208-CGO-N20-PLC` | `M0208-HASH-N20` | 6 | |
| `M0215-CTRL-PLC` | `M0215-HASH` | 7 | both old arms resolve to `CTRL`; the declaration is what separates them |
| `M0215-CAP4-PLC` | `M0215-HASH-CAP4` | 7 | |

Fourteen rows: the thirteen `refuse` arms plus `M0047-PLC1-MV20`, which only warns. Three of the
fourteen pair arms whose resolved targets **differ**, which is the whole reason D17's rule reads
a declaration and not a target match (see **Decisions**).

## Phases

| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID | Card |
|---|-------|-----------|---------|-------|-----------|------------|------|--------|------|
| 1 | The matched-draw rule, proven on both poles (M0227, M0243) | R1, R2, R3, R4 | `engine/lab` | 6 | — | HARD | `.workflows/plan/honest-control-redraw/phase-1.md` | — | — |
| 2 | D17 supersedes: a declared honest control retires a handicapped one | R4 | `engine/lab` | 5 | — | NORMAL | `.workflows/plan/honest-control-redraw/phase-2.md` | — | — |
| 3 | The twin yardsticks: M0221 and M0225 | R2, R3, R4 | `engine/lab/methods` | 3 | 1 | NORMAL | `.workflows/plan/honest-control-redraw/phase-3.md` | — | — |
| 4 | M0047 — the size-weighted residual's two placebos | R2, R3, R4 | `engine/lab/methods` | 2 | 1 | NORMAL | `.workflows/plan/honest-control-redraw/phase-4.md` | — | — |
| 5 | M0201 and M0202 — the rate-beta chassis, five arms | R2, R3, R4 | `engine/lab/methods` | 3 | 1 | HARD | `.workflows/plan/honest-control-redraw/phase-5.md` | — | — |
| 6 | M0208 — the 4.41x extreme | R2, R3, R4 | `engine/lab/methods` | 2 | 1 | NORMAL | `.workflows/plan/honest-control-redraw/phase-6.md` | — | — |
| 7 | M0215 — the sector-capped placebo pair | R2, R3, R4 | `engine/lab/methods` | 2 | 1 | NORMAL | `.workflows/plan/honest-control-redraw/phase-7.md` | — | — |
| 8 | Close-out: which verdicts survived their honest control | R3, R4 | repo | 4 | 1,2,3,4,5,6,7 | NORMAL | `.workflows/plan/honest-control-redraw/phase-8.md` | — | — |

Waves the DAG allows: **{1, 2}** → **{3, 4, 5, 6, 7}** → **{8}**. Unchanged by the
reconciliation, and deliberately so: phase 2 reads `Candidate.supersedes` duck-typed
(`getattr(arm, SUPERSEDES_ATTR, ())`), so it needs no dependency on phase 1 creating the field,
and phase 1 needs none on phase 2 reading it. Either order compiles and either order is correct.

`Files` counts rose by one in phases 3–7 (each now writes its `phase-N-results.md`, invariant 15)
and by one in phase 1 (which also writes `backtest/dev.py`, and whose index edit was removed).
`Satisfies` gained **R4** in phases 1 and 3–7: each declares which recorded arm its new arm
supersedes, and without those fourteen declarations phase 2's rule fires on nothing. That is a
step moving with its requirement id, not a widened `Satisfies`.

### Phase 1 — The matched-draw rule, proven on both poles (M0227, M0243)

**Satisfies:** R1, R2, R3, R4
**Owns:** the new `engine/src/seer_engine/lab/control_draw.py`; the one trailing defaulted field
`Candidate.supersedes` on `engine/src/seer_engine/backtest/dev.py` and its validation; the
amendment blocks on `m0227_net_share_shrinkers.py` (one arm, `M0227-S20-PLC`) and
`m0243_shrinkers_near_high.py` (one arm, `M0243-NEAR20-PLC`); the new
`engine/tests/test_lab_control_draw.py`; the two `lab run --amend` runs;
`phase-1-results.md`; and the written rule the other five method phases consume.
**Does not touch:** `control_shape.py`, `hardgate.py`, `commands/lab.py`, any other method file,
`lab stage`, **and the plan index** — its Reconciliation Log is the reconciler's and its Status
line is phase 8's, so the gate lives in `phase-1-results.md` and nowhere else.
**Exit criteria:**
- `control_draw.py` exists and holds the rule in one place, with a prose docstring saying *why*
  a derived churn beats a hand-chosen re-key period, naming M0227's 0.07x and M0243's 3.01x as
  the two poles and M0241's 1.372x as the state of the art it has to beat.
- Its public surface is the one phases 3–7 were reconciled onto: `RULE_ID`, `CADENCES`,
  `PREVIOUS_DECISION_BARS`, `Select`, `keep_key`, `entry_key`, `churn`,
  `previous_decision_date`, `lookback_for`, **`matched_partition`**, `matched_names`,
  `matched_book`. `matched_partition` returns `(keep, tail)` with **fresh names ahead of dropped
  holdings**, and `matched_names` is built from it, so the book and the partition cannot
  disagree about who is fresh.
- `test_lab_control_draw.py` asserts, session by session on the smoke fixture and **before any
  backtest**, that the matched-draw allocator's per-rebalance entry count equals the target
  allocator's, and that a dropped holding is never re-taken ahead of a fresh name. This is the
  verification that costs nothing and sees no return.
- Neither method file gains a params dataclass: each new arm reuses the replaced arm's params
  value under a new allocator id (`M0227-A1`, `M0243-A1`), with a guard that keeps the placebo
  marker honest (invariant 12).
- Both new arms declare their supersession (`M0227-R20`, `M0243-NEAR20-R`), and
  `Candidate.supersedes` is proved outside `config_digest` by a test rather than by argument.
- Both amendment blocks are committed before their run; both runs record one trial each.
- `lab control M0227 M0243` reports **both** new arms inside `WARN_BAND` (0.80x–1.25x) on **both**
  axes. If either lands outside, the phase stops, writes the measured ratios and the reason into
  `phase-1-results.md`, and **does not** fan out — the other five method phases depend on this.
- The two re-measured margins are written down in `mwr`, against the pre-registered direction.
- `pytest engine/tests` and `ruff check engine` green.

### Phase 2 — D17 supersedes: a declared honest control retires a handicapped one

**Satisfies:** R4
**Owns:** `control_shape.py` (the supersession predicate and its `Finding` surface),
`hardgate.py` (D17's prose and `mis_shaped_controls`), `commands/lab.py` (the `lab control`
report, the run's control print, the subcommand help), and
`test_lab_control_shape.py` / `test_lab_hardgate.py`.
**Does not touch:** any method file, the lab database, `control_draw.py`, `lab stage`.
**Why it is needed, stated plainly:** `mis_shaped_controls` returns **every** recorded arm outside
the band and `hardgate.check` raises on a non-empty tuple. The old mis-shaped arm stays in
`all_candidates()` and keeps its recorded trial forever, so **an amendment alone does not unblock
`lab promote`.** D17's own message says the way back is to re-draw and amend; today the code does
not honour its own sentence.
**The rule, exactly — and this is the reconciled rule, not the draft's:** a `REFUSE` **or `WARN`**
finding is **superseded** — reported, never dropped — when the same method holds another
`placebo` arm that **(a)** is a placebo, **(b)** has verdict `OK` (inside `WARN_BAND` on both
axes, not merely inside `REFUSE_BAND`), and **(c)** **names it** in its own pre-registered
declaration, `Candidate.supersedes`, read duck-typed through `control_shape.SUPERSEDES_ATTR`
exactly as `DECLARATION_ATTR` is. **There is no target-equality condition.** `refusals()` then
excludes it. Nothing else changes: the band does not move, an arm that declares nothing retires
nothing, an `unresolved` or `unrecorded` arm is still never a refusal, and the superseded arm
stays visible in `lab control` with the id of the arm that superseded it **and that arm's own
resolved target**, so a deliberate re-point is something a reader sees rather than something the
rule hides.
**Does not touch the band and is not an override.** The hard gate still has no override; this is
the rule change its own text invites, argued for in the commit.
**Exit criteria:**
- `lab control` prints a superseded arm as `superseded by <id>` — with `-> <its target>` where
  the two differ — and still shows its ratios and its verdict.
- A new test proves the rule is **a no-op on today's lab**: with the committed database, all nine
  methods still fail D17, and **no arm in it declares anything at all**, which is the stronger
  reason.
- New tests prove a band-clean placebo that **declares** a refusal retires it, across a
  *different* resolved target, with both targets reported; and that a clean placebo declaring
  nothing, a `warn` superseder, an arm a clean superseder did not name, an `unrecorded`
  superseder, an `unresolved` superseder and a dose-response superseder each do **not**. A
  declared `warn` finding **is** superseded and stays flagged.
- D17's docstring in `hardgate.py` carries the change and the argument for it, including both
  halves of why target equality was rejected.
- `pytest engine/tests` and `ruff check engine` green.

### Phase 3 — The twin yardsticks: M0221 and M0225

**Satisfies:** R2, R3, R4
**Owns:** amendment seq 1 on `m0221_cap_weighted_top_n.py` (`M0221-C50-PLC`) and amendment
**seq 2** on `m0225_cap_weighted_top_n_repaired.py` (`M0225-C50-PLC`); both runs.
**Does not touch:** `control_draw.py`, any other method file, `lab stage`.
**Boundary note that is the whole point of pairing them:** M0225 is M0221's twin on the repaired
store and exists so the before-and-after measures the data fix and nothing else. The two re-drawn
arms must use the **identical** rule and the identical seed discipline, or the twin comparison
breaks. M0225's existing amendment is seq 1 (E100, 2026-10-18), so this one is **seq 2**;
`pending_amendment` compares every recorded row field by field, so the E100 block must be left
byte-identical.
**Exit criteria:** both new arms inside `WARN_BAND` on both axes; both declare their supersession
(`M0221-R50`, `M0225-R50`); both reuse `CapTopParams(50, pick="random", seed=1, trend=None)` with
no new dataclass; both margins re-stated in `mwr` (`M0221-C50` 5.63 vs `R50` 6.72; `M0225-C50`
5.85 vs `R50` 6.74 — the control currently *wins* both, which is the family-A prediction's
hardest case); `phase-3-results.md` written and committed; tests and lint green.
**The axis at risk here, and the settled policy:** this is a cap-weighted chassis, so turnover is
a property of the weight vector and not only of the names — phase 3 measured `M0221-E50` holding
`C50`'s exact names and recording `C50`'s exact 360 trades while turning over 1.60x. Invariant 13
applies: names and churn only, and a turnover miss is a recorded STOP.

### Phase 4 — M0047: the size-weighted residual's two placebos

**Satisfies:** R2, R3, R4
**Owns:** amendment seq 1 on `m0047_market_value_residual.py`, two arms —
`M0047-MV10-PLC` and `M0047-MV20-PLC`; and `phase-4-results.md`.
**Does not touch:** any other file.
**Boundary note:** the existing pair resolves to `M0047-EQ` by `first-declared`, which is a guess
the ladder reports as one; their true targets are `M0047-MV10` and `M0047-MV20`. Naming the new
arms `<target>-PLC` makes `sibling-stem` resolve them correctly, and the margin must be re-stated
against the **true** target (+1.28 pts against `MV10`), not against `EQ` (+3.80 pts). Both the old
number and the new one go in the report.
**This is the method the correction of the brief is about.** M0047's residual arms are **not**
quarterly/banded: `REPICK_MONTHS` and `KEEP_PCT` appear only inside `placebo_order` (`:189-202`)
and the residual arms take a fresh `one_per_company(order, 20)` at every monthly decision
(`:244-248`). The quarterly band is the handicap being removed, not a property to reproduce, so
this phase calls the shared monthly `control_draw.previous_decision_date`. (Phase 5's chassis is
the genuinely quarterly one.)
**And the consequence that must be written down:** after this phase `M0047-EQ` has **no control
arm at all**, because its only two placebos were size-weighted arms the ladder mis-aimed at it
and both are re-pointed. That is correct. The standing sentence about EQ's **+3.80-point lead is
withdrawn, not re-measured** — it was never supported by a correctly-aimed control — and a method
arm with no placebo produces an empty findings tuple and is not refused, so this is consistent
with D17 rather than an exception to it. It goes in `phase-4-results.md` and in phase 8's
handover.
**Exit criteria:** both new arms inside `WARN_BAND` on both axes; both declare their supersession
(`M0047-PLC1-MV10`, `M0047-PLC1-MV20` — the second a `warn` arm, which blocks nothing but keeps
the pair's record consistent); both reuse the replaced arms' own `SizeParams` values with no new
dataclass and no `size_weights` annotation change; both margins re-stated in `mwr` against their
true targets **and** against `EQ`; the `M0047-EQ` sentence withdrawn in writing;
`phase-4-results.md` written and committed; tests and lint green.
**The axis at risk:** size-weighted under a ceiling, so invariant 13 applies here too.

### Phase 5 — M0201 and M0202: the rate-beta chassis, five arms

**Satisfies:** R2, R3, R4
**Owns:** amendment seq 1 on `m0201_treasury_beta_size_weighted.py` (`M0201-Y20-MV10-PLC1`,
`M0201-Y20-MV10-PLC2`) and amendment seq 1 on `m0202_treasury_beta_half_guard.py`
(`M0202-Y20-HALF-PLC1`, `M0202-Y20-HALF-PLC2`, `M0202-Y20-HALF-FAST-PLC1`).
**Does not touch:** any other file.
**Boundary notes:** (a) both files share M0197's screened, banded, quarterly book and both order
by `m0187.draw(seed, symbol, data_date)`, so one application of the rule serves both — but they
are two separate amendments under two ids. (b) The two-seed spread is deliberate and must survive:
each book keeps **two** re-drawn placebo seeds so its lead is read against a spread and not a
single draw. (c) `M0202-PLC1-HALF-FAST` currently resolves to `Y20-HALF`, not to its true target
`Y20-HALF-FAST`; the new arm's `<target>-PLC` name fixes that and the margin is re-stated against
`Y20-HALF-FAST`. (d) A `-PLC1` / `-PLC2` suffix leaves the stem one segment up
(`M0201-Y20-MV10`), which is the intended target — verify that `sibling-stem` resolves it before
committing.
**Boundary note (e), added in reconciliation and load-bearing:** this is the **only** chassis in
the set whose basket does not move every month. `_run` passes an empty `frac` on every
non-`REPICK_MONTHS` month, so the book moves quarterly behind M0197's 40% keep band and there is
no monthly entry count to match. These two files therefore derive their **own** previous re-pick
(`prev_repick_session`) and take the entry count from the band rather than from a set
difference, and they do **not** call `control_draw.previous_decision_date`. Measured before
anything ran: **423 entries against the real book's 443 over the dev window's 79 re-picks, a
ratio of 0.9549**, where the recorded pair sits at 2.24. Phase 1's docstring carries the split so
nobody later "simplifies" this into the monthly helper.
**Exit criteria:** all five new arms inside `WARN_BAND` on both axes; all five declare their
supersession (the five rows of the mapping above, one of which — `Y20-HALF-FAST-PLC1` —
deliberately crosses a different resolved target); no new params dataclass (this phase already
reused `SizedYieldBetaParams` and `HalfGuardParams`, and the set adopted its approach); five
margins re-stated in `mwr`; `phase-5-results.md` written and committed; tests and lint green.
**The axis at risk:** M0201 re-sizes monthly by company size, so invariant 13 applies to it.

### Phase 6 — M0208: the 4.41x extreme

**Satisfies:** R2, R3, R4
**Owns:** amendment seq 1 on `m0208_capital_gains_overhang.py`, one arm `M0208-CGO-N20-PLC`; and
`phase-6-results.md`.
**Does not touch:** any other file.
**Boundary note:** `M0208-HASH-N20` is the widest miss in the set — 4.41x trades and 5.20x
turnover against `CGO-N20`, which is also the lab's biggest quoted placebo margin at
**+5.87 pts** (13.88 vs 8.01). The family-B prediction says an honestly-shaped draw earns more
and that margin narrows; this is the arm most likely to reverse, and that is the finding.
**The one params exception in the set lives here.** Every other phase reuses the params value of
the arm it **replaces**; this one reuses the value of the arm it **controls**
(`OverhangParams(N20, keep=40)`, `signal="high"`), because `_targets` calls the shared `scored()`
to compute the real overhang ranking and `scored` branches on `p.signal` — handed `"hash"` it
would match the churn of a placebo instead of the churn of the book. Invariant 12 records it.
**Exit criteria:** the new arm inside `WARN_BAND` on both axes; it declares
`supersedes=("M0208-HASH-N20",)`; no new params dataclass; the margin re-stated in `mwr` against
the pre-registered direction; `phase-6-results.md` written and committed; tests and lint green.
**Not at risk on the turnover axis:** equal 1/20 slots on both sides, so the turnover ratio
follows the trade ratio arithmetically.

### Phase 7 — M0215: the sector-capped placebo pair

**Satisfies:** R2, R3, R4
**Owns:** amendment seq 1 on `m0215_sector_capped_calm_raisers.py`, two arms —
`M0215-CTRL-PLC` and `M0215-CAP4-PLC`; and `phase-7-results.md`.
**Does not touch:** any other file.
**Boundary note:** the existing pair both resolve to `M0215-CTRL`, but `HASH-CAP4`'s job is to
price what a cap does to any book of this shape, so its true target is `M0215-CAP4`. The two new
arms take the two true targets. M0215's method-level success condition is *"a capped variant beats
CTRL … and its gain over CTRL is larger than HASH-CAP4's over HASH"*, which is a comparison
**between two placebos** — re-state it on the re-drawn pair and say in the report whether it still
holds.
**This method is the sharpest argument for a declared supersession.** `M0215-HASH` and
`M0215-HASH-CAP4` **both** resolve to `M0215-CTRL` — the capped one because its own stem is a
placebo and the ladder steps past it — so a rule keyed on target equality would have let one
honest control of `CTRL` excuse an arm that exists to price what a cap does and was never scored
against `CTRL` in spirit. The declaration pairs each old arm with the arm drawn to replace it and
with no other.
**Exit criteria:** both new arms inside `WARN_BAND` on both axes; `CTRL-PLC` declares
`supersedes=("M0215-HASH",)` and `CAP4-PLC` declares `supersedes=("M0215-HASH-CAP4",)`; both
reuse the replaced arms' own `CapParams` values (`order="hash"`, seed 1) with no new dataclass;
both margins and the cap-over-placebo difference-in-differences re-stated in `mwr`;
`phase-7-results.md` written and committed; tests and lint green.
**Not at risk on the turnover axis:** equal 1/20 slots with the remainder parked in SPY, the same
on both sides.

### Phase 8 — Close-out: which verdicts survived their honest control

**Satisfies:** R3, R4
**Owns:** `docs/plans/HANDOVER_20261019-the-honest-control.md`; the lab insights; the merge of
`feature/honest-control-redraw` into `main`; the single `lab stage`; the commit and push.
**Does not touch:** any method file, `control_draw.py`, `control_shape.py`, `hardgate.py` — every
code change is already landed and verified by the time this phase starts.
**Order, and it matters — corrected in reconciliation, because the draft's guard was red by
construction:**

1. **merge** the branch into `main` (first, so `main` never carries lab rows for method files it
   does not have);
2. the **read-only verification sweep** — `lab control` on the nine, the hard gate run through
   `store.connect_readonly`, the counts and the margins;
3. **`lab stage`** on the main checkout;
4. **the full suite and the lint**, with `PYTHONPATH=/home/miftah/seer/engine/src`;
5. the four **`lab insight`** rows;
6. **`lab stage` again**, because the insights landed after step 3 and `web/data/lab.json` must
   carry them;
7. write the **handover**;
8. **commit** through the index `lab stage` built (**no pathspec**), re-check the snapshot
   agreement against what is committed, and **push**.

The draft index put "pytest green on main after the merge" between 1 and 3 and called it the
guard. It is unsatisfiable there:
`test_the_committed_snapshot_is_the_export_of_the_committed_database` compares
`web/data/lab.json` against `lab/lab.sqlite`, and at that point the snapshot is still the
pre-batch export, so the suite is red **by construction** and tells a reader nothing. The suite
belongs after the first staging and before the commit. And `store.COMMITTED_DB` resolves through
`config.REPO_ROOT = Path(__file__).resolve().parents[3]`, i.e. it **follows `PYTHONPATH`** — run
that closing suite with the worktree on the path and it compares the worktree's stale pair and
proves nothing. See invariant 8.

**Exit criteria:**
- `lab control M0047 M0201 M0202 M0208 M0215 M0221 M0225 M0227 M0243` shows all fourteen new arms
  `ok` and all fourteen old arms `superseded by …` — thirteen `refuse` plus `M0047-PLC1-MV20`,
  which only warns and is superseded too.
- The fourteen declarations in the method files match **The supersession mapping** above, row for
  row, read off the files rather than off any plan's claim. A missing supersession has two
  possible causes — the new arm missed the band, or its declaration is wrong — and the close-out
  says which.
- The hard gate is run (not promoted) against each of the nine and the D17 clause no longer
  refuses any of them; any that still fail, fail on a *different* clause, and the close-out names
  which.
- One table in the handover: for each of the nine, the arm, the old control, the old margin, the
  new control, the new margin — all in `trial_funding.mwr` against SPY TR 7.19%/yr — and one
  sentence per method saying whether the standing verdict survived.
- **`M0047-EQ` is recorded as having no control arm at all, and its +3.80-point sentence is
  withdrawn rather than re-measured.** Both of its placebos were size-weighted arms the ladder
  mis-aimed at it; a method arm with no placebo produces an empty findings tuple and is not
  refused, so this is consistent with D17 and not a gap to fill with a third arm.
- The six `phase-N-results.md` files are read for attribution; a missing one is re-derived
  read-only and the attribution line says so. The completeness check itself is derived from the
  **database** and trusts no plan file's claim.
- Both the trials count and the amendment count are re-derived read-only, with
  `git hash-object lab/lab.sqlite` recorded before and after every `lab` command.
- `lab insight` records the two family findings, the D17 supersession and the matched-draw rule.
- The test-window look count is still **4**.
- `pytest engine/tests` green on `main` **after `lab stage`**, `web/data/lab.json` and
  `lab.sqlite` agreeing row for row (the CI check, re-run against what is committed), and the
  push lands.

## Reconciliation Log

The eight planners ran in parallel and could not see each other. Every row below was resolved by
**editing the plan files**, not by adding a caveat: where two plans implied different behaviour,
the losing side is gone from the file rather than merely outranked.

| # | Conflict | Class | Resolution |
|---|---|---|---|
| 1 | Phases 3, 4, 5, 6 and 7 each assumed a **different** `control_draw` signature, and each said so explicitly: `matched_book(pool,now,prev,held,key,…)`, `matched_order(pool,held,keeps,…)`, `matched_book(…)->(keep,tail)`, `matched_book(picks_now,picks_prev,…)` positional, and `churn`/`previous_rank_session`/`matched_order` | unmet assumption | Phase 1's module is authoritative (it owns the file). All five retargeted **in the code blocks**, not noted: P3 and P6 → `matched_names(...)` keyword-only; P4, P5 and P7 → `matched_partition(...)`; P7 also → `churn`. Each phase's "assumed contract" section is replaced by Phase 1's real one with the differences enumerated. Every call site was type-checked against the real signature |
| 2 | Three phases needed an **ordered permutation of the pool** (to apply their own slot count, cap or keep band) and Phase 1's module offered only a finished book | gap | **Phase 1 edited**: `matched_partition(*, pool, held, keep_n, tag, seed, data_date) -> (keep, tail)` added to its public surface, and `matched_names` rebuilt on top of it so the book and the partition cannot disagree. `churn` added for the same reason P7 wanted it |
| 3 | **A real bug in Phase 1**, found because Phase 5 stated the requirement: Phase 1's `matched_names` drew its fresh names from the whole eligible pool, so a holding it had just dropped could be taken straight back. Entries then fall below `e`, the trade ratio sags under 1.00, and every size assertion stays green | contract drift | **Phase 1 edited.** `matched_partition` sorts every non-held name ahead of every dropped holding, documents it as a guarantee, and `test_a_dropped_holding_is_never_re_taken_ahead_of_a_fresh_name` pins it. Phase 5's 0.9549 was measured with that ordering and stands; Phase 5 now says so instead of asserting a requirement back at Phase 1 |
| 4 | Phase 1 told phases 4 and 5 *"do not reach for the previous quarter"*; Phase 5 reaches for the previous quarter and **measured 0.9549** doing it | contradiction | Split on the measurement rung. Phase 1's warning is right for M0047 (monthly) and wrong for M0201/M0202, whose `_run` passes an empty `frac` on non-`REPICK_MONTHS` months so the basket moves only quarterly behind a 40% keep band. Phase 1's docstring now carries **both halves**; Phase 4 calls the shared monthly helper and Phase 5 keeps its own `prev_repick_session`. The losing blanket sentence is deleted |
| 5 | D17 supersession: Phase 2 planned **target equality**; phases 4, 5 and 7 each proved it broken in both directions | contradiction, decided by the user | Rewritten to an **explicit declaration** (see Decisions). Phase 2's predicate, `Finding`, report, prose, tests and commit message all rewritten; the target-equality code is gone. Mechanism: a defaulted `Candidate.supersedes` created by Phase 1, read duck-typed by Phase 2 — so the DAG is unchanged |
| 6 | Phase 2's cross-phase caution to phases 4, 5 and 7 ("your re-pointed arm will not be superseded and the method stays blocked") | consequence of #5 | **Closed**, and closing it is the argument for #5. Each of those phases' handoffs now records that the hazard is resolved and that its contribution is getting its `supersedes` tuple right |
| 7 | Phases 1, 4 and 7 each minted a new params dataclass; phases 3, 5 and 6 found none was needed | duplicate work / inconsistent rule | Checked field by field against the real dataclasses: **all nine chassis already carry every input a matched draw reads.** The three new dataclasses are deleted. Invariant 12 states the rule once — reuse the replaced arm's params **value**, let the new allocator id be the whole difference, keep the placebo marker honest — with M0208's one functional exception named |
| 8 | A consequence of #7 that removed work: Phase 4's Step 2 widened `size_weights`'s annotation to `SizeParams \| MatchedParams` | duplicate work | Step 2 withdrawn; `size_weights` is byte-identical. Phase 4's "Signature changes" is now **none** |
| 9 | Phase 1 wrote `PHASE-1-RESULT.md`; Phase 3 wrote `phase-3-results.md`; phases 4–7 each described recording numbers somewhere | file collision / gap | One convention, invariant 15: `.workflows/plan/honest-control-redraw/phase-N-results.md` for N in 1..7, phase 1's doubling as the GO/STOP gate. Phases 4, 5, 6 and 7 gained an explicit write-and-commit step; Phase 8 reads exactly that set — and keeps its database-derived completeness check, which trusts none of them |
| 10 | Phase 1 also appended to the plan index's Reconciliation Log and committed the index | file collision | Removed. The Log is the reconciler's and the **Status** line is Phase 8's; the index already points at `phase-1-results.md` as the gate |
| 11 | The turnover axis: Phase 3 measured the risk and deliberately declined the remedy; phases 4 and 5 named the same risk; nobody had a policy | gap | Invariant 13 settles it for the set — **names and churn only, a turnover miss is a recorded STOP** — with the reasoning (the remedy is a second mechanism applying to three of nine chassis, which fails R1) and the carry-forward to Phase 8's close-out. Written into phases 3, 4 and 5; phases 6 and 7 record that they are the not-at-risk kind |
| 12 | The brief, the analysis document and Phase 1 all called M0047's real arms "quarterly/banded"; Phase 4 proved they are plain monthly re-picks | factual error | Corrected in the analysis document (the Rule A risk bullet and the family-A table), in Phase 1's `previous_decision_date` docstring and Handoffs, and in the index's Phase 4 section. Phase 4's own correction is promoted to the set's authoritative reading. **Phase 5's prose was checked and is accurate** — M0201/M0202's quarterly keep band is real |
| 13 | Phase 8's ordering correction: the index's "pytest green on main after the merge" is red by construction, and `lab stage` must run twice | ordering violation | Phase 8's ordering adopted verbatim into the index's Phase 8 section and invariant 8, together with its finding that `store.COMMITTED_DB` follows `PYTHONPATH`, so the closing suite must run with `PYTHONPATH=/home/miftah/seer/engine/src` |
| 14 | `M0047-EQ` ends the set with no control arm at all, and no phase said so | gap | Written into Phase 4 (handoffs, exit criteria, results block), Phase 2 (handoffs), Phase 8 (the handover's mis-resolution section and the family-A insight) and the index's Phase 4 and Phase 8 sections, in the same words: the +3.80 sentence is **withdrawn, not re-measured**, and an arm with no placebo is not refused |
| 15 | `Satisfies` lines vs the work actually in each phase: the fourteen `supersedes` declarations live in phases 1 and 3–7 but serve R4 | requirement creep | The **id moved with the step**: R4 added to phases 1, 3, 4, 5, 6, 7 in both the phase table and each phase file, and to the Requirements table. No phase's `Satisfies` was widened to legalise a step that should have moved |
| 16 | Counts: the index says fourteen arms / nine amendments / thirteen refuse + one warn; Phase 2's `BLOCKED_NINE` holds thirteen; Phase 8 expects fourteen supersession markers | consistency | All consistent, and now explained where it was silent: `BLOCKED_NINE` is the **refuse-band** set (13) and `M0047-PLC1-MV20` is the fourteenth, a `warn`. Phase 2's predicate was widened to `REFUSE or WARN` so the warn twin is superseded too — it blocks nothing, but leaving one of a re-drawn pair unmarked would tell a reader the opposite |

**Checked and found already consistent** (no edit needed): the fourteen candidate ids appear in
exactly one phase each and match Phase 8's expected list; amendment seqs — M0225 is **seq 2** and
the other eight are **seq 1**, re-verified read-only against `method_amendments`, which holds only
M0030/1, M0053/1 and M0225/1; the nine allocator ids `M0047-A1`, `M0201-A1`, `M0202-A1`,
`M0208-A1`, `M0215-A1`, `M0221-A1`, `M0225-A2`, `M0227-A1`, `M0243-A1` are distinct and each
belongs to exactly one shared instance object (`test_allocator_ids_are_unique_across_methods`
compares by identity — M0225's `MatchedRepairedCapTopAllocator` subclasses M0221's class but is
its own instance with its own id); **no phase before 8 runs `lab stage`**; **no phase anywhere**
runs `lab test` or `lab promote` or reads `SEER_RESEARCH_TEST_STORE` (Phase 8 explicitly unsets
it); every phase records `git hash-object lab/lab.sqlite` around every `lab` command; no symbol is
deleted anywhere in the set, so there is no deleted-then-used conflict; and every file is owned by
exactly one phase (`backtest/dev.py` is Phase 1's, newly).

## Decisions

| Fork | Chosen | Rung |
|---|---|---|
| "one pilot method" vs "a rule that fixes one family will not fix the other" | the pilot is **two** methods, one per pole — M0227 (0.07x, the stickiest draw) and M0243 (3.01x, the churniest), which share the closest chassis in the set and whose own files already cite each other | 5: the user's raw input, reconciling its two sentences |
| is the D17 supersession in scope? | **yes, phase 2.** `mis_shaped_controls` refuses on any recorded arm outside the band and the old arm is recorded forever, so the stated remedy alone leaves all nine blocked. Delivering only the amendments would not meet the stated purpose | 5: the user's raw input — "nine dev-eligible methods are blocked" is the purpose, and `hardgate.py:1796` invites exactly this change |
| which re-draw rule | **Rule A, churn-matched to the real arm's own calendar** (recompute the target's selection at this and the previous decision session, match the entry count, keep the rest), with **Rule C, the persistence-inherited permutation**, as the named fallback. Rule B (M0241's cohort mirror) is excluded on evidence: it measures 1.372x/1.131x, outside the match band | 6: the lab's own convention, plus the one measurement that bears on it |
| candidate and allocator naming | candidates are `<target-id>-PLC` so `sibling-stem` — the strongest resolution rung — names the intended book; allocators are `<METHOD>-A<seq>`, new per amendment, unique lab-wide | 6: `control_shape`'s own ladder, and `M0225`'s `RepairedCapTopAllocator` precedent |
| worktree, or straight on main | **one worktree** for the whole set, as the gate-reading-cadence set used, with the lab database and research store read at the main checkout's paths; phase 8 merges to `main` **before** `lab stage` | 6: repo convention (`merge(gate-reading-cadence): 4 phases`) plus the split-brain the merge-first order removes |
| when `lab stage` runs | **once, in phase 8 only.** It regenerates `lab.json` from the whole database and git-adds it with `lab.sqlite`; running it mid-batch stages other phases' half-finished work | 6: convention, and the known mid-batch red snapshot test |
| what happens if the pilot misses the band | phase 1 **stops and reports**; phases 3–7 do not start. A second attempt is a new rule in `control_draw.py`, never a tuned seed | 1: invariant 4 and design §4 |

### Settled in reconciliation, 2026-10-19

| Fork | Chosen | Rung |
|---|---|---|
| **The D17 supersession predicate.** Phase 2 planned "a REFUSE finding is excused when another placebo arm of the same method resolves to the SAME `target_id` and is itself band-clean". Phases 4, 5 and 7 each independently proved it broken in **both** directions | **Supersession is EXPLICIT and DECLARED by the new arm, never inferred from target equality.** A `REFUSE` or `WARN` finding is superseded when the same method holds an arm that (a) is kind `placebo`, (b) has verdict `OK` — inside `WARN_BAND` on both axes, not merely inside `REFUSE_BAND` — and (c) **names the superseded candidate id in its own pre-registered declaration**. No target-equality condition. The report prints the superseded arm, its resolved target, the superseding arm **and the superseding arm's own target**, so a re-point is visible. *Too strict:* the `<target-id>-PLC` convention deliberately re-points three new arms at their true target, so `M0047-MV10-PLC`→`MV10` against `M0047-PLC1-MV10`→`EQ`, and `M0202-Y20-HALF-FAST-PLC1`→`Y20-HALF-FAST` against `M0202-PLC1-HALF-FAST`→`Y20-HALF`; equality retires none of them and M0047 and M0202 stay blocked after all the work. *Too loose:* `M0215-HASH` and `M0215-HASH-CAP4` both resolve to `M0215-CTRL`, so one honest control of `CTRL` excuses both, including a capped arm never scored against `CTRL` in spirit | **5: the user's raw input** — the stated purpose is that the nine stop being blocked, and `hardgate.py:1796` explicitly invites the rule change |
| **The mechanism for that declaration.** A defaulted field on `backtest.dev.Candidate`, or an explicit token in the arm's `rationale` prose | **A defaulted `Candidate.supersedes: tuple[str, ...] = ()`**, created by phase 1, read duck-typed by phase 2 through `control_shape.SUPERSEDES_ATTR` exactly as `DECLARATION_ATTR` is read today. Three reasons it beat the prose token, which was also admissible: it is **validated at import** (`__post_init__` checks every entry against `_ID`, refuses a self-reference, demands sorted-and-unique), so a typo is an `ImportError` the phase session sees rather than a silent non-supersession found in phase 8; it is **structured**, so `lab control` prints the mapping without re-parsing prose; and it is **the forward path `control_shape`'s own docstring already names** — *"The forward path for a method written tomorrow is `DECLARATION_ATTR`, not a wider guess"* — whose stated reason for not using it on existing arms (`methods.source_sha` is written once and trigger-protected) does not apply to fourteen arms living in `Amendment` blocks on files that are growing anyway. **Digest safety verified, not assumed:** `lab.method.config_text` names three attributes by hand, `registry.candidate_text` names five, and grepped over `engine/src/seer_engine/` every `_canon(...)` call site is `_canon(c.rules)`, `_canon(c.params)` or a recursive call — **no call site passes a whole `Candidate`**, so `_canon`'s `dataclasses.fields()` walk never meets one. `Candidate` is `@dataclass(frozen=True)` with no `slots=True`. **And the DAG does not change:** `getattr(arm, "supersedes", ())` answers `()` on any arm without the field, so phase 2 needs no dependency on phase 1 and either order compiles | 6: `control_shape`'s own documented design, plus the measured `_canon` grep |
| **A new params dataclass per method, or reuse the existing value?** Phases 1, 4 and 7 each minted one; phases 3, 5 and 6 found none was needed | **Reuse, everywhere. No new params dataclass in the set** (invariant 12). Checked field by field against the real classes: `IssuanceParams`, `NearShrinkParams`, `CapTopParams`, `SizeParams`, `SizedYieldBetaParams`, `HalfGuardParams`, `OverhangParams` and `CapParams` **already carry every input a matched draw reads**, so a new dataclass is load-bearing nowhere and would be nine ways of saying one thing. The re-drawn arm takes the params **value** of the arm it replaces and its new allocator id is the whole of the difference — which satisfies `_canon`-by-fields (no recorded digest moves, because no params class is touched at all) and `Method.__post_init__` (the `allocator=` line makes the text new). The reused value keeps the **placebo marker** the old arm carried, and each phase's guard enforces it, because the config text is the public record of what an arm did. **One exception:** M0208's allocator calls the shared `scored()` to compute the real ranking and `scored` branches on `p.signal`, so it reuses the value of the arm it **controls** (`signal="high"`) instead | 3: the plans' own code blocks — three phases had already found the reuse pattern and demonstrated it digest-safe |
| **The turnover axis.** Phase 3 measured that `M0221-E50` holds `C50`'s exact names and records `C50`'s exact 360 trades yet turns over **1.60x**, so on a weight-varying chassis a name-and-churn-matched control can clear the trade axis and still miss the band. Phase 3 declined the remedy; phases 4 and 5 named the same risk; three phases had three answers | **Names and churn only, set-wide. A turnover miss is a recorded STOP** (invariant 13). The remedy — giving the drawn names the real arm's own weight vector — is a **second mechanism** that applies to only three of the nine chassis (M0221/M0225, M0047, M0201) and would leave those three running a different rule from the other six. R1's deliverable is ONE reusable rule, so a rule that needs a per-chassis patch has already failed R1 and the honest answer is the measurement. On the other six, equal slots of the same count make the turnover ratio follow the trade ratio arithmetically, so the risk is confined and named. The weight-vector remedy is carried into phase 8's close-out as a stated option for a later plan set | 4: the index's own **Why** — *"there is probably ONE reusable way… and getting it wrong in nine parallel sessions is the expensive failure"* |
| **Does `previous_decision_date` answer the previous month or the previous re-pick?** Phase 1 said *"do not reach for the previous quarter"* and named M0047, M0201 and M0202; phase 5 reaches for the previous quarter and **measured 0.9549** doing so | **Split, per chassis, and both halves written into phase 1's docstring.** The shared helper answers the previous **monthly** decision, and that is right wherever the allocator's basket actually moves monthly — including M0047, whose residual arms take a fresh `one_per_company(order, 20)` every month (`REPICK_MONTHS` and `KEEP_PCT` live only inside `placebo_order`). It is **wrong** for M0201/M0202, whose shared `_run` passes an empty `frac` on non-`REPICK_MONTHS` months so the basket moves only quarterly behind M0197's 40% keep band — there is no monthly entry count there to match, and phase 5 derives its own `prev_repick_session` in its own two files. Phase 1's blanket sentence is deleted, not footnoted | 3: the plans' code blocks, settled by phase 5's measurement over 79 re-picks |
| **"M0047's real arms are quarterly/banded."** Stated in the brief, the analysis document and phase 1; contradicted by phase 4 reading the file | **Phase 4 is right and its correction is the set's authoritative reading.** Fixed in the analysis document, in phase 1's docstring and handoffs, and in the index's phase 4 section. Phase 5's prose was checked against `m0201`/`m0202` and is accurate — that chassis's quarterly keep band is real | 6: the surrounding code itself (`m0047:189-202` against `:244-248`) |
| **Phase 8's ordering.** The index said merge → `lab stage` → commit → push with "pytest green on main after the merge" as the guard; phase 8 showed that guard is red by construction | **Phase 8's ordering adopted**: merge → read-only sweep → `lab stage` → the suite → the four insights → `lab stage` **again** → handover → commit → push, with the closing suite run as `PYTHONPATH=/home/miftah/seer/engine/src` because `store.COMMITTED_DB` follows `PYTHONPATH` and not `SEER_LAB_DB`. The index's phase 8 section and invariant 8 were rewritten to match | 2: phase 8's own exit criteria, which the draft index's guard could not satisfy |
| **One results-file convention.** Phase 1 wrote `PHASE-1-RESULT.md`, phase 3 wrote `phase-3-results.md`, phases 4–7 each described "recording the numbers somewhere" | **`.workflows/plan/honest-control-redraw/phase-N-results.md`, N in 1..7** (invariant 15), with phase 1's doubling as the GO/STOP gate. Phase 8 reads exactly that set — **and keeps its database-derived completeness check, which trusts no plan file's claim.** Phase 1 also stops editing the plan index: the Reconciliation Log is the reconciler's and the Status line is phase 8's | 6: repo convention, plus phase 8's own (correct) refusal to trust a plan file over the database |

## Open Questions

*(empty.)*

Every fork above was decided on a stated rung and the losing side was edited out of the plan
files, so nothing is parked for a phase session to re-litigate at 3am. Nothing in this set
qualifies for this section anyway: it is reserved for a fork where **every** branch is
irreversible, and the two irreversible things here — a recorded trial and a journalled insight —
are not forks. They are measurements, and invariant 4 and design §4 already say what to do with
one that comes out wrong.

Specifically, and so no later reader re-opens them:

- **A re-drawn control whose margin reverses is not an open question.** It is the finding
  (invariant 4). Re-drawing until a margin survives is what design §4 forbids.
- **A re-drawn control whose SHAPE misses the band is not an open question either.** It is a
  recorded STOP with both ratios written down (invariants 4 and 13), and a second attempt is a
  new rule in `control_draw.py` applied to every method at once, never a tuned seed in one file.
- **Every requirement id is owned**: R1 by phase 1; R2 by phases 1 and 3–7; R3 by phases 1, 3–7
  and 8; R4 by phases 1, 2, 3–7 and 8. There is no `R` this set does not serve, which is the one
  conflict class that would have had to be parked here.

## Rollback

- **Per phase, before its run:** `git revert` the commit that added the `Amendment` block. The
  block is pre-registration only until `lab run --amend` executes.
- **Per phase, after its run:** nothing in the lab database is reversible — `trials`,
  `trial_funding` and `method_amendments` all carry append-only triggers on update and delete.
  The `Amendment` block must therefore stay in the file forever, and the correct rollback is a
  journalled insight saying the arm was run and what it showed. **This is why invariant 2 puts
  the whole pre-registration in the commit that precedes the run.**
- **Phase 2:** a plain revert. It writes nothing to the database.
- **Whole set, before phase 8:** delete the branch and the worktree. The database keeps whatever
  amendments ran, which is correct — they are measurements, and the method files that produced
  them are on the branch; recover by re-merging the branch, never by editing the database.
- **After phase 8's push:** forward-only. A later correction is a new commit.

## Next

Execute the phases one at a time, starting at phase 1:

    /implement -f docs/plans/HONEST_CONTROL_REDRAW_PLAN.md --phase 1

Or run the whole set as a swarm — a session per phase, concurrent wherever `Depends on` allows,
resumable on any machine:

    /analyze-orchestrator -f docs/plans/HONEST_CONTROL_REDRAW_PLAN.md

Or put them on the board first (GitHub repos only):

    /create-task --from-plan docs/plans/HONEST_CONTROL_REDRAW_PLAN.md

# Plan: the two carried remedies in `control_draw` — the held-set shadow and the weight vector

**Slug:** `control-draw-remedies`
**Date:** 2026-10-20 11:33:06
**Analysis:** `docs/analyzer/20261020-113306-C7K4_code_analyzer.md`
**Worktree:** none — this set is planned and run in the main checkout, `/home/miftah/seer`
**Branch:** `main` (base: `main` @ `e3aeeff`)
**Phases:** 6
**Status:** reconciled
**Coordinator:** —
**Reconciled:** 2026-10-20 (round 1) — see the **Reconciliation Log** below

---

## Why

Two defects in the lab's one matched-draw rule were measured on 2026-10-19 and deliberately
carried rather than fixed. This set fixes them. Before anything else, what it buys:

**It buys honest controls. It buys no promotions, and it cannot.** Of the nine dev-eligible methods
the honest-control set re-drew, the hard gate takes **none**. Four still carry a live D17 refusal —
M0201, M0208, M0221, M0225 — and `hardgate.check` tests the walk-forward fold majority **before**
D17, so for **M0201, M0221 and M0225 the D17 refusal is inert**: it is never the sentence `lab
promote` prints, and clearing it would change nothing about any of the three. **M0208 is the only
method of the nine whose operative clause is D17** — and immediately behind D17 stands the kin
rule, where `failed_kin(M0208)` returns `('M0002',)`, a method that has already read test-failed.
So even a perfect fix on M0208 changes the refusal *message* and not the answer.

What it does buy is worth having, and it is the lab's actual job. Four owner-facing numbers are
either wrong or admitted-unmeasured today:

- **M0208's published lead is a floor, not a measurement.** Its verdict says the book beat a
  meaningless book "by at least 4.3 points a year — provisional, and a floor rather than a
  measurement, because even the fairest control the lab can draw here still trades a quarter less
  than the book." Remedy 1 is what turns that into a number. *(The close-out's supporting figure —
  "304 estimated entries against the real book's 624" — is **624 as the close-out recorded it, to
  be confirmed by phase 1's probe**: `M0208-CGO-N20`'s recorded `trials.trades` is also 624 and an
  entry count is not a trade count. **The 0.487× ratio is the finding and is unaffected either
  way.** Phase 3 anchors against phase 1's measured number rather than the literal 624, and
  **phase 6 owns the correction** if they disagree.)*
- **M0225 has no honest control at all.** Phase 3 of the last set correctly refused to draw one
  under a rule it had just watched miss on M0221's identical chassis, so the only arm M0225's
  **−0.890** deficit can be computed against is `M0225-R50`, which traded **0.195×** and turned
  over **0.424×** the book it controls. **That deficit is recorded in `trials` and quoted in
  `docs/plans/HANDOVER_20261019-the-honest-control.md`; verified read-only at `e3aeeff`, no
  sentence in `methods.verdict` or `methods.analysis` quotes it** — so what this set can buy M0225
  is not a corrected sentence but a control it has never had. Phase 6 confirms the absence with its
  own sweep rather than assuming it, and invents no sentence to correct.
- **M0221's −0.42 is quoted against a control over-paying turnover by 1.95×**, so the honest
  reading is a range ("between 0 and 0.4 points") and not a figure.
- **M0201's honest control misses the match band by 0.0059** on one of two seeds.

And one thing the set must settle rather than carry a third time: **whether the weight-vector
remedy exists at all.** Its direction is not known (see Decision D7), and a measured dead end that
closes the leftover with a number is a legitimate and valuable outcome of this set.

### The user's own framing, verbatim

> THE HELD-SET SHADOW (leftover 3). control_draw.matched_names estimates the real book's churn from
> a FRESHLY-DERIVED top-N stand-in for real_prev. That stand-in is too fresh: a just-taken top-20
> is ranked 1-20 and the band only drops a name past rank 40, while a real held set accumulates
> names that have drifted to the edge and fall out far faster. Measured cost on M0208: the
> estimator reads 304 entries against the real book's 624 — 0.487x, uniform across eras
> (0.444/0.509/0.500). The fix is to carry a shadow of the real held set ACROSS decisions. THE
> CONSTRAINT: this is phase 1's module and FIVE recorded arms depend on its current contract, so it
> must be applied to every chassis at once, never to one file.
>
> THE WEIGHT VECTOR (leftover 2). Give the drawn names the real arm's own weight VECTOR — the k-th
> drawn name taking the k-th largest weight the real book holds that month. The two numbers that
> make the case: M0221-E50 pays 1.60x turnover on IDENTICAL names and IDENTICAL trades, against
> M0221-C50-PLC's 1.95x on matched churn — so about three-quarters of the excess was never the
> matched draw's to close. THE CONSTRAINT, and it is the hard one: this is a SECOND mechanism, it
> applies to only three of the nine chassis (M0221/M0225 cap-weighted, M0047 size-weighted under a
> ceiling, M0201 market-value-sized and re-sized monthly), and the original requirement R1 asked
> for ONE reusable rule — so a rule needing a per-chassis patch HAS ALREADY FAILED R1. The plan
> must confront that, not paper over it.
>
> HARD RULES: recorded trials and closed records are FROZEN — re-drawing an arm means a NEW arm
> under an amendment, never an edit to a recorded one. Changing matched_names changes the contract
> five recorded arms were drawn under; the plan must say what happens to those five. Do not spend a
> test-window look in any phase.

---

## The honest answer on R1, stated up front

The brief asked for it, so it is not buried in a phase file.

**R1 as the brief reads it — one reusable rule with no per-chassis patch — cannot be met by remedy
2, and no further work will make it meetable.** Two structural facts, both measured:

1. **Turnover on a weight-varying book is not in name space at all.** `M0221-E50` holds `C50`'s
   exact fifty names and records its exact 360 trades, and still turns over 1.60×. No rule that
   decides *which names* a control holds can reach that, however the entry count is derived. The
   matched draw is a name rule by construction.
2. **A weight vector cannot be produced by a shared module.** Each chassis computes its own:
   `m0221.weights` (market value, 10 % ceiling), `m0047.size_weights` (size under a ceiling),
   `m0201`'s per-company sizing with class splitting. A shared module has no way to produce any of
   them. Whatever is shared is the *assignment* of a vector the chassis hands over — never the
   vector.

**R1 in the sense `control_draw` already satisfies it is meetable, and is the most R2 can honestly
aim at.** `matched_partition` is a shared ordering contract that five chassis each adapt with their
own slot count, sector cap or keep band — and the lab already calls that one rule. A weight
contract of the same shape (the module owns the assignment; the chassis hands over its vector) is
the same standard, met the same way.

**So these are two rules on two axes, and this plan makes that visible in the layout** (Decision
D3): a **name** rule in `control_draw.py` and a **weight** rule in a new `control_weight.py`. A
single module named after one of them would be the paper-over the brief forbids.

---

## Requirements

This table is what `create-task` reads, and it is final: it maps every `R` to the phases that
**ended up** serving it after reconciliation, not to the draft's intentions.

| ID | What the user asked for | Phases |
|---|---|---|
| R1 | Carry a shadow of the real held set across decisions instead of re-deriving a fresh top-N stand-in for `real_prev`; apply it to every chassis at once, never to one file; say what happens to the recorded arms drawn under the current contract | **1, 2, 3** |
| R2 | Give the drawn names the real arm's own weight vector; confront that it is a second mechanism on three of nine chassis and has already failed the original "one reusable rule" requirement | **4, 5, 6** |
| R3 | State plainly what this buys — honest controls, not promotions | **3, 6** (and the **Why** above) |
| R4 | Recorded trials and closed records frozen; a re-draw is a NEW arm under an amendment; no test-window look in any phase | **2, 3, 5, 6** write; held by **every** phase as invariants I1–I3, I7 |

No requirement moved between phases during reconciliation and none is unowned. Two notes the
reconciler recorded rather than resolving by widening a **Satisfies** line:

- **Phase 5 also states "the gate takes none of these methods and this phase implies no
  promotion."** That is Decision D8 applied, which binds *every* phase that touches one of the
  nine, not R3's deliverable — R3's deliverable is the plain statement in this file's **Why** and
  in phase 6's handover. Phase 5's **Satisfies** stays `R2, R4`.
- **Phase 1 prices the membership convention and phase 6 carries it as a leftover.** That is a
  *finding*, not a requirement: it is a second, independent defect that R1 did not ask for and that
  no replay depth closes. It is carried, named and sized — never folded into R1's work (phase 2 is
  explicitly forbidden from attempting it).

R5 (the plan set on disk, committed, with phases, dependencies, file ownership and exit criteria)
and R6 (stop, report to `orch-honest-control-redraw`) are satisfied by the analyze session that
wrote this file and own no phase.

---

## Scope

**In scope**

- A shadow of the real held set, carried across decisions, written **beside** the shipped rule and
  never in place of it.
- A measurement, on every one of the eight chassis that call `control_draw`, of what that shadow
  changes — so "the shadow is a no-op here" is a recorded number.
- A new arm, under a new `Amendment`, on every chassis where the shadow moves the entry count.
- A free, trial-free measurement of the weight-vector mechanism on M0221, with three candidate
  assignment rules and an explicit STOP.
- If it clears: a weight contract in a new module, and new arms on M0221, M0225 and (if it closes
  the 0.0059 gap) M0201.
- The close-out: the R1 verdict, the owner-facing sentences the set moves, the journalled insights
  and the handover.

**Out of scope, and why**

- **Promotion of anything.** The gate takes none of the nine, three of the four live D17 refusals
  are inert, and the kin rule stands behind M0208's. Promotion is the owner's call on a separate
  day and nothing here implies it.
- **The walk-forward fold majority**, which is the operative clause for eight of the nine and which
  no amount of control re-drawing touches.
- **M0047's honest arms.** They already read 0.99/0.92 and 0.98/0.89 — band-clean, superseding.
  Re-drawing them retires nothing and spends compute (Decision D6).
- **M0202, M0215, M0227, M0243's honest arms**, unless phase 1 measures the shadow moving them.
- **Any edit to a recorded candidate, a recorded `Amendment` block, `choose`, `_banded_picks`, or
  any closed record.**
- **`lab test`.** Not invoked in any phase. Looks stay at 4.

---

## Invariants

Every phase holds all of these. A phase that cannot is a phase that stops and reports.

| # | Invariant |
|---|---|
| I1 | **No test-window look.** `lab test` is never invoked and `SEER_RESEARCH_TEST_STORE` is never read. Looks are 4 before and 4 after every phase, asserted. |
| I2 | **Recorded records are frozen.** No recorded trial, recorded candidate, recorded `Amendment` block, closed backtest report or existing lab row is edited or reformatted. A re-draw is a NEW arm under a NEW amendment appended after the existing ones. |
| I3 | **v1 keeps its body, byte for byte.** `matched_names`, `matched_partition`, `matched_book`, `keep_key`, `entry_key`, `churn`, `previous_decision_date` and `lookback_for` are not edited. A module body is outside `config_digest`, so an edit here would move thirteen recorded arms **without failing a single existing test** — phase 2 adds a golden-vector test so that it would. |
| I4 | **A lab command's exit code is read directly, never through a pipe.** `grep -v` owns the status of a pipeline. A `lab note` or `lab insight` is never retried on a non-zero exit without reading the journal first: `insights` is append-only and a double append is permanent. |
| I5 | **`git hash-object lab/lab.sqlite` is recorded before and after every phase.** A measurement phase leaves it unmoved. Any `lab` command may migrate the file on connect, even a read; a `sqlite3 "file:…?mode=ro"` query never does. |
| I6 | **`lab stage` runs in the checkout that owns the database and its commit takes no pathspec.** A pathspec re-reads the working tree and defeats the staging. |
| I7 | **Pre-registration before the run.** The method file and its `Amendment` block are committed before `lab run --amend`, on the same branch the database is committed on. A database committed ahead of the method files it refers to fails the sha freeze on a fresh clone. |
| I8 | **Re-run against re-run.** Any pre-run shape comparison measures both arms inside one `dev.run_registry` sweep. Recorded columns are compared only to recorded columns, and only by `lab control`. A recorded row is not reproducible to the digit. |
| I9 | **No mutable allocator state.** `dev.run_registry` reuses one allocator object per id across candidates and across walk-forward folds, so per-instance state leaks. The shadow is a pure function of the dates it is given. |
| I10 | **No allocator's `lookback` exceeds 473 bars** — `labkit.smoke_market`'s fixture size, and absolute. A dedicated test module beats shrinking a frozen feature window. |
| I11 | **The tree builds and `engine/.venv/bin/pytest engine/tests` is green at the END of every phase** — after that phase's last `lab stage` — with `engine/.venv/bin/ruff check engine` clean. **Not in the middle.** `test_lab_snapshot.py::test_the_committed_snapshot_is_the_export_of_the_committed_database` compares the committed snapshot to the committed database and reads the **working tree**, so between a `lab run --amend` and the `lab stage` that follows it, it is **expected red by construction** and the suite must not be run in that window. Phases 3, 5 and 6 each have that window — phase 5 has it two or three times — and each says so in the same words. |
| I12 | **Text the owner reads carries no ids, digests or code.** `methods.verdict` and `methods.analysis` are plain language. |

---

## Phases

| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID | Card |
|---|-------|-----------|---------|-------|-----------|------------|------|--------|------|
| 1 | Measure the shadow on every chassis, before it is built | R1 | `.workflows/plan/` (+ scratchpad) | **2** (+2 scratch) | — | NORMAL | `.workflows/plan/control-draw-remedies/phase-1.md` | — | — |
| 2 | The shadow rule, written beside v1 | R1, R4 | `engine/src/seer_engine/lab` | **3** | 1 | HARD | `.workflows/plan/control-draw-remedies/phase-2.md` | — | — |
| 3 | M0208's honest control, re-drawn under the shadow | R1, R3, R4 | `engine/.../lab/methods` + `engine/tests` + lab db | **5** (+1 scratch) | 2 | HARD | `.workflows/plan/control-draw-remedies/phase-3.md` | — | — |
| 4 | Measure the weight vector, before it is built | R2 | `.workflows/plan/` (+ scratchpad) | **2** | — | HARD | `.workflows/plan/control-draw-remedies/phase-4.md` | — | — |
| 5 | The weight rule, and the arms it earns | R2, R4 | `engine/.../lab` + methods + `engine/tests` + lab db | **9** branch G / **1** branch S | 4 | HARD | `.workflows/plan/control-draw-remedies/phase-5.md` | — | — |
| 6 | The R1 verdict, the sentences, and the close-out | R2, R3, R4 | `docs/plans` + `.workflows/plan/` + lab db | **9** | 3, 5 | NORMAL | `.workflows/plan/control-draw-remedies/phase-6.md` | — | — |

**Files** counts repository files the phase writes; scratchpad files are noted separately and are
never committed. Phase 5's count is branch-dependent by design (§0 of its plan).

### File ownership — exactly one phase owns each path

| path | owner | everyone else |
|---|---|---|
| `engine/src/seer_engine/lab/control_draw.py` | **2** (additions only) | 1, 3, 4, 5, 6 read and quote it; none edits it |
| `engine/tests/test_lab_control_draw.py` | **2** (one appended test) | — |
| `engine/tests/test_lab_control_draw_shadow.py` | **2** (new) | — |
| `engine/tests/test_lab_control_draw_twins.py` | **5** | **2 explicitly does not open it**, even though it carries the same `SMOKE_BARS = 473` literal |
| `engine/src/.../methods/m0208_capital_gains_overhang.py` | **3** | — |
| `engine/tests/test_lab_m0208_matched_draw.py` | **3** | — |
| `engine/src/seer_engine/lab/control_weight.py` (new) | **5** | — |
| `engine/tests/test_lab_control_weight.py` (new) | **5** | — |
| `engine/src/.../methods/m0221`, `m0225`, `m0201` | **5** | 4 subclasses their allocators in a throwaway prototype and mutates nothing |
| `engine/src/.../methods/m0047`, `m0202`, `m0215`, `m0227`, `m0243` | **nobody** | measured by 1, excluded by D4/D6 |
| `lab/lab.sqlite`, `web/data/lab.json` | **3, then 5, then 6** — append-only rows plus a regenerated export, written strictly in that order by hand | 1, 2, 4 open the database read-only and never run a `lab` command |
| `docs/plans/HANDOVER_20261020-control-draw-remedies.md` | **6** | — |
| `.workflows/plan/control-draw-remedies/phase-N-results.md` | **phase N** | 6 reads 1, 3, 4 and 5's; edits none |

### Dependency shape, and the fact that it does not buy parallelism here

```
1 ──▶ 2 ──▶ 3 ──┐
                 ├──▶ 6
4 ──▶ 5 ─────────┘
```

Two independent chains. **They will not be run concurrently.** The coordinator drives every phase
by hand, one at a time: a parallel wave of lab phases took this laptop down twice in the last
twenty-four hours, and a `dev.run_registry` sweep over the dev window holds the whole research
store in memory (~1 MB per symbol). **Spawn one phase at a time, cheapest first, and never two
backtest sweeps at once.**

**So does the ordering matter?** Yes, in two places and only two:

- **2 must follow 1, and 3 must follow 2.** Phase 1 chooses the replay depth K that phase 2
  implements, and names which chassis phase 3 re-draws. Building first would be guessing.
- **5 must follow 4.** Phase 4 can kill phase 5 outright, and that is its job.

Everywhere else the order is free. **The recommended running order is 1, 2, 3, 4, 5, 6** — remedy 1
is the one with a known mechanism and an owner-facing number waiting on it. **Pull phase 4 to the
front if you want the R2 verdict earliest**; it depends on nothing, it is the only phase carrying a
real STOP, and a STOP there shrinks phase 5 to nothing and changes phase 6's shape. Phase 5 and
phase 2 touch no file in common, so no ordering between them is required either way.

---

### Phase 1 — Measure the shadow on every chassis, before it is built
**Satisfies:** R1
**Owns:** a scratchpad probe script; `.workflows/plan/control-draw-remedies/phase-1-results.md`
**Does not touch:** any engine source, any method file, `lab/lab.sqlite`, `web/data/lab.json`
**Exit criteria:**
- A table, one row per chassis (M0047, M0201, M0202, M0208, M0215, M0221, M0225, M0227, M0243),
  giving over the whole dev window: the **true** cumulative entry count of the real book from a
  full forward replay of its own band; the **current estimator's** count; and a **K-step backward
  replay's** count for every K from 1 to that chassis's affordable maximum.
- A per-chassis verdict in one word: *shadow needed* or *shadow is a measured no-op*, with the
  ratio that decides it.
- For M0208, the smallest K whose estimate reaches **≥ 0.90** of the true entry count — and the
  bars that K costs, checked against `473 − lookback`. **This K is a PROPOSAL**: phase 3 verifies
  it on its own probe and ships its own number (see *The replay depth K*, below).
- The absolute `m0208_true_entries` and `m0208_shipped_entries` carried into the contract block, so
  phase 3 anchors against a measured number and not against the close-out's 624.
- The **membership decomposition** — `(b) SHIPPED` against `(c) K = 1`, per chassis — which prices
  a *second*, independent defect that no replay depth closes. It is handed to phase 6 as a new
  leftover and is **not** folded into phase 2.
- The corrected quarterly step for M0201/M0202: `m0201.PREV_SPAN = 70` bars, so `K_max = 3`, not
  the 78 / `K_max = 2` an earlier draft of the analysis gave.
- `git hash-object lab/lab.sqlite` identical before and after. Looks 4 → 4.
- **STOP rule:** if no affordable K reaches 0.90 on M0208, the phase records that and stops. A
  bounded replay is then not the remedy, and phases 2 and 3 do not run as designed.

### Phase 2 — The shadow rule, written beside v1
**Satisfies:** R1, R4
**Owns:** `engine/src/seer_engine/lab/control_draw.py` (**additions only**);
`engine/tests/test_lab_control_draw_shadow.py` (new); one added golden-vector test in
`engine/tests/test_lab_control_draw.py`
**Does not touch:** any method file; the lab database; the existing bodies of `matched_names`,
`matched_partition`, `matched_book`, `keep_key`, `entry_key`, `churn`, `previous_decision_date`,
`lookback_for`
**Exit criteria:**
- A pure, stateless, bounded backward replay that reconstructs the real book's held set at the
  previous decision, plus the lookback arithmetic that pays for it, plus `SHADOW_RULE_ID`
  (`"matched-draw-v2"`) **beside** `RULE_ID`, which is not bumped.
- **The names, which are the plan set's one vocabulary and which phases 3 and 5 code against
  verbatim:** `Replay`, `ShadowReading`, `max_shadow_depth`, `shadow_lookback_for`,
  `shadow_decision_dates`, `shadow_selection`, `shadow_book`, `SHADOW_RULE_ID`, `FIXTURE_BARS`.
- **No K is baked anywhere.** `depth` is a required keyword-only argument with no default on both
  public entry points, so the number lives in the method file (`SHADOW_DEPTH`) and never here.
- **The membership convention is NOT attempted here.** It is a second defect, no replay depth
  closes it, and the v2 block takes no `members` argument.
- A **golden-vector test pinning v1's output** for a fixed input, so a future in-place edit to the
  frozen path goes red. Today nothing would catch it: a module body is outside `config_digest`.
- The new tests live in their own module and every allocator still fits **473 bars**.
- `ruff check engine` clean; `pytest engine/tests` green, including
  `test_every_recorded_configuration_still_digests_to_its_recorded_digest`.
- `git hash-object lab/lab.sqlite` unmoved. Looks 4 → 4.

### Phase 3 — M0208's honest control, re-drawn under the shadow
**Satisfies:** R1, R3, R4
**Owns:** `engine/src/seer_engine/lab/methods/m0208_capital_gains_overhang.py` (**append + three
pin-point edits**: the import line, an Amendment-2 docstring paragraph, and the `amendments=`
tuple); **`engine/tests/test_lab_m0208_matched_draw.py`** (its "exactly one amendment" test is
inverted to the post-run truth, plus the A2 guards — no other phase owns this module); the lab rows
it writes; `web/data/lab.json`; `.workflows/plan/control-draw-remedies/phase-3-results.md`
**Does not touch:** `control_draw.py` (quoted, never edited); `MatchedDrawAllocator`; the
`MATCHED_DRAW` amendment block; `choose`; `_banded_picks`; `previous_month_end`; `OverhangParams`;
**any other method file at all** — the phase's own three-condition rule resolves to *M0208 and
nothing else*, and a chassis phase 1 names that this rule does not cover is **recorded and handed
to the coordinator, never absorbed**
**Exit criteria:**
- A new allocator id (`M0208-A2`) and a new `Amendment` block, **appended after** the existing one,
  with `why`, `hypothesis` and `expected_failure` written before any result is seen.
- A free pre-run probe showing: the calendar agreement between `control_draw.previous_decision_date`
  and `m0208.previous_month_end` over the whole dev window (anchor 0); the true entry count against
  phase 1's measured number (anchor 1); the unguarded `K = 1` ladder reproducing 304 (anchor 2);
  and the whole `K` ladder — all before the amendment is committed.
- **`SHADOW_DEPTH` set from this phase's own ladder**, not from phase 1's proposal. The two may
  legitimately differ because this phase's `Replay` closes the SPY 200-day switch inside the replay
  and phase 1's shipped column reproduces amendment 1's unguarded reading; both numbers are
  reported, with one sentence saying why.
- Pre-registration committed, then `lab run M0208 --amend`, then `lab control M0208`.
- The new arm's measured ratios reported against the band-clean window **500 … 752 trades /
  2.4492 … 3.8268 turnover** (`band_verdict` is inclusive, `0.80 × 624 = 499.2` so 499 reads
  `warn`; turnover runs 1.0362× trades on this equal-slot chassis so the **high** side binds on
  turnover), and D17's live state for M0208 re-read through `store.connect_readonly`.
- The published sentence updated by `lab note` **only if** the arm is band-clean: M0208's verdict
  currently says "at least 4.3 points a year — provisional, and a floor". A `warn` arm leaves it a
  floor and the phase says so. The note is **rehearsed on a copy via `SEER_LAB_DB`** first —
  `--dry-run` does not protect `lab note`.
- `lab stage`, commit, push — **merging, never rebasing, on a rejected push**. Looks 4 → 4.
- **The phase explicitly states that the gate still refuses M0208**, on the kin rule, whatever D17
  now says.
- **The no-op branch:** if phase 1 handed over `stop: true`, or this phase's own probe returns
  NO-GO, **no file is edited and no `lab` command is run**. The phase writes `phase-3-results.md`
  with the verdict word `STOP`, the ladder, both anchors, the sentence *"M0208's published lead
  stays a floor"*, `published_sentence_moved: false` for phase 6, and tells the coordinator to run
  phase 4 next.

### Phase 4 — Measure the weight vector, before it is built
**Satisfies:** R2
**Owns:** `.workflows/plan/control-draw-remedies/phase-4-weight-probe.py` (the prototypes, the free
probe and the sweep harness — a committed `.workflows/plan/` file, **not** under `engine/`, and
imported by nothing); `.workflows/plan/control-draw-remedies/phase-4-results.md`
**Does not touch:** any file under `engine/src`; any method file; `engine/tests/*`;
`lab/lab.sqlite`; `web/data/lab.json`. The prototypes **subclass** the shipped allocators and
override only the weighting step — they never mutate a shipped class, rebind a module attribute or
reuse a recorded allocator id.
**Exit criteria:**
- Turnover and trade counts for `M0221-C50`, `M0221-C50-PLC` (the shipped matched draw) and
  **four** prototype weight-assignment rules, all measured **inside one `dev.run_registry` sweep
  per chassis** so every comparison is re-run against re-run (I8). M0221 and M0201 are swept in
  **separate processes, one at a time** — a twelve-arm sweep holds two research panels at once on a
  15 GB laptop.
- The four rules are: **(A)** the real book's sorted weight vector assigned in the control's
  month-keyed order; **(B)** the same vector assigned in the date-free keep order, so a held name
  holds its rung; **(C)** the control's own sizes re-shaped so the ceiling binds at the real book's
  rate; **(D)** keeps first in keep order and entrants last, down the sorted vector, so an entrant
  always takes a bottom rung as a real top-N's entrant does. **D is pre-registered here, in this
  plan, before any number is seen** — derived from the mechanism, not invented after watching A, B
  and C miss. The assignment order is itself a turnover generator and is the open question.
- A yes/no, with the number: does any rule bring M0221's control to **≤ 0.5563 turnover** (1.25×)
  while holding trades inside 0.8–1.25×?
- The same measurement for M0201's 0.0059 gap, on its own chassis — **answered independently**, so
  an M0221 STOP cannot suppress an M0201 GO or the reverse.
- The winner named by **both** its letter and phase 5's branch key (`G-entry` / `G-ladder` /
  `G-size` / `G-bottom`), so phase 5's §0 is a lookup and not a judgement.
- `git hash-object lab/lab.sqlite` unmoved. Looks 4 → 4. No `lab` command is run at all.
- **STOP rule:** if no rule lands M0221 inside `WARN_BAND`, phase 5 draws neither M0221 nor M0225.
  The phase records the measurement, leftover 2 closes with a number instead of being carried a
  third time, and phase 6 writes that up as the answer. **This is a legitimate outcome, not a
  failure**, and the phase must not keep inventing rules to avoid it: **four rules, measured, then
  stop. There is no rule E, under any result.**

### Phase 5 — The weight rule, and the arms it earns
**Satisfies:** R2, R4
**Owns:** `engine/src/seer_engine/lab/control_weight.py` (new);
`engine/tests/test_lab_control_weight.py` (new);
`engine/src/seer_engine/lab/methods/m0221_cap_weighted_top_n.py` (append);
`engine/src/seer_engine/lab/methods/m0225_cap_weighted_top_n_repaired.py` (append);
`engine/src/seer_engine/lab/methods/m0201_treasury_beta_size_weighted.py` (append, **only** if
phase 4 showed the rule closes its gap); **`engine/tests/test_lab_control_draw_twins.py`** — two of
its tests pin the pre-amendment file state and are inverted to the post-run truth; **phase 2
explicitly does not open this module**, so there is no collision; the lab rows it writes;
`web/data/lab.json`; `.workflows/plan/control-draw-remedies/phase-5-results.md`
**Does not touch:** `control_draw.py` (quoted as it stands after phase 2 — it imports exactly one
name from it, `keep_key`, which is on the frozen-v1 list, and it never reads the v2 shadow);
`engine/tests/test_lab_control_draw.py` and `test_lab_control_draw_shadow.py` (phase 2);
`m0208` and its test module (phase 3); m0047, m0202, m0215, m0227, m0243
**Exit criteria:**
- **§0's branch key written first, in writing, before an editor is opened** — one of **S**,
  **G-entry** (rule A), **G-ladder** (B), **G-size** (C), **G-bottom** (D). Any ambiguity in phase
  4's file resolves to **S**. There is no sixth key and this phase re-measures nothing.
- **Branch G:** the weight-assignment contract in its own module, with its own tests, and the
  per-chassis adapter in each method file — the same shape `matched_partition` already has, and the
  module docstring says so rather than claiming one rule.
- New allocator ids and new `Amendment` blocks appended; pre-registration committed before each
  `lab run --amend`; **one `lab run` at a time**.
- `lab control M0221 M0225` (and M0201 if drawn) reporting the measured ratios, and the supersession
  declarations that retire `M0221-R50`, `M0221-C50-PLC` and `M0225-R50` **only if** the new arms
  read `OK`.
- **M0225's −0.890 stated accurately.** It is recorded in `trials` and in the previous handover and
  appears in **no** owner-facing string, so a band-clean arm gives M0225 an honest margin sentence
  for the first time rather than correcting a wrong one; if no arm is drawn, the phase records that
  M0225 still has no honest control and invents no sentence.
- **`controls=` is not declared** on M0221's or M0225's arms (D9) — the `sibling-stem` rung already
  resolves them and the `declared` rung has never fired in this lab; M0201's stem is re-checked
  before its id is written, and a declaration there is recorded as the rung's first use.
- Every `lab note` **rehearsed on a copy via `SEER_LAB_DB`** first — `--dry-run` does not protect it.
- `lab stage` after each run, commit with **no pathspec**, push — **merging, never rebasing**, on a
  rejected push. The suite is run at each `lab stage` boundary and at the end, never in the window
  between a `lab run` and its stage. Looks 4 → 4.
- **Decision D6 recorded under either branch** — M0047 excluded on measurement, not omitted.
- **If phase 4 stopped (branch S)**, this phase is one results section and **no code at all**: no
  module, no test, no method-file edit, no `lab` command, no commit to `engine/`. The database hash
  is identical before and after.

### Phase 6 — The R1 verdict, the sentences, and the close-out
**Satisfies:** R2, R3, R4
**Owns:** `docs/plans/HANDOVER_20261020-control-draw-remedies.md` (new);
`.workflows/plan/control-draw-remedies/phase-6-results.md` and `insights/*` (new);
`methods.verdict` and `methods.analysis` via `lab note`; `lab insight` rows; the final `lab stage`
**Does not touch:** any file under `engine/src`; the results files of phases 1, 3, 4 and 5 (read,
never edited); the `trials`, `method_amendments` and `candidates` rows phases 3 and 5 recorded
**Exit criteria:**
- The R1 answer written where a reader will find it: two rules on two axes, R1 as literally written
  is unmeetable, R1 in the sense `control_draw` already satisfies it is met — with the two
  structural reasons and the `E50` number behind them.
- **A sweep of every `methods.verdict` and `methods.analysis` in the lab — all 276 methods, not
  just the nine** — because the previous close-out's six phases missed four sentences, three of
  them in `verdict`. The three sentences this set names are a **floor** on the list, never the list.
- Every sentence the sweep marks MOVED, corrected in plain language with no ids or digests. At
  minimum M0208's "at least 4.3 points a year" and M0221's "between 0 and 0.4". **M0225's −0.890 is
  NOT among them**: verified read-only at `e3aeeff` it appears in no owner-facing string, so the
  handover records that M0225 has no honest control and that the lab publishes no claim resting on
  the figure — **it invents no sentence to correct**.
- **The 624 figure settled.** If phase 1's and phase 3's probes measured a true entry count near
  1248, this phase corrects the close-out's "304 against 624" in the handover and in an insight,
  says the **ratio is unaffected and remains the finding**, and — the sweep finding no published
  string quoting it — warrants no `lab note` for it alone.
- All counts **re-derived read-only**, never copied: the honest-control handover's table (849 / 275
  / 11 / 470 / 853 / N=164) is stale and reads **855 / 276 / 11 / 478 / 859 / N=165** at `e3aeeff`
  before this set. Leftovers **4, 5 and 7 of that handover are already closed** (insights 471–474
  in `316c5cc`; the eight sentences in `a8c07de` / `ef972c1`; M0261 in `e3aeeff`) and this phase
  **verifies** that read-only rather than assuming it, and re-does none of it.
- Every `lab note` and `lab insight` **rehearsed on a copy via `SEER_LAB_DB`** — `--dry-run` does
  not protect either; only `lab test` and `lab gate-probe` read `args.dry_run`.
- Insights journalled **last, one command at a time, exit code read directly, never piped** (I4).
- `lab stage` run last, `lab/lab.sqlite` and `web/data/lab.json` agreeing row for row, committed
  together with no pathspec, pushed — **merging, never rebasing**, on a rejected push. The suite is
  run **after** the final stage, not in the window between the first write and it.
- A leftovers list that carries forward what this set did not do, that **closes leftovers 1, 2
  and 3 of the honest-control handover with a result each** — including a STOP, if that is what
  phase 4 measured — and that carries **the membership convention as a new leftover of its own**,
  with phase 1's number attached. It is a second, independent defect that no replay depth closes
  and it is explicitly not R1's.
- **It handles a set in which phase 5 wrote no code** (branch S): its SHAPE-B input block, its
  leftover-2-closes-with-a-number row, and its "what this set did not do" section all already read
  that way.
- Looks 4 → 4, asserted and stated.

---

## Reconciliation Log

Round 1, 2026-10-20. Every row was resolved by **editing the plan files**, not by reporting. The
"where" column names every document the fix had to land in.

| # | Conflict | Where | Resolution |
|---|---|---|---|
| C1 | **Contract drift — the v2 interface names.** Phase 3 coded against `control_draw.shadow_held(*, dates, step, start=frozenset())` and `lookback_for_replay(inner, steps)`; phase 2, which owns `control_draw.py`, ships `Replay`, `ShadowReading`, `shadow_selection(replay, data_date, *, depth, cadence)`, `shadow_book`, `shadow_lookback_for`, `max_shadow_depth`, `shadow_decision_dates`, `SHADOW_RULE_ID`, `FIXTURE_BARS`. | phases 2, 3; index | **Phase 2's names win (rule 3, one owner per file region).** Phase 3's `Requires` block, its import line, its allocator body, its tests and its prose were rewritten to phase 2's spellings verbatim, and `shadow_held` / `lookback_for_replay` are marked **withdrawn** in both files. Phase 3's `step(d, carried)` became a `Replay` closure returning `(pool, book)`. Phase 2 now states that its table is the plan set's one vocabulary. Phase 5 was checked: it imports only `keep_key` and names no v2 symbol — **no change needed**. |
| C1b | **A behavioural fork inside C1: who owns the replay calendar.** Phase 3 wanted to hand in its own date list built from `m0208.previous_month_end(grid, d)` (SPY's own grid); `shadow_selection` derives its own from `control_draw.previous_decision_date` (the NYSE calendar). | phases 2, 3; Decisions | **Settled on rung 6, the code**, and the losing branch edited out. `previous_decision_date` returns `dates.prev_session(first of the month)`; `previous_month_end` returns SPY's last column strictly before the first of the month — **the same session wherever SPY trades, which is every session from 1993**. Phase 3 now calls `shadow_selection` and supplies no calendar; `previous_month_end` keeps its existing callers and is not deleted. **A free anchor-0 check was added to phase 3's pre-run probe** asserting the agreement over every decision of the dev window, with a STOP if it ever fails, plus a test pinning the one-step identity. |
| C2 | **Factual error — the M0201/M0202 lookback budget.** The analysis gave the quarterly step as **78** bars and one affordable extra step (`K_max = 2`). Phase 1 measured `m0201.PREV_SPAN = 70`, so `inner = 261` and `K_max = 3`. | analysis; phase 2 | Corrected in the analysis's *Measured lookback budget* table (**2** extra quarterly steps, 70 bars a step) and in its `PREVIOUS_DECISION_BARS` note, with a dated correction paragraph. Phase 2's comparison table was annotated so its `inner = 305` (a *monthly* reading, which is why a quarterly chassis must not call `max_shadow_depth`) no longer reads as a contradiction of phase 1's 261. Phase 1's run-time computation stands as the authority. |
| C3 | **Factual error — M0208's band bar.** The index and the analysis said "≥ 499 trades / ≥ 2.449 turnover". `band_verdict` is **inclusive** and `0.80 × 624 = 499.2`, so 499 reads `warn`. | analysis; index; phase 6 | Corrected everywhere to **≥ 500 trades and ≥ 2.4492 turnover**, with the high side binding on **turnover** (turnover-per-trade runs **1.0362×** on this equal-slot chassis, so ≤ 1.25 turnover ⇒ ≤ 1.2063 trades ⇒ **≤ 752**) and the band-clean window stated as **500 … 752 trades / 2.4492 … 3.8268 turnover**. Phase 3 already had it right and was left alone. |
| C4 | **Contract drift — where the replay depth K comes from.** Phase 1 "chooses" K, phase 2 "implements" it, phase 3 caps it at 8 — three phases describing one number three ways, with no statement of what happens when phase 1's probe and phase 3's probe disagree. | phases 1, 2, 3; index | Made an explicit three-link chain, in the same words in all four documents: **phase 1 proposes** (`k_proposed`), **phase 3 verifies on its own probe and ships its own number**, **phase 2 never sees a K**. Phase 2 was checked and **hardcodes none** — `depth` is keyword-only with no default on both entry points — and its K-contract table now says so and drops `k_for_phase_2` from what it consumes. The reason the two probes may differ (phase 3's `Replay` closes the SPY 200-day switch inside the replay; phase 1's shipped column reproduces amendment 1's unguarded reading) is stated in both, as **expected, not an error**. |
| C5 | **Factual error — M0225's −0.890.** The index's **Why** claimed it is "still quoted against an arm that traded 0.195×", implying a published sentence. Phase 6 verified at `e3aeeff` that **no `methods.verdict` or `methods.analysis` string quotes it**: it lives in `trials` and in the previous handover. | index; phases 4, 5 | The bullet was **softened, not deleted**: M0225 has **no honest control at all**, and the deficit is recorded in the lab and in the handover rather than in a sentence the owner reads. Phases 4 and 5 were brought into line (phase 4's **Satisfies**, its STOP consequences; phase 5's branch-S bullet, its step 4c–4f note, its exit criterion 4). Phase 5's "the single most wrong owner-facing number" claim was corrected. Phase 6 already had it right and **confirms the absence with its own sweep rather than assuming it**. |
| C6 | **Factual error, possible — entries vs trades.** "304 estimated entries against the real book's 624" may have conflated an entry count with a trade count: `M0208-CGO-N20`'s recorded `trials.trades` is **also 624**. | analysis; index; phases 1, 2, 3, 6 | Every site now states it as **"624 as the close-out recorded it, to be confirmed by phase 1's probe"**, with the standing note that **the ratio is the finding and the absolute is a cross-check**. Phase 1 carries `m0208_true_entries` forward in its contract block; **phase 3's probe anchor was changed from the literal 624 to phase 1's measured number** (anchoring on 624 would have made phase 3 STOP on a correct measurement); phase 2's two code docstrings were hedged so the committed module cannot be wrong either way; **phase 6 owns the correction**, and — the sweep finding no published string — warrants no `lab note` for it alone. The 500 … 752 band is untouched: it derives from `trials.trades`, which *is* a trade count. |
| C7 | **Unsafe rehearsal — `--dry-run` is not a safety net for `lab note` / `lab insight`.** Only `lab test` and `lab gate-probe` read `args.dry_run`; `_note` and `_insight` commit inside `with conn:` regardless. | phases 3, 5, 6; index | Phase 6 already used the DB-copy rehearsal. **The same `SEER_LAB_DB=<copy>` rehearsal block, with the command, the read-back and the `git hash-object` proof, was added to phase 3's `lab note` step and phase 5's step 3f** (covering M0225's and M0201's notes too), and named in the index's phase-3, phase-5 and phase-6 exit criteria. |
| C8 | **Broken invariant mid-phase — the snapshot test.** `test_the_committed_snapshot_is_the_export_of_the_committed_database` reads the **working tree**, so it is red by construction between a `lab run --amend` and the `lab stage` that follows. Phase 6 said so; phases 3 and 5 said it inconsistently or in passing; invariant I11 said "green at the end of every phase" without reconciling the two. | index (I11); phases 3, 5, 6 | **I11 was rewritten**: green at the **END** of the phase, after that phase's last `lab stage` — *not* in the middle — and the suite **must not be run** in the window. The same note, in the same words, now appears in phases 3, 5 and 6, with phase 5 told it has that window **two or three times** (once per `lab run`) and must be green at each stage boundary and at the end. |
| C9 | **Scope creep risk — the membership convention.** Every method file reads **today's** member list at the earlier date. Phase 1 prices it (0.034 on M0047) and no replay depth closes it. | phases 2, 6; index | Confirmed **phase 2 does not attempt it**, and made that explicit: a new "Leaves alone" entry stating it is a **second, independent defect, not R1's**, that the v2 block takes no `members` argument, and that it is carried to phase 6. **Phase 6's "New, from this set" leftover 14 now names it** with phase 1's number attached. The index's phase-1 and phase-2 exit criteria say the same. Recorded in the Requirements table as a finding, **not** as a requirement — no `Satisfies` line was widened to absorb it. |
| C10 | **A push rejection must be merged, never rebased.** A rebase replays a stale `lab.sqlite` over the live shared file. Phase 6 said "fetch, merge"; phases 1, 3 and 5 said only "never rebase" or nothing. | phases 1, 3, 5; index | All three now carry the full rule in the same words: **fetch, merge `origin/main`, re-run `lab stage` so the snapshot matches the merged database, re-check that trial `n` is contiguous, commit the re-stage with no pathspec, push again.** Named in the index's phase-3, phase-5 and phase-6 exit criteria. |
| C11 | **Stale counts.** The honest-control handover's "lab after this run" table (849 / 275 / 470 / 853 / N=164) is stale, and its leftovers 4, 5 and 7 are already closed. | index; phase 6 | Phase 6 already measured **855 dev trials / 276 methods / 11 amendments / 478 insights / trial ids 1..859 / N = 165** and already verifies leftovers 4, 5 and 7 as closed (`316c5cc`; `a8c07de` + `ef972c1`; `e3aeeff`) **read-only rather than assuming**. The index's phase-6 exit criteria now state the numbers and the three closed leftovers explicitly, so no phase can re-do closed work. Checked: **no other phase re-does any of it.** |
| C12 | **Duplicate/contradictory scope — three rules or four.** Phase 4 measures **four** weight-assignment rules (A, B, C and a pre-registered D); phase 5's branch-key table offered only four keys for three rules, phase 6's input schema read `A \| B \| C`, and the index said "at least three … three rules, measured, then stop". A phase-4 win on rule D would have been classified **ambiguous → S** and silently thrown away. | index; phases 4, 5, 6 | **Four rules everywhere.** Phase 5 gained a fifth key, **`G-bottom` (rule D)**, and its table now carries phase 4's letter beside each key; its branch-S bullets ask for four rows and forbid inventing a *fifth*. Phase 6's SHAPE-A gained `winning_rule: A\|B\|C\|D` plus an explicit `branch_key`, and SHAPE-B gained `rule_D`. Phase 4 now hands over the winner by **both** letter and key. The index's phase-4 block describes all four and states "there is no rule E". |
| C13 | **Ownership drift — phase 4's probe location.** The index said "a scratchpad prototype and harness"; phase 4 writes a committed `.workflows/plan/control-draw-remedies/phase-4-weight-probe.py`. | index | **Phase 4 is the owner and its choice stands** (it is outside `engine/`, imported by nothing, and `run_registry` checks no git state). The index's phase-4 **Owns** line and Files count were corrected to match. |
| C14 | **Naming drift — the method-file depth constant.** Phase 2's K-contract prescribed `SHADOW_DEPTH`; phase 3 wrote `REPLAY_STEPS`. | phases 2, 3 | **`SHADOW_DEPTH` is the set's one spelling** (it matches `depth=`). Phase 3's constant, docstring, allocator, tests and prose were renamed; `REPLAY_STEPS` is marked withdrawn in both files. |
| C15 | **Unowned file — `engine/tests/test_lab_m0208_matched_draw.py`.** Phase 3 must edit it (`test_m0208_carries_exactly_one_amendment_of_one_arm` goes red on the amendment) but the index's phase-3 **Owns** list never named it. | index | **Assigned to phase 3**, which is the only phase that touches it. Added to the index's phase-3 **Owns** line and to the new file-ownership table. |
| C16 | **Unowned file — `engine/tests/test_lab_control_draw_twins.py`.** Phase 5 inverts two of its pre-amendment assertions; the index's phase-5 **Owns** list never named it, and the analysis's Reference List attributed it to "2, 5". | index; analysis | **Assigned to phase 5 alone.** Phase 2 already states it does not open the module (and declines the drive-by `SMOKE_BARS` consolidation for that reason). The index's phase-5 **Owns** line and the analysis's Reference List row were corrected. |
| C17 | **Scope drift — phase 3's conditional second chassis.** The index said phase 3 may touch "any other method file phase 1 named as *shadow needed*"; phase 3's own three-condition rule resolves to **M0208 and nothing else** and tells the session to hand anything else to the coordinator. | index | **Phase 3's stricter rule wins** — it is the owner, it is decided, and a quietly-grown second method file means a second amendment and a second pre-registration on a laptop a parallel wave has already taken down twice. The index's phase-3 **Does not touch** line now reads "any other method file at all". |
| C18 | **Missing no-op branch.** Phase 5 states its branch-S behaviour in full; **phase 3 did not state what it does when phase 1 STOPs**, and the index's phase-3 block did not either. | phase 3; index | A *"The no-op branch, stated before the phase starts"* section was added to phase 3 (no file edited, no `lab` command, a `STOP`-headed results file, the sentence *"M0208's published lead stays a floor"*, `published_sentence_moved: false` handed to phase 6, and run phase 4 next) and mirrored into the index's phase-3 exit criteria. Phase 6 was checked and already handles a set in which phase 5 wrote no code (its SHAPE-B input block). |
| C19 | **D9 / D10 (added by the coordinator after the draft).** The `controls=` declaration and the once-per-decision allocator call were settled but recorded nowhere, and D9 asks phases 3 and 5 to say whether they use `controls=`. | index; phases 3, 5 | **D9 and D10 added to the Decisions table.** Phase 3's `_a2` docstring and phase 5's amendment section now each say **they do not declare `controls=`**, why (the `sibling-stem` rung already resolves them; the `declared` rung has never fired in this lab; a first use inside a recorded trial is the wrong place to find out it is wrong) and that it would be *safe* to add. **M0201 is the one arm told to re-check its stem** before its id is written. |

**Nothing was found of these classes:** no deleted-then-used symbol (the set deletes nothing and
renames nothing); no unmet `Requires` (phase 3 depends on phase 2, phase 5 depends only on
`keep_key`, which exists on `main` today); no broken-build phase (phase 2 is additions-only, phase
5 touches no file phase 2 touches); no ordering violation (every dependency points backward); no
unowned impact point (all eleven of the analysis's are owned, including the deliberate M0047
exclusion); and no unowned requirement id.

---

## Decisions

Every fork settled here rather than left for a phase session to meet at 3am, with the rung of the
precedence ladder that settled it.

| # | Fork | Chosen | Rung |
|---|---|---|---|
| D1 | Cut a worktree, or plan against `main`? | **`main`, no worktree.** Pre-registration and the database must be committed on the same branch | 6: convention + the honest-control handover's measured note — "a lab database committed ahead of the method files it refers to puts `main` in a state where a fresh clone fails the sha freeze"; and every `lab: MNNNN pre-registered` commit in this repo's log is on `main` |
| D2 | Carry the shadow as allocator state, or recompute it as a bounded backward replay? | **A pure, bounded backward replay.** No instance state anywhere | 1: invariant I9 — `dev.run_registry` reuses one allocator object per id across candidates and folds, so per-instance state leaks between them; a pure replay is also reproducible, parallel-safe and testable on the smoke fixture |
| D3 | Put the weight rule in `control_draw.py`, or in its own module? | **A new `control_weight.py`.** The layout says what the prose says: two rules, two axes | 5: the user's raw input — "If the honest answer is that these are two rules and R1 cannot be met, say so in the plan" — plus the analysis finding that turnover is not in name space |
| D4 | "Applied to every chassis at once" — re-draw every chassis, or measure every chassis? | **One shared rule, every chassis measured under it, re-drawn only where the shadow moves the entry count.** A chassis where the shadow is a measured no-op is not re-drawn | 5: the user's raw input — the constraint's purpose is that the thirteen arms not be drawn under two different rules, and a measured no-op is not a second rule — plus R4, since a re-draw costs a new arm and drawing a no-op spends compute to measure nothing |
| D5 | "FIVE recorded arms depend on its current contract" — which five, and what happens to them? | **The measured count is thirteen arms** (lab trials 841–853), of which four call `matched_names`/`matched_book` and nine call `matched_partition`; an in-place edit to `matched_partition` moves all thirteen. "Five" reads best as the five **methods** whose honest control is band-clean and supersedes — M0047, M0202, M0215, M0227, M0243, nine arms between them. **What happens to all of them: nothing.** v1 keeps its body byte for byte (I3), every recorded arm keeps its allocator id, and phase 2's golden-vector test makes an accidental edit go red — which nothing would catch today, because a module body is outside `config_digest` | 4: the index's Requirements table and the plan's own invariants, resolved against the measured code and the `trials` table |
| D6 | Does remedy 2 apply to M0047, as the brief lists? | **No — excluded on measurement.** M0047's honest arms already read 0.99/0.92 and 0.98/0.89, band-clean and superseding; re-drawing retires nothing. Its allocator also has only 46 bars of lookback headroom | 4: the Requirements table read against the honest-control handover's own measured ratio table |
| D7 | Write the weight rule, or measure it first? | **Measure first, with a STOP.** Its direction is unknown: `M0221-C50-PLC` is already drift-neutral (it uses the real chassis's own weighting code on its own drawn names), and attaching a *foreign* vector makes the control's target move with the real book's prices while its holding moves with its own — two uncorrelated drifts cross the 1 %-of-equity band more often than one tracked drift. The remedy may raise turnover. The existing numbers cannot tell us which | 4: the index's Why ("whether the weight-vector remedy exists at all") plus the analysis section *The weight-vector mechanism, examined* |
| D8 | Should the set promise M0208 a promotion if D17 clears? | **No, and every phase that touches M0208 must say so.** The kin rule stands immediately behind D17 and `failed_kin(M0208)` returns a test-failed method | 5: the user's raw input — "THE GATE TAKES NONE OF THE NINE … or it is selling something it cannot deliver" |
| D9 | A new `Candidate` field is safe, and the `declared` resolver rung is dormant | `Candidate` already carries `supersedes`, added the same way; `lab.method.config_text` renders only rules + allocator id + params, so a new `Candidate` field is **outside `config_digest` by construction**. `control_shape.DECLARATION_ATTR = "controls"` exists but **no method file sets it**, so the `declared` rung never fires today. A new arm **may** declare `controls=` to avoid a first-declared guess — **phases 3 and 5 say whether they use it**, and both say no: M0208's and M0221/M0225's arms resolve correctly on the `sibling-stem` rung, and a `Candidate` field exercised for the first time inside a recorded trial is a strictly worse place to find out it is wrong. M0201 is the one arm whose stem is re-checked before its id is written, and a declaration there is recorded as the rung's first use | rung 6: the code |
| D10 | The allocator is called once per decision, not twice | `MONTHLY_HOLD_FRAC_GOTRADE` has `resize_cadence=None`, and `is_resize_session` returns `False` unconditionally without one. So there are **no resize-only allocator calls** to corrupt a shadow and **no off-cadence call** to account for: `shadow_selection` is reached exactly once per decision date, and the replay's purity (I9) is about sweep order and fold reuse, never about an extra intra-month call | rung 6: the code |

---

## Open Questions

**None.** Every fork was decidable from the ladder, every requirement id is owned by a phase, and
no branch of any fork is irreversible. Reconciliation added one fork (C1b, who owns the replay
calendar) and settled it on rung 6 — the code — rather than parking it; the losing branch was
edited out of phase 3 and the choice is recorded in the Reconciliation Log.

The two genuine unknowns in this set — the replay depth K, and whether the weight vector helps at
all — are not open questions. They are **measurements**, each owned by a phase (1 and 4) that is
built to answer them for free and to STOP if the answer is no. A STOP in either is a recorded
result, not a question handed back.

---

## Rollback

| Phase | How to back it out |
|---|---|
| 1, 4 | Nothing to back out. Both write only to the scratchpad and to `.workflows/plan/`. Neither opens the lab database for writing; I5 asserts the hash is unmoved. |
| 2 | `git revert` the commit. v1's bodies were never touched (I3), so nothing recorded moves either way. |
| 3, 5 | **A recorded trial cannot be rolled back** — `trials` is append-only by trigger, and that is the point. What *can* be backed out is the method-file commit, and only **before** `lab run --amend`. After the run, the arm is part of the record: the repair is a further amendment, never a revert. This is why I7 puts the commit before the run and why both phases probe for free first. |
| 6 | `methods.verdict` and `methods.analysis` are not append-only and can be rewritten by a further `lab note`. **`insights` is append-only**: a journalled row that turns out wrong can only be superseded by a later one, never removed. Journal last, one command at a time, exit code read directly. |
| whole set | `main` carries it. Reverting the engine commits is clean; the lab rows the set recorded stay, as every lab row does. |

---

## Next

Run the phases one at a time, by hand, starting at phase 1:

    /implement -f docs/plans/CONTROL_DRAW_REMEDIES_PLAN.md --phase 1

Do **not** run these as a swarm. The dependency graph has two independent chains, and running them
concurrently would put two `dev.run_registry` sweeps on one 15 GB laptop that a parallel wave has
already taken down twice in the last twenty-four hours.

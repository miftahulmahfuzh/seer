# Phase 4: Handover, bookkeeping and the standing correction

**Plan set:** `GATE_READING_CADENCE_PLAN.md`
**Analysis:** `docs/analyzer/20261019-152028-SSYJ_code_analyzer.md`
**Satisfies:** R4 (say which rungs can be promoted and which never can, rather than minting a preset mid-run) — R5 (every number a human reads is money-weighted, `trial_funding.mwr`) — R7 (no test-window look: this phase's hard stop and exit criterion 6 are where the count is proved still 4, and none of its own commands reads the test store)
**Depends on:** Phase 3 — and transitively 1 and 2
**Difficulty:** NORMAL
**Package:** `docs/plans`, `.workflows` (root), plus `~/.claude/projects/-home-miftah-seer/memory/` (outside the repo)

---

## Goal

After this phase the M0260 run is readable by a person who was not here: one handover in the house
style carrying the ladder in money-weighted terms, the decomposition arithmetic, and an explicit
paragraph on which rungs could ever become a book the owner runs; the lab's durable lessons are in
memory where the next session will actually meet them; the root todo list is closed out; and
`feature/gate-reading-cadence` is merged to `main` and pushed, with the worktree and branch gone.

This phase writes prose and bookkeeping only. It re-derives nothing. Every number in it is quoted
from phase 3's captures.

## Interface Contract

**Deletes:** nothing. No symbol, no config key, no file.

**Renames:** nothing.

**Creates:**
- `docs/plans/HANDOVER_20261019-the-gate-reading-cadence.md` (new, on the branch)
- `~/.claude/projects/-home-miftah-seer/memory/seer-gate-cadence-separable-only-on-the-slow-side.md` (new, outside the repo)
- one new task entry in `.workflows/todos.md` (root), `P1-ROOT-C4DN`
- conditionally, one `P3-ROOT-<4CharID>` task if the run opens a leftover (see Step 5c)

**Modifies:**
- `.workflows/todos.md` (root) — one new entry, closed in the same phase; Quick Stats recounted
- `docs/plans/GATE_READING_CADENCE_PLAN.md` — `**Status:** planned` -> `**Status:** complete`, and
  the Phases table's `TaskID` column filled for row 4 only. The file is **tracked on the branch**
  (the coordinator committed it before phase 1), so it is edited in the worktree and committed in
  Step 8b.
- `~/.claude/projects/-home-miftah-seer/memory/seer-gate-cadence-is-worth-more-than-any-band.md`
  (superseded in place — it is this run's own parent claim)
- `~/.claude/projects/-home-miftah-seer/memory/seer-walkforward-picks-folds-by-mar.md`
  (one appended data point)
- `~/.claude/projects/-home-miftah-seer/memory/MEMORY.md` (one new pointer line; one existing
  pointer line's hook rewritten)

**Signature changes:** none. No Python is touched by this phase.

**Requires (from earlier phases):**
- Phase 3 has recorded **six** M0260 trials, a verdict, a plain-language analysis and at least one
  insight, has run `lab stage`, and has committed `lab/lab.sqlite` + `web/data/lab.json` **in the
  main checkout on `main`, with no pathspec**.
- Phase 3 has left its command output as capture files **in `/tmp/m0260`** (or copied to
  `/home/miftah/.cache/seer-captures-m0260`). Step 1 names every file this phase reads and the
  read-only fallback for when they are gone.
- Phase 2's method file and test module are committed on `feature/gate-reading-cadence` — that
  commit is the pre-registration, phase 2 made it, and nothing here touches it.
- **The coordinator committed `docs/plans/GATE_READING_CADENCE_PLAN.md`,
  `docs/analyzer/20261019-152028-SSYJ_code_analyzer.md` and all four phase plan files on
  `feature/gate-reading-cadence` before phase 1 started.** So the plan index is a **tracked file in
  this worktree**: Step 6 edits it here and this phase's close-out commit carries it. No phase
  creates it, and no phase commits it from the main checkout.
- Phase 1's study script and its committed output are on the same branch.

**Leaves alone (owned by others):**
- `lab/lab.sqlite` and `web/data/lab.json` — Phase 3. This phase does not write them, does not
  re-stage them, and does not merge them from the branch.
- `engine/src/seer_engine/lab/methods/m0260_gate_reading_cadence.py` — Phase 2, and frozen by its
  pre-registration commit. Not a typo, not a docstring.
- `engine/tests/test_lab_m0260_cadence.py` — Phase 2.
- `docs/backtests/2026-10-19-gate-reading-cadence.{py,md}` — Phase 1.
- `engine/.workflows/todos.md` — if phase 2 or 3 opened an engine-package task there, that is
  theirs to close. This phase touches only the root list.

## Files

| File | Action | What changes |
|---|---|---|
| `docs/plans/HANDOVER_20261019-the-gate-reading-cadence.md` | create | the whole handover, Step 2 |
| `.workflows/todos.md` | modify | `:4` Last Updated, `:5` Total Active, `:9-15` Quick Stats, one entry under `### [P1] High` (`:28`), then moved into `## Completed Tasks` (`:46`) |
| `docs/plans/GATE_READING_CADENCE_PLAN.md` | modify | the `**Status:**` line (`planned` -> `complete`) and the phase-4 row's `TaskID` cell. **Line numbers are not quoted** — the reconciler rewrote this file, so match on content |
| `~/.claude/.../memory/seer-gate-cadence-separable-only-on-the-slow-side.md` | create | Step 4a, whole file |
| `~/.claude/.../memory/seer-gate-cadence-is-worth-more-than-any-band.md` | modify | Step 4b, whole file rewritten |
| `~/.claude/.../memory/seer-walkforward-picks-folds-by-mar.md` | modify | Step 4c, one paragraph appended before `**Why:**` |
| `~/.claude/.../memory/MEMORY.md` | modify | one line rewritten, one line appended at the end |

---

## Implementation Steps

### Step 1: Collect phase 3's numbers — and never re-derive one

**File:** none (read-only)

**Change:** Every result-dependent cell in this phase comes out of phase 3's captures, **which
live in `/tmp/m0260` under the names phase 3 writes them with.** That is phase 3's directory and
phase 3's naming; this phase reads it and renames nothing.

    CAP=/tmp/m0260          # phase 3's capture directory
    ls -la "$CAP"

| capture file | what this phase reads out of it |
|---|---|
| `$CAP/04-show.txt` | `lab show M0260`: the six-arm ladder as the lab prints it, the method verdict, the screen verdicts, the recorded analysis |
| `$CAP/06-ladder.tsv` | **the table this phase quotes**: `n`, `candidate_id`, `mwr_pct`, `spy_pct`, `fall_pct`, `trades`, `turnover`, `exposure`, `pf`, `dsr`, `n_at_run`, `failed`, at full precision. The deposit-matched SPY TR figure is its `spy_pct` column — confirm it against M0258's handover's **7.19%/yr**, do not assume |
| `$CAP/06-decomp.txt` | the two reproduction verdicts (`REPRODUCES` / `*** DRIFT ***`) against `M0258-M-B0` and `M0258-W-B0` field by field, and the A−C / C−B / A−B decomposition on both axes with its sum residual |
| `$CAP/07-walkforward.txt` | the walk-forward headline: folds won, stable, 2009-15 edge, verdict, and whether `*** BUY SIGNAL ***` printed |
| `$CAP/08-folds.txt` | **fold by fold: which arm each fold picked and whether it won** (R2), plus the `picks by arm` line and the whole-arm 2009-2015 MAR table |
| `$CAP/09-control.txt` | the D17 verdict (`dose-response` rows, ratio or none, refuse or none) and its closing sentence |
| `$CAP/10-costs-M-NATIVE.txt`, `$CAP/10-costs-M-G12.txt` (and `10-costs-M-G3.txt` if phase 3 ran a third) | the real-Gotrade-versus-flat-0.1% fee split at each end of the ladder |
| `$CAP/16-final.txt` | `lab status` plus the four counts and `lab next-id`: dev trials after, test-window looks after, methods, insights, next free id |
| `$CAP/05-verify.txt` | `methods.source_sha`, every `trials.git_sha`, the six config digests, the test-look count, `methods.M0260` status/family/parent |
| `$CAP/02-probe.txt`, `$CAP/02-probe-w.txt` | the pre-run reproduction probe and its `row.start` (**must read `1996-01-03`**) — cite these if the handover has to explain the widened lookback |
| `$CAP/11-note.txt`, `$CAP/12-insight-*.txt`, `$CAP/13-idea.txt` | what was recorded: the verdict and analysis, each journalled insight, and any queued follow-up idea |
| `$CAP/01-prereg.txt`, `$CAP/15-commit.txt` | the pre-registration commit (phase 2's) and phase 3's result commit in the main checkout |

**`/tmp` does not survive a reboot.** Phase 3 is told to copy the whole directory to
`/home/miftah/.cache/seer-captures-m0260` before it closes out. If `/tmp/m0260` is empty, try that
path first:

    CAP=/home/miftah/.cache/seer-captures-m0260
    ls -la "$CAP"

**Fallback, if both are gone.** Re-read the lab read-only, and restore the file afterwards — a
`lab` connect migrates `lab.sqlite` even on a pure read, and phase 3 already committed it:

    PY=/home/miftah/seer/engine/.venv/bin/python
    export SEER_LAB_DB=/home/miftah/seer/lab/lab.sqlite
    export SEER_RESEARCH_STORE=/home/miftah/seer/engine/.research
    CAP=/tmp/m0260; mkdir -p "$CAP"
    BEFORE=$(git -C /home/miftah/seer hash-object lab/lab.sqlite)
    $PY -m seer_engine lab show M0260        > "$CAP/04-show.txt" 2>&1; echo "exit=$?"
    $PY -m seer_engine lab walkforward M0260 > "$CAP/07-walkforward.txt" 2>&1; echo "exit=$?"
    $PY -m seer_engine lab control M0260     > "$CAP/09-control.txt" 2>&1; echo "exit=$?"
    $PY -m seer_engine lab status            > "$CAP/16-final.txt" 2>&1; echo "exit=$?"
    git -C /home/miftah/seer checkout -- lab/lab.sqlite
    test "$(git -C /home/miftah/seer hash-object lab/lab.sqlite)" = "$BEFORE" && echo "lab.sqlite restored"

    # 06-ladder.tsv is a pure read and needs no restore — ?mode=ro never migrates:
    sqlite3 -header -column "file:/home/miftah/seer/lab/lab.sqlite?mode=ro" \
    "select t.n, t.candidate_id, round(f.mwr*100,4) as mwr_pct, round(f.spy_tr_mwr*100,4) as spy_pct,
            round(t.max_drawdown*100,4) as fall_pct, t.trades, round(t.turnover,4) as turnover,
            round(t.exposure,4) as exposure, round(t.profit_factor,4) as pf, round(t.dsr,4) as dsr
       from trials t left join trial_funding f on f.trial_n = t.n
      where t.method_id = 'M0260' order by t.n;" > "$CAP/06-ladder.tsv" 2>&1; echo "exit=$?"

**`08-folds.txt` cannot be re-derived by a `lab` command** — `lab walkforward` prints only the
per-method headline and never names the arm each fold picked. If it is missing, re-run phase 3's
`/tmp/m0260/folds.py`, which is quoted in full in phase 3's step 8. Do not substitute the headline
for the fold table: R2 asks for the arms.

**Impact:** No number in the handover is this phase's own arithmetic except the two decomposition
subtractions in Step 2, which are shown with their operands so a reader can check them — and
`06-decomp.txt` already computed them, so the handover's job is to copy and show the working, not
to re-derive.

**Hard stop.** If the ladder shows fewer than **six** M0260 trials, or `16-final.txt` shows
`test looks` greater than 4, stop and report. Do not write a handover over an incomplete or a
rule-breaking run.

---

### Step 2: Write the handover

**File:** `/home/miftah/.worktrees/seer/gate-reading-cadence/docs/plans/HANDOVER_20261019-the-gate-reading-cadence.md` (new)

**Change:** Write the file below verbatim, replacing every `«…»` placeholder from the capture named
beside it. The structure matches `HANDOVER_20261019-the-gate-price-band.md` section for section: a
title line that states the **finding**, never the topic; the four-line written/branch/method/next-id
block; the lab-state table; "What this session established"; the paired-difference tables; "What is
now dead, and must not be bought with another method id"; "Leftovers, in priority order";
"Environment notes that save an hour".

Two rules that bind the prose, not just the numbers:

- **R5.** Every return is `trial_funding.mwr` — what `lab show` prints as *your money earned* — and
  the handover says in its own words, as M0258's does, that the curve-shape columns are not quoted
  because these books are funded and `total_return`/`cagr` count the owner's deposits as gains.
- **R4.** The promotability paragraph is written whatever the result is. If the winning rung has no
  promotion path, **say so plainly and queue a `feature-wish` insight** — do not propose minting a
  preset.

**Code:**

````markdown
# Handover — «the finding in one clause: where the gate's reading cadence turns, stated as a claim, not a topic» (`04-show.txt`)

**Written:** 2026-10-19 · **Branch:** `feature/gate-reading-cadence` (merged to `main`)
**Method spent:** M0260 · **Next free id:** «M0261 or M0262 — `16-final.txt`»

**The lab after this run**

| | |
|---|---|
| dev trials | **«836»** (830 + 6) — `16-final.txt` |
| test-window looks used | **4 — unchanged. None was spent.** — `16-final.txt` |
| methods | «274 + any idea this run queued» — `16-final.txt` |
| insights | **«466»** («465» + «1») — `16-final.txt` |
| N the luck gate judges at (policy: methods) | **«164»** (163 + 1) — `16-final.txt` |
| next free id | **«M0261»** — `16-final.txt` (`lab next-id`) |

---

## What this session established

M0260 swept how often the SPY 200-day gate is read, on a book that actually holds stocks —
`M0072-Z2-RAWRANK`, carried verbatim — from weekly to yearly. **Six arms**, one book, nothing
moving but the rule set's cadence and the gate's checking interval. Every figure below is the
**money-weighted** return on the owner's own monthly deposits (`trial_funding.mwr`, what `lab show`
prints as "your money earned"), against **«7.19»%/yr** for the same deposits put into SPY TR
(`06-ladder.tsv`'s `spy_pct` column). The curve-shape columns are not quoted anywhere: these books
are funded and `total_return` and `cagr` count the deposits as gains.

**Six arms, not seven, and the monthly ladder has four rungs.** `lab/method.py:40` caps a method at
`MAX_VARIANTS = 6`. The two-month rung was measured as a prior on SPY alone
(`docs/backtests/2026-10-19-gate-reading-cadence.md`) and deferred to an `Amendment` under this
same id, which costs no method id. Say that here, so a reader does not read a four-rung ladder as a
five-rung one with a hole in it.

### The ladder

| arm | re-pick | gate read | money | worst fall | trades | turnover | PF | DSR | screen |
|---|---|---|---|---|---|---|---|---|---|
| `M0260-W-NATIVE` | weekly | weekly | «%» | «%» | «n» | «x» | «x» | «x» | «verdict» |
| `M0260-W-G1` | weekly | **monthly** | «%» | «%» | «n» | «x» | «x» | «x» | «verdict» |
| `M0260-M-NATIVE` | monthly | monthly | «%» | «%» | «n» | «x» | «x» | «x» | «verdict» |
| `M0260-M-G3` | monthly | quarterly | «%» | «%» | «n» | «x» | «x» | «x» | «verdict» |
| `M0260-M-G6` | monthly | half-yearly | «%» | «%» | «n» | «x» | «x» | «x» | «verdict» |
| `M0260-M-G12` | monthly | yearly | «%» | «%» | «n» | «x» | «x» | «x» | «verdict» |

*(every cell from `06-ladder.tsv` at full precision, cross-read against `04-show.txt`; trials
«n»-«n». Six rows, not seven — the two-month rung was not run.)*

**«Where it turns.»** «One paragraph: the monthly ladder read as a dose-response curve —
monotone, humped, or flat — and the rung that maximises money and the rung that minimises the fall,
named separately when they differ. If no rung beats `M-NATIVE` on either axis, say that in those
words: the cadence the lab already runs is the best speed, and the ladder bought the knowledge that
there is nothing above it.»

### The reproduction

`M0260-M-NATIVE` «reproduced / did not reproduce» `M0258-M-B0` = `M0072-Z2-RAWRANK`: «12.3314%,
23.8026%, 1208 trades, turnover 6.529 against the recorded «…»» — `06-decomp.txt`, which prints
`REPRODUCES` or `*** DRIFT ***` field by field. `M0260-W-NATIVE` «reproduced / did not reproduce»
`M0258-W-B0`: «5.32%, 35.49% against «…»».

**Say in one sentence that the lookback was widened and the reproduction survived it.** M0260 runs
at `lookback = 454`, not M0072's 253, because a twelve-month anchor sits up to 253 sessions behind
the data date and still needs its 200-bar average. It does not move the window: `candidate_window`
checks only the candidate's fixed symbols and floors index members at `MEMBERSHIP_START`
(1996-01-02), so any `lookback <= 739` leaves the first scored session at **1996-01-03** — the same
session M0072 and M0258 recorded. The probe captures (`02-probe.txt`, `02-probe-w.txt`) show it
before the run; the trials' `start` shows it after. The standing rule worth carrying forward is
**"never cross 739"**, not "never widen".
«If either drifted, state the drift and say which paired differences it does and does not
invalidate — a drift in a reproduction arm is a finding about the lab, not an embarrassment to
hide. See the standing note that a re-run of a recorded row is not bit-reproducible in general;
M0258 found it did not apply to an overlay that passes the host's own params to the host's own
target builder.»

### The decomposition: M0258's +7.01 points, split

With A = `M0260-M-NATIVE` (monthly re-pick, monthly gate), C = `M0260-W-G1` (weekly re-pick,
monthly gate) and B = `M0260-W-NATIVE` (weekly re-pick, weekly gate):

| term | what moves | money | worst fall |
|---|---|---|---|
| **A − C** | re-pick frequency, gate held monthly | «+x.xx pts/yr» | «x.xx shallower» |
| **C − B** | gate reading cadence, re-pick held weekly | «+x.xx pts/yr» | «x.xx shallower» |
| **A − B** = the sum | both, as M0258 measured it | «+x.xx pts/yr» | «x.xx shallower» |

The arithmetic, in full, so it can be checked: money `«A» − «C» = «A−C»` and `«C» − «B» = «C−B»`,
which sum to `«A−B»`; worst fall `«B» − «A» = «A−B fall»` splits as `«C» − «A»` and `«B» − «C»`.
M0258 measured A − B at **+7.01 pts/yr and 11.69 points of worst fall** on the same book; this run
re-measures it at «…» and attributes «…» of it to how often the book re-picks and «…» of it to how
often the gate is read.

**Why C − B is clean.** At a weekly rank session in month *M*, arm C's anchor is the newest month
end on or before its `data_date` — the same month-end session arm A read at its own rank session
that month. Arm C literally reuses arm A's gate reading, so A − C moves re-pick frequency and
nothing else. Phase 2 asserts that session by session in `test_lab_m0260_cadence.py`.

**What the decomposition does not reach.** The cadence axis is separable **only on the slow side**.
A monthly book cannot act on a gate reading taken between its rank sessions — a reading it never
acts on changes no target and no trade — so making the book read the gate faster than it re-picks
*is* a rule-set change, which re-picks faster too. The sub-monthly rung is inseparably confounded
on this chassis. That is a property of the simulator, not a gap in the design, and it is why the
ladder is built upward from monthly rather than downward from weekly.

### What can be promoted, and what never can

«Written whatever the result is. The facts, which do not depend on the result:»

- Every **monthly** arm — `M-NATIVE`, `M-G3`, `M-G6`, `M-G12` — runs on
  `monthly-hold-frac-gotrade`, which **is** in `sim.rules.PRESETS` (`sim/rules.py:261`, registered
  at `:308`). All four are promotable.
- Both **weekly** arms — `W-NATIVE` and `W-G1` — run on `weekly-hold-frac-gotrade`, which is
  defined in `m0063_earnings_day_jump.py:64` and is **not** in `PRESETS`. `lab promote` requires
  membership, so **no weekly result of this run can ever become a book the owner runs**, whatever
  it shows. They are diagnostic forever, by design, and the method file says so in its own words.
- There is no quarterly or yearly **rule set** either, and there cannot be one without a schema
  move: `sim.rules.Cadence` is `Literal["daily", "weekly", "monthly"]`. Adding a member would move
  `_CADENCE_ORDER`, `_first_of`, `is_rank_session`, every `TradeRules` canonical text and the web
  mirror. **This is precisely why the slow rungs were built as allocator params and not as rule
  sets** — the params route leaves `TradeRules` untouched, so a quarterly or yearly *gate* stays
  promotable even though a quarterly or yearly *cadence* does not exist.

«Then the result-dependent sentence, one of:»

- *If the winning rung is a monthly arm:* «`M0260-M-G«k»` is promotable today; nothing has to be
  built for it.»
- *If the winning rung is a weekly arm:* **say so plainly and do not propose minting a preset.**
  «The arm that won cannot be promoted. A `feature-wish` insight has been journalled asking for a
  weekly fractional Gotrade preset; until the owner decides on it, this result is information and
  not a candidate.» (This is the previous handover's leftover item 6, now live.)

### The walk-forward folds, arm by arm

`lab walkforward M0260` «printed / did not print» `*** BUY SIGNAL ***` — `07-walkforward.txt`. The
fold-by-fold table below comes from `08-folds.txt`, which is the only place the arm each fold
picked is printed at all. Read it arm by
arm before acting on it, because the folds select each fold's variant **by MAR**, which
structurally favours whichever arm trades least, and this ladder's slowest rungs trade least by
construction:

| fold | arm selected | won? |
|---|---|---|
| 1 | «arm» | «yes/no» |
| 2 | «arm» | «yes/no» |
| 3 | «arm» | «yes/no» |
| 4 | «arm» | «yes/no» |

**Won or lost, never a percentage.** `08-folds.txt`'s `its return` and `bench` columns are
`total_return` over a fold slice and its whole-arm block prints `cagr` and `MAR` — curve-shape
figures, not the owner's money (index invariant 4). This table carries the arm and the verdict and
nothing else; every percentage anywhere in this handover is `trial_funding.mwr`.

«One sentence: did the folds drift toward the least-trading arm, as the pre-registration warned?
M0245 said yes; M0258 said no (two of four chose no band at all). This is the third data point and
it is recorded either way — `08-folds.txt`'s `picks by arm` line.» 2009-2015 edge: «+x.x pts»
(`07-walkforward.txt`). Kin: «clean / «0.xx» against «arm»» (`07-walkforward.txt`).

### D17 and the control shape

`lab control M0260` reports «six» `dose-response` rows, verdict «…», «ratio / no ratio», «refuse /
no refuse» — `09-control.txt`. The ladder with `M-NATIVE` as its zero rung is its own control; no
drawn arm exists by design, which is the shape D17 was built to require. All six arms carry the
literal phrase `dose-response` in their rationale, which is how `control_shape.kind_of` classifies
them (`lab/control_shape.py:191-200`) — a classification that reads an arm's prose, so it was
checked before the pre-registration commit froze the file, not after.

---

## What is now dead, and must not be bought with another method id

«Carried forward verbatim from HANDOVER_20261019-the-gate-price-band.md, then extended.»

- **The price band.** Measured three times — on SPY alone read monthly (−0.40 pts/yr), on M0101's
  calm-raisers stock book (−0.18 at 3%, −0.52 at 5%), and on M0072's earnings-jump book across a
  four-rung ladder (−0.57 at 3%, −3.21 at 6%). It is only ever worth something when the gate is
  read faster than monthly, and no promotable rule set reads it faster than monthly. Do not spend
  another id widening, narrowing or asymmetrising it.
- **Turning the gate off.** Helped 22 of 22 variants whole-window, 0 of 22 after 2009, and every
  gate-off arm was worse on return *and* drawdown at once.
- **A time lock on the switch.** Costs return and deepens the worst fall from 20% to 32%: the
  flips it suppressed included the 2008 exit. The standing rule is "stop hunting hysteresis here".
- **An account-reading drawdown brake.** Pays about 10 points a year of 2009-2015 to save 40 of
  2008. A volatility dial beats a drawdown dial on every axis.
- **A learned fall-sizing brake** (M0132). Beaten by the plain gate on both axes.
- **VIX-level confirmation of the exit.** Worse on both axes at 20, 25 and 30, and VIX3M only
  begins 2006-07-17, so it cannot be checked against the dot-com fall at all.
- **Exit-buffer-only, confirm-N-days, partial exposure, fast re-entry on the 50-day.** All in the
  committed variant grid, all worse than the symmetric band.
- **«NEW — whatever this run buries.»** «e.g. "Slowing the gate past «k» months. The ladder is
  «monotone falling / flat» above «k»: «M-G6» and «M-G12» give «…», so a gate read half-yearly or
  yearly is not a gate. Do not spend an id on a slower reading." Or, if nothing was buried: say
  so, and say what replaced it as the open question.»

## Leftovers, in priority order

«Carried forward and re-prioritised. Drop any this run closed; add any it opened.»

1. **The nine D17-blocked dev-eligible methods** — M0047, M0201, M0202, M0208, M0215, M0221,
   M0225, M0227, M0243 — each carrying a control arm whose trade count or turnover does not match
   the arm it controls. The remedy costs **no method id**: re-draw each control at the book's own
   shape and record it as an amendment under the existing id. This is still the cheapest
   information left in the lab and it re-tests nine standing verdicts.
2. **«The new top item, if this run opened one»** — «e.g. "Apply the winning cadence to the rest of
   the roster. Every other book still reads its gate at whatever cadence it happens to re-pick,
   and this run says that is worth «…» points a year. The remedy costs no method id where a book's
   hold is counted in sessions: it is an amendment arm on each existing method. Check first that
   the book's chooser does not key on `data_date.month` — M0197's does, which is why it could not
   host this axis."»
3. **The buyback holdability problem.** The cheap-buyback book led by 11.4 points a year in
   2009-2015 on honest prices and won all four out-of-sample stretches, but falls 55-85%, so it
   cannot be held. A containment problem, not a gate problem.
4. **Insight 457's practical conclusion still stands on the site** ("weight by company size"),
   withdrawn by 462 but, `insights` being append-only, still visible to the owner. Another
   correction row — same shape as the one M0258's run queued, different subject.
5. **P2-ENG-N3LB** — `name_count.py`'s docstring still calls the dev trial count "the lab's N",
   which the 2026-10-08 policy move made wrong.
6. **P3-ENG-V2KQ** — append a dated §7.3 revision to the lab design doc recording the N policy
   move to methods.
7. **`sim.rules.PRESETS` has no weekly fractional Gotrade preset**, so this method's two weekly
   arms can never be promoted whatever they showed. «If a weekly arm won, promote this item to the
   top and note that the `feature-wish` insight is now journalled; if no weekly arm won, leave it
   here and note that the question is now academic for this book.»

## Environment notes that save an hour

- **The worktree has no venv and no research store.** Use the main checkout's:
  `PY=/home/miftah/seer/engine/.venv/bin/python`,
  `SEER_RESEARCH_STORE=/home/miftah/seer/engine/.research`. Never rebuild a store — it is 30
  minutes for nothing.
- **`PYTHONPATH=<worktree>/engine/src` or pytest silently tests the main checkout**, not the
  branch.
- **`SEER_LAB_DB=/home/miftah/seer/lab/lab.sqlite`.** A worktree copy must never be written, and
  **even a pure read migrates the file on connect** — so a read-only `lab show` after the run
  dirties the committed database. Hash it before, restore it by path after.
- **`lab stage` targets the MAIN checkout** — it regenerates and `git add`s `/home/miftah/seer`'s
  `lab/lab.sqlite` and `web/data/lab.json`. Commit them with `git -C /home/miftah/seer commit` and
  **no pathspec**: a pathspec re-reads the working tree and defeats the staging.
- **Never `pull --rebase` over a lab commit.** A rebase replays a stale `lab.sqlite` and overwrites
  the live shared database other sessions are writing. If a push is rejected, re-run `lab stage`,
  re-commit with no pathspec, and check trial `n` is contiguous.
- **Never judge a `lab` command by a piped exit code.** Redirect to a file and echo `$?`; a
  `grep`/`head` owns the pipeline's status, and this shell prints a spurious
  `setValueForKeyFakeAssocArray:27: command not found: _encode` line at startup that appears at
  the head of every captured file.
- **One core.** Run pytest with `-n0`; never override `addopts`.
- **The DB tests need Postgres**: `docker start seer-pg`, and
  `PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres`. CI fails if they skip.
- **This set's cadence study takes an ABSOLUTE `--store`, unlike M0258's**, so it runs from the
  worktree and does not have to be run from the main checkout:
  `PYTHONPATH=<worktree>/engine/src /home/miftah/seer/engine/.venv/bin/python
  docs/backtests/2026-10-19-gate-reading-cadence.py --store /home/miftah/seer/engine/.research`.
  That is a deliberate correction of the M0258 precedent (whose
  `docs/backtests/2026-10-19-gate-band-cadence.py` hard-codes a relative `engine/.research`); the
  older file is a committed record of a finished study and **must not be edited** to match.
- **A lab allocator on an index-member book may widen its lookback up to 739 bars without moving
  the dev window's first scored session.** `dev.candidate_window` checks only the candidate's
  fixed symbols and floors index members at `MEMBERSHIP_START` (1996-01-02); SPY's 739th bar on
  the dev store is 1996-01-02 and its 740th is 1996-01-03. The real operative ceiling is the
  473-session smoke fixture. M0260 runs at 454. The rule is **"never cross 739"**, not "never
  widen" — M0258's file says the latter because its own proposed widening reached 757.
- **Phase 3's captures live in `/tmp/m0260`**, and `/tmp` does not survive a reboot; phase 3 copies
  them to `/home/miftah/.cache/seer-captures-m0260` before closing out. `08-folds.txt` is the only
  place the arm each walk-forward fold picked is printed — `lab walkforward` prints the headline
  only.
- **«Anything this plan set learned that is not already above.»** «e.g. a `lab run` of six arms
  on this store took «…» minutes against the ~40 s projection; the anchor probe's runtime; a
  capture path convention.»
````

**Impact:** The handover is the only artifact a future session is guaranteed to read. Nothing in it
may contradict `lab show M0260`; every table cell traces to a capture file.

---

### Step 3: Sanity-check the handover against R4 and R5 before committing it

**File:** the file just written

**Change:** Four mechanical checks:

    H=/home/miftah/.worktrees/seer/gate-reading-cadence/docs/plans/HANDOVER_20261019-the-gate-reading-cadence.md
    # R5: no curve-shape column may be quoted as a return
    grep -nEi 'total[_ ]return|\bcagr\b' "$H"          # expect: only the sentence that says they are NOT quoted
    # R4: the promotability paragraph exists and names PRESETS and Cadence
    grep -n 'PRESETS' "$H" && grep -n 'Literal\["daily", "weekly", "monthly"\]' "$H"
    # no placeholder survived
    grep -n '«' "$H"                                    # expect: no output
    # the title states a finding, not a topic
    head -1 "$H"

**Impact:** `grep -n '«'` returning nothing is the gate on this phase's prose. If it prints a line,
the handover is not finished.

---

### Step 4: Memory

Memory files live at `/home/miftah/.claude/projects/-home-miftah-seer/memory/` and are **outside
the repository** — they are not committed, not merged and not pushed. Write them before the merge
anyway, so an interrupted session still leaves the lesson behind.

#### Step 4a: the structural memory (new — write this one whatever the result)

**File:** `/home/miftah/.claude/projects/-home-miftah-seer/memory/seer-gate-cadence-separable-only-on-the-slow-side.md`

**Change:** create, with exactly this content (the two `«…»` cells come from `06-decomp.txt`):

````markdown
---
name: seer-gate-cadence-separable-only-on-the-slow-side
description: A book's gate-reading cadence and its re-pick frequency are the same event on this chassis — separable only by slowing the gate inside the allocator, which is also the only shape that stays promotable.
metadata:
  type: project
---

`book_runner.run_book` calls the allocator **only on decision sessions**, with
`data_date = prev_session(session)`, and the gate is read inside that call. So "how often the gate
is read" is *defined* by `TradeRules.cadence`, which is also what sets how often the book re-picks.
Any measurement that moves the rule set's cadence moves both axes and names neither — which is
exactly what M0258's +7.01 pts/yr was.

**The asymmetry is the whole design space.**

- **Slower than the re-pick: separable, and promotable.** Nothing stops the allocator evaluating
  the gate at a date *earlier* than `data_date`. Anchor it to a month-end grid
  (`anchor(h, data_date, k)` = newest month-end bar `a <= data_date` with
  `month_index(a) % k == k - 1`, falling back to `data_date`) and `TradeRules` is untouched, so the
  book still runs on `monthly-hold-frac-gotrade` — which **is** in `sim.rules.PRESETS`.
- **Faster than the re-pick: not separable, by construction.** A monthly book cannot act on a
  reading taken between its rank sessions; a reading it never acts on changes no target and no
  trade. Making it act weekly *is* a rule-set change, which re-picks weekly too.

**Two facts that make the slow side the only buildable side.** `sim.rules.Cadence` is
`Literal["daily", "weekly", "monthly"]` — there is **no quarterly and no yearly rule set**, and
adding one would move `_CADENCE_ORDER`, `_first_of`, `is_rank_session`, every `TradeRules`
canonical text and the web mirror. And `WEEKLY_HOLD_FRAC_GOTRADE` (`m0063_earnings_day_jump.py:64`)
is **not** in `PRESETS`, so every weekly arm in the lab is diagnostic forever whatever it shows.
Put the slow rungs in the allocator's params and they need neither: a quarterly *gate* is
promotable even though a quarterly *cadence* does not exist.

**On a monthly book, the anchored `k = 1` rung is the native rung** — a monthly book's `data_date`
is always a calendar month end (`_first_of` makes the rank session the first NYSE session of the
month, so `prev_session` of it is the last session of the month before). Assert that identity in a
test; do not spend a trial on it. And `k >= 2` is strictly *safer* on look-ahead than the native
reading, because the anchor is never later than `data_date`.

**The exact decomposition, when you need to split a cadence result.** A = monthly re-pick/monthly
gate, C = weekly re-pick/**monthly anchored** gate, B = weekly re-pick/weekly gate:
`(A − B) = (A − C) + (C − B)`, re-pick frequency plus gate cadence. `A − C` is clean because at a
weekly rank session in month *M*, arm C's anchor is the **same month-end session** arm A read that
month — C literally reuses A's reading. Measured by M0260, 2026-10-19:
**«A − C = +x.xx pts/yr» of re-pick frequency and «C − B = +x.xx pts/yr» of gate cadence**
(`06-decomp.txt`).

**How to apply:** before claiming any gate finding, check whether the book's hold is counted in
**sessions** or in calendar months — a chooser that keys on `data_date.month` (M0197's does) cannot
host this axis at all, because its re-pick is already welded to the calendar. M0072's is counted in
sessions, which is why it could host it. Related:
[[seer-gate-cadence-is-worth-more-than-any-band]], [[seer-band-worth-is-a-cadence-artifact]],
[[seer-gate-premium-is-a-constant-36-pts]], [[seer-spy-200-day-gate-is-not-a-drag-to-remove]],
[[seer-shared-params-cannot-gain-a-field]].
````

**`MEMORY.md` line** — append exactly one line at the end of
`/home/miftah/.claude/projects/-home-miftah-seer/memory/MEMORY.md`:

    - [Gate cadence is separable only on the slow side](seer-gate-cadence-separable-only-on-the-slow-side.md) — reading and re-picking are one event; anchor the gate inside the allocator and it stays promotable, because `Cadence` has no quarterly member.

#### Step 4b: supersede the parent memory in place (do not duplicate it)

**File:** `/home/miftah/.claude/projects/-home-miftah-seer/memory/seer-gate-cadence-is-worth-more-than-any-band.md`

**Change:** This file currently ends with *"Queued as **M0260**: sweep the checking interval …"*.
That queue is now spent. Rewrite the whole file so the ladder's answer replaces the question —
this is the one file in the set that must not be duplicated, because the next session will meet it
under the same name:

````markdown
---
name: seer-gate-cadence-is-worth-more-than-any-band
description: «one sentence stating where the ladder turns — e.g. "Reading the SPY-200 gate monthly beats weekly by +7.0 pts/yr, and slowing it past monthly gives «…»; the cadence the lab already runs is «the best / not the best» speed."»
metadata:
  type: project
---

Measured 2026-10-19 by M0258, then swept by M0260, on `M0072-Z2-RAWRANK`'s earnings-jump book —
same book on every arm, nothing moving but how often the SPY 200-day gate is read. Money-weighted
on the owner's deposits (`trial_funding.mwr`), against «7.19»%/yr for the same deposits into SPY TR:

| gate read | re-pick | money | worst fall | trades | turnover | PF | DSR |
|---|---|---|---|---|---|---|---|
| weekly (`M0260-W-NATIVE`) | weekly | «%» | «%» | «n» | «x» | «x» | «x» |
| **monthly, weekly re-pick** (`M0260-W-G1`) | weekly | «%» | «%» | «n» | «x» | «x» | «x» |
| **monthly** (`M0260-M-NATIVE`) | monthly | «%» | «%» | «n» | «x» | «x» | «x» |
| quarterly (`M0260-M-G3`) | monthly | «%» | «%» | «n» | «x» | «x» | «x» |
| half-yearly (`M0260-M-G6`) | monthly | «%» | «%» | «n» | «x» | «x» | «x» |
| yearly (`M0260-M-G12`) | monthly | «%» | «%» | «n» | «x» | «x» | «x» |

**«Where it turns, in one bolded sentence — the number nobody can re-derive without six
trials.»** M0258's weekly-to-monthly step was +7.01 pts/yr and 11.69 points of worst fall; M0260
splits that into **«…» from re-pick frequency** and **«…» from the gate's reading cadence**, and
measures what happens above monthly: «…».

**Why:** a gate read weekly keeps reacting to moves that reverse before the month is out. A
monthly reading ignores every flip shorter than a month for free, which is the same suppression a
price band buys — see [[seer-band-worth-is-a-cadence-artifact]]. «And above monthly: state what
the slow rungs cost or earn, and whether gating survives at all at half-yearly and yearly, against
the constant [[seer-gate-premium-is-a-constant-36-pts]].»

**What can be acted on:** every monthly rung runs on `monthly-hold-frac-gotrade`, which is in
`sim.rules.PRESETS`, so «the winning rung» is promotable today. Both weekly arms run on
`weekly-hold-frac-gotrade`, which is not in `PRESETS`, so **no weekly result here can ever become a
book the owner runs**. The structural reason the slow rungs are promotable at all — and the only
way the two axes come apart — is [[seer-gate-cadence-separable-only-on-the-slow-side]].

**How to apply:** **every book in the lab reads its gate at whatever cadence it happens to re-pick
stocks, and nobody ever chose that.** It is an inherited side effect, not a decision, and this
sweep says it is worth «…» points a year on this book. «Next step, if any: apply it to the rest of
the roster as amendment arms — free in method ids — but only on books whose hold is counted in
sessions; M0197's chooser keys on `data_date.month` and cannot host the axis.» Two cautions when
reading the sweep: the walk-forward folds pick by MAR so they favour the slowest-trading rung by
construction ([[seer-walkforward-picks-folds-by-mar]]), and no test-window look was spent — all
six arms are dev-window only. The two-month rung was never run: `MAX_VARIANTS = 6` caps a method at
six arms, so it is a measured prior on SPY alone and a free `Amendment` if the ladder turns out
humped between monthly and quarterly.

Related: [[seer-spy-200-day-gate-is-not-a-drag-to-remove]],
[[seer-switch-time-lock-loses-both-ways]], [[seer-funded-book-cagr-is-a-lie]],
[[seer-gate-band-beats-the-bare-gate]].
````

**`MEMORY.md` line** — this file already has a pointer. **Rewrite that one line in place**; do not
add a second. Replace:

    - [Gate cadence is worth more than any band](seer-gate-cadence-is-worth-more-than-any-band.md) — reading it monthly not weekly is +7.0 pts/yr and 11.7 pts of fall on a stock book; no one ever chose the cadence. Queued as M0260.

with:

    - [Gate cadence is worth more than any band](seer-gate-cadence-is-worth-more-than-any-band.md) — «the ladder's answer in one hook: where it turns, and that no one ever chose the cadence». Swept by M0260.

#### Step 4c: the third walk-forward data point (append, do not rewrite)

**File:** `/home/miftah/.claude/projects/-home-miftah-seer/memory/seer-walkforward-picks-folds-by-mar.md`

**Change:** This is the third observation of the same selection effect (M0245 drifted, M0258 did
not), and the instruction is to record it either way. Insert one paragraph **after** the existing
`Measured on M0230 (2026-10-19)…` paragraph and **before** the `**Why:**` line:

````markdown
Three data points now, and they disagree — which is itself the lesson. **M0245**: the folds drifted
to the braked arm. **M0258** (2026-10-19): they did not — two of four folds chose `M-B0`, the arm
with no band at all. **M0260** (2026-10-19), a cadence ladder whose slowest rungs trade least by
construction and so are the most exposed to this effect: «folds «…» selected «…»; the folds «did /
did not» drift toward the slowest-trading rung». So the MAR rule is a *bias to check*, not a bias
to assume — read which arm each fold scored, every time.
````

**Impact:** No `MEMORY.md` change for 4c — that file's pointer line already exists and still reads
true.

---

### Step 5: Root todos

**File:** `/home/miftah/.worktrees/seer/gate-reading-cadence/.workflows/todos.md`

This phase owns the **root** list only. If phase 2 or 3 opened an entry in
`engine/.workflows/todos.md`, that one is theirs; do not close it from here.

#### Step 5a: open the entry (do this first, before the handover is written)

Insert under `### [P1] High` (currently line 28, after the existing `P1-ROOT-H5NX` block — leave
that entry untouched, it belongs to the `lab-brakes-and-gate` set):

````markdown
- [ ] **P1-ROOT-C4DN** Phase 4: Handover, bookkeeping and the standing correction
  - **Difficulty**: NORMAL
  - **Type**: Documentation
  - **Context**: Owns `docs/plans/HANDOVER_20261019-the-gate-reading-cadence.md` (new), `.workflows/todos.md` (root only), the `**Status:**` tick on `docs/plans/GATE_READING_CADENCE_PLAN.md`, and the memory files under `/home/miftah/.claude/projects/-home-miftah-seer/memory/` with their `MEMORY.md` pointers. Does not touch `lab/lab.sqlite` or `web/data/lab.json` (phase 3 closed them in the main checkout and they are never merged from the branch), the method file or its test module (phase 2, frozen by the pre-registration commit), the study script (phase 1), or `engine/.workflows/todos.md`. Exit: the handover matches the house template section for section, carries the lab-state table with test-window looks still at 4, quotes `trial_funding.mwr` and nothing else as a return, carries the ladder arm by arm and the A−C / C−B decomposition with its arithmetic shown, carries an explicit paragraph on which rungs are promotable and which never can be with `sim.rules.PRESETS` and `sim.rules.Cadence` named, carries the dead list forward and extended and the leftovers list forward and re-prioritised, and contains no surviving `«` placeholder; at least one memory file written with its `MEMORY.md` line; `ruff check engine` clean and `pytest -n0 engine/tests` green from the worktree with `PYTHONPATH` set and Postgres up; `feature/gate-reading-cadence` merged to `main` in the main checkout and pushed, without a rebase over phase 3's lab commits; the worktree and the branch deleted.
  - **Status**: in-progress
  - **Plan Set**: `/home/miftah/.worktrees/seer/gate-reading-cadence/docs/plans/GATE_READING_CADENCE_PLAN.md` (phase 4 of 4)
  - **Satisfies**: R4 — Check `sim.rules.PRESETS` before calling any arm promotable; say so when a winning cadence has no preset rather than minting one mid-run; R5 — Quote `trial_funding.mwr` throughout, never `total_return` or `cagr`; R7 — Spend no test-window look (verified: the lab-state table must read 4 and no command here reads the test store)
  - **Depends on**: phase 3 (`lab run M0260` recorded, staged and committed)
  - **Plan**: `.workflows/plan/gate-reading-cadence/phase-4.md`
````

And update the header block:

| line | from | to |
|---|---|---|
| `:4` | `**Last Updated**: 2026-10-14` | `**Last Updated**: 2026-10-19` |
| `:5` | `**Total Active Tasks**: 1` | `**Total Active Tasks**: 2` |
| `:10` | `- P1 High: 1` | `- P1 High: 2` |

#### Step 5b: close it (last edit of the phase, after the merge verification in Step 7)

Move the whole block into `## Completed Tasks` as the **first** entry (newest first — that is how
the list reads today), change `- [ ]` to `- [x]`, `**Status**: in-progress` to
`**Status**: completed`, and append the house closing fields:

````markdown
  - **Completed**: 2026-10-19 «HH:MM»
  - **Method**: /implement
  - **Files**: `docs/plans/HANDOVER_20261019-the-gate-reading-cadence.md`, `docs/plans/GATE_READING_CADENCE_PLAN.md`, `.workflows/todos.md`, and (outside the repo) `memory/seer-gate-cadence-separable-only-on-the-slow-side.md`, `memory/seer-gate-cadence-is-worth-more-than-any-band.md`, `memory/seer-walkforward-picks-folds-by-mar.md`, `memory/MEMORY.md`
  - **Result**: «one paragraph: M0260's six trials «n»-«n», dev trials 830 -> «836», N 163 -> «164», test-window looks unchanged at 4, and the ladder's answer in one sentence»
  - **Drift**: «anything the phase had to do differently — e.g. phase 3's captures were under a different path; the handover's SPY benchmark differed from M0258's 7.19%; the merge conflicted on the plan index»
  - **Decided**: «each judgement call with its rung — e.g. "the winning rung has no promotion path -> queued a feature-wish insight rather than minting a preset (rung 1: R4 says so in those words)"»
````

Then recount the header: `**Total Active Tasks**: 1`, `- P1 High: 1`, `- Completed: 22`, and the
`**Last Updated**` stays `2026-10-19`.

#### Step 5c: conditional — one new task if the run opened a leftover

Only if the handover's leftovers list gained an item that is *work in this repo* rather than a lab
question. The two likely ones:

- The winning cadence has no promotion path -> the preset is a feature wish, and phase 3 journalled
  it as an insight. Add `P3-ROOT-<4CharID>` under `### [P3] Low` naming
  `sim.rules.PRESETS` and `WEEKLY_HOLD_FRAC_GOTRADE` (`m0063_earnings_day_jump.py:64`), and bump
  `- P3 Low:` and `**Total Active Tasks**`.
- The cadence is worth applying to the rest of the roster -> that is a *lab* leftover, not a repo
  task. It goes in the handover's leftovers list and **not** in `todos.md`.

**Impact:** The root list gains one closed entry and, at most, one open low-priority one. It does
not gain a task for phases 1-3; those phases own their own bookkeeping.

---

### Step 6: Tick the plan index

**File:** `/home/miftah/.worktrees/seer/gate-reading-cadence/docs/plans/GATE_READING_CADENCE_PLAN.md`

**Change:** two content-matched edits — **no line numbers**, because the reconciler rewrote this
file and every line has moved:

- `**Status:** planned` becomes `**Status:** complete`.
- In the Phases table, row 4's `TaskID` cell becomes `P1-ROOT-C4DN` and its `Card` cell stays `—`.

Rows 1-3's TaskID cells belong to those phases. **Leave them exactly as found**, whatever they say
when this phase runs.

**Where the file lives — settled, no branching.** The standing convention is that an orchestration
`PLAN.md` lives on `main` and a phase ticks it in the main checkout. **This set is the exception,
and it was decided before phase 1 ran:** the coordinator committed the index, the analysis document
and all four phase plan files on `feature/gate-reading-cadence` before any phase started. So the
index is a **tracked file in this worktree**. Edit it here, commit it in Step 8b, and let the merge
carry it to `main`. Confirm it in one line before editing:

    git -C /home/miftah/.worktrees/seer/gate-reading-cadence log --oneline -1 -- docs/plans/GATE_READING_CADENCE_PLAN.md

**Expected:** one commit. If that prints nothing, the index is untracked and the coordinator's
pre-phase commit did not happen — commit it from the worktree with this phase's close-out commit
anyway, so the set is not merged without its own index, and say so in the close-out message's
`Drift:` line.

**Impact:** The index is how the next session knows the set is finished. A `draft` left behind
reads as an abandoned swarm.

---

### Step 7: Verify green, from the worktree

**File:** none

**Change:**

    docker start seer-pg
    export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres
    export PYTHONPATH=/home/miftah/.worktrees/seer/gate-reading-cadence/engine/src
    PY=/home/miftah/seer/engine/.venv/bin/python

    cd /home/miftah/.worktrees/seer/gate-reading-cadence
    $PY -m ruff check engine                > /tmp/p4-ruff.txt 2>&1; echo "ruff exit=$?"
    $PY -m pytest -n0 engine/tests           > /tmp/p4-pytest.txt 2>&1; echo "pytest exit=$?"
    tail -5 /tmp/p4-pytest.txt

Both must be clean before the merge. `ruff` is run from the **worktree root** with the path
`engine` — `cd engine && ruff check engine` doubles the path segment and fails with E902 (a drift
recorded by an earlier phase of another set).

If `pytest` is red, read the failures before doing anything else: a failure in
`test_lab_m0260_cadence.py` or `test_lab_methods.py` is phase 2's and this phase stops and reports
rather than patching a frozen method file; a failure in `test_lab_snapshot` means the working tree
and `web/data/lab.json` disagree, which is phase 3's staging and is fixed by re-running `lab stage`
in the main checkout, not by editing anything.

**Impact:** Nothing merges on a red tree.

---

### Step 8: Commit, merge, push

**File:** none

**Change:** Two commits on the branch, then the merge in the main checkout.

**8a — the handover commit (on the branch):**

    cd /home/miftah/.worktrees/seer/gate-reading-cadence
    git add docs/plans/HANDOVER_20261019-the-gate-reading-cadence.md
    # write the message to a file first — a heredoc indented inside a plan block will not terminate
    cat > /tmp/p4-msg-handover.txt <<'MSG'
    docs: handover — «the finding, as a claim: e.g. "the gate wants to be read slowly, and the lab already reads it at the best speed"»

    M0260's six arms on M0072-Z2-RAWRANK's book, weekly through yearly, with nothing moving
    but the rule set's cadence and the gate's checking interval. «Two or three sentences: where
    the ladder turns; the split of M0258's +7.01 points a year into «…» of re-pick frequency
    and «…» of gate reading cadence; whether the folds drifted toward the slowest-trading rung.»

    Records that the cadence axis is separable only on the slow side — a monthly book cannot act
    on a reading taken between its rank sessions — and that this is why the slow rungs live in
    the allocator's params rather than in TradeRules: sim.rules.Cadence has no quarterly or
    yearly member, so a quarterly gate is promotable where a quarterly cadence does not exist.
    Both weekly arms run on a rule set that is not in sim.rules.PRESETS and can never be
    promoted whatever they showed.

    Every return quoted is money-weighted on the owner's own deposits. No test-window look was
    spent: looks still read 4.

    Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
    MSG
    git commit -F /tmp/p4-msg-handover.txt

(The message body above is indented only by this plan. Strip the four-space indent when writing
`/tmp/p4-msg-handover.txt`, so the commit's subject line starts at column 1.)

**8b — the close-out commit (on the branch):** `.workflows/todos.md`, and
`docs/plans/GATE_READING_CADENCE_PLAN.md` **only if Step 6 found it tracked on the branch or still
untracked**.

    git add .workflows/todos.md
    git add docs/plans/GATE_READING_CADENCE_PLAN.md
    cat > /tmp/p4-msg-closeout.txt <<'MSG'
    chore(lab): close out the M0260 gate-reading-cadence plan set

    Mark P1-ROOT-C4DN completed in .workflows/todos.md (moved into Completed Tasks, Quick Stats
    recounted: P1 2->1, Completed 21->22, Total Active 2->1) and set
    GATE_READING_CADENCE_PLAN.md's Status to complete. Four-phase set; no next phase to unblock.

    Result: M0260 pre-registered, run and recorded. Six dev trials («n»-«n»), dev trials
    830 -> «836», lab N 163 -> «164», test-window looks unchanged at 4. «The ladder's answer in
    one sentence.»

    Drift: «…»

    Decided: «…»

    Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
    MSG
    git commit -F /tmp/p4-msg-closeout.txt

(Same note: strip this plan's four-space indent before writing the file.)

**8c — the merge, in the MAIN checkout.** `main` has moved since the branch was cut: phase 3's
`lab run` / `lab stage` commits landed there. The merge direction is branch -> main.

    cd /home/miftah/seer
    git -C /home/miftah/seer status --short          # must be clean; if lab.sqlite shows modified, see 8e
    git -C /home/miftah/seer rev-parse --abbrev-ref HEAD   # must print: main
    cat > /tmp/p4-msg-merge.txt <<'MSG'
    merge(gate-reading-cadence): 4 phases -- gate-reading-cadence

    M0260 — the SPY-200 gate's reading cadence, swept weekly to yearly on M0072-Z2-RAWRANK's
    book. Phase 1 the prior grid and the anchor probe, phase 2 the method file and its dedicated
    tests, phase 3 the pre-registration, the run and the verdict, phase 4 the handover.

    Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
    MSG
    git -C /home/miftah/seer merge --no-ff feature/gate-reading-cadence -F /tmp/p4-msg-merge.txt

(Same note about the indent.)

**The three things that must NOT happen in this merge:**

1. **`lab/lab.sqlite` and `web/data/lab.json` must not come from the branch.** Phase 3 committed
   them on `main` in the main checkout; the branch never had them. Confirm after the merge:

       git -C /home/miftah/seer show --stat HEAD | grep -E 'lab\.sqlite|lab\.json'   # expect: no output

   If either appears in the merge's diffstat, the branch carried a stale copy. Abort
   (`git merge --abort` before committing, or `git revert -m 1 HEAD` after) and re-run `lab stage`
   in the main checkout before trying again.

2. **No `git pull --rebase`, ever, on this repo while a lab commit is unpushed.** A rebase replays
   a stale `lab.sqlite` over the live shared database that other sessions are writing.

3. **No `git add -A`, no `git reset --hard`.** This worktree shares an index with other swarm
   sessions; stage by explicit path only.

**8d — push:**

    git -C /home/miftah/seer push origin main
    echo "push exit=$?"

**8e — if the push is rejected** (someone else pushed first):

    git -C /home/miftah/seer fetch origin
    git -C /home/miftah/seer log --oneline HEAD..origin/main          # see what landed
    # DO NOT rebase. Merge origin/main in instead:
    git -C /home/miftah/seer merge origin/main

    # If the conflict is lab/lab.sqlite or web/data/lab.json, resolve by REGENERATING, never by
    # picking a side — a binary "ours/theirs" silently drops someone's trials:
    PYTHONPATH=/home/miftah/seer/engine/src \
      /home/miftah/seer/engine/.venv/bin/python -m seer_engine lab stage > /tmp/p4-stage.txt 2>&1
    echo "stage exit=$?"
    git -C /home/miftah/seer commit          # NO pathspec — a pathspec re-reads the working tree
                                             # and defeats lab stage

    # Then check the trials are contiguous before pushing again:
    sqlite3 /home/miftah/seer/lab/lab.sqlite \
      "select count(*), min(n), max(n), max(n)-min(n)+1 from trials;"
    git -C /home/miftah/seer push origin main

A conflict on `docs/plans/GATE_READING_CADENCE_PLAN.md` or `.workflows/todos.md` is resolved by
**union** — keep both sides' rows and recount the Quick Stats by hand. Never resolve a todos
conflict by taking one side whole.

**8f — clean up, only after the push succeeded:**

    git -C /home/miftah/seer log --oneline origin/main -3     # the merge must be on origin/main
    git worktree remove /home/miftah/.worktrees/seer/gate-reading-cadence
    git -C /home/miftah/seer worktree prune
    git -C /home/miftah/seer branch -d feature/gate-reading-cadence   # -d, never -D

`git branch -d` refuses if the branch is not fully merged — that refusal is the safety check, so do
not reach for `-D`. If `git worktree remove` refuses because the tree is dirty, read what is dirty
first: an uncommitted capture or scratch file is fine to discard, an uncommitted edit to a tracked
file means Step 8a or 8b missed something.

**Impact:** `main` carries the whole set; the branch and the worktree are gone; `origin/main` is
the record. Vercel builds only `main`, so this push is also what updates `/sera` with phase 3's
`web/data/lab.json`.

---

## Verification

**Build:** `PY=/home/miftah/seer/engine/.venv/bin/python; cd /home/miftah/.worktrees/seer/gate-reading-cadence && $PY -m ruff check engine`

**Tests:**

    docker start seer-pg
    export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres
    export PYTHONPATH=/home/miftah/.worktrees/seer/gate-reading-cadence/engine/src
    cd /home/miftah/.worktrees/seer/gate-reading-cadence && \
      /home/miftah/seer/engine/.venv/bin/python -m pytest -n0 engine/tests

**Manual check:** read the handover top to bottom once, out loud if that helps, against
`/tmp/m0260/06-ladder.tsv` and `/tmp/m0260/06-decomp.txt` open beside it. The failure mode this
phase actually has is a number that is right in the capture and wrong in the prose.

**Exit criteria**, each one checkable:

1. `test -f /home/miftah/seer/docs/plans/HANDOVER_20261019-the-gate-reading-cadence.md` succeeds
   after the merge.
2. `grep -c '«' <handover>` returns `0`.
3. `grep -Ei 'total_return|\bcagr\b' <handover>` matches only the sentence that says those columns
   are *not* quoted — zero of them appear in a table cell. **(R5)**
4. `grep -q 'PRESETS' <handover> && grep -q 'Cadence' <handover>` succeeds, and the handover
   contains a paragraph that names the **four** monthly arms as promotable and both weekly arms as
   never promotable. **(R4)**
5. The handover contains all eight house section headers: the title line stating a finding, the
   `**Written:** / **Branch:** / **Method spent:** / **Next free id:**` block, the lab-state table,
   `## What this session established`, a paired-difference table, `## What is now dead, and must
   not be bought with another method id`, `## Leftovers, in priority order`,
   `## Environment notes that save an hour`.
6. The lab-state table reads `test-window looks used | **4 — unchanged. None was spent.**` and
   agrees with `16-final.txt`.
7. The handover's ladder table has **six** arm rows — `W-NATIVE`, `W-G1`, `M-NATIVE`, `M-G3`,
   `M-G6`, `M-G12`, and **no `M-G2` row** — and its decomposition table has three rows whose first
   two sum to the third on both columns.
7b. The handover says in its own words that the ladder is six arms because `MAX_VARIANTS = 6`, and
   that the two-month rung is a measured prior deferred to an `Amendment` that costs no method id.
7c. The handover says the lookback is 454 and that the first scored session is still `1996-01-03`,
   so the two native arms are reproductions and not approximations.
8. `test -f ~/.claude/projects/-home-miftah-seer/memory/seer-gate-cadence-separable-only-on-the-slow-side.md`
   succeeds, and `grep -c 'seer-gate-cadence-separable-only-on-the-slow-side.md' ~/.claude/projects/-home-miftah-seer/memory/MEMORY.md`
   returns exactly `1`.
9. `grep -c 'seer-gate-cadence-is-worth-more-than-any-band.md' ~/.claude/projects/-home-miftah-seer/memory/MEMORY.md`
   returns exactly `1` — superseded in place, not duplicated — and that line no longer says
   "Queued as M0260".
10. `grep -c 'P1-ROOT-C4DN' /home/miftah/seer/.workflows/todos.md` returns `1`, under
    `## Completed Tasks`, and the Quick Stats arithmetic adds up.
11. `grep -n '^\*\*Status:\*\*' /home/miftah/seer/docs/plans/GATE_READING_CADENCE_PLAN.md` reads
    `complete` (it read `planned` when this phase started), and the file is tracked on `main`
    through the merge of the branch, not committed separately in the main checkout.
12. `git -C /home/miftah/seer show --stat HEAD | grep -E 'lab\.sqlite|lab\.json'` prints nothing —
    the merge carried no lab database.
13. `git -C /home/miftah/seer log --oneline origin/main -1` is the merge commit; `ruff` and
    `pytest -n0 engine/tests` were green on the branch before it.
14. `git -C /home/miftah/seer worktree list` does not list `gate-reading-cadence`, and
    `git -C /home/miftah/seer branch --list feature/gate-reading-cadence` prints nothing.
15. `sqlite3 /home/miftah/seer/lab/lab.sqlite "select max(n)-min(n)+1 = count(*) from trials;"`
    returns `1` — trial `n` is contiguous after every push.

---

## Handoffs

- **R1 and R2 belong to phase 3**, not here. This phase *quotes* where the ladder turns and *quotes*
  the fold-by-fold reading; it does not decide either. If a capture is ambiguous — a fold line that
  does not name its arm, a ladder with a missing DSR — ask phase 3's session or re-read the lab
  read-only (Step 1's fallback), but do not compute a verdict.
- **Any `feature-wish` insight** for a `weekly-hold-frac-gotrade` preset is phase 3's to journal,
  because journalling writes `lab.sqlite`. This phase only records in the handover that it was
  journalled, or that it is still owed. If phase 3 did not journal it and a weekly arm won, that
  becomes leftover item 1 of the next session, written as such.
- **`engine/.workflows/todos.md`** — left to whichever of phases 2 and 3 opened an entry there.
- **The nine D17-blocked methods**, the buyback holdability problem, insight 457's withdrawn
  conclusion, `P2-ENG-N3LB` and `P3-ENG-V2KQ` — all carried forward into the leftovers list
  unchanged. None is in scope for this phase, and none should be quietly "fixed" while writing a
  handover.
- **Applying the winning cadence to the rest of the roster** is the obvious next method — and it is
  deliberately *not* started here. It goes in the leftovers list with the M0197 caution attached.
- **`docs/plans/2026-10-04-method-lab-design.md`** is not touched. If this run's result argues for
  a design-doc revision, that is an owner-facing change and belongs in the leftovers list, not in
  this phase's diff.

## Rollback

This phase is additive prose plus a merge, so it undoes cleanly — unlike phase 3, whose trials are
append-only by trigger and stay recorded whatever happens here.

**Before the push:**

    git -C /home/miftah/seer reset --hard ORIG_HEAD      # undoes the merge only; the branch survives
    # (safe here because the main checkout is clean and nothing else is mid-write in it —
    #  check `git -C /home/miftah/seer status --short` first)

**After the push:**

    git -C /home/miftah/seer revert -m 1 <merge sha>     # reverts the whole set's branch content
    git -C /home/miftah/seer push origin main

That revert removes the handover, the study, the method file and the test module — it does **not**
remove M0260's trials, which are in `lab.sqlite` and append-only. A reverted method file with live
trials is a worse state than either end, so prefer the surgical rollback: revert only the two
commits this phase authored.

    git -C /home/miftah/seer revert <close-out sha> <handover sha>

**Memory files** are outside git. To undo them: delete
`seer-gate-cadence-separable-only-on-the-slow-side.md`, remove its `MEMORY.md` line, and restore
the two edited files from their previous text (the pre-edit content of
`seer-gate-cadence-is-worth-more-than-any-band.md` is quoted in full in Step 4b's preamble and in
this plan set's analysis).

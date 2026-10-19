# Plan: the lab stops naming its residual after whichever ingredient it was thinking about

**Slug:** lab-shortfall-and-control-shape
**Date:** 2026-10-19 11:05:02
**Analysis:** `docs/analyzer/20261019-110502-S4KQ_code_analyzer.md`
**Worktree:** `/home/miftah/.worktrees/seer/lab-shortfall-and-control-shape`
**Branch:** `feature/lab-shortfall-and-control-shape` (base: `origin/main` @ `ad8792d`)
**Phases:** 4
**Status:** landed — all four phases merged to `main` 2026-10-19 as `da9d326`
**Coordinator:** `orch-lab-shortfall-and-control-shape`

---

## Why

The user's brief, verbatim:

```
lab feature

Read docs/plans/HANDOVER_20261019-the-placebo-is-a-control-not-a-constant.md first — it is your
brief, written by the session that found the problem. Sections 1 and 2 carry the evidence; the
section "The task for the next session" at the bottom is the scope.

Build: (1) a shortfall decomposition that splits any trial's gap to SPY TR over an era into gate
premium, fee drag, pool and residual weighting — the inputs are already in the trials row
(exposure, turnover, curve_json, spy_tr_cagr); (2) a control-shape check that compares a
placebo/control arm's trade count and turnover against the arm it controls and refuses or loudly
flags a mismatch; (3) as a small phase, the PIPESTATUS / duplicate-note fix in section 5.

The motivating case is trial n=828 (M0244-PLACEBO30): the lab published its 2009-2015 shortfall as
an 8.2 pt "equal-weight handicap" when the arm also carries the SPY-200 gate at 0.692 exposure, 15
turns/yr of fees, and a top-50 momentum pool. The decomposition must be able to answer whether any
of that 8.2 is actually weighting.
```

And the brief's own closing section, which is the acceptance test:

> **Done means:** a decomposition command exists and is run on trial 828, the 8.2 figure is either
> confirmed with its components named or retired from the memory note, insight 461 and the `/sera`
> page; a mismatched control arm fails loudly; and `lab note` cannot double-append.

## Requirements

| ID | What the user asked for | Phases |
|---|---|---|
| R1 | A shortfall decomposition: split any trial's gap to SPY TR over an era into gate premium, fee drag, pool and residual weighting, from inputs already in the trials row. Run it on trial 828 and answer whether any of the 8.2 pts is weighting. | **1** (builds it, and measures 828), **4** (runs it on 828 for the record and writes `docs/backtests/2026-10-19-trial-828-shortfall.md`) |
| R2 | A control-shape check: compare a placebo/control arm's trade count and turnover against the arm it controls, and refuse or loudly flag a mismatch. It must catch M0230 and M0248. | **2** (the module and the calibrated band), **4** (`lab control`, the `lab run` annotation, hard gate D17) |
| R3 | The `PIPESTATUS` / duplicate-note fix from handover §5: `lab note` must not be able to double-append an identical analysis. | **3** |

R1 is split across two phases because the brief's acceptance test is split: "a decomposition
command **exists** *and* **is run on trial 828**". Phase 1 owns the command; phase 4 owns the
written run, because the same document also carries the `lab control` table, which does not exist
until phases 2 and 4 have landed. The id follows the work — phase 4's **Satisfies** line says R1
and R2, and its Step 10 is the R1 half.

## Scope

**In scope**

- A new `lab/shortfall.py` and a `lab shortfall` report: pure arithmetic over recorded trial rows,
  with one optional store read for the era-resolved gate exposure.
- A new `lab/control_shape.py` and a `lab control` report, plus the annotation at `lab run` and the
  refusal at `lab promote` (hard gate D17).
- `store.append_analysis` refusing a byte-identical re-append, and `lab note` printing a
  confirmation line so a piped invocation has output to match.
- One backtest note recording the run on trial 828.

**Out of scope, and why**

- **Correcting insight 461, the memory note and the `/sera` synthesis page.** The brief's "done
  means" asks for the 8.2 to be retired *in those three places*, but `insights` is append-only, a
  `/sera` correction runs through the `update-stale-sera-methods-page` skill, and a memory note is
  the owner's file. This plan produces the measurement and the backtest note that those three
  corrections quote; making them is a separate, owner-visible act. Phase 4 states the three
  corrections and their exact numbers so they can be applied in one sitting.
- **Re-running any arm.** The handover's §1 "Do" also suggests re-running the placebo with
  `trend=None`, at STALE-like turnover, and on a non-momentum pool. Those are three new trials that
  cost method ids and raise N for the whole lab. The decomposition answers the same question from
  recorded rows for free; if it leaves a residual anyone disputes, the re-runs are the next step and
  not this one.
- **Any new lab method, trial, insight row, or status change.** Nothing here moves N or spends a
  test-window look.
- **`web/`**. Nothing is journaled, so `web/data/lab.json` does not move and `lab stage` is not
  called by any phase.

## Invariants

Every phase holds all of these. They are the lab's rules, not this plan's preferences.

1. **The tree builds and `pytest engine/tests` passes at the end of each phase**, with
   `PYTHONPATH=engine/src` set — without it pytest silently tests the main checkout instead of this
   branch.
2. **Nothing is recorded.** No phase adds a `trials`, `trial_moments`, `trial_funding`,
   `trial_provenance`, `insights` or `method_folds` row, and no phase moves a method status. Every
   new report prints `N (dev trials)` and `test-window looks` before and after its work, the way
   `lab regime`, `lab turnover` and `lab names` already do, so the invariant is visible on the
   terminal and not merely asserted in a test.
3. **The test window is never read.** No phase passes `window="test"`, opens
   `engine/.research-test`, or calls anything that could.
4. **Closed records are frozen.** No phase edits a recorded `lab.sqlite` row, a past backtest
   report, `backtest/registry.py`, or any `lab/methods/mNNNN_*.py` file. Method files are frozen
   against their recorded `source_sha` and an edit breaks `store.latest_source_sha` for a method
   whose trials already exist.
5. **No recorded `config_digest` moves.** `method.config_text` reads `rules`, `allocator.id` and
   `params` only. A new field may be added to `Candidate` (outside the digest) but **never** to a
   shared params dataclass.
6. **`lab/lab.sqlite` is never committed from this branch.** Every `lab` subcommand runs the
   migrations on connect, so even a read dirties the file. Phases that run a `lab` command check
   the hash before and after and `git checkout -- lab/lab.sqlite` if it moved.
7. **Tests never reach production.** The autouse fixture pointing tests at a nonexistent env file
   and an `.invalid` DB host stays exactly as it is.
8. **argparse `help=` strings escape `%` as `%%`.** `description=` is not interpolated and stays
   single. Every new parser carries the same comment the `costs`, `exposure` and `gate` parsers do.
9. **Module docstrings explain *why* the code is shaped the way it is**, in the prose style the
   rest of `lab/` uses. A new module in this package with a one-line docstring is not finished.
10. **One de-funding path.** Any era slice of a recorded curve goes through
    `walkforward.measure` + `hardgate.trial_deposits`. No phase writes a second reconstruction:
    `trial_deposits`'s own docstring is explicit that a second one is a second chance to read a
    deposit as edge.
11. **Exit codes:** 0 ok, 2 for a `store.LabError` (the lab's rules refused), 1 for an error.
12. **The research store is not in the worktree.** `engine/.research*` are gitignored. A phase that
    needs the dev store passes `--store /home/miftah/seer/engine/.research`; it never rebuilds one.

## Working environment — already prepared, do not rebuild

This was set up and verified by the analysis session on 2026-10-19 so that no phase pays for it and,
more importantly, so that **two concurrent phases cannot race to create the same virtualenv**.
Phases 1 and 2 run at the same time in this one worktree; two `pip install -e` runs into one
`engine/.venv` corrupt it.

- **`engine/.venv` exists and is installed** (`engine[dev]`, `seer_engine` importable, `pytest` and
  `pytest-xdist` present). **Do not recreate it.** If it is genuinely broken, say so in the phase
  report rather than silently rebuilding it under another phase's feet.
- **`python3.11` is NOT on this machine's PATH**, despite the command in `CLAUDE.md`. The
  interpreter both checkouts actually use is `/home/miftah/miniconda3/bin/python3.12` (Python
  3.12.7). Use `engine/.venv/bin/python`, `engine/.venv/bin/pytest` and `engine/.venv/bin/ruff`
  and the question does not arise.
- **The baseline is green**, measured in this worktree at `ad8792d` before any phase ran:

      PYTHONPATH=engine/src PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
          engine/.venv/bin/pytest engine/tests -q
      -> 5947 passed, 4 skipped, 130.69s

  The 4 skips are all opt-in live-store tests (`SEER_LAB_COSTS_LIVE`, `SEER_LAB_NAMES_LIVE`,
  `SEER_LAB_SURVIVORSHIP_LIVE`, and a month-end sweep absent on this machine). **The Postgres DB
  tests did not skip** — CI fails if they do. Any other failure a phase sees is that phase's own.
- **The `seer-pg` container is running** on port 55432. Export
  `PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres` for every test run.
- **This shell prints `setValueForKeyFakeAssocArray: command not found: _encode` on startup.** It is
  harmless noise, and it is the origin of the bug phase 3 fixes — a `grep -v` scrubbing it owns the
  pipeline's exit code. Never judge a lab command by a piped exit code; redirect to a file and echo
  the command's own `$?`.
- **The research stores are gitignored and absent here.** The dev store is
  `/home/miftah/seer/engine/.research`; pass `--store` at it. Never rebuild one — it is 30 minutes
  plus a yfinance crawl for nothing.

## Phases

| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID | Card |
|---|-------|-----------|---------|-------|-----------|------------|------|--------|------|
| 1 | The shortfall decomposition, and `lab shortfall` | R1 | `engine/seer_engine/lab` | 3 | — | HARD | `.workflows/plan/lab-shortfall-and-control-shape/phase-1.md` | P1-ENG-NVHT (done 2026-10-19) | — |
| 2 | Control detection, target resolution and the calibrated band | R2 | `engine/seer_engine/lab` | 2 | — | NORMAL | `.workflows/plan/lab-shortfall-and-control-shape/phase-2.md` | P1-ENG-03W0 (done 2026-10-19) | — |
| 3 | `lab note` cannot double-append, and says what it did | R3 | `engine/seer_engine/lab` | 3 | 1 | EASY | `.workflows/plan/lab-shortfall-and-control-shape/phase-3.md` | P1-ENG-ISID (done 2026-10-19) | — |
| 4 | `lab control`, the `lab run` annotation, hard gate D17, and the trial-828 note | R1, R2 | `engine/seer_engine/lab` + `commands` + `docs/backtests` | 4 | 2, 3 | HARD | `.workflows/plan/lab-shortfall-and-control-shape/phase-4.md` | P1-ENG-DZDN (done 2026-10-19) | — |

**Files** counts, after reconciliation: phase 1 = `lab/shortfall.py` (new), `commands/lab.py`,
`tests/test_lab_shortfall.py` (new). Phase 2 = `lab/control_shape.py` (new),
`tests/test_lab_control_shape.py` (new). Phase 3 = `lab/store.py`, `commands/lab.py`,
`tests/test_lab_store.py`. Phase 4 = `commands/lab.py`, `lab/hardgate.py`,
`tests/test_lab_hardgate.py`, `docs/backtests/2026-10-19-trial-828-shortfall.md` (new). No count
moved in reconciliation; phase 4 lost two symbols (`_control_shape_line`, `hardgate._shape_cell`)
but no file.

Waves: **{1, 2}** run concurrently, then **{3}**, then **{4}**.

### Phase 1 — The shortfall decomposition, and `lab shortfall`

**Satisfies:** R1 — the command itself. Phase 4 owns R1's written acceptance (the run on trial 828
recorded in `docs/backtests/2026-10-19-trial-828-shortfall.md`), and this phase hands it the
numbers.

**Owns:**
- **new** `engine/src/seer_engine/lab/shortfall.py`
- the `shortfall` subparser and its dispatch entry in `engine/src/seer_engine/commands/lab.py`
- **new** `engine/tests/test_lab_shortfall.py`

**Does not touch:** `lab/control_shape.py` (phase 2), `lab/store.py` (phase 3), `lab/hardgate.py`
(phase 4), any method file, any recorded row.

**What it builds.** A report of shape (A) — pure arithmetic over recorded rows, nothing written,
`N` and the looks printed before and after. Given a trial (by `n` or by candidate id) and an era
from `exposure.ERAS` (default `2009-2015`, `--era whole` for the whole window), it prints:

```
gap to SPY TR                      the era's de-funded CAGR minus REF-SPY-HOLD's, same slice
  - gate premium                   (1 - era exposure) x the era's SPY TR return
  - fee drag                       turnover x the modelled per-dollar round-trip rate
  = pool + weighting residual      what the two named terms do not explain
```

**The four things that make this honest, and that the phase plan must implement rather than
approximate:**

1. **The gap is not recomputed.** It comes from `walkforward.measure(curve, start, end, deposits)`
   with `deposits` from `hardgate.trial_deposits`, against `REF-SPY-HOLD` sliced the same way —
   the identical path `lab exposure`, `lab gate` and `lab survivorship` already use. Invariant 10.
2. **Era exposure is era-resolved when it can be, and labelled when it cannot.** `trials.exposure`
   is whole-window; using it for 2009-2015 prices the gate at 5.11 pts/yr where the era-resolved
   figure is 3.60 — a 1.5 pt error on an 8.2 pt headline. With `--store`, the command measures the
   shared SPY-200 gate's on-share per era from SPY's own bars and scales:
   `era_exposure = recorded_exposure x (era_gate_on / whole_gate_on)`. The ratio carries the gate's
   era shape; the recorded exposure carries the book's own slot-fill drag. Without `--store` it
   falls back to the recorded whole-window exposure and says so in the output, every time.
3. **Fee drag is modelled, not recovered.** The run's real fees (`RunStats.costs_usd`) are not a
   `trials` column. The model runs `turnover.round_trip` at the slot size the owner's funding
   implies at the era's month offsets, and reports `turnover x (round_trip_total / (2 x slot))`.
   Both sides are counted because `book_runner._turnover` counts both.
4. **`pool` is not separable from one row, and the command refuses to pretend otherwise.** By
   default the two unexplained ingredients are reported as **one** `pool + weighting` residual.
   `--against <candidate_id>` splits it: the part a sibling arm sharing the same pool, gate and
   frame also carries is attributed to pool and frame, and only the remainder to this arm's own
   weighting and selection.

**Exit criteria:**
- `lab shortfall 828` and `lab shortfall M0244-PLACEBO30` both work; `--era`, `--store` and
  `--against` work; `--era whole` works.
- The terms sum back to the gap exactly, and a test asserts it.
- The output states, in plain words a non-quant reads: that this is an attribution under stated
  assumptions and not an identity; that idle cash earned nothing after 2008 and something before
  it; and which exposure figure was used.
- Run on trial 828 with `--store /home/miftah/seer/engine/.research`, the report reproduces
  gap −8.24, gate ≈ −3.60 at an era-resolved exposure of 0.784, fees ≈ −3.78 (15.05 turns at
  0.2510%, the mean rate over the era's own month offsets, at the **30** names `names_in` reads
  out of trial 828's recorded configuration), residual ≈ −0.87 pts/yr. **Those numbers are the
  phase's own to verify, not to assume** — if the implementation disagrees, the implementation's
  number is the finding and the phase records it. (The analysis document first published
  −3.76 / −0.88, from the rate at one month offset rather than the era mean; it has been corrected
  and the reconciled figures above are what every file in this set quotes.)
- `ruff check engine` clean; `pytest engine/tests` green.

### Phase 2 — Control detection, target resolution and the calibrated band

**Satisfies:** R2

**Owns:**
- **new** `engine/src/seer_engine/lab/control_shape.py`
- **new** `engine/tests/test_lab_control_shape.py`

**Does not touch:** `commands/lab.py` (phase 4 wires the CLI), `lab/hardgate.py` (phase 4),
`lab/shortfall.py`, any method file.

**Interface, final — phase 4 is written against exactly this.** `Finding` is the rich record
(`method_id`, `control_id`, `kind`, `target_id`, `rung`, `control`, `target`, `trade_ratio`,
`turnover_ratio`, `verdict`, `reason`; properties `refused`, `flagged`); `Shape` is the small
per-arm record (`candidate_id`, `n`, `trades`, `turnover`). Entry points: `findings(conn,
method_id, arms)`, `for_method(conn, method_id)`, `survey(conn, method_ids=None)`. Filters and
text: `refusals`, `flags`, `describe`, `band_sentence`, `format_report(found, *, show_clean=True)`.
Verdicts: `OK` / `WARN` / `REFUSE` / `UNRESOLVED` / `UNRECORDED` / `NOT_CHECKED`, with
`WARN_BAND = (0.8, 1.25)` and `REFUSE_BAND = (0.5, 2.0)`. **The module prints nothing and raises
nothing**: every refusal message is phase 4's to compose out of `describe()`.

**What it builds.** A pure module, no CLI, that answers three questions over recorded trial rows:

1. **Which arms are shape-matched controls?** From the candidate id and the `rationale` — a
   placebo, a blind draw, a within-frame control. **Dose-response arms are excluded**:
   `M0244-STALE30` and `M0241-STALE` are *supposed* to differ in shape, because the different date
   is the dose, and treating them as shape-matched controls is a permanent false alarm on a correct
   arm. A `Candidate` may also declare its control relationship outright — a new defaulted field,
   outside `config_text` so no recorded digest moves — but **no existing method file is edited**:
   their `source_sha` is recorded and frozen, so the twelve recorded control arms are reached by
   detection alone.
2. **Which arm does it control?** The sibling the id stems to, else the arm whose rationale marks
   it as the method's own idea or yardstick, else the first declared candidate. The module reports
   the resolution it used, so a wrong guess is visible rather than silent.
3. **Is the shape matched?** Trade count **and** turnover against the controlled arm, as ratios.
   Both axes are mandatory: `M0226-RAND2` is within 1.33× on trades and 14.5× on turnover, so a
   trades-only check misses it entirely.

**The band is calibrated, not chosen.** The fixture is the lab's own control arms measured
**against the arm each one actually controls**, which the module's four-rung resolution ladder
finds (declared → sibling-stem → declared idea/yardstick → first declared, every rung drawing only
from arms that are not themselves a control). Clean arms sit at 0.98–1.02 on both axes; every
mis-shaped one is at 2.976× or worse, or 0.138× or less, on at least one. Warn outside
[0.8, 1.25]; refuse outside [0.5, 2.0]; both log-symmetric. The test pins the whole table,
including the one warn-only case (`M0241-PLACEBO` at 1.372 trades / 1.131 turnover).

The analysis document's table measured each control against its **nearest sibling by trade
ratio**, which is a different arm in several rows; it has been corrected to say so, and the
module's resolved-target numbers supersede it. **Every verdict is the same either way** — only the
numbers move (e.g. `M0248-R` reads 3.180/3.078 against `M0248-EQ`, not 3.08/2.88 against
`M0248-D75`). The analysis document also wrongly listed `M0005-ALL-R` as a control arm: it is a
rank-weighting variant ("does conviction in the top names pay"), it carries no control marker, the
module correctly produces no finding for it, and that row is struck.

**Exit criteria:**
- `M0230-C50-R` (0.067× / 0.138× against `M0230-C50`) and `M0248-R` (3.180× / 3.078× against
  `M0248-EQ`) both land in the refuse band — the two cases the handover named.
- `M0243-NEAR20-R` (3.013× / 2.976× against `M0243-NEAR20`) also lands there. The handover knew
  of two; measured over all 46 placebo arms the lab holds, **19 refuse, 7 warn, 4 are clean and 16
  have no arm to compare against**. The phase records that tally as a finding.
- `M0244-PLACEBO30` (1.015× / 0.984× against `M0244-FRESH30`) passes clean.
- `M0244-STALE30` and `M0241-STALE` are classified dose-response, carry verdict `not-checked`,
  hold no ratio, and are never flagged for shape. No dose arm anywhere in the lab is flagged.
- `M0005-ALL-R` produces **no finding at all**.
- A test builds the table from the committed `lab/lab.sqlite`, opened `mode=ro`, and pins every
  row; it also asserts the file's bytes did not move.
- `ruff check engine` clean; `pytest engine/tests` green.

### Phase 3 — `lab note` cannot double-append, and says what it did

**Satisfies:** R3

**Owns:**
- `engine/src/seer_engine/lab/store.py` — `append_analysis`
- `engine/src/seer_engine/commands/lab.py` — `_note` only
- `engine/tests/test_lab_store.py` — the new refusal

**Does not touch:** the `shortfall` parser (phase 1 owns it), the `control` parser (phase 4), any
other subcommand, `lab/hardgate.py`.

**Depends on phase 1** for one reason only: both edit `engine/src/seer_engine/commands/lab.py`, and
Seer swarm phases share one worktree and one git index, so concurrent edits to that file lose work
rather than conflicting. Phase 3 quotes the file as phase 1 leaves it. There is no semantic
dependency.

**What it builds.** Two halves of one bug.

- **The duplicate cannot be written.** `store.append_analysis` compares the incoming body against
  what is already the newest section and raises `store.LabError` when they are the same, naming
  the method and saying plainly that nothing was appended and the stored copy is intact. The
  refusal must be *before* the write: `methods_analysis_grows` permits only growth, so a duplicate
  that lands is permanent and a direct `UPDATE` to remove it is correctly refused.
- **A success is not silent.** `_note` prints one confirmation line. The root cause memory records
  is that most `lab` subcommands succeed silently, so a filter in the pipeline owns the exit code
  and "no output" is indistinguishable from "failed". A line of output makes the retry unnecessary
  *and* makes the refusal above visible when a retry happens anyway.

**Exit criteria:**
- Appending the same body twice raises `LabError`, exit 2, with the stored analysis unchanged.
- Appending a *different* body still works, and still gets its `### <date>` heading exactly as
  before — including the existing behaviour where the author's own heading is not duplicated.
- A re-append whose only difference is leading or trailing whitespace is still caught.
- `lab note` prints a confirmation naming the method and what was written.
- `ruff check engine` clean; `pytest engine/tests` green.

### Phase 4 — `lab control`, the `lab run` annotation, and hard gate D17

**Satisfies:** R2 (all three bindings) **and the acceptance half of R1** (the run on trial 828,
written down).

**Owns:**
- `engine/src/seer_engine/commands/lab.py` — the `control` subparser, its dispatch, `_control`,
  and the annotation block in `_run`
- `engine/src/seer_engine/lab/hardgate.py` — decision (D17), `mis_shaped_controls`, and the D17
  clause in `check`
- `engine/tests/test_lab_hardgate.py` — the D17 refusal and the three bindings
- **new** `docs/backtests/2026-10-19-trial-828-shortfall.md` — the run on trial 828

**Does not touch:** `lab/control_shape.py` (phase 2 owns it — this phase only calls it),
`lab/shortfall.py` (phase 1), `lab/store.py` (phase 3), any method file.

**Depends on phase 2** for the module it calls, and on **phase 3** because both edit
`commands/lab.py` and that file is serialised across this plan.

**What it builds.** Three bindings of phase 2's module, at the three moments a researcher could
act on a mis-shaped control.

1. **`lab control [M0248 ...]`** — a shape-(A) report over recorded rows: `survey(conn)` then
   `format_report(found)`. No store, nothing written, `N` and the looks printed before and after.
   With no method named it reports every control arm the lab holds — 46 placebo arms, 6
   dose-response and 2 within-frame.
2. **At `lab run`** — a loud block after the trials are recorded, beside the walk-forward verdict.
   **It annotates; it does not refuse.** This follows the lab's own written decision (D15): a
   run-time gate "would only spend method ids to say what the first one already says", and the run
   must complete so the lab can bootstrap.
3. **At `lab promote`** — `hardgate.check` refuses a method whose control arm is outside the
   refuse band (`refusals(for_method(conn, mid))`), because a method's "it beat its control by X"
   evidence is unsound when the control was handicapped. This is the refusal half of "refuse or
   loudly flag", placed where the lab already puts its refusals. **The refusal names the way
   back**: re-draw the control at the book's own trade count and turnover and record it as an
   amendment, which costs no method id. A refusal with no stated remedy would be a dead end, and
   this rule meets nine methods that need one.

**And the backtest note.** `docs/backtests/2026-10-19-trial-828-shortfall.md` records the
`lab shortfall 828` output, the `lab control` table, and the three corrections the handover's "done
means" asks for, each with its exact replacement number: the `MEMORY.md` line and the
`seer-equal-weight-shape-costs-8pts-since-2009` note, insight 461, and the `/sera` synthesis page.
The note states them; applying them is the owner's call and runs through
`update-stale-sera-methods-page`.

**Exit criteria:**
- `lab control` with no argument prints every control arm and its verdict; `lab control M0248`
  prints one method's.
- `lab run` on a method with a mis-shaped control prints the block and still exits 0.
- `lab promote` refuses such a method with a message naming the arm, both ratios and the band.
- **`Promotable now:` is unchanged by D17, AND nine dev-eligible methods would be refused at
  `lab promote` if they ever reached it.** Both halves are measured and both are true, because
  dev-eligible is a wider set than promotable-now. `Promotable now:` is `M0072, M0092, M0197`,
  none of which holds a control arm; the nine dev-eligible methods holding a refuse-band control
  arm are **M0047, M0201, M0202, M0208, M0215, M0221, M0225, M0227, M0243**. The phase takes the
  `lab status` reading **before its first edit** (never `git stash` — the swarm shares one index),
  takes it again at the end, and records both halves. The nine are deliberate; see Decisions.
- The backtest note exists and carries the trial-828 numbers from this phase's own run of phase
  1's command (expected: gap −8.24, gate −3.60 at exposure 0.784, fees −3.78, residual −0.87,
  with 30 names read from the configuration and no `--names` flag passed), the `lab control`
  table, and all three corrections with their numbers.
- `ruff check engine` clean; `pytest engine/tests` green; `lab/lab.sqlite` unchanged in git.

## Reconciliation Log

Reconciled 2026-10-19. The four phase planners ran concurrently and could not see each other's
output. Every row below was fixed **by editing the plan files**, not by noting it.

| # | Conflict | Phases | Resolution |
|---|---|---|---|
| 1 | **Phase 4 written against an API that does not exist.** Phase 4 specified `control_shape.shapes(conn, method_id=None) -> list[Shape]` with a rich `Shape` carrying `target_trades`, `trades_ratio`, `resolution`, and constants `CLEAN/DOSE`. Phase 2 built something different: a small `Shape` record, a rich `Finding`, entry points `findings` / `for_method` / `survey`, filters `refusals` / `flags`, text `describe` / `band_sentence` / `format_report`, and verdicts `OK/WARN/REFUSE/UNRESOLVED/UNRECORDED/NOT_CHECKED`. | 2, 4 | **Phase 2 owns the module, so its API wins.** Phase 4's Interface Contract was replaced with phase 2's real names, and `_control`, the `_run` annotation, `mis_shaped_controls` and the `check` clause were all rewritten to phase 2's own wiring recipe: `lab control` → `survey` + `format_report`; `lab run` → `for_method` + `format_report(show_clean=False)` + `refusals`/`flags`; D17 → `refusals(for_method(...))` + `describe(f)`. Phase 2 was not edited. |
| 2 | **Name collision inside conflict 1:** phase 2 *does* export `shapes()`, but it returns `dict[str, Shape]` of one method's recorded arms — an internal reader, not an entry point. Phase 4 called it in three places expecting a list of rich objects. | 2, 4 | All three call sites rewritten. Phase 4's contract now says in bold **"do not call `shapes()`"**, and phase 2's handoff names it as an internal reader so a later session cannot repeat the mistake. |
| 3 | **Phase 4's D17 tests could not fire — they would pass while testing nothing.** `control_shape.for_method` reads a method's arms through `method.discover()` and returns `()` when no `lab/methods/mNNNN_*.py` declares the id. Every fixture in `test_lab_hardgate.py` builds its method straight into the database with no method file. Worse: `M0001` **is** a real method file, so an unpatched `discover()` would judge the synthetic rows against the real M0001's candidate ids and produce `unrecorded`, never `refuse`. | 2, 4 | **Resolved in phase 4's tests only.** Seam chosen and written out in full: a `_declare(monkeypatch, **by_method)` helper patching `seer_engine.lab.method.discover` to return a stub method whose `all_candidates()` yields stub `_Arm` records. `for_method` imports `discover` inside its body, so the patch takes. The alternative seam (`findings(conn, mid, arms)`, which takes arms explicitly) was **not** chosen because it would not run `hardgate.check`'s own clause, which is the thing under test; phase 2 uses it in its own module's tests. The production path is unaffected — a real method has a file — and phase 4's plan says so. **No method file is created by any phase.** |
| 4 | **Phase 4's `lab run` stub would raise `AttributeError`.** `_stub_full_run` monkeypatched `discover` to return `types.SimpleNamespace(id=method_id)`, which has no `all_candidates`, so `_run`'s new block would crash instead of printing. | 4 | `_stub_full_run` rewritten to build its stub through `_declare`, so the stub carries `all_candidates`. |
| 5 | **Phase 4's test arms were detected by id suffix.** The `_control_arm` fixture's docstring claimed a `-R` suffix beside a sibling was enough. Phase 2 detects a control from the candidate's one-line `rationale`, by measured markers; a bare `-R` is detected as nothing. | 2, 4 | Phase 4's tests now give every stub arm real control prose (`"Placebo: … hash-drawn …"`) and give the controlled arm `"The idea: …"` so the resolution rung is deterministically `declared-idea`. The contract and the test section both state the rule. |
| 6 | **A disagreement of fact.** Phase 4 asserted "It refuses nobody today, and that is the point" (`Promotable now:` = M0072, M0092, M0197, none holding a control arm). Phase 2 measured that **nine dev-eligible** methods carry a refusing placebo (M0047, M0201, M0202, M0208, M0215, M0221, M0225, M0227, M0243), and that across all 46 placebo arms the check reads 19 refuse / 7 warn / 4 clean / 16 unresolved. | 2, 4, index | Both are true — dev-eligible is a wider set than promotable-now. **One reconciled sentence now appears identically in phase 2, phase 4 (D17 prose, Step 3, the backtest note, Verification and the exit criteria) and this index:** *`Promotable now:` is unchanged by D17, AND nine dev-eligible methods would be refused at `lab promote` if they ever reached it.* Phase 4's "refuses nobody" paragraph was rewritten out. The nine refusals are **correct and intended**, and that was settled rather than parked. **The fork, the choice and the rung, for the Decisions section:** *fork* — does D17 refuse nine dev-eligible methods, or is the band loosened / the rule scoped so it refuses nobody today? *choice* — it refuses them, and the refusal names the way back. *rung* — **the user's raw input and the brief's own acceptance criterion**: the brief asks for a check that "refuses or loudly flags a mismatch" and says "Done means: … a mismatched control arm fails loudly", and the lab's own written rule (`seer-placebo-matched-to-a-books-exact-shape`) is that a control must match the book's shape, so a method whose control was handicapped has unsound "it beat its control by X" evidence. Nothing is parked: no branch here is irreversible — no data is destroyed, no history rewritten, no migration spent — and the nine methods keep every recorded row they have. |
| 7 | **A refusal with no way out.** Following from conflict 6: nine methods is too many to refuse with no stated remedy. | 4 | **Required plan edit made.** D17's refusal message and its prose both now name the path back — re-draw the control at the book's own trade count and turnover and record it as an amendment, which costs **no method id** because an amendment appends trials under the existing id. That is what the handover asks for on M0248 (§2). `lab control` and the `lab run` annotation print the same remedy, and phase 4's tests assert `"amendment"` and `"costs no method id"` are in the refusal. |
| 8 | **The analysis document is wrong on one row, and phases quote it.** Its twelve-arm calibration table listed `M0005-ALL-R` as a control arm. Its rationale — *"The same composite with linear rank weights: does conviction in the top names pay"* — carries no control marker; only the `-R` suffix suggested otherwise. | analysis, 2, 4 | The row is **struck from the analysis document** with a one-line reason, and the table is now eleven arms. Phase 2's module already produced no finding for it and its test already asserts `"M0005-ALL-R" not in found`; that is now an exit criterion in the index. Phase 4's D17 table and backtest note never carried it. |
| 9 | **Numbers differ between the analysis document and phase 2 — not a conflict, but readable as one.** The analysis measured each control against its *nearest sibling by trade ratio*; phase 2 measures against *the arm actually controlled*, which is correct (e.g. `M0222-RAND1` turnover 4.451× vs 2.41×; `M0243-NEAR20-R` 3.013/2.976 vs 2.16/2.14; `M0248-R` 3.180/3.078 vs 3.08/2.88). | analysis, 2, 4 | One line added to the analysis document saying its table is nearest-sibling and the module's resolved-target numbers supersede it. **Every verdict is unchanged**; only the numbers move. Phase 4's D17 table, `lab control` prose and the backtest note were rewritten to phase 2's numbers, and phase 1's two handoff mentions of M0243/M0248 ratios with them. |
| 10 | **A possible wrong default on the headline number.** Phase 1 sets `DEFAULT_NAMES = turnover.ROSTER_NAMES` (20), but trial 828 (`M0244-PLACEBO30`) is a 30-name book and the fee rate depends on slot size. | 1, 4 | **Checked against the committed `lab/lab.sqlite`, not assumed.** Trial 828's `config_text` reads `params=GestureParams(window_days=380,top=30,…,screen=FactorParams(…,top=1000,…))`; `names_in` takes the shallowest bracket depth carrying a `top=`, so it resolves **30** and `DEFAULT_NAMES` is never reached. Phase 1's worked example is internally consistent at 30 names. Phase 1 now states this explicitly; **phase 4 runs the backtest-note command with no `--names` flag** and is told to read the report's own `names_from` line and record it. (At 20 names the drag would read −3.74 — bounded either way, which is why the sensitivity band is printed.) |
| 11 | **The headline fee and residual disagreed across files.** The analysis document and the index's draft said fees −3.76 / residual −0.88 (the per-dollar rate at one month offset, 0.2498%); phase 1 measured −3.78 / −0.87 (the **mean** rate over the era's own month offsets 156..237, 0.251041%), which is what the implementation computes. Phase 4's backtest note quoted the analysis's figures. | analysis, 1, 4, index | **Phase 1's measured numbers win** — it owns the computation and measured the era mean. The analysis document carries a "superseded on the fee term" block; phase 1, phase 4's expectation block and this index's exit criteria all now read **gap −8.24, gate −3.60 at exposure 0.784, fees −3.78, residual −0.87**. Nothing the plan rests on moves: gate + fees still account for ~7.4 of the 8.2. |
| 12 | **File collision on `engine/src/seer_engine/commands/lab.py`** — phases 1, 3 and 4 all edit it, in one shared worktree with one git index. | 1, 3, 4 | **Verified, not merely asserted.** Checked against the file at `ad8792d`: phase 1 inserts between the `walkforward` parser (ends `:441`) and the `survivorship` parser (`:442`), after `_walkforward` (`:2352`), and in `_HANDLERS` between `"walkforward"` and `"luck"`; phase 3 rewrites `_note`'s body only (`:2741`); phase 4 inserts between the `gate` parser's last `--csv` (`:594`) and `add_parser("idea")` (`:597`), after `_kin` (`:2531`) before `_exposure` (`:2590`), in `_HANDLERS` after `"gate": _gate,`, and inside `_run` after the `"Folds share training data…"` print (`:1625-1628`). **No two regions overlap**, the declared order 1 → 3 → 4 holds, and every anchor in all three plans is quoted text rather than a line number. Phase 4 gained a table of all eight insertion points. |
| 13 | **Three phases told the implementer to build the virtualenv — a binding-rule violation, and a race.** Phases 1, 2 and 3 each said `python3.11 -m venv engine/.venv && pip install -e 'engine[dev]'`. `engine/.venv` already exists and is installed, `python3.11` is not on this machine (the interpreter is `/home/miftah/miniconda3/bin/python3.12`), and **phases 1 and 2 run concurrently in this one worktree** — two `pip install -e` runs into one venv corrupt it. | 1, 2, 3 | All three Verification sections rewritten: do **not** create it, do **not** `pip install` into it, say so in the phase report if it is broken. `PYTHONPATH=engine/src` restated in each. |
| 14 | **Phase 4's key verification used `git stash` in a shared worktree.** `git stash` / `git stash pop` to read `lab status` "before" would take other sessions' uncommitted work with it. | 4 | Rewritten: take the `lab status` reading **as the first act of the phase, before editing anything**, and the second at the end. An explicit "never `git stash`, never stage broadly, never `reset --hard`" paragraph added, with the shared-index reason. |
| 15 | **Duplicate work: two formatters for one table.** Phase 4 created `commands.lab._control_shape_line` and `hardgate._shape_cell` to format ratios — work phase 2 already does in `format_report` and `describe`. | 2, 4 | **Phase 2 is the earlier owner; both of phase 4's helpers are deleted** from its Creates list, its Files table, its Rollback and its steps. `lab control` and the `lab run` annotation now call the same `format_report`, so they cannot drift on one arm, and D17's message is composed from `describe(f)` — which already prints `--` for a missing ratio, so `_shape_cell` had nothing to do. One fewer symbol in `hardgate.py` is also one less surface for the `force` word ban. |
| 16 | **Contract drift inside phase 4's own D17 text.** It said `M0241-STALE` "reads 1.03/1.01 against `M0241-FRESH20`". Phase 2 classifies `M0241-STALE` as dose-response: verdict `not-checked`, no target, no ratios at all. | 4 | The paragraph rewritten to say what the module does — both dose arms carry `not-checked` and hold no ratio — and to name the load-bearing ordering (dose is tested **before** draw, because `M0241-STALE`'s rationale contains the word "control"). |
| 17 | **Requirement creep.** Phase 4's **Satisfies** said R2, but its Step 10 runs `lab shortfall 828` and writes the backtest note — which is R1's acceptance test ("a decomposition command exists **and is run on trial 828**"). | 1, 4, index | **The id follows the work.** The step cannot move to phase 1, because the same document carries the `lab control` table, which does not exist until phases 2 and 4 land. So R1 is split by the work: phase 1 **Satisfies R1** (the command), phase 4 **Satisfies R1, R2** (the written run). Both plan files' Satisfies lines and the index's Requirements table and phase table say so. |
| 18 | **An exit criterion that cannot hold.** Phase 2's exit criterion 1 required `git status --porcelain` to show exactly its two new files — but phase 1 runs concurrently in the same worktree and its files will be in that output. | 1, 2 | Narrowed to `git status --porcelain <the two paths>` plus an empty `lab/lab.sqlite web/data/`, with "do not assert on a bare `git status --porcelain`" and the commit-by-pathspec rule spelled out. |
| 19 | **A piped `lab` command reading `$?`.** Phase 4's build check ran `lab --help \| grep -c control` — the filter owns the status, which is the exact mechanism behind the bug phase 3 fixes. | 4 | Rewritten to redirect to a file and echo the command's own `$?`, with the reason. |
| 20 | **Gap sweep against the analysis document's Impact Points and Reference List.** | all | **No gaps.** All twelve impact points are owned (1-3 phase 1, 4-5 phase 2, 6-8 phase 3, 9-12 phase 4) and every Reference-List symbol is either read by an owning phase or explicitly left alone (`_comparability_warnings` and `_show` are named in phase 1's Handoffs as deliberately untouched). No symbol is deleted by any phase, so there is no deleted-then-used case anywhere in the set. Every phase builds green on its own: phases 1, 2 and 3 are additive and independent, and phase 4's only new import is of phase 2's module, which lands first. |

## Decisions

Every fork that survived reconciliation, settled here rather than passed to four phase sessions who
would each have settled it differently. The rung is the highest one that spoke, on the ladder every
executor carries: **1** stated invariant · **2** phase scope and exit criteria · **3** the plan's
code blocks · **4** the index's Why and Requirements · **5** the user's raw input · **6**
surrounding convention.

| Fork | Chosen | Rung |
|---|---|---|
| Phase 4 specified a `control_shape` API before phase 2 built one; the two disagree on every name | Phase 2's real API wins and phase 4's code was rewritten to it — `Finding`/`findings`/`for_method`/`survey`/`refusals`/`flags`/`describe`/`format_report` | 2: the index gives phase 2 sole ownership of `lab/control_shape.py` |
| D17 would refuse nine *dev-eligible* methods (M0047, M0201, M0202, M0208, M0215, M0221, M0225, M0227, M0243), far beyond the two the handover named | Accept the nine — a handicapped control makes "it beat its control by X" unsound, and refusing it is the feature. **But the refusal must name the way back**: re-draw the control at the book's own trade count and turnover, recorded as an amendment, costing no method id | 5: "refuses or loudly flags a mismatch"; and the brief's "a mismatched control arm fails loudly" |
| "Refuse or loudly flag" — at which moment? | `lab run` **annotates and does not refuse**; `lab promote` refuses. The run must complete so the lab can bootstrap, and a run-time gate would only spend method ids to say what the promotion gate already says | 6: the lab's own written decision D15 |
| The user named four terms — gate, fees, **pool**, residual weighting — but one trial row cannot separate pool from weighting | Report **one** combined `pool + weighting` residual by default; split it only when `--against` names a sibling that shares the pool. Measured on trial 828: −0.87 total, of which −0.39 is shared pool/frame and **−0.48 this arm's own weighting** | 5, read against what is computable: a fabricated split would be the exact failure the brief exists to stop |
| Should `lab shortfall` journal an observation, as `lab costs`/`exposure`/`gate` do? | No. It writes nothing, like `lab regime`, `lab walkforward`, `lab kin` and `lab turnover` — its nearest neighbours and the same report shape. `web/data/lab.json` never moves and no phase calls `lab stage` | 6: the shape-(A) convention |
| Era exposure: the recorded whole-window figure, or the era's own? | Era-resolved whenever `--store` is given and the candidate carries the shared gate, via the lab's own `f_factor.trend_on`; the whole-window fallback is **labelled in the output every time**. This is load-bearing, not polish: the residual is −0.87 era-resolved and flips sign to **+0.65** without it | 1: invariant 10, one measurement path; and the measurement itself |
| An escape hatch for a deliberate identical `lab note` re-append? | None. The lab's refusals are not flag-skippable | 6: `hardgate.py`'s "There is no override path, in any form" |
| Should any phase add the `controls` field to `backtest.dev.Candidate`? | No. Phase 2 reads it duck-typed and `dev.py` is left alone. The field is verified safe (all 37 construction sites are keyword-only, and `config_text` reads only rules/allocator.id/params) but adding it buys nothing in this set, because no *existing* method file may be edited to use it | 1: invariants 4 and 5 |
| The brief's "Done means" asks for the 8.2 to be retired in the memory note, insight 461 and the `/sera` page | **State, do not apply.** `insights` is append-only, `/sera` runs through `update-stale-sera-methods-page`, and `MEMORY.md` is the owner's file. Phase 4's backtest note carries all three corrections with exact replacement text, ready to apply in one sitting | 4: the index's Scope; the acts are owner-visible and outside an unattended run |
| The fee term's name count is a guess (`names_in` resolves 686 of 824 dev rows, and is confidently wrong on two) | Derive it, **label the derivation a guess, and print a 10/20/30/50 sensitivity band beside it**. Measured: trial 828's fee drag moves only 3.71 → 3.85 pts/yr across that whole range, so the guess cannot change a verdict | 3: measured in phase 1's own worked example |
| Three phases edit `commands/lab.py`, which would lose work if edited concurrently in one shared worktree | Serialise 1 → 3 → 4 by `Depends on`, and require every anchor to be **quoted text, not a line number**. Phases 1 and 2 still run concurrently | 1: the shared-worktree constraint |

## Open Questions

**None.** Every fork was decidable from the ladder and is recorded under Decisions above, so this
plan set launches unattended.

## Rollback

Per phase: `git revert` the phase's commit. Every phase is additive — two new modules, two new
report subcommands, one new refusal and one new gate clause — and no phase edits a recorded row, a
method file or a frozen record, so a revert restores the previous behaviour exactly.

As a whole: delete the branch and the worktree. Nothing outside the worktree is written by any
phase; `lab/lab.sqlite` is never committed, `web/data/lab.json` never moves, and no insight, trial
or status is recorded anywhere.

The one irreversible act in the whole plan would be a `lab note` that lands a duplicate — which is
what phase 3 exists to make impossible, and which no phase performs.

## Next

Execute the phases one at a time, starting at phase 1:

    /implement -f docs/plans/LAB_SHORTFALL_AND_CONTROL_SHAPE_PLAN.md --phase 1

Or run the whole set as a swarm — a session per phase, concurrent wherever `Depends on` allows,
resumable on any machine:

    /analyze-orchestrator -f docs/plans/LAB_SHORTFALL_AND_CONTROL_SHAPE_PLAN.md

Or put them on the board first (GitHub repos only):

    /create-task --from-plan docs/plans/LAB_SHORTFALL_AND_CONTROL_SHAPE_PLAN.md

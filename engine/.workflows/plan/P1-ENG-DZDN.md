> Adopted from `/home/miftah/seer/.workflows/orchestration/lab-shortfall-and-control-shape/PLAN.md` phase 4. Source: `.workflows/plan/lab-shortfall-and-control-shape/phase-4.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 4: `lab control`, the `lab run` annotation, and hard gate D17

**Plan set:** `LAB_SHORTFALL_AND_CONTROL_SHAPE_PLAN.md`
**Analysis:** `docs/analyzer/20261019-110502-S4KQ_code_analyzer.md`
**Satisfies:** **R2** — a control-shape check that refuses or loudly flags a mismatch, bound at
every moment a researcher could act on a mis-shaped control; **and the acceptance half of R1** —
the brief's "a decomposition command exists **and is run on trial 828**", which is Step 10's run
and `docs/backtests/2026-10-19-trial-828-shortfall.md`. Phase 1 builds R1; this phase runs it on
828 and writes down what it retires. The id follows the work: it is not a widening to legalise a
step, and the step cannot move to phase 1 because the same document carries the `lab control`
table, which does not exist until phase 2 and this phase have landed.
**Depends on:** Phase 2 (the module this phase is the only caller of), Phase 3 (file serialisation
on `commands/lab.py` only — no semantic dependency)
**Difficulty:** HARD
**Package:** `engine/seer_engine/lab` + `engine/seer_engine/commands`

---

## Goal

After this phase, a control arm that does not have the shape of the book it controls is visible at
`lab control`, loud at `lab run`, and refused at `lab promote`. The lab can no longer publish a
sentence of the form "the signal beat its blind draw by X points" without the arithmetic that says
whether the blind draw was handicapped. And `docs/backtests/2026-10-19-trial-828-shortfall.md`
records the run that either retires or confirms the published "8.2 pt equal-weight handicap",
naming the exact replacement numbers for the three places it is published.

---

## Interface Contract

The reconciler reads this section to detect cross-phase conflicts. Be exact and exhaustive.

**Creates:**
- `commands.lab._control` (`engine/src/seer_engine/commands/lab.py`) — the `lab control` handler
- `commands.lab` `control` subparser + `_HANDLERS["control"]` entry
- the control-shape annotation block inside `commands.lab._run`
- `hardgate.mis_shaped_controls(conn, method_id) -> tuple` (`engine/src/seer_engine/lab/hardgate.py`)
- `hardgate.__doc__` gains decision **(D17)**
- `docs/backtests/2026-10-19-trial-828-shortfall.md` (new file)
- `engine/tests/test_lab_hardgate.py` gains `_Arm`, `_declare`, `_control_arm` and nine tests

**Signature changes:** none. `hardgate.check(conn, method_id) -> None` keeps its signature and
gains one clause.

**Deletes:** none.
**Renames:** none.

**Requires (from Phase 2) — `engine/src/seer_engine/lab/control_shape.py`.** This phase is the
module's only caller, so this list is the whole of the coupling. **Phase 2 owns the module and its
API is final; every name below is quoted from phase 2's finished contract, not assumed.**

```python
# The three entry points. `survey` and `for_method` read a method's arms from its method FILE
# through `method.discover()`; `findings` takes the arms explicitly.
def findings(conn, method_id: str, arms: Sequence[Arm]) -> tuple[Finding, ...]: ...
def for_method(conn, method_id: str) -> tuple[Finding, ...]: ...        # () when no method file
def survey(conn, method_ids: Sequence[str] | None = None) -> tuple[Finding, ...]: ...

# The value. NOTE: `Shape` is a SMALL record (candidate_id, n, trades, turnover) held INSIDE a
# Finding -- it is not the rich object, and `shapes()` is an internal dict reader, not an entry
# point. Do not call `shapes()` from this phase.
@dataclass(frozen=True, slots=True)
class Finding:
    method_id: str              # "M0248"
    control_id: str             # "M0248-R"        -- the control arm
    kind: str                   # KIND_PLACEBO / KIND_DOSE / KIND_ABLATION / KIND_NONE
    target_id: str | None       # "M0248-EQ"       -- the arm it controls; None if unresolved
    rung: str | None            # RUNG_DECLARED / RUNG_STEM / RUNG_IDEA / RUNG_FIRST
    control: Shape | None
    target: Shape | None
    trade_ratio: float | None   # control trades / target trades;  None when either is missing
    turnover_ratio: float | None
    verdict: str                # OK / WARN / REFUSE / UNRESOLVED / UNRECORDED / NOT_CHECKED
    reason: str                 # one plain sentence
    @property
    def refused(self) -> bool: ...     # verdict == REFUSE, and only that
    @property
    def flagged(self) -> bool: ...     # verdict in (WARN, REFUSE)

# Filters and text. The module PRINTS NOTHING and RAISES NOTHING.
def refusals(found: Iterable[Finding]) -> tuple[Finding, ...]
def flags(found: Iterable[Finding]) -> tuple[Finding, ...]
def describe(f: Finding) -> str          # "M0248-R (against M0248-EQ, resolved by declared-idea): ..."
def band_sentence() -> str
def format_report(found: Sequence[Finding], *, show_clean: bool = True) -> str

# Constants:
OK = "ok"; WARN = "warn"; REFUSE = "refuse"
UNRESOLVED = "unresolved"; UNRECORDED = "unrecorded"; NOT_CHECKED = "not-checked"
WARN_BAND = (0.8, 1.25)
REFUSE_BAND = (0.5, 2.0)
KIND_PLACEBO = "placebo"; KIND_DOSE = "dose-response"
KIND_ABLATION = "within-frame control"; KIND_NONE = ""
RUNG_DECLARED = "declared"; RUNG_STEM = "sibling-stem"
RUNG_IDEA = "declared-idea"; RUNG_FIRST = "first-declared"
DECLARATION_ATTR = "controls"
```

**The wiring recipe, which is phase 2's own and which this phase follows exactly:**

| binding | call |
|---|---|
| `lab control` | `survey(conn)` or `survey(conn, ["M0248"])`, then `format_report(found)` |
| `lab run` | `for_method(conn, mid)`, then `format_report(found, show_clean=False)` and `flags(found)` |
| hard gate D17 | `refusals(for_method(conn, mid))`, then `describe(f)` for the message |

Four things about phase 2's module this phase depends on, stated because they are what the
reconciler settled and they are not obvious from phase 2's exit criteria:

1. **Nothing in it prints, and nothing in it raises.** There is no `LabError` to catch and no
   message to inherit. Every uncertainty comes back as a verdict — `UNRESOLVED` (no arm to compare
   against), `UNRECORDED` (no recorded trial, or no measurable denominator), `NOT_CHECKED` (a dose
   or ablation arm). **Only `REFUSE` refuses.** Every word of every refusal message below is this
   phase's to compose, out of `describe()`.
2. **Detection is by the candidate's `rationale`, never by its id suffix.** `M0005-ALL-R` has a
   `-R` and is a rank-weighting variant, not a control; phase 2 correctly produces no finding for
   it. Any arm this phase's **tests** invent must therefore carry real control prose
   (`"Placebo: ... hash-drawn ..."`), and the arm it controls must carry `"The idea:"` or
   `"The yardstick:"` for the resolution to be deterministic.
3. **`for_method` reads the method FILE.** It returns `()` when no `lab/methods/mNNNN_*.py`
   declares the id. This is right in `check` — a real method has a file — and it is the reason
   this phase's tests need a seam (Step 9, and Conflict 2 in the plan index's Reconciliation Log).
4. **`control_shape` does not import `hardgate`.** This phase imports `control_shape` from inside
   function bodies, not at module scope, so no cycle can form in either direction.

**Requires (from Phase 1):** `lab shortfall` exists and takes `<n|candidate_id> [--era ERA]
[--store DIR] [--against CANDIDATE]`. This phase **runs** it to produce the backtest note; it does
not import `lab/shortfall.py`.

**Requires (from Phase 3):** nothing semantically. Phase 3 edits `commands/lab.py:_note` and
`lab/store.py:append_analysis`; this phase re-reads `commands/lab.py` before quoting it.

**Leaves alone (owned by others):**
- `engine/src/seer_engine/lab/control_shape.py` and `engine/tests/test_lab_control_shape.py` (Phase 2)
- `engine/src/seer_engine/lab/shortfall.py` and `engine/tests/test_lab_shortfall.py` (Phase 1)
- `engine/src/seer_engine/lab/store.py`, `commands/lab.py:_note`, `engine/tests/test_lab_store.py` (Phase 3)
- the `shortfall` subparser and its `_HANDLERS` entry (Phase 1)
- every `lab/methods/mNNNN_*.py`, every recorded `lab.sqlite` row, `backtest/registry.py`, `web/`

---

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/commands/lab.py` | modify | module docstring command list (after the `lab gate` entry, ~:95); the `control` subparser (after the `gate` parser's last `--csv`, ~:595); the `_control` handler (after `_kin`, ~:2586); the control-shape annotation inside `_run` (after the walk-forward block, ~:1628); `_HANDLERS["control"]` (after `"gate": _gate,`, ~:2884) |
| `engine/src/seer_engine/lab/hardgate.py` | modify | decision **(D17)** appended to the module docstring (before the closing `"""` at :522); `mis_shaped_controls` (new, after `benchmark_n` at :726); the D17 clause inside `check` (after the `if candidate is not None:` block, before `bad = failed_kin(...)`, ~:1654) |
| `engine/tests/test_lab_hardgate.py` | modify | one import, an `_Arm` stub, a `_declare` seam, a `_control_arm` fixture and nine tests, appended as a new `(D17)` section |
| `docs/backtests/2026-10-19-trial-828-shortfall.md` | **new** | the trial-828 decomposition, the control table, and the three corrections |

**Line numbers above are at base `ad8792d`.** Phases 1 and 3 land in `commands/lab.py` before this
phase does, so every number in that row will have moved. **Re-read `commands/lab.py` before quoting
it**; every anchor below is given as a quoted line of surrounding text, not a number, for exactly
that reason.

**The file collision is serialised and the regions do not overlap** — checked by the reconciler
against the file at `ad8792d`:

| phase | what it inserts into `commands/lab.py` | where |
|---|---|---|
| 1 | a `shortfall` subparser | between the `walkforward` parser (ends `:441`) and the `survivorship` parser (`:442`) |
| 1 | `_shortfall` | after `_walkforward` (`:2352`) |
| 1 | `"shortfall": _shortfall,` | in `_HANDLERS` (`:2867`), between `"walkforward"` and `"luck"` |
| 3 | `_note` rewritten in place | `:2741`, body only |
| 4 | a `control` subparser | between the `gate` parser's last `--csv` (`:594`) and `s = sub.add_parser("idea", ...)` (`:597`) |
| 4 | `_control` | after `_kin` (`:2531`) and before `def _exposure(conn, args) -> int:` (`:2590`) |
| 4 | `"control": _control,` | in `_HANDLERS`, after `"gate": _gate,` (`:2884`) |
| 4 | the annotation block | inside `_run` (`:1546`), after the `"  Folds share training data, ..."` print (`:1625-1628`) and before `if amendment is not None:` |

No two insertion points touch the same region, and phase 3 changes only `_note`'s body, which
nothing here quotes. Every anchor in the steps below is quoted text.

---

## Implementation Steps

### Step 1: `hardgate` decision (D17), in the module docstring

**File:** `engine/src/seer_engine/lab/hardgate.py` — append immediately **before** the closing
`"""` on line 522, i.e. after D16's last sentence (`...so the fuller history is better evidence,
not true evidence.`).

**Change:** the lab's design record gains its seventeenth decision, in D10-D16's register: the
question as a heading, the answer, the measurement, the limits.

**⚠ A WORD BAN APPLIES TO THIS FILE.** `test_there_is_no_override` (`test_lab_hardgate.py:668`)
greps the whole of `hardgate`'s source for the substrings `force`, `override`, `skip_gate`,
`SEER_SKIP`, `getenv`, `environ`, after stripping only the two literals `"no override"` and
`"There is no override"`. **`enforce`, `enforced`, `enforcement` and `reinforce` all contain
`force` and will turn that test red.** The text below is written clear of them. Do not paraphrase
it with "enforce".

**Code:**

```
**(D17) Does the gate check that a method's control arm has the shape of the book it controls?
-- Yes, and from 2026-10-19 ``check`` REFUSES a method whose control arm is measured outside the
band.**

A control arm is the book's shape with none of its identity: the same number of names, drawn from
the same pool, re-picked on the same calendar, chosen at random or by a scrambled key instead of
by the signal. Every sentence of the form "the signal beat its blind draw by X points" is a
subtraction, and a subtraction is only as good as the thing subtracted. When the control trades
three times as often as the book it controls, X carries the fees and the churn the control paid
and the book did not, and nobody can say how much of it.

Two recorded cases, and seventeen nobody had noticed. Each control is measured against **the arm
it controls**, which ``control_shape``'s resolution ladder finds and names:

    control             the arm it controls      resolved by      trades x   tov x
    M0230-C50-R         M0230-C50                sibling-stem        0.067   0.138
    M0222-RAND1         M0222-CORE               declared-idea       0.984   4.451
    M0226-RAND1         M0226-CORE               declared-idea       0.979   6.934
    M0222-RAND2         M0222-CORE               declared-idea       1.063   8.856
    M0226-RAND2         M0226-CORE               declared-idea       1.330  14.528
    M0243-NEAR20-R      M0243-NEAR20             sibling-stem        3.013   2.976
    M0248-R             M0248-EQ                 declared-idea       3.180   3.078

M0248's is the case the 2026-10-19 handover was written about: its blind draw trades 3.18x and
turns over 3.08x the arm it controls, and the sentence then standing in the record read "all six
arms beat the blind draw by 3.6 to 13.5 points, so the buyback signal itself is real". The gap is
probably still real; the margin was quoted against a handicapped opponent and is overstated by
something like one and a half to three points a year. M0230's is the opposite handicap -- a
control that barely trades at all, 0.067x -- and the lab already wrote the habit down after it
(``seer-placebo-sticky-vs-redrawn``: "line the trade counts of all arms up against each other").
M0243's was found by turning that habit into a measurement and running it over every recorded arm,
which is the ordinary return on writing a rule down. Over all 46 placebo arms the lab holds, the
measured tally is **19 refuse, 7 warn, 4 clean, 16 with no arm to compare against**.

**Both axes, always.** ``M0226-RAND2`` sits within 1.33x of its sibling on trades and 14.53x on
turnover -- about the same number of orders, a fifteen-times-bigger book moved through them. A
trade-count check alone reads it as clean. This rule therefore refuses on the trade ratio OR the
turnover ratio, and an arm that has only one of the two is judged on the one it has.

**The band is calibrated on the lab's own control arms, not chosen.** Measured over every recorded
dev candidate on 2026-10-19, each against the arm the ladder resolves for it: the clean arms sit
at 0.98-1.02 on both axes, and every handicapped one is at 2.976x or worse, or 0.138x or less, on
at least one. ``control_shape.WARN_BAND`` is 0.80x..1.25x and ``control_shape.REFUSE_BAND`` is
0.50x..2.00x; both are log-symmetric (1.25 = 1/0.80, 2.00 = 1/0.50), because trading twice as much
and half as much are the same sin. The bar sits in the gap between 1.372 (``M0241-PLACEBO``, the
single arm that warns and does not refuse) and 2.976, and it is not moved from inside the code.

**A dose-response arm is not a control.** ``M0244-STALE30`` trades about a fifth as often as the
arm beside it, and that is *supposed* to be true: the stale signal date is the dose, and trading a
fifth as often is the treatment rather than a handicap. ``M0241-STALE`` is the same shape of arm,
and its rationale even carries the word "control" ("the dose-response control on the date
itself"), which is why ``control_shape`` tests for a dose **before** it tests for a draw. Both are
classified dose-response, carry the verdict ``not-checked``, hold no ratio at all, and this rule
never reads them. A permanent false alarm on a correct arm is how a rule gets switched off.

**The way back, and why the refusal names it.** A control is not a verdict on the signal; it is
a measuring stick, and a bent stick can be straightened. Re-draw the control at the book's own
trade count and turnover and run it again. That costs **no method id** -- an amendment appends
trials under the method's existing id -- and it is exactly what the 2026-10-19 handover asks for
on M0248 (§2). A refusal that named no way back would be a dead end, and this rule meets nine
methods that need one, so the message says it and so does this paragraph.

**What it does not do.** It does not refuse a method with no control arm -- most of the lab has
none, and the rule makes no claim about a book nobody drew a control for. It does not refuse a
method whose control shape cannot be read: an arm with no resolvable sibling, a row carrying
neither a trade count nor a turnover, an arm whose own trial was never recorded. Those come back
as ``unresolved`` or ``unrecorded`` and are left to the other clauses, because absence is not
evidence -- the same sentence (D16) writes about the survivorship grid. Only a measured
``refuse`` refuses. It does not touch a recorded row, move a recorded ``trades`` or ``turnover``,
or re-open a closed verdict. And it does not reach into ``lab run``: at run time the same reading
is printed beside the fold verdict and nothing is refused, for (D15)'s reason exactly -- a second
gate at run time would only spend method ids to say what this one already says, and a fresh lab
has to be able to run before it has anything to compare.

**Who it stops today, measured.** ``lab status`` reads ``Promotable now:`` M0072, M0092 and
M0197, and none of the three holds a control arm at all, so **the promotable set does not move**.
But *dev-eligible* is a wider set than *promotable now*, and **nine dev-eligible methods hold a
control arm in the refuse band and would be stopped here if they reached it**: M0047, M0201,
M0202, M0208, M0215, M0221, M0225, M0227 and M0243. The arms named in the table above belong to
M0222, M0226, M0230 and M0248, all four already rejected, so those four change nothing either
way; M0241 is dev-eligible and warns rather than refuses.

Those nine are not an accident of the band and they are not collateral. They are the rule working:
each of them quotes, or could quote, "this beat its control by X" against a control that was not
the shape of the book. The lab had already written that rule down twice in its own memory and had
no mechanism to apply it. Each of the nine has the same way back as M0248 -- re-draw the control
at the book's own turnover and amend, no method id spent. As with (D12) and (D14), the real point
is forward: the next method to draw a handicapped control and quote the margin against it is
stopped before a look is spent, rather than after the sentence is published.
```

**Impact:** documentation only. Nothing executes. `test_the_module_answers_the_four_open_questions`
and its siblings read `hardgate.__doc__`; adding text cannot break them.

---

### Step 2: `hardgate.mis_shaped_controls`

**File:** `engine/src/seer_engine/lab/hardgate.py` — insert immediately **after** `benchmark_n`
(`:726`, the function that ends just before `def mismatches(`), so it sits with the other small
readers the gate composes.

**Change:** one reader that turns Phase 2's module into the list the gate refuses on, and that
*cannot raise*. This is the whole of the D16 "absence is not evidence" register, and it is also the
answer to the danger this phase carries: a clause that raises on an unreadable row would make every
such method unpromotable overnight.

**Written against Phase 2's finished API.** `control_shape.for_method` returns a tuple of
`Finding`, `()` when no method file declares the id; `control_shape.refusals` keeps only the
measured mismatches outside the refuse band. Phase 2's module raises nothing of its own, so the
`except` below guards the one thing that still can — `method.discover()`, which `for_method` calls
and which raises on a malformed method file. A broken method file is somebody else's refusal, not
this clause's.

**Code:**

```python
def mis_shaped_controls(conn: sqlite3.Connection, method_id: str) -> tuple:
    """Every control arm of ``method_id`` whose shape is outside the refuse band (D17).

    Returns a tuple of ``control_shape.Finding`` in the method's own declaration order, and
    **never raises**. A control arm whose shape cannot be read at all -- no arm the id stems to
    and none that names itself the idea, a row carrying neither a trade count nor a turnover, a
    method with no file to read its arms from -- comes back from the reader as ``unresolved`` or
    ``unrecorded``, never as ``refuse``, and is not evidence of a handicap. Refusing a promotion
    on a number nobody computed is the mechanism by which a rule stops being about the thing it
    was written for. The same sentence is (D16)'s about the survivorship grid: absence is not
    evidence.

    ``control_shape`` is imported inside the body, not at this module's scope. It reads recorded
    ``trials`` rows and nothing else today, so a module-level import would work -- and would make
    the next edit to either module a fifty-fifty bet on an import cycle, exactly as ``Run``'s
    docstring in ``lab/runner.py`` says about this module. One dictionary lookup per promotion is
    the price.

    ``for_method`` reads the method's arms from its ``lab/methods/mNNNN_*.py`` file, which is the
    right reader here: a method with no file cannot be promoted at all -- ``prereg`` refuses it on
    the source sha long before anything reaches this clause.
    """
    from seer_engine.lab import control_shape

    try:
        found = control_shape.for_method(conn, method_id)
    except store.LabError:
        return ()
    return control_shape.refusals(found)
```

**Impact:** a new pure reader. Nothing calls it until Step 3.

---

### Step 3: the D17 clause inside `hardgate.check`

**File:** `engine/src/seer_engine/lab/hardgate.py` — inside `check` (`:1566`), **after** the
`if candidate is not None:` block closes (the last statement in it is the `survivorship_record`
refusal, which ends `...argue for it in the commit"\n            )`) and **before** the line
`    bad = failed_kin(conn, method_id)`.

**Why there.** `check`'s own docstring sets the order: "(F) is a statement about *this* method's
own evidence, which is what the researcher asked about; (K) is about the company it keeps, and
reads better second." A handicapped control is a statement about this method's own evidence — the
margin it would quote is its own — so it belongs on the (F) side of that line, after the variant's
record and before the kin.

**Change:** the gate's seventh refusal.

**The message is composed from `control_shape.describe(f)`,** which already reads
`"M0248-R (against M0248-EQ, resolved by declared-idea): trades 3.18x and turns over 3.08x the arm
it controls, outside the 0.50-2.00 band: the control carries a different cost and a different
cadence, so the gap between them is not evidence about the signal"`. Both ratios, both ids, the
rung and the band are therefore in the refusal without this module formatting a single number —
which is also why no `_shape_cell` helper is needed: `describe` prints `--` for a missing ratio
itself.

**⚠ THE WORD BAN APPLIES HERE TOO.** Nothing added to `hardgate.py` may contain `force`,
`override` (outside the two sanctioned literals), `skip_gate`, `SEER_SKIP`, `getenv` or `environ`.
`enforce`/`enforced`/`enforcement`/`reinforce` all contain `force`. The text below is clear of
them; do not paraphrase it with "enforce".

**Code:** insert exactly this, at four-space indentation inside `check`:

```python
    # (D17) A control arm exists to be the book's shape with none of its identity, so a margin
    # measured against a control that traded three times as often is partly fees and churn. The
    # reader never raises and only a measured mismatch refuses: a shape nobody could read comes
    # back `unresolved` or `unrecorded` and is left to the clauses below, because absence is not
    # evidence (D16). `lab run` prints this same reading and refuses nothing (D15).
    off_shape = mis_shaped_controls(conn, method_id)
    if off_shape:
        from seer_engine.lab import control_shape

        low, high = control_shape.REFUSE_BAND
        said = "; ".join(control_shape.describe(f) for f in off_shape)
        raise store.LabError(
            f"{method_id} is not promoted: {said}. The band is {low:.2f}x to {high:.2f}x on both "
            f"axes, calibrated on every control arm the lab holds (D17). A control is the book's "
            f"shape with none of its identity, so 'this method beat its control by X' is not "
            f"sound when the control was handicapped -- part of X is the fees and the churn the "
            f"control paid and the book did not, and no one can say how much. The way back: "
            f"re-draw the control at the book's own trade count and turnover and run it again as "
            f"an amendment. That costs no method id, because an amendment appends trials under "
            f"this id, and it is what the 2026-10-19 handover asks for on M0248. Nothing was "
            f"written and no status moved. There is no override -- if the rule is wrong, change "
            f"it in seer_engine/lab/hardgate.py and argue for it in the commit"
        )
```

**Impact — and this is the phase's one real risk.** `check` governs promotion for every method in
the lab, and this clause additionally makes every promotion read the method's own file through
`control_shape.for_method` → `method.discover()`. That import of all 271 method modules already
happens on the `lab promote` path (`prereg` reads the source sha), so it is a lookup rather than a
new cost. Verification below runs `lab status` before and after.

**THE RECONCILED FACT about who this stops — state it this way and no other way, in this plan, in
the D17 prose, in the backtest note and in the phase report:**

> **`Promotable now:` is unchanged by D17, AND nine dev-eligible methods would be refused at
> `lab promote` if they ever reached it.**

Both halves are measured and both are true, because *dev-eligible* is a wider set than *promotable
now*. Measured at `ad8792d` on 2026-10-19 against the committed `lab/lab.sqlite`:

- **`Promotable now:` is `M0072, M0092, M0197`**, and none of the three has a control, placebo or
  random arm (`M0072-Z2/-Z3/-Z2-RAWRANK/-Z3-NOFLOOR`; `M0092-DV-CAP10/-SQRT-CAP10/-TOP100-EW`;
  `M0197-Y20/-Y20-SW/-Y20-OPP/-Y20-OPP-SW/-N20/-N20-SW`). The promotable set does not move.
- **Nine dev-eligible methods hold a control arm in the refuse band** and would be refused here:
  **M0047, M0201, M0202, M0208, M0215, M0221, M0225, M0227, M0243** (Phase 2 measured this over
  all 46 placebo arms: 19 refuse, 7 warn, 4 clean, 16 unresolved). M0222, M0226, M0230 and M0248
  are already `rejected`. M0241 is dev-eligible and warn-only.

**That is the intended, settled outcome — it is the point of the feature, not a defect, and no
phase re-opens it.** It is recorded in the plan index's Decisions with its rung. What follows from
it is the requirement above: the refusal and the D17 prose must both name the way back.

---

### Step 4: the `control` subparser

**File:** `engine/src/seer_engine/commands/lab.py` — insert between the `gate` subparser's final
`s.add_argument("--csv", ...)` and the line `    s = sub.add_parser("idea", help="queue an idea in
the backlog")`.

**Change:** the report's CLI surface. Note the `%`-escaping comment: it is copied verbatim from the
`gate` parser above it, and it is a lab invariant, not a style choice.

**Code:**

```python
    s = sub.add_parser(
        "control",
        # No literal `%` in any `help=` string below, and none may be added: argparse runs every
        # `help=` through %-interpolation (HelpFormatter._expand_help), so a bare `%` is read as a
        # format spec and `lab --help` dies. A doubled `%%` renders as one `%`. `description=` is
        # NOT interpolated and must stay single. See the `gate` parser above.
        help="report only: whether each control arm trades like the arm it controls",
        description=(
            "A control arm exists to be the real book's shape with none of its identity, so "
            "'the signal beat its control by X' is only sound when the two traded about as often "
            "and turned the book over about as fast. This prints every control, placebo and "
            "blind-draw arm the lab holds beside the arm it controls, as a trade-count ratio and "
            "a turnover ratio, and says whether each is clean, worth a warning, or outside the "
            "band the hard gate refuses on (lab/hardgate.py, D17). Both axes are mandatory: one "
            "recorded arm sits within 1.33x of its sibling on trades and 14.5x on turnover, so a "
            "trade-count check alone reads it as clean. A dose-response arm -- one whose "
            "different shape IS the treatment, like a deliberately stale signal date -- is listed "
            "as such and never flagged. Pure arithmetic over recorded trial rows: no research "
            "store is opened, no backtest runs, and no trial row, moments row, funding row, "
            "status or journal entry is written, so the lab's N and the test-window looks cannot "
            "move, web/data/lab.json does not change and `lab stage` is not needed."
        ),
    )
    s.add_argument("method", nargs="*", metavar="M0248",
                   help="methods to report (default: every method that has a control arm)")
```

**Note:** `description=` above is not %-interpolated, so its single `%` characters (there are
none today) would be safe; `help=` is, so neither `help=` string may ever gain a literal `%`.

**Impact:** `lab control --help` renders. `lab control` itself still fails until Step 6 adds the
handler to `_HANDLERS`.

---

### Step 5: the module docstring's command list

**File:** `engine/src/seer_engine/commands/lab.py` — insert after the `lab gate ...` entry (which
ends `...moments, no status change: N and the looks do not move`) and before
`    lab idea --name ... --hypothesis ...`.

**Code:**

```
    lab control [M0248 ...]         report only: whether each control, placebo or blind-draw arm
                                    has the shape of the arm it controls -- its trade count and
                                    its turnover as ratios -- so a margin quoted against it is
                                    sound. Arithmetic over recorded trial rows: no research store,
                                    no backtest, no method file read. A dose-response arm, whose
                                    different shape is the treatment, is listed and never flagged.
                                    The refuse half of the band is what `lab promote` refuses on
                                    (lab/hardgate.py, D17); `lab run` prints the same reading and
                                    refuses nothing (D15). No trial row, no moments, no status
                                    change: N and the looks do not move
```

**Impact:** documentation only.

---

### Step 6: `_control`

**File:** `engine/src/seer_engine/commands/lab.py` — insert immediately after `_kin` ends (its last
statements are the `print(f"recorded dev trials ...")` block and `return 0`) and before
`def _exposure(conn, args) -> int:`.

**Change:** the report, modelled on `_kin` — the closest shape-(A) sibling that opens no store at
all.

**Phase 2 owns the table.** `control_shape.format_report(found)` already prints the band sentence,
the aligned table (method, control, kind, controls, resolved by, trades x, turnover x, verdict)
and a "what to read before quoting a control gap" list under it. The draft of this phase carried
its own `_control_shape_line` formatter written against an API that does not exist; it is **gone**,
and with it the risk that `lab control` and `lab run` print different numbers for the same arm —
both now call the same `format_report`.

**Code:**

```python
def _control(conn, args) -> int:
    """``lab control [M0248 ...]``: does each control arm trade like the arm it controls?

    Report only, in the sense ``lab kin`` is a report: pure arithmetic over recorded trial rows.
    No research store is opened, no backtest runs, no trial is inserted, no status moves and no
    look is spent. N and the test-window looks are printed before and after, so the "nothing was
    recorded" invariant is visible on the terminal rather than merely asserted in a test.

    With no method named it reports every control arm the lab holds -- forty-six placebo arms on
    the committed database, of which nineteen are outside the band, plus the dose-response and
    within-frame arms it lists and never flags. The band it prints is ``control_shape``'s,
    calibrated on this same evidence, and its refuse half is what ``lab promote`` refuses on
    (``hardgate`` D17). ``lab run`` prints the same rows through the same ``format_report`` and
    refuses nothing (``hardgate`` D15), so the three bindings can never disagree about one arm.

    One thing this does read that the rest of the report path does not: ``control_shape.survey``
    reads each method's arms from its ``lab/methods/mNNNN_*.py`` file, because a control arm is
    identified by the one-line ``rationale`` its author wrote and no recorded row carries that.
    It is a read; no method file is written, hashed against, or re-registered.
    """
    from seer_engine.lab import control_shape as cs

    wanted = [m.upper() for m in args.method]
    if wanted:
        known = {
            str(r["method_id"])
            for r in conn.execute("SELECT DISTINCT method_id FROM trials WHERE window = 'dev'")
        }
        missing = sorted(set(wanted) - known)
        if missing:
            raise store.LabError(f"no dev trial for {', '.join(missing)}")

    n_before = store.dev_trial_count(conn)
    looks_before = store.test_looks(conn)

    found = cs.survey(conn, wanted) if wanted else cs.survey(conn)
    print(cs.format_report(found))

    refused = cs.refusals(found)
    if refused:
        low, high = cs.REFUSE_BAND
        print()
        print(f"{len(refused)} control arm(s) sit outside {low:.2f}x..{high:.2f}x on at least one")
        print("axis. `lab promote` refuses a method holding one (lab/hardgate.py, D17), and any")
        print("sentence already written about one of those margins is quoted against a")
        print("handicapped opponent. The way back costs no method id: re-draw the control at the")
        print("book's own trade count and turnover and run it again as an amendment.")

    print()
    print(f"recorded dev trials {n_before} -> {store.dev_trial_count(conn)}; "
          f"test-window looks {looks_before} -> {store.test_looks(conn)}. "
          f"Nothing was written, no research store was opened and no method id was minted.")
    return 0
```

**Impact:** `lab control` becomes a usable report once Step 7 registers it.

---

### Step 7: the dispatch entry

**File:** `engine/src/seer_engine/commands/lab.py` — in `_HANDLERS`, add one line after
`    "gate": _gate,`.

**Change:**

```python
    "gate": _gate,
    "control": _control,
```

**Note for the implementer:** Phase 1 adds `"shortfall": _shortfall` to this same dict. The two
lines are independent; if a merge shows both, keep both.

**Impact:** `lab control` dispatches. Exit codes are the shared ones — `run()`'s `except
store.LabError` turns a refusal into 2.

---

### Step 8: the annotation inside `_run`

**File:** `engine/src/seer_engine/commands/lab.py`, inside `_run`. Insert **after** the
walk-forward block's closing statement —

```python
    print(
        "  Folds share training data, so they are a sanity check, never a significance test, and "
        "nothing here enters a DSR."
    )
```

— and **before** `    if amendment is not None:`.

**Change:** the run prints the same reading the report does, beside the fold verdict and for the
same reason. **It annotates; it does not refuse.** This is (D15) applied verbatim: a run-time gate
"would only spend method ids to say what the first one already says", and "a fresh lab has to be
able to run before it has a benchmark". Every failure mode degrades to one reason line and the run
still returns 0.

**Code:**

```python
    # The run's control-shape reading, printed from the rows that were just recorded (R2, D17).
    # Beside the walk-forward verdict and for the same reason: until now a researcher met this
    # only at `lab promote`, by which time the method id was spent and the dev write-up was often
    # already written.
    #
    # It ANNOTATES; it does not gate (hardgate D15). A second gate at run time would only spend
    # method ids to say what `lab promote` already says, and the lab has to be able to bootstrap.
    # `format_report(..., show_clean=False)` is the shape this wants: a clean control prints one
    # line saying so, and only what must be acted on is listed. It is the same formatter
    # `lab control` and nothing else uses, so the two can never drift on one arm.
    #
    # `control_shape` raises nothing of its own; the guard is for `method.discover()`, which
    # `for_method` calls, and whose failure must not take down a run whose trials are already
    # recorded.
    from seer_engine.lab import control_shape as cs

    try:
        found = cs.for_method(conn, method.id)
    except store.LabError as e:
        print(f"\nControl shape: not read ({e}). The trials above are recorded either way.")
    else:
        if not found:
            print("\nControl shape: this method declares no control or placebo arm, so there is "
                  "nothing to match and nothing is claimed either way.")
        else:
            print("\nControl shape: does each control arm trade like the arm it controls?")
            print(cs.format_report(found, show_clean=False))
            off = cs.refusals(found)
            warned = [f for f in cs.flags(found) if not f.refused]
            if off:
                low, high = cs.REFUSE_BAND
                print(f"  *** {len(off)} control arm(s) outside {low:.2f}x..{high:.2f}x on at "
                      f"least one axis.")
                print("      A sentence of the form 'this beat its control by X' is quoted "
                      "against a handicapped opponent: part")
                print("      of X is the fees and the churn the control paid and this book did "
                      "not. Re-draw the control at")
                print("      this book's own trade count and turnover and amend -- that costs no "
                      "method id. `lab promote` refuses")
                print("      this method until then (lab/hardgate.py, D17); the trials above are "
                      "recorded either way (D15).")
            elif warned:
                print(f"  {len(warned)} control arm(s) outside {cs.WARN_BAND[0]:.2f}x.."
                      f"{cs.WARN_BAND[1]:.2f}x but inside the refuse band -- worth a look before "
                      f"the margin is written up, not a refusal.")
            else:
                print("  Every control arm matches the arm it controls on both axes. A margin "
                      "measured against them is this book's own.")
```

**Impact:** `lab run` prints one extra block and its return value is unchanged. Nothing new can
raise out of `_run`: the only call is wrapped, and `control_shape` is contractually forbidden from
raising anything at all.

**Note on `_run`'s own `discover()`.** `_run` has already called `method.discover()` to find the
method it is running, so `cs.for_method`'s own call is a repeat lookup and not a new import cost.
It also means that in this one place `for_method` is guaranteed to find a file.

---

### Step 9: the tests

**File:** `engine/tests/test_lab_hardgate.py` — add `from dataclasses import dataclass` to the
import block (beside `from decimal import Decimal`), then append a new section at the end of the
file.

**Why here and not in a new module.** This file already hosts the `lab promote` CLI refusals, the
`lab run` CLI tests (`_stub_run`, `_run_args`) and the `lab walkforward` report tests, together
with the `_benchmark` / `_method` / `_variant` fixtures all of the below need. Phase 2 owns
`test_lab_control_shape.py` and pins the calibration table there; this file pins the three
*bindings*.

**THE SEAM, AND WHY THIS ONE — read this before writing a line of the tests.**

`control_shape.for_method` reads a method's arms through `method.discover()`, which walks
`lab/methods/mNNNN_*.py`. **Every fixture in this file builds its method straight into the
database with no method file.** Left alone, two things happen and both are silent:

- for a synthetic id with no file, `discover()` yields nothing, `for_method` returns `()`, and
  **D17 never fires — every test below would pass while testing nothing**;
- `M0001` *is* a real method file (`m0001_momentum_own_vol_scaling.py`), so an unmonkeypatched
  `discover()` would hand `for_method` the real M0001's candidates and judge this file's synthetic
  rows against *their* ids, producing `unrecorded` findings and, again, no refusal.

**The seam chosen: monkeypatch `seer_engine.lab.method.discover`** to return a stub method whose
`all_candidates()` yields stub arms. `for_method` does `from seer_engine.lab.method import
discover` *inside its body*, so the attribute is resolved at call time and the patch takes.

**The seam not chosen, and why:** Phase 2 also exposes `findings(conn, method_id, arms)`, which
takes the arms explicitly and needs no patch. It is not used here because it would exercise Phase
2's module rather than **`hardgate.check`'s own clause, which is the thing this phase added and
the thing under test**. `findings` is the right tool in `test_lab_control_shape.py`, and Phase 2
uses it there.

**The production path is unaffected.** A real method has a file, so `for_method`'s `discover()`
lookup is correct inside `check`; `prereg` refuses a method with no file on its source sha long
before promotion reaches D17, so the `()` branch is never the deciding one in production.

**Detection is by `rationale`, not by id suffix** (phase 2, `M0005-ALL-R`). Every stub arm below
therefore carries the lab's own control prose, and the arm being controlled carries `"The idea:"`
so the resolution rung is deterministically `declared-idea` rather than a positional guess.

**Why `Promotable now:` is verified and not asserted.** A test pinning `M0072, M0092, M0197`
against the committed `lab/lab.sqlite` would go red the moment a parallel Sera session promotes
anything, and the lab's own memory records that tests pinning pre-run DB state are the wrong shape.
It is a verification step (below), recorded in the backtest note.

**Code:**

```python
# ------------------------------------------------------------------ control shape (D17)
#
# The seam these tests turn on: `control_shape.for_method` reads a method's arms from its
# `lab/methods/mNNNN_*.py` file, and every fixture in this module builds its method straight into
# the database with no file. Without `_declare` below, `for_method` returns () for a synthetic id
# -- or, for `M0001`, finds the REAL method file of that name and judges these rows against its
# candidate ids -- and D17 never fires, so every test here would pass while testing nothing.


R_IDEA = "The idea: the twenty strongest names in the pool, equal slots, nothing timed"
R_DRAW = "Placebo: the same frame with 20 hash-drawn names from the same scored pool"
R_DOSE = "the same names one to two years stale and none since: does the date do any work?"
R_PLAIN = "the same book, held a month longer"


@dataclass(frozen=True)
class _Arm:
    """An arm as `control_shape` sees one: an id and the one line of prose its author wrote.

    Detection is by the rationale and never by the id suffix -- `M0005-ALL-R` carries a `-R` and
    is a rank-weighting variant, not a control -- so these strings are load-bearing, not labels.
    """

    id: str
    rationale: str


def _declare(monkeypatch, **by_method: list) -> None:
    """Make `control_shape.for_method` and `survey` see `arms` for each method, with no file.

    See the section header: this is the seam, and it is the only way D17 can fire in this module.
    `for_method` imports `discover` inside its body, so patching the attribute on
    `seer_engine.lab.method` is enough.
    """
    import types
    from pathlib import Path

    from seer_engine.lab import method as method_mod

    files = {
        mid: (types.SimpleNamespace(id=mid, all_candidates=lambda arms=arms: tuple(arms)),
              Path(f"{mid}.py"))
        for mid, arms in by_method.items()
    }
    monkeypatch.setattr(method_mod, "discover", lambda: files)


def _control_arm(conn, mid: str, suffix: str, *, trades: int, turnover: float,
                 annual: float = 0.15) -> None:
    """A recorded control arm of ``mid``: one dev trial carrying a trade count and a turnover.

    The arm it controls is `{mid}-A`, which `_method` records with trades 250 and turnover 1.1.
    """
    with conn:
        ns = store.insert_trials(conn, [_trial(
            method_id=mid, candidate_id=f"{mid}-{suffix}", config_digest=f"d-{mid}-{suffix}",
            trades=trades, turnover=turnover,
            curve_json=_curve(_months(*DEV_SPAN), annual),
        )])
        stamp_provenance(conn, ns, price_fingerprint=SAME_PRICES)


def _with_control(monkeypatch, mid: str = "M0001") -> None:
    """The ordinary shape: one book that names itself the idea, one placebo drawn against it."""
    _declare(monkeypatch, **{mid: [_Arm(f"{mid}-A", R_IDEA), _Arm(f"{mid}-R", R_DRAW)]})


def test_the_module_records_the_control_shape_decision():
    """(D17) is written down where the other sixteen are, with its calibration in it."""
    doc = hardgate.__doc__ or ""
    assert "(D17)" in doc
    assert "M0248-R" in doc and "M0230-C50-R" in doc and "M0243-NEAR20-R" in doc
    assert "dose-response" in doc
    # The two cases the band has to separate, both named in the text.
    assert "M0226-RAND2" in doc and "M0241-PLACEBO" in doc
    # The reconciled fact, both halves, and the way back.
    assert "M0072" in doc and "M0047" in doc
    assert "amendment" in doc


def test_a_mis_shaped_control_refuses_promotion_and_names_both_ratios(conn, monkeypatch):
    """M0248's shape: the blind draw trades about three times the book it controls."""
    from seer_engine.lab import control_shape as cs

    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)                      # M0001-A, 250 trades, turnover 1.1
    _control_arm(conn, "M0001", "R", trades=800, turnover=3.5)
    _with_control(monkeypatch)
    with pytest.raises(store.LabError) as e:
        hardgate.check(conn, "M0001")
    said = str(e.value)
    assert "M0001-R" in said and "M0001-A" in said
    assert "3.20x" in said and "3.18x" in said               # 800/250 and 3.5/1.1
    assert cs.RUNG_IDEA in said                              # describe() names the rung
    assert f"{cs.REFUSE_BAND[0]:.2f}x to {cs.REFUSE_BAND[1]:.2f}x" in said
    assert "D17" in said and "no override" in said
    assert "amendment" in said and "costs no method id" in said   # the way back is named


def test_a_control_handicapped_the_other_way_is_refused_too(conn, monkeypatch):
    """M0230's shape: a control that barely trades at all is just as unusable as one that churns."""
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    _control_arm(conn, "M0001", "R", trades=18, turnover=0.15)
    _with_control(monkeypatch)
    with pytest.raises(store.LabError) as e:
        hardgate.check(conn, "M0001")
    assert "M0001-R" in str(e.value)


def test_a_matched_control_promotes(conn, monkeypatch):
    """M0244-PLACEBO30's shape -- about 1.01x / 0.98x -- is what a control should look like."""
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    _control_arm(conn, "M0001", "R", trades=252, turnover=1.08)
    _with_control(monkeypatch)
    hardgate.check(conn, "M0001")                            # returns: no refusal


def test_a_dose_response_arm_is_never_refused_for_its_shape(conn, monkeypatch):
    """The permanent-false-alarm case. A dose arm trades a fifth as often BY DESIGN."""
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    _control_arm(conn, "M0001", "STALE", trades=50, turnover=0.22)
    _declare(monkeypatch, M0001=[_Arm("M0001-A", R_IDEA), _Arm("M0001-STALE", R_DOSE)])
    hardgate.check(conn, "M0001")                            # not-checked, never refuse


def test_a_method_with_no_control_arm_promotes_exactly_as_before(conn, monkeypatch):
    """Most of the lab draws no control. (D17) makes no claim about a book nobody drew one for."""
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    _variant(conn, "M0001", "B", annual=0.14)
    _declare(monkeypatch, M0001=[_Arm("M0001-A", R_IDEA), _Arm("M0001-B", R_PLAIN)])
    hardgate.check(conn, "M0001")


def test_a_shape_that_cannot_be_read_does_not_refuse(conn, monkeypatch):
    """Absence is not evidence (D16's sentence). Only a measured mismatch refuses.

    Two ways a shape goes unread, both pinned: the reader raising (the `except` in
    `mis_shaped_controls`), and the reader coming back with a verdict that is not `refuse` --
    here `unresolved`, because every arm of the method is itself a placebo and none of them
    controls another.
    """
    from seer_engine.lab import control_shape as cs

    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    _control_arm(conn, "M0001", "R", trades=800, turnover=3.5)

    _declare(monkeypatch, M0001=[_Arm("M0001-A", R_DRAW), _Arm("M0001-R", R_DRAW)])
    found = cs.for_method(conn, "M0001")
    assert {f.verdict for f in found} == {cs.UNRESOLVED}
    assert hardgate.mis_shaped_controls(conn, "M0001") == ()
    hardgate.check(conn, "M0001")                            # and the gate stays silent

    def refuses(*_a, **_k):
        raise store.LabError("cannot resolve what M0001-R controls")

    monkeypatch.setattr(cs, "for_method", refuses)
    assert hardgate.mis_shaped_controls(conn, "M0001") == ()
    hardgate.check(conn, "M0001")


def test_lab_promote_exits_2_and_writes_nothing_on_a_mis_shaped_control(tmp_path, monkeypatch):
    db, prereg_dir = tmp_path / "lab.sqlite", tmp_path / "prereg"
    c = store.connect(db)
    _benchmark(c)
    _method(c, "M0001", annual=0.15)
    _control_arm(c, "M0001", "R", trades=800, turnover=3.5)
    before = db.read_bytes()
    c.close()
    _with_control(monkeypatch)

    assert _cli(tmp_path, db, prereg_dir) == 2
    assert not prereg_dir.exists()
    assert db.read_bytes() == before


def _stub_full_run(monkeypatch, tmp_path, method_id: str, arms: list):
    """`lab run` all the way to its printing, with no method file, no store and no backtest.

    Extends `_stub_run` past the store pin: `preflight_data` returns None and `run_method` hands
    back the attributes `_run` reads off it. The verdict is the reason-carrying kind (D15's own
    bootstrap case), so no fold geometry is needed.

    The stub method carries `all_candidates`, because `_run`'s control-shape block reads the
    method's arms through `control_shape.for_method` -> this same `discover` -- the seam described
    at the top of this section. A bare `SimpleNamespace(id=...)` would raise `AttributeError`
    inside `_run` instead of printing the block.
    """
    import types

    from seer_engine import research
    from seer_engine.lab import runner

    _declare(monkeypatch, **{method_id: arms})
    monkeypatch.setattr(runner, "preflight", lambda *a, **k: None)
    monkeypatch.setattr(
        research, "load_store",
        lambda _path: types.SimpleNamespace(fingerprint="f" * 64, price_fingerprint=SAME_PRICES),
    )
    monkeypatch.setattr(runner, "preflight_data", lambda *a, **k: None)
    verdict = hardgate.FoldVerdict(
        method=method_id, bench_n=None, total=None, scored=None, won=None, majority=None,
        stable=None, picks_json="[]", summary="", reason="stubbed: no fold record in this test",
    )
    monkeypatch.setattr(
        runner, "run_method",
        lambda *a, **k: types.SimpleNamespace(ran=(), folds=None, verdict=verdict),
    )


def test_lab_run_prints_the_control_block_and_still_exits_zero(tmp_path, monkeypatch, capsys):
    """(D15), tested rather than quoted: the run ANNOTATES a handicapped control and completes.

    This is the decision, not an implementation detail. A run-time refusal would only spend method
    ids to say what `lab promote` already says, and a fresh lab has to be able to run before it
    has anything to compare -- so the block is loud and the exit code is 0.
    """
    from seer_engine.commands import lab as lab_cmd

    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _benchmark(c)
    _method(c, "M0099", annual=0.15)
    _control_arm(c, "M0099", "R", trades=800, turnover=3.5)
    c.close()

    _stub_full_run(monkeypatch, tmp_path, "M0099",
                   [_Arm("M0099-A", R_IDEA), _Arm("M0099-R", R_DRAW)])
    assert lab_cmd.run(argparse.Namespace(
        db=db, lab_command="run", method="M0099", store=tmp_path / "store", allow_coverage=0.8,
    )) == 0
    out = capsys.readouterr().out
    assert "Control shape:" in out
    assert "M0099-R" in out
    assert "outside" in out                  # the loud line fired
    assert "lab/hardgate.py, D17" in out     # and it names where the refusal lives


def test_lab_run_says_so_when_there_is_no_control_arm(tmp_path, monkeypatch, capsys):
    from seer_engine.commands import lab as lab_cmd

    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _benchmark(c)
    _method(c, "M0099", annual=0.15)
    c.close()

    _stub_full_run(monkeypatch, tmp_path, "M0099", [_Arm("M0099-A", R_IDEA)])
    assert lab_cmd.run(argparse.Namespace(
        db=db, lab_command="run", method="M0099", store=tmp_path / "store", allow_coverage=0.8,
    )) == 0
    assert "no control or placebo arm" in capsys.readouterr().out


def test_lab_control_reports_every_arm_and_writes_nothing(tmp_path, monkeypatch, capsys):
    """Shape (A): N and the looks are printed either side, and the database bytes do not move."""
    from seer_engine.commands import lab as lab_cmd

    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _benchmark(c)
    _method(c, "M0001", family="a", annual=0.15)
    _control_arm(c, "M0001", "R", trades=800, turnover=3.5)
    _method(c, "M0002", family="b", annual=0.15)
    _control_arm(c, "M0002", "R", trades=252, turnover=1.08)
    n_before = store.dev_trial_count(c)
    looks_before = store.test_looks(c)
    c.close()
    before = db.read_bytes()

    _declare(
        monkeypatch,
        M0001=[_Arm("M0001-A", R_IDEA), _Arm("M0001-R", R_DRAW)],
        M0002=[_Arm("M0002-A", R_IDEA), _Arm("M0002-R", R_DRAW)],
    )

    rc = lab_cmd.run(argparse.Namespace(db=db, lab_command="control", method=[]))
    assert rc == 0
    out = capsys.readouterr().out
    assert "M0001-R" in out and "M0002-R" in out
    assert "refuse" in out and "ok" in out        # one of each, so the band is not refusing all
    assert f"recorded dev trials {n_before} -> {n_before}" in out
    assert f"test-window looks {looks_before} -> {looks_before}" in out
    assert db.read_bytes() == before

    rc = lab_cmd.run(argparse.Namespace(db=db, lab_command="control", method=["M0001"]))
    assert rc == 0
    one = capsys.readouterr().out
    assert "M0001-R" in one and "M0002-R" not in one

    assert lab_cmd.run(argparse.Namespace(db=db, lab_command="control", method=["M9999"])) == 2
```

**Impact:** eleven new tests, one new import, one stub dataclass and two helpers. None touches the
committed `lab/lab.sqlite`; every one builds its own database under `tmp_path`, and every one that
can reach `control_shape` installs the `discover` seam so no test can silently pass by reading a
real method file.

---

### Step 10: run the decomposition and write the backtest note

**File:** `docs/backtests/2026-10-19-trial-828-shortfall.md` — new.

**Run these, in this order, from the worktree root, and paste the real output.** The dev store is
absent from the worktree and must never be rebuilt:

```bash
cd /home/miftah/.worktrees/seer/lab-shortfall-and-control-shape
md5sum lab/lab.sqlite                                   # record it

# /tmp/status-before.txt was captured BEFORE this phase edited anything (see Verification).
# Do not re-take it here -- by now the D17 clause is in the tree and it would not be a "before".
grep -A4 'Promotable now' /tmp/status-before.txt        # expect: M0072, M0092, M0197

PYTHONPATH=engine/src engine/.venv/bin/python -m seer_engine lab shortfall 828 \
    --store /home/miftah/seer/engine/.research > /tmp/shortfall-828.txt 2>&1; echo "exit $?"

PYTHONPATH=engine/src engine/.venv/bin/python -m seer_engine lab shortfall 828 --era whole \
    --store /home/miftah/seer/engine/.research > /tmp/shortfall-828-whole.txt 2>&1; echo "exit $?"

PYTHONPATH=engine/src engine/.venv/bin/python -m seer_engine lab shortfall 828 \
    --against M0244-FRESH30 --store /home/miftah/seer/engine/.research \
    > /tmp/shortfall-828-against.txt 2>&1; echo "exit $?"

PYTHONPATH=engine/src engine/.venv/bin/python -m seer_engine lab control \
    > /tmp/control.txt 2>&1; echo "exit $?"

PYTHONPATH=engine/src engine/.venv/bin/python -m seer_engine lab status \
    > /tmp/status-after.txt 2>&1; echo "exit $?"
diff <(grep -A6 'Promotable now' /tmp/status-before.txt) \
     <(grep -A6 'Promotable now' /tmp/status-after.txt) && echo "PROMOTABLE UNCHANGED"

md5sum lab/lab.sqlite                                   # compare; see Verification
```

**Never pipe a `lab` command into a filter and read `$?`** — the filter owns the status, and this
shell prints `setValueForKeyFakeAssocArray: command not found: _encode` on startup, which is the
exact noise that produced the bug Phase 3 fixes. Redirect to a file and echo the command's own `$?`,
as above.

**Do not copy the expected numbers below into the note.** They are the analysis session's
measurement, repeated here only so the implementer can tell a reproduction from a surprise. **If
the run disagrees, the run is the finding** — record what it actually said, say that it differs and
by how much, and change nothing to make it match.

> **Expected, reconciled.** Trial 828 over 2009-2015: gap `-8.24` pts/yr; gate premium `-3.60` at
> an era-resolved exposure of `0.784` (not the recorded whole-window `0.692`, which would price it
> at `-5.11`); fee drag `-3.78` from `15.05` turns a year at `0.2510%` per dollar of notional —
> the **mean rate over the era's own month offsets (156..237)**, at the **30 names** `names_in`
> reads out of the recorded configuration; pool + weighting residual `-0.87`.
>
> The analysis document first published `-3.76` / `-0.88`, from the rate at a single month offset
> (month 236, `0.2498%`). Phase 1 measured the era mean and that is what the implementation
> computes; the analysis document has been corrected to say so. **Quote `-3.78` / `-0.87`.**
>
> **No `--names` flag is passed, and none is needed.** Trial 828's recorded `config_text` reads
> `params=GestureParams(window_days=380,top=30,...,screen=FactorParams(...,top=1000,...))`, and
> `names_in` takes the shallowest bracket depth carrying a `top=`, so it resolves **30** rather
> than falling back to `DEFAULT_NAMES` (20). The report's own `names_from` line proves which
> number it used — **read it and record it in the note.** If it says the roster's 20, that is a
> finding: say so, and re-run with `--names 30` beside it rather than editing anything.

**Code — the note's skeleton.** `<ANGLE BRACKETS>` are placeholders the run fills:

````markdown
# Trial 828's eight points, named

**Measured:** 2026-10-19 · **Trial:** #828 `M0244-PLACEBO30` (M0244's shape-matched placebo)
**Era:** 2009-01-01 → 2015-10-16 · **Whole window:** 1996-01-02 → 2015-10-16
**Research store:** `<FINGERPRINT>` (dev, unmarked) · **Prices:** `<PRICE FINGERPRINT>`
**Commands:**
`lab shortfall 828 --store /home/miftah/seer/engine/.research`,
`lab shortfall 828 --era whole --store ...`,
`lab shortfall 828 --against M0244-FRESH30 --store ...`,
`lab control`
**Nothing was recorded.** N (dev trials) `<N>` before and after; test-window looks `<L>` before and
after. No journal entry, so seertrade.site/sera is unchanged by this measurement itself.

## The short answer

<One paragraph in plain language. The shape it should take, if the run reproduces: the eight
points this book lost to the market after 2009 are mostly two things that have nothing to do with
how the money was split between names -- standing out of the market under a trend rule, and the
fees on trading fifteen times a year -- and what is left for the pool and the weighting together
is under a point. If the run disagrees, say what it said instead, in the same plain words, and say
that it contradicts the figure this note was written to check.>

## What was published, and why it is being checked

On 2026-10-19 the lab published this trial's 2009-2015 shortfall as an **8.2-point equal-weight
handicap** -- in insight 461, in the memory note
`seer-equal-weight-shape-costs-8pts-since-2009`, and on the `/sera` synthesis page. The arm is not
"thirty index members in equal slices". It is thirty names drawn from the fifty strongest 12-1
momentum stocks, turning over 15.05 times a year, behind the SPY 200-day gate at a recorded
whole-window exposure of 0.692. Three ingredients the published name does not mention sit inside
the number.

As a *control for M0244* the placebo is sound -- its 15.05 turns against FRESH30's 15.3 is a
genuinely good match, so "+1.5 and +3.9 against the placebo" stands. The error was lifting one
matched pair's absolute shortfall and promoting it to a universal constant. It is a good control
and a bad constant.

## The decomposition

```
<PASTE /tmp/shortfall-828.txt VERBATIM>
```

Whole window, for contrast:

```
<PASTE /tmp/shortfall-828-whole.txt VERBATIM>
```

Against its sibling FRESH30, which splits the residual into the part the pool and frame carry and
the part that is this arm's own:

```
<PASTE /tmp/shortfall-828-against.txt VERBATIM>
```

### What each term is, and what it is not

- **Gate premium.** <State the exposure figure the run used, whether it was era-resolved or the
  recorded whole-window one, and the pts/yr.> The 2009-2015 window contains no bear market at all
  (M0245 counted the exits), so every post-2009 exit was a false alarm, and cash earned about
  nothing after 2008 (`seer-idle-cash-credit-worth-08-before-2008-only`). The same batch measured
  the gate's false-alarm premium directly and then attributed the same money to equal weighting in
  the same document.
- **Fee drag.** <turnover x rate = pts/yr.> A model of the fees at the era's slot size, not the
  fees the run paid -- `RunStats.costs_usd` is not a `trials` column. The independent check: the
  model predicts a <X> pt difference between this arm and `M0244-STALE30` (3.57 turns), against an
  observed gap difference of 3.94 pts (-8.24 vs -4.30).
- **Pool + weighting residual.** <pts/yr.> Nothing in a trial row names the pool a book was drawn
  from, so these two cannot be separated from one row; the `--against` run above is the only
  honest split and it is a *peer* split, not an identity.
- **This is an attribution under stated assumptions, not an identity.** The terms are computed
  independently and the residual absorbs their error.

## The control table

```
<PASTE /tmp/control.txt VERBATIM>
```

`<N>` of the lab's 46 placebo arms sit outside the refuse band — measured at the branch base,
**19 refuse, 7 warn, 4 clean, 16 with no arm to compare against**, beside 6 dose-response and 2
within-frame arms that are listed and never flagged. Two of the nineteen were known —
`M0230-C50-R` (0.067x / 0.138x against `M0230-C50`) and `M0248-R` (3.180x / 3.078x against
`M0248-EQ`). `M0243-NEAR20-R` (3.013x / 2.976x against `M0243-NEAR20`) was found by writing the
rule down. The handover knew of two; the measurement finds nineteen. From this phase,
`lab promote` refuses a method holding one (hardgate D17) and `lab run` prints the reading without
refusing (D15).

**The reconciled fact about who this stops — both halves, stated the same way here as in D17 and
in the plan index:**

> **`Promotable now:` is unchanged by D17, AND nine dev-eligible methods would be refused at
> `lab promote` if they ever reached it.**

`Promotable now:` is `<PASTE THE LINE AND ITS METHODS FROM /tmp/status-before.txt>` before and the
same after; none of those methods holds a control arm at all. The nine dev-eligible methods that
do hold a refuse-band control arm are **M0047, M0201, M0202, M0208, M0215, M0221, M0225, M0227,
M0243**. M0222, M0226, M0230 and M0248 are already rejected; M0241 is dev-eligible and warn-only.

Those nine are the point of the feature, not a side effect: each of them quotes, or could quote,
"this beat its control by X" against a control that was not the shape of the book, which is the
unsound sentence this whole plan set exists to stop. **Every one of them has the same way back and
it costs no method id** — re-draw the control at the book's own trade count and turnover and record
it as an amendment under the existing method id, which is exactly what the handover's §2 asks for
on M0248. D17's refusal message names that path, so a researcher who meets it is not at a dead
end.

## The three corrections this note asks for

**This note states them; it does not apply them.** `insights` is append-only, a `/sera` correction
runs through the `update-stale-sera-methods-page` skill, and a memory note is the owner's file.

### 1. `MEMORY.md` line 70 and `seer-equal-weight-shape-costs-8pts-since-2009.md`

Standing text (line 70):

> `- [An equal-weight book loses 8 pts/yr to SPY by shape alone](seer-equal-weight-shape-costs-8pts-since-2009.md) — measured on a coin-flip placebo in 2009-2015; subtract it before blaming the signal.`

Replace with (the `<...>` are the run's own numbers; the reconciled expectation is gate `3.60`,
gap `8.24`, fees `3.78`, residual `0.87`):

> `- [The "8 pt equal-weight handicap" was the gate and the fees](seer-equal-weight-shape-costs-8pts-since-2009.md) — decomposed 2026-10-19: ~<GATE> of trial 828's <GAP> was the SPY-200 gate and ~<FEES> was fee drag on 15 turns/yr; pool and weighting together are bounded under <RESIDUAL>. Never subtract it as a constant.`

The note body's three load-bearing claims and their replacements:

| Standing claim | Replacement |
|---|---|
| "**−8.2 pts/yr vs SPY TR over 2009-2015**, with no signal in it at all" | stands as the *gap*, but it is not the shape: `<GATE>` is the gate at an era-resolved exposure of `<EXPOSURE>`, `<FEES>` is fees on 15.05 turns/yr, and `<RESIDUAL>` is everything pool and weighting can account for together |
| "an equal-weight book starts ~8 points behind before it picks anything" | withdrawn. External check points the other way: equal-weight S&P 500 beat cap-weight over 2009-2015 by roughly 2-3 pts/yr |
| "when a method's 2009-2015 lead is −4 to −9 pts/yr … subtract the placebo first" | stands **only** for a placebo matched to that book's own shape, which is what `lab control` now measures; it is not a constant to carry between methods |

The sound half survives verbatim: "+1.5 and +3.9 against the placebo in that era: the signal
worked, the vehicle lost."

### 2. Insight 461

Two passages. First, in the board-confidence paragraph:

> "But the whole book was thirty index members in equal slices, and that shape lost 8.2 points a
> year to the market after 2009 — more than every stock-picking edge the lab has measured. An
> equal-weight book starts eight points behind before it picks a single company. That number now
> explains more of the lab's record than any signal failure."

Replacement:

> "But the whole book was thirty momentum-screened names in equal slices, traded fifteen times a
> year behind the 200-day rule, and it lost 8.2 points a year to the market after 2009. Decomposed
> on 2026-10-19: about `<GATE>` of that was standing out of the market under the 200-day rule and
> about `<FEES>` was the fees on trading that often. What is left for the pool and the equal
> slices together is under `<RESIDUAL>`. The shape was not the handicap; the gate and the fees
> were, and this batch measured the gate's premium directly in the same document."

Second, in "What would unlock the most":

> "Second, the equal-weight handicap: every stock book the lab builds is measured against a
> cap-weighted index while holding equal slices, and the gap is now measured at eight points a
> year."

Replacement:

> "Second — withdrawn. The eight points were the gate and the fees, not the equal slices. What the
> lab should build instead is a control that matches the book it controls on trade count and
> turnover, which `lab control` now measures and `lab promote` now refuses on."

`insights` is append-only, so this is appended as a correction row (`lab insight --kind correction`
quoting this note), never an edit of 461. That act is the owner's.

### 3. The `/sera` synthesis page

`seertrade.site/sera` renders `web/data/lab.json`, which carries insight 461's body. It changes
when the correction row above is journaled and `lab stage` is run from the main checkout. Run it
through the `update-stale-sera-methods-page` skill, which is the path for a published page that
reads against evidence the lab no longer holds. **No phase of this plan stages `web/data/lab.json`.**

## What this does not say

- It does not say equal weighting is free. It says this trial's eight points are not evidence about
  it, and a method that wants to know should measure it against a control matched on both axes.
- It does not re-run any arm. The handover's §1 also suggested re-running the placebo with
  `trend=None`, at STALE-like turnover, and on a non-momentum pool. Those are three new trials and
  three method ids; this decomposition answers the same question from recorded rows for free. If
  anyone disputes the residual, those re-runs are the next step.
- It does not move `MAX_DRAWDOWN`, re-open a verdict, or touch a recorded row.
````

**Impact:** one new document. Nothing in the engine reads `docs/backtests/`.

---

## Verification

**Build:**
```bash
cd /home/miftah/.worktrees/seer/lab-shortfall-and-control-shape
engine/.venv/bin/ruff check engine
PYTHONPATH=engine/src engine/.venv/bin/python -c "import seer_engine.commands.lab, seer_engine.lab.hardgate"
PYTHONPATH=engine/src engine/.venv/bin/python -m seer_engine lab --help > /tmp/lab-help.txt 2>&1
echo "exit $?"; grep -c control /tmp/lab-help.txt
```

Note the redirect: **never pipe a `lab` command into a filter and read `$?`** — the filter owns the
status, and this shell's startup noise is the exact mechanism behind the bug phase 3 fixes.

**Tests:**
```bash
cd /home/miftah/.worktrees/seer/lab-shortfall-and-control-shape
export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres
PYTHONPATH=engine/src engine/.venv/bin/pytest engine/tests/test_lab_hardgate.py -q
PYTHONPATH=engine/src engine/.venv/bin/pytest engine/tests -q        # -n auto is in addopts; never -o addopts
```
Baseline at `ad8792d`, measured in this worktree: **5947 passed, 4 skipped**. The 4 skips are the
opt-in live-store tests. The Postgres DB tests must not skip — CI fails if they do.

The one test most likely to break, and the reason it would: **`test_there_is_no_override`** greps
`hardgate`'s source for `force`. `enforce` contains it. If that test goes red, the fix is the word,
not the test.

**Manual check — the three bindings, in order:**

1. `lab control` with no argument prints every control arm the lab holds (54 rows measured at the branch base: 46 placebo, 6 dose-response, 2 within-frame) and `recorded dev trials X -> X`.
2. `lab control M0248` prints one method's; `lab control M9999` exits 2.
3. `lab run` on a method with a handicapped control prints the block **and exits 0** (test
   `test_lab_run_prints_the_control_block_and_still_exits_zero`; this is (D15), not a detail).
4. `lab promote` on such a method exits 2 and writes nothing.

**THE VERIFICATION THIS PHASE EXISTS TO PASS — `Promotable now:` must not move.**

**Take the "before" reading as the FIRST act of this phase, before editing a single file.**

```bash
# >>> run this BEFORE Step 1, while the tree is still as phase 3 left it <<<
cd /home/miftah/.worktrees/seer/lab-shortfall-and-control-shape
PYTHONPATH=engine/src engine/.venv/bin/python -m seer_engine lab status \
    > /tmp/status-before.txt 2>&1; echo "exit $?"
git status --short lab/lab.sqlite && git checkout -- lab/lab.sqlite   # it migrates on connect
```

```bash
# >>> and this at the END, with the clause in place <<<
cd /home/miftah/.worktrees/seer/lab-shortfall-and-control-shape
PYTHONPATH=engine/src engine/.venv/bin/python -m seer_engine lab status \
    > /tmp/status-after.txt 2>&1; echo "exit $?"
diff <(sed -n '/Promotable now/,/^  [A-Z]/p' /tmp/status-before.txt) \
     <(sed -n '/Promotable now/,/^  [A-Z]/p' /tmp/status-after.txt) && echo "PROMOTABLE UNCHANGED"
```

**Never `git stash` in this worktree.** The draft of this phase said to, and it is wrong: Seer
swarm phases share one worktree and one git index, so a stash takes other sessions' uncommitted
work with it and a `stash pop` can land it back in the wrong order or conflict. Commit by pathspec,
never stage broadly, never `stash`, never `reset --hard`. Reading `lab status` before the first
edit gives the same answer with none of that risk.

Measured at `ad8792d` on 2026-10-19 against the committed `lab/lab.sqlite`, the answer is
**`M0072`, `M0092`, `M0197`** and it is expected to be identical afterwards, because none of the
three holds a control arm.

**Expected and NOT a failure: nine dev-eligible methods become unpromotable.** `Promotable now:`
does not move, but M0047, M0201, M0202, M0208, M0215, M0221, M0225, M0227 and M0243 each hold a
control arm in the refuse band and would be refused if they reached promotion. That is the
reconciled, recorded decision (plan index, Decisions) and the point of the feature. Check it
deliberately rather than discovering it:

```bash
cd /home/miftah/.worktrees/seer/lab-shortfall-and-control-shape
for M in M0047 M0201 M0202 M0208 M0215 M0221 M0225 M0227 M0243; do
  PYTHONPATH=engine/src engine/.venv/bin/python -m seer_engine lab control "$M" \
      > "/tmp/control-$M.txt" 2>&1; echo "$M exit $?"
done
git status --short lab/lab.sqlite && git checkout -- lab/lab.sqlite
```

Record the nine in the phase report and in the backtest note, with the way back beside them.

Record the before/after in the backtest note and in the phase report.

**If `Promotable now:` HAS changed: that is a finding to report, loudly, not a reason to weaken the
clause and not something to absorb.** Stop, and report, in the phase report and in the backtest
note: which method moved, which control arm did it, both ratios, and which sibling `control_shape`
resolved the arm against. There are exactly three legitimate readings and the report must say which
one it is:

- the arm really is handicapped and the margin really is unsound — the rule worked, and the method
  is correctly no longer promotable (this is the expected reading for any of the nine named above,
  and it is not a reason to weaken anything);
- `control_shape` resolved the wrong sibling — a **Phase 2 defect**, reported to the reconciler and
  fixed there, not papered over by widening the band here;
- the band is wrong — which needs a measurement and an argued change in git, in the D17 text, not
  an edit made to get a green run.

**`lab/lab.sqlite` must be unchanged in git.** Every `lab` subcommand runs the migrations on
connect, so even `lab status` and `lab control` dirty the file's bytes:

```bash
cd /home/miftah/.worktrees/seer/lab-shortfall-and-control-shape
git status --short lab/lab.sqlite
git checkout -- lab/lab.sqlite      # if it moved
```
Commit by pathspec is correct for this phase because this phase stages no database: the commit is
`engine/src/seer_engine/commands/lab.py`, `engine/src/seer_engine/lab/hardgate.py`,
`engine/tests/test_lab_hardgate.py`, `docs/backtests/2026-10-19-trial-828-shortfall.md` and this
plan file — named explicitly, never `git add -A`, because the swarm shares one index.

**Exit criteria:**

1. `lab control` and `lab control M0248` work and write nothing — N and the looks printed either
   side and identical.
2. `lab run` on a method with a mis-shaped control prints the block and returns 0.
3. `lab promote` refuses such a method, exit 2, naming the arm, the arm it controls, the rung,
   both ratios, the band **and the way back** (re-draw and amend, no method id spent); the
   database bytes and the prereg directory are untouched.
4. A method with no control arm promotes exactly as before, and a shape that cannot be read does
   not refuse.
5. `hardgate.__doc__` carries (D17) with its calibration table.
6. `Promotable now:` is recorded before and after and is unchanged — or the change is reported.
   The nine dev-eligible methods D17 would refuse (M0047, M0201, M0202, M0208, M0215, M0221,
   M0225, M0227, M0243) are checked deliberately, recorded with the way back beside them, and are
   **not** treated as a defect.
7. `docs/backtests/2026-10-19-trial-828-shortfall.md` exists and carries the real output of
   `lab shortfall 828`, the real `lab control` table, and all three corrections with their numbers.
8. `ruff check engine` clean; `pytest engine/tests` green; `lab/lab.sqlite` unchanged in git;
   `web/data/lab.json` unchanged.

---

## Handoffs

Work found and deliberately left:

- **The three corrections are stated, not applied.** `MEMORY.md` line 70 and its note are the
  owner's files; insight 461 is an append-only row that needs a `correction` insight quoting this
  note; the `/sera` page needs `update-stale-sera-methods-page` and a `lab stage` from the main
  checkout. The plan index puts all three out of scope on purpose and this phase writes the exact
  replacement text for each. **Owner / a later session.**
- **`hardgate.__doc__` has two stale sentences.** Lines 245 and 441 say `lab status` "still prints
  ``Promotable now: (none)``". Measured 2026-10-19, it prints `M0072, M0092, M0197`. Both sentences
  were true when (D11) and (D14) landed and are history rather than claims about today — but a
  reader meets them as present tense. **Not this phase:** they are inside D11's and D14's recorded
  reasoning, and editing a past decision's evidence to match today's number is exactly the thing
  this plan set exists to stop. A dated line in the owner's own revision style would be the right
  fix. **Handed to the owner.**
- **Nineteen refusals are a new finding, not just a new rule.** The handover knew of two
  handicapped controls; measured over all 46 placebo arms the lab holds, nineteen refuse, seven
  warn, four are clean and sixteen have no arm to compare against. `M0243-NEAR20-R` is the one the
  analysis named; every "X beats its blind draw by Y" sentence behind the other eighteen has the
  same defect M0248's does and nobody has re-read them. **Phase 2 records the detection; the
  re-reading is a Sera session's work, not this phase's.**
- **`M0248-R` should be re-drawn at the book's own turnover**, which the handover's §2 asks for
  directly. That is a new trial — an amendment under M0248's own id, so no method id is spent — and
  the plan index puts re-running any arm out of scope. **A later session.**
- **A `controls=` declaration on `Candidate`.** Phase 2 may add a defaulted field so a *new* method
  can name its control outright instead of being detected. No existing method file may gain one:
  `methods.source_sha` is recorded and frozen. If Phase 2 adds it, `lab control`'s output needs no
  change — `Finding.rung` already says how the target was found, and the module already reads   the field duck-typed through `DECLARATION_ATTR`. **Phase 2's call, and phase 2 deliberately   did not add it: `backtest/dev.py` is outside its two files and no phase of this set touches   it.**
- **No `--csv` on `lab control`.** The table fits on a terminal and nothing downstream
  reads it. If a grid is ever wanted, `lab turnover --csv` is the pattern. **Deliberately omitted.**

---

## Rollback

`git revert` this phase's commit. Every change is additive:

- `commands/lab.py` gains a parser, one handler, one dispatch entry, one docstring block and one
  printed block inside `_run`; removing them restores the previous output exactly.
- `hardgate.py` gains docstring text, one reader and one clause in `check`; removing
  the clause restores the gate's previous behaviour exactly, and the measurement above says that
  behaviour and this one are the same for every method in the lab today.
- `test_lab_hardgate.py` gains one import, one stub dataclass, two helpers and eleven tests.
- The backtest note is a new file; deleting it leaves no reference behind.

Nothing recorded, nothing staged, no method file touched, no `lab.sqlite` row written, no status
moved, no test-window look spent, `web/data/lab.json` unmoved. If the revert happens after the
corrections in Step 10 have been applied by the owner, those corrections stand on their own
measurement and do not need reverting with the code.

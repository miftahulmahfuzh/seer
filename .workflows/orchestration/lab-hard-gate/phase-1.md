# Phase 1: The rule, and the refusal at `lab promote`

**Plan set:** `LAB_HARD_GATE_PLAN.md`
**Analysis:** `docs/analyzer/20261009-161956-K3QD_code_analyzer.md`
**Satisfies:** R1, R2, R3, R4, R5 — `lab promote` refuses a method that lost its walk-forward
folds or whose kin has already failed the test window, before anything is written
**Depends on:** none
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/lab`

---

## Goal

After this phase there is one module, `lab/hardgate.py`, that holds the whole rule: the fold
record for a method, the kin walk, the two conditions, and the refusal. `lab promote` calls it
before `prereg.promote_method`, so a method that lost its folds or whose family or ancestry reads
`test-failed` exits 2 with a named reason and leaves the repository and the database
byte-identical. `_trial_deposits` moves out of `commands/lab.py` into `hardgate.trial_deposits`,
so the gate, `lab regime` and `lab walkforward` share one de-funding path instead of the gate
growing a second one.

---

## READ THIS FIRST — the measured conflict, now recorded in the index

Reconciliation folded this into the plan index: **Decision D1 was corrected in place**, and now
states the gate's location *and* this consequence. What follows is the measurement behind that
correction, and it stays here because it is the reason Steps 2 and 6 must land in one commit.

D1's first half was right: the gate cannot live inside `prereg.promote_method`, because
`test_lab_prereg.py`'s fixtures insert `curve_json="[]"` and no `REF-SPY-HOLD` row. That is true,
and it is verified below. **But the draft stopped one step short:** one existing test drives the
gate's chosen home too.

`engine/tests/test_lab_prereg.py:490` `test_lab_promote_command_writes_the_file_and_names_the_next_step`
calls the **CLI** handler:

```python
args = argparse.Namespace(db=db, lab_command="promote", method="M0001", dir=prereg_dir)
assert lab_cmd.run(args) == 0
```

`lab_cmd.run` dispatches to `_promote`, which is exactly where this phase puts the gate. The lab
that test builds comes from `_real_method` (`tests/test_lab_prereg.py:135`), which inserts two
`_trial` rows with `curve_json="[]"` and never inserts a `REF-SPY-HOLD` benchmark.

**Measured, not assumed.** Against a prototype of `hardgate.fold_record` built in the scratchpad
and run on a database shaped exactly like `_real_method`'s:

```
empty-curve lab -> LabError : no REF-SPY-HOLD dev trial
```

`store.LabError` → `commands/lab.py:367` → `return 2`. The test asserts `== 0`. **It fails.**

Also measured, two corrections to the index's numbers:

| the index's draft said | measured at `7708350` in this worktree — **both corrected in the index** |
|---|---|
| "the 29 existing tests in `test_lab_prereg.py`" | **31** tests (`pytest -q --collect-only tests/test_lab_prereg.py` → `31 tests collected`) |
| baseline `test_lab_*.py` subset | `tests/test_lab_prereg.py tests/test_lab_walkforward.py tests/test_lab_status.py` → **68 passed**. Quote the count, never the seconds: 8.99s for the analyst, 11.35s here, same 68 tests |

### How this phase resolves it

Not with an override, not by weakening D7, and not by editing a test body. **The fixture lab is
made into a lab that could actually promote something** — which is what the brief's sentence "a
method winning a majority with a clean family **promotes** (the existing promote tests must still
pass unchanged)" asks for. A fixture that cannot represent a promotable lab is a fixture that is
behind the gate, exactly as it was when `_ballast` had to be added for the DSR variance (see its
docstring at `tests/test_lab_prereg.py:85-98` — the same move, for the same reason, one gate
earlier).

So Step 6 edits **three helpers** in `tests/test_lab_prereg.py` — `_real_method` and two new
module-level helpers — and **no test body**. All 31 test bodies stay byte-identical.

**Measured.** The patched helper was applied to a scratchpad copy of the file and the whole file
re-run:

```
31 passed in 4.85s
```

No DSR, N-policy or eligibility side effect from the extra dev trial. The gate on that same
fixture lab then reports `4 of 4 folds, majority True`.

**Boundary, settled by reconciliation.** Phase 2 owns *additions* to `tests/test_lab_prereg.py`;
phase 1 owns the three *helpers* in it (`_real_method`, and new `_months` / `_curve` /
`_benchmark`) and no test body. Phase 2 rebases its additions on the post-phase-1 file and
**reuses `_months()`, `_curve()` and `_benchmark()` rather than redefining them**. This is the one
place phase 1 reaches into a file another phase also touches; the edit regions are disjoint
(helpers near line 135 vs. new tests appended at the end), and `1 -> 2` is sequential for exactly
this reason.

This restates plan **Invariant 2** as reconciliation rewrote it: *no existing **test body** is
edited in any file; fixture helpers may be extended; every pre-existing test still passes.* The
brief's requirement — "the existing promote tests must still pass unchanged" — is preserved
exactly: all 31 pass, and not one of their bodies moves.

---

## Interface Contract

**Creates:**
- module `seer_engine.lab.hardgate` (`engine/src/seer_engine/lab/hardgate.py`)
- `hardgate.MIN_FOLDS: int` = `4`
- `hardgate.COIN_FLIP_NULL: tuple[tuple[int, float], ...]` — the strict-majority probability under
  a coin-flip null, as data so a test can check it against the binomial tail
- `hardgate.trial_deposits(conn, row, curve) -> dict[date, float]` — moved verbatim-in-behaviour
  from `commands/lab.py:1656 _trial_deposits`
- `hardgate.Geometry` (frozen dataclass: `bench: tuple[tuple[date, float], ...]`,
  `folds: tuple[walkforward.Fold, ...]`)
- `hardgate.geometry(conn) -> Geometry` — raises `store.LabError`
- `hardgate.fold_record(conn, method_id, geo=None) -> walkforward.Record` — raises `store.LabError`
- `hardgate.fold_summary(conn, method_id, geo=None) -> str` — raises `store.LabError`; the
  one-line fold record, `Record.summary()` verbatim, e.g. `"3 of 4 folds, pick changed"`
- `hardgate.failed_kin(conn, method_id) -> tuple[str, ...]` — raises `store.LabError` only for an
  unknown method; `()` means clean
- `hardgate.family_state(conn, method_id) -> str` — the kin state `summary` prints, e.g.
  `"clean"` or `"blocked: M0022 reads test-failed"`
- `hardgate.summary(conn, method_id, geo=None) -> str` — **phase 3's display line**; never raises
- `hardgate.check(conn, method_id) -> None` — raises `store.LabError`; the refusal
- test module `engine/tests/test_lab_hardgate.py`

**Deletes:** `commands.lab._trial_deposits` (`engine/src/seer_engine/commands/lab.py:1656`)

**Renames:** `commands.lab._trial_deposits` -> `lab.hardgate.trial_deposits` (module move; the
leading underscore goes because the function is now public API of `hardgate`)

**Signature changes:** none. `trial_deposits(conn, row, curve) -> dict` keeps
`_trial_deposits`'s exact parameters, order and return type.

**Requires (from earlier phases):** none — phase 1 is the root.

**Leaves alone (owned by others):**
- `engine/src/seer_engine/lab/prereg.py` (Phase 2)
- `engine/src/seer_engine/lab/walkforward.py` — **read only**; `Record.majority`,
  `Record.scored`, `Record.stable`, `Record.summary`, `folds`, `evaluate`, `measure` are used
  exactly as they are
- `engine/src/seer_engine/backtest/walkforward.py` — a different module; not opened
- `engine/src/seer_engine/lab/runner.py`
- `commands/lab.py:_promotable_now` (`:834`) and `_promotion_path` (`:882`) (Phase 3)
- every **test body** in `engine/tests/test_lab_prereg.py`
- `.claude/skills/*/SKILL.md`, `engine/package_readme.md`,
  `docs/plans/WALK_FORWARD_EVALUATION_PLAN.md` (Phase 3)
- `lab/lab.sqlite`, `docs/lab/prereg/*.md`, `web/data/lab.json`

**Signatures phases 2 and 3 should pin to (asked for explicitly in the briefs):**

| caller | function | signature | returns |
|---|---|---|---|
| Phase 2 (`prereg.fold_text`) | `hardgate.fold_record` | `(conn: sqlite3.Connection, method_id: str, geo: Geometry \| None = None) -> wf.Record` | the record itself — phase 2 reads `rec.won`, `len(rec.scored)` and `rec.stable` separately |
| Phase 2 (`prereg.fold_text`) | `hardgate.MIN_FOLDS` | `int` | named in the written line as the bar *this* method cleared |
| Phase 2 (`prereg.family_text`, `runner.kin_note`) | `hardgate.failed_kin` | `(conn: sqlite3.Connection, method_id: str) -> tuple[str, ...]` | every failed relative, in id order; `()` when clean |
| Phase 3 (`_promotable_now`) | `hardgate.geometry` | `(conn: sqlite3.Connection) -> Geometry` | call **once** per `lab status`, pass to each `summary` |
| Phase 3 (`_promotable_now`) | `hardgate.summary` | `(conn, method_id, geo: Geometry \| None = None) -> str` | one line; **never raises** |

`fold_record`, `fold_summary`, `family_state` and `failed_kin` are **strict** (they raise). That
is safe for phase 2, which reaches them only through `prereg.promote_method`, one line after
`_promote` has already called `check` on the same connection — so by then both are computable. A
pre-registration must never record a number it could not compute.

**Phase 2 calls `fold_record` and `failed_kin`, not `fold_summary` and `family_state`**, and that
is deliberate on phase 2's side: `Record.summary()` says ", pick changed" only when the pick moved,
so a *stable* record would convey stability by absence, and R6 asks the file to name all three
facts. Phase 2 therefore composes its own one-line text from the record's parts (`prereg.fold_text`,
`prereg.family_text`) and wraps both calls in `except store.LabError`, recording "not recorded:
…" rather than raising at the file-writing step. `fold_summary` and `family_state` stay as this
module's own display helpers — `summary` is built from them, and `test_lab_hardgate.py` pins them.

`summary` is **lenient** (it catches `store.LabError` and returns the reason as text) because phase
3 calls it inside `lab status`, which must keep printing on a lab with no benchmark.

---

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/hardgate.py` | create | the whole rule, the kin walk, the de-funding path, the four answered questions |
| `engine/src/seer_engine/commands/lab.py:17-19` | modify | the `lab promote` help line says it refuses |
| `engine/src/seer_engine/commands/lab.py:1148-1172` | modify | `_promote` calls `hardgate.check` before `prereg.promote_method` |
| `engine/src/seer_engine/commands/lab.py:1656-1694` | modify | `_trial_deposits` deleted (the body moves to `hardgate`) |
| `engine/src/seer_engine/commands/lab.py:1760` | modify | `_regime` calls `hardgate.trial_deposits` |
| `engine/src/seer_engine/commands/lab.py:1796-1797, 1847` | modify | `_walkforward` imports and calls `hardgate.trial_deposits` |
| `engine/tests/test_lab_prereg.py:135-153` | modify | `_real_method` builds a lab that can actually promote (helpers only, no test body) |
| `engine/tests/test_lab_hardgate.py` | create | the gate's own tests |

---

## Implementation Steps

### Step 1: `engine/src/seer_engine/lab/hardgate.py` — the whole rule

**File:** `engine/src/seer_engine/lab/hardgate.py` (new)
**Change:** the complete module. Prose answers D2, D3, D4, D6 in place, each with its reason.

**Code:**

```python
"""The hard gate: ``lab promote`` refuses what the folds and the kin have already judged.

**The rule.** A method is promoted only when both hold:

- **(F) the folds.** It beat the recorded benchmark in a strict majority of the walk-forward
  folds (``walkforward.Record.majority``), and it was scoreable on *every* fold the geometry
  yields, and there were at least ``MIN_FOLDS`` of them.
- **(K) the kin.** No other method in its ``family``, and no transitive ancestor through
  ``parent_id``, reads ``test-failed``.

**Decided 2026-10-09 by the owner, after seeing what it costs.** It blocks every promotion in the
lab as of today, and that is the intended effect rather than a side effect: five out-of-sample
results, five failures, and the surviving ideas are all cousins of the methods that produced
them. A lab that keeps promoting cousins of disproven families is not learning.

**There is no override path, in any form** -- no flag, no environment variable, no "promote
anyway". If this proves too strict in practice the answer is a recorded, argued change to this
file, in git, because an override is precisely the mechanism that produced the 0-for-5 roster.

**Why here and not in ``prereg.promote_method``.** The brief requires that the existing promote
tests still pass. ``prereg.promote_method`` is the one function every one of them calls, and a
refusal inside it would refuse a fixture database rather than a method. The gate therefore sits
one layer out, in ``commands/lab.py:_promote``, which calls ``check`` before ``promote_method``.
``promote_method`` has exactly **one** production caller (``commands/lab.py:_promote``), so this
is not a hole in practice -- but **a second caller must call ``check`` too**, and whoever adds one
is the person who has to read this sentence.

**Why this is not a hole in the status machine either.** ``store.TRANSITIONS`` admits exactly one
edge into ``promoted``: ``dev-eligible -> promoted``. ``check`` acts on a ``dev-eligible`` method
and is silent for every other status, so gating ``dev-eligible`` gates *every* promotion the
database will accept. Silence for a non-promotable status is not a waiver: the caller is
``prereg.promote_method``, one line later, which refuses it with the better message it already
has. Silence for ``promoted`` is deliberate too -- that method already cleared this gate, its
pre-registration is a promise (see **(D3)** below), and ``promote_method``'s repair path for a
half-finished promotion must keep working.

**What it spends: nothing.** No research store, no backtest, no trial row, no counted look. It is
SQL plus arithmetic on ``trials.curve_json``, and a refusal happens *before* the pre-registration
file is written and before any status moves, so a refused ``lab promote`` leaves the repository
and the database byte-identical.

**A funded curve is de-funded before it is measured.** Every trial from M0032 on is funded, and a
raw funded curve counts the owner's deposits as growth while the benchmark it is measured against
receives none -- seventy to eighty points a year, until it was fixed (insights 72, 75).
``trial_deposits`` below reconstructs each trial's deposit series; ``walkforward.measure`` calls
``regime.defunded`` with it. Nothing here re-implements de-funding.

**Not ``backtest.walkforward``.** That is P3b's anchored walk-forward for Strategy A2 on the
bracket engine, a different module answering a different question. This gate reads
``lab.walkforward``, which slices curves the lab already recorded.

---

The four questions the brief left open, and the answer to each with its reason.

**(D2) How thin is too thin? -- scoreable on EVERY fold the geometry yields, and at least
``MIN_FOLDS = 4``.**

The fold geometry is cut from the *benchmark* curve, so it is global rather than per method:
``REF-SPY-HOLD`` spans 1993-02-01..2015-10-16 and yields exactly 4 folds. Every ``M*`` method in
the lab has a dev curve spanning 1996-01-03..2015-10-16 and is scoreable on all four, so this
minimum costs a real method nothing. ``H-P7A-F10``, whose curve starts 2007-04-10, scores only 2
-- the thin case is not hypothetical. And measured on a curve of that shape, it wins **both** of
the folds it can be scored on, so ``Record.majority`` reads True: the literal rule "wins a
majority of its walk-forward folds" would promote it on two looks at the post-crisis decade
alone. That is what the "every fold" clause is for, and why it is not redundant with
``majority``.

Why not "3 or more". Under a coin-flip null -- a **bound, not a p-value**: folds share training
data and may never be treated as independent observations, and nothing here may be fed into a
DSR -- the probability of a strict majority is:

====================  ===============================
scoreable folds       P(strict majority | coin flip)
====================  ===============================
1                     0.5000
2                     0.2500
**3**                 **0.5000**
**4**                 **0.3125**
5                     0.5000
6                     0.3438
====================  ===============================

A strict majority of an **odd** count is a coin flip at every odd count, because the null has no
tie to lose. A "minimum of 3" would therefore admit evidence strictly weaker than 4 and no
stronger than 1. The rule is the conjunction: the first clause refuses a method whose curve does
not cover the window; ``MIN_FOLDS`` is a tripwire that fires if ``MIN_TRAIN_YEARS``,
``EVAL_YEARS`` or the dev window ever changes the geometry, so a changed setting cannot silently
lower the bar.

**(D3) Is (K) re-checked at ``lab test``? -- No. The pre-registration is a promise.**

Three reasons, in the order they matter. ``promoted`` has only two exits and both are final, so a
refusal at ``lab test`` strands a method in a state it can never leave -- the exact failure the
brief's "refuse before the commitment, not after it" rejects. A pre-registration whose meaning
depends on events after it was written is not a pre-registration. And the family's state **is**
recorded in the file (``family_state``, written by ``prereg``), so a reader can see the promise's
basis without the code re-deriving it.

What ``lab test`` gets instead is one printed line and no new refusal: when the method's kin has
failed since promotion, it says so above the look. That is information the owner should have
before spending the one look; it changes no exit code and no transition.

**(D4) Does (K) walk ``parent_id`` as well as ``family``? -- Yes: ``family`` union transitive
ancestors. Not the full connected component.**

The brief gives the reason for yes: M0032 is M0007's realistic twin by ``parent_id``, not by
family string, and a method whose *parent* failed is as disproven as one whose sibling did.
Measured on the committed lab (63 methods, 4 reading ``test-failed``):

================================  =========  =====================================================
rule                              blocks     note
================================  =========  =====================================================
``family`` only                   26 of 63   the literal rule; **misses M0030**, whose family is
                                             clean but whose parent M0029 and grandparent M0021
                                             both read ``test-failed``
ancestors only                    10 of 63   misses M0007, M0019, M0020, M0033
**``family`` union ancestors**    29 of 63   catches all seven dev-eligible methods
full connected component          36 of 63   one **26-method blob**; would refuse M0019 on account
                                             of M0021, a multi-factor blend four hops away in an
                                             unrelated family
================================  =========  =====================================================

The component rule is rejected on that last line: "cousin of a disproven family" stretched to four
hops through unrelated families stops being a statement about the evidence. Descendants are left
to the ``family`` string, which by construction holds a variation twin (``lab idea
--source-kind variation --parent ...`` keeps the family), and the measurement shows ``family``
already catches every failed-descendant case the lab has.

**(D6) Is there a path back? -- None is built, and the need is recorded.**

The brief said not to invent one here, and to note whether it will be needed. **It will.**
``reevaluate`` exists for ``rejected -> dev-eligible`` when the bars move; nothing equivalent
exists for a method whose kin is blocked. Two shapes will eventually be wanted and neither is
built here:

1. a family whose failure is later attributed to something other than the idea -- a cost model, a
   fill assumption -- so the failure does not disprove the hypothesis;
2. a method whose ``parent_id`` links it to a failure it does not inherit.

Both are *arguments*, and the brief's own sentence says an argued change to the rule is the
mechanism: a commit, not a flag. Until then the gate is not a permanent stop -- M0034 and M0035
both win 3 of 4 folds with clean kin (their parent M0032 reads ``rejected``, not ``test-failed``),
they simply read ``rejected`` themselves today.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import date

from seer_engine.backtest import regime
from seer_engine.lab import store
from seer_engine.lab import walkforward as wf

#: The fewest scoreable folds that count as evidence. See (D2) in the module docstring: the rule
#: is "every fold the geometry yields, AND at least this many". Four is what the recorded
#: benchmark's span yields today, so this is a tripwire on the geometry, not a quota on a method.
MIN_FOLDS = 4

#: P(strict majority | coin flip) for n folds -- the binomial tail P(X > n/2), X ~ Bin(n, 1/2).
#: A **bound on how impressed to be**, never a p-value: the folds share training data, so they are
#: not independent observations and nothing derived from this may enter a DSR. It is here as data
#: so a test can check it against the binomial rather than against a typed-in table, and so the
#: next person to argue for MIN_FOLDS = 3 has to argue with the 0.5000 on its row.
COIN_FLIP_NULL: tuple[tuple[int, float], ...] = (
    (1, 0.5000),
    (2, 0.2500),
    (3, 0.5000),
    (4, 0.3125),
    (5, 0.5000),
    (6, 0.3438),
)

#: The statuses the gate judges. Exactly the tail of ``store.TRANSITIONS``' only edge into
#: ``promoted``, so this set is the complete set of promotions the database will accept.
_GATED_STATUS = "dev-eligible"


def trial_deposits(
    conn: sqlite3.Connection, row: sqlite3.Row, curve: list[tuple[date, float]]
) -> dict[date, float]:
    """What a funded trial received inside each curve step, in the curve's own units.

    A recorded curve is normalised to the opening cash, so one deposit is
    ``amount_idr / INITIAL_IDR`` -- 0.5 for the owner's 5,000,000 against a 10,000,000 start --
    and no exchange rate is involved, because the run converted both at the same rate. (M0032's
    curve opens at 1.5 for exactly this reason: January's deposit is already in the first point.)

    ``{}`` for a lump-sum trial, which is every trial recorded before the contribution schedule
    existed. Without this, slicing a funded curve counts the owner's deposits as growth and
    compares the result against a benchmark that received none -- see ``regime.split``.

    This lived in ``commands/lab.py`` as ``_trial_deposits`` until the hard gate needed it too.
    It is here, not there, so that the gate, ``lab regime`` and ``lab walkforward`` share **one**
    de-funding path: a second reconstruction is a second chance to read a deposit as edge.
    """
    from seer_engine import dates as nyse
    from seer_engine.backtest.regime import bucket
    from seer_engine.backtest.runner import INITIAL_IDR
    from seer_engine.lab import runner as labrunner

    schedule = labrunner.recorded_contributions(conn, int(row["n"]))
    if schedule is None:
        return {}
    start, end = date.fromisoformat(row["start"]), date.fromisoformat(row["end"])
    unit = float(schedule.amount_idr / INITIAL_IDR)
    due = schedule.dates_in(start, end)
    credited: dict[date, float] = {}
    for d in due:
        session = d if nyse.is_session(d) else nyse.next_session(d)
        if session > end:
            continue
        credited[session] = credited.get(session, 0.0) + unit
    recorded = store.funding_of(conn, int(row["n"]))
    expected = int(recorded["deposits_n"])
    if len(due) != expected:
        raise store.LabError(
            f"{row['candidate_id']}: reconstructed {len(due)} deposits from "
            f"{recorded['schedule']!r} over {start}..{end}, but the trial records {expected}. "
            f"The schedule in sim.contributions has moved since this trial ran, so its curve "
            f"cannot be de-funded safely; `lab regime` will not guess"
        )
    return bucket(curve, credited)


@dataclass(frozen=True, slots=True)
class Geometry:
    """The benchmark curve and the folds cut from it -- the same split for every method.

    Global on purpose: the folds come from ``REF-SPY-HOLD``, not from the method under test, so
    two methods are never judged on different windows. Computed once per command and passed down,
    because ``lab status`` asks for a summary per dev-eligible method and re-cutting the folds
    each time would be the same arithmetic seven times over.
    """

    bench: tuple[tuple[date, float], ...]
    folds: tuple[wf.Fold, ...]


def _curve_of(row: sqlite3.Row) -> list[tuple[date, float]]:
    return [(date.fromisoformat(d), float(v)) for d, v in json.loads(row["curve_json"])]


def geometry(conn: sqlite3.Connection) -> Geometry:
    """The benchmark curve and its folds, or ``store.LabError`` saying what is missing.

    A missing benchmark **refuses**. The brief's open question 1 says a method with no scoreable
    folds must be refused and never waved through, and the same answer applies when it is the
    benchmark rather than the method that is absent: without it no fold can be scored at all. The
    message names ``REF-SPY-HOLD`` so the reader knows it is the lab's fixture that is wrong, not
    their method.
    """
    row = conn.execute(
        'SELECT n, candidate_id, start, "end", curve_json FROM trials '
        "WHERE window = 'dev' AND candidate_id = ? AND curve_json IS NOT NULL "
        "ORDER BY n LIMIT 1",
        (regime.BENCH_CANDIDATE,),
    ).fetchone()
    if row is None:
        raise store.LabError(
            f"no {regime.BENCH_CANDIDATE} dev trial, so no fold can be scored. The hard gate "
            f"measures every method against the lab's recorded SPY buy-and-hold curve; without "
            f"it there is no benchmark and nothing is promotable. This is the lab's fixture "
            f"missing, not your method failing"
        )
    bench = _curve_of(row)
    if len(bench) < 2:
        raise store.LabError(
            f"the recorded {regime.BENCH_CANDIDATE} dev curve has {len(bench)} point(s); the "
            f"hard gate cannot cut folds from it"
        )
    the_folds = wf.folds([d for d, _v in bench])
    if len(the_folds) < MIN_FOLDS:
        raise store.LabError(
            f"the recorded {regime.BENCH_CANDIDATE} curve yields {len(the_folds)} walk-forward "
            f"fold(s), below the minimum of {MIN_FOLDS}. Nothing is promotable on this geometry. "
            f"If walkforward.MIN_TRAIN_YEARS, walkforward.EVAL_YEARS or the dev window moved, "
            f"that is the change to argue with -- the gate will not lower its own bar to fit"
        )
    return Geometry(tuple(bench), the_folds)


def _dev_curves(conn: sqlite3.Connection, method_id: str) -> list[sqlite3.Row]:
    """Every dev trial of ``method_id`` that carries a non-empty curve.

    The empty filter is load-bearing: ``walkforward.evaluate`` takes ``min()`` over every curve's
    dates and raises ``ValueError`` -- not a ``LabError`` -- on a curve of ``[]``. Rows recorded
    with ``curve_json = '[]'`` exist (the lab's own test fixtures write them), so they are dropped
    here and a method with nothing left is refused below with a sentence instead of a traceback.

    Every variant is a candidate, eligible or not, exactly as ``lab walkforward`` does it: the
    fold's question is "which variant would the lab's own rule have named at this point in time",
    and that rule ranks the whole family of variants, not a pre-filtered subset.
    """
    rows = conn.execute(
        'SELECT n, candidate_id, start, "end", curve_json FROM trials '
        "WHERE window = 'dev' AND method_id = ? AND curve_json IS NOT NULL ORDER BY n",
        (method_id,),
    ).fetchall()
    return [r for r in rows if json.loads(r["curve_json"])]


def fold_record(
    conn: sqlite3.Connection, method_id: str, geo: Geometry | None = None
) -> wf.Record:
    """``method_id``'s whole walk-forward record, de-funded, on the shared geometry.

    The benchmark is measured without deposits: ``REF-SPY-HOLD`` is a seed buy-and-hold trial and
    was never fed. That is the same treatment ``lab walkforward`` gives it, deliberately -- the
    two must not disagree about what a fold says.
    """
    geo = geometry(conn) if geo is None else geo
    rows = _dev_curves(conn, method_id)
    if not rows:
        raise store.LabError(
            f"{method_id} has no dev trial carrying a monthly curve, so no fold can be scored "
            f"and it cannot be promoted. The hard gate fails closed on thin evidence: a method "
            f"with no out-of-sample record is not a method with a clean one"
        )
    curves = {r["candidate_id"]: _curve_of(r) for r in rows}
    deposits = {
        r["candidate_id"]: trial_deposits(conn, r, curves[r["candidate_id"]]) for r in rows
    }
    return wf.Record(method_id, wf.evaluate(curves, list(geo.bench), geo.folds, deposits))


def fold_summary(
    conn: sqlite3.Connection, method_id: str, geo: Geometry | None = None
) -> str:
    """One line: ``"3 of 4 folds"``, or ``"3 of 4 folds, pick changed"`` when unstable.

    Strict -- it raises ``store.LabError`` when the record cannot be computed -- because its
    caller is the pre-registration, and a pre-registration must never record a number it could
    not compute. Use ``summary`` for display.
    """
    return fold_record(conn, method_id, geo).summary()


def failed_kin(conn: sqlite3.Connection, method_id: str) -> tuple[str, ...]:
    """Every method in ``method_id``'s kin that reads ``test-failed``; ``()`` when clean.

    Kin is the ``family`` string **union** the transitive ancestors reached through
    ``parent_id``, excluding the method itself. See (D4) in the module docstring for why that
    union and not the full connected component, with the measurement that decided it.

    The ancestor walk carries a ``seen`` set: ``methods.parent_id`` is a self-referencing foreign
    key with no cycle constraint, so a cycle would otherwise hang the gate.
    """
    row = store.get_method(conn, method_id)
    if row is None:
        raise store.LabError(f"no method {method_id}")

    ancestors: set[str] = set()
    cur = row["parent_id"]
    while cur is not None and cur not in ancestors:
        ancestors.add(str(cur))
        parent = store.get_method(conn, str(cur))
        cur = None if parent is None else parent["parent_id"]

    kin = set(ancestors)
    for r in conn.execute("SELECT id FROM methods WHERE family = ?", (row["family"],)):
        kin.add(str(r["id"]))
    kin.discard(method_id)
    if not kin:
        return ()

    ids = sorted(kin)
    marks = ", ".join("?" for _ in ids)
    bad = conn.execute(
        f"SELECT id FROM methods WHERE id IN ({marks}) AND status = 'test-failed' ORDER BY id",
        tuple(ids),
    ).fetchall()
    return tuple(str(r["id"]) for r in bad)


def family_state(conn: sqlite3.Connection, method_id: str) -> str:
    """``"clean"``, or which kin read ``test-failed`` -- what the pre-registration records.

    Phrased as a state rather than a boolean because the pre-registration is read years later by
    someone asking what was true when the promise was made, and "clean" is a claim about the
    whole kin set, not about a flag.
    """
    bad = failed_kin(conn, method_id)
    if not bad:
        return "clean"
    return f"blocked: {', '.join(bad)} read test-failed"


def summary(conn: sqlite3.Connection, method_id: str, geo: Geometry | None = None) -> str:
    """One display line for ``method_id``: the fold record and the kin state.

    Lenient on purpose -- it catches ``store.LabError`` and returns the reason as text. Its
    caller is ``lab status``, which must keep printing on a lab whose benchmark is missing or
    whose method has no curve. A report that dies on one row is a worse report than one that says
    why that row is blank.
    """
    try:
        folds = fold_record(conn, method_id, geo).summary()
    except store.LabError as e:
        folds = f"not scoreable ({e})"
    try:
        kin = family_state(conn, method_id)
    except store.LabError as e:
        kin = f"kin unknown ({e})"
    return f"{folds}; kin {kin}"


def check(conn: sqlite3.Connection, method_id: str) -> None:
    """Refuse ``method_id``'s promotion, or return. Raises ``store.LabError``.

    Called by ``commands/lab.py:_promote`` **before** ``prereg.promote_method``, so a refusal
    happens before the pre-registration file is written and before any status moves: the
    repository and the database are byte-identical afterwards.

    Silent for any status but ``dev-eligible``. That is the only edge into ``promoted`` that
    ``store.TRANSITIONS`` admits, so every promotion is gated; and the caller one line later is
    ``promote_method``, which refuses a wrong status with the message it already has. See the
    module docstring.

    The folds are checked before the kin. (F) is a statement about *this* method's own evidence,
    which is what the researcher asked about; (K) is about the company it keeps, and reads better
    second. Both are cheap -- SQL and arithmetic on recorded curves -- so the order is about the
    message, not the cost.
    """
    row = store.get_method(conn, method_id)
    if row is None:
        raise store.LabError(f"no method {method_id}")
    if str(row["status"]) != _GATED_STATUS:
        return

    geo = geometry(conn)
    record = fold_record(conn, method_id, geo)
    scored, total = len(record.scored), len(geo.folds)

    if scored < total:
        raise store.LabError(
            f"{method_id} is scoreable on only {scored} of the {total} walk-forward folds, so "
            f"its out-of-sample record is thinner than the lab's own window. The hard gate fails "
            f"closed on thin evidence: a method must be scoreable on every fold the geometry "
            f"yields. Nothing was written and no status moved"
        )
    if scored < MIN_FOLDS:
        raise store.LabError(
            f"{method_id} has {scored} scoreable fold(s), below the minimum of {MIN_FOLDS}. A "
            f"strict majority of an odd number of folds is a coin flip under the null, so the "
            f"minimum is not negotiable from inside the code -- see hardgate.COIN_FLIP_NULL. "
            f"Nothing was written and no status moved"
        )
    if not record.majority:
        raise store.LabError(
            f"{method_id} wins {record.summary()} and is not promoted: the hard gate requires a "
            f"strict majority of the walk-forward folds. A method that wins its dev average but "
            f"loses the folds is a selection, not an edge. Nothing was written and no status "
            f"moved. There is no override -- if the rule is wrong, change it in "
            f"seer_engine/lab/hardgate.py and argue for it in the commit"
        )

    bad = failed_kin(conn, method_id)
    if bad:
        raise store.LabError(
            f"{method_id} is not promoted: {', '.join(bad)} already read test-failed, and "
            f"{'they are' if len(bad) > 1 else 'it is'} kin -- same family ({row['family']!r}) "
            f"or an ancestor through parent_id. A new variant of a family that has been disproven "
            f"out of sample is not a fresh candidate. Nothing was written and no status moved. "
            f"There is no override -- if this family deserves another look, that is an argued "
            f"change to the rule, in git"
        )
```

**Impact:** a new module. Nothing imports it yet; the tree still builds and every test still
passes at this step alone.

---

### Step 2: `_promote` calls the gate before anything is written

**File:** `engine/src/seer_engine/commands/lab.py:1148-1172`
**Change:** replace the whole `_promote` handler. The gate call is the first statement after the
imports, before `prereg.promote_method`.

**Code:**

```python
def _promote(conn, args) -> int:
    """`lab promote M0007`: pre-register the best dev-eligible variant and move it to promoted.

    Writes one markdown file and one status transition. It loads no research store, runs no
    backtest and inserts no trial, so the test-window look count it prints is the one it found.

    **The hard gate runs first.** `hardgate.check` refuses a method that lost a majority of its
    walk-forward folds, that is scoreable on fewer folds than the geometry yields, or whose
    family or ancestry already reads `test-failed`. It raises `store.LabError`, which `run` turns
    into exit 2, and it raises *before* `prereg.promote_method` writes the file or moves the
    status -- so a refused promote leaves the repository and the database byte-identical. There
    is no flag that skips it.

    `prereg.promote_method` has exactly one production caller, and this is it. A second caller
    must call `hardgate.check` too.

    Like every other `lab` subcommand, the global `--dry-run` is ignored: there is no roll-back
    half of this to show, and a dry run that printed a pre-registration without writing it would
    be exactly the artefact design §3 exists to prevent.
    """
    from seer_engine.lab import hardgate, prereg
    from seer_engine.lab.runner import git_head

    hardgate.check(conn, args.method)

    done = prereg.promote_method(
        conn,
        args.method,
        git_sha=git_head(config.REPO_ROOT),
        directory=None if args.dir is None else Path(args.dir),
    )
    p = done.prereg
    rel = prereg.repo_path(done.path)
    print(f"wrote {rel}" if done.wrote_file else f"{rel} already pre-registers {p.candidate}")
    print(f"{p.method} is {done.status}" + ("" if done.moved_status else " (already)"))
    print(f"  candidate      {p.candidate}  (dev trial #{p.dev_trial})")
    print(f"  config digest  {p.config_digest}")
    print(f"  dev window     {p.dev_window}  MAR {p.mar}  DSR {p.dsr} at N = {p.n_trials_at_run}")
    print(f"  test window    {p.test_window}")
    print(f"  gate           {p.gate}")
    print()
    print(f"Commit and push {rel} before the look is spent (design §3):")
    print(f"    git add {rel}")
    print(f"    git commit -m 'lab: pre-register {p.candidate} for the test window'")
    print(f"    python -m seer_engine lab test {p.candidate}")
    print(f"\ntest-window looks used: {store.test_looks(conn)}")
    return 0
```

**Impact:** this is R1. `lab promote` now refuses. Until Step 6 lands,
`test_lab_prereg.py:490` fails — Steps 2 and 6 must be in the same commit.

---

### Step 3: delete `_trial_deposits` from `commands/lab.py`

**File:** `engine/src/seer_engine/commands/lab.py:1656-1694`
**Change:** delete the entire function, from `def _trial_deposits(conn, row, curve) -> dict:`
through `    return bucket(curve, credited)` inclusive, and the blank line that separated it from
`_names` above. The body now lives in `hardgate.trial_deposits` (Step 1), unchanged.

**Code:** (what remains at the seam — the end of `_names` running straight into `_regime`)

```python
    log.info("lab names: %d runs done (%.1fs)", len(sweep.points), time.perf_counter() - t0)
    return 0


def _regime(conn, args) -> int:
```

**Impact:** `lab regime` and `lab walkforward` break until Steps 4 and 5 land. All three are one
commit.

---

### Step 4: `_regime` calls `hardgate.trial_deposits`

**File:** `engine/src/seer_engine/commands/lab.py:1705-1708` (the import block of `_regime`) and
`:1760` (the call site) — line numbers as they read *before* Step 3's deletion.
**Change:** add the `hardgate` import beside the existing `regime` import, and qualify the call.

**Code:** the import block inside `_regime`:

```python
    import json

    from seer_engine.backtest import regime
    from seer_engine.lab import hardgate
```

and the call site, in the per-trial loop:

```python
        curve = [(date.fromisoformat(d), float(v)) for d, v in json.loads(r["curve_json"])]
        pan = regime.panel(curve, bench_curve, label, hardgate.trial_deposits(conn, r, curve))
```

**Impact:** `lab regime`'s behaviour is unchanged — same function, same arguments, one import
hop. Covered by Verification's `lab regime` smoke check on a scratchpad copy.

---

### Step 5: `_walkforward` calls `hardgate.trial_deposits`

**File:** `engine/src/seer_engine/commands/lab.py:1794-1797` (the import block of `_walkforward`)
and `:1846-1848` (the call site) — line numbers as they read *before* Step 3's deletion.
**Change:** add the `hardgate` import and qualify the call.

**Code:** the import block inside `_walkforward`:

```python
    import json

    from seer_engine.backtest import regime
    from seer_engine.lab import hardgate
    from seer_engine.lab import walkforward as wf
```

and the call site:

```python
        curves = {r["candidate_id"]: curve_of(r) for r in trials}
        deps = {
            r["candidate_id"]: hardgate.trial_deposits(conn, r, curves[r["candidate_id"]])
            for r in trials
        }
```

**Impact:** `lab walkforward`'s numbers are unchanged — it is the same reconstruction. `lab
walkforward` keeps its own inline kin query (`commands/lab.py:1863-1866`, `family` only); that
query feeds `wf.buy_signal`, which is a *report*, not the gate, and the brief does not ask for
them to agree. **Left deliberately. Noted in Handoffs.**

---

### Step 6: make the promote fixture a lab that can promote

**File:** `engine/tests/test_lab_prereg.py:12` (the `datetime` import) and `:135-153`
(`_real_method`, plus two new helpers immediately above it)
**Change:** add `_months`, `_curve` and `_benchmark` helpers; `_real_method` inserts the benchmark
and gives its real trial a winning twenty-year curve. **No test body is touched.** See the
"READ THIS FIRST" section for why this is necessary and for the measurement that it is
side-effect-free.

**Code:** the import line at `:12` becomes:

```python
from datetime import date, timedelta
```

and the block from `:135` (`def _real_method(conn, mid: str = "M0001"):`) is replaced by:

```python
def _months(start: date, end: date) -> list[date]:
    """Month-end dates in ``[start, end]`` -- the shape a recorded ``trials.curve_json`` has."""
    out, d = [], date(start.year, start.month, 1)
    while True:
        nxt = date(d.year + (d.month == 12), (d.month % 12) + 1, 1)
        last = nxt - timedelta(days=1)
        if last > end:
            return out
        if last >= start:
            out.append(last)
        d = nxt


def _curve(months: list[date], annual: float) -> str:
    """A ``curve_json`` compounding at ``annual`` from 1.0, one point per month end."""
    import json

    out, v = [], 1.0
    for d in months:
        out.append([d.isoformat(), round(v, 8)])
        v *= (1.0 + annual) ** (1.0 / 12.0)
    return json.dumps(out)


def _benchmark(conn) -> None:
    """The lab's recorded SPY buy-and-hold dev trial (``regime.BENCH_CANDIDATE``).

    Since the hard gate (`lab/hardgate.py`) a lab with no ``REF-SPY-HOLD`` dev trial can promote
    nothing: there is no benchmark to cut folds from, so no fold can be scored, and the gate
    fails closed rather than waving a method through. A fixture that wants a *promotable* method
    therefore has to look like a lab that could have one -- the same reason `_ballast` exists one
    gate earlier. Its span matches the real row's, 1993-02-01..2015-10-16, which is what yields
    the four folds the gate requires.

    Its own family and its own method id, so it is never kin to the method under test.
    """
    store.add_method(conn, id="H-P7A-REF", name="SPY buy and hold", family="reference",
                     source_kind="seed", hypothesis="h", status="registered")
    store.insert_trials(conn, [_trial(
        method_id="H-P7A-REF", candidate_id="REF-SPY-HOLD", config_digest="ref-spy-hold",
        start="1993-02-01", end="2015-10-16",
        curve_json=_curve(_months(date(1993, 2, 1), date(2015, 10, 16)), 0.08),
    )])


def _real_method(conn, mid: str = "M0001"):
    """What `lab run` would have left behind for the committed `mNNNN_*.py` file `mid`.

    The real file is used so `check_source` has something true to check: the trial's digest is
    the file's own `config_digest` and `source_sha` is the file's sha256.

    Its trial carries a real curve, and the lab carries a benchmark, because `lab promote` now
    runs the hard gate before `prereg.promote_method`: a method with no curve is scoreable on no
    fold and is refused. The curve compounds at 15% a year against the benchmark's 8%, so the
    method wins all four folds -- which is what the brief means by "a method winning a majority
    with a clean family promotes".
    """
    method, path = discover()[mid]
    c = method.candidates[0]
    with conn:
        _benchmark(conn)
        store.add_method(conn, id=mid, name=method.name, family=method.family,
                         source_kind=method.source_kind, source_ref=method.source_ref,
                         hypothesis="h", status="registered")
        store.insert_trials(conn, [
            _trial(method_id=mid, candidate_id=c.id, config_digest=config_digest(c),
                   rules_id=c.rules.id, allocator_id=str(c.allocator.id),
                   curve_json=_curve(_months(date(1996, 1, 2), date(2015, 10, 16)), 0.15)),
            _ballast(mid),
        ])
        store.update_method(conn, mid, source_sha=source_sha(path), status="dev-eligible")
    return c, path
```

**Impact:** `test_lab_prereg.py:490` passes again. Measured on a scratchpad copy of the file with
exactly this patch: **31 passed in 4.85s**, unchanged from baseline. Tests at `:226` and `:233`
also use `_real_method` and call `prereg.promote_method` directly (the gate does not run there);
both still pass.

---

### Step 7: the module help block says `lab promote` refuses

**File:** `engine/src/seer_engine/commands/lab.py:17-19`
**Change:** replace the three `lab promote` lines.

**Code:**

```python
    lab promote M0007               pre-register the best dev-eligible variant by MAR in
                                    docs/lab/prereg/M0007.md and move the method to promoted;
                                    commit that file before `lab test` will spend the one look.
                                    REFUSES a method that does not win a majority of its
                                    walk-forward folds, or that is scoreable on fewer than the
                                    folds the benchmark yields, or whose family or ancestry
                                    already reads test-failed (lab/hardgate.py). The refusal
                                    comes before anything is written, and there is no override
```

**Impact:** `lab --help` / the module docstring tells the truth. No behaviour change.

---

### Step 8: `engine/tests/test_lab_hardgate.py`

**File:** `engine/tests/test_lab_hardgate.py` (new)
**Change:** the gate's own tests. Every one builds its own temp database, the way
`test_lab_prereg.py` does; none touches `lab/lab.sqlite`.

**Code:**

```python
"""The hard gate (lab/hardgate.py): the fold rule, the kin walk, and the refusal at promote.

Every test builds its own temp lab database. The real one has no promotable method, and these
tests must keep passing on the day it does.
"""

from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from math import comb

import pytest

from seer_engine.backtest import regime
from seer_engine.lab import hardgate, store
from seer_engine.lab import walkforward as wf


@pytest.fixture(autouse=True)
def _at_the_policy_these_fixtures_were_recorded_under(monkeypatch):
    """Judge every lab here under ``all-trials``, the policy its rows are stamped with.

    The same reason `test_lab_prereg.py` pins it: these fixtures carry ``n_trials_at_run`` equal
    to a small dev row count, which is what a lab recorded under ``all-trials`` looks like.
    """
    monkeypatch.setattr(store, "DSR_POLICY", "all-trials")
    store._GATE_CACHE.clear()
    yield
    store._GATE_CACHE.clear()


@pytest.fixture()
def conn(tmp_path):
    c = store.connect(tmp_path / "lab.sqlite")
    yield c
    c.close()


def _months(start: date, end: date) -> list[date]:
    out, d = [], date(start.year, start.month, 1)
    while True:
        nxt = date(d.year + (d.month == 12), (d.month % 12) + 1, 1)
        last = nxt - timedelta(days=1)
        if last > end:
            return out
        if last >= start:
            out.append(last)
        d = nxt


def _curve(months: list[date], annual: float) -> str:
    out, v = [], 1.0
    for d in months:
        out.append([d.isoformat(), round(v, 8)])
        v *= (1.0 + annual) ** (1.0 / 12.0)
    return json.dumps(out)


BENCH_SPAN = (date(1993, 2, 1), date(2015, 10, 16))
DEV_SPAN = (date(1996, 1, 2), date(2015, 10, 16))


def _trial(**kw) -> store.TrialRow:
    base = dict(
        method_id="M0001", candidate_id="M0001-A", config_digest="d1", config_text="t",
        rules_id="MONTHLY_HOLD", allocator_id="TIMING", window="dev", start="1996-01-02",
        end="2015-10-16", store_fingerprint="399d0d25", git_sha="abc123",
        run_at="2026-10-06T00:00:00+00:00", total_return=3.0, cagr=0.12, max_drawdown=0.11,
        profit_factor=1.6, trades=250, sharpe=0.9, exposure=0.95, turnover=1.1, worst_year=2008,
        worst_year_return=-0.1, spy_tr_return=2.0, spy_tr_cagr=0.08, mar=0.8, failed="",
        eligible=True, dsr=0.97, n_trials_at_run=60, curve_json="[]",
    )
    base.update(kw)
    return store.TrialRow(**base)


def _benchmark(conn) -> None:
    with conn:
        store.add_method(conn, id="H-P7A-REF", name="SPY buy and hold", family="reference",
                         source_kind="seed", hypothesis="h", status="registered")
        store.insert_trials(conn, [_trial(
            method_id="H-P7A-REF", candidate_id=regime.BENCH_CANDIDATE,
            config_digest="ref-spy-hold", start="1993-02-01", end="2015-10-16",
            curve_json=_curve(_months(*BENCH_SPAN), 0.08),
        )])


def _method(conn, mid="M0001", *, family="trend", parent=None, status="dev-eligible",
            annual=0.15, span=DEV_SPAN, curves=True) -> None:
    """One method with one dev trial, walked to ``status`` through the real transitions."""
    with conn:
        store.add_method(conn, id=mid, name=f"n{mid}", family=family, parent_id=parent,
                         source_kind="variation" if parent else "knowledge", hypothesis="h",
                         status="registered")
        store.insert_trials(conn, [_trial(
            method_id=mid, candidate_id=f"{mid}-A", config_digest=f"d-{mid}",
            curve_json=_curve(_months(*span), annual) if curves else "[]",
        )])
        for step in {
            "registered": (),
            "dev-eligible": ("dev-eligible",),
            "promoted": ("dev-eligible", "promoted"),
            "test-failed": ("dev-eligible", "promoted", "test-failed"),
            "rejected": ("rejected",),
        }[status]:
            store.update_method(conn, mid, status=step)


# ------------------------------------------------------------------ the rule, stated


def test_the_minimum_is_four_and_the_coin_flip_table_is_the_binomial_tail():
    """MIN_FOLDS = 4, and COIN_FLIP_NULL is P(X > n/2) for X ~ Bin(n, 1/2), not a typed-in table.

    The table is the argument for 4 over 3: a strict majority of an odd count is a coin flip at
    every odd count, so "at least 3" would admit evidence no stronger than one fold.
    """
    assert hardgate.MIN_FOLDS == 4
    for n, stated in hardgate.COIN_FLIP_NULL:
        tail = sum(comb(n, k) for k in range(n // 2 + 1, n + 1)) / 2 ** n
        assert stated == pytest.approx(tail, abs=5e-5), n
    odd = {n: p for n, p in hardgate.COIN_FLIP_NULL if n % 2 == 1}
    assert set(odd.values()) == {0.5}
    assert dict(hardgate.COIN_FLIP_NULL)[4] < 0.5


def test_the_module_answers_the_four_open_questions():
    """The brief asked for the reason beside each answer, in the code. This is that check."""
    doc = hardgate.__doc__ or ""
    for marker in ("(D2)", "(D3)", "(D4)", "(D6)"):
        assert marker in doc
    assert "no override path" in doc.lower()


# ------------------------------------------------------------------ the geometry


def test_the_benchmark_cuts_four_folds_and_the_geometry_is_shared(conn):
    _benchmark(conn)
    geo = hardgate.geometry(conn)
    assert len(geo.folds) == hardgate.MIN_FOLDS
    assert geo.folds[0].eval_start.year == 2003
    assert geo.folds[-1].eval_end.year == 2015
    assert geo.bench[0][0] == date(1993, 2, 28)


def test_a_missing_benchmark_refuses_and_names_ref_spy_hold(conn):
    """D7: fail closed, and say it is the lab's fixture that is missing, not the method."""
    _method(conn)
    with pytest.raises(store.LabError) as e:
        hardgate.geometry(conn)
    assert regime.BENCH_CANDIDATE in str(e.value)
    with pytest.raises(store.LabError) as e:
        hardgate.check(conn, "M0001")
    assert regime.BENCH_CANDIDATE in str(e.value)


# ------------------------------------------------------------------ the fold record


def test_a_winning_curve_takes_every_fold(conn):
    _benchmark(conn)
    _method(conn, annual=0.15)
    rec = hardgate.fold_record(conn, "M0001")
    assert isinstance(rec, wf.Record)
    assert (rec.won, len(rec.scored)) == (4, 4)
    assert rec.majority
    assert hardgate.fold_summary(conn, "M0001") == "4 of 4 folds"
    hardgate.check(conn, "M0001")  # does not raise


def test_a_losing_curve_is_refused_and_the_message_names_the_record(conn):
    _benchmark(conn)
    _method(conn, annual=0.02)
    rec = hardgate.fold_record(conn, "M0001")
    assert rec.won == 0 and not rec.majority
    with pytest.raises(store.LabError) as e:
        hardgate.check(conn, "M0001")
    assert "0 of 4 folds" in str(e.value)
    assert "override" in str(e.value)


def test_a_short_curve_is_refused_even_when_it_wins_every_fold_it_is_scored_on(conn):
    """**The case that justifies the "every fold" clause** (D2), measured, not supposed.

    A curve starting 2007-04-10 -- ``H-P7A-F10``'s real shape -- is scoreable on 2 of the 4 folds
    and wins both. ``Record.majority`` is therefore **True**: the brief's literal rule, "wins a
    majority of its walk-forward folds", would promote it on two looks at the post-crisis decade
    alone. It is refused because it is scoreable on fewer folds than the geometry yields, which
    is the whole content of "fail closed on thin evidence".
    """
    _benchmark(conn)
    _method(conn, annual=0.15, span=(date(2007, 4, 10), date(2015, 10, 16)))
    rec = hardgate.fold_record(conn, "M0001")
    assert (rec.won, len(rec.scored)) == (2, 2)
    assert rec.majority  # and it is refused anyway
    with pytest.raises(store.LabError) as e:
        hardgate.check(conn, "M0001")
    assert "2 of the 4" in str(e.value)


def test_a_method_with_no_curve_is_refused_not_crashed(conn):
    """`walkforward.evaluate` raises ValueError on an empty curve; the gate must say a sentence."""
    _benchmark(conn)
    _method(conn, curves=False)
    with pytest.raises(store.LabError):
        hardgate.fold_record(conn, "M0001")
    with pytest.raises(store.LabError):
        hardgate.check(conn, "M0001")


# ------------------------------------------------------------------ the kin walk (D4)


def test_a_failed_sibling_in_the_family_blocks(conn):
    _benchmark(conn)
    _method(conn, "M0001", family="trend", annual=0.15)
    _method(conn, "M0002", family="trend", status="test-failed")
    assert hardgate.failed_kin(conn, "M0001") == ("M0002",)
    assert hardgate.family_state(conn, "M0001") == "blocked: M0002 read test-failed"
    with pytest.raises(store.LabError) as e:
        hardgate.check(conn, "M0001")
    assert "M0002" in str(e.value)


def test_a_failed_grandparent_blocks_even_when_the_family_is_clean(conn):
    """M0030's live case: family clean, parent and grandparent both test-failed (D4)."""
    _benchmark(conn)
    _method(conn, "M0021", family="blended", status="test-failed")
    _method(conn, "M0029", family="satellite", parent="M0021", status="test-failed")
    _method(conn, "M0030", family="core-satellite", parent="M0029", annual=0.15)
    assert hardgate.failed_kin(conn, "M0030") == ("M0021", "M0029")
    with pytest.raises(store.LabError) as e:
        hardgate.check(conn, "M0030")
    assert "M0021" in str(e.value) and "M0029" in str(e.value)


def test_a_failed_descendant_does_not_reach_up_through_parent_id(conn):
    """Not the connected component (D4): a child's failure is caught by `family`, not by walking
    down. A child in a *different* family does not block its parent."""
    _benchmark(conn)
    _method(conn, "M0001", family="trend", annual=0.15)
    _method(conn, "M0002", family="elsewhere", parent="M0001", status="test-failed")
    assert hardgate.failed_kin(conn, "M0001") == ()
    hardgate.check(conn, "M0001")  # does not raise


def test_the_method_itself_is_never_its_own_kin(conn):
    _benchmark(conn)
    _method(conn, "M0001", family="trend", status="test-failed")
    assert hardgate.failed_kin(conn, "M0001") == ()


def test_a_clean_kin_reads_clean_and_an_unknown_method_raises(conn):
    _benchmark(conn)
    _method(conn, "M0001", family="trend", annual=0.15)
    assert hardgate.failed_kin(conn, "M0001") == ()
    assert hardgate.family_state(conn, "M0001") == "clean"
    with pytest.raises(store.LabError):
        hardgate.failed_kin(conn, "M9999")


def test_a_parent_cycle_does_not_hang_the_kin_walk(conn):
    """`methods.parent_id` has no cycle constraint. The walk carries a `seen` set."""
    _benchmark(conn)
    _method(conn, "M0001", family="a", annual=0.15)
    _method(conn, "M0002", family="b", parent="M0001", annual=0.15)
    with conn:
        store.update_method(conn, "M0001", parent_id="M0002")
    assert hardgate.failed_kin(conn, "M0002") == ()


# ------------------------------------------------------------------ what other phases call


def test_summary_never_raises_and_says_why_it_is_blank(conn):
    """`lab status` (phase 3) calls this once per dev-eligible method and must keep printing."""
    _method(conn, "M0001")  # no benchmark at all
    line = hardgate.summary(conn, "M0001")
    assert regime.BENCH_CANDIDATE in line
    _benchmark(conn)
    _method(conn, "M0002", family="trend", annual=0.15)
    assert hardgate.summary(conn, "M0002") == "4 of 4 folds; kin clean"


def test_a_shared_geometry_gives_the_same_answer_as_a_fresh_one(conn):
    """Phase 3 computes the geometry once and passes it down; it must change no number."""
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    geo = hardgate.geometry(conn)
    assert hardgate.fold_summary(conn, "M0001", geo) == hardgate.fold_summary(conn, "M0001")
    assert hardgate.summary(conn, "M0001", geo) == hardgate.summary(conn, "M0001")


# ------------------------------------------------------------------ de-funding


def test_a_lump_sum_trial_has_no_deposits(conn):
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    row = conn.execute(
        'SELECT n, candidate_id, start, "end", curve_json FROM trials WHERE method_id = ?',
        ("M0001",),
    ).fetchone()
    curve = [(date.fromisoformat(d), float(v)) for d, v in json.loads(row["curve_json"])]
    assert hardgate.trial_deposits(conn, row, curve) == {}


def test_a_funded_trial_is_de_funded_before_it_is_scored(conn):
    """Every trial from M0032 on is funded; reading a deposit as edge is insight 72/75's bug.

    Two claims, both measured. The reconstruction credits ``amount_idr / INITIAL_IDR`` -- 0.5 --
    per deposit, **except** the one landing on or before the curve's first point, which
    ``regime.bucket`` drops because it is already in the opening balance rather than growth over
    it: 237 deposits, 236 credited steps, 118.0 and not 118.5. And the de-funding reaches the
    gate: the same method's record changes once the funding row exists. (It changes a long way --
    half the opening balance arriving every month for twenty years is not a realistic schedule
    against a curve that opens at 1.0, which is exactly why M0032's real curve opens at 1.5. The
    test asserts that it changed, not by how much.)
    """
    from seer_engine.sim.contributions import OWNER_MONTHLY

    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    unfunded = hardgate.fold_summary(conn, "M0001")
    assert unfunded == "4 of 4 folds"

    row = conn.execute(
        'SELECT n, candidate_id, start, "end", curve_json FROM trials WHERE method_id = ?',
        ("M0001",),
    ).fetchone()
    due = OWNER_MONTHLY.dates_in(date(1996, 1, 2), date(2015, 10, 16))
    with conn:
        store.insert_funding(conn, [store.FundingRow(
            trial_n=int(row["n"]), mwr=0.11, spy_tr_mwr=0.08, deposits_usd=1.0,
            deposits_n=len(due),
            schedule="+5,000,000 IDR on the 25th of each month", measured="test",
        )])

    curve = [(date.fromisoformat(d), float(v)) for d, v in json.loads(row["curve_json"])]
    deposits = hardgate.trial_deposits(conn, row, curve)
    assert len(deposits) == len(due) - 1  # the first lands in the opening balance
    assert sum(deposits.values()) == pytest.approx(0.5 * (len(due) - 1), rel=1e-9)
    assert set(deposits) <= {d for d, _v in curve}  # keyed on curve-step end dates
    assert hardgate.fold_summary(conn, "M0001") != unfunded


def test_a_moved_contribution_schedule_refuses_rather_than_guesses(conn):
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    row = conn.execute(
        'SELECT n, candidate_id, start, "end", curve_json FROM trials WHERE method_id = ?',
        ("M0001",),
    ).fetchone()
    with conn:
        store.insert_funding(conn, [store.FundingRow(
            trial_n=int(row["n"]), mwr=0.11, spy_tr_mwr=0.08, deposits_usd=1.0, deposits_n=3,
            schedule="+5,000,000 IDR on the 25th of each month", measured="test",
        )])
    curve = [(date.fromisoformat(d), float(v)) for d, v in json.loads(row["curve_json"])]
    with pytest.raises(store.LabError) as e:
        hardgate.trial_deposits(conn, row, curve)
    assert "cannot be de-funded safely" in str(e.value)


# ------------------------------------------------------------------ what the gate judges


def test_the_gate_is_silent_for_every_status_but_dev_eligible(conn):
    """`dev-eligible -> promoted` is the only edge into `promoted` that store.TRANSITIONS admits,
    so gating it gates every promotion -- and `promote_method`, one line later, refuses a wrong
    status with the better message it already has. A `promoted` method already cleared this gate
    and its pre-registration is a promise (D3), so a repair re-run is not re-judged."""
    _method(conn, "M0001", status="registered")  # no benchmark: the gate would refuse if it ran
    hardgate.check(conn, "M0001")
    _method(conn, "M0002", family="b", status="rejected")
    hardgate.check(conn, "M0002")
    _method(conn, "M0003", family="c", status="promoted")
    hardgate.check(conn, "M0003")
    with pytest.raises(store.LabError):
        hardgate.check(conn, "M9999")


# ------------------------------------------------------------------ the refusal at the CLI


def _cli(tmp_path, db, prereg_dir, method="M0001"):
    from seer_engine.commands import lab as lab_cmd

    return lab_cmd.run(argparse.Namespace(
        db=db, lab_command="promote", method=method, dir=prereg_dir,
    ))


def test_lab_promote_exits_2_and_writes_nothing_when_the_folds_are_lost(tmp_path):
    db, prereg_dir = tmp_path / "lab.sqlite", tmp_path / "prereg"
    c = store.connect(db)
    _benchmark(c)
    _method(c, "M0001", annual=0.02)
    before = db.read_bytes()
    c.close()

    assert _cli(tmp_path, db, prereg_dir) == 2
    assert not prereg_dir.exists()
    assert db.read_bytes() == before


def test_lab_promote_exits_2_and_writes_nothing_when_the_kin_has_failed(tmp_path):
    db, prereg_dir = tmp_path / "lab.sqlite", tmp_path / "prereg"
    c = store.connect(db)
    _benchmark(c)
    _method(c, "M0001", family="trend", annual=0.15)
    _method(c, "M0002", family="trend", status="test-failed")
    before = db.read_bytes()
    c.close()

    assert _cli(tmp_path, db, prereg_dir) == 2
    assert not prereg_dir.exists()
    assert db.read_bytes() == before


def test_lab_promote_exits_2_on_thin_evidence(tmp_path):
    db, prereg_dir = tmp_path / "lab.sqlite", tmp_path / "prereg"
    c = store.connect(db)
    _benchmark(c)
    _method(c, "M0001", annual=0.15, span=(date(2007, 4, 10), date(2015, 10, 16)))
    c.close()

    assert _cli(tmp_path, db, prereg_dir) == 2
    assert not prereg_dir.exists()


def test_there_is_no_override(tmp_path):
    """No flag, no environment variable, no 'promote anyway'. The brief forbids one in the
    sentence that decides the rule, and an override is the mechanism that produced 0-for-5."""
    import inspect
    import os

    src = inspect.getsource(hardgate)
    for word in ("force", "override", "skip_gate", "SEER_SKIP", "getenv", "environ"):
        assert word not in src.replace("no override", "").replace("There is no override", "")
    assert not any(k.startswith("SEER_HARDGATE") for k in os.environ)
```

**Impact:** the gate's behaviour is pinned. `test_there_is_no_override` is the invariant that
survives a future reader's good intentions.

---

## Verification

**Build:**

```
cd /home/miftah/.worktrees/seer/lab-hard-gate/engine && \
  PYTHONPATH=$PWD/src /home/miftah/seer/engine/.venv/bin/python -c "import seer_engine.commands.lab, seer_engine.lab.hardgate"
```

**Tests:**

```
cd /home/miftah/.worktrees/seer/lab-hard-gate/engine && \
  PYTHONPATH=$PWD/src /home/miftah/seer/engine/.venv/bin/python -m pytest -q tests/test_lab_*.py
```

`PYTHONPATH` is not optional. Without it pytest silently tests the **main checkout**, not this
branch, and the whole run is meaningless. The worktree has no `.venv` of its own, which is why
the interpreter path points at the main checkout.

Baseline to beat, measured at `7708350` in this worktree:

```
tests/test_lab_prereg.py tests/test_lab_walkforward.py tests/test_lab_status.py -> 68 passed
tests/test_lab_prereg.py alone                                                  -> 31 passed
```

After this phase: `68 passed` for the same three files (all 31 prereg tests still pass, bodies
byte-identical), plus `test_lab_hardgate.py`'s own tests.

**Lint:**

```
cd /home/miftah/.worktrees/seer/lab-hard-gate/engine && /home/miftah/seer/engine/.venv/bin/python -m ruff check src tests
```

**Manual check — `lab regime` and `lab walkforward` still agree with themselves.** These two are
the only behavioural risk in the `_trial_deposits` move, and neither has a test that would catch a
regression. Check against a **copy** of the database, never the real one — `lab` migrates
`lab.sqlite` on connect and even a read dirties it:

```
cp /home/miftah/seer/lab/lab.sqlite "$SCRATCH/lab-copy.sqlite"
cd /home/miftah/.worktrees/seer/lab-hard-gate/engine && \
  PYTHONPATH=$PWD/src /home/miftah/seer/engine/.venv/bin/python -m seer_engine lab \
    --db "$SCRATCH/lab-copy.sqlite" walkforward > "$SCRATCH/after.txt"
```

Run the same command from the main checkout against a second copy and `diff` the two outputs.
They must be identical: the move changes no arithmetic. Then throw both copies away.

**Manual check — the gate's own reading of the real lab.** On the same scratchpad copy:

```
PYTHONPATH=$PWD/src /home/miftah/seer/engine/.venv/bin/python -c "
from seer_engine.lab import store, hardgate
c = store.connect('$SCRATCH/lab-copy.sqlite')
geo = hardgate.geometry(c)
print('folds', len(geo.folds))
for r in c.execute(\"SELECT id FROM methods WHERE status='dev-eligible' ORDER BY id\"):
    print(r['id'], hardgate.summary(c, r['id']))
"
```

Expected, from the plan's measurement — all seven refused by the conjunction:

```
M0007 3 of 4 folds; kin blocked: M0022 read test-failed
M0011 2 of 4 folds; kin blocked: M0022 read test-failed
M0019 3 of 4 folds; kin blocked: M0002 read test-failed
M0020 3 of 4 folds; kin blocked: M0002 read test-failed
M0024 2 of 4 folds; kin clean
M0030 2 of 4 folds; kin blocked: M0021, M0029 read test-failed
M0033 3 of 4 folds; kin blocked: M0022 read test-failed
```

Discard the copy afterwards. **Do not commit it, and do not run any `lab` command against
`lab/lab.sqlite` itself.**

**Exit criteria:**

- `lab promote` on a method that loses the folds exits 2, names the record (`"2 of 4 folds"`),
  and leaves `docs/lab/prereg/` and the database byte-identical
- `lab promote` on a method whose family or ancestry reads `test-failed` exits 2 and names the
  member by id
- `lab promote` on a method scoreable on fewer folds than the geometry yields exits 2 and says so
- `lab promote` on a method with a majority and clean kin behaves exactly as before
- every test body in `test_lab_prereg.py` is unchanged and all 31 pass;
  `test_lab_walkforward.py` and `test_lab_status.py` pass unchanged
- `grep -n "_trial_deposits" engine/src/seer_engine/commands/lab.py` returns nothing
- `hardgate.py`'s docstring answers D2, D3, D4 and D6, each with its reason — pinned by
  `test_the_module_answers_the_four_open_questions`
- no flag, environment variable or keyword skips the gate — pinned by `test_there_is_no_override`

---

## Handoffs

**To Phase 2 (`prereg`):**
- Phase 2 calls `hardgate.fold_record(conn, method_id)`, `hardgate.failed_kin(conn, method_id)`
  and `hardgate.MIN_FOLDS` — **not** `fold_summary` / `family_state`, because it names the folds
  won, the folds scored and the pick's stability as three separate words (R6) and
  `Record.summary()` conveys stability by absence. Signatures and return shapes are in the
  Interface Contract. Both functions are **strict**: they raise `store.LabError`. That is safe,
  because `_promote` calls `hardgate.check` immediately before `prereg.promote_method`, so by the
  time `promote_method` runs, both are computable; phase 2 catches them anyway and records what
  went wrong rather than raising after the decision.
- `prereg.promote_method` itself does **not** call `hardgate.check` — D1. It calls the two
  *recording* functions only.
- Phase 1 edited three **helpers** in `tests/test_lab_prereg.py` (`_real_method`, and new
  `_months` / `_curve` / `_benchmark`). Rebase additions on the post-phase-1 file and reuse
  `_benchmark()` and `_curve()` rather than writing new ones. No test body changed.
- Phase 1 does **not** add the D3 printed note to `lab test` / `preflight_test`. Reconciliation
  **assigned it to phase 2**, which already carries R3 and the "a pre-registration is a promise"
  prose: phase 2 owns `engine/src/seer_engine/lab/runner.py` and the test for it. It must change
  no exit code and no transition — a sentence, not a gate.

**To Phase 3 (`lab status`, skills, docs):**
- Call `hardgate.geometry(conn)` **once** per `lab status` (inside a `try: except store.LabError:`
  — a lab with no benchmark must still print a status), then `hardgate.summary(conn, mid, geo)`
  per dev-eligible method. `summary` never raises. The per-method cost is parsing that method's
  recorded curves plus four slices; measured as SQL-and-arithmetic, well inside invariant 4's one
  second for the lab's seven dev-eligible methods.
- The measured counts, now in the index: `test_lab_prereg.py` holds **31** tests, not 29, and the
  `prereg` + `walkforward` + `status` baseline is **68 passed**. Phase 3's `package_readme.md` and
  plan edits must use those numbers, and quote the count rather than the seconds.
- `docs/plans/WALK_FORWARD_EVALUATION_PLAN.md`'s D6 note (no path back, and why the need will
  come) is written in `hardgate.py`'s docstring; phase 3 mirrors it into the plan.

**Deliberately not done, and not mine:**
- `commands/lab.py:1863-1866` — `_walkforward`'s own inline kin query is `family` **only** (and
  `LIMIT 1`, so it can name only one failed relative), while the gate walks `family ∪ ancestors`.
  It feeds `wf.buy_signal`, which is a *report*, not the gate. The buy signal is a separate,
  owner-decided rule about when to buy data; changing it is beyond this brief. **Deliberately
  left** — recorded as index **Decision D9**, and phase 3 states the asymmetry where a reader
  meets it (the explore skill's step 0b). Worth a follow-up card, not a change here.
- `wf.BUY_CONDITIONS` says `"no family member has test-failed"`; under D4 the gate's condition is
  wider. Same decision, same follow-up.
- `lab/walkforward.py` is untouched. `Record.majority`, `Record.scored` and `Record.summary` are
  read exactly as they are.

---

## Rollback

`git revert` this phase's single commit on `feature/lab-hard-gate`.

- `lab promote`'s pre-gate behaviour is restored exactly: `hardgate.py` and
  `test_lab_hardgate.py` disappear, `_trial_deposits` moves back into `commands/lab.py`, and
  `_real_method` goes back to its curve-less fixture.
- Nothing persisted depends on the gate. It writes no file, inserts no row, moves no status and
  records no insight, so there is no state outside git to undo.
- `lab/lab.sqlite`, `web/data/lab.json`, `docs/lab/prereg/*.md`, Neon, Vercel and the research
  store are untouched by this phase in every path, including a refusal.
- Reverting phase 1 **after** phase 2 has landed breaks phase 2: `prereg.promote_method` imports
  `hardgate`. Revert 2 first, or revert both together.

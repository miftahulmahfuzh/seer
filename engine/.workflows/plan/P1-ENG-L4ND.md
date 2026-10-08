> Adopted from `LAB_REALISTIC_GATE_PLAN.md` phase 1. Source: `.workflows/plan/lab-realistic-gate/phase-1.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 1: Count the looks the data supports, and publish today's verdict

**Plan set:** `LAB_REALISTIC_GATE_PLAN.md`
**Analysis:** `20261008-135044-N7K3_code_analyzer.md`
**Satisfies:** R1 — the luck gate stops counting every variant run as an independent look, so
re-running one method no longer perturbs every other method's verdict, and the published snapshot
states the verdict the bars in force now actually produce.
**Depends on:** none. **Phase 2 depends on this phase** (see *Interface Contract*), so the set is
sequential: 1 -> 2 -> 3.

**Ownership rule applied here:** *each phase repairs what it itself breaks.* The policy change is
what turns these tests red, so **all eight affected test modules are phase 1's**, and the exit
criterion is the full engine suite green on phase 1's files alone.
**Difficulty:** HARD
**Package:** `engine.lab` (plus `web/data`, `docs/lab/prereg`, `.claude/skills`)
**Pre-sweep commit sha:** `2b493ee4d79b0dd9bd70a6baadd967ca0c1bb68d` — the blob to restore
`lab/lab.sqlite` from if the status moves have to be undone (the trigger makes status forward-only).

---

## Goal

`store.DSR_POLICY` becomes `"methods"`, so the lab deflates the Sharpe by the number of distinct
ideas it has looked at (28 on the committed database) instead of the number of trial rows it has
written (126), floored at the measured participation ratio so it can never claim fewer independent
looks than the curves show. `lab reevaluate` then moves every method whose recorded dev trials
clear at that N, and `lab stage` republishes `lab/lab.sqlite` and `web/data/lab.json` together.
Afterwards a new variation twin of an existing method adds **0** to N and a brand-new method adds
**1** — which is what makes re-running a method honest, and is the owner's objection removed at its
cause. The phase also fixes `lab --help`, which has been dead on `main` since a bare `%` entered an
argparse help string.

**Every one of the numbers below was measured in a throwaway copy of this worktree, with the
changes applied, the sweep run and both suites executed.** Where a number in the plan index or the
analysis disagrees with a number here, this file is the measurement and the index is the estimate —
the discrepancies are called out by name in *Measured reality vs. the brief*.

---

## Measured reality vs. the brief

Three things the brief predicted did not survive measurement. None of them changes what the phase
does; all three change what the phase must *say* and what it must *verify*.

1. **Six methods move, not two.** The brief's exit criterion names `M0002` and `M0007`. The sweep,
   run against the committed database under `methods`, moves **six**:

   | Method | moves | the dev candidates that unblock it |
   |---|---|---|
   | `M0002` | `rejected` -> `dev-eligible` | `M0002-REL-85` |
   | `M0007` | `rejected` -> `dev-eligible` | `M0007-N30`, `M0007-N20-RAW` |
   | `M0011` | `rejected` -> `dev-eligible` | `M0011-RAW20-TV12`, `-TV14`, `-TV16`, `M0011-RAW30-TV14`, `M0011-RAW20-TV14-N21` |
   | `M0019` | `rejected` -> `dev-eligible` | `M0019-RAW20-S15`, `M0019-TV14N21-S20` |
   | `M0024` | `rejected` -> `dev-eligible` | `M0024-SAME-N20-RANKSUM`, `M0024-SAME-N20-BLEND-RM` |
   | `M0030` | `rejected` -> `dev-eligible` | `M0030-C70T`, `M0030-C50T` |

   `M0008` does **not** move and `M0022` was already `dev-eligible`, exactly as the brief says.
   Published `byStatus` goes `rejected 27 -> 21`, `dev-eligible 2 -> 8`; 16 dev trials flip
   `eligibleNow`. This is a loosening of a gate that exists to prevent self-deception and the
   owner should see the full list, not a two-name subset.

2. **The blast radius is eight test modules, not six.** Flipping the constant alone turns **41**
   engine tests red across `test_lab_gate_policy` (10), `test_lab_prereg` (15),
   `test_lab_remeasure` (7, six of which are the `batches_of` source bug below),
   `test_lab_status` (4), `test_lab_runner` (2), `test_lab_npolicy` (1), `test_lab_snapshot` (1)
   and `test_lab_store` (1). **All eight are phase 1's**, under the set's rule that a phase repairs
   what it breaks. Two of the six modules the brief lists (`test_lab_snapshot.py:373`,
   `test_lab_prereg.py:439`) need **no edit at all** — both already assert against
   `store.DSR_POLICY` rather than against the literal, which is the property that was supposed to
   make them survive, and it did. That is the shape every other assertion is moved toward.

   **How each module is repaired, and why.** Two kinds of test, two treatments:

   | Module | treatment | why |
   |---|---|---|
   | `test_lab_gate_policy.py` | **explicit literals**, split by fixture (`committed_unpinned` vs `committed`, plus `at_all_trials`) | its job *is* to pin the shipped policy and to describe a frozen N=110 database. Both numbers must be typed or the test asserts nothing. |
   | `test_lab_npolicy.py` | **explicit literal**, plus an equality to `store.DSR_POLICY` | same: it pins the two constants' agreement. |
   | `test_lab_runner.py` | **re-expressed** — `store.pending_gate(conn, m.id, len(m.candidates))` taken before the run; row count asserted separately | it tests what `trial_rows` records, not which policy is shipped. No literal N survives, so phase 2's funding work never has to touch it for N reasons. |
   | `test_lab_remeasure.py` | **re-expressed** — the N is read back off `trials.n_trials_at_run` | `remeasure`'s whole job is to rebuild inputs that reproduce the *recorded* DSR, so the recorded N is the only honest source for it. |
   | `test_lab_store.py` | **re-expressed** — `at=store.Gate(n=store.dev_trial_count(conn), policy="all-trials")` | `best_dev_eligible` takes an `at=`, so the gate can be named instead of inherited. Strictly better than a pin: it names no shipped constant and survives any future policy move. |
   | `test_lab_prereg.py` | **autouse `all-trials` pin** | `prereg.promote_method` and the `lab promote` CLI resolve the gate internally with no `at=` to inject, and the fixtures hold several *variants of one method*, so no reshaping makes the two policies agree. The pin is not a workaround: every trial these fixtures insert carries `n_trials_at_run` equal to the fixture's dev row count, which is what a lab recorded under `all-trials` looks like and nothing else. |
   | `test_lab_status.py` | **autouse `all-trials` pin** | same — `lab status` resolves the gate inside the command. The module's own comment under `_trial` already states the assumption ("`n_trials_at_run=2` is load-bearing … the gate resolves to N = 2 under `all-trials`"); the fixture makes it explicit instead of inherited. |
   | `test_lab_snapshot.py` | **no edit** | goes green on Step 10's `lab stage`. |

   The pin is used in exactly two modules, and only where the production path under test resolves
   the gate itself. Everywhere the call site accepts an `at=` or exposes a projection, the
   assertion is derived instead.

3. **`lab remeasure` breaks at the source, not in its tests.** `remeasure.batches_of` enforces
   `count(preceding dev trials) + len(batch) == n_trials_at_run`. That equality *is* the
   `all-trials` projection. Under `methods` every batch recorded after this phase lands is refused
   with a `LabError`, and no test edit can fix it because it is a production refusal. `remeasure.py`
   is owned by no other phase in this set, so phase 1 fixes it. Without this change
   `test_lab_remeasure` fails **7** tests; with it, **1** — a literal `56`, re-expressed in Step 10c.

---

## Interface Contract

**Deletes:** nothing.

**Renames:** nothing.

**Creates:**
- `at_all_trials` fixture (`engine/tests/test_lab_gate_policy.py`, after `_clean_gate_cache`)
- `committed_unpinned` fixture (`engine/tests/test_lab_gate_policy.py`) — the old `committed` body;
  `committed` becomes a thin pinning wrapper over it
- `_every_parser` helper + `test_every_parsers_help_text_formats_without_raising`
  (`engine/tests/test_cli.py`, appended)

**Value changes (behaviour-bearing):**
- `store.DSR_POLICY`: `"all-trials"` -> `"methods"` (`engine/src/seer_engine/lab/store.py:165`).
  **Resolves to N = 28 on `lab/lab.sqlite` and N = 23 on `engine/tests/fixtures/lab_n110.sqlite`.**
- `npolicy.DEFAULT_POLICY`: `"all-trials"` -> `"methods"`
  (`engine/src/seer_engine/lab/npolicy.py:53`). Must move with the one above; their equality is
  asserted from both sides.

**Signature changes:** none. One **behaviour** change with no signature change:
- `remeasure.batches_of(conn, trials)` — its second guard widens from
  `before + len(ns) == n_at_run` to `1 <= n_at_run <= max(before + len(ns), npolicy.DSR_MIN_N)`.
  Same arguments, same return type, same exception type; it now accepts batches recorded under any
  policy. **Phase 2's `test_lab_remeasure` work depends on this landing.**
- `remeasure.py` gains `npolicy` to its `from seer_engine.lab import store` line.

**Data changes (committed):**
- `lab/lab.sqlite` — six `methods.status` rows move `rejected` -> `dev-eligible`; six `transitions`
  rows appended; eight methods' `analysis` grown with `REEVALUATION_MARKER`. **No `trials` row is
  written**: `SELECT count(*) FROM trials` stays **128** and the sha256 over
  `(n, dsr, eligible, failed, n_trials_at_run)` stays
  `6137e3ded7ac5bd4360b2c4fd061054cca76a9b1e4d0896610d56230f129e13e` (verified identical before and
  after). `store.test_looks` stays **2**.
- `web/data/lab.json` — `gate.dsrPolicy` `"all-trials"` -> `"methods"`, `gate.dsrN` `126` -> `28`,
  `gate.dsrNBasis` rewritten, six `methods[].status`, 16 `trials[].eligibleNow`,
  `summary.byStatus`. **The `paper[]` block does not change** and must not: its `labStatus` is the
  status at the moment of promotion (all four entries read `"rejected"` / `"owner-override"`, M0022
  included, even though M0022 was already `dev-eligible` before this phase), i.e. frozen
  provenance, not a live read.

**Requires (from earlier phases):** none — phase 1 has no `depends_on`.

**Depended on by:** **phase 2.** Phase 2's funding work runs through `lab run`, whose trials are
stamped with the gate N; `lab remeasure` over such a batch is refused outright by
`remeasure.batches_of` until this phase's Step 3 lands, and that is a production `LabError` no test
edit can route around. The index DAG must therefore read `2 depends on 1`. Phase 2 also inherits
`test_lab_runner.py` and `test_lab_remeasure.py` in a state where no literal N remains, so its own
edits to those modules never collide with the policy.

**Leaves alone (owned by others):**
- `engine/src/seer_engine/lab/runner.py` — phase 2. Its module docstring (`:9`) and
  `trial_rows` docstring (`:191`, `:198`) both say the policy "ships as `all-trials`" and become
  stale on this phase's landing; correcting them is phase 2's, in the file phase 2 is already in.
  **Flagged to phase 2 explicitly** — the three line numbers are in *Handoffs*. They are prose
  only: no test reads them, so leaving them for one phase breaks nothing.
- `engine/src/seer_engine/backtest/dev.py` — phase 2.
- `.claude/skills/redo-sera-experiment/`, `.claude/skills/sera-the-explorer/SKILL.md` — phase 3.
- `store.DSR_MIN`, `tuning.MAX_DRAWDOWN`, `tuning.MIN_PROFIT_FACTOR`, `dev._MIN_TRADES` — only N
  moves in this plan set.
- Every recorded `trials` row, every `methods.analysis` already written, the paper roster's
  composition.

---

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/store.py` | modify | `:151-165` — `DSR_POLICY` to `"methods"` and the comment block that justifies it |
| `engine/src/seer_engine/lab/npolicy.py` | modify | `:47-53` — `DEFAULT_POLICY` to `"methods"`, same justification |
| `engine/src/seer_engine/lab/remeasure.py` | modify | `:66` import; `:224-235` docstring clause 2; `:250-256` the guard |
| `engine/src/seer_engine/commands/lab.py` | modify | `:236` — `0.1%` -> `0.1%%` in the `costs` subparser's `help=` |
| `engine/src/seer_engine/lab/prereg.py` | modify | `:156-162` — `gate_text` docstring's description of what N is |
| `engine/tests/test_lab_gate_policy.py` | modify | `:10-11` and a new docstring note; `:70` new `at_all_trials` fixture; `:415,475,514,593,604` signatures; `:617-631` the projection test; `:696-712` the two `committed` fixtures and the shipped-defaults test |
| `engine/tests/test_lab_npolicy.py` | modify | `:99-101` — the default-agreement assertion |
| `engine/tests/test_lab_gate_wording.py` | modify | `:19-21` — the docstring clause that says the row-count phrasings are correct |
| `engine/tests/test_lab_luck.py` | modify | `:150-159` — the D1 docstring that says the lever stays unpulled |
| `engine/tests/test_lab_runner.py` | modify | `:53` the projection test; `:85` the moments/trial N equality |
| `engine/tests/test_lab_remeasure.py` | modify | `:87` read the recorded N back; `:99,:102` use it |
| `engine/tests/test_lab_store.py` | modify | `:93-95` name the gate via `at=` |
| `engine/tests/test_lab_prereg.py` | modify | new autouse policy fixture before `conn` (`:23`) |
| `engine/tests/test_lab_status.py` | modify | new autouse policy fixture before `status` (`:25`) |
| `engine/tests/test_cli.py` | modify | `:5` import; appended regression test for `--help` formatting |
| `engine/package_readme.md` | modify | `:2442`, `:2480-2482`, `:2492`, `:2531` — five live claims that the shipped policy is `all-trials` |
| `.claude/skills/explore-and-experiment-new-method/SKILL.md` | modify | `:112-113` — what the explorer is told N is |
| `docs/lab/prereg/README.md` | modify | `:37` — what `n_trials_at_run` means |
| `web/app/sera/overview.ts` | modify | `:338-341` — the comment that justifies the scatter's colour rule from `all-trials` |
| `lab/lab.sqlite` | data | six statuses moved by `lab reevaluate`; staged by `lab stage` only |
| `web/data/lab.json` | data | regenerated by `lab stage` in the same step |

**Not touched:** `engine/tests/test_lab_snapshot.py` and `engine/tests/test_lab_prereg.py:439` —
measured: both already read `store.DSR_POLICY` and pass unchanged. `test_lab_snapshot.py`'s
`test_the_committed_snapshot_is_the_export_of_the_committed_database` goes green on Step 13's
`lab stage`, not on an edit.

---

## Implementation Steps

Steps 1–12 are code and documentation and are independent of the database. Step 13 is the data
step and is the only step that writes `lab/lab.sqlite`; Step 14 is the read-only hygiene that
applies to every other lab command. Run the data verification after Step 13, not before.

### Step 1: The constant

**File:** `engine/src/seer_engine/lab/store.py:151-165`
**Change:** replace the whole comment block and the constant. The comment is the record of why the
lever moved; it is not decoration.
**Code:** replace lines 151–165 with

```python
# The N the luck test deflates by, resolved through ``npolicy.effective_n``. ONE constant: the
# only place in the lab where the multiple-testing count is decided, read at call time by
# ``gate`` below rather than frozen into a row at run time.
#
# **Shipped as "methods" since 2026-10-08** (lab-realistic-gate R1), and NOT inherited from
# npolicy's own default. It was ``"all-trials"`` until then -- LAB_LUCK_GATE_PLAN.md Decision D1
# moved the threshold and deliberately left N alone, with the lever measured and ready.
#
# What pulled it is the owner's own observation: under ``all-trials`` every new variant run is
# counted as another independent look, so re-running one method moves every other method's
# verdict. That is a true statement about the policy, not about the methods -- and the lab's own
# estimator contradicts the independence it asserts. Measured on the committed database:
# 126 dev trial rows, 28 distinct methods, participation ratio 2.34, mean pairwise correlation
# 0.612. ``methods`` counts one look per distinct method, floored at ceil(participation ratio),
# so it can never claim fewer independent looks than the curves themselves show:
#     all-trials  N = 126     methods  N = 28     effective  N = 2
# Under ``methods`` a new variation twin of an existing method adds 0 to N and a brand-new method
# adds 1, instead of one per candidate -- which is what makes re-running a method honest.
#
# Set explicitly, and always passed as an argument to ``npolicy.effective_n``, so that nobody has
# to reason about which module's default wins. ``test_the_shipped_defaults_reproduce_todays_n``
# holds it to the distinct-method count of the fixture it reads.
DSR_POLICY = "methods"
```

**Impact:** every `store.gate` / `pending_gate` / `verdict` / `published_verdict` / `snapshot`
caller re-resolves N. Nothing is written by this step.

### Step 2: The module default moves with it

**File:** `engine/src/seer_engine/lab/npolicy.py:47-53`
**Change:** the two constants must agree by construction; the docstring already says so and must
keep saying so.
**Code:** replace lines 47–53 with

```python
# The policy a caller that does not name one gets. It is deliberately the same policy the lab
# actually ships -- ``store.DSR_POLICY = "methods"`` (lab-realistic-gate R1; it was
# ``"all-trials"`` until 2026-10-08) -- so that no code path can ever be deflated by an N the gate
# does not use. ``store`` sets its own constant explicitly and passes it to ``effective_n`` on
# every call, so this default is a belt beside that brace rather than the thing the gate relies
# on; the two agreeing is what makes a mistaken inheritance harmless instead of silent.
#
# **This constant moves whenever ``store.DSR_POLICY`` moves, and only then.**
# ``test_the_policy_names_are_a_closed_set`` pins the equality from this side and
# ``test_the_shipped_defaults_reproduce_todays_n`` from the other.
DEFAULT_POLICY: Policy = "methods"
```

**Impact:** none at runtime — `store.gate` always passes the policy explicitly. This is the belt.

### Step 3: `lab remeasure` stops refusing batches recorded under a non-row-count policy

**File:** `engine/src/seer_engine/lab/remeasure.py:66`, `:224-235`, `:250-256`

**3a. The import.** Line 66:

```python
from seer_engine.lab import npolicy, store
```

**3b. The docstring.** In `batches_of`, replace clause 2 (lines 224–228, ending at the closing
`"""`) with:

```
    2. ``1 <= n_trials_at_run <= count(dev trials with n < the batch's first n) + len(batch)``.
       The upper bound is the number of looks that existed when the batch was judged, which is
       exactly what the ``all-trials`` policy resolves to and is the ceiling of every other
       policy (``methods`` is ``max(distinct methods, ceil(participation ratio))`` and
       ``effective`` is ``max(2, round(participation ratio))``, and neither counts more than one
       look per row). A recorded N above it cannot describe this batch.

       **This was an equality until 2026-10-08** and had to stop being one when
       ``store.DSR_POLICY`` moved to ``"methods"`` (lab-realistic-gate R1): the row-count
       expression is the all-trials projection, so every batch recorded under any other policy
       would be refused by a guard that is testing the policy rather than the batch. The quantity
       this function actually reconstructs -- ``prior_sharpes``, and through it ``var_trials`` --
       is read from the rows with ``n < first`` and never from ``n_trials_at_run``, so widening
       the bound loses nothing: the recorded N is carried through verbatim into the rebuilt
       ``MomentsRow``, and ``remeasure`` already refuses and writes nothing when the DSR it
       recomputes from it does not reproduce the recorded one (``SHARPE_TOL``/``DSR_TOL``).
       ``npolicy.DSR_MIN_N`` widens the ceiling on the degenerate one-trial lab, where
       ``effective`` floors at 2 and the row count is 1.
    """
```

**3c. The guard.** Replace lines 250–256:

```python
        ceiling = max(before + len(ns), npolicy.DSR_MIN_N)
        if not 1 <= n_at_run <= ceiling:
            raise store.LabError(
                f"{method_id}: trial #{first} records N = {n_at_run}, but only {before} dev "
                f"trials precede it and its batch holds {len(ns)}, so at most {ceiling} looks "
                f"existed when it was judged. The recorded N does not describe this batch, so "
                f"the var_trials it was deflated by cannot be reconstructed honestly. "
                f"Nothing is backfilled"
            )
```

**Impact:** measured — `test_lab_remeasure` goes from 7 failures to 1 (the remaining one is a
literal `56`, re-expressed in Step 10c). Contiguity check 1 is untouched, so the guard that actually
catches "these rows were not written by one run" is unchanged.

### Step 4: `lab --help` stops crashing

**File:** `engine/src/seer_engine/commands/lab.py:236`
**Change:** argparse runs every `help=` string through `%`-interpolation
(`HelpFormatter._expand_help`), so `0.1%,` is parsed as a format spec and
`python -m seer_engine lab --help` dies with
`ValueError: unsupported format character ',' (0x2c) at index 70`. One doubled `%`.
**Code:** replace line 236 with

```python
        # `0.1%%`, not `0.1%`: argparse runs every `help=` string through %-interpolation
        # (`HelpFormatter._expand_help`), so a bare `%` is read as a format spec and
        # `lab --help` died with "unsupported format character ','". A doubled `%%` renders as
        # one `%`. `description=` below is NOT interpolated and must stay single.
        help="report only: a recorded method at Gotrade's real fees vs the flat 0.1%%, journaled",
```

**Do not touch** `description=` at `:237-242`, `:258-266` or the module docstring at `:16` and
`:47`: argparse does not interpolate `description` or `epilog`, and doubling the `%` there would
render a literal `%%` to the user.

**Completeness.** An AST sweep of every `help=` keyword argument under
`engine/src/seer_engine/` — constant parts and f-string format specs both — found **exactly one**
string that fails `%`-interpolation, the line above. The sweep is reproducible:

```bash
cd /home/miftah/.worktrees/seer/lab-realistic-gate/engine/src/seer_engine && \
/home/miftah/seer/engine/.venv/bin/python - <<'PY'
import ast, pathlib
bad = []
for p in sorted(pathlib.Path(".").rglob("*.py")):
    try: tree = ast.parse(p.read_text())
    except SyntaxError: continue
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call): continue
        for kw in node.keywords:
            if kw.arg != "help": continue
            text = "".join(c.value for c in ast.walk(kw.value)
                           if isinstance(c, ast.Constant) and isinstance(c.value, str))
            if "%" not in text: continue
            try: text % {}
            except Exception as e: bad.append((str(p), kw.value.lineno, str(e)))
print(bad or "clean")
PY
```

**Impact:** `lab --help` and `lab costs --help` work again. No behaviour change beyond the text.

### Step 5: `prereg.gate_text`'s docstring stops describing N as the row count

**File:** `engine/src/seer_engine/lab/prereg.py:156-162`
**Change:** the emitted string is already built from `store.DSR_POLICY` and needs no change; the
docstring that explains what the N *is* does.
**Code:** replace the paragraph at lines 156–162 with

```
    Two numbers, both of which decide the verdict and neither of which can be recovered from the
    other. The **threshold** moved on 2026-10-07 (design §7.1: the owner set ``DSR_MIN`` to 0.90),
    and a pre-registration written at 0.90 records a different claim from one written at 0.95, so
    the file has to say which. The **N** is whatever the policy named in ``store.DSR_POLICY``
    resolves to -- ``methods`` since 2026-10-08 (lab-realistic-gate R1): one look per distinct
    method with a dev trial, floored at the measured participation ratio, where it was one look
    per trial *row* before. Committed files written under either policy are correct records,
    because each names the policy it was written under; the number it came to that day is the
    multiple-testing count the deflation actually used.
```

**Impact:** documentation only. The two committed pre-registrations (`M0021.md`, `M0029.md`) keep
their `'all-trials'` text and must: each is a dated record of the rule in force when it was
written, and `docs/lab/prereg/` files are never rewritten.

### Step 6: The gate-policy tests

**File:** `engine/tests/test_lab_gate_policy.py`

**6a. Module docstring, claim 1** (`:10-11`). Replace with:

```
1. the shipped defaults -- DSR_MIN 0.90, DSR_POLICY "methods" -- resolve to N = 23 on the
   ``lab_n110`` fixture, which is its distinct-method count, and ``npolicy.DEFAULT_POLICY``
   agrees with ``store.DSR_POLICY`` by assertion from both sides;
```

**6b. Module docstring, a new note** immediately before the line
`**A note on the fixtures, and why most of them insert two trials.**`:

```
**A note on the policy these fixtures are judged under.** ``store.DSR_POLICY`` shipped as
``all-trials`` until 2026-10-08 and is ``methods`` since (lab-realistic-gate R1). Every claim
below about ``lab_n110.sqlite`` -- the three eligible candidates, M0007-N20-RAW's 0.8985,
F9's NULL DSR, M0011's divergence -- is a claim **at N = 110**, which is what ``all-trials``
resolves to on that frozen database and what its 110 rows were stamped with. The ``committed``
fixture therefore pins ``all-trials`` beside the database it describes; ``committed_unpinned``
is the same copy under the shipped policy and is used by exactly one test, the one whose
subject IS the shipped default. The hand-built labs below pin nothing and the few that need a
row-counting N take ``at_all_trials`` explicitly. Re-pointing the N=110 claims at the new
policy would delete the record of what the two moved bars did rather than test anything; the
new policy's verdict is measured on the LIVE database and published by ``lab stage``.

```

**6c. A new fixture**, inserted between `_clean_gate_cache` and `conn` (i.e. after `:68`):

```python
@pytest.fixture()
def at_all_trials(monkeypatch):
    """Judge this test's hand-built lab by its **row count** rather than by the shipped policy.

    For the tests whose fixture is two or three dev trials of one method, recorded at
    ``n_trials_at_run=2`` and judged at ``Gate(n=2)`` so that ``verdict``'s re-evaluation is the
    identity. The shipped ``methods`` policy resolves a one-method lab to
    ``max(1, ceil(participation ratio))``, which is 1 on two correlated curves -- and
    ``dev.deflated_sharpe`` is undefined below two looks, so the derived verdict would collapse
    to "no evaluable luck test" for a reason that has nothing to do with the rule under test.

    ``_clean_gate_cache`` is autouse and clears the memo at both ends, so nothing has to be
    cleared here.
    """
    monkeypatch.setattr(store, "DSR_POLICY", "all-trials")
```

**6d. Five signatures take it.** Change `(conn)` to `(conn, at_all_trials)` on exactly these, and
nothing else in the file:

| line | test |
|---|---|
| `:415` | `test_best_dev_eligible_keeps_its_contract_on_the_derived_verdict` |
| `:475` | `test_reevaluate_takes_the_edge_for_a_luck_only_rejection` |
| `:514` | `test_reevaluate_does_move_a_method_the_moved_drawdown_bar_unblocks` |
| `:593` | `test_reevaluate_is_idempotent_and_moves_only_from_rejected` |
| `:604` | `test_reevaluate_sweeps_every_rejected_method` |

`test_reevaluate_will_not_move_a_method_that_failed_an_owner_condition` (`:542` after the
insertions) and `test_the_independent_check_refuses_a_recorded_owner_inputs_whatever_the_verdict`
deliberately do **not** take it: both assert a *refusal*, which is correct under any N, and leaving
them on the shipped policy keeps a negative case running against it.

**6e. The projection test** (`:617-631`). Replace the whole function with:

```python
def test_pending_gate_reproduces_todays_n_under_the_shipped_policy(conn, monkeypatch):
    """What a batch about to be recorded is deflated by, under the policy the lab ships.

    This is R1's whole point, as one assertion: under ``methods`` a batch of variants of a
    method the lab already holds adds **nothing** to N, and a brand-new method adds exactly
    **one** -- so re-running a method no longer moves every other method's verdict. Under the
    policy that shipped until 2026-10-08 the same batch added one per candidate.
    """
    _method(conn, "M0001")
    with conn:
        store.insert_trials(conn, [_trial(method_id="M0001", candidate_id="M0001-A")])
    assert store.DSR_POLICY == "methods"
    assert store.pending_gate(conn, "M0001", 3).n == store.gate(conn).n      # known method
    assert store.pending_gate(conn, "M0009", 3).n == store.gate(conn).n + 1  # new method
    assert store.pending_gate(conn, "M0009", 0).n == store.gate(conn).n
    # ...and under `all-trials` it is still the row count: exactly the expression
    # `runner.trial_rows` used before the policy existed, kept here because the projection
    # machinery must keep working for every policy in POLICIES and not only for the shipped one.
    monkeypatch.setattr(store, "DSR_POLICY", "all-trials")
    assert store.pending_gate(conn, "M0001", 3).n == store.dev_trial_count(conn) + 3
    assert store.pending_gate(conn, "M0009", 3).n == store.dev_trial_count(conn) + 3
    for policy in npolicy.POLICIES:
        monkeypatch.setattr(store, "DSR_POLICY", policy)
        assert store.pending_gate(conn, "M0009", 5).n >= store.gate(conn).n, policy
```

**6f. The committed fixtures and the shipped-defaults test** (`:696-712`). Replace the `committed`
fixture and `test_the_shipped_defaults_reproduce_todays_n` with:

```python
@pytest.fixture()
def committed_unpinned(tmp_path):
    """A writable copy of the lab at phase 4, migrated, judged under the **shipped** policy.

    The original is never opened for writing. Exactly one test wants this -- the one whose
    subject is what the shipped defaults resolve to. Everything else wants ``committed``, which
    is this copy with the policy its 110 rows were recorded under pinned beside it.
    """
    path = tmp_path / "lab.sqlite"
    shutil.copyfile(LAB_AT_PHASE_4, path)
    c = store.connect(path)
    c.row_factory = sqlite3.Row
    yield c
    c.close()


@pytest.fixture()
def committed(committed_unpinned, monkeypatch):
    """``committed_unpinned``, judged under ``all-trials``: the policy this database describes.

    ``lab_n110.sqlite`` is frozen at commit feed608 -- 110 dev trials over 23 methods, every
    ``dsr`` and ``n_trials_at_run`` stamped by a ``lab run`` whose gate was the row count. Every
    claim the tests below make about it is a claim at N = 110. The shipped policy moved to
    ``methods`` on 2026-10-08 (lab-realistic-gate R1), which on this fixture resolves to N = 23
    and admits far more candidates; that is the new lab's verdict, measured on the live database
    and published by ``lab stage``, not a correction to this record.
    """
    monkeypatch.setattr(store, "DSR_POLICY", "all-trials")
    store._GATE_CACHE.clear()
    return committed_unpinned


def test_the_shipped_defaults_reproduce_todays_n(committed_unpinned):
    """Nobody should have to reason about which module's default wins.

    Both sides of the agreement, and what the shipped policy counts: one look per distinct
    method with a dev trial, floored at ceil(participation ratio). On this fixture that is 23
    methods across 110 trial rows (the floor, ceil 2.44 = 3, does not bind).
    """
    assert store.DSR_POLICY == "methods" == npolicy.DEFAULT_POLICY
    g = store.gate(committed_unpinned)
    assert g.policy == "methods"
    assert g.n == 23 == npolicy.dev_method_count(committed_unpinned)
    assert store.dev_trial_count(committed_unpinned) == 110, "the row count is unchanged"
```

`npolicy` is already imported at module scope (`:52`), so no import is added.

**Impact:** `RECORDED_VERDICT_DIGEST` and
`test_the_committed_lab_keeps_every_recorded_verdict_and_spends_no_look` need **no** change —
measured: `reevaluate` writes no `trials` row, so the digest over that fixture is a constant under
either policy. `test_the_old_bars_reproduce_todays_verdicts` already monkeypatches the policy to
`all-trials` itself and keeps working through the new `committed` wrapper.

### Step 7: The default-agreement test

**File:** `engine/tests/test_lab_npolicy.py:99-101`
**Code:** replace those three lines with

```python
    # Reconciled: this module's default is the policy the lab ships (store.DSR_POLICY), so no
    # caller can be deflated by an N the gate does not use. `test_the_shipped_defaults_
    # reproduce_todays_n` pins the other side. Asserted as an EQUALITY to the store's constant
    # rather than as two literals, so the next move of the lever cannot separate them silently;
    # the literal is kept beside it so that a move is still a deliberate edit here.
    assert npolicy.DEFAULT_POLICY == store.DSR_POLICY
    assert npolicy.DEFAULT_POLICY == "methods"
```

`store` is already imported at `:18`.

### Step 8: The prose that states the old rule

**8a. `engine/tests/test_lab_gate_wording.py:19-21`** — replace the first bullet of the
"Two things this test deliberately does **not** do" list with:

```
- It does not forbid "every dev trial" or "N = all lab trials", and it still does not, even
  though ``DSR_POLICY`` moved from ``all-trials`` to ``methods`` on 2026-10-08
  (lab-realistic-gate R1) and those phrases stopped being true of the live gate. The reason is
  the same one that keeps the design document out of ``SCANNED``: this guard's subject is the
  **threshold**, which is a number a document can state and get wrong, and it compares what it
  finds against ``store.DSR_MIN``. The policy has no number to compare -- it is a name -- and the
  documents that state it are swept for it by
  ``test_the_gate_text_is_built_from_the_constants_that_decide_the_verdict``, which requires the
  live ``store.DSR_POLICY`` to appear in the text rather than forbidding the dead one. Prose that
  still describes N as the row count is stale and was corrected where it states a live rule
  (``lab/prereg.py``'s ``gate_text`` docstring, ``docs/lab/prereg/README.md``, the explorer
  skill); extending this guard to policy *names* is a separate, bigger piece of work than a
  constant move, and is recorded as such rather than half-done here.
```

**8b. `engine/tests/test_lab_luck.py:150-159`** — replace the body of
`test_d1_three_candidates_clear_the_owners_bar_at_the_live_n_and_all_seven_at_n_23`'s docstring
after its first line with:

```
    At N = 110 -- what `all-trials` resolved to on the 110-trial lab this sample was measured
    from -- the two owner-set bars admit **three** candidates across the whole lab, the three
    highest-MAR books, asserted by name. Pulling the N lever as well (N = 23, the distinct-method
    count of that same lab) admits **every one of this sample's seven**, including
    `M0011-RAW20-TV12` at MAR 0.60; over the full database it admits 18 of the 25 luck-only
    trials rather than 3.

    **That was the argument for leaving the lever alone, and the lever has since been pulled.**
    `DSR_POLICY` moved to `methods` on 2026-10-08 (lab-realistic-gate R1) -- not because the
    number of admissions became acceptable, but because `all-trials` asserts an independence the
    lab's own estimator contradicts (participation ratio 2.34 over 126 curves, mean pairwise
    correlation 0.612) and because counting one look per variant *run* is what made re-running a
    method perturb every other method's verdict. This test is therefore the measured record of
    what that move costs, stated in advance, and both literals below are deliberate: 110 and 23
    are the two N's of the lab this sample was taken from, not the live gate's.
    """
```

The assertions below it are unchanged: they operate on a frozen `LUCK_ONLY` sample at literal N's
and are policy-independent. The test name stays — it is still accurate.

**8c. `.claude/skills/explore-and-experiment-new-method/SKILL.md:112-113`** — this is read by the
unattended explorer, so it must not tell an agent to count trial rows:

```
     2026-10-07 (design §7.1), and N is one look per distinct method in the lab, floored at the
     measured participation ratio (`DSR_POLICY = "methods"` since 2026-10-08; it was one look per
     dev trial row before). Both are printed by `lab status`; neither is yours to change. Read
     the N off `lab status` rather than counting trials: a method's variants are one look, so the
     trial-row count is no longer the N.
```

**8d. `docs/lab/prereg/README.md:37`** — replace the whole table row:

```
| `mar`, `dsr`, `n_trials_at_run` | the dev numbers it passed with. `n_trials_at_run` is **the N that trial's DSR was deflated by**, whatever the policy in force on its run date resolved to — the trial-row count for every row recorded before 2026-10-08 (`all-trials`), the distinct-method count after it (`methods`). It is not the row count and must not be read as one; the N the gate used is the one stated in `gate` |
```

**8e. `web/app/sera/overview.ts:338-341`** — the comment justifies the scatter's colour rule from a
property of `all-trials`; the property holds for every policy, so say that instead:

```typescript
  // ratchet, drawn. N only ever grows under every policy the gate ships -- `all-trials` counts
  // rows, `methods` (in force since 2026-10-08) counts distinct methods, and neither can shrink
  // -- and the DSR falls with it, so an eligible dot is always above the line: the colours can
  // disagree with the line, never contradict it.
```

No TypeScript changes: `web/lib/sera/types.ts` already carries `'methods'` in `DsrPolicy`,
`DSR_POLICIES` and `DSR_POLICY_LABEL` (`'one look per distinct idea'`), so the site renders the new
policy without a code change. Measured: the whole web suite (48 files, 626 tests) is green against
the regenerated `lab.json`.

### Step 9: The `--help` regression test

**File:** `engine/tests/test_cli.py` — add `import argparse` to the stdlib import block at `:5`,
then append to the end of the file:

```python

# --------------------------------------------------------------- every --help must format


def _every_parser(parser: argparse.ArgumentParser) -> list[argparse.ArgumentParser]:
    """``parser`` and every subparser reachable from it, depth-first.

    Subparsers are only reachable through the ``choices`` mapping of the ``_SubParsersAction``
    that created them, and the action list is private. That is the whole public surface argparse
    offers for walking a parser tree, and a test is the right place to use it: the alternative is
    to maintain a hand-written list of command names, which is exactly the thing that goes stale.
    """
    out = [parser]
    for action in parser._actions:
        choices = getattr(action, "choices", None)
        if isinstance(choices, dict):
            for child in choices.values():
                if isinstance(child, argparse.ArgumentParser):
                    out.extend(_every_parser(child))
    return out


def test_every_parsers_help_text_formats_without_raising():
    """`lab --help` crashed with `ValueError: unsupported format character ','`.

    argparse runs every ``help=`` string through %-interpolation in
    ``HelpFormatter._expand_help``, so a help string that writes a percentage as ``0.1%`` is
    read as a format spec and the whole ``--help`` dies. Nothing catches it: the string is only
    interpolated when that particular parser's help is rendered, so the bug sits in a subparser
    until somebody runs ``--help`` on it. One did, in ``lab costs``, for about a week.

    This walks every parser the CLI builds and formats each one's help. ``format_help()`` is the
    call ``--help`` makes just before it exits, so it does the interpolation without printing or
    raising ``SystemExit`` -- which is why this asserts on the formatting rather than on output.
    """
    parsers = _every_parser(cli.build_parser())
    assert len(parsers) > 10, (
        "the parser walk found almost nothing, so this test is not covering the subparsers it "
        "exists for -- check _every_parser against the argparse version in use"
    )
    broken = []
    for p in parsers:
        try:
            text = p.format_help()
        except Exception as exc:  # noqa: BLE001 -- the point is that NOTHING may escape
            broken.append(f"  {p.prog}: {type(exc).__name__}: {exc}")
            continue
        if not text.strip():
            broken.append(f"  {p.prog}: formatted to nothing")
    assert not broken, (
        "`--help` raises or renders empty for these parsers. A bare `%` in a `help=` string is "
        "the usual cause -- write it `%%`; `description=` and `epilog=` are not interpolated and "
        "must stay single:\n" + "\n".join(broken)
    )
```

**Impact:** verified both ways — green with Step 4 applied, and with Step 4 reverted it fails with
`assert not ["  seer_engine lab: ValueError: unsupported format character ',' (0x2c) at index 70"]`.

### Step 10: The modules that trip over N — re-expressed, no literal survives

Three modules fail only because they typed an N that was the row count. None of them is about the
policy, so none of them gets a pin: each is re-expressed against the store, which also means phase
2's funding work never has to touch them for N reasons.

**10a. `engine/tests/test_lab_runner.py:53`** — replace the test's opening (down to and including
the `n_trials_at_run` assertion) with:

```python
def test_run_records_trials_with_lab_wide_n(conn, data, tmp_path):
    """``n_trials_at_run`` is the lab-wide gate N projected over the batch -- NOT the row count.

    Derived from ``store.pending_gate`` rather than typed, because the two are only the same
    number under the ``all-trials`` policy. ``store.DSR_POLICY`` is ``methods``
    (lab-realistic-gate R1), so on this seeded lab the batch is judged at the distinct-method
    count plus one for M0001, while the row count goes to 56. Asserting the projection keeps
    this test about what ``trial_rows`` records -- the N the DSR was actually deflated by -- and
    keeps it true under whichever policy the lab ships next.

    The row count is asserted separately, so the two cannot be silently conflated again.
    """
    m = _method()
    projected = store.pending_gate(conn, m.id, len(m.candidates))
    ran = runner.run_method(conn, m, Path(__file__), data, git_sha="deadbeef", require_commit=False)
    assert [r.trial.candidate_id for r in ran] == ["M0001-A", "M0001-B"]
    rows = store.trials_of(conn, "M0001")
    assert [r["n"] for r in rows] == [55, 56]
    assert {r["n_trials_at_run"] for r in rows} == {projected.n}
    assert store.dev_trial_count(conn) == 56, "the row count is still the row count"
```

**10b. `engine/tests/test_lab_runner.py:85`** — replace the one assertion:

```python
        # The EQUALITY is the claim, not the number: the moments row and the trial row must
        # name the same N or the re-evaluation below is not the same measurement. The number
        # itself is whatever `store.DSR_POLICY` resolved to and is pinned in
        # `test_run_records_trials_with_lab_wide_n` against `store.pending_gate`.
        assert mom["n_at_run"] == r["n_trials_at_run"]
```

**10c. `engine/tests/test_lab_remeasure.py:87`** — after
`assert all(store.moments_of(conn, n) is None for n in numbers)`, insert:

```python
    # The N to reproduce is the one the run recorded, whatever `store.DSR_POLICY` resolved to --
    # read back off the rows rather than typed, because it is the row count only under
    # `all-trials` and `methods` has shipped since 2026-10-08 (lab-realistic-gate R1). The whole
    # point of `remeasure` is to rebuild inputs that reproduce the RECORDED dsr, so the recorded
    # N is the only honest source for it.
    recorded = {int(r["n_trials_at_run"]) for r in store.trials_of(conn, "M0001")}
    assert len(recorded) == 1, f"one batch, one N: {recorded}"
    (n_at_run,) = recorded
```

...and at `:99` and `:102` replace the literal `56` with `n_at_run`:

```python
        assert r.n_at_run == n_at_run
    for n in numbers:
        row = store.moments_of(conn, n)
        assert row is not None and row["n_at_run"] == n_at_run and row["t"] > 2
```

**10d. `engine/tests/test_lab_store.py:93-95`** — `best_dev_eligible` accepts an `at=`, so name the
gate the fixture was built for instead of inheriting one:

```python
    # Judge at the N these rows were RECORDED at -- `n_trials_at_run=4`, which is the dev row
    # count -- rather than at whatever `store.DSR_POLICY` resolves to. That is what makes
    # `store.verdict`'s re-evaluation the identity here, which is the condition the comment above
    # describes and which every assertion below rests on. Derived from the data, not typed, and
    # it names no shipped constant: the subject is `best_dev_eligible`'s ordering, not the gate.
    at = store.Gate(n=store.dev_trial_count(conn), policy="all-trials")
    best = store.best_dev_eligible(conn, "M0001", at=at)
    assert best["candidate_id"] == "M0001-A"  # the tie breaks on n, and the test trial is not it
    assert store.best_dev_eligible(conn, "M0002", at=at) is None
```

**Impact:** measured — those three modules go green (52 tests) and contain no literal N at all.

### Step 11: The two modules whose production path resolves the gate itself

`prereg.promote_method`, the `lab promote` CLI and `lab status` all call `store.best_dev_eligible`
/ `store.gate` with no `at=` to inject, and their fixtures hold several *variants of one method*,
so no reshaping makes `methods` and `all-trials` agree on N. These two modules get the policy named
beside the fixtures that assume it — which is more honest than inheriting it, not less.

Add this fixture to **both** modules. In `engine/tests/test_lab_prereg.py` put it immediately before
`def conn` (`:23`); in `engine/tests/test_lab_status.py` immediately before `def status` (`:25`).
The last paragraph differs per module and is marked.

```python
@pytest.fixture(autouse=True)
def _at_the_policy_these_fixtures_were_recorded_under(monkeypatch):
    """Judge every lab in this module under ``all-trials``, the policy its rows were stamped with.

    Not a convenience and not a workaround for the shipped policy: it is the one assumption these
    fixtures already encode. Every trial they insert carries ``n_trials_at_run`` equal to the
    fixture's dev row count, which is what a lab recorded under ``all-trials`` looks like and
    nothing else. ``store.verdict`` re-evaluates a recorded DSR **at the gate's current N**, so
    the re-evaluation is the identity -- and an eligibility assertion means what it says -- only
    while the gate resolves to the N stamped on the rows. Judging a recorded lab under the policy
    it was recorded under is the condition, and naming it here is strictly more honest than
    inheriting it from whatever ``store.DSR_POLICY`` happens to be.

    Since 2026-10-08 it no longer is: ``DSR_POLICY`` is ``methods`` (lab-realistic-gate R1), which
    on a one-method lab resolves to ``max(1, ceil(participation ratio))`` -- 1 when the fixtures
    record no curves -- and ``dev.deflated_sharpe`` is undefined below two looks. Every derived
    verdict here would then collapse to "no evaluable luck test" for a reason that has nothing to
    do with this module's subject. What the shipped policy resolves to is pinned where it belongs,
    in ``test_lab_gate_policy.py`` and ``test_lab_npolicy.py``.

    Autouse rather than folded into a connection fixture, because the paths under test resolve the
    gate themselves -- <PER-MODULE SENTENCE>
    """
    monkeypatch.setattr(store, "DSR_POLICY", "all-trials")
    store._GATE_CACHE.clear()
    yield
    store._GATE_CACHE.clear()
```

`<PER-MODULE SENTENCE>` in `test_lab_prereg.py`:

```
``prereg.promote_method`` and the ``lab promote`` CLI both call
    ``store.best_dev_eligible`` with no ``at=``, and several tests here open their own database.
```

`<PER-MODULE SENTENCE>` in `test_lab_status.py`:

```
``lab status`` resolves the gate inside the command, and every test here
    builds its own database and hands the path to the CLI.
```

**Impact:** measured — 15 `test_lab_prereg` tests and 4 `test_lab_status` tests go green.
`test_lab_prereg.py:439` is untouched and keeps passing on its own `store.DSR_POLICY` assertion.
Both modules keep exercising the ratchet and `sinks_at`: N still grows under `all-trials`, one row
at a time, which is what those tests are about.

### Step 12: `engine/package_readme.md` — five live claims

The readme states the old policy as the *live* rule in five places. Taken here rather than carded:
they are five one-paragraph edits, and a package reference that contradicts its own constant is the
exact failure mode `test_lab_gate_wording.py` exists to prevent for the threshold.

| line | change |
|---|---|
| `:2442` | `(`all-trials` = every dev trial in the lab, left there deliberately — §7.2)` -> `` (`methods` = one look per distinct method, floored at the measured participation ratio, since 2026-10-08; it was `all-trials` = every dev trial in the lab before that) `` |
| `:2480-2481` | "the literal reading of the design and what the lab **does today**" -> "…and what the lab **did until 2026-10-08**" |
| `:2482` | prefix the `methods` bullet with "**in force since 2026-10-08** (lab-realistic-gate R1)." |
| `:2492` | `` `DEFAULT_POLICY = "all-trials"` `` -> `` `DEFAULT_POLICY = "methods"` ``, adding "(`store.DSR_POLICY`; it was `"all-trials"` until 2026-10-08) … It moves whenever that constant moves, and only then." |
| `:2531` | `` `DSR_POLICY = "all-trials"` is the single name that decides N (Decision D2) `` -> `` `DSR_POLICY = "methods"` is the single name that decides N (Decision D2; `"all-trials"` until 2026-10-08, moved by lab-realistic-gate R1 because counting one look per variant *run* made re-running one method perturb every other method's verdict — N = 28 on the committed database, not 126) `` |

**Deliberately left:** `:43`, `:801` and `:890` state what *lab-luck-gate phase 4 did*, at N = 110,
on its own date. Those are dated records of a landed phase, not claims about the live rule, and
rewriting them would destroy the record the same way editing `docs/plans/…-method-lab-design.md`
would. `:141` and `:2586` describe all three policies evenhandedly and are correct as they stand.

### Step 13: The sweep and the republish

**This is the only step that writes `lab/lab.sqlite`.** Run it only after Steps 1–12 are in place;
`lab reevaluate` reads `store.DSR_POLICY` at call time.

```bash
cd /home/miftah/.worktrees/seer/lab-realistic-gate

# 1. Record what the database is before anything touches it. Both numbers go in the commit message.
md5sum lab/lab.sqlite          # expect 17d169420299a37485c93eb452653baa at 2b493ee
/home/miftah/seer/engine/.venv/bin/python - <<'PY'
import sqlite3, hashlib
c = sqlite3.connect("file:lab/lab.sqlite?mode=ro", uri=True)   # read-only: does NOT migrate
h = hashlib.sha256()
for r in c.execute("SELECT n, dsr, eligible, failed, n_trials_at_run FROM trials ORDER BY n"):
    h.update(repr(tuple(r)).encode())
print("trials:", c.execute("SELECT count(*) FROM trials").fetchone()[0], "digest:", h.hexdigest())
PY
# expect: trials: 128 digest: 6137e3ded7ac5bd4360b2c4fd061054cca76a9b1e4d0896610d56230f129e13e

# 2. The sweep. Reads only, writes only methods.status / transitions / methods.analysis.
PYTHONPATH=/home/miftah/.worktrees/seer/lab-realistic-gate/engine/src \
  /home/miftah/seer/engine/.venv/bin/python -m seer_engine lab reevaluate

# 3. The republish. Takes the write lock, regenerates web/data/lab.json, git-adds BOTH.
PYTHONPATH=/home/miftah/.worktrees/seer/lab-realistic-gate/engine/src \
  /home/miftah/seer/engine/.venv/bin/python -m seer_engine lab stage
```

Expected tail of the sweep, verbatim:

```
luck bar: DSR >= 0.90   N policy: methods, N = 28   (126 dev trial rows on the books)
  ...
  M0002: rejected -> dev-eligible  (M0002-REL-85)
  M0007: rejected -> dev-eligible  (M0007-N30, M0007-N20-RAW)
  M0008: re-judged 5 of 5 dev trial(s) at N = 28 against DSR >= 0.90; still rejected
  M0011: rejected -> dev-eligible  (M0011-RAW20-TV12, M0011-RAW20-TV14, M0011-RAW20-TV16, M0011-RAW30-TV14, M0011-RAW20-TV14-N21)
  M0019: rejected -> dev-eligible  (M0019-RAW20-S15, M0019-TV14N21-S20)
  M0024: rejected -> dev-eligible  (M0024-SAME-N20-RANKSUM, M0024-SAME-N20-BLEND-RM)
  M0030: rejected -> dev-eligible  (M0030-C70T, M0030-C50T)

6 method(s) moved rejected -> dev-eligible; test-window looks used: 2
```

`lab stage` prints `staged .../lab/lab.sqlite` and `staged .../web/data/lab.json`.

**The index is shared with concurrent phase sessions.** `lab stage` runs `git add` on exactly those
two paths, which is safe, but do not leave them sitting staged: commit by pathspec immediately, and
never `git add -A`, never `git reset --hard`.

```bash
git -C /home/miftah/.worktrees/seer/lab-realistic-gate commit \
  -m "lab(gate): deflate by distinct methods, not trial rows; republish" \
  -- lab/lab.sqlite web/data/lab.json
```

### Step 14: Hygiene for any read-only lab command

**Every lab command migrates `lab.sqlite` on connect, so even a read dirties the file.** For any
inspection outside Step 10, hash first and restore by path afterwards:

```bash
cd /home/miftah/.worktrees/seer/lab-realistic-gate
BEFORE=$(md5sum lab/lab.sqlite | cut -d' ' -f1)
# ... the read-only command ...
[ "$(md5sum lab/lab.sqlite | cut -d' ' -f1)" = "$BEFORE" ] || \
  git checkout -- lab/lab.sqlite      # by path, never `git checkout .`
```

Use `sqlite3.connect("file:lab/lab.sqlite?mode=ro", uri=True)` instead wherever a plain read will
do — it never migrates, which is why the digest command above uses it.

---

## Verification

Every command below is absolute-pathed and was executed as written.

**Build / lint:**

```bash
cd /home/miftah/.worktrees/seer/lab-realistic-gate/engine && \
PYTHONPATH=/home/miftah/.worktrees/seer/lab-realistic-gate/engine/src \
  /home/miftah/seer/engine/.venv/bin/python -c "
from seer_engine.lab import store, npolicy, remeasure, prereg
from seer_engine.commands import lab
print(store.DSR_POLICY, npolicy.DEFAULT_POLICY)"
# expect: methods methods
```

**Engine tests** — the venv is the MAIN checkout's; `PYTHONPATH` must point at the WORKTREE's
`engine/src` or pytest silently tests the main checkout instead of the branch. Never pass
`-o addopts` (it drops xdist and the suite goes from ~60s to ~340s).

```bash
cd /home/miftah/.worktrees/seer/lab-realistic-gate/engine && \
PYTHONPATH=/home/miftah/.worktrees/seer/lab-realistic-gate/engine/src \
  /home/miftah/seer/engine/.venv/bin/python -m pytest tests -q
```

**Measured with phase 1's files alone, after Step 13: `3079 passed, 406 skipped, 0 failed` in
~45s.** That is the phase's exit criterion and it is met without any other phase landing. The
baseline before any change was `3078 passed, 406 skipped` — the one extra test is the `--help`
regression.

The eight modules the policy change touches, as one focused run:

```bash
cd /home/miftah/.worktrees/seer/lab-realistic-gate/engine && \
PYTHONPATH=/home/miftah/.worktrees/seer/lab-realistic-gate/engine/src \
  /home/miftah/seer/engine/.venv/bin/python -m pytest \
  tests/test_lab_gate_policy.py tests/test_lab_npolicy.py tests/test_lab_snapshot.py \
  tests/test_lab_prereg.py tests/test_lab_status.py tests/test_lab_store.py \
  tests/test_lab_runner.py tests/test_lab_remeasure.py \
  tests/test_lab_gate_wording.py tests/test_lab_luck.py tests/test_cli.py -q
# expect: all passed
```

A guard against the pin being over-applied — no module outside the two named in Step 11 may name
the dead policy in a fixture:

```bash
cd /home/miftah/.worktrees/seer/lab-realistic-gate/engine && \
  grep -rln 'DSR_POLICY", "all-trials"' tests | sort
# expect exactly:
#   tests/test_lab_gate_policy.py   (the at_all_trials and committed fixtures, and the
#                                    old-bars reversal test that already did this)
#   tests/test_lab_prereg.py
#   tests/test_lab_status.py
```

**Web tests** — `web/node_modules` is absent in this worktree, and it must be **hardlinked**, never
symlinked (a symlink passes vitest and tsc and then kills `next build` with a misleading
"filesystem root" error):

```bash
[ -d /home/miftah/.worktrees/seer/lab-realistic-gate/web/node_modules ] || \
  cp -al /home/miftah/seer/web/node_modules /home/miftah/.worktrees/seer/lab-realistic-gate/web/node_modules
cd /home/miftah/.worktrees/seer/lab-realistic-gate/web && npx vitest run
# measured against the regenerated lab.json: 48 files, 626 tests, all passed
```

**The `--help` fix:**

```bash
cd /home/miftah/.worktrees/seer/lab-realistic-gate && \
PYTHONPATH=/home/miftah/.worktrees/seer/lab-realistic-gate/engine/src \
  /home/miftah/seer/engine/.venv/bin/python -m seer_engine lab --help | head -3
# expect the usage block, not a ValueError traceback
```

**The data, after Step 10** — one script, every exit criterion:

```bash
cd /home/miftah/.worktrees/seer/lab-realistic-gate && \
PYTHONPATH=/home/miftah/.worktrees/seer/lab-realistic-gate/engine/src \
  /home/miftah/seer/engine/.venv/bin/python - <<'PY'
import sqlite3, hashlib, json
from seer_engine.lab import store
c = store.connect("lab/lab.sqlite"); c.row_factory = sqlite3.Row
g = store.gate(c)
assert (g.policy, g.n) == ("methods", 28), g
assert c.execute("SELECT count(*) FROM trials").fetchone()[0] == 128
assert store.test_looks(c) == 2
h = hashlib.sha256()
for r in c.execute("SELECT n, dsr, eligible, failed, n_trials_at_run FROM trials ORDER BY n"):
    h.update(repr(tuple(r)).encode())
assert h.hexdigest() == "6137e3ded7ac5bd4360b2c4fd061054cca76a9b1e4d0896610d56230f129e13e"
st = {r["id"]: r["status"] for r in c.execute("SELECT id, status FROM methods")}
assert st["M0002"] == st["M0007"] == "dev-eligible"
assert st["M0022"] == "dev-eligible"          # already was, before the sweep
assert st["M0008"] == "rejected"              # the one that stays out
assert [m for m in ("M0011","M0019","M0024","M0030") if st[m] != "dev-eligible"] == []
assert [m for m, s in st.items() if s == "dev-eligible"].__len__() == 8
bad = [(m["id"], t["candidate_id"])
       for m in c.execute("SELECT id FROM methods WHERE status='rejected'")
       for t in c.execute("SELECT * FROM trials WHERE method_id=? AND window='dev'", (m["id"],))
       if store.verdict(c, t, at=g).eligible]
assert not bad, bad                            # nothing published rejected whose dev trials clear
assert c.execute("SELECT count(*) FROM methods WHERE analysis LIKE ?",
                 (f"%{store.REEVALUATION_MARKER}%",)).fetchone()[0] == 8
d = json.load(open("web/data/lab.json"))
assert (d["gate"]["dsrPolicy"], d["gate"]["dsrN"]) == ("methods", 28), d["gate"]
assert d["summary"]["byStatus"]["rejected"] == 21
assert d["summary"]["byStatus"]["dev-eligible"] == 8
assert d["summary"]["devTrials"] == 126 and d["summary"]["testLooks"] == 2
assert [e["labStatus"] for e in d["paper"]] == ["rejected"] * 4, "paper provenance is frozen"
print("all exit criteria hold")
c.close()
PY
```

**Manual check:** read the six `rejected -> dev-eligible` paragraphs `lab reevaluate` appended to
`methods.analysis`. Each must name the candidates it unblocked and the N it judged them at
(`N = 28`), and must have *grown* the existing analysis rather than replaced it
(`methods_no_delete` cannot catch a rewrite of a TEXT column; the append is `append_analysis`'s job
and the eye is the second check).

**Exit criteria**

- [ ] `store.gate(conn).policy == "methods"` and `.n == 28` on the committed database.
- [ ] `npolicy.DEFAULT_POLICY == store.DSR_POLICY`, asserted from both modules' tests.
- [ ] `M0002` and `M0007` have moved `rejected -> dev-eligible`; `M0008` has not; `M0022` was
      already `dev-eligible`. **And**: `M0011`, `M0019`, `M0024`, `M0030` have moved too — six in
      total, which is the measured truth and supersedes the brief's two.
- [ ] `web/data/lab.json` agrees with `store.gate`, and no method published as `rejected` has a dev
      trial that clears.
- [ ] `SELECT count(*) FROM trials` is **128**, the recorded-column digest is unchanged, and
      `store.test_looks` is **2**.
- [ ] `python -m seer_engine lab --help` prints its usage instead of raising, and
      `test_every_parsers_help_text_formats_without_raising` covers every subparser.
- [ ] **The full engine suite is green on phase 1's files alone** — `3079 passed, 406 skipped,
      0 failed` — and the web suite is green (48 files, 626 tests).
- [ ] No literal N survives in a test that is not about the policy: `test_lab_runner.py`,
      `test_lab_remeasure.py` and `test_lab_store.py` derive theirs from the store, so phase 2
      never has to touch them for N reasons.
- [ ] `engine/package_readme.md` no longer states `all-trials` as the live policy.

---

## Handoffs

**To phase 2 — one dependency and one small edit.**

1. **Phase 2 depends on phase 1.** `remeasure.batches_of`'s widening (Step 3) is a production
   change: without it, any method run after this phase lands is refused by `lab remeasure` with a
   `LabError`, and no test edit can route around it. The index DAG must read `2 depends on 1`.
2. **`engine/src/seer_engine/lab/runner.py` prose, three lines.** `:9` ("``store.pending_gate`` --
   shipped as ``all-trials``, so N = every dev trial in the lab"), `:191` and `:198` (the
   `trial_rows` docstring, "Under the shipped ``all-trials`` policy it is
   ``dev_trial_count(conn) + len(results)``"). All three are stale on this phase's landing. They
   are prose only — no test reads them — and phase 2 is already editing that file for the funding
   work, so correcting them there costs nothing and avoids two phases touching one file.
   **Phase 2 does not need to change `test_lab_runner.py` or `test_lab_remeasure.py` for N
   reasons:** phase 1 leaves both with their N derived from `store.pending_gate` and from the
   recorded `n_trials_at_run`, so they hold under any policy and under the funding change.

**Nothing is left red.** The three modules an earlier draft of this plan flagged as unassigned —
`test_lab_prereg.py`, `test_lab_status.py`, `test_lab_store.py` — are taken in Steps 10 and 11
under the set's rule that a phase repairs what it breaks.

**Taken rather than carded:** `engine/package_readme.md`'s five live claims (Step 12). The three
dated records in it (`:43`, `:801`, `:890`) are deliberately left, with the reason stated in that
step.

**To nobody, deliberately.** `docs/plans/2026-10-04-method-lab-design.md` §3 and §7.2 keep their
text. That document records decisions by appending dated revisions and
`test_lab_gate_wording.py`'s docstring already explains why deleting from it would destroy the
record; §7.2's "deliberately left at `all-trials`" is a true statement about 2026-10-07. A dated
§7.3 revision recording this move would be the right follow-up and is a documentation task, not
this phase's.

**A latent guard worth widening later.** `test_lab_gate_wording.py` sweeps shipped documents for a
stale luck *threshold* (a number) and has no equivalent for a stale N *policy* (a name). This phase
corrected the four live-rule statements it found by hand (`prereg.py`, `docs/lab/prereg/README.md`,
the explorer skill, `web/app/sera/overview.ts`); a `POLICY_IN_PROSE` matcher that catches the fifth
automatically is a real piece of work and is recorded here rather than half-built.

---

## Rollback

**Code (Steps 1–12):** `git checkout <pre-phase-sha> -- <paths>` for the nineteen files in the Files
table, or revert the phase's code commit. No data is involved.

**Data (Step 13):** the status moves are forward-only by trigger, so they cannot be undone with a
command — `methods.status` has no backward edge from `dev-eligible` to `rejected` and
`methods_no_delete` forbids removing the row. The only rollback is to restore the file:

```bash
cd /home/miftah/.worktrees/seer/lab-realistic-gate
git show 2b493ee4d79b0dd9bd70a6baadd967ca0c1bb68d:lab/lab.sqlite > lab/lab.sqlite
PYTHONPATH=/home/miftah/.worktrees/seer/lab-realistic-gate/engine/src \
  /home/miftah/seer/engine/.venv/bin/python -m seer_engine lab stage   # regenerates lab.json
git commit -m "revert(lab): restore the pre-sweep database" -- lab/lab.sqlite web/data/lab.json
md5sum lab/lab.sqlite    # expect 17d169420299a37485c93eb452653baa
```

`2b493ee` is the branch point and no other phase in this set writes `lab/lab.sqlite`, so that blob
is the pre-sweep database regardless of what else lands first. Restore the constants **before**
re-staging, or `lab stage` republishes `lab.json` at `methods` over a database at `all-trials`.

**Whole phase:** the phase touches no file any other phase writes, so reverting its commits leaves
phases 2 and 3 intact.

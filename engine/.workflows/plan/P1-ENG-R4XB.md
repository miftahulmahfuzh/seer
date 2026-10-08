> Adopted from `GOTRADE_FEE_REBUILD_PLAN.md` phase 1. Source: `.workflows/plan/gotrade-fee-rebuild/phase-1.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 1: The CI guard catches what it was written for

**Plan set:** `GOTRADE_FEE_REBUILD_PLAN.md`
**Analysis:** `20261008-091321-H3M8_code_analyzer.md`
**Satisfies:** R6 — the build goes red only when something is actually wrong, and the lab's pinned
evidence keeps asserting as the lab grows instead of quietly switching itself off
**Depends on:** none
**Difficulty:** NORMAL
**Package:** `.github`, `engine/tests`, `engine.lab`

> **Reconciled 2026-10-08.** The plan index's Decision **D11** gives this phase
> `engine/src/seer_engine/lab/npolicy.py`'s stale prose — the same aged-number defect R6 exists to
> fix, in the module this phase's test already exercises, and owned by no other phase. Step 4 below
> is that work; it is **comment-only** and changes no behaviour.

---

## Goal

After this phase the CI step that exists to catch *"Postgres never reached pytest"* fires on that one
condition and on nothing else, so a deliberate `skipif` no longer turns the build red with a message
that is false. And `engine/tests/test_lab_npolicy.py`'s pinned-evidence test asserts against the lab
database as it actually stands, instead of skipping itself the moment the lab outgrows a typed
number — the four `COMMITTED_*` constants are gone, replaced by values derived from the committed
database and by a recomputation of the participation ratio and mean pairwise correlation from the raw
curves. Both halves of handover §6a are closed; `main`'s first cause of red is fixed.

## Measured evidence this phase rests on

Every number below has the command that produced it. Interpreter:
`/home/miftah/seer/engine/.venv/bin/python` (the base `python` on this machine has no `pytest-xdist`).

**1. The suite today, on this branch.**

```
cd /home/miftah/.worktrees/seer/gotrade-fee-rebuild && PYTHONPATH=engine/src \
  PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
  /home/miftah/seer/engine/.venv/bin/python -m pytest engine/tests -q -rs
```

```
=========================== short test summary info ============================
SKIPPED [1] engine/tests/test_lab_costs.py:265: set SEER_LAB_COSTS_LIVE=1 (and SEER_RESEARCH_STORE) to run lab costs M0007 on the real store
SKIPPED [1] engine/tests/test_lab_npolicy.py:319: the lab has moved past 110 dev trials
3362 passed, 2 skipped, 154 warnings in 75.78s (0:01:15)
```

So: **two** skips today, **zero** failures, and neither skip reason mentions `PG_TEST_URL`. The guard
at `engine-ci.yml:70` greps `^SKIPPED` and therefore fails this run while printing *"PG_TEST_URL did
not reach pytest"*, which is untrue. That is handover §6a.

**2. The line the guard was written for.** With `PG_TEST_URL` unset:

```
cd /home/miftah/.worktrees/seer/gotrade-fee-rebuild && PYTHONPATH=engine/src \
  /home/miftah/seer/engine/.venv/bin/python -m pytest engine/tests/test_paper_store.py -q -rs -n0
```

```
SKIPPED [1] engine/tests/test_paper_store.py:229: PG_TEST_URL is not set; start Postgres with `docker run -d --name seer-pg -e POSTGRES_PASSWORD=pg -p 55432:5432 postgres:16` and export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres
...
1 passed, 32 skipped in 1.55s
```

Two facts the fix turns on, both measured rather than assumed:

- pytest prints the **whole** reason on **one** line and does not wrap or truncate it, so grepping
  the reason text works.
- the line is attributed to the **test's** location (`test_paper_store.py:229`), *not* to
  `conftest.py:83` where `pytest.skip` is called. A guard matching `conftest.py:83` would never fire.
  It must match the reason.

**3. Where the skip sites are.** The scope and the analysis both say "eight"; grepping finds **nine**
real ones (two further `grep` hits, `test_market_fundamentals.py:222` and `test_dev_trades_bar.py:105`,
are prose inside docstrings explaining why those tests do *not* skip):

```
cd /home/miftah/.worktrees/seer/gotrade-fee-rebuild && grep -rn 'pytest.skip\|skipif' engine/tests/
```

| Site | Reason text it emits | Narrowed guard |
|---|---|---|
| `engine/tests/conftest.py:83` (the `pg_url` fixture) | `PG_TEST_URL is not set; start Postgres with ...` | **fires** — the one it should catch |
| `engine/tests/test_lab_costs.py:265` | `set SEER_LAB_COSTS_LIVE=1 (and SEER_RESEARCH_STORE) to run lab costs M0007 on the real store` | passes over |
| `engine/tests/test_lab_npolicy.py:287` | `no committed lab database` | passes over |
| `engine/tests/test_lab_npolicy.py:319` | `the lab has moved past 110 dev trials` | **deleted by this phase** |
| `engine/tests/test_lab_methods.py:117` | `no lab database` | passes over |
| `engine/tests/test_lab_status.py:277` | `no committed lab database here` | passes over |
| `engine/tests/test_paper_roster.py:651` | `no lab database` | passes over |
| `engine/tests/test_cost_model_pins.py:38` | `no lab database` | passes over |
| `engine/tests/test_lab_gate_policy.py:861` | `phase 9 has luck-tested the seed; this row now has moments` | passes over |

The reconciler should note the correction: nine sites, not eight. It changes nothing about the fix —
the narrowed guard keys on one reason string, so the count of the others is immaterial — but the index
and the analysis both say eight and the number is checkable.

**4. The guard pattern, checked against both populations.** Pattern
`^SKIPPED .*: PG_TEST_URL is not set;` against a file holding all seven deliberate reasons above
matches **0** lines; against the same file plus one real `pg_url` skip it matches **1**.

**5. The lab database.**

```
cd /home/miftah/.worktrees/seer/gotrade-fee-rebuild && python3 -c "
import sqlite3
c = sqlite3.connect('file:lab/lab.sqlite?mode=ro', uri=True)
print('total trials', c.execute('select count(*) from trials').fetchone()[0])
for w, n in c.execute('select window, count(*) from trials group by window'): print(w, n)
print('distinct dev methods', c.execute(\"select count(distinct method_id) from trials where window='dev'\").fetchone()[0])
"
```

```
total trials 128
dev 126
test 2
distinct dev methods 28
```

**126 dev + 2 test = 128 rows.** `COMMITTED_DEV_TRIALS` is compared against
`store.dev_trial_count`, which counts the **dev** window only (`npolicy.py:271` reads it; the SQL is
`WHERE window = 'dev'`). The handover's §6a number, 128, is the **total** — re-pinning to it would
leave the test skipping exactly as it does today, which is the failure R6 exists to end. This is the
index's Decision **D9**, and it is why this phase does not re-pin to any number at all.

**6. All four constants have moved.**

```
cd /home/miftah/.worktrees/seer/gotrade-fee-rebuild && PYTHONPATH=engine/src \
  /home/miftah/seer/engine/.venv/bin/python -c "
import sqlite3
from seer_engine.lab import npolicy, store
conn = sqlite3.connect(f'file:{store.COMMITTED_DB}?mode=ro', uri=True)
print('dev_trial_count ', store.dev_trial_count(conn))
print('dev_method_count', npolicy.dev_method_count(conn))
c = npolicy.correlation(conn)
print('curves_used     ', c.curves_used)
print('month_ends      ', c.month_ends)
print('participation   ', c.participation_ratio)
print('mean_pairwise   ', c.mean_pairwise)
for p in npolicy.POLICIES:
    n = npolicy.effective_n(conn, p)
    print(f'{p:11s} n={n.n}  basis={n.basis!r}')
"
```

| Constant | Pinned (at `485d416`) | Measured now | Moved? |
|---|---|---|---|
| `COMMITTED_DEV_TRIALS` | 110 | **126** | yes |
| `COMMITTED_METHODS` | 23 | **28** | yes |
| `COMMITTED_PR` | 2.442 | **2.338473061106947** | yes |
| `COMMITTED_RHO` | 0.595 | **0.6124884723866705** | yes |
| `corr.month_ends` (typed inline at `:326`) | 102 | **102** | no |
| `effective_n('effective').n` (typed inline at `:323`) | 2 | **2** | no |
| `effective_n('methods').n` (typed inline at `:322`) | 23 | **28** | yes |

And the `all-trials` basis line now reads
`'126 dev trials, every variant run counted as one independent look'`, which is byte-for-byte what
`web/data/lab.json`'s `gate.dsrNBasis` already publishes (`gate.dsrN` there is **126**):

```
cd /home/miftah/.worktrees/seer/gotrade-fee-rebuild && python3 -c "
import json; print(json.load(open('web/data/lab.json'))['gate'])"
```

**7. The replacement pin reproduces the library exactly.** A second, independent computation of the
participation ratio and mean pairwise correlation — written from the raw `trials.curve_json` rows,
calling none of `npolicy`'s helpers — returns:

```
library  : 2.338473061106947 0.6124884723866705 126 102
reference: 2.338473061106947 0.6124884723866705 126 102
match pr : True   (|Δ| < 1e-12)
match rho: True   (|Δ| < 1e-12)
```

The whole new test body was run standalone against the real committed database before this plan was
written: **every assertion held**, and `ruff check --select E9,F --ignore F401` is clean on it. Cost:
**0.010 s** for the reference pass, against 0.049 s the existing four correlation passes already
spend. It adds nothing measurable to the suite.

## Why the pin becomes a recomputation and not a new number

The user's ask, verbatim in the scope: *prefer the form that cannot age again*. There is no number
for which `participation_ratio == 2.3385` survives the lab growing — it is a property of **this**
set of 126 curves, and Sera adds curves. So the age-proof move is to stop pinning the **answer** and
pin the **arithmetic**: recompute the ratio in the test from the stored curves and assert the library
agrees. That assertion is true at 110 curves, true at 126, true at 1,260, and it still fails if
`_dev_curves`, `_return_matrix` or `correlation` regresses — which is exactly what the four constants
were there to catch. Everything else the old test asserted (`dev_method_count`, the three policies'
`n`, the basis string) becomes an f-string or a `max(...)` over values read from the same database,
so none of it can quote a count it has outgrown.

One assertion is deliberately strict rather than permissive: `corr.curves_used == trials`, i.e. no
dev curve is silently dropped on the way into the measurement. It holds today (126 == 126). If a
future trial records a curve that is too short, non-positive or perfectly flat, `npolicy` drops it
and this test goes red with a message naming how many were dropped. That is a finding worth a human
look at the gate's evidence, not noise — see **Handoffs** for the loosening if the owner disagrees.

## Interface Contract

**Deletes:**
- `engine/tests/test_lab_npolicy.py::COMMITTED_DEV_TRIALS` (`test_lab_npolicy.py:22`)
- `engine/tests/test_lab_npolicy.py::COMMITTED_METHODS` (`:23`)
- `engine/tests/test_lab_npolicy.py::COMMITTED_PR` (`:24`)
- `engine/tests/test_lab_npolicy.py::COMMITTED_RHO` (`:25`)
- `engine/tests/test_lab_npolicy.py::test_the_committed_evidence_at_110_dev_trials` (`:310-334`),
  and with it the skip at `:319`

**Renames:** `test_the_committed_evidence_at_110_dev_trials` ->
`test_the_committed_evidence_is_recomputed_from_the_database_that_holds_it`
(a test function; nothing imports it)

**Creates:**
- `engine/tests/test_lab_npolicy.py::_reference_correlation` (`test_lab_npolicy.py`, new, after
  `_committed()`)
- `engine/tests/test_lab_npolicy.py::test_the_committed_evidence_is_recomputed_from_the_database_that_holds_it`

**Signature changes:** none. No engine source file is touched; no public symbol moves.

**Requires (from earlier phases):** nothing. This phase has no dependencies and is in wave W1.

**Also owned (assigned by Decision D11, after this phase's planner found it unowned):**
- `engine/src/seer_engine/lab/npolicy.py` — **comment-only.** Its module docstring says
  *"110 on the committed database"* (`:17`) and *"23 on the committed database"* (`:21`), and its
  `floored` docstring says *"ceil(2.44) = 3 against 23 methods"* (`:99-100`). Measured now: 126, 28 and
  `ceil(2.34) = 3 against 28 methods`. `:23`'s *"2 on the committed database"* is still correct and
  is left alone. No code, no signature and no behaviour in that file changes — see Step 4.

**Leaves alone (owned by others):**
- `engine/src/seer_engine/lab/store.py` — Phase 2 and Phase 7 own it.
- `lab/lab.sqlite` — read-only, `mode=ro`, never written.
- `web/data/lab.json` and everything under `web/` — Phase 2 (`web/lib/sera`, `web/app/sera`),
  Phase 9, Phase 10.
- `.github/workflows/nightly.yml` — Phase 12 owns its comment. Phase 11 adds a **new** workflow.
  This phase edits **only** `engine-ci.yml`, and only the one `Test engine` step.
- `engine/tests/conftest.py` — read-only. `_SKIP_REASON` is the signature being matched, not
  changed. The new guard *reads* this file to confirm the signature is still there.
- Every other `engine/tests/test_*.py` file: untouched, including the seven deliberate skip sites
  the guard now passes over.

## Files

| File | Action | What changes |
|---|---|---|
| `.github/workflows/engine-ci.yml` | modify | `:65-73`, the `Test engine` step: the `^SKIPPED` grep narrows to `_SKIP_REASON`'s own signature, plus a one-line check that the signature still exists in `conftest.py` so the guard cannot disarm itself silently |
| `engine/tests/test_lab_npolicy.py` | modify | `:10` add `import json`; `:19-25` delete the comment and the four `COMMITTED_*` constants; `:282-334` rewrite the committed-database section — `_reference_correlation` added, the skipping pinned test replaced by one that asserts |
| `engine/src/seer_engine/lab/npolicy.py` | modify (**comment-only**, D11) | `:17` `110` -> `126`; `:21` `23` -> `28`; `:99-100` `ceil(2.44) = 3 against 23 methods` -> `ceil(2.34) = 3 against 28 methods`. No executable line is touched |

Three files.

## Implementation Steps

### Step 1: Narrow the CI guard to the one failure it was written for

**File:** `.github/workflows/engine-ci.yml:65-73`

**Change:** Replace the whole `Test engine (DB tests must run, not skip)` step. Three things change:
the grep matches `conftest._SKIP_REASON`'s reason text rather than the mere fact of a skip; a
preceding check asserts that reason text is still present in `conftest.py`, so rewording the fixture
cannot disarm the guard without failing the build; and the comment says what the step is for, in
plain words, with the measured skip count.

The step being replaced, verbatim as it stands at `485d416`:

```yaml
      - name: Test engine (DB tests must run, not skip)
        shell: bash
        run: |
          set -o pipefail
          python -m pytest engine/tests -q -rs | tee pytest.out
          if grep -q '^SKIPPED' pytest.out; then
            echo "::error::engine tests were skipped; PG_TEST_URL did not reach pytest"
            exit 1
          fi
```

**Code** — the complete replacement step:

```yaml
      - name: Test engine (the Postgres tests must run, not skip)
        shell: bash
        run: |
          set -o pipefail

          # This step guards against exactly one failure: PG_TEST_URL never reached pytest, so
          # every database test "passed" by not running. conftest.py's pg_url fixture skips with
          # the reason matched below and nothing else in the suite uses that wording.
          #
          # It used to grep for any '^SKIPPED' line, which cannot tell that failure from a
          # deliberate skipif and so failed the build while printing a message that was false.
          # Measured 2026-10-08 on a correctly configured run: 3362 passed, 2 skipped, 0 failed --
          # the two being an opt-in live-store test and an aged pin, neither of them a
          # misconfiguration.
          #
          # The signature check comes first: if conftest.py's reason is ever reworded, the grep
          # below would stop matching and the guard would disarm itself in silence. Failing here
          # instead makes the two move together.
          signature='PG_TEST_URL is not set; start Postgres with'
          if ! grep -qF "$signature" engine/tests/conftest.py; then
            echo "::error file=engine/tests/conftest.py::the pg_url skip reason no longer contains \"$signature\", which this step greps for; update conftest.py and this guard together"
            exit 1
          fi

          python -m pytest engine/tests -q -rs | tee pytest.out

          if grep -q "^SKIPPED .*: $signature" pytest.out; then
            echo "::error::PG_TEST_URL did not reach pytest, so the database tests skipped instead of running; check the postgres service and the job's env"
            exit 1
          fi
```

**Impact:** CI stops failing on the two deliberate skips measured above, and keeps failing on a
missing `PG_TEST_URL`. The `grep -qF` on `conftest.py` runs before pytest, so a reworded reason fails
in under a second rather than after a 15-minute suite. `-rs` stays on the pytest invocation even
though `engine/pyproject.toml:35` already sets `addopts = "-ra -n auto"` (which prints skips anyway) —
keeping it explicit means the guard does not depend on `addopts` staying as it is.

Note what is *not* changed: the `env.PG_TEST_URL` at `:40`, the `postgres` service block at
`:27-39`, the lint step, the `web` job. The step's `name` gains "the Postgres tests" because the old
name read as a blanket rule about all skips, which is the misreading that produced the broad grep.

### Step 2: Add the `json` import and delete the four aged constants

**File:** `engine/tests/test_lab_npolicy.py:8-25`

**Change:** `_reference_correlation` (Step 3) parses `trials.curve_json` itself, so the module needs
`json`. The four `COMMITTED_*` constants and the comment above them go: nothing else in the repo
references them (`grep -rn 'COMMITTED_DEV_TRIALS\|COMMITTED_METHODS\|COMMITTED_PR\|COMMITTED_RHO'`
returns hits in this file only).

**Code** — the complete replacement for lines 8 through 25 inclusive (the module docstring at
`:1-6` is unchanged):

```python
from __future__ import annotations

import json
import math
import sqlite3
from datetime import date

import numpy as np
import pytest

from seer_engine.lab import npolicy, store
```

That is the whole block: the comment at `:19-21` and the four assignments at `:22-25` are removed,
and the two blank lines before `@pytest.fixture()` remain as they are.

**Impact:** The file no longer carries a number that has to be hand-edited when Sera records a trial.
`import json` is used by Step 3, so ruff's `F401` (which `engine/pyproject.toml` does not disable for
this path — it disables it globally in the lint selection, but the import is used either way) has
nothing to say.

### Step 3: Replace the skipping pinned test with one that recomputes and asserts

**File:** `engine/tests/test_lab_npolicy.py:282-334` (the whole `# ---- the committed database`
section, from its banner comment to the end of the file)

**Change:** `_committed()` is kept byte-for-byte — its skip at `:287` is the legitimate "a clone
without `lab/lab.sqlite`" case, `lab/lab.sqlite` is tracked in git (`git ls-files --error-unmatch
lab/lab.sqlite` succeeds) so it never fires in CI, and the narrowed guard passes over it.
`test_the_committed_database_orders_the_three_policies` is kept byte-for-byte — it already derives
everything it asserts and does not age. What changes is the second test: it is replaced by a version
that never skips on a count, and `_reference_correlation` is added between the two.

**Code** — the complete replacement for lines 282 to 334 inclusive (end of file):

```python
# ---- the committed database ------------------------------------------------------------------


def _committed():
    if not store.COMMITTED_DB.exists():
        pytest.skip("no committed lab database")
    conn = sqlite3.connect(f"file:{store.COMMITTED_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _reference_correlation(conn: sqlite3.Connection) -> tuple[float, float, int, int]:
    """Recompute the dev trials' co-movement here, from the raw ``trials.curve_json`` rows.

    Calls none of ``npolicy``'s helpers, so the test below compares two independent routes to the
    same four figures: (participation ratio, mean pairwise correlation, curves used, common
    month-ends).

    This replaced four typed constants (``COMMITTED_PR = 2.442`` and friends). A typed number is a
    property of one set of curves, and Sera adds curves: by the time the lab reached 126 dev trials
    the pin said 110 and the test that held it had turned itself into a skip, so CI was asserting
    nothing while reporting a pass. There is no number for which "the ratio is 2.44" survives the
    lab growing -- but the arithmetic that produces it is the same at any size, so the arithmetic
    is what this pins. The filters mirror ``npolicy._dev_curves`` and ``_return_matrix``: a curve
    too short to carry a variance, with a non-positive level, or perfectly flat is dropped rather
    than correlated. If those rules ever change, this changes with them -- deliberately.
    """
    curves: list[dict[str, float]] = []
    for (text,) in conn.execute("SELECT curve_json FROM trials WHERE window = 'dev' ORDER BY n"):
        curve = {str(day): float(level) for day, level in json.loads(text or "[]")}
        if len(curve) >= 3:  # npolicy._MIN_POINTS: fewer points carry no variance
            curves.append(curve)
    assert len(curves) >= 2, "the committed database must hold at least two usable dev curves"
    days = sorted(set.intersection(*(set(c) for c in curves)))
    assert len(days) >= 3, "the dev curves must share at least three month-ends"
    rows: list[np.ndarray] = []
    for curve in curves:
        levels = np.asarray([curve[d] for d in days], dtype=float)
        returns = levels[1:] / levels[:-1] - 1.0
        if np.all(levels > 0.0) and np.all(np.isfinite(returns)) and float(np.std(returns)) > 0.0:
            rows.append(returns)
    matrix = np.vstack(rows)
    corr = np.corrcoef(matrix)
    eigenvalues = np.linalg.eigvalsh(corr)
    ratio = float(np.sum(eigenvalues)) ** 2 / float(np.sum(eigenvalues**2))
    upper = np.triu_indices(len(rows), k=1)
    return ratio, float(np.mean(corr[upper])), len(rows), len(days)


def test_the_committed_database_orders_the_three_policies():
    """Holds for every lab: the measured independence never exceeds the ideas, which never
    exceed the rows. This is the whole claim behind choosing ``methods``."""
    conn = _committed()
    try:
        rows = npolicy.effective_n(conn, "all-trials")
        methods = npolicy.effective_n(conn, "methods")
        effective = npolicy.effective_n(conn, "effective")
        assert rows.n == store.dev_trial_count(conn)
        assert methods.n == max(npolicy.dev_method_count(conn), math.ceil(rows.participation_ratio))
        assert effective.n == max(npolicy.DSR_MIN_N, round(rows.participation_ratio))
        assert npolicy.DSR_MIN_N <= effective.n <= methods.n <= rows.n
        assert rows.mean_pairwise_corr is not None and 0.0 < rows.mean_pairwise_corr < 1.0
    finally:
        conn.close()


def test_the_committed_evidence_is_recomputed_from_the_database_that_holds_it():
    """The gate's N and the evidence behind it, asserted against the lab as it stands today.

    Nothing here is a typed number, so nothing here can age. This test used to carry four
    ``COMMITTED_*`` constants measured at 110 dev trials and skip itself once the lab moved past
    them; the lab now holds 126 dev trials (plus 2 in the test window, 128 rows in all), so it had
    been skipping -- asserting nothing -- while CI failed on the skip itself with a message about
    PG_TEST_URL that was false. Every expected value below is either read from the database or
    recomputed from its raw curves by ``_reference_correlation``, which keeps the test's teeth at
    any lab size.
    """
    conn = _committed()
    try:
        trials = store.dev_trial_count(conn)
        methods = npolicy.dev_method_count(conn)
        corr = npolicy.correlation(conn)
        ratio, rho, curves_used, month_ends = _reference_correlation(conn)

        # The estimator agrees with the arithmetic, curve for curve and month-end for month-end.
        assert corr.curves_used == curves_used
        assert corr.month_ends == month_ends
        assert corr.participation_ratio == pytest.approx(ratio, rel=1e-9)
        assert corr.mean_pairwise == pytest.approx(rho, rel=1e-9)

        # No dev trial's curve is dropped on the way into the measurement. If this fails, the
        # gate's N rests on fewer curves than the lab recorded, which is worth a look before it
        # is accepted.
        assert corr.curves_used == trials, (
            f"{trials - corr.curves_used} of {trials} dev curves were dropped before the "
            "measurement; find which trial and why rather than loosening this"
        )

        # The trials are not independent, and it is measurable: the claim npolicy exists to make.
        # A correlation matrix regressed to the identity would put the ratio at `trials` and rho
        # at 0, and both of these would catch it.
        assert 1.0 <= corr.participation_ratio < float(trials)
        assert corr.mean_pairwise is not None and 0.0 < corr.mean_pairwise < 1.0

        # Each policy resolves to exactly what it is defined as, on this database.
        assert npolicy.effective_n(conn, "all-trials").n == trials
        assert npolicy.effective_n(conn, "methods").n == max(methods, math.ceil(ratio))
        assert npolicy.effective_n(conn, "effective").n == max(npolicy.DSR_MIN_N, round(ratio))

        # The one line committed into every docs/lab/prereg/MNNNN.md and published as
        # web/data/lab.json's gate.dsrNBasis. Built from the measured count, so it can never
        # quote a count the lab has outgrown -- which is the bug this whole test is the fix for.
        assert npolicy.effective_n(conn, "all-trials").basis == (
            f"{trials} dev trials, every variant run counted as one independent look"
        )
    finally:
        conn.close()
```

**Impact:**

- `engine/tests/test_lab_npolicy.py:319`'s skip disappears, so the suite goes from `2 skipped` to
  `1 skipped` — the remaining one being `test_lab_costs.py:265`, the opt-in live-store test, which
  the narrowed guard passes over.
- The test now asserts on every run. Measured against the real database before this plan was
  written: all assertions hold, and the reference pass costs 0.010 s.
- `test_the_committed_database_orders_the_three_policies` and `_committed()` are reproduced above
  unchanged so the replacement block is a single contiguous paste with no "existing code" gaps. An
  implementer replacing lines 282-334 with the block above produces a file whose only differences
  from `485d416` are the ones Steps 2 and 3 describe.
- Verify with `git diff --stat engine/tests/test_lab_npolicy.py`: three files in the phase, and this
  one's diff should touch only the import block, the deleted constants, and the tail from `:282`.

### Step 4: `npolicy.py`'s own prose stops quoting the numbers it has outgrown (D11)

**File:** `engine/src/seer_engine/lab/npolicy.py:17`, `:21`, `:99-100`

**Change:** three comment-only substitutions. Assigned to this phase by the index's Decision **D11**:
it is the same aged-number defect R6 exists to fix, in the module this phase's test already
exercises, and no other phase in the set touches `npolicy.py`. **No executable line, no signature
and no docstring that a test asserts on is changed** — `basis` and `evidence()` are computed from the
database, so none of these strings reaches any output.

The measured replacements come from **Measured evidence §6** above: 126 dev trials, 28 distinct dev
methods, participation ratio 2.338473061106947 (so `ceil` is 3, unchanged).

**Code** — `:16-17`, replacing the second line of the `all-trials` bullet:

```
- ``all-trials`` -- one look per dev trial row. The literal reading of design §3 and what the
  lab did before this module existed. 126 on the committed database.
```

**Code** — `:20-21`, replacing the second line of the `methods` bullet:

```
  family of variants as the one idea it is, and the floor guarantees the policy can never
  assert fewer independent looks than the curves themselves show. 28 on the committed database.
```

**Code** — `:99-100`, inside `floored`'s docstring:

```
        The floor is the policy's justification: it cannot assert fewer independent looks than
        the curves measurably have. On the committed database it does not bind (ceil(2.34) = 3
        against 28 methods); a lab of one method with many uncorrelated variants is where it does.
```

**Not changed:** `:23`'s *"2 on the committed database"* — measured, `effective_n('effective').n` is
still **2**, so that sentence is still true.

**Impact:** documentation of record in engine source now matches the database it describes. Nothing
imports, asserts on or renders these strings, so the suite is unaffected; `ruff check engine` must
still pass, which is the only gate this step has.

## Verification

**Build:** there is no compile step for either file. Lint is the equivalent:

```
cd /home/miftah/.worktrees/seer/gotrade-fee-rebuild && \
  /home/miftah/seer/engine/.venv/bin/python -m ruff check engine
```

Expect `All checks passed!` — this is the same command `engine-ci.yml:62` runs.

**Tests:**

```
cd /home/miftah/.worktrees/seer/gotrade-fee-rebuild && PYTHONPATH=engine/src \
  PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
  /home/miftah/seer/engine/.venv/bin/python -m pytest engine/tests -q -rs -n auto
```

`PYTHONPATH=engine/src` is **required**: without it pytest silently tests `/home/miftah/seer`, not
this branch. Never pass `-o addopts` — it would drop the `-n auto` that takes the suite from ~342 s
to ~76 s. Postgres, if it is not already up:
`docker run -d --name seer-pg -e POSTGRES_PASSWORD=pg -p 55432:5432 postgres:16`.

Expected, against the measured `3362 passed, 2 skipped` baseline:

```
3362 passed, 1 skipped, ... warnings in ~76s
=========================== short test summary info ============================
SKIPPED [1] engine/tests/test_lab_costs.py:265: set SEER_LAB_COSTS_LIVE=1 (and SEER_RESEARCH_STORE) to run lab costs M0007 on the real store
```

**Narrow run while iterating:**

```
cd /home/miftah/.worktrees/seer/gotrade-fee-rebuild && PYTHONPATH=engine/src \
  /home/miftah/seer/engine/.venv/bin/python -m pytest engine/tests/test_lab_npolicy.py -q -rs -n0
```

Expect `0 skipped` from this file.

**Manual check 1 — the guard still catches what it is for.** Simulate the misconfiguration locally
by running one DB-heavy file with `PG_TEST_URL` unset and applying the new pattern by hand:

```
cd /home/miftah/.worktrees/seer/gotrade-fee-rebuild && PYTHONPATH=engine/src \
  /home/miftah/seer/engine/.venv/bin/python -m pytest engine/tests/test_paper_store.py -q -rs -n0 \
  > /tmp/unset.out 2>&1
grep -c '^SKIPPED .*: PG_TEST_URL is not set;' /tmp/unset.out   # expect >= 1  -> guard fires
```

**Manual check 2 — the guard passes over every deliberate skip.** Run the configured suite, keep its
output, and apply the same pattern:

```
cd /home/miftah/.worktrees/seer/gotrade-fee-rebuild && PYTHONPATH=engine/src \
  PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
  /home/miftah/seer/engine/.venv/bin/python -m pytest engine/tests -q -rs -n auto \
  > /tmp/configured.out 2>&1
grep -c '^SKIPPED .*: PG_TEST_URL is not set;' /tmp/configured.out   # expect 0  -> guard silent
grep '^SKIPPED' /tmp/configured.out                                  # expect exactly 1 line
```

**Manual check 3 — the signature check.** Confirm the string the workflow greps for is really in
`conftest.py`, so the guard is armed:

```
cd /home/miftah/.worktrees/seer/gotrade-fee-rebuild && \
  grep -cF 'PG_TEST_URL is not set; start Postgres with' engine/tests/conftest.py   # expect 1
```

**Manual check 4 — the workflow still parses.** `engine-ci.yml` is only read by GitHub, so check it
locally before pushing:

```
cd /home/miftah/.worktrees/seer/gotrade-fee-rebuild && python3 -c "
import yaml, pathlib
d = yaml.safe_load(pathlib.Path('.github/workflows/engine-ci.yml').read_text())
names = [s['name'] for s in d['jobs']['engine']['steps'] if 'name' in s]
print(names)
assert any('Postgres tests must run' in n for n in names)
print('engine-ci.yml parses')
"
```

**Exit criteria:**

1. `grep -c '^SKIPPED' ` on a correctly configured engine run returns **1**, and the narrowed
   pattern returns **0** — the build is green on skips that are deliberate.
2. The narrowed pattern returns **>= 1** on a run with `PG_TEST_URL` unset — the build is red on the
   failure the step exists to catch.
3. `engine/tests/test_lab_npolicy.py` reports **0 skipped**, and contains no `COMMITTED_` identifier
   (`grep -c 'COMMITTED_' engine/tests/test_lab_npolicy.py` → `0`; note `store.COMMITTED_DB` is
   spelled `COMMITTED_DB` and *will* match, so the correct check is
   `grep -c 'COMMITTED_DEV_TRIALS\|COMMITTED_METHODS\|COMMITTED_PR\|COMMITTED_RHO'` → `0`).
4. The full engine suite reports `0 failed` and `3362 passed, 1 skipped` (the count may rise if a
   concurrent phase lands tests first; `0 failed` and `1 skipped` are the invariants).
5. `python -m ruff check engine` passes.
6. `lab/lab.sqlite` is unmodified: `git status --short lab/` is empty.
7. **(D11)** `grep -n '110 on the committed\|23 on the committed\|ceil(2.44)' engine/src/seer_engine/lab/npolicy.py`
   returns **nothing**, and `git diff engine/src/seer_engine/lab/npolicy.py` shows only comment lines
   (every changed line begins with `#`, `-- ` inside a docstring, or lies inside a `"""` block).

## Handoffs

Work found while planning this phase and deliberately **not** done here.

1. ~~**`npolicy.py`'s docstrings quote the aged numbers too.**~~ **RESOLVED — done here, as Step 4.**
   The reconciler took the first of the two options this planner offered, under the index's Decision
   **D11**: `npolicy.py`'s three stale sentences are this phase's, comment-only. The rung is 4 (the
   index's Requirements table — R6 asks for *"a form that cannot age again"*, and prose that states a
   stale number ages exactly the way a constant does). The phase's `Package` line gains `engine.lab`
   and its Files table gains the file; nothing was smuggled into Phase 2 or Phase 7, which own
   `lab/store.py` and not `npolicy.py`.
2. **"Eight skip sites" is nine.** The index's Phase 1 exit criteria and the analysis's Reference
   List both say eight; the measured count is nine (table above). Worth correcting in the index
   because it is a checkable number and this plan set's invariant 6 says every number is measured.
   It changes no code.
3. **If `corr.curves_used == trials` ever goes red** on a legitimately flat or short dev curve, the
   loosening is `assert corr.curves_used <= trials` plus a named exception for the dropped trial —
   not deleting the assertion. Left as a note rather than pre-weakened, because a silently dropped
   curve changes the gate's N and the owner should see it once.
4. **`-ra` in `engine/pyproject.toml:35`** already prints skip summaries, so CI's `-rs` is
   redundant. Left in place on purpose: the guard should not depend on `addopts` keeping `-ra`.
   Nobody owns `engine/pyproject.toml` in this set; not worth a change.
5. **Phase 11's new watcher** will also want to know "CI green y/n" (R8). It reads the workflow's
   *result*, not its steps, so it needs nothing from this phase beyond CI being green for the right
   reasons — which is what this phase delivers. No coordination required; this phase does not create
   or rename a job, so `jobs.engine` and `jobs.web` keep their names for anything that keys on them.
6. **The test-window rows.** `test_lab_npolicy.py` reads only `window = 'dev'`, so the 2 test-window
   rows are outside everything this phase asserts. Phase 2 owns what those rows publish (R7).

## Rollback

This phase is one commit on `feature/gotrade-fee-rebuild` touching exactly three files, none of
which any other phase edits. `git revert <sha>` restores all three.

The consequence of reverting, stated plainly so it is a choice and not a surprise: `main`/the branch
goes back to red for handover §6a — CI fails on the deliberate skip at `test_lab_npolicy.py:319`
with the false message about `PG_TEST_URL` — and the lab's pinned evidence goes back to asserting
nothing. Nothing else regresses: no engine source, no database, no migration, no roster entry and no
paper clock is involved, and `lab/lab.sqlite` is opened `mode=ro` throughout.

If only half is wanted, the two steps are independent and can be reverted separately:

```
git checkout <sha>~1 -- .github/workflows/engine-ci.yml      # guard only
git checkout <sha>~1 -- engine/tests/test_lab_npolicy.py     # pins only
```

Reverting the test alone while keeping the narrowed guard is the one combination to avoid: the guard
would then pass over `:319`'s skip, so the aged pin would be silently inert with a green build —
worse than today, where it is at least loudly wrong.

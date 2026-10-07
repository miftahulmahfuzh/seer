# Phase 1: The N policy and the effective-N estimator

**Plan set:** `LAB_LUCK_GATE_PLAN.md`
**Analysis:** `20261007-085606-D3K1_code_analyzer.md`
**Satisfies:** R1 — the DSR gate's N over-counts the search; this phase builds the thing that can count it correctly, and measures the evidence that says so.
**Depends on:** none
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine/lab`

---

## Goal

A new pure module `seer_engine.lab.npolicy` names the three candidate answers to "how many
independent looks has the lab taken" — `all-trials`, `methods`, `effective` — and measures the
evidence behind them from the month-end equity curves already stored in `trials.curve_json`.
`effective_n(conn, policy)` returns an `NCount` carrying both the int to hand `deflated_sharpe`
and the participation ratio, mean pairwise correlation, row count and method count that produced
it, so a caller can print *why*. Nothing in the lab calls it when this phase lands; phase 4 wires
the gate to it.

## Interface Contract

**Deletes:** none
**Renames:** none
**Creates:**

| Symbol | Kind | Signature / value |
|---|---|---|
| `seer_engine.lab.npolicy` | module | new file `engine/src/seer_engine/lab/npolicy.py` |
| `npolicy.Policy` | type alias | `Literal["all-trials", "methods", "effective"]` |
| `npolicy.POLICIES` | const | `tuple[Policy, ...] = ("all-trials", "methods", "effective")` |
| `npolicy.DEFAULT_POLICY` | const | `Policy = "all-trials"` — **reconciled**: it matches the policy the lab actually ships (`store.DSR_POLICY`, phase 4, Decision D1), so no code path can inherit a different N than the one the gate uses |
| `npolicy.DSR_MIN_N` | const | `int = 2` — below it `deflated_sharpe` is undefined |
| `npolicy.UnknownPolicy` | class | `class UnknownPolicy(ValueError)` |
| `npolicy.Correlation` | frozen dataclass | fields `participation_ratio: float`, `mean_pairwise: float \| None`, `curves_used: int`, `month_ends: int` |
| `npolicy.NCount` | frozen dataclass | fields `n: int`, `policy: Policy`, `trial_rows: int`, `distinct_methods: int`, `participation_ratio: float`, `mean_pairwise_corr: float \| None`, `curves_used: int`, `month_ends: int`; properties `floored: bool`, `basis: str`; method `evidence() -> str` |
| `npolicy.check_policy` | func | `check_policy(policy: str) -> Policy` |
| `npolicy.dev_method_count` | func | `dev_method_count(conn: sqlite3.Connection) -> int` |
| `npolicy.correlation` | func | `correlation(conn: sqlite3.Connection) -> Correlation` |
| `npolicy.participation_ratio` | func | `participation_ratio(conn: sqlite3.Connection) -> float` |
| `npolicy.effective_n` | func | `effective_n(conn: sqlite3.Connection, policy: str = DEFAULT_POLICY) -> NCount` |

**Signature changes:** none
**Requires (from earlier phases):** none — this phase has no dependencies and adds no caller.
**Provides (consumed by later phases):** phase 4 imports `npolicy.effective_n`, `npolicy.NCount`,
`npolicy.POLICIES` and `npolicy.check_policy` to define `store.DSR_POLICY` and `store.verdict`;
phase 5 imports `npolicy.POLICIES` and reads `NCount` generically (`dataclasses.asdict`) for
`lab luck` / `lab status`; phase 7 reads `NCount.policy`, `NCount.n` and **`NCount.basis`** for the
snapshot `gate` block, for `prereg.gate_text` and for the site label.

**`NCount.basis` is load-bearing for phase 7 and is why it exists** (reconciled): phase 7 writes it
verbatim into every committed `docs/lab/prereg/MNNNN.md` and into `web/data/lab.json`'s
`gate.dsrNBasis`. It must therefore be **one line, never empty, with no newline**, and stable for a
given database. `evidence()` stays as it is — it is the CLI's long form and repeats "N = … under
policy …", which `gate_text` and the site already say for themselves.

**`NCount.n` is `0` on a lab with no dev trials under `all-trials`, and that is deliberate**
(design note 1 below). Phase 7's snapshot guard was written assuming `>= 1`; it has been reconciled
to `>= 0`. Do not floor `all-trials` to make a downstream guard happy.

**Import-cycle note for phase 4 (load-bearing).** `npolicy` does **not** import `store` at module
scope. Its one use of `store` (`store.dev_trial_count`) is a function-local import inside
`effective_n`, precisely so that phase 4 may write `from seer_engine.lab import npolicy` at the
top of `store.py` without closing a cycle. Phase 4 must not "tidy" that deferred import upward.

**Leaves alone (owned by others):**
- `engine/src/seer_engine/lab/store.py` — phases 2 and 4
- `engine/src/seer_engine/lab/runner.py` — phases 2 and 4
- `engine/src/seer_engine/commands/lab.py` — phases 3 and 5
- `engine/src/seer_engine/backtest/dev.py` — nobody; `deflated_sharpe` is frozen by invariant 4
- `lab/lab.sqlite` — phase 4 alone (D5). This phase reads it read-only in one test and writes nothing.
- `engine/src/seer_engine/lab/prereg.py`, `paper/roster.py`, `web/*`, `docs/*` — phases 6 and 7

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/npolicy.py` | **create** | the whole module (Step 1) |
| `engine/tests/test_lab_npolicy.py` | **create** | 14 tests (Step 2) |
| `engine/pyproject.toml:10` | **verify only, no edit** | `numpy>=2` is already a declared dependency (Step 0) |

**Two files changed** (both new). No existing file is modified by this phase, and no file in this
phase is shared with another phase — phase 1 is the only phase that writes `lab/npolicy.py`.

## Implementation Steps

### Step 0: Confirm numpy is already a dependency (no edit expected)

**File:** `engine/pyproject.toml:10`
**Change:** none. Read it and confirm the line before writing Step 1.

Verified on the worktree at `a95126a`:

```toml
dependencies = [
  "psycopg[binary]>=3.2",
  "pandas>=2.2",
  "numpy>=2",
  "pandas_market_calendars>=5.0",
  "yfinance>=1.0",
  "requests>=2.32",
  "python-dotenv>=1.0",
  "scikit-learn>=1.9,<1.10",
  "openpyxl>=3.1",
]
```

`numpy>=2` is line 10. **Do not edit `pyproject.toml`.** The phase scope's contingency (a stdlib
Jacobi eigenvalue routine instead of adding a dependency) does not apply: numpy is already there,
`engine/tests/labkit.py:9` already imports it, and `conftest.py` already caps its thread pools to
one before it loads.

**Impact:** none. This step exists so the implementer does not add a redundant dependency line.

---

### Step 1: Create the module

**File:** `engine/src/seer_engine/lab/npolicy.py` (new file, 1-220)
**Change:** write the file below, verbatim. It is complete and runnable as written.

**Code:**

```python
"""The N the luck gate deflates by: the named policies and the effective-N estimator.

``deflated_sharpe`` (``backtest/dev.py``) assumes ``n_trials`` **independent** trial Sharpes.
The lab feeds it one per trial *row*, and the rows are not independent: measured over the
month-end equity curves the database already stores, the mean pairwise correlation across the
dev trials is ~0.60 and the participation ratio of their correlation matrix is ~2.4. Deflating
by the row count therefore asserts an independence the data contradicts and overstates the
hurdle (lab-luck-gate analysis, "The trials are not independent, and this is measurable").

This module names the three candidate answers and measures the evidence behind them. It
decides nothing: it is pure (reads, never writes; no clock, no filesystem, no network) and
nothing in the lab calls it until the gate is wired to it.

The policies:

- ``all-trials`` -- one look per dev trial row. The literal reading of design §3 and what the
  lab did before this module existed. 110 on the committed database.
- ``methods`` -- one look per distinct method with a dev trial, floored at the measured
  participation ratio: ``N = max(distinct_methods, ceil(participation_ratio))``. Counts a
  family of variants as the one idea it is, and the floor guarantees the policy can never
  assert fewer independent looks than the curves themselves show. 23 on the committed database.
- ``effective`` -- the measured participation ratio alone, rounded, floored at 2 (below 2 the
  deflated Sharpe is undefined). 2 on the committed database. The honest measure of how many
  independent *return streams* exist, and for that reason not a count of how many times the
  search looked: every strategy in the lab holds US large-cap equities, so the streams collapse
  onto the market factor. Kept live so the gate's sensitivity is inspectable.

The participation ratio is ``(Σλ)² / Σλ²`` over the eigenvalues of the correlation matrix of
the trials' monthly returns -- 1 when every curve is the same curve, N when they are mutually
uncorrelated.
"""

from __future__ import annotations

import json
import math
import sqlite3
from dataclasses import dataclass
from typing import Literal

import numpy as np

Policy = Literal["all-trials", "methods", "effective"]

POLICIES: tuple[Policy, ...] = ("all-trials", "methods", "effective")

# The policy a caller that does not name one gets. It is deliberately the same policy the lab
# actually ships -- ``store.DSR_POLICY = "all-trials"`` (LAB_LUCK_GATE_PLAN.md Decisions D1: the
# owner moved the threshold, not N) -- so that no code path can ever be deflated by an N the gate
# does not use. ``store`` sets its own constant explicitly and passes it to ``effective_n`` on
# every call, so this default is a belt beside that brace rather than the thing the gate relies
# on; the two agreeing is what makes a mistaken inheritance harmless instead of silent.
DEFAULT_POLICY: Policy = "all-trials"

# A curve needs this many month-ends to yield a variance, and the aligned grid this many to
# yield one return per trial that is worth correlating.
_MIN_POINTS = 3
# deflated_sharpe returns None below two trials, so no policy may resolve lower than this --
# except ``all-trials``, which is the literal row count and keeps reading 0 on an empty lab.
DSR_MIN_N = 2


class UnknownPolicy(ValueError):
    """A policy name that is not one of ``POLICIES``."""


@dataclass(frozen=True)
class Correlation:
    """What the dev curves say about how many independent looks the lab actually took.

    ``mean_pairwise`` is None when fewer than two curves survived alignment, which is also the
    case in which ``participation_ratio`` falls back to 1.0 rather than being measured.
    """

    participation_ratio: float
    mean_pairwise: float | None
    curves_used: int
    month_ends: int


@dataclass(frozen=True)
class NCount:
    """The N one policy resolves to, and the evidence a caller can print to say why."""

    n: int
    policy: Policy
    trial_rows: int
    distinct_methods: int
    participation_ratio: float
    mean_pairwise_corr: float | None
    curves_used: int
    month_ends: int

    @property
    def floored(self) -> bool:
        """True when the ``methods`` policy's participation-ratio floor is what decided ``n``.

        The floor is the policy's justification: it cannot assert fewer independent looks than
        the curves measurably have. On the committed database it does not bind (ceil(2.44) = 3
        against 23 methods); a lab of one method with many uncorrelated variants is where it does.
        """
        return self.policy == "methods" and math.ceil(self.participation_ratio) > self.distinct_methods

    @property
    def basis(self) -> str:
        """One line saying *what was counted* to get ``n``, in plain words. Never empty.

        Written verbatim into every committed ``docs/lab/prereg/MNNNN.md`` and into
        ``web/data/lab.json``'s ``gate.dsrNBasis``, both of which are one-line fields, so this
        must never contain a newline and must be stable for a given database. It says only what
        was counted; the caller already prints ``n`` and ``policy`` beside it, which is why this
        does not repeat them the way ``evidence()`` does.
        """
        rho = "" if self.mean_pairwise_corr is None else (
            f", mean pairwise correlation {self.mean_pairwise_corr:.3f}"
        )
        if self.policy == "all-trials":
            return (
                f"{self.trial_rows} dev trials, every variant run counted as one independent look"
            )
        if self.policy == "methods":
            floored = " (the participation-ratio floor binds)" if self.floored else ""
            return (
                f"{self.distinct_methods} distinct methods with a dev trial across "
                f"{self.trial_rows} trial rows, floored at ceil(participation ratio "
                f"{self.participation_ratio:.2f}){floored}"
            )
        return (
            f"participation ratio {self.participation_ratio:.2f} over {self.curves_used} dev "
            f"curves on {self.month_ends} common month-ends{rho}"
        )

    def evidence(self) -> str:
        rho = "n/a" if self.mean_pairwise_corr is None else f"{self.mean_pairwise_corr:.3f}"
        floor = " (the participation-ratio floor binds)" if self.floored else ""
        return (
            f"N = {self.n} under policy {self.policy!r}{floor}: "
            f"{self.trial_rows} dev trial rows, {self.distinct_methods} distinct methods, "
            f"participation ratio {self.participation_ratio:.2f} and mean pairwise correlation "
            f"{rho} over {self.curves_used} curves on {self.month_ends} common month-ends"
        )


def check_policy(policy: str) -> Policy:
    """``policy`` itself when it names a policy; raise ``UnknownPolicy`` otherwise."""
    if policy not in POLICIES:
        known = ", ".join(POLICIES)
        raise UnknownPolicy(f"unknown N policy {policy!r}; known policies: {known}")
    return policy  # type: ignore[return-value]


def dev_method_count(conn: sqlite3.Connection) -> int:
    """How many distinct methods have at least one dev trial."""
    return int(
        conn.execute("SELECT count(DISTINCT method_id) FROM trials WHERE window = 'dev'").fetchone()[0]
    )


def _dev_curves(conn: sqlite3.Connection) -> list[dict[str, float]]:
    """Every dev trial's month-end equity curve as {month-end: level}, skipping unusable ones.

    ``curve_json`` is NOT NULL on the table, but a curve can still be empty or short (a trial
    with almost no history), and this module must never raise on data it only reads.
    """
    out: list[dict[str, float]] = []
    for row in conn.execute("SELECT curve_json FROM trials WHERE window = 'dev' ORDER BY n"):
        text = row[0]
        if not text:
            continue
        try:
            points = json.loads(text)
        except (TypeError, ValueError):
            continue
        if not isinstance(points, list):
            continue
        curve: dict[str, float] = {}
        for point in points:
            if not isinstance(point, (list, tuple)) or len(point) != 2:
                continue
            day, value = point
            try:
                level = float(value)
            except (TypeError, ValueError):
                continue
            if math.isfinite(level):
                curve[str(day)] = level
        if len(curve) >= _MIN_POINTS:
            out.append(curve)
    return out


def _return_matrix(curves: list[dict[str, float]]) -> tuple[np.ndarray, int]:
    """(one row of monthly returns per usable curve, number of common month-ends).

    The curves are aligned on the month-ends common to *every* one of them, so each row is the
    same months measured the same way. A row whose levels are not all positive, whose returns
    are not all finite, or whose returns have no variance at all (a flat curve carries no
    information about independence) is dropped rather than correlated.
    """
    if len(curves) < 2:
        return np.zeros((0, 0)), 0
    common: set[str] = set(curves[0])
    for curve in curves[1:]:
        common &= set(curve)
    days = sorted(common)
    if len(days) < _MIN_POINTS:
        return np.zeros((0, 0)), len(days)
    rows: list[np.ndarray] = []
    for curve in curves:
        levels = np.asarray([curve[d] for d in days], dtype=float)
        if not np.all(levels > 0.0):
            continue
        rets = levels[1:] / levels[:-1] - 1.0
        if not np.all(np.isfinite(rets)):
            continue
        if float(np.std(rets)) <= 0.0:
            continue
        rows.append(rets)
    if len(rows) < 2:
        return np.zeros((0, 0)), len(days)
    return np.vstack(rows), len(days)


def correlation(conn: sqlite3.Connection) -> Correlation:
    """Measure the dev trials' co-movement from the curves already in ``trials.curve_json``.

    Reads only; spends no test-window look and runs no backtest. 1.0 with no measurement when
    fewer than two curves survive alignment -- one look is still one look.
    """
    curves = _dev_curves(conn)
    matrix, month_ends = _return_matrix(curves)
    count = int(matrix.shape[0])
    if count < 2:
        return Correlation(
            participation_ratio=1.0, mean_pairwise=None, curves_used=count, month_ends=month_ends
        )
    corr = np.corrcoef(matrix)
    corr = np.nan_to_num(np.asarray(corr, dtype=float), nan=0.0, posinf=0.0, neginf=0.0)
    eigenvalues = np.linalg.eigvalsh(corr)
    denominator = float(np.sum(eigenvalues**2))
    ratio = (float(np.sum(eigenvalues)) ** 2) / denominator if denominator > 0.0 else 1.0
    # The ratio is 1 for one shared factor and `count` for mutual independence; clamp, because
    # floating point on a near-singular matrix can step a hair outside either end.
    ratio = min(max(ratio, 1.0), float(count))
    upper = np.triu_indices(count, k=1)
    return Correlation(
        participation_ratio=ratio,
        mean_pairwise=float(np.mean(corr[upper])),
        curves_used=count,
        month_ends=month_ends,
    )


def participation_ratio(conn: sqlite3.Connection) -> float:
    """How many independent return streams the dev trials amount to: ``(Σλ)² / Σλ²``."""
    return correlation(conn).participation_ratio


def effective_n(conn: sqlite3.Connection, policy: str = DEFAULT_POLICY) -> NCount:
    """The multiple-testing N under ``policy``, with the evidence that produced it.

    ``NCount.n`` is the int to hand ``dev.deflated_sharpe``; the rest is why. Raises
    ``UnknownPolicy`` for a name outside ``POLICIES``.
    """
    # Deferred: ``store`` is the lab's own module and will import this one once the gate reads
    # the policy, so importing it at module scope would close a cycle.
    from seer_engine.lab import store

    name = check_policy(policy)
    evidence = correlation(conn)
    rows = store.dev_trial_count(conn)
    methods = dev_method_count(conn)
    ratio = evidence.participation_ratio
    if name == "all-trials":
        n = rows
    elif name == "methods":
        n = max(methods, math.ceil(ratio))
    else:
        # round() is half-to-even, which is deterministic and does not matter: a ratio landing
        # exactly on .5 is measurement noise either way.
        n = max(DSR_MIN_N, round(ratio))
    return NCount(
        n=int(n),
        policy=name,
        trial_rows=rows,
        distinct_methods=methods,
        participation_ratio=ratio,
        mean_pairwise_corr=evidence.mean_pairwise,
        curves_used=evidence.curves_used,
        month_ends=evidence.month_ends,
    )
```

**Impact:** purely additive. No existing symbol changes, no existing module imports this one, and
the lab's behaviour is byte-for-byte what it was. The only engine-wide risk a new lab module could
carry — an import cycle with `store` — is pre-empted by the deferred import inside `effective_n`.

**Design notes the implementer must not silently change:**

1. **`all-trials` is the literal row count, not floored.** It must keep returning 0 on an empty
   lab and `store.dev_trial_count(conn)` on a full one, because it is the "what the lab did
   before" baseline and phase 5's `lab luck` prints it against the others.
2. **`methods` is floored, `effective` is floored, `all-trials` is not.** `max(methods, ceil(pr))`
   and `max(2, round(pr))` respectively. The `methods` floor is Decision D1's justification.
3. **`ceil` for the floor, `round` for `effective`.** `ceil(2.442) = 3` as a floor is the
   conservative direction (never assert fewer looks than measured); `round(2.442) = 2` for
   `effective` is the honest point estimate.
4. **Zero-variance rows are dropped before `np.corrcoef`,** not after. `np.corrcoef` emits NaN
   for a constant row and a NaN anywhere poisons `eigvalsh`. The `np.nan_to_num` call after it is
   a second line of defence, not the first.
5. **Alignment is the intersection across *every* curve.** On the committed database that is 102
   month-ends out of 274 on the longest curve — the P7a seed trials start in 1993 and the lab
   methods later. Aligning pairwise instead would make the matrix non-comparable row to row.
6. **`DEFAULT_POLICY` is `"all-trials"`, matching `store.DSR_POLICY`.** An earlier draft of this
   phase set it to `"methods"`, which predates the owner's instruction of 2026-10-07 (the lever
   that moved is the threshold, not N — Decisions D1). Two different defaults in two modules is a
   trap: every caller passes the policy explicitly today, so the mismatch would be invisible until
   the one day somebody did not. Reconciled to one value in both places.
7. **`NCount.basis` is one line and never empty**, for every policy and on an empty lab. Phase 7
   writes it into a committed pre-registration and into `web/data/lab.json`, both one-line fields.

---

### Step 2: Create the tests

**File:** `engine/tests/test_lab_npolicy.py` (new file, 1-280)
**Change:** write the file below, verbatim.

**Code:**

```python
"""The N the luck gate deflates by (lab-luck-gate phase 1): the three named policies, the
participation-ratio estimator over the recorded dev curves, and the floor that keeps the
``methods`` policy from asserting fewer independent looks than the evidence shows.

Pure reads throughout: no backtest runs here and no test-window look is spent.
"""

from __future__ import annotations

import math
import sqlite3
from datetime import date

import numpy as np
import pytest

from seer_engine.lab import npolicy, store

# The committed database as this phase measured it (lab-luck-gate analysis, "Measured
# Evidence"). The lab grows, so the pinned assertions below skip once it does; the ordering
# assertions hold for every lab, forever.
COMMITTED_DEV_TRIALS = 110
COMMITTED_METHODS = 23
COMMITTED_PR = 2.442
COMMITTED_RHO = 0.595


@pytest.fixture()
def conn(tmp_path):
    c = store.connect(tmp_path / "lab.sqlite")
    yield c
    c.close()


def _method(conn, mid: str) -> None:
    with conn:
        store.add_method(
            conn, id=mid, name=f"n{mid}", family="f", source_kind="knowledge", hypothesis="h"
        )


def _month_ends(count: int) -> list[date]:
    return [date(1996 + i // 12, i % 12 + 1, 28) for i in range(count)]


def _curve(returns) -> str:
    """A month-end equity curve compounded from ``returns`` (one fewer month-end than points)."""
    days = _month_ends(len(returns) + 1)
    level = 1.0
    points = [(days[0], level)]
    for day, r in zip(days[1:], returns):
        level *= 1.0 + float(r)
        points.append((day, level))
    return store.curve_json(points)


def _trial(conn, method_id: str, tag: str, curve: str) -> None:
    row = store.TrialRow(
        method_id=method_id,
        candidate_id=f"{method_id}-{tag}",
        config_digest=f"{method_id}-{tag}-digest",
        config_text="t",
        rules_id="r",
        allocator_id="a",
        window="dev",
        start="2000-01-03",
        end="2015-10-16",
        store_fingerprint="fp",
        git_sha="abc",
        run_at="2026-10-07T00:00:00+00:00",
        total_return=1.0,
        cagr=0.1,
        max_drawdown=0.2,
        profit_factor=1.5,
        trades=200,
        sharpe=0.8,
        exposure=0.9,
        turnover=1.0,
        worst_year=2008,
        worst_year_return=-0.2,
        spy_tr_return=0.5,
        spy_tr_cagr=0.07,
        mar=0.5,
        failed="",
        eligible=True,
        dsr=0.9,
        n_trials_at_run=1,
        curve_json=curve,
    )
    with conn:
        store.insert_trials(conn, [row])


def _independent(count: int, months: int = 120, seed: int = 7) -> list[str]:
    """``count`` curves whose monthly returns are mutually uncorrelated by construction."""
    rng = np.random.default_rng(seed)
    return [_curve(rng.normal(0.006, 0.03, months)) for _ in range(count)]


# ---- the named set ---------------------------------------------------------------------------


def test_the_policy_names_are_a_closed_set():
    assert npolicy.POLICIES == ("all-trials", "methods", "effective")
    assert npolicy.DEFAULT_POLICY in npolicy.POLICIES
    # Reconciled: this module's default is the policy the lab ships (store.DSR_POLICY, phase 4),
    # so no caller can be deflated by an N the gate does not use. Phase 4 pins the other side.
    assert npolicy.DEFAULT_POLICY == "all-trials"
    for name in npolicy.POLICIES:
        assert npolicy.check_policy(name) == name
    with pytest.raises(npolicy.UnknownPolicy, match="unknown N policy"):
        npolicy.check_policy("per-variant")
    with pytest.raises(ValueError):  # UnknownPolicy is a ValueError, so callers may catch either
        npolicy.check_policy("")


def test_an_unknown_policy_is_refused_before_anything_is_measured(conn):
    with pytest.raises(npolicy.UnknownPolicy):
        npolicy.effective_n(conn, "all trials")


# ---- an empty lab ----------------------------------------------------------------------------


def test_an_empty_lab_measures_nothing_and_still_answers(conn):
    corr = npolicy.correlation(conn)
    assert corr.participation_ratio == 1.0
    assert corr.mean_pairwise is None
    assert corr.curves_used == 0
    assert npolicy.participation_ratio(conn) == 1.0
    assert npolicy.effective_n(conn, "all-trials").n == 0  # the literal row count, as before
    assert npolicy.effective_n(conn, "methods").n == 1
    assert npolicy.effective_n(conn, "effective").n == npolicy.DSR_MIN_N


# ---- what each policy counts -----------------------------------------------------------------


def test_all_trials_counts_rows_and_methods_counts_methods(conn):
    for mid in ("M0001", "M0002"):
        _method(conn, mid)
    curves = _independent(6)
    for i, curve in enumerate(curves):
        _trial(conn, "M0001" if i < 3 else "M0002", f"V{i}", curve)

    assert store.dev_trial_count(conn) == 6
    assert npolicy.dev_method_count(conn) == 2

    rows = npolicy.effective_n(conn, "all-trials")
    assert rows.n == 6
    assert rows.policy == "all-trials"
    assert rows.trial_rows == 6
    assert rows.distinct_methods == 2
    assert rows.curves_used == 6
    assert rows.month_ends == 121
    assert not rows.floored

    # Six uncorrelated curves: the participation ratio is near six, so the floor outranks the
    # two methods and the evidence -- not the method count -- decides N.
    methods = npolicy.effective_n(conn, "methods")
    assert methods.participation_ratio > 2.0
    assert methods.n == math.ceil(methods.participation_ratio)
    assert methods.floored


def test_the_methods_floor_binds_when_the_evidence_exceeds_the_method_count(conn):
    """One method, eight uncorrelated variants: 1 look is a claim the curves contradict."""
    _method(conn, "M0001")
    for i, curve in enumerate(_independent(8, seed=11)):
        _trial(conn, "M0001", f"V{i}", curve)

    count = npolicy.effective_n(conn, "methods")
    assert count.distinct_methods == 1
    assert count.participation_ratio > 1.0
    assert count.floored, "the floor must bind when the ratio exceeds the method count"
    assert count.n == math.ceil(count.participation_ratio) > count.distinct_methods
    assert count.n >= npolicy.DSR_MIN_N
    assert "the participation-ratio floor binds" in count.evidence()


def test_identical_curves_are_one_independent_look(conn):
    """The floor must not punish a family that is genuinely one idea measured many ways."""
    _method(conn, "M0001")
    one = _independent(1, seed=3)[0]
    for i in range(5):
        _trial(conn, "M0001", f"V{i}", one)

    corr = npolicy.correlation(conn)
    assert corr.curves_used == 5
    assert corr.participation_ratio == pytest.approx(1.0, abs=1e-9)
    assert corr.mean_pairwise == pytest.approx(1.0, abs=1e-9)

    assert npolicy.effective_n(conn, "all-trials").n == 5
    assert npolicy.effective_n(conn, "methods").n == 1  # the floor is 1 and does not bind
    assert npolicy.effective_n(conn, "effective").n == npolicy.DSR_MIN_N


def test_effective_is_the_rounded_ratio_floored_at_two(conn):
    _method(conn, "M0001")
    for i, curve in enumerate(_independent(5, seed=23)):
        _trial(conn, "M0001", f"V{i}", curve)

    count = npolicy.effective_n(conn, "effective")
    assert count.policy == "effective"
    assert count.n == max(npolicy.DSR_MIN_N, round(count.participation_ratio))
    assert count.n >= npolicy.DSR_MIN_N


# ---- what the estimator refuses to be fooled by ----------------------------------------------


def test_a_flat_curve_carries_no_information_and_is_dropped(conn):
    _method(conn, "M0001")
    for i, curve in enumerate(_independent(3, seed=5)):
        _trial(conn, "M0001", f"V{i}", curve)
    _trial(conn, "M0001", "FLAT", _curve([0.0] * 120))

    corr = npolicy.correlation(conn)
    assert store.dev_trial_count(conn) == 4
    assert corr.curves_used == 3, "a zero-variance curve must not enter the correlation matrix"
    assert npolicy.effective_n(conn, "all-trials").n == 4  # the row count is still the row count


def test_a_short_or_empty_curve_never_raises(conn):
    _method(conn, "M0001")
    for i, curve in enumerate(_independent(2, seed=9)):
        _trial(conn, "M0001", f"V{i}", curve)
    _trial(conn, "M0001", "EMPTY", "[]")
    _trial(conn, "M0001", "TINY", store.curve_json([(date(2000, 1, 31), 1.0)]))

    corr = npolicy.correlation(conn)
    assert corr.curves_used == 2
    assert npolicy.effective_n(conn, "methods").n >= 1


def test_the_test_window_is_never_read(conn):
    """Only dev trials count. No policy may be moved by a test-window look."""
    _method(conn, "M0001")
    for i, curve in enumerate(_independent(3, seed=13)):
        _trial(conn, "M0001", f"V{i}", curve)
    before = npolicy.effective_n(conn, "all-trials")

    row = store.TrialRow(
        method_id="M0001", candidate_id="M0001-T", config_digest="test-digest", config_text="t",
        rules_id="r", allocator_id="a", window="test", start="2015-10-19", end="2018-12-31",
        store_fingerprint="fp", git_sha="abc", run_at="2026-10-07T00:00:00+00:00", total_return=1.0,
        cagr=0.1, max_drawdown=0.2, profit_factor=1.5, trades=200, sharpe=0.8, exposure=0.9,
        turnover=1.0, worst_year=2008, worst_year_return=-0.2, spy_tr_return=0.5, spy_tr_cagr=0.07,
        mar=0.5, failed="", eligible=True, dsr=0.9, n_trials_at_run=1,
        curve_json=_independent(1, seed=99)[0],
    )
    with conn:
        store.insert_trials(conn, [row])

    after = npolicy.effective_n(conn, "all-trials")
    assert after == before


# ---- the evidence line phase 7 commits -------------------------------------------------------


def test_the_basis_is_one_usable_line_for_every_policy_on_every_lab(conn):
    """``NCount.basis`` is written verbatim into a committed pre-registration and into
    ``web/data/lab.json``'s one-line ``gate.dsrNBasis``. It must never be empty and never wrap."""
    for policy in npolicy.POLICIES:  # an empty lab first: snapshot runs on empty fixtures
        basis = npolicy.effective_n(conn, policy).basis
        assert basis and "\n" not in basis, policy

    _method(conn, "M0001")
    for i, curve in enumerate(_independent(4, seed=31)):
        _trial(conn, "M0001", f"V{i}", curve)
    for policy in npolicy.POLICIES:
        count = npolicy.effective_n(conn, policy)
        basis = count.basis
        assert basis and "\n" not in basis, policy
        assert basis == npolicy.effective_n(conn, policy).basis  # stable for one database
    assert "dev trials" in npolicy.effective_n(conn, "all-trials").basis
    assert "distinct methods" in npolicy.effective_n(conn, "methods").basis
    assert "participation ratio" in npolicy.effective_n(conn, "effective").basis


# ---- the committed database ------------------------------------------------------------------


def _committed():
    if not store.COMMITTED_DB.exists():
        pytest.skip("no committed lab database")
    conn = sqlite3.connect(f"file:{store.COMMITTED_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


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


def test_the_committed_evidence_at_110_dev_trials():
    """The three numbers this phase was specified against, pinned to the database it measured.

    Skips once Sera records more trials -- the invariant that outlives the counts is the
    ordering asserted above.
    """
    conn = _committed()
    try:
        if store.dev_trial_count(conn) != COMMITTED_DEV_TRIALS:
            pytest.skip(f"the lab has moved past {COMMITTED_DEV_TRIALS} dev trials")
        assert npolicy.dev_method_count(conn) == COMMITTED_METHODS
        assert npolicy.effective_n(conn, "all-trials").n == 110
        assert npolicy.effective_n(conn, "methods").n == 23
        assert npolicy.effective_n(conn, "effective").n == 2
        corr = npolicy.correlation(conn)
        assert corr.curves_used == COMMITTED_DEV_TRIALS
        assert corr.month_ends == 102
        assert corr.participation_ratio == pytest.approx(COMMITTED_PR, abs=5e-3)
        assert corr.mean_pairwise == pytest.approx(COMMITTED_RHO, abs=5e-3)
        # The line phase 7 commits into every pre-registration and into web/data/lab.json.
        assert npolicy.effective_n(conn, "all-trials").basis == (
            "110 dev trials, every variant run counted as one independent look"
        )
    finally:
        conn.close()
```

**Impact:** 14 new tests, all additive. The two committed-database tests open the file **read-only**
(`file:…?mode=ro`, the pattern `test_lab_methods.py:118` already uses for exactly this reason —
`COMMITTED_DB`, not `SEER_LAB_DB`, so a sera worktree sharing the main checkout's database does not
move the numbers). Nothing in this phase writes `lab/lab.sqlite`, upholding Decision D5 and
invariant 6.

**Why the pinned numbers are split into their own test.** `lab/lab.sqlite` is a live, growing
artifact: a Sera batch adds ~25 dev trials in a night, and a test asserting `110` would break for a
reason that is not a defect. `test_the_committed_database_orders_the_three_policies` therefore
asserts the forever-true relationship (`2 ≤ effective ≤ methods ≤ all-trials`, and that each policy
computes the formula it claims), and `test_the_committed_evidence_at_110_dev_trials` pins the exact
numbers this phase was specified against, skipping itself once the lab moves past 110.

---

## Verification

These numbers were measured on the worktree at base `a95126a` while this plan was written, against
`lab/lab.sqlite` opened read-only.

**Build:** `/home/miftah/seer/engine/.venv/bin/python -c "import seer_engine.lab.npolicy"` with
`PYTHONPATH=/home/miftah/.worktrees/seer/lab-luck-gate/engine/src`
(the worktree has no `engine/.venv`; use the main checkout's venv with `PYTHONPATH` shadowing the
editable install).

**Tests:**

```
cd /home/miftah/.worktrees/seer/lab-luck-gate/engine
PYTHONPATH=/home/miftah/.worktrees/seer/lab-luck-gate/engine/src \
  /home/miftah/seer/engine/.venv/bin/python -m pytest tests/test_lab_npolicy.py -q
```

Expected: `14 passed`.

Then the lab suite, to prove nothing regressed:

```
cd /home/miftah/.worktrees/seer/lab-luck-gate/engine
PYTHONPATH=/home/miftah/.worktrees/seer/lab-luck-gate/engine/src \
  /home/miftah/seer/engine/.venv/bin/python -m pytest tests/ -q
```

**Lint:**

```
/home/miftah/seer/engine/.venv/bin/python -m ruff check \
  --select E9,F --ignore F401 \
  /home/miftah/.worktrees/seer/lab-luck-gate/engine/src/seer_engine/lab/npolicy.py \
  /home/miftah/.worktrees/seer/lab-luck-gate/engine/tests/test_lab_npolicy.py
```

Expected: `All checks passed!`

**Manual check — the three numbers, by hand, on the committed database:**

```
cd /home/miftah/.worktrees/seer/lab-luck-gate
PYTHONPATH=engine/src /home/miftah/seer/engine/.venv/bin/python -c "
import sqlite3
from seer_engine.lab import npolicy, store
c = sqlite3.connect(f'file:{store.COMMITTED_DB}?mode=ro', uri=True)
c.row_factory = sqlite3.Row
for p in npolicy.POLICIES:
    print(npolicy.effective_n(c, p).evidence())
"
```

Expected output (exact to the stated precision; measured while writing this plan):

```
N = 110 under policy 'all-trials': 110 dev trial rows, 23 distinct methods, participation ratio 2.44 and mean pairwise correlation 0.595 over 110 curves on 102 common month-ends
N = 23 under policy 'methods': 110 dev trial rows, 23 distinct methods, participation ratio 2.44 and mean pairwise correlation 0.595 over 110 curves on 102 common month-ends
N = 2 under policy 'effective': 110 dev trial rows, 23 distinct methods, participation ratio 2.44 and mean pairwise correlation 0.595 over 110 curves on 102 common month-ends
```

The underlying measurement, reproduced independently of this module during planning:

| quantity | value |
|---|---|
| dev trial rows | 110 |
| test trial rows | **0** (invariant 2 holds; this phase reads only) |
| distinct methods with a dev trial | 23 |
| curves with a usable `curve_json` | 110 (none are empty) |
| month-ends common to every dev curve | 102 → 101 monthly returns per row |
| rows surviving the zero-variance drop | 110 |
| participation ratio `(Σλ)²/Σλ²` | 2.4424 (`ceil` 3, `round` 2) |
| mean pairwise correlation | 0.5954 (median 0.6399) |
| `max(23, ceil(2.4424))` | **23** |
| `max(2, round(2.4424))` | **2** |

**Exit criteria:**

1. `npolicy.effective_n(conn, "all-trials").n == 110`, `"methods" == 23`, `"effective" == 2` on
   the committed database (`test_the_committed_evidence_at_110_dev_trials`).
2. The `methods` policy's participation-ratio floor binds on a synthetic lab where the ratio
   exceeds the method count, and `NCount.floored` says so
   (`test_the_methods_floor_binds_when_the_evidence_exceeds_the_method_count`).
3. `2 ≤ effective ≤ methods ≤ all-trials` on any lab (`test_the_committed_database_orders_the_three_policies`).
3b. `npolicy.DEFAULT_POLICY == "all-trials"`, the same policy `store.DSR_POLICY` ships (phase 4),
   so no caller can inherit an N the gate does not use
   (`test_the_policy_names_are_a_closed_set`).
3c. `NCount.basis` is a non-empty single line for every policy, on an empty lab and on the
   committed one, and reads `"110 dev trials, every variant run counted as one independent look"`
   under `all-trials` at 110 dev trials — the string phase 7 commits into every pre-registration
   and into `web/data/lab.json` (`test_the_basis_is_one_usable_line_for_every_policy_on_every_lab`,
   `test_the_committed_evidence_at_110_dev_trials`).
4. `pytest` green in `engine/`; `ruff check --select E9,F` clean.
5. `git status` shows exactly two new files and **no modified file** — in particular
   `lab/lab.sqlite`, `store.py`, `runner.py`, `commands/lab.py` and `pyproject.toml` are untouched.
6. `store.test_looks(conn)` still reads `0` on the committed database.

**Commit allowlist (the swarm shares one worktree — see the project memory note).** Stage exactly:

```
engine/src/seer_engine/lab/npolicy.py
engine/tests/test_lab_npolicy.py
.workflows/plan/lab-luck-gate/phase-1.md
```

and verify after committing that the commit's file list *equals* that allowlist. Never
`git add -A`: phases 2 and 6 run concurrently in this same worktree.

## Handoffs

Work found while planning that this phase deliberately leaves alone:

- **Wiring the gate to the policy (R1, phase 4).** `runner.trial_rows` (`runner.py:170`) computes
  `n_trials = store.dev_trial_count(conn) + len(results)` and `store.best_dev_eligible`
  (`store.py:572`) selects `WHERE eligible = 1`. Both are phase 4's. This phase adds no caller; a
  `grep -rn npolicy engine/src` after it lands returns only `npolicy.py` itself.
- **`store.DSR_POLICY` (phase 4).** The single constant that picks the policy belongs in `store.py`
  with `DSR_MIN`, not here, so that overturning D1 is one edit in one place. **Reconciled:** phase 4
  sets `DSR_POLICY = "all-trials"` as an explicit literal, with the reasoning beside it, and passes
  it to `npolicy.effective_n` on every call — it deliberately does **not** write
  `DSR_POLICY = npolicy.DEFAULT_POLICY`, so a reader never has to work out which module's default
  wins. `npolicy.DEFAULT_POLICY` is now the same value for exactly that reason: the two cannot
  disagree, so an accidental inheritance is harmless rather than silent. Do not couple them by
  import in either direction.
- **The batch-inclusive N (phase 4).** Today's runner counts the batch being run (`+ len(results)`).
  `effective_n` reads only what is already recorded, because it is a pure read over the database.
  Phase 4 must decide whether a new batch's own variants raise its own N and say so explicitly;
  under `methods` the natural answer is `max(ncount.n, ...)` over the method being added, but that
  decision is phase 4's and this module deliberately does not pre-empt it.
- **Caching (nobody, yet).** `correlation` eigen-decomposes a 110×110 matrix on every call — about
  10 ms, called at most a handful of times per command. If phase 5's `lab luck` ends up calling
  it once per policy per method, memoise it there on the connection; do not add caching here, where
  it would make a pure function stateful.
- **`NCount` in the web snapshot (R1, phase 7).** `store.snapshot`'s `gate` block gains the policy
  name, the resolved N and `NCount.basis`. `NCount` is a flat frozen dataclass of JSON-safe scalars
  (`mean_pairwise_corr` is `float | None`), so phase 5 can `dataclasses.asdict` it; `basis` and
  `floored` are properties and are therefore **not** in `asdict`, which is correct — phase 5 prints
  the fields generically and phase 7 asks for `basis` by name.
- **`lab luck`'s N-sensitivity table (R3, phase 5).** `effective_n` over `POLICIES` is exactly
  the loop that reproduces the analysis document's table. Phase 5 owns the printing;
  `NCount.evidence()` is provided for it.
- **The `all-trials` floor.** `all-trials` returns 0 on an empty lab, which `deflated_sharpe`
  rejects with `None` — today's behaviour, preserved deliberately. If a later phase wants every
  policy floored at 2, that is a gate decision (phase 4), not an estimator one.

## Rollback

```
cd /home/miftah/.worktrees/seer/lab-luck-gate
git revert <phase-1 commit>
```

or, before the commit:

```
rm engine/src/seer_engine/lab/npolicy.py engine/tests/test_lab_npolicy.py
```

Nothing else is touched. The module has no callers, modifies no file, and writes no row, so
reverting it leaves the lab byte-for-byte as it is on `main` — the gate still deflates by
`store.dev_trial_count`, and `lab/lab.sqlite` was never opened for writing.

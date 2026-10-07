# Phase 3: `lab remeasure` — recover the DSR inputs for a recorded method

**Plan set:** `LAB_LUCK_GATE_PLAN.md`
**Analysis:** `20261007-085606-D3K1_code_analyzer.md`
**Satisfies:** R2 — a trial's verdict is frozen at the N of its run date, so verdicts are not
comparable across time and a method can never be re-judged. Phase 2 keeps the DSR's inputs for
every *new* trial; this phase recovers them for the 56 that predate it, so phase 4's derived
verdict has something to derive from.
**Depends on:** Phase 2
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine/lab` (+ one subcommand in `engine/src/seer_engine/commands`)

---

## Goal

`lab remeasure M0022` re-runs a recorded method's variants on the **dev** window through the same
`dev.run_registry` path `lab run` uses, proves the re-run is the same measurement by reproducing
each trial's recorded annualized Sharpe and its recorded `dsr` to within `1e-6`, and appends one
`trial_moments` row per trial — and nothing else. After this phase the 56 lab-method dev trials
recorded before phase 2 can be given back their `(sr_daily, t, skew, kurt, var_trials, n_at_run)`
one method at a time, on demand (decision D4), without rewriting a single recorded column, without
moving a status, and without the lab ever being able to construct a test-window store from this
command.

---

## The honest `var_trials` question — decided, and verified against the real database

The phase brief flags the subtlety: **`var_trials` as of the original run is not recorded
anywhere.** The brief offers two honest routes. **This plan takes route (b): the original
`var_trials` is reconstructed exactly, and the recomputed DSR is asserted, not merely reported.**

### Why it is reconstructible, exactly

`runner.trial_rows` (`lab/runner.py:166-170`) computes, once per `lab run`:

```python
prior       = store.dev_daily_sharpes(conn)                   # every dev trial's `sharpe` / sqrt(252)
new_sharpes = [daily_moments(r.stats.daily_returns)[0] ...]   # this batch's measured daily Sharpes
n_trials    = store.dev_trial_count(conn) + len(results)
var_trials  = statistics.variance(prior + new_sharpes)
```

Every term is recoverable:

1. `prior` is literally the `trials.sharpe` column divided by `sqrt(252)` — `dev_daily_sharpes`
   (`store.py:562`) is that one query and nothing else. The column is append-only and intact.
2. *Which* rows were in `prior` is pinned by two facts together: `trials.n` is a monotone
   `AUTOINCREMENT`, and `run_method` inserts its whole batch inside one `BEGIN IMMEDIATE`
   transaction (`runner.py:236-237`). So a batch's `n` are contiguous, and every dev trial that
   existed when the batch was deflated is exactly *a dev row with a lower `n`*.
3. `new_sharpes` is this batch's own measured daily Sharpes — which is precisely what the re-run
   produces. The re-run supplies them; the database supplies the rest.
4. `n_trials_at_run` is recorded per row, and it must equal
   `count(dev trials with n < batch's first n) + len(batch)`. **The command checks that equality
   before it reconstructs anything**, and refuses if it does not hold.

`statistics.variance` sums in exact `Fraction` arithmetic, so the result does not depend on the
order the two lists are concatenated in.

### Verified against the committed `lab/lab.sqlite`, with no backtest re-run

Reconstructing `var_trials` this way for all 56 lab-method dev trials and inverting each recorded
`dsr` for its per-trial constant `k = sqrt(t-1)/sqrt(radicand)`:

```
var at N=110 reconstructed = 2.395048e-04   (the analysis's independently measured 2.395e-04)
k across all 56 trials      = 69.10 .. 70.86, zero outliers
```

`k` is `sqrt(t-1)` scaled by a `radicand` near 1, and the dev window `1996-01-03..2015-10-16` is
≈4,985 sessions, so `k ≈ 69–71` is exactly the band a correct reconstruction must land in. A wrong
`var_trials` would scatter `k` across batches, because `SR*` enters the inversion linearly and the
twelve batches were deflated at twelve different `N` (58, 64, 69, 74, 80, 85, 90, 94, 100, 104,
107, 110). It does not scatter. The reconstruction is right.

### What is asserted, and what is only reported

| check | kind | tolerance | why |
|---|---|---|---|
| fresh `row.stats.sharpe` vs recorded `trials.sharpe` | **asserted**, aborts | `1e-9` relative | route (a)'s check, kept. It is the strictly-prior question — "did the store, the method file or the engine change?" — and it localizes a failure before the DSR arithmetic is blamed. |
| recomputed DSR at the **recorded** `n_trials_at_run` and the **reconstructed** `var_trials` vs recorded `dsr` | **asserted**, aborts | `1e-6` absolute | the phase's whole justification. Nothing is written unless every trial clears it. |

Nothing is "reported as a diagnostic instead of asserted", because nothing had to be. Route (a)'s
fallback was only needed if `var_trials` were unreconstructible; it is not.

One residual difference worth naming in the code, and named there: `book_runner._sharpe`
(`book_runner.py:485`) sums left-to-right while `backtest_dev.daily_moments` (`backtest_dev.py:419`)
uses `math.fsum`, so `recorded_sharpe / sqrt(252)` and the freshly measured `sr_daily` differ in the
last ulp. This changes nothing: the reconstruction feeds the *recorded column* into `prior` (exactly
as the original run did) and the *freshly measured* `sr_daily` into `new_sharpes` (exactly as the
original run did). The two paths are the same paths.

---

## Interface Contract

**Creates:**
- `seer_engine.lab.remeasure` (new module, `engine/src/seer_engine/lab/remeasure.py`) — and within it
  `remeasure.TRADING_DAYS`, `remeasure.SHARPE_TOL`, `remeasure.DSR_TOL`, `remeasure.Batch`,
  `remeasure.Reproduced`, `remeasure.Plan`, `remeasure.Report`, `remeasure.resolve_method`,
  `remeasure.preflight`, `remeasure.batches_of`, `remeasure.measure`, `remeasure.check`,
  `remeasure.remeasure`, `remeasure.format_report`
- `seer_engine.commands.lab._remeasure` (`commands/lab.py`, inserted between line 508 and line 511)
- the `remeasure` subparser (`commands/lab.py`, inserted between line 119 and line 120)
- the `"remeasure"` entry in `commands.lab._HANDLERS` (`commands/lab.py:626`, inserted after `"test"`)
- `engine/tests/test_lab_remeasure.py` (new)

**Deletes:** none.
**Renames:** none.
**Signature changes:** none. No existing function's signature changes.

**Changed later by phase 9 (which depends on this phase) — write these as specified here, and do
not pre-empt or revert them:**

| symbol | what phase 9 does | kind |
|---|---|---|
| `remeasure._moments_row` | annotation widened to `r: Reproduced \| SeedReproduced` | annotation-only; no call site, no runtime change (`from __future__ import annotations`) |
| `remeasure.resolve_method` | two sentences of its docstring and its `LabError` message replaced — they assert the `H-*` families can never be re-run, which phase 9 makes false | text-only; the message still contains `"not a lab method id"`, so this phase's `test_a_seed_family_is_refused_by_name` stays green |
| the `remeasure` subparser, `_remeasure` | gains `--only` / `--chunk`, a widened `method` metavar, and a two-line seed dispatch at the top of `_remeasure` | additive, entirely inside the region this phase creates |

Phase 9 adds a new section to `remeasure.py` and touches nothing else of this phase's. The
`_HANDLERS` entry and `batches_of`, `preflight`, `measure`, `check`, `remeasure` and
`format_report` are untouched by it.

**Requires (from earlier phases) — Phase 2, exactly these three symbols and nothing else:**

| symbol | shape this phase assumes |
|---|---|
| `store.MomentsRow` | a frozen dataclass constructible by keyword with the fields `trial_n: int`, `sr_daily: float`, `t: int`, `skew: float`, `kurt: float`, `var_trials: float \| None`, `n_at_run: int`, **`measured: str`** |
| `store.insert_moments(conn, rows)` | inserts a sequence of `MomentsRow` into `trial_moments`; **the caller holds the transaction** (the idiom `store.insert_trials` already uses, `store.py:534`); an empty sequence is a no-op |
| `store.moments_of(conn, trial_n)` | `sqlite3.Row \| None` for one trial's moments row, with at least the columns `sr_daily`, `t`, `skew`, `kurt`, `var_trials`, `n_at_run`, `measured` |

**Reconciled — `measured` is not optional.** Phase 2's `MomentsRow` carries an eighth field,
`measured: str`, with **no default**, backed by `TEXT NOT NULL CHECK (length(trim(measured)) > 0)`.
An earlier draft of this phase listed seven fields and built the row without it, which is a
`TypeError` on the first backfill. `_moments_row` below now passes `measured=store.now_iso()` — the
backfill's own stamp, deliberately **not** the old trial's `run_at`, because the re-measurement
happened today and the row says when it was made.

Also required of phase 2, and used only by this phase's tests: **`runner` must call the writer as
`store.insert_moments(...)`, not via `from seer_engine.lab.store import insert_moments`** — the
test fixture that reproduces "a trial recorded before the moments table existed" monkeypatches
`store.insert_moments` for the duration of one `run_method` call.

If phase 2 spells any of these differently, exactly two places in this phase need editing:
`remeasure._moments_row` (one constructor call) and the two `store.moments_of` call sites in
`remeasure.preflight`. Every other reference is to this phase's own code.

**Leaves alone (owned by others):**
- `lab/npolicy.py` (Phase 1)
- the `trial_moments` DDL, `_migrate`, `SCHEMA_VERSION`, `runner.trial_rows` (Phase 2) — consumed, never defined or edited here
- `store.DSR_POLICY`, `store.verdict`, `store.best_dev_eligible`, `TRANSITIONS`, the
  `rejected -> dev-eligible` edge, the committed `lab/lab.sqlite` (Phase 4)
- `commands/lab.py`'s `_status` (lines 178-235), its `misses()` helper at `:204-206` (Phase 4's
  one-line fix) and the read-only `lab luck` handler (Phase 5)
- `paper/roster.py` (Phase 6)
- `lab/prereg.py`, the design doc, `SKILL.md`, `web/` (Phase 7)

**Invariants this phase could break, and the structure that stops it:**

- **Invariant 2 (no test-window look).** Four independent noes, three of them structural:
  1. `remeasure.preflight` refuses, *by name and before any store is opened*, a method with any
     `window='test'` trial — the mirror of `runner.run_test`'s refusal of a dev store
     (`runner.py:507-513`).
  2. `commands/lab.py:_remeasure` calls `research.load_store(Path(args.store))` with **no `window`
     argument**. `load_store`'s default is `DEV_WINDOW` and it "fails loudly here instead of
     silently running the dev pipeline on test data" (`research.py:862-867`). A test store is
     refused by the loader before a byte of data is read. `declared_window` is never called, so
     there is no code path by which a test window can be *selected*.
  3. `remeasure.measure` refuses `data.window != research.DEV_WINDOW`.
  4. `remeasure.measure` calls `dev.run_registry(...)` with **no `window=` keyword**, and neither
     `measure` nor `remeasure` has a `window` parameter to pass one. A test asserts both: the
     signatures carry no `window`, and the captured `run_registry` kwargs carry no `window`.
- **Invariant 3 (`trials` stays append-only).** The module contains no `INSERT`, `UPDATE` or
  `DELETE` against `trials`, `methods` or any other table. Its only write is
  `store.insert_moments`. A test snapshots every column of every `trials` row and the whole
  `methods` row before and after, and asserts byte-equality.

---

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/remeasure.py` | create | the whole command: refusals, batch reconstruction, the re-run, the two checks, the one write |
| `engine/src/seer_engine/commands/lab.py` | modify | 4 insertions: docstring line (after `:18`), subparser (after `:119`), handler `_remeasure` (after `:508`), `_HANDLERS` entry (after `:626`) |
| `engine/tests/test_lab_remeasure.py` | create | 11 tests |

---

## Implementation Steps

### Step 1: the `remeasure` module

**File:** `engine/src/seer_engine/lab/remeasure.py` (new file)
**Change:** the whole command as a library, so `commands/lab.py` keeps a thin handler and this
phase never edits `lab/runner.py` (owned by phases 2 and 4) or `lab/store.py` (owned by 2 and 4).

**Code:**

```python
"""``lab remeasure <method>``: recover the DSR inputs of dev trials recorded before they were kept.

The lab's 56 lab-method dev trials predate the ``trial_moments`` table, so the four numbers a
re-evaluation needs -- the daily Sharpe, the number of returns, the skew and the kurtosis -- were
computed, used once and discarded. This module gets them back for one method at a time, on demand
(plan decision D4), by re-running that method's recorded variants on the dev window and proving
the re-run is the same measurement before it writes anything.

**What it writes:** ``trial_moments`` rows, and nothing else. There is no INSERT, UPDATE or DELETE
against ``trials`` or ``methods`` anywhere in this module; no status moves; no pre-registration is
written. ``trials`` stays append-only and every recorded ``dsr``, ``eligible``, ``failed`` and
``n_trials_at_run`` is left exactly as it is.

**Why a re-run can be trusted.** Two checks, both asserted, both aborting the whole command before
a single row is written:

1. the freshly measured annualized Sharpe reproduces the recorded ``trials.sharpe`` column to
   ``SHARPE_TOL`` relative. This asks the prior question -- has the research store, the method file
   or the engine changed since the trial ran? -- and it is the one a failure should name first.
2. the DSR recomputed from the fresh moments, at the trial's **recorded** ``n_trials_at_run`` and
   the **reconstructed** ``var_trials`` of its run, reproduces the recorded ``trials.dsr`` to
   ``DSR_TOL``. This is the phase's justification: a re-run that does not land on the recorded
   verdict is not the measurement that produced it, and backfilling it would launder a different
   number into the row's history.

**Reconstructing ``var_trials``.** It was never recorded, and it is still recoverable exactly.
``runner.trial_rows`` computes it as ``statistics.variance(prior + new_sharpes)`` where ``prior``
is ``store.dev_daily_sharpes`` -- the ``trials.sharpe`` column of every dev trial that existed --
and ``new_sharpes`` is the batch's own measured daily Sharpes. ``trials.n`` is a monotone
AUTOINCREMENT and ``run_method`` writes a whole batch inside one ``BEGIN IMMEDIATE``, so a batch's
trial numbers are contiguous and "every dev trial that existed then" is exactly "every dev row with
a lower ``n``". ``batches_of`` rebuilds that list from the column and checks it against the recorded
``n_trials_at_run`` before handing it back; the batch's own daily Sharpes come from the re-run,
which is what the original run used too. ``statistics.variance`` sums in exact Fraction arithmetic,
so the concatenation order is immaterial.

**The test window.** This command cannot spend a look, by construction rather than by care:

- a method with any ``window='test'`` trial is refused in ``preflight``, before a store is opened
  -- the mirror of ``runner.run_test`` refusing a dev store;
- the caller hands ``research.load_store`` no window, so it defaults to ``DEV_WINDOW`` and refuses
  a test store by name before reading a byte (``research.load_store``'s docstring);
- ``measure`` refuses a loaded store whose window is not ``research.DEV_WINDOW``;
- ``dev.run_registry`` is called with no ``window`` keyword, and neither ``measure`` nor
  ``remeasure`` has a ``window`` parameter with which to pass one.
"""

from __future__ import annotations

import logging
import math
import sqlite3
import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from seer_engine import research
from seer_engine.backtest import dev
from seer_engine.backtest.book_runner import TRADING_DAYS
from seer_engine.backtest.dev import Candidate, DevRow
from seer_engine.commands.backtest_dev import daily_moments, registry_problem
from seer_engine.lab import store
from seer_engine.lab.method import METHOD_ID, Method, config_digest, source_sha

log = logging.getLogger(__name__)

# The freshly measured annualized Sharpe against the recorded column. Same code, same store, same
# inputs: in practice this is bit-identical, and the tolerance exists only so a numpy or libm
# version bump in the last ulp does not read as a changed measurement.
#
# **Relative, deliberately, and the reason matters because phase 9's seed check is ABSOLUTE at
# 1e-6 and a reader will otherwise think one of the two is a mistake.** These values came out of
# the engine as full-precision IEEE doubles and went straight into `trials.sharpe`, so the only
# expected difference is a last-ulp wobble -- an error proportional to the magnitude, which is
# exactly the shape a relative bound has. Phase 9's 54 P7a seed rows did not come from the engine:
# they were imported from a CSV written to six decimal places, so their error source is decimal
# rounding, whose bound (5e-7) is ABSOLUTE and independent of magnitude. Same intent, two
# different error sources, two correctly different shapes of tolerance.
SHARPE_TOL = 1e-9  # relative -- full-precision engine floats; ulp-scaled error

# The recomputed DSR against the recorded column. The plan's mandated bar. Absolute because the
# DSR is a probability in [0, 1]: a relative bound would be meaninglessly tight near 0 and
# meaninglessly loose near 1.
DSR_TOL = 1e-6  # absolute


def _g(x: float | int | None) -> str:
    return "-" if x is None else f"{x:.12g}"


def _e(x: float | None) -> str:
    return "-" if x is None else f"{x:.3e}"


# --------------------------------------------------------------------------- what a re-run yields


@dataclass(frozen=True)
class Batch:
    """One ``lab run``'s dev trials and the lab-wide state they were deflated against.

    ``prior_sharpes`` is the daily Sharpe (``trials.sharpe`` / sqrt(252)) of every dev trial that
    preceded this batch, in trial-number order -- that is, ``store.dev_daily_sharpes`` as it read
    the instant before the batch was inserted.
    """

    run_at: str
    n_at_run: int
    trials: tuple[sqlite3.Row, ...]  # this batch's dev trials, by ``n``
    prior_sharpes: tuple[float, ...]


@dataclass(frozen=True)
class Reproduced:
    """One recorded trial, re-measured: its fresh moments beside what the lab recorded."""

    trial_n: int
    candidate_id: str
    n_at_run: int
    t: int
    sr_daily: float
    skew: float
    kurt: float
    var_trials: float | None
    recorded_sharpe: float | None
    measured_sharpe: float | None
    recorded_dsr: float | None
    recomputed_dsr: float | None

    @property
    def sharpe_delta(self) -> float | None:
        if self.recorded_sharpe is None or self.measured_sharpe is None:
            return None
        return abs(self.measured_sharpe - self.recorded_sharpe)

    @property
    def sharpe_ok(self) -> bool:
        delta = self.sharpe_delta
        if delta is None or self.recorded_sharpe is None:
            return False
        return delta <= SHARPE_TOL * max(abs(self.recorded_sharpe), 1.0)

    @property
    def dsr_delta(self) -> float | None:
        if self.recorded_dsr is None or self.recomputed_dsr is None:
            return None
        return abs(self.recomputed_dsr - self.recorded_dsr)

    @property
    def dsr_ok(self) -> bool:
        delta = self.dsr_delta
        return delta is not None and delta <= DSR_TOL

    @property
    def ok(self) -> bool:
        return self.sharpe_ok and self.dsr_ok


@dataclass(frozen=True)
class Plan:
    """What ``remeasure`` would do, decided from the database alone: no store, no backtest."""

    method_id: str
    batches: tuple[Batch, ...]
    candidates: tuple[Candidate, ...]  # the variants to re-run, in trial order
    missing: tuple[int, ...]  # trial numbers with no trial_moments row
    present: tuple[int, ...]  # trial numbers that already have one

    @property
    def nothing_to_do(self) -> bool:
        return not self.missing


@dataclass(frozen=True)
class Report:
    """What one ``lab remeasure`` did."""

    method_id: str
    measured: tuple[Reproduced, ...]
    written: tuple[int, ...]
    skipped: tuple[int, ...]


# --------------------------------------------------------------------------- refusals


def resolve_method(method_id: str) -> tuple[Method, Path]:
    """``(METHOD, its file)`` for a lab method id (``store.LabError`` otherwise).

    ``H-*`` ids -- the P7a seed families -- are refused by shape. Their trials carry
    ``dsr IS NULL`` by construction (``lab/seed.py:136``, "P7a reported it for one row only"), so
    there is no recorded verdict for a re-run to reproduce and no method file to re-run.

    NOTE TO THE IMPLEMENTER: write this text as it stands. **Phase 9 replaces these two sentences
    and the error message below**, because it adds a seed path that re-runs the ``H-*`` families
    out of the frozen registry and verifies them against six recorded metrics instead of a
    recorded DSR. Phase 9 depends on this phase and quotes the text above as the left side of its
    diff, so changing it here would break that diff. Do not pre-empt it, and do not revert it
    afterwards.
    """
    from seer_engine.lab.method import discover

    if METHOD_ID.fullmatch(method_id) is None:
        raise store.LabError(
            f"{method_id!r} is not a lab method id; `lab remeasure` takes a method like M0022. "
            f"The P7a seed families (H-*) recorded no DSR and have no method file, so there is "
            f"nothing to re-run and nothing to reproduce"
        )
    methods = discover()
    if method_id not in methods:
        raise store.LabError(
            f"no method file for {method_id} in seer_engine/lab/methods/. `lab remeasure` re-runs "
            f"the committed method file, not a database row. Known: {', '.join(methods) or '(none)'}"
        )
    return methods[method_id]


def batches_of(conn: sqlite3.Connection, trials: Sequence[sqlite3.Row]) -> tuple[Batch, ...]:
    """``trials`` (one method's dev rows, by ``n``) grouped into the ``lab run`` batches that
    wrote them, each carrying the daily Sharpes of every dev trial that preceded it.

    Two checks stand between the recorded rows and the reconstruction, and either one refuses:

    1. a batch's trial numbers are contiguous. One ``lab run`` writes its whole batch inside one
       ``BEGIN IMMEDIATE`` transaction (``runner.run_method``), so a gap means the rows were not
       written by one run and "what existed then" cannot be read off ``n``.
    2. ``count(dev trials with n < the batch's first n) + len(batch) == n_trials_at_run``. That
       equality *is* ``store.dev_trial_count(conn) + len(results)``, the line that produced the
       recorded N. If it does not hold, the recorded N does not describe this batch and no honest
       ``var_trials`` can be rebuilt from it.
    """
    groups: dict[tuple[str, int], list[sqlite3.Row]] = {}
    for row in trials:
        groups.setdefault((str(row["run_at"]), int(row["n_trials_at_run"])), []).append(row)
    out: list[Batch] = []
    for (run_at, n_at_run), group in groups.items():
        method_id = str(group[0]["method_id"])
        ns = [int(r["n"]) for r in group]
        first = ns[0]
        if ns != list(range(first, first + len(ns))):
            raise store.LabError(
                f"{method_id}: the dev trials {ns} recorded at {run_at} are not contiguous, so the "
                f"batch that deflated them cannot be reconstructed from the trial numbers. "
                f"Nothing is backfilled"
            )
        before = int(
            conn.execute(
                "SELECT count(*) FROM trials WHERE window = 'dev' AND n < ?", (first,)
            ).fetchone()[0]
        )
        if before + len(ns) != n_at_run:
            raise store.LabError(
                f"{method_id}: trial #{first} records N = {n_at_run}, but {before} dev trials "
                f"precede it and its batch holds {len(ns)}. The recorded N does not describe this "
                f"batch, so the var_trials it was deflated by cannot be reconstructed honestly. "
                f"Nothing is backfilled"
            )
        prior = tuple(
            float(r[0]) / math.sqrt(TRADING_DAYS)
            for r in conn.execute(
                "SELECT sharpe FROM trials WHERE window = 'dev' AND n < ? AND sharpe IS NOT NULL "
                "ORDER BY n",
                (first,),
            )
        )
        out.append(Batch(run_at=run_at, n_at_run=n_at_run, trials=tuple(group), prior_sharpes=prior))
    return tuple(out)


def preflight(
    conn: sqlite3.Connection, method: Method, path: Path, *, require_commit: bool = True
) -> Plan:
    """Every refusal ``lab remeasure`` makes from the database and the file alone.

    Nothing here opens a research store, runs a backtest or writes a row, and the test-window
    refusal is made first so a method that has had its look is told so before anything is loaded.
    ``require_commit=False`` skips the git check on the method file; it never relaxes the
    ``source_sha`` comparison, which is the stronger of the two.
    """
    row = store.get_method(conn, method.id)
    if row is None:
        raise store.LabError(
            f"no method {method.id} in the lab database; `lab remeasure` recovers the inputs of "
            f"trials the lab already recorded, and this method has none"
        )
    looks = conn.execute(
        "SELECT candidate_id, run_at FROM trials WHERE method_id = ? AND window = 'test' ORDER BY n",
        (method.id,),
    ).fetchall()
    if looks:
        spent = ", ".join(f"{r['candidate_id']} on {r['run_at']}" for r in looks)
        raise store.LabError(
            f"{method.id} has already had its look at the test window ({spent}). `lab remeasure` "
            f"re-runs the dev window, and it will not re-run anything for a method whose test "
            f"trial exists: the one look is spent, it is never given back, and nothing in this "
            f"command may stand near it"
        )
    trials = conn.execute(
        "SELECT * FROM trials WHERE method_id = ? AND window = 'dev' ORDER BY n", (method.id,)
    ).fetchall()
    if not trials:
        raise store.LabError(
            f"{method.id} has no dev trial, so there is nothing to re-measure. "
            f"`lab run {method.id}` records the trials and their moments in one transaction"
        )
    unverifiable = [r for r in trials if r["dsr"] is None or r["sharpe"] is None]
    if unverifiable:
        names = ", ".join(str(r["candidate_id"]) for r in unverifiable)
        raise store.LabError(
            f"{method.id}: {names} recorded no DSR or no Sharpe, so a re-run cannot be checked "
            f"against what the lab recorded. `lab remeasure` only backfills trials whose recorded "
            f"verdict it can reproduce"
        )
    if require_commit:
        problem = registry_problem(path)
        if problem is not None:
            raise store.LabError(
                f"{method.id}: {problem}. `lab remeasure` re-runs the committed method file -- the "
                f"same file the trials ran under -- and nothing else"
            )
    recorded_sha = row["source_sha"]
    if recorded_sha is None:
        raise store.LabError(
            f"{method.id} has no recorded source_sha, so nothing proves the method file on disk is "
            f"the one its trials ran under; a re-run would measure a different thing"
        )
    actual = source_sha(path)
    if actual != recorded_sha:
        raise store.LabError(
            f"{method.id}: the method file hashes {actual[:12]} but its trials ran under "
            f"{str(recorded_sha)[:12]}; the file changed after it ran. Re-running it would measure "
            f"a different configuration, not recover the recorded one"
        )
    by_digest = {config_digest(c): c for c in method.candidates}
    drifted = [r for r in trials if str(r["config_digest"]) not in by_digest]
    if drifted:
        names = ", ".join(str(r["candidate_id"]) for r in drifted)
        raise store.LabError(
            f"{method.id}: {names} has a configuration the method file no longer defines. The "
            f"recorded trials and the file have diverged, so the re-run would not be the same "
            f"measurement"
        )
    have = {int(r["n"]) for r in trials if store.moments_of(conn, int(r["n"])) is not None}
    return Plan(
        method_id=method.id,
        batches=batches_of(conn, trials),
        candidates=tuple(by_digest[str(r["config_digest"])] for r in trials),
        missing=tuple(int(r["n"]) for r in trials if int(r["n"]) not in have),
        present=tuple(sorted(have)),
    )


# --------------------------------------------------------------------------- the re-run


def measure(
    conn: sqlite3.Connection, method: Method, plan: Plan, data: research.ResearchData
) -> tuple[Reproduced, ...]:
    """Re-run ``plan.candidates`` on the dev window and reproduce each trial's recorded numbers.

    ``conn`` is read from only (``plan`` already carries every row this needs); it is taken so the
    signature matches the rest of the module and a future check can reach the database without a
    call-site change.

    The dev window is not a parameter and not a choice. ``data`` is refused unless it *is* the dev
    window -- the mirror of ``runner.run_test``'s refusal of a dev store -- and ``dev.run_registry``
    is called with no ``window`` keyword, so the run is bounded by ``DEV_WINDOW`` by construction.
    """
    if data.window != research.DEV_WINDOW:
        w = data.window
        raise store.LabError(
            f"{method.id}: this research store was built for the {w.name!r} window "
            f"({w.start}..{w.end}); `lab remeasure` re-runs the dev window and nothing else. "
            f"Build it with `python -m seer_engine research_store`"
        )
    rows: dict[str, DevRow] = {}

    def on_result(i: int, result: Any, row: DevRow) -> None:
        rows[config_digest(row.candidate)] = row

    dev.run_registry(
        data.market, data.dividends, data.spy_dividends, plan.candidates, on_result=on_result
    )
    out: list[Reproduced] = []
    for batch in plan.batches:
        moments: dict[int, tuple[float, float, float]] = {}
        fresh: list[float] = []
        for t in batch.trials:
            row = rows.get(str(t["config_digest"]))
            if row is None:
                raise store.LabError(
                    f"{method.id}: {t['candidate_id']} produced no row on the re-run. "
                    f"Nothing is backfilled"
                )
            m = daily_moments(row.stats.daily_returns)
            if m is None:
                raise store.LabError(
                    f"{method.id}: {t['candidate_id']} has no daily moments on the re-run but "
                    f"recorded a Sharpe of {_g(t['sharpe'])}; the re-run is not the recorded "
                    f"measurement. Nothing is backfilled"
                )
            moments[int(t["n"])] = m
            fresh.append(m[0])
        sharpes = list(batch.prior_sharpes) + fresh
        var_trials = statistics.variance(sharpes) if len(sharpes) >= 2 else None
        for t in batch.trials:
            row = rows[str(t["config_digest"])]
            sr, skew, kurt = moments[int(t["n"])]
            observations = len(row.stats.daily_returns)
            out.append(
                Reproduced(
                    trial_n=int(t["n"]),
                    candidate_id=str(t["candidate_id"]),
                    n_at_run=batch.n_at_run,
                    t=observations,
                    sr_daily=sr,
                    skew=skew,
                    kurt=kurt,
                    var_trials=var_trials,
                    recorded_sharpe=None if t["sharpe"] is None else float(t["sharpe"]),
                    measured_sharpe=row.stats.sharpe,
                    recorded_dsr=None if t["dsr"] is None else float(t["dsr"]),
                    recomputed_dsr=(
                        None
                        if var_trials is None
                        else dev.deflated_sharpe(
                            sr, batch.n_at_run, var_trials, observations, skew, kurt
                        )
                    ),
                )
            )
    return tuple(out)


def check(method_id: str, measured: Sequence[Reproduced]) -> None:
    """Raise ``store.LabError`` naming every trial the re-run failed to reproduce, and by how much.

    All or nothing: one divergent trial aborts the whole command. A partial backfill would put
    moments measured on one store beside moments measured on another, inside a table whose entire
    point is that a verdict can be recomputed from it.
    """
    bad = [r for r in measured if not r.ok]
    if not bad:
        return
    lines = [
        f"{method_id}: the re-run does not reproduce what the lab recorded, so it is not the same "
        f"measurement. Nothing was written."
    ]
    for r in bad:
        if not r.sharpe_ok:
            lines.append(
                f"  #{r.trial_n} {r.candidate_id}: annualized Sharpe {_g(r.recorded_sharpe)} "
                f"recorded, {_g(r.measured_sharpe)} measured (delta {_e(r.sharpe_delta)}, "
                f"tolerance {SHARPE_TOL:g} relative)"
            )
        else:
            lines.append(
                f"  #{r.trial_n} {r.candidate_id}: DSR {_g(r.recorded_dsr)} recorded, "
                f"{_g(r.recomputed_dsr)} recomputed at N={r.n_at_run} with var_trials "
                f"{_g(r.var_trials)} (delta {_e(r.dsr_delta)}, tolerance {DSR_TOL:g})"
            )
    lines.append(
        "  The research store, the method file or the engine has changed since those trials ran. "
        "Rebuild the dev store they were measured on and try again, or leave them un-remeasured: "
        "a trial with no moments keeps the verdict it already has."
    )
    raise store.LabError("\n".join(lines))


def _moments_row(r: Reproduced, measured: str) -> "store.MomentsRow":
    """One ``trial_moments`` row from a reproduced trial (phase 2 owns the dataclass).

    NOTE TO THE IMPLEMENTER: write the annotation as ``r: Reproduced``. **Phase 9 widens it to
    ``Reproduced | SeedReproduced``** -- annotation-only, no call site and no runtime behaviour
    changes, because the module has ``from __future__ import annotations``. Phase 9 reuses this
    builder rather than forking it, which is what this phase asked for; the widened annotation is
    the cost.

    ``n_at_run`` is the trial's **recorded** ``n_trials_at_run``, not today's dev trial count: the
    row documents the measurement that was made, and phase 4 derives a verdict under the current
    policy from the moments beside it.

    ``measured`` is **this backfill's** stamp, not the old trial's ``run_at``. A row written by
    ``lab run`` carries the trial's own ``run_at`` because the trial and its moments are one
    measurement with one stamp; a row written here was measured today, on today's research store
    and today's engine, and saying otherwise would claim a provenance it does not have. The two
    checks above are what tie it back to the original verdict; the stamp records when the tie was
    made.
    """
    return store.MomentsRow(
        trial_n=r.trial_n,
        sr_daily=r.sr_daily,
        t=r.t,
        skew=r.skew,
        kurt=r.kurt,
        var_trials=r.var_trials,
        n_at_run=r.n_at_run,
        measured=measured,
    )


def remeasure(
    conn: sqlite3.Connection,
    method: Method,
    path: Path,
    data: research.ResearchData,
    *,
    require_commit: bool = True,
) -> Report:
    """Re-measure ``method``'s recorded dev trials and append their ``trial_moments`` rows.

    Idempotent: when every dev trial already has its moments, this returns a Report that wrote
    nothing and names what it skipped. ``trial_moments`` is append-only, so "already there" is the
    answer, never a rewrite. The caller (``commands/lab.py``) runs ``preflight`` first and skips
    loading a research store at all in that case.

    The write is the last thing that happens and it is one statement: ``store.insert_moments``
    inside one ``BEGIN IMMEDIATE``, after both checks have passed for every trial. ``preflight``
    runs again inside the lock because a parallel explorer session may have backfilled the same
    method in between -- the same race ``runner.run_method`` guards.
    """
    plan = preflight(conn, method, path, require_commit=require_commit)
    if plan.nothing_to_do:
        return Report(method_id=method.id, measured=(), written=(), skipped=plan.present)
    measured = measure(conn, method, plan, data)
    check(method.id, measured)
    stamp = store.now_iso()  # when this backfill measured, not when the trial ran
    store.begin_immediate(conn)
    with conn:
        fresh = preflight(conn, method, path, require_commit=False)
        have = set(fresh.present)
        rows = [_moments_row(r, stamp) for r in measured if r.trial_n not in have]
        store.insert_moments(conn, rows)
    return Report(
        method_id=method.id,
        measured=measured,
        written=tuple(r.trial_n for r in rows),
        skipped=tuple(sorted(have)),
    )


# --------------------------------------------------------------------------- what it prints


def format_report(report: Report) -> str:
    """The per-trial reproduction report: what was recorded, what was measured, the difference."""
    out: list[str] = [
        f"{report.method_id}: {len(report.measured)} dev trial(s) re-measured on the dev window",
        "",
    ]
    for r in report.measured:
        mark = "wrote" if r.trial_n in report.written else "kept "
        out.append(
            f"  {mark} #{r.trial_n} {r.candidate_id}  N={r.n_at_run}  t={r.t}  "
            f"sr_daily={_g(r.sr_daily)}  skew={_g(r.skew)}  kurt={_g(r.kurt)}  "
            f"var_trials={_g(r.var_trials)}"
        )
        out.append(
            f"        Sharpe {_g(r.recorded_sharpe)} recorded vs {_g(r.measured_sharpe)} measured "
            f"(delta {_e(r.sharpe_delta)}, tolerance {SHARPE_TOL:g} relative)"
        )
        out.append(
            f"        DSR    {_g(r.recorded_dsr)} recorded vs {_g(r.recomputed_dsr)} recomputed "
            f"at N={r.n_at_run} (delta {_e(r.dsr_delta)}, tolerance {DSR_TOL:g})"
        )
    if report.skipped:
        out.append("")
        out.append(
            "  already recorded, left alone: " + ", ".join(f"#{n}" for n in report.skipped)
        )
    out.append("")
    out.append(
        f"  wrote {len(report.written)} trial_moments row(s). No trials row was inserted, updated "
        f"or deleted; no method status moved; no pre-registration was written"
    )
    return "\n".join(out)
```

**Impact:** a new module, imported by nothing until step 3. It reads `trials`, `methods` and
`trial_moments`, and writes `trial_moments` only.

---

### Step 2: the subcommand's four insertions in `commands/lab.py`

**Shared-file protocol (reconciled).** Three phases write `commands/lab.py`: **3** (this one,
`lab remeasure`), **4** (`lab reevaluate`, plus the one-line `misses()` correctness fix at
`:204-206`) and **5** (`lab status`'s promotion path and the read-only `lab luck`). All four of
this phase's edits are **insertions at anchors neither of the others touches**:

| phase | docstring | subparser | handler | `_HANDLERS` | other |
|---|---|---|---|---|---|
| 3 (here) | after the `lab test` block (`:18`) | after the `test` subparser (`:119`) | after `_test` (`:508`) | one line after `"test"` | — |
| 4 | after the `lab promote` block (`:10-12`) | after the `promote` block (`:90-99`) | after `_promote` (`:340`) | one line after `"promote"` | `misses()` at `:204-206` |
| 5 | the `lab status` line (`:3`) + a `lab luck` entry | after the `status` subparser (`:70`) | between `_status` (`:235`) and `_show` (`:238`) | one line after `"status"` | `_status`'s section loop (`:214-223`), the import block |

Three rules bind all three phases:

1. **Insert at your named anchor; never rewrite a whole literal.** The `_HANDLERS` dict gets **one
   new line per phase**, never a replacement of the dict — a whole-dict rewrite by a later phase
   silently deletes the earlier phases' keys. The import block is likewise a **union**: add what
   you need, keep what is there.
2. **Anchor on quoted text, not on a line number.** Every line number above is the number on
   `main`; whichever of these phases lands first moves the others.
3. **The swarm shares one worktree.** A commit of `commands/lab.py` may legitimately carry another
   phase's insertions at other anchors. Keep them; never revert another phase's region, never
   `git add -A`.

After all three have landed the dict reads exactly (alphabetical within the existing order):

```python
_HANDLERS = {
    "status": _status,
    "luck": _luck,            # phase 5, read-only
    "show": _show,
    "run": _run,
    "promote": _promote,
    "reevaluate": _reevaluate,  # phase 4, writes
    "test": _test,
    "remeasure": _remeasure,    # phase 3, writes trial_moments only
    "idea": _idea,
    "note": _note,
    "block": _block,
    "drop": _drop,
    "seen": _seen,
    "insight": _insight,
    "stage": _stage,
    "next-id": _next_id,
    "export": _export,
    "export-json": _export_json,
    "seed": _seed,
}
```

#### 2a — the usage docstring

**File:** `engine/src/seer_engine/commands/lab.py:18` (insert between line 18 and line 19)
**Change:** one usage entry, after the `lab test` block and before `lab idea`.
**Code:** the file reads

```python
    s.add_argument("--dry-run", action="store_true",
                   help="print what would run -- the window, the store, the pre-registration and "
                        "the conditions that decide the verdict -- and stop. Loads nothing, runs "
                        "nothing, records nothing; the look is not spent")
```

in the parser; the *docstring* lines 12-19 currently read:

```
    lab test M0007-A [--store DIR] [--roster-id ID] [--dry-run]
                                    the one counted look: run a promoted method's pre-registered
                                    variant once on the test window, record a `test` trial and set
                                    test-passed / test-failed (both final). Refuses without a
                                    committed pre-registration, refuses a method that is not
                                    promoted, and the database refuses a second look. --dry-run
                                    prints what would run and spends nothing
    lab idea --name ... --hypothesis ...   queue an idea (prints its id)
```

Insert between them so it becomes:

```
    lab test M0007-A [--store DIR] [--roster-id ID] [--dry-run]
                                    the one counted look: run a promoted method's pre-registered
                                    variant once on the test window, record a `test` trial and set
                                    test-passed / test-failed (both final). Refuses without a
                                    committed pre-registration, refuses a method that is not
                                    promoted, and the database refuses a second look. --dry-run
                                    prints what would run and spends nothing
    lab remeasure M0022 [--store DIR]
                                    re-run a recorded method's variants on the dev window and
                                    write back the DSR inputs (trial_moments) its trials predate.
                                    Writes nothing else: no trials row, no status, no
                                    pre-registration. Idempotent, and refuses a method that has
                                    already had its test-window look
    lab idea --name ... --hypothesis ...   queue an idea (prints its id)
```

**Impact:** documentation only.

#### 2b — the subparser

**File:** `engine/src/seer_engine/commands/lab.py:119` (insert between line 119, the blank line
after the `test` subparser, and line 120, `s = sub.add_parser("idea", ...)`)
**Change:** register `remeasure`.
**Code:**

```python
    s = sub.add_parser(
        "remeasure",
        help="recover the DSR inputs (trial_moments) of a method whose trials predate them",
    )
    s.add_argument("method", metavar="M0022",
                   help="the lab method whose recorded dev trials get their moments back")
    s.add_argument(
        "--store",
        type=Path,
        default=Path(os.environ.get("SEER_RESEARCH_STORE") or research.STORE_DIR),
        help=f"dev-window research store (default: {research.STORE_DIR}, or "
             "$SEER_RESEARCH_STORE). A test store is refused by research.load_store before a "
             "byte is read: this command never names a test window and never spends a look",
    )
```

**Impact:** `lab remeasure` becomes reachable. `os`, `Path` and `research` are already imported
(`commands/lab.py:41-45`).

#### 2c — the handler

**File:** `engine/src/seer_engine/commands/lab.py:508` (insert between line 508, `_test`'s
`return 0`, and line 511, `def _idea`)
**Change:** the thin handler.
**Code:**

```python
def _remeasure(conn, args) -> int:
    """``lab remeasure M0022``: recover the DSR inputs of trials recorded before they were kept.

    Re-runs the method's recorded variants on the **dev** window through the same
    ``dev.run_registry`` path ``lab run`` uses, proves the re-run reproduces each trial's recorded
    Sharpe and DSR, and appends ``trial_moments`` rows -- nothing else. No ``trials`` row is
    inserted, updated or deleted; no status moves; no pre-registration is written.

    The test window is unreachable from here by construction, not by care: a method with a
    ``window='test'`` trial is refused by ``remeasure.preflight`` before this function opens
    anything, ``research.load_store`` is called with no ``window`` so it defaults to ``DEV_WINDOW``
    and refuses a test store by name, and ``remeasure.measure`` refuses a loaded store that is not
    the dev window and calls ``dev.run_registry`` with no window argument at all.

    When every dev trial already has its moments, this prints what it skipped and returns without
    loading a research store: re-loading a 135 MB store and re-running backtests to write nothing
    is not idempotence. (For scale, measured: the store load is ~11s and all 54 P7a seed
    candidates re-run in ~52s. A method's two to five variants are seconds. Nothing here is an
    hours-long job, and no doc in this set may say it is.)
    """
    from seer_engine.lab import remeasure as rm

    method, path = rm.resolve_method(args.method)
    plan = rm.preflight(conn, method, path)
    if plan.nothing_to_do:
        print(f"{method.id}: every dev trial already has its moments; nothing to do.")
        print("  already recorded: " + ", ".join(f"#{n}" for n in plan.present))
        print(f"\nLab N (dev trials) is still {store.dev_trial_count(conn)}; "
              f"test-window looks used: {store.test_looks(conn)}")
        return 0
    if research.DEV_END != dev.DEV_END:
        raise store.LabError("research.DEV_END differs from dev.DEV_END; refusing to run")
    t0 = time.perf_counter()
    try:
        data = research.load_store(Path(args.store))
    except FileNotFoundError as e:
        raise store.LabError(
            f"research store {args.store} is missing {e.filename or e}; build it with "
            "`python -m seer_engine research_store`"
        ) from e
    except ValueError as e:
        raise store.LabError(
            f"{args.store}: {e}. `lab remeasure` asks load_store for the dev window and nothing "
            f"else, so a test-window store is refused here rather than re-measured"
        ) from e
    log.info("research store %s loaded (%.1fs)", data.fingerprint[:12], time.perf_counter() - t0)
    report = rm.remeasure(conn, method, path, data)
    print(rm.format_report(report))
    print(f"\nLab N (dev trials) is still {store.dev_trial_count(conn)}; "
          f"test-window looks used: {store.test_looks(conn)}")
    return 0
```

**Impact:** `store.LabError` from any refusal becomes exit 2 through the existing `run()` wrapper
(`commands/lab.py:164-172`). `time`, `dev`, `research`, `store`, `Path` and `log` are all already
imported.

#### 2d — the handler table

**File:** `engine/src/seer_engine/commands/lab.py:626` (insert immediately after `"test": _test,`)
**Change:** **one line, inserted** — not a rewrite of the dict. Phase 4 inserts `"reevaluate"`
after `"promote"` and phase 5 inserts `"luck"` after `"status"` into the same literal, and a
whole-dict replacement by any of the three would silently delete the other two keys.

**Code:** insert exactly this line after the `"test": _test,` line:

```python
    "remeasure": _remeasure,
```

so that the dict reads, in this phase's part of it:

```python
    "promote": _promote,
    "test": _test,
    "remeasure": _remeasure,
    "idea": _idea,
```

**Impact:** dispatch. The dict as it reads after all three phases land is quoted at the top of
Step 2; if `"reevaluate"` or `"luck"` is already present when you get here, leave it alone.

---

### Step 3: the tests

**File:** `engine/tests/test_lab_remeasure.py` (new file)
**Change:** 11 tests. The headline one — `test_the_reconstructed_var_trials_equals_what_the_run_used`
— runs the same method twice into two databases, once with phase 2's writer live and once with it
suppressed, and asserts the backfilled `var_trials` is **exactly** the number the live run stored.
That is the strongest available proof that this phase's reconstruction is the original quantity and
not a plausible-looking substitute.

**Code:**

```python
"""``lab remeasure`` (plan phase 3): recover the DSR inputs of trials recorded before them.

The fixture that matters is ``no_moments``: it suppresses phase 2's ``store.insert_moments`` for
the duration of one ``runner.run_method`` call, which is exactly the shape of the 56 lab-method dev
trials recorded before the ``trial_moments`` table existed.
"""

from __future__ import annotations

import dataclasses
import inspect
from datetime import date
from pathlib import Path

import pytest
from labkit import smoke_data, smoke_test_data

from seer_engine import research
from seer_engine.backtest import dev
from seer_engine.backtest.dev import Candidate
from seer_engine.lab import remeasure, runner, store
from seer_engine.lab.method import Method
from seer_engine.lab.seed import seed
from seer_engine.sim.rules import DAILY_SWITCH, MONTHLY_HOLD
from seer_engine.strategies.f_index import TIMING, TimingParams

HERE = Path(__file__)


def _cand(cid: str, family: str, rules=MONTHLY_HOLD, n: int = 50) -> Candidate:
    return Candidate(
        id=cid, family=family, rules=rules, allocator=TIMING,
        params=TimingParams(hold="SPY", signal="SPY", rule="sma", n=n),
        rationale="test", added=date(2026, 10, 4), owner_inputs=(),
    )


def _method(mid="M0001", cands=None, **kw) -> Method:
    cands = cands or (_cand(f"{mid}-A", mid), _cand(f"{mid}-B", mid, rules=DAILY_SWITCH, n=20))
    base = dict(id=mid, name="SMA test", family="trend", source_kind="knowledge", source_ref="",
                hypothesis="h", expected_failure="f", candidates=tuple(cands))
    base.update(kw)
    return Method(**base)


@pytest.fixture()
def conn(tmp_path):
    c = store.connect(tmp_path / "lab.sqlite")
    seed(c)
    yield c
    c.close()


@pytest.fixture(scope="module")
def data():
    return smoke_data()


@pytest.fixture()
def no_moments(monkeypatch):
    """``lab run`` as it behaved before ``trial_moments``: trials written, moments not.

    Yields the ``monkeypatch`` instance so a test can ``.undo()`` the suppression after the run it
    was for -- pytest hands the fixture and the test the same instance, so a test that also takes
    ``monkeypatch`` must call ``no_moments.undo()`` **before** its own ``setattr``.
    """
    monkeypatch.setattr(store, "insert_moments", lambda conn, rows: None)
    yield monkeypatch


def _run(conn, data, method):
    return runner.run_method(conn, method, HERE, data, git_sha="deadbeef", require_commit=False)


def _trials_snapshot(conn):
    return [tuple(r) for r in conn.execute("SELECT * FROM trials ORDER BY n")]


# ---- the backfill ------------------------------------------------------------------------------


def test_remeasure_backfills_moments_and_reproduces_the_recorded_dsr(conn, data, no_moments):
    m = _method()
    _run(conn, data, m)
    no_moments.undo()
    numbers = [int(r["n"]) for r in store.trials_of(conn, "M0001")]
    assert numbers == [55, 56]
    assert all(store.moments_of(conn, n) is None for n in numbers)

    report = remeasure.remeasure(conn, m, HERE, data, require_commit=False)

    assert sorted(report.written) == numbers
    assert report.skipped == ()
    assert len(report.measured) == 2
    for r in report.measured:
        assert r.ok
        assert r.sharpe_delta <= remeasure.SHARPE_TOL * max(abs(r.recorded_sharpe), 1.0)
        assert r.dsr_delta <= remeasure.DSR_TOL
        assert r.n_at_run == 56
    for n in numbers:
        row = store.moments_of(conn, n)
        assert row is not None and row["n_at_run"] == 56 and row["t"] > 2
    assert store.test_looks(conn) == 0
    text = remeasure.format_report(report)
    assert "re-measured on the dev window" in text and "No trials row was inserted" in text


def test_the_reconstructed_var_trials_equals_what_the_run_used(tmp_path, data, monkeypatch):
    """The proof that the reconstruction is the original quantity, not a lookalike.

    ``var_trials`` as of a run is recorded nowhere. Run the same method into two databases -- once
    with phase 2's writer live, once with it suppressed and then backfilled by ``remeasure`` -- and
    the two ``trial_moments`` rows must agree exactly.
    """
    m = _method()
    live = store.connect(tmp_path / "live.sqlite")
    seed(live)
    runner.run_method(live, m, HERE, data, git_sha="x", require_commit=False)
    truth = {int(r["n"]): dict(store.moments_of(live, int(r["n"])))
             for r in store.trials_of(live, "M0001")}
    live.close()
    assert truth and all(v["var_trials"] is not None for v in truth.values())

    back = store.connect(tmp_path / "back.sqlite")
    seed(back)
    monkeypatch.setattr(store, "insert_moments", lambda conn, rows: None)
    runner.run_method(back, m, HERE, data, git_sha="x", require_commit=False)
    monkeypatch.undo()
    remeasure.remeasure(back, m, HERE, data, require_commit=False)
    for n, want in truth.items():
        got = store.moments_of(back, n)
        assert got["var_trials"] == want["var_trials"]
        assert got["sr_daily"] == want["sr_daily"]
        assert got["t"] == want["t"]
        assert got["skew"] == want["skew"]
        assert got["kurt"] == want["kurt"]
        assert got["n_at_run"] == want["n_at_run"]
    back.close()


def test_remeasure_is_idempotent(conn, data, no_moments):
    m = _method()
    _run(conn, data, m)
    no_moments.undo()
    first = remeasure.remeasure(conn, m, HERE, data, require_commit=False)
    assert len(first.written) == 2
    before = {n: dict(store.moments_of(conn, n)) for n in first.written}

    plan = remeasure.preflight(conn, m, HERE, require_commit=False)
    assert plan.nothing_to_do and sorted(plan.present) == sorted(first.written)

    second = remeasure.remeasure(conn, m, HERE, data, require_commit=False)
    assert second.written == () and second.measured == ()
    assert sorted(second.skipped) == sorted(first.written)
    assert {n: dict(store.moments_of(conn, n)) for n in first.written} == before


def test_remeasure_writes_only_trial_moments(conn, data, no_moments):
    m = _method()
    _run(conn, data, m)
    no_moments.undo()
    trials_before = _trials_snapshot(conn)
    method_before = tuple(store.get_method(conn, "M0001"))

    remeasure.remeasure(conn, m, HERE, data, require_commit=False)

    assert _trials_snapshot(conn) == trials_before
    assert tuple(store.get_method(conn, "M0001")) == method_before
    assert store.dev_trial_count(conn) == 56
    assert store.test_looks(conn) == 0


# ---- the refusals ------------------------------------------------------------------------------


def test_a_method_with_a_test_trial_is_refused_before_anything_is_loaded(conn, data, no_moments):
    m = _method()
    ran = _run(conn, data, m)
    no_moments.undo()
    # The same configuration, one window along: `UNIQUE(config_digest, window)` and
    # `UNIQUE(candidate_id, window)` are both per-window, so this is the shape `lab test` writes.
    with conn:
        store.insert_trials(conn, [dataclasses.replace(ran[0].trial, window="test")])
    assert store.test_looks(conn) == 1
    # `data` is never reached: preflight refuses first, so None is safe to pass.
    with pytest.raises(store.LabError, match="look at the test window"):
        remeasure.remeasure(conn, m, HERE, None, require_commit=False)


def test_a_method_with_no_dev_trial_is_refused(conn, data):
    with conn:
        store.add_method(conn, id="M0003", name="queued", family="trend",
                         source_kind="knowledge", hypothesis="h")
    with pytest.raises(store.LabError, match="no dev trial"):
        remeasure.remeasure(conn, _method("M0003"), HERE, None, require_commit=False)


def test_a_seed_family_is_refused_by_name(conn):
    with pytest.raises(store.LabError, match="not a lab method id"):
        remeasure.resolve_method("H-P7A-F1")
    with pytest.raises(store.LabError, match="no method file"):
        remeasure.resolve_method("M9999")


def test_a_trial_with_no_recorded_dsr_cannot_be_verified(conn, data, no_moments):
    """The P7a seed's shape: a dev trial whose ``dsr`` is NULL has no verdict to reproduce."""
    ran = _run(conn, data, _method())
    no_moments.undo()
    with conn:
        store.add_method(conn, id="M0003", name="seed-shaped", family="trend",
                         source_kind="knowledge", hypothesis="h")
        store.insert_trials(conn, [dataclasses.replace(
            ran[0].trial, method_id="M0003", candidate_id="M0003-A",
            config_digest="0" * 64, dsr=None,
        )])
    with pytest.raises(store.LabError, match="recorded no DSR"):
        remeasure.preflight(conn, _method("M0003", cands=(_cand("M0003-A", "M0003"),)),
                            HERE, require_commit=False)


# ---- the test window is unreachable, structurally ----------------------------------------------


def test_a_test_window_store_is_refused(conn, data, no_moments):
    m = _method()
    _run(conn, data, m)
    no_moments.undo()
    with pytest.raises(store.LabError, match="re-runs the dev window"):
        remeasure.remeasure(conn, m, HERE, smoke_test_data(), require_commit=False)
    assert all(store.moments_of(conn, n) is None for n in (55, 56))
    assert store.test_looks(conn) == 0


def test_no_window_can_be_selected_anywhere_in_the_command(conn, data, no_moments, monkeypatch):
    m = _method()
    _run(conn, data, m)
    no_moments.undo()
    for fn in (remeasure.measure, remeasure.remeasure, remeasure.preflight):
        assert "window" not in inspect.signature(fn).parameters
    calls: list[dict] = []
    real = dev.run_registry

    def spy(*a, **k):
        calls.append(dict(k))
        return real(*a, **k)

    monkeypatch.setattr(remeasure.dev, "run_registry", spy)
    remeasure.remeasure(conn, m, HERE, data, require_commit=False)
    assert calls and all("window" not in k for k in calls)
    assert data.window == research.DEV_WINDOW
    assert store.test_looks(conn) == 0


# ---- a divergent re-run aborts -----------------------------------------------------------------


def test_a_divergent_rerun_aborts_and_writes_nothing(conn, data, no_moments, monkeypatch):
    m = _method()
    _run(conn, data, m)
    no_moments.undo()
    real = remeasure.daily_moments

    def shifted(returns):
        out = real(returns)
        return None if out is None else (out[0] * 1.05, out[1], out[2])

    monkeypatch.setattr(remeasure, "daily_moments", shifted)
    with pytest.raises(store.LabError, match="does not reproduce"):
        remeasure.remeasure(conn, m, HERE, data, require_commit=False)
    assert all(store.moments_of(conn, n) is None for n in (55, 56))


def test_check_names_the_trial_and_the_delta(conn):
    base = dict(trial_n=55, candidate_id="M0001-A", n_at_run=56, t=400, sr_daily=0.05,
                skew=-0.1, kurt=4.0, var_trials=2.4e-4, recorded_sharpe=0.9,
                measured_sharpe=0.9, recorded_dsr=0.91, recomputed_dsr=0.91)
    remeasure.check("M0001", [remeasure.Reproduced(**base)])  # the good case raises nothing

    drifted_sharpe = remeasure.Reproduced(**{**base, "measured_sharpe": 0.8})
    with pytest.raises(store.LabError, match="annualized Sharpe"):
        remeasure.check("M0001", [drifted_sharpe])

    drifted_dsr = remeasure.Reproduced(**{**base, "recomputed_dsr": 0.95})
    with pytest.raises(store.LabError, match=r"DSR 0\.91 recorded"):
        remeasure.check("M0001", [drifted_dsr])


# ---- the CLI ------------------------------------------------------------------------------------


def test_the_cli_refuses_with_exit_2_and_loads_no_store(tmp_path, conn):
    import argparse

    from seer_engine.commands import lab as lab_cmd

    args = argparse.Namespace(
        db=tmp_path / "lab.sqlite", lab_command="remeasure", method="M9999",
        store=tmp_path / "nowhere",
    )
    assert lab_cmd.run(args) == 2
    assert not (tmp_path / "nowhere").exists()
```

**Impact:** `pytest engine/tests/test_lab_remeasure.py` is green and nothing else in the suite
changes. The two tests that touch `runner._dsr` and `store.insert_moments` undo their patches
before asserting.

---

## Verification

**Build:**

```
cd /home/miftah/.worktrees/seer/lab-luck-gate/engine && \
PYTHONPATH=/home/miftah/.worktrees/seer/lab-luck-gate/engine/src \
/home/miftah/seer/engine/.venv/bin/python -c "from seer_engine.lab import remeasure; from seer_engine.commands import lab; print(sorted(lab._HANDLERS))"
```

**Tests:**

```
cd /home/miftah/.worktrees/seer/lab-luck-gate/engine && \
PYTHONPATH=/home/miftah/.worktrees/seer/lab-luck-gate/engine/src \
/home/miftah/seer/engine/.venv/bin/python -m pytest tests/test_lab_remeasure.py tests/test_lab_runner.py tests/test_lab_store.py tests/test_lab_test_window.py -q
```

then the whole suite:

```
cd /home/miftah/.worktrees/seer/lab-luck-gate/engine && \
PYTHONPATH=/home/miftah/.worktrees/seer/lab-luck-gate/engine/src \
/home/miftah/seer/engine/.venv/bin/python -m pytest -q
```

(The worktree has no `engine/.venv`; the main checkout's venv plus `PYTHONPATH` shadowing the
editable install is the established way to run this repo's suite from a swarm worktree.)

**Manual check** — against the real committed database and the real dev store, after phase 2 has
landed and `engine/.research` is built:

```
cd /home/miftah/.worktrees/seer/lab-luck-gate && \
PYTHONPATH=engine/src /home/miftah/seer/engine/.venv/bin/python -m seer_engine lab remeasure M0022
```

Expect three `trial_moments` rows written (trials #108, #109, #110), each line reporting the
recorded Sharpe against the measured one and the recorded DSR (0.912210, 0.915623, 0.764668)
against the recomputed one at N=110 with `var_trials = 2.395048e-04`, every delta inside
`1e-6`. Run it again: it prints "every dev trial already has its moments; nothing to do", loads no
research store, and writes nothing. Then:

```
PYTHONPATH=engine/src /home/miftah/seer/engine/.venv/bin/python - <<'PY'
import sqlite3
c = sqlite3.connect("lab/lab.sqlite")
print("dev", c.execute("select count(*) from trials where window='dev'").fetchone()[0])
print("test looks", c.execute("select count(*) from trials where window='test'").fetchone()[0])
print("moments", c.execute("select count(*) from trial_moments").fetchone()[0])
print(c.execute("select status from methods where id='M0022'").fetchone()[0])
PY
```

Expect `dev 110`, `test looks 0`, `moments 3`, `rejected`. **Do not commit `lab/lab.sqlite` from
this phase** — invariant 6 and decision D5 give the committed database to phase 4 alone. Run the
manual check against a copy (`SEER_LAB_DB=/tmp/lab-check.sqlite` with the committed file copied
there) if phase 4 has not yet taken the file.

**Exit criteria:**

1. `lab remeasure M0022` writes exactly three `trial_moments` rows and prints, per trial, the
   recorded DSR beside the DSR recomputed from the fresh moments at the recorded
   `n_trials_at_run` and the reconstructed `var_trials`, every delta ≤ `1e-6`.
2. Running it a second time loads no research store, writes nothing, and names the three trials it
   skipped.
3. `lab remeasure` on a method with any `window='test'` trial exits 2 with a message naming the
   spent look, before any store is opened. `lab remeasure` on a method with no dev trial exits 2.
   `lab remeasure H-P7A-F1` exits 2 on the id's shape. **(True as of this phase, and deliberately
   temporary: phase 9 adds the seed path, after which `lab remeasure H-P7A-F1` re-measures that
   family instead of exiting 2. `resolve_method` goes on refusing `H-*` by shape — the dispatch
   happens before it — so this phase's unit test `test_a_seed_family_is_refused_by_name`, which
   calls `resolve_method` directly and matches on "not a lab method id", stays green through
   phase 9. Only this CLI-level sentence is superseded.)**
4. `store.test_looks(conn)` reads `0`; `store.dev_trial_count(conn)` reads `110`; every column of
   every `trials` row and the whole `methods` row for the remeasured method are byte-identical
   before and after.
5. `pytest` green in `engine/`.

---

## Handoffs

- **Backfilling the other 11 lab methods (R2, decision D4).** This phase ships the command; it does
  not run it 12 times. D4 chose on-demand recovery precisely so an unattended night never depends
  on hours of backtests, and phase 4's derived verdict falls back to the recorded columns for any
  trial with no moments. Whoever wants M0011's or M0020's moments runs `lab remeasure M0011`.
- **Phase 4 — reading the backfilled rows.** `store.verdict` consumes `trial_moments`; this phase
  neither reads nor defines it. Note for phase 4: a backfilled row's `n_at_run` is the trial's
  **recorded** `n_trials_at_run`, not today's count, so `n_at_run` is a historical fact and the
  policy's N must come from `npolicy`/`DSR_POLICY`, never from this column.
- **Phase 4 — the committed `lab/lab.sqlite`.** Decision D5 gives the binary to phase 4 alone.
  This phase commits source and tests only; the actual backfill of the committed database belongs
  with phase 4's migration commit or a later, deliberate run.
- **Phase 5 — surfacing un-remeasured trials.** `lab status` could usefully say "k dev trials have
  no recorded moments; `lab remeasure <method>` recovers them". That is status output, which phase
  5 owns; this phase adds nothing to `_status`.
- **Phase 7 — documentation.** `SKILL.md`, `engine/package_readme.md` and the design doc should
  mention `lab remeasure` beside `lab run`. Phase 7 owns every doc in this set; this phase edits
  only `commands/lab.py`'s own usage docstring.
- **Not done, deliberately:** no `--dry-run` for `remeasure` (nothing is spent, so there is nothing
  to preview), no `--all` sweep over every method (D4 says on demand), and no touch to
  `runner.trial_rows` to share the batch-reconstruction helper — `runner.py` is phase 2's and
  phase 4's, and a shared helper would make three phases collide on one file for no behavioural
  gain.

---

## Rollback

This phase is one commit over three paths and reverts cleanly on its own:

```
git revert <phase-3 commit>
```

It is purely additive. `lab/remeasure.py` and `tests/test_lab_remeasure.py` are new files that
nothing else imports; the four edits to `commands/lab.py` are insertions that remove without
touching a line any other phase wrote. Reverting leaves `lab remeasure` unavailable and every other
`lab` subcommand exactly as it is.

**If the command has already been run against a database**, the rows it wrote stay. That is correct
and needs no undo: `trial_moments` is append-only by phase 2's triggers, the rows are a true record
of a verified re-measurement, and phase 4's `store.verdict` reads them under the policy — reverting
this phase's *code* does not invalidate the *data* it produced. If a backfilled database must be
restored anyway, `git checkout origin/main -- lab/lab.sqlite` replaces the binary wholesale, as the
plan index's rollback section already prescribes.

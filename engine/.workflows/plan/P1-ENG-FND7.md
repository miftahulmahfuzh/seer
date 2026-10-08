> Adopted from `LAB_REALISTIC_GATE_PLAN.md` phase 2. Source: `.workflows/plan/lab-realistic-gate/phase-2.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 2: The lab's search is funded like the owner's account

**Plan set:** `LAB_REALISTIC_GATE_PLAN.md`
**Analysis:** `20261008-135044-N7K3_code_analyzer.md`
**Satisfies:** R2 — the lab's own search measures the owner's real funding (+5,000,000 IDR monthly
on a 10,000,000 IDR start), not a book that never grows
**Depends on:** Phase 1 — the set is strictly sequential, 1 -> 2 -> 3
**Difficulty:** HARD
**Package:** `engine.lab`, `engine.backtest`

> **Baseline note.** Every number in this plan was measured in a throwaway copy of `engine/` at
> base `2b493ee` with `DSR_POLICY = "all-trials"`, before phase 1 landed. Phase 1 moves the policy
> to `"methods"` and widens `remeasure.batches_of`'s guard; **quote both files as phase 1 leaves
> them, not as `main` has them today**, and re-locate every edit by function name rather than by
> the line numbers here. Nothing in this phase's change interacts with the policy — verified: the
> funding work is green under `"all-trials"` and the runner's own tests pass under both policies —
> but the measured *values* (N = 56, trial numbers 55/56) will differ after phase 1.

---

## Goal

`lab run` and `lab test` run every candidate on `OWNER_MONTHLY` — 10,000,000 IDR to start, then
+5,000,000 IDR on the 25th of every month — and record one `trial_funding` row per funded trial
inside the transaction that records the trial. The gate's money-weighted branch
(`store._blocking`, `store.owner_failures`) therefore judges a newly run method on `mwr` against a
dollar-cost-averaged SPY instead of on a total return that counts the owner's own deposits as
growth. The 128 recorded trials are not backfilled and not touched: `funding_of` keeps returning
None for all of them, which already means "this run was not fed".

**Measured on the smoke fixture, this is the lie the phase ends.** A funded `M0001-A` records
`total_return = 10.7821` (+1078%) against `spy_tr_return = 11.2162`; its honest money-weighted
return is `0.0764` against a DCA'd SPY's `0.1182`. Both the old and the new branch reject it, but
only the new one rejects it for a true reason. `M0001-B` records `total_return = 12.8471` and
`mwr = 0.2050` vs SPY's `0.1228` — the same direction, measured honestly.

**And the phase must not introduce a worse lie than the one it removes.** Funding the book makes
two *gate conditions* read wrong, because both are computed off raw equity and a deposit is not a
return. Steps 11–13 correct them. Measured on the same fixture, funded against unfunded:

| Gate input | Funded, uncorrected | Corrected | Unfunded (the honest reference) |
|---|---|---|---|
| annualized Sharpe -> `dsr` -> the **luck test** | **2.6524** | **0.2904** | 0.2620 |
| largest single session "return" | **+50.0000%** | **+3.0697%** | +3.0697% |
| `max_drawdown` -> the **20% bar** | **0.0796** | **0.1034** | 0.1055 |
| SPY TR `max_drawdown` (the benchmark) | **0.1059** | **0.2555** | 0.2575 |
| `worst_year` (recorded, not a condition) | **(2015, +74.3%)** | **(2014, +1.70%)** | (2014, +0.84%) |

A **10.1x** Sharpe inflation on a gate condition, from deposit sessions being recorded as returns.
Without steps 11–13 this phase would make the luck gate far too lenient at the same time phase 1
corrects it for being too strict — strictly worse than shipping neither.

---

## Interface Contract

The reconciler reads this section to detect cross-phase conflicts. Be exact and exhaustive.

**Creates:**
- `backtest.metrics.flow_map(cashflows) -> dict[date, float]`
  (`engine/src/seer_engine/backtest/metrics.py`) — `{session: total deposited that session}`, the
  single place deposits become a lookup. Several deposits can share a session, so they are summed.
  Read by `metrics.strategy_metrics` and by `book_runner._daily_returns` / `_year_returns`.
- `lab.runner.OWNER_SCHEDULE_TEXT` (`engine/src/seer_engine/lab/runner.py`) — the string written
  into `trial_funding.schedule`, derived from `OWNER_MONTHLY` so it cannot drift from the constant.
  Measured value: `'+5,000,000 IDR on the 25th of each month'`.
- `lab.runner._ordinal` (`runner.py`) — private, used only to build the above.
- `lab.runner.recorded_contributions(conn, trial_n) -> ContributionSchedule | None`
  (`runner.py`) — **the public answer to "what funding was this recorded trial run on"**:
  `OWNER_MONTHLY` when `store.funding_of` returns a row, else None. Every re-run path in the tree
  must route through this.
- `lab.runner.Ran.funding: store.FundingRow | None = None` — a new defaulted field on an existing
  frozen dataclass; positional construction `Ran(trial, row)` still works.

**Signature changes:**
- `lab.runner.trial_rows(conn, method, results, *, fingerprint, git_sha)` ->
  `(..., *, fingerprint, git_sha, deposits=(), schedule=OWNER_SCHEDULE_TEXT)`. Both new parameters
  are keyword-only with defaults, so the old call shape is unchanged. **`trial_rows` has no caller
  outside `run_method` anywhere in `src/` or `tests/`** (verified by grep: every other mention is
  prose in a docstring or a comment).
- `lab.real_costs.measure(method, candidate, trial, data)` ->
  `(..., *, contributions=None)`.
- `book_runner._daily_returns(equity)` -> `(equity, cashflows=())`
- `book_runner._year_returns(equity)` -> `(equity, cashflows=())`
- `book_runner._assemble(..., dividends)` -> `(..., dividends, cashflows=())`
- `book_runner._book_metrics(snaps, trades)` -> `(snaps, trades, cashflows=())`

All four are module-private (`_`-prefixed) with defaulted new parameters; **measured: no caller
anywhere in `src/` or `tests/` passes them positionally past the new parameter**, and the full
suite is unmoved.

**Behaviour changes (no symbol moves):**
- `lab.runner.run_method` passes `contributions=OWNER_MONTHLY` to `dev.run_registry` and calls
  `store.insert_funding` inside its existing `BEGIN IMMEDIATE`.
- `lab.runner.run_test` passes `contributions=OWNER_MONTHLY` and calls `store.insert_funding`
  inside its existing `BEGIN IMMEDIATE`, after `insert_trials`. **It spends no extra look and
  changes nothing about when a look is spent** — the insert is inside the transaction that already
  spends it, so the outcome is still "both or neither".
- `lab.remeasure.measure` resolves the re-run's funding from the plan's own trials and refuses a
  plan that mixes funded and unfunded trials.
- `commands.lab._costs` resolves the re-run's funding through `runner.recorded_contributions`.
- **`book_runner._daily_returns`, `_year_returns` and `metrics.strategy_metrics`'s max drawdown
  become cashflow-adjusted for a funded run and are byte-identical for an unfunded one.** This
  changes what a funded run's `sharpe`, `dsr`, `worst_year` and `max_drawdown` are — two of which
  are gate conditions. No recorded trial moves: all 128 are unfunded.

**Deletes:** none. **Renames:** none. **No schema change** — `trial_funding`, `FundingRow`,
`insert_funding` and `funding_of` are already built, tested and migrated (schema v4).

**Requires (from Phase 1):**
- `lab.store.DSR_POLICY == "methods"` and `npolicy.DEFAULT_POLICY` with it.
- **`remeasure.batches_of`'s widened guard** — phase 1 replaces the hardcoded all-trials identity
  `before + len(ns) == n_at_run` (`remeasure.py:251` on `main`) with
  `1 <= n_at_run <= max(before + len(ns), npolicy.DSR_MIN_N)`. Step 7's funding work on
  `remeasure.measure` sits on top of that and assumes it has landed; without it six further
  `test_lab_remeasure` tests fail with a production `LabError` that no test edit can repair.
  **Step 7 does not touch `batches_of`** — it edits `measure`, a different function further down
  the file — so the two changes do not overlap, but the line numbers in step 7 are pre-phase-1 and
  must be re-located by function name.
- The N assertions in `test_lab_runner.py` and `test_lab_remeasure.py` re-expressed
  policy-independently, and a green engine suite at the end of phase 1. This phase starts from a
  green tree and leaves one.

**Leaves alone (owned by others):**
- `engine/src/seer_engine/lab/store.py` — **phase 1 edits `DSR_POLICY` at `:165`; this phase does
  not open the file.** The funding API (`FundingRow` `:1695`, `insert_funding` `:1759`,
  `funding_of` `:1736`, `_blocking` `:1409`, `owner_failures` `:1053`) is called, never edited.
- `engine/src/seer_engine/lab/npolicy.py` — phase 1's.
- `engine/src/seer_engine/sim/contributions.py` — read-only; `OWNER_MONTHLY` is imported as is.
- `engine/src/seer_engine/backtest/dev.py` — **behaviour untouched; only the one false sentence in
  `run_registry`'s docstring at `:594` is corrected.**
- `engine/src/seer_engine/backtest/runner.py` and `benchmark.py` — the funding engine, already
  shipped. (`book_runner.py` and `metrics.py` are **no longer** on this list: steps 11–13 correct
  the two contaminated gate inputs in them. Both files are otherwise untouched, and no phase in
  this set names either.)
- `engine/src/seer_engine/lab/name_count.py` — already runs funded dev sweeps; it is the existing
  precedent this phase mirrors, not a file to change.
- `.claude/skills/` — phase 3's.
- `lab/lab.sqlite`, `web/data/lab.json` — **no recorded row is written by this phase at all.**
- The six test modules phase 1 owns: `test_lab_gate_policy.py`, `test_lab_snapshot.py`,
  `test_lab_prereg.py`, `test_lab_gate_wording.py`, `test_lab_luck.py`, `test_lab_npolicy.py`.

### Test modules shared with phase 1 — funding behaviour only

This phase edits `engine/tests/test_lab_runner.py` and `engine/tests/test_lab_remeasure.py`, but
**only for funding behaviour**, and quotes them as phase 1 leaves them.

An earlier reconciliation assigned both modules to phase 2 outright, including their `N`
assertions, to keep the two phases concurrent. **That assignment is withdrawn**: phase 1 found that
`remeasure.batches_of` breaks at the source under `"methods"` — not only in tests — so the set is
sequential and the concurrency the assignment bought no longer exists. The governing rule is now
*each phase repairs what it itself breaks*: **N breakage is phase 1's, funding breakage is mine.**

Phase 1 therefore owns, and this phase does not touch:

- `test_lab_runner.py:58` `{r["n_trials_at_run"] for r in rows} == {56}` and `:86`
  `mom["n_at_run"] == r["n_trials_at_run"] == 56`
- `test_lab_remeasure.py:99` `r.n_at_run == 56`, `:102` `row["n_at_run"] == 56`, `:274`
  `n_at_run=56` (a hand-built `Reproduced` fixture, no database, no gate)
- `test_lab_remeasure.py:169` `store.dev_trial_count(conn) == 56` — a raw `COUNT(*)`,
  policy-independent by construction; **measured: passes unchanged under both policies**, so phase
  1 may well leave it alone

A finding worth passing on, since this phase measured it while the assignment stood: re-expressing
`:58` and `:86` as `== store.gate(conn).n` makes `test_lab_runner.py` pass under **both** policies
(**measured: 15 passed at `"all-trials"`, 15 passed at `"methods"`**), because the pending
projection `trial_rows` deflates by and the post-hoc `store.gate(conn).n` resolve to the same
number under each. For `test_lab_remeasure.py` the honest source is the trial's own recorded
`n_trials_at_run` column, not today's gate — `remeasure.Reproduced.n_at_run` is documented at
`remeasure.py:488` as exactly that. Offered to phase 1 as evidence, not as work this phase does.

Every test this phase *adds* asserts no absolute N, so none of it can collide.

### What a caller must do to get a funded run (phase 3 will document this)

Nothing. **Funding is not opt-in and has no flag.** As of this phase:

    python -m seer_engine lab run MNNNN --store /home/miftah/seer/engine/.research/

runs every variant on `OWNER_MONTHLY` and writes one `trial_funding` row per variant. Phase 3's
twin needs no extra argument, no new keyword and no new CLI flag — it only needs to be a method the
lab has never run (so `preflight` lets it through) at `cost_model="gotrade"` (which
`real_cost_problem` enforces for M0031+ anyway). The one thing phase 3 may rely on and should say
out loud: **a twin minted and run after this phase lands is judged on `mwr` vs the DCA'd SPY's
`spy_tr_mwr`, and its parent — recorded before — is judged on `total_return` vs `spy_tr_return`.
The two numbers are not comparable, and the twin's page must say so.** The funded flag is the
existence of the `trial_funding` row; `store.funding_of(conn, n)` is how to read it and
`lab.runner.recorded_contributions(conn, n)` is how to re-run it the way it was recorded.

---

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/runner.py` | modify | imports (`:42`–`:57`); module docstring `:7` and the stale-policy lines `:9`, `:191`, `:198`; `Ran` + `OWNER_SCHEDULE_TEXT` + `recorded_contributions` (`:78`); `trial_rows` signature and body (`:181`, `:227`, `:284`); `run_method` (`:299`, `:310`, `:314`, `:347`); `run_test` (`:607`, `:612`, `:620`, `:622`, `:635`) |
| `engine/src/seer_engine/backtest/book_runner.py` | modify | **gate-critical** — `_daily_returns` (`:536`) and `_year_returns` (`:552`) become cashflow-adjusted; `_assemble` (`:586`), `_run_result_stats` (`:638`), `_book_metrics` (`:641`) and `_book_result_stats` (`:675`) thread the deposits; one import (`:48`) |
| `engine/src/seer_engine/backtest/metrics.py` | modify | **gate-critical** — new `flow_map` helper; `strategy_metrics`'s max-drawdown loop (`:261`–`:265`) becomes cashflow-adjusted for a funded run |
| `engine/tests/test_book_runner.py` | modify | four new tests: a deposit is not a return (daily and yearly), it does not damp the drawdown, and an unfunded run is byte-identical |
| `engine/src/seer_engine/lab/remeasure.py` | modify | one import (`:66`); `measure` resolves the recorded funding and refuses a mixed plan (`:375`) |
| `engine/src/seer_engine/lab/real_costs.py` | modify | `measure` gains `contributions=` and threads it (`:247`, `:267`) |
| `engine/src/seer_engine/commands/lab.py` | modify | `_costs` imports `runner` and resolves the recorded funding (`:1526`, `:1549`) |
| `engine/src/seer_engine/backtest/dev.py` | modify | **docstring only** — the now-false "what every caller in the tree passes" at `:594` |
| `engine/tests/test_lab_test_window.py` | modify | three `run_registry` doubles need `contributions=` and a `cashflows` attribute (`:14`, `:23`, `:26`, `:340`, `:365`, `:390`) |
| `engine/tests/test_lab_costs.py` | modify | the two direct `real_costs.measure` calls pass the recorded funding (`:94`, `:153`) |
| `engine/tests/test_lab_runner.py` | modify | new tests only: the funding row, the money-weighted gate branch, no backfill. **The N assertions are phase 1's** |
| `engine/tests/test_lab_remeasure.py` | modify | one new test only: a mixed plan is refused. **The N assertions are phase 1's** |

---

## Implementation Steps

### Step 1: `lab/runner.py` — imports

**File:** `engine/src/seer_engine/lab/runner.py:42`
**Change:** add `Sequence`, `date`, `external_cashflows`, `OWNER_MONTHLY` and
`ContributionSchedule`. `runner` already imports `backtest.dev`, which imports `backtest.metrics`
and `sim.contributions`, so none of these closes a new cycle.

**Code** — replace the import block (currently `:42`–`:57`):

```python
import sqlite3
import statistics
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any

from seer_engine import research
from seer_engine.backtest import dev
from seer_engine.backtest.dev import Candidate, DevRow
from seer_engine.backtest.metrics import external_cashflows
from seer_engine.commands.backtest_dev import daily_moments, month_end_curve, registry_problem
from seer_engine.fundamentals import coverage
from seer_engine.lab import store
from seer_engine.lab.method import METHOD_ID, Method, config_digest, config_text, source_sha
from seer_engine.lab.real_costs import real_cost_problem
from seer_engine.sim.contributions import OWNER_MONTHLY, ContributionSchedule
from seer_engine.strategies.allocator import MarketAware
```

(The three lines above `import sqlite3` — `from __future__ import annotations`, `import logging` —
are unchanged.)

**Impact:** none on behaviour. `external_cashflows` is the module's documented single reader of
`RunResult.cashflows` / `BookResult.cashflows`; using it rather than touching `.cashflows` directly
keeps that promise true (`backtest/metrics.py:324`).

---

### Step 2: `lab/runner.py` — the module docstring stops describing an unfunded search

**File:** `engine/src/seer_engine/lab/runner.py:7`
**Change:** step 2 of the `lab run` list must say the run is funded, because that is now the first
thing a reader needs to know about what the numbers mean.

**Code** — replace line 7:

```
2. Run the variants through ``dev.run_registry`` on the research store (every D9 guard), funded on
   ``sim.contributions.OWNER_MONTHLY`` -- 10,000,000 IDR to start and +5,000,000 IDR on the 25th of
   every month, the owner's real plan. The dollar-cost-averaged SPY TR curve receives the identical
   dollars on the identical sessions, so "beats SPY TR" stays a comparison of two books holding the
   same money, and one ``trial_funding`` row per variant records what the deposits earned. A trial
   that received no deposit (a window with no 25th in it) gets no row, and no row means "this run
   was not fed" -- which is true of all 128 trials recorded before this.
```

**Also in this step — the three lines that go stale when phase 1 lands.** Phase 1 flagged these and
the file is this phase's, so they are corrected here. All three say the policy "ships as
all-trials", which stops being true.

`:9` — inside the same module docstring, item 3:

```
3. Deflated Sharpe per trial with N resolved by ``store.DSR_POLICY`` through
   ``store.pending_gate`` -- whatever that policy resolves to, projected over this batch -- and
   the variance of the daily Sharpe across those trials. *What* N counts is the policy's business
   and need not be a row count; this module never reads the policy's value, only the N it yields.
```

`:191`–`:198` — inside `trial_rows`'s docstring, replace the sentence beginning "Under the shipped
``all-trials`` policy":

```
    The luck test's N is ``store.pending_gate(conn, method.id, len(results)).n`` -- the N the
    lab's ``store.DSR_POLICY`` resolves to, projected over this batch, which is the same N
    ``store.verdict`` re-reads these trials under. A trial run tonight and one recorded six weeks
    ago are therefore judged by one bar, which is R2. Under an ``all-trials`` policy that N is
    ``dev_trial_count(conn) + len(results)``, the expression this function used before the policy
    existed; under ``methods`` it is a count of distinct ideas. This function does not care which
    -- it asks ``pending_gate`` and records the answer in ``n_trials_at_run``.
```

**Impact:** prose only. The implementer should re-read `:5`–`:12` and `:188`–`:200` as phase 1
leaves them before editing — phase 1 may already have touched neighbouring wording.

---

### Step 3: `lab/runner.py` — `Ran.funding`, the schedule text, and `recorded_contributions`

**File:** `engine/src/seer_engine/lab/runner.py:78`
**Change:** mirror the existing `MomentsRow` pattern exactly — a `trial_n=0` row carried on `Ran`
and stamped after `insert_trials`. Add the schedule's human words and the one public reader of the
funded flag.

**Code** — replace the `Ran` dataclass's field block and the lines up to `def git_head`:

```python
@dataclass(frozen=True)
class Ran:
    """One finished variant: its database row, its dev row, and the DSR's inputs.

    ``moments`` carries ``trial_n=0`` until ``insert_trials`` assigns the real trial number;
    ``run_method`` stamps it and records it. It is None exactly when ``daily_moments`` returned
    None for this variant, which is exactly when ``trial.dsr`` is None -- a trial that never had
    a deflated Sharpe has no inputs to keep. It defaults to None so a caller that only cares
    about the trial can still build a ``Ran`` positionally.

    ``funding`` is the same pattern for the same reason: ``trial_n=0`` until the insert, stamped
    with ``dataclasses.replace`` afterwards, and None exactly when the variant received no
    deposit. **The existence of the row is the funded flag** (``store.FundingRow``), so None here
    must produce no row at all rather than a row of zeroes -- ``trial_funding`` CHECKs
    ``deposits_usd > 0`` and ``deposits_n >= 1`` and would refuse one.
    """

    trial: store.TrialRow
    row: DevRow
    moments: store.MomentsRow | None = None
    funding: store.FundingRow | None = None


def _ordinal(n: int) -> str:
    suffix = "th" if 11 <= n % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


#: The owner's funding in his own words, for ``trial_funding.schedule``. Built from
#: ``OWNER_MONTHLY`` rather than typed out, so a reader of a recorded row can never be told a
#: schedule the run was not actually fed. Measured: "+5,000,000 IDR on the 25th of each month".
OWNER_SCHEDULE_TEXT = (
    f"+{OWNER_MONTHLY.amount_idr:,.0f} IDR on the {_ordinal(OWNER_MONTHLY.day_of_month)} of each month"
)


def recorded_contributions(conn: sqlite3.Connection, trial_n: int) -> ContributionSchedule | None:
    """The schedule trial ``trial_n`` was run on: ``OWNER_MONTHLY`` when funded, else None.

    **Every path that re-runs a recorded trial must go through this**, because a re-run on the
    wrong funding is not the same measurement: ``lab remeasure`` compares the re-run's annualized
    Sharpe to the recorded one at 1e-9 relative, and ``lab costs`` compares total returns. The
    funded flag is the existence of a ``trial_funding`` row (``store.funding_of``), not a column,
    so None is the normal and meaningful answer for all 128 trials recorded before this phase.
    """
    return None if store.funding_of(conn, int(trial_n)) is None else OWNER_MONTHLY
```

**Impact:** `Ran` gains a defaulted field — existing positional construction is unaffected.
`OWNER_SCHEDULE_TEXT` is evaluated at import; `OWNER_MONTHLY.amount_idr` is a `Decimal`, and
`f"{Decimal('5000000'):,.0f}"` is `"5,000,000"`.

---

### Step 4: `lab/runner.py` — `trial_rows` builds the funding row

**File:** `engine/src/seer_engine/lab/runner.py:181` (signature), `:227` (the loop head), `:284`
(the append)
**Change:** two keyword-only parameters with defaults, a `flows` list aligned 1:1 with `results`,
and a `FundingRow` built from the row's own metrics. `met.mwr` is `backtest.metrics.Metrics.mwr`,
filled in for a funded book run by `dev._funded_stats`; `row.spy_tr.mwr` is the same measure on
the dollar-cost-averaged SPY TR curve, filled in by `metrics.curve_metrics` from the curve's own
cashflows.

**Code** — the signature becomes:

```python
def trial_rows(
    conn: sqlite3.Connection,
    method: Method,
    results: list[tuple[DevRow, Any]],
    *,
    fingerprint: str,
    git_sha: str,
    deposits: Sequence[Sequence[tuple[date, float]]] = (),
    schedule: str = OWNER_SCHEDULE_TEXT,
) -> list[Ran]:
```

Append these two paragraphs to the end of the existing docstring (keep every word already there):

```
    ``deposits`` is one ``metrics.external_cashflows(result)`` per entry of ``results``, in the
    same order -- the deposits that run actually received, dated by the NYSE session they landed
    on. A non-empty entry produces that trial's ``store.FundingRow``, carrying ``trial_n=0`` until
    ``run_method`` stamps it, exactly as ``moments`` does. An empty entry produces None and
    therefore no row, which is what "this run was not fed" is spelled as. ``deposits`` defaults to
    ``()`` and is then read as "no deposit anywhere", so a caller that does not fund its runs gets
    byte-for-byte what this function produced before the parameter existed.

    ``schedule`` is the text written into ``trial_funding.schedule`` -- the owner's own words, so a
    reader of the row never reconstructs the plan from the dates. It travels with ``deposits``
    because the two describe one run: funding a batch on some other schedule and leaving this at
    its default would record a sentence the run never obeyed.
```

The body changes in exactly three places. After `run_at = store.now_iso()` (`:227`), insert:

```python
    flows: list[Sequence[tuple[date, float]]] = list(deposits) if deposits else [()] * len(results)
    if len(flows) != len(results):
        raise ValueError(f"deposits has {len(flows)} entries for {len(results)} results")
```

The loop head (`:229`) becomes:

```python
    for (row, curve), m, cash in zip(results, moments, flows, strict=True):
```

and the append (`:284`) becomes:

```python
        fund = None if not cash else store.FundingRow(
            trial_n=0,  # insert_trials assigns it; run_method stamps this row with it
            mwr=_f(met.mwr),
            spy_tr_mwr=_f(row.spy_tr.mwr),
            deposits_usd=float(sum(amount for _, amount in cash)),
            deposits_n=len(cash),
            schedule=schedule,
            measured=run_at,
        )
        out.append(Ran(trial=trial, row=row, moments=mom, funding=fund))
    return out
```

For reference, the whole body after the change, so nothing between those three edits is in doubt:

```python
    prior = store.dev_daily_sharpes(conn)
    moments = [daily_moments(r.stats.daily_returns) for r, _ in results]
    new_sharpes = [m[0] for m in moments if m is not None]
    all_sharpes = prior + new_sharpes
    gate = store.pending_gate(conn, method.id, len(results))
    n_trials = gate.n
    var_trials = statistics.variance(all_sharpes) if len(all_sharpes) >= 2 else None
    run_at = store.now_iso()
    flows: list[Sequence[tuple[date, float]]] = list(deposits) if deposits else [()] * len(results)
    if len(flows) != len(results):
        raise ValueError(f"deposits has {len(flows)} entries for {len(results)} results")
    out: list[Ran] = []
    for (row, curve), m, cash in zip(results, moments, flows, strict=True):
        c = row.candidate
        met = row.stats.metrics
        t = len(row.stats.daily_returns)
        if m is None or var_trials is None:
            dsr = None
            mom = None
        else:
            dsr = dev.deflated_sharpe(m[0], n_trials, var_trials, t, m[1], m[2])
            mom = store.MomentsRow(
                trial_n=0,  # insert_trials assigns it; run_method stamps this row with it
                sr_daily=float(m[0]),
                t=t,
                skew=float(m[1]),
                kurt=float(m[2]),
                var_trials=float(var_trials),
                n_at_run=n_trials,
                measured=run_at,
            )
        failed = list(row.failed)
        if dsr is None or dsr < store.DSR_MIN:
            failed.append(store.DSR_LABEL)
        worst = row.stats.worst_year
        trial = store.TrialRow(
            method_id=method.id,
            candidate_id=c.id,
            config_digest=config_digest(c),
            config_text=config_text(c),
            rules_id=c.rules.id,
            allocator_id=str(c.allocator.id),
            window="dev",
            start=row.start.isoformat(),
            end=row.end.isoformat(),
            store_fingerprint=fingerprint,
            git_sha=git_sha,
            run_at=run_at,
            total_return=_f(met.total_return),
            cagr=_f(met.cagr),
            max_drawdown=_f(met.max_drawdown),
            profit_factor=_f(met.profit_factor),
            trades=int(met.trades),
            sharpe=_f(row.stats.sharpe),
            exposure=_f(row.stats.exposure),
            turnover=_f(row.stats.turnover),
            worst_year=None if worst is None else int(worst[0]),
            worst_year_return=None if worst is None else float(worst[1]),
            spy_tr_return=_f(row.spy_tr.total_return),
            spy_tr_cagr=_f(row.spy_tr.cagr),
            mar=row.mar,
            failed="; ".join(failed),
            eligible=not failed,
            dsr=dsr,
            n_trials_at_run=n_trials,
            curve_json=store.curve_json(curve),
        )
        fund = None if not cash else store.FundingRow(
            trial_n=0,  # insert_trials assigns it; run_method stamps this row with it
            mwr=_f(met.mwr),
            spy_tr_mwr=_f(row.spy_tr.mwr),
            deposits_usd=float(sum(amount for _, amount in cash)),
            deposits_n=len(cash),
            schedule=schedule,
            measured=run_at,
        )
        out.append(Ran(trial=trial, row=row, moments=mom, funding=fund))
    return out
```

**Impact:** `TrialRow` is built from exactly the same expressions as before — `dsr`, `failed`,
`eligible` and `n_trials_at_run` are untouched. What moves is the *inputs*, because the run is now
funded; nothing about how a row is derived from a run changes here.

---

### Step 5: `lab/runner.py` — `run_method` funds the search and records the funding atomically

**File:** `engine/src/seer_engine/lab/runner.py:299`, `:310`, `:314`, `:347`
**Change:** capture the deposits in `on_result`, fund `run_registry`, report the honest numbers in
the progress log, pass the deposits to `trial_rows`, and insert the funding rows inside the
existing `BEGIN IMMEDIATE` right after `insert_moments` — so trials, moments and funding are one
atomic unit.

**Code** — the complete function after the change:

```python
def run_method(
    conn: sqlite3.Connection,
    method: Method,
    path: Path,
    data: research.ResearchData,
    *,
    git_sha: str,
    require_commit: bool = True,
) -> list[Ran]:
    """Run ``method`` on the dev window and record it (see the module docstring)."""
    preflight(conn, method, path, require_commit=require_commit)
    results: list[tuple[DevRow, Any]] = []
    deposits: list[Sequence[tuple[date, float]]] = []

    def on_result(i: int, result: Any, row: DevRow) -> None:
        results.append((row, month_end_curve(result.snapshots)))
        cash = external_cashflows(result)
        deposits.append(cash)
        m = row.stats.metrics
        log.info(
            "[%d/%d] %s %s..%s: money-weighted %s vs DCA SPY TR %s (%d deposits, %.2f USD), "
            "max DD %s, PF %s, trades %d",
            i + 1, len(method.candidates), row.candidate.id, row.start, row.end,
            m.mwr, row.spy_tr.mwr, len(cash), float(sum(a for _, a in cash)),
            m.max_drawdown, m.profit_factor, m.trades,
        )

    dev.run_registry(
        data.market, data.dividends, data.spy_dividends, method.candidates,
        on_result=on_result, contributions=OWNER_MONTHLY,
    )
    store.begin_immediate(conn)  # lab-wide N and the inserts, atomic against parallel sessions
    with conn:
        preflight(conn, method, path, require_commit=False)  # a parallel session may have won a race
        ran = trial_rows(
            conn, method, results, fingerprint=data.fingerprint, git_sha=git_sha, deposits=deposits
        )
        status = "dev-eligible" if any(r.trial.eligible for r in ran) else "rejected"
        if store.get_method(conn, method.id) is None:
            store.add_method(
                conn,
                id=method.id,
                name=method.name,
                family=method.family,
                source_kind=method.source_kind,
                source_ref=method.source_ref,
                hypothesis=_hypothesis(method),
                parent_id=method.parent_id,
                status="registered",
            )
        else:
            row = store.get_method(conn, method.id)
            if row["status"] == "idea":
                store.update_method(
                    conn, method.id, hypothesis=_hypothesis(method), name=method.name,
                    family=method.family, source_kind=method.source_kind,
                    source_ref=method.source_ref, parent_id=method.parent_id,
                )
                store.update_method(conn, method.id, status="registered")
        ns = store.insert_trials(conn, [r.trial for r in ran])
        # The DSR's inputs, stamped with the trial numbers SQLite just assigned, in this same
        # transaction: a trial and the measurement that judged it are recorded together or not
        # at all. A variant with no computable moments contributes no row, exactly as it
        # contributes no dsr.
        store.insert_moments(conn, [
            replace(r.moments, trial_n=n)
            for n, r in zip(ns, ran, strict=True)
            if r.moments is not None
        ])
        # The deposits and what they earned, stamped the same way and in the same transaction, for
        # the same reason: the money-weighted verdict and the trial it judges are one record. A
        # variant that received no deposit contributes no row, and no row is how the lab says
        # "this run was not fed" -- the answer `funding_of` gives for all 128 trials recorded
        # before this, which this phase does not backfill (GOTRADE_FEE_REBUILD_PLAN.md D18).
        store.insert_funding(conn, [
            replace(r.funding, trial_n=n)
            for n, r in zip(ns, ran, strict=True)
            if r.funding is not None
        ])
        store.update_method(conn, method.id, source_sha=source_sha(path), status=status)
        for key in method.seen_keys:
            store.mark_seen(conn, key, method.id)
    return ran
```

**Impact:** `lab run` now records the owner's funding. The progress log reports the money-weighted
return instead of a total return that counts deposits as growth — measured on the smoke fixture,
the old line would have printed `return 10.78` for a book whose money earned 7.6%.
`store.insert_funding([])` is a no-op loop, so an unfunded batch (no 25th inside any candidate's
window) writes nothing and raises nothing.

---

### Step 6: `lab/runner.py` — `run_test` funds the one look and records it

**File:** `engine/src/seer_engine/lab/runner.py:607`, `:612`, `:620`, `:622`, `:635`
**Change:** the same three moves on the test-window path. **The look is spent in exactly the same
place as before**: `insert_trials` is still the first write inside the same `BEGIN IMMEDIATE`, and
the funding insert that follows is inside that transaction, so the outcome stays "the look and its
record, or neither". Nothing is checked, refused or decided differently, and no new way to spend a
look is introduced.

Funding the look is not optional once `lab run` is funded: `make_row` already decides
`beats_spy_tr` money-weighted when both sides carry an `mwr` (`dev.py:419`), so a funded run whose
funding went unrecorded would record `eligible` on `mwr` while `store.verdict` re-derived it on
`total_return`. That is the exact drift `owner_failures` exists to prevent.

> ### ⛔ MUST NOT be "cleaned up": the funding insert stays inside the transaction
>
> `store.insert_funding` is called **inside** the `with conn:` block that `store.begin_immediate`
> opened, after `store.insert_trials`. That placement is load-bearing and is not stylistic.
>
> Because the insert is inside the transaction, a raise from it — a `LabError`, a CHECK violation,
> a disk error — rolls the whole transaction back and **the look is not spent**: no `trials` row
> with `window='test'`, no status move, nothing. `store.test_looks` still reads what it read
> before, and the method can be tested again once the cause is fixed.
>
> Moving the insert after the `with conn:` block, or into a second transaction, or wrapping it in
> a `try`/`except` that swallows, inverts that: the look is spent and the record of what it
> measured is lost. **A spent look is unrecoverable.** `UNIQUE(config_digest, window)` plus
> `trials_no_update` and `trials_no_delete` mean the configuration never gets a second one — the
> database will refuse the retry, by design, forever.
>
> The same applies to `run_method`'s `insert_funding` for the same structural reason (a trial and
> the measurement that judged it are recorded together or not at all), but the test window is
> where the cost of getting it wrong is permanent. **Do not move either call out of its
> transaction, and do not "simplify" the `if cash:` guard into an unconditional insert** — an
> unconditional one would hit the `deposits_usd > 0` CHECK on an unfunded window and fail a look
> that had nothing wrong with it.

**Code** — the complete function after the change:

```python
def run_test(
    conn: sqlite3.Connection,
    method: Method,
    path: Path,
    candidate: Candidate,
    data: research.ResearchData,
    *,
    git_sha: str,
    require_commit: bool = True,
) -> Tested:
    """Spend the one counted look at the test window and record it (design §3).

    ``data`` must be a **test**-window store. The window it was built for travels on it
    (``ResearchData.window``, phase 2), the candidate runs between that window's bounds, and a dev
    store is refused here as well as by ``load_store``: a mis-pointed ``SEER_RESEARCH_STORE`` must
    never produce a ``window='test'`` trial measured on dev data, because the row can never be
    corrected.

    The candidate goes through ``dev.run_registry`` -- the same path, the same ``prepare_for``
    dispatch and the same D8 row ``lab run`` uses, on the same ``OWNER_MONTHLY`` funding, with the
    window as the only difference -- then one ``trials`` row is appended, its ``trial_funding`` row
    beside it, and the method moves to ``test-passed`` or ``test-failed``, both final, in one
    transaction. Every refusal is made before the store is loaded except the two the store itself
    makes possible, and all of them spend nothing.

    **The funding changes nothing about when or whether the look is spent.** ``insert_trials`` is
    still the first write inside the one ``BEGIN IMMEDIATE``, every refusal is the same refusal in
    the same order, and the funding row is written inside that transaction -- so the look and its
    record land together or not at all, exactly as the trial and the status move already did.
    """
    window = data.window
    if window.name != "test":
        raise store.LabError(
            f"{candidate.id}: this research store was built for the {window.name!r} window "
            f"({window.start}..{window.end}); `lab test` runs on the test window and nothing else. "
            f"Build it with `python -m seer_engine research_store --test-window`"
        )
    aware = market_aware_candidates(method)
    if candidate.id in aware and len(data.market.fundamentals) == 0:
        raise store.LabError(
            f"{candidate.id} ranks on Market.fundamentals and this test store carries no panel; "
            f"the look would measure the missing panel, not the hypothesis. Build the test store "
            f"with `research_store --test-window --with-fundamentals` and run it again -- nothing "
            f"has been spent"
        )
    pre = preflight_test(conn, method, path, candidate, require_commit=require_commit)

    captured: list[tuple[DevRow, Any, Sequence[tuple[date, float]]]] = []

    def on_result(i: int, result: Any, row: DevRow) -> None:
        captured.append((row, month_end_curve(result.snapshots), external_cashflows(result)))

    dev.run_registry(
        data.market,
        data.dividends,
        data.spy_dividends,
        (candidate,),
        on_result=on_result,
        window=window,
        contributions=OWNER_MONTHLY,
    )
    (row, curve, cash), = captured
    m = row.stats.metrics
    log.info(
        "%s on the test window %s..%s: money-weighted %s vs DCA SPY TR %s (%d deposits, %.2f USD), "
        "max DD %s, PF %s, trades %d",
        candidate.id, row.start, row.end, m.mwr, row.spy_tr.mwr,
        len(cash), float(sum(a for _, a in cash)),
        m.max_drawdown, m.profit_factor, m.trades,
    )
    store.begin_immediate(conn)  # the look and the status move, atomic against parallel sessions
    with conn:
        # A parallel session may have won the race to this configuration's one look. `pre` is
        # the pre-registration git already vouched for above, so this re-check costs no
        # subprocess and still re-runs check_digest and both database refusals.
        preflight_test(conn, method, path, candidate, pre=pre, require_commit=False)
        trial = test_trial_row(conn, method, row, curve, fingerprint=data.fingerprint, git_sha=git_sha)
        status = "test-passed" if row.eligible else "test-failed"
        (n,) = store.insert_trials(conn, [trial])
        if cash:
            store.insert_funding(conn, [store.FundingRow(
                trial_n=n,
                mwr=_f(m.mwr),
                spy_tr_mwr=_f(row.spy_tr.mwr),
                deposits_usd=float(sum(a for _, a in cash)),
                deposits_n=len(cash),
                schedule=OWNER_SCHEDULE_TEXT,
                measured=trial.run_at,
            )])
        store.update_method(conn, method.id, status=status)
    return Tested(trial=trial, row=row, status=status)
```

**Impact:** `store.test_looks(conn)` counts `trials WHERE window='test'` and is unchanged by this
step: one look still writes one trial row. The committed database stays at 2 looks because **this
phase runs no `lab test`**.

---

### Step 7: `lab/remeasure.py` — the backfill re-runs the funding the trials were recorded on

**File:** `engine/src/seer_engine/lab/remeasure.py:66` (import), `:375` (the re-run)
**Change:** `lab remeasure` re-runs recorded trials and refuses to write unless the re-run
reproduces the recorded annualized Sharpe to 1e-9 relative. An unfunded re-run of a funded trial
cannot. **Measured before the fix: 5 tests in `test_lab_remeasure.py` fail with deltas of 2.4 and
2.2 on the Sharpe** (`2.65 recorded, 0.26 measured`). The recorded funding is the plan's own
trials', read through `store.funding_of`.

A plan may not mix funded and unfunded trials: one `run_registry` call runs every candidate on one
schedule, so a mixed plan has no correct answer and gets a refusal instead of a silent half-wrong
re-run. In practice it cannot arise — `run_method` records moments for every trial that has a DSR,
so a funded trial never *needs* remeasuring — but the refusal is what makes that a fact rather
than a hope.

**Code** — add the import beside the existing one at `:66`:

```python
from seer_engine.lab import store
from seer_engine.sim.contributions import OWNER_MONTHLY
```

Append this paragraph to `measure`'s docstring (after the existing dev-window paragraph):

```
    The **funding** is not a parameter either: it is read off the trials being reproduced. A trial
    with a ``trial_funding`` row was run on ``sim.contributions.OWNER_MONTHLY`` and is re-run on
    it; a trial without one was run on a lump sum and is re-run on a lump sum. Getting this wrong
    is not a small error -- measured, an unfunded re-run of a funded trial reports an annualized
    Sharpe of 0.26 against a recorded 2.65 and this module correctly refuses to write anything. A
    plan that mixes the two is refused outright, because one ``run_registry`` call runs every
    candidate on one schedule and there is no answer that reproduces both.
```

Then replace the four lines from `rows: dict[str, DevRow] = {}` through the `dev.run_registry(...)`
call (`:375`–`:382`) with:

```python
    ns = tuple(sorted(plan.missing + plan.present))
    funded = tuple(n for n in ns if store.funding_of(conn, n) is not None)
    if funded and len(funded) != len(ns):
        raise store.LabError(
            f"{method.id}: trials {funded} received deposits and "
            f"{tuple(n for n in ns if n not in funded)} did not, so one re-run cannot reproduce "
            f"both. Nothing is backfilled"
        )
    contributions = OWNER_MONTHLY if funded else None
    rows: dict[str, DevRow] = {}

    def on_result(i: int, result: Any, row: DevRow) -> None:
        rows[config_digest(row.candidate)] = row

    dev.run_registry(
        data.market, data.dividends, data.spy_dividends, plan.candidates,
        on_result=on_result, contributions=contributions,
    )
```

**Impact:** for all 128 recorded trials `funded == ()` and `contributions is None`, so `lab
remeasure` on the committed database is byte-for-byte what it is today. `measure`'s signature does
not change, and `conn` — which its docstring says is taken so "a future check can reach the
database without a call-site change" — is finally used for exactly that.

`remeasure_seed` / `run_chunk` are **deliberately not changed**: the 54 P7a seed rows are frozen
records that can never acquire a funding row, so their re-run is correctly unfunded. See Handoffs.

---

### Step 8: `lab/real_costs.py` — `lab costs` re-runs the funding the trial was recorded on

**File:** `engine/src/seer_engine/lab/real_costs.py:247`, `:267`
**Change:** `Comparison.reproduced` compares the re-run's total return to the recorded one and
False means "the store or the engine changed". **Measured before the fix: `reproduced` is False for
every funded trial**, a false alarm on every method run after this phase. Give `measure` the
funding as a keyword and let the caller resolve it from the trial.

A keyword rather than a `conn` parameter, because `measure` is deliberately conn-free (it writes
nothing anywhere) and `pick_candidate`, which already has the connection, is always called first.

**Code** — the complete function after the change:

```python
def measure(
    method: Method,
    candidate: Candidate,
    trial: Mapping[str, Any],
    data: research.ResearchData,
    *,
    contributions: Any = None,
) -> Comparison:
    """Run ``candidate`` at both cost models on the dev window. Writes nothing anywhere.

    ``contributions`` is the funding the **recorded** trial ran on -- resolve it with
    ``lab.runner.recorded_contributions(conn, trial["n"])`` and pass it through, so the re-run is
    the same measurement and ``Comparison.reproduced`` means what it says. Measured: re-running a
    funded trial unfunded lands on a different total return, and the report then announces that
    the store or the engine changed when neither did. None -- the default -- is right for every
    trial recorded before the lab was funded, which is all 128 of them.

    Both sides are fed the same schedule, so the flat/Gotrade comparison is still a comparison of
    one variant at two fee models and nothing else.
    """
    if data.window != research.DEV_WINDOW:
        w = data.window
        raise store.LabError(
            f"{method.id}: this research store was built for the {w.name!r} window "
            f"({w.start}..{w.end}); `lab costs` re-runs the dev window and nothing else. "
            f"Build it with `python -m seer_engine research_store`"
        )
    flat, real = twins(candidate)
    rows: dict[str, DevRow] = {}

    def on_result(i: int, result: Any, row: DevRow) -> None:
        rows[row.candidate.id] = row

    dev.run_registry(
        data.market, data.dividends, data.spy_dividends, (flat, real),
        on_result=on_result, contributions=contributions,
    )
    f, g = rows[flat.id], rows[real.id]
    return Comparison(
        method_id=method.id,
        method_name=method.name,
        candidate_id=candidate.id,
        recorded_model=getattr(candidate.rules, "cost_model", FLAT),
        trial_n=int(trial["n"]),
        recorded_total_return=None if trial["total_return"] is None else float(trial["total_return"]),
        start=f.start,
        end=f.end,
        fingerprint=str(data.fingerprint),
        flat=side_of(FLAT, f),
        real=side_of(REAL, g),
    )
```

**Impact:** `contributions` is typed `Any` to match the module's existing style for engine values
it only passes through (it does not import `sim.contributions`). Default None keeps `lab costs` on
the 128 recorded trials exactly as it is.

---

### Step 9: `commands/lab.py` — `_costs` resolves the recorded funding

**File:** `engine/src/seer_engine/commands/lab.py:1526`, `:1549`
**Change:** two lines. `runner` is imported locally in this module's handlers (there is no
module-level `runner` import — a measured `NameError` confirmed it), so it joins the existing local
`real_costs` import.

**Code** — line `:1526` becomes:

```python
    from seer_engine.lab import real_costs, runner
```

and line `:1549` becomes:

```python
    cmp = real_costs.measure(
        method, candidate, trial, data,
        contributions=runner.recorded_contributions(conn, int(trial["n"])),
    )
```

**Impact:** `lab costs` on a recorded, unfunded trial resolves to None and behaves exactly as
today; on a funded one it reproduces. Nothing else in `_costs` changes — it still writes only the
one journal entry and still prints N and the looks before and after.

---

### Step 10: `backtest/dev.py` — the docstring claim that is now false

**File:** `engine/src/seer_engine/backtest/dev.py:593`–`:597`
**Change:** `run_registry`'s docstring says None is "what every caller in the tree passes". After
step 5 and step 6 that is false for `lab.runner`, and `lab.name_count` already passed a schedule
before this phase. Correct the sentence; **change nothing else in this file.**

**Code** — replace the paragraph at `:593`–`:597`:

```
    ``contributions`` is the funding schedule every candidate is run on
    (``sim.contributions.ContributionSchedule``), or None -- the default, and a lump-sum book that
    never grows. ``lab.runner.run_method`` and ``run_test`` pass ``OWNER_MONTHLY``, and
    ``lab.name_count`` passes it unless ``--lump``; ``lab.remeasure`` and ``lab.real_costs`` pass
    whatever the trial they are reproducing was recorded on
    (``lab.runner.recorded_contributions``), so a recorded trial re-runs as the measurement it was.
    Every one of the 128 trials recorded before the lab was funded has no ``trial_funding`` row and
    re-runs unfunded, byte-for-byte as it did. When a schedule is given, the book is fed the
    deposits AND ``spy_curves`` receives the same dollars on the same sessions, so "beats SPY TR"
    stays a comparison of two books holding the same money.
```

**Impact:** prose only. The parameter, its default and its behaviour are untouched — this phase
does not change `dev.py`'s behaviour in any way.

---

### Step 11: `backtest/metrics.py` — `flow_map`, and a drawdown deposits cannot damp

**File:** `engine/src/seer_engine/backtest/metrics.py` — new helper above `run_metrics` (`:334`);
`strategy_metrics`'s drawdown loop (`:261`–`:265`)
**Change:** `max_drawdown` is computed over raw equity, so a deposit raises the peak and refills
the trough and a funded run reads **safer than the strategy was** — against `tuning.MAX_DRAWDOWN`,
which `dev.make_row` applies and which `lab.store.owner_failures` and `_blocking` re-derive from
the recorded column. **It is a gate condition.** Measured on the smoke fixture: 0.0796 recorded
against 0.1055 honest, and the DCA'd SPY benchmark damped from 0.2575 to 0.1059.

The fix measures the drawdown on the **time-weighted wealth index** — the curve the strategy would
have traced on one unchanging dollar — built from the same cashflow-adjusted session growth step 12
uses. `cashflows` is already a parameter of `strategy_metrics` (it feeds `mwr`), so nothing new is
threaded in here.

**Code** — the new helper, immediately above `def run_metrics`:

```python
def flow_map(cashflows: Sequence[tuple[date, float]]) -> dict[date, float]:
    """``{session: total deposited that session}`` -- the one place deposits become a lookup.

    Several deposits can share a session (a schedule the calendar lagged onto one open), so they
    are summed rather than overwritten. Used by the cashflow-adjusted return and drawdown
    computations in this module and in ``book_runner``.
    """
    out: dict[date, float] = {}
    for when, amount in cashflows:
        out[when] = out.get(when, 0.0) + float(amount)
    return out
```

and the drawdown block inside `strategy_metrics` becomes:

```python
    peak = -math.inf
    max_dd = 0.0
    if cashflows:
        # A deposit raises the peak and refills the trough, so a funded run's drawdown measured on
        # raw equity reads SAFER than the strategy was -- and `max_drawdown` is a gate condition
        # (`tuning.MAX_DRAWDOWN`, re-derived by `lab.store.owner_failures` and `_blocking`).
        # Measured on the smoke fixture: 7.96% on raw equity against 10.55% honest, and the DCA'd
        # SPY benchmark damped from 25.75% to 10.59%. So the drawdown of a funded run is taken on
        # the time-weighted wealth index -- the curve the strategy would have traced on one
        # unchanging dollar -- built from the same cashflow-adjusted session growth
        # `book_runner._daily_returns` uses. With no cashflows the branch below is skipped and the
        # original loop runs unchanged, so every unfunded run is byte-identical.
        flows = flow_map(cashflows)
        index = 1.0
        peak = index
        for (_, prev), (d, cur) in zip(snaps, snaps[1:]):
            index *= cur / (prev + flows.get(d, 0.0))
            peak = max(peak, index)
            max_dd = max(max_dd, (peak - index) / peak)
    else:
        for _, equity in snaps:
            peak = max(peak, equity)
            max_dd = max(max_dd, (peak - equity) / peak)
```

Add to `strategy_metrics`'s docstring, after the paragraph that defends `total_return`/`cagr`:

```
    ``max_drawdown`` is **not** in that amnesty, and the asymmetry is the point. ``total_return``
    and ``cagr`` are left contaminated deliberately, because they are the recorded shape of the
    curve that readers of the 128 historical trials depend on, and ``mwr`` stands beside them with
    the honest number. The drawdown has no such companion and is read directly as a go-live
    condition, so for a funded run it is measured on the time-weighted index instead of on raw
    equity -- a deposit must not be allowed to make a method look safer than it was.
```

**Impact:** `curve_metrics` passes `c.cashflows`, so the DCA'd SPY benchmark is corrected by the
same change and the book is compared against a benchmark measured the same way. `run_metrics`
already passes `external_cashflows(r)`, so the bracket engine is corrected too. **Unfunded: the
`else` branch is the original loop, reached by the original path — byte-identical.**

---

### Step 12: `backtest/book_runner.py` — a deposit is not a return

**File:** `engine/src/seer_engine/backtest/book_runner.py:536` (`_daily_returns`), `:552`
(`_year_returns`), `:48` (the import)
**Change:** **this is the gate defect.** `_daily_returns` is `cur / prev - 1.0` with no cashflow
term, so once the book is funded a deposit session records the deposit as a *return*. That series
feeds `_sharpe` (`:540`) -> `runner.daily_moments` -> `dev.deflated_sharpe` -> the `dsr` written to
`trials` -> `store.verdict`'s luck test. **DSR is a gate condition, not a display.**

Measured on the smoke fixture, funded on `OWNER_MONTHLY`: a single session recorded **+50.0000%**
and the annualized Sharpe came out **2.6524** for a book whose honest Sharpe is **0.2620** — a
**10.1x** inflation. After the fix the largest session is **+3.0697%**, identical to the unfunded
run's largest session, and the Sharpe is **0.2904**. (The residual 1.11x against the unfunded book
is not contamination: a funded book holds different amounts at different times and genuinely has a
slightly different time-weighted return.)

A deposit is credited at the **open** of the session it lands on and earns that session, so it
belongs in the **denominator** of the return into that session: `cur / (prev + flow_t) - 1`.

**Code** — the import at `:48`:

```python
from seer_engine.backtest.metrics import (
    YEAR_DAYS,
    Metrics,
    external_cashflows,
    flow_map,
    run_metrics,
    strategy_metrics,
)
```

`_daily_returns` in full:

```python
def _daily_returns(
    equity: Sequence[tuple[date, float]], cashflows: Sequence[tuple[date, float]] = ()
) -> tuple[float, ...]:
    """The session-over-session returns of the equity curve, net of external deposits.

    A deposit is credited at the OPEN of the session it lands on and earns that session, so it
    belongs in the DENOMINATOR of the return into that session: ``cur / (prev + flow_t) - 1``.
    Without that term a deposit is recorded as a return, and these returns feed ``_sharpe`` ->
    ``runner.daily_moments`` -> ``dev.deflated_sharpe`` -> the ``dsr`` the luck gate reads.
    Measured on the smoke fixture, the naive form reported a single +50.00% session and an
    annualized Sharpe of 2.652 for a book whose honest Sharpe is 0.262 -- a 10.1x inflation of a
    GATE CONDITION, which is why this is adjusted and ``total_return``/``cagr`` are deliberately
    not (``metrics.strategy_metrics``).

    ``cashflows`` empty -- the default, and every unfunded run -- takes the original expression
    unchanged, so the 128 recorded trials and every existing test are byte-identical.
    """
    if not cashflows:
        return tuple(cur / prev - 1.0 for (_, prev), (_, cur) in zip(equity, equity[1:]))
    flows = flow_map(cashflows)
    return tuple(
        cur / (prev + flows.get(d, 0.0)) - 1.0
        for (_, prev), (d, cur) in zip(equity, equity[1:])
    )
```

`_year_returns` in full:

```python
def _year_returns(
    equity: Sequence[tuple[date, float]], cashflows: Sequence[tuple[date, float]] = ()
) -> tuple[tuple[int, float], ...]:
    """Calendar-year returns of the curve; **time-weighted** when the run received deposits.

    With no cashflows this is end-of-year over end-of-previous-year, exactly as it always was --
    the original code path, taken verbatim, so an unfunded run is byte-identical.

    With deposits that ratio is not a return: measured on the smoke fixture a funded book reported
    a "worst year" of +74.3%, which is the deposits being counted as growth. The funded branch
    chains the cashflow-adjusted session returns inside each calendar year instead, which is the
    time-weighted return of that year and is what ``worst_year`` is trying to say. ``worst_year``
    is recorded and displayed but is **not** a gate condition (``dev.make_row``'s five checks are
    beats-SPY, drawdown, profit factor, trades and owner inputs), so this corrects a published
    number rather than a verdict.
    """
    if not cashflows:
        last_of_year: dict[int, float] = {}
        for d, value in equity[1:]:
            last_of_year[d.year] = value  # snapshots ascend, so the last one of a year wins
        out: list[tuple[int, float]] = []
        base = equity[0][1]
        for year in sorted(last_of_year):
            value = last_of_year[year]
            out.append((year, value / base - 1.0))
            base = value
        return tuple(out)
    flows = flow_map(cashflows)
    growth: dict[int, float] = {}
    for (_, prev), (d, cur) in zip(equity, equity[1:]):
        growth[d.year] = growth.get(d.year, 1.0) * (cur / (prev + flows.get(d, 0.0)))
    return tuple((year, growth[year] - 1.0) for year in sorted(growth))
```

**Impact:** `worst_year` for the smoke fixture's funded run moves from `(2015, +74.3%)` to
`(2014, +1.70%)`, beside the unfunded `(2014, +0.84%)`. **Unfunded: both functions take the
`if not cashflows` branch, which is the original code verbatim.**

---

### Step 13: `backtest/book_runner.py` — thread the deposits to where they are needed

**File:** `engine/src/seer_engine/backtest/book_runner.py:586` (`_assemble`), `:638`
(`_run_result_stats`), `:641` (`_book_metrics`), `:675` (`_book_result_stats`)
**Change:** both stats builders already hold the result, which carries `.cashflows`; read it with
`metrics.external_cashflows` (the module's documented single accessor) and pass it down. Nothing
invents a second way to reach that field.

**Code** — `_assemble`'s signature and first three lines:

```python
def _assemble(
    metrics: Metrics,
    equity: Sequence[tuple[date, float]],
    exposures: Sequence[float],
    notional: Decimal,
    costs: Decimal,
    trade_pnl: Decimal,
    trade_fees: Decimal,
    dividends: Decimal,
    cashflows: Sequence[tuple[date, float]] = (),
) -> RunStats:
    gross = trade_pnl + trade_fees
    returns = _daily_returns(equity, cashflows)
    years = _year_returns(equity, cashflows)
```

(the rest of `_assemble` is unchanged.)

`_run_result_stats`'s last statement:

```python
    return _assemble(
        run_metrics(r), equity, exposures, notional, costs, trade_pnl, trade_fees, _ZERO,
        cashflows=external_cashflows(r),
    )
```

`_book_metrics`'s signature and first line:

```python
def _book_metrics(
    snaps: Sequence[tuple[date, float]],
    trades: Sequence[Trade],
    cashflows: Sequence[tuple[date, float]] = (),
) -> Metrics:
    base = strategy_metrics(snaps, [float(t.pnl_usd) for t in trades], cashflows)
```

(the rest of `_book_metrics` is unchanged.)

`_book_result_stats`'s last statement:

```python
    cashflows = external_cashflows(r)
    return _assemble(
        _book_metrics(equity, trades, cashflows), equity, exposures, notional, r.costs_usd,
        trade_pnl, trade_fees, r.dividends_usd, cashflows=cashflows,
    )
```

**Impact:** passing `cashflows` into `_book_metrics` also makes `strategy_metrics` fill `Metrics.mwr`
for a funded `BookResult`, which closes the gap `dev._funded_stats` was patching after the fact
(`dev.py:451`–`:479`). **`_funded_stats` keeps working untouched and produces the identical number**
— its guard is `if not cashflows or stats.metrics.mwr is not None: return stats`, so it now returns
early, and the inputs it would have used (`[(s.date, float(s.equity_usd)) for s in result.snapshots]`
and `external_cashflows(result)`) are exactly what `_book_metrics` now passes. `dev.py`'s behaviour
is unchanged, so this phase still edits only its docstring. Worth noting in step 10's edit: the
sentence in `_funded_stats` naming "one keyword in ``book_runner._book_metrics``" as a later phase's
handoff is now satisfied — leave the text, it is still an accurate account of why the function
exists, but do not let a reader think the gap is open.

---

### Step 14: `tests/test_lab_test_window.py` — three doubles learn the new call

**File:** `engine/tests/test_lab_test_window.py:14`, `:23`, `:26`, `:340`, `:365`, `:390`
**Change:** three `dev.run_registry` test doubles. The first names its keywords explicitly and now
needs `contributions`; all three hand `run_test` a `SimpleNamespace` result that needs a
`cashflows` attribute, because `metrics.external_cashflows` reads it. **Measured: without this the
three tests fail with `TypeError: unexpected keyword argument 'contributions'` and
`AttributeError: 'types.SimpleNamespace' object has no attribute 'cashflows'`.**

**Code** — add to the imports at `:14` and `:23`:

```python
import sqlite3
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
```

```python
from seer_engine.sim.contributions import OWNER_MONTHLY
from seer_engine.sim.rules import MONTHLY_HOLD
```

Add this module constant just above the `# ---- fixtures ----` banner at `:26`:

```python
#: Two deposits a funded look would have received, in the shape `BookResult.cashflows` carries:
#: (session, Decimal USD), ascending, the opening cash excluded. The doubles return it so
#: `metrics.external_cashflows` has something real to read and `run_test` writes a funding row.
CASHFLOWS = ((date(2015, 10, 26), Decimal("2500.0000")), (date(2015, 11, 25), Decimal("2500.0000")))
```

Replace the double at `:340` with:

```python
    def fake_run_registry(market, dividends, spy_dividends, registry, *,
                          on_result=None, window=None, contributions=None):
        assert window.name == "test" and tuple(registry) == (c,)
        assert contributions is OWNER_MONTHLY  # the look is funded like the owner's account
        on_result(0, SimpleNamespace(snapshots=snaps, cashflows=CASHFLOWS), row)
        return (row,)
```

and both lambdas (`:365` and `:390`, identical text) with:

```python
        lambda *a, on_result=None, window=None, **k: (on_result(0, SimpleNamespace(snapshots=snaps, cashflows=CASHFLOWS), row), (row,))[1],
```

**Impact:** `test_a_passing_look_records_test_passed_and_a_dsr_that_is_not_a_condition` now also
pins that the look is funded. The other two are mechanical.

---

### Step 15: `tests/test_lab_costs.py` — the two direct `measure` calls

**File:** `engine/tests/test_lab_costs.py:94` and `:153`
**Change:** both call `real_costs.measure` on a trial that `run_method` has just recorded, so after
step 5 that trial is funded and the re-run must be too. **Measured: without this,
`cmp.reproduced is True` fails with False in `test_measure_runs_the_variant_at_both_fees_and_writes_nothing`.**
`runner` is already imported in this module (`from seer_engine.lab import real_costs, runner, store`).

**Code** — both call sites become (identical text in each test; `conn` and `trial` are already in
scope in both):

```python
    cmp = real_costs.measure(
        recorded, c, trial, data,
        contributions=runner.recorded_contributions(conn, int(trial["n"])),
    )
```

**Impact:** `cmp.reproduced is True` is preserved — the guard keeps its meaning instead of being
weakened to accommodate the funding. `test_a_test_window_store_is_refused` (`:144`) calls `measure`
with no `contributions` on purpose: it asserts the window refusal, which fires before any run.

---

### Step 16: `tests/test_book_runner.py` — a funded run's Sharpe is not inflated

**File:** `engine/tests/test_book_runner.py` — append at the end of the file
**Change:** four tests pinning steps 11–13. The construction is a book with a **known constant true
return** plus a deposit: a constant return has zero dispersion and therefore **no Sharpe at all**,
which is the sharpest possible statement of the property — the deposit must not create dispersion
where the strategy has none. Each test also states what the uncorrected form would do, so the
defect cannot be reintroduced silently.

The module already imports `date`, `math`, `pytest`, `book_runner` and `strategy_metrics`.

**Code** — append:

```python
# ---- R2: deposits are not returns (lab-realistic-gate phase 2) --------------------------------

_TW_DAYS = (date(2015, 1, 5), date(2015, 1, 6), date(2015, 1, 7), date(2015, 1, 8), date(2015, 1, 9))


def _steady_curve():
    """A book that grows EXACTLY 1% a session, with 50.00 deposited at the open of day 3.

    Its true return is constant, so its return series has zero dispersion and therefore no Sharpe
    at all. That is the sharpest possible statement of the property under test: the deposit must
    not create dispersion where the strategy has none.
    """
    flows = {_TW_DAYS[3]: 50.0}
    equity, value = [(_TW_DAYS[0], 100.0)], 100.0
    for d in _TW_DAYS[1:]:
        value = (value + flows.get(d, 0.0)) * 1.01
        equity.append((d, value))
    return equity, ((_TW_DAYS[3], 50.0),)


def test_a_deposit_is_not_a_return_in_the_daily_series():
    equity, cashflows = _steady_curve()
    adjusted = book_runner._daily_returns(equity, cashflows)
    assert adjusted == pytest.approx((0.01, 0.01, 0.01, 0.01), abs=1e-12)
    # Zero dispersion -> no Sharpe. The strategy earns a constant rate; there is nothing to
    # annualize a ratio over.
    assert book_runner._sharpe(adjusted) is None

    # The defect this pins, stated as what it would do: without the cashflow term the deposit
    # session reads as a ~+50% return -- dispersion the strategy never had -- and the Sharpe stops
    # being None. `trials.dsr` is computed from exactly this series and IS a gate condition
    # (`store.verdict`'s luck test), so an inflated Sharpe is an inflated verdict.
    naive = book_runner._daily_returns(equity)
    assert max(naive) > 0.4
    assert book_runner._sharpe(naive) is not None


def test_a_deposit_is_not_a_return_in_the_year_series():
    equity, cashflows = _steady_curve()
    (year, ret), = book_runner._year_returns(equity, cashflows)
    assert year == 2015 and ret == pytest.approx(1.01 ** 4 - 1.0, abs=1e-12)
    # Naively the deposit is growth: the year reads ~+58% instead of ~+4%.
    (_, naive_ret), = book_runner._year_returns(equity)
    assert naive_ret > 0.5


def test_a_deposit_does_not_damp_the_measured_drawdown():
    """A deposit that lands mid-drawdown refills the trough and hides the second leg.

    -20%, then 100.00 deposited at the open of the next session, then another -10%. The strategy
    is down 1 - 0.8 * 0.9 = 28%. Measured on raw equity the final mark (162) is above the old peak
    (100), so the fall reads as 20% and the method looks safer than it was -- against
    `tuning.MAX_DRAWDOWN`, which `lab.store.owner_failures` and `_blocking` re-derive as a GATE
    CONDITION.
    """
    d0, d1, d2, d3 = _TW_DAYS[:4]
    snaps = [(d0, 100.0), (d1, 100.0), (d2, 80.0), (d3, 162.0)]
    cashflows = ((d3, 100.0),)
    assert strategy_metrics(snaps, [], cashflows).max_drawdown == pytest.approx(0.28, abs=1e-12)
    assert strategy_metrics(snaps, []).max_drawdown == pytest.approx(0.20, abs=1e-12)


def test_an_unfunded_run_is_byte_identical():
    """Every expression above reduces to the original one when there is no deposit."""
    equity = [(d, 100.0 * 1.01 ** i) for i, d in enumerate(_TW_DAYS)]
    assert book_runner._daily_returns(equity, ()) == book_runner._daily_returns(equity)
    assert book_runner._year_returns(equity, ()) == book_runner._year_returns(equity)
    assert strategy_metrics(equity, [], ()).max_drawdown == strategy_metrics(equity, []).max_drawdown
```

> **Note on the drawdown test.** An earlier draft asserted the two forms on a curve where they
> happen to agree (both 0.20) and so proved nothing — it passed against the *uncorrected* code.
> The construction above is the minimal one where they genuinely differ: the deposit must land
> **mid-drawdown**, so the refilled trough hides a second leg down. If this test is edited, re-run
> it against the uncorrected `strategy_metrics` and confirm it fails.

**Impact:** four tests, **measured: 65 passed in `test_book_runner.py`** (61 before).

---

### Step 17: `tests/test_lab_runner.py` — the new tests

**File:** `engine/tests/test_lab_runner.py` — append at the end of the file
**Change:** four tests. **None asserts an absolute N**, so none of them can collide with
phase 1's work in this file.

**Code** — add to the imports:

```python
from seer_engine.lab.runner import OWNER_SCHEDULE_TEXT
from seer_engine.sim.contributions import OWNER_MONTHLY
```

and append:

```python
# ---- R2: the search is funded like the owner's account ---------------------------------------


def test_a_run_records_one_funding_row_per_trial(conn, data):
    """R2: every trial a funded run records carries what its deposits were and what they earned.

    The existence of the row is the funded flag, so this asserts a row per trial and not a column
    on `trials`. The numbers are the ones `trial_funding`'s CHECKs insist on -- deposits_usd > 0
    and deposits_n >= 1 -- plus the money-weighted pair the gate reads.
    """
    ran = runner.run_method(conn, _method(), Path(__file__), data, git_sha="x", require_commit=False)
    rows = store.trials_of(conn, "M0001")
    assert len(rows) == len(ran) == 2
    assert conn.execute("SELECT count(*) FROM trial_funding").fetchone()[0] == 2
    for r in rows:
        f = store.funding_of(conn, r["n"])
        assert f is not None, "a funded run records its funding beside the trial it judged"
        assert f["trial_n"] == r["n"]
        assert f["deposits_usd"] > 0 and f["deposits_n"] >= 1
        assert f["mwr"] is not None and f["spy_tr_mwr"] is not None
        assert f["schedule"] == OWNER_SCHEDULE_TEXT == "+5,000,000 IDR on the 25th of each month"
        assert f["measured"] == r["run_at"]  # one measurement, one stamp
        # The lie this phase ends: the total return counts the owner's own deposits as growth.
        assert r["total_return"] > 1.0 and f["mwr"] < 1.0
    # A second measurement of the same trial is refused by the store, not by luck.
    with pytest.raises(store.LabError, match="already has recorded funding"):
        with conn:
            store.insert_funding(conn, [store.FundingRow(
                trial_n=int(rows[0]["n"]), mwr=0.1, spy_tr_mwr=0.1, deposits_usd=1.0,
                deposits_n=1, schedule="x", measured="2026-01-01T00:00:00Z",
            )])


def test_the_money_weighted_branch_judges_a_funded_trial(conn, data):
    """The gate's money-weighted branch (`store._blocking`) is reachable and is what decides.

    A funded trial is judged on `mwr` vs `spy_tr_mwr`; the same row with no funding falls back to
    `total_return` vs `spy_tr_return`. Both branches are exercised on the same row, so this pins
    that the switch is the funding row and nothing else.
    """
    runner.run_method(conn, _method(), Path(__file__), data, git_sha="x", require_commit=False)
    seen = set()
    for r in store.trials_of(conn, "M0001"):
        f = store.funding_of(conn, r["n"])
        funded = store._blocking(r, f)
        lump = store._blocking(r, None)
        beats_mw = not any("money-weighted return" in m for m in funded)
        beats_total = not any("total return" in m for m in lump)
        seen.add((beats_mw, beats_total))
        # Whichever way each decides, the funded branch must speak money-weighted and the
        # unfunded one must speak total return. That is the branch, named.
        assert all("total return" not in m for m in funded)
        assert all("money-weighted return" not in m for m in lump)
    assert seen, "at least one trial was judged"


def test_the_recorded_trials_are_not_backfilled(conn, data):
    """GOTRADE_FEE_REBUILD_PLAN.md D18: funding applies to newly run methods only.

    The 54 seed rows this fixture carries stand in for the committed database's 128. A run must
    add funding for its own trials and for nobody else's.
    """
    before = {r[0] for r in conn.execute("SELECT n FROM trials")}
    assert before and all(store.funding_of(conn, n) is None for n in before)
    runner.run_method(conn, _method(), Path(__file__), data, git_sha="x", require_commit=False)
    assert all(store.funding_of(conn, n) is None for n in before)
    assert {r[0] for r in conn.execute("SELECT trial_n FROM trial_funding")}.isdisjoint(before)
    assert store.test_looks(conn) == 0  # and no look was spent


def test_the_recorded_funding_is_what_a_rerun_must_use(conn, data):
    """`recorded_contributions` is the single answer every re-run path asks for.

    `lab remeasure` and `lab costs` reproduce a recorded trial and refuse to write when the
    re-run is not the same measurement; funding it wrongly is exactly that. The funded flag is the
    row, so the answer is None for a seed trial and OWNER_MONTHLY for a trial this run recorded.
    """
    seeds = sorted(r[0] for r in conn.execute("SELECT n FROM trials"))
    runner.run_method(conn, _method(), Path(__file__), data, git_sha="x", require_commit=False)
    for n in seeds:
        assert runner.recorded_contributions(conn, n) is None
    for r in store.trials_of(conn, "M0001"):
        assert runner.recorded_contributions(conn, r["n"]) is OWNER_MONTHLY


def test_trial_rows_with_no_deposits_records_no_funding(conn, data):
    """The default is still a lump-sum book, and a lump-sum book has no funding row.

    `deposits=()` is read as "no deposit anywhere", which is what makes every one of the 128
    recorded trials describable by this code without a NULL to read two ways.
    """
    results: list = []
    dev_rows = dev_module.run_registry(
        data.market, data.dividends, data.spy_dividends, _method().candidates,
        on_result=lambda i, result, row: results.append((row, month_end_curve(result.snapshots))),
    )
    assert len(dev_rows) == 2
    ran = runner.trial_rows(conn, _method(), results, fingerprint="smoke", git_sha="x")
    assert [r.funding for r in ran] == [None, None]
```

The last test needs two more imports at the top of the module:

```python
from seer_engine.backtest import dev as dev_module
from seer_engine.commands.backtest_dev import month_end_curve
```

(`test_lab_runner.py` already imports `from seer_engine.backtest.dev import Candidate,
deflated_sharpe`; the module alias avoids shadowing.)

**Impact:** five new tests appended. **No pre-existing assertion in this file is changed by this
phase** -- the N assertions at `:58` and `:86` are phase 1's.

---

### Step 18: `tests/test_lab_remeasure.py` — the mixed-plan refusal

**File:** `engine/tests/test_lab_remeasure.py` — append at the end of the file
**Change:** one test for the only new refusal step 7 adds.

**Code** — append (the module's existing `_run`/`plan` helpers are at `:72` and are used as the
other tests in the file use them; adjust the helper names to the ones already in the module if they
differ):

```python
def test_a_plan_that_mixes_funded_and_unfunded_trials_is_refused(conn, data, tmp_path):
    """One `run_registry` call runs every candidate on one schedule, so a mixed plan has no
    answer that reproduces both. It is refused before anything is re-run or written."""
    import sqlite3 as _sqlite3

    from seer_engine.lab import remeasure as rm

    m = _method()
    runner.run_method(conn, m, HERE, data, git_sha="x", require_commit=False)
    ns = sorted(int(r["n"]) for r in store.trials_of(conn, m.id))
    assert len(ns) >= 2 and all(store.funding_of(conn, n) is not None for n in ns)
    # Drop one trial's funding row the only way the schema allows it to be absent: a database
    # where it was never written. `trial_funding` has no-delete and no-update triggers, so this
    # test builds the mixed state by copying the lab to a file and deleting with the triggers
    # dropped -- a state a real run cannot produce, which is the point of refusing it.
    path = tmp_path / "mixed.sqlite"
    other = _sqlite3.connect(path)
    conn.backup(other)
    other.execute("DROP TRIGGER trial_funding_no_delete")
    other.execute("DELETE FROM trial_funding WHERE trial_n = ?", (ns[0],))
    other.commit()
    other.close()
    mixed = store.connect(path)
    try:
        with pytest.raises(store.LabError, match="received deposits"):
            rm.measure(mixed, m, rm.plan_for(mixed, m), data)
    finally:
        mixed.close()
```

**Impact:** one new test appended. **No pre-existing assertion in this file is changed by this
phase** -- the N assertions at `:99`, `:102`, `:169` and `:274` are phase 1's.

> **Implementer note:** if `plan_for`'s real name or signature in `remeasure.py` differs from what
> this test assumes, read `engine/src/seer_engine/lab/remeasure.py:300`–`:352` and the existing
> tests in `test_lab_remeasure.py` and use the module's own idiom. The *assertion* that matters is
> `pytest.raises(store.LabError, match="received deposits")`; everything else is scaffolding. If
> building the mixed state proves awkward, assert the refusal against a hand-built `Plan` instead —
> `measure` reads only `plan.missing`, `plan.present`, `plan.candidates` and `plan.batches`.

---

## Verification

All commands assume the worktree. **`PYTHONPATH` is mandatory** — without it pytest silently tests
the main checkout instead of this branch.

**Build / lint:**

```bash
cd /home/miftah/.worktrees/seer/lab-realistic-gate/engine
/home/miftah/seer/engine/.venv/bin/python -m ruff check --select E9,F --ignore F401 \
  src/seer_engine/lab/runner.py src/seer_engine/lab/remeasure.py \
  src/seer_engine/lab/real_costs.py src/seer_engine/commands/lab.py \
  src/seer_engine/backtest/dev.py src/seer_engine/backtest/book_runner.py \
  src/seer_engine/backtest/metrics.py \
  tests/test_lab_runner.py tests/test_lab_costs.py tests/test_book_runner.py \
  tests/test_lab_test_window.py tests/test_lab_remeasure.py
```

Expected: `All checks passed!` (measured on the verified change).

**The modules this phase moves:**

```bash
cd /home/miftah/.worktrees/seer/lab-realistic-gate/engine
PYTHONPATH=$PWD/src /home/miftah/seer/engine/.venv/bin/python -m pytest \
  tests/test_lab_runner.py tests/test_lab_costs.py tests/test_lab_remeasure.py \
  tests/test_lab_remeasure_seed.py tests/test_lab_test_window.py tests/test_lab_prereg.py \
  tests/test_lab_snapshot.py tests/test_sim_contributions.py tests/test_backtest_dev.py \
  tests/test_book_runner.py tests/test_backtest_metrics.py tests/test_backtest_runner.py \
  tests/test_paper_book.py tests/test_paper_replay.py tests/test_backtest_walkforward.py -q
```

Expected: all pass. **Measured on the verified change (without this phase's new tests): 123 passed,
1 skipped** (`test_lab_costs.py:265`, which needs `SEER_LAB_COSTS_LIVE=1`). The six modules added
to the list are the ones that exercise `book_runner` and `strategy_metrics` directly — the files
steps 11-13 touch.

**Full engine suite:**

```bash
cd /home/miftah/.worktrees/seer/lab-realistic-gate/engine
PYTHONPATH=$PWD/src /home/miftah/seer/engine/.venv/bin/python -m pytest -q
```

Expected: green, with no "set-wide" qualifier — phase 1 leaves a green tree and so must this phase.

**Measured before/after**, two copies of `engine/` at base `2b493ee` under one environment, the
only difference being the change:

| | passed | failed | skipped |
|---|---|---|---|
| baseline, unmodified | **3076** | 2 | 406 |
| funding + cashflow correction + the four `test_book_runner` tests | **3080** | 2 | 406 |

**+4 passed, which is exactly the four new tests. Not one existing test moved** — that is the
suite-level proof of requirement 4, unfunded runs being byte-identical. The 2 failures are
identical in both columns and are artifacts of measuring in a copy
(`test_lab_promote_command_exits_2_when_the_lab_refuses` needs a real `.git`;
`test_snapshot_path_is_beside_the_databases_repo` resolves `COMMITTED_DB` through a symlink). In
the worktree both pass. The skips are `PG_TEST_URL` DB tests plus the live-store opt-ins.

Implementing steps 17 and 18 as well adds 6 more, for an expected **3086 passed** in the worktree.

Do **not** pass `-o addopts`; `-n auto` comes from `pyproject.toml` and the suite is ~50s with it
and ~6 minutes without.

**The contamination check — the one that would have caught this before it shipped.** Steps 11-13
exist because a funded run's Sharpe and drawdown are gate conditions. Measure them directly rather
than trusting that the suite is green:

```bash
cd /home/miftah/.worktrees/seer/lab-realistic-gate/engine
cat > /tmp/verify_tw.py <<'EOF'
from datetime import date
from labkit import smoke_data
from seer_engine.backtest import dev
from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.metrics import external_cashflows
from seer_engine.sim.contributions import OWNER_MONTHLY
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC
from seer_engine.strategies.f_index import TIMING, TimingParams

c = Candidate(id="M0001-A", family="M0001", rules=MONTHLY_HOLD_FRAC, allocator=TIMING,
              params=TimingParams(hold="SPY", signal="SPY", rule="sma", n=50),
              rationale="t", added=date(2026, 10, 8), owner_inputs=())
d = smoke_data()
for label, contrib in (("unfunded", None), ("funded", OWNER_MONTHLY)):
    got = {}
    dev.run_registry(d.market, d.dividends, d.spy_dividends, (c,),
                     on_result=lambda i, result, row: got.update(row=row, result=result),
                     contributions=contrib)
    row, m = got["row"], got["row"].stats.metrics
    print(f"{label:9s} sharpe={row.stats.sharpe:.4f}  max_dd={m.max_drawdown:.4f}  "
          f"spy_tr_dd={row.spy_tr.max_drawdown:.4f}  "
          f"worst_day=+{max(row.stats.daily_returns):.4%}  worst_year={row.stats.worst_year}  "
          f"deposits={len(external_cashflows(got['result']))}")
EOF
PYTHONPATH=$PWD/src:$PWD/tests /home/miftah/seer/engine/.venv/bin/python /tmp/verify_tw.py
```

**Measured expected output after steps 11-13:**

```
unfunded  sharpe=0.2620  max_dd=0.1055  spy_tr_dd=0.2575  worst_day=+3.0697%  worst_year=(2014, 0.00839316000000001)  deposits=0
funded    sharpe=0.2904  max_dd=0.1034  spy_tr_dd=0.2555  worst_day=+3.0697%  worst_year=(2014, 0.017033361651642043)  deposits=20
```

The three things to read, in order of importance:

1. **`funded worst_day == unfunded worst_day`** (`+3.0697%`). If the funded figure is tens of
   percent, a deposit is still being recorded as a return and the DSR is inflated. **Uncorrected
   this reads `+50.0000%`.**
2. **`funded sharpe` is within ~15% of `unfunded sharpe`.** Uncorrected it is **2.6524**, a 10.1x
   inflation of a gate condition. The residual gap (0.2904 vs 0.2620) is real and expected.
3. **`funded max_dd` and `spy_tr_dd` are close to the unfunded ones.** Uncorrected they are
   **0.0796** and **0.1059** — deposits damping the fall on both sides of the comparison.

The unfunded line must be **character-for-character** what it is before the phase. That is
requirement 4, and the full suite is the other half of its proof.

**Manual check — a funded run end to end, on a throwaway database only:**

```bash
cd /home/miftah/.worktrees/seer/lab-realistic-gate/engine
cat > /tmp/verify_funding.py <<'EOF'
import pathlib, tempfile
from datetime import date
from labkit import smoke_data
from seer_engine.backtest.dev import Candidate
from seer_engine.lab import runner, store
from seer_engine.lab.method import Method
from seer_engine.lab.seed import seed
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC
from seer_engine.strategies.f_index import TIMING, TimingParams

d = pathlib.Path(tempfile.mkdtemp())
conn = store.connect(d / "lab.sqlite"); seed(conn)
before = conn.execute("SELECT count(*) FROM trials").fetchone()[0]
def cand(cid, n):
    return Candidate(id=cid, family="M0001", rules=MONTHLY_HOLD_FRAC, allocator=TIMING,
                     params=TimingParams(hold="SPY", signal="SPY", rule="sma", n=n),
                     rationale="t", added=date(2026, 10, 8), owner_inputs=())
m = Method(id="M0001", name="x", family="trend", source_kind="knowledge", source_ref="",
           hypothesis="h", expected_failure="f",
           candidates=(cand("M0001-A", 50), cand("M0001-B", 20)))
runner.run_method(conn, m, pathlib.Path(__file__), smoke_data(), git_sha="x", require_commit=False)
print("schedule text:", repr(runner.OWNER_SCHEDULE_TEXT))
print("trials before/after:", before, conn.execute("SELECT count(*) FROM trials").fetchone()[0])
print("funding rows:", conn.execute("SELECT count(*) FROM trial_funding").fetchone()[0])
for r in store.trials_of(conn, "M0001"):
    f = store.funding_of(conn, r["n"])
    print(f"n={r['n']} {r['candidate_id']}: total_return={r['total_return']:.4f} "
          f"spy_tr={r['spy_tr_return']:.4f} -> mwr={f['mwr']:.4f} spy_tr_mwr={f['spy_tr_mwr']:.4f} "
          f"deposits={f['deposits_n']}x -> {f['deposits_usd']:.2f} USD")
    print("   funded branch  :", store._blocking(r, f)[0])
    print("   lump-sum branch:", store._blocking(r, None)[0])
print("seed trial 1 funding:", store.funding_of(conn, 1))
print("test looks:", store.test_looks(conn))
EOF
PYTHONPATH=$PWD/src:$PWD/tests /home/miftah/seer/engine/.venv/bin/python /tmp/verify_funding.py
```

**Measured expected output** (deterministic on the smoke fixture, except `run_at`):

```
schedule text: '+5,000,000 IDR on the 25th of each month'
trials before/after: 54 56
funding rows: 2
n=55 M0001-A: total_return=10.7821 spy_tr=11.2162 -> mwr=0.0764 spy_tr_mwr=0.1182 deposits=20x -> 50000.00 USD
   funded branch  : money-weighted return 0.0763716872942998 does not beat the SPY TR fed the same deposits 0.1182387296702205
   lump-sum branch: total return 10.78211698 does not beat SPY TR 11.21619776
n=56 M0001-B: total_return=12.8471 spy_tr=11.8912 -> mwr=0.2050 spy_tr_mwr=0.1228 deposits=21x -> 52500.00 USD
   funded branch  : 4 closed trades is under 100
   lump-sum branch: 4 closed trades is under 100
seed trial 1 funding: None
test looks: 0
```

(The two candidates get 20 and 21 deposits because their SMA warm-up puts the window start a month
apart; `deposits_n` is a property of the run, not of the schedule.)

**The committed database must be untouched:**

```bash
cd /home/miftah/.worktrees/seer/lab-realistic-gate
git status --porcelain lab/ web/data/lab.json      # expect: empty
sha256sum lab/lab.sqlite                           # compare with the pre-phase value
```

**Do not run `lab run` or `lab test` against `lab/lab.sqlite` in this phase.** Every lab command
migrates the file on connect, so even a read dirties it. If a read happens anyway: hash the file
first, restore it by path afterwards (`git checkout -- lab/lab.sqlite`), and never
`git add -A` / `git reset --hard` — the worktree and index are shared with the phase 1 session.

**Exit criteria:**

1. A newly run method records **exactly one** `trial_funding` row per trial, each with
   `deposits_usd > 0`, `deposits_n >= 1`, a non-NULL `mwr` and a non-NULL `spy_tr_mwr`, a
   `schedule` of `"+5,000,000 IDR on the 25th of each month"`, and `measured == the trial's run_at`.
2. `store.funding_of(conn, n) is None` for every trial recorded before the phase — **all 128 on the
   committed database, none of them backfilled.**
3. The money-weighted branch at `store.py:1428` is reachable and exercised: a funded trial is
   judged on `mwr` vs `spy_tr_mwr`, the same row with `funding=None` on `total_return` vs
   `spy_tr_return` (`test_the_money_weighted_branch_judges_a_funded_trial`).
4. `SELECT count(*) FROM trials` on `lab/lab.sqlite` is **128**, unchanged by the phase, and
   `store.test_looks` is **2**. The phase writes no real trial: every test uses a tmp database.
5. `lab remeasure` and `lab costs` reproduce a funded trial (no false "the store or the engine
   changed"), and reproduce an unfunded recorded trial byte-for-byte as they do today.
6. **No deposit is recorded as a return.** For a funded run on the smoke fixture,
   `max(row.stats.daily_returns)` equals the unfunded run's largest session (`+3.0697%`) rather
   than a deposit-sized jump (`+50.0000%`), and `book_runner._sharpe` of a constant-return funded
   curve is `None`.
7. **The two contaminated gate conditions read honestly.** A funded run's annualized Sharpe is
   within ~15% of the same candidate's unfunded Sharpe (measured 0.2904 vs 0.2620) and **not the
   uncorrected 2.6524**; its `max_drawdown` is within ~5% of the unfunded one (measured 0.1034 vs
   0.1055) and **not the uncorrected 0.0796**; and the DCA'd SPY benchmark's `max_drawdown` is
   0.2555, **not the uncorrected 0.1059**.
   *An implementation that records an inflated `dsr` fails this criterion. Criteria 1–5 alone would
   not have caught it — that is how this nearly shipped.*
8. **Unfunded runs are byte-identical.** Full-suite before/after: **3076 -> 3080 passed, the +4
   being exactly the new `test_book_runner.py` tests, with no existing test changed, skipped or
   re-expected.**
9. `git diff --stat` touches
   `engine/src/seer_engine/{lab/runner.py,lab/remeasure.py,lab/real_costs.py,commands/lab.py,backtest/dev.py,backtest/book_runner.py,backtest/metrics.py}`
   and five test modules, and **nothing else** — in particular not `lab/store.py`,
   `lab/npolicy.py`, `sim/contributions.py`, `lab/lab.sqlite` or `web/data/lab.json`.
10. Full engine suite green.

---

## Handoffs

- **Phase 1 owns the N assertions in the two test modules this phase also edits** — resolved, not
  open: see "Test modules shared with phase 1" in the contract. This phase edits those files for
  funding behaviour only.
- **`backtest.book_runner._book_metrics`'s missing cashflows keyword is now closed** by step 13,
  which satisfies the handoff `dev._funded_stats` records in its own docstring
  (`dev.py:451`–`:479`). `_funded_stats` still works and still returns the identical number; it
  simply returns early now. Removing it would be a tidy-up for a later phase, not this one — it
  remains the correct safety net for any future funded result type whose metrics are built without
  cashflows.
- **Backfilling funding onto the 128 recorded trials is refused, not deferred.**
  `GOTRADE_FEE_REBUILD_PLAN.md` D18 froze the lab so recorded trials stay byte-reproducible, and
  `funding_of` returning None already means something definite. If the owner ever wants the old
  methods measured on his real funding, the route is phase 3's variation twin, not a backfill.
- **`lab.remeasure.run_chunk` / `remeasure_seed` stay unfunded** and are deliberately not touched:
  the 54 P7a seed rows are frozen records with `dsr` NULL by construction and can never acquire a
  `trial_funding` row, so an unfunded re-run is the correct re-run. If seed rows are ever re-run
  funded, `run_chunk` needs the same `recorded_contributions` treatment `measure` gets here.
- **`mar` mixes two measures for a funded run.** `dev.make_row` computes
  `mar = rate / max_drawdown` where `rate` is the **money-weighted** return and, after step 11, the
  drawdown is **time-weighted**. Both are now honest numbers and the ratio is far better than the
  deposit-inflated one it replaces, but they answer slightly different questions. `mar` ranks
  finalists and is recorded; deciding whether it should be time-weighted on both sides is a
  measurement question worth its own look, and no gate condition reads `mar`.
- **`web/data/lab.json` publishes no funding fields.** `store.snapshot` reads funding only through
  `published_verdict`, which already branches on `funding_of`, so the web is correct for the 128
  unfunded trials and correct for a funded one's verdict — but a reader of seertrade.site cannot
  yet *see* the deposits or the money-weighted pair. Publishing them is a snapshot-contract change
  (a schema bump plus `web/lib/sera/*` and its tests) and belongs to its own phase, not here.
- **`real_costs.Side` and `Comparison` carry no `mwr`.** `lab costs` prints total returns and CAGRs
  side by side; on a funded trial those are the deposit-inflated numbers. The report is still
  internally consistent (both sides fed identically), but a money-weighted row would make it
  readable. Report-only change, no recorded row, not needed for R2.
- **`lab.name_count` resolves `OWNER_MONTHLY` by `getattr` on a module name string**
  (`name_count.py:88`–`:153`), a shape from before `sim.contributions` existed. Now that
  `lab.runner` imports it directly, those indirections could collapse to an import. Pure cleanup,
  deliberately left out.

---

## Rollback

Nothing recorded, nothing migrated, nothing published — this phase writes no row to
`lab/lab.sqlite` and no byte to `web/data/lab.json`, so there is nothing to restore.

```bash
cd /home/miftah/.worktrees/seer/lab-realistic-gate
git checkout -- \
  engine/src/seer_engine/lab/runner.py \
  engine/src/seer_engine/lab/remeasure.py \
  engine/src/seer_engine/lab/real_costs.py \
  engine/src/seer_engine/commands/lab.py \
  engine/src/seer_engine/backtest/dev.py \
  engine/src/seer_engine/backtest/book_runner.py \
  engine/src/seer_engine/backtest/metrics.py \
  engine/tests/test_lab_runner.py \
  engine/tests/test_lab_remeasure.py \
  engine/tests/test_lab_costs.py \
  engine/tests/test_lab_test_window.py \
  engine/tests/test_book_runner.py
```

Reverting to phase 1's commit, not to `main`: this phase depends on phase 1 and the two share
`remeasure.py` and the two lab test modules. Check out the paths above from phase 1's tip, never
from `main`.

By pathspec only. **Never `git add -A` and never `git reset --hard`** — the worktree and its index
may still be shared with other sessions in this set.

Reverting steps 11-13 alone is possible (`book_runner.py` + `metrics.py` + `test_book_runner.py`)
but **must not be done while the funding work stands**: that combination is the one state this plan
calls strictly worse than either end point — a funded lab whose luck gate reads an inflated Sharpe
and a damped drawdown. Revert both together or neither.

If the phase has already been committed, revert that commit alone; it touches no database file, so
no `lab stage` and no republish is needed to undo it. A method *run* after the phase landed keeps
its `trial_funding` rows, which cannot be deleted (`trial_funding_no_delete`) — reverting the code
does not and must not unrecord a measurement that really happened.

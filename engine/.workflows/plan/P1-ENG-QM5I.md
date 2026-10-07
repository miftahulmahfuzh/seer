> Adopted from `LAB_LUCK_GATE_PLAN.md` phase 5. Source: `.workflows/plan/lab-luck-gate/phase-5.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 5: `lab status` shows the queue and the look budget

**Plan set:** `LAB_LUCK_GATE_PLAN.md`
**Analysis:** `20261007-085606-D3K1_code_analyzer.md`
**Satisfies:** R3 — the promotion path is unreachable and the test window unspent, and nothing
surfaces either. Also **R1**, through Decision **D1b** alone: the index's Requirements table now
lists phase 5 under R1 because the ratchet warning is this phase's, and `lab luck` is the
instrument that shows what the unpulled N lever would do. This phase does **not** change the gate.
**Depends on:** Phase 4 (and, transitively, Phases 1, 2 and 8). **Not** phase 3, although both
write `commands/lab.py`: this phase's `_HANDLERS` and import edits are stated as *insertions*
(Steps 1 and 9), so they are correct whether phase 3's line is already there or not. See the
shared-file protocol below.
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine/commands`

> **Written against Decisions D1 and D1b as amended 2026-10-07.** Phase 4 ships
> `DSR_MIN = 0.90` (the owner's stated risk appetite) and leaves N alone: `store.DSR_POLICY`
> defaults to `all-trials`, so the live N is still every dev trial row, 110 today. Everything
> below quotes the tree as it will look after that lands. Two things follow, and both are new
> since the first draft of this plan:
>
> - `lab luck` is now the instrument for the lever that was *not* pulled, so it must print, per
>   policy, how many candidates clear the current bar at that policy's N. Measured on the
>   committed database: **2** at (N=110, 0.90) — M0022-W-TV14 and W-TV16 — and **5** at
>   (N=23, 0.90). That contrast is D1's evidence, and it belongs in the output.
> - `lab status` must warn before the gate re-closes (D1b), because at 0.90 the best candidate
>   has 0.016 of margin and loses it to the search itself.

---

## Goal

After this phase, `lab status` always prints the promotion path — `dev-eligible → promoted →
test-passed → paper` — including when every section of it is empty, with the reason it is empty
built from the trials themselves; it prints what `lab promote` would take today ("Promotable
now"); it prints the test-window look budget as a budget, not a counter; and it warns when the
luck bar is about to re-close, naming the N at which the best candidate falls back below it. A new
read-only subcommand, `lab luck`, prints the dev leaderboard under every N policy side by side,
with the N each resolves to, the evidence behind it, and how many candidates clear the bar there.

The condition the analysis found silent for 110 trials — "`lab promote` requires `dev-eligible`
and `lab test` requires `promoted`, so the entire promotion path is unreachable code" — becomes
the first thing the promotion-path block says, and the *next* time it is about to become true,
the block says so roughly 33 dev trials in advance instead of 110 late.

---

## Interface Contract

**Deletes:** nothing.

**Renames:** nothing.

**Creates (all in `commands/lab.py` unless noted):**
- ~~`sr_star`~~ and ~~`recover_dsr`~~ — **moved to `lab/store.py` and owned by phase 4**
  (reconciled). This phase drafted them here because `store.py` belonged to phases 2 and 4; phase
  4 then turned out to need the same inversion for the gate itself (`store.dsr_at`), and two
  implementations of the deflated Sharpe's inversion is one too many. This phase **re-exports**
  the two names so its call sites and tests read unchanged:

  ```python
  # the lab's own arithmetic, defined once in lab/store.py (phase 4)
  from seer_engine.lab.store import recover_dsr, sr_star
  ```

  Their signatures and semantics are exactly as drafted here, including the identity that
  `recover_dsr` returns `dsr_at_run` unchanged at `n_trials == n_at_run`.
- `_owner_misses(row) -> list[str]` — **a one-line alias for `store.owner_failures(row)`**
  (phase 4), which re-derives the four threshold conditions from the row's recorded columns
  against the live constants and carries `owner inputs` from the recorded string. It takes the
  **row**, never `row["failed"]`, and carries no rule of its own
- `_dev_var`, `_labels`, `_policies`, `_n_counts`, `_evidence`, `_live_n`
- `_best_luck_only`, `_no_dev_eligible_reason`, `_empty_reason`, `_promotable_now`
- `_dev_trials_per_run_day`, `_sinks_at`, `_ratchet_warning` — D1b
- `_eligible_at` — D1's per-policy count
- `_promotion_path`, `_PROMOTION_STATUSES`, `_WARN_MARGIN`, `_N_CEILING`
- `_positive_n`, `_luck_rows`, `_luck`
- CLI subcommand `lab luck [--at N ...] [--limit K]`
- `engine/tests/test_lab_status.py` (new file)
- `engine/tests/test_lab_luck.py` (new file)

**Signature changes:** none. `_status(conn, args)` keeps its signature.

**Modifies (shared file — see "Leaves alone"):**
- `commands/lab.py` module docstring: the `lab status` line, and a new `lab luck` entry after it
- `commands/lab.py` imports: `+ dataclasses`, `+ math`, `+ statistics`,
  `+ from collections.abc import Sequence`
- `commands/lab.py` `add_arguments`: one new subparser, after `sub.add_parser("status", ...)`
  (`lab.py:70`)
- `commands/lab.py` `_status`: the inline `misses()` at `lab.py:205-206` becomes `_owner_misses`
  (**a correctness fix forced by D1**, see Step 7a); the section loop at `lab.py:214-223` splits
  into a backlog loop plus `_promotion_path(conn)`
- `commands/lab.py` `_HANDLERS`: one new key, `"luck": _luck`

**Requires (from earlier phases) — pin these, reconciler:**

1. **Phase 4 ships `store.DSR_MIN = 0.90`, with `store.DSR_LABEL` derived from it**
   (`DSR_LABEL = f"{LUCK_LABEL_PREFIX}{DSR_MIN:.2f}"`) rather than left as the literal
   `"DSR >= 0.95"`. **Phase 8 ships `tuning.MAX_DRAWDOWN = 0.20`**, with
   `dev.FAILURE_LABELS`'s drawdown entry following it. Nothing in this phase hardcodes any of
   those values.
2. **Phase 4 exports `store.owner_failures(trial_row)` and this phase uses it for every
   "which conditions does this trial miss?" question.** Reconciled, and this replaced an earlier
   draft of this phase that carried its own rule (`not f.startswith("DSR ")`) over the recorded
   `failed` string. Two things were wrong with that draft:

   - **Two definitions of one rule.** The question "is this label the luck test?" must have one
     answer, and it lives in `store.py` (`store.is_luck_label`, `store.LUCK_LABEL_PREFIX`).
   - **Reading conditions out of `failed` at all is now a bug, not a style.** `trials` is
     append-only, so those 110 strings name the bars in force on each trial's **run date** —
     `"DSR >= 0.95"` and `"max DD <= 15%"` — and the owner has moved **both** (0.90 on D1, 20% on
     D6). Parsing them freezes every recorded trial at the bar it was judged by: `M0022` would
     show as failing a luck bar nobody applies, and `M0020-W-NOSTOP` — newly eligible at 19.3%
     under the 20% bar — would show `misses 1: max DD <= 15%` for ever. Those are the two
     candidates this plan set exists to unblock.

   `store.owner_failures` takes the **row** and re-derives the four threshold conditions from its
   recorded numeric columns against the live constants, carrying only `owner inputs` from the
   string. `_owner_misses(row)` is a one-line alias for it.

2b. **Where this phase still reads the recorded string, it is display, and it says so.**
   `store.recorded_labels(failed)` and `store.is_luck_label` (both phase 4) are the helpers for
   "what did the lab say on the day?". Never use them to decide what a trial is now.
3. Phase 1: `npolicy.effective_n(conn, policy) -> NCount` with `.n: int` and `.policy: str`. The
   evidence fields are read **generically** (`dataclasses.asdict`), so no `NCount` field name is
   hardcoded here. `npolicy.POLICIES` is read if present; `("all-trials", "methods", "effective")`
   is the fallback order.
4. Phase 4: `store.DSR_POLICY: str`, default `"all-trials"` per D1 — read, never written.
5. Phase 4: `store.verdict(conn, trial) -> Verdict` with `.dsr: float | None`, `.eligible: bool`,
   `.n: int`, `.policy: str` and **`.failed: tuple[str, ...]`** — pinned to a tuple of label
   strings, owner conditions first in `dev.FAILURE_LABELS` order, luck label last. `_labels`
   accepts either shape and is kept only as a defensive reader for display.
6. Phase 4: **`store.verdict` re-derives the four threshold conditions as well as the luck test**,
   and carries only `owner inputs` from the record. Reconciled — an earlier draft of this phase
   assumed the owner conditions came through verbatim, which stopped being true when the owner
   moved the drawdown bar. The consequence here is that the two pre-filters below —
   `if _owner_misses(r): continue` in `_best_luck_only` and `_eligible_at` — are **still correct
   and still cheap**, because `_owner_misses` is now `store.owner_failures`, a pure read of the
   row's own columns with no estimator and no database query behind it. They remain pre-filters
   for the expensive call (`store.verdict`, which resolves the gate), not a second rule.
7. Phase 4: `store.best_dev_eligible(conn, method_id)` selects on the **derived** verdict, so
   "Promotable now" and `lab promote` cannot disagree.
8. Performance — **settled.** `lab status` calls `store.best_dev_eligible` once per method that
   has a dev trial (23 on the committed database), and the estimator is an eigendecomposition
   over 110 curves. Phase 4 memoises `store.gate` on a content-derived key (`_GATE_CACHE`), so the
   estimator runs once per (database, policy, dev trial set). **The memo is the optimisation; the
   guarantee is `at=`:** `store.gate` and `store.verdict`/`store.best_dev_eligible` all take
   `at: Gate | None`, so `_promotion_path` should resolve `g = store.gate(conn)` once at the top
   and pass `at=g` down through `_promotable_now`, `_best_luck_only` and `_no_dev_eligible_reason`
   rather than lean on the cache being warm.

**Leaves alone (owned by others):**
- `lab/npolicy.py` (Phase 1); `lab/store.py` and `lab/runner.py` (Phases 2 and 4) — including
  `DSR_MIN`, `DSR_LABEL`, `DSR_POLICY`, `summary_rows` and `snapshot`; `lab/prereg.py`, the design
  doc, `SKILL.md` and the web (Phase 7); `paper/roster.py` (Phase 6).
- Every write path. **`lab luck` writes nothing and loads no research store**; it is safe
  against the committed database. `lab status` is read-only and stays so.
### Shared-file protocol (reconciled — read before editing `commands/lab.py`)

`commands/lab.py` is written by **three** phases, and this one lands **last**: phase 3 adds
`lab remeasure`, phase 4 adds `lab reevaluate` plus the one-line `misses()` correctness fix at
`:204-206`, and this phase adds `lab luck` and rewrites `_status`'s section loop. The anchors are
disjoint:

| phase | docstring | subparser | handler | `_HANDLERS` | other |
|---|---|---|---|---|---|
| 3 | after the `lab test` block (`:18`) | after the `test` subparser (`:119`) | after `_test` (`:508`) | one line after `"test"` | — |
| 4 | after the `lab promote` block (`:10-12`) | after the `promote` block (`:90-99`) | after `_promote` (`:340`) | one line after `"promote"` | `misses()` at `:204-206` |
| 5 (here) | the `lab status` line (`:3`) + a `lab luck` entry | after the `status` subparser (`:70`) | between `_status` (`:235`) and `_show` (`:238`) | one line after `"status"` | `_status`'s section loop (`:214-223`), the import block |

Three rules:

1. **Insert at your named anchor; never rewrite a whole literal.** `_HANDLERS` gets **one line**
   from this phase (Step 9) and the import block is a **union** (Step 1). An earlier draft of this
   phase replaced both wholesale, which would have deleted phase 3's and phase 4's keys.
2. **Anchor on quoted text, not on a line number.** Every number above is `main`'s; phases 3 and 4
   land first and move them.
3. **The swarm shares one worktree.** A commit of this file may legitimately carry another phase's
   insertions. Keep them; never `git add -A`.

---

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/commands/lab.py` | modify | docstring (`:3`), imports (`:37-51`), `add_arguments` (`:70`), `_status`'s `misses()` (`:205-206`) and section loop (`:214-223`), new helpers + `_promotion_path` + `_luck` (inserted between `_status` at `:235` and `_show` at `:238`), `_HANDLERS` (`:621-638`) |
| `engine/tests/test_lab_status.py` | create | the path prints when empty; the reason; Promotable now; the budget; **the D1b ratchet warning**; the historical-label regression |
| `engine/tests/test_lab_luck.py` | create | `recover_dsr` reproduces the analysis document's table and SR\* row; **D1's 2-vs-5 counts**; **D1b's crossing N**; `lab luck` is read-only |

---

## Implementation Steps

### Step 1: imports

**File:** `engine/src/seer_engine/commands/lab.py:37-51`

**Change:** add `dataclasses`, `math`, `statistics`, `Sequence`. `statistics.NormalDist` is the
same normal the deflated Sharpe uses; `dataclasses` reads phase 1's `NCount` without naming its
fields.

**Code:** replace lines 37-51 with

```python
from __future__ import annotations

import argparse
import dataclasses
import logging
import math
import os
import statistics
import time
from collections.abc import Sequence
from pathlib import Path

from seer_engine import config, research
from seer_engine.backtest import dev
from seer_engine.backtest.metrics import fmt_num, fmt_pct, fmt_pf, fmt_signed_pct
from seer_engine.fundamentals import coverage
from seer_engine.lab import store

log = logging.getLogger(__name__)
```

**Impact:** none at runtime. **This is a union, not a replacement:** phases 3 and 4 land before
this one and may have added imports to the same block. Add `dataclasses`, `math`, `statistics` and
`Sequence` if they are not already there; keep everything that is. The block above is `main`'s
contents plus this phase's four names, not an exhaustive list of what should be there when you
arrive.

---

### Step 2: the module docstring

**File:** `engine/src/seer_engine/commands/lab.py:3`

**Change:** anchored on the `lab status` line, so phase 3's `lab remeasure` entry (which belongs
with `run`/`promote`) does not collide.

**Code:** replace line 3

```python
    lab status                      N, test looks, near misses, backlog, blocked ideas
```

with

```python
    lab status                      N, the promotion path and what is promotable now, the
                                    test-window look budget, a warning when the luck bar is about
                                    to re-close, near misses, backlog, blocked ideas
    lab luck [--at N ...] [--limit K]
                                    read-only: the dev leaderboard under every N policy side by
                                    side, the N each resolves to, the evidence behind it and how
                                    many candidates clear the luck bar there. Writes nothing,
                                    loads no research store, spends no look. --at N adds a column
                                    at a literal N (repeatable)
```

**Impact:** documentation only.

---

### Step 3: register the `lab luck` subparser

**File:** `engine/src/seer_engine/commands/lab.py:63` (helper) and `:70` (subparser)

**Code:** `_positive_n` goes next to `_coverage_floor`, after line 63:

```python
def _positive_n(text: str) -> int:
    """An ``--at N`` column: an integer the deflated Sharpe is defined at.

    ``dev.deflated_sharpe`` returns None below two looks, so ``--at 1`` would silently add a
    column of dashes. argparse says so instead.
    """
    try:
        value = int(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"not an integer: {text!r}") from exc
    if value < 2:
        raise argparse.ArgumentTypeError(
            f"the deflated Sharpe is undefined below N = 2 trials, got {value}"
        )
    return value
```

and inside `add_arguments`, replace line 70

```python
    sub.add_parser("status", help="the lab at a glance")
```

with

```python
    sub.add_parser("status", help="the lab at a glance")

    s = sub.add_parser(
        "luck",
        help="read-only: the dev leaderboard under every N policy, side by side",
        description=(
            "Re-evaluate every recorded dev DSR at the N each named policy resolves to, and at "
            "any literal N given with --at, and say how many candidates clear the luck bar at "
            "each. Reads the lab, writes nothing, loads no research store and spends no "
            "test-window look: safe against the committed database. The gate itself is one "
            "constant, store.DSR_POLICY; this command is how you decide whether to touch it."
        ),
    )
    s.add_argument(
        "--at",
        type=_positive_n,
        action="append",
        default=None,
        metavar="N",
        help="add a column at this literal N, on top of the named policies (repeatable)",
    )
    s.add_argument(
        "--limit",
        type=int,
        default=12,
        metavar="K",
        help="how many dev trials to list, ranked by the live policy (default 12; 0 for all)",
    )
```

**Impact:** `python -m seer_engine lab luck` becomes reachable. No existing subcommand changes.

---

### Step 4: the pure core — `sr_star`, `recover_dsr`, `_dev_var`, `_owner_misses`

**File:** `engine/src/seer_engine/commands/lab.py`, inserted after `_status` ends (`lab.py:235`)
and before `_show` (`lab.py:238`)

**Change — reconciled, and smaller than it was.** `sr_star` and `recover_dsr` are **phase 4's**,
defined in `lab/store.py` beside `store.dsr_at`, which needs the same inversion for the gate
itself. This module re-exports both names (no leading underscore) because the tests call them
directly: they are what the exit criterion "`lab luck` reproduces the analysis document's table"
is asserted against. Neither re-implements `dev.deflated_sharpe` — `sr_star` is that function's
own `sr_star` line, with its own `_EULER_GAMMA`, isolated so the hurdle can be asked for at an N
no trial was ever run at.

`_owner_misses` and `_dev_var` are likewise thin aliases for `store.owner_failures` and
`store.dev_sharpe_variance`. **Nothing in this module carries a rule of its own.** That is the
reconciled shape: phase 5 is a *presentation* layer over phase 4's gate, and every number it
prints is a number the gate would give.

**Code:**

```python
# --------------------------------------------------------------------------- the luck bar at another N
#
# `lab luck` and the ratchet warning answer one question: what would the recorded verdicts be
# if the deflated Sharpe had deflated by a different number of looks? They answer it without
# re-running anything, from the columns `trials` already carries, and they write nothing.
#
#     DSR = Phi((SR - SR*(N)) * k),  k = sqrt(t - 1) / sqrt(1 - g3*SR + (g4-1)/4 * SR^2)
#
# `k` does not depend on N. `t`, `g3` and `g4` are not in `trials` -- that is exactly what phase
# 2's `trial_moments` exists to fix for trials run from now on -- so `k` is recovered by
# inverting a known DSR at the N it belongs to, and the answer is the same Phi with a different
# `SR*`. See the analysis document, "What each N would do to the recorded verdicts".


def _owner_misses(row) -> list[str]:
    """The five go-live conditions ``row`` misses **at the bars in force now**. One line, by rule.

    ``store.owner_failures`` is the single definition of that question and it lives in
    ``lab/store.py`` (phase 4). This is a thin alias so the call sites below read as English;
    it must never grow a rule of its own.

    **It takes the trial row, not ``row["failed"]``.** That distinction is the whole point.
    ``trials`` is append-only, so a recorded ``failed`` string names the bars in force on the
    trial's **run date** -- all 110 recorded rows say ``"DSR >= 0.95"`` and ``"max DD <= 15%"``,
    and the owner moved both on 2026-10-07 (0.90 and 20%). Reading conditions back out of that
    string would show ``M0022`` as failing a luck bar nobody applies and ``M0020-W-NOSTOP`` as
    failing a drawdown bar nobody applies -- the two candidates this plan set exists to unblock,
    both rendered permanently ineligible by a sentence about the past.

    ``store.owner_failures`` re-derives the four *threshold* conditions from the row's recorded
    numeric columns against the live constants, and carries ``owner inputs`` -- the one condition
    that is not a threshold and has no column -- from the recorded string. See phase 4.
    """
    return list(store.owner_failures(row))


# ``sr_star`` and ``recover_dsr`` are **phase 4's**, defined in ``lab/store.py`` beside the gate
# that uses them, and re-exported here so this module's call sites and tests read as English.
# (Reconciled: this phase drafted them locally because ``store.py`` belonged to phases 2 and 4;
# phase 4 then needed the same inversion for ``store.dsr_at``, and the lab must not carry two
# implementations of the deflated Sharpe's inversion.)
#
#   sr_star(n_trials, var_trials)        -- the daily hurdle SR* at n_trials looks
#   recover_dsr(*, sharpe_daily, dsr_at_run, n_at_run, var_trials, n_trials)
#                                        -- a recorded DSR re-evaluated at another N; returns
#                                           dsr_at_run exactly at n_trials == n_at_run
from seer_engine.lab.store import recover_dsr, sr_star  # noqa: F401  (re-exported for the CLI)


def _dev_var(conn) -> float | None:
    """The variance of the dev trials' daily Sharpes. **Phase 4's ``store.dev_sharpe_variance``.**

    An alias, kept so the call sites below read locally; it must not grow a rule of its own. It
    is the same expression ``runner.trial_rows`` deflates by **and** the one ``store.dsr_at``
    uses on both of its routes, so the hurdle this module prints is the hurdle the gate applies.
    """
    return store.dev_sharpe_variance(conn)
```

**Impact:** new pure code; `_owner_misses` is wired into `_status` in Step 7a.

---

### Step 5: reading the N policies without naming phase 1's fields

**File:** `engine/src/seer_engine/commands/lab.py`, after Step 4's block

**Code:**

```python
def _policies() -> tuple[str, ...]:
    """The named N policies, in ``npolicy``'s own order."""
    from seer_engine.lab import npolicy

    return tuple(getattr(npolicy, "POLICIES", ("all-trials", "methods", "effective")))


def _n_counts(conn) -> list[tuple[str, object | None, str]]:
    """``(policy, NCount | None, why-not)`` for every named policy.

    A policy that cannot be resolved on this database -- too few trials to estimate a
    participation ratio, no stored curves -- keeps its row with ``None`` and the reason, instead
    of being dropped. ``lab luck`` is the command you run when the gate is behaving oddly; a
    policy that silently vanished from its table would be the worst possible answer.
    """
    from seer_engine.lab import npolicy

    out: list[tuple[str, object | None, str]] = []
    for name in _policies():
        try:
            out.append((name, npolicy.effective_n(conn, name), ""))
        except Exception as e:  # noqa: BLE001 - a diagnostic never dies on one unresolvable policy
            out.append((name, None, str(e) or type(e).__name__))
    return out


def _evidence(count: object) -> str:
    """Every field of an ``npolicy.NCount`` except ``n`` and ``policy``, which the caller prints.

    Read generically rather than by name: phase 1 owns the field names, and the evidence behind a
    policy is exactly the thing that must not go stale in this output.
    """
    try:
        data = dataclasses.asdict(count)  # type: ignore[arg-type]
    except TypeError:
        data = {
            k: getattr(count, k)
            for k in dir(count)
            if not k.startswith("_") and not callable(getattr(count, k, None))
        }
    parts = []
    for key, value in data.items():
        if key in ("n", "policy") or value is None:
            continue
        shown = fmt_num(value, 3) if isinstance(value, float) else value
        parts.append(f"{key.replace('_', ' ')} {shown}")
    return ", ".join(parts)


def _live_n(conn, policy: str) -> int | None:
    """The N the live policy resolves to, or None when it cannot be resolved here.

    ``lab status`` must print on any database, a fresh one with no trials included, so an
    unresolvable policy costs the N in the heading and nothing else.
    """
    from seer_engine.lab import npolicy

    try:
        return int(npolicy.effective_n(conn, policy).n)
    except Exception:  # noqa: BLE001 - see the docstring; status prints either way
        return None


def _labels(failed: object) -> list[str]:
    """``Verdict.failed`` (phase 4) as a list of labels, whichever shape it carries.

    ``trials.failed`` is a ``"; "``-joined string; ``DevRow.failed`` is a sequence. Phase 4's
    ``Verdict.failed`` mirrors one of the two. Both are read here, so the sentences this file
    exists to print are not the thing that breaks when that is pinned.
    """
    if failed is None:
        return []
    if isinstance(failed, str):
        return [f for f in failed.split("; ") if f]
    return [str(f) for f in failed]  # type: ignore[union-attr]


def _eligible_at(conn, n_trials: int, var_trials: float) -> list[str]:
    """The candidates that would clear the luck bar at ``n_trials`` looks, missing nothing else.

    D1's evidence, recomputed rather than quoted: on the committed database this returns two
    candidates at N = 110 (M0022-W-TV14 and W-TV16, the live policy) and five at N = 23. That
    contrast is why the owner can move the threshold and leave the N alone with confidence, and
    it belongs in `lab luck`'s output rather than in a commit message.

    Owner conditions come from the recorded labels through ``_owner_misses``; only the luck test
    moves with N.
    """
    out: list[str] = []
    for r in conn.execute(
        "SELECT * FROM trials WHERE window = 'dev' AND dsr IS NOT NULL AND sharpe IS NOT NULL "
        "ORDER BY n"
    ).fetchall():
        if _owner_misses(r):
            continue
        v = recover_dsr(
            sharpe_daily=float(r["sharpe"]) / math.sqrt(252),
            dsr_at_run=float(r["dsr"]),
            n_at_run=int(r["n_trials_at_run"]),
            var_trials=var_trials,
            n_trials=n_trials,
        )
        if v is not None and v >= store.DSR_MIN:
            out.append(str(r["candidate_id"]))
    return out
```

**Impact:** new code; nothing existing calls it yet.

---

### Step 6: the promotion path, the empty reasons, and the D1b ratchet warning

**File:** `engine/src/seer_engine/commands/lab.py`, after Step 5's block

**Code:**

```python
# --------------------------------------------------------------------------- the promotion path
#
# design §3's path is dev-eligible -> promoted -> test-passed -> paper, and every step refuses a
# method that has not taken the one before it. A lab where nothing is dev-eligible therefore has
# an unreachable `lab promote` and an unreachable `lab test`. Until this block existed, `lab
# status` listed these sections only when they had rows -- so that state printed nothing at all
# about the promotion path, and the one condition that most needed saying was the one condition
# that was silent. 110 dev trials went by that way.
#
# Here every section prints, an empty one prints the reason it is empty built from the trials,
# and `_ratchet_warning` says so *before* it happens again (Decision D1b).

_PROMOTION_STATUSES: tuple[tuple[str, str, str], ...] = (
    ("Dev-eligible", "dev-eligible", "`lab promote` pre-registers these"),
    ("Promoted (pre-registered)", "promoted", "`lab test` spends the one look on these"),
    ("Test-passed", "test-passed", "the owner's call: a paper roster entry with its own clock"),
    ("Test-failed", "test-failed", "final; there is no second look at the configuration"),
    ("Paper", "paper", "trading on the paper roster"),
)

# D1b. 0.03 of DSR is roughly 30 more dev trials at the margins this lab runs at, which is under
# a run day of Sera -- close enough that the owner wants to hear about it before the batch, not
# after. The warning is a sentence, not a gate: nothing refuses to run because of it.
_WARN_MARGIN = 0.03
_N_CEILING = 100_000  # beyond this the ratchet is not a near-term concern; say "never" instead


def _best_luck_only(conn):
    """The dev trial with the highest derived DSR among those missing no owner condition.

    The pre-filter is on the recorded labels (``_owner_misses``), because phase 4's derived
    verdict re-derives the luck test and nothing else -- so the owner conditions a trial misses
    are the recorded ones, and filtering first keeps `lab status` to a handful of
    ``store.verdict`` calls instead of one per dev trial.

    ``(row, verdict)``, or None when no dev trial passes all five owner conditions.
    """
    best = None
    for r in conn.execute(
        "SELECT * FROM trials WHERE window = 'dev' AND mar IS NOT NULL ORDER BY n"
    ).fetchall():
        if _owner_misses(r):
            continue
        v = store.verdict(conn, r)
        key = (-1.0 if v.dsr is None else float(v.dsr), -int(r["n"]))
        if best is None or key > best[0]:
            best = (key, r, v)
    return None if best is None else (best[1], best[2])


def _sinks_at(conn, trial, verdict, var_trials: float | None) -> int | None:
    """The smallest N at which this trial's DSR falls below the bar. D1b's number.

    Seeded from the verdict (phase 4), not from the recorded columns: the warning has to be about
    the gate as it actually stands. ``recover_dsr`` anchored at ``(verdict.dsr, verdict.n)``
    returns ``verdict.dsr`` exactly at ``verdict.n`` and falls monotonically from there, so this
    is the gate's own curve and the bisection on it is exact.

    None when it never falls below within ``_N_CEILING`` looks, or when the recovery is
    undefined, or when the verdict is already under the bar -- in which case the empty
    ``Dev-eligible`` section is already saying so and a second sentence would be noise.
    """
    if var_trials is None or var_trials <= 0 or verdict.dsr is None:
        return None
    if trial["sharpe"] is None or int(verdict.n) < 2:
        return None
    if float(verdict.dsr) <= 0.5 or float(verdict.dsr) < store.DSR_MIN:
        return None
    common = dict(
        sharpe_daily=float(trial["sharpe"]) / math.sqrt(252),
        dsr_at_run=float(verdict.dsr),
        n_at_run=int(verdict.n),
        var_trials=var_trials,
    )
    lo, hi = int(verdict.n), _N_CEILING
    far = recover_dsr(n_trials=hi, **common)
    if far is None or far >= store.DSR_MIN:
        return None
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        v = recover_dsr(n_trials=mid, **common)
        if v is None:
            return None
        if v >= store.DSR_MIN:
            lo = mid
        else:
            hi = mid
    return hi


def _dev_trials_per_run_day(conn) -> float | None:
    """The lab's recent rate: the median dev trials recorded per distinct run day.

    Measured from ``trials.run_at``, never assumed -- a hardcoded "a Sera night is 25 trials"
    would be exactly the kind of stale constant this plan set exists to remove. None below three
    run days, where a median is not a rate.
    """
    counts = [
        int(r[0])
        for r in conn.execute(
            "SELECT count(*) FROM trials WHERE window = 'dev' "
            "GROUP BY substr(run_at, 1, 10) ORDER BY substr(run_at, 1, 10) DESC LIMIT 10"
        ).fetchall()
    ]
    return statistics.median(counts) if len(counts) >= 3 else None


def _ratchet_warning(conn, var_trials: float | None) -> list[str]:
    """Decision D1b: say it *before* the luck bar re-closes, not 110 trials after.

    The gate admits a candidate today because the threshold moved, not because the N did. The N
    still rises with every exploration, so the margin the threshold bought is spent by the search
    itself -- which is the complaint R1 names, deferred rather than removed. This prints the
    margin, the N at which the best candidate falls back below the bar, and, when the lab has
    enough run days to have a rate, how many run days of exploration that is.

    Nothing here is a constant lifted from the analysis document: the candidate and its DSR come
    from ``store.verdict``, its N from ``npolicy`` through that, the bar from ``store.DSR_MIN``
    and the rate from ``trials.run_at``. It is silent when there is no candidate above the bar,
    and silent when the margin is comfortable.
    """
    found = _best_luck_only(conn)
    if found is None:
        return []
    trial, v = found
    if v.dsr is None or float(v.dsr) < store.DSR_MIN:
        return []  # the empty Dev-eligible section already explains this one
    margin = float(v.dsr) - store.DSR_MIN
    if margin > _WARN_MARGIN:
        return []
    sinks = _sinks_at(conn, trial, v, var_trials)
    head = (
        f"  !! The luck bar is close. {trial['candidate_id']} is the best candidate that passes "
        f"all five go-live"
    )
    second = (
        f"     conditions, and its DSR is {fmt_num(v.dsr, 3)} against a {store.DSR_MIN} bar -- "
        f"{fmt_num(margin, 3)} of margin at N = {v.n} ({v.policy})."
    )
    if sinks is None:
        return [head, second, "     It does not fall below the bar at any N worth worrying about."]
    more = sinks - int(v.n)
    rate = _dev_trials_per_run_day(conn)
    pace = ""
    if rate and rate > 0:
        days = more / float(rate)
        pace = (
            f" -- about {fmt_num(days, 1)} run day(s) at this lab's recent rate of "
            f"{fmt_num(rate, 0)} dev trials a run day"
        )
    return [
        head,
        second,
        f"     It falls below the bar at N = {sinks}: {more} more dev trials{pace}.",
        "     More exploration re-closes this gate. `lab luck` shows what each N policy would do.",
    ]


def _no_dev_eligible_reason(conn) -> str:
    """Why no method is dev-eligible, in one sentence built from the trials.

    Three shapes, in the order a reader needs them:

    1. nothing has run, so nothing has been judged;
    2. something has run, and every candidate misses an owner condition -- which no change to the
       luck bar's N or threshold can rescue, and the sentence says so;
    3. candidates pass all five owner conditions and the luck bar alone is holding them, in which
       case the closest one, its derived DSR and its distance from the bar *is* the sentence.
    """
    methods = int(
        conn.execute(
            "SELECT count(DISTINCT method_id) FROM trials WHERE window = 'dev'"
        ).fetchone()[0]
    )
    if methods == 0:
        return "no method has run on the dev window yet, so nothing has been judged"
    ran = "1 method has run" if methods == 1 else f"{methods} methods have run"
    found = _best_luck_only(conn)
    if found is not None:
        r, v = found
        return (
            f"no method is dev-eligible: {ran}, and every candidate that passes all five go-live "
            f"conditions is held by the luck bar alone -- the closest is {r['candidate_id']} at "
            f"DSR {fmt_num(v.dsr, 3)} against a {store.DSR_MIN} bar, N = {v.n} under policy "
            f"{v.policy}. `lab luck` shows what another N would do"
        )
    rows = conn.execute(
        "SELECT * FROM trials WHERE window = 'dev' AND mar IS NOT NULL ORDER BY n"
    ).fetchall()
    if rows:
        r = min(
            rows,
            key=lambda x: (len(_owner_misses(x)), -(x["mar"] or 0.0), int(x["n"])),
        )
        misses = _owner_misses(r)
        return (
            f"no method is dev-eligible: {ran} and none passes the five go-live conditions -- the "
            f"closest is {r['candidate_id']}, missing {len(misses)}: {'; '.join(misses)}. No luck "
            f"bar, at any N or any threshold, can rescue a candidate that misses one of these"
        )
    return f"no method is dev-eligible: {ran} but no dev trial carries a MAR, so nothing can rank"


def _empty_reason(conn, status: str) -> str:
    """Why one promotion-path section is empty.

    Every step but the first is empty for exactly one reason worth printing -- the step before it
    -- and naming the command that would move it is the whole value of the sentence. The first
    step, ``dev-eligible``, is empty because of the gate, and that is the sentence this block
    exists for.
    """
    if status == "dev-eligible":
        return _no_dev_eligible_reason(conn)
    prior = {
        "promoted": "dev-eligible",
        "test-passed": "promoted",
        "test-failed": "promoted",
        "paper": "test-passed",
    }[status]
    cmd = {
        "promoted": "lab promote",
        "test-passed": "lab test",
        "test-failed": "lab test",
        "paper": "python -m seer_engine promote",
    }[status]
    n = int(conn.execute("SELECT count(*) FROM methods WHERE status = ?", (prior,)).fetchone()[0])
    if n == 0:
        return f"nothing is {prior}, so `{cmd}` has nothing to take"
    noun = "1 method is" if n == 1 else f"{n} methods are"
    it = "it" if n == 1 else "them"
    return f"{noun} {prior}; `{cmd}` has not been run on {it} yet"


def _promotable_now(conn) -> list[str]:
    """What ``lab promote`` would take today, and what the status machine is still holding back.

    ``prereg.promote_method`` wants two things: a method at ``dev-eligible`` (or already
    ``promoted``), and a best dev trial the verdict calls eligible. ``store.best_dev_eligible``
    answers the second under ``store.DSR_POLICY`` (phase 4), so this section says what the gate
    says and cannot drift from it -- which is the point of reading the derived verdict here
    rather than the recorded ``eligible`` column, which was frozen at a 0.95 bar and an N of
    whatever day the trial ran.

    A method whose best trial *is* derived-eligible but whose status still reads ``rejected`` is
    listed separately and by name: it is not promotable now, and the one command that moves it is
    ``lab reevaluate <id>`` (phase 4), which takes the ``rejected -> dev-eligible`` edge. **Not
    ``lab run``** -- that refuses a method whose variants already have dev trials, so telling the
    reader to run it would send them into a refusal.

    Only methods that have a dev trial are asked, so the derivation runs 23 times on the
    committed database rather than 37.
    """
    ready: list[str] = []
    held: list[str] = []
    for m in conn.execute(
        "SELECT * FROM methods m WHERE EXISTS "
        "(SELECT 1 FROM trials t WHERE t.method_id = m.id AND t.window = 'dev') ORDER BY m.id"
    ).fetchall():
        best = store.best_dev_eligible(conn, m["id"])
        if best is None:
            continue
        if m["status"] in ("dev-eligible", "promoted"):
            v = store.verdict(conn, best)
            tail = "  (already pre-registered)" if m["status"] == "promoted" else ""
            ready.append(
                f"    {m['id']:<6} {best['candidate_id']:<28} MAR {fmt_num(best['mar'])}  "
                f"DSR {fmt_num(v.dsr, 3)} at N={v.n} ({v.policy}){tail}"
            )
        else:
            held.append(
                f"    {m['id']:<6} {best['candidate_id']:<28} status {m['status']!r}: "
                f"`lab reevaluate {m['id']}` re-judges it and moves it to dev-eligible"
            )
    out = ["  Promotable now (`lab promote` would take these):"]
    out += ready or ["    (none)"]
    if held:
        out.append("  Eligible on the evidence, held by the status machine:")
        out += held
    return out


def _promotion_path(conn) -> list[str]:
    """The whole promotion-path block: always printed, empty sections included."""
    policy = store.DSR_POLICY
    n = _live_n(conn, policy)
    at = f" at N = {n}" if n is not None else ""
    out = [
        f"Promotion path (dev-eligible -> promoted -> test-passed -> paper), luck bar "
        f"DSR >= {store.DSR_MIN} under policy {policy}{at}:"
    ]
    out += _ratchet_warning(conn, _dev_var(conn))
    out += _promotable_now(conn)
    for title, status, why in _PROMOTION_STATUSES:
        rows = conn.execute(
            "SELECT * FROM methods WHERE status = ? ORDER BY id", (status,)
        ).fetchall()
        if rows:
            out.append(f"  {title} ({len(rows)}) -- {why}:")
            for m in rows:
                out.append(f"    {m['id']} {m['name']} ({m['family']}, {m['source_kind']})")
        else:
            out.append(f"  {title}: (none) -- {_empty_reason(conn, status)}")
    out.append(
        f"  Test-window looks used: {store.test_looks(conn)}. One look per configuration, "
        f"pre-registered before it is spent, and never given back (design §3)."
    )
    return out
```

**Impact:** new code; `_status` calls it in Step 7.

---

### Step 7a: fix `_status`'s luck-label filter (forced by D1)

**File:** `engine/src/seer_engine/commands/lab.py:205-206`

> **Reconciled — the correctness fix itself is phase 4's and has already landed.** Both phases
> independently found the same defect in the same two lines. One owner per file region: **phase 4
> owns it** (its Step 7e), because the rule it delegates to (`store.owner_failures`) is phase 4's
> symbol in phase 4's file, and phase 4 lands first. By the time this phase edits
> `commands/lab.py`, line 205-206 already reads `return list(store.owner_failures(r))`.
>
> **What is left for this phase is a tidy, not a fix:** collapse the local `misses()` closure into
> the module-level `_owner_misses` that this phase's other six call sites already use, so the file
> has one name for one question. If the closure is still there when you arrive, do this; if a
> later refactor has already removed it, skip the step. **Do not re-derive the rule.**

**Change:** the "Closest to eligible" table had two defects, both already corrected in phase 4:
it stripped the luck label by equality with `store.DSR_LABEL` (which no longer matches the 110
recorded `"DSR >= 0.95"` rows), and it read the owner conditions out of the recorded `failed`
string at all (which freezes every row at the old 15% drawdown bar, so `M0020-W-NOSTOP` would
read `misses 1: max DD <= 15%` for ever despite clearing the owner's new 20% bar).

**Code:** replace the closure as phase 4 left it

```python
    def misses(r) -> list[str]:
        return list(store.owner_failures(r))

    for r in sorted(rows, key=lambda r: (len(misses(r)), -r["mar"], r["n"]))[:8]:
```

with the module-level helper (one name for one question — the two are already the same rule)

```python
    for r in sorted(rows, key=lambda r: (len(_owner_misses(r)), -r["mar"], r["n"]))[:8]:
```

and, in the body of that loop, replace the two uses of `misses(r)`

```python
            f"  {r['candidate_id']:<28} misses {len(misses(r))}: {'; '.join(misses(r)) or '-'}  "
```

with

```python
            f"  {r['candidate_id']:<28} misses {len(_owner_misses(r))}: "
            f"{'; '.join(_owner_misses(r)) or '-'}  "
```

**Impact:** none behavioural — `misses(r)` and `_owner_misses(r)` are the same call once phase 4
has landed. What the table *shows* changed in phase 4, and it is worth knowing what to expect:
`M0022-W-TV14` and `M0022-W-TV16` read `misses 0` (their only recorded failure was a luck bar that
has moved), and so does `M0020-W-NOSTOP` (19.3% drawdown, inside the owner's new 20% bar). If any
of the three shows `misses 1`, the delegation is not in place and the table is ranking by a bar
nobody applies.

---

### Step 7b: `_status` prints the promotion path

**File:** `engine/src/seer_engine/commands/lab.py:214-223`

**Change:** the single loop over six statuses splits. Backlog and Blocked keep their "only when
non-empty" behaviour — they are a worklist, and an empty worklist is good news that needs no
sentence. The five promotion statuses move into `_promotion_path`, which always prints.

**Code:** replace lines 214-223

```python
    for title, status in (("Backlog (idea)", "idea"), ("Blocked on data", "blocked-data"),
                          ("Dev-eligible", "dev-eligible"), ("Promoted (pre-registered)", "promoted"),
                          ("Test-passed", "test-passed"), ("Test-failed", "test-failed")):
        rows = conn.execute("SELECT * FROM methods WHERE status = ? ORDER BY id", (status,)).fetchall()
        if rows:
            out.append("")
            out.append(f"{title}:")
            for m in rows:
                extra = f" [needs: {m['blocked_on']}]" if m["blocked_on"] else ""
                out.append(f"  {m['id']} {m['name']} ({m['family']}, {m['source_kind']}){extra}")
```

with

```python
    for title, status in (("Backlog (idea)", "idea"), ("Blocked on data", "blocked-data")):
        rows = conn.execute("SELECT * FROM methods WHERE status = ? ORDER BY id", (status,)).fetchall()
        if rows:
            out.append("")
            out.append(f"{title}:")
            for m in rows:
                extra = f" [needs: {m['blocked_on']}]" if m["blocked_on"] else ""
                out.append(f"  {m['id']} {m['name']} ({m['family']}, {m['source_kind']}){extra}")
    out.append("")
    out += _promotion_path(conn)
```

**Impact:** `lab status`'s output grows a block that always prints, and a `Paper` section the old
loop never had. Nothing is removed: the summary header's `test-window looks used: 0` line, from
`store.summary_rows`, stays where it is — the new budget line restates it inside the promotion
path with the sentence that makes it a budget rather than a counter.

---

### Step 8: the `lab luck` handler

**File:** `engine/src/seer_engine/commands/lab.py`, after Step 6's block and before `_show`

**Code:**

```python
def _luck_rows(
    conn,
    ns: Sequence[int],
    *,
    var_trials: float,
    rank_at: int,
    limit: int,
) -> list[tuple[object, list[float | None]]]:
    """Every dev trial with a recorded DSR, re-evaluated at each N in ``ns``.

    Ranked by the DSR at ``rank_at`` -- the live policy's N -- highest first, ties by trial
    number, so the order is a property of this function and not of the insertion order.

    The 54 P7a seed trials carry ``dsr IS NULL`` by construction (``seed.py``: "P7a reported it
    for one row only") and are skipped. There is nothing to re-evaluate for them, and putting a
    number where the record has none is the opposite of what this command is for.
    """
    scored: list[tuple[object, list[float | None], float]] = []
    for r in conn.execute(
        "SELECT * FROM trials WHERE window = 'dev' AND dsr IS NOT NULL AND sharpe IS NOT NULL "
        "ORDER BY n"
    ).fetchall():
        common = dict(
            sharpe_daily=float(r["sharpe"]) / math.sqrt(252),
            dsr_at_run=float(r["dsr"]),
            n_at_run=int(r["n_trials_at_run"]),
            var_trials=var_trials,
        )
        at = [recover_dsr(n_trials=n, **common) for n in ns]
        rank = recover_dsr(n_trials=rank_at, **common)
        scored.append((r, at, -1.0 if rank is None else rank))
    scored.sort(key=lambda x: (-x[2], int(x[0]["n"])))  # type: ignore[index]
    rows = [(r, at) for r, at, _ in scored]
    return rows if limit <= 0 else rows[:limit]


def _luck(conn, args) -> int:
    """``lab luck``: the dev leaderboard under every N policy, side by side. Read-only.

    It opens no research store, runs no backtest, inserts no row and spends no test-window look.
    That is the point. Decision D1 moved the threshold and deliberately left the N where it was,
    so the second lever is built, measured and *not pulled* -- and this is the instrument that
    shows what pulling it would do, against the committed database, without editing
    ``store.DSR_POLICY`` and re-running anything.

    What it is not: a verdict. The verdict is ``store.verdict``, which recomputes exactly from
    ``trial_moments``. The columns here are recovered from the recorded columns by inverting each
    trial's own per-trial constant at the N it ran at -- so the ``recorded`` column reproduces the
    database exactly and the other columns move only the multiple-testing count.
    """
    live = store.DSR_POLICY
    counts = _n_counts(conn)
    var = _dev_var(conn)
    out: list[str] = [
        "lab luck -- the dev leaderboard under each N policy (read-only: nothing is written)",
        "",
        f"dev trials {store.dev_trial_count(conn)}  ·  test-window looks used "
        f"{store.test_looks(conn)}  ·  luck bar {store.DSR_LABEL}",
        f"live policy: {live}  (store.DSR_POLICY -- changing the N is this one constant)",
        "",
        "The N each policy resolves to, and what clears the bar there:",
    ]
    ns: list[int] = []
    labels: list[str] = []
    for name, count, why in counts:
        mark = "   <- live" if name == live else ""
        if count is None:
            out.append(f"  {name:<12} N = ?      unavailable here: {why}{mark}")
            continue
        n = int(count.n)  # type: ignore[attr-defined]
        if var is None:
            out.append(f"  {name:<12} N = {n:<6d}{mark}")
        else:
            clears = _eligible_at(conn, n, var)
            out.append(
                f"  {name:<12} N = {n:<6d} SR* {sr_star(n, var):.6f}/day   {len(clears)} "
                f"candidate(s) clear {store.DSR_LABEL}{mark}"
            )
            if clears:
                out.append(f"  {'':<12} {', '.join(clears)}")
        out.append(f"  {'':<12} evidence: {_evidence(count)}")
        ns.append(n)
        labels.append(name)
    # --at columns are never deduplicated against a policy that happens to resolve to the same N:
    # the reader asked for a column at a literal N and gets one, labelled by the N.
    extra = [int(n) for n in (args.at or ())]
    for n in extra:
        ns.append(n)
        labels.append(f"N={n}")
    if extra and var is not None:
        out.append("")
        out.append(
            "  at a literal N:  "
            + "  ·  ".join(f"N={n} -> {len(_eligible_at(conn, n, var))} clear" for n in extra)
        )

    if var is None or not ns:
        out += [
            "",
            "No leaderboard: "
            + (
                "fewer than two dev trials carry a Sharpe, so there is no trial-Sharpe variance "
                "to deflate by."
                if var is None
                else "no policy resolved to an N on this database and no --at N was given."
            ),
        ]
        print("\n".join(out))
        return 0

    rank_at = next(
        (int(c.n) for name, c, _ in counts if name == live and c is not None),  # type: ignore[attr-defined]
        ns[0],
    )
    sharpes = len(store.dev_daily_sharpes(conn))
    out += [
        "",
        f"Trial-Sharpe variance now: {var:.6e} (sd {math.sqrt(var):.6f}) over {sharpes} dev "
        f"trials carrying a Sharpe.",
        "",
        f"Dev leaderboard, each recorded DSR re-evaluated at each N, ranked by {live} "
        f"(N={rank_at}).",
        "Trials with no recorded DSR (the P7a seed import) are not listed: there is nothing to "
        "re-evaluate.",
        "",
        "  "
        + f"{'candidate':<28}{'N@run':>7}{'recorded':>10}"
        + "".join(f"{lab:>12}" for lab in labels)
        + "   other failed conditions",
    ]
    for r, at in _luck_rows(conn, ns, var_trials=var, rank_at=rank_at, limit=int(args.limit)):
        others = "; ".join(_owner_misses(r))  # type: ignore[index]
        out.append(
            "  "
            + f"{r['candidate_id']:<28}{int(r['n_trials_at_run']):>7}"  # type: ignore[index]
            + f"{fmt_num(r['dsr'], 3):>10}"  # type: ignore[index]
            + "".join(f"{fmt_num(v, 3):>12}" for v in at)
            + f"   {others or 'none'}"
        )
    out += [
        "",
        f"A cell at or above {store.DSR_MIN} with 'none' in the last column is a candidate that N "
        f"would admit.",
        "The `recorded` column is this same recovery evaluated at each trial's own N@run, so it "
        "reproduces the",
        "database exactly; the other columns move nothing but the multiple-testing count. The "
        "verdict the gate",
        "uses is store.verdict, which recomputes from trial_moments where `lab remeasure` has "
        "recovered them.",
        "",
        "Nothing was written and no test-window look was spent.",
    ]
    print("\n".join(out))
    return 0
```

**Impact:** a new read-only command. No existing behaviour changes.

---

### Step 9: register the handler

**File:** `engine/src/seer_engine/commands/lab.py:621-638`

**Change:** **insert one line** after `"status": _status,`. **Do not replace the dict** — that is
what an earlier draft of this step did, and it would have silently deleted phase 3's
`"remeasure"` and phase 4's `"reevaluate"` keys, both of which are inserted into this same literal
and both of which land before this phase.

**Code:**

```python
    "luck": _luck,
```

so that the literal reads, after all three phases:

```python
_HANDLERS = {
    "status": _status,
    "luck": _luck,              # this phase, read-only
    "show": _show,
    "run": _run,
    "promote": _promote,
    "reevaluate": _reevaluate,  # phase 4, writes
    "test": _test,
    "remeasure": _remeasure,    # phase 3, writes trial_moments only
    "idea": _idea,
    ...
}
```

**Impact:** dispatch. `lab luck` and `lab reevaluate` do not collide — argparse matches subcommand
names exactly — and the owner's rename (Decision **D9**) is what keeps the *pair* legible: one
reads, one writes, and they no longer differ by two characters.

---

### Step 10: `engine/tests/test_lab_luck.py` (new)

**Why the document's table is pinned in a pure test and not against the live database.**
`recover_dsr` takes the trial-Sharpe variance as an argument, and that variance moves every time a
trial lands. The analysis document computed its table at `var = 2.395048e-04`, the variance over
the 110 dev trials on the committed database on 2026-10-07. Asserting the document's numbers
against next month's variance would be asserting a different table. So the document's table — and
D1's and D1b's measured claims, which come from the same arithmetic — are pinned with the
document's variance, and the CLI tests assert that `lab luck` feeds `recover_dsr` the right
columns and writes nothing. Together those are the exit criterion.

**Code:**

```python
"""`lab luck`: the dev leaderboard under each N policy (lab-luck-gate phase 5).

Read-only by construction and by test: `lab luck` opens no research store, runs no backtest,
inserts no row and spends no test-window look.

The numbers here are the analysis document's N-sensitivity table
(`20261007-085606-D3K1_code_analyzer.md`, "What each N would do to the recorded verdicts") plus
the two measured claims the plan index's Decisions D1 and D1b rest on, all at the trial-Sharpe
variance they were computed at. They are pinned to the document rather than to the live database
because the database's variance moves with every trial that lands, and a table at a different
variance is a different table.
"""

from __future__ import annotations

import argparse
import math

import pytest

from seer_engine.backtest import dev
from seer_engine.commands import lab as lab_cmd
from seer_engine.lab import store

# The variance of the 110 dev trials' daily Sharpes on the committed database, 2026-10-07 --
# the analysis document's "var = 2.395e-04, sd 0.01548".
DOC_VAR = 2.395048e-04

# The document's SR*(N) row, daily, at DOC_VAR.
DOC_SR_STAR: tuple[tuple[int, float], ...] = (
    (10, 0.0244), (20, 0.0294), (37, 0.0334), (54, 0.0357), (85, 0.0383),
    (110, 0.0397), (135, 0.0408), (200, 0.0428), (400, 0.0462),
)

# candidate, annualized Sharpe, DSR as recorded, N at run, DSR at N=37, DSR at N=23.
# The last two columns are the document's table; the first three are the recorded columns it was
# computed from.
DOC_TABLE: tuple[tuple[str, float, float, int, float, float], ...] = (
    ("M0022-W-TV16", 0.9451487465911588, 0.9156233536577147, 110, 0.965, 0.978),
    ("M0022-W-TV14", 0.9399457541304774, 0.9122102223368624, 110, 0.963, 0.977),
    ("M0020-W-NOSTOP", 0.9381821396726596, 0.9143575652641522, 107, 0.964, 0.978),
    ("M0007-N20-RAW", 0.9415179650334398, 0.9137573992873155, 85, 0.953, 0.970),
    ("M0019-RAW20-S25", 0.9165875788092439, 0.9004485465260565, 104, 0.956, 0.972),
    ("M0001-TV10", 0.8139921595082781, 0.9034978186707492, 58, 0.937, 0.964),
)

# Every dev trial on the committed database that misses NO owner condition **at the bars in force
# since 2026-10-07** -- DSR >= 0.90 (D1) and max DD <= 20% (D6, phase 8). The luck bar alone
# judges these seven. D1's and D1b's claims are counted over exactly this set.
#
# It is SEVEN, not five: the owner's drawdown change admitted two candidates the 15% bar kept out
# of the pool entirely -- M0020-W-NOSTOP at 19.3% and M0007-N20-RAW at 19.6%. Recomputing this
# table is the first thing to do if either owner-set bar moves again.
#
# (candidate, annualized Sharpe, DSR as recorded, N at run)
LUCK_ONLY: tuple[tuple[str, float, float, int], ...] = (
    ("M0011-RAW20-TV12", 0.8377892220995373, 0.8106495874759774, 90),
    ("M0011-RAW20-TV14-N21", 0.9263098412009216, 0.8974466395413563, 90),
    ("M0019-TV14N21-S20", 0.8853472123958809, 0.8728852717568223, 104),
    ("M0020-W-NOSTOP", 0.9381821396726596, 0.9143575652641522, 107),
    ("M0007-N20-RAW", 0.9415179650334398, 0.9137573992873155, 85),
    ("M0022-W-TV14", 0.9399457541304774, 0.9122102223368624, 110),
    ("M0022-W-TV16", 0.9451487465911588, 0.9156233536577147, 110),
)

OWNER_BAR = 0.90  # Decision D1: the owner's stated risk appetite, 2026-10-07


def _daily(annualized: float) -> float:
    return annualized / math.sqrt(252)


def _at(sharpe: float, dsr: float, n_at: int, n: int) -> float | None:
    return lab_cmd.recover_dsr(
        sharpe_daily=_daily(sharpe), dsr_at_run=dsr, n_at_run=n_at,
        var_trials=DOC_VAR, n_trials=n,
    )


# ------------------------------------------------------------------ the document's arithmetic


def test_sr_star_reproduces_the_documents_hurdle_row():
    for n, expected in DOC_SR_STAR:
        assert round(lab_cmd.sr_star(n, DOC_VAR), 4) == expected


def test_sr_star_rises_with_n():
    """The defect R1 names, as an assertion: every extra look raises the bar."""
    values = [lab_cmd.sr_star(n, DOC_VAR) for n, _ in DOC_SR_STAR]
    assert values == sorted(values)
    assert values[0] < values[-1]


def test_recover_dsr_reproduces_the_analysis_table():
    """The exit criterion: `lab luck`'s arithmetic is the document's table."""
    for candidate, sharpe, dsr, n_at, at37, at23 in DOC_TABLE:
        got37 = _at(sharpe, dsr, n_at, 37)
        got23 = _at(sharpe, dsr, n_at, 23)
        assert got37 is not None and got23 is not None
        assert round(got37, 3) == at37, candidate
        assert round(got23, 3) == at23, candidate


def test_recover_dsr_returns_the_known_value_at_its_own_n_for_any_variance():
    """The identity that makes the `recorded` column a reproduction, not a second estimate --
    and that lets the ratchet warning anchor on `store.verdict`'s own number."""
    for _, sharpe, dsr, n_at, _, _ in DOC_TABLE:
        for var in (1e-6, DOC_VAR, 1e-2):
            got = lab_cmd.recover_dsr(
                sharpe_daily=_daily(sharpe), dsr_at_run=dsr, n_at_run=n_at,
                var_trials=var, n_trials=n_at,
            )
            assert got == pytest.approx(dsr, abs=1e-12)


def test_recover_dsr_falls_monotonically_as_n_rises():
    """What `_sinks_at` bisects on."""
    for _, sharpe, dsr, n_at, _, _ in DOC_TABLE:
        series = [_at(sharpe, dsr, n_at, n) for n in (23, 37, 54, 85, 110, 200, 400)]
        assert series == sorted(series, reverse=True)


@pytest.mark.parametrize(
    "kw",
    [
        dict(n_trials=1),
        dict(n_at_run=1),
        dict(var_trials=0.0),
        dict(var_trials=-1.0),
        dict(dsr_at_run=0.0),
        dict(dsr_at_run=1.0),
        dict(sharpe_daily=float("nan")),
    ],
)
def test_recover_dsr_is_none_where_the_inversion_is_undefined(kw):
    base = dict(sharpe_daily=0.0595, dsr_at_run=0.916, n_at_run=110,
                var_trials=DOC_VAR, n_trials=23)
    base.update(kw)
    assert lab_cmd.recover_dsr(**base) is None


# ------------------------------------------------------------------ D1 and D1b, measured


def test_d1_three_candidates_clear_the_owners_bar_at_the_live_n_and_all_seven_at_n_23():
    """Decisions D1 and D6's evidence, and D1's reason for leaving the N lever alone.

    At the live N of 110 the two owner-set bars admit **three** of the seven luck-only
    candidates — the three highest-MAR books in the lab. Pulling the N lever as well (N = 23)
    would admit **all seven**, including `M0011-RAW20-TV12` at MAR 0.60, which is four more than
    the owner asked for and why `DSR_POLICY` stays at `all-trials`.
    """
    at110 = [c for c, s, d, n in LUCK_ONLY if _at(s, d, n, 110) >= OWNER_BAR]
    at23 = [c for c, s, d, n in LUCK_ONLY if _at(s, d, n, 23) >= OWNER_BAR]
    assert sorted(at110) == ["M0020-W-NOSTOP", "M0022-W-TV14", "M0022-W-TV16"]
    assert len(at23) == len(LUCK_ONLY) == 7


def test_d1_m0007_is_in_the_pool_now_and_still_does_not_clear():
    """The drawdown change let M0007-N20-RAW into the luck-only pool (19.6% <= 20%); the luck
    bar still keeps it out. Recorded 0.914 at its recorded N = 85, **0.898** at today's N = 110 —
    the clearest case in the lab of why a recorded DSR is not a verdict."""
    _, sharpe, dsr, n_at = LUCK_ONLY[4]
    assert LUCK_ONLY[4][0] == "M0007-N20-RAW"
    assert round(dsr, 3) == 0.914                      # as recorded, at N = 85
    assert round(_at(sharpe, dsr, n_at, 110), 3) == 0.898   # re-evaluated at today's N
    assert _at(sharpe, dsr, n_at, 110) < OWNER_BAR


def test_d1_nothing_cleared_the_old_bar_at_the_live_n():
    """The deadlock the plan set was opened on: at (N=110, 0.95) the gate admits nothing."""
    assert [c for c, s, d, n in LUCK_ONLY if _at(s, d, n, 110) >= 0.95] == []


def test_d1b_the_best_candidate_sinks_back_below_the_bar_at_n_143():
    """Decision D1b: the threshold change buys runway, it does not remove the ratchet. The
    warning `lab status` prints has to name this N, and this is the N."""
    name, sharpe, dsr, n_at = LUCK_ONLY[-1]
    assert name == "M0022-W-TV16"
    assert round(_at(sharpe, dsr, n_at, 110), 3) == 0.916
    assert _at(sharpe, dsr, n_at, 142) >= OWNER_BAR
    assert _at(sharpe, dsr, n_at, 143) < OWNER_BAR
    assert round(_at(sharpe, dsr, n_at, 200), 3) == 0.877


# ------------------------------------------------------------------ the historical luck label


def test_owner_misses_is_a_one_line_delegation_and_reads_the_row_not_the_string():
    """There is one rule for "which conditions does this trial miss?", and it is phase 4's.

    The 110 recorded `failed` strings say "DSR >= 0.95" and "max DD <= 15%" and always will; the
    live bars are 0.90 and 20%. A trial at 19.3% drawdown whose record says it missed the old 15%
    bar must read as missing **nothing** — that trial is M0020-W-NOSTOP, and showing it as a
    drawdown failure is the bug this delegation exists to prevent.
    """
    import inspect

    src = inspect.getsource(lab_cmd._owner_misses)
    assert "store.owner_failures" in src
    assert "startswith" not in src and "split" not in src, (
        "_owner_misses must carry no rule of its own: one definition, in store.py"
    )

    row = {
        "total_return": 3.0, "spy_tr_return": 2.0, "max_drawdown": 0.193,
        "profit_factor": 1.6, "trades": 250, "failed": "max DD <= 15%; DSR >= 0.95",
    }
    assert lab_cmd._owner_misses(row) == []          # both recorded bars have moved
    assert lab_cmd._owner_misses({**row, "max_drawdown": 0.247}) == [dev.FAILURE_LABELS[1]]
    assert lab_cmd._owner_misses({**row, "failed": store.OWNER_INPUTS_LABEL}) == [
        store.OWNER_INPUTS_LABEL
    ]  # the one condition carried from the record rather than re-derived


def test_no_owner_condition_label_could_be_mistaken_for_a_luck_label():
    """`store.is_luck_label` is still the display readers' rule, and it is still exact."""
    for label in dev.FAILURE_LABELS:
        assert not store.is_luck_label(label), label
    assert store.is_luck_label("DSR >= 0.95") and store.is_luck_label(store.DSR_LABEL)
    assert store.LUCK_LABEL_PREFIX == "DSR >= "


# ------------------------------------------------------------------ the CLI


def _trial(**kw) -> store.TrialRow:
    base = dict(
        method_id="M0001", candidate_id="M0001-A", config_digest="d1", config_text="t",
        rules_id="MONTHLY_HOLD", allocator_id="TIMING", window="dev", start="1996-01-02",
        end="2015-10-16", store_fingerprint="399d0d25", git_sha="abc123",
        run_at="2026-10-06T00:00:00+00:00", total_return=3.0, cagr=0.12, max_drawdown=0.11,
        profit_factor=1.6, trades=250, sharpe=0.9, exposure=0.95, turnover=1.1, worst_year=2008,
        worst_year_return=-0.1, spy_tr_return=2.0, spy_tr_cagr=0.08, mar=0.8,
        failed="DSR >= 0.95", eligible=False, dsr=0.91, n_trials_at_run=6, curve_json="[]",
    )
    base.update(kw)
    return store.TrialRow(**base)


def _lab(db):
    """A small lab: three methods, six dev trials, varied Sharpes so a variance exists."""
    c = store.connect(db)
    with c:
        for i, mid in enumerate(("M0001", "M0002", "M0003"), start=1):
            store.add_method(c, id=mid, name=f"m{i}", family="f", source_kind="knowledge",
                             hypothesis="h", status="registered")
            store.insert_trials(c, [
                _trial(method_id=mid, candidate_id=f"{mid}-A", config_digest=f"{mid}a",
                       sharpe=0.70 + 0.07 * i, dsr=0.80 + 0.03 * i),
                _trial(method_id=mid, candidate_id=f"{mid}-B", config_digest=f"{mid}b",
                       sharpe=0.55 + 0.05 * i, dsr=0.70 + 0.02 * i,
                       failed="max DD <= 15%; DSR >= 0.95"),
            ])
            store.update_method(c, mid, status="rejected")
    c.close()


def test_lab_luck_prints_a_column_per_policy_and_per_at(tmp_path, capsys):
    db = tmp_path / "lab.sqlite"
    _lab(db)
    args = argparse.Namespace(db=db, lab_command="luck", at=[37, 23], limit=0)
    assert lab_cmd.run(args) == 0
    out = capsys.readouterr().out
    assert "read-only" in out
    assert "N=37" in out and "N=23" in out
    for name in lab_cmd._policies():
        assert name in out
    assert "live policy: " + store.DSR_POLICY in out
    assert "M0001-A" in out and "M0003-B" in out
    assert "clear " + store.DSR_LABEL in out
    assert "Nothing was written" in out


def test_lab_luck_recorded_column_reproduces_the_database(tmp_path, capsys):
    db = tmp_path / "lab.sqlite"
    _lab(db)
    args = argparse.Namespace(db=db, lab_command="luck", at=None, limit=0)
    assert lab_cmd.run(args) == 0
    out = capsys.readouterr().out
    c = store.connect(db)
    recorded = {
        r["candidate_id"]: float(r["dsr"])
        for r in c.execute("SELECT * FROM trials WHERE window = 'dev'")
    }
    c.close()
    seen = 0
    for line in out.splitlines():
        parts = line.split()
        if parts and parts[0] in recorded:
            assert float(parts[2]) == pytest.approx(recorded[parts[0]], abs=5e-4)
            seen += 1
    assert seen == len(recorded)


def test_lab_luck_writes_nothing(tmp_path, capsys):
    db = tmp_path / "lab.sqlite"
    _lab(db)
    before = db.read_bytes()
    args = argparse.Namespace(db=db, lab_command="luck", at=[23], limit=0)
    assert lab_cmd.run(args) == 0
    capsys.readouterr()
    assert db.read_bytes() == before
    c = store.connect(db)
    assert store.test_looks(c) == 0
    c.close()


def test_lab_luck_on_an_empty_lab_says_so_instead_of_failing(tmp_path, capsys):
    db = tmp_path / "lab.sqlite"
    store.connect(db).close()
    args = argparse.Namespace(db=db, lab_command="luck", at=None, limit=0)
    assert lab_cmd.run(args) == 0
    assert "No leaderboard" in capsys.readouterr().out


def test_at_refuses_an_n_the_deflated_sharpe_is_undefined_at():
    with pytest.raises(argparse.ArgumentTypeError):
        lab_cmd._positive_n("1")
    assert lab_cmd._positive_n("23") == 23
```

> Reconciled: the dead placeholder line that stood at the top of
> `test_d1b_the_best_candidate_sinks_back_below_the_bar_at_n_143` was a drafting artefact and has
> been removed from the code above. The test is `name, sharpe, dsr, n_at = LUCK_ONLY[4]` and the
> four assertions, as written.

**Impact:** new tests.

---

### Step 11: `engine/tests/test_lab_status.py` (new)

**Code:**

```python
"""`lab status`'s promotion path, look budget and ratchet warning (lab-luck-gate phase 5).

Every test builds its own temp lab. The real one's state changes with every Sera batch and these
tests must keep passing through all of them -- so nothing here asserts a count the committed
database happens to have.

The recorded `failed` strings in these fixtures deliberately say "DSR >= 0.95", the text the 110
append-only rows carry, while `store.DSR_LABEL` now reads "DSR >= 0.90". That mismatch is the
hazard Decision D1 created and `_owner_misses` exists to handle.
"""

from __future__ import annotations

import argparse
import shutil

import pytest

from seer_engine.commands import lab as lab_cmd
from seer_engine.lab import store

OLD_LUCK_LABEL = "DSR >= 0.95"  # what the append-only rows say, forever


@pytest.fixture()
def status(capsys):
    def go(db) -> str:
        args = argparse.Namespace(db=db, lab_command="status")
        assert lab_cmd.run(args) == 0
        return capsys.readouterr().out

    return go


def _trial(**kw) -> store.TrialRow:
    base = dict(
        method_id="M0001", candidate_id="M0001-A", config_digest="d1", config_text="t",
        rules_id="MONTHLY_HOLD", allocator_id="TIMING", window="dev", start="1996-01-02",
        end="2015-10-16", store_fingerprint="399d0d25", git_sha="abc123",
        run_at="2026-10-06T00:00:00+00:00", total_return=3.0, cagr=0.12, max_drawdown=0.11,
        profit_factor=1.6, trades=250, sharpe=0.9, exposure=0.95, turnover=1.1, worst_year=2008,
        worst_year_return=-0.1, spy_tr_return=2.0, spy_tr_cagr=0.08, mar=0.8, failed="",
        eligible=True, dsr=0.97, n_trials_at_run=2, curve_json="[]",
    )
    base.update(kw)
    return store.TrialRow(**base)


# `n_trials_at_run=2` is load-bearing in this file, not arbitrary. Phase 4's `store.verdict`
# re-evaluates every recorded DSR **at the gate's current N**; these fixtures hold two dev trials,
# so the gate resolves to N = 2 under `all-trials` and the re-evaluation is the identity. Give a
# fixture a different N and its DSR moves under the assertions — which is exactly the behaviour
# the gate is supposed to have, and exactly what makes a fixture that forgets it confusing.


def _method(c, mid: str, *, status: str, trials) -> None:
    """A method at ``status`` with ``trials`` recorded, walked along TRANSITIONS."""
    path = {
        "registered": ("registered",),
        "rejected": ("registered", "rejected"),
        "dev-eligible": ("registered", "dev-eligible"),
    }[status]
    with c:
        store.add_method(c, id=mid, name=f"name {mid}", family="fam",
                         source_kind="knowledge", hypothesis="h")
        store.insert_trials(c, list(trials))
        for s in path:
            store.update_method(c, mid, status=s)


# ------------------------------------------------------------------ the path prints when empty


def test_an_empty_promotion_path_still_prints_every_section(tmp_path, status):
    """R3 in one assertion: a lab in which `lab promote` and `lab test` are both unreachable
    says so, instead of printing nothing at all about the promotion path."""
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _method(c, "M0001", status="rejected", trials=[
        _trial(method_id="M0001", candidate_id="M0001-A", config_digest="a",
               failed=OLD_LUCK_LABEL, eligible=False, dsr=0.80),
        _trial(method_id="M0001", candidate_id="M0001-B", config_digest="b", sharpe=0.7,
               failed=f"max DD <= 15%; {OLD_LUCK_LABEL}", eligible=False, dsr=0.70),
    ])
    c.close()
    out = status(db)
    assert "Promotion path" in out
    for title in ("Dev-eligible", "Promoted (pre-registered)", "Test-passed", "Test-failed",
                  "Paper"):
        assert f"{title}: (none)" in out
    assert "Promotable now" in out
    assert "Test-window looks used: 0" in out
    assert "never given back" in out


def test_the_empty_dev_eligible_section_names_the_closest_candidate_and_the_bar(tmp_path, status):
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _method(c, "M0001", status="rejected", trials=[
        _trial(method_id="M0001", candidate_id="M0001-A", config_digest="a",
               failed=OLD_LUCK_LABEL, eligible=False, dsr=0.88),
        _trial(method_id="M0001", candidate_id="M0001-B", config_digest="b", sharpe=0.7, mar=0.7,
               failed=OLD_LUCK_LABEL, eligible=False, dsr=0.70),
    ])
    c.close()
    out = status(db)
    assert "held by the luck bar alone" in out
    assert "M0001-A" in out            # the closest, not the other one
    assert str(store.DSR_MIN) in out
    assert "lab luck" in out


def test_a_candidate_that_misses_an_owner_condition_is_named_as_unrescuable(tmp_path, status):
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _method(c, "M0001", status="rejected", trials=[
        _trial(method_id="M0001", candidate_id="M0001-A", config_digest="a",
               failed=f"max DD <= 15%; {OLD_LUCK_LABEL}", eligible=False, dsr=0.99),
    ])
    c.close()
    out = status(db)
    assert "none passes the five go-live conditions" in out
    assert "max DD <= 15%" in out
    assert "can rescue" in out


def test_a_historical_luck_label_is_not_read_as_an_owner_condition(tmp_path, status):
    """Decision D1's hazard: `store.DSR_LABEL` reads "DSR >= 0.90" while every recorded row says
    "DSR >= 0.95". A trial that missed only the old luck bar must still count as passing all five
    owner conditions, in the reason sentence and in the Closest-to-eligible table."""
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _method(c, "M0001", status="rejected", trials=[
        _trial(method_id="M0001", candidate_id="M0001-A", config_digest="a",
               failed=OLD_LUCK_LABEL, eligible=False, dsr=0.88),
    ])
    c.close()
    out = status(db)
    assert "held by the luck bar alone" in out
    assert "M0001-A" in out
    assert "misses 0" in out        # the Closest-to-eligible table agrees
    assert OLD_LUCK_LABEL not in out.split("Closest to eligible")[1].split("Promotion path")[0]


def test_an_empty_lab_says_nothing_has_run(tmp_path, status):
    db = tmp_path / "lab.sqlite"
    store.connect(db).close()
    out = status(db)
    assert "no method has run on the dev window yet" in out
    assert "Test-window looks used: 0" in out


# ------------------------------------------------------------------ promotable now


def test_promotable_now_lists_what_lab_promote_would_take(tmp_path, status):
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _method(c, "M0001", status="dev-eligible", trials=[
        _trial(method_id="M0001", candidate_id="M0001-A", config_digest="a", mar=0.9),
        _trial(method_id="M0001", candidate_id="M0001-B", config_digest="b", mar=0.5),
    ])
    c.close()
    out = status(db)
    block = out.split("Promotable now")[1]
    assert "M0001-A" in block          # best by MAR, the one `lab promote` pre-registers
    assert "Dev-eligible (1)" in out


def test_a_derived_eligible_method_still_rejected_is_named_as_held(tmp_path, status):
    """`lab promote` refuses a rejected method however good its trial is, and the status says
    which command moves it rather than leaving the reader to guess."""
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _method(c, "M0001", status="rejected", trials=[
        _trial(method_id="M0001", candidate_id="M0001-A", config_digest="a", mar=0.9),
    ])
    c.close()
    out = status(db)
    assert "held by the status machine" in out
    assert "'rejected'" in out
    assert "lab reevaluate M0001" in out   # the command that actually moves it, not `lab run`


# ------------------------------------------------------------------ D1b: the ratchet warning


def _near_the_bar(c) -> None:
    """A lab whose best luck-only candidate clears the bar by less than `_WARN_MARGIN`.

    Two trials so there is a Sharpe variance to deflate by, and `n_trials_at_run=2` so the gate's
    N is the trial's own N and `store.dsr_at` returns the recorded number unchanged — the
    identity `recover_dsr` rests on. The warning then has a DSR of exactly `DSR_MIN + 0.01` to
    reason about, which is what makes these assertions deterministic.
    """
    _method(c, "M0001", status="dev-eligible", trials=[
        _trial(method_id="M0001", candidate_id="M0001-A", config_digest="a", sharpe=0.95,
               mar=0.9, failed="", eligible=True,
               dsr=store.DSR_MIN + 0.01, n_trials_at_run=2),
        _trial(method_id="M0001", candidate_id="M0001-B", config_digest="b", sharpe=0.40,
               mar=0.4, failed=f"max DD <= 15%; {OLD_LUCK_LABEL}", eligible=False,
               dsr=0.55, n_trials_at_run=2),
    ])


def test_the_ratchet_warning_fires_and_names_the_n_that_sinks_the_candidate(tmp_path, status):
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _near_the_bar(c)
    c.close()
    out = status(db)
    assert "The luck bar is close" in out
    assert "M0001-A" in out
    assert "of margin" in out
    assert "falls below the bar at N =" in out
    assert "more dev trials" in out
    assert "lab luck" in out


def test_the_ratchet_warning_is_silent_when_the_margin_is_comfortable(tmp_path, status):
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _method(c, "M0001", status="dev-eligible", trials=[
        _trial(method_id="M0001", candidate_id="M0001-A", config_digest="a", sharpe=0.95,
               mar=0.9, failed="", eligible=True, dsr=0.999, n_trials_at_run=2),
        _trial(method_id="M0001", candidate_id="M0001-B", config_digest="b", sharpe=0.40,
               mar=0.4, failed=f"max DD <= 15%; {OLD_LUCK_LABEL}", eligible=False,
               dsr=0.55, n_trials_at_run=2),
    ])
    c.close()
    assert "The luck bar is close" not in status(db)


def test_the_ratchet_warning_is_silent_when_nothing_is_above_the_bar(tmp_path, status):
    """Below the bar, the empty Dev-eligible section is already the sentence; a second one would
    be noise."""
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _method(c, "M0001", status="rejected", trials=[
        _trial(method_id="M0001", candidate_id="M0001-A", config_digest="a", sharpe=0.95,
               mar=0.9, failed=OLD_LUCK_LABEL, eligible=False, dsr=0.70, n_trials_at_run=2),
        _trial(method_id="M0001", candidate_id="M0001-B", config_digest="b", sharpe=0.40,
               mar=0.4, failed=f"max DD <= 15%; {OLD_LUCK_LABEL}", eligible=False,
               dsr=0.55, n_trials_at_run=2),
    ])
    c.close()
    out = status(db)
    assert "The luck bar is close" not in out
    assert "held by the luck bar alone" in out


def test_sinks_at_finds_the_first_n_below_the_bar(tmp_path):
    """The bisection, directly: the N it returns is below the bar and the one before it is not."""
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _near_the_bar(c)
    found = lab_cmd._best_luck_only(c)
    assert found is not None
    trial, v = found
    var = lab_cmd._dev_var(c)
    n = lab_cmd._sinks_at(c, trial, v, var)
    c.close()
    assert n is not None and n > int(v.n)
    common = dict(sharpe_daily=float(trial["sharpe"]) / (252 ** 0.5),
                  dsr_at_run=float(v.dsr), n_at_run=int(v.n), var_trials=var)
    assert lab_cmd.recover_dsr(n_trials=n, **common) < store.DSR_MIN
    assert lab_cmd.recover_dsr(n_trials=n - 1, **common) >= store.DSR_MIN


# ------------------------------------------------------------------ the committed database


@pytest.mark.skipif(not store.COMMITTED_DB.is_file(), reason="no committed lab database here")
def test_status_runs_on_a_copy_of_the_committed_database(tmp_path, status):
    """The real shape, on the real data, without touching the committed file."""
    db = tmp_path / "lab.sqlite"
    shutil.copy(store.COMMITTED_DB, db)
    out = status(db)
    assert "Promotion path" in out
    assert "Promotable now" in out
    assert "Test-window looks used: 0" in out
    c = store.connect(db)
    assert store.test_looks(c) == 0
    c.close()
```

**Impact:** new tests. The `_near_the_bar` fixture depends on `recover_dsr`'s identity — at
`n_trials == n_at_run` the recorded DSR comes back unchanged, for any variance — which is what
makes these assertions deterministic without building a `trial_moments` row by hand. Reconciled:
an earlier draft of this phase leaned on a "falls back to the recorded columns" case in phase 4's
`verdict`; that case no longer exists (Decision **D11**), and these fixtures are aligned to the
identity instead, which is the more robust footing anyway.

---

## Verification

**Build (import and CLI wiring):**

```
cd /home/miftah/.worktrees/seer/lab-luck-gate/engine && \
  PYTHONPATH=src /home/miftah/seer/engine/.venv/bin/python -c \
  "from seer_engine.commands import lab; print(sorted(lab._HANDLERS))"
```

**Tests:**

```
cd /home/miftah/.worktrees/seer/lab-luck-gate/engine && \
  PYTHONPATH=src /home/miftah/seer/engine/.venv/bin/python -m pytest \
  tests/test_lab_status.py tests/test_lab_luck.py tests/test_lab_store.py \
  tests/test_lab_prereg.py tests/test_lab_runner.py tests/test_lab_snapshot.py \
  tests/test_lab_test_window.py tests/test_cli.py -q
```

then the whole suite:

```
cd /home/miftah/.worktrees/seer/lab-luck-gate/engine && \
  PYTHONPATH=src /home/miftah/seer/engine/.venv/bin/python -m pytest -q
```

**Manual check** (read-only; both commands write nothing, so running them against the committed
database is safe and is the point):

```
cd /home/miftah/.worktrees/seer/lab-luck-gate/engine && \
  PYTHONPATH=src SEER_LAB_DB=/home/miftah/.worktrees/seer/lab-luck-gate/lab/lab.sqlite \
  /home/miftah/seer/engine/.venv/bin/python -m seer_engine lab status | sed -n '/Promotion path/,$p'

cd /home/miftah/.worktrees/seer/lab-luck-gate/engine && \
  PYTHONPATH=src SEER_LAB_DB=/home/miftah/.worktrees/seer/lab-luck-gate/lab/lab.sqlite \
  /home/miftah/seer/engine/.venv/bin/python -m seer_engine lab luck --at 37 --at 23 --limit 0
```

Then `git status --porcelain lab/lab.sqlite` must be empty: neither command may have written.

**What to look for, with phases 1-4 and 8 landed** (`DSR_MIN` 0.90, `DSR_POLICY` `all-trials`,
`tuning.MAX_DRAWDOWN` 0.20):

`lab status` —
- `Promotion path ... luck bar DSR >= 0.9 under policy all-trials at N = 110:`
- the ratchet warning fires on **`M0022-W-TV16`** — `_best_luck_only` ranks by **DSR**, and
  W-TV16's 0.916 is the highest: `DSR 0.916 against a 0.9 bar -- 0.016 of margin at N = 110`,
  `falls below the bar at N = 143: 33 more dev trials`
- `Promotable now` lists **two** methods: `M0022` with **`M0022-W-TV14`** and `M0020` with
  `M0020-W-NOSTOP`. **W-TV14, not W-TV16** — `_promotable_now` reads `store.best_dev_eligible`,
  which ranks by **MAR** (0.857 against 0.816), not by DSR. The two sections rank by different
  things on purpose and will name different variants of the same method; that is correct.
- `Dev-eligible (2)` lists M0020 and M0022
- `Test-window looks used: 0.`
- the `Closest to eligible` table shows `M0022-W-TV14`, `M0022-W-TV16` **and `M0020-W-NOSTOP`** at
  `misses 0` — **not** `misses 1` (that would be the `_owner_misses` delegation regressing, and
  for M0020 it would mean the recorded `max DD <= 15%` is still being read as a live condition)

`lab luck --at 37 --at 23` — **note that `_eligible_at` counts candidates clearing the *luck*
bar at that N **among those missing no owner condition at today's bars**, so M0020-W-NOSTOP and
M0007-N20-RAW now enter the pool that the old 15% drawdown bar kept out:
- `all-trials N = 110 ... 3 candidate(s) clear DSR >= 0.90`, naming M0022-W-TV14, M0022-W-TV16
  and M0020-W-NOSTOP. (M0007-N20-RAW is in the pool and does **not** clear: 0.898 at N = 110.)
- `methods N = 23 ... ` more again — every luck-only candidate clears at N = 23
- `at a literal N:  N=37 -> 4 clear  ·  N=23 -> 5 clear`
- the `N=37` / `N=23` columns carry 0.965 / 0.978 for `M0022-W-TV16`, 0.963 / 0.977 for
  `M0022-W-TV14`, 0.964 / 0.978 for `M0020-W-NOSTOP`, 0.953 / 0.970 for `M0007-N20-RAW`,
  0.956 / 0.972 for `M0019-RAW20-S25` and 0.937 / 0.964 for `M0001-TV10` — the analysis
  document's table to the last digit it prints. (These hold while the dev Sharpes' variance is
  still 2.395e-04; the `recorded` column reproduces the database exactly whatever it becomes.)

**Exit criteria:**

1. `lab status` on a lab with nothing promotable prints the promotion path with every section
   present, each empty one carrying the reason it is empty, and `Promotable now` reading `(none)`.
2. The `Dev-eligible: (none)` reason names the closest candidate, its derived DSR, the bar, and
   the N and policy the derivation used — built from the data.
3. `Test-window looks used: 0` prints inside the promotion path, with the one-look sentence, on
   every run.
4. After phase 4's re-evaluation, `lab status` lists **M0022 and M0020** under both
   `Promotable now` and `Dev-eligible` — M0022 with `M0022-W-TV14` (MAR decides, not DSR) and
   M0020 with `M0020-W-NOSTOP`.
5. **D1b:** the ratchet warning fires whenever the best luck-only candidate clears the bar by
   `<= 0.03`, names the N at which it falls below and how many more dev trials that is, and is
   silent otherwise. Every number in it comes from `store.verdict`, `npolicy` and `trials.run_at`;
   none is written down.
6. **D1:** `lab luck` prints, per named policy, the N it resolves to, its evidence and how many
   candidates clear the bar there — **three** at N=110 and **seven** at N=23 on the committed
   database, over the luck-only pool as the owner's two bars now define it. `recover_dsr`
   reproduces the analysis document's table and its SR\* row.
7. **Neither a recorded `"DSR >= 0.95"` nor a recorded `"max DD <= 15%"` is ever read as a live
   missed condition** anywhere in `lab status` or `lab luck`. `_owner_misses` is a one-line
   delegation to `store.owner_failures` and carries no rule of its own
   (`test_owner_misses_is_a_one_line_delegation_and_reads_the_row_not_the_string`).
8. `lab/lab.sqlite` is byte-identical before and after running both commands; `store.test_looks`
   reads 0; `pytest` is green in `engine/`.

---

## Handoffs

- **The historical-label hazard — settled, and settled harder than this phase proposed.** This
  phase found it and proposed a shared prefix rule. The reconciled answer went further: phase 4's
  `store.verdict` no longer parses the recorded `failed` string for conditions **at all**. It
  re-derives the four threshold conditions from the row's own numeric columns against the live
  constants and carries only `owner inputs`. That was forced by the owner's second change of the
  same day — `tuning.MAX_DRAWDOWN` 0.15 → 0.20 (D6, phase 8) — which gave the drawdown label the
  same staleness the luck label had, on rows where it matters: `M0020-W-NOSTOP` at 19.3%.
  `store.is_luck_label` and `store.LUCK_LABEL_PREFIX` survive for the three readers that display
  recorded history (this phase, phase 7's `derive.ts`, and `lab reevaluate`'s refusal text).
  **Nothing in this phase carries a rule of its own any more.**
- **`sr_star` / `recover_dsr` — settled, and they did not stay here.** This phase drafted them in
  `commands/lab.py` because `lab/store.py` belonged to phases 2 and 4, and noted that lab-domain
  arithmetic in a CLI module is half an altitude off. The reconciliation moved them: phase 4
  needed the same inversion for `store.dsr_at` (the gate re-evaluates every recorded DSR at the
  current N), so they are defined once in `lab/store.py` and re-exported here. The follow-up this
  handoff anticipated has already happened.
- **`lab luck` does not read `trial_moments`.** Where `lab remeasure` (phase 3) has recovered a
  trial's moments an exact recomputation is possible with no inversion at all. `lab luck`
  deliberately does not use it: the inversion works uniformly on every recorded trial including
  the ones never remeasured, and a table whose rows switched methods depending on what had been
  remeasured would be a worse table. A later phase could add an exactness marker per row.
- **`store.summary_rows`'s "dev trials (N for the DSR)" label** is correct today (D1 leaves
  `DSR_POLICY` at `all-trials`) but becomes wrong the moment the N lever is pulled. It lives in
  `lab/store.py`, phase 4's file, and `lab export`'s summary sheet reads the same function.
  Flagged; not touched here.
- **The web snapshot and the sera site** gain none of this. `store.snapshot`'s `gate` block and
  `web/app/sera/overview.ts` are phase 7's, as is teaching `SKILL.md` to print `lab luck` after
  a Sera batch — which is where the D1b warning would do the most good, and is phase 7's wording
  to add, not this phase's.

---

## Rollback

One commit, purely additive to behaviour. `git revert <sha>` restores `_status`'s single section
loop and its inline `misses()`, removes the `lab luck` subcommand and deletes the two test files.
Nothing else in the set reads anything this phase creates: phases 6 and 7 do not import
`commands/lab.py`, and phases 1-4 are upstream of it. No data is written by this phase, so there
is nothing to undo in `lab/lab.sqlite` — the revert is code only, and `git status` on the database
stays clean through both the apply and the revert.

**One caveat on reverting alone:** Step 7a's `misses()` fix is a correctness dependency on phase
4's `DSR_MIN = 0.90`. Reverting this phase while phase 4 stays landed restores the bug —
`lab status`'s "Closest to eligible" table would read every recorded `"DSR >= 0.95"` as a missed
owner condition and rank by noise. If this phase has to be reverted on its own, cherry-pick Step
7a back, or revert phase 4 with it.

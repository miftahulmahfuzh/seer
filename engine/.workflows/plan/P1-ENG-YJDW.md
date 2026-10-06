> Adopted from `BUILD_PROMOTION_PATH_PLAN.md` phase 4. Source: `.workflows/plan/build-promotion-path/phase-4.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 4: `lab test` — one counted look, recorded and final

**Plan set:** `BUILD_PROMOTION_PATH_PLAN.md`
**Analysis:** `20261006-115723-B7K2_code_analyzer.md`
**Satisfies:** R2 — `lab test <candidate>` refuses without a committed pre-registration, runs once,
records a `test` trial, and sets `test-passed` / `test-failed`
**Depends on:** Phase 2 (which depends on Phase 1), Phase 3
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/lab` (with the CLI surface in `engine/src/seer_engine/commands/lab.py`)

---

## Interfaces from Phases 1, 2 and 3 (final, reconciled 2026-10-06)

This plan was drafted before `phase-1.md`, `phase-2.md` and `phase-3.md` existed on disk, against
assumed names. The reconciler has read all three and **rewritten this section and every call site
below to the real contracts.** Nothing here is an assumption any more; where this phase's draft
disagreed with an owning phase, this phase was changed, never the owner.

### From Phase 1 — `seer_engine.backtest.window` and `seer_engine.backtest.dev`

| What exists | Used by me at |
|---|---|
| `seer_engine.backtest.window.Window` — frozen, fields in order `name: str` (`"dev"`/`"test"`), `start: date`, `end: date`; `.covers(d)`, `.following(name, end)` | `tests/labkit.py`, `tests/test_lab_test_window.py`. **Import it from `seer_engine.backtest.window`, not through `dev`** — `dev.py` re-exports it only incidentally. |
| `dev.DEV_WINDOW = Window(name="dev", start=date.min, end=DEV_END)` | not called directly; it is the **default** everywhere, which is what keeps `lab run` unchanged (invariant 4) |
| `dev.run_registry(market, dividends, spy_dividends, registry, *, on_result=None, window: Window = DEV_WINDOW)` | `runner.run_test`. `run_candidate` is **not** used (see Step 5 rationale). |
| `dev.make_row(candidate, start, end, stats, *, spy_tr, spy_price, window: Window = DEV_WINDOW)` | `tests/test_lab_test_window.py` only |
| `DevRow.window: Window = DEV_WINDOW`, appended last and defaulted; `__post_init__` validates with `check_dev_session(self.end, self.window)` and floors `start` at `self.window.start` | `runner.test_trial_row` reads `row.start` / `row.end`; the `window` field is why a test row can exist at all |

**The hard dependency is satisfied.** The draft flagged `DevRow.__post_init__`'s
`check_dev_session(self.end)` (`dev.py:280`) as a hard blocker — with the dev window in force it
refuses every test row, so no test trial could be constructed. **Verified against `phase-1.md`
Step 5:** phase 1 appends the `window` field *and* changes that line to
`check_dev_session(self.end, self.window)`, and adds a `start < self.window.start` floor. This
phase needs no change to `backtest/dev.py` and makes none.

`dev.make_row`'s five D8 conditions are **window-independent** (they read `tuning` thresholds and
`candidate_owner_inputs`), so `row.failed` / `row.eligible` mean the same thing on the test window
as on dev. That is what makes the verdict a one-liner in Step 4.

### From Phase 2 — `seer_engine.research`

| What exists | Used by me at |
|---|---|
| `research.TEST_STORE_DIR = config.REPO_ROOT / "engine" / ".research-test"` | `commands/lab.py` `--store` default |
| `research.declared_window(store_dir) -> Window` — reads `manifest.json` alone, verifies nothing, answers "which window is this store for?". No window keys means `DEV_WINDOW`. | `commands/lab.py:_test` |
| `research.load_store(store_dir, *, data_dir=None, window: Window = DEV_WINDOW)` — `window` is a **`Window` value, not a name string**, and `_read_manifest` raises `ValueError` before any data file is read when the store declares a different one | `commands/lab.py:_test` |
| `research.ResearchData.window: Window = DEV_WINDOW` — the window the loaded store was built for, defaulted so every existing `ResearchData(...)` construction (`labkit.smoke_data` at `labkit.py:52` included) keeps working | `runner.run_test`, `tests/labkit.py` |
| `python -m seer_engine research_store --test-window [--window-end YYYY-MM-DD]` builds it | three refusal messages, text only |

**Three names corrected from the draft.** The build flag is `--test-window`, not `--test`;
`load_store`'s `window=` takes a `Window`, not `"test"`; and the expectation is expressed by
reading `declared_window(store_dir)` and passing it back in. Phase 2's own Interface Contract
spells the idiom out, and Step 7 below now uses it verbatim.

**And the draft's open question is answered.** Phase 2 carries a **coordinator decision**: the
test store holds `research.STORE_START` (1993-01-29) through the latest available session — it is
**not** truncated to 2015-10-19. The window's `start` bounds what is traded and scored; the store
carries the run-up a candidate's lookback needs, exactly as the dev store does. So a 200-session
candidate's one look opens on 2015-10-19, not ten months late. Nothing in this phase changes
either way; the question is settled and is no longer a handoff.

### From Phase 3 — `seer_engine.lab.prereg`

| What exists | Used by me at |
|---|---|
| module `seer_engine.lab.prereg`; `prereg.PreregError(store.LabError)` → `commands/lab.py:run` already returns exit 2 | `runner.preflight_test` |
| **`prereg.require_committed(candidate_id: str, *, directory: Path \| None = None) -> Prereg`** — takes the **candidate** id, not the method id; raises when the id is not `MNNNN-SUFFIX`, the file is missing / untracked / staged-only / modified, does not parse, or names another method or another candidate | `runner.preflight_test` |
| **`prereg.check_digest(p, digest, *, directory=None) -> None`** — a **separate** call; raises when the live configuration drifted from the pre-registered one | `runner.preflight_test` |
| `prereg.Prereg` — frozen, **every field a `str`**: `method`, `candidate`, `config_digest`, `rules_id`, `allocator_id`, `dev_trial`, `dev_window`, `test_window`, `gate`, `mar`, `dsr`, `n_trials_at_run`, `store_fingerprint`, `git_sha`, `date` | `runner.preflight_test`, `commands/lab.py:_test_plan` |
| `prereg.path_for(method_id, directory=None) -> Path` | `commands/lab.py:_test_plan` |

**Four corrections from the draft, all of them this phase's to absorb.** There is no
`prereg.read_committed`; there is no `require_commit=` parameter on anything in `prereg`; the
field is `p.candidate`, **not** `p.candidate_id`; and `Prereg` has **no `.path`** — the path is
`prereg.path_for(p.method)`. Two checks the draft wrote itself are now phase 3's and are deleted
here rather than duplicated: the candidate-id comparison lives inside `require_committed`, and the
digest comparison is `check_digest`.

**How the in-transaction re-check works without a `require_commit` flag.** `require_committed`
shells out to git and must run once, up front. `preflight_test` therefore takes an optional
`pre: Prereg | None`: when it is given, the already-read, already-git-verified pre-registration is
re-used and only `check_digest` plus the two database refusals run again inside the write lock.
That is exactly what the draft wanted `require_commit=False` for, with no change to phase 3.

---

## Goal

After this phase a pre-registered, promoted lab method can spend its single out-of-sample look:
`python -m seer_engine lab test M0007-RESID` refuses a method that is not `promoted`, refuses one
with no committed pre-registration, refuses a second look, and otherwise runs the pre-registered
variant once on the test-window store, appends exactly one `trials` row with `window='test'`, and
moves the method to `test-passed` or `test-failed` — both final. The lab's multiple-testing count N
does not move: `store.dev_trial_count` stays dev-only, so every recorded dev trial stays
reproducible and every future dev DSR is deflated by exactly the N it would have had if this look
had never happened.

---

## Interface Contract

**Deletes:** nothing.

**Renames:** nothing.

**Creates:**
- `seer_engine.lab.runner.Tested` (`lab/runner.py`) — frozen dataclass `(trial, row, status)`
- `seer_engine.lab.runner.resolve_candidate(candidate_id) -> (Method, Path, Candidate)` (`lab/runner.py`)
- `seer_engine.lab.runner.preflight_test(conn, method, path, candidate, *, pre: prereg.Prereg | None = None, require_commit: bool = True) -> prereg.Prereg` (`lab/runner.py`)
- `seer_engine.lab.runner.test_trial_row(conn, method, row, curve, *, fingerprint, git_sha) -> store.TrialRow` (`lab/runner.py`)
- `seer_engine.lab.runner.run_test(conn, method, path, candidate, data, *, git_sha, require_commit=True) -> Tested` (`lab/runner.py`)
- CLI subcommand `lab test <candidate> [--store DIR] [--roster-id ID] [--dry-run]` (`commands/lab.py`)
- `commands.lab._test`, `_test_plan`, `_gate_note`, `_promote_argv`, `_verdict_report` (`commands/lab.py`)
- `tests.labkit.smoke_test_window`, `smoke_test_market`, `smoke_test_data` (`tests/labkit.py`)
- `engine/tests/test_lab_test_window.py` (new file)

**Signature changes:** none to any existing function. `runner.run_method`, `runner.preflight`,
`runner.trial_rows`, `runner.preflight_data` and `runner._dsr` are **not touched** — `lab run` must
stay byte-identical (plan invariant 4).

**Requires (from earlier phases):** everything in **Interfaces from Phases 1, 2 and 3** above —
all three verified present in the owning plans. In particular `DevRow` accepts a test-window
`end` (Phase 1 Step 5), `ResearchData` carries `window` (Phase 2 Step 2), and `lab.prereg`
exposes `require_committed` + `check_digest` (Phase 3 Step 2).

**Depends-on ordering, enforced:** this phase runs after **2 and 3**, so every file it shares
with them is quoted in its post-phase state, not as it stands at `2d03fd1`.

**Leaves alone (owned by others):**
- `engine/src/seer_engine/backtest/dev.py` — Phase 1
- `engine/src/seer_engine/research.py`, `engine/src/seer_engine/commands/research_store.py`,
  `.gitignore` — Phase 2
- `engine/src/seer_engine/lab/prereg.py`, `docs/lab/prereg/*`, the `lab promote` subcommand,
  `tests/test_lab_prereg.py` — Phase 3
- `engine/src/seer_engine/lab/store.py` — **no schema change, no migration.** `WINDOWS`,
  `UNIQUE(config_digest, window)`, the append-only triggers, `has_trial`, `insert_trials`,
  `test_looks`, `dev_trial_count`, `record_promotion` all already exist and are consumed as-is.
- `engine/src/seer_engine/commands/promote.py` and `lab.store.record_promotion` — consumed, never
  rebuilt
- `engine/src/seer_engine/fundamentals/coverage.py` and `tests/test_fundamentals_coverage.py` — the
  `DEV_END` equality pin at `:107` is untouched
- `lab/lab.sqlite`, `web/data/lab.json` — **never written or committed by this phase**

**Shared files, resolved by the reconciler (2026-10-06):**

1. `.claude/skills/explore-and-experiment-new-method/SKILL.md` — **this phase is the sole owner**
   of its `## Promotion` section (`:123`–`:143`). Phase 3 deliberately touches no skill file, so
   there is no merge: Step 10 replaces the whole section, including the `lab promote` step phase
   3's command makes possible and the now-false "if `lab test` and the test-window store don't
   exist yet, build them first". Documenting `lab promote` there is **R2** work, not R3:
   `lab test` *refuses* without a committed pre-registration, so an agent never told how to
   produce one has a `lab test` that cannot run. This phase's **Satisfies** stays R2.
2. `engine/src/seer_engine/commands/lab.py` — **phase 3 lands first** and adds the `promote`
   subparser, the `_promote` handler and the `"promote": _promote,` dispatch entry. Steps 6 and 7
   below are written against that post-phase-3 file: the anchors are `promote`'s own blocks, not
   `run`'s, and line numbers from `2d03fd1` are no longer valid past `:78`.
3. `engine/tests/test_research_store.py` — phase 1 appends to it, phase 2 does **not** touch it
   (phase 2 creates `test_research_test_store.py` instead). This phase touches neither.

---

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/runner.py` | modify | module docstring (`:1`–`:11`); imports (`:23`–`:30`); **append** a new "the test window" section after `:253` with `Tested`, `resolve_candidate`, `preflight_test`, `test_trial_row`, `run_test`. Nothing above `:253` changes except the docstring and two import lines. |
| `engine/src/seer_engine/commands/lab.py` | modify | **post-phase-3 file.** Module docstring: insert the `lab test` block after phase 3's `lab promote` block; `add_arguments` — new `test` subparser immediately after phase 3's `promote` subparser; `_status`'s status sections (the `("Dev-eligible / promoted", "dev-eligible"), ("Promoted", "promoted")` tuple); new handlers `_test_plan`, `_gate_note`, `_promote_argv`, `_verdict_report`, `_test` after phase 3's `_promote`; `_HANDLERS` gains `"test": _test,` after `"promote": _promote,` |
| `engine/tests/labkit.py` | modify | append `smoke_test_window` / `smoke_test_market` / `smoke_test_data` after `:58`; add one `Window` import beside `:13` |
| `engine/tests/test_lab_test_window.py` | create | the phase's tests: the database's refusal of a second look, N unmoved, the verdict, the transitions, the hand-off |
| `.claude/skills/explore-and-experiment-new-method/SKILL.md` | modify | replace the whole `## Promotion` section (`:123`–`:143`): both subcommands exist now — `lab promote` + commit, then `lab test --dry-run`, then `lab test`, then the printed `promote` command |

---

## Implementation Steps

### Step 1: Widen `runner.py`'s docstring and imports

**File:** `engine/src/seer_engine/lab/runner.py:1`–`:32`
**Change:** the module is no longer only `lab run`. Two symbols are added to the existing import
lines; no existing import is removed.

**Code — replace lines 1–32 with:**

```python
"""The lab's two runners: ``lab run`` on the dev window, ``lab test`` on the test window.

``lab run`` (design §2, §3) -- the search:

1. Refuse when the method file is not committed (its commit is the pre-registration), when the
   method has already run, or when any variant's configuration already has a dev trial.
2. Run the variants through ``dev.run_registry`` on the research store (every D9 guard).
3. Deflated Sharpe per trial with N = every dev trial in the lab, this batch included, and the
   variance of the daily Sharpe across those trials.
4. Eligible = the five P7a D8 conditions and DSR >= 0.95. Insert the trials, set the method's
   ``source_sha`` and status (``dev-eligible`` when any trial is eligible, else ``rejected``),
   all in one transaction.

``lab test`` (design §3) -- the one counted look:

1. Refuse a method that is not ``promoted``, a method file that is not committed or no longer
   hashes to the ``source_sha`` it ran under, a pre-registration that is missing, uncommitted or
   names another configuration, a configuration with no dev trial, and a configuration that has
   already been looked at.
2. Run the one pre-registered variant through the same ``dev.run_registry`` on the **test**-window
   store, between the bounds that store carries.
3. Append one ``trials`` row with ``window='test'`` and move the method to ``test-passed`` or
   ``test-failed``, both final, in one transaction.

**The look does not move the lab's N.** ``store.dev_trial_count`` and ``store.dev_daily_sharpes``
are dev-only and stay dev-only: design §1 makes ``trials`` the multiple-testing count of the
*search*, and §3 makes the test window a *look* at one already-counted configuration. A dev trial
recorded tomorrow is deflated by exactly the N it would have had if no look had ever been spent,
so every recorded dev trial stays reproducible.
"""

from __future__ import annotations

import logging
import sqlite3
import statistics
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from seer_engine import research
from seer_engine.backtest import dev
from seer_engine.backtest.dev import Candidate, DevRow
from seer_engine.commands.backtest_dev import daily_moments, month_end_curve, registry_problem
from seer_engine.fundamentals import coverage
from seer_engine.lab import store
from seer_engine.lab.method import METHOD_ID, Method, config_digest, config_text, source_sha
from seer_engine.strategies.allocator import MarketAware

log = logging.getLogger(__name__)
```

**Impact:** no behaviour change. `Candidate` and `METHOD_ID` become available to the new section.
`daily_moments` keeps its existing use in `_dsr`.

---

### Step 2: `Tested` and `resolve_candidate`

**File:** `engine/src/seer_engine/lab/runner.py` — **append** after `_hypothesis` ends at `:253`
**Change:** the value the test runner returns, and the `M0007-RESID` → `(Method, path, Candidate)`
lookup the CLI needs.

**Code:**

```python
# --------------------------------------------------------------------------- the test window


@dataclass(frozen=True)
class Tested:
    """The one counted look at the test window: its trial row, its dev row and its verdict."""

    trial: store.TrialRow
    row: DevRow
    status: str  # "test-passed" | "test-failed", both final


def resolve_candidate(candidate_id: str) -> tuple[Method, Path, Candidate]:
    """``(METHOD, its file, the named Candidate)`` for a candidate id like ``M0007-RESID``.

    ``lab test`` is addressed by *candidate*, not by method, because one variant per method is
    pre-registered and it is that variant -- not the method -- that gets the look. The method id
    is the part before the first hyphen (``method.Method`` enforces that shape at ``method.py:84``).

    ``store.LabError`` when the id is not a candidate id, when no method file carries it, or when
    the method has no such variant.
    """
    method_id, sep, _suffix = candidate_id.partition("-")
    if not sep or METHOD_ID.fullmatch(method_id) is None:
        raise store.LabError(
            f"{candidate_id!r} is not a candidate id; `lab test` takes the pre-registered variant, "
            f"which looks like M0007-RESID (<method>-<suffix>)"
        )
    from seer_engine.lab.method import discover

    methods = discover()
    if method_id not in methods:
        raise store.LabError(
            f"no method file for {method_id} in seer_engine/lab/methods/. The test window runs the "
            f"committed method file, not a database row. Known: {', '.join(methods) or '(none)'}"
        )
    method, path = methods[method_id]
    found = [c for c in method.candidates if c.id == candidate_id]
    if len(found) != 1:
        raise store.LabError(
            f"{method_id} has no variant {candidate_id!r}; its variants are "
            f"{', '.join(c.id for c in method.candidates)}"
        )
    return method, path, found[0]
```

**Impact:** new symbols only. `discover()` is imported inside the function exactly as
`commands/lab.py:226` and `commands/promote.py:146` already do it, so importing `runner` never
imports every method module.

---

### Step 3: `preflight_test` — every refusal, before any data is loaded

**File:** `engine/src/seer_engine/lab/runner.py` — append after Step 2
**Change:** the gate. Five refusals, all made before the store is opened, because the look is spent
once and never given back.

**Reconciled against phase 3.** Refusal 3 is now two calls into `lab.prereg` and no logic of its
own: `prereg.require_committed(candidate.id)` already refuses a file that names another method or
another candidate, and `prereg.check_digest(p, digest)` already refuses a drifted configuration.
The draft's hand-rolled `pre.candidate_id != candidate.id` and `pre.config_digest != digest`
comparisons are **deleted**, not duplicated — one owner per rule. `pre=` replaces the draft's
`require_commit=False` for the prereg half: `require_committed` shells out to git, so it runs
once and its answer is handed back in for the in-transaction re-check.

**Code:**

```python
def preflight_test(
    conn: sqlite3.Connection,
    method: Method,
    path: Path,
    candidate: Candidate,
    *,
    pre: "prereg.Prereg | None" = None,
    require_commit: bool = True,
) -> "prereg.Prereg":
    """Every refusal ``lab test`` makes before any data is loaded (``store.LabError``).

    The look at the test window is spent once and never given back, so each of these is checked
    before the store is even opened:

    1. **the method is ``promoted``.** ``lab promote`` (phase 3) is the only thing that moves it
       there, and the lab's ``TRANSITIONS`` give ``promoted`` only two exits, both of them final.
    2. **the method file is committed and still hashes to the ``source_sha`` recorded when it
       ran.** The dev trial measured one file; the test window must measure the same one. A
       changed file is a new variation method, not a second look.
    3. **a pre-registration exists, is committed, and names this candidate and this configuration
       digest** (``lab.prereg``, phase 3). This is design §3's "pre-registered ... before any test
       number exists": the thing pre-registered is the thing that runs. Both halves are phase 3's
       functions -- ``require_committed`` (git state, and that the file names *this* method and
       *this* candidate) and ``check_digest`` (that the configuration has not drifted since) --
       and neither is reimplemented here.
    4. **this configuration has a recorded ``dev`` trial.** The test window confirms a dev result;
       it never discovers one.
    5. **this configuration has no ``test`` trial.** The database refuses a second look on its own
       (``UNIQUE(config_digest, window)`` plus the append-only triggers, ``store.py:169``,
       ``:186``, ``:189``); this is the early, readable form of the same no, made before a store
       is loaded and a backtest is run.

    Returns the pre-registration, so the caller can print what it is about to honour.

    ``pre`` is an already-read pre-registration. ``require_committed`` shells out to git, so the
    caller reads it once and hands it back for the re-check inside the write lock; ``check_digest``
    and the two database refusals still run every time. ``require_commit=False`` skips 2's git
    checks on the *method file*; it never relaxes 1, 3's digest comparison, 4 or 5. Tests pass
    both.
    """
    from seer_engine.lab import prereg

    row = store.get_method(conn, method.id)
    if row is None:
        raise store.LabError(
            f"no method {method.id} in the lab database; nothing reaches the test window that the "
            f"lab has not run"
        )
    status = str(row["status"])
    if status != "promoted":
        raise store.LabError(
            f"{method.id} is {status!r}; only a 'promoted' method reaches the test window. "
            f"`lab promote {method.id}` pre-registers the best dev-eligible variant by MAR and "
            f"moves it there. From {status!r} the lab's TRANSITIONS have no edge to 'promoted', "
            f"and the test window stays shut"
        )
    if require_commit:
        problem = registry_problem(path)
        if problem is not None:
            raise store.LabError(
                f"{method.id}: {problem}. The test window is spent once; it runs only against the "
                f"committed method file"
            )
        recorded = row["source_sha"]
        actual = source_sha(path)
        if recorded is not None and recorded != actual:
            raise store.LabError(
                f"{method.id}: the method file hashes {actual[:12]} but its dev trials ran under "
                f"{recorded[:12]}; the file changed after it ran. A changed method is a new "
                f"variation method (source_kind='variation', parent_id={method.id}), not a second look"
            )
    # Phase 3 owns both halves of refusal 3. require_committed checks git AND that the file
    # names this method and this candidate; check_digest checks what the candidate *does*.
    if pre is None:
        pre = prereg.require_committed(candidate.id)
    digest = config_digest(candidate)
    prereg.check_digest(pre, digest)
    if not store.has_trial(conn, digest, "dev"):
        raise store.LabError(
            f"{candidate.id}: this configuration has no dev trial. The test window confirms a dev "
            f"result; it never discovers one"
        )
    if store.has_trial(conn, digest, "test"):
        hit = conn.execute(
            "SELECT candidate_id, run_at, eligible FROM trials WHERE config_digest = ? AND window = 'test'",
            (digest,),
        ).fetchone()
        raise store.LabError(
            f"{candidate.id}: this configuration already had its look at the test window as "
            f"{hit[0]} on {hit[1]} ({'passed' if hit[2] else 'failed'}). There is no second look: "
            f"the database holds at most one test trial per configuration and trials are "
            f"append-only"
        )
    return pre
```

**Impact:** new symbol. Refusal 2's `source_sha` comparison is strictly stronger than `lab run`'s
`registry_problem` alone, and costs nothing — the file has already been read by `discover()`.
Refusals 3a and 3b are `prereg.PreregError`, which is a `store.LabError`, so the single
`except store.LabError` in `commands/lab.py:run` still turns every one of the five into exit 2.

---

### Step 4: `test_trial_row` — what goes in `n_trials_at_run` and `dsr`

**File:** `engine/src/seer_engine/lab/runner.py` — append after Step 3
**Change:** the plan's named open point, decided and justified in the docstring so the decision
travels with the code.

**The decision.**

- **`n_trials_at_run` = `store.dev_trial_count(conn)` as it stands, unchanged by this row.**
  Design §1 makes `trials` "the multiple-testing count"; §3 makes the test window a *look* at one
  configuration that the dev search already counted. Counting it again would deflate every future
  dev trial by an N inflated by out-of-sample confirmations, which are not searches. `store`'s
  `dev_trial_count` and `dev_daily_sharpes` both already filter `window = 'dev'`
  (`store.py:555`, `:564`) and **stay dev-only**: this phase reads them and does not change them.
  The consequence is the testable invariant `dev_trial_count` before == after (Step 9, test 2).
- **`dsr` is recorded and does not decide the verdict.** It is this candidate's out-of-sample daily
  Sharpe deflated by the N that selected it and by the variance of the dev trials' daily Sharpe —
  a meaningful number ("is this still significant given how hard we looked?") and one the web
  already renders (`store.py:776`). It is *not* a pass condition, because the look was
  pre-registered: there is no selection among test results to deflate, and adding `DSR >= 0.95` on
  top of the five go-live conditions would be inventing a sixth gate this phase does not own.
  `store.DSR_LABEL` therefore never appears in a test trial's `failed`.
- **The verdict is the five design §1 go-live conditions**, which `dev.make_row` has already
  applied to the row (`dev.py:330`–`:348`): `failed` and `eligible` are the row's own, copied
  across unchanged.

`deflated_sharpe` returns `None` for `n_trials < 2` (`dev.py:528`), and `var_trials` is `None`
below two dev Sharpes, so an empty or near-empty lab yields `dsr = None` rather than an error.

**Code:**

```python
def test_trial_row(
    conn: sqlite3.Connection,
    method: Method,
    row: DevRow,
    curve: Any,
    *,
    fingerprint: str,
    git_sha: str,
) -> store.TrialRow:
    """The one ``window='test'`` trial row for ``row`` (``curve``: its month-end equity curve).

    **It does not move the lab's N.** ``n_trials_at_run`` is ``store.dev_trial_count(conn)`` as it
    stands, unchanged by this row: design §1 makes ``trials`` the multiple-testing count of the
    *search*, and §3 makes the test window a look at one already-counted configuration, not a new
    search. ``store.dev_trial_count`` and ``store.dev_daily_sharpes`` are dev-only and stay
    dev-only, so a dev trial recorded afterwards is deflated by exactly the N it would have had if
    this look had never happened and every recorded dev trial stays reproducible.

    ``dsr`` is recorded and **does not decide the verdict**: the out-of-sample Sharpe deflated by
    the N that selected this configuration and by the variance of the dev trials' daily Sharpe. It
    is worth keeping in the column the web already renders, but it is not a condition, because the
    look was pre-registered -- there is no selection among test results to deflate, and
    ``store.DSR_LABEL`` never appears in a test trial's ``failed``.

    The verdict is the five design §1 go-live conditions, which ``dev.make_row`` already applied to
    ``row``; ``failed`` and ``eligible`` are the row's own.
    """
    n_trials = store.dev_trial_count(conn)
    sharpes = store.dev_daily_sharpes(conn)
    var_trials = statistics.variance(sharpes) if len(sharpes) >= 2 else None
    c = row.candidate
    m = row.stats.metrics
    worst = row.stats.worst_year
    return store.TrialRow(
        method_id=method.id,
        candidate_id=c.id,
        config_digest=config_digest(c),
        config_text=config_text(c),
        rules_id=c.rules.id,
        allocator_id=str(c.allocator.id),
        window="test",
        start=row.start.isoformat(),
        end=row.end.isoformat(),
        store_fingerprint=fingerprint,
        git_sha=git_sha,
        run_at=store.now_iso(),
        total_return=_f(m.total_return),
        cagr=_f(m.cagr),
        max_drawdown=_f(m.max_drawdown),
        profit_factor=_f(m.profit_factor),
        trades=int(m.trades),
        sharpe=_f(row.stats.sharpe),
        exposure=_f(row.stats.exposure),
        turnover=_f(row.stats.turnover),
        worst_year=None if worst is None else int(worst[0]),
        worst_year_return=None if worst is None else float(worst[1]),
        spy_tr_return=_f(row.spy_tr.total_return),
        spy_tr_cagr=_f(row.spy_tr.cagr),
        mar=row.mar,
        failed="; ".join(row.failed),
        eligible=row.eligible,
        dsr=_dsr(row, n_trials, var_trials),
        n_trials_at_run=n_trials,
        curve_json=store.curve_json(curve),
    )
```

**Impact:** new symbol. `_dsr` and `_f` are the existing module-private helpers at `:124` and
`:132`, reused unchanged.

---

### Step 5: `run_test` — spend the look, record it, close the method

**File:** `engine/src/seer_engine/lab/runner.py` — append after Step 4
**Change:** the runner itself, shaped on `run_method` (`:196`) and sharing its transaction
discipline: compute outside the lock, re-check inside it, write once.

**Two things it does that `run_method` does not, and why.**

1. **It refuses a store that is not a test store.** `load_store` refuses it too (phase 2), but a
   mis-pointed `SEER_RESEARCH_STORE` producing a `window='test'` trial measured on dev data would
   be an unrecoverable lie in an append-only table. Two independent noes is the right number here.
2. **It refuses a `MarketAware` method against an empty fundamental panel.** `lab run`'s coverage
   gate (`preflight_data`, `:86`) is **not** reused: `fundamentals.coverage` measures over
   `coverage.WINDOW_END`, which `tests/test_fundamentals_coverage.py:107` pins equal to `DEV_END`,
   so running it against a test store would measure the wrong window and refuse everything. The
   dev-window coverage gate has already done its job for this method. What remains is the one
   failure mode that gate would still have caught — ranking on a panel that is not there — and
   that is a one-line check needing nothing from `coverage`.

**Code:**

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
    dispatch and the same D8 row ``lab run`` uses, with the window as the only difference -- then
    one ``trials`` row is appended and the method moves to ``test-passed`` or ``test-failed``, both
    final, in one transaction. Every refusal is made before the store is loaded except the two the
    store itself makes possible, and all of them spend nothing.
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

    captured: list[tuple[DevRow, Any]] = []

    def on_result(i: int, result: Any, row: DevRow) -> None:
        captured.append((row, month_end_curve(result.snapshots)))

    dev.run_registry(
        data.market,
        data.dividends,
        data.spy_dividends,
        (candidate,),
        on_result=on_result,
        window=window,
    )
    (row, curve), = captured
    m = row.stats.metrics
    log.info(
        "%s on the test window %s..%s: return %s vs SPY TR %s, max DD %s, PF %s, trades %d",
        candidate.id, row.start, row.end, m.total_return, row.spy_tr.total_return,
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
        store.insert_trials(conn, [trial])
        store.update_method(conn, method.id, status=status)
    return Tested(trial=trial, row=row, status=status)
```

**Impact:** new symbol. `run_registry` with a one-candidate tuple is deliberate: it is the exact
code path `lab run` takes (including `prepare_for`, the duplicate-id checks and the
`MAX_CANDIDATES` cap), so the test trial is produced by the same machinery as the dev trial it
confirms. `run_candidate` would bypass `prepare_for` and hand `prepared=None` to a `MarketAware`
allocator.

---

### Step 6: the `lab test` subcommand

**File:** `engine/src/seer_engine/commands/lab.py`
**Change:** docstring, subparser, `_status` sections, four helpers, the handler, the dispatch entry.

**Written against the post-phase-3 `commands/lab.py`.** Phase 3 lands first and has already
added a `lab promote` docstring block, a `promote` subparser, a `_promote` handler between `_run`
and `_idea`, and a `"promote": _promote,` entry in `_HANDLERS`. Every anchor below names phase
3's blocks, not `run`'s, and no line number from `2d03fd1` past `:78` is still valid.

**6a — module docstring.** Insert the `lab test` block **immediately after phase 3's `lab promote`
block** and before `lab idea`, so the docstring reads in the order the lab is used
(run → promote → test). Leave the `lab run` block alone — it is unchanged:

```python
    lab test M0007-A [--store DIR] [--roster-id ID] [--dry-run]
                                    the one counted look: run a promoted method's pre-registered
                                    variant once on the test window, record a `test` trial and set
                                    test-passed / test-failed (both final). Refuses without a
                                    committed pre-registration, refuses a method that is not
                                    promoted, and the database refuses a second look. --dry-run
                                    prints what would run and spends nothing
```

**6b — the subparser.** Insert **after phase 3's `promote` subparser** (the one ending with its
`--dir` argument) and before the `idea` subparser:

```python
    s = sub.add_parser("test", help="the one counted look at the test window (design §3)")
    s.add_argument("candidate", metavar="M0007-A",
                   help="the pre-registered variant, not the method: one variant per method "
                        "is pre-registered and it is the one that gets the look")
    s.add_argument(
        "--store",
        type=Path,
        default=Path(os.environ.get("SEER_RESEARCH_TEST_STORE") or research.TEST_STORE_DIR),
        help=f"test-window research store (default: {research.TEST_STORE_DIR}, or "
             "$SEER_RESEARCH_TEST_STORE); a dev store here is refused",
    )
    s.add_argument("--roster-id", default=None, metavar="ID",
                   help="the paper-roster id to propose in the promote command printed on a pass "
                        "(default: the method id)")
    s.add_argument("--dry-run", action="store_true",
                   help="print what would run -- the window, the store, the pre-registration and "
                        "the conditions that decide the verdict -- and stop. Loads nothing, runs "
                        "nothing, records nothing; the look is not spent")
```

**6c — `_status`'s status sections.** Phase 3 does not touch `_status`, so this is the tuple as
it stands at `2d03fd1` (`:174`–`:175`), currently
`(("Backlog (idea)", "idea"), ("Blocked on data", "blocked-data"), ("Dev-eligible / promoted",
"dev-eligible"), ("Promoted", "promoted"))`. Replace it with:

```python
    for title, status in (("Backlog (idea)", "idea"), ("Blocked on data", "blocked-data"),
                          ("Dev-eligible", "dev-eligible"), ("Promoted (pre-registered)", "promoted"),
                          ("Test-passed", "test-passed"), ("Test-failed", "test-failed")):
```

The two statuses this phase makes reachable now have somewhere to appear, and the stale
"Dev-eligible / promoted" label stops naming a section it never held. `summary_rows` already prints
`test-window looks used` (`store.py:669`), so nothing else in `_status` changes.

**Impact:** `lab status` grows at most four lines, and only for a lab that has promoted something.

---

### Step 7: the handler and the hand-off to `promote`

**File:** `engine/src/seer_engine/commands/lab.py` — insert **after phase 3's `_promote`**, before
`_idea`
**Change:** `_test` plus the four pure helpers it prints with.

**The hand-off decision, stated.** Design §6 makes the paper-roster entry autonomous — "never ask"
— and the index records that as governing. It does **not** require one process, and three facts
argue against calling `promote.run()` inside `lab test`:

- `commands/promote.py` opens Neon (`db.connect()`, `promote.py:444`) and imports `psycopg`.
  `lab test` must stay offline: it reads a research store and a SQLite file, and the look it spends
  must not be able to fail on a network.
- The lab write and the roster write cannot share a transaction. `promote.py:37`–`:43` already
  solved that ordering once, for itself; re-entering it from inside the look's own transaction
  would add a third partial state nobody has reasoned about.
- `promote` needs a roster id, display name, subtitle and gate note. Composing them is exactly what
  the skill (the autonomous agent) does, and `lab test` composing them *and printing them filled
  in* is the hand-off: the agent runs the printed line without asking anyone.

So: on a pass, `lab test` prints the complete `python -m seer_engine promote …` command, every
argument filled in from the two recorded trials, and SKILL.md (Step 10) tells the agent to run it.
`record_promotion` and `commands/promote.py` are untouched — they already handle the
`('test-passed', 'paper')` edge and are idempotent. **Flagged for the reconciler:** if the set's
owner wants it in-process instead, the change is one `subprocess.run(argv)` at the end of `_test`
behind a `--promote` flag; `_promote_argv` is already the argv.

**Code:**

```python
def _test_plan(method, candidate, pre, store_dir: Path) -> str:
    """What ``lab test`` would do, printed by ``--dry-run``. Nothing is loaded or run.

    ``pre`` is a ``lab.prereg.Prereg`` (phase 3): every field is a ``str`` and it carries no
    path, so the file is named with ``prereg.path_for(pre.method)``.
    """
    from seer_engine.lab.method import config_digest
    from seer_engine.lab.prereg import path_for, repo_path

    return "\n".join((
        f"lab test {candidate.id}  (dry run: nothing is loaded, run or recorded)",
        "",
        f"  method            {method.id} {method.name}  [promoted]",
        f"  variant           {candidate.id}  rules {candidate.rules.id}  allocator "
        f"<{candidate.allocator.id}>",
        f"  config digest     {config_digest(candidate)}",
        f"  pre-registration  {repo_path(path_for(pre.method))}  (committed; digest "
        f"{pre.config_digest[:12]})",
        f"  pre-registered    {pre.candidate} on {pre.date}, for the test window {pre.test_window}",
        f"  test store        {store_dir}",
        "",
        "  the verdict is the five design §1 go-live conditions on the test window:",
        "    " + ", ".join(dev.FAILURE_LABELS),
        "  DSR is recorded, not a condition: the look is pre-registered, so there is nothing to",
        "  deflate. The lab's N does not move -- a test trial is a look, not a search.",
        "",
        "  on a pass  -> test-passed (final), and the promote command is printed",
        "  on a fail  -> test-failed (final)",
        "",
        "  Run it for real without --dry-run. There is exactly one look per configuration and the",
        "  database refuses a second.",
    ))


def _gate_note(conn, tested) -> str:
    """The honest backtest-gate sentence for ``promote --gate-note``.

    Every roster entry's gate note says what the backtest gate actually did; no entry has ever
    passed one. A method that reaches here is the first kind that can say otherwise, and the
    sentence says exactly what it passed and what it still has not: forward paper time.
    """
    t = tested.trial
    d = conn.execute(
        "SELECT * FROM trials WHERE config_digest = ? AND window = 'dev'", (t.config_digest,)
    ).fetchone()
    dev_part = (
        "no recorded dev trial"
        if d is None
        else (f"dev window {d['start']}..{d['end']}: MAR {fmt_num(d['mar'])}, DSR "
              f"{fmt_num(d['dsr'], 3)} at N={d['n_trials_at_run']}, all five conditions met")
    )
    test_part = (
        f"test window {t.start}..{t.end}, one pre-registered look: return "
        f"{fmt_signed_pct(t.total_return)} vs SPY TR {fmt_signed_pct(t.spy_tr_return)}, max DD "
        f"{fmt_pct(t.max_drawdown)}, PF {fmt_pf(t.profit_factor)}, {t.trades} trades, MAR "
        f"{fmt_num(t.mar)} -- all five conditions met"
    )
    return (
        f"Passed the quant backtest gate. {dev_part}; {test_part}. No forward paper record yet: "
        f"design §1 still needs >= 3 months and >= 100 closed paper trades before real money."
    )


def _promote_argv(method, tested, *, roster_id: str, gate_note: str, lab_db: Path) -> list[str]:
    """The exact ``promote`` command for a passed method. Pure: builds argv, runs nothing.

    ``lab test`` does not call ``commands/promote.py`` in-process. It reads a research store and a
    SQLite file and must stay offline; ``promote`` opens Neon, and the two writes cannot share a
    transaction (``promote.py`` module docstring). Design §6's "never ask" is satisfied by the
    skill running this line immediately, which is what it does.
    """
    sub = method.hypothesis.strip().splitlines()[0].strip()
    if len(sub) > 80:
        sub = sub[:77].rstrip() + "..."
    return [
        "python", "-m", "seer_engine", "promote",
        "--method", method.id,
        "--candidate", tested.trial.candidate_id,
        "--id", roster_id,
        "--name", f"{roster_id} · {method.name}",
        "--sub", sub,
        "--gate-note", gate_note,
        "--lab-db", str(lab_db),
    ]


def _verdict_report(conn, method, tested, *, roster_id: str, lab_db: Path) -> str:
    """What the owner (or the skill) reads after the look: the verdict and the one next step."""
    import shlex

    t = tested.trial
    head = [
        "",
        f"{t.candidate_id} on the test window {t.start}..{t.end}: {tested.status.upper()}",
        f"  return {fmt_signed_pct(t.total_return)} vs SPY TR {fmt_signed_pct(t.spy_tr_return)}, "
        f"CAGR {fmt_signed_pct(t.cagr)}, maxDD {fmt_pct(t.max_drawdown)}, "
        f"PF {fmt_pf(t.profit_factor)}, trades {t.trades}, MAR {fmt_num(t.mar)}",
        f"  DSR {fmt_num(t.dsr, 3)} at N={t.n_trials_at_run} (recorded, not a condition)",
    ]
    if tested.status == "test-failed":
        return "\n".join(head + [
            f"  failed: {t.failed}",
            "",
            "test-failed is final. There is no second look at this configuration, on any window.",
            "Queue a variation (lab idea --source-kind variation --parent "
            f"{method.id} ...) if the evidence supports one, and journal what the test window said",
            "that the dev window did not.",
        ])
    argv = _promote_argv(method, tested, roster_id=roster_id,
                         gate_note=_gate_note(conn, tested), lab_db=lab_db)
    return "\n".join(head + [
        "",
        "test-passed. Next, without asking anyone (design §6): put it on the paper roster under a",
        "new id with its own clock, then stage and commit the lab.",
        "",
        f"  {shlex.join(argv)}",
        "",
        "  lab stage      # writes web/data/lab.json and git-adds it with the database",
        "",
        "promote writes the roster row with no paper_start, so the next paper night freezes the",
        "spec and starts the clock there: the paper record begins at the promotion and claims",
        "nothing earlier. Real money still needs all of design §1.",
    ])


def _test(conn, args) -> int:
    """``lab test <candidate>``: the one counted look at the test window (design §3)."""
    from seer_engine.lab import runner

    method, path, candidate = runner.resolve_candidate(args.candidate)
    store_dir = Path(args.store)
    pre = runner.preflight_test(conn, method, path, candidate)
    if args.dry_run:
        print(_test_plan(method, candidate, pre, store_dir))
        return 0
    t0 = time.perf_counter()
    # Phase 2's idiom: ask the store which window it is for, then ask load_store for exactly
    # that one. load_store compares the two before it reads a single data file, so a dev store
    # here is refused by name; the `window.name != "test"` test below is the second of the two
    # independent noes `run_test` wants, and it names the fix.
    try:
        window = research.declared_window(store_dir)
        if window.name != "test":
            raise store.LabError(
                f"{store_dir} declares the {window.name} window; `lab test` needs the test-window "
                f"store. Build it with `python -m seer_engine research_store --test-window` and "
                f"point --store at {research.TEST_STORE_DIR}"
            )
        data = research.load_store(store_dir, window=window)
    except FileNotFoundError as e:
        raise store.LabError(
            f"test-window research store {store_dir} is missing {e.filename or e}; build it with "
            f"`python -m seer_engine research_store --test-window --store {store_dir}`"
        ) from e
    except ValueError as e:
        raise store.LabError(f"{store_dir}: {e}") from e
    log.info("test store %s loaded, window %s..%s (%.1fs)", data.fingerprint[:12],
             data.window.start, data.window.end, time.perf_counter() - t0)
    tested = runner.run_test(conn, method, path, candidate, data,
                             git_sha=runner.git_head(config.REPO_ROOT))
    _show(conn, argparse.Namespace(method=method.id))
    print(_verdict_report(conn, method, tested,
                          roster_id=args.roster_id or method.id, lab_db=Path(args.db)))
    print(f"\nLab N (dev trials) is still {store.dev_trial_count(conn)}; "
          f"test-window looks used: {store.test_looks(conn)}")
    return 0
```

**7b — dispatch.** In `_HANDLERS`, add **after phase 3's `"promote": _promote,` line**, so the
table reads in the same order as the docstring (`run`, `promote`, `test`, `idea`, …):

```python
    "test": _test,
```

**Impact:** `lab test` returns 0 for both verdicts — a recorded `test-failed` is the command
succeeding. Only a refusal exits 2, through `run`'s existing `except store.LabError` at `:128`.
`fmt_num`, `fmt_pct`, `fmt_pf`, `fmt_signed_pct` are already imported at `:37`; `dev` at `:36`;
`config`, `research` at `:35`; `os`, `time`, `argparse`, `Path` at `:29`–`:33`. Only `shlex` is new,
and it is imported inside `_verdict_report` the way `_stage` imports `subprocess` at `:329`.

---

### Step 8: a test-window fixture

**File:** `engine/tests/labkit.py` — import line `:13`, then append after `:58`
**Change:** a synthetic *test*-window `ResearchData`, beside the existing dev one. **No existing
function in this file is modified**, so phase 1's and phase 2's tests keep the fixture they have.

**8a — the import.** Keep `tests/labkit.py:13` (`from seer_engine.backtest.dev import DEV_END`)
and add phase 1's window module beside it, after the `market` import:

```python
from seer_engine.backtest.dev import DEV_END
from seer_engine.backtest.market import Market, Membership
from seer_engine.backtest.window import Window
```

`Window` comes from `seer_engine.backtest.window`, the module phase 1 creates and owns —
`backtest/dev.py` only re-exports it as a side effect of its own import, and depending on that
would couple this fixture to an import line rather than to a contract.

**8b — append after `:58`:**

```python
# ---- the test window (build-promotion-path phase 4) ------------------------------------------

TEST_FIRST = date(2015, 10, 19)  # the first session after DEV_END: the test window opens here
TEST_LAST = date(2018, 12, 31)  # a fixture end; the real store's end is whatever its manifest says
TEST_SPY_EX_DATE = date(2016, 6, 17)


def smoke_test_window() -> Window:
    """The fixture's test window, shaped like the one a built ``engine/.research-test`` carries."""
    return Window(name="test", start=TEST_FIRST, end=TEST_LAST)


def smoke_test_market(extra: Iterable[str] = ()) -> Market:
    """``smoke_market``'s shape over test-window sessions only: no bar on or before ``DEV_END``.

    The symbols, the price generator and the membership are the dev fixture's, so a candidate that
    runs on one runs on the other and only the window differs.
    """
    days = dates.sessions(TEST_FIRST, TEST_LAST)
    assert days[0] > DEV_END  # a test fixture that straddles DEV_END would prove nothing
    symbols = tuple(sorted(set(BASE_ETFS) | set(extra) - set(MEMBER_STOCKS))) + MEMBER_STOCKS
    history = {s: smoke_history(s, k, days) for k, s in enumerate(symbols)}
    membership = Membership(intervals=tuple((s, days[0], None) for s in MEMBER_STOCKS))
    return Market(history=history, membership=membership, fx=((days[0], Decimal("2000")),))


def smoke_test_data(extra: Iterable[str] = ()) -> ResearchData:
    """A loaded *test*-window store, as ``research.load_store(d, window=declared_window(d))``
    returns one (phase 2's idiom: ask the store which window it is for, then ask for that one)."""
    spy_div = Decimal("1.1000")
    return ResearchData(
        market=smoke_test_market(extra),
        dividends={"SPY": {TEST_SPY_EX_DATE: spy_div}},
        spy_dividends=(Dividend(TEST_SPY_EX_DATE, spy_div),),
        fingerprint="smoke-test",
        # Phase 2's three optional manifest keys, spelled as it spells them. Nothing in
        # `run_test` reads the manifest -- the window travels on `ResearchData.window` -- but a
        # fixture that invents key names is a fixture that teaches the wrong ones.
        manifest={
            "window_name": "test",
            "window_start": TEST_FIRST.isoformat(),
            "window_end": TEST_LAST.isoformat(),
        },
        window=smoke_test_window(),
    )
```

**Impact:** `dates.sessions(2015-10-19, 2018-12-31)` is roughly 807 sessions, enough for the
50-session lookback the phase's test candidate uses and far too few for 100 closed monthly trades —
so the fixture's end-to-end verdict is deterministically `test-failed` on `>= 100 trades`, which is
what the integration test asserts. The `test-passed` branch is driven by a synthetic eligible row
instead (Step 9, test 5), because forcing a synthetic market to genuinely pass five conditions
would be fitting the fixture to the answer.

---

### Step 9: the tests

**File:** `engine/tests/test_lab_test_window.py` (new)
**Change:** the phase's proof. Every test uses a temp database and fixture data; **none of them
touches `lab/lab.sqlite`, builds a store, or reaches the network.**

**Code (complete file):**

```python
"""``lab test``: the one counted look at the test window (method lab design §3).

Nothing here touches ``lab/lab.sqlite`` or ``engine/.research-test``: every test runs against a
temp database and the synthetic test-window market in ``labkit``. Building the mechanism spends no
look, and the committed lab must still read "test-window looks used: 0" when this lands.
"""

from __future__ import annotations

import sqlite3
from datetime import date
from types import SimpleNamespace

import pytest
from labkit import TEST_FIRST, TEST_LAST, smoke_test_data, smoke_test_window

from seer_engine.backtest import dev
from seer_engine.backtest.book_runner import RunStats
from seer_engine.backtest.dev import Candidate, make_row
from seer_engine.backtest.metrics import Metrics
from seer_engine.lab import prereg, runner, store
from seer_engine.lab.method import Method, config_digest, config_text
from seer_engine.sim.rules import MONTHLY_HOLD
from seer_engine.strategies.f_index import TIMING, TimingParams


# ---- fixtures ---------------------------------------------------------------------------------


def _cand(cid: str, family: str, n: int = 50) -> Candidate:
    return Candidate(
        id=cid, family=family, rules=MONTHLY_HOLD, allocator=TIMING,
        params=TimingParams(hold="SPY", signal="SPY", rule="sma", n=n),
        rationale="the pre-registered variant", added=date(2026, 10, 6), owner_inputs=(),
    )


def _method(mid: str = "M0001", cands=None) -> Method:
    return Method(
        id=mid, name="SMA test", family="trend", source_kind="knowledge", source_ref="",
        hypothesis="A 50-day SMA on SPY beats buy-and-hold after costs.\nSecond line ignored.",
        expected_failure="whipsaw", candidates=tuple(cands or (_cand(f"{mid}-A", mid),)),
    )


def _prereg(c: Candidate, *, method: str = "M0001", digest: str | None = None) -> prereg.Prereg:
    """A real ``prereg.Prereg`` (phase 3) -- every field a ``str``, no ``path`` field.

    Built rather than faked: ``Prereg`` is a frozen dataclass of fifteen strings with no
    behaviour, so constructing the real one costs nothing and cannot drift from phase 3's
    field names the way a local stand-in would.
    """
    return prereg.Prereg(
        method=method,
        candidate=c.id,
        config_digest=config_digest(c) if digest is None else digest,
        rules_id=c.rules.id,
        allocator_id=str(c.allocator.id),
        dev_trial="1",
        dev_window="1996-01-02..2015-10-16",
        test_window="2015-10-19..data end",
        gate=prereg.gate_text(),
        mar="0.790000",
        dsr="0.960000",
        n_trials_at_run="56",
        store_fingerprint="fp",
        git_sha="abc",
        date="2026-10-06",
    )


@pytest.fixture()
def conn(tmp_path):
    c = store.connect(tmp_path / "lab.sqlite")
    yield c
    c.close()


@pytest.fixture()
def promoted(conn):
    """M0001 at ``promoted`` with a recorded dev trial for its variant -- the state ``lab test``
    requires and the only state ``lab promote`` (phase 3) leaves behind."""
    m = _method()
    c = m.candidates[0]
    with conn:
        store.add_method(conn, id=m.id, name=m.name, family=m.family, source_kind=m.source_kind,
                         hypothesis="h", status="registered")
        store.insert_trials(conn, [_dev_trial(m, c)])
        store.update_method(conn, m.id, status="dev-eligible")
        store.update_method(conn, m.id, status="promoted")
    return m


def _dev_trial(m: Method, c: Candidate, **kw) -> store.TrialRow:
    base = dict(
        method_id=m.id, candidate_id=c.id, config_digest=config_digest(c), config_text=config_text(c),
        rules_id=c.rules.id, allocator_id=str(c.allocator.id), window="dev", start="1996-01-02",
        end="2015-10-16", store_fingerprint="fp", git_sha="abc",
        run_at="2026-10-06T00:00:00+00:00", total_return=3.0, cagr=0.11, max_drawdown=0.14,
        profit_factor=1.6, trades=180, sharpe=0.9, exposure=0.8, turnover=1.2, worst_year=2008,
        worst_year_return=-0.09, spy_tr_return=2.0, spy_tr_cagr=0.08, mar=0.79, failed="",
        eligible=True, dsr=0.96, n_trials_at_run=56, curve_json="[]",
    )
    base.update(kw)
    return store.TrialRow(**base)


@pytest.fixture()
def prereg_ok(monkeypatch, promoted):
    """Phase 3's committed-prereg check, standing in for a real ``docs/lab/prereg/M0001.md``.

    ``preflight_test`` **calls** phase 3's ``require_committed``; it never reimplements the git
    or identity checks, so what a phase-4 test can honestly stub is its answer. ``check_digest``
    is phase 3's too and is **not** stubbed -- it is pure, so the real one runs here, which is
    what makes the stale-digest test below a real test.
    """
    c = promoted.candidates[0]
    pre = _prereg(c)

    def fake(candidate_id: str, *, directory=None):
        if candidate_id != c.id:
            raise prereg.PreregError(f"no pre-registration naming {candidate_id}")
        return pre

    monkeypatch.setattr(prereg, "require_committed", fake)
    return pre


@pytest.fixture(scope="module")
def data():
    return smoke_test_data()


# ---- the database refuses a second look --------------------------------------------------------


def test_the_database_refuses_a_second_look_without_any_python_guard(conn):
    """Design §3's "the database refuses a second look", proven against the schema.

    ``insert_trials`` makes the refusal readable (``store.py:542``), but the guarantee is
    ``UNIQUE(config_digest, window)`` (``store.py:169``): the same configuration, inserted with raw
    SQL past every Python check, is still refused -- and the append-only triggers mean the first
    row can never be deleted to make room.
    """
    m = _method()
    c = m.candidates[0]
    with conn:
        store.add_method(conn, id=m.id, name=m.name, family=m.family,
                         source_kind=m.source_kind, hypothesis="h")
        row = _dev_trial(m, c, window="test", start=TEST_FIRST.isoformat(), end=TEST_LAST.isoformat())
        store.insert_trials(conn, [row])
    assert store.test_looks(conn) == 1

    cols = ", ".join(f'"{x}"' for x in store.TRIAL_COLUMNS)
    marks = ", ".join("?" for _ in store.TRIAL_COLUMNS)
    values = [getattr(row, x) for x in store.TRIAL_COLUMNS]
    values[store.TRIAL_COLUMNS.index("eligible")] = int(row.eligible)
    values[store.TRIAL_COLUMNS.index("candidate_id")] = "M0001-SECOND"  # a new id does not help
    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
        conn.execute(f"INSERT INTO trials ({cols}) VALUES ({marks})", values)
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("DELETE FROM trials WHERE window = 'test'")
    assert store.test_looks(conn) == 1


# ---- the refusals ------------------------------------------------------------------------------


def test_a_method_that_is_not_promoted_is_refused(conn, prereg_ok, promoted, tmp_path):
    m2 = _method("M0002", cands=(_cand("M0002-A", "M0002"),))
    with conn:
        store.add_method(conn, id="M0002", name="n", family="f", source_kind="knowledge",
                         hypothesis="h", status="registered")
        store.update_method(conn, "M0002", status="dev-eligible")
    with pytest.raises(store.LabError, match="only a 'promoted' method"):
        runner.preflight_test(conn, m2, tmp_path / "m0002_x.py", m2.candidates[0],
                              require_commit=False)


def test_a_missing_prereg_is_refused(conn, monkeypatch, promoted, tmp_path):
    """`preflight_test` calls phase 3's `require_committed` and lets its refusal through.

    Phase 3's own tests prove *when* it refuses (missing, untracked, staged-only, modified,
    naming another method or another candidate) against a real git repository. What is this
    phase's to prove is that `lab test` asks, and that a `PreregError` is a `store.LabError`
    and so reaches exit 2 unchanged.
    """
    c = promoted.candidates[0]

    def missing(candidate_id, *, directory=None):
        raise prereg.PreregError(f"{candidate_id}: docs/lab/prereg/M0001.md does not exist")

    monkeypatch.setattr(prereg, "require_committed", missing)
    with pytest.raises(store.LabError, match="does not exist"):
        runner.preflight_test(conn, promoted, tmp_path / "x.py", c, require_commit=False)


def test_a_stale_digest_is_refused_by_phase_threes_check_digest(conn, promoted, tmp_path):
    """The configuration drifted after it was pre-registered. `check_digest` is not stubbed."""
    c = promoted.candidates[0]
    stale = _prereg(c, digest="0" * 64)
    with pytest.raises(prereg.PreregError, match="pre-registered 0{64}"):
        runner.preflight_test(conn, promoted, tmp_path / "x.py", c, pre=stale,
                              require_commit=False)


def test_a_configuration_with_no_dev_trial_is_refused(conn, promoted, tmp_path):
    fresh = _cand("M0001-B", "M0001", n=77)  # a variant that never ran on dev
    m = _method(cands=(promoted.candidates[0], fresh))
    with pytest.raises(store.LabError, match="no dev trial"):
        runner.preflight_test(conn, m, tmp_path / "x.py", fresh, pre=_prereg(fresh),
                              require_commit=False)


def test_a_dev_store_is_refused_before_anything_runs(conn, prereg_ok, promoted, tmp_path):
    """A mis-pointed store must never produce a 'test' trial measured on dev data."""
    from labkit import smoke_data

    with pytest.raises(store.LabError, match="research store was built for the 'dev' window"):
        runner.run_test(conn, promoted, tmp_path / "x.py", promoted.candidates[0], smoke_data(),
                        git_sha="x", require_commit=False)
    assert store.test_looks(conn) == 0


def test_resolve_candidate_refuses_a_method_id_and_an_unknown_variant():
    with pytest.raises(store.LabError, match="not a candidate id"):
        runner.resolve_candidate("M0007")
    with pytest.raises(store.LabError, match="no method file"):
        runner.resolve_candidate("M9999-A")


# ---- the look itself ---------------------------------------------------------------------------


def test_the_look_is_recorded_and_does_not_move_the_lab_s_n(conn, data, prereg_ok, promoted, tmp_path):
    before_n = store.dev_trial_count(conn)
    before_sharpes = store.dev_daily_sharpes(conn)
    c = promoted.candidates[0]
    tested = runner.run_test(conn, promoted, tmp_path / "x.py", c, data,
                             git_sha="cafe", require_commit=False)

    assert store.dev_trial_count(conn) == before_n          # the search's N did not move
    assert store.dev_daily_sharpes(conn) == before_sharpes  # nor the DSR's variance term
    assert store.test_looks(conn) == 1

    row = conn.execute("SELECT * FROM trials WHERE window = 'test'").fetchone()
    assert row["candidate_id"] == c.id
    assert row["config_digest"] == config_digest(c)
    assert row["git_sha"] == "cafe" and row["store_fingerprint"] == "smoke-test"
    assert row["n_trials_at_run"] == before_n
    assert date.fromisoformat(row["start"]) >= TEST_FIRST
    assert row["end"] == TEST_LAST.isoformat()
    assert store.DSR_LABEL not in row["failed"]  # DSR is recorded, never a condition
    assert tested.status == "test-failed"        # the fixture is ~3 years: far under 100 trades
    assert ">= 100 trades" in row["failed"]
    assert store.get_method(conn, "M0001")["status"] == "test-failed"


def test_a_second_look_is_refused_after_a_real_run(conn, data, prereg_ok, promoted, tmp_path):
    c = promoted.candidates[0]
    runner.run_test(conn, promoted, tmp_path / "x.py", c, data, git_sha="x", require_commit=False)
    with pytest.raises(store.LabError, match="already had its look"):
        runner.preflight_test(conn, promoted, tmp_path / "x.py", c, require_commit=False)
    assert store.test_looks(conn) == 1


def test_test_failed_is_final(conn, data, prereg_ok, promoted, tmp_path):
    runner.run_test(conn, promoted, tmp_path / "x.py", promoted.candidates[0], data,
                    git_sha="x", require_commit=False)
    for nxt in ("test-passed", "promoted", "paper", "dev-eligible"):
        with pytest.raises(store.LabError, match="forward"):
            store.update_method(conn, "M0001", status=nxt)


# ---- the verdict and the pass branch -----------------------------------------------------------


def _stats(*, trades: int = 150, dd: float = 0.10, pf: float = 1.6, total: float = 1.2) -> RunStats:
    m = Metrics(total_return=total, win_rate=0.55, profit_factor=pf, max_drawdown=dd,
                trades=trades, months=38.0, cagr=0.14)
    return RunStats(metrics=m, exposure=0.7, turnover=1.5, costs_usd=10.0, gross_pnl_usd=100.0,
                    cost_drag=0.1, dividends_usd=0.0, sharpe=0.9,
                    daily_returns=(0.01, -0.004, 0.006), year_returns=((2016, 0.1),),
                    worst_year=(2016, 0.1))


_SPY_TR = Metrics(total_return=0.6, win_rate=None, profit_factor=None, max_drawdown=0.2, trades=0,
                  months=38.0, cagr=0.08)


def _test_row(c: Candidate, **kw):
    """A DevRow on the **test** window -- phase 1's ``make_row(window=...)``."""
    return make_row(c, TEST_FIRST, TEST_LAST, _stats(**kw), spy_tr=_SPY_TR, spy_price=_SPY_TR,
                    window=smoke_test_window())


def test_the_verdict_is_the_five_go_live_conditions(promoted):
    c = promoted.candidates[0]
    assert _test_row(c).eligible is True
    assert _test_row(c, trades=99).failed == (">= 100 trades",)
    assert _test_row(c, total=0.6).failed == ("beats SPY TR",)  # equal is not beating
    assert _test_row(c, dd=0.16).failed == ("max DD <= 15%",)
    assert _test_row(c, pf=1.2).failed == ("PF >= 1.3",)


def test_a_passing_look_records_test_passed_and_a_dsr_that_is_not_a_condition(
    conn, monkeypatch, prereg_ok, promoted, tmp_path
):
    """The pass branch, driven by a synthetic eligible row rather than by a fitted market."""
    c = promoted.candidates[0]
    row = _test_row(c)
    snaps = (SimpleNamespace(date=TEST_FIRST, equity_usd=100.0),
             SimpleNamespace(date=TEST_LAST, equity_usd=220.0))

    def fake_run_registry(market, dividends, spy_dividends, registry, *, on_result=None, window=None):
        assert window.name == "test" and tuple(registry) == (c,)
        on_result(0, SimpleNamespace(snapshots=snaps), row)
        return (row,)

    monkeypatch.setattr(runner.dev, "run_registry", fake_run_registry)
    tested = runner.run_test(conn, promoted, tmp_path / "x.py", c, smoke_test_data(),
                             git_sha="x", require_commit=False)
    assert tested.status == "test-passed"
    assert store.get_method(conn, "M0001")["status"] == "test-passed"
    t = conn.execute("SELECT * FROM trials WHERE window = 'test'").fetchone()
    assert t["eligible"] == 1 and t["failed"] == ""
    assert t["dsr"] is None or 0.0 <= t["dsr"] <= 1.0
    assert t["n_trials_at_run"] == store.dev_trial_count(conn)


def test_a_passed_method_can_still_reach_paper(conn, monkeypatch, prereg_ok, promoted, tmp_path):
    """``record_promotion`` already owns the ('test-passed', 'paper') edge; this phase only has to
    leave the method where that edge starts."""
    c = promoted.candidates[0]
    row = _test_row(c)
    snaps = (SimpleNamespace(date=TEST_FIRST, equity_usd=100.0),
             SimpleNamespace(date=TEST_LAST, equity_usd=220.0))
    monkeypatch.setattr(
        runner.dev, "run_registry",
        lambda *a, on_result=None, window=None, **k: (on_result(0, SimpleNamespace(snapshots=snaps), row), (row,))[1],
    )
    runner.run_test(conn, promoted, tmp_path / "x.py", c, smoke_test_data(),
                    git_sha="x", require_commit=False)
    with conn:
        status = store.record_promotion(
            conn, method_id="M0001", strategy_id="SMA", candidate_id=c.id,
            object_name="TIMING", spec_digest="d" * 64,
        )
    assert status == "paper"
    assert store.test_looks(conn) == 1  # a promotion is not a backtest: no trial was added


# ---- the hand-off ------------------------------------------------------------------------------


def test_the_promote_command_is_printed_filled_in(conn, monkeypatch, prereg_ok, promoted, tmp_path):
    from seer_engine.commands import lab as lab_cmd

    c = promoted.candidates[0]
    row = _test_row(c)
    snaps = (SimpleNamespace(date=TEST_FIRST, equity_usd=100.0),
             SimpleNamespace(date=TEST_LAST, equity_usd=220.0))
    monkeypatch.setattr(
        runner.dev, "run_registry",
        lambda *a, on_result=None, window=None, **k: (on_result(0, SimpleNamespace(snapshots=snaps), row), (row,))[1],
    )
    tested = runner.run_test(conn, promoted, tmp_path / "x.py", c, smoke_test_data(),
                             git_sha="x", require_commit=False)
    note = lab_cmd._gate_note(conn, tested)
    assert "Passed the quant backtest gate" in note
    assert "one pre-registered look" in note
    assert "100 closed paper trades" in note  # it still says what has not happened

    argv = lab_cmd._promote_argv(promoted, tested, roster_id="SMA", gate_note=note,
                                 lab_db=tmp_path / "lab.sqlite")
    assert argv[:5] == ["python", "-m", "seer_engine", "promote", "--method"]
    assert "--candidate" in argv and argv[argv.index("--candidate") + 1] == c.id
    assert argv[argv.index("--id") + 1] == "SMA"
    assert argv[argv.index("--gate-note") + 1] == note
    report = lab_cmd._verdict_report(conn, promoted, tested, roster_id="SMA",
                                     lab_db=tmp_path / "lab.sqlite")
    assert "TEST-PASSED" in report and "seer_engine promote" in report and "lab stage" in report


def test_a_failed_look_prints_no_promote_command(conn, data, prereg_ok, promoted, tmp_path):
    from seer_engine.commands import lab as lab_cmd

    tested = runner.run_test(conn, promoted, tmp_path / "x.py", promoted.candidates[0], data,
                             git_sha="x", require_commit=False)
    report = lab_cmd._verdict_report(conn, promoted, tested, roster_id="SMA",
                                     lab_db=tmp_path / "lab.sqlite")
    assert "TEST-FAILED" in report
    assert "test-failed is final" in report
    assert "seer_engine promote" not in report


# ---- the dry run spends nothing ----------------------------------------------------------------


def test_the_dry_run_loads_nothing_and_spends_nothing(conn, prereg_ok, promoted, tmp_path, capsys):
    from seer_engine.commands import lab as lab_cmd

    text = lab_cmd._test_plan(promoted, promoted.candidates[0], prereg_ok, tmp_path / ".research-test")
    assert config_digest(promoted.candidates[0]) in text
    assert "nothing is loaded, run or recorded" in text
    for label in dev.FAILURE_LABELS:
        assert label in text
    assert store.test_looks(conn) == 0
```

**Impact:** one new test file, roughly a dozen tests, no network, no store build, no write outside
`tmp_path`.

---

### Step 10: the skill doc — the whole Promotion section, both subcommands

**File:** `.claude/skills/explore-and-experiment-new-method/SKILL.md:123`–`:143`
**Change:** **replace the entire `## Promotion` section.** This phase is its sole owner
(reconciled 2026-10-06): phase 3 deliberately touches no skill file, so there is no merge and no
half of the section left stale.

Three things in the current text are now **wrong**, not merely incomplete, and all three must go
in one edit — which is why this is a section replacement and not three bullet swaps:

1. `:125`–`:126` tells the agent to **build** `lab test` and the test-window store first. After
   this plan set they exist. An agent that follows the old sentence rebuilds a shipped feature.
2. `:135` ("Pre-register the best eligible variant by MAR … in `docs/lab/prereg/MNNNN.md`") names
   **no command**. `lab promote` (phase 3) is what writes that file, and `lab test` **refuses**
   without it. Leaving this step command-less is the gap that would stop every promotion dead:
   the agent would hand-write a file whose `config_digest` is not copied from the recorded dev
   trial, and `lab test` would refuse it. **This is why the edit is R2 work** — it is the
   precondition of the subcommand this phase ships, not the pre-registration mechanism itself.
3. `:139`–`:141` ("add it to the paper roster … following `docs/runbooks/paper-trading.md` and
   the existing roster code") describes hand-work. `lab test` now prints the finished command.

**Replace `:123`–`:143` with:**

````markdown
## Promotion (dev-eligible): autonomous, one counted look

Nobody approves this; you do it. Both commands exist — do not build them:

- **`lab promote <method>`:** picks the method's best eligible **dev** trial by MAR (one variant
  per method), writes `docs/lab/prereg/MNNNN.md` with the `config_digest` **copied from that
  recorded trial**, and moves the method `dev-eligible → promoted`. It is written once and never
  rewritten: a re-run with a better-looking variant available is a refusal, not an update. It
  loads no store, runs no backtest and spends no look.
- **`lab test <candidate>`:** takes the *variant* id (`M0007-RESID`), not the method id. It
  refuses a method that is not `promoted`, refuses a pre-registration that is missing,
  uncommitted, modified or names another configuration, refuses a configuration with no dev
  trial, and the database refuses a second look at any configuration
  (`UNIQUE(config_digest, window)` plus append-only triggers). `--dry-run` prints what would run
  and spends nothing. One `test` trial is recorded; **the lab's N does not move** (a look is not
  a search), and the method ends at `test-passed` or `test-failed`, both final.
- **The test-window store** lives at `engine/.research-test/` (gitignored), sessions 2015-10-19 →
  the latest session, built by `python -m seer_engine research_store --test-window`. It holds the
  same deep history as the dev store from 1993 — the window bounds what is *scored*, the store
  carries the lookback run-up — plus every session after `DEV_END`. Build it once, the first time
  something is promoted. `lab test` refuses a dev store pointed at it, and `lab run` refuses this
  one, so the two can never be swapped by accident.

Then:
1. `python -m seer_engine lab promote MNNNN`. Read what it printed, then **commit and push
   `docs/lab/prereg/MNNNN.md` before any test number exists** (design §3) — the command prints the
   exact `git add` / `git commit` lines. `lab test` refuses while the file is uncommitted, so this
   is not optional and not a formality.
2. `python -m seer_engine lab test MNNNN-X --dry-run` to read back what it will do, then the same
   command without `--dry-run`. That is the one look; there is never another.
3. Write the analysis and verdict (`lab note`).
4. **Pass:** `lab test` prints the exact `python -m seer_engine promote …` command, every argument
   filled in from the two recorded trials. **Run it** — you do not ask anyone (design §6). It
   writes the roster row with no `paper_start`, so the next paper night freezes the spec and
   starts its own clock. Then `lab stage`, commit, push, verify. **Real money stays out of
   scope:** design §1 needs ≥ 3 months and ≥ 100 closed paper trades of forward paper first.
5. **Fail:** `test-failed` is final. There is no second look at that configuration, on any
   window. Queue a variation (`lab idea --source-kind variation --parent MNNNN …`) if the
   evidence supports one, and journal what the test window said that the dev window did not.
````

**Why step 4 says "Run it".** `lab test` hands off by *printing* the promote command rather than
calling `commands/promote.py` in-process (Step 7's decision, recorded in the index's Decisions
table). Design §6's "never ask" still holds because an agent, not a human, runs the printed line
— so this sentence is load-bearing. Without it the promotion stops silently at `test-passed` and
the roster entry never happens.

**Impact:** documentation only. `.claude/skills/sera-the-explorer/SKILL.md:11` says only
"promotes eligible methods" and names no command, so it is already accurate and is not edited by
any phase.

---

## Verification

**Build / lint:**

```
cd /home/miftah/.worktrees/seer/build-promotion-path
ruff check engine/src/seer_engine engine/tests
engine/.venv/bin/python -c "import seer_engine.lab.runner, seer_engine.commands.lab"
```

**Tests:**

```
engine/.venv/bin/pytest engine/tests/test_lab_test_window.py -q
engine/.venv/bin/pytest engine/tests/test_lab_runner.py engine/tests/test_lab_store.py \
    engine/tests/test_lab_snapshot.py engine/tests/test_lab_methods.py \
    engine/tests/test_backtest_dev.py engine/tests/test_research_store.py \
    engine/tests/test_fundamentals_coverage.py -q
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q
```

The three `DEV_END` pins (`test_fundamentals_coverage.py:107`, `test_research_store.py:152`,
`test_research_store.py:412`) must pass **unedited**; this phase touches neither constant.

**Manual checks:**

1. **The real lab is untouched and unspent:**
   ```
   engine/.venv/bin/python -m seer_engine lab status | grep "test-window looks used"
   ```
   must print `test-window looks used: 0`. (This is a manual check and deliberately not a test: a
   test pinning the committed database at 0 would fail the day a real look is legitimately spent.)
2. **Nothing lab-stateful is staged:**
   ```
   git status --porcelain lab/lab.sqlite web/data/lab.json engine/.research-test
   ```
   must print nothing.
3. **The command's own surface:**
   ```
   engine/.venv/bin/python -m seer_engine lab test --help
   engine/.venv/bin/python -m seer_engine lab test M0007-RESID --dry-run   # expect exit 2:
   ```
   M0007 is `rejected`, so the refusal must name "only a 'promoted' method reaches the test
   window" and exit 2 — a good live proof that the gate is shut and the dry run spends nothing.

**Exit criteria:**

- `lab test <candidate>` refuses, with exit 2 and a message naming the reason, a candidate whose
  method is not `promoted`, one with no committed pre-registration, one whose pre-registration
  names a different candidate or digest, one with no dev trial, and a second look.
- The second-look refusal is proven **against the database** (`UNIQUE(config_digest, window)` via
  raw SQL, plus the append-only trigger refusing a DELETE), not only in the command.
- One passing run appends exactly one `trials` row with `window='test'`, and
  `store.dev_trial_count` and `store.dev_daily_sharpes` are byte-identical before and after.
- The method ends at `test-passed` or `test-failed`, and every further transition except
  `test-passed → paper` is refused by the trigger.
- `lab status` shows `test-window looks used: 1` in a temp database after a simulated look and
  `0` in the committed one; `store.snapshot`'s `summary.testLooks` agrees (already wired,
  `store.py:833`).
- On a pass, `lab test` prints a ready-to-run `python -m seer_engine promote …` with every
  argument filled in; nothing in this phase writes to Neon or to the roster.
- `SKILL.md`'s `## Promotion` section names **both** subcommands — `lab promote MNNNN` and the
  commit of `docs/lab/prereg/MNNNN.md` as step 1, `lab test` as step 2 — and tells the agent to
  **run** the printed `promote` command on a pass. No sentence in it still says to build
  `lab test` or the test store.
- `engine/.venv/bin/pytest engine/tests -q` is green with no existing test edited.

---

## Handoffs

1. **Settled, not a handoff: the test store carries the lookback run-up.** Phase 2 holds a
   coordinator decision — `engine/.research-test` is built over `STORE_START..window.end`
   (1993-01-29 → the latest session), *not* truncated to 2015-10-19, while the test `Window`'s
   `start` of 2015-10-19 is what floors the run in `dev.candidate_window`. So a 200-session
   candidate's one look opens on 2015-10-19, not ten months late. Nothing in this phase changes.
2. **Settled, not a handoff: the prereg records which gate is which.** This phase decided the
   test verdict is the five design §1 go-live conditions with **no DSR condition**. Phase 3's
   `gate` field records the **dev** gate the variant passed (five conditions *and* DSR ≥ 0.95),
   and phase 3's plan has been edited so `render`'s prose and `gate_text`'s docstring both say
   that the test look is judged by the five alone with DSR recorded, not applied. The two
   cannot drift silently any more.
3. **Not this phase's to fix: the 100-trade condition on an 11-year window.** `>= 100 trades` was
   calibrated on the ~20-year dev window. Applied unchanged to a ~11-year test window it is a
   materially harder bar, and `test-failed` is final. Changing the gate is explicitly out of this
   phase's scope (`satisfies: R2` only; the gate serves no R here), so the condition is applied
   as-is, printed in both the dry run and the verdict so it is never a surprise. **Suggested
   follow-up, for the owner, not for this plan set:** a `lab insight --kind risk` recording that
   the condition is window-length-dependent, before the first real look is spent.
4. **A test-window panel-coverage measure.** `lab test` deliberately does not call
   `runner.preflight_data`: `fundamentals.coverage` measures over `WINDOW_END`, pinned equal to
   `DEV_END` by a test this set must not edit. What remains is the one-line empty-panel refusal in
   `run_test`. Generalising `coverage` to an arbitrary window is a separate change, for whoever
   first promotes a `MarketAware` method.
5. **In-process promotion — decided, not open.** The set's owner has accepted the printed
   hand-off; it is recorded in the index's `## Decisions` table (fork "invoke promote.py
   in-process vs print the command"). `lab test` prints the filled-in command and SKILL.md
   (Step 10, step 4) tells the agent to run it, which is what keeps design §6's "never ask"
   true. If it is ever revisited, `_promote_argv` is already the argv and the change is one
   `subprocess.run(argv, check=False)` behind a `--promote` flag — but that is a later change,
   not an open question in this plan set.
6. **Stale label fixed in passing, deliberately:** `lab status`'s `"Dev-eligible / promoted"`
   heading listed only `dev-eligible` rows. It became `"Dev-eligible"` in Step 6c because this
   phase adds the `"Promoted (pre-registered)"` row beside it. No other `_status` behaviour changed.

---

## Rollback

This phase is one commit on `feature/build-promotion-path`; `git revert` it.

It is additive by construction, so reverting it cannot disturb anything that was working:

- `engine/src/seer_engine/lab/runner.py` — the revert removes an appended section plus two import
  names and a docstring. `preflight`, `preflight_data`, `trial_rows` and `run_method` are
  byte-identical to before this phase and after it, so `lab run` is unaffected either way.
- `engine/src/seer_engine/commands/lab.py` — the revert removes one subparser, one `_HANDLERS`
  entry, four helpers and four status headings. Every other subcommand is untouched.
- `engine/tests/labkit.py` — three appended functions and one import line.
- `engine/tests/test_lab_test_window.py` — deleted whole.
- `.claude/skills/.../SKILL.md` — the whole `## Promotion` section reverts to its previous text,
  "build `lab test` if it does not exist yet", which is
  what it said before.

**There is no lab state to unwind.** This phase writes no row to `lab/lab.sqlite`, spends no
test-window look, changes no recorded trial, creates no store on disk and touches no remote
database. The committed lab reads `test-window looks used: 0` before the phase and after it.

# Phase 2: `lab gate`: price the shared SPY 200-day gate across the lab, report only

**Plan set:** `LAB_BRAKES_AND_GATE_PLAN.md`
**Analysis:** `docs/analyzer/20261012-124247-B4K9_code_analyzer.md`
**Satisfies:** R2 — interrogate the shared SPY 200-day gate that §2 of the handover showed is
nearly all one year of value and a drag since 2009
**Depends on:** Phase 1 — **not for a symbol, for a file.** This phase imports nothing phase 1
creates and reads nothing phase 1 changes, but both edit
`engine/src/seer_engine/commands/lab.py`, and this plan set runs its phases concurrently in one
shared worktree with one git index. Two sessions editing one file that way is the failure this
set must not have, so the reconciler serialised them (C4): phase 1 lands first, and every quote of
`commands/lab.py` below is **the file as it will look after phase 1**.
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/lab`

---

## Goal

After this phase the lab can ask one question of every book it has ever recorded: *how much of
this result came from the shared SPY 200-day trend gate?* `lab gate` re-runs each recorded dev
variant twice on the dev window — once as recorded, once with that one gate switched off and
nothing else moved — and prints the whole-window and per-era lead over deposit-matched SPY side by
side. The gate is found and switched off **generically**, by a recursive `dataclasses.replace`
walk over the params tree, so no method file changes and no method id is minted; a variant whose
gate the walk cannot identify is reported as such and **never run as if the gate were off**. The
command writes at most one journal `observation` per method and no trial, ever.

## Interface Contract

The reconciler reads this section to detect cross-phase conflicts.

**Creates — new module `engine/src/seer_engine/lab/gate_probe.py`:**

| name | kind |
|---|---|
| `gate_probe.GATE_SYMBOL` = `"SPY"`, `GATE_N` = `200`, `GATE` = `("SPY", 200)` | const |
| `gate_probe.GATED` = `"gated"`, `UNGATED` = `"ungated"`, `MODES` | const |
| `gate_probe.ARM_SUFFIX` = `"-NOGATE"`, `ARM_HEAD`, `ARM_LABEL` | const |
| `gate_probe.CARRIES`, `NO_GATE`, `REFUSED` (the three `Variant.status` values) | const |
| `gate_probe.CONTROLS`, `CORE_CONTROLS`, `IMPURE_CONTROLS` | const |
| `gate_probe.NOGATE_SUSPECT` = `0.01` | const |
| `gate_probe.GateOffRefused` (subclass of `ValueError`) | class |
| `gate_probe.gate_off(params) -> tuple[Any, tuple[str, ...]]` | func |
| `gate_probe.control_problems() -> tuple[tuple[str, ...], int]` | func |
| `gate_probe.GateParams` (frozen dataclass: `inner_params`, `tally`) | class |
| `gate_probe.GateAllocator` (`id = f"NOGATE-{inner.id}"`), `wrapper_for(inner)` | class/func |
| `gate_probe.arm_id_for(cid, suffix, taken)`, `arm_candidate(...)`, `arms_for(v)` | func |
| `gate_probe.Variant`, `MethodPlan` | class |
| `gate_probe.resolve_method`, `recorded_method_ids`, `plan_method`, `plan_methods` | func |
| `gate_probe.arm_of`, `measure`, `measure_store` | func |
| `gate_probe.VariantRow`, `MethodReport`, `compare` | class/func |
| `gate_probe.format_plan`, `format_report`, `summary_line`, `lab_summary` | func |
| `gate_probe.insight_text`, `journal` | func |
| `gate_probe.CSV_HEADER`, `csv_rows`, `write_csv` | const/func |

**Creates — CLI surface phase 5 runs:**

```
python -m seer_engine lab [--db PATH] gate [M0030 M0053 ...] [--all] [--only IDS]
                                           [--store DIR] [--csv PATH]
                                           [--gated-only] [--no-journal] [--dry-run]
```

**Creates — in `engine/src/seer_engine/commands/lab.py`:** the `gate` subparser block, the
`_gate(conn, args)` handler, the `"gate": _gate` entry in `_HANDLERS`, and the `lab gate …` stanza
in the module docstring.

**Creates — `engine/tests/test_lab_gate_probe.py`** (26 tests).

**Modifies:** `engine/package_readme.md` — the `Last Updated` line, one new module-map line for
`gate_probe.py`, **and** clauses on the `method.py` / `store.py` / `runner.py` module-map lines
for phase 1's amendment mechanism (reconciler, C5: phase 1 handed its readme line here so the file
is touched once, which is safe because phase 2 now depends on phase 1).

**Deletes:** none. **Renames:** none. **Signature changes:** none.

**Requires (from earlier phases):** no symbol, but **phase 1 must have landed** (reconciler, C4).
It adds `--amend` to the `run` subparser (after `commands/lab.py:195`) and rewrites `_run`'s tail,
which shifts every line number below those points. Re-read the file and locate the insertion
points by their surrounding code, not by the line numbers quoted here — those were measured at
base commit `d3c1ec4`, before phase 1. Phase 1 also touches one line of `lab/exposure.py`
(`:500`'s `by_id` comprehension, reconciler C6); this phase **imports** `exposure.py` and edits
none of it, so that change is invisible here.

**Line numbers in this plan, and how to use them after phase 1.** Every `commands/lab.py` line
number below is at `d3c1ec4`. Phase 1 adds roughly a dozen lines inside the `run` subparser near
`:195` and roughly a dozen more at the end of `_run` near `:1399`. The module docstring stanza
(Step 2, `:73`) is **above** both and does not move; the `gate` subparser (Step 3, `:418`), the
`_gate` handler (Step 4, `:2293`) and the `_HANDLERS` entry (Step 5, `:2447`) are all **below**
both and shift down by that amount. Each step names the code it sits between; use that.

**Leaves alone (owned by others):**

- `engine/src/seer_engine/lab/exposure.py` — **imported, never edited** (`ERAS`, `ERA_LABELS`,
  `WHOLE`, `Arm`, `StoreRun`, `Tally`, `load_dev_store`).
- `lab/method.py`, `lab/store.py`, `lab/runner.py`, `lab/prereg.py`, `lab/remeasure.py` — phase 1.
- every `lab/methods/mNNNN_*.py` — phases 3 and 4. **This phase adds no candidate to any method
  file**, which is the whole point of a generic transform.
- the ten `Lab N (dev trials)` strings in `commands/lab.py` (lines 1399, 1684, 1718, 1739, 1785,
  1817, 1870, 1923, 2238, 2287) — R5, phase 6, surfaced not fixed. **The new `_gate` handler does
  not add an eleventh** (reconciler, C8): it prints both numbers under distinct labels instead.
  Invariant 9 forbids editing the ten; it does not oblige this phase to write another one. After
  this phase, `grep -c 'Lab N (dev trials)' engine/src/seer_engine/commands/lab.py` still returns
  **10**, which is what phase 6's memo and its own exit check assert.
- `lab/lab.sqlite` and `web/data/lab.json` — phase 5, through `lab stage`. This phase commits
  neither.
- `trials`, `trial_moments`, `trial_funding`, `trial_provenance` — never written.

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/gate_probe.py` | create | the whole diagnostic: the transform, the counting wrapper, the planner, the measurement, the report, the CSV |
| `engine/src/seer_engine/commands/lab.py` | modify | docstring stanza after the `lab exposure` one (after line 73); the `gate` subparser after the `exposure` parser block (after line 417); `_gate` after `_exposure` (after line 2292); `"gate": _gate` in `_HANDLERS` (after line 2447) |
| `engine/tests/test_lab_gate_probe.py` | create | 26 tests |
| `engine/package_readme.md` | modify | line 4 (`Last Updated`, naming both landings); a new `gate_probe.py` module-map line after the `exposure.py` one (line 158 at `d3c1ec4`); and an appended clause each on the `method.py`, `store.py` and `runner.py` module-map lines for phase 1's amendment mechanism (C5) |

---

## Measured before planning, 2026-10-12, in this worktree

Every figure below was taken today, on this branch, with
`/home/miftah/seer/engine/.venv/bin/python` and
`PYTHONPATH=/home/miftah/.worktrees/seer/lab-brakes-and-gate/engine/src`. Invariant 10: a measured
number carries its date and what it was measured on.

| what | value | how |
|---|---|---|
| suite baseline | **4364 passed, 3 skipped, 100.58s** | `pytest engine/tests` with Postgres up |
| dev store fingerprint | `77c37d553508` | `manifest.json` of `/home/miftah/seer/engine/.research` |
| dev store price fingerprint | `5451195fd552` | `research.price_fingerprint_of(manifest["files"])` |
| `lab/lab.sqlite` md5 | `4a34ddb823ec88a5e86afeb5d7e1b7c9` | `md5sum`, before any lab command ran |
| recorded dev trial rows | 354 | `SELECT DISTINCT method_id, candidate_id FROM trials WHERE window='dev'` on a **copy** |
| of those, still in a method file | 300 | 54 recorded candidate ids are gone from their files |
| **carry the shared SPY-200 gate and transform cleanly** | **225** | the prototype of `gate_off` below |
| carry no SPY-200 gate the walk can see | 69 | — |
| gate found, but the method **refuses** it off | **6** | `M0054-HALF-PARK`, `M0054-PARK-SPY`, `M0101-BAND-3`, `M0101-BAND-5`, `M0101-CTRL`, `M0101-FABER` |
| bracket-engine variants | 0 | — |

The store's two fingerprints are **unchanged** from the handover's §6 figures. Invariant 8 holds
and **nothing is rebuilt**.

### The transform, validated against the lab's own recorded controls

Run today against the committed method files. `gate_off(X.params)` must equal the recorded
sibling's params **exactly**:

| recorded variant | recorded sibling | result |
|---|---|---|
| `M0002-MED-TV12` | `M0002-MED-TV12-NOTREND` | **match** |
| `M0007-N20` | `M0007-N20-NOTREND` | **match** |
| `M0008-C10` | `M0008-C10-NOTREND` | **match** |
| `M0024-SAME-N20` | `M0024-SAME-N20-NOTREND` | **match** |
| `M0064-P50` | `M0064-P50-NOGATE` | **match** |
| `M0030-C50T` core leg | `M0030-C50A` core leg | **match** (`TimingParams(hold='SPY', signal='SPY', rule='always', n=200)` — exactly `ALWAYS_SPY`) |
| `M0001-TV10` | `M0001-TV10-NOTREND` | **differs, and correctly so** |

The `M0001` row is a finding, not a bug, and it is why `IMPURE_CONTROLS` exists in the code:
`M0001-TV10` runs `OwnVolParams(..., n=63)` and its recorded "no trend filter" sibling runs
`n=126`. The lab's own gate control on M0001 **also moved the own-vol window**, so it was never a
clean control. The probe's transform is the clean one, and the module says so in a comment with
the date.

Also measured: `gate_off(M0030-C50T) == gate_off(M0030-C50A)` — both converge on the same fully
ungated blend, which is the params the index's `M0030-C50A-NOGATE` candidate (phase 3) pins. Phase
3 and this phase agree by construction.

---

## Implementation Steps

### Step 1: `engine/src/seer_engine/lab/gate_probe.py` (new file, whole contents)

**File:** `engine/src/seer_engine/lab/gate_probe.py` (new; sits beside `exposure.py`)
**Change:** the whole diagnostic.

```python
"""``lab gate M0030 [M0053 ...]``: what the shared SPY 200-day gate is worth, book by book.

Four of the five live books go to cash on **the same 28.3% of their decision days** -- 67 of 237
monthly decisions, bit-identical across them -- because they sit behind the same rule: SPY's close
against its own 200-day average, read on the same monthly dates (measured 2026-10-12,
``docs/backtests/2026-10-12-exposure-diagnostic.md``). That one shared rule produced the identical
**+34.8 point lead in 2008** in every one of them. It is not five discoveries; it is one trade,
shared five ways.

The lab already holds a recorded control that prices it on one book -- ``M0024-SAME-N20`` against
``M0024-SAME-N20-NOTREND`` -- and the control is damning: **+2.7 a year whole-window gated against
+1.0 ungated, but after 2009 the gated version trails by 5.4 while the ungated one leads by 1.5**
(same measurement, same date). Nearly all of the gate's whole-window value is one year, and it has
been a drag for six. One control on one book cannot settle that for a shared component, and the
gate is shared: changing it moves every book at once. So this command prices it **everywhere the
lab has a record of it**, on the dev window, as a report.

**Two arms, one allocator.** For each recorded dev variant this runs the *same* allocator on the
*same* window at the *same* recorded capital and funding, twice, differing only in its params:

==============  =======================================================================
arm             what it prices
==============  =======================================================================
``gated``       the candidate used unchanged: the reference, and the reproduction check
                against the number the lab recorded
``-NOGATE``     the same candidate with the shared SPY 200-day gate switched off and
                **nothing else moved**: the counterfactual the lab has never had for
                most of its books
==============  =======================================================================

**The gate is found generically, and refused when it cannot be.** ``gate_off`` is a recursive
``dataclasses.replace`` walk over the params tree with exactly two rewrites, both pinned to the
shared gate and to nothing else:

* a ``compare=True`` field named ``trend`` holding ``("SPY", 200)`` becomes ``None`` -- the form
  ``f_factor.trend_on`` reads, which is the single read every gated stock book shares;
* a ``TimingParams(signal="SPY", rule="sma", n=200)`` becomes ``rule="always"`` -- the blend-core
  form of the same gate (``m0030_spy_core_momentum_satellite``'s ``TIMED_SPY`` -> ``ALWAYS_SPY``).

Everything else **raises**. A ``trend`` that is not ``("SPY", 200)``, a ``TimingParams`` on another
signal, rule or length, a params value whose ``__post_init__`` rejects the gateless version -- each
is a ``GateOffRefused``, and the variant is listed as *not transformable* and **never run**. Six
recorded variants are exactly that case today (measured 2026-10-12): ``M0054``'s park arms, whose
``ParkParams`` says *"inner must have a trend switch; without one there is nothing to park"*, and
``M0101``'s four, whose ``SwitchParams`` says the same of its band switch. Guessing at those would
produce a number that looks like a gate-off counterfactual and is not one, which is worse than no
number.

**The transform checks itself against the lab's own record before it measures anything.**
``control_problems()`` runs ``gate_off`` over five recorded pairs (``M0007-N20`` ->
``M0007-N20-NOTREND`` and four more) plus ``M0030-C50T``'s core leg against ``M0030-C50A``'s, and
demands they match the recorded sibling exactly. ``lab gate`` refuses (exit 2) if any fails. The
transform is not trusted because it reads right; it is trusted because the lab already contains six
configurations it must reproduce and does.

``M0001-TV10`` / ``M0001-TV10-NOTREND`` is deliberately **not** in that set: measured 2026-10-12,
the recorded "no trend filter" sibling also moves the own-vol window from 63 to 126 sessions, so it
was never a clean gate control. It is listed in ``IMPURE_CONTROLS`` with that reason, and the probe
is the clean control M0001 never had.

**A variant with no gate is not asserted to be ungated.** When the walk finds no site, the probe
still runs the single recorded arm through its counting wrapper and reads ``Tally.empty_share`` --
the share of decision sessions on which the allocator returned no targets at all. A book that holds
nothing on a meaningful share of its decision days while declaring no SPY-200 gate has a brake this
transform does not reach (``M0012``'s weekly SPY-200 read lives in ``GateParams.smas``, not in a
``trend`` field; ``M0039``'s lives in a VIX term-structure signal). The report flags those loudly
instead of printing "ungated" beside them. That flag is a **measurement**, not a word list.

**A report, not a trial.** Nothing is written but, unless ``--no-journal``, one ``observation`` per
method: no ``trials``, ``trial_moments``, ``trial_funding`` or ``trial_provenance`` row, no status,
no pre-registration, and no method id is minted -- which matters here more than convenience,
because ``N`` for the deflated Sharpe counts distinct **methods** and every new one raises the luck
hurdle for the whole lab retroactively (``lab/npolicy.py``; N = 74 under the ``methods`` policy,
measured 2026-10-12). ``store.dev_trial_count`` and ``store.test_looks`` are read before and after
and printed, so the invariant is visible rather than merely asserted. ``dev.run_registry`` is
called with **no** ``window=`` keyword, so D9's dev default binds and nothing here can name the
test window.

**The arms are compared with each other, never with the recorded trial.** The gated arm's total
return is checked against the recorded one at ``real_costs.REPRO_TOL`` and printed as information,
the way ``lab costs`` prints it. A store or an engine that moved since a trial ran makes that check
fail without making the two arms any less comparable, and no conclusion here rests on a recorded
number beside a re-run one.
"""

from __future__ import annotations

import csv
import gc
import logging
import math
import sqlite3
import time
from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field, fields, is_dataclass, replace
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from seer_engine import research
from seer_engine.backtest import dev
from seer_engine.backtest.dev import Candidate, DevRow
from seer_engine.backtest.metrics import fmt_num, fmt_pct, fmt_pf, fmt_signed_pct
from seer_engine.commands.backtest_dev import month_end_curve
from seer_engine.lab import hardgate, runner, store
from seer_engine.lab import walkforward as wf
from seer_engine.lab.exposure import ERA_LABELS, ERAS, WHOLE, Arm, StoreRun, Tally, load_dev_store
from seer_engine.lab.method import METHOD_ID, Method, discover
from seer_engine.lab.real_costs import REPRO_TOL
from seer_engine.sim.book import Target
from seer_engine.sim.contributions import ContributionSchedule
from seer_engine.sim.rules import is_bracket
from seer_engine.strategies.allocator import Allocator, prepare_for
from seer_engine.strategies.base import History
from seer_engine.strategies.f_index import TimingParams

log = logging.getLogger(__name__)

# --------------------------------------------------------------------------- the gate

#: The shared gate, in the one form every gated book in this lab expresses it:
#: ``f_factor.FactorParams.trend == ("SPY", 200)``, read by ``f_factor.trend_on``.
GATE_SYMBOL = "SPY"
GATE_N = 200
GATE: tuple[str, int] = (GATE_SYMBOL, GATE_N)
#: The one ``compare=True`` field name that carries it as a tuple.
TREND_FIELD = "trend"
#: The ``TimingParams.rule`` that *is* the gate, and the one that is the gate switched off.
GATE_RULE = "sma"
OFF_RULE = "always"

# --------------------------------------------------------------------------- the two arms

GATED = "gated"
UNGATED = "ungated"
MODES: tuple[str, ...] = (GATED, UNGATED)

#: Appended to the recorded candidate id for the gate-off arm. Candidate ids must match
#: ``dev._ID`` (``[A-Z0-9]+(-[A-Z0-9]+)*``), which this keeps -- and so do its numbered fallbacks.
ARM_SUFFIX = "-NOGATE"
ARM_LABEL: Mapping[str, str] = {
    GATED: "as recorded, with its SPY 200-day gate",
    UNGATED: "the same book with the shared SPY 200-day gate switched off",
}
ARM_HEAD: Mapping[str, str] = {GATED: "as recorded", UNGATED: "gate off"}

# --------------------------------------------------------------------------- classification

CARRIES = "carries"   # the shared gate was found and can be switched off
NO_GATE = "no-gate"   # no site found: one arm only, and the empty-day cross-check
REFUSED = "refused"   # a site was found but the gateless configuration is rejected

#: Below this share of decision sessions, "held nothing" is unfilled slots rather than a brake.
NOGATE_SUSPECT = 0.01


class GateOffRefused(ValueError):
    """The gate in this params tree cannot be switched off without guessing.

    Raised rather than returned, and never swallowed into a silent "no gate here": a variant whose
    gate this walk cannot identify is reported as not transformable and does not get a gate-off
    arm. The alternative -- running it unchanged and labelling the column "gate off" -- would put a
    number in the grid that is not the thing the column claims to measure.
    """


# --------------------------------------------------------------------------- the transform


def _is_trend_pair(value: object) -> bool:
    """``("SPY", 200)``'s shape: a 2-tuple of a str and a non-bool int."""
    return (
        isinstance(value, tuple)
        and len(value) == 2
        and isinstance(value[0], str)
        and isinstance(value[1], int)
        and not isinstance(value[1], bool)
    )


def _walk(value: Any, path: str, sites: list[str]) -> Any:
    """``value`` with every shared-gate site switched off, appending each site to ``sites``.

    Returns the **same object** when nothing in its subtree changed, so a caller can test identity
    to know whether a rewrite happened anywhere.

    An ``Allocator`` is returned untouched: ``BlendPart.allocator`` holds one, allocators are
    module singletons the registry prepares by identity, and some are dataclasses that this walk
    would otherwise descend into and rebuild.
    """
    if isinstance(value, Allocator):
        return value
    if isinstance(value, TimingParams):
        if value.rule == OFF_RULE:
            return value  # already off: M0030's ALWAYS_SPY core
        if (value.signal, value.rule, value.n) == (GATE_SYMBOL, GATE_RULE, GATE_N):
            sites.append(f"{path}: timing rule {GATE_RULE!r} -> {OFF_RULE!r}")
            return replace(value, rule=OFF_RULE)
        raise GateOffRefused(
            f"{path} is TimingParams(signal={value.signal!r}, rule={value.rule!r}, n={value.n}), "
            f"which is a timing gate but not the shared {GATE_SYMBOL} {GATE_N}-day one; this "
            f"probe will not guess what switching it off means"
        )
    if is_dataclass(value) and not isinstance(value, type):
        changes: dict[str, Any] = {}
        for f in fields(value):
            if not f.compare:
                continue  # a compare=False field is not part of the configuration
            current = getattr(value, f.name)
            if f.name == TREND_FIELD:
                if current is None:
                    continue
                if not _is_trend_pair(current):
                    raise GateOffRefused(
                        f"{path}.{TREND_FIELD} is {current!r}, not a (symbol, n) pair; this probe "
                        f"only knows the {GATE!r} form of the gate"
                    )
                if tuple(current) != GATE:
                    raise GateOffRefused(
                        f"{path}.{TREND_FIELD} is {tuple(current)!r}, not the shared {GATE!r} "
                        f"gate; switching off a different gate is a different question"
                    )
                sites.append(f"{path}.{TREND_FIELD} -> None")
                changes[f.name] = None
                continue
            rewritten = _walk(current, f"{path}.{f.name}", sites)
            if rewritten is not current:
                changes[f.name] = rewritten
        if not changes:
            return value
        try:
            return replace(value, **changes)
        except (TypeError, ValueError) as e:
            raise GateOffRefused(
                f"{type(value).__name__} refuses the gate off: {e}. This method is built around "
                f"the gate being on, so there is no 'same book without it' to measure"
            ) from e
    if isinstance(value, tuple):
        out = tuple(_walk(v, f"{path}[{i}]", sites) for i, v in enumerate(value))
        if any(a is not b for a, b in zip(out, value)):
            return out
        return value
    return value


def gate_off(params: Any) -> tuple[Any, tuple[str, ...]]:
    """``params`` with the shared SPY 200-day gate switched off, and the sites that were switched.

    ``(params, ())`` when the walk reaches no site -- which means *this probe saw no shared gate*,
    not *this book has no brake*. ``GateOffRefused`` when a gate-shaped thing is found that is not
    the shared gate, or when the gateless configuration is rejected by the params type itself.

    The rewrite goes through ``dataclasses.replace``, so every ``__post_init__`` on the way back up
    runs: a method that validates "this book must carry a trend switch" refuses here rather than
    producing a mis-labelled column. Only ``compare=True`` fields are visited, which is the same
    set ``backtest/registry._canon`` renders into a ``config_digest``, so a site this walk can
    change is by construction a site that is part of the recorded configuration.
    """
    sites: list[str] = []
    return _walk(params, "params", sites), tuple(sites)


# --------------------------------------------------------------------------- the self-check

#: ``(gated id, the recorded sibling that is the same book with the gate off)``. Every pair is a
#: configuration the lab already holds, so the transform is checked against the record rather than
#: against this module's own opinion. All five matched when measured 2026-10-12.
CONTROLS: tuple[tuple[str, str], ...] = (
    ("M0002-MED-TV12", "M0002-MED-TV12-NOTREND"),
    ("M0007-N20", "M0007-N20-NOTREND"),
    ("M0008-C10", "M0008-C10-NOTREND"),
    ("M0024-SAME-N20", "M0024-SAME-N20-NOTREND"),
    ("M0064-P50", "M0064-P50-NOGATE"),
)

#: ``(gated id, sibling id, the index of the blend part that must match)``. ``M0030-C50A`` is the
#: recorded always-on core with the satellite still gated, so only its core leg is a control for
#: the ``TimingParams`` half of the transform. Matched when measured 2026-10-12.
CORE_CONTROLS: tuple[tuple[str, str, int], ...] = (("M0030-C50T", "M0030-C50A", 0),)

#: Recorded pairs that *look* like gate controls and are not, with why. Listed so a reader who
#: finds them does not conclude the transform is broken, and so nobody adds them to ``CONTROLS``.
#: Measured 2026-10-12: M0001-TV10 runs the own-vol window at 63 sessions and its "no trend filter"
#: sibling at 126, so the recorded pair moves two things at once and was never a clean control.
IMPURE_CONTROLS: Mapping[tuple[str, str], str] = {
    ("M0001-TV10", "M0001-TV10-NOTREND"):
        "the recorded sibling also moves the own-vol window from 63 to 126 sessions",
}


def _candidate_in(methods: Mapping[str, Any], cid: str) -> Candidate | None:
    method = methods.get(cid.split("-")[0])
    if method is None:
        return None
    return next((c for c in method[0].candidates if c.id == cid), None)


def control_problems() -> tuple[tuple[str, ...], int]:
    """``(problems, checked)``: where the transform disagrees with the lab's own recorded controls.

    A control whose method file no longer carries either side is **skipped**, not failed -- a
    method file is allowed to change and that is not this probe's business -- and ``checked`` says
    how many were actually compared, so a silently empty check cannot pass for a green one. The
    test suite pins ``checked`` at the full set against the committed files.
    """
    methods = discover()
    problems: list[str] = []
    checked = 0
    for gated_id, off_id in CONTROLS:
        a, b = _candidate_in(methods, gated_id), _candidate_in(methods, off_id)
        if a is None or b is None:
            continue
        checked += 1
        try:
            got, sites = gate_off(a.params)
        except GateOffRefused as e:
            problems.append(f"{gated_id}: the transform refuses its own control ({e})")
            continue
        if not sites:
            problems.append(f"{gated_id}: the transform found no gate, but {off_id} is recorded")
        elif got != b.params:
            problems.append(
                f"{gated_id}: the transform gives {got!r}, but the recorded {off_id} is {b.params!r}"
            )
    for gated_id, off_id, part in CORE_CONTROLS:
        a, b = _candidate_in(methods, gated_id), _candidate_in(methods, off_id)
        if a is None or b is None:
            continue
        checked += 1
        try:
            got, _sites = gate_off(a.params)
        except GateOffRefused as e:
            problems.append(f"{gated_id}: the transform refuses its own control ({e})")
            continue
        try:
            mine, theirs = got.parts[part], b.params.parts[part]
        except (AttributeError, IndexError):
            problems.append(f"{gated_id}: part {part} is not a blend leg on both sides any more")
            continue
        if mine != theirs:
            problems.append(
                f"{gated_id}: leg {part} transforms to {mine!r}, but {off_id}'s is {theirs!r}"
            )
    return tuple(problems), checked


# --------------------------------------------------------------------------- the wrapper


@dataclass(frozen=True)
class GateParams:
    """One arm's params: the allocator's own params, plus the arm's own counter.

    The wrapper changes nothing about the allocation; it exists only so both arms report the share
    of decision sessions on which the allocator returned no targets at all. That number is how the
    gated arm proves the gate fired, how the gate-off arm proves it stopped firing, and how a
    variant the transform calls ungated is cross-examined (see the module docstring).

    ``tally`` is ``compare=False`` so the params value stays a value; ``as_dict`` follows every
    other params class in the repo and is never read on the run path.
    """

    inner_params: Any
    tally: Tally = field(default_factory=Tally, compare=False, repr=False)

    def as_dict(self) -> dict[str, str]:
        inner = getattr(self.inner_params, "as_dict", None)
        rendered = dict(inner()) if callable(inner) else {"repr": repr(self.inner_params)}
        return {f"inner.{k}": v for k, v in rendered.items()}


def _params(params: object) -> GateParams:
    if not isinstance(params, GateParams):
        raise TypeError(f"params must be GateParams, got {type(params).__name__}")
    return params


class GateAllocator:
    """A pass-through over its inner allocator that counts its empty decisions.

    Every member delegates and nothing is re-weighted: ``targets`` returns exactly what the inner
    returned. That is deliberate and is itself checked -- the gated arm must reproduce the recorded
    trial's total return, which it cannot do if the wrapper perturbs anything.

    Preparation goes through ``strategies.allocator.prepare_for`` rather than ``LazyPrepared``,
    for the same reason ``exposure.ExposureAllocator`` does: ``LazyPrepared`` calls
    ``inner.prepare(history)`` and so silently loses ``prepare_market``, and twenty method files
    implement ``prepare_market`` to read the point-in-time fundamentals or dividend panel. A
    wrapper built the other way would quietly measure a bar-only version of each of them and report
    the difference as a finding about the gate.

    ``market_fields`` is forwarded so a future caller that consults it -- ``runner.market_fields``
    does -- sees the inner's declaration rather than the default.
    """

    __slots__ = ("id", "inner")

    def __init__(self, inner: Allocator) -> None:
        if not isinstance(inner, Allocator):
            raise TypeError(f"inner must be an Allocator, got {type(inner).__name__}")
        self.inner = inner
        self.id = f"NOGATE-{inner.id}"

    @property
    def market_fields(self) -> tuple[str, ...]:
        return tuple(getattr(self.inner, "market_fields", ("fundamentals",)))

    def lookback(self, params: Any) -> int:
        return self.inner.lookback(_params(params).inner_params)

    def symbols(self, params: Any) -> tuple[str, ...]:
        return self.inner.symbols(_params(params).inner_params)

    def uses_members(self, params: Any) -> bool:
        return self.inner.uses_members(_params(params).inner_params)

    def holds(self, params: Any) -> tuple[str, ...]:
        return self.inner.holds(_params(params).inner_params)

    def prepare(self, history: Mapping[str, History]) -> Any:
        return self.inner.prepare(history)

    def prepare_market(self, market: Any) -> Any:
        return prepare_for(self.inner, market)

    def targets(
        self,
        history: Mapping[str, History],
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        p = _params(params)
        out = self.inner.targets(history, members, data_date, held, p.inner_params)
        p.tally.saw(len(out), len(out))
        return out

    def targets_prepared(
        self,
        prepared: Any,
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        p = _params(params)
        out = self.inner.targets_prepared(prepared, members, data_date, held, p.inner_params)
        p.tally.saw(len(out), len(out))
        return out


#: One wrapper per inner allocator **object**, memoized by identity -- ``dev.run_registry`` refuses
#: two different allocator objects that share an ``allocator.id``, and every wrapper's id is
#: derived from its inner's. Module-level because the inner allocators are module singletons and
#: the memo must survive across the chunks of one command. ``lab/`` is not globbed by
#: ``tests/test_strategy_purity.py``, so a lab module may hold state, as ``exposure.py`` already
#: does.
_WRAPPERS: list[tuple[Any, GateAllocator]] = []


def wrapper_for(inner: Allocator) -> GateAllocator:
    """The one ``GateAllocator`` over ``inner``, created on first ask. Keyed by identity."""
    for obj, wrapped in _WRAPPERS:
        if obj is inner:
            return wrapped
    wrapped = GateAllocator(inner)
    _WRAPPERS.append((inner, wrapped))
    return wrapped


# --------------------------------------------------------------------------- building the arms


def arm_id_for(cid: str, suffix: str, taken: AbstractSet[str]) -> str:
    """``cid + suffix``, or the first free numbered form, so an arm never shadows a recorded id.

    ``M0064`` really does hold both ``M0064-P50`` and a recorded ``M0064-P50-NOGATE``, and
    ``dev.run_registry`` is given both the recorded variants and their arms in one call. Two
    candidates sharing an id in one registry call is a measurement that quietly answers about the
    wrong book, so the collision is resolved here and the chosen id is printed in the report.
    ``-NOGATE-2`` still matches ``dev._ID``.
    """
    base = f"{cid}{suffix}"
    if base not in taken:
        return base
    for k in range(2, 100):
        numbered = f"{base}-{k}"
        if numbered not in taken:
            return numbered
    raise store.LabError(f"cannot find a free arm id for {cid}; 98 variants of {base} are taken")


def arm_candidate(c: Candidate, mode: str, inner_params: Any, arm_id: str) -> Candidate:
    """One arm of ``c``: the same allocator wrapped, at ``inner_params``, under ``arm_id``.

    ``rules`` are kept **exactly** as recorded -- unlike ``lab exposure``, which strips the idle
    instrument, because there the parked money is the subject and here only the gate is. ``family``
    stays the method id so an arm can never be mistaken for another family's row.
    ``owner_inputs`` is recomputed, because the ungated arm of a blend stops reading the trend
    symbol and so may declare fewer ETFs.
    """
    arm = Candidate(
        id=arm_id,
        family=c.family,
        rules=c.rules,
        allocator=wrapper_for(c.allocator),
        params=GateParams(inner_params=inner_params),
        rationale=f"{ARM_LABEL[mode]} -- {c.rationale}",
        added=c.added,
        owner_inputs=(),
    )
    return replace(arm, owner_inputs=dev.candidate_owner_inputs(arm))


def arms_for(v: Variant) -> tuple[tuple[str, Candidate], ...]:
    """``(mode, candidate)`` for every arm of one variant, the recorded one first.

    Fresh ``GateParams`` -- and so a fresh ``Tally`` -- on every call: an arm is measured once.
    A variant whose gate the transform refuses, or in which it found none, contributes the gated
    arm only; its ``-NOGATE`` column is the reason it has none, printed in words.
    """
    out: list[tuple[str, Candidate]] = [
        (GATED, arm_candidate(v.candidate, GATED, v.candidate.params, v.gated_arm_id))
    ]
    if v.status == CARRIES:
        out.append((UNGATED, arm_candidate(v.candidate, UNGATED, v.off_params, v.ungated_arm_id)))
    return tuple(out)


# --------------------------------------------------------------------------- what to re-run


@dataclass(frozen=True)
class Variant:
    """One recorded dev variant, classified against the transform before any store loads."""

    candidate: Candidate
    trial_n: int
    trial: sqlite3.Row = field(compare=False, repr=False)
    capital: Decimal
    contributions: ContributionSchedule | None
    status: str                 # CARRIES | NO_GATE | REFUSED
    sites: tuple[str, ...]      # the gate sites the walk switched off (empty unless CARRIES)
    off_params: Any             # the gateless params (None unless CARRIES)
    why: str                    # why it is not transformable (empty unless REFUSED)
    gated_arm_id: str
    ungated_arm_id: str
    recorded_total_return: float | None
    recorded_mar: float | None
    recorded_eligible: bool

    @property
    def funded(self) -> bool:
        return self.contributions is not None


@dataclass(frozen=True)
class MethodPlan:
    method: Method
    variants: tuple[Variant, ...]
    missing: tuple[str, ...]  # recorded candidate ids that are no longer in the method file


def resolve_method(method_id: str) -> Method:
    """The committed ``METHOD`` for a lab method id (``store.LabError`` otherwise)."""
    if not isinstance(method_id, str) or METHOD_ID.fullmatch(method_id) is None:
        raise store.LabError(
            f"{method_id!r} is not a lab method id; `lab gate` takes methods like M0030"
        )
    methods = discover()
    if method_id not in methods:
        raise store.LabError(
            f"no method file for {method_id} in seer_engine/lab/methods/. `lab gate` re-runs the "
            f"committed method file, not a database row"
        )
    return methods[method_id][0]


def recorded_method_ids(conn: sqlite3.Connection) -> tuple[str, ...]:
    """Every method id with a recorded dev trial that still has a method file, in id order.

    ``--all``'s scope. A method whose file is gone is left out here rather than refused, because
    the whole point of ``--all`` is to sweep what the lab can still re-run.
    """
    files = discover()
    rows = conn.execute(
        "SELECT DISTINCT method_id FROM trials WHERE window = 'dev' ORDER BY method_id"
    ).fetchall()
    return tuple(str(r["method_id"]) for r in rows if str(r["method_id"]) in files)


def _f(x: object) -> float | None:
    return None if x is None else float(x)


def _classify(c: Candidate) -> tuple[str, tuple[str, ...], Any, str]:
    """``(status, sites, off_params, why)`` for one candidate, with no store and no bars.

    The allocator is asked to accept the gateless params through its own cheap members
    (``lookback`` / ``symbols`` / ``holds`` / ``uses_members``) before the variant is called
    transformable: a params type can validate while the allocator that reads it cannot, and the
    cost of finding that out at the start of a four-hundred-backtest run is a refusal, not a
    wasted hour.
    """
    try:
        off, sites = gate_off(c.params)
    except GateOffRefused as e:
        return REFUSED, (), None, str(e)
    if not sites:
        return NO_GATE, (), None, ""
    try:
        c.allocator.lookback(off)
        c.allocator.symbols(off)
        c.allocator.holds(off)
        c.allocator.uses_members(off)
    except Exception as e:  # noqa: BLE001 -- an allocator may raise anything about its own params
        return REFUSED, (), None, f"{c.allocator.id} refuses the gateless params: {e}"
    return CARRIES, sites, off, ""


def plan_method(conn: sqlite3.Connection, method_id: str) -> MethodPlan:
    """Every recorded dev variant of ``method_id`` that is still in its method file, classified.

    Resolves recorded capital, funding and the gate classification now, so a trial that cannot be
    re-run as the measurement it was is refused before a store is opened, and so the scope of the
    run is knowable (``--dry-run``) for free. A funded trial's schedule is checked against its
    recorded deposit count here too (``hardgate.trial_deposits`` with an empty curve buckets
    nothing but still raises on a moved schedule).
    """
    method = resolve_method(method_id)
    trials = [t for t in store.trials_of(conn, method.id) if t["window"] == "dev"]
    if not trials:
        raise store.LabError(
            f"{method.id} has no dev trial; `lab gate` re-runs what the lab recorded. Run it with "
            f"`lab run {method.id}` first"
        )
    by_id = {c.id: c for c in method.candidates}
    taken: set[str] = set(by_id) | {str(t["candidate_id"]) for t in trials}
    seen: set[str] = set()
    variants: list[Variant] = []
    missing: list[str] = []
    for t in trials:  # trials_of orders by n: the first recording of a variant wins
        cid = str(t["candidate_id"])
        if cid in seen:
            continue
        seen.add(cid)
        candidate = by_id.get(cid)
        if candidate is None:
            missing.append(cid)
            continue
        if is_bracket(candidate.rules):
            raise store.LabError(
                f"{cid} runs the bracket engine ({candidate.rules.id}), whose strategies are not "
                f"allocators and carry no params the trend gate lives in. `lab gate` measures book "
                f"methods; there is no SPY 200-day gate here to switch off"
            )
        n = int(t["n"])
        capital = runner.recorded_capital(conn, n)
        contributions = runner.recorded_contributions(conn, n)
        if contributions is not None:
            hardgate.trial_deposits(conn, t, [])
        status, sites, off, why = _classify(candidate)
        ungated_id = arm_id_for(cid, ARM_SUFFIX, taken)
        taken.add(ungated_id)
        variants.append(
            Variant(
                candidate=candidate,
                trial_n=n,
                trial=t,
                capital=capital,
                contributions=contributions,
                status=status,
                sites=sites,
                off_params=off,
                why=why,
                gated_arm_id=cid,
                ungated_arm_id=ungated_id,
                recorded_total_return=_f(t["total_return"]),
                recorded_mar=_f(t["mar"]),
                recorded_eligible=bool(t["eligible"]),
            )
        )
    if not variants:
        raise store.LabError(
            f"{method.id}: none of its recorded variants ({', '.join(missing)}) is in its method "
            f"file any more; there is nothing to re-run"
        )
    return MethodPlan(method, tuple(variants), tuple(missing))


def plan_methods(
    conn: sqlite3.Connection,
    ids: Sequence[str],
    only: str | None = None,
    *,
    gated_only: bool = False,
) -> tuple[MethodPlan, ...]:
    """``plan_method`` for each id, upper-cased and de-duplicated in the order given.

    ``only`` is a comma-separated list of recorded candidate ids; an id that matches no planned
    variant is a refusal rather than a silently empty run. ``gated_only`` drops the variants the
    transform found no gate in, which is the fast path for a targeted question -- at the cost of
    the empty-day cross-check that keeps "no gate found" honest, so the report says when it is on.
    """
    out: list[MethodPlan] = []
    done: set[str] = set()
    for raw in ids:
        mid = str(raw).strip().upper()
        if mid in done:
            continue
        done.add(mid)
        out.append(plan_method(conn, mid))
    if not out:
        raise store.LabError("name at least one method, e.g. `lab gate M0030`, or pass --all")
    if only is not None:
        wanted = {part.strip().upper() for part in str(only).split(",") if part.strip()}
        if not wanted:
            raise store.LabError("--only was given but names no candidate id")
        narrowed: list[MethodPlan] = []
        kept: set[str] = set()
        for plan in out:
            keep = tuple(v for v in plan.variants if v.candidate.id in wanted)
            kept.update(v.candidate.id for v in keep)
            if keep:
                narrowed.append(replace(plan, variants=keep))
        unknown = sorted(wanted - kept)
        if unknown:
            raise store.LabError(
                f"--only names {', '.join(unknown)}, which is not a recorded dev variant of "
                f"{', '.join(p.method.id for p in out)}"
            )
        out = narrowed
    if gated_only:
        trimmed = [
            replace(p, variants=tuple(v for v in p.variants if v.status == CARRIES)) for p in out
        ]
        out = [p for p in trimmed if p.variants]
        if not out:
            raise store.LabError(
                "--gated-only was given, and none of the named variants carries the shared "
                f"{GATE_SYMBOL} {GATE_N}-day gate; drop the flag to see why"
            )
    return tuple(out)


# --------------------------------------------------------------------------- one arm's numbers


def arm_of(
    mode: str,
    v: Variant,
    row: DevRow,
    curve: Sequence[tuple[date, float]],
    deposits: Mapping[date, float],
    bench: Sequence[tuple[date, float]],
) -> Arm:
    """One arm's ``exposure.Arm`` from its ``DevRow``, its monthly curve and the benchmark's.

    The shape and the per-era path are ``exposure.arm_of``'s, deliberately: the two commands must
    produce the same kind of number or their write-ups cannot be read beside each other. It is
    re-stated here rather than called because ``exposure.arm_of`` reads the tally off an
    ``ExposureParams`` by type, and ``exposure.py`` is owned by a landing this phase must not edit.

    **Whole window** comes from the ``DevRow``: the money-weighted return when the run was funded
    and the CAGR otherwise, against ``row.spy_tr``'s same measure -- which ``dev._run`` already
    makes deposit-matched. **Per era** goes through ``wf.measure``, which de-funds the whole curve
    with ``regime.defunded`` *before* it cuts it, against the recorded ``REF-SPY-HOLD`` curve
    sliced the same way; a second reconstruction would be a second chance to read the owner's
    deposits as edge.
    """
    m = row.stats.metrics
    yearly = m.mwr if m.mwr is not None else m.cagr
    spy_yearly = row.spy_tr.mwr if row.spy_tr.mwr is not None else row.spy_tr.cagr
    params = row.candidate.params
    tally = params.tally if isinstance(params, GateParams) else None
    mine: dict[str, float | None] = {WHOLE: yearly}
    theirs: dict[str, float | None] = {WHOLE: spy_yearly}
    for label, start, end in ERAS:
        got = wf.measure(curve, start, end, deposits)
        ref = wf.measure(bench, start, end)
        mine[label] = None if got is None else got.cagr
        theirs[label] = None if ref is None else ref.cagr
    lead = {
        label: (
            None
            if mine[label] is None or theirs[label] is None
            else mine[label] - theirs[label]
        )
        for label in ERA_LABELS
    }
    return Arm(
        mode=mode,
        candidate_id=row.candidate.id,
        start=row.start,
        end=row.end,
        funded=v.funded,
        exposure=float(row.stats.exposure),
        total_return=m.total_return,
        yearly=yearly,
        spy_yearly=spy_yearly,
        max_drawdown=m.max_drawdown,
        profit_factor=m.profit_factor,
        trades=int(m.trades),
        sharpe=row.stats.sharpe,
        empty_share=None if tally is None else tally.empty_share,
        mean_names=None if tally is None else tally.mean_names,
        era_yearly=mine,
        era_spy_yearly=theirs,
        era_lead=lead,
        curve=tuple(curve),
    )


def measure(
    conn: sqlite3.Connection,
    plans: Sequence[MethodPlan],
    data: research.ResearchData,
    bench: Sequence[tuple[date, float]],
) -> dict[tuple[str, str], dict[str, Arm]]:
    """Every arm of every variant of every plan: ``{(method id, candidate id): {mode: Arm}}``.

    One ``dev.run_registry`` call per (method, recorded capital, recorded schedule), chunked so no
    call exceeds ``dev.MAX_CANDIDATES`` arms -- a variant contributes at most two, so at most
    ``MAX_CANDIDATES // 2`` variants go into a call and a variant's arms are never split across
    calls. Never across methods: two method files may define different allocator objects under one
    allocator id, which ``run_registry`` refuses within a call.

    Called with **no** ``window=`` keyword, so D9's ``DEV_WINDOW`` default binds and no code path
    here can name the test window. Both arms of one variant run at that variant's recorded capital
    and funding, or they stop being a comparison.
    """
    if data.window != research.DEV_WINDOW:
        raise store.LabError(
            f"the loaded store declares the {data.window.name!r} window; `lab gate` measures the "
            f"dev window and nothing else"
        )
    out: dict[tuple[str, str], dict[str, Arm]] = {}
    per_chunk = max(1, dev.MAX_CANDIDATES // len(MODES))
    for plan in plans:
        mid = plan.method.id
        groups: dict[tuple[Decimal, ContributionSchedule | None], list[Variant]] = {}
        for v in plan.variants:
            groups.setdefault((v.capital, v.contributions), []).append(v)
        for (capital, contributions), group in groups.items():
            for i in range(0, len(group), per_chunk):
                chunk = group[i : i + per_chunk]
                registry: list[Candidate] = []
                owner: dict[str, tuple[str, Variant]] = {}
                for v in chunk:
                    for mode, cand in arms_for(v):
                        registry.append(cand)
                        owner[cand.id] = (mode, v)

                def on_result(
                    _i: int, result: Any, row: DevRow, *, _mid: str = mid,
                    _owner: Mapping[str, tuple[str, Variant]] = owner,
                ) -> None:
                    mode, v = _owner[row.candidate.id]
                    curve = month_end_curve(result.snapshots)
                    deposits = hardgate.trial_deposits(conn, v.trial, list(curve))
                    arm = arm_of(mode, v, row, curve, deposits, bench)
                    out.setdefault((_mid, v.candidate.id), {})[mode] = arm
                    log.info(
                        "%s [%s]: no pick on %s of its decision days, yearly %s vs SPY %s, max DD %s",
                        v.candidate.id, mode, fmt_pct(arm.empty_share),
                        fmt_signed_pct(arm.yearly), fmt_signed_pct(arm.spy_yearly),
                        fmt_pct(arm.max_drawdown),
                    )

                dev.run_registry(
                    data.market, data.dividends, data.spy_dividends, tuple(registry),
                    on_result=on_result, contributions=contributions, initial_idr=capital,
                )
    return out


def measure_store(
    conn: sqlite3.Connection,
    plans: Sequence[MethodPlan],
    store_dir: Path,
    bench: Sequence[tuple[date, float]],
) -> tuple[StoreRun, dict[tuple[str, str], dict[str, Arm]]]:
    """Load the dev store, measure every arm on it, free it, return the numbers.

    The store is about 2.5M bar rows; only small ``Arm`` records survive the call, so a sweep over
    many methods does not hold two copies of it.
    """
    t0 = time.perf_counter()
    data = load_dev_store(Path(store_dir))
    run = StoreRun(
        store_dir=str(store_dir),
        fingerprint=str(data.fingerprint),
        price_fingerprint=data.price_fingerprint,
        purpose=data.purpose,
    )
    log.info("dev store %s loaded (%.1fs)", run.fingerprint[:12], time.perf_counter() - t0)
    try:
        return run, measure(conn, plans, data, bench)
    finally:
        del data  # the only reference: the store is freed before the caller formats anything
        gc.collect()
        log.info("dev store released (%.1fs)", time.perf_counter() - t0)


# --------------------------------------------------------------------------- the comparison


@dataclass(frozen=True)
class VariantRow:
    method_id: str
    variant: Variant
    arms: Mapping[str, Arm]

    @property
    def gated(self) -> Arm:
        return self.arms[GATED]

    @property
    def ungated(self) -> Arm | None:
        return self.arms.get(UNGATED)

    @property
    def modes(self) -> tuple[str, ...]:
        return tuple(m for m in MODES if m in self.arms)

    @property
    def reproduced(self) -> bool | None:
        """Did the gated arm land on the recorded total return? None when either is missing."""
        recorded, measured = self.variant.recorded_total_return, self.gated.total_return
        if recorded is None or measured is None:
            return None
        return abs(measured - recorded) <= REPRO_TOL * max(1.0, abs(recorded))

    @property
    def suspect(self) -> bool:
        """``no gate found`` and yet it holds nothing on a real share of its decision days.

        The cross-examination of a "no gate" verdict, measured rather than guessed: the transform
        only knows two spellings of the gate, and a book braked some other way (``M0012``'s weekly
        SPY-200 read lives in a tuple of SMA lengths, ``M0039``'s in a VIX term structure) would
        otherwise be printed as ungated.
        """
        if self.variant.status != NO_GATE:
            return False
        share = self.gated.empty_share
        return share is not None and share > NOGATE_SUSPECT

    def gate_cost(self, label: str) -> float | None:
        """The gate's contribution in ``label``: the gated lead minus the ungated one, in points.

        Positive means the gate helped that era; negative means it was a drag. ``None`` when either
        arm is missing or either lead is undefined.
        """
        other = self.ungated
        if other is None:
            return None
        mine, theirs = self.gated.era_lead[label], other.era_lead[label]
        if mine is None or theirs is None:
            return None
        return mine - theirs


@dataclass(frozen=True)
class MethodReport:
    method_id: str
    method_name: str
    missing: tuple[str, ...]
    rows: tuple[VariantRow, ...]

    @property
    def headline(self) -> VariantRow:
        """The best recorded **eligible** variant that carries the gate, else the best by MAR.

        Ties break on the trial number, so the choice is reproducible rather than dict-ordered.
        A row that carries the gate is preferred over one that does not, because this report is
        about the gate and a headline with no gate-off column says nothing.
        """
        return sorted(
            self.rows,
            key=lambda r: (
                r.variant.status != CARRIES,
                not r.variant.recorded_eligible,
                r.variant.recorded_mar is None,
                -(r.variant.recorded_mar or 0.0),
                r.variant.trial_n,
            ),
        )[0]

    @property
    def reproduced(self) -> bool:
        return all(r.reproduced is not False for r in self.rows)

    @property
    def gated_rows(self) -> tuple[VariantRow, ...]:
        return tuple(r for r in self.rows if r.variant.status == CARRIES)


def compare(
    plans: Sequence[MethodPlan], arms: Mapping[tuple[str, str], Mapping[str, Arm]]
) -> tuple[MethodReport, ...]:
    out: list[MethodReport] = []
    for plan in plans:
        mid = plan.method.id
        rows: list[VariantRow] = []
        for v in plan.variants:
            measured = arms.get((mid, v.candidate.id))
            want = tuple(mode for mode, _c in arms_for(v))
            if measured is None or any(mode not in measured for mode in want):
                got = () if measured is None else tuple(sorted(measured))
                raise store.LabError(
                    f"{v.candidate.id}: expected arms {want}, measured {got}. The registry run did "
                    f"not produce a row for every arm, so there is nothing to compare"
                )
            rows.append(VariantRow(mid, v, dict(measured)))
        out.append(MethodReport(mid, plan.method.name, plan.missing, tuple(rows)))
    return tuple(out)


# --------------------------------------------------------------------------- the terminal report


def _finite(x: float | None) -> bool:
    return x is not None and math.isfinite(x)


def format_plan(plans: Sequence[MethodPlan], *, gated_only: bool = False) -> str:
    """What a run would measure, with no store opened and no bar read (``--dry-run``).

    This is also how the scope of a sweep is known before an hour is spent on it, and how the six
    variants the transform refuses are read without running anything.
    """
    carries = [v for p in plans for v in p.variants if v.status == CARRIES]
    nogate = [v for p in plans for v in p.variants if v.status == NO_GATE]
    refused = [v for p in plans for v in p.variants if v.status == REFUSED]
    arms = 2 * len(carries) + len(nogate)
    out = [
        f"lab gate: {len(plans)} method(s), "
        f"{sum(len(p.variants) for p in plans)} recorded dev variant(s), {arms} backtest(s)",
        f"the gate this prices: {GATE_SYMBOL} close against its own {GATE_N}-day average "
        f"(f_factor.trend_on), and the blend-core spelling of the same rule",
    ]
    if gated_only:
        out.append(
            "--gated-only: the variants with no gate site are dropped, and with them the "
            "empty-decision cross-check that keeps a 'no gate' verdict honest"
        )
    out.append("")
    out.append(f"carries the shared gate and can switch it off ({len(carries)}):")
    for v in carries:
        out.append(f"  {v.candidate.id:<30} -> {v.ungated_arm_id}   {'; '.join(v.sites)}")
    out.append("")
    out.append(f"no {GATE_SYMBOL} {GATE_N}-day gate this probe can see ({len(nogate)}):")
    for v in nogate:
        out.append(f"  {v.candidate.id}")
    out.append(
        "  these run the recorded arm only; the report flags any that still hold nothing on a "
        "real share of their decision days, because their brake is somewhere this probe does not "
        "reach"
    )
    out.append("")
    out.append(f"gate found, but the method refuses it off ({len(refused)}):")
    for v in refused:
        out.append(f"  {v.candidate.id}: {v.why}")
    if not refused:
        out.append("  (none)")
    missing = [cid for p in plans for cid in p.missing]
    if missing:
        out.append("")
        out.append(f"recorded, but no longer in a method file: {', '.join(missing)}")
    return "\n".join(out)


def _variant_block(row: VariantRow) -> list[str]:
    v = row.variant
    modes = row.modes
    measure_name = "money-weighted" if v.funded else "CAGR"
    out = [
        f"  {v.candidate.id}  (trial #{v.trial_n}, {'funded' if v.funded else 'lump sum'}, "
        f"capital {v.capital:,.0f} IDR, {row.gated.start}..{row.gated.end})",
    ]
    if v.status == CARRIES:
        out.append(f"    gate switched off at: {'; '.join(v.sites)}  [{v.ungated_arm_id}]")
    elif v.status == REFUSED:
        out.append(f"    NOT MEASURED with the gate off: {v.why}")
    else:
        out.append(
            f"    no {GATE_SYMBOL} {GATE_N}-day gate in its params: there is nothing for this "
            f"probe to switch off, and the recorded column is the only one"
        )
    if row.suspect:
        out.append(
            f"    *** it holds nothing on {fmt_pct(row.gated.empty_share)} of its decision days "
            f"while declaring no {GATE_SYMBOL} {GATE_N}-day gate: its brake is somewhere this "
            f"probe does not reach. Do not read this row as ungated ***"
        )
    grid: list[tuple[str, tuple[str, ...]]] = [
        ("decision days with no pick", tuple(fmt_pct(row.arms[m].empty_share) for m in modes)),
        ("names it asked for (mean)", tuple(fmt_num(row.arms[m].mean_names, 1) for m in modes)),
        ("money in the market", tuple(fmt_pct(row.arms[m].exposure) for m in modes)),
        ("total return", tuple(fmt_signed_pct(row.arms[m].total_return) for m in modes)),
        (f"yearly return ({measure_name})", tuple(fmt_signed_pct(row.arms[m].yearly) for m in modes)),
        (f"SPY TR yearly ({measure_name})", tuple(fmt_signed_pct(row.arms[m].spy_yearly) for m in modes)),
        ("max drawdown", tuple(fmt_pct(row.arms[m].max_drawdown) for m in modes)),
        ("profit factor", tuple(fmt_pf(row.arms[m].profit_factor) for m in modes)),
        ("trades", tuple(str(row.arms[m].trades) for m in modes)),
        ("Sharpe (annualized)", tuple(fmt_num(row.arms[m].sharpe) for m in modes)),
        ("lead over SPY a year, by era:", tuple("" for _m in modes)),
    ]
    for label in ERA_LABELS:
        grid.append(
            (f"  {label}", tuple(fmt_signed_pct(row.arms[m].era_lead[label]) for m in modes))
        )
    if row.ungated is not None:
        grid.append(("what the gate was worth, by era:", tuple("" for _m in modes)))
        for label in ERA_LABELS:
            grid.append((f"  {label}", (fmt_signed_pct(row.gate_cost(label)), "")))
    width = max(len(label) for label, _cells in grid)
    out.append(f"    {'':<{width}}" + "".join(f"  {ARM_HEAD[m]:>14}" for m in modes))
    for label, cells in grid:
        out.append(f"    {label:<{width}}" + "".join(f"  {c:>14}" for c in cells))
    head = (
        f"    recorded dev trial #{v.trial_n}: total return "
        f"{fmt_signed_pct(v.recorded_total_return)}"
    )
    rep = row.reproduced
    if rep is None:
        out.append(f"{head}; there is no number to check the recorded column against")
    elif rep:
        out.append(f"{head}; the recorded column reproduces it")
    else:
        out.append(
            f"{head}; the recorded column measured {fmt_signed_pct(row.gated.total_return)} -- the "
            f"store or the engine changed since it ran, so compare the two columns with each "
            f"other, not with the recorded trial"
        )
    return out


def format_report(rep: MethodReport, run: StoreRun) -> str:
    """One method's terminal grid. Ids, arm names and symbols are fine here."""
    out = [
        f"lab gate {rep.method_id} -- {rep.method_name}: {len(rep.rows)} recorded variant(s) "
        f"on dev store {run.fingerprint[:12]}"
        + (f" (purpose {run.purpose!r})" if run.purpose else ""),
        "report only: no trial row, no moments, no funding, no status change; no method file "
        "changed and no method id was minted, so the lab's N and the test-window looks do not move",
        f"columns: as recorded = the variant as the lab ran it; gate off = the same variant with "
        f"{GATE_SYMBOL}'s {GATE_N}-day trend gate removed and nothing else moved",
    ]
    if rep.missing:
        out.append(
            f"not measured (recorded, but no longer in the method file): {', '.join(rep.missing)}"
        )
    for row in rep.rows:
        out.append("")
        out += _variant_block(row)
    return "\n".join(out)


def summary_line(rep: MethodReport) -> str:
    h = rep.headline
    gated, off = h.gated, h.ungated
    if off is None:
        return (
            f"{rep.method_id} ({h.variant.candidate.id}): no {GATE_SYMBOL} {GATE_N}-day gate to "
            f"remove; it led SPY by {fmt_signed_pct(gated.lead)} a year, "
            f"{fmt_signed_pct(gated.era_lead['2009-2015'])} after 2009"
            + ("  *** but it holds nothing on "
               f"{fmt_pct(gated.empty_share)} of its decision days ***" if h.suspect else "")
        )
    bits = [
        f"{rep.method_id} ({h.variant.candidate.id}): lead over SPY a year "
        f"{fmt_signed_pct(gated.lead)} gated, {fmt_signed_pct(off.lead)} with the gate off",
        f"2009-2015 {fmt_signed_pct(gated.era_lead['2009-2015'])} -> "
        f"{fmt_signed_pct(off.era_lead['2009-2015'])}",
        f"2008 {fmt_signed_pct(gated.era_lead['2008'])} -> {fmt_signed_pct(off.era_lead['2008'])}",
        f"worst fall {fmt_pct(gated.max_drawdown)} -> {fmt_pct(off.max_drawdown)}",
        f"no pick on {fmt_pct(gated.empty_share)} of its decision days -> "
        f"{fmt_pct(off.empty_share)}",
    ]
    if not rep.reproduced:
        bits.append("WARNING: a recorded column did not reproduce its trial")
    return "; ".join(bits)


def lab_summary(reports: Sequence[MethodReport]) -> list[str]:
    """The roll-up the whole question turns on: where the gate paid, across everything measured.

    Counting variants rather than methods on purpose -- this is a statement about configurations,
    not a second N -- and saying so, because the lab has exactly one number called N and it is the
    luck gate's distinct-method count.
    """
    rows = [r for rep in reports for r in rep.gated_rows]
    out = [
        f"what the shared {GATE_SYMBOL} {GATE_N}-day gate was worth, over "
        f"{len(rows)} recorded variant(s) that carry it "
        f"(a count of configurations, not the luck gate's N):",
    ]
    for label in ERA_LABELS:
        costs = [r.gate_cost(label) for r in rows]
        judged = [c for c in costs if _finite(c)]
        if not judged:
            out.append(f"  {label:<12} not enough years to judge")
            continue
        helped = [c for c in judged if c is not None and c > 0]
        mean = sum(c for c in judged if c is not None) / len(judged)
        out.append(
            f"  {label:<12} mean {fmt_signed_pct(mean):>9} a year; it helped "
            f"{len(helped)} of {len(judged)}"
        )
    suspects = [r for rep in reports for r in rep.rows if r.suspect]
    if suspects:
        out.append("")
        out.append(
            f"{len(suspects)} variant(s) declare no {GATE_SYMBOL} {GATE_N}-day gate and still hold "
            f"nothing on more than {NOGATE_SUSPECT:.0%} of their decision days -- their brake is "
            f"somewhere this probe does not reach: "
            + ", ".join(r.variant.candidate.id for r in suspects)
        )
    refused = [
        r for rep in reports for r in rep.rows if r.variant.status == REFUSED
    ]
    if refused:
        out.append("")
        out.append(
            f"{len(refused)} variant(s) carry the gate and refuse to run without it: "
            + ", ".join(r.variant.candidate.id for r in refused)
        )
    return out


# --------------------------------------------------------------------------- the journal


def _verdict(rows: Sequence[VariantRow]) -> str:
    """Across the versions that have both columns, did removing the gate help or hurt, and when?"""
    pairs = [r for r in rows if r.ungated is not None]
    if not pairs:
        return (
            "None of this method's versions carries the market safety rule this measurement "
            "removes, so there was nothing here to price."
        )
    whole = [r.gate_cost(WHOLE) for r in pairs]
    recent = [r.gate_cost("2009-2015") for r in pairs]
    crash = [r.gate_cost("2008") for r in pairs]
    whole_j = [x for x in whole if _finite(x)]
    recent_j = [x for x in recent if _finite(x)]
    crash_j = [x for x in crash if _finite(x)]
    if not whole_j:
        return "There were not enough years to say what the safety rule was worth."
    mean_whole = sum(x for x in whole_j if x is not None) / len(whole_j)
    parts = [
        f"Over the whole history the safety rule was worth "
        f"{fmt_signed_pct(mean_whole)} a year on average across this method's versions."
    ]
    if crash_j:
        mean_crash = sum(x for x in crash_j if x is not None) / len(crash_j)
        parts.append(f"In the 2008 crash alone it was worth {fmt_signed_pct(mean_crash)}.")
    if recent_j:
        mean_recent = sum(x for x in recent_j if x is not None) / len(recent_j)
        verb = "earned" if mean_recent > 0 else "cost"
        parts.append(
            f"From 2009 to the end of the history it {verb} "
            f"{fmt_signed_pct(abs(mean_recent))} a year."
        )
    return " ".join(parts)


def insight_text(rep: MethodReport) -> tuple[str, str]:
    """``(title, body)`` in plain words for a non-trader: no ids, no code, no column names."""
    h = rep.headline
    gated, off = h.gated, h.ungated
    years = f"{gated.start.year}-{gated.end.year}"
    money = (
        "the same starting money and the same monthly top-ups"
        if h.variant.funded else "the same starting money"
    )
    intro = (
        f"Most of the methods this lab still holds stop buying whenever the market is below its "
        f"own long-term average, and they all read that same rule on the same dates. The lab took "
        f"the {len(rep.rows)} version(s) of this method it had already tested and ran each of them "
        f"again over the same {years} history, with {money}, once as it stands and once with that "
        f"one rule switched off and nothing else changed. The numbers below are for its best "
        f"version."
    )
    if off is None:
        bullets = [
            f"- This version does not use that rule, so there was nothing to switch off.",
            f"- It earned {fmt_signed_pct(gated.yearly)} a year against the market's "
            f"{fmt_signed_pct(gated.spy_yearly)}.",
        ]
        if h.suspect:
            bullets.append(
                f"- It still held nothing at all on {fmt_pct(gated.empty_share)} of the days it "
                f"chose what to hold, so it has a brake of its own that this measurement did not "
                f"reach."
            )
    else:
        bullets = [
            f"- As it stands it earned {fmt_signed_pct(gated.yearly)} a year against the market's "
            f"{fmt_signed_pct(gated.spy_yearly)}; with the rule off, "
            f"{fmt_signed_pct(off.yearly)}.",
            f"- Its worst fall was {fmt_pct(gated.max_drawdown)} with the rule and "
            f"{fmt_pct(off.max_drawdown)} without it.",
            f"- With the rule it held nothing at all on {fmt_pct(gated.empty_share)} of the days "
            f"it chose what to hold; without it, {fmt_pct(off.empty_share)}.",
        ]
    eras = "\n".join(
        f"- {label}: {fmt_signed_pct(gated.era_lead[label])} a year against the market as it "
        f"stands"
        + (
            f", {fmt_signed_pct(off.era_lead[label])} with the rule off"
            if off is not None else ""
        )
        + "."
        for label in ERA_LABELS
    )
    body = "\n\n".join(
        (
            intro,
            "\n".join(bullets),
            "Period by period, ahead of or behind the market:",
            eras,
            _verdict(rep.rows),
            "This was a measurement, not a new try: nothing was recorded, the lab's count of "
            "tries did not move, and no verdict changed.",
        )
    )
    title = f"{rep.method_name}: what its market safety rule was worth"
    return title, body


def journal(conn: sqlite3.Connection, rep: MethodReport) -> int:
    """One ``observation`` on the method. The caller owns the transaction. Returns its id."""
    title, body = insight_text(rep)
    return store.add_insight(
        conn, kind="observation", title=title, body=body, method_id=rep.method_id
    )


# --------------------------------------------------------------------------- the CSV grid


def _slug(label: str) -> str:
    return label.replace(" ", "_").replace("-", "_")


CSV_HEADER: tuple[str, ...] = (
    "method_id", "candidate_id", "arm", "arm_candidate_id", "gate_status", "gate_sites",
    "gate_refusal", "suspect", "store_fingerprint", "price_fingerprint", "store_purpose",
    "trial_n", "funded", "capital_idr", "start", "end", "exposure", "mean_names", "empty_share",
    "total_return", "recorded_total_return", "reproduced", "yearly_return", "spy_yearly_return",
    "lead", "max_drawdown", "profit_factor", "trades", "sharpe",
    *(f"lead_{_slug(label)}" for label in ERA_LABELS),
    *(f"yearly_{_slug(label)}" for label in ERA_LABELS),
    *(f"spy_yearly_{_slug(label)}" for label in ERA_LABELS),
    *(f"gate_worth_{_slug(label)}" for label in ERA_LABELS),
)


def _cell(x: object) -> str:
    if x is None:
        return ""
    if isinstance(x, bool):
        return "1" if x else "0"
    if isinstance(x, float):
        return repr(x)  # full precision; inf stays "inf"
    if isinstance(x, date):
        return x.isoformat()
    return str(x)


def csv_rows(reports: Sequence[MethodReport], run: StoreRun) -> list[list[str]]:
    out: list[list[str]] = [list(CSV_HEADER)]
    for rep in reports:
        for row in rep.rows:
            v = row.variant
            for mode in row.modes:
                arm = row.arms[mode]
                out.append([
                    _cell(x) for x in (
                        rep.method_id, v.candidate.id, mode, arm.candidate_id, v.status,
                        "; ".join(v.sites), v.why, row.suspect, run.fingerprint,
                        run.price_fingerprint, run.purpose, v.trial_n, v.funded, v.capital,
                        arm.start, arm.end, arm.exposure, arm.mean_names, arm.empty_share,
                        arm.total_return, v.recorded_total_return,
                        row.reproduced if mode == GATED else None,
                        arm.yearly, arm.spy_yearly, arm.lead, arm.max_drawdown,
                        arm.profit_factor, arm.trades, arm.sharpe,
                        *(arm.era_lead[label] for label in ERA_LABELS),
                        *(arm.era_yearly[label] for label in ERA_LABELS),
                        *(arm.era_spy_yearly[label] for label in ERA_LABELS),
                        *(
                            (row.gate_cost(label) if mode == GATED else None)
                            for label in ERA_LABELS
                        ),
                    )
                ])
    return out


def write_csv(reports: Sequence[MethodReport], run: StoreRun, path: Path) -> Path:
    """Write the full variant x arm grid to ``path`` (parents created). Returns the path written."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(csv_rows(reports, run))
    return path
```

**Impact:** a new module. Nothing imports it except the new CLI handler and the new test file, so
nothing in the tree changes behaviour until `lab gate` is run.

---

### Step 2: the `lab gate` stanza in the `commands/lab.py` module docstring

**File:** `engine/src/seer_engine/commands/lab.py:73` — insert immediately **after** the
`lab exposure` stanza (which ends `...N and the looks do not move`) and **before** the
`lab idea --name ...` line at 74.
**Change:** one stanza, in the file's existing column layout.

```
    lab gate [M0030 ...] [--all] [--only IDS] [--store DIR] [--csv PATH] [--gated-only]
             [--no-journal] [--dry-run]
                                    report only: what the shared SPY 200-day trend gate is worth,
                                    book by book. Re-runs every recorded dev variant twice -- as
                                    recorded, and with that one gate switched off and nothing else
                                    moved -- and prints the lead over SPY whole-window and per era
                                    beside what the gate was worth in each. The gate is found by a
                                    generic walk over the params, checked first against the
                                    recorded controls the lab already holds; a variant whose gate
                                    cannot be identified is listed, never run as if it were off.
                                    No method file changes and no new method id. No trial row, no
                                    moments, no status change: N and the looks do not move
```

**Impact:** `lab --help` text only. **Does not touch** the `lab run` stanza at lines 13-19, which
phase 1 edits for `--amend`.

---

### Step 3: the `gate` subparser

**File:** `engine/src/seer_engine/commands/lab.py:418` — insert immediately **after** the
`exposure` parser's last line (`s.add_argument("--csv", type=Path, default=None, metavar="PATH", help="also write the full grid (variant x column) to PATH as CSV, full precision")`)
and **before** `s = sub.add_parser("idea", ...)` at line 419.
**Change:** a new, self-contained parser block that touches nothing else.

```python
    s = sub.add_parser(
        "gate",
        # No literal `%` in any `help=` string below, and none may be added: argparse runs every
        # `help=` through %-interpolation (HelpFormatter._expand_help), so a bare `%` is read as a
        # format spec and `lab --help` dies. A doubled `%%` renders as one `%`. `description=` is
        # NOT interpolated and must stay single. See the `exposure` parser above.
        help="report only: what the shared SPY 200-day trend gate was worth, book by book",
        description=(
            "Re-run every recorded dev variant of each named method at its recorded capital and "
            "funding, twice on the dev window: the candidate as the lab recorded it, and the same "
            "candidate with SPY's 200-day trend gate switched off and nothing else moved. Prints "
            "the lead over SPY whole-window and per era (1996-2002, 2003-2008, 2008 alone, "
            "2009-2015), what the gate was worth in each era, the share of decision days each arm "
            "held nothing, and a roll-up over everything measured. The gate is found by a generic "
            "walk over the candidate's params -- the trend pair f_factor.trend_on reads, and the "
            "blend-core spelling of the same rule -- so no method file changes and no method id is "
            "minted; the walk is checked against the gate-off controls the lab already holds "
            "before anything runs, and a variant whose gate it cannot identify is listed as not "
            "transformable and never run as though the gate were off. Records no trial, no "
            "moments, no funding and no status, so the lab's N and the test-window looks do not "
            "move and the test window is never read; one plain-words observation per method is "
            "journaled unless --no-journal."
        ),
    )
    s.add_argument("method", nargs="*", metavar="M0030",
                   help="the methods to measure; omit and pass --all for every method with a "
                        "recorded dev trial")
    s.add_argument("--all", action="store_true",
                   help="measure every method that has a recorded dev trial and still has a "
                        "method file, instead of naming them. Hundreds of backtests: use --dry-run "
                        "first to see the scope")
    s.add_argument(
        "--only", "--candidate", default=None, metavar="IDS",
        help="measure only these recorded variants (comma-separated candidate ids, e.g. "
             "M0030-C50T) instead of every recorded dev variant of each method",
    )
    s.add_argument(
        "--store",
        type=Path,
        default=Path(os.environ.get("SEER_RESEARCH_STORE") or research.STORE_DIR),
        help=f"the dev store the trials were recorded on (default: {research.STORE_DIR}, or "
             "$SEER_RESEARCH_STORE); a test-window store is refused. The store is gitignored, so "
             "a fresh worktree has none -- point this at a checkout that does",
    )
    s.add_argument("--gated-only", action="store_true",
                   help="skip the recorded variants the walk finds no gate in. Faster, and it "
                        "gives up the empty-decision cross-check that keeps a no-gate verdict "
                        "honest")
    s.add_argument("--dry-run", action="store_true",
                   help="classify every recorded variant and print what would run -- which carry "
                        "the gate, which do not, and which refuse it off -- then stop. Opens no "
                        "store, reads no bar, writes nothing")
    s.add_argument("--no-journal", action="store_true",
                   help="print the report and write nothing at all, not even the observation")
    s.add_argument("--csv", type=Path, default=None, metavar="PATH",
                   help="also write the full grid (variant x column) to PATH as CSV, full precision")
```

**Impact:** `lab gate` becomes a parseable subcommand. `os`, `Path` and `research` are already
imported at the top of the file (lines 101, 106, 108).

**Note on sharing this file with phase 1 (reconciler, C4):** phase 1 adds `--amend` to the `run`
subparser at lines 181-195 and rewrites `_run`'s tail. **Phase 1 lands first**, so this block is
written against the file as phase 1 leaves it: the `exposure` parser's `--csv` line is still the
anchor, but it now sits ~12 lines further down than `:418`. Find it by its text, not its number.
The two hunks are independent additions and do not overlap; if git ever reports a conflict here,
take **both**.

---

### Step 4: the `_gate` handler

**File:** `engine/src/seer_engine/commands/lab.py:2293` — insert immediately **after** `_exposure`
(which ends `return 0` at 2292) and **before** `def _idea(conn, args)` at 2295.
**Change:** a new handler.

```python
def _gate(conn, args) -> int:
    """``lab gate M0030 [M0053 ...]``: what the shared SPY 200-day gate was worth.

    Report only. Every refusal that needs no bars -- the method ids, their files, their recorded
    trials, a bracket-engine variant with no params to walk, the recorded capital and funding, an
    unknown --only id, the benchmark geometry, and the transform's own disagreement with the lab's
    recorded gate-off controls -- is made before the research store is loaded. --dry-run stops
    there. Then one or two arms per recorded variant run on the dev window and the grid is
    printed. Nothing is written except one observation per method (none with --no-journal); N and
    the test-window looks are printed before and after so the invariant is visible, not just
    tested.
    """
    from seer_engine.lab import gate_probe as gp
    from seer_engine.lab import hardgate

    if research.DEV_END != dev.DEV_END:
        raise store.LabError("research.DEV_END differs from dev.DEV_END; refusing to run")
    if bool(args.method) == bool(args.all):
        raise store.LabError(
            "name at least one method (e.g. `lab gate M0030`) or pass --all, not both and not "
            "neither"
        )
    problems, checked = gp.control_problems()
    if problems:
        raise store.LabError(
            "the gate transform disagrees with the lab's own recorded gate-off controls, so it "
            "cannot be trusted to switch the gate off anywhere else:\n  "
            + "\n  ".join(problems)
        )
    ids = gp.recorded_method_ids(conn) if args.all else args.method
    plans = gp.plan_methods(conn, ids, args.only, gated_only=args.gated_only)
    print(
        f"the gate transform reproduced all {checked} of the lab's recorded gate-off controls "
        f"({', '.join(a for a, _b in gp.CONTROLS)}, and M0030-C50T's core leg against M0030-C50A)"
    )
    print()
    print(gp.format_plan(plans, gated_only=args.gated_only))
    if args.dry_run:
        print("\n--dry-run: no store was opened, no backtest ran and nothing was written.")
        return 0
    geo = hardgate.geometry(conn)  # the recorded SPY hold: the per-era benchmark, before any load
    n_before = store.dev_trial_count(conn)
    looks_before = store.test_looks(conn)
    t0 = time.perf_counter()
    run, arms = gp.measure_store(conn, plans, Path(args.store), geo.bench)
    reports = gp.compare(plans, arms)
    for rep in reports:
        print()
        print(gp.format_report(rep, run))
    print()
    print("summary (best recorded gated variant by MAR, else the best by MAR):")
    for rep in reports:
        print(f"  {gp.summary_line(rep)}")
    print()
    for line in gp.lab_summary(reports):
        print(line)
    if args.csv is not None:
        written = gp.write_csv(reports, run, Path(args.csv))
        print(f"\ngrid written to {written}")
    if args.no_journal:
        tail = "No journal entry (--no-journal), so `lab stage` is not needed."
    else:
        with conn:
            entries = [gp.journal(conn, rep) for rep in reports]
        tail = (
            f"journal entries {', '.join(f'#{e}' for e in entries)} written (one observation per "
            f"method). Solo: `python -m seer_engine lab stage` so seertrade.site/sera shows them."
        )
    # Two numbers, two labels, and neither of them called "Lab N". The ten strings §5.1 puts to
    # the owner print `Lab N (dev trials) is now <dev_trial_count>`, which names the trial ROW
    # count as the lab's N when the gate actually applies `store.gate(conn).n` -- 354 against 74,
    # measured 2026-10-12. This command is new today, so it is under no obligation to repeat that;
    # it prints the hurdle as the hurdle and the row count as rows. The ten are untouched (plan
    # invariant 9) and this adds no eleventh, so a grep for the misleading wording still returns
    # exactly ten and phase 6's count stays right.
    g_after = store.gate(conn)
    print(
        f"\nNo trial was recorded and no method id was minted. "
        f"Luck hurdle N: {g_after.n} (policy {g_after.policy}) -- unchanged, because this command "
        f"records no trial and mints no method id. "
        f"Dev trial rows: {n_before} before, {store.dev_trial_count(conn)} after. "
        f"Test-window looks used: {looks_before} before, {store.test_looks(conn)} after. {tail}"
    )
    log.info("lab gate: %d method(s) done (%.1fs)", len(reports), time.perf_counter() - t0)
    return 0
```

**Impact:** `lab gate` runs. `time`, `Path`, `dev`, `research`, `store`, `log` are already imported
in this module.

**On the `Lab N (dev trials)` wording (reconciler, C8):** an earlier draft of this handler printed
an **eleventh** copy of the exact phrase §5.1 documents as misleading, on the reasoning that a new
command spelling it differently would hide the inconsistency. The reconciler reversed that. R5's
instruction is *surface it, do not fix it*, and the set's invariant 9 forbids **editing** the ten
— neither obliges a brand-new command to reproduce a known-wrong label, and doing so would put an
eleventh misleading line in front of the owner while the memo asking him about the other ten was
still unanswered. So this handler prints the gate's own N under its own label and the row count
under its own label, which is Decision A's **option 1** demonstrated once, on one new surface,
without touching anything the owner has to decide about.

Phase 6's memo names this as **evidence the owner can weigh, not a recommendation**: one command
in the lab now prints the clear form, and he can see what it reads like before choosing what the
other ten should do. Also capture the gate's N **before** the run beside `n_before` if you want
the before/after symmetry in the line; `store.gate(conn)` is cheap and read-only.

---

### Step 5: register the handler

**File:** `engine/src/seer_engine/commands/lab.py:2447` — in the `_HANDLERS` dict, immediately
after `"exposure": _exposure,`.
**Change:**

```python
    "exposure": _exposure,
    "gate": _gate,
```

**Impact:** `lab gate` dispatches. `run()` at line 467 already turns `store.LabError` into exit 2
and anything else into the CLI's generic exit 1.

---

### Step 6: `engine/tests/test_lab_gate_probe.py` (new file)

**File:** `engine/tests/test_lab_gate_probe.py` (new)
**Change:** 26 tests, in the six groups `test_lab_exposure.py` uses.

```python
"""``lab gate``: the shared SPY 200-day gate, priced apart from everything else a book does.

Report only: N, the looks and every trial-side table stay as they were; every refusal comes before
a store loads; the transform agrees with the gate-off controls the lab already holds; the wrapper
keeps the Allocator contract and perturbs nothing; and a variant whose gate cannot be identified is
listed, never run as though the gate were off.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from allocatorkit import assert_p4_identity, assert_valid_targets, everyone
from labkit import smoke_data, smoke_test_data

from seer_engine import cli, research
from seer_engine.backtest.dev import Candidate
from seer_engine.lab import gate_probe as gp
from seer_engine.lab import hardgate, runner, store
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20, N20_NOTREND
from seer_engine.lab.seed import seed
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC
from seer_engine.strategies.allocator import (
    BLEND,
    Allocator,
    BlendParams,
    BlendPart,
    last_close,
    target_from_close,
)
from seer_engine.sim.book import Target
from seer_engine.strategies.f_factor import FACTOR, FactorParams
from seer_engine.strategies.f_index import TIMING, TimingParams

HERE = Path(__file__)
GATED_PARAMS = FactorParams(rank="momentum", top=6, mom_n=40, mom_skip=0, vol_n=20,
                            trend=("SPY", 200))
OPEN_PARAMS = replace(GATED_PARAMS, trend=None)
OTHER_GATE = replace(GATED_PARAMS, trend=("QQQ", 50))
TIMED_SPY = TimingParams(hold="SPY", signal="SPY", rule="sma", n=200)
ALWAYS_SPY = TimingParams(hold="SPY", signal="SPY", rule="always")


def _blend(params: FactorParams, core: TimingParams = TIMED_SPY) -> BlendParams:
    """M0030's shape on the smoke fixture: half a timed SPY core, half a gated stock sleeve."""
    return BlendParams((
        BlendPart(TIMING, core, Decimal("0.5")),
        BlendPart(FACTOR, params, Decimal("0.5")),
    ))


def _cand(cid: str, params: Any, allocator: Any = FACTOR) -> Candidate:
    return Candidate(
        id=cid, family="M0001", rules=MONTHLY_HOLD_FRAC, allocator=allocator, params=params,
        rationale="test", added=date(2026, 10, 12), owner_inputs=(),
    )


def _method(cands=None) -> Method:
    return Method(
        id="M0001", name="Momentum under the market's own 200-day average", family="factor",
        source_kind="knowledge", source_ref="", hypothesis="h", expected_failure="f",
        candidates=cands or (_cand("M0001-A", GATED_PARAMS), _cand("M0001-B", OPEN_PARAMS)),
    )


# ---- a tiny gated allocator, for the contract checks ---------------------------------------------


class GatedFake:
    """Two names, but only on days the fixture's SPY is above its own 200-day average."""

    id = "FAKE_GATE"

    def lookback(self, params: Any) -> int:
        return 200

    def symbols(self, params: Any) -> tuple[str, ...]:
        return ("AAA", "BBB", "SPY")

    def holds(self, params: Any) -> tuple[str, ...]:
        return ()

    def uses_members(self, params: Any) -> bool:
        return False

    def targets(self, history, members, data_date, held, params) -> tuple[Target, ...]:
        out: list[Target] = []
        for symbol in ("AAA", "BBB"):
            h = history.get(symbol)
            close = last_close(h, data_date)
            if close is None:
                continue
            t = target_from_close(symbol, close, Decimal("0.5"))
            if t is not None:
                out.append(t)
        return tuple(out)

    def prepare(self, history):
        return dict(history)

    def targets_prepared(self, prepared, members, data_date, held, params) -> tuple[Target, ...]:
        return self.targets(prepared, members, data_date, held, params)


GATED_FAKE = GatedFake()


# ---- fixtures ------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def dev_data():
    return smoke_data()


@pytest.fixture()
def lab(tmp_path):
    path = tmp_path / "lab.sqlite"
    c = store.connect(path)
    seed(c)
    yield c, path
    c.close()


@pytest.fixture()
def recorded(lab, dev_data, monkeypatch):
    conn, _ = lab
    m = _method()
    runner.run_method(conn, m, HERE, dev_data, git_sha="x", require_commit=False)
    monkeypatch.setattr(gp, "discover", lambda: {"M0001": (m, HERE)})
    return m


def _dir(tmp_path) -> Path:
    d = tmp_path / "dev-store"
    d.mkdir()
    return d


def _loader(by_dir):
    def load(store_dir, **kw):
        got = by_dir[Path(store_dir)]
        if isinstance(got, BaseException):
            raise got
        return replace(got)

    return load


def _untouched(conn):
    """Everything `lab gate` must leave as it found it (insights excepted)."""
    return (
        store.dev_trial_count(conn),
        store.test_looks(conn),
        conn.execute("SELECT count(*) FROM trials").fetchone()[0],
        conn.execute("SELECT count(*) FROM trial_moments").fetchone()[0],
        conn.execute("SELECT count(*) FROM trial_funding").fetchone()[0],
        conn.execute("SELECT count(*) FROM trial_provenance").fetchone()[0],
        tuple(tuple(r) for r in conn.execute(
            "SELECT id, status, verdict, source_sha FROM methods ORDER BY id")),
    )


def _insights(conn) -> int:
    return conn.execute("SELECT count(*) FROM insights").fetchone()[0]


def _measure(conn, dev_data, tmp_path, monkeypatch, only=None, gated_only=False):
    d = _dir(tmp_path)
    monkeypatch.setattr(research, "load_store", _loader({d: dev_data}))
    plans = gp.plan_methods(conn, ["M0001"], only, gated_only=gated_only)
    geo = hardgate.geometry(conn)
    run, arms = gp.measure_store(conn, plans, d, geo.bench)
    return gp.compare(plans, arms), run


# ---- the transform -------------------------------------------------------------------------------


def test_the_transform_switches_off_a_trend_pair_and_a_timing_rule():
    off, sites = gp.gate_off(GATED_PARAMS)
    assert off == OPEN_PARAMS and len(sites) == 1 and "trend" in sites[0]
    off, sites = gp.gate_off(_blend(GATED_PARAMS))
    assert off.parts[0].params == ALWAYS_SPY
    assert off.parts[1].params == OPEN_PARAMS
    assert len(sites) == 2
    # the shares, the allocators and everything else are untouched
    assert [p.share for p in off.parts] == [p.share for p in _blend(GATED_PARAMS).parts]
    assert [p.allocator for p in off.parts] == [TIMING, FACTOR]


def test_the_transform_is_a_no_op_on_a_book_with_no_gate():
    off, sites = gp.gate_off(OPEN_PARAMS)
    assert sites == () and off is OPEN_PARAMS
    off, sites = gp.gate_off(_blend(OPEN_PARAMS, ALWAYS_SPY))
    assert sites == () and off is not None


def test_the_transform_refuses_a_gate_that_is_not_the_shared_one():
    with pytest.raises(gp.GateOffRefused, match="not the shared"):
        gp.gate_off(OTHER_GATE)
    with pytest.raises(gp.GateOffRefused, match="not the shared"):
        gp.gate_off(_blend(GATED_PARAMS, TimingParams(hold="SPY", signal="SPY", rule="sma", n=50)))
    with pytest.raises(gp.GateOffRefused, match="timing gate"):
        gp.gate_off(_blend(OPEN_PARAMS, TimingParams(hold="QQQ", signal="QQQ", rule="sma", n=200)))


def test_the_transform_refuses_params_that_reject_the_gateless_version():
    """A method built around the gate being on has no 'same book without it' to measure."""

    @dataclass(frozen=True)
    class NeedsGate:
        inner: FactorParams

        def __post_init__(self) -> None:
            if self.inner.trend is None:
                raise ValueError("inner must have a trend switch")

    with pytest.raises(gp.GateOffRefused, match="refuses the gate off"):
        gp.gate_off(NeedsGate(GATED_PARAMS))


def test_the_transform_leaves_allocators_and_non_compare_fields_alone():
    """``BlendPart.allocator`` is an Allocator and ``Tally`` is compare=False: neither is walked."""
    off, _sites = gp.gate_off(_blend(GATED_PARAMS))
    assert off.parts[0].allocator is TIMING and off.parts[1].allocator is FACTOR
    p = gp.GateParams(inner_params=GATED_PARAMS)
    assert p.tally is not gp.GateParams(inner_params=GATED_PARAMS).tally
    assert gp.GateParams(inner_params=GATED_PARAMS) == p  # tally does not enter equality


def test_the_transform_reproduces_every_recorded_gate_off_control():
    """The committed lab already holds six configurations the transform must land on exactly.

    This is the check that makes the transform trustworthy anywhere else; ``lab gate`` runs it
    before it measures anything and refuses (exit 2) when it fails.
    """
    problems, checked = gp.control_problems()
    assert problems == ()
    assert checked == len(gp.CONTROLS) + len(gp.CORE_CONTROLS)


def test_the_impure_controls_are_listed_with_their_reason():
    """M0001-TV10's recorded NOTREND sibling moves two things, so it is not a control."""
    assert ("M0001-TV10", "M0001-TV10-NOTREND") in gp.IMPURE_CONTROLS
    assert ("M0001-TV10", "M0001-TV10-NOTREND") not in gp.CONTROLS
    assert "own-vol window" in gp.IMPURE_CONTROLS[("M0001-TV10", "M0001-TV10-NOTREND")]


def test_the_m0007_pair_is_the_simplest_control_and_still_holds():
    """``ResidParams(N20)`` -> ``ResidParams(N20_NOTREND)``: the lab's own recorded gate control."""
    assert N20.trend == gp.GATE and N20_NOTREND.trend is None
    off, sites = gp.gate_off(N20)
    assert off == N20_NOTREND and len(sites) == 1


# ---- the wrapper ---------------------------------------------------------------------------------


def _cases(dev_data):
    history = dev_data.market.history
    return history, list(history["SPY"].dates.tolist())[-12:]


def test_the_wrapper_keeps_the_allocator_contract(dev_data):
    history, days = _cases(dev_data)
    wrapper = gp.wrapper_for(GATED_FAKE)
    assert isinstance(wrapper, Allocator)
    params = [gp.GateParams(inner_params=None)]
    nonempty = assert_p4_identity(
        wrapper, history, everyone(history), days,
        [frozenset(), frozenset({"AAA"})], params,
    )
    assert nonempty > 0  # the check was not vacuous


def test_the_wrapper_returns_exactly_what_the_inner_returned(dev_data):
    """A pass-through that perturbed anything would break the reproduction check silently."""
    history, days = _cases(dev_data)
    d = days[-1]
    wrapper = gp.wrapper_for(GATED_FAKE)
    inner = GATED_FAKE.targets(history, frozenset(), d, frozenset(), None)
    got = wrapper.targets(history, frozenset(), d, frozenset(),
                          gp.GateParams(inner_params=None))
    assert got == inner
    assert_valid_targets(got, history, d, frozenset())


def test_one_wrapper_per_inner_object():
    """``dev.run_registry`` refuses two allocator objects sharing an id, so the memo is required."""
    assert gp.wrapper_for(GATED_FAKE) is gp.wrapper_for(GATED_FAKE)
    assert gp.wrapper_for(GatedFake()) is not gp.wrapper_for(GATED_FAKE)
    assert gp.wrapper_for(GATED_FAKE).id == "NOGATE-FAKE_GATE"


def test_the_wrapper_delegates_preparation_and_market_fields(dev_data):
    """A MarketAware inner must keep its market: LazyPrepared would silently drop it."""
    seen: list[Any] = []

    class MarketAwareFake(GatedFake):
        id = "FAKE_MARKET_GATE"
        market_fields = ("dividends",)

        def prepare_market(self, market):
            seen.append(market)
            return dict(market.history)

    wrapper = gp.wrapper_for(MarketAwareFake())
    prepared = wrapper.prepare_market(dev_data.market)
    assert seen == [dev_data.market]
    assert set(prepared) == set(dev_data.market.history)
    assert wrapper.market_fields == ("dividends",)
    assert gp.wrapper_for(GATED_FAKE).market_fields == ("fundamentals",)


def test_the_tally_counts_the_gate_firing(dev_data):
    """The empty-decision count is how both arms prove the gate turned on and off."""
    history, days = _cases(dev_data)
    p = gp.GateParams(inner_params=None)
    wrapper = gp.wrapper_for(GATED_FAKE)
    for d in days:
        wrapper.targets(history, frozenset(), d, frozenset(), p)
    assert p.tally.calls == len(days)
    assert p.tally.empty_share == 0.0 and p.tally.mean_names == 2.0


# ---- the arms and the plan -----------------------------------------------------------------------


def test_two_arms_when_it_carries_the_gate_and_one_when_it_does_not(lab, dev_data, recorded):
    conn, _ = lab
    (plan,) = gp.plan_methods(conn, ["M0001"])
    by_id = {v.candidate.id: v for v in plan.variants}
    assert by_id["M0001-A"].status == gp.CARRIES
    assert by_id["M0001-B"].status == gp.NO_GATE
    assert [m for m, _c in gp.arms_for(by_id["M0001-A"])] == [gp.GATED, gp.UNGATED]
    assert [c.id for _m, c in gp.arms_for(by_id["M0001-A"])] == ["M0001-A", "M0001-A-NOGATE"]
    assert [m for m, _c in gp.arms_for(by_id["M0001-B"])] == [gp.GATED]
    for _mode, c in gp.arms_for(by_id["M0001-A"]):
        assert c.family == "M0001"
        assert c.rules is by_id["M0001-A"].candidate.rules  # rules are NOT stripped here


def test_an_arm_id_never_shadows_a_recorded_candidate_id():
    """M0064 really does hold both ``M0064-P50`` and a recorded ``M0064-P50-NOGATE``."""
    assert gp.arm_id_for("X-A", "-NOGATE", set()) == "X-A-NOGATE"
    assert gp.arm_id_for("X-A", "-NOGATE", {"X-A-NOGATE"}) == "X-A-NOGATE-2"
    assert gp.arm_id_for("X-A", "-NOGATE", {"X-A-NOGATE", "X-A-NOGATE-2"}) == "X-A-NOGATE-3"


def test_a_variant_whose_method_refuses_the_gate_off_is_planned_not_run(lab, dev_data, monkeypatch):
    @dataclass(frozen=True)
    class NeedsGate:
        inner: FactorParams

        def __post_init__(self) -> None:
            if self.inner.trend is None:
                raise ValueError("inner must have a trend switch")

        def as_dict(self) -> dict[str, str]:
            return self.inner.as_dict()

    class NeedsGateAllocator(GatedFake):
        id = "FAKE_NEEDS_GATE"

    conn, _ = lab
    needs = NeedsGateAllocator()
    m = _method((_cand("M0001-A", GATED_PARAMS),
                 _cand("M0001-N", NeedsGate(GATED_PARAMS), needs)))
    runner.run_method(conn, m, HERE, dev_data, git_sha="x", require_commit=False)
    monkeypatch.setattr(gp, "discover", lambda: {"M0001": (m, HERE)})
    (plan,) = gp.plan_methods(conn, ["M0001"])
    v = next(x for x in plan.variants if x.candidate.id == "M0001-N")
    assert v.status == gp.REFUSED and "trend switch" in v.why
    assert [m for m, _c in gp.arms_for(v)] == [gp.GATED]
    assert "NOT MEASURED with the gate off" in gp.format_plan(plan.variants and [plan])


def test_dry_run_classifies_without_opening_a_store(lab, recorded, tmp_path, monkeypatch, capsys):
    conn, path = lab
    before, notes = _untouched(conn), _insights(conn)
    monkeypatch.setattr(research, "load_store", _boom)
    assert cli.main(["lab", "--db", str(path), "gate", "M0001", "--store",
                     str(_dir(tmp_path)), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "carries the shared gate and can switch it off (1)" in out
    assert "M0001-A-NOGATE" in out and "M0001-B" in out
    assert "no store was opened" in out
    assert _untouched(conn) == before and _insights(conn) == notes


# ---- the measurement -----------------------------------------------------------------------------


def test_the_gate_is_priced_and_nothing_is_written(lab, dev_data, recorded, tmp_path, monkeypatch):
    conn, _ = lab
    before, notes = _untouched(conn), _insights(conn)
    (rep,), run = _measure(conn, dev_data, tmp_path, monkeypatch)
    assert [r.variant.candidate.id for r in rep.rows] == ["M0001-A", "M0001-B"]
    gated_row = rep.rows[0]
    assert gated_row.modes == (gp.GATED, gp.UNGATED)
    assert gated_row.reproduced is True
    gated, off = gated_row.gated, gated_row.ungated
    # the gate's whole job is to hand back nothing sometimes; with it off, never.
    assert gated.empty_share is not None and gated.empty_share > 0.0
    assert off.empty_share == 0.0
    assert gated_row.gate_cost(gp.WHOLE) is not None
    assert set(gated.era_lead) == set(gp.ERA_LABELS)
    assert rep.rows[1].modes == (gp.GATED,) and rep.rows[1].ungated is None
    assert run.fingerprint == "smoke"
    assert _untouched(conn) == before and _insights(conn) == notes


def test_the_gated_arm_reproduces_the_recorded_trial(lab, dev_data, recorded, tmp_path, monkeypatch):
    """The pass-through wrapper must not perturb the measurement; this is how we know it does not."""
    conn, _ = lab
    (rep,), _run = _measure(conn, dev_data, tmp_path, monkeypatch)
    assert rep.reproduced is True
    for row in rep.rows:
        assert row.gated.total_return == pytest.approx(row.variant.recorded_total_return, rel=1e-12)


def test_the_ungated_arm_matches_the_recorded_sibling_that_has_no_gate(
        lab, dev_data, recorded, tmp_path, monkeypatch):
    """M0001-A with the gate off IS M0001-B, so the two must measure identically."""
    conn, _ = lab
    (rep,), _run = _measure(conn, dev_data, tmp_path, monkeypatch)
    off = rep.rows[0].ungated
    sibling = rep.rows[1].gated
    assert off.total_return == sibling.total_return
    assert off.max_drawdown == sibling.max_drawdown
    assert off.trades == sibling.trades


def test_every_arm_runs_at_the_recorded_capital_and_funding(
        lab, dev_data, recorded, tmp_path, monkeypatch):
    conn, _ = lab
    seen: list = []
    real = gp.dev.run_registry

    def spy(*a, **k):
        seen.append((k.get("initial_idr"), k.get("contributions"), "window" in k, len(a[3])))
        return real(*a, **k)

    monkeypatch.setattr(gp.dev, "run_registry", spy)
    _measure(conn, dev_data, tmp_path, monkeypatch)
    n = int(store.trials_of(conn, "M0001")[0]["n"])
    want = (runner.recorded_capital(conn, n), runner.recorded_contributions(conn, n))
    assert len(seen) == 1  # both variants share capital and schedule: one call
    assert seen[0][:3] == (*want, False)  # and NO window= keyword, so the dev default binds
    assert seen[0][3] == 3  # one gated variant x two arms, one ungated variant x one


def test_gated_only_drops_the_variants_with_no_gate(lab, dev_data, recorded, tmp_path, monkeypatch):
    conn, _ = lab
    (rep,), _run = _measure(conn, dev_data, tmp_path, monkeypatch, gated_only=True)
    assert [r.variant.candidate.id for r in rep.rows] == ["M0001-A"]


# ---- refusals ------------------------------------------------------------------------------------


def _boom(*a, **k):
    raise AssertionError("a store must not be loaded for a refusal")


def test_cli_refuses_unknown_or_unrun_methods_before_loading(lab, recorded, tmp_path, monkeypatch):
    _, path = lab
    d = _dir(tmp_path)
    monkeypatch.setattr(research, "load_store", _boom)
    for mid in ("M9999", "H-P7A", "nonsense"):
        assert cli.main(["lab", "--db", str(path), "gate", mid, "--store", str(d)]) == 2


def test_cli_refuses_both_or_neither_of_methods_and_all(lab, recorded, tmp_path, monkeypatch):
    _, path = lab
    d = _dir(tmp_path)
    monkeypatch.setattr(research, "load_store", _boom)
    assert cli.main(["lab", "--db", str(path), "gate", "--store", str(d)]) == 2
    assert cli.main(["lab", "--db", str(path), "gate", "M0001", "--all", "--store", str(d)]) == 2


def test_an_unknown_only_id_is_refused_before_loading(lab, recorded, tmp_path, monkeypatch):
    conn, path = lab
    d = _dir(tmp_path)
    monkeypatch.setattr(research, "load_store", _boom)
    with pytest.raises(store.LabError, match="not a recorded dev variant"):
        gp.plan_methods(conn, ["M0001"], "M0001-ZZZ")
    assert cli.main(["lab", "--db", str(path), "gate", "M0001",
                     "--only", "M0001-ZZZ", "--store", str(d)]) == 2
    (plan,) = gp.plan_methods(conn, ["M0001"], "m0001-a")
    assert [v.candidate.id for v in plan.variants] == ["M0001-A"]


def test_a_bracket_variant_is_refused_before_loading(lab, dev_data, monkeypatch):
    conn, _ = lab
    from seer_engine.sim.rules import DESIGN_V0
    from seer_engine.strategies.a import DESIGN_PARAMS, STRATEGY_A

    m = _method()
    runner.run_method(conn, m, HERE, dev_data, git_sha="x", require_commit=False)
    bracket = Candidate(id="M0001-A", family="M0001", rules=DESIGN_V0, allocator=STRATEGY_A,
                        params=DESIGN_PARAMS, rationale="t", added=date(2026, 10, 12),
                        owner_inputs=())
    monkeypatch.setattr(gp, "discover", lambda: {"M0001": (_method((bracket,)), HERE)})
    with pytest.raises(store.LabError, match="bracket engine"):
        gp.plan_methods(conn, ["M0001"])


def test_a_broken_transform_refuses_the_whole_command(lab, recorded, tmp_path, monkeypatch, capsys):
    """``control_problems`` is the gate on the gate probe: a wrong transform measures nothing."""
    conn, path = lab
    before = _untouched(conn)
    monkeypatch.setattr(research, "load_store", _boom)
    monkeypatch.setattr(gp, "control_problems", lambda: (("M0007-N20: nope",), 6))
    assert cli.main(["lab", "--db", str(path), "gate", "M0001", "--store",
                     str(_dir(tmp_path))]) == 2
    assert _untouched(conn) == before


def test_a_trial_with_no_recorded_capital_is_refused_before_loading(lab, recorded, monkeypatch):
    conn, _ = lab
    monkeypatch.setattr(store, "provenance_of", lambda c, n: None)
    with pytest.raises(store.LabError, match="no recorded starting capital"):
        gp.plan_methods(conn, ["M0001"])


def test_a_variant_gone_from_the_file_is_listed_not_run(lab, dev_data, recorded, tmp_path, monkeypatch):
    conn, _ = lab
    monkeypatch.setattr(gp, "discover",
                        lambda: {"M0001": (_method((_cand("M0001-A", GATED_PARAMS),)), HERE)})
    (rep,), run = _measure(conn, dev_data, tmp_path, monkeypatch)
    assert rep.missing == ("M0001-B",)
    assert "no longer in the method file): M0001-B" in gp.format_report(rep, run)


def test_a_test_window_store_is_refused(lab, recorded, tmp_path, monkeypatch):
    conn, path = lab
    d = _dir(tmp_path)
    monkeypatch.setattr(research, "load_store", _loader({d: smoke_test_data()}))
    with pytest.raises(store.LabError, match="dev window"):
        gp.load_dev_store(d)
    before = _untouched(conn)
    assert cli.main(["lab", "--db", str(path), "gate", "M0001", "--store", str(d)]) == 2
    assert _untouched(conn) == before


# ---- the command ---------------------------------------------------------------------------------


def test_cli_reports_journals_and_writes_the_grid(lab, dev_data, recorded, tmp_path, monkeypatch, capsys):
    conn, path = lab
    before, notes = _untouched(conn), _insights(conn)
    d = _dir(tmp_path)
    monkeypatch.setattr(research, "load_store", _loader({d: dev_data}))
    grid = tmp_path / "out" / "grid.csv"
    argv = ["lab", "--db", str(path), "gate", "m0001", "M0001", "--store", str(d),
            "--csv", str(grid)]
    assert cli.main(argv) == 0
    out = capsys.readouterr().out
    assert "report only" in out and "reproduced all 6 of the lab's recorded gate-off controls" in out
    assert "gate switched off at:" in out
    assert "lead over SPY a year, by era:" in out and "2009-2015" in out
    assert "what the gate was worth, by era:" in out
    assert "what the shared SPY 200-day gate was worth" in out
    # Two numbers under two labels, and the misleading `Lab N (dev trials)` wording of the ten
    # §5.1 strings is NOT among them (plan invariant 9, reconciler C8). This assertion is what
    # keeps a later edit from quietly adding an eleventh copy.
    assert f"Luck hurdle N: {store.gate(conn).n} (policy {store.gate(conn).policy})" in out
    assert f"Dev trial rows: {before[0]} before, {before[0]} after" in out
    assert "Lab N (dev trials)" not in out
    assert "no method id was minted" in out
    assert _untouched(conn) == before
    assert _insights(conn) == notes + 1  # one method, named twice: one observation
    rows = list(csv.reader(grid.open(encoding="utf-8")))
    assert rows[0] == list(gp.CSV_HEADER)
    assert [(r[1], r[2]) for r in rows[1:]] == [
        ("M0001-A", "gated"), ("M0001-A", "ungated"), ("M0001-B", "gated"),
    ]
    assert rows[1][4] == gp.CARRIES and rows[3][4] == gp.NO_GATE


def test_no_journal_writes_nothing(lab, dev_data, recorded, tmp_path, monkeypatch, capsys):
    conn, path = lab
    before, notes = _untouched(conn), _insights(conn)
    d = _dir(tmp_path)
    monkeypatch.setattr(research, "load_store", _loader({d: dev_data}))
    assert cli.main(["lab", "--db", str(path), "gate", "M0001", "--store", str(d),
                     "--no-journal"]) == 0
    assert "No journal entry" in capsys.readouterr().out
    assert _untouched(conn) == before and _insights(conn) == notes


def test_the_journal_entry_is_plain_words(lab, dev_data, recorded, tmp_path, monkeypatch):
    conn, _ = lab
    (rep,), _run = _measure(conn, dev_data, tmp_path, monkeypatch)
    before = _untouched(conn)
    with conn:
        entry = gp.journal(conn, rep)
    row = conn.execute("SELECT * FROM insights WHERE id = ?", (entry,)).fetchone()
    assert row["kind"] == "observation" and row["method_id"] == "M0001"
    assert row["title"].endswith("what its market safety rule was worth")
    for text in (row["title"], row["body"]):
        for banned in ("M0001", "-NOGATE", "SPY", "200-day average", "`", "DSR", "MAR",
                       "trend", "params"):
            assert banned not in text, banned
    assert "count of tries did not move" in row["body"]
    assert _untouched(conn) == before


def test_the_help_strings_still_format(capsys):
    """argparse %-interpolates every help= string; a bare % there kills `lab --help`."""
    with pytest.raises(SystemExit) as e:
        cli.main(["lab", "gate", "--help"])
    assert e.value.code == 0
    out = capsys.readouterr().out
    for flag in ("--all", "--only", "--gated-only", "--dry-run", "--no-journal", "--csv"):
        assert flag in out, flag
    with pytest.raises(SystemExit):
        cli.main(["lab", "--help"])
    assert "gate" in capsys.readouterr().out
```

**Impact:** 26 new tests. The run is DB-free except for the SQLite lab fixture, so it adds no
Postgres dependency; the whole file runs on the smoke fixture in a few seconds.

**Two notes for the implementer.**

1. `test_the_journal_entry_is_plain_words` bans the words `SPY` and `200-day average` from the
   journal text. The `insight_text` code above writes "below its own long-term average", which
   passes. If a later edit reintroduces either, fix the *text*, not the test — the owner-facing
   rule in `CLAUDE.md` is plain language with no ids or code.
2. `test_a_variant_whose_method_refuses_the_gate_off_is_planned_not_run` calls
   `gp.format_plan([plan])`; the expression written above (`plan.variants and [plan]`) is a
   defensive truthiness idiom — simplify it to `gp.format_plan([plan])` when you write the file.

---

### Step 7: `engine/package_readme.md` — the `lab gate` line **and** phase 1's `lab run --amend` line

**Reconciler, C5.** Phase 1 added `lab run --amend`, the `method_amendments` table and schema v6,
and its plan handed the readme line for them to this phase rather than have two phases edit one
file. This step therefore writes **both** sets of changes. Phase 1 does not touch this file; phase
1 has already landed when this runs, so its symbols exist and the sentences below are true when
written. There is no `package_readme.md` under `engine/src/seer_engine/lab/` — this is the file.

#### 7a — the `gate_probe.py` module-map line

**File:** `engine/package_readme.md:158` — insert one line immediately after the `exposure.py`
module-map line, in the same two-column style.
**Change:**

```
      gate_probe.py         `lab gate` (lab-brakes-and-gate phase 2): what the shared SPY 200-day trend gate was worth, book by book. GATE = ("SPY", 200), GATED/UNGATED arms, ARM_SUFFIX "-NOGATE"; GateOffRefused and gate_off() -- a recursive dataclasses.replace walk that sets a `trend` field holding ("SPY", 200) to None and turns TimingParams(signal="SPY", rule="sma", n=200) into rule="always", and RAISES on any other gate rather than guessing; CONTROLS / CORE_CONTROLS / IMPURE_CONTROLS and control_problems(), which checks the transform against six gate-off configurations the lab already holds before the command measures anything (M0007-N20 -> M0007-N20-NOTREND and four more, plus M0030-C50T's core leg against M0030-C50A; all six matched 2026-10-12); Tally-counting GateAllocator / wrapper_for() (a pass-through, so the gated arm still reproduces its recorded trial); arm_id_for() so an arm never shadows a recorded id (M0064 holds both M0064-P50 and M0064-P50-NOGATE); plan_method()/plan_methods() classifying each recorded variant as carries / no-gate / refused, VariantRow.suspect (a "no gate" verdict is cross-examined against the share of decision days it still held nothing), gate_cost() per era, format_plan() (--dry-run, no store opened), format_report(), summary_line(), lab_summary(), insight_text(), journal(), csv_rows()/write_csv(). Report only: one journal observation per method, never a trial, and never a new method id. Measured 2026-10-12 over the 354 recorded dev trial rows: 225 variants carry the gate and transform cleanly, 69 carry no SPY-200 gate this walk can see, 6 (M0054's two park arms, M0101's four) carry it and refuse to run without it
```

#### 7b — phase 1's amendment mechanism, on the three module-map lines that own it

Three existing module-map lines gain a clause each, in the file's existing style (a landing's name
in parentheses, then what it added). Nothing already on those lines is edited or reordered —
append to the end of each.

**`method.py`** (find the line, it is above `store.py` in the lab block):

```
; plus Amendment, Method.amendments and Method.all_candidates() (lab-brakes-and-gate phase 1) — a method that has already run may grow further separately pre-registered batches of variants of the same idea, recorded under its own method id so the luck gate's N does not move. The old whole-file freeze became two checks read together: the file hashes to store.latest_source_sha (the newest method_amendments row, else the methods.source_sha written once when it first ran), and every recorded trial's configuration still digests to the config_digest the lab holds. Every reader of "what variants does this method have" now asks all_candidates(); candidates is the original batch alone
```

**`store.py`**:

```
; plus the append-only method_amendments side table with AmendmentRow, AMENDMENT_COLUMNS, insert_amendment(), amendments_of(), latest_source_sha(), SCHEMA_VERSION now "6" and the purely additive _v5_to_v6 migration step (lab-brakes-and-gate phase 1). methods.source_sha is still written exactly once and methods_source_sha_once still refuses to let it move; an amended file's later shas live in the side table, and latest_source_sha is the one place that answers which sha a file is supposed to hash to today
```

**`runner.py`**:

```
; plus the amendment path (lab-brakes-and-gate phase 1): AMEND_CLOSED, pending_amendment(), preflight(..., amend=) returning the Amendment it resolved, run_method(..., amend=) recording the batch under the method's own id and appending a method_amendments row instead of rewriting methods.source_sha, and preflight_test() checking the latest recorded sha. `lab run --amend MNNNN` runs the next Amendment the file declares and the lab has not recorded; it never moves methods.status (store.reevaluate_method is the one door on rejected -> dev-eligible) and refuses any method that has reached the test window
```

#### 7c — the `Last Updated` line

And line 4, the `Last Updated` line, gains a leading clause in the file's existing style. It names
**both** landings, phase 1 first because it is the one that changed a lab rule:

```
**Last Updated**: 2026-10-12 (lab-brakes-and-gate phase 1: a method that has already run may now be **amended** — `lab run --amend MNNNN` runs a further, separately dated and separately pre-registered batch of variants declared in the same method file and records them under that method's own id, so the luck gate's N does not move (measured 2026-10-12: a new method id prices at N = 75 against 74 for a variant of a counted idea, retroactively for all 130 methods). `methods.source_sha` is still written exactly once; later shas live in the new append-only `method_amendments` table (schema v6). The whole-file freeze became two checks read together: the file hashes to `store.latest_source_sha`, and every recorded trial's configuration still digests to its recorded `config_digest`. — and lab-brakes-and-gate phase 2: the report-only `lab gate [MNNNN ...] [--all]` (`seer_engine.lab.gate_probe`) re-runs every recorded dev variant twice — as recorded, and with the shared SPY 200-day trend gate switched off and nothing else moved — and prints the lead over SPY whole-window and per era beside what the gate was worth in each. The gate is found by a generic recursive `dataclasses.replace` walk over the params, so no method file changes and no method id is minted; the walk is checked against six gate-off configurations the lab already holds before anything runs, and a variant whose gate it cannot identify is listed and never run as though the gate were off. Measured 2026-10-12: of the lab's 354 recorded dev trial rows, 225 variants carry the gate and transform cleanly, 69 carry none this walk can see, and 6 carry it and refuse to run without it. Before that, lab-exposure-diagnostic (P1-ENG-XP7Q): …
```

(keep the rest of line 4 verbatim from `the report-only \`lab exposure MNNNN …` onwards, prefixed
by `Before that, `.)

**Impact:** documentation only.

---

## Verification

Run every command from the worktree root
`/home/miftah/.worktrees/seer/lab-brakes-and-gate`, with the **main checkout's** venv.

```bash
export WT=/home/miftah/.worktrees/seer/lab-brakes-and-gate
export PY=/home/miftah/seer/engine/.venv/bin/python
export PYTHONPATH=$WT/engine/src
docker start seer-pg
export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres
```

**Guard the committed database first** — a lab command migrates `lab/lab.sqlite` on connect, even
for a read:

```bash
cd $WT && md5sum lab/lab.sqlite      # expect 4a34ddb823ec88a5e86afeb5d7e1b7c9
cp lab/lab.sqlite /tmp/lab.sqlite.phase2.bak
```

**Lint:**

```bash
/home/miftah/seer/engine/.venv/bin/ruff check engine
```

**Build (import the new module and parse the new CLI):**

```bash
cd $WT && $PY -c "from seer_engine.lab import gate_probe; print(gate_probe.GATE)"
cd $WT && $PY -m seer_engine lab gate --help >/dev/null && echo "help formats"
cd $WT && $PY -m seer_engine lab --help | grep -q '^\s*gate\b' && echo "listed"
```

**Tests — the new file first, then the suite:**

```bash
cd $WT && $PY -m pytest engine/tests/test_lab_gate_probe.py -q
cd $WT && $PY -m pytest engine/tests -q
```

Expected: **the branch's current count + 26 passed, 3 skipped.** The three skips are the opt-in
live-store tests and must stay skips.

**Do not use 4364 as the baseline.** That figure was measured at base commit `d3c1ec4`, before
**phase 1 landed** — and phase 1 is now this phase's dependency (reconciler, C4), so it is always
already on the branch when this runs. It adds roughly 15 tests of its own (its `test_lab_amendments.py`
has 14, plus one migration test in `test_lab_snapshot.py`). Re-measure with
`git stash && $PY -m pytest engine/tests -q | tail -3 && git stash pop`, or simply read the count
before and after this phase's commit; the number that matters is **+26 and 0 new skips**, not an
absolute.

**Manual check — the transform against the real lab, no store, nothing written:**

```bash
cd $WT && $PY -m seer_engine lab gate M0024 M0030 M0053 \
  --store /home/miftah/seer/engine/.research --dry-run
cd $WT && md5sum lab/lab.sqlite    # migrated by the connect: restore it below
```

Expect the controls line (`reproduced all 6 …`), `M0024-SAME-N20` and `M0030-C50T` under *carries
the shared gate*, `M0024-SAME-N20-NOTREND` under *no gate this probe can see*, and an empty
*refuses* section for these three methods.

```bash
cd $WT && $PY -m seer_engine lab gate --all \
  --store /home/miftah/seer/engine/.research --dry-run | tail -30
```

Expect, measured 2026-10-12: **225** carries, **69** no-gate, **6** refused
(`M0054-HALF-PARK`, `M0054-PARK-SPY`, `M0101-BAND-3`, `M0101-BAND-5`, `M0101-CTRL`,
`M0101-FABER`) over **300** live recorded variants, and `recorded, but no longer in a method file`
listing 54.

**Manual check — a real two-arm run on one book, report only** (about a minute; this is the
smallest end-to-end proof, and phase 5 does the full sweep):

```bash
cd $WT && $PY -m seer_engine lab gate M0024 --only M0024-SAME-N20 \
  --store /home/miftah/seer/engine/.research --no-journal
```

Read the `2008` and `2009-2015` rows of *what the gate was worth*. The handover's §2 control says
they should be large and positive in 2008 and negative after 2009; whatever they say, the write-up
is phase 5's and this phase only has to produce the number.

**Restore the database — this phase commits no lab state:**

```bash
cd $WT && cp /tmp/lab.sqlite.phase2.bak lab/lab.sqlite
cd $WT && md5sum lab/lab.sqlite      # back to 4a34ddb823ec88a5e86afeb5d7e1b7c9
cd $WT && git status --porcelain lab/lab.sqlite   # must be empty
```

**Exit criteria**

1. `lab gate [MNNNN …] | --all` runs, and `--dry-run` classifies every recorded dev variant with
   no store opened.
2. `control_problems()` returns `((), 6)` against the committed method files, and `lab gate`
   refuses with exit 2 when it does not.
3. Every variant the transform refuses (6 today) is named with its reason and **has no gate-off
   arm**; no column in the grid labelled "gate off" was produced by guessing.
4. The gated arm reproduces its recorded total return at `REPRO_TOL` on the smoke fixture, which
   is how the pass-through wrapper is known not to perturb the measurement.
5. `store.dev_trial_count`, `store.test_looks`, `store.gate` and every trial-side table are
   unchanged across a full run, printed before and after, and `lab/lab.sqlite` is byte-identical
   under `--no-journal` once restored by explicit path.
6. `ruff check engine` is clean; the suite is green with Postgres up and no DB test skipped.
7. `lab/lab.sqlite` and `web/data/lab.json` are **not** in this phase's commit.
8. `grep -c 'Lab N (dev trials)' engine/src/seer_engine/commands/lab.py` returns **10**, not 11:
   the ten are untouched and this phase adds none (invariant 9, reconciler C8).
9. `engine/package_readme.md` names **both** landings — `lab gate` and phase 1's `lab run --amend`
   (reconciler, C5).

---

## Handoffs

- **Phase 5 runs the command; this phase does not.** `lab gate --all --store
  /home/miftah/seer/engine/.research --csv docs/backtests/2026-10-12-brakes-and-gate-gate-grid.csv`
  is ~519 backtests (225 × 2 + 69) and will take a long time; `--dry-run` first, and
  `--gated-only` if the sweep has to be cut down. Any run that journals must be followed by
  `lab stage`, which is also phase 5's.
- **No eleventh `Lab N (dev trials)` string** (reconciler, C8). `_gate`'s closing `print`
  deliberately does **not** reuse the wording of the ten §5.1 strings at `commands/lab.py:1399,
  1684, 1718, 1739, 1785, 1817, 1870, 1923, 2238, 2287`: it prints the gate's own N under its own
  label and the dev trial row count under its own. So **phase 6's memo still says ten**, which is
  correct at base commit `d3c1ec4` and still correct after this phase; its exit check
  `grep -c 'Lab N (dev trials)' engine/src/seer_engine/commands/lab.py` still returns 10. Phase 6
  notes that the set's one new command prints the clear form — as evidence the owner can weigh,
  **not** as a recommendation, and without touching the ten.
- **`exposure.load_dev_store`'s refusal text says "lab exposure"** even when `lab gate` raised it
  (`exposure.py:610, 615`). **Deliberate non-fix, owned by nobody on purpose** (reconciler, C13).
  Phase 1 does touch one line of `exposure.py` (`:500`'s `by_id` comprehension, C6), so an owner
  was available — the reconciler still declined, because fixing the message means giving
  `load_dev_store` a command-name parameter, which is a signature change on a function this phase
  only imports and which three other call sites pass through. The refusal's exit code, its reason
  and the store path it names are all correct; only the command name in the sentence is wrong, and
  `lab gate`'s own `--store` help text already says which store it wants. Recorded in the index's
  Decisions rather than left as a silent gap. A later landing that owns `exposure.py` properly
  should take it together with the `arm_of` duplication below — they are the same refactor.
- **`gate_probe.arm_of` restates `exposure.arm_of`.** The duplication is deliberate and is marked
  as such in the docstring: `exposure.arm_of` reads its tally off an `ExposureParams` by type, and
  `exposure.py` is not this phase's to edit. The clean fix is to lift `arm_of` into a shared
  `lab/arms.py` taking the tally as an argument; that is a refactor for a later landing, after
  both commands have been run in anger.
- **Phases 3 and 4 do not need this module.** Their gate-off candidates are written by hand into
  the method files; measured today, `gate_off(M0030-C50T.params)` lands exactly on the index's
  `M0030-C50A-NOGATE` params, so the two agree — but phase 3 should re-derive its digest, not take
  it from here.
- **`M0001-TV10-NOTREND` is not a clean gate control** (it also moves the own-vol window from 63
  to 126 sessions, measured 2026-10-12). **Phase 5's write-up carries it** (reconciler, C14), in
  *The market switch, priced across the roster* — the lab has believed it was a control, and the
  probe is the clean one M0001 never had. `IMPURE_CONTROLS` in this module is the source; quote
  the constant's own comment, not this bullet.
- **`--all` sweeps every method, including the dividend family the exposure diagnostic closed.**
  Phase 5 may want to exclude closed families to keep the grid readable; `--only` and naming
  methods already allow it, and no code change is needed.

---

## Rollback

This phase is additive. `git revert` its commit, or by hand:

```bash
cd $WT
rm engine/src/seer_engine/lab/gate_probe.py engine/tests/test_lab_gate_probe.py
git checkout -- engine/src/seer_engine/commands/lab.py engine/package_readme.md
$PY -m pytest engine/tests -q     # back to the branch's pre-phase-2 count (phase 1 included)
```

**Careful with `git checkout --` on those two files:** phase 1 has already landed on this branch,
so both carry its changes too — `--amend` on the `run` subparser, `_run`'s new prints, and the
three amendment clauses in the readme. `git checkout --` restores them from HEAD, which is right
*only* if this phase's work is not yet committed. If it is, `git revert` this phase's commit
instead; a `checkout` from an older ref would silently take phase 1's work out with it.

Nothing else is touched: no method file, no `lab/lab.sqlite`, no `web/data/lab.json`, no recorded
trial, no status, no research store. `engine/.research` is read-only to this phase and is never
rebuilt (invariant 8), so a rollback costs nothing but the commit.

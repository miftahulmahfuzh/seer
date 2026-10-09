> Adopted from `TRIAL_REPRODUCIBILITY_PLAN.md` phase 3. Source: `.workflows/plan/trial-reproducibility/phase-3.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 3: Compare like with like: gate refuses, reports warn, `lab run` pins the store

**Plan set:** `TRIAL_REPRODUCIBILITY_PLAN.md`
**Analysis:** `20261009-192826-T7RQ_code_analyzer.md`
**Satisfies:** R2, R1. R2: `trials.store_fingerprint` is the wrong key; the price fingerprint is the right one. The gate refuses on it, the reports warn on it. R1: policy (c′), a refusal on the price fingerprint, and policy (a), a pinned dev store, made mechanical.
**Depends on:** Phase 2 (`trial_provenance`, `store.provenance_of`, `store.ProvenanceRow`, `store.insert_provenance`, `ResearchData.price_fingerprint`, the v5 migration backfill, the test helpers `labkit.stamp_provenance` / `labkit.LAB_PRICE_FINGERPRINT`, and its edits to `hardgate.trial_deposits`, `commands/lab.py:_costs` and `test_lab_hardgate.py`, which this plan quotes the tree after)
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine/lab` (`hardgate.py`), `engine/src/seer_engine/commands` (`lab.py`)

---

## Goal

Before this phase nothing in the lab checks that two recorded curves were measured on the same prices. After it:
- the hard gate fails closed. `fold_record`, and through it `check`, `fold_summary` and `summary`, raises `store.LabError` when the benchmark's price fingerprint or any of the method's dev trials' price fingerprint is unknown or differs.
- `lab walkforward` and `lab regime` print one `WARNING` line for each method that is not comparable.
- `lab run` refuses a dev store whose prices are not the benchmark's, and it does so before any backtest runs.

On the committed lab this changes no verdict. All 148 dev trials share price fingerprint `5451195fd552…` (analysis M1, M5), so the rule strands 0.

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.
**Creates:**
- `hardgate.Geometry.bench_n: int`: a new third field, the `trials.n` of the benchmark row the geometry was cut from (`lab/hardgate.py`).
- `hardgate.benchmark_n(conn) -> int | None` (`lab/hardgate.py`): the benchmark trial `geometry` reads, or None.
- `hardgate.mismatches(conn, bench_n: int, rows: Sequence[sqlite3.Row]) -> tuple[str, ...]` (`lab/hardgate.py`): the low-level check that reports reuse. `rows` need `n` and `candidate_id`.
- `hardgate.comparability(conn, method_id: str, geo: Geometry | None = None) -> tuple[str, ...]` (`lab/hardgate.py`): human-readable mismatch descriptions, `()` when comparable.
- `hardgate.describe(problems: Sequence[str], limit: int = 3) -> str` (`lab/hardgate.py`).
- `hardgate.pin_dev_store(conn, price_fingerprint: str | None) -> None` (`lab/hardgate.py`): raises `store.LabError` when `price_fingerprint` is None (unknown, fail closed — checked first, benchmark or not), when the benchmark's prices are unknown, or when they differ; silent only when the store names its prices and the lab has no benchmark trial.
- `commands.lab._comparability_warnings(conn, bench_n: int, rows, wanted: set[str]) -> list[str]` (`commands/lab.py`).
- Module docstring section **(D10)** in `lab/hardgate.py`.
- Test helpers: **none**. `labkit.LAB_PRICE_FINGERPRINT` and the idempotent `labkit.stamp_provenance` are created by Phase 2 (reconciled: one stamping helper for the set); this phase only imports them.

**Signature changes:**
- `Geometry(bench, folds)` -> `Geometry(bench, folds, bench_n)`. There is exactly one constructor call, `hardgate.geometry`, and nothing else in `src/` or `tests/` constructs it.
- `fold_record` / `check` / `fold_summary` / `summary`: the signatures are unchanged, but they now raise (`summary` reports) on a price mismatch.

**Requires (from earlier phases):**
- Phase 2: `store.provenance_of(conn, trial_n: int) -> sqlite3.Row | None`, where the row has a `price_fingerprint` key (`str | None`).
- Phase 2: `store.ProvenanceRow(trial_n: int, initial_idr: Decimal, price_fingerprint: str | None, source: str, measured: str)`, `source` in `('recorded','backfill')`; `insert_provenance` refuses a non-`Decimal` capital.
- Phase 2: `store.insert_provenance(conn, rows)`, with the caller holding the transaction; refuses a second row for the same trial.
- Phase 2: `ResearchData.price_fingerprint: str | None = None` — a dataclass field (the last one), not a property. `research.load_store` always sets it; None means a hand-built `ResearchData` that never named its prices, and this phase reads None as **unknown → refuse**.
- Phase 2: `store.P7A_PRICE_FINGERPRINT`; test helpers `labkit.LAB_PRICE_FINGERPRINT` (`= store.P7A_PRICE_FINGERPRINT`) and `labkit.stamp_provenance(conn, trial_ns, *, price_fingerprint=LAB_PRICE_FINGERPRINT, initial_idr=Decimal("10000000"))`, idempotent (skips a trial that already has a row), caller holds the transaction.
- Phase 2: `store.connect` migrates to v5 and backfills every existing trial. Benchmark trial #1 gets `5451195fd552e208eaadfc6bc89241b9b8e3e6ccb0f4c447a84bbc4f32e7d90a`.
- Phase 2: `hardgate.trial_deposits` divides by `runner.recorded_capital`. This phase does not touch `trial_deposits`.

**Leaves alone (owned by others):**
- `lab/walkforward.py` (pure; `buy_signal` is the owner's rule).
- `lab/store.py` schema and migration, `research.py`, `lab/runner.py`, `lab/remeasure.py`, `lab/real_costs.py`, `lab/seed.py` (Phase 2).
- `hardgate.trial_deposits` body (Phase 2).
- `backtest/dev.py` (Phase 1).
- docs, skills, `lab/lab.sqlite`, `web/data/lab.json` (Phase 4).

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/hardgate.py` | modify | (D10) docstring section; `Sequence` import; `Geometry.bench_n`; `geometry` carries n; new `benchmark_n`, `mismatches`, `describe`, `comparability`, `pin_dev_store`; `fold_record` refuses on a mismatch |
| `engine/src/seer_engine/commands/lab.py` | modify | usage lines for `lab run` / `lab promote`; `_run` calls `hardgate.pin_dev_store`; new `_comparability_warnings`; `_regime` and `_walkforward` print its lines |
| `engine/tests/test_lab_hardgate.py` | modify | `labkit` import gains `LAB_PRICE_FINGERPRINT`; `_benchmark` / `_method` stamp provenance; the benchmark takes the P7a store fingerprint; new D10 tests (gate, pin, report warnings, CLI) |
| `engine/tests/test_lab_prereg.py` | modify | `_benchmark` and `_real_method` stamp provenance |
| `engine/tests/test_lab_status.py` | modify | `_method_at` stamps provenance |

**Line numbers below are against the tree after Phase 2**, which edits three of these files first:
- `lab/hardgate.py`: Phase 2 replaces `trial_deposits` (`e5eda52` :183-227, 45 lines) with 55 lines, so every line after :227 moves **+10** (`Geometry` :240, `geometry` :258, `_dev_curves` :297-314, `fold_record` :317). Lines 1-182 (the docstring and imports) do not move. Step 1 then inserts the (D10) docstring section above all of them, so within this phase anchor on function names, not on these numbers.
- `commands/lab.py`: Phase 2 edits `_costs` only (+5 lines), so `_regime` is at :1817 and `_walkforward` at :1908; `_run` (:1248) and the usage block (:13-24) do not move. Phase 2 does not touch any line this phase replaces.
- `tests/test_lab_hardgate.py`: Phase 2 adds two import lines (`from decimal import Decimal`, `from labkit import stamp_provenance`), adds `with conn: stamp_provenance(conn, [int(row["n"])])` to the two funded tests, and inserts `_funded_trial` + two tests after `test_a_moved_contribution_schedule_refuses_rather_than_guesses`. `_benchmark` / `_method` are at :81-112, and the file still ends with `test_there_is_no_override`.

Anchor every edit on the function name; the numbers are a guide.

Fixture audit. `grep -rln "REF-SPY-HOLD\|hardgate\|BENCH_CANDIDATE" engine/tests` returns these files: `test_lab_hardgate.py`, `test_lab_prereg.py`, `test_lab_status.py`, `test_lab_test_window.py`, `test_lab_remeasure_seed.py`, `test_lab_walkforward.py`, and the `test_backtest_*` / `test_strategy_*` / `test_registry` / `test_sim_costs` / `test_sean_calibrate` family.
- Only the first three insert dev trials and then call the gate (`check` / `fold_record` / `summary`, directly or via `lab promote` / `lab status`).
- `test_lab_test_window.py` mentions hardgate only in a docstring.
- `test_lab_remeasure_seed.py` uses `REF-SPY-HOLD` as a seed candidate, not as a gate benchmark.
- `test_lab_walkforward.py` tests the pure module.
- The `backtest` / `strategy` files mean the backtest walk-forward or `regime`, not the lab gate.
- No existing test runs `lab walkforward`, `lab regime` or `lab run` through the CLI (re-checked by the reconciler: no test reaches `commands/lab.py:_run`). So Phase 2's `smoke_data().price_fingerprint == "smoke"` never meets the pin: runner-level tests call `runner.run_method`, which is not pinned, and this phase's own `_run` tests stub `research.load_store` with an explicit price fingerprint.
- `test_lab_status.py`'s `_method` helper is used only by fixtures without a benchmark, where `geometry` refuses before comparability is read, so it is left alone.

## Implementation Steps

### Step 1: Record the decision (D10) in the module docstring
**File:** `engine/src/seer_engine/lab/hardgate.py:145` (append after the last paragraph of **(D6)**, which ends "…they simply read ``rejected`` themselves today.", and before the closing `"""` on line 146)
**Change:** add a new decision section in the voice of D2–D6. It must not contain the substrings `force`, `override` (except inside "no override"), `skip_gate`, `getenv` or `environ`, because `test_there_is_no_override` scans this module's source. Avoid "enforce" in particular.
**Code:** insert these lines between line 145 and line 146:
```python

**(D10) What makes two recorded curves comparable? -- the prices they were measured on, read from
``trial_provenance.price_fingerprint``. A difference or an unknown refuses, and there is no way
past it.**

The handover (§5.1) asked whether ``trials.store_fingerprint`` is enough to detect a comparison
across stores. It is the wrong key. ``research.fingerprint_of`` hashes the store's whole ``files``
map, so adding or rebuilding ``fundamentals.csv`` moves it without moving one bar. Measured on
2026-10-09: the lab's 148 dev trials carry three store fingerprints -- ``399d0d254c7a`` (84),
``5451195fd552`` (58, the benchmark ``REF-SPY-HOLD``, trial #1, among them) and ``e597367bb680``
(6) -- and the current store's fingerprint recomputed **without** ``fundamentals.csv`` is
``5451195fd552`` exactly. The three stores hold byte-identical prices. That hash is
``research.price_fingerprint_of``; it is recorded per trial from schema v5 on and was backfilled
for every trial before it.

==================================  ======================  =====================================
rule                                strands today           note
==================================  ======================  =====================================
refuse across ``store_fingerprint``  90 of 148 dev trials,   every ``M*`` trial is ``399d0d`` or
                                    all seven dev-eligible  ``e597367`` against a ``5451195``
                                    methods                 benchmark: it would close every
                                                            promotion over a file no price-only
                                                            method reads
**refuse across price fingerprint**  **0 of 148**            all 148 carry ``5451195fd552``
warn only                           0                       and the day a store is rebuilt, the
                                                            gate decides a promotion out of
                                                            cross-store arithmetic anyway
==================================  ======================  =====================================

So the gate refuses -- ``fold_record`` raises, and with it ``check``, ``fold_summary`` and (as
text) ``summary`` -- when the benchmark trial or **any** of the method's dev trials has no
provenance row, records no price fingerprint, or records a different one. Any one variant is
enough, because every variant is a candidate in every fold's pick. An unknown fails closed: a
trial whose prices nobody recorded is not evidence that they match.

The two reports, ``lab walkforward`` and ``lab regime``, **warn** on the same condition, one line
per method, and print the row anyway. They decide nothing, and a report that refused would hide
the very record its reader came to inspect. ``lab run`` **refuses** a dev store whose price
fingerprint is not the benchmark's (``pin_dev_store``), before any backtest, because a trial it
recorded there could never be compared with anything and its method id would be spent on it. A
store is copied between machines, never rebuilt (``.claude/skills/sync-research-store``); if the
lab's prices ever have to move, that is a change argued in git -- a new benchmark trial and an
edit to this rule -- and no such path is built here.

What actually made recorded trials irreproducible between 2026-10-04 and today was the engine's
starting capital, not the store: ``INITIAL_IDR`` moved from 20M to 10M IDR and whole-share
rounding made that result-moving. That is recorded beside the price fingerprint
(``trial_provenance.initial_idr``) and honoured by ``trial_deposits`` and every re-run; it is not
a comparability question, because a recorded curve is normalised to its own opening cash.
```
**Impact:** documentation only. `test_the_module_answers_the_four_open_questions` still finds (D2), (D3), (D4) and (D6).

### Step 2: Add the `Sequence` import
**File:** `engine/src/seer_engine/lab/hardgate.py:148-157`
**Change:** replace the import block.
**Code:**
```python
from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from seer_engine.backtest import regime
from seer_engine.lab import store
from seer_engine.lab import walkforward as wf
```
**Impact:** none.

### Step 3: `Geometry` carries the benchmark's trial number
**File:** `engine/src/seer_engine/lab/hardgate.py:240-251` (`e5eda52` :230-241, +10 after Phase 2)
**Change:** replace the class.
**Code:**
```python
@dataclass(frozen=True, slots=True)
class Geometry:
    """The benchmark curve and the folds cut from it -- the same split for every method.

    Global on purpose: the folds come from ``REF-SPY-HOLD``, not from the method under test, so
    two methods are never judged on different windows. Computed once per command and passed down,
    because ``lab status`` asks for a summary per dev-eligible method and re-cutting the folds
    each time would be the same arithmetic seven times over.

    ``bench_n`` is the ``trials.n`` the curve was read from. The comparability rule (D10) needs
    it: a method is scored against **this** row's prices, so the row has to travel with the
    curve rather than be looked up again and risk naming a different one.
    """

    bench: tuple[tuple[date, float], ...]
    folds: tuple[wf.Fold, ...]
    bench_n: int
```
**Impact:** the only constructor is `geometry` (Step 4). `tests/test_lab_hardgate.py` reads only `geo.bench` and `geo.folds`.

### Step 4: `geometry` passes the row's n
**File:** `engine/src/seer_engine/lab/hardgate.py:258-294` (`e5eda52` :248-284, +10 after Phase 2)
**Change:** replace the function. Only the final `return` changes, because the query already selects `n`.
**Code:**
```python
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
    return Geometry(tuple(bench), the_folds, int(row["n"]))
```
**Impact:** none beyond Step 3.

### Step 5: The comparability rule, its helpers and the store pin
**File:** `engine/src/seer_engine/lab/hardgate.py:315`, inserted after `_dev_curves` (which ends at line 314 after Phase 2, `return [r for r in rows if json.loads(r["curve_json"])]`) and before `def fold_record` (line 317)
**Change:** add five functions.
**Code:**
```python
def benchmark_n(conn: sqlite3.Connection) -> int | None:
    """The ``trials.n`` of the benchmark row ``geometry`` reads, or None when the lab has none.

    The same row by the same rule -- the first ``REF-SPY-HOLD`` dev trial that carries a curve --
    so ``pin_dev_store`` and the gate can never be talking about two different benchmarks.
    """
    row = conn.execute(
        "SELECT n FROM trials WHERE window = 'dev' AND candidate_id = ? "
        "AND curve_json IS NOT NULL ORDER BY n LIMIT 1",
        (regime.BENCH_CANDIDATE,),
    ).fetchone()
    return None if row is None else int(row["n"])


def mismatches(
    conn: sqlite3.Connection, bench_n: int, rows: Sequence[sqlite3.Row]
) -> tuple[str, ...]:
    """Why ``rows`` cannot be compared with benchmark trial ``bench_n``; ``()`` when they can.

    The rule is (D10): two curves are comparable only when both trials record the **same price
    fingerprint** -- ``trial_provenance.price_fingerprint``, the store's four price files hashed
    with ``fundamentals.csv`` left out. ``trials.store_fingerprint`` is deliberately not read: it
    moves with the fundamentals panel, and refusing on it would strand every method in the lab
    over a file no price-only method opens.

    Fails closed. A trial with no provenance row, or one whose price fingerprint is NULL, is a
    mismatch, not a pass: "nobody recorded the prices" is not evidence that they match. When the
    benchmark itself is unknown, that one sentence is the whole answer, because nothing can be
    compared with it.

    ``rows`` need ``n`` and ``candidate_id`` -- the shape every caller already selects. Each
    sentence names the candidate and its trial number, so a reader can find the row.
    """
    bench = store.provenance_of(conn, bench_n)
    name = f"the benchmark {regime.BENCH_CANDIDATE} (trial #{bench_n})"
    if bench is None:
        return (f"{name} has no provenance row, so the prices it was measured on are unknown",)
    bench_prices = bench["price_fingerprint"]
    if bench_prices is None:
        return (
            f"{name} records no price fingerprint, so the prices it was measured on are unknown",
        )
    out: list[str] = []
    for r in rows:
        n = int(r["n"])
        label = f"{r['candidate_id']} (trial #{n})"
        mine = store.provenance_of(conn, n)
        if mine is None:
            out.append(f"{label} has no provenance row")
        elif mine["price_fingerprint"] is None:
            out.append(f"{label} records no price fingerprint")
        elif str(mine["price_fingerprint"]) != str(bench_prices):
            out.append(
                f"{label} was measured on prices {str(mine['price_fingerprint'])[:12]}, "
                f"the benchmark on {str(bench_prices)[:12]}"
            )
    return tuple(out)


def describe(problems: Sequence[str], limit: int = 3) -> str:
    """``problems`` as one clause: the first ``limit`` joined by ``"; "``, then a count of the rest.

    A method can carry a dozen variants; a refusal that listed every one would bury its own
    reason. The first few name the shape of the problem, and the count says how far it reaches.
    """
    shown = "; ".join(problems[:limit])
    rest = len(problems) - limit
    return shown if rest <= 0 else f"{shown}; and {rest} more"


def comparability(
    conn: sqlite3.Connection, method_id: str, geo: Geometry | None = None
) -> tuple[str, ...]:
    """Why ``method_id``'s dev curves cannot be scored against the benchmark; ``()`` when they can.

    Exactly the rows the gate scores (``_dev_curves``) against exactly the benchmark row it cut
    the folds from (``geo.bench_n``). Raises ``store.LabError`` only when there is no geometry at
    all, the same way ``fold_record`` does.
    """
    geo = geometry(conn) if geo is None else geo
    return mismatches(conn, geo.bench_n, _dev_curves(conn, method_id))


def pin_dev_store(conn: sqlite3.Connection, price_fingerprint: str | None) -> None:
    """Refuse a dev store whose prices are not the benchmark's. Raises ``store.LabError``.

    Called by ``commands/lab.py:_run`` after the store is loaded and **before** any backtest, so
    a refusal records nothing and spends no method id. This is policy (a) of the handover, made
    mechanical (D10): the dev store is pinned to the prices the lab's yardstick was measured on,
    and a rebuilt store -- which re-fetches yfinance and is never bit-identical -- cannot slip
    into the record unannounced.

    ``price_fingerprint`` is ``ResearchData.price_fingerprint``. ``research.load_store`` always
    sets it; None (a hand-built ``ResearchData`` that never named its prices) is **unknown** and
    refuses first, benchmark or not, because every trial recorded on it would carry a NULL price
    fingerprint that the gate refuses forever.

    Otherwise silent when the lab has no benchmark trial: such a lab can promote nothing anyway
    (``geometry`` refuses), and a fresh lab has to be able to run before it has a benchmark.
    Refuses when the benchmark exists but its prices are unknown, because every trial this run
    recorded would then be refused by the gate as incomparable.
    """
    if price_fingerprint is None:
        raise store.LabError(
            f"this research store carries no price fingerprint, so nothing can show its prices "
            f"are the ones the lab's benchmark {regime.BENCH_CANDIDATE} was measured on, and "
            f"every trial recorded on it would be refused by the hard gate as incomparable "
            f"(lab/hardgate.py, D10). Nothing ran and nothing was recorded. research.load_store "
            f"always names a store's prices: point --store at a store this code built or copied"
        )
    n = benchmark_n(conn)
    if n is None:
        return
    bench = store.provenance_of(conn, n)
    recorded = None if bench is None else bench["price_fingerprint"]
    if recorded is None:
        why = "has no provenance row" if bench is None else "records no price fingerprint"
        raise store.LabError(
            f"the lab's benchmark {regime.BENCH_CANDIDATE} (trial #{n}) {why}, so no research "
            f"store can be shown to carry the prices it was measured on, and the hard gate "
            f"refuses every comparison against it (lab/hardgate.py, D10). Nothing ran and "
            f"nothing was recorded"
        )
    if str(recorded) != price_fingerprint:
        raise store.LabError(
            f"this research store's prices (price fingerprint {price_fingerprint[:12]}) are not "
            f"the prices the lab's benchmark {regime.BENCH_CANDIDATE} (trial #{n}) was measured "
            f"on ({str(recorded)[:12]}). Every trial recorded here would be refused by the hard "
            f"gate as incomparable, and the method id would be spent on it. Nothing ran and "
            f"nothing was recorded. A store is copied between machines, never rebuilt: point "
            f"--store at a copy of the one the lab was measured on (the sync-research-store "
            f"skill). Moving the lab's prices is a change argued in git (D10), not a flag on "
            f"this command"
        )
```
**Impact:** new public names only. Nothing calls them until Steps 6 and 8–10.

### Step 6: `fold_record` refuses an incomparable method
**File:** `engine/src/seer_engine/lab/hardgate.py:317-338` (`e5eda52` :307-328, +10 after Phase 2; before Step 5's insertion)
**Change:** replace the function. The comparability check goes after the "no curve" refusal, so that test keeps its message, and before `trial_deposits`, so a funded trial with no provenance gets this sentence rather than Phase 2's `recorded_capital` refusal.
**Code:**
```python
def fold_record(
    conn: sqlite3.Connection, method_id: str, geo: Geometry | None = None
) -> wf.Record:
    """``method_id``'s whole walk-forward record, de-funded, on the shared geometry.

    The benchmark is measured without deposits: ``REF-SPY-HOLD`` is a seed buy-and-hold trial and
    was never fed. That is the same treatment ``lab walkforward`` gives it, deliberately -- the
    two must not disagree about what a fold says.

    Refuses (D10) when any of the method's curves was measured on prices other than the
    benchmark's, or on prices nobody recorded. A fold scored across two price histories measures
    the data, not the method.
    """
    geo = geometry(conn) if geo is None else geo
    rows = _dev_curves(conn, method_id)
    if not rows:
        raise store.LabError(
            f"{method_id} has no dev trial carrying a monthly curve, so no fold can be scored "
            f"and it cannot be promoted. The hard gate fails closed on thin evidence: a method "
            f"with no out-of-sample record is not a method with a clean one"
        )
    problems = mismatches(conn, geo.bench_n, rows)
    if problems:
        raise store.LabError(
            f"{method_id} cannot be scored against {regime.BENCH_CANDIDATE}: "
            f"{describe(problems)}. The hard gate compares two curves only when both were "
            f"measured on the same prices -- the price fingerprint each trial records, "
            f"fundamentals excluded (D10) -- and fails closed when either side's prices differ "
            f"or are unknown. There is no override"
        )
    curves = {r["candidate_id"]: _curve_of(r) for r in rows}
    deposits = {
        r["candidate_id"]: trial_deposits(conn, r, curves[r["candidate_id"]]) for r in rows
    }
    return wf.Record(method_id, wf.evaluate(curves, list(geo.bench), geo.folds, deposits))
```
**Impact:**
- `check` raises the same error before its fold-count conditions.
- `summary` catches it as `"not scoreable (…)"`, `prereg.fold_text` as `"not recorded: …"`, and `_hard_gate_states` puts it in the refusal line.
- On the committed lab after the v5 migration, `mismatches` returns `()` for all seven dev-eligible methods, so nothing changes there.

### Step 7: Usage text for `lab run` and `lab promote`
**File:** `engine/src/seer_engine/commands/lab.py:13-24`
**Change:** replace the two usage entries.
**Code:**
```
    lab run M0007 [--store DIR] [--allow-coverage F]
                                    run a committed method on the dev window, record its trials;
                                    a method with a MarketAware allocator is refused when the
                                    store's fundamental panel covers less than 80% of the window,
                                    and every method is refused, before any backtest, when the
                                    store's prices are not the ones the lab's benchmark was
                                    measured on (lab/hardgate.py, D10)
    lab promote M0007               pre-register the best dev-eligible variant by MAR in
                                    docs/lab/prereg/M0007.md and move the method to promoted;
                                    commit that file before `lab test` will spend the one look.
                                    REFUSES a method that does not win a majority of its
                                    walk-forward folds, or that is scoreable on fewer than the
                                    folds the benchmark yields, or whose curves were measured on
                                    prices other than the benchmark's, or whose family or ancestry
                                    already reads test-failed (lab/hardgate.py). The refusal
                                    comes before anything is written, and there is no override
```
**Impact:** `--help` / module docstring text only.

### Step 8: `lab run` pins the dev store
**File:** `engine/src/seer_engine/commands/lab.py:1248-1286`
**Change:** replace `_run`. It imports `hardgate` and calls `pin_dev_store` immediately after the store loads, before `preflight_data` and `run_method`. There is no flag.
**Code:**
```python
def _run(conn, args) -> int:
    from seer_engine.lab import hardgate, runner
    from seer_engine.lab.method import discover

    methods = discover()
    if args.method not in methods:
        raise store.LabError(f"no method file for {args.method} in seer_engine/lab/methods/")
    method, path = methods[args.method]
    runner.preflight(conn, method, path)
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
    log.info("research store %s loaded (%.1fs)", data.fingerprint[:12], time.perf_counter() - t0)
    # Decision D10 (lab/hardgate.py): the dev store is pinned to the prices the lab's benchmark
    # was measured on. A store whose price fingerprint differs is refused here, before any
    # backtest, so a rebuilt store cannot slip into the record unannounced -- every trial it
    # produced would be one the hard gate refuses as incomparable. No flag skips this.
    hardgate.pin_dev_store(conn, data.price_fingerprint)
    # The second checkpoint: runner.preflight ran before the store existed and could not see the
    # panel. Nothing here is reached for a price-only method.
    floor = float(getattr(args, "allow_coverage", coverage.MIN_DEV_COVERAGE))
    cov = runner.preflight_data(data, method, min_coverage=floor)
    if cov is not None:
        print(coverage.format_report(cov, floor=floor))
        if floor < coverage.MIN_DEV_COVERAGE:
            print(
                f"--allow-coverage {floor:.2f}: {method.id} runs against a panel that can rank on "
                f"{cov.fraction:.1%} of the dev window, below the "
                f"{coverage.MIN_DEV_COVERAGE:.0%} floor. These trials measure the panel, not the "
                "hypothesis, and the method id is spent either way."
            )
    ran = runner.run_method(conn, method, path, data, git_sha=runner.git_head(config.REPO_ROOT))
    status = store.get_method(conn, method.id)["status"]
    log.info("%s: %d trial(s) recorded, status %s (%.1fs)", method.id, len(ran), status, time.perf_counter() - t0)
    _show(conn, argparse.Namespace(method=method.id))
    print(f"\nLab N (dev trials) is now {store.dev_trial_count(conn)}; test-window looks used: {store.test_looks(conn)}")
    return 0
```
**Impact:**
- With the real dev store, `data.price_fingerprint == 5451195…`, which is benchmark #1's backfilled value, so a real `lab run` is unchanged.
- `data.price_fingerprint` is `str | None` (Phase 2's field); `pin_dev_store` refuses None. `research.load_store` always sets it, so only a hand-built `ResearchData` can be refused that way, and no existing test drives `_run`.
- `lab test`, `lab remeasure` and `lab costs` are deliberately not pinned. The test store has other prices by design, and the re-runs already verify against recorded metrics.

### Step 9: One warning helper shared by the two reports
**File:** `engine/src/seer_engine/commands/lab.py:1815`, inserted immediately before `def _regime` (line 1817 after Phase 2's `_costs` edit)
**Change:** add the helper.
**Code:**
```python
def _comparability_warnings(conn, bench_n: int, rows, wanted: set[str]) -> list[str]:
    """One line per method whose recorded curves cannot be compared with the benchmark's (D10).

    ``lab regime`` and ``lab walkforward`` are reports: they decide nothing, so on the condition
    the hard gate refuses they **warn** and keep printing. A report that refused would hide the
    very record its reader came to look at. The test is the gate's own
    (``hardgate.mismatches``), against the benchmark row the report itself is using, over the
    rows the report itself will print -- so a warning and a refusal can never disagree about
    which method is incomparable.

    ``rows`` need ``n``, ``method_id`` and ``candidate_id``; the benchmark's own row is skipped,
    and so is every method outside ``wanted`` when ``wanted`` is non-empty.
    """
    from seer_engine.backtest import regime
    from seer_engine.lab import hardgate

    by_method: dict[str, list] = {}
    for r in rows:
        if r["candidate_id"] == regime.BENCH_CANDIDATE:
            continue
        if wanted and r["method_id"] not in wanted:
            continue
        by_method.setdefault(str(r["method_id"]), []).append(r)
    out: list[str] = []
    for mid, trials in sorted(by_method.items()):
        problems = hardgate.mismatches(conn, bench_n, trials)
        if problems:
            out.append(
                f"WARNING {mid} is not comparable with {regime.BENCH_CANDIDATE}: "
                f"{hardgate.describe(problems)}. Its row below is cross-store arithmetic, and "
                f"`lab promote` refuses it (lab/hardgate.py, D10)"
            )
    return out


```
**Impact:** none until Steps 10 and 11 call it.

### Step 10: `lab regime` warns
**File:** `engine/src/seer_engine/commands/lab.py:1817-1902` (`e5eda52` :1812-1897, +5 after Phase 2)
**Change:** replace `_regime`. The warnings print after the intro paragraph and before the table header, then the table prints exactly as before. The exit code is unchanged.
**Code:**
```python
def _regime(conn, args) -> int:
    """``lab regime``: every recorded dev result, split by whether the market was narrow or broad.

    A report, in the sense ``lab costs`` is a report: it re-runs nothing, inserts no trial, moves
    no status and spends no look. Recorded curves (``trials.curve_json``) are monthly, so the
    split is arithmetic on rows the lab already has; the research store is opened only to measure
    breadth, which needs member bars.

    A method whose curves were measured on prices other than the benchmark's -- or on prices
    nobody recorded -- gets one ``WARNING`` line above the table and its row anyway (D10 in
    ``lab/hardgate.py``): a report warns, the gate refuses.
    """
    import json

    from seer_engine.backtest import regime
    from seer_engine.lab import hardgate

    rows = [
        r for r in conn.execute(
            "SELECT n, method_id, candidate_id, start, end, curve_json FROM trials "
            "WHERE window = 'dev' AND curve_json IS NOT NULL ORDER BY method_id, n"
        )
    ]
    bench = next((r for r in rows if r["candidate_id"] == regime.BENCH_CANDIDATE), None)
    if bench is None:
        raise store.LabError(
            f"no {regime.BENCH_CANDIDATE} dev trial to compare against; the breadth panel needs "
            f"the recorded SPY buy-and-hold curve as its benchmark"
        )
    wanted = {m.upper() for m in args.method}
    if wanted:
        known = {r["method_id"] for r in rows}
        missing = sorted(wanted - known)
        if missing:
            raise store.LabError(f"no dev trial for {', '.join(missing)}")

    t0 = time.perf_counter()
    try:
        data = research.load_store(Path(args.store))
    except (ValueError, FileNotFoundError) as e:
        raise store.LabError(f"{args.store}: {e}") from e
    bench_curve = [(date.fromisoformat(d), float(v)) for d, v in json.loads(bench["curve_json"])]
    spread = regime.breadth(data.market, [d for d, _ in bench_curve])
    label = regime.labels(spread)
    counts = {r: sum(1 for x in label.values() if x == r) for r in regime.REGIMES}
    runs = regime.persistence(spread)
    log.info("breadth measured over %d months (%.1fs)", len(label), time.perf_counter() - t0)

    funded = sum(1 for r in rows if store.funding_of(conn, int(r["n"])) is not None)
    if funded:
        print(f"{funded} of these trials were funded with the owner's monthly deposits; their "
              f"curves\nhave the deposits removed before slicing, so a deposit is never read as "
              f"a gain.\n")
    print(f"Market breadth on the dev window, {len(label)} months labelled: "
          f"{counts[regime.NARROW]} narrow, {counts[regime.BROAD]} broad.")
    print("A month is NARROW when the index beat the equal-weighted average of its own members")
    print("-- a few big names carried it -- and BROAD otherwise. Returns are annualised within")
    print("each regime's months alone, so they describe where a result came from, not a return")
    print("anyone could have earned.\n")
    warnings = _comparability_warnings(conn, int(bench["n"]), rows, wanted)
    for line in warnings:
        print(line)
    if warnings:
        print()
    head = f"  {'candidate':<26}{'narrow vs SPY':>15}{'broad vs SPY':>15}   {'verdict':<22}"
    print(head)
    print("  " + "-" * (len(head) - 2))
    for r in rows:
        if r["candidate_id"] == regime.BENCH_CANDIDATE:
            continue
        if wanted and r["method_id"] not in wanted:
            continue
        curve = [(date.fromisoformat(d), float(v)) for d, v in json.loads(r["curve_json"])]
        pan = regime.panel(curve, bench_curve, label, hardgate.trial_deposits(conn, r, curve))
        cells, gaps = [], {}
        for name in regime.REGIMES:
            mine, theirs, gap = pan[name]
            if gap is None or mine.months < args.min_months:
                cells.append(f"{'-':>15}")
            else:
                cells.append(f"{fmt_signed_pct(gap):>15}")
                gaps[name] = gap
        print(f"  {r['candidate_id']:<26}{cells[0]}{cells[1]}   {regime.read(gaps):<22}")
    if runs:
        peak_at, peak = max(runs, key=lambda x: x[1])
        pos = sum(1 for _d, v in runs if v > 0)
        print(f"\nPersistence ({regime.PERSIST_MONTHS}-month trailing mean spread): "
              f"{pos} of {len(runs)} windows positive, peak {fmt_signed_pct(peak)} a month "
              f"ending {peak_at}.")
        print("A sustained positive reading is a standing headwind for an equal-weighted or")
        print("beta-stripped book. THIS is the measure that separates eras; the narrow/broad")
        print("month counts above do not -- on them almost every method reads 'pays in both'.")
    print(f"\n{len(label)} months, store {data.fingerprint[:12]}. Nothing was recorded.")
    return 0
```
**Impact:** on the committed lab no method is incomparable, so stdout is byte-identical.

### Step 11: `lab walkforward` warns
**File:** `engine/src/seer_engine/commands/lab.py:1908-2011` (`e5eda52` :1903-2006, +5 after Phase 2)
**Change:** replace `_walkforward`. The warnings print after the three intro lines and before the table header. The buy-signal logic is untouched: `walkforward.buy_signal` is the owner's, and the gate already refuses an incomparable method at `lab promote`.
**Code:**
```python
def _walkforward(conn, args) -> int:
    """``lab walkforward``: the lab's selection rule, scored out of sample many times.

    Report only, and unlike ``lab regime`` it needs no research store at all: recorded trials carry
    monthly curves, so every fold is a date slice of rows already in the database. Nothing is
    written, no status moves, no look is spent.

    A method whose curves were measured on prices other than the benchmark's -- or on prices
    nobody recorded -- gets one ``WARNING`` line above the table and its row anyway (D10 in
    ``lab/hardgate.py``): a report warns, the gate refuses.
    """
    import json

    from seer_engine.backtest import regime
    from seer_engine.lab import hardgate
    from seer_engine.lab import walkforward as wf

    rows = list(conn.execute(
        "SELECT n, method_id, candidate_id, start, end, curve_json FROM trials "
        "WHERE window = 'dev' AND curve_json IS NOT NULL ORDER BY method_id, n"
    ))
    bench_row = next((r for r in rows if r["candidate_id"] == regime.BENCH_CANDIDATE), None)
    if bench_row is None:
        raise store.LabError(
            f"no {regime.BENCH_CANDIDATE} dev trial; walk-forward needs the recorded SPY "
            f"buy-and-hold curve as its benchmark"
        )

    def curve_of(row):
        return [(date.fromisoformat(d), float(v)) for d, v in json.loads(row["curve_json"])]

    bench = curve_of(bench_row)
    kw = {}
    if args.min_train_years is not None:
        kw["min_train_years"] = args.min_train_years
    if args.eval_years is not None:
        kw["eval_years"] = args.eval_years
    the_folds = wf.folds([d for d, _v in bench], **kw)
    if not the_folds:
        raise store.LabError("the recorded benchmark curve is too short to split into folds")

    wanted = {m.upper() for m in args.method}
    by_method: dict[str, list] = {}
    for r in rows:
        if r["candidate_id"] == regime.BENCH_CANDIDATE:
            continue
        if wanted and r["method_id"] not in wanted:
            continue
        by_method.setdefault(r["method_id"], []).append(r)
    if wanted and not by_method:
        raise store.LabError(f"no dev trial for {', '.join(sorted(wanted))}")

    print(f"Walk-forward over {len(the_folds)} folds, {the_folds[0].eval_start} to "
          f"{the_folds[-1].eval_end}. Each fold picks the variant the lab's own rule would have")
    print("named knowing nothing past the train end, then scores it on months it has never seen.")
    print("Folds share training data, so they are a sanity check and never a significance test.\n")
    warnings = _comparability_warnings(conn, int(bench_row["n"]), rows, wanted)
    for line in warnings:
        print(line)
    if warnings:
        print()
    head = f"  {'method':<8}{'folds won':>11}{'stable':>9}{'2009-15 edge':>15}   verdict"
    print(head)
    print("  " + "-" * (len(head) + 16))

    fired: list[str] = []
    majorities = 0
    for mid, trials in sorted(by_method.items()):
        curves = {r["candidate_id"]: curve_of(r) for r in trials}
        deps = {
            r["candidate_id"]: hardgate.trial_deposits(conn, r, curves[r["candidate_id"]])
            for r in trials
        }
        rec = wf.Record(mid, wf.evaluate(curves, bench, the_folds, deps))
        best = max(
            (c for c in curves),
            key=lambda c: (wf.measure(curves[c], HIGH_COVERAGE[0], HIGH_COVERAGE[1], deps[c])
                           or wf.Slice(0, None, None, None, None)).mar or -1e9,
        )
        mine = wf.measure(curves[best], *HIGH_COVERAGE, deps[best])
        theirs = wf.measure(bench, *HIGH_COVERAGE)
        edge = (
            None if mine is None or theirs is None or mine.cagr is None or theirs.cagr is None
            else mine.cagr - theirs.cagr
        )
        row = store.get_method(conn, mid)
        eligible = row is not None and row["status"] == "dev-eligible"
        # The SAME kin rule the promote gate uses (hardgate.failed_kin: family union transitive
        # ancestors), not a second family-only query beside it. Decision D9 is what happens when
        # these two disagree: the signal said M0030's family was clean while the gate refused it
        # on ancestry, which is a worse answer than either one alone.
        kin = hardgate.failed_kin(conn, mid) if row is not None else ()
        signal, why = wf.buy_signal(eligible, rec, edge, ", ".join(kin) if kin else None)
        if signal:
            fired.append(f"{mid}: {why}")
        if rec.majority:
            majorities += 1
        print(f"  {mid:<8}{rec.won:>6} of {len(rec.scored):<3}"
              f"{('yes' if rec.stable else 'no'):>9}"
              f"{(fmt_signed_pct(edge) if edge is not None else '-'):>15}   {why}")

    print(f"\n{majorities} of {len(by_method)} methods beat the benchmark in a majority of folds.")
    if fired:
        print("\n  *** BUY SIGNAL ***")
        for line in fired:
            print(f"  {line}")
        print("  This is the moment survivorship-free price history is worth buying: the free")
        print("  evidence is used up, and the next two things that happen are a counted look and")
        print("  real money. See the explore skill's Promotion step 0b.")
    else:
        print("No buy signal. Survivorship-free price history is not worth buying yet.")
    print("\nNothing was recorded. No research store was opened.")
    return 0
```
**Impact:** on the committed lab, stdout is byte-identical (no warnings).

### Step 12: (no change) the fixture helper comes from Phase 2
**File:** none. `engine/tests/labkit.py` is **not** edited by this phase.
**Change:** reconciled into Phase 2 (Step 11 there), so the plan set has exactly one fixture
stamping site. Phase 2 creates `labkit.LAB_PRICE_FINGERPRINT` (`= store.P7A_PRICE_FINGERPRINT`,
`5451195fd552…`) and `labkit.stamp_provenance(conn, trial_ns, *, price_fingerprint=LAB_PRICE_FINGERPRINT,
initial_idr=Decimal("10000000"))`, with the caller holding the transaction. It is **idempotent**:
a trial that already has a provenance row is skipped, so the explicit stamps Phase 2 added to the
two funded tests in `test_lab_hardgate.py` become harmless no-ops once Step 13's `_method` stamps
first, and `trial_provenance`'s one-row-per-trial refusal is never hit by a fixture. The capital is a
`Decimal`, because `store.insert_provenance` refuses anything else.
**Impact:** none.

### Step 13: `test_lab_hardgate.py`: fixtures stamp, and the benchmark lives in another store
**File:** `engine/tests/test_lab_hardgate.py:15-20` (imports, as Phase 2 leaves them) and `:81-112` (`_benchmark`, `_method`; `e5eda52` :79-110, +2 after Phase 2's two import lines)
**Change:**
- extend Phase 2's `from labkit import stamp_provenance` to also import `LAB_PRICE_FINGERPRINT`, and define two fingerprints.
- `_benchmark` takes the P7a store fingerprint `"5451195f"`, as the real row does, while methods keep `"399d0d25"`. Every existing positive test therefore also shows that a different `store_fingerprint` on the same prices is comparable.
- both helpers stamp, with switches to stamp other prices, NULL prices, or nothing.

**Code:** imports. After Phase 2 lines 15-20 read `import pytest`, a blank line,
`from labkit import stamp_provenance`, then the three `seer_engine` imports (and `from decimal
import Decimal` sits above, among the stdlib imports, untouched here). They become:
```python
import pytest

from labkit import LAB_PRICE_FINGERPRINT, stamp_provenance
from seer_engine.backtest import regime
from seer_engine.lab import hardgate, store
from seer_engine.lab import walkforward as wf

SAME_PRICES = LAB_PRICE_FINGERPRINT
OTHER_PRICES = "e" * 64
```
Replace `_benchmark` and `_method` (lines 81-112 after Phase 2; neither function is edited by Phase 2):
```python
def _benchmark(conn, *, prices: str | None = SAME_PRICES, stamped: bool = True) -> None:
    """The lab's REF-SPY-HOLD dev trial, recorded -- like the real trial #1 -- under the P7a store
    fingerprint while every method below carries ``399d0d25``. Same prices, different store: the
    committed lab's own shape, and the case D10 says must stay comparable."""
    with conn:
        store.add_method(conn, id="H-P7A-REF", name="SPY buy and hold", family="reference",
                         source_kind="seed", hypothesis="h", status="registered")
        ns = store.insert_trials(conn, [_trial(
            method_id="H-P7A-REF", candidate_id=regime.BENCH_CANDIDATE,
            config_digest="ref-spy-hold", start="1993-02-01", end="2015-10-16",
            store_fingerprint="5451195f", curve_json=_curve(_months(*BENCH_SPAN), 0.08),
        )])
        if stamped:
            stamp_provenance(conn, ns, price_fingerprint=prices)


def _method(conn, mid="M0001", *, family="trend", parent=None, status="dev-eligible",
            annual=0.15, span=DEV_SPAN, curves=True, prices: str | None = SAME_PRICES,
            stamped: bool = True) -> None:
    """One method with one dev trial, walked to ``status`` through the real transitions.

    The trial is stamped with provenance on ``prices`` unless ``stamped`` is False -- the gate
    refuses an unstamped trial (D10), which is a test of its own below, not a default.
    """
    with conn:
        store.add_method(conn, id=mid, name=f"n{mid}", family=family, parent_id=parent,
                         source_kind="variation" if parent else "knowledge", hypothesis="h",
                         status="registered")
        ns = store.insert_trials(conn, [_trial(
            method_id=mid, candidate_id=f"{mid}-A", config_digest=f"d-{mid}",
            curve_json=_curve(_months(*span), annual) if curves else "[]",
        )])
        if stamped:
            stamp_provenance(conn, ns, price_fingerprint=prices)
        for step in {
            "registered": (),
            "dev-eligible": ("dev-eligible",),
            "promoted": ("dev-eligible", "promoted"),
            "test-failed": ("dev-eligible", "promoted", "test-failed"),
            "rejected": ("rejected",),
        }[status]:
            store.update_method(conn, mid, status=step)
```
**Impact:**
- Every existing test in the file keeps its assertions.
- The funded-trial test (`test_a_funded_trial_is_de_funded_before_it_is_scored`) relies on the 10M default for its `0.5` unit under Phase 2's `recorded_capital`. `_method` now stamps that trial first; the `with conn: stamp_provenance(conn, [int(row["n"])])` Phase 2 added after its `insert_funding` block is then a no-op (idempotent helper) and is left in place.
- Phase 2's `_funded_trial` builds its trial without `_method` and stamps (or deliberately does not stamp) it itself; nothing here changes it.

### Step 14: `test_lab_hardgate.py`: the D10 tests
**File:** `engine/tests/test_lab_hardgate.py` (append at the end of the file, after `test_there_is_no_override`; `e5eda52` :444, longer after Phase 2)
**Change:** new section.
**Code:**
```python


# ------------------------------------------------------------------ comparability (D10)


def test_the_module_records_the_comparability_decision():
    doc = hardgate.__doc__ or ""
    assert "(D10)" in doc
    assert "price fingerprint" in doc
    assert "store_fingerprint" in doc


def test_a_different_store_fingerprint_on_the_same_prices_is_comparable(conn):
    """M1/M5: the store fingerprint moves with fundamentals.csv; the prices do not. Refusing on
    the store fingerprint would strand all seven dev-eligible methods in the real lab."""
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    stores = {r[0] for r in conn.execute("SELECT store_fingerprint FROM trials")}
    assert len(stores) == 2
    assert hardgate.comparability(conn, "M0001") == ()
    hardgate.check(conn, "M0001")  # does not raise


def test_a_trial_on_other_prices_is_refused_and_both_fingerprints_are_named(conn):
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15, prices=OTHER_PRICES)
    problems = hardgate.comparability(conn, "M0001")
    assert len(problems) == 1
    assert "M0001-A" in problems[0]
    assert OTHER_PRICES[:12] in problems[0] and SAME_PRICES[:12] in problems[0]
    with pytest.raises(store.LabError) as e:
        hardgate.fold_record(conn, "M0001")
    assert "M0001-A" in str(e.value) and "D10" in str(e.value)
    with pytest.raises(store.LabError):
        hardgate.check(conn, "M0001")
    with pytest.raises(store.LabError):
        hardgate.fold_summary(conn, "M0001")
    assert hardgate.summary(conn, "M0001").startswith("not scoreable (")


def test_a_trial_whose_prices_are_unknown_is_refused(conn):
    """Fail closed: nobody recording the prices is not evidence that they match."""
    _benchmark(conn)
    _method(conn, "M0001", family="a", annual=0.15, prices=None)
    _method(conn, "M0002", family="b", annual=0.15, stamped=False)
    assert "records no price fingerprint" in hardgate.comparability(conn, "M0001")[0]
    assert "has no provenance row" in hardgate.comparability(conn, "M0002")[0]
    for mid in ("M0001", "M0002"):
        with pytest.raises(store.LabError):
            hardgate.check(conn, mid)


def test_a_benchmark_whose_prices_are_unknown_refuses_every_method(conn):
    _benchmark(conn, stamped=False)
    _method(conn, "M0001", annual=0.15)
    problems = hardgate.comparability(conn, "M0001")
    assert len(problems) == 1 and regime.BENCH_CANDIDATE in problems[0]
    with pytest.raises(store.LabError) as e:
        hardgate.check(conn, "M0001")
    assert regime.BENCH_CANDIDATE in str(e.value)


def test_one_variant_on_other_prices_refuses_the_whole_method(conn):
    """Every variant is a candidate in every fold's pick, so one on other prices taints them all."""
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    with conn:
        ns = store.insert_trials(conn, [_trial(
            method_id="M0001", candidate_id="M0001-B", config_digest="d-M0001-B",
            curve_json=_curve(_months(*DEV_SPAN), 0.10),
        )])
        stamp_provenance(conn, ns, price_fingerprint=OTHER_PRICES)
    problems = hardgate.comparability(conn, "M0001")
    assert [p.split(" ")[0] for p in problems] == ["M0001-B"]
    with pytest.raises(store.LabError):
        hardgate.check(conn, "M0001")


def test_describe_names_three_and_counts_the_rest():
    assert hardgate.describe(()) == ""
    assert hardgate.describe(("a", "b")) == "a; b"
    assert hardgate.describe(("a", "b", "c", "d", "e")) == "a; b; c; and 2 more"


def test_lab_promote_exits_2_and_writes_nothing_on_other_prices(tmp_path):
    db, prereg_dir = tmp_path / "lab.sqlite", tmp_path / "prereg"
    c = store.connect(db)
    _benchmark(c)
    _method(c, "M0001", annual=0.15, prices=OTHER_PRICES)  # wins 4 of 4, kin clean
    before = db.read_bytes()
    c.close()

    assert _cli(tmp_path, db, prereg_dir) == 2
    assert not prereg_dir.exists()
    assert db.read_bytes() == before


# ------------------------------------------------------------------ the store pin (D10)


def test_the_dev_store_pin_takes_the_benchmarks_prices(conn):
    _benchmark(conn)
    hardgate.pin_dev_store(conn, SAME_PRICES)  # does not raise


def test_the_dev_store_pin_refuses_other_prices_and_names_both(conn):
    _benchmark(conn)
    with pytest.raises(store.LabError) as e:
        hardgate.pin_dev_store(conn, OTHER_PRICES)
    msg = str(e.value)
    assert OTHER_PRICES[:12] in msg and SAME_PRICES[:12] in msg
    assert "Nothing ran" in msg


def test_the_dev_store_pin_refuses_when_the_benchmarks_prices_are_unknown(conn):
    _benchmark(conn, stamped=False)
    with pytest.raises(store.LabError) as e:
        hardgate.pin_dev_store(conn, SAME_PRICES)
    assert regime.BENCH_CANDIDATE in str(e.value)


def test_the_dev_store_pin_refuses_a_store_whose_prices_are_unknown(conn):
    """Fail closed (D10): ``ResearchData.price_fingerprint`` is None only on a hand-built store,
    and a trial recorded on it would carry NULL prices the gate refuses forever -- so it is
    refused with or without a benchmark."""
    with pytest.raises(store.LabError, match="carries no price fingerprint"):
        hardgate.pin_dev_store(conn, None)  # no benchmark yet
    _benchmark(conn)
    with pytest.raises(store.LabError, match="carries no price fingerprint"):
        hardgate.pin_dev_store(conn, None)


def test_the_dev_store_pin_is_silent_on_a_lab_with_no_benchmark(conn):
    """A fresh lab must be able to run before it has a yardstick; the gate refuses it anyway."""
    _method(conn, "M0001")
    assert hardgate.benchmark_n(conn) is None
    hardgate.pin_dev_store(conn, OTHER_PRICES)  # does not raise


def _run_args(db, tmp_path):
    return argparse.Namespace(
        db=db, lab_command="run", method="M0099", store=tmp_path / "store", allow_coverage=0.8,
    )


def _stub_run(monkeypatch, tmp_path, prices: str):
    """`lab run` up to the store load, with no method file, no store on disk and no backtest."""
    import types

    from seer_engine import research
    from seer_engine.lab import method as method_mod
    from seer_engine.lab import runner

    stub = types.SimpleNamespace(id="M0099")
    monkeypatch.setattr(method_mod, "discover", lambda: {"M0099": (stub, tmp_path / "m.py")})
    monkeypatch.setattr(runner, "preflight", lambda *a, **k: None)
    monkeypatch.setattr(
        research, "load_store",
        lambda _path: types.SimpleNamespace(fingerprint="f" * 64, price_fingerprint=prices),
    )


class _Reached(Exception):
    """Raised by a stubbed step to prove `_run` got that far."""


def test_lab_run_refuses_a_store_with_other_prices_before_any_backtest(tmp_path, monkeypatch):
    from seer_engine.commands import lab as lab_cmd
    from seer_engine.lab import runner

    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _benchmark(c)
    trials_before = c.execute("SELECT COUNT(*) FROM trials").fetchone()[0]
    c.close()

    _stub_run(monkeypatch, tmp_path, OTHER_PRICES)

    def no_backtest(*_a, **_k):
        raise AssertionError("the store pin must refuse before any backtest")

    monkeypatch.setattr(runner, "preflight_data", no_backtest)
    monkeypatch.setattr(runner, "run_method", no_backtest)

    assert lab_cmd.run(_run_args(db, tmp_path)) == 2
    c = store.connect(db)
    assert c.execute("SELECT COUNT(*) FROM trials").fetchone()[0] == trials_before
    c.close()


def test_lab_run_takes_a_store_with_the_benchmarks_prices(tmp_path, monkeypatch):
    from seer_engine.commands import lab as lab_cmd
    from seer_engine.lab import runner

    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _benchmark(c)
    c.close()

    _stub_run(monkeypatch, tmp_path, SAME_PRICES)

    def reached(*_a, **_k):
        raise _Reached()

    monkeypatch.setattr(runner, "preflight_data", reached)
    with pytest.raises(_Reached):
        lab_cmd.run(_run_args(db, tmp_path))


# ------------------------------------------------------------------ the reports warn (D10)


def test_report_warnings_name_each_incomparable_method_once(conn):
    from seer_engine.commands import lab as lab_cmd

    _benchmark(conn)
    _method(conn, "M0001", family="a", annual=0.15)
    _method(conn, "M0002", family="b", annual=0.15, prices=OTHER_PRICES)
    _method(conn, "M0003", family="c", annual=0.15, stamped=False)
    rows = list(conn.execute(
        "SELECT n, method_id, candidate_id FROM trials WHERE window = 'dev' "
        "ORDER BY method_id, n"
    ))
    bench_n = hardgate.benchmark_n(conn)
    lines = lab_cmd._comparability_warnings(conn, bench_n, rows, set())
    assert [line.split()[1] for line in lines] == ["M0002", "M0003"]
    assert all(line.startswith("WARNING ") for line in lines)
    assert lab_cmd._comparability_warnings(conn, bench_n, rows, {"M0001"}) == []


def test_lab_walkforward_warns_on_other_prices_and_still_reports(tmp_path, capsys):
    from seer_engine.commands import lab as lab_cmd

    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _benchmark(c)
    _method(c, "M0001", family="a", annual=0.15)
    _method(c, "M0002", family="b", annual=0.15, prices=OTHER_PRICES)
    c.close()

    rc = lab_cmd.run(argparse.Namespace(
        db=db, lab_command="walkforward", method=[], min_train_years=None, eval_years=None,
    ))
    assert rc == 0  # a report warns; it does not refuse
    lines = capsys.readouterr().out.splitlines()
    warned = [line for line in lines if line.startswith("WARNING")]
    assert len(warned) == 1 and "M0002" in warned[0]
    assert any(line.strip().startswith("M0002") for line in lines)  # its row is still printed
    assert any(line.strip().startswith("M0001") for line in lines)


def test_lab_walkforward_is_silent_when_everything_is_comparable(tmp_path, capsys):
    from seer_engine.commands import lab as lab_cmd

    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _benchmark(c)
    _method(c, "M0001", annual=0.15)
    c.close()

    assert lab_cmd.run(argparse.Namespace(
        db=db, lab_command="walkforward", method=[], min_train_years=None, eval_years=None,
    )) == 0
    assert "WARNING" not in capsys.readouterr().out
```
**Impact:** new tests only.

### Step 15: `test_lab_prereg.py`: the benchmark and the real method stamp
**File:** `engine/tests/test_lab_prereg.py:15-20` (imports), `:159-177` (`_benchmark`), `:180-206` (`_real_method`)
**Change:** stamp provenance. Without it, `test_lab_promote_command_writes_the_file_and_names_the_next_step` would exit 2 at `hardgate.check`. The other `_eligible` / `_ballast` fixtures carry `curve_json="[]"` and reach the gate only through `prereg.fold_text`, which is lenient and is not asserted on beyond "non-empty, one line", so they are left alone.
**Code:** imports:
```python
import pytest

from labkit import stamp_provenance
from seer_engine import dates
from seer_engine.backtest import dev
from seer_engine.lab import prereg, store
from seer_engine.lab.method import config_digest, discover, source_sha
```
`_benchmark`:
```python
def _benchmark(conn) -> None:
    """The lab's recorded SPY buy-and-hold dev trial (``regime.BENCH_CANDIDATE``).

    Since the hard gate (`lab/hardgate.py`) a lab with no ``REF-SPY-HOLD`` dev trial can promote
    nothing: there is no benchmark to cut folds from, so no fold can be scored, and the gate
    fails closed rather than waving a method through. A fixture that wants a *promotable* method
    therefore has to look like a lab that could have one -- the same reason `_ballast` exists one
    gate earlier. Its span matches the real row's, 1993-02-01..2015-10-16, which is what yields
    the four folds the gate requires.

    Its own family and its own method id, so it is never kin to the method under test. Stamped
    with provenance on the lab's prices, because the gate refuses a benchmark whose prices are
    unknown (D10).
    """
    store.add_method(conn, id="H-P7A-REF", name="SPY buy and hold", family="reference",
                     source_kind="seed", hypothesis="h", status="registered")
    ns = store.insert_trials(conn, [_trial(
        method_id="H-P7A-REF", candidate_id="REF-SPY-HOLD", config_digest="ref-spy-hold",
        start="1993-02-01", end="2015-10-16",
        curve_json=_curve(_months(date(1993, 2, 1), date(2015, 10, 16)), 0.08),
    )])
    stamp_provenance(conn, ns)
```
`_real_method`:
```python
def _real_method(conn, mid: str = "M0001"):
    """What `lab run` would have left behind for the committed `mNNNN_*.py` file `mid`.

    The real file is used so `check_source` has something true to check: the trial's digest is
    the file's own `config_digest` and `source_sha` is the file's sha256.

    Its trial carries a real curve, and the lab carries a benchmark, because `lab promote` now
    runs the hard gate before `prereg.promote_method`: a method with no curve is scoreable on no
    fold and is refused. The curve compounds at 15% a year against the benchmark's 8%, so the
    method wins all four folds -- which is what the brief means by "a method winning a majority
    with a clean family promotes". Both trials are stamped with provenance on the benchmark's
    prices, as `lab run` stamps a real one, because the gate refuses an unstamped trial (D10).
    """
    method, path = discover()[mid]
    c = method.candidates[0]
    with conn:
        _benchmark(conn)
        store.add_method(conn, id=mid, name=method.name, family=method.family,
                         source_kind=method.source_kind, source_ref=method.source_ref,
                         hypothesis="h", status="registered")
        ns = store.insert_trials(conn, [
            _trial(method_id=mid, candidate_id=c.id, config_digest=config_digest(c),
                   rules_id=c.rules.id, allocator_id=str(c.allocator.id),
                   curve_json=_curve(_months(date(1996, 1, 2), date(2015, 10, 16)), 0.15)),
            _ballast(mid),
        ])
        stamp_provenance(conn, ns)
        store.update_method(conn, mid, source_sha=source_sha(path), status="dev-eligible")
    return c, path
```
**Impact:** fixtures only. Before editing, check the exact import lines at `test_lab_prereg.py:15-20`: `labkit` slots in alphabetically before `seer_engine`, and `from pathlib import Path` / `import subprocess` stay as they are above.

### Step 16: `test_lab_status.py`: `_method_at` stamps
**File:** `engine/tests/test_lab_status.py:19-22` (imports), `:350-370` (`_method_at`)
**Change:** stamp every trial `_method_at` inserts. It is the only helper that builds a benchmark lab (`_lab_with_a_benchmark`). Without stamps, `test_a_method_that_clears_the_hard_gate_is_listed_with_its_fold_record` would lose its promotable listing, and the "of 4 folds" assertions would read "not scoreable".
**Code:** imports:
```python
import pytest

from labkit import stamp_provenance
from seer_engine.commands import lab as lab_cmd
from seer_engine.lab import store
```
`_method_at`:
```python
def _method_at(c, mid: str, *, status: str, family: str = "fam", trials=()) -> None:
    """Like ``_method``, but reaching the statuses the hard gate cares about.

    ``_method`` above stops at ``dev-eligible``; the gate's (K) condition needs a kin that reads
    ``test-failed``, which is three transitions further along. A separate helper rather than an
    edit to ``_method``, because every test above depends on that one exactly as it is.

    Every trial is stamped with provenance on the lab's prices, because the gate refuses a trial
    whose prices are unknown (D10) and these fixtures are about the folds and the kin, not that.
    """
    path = {
        "registered": ("registered",),
        "rejected": ("registered", "rejected"),
        "dev-eligible": ("registered", "dev-eligible"),
        "promoted": ("registered", "dev-eligible", "promoted"),
        "test-failed": ("registered", "dev-eligible", "promoted", "test-failed"),
    }[status]
    with c:
        store.add_method(c, id=mid, name=f"name {mid}", family=family,
                         source_kind="knowledge", hypothesis="h")
        if trials:
            stamp_provenance(c, store.insert_trials(c, list(trials)))
        for s in path:
            store.update_method(c, mid, status=s)
```
**Impact:** fixtures only.

## Verification

All commands run from the worktree, with the main checkout's venv (the worktree has none) and the research store at `/home/miftah/seer/engine/.research`. Work only on scratch copies of `lab/lab.sqlite`. Never pass the committed path to a command that opens it with `store.connect`, because that migrates it.

**Build:**
```
cd /home/miftah/.worktrees/seer/trial-reproducibility/engine && \
PYTHONPATH=$PWD/src /home/miftah/seer/engine/.venv/bin/python -c \
  "import seer_engine.commands.lab, seer_engine.lab.hardgate as h; print(h.Geometry.__slots__)"
```

**Tests:**
```
cd /home/miftah/.worktrees/seer/trial-reproducibility/engine && \
PYTHONPATH=$PWD/src /home/miftah/seer/engine/.venv/bin/python -m pytest -q \
  tests/test_lab_hardgate.py tests/test_lab_prereg.py tests/test_lab_status.py && \
PYTHONPATH=$PWD/src /home/miftah/seer/engine/.venv/bin/python -m pytest -q
```

**Manual check:** run everything on scratch copies. Set `S=<scratchpad>/phase3`.

1. **Baseline at the base commit:**
   ```
   mkdir -p $S/base && git -C /home/miftah/.worktrees/seer/trial-reproducibility archive e5eda52 engine/src | tar -x -C $S/base
   cp /home/miftah/.worktrees/seer/trial-reproducibility/lab/lab.sqlite $S/before.sqlite
   cp /home/miftah/.worktrees/seer/trial-reproducibility/lab/lab.sqlite $S/after.sqlite
   PYTHONPATH=$S/base/engine/src /home/miftah/seer/engine/.venv/bin/python -m seer_engine lab --db $S/before.sqlite status      > $S/status.before
   PYTHONPATH=$S/base/engine/src /home/miftah/seer/engine/.venv/bin/python -m seer_engine lab --db $S/before.sqlite walkforward > $S/wf.before
   ```
2. **After this phase** (the copy migrates to v5 with Phase 2's backfill on open):
   ```
   cd /home/miftah/.worktrees/seer/trial-reproducibility/engine
   PYTHONPATH=$PWD/src /home/miftah/seer/engine/.venv/bin/python -m seer_engine lab --db $S/after.sqlite status      > $S/status.after
   PYTHONPATH=$PWD/src /home/miftah/seer/engine/.venv/bin/python -m seer_engine lab --db $S/after.sqlite walkforward > $S/wf.after
   diff $S/status.before $S/status.after && diff $S/wf.before $S/wf.after && echo IDENTICAL
   grep -c WARNING $S/wf.after   # 0
   ```
   `lab regime` is checked the same way with `--store /home/miftah/seer/engine/.research`. Expect an identical diff and 0 `WARNING` lines.
3. **Comparability on the real lab is empty for every dev-eligible method:**
   ```
   PYTHONPATH=$PWD/src /home/miftah/seer/engine/.venv/bin/python -c "
   from seer_engine.lab import store, hardgate
   c = store.connect('$S/after.sqlite'); g = hardgate.geometry(c)
   print(g.bench_n, [ (m, hardgate.comparability(c, m, g)) for (m,) in c.execute(\"SELECT id FROM methods WHERE status='dev-eligible' ORDER BY id\") ])"
   ```
   Expect `1` and seven `()`.
4. **The pin, against the real store:**
   ```
   PYTHONPATH=$PWD/src /home/miftah/seer/engine/.venv/bin/python -c "
   from pathlib import Path
   from seer_engine import research
   from seer_engine.lab import store, hardgate
   c = store.connect('$S/after.sqlite')
   d = research.load_store(Path('/home/miftah/seer/engine/.research'))
   print(d.price_fingerprint[:12]); hardgate.pin_dev_store(c, d.price_fingerprint); print('pinned ok')
   try: hardgate.pin_dev_store(c, 'e'*64)
   except store.LabError as e: print('refused:', str(e)[:80])"
   ```
   Expect `5451195fd552`, `pinned ok`, then `refused: this research store's prices …`. The CLI path through `_run`, where refusal happens before `preflight_data` / `run_method`, is proven by `test_lab_run_refuses_a_store_with_other_prices_before_any_backtest`. Running `lab run` for real would need a committed, unrun method and would spend its id, so this check does not do it.

**Exit criteria:**
- The full engine suite passes.
- On a scratch copy of the committed DB migrated to v5, `lab status` output is **byte-identical** to the base commit's output on an unmigrated copy. It still reads `Promotable now: (none)`, and each of the seven dev-eligible methods (M0007, M0011, M0019, M0020, M0024, M0030, M0033) has an unchanged refusal reason, so 0 are stranded.
- `lab walkforward` output is byte-identical, with no `WARNING`.
- `hardgate.comparability` is `()` for all seven.
- A fixture method whose trial records other prices is refused by `lab promote` (exit 2, nothing written) and warned, not refused, by `lab walkforward` (exit 0, one `WARNING` line, row still printed).
- `lab run` against a store whose price fingerprint differs from benchmark #1's exits 2 before any backtest; `pin_dev_store` refuses a store whose price fingerprint is None (unknown), with or without a benchmark.

## Assumptions

- Phase 2's names, as reconciled against Phase 2's plan: `store.provenance_of` returns `sqlite3.Row | None` with a `price_fingerprint` key; `store.ProvenanceRow(trial_n, initial_idr: Decimal, price_fingerprint, source, measured)`; `store.insert_provenance(conn, rows)` with the caller holding the transaction and refusing a duplicate `trial_n` and a non-`Decimal` capital; `ResearchData.price_fingerprint` is a dataclass field `str | None = None` (Step 5's `pin_dev_store` refuses None); `labkit.stamp_provenance` / `labkit.LAB_PRICE_FINGERPRINT` exist and the helper is idempotent.
- Phase 2's migration gives trial #1 (`REF-SPY-HOLD`) a non-NULL `price_fingerprint` of `5451195fd552…`, and gives every other dev trial the same value. That is the "strands 0" condition, and the exit criteria test it rather than assume it.
- Phase 2's `hardgate.trial_deposits` change, using `recorded_capital`, keeps its signature, and Phase 2 places it in the same function body this plan leaves alone. The line numbers quoted for `hardgate.py`, `commands/lab.py` and `test_lab_hardgate.py` are post-Phase-2 (see the note under Files). Anchor on function names.
- `store.connect` on a scratch copy migrates it to v5. `lab status` / `walkforward` / `regime` all open with `store.connect`.

## Handoffs

- **Phase 2 (resolved by the reconciler):** one stamping site — `labkit.stamp_provenance`, created by Phase 2, idempotent, capital `Decimal("10000000")` by default. Phase 2 adds no local `_capital` helper; its funded tests and `_funded_trial` call the labkit helper.
- **Phase 4 (docs) — owned there after reconciliation:**
  - `docs/runbooks/data-pipeline.md` and `engine/package_readme.md` state that `lab run` refuses a store whose price fingerprint is not the benchmark's (`hardgate.pin_dev_store`), and that `lab walkforward` / `lab regime` print `WARNING` lines (`commands/lab.py:_comparability_warnings` over `hardgate.mismatches`).
  - `.claude/skills/sync-research-store/SKILL.md`, `explore-and-experiment-new-method/SKILL.md` and `redo-sera-experiments/SKILL.md` say a missing store is pulled, not rebuilt, because `lab run` refuses a store on other prices (Phase 4 Step 6d).
  - The lab insight should quote the (D10) table: 90 of 148 dev trials and all seven dev-eligible methods would be stranded by the store-fingerprint rule, 0 by the price-fingerprint rule.
- **Not owned by any phase (out of scope, noted):** `lab remeasure`, `lab costs` and `lab names` are not pinned. They re-run on whatever store they are given and already verify against recorded metrics (`METRIC_TOL`), so a different store shows up as non-reproduction, not as a silent comparison. `lab test` is not pinned because the test store's prices differ by design.

## Risks

- **Duplicate provenance in fixtures:** resolved — `labkit.stamp_provenance` skips a trial that already has a row. If a `LabError: already has recorded provenance` appears anyway, something stamped with `store.insert_provenance` directly; route it through the helper.
- **`test_there_is_no_override`** scans `hardgate.py` source for `force`, `override`, `skip_gate`, `SEER_SKIP`, `getenv` and `environ`. The new text was written to avoid all of them: no "enforce", no "environment", and "There is no override" is the only use of the word. Re-run that test after any wording edit.
- **Changed `lab status` output from Phase 2:** if Phase 2's migration changes what `lab status` prints, for example a schema line, the byte-identical diff in Exit criteria fails for a reason this phase does not own. In that case compare a Phase-2-only tree against this phase instead of `e5eda52`.

## Rollback

Revert this phase's commit. It touches only `lab/hardgate.py`, `commands/lab.py` and three test files (`test_lab_hardgate.py`, `test_lab_prereg.py`, `test_lab_status.py`), adds no schema and writes no data. Phase 2's provenance table and backfill stay in place and keep working without this phase's readers.

# Phase 2: A test-window look is not luck-gated, and says so

**Plan set:** `GOTRADE_FEE_REBUILD_PLAN.md`
**Analysis:** `20261008-091321-H3M8_code_analyzer.md`
**Satisfies:** R7 (Q7) — settle how a test-window look relates to the luck gate; make the snapshot, the Sera pages and the test agree
**Depends on:** none
**Difficulty:** HARD
**Package:** `engine.lab` + `web/lib/sera`

---

## Goal

The published lab snapshot says, per trial, **whether the luck gate applies to it** — one boolean,
`luckGated`, written by the engine beside the verdict it already publishes. After this phase no
consumer re-derives the dev/test rule; `/sera/methods/M0021` renders the luck check as a dashed
"not applicable" instead of a green tick on a score of 0.51 against a stated bar of 0.90; the DSR
column stops printing `at N 126` beside a number that was never scored at N; and
`web/lib/sera/lab.test.ts` goes from `1 failed | 9 passed` to `10 passed` by **reading the marker**
rather than by excusing the rows that exposed the defect.

## The fork, settled

The handover (§6b / Q7) offers three options. **Option (c) — an explicit marker both the UI and the
test read — is chosen.** The other two were rejected on measured grounds:

- **(a) the assertion excludes `window === 'test'`.** Rejected. It turns the suite green and leaves
  the live page rendering a green tick on `M0021-B70-RAW`'s 0.513013 — `derive.ts`'s own header
  comment calls that "the worst failure this page has: a missed hurdle shown as a green tick". The
  test is the thing that *noticed*; it is not the thing that is wrong.
- **(b) the exporter stops publishing `dsrNow` on test rows.** Rejected on two counts. First, it
  destroys a measurement the owner should see: a test look's DSR is recorded, is meaningful as a
  number, and is simply not a *hurdle*. Second, it makes `dsrNow === null` mean two opposite things
  at once — "no score could be computed, so the hurdle was missed" (the 54 P7a dev rows, measured:
  `dev with dsrNow null = 54`) and "the hurdle does not apply". `derive.ts:211` already keys the
  funnel's honest denominator on `dsrNow !== null`, so (b) would silently fold two test looks into
  that count. **The marker must distinguish "not applicable" from "not measured", and (b) deletes
  exactly that distinction.**

**Why not `Verdict.derived`:** it is already `False` for a dev row whose DSR could not be evaluated.
That is a **miss**, not an exemption. The two cases are opposites and `derived` cannot tell them
apart — which is why a new field is required rather than publishing one that already exists.

**Why the engine is not changed:** `published_verdict` (`store.py:1243`) splits on window and is
**correct** — a pre-registered confirmatory look has no selection among results to deflate, so
`owner_failures` runs and nothing else. `failedNow` correctly omits a DSR failure on a test row.
This phase publishes that rule; it does not touch it.

## Measured inputs (every number here has a command behind it)

```
cd web && npx vitest run lib/sera/lab.test.ts
  FAIL lib/sera/lab.test.ts > publishes a verdict that agrees with the gate published beside it
  AssertionError: expected [ 'M0021-B70-RAW', false ] to deeply equal [ 'M0021-B70-RAW', true ]
  Test Files 1 failed (1) · Tests 1 failed | 9 passed (10)

PYTHONPATH=engine/src python3 -c "import json; s=json.load(open('web/data/lab.json')); ..."
  version 3
  gate: dsrMin 0.9, dsrPolicy 'all-trials', dsrN 126, maxDrawdown 0.2, minProfitFactor 1.3, minTrades 100
  summary: devTrials 126, testLooks 2, methods 45, labMethods 31, historicalMethods 14, insights 53
  total trials 128      dev rows with dsrNow null: 54
  trials[n=123] M0021-B70-RAW       window=test dsr=0.513013 dsrNow=0.513013
                failedNow=['beats SPY TR']                    eligibleNow=False
  trials[n=125] M0029-B70-RAW-FRAC  window=test dsr=0.388958 dsrNow=0.388958
                failedNow=['beats SPY TR','max DD <= 20%']    eligibleNow=False

PYTHONPATH=engine/src python3 -c "from seer_engine.lab import store; ro=store.connect_readonly(store.COMMITTED_DB); \
  print(store.snapshot_json(ro) == open('web/data/lab.json').read())"
  byte-equal today: True      (1,111,529 bytes)
```

The committed snapshot is currently the exact export of the committed database, so the only thing
that will move `web/data/lab.json` in this phase is the new field — which is what makes the
regeneration step reviewable.

## Interface Contract

**Creates:**
- `seer_engine.lab.store.luck_gated(trial) -> bool` (`engine/src/seer_engine/lab/store.py`, new
  function placed immediately after `published_verdict`)
- snapshot key `trials[].luckGated` (boolean, every trial) — `_snapshot_trial`
- `LabTrial.luckGated: boolean` (`web/lib/sera/types.ts`) — **required**, not optional
- `view.dsrNote(trial, gate) -> string | null` (`web/app/sera/methods/view.ts`)

**Signature changes:** none. `luck_gated` is additive; `_snapshot_trial(t, v)` keeps its signature.

**Value changes:**
- `seer_engine.lab.store.SNAPSHOT_VERSION` `3` -> `4` (`store.py:1687`)
- `LabSnapshot.version` type `3` -> `4` (`web/lib/sera/types.ts:8`)

> ### Two different version numbers live in `lab/store.py`. Do not conflate them.
>
> | | what it versions | spelled | moved by | where it is pinned in `test_lab_snapshot.py` |
> |---|---|---|---|---|
> | `SNAPSHOT_VERSION` | the **published JSON** (`web/data/lab.json`'s `version`, `LabSnapshot.version`) | an **int**: `3` -> `4` | **this phase** | `:280`, `assert s["version"] == 3` |
> | `SCHEMA_VERSION` | the **sqlite schema** of `lab/lab.sqlite` (`meta.schema_version`) | a **string**: `"3"` -> `"4"` | **phase 7** (its `trial_funding` side table) | `:86`, `:104`, `:113`, `:180`, `:207`, `:238` — every one of them `store.schema_version(...) == "3"` or `store.SCHEMA_VERSION == "3"` |
>
> **This phase moves only the int, and only at `:280`.** It leaves all six string `"3"` pins at
> `"3"`; phase 7 moves those, and it depends on this phase, so the two edits are sequential and
> never concurrent. Reconciled 2026-10-08.
- `derive.conditionOk(trial, 'dsr')` now returns `null` (not `true`) for a trial with
  `luckGated === false`. Its return type is unchanged: `boolean | null`.
- `view.markLabel`'s `ok === null` branch: `'not measured'` -> `'not applicable'`. After this phase
  `ok === null` arises **only** from an ungated luck check; a gated row with no score still comes
  back `false` (the engine puts the luck label in `failedNow` for exactly those rows), so the two
  states stay distinct without a second field on `Mark`.
- `web/data/lab.json` is regenerated (128 trials each gain `"luckGated":true|false`; 126 true,
  2 false).

**Deletes:** nothing. **Renames:** nothing.

**Requires (from earlier phases):** nothing. This phase has no `depends_on`.

**Leaves alone (owned by others):**
- `store.published_verdict` (`:1243`), `store.verdict` (`:1175`), `store.dsr_at` (`:1100`) — the
  engine's dev/test rule is correct and is the thing being published. **Not edited, not even to
  call `luck_gated`**; a pin test holds the two to one rule instead (Step 3).
- `store.owner_failures` and the trial schema — **Phase 7** also edits `lab/store.py` and depends on
  this phase. Phase 7 must quote `lab/store.py` as this phase leaves it. **What phase 2 changed in
  `lab/store.py`: `SNAPSHOT_VERSION` 3 -> 4 (`:1687`); a new `luck_gated()` after
  `published_verdict` (inserted at `:1272`, shifting everything below by ~22 lines); one new key
  `"luckGated"` inside `_snapshot_trial`'s returned dict (`:1791`).** Nothing else.
- `.github/workflows/engine-ci.yml`, `engine/tests/test_lab_npolicy.py` — Phase 1.
- `web/app/(app)/*`, `web/lib/session.ts` — Phase 9.
- `web/lib/sean/*` — Phase 10.
- `lab/lab.sqlite` — **never written by this phase.** `web/data/lab.json` is regenerated from it
  read-only; the database itself is untouched, so Phase 1's `COMMITTED_DEV_TRIALS = 126` re-pin is
  unaffected.

**Scope note on file count.** The index lists 13 files (corrected by the reconciler from the draft's
8); this plan touches 13. The extra five are
test-side fixtures (`web/lib/sera/fixture.ts`, `derive.test.ts`, `web/app/sera/methods/view.test.ts`,
`web/app/sera/overview.test.ts`) plus a one-line correctness fix in `web/app/sera/methods/page.tsx`.
They are forced, not discretionary: `LabTrial` gains a **required** field, so every literal that
constructs one fails `tsc --noEmit` until it carries the field. No other phase owns any file under
`web/app/sera` or `web/lib/sera`.

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/store.py` | modify | `luck_gated()` after `published_verdict` (`:1272`); `SNAPSHOT_VERSION` 3 -> 4 (`:1687`); `"luckGated"` key in `_snapshot_trial` (`:1791`) |
| `engine/tests/test_lab_snapshot.py` | modify | `TRIAL_KEYS` (`:50-53`) gains the key; `s["version"] == 4` (`:280`, the **snapshot** version, an int); two new tests appended after `:359`. **The six `store.schema_version(...) == "3"` / `store.SCHEMA_VERSION == "3"` pins at `:86`, `:104`, `:113`, `:180`, `:207`, `:238` are left at `"3"` — they are the sqlite schema version and phase 7 moves them** |
| `web/data/lab.json` | regenerate | `lab export-json`; 128 trials gain `luckGated` |
| `web/lib/sera/types.ts` | modify | `version: 4` (`:8`) + its comment (`:4-7`); `LabTrial.luckGated` after `dsrNow` (`:157`) |
| `web/lib/sera/derive.ts` | modify | header comment (`:1-15`); `conditionOk` (`:103`); `gateChecks` dsr row (`:153-161`); `conditionsPassed` doc (`:165`); `funnel` (`:196-213`) |
| `web/lib/sera/fixture.ts` | modify | `trial()` base literal (`:59`) and `withVerdict` (`:71-76`) carry `luckGated` |
| `web/lib/sera/lab.test.ts` | modify | version pin (`:8`); key list (`:10-11`); the verdict assertion (`:50-67`); one new contract test |
| `web/lib/sera/derive.test.ts` | modify | one new `gateChecks` case for an ungated row (after `:75`) |
| `web/app/sera/methods/view.ts` | modify | `Mark` doc + `markLabel` (`:142-155`); `conditionSentence` (`:170-193`); `workedSummary` (`:203-211`); new `dsrNote`; `techRows` (`:305-323`) |
| `web/app/sera/methods/view.test.ts` | modify | `trial()` base literal (`:20-30`); two new cases |
| `web/app/sera/methods/[id]/page.tsx` | modify | the DSR cell (`:332-337`); import `dsrNote` (`:20-24`) |
| `web/app/sera/methods/page.tsx` | modify | `Dots`'s `missed` filter (`:174`) |
| `web/app/sera/overview.test.ts` | modify | `trial()` base literal (`:41-76`) carries `luckGated` |

---

## Implementation Steps

### Step 1: The engine names the split once
**File:** `engine/src/seer_engine/lab/store.py:1272` (immediately after `published_verdict`'s
closing `)`, before the `REEVALUATION_MARKER` comment block)
**Change:** add the predicate. `published_verdict` is **not** edited — Step 3 pins the two to one
rule instead, which is how this phase respects the boundary without leaving the rule in two places
unguarded.
**Code:**
```python
def luck_gated(trial: Mapping[str, Any] | sqlite3.Row) -> bool:
    """Does the luck gate apply to ``trial``? True for a dev row, False for a test look.

    The same split :func:`published_verdict` makes, named once so that no reader downstream has to
    re-derive it. A dev row is one result selected from many, so its Sharpe is deflated by the
    number of looks; a test-window row is a single pre-registered confirmatory look with no
    selection to deflate, so its recorded ``dsr`` is a measurement and not a condition.

    **This is not ``Verdict.derived``.** ``derived`` is False for a test row *and* for a dev row
    whose DSR could not be evaluated -- and those two are opposites. The first is a hurdle that
    does not apply; the second is a hurdle that was missed because nothing could be measured
    (the 54 P7a seed rows, whose ``dsr`` is NULL by construction). A reader that cannot tell them
    apart prints a pass where there is none: ``web/lib/sera/derive.conditionOk`` returned a green
    tick on ``M0021-B70-RAW``'s 0.513013 against a published bar of 0.90, which is R7.

    Published as ``trials[].luckGated`` from snapshot v4 so the web reads this answer rather than
    guessing at it. ``test_the_marker_names_the_same_split_published_verdict_makes`` holds this
    function and ``published_verdict`` to one rule, so the two cannot drift apart.
    """
    return str(trial["window"]) == "dev"
```
**Impact:** additive; nothing calls it yet.

### Step 2: `_snapshot_trial` publishes the marker, and the version moves
**File:** `engine/src/seer_engine/lab/store.py:1687` and `:1745-1797`
**Change:** bump `SNAPSHOT_VERSION` and add one key to the verdict block of `_snapshot_trial`.
**Code — replace the `SNAPSHOT_VERSION` comment block and constant at `:1679-1687`:**
```python
# 2 adds the derived verdict to every trial (``failedNow`` / ``eligibleNow`` / ``dsrNow``). The
# bump is not cosmetic: before it, the snapshot published the gate's bars live and every trial's
# verdict as recorded history, so a page drawing both read `0.912 < 0.90` off one trial -- the
# tick from the row's recorded `DSR >= 0.95`, the number from the live bar beside it.
#
# 3 adds ``paper``: which roster entry is which lab method (``paper.roster.LAB_PROVENANCE``). The
# web had no way to answer that -- ``rules_id`` is shared by a dozen methods, so it is not a key --
# and a map hand-written in the site would drift the next promotion night in silence.
#
# 4 adds ``luckGated``: does the luck gate apply to this row at all. The lab produced its first two
# test-window looks on 2026-10-07, and ``published_verdict`` rightly does not luck-gate them -- a
# pre-registered confirmatory look has no selection to deflate. Nothing said so, so every consumer
# re-derived the rule and the web derived it wrongly: a score of 0.513013 rendered as a cleared
# hurdle against a published bar of 0.90. The marker is a third state, not a second one: it
# separates "this hurdle does not apply" from "this hurdle could not be measured, so it was
# missed", which ``Verdict.derived`` conflates (R7).
SNAPSHOT_VERSION = 4
```
**Code — `_snapshot_trial`, complete, replacing `:1745-1797`:**
```python
def _snapshot_trial(t: Mapping[str, Any], v: Verdict) -> dict[str, Any]:
    """One ``trials`` row as the web reads it: the record, **and** the verdict it reads as now.

    Both, and labelled as such, because they answer different questions and the site asks both.
    ``failed`` / ``eligible`` / ``dsr`` / ``nTrialsAtRun`` are the row as the lab wrote it on its
    run date -- append-only history, and the technical record a reader reruns from. ``failedNow``
    / ``eligibleNow`` / ``dsrNow`` are ``published_verdict``: the same row judged by the bars in
    force at export time, at the gate's current N.

    Publishing only the first is what made ``/sera/methods/M0022`` print ``0.912 < 0.90``: the
    gate block beside it is resolved live (``_gate_n``, ``DSR_MIN``), so a page that took its
    ticks from ``failed`` and its numbers from ``gate`` was reading two different days at once.
    A page must take **both** from the ``Now`` fields; ``failed`` is for the record panel only.

    ``luckGated`` says whether the luck hurdle applies to this row at all (:func:`luck_gated`).
    Without it the verdict is ambiguous in exactly one place: a test look's ``failedNow`` omits
    the luck label because the gate does not apply, and a reader with only ``failedNow`` to go on
    cannot tell that from a hurdle that was cleared. It published a tick on 0.513013 against a
    bar of 0.90. **Three states, not two**: gated and cleared, gated and missed (``dsrNow`` may be
    null -- nothing is admitted for being unmeasurable), and not gated at all.
    """
    pf = t["profit_factor"]
    return {
        "n": int(t["n"]),
        "methodId": t["method_id"],
        "candidateId": t["candidate_id"],
        "rulesId": t["rules_id"],
        "allocatorId": t["allocator_id"],
        "configText": t["config_text"],
        "window": t["window"],
        "start": t["start"],
        "end": t["end"],
        "gitSha": t["git_sha"],
        "runAt": t["run_at"],
        "totalReturn": _num(t["total_return"]),
        "cagr": _num(t["cagr"]),
        "maxDrawdown": _num(t["max_drawdown"]),
        "profitFactor": _num(pf),
        "pfInfinite": pf is not None and float(pf) == math.inf,
        "trades": int(t["trades"]),
        "sharpe": _num(t["sharpe"]),
        "exposure": _num(t["exposure"]),
        "turnover": _num(t["turnover"]),
        "worstYear": None if t["worst_year"] is None else int(t["worst_year"]),
        "worstYearReturn": _num(t["worst_year_return"]),
        "spyTrReturn": _num(t["spy_tr_return"]),
        "spyTrCagr": _num(t["spy_tr_cagr"]),
        "mar": _num(t["mar"]),
        # The record: what the lab said on the run date, by the bars of that day.
        "failed": [f for f in t["failed"].split("; ") if f],
        "eligible": bool(t["eligible"]),
        "dsr": _num(t["dsr"]),
        "nTrialsAtRun": int(t["n_trials_at_run"]),
        # Whether the luck hurdle applies to this row at all. Published so the web never has to
        # re-derive the dev/test rule -- which it did, and got wrong.
        "luckGated": luck_gated(t),
        # The verdict: the same row by the bars in force now, at the gate's N (gate.dsrN).
        "failedNow": list(v.failed),
        "eligibleNow": v.eligible,
        "dsrNow": _num(v.dsr),
        "curve": _snapshot_curve(t["curve_json"]),
    }
```
**Impact:** `web/data/lab.json` and every snapshot-shape test change. The engine suite is red until
Steps 3 and 4 land.

### Step 3: The engine pins the marker, and pins it to `published_verdict`
**File:** `engine/tests/test_lab_snapshot.py:50-53`, `:280`, and two new tests after
`test_the_snapshot_follows_the_contract` (i.e. after `:359`)
**Change:** extend the key set, move the version pin, add the two tests that make the marker
non-vacuous and drift-proof.
**Code — replace `TRIAL_KEYS` at `:50-53`:**
```python
TRIAL_KEYS = {"n", "methodId", "candidateId", "rulesId", "allocatorId", "configText", "window", "start", "end",
              "gitSha", "runAt", "totalReturn", "cagr", "maxDrawdown", "profitFactor", "pfInfinite", "trades",
              "sharpe", "exposure", "turnover", "worstYear", "worstYearReturn", "spyTrReturn", "spyTrCagr", "mar",
              "failed", "eligible", "dsr", "nTrialsAtRun", "luckGated", "failedNow", "eligibleNow", "dsrNow",
              "curve"}
```
**Code — replace `:280`:**
```python
    assert s["version"] == 4
```
**Code — insert both tests after `test_the_snapshot_follows_the_contract` (after `:359`):**
```python
def test_a_test_window_row_publishes_that_the_luck_gate_does_not_apply(lab):
    """R7: the snapshot says, per trial, whether the luck hurdle applies -- it is not re-derived.

    A test-window look is one pre-registered confirmatory run with no selection among results to
    deflate, so ``published_verdict`` applies the four owner thresholds and nothing else and its
    recorded ``dsr`` rides through as a measurement. Published with no marker, that verdict read
    on the site as a *cleared* luck check: ``M0021-B70-RAW`` scored 0.513013 against a published
    bar of 0.90 and rendered a green tick.
    """
    with lab:
        store.insert_trials(lab, [store.TrialRow(
            method_id="M0001", candidate_id="M0001-A", config_digest="d2", config_text="t", rules_id="r",
            allocator_id="a", window="test", start="2015-10-19", end="2026-10-01", store_fingerprint="fp",
            git_sha="abc", run_at="2026-10-06T00:00:00+00:00", total_return=0.2, cagr=0.02,
            max_drawdown=0.1, profit_factor=1.4, trades=150, sharpe=0.3, exposure=0.9, turnover=1.0,
            worst_year=2018, worst_year_return=-0.1, spy_tr_return=0.5, spy_tr_cagr=0.07, mar=0.2,
            failed="beats SPY TR", eligible=False, dsr=0.513013, n_trials_at_run=56,
            curve_json='[["2015-10-30",1.0],["2015-11-30",1.01]]',
        )])
    s = store.snapshot(lab)
    by_window = {t["window"]: t for t in s["trials"] if t["n"] in (55, 56)}

    look = by_window["test"]
    assert look["luckGated"] is False
    # The score is still published -- it is a measurement, not a hurdle. Dropping it would make
    # "not applicable" and "not measured" indistinguishable, which is the defect, not the fix.
    assert look["dsrNow"] == 0.513013
    assert not any(store.is_luck_label(f) for f in look["failedNow"])
    # The owner thresholds still apply to a test row and are still re-derived from its columns.
    assert look["failedNow"] == ["beats SPY TR"] and look["eligibleNow"] is False

    dev_row = by_window["dev"]
    assert dev_row["luckGated"] is True
    # The gated row with no clearable score is the other side of the distinction: a MISS, with
    # the luck label present, not an exemption.
    assert any(store.is_luck_label(f) for f in dev_row["failedNow"])

    assert s["summary"]["testLooks"] == 1
    assert [t["luckGated"] for t in s["trials"]].count(False) == s["summary"]["testLooks"]


def test_the_marker_names_the_same_split_published_verdict_makes(lab):
    """``luck_gated`` and ``published_verdict`` are one rule, written in two places on purpose.

    ``published_verdict`` is correct and this phase does not touch it; the marker is published
    beside it. This test is what stops the two drifting: if ``published_verdict`` ever started
    luck-gating a test look -- or stopped gating a dev row -- the marker would be telling the site
    something the verdict no longer does, and the site would print a tick on it.
    """
    with lab:
        store.insert_trials(lab, [store.TrialRow(
            method_id="M0001", candidate_id="M0001-A", config_digest="d2", config_text="t", rules_id="r",
            allocator_id="a", window="test", start="2015-10-19", end="2026-10-01", store_fingerprint="fp",
            git_sha="abc", run_at="2026-10-06T00:00:00+00:00", total_return=0.2, cagr=0.02,
            max_drawdown=0.1, profit_factor=1.4, trades=150, sharpe=0.3, exposure=0.9, turnover=1.0,
            worst_year=2018, worst_year_return=-0.1, spy_tr_return=0.5, spy_tr_cagr=0.07, mar=0.2,
            failed="beats SPY TR", eligible=False, dsr=0.1, n_trials_at_run=56,
            curve_json='[["2015-10-30",1.0]]',
        )])
    windows = set()
    for row in lab.execute("SELECT * FROM trials ORDER BY n").fetchall():
        gated = store.luck_gated(row)
        windows.add(str(row["window"]))
        assert gated == (str(row["window"]) == "dev")
        v = store.published_verdict(lab, row)
        if gated:
            # A gated row's luck test is decided: it is in `failed` exactly when it was not passed.
            assert (v.dsr is None or v.dsr < store.DSR_MIN) == any(store.is_luck_label(f) for f in v.failed)
        else:
            # An ungated row never carries a luck failure, whatever its score says.
            assert not any(store.is_luck_label(f) for f in v.failed)
            assert v.dsr == 0.1  # carried verbatim, and still under the 0.90 bar
    assert windows == {"dev", "test"}  # neither branch was vacuous
```
**Impact:** the engine suite is green again except
`test_the_committed_snapshot_is_the_export_of_the_committed_database`, which Step 4 fixes.
Note `lab` is a function-scoped fixture, so each test gets its own database; neither test disturbs
`test_the_snapshot_follows_the_contract`'s `devTrials: 55, testLooks: 0` pins.

### Step 4: Regenerate the committed snapshot
**File:** `web/data/lab.json` (regenerated, not hand-edited)
**Change:** run the exporter against the committed database.
**Code:**
```sh
cd /home/miftah/.worktrees/seer/gotrade-fee-rebuild
PYTHONPATH=engine/src python3 -m seer_engine lab export-json
```
**Verify the diff is only the new field and the version:**
```sh
PYTHONPATH=engine/src python3 - <<'PY'
import json
s = json.load(open('web/data/lab.json'))
assert s['version'] == 4, s['version']
g = [t for t in s['trials'] if t['luckGated']]
u = [t for t in s['trials'] if not t['luckGated']]
print('gated', len(g), 'ungated', len(u), 'testLooks', s['summary']['testLooks'])
assert len(u) == s['summary']['testLooks'] == 2
assert all(t['window'] == 'test' for t in u)
for t in u:
    print(t['candidateId'], t['dsrNow'], t['failedNow'])
PY
```
Expected, measured against the committed database: `gated 126 ungated 2 testLooks 2`, then
`M0021-B70-RAW 0.513013 ['beats SPY TR']` and
`M0029-B70-RAW-FRAC 0.388958 ['beats SPY TR', 'max DD <= 20%']`.
**Impact:** `lab/lab.sqlite` is **not** written — `export-json` opens it read-only. Commit
`web/data/lab.json` alone. `test_the_committed_snapshot_is_the_export_of_the_committed_database`
goes green.

### Step 5: The web type carries the marker
**File:** `web/lib/sera/types.ts:4-8` and `:152-158`
**Change:** move the version pin and add the field, required.
**Code — replace `:4-8`:**
```ts
  /**
   * 2 added the derived verdict to every trial (`failedNow` / `eligibleNow` / `dsrNow`);
   * 3 added `paper`, which names the lab method behind each roster entry;
   * 4 added `luckGated`, which says whether the luck hurdle applies to a trial at all.
   */
  version: 4;
```
**Code — replace `:152-158` (the `dsrNow` doc, `dsrNow`, and `curve`):**
```ts
  /**
   * The verdict: this trial's deflated Sharpe re-evaluated at `gate.dsrN`, or null when it
   * cannot be — the 54 P7a seed rows have no recorded DSR. On a `luckGated` row, null is a
   * **missed** luck check, not an excused one: the engine puts the luck label in `failedNow` for
   * exactly those rows. On a row that is not `luckGated` this is a measurement with no hurdle
   * attached, and must never be compared against `gate.dsrMin`.
   */
  dsrNow: number | null;
  /**
   * **Does the luck hurdle apply to this trial at all?** True for a development row, false for a
   * test-window look (`lab.store.luck_gated`). The web reads this; it must never re-derive it.
   *
   * A test look is one pre-registered confirmatory run, so there is no selection among results to
   * deflate and the engine applies the four owner thresholds and nothing else. `failedNow`
   * therefore has no luck label on such a row — which, read without this marker, is
   * indistinguishable from a cleared hurdle. That is how `M0021-B70-RAW` came to render a green
   * tick on a score of 0.513 against a published bar of 0.90.
   *
   * Three states, and the page must show three: `luckGated && conditionOk === true` (cleared),
   * `luckGated && conditionOk === false` (missed, possibly because `dsrNow` is null and nothing
   * could be scored), and `!luckGated` (does not apply).
   */
  luckGated: boolean;
  curve: [string, number][];
```
**Impact:** `npx tsc --noEmit` now fails in every file that builds a `LabTrial` literal — Steps 6,
9, 11 and 13 close those.

### Step 6: `derive.ts` stops guessing
**File:** `web/lib/sera/derive.ts:1-15`, `:96-107`, `:153-161`, `:165-168`, `:196-214`
**Change:** `conditionOk` returns `null` for an ungated luck check; `gateChecks` says so in words;
the funnel's denominator counts only rows the hurdle applies to.
**Code — replace the module header at `:1-15`:**
```ts
/**
 * Pure reshaping of the lab snapshot for the /sera pages.
 *
 * Pass/fail always comes from the engine (invariant 5: the web never re-judges a trial), and
 * the gate is used only to print targets. **Which** engine answer, though, is the whole
 * question: `trial.failed` is what the lab said on the run date, and `trial.failedNow` is what
 * the same row is judged as today. Reading the first while printing targets out of `gate` is
 * how the method page came to render `Luck check: no (0.912 < 0.90)` — the cross from a row
 * recorded against the old 0.95 bar, the number from the live one beside it.
 *
 * So: every pass/fail here reads `failedNow`, and `failed` is displayed only where the page
 * says it is showing the record (the technical detail block). The web still does not re-judge
 * anything — it must not, because the luck test is not `dsr >= gate.dsrMin`; re-scoring a DSR
 * at today's N is arithmetic the engine holds (`store.dsr_at`).
 *
 * The same rule covers **which hurdles a row has**, not only how it did on them. A hurdle the
 * engine never applied is absent from `failedNow`, and absence read as a pass is the worst
 * failure this page has: a missed hurdle shown as a green tick. So the one hurdle that does not
 * apply to every row — the luck check, which a pre-registered test look has no selection to
 * deflate — is read off the engine's own marker, `trial.luckGated`, and never inferred from the
 * shape of `failedNow`.
 */
```
**Code — replace `:96-107`:**
```ts
/**
 * Does this trial clear `key` **as the bars read now**? true = cleared, false = missed,
 * null = the hurdle does not apply to this row.
 *
 * Reads `failedNow` and `luckGated`, never `failed`. The engine decided all six there
 * (`store.published_verdict`) against the same gate the snapshot publishes, and said which rows
 * the luck hurdle applies to (`store.luck_gated`), so this is a lookup, not a judgement — which
 * is what keeps a tick and the target printed beside it from describing two different days.
 *
 * `null` means **not applicable**, never "not measured". A gated row whose DSR could not be
 * scored still comes back `false`: the engine puts the luck label in `failedNow` for exactly
 * those rows, because nothing is admitted for being unmeasurable (its D11).
 */
export function conditionOk(trial: LabTrial, key: ConditionKey): boolean | null {
  if (key === 'dsr') {
    if (!trial.luckGated) return null;
    return !trial.failedNow.some((f) => f.startsWith(DSR_FAILURE_PREFIX));
  }
  if (key === 'drawdown') return !trial.failedNow.some((f) => f.startsWith(DRAWDOWN_FAILURE_PREFIX));
  return !trial.failedNow.includes(FAILURE_LABEL[key]);
}
```
**Code — replace the `dsr` entry of `gateChecks` at `:153-161`:**
```ts
    {
      key: 'dsr',
      label: CONDITION_LABEL.dsr,
      // `dsrNow`, not `dsr`: the score at the gate's N, which is the N `gate.dsrMin` is the bar
      // for. The recorded `dsr` belongs to the N of its own run date and is shown as the record.
      value: trial.dsrNow === null ? 'not measured' : trial.dsrNow.toFixed(2),
      // A test look is scored but not gated, so quoting the bar beside its number would invent a
      // hurdle the lab never set it.
      target: trial.luckGated ? `${num(gate.dsrMin)} or more` : 'does not apply to a test look',
      ok: conditionOk(trial, 'dsr'),
    },
```
**Code — replace `:165-168`:**
```ts
/**
 * How many of the six hurdles the trial cleared. Not-measured counts as not cleared (the engine
 * already listed it as a failure); a hurdle that does not apply counts as neither cleared nor
 * missed, so a test look reads 5 of 5 rather than 5 of 6.
 */
export function conditionsPassed(trial: LabTrial): number {
  return CONDITION_KEYS.filter((k) => conditionOk(trial, k) === true).length;
}
```
**Code — replace `funnel` at `:196-214`:**
```ts
/**
 * Per hurdle, how many dev trials cleared it.
 *
 * `measured` is how many rows the hurdle could be *scored* on, which is every row except for the
 * luck check: the P7a seed rows have no DSR to re-evaluate at any N. Those rows still **miss**
 * the luck check — nothing is admitted for being unmeasurable, and `passing` counts them as
 * misses — but saying "1 of the 56 it was checked on" rather than "1 of 110" is the honest
 * denominator, and the page's tip names the gap.
 *
 * `luckGated` is checked alongside the score for the same reason the denominator exists at all:
 * a row the hurdle does not apply to was not "checked and unscorable", it was not checked. Every
 * dev row is gated today, so this changes no published number — it stops the count being wrong
 * if that ever stops being true.
 */
export function funnel(trials: LabTrial[]): FunnelRow[] {
  const dev = devTrials(trials);
  return CONDITION_KEYS.map((key) => ({
    key,
    label: CONDITION_LABEL[key],
    passing: dev.filter((t) => conditionOk(t, key) === true).length,
    measured: key === 'dsr' ? dev.filter((t) => t.luckGated && t.dsrNow !== null).length : dev.length,
    total: dev.length,
  }));
}
```
**Impact:** every tick on the site that reads `conditionOk` now shows three states for the luck
check. `misses()` is unchanged (`=== false`), so an ungated row is never listed as a miss.

### Step 7: The shared test builders default the marker from the window
**File:** `web/lib/sera/fixture.ts:25-76`
**Change:** `withVerdict` derives `luckGated` from the trial's window, so the three test builders
that share it agree and a test writing `{ window: 'test' }` gets an ungated row for free.
**Code — replace `trial` and `withVerdict` at `:25-76`:**
```ts
export function trial(over: Partial<LabTrial> = {}): LabTrial {
  const t: LabTrial = {
    n: 1,
    methodId: 'M0001',
    candidateId: 'M0001-V1',
    rulesId: 'rules-v1',
    allocatorId: 'alloc-v1',
    configText: '{}',
    window: 'dev',
    start: '1996-01-03',
    end: '2015-10-16',
    gitSha: 'abc1234',
    runAt: '2026-10-04T10:00:00+07:00',
    totalReturn: 3.2,
    cagr: 0.076,
    maxDrawdown: 0.12,
    profitFactor: 1.5,
    pfInfinite: false,
    trades: 240,
    sharpe: 0.8,
    exposure: 0.9,
    turnover: 2.1,
    worstYear: 2008,
    worstYearReturn: -0.11,
    spyTrReturn: 4.0,
    spyTrCagr: 0.079,
    mar: 0.63,
    failed: ['beats SPY TR'],
    eligible: false,
    dsr: 0.97,
    nTrialsAtRun: 55,
    luckGated: true,
    failedNow: [] as string[],
    eligibleNow: false,
    dsrNow: null as number | null,
    curve: [['1996-01-31', 1]] as [string, number][],
    ...over,
  };
  return withVerdict(t, over);
}

/**
 * Default a trial's verdict fields from its record: `failedNow` mirrors `failed`, `dsrNow`
 * mirrors `dsr`, and a row with no score picks up the luck label — the engine's own rule, that a
 * luck test which cannot be scored was not passed. Shared by the test-local trial builders so
 * all three agree. A test about the record/verdict split passes the fields explicitly instead.
 *
 * `luckGated` follows the window unless the test sets it, which is `store.luck_gated` exactly: a
 * `{ window: 'test' }` trial comes back ungated and carries no luck label, so a test does not
 * have to remember to say both things.
 */
export function withVerdict(t: LabTrial, over: Partial<LabTrial>): LabTrial {
  const luckGated = over.luckGated ?? t.window === 'dev';
  const dsrNow = 'dsrNow' in over ? (over.dsrNow as number | null) : t.dsr;
  const unscored = luckGated && dsrNow === null && !t.failed.some((f) => f.startsWith('DSR >= '));
  const failedNow = over.failedNow ?? (unscored ? [...t.failed, 'DSR >= 0.90'] : t.failed);
  return { ...t, luckGated, failedNow, eligibleNow: over.eligibleNow ?? failedNow.length === 0, dsrNow };
}
```
**Impact:** the `unscored` guard gains `luckGated &&` so an ungated fixture row never picks up a
luck label it could not have. No existing `trial()` call site changes meaning: every one of them is
`window: 'dev'` unless it overrides, and the two that override `failedNow` pass it explicitly.

### Step 8: `lab.test.ts` reads the marker
**File:** `web/lib/sera/lab.test.ts:8`, `:9-12`, `:50-67`
**Change:** move the version pin, and split the verdict assertion three ways — the third branch
reading `luckGated` instead of excusing the rows.
**Code — replace `:8`:**
```ts
    expect(lab.version).toBe(4);
```
(The key list at `:9-12` is unchanged: `luckGated` is a trial key, not a top-level one. Leave it.)
**Code — replace the whole `it(...)` at `:50-67`:**
```ts
  it('publishes a verdict that agrees with the gate published beside it', () => {
    // The regression this file exists to catch. `/sera/methods/M0022` once rendered
    // "Luck check: no (0.912 < 0.90)": the cross came from the trial's recorded `DSR >= 0.95`
    // and the number from the live gate. Both halves of every hurdle must now come from the
    // same day, so a scored trial misses the luck check exactly when its score is under the bar.
    //
    // Which rows that applies to is the engine's answer, read here and not re-derived: a
    // pre-registered test look has no selection to deflate, so `published_verdict` applies the
    // owner thresholds and nothing else and `luckGated` is false. Before the marker existed this
    // branch had to be either a failure (it was) or an exception that also excused the live page.
    for (const t of lab.trials) {
      const missedLuck = t.failedNow.some((f) => f.startsWith(DSR_FAILURE_PREFIX));
      if (!t.luckGated) {
        // No hurdle, whatever the score. M0021-B70-RAW: 0.513013, and correctly not a failure.
        expect([t.candidateId, missedLuck]).toEqual([t.candidateId, false]);
      } else if (t.dsrNow !== null) {
        expect([t.candidateId, missedLuck]).toEqual([t.candidateId, t.dsrNow < lab.gate.dsrMin]);
      } else {
        // A trial with no score cannot pass a luck test it never had.
        expect([t.candidateId, missedLuck]).toEqual([t.candidateId, true]);
      }

      const missedDd = t.failedNow.some((f) => f.startsWith(DRAWDOWN_FAILURE_PREFIX));
      if (t.maxDrawdown !== null) {
        expect([t.candidateId, missedDd]).toEqual([t.candidateId, t.maxDrawdown > lab.gate.maxDrawdown]);
      }
      expect(t.eligibleNow).toBe(t.failedNow.length === 0);
    }
  });

  it('says per trial whether the luck gate applies, and the ungated branch is not empty', () => {
    // The marker's contract, pinned on the real snapshot: it is window-shaped, it agrees with
    // `summary.testLooks`, and there is at least one row where it actually changes the answer —
    // a scored row, under the bar, that is correctly not a failure. Without that last pin the
    // branch above could pass vacuously the day the lab's test looks are rewritten.
    expect(lab.trials.every((t) => t.luckGated === (t.window === 'dev'))).toBe(true);
    const ungated = lab.trials.filter((t) => !t.luckGated);
    expect(ungated.length).toBe(lab.summary.testLooks);
    expect(ungated.length).toBeGreaterThan(0);
    const underTheBarAnyway = ungated.filter(
      (t) => t.dsrNow !== null && t.dsrNow < lab.gate.dsrMin,
    );
    expect(underTheBarAnyway.length).toBeGreaterThan(0);
    for (const t of underTheBarAnyway) {
      expect(t.failedNow.some((f) => f.startsWith(DSR_FAILURE_PREFIX))).toBe(false);
    }
  });
```
**Impact:** `lib/sera/lab.test.ts` goes to 11 passing tests.

### Step 9: `derive.test.ts` covers the third state
**File:** `web/lib/sera/derive.test.ts`, inserted after the existing unscorable-luck case (`:75`)
**Change:** one new case. No existing case changes — every fixture row is `window: 'dev'`.
**Code:**
```ts
  it('shows a test look as not applicable, never as a cleared hurdle', () => {
    // M0021-B70-RAW exactly: a pre-registered test look scoring 0.513 against a published bar of
    // 0.90, with no luck label in `failedNow` because the gate does not apply to it. Read without
    // `luckGated` this rendered a green tick, which is the whole of R7.
    const look = trial({
      window: 'test', dsr: 0.513013, dsrNow: 0.513013,
      failed: ['beats SPY TR'], failedNow: ['beats SPY TR'],
    });
    expect(look.luckGated).toBe(false);
    expect(gateChecks(look, GATE)[5]).toMatchObject({
      value: '0.51', target: 'does not apply to a test look', ok: null,
    });
    // Not applicable is neither a pass nor a miss: it does not count toward the tally and it does
    // not appear in the misses list.
    expect(conditionsPassed(look)).toBe(4);
    expect(misses(look)).toEqual(['spy']);
    // And the other side of the distinction is untouched: a gated row with no score is a MISS.
    const seed = trial({ dsr: null, dsrNow: null, failed: ['beats SPY TR'], failedNow: ['beats SPY TR', 'DSR >= 0.90'] });
    expect(seed.luckGated).toBe(true);
    expect(gateChecks(seed, GATE)[5]).toMatchObject({ value: 'not measured', ok: false });
  });
```
**Impact:** none on the app. `conditionsPassed(look)` is 4 because the fixture's `spy` hurdle fails
and the luck check no longer counts either way.

### Step 10: `view.ts` says "not applicable" in plain words
**File:** `web/app/sera/methods/view.ts:142-155`, `:170-193`, `:203-211`, `:305-323`
**Change:** `markLabel`'s null branch, `conditionSentence`'s null branch, a headline that counts
applicable hurdles, a new `dsrNote` for the variants table, and one more technical-record row.
**Code — replace `:142-155`:**
```ts
/**
 * true = cleared, false = missed, null = the hurdle does not apply to this row
 * (derive.conditionOk, which reads the engine's `failedNow` and `luckGated`).
 *
 * `null` is the luck check on a test-window look and nothing else. A luck test that *could not be
 * scored* is still a miss — the engine lists it in `failedNow` — so a dashed mark always means
 * "no such hurdle here", never "we did not look".
 */
export type Mark = { key: ConditionKey; label: string; ok: boolean | null };

/** The six hurdles of one trial, in display order. */
export const marks = (t: LabTrial): Mark[] =>
  CONDITION_KEYS.map(key => ({ key, label: CONDITION_LABEL[key], ok: conditionOk(t, key) }));

/** 'Beats SPY: cleared' / 'missed' / 'not applicable'. */
export const markLabel = (m: Mark): string =>
  `${m.label}: ${m.ok === null ? 'not applicable' : m.ok ? 'cleared' : 'missed'}`;
```
**Code — replace `conditionSentence` at `:169-193`:**
```ts
/** 'Beats SPY: no (7.6% vs 7.9% a year).' and so on, one per hurdle. */
export function conditionSentence(key: ConditionKey, ok: boolean | null, t: LabTrial, gate: Gate): string {
  const label = CONDITION_LABEL[key];
  if (ok === null) {
    // Only the luck check reaches here, and only on a test look. Say which hurdle it is, say it
    // does not apply, and still show the number — it was measured, it is simply not a bar.
    return key === 'dsr'
      ? `${label}: does not apply. A test run is a single try booked in advance, so there is nothing to discount for luck${t.dsrNow === null ? '' : ` (it scored ${fixed(t.dsrNow, 3)})`}.`
      : `${label}: does not apply.`;
  }
  const yn = ok ? 'yes' : 'no';
  switch (key) {
    case 'spy':
      return `${label}: ${yn} (${pct1(t.cagr)} vs ${pct1(t.spyTrCagr)} a year).`;
    case 'drawdown':
      return `${label}: ${yn} (${pct1(t.maxDrawdown)} ${ok ? '≤' : '>'} ${pct(gate.maxDrawdown, 0)}).`;
    case 'pf':
      return `${label}: ${yn} (${pfText(t)} ${ok ? '≥' : '<'} ${gate.minProfitFactor}).`;
    case 'trades':
      return `${label}: ${yn} (${count(t.trades)} ${ok ? '≥' : '<'} ${count(gate.minTrades)}).`;
    case 'owner':
      return ok ? `${label}: yes (none needed).` : `${label}: no (needs a setting only the owner can decide).`;
    case 'dsr':
      // `dsrNow` at `gate.dsrN`, never the recorded pair: the bar is the bar *at that N*, and
      // quoting a score from one N against a bar from another is how this line once read
      // "no (0.912 < 0.90)". Null means the luck test could not be run, which is a miss.
      return t.dsrNow === null
        ? `${label}: no (not measured — the luck test cannot be scored for this trial, so it cannot pass it).`
        : `${label}: ${yn} (${fixed(t.dsrNow, 3)} ${ok ? '≥' : '<'} ${fixed(gate.dsrMin, 2)}, scored at N = ${count(gate.dsrN)}).`;
  }
}

/**
 * What follows the DSR number in the variants table: the N the score belongs to, or why there is
 * no bar beside it. Null when there is no score to annotate.
 *
 * `at N 126` beside a test look's number is a false statement — that score was never computed at
 * the gate's N and is not read against it — so the two cases carry different words.
 */
export const dsrNote = (t: LabTrial, gate: Gate): string | null =>
  t.dsrNow === null ? null : t.luckGated ? `at N ${count(gate.dsrN)}` : 'not a hurdle on a test run';
```
**Code — replace `workedSummary` at `:202-211`:**
```ts
/** The plain 'Did it work?' answer for a method's best variant. */
export function workedSummary(best: LabTrial, gate: Gate): Worked {
  const lines = marks(best).map(m => ({ key: m.key, ok: m.ok, text: conditionSentence(m.key, m.ok, best, gate) }));
  const passed = conditionsPassed(best);
  // Hurdles that do not apply to this row are not hurdles it failed to clear. Every dev row has
  // all six, so this reads "all six" exactly as before; a test look is counted out of five.
  const applicable = lines.filter(l => l.ok !== null).length;
  const span = windowText(best);
  const headline = passed === applicable
    ? `Yes. Its best variant, ${best.candidateId}, cleared all ${applicable === CONDITION_KEYS.length ? 'six' : count(applicable)} hurdles on ${span} data.`
    : `Not yet. Its best variant, ${best.candidateId}, cleared ${passed} of ${count(applicable)} hurdles on ${span} data.`;
  return { headline, lines, sentence: lines.map(l => l.text).join(' ') };
}
```
**Code — replace `techRows` at `:304-323`:**
```ts
/** The full technical record of one trial, as label/value rows. */
export function techRows(t: LabTrial): [string, string][] {
  return [
    ['Trial number', `#${t.n}`],
    ['Window', `${t.window === 'dev' ? 'Development' : 'Test'}, ${t.start} → ${t.end}`],
    ['Trading rules', t.rulesId],
    ['Allocator', t.allocatorId],
    ['Code version (git)', t.gitSha || '—'],
    ['Run at', t.runAt],
    ['Tries counted when run (N)', count(t.nTrialsAtRun)],
    ['Time in the market', pct1(t.exposure)],
    ['Turnover', fixed(t.turnover, 2)],
    ['Worst year', t.worstYear === null ? '—' : `${t.worstYear} (${signed1(t.worstYearReturn)})`],
    // Both, and labelled. The record names the bars of its own run date and never changes; the
    // verdict is the same row read against the bars in force now, which is what the page's ticks
    // show. They differ for every row recorded before the owner moved a bar on 2026-10-07.
    ['Luck score when run', t.dsr === null ? 'not measured' : `${fixed(t.dsr, 3)} at N = ${count(t.nTrialsAtRun)}`],
    // Published by the engine (`store.luck_gated`), not worked out here: the luck bar applies to
    // a development try, which is one of many results selected among, and not to a test run,
    // which is a single try booked in advance.
    ['Luck bar applies', t.luckGated ? 'yes' : 'no — a test run has nothing to discount for luck'],
    ['Missed when run', t.failed.length ? t.failed.join('; ') : 'nothing: eligible'],
    ['Missed by today’s bars', t.failedNow.length ? t.failedNow.join('; ') : 'nothing: eligible'],
  ];
}
```
**Impact:** `techRows` gains a row; any test pinning its length or index must move (Step 11).

### Step 11: `view.test.ts` keeps up
**File:** `web/app/sera/methods/view.test.ts:19-32`, and two new cases in the
`marks / workedSummary` block (after `:149`)
**Change:** the base literal carries the field; two cases cover the new state. The existing
headline pins (`cleared 4 of 6`, `cleared all six hurdles`) are unchanged — the base trial is a dev
row, so `applicable` is 6.
**Code — replace the `trial` builder at `:18-32`:**
```ts
/** Mirrors `lib/sera/fixture`: the verdict follows the record unless a test sets it apart. */
const trial = (over: Partial<LabTrial> = {}): LabTrial => {
  const t: LabTrial = {
    n: 58, methodId: 'M0001', candidateId: 'M0001-TV12', rulesId: 'monthly-hold', allocatorId: 'M0001',
    configText: 'rules=TradeRules(...)', window: 'dev', start: '1996-01-03', end: '2015-10-16', gitSha: 'abc1234',
    runAt: '2026-10-04T12:00:00+07:00', totalReturn: 3.276, cagr: 0.076, maxDrawdown: 0.129, profitFactor: 2.27,
    pfInfinite: false, trades: 1130, sharpe: 0.71, exposure: 0.48, turnover: 3.1, worstYear: 2015,
    worstYearReturn: -0.023, spyTrReturn: 3.514, spyTrCagr: 0.079, mar: 0.59,
    failed: ['beats SPY TR', 'DSR >= 0.95'], eligible: false, dsr: 0.899, nTrialsAtRun: 58,
    luckGated: true, failedNow: [], eligibleNow: false, dsrNow: null,
    curve: [['1996-01-31', 1], ['1996-02-29', 1.02], ['1997-01-31', 1.1]],
    ...over,
  };
  return withVerdict(t, over);
};
```
**Code — insert after the "treats a missing luck score as a miss" case (`:149`):**
```ts
  it('calls a test run\'s luck check not applicable, and never missed', () => {
    // M0021-B70-RAW's shape: a test look scoring 0.513 with no luck label in `failedNow`, because
    // a single pre-registered try has nothing to discount. Rendered without the engine's marker,
    // this was a green tick against a published bar of 0.90.
    const look = trial({
      window: 'test', start: '2015-10-19', end: '2026-10-01',
      dsr: 0.513013, dsrNow: 0.513013, failed: ['beats SPY TR'], failedNow: ['beats SPY TR'],
    });
    const dsr = marks(look).find(x => x.key === 'dsr')!;
    expect(dsr.ok).toBe(null);
    expect(markLabel(dsr)).toBe('Luck check: not applicable');
    expect(conditionSentence('dsr', null, look, GATE)).toBe(
      'Luck check: does not apply. A test run is a single try booked in advance, so there is ' +
      'nothing to discount for luck (it scored 0.513).',
    );
    // The number is still annotated, but not with an N it was never scored at.
    expect(dsrNote(look, GATE)).toBe('not a hurdle on a test run');
    expect(dsrNote(trial({ dsrNow: 0.9122 }), GATE)).toBe('at N 110');
    expect(dsrNote(trial({ dsr: null, dsrNow: null }), GATE)).toBe(null);
    // And it is counted out of five, not scored 5 of 6 for a hurdle it never had.
    expect(workedSummary(look, GATE).headline).toBe(
      'Not yet. Its best variant, M0001-TV12, cleared 4 of 5 hurdles on 2015–2026 data.',
    );
  });

  it('records whether the luck bar applied, from the engine and not from the window', () => {
    const rows = Object.fromEntries(techRows(trial()));
    expect(rows['Luck bar applies']).toBe('yes');
    const look = techRows(trial({ window: 'test', failedNow: ['beats SPY TR'] }));
    expect(Object.fromEntries(look)['Luck bar applies']).toBe(
      'no — a test run has nothing to discount for luck',
    );
  });
```
Add `dsrNote` to the import list at `:4-8` (alphabetically between `count` and `fixed`).
**Impact:** none on the app.

### Step 12: the variants table stops printing `at N 126` on an ungated row
**File:** `web/app/sera/methods/[id]/page.tsx:20-24` (import) and `:318-342` (the row)
**Change:** the DSR cell takes its annotation from `dsrNote`.
**Code — replace the import block at `:20-24`:**
```tsx
import {
  BEST_COLOR, conditionTip, count, dsrNote, fixed, growthFmt, growthLines, hurdlePoints, longDate, markLabel, marks,
  pct1, pfText, signed1, SOURCE_ICON, sourceHref, SPY_COLOR, SPY_DASH, techRows, untestedNote, windowText,
  workedSummary, yearPairs, type Mark,
} from '../view';
```
**Code — replace the `<tbody>` body at `:317-343`:**
```tsx
            <tbody>
              {trials.map(t => {
                const note = dsrNote(t, gate);
                return (
                  <tr key={t.n} className={t.n === best.n ? s.bestRow : undefined}>
                    <th scope="row" className={s.variant}>{t.candidateId}</th>
                    <td><span className={s.window} data-window={t.window}>{t.window === 'dev' ? 'Dev' : 'Test'}</span> {windowText(t)}</td>
                    <td className={s.r}>
                      <span className="num">{pct1(t.cagr)}</span>
                      <span className={s.vs}> vs {pct1(t.spyTrCagr)}</span>
                    </td>
                    <td className={`num ${s.r}`}>{signed1(t.totalReturn)}</td>
                    <td className={`num ${s.r}`}>{pct1(t.maxDrawdown)}</td>
                    <td className={`num ${s.r}`}>{pfText(t)}</td>
                    <td className={`num ${s.r}`}>{count(t.trades)}</td>
                    <td className={`num ${s.r}`}>{fixed(t.sharpe, 2)}</td>
                    <td className={`num ${s.r}`}>{fixed(t.mar, 2)}</td>
                    {/* The score at today's N, beside ticks decided at today's N — but only where
                        today's N is the N it was scored at. A test run's DSR is a measurement with
                        no bar beside it, so it is annotated as such rather than as `at N 126`. The
                        run-date pair (t.dsr at t.nTrialsAtRun) is the record and lives in
                        Technical detail. */}
                    <td className={`num ${s.r}`}>
                      {fixed(t.dsrNow, 2)}
                      {note !== null && <span className={s.vs}> {note}</span>}
                    </td>
                    {marks(t).map(x => (
                      <td key={x.key} className={s.c}><MarkIcon mark={x} size={14} /></td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
```
**Impact:** the two test rows in the table render a dashed `CircleDashed` under "Luck check"
(`MarkIcon` at `:175-183` already handles `ok === null` with the `.na` class, defined at
`method.module.css:24,30,46` — no CSS change needed), with the tooltip
"Luck check: not applicable", and `0.51 not a hurdle on a test run` in the DSR column.

### Step 13: the leaderboard does not call a non-hurdle "missed"
**File:** `web/app/sera/methods/page.tsx:172-183` and `web/app/sera/overview.test.ts:41-76`
**Change:** one filter, and the overview fixture's literal.
**Code — replace `Dots` at `:172-183`:**
```tsx
function Dots({ best, passed }: { best: LabTrial; passed: number }) {
  const ms = marks(best);
  // `=== false`, not `!== true`: a hurdle that does not apply to this row was not missed, and
  // listing it under "missed" is the same wrong answer as ticking it, one column over.
  const missed = ms.filter(x => x.ok === false).map(markLabel);
  const tip = missed.length ? missed.join(' · ') : 'Cleared every hurdle';
  return (
    <span className={s.dots} role="img" aria-label={`Cleared ${passed} of 6 hurdles. ${tip}`} data-tip={tip}>
      {ms.map(x => (
        <span key={x.key} className={x.ok === true ? s.dotOn : x.ok === null ? s.dotNa : s.dotOff} />
      ))}
      <span className={`num ${s.dotsN}`}>{passed}/6</span>
    </span>
  );
}
```
**Code — `web/app/sera/overview.test.ts`, in the `trial` factory's object literal, insert
`luckGated: true,` on the line immediately before `failedNow: [],` (`:70-71`):**
```ts
  nTrialsAtRun: n,
  luckGated: true,
  failedNow: [],
```
**Impact:** `bestVariant` prefers dev trials (`derive.ts:189-194`), and every method in the
committed lab with a test look also has dev trials, so no leaderboard row changes today. The
`/6` denominator and `.dotNa` style are unchanged — see Handoffs.

---

## Verification

**Engine build + tests** (from the worktree root; `PYTHONPATH` is required — without it pytest
silently tests the main checkout instead of this branch; never pass `-o addopts`):
```sh
cd /home/miftah/.worktrees/seer/gotrade-fee-rebuild
PYTHONPATH=engine/src PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
  python -m pytest engine/tests -q -n auto
```
Narrow run while iterating:
```sh
PYTHONPATH=engine/src python -m pytest engine/tests/test_lab_snapshot.py -q
```

**Web:**
```sh
cd /home/miftah/.worktrees/seer/gotrade-fee-rebuild/web && npx vitest run && npx tsc --noEmit
```
`web/node_modules` here is **hardlinked** and already set up. Never replace it with a symlink: a
symlink passes vitest and tsc, then kills `next build` with a misleading "filesystem root" error.

**Snapshot regeneration is idempotent** (the guard in `test_the_committed_snapshot_is_the_export_of_the_committed_database`):
```sh
PYTHONPATH=engine/src python3 -m seer_engine lab export-json && git diff --stat -- web/data/lab.json
```
A second run must print nothing.

**Manual check:** `/sera/methods/M0021` and `/sera/methods/M0029`. In "Every variant", the
`M0021-B70-RAW` row must show a **dashed** mark under "Luck check" (tooltip "Luck check: not
applicable") and a DSR cell reading `0.51 not a hurdle on a test run` — not a green tick, and not
`at N 126`. The `Dev` rows above it are unchanged. Open its Technical detail and confirm
`Luck bar applies: no — a test run has nothing to discount for luck`.

**Exit criteria:**
1. `cd web && npx vitest run` reports `0 failed` (today: `1 failed | 9 passed` in `lib/sera/lab.test.ts`).
2. `npx tsc --noEmit` is clean.
3. The engine suite reports `0 failed` for `engine/tests/test_lab_snapshot.py`.
4. `web/data/lab.json` has `"version":4` and exactly 2 trials with `"luckGated":false`, both
   `window: "test"`, both still carrying their `dsrNow`.
5. A test-window row renders "not applicable", not a tick, and prints no `at N 126`.
6. `lab.test.ts` decides the luck branch by reading `t.luckGated`; no file under `web/` re-derives
   the rule from `window` except the one contract pin that exists to say the marker is
   window-shaped.
7. `lab/lab.sqlite` is byte-identical to its state before the phase (`git status` shows it
   unmodified).

## Handoffs

- **Phase 7** owns the next edit to `engine/src/seer_engine/lab/store.py` (`metrics`, the trial
  schema, `owner_failures`) and must quote it as this phase leaves it. The three changes are listed
  verbatim under **Interface Contract → Leaves alone**. **Line numbers below `:1272` shift by about
  +22 once this phase's `luck_gated()` lands** — phase 7's Files table quotes pre-phase-2 numbers
  (`:1294`, `:1386`, `:1564`), so that phase must locate those hunks by symbol, not by line.
- **Phase 7 also owns `engine/tests/test_lab_snapshot.py`'s six `SCHEMA_VERSION` pins** (`:86`,
  `:104`, `:113`, `:180`, `:207`, `:238`) and the new v3 -> v4 migration test. This phase leaves every
  one of them reading `"3"`. See the callout under **Interface Contract → Value changes**: the
  string `"3"` is the sqlite schema version, the int `3` at `:280` is the published snapshot version,
  and only the second is this phase's.
- **Collapsing `published_verdict`'s inline `str(trial["window"]) == "dev"` onto `luck_gated()`**
  is a one-line simplification deliberately **not** made here: the phase scope forbids touching
  `published_verdict`, and `test_the_marker_names_the_same_split_published_verdict_makes` holds the
  two to one rule in the meantime. Not assigned to any phase; raise it as its own card if the
  duplication ever becomes a problem.
- **`Dots`'s `passed/6` denominator** (`web/app/sera/methods/page.tsx:181` and its `aria-label`)
  still says "6" where a test-only method would have five applicable hurdles. No such method exists
  in the committed lab — `bestVariant` prefers dev trials and every method with a test look has
  them — so this is unreachable today and is left rather than chased. It becomes reachable only if
  the lab ever registers a method whose first run is a test look.
- **`conditionTip('dsr', gate)`** (`view.ts:165`) is a column-header tip shared by every row and
  still describes the gated case only. It is correct as a description of the hurdle; it does not
  claim every row has it. Left unchanged deliberately.
- **`overview.ts`'s luck chart** (`:333-358`) already filters `devTrials`, so no test look ever
  reached it. Verified, not changed.
- Nothing here touches `.github/workflows/engine-ci.yml` or `engine/tests/test_lab_npolicy.py`
  (**Phase 1**), `web/app/(app)/*` (**Phase 9**) or `web/lib/sean/*` (**Phase 10**).

## Rollback

One commit on `feature/gotrade-fee-rebuild`; `git revert` it. The phase is independently revertible
and nothing depends on it except Phase 7, which depends on the *file state* of `lab/store.py`, not
on the marker's behaviour — a revert before Phase 7 lands costs nothing, and after it lands the
revert is a three-hunk conflict in `lab/store.py` resolved by keeping Phase 7's hunks.

No data is consumed and nothing is irreversible: `lab/lab.sqlite` is never written, `web/data/lab.json`
is regenerated from it by a single command, and reverting the engine change plus rerunning
`lab export-json` restores the previous snapshot byte for byte (verified today: the committed JSON
is already the exact export of the committed database, 1,111,529 bytes).

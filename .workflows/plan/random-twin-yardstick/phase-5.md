# Phase 5: Snapshot and Sera pages

**Plan set:** `RANDOM_TWIN_YARDSTICK_PLAN.md`
**Analysis:** `.workflows/analyze/20261113-125454-Y7RT_code_analyzer.md`
**Satisfies:** R2 — "Judge ideas against it": the owner can see, in plain words on the method page, whether each arm beat its random look-alikes, and which arms are comparison books rather than candidates
**Criteria:** R2.4
**Depends on:** Phase 4 (and through it 1, 2, 3)
**Difficulty:** NORMAL
**Package:** `web` (plus the snapshot block of `engine/src/seer_engine/lab/store.py`)

---

## Goal

`web/data/lab.json` (snapshot 8) publishes every arm's recorded role and its latest random-twin
reading, plus the bar and draw count in the gate block. The Sera method page shows the random-twin
check as a seventh condition in plain words ("Beats look-alikes", target "beats at least 9 in 10
random look-alike books", reading "beat 187 of 200"), draws an arm with no reading as "not measured
yet" (never as a pass), says the check does not apply to a book that only holds funds, and labels
control arms as comparison books instead of drawing the control label as a failed hurdle.

## Interface Contract

The reconciler reads this section to detect cross-phase conflicts.

**Deletes:** the literal `HURDLES = 6` in `web/app/sera/overview.ts:20` (replaced by `CONDITION_KEYS.length`); the literal `'six'` branch in `workedSummary` (`web/app/sera/methods/view.ts:304`, replaced by a number-word table)
**Renames:** none
**Creates:**
- engine: `store._snapshot_yardstick(row) -> dict | None` (`lab/store.py`, snapshot block); snapshot keys `trials[].role`, `trials[].yardstick` (`{status, percentile, draws, beaten, armRate, medianRate, tradeRatio}` or null), `gate.yardstickMin`, `gate.yardstickDraws`
- engine tests: `test_a_trial_publishes_its_role_and_its_random_twin_reading`, `test_a_lab_without_the_role_and_twin_tables_publishes_nulls` (`test_lab_snapshot.py`); `test_the_web_mirrors_the_engines_random_twin_label`, `test_the_web_mirrors_the_engines_control_label`, `test_the_web_mirrors_the_engines_arm_roles_and_reading_statuses` (`test_lab_gate_wording.py`)
- `web/lib/sera/types.ts`: `ArmRole`, `YardstickStatus`, `LabYardstick`, `ARM_ROLES`, `YARDSTICK_STATUSES`; `LabTrial.role`, `LabTrial.yardstick`; `Gate.yardstickMin`, `Gate.yardstickDraws`
- `web/lib/sera/derive.ts`: `CONDITION_KEYS` gains `'yardstick'`; `YARDSTICK_FAILURE_PREFIX`, `YARDSTICK_FAILURE_SUFFIX`, `isYardstickLabel`, `CONTROL_LABEL`, `isComparisonBook`, `TwinsState`, `twinsState`, `shareInWords`, `twinsValue`, `twinsTarget`
- `web/lib/sera/glossary.ts`: keys `randomTwin`, `twinsBeaten`, `comparisonBook`
- `web/lib/sera/fixture.ts`: `TWINS_MISS`, `CONTROL`, `reading()`, `armStates()`
- `web/app/sera/methods/view.ts`: `Mark.naText`, `Mark.detail`, `twinsSentence`, `twinsRecord`, `roleText`, `techStatus`, `missInWords` (the redone panel's plain words for the two new labels; Decision D15)
**Signature changes:**
- `store._snapshot_trial(t, v, f=None)` -> `store._snapshot_trial(t, v, f=None, role=None, y=None)`
- `store.SNAPSHOT_VERSION = 7` -> `8`; `LabSnapshot.version: 7` -> `8`
- `Worked.lines: { key; ok; text }[]` -> `(Mark & { text: string })[]`
- `derive.bestVariant` and `derive.closest` skip comparison books when the method has another arm
**Requires (from earlier phases):**
- Phase 1: `store.role_of_trial(conn, trial_n) -> str | None` (None when the table or row is absent); `store.CONTROL_LABEL == "not a control arm"`, appended by `store.verdict` to a control arm's `failed`; `store.RoleRow(trial_n, role, source, measured)` and `store.insert_roles(conn, rows)`
- Phase 2: `lab/yardstick.py` with `DRAWS = 200`, `RULE_ID`, `STATUS_MEASURED`, `STATUS_NOT_APPLICABLE`, `STATUS_UNMATCHED`, importable without a database
- Phase 3: `store.yardstick_of(conn, trial_n) -> sqlite3.Row | None` (latest row; None when the table or row is absent) whose columns are named exactly as the `trial_yardstick` table in the index; `store.YardstickRow` with one field per column; `store.insert_yardstick(conn, row) -> bool`, which accepts exactly the shapes phase 2's `Measurement` admits (Decision D11: a not-applicable row is `draws=0, beaten=0, percentile=None, trade_ratio=None, turnover_ratio=None`; a measured or unmatched row has `draws >= 1` and `percentile == beaten / draws`); `store.YARDSTICK_MIN_PERCENTILE = 0.90`; `store.YARDSTICK_LABEL` of the form `"beats <number>% of random twins"`
- Phase 4: `store.verdict` appends `YARDSTICK_LABEL` for a below-bar or `unmatched` reading (and for an unmeasured arm run on or after `YARDSTICK_SINCE`), so `failedNow` already carries it; `published_verdict` never puts it on a test-window row
**Leaves alone (owned by others):** `store.verdict`, `published_verdict`, `runner.py`, `hardgate.py`, `lab/yardstick.py`, `commands/lab.py` (phases 1-4); `lab/lab.sqlite` (nobody commits it); every paper-trading page; the explore, Sera and stale-page skills (phase 4)

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/store.py:3069` (`SNAPSHOT_VERSION`), `:3178` (`_snapshot_trial`), `:3286` (`snapshot`) | modify | version 8 with its reason; new `_snapshot_yardstick`; `role` / `yardstick` per trial; `yardstickMin` / `yardstickDraws` in the gate |
| `engine/tests/test_lab_snapshot.py:136` (`TRIAL_KEYS`), `:670`, `:940` | modify | contract pins move to snapshot 8; two new tests |
| `engine/tests/test_lab_gate_wording.py:203-256` | modify | three new web-mirror pins next to the luck and drawdown ones |
| `web/lib/sera/types.ts:14`, `:20-27`, `:237`, end of file | modify | version 8, gate fields, `role`, `yardstick`, new types and constant lists |
| `web/lib/sera/derive.ts:26-66`, `:121-222`, `:230-268` | modify | seventh condition, label matchers, comparison books, twins helpers |
| `web/lib/sera/glossary.ts:5-23`, `:104-136` | modify | three plain entries; `CONDITION_TERM.yardstick` |
| `web/lib/sera/fixture.ts:4-15`, `:59`, end of file | modify | gate fields, `role` / `yardstick` defaults, the seven arm states |
| `web/lib/sera/lab.ts:17-33` | modify | build-time guard requires the two new gate fields |
| `web/lib/sera/lab.test.ts:7-19`, `:54-66` | modify | version 8; known labels; role and reading shape on the real snapshot |
| `web/lib/sera/derive.test.ts:37-245` | modify | seven-key expectations; new random-twin and comparison-book blocks |
| `web/lib/sera/glossary.test.ts:16-41` | modify | three new keys |
| `web/app/sera/methods/view.ts:1-15`, `:52`, `:207-307`, `:409-433` | modify | marks, sentences, tips, summary, technical record |
| `web/app/sera/methods/view.test.ts:22-35`, `:136-245`, `:297-312` | modify | builder fields; seventh mark; sentences; record rows |
| `web/app/sera/methods/[id]/page.tsx:14`, `:180-198`, `:256`, `:307-316`, `:385`, `:430`, `:512`, `:599` | modify | seventh row in "Did it work?"; comparison-book chip in table and cards; caption; record summary; the redone panel's "Still misses" in plain words |
| `web/app/sera/methods/[id]/method.module.css:56` | modify | `.compare` chip |
| `web/app/sera/methods/page.tsx:8`, `:61`, `:195`, `:259-271` | modify | seven dots, `n/7`, caption |
| `web/app/sera/how/view.ts:11`, `:116-129`, `:211-244` | modify | pipeline stage "Seven hurdles"; seventh hurdle card |
| `web/app/sera/how/view.test.ts:58-77`, `:111-122` | modify | stage and hurdle expectations |
| `web/app/sera/how/page.tsx:87-89` | modify | "Seven things every method must clear" |
| `web/app/sera/overview.ts:5-20`, `:276` | modify | `HURDLES` from `CONDITION_KEYS`; the twins bar's tip wording |
| `web/app/sera/overview.test.ts:42-80`, `:101-115`, `:285-307` | modify | builder fields; version 8; seven bars; 0-7 ticks |
| `web/components/sera/diagrams/geometry.ts:10` | modify | comment: six detail lines fit under a one-line title |
| `web/data/lab.json` | regenerate | derived: the read-only export of the worktree's unmodified `lab/lab.sqlite` |
| `.claude/skills/verify-seer/features/sera.md` | modify | the seventh condition and comparison books, and how to drive them |

## Implementation Steps

Line numbers are today's. Phases 1-4 add code to `store.py` above the snapshot block, so locate
`SNAPSHOT_VERSION`, `_snapshot_trial` and `snapshot` by name. The web files are untouched by
phases 1-4, so their line numbers hold.

Order matters: the engine steps (1-5) come first, then the regeneration (step 6), because
`web/lib/sera/lab.test.ts` reads the committed `web/data/lab.json` and fails on a version 7 file.

### Step 1: Snapshot 8, and why
**File:** `engine/src/seer_engine/lab/store.py:3069` (the line `SNAPSHOT_VERSION = 7`, after the "# 7 adds ``books``" comment paragraph)
**Change:** append a paragraph for 8 to the version comment and bump the constant.
**Code:** replace the single line `SNAPSHOT_VERSION = 7` with:
```python
#
# 8 adds each trial's ``role`` and ``yardstick``, and ``gate.yardstickMin`` / ``gate.yardstickDraws``.
# On 2026-11-14 the lab grew a seventh screen condition: a dev arm must out-earn
# ``YARDSTICK_MIN_PERCENTILE`` of its random twins, books that replay its own decisions with every
# picked name swapped for a random index member of similar trading size. It also started recording
# which arms are controls. ``failedNow`` already carries both answers as labels (``verdict``), but a
# label is a verdict and not a reading: from it alone the page could say "missed" and not "beat 150
# of 200", and it could not tell an arm nobody has measured from one that cleared -- the one
# confusion the method page must never make. Both fields are null when their table is absent or
# holds no row for the trial, which was every trial the committed lab held when this version shipped.
SNAPSHOT_VERSION = 8
```
**Impact:** every pin of `7` moves (steps 4, 7, 9, 13).

### Step 2: `_snapshot_yardstick` and the two new trial fields
**File:** `engine/src/seer_engine/lab/store.py:3178` (`_snapshot_trial`)
**Change:** add `_snapshot_yardstick` directly above `_snapshot_trial`, and replace `_snapshot_trial` whole.
**Code:**
```python
def _snapshot_yardstick(y: Mapping[str, Any] | sqlite3.Row | None) -> dict[str, Any] | None:
    """One ``trial_yardstick`` row as the web reads it, or None when the trial has none.

    A reading, not a verdict. Whether the arm clears is decided once, by ``verdict``, and reaches
    the web as the label in ``failedNow``; this is the measurement that sentence is about, so the
    page can say *how* it went ("beat 187 of 200") and not only *that* it went. ``medianRate`` is
    the middle twin's rate, worked out here from ``rates_json`` so the web never parses a list it
    only wants one number from. ``rates_json`` itself stays out: 200 floats per arm across the
    whole lab is weight the page has no use for.

    ``_num`` and ``_opt_int`` keep the published shape strict JSON: a not-applicable reading has
    no draws to rank against, and its null ``percentile`` must stay null rather than become NaN,
    which ``snapshot_json`` refuses. Its ``beaten`` is stored as 0 (the table mirrors
    ``yardstick.Measurement``, plan Decision D11) and is **published as null**: "beat 0 of 0" is
    not a reading, and the page tells "does not apply" from a result by ``status`` and a null.
    """
    if y is None:
        return None
    from statistics import median

    status = str(y["status"])
    raw = y["rates_json"]
    rates = [
        float(r) for r in (json.loads(raw) if raw else [])
        if r is not None and math.isfinite(float(r))
    ]
    return {
        "status": status,
        "percentile": _num(y["percentile"]),
        "draws": _opt_int(y["draws"]),
        "beaten": None if status == "not-applicable" else _opt_int(y["beaten"]),
        "armRate": _num(y["arm_rate"]),
        "medianRate": _num(median(rates)) if rates else None,
        "tradeRatio": _num(y["trade_ratio"]),
    }


def _snapshot_trial(
    t: Mapping[str, Any],
    v: Verdict,
    f: Mapping[str, Any] | sqlite3.Row | None = None,
    role: str | None = None,
    y: Mapping[str, Any] | sqlite3.Row | None = None,
) -> dict[str, Any]:
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

    ``f`` is this trial's :func:`funding_of` row, or None when it received no deposits -- the
    normal answer for all 128 recorded trials. It publishes ``mwr`` and ``spyTrMwr``, and they are
    the reason this row cannot be read off ``totalReturn`` alone once the book is fed: with money
    going in after the start, ``total_return`` counts the owner's own deposits as gains (10.7821
    beside an ``mwr`` of 0.0764 on one measured run). Both are published or neither is, because the
    comparison ``beats SPY TR`` is decided on for such a row is the **pair** -- ``dev.beats_spy_tr``
    falls back to the total-return comparison the moment either is missing, so a consumer that
    showed one alone would contradict the verdict beside it.

    ``luckGated`` says whether the luck hurdle applies to this row at all (:func:`luck_gated`).
    Without it the verdict is ambiguous in exactly one place: a test look's ``failedNow`` omits
    the luck label because the gate does not apply, and a reader with only ``failedNow`` to go on
    cannot tell that from a hurdle that was cleared. It published a tick on 0.513013 against a
    bar of 0.90. **Three states, not two**: gated and cleared, gated and missed (``dsrNow`` may be
    null -- nothing is admitted for being unmeasurable), and not gated at all.

    ``role`` is :func:`role_of_trial` and ``y`` is :func:`yardstick_of` (snapshot 8). The random-
    twin condition has the same trap ``luckGated`` closed, one condition over: an arm nobody has
    measured has no label in ``failedNow``, and neither has one that cleared. ``yardstick`` is what
    tells them apart, so it is published whole or as null, and null means "not measured" -- never
    a pass. ``role`` lets the page show a control arm as the comparison book it was registered as,
    instead of an idea that failed a seventh hurdle.
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
        # What the money actually earned on a funded run, and what the same deposits put into SPY
        # TR earned. Null together for an unfunded trial, which is every recorded one.
        "mwr": None if f is None else _num(f["mwr"]),
        "spyTrMwr": None if f is None else _num(f["spy_tr_mwr"]),
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
        # Snapshot 8: the arm's registered role and its latest random-twin reading, or null.
        "role": role,
        "yardstick": _snapshot_yardstick(y),
        "curve": _snapshot_curve(t["curve_json"]),
    }
```
**Impact:** key order of every trial in `web/data/lab.json` changes (two keys before `curve`); regenerated in step 6.

### Step 3: Publish the gate fields and pass the two helpers' answers
**File:** `engine/src/seer_engine/lab/store.py:3286` (`snapshot`)
**Change:** three edits inside `snapshot`.

(a) In the docstring, replace the sentence
```python
    a database that has not been migrated -- the one table added since, ``trial_funding``, is
    reached only through ``funding_of``, which answers None when it does not exist. Gate and data
```
with
```python
    a database that has not been migrated -- the tables added since, ``trial_funding``,
    ``trial_roles`` and ``trial_yardstick``, are reached only through ``funding_of``,
    ``role_of_trial`` and ``yardstick_of``, each of which answers None when its table does not
    exist. Gate and data
```

(b) Replace the import block at the top of the body
```python
    from seer_engine import dates, research
    from seer_engine.backtest import dev, tuning
    from seer_engine.lab import seed
    from seer_engine.paper import roster
```
with
```python
    from seer_engine import dates, research
    from seer_engine.backtest import dev, tuning
    from seer_engine.lab import seed
    from seer_engine.lab import yardstick as _yardstick
    from seer_engine.paper import roster
```
and replace the gate block
```python
            "dsrMin": DSR_MIN,
            **gate_block,
            "devStart": research.STORE_START.isoformat(),
```
with
```python
            "dsrMin": DSR_MIN,
            **gate_block,
            # Snapshot 8: the random-twin bar and how many twins it is read against. Published, not
            # retyped in the web, for the reason ``dsrMin`` is: the owner moves bars.
            "yardstickMin": YARDSTICK_MIN_PERCENTILE,
            "yardstickDraws": _yardstick.DRAWS,
            "devStart": research.STORE_START.isoformat(),
```

(c) Replace the trials comprehension
```python
        "trials": [
            _snapshot_trial(t, published_verdict(conn, t, at=g), funding_of(conn, t["n"]))
            for t in _dicts(conn, "SELECT * FROM trials ORDER BY n")
        ],
```
with
```python
        "trials": [
            _snapshot_trial(
                t,
                published_verdict(conn, t, at=g),
                funding_of(conn, t["n"]),
                role_of_trial(conn, t["n"]),
                yardstick_of(conn, t["n"]),
            )
            for t in _dicts(conn, "SELECT * FROM trials ORDER BY n")
        ],
```
**Impact:** none on a database without the new tables (both helpers answer None). `failedNow` is untouched: phases 1 and 4 already put the control and twin labels in `verdict`, and this step does not re-derive them.

### Step 4: Engine snapshot tests
**File:** `engine/tests/test_lab_snapshot.py`
**Change:** (a) imports, (b) `TRIAL_KEYS`, (c) the v6 pin, (d) the contract test, (e) two new tests at the end of the file.

(a) After `from seer_engine.lab import store` (line 22) add:
```python
from seer_engine.lab import yardstick as yardstick_mod
```

(b) Replace `TRIAL_KEYS` (line 136-140) with:
```python
TRIAL_KEYS = {"n", "methodId", "candidateId", "rulesId", "allocatorId", "configText", "window", "start", "end",
              "gitSha", "runAt", "totalReturn", "cagr", "maxDrawdown", "profitFactor", "pfInfinite", "trades",
              "sharpe", "exposure", "turnover", "worstYear", "worstYearReturn", "spyTrReturn", "spyTrCagr", "mar",
              "failed", "eligible", "dsr", "nTrialsAtRun", "luckGated", "failedNow", "eligibleNow", "dsrNow",
              "mwr", "spyTrMwr", "role", "yardstick", "curve"}
```

(c) In `test_the_v6_to_v7_migration_moves_not_one_byte_of_the_web_snapshot` (line 670) replace
`    assert store.SNAPSHOT_VERSION == 7` with:
```python
    # 7 when this was written; 8 since the random-twin fields (an additive change to the trials,
    # not to this migration). The claim above is about the migration, and still holds.
    assert store.SNAPSHOT_VERSION == 8
```

(d) In `test_the_snapshot_follows_the_contract` (line 940): replace `    assert s["version"] == 7` with `    assert s["version"] == 8`; replace the gate key list
```python
    assert list(gate) == [
        "maxDrawdown", "minProfitFactor", "minTrades", "dsrMin",
        "dsrPolicy", "dsrN", "dsrNBasis", "devStart", "devEnd", "testStart",
    ]
```
with
```python
    assert list(gate) == [
        "maxDrawdown", "minProfitFactor", "minTrades", "dsrMin",
        "dsrPolicy", "dsrN", "dsrNBasis", "yardstickMin", "yardstickDraws",
        "devStart", "devEnd", "testStart",
    ]
    # The random-twin bar is the owner's too: published from the constants, never pinned here.
    assert gate["yardstickMin"] == store.YARDSTICK_MIN_PERCENTILE
    assert gate["yardstickDraws"] == yardstick_mod.DRAWS
```
and inside the `for t in s["trials"]:` loop, after `assert t["mwr"] is None and t["spyTrMwr"] is None`, add:
```python
        # No role and no random-twin reading is recorded in this fixture, which was the state of
        # the committed lab when snapshot 8 shipped: both null, and null means "not recorded".
        assert t["role"] is None and t["yardstick"] is None
```

(e) Append:
```python
def _twin_row(trial_n: int, **over):
    """A ``trial_yardstick`` row: 200 twins earning 0.000..0.199, an arm earning 0.187.

    Ties count against the arm (decision D7), so 0.187 beats the 187 twins below it and not the
    one equal to it: 187 of 200, 0.935. The middle twin earns (0.099 + 0.100) / 2.
    """
    row = dict(
        trial_n=trial_n, rule_id=yardstick_mod.RULE_ID, store_fingerprint="fp",
        status=yardstick_mod.STATUS_MEASURED, draws=200, arm_rate=0.187, beaten=187,
        percentile=0.935, rates_json=json.dumps([i / 1000 for i in range(200)]),
        trade_ratio=1.04, turnover_ratio=0.98, reproduced=1, git_sha="abc",
        measured="2026-11-14T00:00:00+00:00",
    )
    row.update(over)
    return store.YardstickRow(**row)


def test_a_trial_publishes_its_role_and_its_random_twin_reading(lab):
    """Snapshot 8: the record of what an arm *is* and how it did against its random twins.

    The verdict already says whether it clears (phase 4 puts the label in ``failedNow``); this is
    the reading behind that sentence, and the one field that tells "nobody measured it" from
    "it cleared" -- both of which leave ``failedNow`` without the label.
    """
    first = store.snapshot(lab)
    assert all(t["role"] is None and t["yardstick"] is None for t in first["trials"])
    with lab:
        store.insert_roles(lab, [
            store.RoleRow(trial_n=53, role="control", source="backfill",
                          measured="2026-11-14T00:00:00+00:00"),
            store.RoleRow(trial_n=55, role="treatment", source="backfill",
                          measured="2026-11-14T00:00:00+00:00"),
        ])
        assert store.insert_yardstick(lab, _twin_row(55))
        assert store.insert_yardstick(lab, _twin_row(
            54, store_fingerprint=seed_mod.P7A_FINGERPRINT,
            status=yardstick_mod.STATUS_NOT_APPLICABLE, draws=0, beaten=0, percentile=None,
            rates_json="[]", trade_ratio=None, turnover_ratio=None,
        ))
    trials = {t["n"]: t for t in store.snapshot(lab)["trials"]}
    assert trials[55]["role"] == "treatment"
    assert trials[55]["yardstick"] == {
        "status": "measured", "percentile": 0.935, "draws": 200, "beaten": 187,
        "armRate": 0.187, "medianRate": 0.0995, "tradeRatio": 1.04,
    }
    # Not applicable: nothing was drawn, so nothing is ranked -- nulls, never NaN. The row stores
    # beaten = 0 (Decision D11); the snapshot publishes it as null.
    assert trials[54]["role"] is None
    assert trials[54]["yardstick"] == {
        "status": "not-applicable", "percentile": None, "draws": 0, "beaten": None,
        "armRate": 0.187, "medianRate": None, "tradeRatio": None,
    }
    # A control: its role is published, and the verdict beside it is the engine's (phase 1's
    # label), not something this export derived.
    assert trials[53]["role"] == "control" and trials[53]["yardstick"] is None
    assert store.CONTROL_LABEL in trials[53]["failedNow"]
    assert all(t["role"] is None and t["yardstick"] is None for n, t in trials.items() if n < 53)
    json.loads(store.snapshot_json(lab))  # still strict JSON


def test_a_lab_without_the_role_and_twin_tables_publishes_nulls(lab, tmp_path):
    """``snapshot`` answers on a read-only connection to a lab that predates both tables.

    Every parallel Sera session runs an older checkout against the shared database, and the
    committed ``lab/lab.sqlite`` itself has neither table until the backfill runs on ``main``. The
    two helpers answer None when their table is absent, so the export is nulls -- never an error.
    """
    old = tmp_path / "old.sqlite"
    dst = sqlite3.connect(old)
    lab.backup(dst)
    dst.execute("DROP TABLE trial_roles")
    dst.execute("DROP TABLE trial_yardstick")
    dst.commit()
    dst.close()
    ro = store.connect_readonly(old)
    try:
        names = {r[0] for r in ro.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        assert "trial_roles" not in names and "trial_yardstick" not in names
        trials = store.snapshot(ro)["trials"]
    finally:
        ro.close()
    assert len(trials) == 55
    assert all(t["role"] is None and t["yardstick"] is None for t in trials)
```
**Impact:** the contract test now fails if a later phase drops either field or the gate pair.

### Step 5: Pin every web mirror of an engine value
**File:** `engine/tests/test_lab_gate_wording.py`, after `test_the_web_mirrors_the_engines_luck_label_prefix` (ends ~line 256)
**Change:** three new tests, modelled on the two drawdown and luck prefix pins already there.
**Code:**
```python
_WEB_TWINS_PREFIX = re.compile(r"YARDSTICK_FAILURE_PREFIX\s*=\s*'([^']*)'")
_WEB_TWINS_SUFFIX = re.compile(r"YARDSTICK_FAILURE_SUFFIX\s*=\s*'([^']*)'")
_WEB_CONTROL = re.compile(r"CONTROL_LABEL\s*=\s*'([^']*)'")


def _derive_ts() -> str:
    return (config.REPO_ROOT / "web" / "lib" / "sera" / "derive.ts").read_text(encoding="utf-8")


def _ts_string_list(src: str, name: str, rel: str) -> set[str]:
    m = re.search(rf"export const {name}\s*=\s*\[([^\]]*)\]", src)
    assert m is not None, f"{rel}: could not find `export const {name} = [...]`; fix this parse"
    items = set(re.findall(r"'([^']+)'", m.group(1)))
    assert items, f"{rel}: `{name}` parsed empty; fix this parse"
    return items


def test_the_web_mirrors_the_engines_random_twin_label() -> None:
    """The random-twin label carries its bar in the middle, so the site matches both ends.

    ``beats `` alone would also match ``beats SPY TR``, so ``derive.ts`` requires the fixed start,
    the fixed end and a number between them. This pins both ends to ``store.YARDSTICK_LABEL`` and
    the number to ``YARDSTICK_MIN_PERCENTILE``: if either drifts, a missed random-twin check renders
    as a tick on the owner's page.
    """
    src = _derive_ts()
    p, s = _WEB_TWINS_PREFIX.search(src), _WEB_TWINS_SUFFIX.search(src)
    assert p is not None and s is not None, (
        "web/lib/sera/derive.ts no longer defines YARDSTICK_FAILURE_PREFIX and "
        "YARDSTICK_FAILURE_SUFFIX as single-quoted literals; say how the site reads the label now"
    )
    prefix, suffix = p.group(1), s.group(1)
    label = store.YARDSTICK_LABEL
    assert prefix and suffix
    assert label.startswith(prefix) and label.endswith(suffix), (
        f"the engine writes {label!r}, but the site looks for {prefix!r}...{suffix!r}"
    )
    bar = label[len(prefix):len(label) - len(suffix)]
    assert re.fullmatch(r"\d+(?:\.\d+)?", bar), f"the bar inside {label!r} is not a number"
    assert float(bar) == pytest.approx(store.YARDSTICK_MIN_PERCENTILE * 100)
    # The SPY label shares the start and must not be read as a random-twin miss.
    assert not "beats SPY TR".endswith(suffix)


def test_the_web_mirrors_the_engines_control_label() -> None:
    """``derive.ts`` recognises a control arm by the label phase 1 writes into its verdict."""
    m = _WEB_CONTROL.search(_derive_ts())
    assert m is not None, "web/lib/sera/derive.ts no longer defines CONTROL_LABEL as a literal"
    assert m.group(1) == store.CONTROL_LABEL, (
        f"the engine writes {store.CONTROL_LABEL!r} for a control arm, but the site looks for "
        f"{m.group(1)!r}: every control would read as an unknown failure"
    )


def test_the_web_mirrors_the_engines_arm_roles_and_reading_statuses() -> None:
    """The two closed vocabularies snapshot 8 publishes, as typed in ``web/lib/sera/types.ts``."""
    from seer_engine.lab import control_shape, yardstick

    rel = "web/lib/sera/types.ts"
    src = (config.REPO_ROOT / rel).read_text(encoding="utf-8")
    assert _ts_string_list(src, "ARM_ROLES", rel) == set(control_shape.ROLES)
    assert _ts_string_list(src, "YARDSTICK_STATUSES", rel) == {
        yardstick.STATUS_MEASURED, yardstick.STATUS_NOT_APPLICABLE, yardstick.STATUS_UNMATCHED,
    }
```
**Impact:** red until steps 8-9 land the web constants; run it after step 9.

### Step 6: Regenerate `web/data/lab.json` without touching `lab/lab.sqlite`
**File:** `web/data/lab.json` (derived)
**Change:** export the worktree's committed database read-only with the new snapshot code. Do **not** use `lab stage` (it git-adds `lab.sqlite`) or `lab export-json` (it opens the database with `store.connect`, which migrates and can dirty the file).
**Code:**
```sh
cd /home/miftah/.worktrees/seer/random-twin-yardstick
engine/.venv/bin/python - <<'EOF'
from pathlib import Path
from seer_engine.lab import store

db = Path("lab/lab.sqlite").resolve()
conn = store.connect_readonly(db)
try:
    print("written" if store.write_snapshot(conn, store.snapshot_path(db)) else "unchanged")
finally:
    conn.close()
EOF
git status --short lab/lab.sqlite   # must print nothing; if it does: git checkout -- lab/lab.sqlite
```
**Impact:** every trial gains `"role":null,"yardstick":null` (the committed lab has neither table), the gate gains the pair, `version` reads 8. This file is derived: the integrator regenerates it at merge from the merged `lab/lab.sqlite` instead of merging it, and `lab stage` on `main` rewrites it on the next lab commit.

### Step 7: Types
**File:** `web/lib/sera/types.ts`
**Change:** (a) version doc and literal (line 4-14), (b) gate fields after `dsrNBasis` (line 27), (c) `role` / `yardstick` after `luckGated` (line 237), (d) new types and lists at the end of the file.

(a) Replace lines 4-14 (`/** 2 added ... */ version: 7;`) with:
```ts
  /**
   * 2 added the derived verdict to every trial (`failedNow` / `eligibleNow` / `dsrNow`);
   * 3 added `paper`, which names the lab method behind each roster entry;
   * 4 added `luckGated`, which says whether the luck hurdle applies to a trial at all;
   * 5 added `mwr` / `spyTrMwr`, what a funded trial's money actually earned;
   * 6 added the journal's version chain (`supersedes` / `docKey` / `version` / `supersededBy`)
   *   and split the journal count: `summary.insights` now counts documents, not rows;
   * 7 added `books` and `summary.testBooks` — the buy signal and the spent looks collapsed from
   *   method ids to distinct strategies, because a method id is not a strategy;
   * 8 added each trial's `role` and `yardstick` (its random-twin reading) and the gate's
   *   `yardstickMin` / `yardstickDraws` — the seventh condition, and which arms are comparison books.
   */
  version: 8;
```
(b) After the `dsrNBasis: string;` line inside `gate`, add:
```ts
    /** The random-twin bar (`lab.store.YARDSTICK_MIN_PERCENTILE`): the share of look-alikes a dev arm must out-earn. */
    yardstickMin: number;
    /** How many random look-alike books each arm is measured against (`lab.yardstick.DRAWS`). */
    yardstickDraws: number;
```
(c) After `luckGated: boolean;` inside `LabTrial`, add:
```ts
  /**
   * The arm's registered role (`lab.store.role_of_trial`), or null when none is recorded — every
   * arm the committed lab held when snapshot 8 shipped. `control` is a comparison book: built to be
   * beaten, never a candidate. Read it through `derive.isComparisonBook`, which also honours the
   * engine's own label for a control.
   */
  role: ArmRole | null;
  /**
   * The arm's latest random-twin reading (`lab.store.yardstick_of`), or null when it has none.
   * A reading is a measurement, not a verdict: whether the arm clears is the engine's call, made in
   * `failedNow`, and `derive.twinsState` is the one place the two are combined. Null is "not
   * measured", never a pass.
   */
  yardstick: LabYardstick | null;
```
(d) Append at the end of the file:
```ts
/** An arm's registered role (`lab.control_shape.ROLES`). `control` is a comparison book. */
export type ArmRole = 'control' | 'dose' | 'idea' | 'treatment';

/** How a random-twin measurement came out (`lab.yardstick.STATUS_*`). */
export type YardstickStatus = 'measured' | 'not-applicable' | 'unmatched';

/** One random-twin reading as the engine publishes it (`store._snapshot_yardstick`). */
export type LabYardstick = {
  status: YardstickStatus;
  /** Share of the look-alikes the arm out-earned (ties count against it); null when none were drawn. */
  percentile: number | null;
  /** How many look-alikes were drawn: 0 or null for a book that only holds funds. */
  draws: number | null;
  /** How many of them the arm out-earned. */
  beaten: number | null;
  /** The arm's own rate: what the money earned on a funded run, yearly growth otherwise. */
  armRate: number | null;
  /** The middle look-alike's rate, on the same measure. */
  medianRate: number | null;
  /** The look-alikes' median trade count over the arm's own. */
  tradeRatio: number | null;
};

/** Mirrors `lab.control_shape.ROLES`; `engine/tests/test_lab_gate_wording.py` pins the two. */
export const ARM_ROLES = ['control', 'dose', 'idea', 'treatment'] as const satisfies readonly ArmRole[];

/** Mirrors `lab.yardstick.STATUS_*`; pinned by the same engine test. */
export const YARDSTICK_STATUSES = ['measured', 'not-applicable', 'unmatched'] as const satisfies readonly YardstickStatus[];
```

### Step 8: The seventh condition in `derive.ts`
**File:** `web/lib/sera/derive.ts`
**Change:** six edits.

(a) In the module docstring (line 1-22), before the closing ` */`, add:
```ts
 *
 * The seventh hurdle, the random-twin check, has the same trap one condition over: an arm nobody
 * has measured carries no label in `failedNow`, and neither does one that cleared. So it is read
 * off the engine's published reading, `trial.yardstick`, through `twinsState`, and an arm with no
 * reading is "not measured yet" — never a tick. A control arm is a third kind of thing again: the
 * engine refuses it with a label that is not a condition, and the page shows it as a comparison
 * book rather than as an idea that failed.
```

(b) Replace lines 26-66 (from `export const CONDITION_KEYS` through the closing `};` of `CONDITION_LABEL`) with:
```ts
export const CONDITION_KEYS = ['spy', 'drawdown', 'pf', 'trades', 'owner', 'dsr', 'yardstick'] as const;
export type ConditionKey = (typeof CONDITION_KEYS)[number];

/**
 * The engine's label for each condition, exactly as it appears in a failure list.
 *
 * Three are matched by shape instead (`DSR_FAILURE_PREFIX`, `DRAWDOWN_FAILURE_PREFIX`,
 * `isYardstickLabel`), because each carries its bar inside its own text. `failedNow` always names
 * today's bar, so an exact match would work there — but `failed` does not, the two lists are read
 * by the same helpers, and a shape match cannot go stale the next time the owner moves a bar.
 */
export const FAILURE_LABEL: Record<Exclude<ConditionKey, 'dsr' | 'drawdown' | 'yardstick'>, string> = {
  spy: 'beats SPY TR',
  pf: 'PF >= 1.3',
  trades: '>= 100 trades',
  owner: 'owner inputs',
};

/**
 * The two labels that carry a threshold in their own text, and so must be matched by prefix.
 *
 * `trials` is append-only, so the *record* (`failed`) on a row judged before 2026-10-07 carries
 * `DSR >= 0.95` and `max DD <= 15%` for ever; the *verdict* (`failedNow`) always carries today's
 * `DSR >= 0.90` and `max DD <= 20%`. Matching either literal would render the other as a
 * **pass**, which is the worst failure this page has: a missed hurdle shown as a green tick.
 *
 * These mirror `store.LUCK_LABEL_PREFIX` and the live `dev.FAILURE_LABELS` drawdown entry; the
 * engine-side pins in Steps 9 and 14 are what keep the mirror honest.
 */
export const DSR_FAILURE_PREFIX = 'DSR >= ';
export const DRAWDOWN_FAILURE_PREFIX = 'max DD <= ';

/**
 * The random-twin label (`store.YARDSTICK_LABEL`, "beats 90% of random twins"), matched by its two
 * fixed ends with a number between them.
 *
 * Its bar sits in the middle of the text, so a prefix alone cannot do what it does for the luck
 * and drawdown labels: `beats ` is also how `beats SPY TR` begins. Both ends plus a number is the
 * narrowest shape that still reads the label after the owner moves the bar.
 * `engine/tests/test_lab_gate_wording.py` pins both ends, and the number, to the engine.
 */
export const YARDSTICK_FAILURE_PREFIX = 'beats ';
export const YARDSTICK_FAILURE_SUFFIX = '% of random twins';

export function isYardstickLabel(label: string): boolean {
  if (!label.startsWith(YARDSTICK_FAILURE_PREFIX) || !label.endsWith(YARDSTICK_FAILURE_SUFFIX)) return false;
  const bar = label.slice(YARDSTICK_FAILURE_PREFIX.length, label.length - YARDSTICK_FAILURE_SUFFIX.length);
  return /^\d+(\.\d+)?$/.test(bar);
}

/**
 * What the engine adds to a control arm's verdict (`store.CONTROL_LABEL`).
 *
 * It is not a condition and is never drawn as a seventh crossed hurdle. A control arm is a book
 * the lab built to be beaten, so the idea beside it has something fair to be measured against;
 * its not becoming a candidate is the design working, not an idea failing. The page presents it
 * as a comparison book instead (`isComparisonBook`). Pinned by `engine/tests/test_lab_gate_wording.py`.
 */
export const CONTROL_LABEL = 'not a control arm';

/** Is this arm a comparison book rather than a candidate? Its recorded role, or the engine's own label. */
export function isComparisonBook(trial: LabTrial): boolean {
  return trial.role === 'control' || trial.failedNow.includes(CONTROL_LABEL);
}

/** Plain-language name of each condition. */
export const CONDITION_LABEL: Record<ConditionKey, string> = {
  spy: 'Beats SPY',
  drawdown: 'Max drawdown',
  pf: 'Profit factor',
  trades: 'Trade count',
  owner: 'Owner inputs',
  dsr: 'Luck check',
  yardstick: 'Beats look-alikes',
};
```

(c) After `moneyWeighted` (ends line 119), insert:
```ts
/**
 * Where an arm stands on the random-twin check, read off the engine and never re-judged.
 *
 * - `cleared`: a measured reading, and the engine lists no random-twin miss.
 * - `missed`: the engine lists the miss. With a reading, the arm was below the bar; without one,
 *   it was run after the check began and nobody measured it, which the engine fails closed.
 * - `unmatched`: the look-alikes ended up trading too differently to be a fair comparison. Never
 *   a pass, whatever the engine's list says.
 * - `not-applicable`: the book only holds funds, so there are no picked stocks to swap.
 * - `not-measured`: no reading and no miss — every arm the lab held when the check began.
 *   Neither a pass nor a miss, and never drawn as either.
 * - `test-look`: a test-window run. The check is a development-stage hurdle.
 */
export type TwinsState = 'cleared' | 'missed' | 'unmatched' | 'not-applicable' | 'not-measured' | 'test-look';

export function twinsState(trial: LabTrial): TwinsState {
  const y = trial.yardstick;
  if (trial.failedNow.some(isYardstickLabel)) return y?.status === 'unmatched' ? 'unmatched' : 'missed';
  if (trial.window !== 'dev') return 'test-look';
  if (y === null) return 'not-measured';
  if (y.status === 'not-applicable') return 'not-applicable';
  if (y.status === 'unmatched') return 'unmatched';
  return 'cleared';
}

/**
 * A share in words, as "N in D" with the smallest of 10, 20, 100 or 1000 that makes N whole:
 * 0.9 -> "9 in 10", 0.95 -> "19 in 20". The owner reads "9 in 10" without a percent sign to parse.
 */
export function shareInWords(share: number): string {
  for (const d of [10, 20, 100, 1000]) {
    const k = share * d;
    if (Math.abs(k - Math.round(k)) < 1e-9) return `${Math.round(k)} in ${d}`;
  }
  return `${Math.round(share * 1000)} in 1000`;
}

/** The reading as printed beside its mark: "beat 187 of 200", or why there is none. */
export function twinsValue(trial: LabTrial): string {
  const y = trial.yardstick;
  const beat = y !== null && y.beaten !== null && y.draws !== null ? `beat ${y.beaten} of ${y.draws}` : null;
  switch (twinsState(trial)) {
    case 'cleared':
      return beat ?? 'cleared';
    case 'missed':
      return beat ?? 'not measured';
    case 'unmatched':
      return 'look-alikes traded too differently to compare';
    case 'not-applicable':
    case 'test-look':
      return 'does not apply';
    case 'not-measured':
      return 'not measured yet';
  }
}

/** What the arm had to do, in words, with the bar read from the snapshot's gate. */
export function twinsTarget(trial: LabTrial, gate: Gate): string {
  switch (twinsState(trial)) {
    case 'test-look':
      return 'does not apply to a test look';
    case 'not-applicable':
      return 'does not apply to a book that only holds funds';
    default:
      return `beats at least ${shareInWords(gate.yardstickMin)} random look-alike books`;
  }
}
```

(d) Replace `conditionOk` (lines 121-141, docstring included) with:
```ts
/**
 * Does this trial clear `key` **as the bars read now**? true = cleared, false = missed,
 * null = there is no hurdle to score here.
 *
 * Reads `failedNow`, `luckGated` and `yardstick`, never `failed`. The engine decided all seven
 * there (`store.published_verdict`) against the same gate the snapshot publishes, and said which
 * rows the luck hurdle applies to (`store.luck_gated`), so this is a lookup, not a judgement —
 * which is what keeps a tick and the target printed beside it from describing two different days.
 *
 * `null` is "not applicable" for the luck check (a test look) and for the random-twin check (a
 * test look, or a book that only holds funds), and — for the random-twin check only — "not
 * measured yet". It is never a pass: every count here counts only `true`. A gated row whose DSR
 * could not be scored still comes back `false`: the engine puts the luck label in `failedNow` for
 * exactly those rows, because nothing is admitted for being unmeasurable (its D11).
 */
export function conditionOk(trial: LabTrial, key: ConditionKey): boolean | null {
  if (key === 'yardstick') {
    const state = twinsState(trial);
    if (state === 'cleared') return true;
    if (state === 'missed' || state === 'unmatched') return false;
    return null;
  }
  if (key === 'dsr') {
    if (!trial.luckGated) return null;
    return !trial.failedNow.some((f) => f.startsWith(DSR_FAILURE_PREFIX));
  }
  if (key === 'drawdown') return !trial.failedNow.some((f) => f.startsWith(DRAWDOWN_FAILURE_PREFIX));
  return !trial.failedNow.includes(FAILURE_LABEL[key]);
}
```

(e) In `gateChecks` (line 143-208): change its docstring to `/** The seven hurdles for one trial, in display order, with plain labels and display strings. */` and, after the `dsr` entry's closing `},` (line 206), add:
```ts
    {
      key: 'yardstick',
      label: CONDITION_LABEL.yardstick,
      value: twinsValue(trial),
      target: twinsTarget(trial, gate),
      ok: conditionOk(trial, 'yardstick'),
    },
```
and replace the `conditionsPassed` docstring (lines 210-214) with:
```ts
/**
 * How many of the seven hurdles the trial cleared. Not-measured luck counts as not cleared (the
 * engine already listed it as a failure); a hurdle that does not apply, or a random-twin check
 * nobody has run yet, counts as neither cleared nor missed, so a test look reads 4 of 5.
 */
```

(f) Replace `closest`, `bestVariant` and `funnel` (lines 230-268, docstrings included) with:
```ts
/**
 * The k dev trials nearest to eligible: most hurdles cleared, then best MAR, then earliest.
 * Comparison books are left out: they are built to be beaten and are never "nearly there".
 */
export function closest(trials: LabTrial[], k: number): LabTrial[] {
  return devTrials(trials)
    .filter((t) => !isComparisonBook(t))
    .sort((a, b) => conditionsPassed(b) - conditionsPassed(a) || marDesc(a, b) || byN(a, b))
    .slice(0, k);
}

/**
 * A method's best variant: fewest missed hurdles, then best MAR, then earliest. Dev trials first,
 * and among them the candidates: a comparison book clears the six classic hurdles as easily as an
 * idea does (that is what makes it a fair comparison), so letting it win here would headline the
 * method with the arm registered to lose. It is chosen only when the method has nothing else.
 */
export function bestVariant(trials: LabTrial[]): LabTrial | null {
  const dev = devTrials(trials);
  const candidates = dev.filter((t) => !isComparisonBook(t));
  const pool = candidates.length > 0 ? candidates : dev.length > 0 ? dev : [...trials];
  if (pool.length === 0) return null;
  return pool.sort((a, b) => misses(a).length - misses(b).length || marDesc(a, b) || byN(a, b))[0];
}

/** Could this hurdle be scored on this row at all? The denominator `funnel` quotes. */
function scored(t: LabTrial, key: ConditionKey): boolean {
  if (key === 'dsr') return t.luckGated && t.dsrNow !== null;
  if (key === 'yardstick') {
    const state = twinsState(t);
    return state === 'cleared' || state === 'missed' || state === 'unmatched';
  }
  return true;
}

/**
 * Per hurdle, how many dev trials cleared it.
 *
 * `measured` is how many rows the hurdle could be *scored* on. For most hurdles that is every
 * row. The luck check leaves out the P7a seed rows, which have no DSR to re-evaluate at any N;
 * those rows still **miss** it — nothing is admitted for being unmeasurable, and `passing` counts
 * them as misses — but "1 of the 56 it was checked on" rather than "1 of 110" is the honest
 * denominator. The random-twin check counts only rows that have been judged on it (a reading, or
 * the engine's miss): an arm nobody has measured was not checked, and one that only holds funds
 * has nothing to check.
 *
 * `luckGated` is checked alongside the score for the same reason the denominator exists at all:
 * a row the hurdle does not apply to was not "checked and unscorable", it was not checked.
 */
export function funnel(trials: LabTrial[]): FunnelRow[] {
  const dev = devTrials(trials);
  return CONDITION_KEYS.map((key) => ({
    key,
    label: CONDITION_LABEL[key],
    passing: dev.filter((t) => conditionOk(t, key) === true).length,
    measured: dev.filter((t) => scored(t, key)).length,
    total: dev.length,
  }));
}
```
**Impact:** `misses` and `conditionsPassed` count seven keys. On the committed snapshot every arm has `yardstick: null`, so the seventh is `null` everywhere and every existing count is unchanged.

### Step 9: Glossary, fixture and the build-time guard
**File:** `web/lib/sera/glossary.ts:5-23`, `:104-136`
**Change:** add three keys to `GlossaryKey` (after `'ownerInputs'`: `| 'randomTwin' | 'twinsBeaten' | 'comparisonBook'`), three entries to `GLOSSARY` (after `ownerInputs`), three to `GLOSSARY_ORDER` (after `'tries'`), and `yardstick` to `CONDITION_TERM`.
**Code:**
```ts
export type GlossaryKey =
  | 'return'
  | 'mwr'
  | 'cagr'
  | 'maxDrawdown'
  | 'profitFactor'
  | 'trades'
  | 'sharpe'
  | 'mar'
  | 'dsr'
  | 'tries'
  | 'exposure'
  | 'turnover'
  | 'devWindow'
  | 'testWindow'
  | 'paperTrading'
  | 'spyTr'
  | 'ownerInputs'
  | 'randomTwin'
  | 'twinsBeaten'
  | 'comparisonBook';
```
Inside `GLOSSARY`, after the `ownerInputs` entry:
```ts
  randomTwin: {
    term: 'Random look-alike',
    plain:
      'A made-up book that trades on exactly the same days and in the same amounts as the variant ' +
      'being judged but swaps every stock that variant picked for a randomly drawn index stock of ' +
      'similar trading size, so it has the variant’s shape and none of its judgement.',
  },
  twinsBeaten: {
    term: 'Look-alikes beaten',
    plain:
      'Out of a few hundred random look-alike books, how many the variant earned more than, where ' +
      'an idea that really picks well should beat nearly all of them and one that only has a good ' +
      'shape lands near the middle.',
  },
  comparisonBook: {
    term: 'Comparison book',
    plain:
      'A variant built on purpose to be beaten, such as one that picks at random or leaves the idea ' +
      'out, so the idea can be judged by how far ahead of it it lands, and never a candidate itself.',
  },
```
`GLOSSARY_ORDER` becomes:
```ts
export const GLOSSARY_ORDER: GlossaryKey[] = [
  'spyTr',
  'return',
  'mwr',
  'cagr',
  'maxDrawdown',
  'profitFactor',
  'trades',
  'ownerInputs',
  'dsr',
  'tries',
  'twinsBeaten',
  'randomTwin',
  'comparisonBook',
  'mar',
  'sharpe',
  'exposure',
  'turnover',
  'devWindow',
  'testWindow',
  'paperTrading',
];
```
`CONDITION_TERM` becomes:
```ts
export const CONDITION_TERM: Record<ConditionKey, GlossaryKey> = {
  spy: 'spyTr',
  drawdown: 'maxDrawdown',
  pf: 'profitFactor',
  trades: 'trades',
  owner: 'ownerInputs',
  dsr: 'dsr',
  yardstick: 'twinsBeaten',
};
```

**File:** `web/lib/sera/fixture.ts`
**Change:** gate fields, trial defaults, and the arm states the tests need. Replace the import line and `GATE` (lines 2-15):
```ts
import type { Gate, LabMethod, LabTrial, LabYardstick } from './types';

export const GATE: Gate = {
  maxDrawdown: 0.25,
  minProfitFactor: 1.3,
  minTrades: 100,
  dsrMin: 0.9,
  dsrPolicy: 'all-trials',
  dsrN: 110,
  dsrNBasis: '110 dev trials, every variant run counted as one independent look',
  yardstickMin: 0.9,
  yardstickDraws: 200,
  devStart: '1993-01-29',
  devEnd: '2015-10-16',
  testStart: '2015-10-19',
};
```
In `trial()`, after `luckGated: true,` (line 60) add:
```ts
    // No role and no random-twin reading: the state of every arm the lab held when the check
    // began. A test about either sets it.
    role: null,
    yardstick: null as LabYardstick | null,
```
Append at the end of the file:
```ts
/** The engine's random-twin miss and control labels, as `failedNow` carries them. */
export const TWINS_MISS = 'beats 90% of random twins';
export const CONTROL = 'not a control arm';

/** A measured random-twin reading: beat 187 of 200 look-alikes. */
export function reading(over: Partial<LabYardstick> = {}): LabYardstick {
  return {
    status: 'measured',
    percentile: 0.935,
    draws: 200,
    beaten: 187,
    armRate: 0.112,
    medianRate: 0.081,
    tradeRatio: 1.04,
    ...over,
  };
}

/**
 * One dev arm in each state the method page has to draw for the random-twin check, otherwise
 * clean (it clears the six classic hurdles), so a test isolates the seventh.
 *
 * Built here rather than in each test because the committed snapshot cannot supply them: the
 * committed lab has no role and no reading recorded yet, so on the real data every arm is
 * `notMeasured`. These are the only way the other six states are exercised before the backfill.
 */
export function armStates() {
  const clean = { failed: [] as string[], dsr: 0.97, dsrNow: 0.97 };
  return {
    measuredPass: trial({ ...clean, n: 101, candidateId: 'M0001-PASS', role: 'treatment', yardstick: reading(), failedNow: [] }),
    measuredFail: trial({
      ...clean, n: 102, candidateId: 'M0001-FAIL', role: 'treatment',
      yardstick: reading({ percentile: 0.75, beaten: 150, armRate: 0.07 }), failedNow: [TWINS_MISS],
    }),
    unmatched: trial({
      ...clean, n: 103, candidateId: 'M0001-ODD', role: 'treatment',
      yardstick: reading({ status: 'unmatched', percentile: 0.96, beaten: 192, tradeRatio: 2.6 }), failedNow: [TWINS_MISS],
    }),
    notApplicable: trial({
      ...clean, n: 104, candidateId: 'M0001-FUNDS', role: 'treatment',
      yardstick: reading({ status: 'not-applicable', percentile: null, draws: 0, beaten: null, medianRate: null, tradeRatio: null }),
      failedNow: [],
    }),
    notMeasured: trial({ ...clean, n: 105, candidateId: 'M0001-OLD', failedNow: [] }),
    recentUnmeasured: trial({ ...clean, n: 106, candidateId: 'M0001-NEW', role: 'treatment', failedNow: [TWINS_MISS] }),
    control: trial({ ...clean, n: 107, candidateId: 'M0001-RAND', role: 'control', failed: [CONTROL], failedNow: [CONTROL] }),
  };
}
```

**File:** `web/lib/sera/lab.ts:17-33` (`requireGate`)
**Change:** the guard also requires the two snapshot-8 gate fields, so a stale `lab.json` fails the build instead of printing "beats at least NaN in 10".
**Code:**
```ts
function requireGate(snap: LabSnapshot): LabSnapshot {
  const g = snap.gate;
  const ok =
    g != null &&
    Number.isFinite(g.dsrMin) &&
    Number.isInteger(g.dsrN) &&
    g.dsrN >= 0 &&
    DSR_POLICIES.includes(g.dsrPolicy) &&
    typeof g.dsrNBasis === 'string' &&
    g.dsrNBasis.length > 0 &&
    Number.isFinite(g.yardstickMin) &&
    Number.isInteger(g.yardstickDraws);
  if (!ok) {
    throw new Error(
      'web/data/lab.json is missing a usable gate.dsrPolicy / gate.dsrN / gate.dsrNBasis / ' +
        'gate.yardstickMin / gate.yardstickDraws. ' +
        'Regenerate it with `python -m seer_engine lab export-json` and commit it.',
    );
  }
  return snap;
}
```

### Step 10: The method page's helpers
**File:** `web/app/sera/methods/view.ts`
**Change:** imports (lines 11-15), `MethodRow.passed` doc (line 52), the hurdle block (lines 207-307), and the technical record (lines 409-433).

Imports become:
```ts
import {
  bestVariant, CONDITION_KEYS, CONDITION_LABEL, CONTROL_LABEL, conditionOk, conditionsPassed, excessCagr,
  isComparisonBook, isYardstickLabel, misses, moneyWeighted, shareInWords, trialsByMethod, twinsState,
  twinsValue, type ConditionKey,
} from '../../../lib/sera/derive';
import type { ArmRole, Gate, LabMethod, LabTrial, Point } from '../../../lib/sera/types';
```
Line 52: `  /** Hurdles the best variant cleared (0..7), or null when it was never run. */`

Add, directly after `techStatus` (in the technical-record block below), the one place the two new
engine labels become owner words outside the condition marks (Decision D15):
```ts
/**
 * One `failedNow` label as the owner reads it in a sentence ("Still misses: …" on the redone panel).
 *
 * Only the two labels this lab grew on 2026-11-14 are translated: the random-twin miss and the
 * control arm's label, which would otherwise print engine text ("beats 90% of random twins",
 * "not a control arm") on a page with no ids or code. Every older label is returned as it was;
 * rewording those is a separate change.
 */
export function missInWords(label: string, gate: Gate): string {
  if (isYardstickLabel(label)) return `beating ${shareInWords(gate.yardstickMin)} random look-alike books`;
  if (label === CONTROL_LABEL) return 'it is a comparison book, built to be beaten';
  return label;
}
```

Replace lines 207-307 (from `/* ---- The six hurdles` through the end of `workedSummary`) with:
```ts
/* ---- The seven hurdles --------------------------------------------------------------------- */

/**
 * true = cleared, false = missed, null = nothing to score here
 * (derive.conditionOk, which reads the engine's `failedNow`, `luckGated` and `yardstick`).
 *
 * `null` is the luck check on a test-window look, the random-twin check on a test look or on a
 * book that only holds funds, and the random-twin check on an arm nobody has measured yet. The
 * last one says so in `naText` ("not measured yet"), so a dashed mark is never read as an excused
 * hurdle when it is really a pending one. `detail` is the reading behind a random-twin mark
 * ("beat 187 of 200"), printed after the state wherever the mark is spelled out.
 */
export type Mark = { key: ConditionKey; label: string; ok: boolean | null; naText?: string; detail?: string };

/** The seven hurdles of one trial, in display order. */
export const marks = (t: LabTrial): Mark[] =>
  CONDITION_KEYS.map(key => {
    const mark: Mark = { key, label: CONDITION_LABEL[key], ok: conditionOk(t, key) };
    if (key !== 'yardstick') return mark;
    const state = twinsState(t);
    if (state === 'not-measured') return { ...mark, naText: 'not measured yet' };
    if (state === 'cleared' || state === 'missed' || state === 'unmatched') return { ...mark, detail: twinsValue(t) };
    return mark;
  });

/** 'Beats SPY: cleared' / 'missed' / 'not applicable' / 'not measured yet', plus any reading. */
export const markLabel = (m: Mark): string => {
  const state = m.ok === null ? (m.naText ?? 'not applicable') : m.ok ? 'cleared' : 'missed';
  return m.detail ? `${m.label}: ${state} (${m.detail})` : `${m.label}: ${state}`;
};

/** One plain sentence per hurdle, with its threshold read from the gate. */
export function conditionTip(key: ConditionKey, gate: Gate): string {
  switch (key) {
    case 'spy': return 'Grew faster a year than holding SPY with dividends reinvested';
    case 'drawdown': return `Never fell more than ${pct(gate.maxDrawdown, 0)} from a peak`;
    case 'pf': return `Money won on winners is at least ${gate.minProfitFactor}× the money lost on losers`;
    case 'trades': return `At least ${count(gate.minTrades)} trades, so the result is not a handful of lucky bets`;
    case 'owner': return 'Needs no setting that only the owner can decide';
    case 'dsr': return `A luck-adjusted score of at least ${fixed(gate.dsrMin, 2)}, discounted by all ${count(gate.dsrN)} tries counted so far (${gate.dsrNBasis})`;
    case 'yardstick': return `Earned more than at least ${shareInWords(gate.yardstickMin)} of ${count(gate.yardstickDraws)} random look-alike books: the same trading days and amounts, with every picked stock swapped for a random one of similar size`;
  }
}

/**
 * The random-twin sentence. Its own function because it has six things to say, not three, and
 * which one is decided by `twinsState` — the engine's verdict and its reading together — rather
 * than by the tick alone.
 */
export function twinsSentence(t: LabTrial, gate: Gate): string {
  const label = CONDITION_LABEL.yardstick;
  const bar = shareInWords(gate.yardstickMin);
  const y = t.yardstick;
  const beat = y !== null && y.beaten !== null && y.draws !== null
    ? `${count(y.beaten)} of ${count(y.draws)}`
    : null;
  switch (twinsState(t)) {
    case 'cleared':
      return beat === null
        ? `${label}: yes.`
        : `${label}: yes (it earned more than ${beat} random look-alike books, and the bar is ${bar}).`;
    case 'missed':
      return beat === null
        ? `${label}: no (not measured — a variant this recent cannot pass until it has been compared with random look-alike books).`
        : `${label}: no (it earned more than only ${beat} random look-alike books, short of ${bar}).`;
    case 'unmatched':
      return `${label}: no (its random look-alikes ended up trading too differently from it to be a fair comparison, and that never counts as a pass).`;
    case 'not-applicable':
      return `${label}: does not apply. It only holds funds, so there are no picked stocks to swap for random ones.`;
    case 'not-measured':
      return `${label}: not measured yet. It has not been compared with random look-alike books, so this is neither a pass nor a miss.`;
    case 'test-look':
      return `${label}: does not apply to a test run.`;
  }
}

/** 'Beats SPY: no (7.6% vs 7.9% a year).' and so on, one per hurdle. */
export function conditionSentence(key: ConditionKey, ok: boolean | null, t: LabTrial, gate: Gate): string {
  if (key === 'yardstick') return twinsSentence(t, gate);
  const label = CONDITION_LABEL[key];
  if (ok === null) {
    // Only the luck check reaches here, and only on a test look. Say which hurdle it is, say it
    // does not apply, and still show the number — it was measured, it is simply not a bar.
    return key === 'dsr'
      ? `${label}: does not apply. A test run is a single try booked in advance, so there is nothing to discount for luck${t.dsrNow === null ? '' : ` (it scored ${fixed(t.dsrNow, 3)})`}.`
      : `${label}: does not apply.`;
  }
  const yn = ok ? 'yes' : 'no';
  const money = moneyWeighted(t);
  switch (key) {
    case 'spy':
      // A funded run is judged on what its money earned, so that is what this sentence quotes.
      // Its `cagr` is not a yearly return once deposits keep arriving — it is the shape of a
      // curve that the deposits themselves lifted — and quoting it here would name a number the
      // engine did not decide the tick by.
      return money !== null
        ? `${label}: ${yn} (your money earned ${pct1(money.mwr)} a year, against ${pct1(money.spyTrMwr)} from putting the same deposits into SPY on the same days).`
        : `${label}: ${yn} (${pct1(t.cagr)} vs ${pct1(t.spyTrCagr)} a year).`;
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

export type Worked = {
  headline: string;
  /** One per hurdle: its mark, and the sentence printed beside it. */
  lines: (Mark & { text: string })[];
  /** Every line joined: the one-paragraph summary. */
  sentence: string;
};

const NUMBER_WORDS = ['no', 'one', 'two', 'three', 'four', 'five', 'six', 'seven'];

/**
 * The plain 'Did it work?' answer for a method's best variant.
 *
 * Hurdles with nothing to score are not hurdles it failed to clear, so they leave the count: a
 * test look is counted out of five, and an arm nobody has compared with its random look-alikes
 * out of six. That second case is a hurdle still ahead of it, not one behind it, so a "Yes" says
 * so in the same sentence rather than reading as "cleared everything".
 */
export function workedSummary(best: LabTrial, gate: Gate): Worked {
  const lines = marks(best).map(m => ({ ...m, text: conditionSentence(m.key, m.ok, best, gate) }));
  const passed = conditionsPassed(best);
  const applicable = lines.filter(l => l.ok !== null).length;
  const span = windowText(best);
  const pending = twinsState(best) === 'not-measured' ? '; it has not been compared with random look-alike books yet' : '';
  const headline = passed === applicable
    ? `Yes. Its best variant, ${best.candidateId}, cleared all ${NUMBER_WORDS[applicable] ?? count(applicable)} hurdles on ${span} data${pending}.`
    : `Not yet. Its best variant, ${best.candidateId}, cleared ${passed} of ${count(applicable)} hurdles on ${span} data.`;
  return { headline, lines, sentence: lines.map(l => l.text).join(' ') };
}
```
Replace `untestedNote`'s neighbour `techRows` (lines 409-433) with the version below, and add `roleText`, `twinsRecord` and `techStatus` directly above it:
```ts
const ROLE_TEXT: Record<ArmRole, string> = {
  idea: 'the idea itself',
  treatment: 'the idea itself',
  dose: 'the idea at a stronger or weaker setting',
  control: 'a comparison book, built to be beaten',
};

/** An arm's registered role in words, or 'not recorded'. */
export const roleText = (role: ArmRole | null): string => (role === null ? 'not recorded' : ROLE_TEXT[role]);

/** The random-twin reading for the technical record: the count, the arm's rate and the middle look-alike's. */
export function twinsRecord(t: LabTrial): string {
  const y = t.yardstick;
  switch (twinsState(t)) {
    case 'cleared':
    case 'missed':
      return y === null || y.beaten === null || y.draws === null
        ? 'not measured, and a variant this recent cannot pass without it'
        : `${twinsValue(t)}; it earned ${pct1(y.armRate)} a year, the middle look-alike ${pct1(y.medianRate)}`;
    case 'unmatched':
      return 'not comparable: its look-alikes traded too differently from it';
    case 'not-applicable':
      return 'does not apply: it only holds funds';
    case 'test-look':
      return 'does not apply to a test run';
    case 'not-measured':
      return 'not measured yet';
  }
}

/** The one-line state on a technical-record summary. A comparison book is not a missed idea. */
export const techStatus = (t: LabTrial): string =>
  isComparisonBook(t) ? 'comparison book' : t.failedNow.length ? `missed ${t.failedNow.length}` : 'eligible';

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
    // Snapshot 8. What the arm was registered as, and how it did against its random look-alikes.
    ['Kind of variant', roleText(t.role)],
    ['Random look-alikes', twinsRecord(t)],
    // Only for a run that was fed. An unfunded trial has nothing to say here and says nothing,
    // which is why these are appended rather than dashed: every recorded trial is unfunded, and a
    // row of em-dashes on all 128 of them would be noise standing in for a definite answer.
    ...(moneyWeighted(t)
      ? ([
        ['What the money earned', `${earned(t)} a year`],
        ['The same deposits in SPY', `${signed1(moneyWeighted(t)!.spyTrMwr)} a year`],
      ] as [string, string][])
      : []),
  ];
}
```
**Impact:** `workedSummary(...).lines` carries `Mark` fields; the page passes each line as the mark (step 11).

### Step 11: The method page
**File:** `web/app/sera/methods/[id]/page.tsx`
**Change:** eight edits.

(a) Line 14 import becomes:
```tsx
import { bestVariant, CONDITION_KEYS, CONDITION_LABEL, drawdownSeries, isComparisonBook, moneyWeighted, spyForWindow, yearlyReturns } from '@/lib/sera/derive';
```
and in the `../view` import (lines 20-25) add `techStatus` and `missInWords` after `techRows,`.

(b) Replace the `MarkIcon` docstring's first line (line 180) `* A condition mark: tick, cross, or a dashed circle for a hurdle that does not apply.` with:
```tsx
 * A condition mark: tick, cross, or a dashed circle for a hurdle with nothing to score — one that
 * does not apply, or a random-twin check nobody has run yet. The label says which; the circle
 * never reads as a pass.
```

(c) Add the comparison-book chip above `function Tested` (line 273):
```tsx
/**
 * A control arm, named for what it is to the owner: a book registered to be beaten, so the idea
 * has something fair to beat. The engine refuses it as a candidate with a label that is not a
 * condition ("not a control arm"); drawing that as a crossed seventh hurdle would read as the idea
 * failing, which is not what happened. Dashed like a waiting status chip, never filled like a result.
 */
function ComparisonChip() {
  return (
    <span className={s.compare} data-tip={GLOSSARY.comparisonBook.plain}>comparison book</span>
  );
}
```

(d) In `Tested`, replace the "Did it work?" list body (lines 308-315):
```tsx
        <ul className={s.worked}>
          {worked.lines.map(l => (
            <li key={l.key} className={s.workedItem}>
              <MarkIcon mark={l} size={16} />
              <span>{l.text}</span>
            </li>
          ))}
        </ul>
```

(e) Replace the variants caption (lines 385-386):
```tsx
        caption={`One row per test run. A tick means the hurdle was cleared; a dashed circle means it does not apply, or has not been measured yet. A row marked comparison book was built to be beaten, so the idea can be judged against it. The best variant is highlighted.${
          funded ? ' Some runs here had money added every month, so their return and growth-a-year cells are left blank: with deposits arriving, neither is a return. What that money actually earned has a column of its own.' : ''}`}
```

(f) Replace the row header (line 430):
```tsx
                    <th scope="row" className={s.variant}>
                      {t.candidateId}
                      {isComparisonBook(t) && <ComparisonChip />}
                    </th>
```
and in `VariantCard`, replace line 512 `<span className={s.vName}>{t.candidateId}</span>` with:
```tsx
        <span className={s.vName}>{t.candidateId}</span>
        {isComparisonBook(t) && <ComparisonChip />}
```

(g) Replace the technical summary line (line 599):
```tsx
        <span className={s.techSub}>#{t.n} · {t.window === 'dev' ? 'development' : 'test'} {windowText(t)} · {techStatus(t)}</span>
```
(h) In `RedonePanel` (line 256), replace
```tsx
              <span className={s.redoneNote}>Still misses: {trial.failedNow.join(', ')}.</span>
```
with
```tsx
              <span className={s.redoneNote}>
                Still misses: {trial.failedNow.map(f => missInWords(f, lab.gate)).join(', ')}.
              </span>
```
and add `missInWords` to the `../view` import beside `techStatus`. `lab` is already imported
(line 17). The two new labels now read in plain words; every older label prints as before (Decision D15).

**Impact:** the desk table grows one condition column (18 columns inside the existing `min-width: 1240px` scroller); each card lists seven marks. No new button: the chip is a static label with a tooltip, like `statusChip`. The redone panel never shows the engine's text for the two new labels.

**File:** `web/app/sera/methods/[id]/method.module.css:56` (after `.window[data-window='test']`)
**Code:**
```css
/* A comparison book (a control arm): built to be beaten, so it carries the dashed outline the
   status chip uses for "waiting", never the filled ink of a result. Same pill as .window. */
.compare {
  display: inline-flex; flex: none; align-items: center; height: 22px; margin-left: 8px; padding: 0 8px;
  border-radius: 999px; border: 1.5px dashed var(--outline); color: var(--ink-2); vertical-align: middle;
  font-size: 11px; font-weight: 400; letter-spacing: 0.06em; text-transform: uppercase;
}
```

### Step 12: The methods list, the how page and the overview count
**File:** `web/app/sera/methods/page.tsx`
**Change:** (a) line 8 `import { excessCagr } from '@/lib/sera/derive';` becomes `import { CONDITION_KEYS, excessCagr } from '@/lib/sera/derive';`. (b) Line 61 caption becomes:
```tsx
        caption="The seven dots on each row are the seven hurdles a method must clear before it may trade. A filled dot means cleared; a dashed one means it does not apply or has not been measured yet."
```
(c) Line 195 comment: `*   - Trades: a sample-size check, not a result; its hurdle is still one of the seven dots.` (d) Replace `Dots` (lines 259-271):
```tsx
function Dots({ best, passed }: { best: LabTrial; passed: number }) {
  const ms = marks(best);
  // `=== false`, not `!== true`: a hurdle that does not apply to this row was not missed, and
  // listing it under "missed" is the same wrong answer as ticking it, one column over.
  const missed = ms.filter(x => x.ok === false).map(markLabel);
  const tip = missed.length ? missed.join(' · ') : 'Cleared every hurdle';
  const total = CONDITION_KEYS.length;
  return (
    <span className={s.dots} role="img" aria-label={`Cleared ${passed} of ${total} hurdles. ${tip}`} data-tip={tip}>
      {ms.map(x => (
        <span key={x.key} className={x.ok === true ? s.dotOn : x.ok === null ? s.dotNa : s.dotOff} />
      ))}
      <span className={`num ${s.dotsN}`}>{passed}/{total}</span>
    </span>
  );
}
```

**File:** `web/app/sera/how/view.ts`
**Change:** (a) line 11 import becomes `import { CONDITION_KEYS, shareInWords, type ConditionKey } from '../../../lib/sera/derive';`. (b) Replace the `hurdles` stage (lines 116-129):
```ts
    {
      key: 'hurdles',
      // One title line, so the box has room for six detail lines above its count pill.
      title: ['Seven hurdles'],
      detail: [
        'Beat SPY + dividends',
        `Worst fall ≤ ${pctLabel(g.maxDrawdown)}`,
        `PF ≥ ${num(g.minProfitFactor)} · ${count(g.minTrades)}+ trades`,
        'No owner inputs',
        `Luck check ≥ ${num(g.dsrMin)}`,
        `Beat ${shareInWords(g.yardstickMin)} look-alikes`,
      ],
      count: `${count(c.eligible)} pass`,
      countTip: `${count(c.eligible)} of ${count(c.devTrials)} tries clear every hurdle at once`,
      fails: true,
      weight: 1.35,
    },
```
(c) In `hurdles()` (line 211), after the `dsr` entry of `text`, add:
```ts
    yardstick: {
      title: 'Better than random picks',
      target: `Beats ${shareInWords(gate.yardstickMin)} random look-alikes`,
      plain: `A strong result can come from the shape of a book — how many stocks it holds, how often it trades, when it steps aside — rather than from which stocks it picks. So each variant is replayed ${count(gate.yardstickDraws)} times on its own trading days and in its own amounts, with every stock it picked swapped for a random index stock of similar trading size, and it must earn more than at least ${shareInWords(gate.yardstickMin)} of those look-alikes. A book that only holds funds has no picks to swap, so this one does not apply to it.`,
    },
```

**File:** `web/components/sera/diagrams/geometry.ts:10`
**Change:** the comment becomes `/** 1–5 short lines under a two-line title, 1–6 under a one-line title (≤ 18 characters, ≤ 26 on a weight-1.35 box). */` (measured: a sixth line under a two-line title lands at y 199, inside the count pill at 192; under a one-line title the sixth sits at 179).

**File:** `web/app/sera/how/page.tsx:87-89`
**Change:**
```tsx
          title="Seven things every method must clear"
          caption="A method passes the practice stage only if one of its variants clears all seven at once. The numbers come from the lab’s own settings."
```

**File:** `web/app/sera/overview.ts:5-20`, `:276`
**Change:** add `CONDITION_KEYS,` to the `../../lib/sera/derive` import list, and replace lines 19-20 with:
```ts
/** The conditions every dev try is judged on (the contract's failure labels). A count, not a threshold. */
export const HURDLES = CONDITION_KEYS.length;
```
and the tip at line 276 with:
```ts
            ? `${r.passing} of the ${r.measured} tries it was checked on pass “${r.label}” (${r.total - r.measured} ${r.key === 'yardstick' ? 'not compared with random look-alikes yet' : 'older tries predate it'})`
```
`overview.ts:130` already counts `eligibleNow` (`dev.filter(t => t.eligibleNow).length`): the engine's verdict carries the twin and control labels, so the headline count is right with no logic change. Confirmed by reading; nothing else in `overview.ts` changes.

### Step 13: Web tests
**File:** `web/lib/sera/lab.test.ts`
**Change:** (a) imports (lines 2-4):
```ts
import {
  CONTROL_LABEL, DRAWDOWN_FAILURE_PREFIX, DSR_FAILURE_PREFIX, FAILURE_LABEL, isYardstickLabel,
} from './derive';
import { childrenOf, insightsOf, lab, methodById, trialsOf } from './lab';
import { ARM_ROLES, DSR_POLICIES, INSIGHT_KINDS, METHOD_STATUSES, SOURCE_KINDS, YARDSTICK_STATUSES } from './types';
```
(b) `expect(lab.version).toBe(7);` becomes `expect(lab.version).toBe(8);`, and after `expect(lab.gate.devStart).toBe('1993-01-29');` add:
```ts
    // Snapshot 8: the random-twin bar and draw count, published from the engine's constants.
    expect(lab.gate.yardstickMin > 0 && lab.gate.yardstickMin < 1).toBe(true);
    expect(Number.isInteger(lab.gate.yardstickDraws) && lab.gate.yardstickDraws > 0).toBe(true);
```
(c) In 'writes every failure label in a shape conditionOk can read' replace the `known` / `unreadable` lines with:
```ts
    const known = new Set([...Object.values(FAILURE_LABEL), CONTROL_LABEL]);
    const unreadable = lab.trials
      .flatMap((t) => [...t.failed, ...t.failedNow])
      .filter(
        (f) =>
          !known.has(f) &&
          !f.startsWith(DSR_FAILURE_PREFIX) &&
          !f.startsWith(DRAWDOWN_FAILURE_PREFIX) &&
          !isYardstickLabel(f),
      );
```
(d) Add a new `it` after it:
```ts
  it('publishes every arm\'s role and random-twin reading, or null', () => {
    // A missing key reads as `undefined`, which neither branch accepts: a lab.json exported by an
    // engine older than snapshot 8 fails here rather than rendering every arm as "not measured".
    const bad = lab.trials.filter(
      (t) =>
        !(t.role === null || ARM_ROLES.includes(t.role)) ||
        !(t.yardstick === null || YARDSTICK_STATUSES.includes(t.yardstick.status)),
    );
    expect(bad.map((t) => t.n)).toEqual([]);
  });
```

**File:** `web/lib/sera/derive.test.ts`
**Change:** (a) imports become:
```ts
import {
  bestVariant,
  books,
  closest,
  conditionOk,
  conditionsPassed,
  drawdownSeries,
  excessCagr,
  families,
  funnel,
  gateChecks,
  isComparisonBook,
  isYardstickLabel,
  misses,
  moneyWeighted,
  progress,
  shareInWords,
  spyForWindow,
  trialsByMethod,
  twinsState,
  yearlyReturns,
} from './derive';
import { armStates, CONTROL, GATE, method, trial } from './fixture';
```
(b) In 'lists six hurdles in order…' (line 53): rename to `'lists seven hurdles in order with plain labels, values and targets from the gate'`, the key list becomes `['spy', 'drawdown', 'pf', 'trades', 'owner', 'dsr', 'yardstick']`, the label list gains `'Beats look-alikes'`, and add at the end of the test:
```ts
    // No reading on the default fixture: the seventh is pending, never a tick.
    expect(checks[6]).toMatchObject({
      value: 'not measured yet', target: 'beats at least 9 in 10 random look-alike books', ok: null,
    });
```
(c) In 'counts dev trials clearing each hurdle' (funnel, line 202) add `['yardstick', 0, 0, 3]` to the end of the expected rows.
(d) Append two blocks:
```ts
describe('the random-twin condition', () => {
  const s = armStates();

  it('matches the engine label by both ends and a number, never the SPY label', () => {
    expect(isYardstickLabel('beats 90% of random twins')).toBe(true);
    expect(isYardstickLabel('beats 92.5% of random twins')).toBe(true);
    expect(isYardstickLabel('beats SPY TR')).toBe(false);
    expect(isYardstickLabel('beats % of random twins')).toBe(false);
  });

  it('is three-state: cleared, missed, or nothing to score', () => {
    expect(conditionOk(s.measuredPass, 'yardstick')).toBe(true);
    expect(conditionOk(s.measuredFail, 'yardstick')).toBe(false);
    expect(conditionOk(s.unmatched, 'yardstick')).toBe(false);
    expect(conditionOk(s.recentUnmeasured, 'yardstick')).toBe(false);
    expect(conditionOk(s.notApplicable, 'yardstick')).toBe(null);
    expect(conditionOk(s.notMeasured, 'yardstick')).toBe(null);
    expect(conditionOk(trial({ window: 'test', failed: [] }), 'yardstick')).toBe(null);
    expect(twinsState(trial({ window: 'test', failed: [] }))).toBe('test-look');
  });

  it('never draws a missing reading as a pass', () => {
    // The arm clears the six classic hurdles and has never been measured: six cleared, nothing
    // missed, and the seventh is pending — not a seventh tick.
    expect(conditionsPassed(s.notMeasured)).toBe(6);
    expect(misses(s.notMeasured)).toEqual([]);
    expect(gateChecks(s.notMeasured, GATE)[6]).toMatchObject({ key: 'yardstick', value: 'not measured yet', ok: null });
    // An unmatched reading out-earned 192 of 200 and still does not pass.
    expect(gateChecks(s.unmatched, GATE)[6]).toMatchObject({
      value: 'look-alikes traded too differently to compare', ok: false,
    });
  });

  it('prints the reading, and the bar from the gate', () => {
    expect(gateChecks(s.measuredPass, GATE)[6]).toEqual({
      key: 'yardstick',
      label: 'Beats look-alikes',
      value: 'beat 187 of 200',
      target: 'beats at least 9 in 10 random look-alike books',
      ok: true,
    });
    expect(gateChecks(s.measuredFail, { ...GATE, yardstickMin: 0.95 })[6]).toMatchObject({
      value: 'beat 150 of 200', target: 'beats at least 19 in 20 random look-alike books', ok: false,
    });
    expect(gateChecks(s.recentUnmeasured, GATE)[6]).toMatchObject({ value: 'not measured', ok: false });
    expect(shareInWords(0.9)).toBe('9 in 10');
    expect(shareInWords(0.95)).toBe('19 in 20');
    expect(shareInWords(0.925)).toBe('925 in 1000');
  });

  it('says a book that only holds funds has nothing to swap', () => {
    expect(gateChecks(s.notApplicable, GATE)[6]).toMatchObject({
      value: 'does not apply', target: 'does not apply to a book that only holds funds', ok: null,
    });
  });

  it('counts a reading in the funnel only where the arm was judged on it', () => {
    const rows = funnel(Object.values(s));
    // Seven dev arms; judged on it: the pass, the fail, the unmatched and the recent unmeasured.
    expect(rows[6]).toMatchObject({ key: 'yardstick', passing: 1, measured: 4, total: 7 });
  });
});

describe('comparison books', () => {
  const s = armStates();

  it('knows a control by its recorded role or by the engine label alone', () => {
    expect(isComparisonBook(s.control)).toBe(true);
    expect(isComparisonBook(trial({ failed: [CONTROL] }))).toBe(true);
    expect(isComparisonBook(s.measuredPass)).toBe(false);
  });

  it('never counts the control label as a missed hurdle', () => {
    expect(misses(s.control)).toEqual([]);
    expect(s.control.eligibleNow).toBe(false);
  });

  it('never makes a comparison book the method\'s best variant or its nearest miss', () => {
    // The control misses nothing; the treatment misses the random-twin check. Without the rule
    // the control would headline the method.
    expect(bestVariant([s.control, s.measuredFail])?.n).toBe(102);
    expect(closest([s.control, s.measuredFail], 1).map((t) => t.n)).toEqual([102]);
    // A method made only of comparison books still has something to show.
    expect(bestVariant([s.control])?.n).toBe(107);
  });
});
```
**File:** `web/lib/sera/glossary.test.ts:18-37`
**Change:** add `'randomTwin', 'twinsBeaten', 'comparisonBook',` to the expected key list (before `].sort()`). The one-sentence, no-percent and `CONDITION_TERM` checks then cover the new entries.

**File:** `web/app/sera/methods/view.test.ts`
**Change:** (a) import `armStates` beside `GATE, withVerdict` and add `roleText, techStatus, twinsRecord,` to the `./view` import list. (b) In the local `trial` builder (line 31) change `luckGated: true, failedNow: [], eligibleNow: false, dsrNow: null,` to `luckGated: true, failedNow: [], eligibleNow: false, dsrNow: null, role: null, yardstick: null,`. (c) In 'marks the failed hurdles from the engine list' (line 139) the expected object gains `yardstick: null`. (d) In 'writes the plain summary from the gate thresholds' (line 231) the expected sentence gains, after `'Luck check: no (0.899 < 0.90, scored at N = 110).'`:
```ts
      ' Beats look-alikes: not measured yet. It has not been compared with random look-alike books, so this is neither a pass nor a miss.',
```
(e) 'says yes when every hurdle clears' (line 240) expects:
```ts
    expect(workedSummary(t, GATE).headline).toBe(
      'Yes. Its best variant, M0001-TV12, cleared all six hurdles on 1996–2015 data; it has not been compared with random look-alike books yet.',
    );
```
(f) Add inside `describe('marks / workedSummary', …)`:
```ts
  it('draws every random-twin state in words, and never a missing reading as a pass', () => {
    const s = armStates();
    const twins = (t: LabTrial) => marks(t).find(x => x.key === 'yardstick')!;
    expect(markLabel(twins(s.measuredPass))).toBe('Beats look-alikes: cleared (beat 187 of 200)');
    expect(markLabel(twins(s.measuredFail))).toBe('Beats look-alikes: missed (beat 150 of 200)');
    expect(markLabel(twins(s.unmatched))).toBe('Beats look-alikes: missed (look-alikes traded too differently to compare)');
    expect(markLabel(twins(s.recentUnmeasured))).toBe('Beats look-alikes: missed (not measured)');
    expect(markLabel(twins(s.notApplicable))).toBe('Beats look-alikes: not applicable');
    expect(markLabel(twins(s.notMeasured))).toBe('Beats look-alikes: not measured yet');
    expect(twins(s.notMeasured).ok).toBe(null);

    expect(conditionSentence('yardstick', true, s.measuredPass, GATE)).toBe(
      'Beats look-alikes: yes (it earned more than 187 of 200 random look-alike books, and the bar is 9 in 10).',
    );
    expect(conditionSentence('yardstick', false, s.measuredFail, GATE)).toBe(
      'Beats look-alikes: no (it earned more than only 150 of 200 random look-alike books, short of 9 in 10).',
    );
    expect(conditionSentence('yardstick', null, s.notApplicable, GATE)).toBe(
      'Beats look-alikes: does not apply. It only holds funds, so there are no picked stocks to swap for random ones.',
    );
    expect(workedSummary(s.measuredPass, GATE).headline).toBe(
      'Yes. Its best variant, M0001-PASS, cleared all seven hurdles on 1996–2015 data.',
    );
    expect(workedSummary(s.measuredFail, GATE).headline).toBe(
      'Not yet. Its best variant, M0001-FAIL, cleared 6 of 7 hurdles on 1996–2015 data.',
    );
    // Owner-facing words carry no code: no status token, no engine label, no id.
    for (const t of Object.values(s)) {
      for (const m of marks(t)) expect(markLabel(m)).not.toMatch(/yardstick|not-applicable|unmatched|random twins/);
      expect(workedSummary(t, GATE).sentence).not.toMatch(/yardstick|not-applicable|unmatched|random twins/);
    }
  });

  it('records the role and the reading in the technical record, and names a comparison book', () => {
    const s = armStates();
    const pass = Object.fromEntries(techRows(s.measuredPass));
    expect(pass['Kind of variant']).toBe('the idea itself');
    expect(pass['Random look-alikes']).toBe('beat 187 of 200; it earned 11.2% a year, the middle look-alike 8.1%');
    expect(Object.fromEntries(techRows(s.notMeasured))['Random look-alikes']).toBe('not measured yet');
    expect(Object.fromEntries(techRows(s.notApplicable))['Random look-alikes']).toBe('does not apply: it only holds funds');
    expect(roleText('control')).toBe('a comparison book, built to be beaten');
    expect(roleText(null)).toBe('not recorded');
    expect(twinsRecord(s.unmatched)).toBe('not comparable: its look-alikes traded too differently from it');
    expect(techStatus(s.control)).toBe('comparison book');
    expect(techStatus(s.measuredFail)).toBe('missed 1');
    expect(techStatus(s.measuredPass)).toBe('eligible');
  });

  it('puts the two new engine labels into plain words for the redone panel, and leaves the rest', () => {
    const twinsMiss = armStates().measuredFail.failedNow.find(isYardstickLabel)!;
    expect(missInWords(twinsMiss, GATE)).toBe('beating 9 in 10 random look-alike books');
    expect(missInWords(CONTROL_LABEL, GATE)).toBe('it is a comparison book, built to be beaten');
    expect(missInWords('PF >= 1.3', GATE)).toBe('PF >= 1.3');   // older labels: unchanged
    expect(missInWords(twinsMiss, GATE)).not.toMatch(/random twins|%/);
  });
```
and add `missInWords` to the `./view` import list and `CONTROL_LABEL, isYardstickLabel` to this file's `derive` import (or a new `import { CONTROL_LABEL, isYardstickLabel } from '../../../lib/sera/derive';`).

**File:** `web/app/sera/how/view.test.ts`
**Change:** (a) In 'reads the windows and thresholds from the gate' (line 63) the detail expectation becomes:
```ts
    expect(st[3].title).toEqual(['Seven hurdles']);
    expect(st[3].detail.join(' | ')).toBe(
      'Beat SPY + dividends | Worst fall ≤ 25% | PF ≥ 1.3 · 100+ trades | No owner inputs | Luck check ≥ 0.9 | Beat 9 in 10 look-alikes',
    );
```
and add `expect(pipelineStages(snap({ gate: { ...GATE, yardstickMin: 0.95 } }))[3].detail).toContain('Beat 19 in 20 look-alikes');` after the `loose` assertions. (b) In 'keeps every line short enough for its box' add as the loop's first line: `expect(x.detail.length).toBeLessThanOrEqual(x.title.length === 1 ? 6 : 5);`. (c) 'lists the six conditions…' (line 112) becomes:
```ts
  it('lists the seven conditions in gate order with thresholds from the gate', () => {
    const h = hurdles(GATE, 58);
    expect(h.map(x => x.key)).toEqual(['spy', 'drawdown', 'pf', 'trades', 'owner', 'dsr', 'yardstick']);
    expect(h.map(x => x.target)).toEqual([
      'More than SPY total return', 'Max drawdown ≤ 25%', 'Profit factor ≥ 1.3', 'At least 100 trades',
      'Nothing left for the owner to decide', 'Luck check ≥ 0.9', 'Beats 9 in 10 random look-alikes',
    ]);
    expect(h.map(x => x.term)).toEqual(['spyTr', 'maxDrawdown', 'profitFactor', 'trades', 'ownerInputs', 'dsr', 'twinsBeaten']);
    expect(h[5].plain).toContain('N = 110'); // the gate's N, from GATE.dsrN
    expect(h[5].plain).toContain('58'); // the tries argument, still quoted
    expect(h[6].plain).toContain('200 times'); // GATE.yardstickDraws
    expect(h[6].plain).toContain('only holds funds');
  });
```

**File:** `web/app/sera/overview.test.ts`
**Change:** (a) the `trial` builder (after `luckGated: true,` line 74) gains `role: null,` and `yardstick: null,`. (b) `snap`: `version: 7` becomes `version: 8`, and the gate gains `yardstickMin: 0.9, yardstickDraws: 200,` after `dsrNBasis`. (c) 'has one bar per condition' expects ids `['spy', 'drawdown', 'pf', 'trades', 'owner', 'dsr', 'yardstick']` and adds `expect(h.groups[6].items[0]).toMatchObject({ value: 0, valueText: '0' });` and `expect(h.groups[6].items[0].tip).toContain('not compared with random look-alikes yet');`. (d) 'runs over dev try numbers on a 0–6 scale' becomes `'runs over dev try numbers on a 0–7 scale'` with `expect(c.passedTicks).toHaveLength(8);` (`latestPassed` stays 6: no fixture arm has a reading).

### Step 14: Feature map
**File:** `.claude/skills/verify-seer/features/sera.md`
**Change:** add a sub-feature bullet after the first one, driving lines, and a gotcha.
**Code:** after `- Overview, Methods, one method's page (...)` add:
```markdown
- One method's page, the seventh condition: "Beats look-alikes" (the random-twin check) in "Did it work?", in every variant row and card, and in the technical record ("Random look-alikes", "Kind of variant"). A variant with no reading reads "not measured yet" and is drawn as a dashed circle, never a tick; a book that only holds funds reads "does not apply"; a control arm carries a "comparison book" chip instead of a crossed hurdle. The how page lists seven hurdles; the methods list shows seven dots and `n/7`.
```
In the driving block, after the `M0007` line, add:
```sh
$V api RUN GET /sera/methods/M0007         # "Beats look-alikes: not measured yet" (committed lab: no readings yet)
$V api RUN GET /sera/how                   # "Seven things every method must clear", "Better than random picks"
```
Under Gotchas add:
```markdown
- Until the post-merge backfill (`docs/runbooks/yardstick-backfill.md`) runs on `main`, the committed `lab.json` has `role: null` and `yardstick: null` on every trial, so every page reads "not measured yet". To see the measured, unmatched and comparison-book states, write role and reading rows into the run's own lab copy and re-export into the run's web snapshot (`$RUN_DIR/web/data/lab.json`), as the phase-5 Proof does; never into the checkout.
```

## Principles applied

- Make illegal states unrepresentable: the page never combines `failedNow` and `yardstick` itself. `derive.twinsState` is the one function that folds the engine's label and reading into six named states, and every mark, sentence, value and record row switches on it, so "no reading" cannot be drawn as a tick by a component that forgot a branch. `Mark.naText` carries "not measured yet" so a dashed circle says which kind of null it is.
- Encode lessons in structure: every new web literal that mirrors an engine value is pinned by an engine test (both ends and the number of the twin label, the control label, the role and status vocabularies), `lab.test.ts` widens the known-labels check instead of trusting it, and `requireGate` fails the build on a stale snapshot instead of printing "NaN in 10". The bar itself is read from `gate.yardstickMin`, never typed in TS.
- Subtract before you add: the duplicated count `HURDLES = 6` and the `'six'` literal in `workedSummary` are deleted in favour of `CONDITION_KEYS.length` and a number-word table, so the next condition cannot leave a stale "of 6" behind.
- Laziness protocol: no new component or panel. The seventh condition rides the existing `CONDITION_KEYS` loops (table column, card marks, dots, funnel, how cards), the existing dashed `CircleDashed` mark and the existing chip styling; overview logic is unchanged apart from the derived count.
- Prove it works: the Proof drives the real page in a verify-seer run twice, once on the committed snapshot (everything pending) and once on a run-local export carrying a pass, a fail, an unmatched and a control, and reads the screenshots at 390 and 1280 in both themes.

## Verification

**Build:** `cd /home/miftah/.worktrees/seer/random-twin-yardstick && (test -x engine/.venv/bin/python || (python3.11 -m venv engine/.venv && engine/.venv/bin/pip install -e 'engine[dev]')) && engine/.venv/bin/ruff check engine` (the worktree's own venv; main's would test the wrong tree), then `cd web && npm ci && npx tsc --noEmit`
**Tests:** `engine/.venv/bin/pytest engine/tests/test_lab_snapshot.py engine/tests/test_lab_gate_wording.py -n0` then `engine/.venv/bin/pytest engine/tests` (needs `PG_TEST_URL`, per CLAUDE.md); `cd web && npm test`
**Proof:** the exported snapshot carries role and reading, and the method page renders all seven states in plain words.
- Harness: `.claude/skills/verify-seer` (`V=.claude/skills/verify-seer/scripts/verify.sh`, run from the worktree; needs `web/node_modules`)
- Feature-map entries: `features/sera.md`
- Journeys:
  - **J1** · traces R2.4 — run step 6's export, then `git status --short lab/lab.sqlite; jq -c '[.version, .gate.yardstickMin, .gate.yardstickDraws, ([.trials[] | has("role") and has("yardstick")] | all), ([.trials[] | select(.role != null or .yardstick != null)] | length), ([.trials[] | (.failed + .failedNow)[] | select(. == "not a control arm" or endswith("% of random twins"))] | length)]' web/data/lab.json; engine/.venv/bin/pytest -n0 engine/tests/test_lab_snapshot.py -k committed_snapshot_is_the_export` → passes when `git status` prints nothing, `jq` prints `[8,0.9,200,true,0,0]` (the last 0: the export of the unmodified committed `lab/lab.sqlite` — no `trial_roles` table, no reading, newest `run_at` before 2026-11-14 — carries **neither** new label, so `web/lib/sera/lab.test.ts`'s label pin is exercised on this snapshot only through the fixture and the widened known-label set), and the sync test passes
  - **J2** · traces R2.4 — on a scratch copy of the committed lab, record one role and one reading and export:
    ```sh
    S=$(mktemp -d) && cd /home/miftah/.worktrees/seer/random-twin-yardstick && engine/.venv/bin/python - "$S" <<'EOF'
    import json, sqlite3, sys
    from pathlib import Path
    from seer_engine.lab import store, yardstick
    copy = Path(sys.argv[1]) / "lab.sqlite"
    src = sqlite3.connect("file:lab/lab.sqlite?mode=ro", uri=True); dst = sqlite3.connect(copy)
    src.backup(dst); src.close(); dst.close()
    conn = store.connect(copy)   # migrates the COPY: adds the two tables
    n, fp = conn.execute("SELECT n, store_fingerprint FROM trials WHERE method_id = 'M0007' "
                         "AND window = 'dev' ORDER BY n").fetchone()
    with conn:
        store.insert_roles(conn, [store.RoleRow(trial_n=n, role="treatment", source="backfill",
                                                measured="2026-11-14T00:00:00+00:00")])
        store.insert_yardstick(conn, store.YardstickRow(
            trial_n=n, rule_id=yardstick.RULE_ID, store_fingerprint=fp, status="measured", draws=200,
            arm_rate=0.187, beaten=187, percentile=0.935,
            rates_json=json.dumps([i / 1000 for i in range(200)]), trade_ratio=1.04,
            turnover_ratio=0.98, reproduced=1, git_sha="verify", measured="2026-11-14T00:00:00+00:00"))
    s = store.snapshot(conn)
    t = next(t for t in s["trials"] if t["n"] == n)
    print(json.dumps({"gate": [s["gate"]["yardstickMin"], s["gate"]["yardstickDraws"]],
                      "role": t["role"], "yardstick": t["yardstick"]}, sort_keys=True))
    EOF
    git status --short lab/lab.sqlite
    ```
    → passes when it prints `{"gate": [0.9, 200], "role": "treatment", "yardstick": {"armRate": 0.187, "beaten": 187, "draws": 200, "medianRate": 0.0995, "percentile": 0.935, "status": "measured", "tradeRatio": 1.04}}` and `git status` prints nothing
  - **J3** · traces R2.4 — `$V up` (prints `RUN=`), then `$V api RUN GET /sera/methods/M0007`; on the saved HTML (`~/.local/state/seer-verify/$RUN/evidence/NN-api-*.html`) run `grep -o 'Beats look-alikes: [^"<]*' F | sort -u` and `grep -ci 'yardstick\|not-applicable\|unmatched' <the NN-api-*.txt visible text>` → passes when every line grep prints starts with `Beats look-alikes: not measured yet` (no `cleared`, `missed`, `yes` or `no`: the committed lab has no readings, and none is drawn as a pass) and the second count is `0` (no code words in the page text)
  - **J4** · traces R2.4 — in the same run, give M0007's first four dev arms a pass, a fail, an unmatched reading and a control role in the run's OWN lab copy and re-export into the run's OWN web snapshot (never the checkout), then re-read the page:
    ```sh
    D=$HOME/.local/state/seer-verify/$RUN
    SEER_ENV_FILE=$D/engine.env /home/miftah/.worktrees/seer/random-twin-yardstick/engine/.venv/bin/python - "$D" <<'EOF'
    import json, sys
    from pathlib import Path
    from seer_engine.lab import store, yardstick
    d = Path(sys.argv[1])
    conn = store.connect(d / "lab.sqlite")          # the run's private copy
    rows = conn.execute("SELECT n, store_fingerprint FROM trials WHERE method_id = 'M0007' "
                        "AND window = 'dev' ORDER BY n").fetchall()
    assert len(rows) >= 5, rows
    (p, pfp), (f, ffp), (u, ufp), (c, _cfp) = rows[:4]
    rates = json.dumps([i / 1000 for i in range(200)])
    now = "2026-11-14T00:00:00+00:00"
    def row(n, fp, **over):
        base = dict(trial_n=n, rule_id=yardstick.RULE_ID, store_fingerprint=fp, status="measured",
                    draws=200, arm_rate=0.187, beaten=187, percentile=0.935, rates_json=rates,
                    trade_ratio=1.04, turnover_ratio=0.98, reproduced=1, git_sha="verify", measured=now)
        base.update(over)
        return store.YardstickRow(**base)
    with conn:
        store.insert_roles(conn, [store.RoleRow(trial_n=c, role="control", source="backfill", measured=now)])
        store.insert_yardstick(conn, row(p, pfp))
        store.insert_yardstick(conn, row(f, ffp, arm_rate=0.150, beaten=150, percentile=0.75))
        store.insert_yardstick(conn, row(u, ufp, status="unmatched", arm_rate=0.199, beaten=199,
                                         percentile=0.995, trade_ratio=2.6))
    store.write_snapshot(conn, d / "web" / "data" / "lab.json")
    print(json.dumps({"pass": p, "fail": f, "unmatched": u, "control": c}))
    EOF
    $V api RUN GET /sera/methods/M0007
    ```
    then on the new `NN-api-*.html`: `grep -o 'Beats look-alikes: cleared[^"<]*' F | sort -u`, `grep -c 'missed (beat 150 of 200)' F`, `grep -c 'missed (look-alikes traded too differently to compare)' F`, `grep -c 'not measured yet' F`, `grep -ci 'comparison book' F` → passes when the first prints exactly one line, `Beats look-alikes: cleared (beat 187 of 200)` (only the measured pass is ever drawn as a pass), and each count is at least 1. If the page still shows the J3 text, `touch $D/web/lib/sera/lab.ts` and re-run the `api` line (the dev server recompiles on the import's change)
  - **J5** · traces R2.4 — same run, after J4: `$V shoot RUN --theme dark --width 390 /sera/methods/M0007`, `$V shoot RUN --theme light --width 390 /sera/methods/M0007`, `$V shoot RUN --theme dark --width 1280 /sera/methods/M0007 /sera/how`, `$V shoot RUN --theme light --width 1280 /sera/methods/M0007` → passes when every `shoot` exits 0 (no HTTP error, no console error, no horizontal scroll) and, reading the PNGs: at 390 each variant card lists seven marks with "Beats look-alikes" spelled out and one card carries the dashed "COMPARISON BOOK" chip beside its name; at 1280 the variants table has a seventh mark column whose header reads "Beats look-alikes", the control row carries the chip after its name, and the how page shows seven hurdle cards with "Better than random picks" last
  - **J6** · traces R2.4 — `cd web && npx tsc --noEmit && npm test -- lib/sera app/sera` → passes when every test passes, including `derive.test.ts` 'the random-twin condition' and 'comparison books' and `view.test.ts` 'draws every random-twin state in words…' and 'puts the two new engine labels into plain words for the redone panel…', which exercise the measured-pass, measured-fail, unmatched, not-applicable, not-measured, recent-unmeasured and control-arm states the committed snapshot cannot yet show
- Neighbor check: the Overview and the methods list read the same condition list. In the J3 run, `$V api RUN GET /sera` and `$V api RUN GET /sera/methods` → both answer 200; `/sera` shows "of 7" (the closest-miss tile and the progress chart title) and `/sera/methods` shows `/7` on every tested row; `$V shoot RUN --width 390 /sera /sera/methods` exits 0
- Cost: none (offline run, no LLM, no `--net`)

**Exit criteria:** `test_lab_snapshot.py` (including the committed-export sync test) and `test_lab_gate_wording.py` pass; `npx tsc --noEmit && npm test` pass; `web/data/lab.json` is snapshot 8 and `lab/lab.sqlite` is unmodified; the method page shows "Beats look-alikes" as a seventh condition in plain words in both themes at 390 and 1280, and an arm with no reading reads "not measured yet" and is never drawn as a pass; the redone panel shows neither new engine label as raw text.

**Commit (explicit paths only; never `git commit -a`; `lab/lab.sqlite` is never staged — invariant 2; `web/data/lab.json` is the one derived file this phase commits):**
```bash
cd /home/miftah/.worktrees/seer/random-twin-yardstick
git checkout -- lab/lab.sqlite 2>/dev/null; git status --porcelain lab   # must print nothing
git add engine/src/seer_engine/lab/store.py engine/tests/test_lab_snapshot.py \
        engine/tests/test_lab_gate_wording.py \
        web/lib/sera/types.ts web/lib/sera/derive.ts web/lib/sera/glossary.ts \
        web/lib/sera/fixture.ts web/lib/sera/lab.ts web/lib/sera/lab.test.ts \
        web/lib/sera/derive.test.ts web/lib/sera/glossary.test.ts \
        web/app/sera/methods/view.ts web/app/sera/methods/view.test.ts \
        'web/app/sera/methods/[id]/page.tsx' 'web/app/sera/methods/[id]/method.module.css' \
        web/app/sera/methods/page.tsx web/app/sera/how/view.ts web/app/sera/how/view.test.ts \
        web/app/sera/how/page.tsx web/app/sera/overview.ts web/app/sera/overview.test.ts \
        web/components/sera/diagrams/geometry.ts web/data/lab.json \
        .claude/skills/verify-seer/features/sera.md
git commit -m "sera: the random-twin check as a seventh condition, and comparison books (random-twin-yardstick phase 5)"
```

## Handoffs

- **Integrator:** `web/data/lab.json` is derived. Do not merge it; regenerate it from the merged `lab/lab.sqlite` with step 6's read-only export after every phase has landed, then run `test_the_committed_snapshot_is_the_export_of_the_committed_database`.
- **Post-merge lab operation (out of scope, `## Next` in the index):** until `lab roles --backfill` and `lab yardstick --pending` run on `main`, every trial publishes `role: null, yardstick: null`, so the Overview's random-twin bar reads 0 and every method page reads "not measured yet". That is the correct reading of the committed data, not a bug.
- **Phase 4 (skills):** `.claude/skills/update-stale-sera-methods-page/` and the Sera skills describe the page's conditions; if they say "six", phase 4 owns that text. This phase changes no skill except the `verify-seer` feature map.
- **Phase 3 (settled at reconcile, Decision D11):** `store.YardstickRow` has one keyword per `trial_yardstick` column, and a not-applicable row is `draws=0, beaten=0, percentile=None, rates_json="[]", trade_ratio=None, turnover_ratio=None, arm_rate=<the arm's rate or None>`. Step 4's `_twin_row` call and the J2/J4 scripts use exactly those shapes (J2/J4 write only measured and unmatched rows, each with `percentile == beaten / 200`). `_snapshot_yardstick` reads `status, percentile, draws, beaten, arm_rate, rates_json, trade_ratio` and publishes `beaten` as null for a not-applicable row.
- **Phase 3 (assumption):** `store.YARDSTICK_LABEL` is `beats <number>% of random twins`. Step 5's pin fails loudly if it is not, and `derive.YARDSTICK_FAILURE_PREFIX` / `_SUFFIX` then move with it.
- **Phase 1 (confirmed at reconcile):** `store.verdict` puts `CONTROL_LABEL` in a recorded control's `failedNow` for any trial with a `control` role row, P7a seed rows included (phase 1's rule reads only `role_of_trial`), so step 4's test on trial 53 holds.
- **Owned here (settled at reconcile, Decision D15):** `RedonePanel` printed `trial.failedNow.join(', ')` raw ("Still misses: …"), which would show the engine's two new labels to the owner. Step 10's `missInWords` and Step 11 (h) map those two labels to plain words there; every existing label is printed as it was.

## Rollback

Revert this phase's commit(s). That restores `SNAPSHOT_VERSION = 7`, the six-condition web, and the
version-7 `web/data/lab.json`; regenerate the JSON from the then-current `lab/lab.sqlite` with step
6's export if the lab has moved since. Phases 1-4 are unaffected: the role and twin tables stay in
the database, `failedNow` keeps carrying the labels, and a version-7 page reads the two unknown
labels as unknown, which `lab.test.ts:60` would then flag until this phase is re-applied.

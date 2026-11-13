# Phase 4: The yardstick as a screen condition

**Plan set:** `RANDOM_TWIN_YARDSTICK_PLAN.md`
**Analysis:** `.workflows/analyze/20261113-125454-Y7RT_code_analyzer.md`
**Satisfies:** R2 — "Judge ideas against it. An arm passes only if it beats roughly the top tenth of random books on its own setup" (added as a seventh condition, index Decision D2)
**Criteria:** R2.1, R2.2, R2.3
**Depends on:** Phase 3 (and through it phases 1 and 2)
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/lab`

---

## Goal

After this phase the random-twin yardstick is a condition of the dev screen in the three places
that decide anything. `lab run` measures every non-control arm that clears the other six
conditions before it takes the write lock, and records the arm eligible only if it out-earned at
least `YARDSTICK_MIN_PERCENTILE` (0.90) of its twins. `store.verdict` fails an arm whose reading is
below the bar or `unmatched`, and an arm recorded on or after `YARDSTICK_SINCE` that was never
measured. `lab promote` (hardgate D20) refuses any arm without a reading that clears, whatever its
age. The design gets its dated §10 revision, and the backfill gets a runbook.

## Interface Contract

The reconciler reads this section to detect cross-phase conflicts. Be exact and exhaustive.

**Deletes:** nothing.

**Renames:** nothing.

**Creates:**
- `store.YARDSTICK_SINCE = "2026-11-14"` (`lab/store.py`, directly after phase 3's `YARDSTICK_LABEL`)
- `store._yardstick_binds(conn, trial, failed) -> bool` (`lab/store.py`, private, directly above `verdict`)
- `runner.Ran.yardstick: store.YardstickRow | None = None` (new last field of `Ran`, directly after phase 1's `role: str | None = None`)
- `runner._luck_inputs`, `runner._provisional_dsrs`, `runner._due_for_yardstick`, `runner._measure_yardsticks` (`lab/runner.py`, private, between `_f` and `trial_rows`). **No row builder of its own**: a reading becomes a row through phase 3's `store.YardstickRow.from_measurement` (settled at reconcile)
- `hardgate.yardstick_refusal(conn, method_id, candidate_id) -> str | None` (`lab/hardgate.py`, after `book_twin_refusal`)
- hardgate decision **(D20)** in the module docstring and in `check`
- `lab run --jobs J` (default 2), validated by phase 3's `commands/lab.py:_positive_count`; each reading is logged with phase 3's `commands/lab.py:_yardstick_line(candidate_id, row, note)` (no `_job_count` and no second `_yardstick_line`: settled at reconcile)
- `labkit.stamp_yardstick(conn, trial_ns, *, status=..., percentile=..., draws=...)` (`engine/tests/labkit.py`; phase 3 has no fixture helper, so this is the one)
- `prereg.gate_text` names the random-twin yardstick (Step 16b; settled at reconcile, Decision D13)
- `engine/tests/test_lab_yardstick_gate.py` (new)
- `docs/runbooks/yardstick-backfill.md` (new); `docs/plans/2026-10-04-method-lab-design.md` §10

**Signature changes:**
- `store._blocking(trial, funding=None)` -> `store._blocking(trial, funding=None, reading=None)`
- `prereg.gate_text(conn=None)` signature unchanged; its `head` gains one clause naming the yardstick bar, built from `store.YARDSTICK_MIN_PERCENTILE` (still one line; the `conn` form still only appends)
- `runner.trial_rows(conn, method, results, *, fingerprint, git_sha, deposits=(), schedule=OWNER_SCHEDULE_TEXT)` -> adds `yardsticks: Mapping[str, yardstick.Measurement] | None = None`. `None` (the default) means the rule is off for that caller: byte-for-byte what it recorded before.
- `runner.run_method(conn, method, path, data, *, git_sha, require_commit=True, amend=False)` -> adds `yardstick_jobs: int = 1, measure: Callable[..., yardstick.Measurement] = yardstick.measure`

**Requires (from earlier phases):**
- Phase 1: `store.CONTROL_LABEL`, appended in `store.verdict` after the luck label and in `runner.trial_rows` to a control arm's `failed`. This phase reads `CONTROL_LABEL in failed` as "this arm is a control". Also `store.RoleRow(trial_n, role, source, measured)` and `store.insert_roles(conn, rows)` (one test only). Also phase 1's role-aware status in `run_method` (`dev-eligible` only if a non-control arm is eligible). It reads `r.trial.eligible`, which this phase's label already makes False for an arm that loses to its twins. Also phase 1's `Ran.role` field, its `control_shape` import in `runner.py`, its `store.insert_roles(...)` block in `run_method`, and its `demoted` clause in `reevaluate_method` (Step 9b of phase 1), all of which this phase's anchors quote.
- Phase 2: `yardstick.measure(market, dividends, spy_dividends, candidate, *, initial_idr, contributions, draws=DRAWS, jobs=1, expect=None) -> Measurement`; `Measurement(status, draws, arm_rate, beaten, percentile, rates, trade_ratio, turnover_ratio, reproduced)` whose `__post_init__` is the source of truth for a reading's shape (Decision D11: a not-applicable reading has `draws=0, beaten=0, percentile=None`; measured and unmatched have `percentile == beaten / draws`); `STATUS_MEASURED`, `STATUS_NOT_APPLICABLE`, `STATUS_UNMATCHED`; `RULE_ID`; `DRAWS`; `Unreproducible`. **`lab/yardstick.py` must not import `lab/runner.py`**: this phase imports `yardstick` at `runner`'s module scope, because `measure=yardstick.measure` is a default argument.
- Phase 3: `store.YardstickRow` with exactly the `trial_yardstick` column names as fields (`trial_n, rule_id, store_fingerprint, status, draws, arm_rate, beaten, percentile, rates_json, trade_ratio, turnover_ratio, reproduced, git_sha, measured`) and `YardstickRow.from_measurement(m, *, trial_n, rule_id, store_fingerprint, checked, git_sha, measured)`; `store.insert_yardstick(conn, row) -> bool`; `store.yardstick_of(conn, trial_n) -> sqlite3.Row | None`, None when the table is absent (a `mode=ro` connection to the committed lab must work); `store.YARDSTICK_MIN_PERCENTILE`; `store.YARDSTICK_LABEL`; and **`store.yardstick_clears(row)` accepting any `Mapping[str, Any]` as well as a `sqlite3.Row`** (phase 3 states and tests it). This phase calls it on `dataclasses.asdict(YardstickRow)` and on plain dicts, so there is one clearing rule. Also `commands/lab.py:_positive_count` and `commands/lab.py:_yardstick_line(candidate_id, row: store.YardstickRow, note: str) -> str`, and the `lab yardstick [MNNNN ...] [--arm C] [--pending] [--limit N] [--jobs J]` command (used by the Proof and the runbook).

**Leaves alone (owned by others):** `lab/yardstick.py` (phase 2); the `trial_yardstick` table, its helpers, `yardstick_due`, `_positive_count`, `_yardstick_line` and `lab yardstick` (phase 3); `trial_roles`, `demote_method`, `lab roles`, `lab reevaluate --demote`, the `demoted` clause in `reevaluate_method` (phase 1); `_snapshot_trial`, `snapshot`, `SNAPSHOT_VERSION`, `web/`, `web/data/lab.json` (phase 5); `lab/lab.sqlite`; every recorded method file; `DSR_MIN`, `DSR_POLICY`, `owner_failures`, `published_verdict`'s test-row branch; every committed `docs/lab/prereg/MNNNN.md` (frozen records).

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/store.py` | modify | `YARDSTICK_SINCE`; `_yardstick_binds`; one block in `verdict` (:1810) after phase 1's control block; `Verdict` docstring (:1436); `_blocking` (:1957) takes `reading`; `reevaluate_method` (:2071) passes it |
| `engine/src/seer_engine/lab/runner.py` | modify | imports (:69-94); `Ran` (:119-122); four private helpers before `trial_rows` (:524); `trial_rows` takes `yardsticks`; `run_method` (:659) measures before `begin_immediate` (:725) and inserts the readings with the trial batch (after phase 1's role rows); module docstring item 4 (:22) |
| `engine/src/seer_engine/lab/hardgate.py` | modify | module docstring gains (D20) after (D19) (:886-887); `yardstick_refusal` after `book_twin_refusal` (:1236); `check` docstring (:2076-2085) and the D20 clause between D18 (:2174) and D19 (:2175) |
| `engine/src/seer_engine/lab/prereg.py` | modify | `gate_text`'s head names the yardstick bar (:234-239), and one docstring sentence (Step 16b) |
| `engine/src/seer_engine/commands/lab.py` | modify | `lab run --jobs` (:310, type phase 3's `_positive_count`); `_run` passes it (:1973) and logs readings with phase 3's `_yardstick_line` (:1978); the "Refused by the hard gate" header (:1666-1669) names the yardstick |
| `engine/tests/labkit.py` | modify | `stamp_yardstick` after `stamp_provenance` (:156) |
| `engine/tests/test_lab_yardstick_gate.py` | create | R2.1 and R2.2 tests |
| `engine/tests/test_lab_hardgate.py` | modify | `stamp_yardstick` beside the stamps of promotable fixtures; `_method(measured=...)`; D20 tests (R2.3) |
| `engine/tests/test_lab_prereg.py` | modify | `_real_method` (:210) and the helper at :181 stamp a clearing reading, as `lab run` now records one; one test that the gate text names the yardstick bar (Step 16b) |
| `engine/tests/test_lab_status.py` | modify | `_method_at` (:374) stamps a clearing reading |
| `engine/tests/test_lab_gate_wording.py` | modify | a guard that no shipped yardstick document states a bar the lab does not apply |
| `docs/plans/2026-10-04-method-lab-design.md` | modify | append §10 after §9 (:602) |
| `docs/runbooks/yardstick-backfill.md` | create | the three post-landing commands, cost, resume, stage, commit style |
| `.claude/skills/explore-and-experiment-new-method/SKILL.md` | modify | step 6 (:221-240), the Promotion bullets (:380-390), the quick reference (:588) |
| `.claude/skills/sera-the-explorer/SKILL.md` | modify | the dev-eligible harvest bullet (:164-185) and the Refill step (:192) |
| `.claude/skills/update-stale-sera-methods-page/SKILL.md` | modify | the constants the snapshot's `gate` is resolved from (:36-38) gain `store.YARDSTICK_MIN_PERCENTILE`; every other hit of Step 19's grep |
| `CLAUDE.md` | modify | the "Experiment protocol" paragraph (:84-89), one clause |
| `.claude/skills/verify-seer/features/lab-cli.md` | modify | Sub-features, Driving, Gotchas |

All line numbers are today's (`f83fb237`). Phases 1-3 edit `store.py`, `runner.py`, `commands/lab.py`
and `lab-cli.md` first. Each step below names the earlier-phase addition it sits after, quoting the
file as the earlier phases leave it.

No other test file needs a clearing reading (item checked at reconcile): the only test files that
call `hardgate.check` or drive `lab promote` are `test_lab_hardgate.py`, `test_lab_prereg.py`,
`test_lab_status.py` (all three edited here) and `test_lab_fold_verdict.py`, whose one `check` call
(`test_the_promote_gate_still_refuses_what_it_refused_before`, :301) is refused by the fold-majority
clause, which runs before D18 and D20, so it needs no reading. `test_lab_test_window.py:418` only
builds an argv. Phase 1's `test_lab_roles.py` and phase 3's `test_lab_yardstick_record.py` never
call `check` or promote.

## Implementation Steps

### Step 1: `YARDSTICK_SINCE`
**File:** `engine/src/seer_engine/lab/store.py`, immediately after phase 3's line `YARDSTICK_LABEL = f"beats {YARDSTICK_MIN_PERCENTILE:.0%} of random twins"` (which phase 3 placed after phase 1's `CONTROL_LABEL`, after `is_luck_label`), before the `# The N the luck test deflates by` comment.
**Change:** add the constant and the reason for it.
**Code:**
```python
# The day the random-twin yardstick became a condition of the dev screen
# (RANDOM_TWIN_YARDSTICK_PLAN.md Decision D5), compared with ``trials.run_at`` as text. ISO-8601
# strings sort as dates, and "2026-11-14" sorts before every timestamp of that day, so "recorded
# on or after it" is ``str(run_at) >= YARDSTICK_SINCE``.
#
# **Why a date at all.** On 2026-11-13 the committed lab held 256 dev arms that read eligible at
# today's bars and not one yardstick reading. Failing every unmeasured arm at once would flip all
# of them on the day the code lands, before ``lab yardstick --pending`` has measured one, and the
# shared lab and the site would read "nothing is eligible" for the hours the backfill takes, for a
# reason that is a queue and not a result. So the condition is staged:
#
# - an arm recorded BEFORE this date is judged by its reading once it has one, and by the six
#   other conditions alone until then;
# - an arm recorded ON OR AFTER it was measured by ``lab run`` itself, so an unmeasured one is a
#   hole in the record and fails closed.
#
# ``lab promote`` (hardgate D20) is not staged: the look and the owner's money are never spent on
# an arm nobody measured, whatever its age.
YARDSTICK_SINCE = "2026-11-14"
```
**Impact:** none on its own.

### Step 2: `_yardstick_binds`, the rule `verdict` reads
**File:** `engine/src/seer_engine/lab/store.py`, directly above `def verdict(` (today :1810, after `dsr_at`).
**Change:** one private function holding Decision D5's rule. It reads phase 1's control label from
the failures already decided, so a control is never judged on its yardstick (phase 1 has already
failed it).
**Code:**
```python
def _yardstick_binds(
    conn: sqlite3.Connection,
    trial: Mapping[str, Any] | sqlite3.Row,
    failed: tuple[str, ...],
) -> bool:
    """Does the random-twin yardstick fail ``trial`` today? ``failed`` is every other label
    ``verdict`` has already decided for it, the control label included.

    - **A control arm is never judged on it.** ``CONTROL_LABEL`` already fails a control, and a
      control is the arm the method registered in order to be beaten. Adding a second label to
      it would describe the control, not the idea.
    - **A reading decides when there is one** (``yardstick_clears``): below the bar or
      ``unmatched`` fails; at or above the bar, or ``not-applicable``, passes. This binds every
      arm whatever its run date, which is how an old arm is re-judged once the backfill has
      measured it.
    - **No reading fails only an arm that would otherwise pass and was recorded on or after
      ``YARDSTICK_SINCE``.** Such an arm went through a ``lab run`` that measures, so a missing
      reading is a hole in the record. An older arm is left to its other conditions until it is
      measured (Decision D5). An arm that already fails something else gains nothing from a
      second label for a measurement nobody took.
    """
    if CONTROL_LABEL in failed:
        return False
    clears = yardstick_clears(yardstick_of(conn, int(trial["n"])))
    if clears is None:
        return not failed and str(trial["run_at"]) >= YARDSTICK_SINCE
    return not clears
```
**Impact:** none until Step 3 calls it.

### Step 3: the yardstick in `verdict`
**File:** `engine/src/seer_engine/lab/store.py`, `verdict` (today :1810-1878).
**Change (body):** as phase 1 leaves `verdict`, its body ends
```python
    if dsr is None or dsr < DSR_MIN:
        failed = failed + (DSR_LABEL,)
    # An arm registered to be beaten never makes its method eligible, whatever its numbers. Read
    # from the recorded role, never from the method file, so this read opens nothing; a trial with
    # no role row (or a database without the table) is judged exactly as before.
    if role_of_trial(conn, trial["n"]) == CONTROL_ROLE:
        failed = failed + (CONTROL_LABEL,)
    return Verdict(
```
Insert the block below directly after `failed = failed + (CONTROL_LABEL,)` and **before**
`return Verdict(`. Label order is then: owner conditions, the luck label, `CONTROL_LABEL`,
`YARDSTICK_LABEL` (the yardstick label always last).
**Code:**
```python
    # The seventh condition (RANDOM_TWIN_YARDSTICK_PLAN.md, phase 4): did this arm out-earn the
    # random twins that repeat its every decision with the picked stocks swapped? Last, after the
    # control label, and never on a control. Staged by run date for an arm with no reading; see
    # `_yardstick_binds` and `YARDSTICK_SINCE`.
    if _yardstick_binds(conn, trial, failed):
        failed = failed + (YARDSTICK_LABEL,)
```
**Change (docstring):** in `verdict`'s docstring replace the sentence
`**Nothing is ever returned verbatim.** Every one of the six conditions is decided here:` with
`**Nothing is ever returned verbatim.** Every condition is decided here:`, and append this bullet
directly after the `- the **luck** test is decided on ``dsr_at(conn, trial, g.n)`` -- ...` bullet
(phase 1 added no bullet there; its control rule is a separate paragraph, `**A recorded control arm
is never eligible**`, further down, and stays as it is):
```text
    - the **random-twin yardstick** is decided on the trial's latest ``trial_yardstick`` reading
      (``yardstick_of``): below ``YARDSTICK_MIN_PERCENTILE`` or ``unmatched`` fails, and its label
      goes last. An arm with no reading fails only when every other condition passes and it was
      recorded on or after ``YARDSTICK_SINCE`` (Decision D5). A control arm is never judged on
      it. On a lab with no reading and no trial on or after that date, this function returns
      exactly what it returned before the yardstick existed (plan invariant 5).
```
**Impact:** `best_dev_eligible`, `reevaluate_method`, `lab status`, `published_verdict` (dev rows
only) and the snapshot's `failedNow` now carry `YARDSTICK_LABEL` for an arm that fails it. On the
committed lab (no reading, latest `run_at` `2026-11-13T04:17:58+00:00`, read back this session)
nothing changes. `published_verdict`'s test-row branch (:1907) does not call `verdict` and is left
as it is.

### Step 4: `Verdict`'s ordering sentence
**File:** `engine/src/seer_engine/lab/store.py:1436-1439` (`Verdict` docstring, first paragraph).
**Change:** phase 1 rewrote this paragraph to
```text
    ``failed`` is the ordered tuple of failure labels (``trials.failed`` is the same list,
    "; "-joined): owner conditions first in ``dev.FAILURE_LABELS`` order, then the luck label,
    then ``CONTROL_LABEL`` for a trial recorded as a control arm. ``eligible`` is
    ``failed == ()``, always.
```
Replace it with:
**Code:**
```text
    ``failed`` is the ordered tuple of failure labels (``trials.failed`` is the same list,
    "; "-joined): owner conditions first in ``dev.FAILURE_LABELS`` order, then the luck label,
    then ``CONTROL_LABEL`` for a trial recorded as a control arm, and ``YARDSTICK_LABEL`` last.
    ``eligible`` is ``failed == ()``, always.
```
**Impact:** docs only.

### Step 5: the second, independent no in `_blocking` and `reevaluate_method`
**File:** `engine/src/seer_engine/lab/store.py:1957-2011` (`_blocking`) and `:2071` (its one call).
**Change:** `_blocking` gains `reading` and says the yardstick's no in its own sentence, written
without calling `yardstick_clears` or `_yardstick_binds`. It is the same rule written a second time,
in the function's established style, against the same constants. `reevaluate_method` passes the
reading and its refusal stops naming a count of conditions.
**Code (full replacement of `_blocking`):**
```python
def _blocking(
    trial: Mapping[str, Any] | sqlite3.Row,
    funding: Mapping[str, Any] | sqlite3.Row | None = None,
    reading: Mapping[str, Any] | sqlite3.Row | None = None,
) -> tuple[str, ...]:
    """The second, independent no: why this trial may **not** take the ``rejected`` edge.

    ``owner_failures`` derives the same four conditions and ``verdict`` reads it, so these
    comparisons are written here a second time **on purpose**. Two owner-set bars moved in this
    plan set -- the luck threshold (phase 4) and the drawdown threshold (phase 8) -- and a gate
    that loosens on two axes at once should not be able to promote a method through a single
    expression. A future change to ``owner_failures`` has to get past this too. That is also why
    the money-weighted branch below is spelled out rather than delegated to ``dev.beats_spy_tr``.

    Phrased as sentences with the numbers in them, because this text goes into the refusal a
    human reads.

    **It reads the dev SCREEN**, ``tuning.DEV_MAX_DRAWDOWN``, because the edge it guards is
    ``rejected -> dev-eligible`` -- a research decision, not a funding one. It must read the same
    number ``owner_failures`` reads or this guard fires on its own module's verdict: measured on
    2026-10-14, holding this at ``MAX_DRAWDOWN`` while the screen moved would have raised
    ``LabError`` for seven recorded trials across M0050, M0058, M0082 and M0085, all of them
    ``rejected``, and ``lab reevaluate`` with no argument sweeps exactly those. The point of the
    repetition is that the comparison is written twice in two places, not that it is written
    against two different bars.

    **The random-twin yardstick is said here a second time too** (RANDOM_TWIN_YARDSTICK_PLAN.md
    phase 4). ``reading`` is ``yardstick_of(conn, trial["n"])``, or None. The rule is
    ``_yardstick_binds``'s, the one ``verdict`` applies, written out again without calling it or
    ``yardstick_clears``: a ``measured`` reading below ``YARDSTICK_MIN_PERCENTILE`` says no, any
    status other than ``measured`` or ``not-applicable`` says no (``unmatched`` is the one there
    is), and no reading says no only for an arm recorded on or after ``YARDSTICK_SINCE``. Control
    arms never reach this function: ``verdict`` fails them first, and only an arm ``verdict``
    calls eligible is checked here.
    """
    from seer_engine.backtest import dev, tuning

    out: list[str] = []
    mwr = None if funding is None else funding["mwr"]
    spy_mwr = None if funding is None else funding["spy_tr_mwr"]
    if mwr is not None and spy_mwr is not None:
        if float(mwr) <= float(spy_mwr):
            out.append(
                f"money-weighted return {mwr!r} does not beat the SPY TR fed the same deposits "
                f"{spy_mwr!r}"
            )
    else:
        total, bench = trial["total_return"], trial["spy_tr_return"]
        if total is None or bench is None or float(total) <= float(bench):
            out.append(f"total return {total!r} does not beat SPY TR {bench!r}")
    dd = trial["max_drawdown"]
    if dd is None or float(dd) > tuning.DEV_MAX_DRAWDOWN:
        out.append(f"max drawdown {dd!r} is outside the {tuning.DEV_MAX_DRAWDOWN:.0%} screen")
    factor = trial["profit_factor"]
    if factor is None or float(factor) < tuning.MIN_PROFIT_FACTOR:
        out.append(f"profit factor {factor!r} is under {tuning.MIN_PROFIT_FACTOR}")
    count = trial["trades"]
    if count is None or int(count) < dev._MIN_TRADES:
        out.append(f"{count!r} closed trades is under {dev._MIN_TRADES}")
    if OWNER_INPUTS_LABEL in recorded_labels(trial["failed"]):
        out.append(
            f"it recorded {OWNER_INPUTS_LABEL!r}, which is a property of the candidate and which "
            f"no threshold re-decides"
        )
    if reading is not None:
        status = str(reading["status"])
        pct = reading["percentile"]
        if status == "measured":
            if pct is None or float(pct) < YARDSTICK_MIN_PERCENTILE:
                out.append(
                    f"it out-earned {reading['beaten']!r} of {reading['draws']!r} random twins "
                    f"(share {pct!r}), under the {YARDSTICK_MIN_PERCENTILE:.0%} bar"
                )
        elif status != "not-applicable":
            out.append(
                f"its random-twin yardstick reads {status!r}, and only a measured share at or "
                f"above {YARDSTICK_MIN_PERCENTILE:.0%}, or a book with no picked stock, clears it"
            )
    elif str(trial["run_at"]) >= YARDSTICK_SINCE:
        out.append(
            f"it was recorded at {trial['run_at']}, on or after {YARDSTICK_SINCE} when the "
            f"random-twin yardstick became a condition, and it has never been measured against "
            f"its twins"
        )
    return tuple(out)
```
The status literals `"measured"` and `"not-applicable"` are typed here on purpose, so that this
check does not share code with the first one. A test (Step 13,
`test_the_independent_check_says_no_in_its_own_words`) pins them to `yardstick.STATUS_MEASURED`
and `yardstick.STATUS_NOT_APPLICABLE`.

**Code (in `reevaluate_method`, today :2071-2079):** replace
```python
        blocking = _blocking(t, funding_of(conn, t["n"]))
        if blocking:
            raise LabError(
                f"{t['candidate_id']} reads eligible at {DSR_LABEL} under the {g.policy} policy "
                f"(N={g.n}), but a second, independent check of its recorded numbers says "
                f"otherwise: {'; '.join(blocking)}. Refusing to move {method_id} -- a method may "
                f"only cross this edge when every one of the five conditions clears the bar in "
                f"force today."
            )
```
with
```python
        blocking = _blocking(t, funding_of(conn, t["n"]), yardstick_of(conn, int(t["n"])))
        if blocking:
            raise LabError(
                f"{t['candidate_id']} reads eligible at {DSR_LABEL} under the {g.policy} policy "
                f"(N={g.n}), but a second, independent check of its recorded numbers says "
                f"otherwise: {'; '.join(blocking)}. Refusing to move {method_id} -- a method may "
                f"only cross this edge when every condition clears the bar in force today."
            )
```
As phase 1 leaves `reevaluate_method`, its loop also carries phase 1's `demoted` clause
(`demoted = DEMOTION_MARKER in str(row["analysis"] or "")` after `status = ...`, and
`if demoted or not bool(t["eligible"]):` after the `_blocking` refusal). Those lines are outside the
snippet replaced above and are kept verbatim: a demoted method's recorded-eligible arm that clears
every condition **including the yardstick** takes the way back. `demote_method` does not call
`_blocking`.
**Impact:** the `rejected -> dev-eligible` door cannot open for an arm whose reading fails, or for
an unmeasured arm recorded since `YARDSTICK_SINCE`. `verdict` already refuses both; `_blocking`
is the second no. An old unmeasured arm opens the door exactly as before (D5). Existing callers of
`_blocking(row)` and `_blocking(row, funding)` (`test_lab_gate_policy.py:676`) are unchanged.

### Step 6: runner imports, `Ran`, and the module docstring
**File:** `engine/src/seer_engine/lab/runner.py`
**Change 6a (imports, :71-94):** add `Callable` and `Mapping`, `asdict`, and `yardstick`. Phase 1
already changed the lab import line to `from seer_engine.lab import control_shape, store, twins`;
this step extends that same line. (No `json`: the row is built by phase 3's
`YardstickRow.from_measurement`.)
**Code:** the import block becomes
```python
import logging
import sqlite3
import statistics
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, replace
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any

from seer_engine import research
from seer_engine.backtest import dev
from seer_engine.backtest.dev import Candidate, DevRow
from seer_engine.backtest.metrics import external_cashflows
from seer_engine.backtest.market import Market
from seer_engine.backtest.runner import INITIAL_IDR
from seer_engine.commands.backtest_dev import daily_moments, month_end_curve, registry_problem
from seer_engine.fundamentals import coverage
from seer_engine.lab import control_shape, store, twins, yardstick
from seer_engine.lab.method import METHOD_ID, Amendment, Method, config_digest, config_text, source_sha
from seer_engine.lab.real_costs import real_cost_problem
from seer_engine.sim.contributions import OWNER_MONTHLY, ContributionSchedule
from seer_engine.strategies.allocator import MarketAware
```
**Change 6b (`Ran`):** as phase 1 leaves it, `Ran`'s docstring ends with phase 1's `role`
paragraph (`... which records no role.`) and its fields end with `role: str | None = None`. Append
one paragraph directly after phase 1's `role` paragraph (before the closing `"""`) and one field
directly after `role`:
```python
    ``yardstick`` is the same pattern a third time: the random-twin reading ``run_method`` took for
    this variant before the write lock, as the ``store.YardstickRow`` that will be inserted,
    ``trial_n=0`` until the insert and stamped with ``dataclasses.replace`` afterwards. None when
    the variant was not measured: a control, an arm that failed another condition, or an arm whose
    measurement could not be taken. It defaults to None for the same reason ``moments`` does.
    """

    trial: store.TrialRow
    row: DevRow
    moments: store.MomentsRow | None = None
    funding: store.FundingRow | None = None
    role: str | None = None
    yardstick: store.YardstickRow | None = None
```
(The five existing fields, phase 1's `role` included, are unchanged.)
**Change 6c (module docstring item 4, :22-28):** phase 1 rewrote item 4 for the role-aware status.
Replace phase 1's item 4 with this text, which keeps phase 1's control and role wording and splices
the yardstick in after the DSR sentence:
```text
4. Eligible = the five P7a D8 conditions and ``store.DSR_LABEL`` (DSR >= 0.90 since 2026-10-07;
   LAB_LUCK_GATE_PLAN.md Decision D1), and never for an arm whose rationale reads as a control
   (``store.CONTROL_LABEL``; random-twin-yardstick R3). Since 2026-11-14 also the random-twin
   yardstick (``store.YARDSTICK_LABEL``; RANDOM_TWIN_YARDSTICK_PLAN.md phase 4): every
   non-control arm that clears the others is measured against ``yardstick.DRAWS`` books that
   repeat its every decision with the picked stocks swapped, **before** the write lock, and is
   eligible only if it out-earned at least ``store.YARDSTICK_MIN_PERCENTILE`` of them. Insert the
   trials, each arm's role (``store.trial_roles``) and each reading (``store.trial_yardstick``),
   set the method's ``source_sha`` and status (``dev-eligible`` when any trial is eligible -- so
   only a non-control arm can make it -- else ``rejected``), all in one transaction.
   ``store.verdict`` re-reads a recorded trial against the same thresholds, N, role and reading,
   so a verdict is comparable across time rather than frozen at its run date.
```
**Impact:** import only. `lab/yardstick.py` must not import `runner` (see Requires).

### Step 7: the measurement helpers
**File:** `engine/src/seer_engine/lab/runner.py`, between `_f` (:520-521) and `def trial_rows(` (:524).
**Change:** four private functions. The luck inputs are pulled out of `trial_rows` so the provisional
DSR used to choose whom to measure is computed by the same expression the recorded DSR is. A reading
becomes a row through phase 3's `store.YardstickRow.from_measurement` (Step 8d), not a helper here.
**Code:**
```python
def _luck_inputs(
    conn: sqlite3.Connection, method_id: str, results: Sequence[tuple[DevRow, Any]]
) -> tuple[list[tuple[float, float, float] | None], int, float | None]:
    """The deflated Sharpe's batch inputs for ``results``: each variant's daily moments, the N the
    batch is judged at (``store.pending_gate``) and the variance of the daily Sharpe across every
    recorded dev trial plus this batch.

    One function, two callers. ``trial_rows`` records with it under the write lock;
    ``_provisional_dsrs`` reads it before the lock to decide which arms are worth measuring
    against their random twins. The order of the reads is the order ``trial_rows`` always used.
    """
    prior = store.dev_daily_sharpes(conn)
    moments = [daily_moments(r.stats.daily_returns) for r, _ in results]
    new_sharpes = [m[0] for m in moments if m is not None]
    all_sharpes = prior + new_sharpes
    n_trials = store.pending_gate(conn, method_id, len(results)).n
    var_trials = statistics.variance(all_sharpes) if len(all_sharpes) >= 2 else None
    return moments, n_trials, var_trials


def _provisional_dsrs(
    conn: sqlite3.Connection, method_id: str, results: Sequence[tuple[DevRow, Any]]
) -> list[float | None]:
    """Each variant's DSR as ``trial_rows`` would record it if the lab did not move first.

    Read-only and outside any transaction. A parallel session can record a method between this
    read and the write lock, and N or the variance can move. ``trial_rows`` therefore decides
    again under the lock and fails closed on an arm that turns eligible there without a reading.
    """
    moments, n_trials, var_trials = _luck_inputs(conn, method_id, results)
    out: list[float | None] = []
    for (row, _), m in zip(results, moments, strict=True):
        if m is None or var_trials is None:
            out.append(None)
        else:
            out.append(dev.deflated_sharpe(
                m[0], n_trials, var_trials, len(row.stats.daily_returns), m[1], m[2]
            ))
    return out


def _due_for_yardstick(row: DevRow, dsr: float | None) -> bool:
    """Is this just-simulated arm worth measuring against its random twins?

    Exactly the arms the yardstick can still decide: not a control (a control is the arm a method
    registered to be beaten, and phase 1 already fails it), clear of the five D8 conditions, and
    clear of the luck test at the provisional DSR. Measuring anything else spends two workers and
    minutes on a verdict that is already no.
    """
    if not row.eligible:
        return False
    if dsr is None or dsr < store.DSR_MIN:
        return False
    return control_shape.role_of(row.candidate) != control_shape.ROLE_CONTROL


def _measure_yardsticks(
    conn: sqlite3.Connection,
    method: Method,
    results: Sequence[tuple[DevRow, Any]],
    data: research.ResearchData,
    *,
    capital: Decimal,
    jobs: int,
    measure: Callable[..., yardstick.Measurement],
) -> dict[str, yardstick.Measurement]:
    """Measure every arm ``_due_for_yardstick`` names, keyed by candidate id. Holds no lock.

    Called between ``dev.run_registry`` and ``store.begin_immediate``, because it is the slowest
    thing ``lab run`` does (``yardstick.DRAWS`` simulations per arm) and the write lock is
    lab-wide: every parallel session would wait on it.

    Each arm is re-run at the capital and on the funding it was just simulated with, and
    ``expect`` hands ``measure`` the trade count and total return this run recorded, so a twin
    replays the decisions of the very book that is about to be written. ``yardstick.Unreproducible``
    leaves the arm out of the result: ``trial_rows`` then records it with the yardstick label, and
    ``run_method`` logs the way back. Any other exception is a bug and propagates before anything
    is written.
    """
    dsrs = _provisional_dsrs(conn, method.id, results)
    due = [row for (row, _), dsr in zip(results, dsrs, strict=True) if _due_for_yardstick(row, dsr)]
    out: dict[str, yardstick.Measurement] = {}
    for i, row in enumerate(due):
        met = row.stats.metrics
        log.info(
            "[yardstick %d/%d] %s cleared every other condition: measuring it against its random "
            "twins (%d worker(s))",
            i + 1, len(due), row.candidate.id, jobs,
        )
        try:
            out[row.candidate.id] = measure(
                data.market, data.dividends, data.spy_dividends, row.candidate,
                initial_idr=capital, contributions=OWNER_MONTHLY, jobs=jobs,
                expect=(int(met.trades), _f(met.total_return)),
            )
        except yardstick.Unreproducible as e:
            log.warning(
                "%s: its random twins could not be measured (%s). It will be recorded not "
                "eligible.", row.candidate.id, e,
            )
    return out
```
**Impact:** none until Steps 8-9 call them.

### Step 8: `trial_rows` takes the readings
**File:** `engine/src/seer_engine/lab/runner.py:524-656`
**Change 8a (signature, :524-533):** add `yardsticks` after `schedule`:
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
    yardsticks: Mapping[str, yardstick.Measurement] | None = None,
) -> list[Ran]:
```
**Change 8b (docstring):** append before its closing `"""`:
```text
    ``yardsticks`` is the random-twin reading ``run_method`` took before the lock, per candidate
    id. **None turns the rule off** -- the default, so a caller that never measures gets
    byte-for-byte what this function recorded before the yardstick existed. Any mapping, even an
    empty one, turns it on. Then a non-control arm that clears every other condition, the luck
    test included, gets ``store.YARDSTICK_LABEL`` unless its reading clears (``yardstick_clears``:
    a measured share at or above ``store.YARDSTICK_MIN_PERCENTILE``, or ``not-applicable``). An
    arm that clears everything else and has **no** reading is labelled too. That happens when the
    luck test moved between the provisional read and this one, or the measurement could not be
    taken. The record fails closed; ``lab yardstick`` and ``lab reevaluate`` are the way back. A
    control never gets the label: phase 1's ``CONTROL_LABEL`` already fails it. Every reading
    becomes a ``store.YardstickRow`` on its ``Ran``, eligible or not, because a measurement is
    worth keeping whatever it decided.
```
**Change 8c (luck inputs, :579-585):** replace
```python
    prior = store.dev_daily_sharpes(conn)
    moments = [daily_moments(r.stats.daily_returns) for r, _ in results]
    new_sharpes = [m[0] for m in moments if m is not None]
    all_sharpes = prior + new_sharpes
    gate = store.pending_gate(conn, method.id, len(results))
    n_trials = gate.n
    var_trials = statistics.variance(all_sharpes) if len(all_sharpes) >= 2 else None
```
with
```python
    moments, n_trials, var_trials = _luck_inputs(conn, method.id, results)
```
(The same reads in the same order, so no recorded number moves. Nothing later in the function, as
phase 1 leaves it, reads the local `gate`, so the two `gate` lines go.)
**Change 8d (the label, inside the loop):** as phase 1 leaves the loop, the luck and control labels read
```python
        failed = list(row.failed)
        if dsr is None or dsr < store.DSR_MIN:
            failed.append(store.DSR_LABEL)
        # R3: an arm registered to be beaten never makes its method eligible, whatever its
        # numbers. After the luck label, the order `store.verdict` reads it back in.
        role = control_shape.role_of(c)
        if role == control_shape.ROLE_CONTROL:
            failed.append(store.CONTROL_LABEL)
```
Insert directly after `failed.append(store.CONTROL_LABEL)` (at the loop's indentation, not inside the
`if`):
```python
        # The seventh condition (phase 4): the reading taken before the lock, as the row it becomes
        # (phase 3's one constructor; trial_n=0 until the insert stamps it). Judged by the one
        # clearing rule, `store.yardstick_clears`, on the same mapping the table will hold.
        reading = None if yardsticks is None else yardsticks.get(c.id)
        ystick = None if reading is None else store.YardstickRow.from_measurement(
            reading, trial_n=0, rule_id=yardstick.RULE_ID, store_fingerprint=fingerprint,
            checked=True, git_sha=git_sha, measured=run_at,
        )
        if yardsticks is not None and not failed:
            if ystick is None or not store.yardstick_clears(asdict(ystick)):
                failed.append(store.YARDSTICK_LABEL)
```
`checked=True` because `_measure_yardsticks` always passes `expect` from this very run, on the store
the trial records (`fingerprint` is `data.fingerprint`), so `lab yardstick` on the same store finds
this row and does not measure the arm twice.
**Change 8e (`Ran`):** phase 1 left the call as
`out.append(Ran(trial=trial, row=row, moments=mom, funding=fund, role=role))`. Replace it with
```python
        out.append(Ran(trial=trial, row=row, moments=mom, funding=fund, role=role, yardstick=ystick))
```
**Impact:** `test_lab_runner.py:384` (no `yardsticks`) records exactly what it did.

### Step 9: `run_method` measures before the lock and records the readings
**File:** `engine/src/seer_engine/lab/runner.py:659-869`
**Change 9a (signature, :659-668):**
```python
def run_method(
    conn: sqlite3.Connection,
    method: Method,
    path: Path,
    data: research.ResearchData,
    *,
    git_sha: str,
    require_commit: bool = True,
    amend: bool = False,
    yardstick_jobs: int = 1,
    measure: Callable[..., yardstick.Measurement] = yardstick.measure,
) -> Run:
```
**Change 9b (docstring):** append before its closing `"""`:
```text
    **The random-twin yardstick is measured here, before the write lock.** After the simulations
    and before ``store.begin_immediate``, every arm that is not a control, clears the five D8
    conditions and clears the luck test at the provisional DSR is handed to ``measure``
    (``yardstick.measure``; a test injects its own). It gets this run's capital, funding and
    recorded trade count and total return, and ``yardstick_jobs`` workers. Nothing slow runs
    under the lock, because the lock is lab-wide. The readings go to ``trial_rows``, which labels
    an arm that lost to its twins, and into ``trial_yardstick`` in the same transaction as the
    trials, stamped with the numbers SQLite assigns: a trial and the reading that judged it are
    one record or neither. An ``--amend`` run measures exactly the same way. ``lab test`` never
    does, because a look is not a search.
```
**Change 9c (measure, between :724 and :725):** insert directly after the `dev.run_registry(...)`
call and before `store.begin_immediate(conn)`:
```python
    # The random-twin yardstick, measured HERE: after the simulations and before the write lock.
    # It is the slowest thing a run does, and the lock is lab-wide.
    yardsticks = _measure_yardsticks(
        conn, method, results, data, capital=capital, jobs=yardstick_jobs, measure=measure,
    )
```
**Change 9d (trial_rows call, :736-738):** replace with
```python
        ran = trial_rows(
            conn, method, results, fingerprint=data.fingerprint, git_sha=git_sha,
            deposits=deposits, yardsticks=yardsticks,
        )
```
**Change 9e (the way-back log line):** directly after the `_log_arm` loop (:750-751), insert:
```python
        for r in ran:
            if r.yardstick is None and store.YARDSTICK_LABEL in store.recorded_labels(r.trial.failed):
                log.warning(
                    "%s cleared every other condition but has no random-twin reading (the luck "
                    "test moved under the write lock, or the twins could not be measured), so it "
                    "is recorded not eligible. The way back: `lab yardstick %s --arm %s`, then "
                    "`lab reevaluate %s`",
                    r.trial.candidate_id, method.id, r.trial.candidate_id, method.id,
                )
```
**Change 9f (insert the readings):** as phase 1 leaves `run_method`, the `store.insert_provenance(conn, [...])`
call (ends :807) is followed by phase 1's block
```python
        store.insert_roles(conn, [
            store.RoleRow(trial_n=n, role=r.role, source="recorded", measured=r.trial.run_at)
            for n, r in zip(ns, ran, strict=True)
            if r.role is not None
        ])
```
Insert directly after that block's closing `])`, before the `# The fold verdict of this batch,
computed HERE` comment:
```python
        # The random-twin readings, stamped with the trial numbers SQLite just assigned, in this
        # same transaction: a trial and the reading that judged it are recorded together or not
        # at all. An arm that was not measured contributes no row; `store.verdict` reads "no row"
        # as "not measured", which fails closed for every arm recorded from today.
        for n, r in zip(ns, ran, strict=True):
            if r.yardstick is not None:
                store.insert_yardstick(conn, replace(r.yardstick, trial_n=n))
```
**Impact:** `lab run` takes about `DRAWS` simulations longer per eligible arm, all before the lock.
Phase 1's status line (`dev-eligible` only if a non-control arm is eligible) needs no edit: an
arm that lost to its twins records `eligible=False`.

### Step 10: hardgate (D20), the docstring
**File:** `engine/src/seer_engine/lab/hardgate.py`, the module docstring. Insert after the
paragraph that ends `and read in front of "is its fall honest".` (:886-887) and before the closing
`"""` (:888).
**Change:** the decision, in the docstring's question-and-answer form. **Do not use the substrings
`force`, `override` (outside "no override"), `environ` or `getenv` anywhere in this file:**
`test_there_is_no_override` greps the module source for them.
**Code:**
```text

**(D20) Does the gate check that the variant beat books of its own shape drawn at random? -- Yes,
from 2026-11-14 (RANDOM_TWIN_YARDSTICK_PLAN.md phase 4), and it fails closed: a variant with no
reading is refused as well as one that lost.**

The dev screen compared every arm with SPY and with zero, never with what a no-skill book of the
same shape earns. Measured on the committed lab on 2026-11-13: 45 dev trials belong to the two
deliberately meaningless families (``placebo-hash-order``, ``blind-draw-baseline``); 42 of them beat
SPY and 14 were recorded eligible. Across all 2,051 dev trials on the main window, 362 were. The
screen was grading the shape of a book, not the idea in it.

**What a reading is** is ``lab/yardstick.py``'s definition and nothing else: ``yardstick.DRAWS``
twin books that replay the arm's own recorded decisions (the same dates, weights, entries and
exits) with each picked stock swapped for a randomly drawn index member of similar trading size,
and the share of them the arm out-earned. ``lab run`` measures it before recording and
``lab yardstick`` measures the arms recorded before that; both write ``trial_yardstick``, which
counts against nothing: no trial row, no N, no look.

**The clause.** The variant ``lab promote`` would pre-register must hold a reading that clears
(``store.yardstick_clears``): a measured share at or above ``store.YARDSTICK_MIN_PERCENTILE``, or
``not-applicable`` -- a book that holds no picked stock, such as an ETF switch, which has no stock
to swap. A share below the bar, an ``unmatched`` reading (twins whose trade count or turnover fell
outside half to twice the arm's) and **no reading at all** are refused.

**Why absence refuses here, when (D16) and (D18) leave absence alone.** Those clauses read
evidence the lab cannot always have: a fuller price history that does not exist for every arm, a
method file that may be gone. A yardstick reading is a measurement the lab can always take, for
free, on the store it already has: ``lab yardstick <method>`` is one command away. So "not
measured" is a step not yet run, not evidence missing from the world, and the look and the owner's
money wait for it.

**Why here as well as in ``store.verdict``.** ``verdict`` is staged (Decision D5): an arm recorded
before ``store.YARDSTICK_SINCE`` with no reading is judged on its six other conditions until the
backfill measures it, so the shared lab does not lose every eligible arm on the day the rule
lands. That staging is right for a research screen and wrong for the door to the look. This clause
is the door, and it is not staged. When ``verdict`` already fails an arm on its reading,
``best_dev_eligible`` never names it and this clause never sees it. The clause's own no on a
losing reading is the second, independent one, for the day the two disagree.

**Where it sits in ``check``.** Right after (D18) and before (D19). (D18) asks what the arm *is*;
this asks whether what it earned is more than its shape earns by luck. Both are about the arm
itself and read in front of "whose book is it", "is its fall honest" and "is its control shaped
right".

**What it does not do.** It does not replace the deflated Sharpe. A share among twins is a
statement about one arm against its own shape, and it does not correct for the lab having tried
hundreds of methods; ``store.DSR_MIN`` at the policy's N still does that, unchanged (index Decision
D2). It does not touch the §1 real-money bar.
```
**Impact:** `test_the_module_records_the_yardstick_decision` (Step 14) reads it.

### Step 11: `hardgate.yardstick_refusal` and the clause in `check`
**File:** `engine/src/seer_engine/lab/hardgate.py`
**Change 11a:** insert after `book_twin_refusal` (its `return None` is :1235), before
`def mismatches(` (:1238).
**Code:**
```python
def yardstick_refusal(
    conn: sqlite3.Connection, method_id: str, candidate_id: str
) -> str | None:
    """Why (D20) will not pre-register ``candidate_id`` for ``method_id``; None when it will.

    The sentence, without the "Nothing was written" tail ``check`` adds, in the shape
    ``book_twin_refusal`` returns. The reading is the trial's latest ``trial_yardstick`` row
    (``store.yardstick_of``) and the decision is ``store.yardstick_clears``, the rule
    ``store.verdict`` reads. What differs is what None means: here it refuses.
    """
    from seer_engine.lab import yardstick

    found = conn.execute(
        "SELECT n FROM trials WHERE method_id = ? AND candidate_id = ? AND window = 'dev' "
        "ORDER BY n LIMIT 1",
        (method_id, candidate_id),
    ).fetchone()
    reading = None if found is None else store.yardstick_of(conn, int(found[0]))
    if store.yardstick_clears(reading):
        return None
    bar = store.YARDSTICK_MIN_PERCENTILE
    if reading is None:
        return (
            f"{candidate_id} -- the variant `lab promote` would pre-register -- has never been "
            f"measured against its random twins: books that repeat its every decision (the same "
            f"dates, weights, entries and exits) with each picked stock swapped for a randomly "
            f"drawn index member of similar trading size. Without that reading nobody can say "
            f"whether it earned more than its own shape earns by luck, and the gate fails closed "
            f"on a missing measurement. The way back: `lab yardstick {method_id}`, which writes "
            f"no trial, moves no N and spends no look; once the arm out-earns at least {bar:.0%} "
            f"of its twins this clause is silent"
        )
    if str(reading["status"]) == yardstick.STATUS_UNMATCHED:
        return (
            f"{candidate_id} -- the variant `lab promote` would pre-register -- could not be "
            f"matched by its random twins: their median trade count or turnover fell outside "
            f"half to twice its own, so any margin over them would be partly fees and churn, and "
            f"an unmatched reading never clears. The way back: register an arm whose shape its "
            f"twins can follow and run it as an amendment, which costs no method id"
        )
    pct = reading["percentile"]
    shown = "an unknown share" if pct is None else f"{float(pct):.1%}"
    return (
        f"{candidate_id} -- the variant `lab promote` would pre-register -- out-earned only "
        f"{reading['beaten']} of its {reading['draws']} random twins ({shown}), under the "
        f"{bar:.0%} bar: what it earned is what books of its own shape, holding stocks nobody "
        f"chose, earn often enough to be luck. The way back: an arm that beats its twins, run as "
        f"an amendment, which costs no method id"
    )
```
**Change 11b (`check` docstring, :2081-2085):** replace the sentence
`(D18) then asks what that variant *is* and refuses a control arm, and (D19) asks whose book it is`
with
`(D18) then asks what that variant *is* and refuses a control arm, (D20) asks whether it out-earned books of its own shape drawn at random and refuses one that did not or was never measured, and (D19) asks whose book it is`,
and replace `All four are statements about the same one arm` with
`All five are statements about the same one arm`.
**Change 11c (the clause):** insert between the end of the D18 block (the `raise` that ends at
:2174) and the `# (D19)` comment (:2175), at the same indentation (inside `if candidate is not None:`):
```python
        # (D20) The arm that takes the look must have out-earned books of its own shape drawn at
        # random: its decisions replayed with every picked stock swapped (lab/yardstick.py). A
        # reading below the bar, an unmatched one, and no reading at all are all refused --
        # unlike (D16) and (D18), absence refuses here, because the lab can always take this
        # measurement and `lab yardstick` is the way to take it. `store.verdict` stages the rule
        # for arms recorded before `store.YARDSTICK_SINCE`; this door does not.
        luck_said = yardstick_refusal(conn, method_id, candidate)
        if luck_said is not None:
            raise store.LabError(
                f"{method_id} is not promoted: {luck_said} (D20). Nothing was written and no "
                f"status moved. There is no override -- if the rule is wrong, change it in "
                f"seer_engine/lab/hardgate.py and argue for it in the commit"
            )
```
**Impact:** every dev-eligible method whose chosen arm has no clearing reading is refused at
`lab promote` and listed under "Refused by the hard gate" in `lab status`. Measured this session on
a read-only copy of the committed lab with today's code, six methods are "Promotable now": M0197,
M0284, M0363, M0383, M0513, M0562. All six move to the refused block until measured. The test
fixtures that expect `check` to pass, or to refuse on a later clause, need a clearing reading
(Steps 14-15).

### Step 12: `lab run --jobs`, the per-arm line, the status header
**File:** `engine/src/seer_engine/commands/lab.py`
**Change 12a:** none. `--jobs` is validated by phase 3's `_positive_count` (defined after
`_positive_n`, :245), the same validator `lab yardstick --jobs` uses: one validator for both flags
(settled at reconcile).
**Change 12b (the flag, after `--amend`, :310):**
```python
    s.add_argument(
        "--jobs",
        type=_positive_count,
        default=2,
        metavar="J",
        help=(
            "worker processes for the random-twin yardstick each arm that clears every other "
            "condition is measured against before it is recorded (default 2: every worker holds "
            "a full simulation in memory, and the lab machine has 11 GiB). The reading is the "
            "same at any J"
        ),
    )
```
**Change 12c (`_run`, :1973-1978):** replace
```python
    done = runner.run_method(
        conn, method, path, data, git_sha=runner.git_head(config.REPO_ROOT), amend=amend
    )
    ran = done.ran
    status = store.get_method(conn, method.id)["status"]
    log.info("%s: %d trial(s) recorded, status %s (%.1fs)", method.id, len(ran), status, time.perf_counter() - t0)
```
with
```python
    # getattr for the same reason as `amend` above: hand-built Namespaces in the tests.
    jobs = int(getattr(args, "jobs", 2))
    done = runner.run_method(
        conn, method, path, data, git_sha=runner.git_head(config.REPO_ROOT), amend=amend,
        yardstick_jobs=jobs,
    )
    ran = done.ran
    status = store.get_method(conn, method.id)["status"]
    log.info("%s: %d trial(s) recorded, status %s (%.1fs)", method.id, len(ran), status, time.perf_counter() - t0)
    # One line per reading, printed by phase 3's `_yardstick_line` -- the same row `lab yardstick`
    # prints -- so a reading reads the same wherever it was taken.
    for r in ran:
        if r.yardstick is not None:
            log.info("random-twin yardstick: %s", _yardstick_line(r.trial.candidate_id, r.yardstick, ""))
```
**Change 12d:** none. The reading is printed by phase 3's `_yardstick_line(candidate_id, row, note)`
(defined after `_twins`, resolved at call time); there is no second formatter (settled at
reconcile).
**Change 12e (status header, :1666-1669):** replace the four string literals with
```python
            "  Refused by the hard gate (dev-eligible, but `lab promote` exits 2 on these -- it "
            "wants a majority of walk-forward folds, won by the picks and by the variant it would "
            "pre-register, a variant that out-earned its random twins, and no kin -- family, "
            "ancestry, blend ingredient or behaviour -- that has test-failed; there is no override):"
```
**Impact:** `lab run` logs one line per measured arm, and `lab status` names the new clause.
Escaping: no `%` in any help string added here. `dataclasses` stays imported at module scope for
its other users; nothing new is imported.

### Step 13: `labkit.stamp_yardstick` and the new test file
**File 13a:** `engine/tests/labkit.py`, after `stamp_provenance` (ends :156). Add `import json` to
the imports at the top.
**Code:**
```python
def stamp_yardstick(
    conn,
    trial_ns: Iterable[int],
    *,
    status: str = "measured",
    percentile: float = 1.0,
    draws: int = 200,
) -> None:
    """Record a random-twin reading for fixture trials, the way ``lab run`` does for real ones.

    ``hardgate.check`` refuses a variant with no reading that clears (D20), so a fixture that
    expects ``lab promote`` to take a method, or to refuse it on a later clause, stamps its trials
    here as it stamps their provenance. The default is a reading that clears: a ``measured``
    share of 1.0. ``status="not-applicable"`` records no draws, no twins beaten and no share (the
    shape ``yardstick.Measurement`` and the table's CHECKs require); any other status records
    ``draws`` twins of which ``round(percentile * draws)`` were out-earned.

    **Idempotent.** ``store.insert_yardstick`` returns False and writes nothing when the trial
    already has a reading under this rule and store, so two helpers stamping the same trial never
    collide. The caller holds the transaction, as with every ``store.insert_*``.
    """
    from seer_engine.lab import yardstick

    for n in trial_ns:
        if status == yardstick.STATUS_NOT_APPLICABLE:
            row = store.YardstickRow(
                trial_n=int(n), rule_id=yardstick.RULE_ID, store_fingerprint="test fixture",
                status=status, draws=0, arm_rate=None, beaten=0, percentile=None,
                rates_json="[]", trade_ratio=None, turnover_ratio=None, reproduced=None,
                git_sha="test fixture", measured="test fixture",
            )
        else:
            beaten = int(round(percentile * draws))
            row = store.YardstickRow(
                trial_n=int(n), rule_id=yardstick.RULE_ID, store_fingerprint="test fixture",
                status=status, draws=draws, arm_rate=0.12, beaten=beaten,
                percentile=beaten / draws, rates_json=json.dumps([0.05] * draws),
                trade_ratio=1.0, turnover_ratio=1.0, reproduced=True,
                git_sha="test fixture", measured="test fixture",
            )
        store.insert_yardstick(conn, row)
```
(Both shapes satisfy phase 3's CHECKs and `insert_yardstick` as reconciled: not-applicable is
`draws=0, beaten=0, percentile=None` with no ratio; any other status has `draws >= 1` and
`percentile == beaten / draws`. Phase 3 adds no labkit helper, so this is the one.)

**File 13b:** `engine/tests/test_lab_yardstick_gate.py` (create).
**Code:**
```python
"""The random-twin yardstick as a screen condition (RANDOM_TWIN_YARDSTICK_PLAN.md phase 4).

Three readers decide with it, and each is proven here by what a caller can see:

- ``lab run`` measures an arm that clears every other condition before it records it, and records
  it eligible only when it out-earned at least ``store.YARDSTICK_MIN_PERCENTILE`` of its twins
  (R2.1);
- ``store.verdict`` fails an arm whose reading is below the bar or ``unmatched``, and an arm
  recorded since ``store.YARDSTICK_SINCE`` that was never measured (R2.2, Decision D5);
- ``store._blocking`` says the same no a second time, in its own words, on the one door that
  reconsiders a verdict.

The ``lab promote`` refusal (hardgate D20, R2.3) is tested in ``test_lab_hardgate.py`` beside the
other clauses of ``check``, because it needs that file's fold fixtures.

Every ``lab run`` test injects ``measure`` through ``run_method``'s own parameter. What is under
test is what the run does with a reading, not how twins are drawn, which phase 2's
``test_lab_yardstick.py`` proves. One test runs the real engine at five draws to prove the two fit.
The smoke market rarely produces an arm that clears all six other conditions, so the tests that
need one pass the real simulations through ``_clear_every_other_condition``. It marks the chosen
arms D8-clean and sets the luck bar to zero; nothing else about the run is touched.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
from datetime import date
from pathlib import Path

import pytest
from labkit import smoke_data, stamp_yardstick

from seer_engine.backtest import dev as dev_module
from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.runner import INITIAL_IDR
from seer_engine.commands.backtest_dev import month_end_curve
from seer_engine.lab import control_shape, runner, store, yardstick
from seer_engine.lab.method import Method
from seer_engine.lab.seed import seed
from seer_engine.sim.contributions import OWNER_MONTHLY
from seer_engine.sim.rules import DAILY_SWITCH, MONTHLY_HOLD, MONTHLY_HOLD_FRAC
from seer_engine.strategies.f_factor import FACTOR, FactorParams
from seer_engine.strategies.f_index import TIMING, TimingParams

HERE = Path(__file__)
OLD = "2026-10-06T00:00:00+00:00"   # before the rule: judged by a reading once it has one
NEW = "2026-11-14T00:00:00+00:00"   # on YARDSTICK_SINCE: an unmeasured arm fails closed
GATE = store.Gate(n=2, policy="all-trials")
PF_LABEL = dev_module.FAILURE_LABELS[2]


# ------------------------------------------------------------------ fixtures


@pytest.fixture()
def conn(tmp_path):
    c = store.connect(tmp_path / "lab.sqlite")
    seed(c)
    yield c
    c.close()


@pytest.fixture()
def bare(tmp_path):
    """A lab with no seed rows, for the verdict tests: two fixture trials and nothing else."""
    c = store.connect(tmp_path / "bare.sqlite")
    yield c
    c.close()


@pytest.fixture(scope="module")
def data():
    return smoke_data()


def _cand(cid: str, *, n: int = 50, rules=MONTHLY_HOLD, rationale: str = "test") -> Candidate:
    return Candidate(
        id=cid, family="M0001", rules=rules, allocator=TIMING,
        params=TimingParams(hold="SPY", signal="SPY", rule="sma", n=n),
        rationale=rationale, added=date(2026, 11, 13), owner_inputs=(),
    )


CONTROL_RATIONALE = "Control: the same switch with the signal removed, registered to be beaten."


def _method(*cands: Candidate) -> Method:
    return Method(
        id="M0001", name="yardstick test", family="trend", source_kind="knowledge",
        source_ref="", hypothesis="h", expected_failure="f",
        candidates=tuple(cands) if cands else (_cand("M0001-A"),),
    )


def _clear_every_other_condition(monkeypatch, *, only=None, fail=()) -> None:
    """Pass the real simulations through, marking arms in ``only`` (all when None) D8-clean and
    arms in ``fail`` failing on profit factor, and set the luck bar to zero so any computable DSR
    clears it. What the run then does with a reading is the thing under test."""
    real = dev_module.run_registry

    def relayed(*args, on_result=None, **kwargs):
        def relay(i, result, row):
            if row.candidate.id in fail:
                row = dataclasses.replace(row, eligible=False, failed=(PF_LABEL,))
            elif only is None or row.candidate.id in only:
                row = dataclasses.replace(row, eligible=True, failed=())
            on_result(i, result, row)

        return real(*args, on_result=relay, **kwargs)

    monkeypatch.setattr(dev_module, "run_registry", relayed)
    monkeypatch.setattr(store, "DSR_MIN", 0.0)


def _reading(status: str = yardstick.STATUS_MEASURED, percentile: float = 0.95,
             draws: int = 200) -> yardstick.Measurement:
    if status == yardstick.STATUS_NOT_APPLICABLE:
        return yardstick.Measurement(
            status=status, draws=0, arm_rate=0.12, beaten=0, percentile=None, rates=(),
            trade_ratio=None, turnover_ratio=None, reproduced=True,
        )
    beaten = int(round(percentile * draws))
    return yardstick.Measurement(
        status=status, draws=draws, arm_rate=0.12, beaten=beaten, percentile=beaten / draws,
        rates=tuple(0.05 + i * 1e-4 for i in range(draws)), trade_ratio=1.0,
        turnover_ratio=1.0, reproduced=True,
    )


class _Twins:
    """Stands in for ``yardstick.measure``: a fixed reading (or a raise), and a log of each call
    with whether the lab-wide write lock was held at that moment."""

    def __init__(self, conn, reading=None, *, raises: Exception | None = None):
        self.conn, self.reading, self.raises, self.calls = conn, reading, raises, []

    def __call__(self, market, dividends, spy_dividends, candidate, *, initial_idr,
                 contributions, draws=yardstick.DRAWS, jobs=1, expect=None):
        self.calls.append({
            "candidate": candidate.id, "initial_idr": initial_idr,
            "contributions": contributions, "jobs": jobs, "expect": expect,
            "locked": self.conn.in_transaction,
        })
        if self.raises is not None:
            raise self.raises
        return self.reading


def _run(conn, data, twins, method=None, **kw):
    return runner.run_method(
        conn, method or _method(), HERE, data, git_sha="deadbeef", require_commit=False,
        measure=twins, **kw,
    )


# ------------------------------------------------------------------ R2.1: `lab run`


def test_an_arm_that_loses_to_its_twins_is_recorded_not_eligible_and_rejects_its_method(
    conn, data, monkeypatch
):
    _clear_every_other_condition(monkeypatch)
    twins = _Twins(conn, _reading(percentile=0.60))
    (r,) = _run(conn, data, twins).ran
    assert store.recorded_labels(r.trial.failed) == (store.YARDSTICK_LABEL,)
    assert r.trial.eligible is False
    assert store.get_method(conn, "M0001")["status"] == "rejected"
    (row,) = store.trials_of(conn, "M0001")
    assert row["eligible"] == 0 and row["failed"] == store.YARDSTICK_LABEL
    reading = store.yardstick_of(conn, row["n"])
    assert reading is not None
    assert reading["percentile"] == pytest.approx(0.60)
    assert reading["store_fingerprint"] == data.fingerprint
    assert reading["rule_id"] == yardstick.RULE_ID
    assert store.verdict(conn, row).failed == (store.YARDSTICK_LABEL,)


def test_an_arm_that_beats_its_twins_is_recorded_eligible(conn, data, monkeypatch):
    _clear_every_other_condition(monkeypatch)
    (r,) = _run(conn, data, _Twins(conn, _reading(percentile=0.95))).ran
    assert r.trial.failed == "" and r.trial.eligible is True
    assert store.get_method(conn, "M0001")["status"] == "dev-eligible"
    (row,) = store.trials_of(conn, "M0001")
    assert store.yardstick_of(conn, row["n"])["percentile"] == pytest.approx(0.95)
    assert store.verdict(conn, row).eligible is True


@pytest.mark.parametrize(
    ("status", "percentile", "eligible"),
    [
        (yardstick.STATUS_MEASURED, 0.900, True),     # the bar is "at least"
        (yardstick.STATUS_MEASURED, 0.895, False),    # 179 of 200
        (yardstick.STATUS_UNMATCHED, 0.990, False),   # unmatched never clears
        (yardstick.STATUS_NOT_APPLICABLE, 0.0, True),  # no picked stock, nothing to swap
    ],
)
def test_what_lab_run_records_for_each_reading(conn, data, monkeypatch, status, percentile,
                                               eligible):
    assert store.YARDSTICK_MIN_PERCENTILE == 0.90
    _clear_every_other_condition(monkeypatch)
    (r,) = _run(conn, data, _Twins(conn, _reading(status, percentile))).ran
    assert r.trial.eligible is eligible
    assert (store.YARDSTICK_LABEL in store.recorded_labels(r.trial.failed)) is (not eligible)
    (row,) = store.trials_of(conn, "M0001")
    assert store.yardstick_of(conn, row["n"])["status"] == status


def test_only_arms_that_clear_everything_else_and_are_not_controls_are_measured_before_the_lock(
    conn, data, monkeypatch
):
    method = _method(
        _cand("M0001-A"),
        _cand("M0001-B", rules=DAILY_SWITCH, n=20),
        _cand("M0001-C", n=30, rationale=CONTROL_RATIONALE),
    )
    assert control_shape.role_of(method.candidates[2]) == control_shape.ROLE_CONTROL
    _clear_every_other_condition(monkeypatch, only={"M0001-A", "M0001-C"}, fail={"M0001-B"})
    twins = _Twins(conn, _reading(percentile=0.95))
    ran = {r.trial.candidate_id: r for r in _run(conn, data, twins, method, yardstick_jobs=3).ran}

    assert [c["candidate"] for c in twins.calls] == ["M0001-A"]
    (call,) = twins.calls
    assert call["locked"] is False, "nothing slow may run under the lab-wide write lock"
    assert call["jobs"] == 3
    assert call["initial_idr"] == INITIAL_IDR and call["contributions"] is OWNER_MONTHLY
    a = ran["M0001-A"].trial
    assert call["expect"] == (a.trades, a.total_return)

    assert a.eligible is True
    assert store.recorded_labels(ran["M0001-B"].trial.failed) == (PF_LABEL,)
    control = store.recorded_labels(ran["M0001-C"].trial.failed)
    assert store.CONTROL_LABEL in control and store.YARDSTICK_LABEL not in control
    rows = {r["candidate_id"]: r["n"] for r in store.trials_of(conn, "M0001")}
    assert store.yardstick_of(conn, rows["M0001-A"]) is not None
    assert store.yardstick_of(conn, rows["M0001-B"]) is None
    assert store.yardstick_of(conn, rows["M0001-C"]) is None


def test_an_eligible_arm_left_unmeasured_is_recorded_with_the_label_and_the_way_back(
    conn, data, monkeypatch, caplog
):
    _clear_every_other_condition(monkeypatch)
    twins = _Twins(conn, raises=yardstick.Unreproducible("the re-run made 12 trades, the run 13"))
    with caplog.at_level(logging.INFO, logger=runner.__name__):
        (r,) = _run(conn, data, twins).ran
    assert store.recorded_labels(r.trial.failed) == (store.YARDSTICK_LABEL,)
    assert r.yardstick is None
    (row,) = store.trials_of(conn, "M0001")
    assert store.yardstick_of(conn, row["n"]) is None
    assert store.get_method(conn, "M0001")["status"] == "rejected"
    assert "lab yardstick M0001 --arm M0001-A" in caplog.text
    assert "lab reevaluate M0001" in caplog.text


def test_a_run_with_nothing_eligible_measures_nothing(conn, data, monkeypatch):
    _clear_every_other_condition(monkeypatch, only=set(), fail={"M0001-A"})
    twins = _Twins(conn, _reading())
    (r,) = _run(conn, data, twins).ran
    assert twins.calls == []
    assert store.recorded_labels(r.trial.failed) == (PF_LABEL,)


def test_trial_rows_with_no_readings_records_what_it_always_did(conn, data):
    method = _method(_cand("M0001-A"), _cand("M0001-B", rules=DAILY_SWITCH, n=20))
    results = []
    dev_module.run_registry(
        data.market, data.dividends, data.spy_dividends, method.candidates,
        on_result=lambda i, res, row: results.append((row, month_end_curve(res.snapshots))),
        contributions=OWNER_MONTHLY, initial_idr=INITIAL_IDR,
    )
    before = runner.trial_rows(conn, method, results, fingerprint="smoke", git_sha="x")
    after = runner.trial_rows(conn, method, results, fingerprint="smoke", git_sha="x",
                              yardsticks=None)
    for a, b in zip(before, after, strict=True):
        assert (a.trial.failed, a.trial.eligible, a.trial.dsr) == (
            b.trial.failed, b.trial.eligible, b.trial.dsr)
        assert store.YARDSTICK_LABEL not in a.trial.failed
        assert a.yardstick is None and b.yardstick is None


def test_the_real_engine_measures_an_arm_inside_lab_run(conn, data, monkeypatch):
    """The fake above proves what the run does with a reading; this proves the real engine's
    reading fits the record. Five draws on the smoke market's eight member stocks. The arm is
    sent to the engine by replacing the filter with "any non-control arm", because a smoke-market
    arm rarely clears the six other conditions; the filter itself is proven above."""
    monkeypatch.setattr(
        runner, "_due_for_yardstick",
        lambda row, dsr: control_shape.role_of(row.candidate) != control_shape.ROLE_CONTROL,
    )
    picker = Candidate(
        id="M0001-LV", family="M0001", rules=MONTHLY_HOLD_FRAC, allocator=FACTOR,
        params=FactorParams(rank="lowvol", top=3, mom_n=60, mom_skip=0, vol_n=20, trend=None),
        rationale="test", added=date(2026, 11, 13), owner_inputs=(),
    )
    measure = functools.partial(yardstick.measure, draws=5)
    (r,) = runner.run_method(conn, _method(picker), HERE, data, git_sha="x",
                             require_commit=False, measure=measure).ran
    assert r.yardstick is not None
    (row,) = store.trials_of(conn, "M0001")
    reading = store.yardstick_of(conn, row["n"])
    assert reading["status"] in (yardstick.STATUS_MEASURED, yardstick.STATUS_UNMATCHED)
    assert reading["draws"] == 5
    assert reading["store_fingerprint"] == data.fingerprint
    labels = store.recorded_labels(r.trial.failed)
    if not [x for x in labels if x != store.YARDSTICK_LABEL]:
        assert (store.YARDSTICK_LABEL in labels) is (not store.yardstick_clears(reading))


# ------------------------------------------------------------------ R2.2: `store.verdict`


def _trial(**kw) -> store.TrialRow:
    """Clear of every owner condition, and of the luck test at ``GATE`` (N = 2 = n_trials_at_run,
    where ``dsr_at`` returns the recorded 0.97 exactly)."""
    base = dict(
        method_id="M0001", candidate_id="M0001-A", config_digest="d1", config_text="t",
        rules_id="MONTHLY_HOLD", allocator_id="TIMING", window="dev", start="1996-01-02",
        end="2015-10-16", store_fingerprint="fp", git_sha="abc", run_at=OLD,
        total_return=3.0, cagr=0.12, max_drawdown=0.11, profit_factor=1.6, trades=250,
        sharpe=0.9, exposure=0.95, turnover=1.1, worst_year=2008, worst_year_return=-0.1,
        spy_tr_return=2.0, spy_tr_cagr=0.08, mar=0.8, failed="", eligible=True, dsr=0.97,
        n_trials_at_run=2, curve_json="[]",
    )
    base.update(kw)
    return store.TrialRow(**base)


def _ballast() -> store.TrialRow:
    """A second dev trial so the lab has a trial-Sharpe variance; ineligible on its drawdown."""
    return _trial(candidate_id="M0001-BALLAST", config_digest="ballast", sharpe=1.46,
                  max_drawdown=0.55, mar=0.1, dsr=0.50, eligible=False, failed="max DD")


def _lab(conn, *trials: store.TrialRow, status: str = "registered") -> list[int]:
    with conn:
        store.add_method(conn, id="M0001", name="n", family="f", source_kind="knowledge",
                         hypothesis="h", status="registered")
        if status != "registered":
            store.update_method(conn, "M0001", status=status)
        ns = store.insert_trials(conn, [*trials, _ballast()])
    return list(ns[: len(trials)])


def _row(conn, n: int):
    return conn.execute("SELECT * FROM trials WHERE n = ?", (n,)).fetchone()


def test_an_old_arm_reads_eligible_until_a_failing_reading_is_recorded(bare):
    (n,) = _lab(bare, _trial())
    assert store.verdict(bare, _row(bare, n), at=GATE).eligible is True
    with bare:
        stamp_yardstick(bare, [n], percentile=0.50)
    v = store.verdict(bare, _row(bare, n), at=GATE)
    assert v.failed == (store.YARDSTICK_LABEL,) and v.eligible is False
    assert store.best_dev_eligible(bare, "M0001", at=GATE) is None


def test_an_unmatched_reading_fails_the_arm_whatever_its_percentile(bare):
    (n,) = _lab(bare, _trial())
    with bare:
        stamp_yardstick(bare, [n], status=yardstick.STATUS_UNMATCHED, percentile=0.99)
    assert store.verdict(bare, _row(bare, n), at=GATE).failed == (store.YARDSTICK_LABEL,)


@pytest.mark.parametrize(
    ("status", "percentile"),
    [(yardstick.STATUS_MEASURED, 0.90), (yardstick.STATUS_MEASURED, 1.0),
     (yardstick.STATUS_NOT_APPLICABLE, 0.0)],
)
def test_a_clearing_reading_adds_nothing(bare, status, percentile):
    (n,) = _lab(bare, _trial(run_at=NEW))
    with bare:
        stamp_yardstick(bare, [n], status=status, percentile=percentile)
    v = store.verdict(bare, _row(bare, n), at=GATE)
    assert v.failed == () and v.eligible is True


def test_an_arm_recorded_since_the_rule_and_never_measured_fails_closed(bare):
    assert store.YARDSTICK_SINCE == "2026-11-14"
    new, eve = _lab(
        bare,
        _trial(run_at=NEW),
        _trial(candidate_id="M0001-E", config_digest="d-eve", run_at="2026-11-13T23:59:59+00:00"),
    )
    assert store.verdict(bare, _row(bare, new), at=GATE).failed == (store.YARDSTICK_LABEL,)
    assert store.verdict(bare, _row(bare, eve), at=GATE).failed == ()


def test_an_unmeasured_new_arm_reads_only_its_real_failure(bare):
    (n,) = _lab(bare, _trial(run_at=NEW, profit_factor=1.1))
    assert store.verdict(bare, _row(bare, n), at=GATE).failed == (PF_LABEL,)


def test_the_yardstick_label_goes_last(bare):
    (n,) = _lab(bare, _trial(profit_factor=1.1, dsr=0.50))
    with bare:
        stamp_yardstick(bare, [n], percentile=0.10)
    failed = store.verdict(bare, _row(bare, n), at=GATE).failed
    assert failed[0] == PF_LABEL and store.DSR_LABEL in failed
    assert failed[-1] == store.YARDSTICK_LABEL


def test_a_control_arm_never_carries_the_yardstick_label(bare):
    (n,) = _lab(bare, _trial())
    with bare:
        store.insert_roles(bare, [store.RoleRow(trial_n=n, role="control", source="recorded",
                                                measured=OLD)])
        stamp_yardstick(bare, [n], percentile=0.10)
    failed = store.verdict(bare, _row(bare, n), at=GATE).failed
    assert store.CONTROL_LABEL in failed and store.YARDSTICK_LABEL not in failed


def test_a_test_window_row_never_reads_the_yardstick(bare):
    """A test look recorded since the rule, with no reading: a dev arm in that state fails closed,
    a look never does. (No reading can be stamped on a look at all: phase 3's
    ``insert_yardstick`` refuses a test-window trial, and its own test proves that.)"""
    (n,) = _lab(bare, _trial(window="test", candidate_id="M0001-T", run_at=NEW))
    assert store.yardstick_of(bare, n) is None
    v = store.published_verdict(bare, _row(bare, n), at=GATE)
    assert store.YARDSTICK_LABEL not in v.failed


def test_a_lab_with_no_role_no_reading_and_nothing_new_reads_as_before(bare):
    """Plan invariant 5: with no ``trial_roles`` row, no ``trial_yardstick`` row and no trial on
    or after ``YARDSTICK_SINCE``, every verdict is the six conditions and nothing else."""
    ns = _lab(
        bare,
        _trial(),
        _trial(candidate_id="M0001-PF", config_digest="d-pf", profit_factor=1.1),
        _trial(candidate_id="M0001-DD", config_digest="d-dd", max_drawdown=0.60),
        _trial(candidate_id="M0001-LUCK", config_digest="d-luck", dsr=0.50),
    )
    assert bare.execute("SELECT count(*) FROM trial_yardstick").fetchone()[0] == 0
    assert bare.execute("SELECT count(*) FROM trial_roles").fetchone()[0] == 0
    for n in ns:
        row = _row(bare, n)
        v = store.verdict(bare, row, at=GATE)
        luck = () if (v.dsr is not None and v.dsr >= store.DSR_MIN) else (store.DSR_LABEL,)
        assert v.failed == store.owner_failures(row, store.funding_of(bare, n)) + luck
        assert store.YARDSTICK_LABEL not in v.failed
    assert store.verdict(bare, _row(bare, ns[0]), at=GATE).eligible is True


def test_the_independent_check_says_no_in_its_own_words(bare):
    assert (yardstick.STATUS_MEASURED, yardstick.STATUS_NOT_APPLICABLE) == (
        "measured", "not-applicable"), "_blocking types these two literals on purpose"
    old, new = _lab(bare, _trial(),
                    _trial(candidate_id="M0001-N", config_digest="d-new", run_at=NEW))
    lost = {"status": "measured", "percentile": 0.5, "beaten": 100, "draws": 200}
    said = "; ".join(store._blocking(_row(bare, old), None, lost))
    assert "100 of 200 random twins" in said and "90%" in said
    odd = {"status": "unmatched", "percentile": 0.99, "beaten": 198, "draws": 200}
    assert "'unmatched'" in "; ".join(store._blocking(_row(bare, old), None, odd))
    clear = {"status": "not-applicable", "percentile": None, "beaten": 0, "draws": 0}
    assert store._blocking(_row(bare, old), None, clear) == ()
    assert store._blocking(_row(bare, old)) == ()
    assert store.YARDSTICK_SINCE in "; ".join(store._blocking(_row(bare, new)))


@pytest.fixture()
def at_all_trials(monkeypatch):
    monkeypatch.setattr(store, "DSR_POLICY", "all-trials")
    store._GATE_CACHE.clear()
    yield
    store._GATE_CACHE.clear()


def test_reevaluate_refuses_outright_when_the_verdict_ignores_a_failing_reading(
    bare, monkeypatch
):
    (n,) = _lab(bare, _trial(failed="DSR >= 0.95", eligible=False), status="rejected")
    with bare:
        stamp_yardstick(bare, [n], percentile=0.10)
    monkeypatch.setattr(
        store, "verdict", lambda c, t, **kw: store.Verdict(0.99, (), True, 2, "all-trials", True)
    )
    with pytest.raises(store.LabError, match="second, independent check") as e:
        with bare:
            store.reevaluate_method(bare, "M0001")
    assert "random twins" in str(e.value)
    assert store.get_method(bare, "M0001")["status"] == "rejected"


def test_reevaluate_does_not_unblock_an_old_arm_whose_reading_failed(bare, at_all_trials):
    (n,) = _lab(bare, _trial(failed="DSR >= 0.95", eligible=False), status="rejected")
    with bare:
        stamp_yardstick(bare, [n], percentile=0.10)
        assert store.reevaluate_method(bare, "M0001").moved is False
    assert store.get_method(bare, "M0001")["status"] == "rejected"


def test_reevaluate_unblocks_an_old_arm_whose_reading_clears(bare, at_all_trials):
    (n,) = _lab(bare, _trial(failed="DSR >= 0.95", eligible=False), status="rejected")
    with bare:
        stamp_yardstick(bare, [n], percentile=0.95)
        assert store.reevaluate_method(bare, "M0001").moved is True
    assert store.get_method(bare, "M0001")["status"] == "dev-eligible"
```
Implementer notes for this file:
- `store.add_method(..., status="registered")` then `update_method(status="rejected")` walks the
  real `registered -> rejected` edge.
- `insert_trials` with `window="test"` needs a `config_digest` the dev rows do not use only within
  `window='test'`; `UNIQUE(config_digest, window)` allows `d1` twice across windows. If a trigger
  refuses a test row for a non-promoted method, walk the method to `promoted` first.
- If smoke data cannot run `FACTOR` with those params, use the stock-picking smoke arm phase 2's
  `test_lab_yardstick.py` uses. The assertions do not change.

### Step 14: `test_lab_hardgate.py`: fixtures carry a clearing reading, and the D20 tests
**File:** `engine/tests/test_lab_hardgate.py`
**Change 14a (import, :22):**
```python
from labkit import LAB_PRICE_FINGERPRINT, stamp_provenance, stamp_yardstick
```
**Change 14b (`_method`, :107-139):** add a keyword `measured: bool = True` to the signature
(after `curve_json`), add a docstring sentence, and stamp after the provenance stamp. The function
becomes:
```python
def _method(conn, mid="M0001", *, family="trend", parent=None, status="dev-eligible",
            annual=0.15, span=DEV_SPAN, curves=True, prices: str | None = SAME_PRICES,
            stamped: bool = True, curve_json: str | None = None, measured: bool = True) -> None:
    """One method with one dev trial, walked to ``status`` through the real transitions.

    The trial is stamped with provenance on ``prices`` unless ``stamped`` is False -- the gate
    refuses an unstamped trial (D10), which is a test of its own below, not a default. It also
    carries a random-twin reading that clears unless ``measured`` is False, as every arm
    ``lab run`` records now does -- the gate refuses an unmeasured variant (D20), which is also a
    test of its own below.
    """
    with conn:
        store.add_method(conn, id=mid, name=f"n{mid}", family=family, parent_id=parent,
                         source_kind="variation" if parent else "knowledge", hypothesis="h",
                         status="registered")
        ns = store.insert_trials(conn, [_trial(
            method_id=mid, candidate_id=f"{mid}-A", config_digest=f"d-{mid}",
            curve_json=(
                "[]" if not curves
                else curve_json if curve_json is not None
                else _curve(_months(*span), annual)
            ),
        )])
        if stamped:
            stamp_provenance(conn, ns, price_fingerprint=prices)
        if measured:
            stamp_yardstick(conn, ns)
        for step in {
            "registered": (),
            "dev-eligible": ("dev-eligible",),
            "promoted": ("dev-eligible", "promoted"),
            "test-failed": ("dev-eligible", "promoted", "test-failed"),
            "rejected": ("rejected",),
        }[status]:
            store.update_method(conn, mid, status=step)
```
**Change 14c (the other promotable-arm stamps):** directly after each of these lines add
`stamp_yardstick(conn, <the same trial-number argument>)`, at the same indentation and inside the
same `with conn:` block:
- `:328` (`_variant`): `stamp_yardstick(conn, ns)`
- `:582` (`_funded_trial`): `stamp_yardstick(conn, [n])`
- `:1356` (`_control_arm`): `stamp_yardstick(conn, ns)`
- `:1723`: `stamp_yardstick(conn, ns)`
- `:1912`: `stamp_yardstick(conn, ns)`

Leave `:104` (`_benchmark`, never promoted), `:365` and `:753` (other prices, refused by D10
first) and `:535`/`:558` (de-funding tests that never call `check`) as they are. **The lever:**
after the edit, run `engine/.venv/bin/pytest -n0 -q engine/tests/test_lab_hardgate.py`. Any test
other than the known-red buy-signal test that fails with `(D20)` in its message has a trial the
list above missed. Add `stamp_yardstick` beside that trial's `stamp_provenance` and re-run. Do not
add an autouse patch of `store.yardstick_of`, which would hide the clause from every test in the
file.
**Change 14d (the D20 tests):** append after `test_lab_promote_exits_2_and_writes_nothing_when_the_kin_has_failed` (:658):
```python
# ------------------------------------------------------------------ the random-twin yardstick (D20)


def test_the_module_records_the_yardstick_decision():
    doc = hardgate.__doc__ or ""
    assert "(D20)" in doc
    assert "random" in doc and "twins" in doc
    assert "fails closed" in doc


def test_the_gate_refuses_a_promoted_variant_never_measured_against_its_twins(conn):
    _benchmark(conn)
    _method(conn, "M0001", measured=False)
    with pytest.raises(store.LabError) as e:
        hardgate.check(conn, "M0001")
    said = str(e.value)
    assert "(D20)" in said
    assert "never been measured against its random twins" in said
    assert "`lab yardstick M0001`" in said
    assert "Nothing was written and no status moved" in said


def test_a_not_applicable_reading_clears_the_gate(conn):
    """A book that holds no picked stock has no twins, and that clears (R2.3's exception)."""
    _benchmark(conn)
    _method(conn, "M0001", measured=False)
    (row,) = store.trials_of(conn, "M0001")
    with conn:
        stamp_yardstick(conn, [row["n"]], status="not-applicable")
    hardgate.check(conn, "M0001")  # does not raise


def test_the_gate_refuses_a_variant_its_twins_out_earned_even_if_the_ranking_names_it(
    conn, monkeypatch
):
    """The second, independent no. `store.verdict` fails a losing arm first, so
    `best_dev_eligible` never names it; the clause still refuses it if the two ever disagree."""
    _benchmark(conn)
    _method(conn, "M0001", measured=False)
    (row,) = store.trials_of(conn, "M0001")
    with conn:
        stamp_yardstick(conn, [row["n"]], percentile=0.50)
    monkeypatch.setattr(hardgate, "promoted_variant", lambda c, m: "M0001-A")
    with pytest.raises(store.LabError, match=r"out-earned only 100 of its 200 random twins"):
        hardgate.check(conn, "M0001")


def test_the_gate_refuses_an_unmatched_variant(conn, monkeypatch):
    _benchmark(conn)
    _method(conn, "M0001", measured=False)
    (row,) = store.trials_of(conn, "M0001")
    with conn:
        stamp_yardstick(conn, [row["n"]], status="unmatched", percentile=0.99)
    monkeypatch.setattr(hardgate, "promoted_variant", lambda c, m: "M0001-A")
    with pytest.raises(store.LabError, match="could not be matched by its random twins"):
        hardgate.check(conn, "M0001")


def test_lab_promote_exits_2_and_writes_nothing_when_the_arm_was_never_measured(tmp_path):
    db, prereg_dir = tmp_path / "lab.sqlite", tmp_path / "prereg"
    c = store.connect(db)
    _benchmark(c)
    _method(c, "M0001", annual=0.15, measured=False)
    before = db.read_bytes()
    c.close()

    assert _cli(tmp_path, db, prereg_dir) == 2
    assert not prereg_dir.exists()
    assert db.read_bytes() == before
    c = store.connect(db)
    assert store.get_method(c, "M0001")["status"] == "dev-eligible"
    c.close()


def test_lab_promote_exits_2_and_writes_nothing_when_the_twins_out_earned_the_arm(tmp_path):
    db, prereg_dir = tmp_path / "lab.sqlite", tmp_path / "prereg"
    c = store.connect(db)
    _benchmark(c)
    _method(c, "M0001", annual=0.15, measured=False)
    (row,) = store.trials_of(c, "M0001")
    with c:
        stamp_yardstick(c, [row["n"]], percentile=0.50)
    before = db.read_bytes()
    c.close()

    assert _cli(tmp_path, db, prereg_dir) == 2
    assert not prereg_dir.exists()
    assert db.read_bytes() == before
```
**Impact:** the file's ~120 existing tests keep asserting what they asserted, now on arms that carry
the reading every new arm has.

### Step 15: the other fixtures that promote
**File 15a:** `engine/tests/test_lab_prereg.py`. Add `stamp_yardstick` to the `labkit` import, and
directly after `stamp_provenance(conn, ns)` at `:181` and at `:210` (`_real_method`) add
`stamp_yardstick(conn, ns)` (same indentation, same `with conn:`). Append one sentence to
`_real_method`'s docstring: `Both trials also carry a random-twin reading that clears, as `lab run`
now records one, because the gate refuses an unmeasured variant (D20).`
**File 15b:** `engine/tests/test_lab_status.py:373-374`, in `_method_at`. Replace
```python
        if trials:
            stamp_provenance(c, store.insert_trials(c, list(trials)))
```
with
```python
        if trials:
            ns = store.insert_trials(c, list(trials))
            stamp_provenance(c, ns)
            stamp_yardstick(c, ns)
```
and add `stamp_yardstick` to that file's `labkit` import. Append to `_method_at`'s docstring:
`Every trial also carries a random-twin reading that clears, because the gate refuses an
unmeasured variant (D20).`
**Impact:** `test_lab_promote_command_writes_the_file_and_names_the_next_step` and
`test_a_method_that_clears_the_hard_gate_is_listed_with_its_fold_record` keep passing.

### Step 16: the guard on the documents' bar
**File:** `engine/tests/test_lab_gate_wording.py`, append at the end of the file.
**Code:**
```python
# ------------------------------------------------------------------ the random-twin yardstick's bar

#: The shipped documents that state the yardstick bar to an unattended session or to the person
#: running the backfill. The design document is left out for ``SCANNED``'s reason: it records by
#: dated revision, and a future §11 that moves the bar must not rewrite §10's number.
YARDSTICK_DOCS: tuple[str, ...] = (
    "docs/runbooks/yardstick-backfill.md",
    ".claude/skills/explore-and-experiment-new-method/SKILL.md",
    ".claude/skills/sera-the-explorer/SKILL.md",
)

#: "90% of its random twins", "90% of their twins": the bar as a document writes it.
TWIN_BAR = re.compile(r"(\d{1,3}(?:\.\d+)?)% of (?:its |their )?(?:random )?twins", re.I)


@pytest.mark.parametrize("rel", YARDSTICK_DOCS)
def test_no_shipped_document_states_a_yardstick_bar_the_lab_does_not_apply(rel: str) -> None:
    """The DSR bar went stale in six shipped files at once when the owner moved it (this module's
    docstring). The yardstick's bar is written into three, so the same guard is built for it on
    the day it ships rather than after the first move."""
    path = config.REPO_ROOT / rel
    assert path.is_file(), f"{rel} is gone; update YARDSTICK_DOCS or restore the file"
    stated = [float(m.group(1)) for m in TWIN_BAR.finditer(path.read_text(encoding="utf-8"))]
    assert stated, f"{rel} no longer states the yardstick bar; it is what a session acts on"
    live = store.YARDSTICK_MIN_PERCENTILE * 100
    wrong = [s for s in stated if abs(s - live) > 1e-9]
    assert not wrong, f"{rel} states {wrong}% of twins; the lab applies {live:.0f}%"
```
**Impact:** Steps 18-19 must write the bar as "90% of its random twins" at least once in each file.

### Step 16b: the pre-registration's gate text names the yardstick (Decision D13)
**File:** `engine/src/seer_engine/lab/prereg.py:234-239` (`gate_text`)
**Why:** `gate_text` is what a pre-registration file records as "the dev gate this variant passed".
From this phase on, a variant can only be promoted if it cleared the random-twin yardstick (D20), so
a file that names only the five conditions and the DSR would understate what was passed. Checked at
reconcile: no test pins the exact historical text of an already-written `docs/lab/prereg/MNNNN.md`
(`parse` reads the `gate:` value as a free string, and the gate-text tests assert membership and
`resolved.startswith(text)`), so the new clause goes into every **newly written** file and the
committed files keep their own day's text, unchanged — they are frozen records.
**Change 1 (code):** replace
```python
    conditions = "; ".join(dev.FAILURE_LABELS[:-1])
    head = (
        f"dev-eligible = the five P7a D8 conditions ({conditions}; no {dev.FAILURE_LABELS[-1]}) "
        f"and DSR >= {store.DSR_MIN:.2f}, deflated by the multiple-testing N that the "
        f"'{store.DSR_POLICY}' policy resolves to"
    )
```
with
```python
    conditions = "; ".join(dev.FAILURE_LABELS[:-1])
    head = (
        f"dev-eligible = the five P7a D8 conditions ({conditions}; no {dev.FAILURE_LABELS[-1]}), "
        f"{store.YARDSTICK_LABEL} (out-earned at least {store.YARDSTICK_MIN_PERCENTILE:.0%} of the "
        f"books that replay its decisions with the picked stocks drawn at random, or held no "
        f"picked stock) and DSR >= {store.DSR_MIN:.2f}, deflated by the multiple-testing N that "
        f"the '{store.DSR_POLICY}' policy resolves to"
    )
```
It stays one line, and the `conn` form still only appends (`: N = ...`).
**Change 2 (docstring):** in `gate_text`'s docstring, after the first paragraph (ends `... or an N
the gate stopped deflating by.`), add:
```text
    Since 2026-11-14 it also names the random-twin yardstick (``store.YARDSTICK_LABEL``, built from
    ``store.YARDSTICK_MIN_PERCENTILE``), because ``lab promote`` refuses a variant without a reading
    that clears it (hardgate D20). Files written before then keep the text of their own day.
```
**Change 3 (test):** `engine/tests/test_lab_prereg.py`, directly after
`test_the_recorded_gate_names_every_condition_the_lab_applies`:
```python
def test_the_recorded_gate_names_the_random_twin_yardstick(tmp_path):
    """Since 2026-11-14 a promoted variant has cleared its random twins (hardgate D20), so the
    file says so, with the bar built from the constant, and the conn form still only appends."""
    text = prereg.gate_text()
    assert store.YARDSTICK_LABEL in text
    assert f"{store.YARDSTICK_MIN_PERCENTILE:.0%}" in text
    conn = store.connect(tmp_path / "lab.sqlite")
    try:
        resolved = prereg.gate_text(conn)
    finally:
        conn.close()
    assert resolved.startswith(text) and "\n" not in resolved
```
`BAR_WITH_NUMBER` in `test_lab_gate_wording.py` matches only `DSR >= x` / "luck check of at least x",
so the new clause does not trip it.

### Step 17: design §10
**File:** `docs/plans/2026-10-04-method-lab-design.md`, append after the last line (:602).
**Change:** the dated revision. Every figure in it was read back by the planning session from a
read-only copy of the committed `lab/lab.sqlite` at `f83fb237`, with the script below:
45 / 42 / 14; 2,051 / 362; N = 415 under `methods`; 256 eligible arms in 125 methods (185
treatment, 64 control, 7 dose); 182 dev-eligible methods, 94 with an eligible non-control arm;
192 non-control eligible arms in 97 methods. **These are unverified in this session until re-run**
(CLAUDE.md, Claim verification). The replay figures (M0562-W60-B100, 0.1494087982869519, 203
trades, 237 decisions, 1.5 s against 2.6 s) are the analysis file's and were not re-measured.
**Before committing, save the script below as `$TMPDIR/measure_s10.py` (any scratch path outside
the repo; it is not committed), run it on the tree's `lab/lab.sqlite` with the phase-3 code in
place, and use its numbers if they moved:**
```bash
PYTHONPATH=engine/src engine/.venv/bin/python "$TMPDIR/measure_s10.py" lab/lab.sqlite
```
```python
"""Re-measure the figures design section 10 quotes, read-only, on a copy of the lab."""
import sqlite3, sys
from collections import Counter
from seer_engine.lab import store, control_shape
from seer_engine.lab.method import discover
from seer_engine.backtest import dev

db = sys.argv[1]
c = sqlite3.connect(f"file:{db}?mode=ro", uri=True); c.row_factory = sqlite3.Row
spy = dev.FAILURE_LABELS[0]
rows = c.execute("SELECT t.*, m.family AS fam FROM trials t JOIN methods m ON m.id=t.method_id WHERE t.window='dev'").fetchall()
plac = [r for r in rows if r["fam"] in ("placebo-hash-order", "blind-draw-baseline")]
beat = sum(1 for r in plac if spy not in store.owner_failures(r, store.funding_of(c, r["n"])))
print("placebo/blind dev trials", len(plac), "beat SPY", beat, "recorded eligible", sum(r["eligible"] for r in plac))
main = [r for r in rows if r["start"] == "1996-01-03"]
print("main-window dev trials", len(main), "recorded eligible", sum(r["eligible"] for r in main))
g = store.gate(c)
print("gate", g)
cands = {}
for mid, (m, _p) in discover().items():
    for cd in list(m.candidates) + [x for a in getattr(m, "amendments", ()) for x in a.candidates]:
        cands[cd.id] = cd
verdicts = {r["n"]: store.verdict(c, r, at=g) for r in rows}
elig = [r for r in rows if verdicts[r["n"]].eligible]
roles = Counter(control_shape.role_of(cands[r["candidate_id"]]) if r["candidate_id"] in cands else "unreadable" for r in elig)
print("eligible now", len(elig), "in methods", len({r["method_id"] for r in elig}), dict(roles))
noncontrol = {r["method_id"] for r in elig if r["candidate_id"] in cands and control_shape.role_of(cands[r["candidate_id"]]) != "control"}
de = [r[0] for r in c.execute("SELECT id FROM methods WHERE status='dev-eligible'")]
print("dev-eligible methods", len(de), "with an eligible non-control arm", len(set(de) & noncontrol))
print("non-control eligible arms", sum(1 for r in elig if r["candidate_id"] in cands and control_shape.role_of(cands[r["candidate_id"]]) != "control"), "in methods", len(noncontrol))
print("dev arms carrying the yardstick label", sum(1 for v in verdicts.values() if store.YARDSTICK_LABEL in v.failed))
print("latest run_at", c.execute("SELECT max(run_at) FROM trials").fetchone()[0])
```
**Code:**
```markdown

## 10. Revision 2026-11-13 (owner's instruction of 2026-11-13): the random-twin yardstick

**This section records a change made by a plan set acting under the owner's instruction of
2026-11-13** — "you idea so we can implement them robustly" — which pointed at a review's three
recommendations: a random-book yardstick per setup that counts against nothing, ideas judged
against it, and status derived from treatment arms only. It does not move the §1 real-money bar,
`DSR_MIN`, the N policy or any of the five P7a conditions.

The sections it qualifies are left exactly as written.

### 10.1 What changed

The dev screen has a **seventh condition**: an arm passes only if it out-earned at least 90% of
its **random twins** (`store.YARDSTICK_MIN_PERCENTILE = 0.90`, `lab/yardstick.py`'s `DRAWS = 200`).

- **What a twin is.** A book that replays the arm's own recorded decisions (the same dates,
  weights, entries and exits) with every picked stock swapped for an index member of similar
  trading size, drawn at random: one within 25 ranks of the real pick by 63-day median dollar
  volume, kept for the whole holding spell. The statistic is the rate the screen already ranks on
  (money-weighted return when funded, CAGR otherwise), and a tie counts against the arm.
- **Where it is read.** `lab run` measures every non-control arm that clears the other six
  conditions before it records it, outside the lab-wide write lock. `store.verdict` fails an arm
  whose reading is below the bar or `unmatched`. `lab promote` refuses an arm with no reading that
  clears (hardgate D20). `lab reevaluate`'s second, independent check says the same no in its own
  words.
- **Old arms are staged.** An arm recorded before 2026-11-14 (`store.YARDSTICK_SINCE`) is judged on
  its six other conditions until `lab yardstick` measures it, and on its reading from then on. An
  arm recorded on or after that date with no reading fails. `lab promote` is not staged.
- **Readings count against nothing.** A reading is a row in `trial_yardstick`, keyed by trial, rule
  and research store. It inserts no trial, does not move N and spends no look.
- **Controls.** An arm the method registered to be beaten (a control, by its own rationale) is
  never measured and never makes a method `dev-eligible` (the same plan set's phase 1).
  Hand-written random and blind arms remain allowed as controls; they no longer decide the luck
  question, the yardstick does.

### 10.2 Why

Measured 2026-11-13 on the committed `lab/lab.sqlite` at `f83fb237`:

- 45 dev trials belong to the two deliberately meaningless families (`placebo-hash-order`,
  `blind-draw-baseline`). 42 beat SPY and 14 were recorded eligible.
- Across the 2,051 dev trials on the main window, 362 were recorded eligible.
- At today's bars (`methods` policy, N = 415), 256 dev arms in 125 methods read eligible. 64 of
  them are control arms; 192 non-control arms in 97 methods remain. 182 methods read
  `dev-eligible`, and 94 of them have an eligible non-control arm.

A screen that books with no idea in them pass a third of the time is grading the shape of a book
(its pool, its size, its cadence, its weighting, its switch), not the idea in it. The fair
comparison for an idea is the same shape holding stocks nobody chose.

"Per setup" became "per arm" because the lab has no machine-readable setup: every method writes its
own allocator. What every arm does expose is its sequence of decisions, and replaying them is exact.
A probe on `M0562-W60-B100` reproduced the arm to the last digit (money-weighted return
0.1494087982869519, 203 trades, 237 decisions).

### 10.3 What still guards it

- The six existing conditions, `DSR_MIN = 0.90` and `DSR_POLICY = "methods"` are untouched. The
  yardstick is **added**, not swapped in for "beats SPY and clears the luck score": a share among
  twins says whether an arm beat its own shape, and says nothing about the lab having tried
  hundreds of methods. The deflated Sharpe still answers that.
- `trials` and `trial_yardstick` are append-only. No recorded row is edited; a verdict is
  re-derived, as §7 established.
- A reading that cannot be reproduced (the re-run does not match the recorded trade count and
  return) is refused, not recorded.
- `unmatched` (twins whose median trade count or turnover fell outside half to twice the arm's)
  never clears. A margin over books that traded differently would be partly fees and churn.

### 10.4 What it does not fix

- **The handicap equal-weight books carry against a cap-weighted SPY over 2015–2026** is untouched.
  A twin shares the arm's weighting, so the yardstick cancels that handicap inside its own
  comparison and says nothing about whether the shape can beat SPY in the later years.
- **The DSR ratchet** is untouched. N still rises with every new method and retroactively lowers
  every recorded DSR; the yardstick neither loosens nor tightens that.
- Bracket-engine (`DESIGN_V0`) candidates and books with no picked stock read `not-applicable`,
  which clears. For them the screen is what it was before.

### 10.5 The re-judging pass

The 192 non-control arms that read eligible on 2026-11-13 are measured once, on `main`, after the
code lands: `docs/runbooks/yardstick-backfill.md`. Until then they read as they did, by the staging
above, and `lab promote` refuses each of them until it is measured.
```

### Step 18: the backfill runbook
**File:** `docs/runbooks/yardstick-backfill.md` (create).
**Code:**
````markdown
# Runbook — the random-twin yardstick backfill

From 2026-11-14 the lab's dev screen has a seventh condition: an arm passes only if it out-earned
at least 90% of its random twins, books that repeat its every decision with each picked stock
swapped for a randomly drawn index member of similar trading size (design §10). `lab run` measures
every new arm itself. The arms recorded before that date were never measured. They read as they
did until they are, and `lab promote` refuses every one of them until then.

This runbook measures them, once, on `main`. It writes the shared `lab/lab.sqlite`, so it runs in
the **main checkout**, never in a worktree or a verify run.

## Before you start

- `git pull` on `main`. The random-twin yardstick code must be on it.
- The dev research store is present and current: `/home/miftah/seer/engine/.research` (use the
  `sync-research-store` skill on a second machine). `lab yardstick` reads it. On the store an arm
  was recorded on, it first re-runs the arm and refuses one that no longer reproduces its recorded
  trades and return; on any other store it measures without that check and the reading says so.
- No Sera batch is running. Each measurement holds two worker processes, a child's `lab run` now
  holds two more, and the machine has 11 GiB of RAM.

## The three commands, in order

```bash
engine/.venv/bin/python -m seer_engine lab roles --backfill
```

Records the role (control, dose, idea or treatment) of every recorded dev arm whose method file can
be read, from its own rationale. It is safe to run twice: an arm already recorded is skipped. The
54 P7a seed rows have no method file and are skipped without failing. It prints how many arms it
recorded and how many it skipped. From here on a control arm reads not eligible.

```bash
engine/.venv/bin/python -m seer_engine lab yardstick --pending --jobs 2 > /tmp/yardstick.txt 2>&1; echo "exit $?"
```

Measures every arm that is due: a dev arm that is not a control and whose only failure today, if
any, is the yardstick itself. It prints one line per arm: how many of its twins it out-earned and
whether that clears 90% of its random twins, or `not-applicable` (no picked stock), or `unmatched`.
It writes one `trial_yardstick` row per arm and nothing else: no trial, no N, no test-window look.
Run it as a background job and wait for it to exit; never add `&` or `nohup`.

**What it costs.** On 2026-11-13 the lab held 192 non-control arms that read eligible, which is the
queue. Each arm is 200 twin simulations at about 2 seconds each (the analysis measured 2.6 s for a
first run and 1.5 s for a replay of `M0562-W60-B100`), so about 400 simulation-seconds per arm, and
about 200 seconds at `--jobs 2`. The whole queue is about 192 × 200 s ≈ 10.7 hours, plus 12 seconds
to load the store per command. Run it in batches with `--limit`:

```bash
engine/.venv/bin/python -m seer_engine lab yardstick --pending --limit 24 --jobs 2 > /tmp/yardstick.txt 2>&1; echo "exit $?"
```

24 arms is about 80 minutes. Stage and commit after each batch (below).

**`--jobs 2`, not more.** Every worker holds a full simulation of the market in memory. The result
is the same at any `--jobs` value, so a smaller number only costs time.

**Resuming.** Run the same command again. An arm that already has a reading on this store is not
measured twice (the row is keyed by trial, rule and store, and a second insert writes nothing), so
an interrupted batch picks up where it stopped. An arm that exits 2 because its re-run does not
reproduce its recorded trades and return writes nothing; note its id and leave it. It stays unmeasured,
and `lab promote` keeps refusing it.

```bash
engine/.venv/bin/python -m seer_engine lab reevaluate --demote
```

Moves every `dev-eligible` method that no longer has an eligible non-control arm at today's bars to
`rejected`, and appends a dated note to its analysis saying why. No trial row changes. Run it after
the last batch, and only then: a method whose arms are not all measured yet still reads as it did.
Afterwards, plain `engine/.venv/bin/python -m seer_engine lab reevaluate` moves back any `rejected`
method whose arm now clears every condition, the yardstick included.

## Stage and commit

After each batch and after `--demote`:

```bash
engine/.venv/bin/python -m seer_engine lab stage
git commit -m "lab: yardstick backfill, batch 3 (24 arms measured, 19 cleared)"   # numbers from the batch's own output
git push
```

and after `--demote`:

```bash
git commit -m "lab: yardstick backfill done (192 arms measured; 31 methods demoted to rejected)"   # numbers from the output
```

`lab stage` writes `web/data/lab.json` and git-adds it with `lab/lab.sqlite`; commit only those two
files. Quote counts read back from the command's output or the database, never from this page (CLAUDE.md,
Claim verification).

## Checking the result

```bash
engine/.venv/bin/python -m seer_engine lab status
```

"Promotable now" lists only methods whose chosen arm out-earned at least 90% of its random twins
(or holds no picked stock). Every other dev-eligible method sits under "Refused by the hard gate"
with the reason. An arm that lost to its twins carries the label `beats 90% of random twins` among
its failures.
````
(Replace the two example commit counts with the run's own numbers when committing a real batch; the
runbook says so in the line.)

### Step 19: the skills and CLAUDE.md
**File 19a:** `.claude/skills/explore-and-experiment-new-method/SKILL.md`.
- In step 6 (`6. **Run** \`lab run MNNNN\`...`, :221), insert this paragraph after the sentence that
  ends `...with no live trigger is the failure.` and before `**Exit 2 naming a repeated book**`:
```markdown
   **`lab run` now measures luck itself.** Every arm that clears the other six conditions (and is
   not a control) is replayed against 200 random twins before it is recorded: books with its exact
   dates, weights, entries and exits, holding randomly drawn index members of similar trading size
   instead of its picks. It is recorded eligible only if it out-earned at least 90% of its random
   twins (design §10). This adds a few minutes per eligible arm (`--jobs 2` by default; leave it
   there, the machine has 11 GiB). The run logs one line per measured arm. An arm logged as
   "has no random-twin reading" is recorded not eligible: solo, run the two commands the line names
   (`lab yardstick MNNNN --arm ...`, then `lab reevaluate MNNNN`); child, put the line in your report.
   A hand-written random or blind arm is still allowed as a **control**, declared as one, but it
   no longer decides whether the idea beat luck. The yardstick does that for every arm.
```
- In **Promotion** (:380), after the bullet text ending `D19 has no override.` (:390), append to that
  bullet:
```markdown
  It also refuses (hardgate D20) when that arm has no random-twin reading that clears: it must
  have out-earned at least 90% of its random twins, or hold no picked stock. The way back is
  `lab yardstick <method>`, which writes no trial and spends no look; then promote again.
```
- In the role table row `| promotion | ...` (:33), the child cell becomes:
  `` `lab` marks it `dev-eligible`; report it, and the coordinator promotes. A child never runs `lab promote`, `lab reevaluate --demote` or `lab yardstick --pending` ``
- In **Quick reference** (:588), after the `lab run M0007 ...` line add:
```text
lab yardstick M0007               # measure a recorded arm against its 200 random twins; no trial, no N, no look
```
**File 19b:** `.claude/skills/sera-the-explorer/SKILL.md`.
- In the **dev-eligible** harvest bullet (:164), after the sentence ending
  `...so check it *before* you plan a promotion.` add:
```markdown
     `lab promote` also refuses an arm with no random-twin reading that clears (hardgate D20): an
     arm must have out-earned at least 90% of its random twins. An arm recorded before 2026-11-14
     may not be measured yet; `lab yardstick MNNNN` measures it, then promote again.
```
- In step 6 **Refill** (:192), append:
```markdown
   **Between batches**, when no child is running, the coordinator may work down the yardstick
   backfill: `lab yardstick --pending --limit N --jobs 2` (docs/runbooks/yardstick-backfill.md),
   then `lab stage` + commit + push ("lab: yardstick backfill, batch k"). Never while children
   run: each measurement holds two workers, and so does each child's `lab run`. A child never
   demotes, promotes or runs the backfill.
```
**File 19c:** `CLAUDE.md:84-89`. Replace the paragraph with:
```markdown
Every method experiment runs in the same order: verify the data store is the one you mean →
pre-register the hypothesis and every arm in a committed method file → run the control arms beside
the treatment (cite a recorded control by trial instead when it is the same book on the current
store; `lab run` itself measures every otherwise-eligible arm against its random twins, so a
hand-written random arm is a control, not the luck test) → survivorship and sanity check → record
the verdict (accept or reject) in the journal → queue the follow-up ideas → report to the
coordinator. Pre-registration is not skippable, least of all when the result looks obvious.
```
**File 19d — every other skill line that counts or lists the dev screen's conditions (grep-based; this
phase owns all of it, phase 5 owns none).** Run, from the worktree root:
```bash
grep -rnE 'six (screen )?conditions|all six|six hurdles|five conditions|five P7a|store\.DSR_POLICY' \
  .claude/skills/explore-and-experiment-new-method .claude/skills/sera-the-explorer \
  .claude/skills/update-stale-sera-methods-page .claude/skills/redo-sera-experiments \
  .claude/skills/calculate-assets docs/runbooks CLAUDE.md
```
Update every hit that describes **the dev screen a method must clear** so it also names the random-twin
yardstick, in that file's own voice; leave hits that count something else (the §1 real-money
conditions, a walk-forward's buy conditions, "all six variants" of a recorded run, or the six
*sentences* of `workedSummary` in the stale-page skill's row 6) untouched. At `f83fb237` the grep
finds these, each of which changes:
- `.claude/skills/explore-and-experiment-new-method/SKILL.md:383`: `the five conditions, the DSR
  threshold in force and the N the multiple-testing policy resolved to that day` becomes `the five
  conditions, the DSR threshold in force and the N the multiple-testing policy resolved to that day,
  and (since 2026-11-14) that the arm out-earned at least 90% of its random twins`.
- `.claude/skills/update-stale-sera-methods-page/SKILL.md:36-38`: the list of constants `gate` is
  resolved from (`tuning.MAX_DRAWDOWN`, `tuning.MIN_PROFIT_FACTOR`, `dev._MIN_TRADES`,
  `store.DSR_MIN` and `store.DSR_POLICY`) gains `store.YARDSTICK_MIN_PERCENTILE` (published as
  `gate.yardstickMin` since snapshot 8, phase 5), and the sentence after it gains: `Each trial also
  carries its random-twin reading (\`yardstick\`) and role (\`role\`); a method page's seventh
  condition, "Beats look-alikes", reads them with \`failedNow\`.`
Re-run the grep after the edits; any remaining hit must be one of the "counts something else" kinds
above. The web's own "six" wording (`web/app/sera/**`) is phase 5's and is not touched here.

**Impact:** Step 16's guard reads 19a and 19b ("90% of its random twins" appears in both).

### Step 20: the feature map
**File:** `.claude/skills/verify-seer/features/lab-cli.md`. Phases 1 and 3 edit this file first; each
anchor below quotes the file as they leave it.
- **Sub-features**, the `Write` bullet: as phase 3 leaves it, it ends with phase 3's sentence
  `` `yardstick` (`lab yardstick MNNNN | --arm CANDIDATE | --pending [--limit N] [--jobs J] [--dry-run]`: random twins of a recorded dev arm, one `trial_yardstick` row per arm and store, never a trial; a repeat prints "already measured" and writes nothing).``
  Append directly after that final `.`:
  `` `run` also measures every arm that clears the other six conditions against its random twins before recording it (`--jobs J`, default 2), logs one line per measured arm, and records an arm that lost to them with the label `beats 90% of random twins`. ``
- **Sub-features**, the `Refused` bullet: append directly after its last words, `and any \`--db\`.`
  (phase 3 inserted its own clause earlier in the bullet, before `; \`lab test\``):
  `` `lab promote` on a method whose chosen arm has no random-twin reading that clears (hardgate D20; proven through `lab status`, see Gotchas). ``
- **Driving it with verify.sh**: phase 3 inserted four lines directly after `$V lab RUN twins M0001-TYPO ...`,
  the first being `$V lab RUN yardstick --arm M0562-W60-B100 --jobs 2 --dry-run ...` and the last
  `$V labsql RUN "select trial_n, rule_id, status, draws, beaten, reproduced from trial_yardstick" ...`.
  Insert this line directly **before** phase 3's first line (the copy has no reading yet):
```sh
$V lab RUN status          # with no reading in the copy: "Promotable now" reads "(none)"; every method that was promotable sits under "Refused by the hard gate" with "has never been measured against its random twins"
```
  and this line directly **after** phase 3's last line (M0562-W60-B100 now has its reading):
```sh
$V lab RUN status          # M0562 is back under "Promotable now" only if M0562-W60-B100 out-earned at least 90% of its twins (or reads not-applicable); otherwise it stays refused with "(D20)"
```
- **Gotchas**, append directly after phase 3's last bullet (`- \`lab yardstick\` loads the dev store from the main checkout ...`):
```markdown
- The yardstick (D20) is proven like D19: through `lab status`'s refused block and read-only Python against the run's copy. `lab run`'s own measurement needs a committed method file, so it is proven by `engine/tests/test_lab_yardstick_gate.py` (an injected `measure`, plus one real-engine run at five draws).
```

## Principles applied

- Laziness protocol: the clearing rule exists once (phase 3's `yardstick_clears`), and so do the row builder (`YardstickRow.from_measurement`), the `--jobs` validator (`_positive_count`) and the reading printer (`_yardstick_line`), all phase 3's. `trial_rows` calls `yardstick_clears` on `dataclasses.asdict(YardstickRow)` instead of a second comparison in the runner. `_blocking` gains a parameter instead of a sibling function.
- Laziness protocol / reuse: the batch luck inputs are pulled out of `trial_rows` into `_luck_inputs`, so the provisional DSR that picks which arms to measure is computed by the same expression the recorded DSR is, not by a copy (Step 7).
- Boundary discipline: `--jobs` is validated once in argparse (phase 3's `_positive_count`). `run_method` and `_measure_yardsticks` trust the integer.
- Test behavior, not implementation: the runner tests inject `measure` through `run_method`'s public parameter and assert on the recorded trial, the reading row, the method status and the lock state. The fixtures that must clear D20 stamp a real `trial_yardstick` row (`labkit.stamp_yardstick`) instead of patching `store.yardstick_of` file-wide, which would have hidden the clause from the whole hardgate suite. The one internal seam patched (`_due_for_yardstick`) is patched only in the real-engine plumbing test, and the filter it replaces is proven by the fake-measure tests.
- Encode lessons in structure: the DSR bar once went stale in six shipped files. The yardstick bar gets a guard on the day it ships (`test_no_shipped_document_states_a_yardstick_bar_the_lab_does_not_apply`), not a sentence asking authors to keep it in sync.
- Sequence into verifiable units: store (Steps 1-5) → runner (6-9) → hardgate (10-11) → CLI (12) → tests (13-16) → docs (17-20). Each group ends in a pytest run that can fail (Verification lists them in that order).

## Verification

**Build:** `cd /home/miftah/.worktrees/seer/random-twin-yardstick && (test -x engine/.venv/bin/python || (python3.11 -m venv engine/.venv && engine/.venv/bin/pip install -q -e 'engine[dev]')) && engine/.venv/bin/ruff check engine`

**Tests:**
- After Steps 1-5: `engine/.venv/bin/pytest -n0 -q engine/tests/test_lab_gate_policy.py engine/tests/test_lab_store.py`
- After Steps 6-9: `engine/.venv/bin/pytest -q engine/tests/test_lab_runner.py engine/tests/test_lab_amendments.py engine/tests/test_lab_repeat_refusal.py engine/tests/test_lab_fold_verdict.py`
- After Steps 10-16b: `engine/.venv/bin/pytest -q engine/tests/test_lab_yardstick_gate.py engine/tests/test_lab_hardgate.py engine/tests/test_lab_prereg.py engine/tests/test_lab_status.py engine/tests/test_lab_gate_wording.py engine/tests/test_lab_fold_verdict.py engine/tests/test_lab_test_window.py engine/tests/test_lab_roles.py engine/tests/test_lab_yardstick_record.py`
- Whole suite: `engine/.venv/bin/pytest engine/tests` (DB tests need `PG_TEST_URL`; CLAUDE.md).
- Known red on the base commit, not this phase's: `test_lab_hardgate.py::test_the_buy_signal_fires_on_the_promoted_arm_and_the_set_moved_both_ways` (run this session on `f83fb237`: 1 failed, 206 passed, 2 skipped across test_lab_hardgate, test_lab_gate_wording, test_lab_prereg, test_lab_status).

**Proof:** the screen refuses on the real lab copy and in the real `lab run` recording path.
- Harness: `.claude/skills/verify-seer` (`V=.claude/skills/verify-seer/scripts/verify.sh`), run from the worktree. `lab promote` and a real `lab run` cannot be driven there (promote is refused, run needs a committed method file), so R2.3 is shown through `lab status` (the same `hardgate.check`) and R2.1 through exact pytest ids. Both are the routes `lab-cli.md` prescribes.
- Feature-map entries: `.claude/skills/verify-seer/features/lab-cli.md`
- Setup for J4 and J6: `$V up --no-web --empty` (prints `RUN=`), then `export RUN=<that id>`. `$V down $RUN` at the end, failed runs included.
- Journeys:
  - **J1** · traces R2.1 — `cd engine && .venv/bin/pytest -n0 -q tests/test_lab_yardstick_gate.py -k "loses_to_its_twins or beats_its_twins or what_lab_run_records or only_arms_that_clear or left_unmeasured or nothing_eligible or no_readings_records"` → passes when pytest reports `10 passed` (1 + 1 + 4 parametrized + 1 + 1 + 1 + 1) and 0 failed: an arm that clears the other six conditions is measured outside the write lock, recorded eligible only when its share is at least 0.90, and recorded not eligible with `beats 90% of random twins` otherwise.
  - **J2** · traces R2.1 — `cd engine && .venv/bin/pytest -n0 -q "tests/test_lab_yardstick_gate.py::test_the_real_engine_measures_an_arm_inside_lab_run"` → passes when it reports `1 passed`: the real `yardstick.measure`, called by `run_method`, wrote a `trial_yardstick` row with `draws == 5` under the trial number SQLite assigned.
  - **J3** · traces R2.2 — `cd engine && .venv/bin/pytest -n0 -q tests/test_lab_yardstick_gate.py -k "old_arm_reads_eligible or unmatched_reading or clearing_reading or since_the_rule or real_failure or goes_last or control_arm_never or test_window_row or reads_as_before or own_words or reevaluate"` → passes when pytest reports `15 passed` and 0 failed: `store.verdict` carries `beats 90% of random twins` for a reading below 0.90 or `unmatched`, and for an unmeasured arm recorded on 2026-11-14, and adds nothing on a lab with no role, no reading and no new trial.
  - **J4** · traces R2.2 — on the verify copy: (a) `$V labsql $RUN "select n from trials where candidate_id = 'M0562-W60-B100' and window = 'dev'"` (note the `n`); (b) `$V lab $RUN yardstick M0562 --arm M0562-W60-B100 --jobs 2` (a few minutes; exit 0); (c) `$V labsql $RUN "select status, beaten, draws, percentile from trial_yardstick where trial_n = <n>"`; (d) `SEER_ENV_FILE=~/.local/state/seer-verify/$RUN/engine.env PYTHONPATH=engine/src engine/.venv/bin/python -c "import sqlite3,sys; from seer_engine.lab import store; c=sqlite3.connect('file:'+sys.argv[1]+'?mode=ro', uri=True); c.row_factory=sqlite3.Row; t=c.execute('select * from trials where n=?',(int(sys.argv[2]),)).fetchone(); y=store.yardstick_of(c,t['n']); v=store.verdict(c,t); print(y['status'], y['percentile'], v.eligible, v.failed)" ~/.local/state/seer-verify/$RUN/lab.sqlite <n>` → passes when (c) shows exactly one row with `draws = 200`, and (d) prints `eligible True` with no `beats 90% of random twins` in `failed` if and only if `status` is `measured` and `percentile >= 0.9` (or `status` is `not-applicable`). Any other reading prints `eligible False` with `beats 90% of random twins` last in `failed`. Before (b), run `SEER_ENV_FILE=~/.local/state/seer-verify/$RUN/engine.env PYTHONPATH=engine/src engine/.venv/bin/python "$TMPDIR/measure_s10.py" ~/.local/state/seer-verify/$RUN/lab.sqlite` (Step 17's script). Its `dev arms carrying the yardstick label` line must print 0 on a copy whose `latest run_at` is before `2026-11-14`, which is plan invariant 5 on the real lab. (If the copy holds trials run on `main` on or after 2026-11-14 by pre-merge code, the count is the number of those that clear every other condition — Decision D14 — and is not a failure; say so in the report with the count read back.)
  - **J5** · traces R2.3 — `cd engine && .venv/bin/pytest -n0 -q tests/test_lab_hardgate.py -k "yardstick_decision or never_measured or not_applicable_reading or out_earned or unmatched_variant"` → passes when pytest reports `7 passed` and 0 failed. Two of them drive `lab promote` through `commands/lab.py:run`, exit 2, leave `prereg/` uncreated and the database bytes unchanged, and leave the method `dev-eligible`.
  - **J6** · traces R2.3 — on a fresh verify copy (before J4's measurement): `$V lab $RUN status > status.txt; echo $?` → passes when it exits 0, the lines between `Promotable now` and `Refused by the hard gate` read `(none)`, and each method that `lab status` listed as promotable on the base commit appears under `Refused by the hard gate` with the sentence `has never been measured against its random twins` and `(D20)`. On `f83fb237`, read back this session, those were M0197, M0284, M0363, M0383, M0513 and M0562. If `git diff --quiet f83fb237 -- lab/lab.sqlite` reports a change, list them again first by running base-commit code on the same copy: `git -C /home/miftah/seer worktree add /tmp/base f83fb237`, then `PYTHONPATH=/tmp/base/engine/src SEER_LAB_DB=<a copy> ... lab status`.
- Neighbor check: `lab reevaluate`, `lab status` and `lab run` were the most likely to break: `cd engine && .venv/bin/pytest -q tests/test_lab_gate_policy.py tests/test_lab_status.py tests/test_lab_runner.py tests/test_lab_amendments.py tests/test_lab_prereg.py tests/test_lab_snapshot.py` → passes when 0 failed. On the verify copy, `$V lab $RUN reevaluate` exits 0 and moves nothing it did not move on the base commit.
- Cost: no paid drives. J4 runs about 200 local simulations (a few minutes at `--jobs 2`). Nothing else is slow.

**Exit criteria:** on a fixture lab, an arm that clears the other six conditions and loses to its twins records not eligible and its method `rejected`; an old arm flips in `verdict` once a failing reading exists; `lab promote` exits 2 on an unmeasured arm and writes nothing; on the committed lab with no reading, `verdict` carries the yardstick label on no arm (invariant 5); a newly written pre-registration names the yardstick; Step 19d's grep leaves no skill line that lists the dev screen without it; ruff is clean and every lab test file passes except the one known-red buy-signal test.

**Commit (explicit paths only; never `git commit -a`; `lab/lab.sqlite` and `web/data/lab.json` are never staged — invariant 2):**
```bash
cd /home/miftah/.worktrees/seer/random-twin-yardstick
git checkout -- lab/lab.sqlite 2>/dev/null; git status --porcelain lab web/data   # must print nothing
git add engine/src/seer_engine/lab/store.py engine/src/seer_engine/lab/runner.py \
        engine/src/seer_engine/lab/hardgate.py engine/src/seer_engine/lab/prereg.py \
        engine/src/seer_engine/commands/lab.py engine/tests/labkit.py \
        engine/tests/test_lab_yardstick_gate.py engine/tests/test_lab_hardgate.py \
        engine/tests/test_lab_prereg.py engine/tests/test_lab_status.py \
        engine/tests/test_lab_gate_wording.py \
        docs/plans/2026-10-04-method-lab-design.md docs/runbooks/yardstick-backfill.md \
        .claude/skills/explore-and-experiment-new-method/SKILL.md \
        .claude/skills/sera-the-explorer/SKILL.md \
        .claude/skills/update-stale-sera-methods-page/SKILL.md \
        .claude/skills/verify-seer/features/lab-cli.md CLAUDE.md
# plus any other file Step 19d's grep made you edit, named explicitly
git commit -m "lab: the random-twin yardstick as a screen condition (random-twin-yardstick phase 4)"
```

## Handoffs

- **Phase 5 (snapshot and Sera pages):** from the moment this phase lands, `published_verdict` and therefore the snapshot's `failedNow` can carry `store.YARDSTICK_LABEL` ("beats 90% of random twins") for a dev arm. That happens on any arm with a failing reading, and on any arm recorded on `main` on or after 2026-11-14 with no reading. `web/lib/sera/lab.test.ts:60` asserts every published label is a known one, so phase 5 must teach the web this label before or with the merge that brings a labelled arm into `web/data/lab.json`. This phase does not regenerate `lab.json`.
- **Settled at reconcile (phase 3 duplicates):** this phase uses phase 3's `YardstickRow.from_measurement`, `_positive_count` and `_yardstick_line`; its own `runner._yardstick_row`, `_job_count` and second `_yardstick_line` were dropped. `labkit.stamp_yardstick` stays here: phase 3 has no fixture helper. Phase 3's `yardstick_clears` accepts any mapping, stated and tested there.
- **Phase 1:** this phase reads `CONTROL_LABEL in failed` in `store._yardstick_binds`; phase 1 appends it before the yardstick block, in `verdict` and in `trial_rows` (label order: owner conditions, luck, `CONTROL_LABEL`, `YARDSTICK_LABEL`).
- **Settled at reconcile (Decision D13):** `prereg.gate_text` now names the yardstick (Step 16b). No test pins the historical text of an already-written pre-registration, so only newly written files carry the clause; the committed ones are frozen and keep theirs.
- **Unowned:** `commands/lab.py:_promotable_now`'s "held" section tells a reader that `lab reevaluate <id>` moves a rejected method whose best arm is derived-eligible. For an arm recorded since 2026-11-14 with no reading, `verdict` already fails it, so the section never lists it. No change needed today; noted in case the staging date moves.
- **Pre-existing red, not this phase's:** `engine/tests/test_lab_hardgate.py::test_the_buy_signal_fires_on_the_promoted_arm_and_the_set_moved_both_ways` fails on `f83fb237` (it pins the committed lab's buy-signal names; verified this session). Not re-pinned here.
- **Lab operation after the set lands:** the backfill (`docs/runbooks/yardstick-backfill.md`) runs on `main` and commits `lab/lab.sqlite`. No phase does it.

## Rollback

`git revert` this phase's commits. It adds no table and bumps no schema version. The
`trial_yardstick` rows that a landed `lab run` wrote stay in the database (append-only, phase 3's
table) and nothing reads them as a condition once `verdict`, `trial_rows` and `check` are reverted.
Trials recorded while this phase was live keep their recorded `failed` string, including
`beats 90% of random twins` where it applied. `store.verdict` re-derives every condition and never
reads that label back from the string, so after a revert those arms read by the six conditions
alone. A method this phase's run recorded `rejected` for losing to its twins stays `rejected` until
plain `lab reevaluate` moves it, which it does when the arm clears the six conditions.

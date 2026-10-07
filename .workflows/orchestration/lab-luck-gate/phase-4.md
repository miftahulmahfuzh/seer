# Phase 4: The verdict is derived under one policy, at evaluation time

**Plan set:** `LAB_LUCK_GATE_PLAN.md`
**Analysis:** `20261007-085606-D3K1_code_analyzer.md`
**Satisfies:** R1 — the gate admits nothing at 110 trials and the bar rises with every exploration
regardless of merit
**Depends on:** Phase 1 (`lab/npolicy.py`), Phase 2 (`trial_moments`, `store.moments_of`,
`runner.trial_rows` writing moments), **Phase 8** (`tuning.MAX_DRAWDOWN = 0.20` and the live
`dev.FAILURE_LABELS`) — this phase's code reads that constant at evaluation time and works at
either value, but its **exit criteria pin three eligible candidates**, which needs the 20% bar
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/lab`

> **Written after the owner's mid-flight instruction of 2026-10-07** — *"this 0.95 threshold is too
> high man. my risk appetite is 0.90"* — and against Decisions **D1** / **D1b** and Scope in the
> plan index. The lever that moves in this phase is the **threshold**, not N.
>
> **Reconciled 2026-10-07.** The index's `### Phase 4` section now matches this file: `DSR_POLICY`
> ships `all-trials`, `DSR_MIN` is this phase's to move, and `best_dev_eligible(M0022)` is
> **W-TV14** (MAR 0.857 beats W-TV16's 0.816 — MAR decides, not DSR). The earlier staleness note
> that stood here is resolved and removed. Two other reconciliations land in this file: the CLI
> name pairing (`lab reevaluate` writes, phase 5's read-only command is now `lab luck` — owner's
> call, Decision D9) and the one-writer rule for `web/data/lab.json` (Decision D10, Step 10).

---

## Goal

`store.DSR_MIN` goes **0.95 -> 0.90**, the owner's stated risk appetite. `store.DSR_POLICY` ships
**`"all-trials"`** — N stays at every dev trial, exactly as today — so the policy machinery phase 1
built is live, inspectable and tested, but the second lever is deliberately not pulled.

A trial's eligibility becomes a **read**, and **every** condition is decided at read time:
`store.verdict` re-derives the four threshold owner conditions from the trial's own recorded
columns against the live constants, carries `owner inputs` from the record, and decides the luck
test on the trial's DSR **at the gate's current N** — exactly from `trial_moments` where they
exist, and otherwise by re-evaluating the recorded DSR there (`store.dsr_at`). A trial whose DSR
cannot be evaluated at all fails the luck test. The lab gains one status edge,
`rejected -> dev-eligible`, which `store.reevaluate_method` takes only for a trial that clears all
five conditions at the bars in force. On the committed database this moves **M0022 and M0020** to
`dev-eligible`, which makes `lab promote` reachable for the first time.

### The sharpest edge in this phase: a recorded `failed` string is a fact about a bar that has moved

`trials.failed` is append-only, and all 110 recorded rows carry the labels of the thresholds in
force on their run date: **`"DSR >= 0.95"`** on every luck failure, and **`"max DD <= 15%"`** on
every drawdown failure. Since 2026-10-07 the owner has moved **both** bars — `DSR_MIN` to 0.90
(D1) and `tuning.MAX_DRAWDOWN` to 0.20 (D6, phase 8) — so the live labels read `"DSR >= 0.90"` and
`"max DD <= 20%"` and **none of the recorded strings will ever be rewritten**.

An earlier draft of this phase read the four non-luck conditions back out of that string and
re-decided only the luck test. **That design is superseded and must not be implemented.** It was
sound while the luck threshold was the only thing moving; with the drawdown bar moving too it
freezes every recorded row at the bar it was judged by — all 110 rows would keep
`"max DD <= 15%"` forever, and `M0020-W-NOSTOP` (19.3% drawdown, now inside a 20% bar) could never
become eligible no matter what the owner set.

**The design, reconciled — four re-derived, one carried.** `store.owner_failures(trial)` takes the
**trial row**, not its `failed` string, and:

| condition | where it comes from now | why |
|---|---|---|
| `beats SPY TR` | re-derived: `total_return > spy_tr_return` | recorded columns, no threshold constant at all |
| `max DD <= …` | re-derived: `max_drawdown <= tuning.MAX_DRAWDOWN` | the owner moved this bar; the recorded label names the old one |
| `PF >= …` | re-derived: `profit_factor >= tuning.MIN_PROFIT_FACTOR` | a threshold, so re-derivable and liable to move |
| `>= … trades` | re-derived: `trades >= dev._MIN_TRADES` | same |
| **`owner inputs`** | **carried from the recorded `failed`** | **the exception.** It is not a threshold and is in no column — it is a property of the *candidate* (did a human hand-pick a parameter?), decided by `dev.candidate_owner_inputs` at run time. There is nothing to re-derive it from, and nothing to re-derive it *against*: no constant re-decides it, so it never goes stale |

All four re-derivations are the same comparisons `dev.py:362-372` makes, against the same
constants, on columns `trials` already stores — so nothing is re-run, nothing is estimated, and a
trial's conditions read today exactly as a fresh `lab run` of the same numbers would read them.
That is R2's comparability, extended from the luck test to every threshold the owner can move.

**The luck-label prefix matcher survives, for the readers that still parse the string.**
`store.LUCK_LABEL_PREFIX = "DSR >= "` and `store.is_luck_label` stay exported, because three
consumers still read a recorded `failed` for **display or history** rather than for a verdict:
`lab status`'s "Closest to eligible" table (`commands/lab.py:205-206`, fixed in Step 7e),
phase 5's status output, and phase 7's `web/lib/sera/derive.ts`. Those readers must never match by
equality with a live constant — **and the same now goes for the drawdown label**, which is phase
7's `derive.ts` fix and a new one (see **Handoffs #9**).
`test_a_recorded_095_label_is_read_as_zero_owner_misses` and
`test_a_recorded_15pct_drawdown_label_does_not_freeze_a_trial_at_15pct` are the two tests that
prove the moved bars actually reach the recorded rows.

### What this loosens, stated plainly

It loosens **one of the two numbers the owner moved on 2026-10-07**: `DSR_MIN`, 0.95 → 0.90. The
other — `tuning.MAX_DRAWDOWN` 0.15 → 0.20 (Decision **D6**) — is **phase 8's constant**, not this
phase's: this phase reads it through `tuning` at evaluation time and never assigns to it. Both are
real loosenings of a gate that exists to prevent self-deception, and a reviewer is entitled to
argue with either. What makes them defensible rather than arbitrary is that each is *one* number,
*measured*, *dated to the owner*, and *reversible by editing one constant*:

| at (N, luck bar, drawdown bar) | candidates admitted |
|---|---|
| **110, 0.95, 15%** (on `main`) | none — the deadlock |
| 110, **0.90**, 15% (this phase alone) | **two**: `M0022-W-TV14` (DSR 0.912, MAR 0.86) and `M0022-W-TV16` (DSR 0.916, MAR 0.82) |
| **110, 0.90, 20%** (this phase + phase 8 — what ships) | **three**: the two above **and `M0020-W-NOSTOP`** (DSR 0.913 re-evaluated at N=110, max DD 19.3%, MAR 0.79) |
| 23, 0.90, 20% (and the N lever too) | more again, including `M0011-RAW20-TV12` at MAR 0.60 — **not done** |

The two levers the owner named admit the three highest-MAR books in the lab. **The N lever stays
where it is** — `DSR_POLICY = "all-trials"` — so the measurement stays on the table without the
change being made, inspectable through phase 5's read-only `lab luck`.

It leaves in place, untouched:

- **The *set* of five P7a D8 conditions, and the comparisons that apply them**
  (`dev.FAILURE_LABELS`, `dev.py:362-372`). This phase adds no condition, removes none, and
  changes none of the comparisons. What it changes is **when** they are evaluated: `verdict`
  re-derives the four *threshold* conditions from the trial's recorded columns at read time,
  against whatever the constants say now, instead of reading a label frozen at run time. The fifth,
  **`owner inputs`**, is carried from the recorded string — it is not a threshold, it is in no
  column, and no constant re-decides it.

  **The drawdown *threshold* is in scope and is not frozen.** `tuning.MAX_DRAWDOWN` moves to 0.20
  in phase 8 on the owner's instruction (D6); invariant 4 does not cover it. Do not read "the five
  conditions are untouched" as "the drawdown bar is untouched": the *condition* is untouched, the
  *number* it compares against is the owner's and has moved.

  Two candidates with a recorded DSR at or above 0.90 stay ineligible on something no threshold in
  this set rescues: `M0019-RAW20-S25` (max DD **20.7%**, outside even the new 20% bar) and
  `M0001-TV10` (does not beat SPY TR). A third, `M0007-N20-RAW`, now clears the drawdown bar at
  19.6% but **fails the luck test**: its DSR re-evaluated at today's N = 110 is **0.898**, under
  0.90 (its *recorded* 0.914 was at its recorded N = 85 — Decision D8's quoting convention, and
  D11, which settled that the gate reads the re-evaluated number).
  This is enforced twice, independently: `verdict` derives every condition from the columns, and
  `reevaluate_method` re-runs all four comparisons in its own code, written separately, before it
  will take the status edge.
- **N.** `DSR_POLICY = "all-trials"` resolves to 110 on the committed database, which is what
  `runner.trial_rows` already uses. New runs are deflated by exactly the N they are deflated by on
  `main`.
- `deflated_sharpe`, `DEV_END`, the D9 guard, the dev store fingerprint.
- **Append-only `trials`.** Nothing here inserts, updates or deletes a trial row, so the lab's N
  does not move and `store.test_looks` stays 0. All 110 rows keep their `dsr`, `eligible`,
  `failed` and `n_trials_at_run` byte-for-byte.
- **Forward-only status.** The new edge is additive: `rejected` gains one successor and loses none
  of its refusals (`rejected -> idea`, `-> registered`, `-> promoted`, `-> paper` all still raise).

### The ratchet is deferred, not fixed — say so

Per **D1b**: at `DSR_MIN = 0.90`, `M0022-W-TV16` passes at N=110 (0.916) and fails at N≈200
(0.877), roughly four more Sera nights. **A threshold change buys runway; it does not stop the
bar rising.** This phase does not pretend otherwise, and the warning that makes the next deadlock
visible before it arrives belongs to phase 5's `lab status` (D1b), not here.

### The asymmetry this creates, and why it is correct

`M0011-RAW20-TV14-N21` stays **ineligible**, and it fails under both readings of its number:

- its **recorded DSR is 0.8974, at its recorded N = 90** — already below the new 0.90 bar on its
  own terms;
- **re-evaluated at today's gate N = 110 it is 0.884**, further below. That is the number the gate
  actually uses.

No `lab remeasure` is needed to reach either conclusion: `store.dsr_at` re-evaluates it from the
recorded `dsr` and the lab's own Sharpe column. Remeasuring would make the recomputation exact
rather than recovered; it would not change the answer.

**The quoting convention this phase follows, and that every file in this set now follows
(Decision D8).** **The gate always uses the re-evaluated-at-current-N value.** The recorded value
is quoted only when the subject is what the database holds, and is then always labelled
*recorded*, with its N. "0.8974 recorded at N = 90" and "0.884 re-evaluated at today's N = 110"
are both true, are different statements about the same trial, and differ by more than the bar's
own margin; a bare "0.884" is not a fact about anything.

So **`RM-FR` remains lab-`rejected` while `RMW-FR` becomes
lab-`dev-eligible`**, even though the owner admitted both to the paper roster by hand. That
asymmetry is not a bug: it is exactly the divergence R4 names, now partly closed and partly
recorded. It gets its own test.

---

## Interface Contract

**Deletes:** nothing.

**Renames:** nothing. `DSR_LABEL` keeps its name but **changes value** (see below).

**Value changes (both in `engine/src/seer_engine/lab/store.py:79-80`):**

- `store.DSR_MIN` `0.95` -> `0.90`
- `store.DSR_LABEL` `"DSR >= 0.95"` -> `f"{LUCK_LABEL_PREFIX}{DSR_MIN:.2f}"` == `"DSR >= 0.90"`.
  **This is load-bearing and easy to get wrong:** 110 recorded `failed` columns contain the string
  `"DSR >= 0.95"`. Any code that recognises the luck label by equality with the constant stops
  recognising the recorded ones the moment the constant changes, and every luck-only rejection
  would then look like an owner failure and stay rejected forever. Hence `is_luck_label` below,
  and hence the one-line fix to `commands/lab.py:206`.

**Creates (`engine/src/seer_engine/lab/store.py` unless noted):**

- `store.LUCK_LABEL_PREFIX` — `"DSR >= "`
- `store.is_luck_label(label: str) -> bool` — **the single rule for recognising a luck label.**
  Prefix match, never equality with the live constant. Phase 5 calls it (via `owner_failures`).
- `store.DSR_POLICY` — module constant, `"all-trials"`
- `store.Gate` — frozen dataclass `(n: int, policy: str)`
- `store.Verdict` — frozen dataclass. **Field shapes, pinned so no caller has to guess:**

  | field | type | notes |
  |---|---|---|
  | `dsr` | `float \| None` | None when `deflated_sharpe` is undefined |
  | `failed` | **`tuple[str, ...]`** | **a tuple of labels, never a string.** Ordered: the owner conditions in recorded order, then the luck label last if it failed. `"; ".join(v.failed)` is the `trials.failed` convention. Empty tuple when eligible |
  | `eligible` | `bool` | `== (v.failed == ())`, always |
  | `n` | `int` | the N the DSR was judged at |
  | `policy` | `str` | the policy name that resolved `n` |
  | `derived` | `bool` | True when the DSR in this verdict was **evaluated at `n`**; False when it could not be, in which case `dsr is None` and the luck label is among `failed`. **Never means "the recorded columns were returned verbatim"** — nothing is ever returned verbatim any more |

- `store.Reevaluation` — frozen dataclass `(method_id: str, status_before: str, status_after: str,
  moved: bool, gate: Gate, unblocked: tuple[str, ...], derived: int, unjudgeable: int,
  dev_trials: int)`. `unblocked` is a **tuple of candidate id strings**.
- `store.gate(conn, policy=None) -> Gate` — **memoised** on a content-derived key, because
  `npolicy.effective_n` runs an eigendecomposition over 110 curves and `lab status` would
  otherwise pay for it once per method
- `store.sr_star(n_trials: int, var_trials: float) -> float` — the deflated Sharpe's daily hurdle
  `SR*` at `n_trials` looks. `dev.deflated_sharpe`'s own `sr_star` line and its own
  `_EULER_GAMMA`, isolated so the hurdle can be asked for at an N no trial was run at. **Pure.**
- `store.recover_dsr(*, sharpe_daily, dsr_at_run, n_at_run, var_trials, n_trials) -> float | None`
  — a recorded DSR re-evaluated at a different N, by inverting the per-trial constant
  `k = Φ⁻¹(dsr_at_run) / (SR − SR*(n_at_run))` and returning `Φ((SR − SR*(n_trials))·k)`. **Pure.**
  Returns `dsr_at_run` **exactly** when `n_trials == n_at_run`, for any `var_trials`. None where
  the inversion is undefined. **Reconciled: this lives in `store.py`, not in `commands/lab.py`** —
  phase 5 drafted it there, and then phase 4 turned out to need the same arithmetic for the gate
  itself. One owner, one definition; phase 5 re-exports the two names.
- `store.dev_sharpe_variance(conn) -> float | None` — `statistics.variance(dev_daily_sharpes(conn))`,
  None below two. The dispersion the expected maximum is drawn from, **as it stands now**
- `store.dsr_at(conn, trial, n_trials) -> float | None` — **this trial's deflated Sharpe at
  `n_trials` looks.** Exact from `trial_moments` when they exist; otherwise recovered from the
  recorded `dsr` by `recover_dsr`. **Both routes deflate by `dev_sharpe_variance(conn)` — today's
  lab-wide trial-Sharpe variance — read once before either route branches; the `var_trials`
  column stored beside a trial is historical record only and is never read here (Decision D12).**
  None when neither route is possible — the 54 P7a seed rows before phase 9
  (`dsr IS NULL`, `seed.py:136`), or a lab with fewer than two dev Sharpes
- `store.pending_gate(conn, method_id, pending, *, policy=None) -> Gate`
- `store.OWNER_INPUTS_LABEL` — `dev.FAILURE_LABELS[-1]`, i.e. `"owner inputs"`: the one D8
  condition with no number in it, and therefore the one whose recorded label can never go stale
- `store.recorded_labels(failed: str) -> tuple[str, ...]` — a recorded `failed` string split on
  `"; "`, empties dropped. **History, not a verdict.** The labels it returns name the thresholds in
  force on the trial's run date
- `store.owner_failures(trial: Mapping[str, Any] | sqlite3.Row) -> tuple[str, ...]` — **the shared
  helper, and it takes the trial row, not its `failed` string.** The four threshold conditions are
  **re-derived** from `total_return`/`spy_tr_return`, `max_drawdown`, `profit_factor` and `trades`
  against the live `tuning.MAX_DRAWDOWN`, `tuning.MIN_PROFIT_FACTOR` and `dev._MIN_TRADES`;
  `owner inputs` is **carried** from the recorded string. Returns labels in `dev.FAILURE_LABELS`
  order, using the **live** label text. Phase 5's `_owner_misses(row)` must be
  `list(store.owner_failures(row))`, not its own rule and not a reading of `row["failed"]`.
- `store.verdict(conn, trial, *, at=None, policy=None) -> Verdict`
- `store.reevaluate_method(conn, method_id) -> Reevaluation`
- `store.reevaluate(conn, method_ids=None) -> list[Reevaluation]`
- `store.REEVALUATION_MARKER` — `"Re-evaluated under the "`
- `commands.lab._reevaluate`, subparser **`"reevaluate"`**, `_HANDLERS["reevaluate"]`
- `engine/tests/test_lab_gate_policy.py` (new)

**Signature changes:**

- `store.best_dev_eligible(conn, method_id)` -> `(conn, method_id, *, at: Gate | None = None,
  policy: str | None = None)`. Return type, ordering, filters and "exactly one row" unchanged;
  only the eligibility test moves from the frozen `eligible` column to `verdict(...).eligible`.
  Its one caller, `prereg.promote_method` (`lab/prereg.py:472`), needs no edit.
  **`at` is the explicit escape hatch for phase 5's loop:** resolve `g = store.gate(conn)` once
  and pass `at=g` to all 23 calls, so the estimator is provably resolved exactly once regardless
  of what the memo does.
- `store.TRANSITIONS` gains `("rejected", "dev-eligible")`.
- `runner.trial_rows`'s body changes how `n_trials` is computed; signature and return unchanged.

**Requires (from earlier phases):**

- Phase 1: `npolicy.effective_n(conn, policy) -> NCount` with `.n: int` and `.policy: str`. This
  phase reads only those two attributes, only through `store.gate`. **It must not inherit phase
  1's `DEFAULT_POLICY`:** `store.DSR_POLICY` is set explicitly to `"all-trials"` and always passed
  as an argument, so no reader has to reason about which module's default wins. A test pins it.
- Phase 1: `npolicy.POLICIES` containing `"all-trials"`, `"methods"`, `"effective"`.
- Phase 1: `effective_n(conn, "all-trials").n == store.dev_trial_count(conn)` — 110 on the
  committed database. A test in this phase pins that too, because `runner.trial_rows` now gets its
  N through `npolicy` and must reproduce today's number exactly.
- Phase 2: table `trial_moments` with columns `trial_n, sr_daily, t, skew, kurt, var_trials,
  n_at_run, measured`, and `store.moments_of(conn, trial_n) -> sqlite3.Row | None`.
- Phase 2: `SCHEMA_VERSION = "3"` and the v2->v3 branch in `store._migrate`, additive.
- Phase 2: `runner.trial_rows` already computes per-row moments once and writes one
  `trial_moments` row per new trial in the same transaction.

**Leaves alone (owned by others):**

- `lab/npolicy.py` (Phase 1) — called, never edited.
- `trial_moments`' schema, triggers, writer, `_migrate` branch (Phase 2) — read only.
- `commands/lab.py`'s `_status` body beyond the one `misses()` line, and the new `lab luck`
  (Phase 5). The D1b closeness warning is phase 5's.
- `paper/roster.py` (Phase 6), including its three historical `"DSR >= 0.95"` gate-note strings,
  which are statements about what happened and must not be retro-edited.
- `store.snapshot()`'s `gate` dict keys, `lab/prereg.py`, `docs/`, `web/` (Phase 7).
- `dev.FAILURE_LABELS`, `dev.deflated_sharpe`, `dev.DEV_END`, the D9 guard,
  `store.summary_rows`, every recorded `trials` column, the test window.
- **`backtest/tuning.py` (Phase 8).** `tuning.MAX_DRAWDOWN` moves 0.15 -> 0.20 on the owner's
  instruction (Decision D6). This phase **reads** it — `owner_failures` and `_blocking` both
  import `tuning` locally and compare against it at call time — and must never assign to it.
  `dev.FAILURE_LABELS`'s drawdown entry moves with it, also in phase 8; this phase unpacks that
  tuple positionally and never types one of its strings.

---

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/store.py` | modify | `DSR_MIN` 0.95->0.90; `DSR_LABEL` derived + `LUCK_LABEL_PREFIX` + `is_luck_label` + `owner_failures` (the one shared luck-label rule); `DSR_POLICY = "all-trials"`; the `("rejected","dev-eligible")` edge; the derived-verdict section with a memoised `gate`; `best_dev_eligible`; module docstring |
| `engine/src/seer_engine/lab/runner.py` | modify | `trial_rows` takes N from `store.pending_gate`; two docstrings |
| `engine/src/seer_engine/commands/lab.py` | modify | `_reevaluate` + subparser + `_HANDLERS` + docstring; `misses()` at line 206 uses `is_luck_label` |
| `engine/tests/test_lab_store.py` | modify | `test_status_only_moves_forward` stops using the now-legal edge as its example |
| `engine/tests/test_lab_gate_policy.py` | create | the whole phase, including every VERIFY claim |
| `lab/lab.sqlite` | migrate | schema v3, the new transition row, and M0022 `rejected -> dev-eligible`. **This phase is its only writer in the set** (invariant 6, Decision D5) |
| `web/data/lab.json` | regenerate | the snapshot re-exported from the migrated database: `gate.dsrMin` 0.95 -> 0.90, M0022's status/analysis, `summary.byStatus`. **Phase 7 regenerates it again** after it adds the gate's policy keys — see Decision D10 and Step 10 |

**Seven files** (the plan index's draft said 6; reconciled). Four of them are shared with other
phases.

### Shared-file protocol (reconciled — read before editing `store.py`, `runner.py` or `commands/lab.py`)

| file | phases that write it | this phase's regions |
|---|---|---|
| `lab/store.py` | 2, **4**, 6, 7 | `DSR_MIN`/`DSR_LABEL`/`LUCK_LABEL_PREFIX`/`is_luck_label`/`DSR_POLICY` (`:79-80`), `TRANSITIONS` (`:62-73`), `best_dev_eligible`'s body, the new derived-verdict section after it, two docstring paragraphs |
| `lab/runner.py` | 2, **4** | two lines of `trial_rows` + two docstrings (Steps 6a, 6b) |
| `commands/lab.py` | 3, **4**, 5 | `_reevaluate` after `_promote`, its subparser after the `promote` block, one `_HANDLERS` line after `"promote"`, the docstring entry after the `lab promote` block, and the one-line `misses()` fix at `:204-206` |
| `tests/test_lab_store.py` | 2, **4**, 6 | `test_status_only_moves_forward` only |

Three rules, the same three every phase in this set follows:

1. **Edit only at your own named anchors, and never rewrite a whole literal.** `_HANDLERS` gets
   **one inserted line** from this phase, never a replacement of the dict — phase 3 inserts
   `"remeasure"` and phase 5 inserts `"luck"` into the same literal, and a whole-dict rewrite
   deletes the others' keys silently.
2. **Anchor on quoted text, never on a line number.** Every `store.py` line number in this file is
   a **pre-phase-2** number: phase 2 inserts roughly 60 lines above `best_dev_eligible`, so
   `:572-589` and `:592` will have moved by about that much. The symbols and the quoted code are
   exact; the numbers are a hint.
3. **The swarm shares one worktree.** `git add <path>` stages what is on disk, so a commit of a
   shared file may legitimately carry another phase's work at other anchors. Keep it; never revert
   another phase's region, never `git add -A`.

---

## Implementation Steps

### Step 1: The threshold, the label, and the policy constant

**File:** `engine/src/seer_engine/lab/store.py:79-80`
**Change:** replace the two existing lines.

**Code:**

```python
# The owner's risk appetite on the dev window, on top of the five P7a D8 conditions.
#
# 0.95 -> 0.90 on 2026-10-07, on the owner's instruction in the session that produced
# LAB_LUCK_GATE_PLAN.md: "this 0.95 threshold is too high man. my risk appetite is 0.90".
# Decisions D1 records why this is the lever that moved and the other one is not.
#
# Measured on the committed lab at the time of the change, N = 110 dev trials:
#   at 0.95 nothing is eligible -- the deadlock, 110 trials and 0 promotions;
#   at 0.90 three candidates clear the whole gate once the owner's other change of the same day
#           lands (tuning.MAX_DRAWDOWN 0.15 -> 0.20, Decisions D6, phase 8): M0022-W-TV14 (0.912),
#           M0022-W-TV16 (0.916) and M0020-W-NOSTOP (0.913 at N=110, 19.3% drawdown);
#   three near misses stay out, each for its own reason: M0007-N20-RAW clears the new drawdown
#           bar at 19.6% but scores 0.898 re-evaluated at N=110; M0019-RAW20-S25 draws down 20.7%,
#           outside even the new bar; M0001-TV10 does not beat SPY TR.
#
# This is a loosening of a gate that exists to prevent self-deception, and it is the owner's
# call to make. What it is not is a drift: it is one number, cited, dated, measured, and undone
# by editing this line back to 0.95. Decisions D1b records the consequence it does not fix --
# at 0.90 the best candidate still sinks below the bar at N ~ 200, about four more Sera nights.
DSR_MIN = 0.90

# The luck label, as it is written into ``trials.failed``. Derived from DSR_MIN rather than
# retyped, so the label and the threshold can never disagree.
#
# ``trials`` is append-only: 110 recorded rows carry the OLD text "DSR >= 0.95". Recognising the
# luck label by ``label == DSR_LABEL`` therefore stops working the moment DSR_MIN moves, and a
# luck-only rejection would read as an owner failure and could never be reconsidered. Every
# reader must use ``is_luck_label`` instead, which matches the label's *shape* and so matches
# every threshold the lab has ever recorded.
LUCK_LABEL_PREFIX = "DSR >= "
DSR_LABEL = f"{LUCK_LABEL_PREFIX}{DSR_MIN:.2f}"


def is_luck_label(label: str) -> bool:
    """True for a luck-test failure label recorded under *any* threshold this lab has used.

    ``DSR_LABEL`` is the one written today; ``"DSR >= 0.95"`` is written on 110 recorded rows.
    Both are the same condition at different thresholds, and the five P7a D8 conditions are
    never of this shape, so the prefix is an exact discriminator.
    """
    return str(label).startswith(LUCK_LABEL_PREFIX)


# The N the luck test deflates by, resolved through ``npolicy.effective_n``. ONE constant: the
# only place in the lab where the multiple-testing count is decided, read at call time by
# ``gate`` below rather than frozen into a row at run time.
#
# **Shipped as "all-trials" deliberately, and NOT inherited from npolicy's own default.**
# Decisions D1: the owner moved the threshold, not N, so N stays at every dev trial -- 110 today,
# the same number ``runner.trial_rows`` used before this phase existed. The policy module, its
# correlation evidence (mean pairwise rho 0.595 across the 110 recorded curves, effective N 2.4,
# 23 distinct methods) and phase 5's read-only ``lab luck`` are all built, so the second lever
# is measured and ready -- it is simply not pulled. Pulling it as well would admit five
# candidates instead of two, including one at MAR 0.60, and would make it impossible to say
# afterwards which change did the work.
#
# Set explicitly, and always passed as an argument to ``npolicy.effective_n``, so that nobody has
# to reason about which module's default wins. ``test_the_shipped_defaults_reproduce_todays_n``
# holds it to 110.
DSR_POLICY = "all-trials"
```

**Impact:** the threshold moves. Nothing else yet reads `DSR_POLICY`. Callers of `DSR_LABEL`
continue to work (they *write* the label); the one caller that *compares* against it is fixed in
Step 7e.

---

### Step 2: The one new status edge

**File:** `engine/src/seer_engine/lab/store.py:62-73`
**Change:** add `("rejected", "dev-eligible")`. `connect()` already runs
`INSERT OR IGNORE INTO transitions (src, dst)` over `TRANSITIONS`, so the
`methods_status_forward` trigger starts admitting it on the next open of any database — which is
half of Step 10's migration.

**Code:**

```python
TRANSITIONS: tuple[tuple[str, str], ...] = (
    ("idea", "registered"),
    ("idea", "rejected"),  # dropped before running (duplicate, untestable for another reason)
    ("idea", "blocked-data"),
    ("registered", "rejected"),
    ("registered", "dev-eligible"),
    ("registered", "blocked-data"),
    ("blocked-data", "idea"),  # the missing data arrived
    # The one edge out of ``rejected`` (LAB_LUCK_GATE_PLAN.md Decisions D2). "Status moves
    # forward only" protects *verdicts from being erased*, and nothing here erases one: the
    # trials that decided the rejection stay in the append-only ``trials`` table, untouched, and
    # the re-evaluation is *appended* to the method's analysis. Admitted only by
    # ``reevaluate_method``, and only for a method whose recorded failure was the luck label
    # alone -- a method that failed max DD cannot take it. Without this edge R1 is unsatisfiable:
    # M0022 reads ``rejected`` today, and re-judging it under a new id would need a duplicate
    # configuration digest, which ``has_trial`` refuses outright.
    ("rejected", "dev-eligible"),
    ("dev-eligible", "promoted"),
    ("promoted", "test-passed"),
    ("promoted", "test-failed"),
    ("test-passed", "paper"),
)
```

**Impact:** `rejected -> dev-eligible` becomes possible at the database level; every other move out
of `rejected` is still refused.

---

### Step 3: The derived verdict

**File:** `engine/src/seer_engine/lab/store.py` — a new section immediately **after**
`best_dev_eligible` (ends at line 589) and **before** the `# ----- ideas_seen` divider.

**Code:**

```python
# --------------------------------------------------------------------------- the derived verdict


@dataclass(frozen=True)
class Gate:
    """The luck bar in force right now: the policy name and the N it resolved to.

    The threshold is not in here: it is ``DSR_MIN``, one module constant, and there is no policy
    over it.
    """

    n: int
    policy: str


@dataclass(frozen=True)
class Verdict:
    """One dev trial's eligibility as it reads *now*.

    ``failed`` is the ordered tuple of failure labels (``trials.failed`` is the same list,
    "; "-joined). ``derived`` is True when the luck label was re-decided here, False when the
    recorded columns were returned verbatim.
    """

    dsr: float | None
    failed: tuple[str, ...]
    eligible: bool
    n: int
    policy: str
    derived: bool


# Resolved gates, keyed by (database file, policy, the dev trial set's fingerprint).
#
# ``npolicy.effective_n`` decodes 110 month-end curves out of ``curve_json`` and takes an
# eigendecomposition of their correlation matrix for the participation ratio. ``lab status``
# calls ``best_dev_eligible`` once per method with dev trials -- 23 of them -- so without this
# the estimator would run 23 times for one command.
#
# The key is derived from the *content*, not from the connection: ``sqlite3.Connection`` supports
# neither weak references nor attributes, so there is nowhere on it to hang a cache and nothing
# safe to key on (``id()`` is reused after a connection is freed). ``trials`` is append-only --
# the ``trials_no_update`` and ``trials_no_delete`` triggers see to that -- so for one database
# file the triple (dev row count, highest dev trial number, distinct dev methods) pins the dev
# trial set exactly, and any insert changes it. That makes the cache self-invalidating.
#
# In-memory databases are never cached: their path is "" and two of them could otherwise collide
# on identical counts.
_GATE_CACHE: dict[tuple[str, str, int, int, int], Gate] = {}
_GATE_CACHE_MAX = 32


def _gate_key(conn: sqlite3.Connection, policy: str) -> tuple[str, str, int, int, int] | None:
    """A content-derived cache key, or None when this database must not be cached."""
    path = ""
    for _seq, name, file in conn.execute("PRAGMA database_list"):
        if name == "main":
            path = str(file or "")
            break
    if not path:
        return None  # ":memory:" and temporary databases
    count, high, methods = conn.execute(
        "SELECT count(*), coalesce(max(n), 0), count(DISTINCT method_id) "
        "FROM trials WHERE window = 'dev'"
    ).fetchone()
    return (path, policy, int(count), int(high), int(methods))


def gate(conn: sqlite3.Connection, policy: str | None = None) -> Gate:
    """The N the luck test deflates by on this database, under ``policy`` (default ``DSR_POLICY``).

    Memoised per (database file, policy, dev trial set) -- see ``_GATE_CACHE``. A caller judging
    many trials should still resolve it once and pass it down as ``verdict(..., at=g)`` or
    ``best_dev_eligible(..., at=g)``: that is explicit and does not depend on the cache being
    warm or on the key being right.

    The policy is always passed to ``npolicy.effective_n`` explicitly; this module never relies
    on that module's own default.

    ``npolicy`` is imported here rather than at module scope, the way ``snapshot`` imports its
    dependencies: importing ``store`` is something the whole lab does, and it should never pull
    in the estimator's curve arithmetic, nor create a cycle if ``npolicy`` ever needs ``store``.
    """
    from seer_engine.lab import npolicy

    name = DSR_POLICY if policy is None else policy
    key = _gate_key(conn, name)
    if key is not None:
        hit = _GATE_CACHE.get(key)
        if hit is not None:
            return hit
    count = npolicy.effective_n(conn, name)
    resolved = Gate(n=int(count.n), policy=str(count.policy))
    if key is not None:
        if len(_GATE_CACHE) >= _GATE_CACHE_MAX:
            _GATE_CACHE.clear()  # a long-lived process never accumulates stale paths
        _GATE_CACHE[key] = resolved
    return resolved


def pending_gate(
    conn: sqlite3.Connection, method_id: str, pending: int, *, policy: str | None = None
) -> Gate:
    """The gate a batch of ``pending`` new dev trials for ``method_id`` will be judged under.

    ``gate`` counts what the database holds, and the batch is not in it yet: the DSR and the
    eligibility have to be decided *before* ``insert_trials`` runs, because ``trials`` is
    append-only and a row is written exactly once. So the count is projected forward over the
    batch, in the unit the policy counts in:

    - ``all-trials``  N + ``pending``  -- every new row is another trial. Under the shipped
      policy this is exactly ``dev_trial_count(conn) + len(results)``, the expression
      ``runner.trial_rows`` used before this phase, so a new ``lab run`` is deflated by the
      number it has always been deflated by.
    - ``methods``     N + 1 when ``method_id`` has no dev trial yet, N otherwise -- a batch of
      variants of one method is one method. The participation-ratio floor is not re-measured
      against curves that do not exist yet; it is a floor, and this projection only ever sits
      on or above it.
    - ``effective``   N -- the measured independence of curves that have not been recorded
      cannot be projected, so the batch is judged under the independence already measured.
    - anything else   N + ``pending``, the most punishing of the three. A policy name this
      module does not recognise must not quietly deflate a new trial by less than the row count.

    Every branch returns at least ``gate(conn).n``, so a trial recorded today is never deflated
    by a smaller N than one recorded yesterday under the same policy.
    """
    g = gate(conn, policy)
    if pending <= 0:
        return g
    if g.policy == "effective":
        return g
    if g.policy == "methods":
        seen_already = conn.execute(
            "SELECT 1 FROM trials WHERE method_id = ? AND window = 'dev' LIMIT 1", (method_id,)
        ).fetchone()
        return g if seen_already is not None else Gate(n=g.n + 1, policy=g.policy)
    return Gate(n=g.n + pending, policy=g.policy)


# The one D8 condition with no number in it, and therefore the one recorded label that can never
# go stale: it asks whether a human hand-picked a parameter of the candidate, not whether a metric
# cleared a bar. ``owner_failures`` carries it from the recorded string instead of re-deriving it,
# because there is no column to re-derive it from.
#
# A literal rather than ``dev.FAILURE_LABELS[-1]``: ``store`` deliberately imports ``dev`` only
# inside the functions that need it (``snapshot``, :811 on ``main``), and a module-level constant
# would pull the whole backtest package into every ``import store``.
# ``test_the_owner_inputs_label_is_the_one_dev_still_writes`` pins the two together.
OWNER_INPUTS_LABEL = "owner inputs"


def recorded_labels(failed: str) -> tuple[str, ...]:
    """A recorded ``trials.failed`` string, split into its labels. **History, not a verdict.**

    Every label it returns names the threshold in force on the trial's **run date**: 110 recorded
    rows say ``"DSR >= 0.95"`` and ``"max DD <= 15%"``, and the live bars are 0.90 and 20%. Use
    this to display what the lab said at the time, or to ask whether a particular condition was
    recorded; never to decide what a trial is today. ``owner_failures`` is that.
    """
    return tuple(f for f in str(failed or "").split("; ") if f)


def owner_failures(trial: Mapping[str, Any] | sqlite3.Row) -> tuple[str, ...]:
    """The five P7a D8 conditions ``trial`` misses **as they read now**, in FAILURE_LABELS order.

    **Four re-derived, one carried.** Four of the five are thresholds over numbers ``trials``
    already records, so they are recomputed here from the recorded columns against the live
    constants -- the same comparisons ``dev.py:362-372`` makes, on the same values:

    - ``beats SPY TR``  ``total_return > spy_tr_return``
    - ``max DD``        ``max_drawdown <= tuning.MAX_DRAWDOWN`` (0.20 since 2026-10-07, phase 8)
    - ``PF``            ``profit_factor >= tuning.MIN_PROFIT_FACTOR``
    - ``trades``        ``trades >= dev._MIN_TRADES``

    The fifth, ``owner inputs``, is **carried from the recorded ``failed`` string**, because it is
    the one condition that is not a threshold: it asks whether a human hand-picked a parameter of
    the *candidate* (``dev.candidate_owner_inputs``), there is no column to recompute it from, and
    no constant re-decides it -- so its recorded label can never go stale.

    **Why nothing is parsed out of ``failed`` for the other four.** ``trials`` is append-only, so
    a recorded label names the bar in force on its run date. All 110 recorded rows carry
    ``"max DD <= 15%"``, and the owner moved that bar to 20% on 2026-10-07; reading the condition
    back out of the string would freeze every recorded trial at the bar it was judged by and
    ``M0020-W-NOSTOP`` (19.3%) could never become eligible. That is precisely the "verdicts mix
    bars" defect R2 names, and it is why this function takes the row rather than the string.

    The returned labels are the **live** ones (``dev.FAILURE_LABELS``), so a caller printing them
    states today's bar, not the one the row was judged by.
    """
    from seer_engine.backtest import dev, tuning

    spy, drawdown, pf, trades, owner = dev.FAILURE_LABELS
    total, bench = trial["total_return"], trial["spy_tr_return"]
    dd, factor, count = trial["max_drawdown"], trial["profit_factor"], trial["trades"]
    out: list[str] = []
    if total is None or bench is None or float(total) <= float(bench):
        out.append(spy)
    if dd is None or float(dd) > tuning.MAX_DRAWDOWN:
        out.append(drawdown)
    if factor is None or float(factor) < tuning.MIN_PROFIT_FACTOR:
        out.append(pf)
    if count is None or int(count) < dev._MIN_TRADES:
        out.append(trades)
    if owner in recorded_labels(trial["failed"]):
        out.append(owner)
    return tuple(out)


def sr_star(n_trials: int, var_trials: float) -> float:
    """The deflated Sharpe's daily hurdle ``SR*`` at ``n_trials`` independent looks.

    ``dev.deflated_sharpe``'s own ``sr_star`` line, with its own ``_EULER_GAMMA``, isolated so
    the hurdle can be asked for at an N no trial was ever run at. Nothing is re-derived: this is
    the formula being inverted, not a second opinion about it.
    """
    from statistics import NormalDist

    from seer_engine.backtest import dev

    normal = NormalDist()
    expected_max = (1 - dev._EULER_GAMMA) * normal.inv_cdf(1 - 1 / n_trials) + (
        dev._EULER_GAMMA * normal.inv_cdf(1 - 1 / (n_trials * math.e))
    )
    return math.sqrt(var_trials) * expected_max


def recover_dsr(
    *,
    sharpe_daily: float,
    dsr_at_run: float,
    n_at_run: int,
    var_trials: float,
    n_trials: int,
) -> float | None:
    """A recorded DSR re-evaluated at ``n_trials`` looks. Pure; reads and writes nothing.

    ``DSR = Phi((SR - SR*(N)) * k)`` where ``k = sqrt(t-1)/sqrt(radicand)`` does **not** depend on
    N. ``t``, the skew and the kurtosis are not in ``trials`` -- that is what ``trial_moments``
    exists to fix going forward -- so ``k`` is recovered by inverting a known DSR at the N it
    belongs to, and the answer is the same ``Phi`` with a different ``SR*``.

    **At ``n_trials == n_at_run`` this returns ``dsr_at_run`` exactly, for any ``var_trials``** --
    the two ``SR*`` terms are the same term and ``k`` cancels. That identity is what makes this a
    *re-reading* of the record rather than a second estimate of it.

    **Monotone in N** for any ``dsr_at_run`` above a half: ``SR*`` rises with N and ``k > 0``
    there, so the DSR falls as the search widens. That is R1's ratchet, as arithmetic.

    None where the inversion is undefined: fewer than two looks at either N, a non-positive
    ``var_trials``, a non-finite input, a DSR of exactly 0 or 1 (``Phi^-1`` has no value there),
    or an SR sitting exactly on the hurdle at ``n_at_run`` (``k`` would divide by zero -- the
    record says the trial was exactly at the bar and says nothing about its ``k``).
    """
    from statistics import NormalDist

    if n_trials < 2 or n_at_run < 2 or var_trials <= 0:
        return None
    if not all(math.isfinite(x) for x in (sharpe_daily, dsr_at_run, var_trials)):
        return None
    if not 0.0 < dsr_at_run < 1.0:
        return None
    gap = sharpe_daily - sr_star(n_at_run, var_trials)
    if gap == 0.0:
        return None
    normal = NormalDist()
    k = normal.inv_cdf(dsr_at_run) / gap
    return normal.cdf((sharpe_daily - sr_star(n_trials, var_trials)) * k)


def dev_sharpe_variance(conn: sqlite3.Connection) -> float | None:
    """The variance of the dev trials' daily Sharpes **as the lab stands now**. None below two.

    The same expression ``runner.trial_rows`` deflates by, so the dispersion the expected maximum
    is drawn from is the dispersion of the search as it actually is -- which is the point: the
    gate describes today on both axes, the count of looks and their spread.
    """
    import statistics

    sharpes = dev_daily_sharpes(conn)
    return statistics.variance(sharpes) if len(sharpes) >= 2 else None


def dsr_at(
    conn: sqlite3.Connection, trial: Mapping[str, Any] | sqlite3.Row, n_trials: int
) -> float | None:
    """``trial``'s deflated Sharpe **at ``n_trials`` looks**, or None when it cannot be had.

    Two routes to one number, in order of exactness:

    1. **From ``trial_moments``**, when ``lab run`` recorded them (phase 2) or ``lab remeasure``
       recovered them (phase 3). The same ``dev.deflated_sharpe`` on the trial's own measured
       ``sr_daily``, ``t``, ``skew`` and ``kurt``. An exact recomputation.

    2. **By inverting the recorded ``dsr``** at its own ``n_trials_at_run`` and re-evaluating at
       ``n_trials`` (``recover_dsr``). Exact arithmetic on recorded data -- no backtest is re-run
       and nothing is estimated -- and it returns the recorded number unchanged when the trial
       was already judged at ``n_trials``.

    **Both routes use ``dev_sharpe_variance(conn)`` -- the trial-Sharpe variance as the lab stands
    now -- and never the ``var_trials`` recorded beside the trial.** The function body reads that
    variance **once, before either route branches**, precisely so the two cannot drift apart
    again; ``moments["var_trials"]`` is not referenced anywhere in this function. That is
    deliberate (**Decision D12**) and it is
    the same principle as using the gate's N rather than ``n_trials_at_run``: the deflated Sharpe
    asks "how extreme is this Sharpe against the maximum of N draws from the trial-Sharpe
    distribution", and **both** N and that distribution describe the search as it is today.
    Pairing today's N with a variance frozen at the run date would mix bars on the other axis --
    exactly the defect R2 names, one column over. The recorded ``var_trials`` stays in
    ``trial_moments`` as history: it is what the trial *was* judged by, and phase 3's
    reproduction check is what it is for.

    **This is not a stylistic preference; it decides a candidate.** On the 54 P7a seed rows that
    phase 9 re-measures, the recorded ``var_trials`` (2.006691e-04, the P7a search's own) and
    today's (2.395048e-04, all 110 dev trials) differ by enough to move
    ``F9-SPY200M70-MOM30`` from **0.903053** (which clears 0.90) to **0.856651** (which does not).
    Under this function it reads **0.8567** and stays ineligible -- on a luck test it finally
    received rather than on a missing column, which is the whole of R6. Verified independently by
    phase 9: route 2 with ``dev_sharpe_variance`` reproduces this phase's own quoted
    ``M0007-N20-RAW`` figure of **0.8985** to four decimals, where the as-of-run variance gives
    0.8962 -- so every number this phase quotes was taken under this rule.

    Measured on the committed lab, the two routes agree to **1.3e-5** across all 56 trials with a
    recorded DSR, which is what makes route 2 a re-reading of the record rather than a second
    opinion about it. A trial recorded *today* reads back exactly as it was recorded, because the
    gate's N and today's variance are then the very values it was judged by.

    **None when the recorded ``dsr`` is NULL**, which is the 54 P7a seed rows by construction
    (``seed.py:136``: "P7a reported it for one row only"). A luck test that cannot be evaluated is
    a luck test that was not passed -- ``verdict`` appends the luck label, exactly as
    ``runner.trial_rows`` does for a new trial whose DSR comes back None. Nothing is admitted for
    being unmeasurable.
    """
    # ONE variance, read once, used by BOTH routes. `moments["var_trials"]` is deliberately not
    # read anywhere in this function: see Decision D12 and the docstring above.
    var = dev_sharpe_variance(conn)
    if var is None:
        return None
    moments = moments_of(conn, int(trial["n"]))
    if moments is not None:
        from seer_engine.backtest import dev

        return dev.deflated_sharpe(
            float(moments["sr_daily"]),
            n_trials,
            var,
            int(moments["t"]),
            float(moments["skew"]),
            float(moments["kurt"]),
        )
    if trial["dsr"] is None or trial["sharpe"] is None:
        return None
    from seer_engine.backtest.book_runner import TRADING_DAYS

    return recover_dsr(
        sharpe_daily=float(trial["sharpe"]) / math.sqrt(TRADING_DAYS),
        dsr_at_run=float(trial["dsr"]),
        n_at_run=int(trial["n_trials_at_run"]),
        var_trials=var,
        n_trials=n_trials,
    )


def verdict(
    conn: sqlite3.Connection,
    trial: Mapping[str, Any] | sqlite3.Row,
    *,
    at: Gate | None = None,
    policy: str | None = None,
) -> Verdict:
    """``trial``'s eligibility as it reads now: every condition, at the bars in force now.

    ``trial`` is a ``trials`` row (anything addressable by column name, including a
    ``sqlite3.Row``) carrying ``n``, ``dsr``, ``sharpe``, ``failed``, ``n_trials_at_run`` and the
    four metric columns. Meaningful for ``window = 'dev'`` rows: a test trial's DSR is recorded
    and is not a condition, because a pre-registered look has no selection among results to
    deflate.

    The recorded columns are the lab's history and are never written (design §1, plan invariant
    3). This is the *read*: what the same trial is judged as today, by the bars the lab holds
    today, rather than by the bars in force on its run date. That is R2's comparability, obtained
    without rewriting anything.

    **Nothing is ever returned verbatim.** Every one of the six conditions is decided here:

    - the four **threshold** owner conditions are re-derived from this row's recorded columns by
      ``owner_failures``, against the live ``tuning.MAX_DRAWDOWN`` / ``tuning.MIN_PROFIT_FACTOR``
      / ``dev._MIN_TRADES``, so a trial recorded under the old 15% drawdown bar reads against
      today's 20% one;
    - ``owner inputs`` is carried from the recorded string, because it is not a threshold and no
      constant re-decides it;
    - the **luck** test is decided on ``dsr_at(conn, trial, g.n)`` -- this trial's DSR **at the
      gate's current N**, never at the N it happened to be run under.

    **The luck test is always evaluated at the current N, and that is the whole of R2.** An
    earlier draft re-thresholded the recorded ``dsr`` only when ``n_trials_at_run`` already
    equalled the gate's N, and returned the row verbatim otherwise. That rule is **superseded and
    must not be implemented**: it would admit ``M0007-N20-RAW`` on a DSR of 0.9138 computed at
    N = 85 while judging ``M0022``'s variants on DSRs computed at N = 110 -- a candidate admitted
    for having been tried *earlier*, which is precisely the leaderboard-mixes-bars defect R2
    names and precisely the self-deception the lab exists to prevent. Re-evaluated at today's
    N = 110, ``M0007-N20-RAW`` is **0.8985** and does not clear 0.90.

    **A DSR that cannot be evaluated fails the luck test.** ``dsr_at`` returns None for the 54
    P7a seed rows, whose ``dsr`` is NULL by construction, and ``verdict`` then appends the luck
    label -- the same rule ``runner.trial_rows`` applies to a new trial
    (``if dsr is None or dsr < DSR_MIN``). Without it, ``F9-SPY200M70-MOM30`` (19.2% drawdown,
    MAR 0.64, no recorded DSR) would become eligible the moment the drawdown bar moved, on the
    strength of a luck test nobody ever ran. ``derived`` is False exactly in this case, and
    ``dsr`` is None with it.

    ``at`` resolves the gate once for a caller judging many trials. ``policy`` names a different
    policy for a read-only comparison (phase 5's ``lab luck``); the write paths never pass it.
    """
    g = gate(conn, policy) if at is None else at
    dsr = dsr_at(conn, trial, g.n)
    # Four re-derived from this row's columns against the live constants, one (`owner inputs`)
    # carried from the recorded string. Never parsed out of `failed` -- that string names the
    # bars in force on the run date, which are not today's.
    failed = owner_failures(trial)
    # The same rule runner.trial_rows applies to a new trial: a DSR that is None is a luck test
    # that was not passed. Nothing is admitted for being unmeasurable.
    if dsr is None or dsr < DSR_MIN:
        failed = failed + (DSR_LABEL,)
    return Verdict(
        dsr=dsr, failed=failed, eligible=not failed, n=g.n, policy=g.policy,
        derived=dsr is not None,
    )
```

**Impact:** new API only; still nothing calls it.

---

### Step 4: `reevaluate_method` — the only write path that reconsiders a verdict

**File:** `engine/src/seer_engine/lab/store.py` — appended to the section Step 3 created.

**Code:**

```python
# The first words of the analysis section ``reevaluate_method`` appends. Not an idempotence key:
# the edge it guards can be taken at most once, because it leads out of the only status it may
# be taken from.
REEVALUATION_MARKER = "Re-evaluated under the "


@dataclass(frozen=True)
class Reevaluation:
    """What ``reevaluate_method`` found, and whether it moved the method."""

    method_id: str
    status_before: str
    status_after: str
    moved: bool
    gate: Gate
    unblocked: tuple[str, ...]  # candidate ids now eligible that the recorded column rejects
    derived: int                # dev trials whose DSR was evaluated at the gate's N
    unjudgeable: int            # dev trials with no evaluable DSR -- they fail the luck test
    dev_trials: int


def _blocking(trial: Mapping[str, Any] | sqlite3.Row) -> tuple[str, ...]:
    """The second, independent no: why this trial may **not** take the ``rejected`` edge.

    ``owner_failures`` derives the same four conditions and ``verdict`` reads it, so these
    comparisons are written here a second time **on purpose**. Two owner-set bars moved in this
    plan set -- the luck threshold (phase 4) and the drawdown threshold (phase 8) -- and a gate
    that loosens on two axes at once should not be able to promote a method through a single
    expression. A future change to ``owner_failures`` has to get past this too.

    Phrased as sentences with the numbers in them, because this text goes into the refusal a
    human reads.
    """
    from seer_engine.backtest import dev, tuning

    out: list[str] = []
    total, bench = trial["total_return"], trial["spy_tr_return"]
    if total is None or bench is None or float(total) <= float(bench):
        out.append(f"total return {total!r} does not beat SPY TR {bench!r}")
    dd = trial["max_drawdown"]
    if dd is None or float(dd) > tuning.MAX_DRAWDOWN:
        out.append(f"max drawdown {dd!r} is outside the {tuning.MAX_DRAWDOWN:.0%} bar")
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
    return tuple(out)


def reevaluate_method(conn: sqlite3.Connection, method_id: str) -> Reevaluation:
    """Re-judge one method's dev trials under ``DSR_MIN`` and ``DSR_POLICY`` and, if that
    unblocks it, move it ``rejected -> dev-eligible``.

    **This is the only write path in the lab that reconsiders a verdict, and it is deliberately
    narrow.** It may take exactly one edge, from exactly one status, for exactly one reason:

    - the method must read ``rejected`` now. Any other status is left alone and ``moved`` is
      False; there is no other edge into ``dev-eligible`` from here, so a method already moved
      is not moved twice.
    - at least one of its dev trials must be eligible under the derived verdict and not already
      recorded eligible.
    - **every trial it relies on must clear all five conditions on a second, independently
      written check.** ``verdict`` already derives them; ``_blocking`` below repeats the four
      comparisons against the same live constants in its own code, and refuses outright if the
      recorded ``failed`` carries ``OWNER_INPUTS_LABEL``. The repetition is the point: **two
      owner-set bars moved in this set** (the luck threshold here, the drawdown threshold in
      phase 8), and a gate that loosens on two axes at once is worth two noes written in two
      places. A trial that reads derived-eligible but does not clear this check is a
      contradiction inside this module, and it raises ``LabError`` rather than promoting quietly.

      Note what this check is **not**: it is not "the recorded failure was the luck label alone".
      That was the earlier draft's rule, and it is wrong now -- ``M0020-W-NOSTOP``'s recorded
      failure is ``"max DD <= 15%; DSR >= 0.95"`` and it *should* become eligible, because the
      owner moved both of those bars. The rule is about the numbers, not about the string.

    Nothing in ``trials`` is written: no row is inserted, updated or deleted, so the lab's N does
    not move and ``test_looks`` is untouched. What is written is one dated section appended to
    ``analysis`` (append-only by trigger, the shape ``record_promotion`` uses) naming the
    threshold, the policy, the N and the date that re-judged it, and the ``status`` column. Both
    happen in the caller's transaction, so a crash leaves neither.

    Neither the threshold nor the policy is a parameter. A write path that could unblock a method
    under any bar on request would make both constants decorative; the read-only comparison
    across policies is phase 5's ``lab luck``.

    The caller holds the transaction (``begin_immediate`` / ``with conn``), as every other
    writer in this module does.
    """
    from seer_engine.backtest import tuning  # for the drawdown bar named in the analysis text

    row = get_method(conn, method_id)
    if row is None:
        raise LabError(f"no method {method_id}")
    status = str(row["status"])
    trials = conn.execute(
        "SELECT * FROM trials WHERE method_id = ? AND window = 'dev' ORDER BY n", (method_id,)
    ).fetchall()
    g = gate(conn)
    unblocked: list[str] = []
    verdicts: dict[str, Verdict] = {}
    derived = 0
    for t in trials:
        v = verdict(conn, t, at=g)
        derived += 1 if v.derived else 0
        if not v.eligible:
            continue
        blocking = _blocking(t)
        if blocking:
            raise LabError(
                f"{t['candidate_id']} reads eligible at {DSR_LABEL} under the {g.policy} policy "
                f"(N={g.n}), but a second, independent check of its recorded numbers says "
                f"otherwise: {'; '.join(blocking)}. Refusing to move {method_id} -- a method may "
                f"only cross this edge when every one of the five conditions clears the bar in "
                f"force today."
            )
        if not bool(t["eligible"]):
            unblocked.append(str(t["candidate_id"]))
            verdicts[str(t["candidate_id"])] = v
    found = Reevaluation(
        method_id=method_id,
        status_before=status,
        status_after=status,
        moved=False,
        gate=g,
        unblocked=tuple(unblocked),
        derived=derived,
        unjudgeable=len(trials) - derived,
        dev_trials=len(trials),
    )
    if status != "rejected" or not unblocked:
        return found

    lines = [
        "# Re-evaluation",
        "",
        f"{REEVALUATION_MARKER}`{g.policy}` N policy at N = {g.n}, against `{DSR_LABEL}` and "
        f"a max drawdown bar of {tuning.MAX_DRAWDOWN:.0%} (both the owner's risk appetite, set "
        f"2026-10-07; LAB_LUCK_GATE_PLAN.md Decisions D1 and D6).",
        "",
        "Every condition was re-read against the bars in force today: the four threshold "
        "conditions from this method's own recorded columns, and the luck test from the same "
        "deflated Sharpe at the same N. No recorded column changed: `trials` is append-only, and "
        "every `dsr`, `eligible`, `failed` and `n_trials_at_run` this method recorded still reads "
        "exactly as it did -- including the `DSR >= 0.95` and `max DD <= 15%` labels that "
        "rejected it, which name the bars of their own day.",
        "",
        f"The {'variant' if len(unblocked) == 1 else 'variants'} this unblocks:",
        "",
    ]
    for cid in unblocked:
        v = verdicts[cid]
        shown = "None" if v.dsr is None else f"{v.dsr:.4f}"
        lines.append(f"- `{cid}`: DSR {shown} at N = {g.n}, against {DSR_LABEL}.")
    lines += [
        "",
        "The *set* of five P7a D8 conditions did not change, and `owner inputs` -- the one that "
        "is a property of the candidate rather than of a number -- was carried from the record "
        "untouched. Status moves `rejected` -> `dev-eligible`.",
    ]
    append_analysis(conn, method_id, "\n".join(lines))
    update_method(conn, method_id, status="dev-eligible")
    return Reevaluation(
        method_id=method_id,
        status_before=status,
        status_after="dev-eligible",
        moved=True,
        gate=g,
        unblocked=tuple(unblocked),
        derived=derived,
        unjudgeable=len(trials) - derived,
        dev_trials=len(trials),
    )


def reevaluate(
    conn: sqlite3.Connection, method_ids: Sequence[str] | None = None
) -> list[Reevaluation]:
    """``reevaluate_method`` over ``method_ids``, or over every ``rejected`` method when None.

    The caller holds the transaction, so the whole sweep is one atomic unit: either every method
    it unblocks moves, or none does.
    """
    if method_ids is None:
        method_ids = [
            str(r[0])
            for r in conn.execute("SELECT id FROM methods WHERE status = 'rejected' ORDER BY id")
        ]
    return [reevaluate_method(conn, m) for m in method_ids]
```

**Impact:** `rejected -> dev-eligible` becomes reachable, under two independent guards.
`Sequence`, `Mapping`, `Any` and `dataclass` are all already imported (`store.py:35-41`).

---

### Step 5: `best_dev_eligible` reads the derived verdict

**File:** `engine/src/seer_engine/lab/store.py:572-589`
**Change:** replace the whole function. Every clause of the contract is preserved — highest MAR,
tie on the trial number, `window='dev'` only, `mar IS NOT NULL`, exactly one row.

**Code:**

```python
def best_dev_eligible(
    conn: sqlite3.Connection,
    method_id: str,
    *,
    at: Gate | None = None,
    policy: str | None = None,
) -> sqlite3.Row | None:
    """The method's best eligible dev trial by MAR -- the one variant design §3 pre-registers.

    Highest MAR wins and a tie breaks on the trial number, so the answer is exactly one row and
    the same row every time: "one per method" is a property of this query, not of the caller.

    Only ``window = 'dev'`` is considered. A test trial is the out-of-sample check on a
    configuration this query already chose, so letting one back in here would let a test number
    decide what gets tested. A trial with no MAR is never the answer either -- an eligible trial
    always has one, because ``beats SPY TR`` is among the conditions it passed, so a NULL here
    means a row that cannot be compared rather than a row that compares badly.

    **Eligible means ``verdict(...).eligible``, not the frozen ``eligible`` column.** The verdict
    is read under one threshold and one N at evaluation time (plan Decisions D1/D2), so two
    trials recorded six weeks apart are ranked against the same bar instead of against whichever
    bar happened to be in force on each run date. Nothing else about the choice changed: the
    ordering is still MAR then ``n``. Selection is still **never** on DSR -- a higher-DSR variant
    does not outrank a higher-MAR one, which is why ``M0022-W-TV14`` (MAR 0.857, DSR 0.912) is
    the answer for M0022 and ``M0022-W-TV16`` (MAR 0.816, DSR 0.916) is not.

    The gate is resolved once, after the rows are fetched, so a method with no comparable dev
    trial costs no estimator read at all.

    ``at`` passes in an already-resolved gate. A caller looping over many methods -- ``lab
    status`` walks all 23 with dev trials -- should resolve ``gate(conn)`` once and pass it to
    every call, so the estimator provably runs once rather than relying on ``_GATE_CACHE``.
    ``policy`` is for phase 5's read-only comparison; the promotion path passes neither.

    None when the method has no eligible dev trial at all.
    """
    rows = conn.execute(
        "SELECT * FROM trials WHERE method_id = ? AND window = 'dev' AND mar IS NOT NULL "
        "ORDER BY mar DESC, n ASC",
        (method_id,),
    ).fetchall()
    if not rows:
        return None
    g = gate(conn, policy) if at is None else at
    for row in rows:
        if verdict(conn, row, at=g).eligible:
            return row
    return None
```

**Impact:** `prereg.promote_method` (`lab/prereg.py:472`) now pre-registers the best variant under
the current bar. Its call site needs no edit. See **Handoffs #2** for the one consequence phase 7
must close.

---

### Step 6a: New trials are judged under the same gate

**File:** `engine/src/seer_engine/lab/runner.py:160-215` (`trial_rows`)

**The exact delta** — the only lines phase 4 owns in `runner.py`:

```python
# old
    n_trials = store.dev_trial_count(conn) + len(results)

# new
    gate = store.pending_gate(conn, method.id, len(results))
    n_trials = gate.n
```

Under the shipped `DSR_POLICY = "all-trials"` these are the **same number**: `pending_gate`
returns `effective_n(conn, "all-trials").n + pending`, and phase 1's `all-trials` policy is
`dev_trial_count`. A test pins that equality, so this step changes no behavior today and changes
the right behavior the day the policy is changed.

**The function in full, as it reads after phase 2 and this phase.** Reconciled: the body below is
**phase 2's**, quoted verbatim from phase 2 Step 7c, with only this phase's two lines substituted.
Phase 2 builds the `store.MomentsRow` **inline** (there is no `_moments_row` helper in `runner.py`),
computes the DSR with a direct `dev.deflated_sharpe` call rather than through `_dsr`, binds the
metrics to `met` because `m` is the moments tuple, and zips `strict=True`. An earlier draft of this
step quoted a pre-phase-2 body and called a helper phase 2 does not define; that draft is
superseded. **Apply the two-line delta and the docstring, and nothing else:**

```python
def trial_rows(
    conn: sqlite3.Connection,
    method: Method,
    results: list[tuple[DevRow, Any]],
    *,
    fingerprint: str,
    git_sha: str,
) -> list[Ran]:
    """The trial rows for one method's dev results (``results``: (row, month-end curve)).

    The luck test's N is ``store.pending_gate(conn, method.id, len(results)).n`` -- the N the
    lab's ``store.DSR_POLICY`` resolves to, projected over this batch, which is the same N
    ``store.verdict`` re-reads these trials under. A trial run tonight and one recorded six weeks
    ago are therefore judged by one bar, which is R2.

    Under the shipped ``all-trials`` policy this is ``dev_trial_count(conn) + len(results)``,
    exactly the expression this function used before the policy existed.

    ``n_trials_at_run`` records **the N the DSR was computed at**, which is what it has always
    meant (``lab promote`` prints it as "DSR ... at N = ..."). The raw dev row count is always
    ``store.dev_trial_count``.

    The variance is still the sample variance of the daily Sharpe across every recorded dev trial
    plus this batch: only the *count* of looks is policy-dependent, not the dispersion the
    expected maximum is drawn from. The threshold the DSR is compared against is
    ``store.DSR_MIN`` -- 0.90 since 2026-10-07.

    **The verdict is not changed by the moments bookkeeping** (phase 2): ``daily_moments`` is
    evaluated once per variant and reused, which is a pure function of the variant's daily
    returns, so hoisting it cannot move a number.
    """
    prior = store.dev_daily_sharpes(conn)
    moments = [daily_moments(r.stats.daily_returns) for r, _ in results]
    new_sharpes = [m[0] for m in moments if m is not None]
    all_sharpes = prior + new_sharpes
    gate = store.pending_gate(conn, method.id, len(results))   # <- phase 4's two lines
    n_trials = gate.n                                          # <- (was: dev_trial_count + len)
    var_trials = statistics.variance(all_sharpes) if len(all_sharpes) >= 2 else None
    run_at = store.now_iso()
    out: list[Ran] = []
    for (row, curve), m in zip(results, moments, strict=True):
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
        out.append(Ran(trial=trial, row=row, moments=mom))
    return out
```

> **Ownership, settled.** Phase 2 owns every line of this body except the two marked above;
> phase 4 owns those two and the docstring. `n_at_run=n_trials` inside the `MomentsRow` is phase
> 2's line and stays correct unchanged — `n_trials` is now the gate's projected N, which is
> exactly the N the DSR beside it was computed at. `runner._dsr` keeps its one remaining caller,
> `run_test`; this phase does not revive it here.

**Impact:** `run_method` already derives the method's status from `any(r.trial.eligible ...)`, so a
fresh `lab run` lands on `dev-eligible` under the current bar with no re-evaluation needed.

---

### Step 6b: The docstrings that now say something false

**File:** `engine/src/seer_engine/lab/runner.py:7-10` — steps 3 and 4 of the `lab run` summary:

```python
3. Deflated Sharpe per trial with N resolved by ``store.DSR_POLICY`` through
   ``store.pending_gate`` -- shipped as ``all-trials``, so N = every dev trial in the lab, this
   batch included -- and the variance of the daily Sharpe across those trials.
4. Eligible = the five P7a D8 conditions and ``store.DSR_LABEL`` (DSR >= 0.90 since 2026-10-07;
   LAB_LUCK_GATE_PLAN.md Decisions D1). Insert the trials, set the method's ``source_sha`` and
   status (``dev-eligible`` when any trial is eligible, else ``rejected``), all in one
   transaction. ``store.verdict`` re-reads a recorded trial against the same threshold and N, so
   a verdict is comparable across time rather than frozen at its run date.
```

**File:** `engine/src/seer_engine/lab/runner.py:23-30` — append to the "**The look does not move
the lab's N**" paragraph, whose claim is unchanged (a test trial is still excluded from both
`dev_trial_count` and `dev_daily_sharpes`):

```python
Since LAB_LUCK_GATE_PLAN.md phase 4, *what* N counts is ``store.DSR_POLICY``'s business and need
not be a row count at all; *which* trials it counts over is still dev trials only, and that is
what this paragraph is about.
```

**File:** `engine/src/seer_engine/lab/store.py:1-27` — module docstring. Add after the `trials`
bullet:

```python
- ``trial_moments``: the DSR's inputs for one dev trial (phase 2), so a verdict can be recomputed
  later. ``store.verdict`` reads it; nothing re-decides a recorded column.
```

and replace the schema-versions paragraph with:

```python
Schema versions (``meta.schema_version``): 1 is the first lab; 2 adds the ``synthesis`` insight
kind; 3 adds ``trial_moments``. ``connect`` migrates an older database in place;
``connect_readonly`` never does.

The **verdict** a trial reads is derived, not frozen: ``DSR_MIN`` is the threshold (0.90 since
2026-10-07) and ``DSR_POLICY`` names the multiple-testing N (``all-trials`` today, so N is every
dev trial, as it has always been). ``verdict`` re-decides the luck label at call time and carries
the five owner conditions through untouched. Recorded rows keep the label of the threshold they
were judged under, so every reader uses ``is_luck_label`` rather than comparing to ``DSR_LABEL``.
```

**Impact:** documentation only.

---

### Step 7: `lab reevaluate`, and the one `misses()` fix

**File:** `engine/src/seer_engine/commands/lab.py`

**(a) the handler** — insert immediately after `_promote` (ends at line 340):

```python
def _reevaluate(conn, args) -> int:
    """`lab reevaluate [M0022 ...]`: re-judge recorded dev trials against the current luck bar
    and move anything the luck label alone was blocking to dev-eligible.

    No research store is loaded, no backtest runs, no trial row is inserted: this reads the dev
    trials the lab already has, re-decides the luck label for each, and takes at most the one
    edge `rejected -> dev-eligible`. The test window is not touched and the look count it prints
    is the one it found.

    Every trial with a recorded DSR is re-judged **at the gate's current N**, either exactly from
    `trial_moments` or by re-evaluating the recorded DSR there (`store.dsr_at`). A trial whose
    DSR cannot be evaluated at all -- the 54 P7a seed rows, whose `dsr` is NULL by construction --
    fails the luck test, exactly as a new trial with no computable DSR does, and is counted and
    named per method rather than passed over in silence.

    Neither the threshold nor the policy is a flag: the write path always uses `store.DSR_MIN`
    and `store.DSR_POLICY`, so the gate cannot be loosened per invocation. To see what another
    policy would say without changing anything, use the read-only `lab luck` (phase 5).

    The pairing is deliberate and the names are deliberately not neighbours: **`lab reevaluate`
    writes** (it can move a method across `rejected -> dev-eligible`) and **`lab luck` reads**
    (it prints the gate's state and its sensitivity to N, and touches nothing).

    Like every other `lab` subcommand, the global `--dry-run` is ignored. The whole sweep is one
    transaction: either every method it unblocks moves, or none does.
    """
    store.begin_immediate(conn)
    with conn:
        results = store.reevaluate(conn, args.method or None)
    if not results:
        print("nothing to re-evaluate: no method reads rejected")
        return 0
    g = results[0].gate
    print(f"luck bar: {store.DSR_LABEL}   N policy: {g.policy}, N = {g.n}   "
          f"({store.dev_trial_count(conn)} dev trial rows on the books)")
    print()
    moved = 0
    for r in results:
        if r.moved:
            moved += 1
            print(f"  {r.method_id}: {r.status_before} -> {r.status_after}  "
                  f"({', '.join(r.unblocked)})")
        elif r.dev_trials == 0:
            print(f"  {r.method_id}: no dev trial (dropped before running); unchanged")
        elif r.derived == 0:
            print(f"  {r.method_id}: none of its {r.dev_trials} dev trial(s) has an evaluable "
                  f"DSR (the P7a seed recorded none), so each fails the luck test and the "
                  f"verdict is unchanged ({r.status_before})")
        else:
            extra = (
                "" if r.unjudgeable == 0
                else f" ({r.unjudgeable} have no recorded DSR and so fail the luck test)"
            )
            print(f"  {r.method_id}: re-judged {r.derived} of {r.dev_trials} dev trial(s) at "
                  f"N = {r.gate.n} against {store.DSR_LABEL}{extra}; still {r.status_before}")
    print()
    print(f"{moved} method(s) moved rejected -> dev-eligible; "
          f"test-window looks used: {store.test_looks(conn)}")
    if moved:
        # `export-json`, not `stage`: `lab stage` also `git add`s, and the swarm shares one
        # worktree, so this phase stages its own path allowlist by hand (Decision D10).
        print("Re-export the web snapshot with "
              "`python -m seer_engine lab export-json`, and commit it with lab/lab.sqlite.")
    return 0
```

**(b) the subparser** — in `add_arguments`, after the `promote` block (`commands/lab.py:90-99`):

```python
    s = sub.add_parser(
        "reevaluate",
        help="re-judge recorded dev trials against the current luck bar; moves a method "
             "rejected -> dev-eligible when the luck label alone was the rejection",
    )
    s.add_argument(
        "method", nargs="*", metavar="M0022",
        help="methods to re-evaluate (default: every method that reads rejected)",
    )
```

**(c) `_HANDLERS`** (`commands/lab.py:621-638`) — **insert one line** after `"promote": _promote,`.
Do not rewrite the dict: phase 3 inserts `"remeasure"` after `"test"` and phase 5 inserts `"luck"`
after `"status"` into the same literal, and a whole-dict replacement deletes their keys silently.

```python
    "reevaluate": _reevaluate,
```

so that this phase's part of it reads

```python
    "promote": _promote,
    "reevaluate": _reevaluate,
    "test": _test,
```

**(d) the module docstring**, after the `lab promote` block (`commands/lab.py:10-12`):

```python
    lab reevaluate [M0022 ...]      re-judge recorded dev trials against the current luck bar
                                    (store.DSR_MIN, store.DSR_POLICY) and move a method whose
                                    only recorded failure was the luck label from rejected to
                                    dev-eligible. Reads only: no store, no backtest, no trial
                                    row, no look. A trial recorded at another N that has never
                                    been through `lab remeasure` keeps its recorded verdict and
                                    is reported as such
```

**(e) the one-line `misses()` fix** — `commands/lab.py:204-206`. **Required**, not a cleanup, and
for two reasons now. The existing code filters by equality with `store.DSR_LABEL`, which after this
phase is `"DSR >= 0.90"` while all 110 recorded rows say `"DSR >= 0.95"` — so every recorded luck
failure would count as a missed *owner* condition. And it reads the conditions out of the recorded
string at all, which after phase 8 freezes every row at the old 15% drawdown bar: `M0020-W-NOSTOP`
would show `misses 1: max DD <= 15%` forever despite being inside the 20% bar the owner set.

```python
# old
    def misses(r) -> list[str]:
        return [f for f in r["failed"].split("; ") if f and f != store.DSR_LABEL]

# new
    def misses(r) -> list[str]:
        # The row, not its `failed` string. `trials` is append-only, so that string names the
        # bars in force on the run date -- "DSR >= 0.95", "max DD <= 15%" -- and both have since
        # moved. `store.owner_failures` re-derives the four threshold conditions from this row's
        # recorded columns against the bars in force now, and carries `owner inputs`.
        return list(store.owner_failures(r))
```

The call sites in the loop below it are unchanged: they already pass `r`.

**Impact:** one new subcommand, one corrected filter. **Collision note for phase 5:** phase 5
rewrites `_status` and adds the read-only `lab luck`; this phase adds the write-path
`lab reevaluate` and touches `_status` only at that one `misses()` helper. See **Handoffs #3**.

---

### Step 8: Fix the one existing test this phase invalidates

**File:** `engine/tests/test_lab_store.py:85-93`
**Change:** `test_status_only_moves_forward` proves forward-only by asserting that
`rejected -> dev-eligible` raises. That edge now exists.

**Code:** replace

```python
def test_status_only_moves_forward(conn):
    _method(conn)
    with conn:
        store.update_method(conn, "M0001", status="registered")
        store.update_method(conn, "M0001", status="rejected")
    with pytest.raises(store.LabError, match="forward"):
        store.update_method(conn, "M0001", status="dev-eligible")
    with pytest.raises(store.LabError, match="forward"):
        store.update_method(conn, "M0001", status="idea")
```

with

```python
def test_status_only_moves_forward(conn):
    # `rejected -> dev-eligible` is the one edge out of `rejected` (LAB_LUCK_GATE_PLAN.md
    # Decisions D2) and is exercised in test_lab_gate_policy.py, where the Python guard that
    # admits it lives. Every other move out of `rejected` is still refused, which is what this
    # test is about.
    _method(conn)
    with conn:
        store.update_method(conn, "M0001", status="registered")
        store.update_method(conn, "M0001", status="rejected")
    with pytest.raises(store.LabError, match="forward"):
        store.update_method(conn, "M0001", status="promoted")
    with pytest.raises(store.LabError, match="forward"):
        store.update_method(conn, "M0001", status="paper")
    with pytest.raises(store.LabError, match="forward"):
        store.update_method(conn, "M0001", status="idea")
```

**Impact:** the existing suite stays green. No other existing test hard-codes the gate in a way
this breaks: `test_lab_prereg.py:395` and `test_lab_runner.py:64-65` compare against
`store.DSR_LABEL` / `store.DSR_MIN` and follow the constants, and `test_lab_snapshot.py`'s `LABELS`
set and its fixture rows both use the string literal `"DSR >= 0.95"`, so they stay consistent with
each other. **Run the full suite and confirm.**

---

### Step 9: The tests that are the phase's exit criteria

**File:** `engine/tests/test_lab_gate_policy.py` (new)

```python
"""The luck gate: one threshold, one N policy, read at evaluation time (plan phase 4).

Nothing here runs a backtest, loads a research store, or writes ``lab/lab.sqlite``: the committed
database is copied into ``tmp_path`` before anything opens it for writing, and the tests that need
DSR inputs construct ``trial_moments`` rows directly, because the backfill that measures them is
``lab remeasure`` (phase 3).

The claims this module exists to hold:

1. the shipped defaults -- DSR_MIN 0.90, DSR_POLICY "all-trials" -- resolve to N = 110 on the
   committed lab, which is today's N, so only the threshold moved;
2. at (110, 0.90, max DD 20%) exactly **three** candidates become eligible -- M0022-W-TV14,
   M0022-W-TV16 and M0020-W-NOSTOP -- and ``best_dev_eligible`` returns W-TV14 for M0022 because
   MAR decides; M0007-N20-RAW does NOT, on 0.8985 re-evaluated at N=110;
3. nothing that fails a non-luck condition becomes eligible at any (policy, threshold)
   combination -- in particular the four candidates whose recorded DSR is already >= 0.90;
4. M0011 stays ineligible, so RM-FR stays lab-rejected while RMW-FR becomes lab-eligible;
5. every recorded dsr / eligible / failed / n_trials_at_run on all 110 rows is byte-identical
   before and after this phase, and ``test_looks`` is still 0;
6. (all-trials, 0.95) together reproduce today's verdicts exactly -- the proof that only the
   threshold moved;
7. a recorded ``failed`` of "DSR >= 0.95" reads as ZERO owner misses under DSR_MIN 0.90 and is
   re-judged on the luck test alone -- the proof that the gate change reaches the recorded rows
   rather than tripping over its own label;
8. ``Verdict.failed`` is a tuple of label strings, and the gate's estimator runs once per dev
   trial set rather than once per method.
"""

from __future__ import annotations

import hashlib
import math
import shutil
import sqlite3
import statistics
from statistics import NormalDist

import pytest

from seer_engine.backtest.dev import deflated_sharpe
from seer_engine.lab import npolicy, store

_EULER_GAMMA = 0.5772156649015329


# --------------------------------------------------------------------------- fixtures


@pytest.fixture(autouse=True)
def _clean_gate_cache():
    """``gate`` memoises on (database file, policy, dev trial set). ``tmp_path`` differs per test
    so entries cannot collide, but a monkeypatched policy or threshold should never be served a
    gate resolved under another one -- clear it at both ends and the question does not arise."""
    store._GATE_CACHE.clear()
    yield
    store._GATE_CACHE.clear()


@pytest.fixture()
def conn(tmp_path):
    c = store.connect(tmp_path / "lab.sqlite")
    yield c
    c.close()


def _method(conn, mid="M0001", status="idea"):
    with conn:
        store.add_method(conn, id=mid, name="n", family="f", source_kind="knowledge",
                         hypothesis="h", status=status)


def _trial(**kw) -> store.TrialRow:
    base = dict(
        method_id="M0001", candidate_id="M0001-A", config_digest="d1", config_text="t",
        rules_id="r", allocator_id="a", window="dev", start="2000-01-03", end="2015-10-16",
        store_fingerprint="fp", git_sha="abc", run_at="2026-10-07T00:00:00+00:00",
        total_return=1.0, cagr=0.1, max_drawdown=0.12, profit_factor=1.5, trades=200,
        sharpe=0.94, exposure=0.9, turnover=1.0, worst_year=2008, worst_year_return=-0.2,
        spy_tr_return=0.5, spy_tr_cagr=0.07, mar=0.8, failed="DSR >= 0.95", eligible=False,
        dsr=0.91, n_trials_at_run=1, curve_json="[]",
    )
    base.update(kw)
    return store.TrialRow(**base)


def _moments(conn, trial_n, *, sr_daily, t, skew=0.0, kurt=3.0, var_trials, n_at_run,
             measured="reconstruction"):
    """Write one ``trial_moments`` row by raw SQL.

    Deliberately not through ``store.insert_moments``: that writer is phase 2's, and this phase
    depends only on the *column names*, so these tests stay green across any change to its
    keyword signature.

    ``measured`` defaults to the literal ``"reconstruction"`` rather than a timestamp, and that is
    the visible mark that these rows were fitted here rather than measured by ``lab run`` or
    recovered by ``lab remeasure`` (phase 3). It is a ``TEXT NOT NULL`` column with a
    ``length(trim(...)) > 0`` check, so it is a string, not a number.

    **``var_trials`` here is history, not a dial.** ``store.dsr_at`` deflates by
    ``store.dev_sharpe_variance(conn)`` on both routes (Decision D12) and never reads this
    column, so passing a different number here does **not** change any DSR these tests observe.
    A fixture that needs a particular hurdle sets the *spread of ``trials.sharpe``*, which is what
    ``dev_sharpe_variance`` is computed from. The column is still written because phase 2's schema
    requires it and because it is the number the trial was judged by.
    """
    conn.execute(
        "INSERT INTO trial_moments (trial_n, sr_daily, t, skew, kurt, var_trials, n_at_run, "
        "measured) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (int(trial_n), float(sr_daily), int(t), float(skew), float(kurt),
         None if var_trials is None else float(var_trials), int(n_at_run), str(measured)),
    )


# --------------------------------------------------------------------------- the constants


def test_the_luck_label_follows_the_threshold_and_still_recognises_the_old_one():
    assert store.DSR_MIN == 0.90
    assert store.DSR_LABEL == "DSR >= 0.90"
    assert store.is_luck_label(store.DSR_LABEL)
    assert store.is_luck_label("DSR >= 0.95")   # the label on all 110 recorded rows
    for owner in ("beats SPY TR", "max DD <= 15%", "max DD <= 20%", "PF >= 1.3",
                  ">= 100 trades", "owner inputs"):
        assert not store.is_luck_label(owner)
    assert store.recorded_labels("max DD <= 15%; DSR >= 0.95") == (
        "max DD <= 15%", "DSR >= 0.95")
    assert store.recorded_labels("") == ()


def test_the_owner_inputs_label_is_the_one_dev_still_writes():
    """``OWNER_INPUTS_LABEL`` is a literal in ``store`` so that importing it does not pull in the
    backtest package. This is the pin that keeps the literal equal to the thing it names."""
    from seer_engine.backtest import dev

    assert store.OWNER_INPUTS_LABEL == dev.FAILURE_LABELS[-1] == "owner inputs"
    # ...and it is the only D8 label with no number in it, which is why it can never go stale.
    assert not any(ch.isdigit() for ch in store.OWNER_INPUTS_LABEL)
    for other in dev.FAILURE_LABELS[1:-1]:
        assert any(ch.isdigit() for ch in other), other


def test_owner_failures_rederives_the_four_thresholds_and_carries_owner_inputs(conn):
    """**Four re-derived, one carried** -- the heart of the reconciled design.

    The recorded ``failed`` string names the bars of the run date. Both of them have moved: the
    luck bar to 0.90 (D1) and the drawdown bar to 20% (D6, phase 8). Only ``owner inputs`` comes
    out of the string.
    """
    from seer_engine.backtest import dev, tuning

    spy, drawdown, pf, trades, owner = dev.FAILURE_LABELS
    _method(conn)
    with conn:
        ns = store.insert_trials(conn, [
            # 19.3% drawdown: outside the old 15% bar, inside the new 20% one. Recorded failing.
            _trial(candidate_id="A", config_digest="da", max_drawdown=0.193,
                   failed="max DD <= 15%; DSR >= 0.95", n_trials_at_run=1),
            # 20.7%: outside both bars. Must still read as a drawdown miss.
            _trial(candidate_id="B", config_digest="db", max_drawdown=0.207,
                   failed="max DD <= 15%; DSR >= 0.95", n_trials_at_run=1),
            # does not beat SPY, and recorded `owner inputs` besides
            _trial(candidate_id="C", config_digest="dc", total_return=0.4, spy_tr_return=0.5,
                   profit_factor=1.1, trades=12,
                   failed=f"beats SPY TR; PF >= 1.3; >= 100 trades; {owner}",
                   n_trials_at_run=1),
        ])
    rows = {r["candidate_id"]: r for r in conn.execute("SELECT * FROM trials")}

    assert tuning.MAX_DRAWDOWN == 0.20, "phase 8 sets the drawdown bar this phase reads"
    # A: the recorded string says it missed drawdown; the columns say it clears today's bar.
    assert rows["A"]["failed"] == "max DD <= 15%; DSR >= 0.95"       # untouched on disk
    assert store.owner_failures(rows["A"]) == ()                      # ...and clear today
    # B: still outside the bar, so still a miss -- and named with TODAY's label, not the old one.
    assert store.owner_failures(rows["B"]) == (drawdown,)
    assert drawdown == "max DD <= 20%" != rows["B"]["failed"].split("; ")[0]
    # C: three thresholds re-derived from columns, plus `owner inputs` carried from the string.
    assert store.owner_failures(rows["C"]) == (spy, pf, trades, owner)
    assert store.owner_failures(rows["C"])[-1] == store.OWNER_INPUTS_LABEL


def test_a_recorded_15pct_drawdown_label_does_not_freeze_a_trial_at_15pct(conn):
    """**The drawdown twin of the luck-label test, and the reason verdict stopped parsing.**

    All 110 recorded rows say ``max DD <= 15%``; the owner set the bar to 20% on 2026-10-07. A
    trial at 19.3% must read as *clearing* drawdown, or ``M0020-W-NOSTOP`` is frozen out of the
    lab for ever by a string describing a bar nobody applies any more.
    """
    _method(conn)
    with conn:
        store.insert_trials(conn, [
            _trial(dsr=0.9134, max_drawdown=0.193, failed="max DD <= 15%; DSR >= 0.95",
                   eligible=False, n_trials_at_run=1),
        ])
    row = conn.execute("SELECT * FROM trials").fetchone()
    v = store.verdict(conn, row, at=store.Gate(n=1, policy="all-trials"))
    assert v.derived is True
    assert v.failed == ()         # neither bar it was recorded against is the bar today
    assert v.eligible is True
    assert row["failed"] == "max DD <= 15%; DSR >= 0.95"   # and the record is untouched


def test_a_recorded_095_label_is_read_as_zero_owner_misses(conn):
    """**The test that proves the gate change reaches the 110 recorded rows.**

    `trials.failed` is append-only and every recorded luck failure says "DSR >= 0.95". If the
    luck label were recognised by equality with the live `DSR_LABEL` ("DSR >= 0.90"), that
    string would read as an unrecognised owner condition, nothing would ever be eligible, and
    the deadlock would come back silently. It must read as zero owner misses and be re-judged on
    the luck test alone.
    """
    _method(conn)
    with conn:
        store.insert_trials(conn, [
            _trial(dsr=0.9156, failed="DSR >= 0.95", eligible=False, n_trials_at_run=1),
        ])
    row = conn.execute("SELECT * FROM trials").fetchone()
    assert row["failed"] == "DSR >= 0.95"                  # untouched on disk
    assert store.owner_failures(row) == ()                 # zero owner misses
    v = store.verdict(conn, row, at=store.Gate(n=1, policy="all-trials"))
    assert v.derived is True
    assert v.failed == ()                                  # re-judged on the luck test alone
    assert v.eligible is True                              # 0.9156 >= DSR_MIN 0.90


def test_verdict_failed_is_a_tuple_of_labels_in_the_recorded_order(conn):
    """Shape, pinned: `failed` is a tuple of label strings, never a "; "-joined string.

    The labels are the **live** ones: a 24.5% drawdown is outside today's 20% bar and is named
    `max DD <= 20%`, not the `max DD <= 15%` the row happens to have recorded.
    """
    from seer_engine.backtest import dev

    drawdown = dev.FAILURE_LABELS[1]
    _method(conn)
    with conn:
        store.insert_trials(conn, [
            _trial(dsr=0.5, max_drawdown=0.245, failed="max DD <= 15%; DSR >= 0.95",
                   n_trials_at_run=1),
        ])
    v = store.verdict(conn, conn.execute("SELECT * FROM trials").fetchone(),
                      at=store.Gate(n=1, policy="all-trials"))
    assert isinstance(v.failed, tuple)
    assert all(isinstance(f, str) for f in v.failed)
    assert v.failed == (drawdown, store.DSR_LABEL)  # owners first, luck last
    assert "; ".join(v.failed) == f"{drawdown}; {store.DSR_LABEL}"
    assert v.eligible is (v.failed == ())


# --------------------------------------------------------------------------- the derived verdict


def test_verdict_rederives_the_luck_label_and_the_four_thresholds(conn):
    _method(conn)
    with conn:
        lucky, owner = store.insert_trials(conn, [
            _trial(candidate_id="M0001-A", config_digest="da", failed="DSR >= 0.95",
                   n_trials_at_run=2),
            _trial(candidate_id="M0001-B", config_digest="db", max_drawdown=0.245,
                   failed="max DD <= 15%; DSR >= 0.95", n_trials_at_run=2),
        ])
        for n in (lucky, owner):
            _moments(conn, n, sr_daily=0.0595, t=3900, var_trials=2.395e-04, n_at_run=2)
    rows = {r["candidate_id"]: r for r in conn.execute("SELECT * FROM trials")}
    g = store.Gate(n=2, policy="all-trials")
    a = store.verdict(conn, rows["M0001-A"], at=g)
    b = store.verdict(conn, rows["M0001-B"], at=g)
    assert a.derived and b.derived
    assert a.dsr == pytest.approx(b.dsr)        # identical inputs, identical DSR
    assert a.dsr > store.DSR_MIN
    assert a.failed == () and a.eligible is True
    # ...and B's drawdown of 24.5% is still outside today's bar, re-derived from the column and
    # named with today's label rather than the one the row recorded.
    from seer_engine.backtest import dev

    assert b.failed == (dev.FAILURE_LABELS[1],)
    assert b.eligible is False


def test_a_recorded_dsr_at_the_gates_own_n_comes_back_unchanged(conn):
    """The identity `recover_dsr` rests on: at the trial's own N, nothing moves."""
    _method(conn)
    with conn:
        store.insert_trials(conn, [
            _trial(candidate_id="A", config_digest="da", dsr=0.9156, sharpe=0.945,
                   failed="DSR >= 0.95", n_trials_at_run=2),
            _trial(candidate_id="B", config_digest="db", dsr=0.80, sharpe=0.70,
                   failed="DSR >= 0.95", n_trials_at_run=2),
        ])
    row = conn.execute("SELECT * FROM trials WHERE candidate_id = 'A'").fetchone()
    v = store.verdict(conn, row, at=store.Gate(n=2, policy="all-trials"))
    assert v.derived is True
    assert v.dsr == pytest.approx(0.9156, abs=1e-12)   # exact, by the k-cancels identity
    assert v.failed == () and v.eligible is True


def test_a_recorded_dsr_at_another_n_is_re_evaluated_not_taken_at_face_value(conn):
    """**The decision this phase turns on.** 0.9156 at N = 2 is not 0.9156 at N = 110.

    An earlier draft returned such a row verbatim, which would have admitted `M0007-N20-RAW` on a
    DSR computed at N = 85 while judging M0022 at N = 110 — a candidate admitted for having been
    tried earlier, which is the leaderboard-mixes-bars defect R2 exists to remove. The DSR is
    re-evaluated at the gate's N instead, and the luck test is decided on *that*.
    """
    _method(conn)
    with conn:
        store.insert_trials(conn, [
            _trial(candidate_id="A", config_digest="da", dsr=0.9156, sharpe=0.945,
                   failed="DSR >= 0.95", n_trials_at_run=2),
            _trial(candidate_id="B", config_digest="db", dsr=0.80, sharpe=0.70,
                   failed="DSR >= 0.95", n_trials_at_run=2),
        ])
    row = conn.execute("SELECT * FROM trials WHERE candidate_id = 'A'").fetchone()
    wide = store.verdict(conn, row, at=store.Gate(n=400, policy="all-trials"))
    assert wide.derived is True
    assert wide.n == 400                           # the gate's N, not the recorded 2
    assert wide.dsr is not None and wide.dsr < 0.9156   # the bar rose, so the score fell
    assert row["dsr"] == pytest.approx(0.9156)     # ...and the record is untouched


def test_a_trial_with_no_evaluable_dsr_fails_the_luck_test(conn):
    """**The P7a seed trap.** `dsr IS NULL` on 54 recorded rows (`seed.py:136`).

    A luck test that cannot be evaluated is a luck test that was not passed — the same rule
    `runner.trial_rows` applies to a new trial. Without it, a seed row that passes all five owner
    conditions once the drawdown bar moves would become eligible on the strength of a luck test
    nobody ever ran. `F9-SPY200M70-MOM30` is exactly that row on the committed database.
    """
    _method(conn)
    with conn:
        n, = store.insert_trials(conn, [_trial(dsr=None, max_drawdown=0.193,
                                               failed="max DD <= 15%", n_trials_at_run=90)])
    # NO `trial_moments` row is written here, and that is the whole shape of the trap: a NULL
    # `dsr` with nothing measured beside it leaves route 2 with nothing to invert and route 1 with
    # nothing to recompute. (Give the row moments -- which is exactly what phase 9 does for the 54
    # seed trials -- and `dsr_at` takes route 1 and returns a real number. The rule below does not
    # change; it simply stops applying, which is R6.)
    row = conn.execute("SELECT * FROM trials").fetchone()
    v = store.verdict(conn, row, at=store.Gate(n=110, policy="all-trials"))
    assert store.owner_failures(row) == ()          # every owner condition clears at 20%
    assert store.dsr_at(conn, row, 110) is None
    assert v.derived is False and v.dsr is None
    assert v.failed == (store.DSR_LABEL,)           # the luck test, failed
    assert v.eligible is False


def test_an_owner_condition_is_never_re_decided_by_the_n_policy(conn):
    """The N policy moves the luck test and nothing else.

    An owner condition is re-derived against its own constant, which no policy touches: a 24.5%
    drawdown is outside the 20% bar at every N, and `owner inputs` is outside every bar there is.
    """
    from seer_engine.backtest import dev

    _method(conn)
    with conn:
        n, = store.insert_trials(conn, [
            _trial(max_drawdown=0.245, failed="max DD <= 15%; DSR >= 0.95", n_trials_at_run=1),
        ])
        _moments(conn, n, sr_daily=0.0595, t=3900, var_trials=2.395e-04, n_at_run=1)
    row = conn.execute("SELECT * FROM trials").fetchone()
    for policy in npolicy.POLICIES:
        v = store.verdict(conn, row, policy=policy)
        assert dev.FAILURE_LABELS[1] in v.failed, policy
        assert v.eligible is False, policy


# --------------------------------------------------------------------------- best_dev_eligible


def test_best_dev_eligible_keeps_its_contract_on_the_derived_verdict(conn):
    _method(conn)
    with conn:
        ns = store.insert_trials(conn, [
            _trial(candidate_id="M0001-A", config_digest="da", mar=0.9, n_trials_at_run=5),
            _trial(candidate_id="M0001-B", config_digest="db", mar=0.9, n_trials_at_run=5),
            _trial(candidate_id="M0001-C", config_digest="dc", mar=1.4, max_drawdown=0.245,
                   failed="max DD <= 15%; DSR >= 0.95", n_trials_at_run=5),  # top MAR, owner fail
            _trial(candidate_id="M0001-D", config_digest="dd", mar=None, n_trials_at_run=5),
            _trial(candidate_id="M0001-E", config_digest="de", window="test", mar=2.0,
                   n_trials_at_run=5),
        ])
        for n in ns:
            _moments(conn, n, sr_daily=0.0595, t=3900, var_trials=2.395e-04, n_at_run=5)
    best = store.best_dev_eligible(conn, "M0001")
    # The tie between A and B breaks on n; C has the highest MAR but fails max DD, which no
    # threshold re-decides; D has no MAR; E is a test trial.
    assert best["candidate_id"] == "M0001-A"
    assert store.best_dev_eligible(conn, "M0002") is None


def test_best_dev_eligible_skips_a_trial_whose_luck_test_cannot_be_evaluated(conn):
    """A NULL `dsr` is never the answer, however good its MAR: it failed the luck test."""
    _method(conn)
    with conn:
        store.insert_trials(conn, [
            _trial(candidate_id="M0001-A", config_digest="da", mar=0.9, dsr=0.9156,
                   sharpe=0.945, failed="DSR >= 0.95", n_trials_at_run=2),
            _trial(candidate_id="M0001-C", config_digest="dc", mar=1.4, dsr=None,
                   failed="DSR >= 0.95", n_trials_at_run=2),
        ])
    best = store.best_dev_eligible(conn, "M0001", at=store.Gate(n=2, policy="all-trials"))
    assert best["candidate_id"] == "M0001-A"   # C has the higher MAR and no evaluable DSR


# --------------------------------------------------------------------------- the one new edge


def _luck_only_method(conn, mid="M0001"):
    """A rejected method with one luck-only dev trial that clears 0.90 but not 0.95."""
    _method(conn, mid)
    with conn:
        store.update_method(conn, mid, status="registered")
        store.update_method(conn, mid, status="rejected")
        store.insert_trials(conn, [
            _trial(method_id=mid, candidate_id=f"{mid}-A", config_digest=f"d{mid}",
                   dsr=0.9156, failed="DSR >= 0.95", n_trials_at_run=1),
        ])


def test_reevaluate_takes_the_edge_for_a_luck_only_rejection(conn):
    _luck_only_method(conn)
    with conn:
        r = store.reevaluate_method(conn, "M0001")
    assert r.moved is True
    assert r.status_before == "rejected" and r.status_after == "dev-eligible"
    assert r.unblocked == ("M0001-A",)
    assert store.get_method(conn, "M0001")["status"] == "dev-eligible"
    analysis = store.get_method(conn, "M0001")["analysis"]
    assert store.REEVALUATION_MARKER in analysis
    assert store.DSR_LABEL in analysis and f"N = {r.gate.n}" in analysis
    assert "M0001-A" in analysis
    # the trial that decided the rejection is untouched, label and all
    row = conn.execute("SELECT * FROM trials WHERE method_id = 'M0001'").fetchone()
    assert row["eligible"] == 0 and row["failed"] == "DSR >= 0.95"
    assert row["dsr"] == pytest.approx(0.9156) and row["n_trials_at_run"] == 1


def test_reevaluate_will_not_move_a_method_that_failed_an_owner_condition(conn):
    _method(conn, "M0002")
    with conn:
        store.update_method(conn, "M0002", status="registered")
        store.update_method(conn, "M0002", status="rejected")
        store.insert_trials(conn, [
            _trial(method_id="M0002", candidate_id="M0002-A", max_drawdown=0.245, dsr=0.9156,
                   failed="max DD <= 15%; DSR >= 0.95", n_trials_at_run=1),
        ])
        r = store.reevaluate_method(conn, "M0002")
    assert r.moved is False and r.unblocked == ()
    assert store.get_method(conn, "M0002")["status"] == "rejected"


def test_reevaluate_does_move_a_method_the_moved_drawdown_bar_unblocks(conn):
    """The counterpart, and the shape ``M0020-W-NOSTOP`` has on the committed database.

    A recorded failure of ``max DD <= 15%; DSR >= 0.95`` is **not** a reason to refuse the edge
    any more: the owner moved both of those bars on 2026-10-07, and a trial at 19.3% drawdown is
    inside the one in force now. The earlier draft's rule -- "only a rejection that was the luck
    label alone may be reconsidered" -- would have frozen this method out for ever.
    """
    _method(conn, "M0004")
    with conn:
        store.update_method(conn, "M0004", status="registered")
        store.update_method(conn, "M0004", status="rejected")
        store.insert_trials(conn, [
            _trial(method_id="M0004", candidate_id="M0004-A", config_digest="d4",
                   max_drawdown=0.193, dsr=0.9134, failed="max DD <= 15%; DSR >= 0.95",
                   n_trials_at_run=1),
        ])
        r = store.reevaluate_method(conn, "M0004")
    assert r.moved is True and r.unblocked == ("M0004-A",)
    assert store.get_method(conn, "M0004")["status"] == "dev-eligible"
    row = conn.execute("SELECT * FROM trials WHERE method_id = 'M0004'").fetchone()
    assert row["failed"] == "max DD <= 15%; DSR >= 0.95"   # the record is untouched
    assert row["eligible"] == 0


def test_reevaluate_refuses_outright_if_a_verdict_contradicts_the_record(conn, monkeypatch):
    """The second, independent no.

    ``verdict`` cannot produce this state -- it derives the same four conditions from the same
    columns -- so the only way to reach the guard is to replace ``verdict``. That is the point:
    ``_blocking`` is written separately so that a future change to ``owner_failures`` or to
    ``verdict`` cannot quietly promote a method whose recorded numbers do not clear the bars.

    24.5% is outside today's 20% bar, so this is a genuine drawdown failure and not a stale label.
    """
    _method(conn, "M0003")
    with conn:
        store.update_method(conn, "M0003", status="registered")
        store.update_method(conn, "M0003", status="rejected")
        store.insert_trials(conn, [
            _trial(method_id="M0003", candidate_id="M0003-A", max_drawdown=0.245,
                   failed="max DD <= 15%; DSR >= 0.95", n_trials_at_run=1),
        ])
    monkeypatch.setattr(
        store, "verdict",
        lambda c, t, **kw: store.Verdict(0.99, (), True, 1, "all-trials", True),
    )
    with pytest.raises(store.LabError, match="second, independent check"):
        with conn:
            store.reevaluate_method(conn, "M0003")
    assert store.get_method(conn, "M0003")["status"] == "rejected"


def test_the_independent_check_refuses_a_recorded_owner_inputs_whatever_the_verdict_says(conn):
    """``owner inputs`` is the one condition no constant re-decides, and the one ``_blocking``
    reads out of the recorded string rather than out of a column."""
    _method(conn, "M0005")
    with conn:
        store.update_method(conn, "M0005", status="registered")
        store.update_method(conn, "M0005", status="rejected")
        store.insert_trials(conn, [
            _trial(method_id="M0005", candidate_id="M0005-A", config_digest="d5", dsr=0.9156,
                   failed=f"{store.OWNER_INPUTS_LABEL}; DSR >= 0.95", n_trials_at_run=1),
        ])
    # verdict already refuses it: `owner inputs` is carried from the record.
    row = conn.execute("SELECT * FROM trials WHERE method_id = 'M0005'").fetchone()
    assert store.verdict(conn, row, at=store.Gate(n=1, policy="all-trials")).failed == (
        store.OWNER_INPUTS_LABEL,)
    with conn:
        assert store.reevaluate_method(conn, "M0005").moved is False
    # ...and so does the independent check, if verdict ever stopped.
    assert store.OWNER_INPUTS_LABEL in "; ".join(store._blocking(row))


def test_reevaluate_is_idempotent_and_moves_only_from_rejected(conn):
    _luck_only_method(conn)
    with conn:
        assert store.reevaluate_method(conn, "M0001").moved is True
    before = store.get_method(conn, "M0001")["analysis"]
    with conn:
        again = store.reevaluate_method(conn, "M0001")
    assert again.moved is False and again.status_before == "dev-eligible"
    assert store.get_method(conn, "M0001")["analysis"] == before


def test_reevaluate_sweeps_every_rejected_method(conn):
    _luck_only_method(conn, "M0001")
    _method(conn, "M0002")
    with conn:
        store.update_method(conn, "M0002", status="rejected")  # dropped before running
        results = store.reevaluate(conn)
    assert {r.method_id for r in results} == {"M0001", "M0002"}
    assert [r.method_id for r in results if r.moved] == ["M0001"]
    assert [r for r in results if r.method_id == "M0002"][0].dev_trials == 0


# --------------------------------------------------------------------------- the projection


def test_pending_gate_reproduces_todays_n_under_the_shipped_policy(conn, monkeypatch):
    _method(conn, "M0001")
    with conn:
        store.insert_trials(conn, [_trial(method_id="M0001", candidate_id="M0001-A")])
    assert store.DSR_POLICY == "all-trials"
    # exactly the expression runner.trial_rows used before this phase
    assert store.pending_gate(conn, "M0001", 3).n == store.dev_trial_count(conn) + 3
    assert store.pending_gate(conn, "M0009", 3).n == store.dev_trial_count(conn) + 3
    assert store.pending_gate(conn, "M0009", 0).n == store.gate(conn).n
    monkeypatch.setattr(store, "DSR_POLICY", "methods")
    assert store.pending_gate(conn, "M0001", 3).n == store.gate(conn).n      # known method
    assert store.pending_gate(conn, "M0009", 3).n == store.gate(conn).n + 1  # new method
    for policy in npolicy.POLICIES:
        monkeypatch.setattr(store, "DSR_POLICY", policy)
        assert store.pending_gate(conn, "M0009", 5).n >= store.gate(conn).n, policy


def test_the_gate_is_resolved_once_per_dev_trial_set(conn, monkeypatch):
    """The estimator is an eigendecomposition over every recorded curve; `lab status` walks 23
    methods. Both the memo and the explicit `at=` must keep that to one call."""
    from seer_engine.lab import npolicy

    _method(conn)
    with conn:
        store.insert_trials(conn, [
            _trial(candidate_id="M0001-A", config_digest="da", mar=0.9, n_trials_at_run=2),
            _trial(candidate_id="M0001-B", config_digest="db", mar=0.8, n_trials_at_run=2),
        ])
    store._GATE_CACHE.clear()
    calls = []
    real = npolicy.effective_n
    monkeypatch.setattr(
        npolicy, "effective_n", lambda c, p: (calls.append(p), real(c, p))[1]
    )
    for _ in range(5):
        store.gate(conn)
    assert len(calls) == 1, "the memo did not hold"
    # ...and it invalidates on an insert, because the key is the dev trial set.
    with conn:
        store.insert_trials(conn, [
            _trial(candidate_id="M0001-C", config_digest="dc", mar=0.7, n_trials_at_run=3),
        ])
    store.gate(conn)
    assert len(calls) == 2, "the memo did not invalidate"
    # The explicit route resolves once regardless of the cache.
    store._GATE_CACHE.clear()
    calls.clear()
    g = store.gate(conn)
    for _ in range(5):
        store.best_dev_eligible(conn, "M0001", at=g)
    assert len(calls) == 1


# --------------------------------------------------------------------------- the committed lab

# The four recorded columns of all 110 trials on `lab/lab.sqlite`, hashed. This phase derives a
# verdict and never writes one, so this digest is a constant for the life of the current rows:
#     SELECT n, dsr, eligible, failed, n_trials_at_run FROM trials ORDER BY n
# hashing `repr(row)` of each sqlite3 tuple into one sha256.
RECORDED_VERDICT_DIGEST = "166ae36bdc4425cebd7380b0187f9c21dc7726d502fe999bd7746e60bc974016"


def _recorded_digest(conn) -> str:
    h = hashlib.sha256()
    for row in conn.execute(
        "SELECT n, dsr, eligible, failed, n_trials_at_run FROM trials ORDER BY n"
    ):
        h.update(repr(row).encode())
    return h.hexdigest()


@pytest.fixture()
def committed(tmp_path):
    """A writable copy of the committed lab, migrated. The original is never opened for writing."""
    if not store.COMMITTED_DB.exists():
        pytest.skip("no committed lab database")
    path = tmp_path / "lab.sqlite"
    shutil.copyfile(store.COMMITTED_DB, path)
    c = store.connect(path)
    c.row_factory = sqlite3.Row
    yield c
    c.close()


def test_the_shipped_defaults_reproduce_todays_n(committed):
    """Nobody should have to reason about which module's default wins."""
    assert store.DSR_POLICY == "all-trials"
    g = store.gate(committed)
    assert g.policy == "all-trials"
    assert g.n == 110 == store.dev_trial_count(committed)


def test_the_committed_lab_keeps_every_recorded_verdict_and_spends_no_look(committed):
    assert committed.execute("SELECT count(*) FROM trials").fetchone()[0] == 110
    assert _recorded_digest(committed) == RECORDED_VERDICT_DIGEST
    assert store.test_looks(committed) == 0
    assert committed.execute(
        "SELECT 1 FROM transitions WHERE src = 'rejected' AND dst = 'dev-eligible'"
    ).fetchone() is not None
    assert committed.execute("SELECT count(*) FROM trial_moments").fetchone()[0] == 0


def test_the_two_moved_bars_unblock_exactly_m0022_and_m0020(committed):
    """R1 + R5, measured. At (N=110, DSR >= 0.90, max DD <= 20%) **three** candidates clear.

    Two of them are M0022's, admitted by the luck threshold the owner moved (D1). The third is
    `M0020-W-NOSTOP`, admitted by the drawdown threshold the owner moved (D6, phase 8): 19.3% is
    outside the old 15% bar and inside the new 20% one, and its DSR of 0.913 clears 0.90.
    """
    from seer_engine.backtest import tuning

    assert store.DSR_MIN == 0.90 and tuning.MAX_DRAWDOWN == 0.20
    with committed:
        results = store.reevaluate(committed)
    assert sorted(r.method_id for r in results if r.moved) == ["M0020", "M0022"]
    assert store.get_method(committed, "M0020")["status"] == "dev-eligible"
    assert store.get_method(committed, "M0022")["status"] == "dev-eligible"
    g = store.gate(committed)
    eligible = [
        row["candidate_id"]
        for row in committed.execute("SELECT * FROM trials WHERE window = 'dev' ORDER BY n")
        if store.verdict(committed, row, at=g).eligible
    ]
    assert sorted(eligible) == ["M0020-W-NOSTOP", "M0022-W-TV14", "M0022-W-TV16"]
    assert len(eligible) == 3, (
        "three, not four: M0007-N20-RAW's recorded 0.9138 was computed at N = 85 and is 0.8985 "
        "at today's N = 110 (Decision D8). If this reads four, verdict is taking a recorded DSR "
        "at face value again."
    )
    # MAR decides, not DSR: W-TV14 is MAR 0.857 / DSR 0.912, W-TV16 is MAR 0.816 / DSR 0.916.
    best = store.best_dev_eligible(committed, "M0022")
    assert best["candidate_id"] == "M0022-W-TV14"
    assert best["mar"] == pytest.approx(0.8567, abs=1e-3)
    assert store.best_dev_eligible(committed, "M0020")["candidate_id"] == "M0020-W-NOSTOP"
    # nothing recorded moved, and no look was spent
    assert _recorded_digest(committed) == RECORDED_VERDICT_DIGEST
    assert store.test_looks(committed) == 0


def test_the_three_near_misses_that_still_do_not_qualify(committed):
    """Each of the three fails for a different, named reason -- and none of them is a stale label.

    This is the test that says the two moved bars did not become a general amnesty.
    """
    from seer_engine.backtest import dev, tuning

    g = store.gate(committed)
    rows = {
        r["candidate_id"]: r
        for r in committed.execute("SELECT * FROM trials WHERE window = 'dev'")
    }

    # 1. **The one trial where the recorded number and the current bar disagree.**
    #    M0007-N20-RAW clears the NEW drawdown bar (19.6% <= 20%) and passes every owner
    #    condition. Its RECORDED dsr is 0.9138, which is above 0.90 -- so reading the recorded
    #    column would admit it. RE-EVALUATED at today's N = 110 it is 0.8985, which is not.
    #    The gate uses the re-evaluated number (Decision D8), so it stays out.
    m7 = rows["M0007-N20-RAW"]
    assert float(m7["max_drawdown"]) <= tuning.MAX_DRAWDOWN
    assert store.owner_failures(m7) == ()                      # every owner condition clears
    assert int(m7["n_trials_at_run"]) == 85
    assert float(m7["dsr"]) == pytest.approx(0.9138, abs=1e-3)  # recorded, at N = 85: ABOVE 0.90
    assert store.dsr_at(committed, m7, g.n) == pytest.approx(0.8985, abs=1e-3)  # at N=110: below
    assert store.verdict(committed, m7, at=g).eligible is False
    assert store.get_method(committed, "M0007")["status"] != "dev-eligible"

    # 2. M0019-RAW20-S25 is outside even the new bar, at 20.7%.
    m19 = rows["M0019-RAW20-S25"]
    assert float(m19["max_drawdown"]) > tuning.MAX_DRAWDOWN
    assert store.owner_failures(m19) == (dev.FAILURE_LABELS[1],)
    assert store.verdict(committed, m19, at=g).eligible is False

    # 3. M0001-TV10 does not beat SPY TR, which no threshold in this plan set moves.
    m1 = rows["M0001-TV10"]
    assert dev.FAILURE_LABELS[0] in store.owner_failures(m1)
    assert store.verdict(committed, m1, at=g).eligible is False


def test_f3_stays_ineligible_on_owner_inputs_whatever_its_luck_test_says(committed):
    """**F3 is the owner-inputs case, not the NULL-DSR case** — and that is unconditional.

    `F3-SEC-TOP3-6M-TREND`'s recorded `failed` is `"max DD <= 15%; owner inputs"`. Phase 8's bar
    clears the drawdown half (19.5% <= 20%); `owner inputs` is the one D8 condition that is not a
    threshold, that no constant re-decides, and that `owner_failures` therefore **carries** from
    the recorded string rather than re-deriving. So F3 is ineligible on owner inputs alone,
    **independently of its luck test** — before phase 9 gives it moments and after.

    This test takes no view on F3's DSR and must never be given one; the NULL-DSR rule is pinned
    on F9 below, where it is the *only* reason. (An earlier brief to this phase called both rows
    "ineligible-by-NULL seed traps". That is wrong about F3 and is corrected here.)
    """
    f3 = committed.execute(
        "SELECT * FROM trials WHERE candidate_id = 'F3-SEC-TOP3-6M-TREND'"
    ).fetchone()
    assert float(f3["max_drawdown"]) == pytest.approx(0.1951, abs=1e-3)
    assert store.owner_failures(f3) == (store.OWNER_INPUTS_LABEL,), (
        "the drawdown half clears at 20%; `owner inputs` is carried and is the whole reason"
    )
    v3 = store.verdict(committed, f3, at=store.gate(committed))
    assert store.OWNER_INPUTS_LABEL in v3.failed
    assert v3.eligible is False
    with committed:
        assert store.reevaluate_method(committed, "H-P7A-F3").moved is False


def test_f9_the_one_seed_row_held_out_by_the_luck_test_alone(committed):
    """**The P7a seed trap, on the real data, in its purest case.**

    `F9-SPY200M70-MOM30` passes **all five** owner conditions once the drawdown bar is 20%
    (fall 19.2%, MAR 0.635). Before the drawdown change the recorded 15% bar kept it out and
    nobody had to think about its missing DSR. At 20% a `verdict` that read a NULL DSR as "no luck
    failure" would admit it on a luck test that was never run. The NULL-DSR rule is the only thing
    holding it, which is what makes it the right pin for that rule.

    **This test describes the lab as phase 4 finds it, not a permanent fact about this trial.**
    Phase 9 (`lab remeasure` over the P7a seed, Decision D7) recovers its moments, at which point
    `dsr_at` takes route 1 and it gets a real luck verdict. Measured by phase 9, under Decision
    D12's today's-variance rule that `dsr_at` applies, that verdict is **0.8567 at N = 110** —
    still under 0.90, so F9 stays ineligible either way, but afterwards on a luck test it
    *received* rather than on a data gap. That is R6.

    The *rule* under test here is unchanged by phase 9 and is the point: a trial with no evaluable
    luck test fails it. Phase 9 does not change the rule; it stops the rule applying to this row
    by giving it something to evaluate. If this test fails after phase 9 has been run against the
    committed database, re-point it at a fixture rather than weakening the rule.
    """
    if committed.execute(
        "SELECT count(*) FROM trial_moments m JOIN trials t ON t.n = m.trial_n "
        "WHERE t.candidate_id = 'F9-SPY200M70-MOM30'"
    ).fetchone()[0]:
        pytest.skip("phase 9 has luck-tested the seed; this row now has moments")
    g = store.gate(committed)
    f9 = committed.execute(
        "SELECT * FROM trials WHERE candidate_id = 'F9-SPY200M70-MOM30'"
    ).fetchone()
    assert f9["dsr"] is None and float(f9["max_drawdown"]) == pytest.approx(0.1924, abs=1e-3)
    assert store.owner_failures(f9) == (), "at 20% it misses no owner condition"
    assert store.dsr_at(committed, f9, g.n) is None
    v9 = store.verdict(committed, f9, at=g)
    assert v9.failed == (store.DSR_LABEL,) and v9.eligible is False
    with committed:
        assert store.reevaluate_method(committed, "H-P7A-F9").moved is False


def test_m0011_stays_rejected_so_rm_and_rmw_diverge_on_purpose(committed):
    """RMW-FR becomes lab-eligible; RM-FR does not. The asymmetry is the measurement, not a bug."""
    with committed:
        store.reevaluate(committed)
    assert store.get_method(committed, "M0011")["status"] == "rejected"
    assert store.get_method(committed, "M0022")["status"] == "dev-eligible"
    row = committed.execute(
        "SELECT * FROM trials WHERE candidate_id = 'M0011-RAW20-TV14-N21'"
    ).fetchone()
    # Decision D8, the quoting convention, as an assertion. The RECORDED value at the RECORDED N
    # is 0.8974 -- already under the new bar on its own terms. (Re-evaluated at today's gate N of
    # 110 it is 0.884, further under; that number is not asserted here because this phase never
    # computes it -- `verdict` refuses to, which is the point of case 3.)
    assert row["dsr"] == pytest.approx(0.8974, abs=1e-3)
    assert row["n_trials_at_run"] == 90                    # and recorded at another N besides
    v = store.verdict(committed, row)
    assert v.derived is False          # case 3: it does not qualify for re-thresholding at all
    assert v.n == 90                   # the recorded N, not the gate's
    assert v.eligible is False


def test_no_candidate_that_fails_a_condition_at_todays_bars_becomes_eligible(committed):
    """The owner conditions bind under every N policy. Note the argument: ``owner_failures`` takes
    the **row**, so this asks what each trial is today, not what its recorded string says."""
    g = store.gate(committed)
    for row in committed.execute("SELECT * FROM trials WHERE window = 'dev'"):
        if store.owner_failures(row):
            assert store.verdict(committed, row, at=g).eligible is False, row["candidate_id"]
            for policy in npolicy.POLICIES:
                assert store.verdict(committed, row, policy=policy).eligible is False, (
                    row["candidate_id"], policy)
    # The two that still fail an owner condition at today's bars, and must never be admitted at
    # any N. (M0007-N20-RAW is no longer one of them -- it now clears every owner condition and
    # fails only the luck test; see test_the_three_near_misses_that_still_do_not_qualify.)
    for cid, index in (("M0019-RAW20-S25", 1), ("M0001-TV10", 0)):
        from seer_engine.backtest import dev

        row = committed.execute("SELECT * FROM trials WHERE candidate_id = ?", (cid,)).fetchone()
        assert dev.FAILURE_LABELS[index] in store.owner_failures(row), cid
        for policy in npolicy.POLICIES:
            assert store.verdict(committed, row, policy=policy).eligible is False, (cid, policy)


# --- the N-sensitivity regression, on reconstructed moments --------------------------------


def _sr_star(var: float, n: int) -> float:
    nd = NormalDist()
    return math.sqrt(var) * (
        (1 - _EULER_GAMMA) * nd.inv_cdf(1 - 1 / n) + _EULER_GAMMA * nd.inv_cdf(1 - 1 / (n * math.e))
    )


def _reconstruct_moments(conn) -> int:
    """Write a ``trial_moments`` row for every recorded dev trial that has a DSR; return the count.

    **A reconstruction, not a measurement** -- the rows are written ``measured = "reconstruction"``.
    ``lab remeasure`` (phase 3) recovers the real ``(t, skew, kurt)`` by re-running the dev
    window, which these tests cannot do. Instead: ``sr_daily`` is the recorded annualized Sharpe
    over sqrt(252), ``skew`` and ``kurt`` are pinned at the normal values, and ``t`` is solved so
    the row reproduces its own recorded DSR at its own recorded N -- verified here to 2e-5.

    **The variance it solves against is ``store.dev_sharpe_variance(conn)`` -- today's -- not the
    variance in force on the trial's run date.** That is the same variance ``store.dsr_at`` uses
    on both of its routes, and using it here is what makes the two routes comparable at all:
    solving ``t`` against a stale variance and then evaluating against today's would put the two
    routes up to **0.098** apart on the committed lab, which is eleven times the margin the gate
    is deciding by. Solved this way they agree to **1.3e-5**
    (``test_the_two_routes_to_a_dsr_agree``).

    That is enough to prove this phase's claims about N and the threshold, and nothing about the
    real higher moments. The solved ``t`` ranges from about 1,800 to 17,600 for a dev window of
    roughly 3,970 sessions, which is the visible sign that it is a fit and not a measurement.
    """
    rows = conn.execute("SELECT * FROM trials WHERE window = 'dev' ORDER BY n").fetchall()
    var = store.dev_sharpe_variance(conn)
    assert var is not None
    nd = NormalDist()
    written = 0
    for r in rows:
        if r["dsr"] is None or r["sharpe"] is None:
            continue  # the 54 P7a seed trials: dsr IS NULL by construction (seed.py:136)
        n0 = int(r["n_trials_at_run"])
        sr = float(r["sharpe"]) / math.sqrt(252)
        k = nd.inv_cdf(float(r["dsr"])) / (sr - _sr_star(var, n0))
        t = round(1 + k * k * (1 + sr * sr / 2))  # skew 0, kurt 3 => radicand = 1 + sr^2/2
        _moments(conn, int(r["n"]), sr_daily=sr, t=t, var_trials=var, n_at_run=n0)
        assert deflated_sharpe(sr, n0, var, t, 0.0, 3.0) == pytest.approx(
            float(r["dsr"]), abs=2e-5
        ), r["candidate_id"]
        written += 1
    return written


def test_the_two_routes_to_a_dsr_agree(committed):
    """``dsr_at``'s two routes are one number.

    Route 2 (invert the recorded DSR and re-evaluate at the gate's N) and route 1 (recompute
    exactly from ``trial_moments``) must agree on every trial, not only on the ones whose
    recorded N is already the gate's. That agreement is what makes route 2 a *re-reading* of the
    record rather than a second opinion about it -- and it is what lets the gate judge all 56
    lab-method trials today, with ``lab remeasure`` an exactness upgrade rather than a
    precondition.
    """
    rows = committed.execute(
        "SELECT * FROM trials WHERE window = 'dev' AND dsr IS NOT NULL ORDER BY n"
    ).fetchall()
    assert rows
    g = store.gate(committed)
    before = {r["candidate_id"]: store.verdict(committed, r, at=g) for r in rows}
    assert all(v.derived for v in before.values()), "every recorded DSR is evaluable at the gate"
    with committed:
        _reconstruct_moments(committed)
    for r in rows:
        after = store.verdict(committed, r, at=g)
        assert after.derived
        assert after.dsr == pytest.approx(before[r["candidate_id"]].dsr, abs=2e-4), (
            r["candidate_id"])
        assert after.eligible == before[r["candidate_id"]].eligible, r["candidate_id"]


def test_dsr_at_deflates_by_todays_variance_not_the_one_recorded_beside_the_trial(conn):
    """**Decision D12, as an assertion.** The pin that stops this fork being re-opened.

    `trial_moments.var_trials` is the trial-Sharpe variance that was in force when the trial ran.
    It is kept as history and is **never** an input to a live verdict: `dsr_at` deflates by
    `dev_sharpe_variance(conn)` -- today's -- on both routes, read once above the branch.

    Phase 9 is where the difference bites. On the 54 P7a seed rows the recorded variance
    (2.006691e-04, the P7a search's own) and today's (2.395048e-04, all 110 dev trials) move
    `F9-SPY200M70-MOM30` from 0.903053 to 0.856651 -- across the 0.90 bar. Rung 4, the index's R2:
    the hurdle is `sqrt(var_trials) x E[max over N]`, so pairing today's N with a run-date
    variance freezes half the hurdle at the run date and reintroduces the very incoherence R2
    exists to remove. This is the same principle, and must stay the same answer, as D11's refusal
    to use `n_trials_at_run`.
    """
    from seer_engine.backtest import dev

    _method(conn)
    with conn:
        # Two trials with DIFFERENT Sharpes, so the fixture lab has a real, non-zero variance.
        a, b = store.insert_trials(conn, [
            _trial(candidate_id="M0001-A", config_digest="da", sharpe=0.94, n_trials_at_run=2),
            _trial(candidate_id="M0001-B", config_digest="db", sharpe=1.46, n_trials_at_run=2),
        ])
        # ...and a moments row whose recorded var_trials is deliberately a DIFFERENT number.
        _moments(conn, a, sr_daily=0.0595, t=3900, var_trials=9.9e-04, n_at_run=2)
    row = conn.execute("SELECT * FROM trials WHERE candidate_id = 'M0001-A'").fetchone()
    today = store.dev_sharpe_variance(conn)
    assert today is not None and today != pytest.approx(9.9e-04)

    got = store.dsr_at(conn, row, 110)
    want_today = dev.deflated_sharpe(0.0595, 110, today, 3900, 0.0, 3.0)
    want_recorded = dev.deflated_sharpe(0.0595, 110, 9.9e-04, 3900, 0.0, 3.0)
    assert want_today != pytest.approx(want_recorded), "the fixture must separate the two"
    assert got == pytest.approx(want_today), (
        "dsr_at read the stored var_trials again; it must deflate by dev_sharpe_variance (D12)"
    )
    assert got != pytest.approx(want_recorded)
    # ...and the recorded column is still there, untouched, as history.
    assert float(store.moments_of(conn, a)["var_trials"]) == pytest.approx(9.9e-04)


def test_the_old_bars_reproduce_todays_verdicts(committed, monkeypatch):
    """Decisions D1's and D6's reversal clause, as a test rather than a claim: put **all three**
    constants back — the N policy, the luck bar and the drawdown bar — and the lab reads exactly
    as it does on `main`, with no data change.

    The drawdown constant is in the list because this phase's `verdict` re-derives against it;
    leaving it at 20% would admit `M0020-W-NOSTOP` and the comparison would not be a comparison.
    """
    from seer_engine.backtest import dev, tuning

    monkeypatch.setattr(store, "DSR_POLICY", "all-trials")
    monkeypatch.setattr(store, "DSR_MIN", 0.95)
    monkeypatch.setattr(store, "DSR_LABEL", "DSR >= 0.95")
    monkeypatch.setattr(tuning, "MAX_DRAWDOWN", 0.15)
    monkeypatch.setattr(
        dev, "FAILURE_LABELS",
        ("beats SPY TR", "max DD <= 15%", "PF >= 1.3", ">= 100 trades", "owner inputs"),
    )
    with committed:
        assert _reconstruct_moments(committed) == 56  # the 54 seed rows have no DSR
        results = store.reevaluate(committed)
    assert store.gate(committed).n == 110
    assert [r.method_id for r in results if r.moved] == []
    g = store.gate(committed)
    for row in committed.execute("SELECT * FROM trials WHERE window = 'dev'"):
        v = store.verdict(committed, row, at=g)
        if v.derived:
            assert v.eligible == bool(row["eligible"]), row["candidate_id"]
    assert _recorded_digest(committed) == RECORDED_VERDICT_DIGEST
```

**Impact:** every VERIFY claim becomes executable.

---

### Step 10: The migration of the committed `lab/lab.sqlite`

Per Decisions **D5**, this is the only phase in the set that commits this binary.

```
cd /home/miftah/.worktrees/seer/lab-luck-gate
PYTHONPATH=engine/src /home/miftah/seer/engine/.venv/bin/python -m seer_engine lab reevaluate
PYTHONPATH=engine/src /home/miftah/seer/engine/.venv/bin/python -m seer_engine lab export-json
```

> **`export-json`, not `stage` (Decision D10, reconciled).** `lab stage` re-exports *and* `git add`s
> both `lab/lab.sqlite` and `web/data/lab.json`. The swarm shares one worktree, so a `git add` from
> inside a tool can stage another phase's in-flight work; every phase in this set stages its own
> explicit path allowlist instead. `export-json` writes the file and adds nothing. Phase 7 follows
> the same rule for the same reason.

`lab reevaluate` opens the database through `store.connect`, which under the write lock:

1. runs phase 2's v2 -> v3 `_migrate`, creating the empty `trial_moments` table and its triggers.
   **No `trials` row is read or written by that migration**;
2. runs `INSERT OR IGNORE INTO transitions (src, dst)` over `TRANSITIONS`, adding the single row
   `('rejected', 'dev-eligible')`;

then re-judges every rejected method and moves **M0022** to `dev-eligible`, appending one dated
section to its analysis. `lab export-json` then rewrites `web/data/lab.json` from the migrated
database, which this phase must do rather than leave to phase 7:
`test_the_committed_snapshot_is_the_export_of_the_committed_database` asserts the committed JSON
*is* the export of the committed database, and this phase changes both `DSR_MIN` and the database.

**Expected output of `lab reevaluate`:**

```
luck bar: DSR >= 0.90   N policy: all-trials, N = 110   (110 dev trial rows on the books)

  ...
  M0011: re-judged 2 of 5 dev trial(s) against DSR >= 0.90 (3 still need `lab remeasure`); still rejected
  ...
  M0020: rejected -> dev-eligible  (M0020-W-NOSTOP)
  ...
  M0022: rejected -> dev-eligible  (M0022-W-TV14, M0022-W-TV16)

2 method(s) moved rejected -> dev-eligible; test-window looks used: 0
```

**M0020 moves because of phase 8's drawdown bar, not because of this phase's threshold** —
`M0020-W-NOSTOP` drew down 19.3%, which the owner's new 20% bar admits, and its DSR of 0.913 at
N = 110 clears 0.90. If phase 8 has not landed, this run moves **M0022 only** and
`test_the_two_moved_bars_unblock_exactly_m0022_and_m0020` fails; that is why phase 8 is a
dependency rather than a nicety.

**What changes in the committed artifacts, exhaustively:**

| artifact | change |
|---|---|
| `lab/lab.sqlite` `meta.schema_version` | `2` -> `3` |
| `lab/lab.sqlite` `trial_moments` | created, **empty** |
| `lab/lab.sqlite` `transitions` | one row added |
| `lab/lab.sqlite` `methods` M0022 **and M0020** | `status` `rejected` -> `dev-eligible`; `analysis` grows by one dated section; `updated` bumped |
| `lab/lab.sqlite` `trials` | **nothing** — verify with `RECORDED_VERDICT_DIGEST` |
| `web/data/lab.json` | `gate.dsrMin` `0.95` -> `0.90`; M0020's and M0022's `status`, `analysis` and `updated`; `summary.byStatus` (`rejected` 26 -> 24, `dev-eligible` 0 -> 2); `asOf`. Every `trials[*].eligible` / `.dsr` / `.nTrialsAtRun` unchanged. (`gate.maxDrawdown` 0.15 -> 0.20 arrives with **phase 8**, which lands before this one and regenerates the file itself.) |

**Idempotent:** a second run creates nothing (`CREATE TABLE IF NOT EXISTS`, `INSERT OR IGNORE`) and
moves nothing (M0022 is no longer `rejected`, so `reevaluate_method` returns `moved=False` and
writes no analysis). SQLite does not promise byte-stable page layout, so verify idempotence with a
SQL dump, not with bytes:

```
for i in 1 2; do
  PYTHONPATH=engine/src /home/miftah/seer/engine/.venv/bin/python -m seer_engine lab reevaluate >/dev/null
  sqlite3 lab/lab.sqlite .dump | sha256sum
done
```

The two digests must match.

**Commit path allowlist** (the swarm shares one worktree — stage these explicitly, never
`git add -A`):

```
engine/src/seer_engine/lab/store.py
engine/src/seer_engine/lab/runner.py
engine/src/seer_engine/commands/lab.py
engine/tests/test_lab_store.py
engine/tests/test_lab_gate_policy.py
lab/lab.sqlite
web/data/lab.json
.workflows/plan/lab-luck-gate/phase-4.md
```

> **`web/data/lab.json` is a generated file that phase 7 also regenerates** (it adds the policy and
> N to the `gate` block). Expect a conflict there at merge; the resolution is always "re-run
> `lab stage` after both code changes land", never a hand edit. See **Handoffs #4**.

---

## Verification

**Build:** there is no build step for `engine/`; import is the check.

```
cd /home/miftah/.worktrees/seer/lab-luck-gate/engine
PYTHONPATH=/home/miftah/.worktrees/seer/lab-luck-gate/engine/src \
  /home/miftah/seer/engine/.venv/bin/python -c \
  "from seer_engine.lab import store, runner; from seer_engine.commands import lab; \
   print(store.DSR_MIN, store.DSR_LABEL, store.DSR_POLICY, \
         ('rejected','dev-eligible') in store.TRANSITIONS)"
```

Expected: `0.9 DSR >= 0.90 all-trials True`.

**Tests:**

```
cd /home/miftah/.worktrees/seer/lab-luck-gate/engine
PYTHONPATH=/home/miftah/.worktrees/seer/lab-luck-gate/engine/src \
  /home/miftah/seer/engine/.venv/bin/python -m pytest -q
```

The full suite, not a subset: the threshold and the label are read by `test_lab_prereg.py`,
`test_lab_runner.py` and `test_lab_snapshot.py`, and `paper/roster.py`'s gate notes mention the old
threshold as history (`test_paper_roster.py` must stay green without editing those strings).

**Manual checks:**

1. `python -m seer_engine lab reevaluate` prints `luck bar: DSR >= 0.90`, `N = 110`, and
   `M0022: rejected -> dev-eligible  (M0022-W-TV14, M0022-W-TV16)`; running it again prints
   `0 method(s) moved`.
2. `python -m seer_engine lab promote M0022 --dir /tmp/prereg-smoke` succeeds and pre-registers
   **`M0022-W-TV14`** — the promotion path is reachable for the first time. Delete the scratch
   directory afterwards; **do not commit a pre-registration in this phase** (it is written by the
   owner when they choose to spend the look, and it needs phase 7's wording fix first — see
   Handoffs #2). Check `git status docs/lab/prereg/` is clean.
3. `python -m seer_engine lab status` renders, and the "Closest to eligible" table's `misses`
   counts do not jump (the `is_luck_label` fix). M0022's two variants must show `misses 0`.
4. **No reader compares against the live label by equality.** This must return nothing:

   ```
   grep -rn 'DSR_LABEL' engine/src | grep -E '==|!=|\bin \b' | grep -v 'is_luck_label'
   ```

   The only legitimate uses of `DSR_LABEL` are *writing* it (`runner.trial_rows`, the analysis
   text, `prereg.gate_text`) and its one definition.
5. `sqlite3 lab/lab.sqlite "SELECT count(*) FROM trials WHERE window='test'"` prints `0`.
6. `git status --porcelain` lists exactly the allowlist above and nothing else.

**Exit criteria:**

- `store.DSR_MIN == 0.90`, cited to the owner and dated 2026-10-07; `store.DSR_LABEL` derives from
  it; `store.is_luck_label` still recognises the `"DSR >= 0.95"` on all 110 recorded rows.
- **A recorded `failed` of `"DSR >= 0.95"` yields zero owner misses under `DSR_MIN = 0.90` and is
  re-judged on the luck test alone** — `test_a_recorded_095_label_is_read_as_zero_owner_misses`.
  No reader anywhere recognises the luck label by equality with the live constant; `grep -n
  'DSR_LABEL' engine/src` shows only writes of it and the one definition.
- **A recorded `failed` of `"max DD <= 15%"` does not freeze a trial at the 15% bar.**
  `store.owner_failures` takes the **trial row** and re-derives the four threshold conditions from
  its recorded columns against `tuning.MAX_DRAWDOWN` / `tuning.MIN_PROFIT_FACTOR` /
  `dev._MIN_TRADES`; only `owner inputs` is carried from the string
  (`test_owner_failures_rederives_the_four_thresholds_and_carries_owner_inputs`,
  `test_a_recorded_15pct_drawdown_label_does_not_freeze_a_trial_at_15pct`). **Nothing in
  `store.py` parses a threshold condition out of a recorded `failed` string.**
- `store.OWNER_INPUTS_LABEL == dev.FAILURE_LABELS[-1]`, and it is the only D8 label with no number
  in it (`test_the_owner_inputs_label_is_the_one_dev_still_writes`).
- `Verdict.failed` is a `tuple[str, ...]`, owner conditions first in recorded order and the luck
  label last; `eligible == (failed == ())` always.
- `npolicy.effective_n` runs **once** per (database, policy, dev trial set), not once per method —
  `test_the_gate_is_resolved_once_per_dev_trial_set`.
- `store.DSR_POLICY == "all-trials"` and `store.gate(committed).n == 110 ==
  store.dev_trial_count(committed)` — only the threshold moved.
- **`store.verdict` evaluates every trial's DSR at the gate's current N**, by `store.dsr_at`'s two
  routes (exactly from `trial_moments`, or by inverting the recorded DSR), and never takes a
  recorded DSR at face value. The two routes agree to 1.3e-5 across all 56 trials with a recorded
  DSR (`test_the_two_routes_to_a_dsr_agree`).
- **Both routes deflate by `store.dev_sharpe_variance(conn)` — today's — never by the `var_trials`
  recorded beside the trial (Decision D12).** The variance is read once, above the branch, and
  `moments["var_trials"]` is not referenced anywhere in `dsr_at`
  (`test_dsr_at_deflates_by_todays_variance_not_the_one_recorded_beside_the_trial`). This decides
  a candidate: on the P7a seed rows the two differ by 2.0067e-04 against 2.3950e-04, which moves
  `F9-SPY200M70-MOM30` from 0.903053 to **0.856651**, across the 0.90 bar.
- **A trial whose DSR cannot be evaluated fails the luck test** — the same rule
  `runner.trial_rows` applies to a new trial. The 54 P7a seed rows are that set today; in
  particular `F9-SPY200M70-MOM30` passes all five owner conditions at the 20% bar and is still
  ineligible (`test_a_trial_with_no_evaluable_dsr_fails_the_luck_test`,
  `test_f9_the_one_seed_row_held_out_by_the_luck_test_alone`). After phase 9 gives it moments it
  stays ineligible at **0.8567**, on a luck test it received rather than on a data gap.
- **`F3-SEC-TOP3-6M-TREND` is the `owner inputs` case, not the NULL-DSR case**, and is ineligible
  independently of its luck test
  (`test_f3_stays_ineligible_on_owner_inputs_whatever_its_luck_test_says`).
- `store.best_dev_eligible` reads the derived verdict and keeps every clause of its contract.
- `("rejected", "dev-eligible")` exists and is taken only by `store.reevaluate_method`, only from
  `rejected`, and only for a trial that clears **all five** conditions at the bars in force —
  guarded independently in `verdict`/`owner_failures` and in `_blocking`. A recorded failure of
  `"max DD <= 15%; DSR >= 0.95"` is **not** a reason to refuse: both of those bars have moved
  (`test_reevaluate_does_move_a_method_the_moved_drawdown_bar_unblocks`).
- On the committed lab at (N = 110, `DSR >= 0.90`, `max DD <= 20%`): **M0022 and M0020 both move
  to `dev-eligible`**, exactly three trials are eligible — `M0022-W-TV14`, `M0022-W-TV16` and
  `M0020-W-NOSTOP` — `best_dev_eligible(conn, "M0022")` is **`M0022-W-TV14`** (MAR 0.857),
  `best_dev_eligible(conn, "M0020")` is **`M0020-W-NOSTOP`**, and **M0011 stays `rejected`**.
- The three near misses each fail for a different, named reason
  (`test_the_three_near_misses_that_still_do_not_qualify`): **`M0007-N20-RAW`** clears the new 20%
  drawdown bar at 19.6% but fails the luck test (recorded 0.914 at its recorded N = 85 — **0.898**
  re-evaluated at today's N = 110); **`M0019-RAW20-S25`** is outside even the new bar at 20.7%;
  **`M0001-TV10`** does not beat SPY TR. None of the three is excluded by a stale label.
- The recorded-column digest over all 110 rows is
  `166ae36bdc4425cebd7380b0187f9c21dc7726d502fe999bd7746e60bc974016` before and after; no
  `trials` row changed; `store.test_looks` is 0.
- Setting `DSR_POLICY = "all-trials"`, `DSR_MIN = 0.95` **and** `tuning.MAX_DRAWDOWN = 0.15`
  together reproduces `main`'s verdicts exactly — a test, not a claim
  (`test_the_old_bars_reproduce_todays_verdicts`).
- `pytest` green in `engine/`.

---

## Handoffs

1. **To the reconciler — settled, nothing outstanding.** The index's `### Phase 4` section now
   matches this file: `DSR_POLICY = "all-trials"`, `DSR_MIN` is this phase's to move, and
   `best_dev_eligible(M0022)` is **W-TV14**. Phase 4 is listed at **7 files**
   (`web/data/lab.json` and `lab/lab.sqlite` counted separately) and depends on **1, 2 and 8**.
   R1's phase list includes 5 (the D1b warning); **R5 is phase 8's alone**, though this phase is
   where its effect becomes visible.

2. **To phase 7 — `prereg.py` will misstate the bar, and it now matters immediately.**
   `prereg.promote_method` (`lab/prereg.py:481-497`) builds the pre-registration from the trial
   row's **recorded** `dsr` and `n_trials_at_run`. For `M0022-W-TV14` those are 0.9122 and 110 —
   correct today, by luck, because its recorded N *is* the gate's N. It stops being correct the
   moment any trial recorded at a different N is promoted. `gate_text()`
   (`lab/prereg.py:148-168`) picks up the new `DSR_LABEL` automatically (so it will say
   "DSR >= 0.90") but still hard-codes "with N = every dev trial in the lab", which is right only
   while `DSR_POLICY` is `all-trials`. Phase 7 owns both; the robust fix is:

   ```python
   v = store.verdict(conn, trial)
   # ...
   dsr=_fmt(v.dsr),
   n_trials_at_run=str(v.n),
   ```

   plus `gate_text()` naming `store.DSR_POLICY` and the N it resolved to. **M0022 is promotable the
   moment this phase lands, so this should land before the owner runs `lab promote` for real.**

3. **To phase 5 — four things, the first of them binding.**

   (a) **`_owner_misses` must delegate, not re-implement — and it must take the row.** Phase 5
   independently found the recorded-label defect and wrote its own prefix rule
   (`not f.startswith("DSR ")`) over the `failed` string. That rule is now wrong twice over: it is
   a second definition of a rule that lives in `store.py`, and reading conditions out of the
   string freezes every row at the 15% drawdown bar. Phase 5's helper must be exactly:

   ```python
   def _owner_misses(row) -> list[str]:
       """The five D8 conditions this trial misses at the bars in force now."""
       return list(store.owner_failures(row))
   ```

   and every call site must pass the **row**, not `row["failed"]`. This phase has already changed
   `misses()` to that call (Step 7e). `store.is_luck_label`, `store.recorded_labels` and
   `store.OWNER_INPUTS_LABEL` are exported for the readers that genuinely want the recorded
   history — phase 5's "which of these was the luck test?" display question is one of them.

   (b) **Resolve the gate once.** `best_dev_eligible` and `verdict` both take `at: Gate | None`.
   `lab status` should do `g = store.gate(conn)` once and pass `at=g` everywhere, rather than
   leaning on `store._GATE_CACHE` — the memo is an optimisation, `at=` is the guarantee.

   (c) The subcommand pairing — **settled, Decision D9.** The owner's call: this phase keeps the
   write path **`lab reevaluate`**, and phase 5's read-only command is renamed from `reeval` to
   **`lab luck`**. Two commands differing by two characters, one writing and one not, was a trap;
   `luck` is already this codebase's word for the DSR (the sera site's "Luck bar", the lab's
   "rejected on luck only", this plan set's own prose), so the rename costs no new vocabulary.
   **This phase renames nothing of its own.**

   (d) Decisions **D1b**'s closeness warning — "the best luck-only candidate is within 0.03 of the
   bar, and N≈200 would sink it" — is phase 5's, and is the thing that stops the next deadlock
   being found 110 trials late. `store.gate(conn)` and `store.verdict(conn, row, policy=...)` are
   what it needs; `Verdict.failed` is a `tuple[str, ...]` and `Verdict.dsr` is `float | None`.

4. **To phase 7 — the web, which this phase has already half-changed.** `store.snapshot()` emits
   `"dsrMin": DSR_MIN`, so re-staging in Step 10 puts `0.90` into `web/data/lab.json`. The web's
   own fixtures and tests still assert `0.95`: `web/lib/sera/fixture.ts:8`,
   `web/app/sera/overview.test.ts:90` and `:250`. Those are phase 7's to update, along with
   `web/app/sera/overview.ts:321-330` and `web/app/sera/how/view.ts:97,202`, which read `dsrMin`
   from the snapshot and need no change but should gain the policy and N. `web/data/lab.json` is
   regenerated by both phases — resolve any merge conflict by re-running `lab stage`, never by
   hand.

5. **To phase 7 — the snapshot still publishes the frozen `eligible` and `dsr`.**
   `_snapshot_trial` (`store.py:765-795`) emits them from the recorded columns, so the site will
   show a `dev-eligible` M0022 all of whose trials read `eligible: false` and `failed: ["DSR >=
   0.95"]`. `store.verdict` gives phase 7 a per-trial derived verdict if it wants one, and
   `store.gate(conn)` gives it the `policy`/`n` for the `gate` block. This phase deliberately stays
   out of `snapshot()`. `engine/src/seer_engine/backtest/dev_report.py:717` ("Values below 0.95 do
   not clear the usual bar") is also now wrong and is phase 7's wording to fix.

6. **To phase 6 — do not retro-edit the roster's gate notes.** `paper/roster.py:569, 624, 644`
   contain the strings `"DSR >= 0.95 (0.006)"`, `"DSR >= 0.95 (0.897 at N=90)"` and
   `"DSR >= 0.95 (0.916 at N=110)"`. Those are statements about the bar **in force when the entry
   was admitted** and are correct history; changing them to 0.90 would falsify the record. Phase
   6's `lab_provenance` is the right place to say that M0022 has since become `dev-eligible` at the
   lowered bar, and that M0011 has not.

7. **To phase 3 — the reconstruction in `_reconstruct_moments` is not a backfill.** It pins
   `skew = 0`, `kurt = 3` and solves for `t`, which lands near 4,800 for a window of about 3,970
   sessions. It exists so this phase can be tested without a research store. `lab remeasure`
   measures the real values, and phase 3's exit criterion (reproducing each recorded `dsr` to 1e-6
   at the recorded N) is the stronger check. **After phase 3 runs, M0011's three verbatim trials
   become exactly recomputable rather than recovered** — and at N=110 they are 0.884, still
   below 0.90, so M0011 stays
   `rejected`. That is worth a test in phase 3.

8. **Not done, on purpose:** no `insights` row is appended by `reevaluate_method` (the phase scope
   asks only for `analysis`); `store.summary_rows`, `LEADERBOARD_SQL` and `export_xlsx` keep
   reading the recorded columns; no pre-registration file is written or committed.

9. **To phase 7 — `derive.ts` has the drawdown version of the same bug, and it is new.**
   `web/lib/sera/derive.ts:19` hard-matches `drawdown: 'max DD <= 15%'` against `trial.failed`.
   After phase 8 the engine writes `max DD <= 20%`, and that literal match reads a *missed*
   drawdown as a **pass** — the same silent green tick phase 7's `DSR_FAILURE_PREFIX` exists to
   prevent, on the same page, one row down. Phase 7 owns `derive.ts` and must match this label by
   prefix too (`'max DD <= '`). Its Step 9 guard and Step 14 data pin both extend to cover it.
   **The site is a display of the recorded string and is allowed to stay a display** — it shows
   what the lab said on the day — but "said it missed" and "said nothing" must not be confused.

10. **To phase 9 — the NULL-DSR rule is a rule, not a verdict on two particular rows.**
    `verdict` fails the luck test for any trial whose DSR cannot be evaluated, which today is the
    54 P7a seed rows (`seed.py:136`). Phase 9 (Decision **D7**, the owner's call) re-runs those
    methods to recover their moments, after which `dsr_at` takes route 1 and each gets a real
    luck verdict. **Nothing in this phase needs to change for that**, and phase 9 must not ask it
    to: the rule stays, and phase 9 simply stops it applying to rows that now have something to
    evaluate. Two things this phase needs back from phase 9:

    - **Invariant 7 — remeasuring must not move N.** The 54 are already inside
      `dev_trial_count`, so recovering their moments must add `trial_moments` rows and **never** a
      `trials` row. If N rose, the gate would re-tighten on everyone and the exercise would undo
      itself. `store.gate`'s memo key is `(path, policy, dev row count, max n, distinct methods)`,
      so a `trial_moments` insert correctly does **not** invalidate it — which is right, and also
      the reason a `trials` insert would be caught.
    - `test_the_two_seed_rows_the_drawdown_change_exposes_stay_ineligible` skips itself once those
      rows have moments, so phase 9 does not break it by running.

11. **To phase 8 — this phase reads `tuning.MAX_DRAWDOWN`, never writes it.**
    `store.owner_failures` and `store._blocking` both import `tuning` locally and compare against
    it at call time, so phase 8's change reaches every recorded trial on the next evaluation with
    no data change — exactly as `DSR_MIN` does. Phase 8 owns the constant, `dev.FAILURE_LABELS`'s
    drawdown entry, `tuning._GATE_NAMES`, `web/lib/metrics.ts` and design §1 item 4. Two things
    this phase needs from it: the label must stay **prefix-stable** (`"max DD <= "` + the number,
    so historical readers can recognise it), and `dev.FAILURE_LABELS` must keep its **five
    entries in order**, since `owner_failures` unpacks it positionally.

---

## Rollback

**This phase alone, as code:** `git revert <phase-4 commit>`. It restores `DSR_MIN = 0.95`, the old
`DSR_LABEL`, the old `TRANSITIONS`, the old `best_dev_eligible` and `trial_rows`, and removes
`lab reevaluate`. `lab/lab.sqlite` and `web/data/lab.json` are in the same commit, so the revert
restores both — including M0022's `rejected` status.

**Without reverting, if the threshold turns out to be wrong:** set `store.DSR_MIN = 0.95` (and
`DSR_LABEL` follows automatically). That is the whole rollback of the *decision*. It needs no data
change, because every recorded column was preserved and the verdict is read at call time;
`test_all_trials_at_095_reproduces_todays_verdicts` is the proof it lands exactly where the lab is
on `main`.

**If N also turns out to be wrong later:** set `store.DSR_POLICY = "methods"`. One constant, no
migration, and phase 5's `lab luck` shows what it would do first.

**M0022, once it has moved:** it can be left where it is. Its trials never changed, its analysis
says under which threshold, policy and N it moved, and a revert of the commit puts the database
back. Moving it back by hand is *not* possible and is not supposed to be: status moves forward
only, and the fix for a method that should not have moved is a verdict
(`lab note M0022 --verdict "..."`) and a refusal to promote it, not an erasure.

**The binaries on their own, after the set has merged:**
`git checkout origin/main -- lab/lab.sqlite web/data/lab.json`, as a separate step from any merge
revert. The `trial_moments` table left behind by a code-only revert is unread and harmless.

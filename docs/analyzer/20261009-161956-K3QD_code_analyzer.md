# Code Analysis: `lab promote` — the hard gate (walk-forward phase 4)

**Type:** Feature Implementation
**Date:** 2026-10-09 16:19:56 +07
**Session ID:** 20261009-161956-K3QD
**Plan:** `docs/plans/LAB_HARD_GATE_PLAN.md` (3 phases)
**Worktree:** `/home/miftah/.worktrees/seer/lab-hard-gate`, branch `feature/lab-hard-gate` (base `origin/main` @ `7708350`)

---

## User Input

### Original User Request

> Phase 4 of docs/plans/WALK_FORWARD_EVALUATION_PLAN.md — the hard gate. Read the 'Phase 4 — the
> hard gate' section of that plan first; it is the brief and it carries the owner's decision, the
> four open questions you must answer rather than assume, and the context you will not guess. Make
> lab promote refuse a method unless it wins a majority of walk-forward folds
> (lab/walkforward.py Record.majority) and no other method in its family reads test-failed.

### User-Provided Context

The brief is `docs/plans/WALK_FORWARD_EVALUATION_PLAN.md`, section **Phase 4 — the hard gate**,
committed on main at `7708350`. Its load-bearing content, carried here verbatim in substance:

- **The rule.** `lab promote` refuses unless **(F)** the method beat the recorded SPY benchmark in
  a majority of its scoreable walk-forward folds (`lab/walkforward.py` `Record.majority`) **and**
  **(K)** no other method in the same `family` reads `test-failed`.
- **Decided 2026-10-09 by the owner, after seeing what it costs.** It blocks promotions. "That is
  the intended effect, not a side effect... If this proves too strict in practice the answer is a
  recorded, argued change to the rule — **not an override path**, which is precisely the mechanism
  that produced the 0-for-5 roster in the first place."
- **Why at promote and not at test.** `promote` is where the lab commits; `promoted` has only two
  exits, both final. Refusing at `lab test` would strand a method in a state it can never leave.
- **What the pre-registration must record:** the folds won and scored, whether the pick was stable
  across folds, and the family's state at promotion.
- **Four open questions the implementer must answer, not assume** (see Requirement IDs below).
- **Also update, or the gate is invisible until it bites:** the explore skill's Promotion step 0b,
  `sera-the-explorer`'s promotion path and Never table, and `lab status`.
- **Tests this phase is not done without:** majority + clean family promotes (**the existing
  promote tests must still pass unchanged**); losing folds refuses, naming the record; a
  `test-failed` family member refuses, naming the member; too few scoreable folds refuses; and the
  refusal happens **before** the pre-registration file is written and before any status moves — a
  refused promote must leave the repository and database byte-identical.
- **Context the implementer needs and will not guess:** five out-of-sample results, five failures;
  the fold detector flags three of the four recorded failures and misses M0029; a funded curve must
  be de-funded before it is measured (`regime.defunded`), and every trial from M0032 on is funded;
  `backtest/walkforward.py` is a **different module** (P3b's anchored walk-forward for Strategy A2)
  — do not edit it.

### User-Provided Files

None marked with `@`. The brief named these, and all were read:

- `docs/plans/WALK_FORWARD_EVALUATION_PLAN.md`
- `engine/src/seer_engine/lab/walkforward.py`
- `engine/src/seer_engine/commands/lab.py`
- `engine/src/seer_engine/lab/prereg.py`
- `engine/src/seer_engine/lab/store.py`
- `engine/tests/test_lab_prereg.py`, `tests/test_lab_walkforward.py`, `tests/labkit.py`
- `.claude/skills/explore-and-experiment-new-method/SKILL.md`
- `.claude/skills/sera-the-explorer/SKILL.md`

### Requirement IDs

| ID | What the user asked for |
|---|---|
| **R1** | `lab promote` refuses a method unless it wins a majority of its walk-forward folds (`Record.majority`) **and** no other method in its family reads `test-failed`. The refusal must land before the pre-registration file is written and before any status moves. |
| **R2** | Answer open question 1 — **fail closed on thin evidence**: decide the minimum number of scoreable folds and say why in the code. |
| **R3** | Answer open question 2 — **is (K) evaluated at promote time only?** Decide whether `lab test` re-checks it or honours the pre-registration as written, and say which was chosen. |
| **R4** | Answer open question 3 — **does (K) look at ancestry as well as `family`?** Decide whether to walk `parent_id` too. |
| **R5** | Answer open question 4 — **is there any path back?** Do not invent one in this phase; note whether it will be needed. |
| **R6** | The pre-registration records the folds won and scored, whether the pick was stable, and the family's state at promotion. |
| **R7** | `lab status` shows the fold record beside the dev-eligible list, so "why can nothing be promoted" is answerable without a second command. |
| **R8** | `explore-and-experiment-new-method` Promotion step 0b says the gate **refuses**, not advises. |
| **R9** | `sera-the-explorer`'s promotion path and Never table say the same. |

---

## Detailed Requirements Understanding

**Problem/Requirement Statement.** The lab's promotion path today is
`dev-eligible -> promoted -> test-passed -> paper`, and the only thing standing between a method
and a counted test-window look is the dev gate (five P7a D8 conditions plus `DSR >= 0.90`
deflated at the `methods` N). That gate has now been wrong five times out of five. Phases 1-3 of
the walk-forward plan built the evidence that would have caught three of those four recorded
failures — `lab/walkforward.py`, `lab walkforward` — but it is a **report**: nothing reads it, and
`lab promote` will happily pre-register a method that lost three of its four folds and whose own
sibling already failed out of sample. Phase 4 turns the report into a refusal.

**Success Criteria.**

1. `python -m seer_engine lab promote MNNNN` exits 2 with a `store.LabError` naming the fold
   record, or the failed kin, when (F) or (K) does not hold — and writes nothing anywhere.
2. A method that clears both still promotes exactly as it does today; **all 29 existing tests in
   `test_lab_prereg.py` pass unchanged**.
3. The four open questions are answered *in the code*, each with the reason beside it.
4. The pre-registration a passing promotion writes carries the fold record and the family state.
5. `lab status`, the explore skill and the Sera skill say the gate refuses, with the fold record
   visible beside the dev-eligible list.

**Key Considerations.**

- **The existing-tests constraint decides where the gate lives.** `test_lab_prereg.py`'s fixtures
  insert trials with `curve_json="[]"` and no `REF-SPY-HOLD` row (`tests/test_lab_prereg.py:71-83`).
  A gate inside `prereg.promote_method` would refuse every one of them — `evaluate` raises
  `ValueError` on `min()` of an empty curve before it even gets to the missing benchmark. So the
  gate cannot live inside `promote_method`. See Decision D1 in the plan.
- **De-funding is not optional.** `_trial_deposits` (`commands/lab.py:1656`) reconstructs each
  funded trial's deposit series and `regime.bucket`s it; `walkforward.measure` then calls
  `regime.defunded` before cutting. Any new caller that skips this reads the owner's 5,000,000
  IDR/month as edge — insight 72/75, and the measured error was seventy to eighty points a year.
- **Report only, and fast.** The gate opens no research store and runs no backtest. It is two
  SQL reads and arithmetic on curves already in `trials.curve_json`.
- **The four committed pre-registrations must keep parsing.** `docs/lab/prereg/` holds M0002,
  M0021, M0022 and M0029, all written before this gate existed, and `prereg.parse` refuses a file
  missing any key in `FIELDS`. Adding two *required* fields would invalidate four records whose
  entire value is that they were committed first — and the module's central rule is that a
  pre-registration is **never rewritten**, so they cannot be migrated.

---

## Analysis Scope

### Explicitly Mentioned Files

- `engine/src/seer_engine/lab/walkforward.py` — `Record.majority`, named in the request
- `engine/src/seer_engine/commands/lab.py` — `lab promote`

### Discovered Related Files

| File | How it was reached |
|---|---|
| `engine/src/seer_engine/lab/prereg.py` | `commands/lab.py:1160` — `_promote` delegates to `prereg.promote_method` |
| `engine/src/seer_engine/lab/store.py` | `methods` schema (`family`, `parent_id`, `status`), `TRANSITIONS`, `best_dev_eligible`, `LabError` |
| `engine/src/seer_engine/backtest/regime.py` | `BENCH_CANDIDATE`, `bucket`, `defunded` — imported by both `walkforward.py` and `_walkforward` |
| `engine/src/seer_engine/lab/runner.py` | `recorded_contributions` (deposit schedule), `preflight_test` (where a `lab test` re-check would have gone) |
| `engine/tests/test_lab_prereg.py` | the 29 tests that must pass unchanged |
| `engine/tests/test_lab_walkforward.py` | 25 tests; the `Record`/`buy_signal` contract |
| `engine/tests/test_lab_status.py` | `lab status` output assertions |
| `.claude/skills/explore-and-experiment-new-method/SKILL.md` | Promotion step 0b, lines 191-227 |
| `.claude/skills/sera-the-explorer/SKILL.md` | promotion path (line 83-89), buy signal (105-113), Never table (127-140) |
| `engine/package_readme.md` | the lab package map and `prereg` API block |
| `docs/lab/prereg/{M0002,M0021,M0022,M0029}.md` | four committed records that must keep parsing |

---

## Current Dataflow

### Entry Point: `lab promote MNNNN`

**Location:** `engine/src/seer_engine/commands/lab.py:1148` (`_promote`), registered at `:2007`
**Trigger:** `python -m seer_engine lab promote M0007`; argparse at `:171-180` gives `method` and
`--dir`
**Input:** `args.db` (default `lab/lab.sqlite`, overridable by `SEER_LAB_DB`), `args.method`,
`args.dir`
**Validation today:** none in the handler. Every refusal is inside `prereg.promote_method`.
**Next step:** `prereg.promote_method(conn, args.method, git_sha=..., directory=...)` at `:1161`

### Processing Chain

1. **`prereg.promote_method()`** — `lab/prereg.py:455`
   - `store.begin_immediate(conn)` — the status read, the file write and the transition, atomic
   - refuses when: no such method; status not in `("dev-eligible", "promoted")`;
     `store.best_dev_eligible` returns None; `check_source` finds the method file changed
   - builds `Prereg` from the **recorded dev trial row**, never from the live method file
   - writes `docs/lab/prereg/MNNNN.md` (`render`), **then** `store.update_method(status='promoted')`
     and `store.append_analysis` + `store.add_insight`, in that order, inside one transaction
   - **the file write is deliberately not rolled back by the transaction** — a crash must leave a
     stranded file, never a `promoted` method with nothing pre-registered
   - returns `Promotion(prereg, path, trial_n, status, wrote_file, moved_status)`
2. **`_promote` prints** the candidate, digest, dev window, gate line and the `git add` / `lab test`
   next steps (`:1167-1182`)

### The evidence the gate needs, and where it already exists

**`lab walkforward`** — `commands/lab.py:1787` (`_walkforward`), registered at `:2003`:

```
rows   = SELECT n, method_id, candidate_id, start, end, curve_json
         FROM trials WHERE window = 'dev' AND curve_json IS NOT NULL
bench  = the row whose candidate_id is regime.BENCH_CANDIDATE ('REF-SPY-HOLD')
folds  = wf.folds([d for d, _v in bench_curve])          # 4 on the dev window
per method:
    curves = {candidate_id: curve}                        # every dev trial of that method
    deps   = {candidate_id: _trial_deposits(conn, row, curve)}
    rec    = wf.Record(mid, wf.evaluate(curves, bench, folds, deps))
    kin    = SELECT id FROM methods
             WHERE family = ? AND id != ? AND status = 'test-failed' ORDER BY id LIMIT 1
    signal, why = wf.buy_signal(eligible, rec, edge, kin)
```

Everything (F) and (K) need is in those nine lines. **(K) is already implemented there**, family-only,
as the buy signal's fourth condition (`walkforward.buy_signal`'s `family_failed` argument).

**`_trial_deposits`** — `commands/lab.py:1656`. Private to the command module today, and the only
correct way to build the deposit series:

```
schedule = runner.recorded_contributions(conn, trial_n)     # None for a lump-sum trial -> {}
unit     = schedule.amount_idr / INITIAL_IDR                # 0.5 for the owner's 5M on a 10M start
due      = schedule.dates_in(start, end)  ->  next NYSE session for each
cross-check: len(due) == trial_funding.deposits_n, else LabError (the schedule moved)
return regime.bucket(curve, credited)
```

**`walkforward.Record`** — `lab/walkforward.py:213`:
- `scored` — the folds where `beat is not None`
- `won` — how many of those the pick out-returned the benchmark on
- `majority` — `n > 0 and won * 2 > n`  ← what R1 names
- `stable` — the training slice kept choosing the same variant
- `summary()` — `"3 of 4 folds"`, or `"2 of 4 folds, pick changed"`, or `"no fold could be scored"`

### Data Persistence

**Database** `lab/lab.sqlite` — `methods` (`family TEXT NOT NULL`, `parent_id TEXT REFERENCES
methods(id)`, `status` in nine values, forward-only via the `transitions` table),
`trials` (append-only, `curve_json TEXT NOT NULL`), `trial_funding` (`deposits_n`, `schedule`).

**Files** `docs/lab/prereg/MNNNN.md` — one per promoted method, written once, never rewritten,
and required to be committed before `lab test`.

### Exit Points

- exit 0 and a pre-registration on disk with the method at `promoted`
- exit 2 on any `store.LabError` (`commands/lab.py:366-368`) — this is the gate's exit
- exit 1 on anything else

---

## Key Data Structures

### `Record` — `engine/src/seer_engine/lab/walkforward.py:213`
`method: str`, `picks: tuple[FoldPick, ...]`. Properties `scored`, `won`, `majority`, `stable`,
`summary()`. Pure; built by `evaluate(curves, bench, folds, deposits)`.
**Used in:** `commands/lab.py:_walkforward:1850`, `walkforward.buy_signal`.

### `Prereg` — `engine/src/seer_engine/lab/prereg.py:76`
Fifteen `str` fields; `FIELDS` is derived from them. `parse(render(p, name)) == p` exactly, and
`parse` refuses a missing, unknown or repeated key. **Four committed files on disk carry the
current fifteen and no more.**
**Used in:** `promote_method`, `require_committed` (the `lab test` gate), `_test_plan`.

### `methods` row
`id, name, family, parent_id, source_kind, source_ref, hypothesis, status, analysis, verdict,
blocked_on, source_sha, created, updated`. `family` is a free string; `parent_id` is a real foreign
key and forms a forest.

---

## Dependencies

### Configuration / Environment
- `SEER_LAB_DB` — parallel Sera sessions share one database through it (`store.py:68`)
- `store.DSR_MIN = 0.90`, `store.DSR_POLICY = "methods"` — the dev gate; untouched by this phase
- `walkforward.MIN_TRAIN_YEARS = 10`, `EVAL_YEARS = 3`, `MIN_EVAL_MONTHS = 12` — the fold geometry
- `regime.BENCH_CANDIDATE = "REF-SPY-HOLD"`
- `config.REPO_ROOT = Path(__file__).resolve().parents[3]` — resolves to the worktree inside a
  worktree, so `docs/lab/prereg/` is the worktree's copy

### External Services
None. The gate opens no research store, makes no network call and runs no backtest.

---

## Measurements taken for this analysis

All taken on a **copy** of `lab/lab.sqlite` in the scratchpad, so the committed database was never
opened by a lab command (`lab` migrates on connect — even a read dirties the file).

### Baseline

`tests/test_lab_prereg.py`, `tests/test_lab_walkforward.py`, `tests/test_lab_status.py`:
**68 passed in 8.99s** at `7708350`.

### The lab today (63 methods; 7 dev-eligible, 4 test-failed)

`test-failed`: **M0002** (`stock-momentum-risk-managed`), **M0021** (`stock-multi-factor-blend`),
**M0022** (`stock-residual-momentum`), **M0029** (`stock-multi-factor-blend`).

`python -m seer_engine lab walkforward` on the copy — every dev-eligible method, against both
candidate kin rules:

| method | family | folds won | stable | (F) majority | (K) family | (K) family ∪ ancestors |
|---|---|---|---|---|---|---|
| M0007 | stock-residual-momentum | 3 of 4 | yes | **pass** | fail (M0022) | fail (M0022) |
| M0011 | stock-residual-momentum | 2 of 4 | yes | **fail** | fail (M0022) | fail (M0022) |
| M0019 | stock-momentum-risk-managed | 3 of 4 | no | **pass** | fail (M0002) | fail (M0002) |
| M0020 | stock-momentum-risk-managed | 3 of 4 | yes | **pass** | fail (M0002) | fail (M0002) |
| M0024 | stock-seasonality | 2 of 4 | yes | **fail** | pass | pass |
| M0030 | stock-core-satellite | 2 of 4 | yes | **fail** | **pass** | **fail (M0021, M0029)** |
| M0033 | stock-residual-momentum | 3 of 4 | yes | **pass** | fail (M0022) | fail (M0022) |

**The brief's cost statement is stale in its details and right in its conclusion.** It says "Every
dev-eligible method -- M0007, M0019, M0020, M0033 -- is in a family that has already failed the
test window, so every one fails (K)." The lab has moved since: M0011, M0024 and M0030 are also
dev-eligible now, and **M0024 and M0030 pass (K) on family alone**. The conjunction still refuses
all seven — M0024 and M0030 fail **(F)** at 2 of 4 — so "it blocks every promotion in the lab as of
today" holds, but the reason set is split, and only the conjunction gets there. This is exactly the
staleness the brief warns about in its own "Picking this up" section, and it is why the plan's
Decision D8 records the measurement rather than the prose.

**M0030 is the live case for open question 3.** Its family (`stock-core-satellite`) is clean; its
parent M0029 and grandparent M0021 are both `test-failed`. Family-only (K) would let it through the
moment it wins a third fold.

### Kin rules, measured across all 63 methods

| rule | blocks | note |
|---|---|---|
| `family` only | 26 of 63 | the brief's literal rule; misses M0030 |
| transitive **ancestors** via `parent_id` only | 10 of 63 | misses M0007, M0019, M0020, M0033 |
| **`family` ∪ transitive ancestors** | 29 of 63 | catches all seven dev-eligible methods |
| full connected component of the `parent_id` graph | 36 of 63 | one **26-method blob**; would refuse M0019 on account of M0021, a multi-factor blend four hops away in another family |

Methods clean under `family ∪ ancestors` include M0034 and M0035 (both 3 of 4 folds, parent M0032
is `rejected` not `test-failed`), so the rule is not "nothing ever moves again".

### Scoreable fold counts

The fold geometry is cut from the **benchmark** curve, so it is global: `REF-SPY-HOLD` spans
1993-02-01..2015-10-16 and yields **4 folds** (eval slices 2003-01-31 → 2014-12-31). Every `M*`
method in the lab has a dev curve spanning 1996-01-03..2015-10-16 and is scoreable on all 4.
The one method with fewer is `H-P7A-F10` (curve starts 2007-04-10, **2 scoreable folds**) — a
`rejected` seed method that `lab promote` can never reach, but proof that the thin case is real.

### Why a strict majority is weakest at an odd fold count

Under a coin-flip null (a bound, not a p-value — the brief forbids treating overlapping folds as
independent observations):

| scoreable folds | P(strict majority \| coin flip) |
|---|---|
| 1 | 0.5000 |
| 2 | 0.2500 |
| **3** | **0.5000** |
| **4** | **0.3125** |
| 5 | 0.5000 |
| 6 | 0.3438 |

A strict majority of an *odd* count is a coin flip, every time. This is the measurement that
decides open question 1: the minimum cannot be "3 or more", because 3 is strictly weaker evidence
than 4 and no stronger than 1.

---

## Reference List

Every site that touches what this phase changes.

| Symbol / key | File:line | Kind | Package |
|---|---|---|---|
| `_promote` | `engine/src/seer_engine/commands/lab.py:1148` | def | `commands` |
| `"promote": _promote` | `engine/src/seer_engine/commands/lab.py:2007` | dispatch | `commands` |
| `promote` subparser | `engine/src/seer_engine/commands/lab.py:171-180` | config | `commands` |
| `lab promote` help block | `engine/src/seer_engine/commands/lab.py:16-18` | doc | `commands` |
| `prereg.promote_method` | `engine/src/seer_engine/lab/prereg.py:455` | def | `lab` |
| `prereg.promote_method` | `engine/src/seer_engine/commands/lab.py:1161` | call (the **only** production call site) | `commands` |
| `Prereg` / `FIELDS` | `engine/src/seer_engine/lab/prereg.py:76-99` | def | `lab` |
| `prereg.render` | `engine/src/seer_engine/lab/prereg.py:200` | def | `lab` |
| `prereg.parse` | `engine/src/seer_engine/lab/parse` → `prereg.py:245` | def | `lab` |
| `prereg.require_committed` | `engine/src/seer_engine/lab/prereg.py:300` | def (the `lab test` gate) | `lab` |
| `runner.preflight_test` | `engine/src/seer_engine/lab/runner.py:494` | def (where a `lab test` re-check would go — **R3 says it does not**) | `lab` |
| `walkforward.Record` | `engine/src/seer_engine/lab/walkforward.py:213` | def | `lab` |
| `walkforward.Record.majority` | `engine/src/seer_engine/lab/walkforward.py:226` | def | `lab` |
| `walkforward.evaluate` / `folds` / `measure` / `pick` | `engine/src/seer_engine/lab/walkforward.py:103-211` | def | `lab` |
| `walkforward.buy_signal` | `engine/src/seer_engine/lab/walkforward.py:261` | def (already carries the family check) | `lab` |
| `_walkforward` | `engine/src/seer_engine/commands/lab.py:1787` | def (the fold/benchmark/deposit reader to extract from) | `commands` |
| `_trial_deposits` | `engine/src/seer_engine/commands/lab.py:1656` | def (needed by the gate; private today) | `commands` |
| `_trial_deposits` | `engine/src/seer_engine/commands/lab.py:1741` (`_regime`), `:1852` (`_walkforward`) | call | `commands` |
| `regime.BENCH_CANDIDATE` | `engine/src/seer_engine/backtest/regime.py:42` | const | `backtest` |
| `regime.defunded` / `regime.bucket` | `engine/src/seer_engine/backtest/regime.py:190`, `:174` | def | `backtest` |
| `_promotable_now` | `engine/src/seer_engine/commands/lab.py:834` | def (**R7** lands here) | `commands` |
| `_promotion_path` | `engine/src/seer_engine/commands/lab.py:882` | def | `commands` |
| `_empty_reason` | `engine/src/seer_engine/commands/lab.py:804` | def | `commands` |
| `store.get_method` | `engine/src/seer_engine/lab/store.py:554` | def | `lab` |
| `store.best_dev_eligible` | `engine/src/seer_engine/lab/store.py:839` | def | `lab` |
| `store.LabError` | `engine/src/seer_engine/lab/store.py:400` | def (exit 2) | `lab` |
| `methods.family` / `methods.parent_id` / `methods.status` | `engine/src/seer_engine/lab/store.py:291-306` | schema | `lab` |
| `test_lab_prereg.py` (29 tests) | `engine/tests/test_lab_prereg.py` | test (**must pass unchanged**) | `tests` |
| `_trial(... curve_json="[]")` | `engine/tests/test_lab_prereg.py:82` | test fixture (why the gate cannot live in `promote_method`) | `tests` |
| `test_lab_walkforward.py` (25 tests) | `engine/tests/test_lab_walkforward.py` | test | `tests` |
| `test_lab_status.py` | `engine/tests/test_lab_status.py` | test | `tests` |
| Promotion step 0b | `.claude/skills/explore-and-experiment-new-method/SKILL.md:191-227` | doc (**R8**) | skills |
| promotion path / buy signal / Never table | `.claude/skills/sera-the-explorer/SKILL.md:83-89`, `:105-113`, `:127-140` | doc (**R9**) | skills |
| lab package map; `prereg` API block | `engine/package_readme.md:145`, `:2543-2560` | doc | `engine` |
| `docs/lab/prereg/{M0002,M0021,M0022,M0029}.md` | 4 files | committed record (**must keep parsing**) | docs |
| `backtest/walkforward.py` | `engine/src/seer_engine/backtest/walkforward.py` | **do not edit** — P3b's anchored walk-forward for Strategy A2 | `backtest` |

---

## Impact Points (files that WILL need changes)

1. **`engine/src/seer_engine/lab/hardgate.py`** (new) — the rule: fold record, kin, the refusal,
   and the one-line summary everything else prints. Owned by **phase 1**.
2. **`engine/src/seer_engine/commands/lab.py`** — `_promote` calls the gate before
   `prereg.promote_method`; `_trial_deposits` moves into `hardgate` and `_regime`/`_walkforward`
   call it there; the module help block says `promote` refuses. Owned by **phase 1**. Phase 2 adds
   two printed lines to `_promote`; phase 3 adds the fold record to `_promotable_now`. Shared file,
   disjoint functions, strictly sequential — see the plan's Scope note.
3. **`engine/src/seer_engine/lab/prereg.py`** — two new `FIELDS` with a documented legacy default so
   the four committed files still parse; `render` states the fold record and family state.
   Owned by **phase 2**.
4. **`engine/tests/test_lab_hardgate.py`** (new) — the gate's own tests. **Phase 1**.
5. **`engine/tests/test_lab_prereg.py`** — *additions only*, for the new fields and the four
   committed files; every existing test is left byte-identical. **Phase 2**.
6. **`engine/tests/test_lab_status.py`** — the fold record in the promotion path. **Phase 3**.
7. **`.claude/skills/explore-and-experiment-new-method/SKILL.md`** — step 0b. **Phase 3**.
8. **`.claude/skills/sera-the-explorer/SKILL.md`** — promotion path and Never table. **Phase 3**.
9. **`engine/package_readme.md`** — the lab package map and the `prereg`/`hardgate` API blocks.
   **Phase 3**.
10. **`docs/plans/WALK_FORWARD_EVALUATION_PLAN.md`** — phase 4 marked done, and its stale cost
    paragraph corrected against the measurement above. **Phase 3**.

**This document describes. The plan files prescribe.**

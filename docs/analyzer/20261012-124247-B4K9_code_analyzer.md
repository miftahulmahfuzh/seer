# Code Analysis: the brakes-off variants (§4.1) and the shared SPY 200-day gate (§4.2)

**Type:** Feature Implementation (with one Feature Update to the lab's pre-registration rules)
**Date:** 2026-10-12 12:42:47 +07
**Session ID:** 20261012-124247-B4K9
**Plan:** `docs/plans/LAB_BRAKES_AND_GATE_PLAN.md` (6 phases)
**Worktree:** `/home/miftah/.worktrees/seer/lab-brakes-and-gate`, branch `feature/lab-brakes-and-gate` (base `origin/main` @ `d3c1ec4`)

---

## User Input

### Original User Request

> docs/plans/HANDOVER_20261012-the-hurdle-counts-methods.md
>
> Read the whole handover first, then plan and build §4.1 and §4.2: the brakes-off variants on
> M0030 and M0053 that the exposure diagnostic found carry the only post-2009 edge in the grid,
> and the interrogation of the shared SPY 200-day gate that §2 showed is nearly all one year of
> value and a drag since 2009.
>
> The hard constraint is §3: the luck gate N is 74 under the methods policy, so these must be
> VARIANTS of the existing method files (free in N) and not new method ids. Verify that with
> store.pending_gate before you commit to a shape. Hold the usual lab rules: pre-register by
> committing the method file before lab run, lab stage for any database commit, Postgres for DB
> tests, no hard-gate override, and never touch the test window.
>
> Do not act on §5.1 (the ten Lab N strings in commands/lab.py) -- that is the owners decision,
> not yours. Surface it, do not fix it.

### User-Provided Context

The handover `docs/plans/HANDOVER_20261012-the-hurdle-counts-methods.md`, read in full. The
sections that bind this work:

- **§2** — the five live books are far less independent than five method ids suggest.
  `empty_share` came back bit-identical at 67/237 (28.3%) across four of them because they share
  one SPY 200-day gate read on the same monthly dates. That single gate produced the **+34.8
  2008 lead for every book**. The lab's own recorded control prices it: gated **+2.7/yr**
  whole-window vs ungated **+1.0**, but after 2009 the gated version **trails by 5.4** while the
  ungated one **leads by 1.5**.
- **§3** — `store.gate(conn)` → N = 74, policy `methods`; `store.dev_trial_count` → 354 rows;
  `pending_gate` on an existing method → 74 (free); on a brand-new method → 75 (+1,
  retroactively, for all 130 methods).
- **§4.1** — the diagnostic's `-FULL` arm found the only post-2009 edge in the grid:
  **M0030 +2.7** and **M0053 +0.5** a year from 2009. Those arms are diagnostic columns, not
  methods the lab holds.
- **§4.2** — the gate is a shared component across the roster, so changing it moves every book
  at once. "The highest-leverage item on the board, and a variant-level question — free in N."
- **§5.1** — ten printed lines in `commands/lab.py` say `Lab N (dev trials) is now <count>`,
  which is `dev_trial_count` (354 rows) and not the gate's N (74). **Explicitly out of scope.**
- **§6** — the dev store fingerprint is `77c37d553508…`; never rebuild on a fingerprint mismatch
  alone; a lab command migrates `lab/lab.sqlite` on connect even for a read.

### User-Provided Files

None marked with `@`. The handover path was given as the argument.

### Requirement IDs

| ID | What the user asked for |
|---|---|
| R1 | Build §4.1: the brakes-off variants on M0030 and M0053 — the `-FULL` arms of the exposure diagnostic, turned into real pre-registered, recorded lab variants |
| R2 | Build §4.2: interrogate the shared SPY 200-day gate that is nearly all one year of value and a drag since 2009 |
| R3 | Hold the hard constraint: these are VARIANTS of the existing method files, free in N, never new method ids — verified with `store.pending_gate` before committing to a shape |
| R4 | Hold the usual lab rules: pre-register by committing the method file before `lab run`; `lab stage` for any database commit; Postgres for DB tests; no hard-gate override; never touch the test window |
| R5 | Surface §5.1 (the ten `Lab N (dev trials)` strings) to the owner as a decision. Do not fix it |

---

## Detailed Requirements Understanding

### Problem / Requirement Statement

The exposure diagnostic that landed on 2026-10-12 ran every recorded dev variant of the five live
methods four ways and found exactly two configurations anywhere in the grid with a positive edge
over deposit-matched SPY in the 2009–2015 era: **M0030's picks at full size (+2.7/yr)** and
**M0053's picks at full size (+0.5/yr, +0.8 for the `TOTON20` pool)**. Those are diagnostic
columns — `ExposureAllocator` wrappers that exist in memory for the length of one run and write
no trial. Nothing in the lab holds "M0030 with the brakes off", so nothing can walk-forward it,
promote it, or ever spend a test look on it.

The same diagnostic found that four of the five books go to cash together on 28.3% of their
decision days because they sit behind the *same* SPY 200-day gate, and that this one shared rule
produced the identical +34.8 2008 lead in every book. The lab's recorded control
(`M0024-SAME-N20` vs `M0024-SAME-N20-NOTREND`) prices the gate as nearly all one year of value
and a drag for six.

Both findings must become **recorded dev trials under the existing method ids M0030 and M0053**,
because under the shipped `methods` N policy a new method id raises the luck hurdle for all 130
methods retroactively while variants of an existing method cost nothing.

### The blocker this analysis found

**The lab has no mechanism for adding variants to a method that has already run, and three
separate guards refuse it.** This is not a detail; it is the whole shape of the work.

1. `runner.preflight` (`engine/src/seer_engine/lab/runner.py:174`):
   `"{method.id} is already {status}: a method runs once. A change is a new variation method"`.
   Both M0030 and M0053 read `dev-eligible`.
2. The SQLite trigger `methods_source_sha_once` (`lab/store.py:490`) aborts any update that
   changes a non-NULL `source_sha`.
3. `test_a_method_that_ran_is_frozen` (`engine/tests/test_lab_methods.py:113`) asserts that every
   method with a recorded `source_sha` still hashes to it byte for byte.

And two readers depend on that freeze: `prereg.check_source` (`lab/prereg.py:440`) and
`remeasure` (`lab/remeasure.py:371`), both of which compare the live file's sha256 to the
recorded `source_sha`.

The handover's §4.1 asserts the shape ("variants of the existing method files costs zero N") and
is right about the **arithmetic** — this analysis verified that empirically — but the lab cannot
execute it today. The mechanism is the first deliverable.

### Success Criteria

- `store.pending_gate(conn, "M0030", k)` and `(conn, "M0053", k)` still return `Gate(n=74,
  policy='methods')` after the new trials are recorded, and `store.gate(conn).n` is still 74.
  The distinct-method count does not move.
- M0030 and M0053 each carry a dated, committed **amendment**: new candidates with their own
  hypothesis and expected-failure text, written before the run, whose commit is the
  pre-registration.
- Every candidate recorded before today still digests to exactly the `config_digest` the lab has
  on file, and every recorded trial row is untouched.
- `lab run` records the new trials under `method_id = 'M0030'` / `'M0053'`.
- A report-only `lab gate` diagnostic prices the shared SPY 200-day gate across every recorded
  dev variant that carries it, writing journal observations and no trials.
- `lab stage` is the only path that commits `lab/lab.sqlite` + `web/data/lab.json`, and CI's
  row-for-row check passes.
- The test window is never named. No `lab test`, no `lab promote`, no hard-gate override.
- §5.1 is written up as a decision for the owner and **not changed**.

### Key Considerations

**The predicted outcome is failure on drawdown, and that is the finding.** From the committed
grid: `M0030-*-FULL` is 20.4% max drawdown and `M0053-*-FULL` is 22.4–22.8%, against the owner's
20% bar. So the brakes-off variants are expected to be **ineligible**, clearing "beats SPY TR",
profit factor and trade count and breaching max DD by 0.4 to 2.8 points. Their value is not a
promotion; it is that the only post-2009 edge in this lab exists **only above the owner's risk
limit**, recorded rather than inferred from a diagnostic column. The hypothesis and the expected
failure must say this plainly before the run, or the result is unreadable afterwards.

**No existing params dataclass may gain or lose a field.** `registry._canon` renders a dataclass
by enumerating every `compare=True` field, so adding one field to `ResidParams`,
`FactorParams`, `OnParams` or `WeeklyOnParams` changes the `config_digest` of every recorded
candidate that uses it — which would break `prereg.check_digest`, `remeasure`, `lab costs` and
the test-window refusals at once. A no-brake variant therefore needs a **new** params type and a
**new** allocator id, never an edit to `WeeklyOnParams`.

**The gate is already expressible.** `m0007_residual_momentum.py` defines `TREND = ("SPY", 200)`,
`N20 = FactorParams(rank="momentum", top=20, trend=TREND)` and, since the method first ran,
`N20_NOTREND = FactorParams(rank="momentum", top=20, trend=None)`. M0007 already recorded an
`N20-NOTREND` variant. So §4.2's gate-off candidates need no new vocabulary — only `trend=None`
and, for M0030's blend core, `TimingParams(rule="always")`, which `ALWAYS_SPY` already is.

**`MAX_VARIANTS = 6` is per method today.** M0030 holds 3 recorded candidates, M0053 holds 5.
A two- or three-candidate amendment on M0053 exceeds 6 in total. The owner's own wording
(design §2: "scope = one idea with 1–6 fixed variants **per run**") settles it: the cap belongs
to the run, so an amendment carries 1–6 of its own and `candidates` keeps its own 1–6.

**Assumptions written down before the work:**
- `MONTHLY_HOLD_FRAC` (M0030's rules, flat 0.1% cost) is kept for M0030's amendment so the new
  variants are comparable with M0030's three recorded ones. `real_costs.requires_real_cost`
  exempts methods numbered ≤ M0030, so `runner.preflight` will not refuse them — the exemption is
  by method id, and an amendment does not change the id. M0053's amendment keeps
  `MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE`, already at Gotrade's real fees.
- A method's `source_sha` column stays exactly what it is. Amendments are recorded in a new,
  append-only table, so the first run's record is never rewritten.
- The dev store at `/home/miftah/seer/engine/.research` (fingerprint `77c37d553508…`, prices
  `5451195f…`) is used as-is. **No rebuild** (handover §6).

---

## Analysis Scope

### Explicitly Mentioned Files

- `docs/plans/HANDOVER_20261012-the-hurdle-counts-methods.md` — the argument

### Discovered Related Files

| File | Why it is here |
|---|---|
| `engine/src/seer_engine/lab/method.py` | `Method`, `config_text`/`config_digest`, `MAX_VARIANTS`, `discover`, `source_sha` |
| `engine/src/seer_engine/lab/runner.py` | `preflight` (the "runs once" refusal), `run_method`, `run_test` |
| `engine/src/seer_engine/lab/store.py` | schema, `methods_source_sha_once`, `gate`, `pending_gate`, `update_method`, `insert_trials` |
| `engine/src/seer_engine/lab/npolicy.py` | `dev_method_count`, `effective_n`, the `methods` policy and its participation-ratio floor |
| `engine/src/seer_engine/lab/prereg.py` | `check_source` — reads `source_sha` |
| `engine/src/seer_engine/lab/remeasure.py` | `source_sha` comparison before a re-measure |
| `engine/src/seer_engine/lab/exposure.py` | `ExposureAllocator`, `reweight`, `ERAS`, the arm/stat/grid machinery the gate probe reuses |
| `engine/src/seer_engine/lab/real_costs.py` | `requires_real_cost` / `real_cost_problem`, the M0031 rule |
| `engine/src/seer_engine/lab/hardgate.py` | `MIN_FOLDS`, the promotion gate (read only — never overridden) |
| `engine/src/seer_engine/lab/methods/m0030_spy_core_momentum_satellite.py` | the method amended by R1/R2 |
| `engine/src/seer_engine/lab/methods/m0053_overnight_winners_weekly_brake.py` | the method amended by R1/R2 |
| `engine/src/seer_engine/lab/methods/m0007_residual_momentum.py` | `RESIDMOM`, `ResidParams`, `TREND`, `N20`, `N20_NOTREND` |
| `engine/src/seer_engine/lab/methods/m0011_raw_residual_own_vol.py` | `RAW20 = ResidParams(N20, scaled=False)` |
| `engine/src/seer_engine/lab/methods/m0050_overnight_momentum.py` | `OnParams`, `build_legs`, `leg_sums`, `targets_from_rows` |
| `engine/src/seer_engine/backtest/registry.py` | `_canon` — why no params class may gain a field |
| `engine/src/seer_engine/backtest/dev.py` | `Candidate`, `run_registry`, `make_row`, the D8 conditions |
| `engine/src/seer_engine/commands/lab.py` | the CLI; the ten §5.1 strings (surfaced, not touched) |
| `db/migrations/` | where a new lab table does **not** go — `lab.sqlite`'s schema lives in `store.py` |
| `docs/plans/2026-10-04-method-lab-design.md` | §2 "1–6 fixed variants per run"; §4 "tuning is a new variation method" |
| `docs/backtests/2026-10-12-exposure-diagnostic.md` + `-grid.csv` | the measured numbers every hypothesis here is written against |
| `engine/tests/test_lab_methods.py`, `test_lab_runner.py`, `test_lab_prereg.py`, `test_lab_store.py`, `test_lab_npolicy.py`, `test_lab_exposure.py` | the tests that pin the freeze and the gate |

---

## Current Dataflow

### Entry Point: `python -m seer_engine lab run MNNNN`

**Location:** `engine/src/seer_engine/commands/lab.py:181` (parser), dispatching into
`lab/runner.py:run_method` (`runner.py:443`)
**Trigger:** CLI subcommand
**Input:** a method id, `--store`, `--allow-coverage`

**Validation chain (`runner.preflight`, `runner.py:158`):**

1. `registry_problem(path)` — the method file must be committed and unmodified in git. *The
   commit is the pre-registration.*
2. `real_costs.real_cost_problem(method)` — from M0031 on, every variant must be at
   `cost_model="gotrade"`. **Keyed on the method id**, so M0030 stays exempt and M0053 stays
   bound.
3. `store.get_method(conn, method.id)` — **refuses any status outside `idea` / `registered`**
   with *"a method runs once"*. ← **the blocker**
4. `parent_id` must exist in the lab.
5. Per candidate: `store.has_trial(conn, config_digest(c), "dev")` — a repeated configuration is
   refused by digest, not by name.

**Then:** `research.load_store` → `preflight_data` (fundamentals coverage) →
`dev.run_registry(...)` with no `window=` keyword (the D9 dev default binds) → `daily_moments`
→ **`store.pending_gate(conn, method.id, len(results))`** → `dev.deflated_sharpe` per trial →
eligibility against the five D8 conditions + `store.DSR_LABEL` → one transaction:
`store.insert_trials`, `store.update_method(..., source_sha=source_sha(path), status=...)`.

### The N computation — the hard constraint, traced

```
store.gate(conn)                       lab/store.py:1117
  └─ npolicy.effective_n(conn, "methods")              lab/npolicy.py (effective_n)
       ├─ store.dev_trial_count(conn)      → 354   (rows; NOT the gate's N)
       ├─ npolicy.dev_method_count(conn)   → 74    SELECT count(DISTINCT method_id)
       │                                             FROM trials WHERE window='dev'
       ├─ correlation(conn).participation_ratio → 2.19
       └─ n = max(74, ceil(2.19)) = 74

store.pending_gate(conn, method_id, pending)          lab/store.py:1149
  └─ policy == "methods":
       SELECT 1 FROM trials WHERE method_id=? AND window='dev' LIMIT 1
       seen  → Gate(74)      ← M0030, M0053
       unseen→ Gate(75)      ← any new method id
```

**Measured in this session, on a copy of the committed `lab/lab.sqlite` (md5 `4a34ddb8`, restored
unchanged):**

```
gate: Gate(n=74, policy='methods')        DSR_POLICY = 'methods'
dev_trial_count: 354        distinct dev methods: 74
M0030 pending_gate(2) -> Gate(n=74)   pending_gate(4) -> Gate(n=74)
M0053 pending_gate(2) -> Gate(n=74)   pending_gate(4) -> Gate(n=74)
M9999 pending_gate(2) -> Gate(n=75)   pending_gate(4) -> Gate(n=75)
```

R3 is therefore satisfied by construction *provided* the trials are recorded under the existing
`method_id`. The only thing that can break it is minting a method id.

### The freeze, traced

```
run_method (runner.py:548)
  store.update_method(conn, id, source_sha=source_sha(path), status=...)
     └─ store.py:490  TRIGGER methods_source_sha_once
          WHEN OLD.source_sha IS NOT NULL AND NEW.source_sha IS NOT OLD.source_sha
          -> ABORT 'source_sha is set once, when the method runs'

test_lab_methods.py:113  test_a_method_that_ran_is_frozen
  for every methods row with source_sha NOT NULL:
      assert source_sha(METHODS[id].path) == row["source_sha"]

prereg.check_source (prereg.py:440)   -- lab test
  recorded = row["source_sha"];  actual = source_sha(path);  must match

remeasure (remeasure.py:371)          -- lab remeasure
  same comparison
```

### `Method` validation — why the shape is constrained

`lab/method.py:60` `Method.__post_init__`:
- `candidates` must be a tuple of 1..`MAX_VARIANTS` (6)
- every candidate id must start with `<method id>-`
- every candidate's `family` must equal the method id
- no duplicate candidate id, **no duplicate `config_digest` within the method**

`lab/method.py:96` `discover()` refuses two modules claiming one id and refuses a module whose
file number disagrees with `METHOD.id`. So "a second file that records under M0030" is not
expressible, and the amendment must live in M0030's own file.

### `config_digest` — what a trial is identified by

`lab/method.py:33`:
```
config_text(c) = "rules=<_canon(c.rules)>\nallocator=<c.allocator.id>\nparams=<_canon(c.params)>\n"
config_digest  = sha256(config_text)
```
`registry._canon` (`backtest/registry.py:302`) renders a dataclass as
`",".join(f"{f.name}={_canon(...)}" for f in fields(value) if f.compare)`. **Adding a field to a
params dataclass changes every recorded digest that uses it.**

### `lab exposure` — the measurement these variants come from

`lab/exposure.py` wraps each recorded candidate's allocator in an `ExposureAllocator` and
re-weights its targets four ways (`BOOK` / `PICKS` / `FULL` / `PARK`, `exposure.py:215`
`reweight`). `FULL` drops the parked targets (`set(allocator.holds(params)) |
{rules.idle_symbol}`) and rescales the survivors to fill the book — **which is exactly "the same
picks with the brake switched off"** for a method with no park set, and "the satellite alone at
full size" for a blend. Nothing is recorded but journal observations.

Two facts read out of the committed grid, which the new candidates must reproduce if they are
built correctly:

- Every `M0030-*` `-FULL` row is **identical** (+7.5 whole, +2.7 for 2009–2015, 20.4% DD,
  15.4%/yr) across `C70T`, `C50T` and `C50A` — because dropping `SPY` and rescaling leaves
  `RESIDMOM`/`RAW20` alone at 100% whatever the core share was.
- Every `M0053-TOTON20-TV*` `-FULL` row is identical (+7.7 whole, **+0.8** for 2009–2015, 22.8%
  DD), and `RESON20-TV16`'s is +7.2 / **+0.5** / 22.4% — because the brake is a scalar on the
  whole basket, so rescaling to fill the book undoes it exactly.

### Data Persistence

**`lab/lab.sqlite`** (committed, append-only via triggers; schema in `lab/store.py`):
- `methods` — one row per idea; `source_sha` set once; `status` forward-only
- `trials` — append-only; `UNIQUE(config_digest, window)`; `method_id` is what N counts
- `trial_moments`, `trial_funding`, `trial_provenance`, `insights`, `ideas_seen`

**`web/data/lab.json`** — written by `lab stage` / `lab export-json`; CI checks it agrees with
`lab.sqlite` row for row. Carries `gate.dsrN` (74) and `gate.dsrNBasis`.

A lab command **migrates `lab/lab.sqlite` on connect, even for a read** (handover §6). Any
read-only probe must hash the file first and restore it by explicit path afterwards.

### Exit Points

- stdout: the run summary and the ten `Lab N (dev trials) is now …` lines (§5.1, untouched)
- `lab/lab.sqlite`: new `trials` / `trial_moments` / `trial_funding` / `insights` rows
- `web/data/lab.json`: regenerated by `lab stage`
- exit codes: 0 ok, **2 the lab's rules refused the request**, 1 error

---

## Key Data Structures

### `Method` — `engine/src/seer_engine/lab/method.py:47`
```
id, name, family, source_kind, source_ref, hypothesis, expected_failure,
candidates: tuple[Candidate, ...]          # 1..6
parent_id: str | None, seen_keys: tuple[str, ...]
```
**Used in:** `discover()`, `runner.preflight`, `runner.run_method`, `prereg`, `remeasure`,
`exposure`, `real_costs`, `name_count`, every `test_lab_*`.

### `Candidate` — `engine/src/seer_engine/backtest/dev.py:~180`
`id`, `family` (must be `F1..F11`, `REF` or a lab method id), `rules`, `allocator`, `params`,
`rationale`, `added`, `owner_inputs`.

### `Gate` / `NCount` — `lab/store.py`, `lab/npolicy.py`
`Gate(n, policy)`; `NCount(n, policy, trial_rows, distinct_methods, participation_ratio, …)`
with `.basis` written verbatim into `docs/lab/prereg/MNNNN.md` and `web/data/lab.json`.

### The gate vocabulary
- `m0007_residual_momentum.py:342` `TREND = ("SPY", 200)`
- `:343` `N20 = FactorParams(rank="momentum", top=20, trend=TREND)`
- `:346` `N20_NOTREND = FactorParams(rank="momentum", top=20, trend=None)`
- `m0011_raw_residual_own_vol.py:107` `RAW20 = ResidParams(N20, scaled=False)`
- `m0030_*.py` `TIMED_SPY = TimingParams(hold="SPY", signal="SPY", rule="sma", n=200)`,
  `ALWAYS_SPY = TimingParams(hold="SPY", signal="SPY", rule="always")`
- `f_factor.trend_on(history, date, params)` is the single read every gated book shares

### Digest collision check — run in this session, all four free

| proposed candidate | rules | allocator | digest | status |
|---|---|---|---|---|
| `M0030-SAT100` | `monthly-hold-frac` | `RESIDMOM` | `542c1b9e439a…` | free |
| `M0030-SAT100-NOGATE` | `monthly-hold-frac` | `RESIDMOM` | `5d00ec7cafc0…` | free |
| `M0053-RESON20-TV16-NOGATE` | `monthly-rank-weekly-resize-frac-gotrade` | `M0053` | `76de74aab178…` | free |
| `M0053-TOTON20-TV16-NOGATE` | `monthly-rank-weekly-resize-frac-gotrade` | `M0053` | `b193a748a421…` | free |

(`M0007`/`M0011` all ran on `monthly-hold`, M0029 on `monthly-hold-frac` with the `BLEND`
allocator, so `monthly-hold-frac` + `RESIDMOM` is unclaimed.)

---

## Dependencies

### Configuration / Environment
- `SEER_LAB_DB` — parallel sessions share lab state through it; defaults to `lab/lab.sqlite`
- `SEER_RESEARCH_STORE` / `--store` — **the research store is not in worktrees**; point at
  `/home/miftah/seer/engine/.research` (dev, fingerprint `77c37d553508…`, prices `5451195f…`)
- `PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres` — container `seer-pg` is **Up**
- `PYTHONPATH=<worktree>/engine/src` with the main checkout's venv, or pytest silently tests
  `main`

### External Services
None. The lab is offline: SQLite plus CSVs in the research store.

---

## Reference List

Every site that touches the method freeze, the N, or the two method files.

| Symbol / key | File:line | Kind | Package | Phase |
|---|---|---|---|---|
| `MAX_VARIANTS = 6` | `lab/method.py:30` | def | lab | 1 |
| `Method.__post_init__` candidates cap | `lab/method.py:77` | def | lab | 1 |
| `Method` dataclass | `lab/method.py:47` | def | lab | 1 |
| `source_sha()` | `lab/method.py:127` | def | lab | 1 |
| `discover()` | `lab/method.py:96` | def | lab | 1 |
| module docstring "frozen once it has run" | `lab/method.py:11` | doc | lab | 1 |
| `preflight` "a method runs once" | `lab/runner.py:174-178` | def | lab | 1 |
| `run_method` sets `source_sha` | `lab/runner.py:548` | call | lab | 1 |
| `run_test` re-checks `source_sha` | `lab/runner.py:717-718` | call | lab | 1 |
| runner module docstring (steps 1–4) | `lab/runner.py:4-20` | doc | lab | 1 |
| `methods.source_sha` column | `lab/store.py:396` | config | lab | 1 |
| `TRIGGER methods_source_sha_once` | `lab/store.py:490-492` | config | lab | 1 |
| `update_method` allowed columns | `lab/store.py:753` | def | lab | 1 |
| `record_promotion` never touches `source_sha` | `lab/store.py:827` | doc | lab | 1 |
| `gate()` | `lab/store.py:1117` | def | lab | — (read only) |
| `pending_gate()` | `lab/store.py:1149` | def | lab | — (read only) |
| `dev_method_count()` | `lab/npolicy.py` | def | lab | — (read only) |
| `prereg.check_source` | `lab/prereg.py:440-460` | def | lab | 1 |
| prereg module docstring point 2 | `lab/prereg.py:18` | doc | lab | 1 |
| `remeasure` sha comparison | `lab/remeasure.py:328,371-377` | def | lab | 1 |
| `hardgate` "frozen by its source_sha" | `lab/hardgate.py:343` | doc | lab | 1 |
| `name_count` "M0007's file is not touched" | `lab/name_count.py:36` | doc | lab | — |
| `real_cost_problem` / `requires_real_cost` | `lab/real_costs.py:54-69` | def | lab | 1 (read) |
| `_canon` dataclass rendering | `backtest/registry.py:302-332` | def | backtest | — (constraint) |
| `lab run` parser | `commands/lab.py:181-195` | config | commands | 1 |
| the ten `Lab N (dev trials)` strings | `commands/lab.py:1399,1684,1718,1739,1785,1817,1870,1923,2238,2287` | call | commands | **none — R5 surfaces only** |
| `test_a_method_that_ran_is_frozen` | `tests/test_lab_methods.py:113-129` | test | tests | 1 |
| `test_source_sha_is_set_once` | `tests/test_lab_store.py:205-210` | test | tests | 1 |
| `test_record_promotion_…_never_touches_source_sha` | `tests/test_lab_store.py:329-338` | test | tests | 1 |
| prereg source tests | `tests/test_lab_prereg.py:188-211,293-325` | test | tests | 1 |
| `test_lab_runner.py` `source_sha` assert | `tests/test_lab_runner.py:87` | test | tests | 1 |
| lab-state snapshot asserts (`SELECT id, status, verdict, source_sha`) | `tests/test_lab_name_count.py:53`, `test_lab_costs.py:79`, `test_lab_survivorship.py:153`, `test_lab_exposure.py:166` | test | tests | 1 |
| `ExposureAllocator`, `reweight`, `ERAS` | `lab/exposure.py:259,215,132` | def | lab | 2 (reused) |
| `METHOD` M0030 | `lab/methods/m0030_spy_core_momentum_satellite.py` | def | lab/methods | 3 |
| `METHOD` M0053 | `lab/methods/m0053_overnight_winners_weekly_brake.py` | def | lab/methods | 4 |
| `TREND`, `N20`, `N20_NOTREND`, `ResidParams`, `RESIDMOM` | `lab/methods/m0007_residual_momentum.py:342-346` | def | lab/methods | 3,4 (imported) |
| `RAW20` | `lab/methods/m0011_raw_residual_own_vol.py:107` | def | lab/methods | 3 (imported) |
| `OnParams`, `build_legs`, `leg_sums`, `targets_from_rows` | `lab/methods/m0050_overnight_momentum.py` | def | lab/methods | 4 (imported) |
| design §2 "1–6 fixed variants per run" | `docs/plans/2026-10-04-method-lab-design.md:16,42` | doc | docs | 6 |
| design §4 "tuning is a new variation method" | `docs/plans/2026-10-04-method-lab-design.md:~92` | doc | docs | 6 |

---

## Impact Points (files that WILL need changes)

1. `engine/src/seer_engine/lab/method.py` — the `Amendment` value, `Method.amendments`, the
   per-amendment cap, `all_candidates()`, the docstring that says a file is frozen. **Phase 1.**
2. `engine/src/seer_engine/lab/store.py` — the `method_amendments` table + its append-only
   trigger, `insert_amendment`, `amendments_of`, `latest_source_sha`. **Phase 1.**
3. `engine/src/seer_engine/lab/runner.py` — `preflight` learns the amendment path; `run_method`
   records the amendment row and leaves `methods.source_sha` alone; `run_test` checks the
   *latest* recorded sha. **Phase 1.**
4. `engine/src/seer_engine/lab/prereg.py` — `check_source` against the latest recorded sha.
   **Phase 1.**
5. `engine/src/seer_engine/lab/remeasure.py` — the same comparison. **Phase 1.**
6. `engine/src/seer_engine/commands/lab.py` — the `run` subcommand's `--amend` flag and its
   summary. **Phase 1.** (The ten §5.1 N strings are *not* touched.)
7. `engine/tests/test_lab_methods.py` — the freeze test becomes "hashes to the latest recorded
   sha, and every recorded candidate still digests to its recorded digest". **Phase 1.**
8. `engine/tests/test_lab_store.py`, `test_lab_prereg.py`, `test_lab_runner.py` — the new table,
   the amendment refusals. **Phase 1.**
9. `engine/src/seer_engine/lab/gate_probe.py` (new) + `engine/tests/test_lab_gate_probe.py` —
   the report-only `lab gate` diagnostic. **Phase 2.**
10. `engine/src/seer_engine/commands/lab.py` — the `gate` subcommand. **Phase 2.**
11. `engine/src/seer_engine/lab/methods/m0030_spy_core_momentum_satellite.py` — the amendment
    block and its candidates. **Phase 3.**
12. `engine/src/seer_engine/lab/methods/m0053_overnight_winners_weekly_brake.py` — the no-brake
    allocator, its params type, the amendment block. **Phase 4.**
13. `lab/lab.sqlite` + `web/data/lab.json` — the recorded trials and the staged snapshot, through
    `lab stage` only. **Phase 5.**
14. `docs/backtests/2026-10-12-brakes-and-gate.md` (+ grid CSV) — the write-up. **Phase 5.**
15. `docs/plans/2026-10-04-method-lab-design.md` — a dated revision recording the amendment rule.
    **Phase 6.**
16. `docs/plans/2026-10-12-lab-n-and-amendments-owner-decision.md` (new) — R5's surfacing, plus
    the amendment's own integrity trade-off. **Phase 6.**

**This document describes. The plan files prescribe.**
